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
<<<<<<< HEAD
| `/onboard-customer-briefing <slug>` | Provision the CEO AI Briefing. **Default: 60-day trial countdown.** Pass `--paid` for paid customers (no trial), or `--trial-days N` to override the default 60. |
=======
| `/onboard-customer-briefing <slug>` | **Paid add-on only** — provision the CEO AI Briefing for a customer who has purchased it. Do NOT run by default. |
| `/validate-customer-metabase <slug>` | **Gate before users get access.** Runs every available Metabase-vs-Sage validator (Balance Sheet, Income Statement / Cash Basis 51-test pytest, AR/AP Aging, `posting_date` filter coverage) within `--tolerance`. Read-only. **Refuses to print a `Next:` pointer if any validator fails** — Mike's hard rule (2026-05-29): "we need to make sure the numbers validate against the Sage reports before we add the users and give them access." |
>>>>>>> origin/feat/validate-customer-metabase
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
<<<<<<< HEAD
5. **Provision the CEO AI Briefing** (default — 60-day trial built in):
   `/onboard-customer-briefing <slug>`
   (pass `--paid` for a customer who has purchased the briefing outright,
   or `--trial-days N` to override the default 60.)
6. **Optional — flip snapshots later:** `/customer-snapshots <slug>`
=======
5. **Validate the Metabase numbers against Sage** (read-only — no writes,
   runs BEFORE any user is added or invited):
   `/validate-customer-metabase <slug> [--reports balance,income,wip,jobcost] [--tolerance 0.01]`
   Runs every available Metabase-vs-Sage validator: Balance Sheet vs Sage
   Excel, Income Statement vs Sage Excel, the `cash-basis-report` 51-test
   pytest suite, AR/AP Aging vs Sage exports, and `posting_date` filter
   coverage. **Hard gate — Mike's rule (2026-05-29):** "we need to make
   sure the numbers validate against the Sage reports before we add the
   users and give them access." If any validator fails, the skill refuses
   to print a `Next:` pointer and exits non-zero. **Do NOT add users until
   validation is green** — fix the underlying dbt/dashboard/Sage mismatch
   first and re-run.
6. **Optional paid add-on — CEO AI Briefing:** `/onboard-customer-briefing <slug>`
   (only if the customer has purchased it — see the "Paid add-on" section below).
7. **Optional — flip snapshots later:** `/customer-snapshots <slug>`
>>>>>>> origin/feat/validate-customer-metabase
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
