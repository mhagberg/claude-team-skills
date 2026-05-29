---
name: onboard-customer-precall
description: Pre-call staging for a new DataXcel customer — NetBird provision, per-customer Sage SQL script, EKS Metabase tenant, and drafts of profiles.yml + single_customers.py entries. Run ~30 min before the IT meeting.
---

# onboard-customer-precall

You are running the **onboard-customer-precall** skill. Goal: get ~99% of a new
customer's infrastructure staged BEFORE the IT call. The on-call work is then
just (a) customer IT runs two scripts, (b) you capture the NetBird IP for the
post-call skill.

Source of truth for the full process:
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/docs/new-customer-onboarding.html`.

**Execution mode:** local file edits and read-only checks run without prompting.
Anything that writes to a remote (NetBird API, kubectl apply, Git push,
Metabase API) MUST ask for explicit `yes` confirmation first, showing exactly
what will happen.

## Step 1 — validate args

Required:
- `<slug>` — customer slug, lowercase alnum+dashes only. Regex `^[a-z0-9-]+$`.

Optional (prompt if missing):
- `--sql-port <port>` — Sage SQL dynamic port. Default if unset: ask the user.
- `--sage-dbs <CompanyA,CompanyB>` — comma-separated Sage company DB names.
- `--dataxcel-password <pw>` — password for the `dataxcel` SQL login. If unset,
  prompt for it AND remind the user to save it in 1Password under
  `<slug>_metabase_user`.

Reject if any required arg is missing or `<slug>` fails the regex. Print a
one-line plan summary back to the user with all resolved args BEFORE running
anything.

## Step 2 — NetBird provisioning (RISKY — confirm)

Confirm with the user, exact text:

> Run `cd XcelConnectAndUpdater && ./netbird-provision.sh --customer <slug>
> --sql-port <port>`? This creates a NetBird group, setup key, and policy for
> the customer. Type `yes` to proceed.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater
./netbird-provision.sh --customer <slug> --sql-port <port>
```

Capture the setup key from stdout. Show it to the user (they will paste it
during the call). Then append a row to the setup-keys table in
`XcelConnectAndUpdater/CLAUDE.md` (LOCAL EDIT — no confirm). Use the existing
table format. If the file or table is missing, abort with a clear error
pointing at the playbook.

## Step 3 — add peer to `Sage100ContractorDatabases` group (RISKY — confirm)

This is the Dietrich-fix gotcha: without this step Metabase pods can't reach
the customer's Sage box. The curl recipe lives in
`XcelConnectAndUpdater/CLAUDE.md` under the Dietrich-fix section. Read it, fill
in the customer name, show the user the exact curl chain that will run, and
ask for `yes`. On confirm, run it. On any non-200 response, stop and print the
error verbatim — do not retry.

(The peer won't exist yet at this stage since the customer hasn't installed
NetBird. That's fine — record this as a post-call step instead and tell the
user it will be re-attempted in `/onboard-customer-postcall`. Mark it `TODO`
in the summary.)

## Step 4 — generate per-customer Sage SQL (LOCAL — no confirm)

```bash
cp /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/setup-sage-readonly.sql \
   /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/setup-sage-readonly-<slug>.sql
```

Edit the new file in place (use the Edit tool):
- Replace the `:setvar DATAXCEL_PASSWORD "..."` line with the captured password.
- Replace the `:setvar SAGE_COMPANY_DBS "..."` line with the comma-separated DBs.

Print to the user the exact email/SCP one-liner they will hand to customer IT:

> Send this file to customer IT (do not commit it — it has the SQL password):
> `setup-sage-readonly-<slug>.sql`. Tell them to run it in SSMS connected as
> `sa` (or any sysadmin login), against the Sage 100 SQL instance.

## Step 5 — Metabase EKS tenant (RISKY — multiple confirms)

Walk through one step at a time. Do NOT bundle confirmations.

### 5a. `duplicate_single.sh` (RISKY — confirm)

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/diglet/k8s/metabase_deployment
```

Read the top of `duplicate_single.sh` to find the credential block the user
must edit (DB password, admin email, etc.). Show the current values, prompt
the user for the new values, sed them in place, then ask:

> Edited duplicate_single.sh credentials for `<slug>`. Show diff?

Show the diff. Then ask:

> Run `./duplicate_single.sh`? This provisions a new PostgreSQL app DB for the
> tenant Metabase. Type `yes` to proceed.

### 5b. DNS CNAME — print only, do NOT touch DNS

Print the Namecheap record fields the user must add manually:

```
Type:  CNAME
Host:  <slug>
Value: <broker hostname from playbook>
TTL:   Automatic
```

Tell the user: "Add this in Namecheap, then type `dns-done` to continue."
Pause. Wait for `dns-done`.

### 5c. `create_customer_template.sh` (RISKY — confirm)

Same pattern as 5a: read the script, find the edit block, prompt for values,
sed in place, show diff, ask for `yes`, then run.

### 5d. `kubectl apply -k overlays/<slug>` (RISKY — confirm)

> Run `kubectl apply -k overlays/<slug>` against the EKS cluster? This deploys
> the new tenant. Type `yes` to proceed.

On `yes`, run it. Then wait for pods:

```bash
until kubectl get pods -n metabase -l customer=<slug> 2>/dev/null | grep -q Running; do
  sleep 5
  kubectl get pods -n metabase -l customer=<slug>
done
```

(Use a sensible timeout — give up after ~5 minutes and tell the user to debug.)

## Step 6 — configure Metabase (LOCAL — no confirm)

Ask for `--name "<Display Name>"` and `--timezone <tz>` if not supplied.

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting
PYTHONPATH=. .venv/bin/python scripts/configure_metabase_instance.py \
    --customer <slug> --name "<display>" --timezone <tz>
```

## Step 7 — draft `profiles.yml` + `single_customers.py` entries (PRINT, do not commit)

Print to the user, ready to paste:

**`profiles.yml` block** (to paste into
`/Users/mike/dev/projects/etl_pipeline/airflow/sage_dbt/profiles.yml` AFTER
the call, once the NetBird IP is known):

```yaml
<slug>_dataxcel_analytics:
  target: prod
  outputs:
    prod:
      type: sqlserver
      driver: ODBC Driver 18 for SQL Server
      server: "<NETBIRD_IP_TBD>"
      port: <sql-port>
      database: dataxcel_analytics
      schema: dbo
      user: dataxcel
      password: "<paste from 1Password>"
      trust_cert: true
```

**`single_customers.py` entry** (default `snapshots=True` per the rollout plan):

```python
DBTConfig(customer="<slug>", snapshots=True),
```

Tell the user: "Don't commit these yet — the post-call skill fills in the
NetBird IP and pushes both files."

## Step 8 — summary + next step

Print a clean summary:

```
Customer: <slug>
NetBird setup key: <key>     (give this to customer IT)
Per-customer SQL: XcelConnectAndUpdater/setup-sage-readonly-<slug>.sql
Metabase tenant: deployed (or status)
profiles.yml draft: shown above
single_customers.py draft: shown above
Sage100ContractorDatabases group add: TODO (post-call, once peer exists)

Next: /onboard-customer-postcall <slug> --netbird-ip <ip-from-customer>
```

Email template for customer IT (print):

```
Subject: DataXcel onboarding — two scripts to run during our call

Hi <name>,

For our kickoff call, we'll have you run two scripts on the Sage server:

1. NetBird agent install (PowerShell, ~2 min):
   iex (iwr "https://broker.xcel.report/updates/connect-netbird.ps1" -UseBasicParsing).Content -CustomerKey <setup-key>

2. Read-only Sage SQL login setup (SSMS, ~30 seconds):
   <attached: setup-sage-readonly-<slug>.sql — run as sa or sysadmin>

Both are documented in the playbook we'll screenshare during the call.

Thanks,
Mike
```

Stop. Do not run anything else.
