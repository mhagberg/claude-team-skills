---
name: git-ship-all
description: Find every dirty repo (parent + submodules), pre-flight a 5-agent parallel review across the combined diffs, ask for one batched go/no-go, then ship each repo (git-ship flow). Conflicts always halt — no auto-resolve. Use when the user runs /git-ship-all or says "ship everything".
---

# git-ship-all

You are running the **git-ship-all** skill. This is the highest-blast-radius skill in the set: it touches potentially N repos, merges to main on each, and runs deploys. The design is **review-first, ship-second, halt-on-conflict-always**.

## Inputs

- `--fire` flag: skip the human go/no-go prompt. Still halts on conflicts and on any unanimous BLOCKER from the review. Without `--fire`, the skill stops and asks for explicit confirmation before any push/merge/deploy.
- `--dry-run` flag: do discovery and review only; never push, never merge, never deploy. Always honored.

## Step 1 — discover dirty repos

From the current working directory (which should be the parent repo root):

1. Identify the parent repo: `git rev-parse --show-toplevel`.
2. List submodules: `git submodule status --recursive`.
3. For each (parent + every submodule), in parallel where possible:
   - `git -C <path> status --short` — uncommitted changes
   - `git -C <path> rev-parse --abbrev-ref HEAD` — branch
   - `git -C <path> log @{u}..HEAD --oneline 2>/dev/null` — unpushed commits (empty if no upstream)
4. A repo is **dirty** if it has uncommitted changes OR unpushed commits OR is on a feature branch with an open PR.

Apply the **hard-exclude list** from `git-push-deploy`:
- `/odoocker/`, `/odoo-`, repos with `odoo-bin`
- `*/sage_dbt`, `*/dbt_rollup`

Excluded repos are shown in the discovery table with reason "excluded" but never touched.

Print one summary table before doing anything else:

```
| Repo                          | Branch     | Dirty files | Unpushed | Status   |
|-------------------------------|------------|------------:|---------:|----------|
| <parent>                      | feature/x  |          3  |       2  | dirty    |
| dataxcel-board-reports-...    | main       |          0  |       0  | clean    |
| odoo-bank-reconciliation      | feature/y  |          7  |       0  | dirty    |
| odoocker                      | -          |          -  |       -  | excluded |
```

If no repos are dirty, stop with "Nothing to ship."

## Step 2 — gather combined diff

For each dirty repo, capture:
- `git diff` (uncommitted)
- `git diff <default-branch>...HEAD` (committed-on-branch)
- Concatenate per repo with a header: `===== repo: <relative-path> branch=<branch> =====`

Combined diff size cap: ~120k chars for the whole multi-repo bundle. If exceeded, truncate the largest repos first and tell the reviewers what was truncated.

## Step 3 — pre-flight 5-agent parallel review

Use the same pattern as `/parallel-code-review`: spawn 5 `Agent` blocks in a **single assistant message**, `subagent_type: general-purpose`.

Same 5 lenses (Correctness / Security / Error handling / Readability / Testing), same `RATING / TOP_ISSUES / SUMMARY` return contract.

The reviewer prompt must include:
- Brief: "This is a cross-repo ship. You are reviewing N repos at once. In TOP_ISSUES, prefix each line with the repo path so the host can group findings."
- The full combined diff.

## Step 4 — consolidate the review

Print:

```
## /git-ship-all pre-flight review

### Discovery
{table from Step 1}

### Combined ratings (5 reviewers across all dirty repos)

| # | Lens           | Rating | Headline issue                       |
| 1 | Correctness    |   X    | [SEVERITY] <repo>: one-line          |
| ... |

**Spread:** min X / median X / max X.

### Unanimous concerns
- ...

### Per-repo BLOCKERs
| Repo | Reviewer | Issue |
| ... |

### Recommendation
{synthesis, ending in: ship-all / ship-some / do-not-ship}
```

## Step 5 — go/no-go gate

Default behavior (no `--fire`):
- Print the recommendation.
- Ask the user: "Proceed to ship all <N> dirty repos? Type 'yes' to continue, or list repos to exclude."
- Wait for response.

With `--fire`:
- If any reviewer gave a rating ≤ 4 with a [BLOCKER], AND that BLOCKER was raised by ≥ 3 reviewers, halt anyway and tell the user `--fire` was overridden by unanimous-blocker safety.
- Otherwise, proceed without asking.

With `--dry-run`: stop here regardless.

## Step 6 — ship each repo, one at a time

For each non-excluded dirty repo, in declaration order (parent last, since submodule bumps land in parent):

1. `cd <repo>` (or use `git -C <repo>` throughout — do NOT actually `cd`; prefer `-C`).
2. Run the equivalent of the `/git-ship` skill on that repo:
   - Refuse-on-main / refuse-on-secrets / no-amend / no-force — all inherited.
   - Stage, conventional commit, push.
   - Open or reuse PR via `gh pr create --fill --base <default>`.
   - `gh pr merge --squash --auto --delete-branch`.
   - Poll until `MERGED` (max 15 min per repo) or `BLOCKED` (halt the whole run).
   - After merge, checkout default branch, pull, run `.claude-deploy` if present (else skip with a note).
3. **Conflicts halt everything.** If `gh pr merge` reports `BLOCKED` for a conflict, stop the whole run, report which repo halted, leave already-shipped repos as-is. Do not attempt any conflict resolution.
4. After the parent repo's submodule bumps, if the parent repo itself becomes dirty due to the new submodule pointers, run the ship flow on the parent too (one more pass, only the parent).

## Step 7 — final summary

```
## /git-ship-all complete

| Repo | Status | PR | Deploy |
|------|--------|----|--------|
| ...  | merged | #123 | ok   |
| ...  | halted (conflict) | #124 | skipped |
| ...  | excluded | - | - |

Shipped: X / Halted: Y / Excluded: Z
```

If anything halted, end with a clear next-action list.

## Guardrails

- **Conflicts ALWAYS halt.** Never `git merge -X ours/theirs`, never accept-current/accept-incoming. The whole skill exists on the premise that auto-resolution destroys code silently.
- **Hard-exclude list** is non-negotiable. Odoo and dbt-rollup paths are owned by external automation.
- **`--fire` is not "no safety":** unanimous BLOCKERs still halt with `--fire`.
- **One review pass only.** Do not re-review after fixes mid-run — that's the user's job for a separate `/git-ship-all` invocation.
- **No force pushes, no --no-verify, no --amend** across any repo in the run.
- **Parent submodule bumps last.** Always.
- If the user has uncommitted changes on `main`/`master` in any repo, stop and refuse — those need a feature branch first.
