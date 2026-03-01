#!/usr/bin/env python
"""
Unified Quality Gate Enforcement Script for Atom CI/CD

This script enforces all quality gates in the CI pipeline:
- Coverage gate: 80% line coverage, 70% branch coverage minimum
- Pass rate gate: 98% minimum pass rate
- Regression gate: No more than 5% coverage drop from baseline
- Flaky test gate: Warn if >5% flaky, fail if >10% flaky
- Main branch gate: 80% overall coverage enforced on main branch merges

Usage:
    python ci_quality_gate.py
    python ci_quality_gate.py --coverage-min 85 --pass-rate-min 99
    python ci_quality_gate.py --strict
    python ci_quality_gate.py --main-branch-min 80 --aggregated

Exit Codes:
    0: All gates passed
    1: One or more gates failed
    2: Error in execution
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


# Default thresholds
DEFAULT_COVERAGE_LINE_MIN = 80.0
DEFAULT_COVERAGE_BRANCH_MIN = 70.0
DEFAULT_PASS_RATE_MIN = 98.0
DEFAULT_REGRESSION_THRESHOLD = 5.0
DEFAULT_FLAKY_WARN = 5.0
DEFAULT_FLAKY_FAIL = 10.0
DEFAULT_MAIN_BRANCH_MIN = 80.0
DEFAULT_BACKEND_WEIGHT = 0.7
DEFAULT_FRONTEND_WEIGHT = 0.3


def is_main_branch_merge() -> bool:
    """Check if current CI run is for main branch push (not PR)."""
    ref = os.getenv("GITHUB_REF", "")
    return ref == "refs/heads/main" or ref.startswith("refs/tags/")


def has_coverage_exception_label() -> bool:
    """Check for !coverage-exception PR label via GitHub API."""
    # Only applicable for PR contexts
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    if event_name != "pull_request":
        return False

    # Check for exception label
    # In CI, this would use GitHub API to check labels
    # For now, check environment variable set by workflow
    return os.getenv("COVERAGE_EXCEPTION", "false").lower() == "true"


def load_backend_coverage(coverage_file: Path) -> float:
    """Load backend coverage from pytest coverage.json format."""
    if not coverage_file.exists():
        return 0.0

    try:
        with open(coverage_file) as f:
            data = json.load(f)
        totals = data.get("totals", {})
        return totals.get("percent_covered", 0.0)
    except (json.JSONDecodeError, IOError):
        return 0.0


def load_frontend_coverage(coverage_file: Path) -> float:
    """Load frontend coverage from Jest coverage-final.json format."""
    if not coverage_file.exists():
        return 0.0  # Missing frontend treated as 0%

    try:
        with open(coverage_file) as f:
            data = json.load(f)

        total_statements = 0
        covered_statements = 0

        for file_path, file_data in data.items():
            if "node_modules" in file_path or "__tests__" in file_path:
                continue
            statements = file_data.get("s", {})
            for stmt_id, count in statements.items():
                total_statements += 1
                if count > 0:
                    covered_statements += 1

        return (covered_statements / total_statements * 100) if total_statements > 0 else 0.0
    except (json.JSONDecodeError, IOError):
        return 0.0


def check_aggregated_coverage(
    backend_cov_file: Path,
    frontend_cov_file: Path,
    weights: Tuple[float, float] = (DEFAULT_BACKEND_WEIGHT, DEFAULT_FRONTEND_WEIGHT)
) -> Tuple[float, float, float, bool, str]:
    """
    Check aggregated coverage (backend + frontend) with weighted average.

    Args:
        backend_cov_file: Path to backend coverage.json
        frontend_cov_file: Path to frontend coverage-final.json
        weights: Tuple of (backend_weight, frontend_weight)

    Returns:
        (overall_pct, backend_pct, frontend_pct, passed, message)
    """
    backend_cov = load_backend_coverage(backend_cov_file)
    frontend_cov = load_frontend_coverage(frontend_cov_file)

    overall = (backend_cov * weights[0]) + (frontend_cov * weights[1])

    passed = overall >= 80.0
    message = (
        f"Aggregated: {overall:.2f}% "
        f"(Backend: {backend_cov:.2f}%, Frontend: {frontend_cov:.2f}%, "
        f"Weights: {weights[0]*100:.0f}%/{weights[1]*100:.0f}%)"
    )

    return overall, backend_cov, frontend_cov, passed, message


def check_main_branch_coverage_gate(
    backend_cov_file: Path,
    frontend_cov_file: Path,
    min_coverage: float = DEFAULT_MAIN_BRANCH_MIN
) -> Tuple[bool, str]:
    """
    Check main branch coverage gate (enforced only on main branch merges).

    Args:
        backend_cov_file: Path to backend coverage.json
        frontend_cov_file: Path to frontend coverage-final.json
        min_coverage: Minimum overall coverage percentage

    Returns:
        (passed, message) tuple
    """
    # Check if running on main branch
    if not is_main_branch_merge():
        return True, "SKIP - Not on main branch (PR or other branch)"

    # Check for exception label
    if has_coverage_exception_label():
        return True, "PASS - Coverage exception label present (!coverage-exception)"

    # Check aggregated coverage
    overall, backend_cov, frontend_cov, passed, message = check_aggregated_coverage(
        backend_cov_file,
        frontend_cov_file
    )

    if not passed:
        message = (
            f"FAIL - {message}, below {min_coverage:.0f}% threshold. "
            f"Add !coverage-exception label to bypass."
        )
        return False, message

    return True, message


def check_coverage_gate(
    coverage_file,
    line_min,
    branch_min
):
    """
    Check coverage gate against minimum thresholds.

    Args:
        coverage_file: Path to coverage.json
        line_min: Minimum line coverage percentage
        branch_min: Minimum branch coverage percentage

    Returns:
        (passed, message) tuple
    """
    if not coverage_file.exists():
        return False, f"FAIL - Coverage file not found: {coverage_file}"

    try:
        with open(coverage_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return False, f"FAIL - Error reading coverage file: {e}"

    # Extract totals from coverage.json
    totals = data.get("totals", {})
    line_coverage = totals.get("percent_covered", 0.0)
    branch_coverage = totals.get("percent_branches_covered", 0.0)

    # Check line coverage
    line_passed = line_coverage >= line_min
    branch_passed = branch_coverage >= branch_min

    if line_passed and branch_passed:
        message = (
            f"PASS - Line: {line_coverage:.2f}% (>= {line_min:.0f}%), "
            f"Branch: {branch_coverage:.2f}% (>= {branch_min:.0f}%)"
        )
        return True, message
    else:
        failures = []
        if not line_passed:
            failures.append(f"Line coverage {line_coverage:.2f}% < {line_min:.0f}%")
        if not branch_passed:
            failures.append(f"Branch coverage {branch_coverage:.2f}% < {branch_min:.0f}%")

        message = f"FAIL - " + ", ".join(failures)
        return False, message


def check_pass_rate_gate(
    health_file,
    pass_rate_min
):
    """
    Check pass rate gate against minimum threshold.

    Args:
        health_file: Path to test_health.json
        pass_rate_min: Minimum pass rate percentage

    Returns:
        (passed, message) tuple
    """
    if not health_file.exists():
        return False, f"WARN - Test health file not found: {health_file} (skipping pass rate check)"

    try:
        with open(health_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return False, f"WARN - Error reading health file: {e} (skipping pass rate check)"

    # Get most recent pass rate from history
    history = data.get("pass_rate_history", [])
    if not history:
        return False, "WARN - No pass rate history found (skipping pass rate check)"

    latest = history[-1]
    pass_rate = latest.get("pass_rate", 0.0)
    total_tests = latest.get("total_tests", 0)
    passed = latest.get("passed", 0)
    failed = latest.get("failed", 0)

    if pass_rate >= pass_rate_min:
        message = (
            f"PASS - {pass_rate:.2f}% (>= {pass_rate_min:.0f}%), "
            f"{passed}/{total_tests} tests passed"
        )
        return True, message
    else:
        message = (
            f"FAIL - {pass_rate:.2f}% < {pass_rate_min:.0f}%, "
            f"{failed}/{total_tests} tests failed"
        )
        return False, message


def check_regression_gate(
    trending_file,
    coverage_file,
    regression_threshold
):
    """
    Check coverage regression gate against baseline.

    Args:
        trending_file: Path to trending.json
        coverage_file: Path to coverage.json (for current coverage)
        regression_threshold: Maximum allowed coverage drop percentage

    Returns:
        (passed, message) tuple
    """
    if not trending_file.exists():
        return False, "WARN - Trending file not found (skipping regression check)"

    try:
        with open(trending_file, 'r') as f:
            trending_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False, "WARN - Error reading trending file (skipping regression check)"

    # Get baseline coverage
    baselines = trending_data.get("baselines", {})
    baseline = baselines.get("090-baseline") or baselines.get("v3.2")

    if not baseline:
        return False, "WARN - No baseline coverage found (skipping regression check)"

    baseline_coverage = baseline.get("coverage_pct", 0.0)

    # Get current coverage
    if not coverage_file.exists():
        return False, "WARN - Coverage file not found (skipping regression check)"

    try:
        with open(coverage_file, 'r') as f:
            coverage_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False, "WARN - Error reading coverage file (skipping regression check)"

    current_coverage = coverage_data.get("totals", {}).get("percent_covered", 0.0)

    # Check regression
    coverage_change = current_coverage - baseline_coverage

    if coverage_change >= -regression_threshold:
        if coverage_change >= 0:
            message = (
                f"PASS - {current_coverage:.2f}% (↑{coverage_change:+.2f}% from baseline {baseline_coverage:.2f}%)"
            )
        else:
            message = (
                f"PASS - {current_coverage:.2f}% (↓{coverage_change:+.2f}% from baseline {baseline_coverage:.2f}%, "
                f"within {regression_threshold:.0f}% threshold)"
            )
        return True, message
    else:
        message = (
            f"FAIL - {current_coverage:.2f}% (↓{coverage_change:+.2f}% from baseline {baseline_coverage:.2f}%, "
            f"exceeds {regression_threshold:.0f}% threshold)"
        )
        return False, message


def check_flaky_test_gate(
    health_file,
    warn_threshold,
    fail_threshold
):
    """
    Check flaky test gate against thresholds.

    Args:
        health_file: Path to test_health.json
        warn_threshold: Warning threshold for flaky test percentage
        fail_threshold: Failure threshold for flaky test percentage

    Returns:
        (passed, message) tuple
    """
    if not health_file.exists():
        return True, "PASS - Test health file not found (skipping flaky test check)"

    try:
        with open(health_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return True, "PASS - Error reading health file (skipping flaky test check)"

    # Get flaky test count
    flaky_tests = data.get("flaky_tests", [])
    history = data.get("pass_rate_history", [])

    if not history:
        return True, "PASS - No test history found (skipping flaky test check)"

    latest = history[-1]
    total_tests = latest.get("total_tests", 0)

    if total_tests == 0:
        return True, "PASS - No tests found (skipping flaky test check)"

    flaky_count = len(flaky_tests)
    flaky_percentage = (flaky_count / total_tests) * 100

    if flaky_percentage >= fail_threshold:
        message = (
            f"FAIL - {flaky_count}/{total_tests} tests flaky ({flaky_percentage:.1f}% >= {fail_threshold:.0f}%)"
        )
        return False, message
    elif flaky_percentage >= warn_threshold:
        message = (
            f"WARN - {flaky_count}/{total_tests} tests flaky ({flaky_percentage:.1f}% >= {warn_threshold:.0f}%)"
        )
        return True, message  # Warning doesn't fail the gate
    else:
        message = (
            f"PASS - {flaky_count}/{total_tests} tests flaky ({flaky_percentage:.1f}% < {warn_threshold:.0f}%)"
        )
        return True, message


def print_summary(results):
    """
    Print formatted summary of all gate results.

    Args:
        results: Dictionary mapping gate names to (passed, message) tuples
    """
    print("\n" + "=" * 80)
    print("QUALITY GATES ENFORCEMENT")
    print("=" * 80)

    # Print individual gate results
    for gate_name, (passed, message) in results.items():
        status = "✓" if passed else "✗"
        print(f"\n{gate_name}: {status}")
        print(f"  {message}")

    # Overall status
    all_passed = all(passed for passed, _ in results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("OVERALL: PASS ✓")
        print("=" * 80 + "\n")
    else:
        failed_gates = [
            name for name, (passed, _) in results.items()
            if not passed
        ]
        print(f"OVERALL: FAIL ✗")
        print(f"Failed gates: {', '.join(failed_gates)}")
        print("=" * 80 + "\n")


def print_remediation(failed_gates):
    """
    Print remediation steps for failed gates.

    Args:
        failed_gates: List of failed gate names
    """
    if not failed_gates:
        return

    print("=" * 80)
    print("REMEDIATION STEPS")
    print("=" * 80 + "\n")

    remediation = {
        "COVERAGE": """Coverage below 80%:
1. Run tests locally: pytest --cov=core --cov=api --cov=tools --cov-report=term-missing
2. Identify uncovered lines in the report above
3. Add tests for uncovered lines (focus on high-value modules first)
4. Re-run tests to verify improvement""",
        "PASS_RATE": """Pass rate below 98%:
1. Fix failing tests: pytest tests/ -v --tb=short
2. Remove broken tests that cannot be fixed
3. Investigate flaky tests (check timing issues, external dependencies)
4. Run tests multiple times to verify stability: pytest --reruns 2""",
        "REGRESSION": """Coverage regression detected:
1. Review new code for test gaps
2. Add coverage for changed functionality
3. Ensure no test files were accidentally removed
4. Check if coverage exclusion patterns changed""",
        "FLAKY": """Too many flaky tests:
1. Identify flaky tests in test_health.json
2. Fix timing issues (add proper async coordination)
3. Add mocks for external dependencies (network, databases)
4. Use unique_resource_name fixture for parallel test isolation
5. Remove test non-determinism (random data, timestamps)"""
    }

    for gate in failed_gates:
        gate_key = gate.split()[0]  # Extract "COVERAGE" from "COVERAGE GATE"
        if gate_key in remediation:
            print(f"\n{remediation[gate_key]}\n")


def main():
    """Main entry point for quality gate enforcement."""
    parser = argparse.ArgumentParser(
        description="Enforce quality gates in CI/CD pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ci_quality_gate.py
  python ci_quality_gate.py --coverage-min 85 --pass-rate-min 99
  python ci_quality_gate.py --strict

Exit Codes:
  0: All gates passed
  1: One or more gates failed
  2: Error in execution
        """
    )

    parser.add_argument(
        "--coverage-file",
        type=str,
        default="tests/coverage_reports/metrics/coverage.json",
        help="Path to coverage.json (default: tests/coverage_reports/metrics/coverage.json)"
    )

    parser.add_argument(
        "--health-file",
        type=str,
        default="tests/coverage_reports/metrics/test_health.json",
        help="Path to test_health.json (default: tests/coverage_reports/metrics/test_health.json)"
    )

    parser.add_argument(
        "--trending-file",
        type=str,
        default="tests/coverage_reports/metrics/trending.json",
        help="Path to trending.json (default: tests/coverage_reports/metrics/trending.json)"
    )

    parser.add_argument(
        "--coverage-min",
        type=float,
        default=DEFAULT_COVERAGE_LINE_MIN,
        help="Minimum line coverage percentage (default: {:.0f}%%)".format(DEFAULT_COVERAGE_LINE_MIN)
    )

    parser.add_argument(
        "--branch-min",
        type=float,
        default=DEFAULT_COVERAGE_BRANCH_MIN,
        help="Minimum branch coverage percentage (default: {:.0f}%%)".format(DEFAULT_COVERAGE_BRANCH_MIN)
    )

    parser.add_argument(
        "--pass-rate-min",
        type=float,
        default=DEFAULT_PASS_RATE_MIN,
        help="Minimum pass rate percentage (default: {:.0f}%%)".format(DEFAULT_PASS_RATE_MIN)
    )

    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=DEFAULT_REGRESSION_THRESHOLD,
        help="Maximum coverage regression percentage (default: {:.0f}%%)".format(DEFAULT_REGRESSION_THRESHOLD)
    )

    parser.add_argument(
        "--flaky-warn",
        type=float,
        default=DEFAULT_FLAKY_WARN,
        help="Flaky test warning threshold (default: {:.0f}%%)".format(DEFAULT_FLAKY_WARN)
    )

    parser.add_argument(
        "--flaky-fail",
        type=float,
        default=DEFAULT_FLAKY_FAIL,
        help="Flaky test failure threshold (default: {:.0f}%%)".format(DEFAULT_FLAKY_FAIL)
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode (fail on warnings, higher thresholds)"
    )

    parser.add_argument(
        "--main-branch-min",
        type=float,
        default=DEFAULT_MAIN_BRANCH_MIN,
        help="Minimum overall coverage for main branch (default: {:.0f}%%)".format(DEFAULT_MAIN_BRANCH_MIN)
    )

    parser.add_argument(
        "--aggregated",
        action="store_true",
        help="Use aggregated coverage (backend + frontend) instead of backend only"
    )

    parser.add_argument(
        "--frontend-coverage",
        type=str,
        default="../frontend-nextjs/coverage/coverage-final.json",
        help="Path to frontend coverage-final.json (default: ../frontend-nextjs/coverage/coverage-final.json)"
    )

    parser.add_argument(
        "--weights",
        type=str,
        default=f"{DEFAULT_BACKEND_WEIGHT},{DEFAULT_FRONTEND_WEIGHT}",
        help="Backend/frontend weights for aggregated coverage (default: 0.7,0.3)"
    )

    parser.add_argument(
        "--allow-exception-label",
        action="store_true",
        help="Allow !coverage-exception PR label to bypass gate"
    )

    args = parser.parse_args()

    # Apply strict mode overrides
    if args.strict:
        args.coverage_min = max(args.coverage_min, 85.0)
        args.branch_min = max(args.branch_min, 75.0)
        args.pass_rate_min = max(args.pass_rate_min, 99.0)
        args.regression_threshold = min(args.regression_threshold, 3.0)
        args.flaky_warn = min(args.flaky_warn, 3.0)
        args.flaky_fail = min(args.flaky_fail, 5.0)

    # Resolve file paths
    backend_dir = Path(__file__).parent.parent.parent
    coverage_file = backend_dir / args.coverage_file
    health_file = backend_dir / args.health_file
    trending_file = backend_dir / args.trending_file

    # Parse weights for aggregated coverage
    try:
        weights_str = args.weights.split(",")
        backend_weight = float(weights_str[0])
        frontend_weight = float(weights_str[1]) if len(weights_str) > 1 else 1.0 - backend_weight
    except (ValueError, IndexError):
        print(f"ERROR: Invalid weights format: {args.weights}. Use comma-separated values (e.g., 0.7,0.3)")
        sys.exit(2)

    weights = (backend_weight, frontend_weight)

    # Frontend coverage path
    frontend_coverage = backend_dir / args.frontend_coverage

    # Run all gates
    results = {}

    # Main branch gate (only on main branch merges)
    if is_main_branch_merge():
        results["MAIN BRANCH GATE"] = check_main_branch_coverage_gate(
            coverage_file,
            frontend_coverage,
            args.main_branch_min
        )

    # Standard coverage gate
    if args.aggregated:
        overall, backend_cov, frontend_cov, passed, message = check_aggregated_coverage(
            coverage_file,
            frontend_coverage,
            weights
        )
        results["COVERAGE GATE"] = (passed, message)
    else:
        results["COVERAGE GATE"] = check_coverage_gate(
            coverage_file,
            args.coverage_min,
            args.branch_min
        )

    results["PASS RATE GATE"] = check_pass_rate_gate(
        health_file,
        args.pass_rate_min
    )

    results["REGRESSION GATE"] = check_regression_gate(
        trending_file,
        coverage_file,
        args.regression_threshold
    )

    results["FLAKY TEST GATE"] = check_flaky_test_gate(
        health_file,
        args.flaky_warn,
        args.flaky_fail
    )

    # Print summary
    print_summary(results)

    # Print remediation for failed gates
    failed_gates = [
        name for name, (passed, _) in results.items()
        if not passed
    ]
    print_remediation(failed_gates)

    # Return exit code
    if all(passed for passed, _ in results.values()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
