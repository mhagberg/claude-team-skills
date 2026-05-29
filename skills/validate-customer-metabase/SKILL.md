---
name: validate-customer-metabase
description: Run every available Metabase-vs-Sage validation suite against a customer's Metabase instance BEFORE adding users and granting access. Blocks user provisioning if any validator fails. Use this after `/onboard-customer-postcall` and BEFORE `/onboard-customer-hub` / first invite.
---

# validate-customer-metabase

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/validate-customer-metabase <slug>` becomes `/validate-customer-metabase lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **validate-customer-metabase** skill. This skill is a
**gate** in the canonical onboarding sequence:

```
precall  ->  customer IT runs scripts  ->  postcall  ->  >>> VALIDATE (you are here) <<<  ->  hub  ->  briefing  ->  invite users
```

Mike's hard rule (2026-05-29 during Lunstrum onboarding):

> "We need to make sure the numbers validate against the Sage reports before
> we add the users and give them access."

Your job: run **every available** Metabase-vs-Sage validator for this
customer and refuse to print the "Next:" pointer unless all of them pass.

**Execution mode:** every validator in this skill is read-only against
Metabase and read-only against the Sage 100 DW. Run them unprompted. The
only write this skill ever performs is a summary markdown to `/tmp` — and
even that, ask before writing anywhere outside `/tmp`.

## Step 1 — parse args + resolve config

CLI shape:

```
/validate-customer-metabase <slug> [--reports balance,income,wip,jobcost]
                                   [--tolerance 0.01]
                                   [--metabase-url https://<slug>.xcel.report]
                                   [--api-key mb_...]
                                   [--start-date YYYY-MM-DD]
                                   [--end-date YYYY-MM-DD]
```

Required:

- `<slug>` — customer slug (e.g. `lunstrum`, `west`, `ais`).

Defaults:

- `--reports` defaults to `balance,income,wip,jobcost`. `--reports all` runs
  every suite this skill knows about. The currently-known suites are listed
  in Step 2.
- `--tolerance` defaults to `0.01` (one cent — penny rounding).
- `--metabase-url` defaults to `https://<slug>.xcel.report`.
- `--api-key` defaults to the shared `single.xcel.report` Metabase API key:
  `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=`
  (source of truth: `XcelConnectAndUpdater/CLAUDE.md`, "Metabase Instances &
  API Keys" table; the shared key works for any customer routed onto the
  `single.xcel.report` shared instance — Hallowell, Roth, Dietrich, Bookout,
  West, AIS all use it). If the customer is on a dedicated Metabase
  instance, the user must pass `--api-key` explicitly.
- `--start-date` / `--end-date` default to the current fiscal-year window
  used by `cash-basis-report/tests/conftest.py` (currently `2026-01-01`
  through `2026-04-01`). Allow the user to override.

Print a one-line plan summary BEFORE running anything, e.g.:

```
Validating lunstrum against https://lunstrum.xcel.report
Reports: balance, income, wip, jobcost
Tolerance: 0.01
Date range: 2026-01-01 to 2026-04-01
```

## Step 2 — discover available validators

Each report name in `--reports` MUST map to a real validator on disk. The
mapping below is authoritative — if a validator is missing for a requested
report, **fail loudly** with `no validator implemented for <report>` and
exit non-zero. Do NOT silently skip.

| Report key | Validator | Location |
|------------|-----------|----------|
| `balance`  | Balance Sheet Excel vs Metabase card | `metabase-migration/metabase-validation/validate.py --report "Balance Sheet"` |
| `income`   | Income Statement Excel vs Metabase card + Cash Basis pytest suite | `metabase-migration/metabase-validation/validate.py --report "Income Statement"` AND `cash-basis-report/tests/` |
| `ar_aging` | AR Invoice Aging Excel vs Metabase card | `metabase-migration/metabase-validation/validate.py --report "AR Invoice Aging"` |
| `ap_aging` | AP Invoice Aging Excel vs Metabase card | `metabase-migration/metabase-validation/validate.py --report "AP Invoice Aging"` |
| `posting_date` | Filter coverage scan (45 unit tests + per-instance scan) | `ais-posting-date-filters/tests/` and `ais-posting-date-filters/scripts/validate_filter.py` |
| `wip`      | NOT YET IMPLEMENTED — see TODOs at the bottom |
| `jobcost`  | NOT YET IMPLEMENTED — see TODOs at the bottom |

Before running, `ls` each validator path to confirm it exists. If a path
is missing, print:

```
[BLOCKED] Validator for <report> not found at <path>
This validator needs to be built before we can gate <slug> on it.
```

…and refuse to proceed. Do not pretend a missing validator passed.

## Step 3 — collect Sage Excel exports (for Excel-based validators)

The `metabase-migration/metabase-validation/validate.py` script compares a
Metabase card against a **Sage Excel export** the user produced from Sage
100 Contractor. Ask the user up front:

> Validating `balance`, `income`, `ar_aging`, `ap_aging` requires Sage
> Excel exports. Do you have them locally? (yes / skip-excel-validators)
>
> If yes, the `validate.py` GUI file-picker will open per report.

If the user types `skip-excel-validators`, fall back to **API-only**
comparison for `balance` / `income`: pull the equivalent T-SQL directly
from the corresponding dbt mart in
`/Users/mike/dev/projects/etl_pipeline/airflow/sage_dbt/dataXcel/models/mart/`
and compare its result rows to the Metabase card. Use Sage 100 as the
ground truth (memory: `Sage Is The Truth` — Sage DB is truth, treat
customer Excel files as hypotheses, not ground truth).

Mark Excel-skipped validators in the final report as
`mode=api-only (no Excel cross-check)` so Mike knows the depth of what was
verified.

## Step 4 — run validators (read-only, parallel where independent)

Run each requested validator. Independent validators can run in parallel
(`cash-basis-report` pytest vs `metabase-validation` script vs
`ais-posting-date-filters` pytest are all independent processes). Stream
output to the console as it arrives.

### 4a. Cash Basis Income Statement pytest suite (for `income`)

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/cash-basis-report
PYTHONPATH=.. python -m pytest tests/ -v \
  --instance=<slug> \
  --start-date=<start-date> \
  --end-date=<end-date>
```

Notes:

- This is the 51-test suite per `cash-basis-report/CLAUDE.md`. It fixes 2
  bugs: Ultimate Sum sign formula and PO Receipt accrual contamination.
- `--instance=<slug>` requires the slug to be registered in
  `cash-basis-report/src/instances.py`. If the customer is brand new and
  not yet in that registry: **stop**, tell the user "register <slug> in
  `cash-basis-report/src/instances.py` (URL, api key, db_id, card_id,
  dash_id, field IDs) and re-run". Do NOT auto-edit `instances.py` from
  this skill — it's a per-customer source of truth that lives outside this
  workflow.
- Some customers have known-skipped tests (e.g. `west` skips SR tests, AIS
  has unknown GL sources). Treat `passed + skipped == total` with `failed
  == 0` as a pass. Any `failed > 0` is a hard fail.

### 4b. metabase-validation Excel comparison (for `balance` / `income` / `ar_aging` / `ap_aging`)

For each report the user has Excel for:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/metabase-migration/metabase-validation
python validate.py \
  --client <slug> \
  --report "<report name>" \
  --card-id <card-id> \
  --excel <path> \
  --tolerance <tolerance>
```

The `--client <slug>` requires the slug to be registered in
`metabase-migration/clients.json`. If it isn't, stop and tell the user to
add it; do NOT auto-edit `clients.json`.

`--card-id` is required — look the card ID up from the customer's
dashboard 49 (Income Statement) or Balance Sheet dashboard via Metabase
API (`GET /api/dashboard/<id>` and inspect dashcards). If the user knows
the card IDs, accept them as additional `--income-card`, `--balance-card`
flags; otherwise interactively prompt per report.

### 4c. posting_date filter validation (for `posting_date`)

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/ais-posting-date-filters
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. python scripts/triage_dashboards.py --instance <slug>
```

The pytest suite is instance-agnostic (it tests payload construction). The
`triage_dashboards.py` script lists which dashboards on the customer's
instance have `posting_date` wired vs missing — useful as a coverage
signal even if it's not strictly a number-validates-vs-Sage check.

### 4d. API-only Sage cross-check (fallback when Excel is unavailable)

For each report where the user said `skip-excel-validators`:

1. Open the corresponding dbt mart SQL in
   `etl_pipeline/airflow/sage_dbt/dataXcel/models/mart/` (Balance Sheet =
   `Balance_Sheet.sql`, Income Statement = the marts feeding dashboard 49,
   etc.).
2. Run that exact SELECT against the customer's `dataxcel_analytics` SQL
   Server via Metabase's `/api/dataset` native query endpoint (POST with
   `{"database": <db_id>, "type": "native", "native": {"query": "<sql>"}}`).
   Use the credentials from Step 1.
3. Run the equivalent Metabase card via `/api/card/<id>/query`.
4. Diff the summary totals (Total Assets, Total Liabilities, Total Equity,
   Total Revenue, Total Expenses, Net Income) row-by-row within
   `--tolerance`.

Print a side-by-side table on mismatch:

```
| Line              | Sage (mart SQL)  | Metabase card   | Delta       | % delta |
|-------------------|------------------|------------------|-------------|---------|
| Total Assets      | 1,234,567.89     | 1,234,567.90     | +0.01       | 0.0000% |
| Total Liabilities | 789,012.34       | 789,012.34       | 0.00        | 0.0000% |
| Total Equity      | 445,555.55       | 445,555.56       | +0.01       | 0.0000% |
```

## Step 5 — pass / fail decision

For each validator collect a status: `pass` | `fail` | `blocked` (missing
validator) | `skipped` (user opted out).

**The skill passes if and only if every requested validator returned
`pass`.** `blocked` and `fail` are both hard fails. `skipped` requires the
user to have explicitly opted out and you must surface it in the summary.

## Step 6 — output

### On pass

Print (ANSI green if the terminal supports it; otherwise plain text):

```
========================================
  all validations passed for <slug>
========================================

  balance       : pass
  income        : pass (cash-basis 51 tests + Excel diff)
  posting_date  : pass (45 unit tests + 12/12 dashboards wired)
  ...

  Tolerance: 0.01   Date range: <start> to <end>
```

Ask the user before writing anywhere outside `/tmp`. By default, write a
summary at `/tmp/validate-<slug>-<YYYYMMDDHHMMSS>.md` with:

- Customer slug + Metabase URL.
- Date range and tolerance used.
- Per-report status, command run, and any noteworthy output.
- The exact Sage vs Metabase side-by-side tables for the API-only path.

End the message with EXACTLY:

```
Next: /onboard-customer-hub <slug>
```

(Or, if the user has not yet run `/onboard-customer-postcall`, point them
back there first. Do not guess — check whether
`profiles.yml` already has `<slug>_dataxcel_analytics` filled in and the
Metabase DB exists; if not, the postcall step was skipped.)

### On fail

Print (ANSI red if supported; otherwise plain text):

```
========================================
  VALIDATION FAILED for <slug>
========================================

  balance       : FAIL  (3 line mismatches > tolerance)
  income        : pass
  posting_date  : BLOCKED (validator not found)
  ...

  Full diff above.

  Do NOT add users until this is resolved.
```

Exit non-zero. Do NOT print a `Next:` pointer. The user has to fix the
underlying problem (dbt mart, dashboard SQL, Metabase card filter, Sage
data, NetBird connectivity, etc.) and re-run `/validate-customer-metabase
<slug>`.

If the failure is a blocked validator (Step 2 found nothing on disk for a
requested report), the user has two options:

1. Build the missing validator (see TODOs section).
2. Drop the report from `--reports` and re-run — but only if Mike
   explicitly approves dropping it (ask: "Drop `<report>` from this
   validation run? Only do this if you accept that we will not have
   number-level confidence for that report. Type `yes` to drop.").

## Step 7 — never tell the user "you should now run X"

Per the skill-over-manual rule (`feedback_skill_over_manual_steps.md`):
every concrete command in this skill body is something *you* run as the
host Claude. The only "Next:" pointer at the tail points to another slash
command. Never tell the user to manually invoke `pytest` or curl —
**you** run it, **you** parse the output, **you** report.

The one exception is Excel exports: the user owns the Sage 100 Contractor
GUI, you can't drive it. Ask for the file path or let `tkinter.filedialog`
in `validate.py` open the picker (the existing tool handles this — pass
the path through, do not re-prompt).

## TODOs — validators that don't exist yet

These report keys are listed in the default `--reports` set but **no
validator currently exists on disk**. Until each is built, requesting it
must return `BLOCKED` per Step 2 — the skill must refuse to declare a
customer validated if these are requested and missing:

- `wip` — WIP / Over-Under Billings validation. Needs a Sage SQL pulled
  from the dbt WIP mart (e.g. `mart/WIP.sql` or whichever model produces
  the WIP dashboard's data) compared against the customer's Metabase WIP
  card on every job. No tool exists yet.
- `jobcost` — Job Cost Detail validation. Needs the Sage `Job_Cost`
  rollup compared against Metabase Job Cost Detail cards (per-job
  cost-code-level diff with `--tolerance`). No tool exists yet.

Both should follow the same shape as the existing
`metabase-migration/metabase-validation/validate.py` (single-file script
with `--client`, `--report`, `--card-id`, `--excel` or `--api-only`,
`--tolerance`). When built, register them in Step 2's table and they
become automatically available.

Until then: requesting `--reports all` will yield `BLOCKED` for `wip` and
`jobcost`, which is the correct behavior — Mike's rule is
"validate before we add users", and we can't claim WIP is validated when
we have no WIP validator.

## Quick recap of the gate

This skill enforces ONE thing: no users get access to a customer's
Metabase until the numbers reconcile to Sage within tolerance. If you
walk away from a `/validate-customer-metabase` run without seeing the
green "all validations passed" block, the next step is NOT
`/onboard-customer-hub` — it's fixing whatever the diff surfaced.
