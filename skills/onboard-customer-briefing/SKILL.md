---
name: onboard-customer-briefing
description: Provision the CEO Weekly AI Briefing for a customer. Wires the customer into the dataxcel-ai-briefing pipeline (NOT dataxcel-board-reports-pipeline — that's AIS monthly board reports, a different system). Three edits + two script runs + one DAG entry, in this exact order.
---

# onboard-customer-briefing

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer-briefing <slug>` becomes `/onboard-customer-briefing lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer-briefing** skill. Goal: stand the
customer's weekly CEO AI Briefing up end-to-end so the Monday-morning DAG
generates the briefing JSON, pushes it to Firestore, and refreshes the
iframe URL on the customer's Metabase homepage dashboard.

## Pipeline architecture — read this first or you WILL go wrong

There are **two completely separate AI report systems** in this repo. They
have similar names and they both touch Metabase iframes. Pick the wrong one
and you will spend two hours fighting the wrong YAML schema.

| System | What it is | When to use |
|---|---|---|
| **`dataxcel-ai-briefing`** + parent-repo `scripts/update_*_ceo_briefing.py` | The CEO Weekly Briefing — React SPA at `ai.xcel.report`, Firestore-backed, iframed on Metabase D94. Runs **every Monday 6 AM UTC** via `customer_ceo_weekly_briefing` DAG. 7 production customers as of 2026-05-29: goodwin, single, jolma, ais, burbach, brekhus, pcg. | **THIS SKILL.** |
| `dataxcel-board-reports-pipeline` | AIS-only **monthly** board-report PDF/HTML pipeline. Customer YAML config, ReportLab PDF generation, hosted at `board.xcel.report`. Runs `0 6 1 * *`. **AIS is the only production tenant.** | Don't touch this unless onboarding for AIS-style monthly reports. |

The two pipelines share the prefix "briefing" and both touch Metabase
iframes, which is how I (Claude) got it wrong onboarding Lunstrum
2026-05-29. Do NOT create a `customers/<slug>.yaml` in
`dataxcel-board-reports-pipeline/customers/`. Do NOT branch on the
board-reports submodule. Do NOT ask Mike for "department codes" — the
weekly briefing has no YAML and no department codes.

## What you actually edit — five concrete files

The weekly briefing has NO YAML. It's driven by Python dicts in three
files plus one Airflow DAG file. Memorise the order:

| # | File | What changes | Why |
|---|---|---|---|
| 1 | `dataxcel-ai-briefing/scripts/install_homepage_iframes.py` (`CUSTOMERS` dict, line ~67) | Add a dict entry for `<slug>` | Installs the iframe placeholder dashcard on Metabase D94 — output of running this script tells you the `dashcard_id` you need in step 2 |
| 2 | `scripts/update_construction_ceo_briefing.py` (`TARGETS` dict, line ~59, parent repo) | Add a dict entry for `<slug>` with the `dashcard_id` from step 1 | Universal construction-AR CEO briefing driver — queries `dbo.All_Receivable_Invoices` and dispatches any construction-AR tenant via `--target <slug>` |
| 3 | `metabase-migration/metabase_customer_audit/airflow/customer_ceo_briefing_dag.py` (`CUSTOMER_COMMANDS` dict, line ~73) | Add `"<slug>": "scripts/update_construction_ceo_briefing.py --target <slug>"` | Wires the weekly Monday 6 AM UTC DAG |
| 4 | (if Anthropic API key unavailable) `/tmp/briefing-<slug>.response.json` | Generate locally via `--local-claude emit` then write the JSON | Two-pass local-claude mode bypasses the API |
| 5 | Commit + push all three Python files | One commit each, separate repos | Lunstrum 2026-05-29: install_homepage_iframes.py + update_construction_ceo_briefing.py live in the PARENT repo; the DAG file lives in the `metabase-migration` submodule |

## Execution mode

Local file edits and dry-runs run unprompted. Each Metabase API write
(install_homepage_iframes.py run, update_construction_ceo_briefing.py consume),
each `git push`, and each Firestore push (via the `push_briefing` Cloud
Function) requires explicit `yes` confirmation.

## Step 1 — validate args

Required:
- `<slug>` — must match the customer slug from earlier onboarding skills.
- The customer must already have a working Metabase tenant. Best-effort
  HEAD `https://<slug>.xcel.report` — warn if it doesn't resolve, but
  allow continue.
- The customer must already have a homepage dashboard. Default is
  Metabase dashboard id `94` (the "Home" dashboard the customer-clone
  template ships with). Pass `--dashboard-id N` to override.

Optional:
- `--local-claude` — force the two-pass emit/consume flow (skip the
  Anthropic API). Defaults to OFF; if `ANTHROPIC_API_KEY` is unset, the
  skill flips it to ON automatically with a warning.
- `--dashboard-id N` — override the homepage dashboard id (default 94).
- `--api-key mb_...` — override the Metabase API key (default: shared
  `single.xcel.report` key from `XcelConnectAndUpdater/CLAUDE.md`).

Print a one-line plan:

> Plan: provision CEO weekly briefing for `<slug>` — install iframe on
> D<dashboard-id>, add to TARGETS, add to weekly DAG. Mode: API | local-claude.

## Step 2 — register the customer in `install_homepage_iframes.py` (LOCAL edit, no confirm)

Open `dataxcel-ai-briefing/scripts/install_homepage_iframes.py`. Locate
`CUSTOMERS = {` at line ~67. Append a new entry **before** the closing
brace, preserving the existing dict-of-dicts shape:

```python
"<slug>": {
    "tenant_id": "<slug>",
    "company_name": "<Display Name>",
    "industry_type": "service",          # or "construction" — ask user
    "metabase_url": "https://<slug>.xcel.report",
    "api_key": "<metabase-api-key>",     # shared key for tenants on single
    "dashboard_id": <dashboard-id>,      # default 94
    "tab_name": None,                    # multi-tab dashboards only
    "tab_id": None,
    "insert_row": 20,                    # below the natural KPI row
    "iframe_height": 14,
},
```

Validate the file still parses:

```bash
python3 -c "import ast; ast.parse(open('/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-ai-briefing/scripts/install_homepage_iframes.py').read())"
```

If it doesn't parse, stop and show the user the error.

## Step 3 — run `install_homepage_iframes.py` for the new customer (RISKY — confirm)

Confirm:

> Run `python scripts/install_homepage_iframes.py --only <slug>` in
> `dataxcel-ai-briefing/`? This writes to the customer's Metabase
> (adds the iframe dashcard on D<dashboard-id>). Idempotent. Type `yes`.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-ai-briefing
python3 scripts/install_homepage_iframes.py --only <slug>
```

Capture the **`dashcard_id`** from the SUMMARY line — it looks like:

```
<slug>      CREATED  install  dashcard=1628
```

You need that number in Step 4. If the script prints `EXISTS  unchanged`,
fetch the existing dashcard id with:

```bash
curl -s -H "x-api-key: <metabase-api-key>" \
  https://<slug>.xcel.report/api/dashboard/<dashboard-id> \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(c['id'],c.get('card_id'),(c.get('visualization_settings') or {}).get('iframe','')[:60]) for c in d['dashcards']]"
```

The right row is the one whose `iframe` value points at `ai.xcel.report`.

## Step 4 — register the customer in `update_construction_ceo_briefing.py` (LOCAL edit, no confirm)

Open `scripts/update_construction_ceo_briefing.py` in the PARENT repo (NOT the
`dataxcel-board-reports-pipeline` submodule — there is a same-named file
there and it is NOT the one you want). Locate `TARGETS = {` at line ~59.
Append a new entry:

```python
"<slug>": {
    "tenant_id": "<slug>",
    "url": "https://<slug>.xcel.report",
    "api_key": "<metabase-api-key>",
    "database_id": 2,                        # standard for cloned tenants
    "dashboard_id": <dashboard-id>,          # default 94
    "dashcard_id": <dashcard-id-from-step-3>,
    "company_name": "<Display Name>",
    "company_short": "<Short>",
},
```

Validate it still parses:

```bash
python3 -c "import ast; ast.parse(open('/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/scripts/update_construction_ceo_briefing.py').read())"
```

## Step 5 — first briefing run (RISKY — confirm)

Two paths. Pick based on `ANTHROPIC_API_KEY` and the `--local-claude` flag.

### 5a. Path A — Anthropic API available (default)

Confirm:

> Run `PYTHONPATH=. python3 scripts/update_construction_ceo_briefing.py --target <slug>`?
> This will: query the customer's Metabase, call Claude Opus to generate
> the briefing JSON (~$2-3 in API cost), push to Firestore via the
> `push_briefing` Cloud Function, and refresh the Metabase iframe URL with
> a fresh signed JWT. Type `yes`.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting
PYTHONPATH=. python3 scripts/update_construction_ceo_briefing.py --target <slug>
```

Expected tail:

```
[3/4] Pushing briefing to Firestore (tenants/<slug>/briefings/<date>)...
  Firestore push: ok
[4/4] Updating Metabase dashboard to iframe...
  JWT generated (30-day TTL)
  Dashboard <dashboard-id> dashcard <dashcard-id> → iframe
  Done!
  Briefing app: https://ai.xcel.report/briefing/<slug>?token=...
```

### 5b. Path B — local-claude two-pass (no API key, or `--local-claude` set)

Pass A — emit prompt + payload to `/tmp`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting
PYTHONPATH=. python3 scripts/update_construction_ceo_briefing.py --target <slug> --local-claude emit
```

This writes:
- `/tmp/briefing-<slug>.prompt.md` — full system prompt
- `/tmp/briefing-<slug>.input.json` — all SQL rollups + alert candidates

Now (still inside this Claude session): read the input.json, generate a
valid briefing JSON matching the schema in the prompt, write it to
`/tmp/briefing-<slug>.response.json`. The schema requires:

- `tenantId`, `date`, `weekLabel`, `generatedAt`, `categoriesIncluded`
- `summaries` — 10 entries (ar, ap, over_under_billing, project_mgmt,
  budget, balance_sheet, income_statement, bookkeeping, eoy_close,
  sage_setup). Pull factual rollups straight from
  `input.json["<category>"]["summary"]` — do NOT fabricate numbers.
- `criticalItems`, `warningItems`, `infoItems` — top-N picks from
  `input.json["<category>"]["critical_<entity>"]` lists. Score with the
  formulas in the prompt; severity tier by score.
- `wins` — 0-5 positive signals derived from recent_payments,
  newInvoices7d, healthy balance sheet, etc.

When response.json is written, pass B — consume + push:

```bash
PYTHONPATH=. python3 scripts/update_construction_ceo_briefing.py --target <slug> --local-claude consume
```

Same expected tail as Path A.

**Mike's rule (verbatim, 2026-05-29):** "we aren't making up numbers
this is not a demo... so if you don't have the data we don't make it
up". Empty AR? `criticalItems: []`. Empty AP? `criticalItems: []`. Do
not invent items to fill space.

## Step 6 — wire the weekly DAG (LOCAL edit, no confirm)

Open `metabase-migration/metabase_customer_audit/airflow/customer_ceo_briefing_dag.py`.
Locate `CUSTOMER_COMMANDS = {` at line ~73. Add:

```python
    "<slug>":  "scripts/update_construction_ceo_briefing.py --target <slug>",
```

If the customer is multi-company (Burbach pattern) or has a long initial
run-time, also add an entry to `CUSTOMER_TIMEOUTS` at line ~85:

```python
CUSTOMER_TIMEOUTS = {
    "burbach": timedelta(minutes=45),
    "brekhus": timedelta(minutes=25),
    "<slug>":  timedelta(minutes=20),     # if needed
}
```

Single-company customers default to 15 minutes; don't add a timeout
entry unless you have a reason.

Validate:

```bash
python3 -c "import ast; ast.parse(open('/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/metabase-migration/metabase_customer_audit/airflow/customer_ceo_briefing_dag.py').read())"
```

## Step 7 — commit + push (RISKY — confirm each)

Three separate repos. Show the user the three commit messages, then ask:

> Commit + push the three briefing-provisioning edits?
>
>   - PARENT repo: `feat(briefing): provision <slug> in install_homepage_iframes.py and TARGETS`
>   - metabase-migration submodule: `feat(briefing): add <slug> to weekly CEO DAG`
>
> Type `yes`.

On `yes`:

```bash
PARENT=/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting

# Parent repo — install_homepage_iframes.py is in the dataxcel-ai-briefing
# submodule, update_construction_ceo_briefing.py is in the parent — handle separately.

git -C "$PARENT/dataxcel-ai-briefing" add scripts/install_homepage_iframes.py
git -C "$PARENT/dataxcel-ai-briefing" commit -m "feat(briefing): add <slug> to homepage-iframe installer"
git -C "$PARENT/dataxcel-ai-briefing" push

git -C "$PARENT" add scripts/update_construction_ceo_briefing.py
git -C "$PARENT" commit -m "feat(briefing): provision <slug> in CEO weekly TARGETS"
git -C "$PARENT" push

git -C "$PARENT/metabase-migration" add metabase_customer_audit/airflow/customer_ceo_briefing_dag.py
git -C "$PARENT/metabase-migration" commit -m "feat(briefing): add <slug> to weekly CEO DAG"
git -C "$PARENT/metabase-migration" push
```

The parent repo will show the two submodules as modified after their
pushes — bump submodule pointers in a final parent-repo commit if your
workflow tracks them.

## Step 8 — summary + next step

```
Customer: <slug>
Metabase iframe: installed (dashcard <dashcard-id> on D<dashboard-id>)
First briefing push: ok — https://ai.xcel.report/briefing/<slug>?token=...
Weekly DAG: registered (next run Monday 6 AM UTC)
Commits + pushes: done (3 repos)

Verify in Metabase: open https://<slug>.xcel.report/dashboard/<dashboard-id>
The iframe should render the briefing app (not a CSP-block frame).

If the iframe is blocked: /configure-customer-metabase ensures
`ai.xcel.report` is in `allowed-iframe-hosts` — re-run that skill if
the iframe shows a CSP error.

Next: /validate-hub-dashboards <slug>
```

## What NOT to do — anti-patterns I (Claude) tried and got wrong

These are lessons from the Lunstrum onboarding (2026-05-29). They are in
this skill because every one of them costs an hour and Mike's patience:

1. **Do NOT create `dataxcel-board-reports-pipeline/customers/<slug>.yaml`.**
   That pipeline is AIS-only monthly board reports. The CEO weekly briefing
   has no YAML. If you find yourself filling in `departments:`,
   `industry_type:`, or `pages:` lists in a YAML file, you are in the
   wrong submodule — back out and edit the dicts above instead.

2. **Do NOT branch on the `dataxcel-board-reports-pipeline` submodule** to
   add a customer. The CEO weekly briefing doesn't touch that submodule
   at all. If you've branched, push it as an empty/abandoned branch and
   move on — don't try to make the YAML approach work.

3. **Do NOT ask Mike for "department codes."** The CEO weekly briefing
   auto-discovers departments from `dbo.stg_sage__departments` if the
   table has rows; empty is fine and matches the AIS/Puro3 pattern. If
   you find yourself asking for department codes, you're in the wrong
   pipeline (see anti-pattern #1).

4. **Do NOT create a separate `update_<slug>_ceo_briefing.py` per
   customer.** `update_construction_ceo_briefing.py` is the universal
   construction-AR driver — it queries `dbo.All_Receivable_Invoices`
   and dispatches every construction-AR tenant via `--target <slug>`.
   The only exceptions are `goodwin`/`single`/`jolma`, which have their
   own `update_<slug>_ceo_briefing.py` scripts because they query
   `dbo.Service_Invoices` instead (service-AR vs construction-AR — the
   SQL shape is different enough to keep separate). (Historical note:
   this file was named `update_ais_ceo_briefing.py` until 2026-05-30 —
   the rename happened because the old name made every onboarder think
   it was AIS-only.)

5. **Do NOT skip the iframe-install step assuming "the DAG will install
   the iframe on first run."** The DAG drives `update_construction_ceo_briefing.py
   --target <slug>` which UPDATES an existing dashcard's iframe URL. It
   does NOT create the dashcard. The dashcard must exist before the first
   DAG run, which is what Step 3 does.

6. **Do NOT generate fake numbers in `--local-claude` mode** to fill out
   `criticalItems`. Pull rollups straight from `input.json[category].summary`,
   pick real top-N items from `input.json[category].critical_*` lists,
   and leave empty lists empty. Mike's rule: "we aren't making up numbers
   this is not a demo".

7. **Do NOT re-edit the playbook §A.10 to point at
   `dataxcel-board-reports-pipeline`.** I already fixed it 2026-05-29 to
   point here. If you see a future edit reverting it, that's a
   regression — push back.
