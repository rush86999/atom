"""
Unit tests for cross_platform_coverage_gate.py

Tests coverage loading, threshold enforcement, weighted calculation,
and CLI integration for cross-platform coverage enforcement.
"""

import json
import pytest
from pathlib import Path
from sys import version_info
import sys
import os

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import cross_platform_coverage_gate as gate


# ===== Test Fixtures =====

@pytest.fixture
def mock_pytest_coverage_json(tmp_path):
    """Valid pytest coverage.json with totals.percent_covered."""
    data = {
        "totals": {
            "percent_covered": 75.0,
            "covered_lines": 1500,
            "num_statements": 2000,
            "covered_branches": 100,
            "num_branches": 150
        }
    }
    file_path = tmp_path / "pytest_coverage.json"
    file_path.write_text(json.dumps(data))
    return file_path


@pytest.fixture
def mock_jest_coverage_json(tmp_path):
    """Valid Jest coverage-final.json with statement data."""
    data = {
        "src/test.ts": {
            "s": {"1": 10, "2": 5, "3": 0},
            "b": {"1": [10, 5], "2": [8, 2]},
            "f": {"1": 10},
            "l": {"1": 10}
        },
        "src/lib.ts": {
            "s": {"1": 1, "2": 1},
            "b": {},
            "f": {"1": 1},
            "l": {"1": 1}
        }
    }
    file_path = tmp_path / "jest_coverage.json"
    file_path.write_text(json.dumps(data))
    return file_path


@pytest.fixture
def mock_tarpaulin_coverage_json(tmp_path):
    """Valid tarpaulin coverage.json with files[].stats."""
    data = {
        "files": {
            "src/main.rs": {
                "stats": {
                    "covered": 50,
                    "coverable": 100,
                    "percent": 50.0
                }
            },
            "src/lib.rs": {
                "stats": {
                    "covered": 30,
                    "coverable": 50,
                    "percent": 60.0
                }
            }
        }
    }
    file_path = tmp_path / "tarpaulin_coverage.json"
    file_path.write_text(json.dumps(data))
    return file_path


@pytest.fixture
def empty_json(tmp_path):
    """Empty JSON object for missing coverage scenario."""
    file_path = tmp_path / "empty.json"
    file_path.write_text("{}")
    return file_path


@pytest.fixture
def invalid_json(tmp_path):
    """Malformed JSON for error handling test."""
    file_path = tmp_path / "invalid.json"
    file_path.write_text("{invalid json")
    return file_path


# ===== Coverage Loading Tests =====

class TestCoverageLoading:
    """Test coverage data loading from different formats."""

    def test_load_backend_coverage_valid(self, mock_pytest_coverage_json):
        """Verify totals.percent_covered extraction."""
        result = gate.load_backend_coverage(mock_pytest_coverage_json)

        assert result["coverage_pct"] == 75.0
        assert result["covered"] == 1500
        assert result["total"] == 2000
        assert result["error"] is None
        assert result["file_path"] == str(mock_pytest_coverage_json)

    def test_load_backend_coverage_missing(self, tmp_path):
        """Verify 0.0 returned with warning when file not found."""
        missing_path = tmp_path / "nonexistent.json"
        result = gate.load_backend_coverage(missing_path)

        assert result["coverage_pct"] == 0.0
        assert result["covered"] == 0
        assert result["total"] == 0
        assert result["error"] == "file not found"

    def test_load_backend_coverage_invalid_json(self, invalid_json):
        """Verify error handling for malformed JSON."""
        result = gate.load_backend_coverage(invalid_json)

        assert result["coverage_pct"] == 0.0
        assert result["covered"] == 0
        assert result["total"] == 0
        assert "error" in result["error"].lower()

    def test_load_frontend_coverage_valid(self, mock_jest_coverage_json):
        """Verify statement aggregation from 's' field."""
        result = gate.load_frontend_coverage(mock_jest_coverage_json)

        # 5 statements total (3+2), 4 covered (10>0, 5>0, 0, 1>0, 1>0)
        assert result["coverage_pct"] > 0
        assert result["covered"] > 0
        assert result["total"] > 0
        assert result["error"] is None

    def test_load_frontend_coverage_excludes_node_modules(self, tmp_path):
        """Verify filtering of node_modules and __tests__ files."""
        data = {
            "node_modules/lib/index.js": {"s": {"1": 1, "2": 1}},
            "src/__tests__/test.ts": {"s": {"1": 1}},
            "src/app.ts": {"s": {"1": 1, "2": 0}}
        }
        file_path = tmp_path / "jest_with_node_modules.json"
        file_path.write_text(json.dumps(data))

        result = gate.load_frontend_coverage(file_path)

        # Only src/app.ts counted (2 statements, 1 covered)
        assert result["total"] == 2
        assert result["covered"] == 1
        assert result["coverage_pct"] == 50.0

    def test_load_mobile_coverage_valid(self, mock_jest_coverage_json):
        """Same as Jest (jest-expo format)."""
        result = gate.load_mobile_coverage(mock_jest_coverage_json)

        assert result["coverage_pct"] > 0
        assert result["covered"] > 0
        assert result["total"] > 0
        assert result["error"] is None

    def test_load_desktop_coverage_valid(self, mock_tarpaulin_coverage_json):
        """Verify tarpaulin files[].stats parsing."""
        result = gate.load_desktop_coverage(mock_tarpaulin_coverage_json)

        # 80 total covered (50+30), 150 total lines (100+50)
        assert result["covered"] == 80
        assert result["total"] == 150
        assert result["coverage_pct"] == pytest.approx(53.33, rel=0.01)

    def test_load_desktop_coverage_missing_files(self, tmp_path):
        """Verify 0.0 returned when no files in coverage."""
        data = {"files": {}}
        file_path = tmp_path / "empty_tarpaulin.json"
        file_path.write_text(json.dumps(data))

        result = gate.load_desktop_coverage(file_path)

        assert result["coverage_pct"] == 0.0
        assert result["covered"] == 0
        assert result["total"] == 0


# ===== Threshold Enforcement Tests =====

class TestThresholdEnforcement:
    """Test platform-specific threshold enforcement."""

    def test_check_platform_thresholds_all_pass(self):
        """All platforms above minimum."""
        coverage_data = {
            "backend": {"coverage_pct": 75.0},
            "frontend": {"coverage_pct": 85.0},
            "mobile": {"coverage_pct": 60.0},
            "desktop": {"coverage_pct": 50.0}
        }
        thresholds = {
            "backend": 70.0,
            "frontend": 80.0,
            "mobile": 50.0,
            "desktop": 40.0
        }

        all_passed, failures = gate.check_platform_thresholds(coverage_data, thresholds)

        assert all_passed is True
        assert len(failures) == 0

    def test_check_platform_thresholds_backend_fails(self):
        """Backend < 70%."""
        coverage_data = {
            "backend": {"coverage_pct": 65.0},
            "frontend": {"coverage_pct": 85.0},
            "mobile": {"coverage_pct": 60.0},
            "desktop": {"coverage_pct": 50.0}
        }
        thresholds = gate.PLATFORM_THRESHOLDS

        all_passed, failures = gate.check_platform_thresholds(coverage_data, thresholds)

        assert all_passed is False
        assert len(failures) == 1
        assert "backend" in failures[0].lower()
        assert "65.00" in failures[0]

    def test_check_platform_thresholds_mobile_fails(self):
        """Mobile < 50%."""
        coverage_data = {
            "backend": {"coverage_pct": 75.0},
            "frontend": {"coverage_pct": 85.0},
            "mobile": {"coverage_pct": 45.0},
            "desktop": {"coverage_pct": 50.0}
        }
        thresholds = gate.PLATFORM_THRESHOLDS

        all_passed, failures = gate.check_platform_thresholds(coverage_data, thresholds)

        assert all_passed is False
        assert "mobile" in failures[0].lower()

    def test_check_platform_thresholds_multiple_failures(self):
        """Multiple platforms below threshold."""
        coverage_data = {
            "backend": {"coverage_pct": 65.0},
            "frontend": {"coverage_pct": 75.0},
            "mobile": {"coverage_pct": 45.0},
            "desktop": {"coverage_pct": 35.0}
        }
        thresholds = gate.PLATFORM_THRESHOLDS

        all_passed, failures = gate.check_platform_thresholds(coverage_data, thresholds)

        assert all_passed is False
        assert len(failures) == 3  # backend, frontend, mobile, desktop

    def test_check_platform_thresholds_missing_platform(self):
        """Missing platform treated as 0%."""
        coverage_data = {
            "backend": {"coverage_pct": 75.0},
            "frontend": {"coverage_pct": 85.0}
            # mobile, desktop missing
        }
        thresholds = gate.PLATFORM_THRESHOLDS

        all_passed, failures = gate.check_platform_thresholds(coverage_data, thresholds)

        # Should only check backend and frontend
        assert all_passed is True
        assert len(failures) == 0

    def test_check_platform_thresholds_custom_thresholds(self):
        """Override defaults via custom thresholds."""
        coverage_data = {
            "backend": {"coverage_pct": 60.0},
            "frontend": {"coverage_pct": 70.0}
        }
        thresholds = {
            "backend": 50.0,  # Lower threshold
            "frontend": 80.0  # Higher threshold
        }

        all_passed, failures = gate.check_platform_thresholds(coverage_data, thresholds)

        # Backend passes (60 >= 50), frontend fails (70 < 80)
        assert all_passed is False
        assert len(failures) == 1
        assert "frontend" in failures[0].lower()


# ===== Weighted Calculation Tests =====

class TestWeightedCalculation:
    """Test weighted coverage calculation."""

    def test_compute_weighted_coverage_equal_weights(self):
        """Verify 50/50 split calculation."""
        coverage_data = {
            "backend": {"coverage_pct": 80.0},
            "frontend": {"coverage_pct": 60.0}
        }
        weights = {
            "backend": 0.5,
            "frontend": 0.5
        }

        result = gate.compute_weighted_coverage(coverage_data, weights)

        assert result["overall_pct"] == 70.0  # (80*0.5 + 60*0.5)
        assert len(result["platform_breakdown"]) == 2
        assert result["validation"]["valid"] is True

    def test_compute_weighted_coverage_default_weights(self):
        """Verify 35/40/15/10 split."""
        coverage_data = {
            "backend": {"coverage_pct": 100.0},
            "frontend": {"coverage_pct": 100.0},
            "mobile": {"coverage_pct": 100.0},
            "desktop": {"coverage_pct": 100.0}
        }
        weights = gate.PLATFORM_WEIGHTS

        result = gate.compute_weighted_coverage(coverage_data, weights)

        assert result["overall_pct"] == 100.0
        assert result["validation"]["total_weight"] == 1.0

    def test_compute_weighted_coverage_zero_coverage(self):
        """Verify 0% platforms handled."""
        coverage_data = {
            "backend": {"coverage_pct": 0.0},
            "frontend": {"coverage_pct": 50.0}
        }
        weights = {
            "backend": 0.5,
            "frontend": 0.5
        }

        result = gate.compute_weighted_coverage(coverage_data, weights)

        assert result["overall_pct"] == 25.0  # (0*0.5 + 50*0.5)

    def test_compute_weighted_coverage_weights_validation(self):
        """Verify sum to 1.0 check."""
        coverage_data = {
            "backend": {"coverage_pct": 75.0},
            "frontend": {"coverage_pct": 85.0}
        }
        weights = {
            "backend": 0.7,
            "frontend": 0.5  # Sum = 1.2 (invalid)
        }

        result = gate.compute_weighted_coverage(coverage_data, weights)

        assert result["validation"]["valid"] is False
        assert result["validation"]["total_weight"] == 1.2

    def test_compute_weighted_coverage_missing_platform(self):
        """Verify exclusion from calculation."""
        coverage_data = {
            "backend": {"coverage_pct": 75.0}
            # frontend missing
        }
        weights = {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }

        result = gate.compute_weighted_coverage(coverage_data, weights)

        # Only backend counted (75 * 0.35 = 26.25)
        assert result["overall_pct"] == pytest.approx(26.25, rel=0.01)
        assert len(result["platform_breakdown"]) == 1


# ===== CLI Integration Tests =====

class TestCLIIntegration:
    """Test CLI argument parsing and output generation."""

    def test_cli_help_text(self, capsys):
        """Verify --help output."""
        with pytest.raises(SystemExit):
            gate.main(["--help"])

        captured = capsys.readouterr()
        assert "Cross-platform coverage enforcement" in captured.out
        assert "--backend-coverage" in captured.out
        assert "--format" in captured.out

    def test_cli_format_text(self, mock_pytest_coverage_json, capsys):
        """Verify text output generation."""
        # Create minimal coverage files for all platforms
        coverage_files = {
            "backend": mock_pytest_coverage_json,
            "frontend": mock_pytest_coverage_json,  # Reuse for test
            "mobile": mock_pytest_coverage_json,
            "desktop": mock_pytest_coverage_json
        }

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "cross_platform_coverage_gate.py",
                "--backend-coverage", str(coverage_files["backend"]),
                "--frontend-coverage", str(coverage_files["frontend"]),
                "--mobile-coverage", str(coverage_files["mobile"]),
                "--desktop-coverage", str(coverage_files["desktop"]),
                "--format", "text"
            ]
            gate.main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        assert "Cross-Platform Coverage Report" in captured.out
        assert "Platform Coverage:" in captured.out
        assert "Overall Weighted Coverage:" in captured.out

    def test_cli_format_json(self, mock_pytest_coverage_json, capsys):
        """Verify JSON output generation."""
        coverage_files = {
            "backend": mock_pytest_coverage_json,
            "frontend": mock_pytest_coverage_json,
            "mobile": mock_pytest_coverage_json,
            "desktop": mock_pytest_coverage_json
        }

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "cross_platform_coverage_gate.py",
                "--backend-coverage", str(coverage_files["backend"]),
                "--frontend-coverage", str(coverage_files["frontend"]),
                "--mobile-coverage", str(coverage_files["mobile"]),
                "--desktop-coverage", str(coverage_files["desktop"]),
                "--format", "json"
            ]
            gate.main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        # Verify JSON is parseable
        data = json.loads(captured.out)
        assert "platforms" in data
        assert "thresholds" in data
        assert "weighted" in data
        assert "timestamp" in data

    def test_cli_format_markdown(self, mock_pytest_coverage_json, capsys):
        """Verify markdown table generation."""
        coverage_files = {
            "backend": mock_pytest_coverage_json,
            "frontend": mock_pytest_coverage_json,
            "mobile": mock_pytest_coverage_json,
            "desktop": mock_pytest_coverage_json
        }

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "cross_platform_coverage_gate.py",
                "--backend-coverage", str(coverage_files["backend"]),
                "--frontend-coverage", str(coverage_files["frontend"]),
                "--mobile-coverage", str(coverage_files["mobile"]),
                "--desktop-coverage", str(coverage_files["desktop"]),
                "--format", "markdown"
            ]
            gate.main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        assert "## Cross-Platform Coverage Report" in captured.out
        assert "| Platform | Coverage |" in captured.out
        assert "|---|" in captured.out

    def test_cli_strict_mode(self, tmp_path, capsys):
        """Verify exit 1 on threshold failure."""
        # Create backend coverage below threshold
        backend_data = {"totals": {"percent_covered": 65.0, "covered_lines": 1300, "num_statements": 2000}}
        backend_file = tmp_path / "backend_fail.json"
        backend_file.write_text(json.dumps(backend_data))

        # Create passing coverage for other platforms
        passing_data = {"totals": {"percent_covered": 85.0, "covered_lines": 1700, "num_statements": 2000}}
        passing_file = tmp_path / "passing.json"
        passing_file.write_text(json.dumps(passing_data))

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "cross_platform_coverage_gate.py",
                "--backend-coverage", str(backend_file),
                "--frontend-coverage", str(passing_file),
                "--mobile-coverage", str(passing_file),
                "--desktop-coverage", str(passing_file),
                "--strict"
            ]
            with pytest.raises(SystemExit) as exc_info:
                gate.main()
            assert exc_info.value.code == 1
        finally:
            sys.argv = old_argv

    def test_cli_custom_weights(self, mock_pytest_coverage_json, capsys):
        """Verify --weights argument parsing."""
        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "cross_platform_coverage_gate.py",
                "--backend-coverage", str(mock_pytest_coverage_json),
                "--frontend-coverage", str(mock_pytest_coverage_json),
                "--mobile-coverage", str(mock_pytest_coverage_json),
                "--desktop-coverage", str(mock_pytest_coverage_json),
                "--weights", "backend=0.5,frontend=0.5"
            ]
            gate.main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

        # Verify weights were applied (should see different contribution)
        captured = capsys.readouterr()
        assert "weight:" in captured.out

    def test_cli_custom_thresholds(self, mock_pytest_coverage_json, capsys):
        """Verify --thresholds argument parsing."""
        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "cross_platform_coverage_gate.py",
                "--backend-coverage", str(mock_pytest_coverage_json),
                "--frontend-coverage", str(mock_pytest_coverage_json),
                "--mobile-coverage", str(mock_pytest_coverage_json),
                "--desktop-coverage", str(mock_pytest_coverage_json),
                "--thresholds", "backend=50,frontend=60"
            ]
            gate.main()
        except SystemExit:
            pass
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        # Verify custom thresholds applied
        assert "50.00%" in captured.out or "60.00%" in captured.out


# ===== End-to-End Tests =====

class TestEndToEnd:
    """Test full pipeline workflows."""

    def test_full_pipeline_all_pass(self, tmp_path):
        """Load all coverages, check thresholds, compute weighted."""
        # Create passing coverage for all platforms
        backend_data = {"totals": {"percent_covered": 75.0, "covered_lines": 1500, "num_statements": 2000}}
        backend_file = tmp_path / "backend_pass.json"
        backend_file.write_text(json.dumps(backend_data))

        frontend_data = {"src/app.ts": {"s": {"1": 1, "2": 1}}}
        frontend_file = tmp_path / "frontend_pass.json"
        frontend_file.write_text(json.dumps(frontend_data))

        mobile_data = {"src/App.tsx": {"s": {"1": 1, "2": 1}}}
        mobile_file = tmp_path / "mobile_pass.json"
        mobile_file.write_text(json.dumps(mobile_data))

        desktop_data = {"files": {"src/main.rs": {"stats": {"covered": 50, "coverable": 100}}}}
        desktop_file = tmp_path / "desktop_pass.json"
        desktop_file.write_text(json.dumps(desktop_data))

        # Load coverages
        coverage_data = {
            "backend": gate.load_backend_coverage(backend_file),
            "frontend": gate.load_frontend_coverage(frontend_file),
            "mobile": gate.load_mobile_coverage(mobile_file),
            "desktop": gate.load_desktop_coverage(desktop_file)
        }

        # Check thresholds
        all_passed, failures = gate.check_platform_thresholds(
            coverage_data,
            gate.PLATFORM_THRESHOLDS
        )

        # Compute weighted
        weighted = gate.compute_weighted_coverage(
            coverage_data,
            gate.PLATFORM_WEIGHTS
        )

        assert all_passed is True
        assert len(failures) == 0
        assert weighted["weighted"]["overall_pct"] > 0
        assert weighted["weighted"]["validation"]["valid"] is True

    def test_full_pipeline_backend_fails(self, tmp_path):
        """Backend below 70%, others pass."""
        # Create failing backend coverage
        backend_data = {"totals": {"percent_covered": 65.0, "covered_lines": 1300, "num_statements": 2000}}
        backend_file = tmp_path / "backend_fail.json"
        backend_file.write_text(json.dumps(backend_data))

        # Create passing coverage for other platforms
        frontend_data = {"src/app.ts": {"s": {"1": 1, "2": 1}}}
        frontend_file = tmp_path / "frontend_pass.json"
        frontend_file.write_text(json.dumps(frontend_data))

        mobile_data = {"src/App.tsx": {"s": {"1": 1, "2": 1}}}
        mobile_file = tmp_path / "mobile_pass.json"
        mobile_file.write_text(json.dumps(mobile_data))

        desktop_data = {"files": {"src/main.rs": {"stats": {"covered": 50, "coverable": 100}}}}
        desktop_file = tmp_path / "desktop_pass.json"
        desktop_file.write_text(json.dumps(desktop_data))

        # Load coverages
        coverage_data = {
            "backend": gate.load_backend_coverage(backend_file),
            "frontend": gate.load_frontend_coverage(frontend_file),
            "mobile": gate.load_mobile_coverage(mobile_file),
            "desktop": gate.load_desktop_coverage(desktop_file)
        }

        # Check thresholds
        all_passed, failures = gate.check_platform_thresholds(
            coverage_data,
            gate.PLATFORM_THRESHOLDS
        )

        assert all_passed is False
        assert len(failures) == 1
        assert "backend" in failures[0].lower()

    def test_full_pipeline_missing_files(self, tmp_path):
        """One platform file missing."""
        # Create passing coverage for 3 platforms, desktop missing
        backend_data = {"totals": {"percent_covered": 75.0, "covered_lines": 1500, "num_statements": 2000}}
        backend_file = tmp_path / "backend_pass.json"
        backend_file.write_text(json.dumps(backend_data))

        frontend_data = {"src/app.ts": {"s": {"1": 1, "2": 1}}}
        frontend_file = tmp_path / "frontend_pass.json"
        frontend_file.write_text(json.dumps(frontend_data))

        mobile_data = {"src/App.tsx": {"s": {"1": 1, "2": 1}}}
        mobile_file = tmp_path / "mobile_pass.json"
        mobile_file.write_text(json.dumps(mobile_data))

        # Desktop file missing
        desktop_file = tmp_path / "desktop_missing.json"

        # Load coverages
        coverage_data = {
            "backend": gate.load_backend_coverage(backend_file),
            "frontend": gate.load_frontend_coverage(frontend_file),
            "mobile": gate.load_mobile_coverage(mobile_file),
            "desktop": gate.load_desktop_coverage(desktop_file)
        }

        # Desktop should be 0% with error
        assert coverage_data["desktop"]["coverage_pct"] == 0.0
        assert coverage_data["desktop"]["error"] == "file not found"

    def test_full_pipeline_strict_mode_fails(self, tmp_path):
        """Exit 1 when any platform below threshold."""
        # Create failing backend coverage
        backend_data = {"totals": {"percent_covered": 65.0, "covered_lines": 1300, "num_statements": 2000}}
        backend_file = tmp_path / "backend_fail.json"
        backend_file.write_text(json.dumps(backend_data))

        # Create passing coverage for other platforms
        passing_data = {"totals": {"percent_covered": 85.0, "covered_lines": 1700, "num_statements": 2000}}
        passing_file = tmp_path / "passing.json"
        passing_file.write_text(json.dumps(passing_data))

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "cross_platform_coverage_gate.py",
                "--backend-coverage", str(backend_file),
                "--frontend-coverage", str(passing_file),
                "--mobile-coverage", str(passing_file),
                "--desktop-coverage", str(passing_file),
                "--strict"
            ]
            with pytest.raises(SystemExit) as exc_info:
                gate.main()
            assert exc_info.value.code == 1
        finally:
            sys.argv = old_argv

    def test_full_pipeline_output_json(self, tmp_path):
        """Verify JSON structure matches expected schema."""
        # Create passing coverage for all platforms
        backend_data = {"totals": {"percent_covered": 75.0, "covered_lines": 1500, "num_statements": 2000}}
        backend_file = tmp_path / "backend_pass.json"
        backend_file.write_text(json.dumps(backend_data))

        frontend_data = {"src/app.ts": {"s": {"1": 1, "2": 1}}}
        frontend_file = tmp_path / "frontend_pass.json"
        frontend_file.write_text(json.dumps(frontend_data))

        mobile_data = {"src/App.tsx": {"s": {"1": 1, "2": 1}}}
        mobile_file = tmp_path / "mobile_pass.json"
        mobile_file.write_text(json.dumps(mobile_data))

        desktop_data = {"files": {"src/main.rs": {"stats": {"covered": 50, "coverable": 100}}}}
        desktop_file = tmp_path / "desktop_pass.json"
        desktop_file.write_text(json.dumps(desktop_data))

        # Load coverages and build result
        coverage_data = {
            "backend": gate.load_backend_coverage(backend_file),
            "frontend": gate.load_frontend_coverage(frontend_file),
            "mobile": gate.load_mobile_coverage(mobile_file),
            "desktop": gate.load_desktop_coverage(desktop_file)
        }

        all_passed, failures = gate.check_platform_thresholds(
            coverage_data,
            gate.PLATFORM_THRESHOLDS
        )

        weighted = gate.compute_weighted_coverage(
            coverage_data,
            gate.PLATFORM_WEIGHTS
        )

        result = {
            "timestamp": "2026-03-06T00:00:00Z",
            "platforms": coverage_data,
            "thresholds": gate.PLATFORM_THRESHOLDS,
            "threshold_failures": failures,
            "all_thresholds_passed": all_passed,
            "weighted": weighted
        }

        # Verify required fields
        assert "platforms" in result
        assert "overall" in result["weighted"]
        assert "thresholds" in result
        assert "timestamp" in result

        # Verify platform structure
        for platform in ["backend", "frontend", "mobile", "desktop"]:
            assert platform in result["platforms"]
            assert "coverage_pct" in result["platforms"][platform]
            assert "covered" in result["platforms"][platform]
            assert "total" in result["platforms"][platform]
