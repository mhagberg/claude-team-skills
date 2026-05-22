#!/usr/bin/env bash
# Symlink every skill in ./skills/ into ~/.claude/skills/.
# Idempotent: if a target symlink already points at our source, leave it alone.
# Safe: if a target exists but is NOT our symlink, move it aside to <name>.bak.<ts>/.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_DIR/skills"
DEST_DIR="$HOME/.claude/skills"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "error: $SRC_DIR not found" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

shopt -s nullglob
ts="$(date +%Y%m%d-%H%M%S)"
installed=0
skipped=0
backed_up=0

for skill_path in "$SRC_DIR"/*/; do
  skill_name="$(basename "$skill_path")"
  target="$DEST_DIR/$skill_name"
  source_abs="$(cd "$skill_path" && pwd)"

  if [[ -L "$target" ]]; then
    current="$(readlink "$target")"
    if [[ "$current" == "$source_abs" ]]; then
      echo "  ok    $skill_name (already linked)"
      skipped=$((skipped+1))
      continue
    fi
    echo "  relink $skill_name (was -> $current)"
    rm "$target"
  elif [[ -e "$target" ]]; then
    backup="$target.bak.$ts"
    echo "  backup $skill_name -> $(basename "$backup")"
    mv "$target" "$backup"
    backed_up=$((backed_up+1))
  fi

  ln -s "$source_abs" "$target"
  echo "  link   $skill_name"
  installed=$((installed+1))
done

echo
echo "done: $installed installed, $skipped already linked, $backed_up backed up"
echo "skills live at: $DEST_DIR"
