#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Platform Coverage Trend Tracking Tests

Tests for update_cross_platform_trending.py script including:
- Data loading and validation
- Trend update functionality
- Trend delta computation
- Report generation (text, json, markdown)
- CLI integration
- Full workflow scenarios
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

from tests.scripts.update_cross_platform_trending import (
    load_trending_data,
    update_trending_data,
    compute_trend_delta,
    generate_trend_report,
    TrendEntry,
    TrendDelta,
    MAX_HISTORY_DAYS,
    MIN_HISTORY_ENTRIES
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create temporary directory for test files."""
    return tmp_path


@pytest.fixture
def mock_trend_data() -> Dict:
    """Mock historical trend data with 10 entries."""
    base_time = datetime.now() - timedelta(days=10)
    history = []

    for i in range(10):
        entry_time = base_time + timedelta(days=i)
        history.append({
            "timestamp": entry_time.isoformat() + "Z",
            "overall_coverage": 70.0 + i * 0.5,  # Gradual improvement
            "platforms": {
                "backend": 65.0 + i * 0.3,
                "frontend": 80.0 + i * 0.4,
                "mobile": 50.0 + i * 0.2,
                "desktop": 40.0 + i * 0.1
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
def mock_summary_data(temp_dir: Path) -> Path:
    """Create mock cross_platform_summary.json file."""
    summary = {
        "platforms": {
            "python": {"coverage_pct": 75.0},
            "javascript": {"coverage_pct": 82.0},
            "mobile": {"coverage_pct": 55.0},
            "rust": {"coverage_pct": 45.0}
        },
        "weighted": {
            "overall_pct": 77.75
        },
        "thresholds": {
            "backend": 70.0,
            "frontend": 80.0,
            "mobile": 50.0,
            "desktop": 40.0
        },
        "timestamp": datetime.now().isoformat() + "Z"
    }

    summary_file = temp_dir / "cross_platform_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f)

    return summary_file


@pytest.fixture
def empty_trend_data() -> Dict:
    """Empty trending structure."""
    return {
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


@pytest.fixture
def single_entry_trend(temp_dir: Path) -> Path:
    """Trend file with only one historical entry."""
    entry = {
        "timestamp": datetime.now().isoformat() + "Z",
        "overall_coverage": 75.0,
        "platforms": {
            "backend": 70.0,
            "frontend": 80.0,
            "mobile": 50.0,
            "desktop": 40.0
        },
        "thresholds": {
            "backend": 70.0,
            "frontend": 80.0,
            "mobile": 50.0,
            "desktop": 40.0
        }
    }

    trend_file = temp_dir / "trend.json"
    with open(trend_file, 'w') as f:
        json.dump({
            "history": [entry],
            "latest": entry,
            "platform_trends": {},
            "computed_weights": {
                "backend": 0.35,
                "frontend": 0.40,
                "mobile": 0.15,
                "desktop": 0.10
            }
        }, f)

    return trend_file


# =============================================================================
# Data Loading Tests
# =============================================================================

def test_load_trending_data_valid(temp_dir: Path, mock_trend_data: Dict):
    """Verify structure validation for valid trending data."""
    trend_file = temp_dir / "trend.json"
    with open(trend_file, 'w') as f:
        json.dump(mock_trend_data, f)

    result = load_trending_data(trend_file)

    assert "history" in result
    assert "latest" in result
    assert "platform_trends" in result
    assert len(result["history"]) == 10
    assert result["latest"]["overall_coverage"] == 74.5


def test_load_trending_data_missing_file(temp_dir: Path):
    """Initialize empty structure when file doesn't exist."""
    trend_file = temp_dir / "nonexistent.json"

    result = load_trending_data(trend_file)

    assert result["history"] == []
    assert result["latest"] == {}
    assert "platform_trends" in result


def test_load_trending_data_invalid_json(temp_dir: Path):
    """Handle malformed JSON gracefully."""
    trend_file = temp_dir / "invalid.json"
    with open(trend_file, 'w') as f:
        f.write("{ invalid json }")

    result = load_trending_data(trend_file)

    # Should return default empty structure
    assert result["history"] == []
    assert result["latest"] == {}


def test_load_trending_data_empty_history(temp_dir: Path):
    """Initialize with empty history list."""
    trend_data = {
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

    trend_file = temp_dir / "empty.json"
    with open(trend_file, 'w') as f:
        json.dump(trend_data, f)

    result = load_trending_data(trend_file)

    assert len(result["history"]) == 0


# =============================================================================
# Trend Update Tests
# =============================================================================

def test_update_trending_new_entry(temp_dir: Path, mock_summary_data: Path):
    """Add new entry to history."""
    trend_file = temp_dir / "trend.json"

    result = update_trending_data(mock_summary_data, trend_file)

    assert len(result["history"]) == 1
    assert result["latest"]["overall_coverage"] == 77.75
    assert result["latest"]["platforms"]["python"] == 75.0


def test_update_trending_prune_old(temp_dir: Path, mock_trend_data: Dict):
    """Remove entries older than MAX_HISTORY_DAYS."""
    # Create trend data with old entries
    trend_file = temp_dir / "trend.json"

    # Add very old entry (40 days ago)
    old_entry = {
        "timestamp": (datetime.now() - timedelta(days=40)).isoformat() + "Z",
        "overall_coverage": 60.0,
        "platforms": {"backend": 55.0, "frontend": 70.0, "mobile": 40.0, "desktop": 30.0},
        "thresholds": {"backend": 70.0, "frontend": 80.0, "mobile": 50.0, "desktop": 40.0}
    }
    mock_trend_data["history"].insert(0, old_entry)

    with open(trend_file, 'w') as f:
        json.dump(mock_trend_data, f)

    # Update with --prune flag
    summary_file = temp_dir / "summary.json"
    summary_file.write_text('{"platforms": {"python": {"coverage_pct": 70.0}}, "weighted": {"overall_pct": 70.0}, "thresholds": {}, "timestamp": "2026-03-06T12:00:00Z"}')

    result = update_trending_data(summary_file, trend_file, commit_sha="abc123", branch="main")

    # Old entry should be pruned
    assert all(
        datetime.fromisoformat(entry["timestamp"].replace("Z", "")) >= datetime.now() - timedelta(days=MAX_HISTORY_DAYS)
        for entry in result["history"]
    )


def test_update_trending_preserve_recent(temp_dir: Path, mock_trend_data: Dict):
    """Keep entries within retention period."""
    trend_file = temp_dir / "trend.json"
    with open(trend_file, 'w') as f:
        json.dump(mock_trend_data, f)

    summary_file = temp_dir / "summary.json"
    summary_file.write_text('{"platforms": {"python": {"coverage_pct": 70.0}}, "weighted": {"overall_pct": 70.0}, "thresholds": {}, "timestamp": "2026-03-06T12:00:00Z"}')

    result = update_trending_data(summary_file, trend_file)

    # All entries should be preserved (within 30 days)
    assert len(result["history"]) == 11  # 10 original + 1 new


def test_update_trending_latest_updated(temp_dir: Path, mock_summary_data: Path):
    """Verify latest entry reflects new data."""
    trend_file = temp_dir / "trend.json"

    result = update_trending_data(mock_summary_data, trend_file)

    assert result["latest"]["overall_coverage"] == 77.75
    assert result["latest"]["platforms"]["python"] == 75.0
    assert result["latest"]["platforms"]["javascript"] == 82.0


def test_update_trending_commit_tracking(temp_dir: Path, mock_summary_data: Path):
    """Verify commit SHA storage."""
    trend_file = temp_dir / "trend.json"

    update_trending_data(mock_summary_data, trend_file, commit_sha="abc123", branch="main")

    # Load and verify
    with open(trend_file, 'r') as f:
        data = json.load(f)

    assert data["history"][-1]["commit_sha"] == "abc123"
    assert data["history"][-1]["branch"] == "main"


def test_update_trending_branch_tracking(temp_dir: Path, mock_summary_data: Path):
    """Verify branch name storage."""
    trend_file = temp_dir / "trend.json"

    update_trending_data(mock_summary_data, trend_file, commit_sha="abc123", branch="feature/test")

    # Load and verify
    with open(trend_file, 'r') as f:
        data = json.load(f)

    assert data["history"][-1]["branch"] == "feature/test"


# =============================================================================
# Trend Delta Computation Tests
# =============================================================================

def test_compute_trend_delta_upward(temp_dir: Path, mock_trend_data: Dict):
    """Positive delta >1% returns 'up'."""
    # Add entry with significant increase
    mock_trend_data["history"].append({
        "timestamp": datetime.now().isoformat() + "Z",
        "overall_coverage": 80.0,
        "platforms": {"backend": 75.0, "frontend": 85.0, "mobile": 60.0, "desktop": 50.0},
        "thresholds": {"backend": 70.0, "frontend": 80.0, "mobile": 50.0, "desktop": 40.0}
    })

    delta = compute_trend_delta(mock_trend_data, "backend", periods=1)

    assert delta is not None
    assert delta.delta > 1.0
    assert delta.trend == "up"
    assert delta.platform == "backend"


def test_compute_trend_delta_downward(temp_dir: Path):
    """Negative delta <-1% returns 'down'."""
    trend_data = {
        "history": [
            {
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0, "frontend": 85.0, "mobile": 60.0, "desktop": 50.0},
                "thresholds": {}
            },
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 70.0,
                "platforms": {"backend": 70.0, "frontend": 80.0, "mobile": 55.0, "desktop": 45.0},
                "thresholds": {}
            }
        ]
    }

    delta = compute_trend_delta(trend_data, "backend", periods=1)

    assert delta is not None
    assert delta.delta < -1.0
    assert delta.trend == "down"


def test_compute_trend_delta_stable(temp_dir: Path):
    """Delta within ±1% returns 'stable'."""
    trend_data = {
        "history": [
            {
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0, "frontend": 85.0, "mobile": 60.0, "desktop": 50.0},
                "thresholds": {}
            },
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 75.3,
                "platforms": {"backend": 75.3, "frontend": 85.3, "mobile": 60.3, "desktop": 50.3},
                "thresholds": {}
            }
        ]
    }

    delta = compute_trend_delta(trend_data, "backend", periods=1)

    assert delta is not None
    assert abs(delta.delta) <= 1.0
    assert delta.trend == "stable"


def test_compute_trend_delta_insufficient_history(temp_dir: Path):
    """None if <2 entries."""
    trend_data = {
        "history": [
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {}
            }
        ]
    }

    delta = compute_trend_delta(trend_data, "backend", periods=1)

    assert delta is None


def test_compute_trend_delta_missing_platform(temp_dir: Path):
    """Treat missing platform as 0%."""
    trend_data = {
        "history": [
            {
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},
                "thresholds": {}
            },
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {},  # Frontend missing
                "thresholds": {}
            }
        ]
    }

    delta = compute_trend_delta(trend_data, "frontend", periods=1)

    assert delta is not None
    assert delta.previous == 0.0
    assert delta.current == 0.0


def test_compute_trend_delta_multi_period(temp_dir: Path, mock_trend_data: Dict):
    """7-period delta calculation."""
    delta = compute_trend_delta(mock_trend_data, "backend", periods=7)

    assert delta is not None
    assert delta.periods == 7
    assert isinstance(delta.delta, float)


# =============================================================================
# Trend Report Generation Tests
# =============================================================================

def test_generate_trend_report_text(temp_dir: Path, mock_trend_data: Dict):
    """Text format with indicators."""
    report = generate_trend_report(mock_trend_data, format="text")

    assert "Cross-Platform Coverage Trend Report" in report
    assert "Trend (1 period):" in report
    assert "Backend" in report or "backend" in report.lower()


def test_generate_trend_report_json(temp_dir: Path, mock_trend_data: Dict):
    """JSON format with deltas."""
    report = generate_trend_report(mock_trend_data, format="json")

    report_data = json.loads(report)
    assert "trends_1_period" in report_data
    assert "trends_7_period" in report_data


def test_generate_trend_report_markdown(temp_dir: Path, mock_trend_data: Dict):
    """Markdown table for PR."""
    report = generate_trend_report(mock_trend_data, format="markdown")

    assert "| Platform |" in report
    assert "| Coverage |" in report
    assert "| Trend (1) |" in report
    assert "**Legend:**" in report


def test_generate_trend_report_indicators(temp_dir: Path, mock_trend_data: Dict):
    """Verify arrow symbols."""
    report = generate_trend_report(mock_trend_data, format="text")

    # Should contain indicators
    assert "↑" in report or "↓" in report or "→" in report


def test_generate_trend_report_no_history(temp_dir: Path, empty_trend_data: Dict):
    """Handle missing trend data gracefully."""
    report = generate_trend_report(empty_trend_data, format="text")

    assert "Insufficient history" in report


# =============================================================================
# CLI Integration Tests
# =============================================================================

def test_cli_update_with_summary(temp_dir: Path, mock_summary_data: Path, capsys):
    """Verify --summary argument."""
    import sys
    from tests.scripts import update_cross_platform_trending

    trend_file = temp_dir / "trend.json"

    sys.argv = [
        "update_cross_platform_trending.py",
        "--summary", str(mock_summary_data),
        "--trending-file", str(trend_file),
        "--format", "text"
    ]

    try:
        update_cross_platform_trending.main()
    except SystemExit:
        pass

    captured = capsys.readouterr()

    # Should show insufficient history (first run)
    assert trend_file.exists()


def test_cli_prune_flag(temp_dir: Path, mock_trend_data: Dict, mock_summary_data: Path):
    """Verify --prune removes old entries."""
    import sys
    from tests.scripts import update_cross_platform_trending

    trend_file = temp_dir / "trend.json"
    with open(trend_file, 'w') as f:
        json.dump(mock_trend_data, f)

    sys.argv = [
        "update_cross_platform_trending.py",
        "--summary", str(mock_summary_data),
        "--trending-file", str(trend_file),
        "--prune"
    ]

    try:
        update_cross_platform_trending.main()
    except SystemExit:
        pass

    # Verify old entries pruned
    with open(trend_file, 'r') as f:
        data = json.load(f)

    assert all(
        datetime.fromisoformat(entry["timestamp"].replace("Z", "")) >= datetime.now() - timedelta(days=MAX_HISTORY_DAYS)
        for entry in data["history"]
    )


def test_cli_periods_argument(temp_dir: Path, mock_trend_data: Dict, capsys):
    """Verify custom periods calculation."""
    report = generate_trend_report(mock_trend_data, format="text", periods=7)

    assert "7 periods" in report.lower() or "week" in report.lower()


def test_cli_format_variants(temp_dir: Path, mock_trend_data: Dict):
    """Verify text/json/markdown output."""
    text_report = generate_trend_report(mock_trend_data, format="text")
    json_report = generate_trend_report(mock_trend_data, format="json")
    md_report = generate_trend_report(mock_trend_data, format="markdown")

    assert "Cross-Platform Coverage Trend Report" in text_report
    assert json.loads(json_report)
    assert "|" in md_report


def test_cli_commit_tracking(temp_dir: Path, mock_summary_data: Path):
    """Verify --commit-sha storage."""
    import sys
    from tests.scripts import update_cross_platform_trending

    trend_file = temp_dir / "trend.json"

    sys.argv = [
        "update_cross_platform_trending.py",
        "--summary", str(mock_summary_data),
        "--trending-file", str(trend_file),
        "--commit-sha", "test123",
        "--branch", "feature-branch"
    ]

    try:
        update_cross_platform_trending.main()
    except SystemExit:
        pass

    with open(trend_file, 'r') as f:
        data = json.load(f)

    assert data["history"][-1]["commit_sha"] == "test123"
    assert data["history"][-1]["branch"] == "feature-branch"


# =============================================================================
# Integration Tests
# =============================================================================

def test_full_workflow(temp_dir: Path, mock_summary_data: Path):
    """Load summary, update trends, compute deltas, generate report."""
    trend_file = temp_dir / "trend.json"

    # Update with first summary
    result1 = update_trending_data(mock_summary_data, trend_file, commit_sha="abc1", branch="main")
    assert len(result1["history"]) == 1

    # Update with second summary (slightly different)
    summary2 = temp_dir / "summary2.json"
    with open(mock_summary_data, 'r') as f:
        summary_data = json.load(f)
    summary_data["platforms"]["python"]["coverage_pct"] = 76.0
    summary_data["weighted"]["overall_pct"] = 78.5
    with open(summary2, 'w') as f:
        json.dump(summary_data, f)

    result2 = update_trending_data(summary2, trend_file, commit_sha="abc2", branch="main")
    assert len(result2["history"]) == 2

    # Compute delta
    delta = compute_trend_delta(result2, "python", periods=1)
    assert delta is not None
    assert delta.delta == 1.0  # 76.0 - 75.0

    # Generate report
    report = generate_trend_report(result2, format="text")
    assert "Coverage Trend Report" in report


def test_pr_comment_integration(temp_dir: Path, mock_trend_data: Dict):
    """Generate PR comment with trend section."""
    report = generate_trend_report(mock_trend_data, format="markdown")

    # Should be markdown table format
    assert "| Platform | Coverage | Trend" in report
    assert "|---" in report or "---|" in report
    assert "**Legend:**" in report


def test_regression_detection(temp_dir: Path):
    """Identify regressing platforms in trend."""
    trend_data = {
        "history": [
            {
                "timestamp": (datetime.now() - timedelta(days=7)).isoformat() + "Z",
                "overall_coverage": 80.0,
                "platforms": {"backend": 80.0, "frontend": 85.0, "mobile": 70.0, "desktop": 60.0},
                "thresholds": {}
            },
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 70.0, "frontend": 80.0, "mobile": 65.0, "desktop": 55.0},
                "thresholds": {}
            }
        ]
    }

    delta = compute_trend_delta(trend_data, "backend", periods=1)

    assert delta is not None
    assert delta.trend == "down"
    assert delta.delta < 0


def test_week_over_week_comparison(temp_dir: Path, mock_trend_data: Dict):
    """7-period trend calculation."""
    delta_7 = compute_trend_delta(mock_trend_data, "backend", periods=7)

    assert delta_7 is not None
    assert delta_7.periods == 7


def test_missing_platform_handling(temp_dir: Path):
    """Trend handles partial platform data."""
    trend_data = {
        "history": [
            {
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0, "frontend": 85.0},
                "thresholds": {}
            },
            {
                "timestamp": datetime.now().isoformat() + "Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 75.0},  # Frontend missing
                "thresholds": {}
            }
        ]
    }

    delta = compute_trend_delta(trend_data, "frontend", periods=1)

    assert delta is not None
    assert delta.current == 0.0
    assert delta.previous == 85.0
