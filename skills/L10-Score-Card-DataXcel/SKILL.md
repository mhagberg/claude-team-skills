---
name: L10-Score-Card-DataXcel
description: Generate Mike's weekly DataXcel L10 (EOS Level-10) scorecard as a self-contained HTML file. Pulls Sales/Marketing/Development/Usage metrics from Odoo (XML-RPC), Google Analytics (GA4), PostHog, and Linear; counts demos from Google Calendar. Use when Mike runs /L10-Score-Card-DataXcel or asks for "the L10 scorecard", "weekly scorecard", or "L10 numbers".
---

# L10-Score-Card-DataXcel

Build the weekly L10 scorecard HTML for Mike, then open it for review. Default
window is the **current week (Mon–Sun containing today)** — the live L10 week
(override with `--start/--end`). GA page-views/engagement always use a trailing
28-day window regardless.

## Metric sources

| Metric | Source | How |
|--------|--------|-----|
| New Qualified Leads | Odoo CRM | opps created in window, qualified+ stage |
| # of Referrals | Odoo CRM | leads created in window tagged ASG/RKL/Wright/CBS/ServerNova |
| Number of Demos | **Google Calendar (you, via MCP)** | count demo events in window → pass `--demos N` |
| Quotations Sent (#/$) | Odoo `sale.order` | DataXcel quotes (a line's product name contains "DataXcel") created in window, non-cancelled |
| Hours Billed (#/$) | Odoo invoices | posted customer-invoice lines on **hourly dev products** (product name contains "Hour") |
| Odoo Page Views | Odoo `website.track` | tracked views in window |
| GA Page Views / Avg Engagement | GA4 API | property 483003616, creds `~/.secrets/ga4-reader.json`. **Trailing 28-day window** (`GA_WINDOW_DAYS`, matches Mike's GA "Pages and screens" report Total ≈437), NOT the weekly window. Engagement = site-wide avg/active user (GA "Total"), NOT the max page |
| PostHog Page Views / Avg Engagement | PostHog | project 425826, key `~/.secrets/posthog-personal-api-key` (shown as "extra", not in the canonical 13) |
| Pending Reports / Data Inaccuracies | Linear | **team SAG (SageXcel)** active cycle, not-done. Data Inaccuracies = Bug-labelled; Pending Reports = the rest |
| Paid Logged-in Users/Week | Metabase RDS | `dataxcel-user-tracking` weekly-active customer users |

## Steps

1. **Count demos from Google Calendar.** Use the `gcal` MCP `list-events` for the
   target window across Mike's **owned calendars** (at least `mhagberg@xcel.software`
   and `scline@xcel.software`). A demo is any event whose title:
   - **starts with "Appointment with Mike"** (the DataXcel demo-booking link
     creates these as "Appointment with Mike (Customer Name)"), OR
   - **contains "DataXcel Demo"**, OR
   - **contains "demo"** (case-insensitive).
   De-dupe events that appear on multiple calendars (same event id). Exclude
   standups, lunches, OOO, payroll, birthdays, the TUG conference block. Pass the
   count as `--demos N`.

2. **Run the generator with the PARENT project's venv** (GA4 lib lives there):

   ```bash
   /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.venv/bin/python \
     "$(dirname "$0")/scripts/generate_scorecard.py" --demos <N> --json
   ```

   Optional flags: `--start YYYY-MM-DD --end YYYY-MM-DD`, `--out PATH`,
   `--pending-reports N`, `--data-inaccuracies N` (manual fallback if Linear is down).

3. The script writes `~/Downloads/l10_scorecard_<start>_<end>.html`, **auto-opens
   it** (pass `--no-open` to suppress), and prints a JSON summary. Any metric it
   couldn't pull shows `N/A — <reason>` and is listed under `NEEDS ATTENTION` on
   stderr — relay those to Mike.

4. The HTML opens automatically on finish. (If `--no-open` was used: `open <path>`.)

## Credentials (all outside the repo — never commit)

- `~/.secrets/ga4-reader.json` — GA4 service account
- `~/.secrets/posthog-personal-api-key` — PostHog personal key
- Linear key: `LINEAR_API_KEY` in the parent `.env` (this wins) or `~/.secrets/linear-api-key`. Raw key, **no** `Bearer` prefix. (A bad key returns HTTP 401 "not authenticated".)
- Odoo creds via `odoo_bank_metabase_payroll_reporting/.env`
- Metabase RDS creds via `dataxcel-user-tracking/config/instances.yaml`

## Config to confirm (top of `generate_scorecard.py`)

- `REFERRAL_TAG_IDS` — verify the tag IDs really map to ASG / RKL / Wright Office
  Solutions / CBSL / SeverNova (some were fuzzy: CBS vs CBSL, ServerNoav vs SeverNova).
- `LINEAR_INACCURACY_LABELS` — which Linear labels mean "data inaccuracy" vs a
  pending report (the rest of not-done cycle issues = Pending Reports).
- `QUALIFIED_STAGE_IDS` — stages that count as a "qualified" lead.

## Notes

- Everything is read-only except writing the HTML file. The script never writes
  to Odoo / Linear / Metabase.
- Each metric is isolated; one dead source never blocks the rest of the report.
