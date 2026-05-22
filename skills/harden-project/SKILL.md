---
name: harden-project
description: Take an existing project and harden it toward enterprise-ready following the same 7-phase pattern as /new-project — but starts from a repo audit, preserves existing code, produces a gap analysis, and lays the documentation/process scaffold on top of what's already there. Use when the user runs /harden-project or says "harden this codebase".
---

# harden-project

You are running the **harden-project** skill. This is the retrofit counterpart to `/new-project`. The output structure is the same (CLAUDE.md router, README, `docs/`, PROJECT-PLAN.md, ENTERPRISE-STANDARDS.md), but the path to get there starts from an existing repo and respects what's already in it.

**Hard rules for this skill:**
- **Never overwrite existing files without explicit user confirmation.** If `CLAUDE.md`, `README.md`, or any file you would create already exists, show the user a diff and ask before overwriting. Default action is "merge intelligently and write to `<filename>.proposed.md`" so the user reviews before replacing.
- **Never refactor, delete, or move existing code.** This skill produces *documentation, structure, and a hardening plan*. Code changes happen later under the new plan, with normal review.
- **Pause for `continue` between every phase**.

## Phase 0 — audit the existing repo

Target path: the current cwd unless the user names another path.

Run in parallel:
- `git -C <path> rev-parse --is-inside-work-tree` (must be true; if not, refuse)
- `git -C <path> log --oneline -20` — recent activity
- `git -C <path> ls-files | wc -l` — rough size
- `find <path> -maxdepth 2 -type f -name '*.md' | sort` — existing docs
- `find <path> -maxdepth 3 -name 'package.json' -o -name 'pyproject.toml' -o -name 'Cargo.toml' -o -name 'go.mod' -o -name 'pubspec.yaml' -o -name 'Gemfile' -o -name 'requirements.txt'` — language & stack
- `ls -la <path>` for top-level layout
- Check for: `CLAUDE.md`, `README.md`, `LICENSE`, `.github/workflows/*`, `tests/` or `test/`, `Dockerfile`, `.env.example`

Print a one-screen "Audit" summary table:
- Repo path, primary language(s), inferred stack
- Top-level files present / missing (from a checklist of: README, CLAUDE.md, LICENSE, CHANGELOG, CONTRIBUTING, SECURITY, CI workflow, tests, Dockerfile, .env.example, .gitignore)
- Existing docs (list)
- Last 5 commits (subject lines)

Ask the user to confirm this is the right repo and the audit looks correct. Get `continue`.

## Phase 1 — 6-agent hardening brainstorm

Spawn **6 `Agent` blocks in a single assistant message**, `subagent_type: general-purpose`. Each gets:
- The audit summary
- The repo's `README.md` content if present (otherwise: `ls -R | head -100`)
- The repo's `CLAUDE.md` content if present
- A list of all top-level dirs

Each agent has a different lens, biased to existing-code analysis:

| # | Agent | Lens |
|---|-------|------|
| 1 | Tech-debt auditor | Fragile code, missing abstractions, dead code, dependency rot, refactor candidates |
| 2 | Security & secrets | Hardcoded secrets, weak auth, injection surfaces, dependency CVEs, unsafe defaults |
| 3 | Test/quality reviewer | Coverage gaps, brittle tests, no tests, tests-that-test-the-mock, missing fixtures |
| 4 | Docs & onboarding | What's undocumented, tribal knowledge, missing diagrams, stale README, no runbook |
| 5 | Ops & reliability | Deploy fragility, missing observability, no runbooks, no SLO/SLA, manual steps |
| 6 | Enterprise-readiness skeptic | What blocks this in an enterprise procurement / SOC2 review? Licensing, SBOM, audit trail |

Prompt contract (same as /new-project, with one addition — agents must cite file paths or line counts to ground their claims):

```
Return your analysis in EXACTLY this format:

RECOMMENDATIONS:
- <one-line recommendation, cite a path if relevant>
- (3-7 items)
RISKS:
- <one-line risk, cite a path if relevant>
- (2-5 items)
GAPS_VS_ENTERPRISE:
- <one-line gap, mapped to: security | reliability | observability | compliance | docs | quality | ops>
- (2-5 items)
ONE_PARAGRAPH_SUMMARY: <how you'd frame this codebase from your lens>

No prose outside this block. Start with "RECOMMENDATIONS:".
```

After all 6 return, write `docs/audit/<date>-hardening-brainstorm.md` containing the raw 6 outputs, plus a consolidated:
- Cross-cutting recommendations (≥3 agents agreed)
- Critical risks
- Aggregated `GAPS_VS_ENTERPRISE` list grouped by category — this feeds Phase 7 directly.

Show the consolidation. Get `continue`.

## Phase 2 — current vs target requirements

Write or merge:
- `docs/requirements/README.md`
- `docs/requirements/functional.md` — describe what the system *does today* by reading the code at a high level, plus what's *missing* per the audit
- `docs/requirements/non-functional.md` — current observed characteristics (e.g. "no SLO defined", "p99 latency unknown", "single-region") and target characteristics
- `docs/requirements/constraints.md` — anything we discovered (must keep API compatible, can't break X integration, regulatory regime)

If any of these already exist as docs in the repo, merge instead of overwrite — write `<filename>.proposed.md` and show the user a diff against the existing file.

Show summary. Get `continue`.

## Phase 3 — hardening plan

Write `docs/plans/HARDENING-PLAN.md`. Phases are derived from the `GAPS_VS_ENTERPRISE` aggregation in Phase 1:

- **Phase 1 — Safety net** (tests, CI, observability basics — anything that lets us refactor without fear)
- **Phase 2 — Security baseline** (secrets, auth, dependency scanning)
- **Phase 3 — Reliability baseline** (deploy automation, runbooks, alerting)
- **Phase 4 — Documentation completion** (diagrams, ADRs, onboarding)
- **Phase 5 — Enterprise polish** (SOC2-adjacent items, accessibility, compliance docs)
- **Phase 6 — Architecture improvements** (refactors that the safety net now makes safe)

Each phase has entry criteria, exit criteria, and concrete tasks pulled from the brainstorm. Adjust phase ordering to fit the repo — but Phase 1 (Safety net) always comes first.

Show plan outline. Get `continue`.

## Phase 4 — AI dark-factory retrofit design

Write `docs/architecture/ai-dark-factory.md` adapted to the existing codebase:

- Where the spec lives going forward (the new `docs/requirements/*.md`).
- How CLAUDE.md will route AI agents through the existing code.
- The verification loop tuned to what tests/observability exist today and what we're adding in Phase 1 of the hardening plan.
- Explicit human-only gates: deploy, secret rotation, schema migrations, anything else the codebase has been doing manually.
- Anti-patterns observed in current code that the dark-factory pattern should *prevent recurring* (e.g. "secrets in commits", "no tests for X module").

Include a mermaid diagram of the agent + repo + CI loop.

Show file. Get `continue`.

## Phase 5 — CLAUDE.md, README, architecture diagrams

Now produce the documentation scaffold. The trick: existing CLAUDE.md / README may already have content. Strategy:

1. **If `CLAUDE.md` doesn't exist:** create it fresh per the `/new-project` Phase 5 template (≤200 lines, router shape).
2. **If `CLAUDE.md` exists:** write `CLAUDE.md.proposed.md` that merges existing content into the router shape. Show the user a unified diff. **Do not overwrite.** Wait for their decision.
3. **README.md:** same merge-or-create logic. If existing README is good, augment it — add the missing high-level architecture diagram, the "Where to learn more" doc table, and links to new `docs/*` files. Preserve install/run/test sections the user already wrote.
4. **Architecture diagrams** in `docs/architecture/` — generate `system-overview.md`, `components.md`, `data-flow.md`, `deployment.md`, `data-model.md`, `security.md`, `observability.md`, `ai-dark-factory.md` (already from Phase 4). Reverse-engineer the diagrams by reading the code: use `Glob`/`Grep` to find module structure, imports, and entry points. Mark anything you couldn't infer as `TODO: confirm with maintainer` rather than guessing.
5. **`docs/architecture/README.md`** — index.

Verify ≤200 line CLAUDE.md. Verify every `docs/*.md` ends with `← Back to CLAUDE.md`.

Show file tree + CLAUDE.md line count + diff summary for any merged files. Get `continue`.

## Phase 6 — PROJECT-PLAN.md + phases/features/bugs

Same as `/new-project` Phase 6, except:

- Phases come from the hardening plan (Safety net, Security baseline, etc.)
- **Features** initially = gaps from the hardening brainstorm, one feature doc per concrete gap. Each links to the owning phase.
- **Bugs** — populate `docs/plans/bugs/` with one bug file per *known* defect surfaced in the audit (open issues from the issue tracker if `gh` is available: `gh issue list --state open --json number,title,labels`).

Bug doc template includes: severity, repro, expected vs actual, owning phase/feature, status, fix branch/PR, post-mortem (filled when closed).

`PROJECT-PLAN.md` status banner: "Hardening — Phase 1 (Safety net) — Not started".

Show files. Get `continue`.

## Phase 7 — ENTERPRISE-STANDARDS.md (audit-driven)

Same shape as `/new-project` Phase 7, but each checklist item's **initial status comes from the brainstorm's `GAPS_VS_ENTERPRISE` data**, not blank:

- If the audit found CI workflows + branch protection → `Quality > CI gates: in-progress` (with notes on what's there)
- If no secret scanning detected → `Security > Secret scanning: not-started`
- If observability is unknown → `Observability > Metrics: unknown (needs investigation)`
- etc.

Link each item to the phase in `HARDENING-PLAN.md` that will close it.

Show file. Get `continue`.

## Phase 8 — commit scaffold

The scaffold is a documentation overlay — no production code was changed.

Show the user the list of created/modified files. Ask:

1. "Commit the documentation scaffold on a new branch `hardening/scaffold` and open a PR?" (recommended)
2. "Commit directly to current branch?" (only if current branch is not `main`/`master`)
3. "Leave uncommitted for now?"

If PR mode: create branch, commit, push, `gh pr create --fill` with a body summarizing what was added. PR description includes the link to the new HARDENING-PLAN.md so reviewers can see what's coming next.

First commit message:
```
docs: introduce hardening scaffold via /harden-project

7-phase hardening scaffold: 6-agent audit brainstorm, requirements
(current vs target), hardening plan, AI dark-factory retrofit design,
CLAUDE.md + README + docs/ with mermaid diagrams reverse-engineered
from the codebase, PROJECT-PLAN.md with phases/features/bugs tied to
the audit, ENTERPRISE-STANDARDS.md with initial status from the audit.

No production code changed. Refactors and remediation land in the
phases described in HARDENING-PLAN.md.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

## Final report

Tree of created/modified files. List of `.proposed.md` files awaiting user review. CLAUDE.md line count. Next-action recommendation: "Run `/parallel-plan-review docs/plans/HARDENING-PLAN.md` to sanity-check the hardening plan before starting Phase 1 (Safety net)."

## Guardrails

- **Never overwrite an existing file silently.** Merge into a `.proposed.md` and show diff.
- **Never modify production code in this skill.** Only `docs/`, `CLAUDE.md`, `README.md`, `PROJECT-PLAN.md`, `ENTERPRISE-STANDARDS.md`, and a hardening branch.
- **Never invent architecture you can't see.** If you can't infer something from the code, label it `TODO: confirm with maintainer` in the diagram.
- **Always pause for `continue`** between phases.
- **CLAUDE.md ≤ 200 lines.** If existing CLAUDE.md is over 200, the merge proposal should split content into sub-docs.
- **Bidirectional backlinks** required on every `docs/*.md`: `← Back to CLAUDE.md` (and `← Back to <parent index>.md` where applicable).
- If the repo has an open uncommitted-changes state, ask the user to stash or commit first — this skill needs a clean working tree to land scaffold files cleanly.
