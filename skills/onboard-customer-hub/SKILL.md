---
name: onboard-customer-hub
description: Register a customer in the Dashboard Hub — append to TENANT_INSTANCES, write Firestore config, mint the 10-year JWT, install the Metabase iframe. Wraps register_tenant.py.
---

# onboard-customer-hub

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer-hub <slug>` becomes `/onboard-customer-hub lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer-hub** skill. Goal: register a new
tenant in the Dashboard Hub (`home.xcel.report`). The heavy lifting is in
`dataxcel-dashboard-hub/scripts/register_tenant.py`; your job is to gather
args, confirm the risky run, and commit the resulting code edits.

**Execution mode:** the script writes to Metabase + Firestore + local source
files. The single `register_tenant.py` invocation is the one RISKY step and
must be confirmed. The follow-up Git push is also RISKY.

## Step 1 — validate args

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug used in every prior onboarding skill (`/onboard-customer-precall` → `/onboard-customer-oncall` → `/onboard-customer-postcall`). |
| `--company "<name>"` | Optional | Display name. Defaults to title-cased slug (`lunstrum` → `Lunstrum`). Mike's `--company-name` from `/onboard-customer-precall` is the canonical source if it was supplied. |
| `--metabase-url <url>` | Optional | Defaults to `https://<slug>.xcel.report` — the tenant created by `/onboard-customer-precall` Step 3. |
| `--metabase-api-key <key>` | Optional | Defaults to the shared `single.xcel.report` key `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=` (same key every other onboarding skill uses on shared-cluster customers). For dedicated-instance customers (`dd`, `brekhus`, `jolma`, `vertex`, `4x`, `burbach`, `ipwlc`, `nvision`, `pcg`), reads the row from `XcelConnectAndUpdater/CLAUDE.md` Metabase Instances & API Keys table. Pass `--metabase-api-key` only to override the resolved value. |
| `--domains <list>` | Optional | Comma-separated email domains for Hub view-count filtering. Skip if unknown — only matters for Hub's usage metrics. |
| `--restrict-collection <id>` | Optional | If scoping the Hub to one Metabase collection. Default: not set (Hub surfaces every non-excluded dashboard). |

Required:
- `<slug>` — must match the customer slug from earlier onboarding skills.

Resolve defaults silently — do NOT prompt for values that have sensible
defaults. Only prompt if the slug fails the regex.

Print a one-line plan summary with all resolved values.

## Step 2 — preflight: gcloud ADC + Firebase login

`register_tenant.py` writes to Firestore using google-cloud-firestore,
which requires Application Default Credentials. The deploy step (Step 4)
uses the Firebase CLI. Both can be expired and there's no good error
message if so — the script reports "Firestore write failed" only after a
60-second hang.

Tell the user:

> Confirm gcloud ADC + Firebase CLI are authed for project `dataxcel-hub`?
> Quick check — type `! gcloud auth application-default print-access-token`
> in the prompt. If it prints a token, ADC is fresh. If it errors with
> "reauthentication needed", run:
>     ! gcloud auth application-default login
> Then for Firebase:
>     ! firebase login --reauth     (only if Step 4 fails)

Don't proceed until ADC is fresh. Lunstrum 2026-05-30: I (Claude) ran
register_tenant.py with stale ADC, got a 60s timeout on the Firestore
write, and the script half-completed (TENANT_INSTANCES updated, Firestore
config NOT written) — then we had to re-run after the user reauth'd.

## Step 3 — run register_tenant.py (RISKY — confirm)

Confirm:

> Run this command? It writes to:
>   - dataxcel-dashboard-hub/functions/main.py (appends to TENANT_INSTANCES)
>   - Firestore tenants/<slug>/config/main (companyName, metabaseUrl,
>     metabaseApiKey, enabled: true)
>   - dataxcel-dashboard-hub/scripts/generate_iframe_snippets.py (appends slug)
>   - Customer Metabase (adds home.xcel.report to allowed-iframe-hosts,
>     snapshots + installs Hub iframe at row 0 of the custom-homepage
>     dashboard)
>
>   cd dataxcel-dashboard-hub
>   python scripts/register_tenant.py <slug> \
>     --company "<name>" --metabase-url <url> --metabase-api-key <key> \
>     [--domains <list>] [--restrict-collection <id>]
>
> Type `yes`.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-dashboard-hub
python scripts/register_tenant.py <slug> \
  --company "<name>" --metabase-url <url> --metabase-api-key <key> \
  [optional flags]
```

Show the script's stdout to the user verbatim (it prints the iframe URL and
the install_hub_iframe.py outcome). If the script exits non-zero, stop and
print the traceback — do NOT push the partial state.

## Step 4 — deploy Cloud Functions so the new TENANT_INSTANCES is live (RISKY — confirm)

**THIS STEP USED TO BE MISSING AND IS THE MAIN REASON LUNSTRUM SHOWED
SINGLE.XCEL.REPORT URLS FOR 24 HOURS.** `register_tenant.py` edits
`functions/main.py` locally, but the deployed Cloud Function still uses
the OLD `TENANT_INSTANCES` until you redeploy.

Symptom when this step is skipped: the Hub iframe loads on the customer
Metabase, but the SPA shows demo dashboards (with `demo.xcel.report` /
`single.xcel.report` URLs) because:

  - `tenants/<slug>/installed/current` is empty (sync_usage_data
    doesn't know about the new tenant)
  - the SPA falls back to popular dashboards from `system/popularity`,
    which all carry demo public-preview URLs

Confirm:

> Deploy the Hub Cloud Functions so the new tenant `<slug>` is included
> in the next `sync_usage_data` run? This updates all 5 functions
> (`sync_usage_data`, `check_dashboard_health`, `validate_token`,
> `set_tenant_config`, `on_new_event`). Idempotent — same code, just
> picks up the new `TENANT_INSTANCES` entry. Type `yes`.

On `yes`:

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-dashboard-hub
firebase deploy --only functions --project dataxcel-hub --force
```

## Step 5 — trigger sync immediately (optional but recommended)

`sync_usage_data` runs daily at 06:00 Mountain Time. If you want
`<slug>` to populate in the Hub today instead of tomorrow morning,
force-run via Cloud Scheduler:

```bash
gcloud scheduler jobs run firebase-schedule-sync_usage_data-us-central1 \
  --location=us-central1 --project=dataxcel-hub
```

If gcloud auth misbehaves in the shell, fall back to the Firebase
console: Cloud Scheduler → `firebase-schedule-sync_usage_data-us-central1`
→ "Force run". Takes ~3-5 minutes across all tenants.

After the sync completes, verify `tenants/<slug>/installed/current`
contains the customer's actual dashboards (not demo dashboards):

```bash
# Quick check — should print the customer's metabase URL
python3 -c "
from google.cloud import firestore
db = firestore.Client(project='dataxcel-hub')
doc = db.collection('tenants').document('<slug>').collection('installed').document('current').get()
d = (doc.to_dict() or {}).get('dashboards', [])
print(f'{len(d)} dashboards; first URL: {d[0][\"metabaseUrl\"] if d else \"none\"}')"
```

The printed URL MUST start with `https://<slug>.xcel.report/` (not
`demo.xcel.report` or `single.xcel.report`). If it doesn't, sync didn't
pick up the tenant — re-verify `TENANT_INSTANCES` was deployed in
Step 4.

## Step 6 — commit + push hub changes (RISKY — confirm push)

Confirm:

> Commit `functions/main.py` + `scripts/generate_iframe_snippets.py` on
> `dataxcel-dashboard-hub` with message `feat(hub): register tenant <slug>`?
> Push to origin? Type `yes`.

On `yes`:

```bash
SUBMODULE=/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-dashboard-hub
git -C "$SUBMODULE" add functions/main.py scripts/generate_iframe_snippets.py
git -C "$SUBMODULE" commit -m "feat(hub): register tenant <slug>"
git -C "$SUBMODULE" push
```

If there are other dirty files in the submodule, ask the user before staging
broader. Default = stage only the two files above.

## Step 7 — summary + next step

```
Customer: <slug>
Hub registry: appended to TENANT_INSTANCES
Firestore: tenants/<slug>/config/main written (enabled: true)
JWT: minted (10-year HS256), iframe URL printed above
Metabase iframe: installed on home dashboard

Note: Usage sync runs at 06:00 MT daily via the Firebase Cloud Function
`sync_usage_data`. To see data sooner, trigger it manually from the
Firebase console.

Onboarding for <slug> is COMPLETE.
```

Stop.
