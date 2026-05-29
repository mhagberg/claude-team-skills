---
name: onboard-customer
description: Walk through a new DataXcel customer onboarding end-to-end. Opens the HTML playbook, asks which phase you're in, and points you at the right sub-skill.
---

# onboard-customer

You are running the **onboard-customer** orchestrator. Your job is to open the
onboarding playbook for reference and route the user to the correct sub-skill
for their current phase. You do NOT auto-run the sub-skills — print the exact
command the user should type next.

## Step 1 — args & playbook open

Optional arg: `<slug>` (lowercase, alnum + dashes only). If supplied, validate
the format with a quick `[[ "$slug" =~ ^[a-z0-9-]+$ ]]` check; if invalid, stop
and tell the user.

Locate the playbook:

```bash
PLAYBOOK="/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/docs/new-customer-onboarding.html"
```

- If the file exists → `open "$PLAYBOOK"` (macOS `open`). Tell the user it
  opened in their browser.
- If it does NOT exist → print the full path and tell the user the playbook
  lives on the `feat/customer-onboarding-playbook` branch of
  `XcelConnectAndUpdater` and they need to check it out or merge it first. Do
  not invent contents — point at the file.

## Step 2 — ask which phase

Ask the user (one question, five choices):

> Which phase are you in?
>   1. **pre-call** — just got the customer; nothing provisioned yet
>   2. **post-call** — customer IT ran connect-netbird.ps1 and the SQL script; you have the NetBird IP
>   3. **hub** — Metabase + dbt are live; ready to install the Dashboard Hub menu (default for every new customer)
>   4. **briefing** — provision the CEO AI Briefing (default for every new customer; 60-day trial countdown built in; pass `--paid` if the customer has purchased outright)
>   5. **snapshots** — toggling dbt snapshots on/off for an existing customer

## Step 3 — route

Map the answer to the suggested sub-skill and print the exact command, filling
in `<slug>` if the user supplied it. Do NOT invoke the sub-skill — the user
runs it themselves so they can review args first.

| Phase | Command to print |
|-------|------------------|
| pre-call | `/onboard-customer-precall <slug> --sql-port <port> --sage-dbs <CompanyA,CompanyB>` |
| post-call | `/onboard-customer-postcall <slug> --netbird-ip <ip>` |
| hub | `/onboard-customer-hub <slug> --company "<name>" --metabase-url <url> --metabase-api-key <key>` |
| briefing | `/onboard-customer-briefing <slug>` (trial mode, 60-day default) — add `--paid` for a paid customer, or `--trial-days N` to override the default |
| snapshots | `/customer-snapshots <slug>` (add `--off` to disable) |

Also remind the user of the **default** canonical sequence:

> 1. pre-call
> 2. on-call (customer IT runs `connect-netbird.ps1` + `setup-sage-readonly-<slug>.sql`)
> 3. post-call
> 4. hub
> 5. briefing (default; 60-day trial built in — pass `--paid` only for paid customers)

## Step 4 — finish

Print a one-line summary: `Playbook open. Next: <command>.` Stop. Do not run
anything else.
