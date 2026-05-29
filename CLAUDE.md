# CLAUDE.md — claude-team-skills design spec

## Purpose

Team-shared Claude Code skills that run **N independent reviewer agents in parallel** and consolidate findings. The first two skills (`parallel-code-review`, `parallel-plan-review`) fix a recurring failure mode: a single reviewer agent gives shallow, confident-sounding feedback that misses real issues. Five independent reviewers force diversity of perspective and surface disagreement.

## Design principles

1. **True parallelism.** All N agent calls go out in a **single assistant message** with multiple `Agent` tool-use blocks. Sequential calls are a bug — they defeat the entire point of the skill.
2. **Independence.** Each agent is told it is one of N independent reviewers and instructed not to consult, harmonize with, or reference others. Each gets identical brief + scope.
3. **Structured return.** Every reviewer must return the same shape (rating, top findings, severity), so the host can table-ize without parsing prose.
4. **Honest consolidation.** The host Claude does not average ratings into a single number — it shows the spread (min/median/max) so disagreement is visible. The recommendations section explicitly calls out where reviewers disagreed.
5. **No silent installs.** `install.sh` never overwrites existing `~/.claude/skills/<name>/` — it backs up first.

## Why symlinks instead of copy

`~/.claude/skills/` is read by every Claude Code session at startup. If we copied files, a `git pull` in the repo wouldn't update Claude until we re-ran install. Symlinks make the repo the live source of truth, which matches the dark-factory principle: one place to edit, propagated everywhere.

Cross-platform note: macOS and Linux handle symlinks natively. Windows users would need `mklink` or WSL; we can add a PowerShell installer later if a teammate needs it.

## Skill anatomy

A SKILL.md is plain markdown with YAML frontmatter:

```markdown
---
name: parallel-code-review
description: 5 independent agents review the diff in parallel; consolidated table + recommendations.
---

# instructions to Claude go here as prose
```

When the user types `/parallel-code-review`, Claude Code loads the SKILL.md body as additional instructions for the current turn. The skill body must be self-contained — Claude will not have read this CLAUDE.md.

## The reviewer prompt contract

Every reviewer agent receives a prompt that ends with:

```
Return your review in EXACTLY this format:

RATING: <integer 1-10>
TOP_ISSUES:
- [severity] <one-line issue>  (repeat 1–5 times)
SUMMARY: <2-3 sentences>

Severity tags: [BLOCKER] [MAJOR] [MINOR] [NIT]. No other prose outside this block.
```

The host parses this with simple line matching. If a reviewer returns malformed output, the host notes "malformed" in the table rather than retrying — a retry would slow the skill and the other 4 reviews are still valid.

## Consolidation output

Both skills print:

1. **Findings table** — one row per reviewer: Reviewer | Rating | Top issue | Severity.
2. **Rating spread** — min / median / max across the 5.
3. **Unanimous concerns** — issues raised by ≥3 reviewers (deduped by Claude semantically, not string match).
4. **Contested calls** — where reviewers disagreed significantly (rating spread ≥ 3, or a finding raised by one but explicitly contradicted by another).
5. **Recommendation** — the host's synthesis: what to fix first, what to investigate, what to ignore.

## Extending

To add a new parallel-N skill (e.g. `/parallel-security-review`):

1. Copy `skills/parallel-code-review/SKILL.md` as a template.
2. Rewrite the reviewer brief for the new domain.
3. Keep the return format identical so the consolidation logic stays uniform.
4. `./install.sh` picks it up automatically.

## Non-goals

- Not a CI tool. These run inside an interactive Claude Code session, not in GitHub Actions.
- Not a replacement for `/ultrareview` (which is a separate Anthropic-hosted multi-agent review). These skills are local, free, and tunable.
- No persistence — each run is independent. If you want history, pipe the output to a file.

## Customer-onboarding skill family

A second family of skills lives alongside the parallel-review skills:
`/onboard-customer`, `/onboard-customer-precall`, `/onboard-customer-postcall`,
`/onboard-customer-briefing`, `/onboard-customer-hub`, `/customer-snapshots`.
These wrap the HTML onboarding playbook at
`XcelConnectAndUpdater/docs/new-customer-onboarding.html` so Mike, Ty, and Stan
can run each onboarding phase as a slash command instead of memorising paths,
flags, and submodule layouts.

These skills follow a different design principle than the parallel-review
ones:

- **No parallel agents.** Onboarding is a linear, side-effecting workflow,
  not an analysis run. Each skill is a single host Claude executing a recipe.
- **Execute with confirmation on risky steps.** Read-only checks and local
  file edits run unprompted. Writes that cross a trust boundary — remote Git
  push, `kubectl apply`, NetBird API mutations, Metabase API writes, Firestore
  writes, dbt DAG triggers — MUST ask the user for an explicit `yes` first
  and show exactly what will run. The threshold is "can I `git checkout --
  .` this back?" If no, confirm.
- **Validate args up front, fail loudly.** Every skill checks its required
  args and any referenced files/scripts before doing work. Missing args are
  prompted for; missing files are a stop-and-tell.
- **End with a "Next:" pointer.** Each sub-skill ends by printing the exact
  slash command for the next phase so the user always knows where they are
  in the canonical sequence (precall → postcall → hub → briefing). The
  briefing is part of the default flow with a 60-day trial countdown built
  in; pass `--paid` to provision without the trial.
- **HTML playbook is the source of truth.** The skills are thin wrappers —
  the playbook owns the prose explanation, troubleshooting appendix, and
  multi-company variant. If a skill and the playbook disagree, the playbook
  wins; update the skill to match.

The "execute with confirmation on risky steps" pattern is the right shape for
*any* future operational skill that mutates production. New parallel-N
analysis skills should still follow the parallel-code-review template.
