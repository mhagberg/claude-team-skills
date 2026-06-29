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

**Source of truth — read this first.** The canonical Balance Sheet
validator procedure lives in
[`metabase-migration/report-repair/CLAUDE.md`](../../../metabase-migration/report-repair/CLAUDE.md)
(see "Balance Sheet Troubleshooting" section). That document is the
authoritative description of how `balance_sheet_balance` is computed in
the dbt mart, how to diagnose a NULL `prior_fys_profit_loss`, and how
to repair the Metabase custom column expression. This skill is a
thin wrapper that **runs that procedure** — it does not duplicate it.

**This is NOT an Excel-vs-Metabase comparison by default.** Sage 100
Contractor does not store the Balance Sheet as a query-able report,
so there is no Sage export to diff against directly. Instead the
validator runs SQL **directly against the customer's
`dataxcel_analytics` warehouse** and against the raw Sage SQL Server
source DB on the customer's box, then diffs the two. Customer Excel
exports exist but are hypotheses, not ground truth — see the
`feedback_sage_is_truth` rule. Excel comparison is a fallback the
user can request explicitly via `--use-excel`; the default path is
SQL-only.

**Point-in-time, not sum-of-months.** A Balance Sheet is a snapshot
— filter to ONE as-of date. The Metabase card is designed to be
filtered by the dashboard's date param at view time;
**unfiltered it sums all months and produces garbage**. The
validator MUST apply a date filter (latest period with data) before
summing. Use `--end-date` (defaults to the latest available
`balance_budget_date` in `Ledger_Accounts_by_Month`).

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
| `balance`  | Balance Sheet diagnostic-SQL procedure (3 queries — accounting identity, RE / `prior_fys_profit_loss`, account coverage) run against `dataxcel_analytics` + raw Sage source DB | `metabase-migration/report-repair/CLAUDE.md` ("Balance Sheet Troubleshooting" section) — see Step 4a below for the exact SQL |
| `income`   | Cash Basis pytest suite (51 tests, Cash Basis Income Statement) | `cash-basis-report/tests/` |
| `ar_aging` | AR Invoice Aging Excel vs Metabase card (Excel fallback only — requires `--use-excel`) | `metabase-migration/metabase-validation/validate.py --report "AR Invoice Aging"` |
| `ap_aging` | AP Invoice Aging Excel vs Metabase card (Excel fallback only — requires `--use-excel`) | `metabase-migration/metabase-validation/validate.py --report "AP Invoice Aging"` |
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

## Step 3 — Excel exports are a FALLBACK, not the default

The default validator path for `balance` is **SQL-only** — it runs the
diagnostic SQL in Step 4a directly against the customer's
`dataxcel_analytics` warehouse and the raw Sage source DB. Do NOT ask
the user for an Excel export by default.

Only collect an Excel export if the user explicitly passes
`--use-excel` (e.g. they want a third-party cross-check) or if a
specific validator only exists as an Excel diff (currently `ar_aging`
and `ap_aging`). In those cases the `validate.py` GUI file-picker
opens per report — pass the path through; do not re-prompt.

Mark the run in the final report with `mode=sql-diagnostic` (default)
or `mode=excel-cross-check` (when `--use-excel` was passed) so Mike
knows the depth of what was verified.

## Step 4 — run validators (read-only, parallel where independent)

Run each requested validator. Independent validators can run in parallel
(`cash-basis-report` pytest vs `metabase-validation` script vs
`ais-posting-date-filters` pytest are all independent processes). Stream
output to the console as it arrives.

### 4a. Balance Sheet diagnostic SQL (for `balance`) — default path

Run all three queries against the customer's `dataxcel_analytics` SQL
Server. Use the connection from the customer's `profiles.yml` block
(see `XcelConnectAndUpdater/CLAUDE.md` "SQL Credentials" table) — the
same credentials dbt uses. Apply the `--end-date` filter; never sum
unfiltered (Balance Sheet is a point-in-time snapshot).

**Test 1 — accounting identity per period.** `Assets = Liabilities +
Equity` must hold to within `--tolerance` ($0.01 default) for every
period:

```sql
SELECT
  balance_budget_date,
  SUM(CASE WHEN balance_sheet_asset_type = '1. Total Assets'      THEN balance_sheet_balance ELSE 0 END) AS assets,
  SUM(CASE WHEN balance_sheet_asset_type = '2. Total Liabilities' THEN balance_sheet_balance ELSE 0 END) AS liabilities,
  SUM(CASE WHEN balance_sheet_asset_type = '3. Equity'            THEN balance_sheet_balance ELSE 0 END) AS equity
FROM dbo.Ledger_Accounts_by_Month
GROUP BY balance_budget_date
ORDER BY balance_budget_date;
```

Fail if any period has `|assets - (liabilities + equity)| > tolerance`.

**Test 2 — Retained Earnings + `prior_fys_profit_loss`.** Flag if
`prior_fys_profit_loss` is NULL but `balance_sheet_balance` differs
from raw `balance` — the dbt `year_to_calculate_from` subquery may
have found no match (floating-point precision bug or genuinely no
closed prior years):

```sql
SELECT fiscal_year, balance_budget_date, ledger_account,
       balance, prior_fys_profit_loss, balance_sheet_balance
FROM dbo.Ledger_Accounts_by_Month
WHERE ledger_account LIKE '%Retained Earn%'
ORDER BY balance_budget_date DESC;
```

For fresh-customer / synthetic-data instances this is an **advisory
flag, not a block** — Sage hasn't closed any years yet so NULL is
expected. For an established customer that's been live for >1
fiscal year, it's a real failure — investigate via the `report-repair`
playbook before unblocking.

**Test 3 — account coverage.** NULL `asset_type` accounts mean the
categorization CASE in `Ledger_Accounts_by_Month.sql` missed them:

```sql
SELECT
  COUNT(DISTINCT ledger_account_id)                                                AS total_accounts,
  COUNT(DISTINCT CASE WHEN balance_sheet_asset_type IS NULL THEN ledger_account_id END) AS uncategorized_accounts
FROM dbo.Ledger_Accounts_by_Month;
```

Fail if `uncategorized_accounts > 0`.

For full troubleshooting (PCG Balance Sheet custom column expressions,
how `balance_sheet_balance` is computed, NULL `prior_fys_profit_loss`
diagnosis, VGW well-behaved-client case study), defer to
`metabase-migration/report-repair/CLAUDE.md` "Balance Sheet
Troubleshooting" — it's the source of truth.

### 4b. Cash Basis Income Statement pytest suite (for `income`)

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

### 4c. metabase-validation Excel comparison (FALLBACK only — `ar_aging` / `ap_aging` always; `balance` / `income` only with `--use-excel`)

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

### 4d. posting_date filter validation (for `posting_date`)

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/ais-posting-date-filters
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. python scripts/triage_dashboards.py --instance <slug>
```

The pytest suite is instance-agnostic (it tests payload construction). The
`triage_dashboards.py` script lists which dashboards on the customer's
instance have `posting_date` wired vs missing — useful as a coverage
signal even if it's not strictly a number-validates-vs-Sage check.

### 4e. API-only Sage cross-check (only used when `--use-excel` was passed AND the user has no Excel file)

For each report where the user said `skip-excel-validators`:

1. Open the corresponding dbt mart SQL in
   `airflow_dags/sage_dbt/dataXcel/models/mart/` (Balance Sheet =
   `Balance_Sheet.sql`, Income Statement = the marts feeding dashboard 49,
   etc.). (Moved 2026-06-26 from the old `etl_pipeline/airflow/sage_dbt/…`
   path; same `sage_dbt` repo, now a submodule of `airflow_dags`.)
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

## Worked example — Lunstrum (2026-05-29)

Live run that informed every correction in this SKILL.md:

- **Test 1 (accounting identity):** green for **14 periods**
  (2025-11 through 2026-12) — `|assets - (liabilities + equity)| <
  $0.01` for every period.
- **Test 2 (RE / `prior_fys_profit_loss`):** `prior_fys_profit_loss
  = NULL` for the Retained Earnings rows — flagged as **advisory
  only** because Lunstrum is fresh synthetic data with no real prior
  years closed. NOT a block. For an established customer this would
  be a real failure.
- **Test 3 (account coverage):** **335 ledger accounts, 0 with NULL
  `asset_type`** — categorization CASE in
  `Ledger_Accounts_by_Month.sql` covers every account.
- **Validator result:** PASS (advisory flag recorded in the
  summary).

Mike's exact instruction (during this run): *"we need to make sure
the numbers validate against the Sage reports before we add the users
and give them access."*

## Quick recap of the gate

This skill enforces ONE thing: no users get access to a customer's
Metabase until the numbers reconcile to Sage within tolerance. If you
walk away from a `/validate-customer-metabase` run without seeing the
green "all validations passed" block, the next step is NOT
`/onboard-customer-hub` — it's fixing whatever the diff surfaced.
