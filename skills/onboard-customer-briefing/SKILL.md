---
name: onboard-customer-briefing
description: Provision the CEO AI Briefing for a customer (60-day trial countdown by default; pass --paid for paid customers). Copy the ais.yaml template, set trial flag, enable in the report factory, dry-run with skip_ai, and install the Metabase iframe.
---

# onboard-customer-briefing

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer-briefing <slug>` becomes `/onboard-customer-briefing lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer-briefing** skill. Goal: stand up the
customer's monthly CEO AI Briefing — one YAML, one dry-run, one iframe
install. The Airflow `board_report_dag_factory.py` auto-emits the per-customer
DAG on the next scheduler tick once `enabled: true` is in the YAML; you do
NOT edit DAG code.

**Reversed 2026-05-29:** This skill is now part of the DEFAULT onboarding
flow. Every new customer gets the briefing provisioned, but with a built-in
60-day trial countdown:

- **Default (no flag):** writes `trial: true` into the YAML; the iframe URL
  carries `trial_started` + `trial_until` claims (now + 60 days, UTC). At
  the end of 60 days the viewer shows "trial expired, contact sales" and
  the monthly DAG ShortCircuits (DAG-side gate is a follow-up — see the
  pipeline's CLAUDE.md "Trial mechanics" section).
- **`--paid` flag:** writes `trial: false` into the YAML; no trial claims
  on the iframe URL, no countdown, no expiry banner. Use this for
  customers who have purchased the briefing outright.

**Execution mode:** local edits + dry-runs run unprompted. Metabase API writes
(`install_briefing_iframe.py`) and Git pushes require explicit `yes`.

## Step 1 — validate args

Required:
- `<slug>` — must match the customer slug from earlier onboarding skills.

Optional:
- `--paid` — provision as a paid customer (no trial countdown). Default is
  trial mode with a 60-day countdown.
- `--trial-days N` — override the default 60 days (still trial mode; mutually
  exclusive with `--paid`).
- `--month YYYY-MM` — month to dry-run. Defaults to the previous month.

Verify the customer exists:
- `dataxcel-board-reports-pipeline/customers/ais.yaml` template must exist.
- Metabase tenant URL `https://<slug>.xcel.report` should resolve (best-effort
  HEAD check). If it doesn't, warn and ask whether to continue.

Print a one-line plan that includes the resolved trial mode, e.g.:

> Plan: provision briefing for `<slug>` — trial mode (60-day countdown,
> expires <YYYY-MM-DD>).

or

> Plan: provision briefing for `<slug>` — PAID (no trial countdown).

## Step 2 — copy ais.yaml template (LOCAL — no confirm)

```bash
cp /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline/customers/ais.yaml \
   /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline/customers/<slug>.yaml
```

If `<slug>.yaml` already exists, stop and ask whether to overwrite.

## Step 3 — fill in customer-specific fields (LOCAL — no confirm, prompt for values)

Read the new YAML. Prompt the user (one field at a time) for everything that
must change from the AIS template:

| Field | Notes |
|---|---|
| `company_name` | Full legal name |
| `company_short` | 1–2 word brand for headers |
| `metabase_url` | `https://<slug>.xcel.report` |
| `database_id` | Metabase DB id from `/onboard-customer-postcall` Step 7 |
| `dashboard_id` | Source dashboard for the briefing (ask Mike if unsure) |
| `dashboard_tab_id` | Optional |
| `departments` | List — ask user |
| `branding.primary_color` | Hex; optional, default keeps AIS palette |
| `branding.logo` | URL or path; optional |

Use the Edit tool to update each field in place. Validate YAML still parses
after edits (`python -c "import yaml; yaml.safe_load(open('...'))"`).

## Step 4 — set the trial flag (LOCAL — no confirm)

Insert (or update) a `trial:` field at the top of the YAML based on the args:

- Default / `--trial-days N`: `trial: true`. If `--trial-days N` was given,
  also add `trial_days: N` on the next line. Otherwise omit `trial_days` and
  the installer uses the 60-day default.
- `--paid`: `trial: false`.

The reference is `customers/_template.yaml` in the
`dataxcel-board-reports-pipeline` repo — it documents both shapes.

## Step 5 — flip `enabled: true` (LOCAL — no confirm)

Set `enabled: true` at the top of the YAML. This is what causes the
`board_report_dag_factory.py` to emit the customer's monthly DAG.

## Step 6 — dry-run with --skip-ai (LOCAL — no confirm, no Claude spend)

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline
python -m ais_report --customer <slug> --skip-ai --format both
```

If `--month` was supplied, add `--month <YYYY-MM>`.

This confirms data pulls work end-to-end (Metabase queries return, JSON
renders, HTML viewer compiles) without paying for Claude. On error: stop,
print the traceback, and tell the user to investigate. Most likely cause is
a wrong `database_id` or `dashboard_id` in the YAML.

## Step 7 — install Metabase iframe (RISKY — confirm)

Build the install command. If the user passed `--trial-days N`, forward it
to the installer so its CLI override matches the YAML; otherwise let the
installer read the YAML default.

Confirm:

> Run `python scripts/install_briefing_iframe.py --customer <slug>
> [--trial-days N]`? This writes to the customer's Metabase (adds
> `board.xcel.report` to `allowed-iframe-hosts`, snapshots the home
> dashboard, installs the iframe at row 0). Idempotent — re-runs just
> refresh the signed URL AND the trial countdown.
>
> Type `yes`.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline
python scripts/install_briefing_iframe.py --customer <slug> [--trial-days N]
```

The script prints the trial expiry on its `OK` line (or `paid (no trial)`
for `--paid` customers). Echo that line back to the user so they can see
the expiry date.

If `--month <YYYY-MM>` was supplied, forward it.

If the script prints a CSP error, walk the user through the playbook
troubleshooting note ("CEO Briefing iframe blocked by Metabase CSP if
board.xcel.report not in allowed-iframe-hosts").

## Step 8 — commit + push YAML (RISKY — confirm push)

Confirm:

> Commit `customers/<slug>.yaml` on `dataxcel-board-reports-pipeline` with
> message `feat(briefing): provision <slug> (trial|paid)`? Push to origin?
> Type `yes`.

On `yes`:

```bash
SUBMODULE=/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline
git -C "$SUBMODULE" add customers/<slug>.yaml
git -C "$SUBMODULE" commit -m "feat(briefing): provision <slug> (trial|paid)"
git -C "$SUBMODULE" push
```

## Step 9 — summary + next step

```
Customer: <slug>
Mode: trial (expires <YYYY-MM-DD>)   OR   paid (no trial)
YAML: customers/<slug>.yaml (enabled: true, trial: true|false)
Dry-run: passed (skip_ai)
Iframe: installed on Metabase home dashboard
Verify URL: https://board.xcel.report/report/<slug>/<month>

Note: The Airflow `<slug>_monthly_board_report` DAG appears on the next
scheduler tick — no manual DAG-code edit needed. The factory
(etl_pipeline/airflow/dags/board_report_dag_factory.py) auto-emits one DAG
per `enabled: true` YAML in customers/.

For trial customers: the viewer will show a "trial expires in N days"
countdown banner once the viewer-side work lands (TODO). The trial claims
flow through today via `trial_started` + `trial_until` URL params and
JWT extra-claims.

If/when the customer upgrades to paid:
  /onboard-customer-briefing <slug> --paid
(idempotent re-run — flips trial: false, the next iframe refresh has no
trial claims, customer is instantly upgraded)
```

Stop.
