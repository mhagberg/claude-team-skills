# claude-team-skills

Shared Claude Code skills for the Xcel Software team. Each skill spawns multiple independent reviewer agents in parallel and consolidates their findings into a single, easy-to-read report.

## Available skills

| Skill | What it does |
|-------|--------------|
| `/parallel-code-review` | 5 independent agents review the current `git diff` (or a PR), each rate 1–10. Consolidated table + recommendations. |
| `/parallel-plan-review` | 5 independent agents review discovered plan files in parallel, each rate 1–10. Consolidated table + recommendations. |
| `/books-audit` | 10 independent agents audit the Xcel + Hagberg Odoo books in parallel — balance integrity, bookkeeping mistakes, tax deductions, tax red flags. Emits a styled **HTML report** (auto-opens) with a P&L summary, CFO/CTO perspective, and a one-click copy-paste **action item** under each finding to run the fix in Claude Code. Read-only. |
| `/onboard-customer <slug> [--from-phase N]` | **End-to-end walkthrough — drives every phase 1-10 in order, confirms before invoking each sub-skill, and pipes captured values (NetBird IP, SQL port, Sage DB, `database_id`, user emails) forward so the operator never has to retype them.** Opens the HTML onboarding playbook for reference, then steps through pre-call → on-call → post-call → hub → configure → validate-hub → validate-numbers → briefing → finalize → register-status-page. `--from-phase N` resumes mid-flow after a fix. |
| `/onboard-customer-precall <slug>` | Pre-call staging (~30 min before the IT meeting): 1Password entry prompt, EKS Metabase tenant clone (with mandatory session-blocking workaround + ownership transfer), Namecheap CNAME instructions, draft `profiles.yml`/`single_customers.py` entries with `<TBD>` placeholders, and NetBird provisioning with a placeholder SQL port (the live port is set in oncall). **Only required arg: `<slug>`.** |
| `/onboard-customer-oncall <slug>` | Live-call skill: confirms pre-call ran, prints the IT-facing quickstart URL, pauses for IT to install NetBird, captures NetBird IP + real SQL port via pause-prompts, updates the NetBird policy port (placeholder → real), renames the peer to `<slug>-sage`, prints the sysadmin-script URL, captures the `dataxcel` SQL password, lists Sage company DBs via `SELECT name FROM sys.databases` and asks Mike which is live, creates `dataxcel_analytics`, and writes everything back to `XcelConnectAndUpdater/CLAUDE.md`. **Only required arg: `<slug>`.** |
| `/onboard-customer-postcall <slug>` | Post-call wiring (~15 min after the call): fills `profiles.yml` with the real NetBird IP / SQL port / Sage DB / dataxcel password (from CLI flags OR by reading the customer table the on-call skill just wrote), pushes `single_customers.py`, triggers the dbt DAG, adds Metabase DB + schema sync, clones the dashboard seed-set. Optional flags: `--netbird-ip`, `--sql-port`, `--sage-db`, `--dataxcel-pw`. |
| `/onboard-customer-hub <slug>` | Provision the Dashboard Hub: wraps `register_tenant.py` (TENANT_INSTANCES + Firestore + JWT + iframe install). |
| `/onboard-customer-briefing <slug>` | Provision the CEO AI Briefing. **Default: 60-day trial countdown.** Pass `--paid` for paid customers (no trial), or `--trial-days N` to override the default 60. |
| `/onboard-customer-wth347 <slug>` | Install/refresh the per-customer signed-URL iframe for the WTH-347 Davis-Bacon certified-payroll app on the customer's Metabase WH-347 dashboard. **🛑 CURRENTLY BLOCKED** — per-customer signed-URL infrastructure is `wth-347-davis-bacon` Phase 6 work and has not shipped yet; the skill verifies the dashboard exists, reports the current demo URL, and exits with a BLOCKED banner instead of pretending the install worked. Re-run once Phase 6 ships and `install_wth347_iframe.py` exists. |
| `/configure-customer-metabase <slug>` | **Configure-the-tenant step — runs after `/onboard-customer-hub`, before any validation.** Sets site name, site URL (HTTPS), report timezone (IANA, default `America/Boise`), email From Name + Reply-To, iframe allowlist (`board`, `home`, `ai`, `metagent.app`), custom-homepage-dashboard = `Dashboard Report Menu`, and archives leftover demo users (`Corbin Taylor`, `DataXcel PlayGround User`, `Julie Allen`, `Randy Fullmer`, `playground@xcel.software`, plus anything else not on the keep-allowlist). **The AI agent does all of this automatically using the shared `single.xcel.report` Metabase API key.** Each write requires `yes`. |
| `/validate-hub-dashboards <slug>` | **Gate AFTER `/configure-customer-metabase`, BEFORE `/validate-customer-metabase`.** Health-checks every dashboard the Dashboard Hub will surface — executes every card via the Metabase REST API, reports pass / empty (warn) / failing. Mirrors the production `check_dashboard_health` Cloud Function. Catches Hallowell-style stale-field-id failure modes. Read-only. |
| `/onboard-writeback <slug> [--from-phase N]` | **End-to-end walkthrough to turn on Sage 100 Contractor WRITE-BACK for an already-onboarded customer** (Claude creates change orders / AP invoices / journal entries via the native API). Drives 4 phases — Sage least-priv user → operator provisioning → customer one-click install → record + verify (dry-run) — confirming before each and piping captured values (setup key, agent token, mesh IP) forward. Runs after `/onboard-customer`. Customer side is **one PowerShell command**. |
| `/onboard-writeback-provision <slug> --company-db "<db>" --datasource <ds> --sage-user <user>` | Operator side: wraps `Sage-API-Write-Back/deploy/provision-customer.sh` — creates the customer's NetBird group + auto-join setup key + a SCOPED **TCP-9447-only** policy (`MCPConnector → customer-<slug>`), mints the agent token (NetBird API token from Google Secret Manager), and prints the single PowerShell command + the IT-facing HTML quickstart to send the customer. |
| `/onboard-writeback-register <slug> --mesh-ip <ip> --agent-token <swa_…>` | Close-out: records `sage_agent_url` + `sage_agent_token` on the lead, then verifies the connector reaches `/healthz`, pins the agent TLS cert (P1 #10), and a **dry-run** write previews cleanly (name-matched, confirm_token issued — nothing committed). |
| `/validate-customer-metabase <slug>` | **Gate before users get access.** Runs every available Metabase-vs-Sage validator (Balance Sheet, Income Statement / Cash Basis 51-test pytest, AR/AP Aging, `posting_date` filter coverage) within `--tolerance`. Read-only. Refuses to print a `Next:` pointer if any validator fails — Mike's hard rule (2026-05-29): "we need to make sure the numbers validate against the Sage reports before we add the users and give them access." |
| `/finalize-customer-metabase <slug> --users ...` | **Last step before go-live.** Invites the customer's users (regular + admin). Hard prerequisite: `/configure-customer-metabase`, `/validate-hub-dashboards`, AND `/validate-customer-metabase` must all have passed. This skill no longer touches site URL / timezone / iframe allowlist / demo-user archive — those moved to `/configure-customer-metabase`. Each write requires `yes`. |
| `/register-customer-status-page <slug>` | **Phase 10 — final onboarding step.** Appends `<slug>` to `INSTANCES` in `dataxcel-customer-report/customer_report/registry.py` (AST-validated + unit-tested), commits + pushes a feature branch in the submodule, and triggers a one-off `customer_report_dag` run so the customer appears at `https://customers.xcel.report`. Only required arg: `<slug>`. Optional flags: `--company`, `--multi`, `--refresh-dag`, `--odoo-sub`, `--internal`. |
| `/install-team-skills` | Idempotent installer/updater — clones repo if missing, pulls latest, runs `./install.sh`, confirms every skill resolves. |
| `/customer-snapshots <slug>` | Flip dbt snapshots on/off for an existing customer in `single_customers.py` (or `rollup_customers.py`). Add `--off` to disable. |

See [`CLAUDE.md`](./CLAUDE.md) for the design spec.

## Notation

In this README, in every SKILL.md, and in the HTML playbook at
`XcelConnectAndUpdater/docs/new-customer-onboarding.html`, anything in
`<angle brackets>` is a **placeholder** — replace it with your actual
value. Example: for the customer named `lunstrum`, `<slug>` means
`lunstrum`, so `/onboard-customer <slug>` becomes
`/onboard-customer lunstrum`. Anything NOT in angle brackets is literal
text you type as-is.

## Onboarding a new DataXcel customer

The canonical sequence, wired to slash commands. Source of truth for the
underlying process is the HTML playbook at
`XcelConnectAndUpdater/docs/new-customer-onboarding.html` — open it with
`/onboard-customer` and follow along.

Every required arg below is a value Mike has in hand at the moment that
step starts. Values produced by an earlier step are passed forward by
the printed `Next:` line OR re-read from `XcelConnectAndUpdater/CLAUDE.md`,
which the live-call skill updates as soon as IT reports them.

1. **Pre-call** (Mike, ~30 min before the IT meeting):
   `/onboard-customer-precall <slug>`
   Only `<slug>` required. Optional `--company-name "<Display>"`
   (defaults to title-cased slug). NetBird is provisioned with a placeholder
   SQL port of `1433` — that gets corrected during the call.
2. **On the call with customer IT** (~30–45 min):
   `/onboard-customer-oncall <slug>`
   The skill prints the IT-facing quickstart URL for Mike to forward
   (`https://broker.xcel.report/updates/quickstart-<slug>.html`) and
   pauses for IT to run the install. It then captures the NetBird IP +
   real SQL port + `dataxcel` password via pause-prompts, lists the
   customer's Sage company DBs via `SELECT name FROM sys.databases`,
   updates the NetBird policy port, renames the peer to `<slug>-sage`,
   creates `dataxcel_analytics`, and writes everything to
   `XcelConnectAndUpdater/CLAUDE.md`. **No customer-IT-runs-X copy-pasta
   in this README — the skill prints the line for Mike to forward, per
   the skill-first rule.**
3. **Post-call** (Mike/Ty, ~15 min after the call):
   `/onboard-customer-postcall <slug> --netbird-ip <ip>`
   `--netbird-ip` is optional — if omitted (or any of `--sql-port`,
   `--sage-db`, `--dataxcel-pw`), the skill reads the values from the
   customer table in `XcelConnectAndUpdater/CLAUDE.md` (the on-call
   skill just wrote them there).
4. **Provision the hub** (the default dashboard menu — iframed into their Metabase):
   `/onboard-customer-hub <slug>`
   Only `<slug>` required. `--company`, `--metabase-url`, and
   `--metabase-api-key` all default sensibly (title-cased slug,
   `https://<slug>.xcel.report`, shared `single.xcel.report` API key —
   override only for dedicated-instance customers).
5. **Configure the Metabase tenant** (every customer's Metabase gets the
   same canonical configuration — site name, HTTPS site URL, IANA
   timezone, email From Name + Reply-To, iframe allowlist, custom
   homepage dashboard, and archives leftover demo users):
   `/configure-customer-metabase <slug> [--site-name "<Display>"] [--timezone <IANA>] [--archive-allowlist email1,email2,...]`
   **The AI agent does all of this automatically using the shared
   `single.xcel.report` Metabase API key.** Each write asks for `yes`.
6. **Validate every dashboard the hub will surface** (read-only):
   `/validate-hub-dashboards <slug> [--timeout 60]`
   Hard gate — if any card fails, fix before proceeding (Hallowell-style
   stale-field-id is the most common cause; see `metabase-migration/pmbql_migrate.py`).
7. **Validate the Metabase numbers against Sage** (read-only — no writes,
   runs BEFORE any user is added or invited):
   `/validate-customer-metabase <slug> [--reports balance,income,wip,jobcost] [--tolerance 0.01]`
   Runs every available Metabase-vs-Sage validator. **Hard gate —
   Mike's rule (2026-05-29):** do NOT add users until validation is green.
8. **Provision the CEO AI Briefing** (default — 60-day trial built in):
   `/onboard-customer-briefing <slug>`
   (pass `--paid` for a customer who has purchased the briefing outright,
   or `--trial-days N` to override the default 60.)
9. **Install the WTH-347 Davis-Bacon per-customer signed-URL iframe**
   (when the customer has the WH-347 certified-payroll dashboard):
   `/onboard-customer-wth347 <slug>`
   **🛑 CURRENTLY BLOCKED — per-customer signed-URL infra has not shipped
   yet** (wth-347-davis-bacon is pre-Phase-1). The skill verifies the
   dashboard, reports the current shared-demo URL, and exits without
   mutating anything. Once `wth-347-davis-bacon` Phase 6 ships and
   `install_wth347_iframe.py` lives in
   `dataxcel-board-reports-pipeline/scripts/` (modelled after the briefing
   installer), this step will mint a per-customer signed URL and swap the
   demo iframe for it. **Until then every real customer's WH-347
   dashboard iframes the shared `wth347-demo.web.app` demo URL** — do not
   pretend otherwise.
10. **Finalize the Metabase tenant** (invites the customer's users). Hard
    prerequisite: steps 5, 6, and 7 must all have passed.
    `/finalize-customer-metabase <slug> --users <email1>,<email2> [--admin-users ...]`
12. **Register the customer on the daily status page** (last step of the
    canonical sequence — makes the customer visible on
    `https://customers.xcel.report`):
    `/register-customer-status-page <slug>`
    Only `<slug>` required. Optional `--company "<Display>"`, `--multi`
    (for rollup customers), `--refresh-dag <dag_id>` (override the
    `<slug>_dataxcel_analytics_dbt_dag` default), `--odoo-sub
    S00150,S00007` (S-numbers from the customer's Odoo subscription
    quotes), `--internal` (mark as internal demo / playground row).
    Appends to `dataxcel-customer-report/customer_report/registry.py`,
    pushes a feature branch, and triggers a one-off
    `customer_report_dag` run so the new row appears tonight instead of
    tomorrow.
13. **Optional — flip snapshots later:** `/customer-snapshots <slug>`
    (pre-call already defaults new customers to `snapshots=True`; only use this
    to flip an existing customer).

### CEO AI Briefing — 60-day trial by default

**Reversed 2026-05-29.** Every new DataXcel customer now gets the CEO AI
Briefing provisioned during onboarding, with a built-in **60-day trial
countdown**. Mike does not have to remember to opt anyone in — the briefing
is part of the canonical sequence above (step 5).

What "60-day trial" means end-to-end:

- `customers/<slug>.yaml` gets `trial: true` (the briefing skill writes this
  by default). The pipeline's `install_briefing_iframe.py` reads the flag
  and mints the signed viewer URL with two extra claims: `trial_started`
  and `trial_until` (UTC ISO 8601, now + 60 days).
- The `board.xcel.report` iframe on the customer's Metabase home dashboard
  shows a countdown ("Trial — N days remaining"). At the end of 60 days the
  banner flips to "trial expired, contact sales" and the monthly DAG
  ShortCircuits — no more reports, no more Claude spend. (Viewer-side
  banner + DAG gate are follow-ups; the claims and URL params already flow
  through.)
- For customers who have **purchased** the briefing, pass `--paid`:
  ```
  /onboard-customer-briefing <slug> --paid
  ```
  This writes `trial: false` into the YAML — no countdown, no expiry banner,
  no DAG ShortCircuit.
- Existing customers like AIS who were provisioned before this change keep
  their no-`trial`-field YAML and are treated as paid. The installer will
  NOT silently put a legacy customer into a trial.

Idempotent re-runs refresh both the signed URL AND the trial countdown. If
a trial customer upgrades, re-run with `--paid`; the next iframe refresh
strips the trial claims and they're instantly upgraded.

All onboarding skills **execute commands directly** and ask for an explicit
`yes` confirmation only on **risky** steps (writes to remote Git, kubectl
apply, NetBird API mutations, Metabase API writes, Firestore writes, dbt DAG
triggers). Read-only checks and local file edits run without prompting.

## Install (each teammate runs once)

```bash
git clone git@github.com:mhagberg/claude-team-skills.git ~/claude-team-skills
cd ~/claude-team-skills
./install.sh
```

`install.sh` symlinks each `skills/<name>/` directory into `~/.claude/skills/<name>/`. Because they are symlinks, a `git pull` in `~/claude-team-skills` instantly updates the live skill for every Claude Code session on your machine — no re-install needed.

If a skill of the same name already exists in `~/.claude/skills/`, it is moved aside to `<name>.bak.<timestamp>/` before the symlink is created. Nothing is silently overwritten.

## Uninstall

```bash
cd ~/claude-team-skills
./uninstall.sh
```

Removes the symlinks. Does not touch your `.bak.*` backups.

## Update

```bash
cd ~/claude-team-skills
git pull
```

That's it — symlinks pick up the new content immediately.

## Using a skill

In any Claude Code session, type the slash command, e.g.:

```
/parallel-code-review
/parallel-code-review 1234           # review GitHub PR #1234
/parallel-plan-review
/parallel-plan-review docs/plans/    # only review plans in this path
```

Claude will spawn 5 reviewer agents in parallel, wait for all to return, then print a consolidated table and recommendations.

## Adding a new skill

1. Create `skills/<your-skill>/SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: your-skill
   description: One-line summary shown in the skill picker.
   ---

   Instructions to Claude go here in plain prose.
   ```
2. `./install.sh` (idempotent — picks up new skills, leaves existing symlinks alone).
3. Commit and push. Teammates `git pull` and it shows up.

## Repo layout

```
claude-team-skills/
├── README.md              ← you are here
├── CLAUDE.md              ← design spec for AI maintainers
├── install.sh             ← symlinks skills into ~/.claude/skills/
├── uninstall.sh
└── skills/
    ├── parallel-code-review/SKILL.md
    └── parallel-plan-review/SKILL.md
```
