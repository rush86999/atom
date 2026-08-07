"""Unit tests for the per-call LLM provider usage tracker.

Covers ``core/llm_call_tracker.py``: the 10-field per-call record
(timestamp, provider, model, success, latency_ms, input_tokens,
output_tokens, fallback, fallback_provider, error), the bounded
in-memory buffer, Prometheus metric emission, and summary aggregation.
"""
from datetime import datetime, timezone

import pytest
from prometheus_client import REGISTRY

from core.llm_call_tracker import (
    LLMCallRecord,
    LLMCallTracker,
)


def get_sample_value(name: str, labels: dict):
    return REGISTRY.get_sample_value(name, labels)


def make_tracker(maxlen: int = 100) -> LLMCallTracker:
    tracker = LLMCallTracker(maxlen=maxlen)
    tracker.clear()
    return tracker


class TestRecord:
    def test_success_record_populates_all_fields(self):
        tracker = make_tracker()
        tracker.record(
            provider="opencode-go",
            model="gpt-5",
            success=True,
            latency_ms=4200.0,
            input_tokens=1200,
            output_tokens=800,
        )
        calls = tracker.get_recent_calls()
        assert len(calls) == 1
        rec = calls[0]
        assert isinstance(rec, LLMCallRecord)
        assert rec.provider == "opencode-go"
        assert rec.model == "gpt-5"
        assert rec.success is True
        assert rec.latency_ms == 4200.0
        assert rec.input_tokens == 1200
        assert rec.output_tokens == 800
        assert rec.fallback is False
        assert rec.fallback_provider is None
        assert rec.error is None
        # Timestamp: aware datetime, roughly now.
        assert isinstance(rec.timestamp, datetime)
        assert rec.timestamp.tzinfo is not None
        delta = abs((datetime.now(timezone.utc) - rec.timestamp).total_seconds())
        assert delta < 30

    def test_failure_record_with_fallback_and_error(self):
        tracker = make_tracker()
        tracker.record(
            provider="deepseek",
            model="deepseek-chat",
            success=False,
            latency_ms=1500.0,
            fallback=True,
            fallback_provider="opencode-go",
            error="Rate limit exceeded",
        )
        rec = tracker.get_recent_calls()[0]
        assert rec.success is False
        assert rec.fallback is True
        assert rec.fallback_provider == "opencode-go"
        assert rec.error == "Rate limit exceeded"

    def test_defaults_for_missing_tokens_and_latency(self):
        tracker = make_tracker()
        tracker.record(provider="openai", model="gpt-4o", success=True)
        rec = tracker.get_recent_calls()[0]
        assert rec.latency_ms == 0.0
        assert rec.input_tokens == 0
        assert rec.output_tokens == 0
        assert rec.fallback is False

    def test_null_success_counts_as_failure(self):
        tracker = make_tracker()
        tracker.record(provider="openai", model="gpt-4o", success=None)
        assert tracker.get_recent_calls()[0].success is False

    def test_negative_tokens_clamped_to_zero(self):
        tracker = make_tracker()
        tracker.record(
            provider="openai", model="gpt-4o", success=True,
            input_tokens=-5, output_tokens=-3,
        )
        rec = tracker.get_recent_calls()[0]
        assert rec.input_tokens == 0
        assert rec.output_tokens == 0

    def test_buffer_is_bounded_most_recent_kept(self):
        tracker = make_tracker(maxlen=5)
        for i in range(20):
            tracker.record(provider="openai", model="gpt-4o", success=True,
                           input_tokens=i, output_tokens=0)
        calls = tracker.get_recent_calls()
        assert len(calls) == 5
        # Most recent records (i=19..15) survive; i=19 is the newest.
        assert calls[0].input_tokens == 19
        assert calls[-1].input_tokens == 15


class TestQueries:
    def test_filter_by_provider(self):
        tracker = make_tracker()
        tracker.record(provider="opencode-go", model="gpt-5", success=True)
        tracker.record(provider="openai", model="gpt-4o", success=True)
        calls = tracker.get_recent_calls(provider="opencode-go")
        assert len(calls) == 1
        assert calls[0].provider == "opencode-go"

    def test_filter_by_model(self):
        tracker = make_tracker()
        tracker.record(provider="opencode-go", model="gpt-5", success=True)
        tracker.record(provider="openai", model="gpt-5", success=True)
        tracker.record(provider="openai", model="gpt-4o", success=True)
        calls = tracker.get_recent_calls(model="gpt-5")
        assert len(calls) == 2

    def test_limit_clamped(self):
        tracker = make_tracker()
        for i in range(10):
            tracker.record(provider="openai", model="gpt-4o", success=True)
        calls = tracker.get_recent_calls(limit=3)
        assert len(calls) == 3

    def test_clear_empties_buffer(self):
        tracker = make_tracker()
        tracker.record(provider="openai", model="gpt-4o", success=True)
        tracker.clear()
        assert tracker.get_recent_calls() == []


class TestSummary:
    def test_summary_aggregates_counts_latency_tokens(self):
        tracker = make_tracker()
        tracker.record(provider="opencode-go", model="gpt-5", success=True,
                       latency_ms=1000.0, input_tokens=100, output_tokens=50)
        tracker.record(provider="opencode-go", model="gpt-5", success=True,
                       latency_ms=3000.0, input_tokens=200, output_tokens=100)
        tracker.record(provider="opencode-go", model="gpt-5", success=False,
                       latency_ms=500.0, fallback=True,
                       fallback_provider="openai", error="boom")
        tracker.record(provider="openai", model="gpt-4o", success=True,
                       latency_ms=2000.0, input_tokens=10, output_tokens=5)
        summary = tracker.get_summary()
        assert summary["total_calls"] == 4
        assert summary["successful_calls"] == 3
        assert summary["failed_calls"] == 1
        assert summary["fallback_calls"] == 1
        assert summary["total_input_tokens"] == 310
        assert summary["total_output_tokens"] == 155
        # avg latency over all 4 calls: (1000+3000+500+2000)/4
        assert summary["avg_latency_ms"] == pytest.approx(1625.0)
        # Per-provider rollup.
        og = summary["by_provider"]["opencode-go"]
        assert og["total_calls"] == 3
        assert og["successful_calls"] == 2
        assert og["failed_calls"] == 1
        assert og["fallback_calls"] == 1
        assert og["total_input_tokens"] == 300
        assert og["total_output_tokens"] == 150
        # Per-model rollup.
        g5 = summary["by_model"]["gpt-5"]
        assert g5["total_calls"] == 3
        assert g5["avg_latency_ms"] == pytest.approx(1500.0)

    def test_summary_empty(self):
        summary = make_tracker().get_summary()
        assert summary["total_calls"] == 0
        assert summary["by_provider"] == {}
        assert summary["by_model"] == {}

    def test_summary_filters(self):
        tracker = make_tracker()
        tracker.record(provider="opencode-go", model="gpt-5", success=True)
        tracker.record(provider="openai", model="gpt-4o", success=True)
        summary = tracker.get_summary(provider="opencode-go")
        assert summary["total_calls"] == 1
        assert list(summary["by_provider"].keys()) == ["opencode-go"]


class TestPrometheusMetrics:
    def test_success_emits_counters_and_histogram(self):
        tracker = make_tracker()
        tracker.record(provider="oc-metric", model="gpt-5-m", success=True,
                       latency_ms=4200.0, input_tokens=1200, output_tokens=800)
        assert get_sample_value(
            "llm_calls_total",
            {"provider": "oc-metric", "model": "gpt-5-m",
             "success": "true", "fallback": "false"},
        ) == 1.0
        assert get_sample_value(
            "llm_tokens_total",
            {"provider": "oc-metric", "model": "gpt-5-m", "direction": "input"},
        ) == 1200.0
        assert get_sample_value(
            "llm_tokens_total",
            {"provider": "oc-metric", "model": "gpt-5-m", "direction": "output"},
        ) == 800.0
        # Histogram: one observation in the 5s bucket.
        assert get_sample_value(
            "llm_call_duration_seconds_count",
            {"provider": "oc-metric", "model": "gpt-5-m"},
        ) == 1.0

    def test_failure_emits_error_and_calls_counters(self):
        tracker = make_tracker()
        tracker.record(provider="ds-metric", model="ds-chat-m", success=False,
                       latency_ms=1500.0, fallback=True,
                       fallback_provider="oc-fallback-m", error="boom")
        assert get_sample_value(
            "llm_calls_total",
            {"provider": "ds-metric", "model": "ds-chat-m",
             "success": "false", "fallback": "true"},
        ) == 1.0
        assert get_sample_value(
            "llm_call_errors_total",
            {"provider": "ds-metric", "model": "ds-chat-m"},
        ) == 1.0
        assert get_sample_value(
            "llm_fallbacks_total",
            {"provider": "ds-metric", "fallback_provider": "oc-fallback-m"},
        ) == 1.0

    def test_calls_counter_accumulates(self):
        tracker = make_tracker()
        for _ in range(3):
            tracker.record(provider="oa-metric", model="gpt-4o-m", success=True)
        assert get_sample_value(
            "llm_calls_total",
            {"provider": "oa-metric", "model": "gpt-4o-m",
             "success": "true", "fallback": "false"},
        ) == 3.0


class TestSingleton:
    def test_get_llm_call_tracker_returns_same_instance(self):
        from core.llm_call_tracker import get_llm_call_tracker
        assert get_llm_call_tracker() is get_llm_call_tracker()
