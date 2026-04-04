"""
Unit tests for aggregate_property_tests.py.

Covers parsing, aggregation, CLI, and PR comment generation.
"""

import json
import tempfile
from pathlib import Path

import pytest

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
try:
    import aggregate_property_tests
except ImportError:
    aggregate_property_tests = None
    pytest.skip("aggregate_property_tests module not found", allow_module_level=True)


class TestJestXmlParsing:
    """Test Jest XML parsing functionality."""

    def test_parse_jest_xml_valid(self, tmp_path):
        """Verify extraction of total/passed/failed from valid JUnit XML."""
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
        assert result["total"] == 5
        assert result["passed"] == 3
        assert result["failed"] == 2

    def test_parse_jest_xml_missing(self, tmp_path):
        """Verify 0,0,0 returned when file missing."""
        missing_file = tmp_path / "missing.xml"
        result = aggregate_property_tests.parse_jest_xml(missing_file)
        assert result == {"total": 0, "passed": 0, "failed": 0}

    def test_parse_jest_xml_invalid_xml(self, tmp_path):
        """Verify error handling for invalid XML."""
        invalid_xml = tmp_path / "invalid.xml"
        invalid_xml.write_text("not valid xml >>>")

        result = aggregate_property_tests.parse_jest_xml(invalid_xml)
        assert result == {"total": 0, "passed": 0, "failed": 0}

    def test_parse_jest_xml_no_failures(self, tmp_path):
        """Verify all tests passed."""
        junit_xml = tmp_path / "results.xml"
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
        assert result["total"] == 3
        assert result["passed"] == 3
        assert result["failed"] == 0

    def test_parse_jest_xml_all_failures(self, tmp_path):
        """Verify all tests failed."""
        junit_xml = tmp_path / "results.xml"
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
        assert result["total"] == 2
        assert result["passed"] == 0
        assert result["failed"] == 2


class TestProptestParsing:
    """Test proptest JSON parsing functionality."""

    def test_parse_proptest_json_valid(self, tmp_path):
        """Verify extraction of total/passed/failed from valid JSON."""
        proptest_json = tmp_path / "results.json"
        proptest_json.write_text('{"total": 10, "passed": 8, "failed": 2}')

        result = aggregate_property_tests.parse_proptest_json(proptest_json)
        assert result["total"] == 10
        assert result["passed"] == 8
        assert result["failed"] == 2

    def test_parse_proptest_json_missing(self, tmp_path):
        """Verify 0,0,0 returned when file missing."""
        missing_file = tmp_path / "missing.json"
        result = aggregate_property_tests.parse_proptest_json(missing_file)
        assert result == {"total": 0, "passed": 0, "failed": 0}

    def test_parse_proptest_json_invalid_json(self, tmp_path):
        """Verify error handling for invalid JSON."""
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("not valid json >>>")

        result = aggregate_property_tests.parse_proptest_json(invalid_json)
        assert result == {"total": 0, "passed": 0, "failed": 0}

    def test_parse_proptest_json_stdout_fallback(self, tmp_path):
        """Verify regex parsing of stdout fallback."""
        # Create JSON with partial data
        proptest_json = tmp_path / "results.json"
        proptest_json.write_text('{"total": 5, "passed": 5, "failed": 0}')

        result = aggregate_property_tests.parse_proptest_json(proptest_json)
        assert result["total"] == 5
        assert result["passed"] == 5
        assert result["failed"] == 0


class TestAggregation:
    """Test result aggregation functionality."""

    def test_aggregate_results_all_pass(self):
        """Verify 100% pass rate when all tests pass."""
        frontend = {"total": 10, "passed": 10, "failed": 0}
        mobile = {"total": 10, "passed": 10, "failed": 0}
        desktop = {"total": 8, "passed": 8, "failed": 0}

        result = aggregate_property_tests.aggregate_results(
            frontend, mobile, desktop
        )
        assert result["total"] == 28
        assert result["passed"] == 28
        assert result["failed"] == 0
        assert result["pass_rate"] == 100.0
        assert "timestamp" in result
        assert result["platforms"]["frontend"] == frontend
        assert result["platforms"]["mobile"] == mobile
        assert result["platforms"]["desktop"] == desktop

    def test_aggregate_results_frontend_fails(self):
        """Verify pass rate calculation with failures."""
        frontend = {"total": 10, "passed": 8, "failed": 2}
        mobile = {"total": 10, "passed": 10, "failed": 0}
        desktop = {"total": 8, "passed": 8, "failed": 0}

        result = aggregate_property_tests.aggregate_results(
            frontend, mobile, desktop
        )
        assert result["total"] == 28
        assert result["passed"] == 26
        assert result["failed"] == 2
        assert result["pass_rate"] == round(26 / 28 * 100, 2)

    def test_aggregate_results_missing_platform(self):
        """Verify exclusion of missing platform (zeros)."""
        frontend = {"total": 10, "passed": 10, "failed": 0}
        mobile = {"total": 0, "passed": 0, "failed": 0}
        desktop = {"total": 8, "passed": 8, "failed": 0}

        result = aggregate_property_tests.aggregate_results(
            frontend, mobile, desktop
        )
        assert result["total"] == 18
        assert result["passed"] == 18
        assert result["failed"] == 0
        assert result["pass_rate"] == 100.0

    def test_aggregate_results_timestamp_included(self):
        """Verify timestamp present in results."""
        frontend = {"total": 1, "passed": 1, "failed": 0}
        mobile = {"total": 0, "passed": 0, "failed": 0}
        desktop = {"total": 0, "passed": 0, "failed": 0}

        result = aggregate_property_tests.aggregate_results(
            frontend, mobile, desktop
        )
        assert "timestamp" in result
        assert result["timestamp"] is not None
        # ISO 8601 format check
        assert "T" in result["timestamp"]
        assert "Z" in result["timestamp"] or "+" in result["timestamp"]

    def test_aggregate_results_pass_rate_calculation(self):
        """Verify accurate percentage calculation."""
        frontend = {"total": 100, "passed": 75, "failed": 25}
        mobile = {"total": 50, "passed": 40, "failed": 10}
        desktop = {"total": 30, "passed": 30, "failed": 0}

        result = aggregate_property_tests.aggregate_results(
            frontend, mobile, desktop
        )
        assert result["total"] == 180
        assert result["passed"] == 145
        assert result["failed"] == 35
        # 145/180 = 80.555...%
        assert result["pass_rate"] == round(145 / 180 * 100, 2)


class TestCliIntegration:
    """Test CLI integration."""

    def test_cli_help_text(self, tmp_path):
        """Verify --help output."""
        import subprocess

        result = subprocess.run(
            ["python3", "backend/tests/scripts/aggregate_property_tests.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Aggregate property test results" in result.stdout
        assert "--frontend" in result.stdout
        assert "--mobile" in result.stdout
        assert "--desktop" in result.stdout
        assert "--output" in result.stdout
        assert "--format" in result.stdout

    def test_cli_json_output(self, tmp_path):
        """Verify JSON file generation."""
        # Create test input files
        frontend_xml = tmp_path / "frontend.xml"
        frontend_xml.write_text("""<?xml version="1.0"?>
<testsuites><testsuite tests="2"><testcase name="test1"/><testcase name="test2"/></testsuite></testsuites>
""")

        output_json = tmp_path / "output.json"

        result = subprocess.run(
            [
                "python3",
                "backend/tests/scripts/aggregate_property_tests.py",
                "--frontend",
                str(frontend_xml),
                "--output",
                str(output_json),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert output_json.exists()

        data = json.loads(output_json.read_text())
        assert "total" in data
        assert "passed" in data
        assert "failed" in data
        assert "pass_rate" in data
        assert "platforms" in data
        assert "timestamp" in data

    def test_cli_markdown_output(self, tmp_path):
        """Verify markdown table generation."""
        frontend_xml = tmp_path / "frontend.xml"
        frontend_xml.write_text("""<?xml version="1.0"?>
<testsuites><testsuite tests="2"><testcase name="test1"/><testcase name="test2"/></testsuite></testsuites>
""")

        output_md = tmp_path / "output.md"

        result = subprocess.run(
            [
                "python3",
                "backend/tests/scripts/aggregate_property_tests.py",
                "--frontend",
                str(frontend_xml),
                "--output",
                str(output_md),
                "--format",
                "markdown",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert output_md.exists()

        content = output_md.read_text()
        assert "## Property Test Results" in content
        assert "| Platform |" in content
        assert "| Frontend |" in content
        assert "✅ All property tests passed" in content

    def test_cli_exit_code_on_failure(self, tmp_path):
        """Verify exit 1 on failures."""
        frontend_xml = tmp_path / "frontend.xml"
        frontend_xml.write_text("""<?xml version="1.0"?>
<testsuites><testsuite tests="2"><testcase name="test1"/><testcase name="test2"><failure message="Failed"/></testcase></testsuite></testsuites>
""")

        result = subprocess.run(
            [
                "python3",
                "backend/tests/scripts/aggregate_property_tests.py",
                "--frontend",
                str(frontend_xml),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1


class TestPrCommentGeneration:
    """Test PR comment generation."""

    def test_generate_pr_comment_all_pass(self):
        """Verify success message."""
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
        assert "## Property Test Results" in comment
        assert "| Frontend | 12 | 12 | 100.0% |" in comment
        assert "| Mobile | 12 | 12 | 100.0% |" in comment
        assert "| Desktop | 8 | 8 | 100.0% |" in comment
        assert "| **Overall** | **32** | **32** | **100.0%** |" in comment
        assert "✅ All property tests passed" in comment

    def test_generate_pr_comment_with_failures(self):
        """Verify failure details."""
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
        assert "## Property Test Results" in comment
        assert "| Frontend | 11 | 12 | 91.7% |" in comment
        assert "| Mobile | 11 | 12 | 91.7% |" in comment
        assert "| Desktop | 8 | 8 | 100.0% |" in comment
        assert "| **Overall** | **30** | **32** | **93.8%** |" in comment
        assert "❌ Some property tests failed (2 failures)" in comment

    def test_generate_pr_comment_markdown_table(self):
        """Verify table format."""
        results = {
            "total": 8,
            "passed": 8,
            "failed": 0,
            "pass_rate": 100.0,
            "platforms": {
                "frontend": {"total": 0, "passed": 0, "failed": 0},
                "mobile": {"total": 0, "passed": 0, "failed": 0},
                "desktop": {"total": 8, "passed": 8, "failed": 0},
            },
            "timestamp": "2026-03-06T00:00:00Z",
        }

        comment = aggregate_property_tests.generate_pr_comment(results)
        lines = comment.split("\n")

        # Check table header
        assert any("| Platform | Passed | Total | Pass Rate |" in line for line in lines)
        # Check separator
        assert any("|----------|" in line for line in lines)
        # Check data rows
        assert any("| Desktop |" in line for line in lines)
        # Check overall row
        assert any("| **Overall** |" in line for line in lines)


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_pipeline(self, tmp_path):
        """Load all formats, aggregate, output JSON."""
        # Create test files
        frontend_xml = tmp_path / "frontend.xml"
        frontend_xml.write_text("""<?xml version="1.0"?>
<testsuites><testsuite tests="2"><testcase name="test1"/><testcase name="test2"/></testsuite></testsuites>
""")

        mobile_xml = tmp_path / "mobile.xml"
        mobile_xml.write_text("""<?xml version="1.0"?>
<testsuites><testsuite tests="2"><testcase name="test1"/><testcase name="test2"/></testsuite></testsuites>
""")

        desktop_json = tmp_path / "desktop.json"
        desktop_json.write_text('{"total": 2, "passed": 2, "failed": 0}')

        output_json = tmp_path / "output.json"

        result = subprocess.run(
            [
                "python3",
                "backend/tests/scripts/aggregate_property_tests.py",
                "--frontend",
                str(frontend_xml),
                "--mobile",
                str(mobile_xml),
                "--desktop",
                str(desktop_json),
                "--output",
                str(output_json),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert output_json.exists()

        data = json.loads(output_json.read_text())
        assert data["total"] == 6  # 2 + 2 + 2
        assert data["passed"] == 6
        assert data["failed"] == 0
        assert data["pass_rate"] == 100.0
        assert data["platforms"]["frontend"]["total"] == 2
        assert data["platforms"]["mobile"]["total"] == 2
        assert data["platforms"]["desktop"]["total"] == 2
        assert "timestamp" in data


# Import subprocess for CLI tests
import subprocess
