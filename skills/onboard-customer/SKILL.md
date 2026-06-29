---
name: onboard-customer
description: End-to-end walkthrough — drives every onboarding phase 1-10 in order, confirms before invoking each sub-skill, pipes captured values forward, and ends by registering the customer on the daily status page. Only required arg is `<slug>`. Pass `--from-phase N` to resume mid-flow.
---

# onboard-customer

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer <slug>` becomes `/onboard-customer lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer** orchestrator. Your job is to walk
the operator through the **canonical 10-step onboarding sequence** for one
customer, one phase at a time, in the right order. You are NOT a router or
a menu — you are the conductor. The operator types `/onboard-customer
<slug>` once at the top of the funnel and you drive the entire run.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Mike's choice. Lowercase alnum + dashes only (regex `^[a-z0-9-]+$`). Same slug used in every sub-skill. |
| `--from-phase <N>` | Optional | Resume the walkthrough at phase N (1-10). Default 1. Use when re-running after a fix (e.g. validation failed and you re-ran `/validate-customer-metabase` separately — pass `--from-phase 7` to pick up at "validate Metabase numbers"). |

That is the full surface. Every later value (NetBird IP, SQL port, Sage DB,
`dataxcel` password, Metabase URL, etc.) is captured by the sub-skill at
its own phase and either piped into the next skill's args or read from
`XcelConnectAndUpdater/CLAUDE.md` — never required up front.

**Execution mode:** the orchestrator does not perform writes itself. Each
sub-skill owns its own confirmations for risky steps. The orchestrator's
only job is (a) confirming before invoking each sub-skill (so the operator
can review the args + know what's about to happen), (b) capturing values
the sub-skill printed and feeding them into the next sub-skill, and
(c) pausing between phases that need the operator to step away (on-call,
DNS propagation, etc.).

> **Important harness note for the agent.** Inside Claude Code today, a
> skill body cannot programmatically invoke another slash command — slash
> commands are operator-driven. So at every "invoke sub-skill" point
> below, **print the EXACT next command the operator should type**, with
> all captured values pre-filled, and PAUSE. When the operator returns
> from running it (they paste back stdout, or just type `done`), the
> orchestrator continues to the next phase. If the harness ever exposes a
> programmatic skill-invocation API, this orchestrator becomes the natural
> place to call it — the structure stays identical, only the "PAUSE for
> operator" line changes to "invoke directly."

## Step 1 — validate args + open the playbook

Validate `<slug>` against `^[a-z0-9-]+$`. Reject and stop on mismatch with
a one-line error.

Validate `--from-phase`, if given, against integers 1-10. Reject and stop
on mismatch.

Locate the HTML playbook (source of truth for the prose explanation of
each phase + troubleshooting appendix):

```
PLAYBOOK="/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/docs/new-customer-onboarding.html"
```

- If the file exists → `open "$PLAYBOOK"` (macOS `open`). Tell the operator
  it opened in their browser for reference.
- If it does NOT exist → print the full path and tell the operator to check
  out / merge the `feat/customer-onboarding-playbook` branch of
  `XcelConnectAndUpdater` first. Continue anyway — the walkthrough does
  not require the HTML, it just helps the operator follow along.

Print a one-line plan:

> Onboarding `<slug>` from phase `<N>`. The walkthrough drives all 10
> canonical phases; type `yes` before each one to proceed, or `skip` to
> jump to the next.

## Step 2 — the walkthrough loop

For each phase from `--from-phase` (default 1) through 10, do exactly this:

1. **Announce.** Print the phase number, title, what the sub-skill does in
   one sentence, AND the exact slash command the operator should run next
   (with every value the orchestrator has captured so far pre-filled).
2. **Ask.** Prompt `Type yes to proceed, skip to jump to the next phase,
   or stop to halt.`
3. **Pause.** Wait for the operator. On `stop` → print "Walkthrough halted
   at phase N. Resume with `/onboard-customer <slug> --from-phase N`."
   and stop. On `skip` → move to phase N+1 without invoking. On `yes` →
   tell the operator to run the printed command in a new turn (or in this
   session, depending on harness behaviour), then PAUSE until they type
   `done` and paste back the sub-skill's final "Next:" or summary block.
4. **Capture.** Parse the pasted summary for any values the next phase
   needs (NetBird IP, SQL port, Sage DB, dataxcel password, Metabase URL,
   `database_id`, etc.). Store them in the running state so the next
   announce step can pre-fill them.
5. **Loop.** Move to phase N+1.

Below is the canonical sequence the loop walks through. Source of truth
for the ordering is `claude-team-skills/README.md` § "Onboarding a new
DataXcel customer". If any phase here disagrees with that README, the
README wins — update this orchestrator to match.

### Phase 1 — Pre-call staging (~30 min before the IT meeting)

Sub-skill: `/onboard-customer-precall <slug>` (only `<slug>` required).
Optional: `--company-name "<Display>"`.

What happens: 1Password entry prompt, EKS Metabase tenant clone (with the
session-blocking workaround + ownership transfer), Namecheap CNAME
instructions, draft `profiles.yml` + `single_customers.py` entries with
`<TBD>` placeholders, and NetBird provisioning with a placeholder SQL
port of `1433`. Produces: IT-facing quickstart URL
`https://broker.xcel.report/updates/quickstart-<slug>.html` for the
operator to forward to customer IT.

Pre-fill: `/onboard-customer-precall <slug>` (plus `--company-name` if the
operator gave it via env or earlier prompt).

**Pause between phases 1 and 2** — the operator now schedules / runs the
kickoff call with customer IT and forwards them the quickstart URL. Tell
them: "Run `/onboard-customer-oncall <slug>` once the call starts and IT
is ready to install. Type `done` when you've returned from that skill and
pasted its summary back here."

### Phase 2 — On-call (during the kickoff call, ~30-45 min)

Sub-skill: `/onboard-customer-oncall <slug>`.

What happens: confirms pre-call ran, prints the IT-facing URL, pauses for
IT to install NetBird, captures NetBird IP + real SQL port via
pause-prompts, updates the NetBird policy port (placeholder → real),
renames the peer to `<slug>-sage`, prints the sysadmin-script URL,
captures the `dataxcel` SQL password, lists Sage DBs via `SELECT name
FROM sys.databases` and asks which is live, creates `dataxcel_analytics`,
and writes everything to `XcelConnectAndUpdater/CLAUDE.md`.

**Capture from the operator-pasted summary:** NetBird IP, SQL port, Sage
DB name, `dataxcel` password (the on-call skill prints them in the final
`Next:` line). Store as state for phase 3.

### Phase 3 — Post-call (~15 min after the call)

Sub-skill: `/onboard-customer-postcall <slug>`.

What happens: fills `profiles.yml` with the four call-discovered values
(from CLI flags OR by reading them back from
`XcelConnectAndUpdater/CLAUDE.md`), pushes `single_customers.py`,
triggers the dbt DAG, adds the Metabase DB connection, syncs schema,
clones the dashboard seed-set.

> **2026-06-26 — Airflow migration.** The dbt repo is now
> `JobXcel-AI/airflow_dags` (sibling clone at
> `/Users/mike/dev/projects/airflow_dags`; `sage_dbt` is a submodule of
> it), NOT `etl_pipeline/airflow/…`. DAG triggers go through the Airflow
> REST API at `https://airflow.xcel.software` (the old
> `ssh mike@100.67.235.51 … docker exec` host is decommissioned).
> postcall handles both — this is just context.

Pre-fill: prefer the no-flag form (the postcall skill reads from the
customer table the on-call skill just wrote) — but show both shapes so
the operator can override if a value differs. If state captured from
phase 2 has all four values, pre-fill them as the explicit-flag form:

```
/onboard-customer-postcall <slug> \
  --netbird-ip <IP> \
  --sql-port <PORT> \
  --sage-db "<DB>" \
  --dataxcel-pw '<PW>'
```

**Capture:** the postcall summary prints `database_id` (Metabase DB id)
and the dashboard-clone count. Store `database_id` for phase 8.

### Phase 4 — Provision the Dashboard Hub

Sub-skill: `/onboard-customer-hub <slug>`.

Only `<slug>` required. `--company`, `--metabase-url`, and
`--metabase-api-key` default sensibly.

What happens: appends to `TENANT_INSTANCES`, writes Firestore config,
mints the 10-year JWT, installs the Metabase iframe on the customer's
custom-homepage dashboard.

### Phase 5 — Configure the Metabase tenant

Sub-skill: `/configure-customer-metabase <slug>`.

What happens: sets site name, HTTPS site URL, IANA timezone, email From
Name + Reply-To, iframe allowlist (`board`, `home`, `ai`, `metagent.app`),
custom-homepage-dashboard = `Dashboard Report Menu`, and archives leftover
demo users. Each write requires `yes` inside the sub-skill.

### Phase 6 — Validate every Hub dashboard (read-only — HARD GATE)

Sub-skill: `/validate-hub-dashboards <slug>`.

What happens: executes every card on every non-excluded dashboard via the
Metabase REST API. Reports pass / empty (warn) / failing. Mirrors the
production `check_dashboard_health` Cloud Function.

**Hard gate.** If any card fails, the operator must fix and re-run this
phase before proceeding. The orchestrator pauses and prompts: "Did all
dashboards pass? Type `yes` to continue, `re-run` to redo this phase, or
`stop` to halt." Anything other than `yes` keeps you on this phase.

### Phase 7 — Validate Metabase numbers vs Sage (read-only — HARD GATE)

Sub-skill: `/validate-customer-metabase <slug>`.

What happens: Balance Sheet, Income Statement / Cash Basis 51-test
pytest, AR/AP Aging, `posting_date` filter coverage, all within
`--tolerance` (default 0.01).

**Hard gate.** Mike's rule (2026-05-29): do NOT add users until validation
is green. Same pause-and-confirm pattern as phase 6.

### Phase 8 — Provision the CEO AI Briefing

Sub-skill: `/onboard-customer-briefing <slug>` (default = 60-day trial).

Add `--paid` only if the customer has purchased the briefing outright.

**Always run the first briefing NOW, as part of onboarding** (never defer
it to the Monday DAG), and **always generate it locally in Claude** (the
local-claude two-pass path) so there is zero Anthropic API spend. Mike,
2026-06-10 — the customer's dashboard must show a real briefing the day
they go live.

If state from phase 3 captured `database_id`, mention it — the briefing
sub-skill will prompt for it inside its own step 3, and the operator can
paste it from memory instead of looking it up.

### Phase 9 — Finalize the Metabase tenant (invites the users)

Sub-skill: `/finalize-customer-metabase <slug> --users <email1>,<email2>
[--admin-users <email3>,<email4>]`.

Hard prerequisite — phases 5, 6, and 7 must all have passed in this run.
The sub-skill checks this itself.

The orchestrator should prompt the operator for the user emails before
emitting the command, since this is the one phase whose args the
orchestrator does NOT know automatically. Prompt:

> What user emails should be invited to `<slug>`'s Metabase? Provide a
> comma-separated list of regular users, then a comma-separated list of
> admin users (or `none`).

Pre-fill the captured emails into the command.

### Phase 10 — Register the customer on the daily status page

Sub-skill: `/register-customer-status-page <slug>`.

What happens: appends `<slug>` to `INSTANCES` in
`dataxcel-customer-report/customer_report/registry.py`, validates with
`ast.parse`, commits + pushes a feature branch in
`dataxcel-customer-report`, and triggers the Airflow
`customer_report_dag` so the customer appears in tonight's report at
`https://customers.xcel.report`.

This is the LAST phase of the canonical sequence.

## Step 3 — finish

After phase 10 returns, print a clean wrap-up:

```
Customer <slug> is live.

Next manual actions for the operator:
  - Send the welcome email to the customer. It MUST include the TRAINING
    booking link (Mike's training-appointments calendar — NOT the demo
    link): https://calendar.google.com/calendar/appointments/schedules/AcZssZ0LLF1EDR7vruRc01qe57yzUecIFn2Aj8WCeyP_wq2Pb7NqZhQVJ_DmpnzvNyhSD7Z8hO8hhgOc
    (so they start training right away) and say Mike wants to be on their
    first login to walk them around — never "we'll reach out shortly to
    schedule." (Mike, 2026-06-10.)
  - Confirm tomorrow's customers.xcel.report includes <slug> (the DAG
    runs daily at 13:30 UTC; if you want it sooner, the register skill
    already triggered a one-off run).

Optional follow-ups (run when needed, not part of the canonical sequence):
  - /customer-snapshots <slug>           # flip dbt snapshots on/off later
  - /onboard-customer-briefing <slug> --paid   # upgrade trial → paid
```

Stop. Do not run anything else.

## Notes for the AI agent

- **Resumability.** If the operator runs `/onboard-customer <slug>
  --from-phase 7`, skip directly to phase 7's announce step. Do NOT
  re-emit phases 1-6 even as informational text. The operator already
  knows where they are.
- **Skip semantics.** A `skip` at any phase moves to the next phase WITHOUT
  invoking the sub-skill. This is for the operator who is re-running the
  orchestrator after a partial run and wants to fast-forward past
  already-completed phases. Do NOT confuse `skip` with `stop`.
- **State across phases.** Keep a running state dict in your head (the
  agent's working memory) with at least: `slug`, `netbird_ip`, `sql_port`,
  `sage_db`, `dataxcel_pw`, `metabase_url`, `database_id`, `user_emails`,
  `admin_emails`. Pre-fill these into every subsequent phase's printed
  command.
- **Confirmation discipline.** The orchestrator's own confirmations are
  for "should I print the next command and pause." The sub-skills own
  their own risky-write confirmations. Do not duplicate.
- **One phase at a time.** Never bundle two phases into one prompt. See
  `feedback_one_step_at_a_time.md`.
- **Always end with a "Next:" pointer** even on `stop` or hard-gate fail
  — the operator must know exactly which command to re-run to resume.
