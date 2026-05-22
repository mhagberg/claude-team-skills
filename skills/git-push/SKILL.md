---
name: git-push
description: Stage all changes, write a conventional-commit message based on the diff, commit, and push the current branch (creating upstream if needed). Use when the user runs /git-push or says "commit and push everything".
---

# git-push

You are running the **git-push** skill. Stage all changes, commit with a sensible conventional-commit message, push.

## Step 1 — survey

Run in parallel:
- `git status --short` — what's dirty
- `git diff` — unstaged content
- `git diff --staged` — already-staged content
- `git log --oneline -5` — recent commit message style for this repo
- `git rev-parse --abbrev-ref HEAD` — current branch

If `git status --short` is empty AND no unpushed commits (`git log @{u}..HEAD` shows nothing), stop and tell the user there's nothing to push.

**Refuse to run on `main` or `master`.** If the current branch is `main` or `master`, stop and tell the user to switch to a feature branch first. Direct commits to the trunk are an anti-pattern; this skill exists for feature-branch work.

**Refuse if `.env`, `*.pem`, `*.key`, `credentials.json`, or files matching `*secret*` are in the dirty set.** Tell the user to either remove them, add them to `.gitignore`, or stage manually.

## Step 2 — propose and commit

Write a conventional-commit message:

```
<type>(<scope>): <short description, <72 chars>

<optional body — what changed and why, NOT a diff summary>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `style`, `build`, `ci`. Pick from the actual diff content. If recent commits in the repo use a different convention, follow that instead.

Show the user the proposed message and run `git add -A && git commit` in one step. Use a heredoc to pass the multi-line message:

```bash
git commit -m "$(cat <<'EOF'
<message>
EOF
)"
```

If the commit fails (pre-commit hook), do NOT use `--no-verify`. Fix the underlying issue, re-stage, create a NEW commit. Never amend.

## Step 3 — push

```bash
# If branch has upstream:
git push

# If not:
git push -u origin HEAD
```

Show the push output. If push is rejected (non-fast-forward), stop and tell the user — do not force-push.

## Step 4 — report

One short summary:
- Branch: `<branch>`
- Commit: `<sha> <subject>`
- Remote: `<remote-url>` (link to commit on GitHub if available via `gh`)

## Guardrails

- Never run on `main`/`master`.
- Never `git push --force` or `--force-with-lease` from this skill.
- Never `--amend` an existing commit.
- Never `--no-verify` to skip hooks.
- Never `git add` individual secret-looking files; refuse the whole run instead.
