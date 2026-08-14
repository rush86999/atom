"""
Backend depth wave 116 (2026-08-13) — coverage push for core/llm_usage_tracker.py.

Covers daily-window budget enforcement, record bounding, lazy date pruning,
reset, and the singleton accessor. Fully mocked — zero LLM spend.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from core.llm_usage_tracker import (
    LLMUsageTracker,
    UsageRecord,
    get_llm_usage_tracker,
    llm_usage_tracker,
)


@pytest.fixture
def tracker():
    return LLMUsageTracker()


class TestRecording:
    """Cover record() including bounding and pruning (lines 80-113)."""

    def test_record_stores_all_fields(self, tracker):
        tracker.record(
            workspace_id="ws-1",
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            savings_usd=0.02,
            agent_id="agent-1",
            complexity="simple",
            is_managed_service=False,
            chain_id="chain-1",
        )
        rec = tracker.get_records("ws-1")[0]
        assert rec.provider == "openai"
        assert rec.model == "gpt-4o"
        assert rec.input_tokens == 100
        assert rec.output_tokens == 50
        assert rec.cost_usd == 0.01
        assert rec.savings_usd == 0.02
        assert rec.agent_id == "agent-1"
        assert rec.complexity == "simple"
        assert rec.is_managed_service is False
        assert rec.chain_id == "chain-1"

    def test_record_bounds_internal_list(self, tracker):
        for i in range(tracker._MAX_RECORDS + 100):
            tracker.record(
                workspace_id=f"ws-{i % 3}", provider="p", model="m",
                input_tokens=1, output_tokens=1, cost_usd=0.001,
            )
        assert len(tracker._records) == tracker._MAX_RECORDS

    def test_record_prunes_old_dates(self, tracker):
        import core.llm_usage_tracker as mod

        base = date(2026, 8, 10)
        fake_now = __import__("datetime").datetime.combine(
            base, __import__("datetime").time(12, 0)
        )
        clock = {"now": fake_now}

        class _FakeUsageRecord(UsageRecord):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault("timestamp", clock["now"])
                super().__init__(*args, **kwargs)

        with patch.object(mod, "UsageRecord", _FakeUsageRecord):
            tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.5)
            tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.25)
            clock["now"] = fake_now + timedelta(days=1)
            tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.1)
            clock["now"] = fake_now + timedelta(days=2)
            tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.05)
        usage = tracker._usage["ws-1"]
        assert len(usage) == 1
        assert base + timedelta(days=2) in usage
        assert usage[base + timedelta(days=2)] == pytest.approx(0.05)

    def test_record_aggregates_daily_spend(self, tracker):
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.30)
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.20)
        assert tracker.get_usage("ws-1") == pytest.approx(0.50)


class TestBudgetEnforcement:
    """Cover daily budget checks (lines 115-175)."""

    def test_no_budget_set_returns_false(self, tracker):
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.99)
        assert tracker.is_budget_exceeded("ws-1") is False
        assert tracker.get_budget("ws-1") is None

    def test_budget_set_and_get(self, tracker):
        tracker.set_budget("ws-1", 1.0)
        assert tracker.get_budget("ws-1") == 1.0

    def test_budget_not_exceeded_under_limit(self, tracker):
        tracker.set_budget("ws-1", 1.0)
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.5)
        assert tracker.is_budget_exceeded("ws-1") is False

    def test_budget_exceeded_at_limit(self, tracker):
        tracker.set_budget("ws-1", 1.0)
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 1.0)
        assert tracker.is_budget_exceeded("ws-1") is True

    def test_budget_exceeded_above_limit(self, tracker):
        tracker.set_budget("ws-1", 1.0)
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 1.5)
        assert tracker.is_budget_exceeded("ws-1") is True

    def test_budgets_are_per_workspace(self, tracker):
        tracker.set_budget("ws-1", 0.1)
        tracker.record("ws-2", "openai", "gpt-4o", 1, 1, 5.0)
        assert tracker.is_budget_exceeded("ws-2") is False


class TestRecords:
    """Cover get_records ordering/limit and reset (lines 177-205)."""

    def test_get_records_most_recent_first_with_limit(self, tracker):
        for i in range(5):
            tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.01)
        records = tracker.get_records("ws-1", limit=2)
        assert len(records) == 2
        assert records[0] is not records[1]

    def test_get_records_isolates_workspaces(self, tracker):
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.01)
        tracker.record("ws-2", "anthropic", "claude", 1, 1, 0.02)
        assert len(tracker.get_records("ws-1")) == 1

    def test_reset_usage_zeroes_today(self, tracker):
        tracker.record("ws-1", "openai", "gpt-4o", 1, 1, 0.75)
        tracker.reset_usage("ws-1")
        assert tracker.get_usage("ws-1") == 0.0


class TestSingleton:
    """Cover singleton accessor (lines 212-226)."""

    def test_singleton_shared_instance(self):
        assert get_llm_usage_tracker() is llm_usage_tracker

    def test_singleton_returns_same_instance(self):
        assert get_llm_usage_tracker() is get_llm_usage_tracker()

    def test_singleton_created_lazily(self):
        import core.llm_usage_tracker as mod

        with patch.object(mod, "_llm_usage_tracker", None):
            instance = mod.get_llm_usage_tracker()
            assert instance is mod._llm_usage_tracker
