#!/usr/bin/env python3
"""
Investigation script for comparing coverage measurements.

Purpose: Understand why coverage.json shows 74.55% while phase_127 shows 26.15%.

Root Cause (discovered): coverage.json only contains 1 file (agent_governance_service.py)
while phase_127 measurements contain 528 files (entire backend production code).

This 48.4 percentage point discrepancy is due to different measurement scopes, not
different methodologies.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(filepath: str) -> dict:
    """Load JSON file with error handling."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {filepath}: {e}")
        return {}


def investigate_coverage_discrepancy():
    """
    Investigate the coverage measurement discrepancy.

    Returns:
        dict: Investigation findings with root cause analysis
    """
    # Define file paths
    backend_dir = Path(__file__).parent.parent.parent
    coverage_json = backend_dir / "tests/coverage_reports/metrics/coverage.json"
    baseline_json = backend_dir / "tests/coverage_reports/metrics/phase_127_baseline.json"
    final_json = backend_dir / "tests/coverage_reports/metrics/phase_127_final_coverage.json"

    # Load all measurements
    measurements = []

    # Load coverage.json (Feb 25 - claimed 74.6% baseline)
    data1 = load_json(str(coverage_json))
    if data1:
        files1 = list(data1.get("files", {}).keys())
        measurements.append({
            "source": "coverage.json",
            "filepath": str(coverage_json),
            "percentage": round(data1["totals"]["percent_covered"], 2),
            "file_count": len(files1),
            "scope": "single file (agent_governance_service.py only)",
            "date": data1["meta"]["timestamp"],
            "files": files1[:5],  # First 5 files for reference
            "total_files_in_measurement": len(files1)
        })

    # Load phase_127_baseline.json (Mar 3 - actual baseline)
    data2 = load_json(str(baseline_json))
    if data2:
        files2 = list(data2.get("files", {}).keys())
        measurements.append({
            "source": "phase_127_baseline.json",
            "filepath": str(baseline_json),
            "percentage": round(data2["totals"]["percent_covered"], 2),
            "file_count": len(files2),
            "scope": "core/, api/, tools/ (full production code)",
            "date": data2["meta"]["timestamp"],
            "files": files2[:5],  # First 5 files for reference
            "total_files_in_measurement": len(files2)
        })

    # Load phase_127_final_coverage.json (Mar 3 - final measurement)
    data3 = load_json(str(final_json))
    if data3:
        files3 = list(data3.get("files", {}).keys())
        measurements.append({
            "source": "phase_127_final_coverage.json",
            "filepath": str(final_json),
            "percentage": round(data3["totals"]["percent_covered"], 2),
            "file_count": len(files3),
            "scope": "core/, api/, tools/ (full production code)",
            "date": data3["meta"]["timestamp"],
            "files": files3[:5],  # First 5 files for reference
            "total_files_in_measurement": len(files3)
        })

    # Calculate discrepancy
    discrepancy = None
    if len(measurements) >= 2:
        coverage_pct = measurements[0]["percentage"]
        baseline_pct = measurements[1]["percentage"]
        discrepancy = {
            "percentage_points": round(coverage_pct - baseline_pct, 2),
            "root_cause": "coverage.json only measures agent_governance_service.py (1 file, 74.55%), "
                        "not the entire backend. Phase 127 measures all 528 production files "
                        "(core/, api/, tools/ directories) at 26.15% actual coverage.",
            "explanation": f"""
The 74.55% in coverage.json is ONLY for agent_governance_service.py (single file).
This is NOT the overall backend coverage.

Phase 127-01 measured the ACTUAL overall backend coverage:
- 528 production files (core/, api/, tools/)
- 26.15% overall coverage
- This is the CORRECT baseline for gap closure planning

ROADMAP incorrectly cited the 74.55% single-file coverage as the overall backend baseline.
The accurate baseline is 26.15%, meaning 53.85 percentage points remain to reach 80% target.
            """.strip(),
            "file_count_difference": measurements[0]["file_count"] - measurements[1]["file_count"]
        }

    # Generate recommendation
    recommendation = {
        "correct_baseline": 26.15,
        "reason": "Phase 127-01 measured all 528 production files (core/, api/, tools/), "
                 "which is the correct scope for overall backend coverage. "
                 "The 74.55% from coverage.json is only for agent_governance_service.py "
                 "(single file), not representative of the entire backend.",
        "roadmap_update_needed": True,
        "action_required": "Update ROADMAP.md Phase 127 goal from '74.6% → 80%' to '26.15% → 80%'",
        "gap_to_target": round(80.0 - 26.15, 2)
    }

    # Compile investigation report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "measurements": measurements,
        "discrepancy": discrepancy,
        "recommendation": recommendation,
        "summary": {
            "finding": "The 74.55% coverage measurement is for a SINGLE file only, "
                      "not the entire backend codebase.",
            "correct_baseline": 26.15,
            "correct_gap": 53.85,
            "measurement_scope": "core/, api/, tools/ directories (production code only)",
            "next_steps": [
                "Update ROADMAP.md with accurate baseline (26.15%)",
                "Document consistent measurement methodology",
                "Use pytest --cov=core --cov=api --cov=tools for all future measurements"
            ]
        }
    }

    return report


def compare_measurement_scopes():
    """
    Compare file inclusion/exclusion across measurements.

    Returns:
        dict: Scope comparison details
    """
    backend_dir = Path(__file__).parent.parent.parent

    # Load measurements
    coverage_data = load_json(str(backend_dir / "tests/coverage_reports/metrics/coverage.json"))
    baseline_data = load_json(str(backend_dir / "tests/coverage_reports/metrics/phase_127_baseline.json"))

    if not coverage_data or not baseline_data:
        return {"error": "Could not load coverage data for comparison"}

    coverage_files = set(coverage_data.get("files", {}).keys())
    baseline_files = set(baseline_data.get("files", {}).keys())

    return {
        "coverage_json_files": len(coverage_files),
        "phase_127_files": len(baseline_files),
        "common_files": len(coverage_files & baseline_files),
        "only_in_coverage_json": list(coverage_files - baseline_files)[:5],
        "only_in_phase_127": list(baseline_files - coverage_files)[:5],
        "conclusion": "coverage.json is a single-file measurement, not representative of overall backend coverage"
    }


def main():
    """Main investigation workflow."""
    print("=" * 80)
    print("COVERAGE MEASUREMENT DISCREPANCY INVESTIGATION")
    print("=" * 80)
    print()

    # Run investigation
    report = investigate_coverage_discrepancy()

    # Print summary
    print("INVESTIGATION SUMMARY:")
    print(f"  Timestamp: {report['timestamp']}")
    print()

    print("MEASUREMENTS FOUND:")
    for m in report['measurements']:
        print(f"  {m['source']}:")
        print(f"    Coverage: {m['percentage']}%")
        print(f"    Files: {m['file_count']}")
        print(f"    Scope: {m['scope']}")
        print(f"    Date: {m['date']}")
        print()

    if report['discrepancy']:
        print("DISCREPANCY ANALYSIS:")
        print(f"  Percentage Points: {report['discrepancy']['percentage_points']} pp")
        print(f"  Root Cause: {report['discrepancy']['root_cause']}")
        print()

    print("RECOMMENDATION:")
    print(f"  Correct Baseline: {report['recommendation']['correct_baseline']}%")
    print(f"  Gap to 80% Target: {report['recommendation']['gap_to_target']} pp")
    print(f"  ROADMAP Update Needed: {report['recommendation']['roadmap_update_needed']}")
    print(f"  Action: {report['recommendation']['action_required']}")
    print()

    # Save report
    output_dir = Path(__file__).parent.parent / "coverage_reports/metrics"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "phase_127_measurement_investigation.json"

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"REPORT SAVED: {output_file}")
    print()
    print("=" * 80)

    # Scope comparison
    print()
    print("SCOPE COMPARISON:")
    scope = compare_measurement_scopes()
    for key, value in scope.items():
        if key != "conclusion":
            print(f"  {key}: {value}")
    print(f"  {scope['conclusion']}")
    print()

    return report


if __name__ == "__main__":
    main()
