---
name: git-push-deploy
description: Stage all, commit, push the current branch, then run the repo's deploy command from .claude-deploy. Use when the user runs /git-push-deploy or wants to ship a branch deploy (Firebase preview, staging, etc.) without merging to main.
---

# git-push-deploy

You are running the **git-push-deploy** skill. This is `/git-push` plus running the repo's deploy command. It does NOT merge to main — use `/git-ship` for that.

## Step 1 — pre-flight safety

**Hard-exclude list.** Refuse to run if the current working directory is inside any of:

- Any path containing `/odoocker/`, `/odoo-`, or that has an `odoo-bin` file at the repo root — the Odoo deploy pipeline (odoocker → ECR → EKS) is owned by external automation; do not interfere.
- Any path matching `*/sage_dbt` or `*/dbt_rollup` — these have their own rollup-DAG ops that must be triggered separately; do not auto-deploy.

If excluded, stop and tell the user which exclusion rule matched and what to do instead (e.g. "use the upstream pipeline" or "trigger the Airflow rollup DAGs").

## Step 2 — check for deploy config

Look for `.claude-deploy` at the repo root (find with `git rev-parse --show-toplevel`).

The file format is a single shell command per non-blank, non-comment line, executed in repo root with shell, the first matching for the current branch:

```
# .claude-deploy
# Lines: <branch-pattern>: <command>
# Branch pattern is a glob; * matches anything; first match wins.
main: bun run deploy:prod
preview/*: bun run deploy:preview
*: bun run deploy:branch
```

If `.claude-deploy` is missing, stop **before pushing** and tell the user:
- "No `.claude-deploy` in this repo. Either create one (see format above) or use `/git-push` for push-only."

This is intentional: pushing without a known deploy is fine via `/git-push`; this skill is specifically the "push + deploy" combo.

## Step 3 — run the git-push flow

Do everything from the `git-push` skill: survey, refuse-on-main, refuse-on-secrets, conventional commit, push. If any of those steps stop, stop the deploy too.

## Step 4 — deploy

After the push succeeds:
1. Re-read `.claude-deploy`, match the current branch to the first matching pattern, get the command.
2. Show the user the command you're about to run.
3. Run it from the repo root. Stream output.
4. If exit code is non-zero, stop and report the failure clearly. Do NOT retry automatically.

## Step 5 — report

- Branch / commit / push (from Step 3)
- Deploy command: `<cmd>`
- Deploy result: success / failure (with stderr summary if failed)

## Guardrails

- Hard-exclude list is non-negotiable. Do not run deploy in Odoo / dbt-rollup paths.
- No `.claude-deploy` = no deploy. Do not guess.
- Do not retry a failed deploy. Tell the user.
- Inherit all `git-push` guardrails (no main, no force, no amend, no --no-verify, no secrets).
