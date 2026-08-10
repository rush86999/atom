"""Coverage wave 16 — ProviderRateTracker sliding-window rate limiting (TDD)."""
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.llm.provider_rate_limits import (
    ProviderRateTracker,
    _env_int,
)


def _tracker(**limits):
    with patch(
        "core.llm.provider_rate_limits.PROVIDER_RATE_LIMITS",
        {"opencode-go": {"rpm": 60, "tpm": 2000000, "max_context": 200000}},
    ):
        tracker = ProviderRateTracker()
    if limits:
        tracker.set_rate_limits("custom", **limits)
    return tracker


def _entry(dt, inp=100, out=50, model="m1"):
    return (dt, inp, out, model)


class TestEnvInt:
    def test_valid(self):
        with patch.dict("os.environ", {"X": "42"}):
            assert _env_int("X", 1) == 42

    def test_invalid(self):
        with patch.dict("os.environ", {"X": "abc"}):
            assert _env_int("X", 7) == 7

    def test_missing(self):
        assert _env_int("NOT_SET_AT_ALL", 3) == 3


class TestRateLimits:
    def test_set_and_get(self):
        t = _tracker()
        t.set_rate_limits("openai", rpm=100, tpm=5000, max_context=16000)
        limits = t.get_rate_limits("openai")
        assert limits["rpm"] == 100
        assert limits["tpm"] == 5000
        assert limits["max_context"] == 16000

    def test_get_unconfigured_empty(self):
        t = _tracker()
        assert t.get_rate_limits("ghost") == {}

    def test_max_context(self):
        t = _tracker()
        t.set_rate_limits("openai", max_context=64000)
        assert t.get_max_context("openai") == 64000
        assert t.get_max_context("ghost") is None
        t.set_rate_limits("openai", max_context=0)
        assert t.get_max_context("openai") is None


class TestRecordUsage:
    def test_records_only_when_limits_configured(self):
        t = _tracker()
        t.record_usage("ghost", 100, 100)  # no limits -> no-op
        assert t.get_headroom("ghost") == 1.0

    def test_records_and_tracks(self):
        t = _tracker()
        t.record_usage("opencode-go", 1000, 500, model_id="deepseek-v4-flash")
        requests, tokens = t._window_totals("opencode-go")
        assert requests == 1
        assert tokens == 1500 * 1.0  # weight 1.0 default

    def test_persistence_recorded(self):
        t = _tracker()
        persistence = MagicMock()
        t.set_persistence(persistence)
        t.record_usage("opencode-go", 10, 5, model_id="m")
        persistence.record.assert_called_once_with("opencode-go", "m", 10, 5)

    def test_persistence_error_tolerated(self):
        t = _tracker()
        persistence = MagicMock()
        persistence.record.side_effect = RuntimeError("db down")
        t.set_persistence(persistence)
        t.record_usage("opencode-go", 10, 5)  # no raise


class TestWindowTotals:
    def test_trim_expired(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        old = now - timedelta(seconds=200)  # beyond 60s window
        t._usage["p"] = deque([
            _entry(old, 100, 100, "m1"),
            _entry(now, 100, 100, "m1"),
        ])
        t._trim("p", now)
        assert len(t._usage["p"]) == 1

    def test_legacy_3_tuples_read(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        t._usage["p"] = deque([(now, 100, 50)])  # legacy tuple
        requests, tokens = t._window_totals("p")
        assert requests == 1
        assert tokens == 150

    def test_model_filter(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        t._usage["p"] = deque([
            _entry(now, 100, 0, "m1"),
            _entry(now, 50, 0, "m2"),
        ])
        requests, tokens = t._window_totals("p", model_id="m2")
        assert requests == 1
        assert tokens == 50


class TestHeadroom:
    def test_no_limits_full(self):
        t = _tracker()
        assert t.get_headroom("ghost") == 1.0

    def test_rpm_consumption(self):
        t = _tracker()
        t.set_rate_limits("custom", rpm=10, tpm=0)
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 0, 0, "m") for _ in range(5)]
        assert t.get_headroom("custom") == pytest.approx(0.5)

    def test_tpm_consumption_weighted(self):
        t = _tracker()
        t.set_rate_limits("custom", rpm=0, tpm=1000)
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 400, 0, "m")]
        t._model_weight = lambda p, m: 1.0  # type: ignore[assignment]
        assert t.get_headroom("custom") == pytest.approx(0.6)

    def test_exhausted_zero(self):
        t = _tracker()
        t.set_rate_limits("custom", rpm=2, tpm=100)
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 60, 0, "m") for _ in range(2)]
        assert t.get_headroom("custom") == 0.0

    def test_headroom_from_static(self):
        assert ProviderRateTracker._headroom_from(5, 0, 10, 0) == 0.5
        assert ProviderRateTracker._headroom_from(0, 500, 0, 1000) == 0.5
        assert ProviderRateTracker._headroom_from(0, 0, 0, 0) == 1.0

    def test_model_headroom_falls_back(self):
        t = _tracker()
        t.set_rate_limits("custom", rpm=10, tpm=0)
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 0, 0, "m") for _ in range(5)]
        assert t.get_model_headroom("custom", None) == pytest.approx(0.5)
        assert t.get_model_headroom("custom", "any-model") == pytest.approx(0.5)


class TestModelLimits:
    def test_model_rate_limits_with_registry(self):
        t = _tracker()
        registry = MagicMock()
        registry.get_model_rate_limits.return_value = {"rpm": 5, "tpm": 100}
        t._model_registry = registry
        assert t.get_model_rate_limits("p", "m") == {"rpm": 5, "tpm": 100}

    def test_model_rate_limits_no_registry(self):
        t = _tracker()
        assert t.get_model_rate_limits("p", "m") == {}

    def test_model_weight(self):
        t = _tracker()
        registry = MagicMock()
        registry.get_weight.return_value = 3.0
        t._model_registry = registry
        assert t.get_model_weight("p", "m") == 3.0
        assert t.get_model_weight("p", "m") == 3.0  # cached registry

    def test_model_weight_error_falls_back(self):
        t = _tracker()
        registry = MagicMock()
        registry.get_weight.side_effect = RuntimeError("boom")
        t._model_registry = registry
        assert t.get_model_weight("p", "m") == 1.0

    def test_model_weight_no_registry(self):
        t = _tracker()
        assert t.get_model_weight("p", "m") == 1.0

    def test_set_model_limits(self):
        t = _tracker()
        registry = MagicMock()
        t._model_registry = registry
        t.set_model_limits("p", "m", weight=2.0, rpm=5)
        registry.set_model_limits.assert_called_once_with(
            "p", "m", weight=2.0, rpm=5, tpm=None
        )

    def test_model_headroom_with_own_limits(self):
        t = _tracker()
        registry = MagicMock()
        registry.get_model_rate_limits.return_value = {"rpm": 4}
        t._model_registry = registry
        t.set_rate_limits("custom", rpm=1000, tpm=0)  # provider budget big
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 0, 0, "m") for _ in range(2)]
        assert t.get_model_headroom("custom", "m") == pytest.approx(0.5)


class TestMonthlyUsage:
    def test_no_persistence_none(self):
        t = _tracker()
        assert t.get_monthly_usage("p") is None

    def test_with_persistence(self):
        t = _tracker()
        persistence = MagicMock()
        persistence.monthly_usage.return_value = {"total_tokens": 500}
        t.set_persistence(persistence)
        assert t.get_monthly_usage("p") == {"total_tokens": 500}

    def test_persistence_error_none(self):
        t = _tracker()
        persistence = MagicMock()
        persistence.monthly_usage.side_effect = RuntimeError("db down")
        t.set_persistence(persistence)
        assert t.get_monthly_usage("p") is None
