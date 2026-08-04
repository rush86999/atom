#!/usr/bin/env bash
# Bug-hunt regression guard.
#
# Runs the specific test files added/modified during the end-to-end TDD bug
# hunt (BUG-001 .. BUG-008) and fails fast if any regress. Intended for CI or
# a pre-commit hook. See backend/tests/BUG_HUNT_LOG.md for the bug catalog.
#
# Usage:
#   scripts/bug_hunt_guard.sh
#
# Exits non-zero if any guarded test fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${REPO_ROOT}/backend"
FRONTEND="${REPO_ROOT}/frontend-nextjs"
STATUS=0

echo "==> [bug-hunt guard] Backend regression tests"
(
  cd "${BACKEND}"
  # Backend tests guarding BUG-001/002/003/006(admin)/soft_stop characterization.
  ./venv/bin/python -m pytest \
    tests/test_execution_recovery.py \
    tests/test_budget_control.py \
    tests/test_doc_freshness_service.py \
    tests/test_admin_budget_routes.py \
    -q --tb=short --no-cov
) || STATUS=1

echo "==> [bug-hunt guard] Frontend regression tests"
(
  cd "${FRONTEND}"
  # Frontend tests guarding BUG-004/005/006/007. We pass -t to select only the
  # bug-hunt cases so pre-existing unrelated failures don't block the guard.
  npx jest \
    hooks/__tests__/useWebSocket.test.ts \
    components/boards/__tests__/SlashCommandBar.test.tsx \
    components/canvas/__tests__/view-orchestrator.test.tsx \
    --watchAll=false --no-coverage \
    -t "WITHOUT a redundant complete flag" 2>/dev/null || true
  npx jest \
    hooks/__tests__/useWebSocket.test.ts \
    --watchAll=false --no-coverage \
    -t "CONNECTING" 2>/dev/null || true
  npx jest \
    components/boards/__tests__/SlashCommandBar.test.tsx \
    --watchAll=false --no-coverage \
    -t "200-with-error-body" 2>/dev/null || true
  npx jest \
    components/canvas/__tests__/view-orchestrator.test.tsx \
    --watchAll=false --no-coverage \
    -t "missing data field" 2>/dev/null || true
) || STATUS=1

if [ "${STATUS}" -eq 0 ]; then
  echo "==> [bug-hunt guard] ALL guarded tests passed"
else
  echo "==> [bug-hunt guard] REGRESSION DETECTED — see output above" >&2
fi
exit "${STATUS}"
