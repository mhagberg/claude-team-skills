---
name: onboard-customer-postcall
description: Post-call wiring for a new DataXcel customer — finalise profiles.yml, push single_customers.py entry, trigger the dbt DAG, add the Metabase DB connection, sync schema, and clone the dashboard seed-set. Run after customer IT confirms NetBird is up.
---

# onboard-customer-postcall

You are running the **onboard-customer-postcall** skill. Goal: take the
NetBird IP the customer just produced, wire it into our dbt + Metabase
stack, and seed the customer's dashboards.

**Execution mode:** local edits and read-only checks run unprompted. Git
pushes, kubectl apply, Metabase API writes, dbt DAG triggers all require an
explicit `yes` confirmation showing exactly what will run.

## Step 1 — validate args

Required:
- `<slug>` — must match the slug used in `/onboard-customer-precall`.
- `--netbird-ip <ip>` — IPv4 address the customer's IT person read off after
  running `connect-netbird.ps1` (typically `100.x.x.x` in the NetBird mesh).

Optional:
- `--sql-port <port>` — if missing, look it up from the customer's row in
  `XcelConnectAndUpdater/CLAUDE.md` (the setup-keys / customer table). If
  that lookup fails, prompt the user.

Validate IP format with a basic regex. Print a one-line plan summary before
running anything.

## Step 2 — broker reachability check (read-only)

If an SSH key for `mike@100.67.235.51` is available locally (test with
`ssh -o BatchMode=yes -o ConnectTimeout=3 mike@100.67.235.51 echo ok`), run:

```bash
ssh mike@100.67.235.51 "ping -c 2 -W 2 <netbird-ip>"
```

If reachable: print "OK". If not: print a warning but continue — the dbt DAG
trigger in Step 4 will be the real end-to-end check. Do NOT block the skill on
this — sometimes the SSH key isn't present.

## Step 3 — fill profiles.yml + push (RISKY — confirm push)

Edit
`/Users/mike/dev/projects/etl_pipeline/airflow/sage_dbt/profiles.yml` in
place. Find the `<slug>_dataxcel_analytics` block drafted by the pre-call
skill (or the `<NETBIRD_IP_TBD>` placeholder). Replace the placeholder with
`<netbird-ip>` and the port placeholder with `<sql-port>`.

If the block isn't there: stop and tell the user the pre-call draft was never
pasted in. Print the block again and ask them to paste it manually, then
re-run this skill.

Confirm:

> Stage and commit profiles.yml on `etl_pipeline` with message
> `chore(profiles): add <slug> Sage DW connection`? Push to origin? Type
> `yes`.

On `yes`:

```bash
git -C /Users/mike/dev/projects/etl_pipeline add airflow/sage_dbt/profiles.yml
git -C /Users/mike/dev/projects/etl_pipeline commit -m "chore(profiles): add <slug> Sage DW connection"
git -C /Users/mike/dev/projects/etl_pipeline push
```

## Step 4 — single_customers.py entry + push (RISKY — confirm push)

Edit
`/Users/mike/dev/projects/etl_pipeline/airflow/dags/utils/single_customers.py`
to add `DBTConfig(customer="<slug>", snapshots=True)`. Match the existing
list's formatting/indent — read the file first to see the convention.

(If the customer is multi-company, the user must instead add a `RollupConfig`
entry in `rollup_customers.py`. Ask the user: "Single-company or
multi-company (rollup)?" before editing. The default is single.)

Confirm push:

> Commit single_customers.py change with message
> `feat: add <slug> to dbt customer registry (snapshots=True)`? Push to
> origin? Type `yes`.

On `yes`, commit + push.

## Step 5 — trigger dbt DAG (RISKY — confirm)

Confirm:

> Trigger Airflow DAG `<slug>_dataxcel_analytics_dbt_dag` via SSH to
> `mike@100.67.235.51`? This kicks off the first dbt build for the customer.
> Type `yes`.

On `yes`, ask the user for the sudo password (do NOT hardcode). Then:

```bash
ssh mike@100.67.235.51 "echo '<password>' | sudo -S docker exec airflow-airflow-scheduler-1 \
  airflow dags trigger <slug>_dataxcel_analytics_dbt_dag"
```

Tail logs for ~30 seconds via `docker exec` against the scheduler. Stop
tailing once the user sees the DAG is queued. If the DAG name isn't
recognized, tell the user to wait 30s for the Airflow scheduler tick and
re-run.

## Step 6 — Add peer to Sage100ContractorDatabases (RISKY — confirm)

Now that the customer peer EXISTS in NetBird, retry the group add that was
deferred in the pre-call skill. Show the user the exact curl chain from
`XcelConnectAndUpdater/CLAUDE.md` Dietrich-fix section with `<slug>` filled
in, ask for `yes`, run it.

This is the canonical gotcha — Metabase pods cannot reach the customer Sage
box without this. If you skip it, Step 7 will fail.

## Step 7 — Metabase DB connection + schema sync (RISKY — confirm)

POST to `<metabase-url>/api/database` to create the database connection.

Resolve `<metabase-url>` as `https://<slug>.xcel.report`. Resolve API token:
look in `~/.config/dataxcel/metabase-tokens.json` for `<slug>`; if missing,
prompt the user.

Confirm:

> POST to `<metabase-url>/api/database` with:
>   name: "Sage DW (<slug>)"
>   engine: sqlserver
>   host: <netbird-ip>
>   port: <sql-port>
>   db: dataxcel_analytics
>   user: dataxcel
>
> Type `yes`.

On `yes`, run the POST via curl. Capture the returned `database_id`. Then
POST `<metabase-url>/api/database/<id>/sync_schema_now` (same auth). If
either call returns non-2xx, print the error and stop.

## Step 8 — clone dashboard seed-set (RISKY — confirm per dashboard)

Look for the seed-set list at
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/claude-team-skills/skills/onboard-customer-postcall/seed_dashboards.txt`
(one dashboard ID per line, optional `# comment` allowed). If the file is
missing, prompt the user for the list interactively.

For each dashboard ID:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/metabase-migration
python pmbql_migrate.py --client <slug> --dashboard <id> --dry-run
```

Show the dry-run output. Ask:

> Apply this dashboard clone for real? Type `yes`.

On `yes`, run again without `--dry-run`. Move to the next dashboard. If a
dashboard fails, stop the loop and tell the user — do NOT continue blindly.

## Step 9 — update XcelConnectAndUpdater/CLAUDE.md customer table (RISKY — confirm push)

Append a row to the customer table in
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md`
with date, NetBird IP, SQL port, status `live`. Match the existing column
order.

Confirm:

> Commit + push XcelConnectAndUpdater/CLAUDE.md with row for `<slug>`? Type
> `yes`.

On `yes`:

```bash
git -C /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater add CLAUDE.md
git -C /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater commit -m "docs: add <slug> to customer table"
git -C /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater push
```

## Step 10 — summary + next steps

```
Customer: <slug>
NetBird IP: <netbird-ip>
SQL port: <port>
dbt DAG: triggered (check Airflow UI)
Metabase DB: id=<database_id>, schema synced
Dashboards cloned: <count>

Next:
  1. /onboard-customer-hub <slug>
  2. /onboard-customer-briefing <slug>   (default: 60-day trial; add --paid if customer has purchased)
```

Stop.
