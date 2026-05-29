# claude-team-skills

Shared Claude Code skills for the Xcel Software team. Each skill spawns multiple independent reviewer agents in parallel and consolidates their findings into a single, easy-to-read report.

## Available skills

| Skill | What it does |
|-------|--------------|
| `/parallel-code-review` | 5 independent agents review the current `git diff` (or a PR), each rate 1–10. Consolidated table + recommendations. |
| `/parallel-plan-review` | 5 independent agents review discovered plan files in parallel, each rate 1–10. Consolidated table + recommendations. |
| `/books-audit` | 10 independent agents audit the Xcel + Hagberg Odoo books in parallel — balance integrity, bookkeeping mistakes, tax deductions, tax red flags. Emits a styled **HTML report** (auto-opens) with a P&L summary, CFO/CTO perspective, and a one-click copy-paste **action item** under each finding to run the fix in Claude Code. Read-only. |
| `/onboard-customer` | Orchestrator — opens the HTML onboarding playbook and routes you to the right sub-skill for your current phase. |
| `/onboard-customer-precall <slug>` | Pre-call staging (~30 min before the IT meeting): NetBird provision, per-customer Sage SQL script, EKS Metabase tenant, draft `profiles.yml` + `single_customers.py` entries. |
| `/onboard-customer-postcall <slug>` | Post-call wiring (~15 min after the call): fill `profiles.yml` with the NetBird IP, push `single_customers.py`, trigger the dbt DAG, add Metabase DB + schema sync, clone the dashboard seed-set. |
| `/onboard-customer-hub <slug>` | Provision the Dashboard Hub: wraps `register_tenant.py` (TENANT_INSTANCES + Firestore + JWT + iframe install). |
| `/onboard-customer-briefing <slug>` | Provision the CEO AI Briefing. **Default: 60-day trial countdown.** Pass `--paid` for paid customers (no trial), or `--trial-days N` to override the default 60. |
| `/configure-customer-metabase <slug>` | **Configure-the-tenant step — runs after `/onboard-customer-hub`, before any validation.** Sets site name, site URL (HTTPS), report timezone (IANA, default `America/Boise`), email From Name + Reply-To, iframe allowlist (`board`, `home`, `ai`, `metagent.app`), custom-homepage-dashboard = `Dashboard Report Menu`, and archives leftover demo users (`Corbin Taylor`, `DataXcel PlayGround User`, `Julie Allen`, `Randy Fullmer`, `playground@xcel.software`, plus anything else not on the keep-allowlist). **The AI agent does all of this automatically using the shared `single.xcel.report` Metabase API key.** Each write requires `yes`. |
| `/validate-hub-dashboards <slug>` | **Gate AFTER `/configure-customer-metabase`, BEFORE `/validate-customer-metabase`.** Health-checks every dashboard the Dashboard Hub will surface — executes every card via the Metabase REST API, reports pass / empty (warn) / failing. Mirrors the production `check_dashboard_health` Cloud Function. Catches Hallowell-style stale-field-id failure modes. Read-only. |
| `/validate-customer-metabase <slug>` | **Gate before users get access.** Runs every available Metabase-vs-Sage validator (Balance Sheet, Income Statement / Cash Basis 51-test pytest, AR/AP Aging, `posting_date` filter coverage) within `--tolerance`. Read-only. Refuses to print a `Next:` pointer if any validator fails — Mike's hard rule (2026-05-29): "we need to make sure the numbers validate against the Sage reports before we add the users and give them access." |
| `/finalize-customer-metabase <slug> --users ...` | **Last step before go-live.** Invites the customer's users (regular + admin). Hard prerequisite: `/configure-customer-metabase`, `/validate-hub-dashboards`, AND `/validate-customer-metabase` must all have passed. This skill no longer touches site URL / timezone / iframe allowlist / demo-user archive — those moved to `/configure-customer-metabase`. Each write requires `yes`. |
| `/install-team-skills` | Idempotent installer/updater — clones repo if missing, pulls latest, runs `./install.sh`, confirms every skill resolves. |
| `/customer-snapshots <slug>` | Flip dbt snapshots on/off for an existing customer in `single_customers.py` (or `rollup_customers.py`). Add `--off` to disable. |

See [`CLAUDE.md`](./CLAUDE.md) for the design spec.

## Onboarding a new DataXcel customer

The canonical sequence, wired to slash commands. Source of truth for the
underlying process is the HTML playbook at
`XcelConnectAndUpdater/docs/new-customer-onboarding.html` — open it with
`/onboard-customer` and follow along.

1. **Pre-call** (Mike, ~30 min before the IT meeting):
   `/onboard-customer-precall <slug> --sql-port <port> --sage-dbs <CompanyA,CompanyB>`
2. **On the call with customer IT** (~30 min): customer IT runs
   `connect-netbird.ps1` and `setup-sage-readonly-<slug>.sql` themselves —
   instructions live in the HTML playbook (and the email template the
   pre-call skill printed for you). Mike captures the NetBird IP the agent
   reports.
3. **Post-call** (Mike/Ty, ~15 min after the call):
   `/onboard-customer-postcall <slug> --netbird-ip <ip>`
4. **Provision the hub** (the default dashboard menu — iframed into their Metabase):
   `/onboard-customer-hub <slug> --company "<name>" --metabase-url https://<slug>.xcel.report --metabase-api-key <key>`
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
9. **Finalize the Metabase tenant** (last step before go-live — invites
   the customer's users). Hard prerequisite: steps 5, 6, and 7 must all
   have passed.
   `/finalize-customer-metabase <slug> --users <email1>,<email2> [--admin-users ...]`
10. **Optional — flip snapshots later:** `/customer-snapshots <slug>`
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
