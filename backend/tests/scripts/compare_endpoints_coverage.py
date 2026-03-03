"""
Compare atom_agent_endpoints.py coverage before and after new tests.
"""
import json

# Load baseline
with open("tests/coverage_reports/metrics/phase_127_baseline.json") as f:
    baseline = json.load(f)

# Load new endpoints coverage
with open("tests/coverage_reports/metrics/phase_127_endpoints_coverage.json") as f:
    new_coverage = json.load(f)

# Extract atom_agent_endpoints.py coverage
baseline_file = "core/atom_agent_endpoints.py"
baseline_ep = baseline["files"].get(baseline_file, {})
new_ep = new_coverage["files"].get(baseline_file, {})

baseline_pct = baseline_ep.get("summary", {}).get("percent_covered", 0)
new_pct = new_ep.get("summary", {}).get("percent_covered", 0)

improvement = new_pct - baseline_pct

result = {
    "file": "core/atom_agent_endpoints.py",
    "baseline_coverage": baseline_pct,
    "new_coverage": new_pct,
    "improvement": round(improvement, 2),
    "lines_covered_before": baseline_ep.get("summary", {}).get("covered_lines", 0),
    "lines_covered_after": new_ep.get("summary", {}).get("covered_lines", 0),
    "lines_added": new_ep.get("summary", {}).get("covered_lines", 0) - baseline_ep.get("summary", {}).get("covered_lines", 0),
}

# Write result
with open("tests/coverage_reports/metrics/phase_127_endpoints_improvement.json", "w") as f:
    json.dump(result, f, indent=2)

print(f"core/atom_agent_endpoints.py coverage: {baseline_pct:.2f}% → {new_pct:.2f}% ({improvement:+.2f} pp)")
print(f"Lines covered: {result['lines_covered_before']} → {result['lines_covered_after']} ({result['lines_added']:+d})")
