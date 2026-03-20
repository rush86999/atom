"""
Tests for LLM Usage Tracker

Tests cover:
- Recording LLM usage events
- Budget management and enforcement
- Usage tracking and retrieval
- Thread-safety
- Edge cases
"""

import pytest
from datetime import datetime
from core.llm_usage_tracker import (
    UsageRecord,
    LLMUsageTracker,
    get_llm_usage_tracker,
    llm_usage_tracker,
)


class TestUsageRecord:
    """Test UsageRecord dataclass."""

    def test_usage_record_creation(self):
        """Test creating a usage record with all fields."""
        record = UsageRecord(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
            savings_usd=0.005,
            agent_id="agent-1",
            complexity="high",
            is_managed_service=True,
        )

        assert record.workspace_id == "ws-1"
        assert record.provider == "openai"
        assert record.model == "gpt-4o"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.cost_usd == 0.01
        assert record.savings_usd == 0.005
        assert record.agent_id == "agent-1"
        assert record.complexity == "high"
        assert record.is_managed_service is True
        assert isinstance(record.timestamp, datetime)

    def test_usage_record_defaults(self):
        """Test usage record with default values."""
        record = UsageRecord(
            workspace_id="ws-1",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=500,
            output_tokens=300,
            cost_usd=0.005,
        )

        assert record.savings_usd == 0.0
        assert record.agent_id is None
        assert record.complexity == "moderate"
        assert record.is_managed_service is True
        assert isinstance(record.timestamp, datetime)


class TestLLMUsageTracker:
    """Test LLMUsageTracker class."""

    def test_tracker_initialization(self):
        """Test tracker initializes with empty state."""
        tracker = LLMUsageTracker()

        assert tracker._records == []
        assert tracker._budgets == {}
        assert tracker._usage == {}

    def test_record_basic_usage(self):
        """Test recording a basic usage event."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
        )

        assert len(tracker._records) == 1
        assert tracker._usage["ws-1"] == 0.01
        assert tracker._records[0].workspace_id == "ws-1"
        assert tracker._records[0].provider == "openai"

    def test_record_multiple_usage_same_workspace(self):
        """Test recording multiple usage events for same workspace."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
        )

        tracker.record(
            workspace_id="ws-1",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=800,
            output_tokens=400,
            cost_usd=0.008,
        )

        assert len(tracker._records) == 2
        assert tracker._usage["ws-1"] == pytest.approx(0.018)

    def test_record_multiple_workspaces(self):
        """Test recording usage for multiple workspaces."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
        )

        tracker.record(
            workspace_id="ws-2",
            provider="openai",
            model="gpt-4o",
            input_tokens=2000,
            output_tokens=1000,
            cost_usd=0.02,
        )

        assert len(tracker._records) == 2
        assert tracker._usage["ws-1"] == 0.01
        assert tracker._usage["ws-2"] == 0.02

    def test_set_budget(self):
        """Test setting budget for workspace."""
        tracker = LLMUsageTracker()

        tracker.set_budget("ws-1", 100.0)

        assert tracker._budgets["ws-1"] == 100.0

    def test_set_budget_multiple_workspaces(self):
        """Test setting budgets for multiple workspaces."""
        tracker = LLMUsageTracker()

        tracker.set_budget("ws-1", 100.0)
        tracker.set_budget("ws-2", 50.0)

        assert tracker._budgets["ws-1"] == 100.0
        assert tracker._budgets["ws-2"] == 50.0

    def test_is_budget_exceeded_no_budget(self):
        """Test budget check when no budget is set."""
        tracker = LLMUsageTracker()

        assert tracker.is_budget_exceeded("ws-1") is False

    def test_is_budget_exceeded_within_budget(self):
        """Test budget check when within budget."""
        tracker = LLMUsageTracker()

        tracker.set_budget("ws-1", 100.0)
        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=10.0,
        )

        assert tracker.is_budget_exceeded("ws-1") is False

    def test_is_budget_exceeded_at_limit(self):
        """Test budget check when exactly at budget limit."""
        tracker = LLMUsageTracker()

        tracker.set_budget("ws-1", 100.0)
        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=100.0,
        )

        assert tracker.is_budget_exceeded("ws-1") is True

    def test_is_budget_exceeded_over_budget(self):
        """Test budget check when over budget."""
        tracker = LLMUsageTracker()

        tracker.set_budget("ws-1", 100.0)
        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=150.0,
        )

        assert tracker.is_budget_exceeded("ws-1") is True

    def test_get_usage_no_usage(self):
        """Test getting usage when no usage recorded."""
        tracker = LLMUsageTracker()

        assert tracker.get_usage("ws-1") == 0.0

    def test_get_usage_with_records(self):
        """Test getting usage with recorded usage."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=10.0,
        )

        tracker.record(
            workspace_id="ws-1",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=800,
            output_tokens=400,
            cost_usd=5.0,
        )

        assert tracker.get_usage("ws-1") == 15.0

    def test_get_budget_no_budget(self):
        """Test getting budget when no budget set."""
        tracker = LLMUsageTracker()

        assert tracker.get_budget("ws-1") is None

    def test_get_budget_with_budget(self):
        """Test getting budget when budget is set."""
        tracker = LLMUsageTracker()

        tracker.set_budget("ws-1", 100.0)

        assert tracker.get_budget("ws-1") == 100.0

    def test_get_records_no_records(self):
        """Test getting records when no records exist."""
        tracker = LLMUsageTracker()

        records = tracker.get_records("ws-1")

        assert records == []

    def test_get_records_with_records(self):
        """Test getting records with existing records."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
            agent_id="agent-1",
        )

        tracker.record(
            workspace_id="ws-1",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=800,
            output_tokens=400,
            cost_usd=0.008,
            agent_id="agent-2",
        )

        records = tracker.get_records("ws-1")

        assert len(records) == 2
        # Should return most recent first
        assert records[0].agent_id == "agent-2"
        assert records[1].agent_id == "agent-1"

    def test_get_records_with_limit(self):
        """Test getting records with limit."""
        tracker = LLMUsageTracker()

        for i in range(10):
            tracker.record(
                workspace_id="ws-1",
                provider="openai",
                model="gpt-4o",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.01,
            )

        records = tracker.get_records("ws-1", limit=5)

        assert len(records) == 5

    def test_get_records_filters_by_workspace(self):
        """Test that get_records only returns records for specified workspace."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
        )

        tracker.record(
            workspace_id="ws-2",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
        )

        ws1_records = tracker.get_records("ws-1")
        ws2_records = tracker.get_records("ws-2")

        assert len(ws1_records) == 1
        assert len(ws2_records) == 1
        assert ws1_records[0].workspace_id == "ws-1"
        assert ws2_records[0].workspace_id == "ws-2"

    def test_reset_usage(self):
        """Test resetting usage for workspace."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=100.0,
        )

        assert tracker.get_usage("ws-1") == 100.0

        tracker.reset_usage("ws-1")

        assert tracker.get_usage("ws-1") == 0.0

    def test_reset_usage_nonexistent_workspace(self):
        """Test resetting usage for workspace with no usage."""
        tracker = LLMUsageTracker()

        tracker.reset_usage("ws-1")

        assert tracker.get_usage("ws-1") == 0.0

    def test_record_with_all_optional_fields(self):
        """Test recording usage with all optional fields."""
        tracker = LLMUsageTracker()

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
            savings_usd=0.005,
            agent_id="agent-1",
            complexity="high",
            is_managed_service=False,
        )

        record = tracker._records[0]

        assert record.savings_usd == 0.005
        assert record.agent_id == "agent-1"
        assert record.complexity == "high"
        assert record.is_managed_service is False

    def test_budget_enforcement_across_workspaces(self):
        """Test that budget is tracked independently per workspace."""
        tracker = LLMUsageTracker()

        tracker.set_budget("ws-1", 10.0)
        tracker.set_budget("ws-2", 20.0)

        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=15.0,
        )

        tracker.record(
            workspace_id="ws-2",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=15.0,
        )

        assert tracker.is_budget_exceeded("ws-1") is True
        assert tracker.is_budget_exceeded("ws-2") is False


class TestGlobalLLMUsageTracker:
    """Test global LLM usage tracker singleton."""

    def test_get_llm_usage_tracker_singleton(self):
        """Test that get_llm_usage_tracker returns same instance."""
        tracker1 = get_llm_usage_tracker()
        tracker2 = get_llm_usage_tracker()

        assert tracker1 is tracker2

    def test_llm_usage_tracker_module_export(self):
        """Test that module-level export is singleton instance."""
        tracker = get_llm_usage_tracker()

        # Module export should be same instance
        assert llm_usage_tracker is tracker

    def test_global_tracker_persists_state(self):
        """Test that global tracker persists state across calls."""
        tracker = get_llm_usage_tracker()

        tracker.record(
            workspace_id="test-ws",
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=5.0,
        )

        tracker2 = get_llm_usage_tracker()

        assert tracker2.get_usage("test-ws") == 5.0
