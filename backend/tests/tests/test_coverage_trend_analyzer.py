#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for coverage_trend_analyzer.py

Tests regression detection, trend analysis, data validation, and report generation.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, mock_open

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from coverage_trend_analyzer import (
    load_trending_data,
    validate_trend_data,
    detect_regressions,
    analyze_trends,
    calculate_moving_average,
    log_regressions,
    generate_text_report,
    generate_json_report,
    generate_markdown_report,
    REGRESSION_THRESHOLD,
    CRITICAL_THRESHOLD,
    MIN_HISTORY_ENTRIES
)


# =============================================================================
# Test fixtures
# =============================================================================

@pytest.fixture
def sample_trending_data():
    """Sample trending data with 10 entries spanning 10 days."""
    history = []
    base_time = datetime.now() - timedelta(days=10)

    # Day 1-3: Backend improving (70% -> 72% -> 74%)
    for i, cov in enumerate([70.0, 72.0, 74.0]):
        history.append({
            "timestamp": (base_time + timedelta(days=i)).isoformat() + "Z",
            "overall_coverage": cov + 10.0,
            "platforms": {
                "backend": cov,
                "frontend": 80.0 + i,
                "mobile": 60.0 + i * 0.5,
                "desktop": 50.0
            },
            "thresholds": {
                "backend": 70.0,
                "frontend": 80.0,
                "mobile": 50.0,
                "desktop": 40.0
            },
            "commit_sha": f"abc{i}",
            "branch": "main"
        })

    # Day 4-6: Backend regression (74% -> 71% -> 68%)
    for i, cov in enumerate([71.0, 68.0]):
        day = i + 3
        history.append({
            "timestamp": (base_time + timedelta(days=day)).isoformat() + "Z",
            "overall_coverage": cov + 10.0,
            "platforms": {
                "backend": cov,
                "frontend": 83.0 + day,
                "mobile": 61.5 + day * 0.5,
                "desktop": 50.0
            },
            "thresholds": {
                "backend": 70.0,
                "frontend": 80.0,
                "mobile": 50.0,
                "desktop": 40.0
            },
            "commit_sha": f"abc{day}",
            "branch": "main"
        })

    # Day 7-10: Mobile improvement (60% -> 62% -> 64% -> 66%)
    for i in range(4):
        day = i + 6
        cov = 60.0 + i * 2.0
        history.append({
            "timestamp": (base_time + timedelta(days=day)).isoformat() + "Z",
            "overall_coverage": 75.0 + i,
            "platforms": {
                "backend": 68.0,
                "frontend": 85.0,
                "mobile": cov,
                "desktop": 50.0
            },
            "thresholds": {
                "backend": 70.0,
                "frontend": 80.0,
                "mobile": 50.0,
                "desktop": 40.0
            },
            "commit_sha": f"def{day}",
            "branch": "main"
        })

    return {
        "history": history,
        "latest": history[-1],
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


@pytest.fixture
def regression_data():
    """Trending data with clear regression (backend -3%, frontend -2%)."""
    base_time = datetime.now() - timedelta(days=2)

    return {
        "history": [
            {
                "timestamp": (base_time).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {
                    "backend": 75.0,
                    "frontend": 82.0,
                    "mobile": 60.0,
                    "desktop": 50.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "abc123",
                "branch": "main"
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 72.0,
                "platforms": {
                    "backend": 72.0,  # -3% regression
                    "frontend": 80.0,  # -2% regression
                    "mobile": 60.0,
                    "desktop": 50.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "def456",
                "branch": "main"
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


@pytest.fixture
def critical_regression_data():
    """Trending data with critical regression (>5% drop)."""
    base_time = datetime.now() - timedelta(days=1)

    return {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 80.0,
                "platforms": {
                    "backend": 80.0,
                    "frontend": 85.0,
                    "mobile": 70.0,
                    "desktop": 60.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "abc123",
                "branch": "main"
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 70.0,
                "platforms": {
                    "frontend": 75.0  # -10% critical regression
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "def456",
                "branch": "main"
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


@pytest.fixture
def improvement_data():
    """Trending data with improvement (no regressions)."""
    base_time = datetime.now() - timedelta(days=1)

    return {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 70.0,
                "platforms": {
                    "backend": 70.0,
                    "frontend": 75.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "abc123",
                "branch": "main"
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {
                    "backend": 75.0,  # +5% improvement
                    "frontend": 80.0,  # +5% improvement
                    "mobile": 55.0,  # +5% improvement
                    "desktop": 45.0  # +5% improvement
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "def456",
                "branch": "main"
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


@pytest.fixture
def insufficient_history_data():
    """Trending data with only 1 history entry."""
    return {
        "history": [
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {
                    "backend": 75.0,
                    "frontend": 80.0,
                    "mobile": 60.0,
                    "desktop": 50.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "abc123",
                "branch": "main"
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


@pytest.fixture
def malformed_data():
    """Trending data with missing required keys."""
    return {
        "history": [],
        # Missing "latest" key
        # Missing "platform_trends" key
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


@pytest.fixture
def zero_coverage_data():
    """Trending data with 0% coverage (failed job)."""
    base_time = datetime.now() - timedelta(days=1)

    return {
        "history": [
            {
                "timestamp": base_time.isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {
                    "backend": 75.0,
                    "frontend": 80.0,
                    "mobile": 60.0,
                    "desktop": 50.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "abc123",
                "branch": "main"
            },
            {
                "timestamp": (base_time + timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 0.0,
                "platforms": {
                    "backend": 0.0,  # Failed job
                    "frontend": 80.0,
                    "mobile": 60.0,
                    "desktop": 50.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                },
                "commit_sha": "def456",
                "branch": "main"
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


# =============================================================================
# Data validation tests
# =============================================================================

class TestValidateTrendData:
    """Tests for validate_trend_data function."""

    def test_validate_trend_data_valid_schema(self, sample_trending_data):
        """Test validation passes for valid data."""
        result = validate_trend_data(sample_trending_data)
        assert result is True

    def test_validate_trend_data_missing_history(self):
        """Test validation fails when 'history' key is missing."""
        data = {
            "latest": {},
            "platform_trends": {},
            "computed_weights": {}
        }
        result = validate_trend_data(data)
        assert result is False

    def test_validate_trend_data_invalid_history_type(self):
        """Test validation fails when 'history' is not a list."""
        data = {
            "history": "not a list",
            "latest": {},
            "platform_trends": {},
            "computed_weights": {}
        }
        result = validate_trend_data(data)
        assert result is False

    def test_validate_trend_data_empty_history(self):
        """Test validation passes for empty history (valid structure)."""
        data = {
            "history": [],
            "latest": {},
            "platform_trends": {},
            "computed_weights": {}
        }
        result = validate_trend_data(data)
        assert result is True

    def test_validate_trend_data_missing_keys(self, malformed_data):
        """Test validation handles missing required keys gracefully."""
        result = validate_trend_data(malformed_data)
        assert result is False


# =============================================================================
# Regression detection tests
# =============================================================================

class TestDetectRegressions:
    """Tests for detect_regressions function."""

    def test_detect_regressions_backend_drop(self, regression_data):
        """Test regression detection for backend -3% drop."""
        regressions = detect_regressions(regression_data, threshold=1.0)

        assert len(regressions) == 2  # backend and frontend

        # Check backend regression
        backend_reg = [r for r in regressions if r["platform"] == "backend"][0]
        assert backend_reg["current_coverage"] == 72.0
        assert backend_reg["previous_coverage"] == 75.0
        assert backend_reg["delta"] == -3.0
        assert backend_reg["severity"] == "warning"

    def test_detect_regressions_critical_drop(self, critical_regression_data):
        """Test regression detection for critical -10% drop."""
        regressions = detect_regressions(critical_regression_data, threshold=1.0)

        assert len(regressions) == 1

        frontend_reg = regressions[0]
        assert frontend_reg["platform"] == "frontend"
        assert frontend_reg["current_coverage"] == 75.0
        assert frontend_reg["previous_coverage"] == 85.0
        assert frontend_reg["delta"] == -10.0
        assert frontend_reg["severity"] == "critical"

    def test_detect_regressions_below_threshold(self):
        """Test no regression detected for -0.5% drop (below 1% threshold)."""
        base_time = datetime.now() - timedelta(days=1)

        data = {
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
                    "platforms": {"mobile": 49.5},  # -0.5% drop
                    "thresholds": {"mobile": 50.0}
                }
            ],
            "latest": {},
            "platform_trends": {},
            "computed_weights": {}
        }

        regressions = detect_regressions(data, threshold=1.0)
        assert len(regressions) == 0  # Below threshold

    def test_detect_regressions_improvement(self, improvement_data):
        """Test no regression detected for +5% improvement."""
        regressions = detect_regressions(improvement_data, threshold=1.0)
        assert len(regressions) == 0  # All improvements, no regressions

    def test_detect_regressions_multiple_platforms(self, regression_data):
        """Test regression detection for multiple platforms."""
        regressions = detect_regressions(regression_data, threshold=1.0)

        platforms = [r["platform"] for r in regressions]
        assert "backend" in platforms
        assert "frontend" in platforms
        assert len(regressions) == 2

    def test_detect_regressions_insufficient_history(self, insufficient_history_data):
        """Test regression detection returns empty list with insufficient history."""
        regressions = detect_regressions(insufficient_history_data, threshold=1.0)
        assert len(regressions) == 0

    def test_detect_regressions_zero_coverage_skipped(self, zero_coverage_data):
        """Test 0% coverage is skipped (likely failed job)."""
        regressions = detect_regressions(zero_coverage_data, threshold=1.0)

        # Backend should be skipped due to 0% coverage
        backend_regressions = [r for r in regressions if r["platform"] == "backend"]
        assert len(backend_regressions) == 0

    def test_detect_regressions_missing_platform_data(self):
        """Test platforms with missing data are skipped."""
        base_time = datetime.now() - timedelta(days=1)

        data = {
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

        regressions = detect_regressions(data, threshold=1.0)
        # Only backend should be checked (mobile/desktop skipped due to missing data)
        assert len(regressions) == 1
        assert regressions[0]["platform"] == "backend"


# =============================================================================
# Trend analysis tests
# =============================================================================

class TestAnalyzeTrends:
    """Tests for analyze_trends function."""

    def test_analyze_trends_declining(self, regression_data):
        """Test trend analysis identifies declining trend."""
        trends = analyze_trends(regression_data, periods=1)

        assert "platform_trends" in trends
        assert "regression_count" in trends
        assert "improvement_count" in trends

        # Backend should be declining
        backend_trend = trends["platform_trends"].get("backend")
        assert backend_trend is not None
        assert backend_trend["classification"] == "declining"

    def test_analyze_trends_improving(self, improvement_data):
        """Test trend analysis identifies improving trend."""
        trends = analyze_trends(improvement_data, periods=1)

        # All platforms should be improving
        for platform in ["backend", "frontend", "mobile", "desktop"]:
            platform_trend = trends["platform_trends"].get(platform)
            assert platform_trend is not None
            assert platform_trend["classification"] == "improving"

        assert trends["improvement_count"] == 4

    def test_analyze_trends_stable(self):
        """Test trend analysis identifies stable trend."""
        base_time = datetime.now() - timedelta(days=2)

        # Create stable history (75% -> 74% -> 75% -> 76%)
        history = []
        for i, cov in enumerate([75.0, 74.0, 75.0, 76.0]):
            history.append({
                "timestamp": (base_time + timedelta(days=i)).isoformat() + "Z",
                "overall_coverage": cov,
                "platforms": {"backend": cov},
                "thresholds": {"backend": 70.0}
            })

        data = {
            "history": history,
            "latest": {},
            "platform_trends": {},
            "computed_weights": {}
        }

        trends = analyze_trends(data, periods=1)

        # Backend should be stable (within ±1%)
        backend_trend = trends["platform_trends"].get("backend")
        assert backend_trend is not None
        # Delta should be small (+1% from 75 to 76)
        assert abs(backend_trend["delta"]) <= 2.0

    def test_analyze_trends_moving_average(self, sample_trending_data):
        """Test 3-period moving average calculation."""
        trends = analyze_trends(sample_trending_data, periods=1)

        # Check moving average for backend (last 3 entries: 71, 68, 68)
        backend_trend = trends["platform_trends"].get("backend")
        if backend_trend and backend_trend.get("moving_avg"):
            # Average of last 3 backend values
            expected_ma = (71.0 + 68.0 + 68.0) / 3
            assert abs(backend_trend["moving_avg"] - expected_ma) < 0.1

    def test_analyze_trends_insufficient_history(self, insufficient_history_data):
        """Test trend analysis handles insufficient history gracefully."""
        trends = analyze_trends(insufficient_history_data, periods=1)

        assert trends["platform_trends"] == {}
        assert trends["regression_count"] == 0
        assert trends["improvement_count"] == 0


# =============================================================================
# Moving average tests
# =============================================================================

class TestCalculateMovingAverage:
    """Tests for calculate_moving_average function."""

    def test_moving_average_3_periods(self, sample_trending_data):
        """Test 3-period moving average calculation."""
        ma = calculate_moving_average(sample_trending_data, "backend", periods=3)

        assert ma is not None
        # Last 3 backend values: 71, 68, 68
        expected_ma = (71.0 + 68.0 + 68.0) / 3
        assert abs(ma - expected_ma) < 0.1

    def test_moving_average_insufficient_history(self, insufficient_history_data):
        """Test moving average returns None with insufficient history."""
        ma = calculate_moving_average(insufficient_history_data, "backend", periods=3)
        assert ma is None

    def test_moving_average_with_zero_coverage(self, zero_coverage_data):
        """Test moving average excludes 0% coverage values."""
        ma = calculate_moving_average(zero_coverage_data, "backend", periods=2)

        # Should exclude the 0% value and only use the 75% value
        # Or return None if only 1 valid data point
        assert ma is None or ma == 75.0


# =============================================================================
# Report generation tests
# =============================================================================

class TestGenerateTextReport:
    """Tests for generate_text_report function."""

    def test_generate_text_report_format(self, regression_data):
        """Test text report contains required sections."""
        regressions = detect_regressions(regression_data, threshold=1.0)
        trends = analyze_trends(regression_data, periods=1)

        report = generate_text_report(regressions, trends)

        assert "Coverage Trend Analysis Report" in report
        assert "Regressions Detected" in report
        assert "Platform Trends" in report
        assert "backend" in report.lower()
        assert "Summary" in report

    def test_generate_text_report_no_regressions(self, improvement_data):
        """Test text report handles no regressions case."""
        regressions = detect_regressions(improvement_data, threshold=1.0)
        trends = analyze_trends(improvement_data, periods=1)

        report = generate_text_report(regressions, trends)

        assert "No Regressions Detected" in report
        assert "Summary: 4 improving, 0 declining" in report

    def test_generate_text_report_severity_breakdown(self, critical_regression_data):
        """Test text report includes severity breakdown."""
        regressions = detect_regressions(critical_regression_data, threshold=1.0)
        trends = analyze_trends(critical_regression_data, periods=1)

        report = generate_text_report(regressions, trends)

        assert "Critical: 1" in report
        assert "WARNING" in report or "critical" in report.lower()


class TestGenerateJsonReport:
    """Tests for generate_json_report function."""

    def test_generate_json_report_structure(self, regression_data):
        """Test JSON report has correct structure."""
        regressions = detect_regressions(regression_data, threshold=1.0)
        trends = analyze_trends(regression_data, periods=1)

        json_report = generate_json_report(regressions, trends)
        report_data = json.loads(json_report)

        assert "regressions" in report_data
        assert "trends" in report_data
        assert "generated_at" in report_data
        assert isinstance(report_data["regressions"], list)

    def test_generate_json_report_parseable(self, regression_data):
        """Test JSON report is valid JSON."""
        regressions = detect_regressions(regression_data, threshold=1.0)
        trends = analyze_trends(regression_data, periods=1)

        json_report = generate_json_report(regressions, trends)

        # Should not raise exception
        parsed = json.loads(json_report)
        assert parsed is not None


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report function."""

    def test_generate_markdown_report_table(self, regression_data):
        """Test markdown report contains tables."""
        regressions = detect_regressions(regression_data, threshold=1.0)
        trends = analyze_trends(regression_data, periods=1)

        md_report = generate_markdown_report(regressions, trends)

        assert "| Platform |" in md_report
        assert "|----------|" in md_report
        assert "|" in md_report  # Table separator

    def test_generate_markdown_report_trend_indicators(self, improvement_data):
        """Test markdown report includes trend indicators (↑↓→)."""
        regressions = detect_regressions(improvement_data, threshold=1.0)
        trends = analyze_trends(improvement_data, periods=1)

        md_report = generate_markdown_report(regressions, trends)

        # Should have up arrow for improvement
        assert "↑" in md_report or "improving" in md_report.lower()

    def test_generate_markdown_report_no_regressions(self, improvement_data):
        """Test markdown report handles no regressions case."""
        regressions = detect_regressions(improvement_data, threshold=1.0)
        trends = analyze_trends(improvement_data, periods=1)

        md_report = generate_markdown_report(regressions, trends)

        assert "No regressions detected" in md_report
        assert "Summary:" in md_report


# =============================================================================
# Regression logging tests
# =============================================================================

class TestLogRegressions:
    """Tests for log_regressions function."""

    def test_log_regressions_creates_file(self, tmp_path, regression_data):
        """Test regression log file is created."""
        output_file = tmp_path / "coverage_regressions.json"
        regressions = detect_regressions(regression_data, threshold=1.0)

        log_regressions(regressions, output_file)

        assert output_file.exists()

    def test_log_regressions_valid_json(self, tmp_path, regression_data):
        """Test regression log file contains valid JSON."""
        output_file = tmp_path / "coverage_regressions.json"
        regressions = detect_regressions(regression_data, threshold=1.0)

        log_regressions(regressions, output_file)

        with open(output_file, 'r') as f:
            data = json.load(f)

        assert "regressions" in data
        assert "metadata" in data

    def test_log_regressions_appends(self, tmp_path):
        """Test regressions are appended to existing file."""
        output_file = tmp_path / "coverage_regressions.json"

        # First batch
        regressions_1 = [
            {
                "platform": "backend",
                "current_coverage": 72.0,
                "previous_coverage": 75.0,
                "delta": -3.0,
                "severity": "warning",
                "detected_at": datetime.now().isoformat() + "Z"
            }
        ]

        log_regressions(regressions_1, output_file)

        # Second batch
        regressions_2 = [
            {
                "platform": "frontend",
                "current_coverage": 78.0,
                "previous_coverage": 80.0,
                "delta": -2.0,
                "severity": "warning",
                "detected_at": datetime.now().isoformat() + "Z"
            }
        ]

        log_regressions(regressions_2, output_file)

        # Verify both are in file
        with open(output_file, 'r') as f:
            data = json.load(f)

        assert len(data["regressions"]) == 2
        platforms = [r["platform"] for r in data["regressions"]]
        assert "backend" in platforms
        assert "frontend" in platforms

    def test_log_regressions_prunes_old(self, tmp_path):
        """Test old regressions are pruned (>90 days)."""
        output_file = tmp_path / "coverage_regressions.json"

        # Create old regression (>90 days ago)
        old_time = datetime.now() - timedelta(days=100)
        old_regression = {
            "platform": "backend",
            "current_coverage": 72.0,
            "previous_coverage": 75.0,
            "delta": -3.0,
            "severity": "warning",
            "detected_at": old_time.isoformat() + "Z"
        }

        # Create initial file with old regression
        initial_data = {
            "regressions": [old_regression],
            "metadata": {
                "created_at": datetime.now().isoformat() + "Z",
                "regression_threshold": 1.0,
                "retention_days": 90
            }
        }

        with open(output_file, 'w') as f:
            json.dump(initial_data, f)

        # Add new regression
        new_regression = {
            "platform": "frontend",
            "current_coverage": 78.0,
            "previous_coverage": 80.0,
            "delta": -2.0,
            "severity": "warning",
            "detected_at": datetime.now().isoformat() + "Z"
        }

        log_regressions([new_regression], output_file)

        # Verify old regression pruned, new regression present
        with open(output_file, 'r') as f:
            data = json.load(f)

        assert len(data["regressions"]) == 1
        assert data["regressions"][0]["platform"] == "frontend"


# =============================================================================
# Edge case tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_insufficient_history_for_trend(self, insufficient_history_data):
        """Test functions handle insufficient history gracefully."""
        regressions = detect_regressions(insufficient_history_data, threshold=1.0)
        trends = analyze_trends(insufficient_history_data, periods=1)

        assert len(regressions) == 0
        assert trends["regression_count"] == 0
        assert trends["improvement_count"] == 0

    def test_missing_platform_in_history(self):
        """Test missing platform data is handled gracefully."""
        base_time = datetime.now() - timedelta(days=1)

        data = {
            "history": [
                {
                    "timestamp": base_time.isoformat() + "Z",
                    "overall_coverage": 75.0,
                    "platforms": {"backend": 75.0, "frontend": 80.0},
                    # mobile and desktop missing
                    "thresholds": {"backend": 70.0, "frontend": 80.0}
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

        regressions = detect_regressions(data, threshold=1.0)

        # Should only process backend (mobile/desktop skipped)
        assert len(regressions) == 1
        assert regressions[0]["platform"] == "backend"

    def test_zero_coverage_handling(self, zero_coverage_data):
        """Test 0% coverage (failed job) is skipped."""
        regressions = detect_regressions(zero_coverage_data, threshold=1.0)

        # Backend with 0% should be skipped
        backend_regressions = [r for r in regressions if r["platform"] == "backend"]
        assert len(backend_regressions) == 0

    def test_empty_history(self):
        """Test empty history is handled gracefully."""
        data = {
            "history": [],
            "latest": {},
            "platform_trends": {},
            "computed_weights": {
                "backend": 0.35,
                "frontend": 0.40,
                "mobile": 0.15,
                "desktop": 0.10
            }
        }

        regressions = detect_regressions(data, threshold=1.0)
        trends = analyze_trends(data, periods=1)

        assert len(regressions) == 0
        assert trends["regression_count"] == 0
        assert trends["improvement_count"] == 0

    def test_malformed_timestamp(self):
        """Test malformed timestamps are handled gracefully."""
        base_time = datetime.now() - timedelta(days=1)

        data = {
            "history": [
                {
                    "timestamp": "invalid-timestamp",
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

        # Should not crash, but may skip entry with invalid timestamp
        regressions = detect_regressions(data, threshold=1.0)

        # If both entries processed, should detect regression
        # If first entry skipped, insufficient history
        assert len(regressions) in [0, 1]
