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

Required:
- `<slug>` — must match the customer slug from earlier onboarding skills.

Required (prompt if missing — one at a time):
- `--company "<name>"` — display name (e.g. `"Acme Construction"`).
- `--metabase-url <url>` — usually `https://<slug>.xcel.report`.
- `--metabase-api-key <key>` — Metabase admin API key for the customer
  tenant. Mike generates this in the Metabase admin panel; tell the user
  where to find it if they don't have one.

Optional pass-throughs:
- `--domains acme.com,acme.io` — used by Hub for view-count filtering.
- `--restrict-collection <id>` — if scoping the Hub to one Metabase collection.

Print a one-line plan summary.

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
