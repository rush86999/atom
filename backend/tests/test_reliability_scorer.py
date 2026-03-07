"""
Unit tests for reliability_scorer.py

Tests cross-platform reliability calculation, platform aggregation,
JSON/database integration, and markdown report generation.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.tests.scripts.reliability_scorer import (
    aggregate_platform_scores,
    calculate_platform_score,
    calculate_reliability_score,
    calculate_score_from_db,
    compare_scores,
    generate_markdown_report,
    get_least_reliable_tests,
    load_flaky_data,
    load_from_database,
)


class TestCalculateReliabilityScore:
    """Test reliability score calculation for individual tests."""

    def test_perfect_reliability(self):
        """Test reliability score for perfect test (0% flaky rate)."""
        score = calculate_reliability_score(0.0)
        assert score == 1.0

    def test_moderate_reliability(self):
        """Test reliability score for moderately flaky test (30% flaky rate)."""
        score = calculate_reliability_score(0.3)
        assert score == 0.7

    def test_low_reliability(self):
        """Test reliability score for unreliable test (70% flaky rate)."""
        score = calculate_reliability_score(0.7)
        assert score == 0.3

    def test_zero_reliability(self):
        """Test reliability score for completely unreliable test (100% flaky rate)."""
        score = calculate_reliability_score(1.0)
        assert score == 0.0

    def test_none_flaky_rate(self):
        """Test reliability score when flaky_rate is None."""
        score = calculate_reliability_score(None)
        assert score == 1.0  # No data = assume reliable

    def test_negative_flaky_rate_clamped(self):
        """Test reliability score clamps negative flaky_rate to 0.0."""
        score = calculate_reliability_score(-0.5)
        assert score == 1.0  # Clamped to 0.0 flaky_rate

    def test_flaky_rate_greater_than_one_clamped(self):
        """Test reliability score clamps flaky_rate > 1.0 to 1.0."""
        score = calculate_reliability_score(1.5)
        assert score == 0.0  # Clamped to 1.0 flaky_rate

    def test_rounding_to_three_decimals(self):
        """Test reliability score is rounded to 3 decimal places."""
        score = calculate_reliability_score(0.3333)
        assert score == 0.667


class TestCalculatePlatformScore:
    """Test platform reliability score calculation."""

    def test_empty_platform_returns_perfect_score(self):
        """Test empty platform returns perfect reliability (1.0)."""
        score = calculate_platform_score([], "backend")
        assert score == 1.0

    def test_single_test_platform(self):
        """Test platform with single flaky test."""
        flaky_tests = [{"flaky_rate": 0.3}]
        score = calculate_platform_score(flaky_tests, "backend")
        assert score == 0.7

    def test_multiple_tests_platform(self):
        """Test platform with multiple flaky tests."""
        flaky_tests = [
            {"flaky_rate": 0.1},
            {"flaky_rate": 0.3},
            {"flaky_rate": 0.5}
        ]
        # Reliabilities: 0.9, 0.7, 0.5 = average 0.7
        score = calculate_platform_score(flaky_tests, "backend")
        assert score == 0.7

    def test_missing_flaky_rate_treated_as_zero(self):
        """Test missing flaky_rate treated as 0.0 (perfect reliability)."""
        flaky_tests = [{"flaky_rate": 0.5}, {}]
        # Reliabilities: 0.5, 1.0 = average 0.75
        score = calculate_platform_score(flaky_tests, "backend")
        assert score == 0.75


class TestAggregatePlatformScores:
    """Test cross-platform score aggregation with Phase 146 weights."""

    def test_weighted_aggregation_all_platforms(self):
        """Test weighted aggregation across all platforms."""
        platform_data = {
            "backend": [{"flaky_rate": 0.1}],    # 0.9 reliability
            "frontend": [{"flaky_rate": 0.2}],  # 0.8 reliability
            "mobile": [{"flaky_rate": 0.3}],    # 0.7 reliability
            "desktop": [{"flaky_rate": 0.0}]    # 1.0 reliability
        }

        result = aggregate_platform_scores(platform_data)

        # Weighted: 0.9*0.35 + 0.8*0.40 + 0.7*0.15 + 1.0*0.10
        # = 0.315 + 0.320 + 0.105 + 0.100 = 0.84
        assert result['overall_score'] == 0.84
        assert result['platform_scores']['backend'] == 0.9
        assert result['platform_scores']['frontend'] == 0.8
        assert result['platform_scores']['mobile'] == 0.7
        assert result['platform_scores']['desktop'] == 1.0

    def test_phase_146_weights(self):
        """Test Phase 146 weights are correct (35/40/15/10)."""
        platform_data = {
            "backend": [],
            "frontend": [],
            "mobile": [],
            "desktop": []
        }

        result = aggregate_platform_scores(platform_data)

        assert result['weights_used']['backend'] == 0.35
        assert result['weights_used']['frontend'] == 0.40
        assert result['weights_used']['mobile'] == 0.15
        assert result['weights_used']['desktop'] == 0.10

    def test_empty_platforms_return_perfect_score(self):
        """Test all platforms empty returns perfect reliability (1.0)."""
        platform_data = {
            "backend": [],
            "frontend": [],
            "mobile": [],
            "desktop": []
        }

        result = aggregate_platform_scores(platform_data)

        assert result['overall_score'] == 1.0


class TestLoadFlakyData:
    """Test loading flaky test data from JSON files."""

    def test_load_from_dict_format(self, tmp_path):
        """Test loading from dict format with 'flaky_tests' key."""
        json_file = tmp_path / "flaky_tests.json"
        data = {
            "flaky_tests": [
                {"test_path": "test_foo.py::test_bar", "flaky_rate": 0.3}
            ],
            "summary": {"total": 1}
        }
        json_file.write_text(json.dumps(data))

        tests = load_flaky_data(str(json_file), "backend")

        assert len(tests) == 1
        assert tests[0]['test_path'] == "test_foo.py::test_bar"
        assert tests[0]['flaky_rate'] == 0.3
        assert tests[0]['platform'] == "backend"

    def test_load_from_list_format(self, tmp_path):
        """Test loading from list format (direct array)."""
        json_file = tmp_path / "flaky_tests.json"
        data = [
            {"test_path": "test_foo.py::test_bar", "flaky_rate": 0.3}
        ]
        json_file.write_text(json.dumps(data))

        tests = load_flaky_data(str(json_file), "frontend")

        assert len(tests) == 1
        assert tests[0]['platform'] == "frontend"

    def test_load_nonexistent_file_returns_empty(self):
        """Test loading nonexistent file returns empty list."""
        tests = load_flaky_data("/nonexistent/file.json", "backend")
        assert tests == []

    def test_load_invalid_json_returns_empty(self, tmp_path):
        """Test loading invalid JSON returns empty list."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("invalid json {{{")

        tests = load_flaky_data(str(json_file), "backend")
        assert tests == []


class TestLoadFromDatabase:
    """Test loading flaky test data from SQLite database."""

    def test_load_from_database(self, tmp_path):
        """Test loading flaky tests from database."""
        db_path = tmp_path / "flaky_tests.db"

        # Create test database
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE flaky_tests (
                id INTEGER PRIMARY KEY,
                test_path TEXT,
                platform TEXT,
                flaky_rate REAL,
                failure_history TEXT
            )
        """)
        conn.execute("""
            INSERT INTO flaky_tests (test_path, platform, flaky_rate, failure_history)
            VALUES ('test_foo.py::test_bar', 'backend', 0.3, '[]')
        """)
        conn.commit()
        conn.close()

        tests = load_from_database(db_path)

        assert len(tests) == 1
        assert tests[0]['test_path'] == 'test_foo.py::test_bar'
        assert tests[0]['flaky_rate'] == 0.3

    def test_load_with_platform_filter(self, tmp_path):
        """Test loading with platform filter."""
        db_path = tmp_path / "flaky_tests.db"

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE flaky_tests (
                id INTEGER PRIMARY KEY,
                test_path TEXT,
                platform TEXT,
                flaky_rate REAL,
                failure_history TEXT
            )
        """)
        conn.execute("""
            INSERT INTO flaky_tests (test_path, platform, flaky_rate, failure_history)
            VALUES ('test_backend.py::test_foo', 'backend', 0.3, '[]')
        """)
        conn.execute("""
            INSERT INTO flaky_tests (test_path, platform, flaky_rate, failure_history)
            VALUES ('test_frontend.test.tsx', 'frontend', 0.2, '[]')
        """)
        conn.commit()
        conn.close()

        backend_tests = load_from_database(db_path, platform="backend")

        assert len(backend_tests) == 1
        assert backend_tests[0]['platform'] == 'backend'

    def test_load_nonexistent_database(self):
        """Test loading nonexistent database returns empty list."""
        tests = load_from_database(Path("/nonexistent/flaky_tests.db"))
        assert tests == []


class TestCalculateScoreFromDatabase:
    """Test calculate_score_from_db function."""

    def test_calculate_score_from_database(self, tmp_path):
        """Test calculating reliability score from database."""
        db_path = tmp_path / "flaky_tests.db"

        # Create test database
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE flaky_tests (
                id INTEGER PRIMARY KEY,
                test_path TEXT,
                platform TEXT,
                flaky_rate REAL,
                failure_history TEXT
            )
        """)
        conn.execute("""
            INSERT INTO flaky_tests (test_path, platform, flaky_rate, failure_history)
            VALUES ('test_backend.py::test_foo', 'backend', 0.3, '[]')
        """)
        conn.execute("""
            INSERT INTO flaky_tests (test_path, platform, flaky_rate, failure_history)
            VALUES ('test_frontend.test.tsx', 'frontend', 0.2, '[]')
        """)
        conn.commit()
        conn.close()

        result = calculate_score_from_db(db_path)

        assert result['data_source'] == 'database'
        assert 'overall_score' in result
        assert result['total_tests_quarantined'] == 2
        assert result['platform_breakdown']['backend'] == 1
        assert result['platform_breakdown']['frontend'] == 1


class TestCompareScores:
    """Test score comparison functionality."""

    def test_compare_with_previous_score(self, tmp_path):
        """Test comparing current score with previous score."""
        previous_file = tmp_path / "previous.json"
        previous_data = {"overall_score": 0.80}
        previous_file.write_text(json.dumps(previous_data))

        current_data = {"overall_score": 0.85}

        delta = compare_scores(current_data, str(previous_file))

        assert delta == "+0.050"

    def test_compare_with_regression(self, tmp_path):
        """Test comparing shows regression."""
        previous_file = tmp_path / "previous.json"
        previous_data = {"overall_score": 0.85}
        previous_file.write_text(json.dumps(previous_data))

        current_data = {"overall_score": 0.82}

        delta = compare_scores(current_data, str(previous_file))

        assert delta == "-0.030"

    def test_compare_with_no_change(self, tmp_path):
        """Test comparing shows no change."""
        previous_file = tmp_path / "previous.json"
        previous_data = {"overall_score": 0.80}
        previous_file.write_text(json.dumps(previous_data))

        current_data = {"overall_score": 0.80}

        delta = compare_scores(current_data, str(previous_file))

        assert delta == "0.000 (no change)"

    def test_compare_with_missing_previous(self, tmp_path):
        """Test comparing when previous file doesn't exist."""
        current_data = {"overall_score": 0.80}

        delta = compare_scores(current_data, "/nonexistent/previous.json")

        assert "no previous data" in delta.lower()

    def test_compare_with_invalid_previous(self, tmp_path):
        """Test comparing when previous file is invalid."""
        previous_file = tmp_path / "invalid.json"
        previous_file.write_text("invalid json")

        current_data = {"overall_score": 0.80}

        delta = compare_scores(current_data, str(previous_file))

        assert "error reading" in delta.lower()


class TestGetLeastReliableTests:
    """Test least reliable tests extraction."""

    def test_get_least_reliable_tests(self):
        """Test extracting least reliable tests."""
        all_tests = [
            {"test_path": "test_a.py::test_foo", "platform": "backend", "flaky_rate": 0.1},
            {"test_path": "test_b.py::test_bar", "platform": "frontend", "flaky_rate": 0.7},
            {"test_path": "test_c.py::test_baz", "platform": "mobile", "flaky_rate": 0.5},
            {"test_path": "test_d.py::test_qux", "platform": "desktop", "flaky_rate": 0.9}
        ]

        least_reliable = get_least_reliable_tests(all_tests, limit=2)

        assert len(least_reliable) == 2
        # Should be sorted by flaky_rate DESC
        assert least_reliable[0]['test_path'] == "test_d.py::test_qux"
        assert least_reliable[0]['flaky_rate'] == 0.9
        assert least_reliable[0]['reliability'] == 0.1
        assert least_reliable[1]['test_path'] == "test_b.py::test_bar"
        assert least_reliable[1]['flaky_rate'] == 0.7

    def test_empty_tests_list(self):
        """Test with empty tests list."""
        least_reliable = get_least_reliable_tests([], limit=10)
        assert least_reliable == []

    def test_limit_greater_than_available(self):
        """Test when limit exceeds available tests."""
        all_tests = [
            {"test_path": "test_a.py::test_foo", "platform": "backend", "flaky_rate": 0.5}
        ]

        least_reliable = get_least_reliable_tests(all_tests, limit=10)

        assert len(least_reliable) == 1


class TestGenerateMarkdownReport:
    """Test markdown report generation."""

    def test_generate_markdown_report(self):
        """Test generating markdown report."""
        reliability_data = {
            "scan_date": "2026-03-07T12:00:00",
            "overall_score": 0.87,
            "score_change": "+0.03",
            "platform_scores": {
                "backend": 0.92,
                "frontend": 0.85,
                "mobile": 0.78,
                "desktop": 0.95
            },
            "weights_used": {
                "backend": 0.35,
                "frontend": 0.40,
                "mobile": 0.15,
                "desktop": 0.10
            },
            "total_tests_quarantined": 15,
            "platform_breakdown": {
                "backend": 5,
                "frontend": 7,
                "mobile": 2,
                "desktop": 1
            },
            "least_reliable_tests": [
                {
                    "test_path": "tests/test_foo.py::test_bar",
                    "platform": "frontend",
                    "flaky_rate": 0.5,
                    "reliability": 0.5
                }
            ],
            "data_source": "database",
            "metadata": {
                "detection_runs": 10,
                "flaky_threshold": 0.3,
                "min_runs_for_classification": 3
            }
        }

        report = generate_markdown_report(reliability_data)

        assert "# Test Reliability Report" in report
        assert "0.87" in report
        assert "+0.03" in report
        assert "BACKEND" in report
        assert "0.92" in report
        assert "Tests Quarantined" in report
        assert "Least Reliable Tests" in report
        assert "test_foo.py::test_bar" in report
        assert "Data source: database" in report

    def test_markdown_report_without_optional_fields(self):
        """Test generating markdown report without optional fields."""
        reliability_data = {
            "overall_score": 0.80,
            "platform_scores": {
                "backend": 0.8,
                "frontend": 0.8,
                "mobile": 0.8,
                "desktop": 0.8
            },
            "weights_used": {
                "backend": 0.35,
                "frontend": 0.40,
                "mobile": 0.15,
                "desktop": 0.10
            },
            "data_source": "json_files"
        }

        report = generate_markdown_report(reliability_data)

        assert "# Test Reliability Report" in report
        assert "0.80" in report
        assert "BACKEND" in report
        assert "Data source: json_files" in report


class TestJsonSchemaValidation:
    """Test JSON schema validation for reliability score output."""

    def test_json_output_schema(self, tmp_path):
        """Test JSON output matches expected schema."""
        output_file = tmp_path / "reliability_score.json"

        # Import main to run CLI
        from backend.tests.scripts import reliability_scorer

        # Create test JSON files
        backend_file = tmp_path / "backend_flaky.json"
        backend_file.write_text(json.dumps({
            "flaky_tests": [{"test_path": "test_foo.py::test_bar", "flaky_rate": 0.3}],
            "summary": {"total": 1}
        }))

        # Run CLI
        with patch('sys.argv', [
            'reliability_scorer.py',
            '--backend-flaky', str(backend_file),
            '--output', str(output_file)
        ]):
            reliability_scorer.main()

        # Verify output file exists and has correct schema
        assert output_file.exists()

        output_data = json.loads(output_file.read_text())

        # Required top-level fields
        assert 'overall_score' in output_data
        assert 'platform_scores' in output_data
        assert 'weights_used' in output_data
        assert 'data_source' in output_data
        assert 'scan_date' in output_data

        # Platform scores must have all platforms
        assert 'backend' in output_data['platform_scores']
        assert 'frontend' in output_data['platform_scores']
        assert 'mobile' in output_data['platform_scores']
        assert 'desktop' in output_data['platform_scores']

        # Weights must match Phase 146
        assert output_data['weights_used']['backend'] == 0.35
        assert output_data['weights_used']['frontend'] == 0.40
        assert output_data['weights_used']['mobile'] == 0.15
        assert output_data['weights_used']['desktop'] == 0.10
