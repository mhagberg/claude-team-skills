---
name: parallel-code-review
description: Spawn 5 independent reviewer agents in parallel over the current diff (or a GitHub PR), each with a different review lens. Returns a consolidated rating table, rating spread, unanimous concerns, contested calls, and a synthesized recommendation. Use when the user asks for "parallel code review", "5 reviewers", or runs /parallel-code-review.
---

# parallel-code-review

You are running the **parallel-code-review** skill. Your job is to spawn 5 independent reviewer agents over the same code change, then consolidate their findings into one report. Do not review the code yourself — your role is orchestration and synthesis.

## Step 1 — determine the scope

Look at the user's invocation:

- **No argument** → review the current branch's working diff. Gather context:
  - `git status --short`
  - `git diff` (uncommitted)
  - `git log --oneline main..HEAD` (committed-on-branch)
  - `git diff main...HEAD` (full branch delta vs main; if `main` doesn't exist, try `master`)
- **Numeric argument** (e.g. `/parallel-code-review 1234`) → `gh pr diff 1234` plus `gh pr view 1234 --json title,body,baseRefName,headRefName,files`
- **Path argument** (e.g. `/parallel-code-review src/foo.py`) → `git diff -- <path>` (uncommitted) or `git diff main...HEAD -- <path>` if there's nothing uncommitted

If the diff is empty, stop and tell the user there's nothing to review.

If the diff exceeds ~80k characters, truncate to the first ~80k and tell the reviewers it was truncated and which files were dropped. Do not silently drop content.

Print a one-line summary of scope before spawning agents, e.g. `Reviewing 7 files / +312 / -88 from current branch vs main.` so the user knows what's being reviewed.

## Step 2 — spawn 5 reviewers in ONE message

This is the most important step. All 5 `Agent` tool-use blocks MUST appear in a **single assistant message**. Sequential calls defeat the purpose of the skill. Use `subagent_type: general-purpose` for all five.

Each reviewer gets the same diff payload but a different lens. Inline the diff into the prompt — agents have no shared filesystem context with you. The prompt template for reviewer N is:

```
You are Reviewer {N} of 5, doing an INDEPENDENT code review. You are NOT
collaborating with the other reviewers — give your honest, focused read.

Your assigned lens: {LENS}
Stay primarily in your lens, but if you spot something egregious outside
it, mention it.

Scope: {one-line scope summary from Step 1}

Diff to review:
```diff
{full diff}
```

{If PR mode, also include: PR title, body, base/head branches.}

Return your review in EXACTLY this format and nothing else:

RATING: <integer 1-10, where 10 = ship it, 1 = do not merge>
TOP_ISSUES:
- [SEVERITY] <one-line issue, include file:line if you can>
- [SEVERITY] <one-line issue>
- (1 to 5 items total; fewer is fine if there's nothing to flag)
SUMMARY: <2-3 sentences explaining your rating>

Severity tags (use exactly these in brackets): [BLOCKER] [MAJOR] [MINOR] [NIT].
Do not write any prose outside this block. Do not preface with "Sure" or
"Here is my review". Start your response with the line "RATING:".
```

The 5 lenses:

| N | Lens | Focus |
|---|------|-------|
| 1 | Correctness & logic | Bugs, off-by-ones, wrong conditions, race conditions, broken invariants, incorrect math/SQL. |
| 2 | Security & input validation | Injection (SQL/shell/XSS), authz/authn, secret leakage, unsafe deserialization, path traversal, untrusted input crossing trust boundaries. |
| 3 | Error handling & edge cases | Unhandled exceptions, swallowed errors, missing null/empty/boundary handling, retry/idempotency, partial failures, resource leaks. |
| 4 | Readability & maintainability | Naming, dead code, unnecessary complexity, premature abstraction, comments that lie, missing comments where the WHY is non-obvious, large functions that should be split. |
| 5 | Testing & verifiability | Missing tests, weak assertions, tests that test the mock, untested branches, hard-to-test code, missing fixtures, flaky patterns. |

Set each `Agent` call's `description` to e.g. `Reviewer 1: correctness` and use a clear prompt as above.

## Step 3 — parse each return

Each reviewer's response should start with `RATING:`. Parse:

- **Rating**: integer 1–10 after `RATING:`. If missing or non-numeric, mark the row `malformed` in the table and use the rating `?` for spread calculations (exclude from min/median/max).
- **Issues**: lines starting with `- [` until `SUMMARY:`. Extract severity tag and text.
- **Summary**: the prose after `SUMMARY:`.

Do NOT retry a malformed reviewer. The other 4 reviews are still signal.

## Step 4 — print the consolidated report

Use this exact structure (markdown, GitHub-flavored):

````
## Parallel code review

**Scope:** {scope line from Step 1}
**Reviewers:** 5 independent agents, differentiated lenses.

### Ratings

| # | Lens                | Rating | Headline issue                          |
|---|---------------------|:------:|------------------------------------------|
| 1 | Correctness         |   X    | [SEVERITY] one-line                      |
| 2 | Security            |   X    | [SEVERITY] one-line                      |
| 3 | Error handling      |   X    | [SEVERITY] one-line                      |
| 4 | Readability         |   X    | [SEVERITY] one-line                      |
| 5 | Testing             |   X    | [SEVERITY] one-line                      |

**Spread:** min X / median X / max X.

### Unanimous concerns (≥3 reviewers)
- {issue} — flagged by reviewers {list}
- ...
(If none, write: "None — no issue was raised by 3+ reviewers.")

### Contested calls
- {issue}: reviewer A flagged as [SEVERITY], reviewer B explicitly rated this fine, etc.
- Rating spread ≥ 3? Note the high/low and one-line WHY each gave that score.
(If none, write: "None — reviewers were broadly aligned.")

### Recommendation
{2–5 sentences. Synthesize, don't average. Order: must-fix BLOCKERs, then
MAJORs that ≥2 reviewers flagged, then notable disagreements worth a human
call. End with one explicit recommendation: ship, ship-with-fixes, or
do-not-ship.}
````

Group issues semantically, not by string match — "uses raw SQL string concatenation" and "SQL injection risk in query builder" are the same concern.

## Guardrails

- **Never** spawn the 5 agents in sequential messages. One message, 5 tool-use blocks.
- **Never** add your own review opinions to the table rows — those rows are the agents' words. The Recommendation section is yours; everything above it is theirs.
- **Never** retry malformed reviewers; note and move on.
- If the user asks a follow-up question, you can answer normally — you do not need to re-run the skill.
- If invoked from a project that uses `git -C <dir>` patterns (e.g. submodule work), still run `git` in the current working directory unless the user explicitly points elsewhere.
