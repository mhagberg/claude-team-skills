---
name: new-project
description: Scaffold a brand-new project through a 7-phase workflow — 6-agent brainstorm, requirements, formal plan, AI dark-factory design, CLAUDE.md + README + docs/ structure with mermaid diagrams and bidirectional backlinks, PROJECT-PLAN.md with phases/features/bugs cross-linked, and ENTERPRISE-STANDARDS.md. Use when the user runs /new-project or says "start a new project".
---

# new-project

You are running the **new-project** skill. Walk the user through 7 phases. **Pause for explicit `continue` between every phase** — do not bundle. Each phase produces concrete artifacts; nothing is hypothetical.

## Conventions used throughout

- **CLAUDE.md is the router**, under 200 lines, links out to `docs/*.md`. Never inline content that belongs in a sub-doc.
- **README.md is the human entry point**, contains the high-level architecture diagram (mermaid) and links to every other design doc.
- **Every `docs/*.md` ends with a `← Back to CLAUDE.md` line**. Bidirectional backlinks are non-negotiable.
- **Diagrams are mermaid** (text-based, GitHub-rendered, AI-maintainable). If the user prefers draw.io or excalidraw, swap them out — but default to mermaid.
- **One file per concept.** Phases, features, bugs each get their own file. Indexes (`README.md` per directory) link to all children.

## Phase 0 — seed

Ask the user, one question at a time:

1. **Project name** (used to create slug — kebab-case, ASCII).
2. **Where to create it.** Default: `./<slug>` in current cwd. Offer override.
3. **One-paragraph concept** — what is this thing, who's it for, what's the win? (3–6 sentences is fine.)
4. **Tech stack hints?** (e.g. "Flutter app", "Python CLI", "TanStack Start"). Optional — agents will recommend if absent.
5. **Confirm before continuing.** Show back the slug, path, concept, stack hint. Get `continue`.

Create the directory. Initialize an empty git repo: `git -C <path> init -b main`. Do not commit yet — files come in later phases.

## Phase 1 — 6-agent brainstorm

Spawn **6 `Agent` blocks in a single assistant message**. `subagent_type: general-purpose` for all. Each gets the seed concept + stack hint, and a different lens:

| # | Agent | Lens |
|---|-------|------|
| 1 | Product strategist | User value, market fit, what to NOT build, monetization if relevant |
| 2 | Software architect | System shape, boundaries, tech stack rationale, integration points |
| 3 | UX / human factors | Friction points, accessibility, what users actually do vs say |
| 4 | Security & compliance | Threat model, data protection, regulatory exposure |
| 5 | Operations / SRE | Deploy, monitor, scaling, on-call burden, cost shape |
| 6 | Red team / skeptic | What kills this, why it won't work, dumb-question critique |

Each agent's prompt ends with this strict return contract:

```
Return your analysis in EXACTLY this format:

RECOMMENDATIONS:
- <one-line concrete recommendation>
- (3-7 items)
RISKS:
- <one-line risk>
- (2-5 items)
OPEN_QUESTIONS:
- <one-line question to surface to the user>
- (1-3 items)
ONE_PARAGRAPH_SUMMARY: <how you'd frame this project in your domain>

No prose outside this block. Start with "RECOMMENDATIONS:".
```

After all 6 return, write `docs/brainstorm/<slug>-brainstorm.md` containing the raw 6 outputs verbatim with section headers, plus a consolidated:
- Cross-cutting recommendations (≥3 agents agreed)
- Critical risks (any [BLOCKER]-level or red-team flag)
- Outstanding questions for the user

Show the consolidation. Get `continue`.

## Phase 2 — requirements & spec

Using the brainstorm + the user's answers to the open questions, write:

- `docs/requirements/README.md` — index
- `docs/requirements/functional.md` — what the system does (user stories, capabilities)
- `docs/requirements/non-functional.md` — performance, availability, latency, scale, browser/device support
- `docs/requirements/constraints.md` — regulatory, budget, deadline, must-integrate-with, must-not-do

Every file ends with `← Back to CLAUDE.md`. Each links to its siblings.

Show the user a summary table of requirements. Get `continue`.

## Phase 3 — formal plan

Write `docs/plans/PLAN.md` — the master plan. Structured as:

- **Goal** (one paragraph from the seed)
- **Constraints** (from requirements)
- **Phases** — 3–6 phases, each a one-line description; full per-phase docs come in Phase 6
- **Out of scope** — explicit list of what this plan does NOT cover
- **Open decisions** — bullet list with each decision Claude or the user owes the project before execution

Use the `act-workflow-spec` and `act-workflow-plan` skills if available for spec/plan deepening — but do not require them.

Show the plan outline. Get `continue`.

## Phase 4 — AI dark-factory design

Write `docs/architecture/ai-dark-factory.md` — how the app's source of truth lives in markdown/code that AI agents maintain. Include a mermaid diagram of the loop. Cover:

- Where the spec lives (e.g. `docs/requirements/*.md` + `CLAUDE.md`).
- How the AI agent reads it (CLAUDE.md as router, agent loads only what it needs).
- Where agent changes land (PR-based; commits trace back to spec docs).
- The verification loop: tests, screenshots, observability — how does the agent know it succeeded?
- Human review points: what does a human always sign off on?
- Anti-patterns: what's explicitly NOT delegated to AI (e.g. deploy, secret rotation, schema migration approval — pick what fits the project).

Show the file. Get `continue`.

## Phase 5 — CLAUDE.md, README, architecture diagrams

Create the top-level scaffold:

1. **`CLAUDE.md`** (target ≤200 lines):
   - One-sentence project description.
   - Link to README, PROJECT-PLAN.md, ENTERPRISE-STANDARDS.md.
   - A **module table** listing every directory and the doc to read when working there.
   - A **detailed docs table** listing every `docs/**/*.md` with a one-line "read when..." hook (same pattern as the parent `CLAUDE.md` in odoo_bank_metabase_payroll_reporting).
   - **Conventions** section (code style, testing, naming, branching). Short.
   - **Do NOT** inline architecture text. Always link out.

2. **`README.md`** (human entry):
   - Project pitch (2–4 sentences).
   - **High-level architecture** mermaid diagram (system context).
   - Install / run / test in fenced code blocks.
   - "Where to learn more" table linking to every doc.

3. **Architecture diagrams** — one mermaid diagram per concern, each in its own file under `docs/architecture/`:
   - `system-overview.md` — C4-style context (users, external systems, this system)
   - `components.md` — internal components / modules and how they call each other
   - `data-flow.md` — request/response or event flow for the main use case
   - `deployment.md` — where this runs (hosting, regions, CI/CD)
   - `data-model.md` — entity-relationship diagram of core data
   - `security.md` — auth, authz, secrets management, trust boundaries
   - `observability.md` — logs, metrics, traces, alerts
   - `ai-dark-factory.md` — already written in Phase 4; cross-link here

   Each diagram file: short prose intro (≤20 lines), the mermaid block, then "Related: …" links to siblings, then `← Back to CLAUDE.md`.

4. **`docs/architecture/README.md`** — index of all architecture docs, links to each.

Verify: CLAUDE.md line count is ≤200. If over, split content into a new `docs/*.md` and link to it. Verify every `docs/*.md` ends with `← Back to CLAUDE.md`.

Show the file tree and CLAUDE.md line count. Get `continue`.

## Phase 6 — PROJECT-PLAN.md + phases/features/bugs

Create the work-tracking scaffold:

1. **`PROJECT-PLAN.md`** — links to:
   - `docs/plans/phases/README.md` (phases index)
   - `docs/plans/features/README.md` (features index)
   - `docs/plans/bugs/README.md` (bugs index)
   - Current status banner (which phase is active)
   - Last updated date

2. **`docs/plans/phases/README.md`** — table of all phases with status (planned/in-progress/done) linking to each phase doc.

3. **`docs/plans/phases/phase-N-<slug>.md`** for each phase from Phase 3, containing:
   - Goal
   - Entry criteria / prerequisites
   - Exit criteria (measurable)
   - Linked features (relative paths)
   - Linked bugs (relative paths)
   - Status + dates
   - `← Back to PROJECT-PLAN.md` and `← Back to CLAUDE.md`

4. **`docs/plans/features/README.md`** — table of all features, status, owning phase.

5. **`docs/plans/features/<feature-slug>.md`** for each feature identified in brainstorm/requirements:
   - One-line description
   - Acceptance criteria (bulleted, testable)
   - Owning phase (link)
   - Implementation notes (initially empty; AI agents fill this)
   - `← Back to features index` and `← Back to CLAUDE.md`

6. **`docs/plans/bugs/README.md`** — empty bugs index for now. Add the template comment block at top so future bug docs are consistent.

7. **`docs/plans/bugs/_template.md`** — template for new bug docs (severity, repro, expected, actual, link to phase/feature, fix branch/PR, post-mortem).

Show the new files. Get `continue`.

## Phase 7 — ENTERPRISE-STANDARDS.md

Write `ENTERPRISE-STANDARDS.md` at repo root. Sections (each is a checklist):

- **Security:** SSO/SAML readiness, secret management, dependency scanning, threat model on file, pen test plan.
- **Compliance:** Data classification, GDPR/CCPA, retention, DPIA needed?, regulatory body if any.
- **Reliability:** SLO defined, error budget, monitoring + alerting, runbooks, on-call rotation, disaster recovery RTO/RPO.
- **Observability:** Structured logs, metrics, traces, dashboard, log retention policy.
- **Operations:** Deploy automation, rollback procedure, infra as code, environment parity (dev/staging/prod).
- **Quality:** Test coverage target, CI gates, code review policy, branch protection, license scan.
- **Documentation:** Onboarding doc, architecture diagrams (already done — link), runbook for every alert, post-mortem template.
- **Accessibility:** WCAG level target if user-facing, audit cadence.
- **Vendor/Procurement:** SOC2 status, SLA, data residency, sub-processor list.

For each item, status is `not-started` / `in-progress` / `done` / `not-applicable (reason)`. Initial state: mostly `not-started`. Link to the relevant `docs/architecture/security.md`, `observability.md`, etc.

End with `← Back to CLAUDE.md`.

Show the file. Get `continue`.

## Phase 8 — first commit + optional GitHub push

Ask: "Push this to GitHub now?"

- **Yes** → `gh repo create <user>/<slug> --private --source=<path> --remote=origin --push` (ask private vs public). Then ask: "Add as submodule of the current parent repo?" If yes, run `git submodule add <url> <slug>` from the parent.
- **No** → leave it as a local repo. Tell the user the manual command for later.

First commit message:
```
chore: scaffold project via /new-project

7-phase initial scaffold: 6-agent brainstorm, requirements, formal
plan, AI dark-factory design, CLAUDE.md + README + docs/ with mermaid
diagrams, PROJECT-PLAN.md with phases/features/bugs cross-linked,
ENTERPRISE-STANDARDS.md.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

## Final report

Print a tree of what was created (use `find <path> -type f -name '*.md' | sort`), the CLAUDE.md line count, the GitHub URL (if pushed), and one-line "next action": "Run `/parallel-plan-review` on `docs/plans/PLAN.md` to sanity-check the plan before starting Phase 1."

## Guardrails

- **Always pause for `continue` between phases.** Bundling defeats the user's "one step at a time" preference.
- **Never** overwrite an existing CLAUDE.md or README.md in the target path. If they exist, stop and tell the user to use `/harden-project` instead.
- **Never** inline content into CLAUDE.md that belongs in a sub-doc. Keep it ≤200 lines.
- **Never** create a doc without the `← Back to CLAUDE.md` footer.
- **Never** create a phase/feature/bug doc without bidirectional links to the index and to its parent phase.
- If the user pushes back on the 6-agent brainstorm shape (wants different lenses, fewer agents, etc.), accept and adapt — the structure of phases 2–8 doesn't depend on the exact brainstorm shape.
- This skill is for greenfield. If `git rev-parse --is-inside-work-tree` returns true in the target path AND there's already a CLAUDE.md, refuse and recommend `/harden-project`.
