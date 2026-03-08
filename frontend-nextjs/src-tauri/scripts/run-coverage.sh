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

# Run tarpaulin with threshold
cargo tarpaulin \
  --out Json \
  --output-dir coverage \
  --fail-under=$FAIL_UNDER \
  --verbose

echo "✅ Desktop coverage passed ($FAIL_UNDER% threshold)"
