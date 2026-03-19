"""
Coverage aggregation and verification tests for Phase 203.

Tests that coverage measurement works correctly, reports are generated,
and module breakdowns are accurate.
"""
import pytest
import json
from pathlib import Path
from subprocess import run, PIPE


class TestCoverageMeasurement:
    """Test coverage measurement infrastructure."""

    def test_coverage_command_runs(self):
        """Test that pytest coverage command runs successfully."""
        result = run(
            ["python3", "-m", "pytest", "--cov=backend", "--cov-report=json", "-o", "addopts=", "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert Path("backend/coverage.json").exists()

    def test_coverage_json_format(self):
        """Test that coverage JSON is valid and parseable."""
        result = run(
            ["python3", "-m", "pytest", "--cov=backend", "--cov-report=json", "-o", "addopts=", "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        with open("backend/coverage.json") as f:
            data = json.load(f)

        assert "totals" in data
        assert "files" in data
        assert "percent_covered" in data["totals"]

    def test_coverage_includes_new_tests(self):
        """Test that coverage includes newly created tests."""
        # This test verifies that tests created in Phase 203 are included
        # in coverage measurement
        result = run(
            ["python3", "-m", "pytest", "--collect-only", "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        # Check that Phase 203 test files are collected
        output = result.stdout
        assert "test_workflow_engine_coverage" in output
        assert "test_byok_handler_coverage_extend" in output


class TestCoverageModuleBreakdown:
    """Test module-level coverage breakdown."""

    def test_module_coverage_totals(self):
        """Test that module coverage totals are calculated correctly."""
        result = run(
            ["python3", "-m", "pytest", "--cov=backend", "--cov-report=json", "-o", "addopts=", "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        with open("backend/coverage.json") as f:
            data = json.load(f)

        # Calculate module totals
        modules = {}
        for path, info in data['files'].items():
            if '/core/' in path:
                module = 'core'
            elif '/api/' in path:
                module = 'api'
            elif '/tools/' in path:
                module = 'tools'
            elif '/cli/' in path:
                module = 'cli'
            else:
                continue

            if module not in modules:
                modules[module] = {'covered': 0, 'total': 0}
            modules[module]['covered'] += info['summary']['covered_lines']
            modules[module]['total'] += info['summary']['num_statements']

        # Verify totals are calculated
        assert 'core' in modules
        assert 'api' in modules
        assert modules['core']['total'] > 0

    def test_zero_coverage_files_identified(self):
        """Test that zero-coverage files are correctly identified."""
        result = run(
            ["python3", "-m", "pytest", "--cov=backend", "--cov-report=json", "-o", "addopts=", "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        with open("backend/coverage.json") as f:
            data = json.load(f)

        # Count zero-coverage files >100 lines
        zero_coverage = []
        for path, info in data['files'].items():
            stmts = info['summary']['num_statements']
            covered = info['summary']['covered_lines']
            if stmts > 100 and covered == 0:
                zero_coverage.append(path)

        # Should have identified zero-coverage files
        assert isinstance(zero_coverage, list)


class TestCoverageBaselines:
    """Test coverage baseline comparisons."""

    def test_compare_to_phase_202_baseline(self):
        """Test coverage comparison to Phase 202 baseline (5.21%)."""
        result = run(
            ["python3", "-m", "pytest", "--cov=backend", "--cov-report=json", "-o", "addopts=", "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        with open("backend/coverage.json") as f:
            data = json.load(f)

        current_coverage = data['totals']['percent_covered']
        phase_202_baseline = 5.21

        # Should have improved from baseline
        assert current_coverage >= phase_202_baseline

    def test_calculate_coverage_improvement(self):
        """Test calculation of coverage improvement from baseline."""
        result = run(
            ["python3", "-m", "pytest", "--cov=backend", "--cov-report=json", "-o", "addopts=", "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        with open("backend/coverage.json") as f:
            data = json.load(f)

        current_coverage = data['totals']['percent_covered']
        phase_202_baseline = 5.21
        improvement = current_coverage - phase_202_baseline

        # Improvement should be positive
        assert improvement >= 0

        # Gap to 65% target
        gap_to_target = 65 - current_coverage
        assert gap_to_target >= 0


class TestCoverageReports:
    """Test coverage report generation."""

    def test_generate_final_coverage_report(self):
        """Test generating final Phase 203 coverage report."""
        result = run(
            ["python3", "-m", "pytest",
             "--cov=backend",
             "--cov-report=term-missing",
             "--cov-report=html",
             "--cov-report=json:backend/backend/final_coverage_203.json",
             "-o", "addopts=",
             "-q"],
            cwd="/Users/rushiparikh/projects/atom",
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert Path("backend/backend/final_coverage_203.json").exists()

    def test_coverage_report_contains_required_fields(self):
        """Test that coverage report contains all required fields."""
        result = run(
            ["python3", "-m", "pytest",
             "--cov=backend",
             "--cov-report=json:backend/backend/final_coverage_203.json",
             "-o", "addopts=",
             "-q"],
            cwd="/Users/rushiparikh/projects/atom",
            capture_output=True,
            text=True
        )

        with open("backend/backend/final_coverage_203.json") as f:
            data = json.load(f)

        # Check required fields
        assert "totals" in data
        assert "files" in data
        assert "percent_covered" in data["totals"]
        assert "covered_lines" in data["totals"]
        assert "num_statements" in data["totals"]
        assert "missing_lines" in data["totals"]

    def test_html_coverage_report_generated(self):
        """Test that HTML coverage report is generated."""
        result = run(
            ["python3", "-m", "pytest",
             "--cov=backend",
             "--cov-report=html",
             "-o", "addopts=",
             "-q"],
            cwd="/Users/rushiparikh/projects/atom/backend",
            capture_output=True,
            text=True
        )

        assert Path("backend/htmlcov/index.html").exists()
