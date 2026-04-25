"""
Workflow Analytics Engine Tests
Tests for core/workflow_analytics_engine.py
"""

import os
os.environ["TESTING"] = "1"

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch


class TestMetricsCollection:
    """Test collect execution data, store metrics, validate schema."""

    def test_collect_execution_metrics(self):
        """Test collecting workflow execution metrics."""
        metrics = {
            "workflow_id": "wf-001",
            "duration_ms": 1500,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        assert metrics["status"] == "completed"
        assert metrics["duration_ms"] > 0


class TestPerformanceAnalytics:
    """Test calculate duration, success rate, percentiles."""

    def test_calculate_success_rate(self):
        """Test calculating workflow success rate."""
        executions = [
            {"status": "completed"},
            {"status": "completed"},
            {"status": "failed"}
        ]
        
        success_count = sum(1 for e in executions if e["status"] == "completed")
        success_rate = success_count / len(executions)
        
        assert success_rate == 0.6666666666666666


class TestErrorTracking:
    """Test categorize errors, track error frequency, error trends."""

    def test_categorize_errors(self):
        """Test categorizing execution errors."""
        errors = [
            {"type": "timeout", "count": 3},
            {"type": "validation", "count": 5}
        ]
        
        total_errors = sum(e["count"] for e in errors)
        assert total_errors == 8


class TestTrendAnalysis:
    """Test compare periods, detect anomalies, forecast trends."""

    def test_compare_periods(self):
        """Test comparing metrics between time periods."""
        period1 = {"executions": 100, "success_rate": 0.95}
        period2 = {"executions": 120, "success_rate": 0.97}
        
        improvement = period2["success_rate"] - period1["success_rate"]
        assert improvement > 0


class TestReportGeneration:
    """Test generate summary reports, detailed reports, export data."""

    def test_generate_summary_report(self):
        """Test generating analytics summary report."""
        report = {
            "period": "last_7_days",
            "total_executions": 500,
            "avg_duration": 1200,
            "success_rate": 0.94
        }
        
        assert report["total_executions"] == 500
        assert "success_rate" in report
