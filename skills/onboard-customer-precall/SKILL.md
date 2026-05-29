---
name: onboard-customer-precall
description: Pre-call staging for a new DataXcel customer — 1Password entry prompt, EKS Metabase tenant clone (with ownership transfer + session-blocking workaround), Namecheap CNAME instructions, draft profiles.yml/single_customers.py entries (with TBD placeholders for values that don't exist yet), and NetBird provisioning with a placeholder SQL port that gets fixed in /onboard-customer-oncall. Only required arg is <slug>. Run ~30 min before the IT meeting.
---

# onboard-customer-precall

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer-precall <slug>` becomes `/onboard-customer-precall lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer-precall** skill. Goal: get ~99% of a
new customer's infrastructure staged BEFORE the IT call — without requiring
any value the operator does not yet have.

## Where each arg comes from

This is the principle (see `feedback_skill_args_match_phase.md`): every
required arg here MUST be a value the operator already knows at pre-call
time, with no detour. Values that only become available during the live
call (NetBird IP, real SQL port, Sage company DB name, `dataxcel` SQL
password) are NOT required here — they are collected by the next skill
(`/onboard-customer-oncall`).

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Mike's choice. Lowercase alnum + dashes only (regex `^[a-z0-9-]+$`). Convention: the customer's short name (`lunstrum`, `acme`, `burbach`). |
| `--company-name "<Display>"` | Optional | The display name used for Metabase site name and Kustomize labels. Defaults to title-cased slug (`lunstrum` → `Lunstrum`). |

That is the full surface. No `--sql-port`, no `--sage-dbs`, no
`--dataxcel-password`. Those values do not exist yet at pre-call time and
trying to require them invited the exact bad-placeholder failure Mike hit
during the Lunstrum onboarding.

Source of truth for the full process:
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/docs/new-customer-onboarding.html`.

**Execution mode:** local file edits and read-only checks run without
prompting. Anything that writes to a remote (NetBird API, kubectl apply,
Git push, Metabase API) MUST ask for explicit `yes` confirmation first,
showing exactly what will happen.

## Step 1 — validate args

Required:
- `<slug>` — regex `^[a-z0-9-]+$`. Reject and stop on mismatch with a
  one-line error pointing at the convention.

Optional:
- `--company-name "<Display>"` — defaults to slug with the first character
  upper-cased and `-` → ` ` (e.g. `lunstrum-glass` → `Lunstrum Glass`).
  Used for the Metabase `site-name` setting and the kustomize overlay
  `customer=<display>` label.

Print a one-line plan summary back to the user with all resolved args
BEFORE running anything.

## Step 2 — 1Password entry reminder (PROMPT — no remote write)

Tell the user, before any other work:

> Before we continue, create a 1Password entry titled `<slug>_metabase_user`
> with a generated password (Mike's convention: 1Password's strong-password
> generator, no symbols requirement). Paste the password back here so the
> EKS clone and the Postgres app DB user creation can use it. Type the
> password (it will only live in this session — not written to disk).

Capture the password into an in-session variable `LUNSTRUM_METABASE_PW`.
Do NOT echo it back in plaintext after capture. Re-prompt if blank.

If the user already has the password (re-running the skill, etc.) accept
`existing` as a response and re-prompt for the value. Do not silently
proceed without one — the EKS clone step needs it.

## Step 3 — Metabase EKS tenant clone (RISKY — multiple confirms)

Walk through one sub-step at a time. Do NOT bundle confirmations.

### 3a. duplicate_single.sh — clone the Postgres app DB (RISKY — confirm)

The wrapper script lives at
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/diglet/k8s/metabase_deployment/duplicate_single.sh`.
It clones the `single_metabase_app` Postgres database into
`<slug>_metabase_app`.

Before running, read the top of `duplicate_single.sh` to find the
credential block the user must edit (PG superuser password, new tenant
`<slug>_metabase_user` password, admin email). Show the current values,
sed in the new ones (using the `<slug>` + captured password from Step 2),
show the diff, then ask:

> Run `duplicate_single.sh <slug>`? This creates a new Postgres app DB for
> the tenant Metabase. Type `yes` to proceed.

**Mandatory pre-step: session-blocking workaround** (Mike hit this during
the Lunstrum onboarding — `pg_dump` fails with "source database is being
accessed by other users" if even one Metabase pod is still pointing at
`single_metabase_app`):

```sql
ALTER DATABASE single_metabase_app ALLOW_CONNECTIONS false;
SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
 WHERE datname = 'single_metabase_app' AND pid <> pg_backend_pid();
-- CREATE DATABASE <slug>_metabase_app TEMPLATE single_metabase_app OWNER <slug>_metabase_user;
ALTER DATABASE single_metabase_app ALLOW_CONNECTIONS true;
```

Wrap the `duplicate_single.sh` invocation so it runs the
`ALLOW_CONNECTIONS false` + `pg_terminate_backend` block immediately
before the `CREATE DATABASE ... TEMPLATE` call, and the
`ALLOW_CONNECTIONS true` immediately after. The wrapper must restore
`ALLOW_CONNECTIONS true` even on failure (trap on error).

**Mandatory post-step: ownership transfer.** Mike forgot to run this
manually for Lunstrum and the EKS pod could not write to the cloned DB.
After the clone:

```sql
-- Transfer every object in the cloned DB to the new tenant role.
REASSIGN OWNED BY single_metabase_user TO <slug>_metabase_user;
-- Drop any leftover privileges from the template owner on the new DB.
DROP OWNED BY single_metabase_user CASCADE;
```

This MUST run inside the new `<slug>_metabase_app` database, not in
`postgres`. The script must connect to the cloned DB explicitly.

On `yes` for sub-step 3a, run the wrapper end-to-end. On failure: print
the full Postgres error, restore `ALLOW_CONNECTIONS true` on the source
DB, and stop. Do NOT continue to 3b.

### 3b. create_customer_template.sh — render the Kustomize overlay (RISKY — confirm)

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/diglet/k8s/metabase_deployment
./create_customer_template.sh <slug>
```

Same pattern as 3a: read the script, find the edit block, prompt for any
missing values, show the diff, ask for `yes`, then run.

### 3c. kubectl apply -k overlays/<slug> (RISKY — confirm)

> Run `kubectl apply -k overlays/<slug>` against the EKS cluster? This
> deploys the new tenant. Type `yes` to proceed.

On `yes`, run it. Wait for pods:

```bash
until kubectl get pods -n metabase -l customer=<slug> 2>/dev/null | grep -q Running; do
  sleep 5
  kubectl get pods -n metabase -l customer=<slug>
done
```

Give up after ~5 minutes and tell the user to debug.

## Step 4 — Namecheap CNAME (manual; print only, do not touch DNS)

Cannot automate Namecheap without an API key, so print the record fields
verbatim:

```
Type:  CNAME
Host:  <slug>
Value: <broker hostname from playbook>
TTL:   Automatic
```

Tell the user: "Add this CNAME in Namecheap, then type `dns-done` to
continue." Pause. Wait for `dns-done`.

## Step 5 — draft profiles.yml + single_customers.py entries (LOCAL, print only — do NOT commit)

These get pushed by `/onboard-customer-postcall` once the NetBird IP, SQL
port, and Sage DB name are known. At pre-call time they are PLACEHOLDERS.

**profiles.yml block** — print, do not edit any file yet:

```yaml
<slug>:
  target: prod
  outputs:
    prod:
      type: sqlserver
      driver: ODBC Driver 18 for SQL Server
      server: "<NETBIRD_IP_TBD>"      # filled by /onboard-customer-postcall
      port: <SQL_PORT_TBD>             # filled by /onboard-customer-postcall
      database: "<SAGE_DB_TBD>"        # filled by /onboard-customer-postcall (real DB name from sys.databases)
      schema: dbx_tests
      user: dataxcel
      password: "<DATAXCEL_PW_TBD>"    # filled by /onboard-customer-postcall (from 1Password)
      threads: 4
      trust_cert: true
```

**single_customers.py entry** (default `snapshots=True` per the rollout
plan):

```python
DBTConfig(customer="<slug>", schedule="45 13-23 * * *", snapshots=True),
```

Tell the user: "Don't commit these yet — `/onboard-customer-postcall`
fills in the four TBD values and pushes both files."

## Step 6 — NetBird provisioning with placeholder SQL port (RISKY — confirm)

This is the load-bearing decision: `netbird-provision.sh` requires
`--sql-port`, but the real SQL port is not known until customer IT runs
the install script. **Provisioning with a placeholder port is safe**
because:

- The customer NetBird **group**, **setup key**, and per-customer
  **install URL** (`connect-netbird-<slug>.ps1` + `quickstart-<slug>.html`
  on the broker) are valid regardless of port.
- The only thing the placeholder affects is the **access policy** rule
  (`xcel-broker-to-<slug>` TCP port restriction). `/onboard-customer-oncall`
  updates the policy port the moment IT reports the real port back.

Use `1433` as the placeholder. The on-call skill rewrites it.

Confirm with the user, exact text:

> Run `./netbird-provision.sh --customer <slug> --sql-port 1433` (placeholder
> port — `/onboard-customer-oncall` updates the policy to the real port the
> install script discovers)? This creates the NetBird customer group with
> `auto_groups` for both `customer-<slug>` and `Sage100ContractorDatabases`
> (so the Dietrich-fix is automatic on registration), a one-off setup key,
> and an access policy. It also generates and uploads the per-customer
> install script + quickstart HTML to the broker and verifies both URLs
> return HTTP 200. Type `yes` to proceed.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater
./netbird-provision.sh --customer <slug> --sql-port 1433
```

Capture the setup key and the printed `📧 EMAIL TO CUSTOMER IT:` URL
(`https://broker.xcel.report/updates/quickstart-<slug>.html`) from stdout.
If the script exits non-zero, abort and surface the error — do NOT
fabricate a URL.

After success, append a row to the setup-keys table in
`XcelConnectAndUpdater/CLAUDE.md` (LOCAL EDIT — no confirm). Use the
existing table format and mark the SQL port column as `1433 (placeholder
— update in oncall)`. If the file or table is missing, abort with a
clear error pointing at the playbook.

## Step 7 — print the IT-facing URL

Print the EXACT URL Mike sends to Chris/customer IT:

```
https://broker.xcel.report/updates/quickstart-<slug>.html
```

That URL is verified 200 by `netbird-provision.sh`. Do NOT print a
placeholder like `<PASTE-SETUP-KEY-HERE>` — the setup key is already baked
into the per-customer `connect-netbird-<slug>.ps1` that the HTML loads.

## Step 8 — summary + next step

Print a clean summary:

```
Customer: <slug>   (company: <display>)
1Password entry: <slug>_metabase_user (operator confirmed)
Metabase EKS tenant: deployed (or status)
DNS CNAME: customer added (dns-done received)
profiles.yml draft: printed above (TBD placeholders — postcall fills)
single_customers.py draft: printed above
NetBird group: customer-<slug> + auto-join to Sage100ContractorDatabases
NetBird policy: xcel-broker-to-<slug> TCP 1433 (PLACEHOLDER — oncall updates)
Setup key: <key> (baked into per-customer .ps1; do not re-paste)
IT-facing URL: https://broker.xcel.report/updates/quickstart-<slug>.html

Next: /onboard-customer-oncall <slug>
       (run this DURING the kickoff call once you've sent IT the quickstart URL)
```

Stop. Do not run anything else.
