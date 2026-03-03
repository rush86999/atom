#!/usr/bin/env python3
"""
Generate gap analysis from baseline coverage report.

Analyzes coverage gaps and prioritizes files by:
1. Potential coverage gain (uncovered lines)
2. Business impact (core vs. utilities)
3. Test complexity (unit vs. integration needs)

Usage:
    python3 tests/scripts/generate_gap_analysis.py
"""
import json
from pathlib import Path
from datetime import datetime, timezone

# Load baseline coverage
baseline_path = Path("tests/coverage_reports/metrics/phase_127_baseline.json")
with open(baseline_path) as f:
    coverage_data = json.load(f)

# Analyze gaps
gaps = []
for file_path, file_data in coverage_data["files"].items():
    # Filter out test files and non-production code
    if any(x in file_path for x in ["tests/", "test_", "__pycache__", "migrations/"]):
        continue

    pct = file_data["summary"]["percent_covered"]
    total = file_data["summary"]["num_statements"]
    covered = file_data["summary"]["covered_lines"]
    missing = total - covered

    if pct < 80.0:
        # Determine complexity by lines of code
        complexity = "high" if total > 500 else "medium" if total > 200 else "low"

        # Determine business impact by module
        if "core/" in file_path:
            impact = "high" if any(x in file_path for x in ["models", "workflow", "agent", "episode"]) else "medium"
        elif "api/" in file_path:
            impact = "high"
        else:
            impact = "low"

        # Calculate priority score
        priority_score = missing * (3 if impact == "high" else 2 if impact == "medium" else 1)

        gaps.append({
            "file": file_path.replace("backend/", ""),
            "coverage_percent": round(pct, 2),
            "lines_total": total,
            "lines_covered": covered,
            "lines_missing": missing,
            "complexity": complexity,
            "business_impact": impact,
            "priority_score": priority_score,
            "gap_to_target": round(80.0 - pct, 2)
        })

# Sort by priority score (descending)
gaps.sort(key=lambda x: x["priority_score"], reverse=True)

# Calculate overall metrics
total_lines = sum(f["summary"]["num_statements"] for f in coverage_data["files"].values())
total_covered = sum(f["summary"]["covered_lines"] for f in coverage_data["files"].values())
overall_pct = (total_covered / total_lines * 100) if total_lines > 0 else 0

# Generate output
gap_analysis = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "baseline_coverage": round(overall_pct, 2),
    "target_coverage": 80.0,
    "gap_to_target": round(80.0 - overall_pct, 2),
    "files_below_target": len(gaps),
    "total_missing_lines": sum(g["lines_missing"] for g in gaps),
    "estimated_lines_needed": round(sum(g["lines_missing"] for g in gaps) * 0.5),  # Assume 50% efficiency
    "high_impact_files": [g for g in gaps if g["business_impact"] == "high"][:30],
    "medium_impact_files": [g for g in gaps if g["business_impact"] == "medium"][:30],
    "low_impact_files": [g for g in gaps if g["business_impact"] == "low"][:30]
}

# Write output
output_path = Path("tests/coverage_reports/metrics/phase_127_gap_analysis.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w") as f:
    json.dump(gap_analysis, f, indent=2)

print(f"Gap analysis complete: {overall_pct:.2f}% → 80% target")
print(f"Files below 80%: {len(gaps)}")
print(f"Estimated lines needed: {gap_analysis['estimated_lines_needed']}")
print(f"Top 10 high-impact targets:")
for g in gaps[:10]:
    print(f"  {g['file']}: {g['coverage_percent']}% ({g['lines_missing']} missing lines, priority={g['priority_score']})")
