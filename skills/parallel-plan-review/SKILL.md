---
name: parallel-plan-review
description: Spawn 5 independent reviewer agents in parallel over one or more plan/spec markdown files, each with a different lens. Returns a consolidated rating table, rating spread, unanimous concerns, contested calls, and a synthesized recommendation. Use when the user asks for "parallel plan review", "review my plan", or runs /parallel-plan-review.
---

# parallel-plan-review

You are running the **parallel-plan-review** skill. Your job is to spawn 5 independent reviewer agents over a plan (or several plans), then consolidate their findings. Do not review the plan yourself — your role is orchestration and synthesis.

## Step 1 — determine the scope

Look at the user's invocation:

- **No argument** → discover plan files in the current working directory. Search these globs (use `Glob` or `git ls-files | grep`):
  - `PLAN.md`, `plan.md`
  - `plans/*.md`, `**/plans/**/*.md`
  - `ai_docs/plans/**/*.md`
  - `docs/plans/**/*.md`
  - `**/PROJECT_PROCESS.md`
  - Any markdown matching `**/plan*.md` or `**/*-plan.md`
- **Path argument** that is a file → review just that file.
- **Path argument** that is a directory → review every `*.md` inside (non-recursive unless it ends with `/**`).

Print the list of discovered files, one per line, prefixed with `Reviewing:`. **Auto-proceed without confirmation** — do not ask the user to confirm the list. If discovery turns up nothing, stop and tell the user no plan files were found and suggest a path argument.

Read each file (use `Read`). If the combined content exceeds ~80k characters, truncate the largest plans first and tell the reviewers what was truncated. Never silently drop content.

If multiple plans are reviewed together, concatenate them in the reviewer prompt with separators:
```
===== plan: docs/plans/foo.md =====
<contents>
===== plan: ai_docs/plans/bar.md =====
<contents>
```

## Step 2 — spawn 5 reviewers in ONE message

All 5 `Agent` tool-use blocks MUST appear in a **single assistant message**. Sequential calls defeat the purpose. Use `subagent_type: general-purpose` for all five.

Each reviewer gets the same plan payload but a different lens. The prompt template for reviewer N:

```
You are Reviewer {N} of 5, doing an INDEPENDENT plan review. You are NOT
collaborating with the other reviewers — give your honest, focused read.

Your assigned lens: {LENS}
Stay primarily in your lens, but if you spot something egregious outside
it, mention it.

Scope: {one-line scope summary — N plans, total lines, etc.}

Plan(s) to review:
{full plan content, with ===== separators if multiple}

Return your review in EXACTLY this format and nothing else:

RATING: <integer 1-10, where 10 = execute as written, 1 = do not execute>
TOP_ISSUES:
- [SEVERITY] <one-line issue, reference plan filename + section if helpful>
- [SEVERITY] <one-line issue>
- (1 to 5 items total)
SUMMARY: <2-3 sentences explaining your rating>

Severity tags (use exactly these in brackets): [BLOCKER] [MAJOR] [MINOR] [NIT].
Do not write any prose outside this block. Do not preface with "Sure" or
"Here is my review". Start your response with the line "RATING:".
```

The 5 lenses:

| N | Lens | Focus |
|---|------|-------|
| 1 | Goal alignment | Does the plan solve the stated problem? Scope drift, missing requirements, unstated assumptions, success criteria that don't match the goal. |
| 2 | Technical soundness | Architecture choices, library/dependency picks, sequencing, "will this actually work?" risks, conflicts with existing code. |
| 3 | Risk & rollback | What happens when a step fails? Reversibility, blast radius, data loss potential, partial-completion states, side effects on shared systems. |
| 4 | Testability & verification | How will we know each step worked? Measurable success criteria, planned tests, observability, gaps where success is asserted but not checkable. |
| 5 | Effort & decomposition | Is the plan rightsized? Steps too coarse (hide subtasks) or too fine (busywork)? Missing prerequisites? Hidden dependencies between steps? Realistic ordering? |

Set each `Agent` call's `description` to e.g. `Reviewer 1: goal alignment`.

## Step 3 — parse each return

Each reviewer's response should start with `RATING:`. Parse:

- **Rating**: integer 1–10 after `RATING:`. If missing or non-numeric, mark the row `malformed`; exclude from min/median/max.
- **Issues**: lines starting with `- [` until `SUMMARY:`. Extract severity tag and text.
- **Summary**: prose after `SUMMARY:`.

Do not retry malformed reviewers. The other 4 are still signal.

## Step 4 — print the consolidated report

````
## Parallel plan review

**Scope:** {N plans, file list, total lines}
**Reviewers:** 5 independent agents, differentiated lenses.

### Ratings

| # | Lens                 | Rating | Headline issue                          |
|---|----------------------|:------:|------------------------------------------|
| 1 | Goal alignment       |   X    | [SEVERITY] one-line                      |
| 2 | Technical soundness  |   X    | [SEVERITY] one-line                      |
| 3 | Risk & rollback      |   X    | [SEVERITY] one-line                      |
| 4 | Testability          |   X    | [SEVERITY] one-line                      |
| 5 | Effort & decomposition |  X    | [SEVERITY] one-line                      |

**Spread:** min X / median X / max X.

### Unanimous concerns (≥3 reviewers)
- {issue} — flagged by reviewers {list}
(If none: "None — no issue was raised by 3+ reviewers.")

### Contested calls
- {issue}: reviewer A flagged as [SEVERITY], reviewer B said it was fine.
- Rating spread ≥ 3? Show the high/low and one-line WHY each gave that score.
(If none: "None — reviewers were broadly aligned.")

### Recommendation
{2–5 sentences. Order: must-fix BLOCKERs in the plan, then MAJORs that
≥2 reviewers flagged, then notable disagreements. End with one explicit
recommendation: execute-as-written, execute-with-revisions, or rework.}
````

Group issues semantically, not by string match.

## Guardrails

- **Never** spawn the 5 agents in sequential messages. One message, 5 tool-use blocks.
- **Never** insert your own opinions into the table rows — those are the agents' words. The Recommendation section is yours.
- **Never** retry malformed reviewers; note and move on.
- If asked a follow-up question after the review, answer normally — don't re-run the skill.
