---
name: onboard-customer-postcall
description: Post-call wiring for a new DataXcel customer — fills profiles.yml with the real NetBird IP / SQL port / Sage DB / dataxcel password (either from CLI flags or from XcelConnectAndUpdater/CLAUDE.md if omitted), pushes single_customers.py entry, triggers the dbt DAG, adds the Metabase DB connection, syncs schema, and clones the dashboard seed-set. Run after `/onboard-customer-oncall <slug>` has reported all four values.
---

# onboard-customer-postcall

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer-postcall <slug>` becomes `/onboard-customer-postcall lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer-postcall** skill. Goal: take the
four values `/onboard-customer-oncall` captured (NetBird IP, SQL port,
Sage DB name, `dataxcel` password) and wire them into the dbt + Metabase
+ Hub stack.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug used in `/onboard-customer-precall` and `/onboard-customer-oncall`. |
| `--netbird-ip <ip>` | Optional (preferred) | Printed by `connect-netbird-<slug>.ps1` on Chris's screen during the call; captured by `/onboard-customer-oncall` Step 3 and written to the customer table in `XcelConnectAndUpdater/CLAUDE.md`. |
| `--sql-port <port>` | Optional | Same — auto-detected by `connect-netbird.ps1` from the Sage SQL registry, captured by `/onboard-customer-oncall` Step 3. |
| `--sage-db "<DB Name>"` | Optional | Discovered by `/onboard-customer-oncall` Step 6 via `SELECT name FROM sys.databases` + Mike's confirmation of which is the live company DB. |
| `--dataxcel-pw '<pw>'` | Optional | Picked by Chris when running `setup-sage-sysadmin.ps1`; captured by `/onboard-customer-oncall` Step 5. |

If any of the four optional flags are omitted, the skill **reads them from
the customer credentials table in
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md`**
(the on-call skill just wrote them there). Pass-by-flag is supported for
re-runs or when the operator wants to override a single value.

If all four are missing AND the customer table doesn't have a row for
`<slug>`, stop and tell the user: "Run `/onboard-customer-oncall <slug>`
first — the call values haven't been captured yet."

**Execution mode:** local edits and read-only checks run unprompted. Git
pushes, kubectl apply, Metabase API writes, dbt DAG triggers all require
an explicit `yes` confirmation showing exactly what will run.

## Step 1 — validate + resolve args

Required:
- `<slug>` — must match the slug used in `/onboard-customer-precall` and
  `/onboard-customer-oncall`.

Optional (with fallback lookup from `XcelConnectAndUpdater/CLAUDE.md`):
- `--netbird-ip <ip>` — IPv4 in the NetBird CGNAT range (`100.x.x.x`).
- `--sql-port <port>` — integer 1–65535.
- `--sage-db "<DB Name>"` — exact Sage company DB name.
- `--dataxcel-pw '<pw>'` — `dataxcel` SQL login password.

Resolution order per value: CLI flag → row in
`XcelConnectAndUpdater/CLAUDE.md` SQL Credentials + NetBird Customers
tables → stop with error.

Validate the NetBird IP regex (`^100\.\d{1,3}\.\d{1,3}\.\d{1,3}$`) and
port range. Print a one-line plan summary with all four resolved values
(mask the password to `<pw>` in the print) before running anything.

## Step 2 — broker reachability check (read-only)

If an SSH key for `mike@100.67.235.51` is available locally (test with
`ssh -o BatchMode=yes -o ConnectTimeout=3 mike@100.67.235.51 echo ok`),
run:

```bash
ssh mike@100.67.235.51 "nc -zv <netbird-ip> <sql-port>"
```

If reachable: print "OK". If not: print a warning but continue — the dbt
DAG trigger in Step 5 will be the real end-to-end check. Do NOT block the
skill on this — sometimes the SSH key isn't present.

## Step 3 — fill profiles.yml + push (RISKY — confirm push)

Edit
`/Users/mike/dev/projects/etl_pipeline/airflow/sage_dbt/profiles.yml` in
place. Find the `<slug>:` block (the pre-call skill prints the draft; the
operator may or may not have pasted it in yet).

**If the block isn't there yet:** insert it using the pre-call template
shape with the FOUR resolved values substituted:

```yaml
<slug>:
  target: prod
  outputs:
    prod:
      type: sqlserver
      driver: ODBC Driver 18 for SQL Server
      server: "<netbird-ip>"
      port: <sql-port>
      database: "<sage-db>"
      schema: dbx_tests
      user: dataxcel
      password: "<dataxcel-pw>"
      threads: 4
      trust_cert: true
```

**If the block already has `<NETBIRD_IP_TBD>` / `<SQL_PORT_TBD>` /
`<SAGE_DB_TBD>` / `<DATAXCEL_PW_TBD>` placeholders:** replace each with
the resolved value.

**If the block is already filled in but with different values:** stop and
print a diff. Ask the user to confirm overwriting.

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
to add `DBTConfig(customer="<slug>", schedule="45 13-23 * * *",
snapshots=True)`. Match the existing list's formatting/indent — read the
file first to see the convention.

(If the customer is multi-company (rollup), the on-call skill flagged
this — instead add a `RollupConfig` entry in `rollup_customers.py`. Use
the slug + per-company list from `--sage-db` if it's comma-separated.)

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

## Step 6 — Metabase DB connection: UPDATE existing id=2 (RISKY — confirm)

> **CRITICAL.** A freshly-cloned tenant via `duplicate_single.sh` already
> has a database row at id=2 — it carries over from the demo and still
> points at the demo's warehouse (for `single.xcel.report` clones that's
> Vertex Coatings' anonymized SQL Server at `100.67.89.249:50285`, user
> `jobxcel`, db `Vertex Coatings Anonymize Reporting`). Renaming in the
> Metabase admin UI does NOT fix this — the connection details must be
> updated via the REST API. Until that happens, every dashboard, every
> validation, every "Sage vs Metabase" comparison runs against the wrong
> warehouse.
>
> This step UPDATES that existing id=2 row. The configure-customer-metabase
> skill re-verifies the same connection later as Step 0 — belt-and-suspenders.

Resolve `<metabase-url>` as `https://<slug>.xcel.report`. Resolve API
token: default to the shared single.xcel.report key
`mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=` unless `<slug>` is in
the dedicated-instance set (`dd`, `brekhus`, `jolma`, `vertex`, `4x`,
`burbach`, `ipwlc`, `nvision`, `pcg`), in which case read the row from
`XcelConnectAndUpdater/CLAUDE.md` Metabase Instances & API Keys table.

### 6.1 Read the current state (read-only)

```
GET <metabase-url>/api/database/2
```

Three possible outcomes:

1. **id=2 exists and points at the demo's host** (the common case for a
   freshly-cloned tenant). Proceed to 6.2 — UPDATE.
2. **id=2 exists and already points at the customer's NetBird IP +
   dataxcel_analytics** (this skill was re-run). Skip 6.2, jump to 6.3 to
   re-verify.
3. **id=2 does NOT exist** (rare — only if a human manually deleted it).
   Fall back to `POST <metabase-url>/api/database` with the same body
   shape from 6.2, capture the returned id, and use that id everywhere
   below (sync, smoke query).

### 6.2 Update the connection (confirm)

Confirm with the exact URL + body:

> PUT to `<metabase-url>/api/database/2` with:
>   name: "<Customer> Analytics"
>   engine: sqlserver
>   details.host: <netbird-ip>
>   details.port: <sql-port>
>   details.db: dataxcel_analytics
>   details.user: dataxcel
>   details.password: <dataxcel-pw>
>   details.ssl: true
>   details.trust-server-certificate: true
>   details.additional-options: "trustServerCertificate=true"
>
> Type `yes`.

On `yes`:

```
PUT <metabase-url>/api/database/2
Headers:
  x-api-key: <api-key>
  Content-Type: application/json
Body:
{
  "name": "<Customer> Analytics",
  "engine": "sqlserver",
  "details": {
    "host": "<netbird-ip>",
    "port": <sql-port>,
    "db": "dataxcel_analytics",
    "user": "dataxcel",
    "password": "<dataxcel-pw>",
    "ssl": true,
    "trust-server-certificate": true,
    "additional-options": "trustServerCertificate=true"
  }
}
```

> **Why BOTH `ssl: true` AND `additional-options:
> "trustServerCertificate=true"` are required.** `ssl: true` is
> Metabase's API model for the GUI "Use a secure connection (SSL)"
> toggle — without it the connection is unencrypted and fails customer
> security review (and may not connect at all to SQL Servers that
> require encryption). `additional-options:
> "trustServerCertificate=true"` is the literal JDBC connection-string
> option appended to the SQL Server JDBC URL (Metabase GUI: "Additional
> JDBC connection string options"). The top-level
> `trust-server-certificate: true` is Metabase's API model for the GUI
> toggle of the same name; `additional-options` is the literal string
> the driver actually consumes. They are NOT redundant — some Metabase
> versions only respect one, and some SQL Server JDBC driver versions
> ignore one without the other. Both must be present. Customer Sage
> servers behind NetBird present self-signed certs, so without
> trust-server-certificate the encrypted handshake fails.

Then trigger the schema sync:

```
POST <metabase-url>/api/database/2/sync_schema
```

(Note: `/sync_schema`, not `/sync_schema_now` — Metabase v0.61+ uses the
shorter path. Both 200 and 202 are success on this stack.)

### 6.3 Verify with a fresh GET (REQUIRED — do NOT trust the PUT echo)

Metabase echoes the PUT body back in the response even on edge-case
persistence failures. The only honest check is a follow-up read:

```
GET <metabase-url>/api/database/2
→ assert details.host == <netbird-ip>
→ assert details.port == <sql-port>
→ assert details.db == "dataxcel_analytics"
→ assert details.user == "dataxcel"
→ assert details.ssl == True
→ assert details["additional-options"] == "trustServerCertificate=true"
→ assert details["trust-server-certificate"] == True
```

Then a smoke query against a table that only exists in the customer's
real warehouse:

```
POST <metabase-url>/api/dataset
{"database":2,"type":"native","native":{"query":"SELECT TOP 1 ledger_account_id FROM dbo.Ledger_Accounts_by_Month"}}
```

Must return rows. If it errors with `Cannot open database 'Vertex
Coatings Anonymize Reporting' requested by the login. The login failed.`
(or any reference to the demo's DB name), the PUT didn't take — stop and
tell the user. Do NOT continue to Step 7 until this smoke query succeeds.

Print:

```
MB DB id=2 now points at <netbird-ip>:<sql-port>/dataxcel_analytics — smoke query OK.
```

## Step 7 — clone dashboard seed-set (RISKY — confirm per dashboard)

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

## Step 8 — summary + next steps

```
Customer: <slug>
NetBird IP: <netbird-ip>
SQL port: <sql-port>
Sage DB: <sage-db>
dbt DAG: triggered (check Airflow UI)
Metabase DB: id=<database_id>, schema synced
Dashboards cloned: <count>

Next:
  1. /onboard-customer-hub <slug>
  2. /configure-customer-metabase <slug>
  3. /validate-hub-dashboards <slug>
  4. /validate-customer-metabase <slug>
  5. /onboard-customer-briefing <slug>   (default: 60-day trial; add --paid if customer has purchased)
  6. /finalize-customer-metabase <slug> --users <email1>,<email2> [--admin-users ...]
```

Stop.
