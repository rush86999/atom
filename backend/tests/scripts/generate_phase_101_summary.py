#!/usr/bin/env python3
"""
Generate Phase 101 Coverage Summary

Generates comprehensive coverage summary for Phase 101 target services:
- agent_governance_service.py
- episode_segmentation_service.py
- episode_retrieval_service.py
- episode_lifecycle_service.py
- canvas_tool.py
- agent_guidance_canvas_tool.py

Output: backend/tests/coverage_reports/metrics/phase_101_coverage_summary.json
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Target services for Phase 101
TARGET_SERVICES = [
    "backend/core/agent_governance_service.py",
    "backend/core/episode_segmentation_service.py",
    "backend/core/episode_retrieval_service.py",
    "backend/core/episode_lifecycle_service.py",
    "backend/tools/canvas_tool.py",
    "backend/tools/agent_guidance_canvas_tool.py",
]

# Baseline coverage from coverage_baseline.json
BASELINE_COVERAGE = {
    "backend/core/agent_governance_service.py": 20.0,
    "backend/core/episode_segmentation_service.py": 8.25,
    "backend/core/episode_retrieval_service.py": 9.03,
    "backend/core/episode_lifecycle_service.py": 0.0,  # Not in baseline, assuming 0%
    "backend/tools/canvas_tool.py": 3.8,
    "backend/tools/agent_guidance_canvas_tool.py": 0.0,  # Not in baseline, assuming 0%
}


def run_coverage() -> Dict[str, Any]:
    """Run pytest with coverage and return JSON output."""
    print("Running coverage analysis for Phase 101 target services...")

    cmd = [
        sys.executable, "-m", "pytest",
        "backend/tests/unit/governance/",
        "backend/tests/unit/episodes/",
        "backend/tests/unit/canvas/",
        "backend/tests/property_tests/governance/",
        "backend/tests/property_tests/episodes/",
        "-v",
        "--cov=backend/core/agent_governance_service",
        "--cov=backend/core/episode_segmentation_service",
        "--cov=backend/core/episode_retrieval_service",
        "--cov=backend/core/episode_lifecycle_service",
        "--cov=backend/tools/canvas_tool",
        "--cov=backend/tools/agent_guidance_canvas_tool",
        "--cov-report=term-missing",
        "--cov-report=json:",
        "--cov-report=term-missing:skip-covered",
    ]

    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)

    # Load coverage.json
    coverage_file = Path(__file__).parent.parent.parent / "coverage.json"
    if not coverage_file.exists():
        print(f"ERROR: coverage.json not found at {coverage_file}", file=sys.stderr)
        return {}

    with open(coverage_file) as f:
        coverage_data = json.load(f)

    return coverage_data


def extract_service_metrics(coverage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract coverage metrics for each target service."""
    services = []

    for service_path in TARGET_SERVICES:
        # Normalize path for coverage.json lookup
        normalized_path = service_path.replace("backend/", "")

        # Find coverage data
        files = coverage_data.get("files", {})
        coverage_info = None

        # Try exact match first
        if normalized_path in files:
            coverage_info = files[normalized_path]
        else:
            # Try finding by partial match
            for file_path, file_data in files.items():
                if service_path.split("/")[-1] in file_path:
                    coverage_info = file_data
                    normalized_path = file_path
                    break

        if not coverage_info:
            print(f"WARNING: No coverage data found for {service_path}", file=sys.stderr)
            continue

        summary = coverage_info.get("summary", {})
        total_lines = summary.get("num_statements", 0)
        covered_lines = summary.get("covered_lines", 0)
        coverage_pct = summary.get("percent_covered", 0.0)

        # Get baseline coverage
        baseline_pct = BASELINE_COVERAGE.get(service_path, 0.0)

        # Calculate baseline covered lines estimate
        baseline_covered = int(total_lines * baseline_pct / 100)

        # Estimate tests added (rough estimate based on coverage improvement)
        # Assume each test covers ~20 lines on average
        new_lines_covered = covered_lines - baseline_covered
        tests_added = max(0, round(new_lines_covered / 20))

        services.append({
            "file": service_path,
            "coverage_pct_before": round(baseline_pct, 2),
            "coverage_pct_after": round(coverage_pct, 2),
            "covered_lines_before": baseline_covered,
            "covered_lines_after": covered_lines,
            "total_lines": total_lines,
            "threshold_met": coverage_pct >= 60.0,
            "tests_added": tests_added,
            "delta_pct": round(coverage_pct - baseline_pct, 2),
        })

    return services


def generate_summary(services: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate overall summary metrics."""
    total_services = len(services)
    services_meeting_threshold = sum(1 for s in services if s["threshold_met"])

    # Calculate overall coverage (weighted by lines of code)
    total_lines = sum(s["total_lines"] for s in services)
    total_covered = sum(s["covered_lines_after"] for s in services)
    overall_coverage = round((total_covered / total_lines * 100) if total_lines > 0 else 0, 2)

    # Calculate baseline overall coverage
    total_covered_before = sum(s["covered_lines_before"] for s in services)
    baseline_coverage = round((total_covered_before / total_lines * 100) if total_lines > 0 else 0, 2)

    # Total tests added (sum of estimates)
    total_tests_added = sum(s["tests_added"] for s in services)

    return {
        "total_services": total_services,
        "services_meeting_threshold": services_meeting_threshold,
        "overall_coverage_pct_before": baseline_coverage,
        "overall_coverage_pct_after": overall_coverage,
        "threshold_met": services_meeting_threshold == total_services,
        "tests_added": total_tests_added,
        "delta_pct": round(overall_coverage - baseline_coverage, 2),
    }


def main():
    """Main execution."""
    print("=" * 80)
    print("Phase 101 Coverage Summary Generator")
    print("=" * 80)

    # Run coverage analysis
    coverage_data = run_coverage()

    if not coverage_data:
        print("ERROR: Failed to generate coverage data", file=sys.stderr)
        sys.exit(1)

    # Extract metrics for each service
    services = extract_service_metrics(coverage_data)

    if not services:
        print("ERROR: No service metrics extracted", file=sys.stderr)
        sys.exit(1)

    # Generate summary
    summary = generate_summary(services)

    # Build final JSON structure
    output = {
        "phase": "101",
        "generated_at": datetime.utcnow().isoformat() + "+00:00Z",
        "baseline_version": "v5.0",
        "target_threshold": 60.0,
        "summary": summary,
        "services": services,
    }

    # Write output file
    output_dir = Path(__file__).parent.parent / "coverage_reports" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "phase_101_coverage_summary.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 80)
    print("Phase 101 Coverage Summary")
    print("=" * 80)
    print(f"Total Services: {summary['total_services']}")
    print(f"Services Meeting 60% Threshold: {summary['services_meeting_threshold']}")
    print(f"Overall Coverage (Before): {summary['overall_coverage_pct_before']}%")
    print(f"Overall Coverage (After): {summary['overall_coverage_pct_after']}%")
    print(f"Delta: +{summary['delta_pct']}%")
    print(f"Threshold Met: {summary['threshold_met']}")
    print(f"Estimated Tests Added: {summary['tests_added']}")
    print(f"\nOutput written to: {output_file}")
    print("=" * 80)

    # Print individual service breakdown
    print("\nIndividual Service Breakdown:")
    print("-" * 80)
    for service in services:
        status = "✓ PASS" if service["threshold_met"] else "✗ FAIL"
        print(f"{status} | {service['file']}")
        print(f"       Before: {service['coverage_pct_before']}% → After: {service['coverage_pct_after']}% (Delta: +{service['delta_pct']}%)")
        print(f"       Lines: {service['covered_lines_after']}/{service['total_lines']} ({service['coverage_pct_after']}%)")
        print(f"       Tests Added: ~{service['tests_added']}")

    # Exit with error if threshold not met
    if not summary["threshold_met"]:
        print("\nERROR: Not all services meet 60% threshold", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
