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
- `--paid` — skip the 60-day trial timer (Step 6). Use for customers
  who signed an annual subscription at onboarding; default is trial.
- `--trial-days N` — override the trial length (default 60).

Print a one-line plan:

> Plan: provision CEO weekly briefing for `<slug>` — install iframe on
> D<dashboard-id>, add to TARGETS, set 60-day trial timer, add to weekly DAG.
> Mode: API | local-claude.

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

## Step 6 — set the 60-day trial timer (RISKY — confirm, skip if `--paid`)

The briefing app shows an in-app trial countdown driven by three fields
on the Firestore tenant config: `subscriptionStatus`, `trialStartDate`,
`trialEndDate`. Without these, the countdown banner stays hidden and
the customer gets no urgency signal.

**Security note:** the Cloud Function uses a shared `API_SECRET`
(hardcoded at `dataxcel-ai-briefing/scripts/update_dashboard_links.py:14`)
that is not per-tenant. Anyone with that secret can write any tenant's
Firestore config — a known limitation tracked in `SECURITY_BACKLOG.md`.
For now, never embed the secret in checked-in source outside that one
file, and never email/Slack it.

If `--paid` was passed, **skip this step entirely** and print:

```
Skipping trial timer (--paid). To flip later, POST to set_tenant_config
with subscriptionStatus="active".
```

### 6a — idempotency pre-check (read-before-write)

Read the existing Firestore config first. If `subscriptionStatus` is
already `"trial"` or `"active"` for this tenant, **do not blindly
overwrite** — re-running Step 6 would silently reset
`trialStartDate`/`trialEndDate` to today and corrupt billing state.

Use the same Python `firebase_admin` path the seed scripts use:

```python
import firebase_admin
from firebase_admin import firestore
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={"projectId": "dataxcel-ai"})
snap = (firestore.client()
        .collection("tenants").document("<slug>")
        .collection("config").document("main").get())
existing = snap.to_dict() if snap.exists else {}
print({k: existing.get(k) for k in
       ("subscriptionStatus", "trialStartDate", "trialEndDate")})
```

If `existing.get("subscriptionStatus")` is `"trial"` or `"active"`,
print the existing dates and confirm:

> Tenant `<slug>` already has `subscriptionStatus=<existing>`,
> trial=<start>..<end>. Overwrite with a NEW <N>-day trial starting
> today? Typing `yes` resets the countdown — say `skip` to keep the
> existing trial dates.

On `skip`, jump to Step 7. On `yes`, proceed to 6b.

(If the Firestore read fails — auth, network — print the error, ask
"proceed without idempotency check? yes/no", and only proceed on
explicit `yes`. Never silently skip the pre-check.)

### 6b — compute dates portably (Python, not BSD `date`)

Do NOT use `date -u -v+60d` (BSD-only) or `date -u -d "+60 days"`
(GNU-only). Use Python so the skill works the same on macOS and Linux:

```bash
TRIAL_DAYS="<--trial-days N, default 60>"
read TODAY TRIAL_END <<<"$(python3 -c "
import datetime as dt
t = dt.datetime.now(dt.timezone.utc).date()
print(t.isoformat(), (t + dt.timedelta(days=$TRIAL_DAYS)).isoformat())
")"
test -n "$TODAY" -a -n "$TRIAL_END" || { echo "date math failed"; exit 1; }
```

Validate before showing the confirm prompt:
- `TRIAL_DAYS` parses as a positive int (reject 0, negative, non-numeric).
- `TRIAL_END > TODAY`.
- Both dates print as `YYYY-MM-DD`.

### 6c — confirm and POST (with real HTTP error handling)

Show the prompt with the actual resolved dates and trial length:

> Set <TRIAL_DAYS>-day trial timer for `<slug>`? trialStartDate=<TODAY>,
> trialEndDate=<TRIAL_END>, subscriptionStatus=trial. Type `yes`.

On `yes`, POST and **check the HTTP code AND parse the JSON body**.
A 401, 5xx, or unexpected JSON shape must surface as a hard failure —
not a silent success in the Step 9 summary:

```bash
RESP=$(mktemp)
HTTP=$(curl -sS -o "$RESP" -w "%{http_code}" \
  -X POST "https://set-tenant-config-b3yw34t2qq-uc.a.run.app" \
  -H "Authorization: Bearer $BRIEFING_API_SECRET" \
  -H "Content-Type: application/json" \
  -d "{
    \"tenant_id\": \"<slug>\",
    \"config\": {
      \"subscriptionStatus\": \"trial\",
      \"trialStartDate\": \"${TODAY}T00:00:00Z\",
      \"trialEndDate\": \"${TRIAL_END}T00:00:00Z\"
    }
  }")

if [ "$HTTP" != "200" ]; then
  echo "FAIL: set_tenant_config returned HTTP $HTTP"
  cat "$RESP"; rm "$RESP"; exit 1
fi
python3 -c "
import json, sys
r = json.load(open('$RESP'))
assert r.get('status') == 'ok' and r.get('tenant_id') == '<slug>', r
print('OK:', r)
" || { echo "FAIL: bad JSON shape"; cat "$RESP"; rm "$RESP"; exit 1; }
rm "$RESP"
```

`$BRIEFING_API_SECRET` must be exported in the shell before this step
(read it from `dataxcel-ai-briefing/scripts/update_dashboard_links.py:14`,
or from `dataxcel-ai-briefing/.env` if present). The skill MUST refuse
to embed the literal secret in this SKILL.md or any other operator-facing
doc — point operators at the source-of-truth file instead.

### 6d — verify (read-back)

After the POST returns OK, read the tenant config again and assert the
three fields landed:

```python
snap = (firestore.client()
        .collection("tenants").document("<slug>")
        .collection("config").document("main").get())
got = snap.to_dict()
expected = {
    "subscriptionStatus": "trial",
    "trialStartDate": f"{TODAY}T00:00:00Z",
    "trialEndDate":   f"{TRIAL_END}T00:00:00Z",
}
for k, v in expected.items():
    assert got.get(k) == v, f"{k}: expected {v!r}, got {got.get(k)!r}"
print("verified: trial countdown live for <slug>")
```

Only after the read-back assertion passes does Step 9's summary line
print `Trial: <N>-day countdown set, expires <TRIAL_END>`.

### Flipping trial → active later

When the customer signs an annual subscription, POST again with
`"subscriptionStatus": "active"` (and optionally clear the trial dates
if you want the banner gone). There is no SKU-to-Firestore automation —
this is a manual flip. Same idempotency pre-check applies.

## Step 7 — wire the weekly DAG (LOCAL edit, no confirm)

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

## Step 8 — commit + push (RISKY — confirm each)

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

## Step 9 — summary + next step

```
Customer: <slug>
Metabase iframe: installed (dashcard <dashcard-id> on D<dashboard-id>)
First briefing push: ok — https://ai.xcel.report/briefing/<slug>?token=...
Trial: <60-day countdown set, expires YYYY-MM-DD | --paid, no trial>
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
