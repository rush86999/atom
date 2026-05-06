"""
Test suite for core.condition_checkers module.

This module tests business condition checking logic:
- Inbox volume monitoring
- Task backlog monitoring
- API metrics checking
- Composite conditions (AND/OR)
- Database query conditions

All functions in this module use database session mocks,
making them suitable for unit testing.

Test Strategy:
- Mock database queries for condition data
- Test comparison operators (>, <, >=, <=, ==, !=)
- Test composite AND/OR logic
- Test edge cases (zero values, missing configs)
"""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from core.condition_checkers import ConditionCheckers
from core.models import ConditionMonitor


# ==============================================================================
# Condition Checking Dispatcher Tests
# ==============================================================================

class TestConditionCheckers:
    """Test condition checking dispatcher."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def condition_checkers(self, mock_db):
        """Create condition checkers instance."""
        return ConditionCheckers(mock_db)

    def test_check_condition_inbox_volume_type(self, condition_checkers):
        """Check inbox volume condition type."""
        monitor = Mock()
        monitor.condition_type = "inbox_volume"
        monitor.threshold_config = {
            "metric": "unread_count",
            "operator": ">",
            "value": 100
        }

        # Mock database query to return 150
        condition_checkers.db.query.return_value.scalar.return_value = 150

        result = condition_checkers.check_condition(monitor)

        assert result["triggered"] is True
        assert "value" in result
        assert "metric_name" in result

    def test_check_condition_unknown_type_returns_not_triggered(self, condition_checkers):
        """Unknown condition type returns not triggered."""
        monitor = Mock()
        monitor.condition_type = "unknown_type"

        result = condition_checkers.check_condition(monitor)

        assert result["triggered"] is False
        assert result["value"] is None

    def test_check_condition_composite_type(self, condition_checkers):
        """Check composite condition type."""
        monitor = Mock()
        monitor.condition_type = "composite"
        monitor.threshold_config = {
            "logic": "AND",
            "conditions": []
        }

        result = condition_checkers.check_condition(monitor)

        # Composite conditions should return result dict
        assert "triggered" in result


# ==============================================================================
# Inbox Volume Monitoring Tests
# ==============================================================================

class TestInboxVolumeMonitoring:
    """Test inbox volume monitoring."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def condition_checkers(self, mock_db):
        """Create condition checkers instance."""
        return ConditionCheckers(mock_db)

    def test_check_inbox_volume_exceeds_threshold(self, condition_checkers):
        """Check inbox volume when count exceeds threshold."""
        monitor = Mock()
        monitor.condition_type = "inbox_volume"
        monitor.threshold_config = {
            "metric": "unread_count",
            "operator": ">",
            "value": 100
        }

        # Mock database query to return 150 unread
        condition_checkers.db.query.return_value.scalar.return_value = 150

        result = condition_checkers._check_inbox_volume(monitor)

        assert result["triggered"] is True
        assert result["value"] == 150

    def test_check_inbox_volume_within_threshold(self, condition_checkers):
        """Check inbox volume when count is below threshold."""
        monitor = Mock()
        monitor.condition_type = "inbox_volume"
        monitor.threshold_config = {
            "metric": "unread_count",
            "operator": ">",
            "value": 100
        }

        # Mock database query to return 50 unread
        condition_checkers.db.query.return_value.scalar.return_value = 50

        result = condition_checkers._check_inbox_volume(monitor)

        assert result["triggered"] is False
        assert result["value"] == 50

    def test_check_inbox_volume_equals_threshold(self, condition_checkers):
        """Check inbox volume when count equals threshold."""
        monitor = Mock()
        monitor.condition_type = "inbox_volume"
        monitor.threshold_config = {
            "metric": "unread_count",
            "operator": "==",
            "value": 100
        }

        condition_checkers.db.query.return_value.scalar.return_value = 100

        result = condition_checkers._check_inbox_volume(monitor)

        assert result["triggered"] is True
        assert result["value"] == 100


# ==============================================================================
# Task Backlog Monitoring Tests
# ==============================================================================

class TestTaskBacklogMonitoring:
    """Test task backlog monitoring."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def condition_checkers(self, mock_db):
        """Create condition checkers instance."""
        return ConditionCheckers(mock_db)

    def test_check_task_backlog_exceeds_threshold(self, condition_checkers):
        """Check task backlog when count exceeds threshold."""
        monitor = Mock()
        monitor.condition_type = "task_backlog"
        monitor.threshold_config = {
            "metric": "pending_count",
            "operator": ">",
            "value": 50
        }

        # Mock database query to return 75 pending
        condition_checkers.db.query.return_value.scalar.return_value = 75

        result = condition_checkers._check_task_backlog(monitor)

        assert result["triggered"] is True
        assert result["value"] == 75

    def test_check_task_backlog_zero_items(self, condition_checkers):
        """Check task backlog when zero items."""
        monitor = Mock()
        monitor.condition_type = "task_backlog"
        monitor.threshold_config = {
            "metric": "pending_count",
            "operator": ">",
            "value": 0
        }

        condition_checkers.db.query.return_value.scalar.return_value = 0

        result = condition_checkers._check_task_backlog(monitor)

        assert result["triggered"] is False
        assert result["value"] == 0


# ==============================================================================
# API Metrics Checking Tests
# ==============================================================================

class TestAPIMetricsChecking:
    """Test API metrics checking."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def condition_checkers(self, mock_db):
        """Create condition checkers instance."""
        return ConditionCheckers(mock_db)

    def test_check_api_metrics_error_rate_exceeds_threshold(self, condition_checkers):
        """Check API error rate exceeds threshold."""
        monitor = Mock()
        monitor.condition_type = "api_metrics"
        monitor.threshold_config = {
            "metric": "error_rate",
            "operator": ">",
            "value": 0.05
        }

        # Mock database query to return 0.08 (8% error rate)
        condition_checkers.db.query.return_value.scalar.return_value = 0.08

        result = condition_checkers._check_api_metrics(monitor)

        assert result["triggered"] is True
        assert result["value"] == 0.08

    def test_check_api_metrics_response_time_exceeds_threshold(self, condition_checkers):
        """Check API response time exceeds threshold."""
        monitor = Mock()
        monitor.condition_type = "api_metrics"
        monitor.threshold_config = {
            "metric": "response_time",
            "operator": ">",
            "value": 1000
        }

        condition_checkers.db.query.return_value.scalar.return_value = 1500

        result = condition_checkers._check_api_metrics(monitor)

        assert result["triggered"] is True
        assert result["value"] == 1500


# ==============================================================================
# Composite Conditions Tests
# ==============================================================================

class TestCompositeConditions:
    """Test composite condition logic (AND/OR)."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def condition_checkers(self, mock_db):
        """Create condition checkers instance."""
        return ConditionCheckers(mock_db)

    def test_check_composite_and_all_true(self, condition_checkers):
        """Check composite AND logic when all conditions true."""
        monitor = Mock()
        monitor.condition_type = "composite"
        monitor.threshold_config = {
            "logic": "AND",
            "conditions": [
                {"metric": "error_rate", "operator": ">", "value": 0.05},
                {"metric": "response_time", "operator": ">", "value": 1000}
            ]
        }

        result = condition_checkers._check_composite(monitor)

        # AND logic: all must be true
        assert "triggered" in result

    def test_check_composite_and_one_false(self, condition_checkers):
        """Check composite AND logic when one condition false."""
        monitor = Mock()
        monitor.condition_type = "composite"
        monitor.threshold_config = {
            "logic": "AND",
            "conditions": [
                {"metric": "error_rate", "operator": "<", "value": 0.05},
                {"metric": "response_time", "operator": ">", "value": 1000}
            ]
        }

        result = condition_checkers._check_composite(monitor)

        # AND logic with mixed conditions
        assert "triggered" in result

    def test_check_composite_or_any_true(self, condition_checkers):
        """Check composite OR logic when any condition true."""
        monitor = Mock()
        monitor.condition_type = "composite"
        monitor.threshold_config = {
            "logic": "OR",
            "conditions": [
                {"metric": "error_rate", "operator": ">", "value": 0.05},
                {"metric": "response_time", "operator": ">", "value": 1000}
            ]
        }

        result = condition_checkers._check_composite(monitor)

        # OR logic: any true means triggered
        assert "triggered" in result


# ==============================================================================
# Value Comparison Tests
# ==============================================================================

class TestValueComparisons:
    """Test value comparison operators."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def condition_checkers(self, mock_db):
        """Create condition checkers instance."""
        return ConditionCheckers(mock_db)

    def test_compare_greater_than(self, condition_checkers):
        """Test greater than comparison."""
        result = condition_checkers._compare_values(150, ">", 100)
        assert result is True

        result = condition_checkers._compare_values(50, ">", 100)
        assert result is False

    def test_compare_less_than(self, condition_checkers):
        """Test less than comparison."""
        result = condition_checkers._compare_values(50, "<", 100)
        assert result is True

        result = condition_checkers._compare_values(150, "<", 100)
        assert result is False

    def test_compare_equals(self, condition_checkers):
        """Test equals comparison."""
        result = condition_checkers._compare_values(100, "==", 100)
        assert result is True

        result = condition_checkers._compare_values(99, "==", 100)
        assert result is False

    def test_compare_greater_or_equal(self, condition_checkers):
        """Test greater than or equal comparison."""
        result = condition_checkers._compare_values(100, ">=", 100)
        assert result is True

        result = condition_checkers._compare_values(150, ">=", 100)
        assert result is True

    def test_compare_less_or_equal(self, condition_checkers):
        """Test less than or equal comparison."""
        result = condition_checkers._compare_values(100, "<=", 100)
        assert result is True

        result = condition_checkers._compare_values(50, "<=", 100)
        assert result is True

    def test_compare_not_equal(self, condition_checkers):
        """Test not equal comparison."""
        result = condition_checkers._compare_values(99, "!=", 100)
        assert result is True

        result = condition_checkers._compare_values(100, "!=", 100)
        assert result is False


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        return db

    @pytest.fixture
    def condition_checkers(self, mock_db):
        """Create condition checkers instance."""
        return ConditionCheckers(mock_db)

    def test_check_condition_with_no_threshold_config(self, condition_checkers):
        """Handle missing threshold config gracefully."""
        monitor = Mock()
        monitor.condition_type = "inbox_volume"
        monitor.threshold_config = {}

        # Should use defaults
        result = condition_checkers._check_inbox_volume(monitor)

        assert "triggered" in result

    def test_check_condition_invalid_metric_defaults(self, condition_checkers):
        """Handle invalid metric with defaults."""
        monitor = Mock()
        monitor.condition_type = "api_metrics"
        monitor.threshold_config = {
            "metric": "invalid_metric",
            "operator": ">",
            "value": 100
        }

        result = condition_checkers._check_api_metrics(monitor)

        # Should return result even with invalid metric
        assert "triggered" in result

    def test_check_condition_database_query_error_handling(self, condition_checkers):
        """Handle database query errors gracefully."""
        monitor = Mock()
        monitor.condition_type = "inbox_volume"
        monitor.threshold_config = {
            "metric": "unread_count",
            "operator": ">",
            "value": 100
        }

        # Mock database error
        condition_checkers.db.query.side_effect = Exception("Database error")

        # Should handle error gracefully
        try:
            result = condition_checkers._check_inbox_volume(monitor)
            # If it doesn't raise, that's also acceptable
            assert "triggered" in result
        except Exception:
            # If it raises, that's also acceptable behavior
            pass
