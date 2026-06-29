---
name: onboard-customer-oncall
description: Live-call skill for a new DataXcel customer — confirms pre-call ran, prints the IT-facing quickstart URL, pauses for IT to install NetBird, captures NetBird IP + real SQL port via pause-prompts, fixes the NetBird policy port + renames the peer, prints the sysadmin SQL script URL, captures the dataxcel SQL password, lists the customer's Sage company DBs via `SELECT name FROM sys.databases` and asks Mike which one is live, creates `dataxcel_analytics`, and updates the customer table in XcelConnectAndUpdater/CLAUDE.md with the harvested values. Only required arg is <slug>.
---

# onboard-customer-oncall

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer-oncall <slug>` becomes `/onboard-customer-oncall lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer-oncall** skill. Goal: drive the
live kickoff call with customer IT — collect every value that didn't exist
at pre-call time, wire them up, and hand a fully-populated set of args to
`/onboard-customer-postcall`.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Mike's choice — same slug used in `/onboard-customer-precall <slug>`. |

Everything else is discovered via pause-prompts during the call:

| Value | Pause-prompt source |
|-------|---------------------|
| NetBird IP | Printed by `connect-netbird-<slug>.ps1` on Chris/IT's screen after install. |
| Real SQL port | Same — `connect-netbird.ps1` auto-detects the Sage dynamic port from the Windows registry and prints it. |
| `dataxcel` SQL password | Chris picks it when running `setup-sage-sysadmin.ps1`. Mike pastes it back. |
| Sage company DB name | Discovered by the skill itself via `SELECT name FROM sys.databases` over the NetBird tunnel — the skill prints the list and asks Mike which one is the live company DB. |

That is the full set. No arg the operator doesn't have at the moment they
invoke the skill.

**Execution mode:** local edits + read-only checks run without prompting.
The NetBird policy update, peer rename, SQL `CREATE DATABASE`, and git
push at the end each require explicit `yes`.

## Step 1 — confirm pre-call ran

Refuse to proceed unless ALL of the following are true:

1. `https://broker.xcel.report/updates/quickstart-<slug>.html` returns
   HTTP 200 (`curl -sI ...`).
2. NetBird group `customer-<slug>` exists
   (`api GET /groups | jq '.[] | select(.name == "customer-<slug>")'`).
3. The setup-keys table in `XcelConnectAndUpdater/CLAUDE.md` has a row
   for `<slug>` with a recorded key + the placeholder-port note from
   pre-call.

If any check fails, stop and tell the user:

```
Pre-call has not been completed for <slug>. Run:
  /onboard-customer-precall <slug>
then come back here.
```

## Step 2 — print the EXACT IT-facing URL

This is the line Mike sends Chris/IT (do NOT improvise — `netbird-provision.sh`
already wrote this file and verified HTTP 200):

```
Send Chris this URL to start the install:

  https://broker.xcel.report/updates/quickstart-<slug>.html

This page contains the one-line PowerShell command that installs NetBird
on the Sage server. The setup key is already baked into the
per-customer .ps1 — there is nothing to paste.
```

PAUSE. Print:

> Waiting for Chris to run the install. When the connect-netbird-<slug>.ps1
> output shows the NetBird IP + Sage SQL port, type `installed` to continue.

Wait for `installed`. Anything else: re-prompt.

## Step 3 — capture NetBird IP + real SQL port (PAUSE-PROMPT)

Prompt:

```
IT just ran the install. Paste the values the script printed at the end:

  NetBird IP:  (e.g. 100.67.139.127)
  SQL port:    (e.g. 49816)
```

Validate:

- NetBird IP regex `^100\.\d{1,3}\.\d{1,3}\.\d{1,3}$` (NetBird CGNAT
  range). Reject and re-prompt on mismatch.
- SQL port integer 1–65535. Reject and re-prompt on mismatch.

Save as `NETBIRD_IP` and `SQL_PORT` for the rest of the skill.

## Step 4 — update NetBird policy port + rename peer (RISKY — confirm each)

### 4a. Update the policy port (1433 placeholder → real)

Find the policy `xcel-broker-to-<slug>` via
`api GET /policies | jq '.[] | select(.name == "xcel-broker-to-<slug>")'`.
Capture its id and the existing rule shape.

Confirm:

> Update the NetBird policy `xcel-broker-to-<slug>` port from `1433`
> (placeholder set in pre-call) to `<SQL_PORT>`? Type `yes`.

On `yes`, `PUT /policies/<id>` with the rule's `ports: ["<SQL_PORT>"]` and
everything else preserved. Confirm 200. On error, print the response body
and stop.

### 4b. Rename the peer to `<slug>-sage`

Confirm:

> Rename the most-recently-registered peer in `customer-<slug>` to
> `<slug>-sage` (using `netbird-name-peer.sh`)? Type `yes`.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater
./netbird-name-peer.sh <slug>
```

If the peer count is zero (timing race — IT hasn't actually finished the
install), the script will error. Tell Mike: "Wait 30 seconds and re-run
`/onboard-customer-oncall <slug>` — peer hasn't registered yet." Stop.

### 4c. Customer TCP reachability check (read-only)

> **2026-06-26 — the old broker host `mike@100.67.235.51` is
> decommissioned.** Run this directly from the operator's NetBird-connected
> machine instead of SSH-ing to the broker.

```bash
nc -zv <NETBIRD_IP> <SQL_PORT>
```

If reachable: print "OK". If not (or the operator isn't on the NetBird
mesh): print a warning but continue — `/onboard-customer-postcall` Step 5
(dbt DAG trigger) is the real end-to-end check. Do NOT block the skill.

## Step 5 — print the sysadmin SQL script URL + capture `dataxcel` password (PAUSE-PROMPT)

Print:

```
IT now needs to run setup-sage-sysadmin.ps1 to create the `dataxcel`
SQL login + grant it db_owner on every Sage company DB. Paste the
one-line URL command back to Chris:

  iwr "https://broker.xcel.report/updates/setup-sage-sysadmin.ps1" `
       -OutFile "$env:TEMP\sa.ps1" -UseBasicParsing
  powershell -ExecutionPolicy Bypass -File "$env:TEMP\sa.ps1"

(The script prompts Chris for the SQL sa password locally — Mike never
sees it. Chris picks the `dataxcel` password and the script grants
db_owner.)
```

PAUSE. Prompt:

> When Chris confirms the script completed, paste the `dataxcel` password
> he picked:

Capture as `DATAXCEL_PW`. Do not echo back. Reject blank input. Strip
leading/trailing whitespace.

## Step 6 — enumerate Sage company DBs + ask Mike which is live

Connect from the broker as `dataxcel` over NetBird and run:

```sql
SELECT name FROM sys.databases
 WHERE name NOT IN ('master','tempdb','model','msdb','dataxcel_analytics')
 ORDER BY name
```

> **2026-06-26 — run this LOCALLY on the operator's NetBird-connected
> machine** (the old `ssh mike@100.67.235.51 … docker exec` host is gone).
> Needs `pyodbc` + the `ODBC Driver 18 for SQL Server` installed locally.
> If they're missing, install (`pip install pyodbc`, `brew install
> msodbcsql18`) or run the same query from any NetBird host that has them.

Via (set `DXP` to the captured `dataxcel` password first, e.g.
`export DXP='<DATAXCEL_PW>'`):

```bash
DXP="$DXP" python3 - <<'PY'
import pyodbc, os
cn = pyodbc.connect(
    'DRIVER={ODBC Driver 18 for SQL Server};'
    'SERVER=<NETBIRD_IP>,<SQL_PORT>;'
    'DATABASE=master;UID=dataxcel;'
    f'PWD={os.environ["DXP"]};'
    'TrustServerCertificate=yes'
)
cur = cn.cursor()
cur.execute("SELECT name FROM sys.databases WHERE name NOT IN "
            "('master','tempdb','model','msdb','dataxcel_analytics') "
            "ORDER BY name")
for (n,) in cur.fetchall():
    print(n)
PY
```

(Pass `DATAXCEL_PW` via env var `DXP` over the SSH connection so it
isn't on the visible command line.)

Print the result list, numbered:

```
Sage databases on <slug>:
  1. <Company A>
  2. <Company B>
  3. Sample Company
  4. SageApplicationTelemetry
  ...

Which is the LIVE Sage company DB for <slug>? (Type the number.)
If the customer has multiple live companies (rollup), type "rollup"
and we'll capture all of them.
```

Single-company: capture as `SAGE_DB`. Rollup: capture comma-separated as
`SAGE_DBS` and flag to the user "Use `/onboard-customer-postcall` with a
`RollupConfig`, not `DBTConfig`."

## Step 7 — create `dataxcel_analytics` on the customer SQL Server (RISKY — confirm)

Confirm:

> Create `dataxcel_analytics` database on `<NETBIRD_IP>:<SQL_PORT>` and
> grant `dataxcel` db_owner? This is the warehouse DB dbt writes
> snapshots and marts into. Type `yes`.

On `yes`, run the SQL below against `<NETBIRD_IP>,<SQL_PORT>` from the
operator's NetBird-connected machine — same local `pyodbc` path as Step 6
(wrap these statements in a `cur.execute(...)` per statement, dropping the
`GO` batch separators which pyodbc doesn't accept):

```sql
CREATE DATABASE dataxcel_analytics;
GO
USE dataxcel_analytics;
GO
CREATE USER dataxcel FOR LOGIN dataxcel;
GO
ALTER ROLE db_owner ADD MEMBER dataxcel;
GO
```

If the DB already exists (re-run), skip CREATE and proceed to ensure
the user + role membership exist. Idempotent.

## Step 8 — update customer credentials table in XcelConnectAndUpdater/CLAUDE.md (RISKY — confirm push)

Append a row to the **NetBird Customers (Migrated — No Legacy Port)**
table in
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md`:

```
| <slug> | <slug> | <slug>-sage.netbird.xcel.software | <NETBIRD_IP> | <SQL_PORT> | <slug>.xcel.report | NetBird ✅, dataxcel ✅, dataxcel_analytics ✅ |
```

Also append/update the row in the **SQL Credentials** table with the
real port + the `dataxcel` user + the captured password + Sage DB name.

Update the placeholder-port note in the setup-keys row written by
pre-call: replace `1433 (placeholder — update in oncall)` with the real
port.

Confirm:

> Commit + push XcelConnectAndUpdater/CLAUDE.md with the three updates
> (setup-keys row port, SQL credentials row, NetBird customers row) for
> `<slug>`? Type `yes`.

On `yes`:

```bash
git -C /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater add CLAUDE.md
git -C /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater commit -m "docs: capture <slug> NetBird IP + SQL port + Sage DB from on-call"
git -C /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater push
```

## Step 9 — summary + next step

Print:

```
Customer: <slug>
NetBird IP: <NETBIRD_IP>
SQL port: <SQL_PORT>
Sage DB: <SAGE_DB>     (or rollup list)
dataxcel password: (captured — written to CLAUDE.md)
dataxcel_analytics: created on customer SQL Server
NetBird policy: xcel-broker-to-<slug> TCP <SQL_PORT> (placeholder fixed)
Peer name: <slug>-sage

Next: /onboard-customer-postcall <slug> \
    --netbird-ip <NETBIRD_IP> \
    --sql-port <SQL_PORT> \
    --sage-db "<SAGE_DB>" \
    --dataxcel-pw '<DATAXCEL_PW>'
```

Note: `/onboard-customer-postcall` accepts these args optionally — if you
omit them it reads them from `XcelConnectAndUpdater/CLAUDE.md` (we just
wrote them in Step 8). Print both forms so Mike can pick.

Stop.
