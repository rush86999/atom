#!/usr/bin/env python3
"""
Standalone test runner for test_coverage_trend_analyzer.py
Runs tests directly without pytest to avoid conftest issues.
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from coverage_trend_analyzer import (
    validate_trend_data,
    detect_regressions,
    analyze_trends,
    calculate_moving_average,
    generate_text_report,
    generate_json_report,
    generate_markdown_report,
    REGRESSION_THRESHOLD,
    CRITICAL_THRESHOLD
)

# Test results
tests_passed = 0
tests_failed = 0
failed_tests = []


def assert_equal(actual, expected, test_name):
    """Assert equality and track results."""
    global tests_passed, tests_failed
    if actual == expected:
        tests_passed += 1
        print(f"  PASS: {test_name}")
    else:
        tests_failed += 1
        failed_tests.append(test_name)
        print(f"  FAIL: {test_name}")
        print(f"    Expected: {expected}")
        print(f"    Actual: {actual}")


def assert_true(condition, test_name):
    """Assert condition is true."""
    assert_equal(condition, True, test_name)


def assert_in(substring, string, test_name):
    """Assert substring in string."""
    global tests_passed, tests_failed
    if substring in string:
        tests_passed += 1
        print(f"  PASS: {test_name}")
    else:
        tests_failed += 1
        failed_tests.append(test_name)
        print(f"  FAIL: {test_name}")
        print(f"    Substring not found: {substring}")


def run_test_group(name, tests):
    """Run a group of tests."""
    print(f"\n{name}")
    print("-" * 70)
    tests()


def test_data_validation():
    """Test data validation functions."""
    # Valid data (with proper 'latest' structure for jsonschema)
    valid_data = {
        "history": [
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {
            "timestamp": datetime.now().isoformat() + "Z",
            "overall_coverage": 75.0,
            "platforms": {"backend": 75.0},
            "thresholds": {"backend": 70.0}
        },
        "platform_trends": {},
        "computed_weights": {"backend": 0.35}
    }

    # Test valid schema
    result = validate_trend_data(valid_data)
    assert_true(result, "Validate valid schema returns True")

    # Test missing history key
    invalid_data = {"latest": {}, "platform_trends": {}}
    result = validate_trend_data(invalid_data)
    assert_true(result == False, "Validate missing history returns False")

    # Test empty history (with proper 'latest' structure)
    empty_data = {
        "history": [],
        "latest": {
            "timestamp": datetime.now().isoformat() + "Z",
            "overall_coverage": 75.0,
            "platforms": {"backend": 75.0},
            "thresholds": {"backend": 70.0}
        },
        "platform_trends": {},
        "computed_weights": {}
    }
    result = validate_trend_data(empty_data)
    assert_true(result, "Validate empty history returns True")


def test_regression_detection():
    """Test regression detection."""
    base_time = datetime.now() - timedelta(days=1)

    # Test backend -3% regression
    regression_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0, "frontend": 82.0},
                "thresholds": {"backend": 70.0, "frontend": 80.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 72.0,
                "platforms": {"backend": 72.0, "frontend": 80.0},
                "thresholds": {"backend": 70.0, "frontend": 80.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(regression_data, threshold=1.0)

    # Should detect 2 regressions (backend -3%, frontend -2%)
    assert_equal(len(regressions), 2, "Detect 2 regressions")

    # Check backend regression
    backend_reg = [r for r in regressions if r["platform"] == "backend"]
    assert_equal(len(backend_reg), 1, "Backend regression detected")
    if backend_reg:
        assert_equal(backend_reg[0]["delta"], -3.0, "Backend delta is -3.0")
        assert_equal(backend_reg[0]["severity"], "warning", "Backend severity is warning")

    # Test critical regression (>5%)
    critical_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 80.0,
                "platforms": {"frontend": 85.0},
                "thresholds": {"frontend": 80.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 70.0,
                "platforms": {"frontend": 75.0},
                "thresholds": {"frontend": 80.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(critical_data, threshold=1.0)
    assert_equal(len(regressions), 1, "Detect 1 critical regression")
    if regressions:
        assert_equal(regressions[0]["severity"], "critical", "Severity is critical")

    # Test below threshold (-0.5%)
    below_threshold_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"mobile": 50.0},
                "thresholds": {"mobile": 50.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 74.5,
                "platforms": {"mobile": 49.5},
                "thresholds": {"mobile": 50.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(below_threshold_data, threshold=1.0)
    assert_equal(len(regressions), 0, "No regression for -0.5% drop")

    # Test improvement (no regression)
    improvement_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 70.0,
                "platforms": {"backend": 70.0},
                "thresholds": {"backend": 70.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(improvement_data, threshold=1.0)
    assert_equal(len(regressions), 0, "No regression for +5% improvement")


def test_trend_analysis():
    """Test trend analysis."""
    base_time = datetime.now() - timedelta(days=2)

    # Test declining trend
    declining_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 72.0,
                "platforms": {"backend": 72.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    trends = analyze_trends(declining_data, periods=1)

    # Check backend trend
    backend_trend = trends["platform_trends"].get("backend")
    assert_true(backend_trend is not None, "Backend trend exists")
    if backend_trend:
        assert_equal(backend_trend["classification"], "declining", "Backend is declining")

    # Test improving trend
    improving_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 70.0,
                "platforms": {"backend": 70.0},
                "thresholds": {"backend": 70.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    trends = analyze_trends(improving_data, periods=1)
    backend_trend = trends["platform_trends"].get("backend")
    if backend_trend:
        assert_equal(backend_trend["classification"], "improving", "Backend is improving")

    # Test insufficient history
    insufficient_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    trends = analyze_trends(insufficient_data, periods=1)
    assert_equal(trends["regression_count"], 0, "0 regressions with insufficient history")
    assert_equal(trends["improvement_count"], 0, "0 improvements with insufficient history")


def test_moving_average():
    """Test moving average calculation."""
    base_time = datetime.now() - timedelta(days=3)

    # Test 3-period moving average
    data = {
        "history": [
            {
                "timestamp": (base_time + timedelta(days=i)).isoformat() + "Z",
                "overall_coverage": 70.0 + i,
                "platforms": {"backend": 70.0 + i},
                "thresholds": {"backend": 70.0}
            }
            for i in range(3)
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    ma = calculate_moving_average(data, "backend", periods=3)
    # Average of 70, 71, 72 = 71
    assert_equal(ma, 71.0, "3-period moving average is 71.0")

    # Test insufficient history
    insufficient_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    ma = calculate_moving_average(insufficient_data, "backend", periods=3)
    assert_equal(ma, None, "Returns None with insufficient history")


def test_report_generation():
    """Test report generation functions."""
    base_time = datetime.now() - timedelta(days=1)

    # Sample data
    regression_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 72.0,
                "platforms": {"backend": 72.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(regression_data, threshold=1.0)
    trends = analyze_trends(regression_data, periods=1)

    # Test text report
    text_report = generate_text_report(regressions, trends)
    assert_in("Coverage Trend Analysis Report", text_report, "Text report has title")
    assert_in("Regressions Detected", text_report, "Text report has regression section")
    assert_in("backend", text_report.lower(), "Text report mentions platform")

    # Test JSON report
    json_report = generate_json_report(regressions, trends)
    report_data = json.loads(json_report)
    assert_true("regressions" in report_data, "JSON report has regressions key")
    assert_true("trends" in report_data, "JSON report has trends key")
    assert_true("generated_at" in report_data, "JSON report has timestamp")

    # Test markdown report
    md_report = generate_markdown_report(regressions, trends)
    assert_in("| Platform |", md_report, "Markdown report has table header")
    assert_in("|", md_report, "Markdown report has table separators")

    # Test no regressions case
    improvement_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 70.0,
                "platforms": {"backend": 70.0},
                "thresholds": {"backend": 70.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(improvement_data, threshold=1.0)
    trends = analyze_trends(improvement_data, periods=1)

    text_report = generate_text_report(regressions, trends)
    assert_in("No Regressions Detected", text_report, "Text report shows no regressions")


def test_edge_cases():
    """Test edge cases."""
    # Test 0% coverage (failed job)
    base_time = datetime.now() - timedelta(days=1)

    zero_coverage_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {"backend": 70.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 0.0,
                "platforms": {"backend": 0.0},
                "thresholds": {"backend": 70.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(zero_coverage_data, threshold=1.0)
    # Should skip 0% coverage
    assert_equal(len(regressions), 0, "0% coverage skipped")

    # Test missing platform data
    missing_platform_data = {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0, "frontend": 80.0},
                "thresholds": {"backend": 70.0, "frontend": 80.0}
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 72.0,
                "platforms": {"backend": 72.0},  # mobile/desktop missing
                "thresholds": {"backend": 70.0, "frontend": 80.0}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(missing_platform_data, threshold=1.0)
    # Should only process backend (mobile/desktop skipped)
    assert_equal(len(regressions), 1, "Missing platforms skipped")

    # Test empty history
    empty_data = {
        "history": [],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }

    regressions = detect_regressions(empty_data, threshold=1.0)
    assert_equal(len(regressions), 0, "Empty history returns no regressions")


# Run all tests
if __name__ == "__main__":
    print("=" * 70)
    print("Coverage Trend Analyzer - Standalone Test Suite")
    print("=" * 70)

    run_test_group("Data Validation Tests", test_data_validation)
    run_test_group("Regression Detection Tests", test_regression_detection)
    run_test_group("Trend Analysis Tests", test_trend_analysis)
    run_test_group("Moving Average Tests", test_moving_average)
    run_test_group("Report Generation Tests", test_report_generation)
    run_test_group("Edge Case Tests", test_edge_cases)

    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    print(f"Pass Rate:    {tests_passed / (tests_passed + tests_failed) * 100:.1f}%")

    if failed_tests:
        print("\nFailed Tests:")
        for test in failed_tests:
            print(f"  - {test}")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)
