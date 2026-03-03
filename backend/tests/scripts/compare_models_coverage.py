#!/usr/bin/env python3
"""
Compare models.py coverage before and after adding tests.
"""
import json
import sys

# Load baseline (from phase_127_baseline.json)
try:
    with open("tests/coverage_reports/metrics/phase_127_baseline.json") as f:
        baseline = json.load(f)
except FileNotFoundError:
    print("ERROR: Baseline coverage file not found: phase_127_baseline.json")
    print("Run: pytest tests/ --cov=core --cov-report=json:tests/coverage_reports/metrics/phase_127_baseline.json")
    sys.exit(1)

# Load new models coverage
try:
    with open("tests/coverage_reports/metrics/phase_127_models_coverage.json") as f:
        new_coverage = json.load(f)
except FileNotFoundError:
    print("ERROR: New models coverage file not found: phase_127_models_coverage.json")
    sys.exit(1)

# Extract models.py coverage from baseline
# Baseline might use different path formats
baseline_models = baseline["files"].get("backend/core/models.py", {}) or \
                  baseline["files"].get("core/models.py", {})
new_models = new_coverage["files"].get("backend/core/models.py", {}) or \
              new_coverage["files"].get("core/models.py", {})

if not baseline_models:
    print("WARNING: models.py not found in baseline coverage")
    baseline_pct = 0
    baseline_covered = 0
    baseline_total = 0
else:
    baseline_pct = baseline_models.get("summary", {}).get("percent_covered", 0)
    baseline_covered = baseline_models.get("summary", {}).get("covered_lines", 0)
    baseline_total = baseline_models.get("summary", {}).get("num_statements", 0)

if not new_models:
    print("ERROR: models.py not found in new coverage report")
    sys.exit(1)

new_pct = new_models.get("summary", {}).get("percent_covered", 0)
new_covered = new_models.get("summary", {}).get("covered_lines", 0)
new_total = new_models.get("summary", {}).get("num_statements", 0)

improvement = new_pct - baseline_pct
lines_added = new_covered - baseline_covered

result = {
    "file": "core/models.py",
    "baseline_coverage": round(baseline_pct, 2),
    "new_coverage": round(new_pct, 2),
    "improvement": round(improvement, 2),
    "lines_covered_before": baseline_covered,
    "lines_covered_after": new_covered,
    "lines_added": lines_added,
    "total_statements": new_total,
    "missing_lines": new_total - new_covered
}

# Write result
with open("tests/coverage_reports/metrics/phase_127_models_improvement.json", "w") as f:
    json.dump(result, f, indent=2)

# Print summary
print("=" * 60)
print("core/models.py Coverage Improvement")
print("=" * 60)
print(f"Before: {baseline_pct:.2f}% ({baseline_covered}/{baseline_total} lines)")
print(f"After:  {new_pct:.2f}% ({new_covered}/{new_total} lines)")
print(f"Gain:   +{improvement:.2f} percentage points ({lines_added:+d} lines)")
print("=" * 60)
print(f"\nRemaining uncovered lines: {result['missing_lines']}")
print(f"Coverage target: 80% | Current: {new_pct:.2f}% | Status: {'✓ PASS' if new_pct >= 80 else '✗ FAIL'}")
