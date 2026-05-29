---
name: onboard-customer-hub
description: Register a customer in the Dashboard Hub — append to TENANT_INSTANCES, write Firestore config, mint the 10-year JWT, install the Metabase iframe. Wraps register_tenant.py.
---

# onboard-customer-hub

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

## Step 2 — run register_tenant.py (RISKY — confirm)

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

## Step 3 — commit + push hub changes (RISKY — confirm push)

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

## Step 4 — summary + next step

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
