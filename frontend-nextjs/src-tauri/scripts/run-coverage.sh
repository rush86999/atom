#!/bin/bash
# Progressive coverage enforcement for Desktop (Rust/Tauri)
# Phase 153: Coverage Gates & Progressive Rollout
#
# Phases:
# - Phase 1: 40% minimum (baseline enforcement)
# - Phase 2: 45% minimum (interim target)
# - Phase 3: 50% minimum (final target)
#
# Usage:
#   COVERAGE_PHASE=phase_1 bash run-coverage.sh

set -e

# Read phase from environment variable
PHASE=${COVERAGE_PHASE:-phase_1}

# Map phase to fail-under threshold
case $PHASE in
  phase_1)
    FAIL_UNDER=40
    ;;
  phase_2)
    FAIL_UNDER=45
    ;;
  phase_3)
    FAIL_UNDER=50
    ;;
  *)
    echo "ERROR: Invalid COVERAGE_PHASE '$PHASE'. Must be phase_1, phase_2, or phase_3"
    exit 2
    ;;
esac

echo "📊 Desktop Coverage Gate: $PHASE"
echo "   Fail-under threshold: $FAIL_UNDER%"

# Detect new Rust files added in this branch
detect_new_rust_files() {
  git diff --name-only --diff-filter=A origin/main...HEAD | grep '\.rs$' || true
}

# Check for new Rust files
NEW_FILES=$(detect_new_rust_files)
if [ -n "$NEW_FILES" ]; then
  echo "⚠️  New Rust files detected:"
  echo "$NEW_FILES"
  echo ""
  echo "⚠️  New files must have 80% coverage (regardless of phase)"
  echo "Note: Tarpaulin does not support per-file thresholds"
  echo "Manual review required for new files:"
  echo "$NEW_FILES" | while read -r file; do
    echo "  - $file"
  done
  echo ""

  # For now, just warn (tarpaulin limitation)
  # Future: Parse tarpaulin JSON output to check per-file coverage
fi

# Note: cargo-tarpaulin does not support per-file coverage thresholds
# New file enforcement is manual review until tarpaulin adds this feature
# Alternative: Use cargo-llvm-cov (better macOS support but more complex)

# Run tarpaulin with threshold
cargo tarpaulin \
  --out Json \
  --output-dir coverage \
  --fail-under=$FAIL_UNDER \
  --verbose

echo "✅ Desktop coverage passed ($FAIL_UNDER% threshold)"

# Parse coverage.json for new files (experimental)
if [ -f coverage/coverage.json ]; then
  echo "Checking new file coverage from coverage.json..."
  # Future: Implement JSON parsing to extract per-file coverage
  # For now, rely on global threshold enforcement
fi
