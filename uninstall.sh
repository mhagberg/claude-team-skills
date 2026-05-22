#!/usr/bin/env bash
# Remove symlinks in ~/.claude/skills/ that point into this repo.
# Leaves .bak.* backups untouched.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_DIR/skills"
DEST_DIR="$HOME/.claude/skills"

if [[ ! -d "$DEST_DIR" ]]; then
  echo "nothing to do: $DEST_DIR does not exist"
  exit 0
fi

shopt -s nullglob
removed=0

for link in "$DEST_DIR"/*; do
  [[ -L "$link" ]] || continue
  target="$(readlink "$link")"
  case "$target" in
    "$SRC_DIR"/*)
      echo "  remove $(basename "$link")"
      rm "$link"
      removed=$((removed+1))
      ;;
  esac
done

echo
echo "done: $removed symlink(s) removed"
echo "(any *.bak.* directories were left untouched)"
