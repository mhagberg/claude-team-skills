# claude-team-skills

Shared Claude Code skills for the Xcel Software team. Each skill spawns multiple independent reviewer agents in parallel and consolidates their findings into a single, easy-to-read report.

## Available skills

| Skill | What it does |
|-------|--------------|
| `/parallel-code-review` | 5 independent agents review the current `git diff` (or a PR), each rate 1–10. Consolidated table + recommendations. |
| `/parallel-plan-review` | 5 independent agents review discovered plan files in parallel, each rate 1–10. Consolidated table + recommendations. |
| `/books-audit` | 10 independent agents audit the Xcel + Hagberg Odoo books in parallel — balance integrity, bookkeeping mistakes, tax deductions, tax red flags. Returns a P&L summary + CFO/CTO perspective. Read-only. |

See [`CLAUDE.md`](./CLAUDE.md) for the design spec.

## Install (each teammate runs once)

```bash
git clone git@github.com:mhagberg/claude-team-skills.git ~/claude-team-skills
cd ~/claude-team-skills
./install.sh
```

`install.sh` symlinks each `skills/<name>/` directory into `~/.claude/skills/<name>/`. Because they are symlinks, a `git pull` in `~/claude-team-skills` instantly updates the live skill for every Claude Code session on your machine — no re-install needed.

If a skill of the same name already exists in `~/.claude/skills/`, it is moved aside to `<name>.bak.<timestamp>/` before the symlink is created. Nothing is silently overwritten.

## Uninstall

```bash
cd ~/claude-team-skills
./uninstall.sh
```

Removes the symlinks. Does not touch your `.bak.*` backups.

## Update

```bash
cd ~/claude-team-skills
git pull
```

That's it — symlinks pick up the new content immediately.

## Using a skill

In any Claude Code session, type the slash command, e.g.:

```
/parallel-code-review
/parallel-code-review 1234           # review GitHub PR #1234
/parallel-plan-review
/parallel-plan-review docs/plans/    # only review plans in this path
```

Claude will spawn 5 reviewer agents in parallel, wait for all to return, then print a consolidated table and recommendations.

## Adding a new skill

1. Create `skills/<your-skill>/SKILL.md` with YAML frontmatter:
   ```markdown
   ---
   name: your-skill
   description: One-line summary shown in the skill picker.
   ---

   Instructions to Claude go here in plain prose.
   ```
2. `./install.sh` (idempotent — picks up new skills, leaves existing symlinks alone).
3. Commit and push. Teammates `git pull` and it shows up.

## Repo layout

```
claude-team-skills/
├── README.md              ← you are here
├── CLAUDE.md              ← design spec for AI maintainers
├── install.sh             ← symlinks skills into ~/.claude/skills/
├── uninstall.sh
└── skills/
    ├── parallel-code-review/SKILL.md
    └── parallel-plan-review/SKILL.md
```
