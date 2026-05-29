---
name: onboard-customer-briefing
description: Provision the CEO AI Briefing for a customer — copy the ais.yaml template, enable in the report factory, dry-run with skip_ai, and install the Metabase iframe.
---

# onboard-customer-briefing

You are running the **onboard-customer-briefing** skill. Goal: stand up the
customer's monthly CEO AI Briefing — one YAML, one dry-run, one iframe
install. The Airflow `board_report_dag_factory.py` auto-emits the per-customer
DAG on the next scheduler tick once `enabled: true` is in the YAML; you do
NOT edit DAG code.

**Execution mode:** local edits + dry-runs run unprompted. Metabase API writes
(`install_briefing_iframe.py`) and Git pushes require explicit `yes`.

## Step 1 — validate args

Required:
- `<slug>` — must match the customer slug from earlier onboarding skills.

Optional:
- `--month YYYY-MM` — month to dry-run. Defaults to the previous month.

Verify the customer exists:
- `dataxcel-board-reports-pipeline/customers/ais.yaml` template must exist.
- Metabase tenant URL `https://<slug>.xcel.report` should resolve (best-effort
  HEAD check). If it doesn't, warn and ask whether to continue.

Print a one-line plan.

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

## Step 4 — flip `enabled: true` (LOCAL — no confirm)

Set `enabled: true` at the top of the YAML. This is what causes the
`board_report_dag_factory.py` to emit the customer's monthly DAG.

## Step 5 — dry-run with --skip-ai (LOCAL — no confirm, no Claude spend)

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline
python -m ais_report --customer <slug> --skip-ai --format both
```

If `--month` was supplied, add `--month <YYYY-MM>`.

This confirms data pulls work end-to-end (Metabase queries return, JSON
renders, HTML viewer compiles) without paying for Claude. On error: stop,
print the traceback, and tell the user to investigate. Most likely cause is
a wrong `database_id` or `dashboard_id` in the YAML.

## Step 6 — install Metabase iframe (RISKY — confirm)

Confirm:

> Run `python scripts/install_briefing_iframe.py --customer <slug>`? This
> writes to the customer's Metabase (adds `board.xcel.report` to
> `allowed-iframe-hosts`, snapshots the home dashboard, installs the iframe
> at row 0). Idempotent — re-runs just refresh the signed URL.
>
> Type `yes`.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline
python scripts/install_briefing_iframe.py --customer <slug>
```

If `--month <YYYY-MM>` was supplied, forward it.

If the script prints a CSP error, walk the user through the playbook
troubleshooting note ("CEO Briefing iframe blocked by Metabase CSP if
board.xcel.report not in allowed-iframe-hosts").

## Step 7 — commit + push YAML (RISKY — confirm push)

Confirm:

> Commit `customers/<slug>.yaml` on `dataxcel-board-reports-pipeline` with
> message `feat(briefing): provision <slug>`? Push to origin? Type `yes`.

On `yes`:

```bash
SUBMODULE=/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-board-reports-pipeline
git -C "$SUBMODULE" add customers/<slug>.yaml
git -C "$SUBMODULE" commit -m "feat(briefing): provision <slug>"
git -C "$SUBMODULE" push
```

## Step 8 — summary + next step

```
Customer: <slug>
YAML: customers/<slug>.yaml (enabled: true)
Dry-run: passed (skip_ai)
Iframe: installed on Metabase home dashboard
Verify URL: https://board.xcel.report/report/<slug>/<month>

Note: The Airflow `<slug>_monthly_board_report` DAG appears on the next
scheduler tick — no manual DAG-code edit needed. The factory
(etl_pipeline/airflow/dags/board_report_dag_factory.py) auto-emits one DAG
per `enabled: true` YAML in customers/.

Next: /onboard-customer-hub <slug>
```

Stop.
