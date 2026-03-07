#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Cross-Platform Coverage Dashboard Generator

Tests cover:
- Data loading and validation
- Chart data preparation
- Matplotlib chart generation
- Statistics calculation
- HTML template generation
- CLI interface
- Edge cases and error handling
"""

import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add scripts directory to path
script_dir = Path(__file__).parent.parent / "tests" / "scripts"
sys.path.insert(0, str(script_dir))

# Import module under test
import generate_cross_platform_dashboard as dashboard


# Fixtures
@pytest.fixture
def sample_trend_data():
    """Sample trending data with 30-day history."""
    return {
        "history": [
            {
                "timestamp": "2026-03-01T12:00:00Z",
                "overall_coverage": 75.0,
                "platforms": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 65.0,
                    "desktop": 60.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                }
            },
            {
                "timestamp": "2026-03-15T12:00:00Z",
                "overall_coverage": 77.5,
                "platforms": {
                    "backend": 72.0,
                    "frontend": 82.0,
                    "mobile": 68.0,
                    "desktop": 62.0
                },
                "thresholds": {
                    "backend": 70.0,
                    "frontend": 80.0,
                    "mobile": 50.0,
                    "desktop": 40.0
                }
            }
        ],
        "latest": {
            "timestamp": "2026-03-15T12:00:00Z",
            "overall_coverage": 77.5,
            "platforms": {
                "backend": 72.0,
                "frontend": 82.0,
                "mobile": 68.0,
                "desktop": 62.0
            },
            "thresholds": {
                "backend": 70.0,
                "frontend": 80.0,
                "mobile": 50.0,
                "desktop": 40.0
            }
        },
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }


@pytest.fixture
def minimal_trend_data():
    """Minimal trending data with 2 entries."""
    return {
        "history": [
            {
                "timestamp": "2026-03-01T12:00:00Z",
                "overall_coverage": 75.0,
                "platforms": {"backend": 70.0, "frontend": 80.0, "mobile": 65.0, "desktop": 60.0},
                "thresholds": {}
            },
            {
                "timestamp": "2026-03-02T12:00:00Z",
                "overall_coverage": 76.0,
                "platforms": {"backend": 71.0, "frontend": 81.0, "mobile": 66.0, "desktop": 61.0},
                "thresholds": {}
            }
        ],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }


@pytest.fixture
def empty_trend_data():
    """Empty trending data structure."""
    return {
        "history": [],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {}
    }


# Data preparation tests
class TestPrepareChartData:
    """Tests for prepare_chart_data function."""

    def test_prepare_chart_data_filters_by_days(self, sample_trend_data):
        """Test that prepare_chart_data filters to last N entries."""
        # Create data with 5 entries, request last 3
        extended_data = {
            "history": sample_trend_data["history"] * 3,  # 6 entries
            "latest": sample_trend_data["latest"],
            "platform_trends": {},
            "computed_weights": {}
        }

        result = dashboard.prepare_chart_data(extended_data, days=3)

        # Should only have last 3 entries
        assert len(result["timestamps"]) == 3
        assert len(result["overall"]) == 3
        for platform_values in result["platforms"].values():
            assert len(platform_values) == 3

    def test_prepare_chart_data_extracts_platforms(self, sample_trend_data):
        """Test that prepare_chart_data extracts all platform data."""
        result = dashboard.prepare_chart_data(sample_trend_data)

        # Check all platform keys exist
        assert "backend" in result["platforms"]
        assert "frontend" in result["platforms"]
        assert "mobile" in result["platforms"]
        assert "desktop" in result["platforms"]

        # Check values are lists
        for platform_values in result["platforms"].values():
            assert isinstance(platform_values, list)

    def test_prepare_chart_data_handles_empty_history(self, empty_trend_data):
        """Test that prepare_chart_data handles empty history gracefully."""
        result = dashboard.prepare_chart_data(empty_trend_data)

        # Should return empty lists
        assert result["timestamps"] == []
        assert result["overall"] == []
        assert result["platforms"] == {}


# Chart generation tests
class TestCreateLineChart:
    """Tests for create_line_chart function."""

    @patch('generate_cross_platform_dashboard.plt')
    def test_create_line_chart_returns_bytes(self, mock_plt, sample_trend_data):
        """Test that create_line_chart returns base64-encoded bytes."""
        # Setup mock
        mock_fig = MagicMock()
        mock_buf = io.BytesIO()
        mock_buf.write(b"fake png data")
        mock_buf.seek(0)
        
        mock_plt.subplots.return_value = (mock_fig, MagicMock())
        mock_plt.tight_layout = MagicMock()
        
        with patch('generate_cross_platform_dashboard.io.BytesIO', return_value=mock_buf):
            result = dashboard.create_line_chart(sample_trend_data)

        # Should return bytes
        assert isinstance(result, bytes)

    @patch('generate_cross_platform_dashboard.plt')
    def test_create_line_chart_closes_figure(self, mock_plt, sample_trend_data):
        """Test that create_line_chart closes figure to prevent memory leaks."""
        mock_fig = MagicMock()
        mock_buf = io.BytesIO()
        mock_buf.write(b"fake png data")
        mock_buf.seek(0)
        
        mock_plt.subplots.return_value = (mock_fig, MagicMock())
        mock_plt.tight_layout = MagicMock()
        mock_plt.close = MagicMock()

        with patch('generate_cross_platform_dashboard.io.BytesIO', return_value=mock_buf):
            dashboard.create_line_chart(sample_trend_data)

        # Should close figure
        mock_plt.close.assert_called_once_with(mock_fig)

    def test_create_line_chart_handles_empty_data(self):
        """Test that create_line_chart handles empty data gracefully."""
        empty_data = {"timestamps": [], "platforms": {}, "overall": []}
        result = dashboard.create_line_chart(empty_data)

        # Should return empty bytes
        assert result == b""


class TestCreatePlatformCharts:
    """Tests for create_platform_charts function."""

    @patch('generate_cross_platform_dashboard.plt')
    def test_create_platform_charts_returns_dict(self, mock_plt, sample_trend_data):
        """Test that create_platform_charts returns dict with base64 images."""
        mock_fig = MagicMock()
        mock_buf = io.BytesIO()
        mock_buf.write(b"fake platform chart")
        mock_buf.seek(0)
        
        mock_plt.subplots.return_value = (mock_fig, [MagicMock()]*4)
        mock_plt.tight_layout = MagicMock()
        mock_plt.close = MagicMock()

        with patch('generate_cross_platform_dashboard.io.BytesIO', return_value=mock_buf):
            result = dashboard.create_platform_charts(sample_trend_data)

        # Should return dict with platforms key
        assert isinstance(result, dict)
        assert "platforms" in result

    def test_create_platform_charts_handles_empty_data(self):
        """Test that create_platform_charts handles empty data gracefully."""
        empty_data = {"timestamps": [], "platforms": {}, "overall": []}
        result = dashboard.create_platform_charts(empty_data)

        # Should return empty dict
        assert result == {}


# Statistics tests
class TestCalculateStatistics:
    """Tests for calculate_statistics function."""

    def test_calculate_statistics_current_value(self, sample_trend_data):
        """Test that calculate_statistics extracts current value correctly."""
        chart_data = dashboard.prepare_chart_data(sample_trend_data)
        stats = dashboard.calculate_statistics(chart_data)

        # Check current values
        assert stats["overall"]["current"] == 77.5
        assert stats["backend"]["current"] == 72.0
        assert stats["frontend"]["current"] == 82.0

    def test_calculate_statistics_min_max_avg(self, sample_trend_data):
        """Test that calculate_statistics calculates min/max/avg correctly."""
        chart_data = dashboard.prepare_chart_data(sample_trend_data)
        stats = dashboard.calculate_statistics(chart_data)

        # Overall: [75.0, 77.5]
        assert stats["overall"]["min"] == 75.0
        assert stats["overall"]["max"] == 77.5
        assert stats["overall"]["avg"] == 76.25

    def test_calculate_statistics_trend_up(self):
        """Test trend calculation for increasing values."""
        values = [70.0, 75.0, 80.0]
        trend = dashboard._calculate_trend(values)
        assert trend == "up"

    def test_calculate_statistics_trend_down(self):
        """Test trend calculation for decreasing values."""
        values = [80.0, 75.0, 70.0]
        trend = dashboard._calculate_trend(values)
        assert trend == "down"

    def test_calculate_statistics_trend_stable(self):
        """Test trend calculation for stable values."""
        values = [75.0, 75.5, 75.3]
        trend = dashboard._calculate_trend(values)
        assert trend == "stable"

    def test_calculate_statistics_handles_insufficient_data(self):
        """Test that _calculate_trend handles insufficient data."""
        trend = dashboard._calculate_trend([75.0])
        assert trend == "stable"


class TestTrendIndicator:
    """Tests for _get_trend_indicator function."""

    def test_get_trend_indicator_up(self):
        """Test trend indicator for 'up'."""
        assert dashboard._get_trend_indicator("up") == "↑"

    def test_get_trend_indicator_down(self):
        """Test trend indicator for 'down'."""
        assert dashboard._get_trend_indicator("down") == "↓"

    def test_get_trend_indicator_stable(self):
        """Test trend indicator for 'stable'."""
        assert dashboard._get_trend_indicator("stable") == "→"


# HTML generation tests
class TestGenerateHtmlTemplate:
    """Tests for generate_html_template function."""

    def test_generate_html_contains_embedded_images(self, sample_trend_data):
        """Test that HTML contains embedded base64 images."""
        chart_data = dashboard.prepare_chart_data(sample_trend_data)
        stats = dashboard.calculate_statistics(chart_data)

        # Create fake base64 images
        fake_chart = base64.b64encode(b"fake main chart")
        fake_platforms = base64.b64encode(b"fake platform charts")

        html = dashboard.generate_html_template(
            fake_chart,
            {"platforms": fake_platforms},
            chart_data,
            stats
        )

        # Should contain embedded images
        assert "<img src=\"data:image/png;base64," in html
        assert "fake main chart" in html
        assert "fake platform charts" in html

    def test_generate_html_contains_statistics(self, sample_trend_data):
        """Test that HTML contains statistics table."""
        chart_data = dashboard.prepare_chart_data(sample_trend_data)
        stats = dashboard.calculate_statistics(chart_data)

        fake_chart = base64.b64encode(b"fake chart")
        fake_platforms = base64.b64encode(b"fake platforms")

        html = dashboard.generate_html_template(
            fake_chart,
            {"platforms": fake_platforms},
            chart_data,
            stats
        )

        # Should contain statistics headers
        assert "Current" in html
        assert "Min" in html
        assert "Max" in html
        assert "Average" in html
        assert "Trend" in html

    def test_generate_html_has_valid_structure(self, sample_trend_data):
        """Test that HTML has valid document structure."""
        chart_data = dashboard.prepare_chart_data(sample_trend_data)
        stats = dashboard.calculate_statistics(chart_data)

        fake_chart = base64.b64encode(b"fake chart")
        fake_platforms = base64.b64encode(b"fake platforms")

        html = dashboard.generate_html_template(
            fake_chart,
            {"platforms": fake_platforms},
            chart_data,
            stats
        )

        # Should have valid HTML structure
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html
        assert "</head>" in html
        assert "</body>" in html


# Edge case tests
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_insufficient_data_for_main_chart(self):
        """Test main chart with insufficient data."""
        empty_data = {"timestamps": [], "platforms": {}, "overall": []}
        result = dashboard.create_line_chart(empty_data)
        assert result == b""

    def test_missing_platform_in_data(self):
        """Test chart generation when a platform is missing."""
        incomplete_data = {
            "timestamps": [datetime.now(), datetime.now()],
            "platforms": {
                "backend": [70.0, 72.0],
                "frontend": [80.0, 82.0]
                # mobile and desktop missing
            },
            "overall": [75.0, 77.0]
        }

        # Should not raise error
        result = dashboard.calculate_statistics(incomplete_data)
        assert "backend" in result
        assert "frontend" in result

    def test_zero_coverage_handling(self):
        """Test that 0% coverage is handled correctly."""
        zero_data = {
            "timestamps": [datetime.now(), datetime.now()],
            "platforms": {
                "backend": [0.0, 0.0],
                "frontend": [50.0, 60.0]
            },
            "overall": [25.0, 30.0]
        }

        result = dashboard.calculate_statistics(zero_data)
        assert result["backend"]["current"] == 0.0
        assert result["backend"]["min"] == 0.0

    @patch('generate_cross_platform_dashboard.plt')
    def test_single_data_point_chart(self, mock_plt):
        """Test chart generation with single data point."""
        single_point_data = {
            "timestamps": [datetime.now()],
            "platforms": {
                "backend": [75.0],
                "frontend": [80.0]
            },
            "overall": [77.5]
        }

        mock_fig = MagicMock()
        mock_buf = io.BytesIO()
        mock_buf.write(b"single point chart")
        mock_buf.seek(0)
        
        mock_plt.subplots.return_value = (mock_fig, MagicMock())

        with patch('generate_cross_platform_dashboard.io.BytesIO', return_value=mock_buf):
            result = dashboard.create_line_chart(single_point_data)

        # Should still generate chart
        assert isinstance(result, bytes)


# CLI tests
class TestCliInterface:
    """Tests for CLI interface."""

    @patch('sys.argv', ['generate_cross_platform_dashboard.py', '--help'])
    def test_cli_help(self):
        """Test that CLI help works."""
        with pytest.raises(SystemExit) as exc_info:
            dashboard.main()
        
        # Help exits with code 0
        assert exc_info.value.code == 0

    @patch('generate_cross_platform_dashboard.load_trending_data')
    @patch('generate_cross_platform_dashboard.prepare_chart_data')
    @patch('generate_cross_platform_dashboard.create_line_chart')
    @patch('generate_cross_platform_dashboard.create_platform_charts')
    @patch('generate_cross_platform_dashboard.calculate_statistics')
    @patch('generate_cross_platform_dashboard.generate_html_template')
    @patch('builtins.open', new_callable=MagicMock)
    def test_main_writes_html_file(
        self, mock_open, mock_html, mock_stats, mock_platforms, 
        mock_line, mock_prepare, mock_load, tmp_path
    ):
        """Test that main() writes HTML file."""
        # Setup mocks
        mock_load.return_value = {"history": [], "latest": {}, "platform_trends": {}, "computed_weights": {}}
        mock_prepare.return_value = {
            "timestamps": [datetime.now()],
            "platforms": {},
            "overall": []
        }
        mock_line.return_value = base64.b64encode(b"chart")
        mock_platforms.return_value = {"platforms": base64.b64encode(b"platforms")}
        mock_stats.return_value = {}
        mock_html.return_value = "<html>test</html>"

        output_file = tmp_path / "test_dashboard.html"

        with patch('sys.argv', [
            'generate_cross_platform_dashboard.py',
            '--output', str(output_file)
        ]):
            result = dashboard.main()

        # Should succeed
        assert result == 0
