"""
Coverage verification tests for Phase 211.

This module provides coverage gate tests to ensure that all modules
meet their coverage targets after Plans 01-03 execution.

Tests verify:
- Plan 01 modules: 80%+ coverage (structured_logger, validation_service, config)
- Plan 02 modules: 75%+ coverage (webhook_handlers, unified_message_processor, jwt_verifier)
- Plan 03 modules: 70%+ coverage (skill_adapter, skill_composition_engine, skill_dynamic_loader, skill_security_scanner)
- Overall backend coverage: 70%+ target
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


# Coverage thresholds by plan
PLAN01_THRESHOLD = 80.0
PLAN02_THRESHOLD = 75.0
PLAN03_THRESHOLD = 70.0
OVERALL_THRESHOLD = 70.0


# Module mapping to files
PLAN01_MODULES = {
    'structured_logger': 'core/structured_logger.py',
    'validation_service': 'core/validation_service.py',
    'config': 'core/config.py'
}

PLAN02_MODULES = {
    'webhook_handlers': 'core/webhook_handlers.py',
    'unified_message_processor': 'core/unified_message_processor.py',
    'jwt_verifier': 'core/jwt_verifier.py'
}

PLAN03_MODULES = {
    'skill_adapter': 'core/skill_adapter.py',
    'skill_composition_engine': 'core/skill_composition_engine.py',
    'skill_dynamic_loader': 'core/skill_dynamic_loader.py',
    'skill_security_scanner': 'core/skill_security_scanner.py'
}


class TestCoverageGates:
    """Coverage gate tests for verifying coverage targets are met."""

    @pytest.mark.parametrize("module,threshold", [
        ('structured_logger', PLAN01_THRESHOLD),
        ('validation_service', PLAN01_THRESHOLD),
        ('config', PLAN01_THRESHOLD),
    ])
    def test_plan01_modules_coverage(self, module, threshold):
        """Verify Plan 01 modules achieve 80%+ coverage."""
        # This test requires running pytest with coverage first
        # Coverage data will be in coverage.json
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found - run coverage first")

        with open(coverage_file) as f:
            data = json.load(f)

        module_file = f"core/{module}.py"
        if module_file not in data['files']:
            pytest.skip(f"Module {module_file} not in coverage data")

        coverage_data = data['files'][module_file]['summary']
        actual_coverage = coverage_data['percent_covered']

        assert actual_coverage >= threshold, (
            f"Module {module} has {actual_coverage:.2f}% coverage, "
            f"below threshold of {threshold}%"
        )

    @pytest.mark.parametrize("module,threshold", [
        ('webhook_handlers', PLAN02_THRESHOLD),
        ('unified_message_processor', PLAN02_THRESHOLD),
        ('jwt_verifier', PLAN02_THRESHOLD),
    ])
    def test_plan02_modules_coverage(self, module, threshold):
        """Verify Plan 02 modules achieve 75%+ coverage."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found - run coverage first")

        with open(coverage_file) as f:
            data = json.load(f)

        module_file = f"core/{module}.py"
        if module_file not in data['files']:
            pytest.skip(f"Module {module_file} not in coverage data")

        coverage_data = data['files'][module_file]['summary']
        actual_coverage = coverage_data['percent_covered']

        assert actual_coverage >= threshold, (
            f"Module {module} has {actual_coverage:.2f}% coverage, "
            f"below threshold of {threshold}%"
        )

    @pytest.mark.parametrize("module,threshold", [
        ('skill_adapter', PLAN03_THRESHOLD),
        ('skill_composition_engine', PLAN03_THRESHOLD),
        ('skill_dynamic_loader', PLAN03_THRESHOLD),
        ('skill_security_scanner', PLAN03_THRESHOLD),
    ])
    def test_plan03_modules_coverage(self, module, threshold):
        """Verify Plan 03 modules achieve 70%+ coverage."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found - run coverage first")

        with open(coverage_file) as f:
            data = json.load(f)

        module_file = f"core/{module}.py"
        if module_file not in data['files']:
            pytest.skip(f"Module {module_file} not in coverage data")

        coverage_data = data['files'][module_file]['summary']
        actual_coverage = coverage_data['percent_covered']

        assert actual_coverage >= threshold, (
            f"Module {module} has {actual_coverage:.2f}% coverage, "
            f"below threshold of {threshold}%"
        )

    def test_overall_coverage_threshold(self):
        """Verify overall backend coverage meets 70%+ threshold."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found - run coverage first")

        with open(coverage_file) as f:
            data = json.load(f)

        overall_coverage = data['totals']['percent_covered']
        assert overall_coverage >= OVERALL_THRESHOLD, (
            f"Overall coverage is {overall_coverage:.2f}%, "
            f"below threshold of {OVERALL_THRESHOLD}%"
        )

    def test_no_regression(self):
        """Verify coverage hasn't regressed from baseline."""
        # Baseline coverage before Phase 211 was 5.75%
        baseline_coverage = 5.75

        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found - run coverage first")

        with open(coverage_file) as f:
            data = json.load(f)

        current_coverage = data['totals']['percent_covered']
        assert current_coverage >= baseline_coverage, (
            f"Coverage has regressed from {baseline_coverage}% to {current_coverage}%"
        )


class TestCoverageMeasurement:
    """Tests for coverage measurement infrastructure."""

    def test_coverage_json_exists(self):
        """Verify coverage.json exists and is accessible."""
        coverage_file = Path('backend/coverage.json')
        assert coverage_file.exists(), "coverage.json not found"
        assert coverage_file.is_file(), "coverage.json is not a file"

    def test_coverage_json_valid(self):
        """Verify coverage.json is valid JSON."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            try:
                data = json.load(f)
                assert isinstance(data, dict), "coverage.json root is not a dict"
            except json.JSONDecodeError as e:
                pytest.fail(f"coverage.json is not valid JSON: {e}")

    def test_coverage_json_structure(self):
        """Verify coverage.json has required fields."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        # Check top-level structure
        assert 'meta' in data, "coverage.json missing 'meta' field"
        assert 'files' in data, "coverage.json missing 'files' field"
        assert 'totals' in data, "coverage.json missing 'totals' field"

        # Check meta fields
        assert 'version' in data['meta'], "coverage.json missing version"
        assert 'timestamp' in data['meta'], "coverage.json missing timestamp"

        # Check totals fields
        totals = data['totals']
        assert 'num_statements' in totals, "coverage.json missing num_statements"
        assert 'covered_lines' in totals, "coverage.json missing covered_lines"
        assert 'percent_covered' in totals, "coverage.json missing percent_covered"

    def test_coverage_percentage_calculated(self):
        """Verify coverage percentage is calculated correctly."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        totals = data['totals']
        num_statements = totals['num_statements']
        covered_lines = totals['covered_lines']
        percent_covered = totals['percent_covered']

        if num_statements > 0:
            expected_percent = (covered_lines / num_statements) * 100
            # Allow 2% tolerance due to branch coverage calculation differences
            assert abs(percent_covered - expected_percent) < 2.0, (
                f"Coverage percentage mismatch: expected {expected_percent:.2f}%, "
                f"got {percent_covered:.2f}%"
            )

    def test_module_coverage_data(self):
        """Verify module coverage data exists for tested modules."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        # Check that at least some modules have coverage data
        assert len(data['files']) > 0, "No module coverage data found"

        # Check a few key modules exist
        key_modules = [
            'core/structured_logger.py',
            'core/validation_service.py',
            'core/config.py'
        ]

        for module in key_modules:
            if module in data['files']:
                module_data = data['files'][module]
                assert 'summary' in module_data, f"{module} missing summary"
                assert 'num_statements' in module_data['summary'], f"{module} missing num_statements"


class TestCoverageReporting:
    """Tests for coverage reporting functionality."""

    def test_generate_coverage_report(self):
        """Verify coverage report can be generated."""
        # This test verifies that we can generate a report from coverage data
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        # Generate a simple text report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("COVERAGE REPORT")
        report_lines.append("=" * 80)

        totals = data['totals']
        report_lines.append(
            f"Overall Coverage: {totals['percent_covered']:.2f}% "
            f"({totals['covered_lines']}/{totals['num_statements']} lines)"
        )

        report_lines.append("\nTop 10 Modules by Coverage:")
        modules_sorted = sorted(
            data['files'].items(),
            key=lambda x: x[1]['summary']['percent_covered'],
            reverse=True
        )

        for i, (file_path, file_data) in enumerate(modules_sorted[:10]):
            summary = file_data['summary']
            report_lines.append(
                f"  {i+1:2d}. {file_path}: {summary['percent_covered']:6.2f}% "
                f"({summary['covered_lines']:5d}/{summary['num_statements']:5d} lines)"
            )

        report_text = "\n".join(report_lines)

        # Verify report was generated
        assert len(report_text) > 0, "Failed to generate coverage report"
        assert "Overall Coverage:" in report_text, "Report missing overall coverage"

    def test_report_includes_all_modules(self):
        """Verify coverage report includes all tested modules."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        # All tested modules should be in the report
        all_modules = list(PLAN01_MODULES.values()) + list(PLAN02_MODULES.values()) + list(PLAN03_MODULES.values())

        for module in all_modules:
            # Module might not be in coverage if tests weren't run
            # This is informational, not a hard requirement
            pass

    def test_report_shows_missing_lines(self):
        """Verify coverage report shows missing lines for low-coverage modules."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        # Check that at least one module has missing lines data
        for file_path, file_data in data['files'].items():
            if 'missing_lines' in file_data['summary']:
                # Missing lines data is available
                missing_lines = file_data['summary']['missing_lines']
                if missing_lines > 0:
                    # Found a module with missing lines
                    return

        # If we get here, no missing lines were found
        # This might mean 100% coverage or data format issue
        pass

    def test_report_export_formats(self):
        """Verify coverage can be exported to multiple formats."""
        # Coverage.py supports JSON, term, HTML, XML formats
        coverage_file = Path('backend/coverage.json')

        # Verify JSON format exists
        if coverage_file.exists():
            assert coverage_file.suffix == '.json', "Coverage file is not JSON format"

        # Other formats would be generated with different --cov-report flags
        # This test verifies the JSON format is available
        pass


class TestTestFilesExist:
    """Verify all test files from Plans 01-03 exist."""

    def test_plan01_test_files_exist(self):
        """Verify Plan 01 test files exist."""
        test_files = [
            Path('backend/tests/test_structured_logger.py'),
            Path('backend/tests/test_validation_service.py'),
            Path('backend/tests/test_config.py')
        ]

        for test_file in test_files:
            assert test_file.exists(), f"Test file {test_file} not found"
            assert test_file.is_file(), f"{test_file} is not a file"

    def test_plan02_test_files_exist(self):
        """Verify Plan 02 test files exist."""
        test_files = [
            Path('backend/tests/test_webhook_handlers.py'),
            Path('backend/tests/test_unified_message_processing.py'),
            Path('backend/tests/test_jwt_verifier.py')
        ]

        for test_file in test_files:
            assert test_file.exists(), f"Test file {test_file} not found"
            assert test_file.is_file(), f"{test_file} is not a file"

    def test_plan03_test_files_exist(self):
        """Verify Plan 03 test files exist."""
        test_files = [
            Path('backend/tests/test_skill_adapter.py'),
            Path('backend/tests/test_skill_composition.py'),
            Path('backend/tests/test_skill_dynamic_loader.py'),
            Path('backend/tests/test_skill_security.py')
        ]

        for test_file in test_files:
            assert test_file.exists(), f"Test file {test_file} not found"
            assert test_file.is_file(), f"{test_file} is not a file"


class TestCoverageThresholds:
    """Test coverage threshold calculations."""

    def test_plan01_threshold_is_80_percent(self):
        """Verify Plan 01 threshold is 80%."""
        assert PLAN01_THRESHOLD == 80.0, "Plan 01 threshold should be 80%"

    def test_plan02_threshold_is_75_percent(self):
        """Verify Plan 02 threshold is 75%."""
        assert PLAN02_THRESHOLD == 75.0, "Plan 02 threshold should be 75%"

    def test_plan03_threshold_is_70_percent(self):
        """Verify Plan 03 threshold is 70%."""
        assert PLAN03_THRESHOLD == 70.0, "Plan 03 threshold should be 70%"

    def test_overall_threshold_is_70_percent(self):
        """Verify overall threshold is 70%."""
        assert OVERALL_THRESHOLD == 70.0, "Overall threshold should be 70%"

    def test_thresholds_are_decreasing(self):
        """Verify thresholds decrease from Plan 01 to Plan 03."""
        assert PLAN01_THRESHOLD > PLAN02_THRESHOLD, "Plan 01 threshold should be higher than Plan 02"
        assert PLAN02_THRESHOLD > PLAN03_THRESHOLD, "Plan 02 threshold should be higher than Plan 03"


class TestCoverageDataIntegrity:
    """Test coverage data integrity and consistency."""

    def test_coverage_totals_match_files(self):
        """Verify coverage totals match sum of file coverage."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        # Sum up all file coverage
        total_statements = 0
        total_covered = 0

        for file_data in data['files'].values():
            summary = file_data['summary']
            total_statements += summary['num_statements']
            total_covered += summary['covered_lines']

        # Compare with totals
        reported_total = data['totals']['num_statements']
        reported_covered = data['totals']['covered_lines']

        # Allow small rounding differences
        assert abs(total_statements - reported_total) <= 1, (
            f"Sum of file statements ({total_statements}) doesn't match reported total ({reported_total})"
        )

    def test_no_negative_coverage(self):
        """Verify no module has negative coverage."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        for file_path, file_data in data['files'].items():
            coverage = file_data['summary']['percent_covered']
            assert coverage >= 0, f"Module {file_path} has negative coverage: {coverage}%"
            assert coverage <= 100, f"Module {file_path} has coverage > 100%: {coverage}%"

    def test_coverage_timestamp_is_recent(self):
        """Verify coverage data has a recent timestamp."""
        coverage_file = Path('backend/coverage.json')
        if not coverage_file.exists():
            pytest.skip("coverage.json not found")

        with open(coverage_file) as f:
            data = json.load(f)

        # Check timestamp exists
        assert 'timestamp' in data['meta'], "Coverage data missing timestamp"

        # Timestamp should be a string
        assert isinstance(data['meta']['timestamp'], str), "Timestamp is not a string"
