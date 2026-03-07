#!/usr/bin/env python3
"""
Simple test runner for aggregate_property_tests to avoid conftest loading issues.
"""

import sys
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import aggregate_property_tests


def test_jest_xml_parsing():
    """Test Jest XML parsing functionality."""
    print("Testing Jest XML parsing...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Test 1: Valid XML
        junit_xml = tmp_path / "results.xml"
        junit_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite tests="5">
    <testcase name="test1"/>
    <testcase name="test2"/>
    <testcase name="test3">
      <failure message="Failed"/>
    </testcase>
    <testcase name="test4"/>
    <testcase name="test5">
      <failure message="Failed"/>
    </testcase>
  </testsuite>
</testsuites>
""")

        result = aggregate_property_tests.parse_jest_xml(junit_xml)
        assert result["total"] == 5, f"Expected total=5, got {result['total']}"
        assert result["passed"] == 3, f"Expected passed=3, got {result['passed']}"
        assert result["failed"] == 2, f"Expected failed=2, got {result['failed']}"
        print("  ✓ Valid XML parsing")

        # Test 2: Missing file
        missing_file = tmp_path / "missing.xml"
        result = aggregate_property_tests.parse_jest_xml(missing_file)
        assert result == {"total": 0, "passed": 0, "failed": 0}, "Missing file should return zeros"
        print("  ✓ Missing file handling")

        # Test 3: Invalid XML
        invalid_xml = tmp_path / "invalid.xml"
        invalid_xml.write_text("not valid xml >>>")
        result = aggregate_property_tests.parse_jest_xml(invalid_xml)
        assert result == {"total": 0, "passed": 0, "failed": 0}, "Invalid XML should return zeros"
        print("  ✓ Invalid XML handling")

        # Test 4: All pass
        junit_xml = tmp_path / "all_pass.xml"
        junit_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite tests="3">
    <testcase name="test1"/>
    <testcase name="test2"/>
    <testcase name="test3"/>
  </testsuite>
</testsuites>
""")

        result = aggregate_property_tests.parse_jest_xml(junit_xml)
        assert result["total"] == 3, f"Expected total=3, got {result['total']}"
        assert result["passed"] == 3, f"Expected passed=3, got {result['passed']}"
        assert result["failed"] == 0, f"Expected failed=0, got {result['failed']}"
        print("  ✓ All pass scenario")

        # Test 5: All fail
        junit_xml = tmp_path / "all_fail.xml"
        junit_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite tests="2">
    <testcase name="test1">
      <failure message="Failed"/>
    </testcase>
    <testcase name="test2">
      <failure message="Failed"/>
    </testcase>
  </testsuite>
</testsuites>
""")

        result = aggregate_property_tests.parse_jest_xml(junit_xml)
        assert result["total"] == 2, f"Expected total=2, got {result['total']}"
        assert result["passed"] == 0, f"Expected passed=0, got {result['passed']}"
        assert result["failed"] == 2, f"Expected failed=2, got {result['failed']}"
        print("  ✓ All fail scenario")


def test_proptest_parsing():
    """Test proptest JSON parsing functionality."""
    print("\nTesting proptest JSON parsing...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Test 1: Valid JSON
        proptest_json = tmp_path / "results.json"
        proptest_json.write_text('{"total": 10, "passed": 8, "failed": 2}')

        result = aggregate_property_tests.parse_proptest_json(proptest_json)
        assert result["total"] == 10, f"Expected total=10, got {result['total']}"
        assert result["passed"] == 8, f"Expected passed=8, got {result['passed']}"
        assert result["failed"] == 2, f"Expected failed=2, got {result['failed']}"
        print("  ✓ Valid JSON parsing")

        # Test 2: Missing file
        missing_file = tmp_path / "missing.json"
        result = aggregate_property_tests.parse_proptest_json(missing_file)
        assert result == {"total": 0, "passed": 0, "failed": 0}, "Missing file should return zeros"
        print("  ✓ Missing file handling")

        # Test 3: Invalid JSON
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("not valid json >>>")
        result = aggregate_property_tests.parse_proptest_json(invalid_json)
        assert result == {"total": 0, "passed": 0, "failed": 0}, "Invalid JSON should return zeros"
        print("  ✓ Invalid JSON handling")


def test_aggregation():
    """Test result aggregation functionality."""
    print("\nTesting result aggregation...")

    # Test 1: All pass
    frontend = {"total": 10, "passed": 10, "failed": 0}
    mobile = {"total": 10, "passed": 10, "failed": 0}
    desktop = {"total": 8, "passed": 8, "failed": 0}

    result = aggregate_property_tests.aggregate_results(frontend, mobile, desktop)
    assert result["total"] == 28, f"Expected total=28, got {result['total']}"
    assert result["passed"] == 28, f"Expected passed=28, got {result['passed']}"
    assert result["failed"] == 0, f"Expected failed=0, got {result['failed']}"
    assert result["pass_rate"] == 100.0, f"Expected pass_rate=100.0, got {result['pass_rate']}"
    assert "timestamp" in result, "Timestamp should be present"
    print("  ✓ All pass aggregation")

    # Test 2: Frontend fails
    frontend = {"total": 10, "passed": 8, "failed": 2}
    mobile = {"total": 10, "passed": 10, "failed": 0}
    desktop = {"total": 8, "passed": 8, "failed": 0}

    result = aggregate_property_tests.aggregate_results(frontend, mobile, desktop)
    assert result["total"] == 28, f"Expected total=28, got {result['total']}"
    assert result["passed"] == 26, f"Expected passed=26, got {result['passed']}"
    assert result["failed"] == 2, f"Expected failed=2, got {result['failed']}"
    expected_rate = round(26 / 28 * 100, 2)
    assert result["pass_rate"] == expected_rate, f"Expected pass_rate={expected_rate}, got {result['pass_rate']}"
    print("  ✓ Mixed pass/fail aggregation")

    # Test 3: Missing platform
    frontend = {"total": 10, "passed": 10, "failed": 0}
    mobile = {"total": 0, "passed": 0, "failed": 0}
    desktop = {"total": 8, "passed": 8, "failed": 0}

    result = aggregate_property_tests.aggregate_results(frontend, mobile, desktop)
    assert result["total"] == 18, f"Expected total=18, got {result['total']}"
    assert result["passed"] == 18, f"Expected passed=18, got {result['passed']}"
    assert result["failed"] == 0, f"Expected failed=0, got {result['failed']}"
    print("  ✓ Missing platform handling")

    # Test 4: Pass rate calculation
    frontend = {"total": 100, "passed": 75, "failed": 25}
    mobile = {"total": 50, "passed": 40, "failed": 10}
    desktop = {"total": 30, "passed": 30, "failed": 0}

    result = aggregate_property_tests.aggregate_results(frontend, mobile, desktop)
    assert result["total"] == 180, f"Expected total=180, got {result['total']}"
    assert result["passed"] == 145, f"Expected passed=145, got {result['passed']}"
    expected_rate = round(145 / 180 * 100, 2)
    assert result["pass_rate"] == expected_rate, f"Expected pass_rate={expected_rate}, got {result['pass_rate']}"
    print("  ✓ Pass rate calculation")


def test_pr_comment_generation():
    """Test PR comment generation."""
    print("\nTesting PR comment generation...")

    # Test 1: All pass
    results = {
        "total": 32,
        "passed": 32,
        "failed": 0,
        "pass_rate": 100.0,
        "platforms": {
            "frontend": {"total": 12, "passed": 12, "failed": 0},
            "mobile": {"total": 12, "passed": 12, "failed": 0},
            "desktop": {"total": 8, "passed": 8, "failed": 0},
        },
        "timestamp": "2026-03-06T00:00:00Z",
    }

    comment = aggregate_property_tests.generate_pr_comment(results)
    assert "## Property Test Results" in comment, "Should have header"
    assert "| Frontend | 12 | 12 | 100.0% |" in comment, "Should have frontend row"
    assert "| Mobile | 12 | 12 | 100.0% |" in comment, "Should have mobile row"
    assert "| Desktop | 8 | 8 | 100.0% |" in comment, "Should have desktop row"
    assert "| **Overall** | **32** | **32** | **100.0%** |" in comment, "Should have overall row"
    assert "✅ All property tests passed" in comment, "Should have success message"
    print("  ✓ All pass comment")

    # Test 2: With failures
    results = {
        "total": 32,
        "passed": 30,
        "failed": 2,
        "pass_rate": 93.75,
        "platforms": {
            "frontend": {"total": 12, "passed": 11, "failed": 1},
            "mobile": {"total": 12, "passed": 11, "failed": 1},
            "desktop": {"total": 8, "passed": 8, "failed": 0},
        },
        "timestamp": "2026-03-06T00:00:00Z",
    }

    comment = aggregate_property_tests.generate_pr_comment(results)
    assert "| Frontend | 11 | 12 | 91.7% |" in comment, "Should have frontend row"
    assert "| Mobile | 11 | 12 | 91.7% |" in comment, "Should have mobile row"
    assert "| Desktop | 8 | 8 | 100.0% |" in comment, "Should have desktop row"
    assert "| **Overall** | **30** | **32** | **93.8%** |" in comment, "Should have overall row"
    assert "❌ Some property tests failed (2 failures)" in comment, "Should have failure message"
    print("  ✓ Failure comment")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Running aggregate_property_tests unit tests")
    print("=" * 60)

    try:
        test_jest_xml_parsing()
        test_proptest_parsing()
        test_aggregation()
        test_pr_comment_generation()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
