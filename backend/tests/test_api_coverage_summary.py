"""
Coverage summary and phase verification for Phase 102 (Backend API Integration Tests).

This module provides:
1. Coverage report generation for all API route files
2. Phase success criteria verification
3. Test execution summary and metrics
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any


# ============================================================================
# Coverage Report Generation
# ============================================================================

def generate_coverage_report() -> Dict:
    """
    Run pytest with coverage and generate per-endpoint breakdown.

    Returns:
        Dict with coverage data for each API file and overall metrics
    """
    print("=" * 80)
    print("PHASE 102: BACKEND API INTEGRATION TESTS - COVERAGE REPORT")
    print("=" * 80)
    print()

    # API files to check coverage for
    api_files = [
        "core/atom_agent_endpoints.py",
        "api/canvas_routes.py",
        "api/browser_routes.py",
        "api/device_capabilities.py",
    ]

    # Run pytest with coverage
    print("Running coverage analysis...")
    cmd = [
        "pytest",
        "--cov=core/atom_agent_endpoints",
        "--cov=api/canvas_routes",
        "--cov=api/browser_routes",
        "--cov=api/device_capabilities",
        "--cov-report=json",
        "--cov-report=term-missing",
        "tests/test_api_*.py",
        "-v",
        "--tb=no"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=Path(__file__).parent.parent
        )

        print(result.stdout)

        # Parse JSON coverage report
        coverage_file = Path(__file__).parent.parent / "coverage.json"
        if coverage_file.exists():
            with open(coverage_file) as f:
                coverage_data = json.load(f)

            return _parse_coverage_data(coverage_data, api_files)
        else:
            print("Warning: coverage.json not generated")
            return {"error": "Coverage report not generated"}

    except subprocess.TimeoutExpired:
        print("Error: Coverage analysis timed out after 5 minutes")
        return {"error": "Timeout"}
    except Exception as e:
        print(f"Error running coverage analysis: {e}")
        return {"error": str(e)}


def _parse_coverage_data(coverage_data: Dict, api_files: List[str]) -> Dict:
    """Parse coverage.json and extract per-file metrics."""
    report = {
        "files": {},
        "overall": {
            "total_statements": 0,
            "total_missing": 0,
            "total_covered": 0,
            "coverage_percent": 0.0
        }
    }

    files_data = coverage_data.get("files", {})

    for api_file in api_files:
        # Normalize path (coverage.json uses full paths)
        file_key = None
        for key in files_data.keys():
            if api_file in key:
                file_key = key
                break

        if file_key and file_key in files_data:
            file_data = files_data[file_key]
            summary = file_data["summary"]

            report["files"][api_file] = {
                "statements": summary["num_statements"],
                "missing": summary["covered_lines"],
                "covered": summary["num_statements"] - summary["covered_lines"],
                "coverage_percent": round(summary["percent_covered"], 2)
            }

            report["overall"]["total_statements"] += summary["num_statements"]
            report["overall"]["total_covered"] += summary["num_statements"] - summary["covered_lines"]

    # Calculate overall percentage
    if report["overall"]["total_statements"] > 0:
        report["overall"]["coverage_percent"] = round(
            (report["overall"]["total_covered"] / report["overall"]["total_statements"]) * 100, 2
        )
        report["overall"]["total_missing"] = (
            report["overall"]["total_statements"] - report["overall"]["total_covered"]
        )

    return report


# ============================================================================
# Phase Success Criteria Verification
# ============================================================================

def verify_phase_success_criteria() -> Dict:
    """
    Verify all Phase 102 success criteria.

    Returns:
        Dict with verification results for each criterion
    """
    print("\n" + "=" * 80)
    print("PHASE 102: SUCCESS CRITERIA VERIFICATION")
    print("=" * 80)
    print()

    results = {
        "criteria": {},
        "overall_status": "PENDING",
        "recommendations": []
    }

    # Test file existence and test counts
    test_files = {
        "102-01": "tests/test_api_agent_endpoints.py",
        "102-02": "tests/test_api_canvas_routes.py",
        "102-03": "tests/test_api_browser_routes.py",
        "102-04": "tests/test_api_device_routes.py",
        "102-05": "tests/test_api_request_validation.py",
        "102-06": "tests/test_api_database_transactions.py",
    }

    expected_test_counts = {
        "102-01": 40,   # Agent endpoints
        "102-02": 30,   # Canvas routes
        "102-03": 35,   # Browser routes
        "102-04": 40,   # Device capabilities
        "102-05": 35,   # Request validation
        "102-06": 20,   # Transaction tests
    }

    # Criterion 1: All test files exist and are importable
    print("1. Verifying test files exist...")
    all_files_exist = True
    for plan, test_file in test_files.items():
        file_path = Path(__file__).parent.parent / test_file
        exists = file_path.exists()
        print(f"   [{plan}] {test_file}: {'✓' if exists else '✗'}")
        all_files_exist = all_files_exist and exists

    results["criteria"]["test_files_exist"] = {
        "status": "PASS" if all_files_exist else "FAIL",
        "description": "All test files exist"
    }

    # Criterion 2: Verify test counts
    print("\n2. Verifying test counts...")
    test_counts_valid = True
    for plan, test_file in test_files.items():
        count = _count_tests_in_file(test_file)
        expected = expected_test_counts[plan]
        status = "✓" if count >= expected else "✗"
        print(f"   [{plan}] {count}/{expected} tests: {status}")
        if count < expected:
            test_counts_valid = False
            results["recommendations"].append(
                f"Plan {plan}: Need {expected - count} more tests"
            )

    results["criteria"]["test_counts_met"] = {
        "status": "PASS" if test_counts_valid else "PARTIAL",
        "description": "Test counts meet minimum thresholds"
    }

    # Criterion 3: Coverage >60% for each API file
    print("\n3. Verifying coverage targets...")
    coverage_data = generate_coverage_report()

    if "error" not in coverage_data:
        coverage_met = True
        for api_file, metrics in coverage_data.get("files", {}).items():
            coverage = metrics["coverage_percent"]
            status = "✓" if coverage >= 60 else "✗"
            print(f"   {api_file}: {coverage}% {status}")
            if coverage < 60:
                coverage_met = False
                results["recommendations"].append(
                    f"{api_file}: Need {60 - coverage:.1f}% more coverage"
                )

        results["criteria"]["coverage_targets_met"] = {
            "status": "PASS" if coverage_met else "FAIL",
            "description": "All API files have 60%+ coverage"
        }

        # Add coverage data to results
        results["coverage"] = coverage_data
    else:
        results["criteria"]["coverage_targets_met"] = {
            "status": "ERROR",
            "description": "Could not measure coverage"
        }
        coverage_met = False

    # Criterion 4: Overall pass rate >98%
    print("\n4. Verifying test pass rate...")
    pass_rate = _calculate_pass_rate()
    print(f"   Pass rate: {pass_rate:.1f}%")

    results["criteria"]["pass_rate_met"] = {
        "status": "PASS" if pass_rate >= 98 else "FAIL",
        "description": f"Test pass rate >98% (actual: {pass_rate:.1f}%)"
    }

    # Overall status
    all_passed = all(
        c["status"] == "PASS"
        for c in results["criteria"].values()
    )

    results["overall_status"] = "PASS" if all_passed else "PARTIAL" if any(
        c["status"] in ["PASS", "PARTIAL"] for c in results["criteria"].values()
    ) else "FAIL"

    print("\n" + "=" * 80)
    print(f"OVERALL STATUS: {results['overall_status']}")
    print("=" * 80)

    if results["recommendations"]:
        print("\nRecommendations:")
        for rec in results["recommendations"]:
            print(f"  - {rec}")

    return results


def _count_tests_in_file(test_file: str) -> int:
    """Count test functions in a test file."""
    file_path = Path(__file__).parent.parent / test_file

    if not file_path.exists():
        return 0

    try:
        with open(file_path) as f:
            content = f.read()

        # Count function definitions starting with "test_"
        test_count = content.count("def test_")
        return test_count

    except Exception as e:
        print(f"   Error counting tests in {test_file}: {e}")
        return 0


def _calculate_pass_rate() -> float:
    """
    Run all API tests and calculate pass rate.

    Returns:
        Pass rate as percentage (0-100)
    """
    cmd = [
        "pytest",
        "tests/test_api_*.py",
        "-v",
        "--tb=no",
        "--no-header"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=Path(__file__).parent.parent
        )

        output = result.stdout + result.stderr

        # Parse pytest output for pass/fail counts
        # Example: "15 passed, 2 failed in 30.5s"
        import re

        match = re.search(r'(\d+) passed(?:, (\d+) failed)?', output)
        if match:
            passed = int(match.group(1))
            failed = int(match.group(2)) if match.group(2) else 0
            total = passed + failed

            if total > 0:
                return (passed / total) * 100

        return 0.0

    except subprocess.TimeoutExpired:
        print("   Error: Pass rate calculation timed out")
        return 0.0
    except Exception as e:
        print(f"   Error calculating pass rate: {e}")
        return 0.0


# ============================================================================
# Test Execution Summary
# ============================================================================

def print_test_execution_summary():
    """Print summary of test execution metrics."""
    print("\n" + "=" * 80)
    print("PHASE 102: TEST EXECUTION SUMMARY")
    print("=" * 80)
    print()

    # Count total tests
    test_files = [
        "tests/test_api_agent_endpoints.py",
        "tests/test_api_canvas_routes.py",
        "tests/test_api_browser_routes.py",
        "tests/test_api_device_routes.py",
        "tests/test_api_request_validation.py",
        "tests/test_api_database_transactions.py",
    ]

    total_tests = 0
    for test_file in test_files:
        count = _count_tests_in_file(test_file)
        total_tests += count
        print(f"  {test_file}: {count} tests")

    print()
    print(f"  Total tests: {total_tests}")
    print()

    # Calculate estimated assertions (assuming ~5 assertions per test)
    estimated_assertions = total_tests * 5
    print(f"  Estimated assertions: ~{estimated_assertions}")
    print()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for coverage summary."""
    print("\n" + "=" * 80)
    print("PHASE 102: BACKEND API INTEGRATION TESTS")
    print("Coverage Summary and Verification")
    print("=" * 80)

    # Print test execution summary
    print_test_execution_summary()

    # Generate coverage report
    coverage = generate_coverage_report()

    # Verify success criteria
    verification = verify_phase_success_criteria()

    # Print final recommendation
    print("\n" + "=" * 80)
    print("FINAL RECOMMENDATION")
    print("=" * 80)
    print()

    if verification["overall_status"] == "PASS":
        print("✓ Phase 102 COMPLETE - All success criteria met")
        print("  Ready to proceed to Phase 103 (Property Tests)")
    elif verification["overall_status"] == "PARTIAL":
        print("⚠ Phase 102 PARTIAL - Some criteria not met")
        print("  Address recommendations before proceeding to Phase 103")
    else:
        print("✗ Phase 102 FAILED - Critical criteria not met")
        print("  Fix blockers before proceeding")

    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
