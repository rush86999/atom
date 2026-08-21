#!/usr/bin/env bash
# TS gate on changed files (berd gap #4): typecheck only what a branch
# touches, so the legacy ~100 errors can't block while new code can't
# silently add more. Usage: scripts/typecheck-changed.sh [base=origin/main]
set -euo pipefail
BASE="${1:-origin/main}"
FILES=$(git diff --name-only --diff-filter=ACMRT "$BASE" -- '*.ts' '*.tsx' | grep -v __tests__ || true)
if [ -z "$FILES" ]; then echo "No changed TS files."; exit 0; fi
echo "Typechecking ${#FILES[@]} changed files (or their directories)…"
# tsc has no per-file mode with project paths; check the project but only
# fail on errors located in changed files.
npx tsc --noEmit 2>&1 | tee /tmp/tsc-out.txt | grep -F -f <(printf '%s\n' $FILES) && {
  echo "❌ Type errors in changed files (see above)."; exit 1
} || echo "✅ No type errors in changed files."
