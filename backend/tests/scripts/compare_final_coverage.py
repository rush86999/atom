#!/usr/bin/env python3
"""Compare final coverage to baseline for Phase 127."""
import json
from pathlib import Path

# Load baseline
baseline_path = Path("tests/coverage_reports/metrics/phase_127_baseline.json")
with open(baseline_path) as f:
    baseline = json.load(f)

# Load final coverage
final_path = Path("tests/coverage_reports/metrics/phase_127_final_coverage.json")
with open(final_path) as f:
    final = json.load(f)

# Extract overall percentages
baseline_pct = baseline["totals"]["percent_covered"]
final_pct = final["totals"]["percent_covered"]
improvement = final_pct - baseline_pct

# Extract per-module improvements
module_improvements = {}
for file_path in final["files"]:
    # File paths don't have "backend/" prefix in coverage JSON
    baseline_file = baseline["files"].get(file_path, {})
    final_file = final["files"][file_path]

    baseline_module_pct = baseline_file.get("summary", {}).get("percent_covered", 0)
    final_module_pct = final_file.get("summary", {}).get("percent_covered", 0)
    module_improvement = final_module_pct - baseline_module_pct

    if module_improvement > 0:
        module_improvements[file_path] = {
            "baseline": round(baseline_module_pct, 2),
            "final": round(final_module_pct, 2),
            "improvement": round(module_improvement, 2)
        }

# Sort by improvement
sorted_improvements = sorted(
    module_improvements.items(),
    key=lambda x: x[1]["improvement"],
    reverse=True
)

# Generate comparison result
result = {
    "phase": "127",
    "baseline_coverage": round(baseline_pct, 2),
    "final_coverage": round(final_pct, 2),
    "improvement": round(improvement, 2),
    "target_coverage": 80.0,
    "target_met": final_pct >= 80.0,
    "gap_to_target": max(0, round(80.0 - final_pct, 2)),
    "total_files_measured": len(final["files"]),
    "files_improved": len(module_improvements),
    "top_improvements": [
        {"file": k, **v} for k, v in sorted_improvements[:10]
    ]
}

# Write result
output_path = Path("tests/coverage_reports/metrics/phase_127_improvement_summary.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w") as f:
    json.dump(result, f, indent=2)

# Print summary
print(f"\n{'='*60}")
print(f"PHASE 127: BACKEND FINAL COVERAGE")
print(f"{'='*60}")
print(f"Baseline:  {baseline_pct:.2f}%")
print(f"Final:     {final_pct:.2f}%")
print(f"Gain:      {improvement:+.2f} percentage points")
print(f"Target:    80.0%")
print(f"Status:    {'✓ MET' if result['target_met'] else '✗ NOT MET'} ({result['gap_to_target']:.2f} pp gap)")
print(f"\nFiles improved: {len(module_improvements)}")
print(f"\nTop 10 improvements:")
for item in result["top_improvements"]:
    print(f"  {item['file']}: {item['baseline']:.1f}% → {item['final']:.1f}% ({item['improvement']:+.1f} pp)")
print(f"{'='*60}\n")
