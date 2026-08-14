"""Coverage wave 77a — LLM compression/quality/rate-limit stack (standalone-certifying suite).

Before % (measured against pre-existing suites in this repo):
  core/llm/compression/rtk_engine.py         100% (w32; re-verified)
  core/llm/compression/session_dedup.py      100% (w32; re-verified)
  core/llm/response_quality.py               100% (w35; re-verified)
  core/llm/canvas_summary_service.py         100% (w36/w37; re-verified)
  core/llm/provider_rate_limits.py            96%  (lines 161-162, 191-192,
                                                    256, 273, 357-358 — filled here)
  core/llm/opencode_model_limits.py          100% (w17; re-verified)

Notes:
- ``test_covpush_gateway_wave10b.test_singleton_creation`` uses a stale
  ``from X import _rate_tracker`` binding (rebinding the imported name does NOT
  reset the module global), so lines 357-358 were still uncovered; this suite
  resets the singleton via module-attribute access.
- All LLM calls are mocked; no network, no DB, no LLM spend.
"""
import asyncio
import hashlib
import json
from collections import deque
from datetime import datetime, timedelta, timezone
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.llm.provider_rate_limits as prl_mod
from core.llm.canvas_summary_service import CanvasSummaryService
from core.llm.compression.rtk_engine import RTKEngine
from core.llm.compression.session_dedup import (
    DEDUP_MIN_CHUNK_CHARS,
    SessionDedupIndex,
    get_or_create_dedup_index,
)
from core.llm.opencode_model_limits import (
    OPCODE_DEFAULT_MODEL_WEIGHTS,
    OpencodeModelLimits,
    get_opencode_model_limits,
    weight_from_prices,
)
from core.llm.provider_rate_limits import (
    PROVIDER_RATE_LIMITS,
    ProviderRateTracker,
    _env_int,
)
from core.llm.response_quality import ResponseQuality, _classify_exception, assess_response_quality


# ============================================================================
# provider_rate_limits.py
# ============================================================================

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


class TestProviderEnvInt:
    def test_valid(self):
        with patch.dict("os.environ", {"PRL_X": "42"}):
            assert _env_int("PRL_X", 1) == 42

    def test_invalid(self):
        with patch.dict("os.environ", {"PRL_X": "abc"}):
            assert _env_int("PRL_X", 7) == 7

    def test_missing(self):
        assert _env_int("PRL_NOT_SET_AT_ALL", 3) == 3

    def test_build_provider_defaults_present(self):
        assert "opencode-go" in PROVIDER_RATE_LIMITS
        assert "openrouter" in PROVIDER_RATE_LIMITS


class TestProviderRateLimits:
    def test_set_and_get(self):
        t = _tracker()
        t.set_rate_limits("openai", rpm=100, tpm=5000, max_context=16000)
        limits = t.get_rate_limits("openai")
        assert limits["rpm"] == 100
        assert limits["tpm"] == 5000
        assert limits["max_context"] == 16000

    def test_set_partial_fields(self):
        t = _tracker()
        t.set_rate_limits("openai", rpm=100)
        limits = t.get_rate_limits("openai")
        assert limits == {"rpm": 100}

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


class TestProviderRecordUsage:
    def test_records_only_when_limits_configured(self):
        t = _tracker()
        t.record_usage("ghost", 100, 100)
        assert t.get_headroom("ghost") == 1.0

    def test_records_and_tracks(self):
        t = _tracker()
        t.record_usage("opencode-go", 1000, 500, model_id="deepseek-v4-flash")
        requests, tokens = t._window_totals("opencode-go")
        assert requests == 1
        assert tokens == 1500 * 1.0

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
        t.record_usage("opencode-go", 10, 5)

    def test_record_conversion_error_tolerated(self):
        """int() of a non-numeric token count is swallowed (lines 191-192)."""
        t = _tracker()
        t.record_usage("opencode-go", "abc", 5)
        assert t._window_totals("opencode-go") == (0, 0.0)


class TestProviderWindowTotals:
    def test_trim_expired(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        old = now - timedelta(seconds=200)
        t._usage["p"] = deque([_entry(old, 100, 100, "m1"), _entry(now, 100, 100, "m1")])
        t._trim("p", now)
        assert len(t._usage["p"]) == 1

    def test_legacy_3_tuples_read(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        t._usage["p"] = deque([(now, 100, 50)])
        requests, tokens = t._window_totals("p")
        assert requests == 1
        assert tokens == 150

    def test_model_filter(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        t._usage["p"] = deque([_entry(now, 100, 0, "m1"), _entry(now, 50, 0, "m2")])
        requests, tokens = t._window_totals("p", model_id="m2")
        assert requests == 1
        assert tokens == 50

    def test_unweighted_totals(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        t._usage["p"] = deque([_entry(now, 100, 100, "m1")])
        t._model_weight = lambda p, m: 5.0  # type: ignore[assignment]
        requests, tokens = t._window_totals("p", weighted=False)
        assert requests == 1
        assert tokens == 200


class TestProviderHeadroom:
    def test_no_limits_full(self):
        t = _tracker()
        assert t.get_headroom("ghost") == 1.0

    def test_zero_limits_returns_full(self):
        """Provider limits dict with rpm/tpm both <= 0 -> 1.0 (line 256)."""
        t = _tracker()
        t.set_rate_limits("custom", rpm=0, tpm=0)
        assert t.get_headroom("custom") == 1.0
        t2 = _tracker()
        t2.set_rate_limits("custom", max_context=100)
        assert t2.get_headroom("custom") == 1.0

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
        assert ProviderRateTracker._headroom_from(20, 0, 10, 0) == 0.0

    def test_model_headroom_falls_back(self):
        t = _tracker()
        t.set_rate_limits("custom", rpm=10, tpm=0)
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 0, 0, "m") for _ in range(5)]
        assert t.get_model_headroom("custom", None) == pytest.approx(0.5)
        assert t.get_model_headroom("custom", "any-model") == pytest.approx(0.5)


class TestProviderModelLimits:
    def test_model_rate_limits_with_registry(self):
        t = _tracker()
        registry = MagicMock()
        registry.get_model_rate_limits.return_value = {"rpm": 5, "tpm": 100}
        t._model_registry = registry
        assert t.get_model_rate_limits("p", "m") == {"rpm": 5, "tpm": 100}

    def test_model_rate_limits_no_registry(self):
        t = _tracker()
        assert t.get_model_rate_limits("p", "m") == {}

    def test_model_rate_limits_registry_error_returns_empty(self):
        """Registry lookup raising is tolerated (lines 161-162)."""
        t = _tracker()
        registry = MagicMock()
        registry.get_model_rate_limits.side_effect = RuntimeError("boom")
        t._model_registry = registry
        assert t.get_model_rate_limits("p", "m") == {}

    def test_model_weight(self):
        t = _tracker()
        registry = MagicMock()
        registry.get_weight.return_value = 3.0
        t._model_registry = registry
        assert t.get_model_weight("p", "m") == 3.0

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
        registry.set_model_limits.assert_called_once_with("p", "m", weight=2.0, rpm=5, tpm=None)

    def test_set_model_limits_no_registry_noop(self):
        t = _tracker()
        with patch(
            "core.llm.opencode_model_limits.get_opencode_model_limits",
            side_effect=RuntimeError("import boom"),
        ):
            t.set_model_limits("p", "m", weight=2.0)  # registry None -> no-op

    def test_registry_lazy_import_failure(self):
        """_registry() except path: per-model registry unavailable (line 122)."""
        t = _tracker()
        with patch(
            "core.llm.opencode_model_limits.get_opencode_model_limits",
            side_effect=RuntimeError("import boom"),
        ):
            assert t._registry() is None
            assert t.get_model_rate_limits("p", "m") == {}
            assert t.get_model_weight("p", "m") == 1.0

    def test_registry_lazy_import_success(self):
        t = _tracker()
        t._model_registry = None
        with patch("core.llm.opencode_model_limits.get_opencode_model_limits", return_value=MagicMock()):
            assert t._registry() is not None

    def test_model_headroom_with_own_limits(self):
        t = _tracker()
        registry = MagicMock()
        registry.get_model_rate_limits.return_value = {"rpm": 4}
        t._model_registry = registry
        t.set_rate_limits("custom", rpm=1000, tpm=0)
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 0, 0, "m") for _ in range(2)]
        assert t.get_model_headroom("custom", "m") == pytest.approx(0.5)

    def test_model_headroom_zero_own_limits_falls_back(self):
        """Model limits with rpm/tpm both 0 -> provider headroom (line 273)."""
        t = _tracker()
        registry = MagicMock()
        registry.get_model_rate_limits.return_value = {"rpm": 0, "tpm": 0}
        t._model_registry = registry
        t.set_rate_limits("custom", rpm=10, tpm=0)
        now = datetime.now(timezone.utc)
        t._usage["custom"] = [_entry(now, 0, 0, "m") for _ in range(5)]
        assert t.get_model_headroom("custom", "m") == pytest.approx(0.5)


class TestProviderMonthlyUsage:
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


class TestProviderUsageSummary:
    def test_summary_with_models_and_monthly(self):
        t = _tracker()
        now = datetime.now(timezone.utc)
        t.set_rate_limits("custom", rpm=10, tpm=1000)
        t._usage["custom"] = [
            _entry(now, 100, 100, "model-a"),
            _entry(now, 100, 100, "model-b"),
        ]
        persistence = MagicMock()
        persistence.monthly_usage.return_value = {"tpm": 500}
        t.set_persistence(persistence)
        summary = t.usage_summary("custom")
        assert summary["requests_in_window"] == 2
        assert summary["tokens_in_window"] == 400.0
        assert summary["limits"] == {"rpm": 10, "tpm": 1000}
        assert set(summary["models"]) == {"model-a", "model-b"}
        assert summary["models"]["model-a"]["requests_in_window"] == 1
        assert summary["monthly"] == {"tpm": 500}
        assert summary["headroom"] > 0

    def test_summary_empty_window(self):
        t = _tracker()
        t.set_rate_limits("custom", rpm=10, tpm=1000)
        summary = t.usage_summary("custom")
        assert summary["requests_in_window"] == 0
        assert "models" not in summary
        assert "monthly" not in summary


class TestProviderSingleton:
    def _reset(self):
        self._old = prl_mod._rate_tracker
        prl_mod._rate_tracker = None

    def _restore(self):
        prl_mod._rate_tracker = self._old

    def test_creation_success_and_reuse(self):
        self._reset()
        try:
            with patch(
                "core.llm.rate_usage_persistence.get_rate_usage_persistence",
                return_value=MagicMock(),
            ):
                tracker = prl_mod.get_provider_rate_tracker()
            assert isinstance(tracker, ProviderRateTracker)
            assert prl_mod.get_provider_rate_tracker() is tracker
        finally:
            self._restore()

    def test_creation_persistence_unavailable(self):
        """get_rate_usage_persistence raising is tolerated (lines 357-358)."""
        self._reset()
        try:
            with patch(
                "core.llm.rate_usage_persistence.get_rate_usage_persistence",
                side_effect=RuntimeError("no persistence"),
            ):
                tracker = prl_mod.get_provider_rate_tracker()
            assert isinstance(tracker, ProviderRateTracker)
            assert tracker._persistence is None
            assert tracker.get_monthly_usage("p") is None
        finally:
            self._restore()


# ============================================================================
# opencode_model_limits.py
# ============================================================================

class TestWeightFromPrices:
    def test_derived(self):
        assert weight_from_prices(0.00000014, 0.00000028) == pytest.approx(1.0)
        assert weight_from_prices(0.000003, 0.000015) == pytest.approx(42.857, rel=0.01)

    def test_unknown_zero_pricing(self):
        assert weight_from_prices(None, None) == 1.0
        assert weight_from_prices(0, 0) == 1.0
        assert weight_from_prices(-1, 0) == 1.0

    def test_invalid_types(self):
        assert weight_from_prices("abc", 1) == 1.0
        assert weight_from_prices(object(), 1) == 1.0

    def test_floor_at_one(self):
        assert weight_from_prices(0.00000001, 0.00000001) == 1.0


class TestOpencodeRegistry:
    def test_defaults_and_unknown(self):
        r = OpencodeModelLimits()
        assert r.get_weight("opencode-go", "deepseek-v4-flash") == 1.0
        assert r.get_weight("opencode-go", "kimi-k3") == OPCODE_DEFAULT_MODEL_WEIGHTS["kimi-k3"]
        assert r.get_weight("opencode-go", "unknown-model") == 1.0
        assert r.get_weight("opencode-go", None) == 1.0

    def test_set_model_limits(self):
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "m1", weight=2.0, rpm=5, tpm=100)
        assert r.get_weight("opencode-go", "m1") == 2.0
        assert r.get_model_rate_limits("opencode-go", "m1") == {"rpm": 5, "tpm": 100}

    def test_set_model_limits_zero_weight_normalized(self):
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "m1", weight=0)
        assert r.get_weight("opencode-go", "m1") == 1.0

    def test_set_model_limits_empty_model_noop(self):
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "", weight=2.0)
        assert r.get_weight("opencode-go", "") == 1.0

    def test_set_model_limits_no_fields_removes_entry(self):
        """All-None call on a fresh model creates an empty entry then pops it."""
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "m1")
        assert r.get_model_rate_limits("opencode-go", "m1") == {}
        assert r.get_weight("opencode-go", "m1") == 1.0
        r.set_model_limits("opencode-go", "m1", rpm=5)
        assert r.get_model_rate_limits("opencode-go", "m1") == {"rpm": 5}

    def test_set_partial_limits(self):
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "m1", tpm=50)
        assert r.get_model_rate_limits("opencode-go", "m1") == {"tpm": 50}

    def test_get_model_rate_limits_empty_model(self):
        r = OpencodeModelLimits()
        assert r.get_model_rate_limits("opencode-go", None) == {}
        assert r.get_model_rate_limits("opencode-go", "nope") == {}

    def test_apply_pricing_weight_explicit_wins(self):
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "m1", weight=3.0)
        got = r.apply_pricing_weight("opencode-go", "m1", 0.000001, 0.000001)
        assert got == 3.0
        assert r.get_weight("opencode-go", "m1") == 3.0

    def test_apply_pricing_weight_derived_applied(self):
        r = OpencodeModelLimits()
        got = r.apply_pricing_weight("opencode-go", "new-model", 0.000003, 0.000015)
        assert got == pytest.approx(42.857, rel=0.01)
        assert r.get_weight("opencode-go", "new-model") == got

    def test_apply_pricing_weight_derived_below_one_not_applied(self):
        r = OpencodeModelLimits()
        got = r.apply_pricing_weight("opencode-go", "new-model", None, None)
        assert got == 1.0
        assert r.get_weight("opencode-go", "new-model") == 1.0

    def test_apply_pricing_weight_limits_without_weight(self):
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "m1", rpm=5)
        got = r.apply_pricing_weight("opencode-go", "m1", 0.000003, 0.000015)
        assert got == pytest.approx(42.857, rel=0.01)

    def test_summary_filters_provider(self):
        r = OpencodeModelLimits()
        r.set_model_limits("opencode-go", "m1", rpm=5)
        r.set_model_limits("other-provider", "m2", rpm=9)
        summary = r.summary("opencode-go")
        assert "m1" in summary["model_limits"]
        assert "m2" not in summary["model_limits"]
        assert summary["weights"]["deepseek-v4-flash"] == 1.0
        summary2 = r.summary("other-provider")
        assert "m2" in summary2["model_limits"]


class TestOpencodeEnvOverrides:
    @staticmethod
    def _registry_with_env(raw):
        with patch.dict("os.environ", {"OPENCODE_MODEL_LIMITS": raw}):
            return OpencodeModelLimits()

    def test_empty_env(self):
        with patch.dict("os.environ", {"OPENCODE_MODEL_LIMITS": ""}):
            r = OpencodeModelLimits()
        assert r.get_weight("opencode-go", "deepseek-v4-pro") == OPCODE_DEFAULT_MODEL_WEIGHTS["deepseek-v4-pro"]

    def test_invalid_json(self):
        r = self._registry_with_env("{not json")
        assert r.get_weight("opencode-go", "deepseek-v4-pro") == OPCODE_DEFAULT_MODEL_WEIGHTS["deepseek-v4-pro"]

    def test_non_object_json(self):
        r = self._registry_with_env("[1, 2, 3]")
        assert r.get_weight("opencode-go", "deepseek-v4-pro") == OPCODE_DEFAULT_MODEL_WEIGHTS["deepseek-v4-pro"]

    def test_cfg_not_object_skipped(self):
        r = self._registry_with_env('{"deepseek-v4-pro": 5}')
        assert r.get_weight("opencode-go", "deepseek-v4-pro") == OPCODE_DEFAULT_MODEL_WEIGHTS["deepseek-v4-pro"]

    def test_invalid_values_skipped(self):
        r = self._registry_with_env(
            '{"deepseek-v4-pro": {"weight": "abc", "rpm": "xyz"}}'
        )
        assert r.get_weight("opencode-go", "deepseek-v4-pro") == OPCODE_DEFAULT_MODEL_WEIGHTS["deepseek-v4-pro"]

    def test_valid_overrides_applied(self):
        r = self._registry_with_env(
            '{"deepseek-v4-pro": {"weight": 3.0, "rpm": 20, "tpm": 500000}}'
        )
        assert r.get_weight("opencode-go", "deepseek-v4-pro") == 3.0
        assert r.get_model_rate_limits("opencode-go", "deepseek-v4-pro") == {"rpm": 20, "tpm": 500000}

    def test_override_weight_only(self):
        r = self._registry_with_env('{"deepseek-v4-pro": {"weight": 5.0}}')
        assert r.get_weight("opencode-go", "deepseek-v4-pro") == 5.0
        assert r.get_model_rate_limits("opencode-go", "deepseek-v4-pro") == {}


class TestOpencodeSingleton:
    def test_singleton(self):
        old = __import__("core.llm.opencode_model_limits", fromlist=["_opencode_model_limits"])._opencode_model_limits
        mod = __import__("core.llm.opencode_model_limits", fromlist=["_opencode_model_limits"])
        try:
            mod._opencode_model_limits = None
            inst = get_opencode_model_limits()
            assert isinstance(inst, OpencodeModelLimits)
            assert get_opencode_model_limits() is inst
        finally:
            mod._opencode_model_limits = old


# ============================================================================
# rtk_engine.py
# ============================================================================

class TestRTKShortAndStructured:
    def test_empty_returns_unchanged(self):
        engine = RTKEngine()
        assert engine.compress("") == ""

    def test_short_returns_unchanged(self):
        engine = RTKEngine()
        text = "short log line here"
        assert engine.compress(text) == text

    def test_json_object_unchanged(self):
        engine = RTKEngine()
        text = '{"name": "acme", "amount": 5000}'
        assert engine.compress(text) == text

    def test_json_array_unchanged(self):
        engine = RTKEngine()
        text = '[{"a": 1}, {"b": 2}]'
        assert engine.compress(text) == text

    def test_xml_declaration_unchanged(self):
        engine = RTKEngine()
        text = '<?xml version="1.0"?><root/>'
        assert engine.compress(text) == text

    def test_xml_namespace_unchanged(self):
        engine = RTKEngine()
        text = '<feed xmlns="http://www.w3.org/2005/Atom">content</feed>'
        assert engine.compress(text) == text

    def test_sql_unchanged(self):
        engine = RTKEngine()
        text = "SELECT * FROM invoices WHERE amount > 100;"
        assert engine.compress(text) == text

    def test_fenced_code_majority_unchanged(self):
        engine = RTKEngine()
        text = "some build preamble\n```python\n" + "x" * 200 + "\n```\n"
        assert len(text) >= 50
        assert engine.compress(text) == text

    def test_small_fence_not_majority_not_structured(self):
        """A small code fence (<=50% of text) does not trip the safety guard."""
        engine = RTKEngine()
        text = "```py\nok\n```\n" + "plain log text " * 12
        assert engine._is_structured_data(text) is False

    def test_plain_log_not_structured(self):
        engine = RTKEngine()
        assert engine._is_structured_data("build succeeded in 10s") is False


class TestRTKPasses:
    def test_strip_ansi(self):
        engine = RTKEngine()
        out = engine._strip_ansi("\x1b[32mgreen\x1b[0m\x07beep\x1b[1;34m")
        assert out == "greenbeep"

    def test_collapse_repeated_lines(self):
        engine = RTKEngine()
        text = "a\nb\nb\nb\nb\nc\n"
        out = engine._collapse_repeated_lines(text)
        assert out == "a\n[4 repeated lines: b]\nc\n"

    def test_collapse_nested_repeats_iterates(self):
        engine = RTKEngine()
        out = engine._collapse_repeated_lines("x\nx\nx\n" * 3)
        assert out.startswith("[9 repeated lines: x]")

    def test_collapse_stable_two_repeats(self):
        engine = RTKEngine()
        text = "a\na\nb\n"
        assert engine._collapse_repeated_lines(text) == text

    def test_compress_test_output_jest(self):
        engine = RTKEngine()
        text = "preamble line\nTests:      1 passed, 1 total\n✓ works (5ms)\n✗ fails (10ms)\nTest Suites: 1 passed\n"
        out = engine._compress_test_output(text)
        assert "preamble line" in out
        assert "Tests:      1 passed" in out
        assert "✓ works (5ms)" not in out
        assert "✗ fails (10ms)" in out
        assert "Test Suites: 1 passed" in out

    def test_compress_test_output_pytest(self):
        """PASSED/FAILED lines carry the 'passed'/'failed' keyword -> kept;
        bare dot progress lines carry no keyword -> dropped."""
        engine = RTKEngine()
        text = "PASSED\nFAILED\nERROR test_x\n....\n===== 2 passed, 1 failed =====\n"
        out = engine._compress_test_output(text)
        assert "PASSED" in out
        assert "FAILED" in out
        assert "ERROR test_x" in out
        assert "...." not in out
        assert "2 passed, 1 failed" in out

    def test_compress_test_output_cargo(self):
        engine = RTKEngine()
        text = "running 2 tests\ntest foo ... ok\n test bar ... FAILED\ntest result: ok. 1 passed\n"
        out = engine._compress_test_output(text)
        assert "test foo ... ok" not in out
        assert "FAILED" in out
        assert "test result: ok" in out

    def test_compress_test_output_go(self):
        engine = RTKEngine()
        text = "--- PASS: TestFoo (0.00s)\n--- FAIL: TestBar (0.01s)\nok\tmy/package\t0.05s\n"
        out = engine._compress_test_output(text)
        assert "--- FAIL: TestBar" in out
        assert "ok\tmy/package" in out

    def test_compress_test_output_docker(self):
        engine = RTKEngine()
        text = "Step 5/12 : RUN make build\nStep 6/12 : CMD [\"/app\"]\n"
        out = engine._compress_test_output(text)
        assert "Step 5/12" in out
        assert "Step 6/12" in out

    def test_compress_test_output_dots_dropped(self):
        engine = RTKEngine()
        text = "....\nFAILED tests/test_x.py\n"
        out = engine._compress_test_output(text)
        assert "...." not in out
        assert "FAILED" in out

    def test_compress_diff_context_collapse(self):
        engine = RTKEngine()
        text = (
            "diff --git a/f.py b/f.py\n@@ -1,12 +1,12 @@\n"
            + " c1\n c2\n c3\n c4\n c5\n c6\n"
            + "+added\n-deleted\n"
        )
        out = engine._compress_diff_context(text)
        assert "[6 context lines collapsed]" in out
        assert "+added" in out
        assert "-deleted" in out

    def test_compress_diff_context_small_buffer_kept(self):
        engine = RTKEngine()
        text = "diff --git a/f.py b/f.py\n@@ -1,2 +1,2 @@\n c1\n c2\n+added\n"
        out = engine._compress_diff_context(text)
        assert " c1\n c2\n" in out
        assert "+added" in out

    def test_compress_diff_context_blank_line_flushes(self):
        engine = RTKEngine()
        text = (
            "diff --git a/f.py b/f.py\n@@ -1,12 +1,12 @@\n"
            + " c1\n c2\n c3\n c4\n c5\n c6\n\n+new line\n"
        )
        out = engine._compress_diff_context(text)
        assert "[6 context lines collapsed]" in out
        assert "+new line" in out
        assert "\n\n" in out

    def test_compress_diff_context_non_diff_line_flushes(self):
        engine = RTKEngine()
        text = "diff --git a/f.py b/f.py\n@@ -1,2 +1,2 @@\n c1\nnot a diff line\n"
        out = engine._compress_diff_context(text)
        assert " c1" in out
        assert "not a diff line" in out

    def test_compress_diff_context_trailing_flush(self):
        """Trailing context buffer is flushed at end-of-text (via blank line)."""
        engine = RTKEngine()
        text = "diff --git a/f.py b/f.py\n@@ -1,12 +1,12 @@\n c1\n c2\n c3\n c4\n c5\n c6\n"
        out = engine._compress_diff_context(text)
        assert out.endswith("[6 context lines collapsed]\n")

    def test_cap_section_length_under(self):
        engine = RTKEngine()
        text = "short text"
        assert engine._cap_section_length(text) == text

    def test_cap_section_length_over(self):
        engine = RTKEngine()
        with patch("core.llm.compression.RTK_MAX_SECTION_CHARS", 100):
            text = "Z" * 500
            out = engine._cap_section_length(text)
        assert "truncated by RTK cap" in out
        assert out.endswith("Z" * 34)
        assert out.startswith("Z" * 66)

    def test_full_pipeline(self):
        engine = RTKEngine()
        text = (
            "build start\n\x1b[32mStep 1/2 : OK\x1b[0m\n"
            "PASSED\nFAILED test_x\n"
            "warning: deprecated\n"
            "b\nb\nb\nb\n"
        )
        out = engine.compress(text)
        assert "\x1b[32m" not in out
        assert "FAILED test_x" in out
        assert "warning" in out
        assert "repeated lines" in out
        assert "PASSED" in out  # carries the 'passed' keyword -> kept


# ============================================================================
# session_dedup.py
# ============================================================================

class TestSessionDedupChunking:
    def test_chunk_empty_returns_empty_list(self):
        assert SessionDedupIndex._chunk("") == []

    def test_chunk_merges_small_parts_into_buffer(self):
        small = "A" * (DEDUP_MIN_CHUNK_CHARS // 4)
        idx = SessionDedupIndex()
        idx.index_text(small + "\n\n" + small)
        assert idx.size == 0

    def test_chunk_flushes_buffer_when_large_part_arrives(self):
        small = "B" * (DEDUP_MIN_CHUNK_CHARS // 4)
        big = "C" * (DEDUP_MIN_CHUNK_CHARS + 100)
        idx = SessionDedupIndex()
        idx.index_text(small + "\n\n" + big)
        assert idx.size == 1

    def test_chunk_buffers_just_under_min_part_for_tail(self):
        mid = "D" * (DEDUP_MIN_CHUNK_CHARS - 1)
        idx = SessionDedupIndex()
        idx.index_text("E" * (DEDUP_MIN_CHUNK_CHARS + 100) + "\n\n" + mid)
        assert idx.size == 1

    def test_chunk_undersized_tail_dropped_when_never_buffered(self):
        idx = SessionDedupIndex()
        idx.index_text("F" * (DEDUP_MIN_CHUNK_CHARS - 10))
        assert idx.size == 0


class TestSessionDedupIndex:
    def test_index_and_deduplicate_single_chunk(self):
        idx = SessionDedupIndex()
        text = "G" * (DEDUP_MIN_CHUNK_CHARS + 50)
        idx.index_text(text)
        out, n = idx.deduplicate(text)
        assert n == 1
        assert out.startswith("[previously sent: ")
        assert text not in out

    def test_single_chunk_not_indexed_unchanged(self):
        idx = SessionDedupIndex()
        text = "H" * (DEDUP_MIN_CHUNK_CHARS + 50)
        assert idx.deduplicate(text) == (text, 0)

    def test_multi_chunk_partial_match(self):
        idx = SessionDedupIndex()
        chunk1 = "I" * (DEDUP_MIN_CHUNK_CHARS + 50)
        chunk2 = "J" * (DEDUP_MIN_CHUNK_CHARS + 50)
        idx.index_text(chunk1)
        text = chunk1 + "\n\n" + chunk2
        out, n = idx.deduplicate(text)
        assert n == 1
        assert out.startswith("[previously sent: ")
        assert chunk2 in out
        assert chunk1 not in out

    def test_multi_chunk_no_match_returns_original(self):
        idx = SessionDedupIndex()
        text = "K" * (DEDUP_MIN_CHUNK_CHARS + 10) + "\n\n" + "L" * (DEDUP_MIN_CHUNK_CHARS + 10)
        assert idx.deduplicate(text) == (text, 0)

    def test_empty_and_whitespace_unchanged(self):
        idx = SessionDedupIndex()
        assert idx.deduplicate("") == ("", 0)
        assert idx.deduplicate("   \n ") == ("   \n ", 0)

    def test_defensive_empty_chunks_guard(self):
        idx = SessionDedupIndex()
        with mock.patch.object(SessionDedupIndex, "_chunk", staticmethod(lambda text: [])):
            text = "some non-empty text"
            assert idx.deduplicate(text) == (text, 0)

    def test_clear_and_size(self):
        idx = SessionDedupIndex()
        text = "M" * (DEDUP_MIN_CHUNK_CHARS + 50)
        idx.index_text(text)
        assert idx.size == 1
        idx.clear()
        assert idx.size == 0

    def test_lru_eviction(self):
        idx = SessionDedupIndex(max_size=2)
        for letter in ("N", "O", "P"):
            idx.index_text(letter * (DEDUP_MIN_CHUNK_CHARS + 50))
        assert idx.size == 2

    def test_short_chunks_not_indexed(self):
        idx = SessionDedupIndex()
        idx.index_text("short")
        assert idx.size == 0

    def test_hash_stability(self):
        assert SessionDedupIndex._hash("x") == hashlib.sha256(b"x").hexdigest()


class TestSessionDedupGetOrCreate:
    def test_creates_and_reuses(self):
        session = {}
        idx1 = get_or_create_dedup_index(session)
        assert isinstance(idx1, SessionDedupIndex)
        assert session["_dedup_index"] is idx1
        assert get_or_create_dedup_index(session) is idx1


# ============================================================================
# response_quality.py
# ============================================================================

class TestResponseQualityHardFailures:
    def test_exception_timeout(self):
        r = assess_response_quality(None, exception=TimeoutError("took too long"))
        assert not r.success
        assert not r.quality_satisfied
        assert r.quality_score == 0.0
        assert r.issues == ["timeout"]

    def test_exception_rate_limited(self):
        r = assess_response_quality("x", exception=RuntimeError("rate limit exceeded"))
        assert r.issues == ["rate_limited"]

    def test_exception_context_length(self):
        r = assess_response_quality("x", exception=RuntimeError("maximum context length exceeded"))
        assert r.issues == ["context_length"]

    def test_exception_auth_by_name(self):
        class MyAuthError(Exception):
            pass

        r = assess_response_quality("x", exception=MyAuthError("bad"))
        assert r.issues == ["auth_error"]

    def test_exception_auth_by_message(self):
        r = assess_response_quality("x", exception=RuntimeError("unauthorized"))
        assert r.issues == ["auth_error"]

    def test_exception_auth_by_api_key_message(self):
        r = assess_response_quality("x", exception=RuntimeError("invalid api key"))
        assert r.issues == ["auth_error"]

    def test_exception_network_by_name(self):
        r = assess_response_quality("x", exception=ConnectionError("boom"))
        assert r.issues == ["network_error"]

    def test_exception_network_by_message(self):
        r = assess_response_quality("x", exception=RuntimeError("network unreachable"))
        assert r.issues == ["network_error"]

    def test_exception_provider_error_fallback(self):
        r = assess_response_quality("x", exception=ValueError("something odd"))
        assert r.issues == ["provider_error"]

    def test_classify_exception_direct(self):
        assert _classify_exception(RuntimeError("rate limit")) == "rate_limited"


class TestResponseQualityContent:
    def test_schema_error(self):
        r = assess_response_quality("content", schema_error=True)
        assert r.success
        assert not r.quality_satisfied
        assert r.quality_score == 0.2
        assert r.issues == ["schema_error"]

    def test_truncated_with_text(self):
        r = assess_response_quality("partial", finish_reason="length")
        assert r.quality_score == 0.3
        assert r.issues == ["truncated"]

    def test_truncated_without_text(self):
        r = assess_response_quality(None, finish_reason="length")
        assert r.quality_score == 0.1

    def test_empty_content(self):
        r = assess_response_quality("   ")
        assert r.quality_score == 0.1
        assert r.issues == ["empty"]

    def test_refusal_marker(self):
        r = assess_response_quality("I'm sorry, but I can't help with that.")
        assert r.quality_score == 0.4
        assert r.issues == ["refusal"]

    def test_refusal_with_preamble(self):
        r = assess_response_quality("Sure — however, unfortunately, I am unable to do this.")
        assert r.quality_score == 0.4

    def test_refusal_beyond_scan_window_not_flagged(self):
        text = ("P" * 200) + " unfortunately, i am unable"
        r = assess_response_quality(text)
        assert r.quality_satisfied
        assert "refusal" not in r.issues

    def test_substantive_short(self):
        r = assess_response_quality("ok done")
        assert r.quality_satisfied
        assert r.quality_score == 0.7

    def test_substantive_medium(self):
        r = assess_response_quality("x" * 300)
        assert r.quality_score == 0.8

    def test_substantive_long(self):
        r = assess_response_quality("y" * 900)
        assert r.quality_score == 0.85

    def test_substantive_very_long_diminished(self):
        r = assess_response_quality("z" * 9000)
        assert r.quality_score == 0.78

    def test_defaults_and_issues_accumulation(self):
        r = assess_response_quality("hello world")
        assert isinstance(r, ResponseQuality)
        assert r.issues == []


# ============================================================================
# canvas_summary_service.py
# ============================================================================

def _llm(return_value="A concise summary of the canvas."):
    llm = AsyncMock()
    llm.generate.return_value = return_value
    return llm


class TestCanvasSummaryService:
    def test_generate_summary_success_and_cache(self):
        llm = _llm()
        svc = CanvasSummaryService(llm)
        state = {"components": [{"type": "chart"}]}
        out = asyncio.run(svc.generate_summary("sheets", state, agent_task="sum revenue", user_interaction="submit"))
        assert out == "A concise summary of the canvas."
        assert llm.generate.await_count == 1
        out2 = asyncio.run(svc.generate_summary("sheets", state, agent_task="sum revenue", user_interaction="submit"))
        assert out2 == out
        assert llm.generate.await_count == 1  # cache hit, no second LLM call

    def test_generate_summary_invalid_type_raises(self):
        svc = CanvasSummaryService(_llm())
        with pytest.raises(ValueError, match="Invalid canvas_type"):
            asyncio.run(svc.generate_summary("bogus", {}))

    def test_generate_summary_timeout_reraises(self):
        async def _slow(*a, **k):
            raise asyncio.TimeoutError("timed out")

        llm = AsyncMock()
        llm.generate.side_effect = _slow
        svc = CanvasSummaryService(llm)
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(svc.generate_summary("docs", {}))

    def test_generate_summary_exception_reraises(self):
        async def _boom(*a, **k):
            raise RuntimeError("llm down")

        llm = AsyncMock()
        llm.generate.side_effect = _boom
        svc = CanvasSummaryService(llm)
        with pytest.raises(RuntimeError):
            asyncio.run(svc.generate_summary("docs", {}))

    def test_generate_summary_calls_with_expected_kwargs(self):
        llm = _llm()
        svc = CanvasSummaryService(llm)
        asyncio.run(svc.generate_summary("terminal", {"command": "pwd"}, agent_task="run"))
        kwargs = llm.generate.call_args.kwargs
        assert kwargs["temperature"] == 0.0
        assert kwargs["task_type"] == "analysis"
        assert "terminal" in kwargs["prompt"]

    def test_build_prompt_all_fields(self):
        svc = CanvasSummaryService(_llm())
        prompt = svc._build_prompt(
            "orchestration",
            {"workflow_id": "wf-1"},
            agent_task="approve payment",
            user_interaction="execute",
        )
        assert "orchestration" in prompt
        assert "approve payment" in prompt
        assert '"workflow_id": "wf-1"' in prompt
        assert "execute" in prompt
        assert "workflow_id" in prompt  # canvas-specific instructions

    def test_build_prompt_unknown_type_empty_instructions(self):
        svc = CanvasSummaryService(_llm())
        prompt = svc._build_prompt("nope", {}, None, None)
        assert "Not specified" in prompt
        assert "None" in prompt

    def test_fallback_metadata_with_components_and_data(self):
        svc = CanvasSummaryService(_llm())
        state = {
            "components": [{"type": "chart"}, {"type": "table"}, {"type": "input"}],
            "workflow_id": "wf-1",
            "revenue": 5000,
            "amount": 100,
            "command": "deploy",
        }
        out = svc._fallback_to_metadata("sheets", state)
        assert "chart, table, input" in out
        assert "workflow wf-1" in out
        assert "$5000" in out
        assert "$100" in out
        assert "command: deploy" in out

    def test_fallback_metadata_no_components(self):
        svc = CanvasSummaryService(_llm())
        out = svc._fallback_to_metadata("docs", {})
        assert out == "Agent presented docs canvas"

    def test_fallback_metadata_no_critical_data(self):
        svc = CanvasSummaryService(_llm())
        out = svc._fallback_to_metadata("generic", {"components": [{"type": "text"}]})
        assert out == "Agent presented text on generic canvas"

    def test_cache_stats(self):
        llm = _llm()
        svc = CanvasSummaryService(llm)
        stats = svc.get_cache_stats()
        assert stats["cache_size"] == 0
        assert stats["tracked_sessions"] == 0
        assert stats["supported_canvas_types"] == 7
        asyncio.run(svc.generate_summary("email", {"to": "a@b.c"}))
        stats = svc.get_cache_stats()
        assert stats["cache_size"] == 1
        assert stats["tracked_sessions"] == 1

    def test_clear_cache(self):
        llm = _llm()
        svc = CanvasSummaryService(llm)
        asyncio.run(svc.generate_summary("email", {"to": "a@b.c"}))
        svc.clear_cache()
        assert svc.get_cache_stats()["cache_size"] == 0

    def test_supported_types_and_validation(self):
        svc = CanvasSummaryService(_llm())
        types = svc.get_supported_canvas_types()
        assert "sheets" in types
        assert svc.is_canvas_type_supported("coding")
        assert not svc.is_canvas_type_supported("bogus")

    def test_cost_tracking(self):
        llm = _llm()
        svc = CanvasSummaryService(llm)
        assert svc.get_total_cost_tracked() == 0.0
        asyncio.run(svc.generate_summary("sheets", {}))
        assert svc.get_total_cost_tracked() == 0.0
        svc._cost_tracker["manual"] = 1.5
        assert svc.get_total_cost_tracked() == 1.5

    def test_canvas_prompt_instructions(self):
        svc = CanvasSummaryService(_llm())
        assert "approval_amount" in (svc.get_canvas_prompt_instructions("orchestration") or "")
        assert svc.get_canvas_prompt_instructions("bogus") is None

    def test_semantic_richness(self):
        svc = CanvasSummaryService(_llm())
        assert svc._calculate_semantic_richness("") == 0.0
        low = svc._calculate_semantic_richness("plain text only")
        assert 0.0 <= low <= 0.1
        rich = svc._calculate_semantic_richness(
            "approval budget revenue workflow stakeholder decision consent deadline "
            "priority growth increase decrease trend $ k m b requiring requesting "
            "highlighting showing due to because for with"
        )
        assert rich == 1.0

    def test_detect_hallucination(self):
        svc = CanvasSummaryService(_llm())
        assert svc._detect_hallucination("workflow wf-123 completed", {}) is True
        assert svc._detect_hallucination("workflow wf-123 completed", {"workflow_id": "wf-123"}) is False
        assert svc._detect_hallucination("no workflow ids here", {}) is False
