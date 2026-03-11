#!/usr/bin/env python3
"""
Coverage measurement script for Phase 165: Core Services Coverage (Governance & LLM)

Measures actual line coverage (not service-level estimates) for:
- agent_governance_service.py (770 lines)
- byok_handler.py (1556 lines)
- cognitive_tier_system.py

Target: 80%+ line coverage with branch coverage enabled
"""
import subprocess
import json
import sys
from pathlib import Path

# Coverage targets
TARGET_LINE_COVERAGE = 80.0

# Services under test
SERVICES = [
    "core.agent_governance_service",
    "core.llm.byok_handler",
    "core.llm.cognitive_tier_system",
]

# Test files
TEST_FILES = [
    "tests/integration/services/test_governance_coverage.py",
    "tests/unit/services/test_agent_governance_service.py",
    "tests/integration/services/test_llm_coverage_governance_llm.py",
    "tests/unit/llm/test_byok_handler.py",
    "tests/unit/llm/test_cognitive_tier_classifier.py",
    "tests/property_tests/governance/test_governance_invariants_extended.py",
    "tests/property_tests/governance/test_governance_cache_consistency.py",
    "tests/property_tests/llm/test_cognitive_tier_invariants.py",
]


def run_coverage_measurement():
    """Run pytest with coverage and generate report."""
    cmd = [
        "pytest",
        *TEST_FILES,
        "--cov", "core.agent_governance_service",
        "--cov", "core.llm.byok_handler",
        "--cov", "core.llm.cognitive_tier_system",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=html:tests/coverage_reports/html",
        "--cov-report=json:tests/coverage_reports/metrics/backend_phase_165_governance_llm.json",
        "-v"
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent)

    return result.returncode


def check_coverage_thresholds():
    """Check if coverage meets 80% target."""
    report_path = Path(__file__).parent.parent / "coverage_reports/metrics/backend_phase_165_governance_llm.json"

    if not report_path.exists():
        print(f"ERROR: Coverage report not found at {report_path}")
        return False

    with open(report_path) as f:
        report = json.load(f)

    # Check overall coverage
    overall_pct = report["totals"]["percent_covered"]
    overall_branch_pct = report["totals"].get("percent_covered_branch", 0)

    print(f"\n=== Phase 165 Coverage Summary ===")
    print(f"Line Coverage: {overall_pct:.1f}%")
    print(f"Branch Coverage: {overall_branch_pct:.1f}%")

    # Check individual files
    print(f"\n=== Per-File Coverage ===")
    for filename, file_data in report["files"].items():
        if any(s in filename for s in ["agent_governance_service", "byok_handler", "cognitive_tier"]):
            line_pct = file_data["summary"]["percent_covered"]
            branch_pct = file_data["summary"].get("percent_covered_branch", 0)
            print(f"{filename}: {line_pct:.1f}% line, {branch_pct:.1f}% branch")

    # Check target
    if overall_pct >= TARGET_LINE_COVERAGE:
        print(f"\n✓ PASSED: {overall_pct:.1f}% >= {TARGET_LINE_COVERAGE}% target")
        return True
    else:
        print(f"\n✗ FAILED: {overall_pct:.1f}% < {TARGET_LINE_COVERAGE}% target")
        return False


if __name__ == "__main__":
    returncode = run_coverage_measurement()
    if returncode == 0:
        success = check_coverage_thresholds()
        sys.exit(0 if success else 1)
    else:
        sys.exit(returncode)
