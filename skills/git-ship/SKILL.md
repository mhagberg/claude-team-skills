---
name: git-ship
description: Stage all, commit, push, open a PR, auto-merge to main once CI is green, then run the repo's .claude-deploy command. Use when the user runs /git-ship or says "ship this branch".
---

# git-ship

You are running the **git-ship** skill. This is `/git-push-deploy` plus opening a PR and auto-merging to main. The merge is gated on CI; the deploy runs after merge.

## Step 1 — pre-flight

Inherit the **hard-exclude list** from `git-push-deploy`:
- `/odoocker/`, `/odoo-`, repos with `odoo-bin` at root → refuse.
- `*/sage_dbt`, `*/dbt_rollup` → refuse.

Refuse if current branch is `main`/`master` (this skill ships branches *into* main).

Refuse on secret-looking files (same list as `git-push`).

`.claude-deploy` must exist OR the repo must explicitly not need deploy. Convention: if `.claude-deploy` is missing AND the user did not pass `--no-deploy`, stop and ask. With `--no-deploy`, skip the deploy step.

## Step 2 — push the branch

Run the `git-push` flow: stage, conventional commit, push (`-u origin HEAD` if needed).

## Step 3 — open or update PR

```bash
gh pr view --json number,state 2>/dev/null
```

- If a PR exists for this branch and is OPEN, reuse it.
- If no PR exists, create one:
  ```bash
  gh pr create --fill --base <default-branch>
  ```
  Default branch from `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`. If `gh` is unavailable or repo has no GitHub remote, fall back to the **fast-forward path** (Step 3b).

### Step 3b — fast-forward fallback (no GitHub remote)

Only if Step 3 PR creation isn't possible:
```bash
git fetch origin
git checkout main           # or master, whichever is default
git pull --ff-only
git merge --ff-only <branch>
git push
git checkout <branch>       # leave the user where they were
```
If `--ff-only` fails (main moved), stop — never force, never non-FF merge. Tell the user to rebase first.

## Step 4 — auto-merge

If PR mode:
```bash
gh pr merge --squash --auto --delete-branch
```

`--auto` waits for required checks to pass. Poll PR state every 30s up to 15 minutes:
```bash
gh pr view --json state,mergeStateStatus,statusCheckRollup
```

States:
- `MERGED` → continue to Step 5.
- `BLOCKED` (CI failed, conflicts, reviews required) → stop and report. Do not auto-resolve.
- `CLOSED` without merge → stop and report.
- After 15 min still pending → stop, tell the user it's queued and they can check `gh pr view` later.

## Step 5 — deploy from main

After merge:
```bash
git checkout <default-branch>
git pull
```

Read `.claude-deploy`, match `<default-branch>` (e.g. `main:` line), run that command from repo root. If `--no-deploy` was passed, skip with a note.

If deploy fails, stop and report. Do not auto-rollback (that's a separate decision).

## Step 6 — report

- PR: `<url>` (or "fast-forward push, no PR")
- Merged commit: `<sha>` on `<default-branch>`
- Deploy: command + result

## Guardrails

- Hard-exclude list applies.
- Never `--force` push; never `--no-verify`; never `--amend`.
- Never auto-resolve conflicts in the PR. If `gh pr merge --auto` reports `BLOCKED`, halt.
- Never bypass branch protection (`gh pr merge --admin` is forbidden by this skill).
- Default branch is whatever GitHub reports — do not hardcode `main`.
- Auto-merge waits for CI; do not override.
