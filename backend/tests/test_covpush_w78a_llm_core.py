"""Coverage wave 78a — core/llm core modules (standalone >=95% each).

Targets (all mocked, zero LLM spend, no network, no real DB):
  core/llm/self_consistency_voter.py
  core/llm/stage_router.py
  core/llm/stage_router_automation.py
  core/llm/match_confidence_tiebreaker.py
  core/llm/action_judge.py
  core/llm/intent_detector.py
  core/llm/cache_aware_router.py
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm import action_judge as aj
from core.llm import cache_aware_router as car
from core.llm import intent_detector as idet
from core.llm import match_confidence_tiebreaker as mct
from core.llm import self_consistency_voter as scv
from core.llm import stage_router as sr
from core.llm import stage_router_automation as auto


# ===========================================================================
# Shared fakes
# ===========================================================================


class _Q:
    """Chainable query fake: filter/order_by/group_by are no-ops."""

    def __init__(self, db: "FakeDb", model: Optional[str]) -> None:
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):  # noqa: A002
        return self

    def order_by(self, *args):
        return self

    def group_by(self, *args):
        return self

    def first(self):
        if self.model is not None:
            return self.db.first_rows.get(self.model)
        return None

    def all(self):
        if self.model is not None:
            return self.db.all_rows.get(self.model, [])
        return []


class FakeDb:
    """Minimal session fake: per-model first()/all() results + add/commit."""

    def __init__(
        self,
        first_rows: Optional[Dict[str, Any]] = None,
        all_rows: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.first_rows = first_rows or {}
        self.all_rows = all_rows or {}
        self.added: List[Any] = []
        self.committed = 0
        self.closed = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, row) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.committed += 1

    def close(self) -> None:
        self.closed += 1

    def query(self, *cols):
        if not cols:
            return _Q(self, None)
        first = cols[0]
        cls = first if isinstance(first, type) else getattr(first, "class_", None)
        name = getattr(cls, "__name__", None) if cls is not None else None
        return _Q(self, name)


class FakeAgent:
    def __init__(self, agent_id: str, config: Optional[Dict] = None) -> None:
        self.id = agent_id
        self.configuration = config or {}


class FakeAction:
    def __init__(self, agent_id: str, verdict: str = "certify", state: str = "approval") -> None:
        self.id = f"action-{agent_id}"
        self.agent_id = agent_id
        self.verdict = verdict
        self.mode = "approve"
        self.state = state
        self.stats_json: Dict[str, Any] = {}
        self.created_at = None
        self.decided_at = None


def arm(n: int, success_rate: float, avg_cost: float = 0.001) -> Dict[str, float]:
    return {"n": n, "success_rate": success_rate, "avg_cost": avg_cost}


def workload(eff: Dict[str, float], cap: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    return {"efficient": eff, "capable": cap}


class FakePricing:
    def __init__(self, pricing: Optional[Dict] = None) -> None:
        self.pricing = pricing

    def get_model_price(self, model: str) -> Optional[Dict]:
        return self.pricing


def fake_session_patch(monkeypatch, db: FakeDb) -> None:
    monkeypatch.setattr("core.database.get_db_session", lambda: db)


# ===========================================================================
# cache_aware_router
# ===========================================================================


class TestCacheAwareRouterCost:
    PRICING = {"input_cost_per_token": 0.001, "output_cost_per_token": 0.002}

    def _router(self) -> car.CacheAwareRouter:
        return car.CacheAwareRouter(FakePricing(dict(self.PRICING)))

    def test_no_pricing_returns_inf(self) -> None:
        router = car.CacheAwareRouter(FakePricing(None))
        result = router.calculate_effective_cost(
            model="unknown", provider="openai", estimated_input_tokens=2000
        )
        assert result.value == float("inf")

    def test_deterministic_turn_mode(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=2000, turn_index=2,
        )
        expected = (0.001 * 0.10 + 0.002) / 2
        assert result.value == pytest.approx(expected)

    def test_probabilistic_explicit_probability(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=2000, cache_hit_probability=0.9,
        )
        discounted = 0.9 * 0.10 + 0.1
        expected = (0.001 * discounted + 0.002) / 2
        assert result.value == pytest.approx(expected)

    def test_probabilistic_predicted_from_history(self) -> None:
        router = self._router()
        router.cache_hit_history["default:abc123"] = [8, 10]
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=2000, prompt_hash="abc123",
        )
        discounted = 0.8 * 0.10 + 0.2
        expected = (0.001 * discounted + 0.002) / 2
        assert result.value == pytest.approx(expected)

    def test_probabilistic_default_0_5(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=2000, prompt_hash="nohistory",
        )
        discounted = 0.5 * 0.10 + 0.5
        expected = (0.001 * discounted + 0.002) / 2
        assert result.value == pytest.approx(expected)

    def test_probabilistic_default_0_5_no_hash(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=2000,
        )
        discounted = 0.5 * 0.10 + 0.5
        expected = (0.001 * discounted + 0.002) / 2
        assert result.value == pytest.approx(expected)

    def test_probability_clamped_above_one(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=2000, cache_hit_probability=1.5,
        )
        discounted = 1.0 * 0.10 + 0.0
        expected = (0.001 * discounted + 0.002) / 2
        assert result.value == pytest.approx(expected)

    def test_probability_clamped_below_zero(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=2000, cache_hit_probability=-0.5,
        )
        expected = (0.001 + 0.002) / 2
        assert result.value == pytest.approx(expected)

    def test_below_min_tokens_full_price(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="gpt-4o", provider="openai",
            estimated_input_tokens=100, cache_hit_probability=0.9,
        )
        assert result.value == pytest.approx((0.001 + 0.002) / 2)

    def test_no_cache_provider_full_price(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="deepseek-chat", provider="deepseek",
            estimated_input_tokens=5000, cache_hit_probability=0.9,
        )
        assert result.value == pytest.approx((0.001 + 0.002) / 2)

    def test_anthropic_min_tokens_threshold(self) -> None:
        router = self._router()
        below = router.calculate_effective_cost(
            model="claude", provider="anthropic",
            estimated_input_tokens=1000, cache_hit_probability=0.9,
        )
        assert below.value == pytest.approx((0.001 + 0.002) / 2)
        above = router.calculate_effective_cost(
            model="claude", provider="anthropic",
            estimated_input_tokens=3000, turn_index=1,
        )
        expected = (0.001 * 0.10 + 0.002) / 2
        assert above.value == pytest.approx(expected)

    def test_moonshot_cached_ratio_0_20(self) -> None:
        router = self._router()
        result = router.calculate_effective_cost(
            model="kimi-k2", provider="moonshot",
            estimated_input_tokens=5000, cache_hit_probability=1.0,
        )
        expected = (0.001 * 0.20 + 0.002) / 2
        assert result.value == pytest.approx(expected)


class TestCacheAwareRouterHistory:
    def test_predict_no_history_default(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        assert router.predict_cache_hit_probability("abc123", "default") == 0.5

    def test_predict_uses_ratio(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.cache_hit_history["default:abc123"] = [8, 10]
        assert router.predict_cache_hit_probability("abc123", "default") == 0.8

    def test_predict_zero_total_falls_back(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.cache_hit_history["default:abc1234567890123"] = [0, 0]
        assert router.predict_cache_hit_probability("abc123", "default") == 0.5

    def test_predict_truncates_key_to_16_chars(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        long_hash = "a" * 40
        router.cache_hit_history[f"ws:{'a' * 16}"] = [1, 2]
        assert router.predict_cache_hit_probability(long_hash, "ws") == 0.5

    def test_record_new_key(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.record_cache_outcome("abc123", "default", True)
        assert router.cache_hit_history["default:abc123"] == [1, 1]

    def test_record_miss_accumulates(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.record_cache_outcome("abc123", "default", True)
        router.record_cache_outcome("abc123", "default", False)
        assert router.cache_hit_history["default:abc123"] == [1, 2]

    def test_fifo_eviction_beyond_max_keys(self, monkeypatch) -> None:
        monkeypatch.setattr(car.CacheAwareRouter, "_MAX_CACHE_KEYS", 2)
        router = car.CacheAwareRouter(FakePricing({}))
        router.record_cache_outcome("key1", "default", True)
        router.record_cache_outcome("key2", "default", True)
        router.record_cache_outcome("key3", "default", True)
        assert "default:key1" not in router.cache_hit_history
        assert "default:key2" in router.cache_hit_history
        assert "default:key3" in router.cache_hit_history

    def test_rolling_window_scales(self, monkeypatch) -> None:
        monkeypatch.setattr(car.CacheAwareRouter, "_CACHE_WINDOW", 10)
        router = car.CacheAwareRouter(FakePricing({}))
        for _ in range(15):
            router.record_cache_outcome("abc123", "default", True)
        hits, total = router.cache_hit_history["default:abc123"]
        assert total == 10
        assert hits == 10

    def test_get_provider_capability_direct(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        caps = router.get_provider_cache_capability("openai")
        assert caps["supports_cache"] is True
        assert caps["cached_cost_ratio"] == 0.10

    def test_get_provider_capability_case_insensitive(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        caps = router.get_provider_cache_capability("ANTHROPIC")
        assert caps["supports_cache"] is True

    def test_get_provider_capability_google_fuzzy(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        caps = router.get_provider_cache_capability("google-gemini")
        assert caps["supports_cache"] is True

    def test_get_provider_capability_unknown_default(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        caps = router.get_provider_cache_capability("mystery-provider")
        assert caps["supports_cache"] is False
        assert caps["min_tokens"] == 0

    def test_get_history_workspace_filtered_defensive_copy(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.record_cache_outcome("abc", "ws1", True)
        router.record_cache_outcome("def", "ws2", True)
        view = router.get_cache_hit_history("ws1")
        assert list(view) == ["ws1:abc"]
        view["ws1:abc"][0] = 99
        assert router.cache_hit_history["ws1:abc"][0] == 1

    def test_get_history_all(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.record_cache_outcome("abc", "ws1", True)
        assert len(router.get_cache_hit_history()) == 1

    def test_clear_history_all(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.record_cache_outcome("abc", "ws1", True)
        router.clear_cache_history()
        assert router.cache_hit_history == {}
        assert router._cache_key_order == []

    def test_clear_history_workspace_scoped_keeps_fifo(self) -> None:
        router = car.CacheAwareRouter(FakePricing({}))
        router.record_cache_outcome("abc", "ws1", True)
        router.record_cache_outcome("def", "ws2", True)
        router.clear_cache_history("ws1")
        assert "ws1:abc" not in router.cache_hit_history
        assert "ws2:def" in router.cache_hit_history
        assert router._cache_key_order == ["ws2:def"]


# ===========================================================================
# match_confidence_tiebreaker
# ===========================================================================


class TestTiebreakerCircuitBreaker:
    def test_init_state(self) -> None:
        cb = mct._CircuitBreaker()
        assert cb.state == "closed"
        assert cb.failures == 0

    def test_opens_after_threshold(self) -> None:
        cb = mct._CircuitBreaker()
        for _ in range(mct._CB_THRESHOLD):
            assert cb.is_tripped() is False
            cb.record_failure()
        assert cb.state == "open"
        assert cb.is_tripped() is True

    def test_cooldown_elapsed_half_open_probe(self, monkeypatch) -> None:
        monkeypatch.setattr(mct, "time", SimpleNamespace(time=lambda: 1000.0))
        cb = mct._CircuitBreaker()
        for _ in range(mct._CB_THRESHOLD):
            cb.record_failure()
        monkeypatch.setattr(mct, "time", SimpleNamespace(time=lambda: 1000.0 + mct._CB_COOLDOWN_S))
        assert cb.is_tripped() is False
        assert cb.state == "half_open"

    def test_record_success_closes(self) -> None:
        cb = mct._CircuitBreaker()
        for _ in range(mct._CB_THRESHOLD):
            cb.record_failure()
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failures == 0

    def test_record_success_from_half_open(self) -> None:
        cb = mct._CircuitBreaker()
        cb.state = "half_open"
        cb.record_success()
        assert cb.state == "closed"

    def test_reset(self) -> None:
        cb = mct._CircuitBreaker()
        for _ in range(mct._CB_THRESHOLD):
            cb.record_failure()
        cb.reset()
        assert cb.state == "closed"
        assert cb.is_tripped() is False


class TestTiebreakerCache:
    def _candidate(self, selector: str = "div.a") -> mct.SelectorCandidate:
        return mct.SelectorCandidate(
            selector=selector, match_count=1, is_text_only=False,
            appeared_after_ms=0, tag_hint="div",
        )

    def test_cache_key_stable_and_host_scoped(self) -> None:
        c1 = self._candidate()
        key_a = mct._cache_key([c1], {"url": "https://example.com/page"})
        key_b = mct._cache_key([c1], {"url": "https://example.com/other"})
        key_c = mct._cache_key([c1], {"url": "https://other.com/x"})
        assert key_a == key_b
        assert key_a != key_c

    def test_cache_key_empty_hostname(self) -> None:
        c1 = self._candidate()
        key = mct._cache_key([c1], {"url": "not-a-url"})
        assert len(key) == 16

    def test_cache_get_miss_returns_none(self) -> None:
        mct._tiebreak_cache.clear()
        assert mct._cache_get("nope") is None

    def test_cache_get_expired_entry_removed(self, monkeypatch) -> None:
        monkeypatch.setattr(mct, "time", SimpleNamespace(time=lambda: 0.0))
        result = mct.TiebreakResult(chosen_index=0, rationale="r", used_llm=True)
        mct._cache_put("k", result)
        monkeypatch.setattr(mct, "time", SimpleNamespace(time=lambda: mct._TIEBREAK_CACHE_TTL_S + 1))
        assert mct._cache_get("k") is None
        assert "k" not in mct._tiebreak_cache

    def test_cache_get_hit_moves_to_end(self) -> None:
        mct._tiebreak_cache.clear()
        result = mct.TiebreakResult(chosen_index=0, rationale="r", used_llm=True)
        mct._cache_put("k1", result)
        mct._cache_put("k2", result)
        got = mct._cache_get("k1")
        assert got is result
        assert list(mct._tiebreak_cache.keys()) == ["k2", "k1"]

    def test_cache_put_evicts_oldest(self, monkeypatch) -> None:
        monkeypatch.setattr(mct, "_TIEBREAK_CACHE_MAX", 2)
        mct._tiebreak_cache.clear()
        result = mct.TiebreakResult(chosen_index=0, rationale="r", used_llm=True)
        mct._cache_put("k1", result)
        mct._cache_put("k2", result)
        mct._cache_put("k3", result)
        assert list(mct._tiebreak_cache.keys()) == ["k2", "k3"]


class TestTiebreakerParse:
    def test_build_prompt_shape(self) -> None:
        cands = [
            mct.SelectorCandidate(
                selector="div.a", match_count=2, is_text_only=False,
                appeared_after_ms=10, tag_hint="button", attributes={"id": "x"},
            )
        ]
        prompt = mct._build_prompt(cands, {"url": "https://ex.com", "surrounding_text": "hello" * 200})
        assert "div.a" in prompt
        assert "button" in prompt
        assert "https://ex.com" in prompt
        assert "chosen_index" in prompt

    def test_parse_empty(self) -> None:
        result = mct._parse_llm_response("")
        assert result.chosen_index == -1
        assert result.used_llm is True

    def test_parse_non_json(self) -> None:
        result = mct._parse_llm_response("no braces here")
        assert result.chosen_index == -1
        assert "non-JSON" in result.rationale

    def test_parse_valid_json(self) -> None:
        result = mct._parse_llm_response('{"chosen_index": 2, "rationale": "best"}')
        assert result.chosen_index == 2
        assert result.rationale == "best"

    def test_parse_defaults(self) -> None:
        result = mct._parse_llm_response('{"rationale": "only"}')
        assert result.chosen_index == -1

    def test_parse_garbage_index(self) -> None:
        result = mct._parse_llm_response('{"chosen_index": "abc"}')
        assert result.chosen_index == -1
        assert "parse failed" in result.rationale

    def test_parse_missing_braces_edge(self) -> None:
        result = mct._parse_llm_response("}")
        assert result.chosen_index == -1


class TestTiebreakerBreakTie:
    @pytest.fixture(autouse=True)
    def _reset_module_state(self):
        mct._circuit_breaker.reset()
        mct._tiebreak_cache.clear()
        yield

    def _candidates(self) -> List[mct.SelectorCandidate]:
        return [
            mct.SelectorCandidate(
                selector="div.a", match_count=1, is_text_only=False,
                appeared_after_ms=0, tag_hint="div",
            ),
            mct.SelectorCandidate(
                selector="button.b", match_count=1, is_text_only=False,
                appeared_after_ms=0, tag_hint="button",
            ),
        ]

    def _llm(self, raw: Any) -> Any:
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value=raw)
        return llm

    def test_disabled_flag(self, monkeypatch) -> None:
        monkeypatch.setattr(mct, "SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", False)
        result = asyncio.run(mct.break_tie(self._candidates(), {}, MagicMock()))
        assert result.chosen_index == -1
        assert result.used_llm is False
        assert "disabled" in result.rationale

    def test_circuit_open_falls_through(self) -> None:
        for _ in range(mct._CB_THRESHOLD):
            mct._circuit_breaker.record_failure()
        result = asyncio.run(mct.break_tie(self._candidates(), {}, MagicMock()))
        assert result.chosen_index == -1
        assert result.used_llm is False
        assert "circuit breaker open" in result.rationale

    def test_cache_hit(self, monkeypatch) -> None:
        monkeypatch.setattr(mct, "SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED", True)
        cached = mct.TiebreakResult(chosen_index=1, rationale="from cache", used_llm=True)
        mct._cache_put(mct._cache_key(self._candidates(), {"url": "https://ex.com"}), cached)
        result = asyncio.run(mct.break_tie(self._candidates(), {"url": "https://ex.com"}, MagicMock()))
        assert result.chosen_index == 1
        assert result.cache_hit is True
        assert result.used_llm is True

    def test_success_dict_response(self) -> None:
        llm = self._llm({"text": '{"chosen_index": 1, "rationale": "ok"}'})
        result = asyncio.run(mct.break_tie(self._candidates(), {}, llm))
        assert result.chosen_index == 1
        assert result.used_llm is True

    def test_success_string_response(self) -> None:
        llm = self._llm('{"chosen_index": 0, "rationale": "first"}')
        result = asyncio.run(mct.break_tie(self._candidates(), {}, llm))
        assert result.chosen_index == 0

    def test_out_of_range_index_corrected(self) -> None:
        llm = self._llm('{"chosen_index": 5, "rationale": "wrong"}')
        result = asyncio.run(mct.break_tie(self._candidates(), {}, llm))
        assert result.chosen_index == -1
        assert "out-of-range" in result.rationale
        assert result.used_llm is False

    def test_timeout_records_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(mct, "SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS", 0.05)
        llm = MagicMock()

        async def slow(*args, **kwargs):
            await asyncio.sleep(1.0)
            return '{"chosen_index": 0}'

        llm.generate_completion = slow
        result = asyncio.run(mct.break_tie(self._candidates(), {}, llm))
        assert result.chosen_index == -1
        assert "timeout" in result.rationale
        assert mct._circuit_breaker.failures == 1

    def test_exception_records_failure(self) -> None:
        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(mct.break_tie(self._candidates(), {}, llm))
        assert result.chosen_index == -1
        assert "LLM error" in result.rationale
        assert mct._circuit_breaker.failures == 1

    def test_cache_disabled_skips_lookup_and_put(self, monkeypatch) -> None:
        monkeypatch.setattr(mct, "SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED", False)
        llm = self._llm('{"chosen_index": 0, "rationale": "r"}')
        result = asyncio.run(mct.break_tie(self._candidates(), {}, llm))
        assert result.chosen_index == 0
        assert mct._tiebreak_cache == {}


# ===========================================================================
# action_judge
# ===========================================================================


class TestJudgeTypes:
    def test_verdict_values(self) -> None:
        assert aj.JudgeVerdict.PROCEED.value == "proceed"
        assert aj.JudgeVerdict.ESCALATE.value == "escalate"
        assert aj.JudgeVerdict.BLOCK.value == "block"

    def test_requires_review(self) -> None:
        assert aj.JudgeResult(verdict=aj.JudgeVerdict.PROCEED).requires_review is False
        assert aj.JudgeResult(verdict=aj.JudgeVerdict.ESCALATE).requires_review is True
        assert aj.JudgeResult(verdict=aj.JudgeVerdict.BLOCK).requires_review is True


class TestJudgeCircuitBreaker:
    def test_allow_closed(self) -> None:
        cb = aj._CircuitBreaker()
        assert asyncio.run(cb.allow()) is True

    def test_allow_open_blocks(self, monkeypatch) -> None:
        monkeypatch.setattr(aj, "time", SimpleNamespace(time=lambda: 1000.0))
        cb = aj._CircuitBreaker(cooldown_seconds=120)
        for _ in range(5):
            asyncio.run(cb.record_failure())
        assert asyncio.run(cb.allow()) is False
        assert cb.is_open is True

    def test_allow_after_cooldown_probe(self, monkeypatch) -> None:
        state = {"now": 1000.0}
        monkeypatch.setattr(aj, "time", SimpleNamespace(time=lambda: state["now"]))
        cb = aj._CircuitBreaker(cooldown_seconds=120)
        for _ in range(5):
            asyncio.run(cb.record_failure())
        state["now"] = 1121.0
        assert asyncio.run(cb.allow()) is True
        assert cb.is_open is False

    def test_record_success_resets(self) -> None:
        cb = aj._CircuitBreaker()
        asyncio.run(cb.record_failure())
        asyncio.run(cb.record_success())
        assert cb._failures == 0
        assert cb._opened_at is None

    def test_record_failure_reopens_after_half_open(self, monkeypatch) -> None:
        state = {"now": 1000.0}
        monkeypatch.setattr(aj, "time", SimpleNamespace(time=lambda: state["now"]))
        cb = aj._CircuitBreaker(cooldown_seconds=120)
        for _ in range(5):
            asyncio.run(cb.record_failure())
        state["now"] = 1121.0  # cooldown elapsed → half-open probe
        assert asyncio.run(cb.allow()) is True
        state["now"] = 1122.0
        asyncio.run(cb.record_failure())  # probe failed → re-open
        assert cb._opened_at == 1122.0


class TestJudgeResultCache:
    def test_get_miss(self) -> None:
        cache = aj._ResultCache()
        assert asyncio.run(cache.get("k")) is None

    def test_put_get_roundtrip(self) -> None:
        cache = aj._ResultCache()
        result = aj.JudgeResult(verdict=aj.JudgeVerdict.PROCEED)
        asyncio.run(cache.put("k", result))
        assert asyncio.run(cache.get("k")) is result

    def test_ttl_expiry(self, monkeypatch) -> None:
        monkeypatch.setattr(aj, "time", SimpleNamespace(time=lambda: 0.0))
        cache = aj._ResultCache(ttl_seconds=10)
        result = aj.JudgeResult(verdict=aj.JudgeVerdict.PROCEED)
        asyncio.run(cache.put("k", result))
        monkeypatch.setattr(aj, "time", SimpleNamespace(time=lambda: 11.0))
        assert asyncio.run(cache.get("k")) is None
        assert "k" not in cache._store

    def test_eviction(self) -> None:
        cache = aj._ResultCache(max_entries=2)
        result = aj.JudgeResult(verdict=aj.JudgeVerdict.PROCEED)
        asyncio.run(cache.put("k1", result))
        asyncio.run(cache.put("k2", result))
        asyncio.run(cache.put("k3", result))
        assert "k1" not in cache._store

    def test_clear(self) -> None:
        cache = aj._ResultCache()
        asyncio.run(cache.put("k", aj.JudgeResult(verdict=aj.JudgeVerdict.PROCEED)))
        asyncio.run(cache.clear())
        assert cache._store == {}


class TestActionJudgeEvaluate:
    @pytest.fixture(autouse=True)
    def _enable_judge(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_judge_enabled", lambda: True)
        yield

    def _judge(self, **kwargs) -> aj.ActionJudge:
        return aj.ActionJudge(**kwargs)

    def test_disabled_returns_proceed(self, monkeypatch) -> None:
        monkeypatch.setattr("core.sandbox_config.is_sandbox_judge_enabled", lambda: False)
        judge = self._judge()
        result = asyncio.run(judge.evaluate(action_description="do thing"))
        assert result.verdict == aj.JudgeVerdict.PROCEED
        assert result.rationale == "judge disabled"

    def test_cache_hit(self) -> None:
        judge = self._judge(llm_service=MagicMock())
        first = asyncio.run(judge.evaluate(
            action_description="device_execute_command('rm -rf /')",
            context="user asked",
            provenance_context=[("USER", "user request")],
        ))
        assert first.used_llm is True
        second = asyncio.run(judge.evaluate(
            action_description="device_execute_command('rm -rf /')",
            context="user asked",
            provenance_context=[("USER", "user request")],
        ))
        assert second.cached is True
        assert second.verdict == first.verdict

    def test_circuit_open_fail_open(self) -> None:
        judge = self._judge(llm_service=MagicMock())
        for _ in range(5):
            asyncio.run(judge._circuit.record_failure())
        result = asyncio.run(judge.evaluate(action_description="x"))
        assert result.verdict == aj.JudgeVerdict.PROCEED
        assert result.circuit_open is True

    def test_no_llm_service_fail_open(self) -> None:
        judge = self._judge()
        result = asyncio.run(judge.evaluate(action_description="x"))
        assert result.verdict == aj.JudgeVerdict.PROCEED
        assert "no LLM service" in result.rationale

    def test_proceed_verdict(self) -> None:
        judge = self._judge(llm_service=self._llm('{"verdict": "proceed", "rationale": "safe"}'))
        result = asyncio.run(judge.evaluate(
            action_description="send email", provenance_context=[("USER", "asked to")],
        ))
        assert result.verdict == aj.JudgeVerdict.PROCEED
        assert result.used_llm is True

    def test_escalate_verdict(self) -> None:
        judge = self._judge(llm_service=self._llm('{"verdict": "escalate", "rationale": "unsure"}'))
        result = asyncio.run(judge.evaluate(action_description="x"))
        assert result.verdict == aj.JudgeVerdict.ESCALATE

    def test_block_verdict(self) -> None:
        judge = self._judge(llm_service=self._llm('{"verdict": "block", "rationale": "injected"}'))
        result = asyncio.run(judge.evaluate(action_description="x"))
        assert result.verdict == aj.JudgeVerdict.BLOCK

    def test_timeout_fail_open(self) -> None:
        async def slow(prompt):
            await asyncio.sleep(1.0)
            return '{"verdict": "block"}'

        llm = SimpleNamespace(generate=slow)
        judge = self._judge(llm_service=llm, timeout_seconds=0.05)
        result = asyncio.run(judge.evaluate(action_description="x"))
        assert result.verdict == aj.JudgeVerdict.PROCEED
        assert result.error == "timeout"
        assert judge._circuit._failures == 1

    def test_exception_fail_open(self) -> None:
        llm = SimpleNamespace(generate=lambda p: (_ for _ in ()).throw(ValueError("down")))
        judge = self._judge(llm_service=llm)
        result = asyncio.run(judge.evaluate(action_description="x"))
        assert result.verdict == aj.JudgeVerdict.PROCEED
        assert result.error  # generic error string recorded

    def _llm(self, text: str) -> Any:
        llm = MagicMock()
        llm.complete = MagicMock(return_value=text)
        return llm


class TestActionJudgeInternals:
    def test_call_llm_sync_generate(self) -> None:
        svc = SimpleNamespace(generate=lambda p: "ok")
        judge = aj.ActionJudge(llm_service=svc)
        assert asyncio.run(judge._call_llm("prompt")) == "ok"

    def test_call_llm_async_complete(self) -> None:
        svc = SimpleNamespace(complete=AsyncMock(return_value="async-ok"))
        judge = aj.ActionJudge(llm_service=svc)
        assert asyncio.run(judge._call_llm("prompt")) == "async-ok"

    def test_call_llm_invoke_fallback(self) -> None:
        svc = SimpleNamespace(
            complete=lambda p: (_ for _ in ()).throw(RuntimeError("nope")),
            invoke=lambda p: "invoked",
        )
        judge = aj.ActionJudge(llm_service=svc)
        assert asyncio.run(judge._call_llm("prompt")) == "invoked"

    def test_call_llm_no_methods_raises(self) -> None:
        judge = aj.ActionJudge(llm_service=SimpleNamespace())
        with pytest.raises(RuntimeError):
            asyncio.run(judge._call_llm("prompt"))

    def test_build_prompt_no_provenance(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        prompt = judge._build_prompt("act", "ctx", None)
        assert "PROVENANCE: none" in prompt
        assert "act" in prompt

    def test_build_prompt_with_provenance_enum(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        prov = [(aj.JudgeVerdict.PROCEED, "chunk text"), ("TOOL_OUTPUT", "more")]  # noqa: F841
        prompt = judge._build_prompt("act", "ctx", [("TOOL_OUTPUT", "from scrape")])
        assert "TOOL_OUTPUT" in prompt

    def test_parse_response_fences(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        verdict, rationale = judge._parse_response('```json\n{"verdict": "block"}\n```')
        assert verdict == aj.JudgeVerdict.BLOCK

    def test_parse_response_invalid_verdict(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        verdict, rationale = judge._parse_response('{"verdict": "maybe", "rationale": "x"}')
        assert verdict == aj.JudgeVerdict.ESCALATE
        assert "unparsed verdict" in rationale

    def test_parse_response_bad_json(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        verdict, _ = judge._parse_response("not json")
        assert verdict == aj.JudgeVerdict.ESCALATE

    def test_parse_response_missing_verdict_defaults_escalate(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        verdict, _ = judge._parse_response('{"rationale": "x"}')
        assert verdict == aj.JudgeVerdict.ESCALATE

    def test_hash_roundtrip_and_provenance(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        h1 = judge._hash("act", "ctx", [("A", "x")])
        h2 = judge._hash("act", "ctx", [("A", "x")])
        assert h1 == h2
        assert len(h1) == 64
        h3 = judge._hash("act", "ctx", [("A", "different")])
        assert h3 != h1

    def test_hash_non_iterable_provenance(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        h = judge._hash("act", "ctx", [42, "plain"])
        assert len(h) == 64

    def test_hash_no_provenance(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        assert len(judge._hash("act", "ctx", None)) == 64

    def test_reset_circuit_and_clear_cache(self) -> None:
        judge = aj.ActionJudge(llm_service=MagicMock())
        asyncio.run(judge._circuit.record_failure())
        asyncio.run(judge.reset_circuit())
        assert judge._circuit._failures == 0
        asyncio.run(judge._cache.put("k", aj.JudgeResult(verdict=aj.JudgeVerdict.PROCEED)))
        asyncio.run(judge.clear_cache())
        assert judge._cache._store == {}

    def test_get_default_judge_singleton(self, monkeypatch) -> None:
        monkeypatch.setattr(aj, "_default_judge", None)
        judge = aj.get_default_judge()
        assert aj.get_default_judge() is judge
        assert judge.llm_service is None


# ===========================================================================
# intent_detector
# ===========================================================================


class TestIntentDetectorBasic:
    def test_is_valid_intent(self) -> None:
        assert idet.is_valid_intent("coding") is True
        assert idet.is_valid_intent("web_browsing") is True
        assert idet.is_valid_intent("bogus") is False

    def test_empty_prompt(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("   ")
        assert result.category is None
        assert result.confidence == 0.0

    def test_no_signals_none(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("qwerty asdfgh")
        assert result.category is None
        assert result.confidence == 0.0

    def test_coding(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("fix this bug in my python function")
        assert result.category == "coding"

    def test_data_analysis(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("analyze this dataset and plot a chart")
        assert result.category == "data_analysis"

    def test_web_browsing(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("search the web for latest news")
        assert result.category == "web_browsing"

    def test_creative_writing(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("write a poem about spring")
        assert result.category == "creative_writing"

    def test_reasoning(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("prove that x implies y")
        assert result.category == "reasoning"

    def test_conversation_low_weight(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("hello hi thanks")
        assert result.category == "conversation"

    def test_code_fence_boost(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("```python\ndef f():\n    pass\n```")
        assert result.category == "coding"

    def test_url_boost(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("check https://example.com for me")
        assert result.category == "web_browsing"

    def test_long_formal_boost(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("therefore, hence, thus we conclude")
        assert result.category == "reasoning"

    def test_confidence_capped_at_one(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("analyze this dataset and plot a chart, regression correlation")
        assert result.category == "data_analysis"
        assert result.confidence == 1.0

    def test_confidence_at_threshold(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("analyze the numbers")
        assert result.category == "data_analysis"
        assert result.confidence == pytest.approx(3.0 / 9.0)


class TestIntentDetectorToolsAndStickiness:
    def test_tool_prefix_dict(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("do something", tools=[{"name": "browser_tab"}])
        assert result.category == "web_browsing"

    def test_tool_prefix_function_name(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("do something", tools=[{"function": {"name": "code_edit"}}])
        assert result.category == "coding"

    def test_tool_prefix_object(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("do something", tools=[SimpleNamespace(name="search_web")])
        assert result.category == "web_browsing"

    def test_tool_string_name(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("do something", tools=["database_query"])
        assert result.category == "data_analysis"

    def test_tool_without_name_skipped(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("hello hi thanks", tools=[{}, SimpleNamespace(name=None), 42])
        assert result.category == "conversation"

    def test_sticky_bias_keeps_neutral_turn(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("hello", recent_intents=["coding", "coding", "coding"])
        assert result.category == "coding"

    def test_sticky_history_too_short(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("hello", recent_intents=["coding"])
        assert result.category is None

    def test_sticky_window_truncated_below_min(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("hello", recent_intents=["coding", "coding"])
        assert result.category is None

    def test_sticky_window_shorter_than_agreement(self, monkeypatch) -> None:
        monkeypatch.setattr(idet, "_STICKY_HISTORY_WINDOW", 2)
        detector = idet.IntentDetector()
        result = detector.detect("hello", recent_intents=["coding", "coding", "coding"])
        assert result.category is None

    def test_sticky_mixed_history_no_bias(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("hello", recent_intents=["coding", "coding", "conversation"])
        assert result.category is None

    def test_penalties_knock_out_winner(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("fix this bug", category_penalties={"coding": 10})
        assert result.category is None

    def test_penalties_unknown_category_ignored(self) -> None:
        detector = idet.IntentDetector()
        result = detector.detect("fix this bug", category_penalties={"nope": 10})
        assert result.category == "coding"

    def test_extract_tool_name_variants(self) -> None:
        assert idet._extract_tool_name("plain_tool") == "plain_tool"
        assert idet._extract_tool_name({"name": "a"}) == "a"
        assert idet._extract_tool_name({"function": {"name": "b"}}) == "b"
        assert idet._extract_tool_name({"function": {}}) is None
        assert idet._extract_tool_name(SimpleNamespace(name="c")) == "c"
        assert idet._extract_tool_name(42) is None

    def test_get_intent_detector_singleton(self, monkeypatch) -> None:
        monkeypatch.setattr(idet, "_default_detector", None)
        detector = idet.get_intent_detector()
        assert idet.get_intent_detector() is detector


class TestNudgeTier:
    def test_invalid_base_tier_unchanged(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("coding", "not-a-tier") == "not-a-tier"

    def test_coding_floors_to_versatile(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("coding", "micro") == "versatile"

    def test_coding_already_above_floor(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("coding", "heavy") == "heavy"

    def test_reasoning_floors_to_versatile(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("reasoning", "standard") == "versatile"

    def test_conversation_caps_at_standard(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("conversation", "heavy") == "standard"

    def test_conversation_below_cap_unchanged(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("conversation", "micro") == "micro"

    def test_data_analysis_floors_to_standard(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("data_analysis", "micro") == "standard"

    def test_creative_writing_floors_to_standard(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("creative_writing", "micro") == "standard"

    def test_web_browsing_no_nudge(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier("web_browsing", "micro") == "micro"

    def test_none_intent_unchanged(self) -> None:
        detector = idet.IntentDetector()
        assert detector.nudge_tier(None, "micro") == "micro"


# ===========================================================================
# self_consistency_voter
# ===========================================================================


class TestVoterVote:
    def _handler(self, samples: List[Any]) -> Any:
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(side_effect=samples)
        return handler

    def test_all_samples_fail_returns_none(self) -> None:
        handler = self._handler([RuntimeError("boom"), RuntimeError("boom")])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote("prompt", dict, sample_count=2))
        assert result is None

    def test_single_valid_sample_returned(self) -> None:
        plan = {"action": "send_email"}
        handler = self._handler([RuntimeError("x"), plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote("prompt", dict, sample_count=2))
        assert result == plan

    def test_majority_vote_wins(self) -> None:
        a = {"action": "send_email", "to": "x"}
        b = {"action": "send_email", "to": "y"}
        handler = self._handler([a, b, a])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote("prompt", dict, sample_count=3))
        assert result == a

    def test_all_distinct_falls_back_to_first(self) -> None:
        a = {"action": "send_email", "to": "x"}
        b = {"action": "send_email", "to": "y"}
        c = {"action": "send_email", "to": "z"}
        handler = self._handler([a, b, c])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote("prompt", dict, sample_count=3))
        assert result == a

    def test_sample_count_floor_of_one(self) -> None:
        plan = {"action": "x"}
        handler = self._handler([plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote("prompt", dict, sample_count=0))
        assert result == plan
        assert handler.generate_structured_response.await_count == 1

    def test_kwargs_extracted_once_and_forwarded(self) -> None:
        plan = {"action": "x"}
        handler = self._handler([plan, plan, plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote(
            "prompt", dict, sample_count=3,
            system_instruction="be careful",
            task_type="plan",
            chain_id="chain-1",
            image_payload="img",
            extra_kwarg=42,
        ))
        assert result == plan
        for call in handler.generate_structured_response.await_args_list:
            kwargs = call.kwargs
            assert kwargs["system_instruction"] == "be careful"
            assert kwargs["task_type"] == "plan"
            assert kwargs["chain_id"] == "chain-1"
            assert kwargs["image_payload"] == "img"
            assert kwargs["allow_moa"] is False
            assert kwargs["extra_kwarg"] == 42

    def test_diversity_overlays_enabled(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.hallucination_config.is_moa_diversity_enabled", lambda: True
        )
        plan = {"action": "x"}
        handler = self._handler([plan, plan, plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote("prompt", dict, sample_count=3))
        assert result == plan
        sys_instructions = [
            c.kwargs["system_instruction"]
            for c in handler.generate_structured_response.await_args_list
        ]
        assert any("step by step" in s for s in sys_instructions)

    def test_cascade_flag_forwarded(self) -> None:
        plan = {"action": "x"}
        handler = self._handler([plan, plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        asyncio.run(voter.vote("prompt", dict, sample_count=2, cascade=True))
        for call in handler.generate_structured_response.await_args_list:
            assert call.kwargs["cascade"] is True

    def test_temperature_spread_passed(self) -> None:
        plan = {"action": "x"}
        handler = self._handler([plan, plan, plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        asyncio.run(voter.vote("prompt", dict, sample_count=3))
        temps = [c.kwargs["temperature"] for c in handler.generate_structured_response.await_args_list]
        assert temps == [0.6, 0.7, 0.8]

    def test_base_temperature_recenters(self) -> None:
        plan = {"action": "x"}
        handler = self._handler([plan, plan, plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        asyncio.run(voter.vote("prompt", dict, sample_count=3, temperature=1.0))
        temps = [c.kwargs["temperature"] for c in handler.generate_structured_response.await_args_list]
        assert temps == [0.9, 1.0, 1.1]

    def test_agent_id_forwarded(self) -> None:
        plan = {"action": "x"}
        handler = self._handler([plan, plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        asyncio.run(voter.vote("prompt", dict, sample_count=2, agent_id="agent-7"))
        assert handler.generate_structured_response.await_args_list[0].kwargs["agent_id"] == "agent-7"


class TestVoteWithConsensus:
    def _handler(self, samples: List[Any]) -> Any:
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(side_effect=samples)
        return handler

    def test_all_fail_result_shape(self) -> None:
        handler = self._handler([RuntimeError("x"), RuntimeError("x")])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=2))
        assert result.winner is None
        assert result.agreement_ratio == 0.0
        assert result.level == scv.LEVEL_AMBIGUOUS
        assert result.valid_count == 0
        assert result.distinct_hashes == 0
        assert result.prompt_hash is not None
        assert result.temperatures == [0.65, 0.75]

    def test_single_valid_agreement_one(self) -> None:
        plan = {"action": "x"}
        handler = self._handler([plan])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=1))
        assert result.winner == plan
        assert result.agreement_ratio == 1.0
        assert result.level == scv.LEVEL_HIGH
        assert result.winner_count == 1
        assert len(result.winner_hash) == 16

    def test_majority_partial_level(self) -> None:
        a = {"action": "send_email"}
        b = {"action": "delete_row"}
        handler = self._handler([a, b, a])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=3))
        assert result.winner == a
        assert result.winner_count == 2
        assert result.level == scv.LEVEL_PARTIAL

    def test_unanimous_high_level(self) -> None:
        a = {"action": "send_email"}
        handler = self._handler([a, a, a])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=3))
        assert result.winner == a
        assert result.winner_count == 3
        assert result.level == scv.LEVEL_HIGH

    def test_split_vote_ambiguous_level(self) -> None:
        a = {"action": "send_email"}
        b = {"action": "delete_row"}
        c = {"action": "create_record"}
        handler = self._handler([a, b, c])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=3))
        assert result.winner == a
        assert result.winner_count == 1
        assert result.level == scv.LEVEL_AMBIGUOUS
        assert result.distinct_hashes == 3

    def test_ambiguous_level(self, monkeypatch) -> None:
        monkeypatch.setattr("core.hallucination_config.get_self_consistency_partial_threshold", lambda: 0.6)
        a = {"action": "send_email"}
        b = {"action": "delete_row"}
        c = {"action": "create_record"}
        handler = self._handler([a, b, c])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=3))
        assert result.level == scv.LEVEL_AMBIGUOUS

    def test_sample_failure_excluded_from_valid(self) -> None:
        a = {"action": "send_email"}
        handler = self._handler([a, RuntimeError("x"), a])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=3))
        assert result.valid_count == 2
        assert result.winner == a

    def test_diversity_overlays_enabled(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.hallucination_config.is_moa_diversity_enabled", lambda: True
        )
        a = {"action": "send_email"}
        handler = self._handler([a, a, a])
        voter = scv.SelfConsistencyVoter(handler=handler)
        result = asyncio.run(voter.vote_with_consensus("prompt", dict, sample_count=3))
        assert result.winner == a
        sys_instructions = [
            c.kwargs["system_instruction"]
            for c in handler.generate_structured_response.await_args_list
        ]
        assert any("edge cases" in s for s in sys_instructions)

    def test_prompt_hash_stable(self) -> None:
        a = {"action": "send_email"}
        handler = self._handler([a, a])
        voter = scv.SelfConsistencyVoter(handler=handler)
        r1 = asyncio.run(voter.vote_with_consensus("same prompt", dict, sample_count=2))
        r2 = asyncio.run(voter.vote_with_consensus("same prompt", dict, sample_count=2))
        assert r1.prompt_hash == r2.prompt_hash


class TestVoterHelpers:
    def test_vote_result_properties(self) -> None:
        high = scv.VoteResult(winner={}, agreement_ratio=1.0, level=scv.LEVEL_HIGH, sample_count=3, valid_count=3, winner_count=3, distinct_hashes=1)
        assert high.is_high is True
        assert high.requires_review is False
        partial = scv.VoteResult(winner={}, agreement_ratio=0.6, level=scv.LEVEL_PARTIAL, sample_count=3, valid_count=3, winner_count=2, distinct_hashes=2)
        assert partial.requires_review is True
        none_result = scv.VoteResult(winner=None, agreement_ratio=0.0, level=scv.LEVEL_AMBIGUOUS, sample_count=3, valid_count=0, winner_count=0, distinct_hashes=0)
        assert none_result.is_no_samples is True

    def test_is_irreversible_none(self) -> None:
        assert scv.SelfConsistencyVoter.is_irreversible(None) is False

    def test_is_irreversible_dict_key_match(self) -> None:
        assert scv.SelfConsistencyVoter.is_irreversible({"send_email": "now"}) is True

    def test_is_irreversible_dict_value_match(self) -> None:
        assert scv.SelfConsistencyVoter.is_irreversible({"action": "send_email"}) is True

    def test_is_irreversible_benign_fields_ignored(self) -> None:
        plan = {"created_at": "2026-01-01", "updated_by": "me", "action": "read_docs"}
        assert scv.SelfConsistencyVoter.is_irreversible(plan) is False

    def test_is_irreversible_pydantic_v2(self) -> None:
        obj = SimpleNamespace(model_dump=lambda: {"action": "delete_user"})
        assert scv.SelfConsistencyVoter.is_irreversible(obj) is True

    def test_is_irreversible_pydantic_v1(self) -> None:
        obj = SimpleNamespace(dict=lambda: {"action": "read"})
        assert scv.SelfConsistencyVoter.is_irreversible(obj) is False

    def test_is_irreversible_namespace(self) -> None:
        obj = SimpleNamespace(action="transfer_money")
        assert scv.SelfConsistencyVoter.is_irreversible(obj) is True

    def test_is_irreversible_scalar_fallback(self) -> None:
        assert scv.SelfConsistencyVoter.is_irreversible("deploy now") is True
        assert scv.SelfConsistencyVoter.is_irreversible("hello world") is False

    def test_hash_sample_pydantic_v2(self) -> None:
        obj = SimpleNamespace(model_dump=lambda mode="json": {"a": 1})
        h = scv.SelfConsistencyVoter._hash_sample(obj)
        assert len(h) == 64

    def test_hash_sample_pydantic_v1(self) -> None:
        obj = SimpleNamespace(dict=lambda: {"a": 1})
        h = scv.SelfConsistencyVoter._hash_sample(obj)
        assert len(h) == 64

    def test_hash_sample_dict(self) -> None:
        h = scv.SelfConsistencyVoter._hash_sample({"b": 2, "a": 1})
        h2 = scv.SelfConsistencyVoter._hash_sample({"a": 1, "b": 2})
        assert h == h2

    def test_hash_sample_scalar(self) -> None:
        h = scv.SelfConsistencyVoter._hash_sample(SimpleNamespace(x=1))
        assert len(h) == 64

    def test_temperatures_for_default_base(self) -> None:
        assert scv.SelfConsistencyVoter._temperatures_for(3) == [0.6, 0.7, 0.8]

    def test_temperatures_for_recenter_clamped(self) -> None:
        temps = scv.SelfConsistencyVoter._temperatures_for(3, base=2.0)
        assert temps == [1.5, 1.5, 1.5]
        temps_low = scv.SelfConsistencyVoter._temperatures_for(3, base=0.0)
        assert temps_low == [0.0, 0.0, 0.1]

    def test_level_from_agreement(self) -> None:
        assert scv.SelfConsistencyVoter._level_from_agreement(1.0) == scv.LEVEL_HIGH
        assert scv.SelfConsistencyVoter._level_from_agreement(0.6) == scv.LEVEL_PARTIAL
        assert scv.SelfConsistencyVoter._level_from_agreement(0.4) == scv.LEVEL_AMBIGUOUS

    def test_hash_prompt(self) -> None:
        h = scv.SelfConsistencyVoter._hash_prompt("hello")
        assert len(h) == 16

    def test_diversity_overlays_disabled(self) -> None:
        assert scv.SelfConsistencyVoter.diversity_overlays(3) == ["", "", ""]
        assert scv.SelfConsistencyVoter.diversity_overlays(0) == [""]

    def test_diversity_overlays_enabled(self) -> None:
        overlays = scv.SelfConsistencyVoter.diversity_overlays(5, enabled=True)
        assert len(overlays) == 5
        assert overlays[0] == overlays[4]  # rotates through 4 perspectives
        assert scv.SelfConsistencyVoter.diversity_overlays(0, enabled=True) == [""]

    def test_majority_vote_all_distinct(self) -> None:
        samples = [{"a": 1}, {"a": 2}, {"a": 3}]
        voter = scv.SelfConsistencyVoter(handler=MagicMock())
        winner = voter._majority_vote(samples)
        assert winner == samples[0]

    def test_majority_vote_clear_winner(self) -> None:
        samples = [{"a": 1}, {"a": 2}, {"a": 1}]
        voter = scv.SelfConsistencyVoter(handler=MagicMock())
        winner = voter._majority_vote(samples)
        assert winner == {"a": 1}


# ===========================================================================
# stage_router
# ===========================================================================


def _outcome(
    name: str,
    severity: sr.SignalSeverity = sr.SignalSeverity.NONE,
    is_read: bool = False,
    is_write: bool = False,
    success: bool = True,
) -> sr.ToolOutcome:
    return sr.ToolOutcome(
        tool_name=name, is_read=is_read, is_write=is_write,
        severity=severity, success=success,
    )


def _default_router(**kwargs) -> sr.StageRouter:
    kwargs.setdefault("enabled", True)
    kwargs.setdefault("enforce", False)
    return sr.StageRouter(**kwargs)


class TestSeverityAndRoles:
    def test_classify_severity_none(self) -> None:
        assert sr.classify_severity(None) == sr.SignalSeverity.NONE

    def test_classify_severity_critical(self) -> None:
        assert sr.classify_severity("Error: permission denied") == sr.SignalSeverity.CRITICAL
        assert sr.classify_severity("fatal corruption detected") == sr.SignalSeverity.CRITICAL

    def test_classify_severity_major(self) -> None:
        assert sr.classify_severity("tool execution failed") == sr.SignalSeverity.MAJOR
        assert sr.classify_severity("timeout after 30s") == sr.SignalSeverity.MAJOR

    def test_classify_severity_minor(self) -> None:
        assert sr.classify_severity("warning: missing field") == sr.SignalSeverity.MINOR
        assert sr.classify_severity("no results found") == sr.SignalSeverity.MINOR

    def test_classify_severity_none_text(self) -> None:
        assert sr.classify_severity("all good here") == sr.SignalSeverity.NONE

    def test_classify_severity_case_insensitive(self) -> None:
        assert sr.classify_severity("Permission Denied") == sr.SignalSeverity.CRITICAL

    def test_classify_tool_roles_read(self) -> None:
        is_read, is_write = sr.classify_tool_roles("search_documents")
        assert is_read is True and is_write is False

    def test_classify_tool_roles_write(self) -> None:
        is_read, is_write = sr.classify_tool_roles("create_record")
        assert is_read is False and is_write is True

    def test_classify_tool_roles_both(self) -> None:
        is_read, is_write = sr.classify_tool_roles("update_and_query")
        assert is_read is True and is_write is True

    def test_classify_tool_roles_neither(self) -> None:
        is_read, is_write = sr.classify_tool_roles("think")
        assert is_read is False and is_write is False


class TestParseToolHistory:
    def test_parses_json_action_blocks(self) -> None:
        history = (
            'Action: {"tool": "search_documents", "params": {"q": "x"}}\n'
            "Observation: found 3 docs\n"
            'Action: {"tool": "create_record", "params": {}}\n'
            "Observation: Error: tool execution failed\n"
        )
        entries = sr.parse_tool_history(history)
        assert len(entries) == 2
        assert entries[0].outcome.tool_name == "search_documents"
        assert entries[0].outcome.is_read is True
        assert entries[0].outcome.success is True
        assert entries[1].outcome.tool_name == "create_record"
        assert entries[1].outcome.severity == sr.SignalSeverity.MAJOR
        assert entries[1].outcome.success is False

    def test_parses_parallel_call_form(self) -> None:
        history = 'Action: search_documents({"q": "x"})\nObservation: ok\n'
        entries = sr.parse_tool_history(history)
        assert len(entries) == 1
        assert entries[0].outcome.tool_name == "search_documents"

    def test_empty_history(self) -> None:
        assert sr.parse_tool_history("") == []
        assert sr.parse_tool_history(None) == []

    def test_empty_action_text_skipped(self) -> None:
        history = (
            'Action: {"tool": "get_thing"}\nObservation: ok\n'
            "Action:\nObservation: bare"
        )
        entries = sr.parse_tool_history(history)
        assert len(entries) == 1
        assert entries[0].outcome.tool_name == "get_thing"

    def test_only_empty_action_blocks(self) -> None:
        assert sr.parse_tool_history("Action:\nObservation: bare") == []

    def test_non_dict_json_skipped(self) -> None:
        history = "Action: 42\nObservation: ok\n"
        assert sr.parse_tool_history(history) == []

    def test_malformed_no_tool_skipped(self) -> None:
        history = "Action: not json at all\nObservation: whatever\n"
        assert sr.parse_tool_history(history) == []

    def test_observation_truncated_to_500(self) -> None:
        history = (
            'Action: {"tool": "get_thing"}\n'
            f"Observation: {'x' * 1000}\n"
        )
        entries = sr.parse_tool_history(history)
        assert len(entries[0].observation) == 500

    def test_ignores_blocks_without_action(self) -> None:
        history = "Observation: bare observation without action\n"
        assert sr.parse_tool_history(history) == []


class TestWeightedRandomSplit:
    def test_pick_respects_weights_seeded(self) -> None:
        split = sr.WeightedRandomSplit({"efficient": 0.7, "capable": 0.3}, seed=42)
        picks = [split.pick() for _ in range(20)]
        assert all(p in (sr.EFFICIENT, sr.CAPABLE) for p in picks)

    def test_invalid_weights_raise(self) -> None:
        with pytest.raises(ValueError):
            sr.WeightedRandomSplit({"efficient": 0, "capable": 0})
        with pytest.raises(ValueError):
            sr.WeightedRandomSplit({"nope": 1.0})

    def test_weights_normalized(self) -> None:
        split = sr.WeightedRandomSplit({"efficient": 2, "capable": 2}, seed=1)
        assert split._weights == [0.5, 0.5]

    def test_single_group_split(self) -> None:
        split = sr.WeightedRandomSplit({"capable": 1.0}, seed=7)
        assert split.pick() == sr.CAPABLE

    def test_from_env_empty_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", "")
        assert sr.WeightedRandomSplit.from_env() is None

    def test_from_env_valid(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", '{"efficient": 0.5, "capable": 0.5}')
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT_SEED", "3")
        split = sr.WeightedRandomSplit.from_env()
        assert split is not None
        assert split.pick() in (sr.EFFICIENT, sr.CAPABLE)

    def test_from_env_invalid_json(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", "not-json")
        assert sr.WeightedRandomSplit.from_env() is None

    def test_from_env_non_dict(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", "[1, 2]")
        assert sr.WeightedRandomSplit.from_env() is None


class TestResolveAgentPolicy:
    def test_no_config_uses_globals(self) -> None:
        policy = sr.resolve_agent_policy(None, global_enforce=True)
        assert policy.enforce is True
        assert policy.source == "global"
        assert policy.picker == sr.StagePicker.EFFICIENT_FIRST

    def test_agent_config_overrides(self) -> None:
        policy = sr.resolve_agent_policy(
            {"stage_routing": {"enforce": True, "picker": "capable_first", "confidence_threshold": 0.45, "window": 5}},
            global_enforce=False,
        )
        assert policy.enforce is True
        assert policy.source == "agent-config"
        assert policy.picker == sr.StagePicker.CAPABLE_FIRST
        assert policy.confidence_threshold == 0.45
        assert policy.window == 5

    def test_invalid_picker_falls_back_with_warning(self) -> None:
        policy = sr.resolve_agent_policy(
            {"stage_routing": {"picker": "bogus"}},
            global_picker=sr.StagePicker.EFFICIENT_FIRST,
        )
        assert policy.picker == sr.StagePicker.EFFICIENT_FIRST

    def test_threshold_clamped(self) -> None:
        policy = sr.resolve_agent_policy({"stage_routing": {"confidence_threshold": 5.0}})
        assert policy.confidence_threshold == 1.0
        policy = sr.resolve_agent_policy({"stage_routing": {"confidence_threshold": -1}})
        assert policy.confidence_threshold == 0.0

    def test_window_ignored_when_non_positive(self) -> None:
        policy = sr.resolve_agent_policy({"stage_routing": {"window": -2}})
        assert policy.window == sr.stage_routing_window()

    def test_non_dict_block_ignored(self) -> None:
        policy = sr.resolve_agent_policy({"stage_routing": "yes"})
        assert policy.source == "global"


class TestStageRouterSignals:
    def test_empty_outcomes(self) -> None:
        router = _default_router()
        signals = router.extract_signals([])
        assert signals.severity == 0.0
        assert signals.spinning is False
        assert signals.production_intensity == 0.0

    def test_window_respects_parameter(self) -> None:
        router = _default_router(window=2)
        outcomes = [
            _outcome("get_a", severity=sr.SignalSeverity.MINOR),
            _outcome("get_b"),
            _outcome("get_c"),
        ]
        signals = router.extract_signals(outcomes, window=2)
        assert signals.severity == float(sr.SignalSeverity.NONE)

    def test_max_severity_windowed(self) -> None:
        router = _default_router()
        outcomes = [
            _outcome("get_a", severity=sr.SignalSeverity.MINOR),
            _outcome("get_b", severity=sr.SignalSeverity.MAJOR),
        ]
        signals = router.extract_signals(outcomes)
        assert signals.severity == 2.0

    def test_critical_flag(self) -> None:
        router = _default_router()
        signals = router.extract_signals([_outcome("get_a", severity=sr.SignalSeverity.CRITICAL)])
        assert signals.critical is True

    def test_spinning_neutral_repeated(self) -> None:
        router = _default_router()
        outcomes = [_outcome("think") for _ in range(3)]
        signals = router.extract_signals(outcomes)
        assert signals.spinning is True

    def test_spinning_neutral_trouble(self) -> None:
        router = _default_router()
        outcomes = [
            _outcome("think", severity=sr.SignalSeverity.MINOR),
            _outcome("think", success=False),
        ]
        signals = router.extract_signals(outcomes)
        assert signals.spinning is True

    def test_not_spinning_with_reads(self) -> None:
        router = _default_router()
        outcomes = [_outcome("search_x", is_read=True), _outcome("search_x", is_read=True)]
        signals = router.extract_signals(outcomes)
        assert signals.spinning is False

    def test_exploring(self) -> None:
        router = _default_router()
        outcomes = [_outcome("search_x", is_read=True), _outcome("get_y", is_read=True)]
        signals = router.extract_signals(outcomes)
        assert signals.exploring is True

    def test_not_exploring_with_writes(self) -> None:
        router = _default_router()
        outcomes = [_outcome("search_x", is_read=True), _outcome("save_y", is_write=True)]
        signals = router.extract_signals(outcomes)
        assert signals.exploring is False

    def test_production_intensity(self) -> None:
        router = _default_router(window=4)
        outcomes = [
            _outcome("save_a", is_write=True),
            _outcome("save_b", is_write=True),
            _outcome("get_c", is_read=True),
            _outcome("get_d", is_read=True),
        ]
        signals = router.extract_signals(outcomes)
        assert signals.production_intensity == 0.5

    def test_to_json(self) -> None:
        signals = sr.StageSignals(severity=1.0, spinning=True, critical=True)
        parsed = json.loads(signals.to_json())
        assert parsed["severity"] == 1.0
        assert parsed["spinning"] is True


class TestStageRouterScore:
    def test_score_zero_for_benign_turn(self) -> None:
        router = _default_router()
        signals = sr.StageSignals()
        assert router._score(signals) == 0.0

    def test_score_positive_for_problems(self) -> None:
        router = _default_router()
        signals = sr.StageSignals(severity=3.0, spinning=True, exploring=True)
        assert router._score(signals) > 0

    def test_score_negative_for_production(self) -> None:
        router = _default_router()
        signals = sr.StageSignals(production_intensity=1.0)
        assert router._score(signals) < 0


class TestStageRouterDecide:
    def test_critical_override(self) -> None:
        router = _default_router()
        decision = router.decide([_outcome("get_a", severity=sr.SignalSeverity.CRITICAL)])
        assert decision.selected_group == sr.CAPABLE
        assert decision.source == sr.DecisionSource.OVERRIDE.value
        assert decision.confidence == 1.0
        assert decision.default_group == sr.EFFICIENT

    def test_dimensions_capable(self) -> None:
        router = _default_router(confidence_threshold=0.2)
        decision = router.decide([
            _outcome("get_a", severity=sr.SignalSeverity.MAJOR, success=False),
            _outcome("get_b", severity=sr.SignalSeverity.MINOR),
        ])
        assert decision.selected_group == sr.CAPABLE
        assert decision.source == sr.DecisionSource.DIMENSIONS.value

    def test_dimensions_efficient(self) -> None:
        router = _default_router(confidence_threshold=0.2)
        decision = router.decide([_outcome("save_a", is_write=True), _outcome("save_b", is_write=True)])
        assert decision.selected_group == sr.EFFICIENT
        assert decision.source == sr.DecisionSource.DIMENSIONS.value

    def test_fall_open_efficient_first(self) -> None:
        router = _default_router()
        decision = router.decide([_outcome("get_a")])
        assert decision.selected_group == sr.EFFICIENT
        assert decision.source == sr.DecisionSource.FALL_OPEN.value
        assert "confidence" in decision.rationale

    def test_fall_open_capable_first(self) -> None:
        router = _default_router(picker=sr.StagePicker.CAPABLE_FIRST)
        decision = router.decide([_outcome("get_a")])
        assert decision.selected_group == sr.CAPABLE
        assert decision.default_group == sr.CAPABLE

    def test_policy_overrides_router(self) -> None:
        router = _default_router(picker=sr.StagePicker.EFFICIENT_FIRST)
        policy = sr.AgentStagePolicy(
            picker=sr.StagePicker.CAPABLE_FIRST,
            confidence_threshold=0.1,
            window=1,
        )
        decision = router.decide([_outcome("get_a")], policy=policy)
        assert decision.selected_group == sr.CAPABLE

    def test_split_forces_applied_group(self) -> None:
        split = sr.WeightedRandomSplit({"capable": 1.0}, seed=1)
        router = _default_router(split=split)
        decision = router.decide([_outcome("get_a")], use_split=True)
        assert decision.split_group == sr.CAPABLE
        assert decision.applied_group == sr.CAPABLE
        assert "harness split" in decision.rationale

    def test_split_never_rides_critical(self) -> None:
        split = sr.WeightedRandomSplit({"efficient": 1.0}, seed=1)
        router = _default_router(split=split)
        decision = router.decide(
            [_outcome("get_a", severity=sr.SignalSeverity.CRITICAL)],
            use_split=True,
        )
        assert decision.split_group == sr.EFFICIENT
        assert decision.applied_group == sr.CAPABLE

    def test_split_without_split_instance_ignored(self) -> None:
        router = _default_router()
        decision = router.decide([_outcome("get_a")], use_split=True)
        assert decision.split_group is None
        assert decision.applied_group == decision.selected_group

    def test_constructor_picker_coercion(self) -> None:
        router = _default_router(picker="capable_first")
        assert router.picker == sr.StagePicker.CAPABLE_FIRST

    def test_constructor_threshold_clamped(self) -> None:
        router = _default_router(confidence_threshold=2.0)
        assert router.confidence_threshold == 1.0
        router = _default_router(confidence_threshold=-1.0)
        assert router.confidence_threshold == 0.0

    def test_constructor_window_floor(self) -> None:
        router = _default_router(window=-5)
        assert router.window == 1

    def test_enforce_requires_enabled(self) -> None:
        router = sr.StageRouter(enabled=False, enforce=True)
        assert router.enforce is False


class TestHandoffNotes:
    def test_no_previous_group_no_note(self) -> None:
        router = _default_router()
        assert router.handoff_note_for(sr.EFFICIENT, None) is None

    def test_same_group_no_note(self) -> None:
        router = _default_router()
        assert router.handoff_note_for(sr.EFFICIENT, sr.EFFICIENT) is None

    def test_to_capable_note(self) -> None:
        router = _default_router()
        note = router.handoff_note_for(sr.CAPABLE, sr.EFFICIENT)
        assert note is not None and "capable tier" in note

    def test_to_efficient_note(self) -> None:
        router = _default_router()
        note = router.handoff_note_for(sr.EFFICIENT, sr.CAPABLE)
        assert note is not None and "efficient tier" in note

    def test_handoff_note_in_decision(self) -> None:
        router = _default_router()
        decision = router.decide(
            [_outcome("get_a", severity=sr.SignalSeverity.MAJOR, success=False)],
            previous_group=sr.EFFICIENT,
            policy=sr.AgentStagePolicy(confidence_threshold=0.1),
        )
        assert decision.handoff_note is not None


class TestDecideForHistory:
    def test_disabled_returns_none(self) -> None:
        router = sr.StageRouter(enabled=False)
        decision = asyncio.run(router.decide_for_history("Action: x\nObservation: y\n"))
        assert decision is None

    def test_audit_recorded_with_metadata(self, monkeypatch) -> None:
        db = FakeDb()
        fake_session_patch(monkeypatch, db)
        router = _default_router()
        decision = asyncio.run(router.decide_for_history(
            'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n',
            agent_id="agent-1", workspace_id="ws-1", tenant_id="t-1",
            execution_id="e-1", step_index=3,
        ))
        assert decision is not None
        assert len(db.added) == 1
        row = db.added[0]
        assert row.agent_id == "agent-1"
        assert row.workspace_id == "ws-1"
        assert row.tenant_id == "t-1"
        assert row.execution_id == "e-1"
        assert row.step_index == 3
        assert row.selected_group == sr.EFFICIENT
        assert row.enforced is False
        assert row.policy_source == "global"

    def test_audit_with_policy(self, monkeypatch) -> None:
        db = FakeDb()
        fake_session_patch(monkeypatch, db)
        router = _default_router()
        policy = sr.AgentStagePolicy(
            enforce=True,
            picker=sr.StagePicker.CAPABLE_FIRST,
            confidence_threshold=0.4,
            window=2,
            source="agent-config",
        )
        decision = asyncio.run(router.decide_for_history(
            'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n',
            policy=policy,
        ))
        assert decision is not None
        row = db.added[0]
        assert row.enforced is True
        assert row.picker == sr.StagePicker.CAPABLE_FIRST.value
        assert row.confidence_threshold == 0.4
        assert row.policy_source == "agent-config"
        assert row.signals is not None

    def test_audit_disabled_skips_persist(self, monkeypatch) -> None:
        db = FakeDb()
        fake_session_patch(monkeypatch, db)
        router = _default_router(audit=False)
        decision = asyncio.run(router.decide_for_history(
            'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n'
        ))
        assert decision is not None
        assert db.added == []

    def test_audit_failure_never_raises(self, monkeypatch) -> None:
        def broken_db():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken_db)
        router = _default_router()
        decision = asyncio.run(router.decide_for_history(
            'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n'
        ))
        assert decision is not None

    def test_exception_in_decision_returns_none(self, monkeypatch) -> None:
        router = _default_router()
        monkeypatch.setattr(sr, "parse_tool_history", lambda h: (_ for _ in ()).throw(RuntimeError("boom")))
        decision = asyncio.run(router.decide_for_history("history"))
        assert decision is None

    def test_decision_id_is_uuid(self) -> None:
        router = _default_router()
        d1 = router.decide([_outcome("get_a")])
        d2 = router.decide([_outcome("get_a")])
        assert d1.id != d2.id


class TestModelTypeMapping:
    def test_none_decision(self) -> None:
        assert sr.map_decision_to_model_type(None, enforce=True) is None

    def test_shadow_mode(self) -> None:
        decision = _default_router().decide([_outcome("get_a")])
        assert sr.map_decision_to_model_type(decision, enforce=False) is None

    def test_enforced_capable(self) -> None:
        decision = _default_router().decide([_outcome("get_a", severity=sr.SignalSeverity.CRITICAL)])
        assert sr.map_decision_to_model_type(decision, enforce=True) == "quality"

    def test_enforced_efficient(self) -> None:
        decision = _default_router().decide([_outcome("get_a")])
        assert sr.map_decision_to_model_type(decision, enforce=True) == "fast"


class TestDecisionCarrier:
    def test_set_get_roundtrip(self) -> None:
        sr.set_stage_decision_carrier("d-1")
        assert sr.get_stage_decision_carrier() == "d-1"
        sr.set_stage_decision_carrier(None)
        assert sr.get_stage_decision_carrier() is None


class TestRecordStageOutcome:
    def _fake_row(self) -> Any:
        return SimpleNamespace(
            success=None, quality_satisfied=None, actual_cost=None,
            actual_latency_ms=None, actual_model=None, actual_provider=None,
        )

    def test_updates_existing_row(self, monkeypatch) -> None:
        row = self._fake_row()
        db = FakeDb(first_rows={"StageRouterAudit": row})
        fake_session_patch(monkeypatch, db)
        sr.record_stage_outcome(
            "d-1", success=True, schema_error=False,
            content="ok", finish_reason="stop", actual_cost=0.01,
            actual_latency_ms=12.0, actual_model="m", actual_provider="p",
        )
        assert row.success is True
        assert row.quality_satisfied is True
        assert row.actual_cost == 0.01
        assert db.committed == 1

    def test_missing_row_returns(self, monkeypatch) -> None:
        db = FakeDb()  # no row
        fake_session_patch(monkeypatch, db)
        sr.record_stage_outcome("missing", success=True)
        assert db.committed == 0

    def test_quality_assessment_failure_keeps_success(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.llm.response_quality.assess_response_quality",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("quality broken")),
        )
        row = self._fake_row()
        db = FakeDb(first_rows={"StageRouterAudit": row})
        fake_session_patch(monkeypatch, db)
        sr.record_stage_outcome("d-1", success=True, content="x")
        assert row.success is True
        assert row.quality_satisfied is None

    def test_db_failure_never_raises(self, monkeypatch) -> None:
        def broken_db():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken_db)
        sr.record_stage_outcome("d-1", success=True)  # must not raise


class TestSampleSizeMath:
    def test_min_turns_default(self) -> None:
        n = sr.min_turns_per_arm()
        assert n == 201

    def test_min_turns_zero_for_bad_inputs(self) -> None:
        assert sr.min_turns_per_arm(effect_size=0) == 0
        assert sr.min_turns_per_arm(effect_size=-0.1) == 0
        assert sr.min_turns_per_arm(base_rate=0.0) == 0
        assert sr.min_turns_per_arm(base_rate=1.0) == 0

    def test_min_turns_pbar_out_of_range(self) -> None:
        assert sr.min_turns_per_arm(effect_size=0.05, base_rate=0.98) == 0

    def test_min_turns_custom_alpha_power(self) -> None:
        n = sr.min_turns_per_arm(alpha=0.01, power=0.9)
        assert n > sr.min_turns_per_arm()

    def test_min_turns_larger_effect_needs_less(self) -> None:
        assert sr.min_turns_per_arm(effect_size=0.2) < sr.min_turns_per_arm(effect_size=0.1)

    def test_min_detectable_gap_zero_turns(self) -> None:
        assert sr.min_detectable_gap(0) == 1.0
        assert sr.min_detectable_gap(-1) == 1.0

    def test_min_detectable_gap_decreases_with_volume(self) -> None:
        small = sr.min_detectable_gap(200)
        big = sr.min_detectable_gap(50)
        assert small < big

    def test_min_detectable_gap_pbar_break(self) -> None:
        gap = sr.min_detectable_gap(1, base_rate=0.99)
        assert 0.0 < gap < 1.0

    def test_z_score_bounds(self) -> None:
        assert sr._z_score(0.0) == -6.0
        assert sr._z_score(1.0) == 6.0

    def test_z_score_tails_and_middle(self) -> None:
        assert sr._z_score(0.00001) < 0
        assert sr._z_score(0.99999) > 0
        assert sr._z_score(0.5) == pytest.approx(0.0, abs=0.01)


class TestReadArmCounts:
    def test_counts_rows(self, monkeypatch) -> None:
        db = FakeDb(all_rows={
            "StageRouterAudit": [
                ("agent-1", "efficient", 40),
                ("agent-1", "capable", 35),
                ("agent-2", "bogus", 3),
                (None, "capable", 5),
            ],
        })
        fake_session_patch(monkeypatch, db)
        counts = sr._read_arm_counts()
        assert counts["agent-1"] == {"efficient": 40, "capable": 35}
        assert "agent-2" not in counts  # bogus group rows are skipped
        assert counts["unknown"]["capable"] == 5


class TestStageRouterStatus:
    def _patch_automation(self, monkeypatch, value: Any) -> None:
        monkeypatch.setattr(
            "core.llm.stage_router_automation.get_automation_status",
            lambda: value,
        )

    def test_off_phase(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "stage_router_enabled", lambda: False)
        self._patch_automation(monkeypatch, {})
        monkeypatch.setattr(sr, "_read_arm_counts", lambda: {})
        status = sr.stage_router_status()
        assert status["phase"] == "off"

    def test_enforced_phase(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: True)
        self._patch_automation(monkeypatch, {})
        monkeypatch.setattr(sr, "_read_arm_counts", lambda: {})
        status = sr.stage_router_status()
        assert status["phase"] == "enforced"

    def test_enforced_with_harness_note(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: True)
        monkeypatch.setattr(sr, "_stage_routing_split_raw", lambda: '{"efficient": 1.0}')
        self._patch_automation(monkeypatch, {})
        monkeypatch.setattr(sr, "_read_arm_counts", lambda: {})
        status = sr.stage_router_status()
        assert status["phase"] == "enforced"
        assert "A/B harness is active" in status["next_action"]

    def test_collecting_phase(self, monkeypatch) -> None:
        self._patch_automation(monkeypatch, {})
        monkeypatch.setattr(sr, "_read_arm_counts", lambda: {
            "agent-1": {"efficient": 5, "capable": 3},
        })
        status = sr.stage_router_status()
        assert status["phase"] == "collecting"
        assert status["sufficiency"]["agent-1"]["calibration_ready"] is False
        assert "Best workload" in status["next_action"]

    def test_collecting_no_workloads(self, monkeypatch) -> None:
        self._patch_automation(monkeypatch, {})
        monkeypatch.setattr(sr, "_read_arm_counts", lambda: {})
        status = sr.stage_router_status()
        assert status["phase"] == "collecting"

    def test_ready_phase(self, monkeypatch) -> None:
        self._patch_automation(monkeypatch, {})
        monkeypatch.setattr(sr, "_read_arm_counts", lambda: {
            "agent-1": {"efficient": 40, "capable": 35},
            "agent-2": {"efficient": 5, "capable": 3},
        })
        status = sr.stage_router_status()
        assert status["phase"] == "ready"
        assert status["ready_workloads"] == ["agent-1"]

    def test_automation_status_failure_tolerated(self, monkeypatch) -> None:
        def boom():
            raise RuntimeError("auto down")

        monkeypatch.setattr(
            "core.llm.stage_router_automation.get_automation_status", boom
        )
        monkeypatch.setattr(sr, "_read_arm_counts", lambda: {})
        status = sr.stage_router_status()
        assert status["automation"] == {}

    def test_db_read_failure_error_phase(self, monkeypatch) -> None:
        self._patch_automation(monkeypatch, {})

        def boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(sr, "_read_arm_counts", boom)
        status = sr.stage_router_status()
        assert status["phase"] == "error"
        assert "check the audit table" in status["next_action"]


class TestGetStageRouter:
    def test_singleton_and_picker_capable(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "_stage_router", None)
        monkeypatch.setattr(sr, "stage_routing_picker", lambda: "capable_first")
        monkeypatch.setattr(
            "core.llm.routing.traffic_split.get_traffic_split", lambda: None
        )
        monkeypatch.setattr(
            "core.llm.stage_router_automation.ensure_automation_task",
            lambda: None,
        )
        router = sr.get_stage_router()
        assert router.picker == sr.StagePicker.CAPABLE_FIRST
        assert sr.get_stage_router() is router
        monkeypatch.setattr(sr, "_stage_router", None)

    def test_invalid_picker_warns_efficient(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "_stage_router", None)
        monkeypatch.setattr(sr, "stage_routing_picker", lambda: "bogus")
        monkeypatch.setattr(
            "core.llm.routing.traffic_split.get_traffic_split", lambda: None
        )
        monkeypatch.setattr(
            "core.llm.stage_router_automation.ensure_automation_task",
            lambda: None,
        )
        router = sr.get_stage_router()
        assert router.picker == sr.StagePicker.EFFICIENT_FIRST
        monkeypatch.setattr(sr, "_stage_router", None)

    def test_traffic_split_attached(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "_stage_router", None)
        monkeypatch.setattr(sr, "stage_routing_picker", lambda: "efficient_first")
        split = sr.WeightedRandomSplit({"efficient": 1.0}, seed=1)
        monkeypatch.setattr(
            "core.llm.routing.traffic_split.get_traffic_split", lambda: split
        )
        monkeypatch.setattr(
            "core.llm.stage_router_automation.ensure_automation_task",
            lambda: None,
        )
        router = sr.get_stage_router()
        assert router.split is split
        monkeypatch.setattr(sr, "_stage_router", None)

    def test_traffic_split_failure_tolerated(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "_stage_router", None)

        def boom():
            raise RuntimeError("split down")

        monkeypatch.setattr("core.llm.routing.traffic_split.get_traffic_split", boom)
        monkeypatch.setattr(
            "core.llm.stage_router_automation.ensure_automation_task",
            lambda: None,
        )
        router = sr.get_stage_router()
        assert router.split is None
        monkeypatch.setattr(sr, "_stage_router", None)

    def test_ensure_automation_failure_tolerated(self, monkeypatch) -> None:
        monkeypatch.setattr(sr, "_stage_router", None)

        def boom():
            raise RuntimeError("loop down")

        monkeypatch.setattr(
            "core.llm.routing.traffic_split.get_traffic_split", lambda: None
        )
        monkeypatch.setattr(
            "core.llm.stage_router_automation.ensure_automation_task", boom
        )
        router = sr.get_stage_router()
        assert router is not None
        monkeypatch.setattr(sr, "_stage_router", None)


# ===========================================================================
# stage_router_automation
# ===========================================================================


class TestAutomationConfig:
    def test_invalid_env_mode_falls_back_to_approve(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_STAGE_ROUTER_AUTO_ENFORCE", "bogus")
        reloaded = importlib.reload(auto)
        assert reloaded._MODE == "approve"
        importlib.reload(auto)  # restore module state from real env

    def test_automation_mode_and_interval(self) -> None:
        assert auto.automation_mode() == auto._MODE
        assert auto.automation_interval_min() == auto._INTERVAL_MIN

    def test_set_config_valid(self) -> None:
        result = auto.set_automation_config(mode="notify", interval_min=5)
        assert result == {"mode": "notify", "interval_min": 5.0}
        auto.set_automation_config(mode="approve", interval_min=60)  # restore

    def test_set_config_invalid_mode_ignored(self) -> None:
        before = auto._MODE
        result = auto.set_automation_config(mode="bogus")
        assert result["mode"] == before

    def test_set_config_invalid_interval_ignored(self) -> None:
        before = auto._INTERVAL_MIN
        result = auto.set_automation_config(interval_min=-3)
        assert result["interval_min"] == before


class TestWorkloadStats:
    def test_real_body_builds_counts(self, monkeypatch) -> None:
        db = FakeDb(all_rows={
            "StageRouterAudit": [
                ("agent-1", "efficient", 40, 36, 0.001),
                ("agent-1", "capable", 35, 31, 0.004),
                ("agent-2", "bogus", 5, 5, 0.1),
                (None, "capable", 5, 5, 0.1),
            ],
        })
        stats = auto._workload_stats(db)
        assert stats["agent-1"]["efficient"]["n"] == 40
        assert stats["agent-1"]["efficient"]["success_rate"] == pytest.approx(0.9)
        assert stats["agent-1"]["capable"]["avg_cost"] == pytest.approx(0.004)
        assert "agent-2" not in stats  # bogus group rows are skipped
        assert None not in stats

    def test_zero_n_success_rate_zero(self, monkeypatch) -> None:
        db = FakeDb(all_rows={
            "StageRouterAudit": [("agent-1", "efficient", 0, 0, None)],
        })
        stats = auto._workload_stats(db)
        assert stats["agent-1"]["efficient"]["success_rate"] == 0.0
        assert stats["agent-1"]["efficient"]["avg_cost"] == 0.0


class TestVerdict:
    def test_insufficient_arms_keeps_shadow(self) -> None:
        assert auto._verdict(workload(arm(5, 0.9), arm(5, 0.95))) == "keep-shadow"
        assert auto._verdict(workload(arm(40, 0.9), arm(5, 0.95))) == "keep-shadow"

    def test_certify_when_gain_clears_gap(self) -> None:
        assert auto._verdict(workload(arm(40, 0.80), arm(35, 0.88))) == "certify"

    def test_certify_blocked_by_cost_ratio(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MAX_COST_RATIO", 2.0)
        assert (
            auto._verdict(workload(arm(40, 0.80, 0.001), arm(35, 0.88, 0.05)))
            == "keep-shadow"
        )

    def test_revoke_on_regression(self) -> None:
        assert auto._verdict(workload(arm(40, 0.90), arm(35, 0.80))) == "revoke"

    def test_revoke_floor_not_met(self) -> None:
        assert auto._verdict(workload(arm(10, 0.90), arm(10, 0.80))) == "keep-shadow"

    def test_keep_shadow_neutral(self) -> None:
        assert auto._verdict(workload(arm(40, 0.85), arm(35, 0.84))) == "keep-shadow"


class TestApplyEnforce:
    def test_certified_markers(self) -> None:
        agent = FakeAgent("a-1")
        auto._apply_enforce(agent, True, certified=True)
        block = agent.configuration["stage_routing"]
        assert block["enforce"] is True
        assert block["auto_certified"] is True
        assert block["certified_at"]
        assert "auto_revoked" not in block

    def test_certified_clears_revoked_markers(self) -> None:
        agent = FakeAgent("a-1", {"stage_routing": {"enforce": False, "auto_revoked": True, "revoked_at": "x"}})
        auto._apply_enforce(agent, True, certified=True)
        block = agent.configuration["stage_routing"]
        assert "auto_revoked" not in block
        assert "revoked_at" not in block

    def test_revoked_markers(self) -> None:
        agent = FakeAgent("a-1")
        auto._apply_enforce(agent, False, revoked=True)
        block = agent.configuration["stage_routing"]
        assert block["enforce"] is False
        assert block["auto_revoked"] is True
        assert block["revoked_at"]

    def test_plain_enforce_preserves_other_config(self) -> None:
        agent = FakeAgent("a-1", {"stage_routing": {"confidence_threshold": 0.4}})
        auto._apply_enforce(agent, True)
        block = agent.configuration["stage_routing"]
        assert block["confidence_threshold"] == 0.4
        assert block["enforce"] is True


class TestAdminRecipient:
    def test_admin_found(self, monkeypatch) -> None:
        db = FakeDb(first_rows={"User": SimpleNamespace(id="admin-1")})
        monkeypatch.setattr("core.database.SessionLocal", lambda: db)
        assert auto._admin_recipient() == "admin-1"
        assert db.closed == 1

    def test_no_admin_returns_none(self, monkeypatch) -> None:
        db = FakeDb()
        monkeypatch.setattr("core.database.SessionLocal", lambda: db)
        assert auto._admin_recipient() is None

    def test_db_failure_returns_none(self, monkeypatch) -> None:
        def broken():
            raise RuntimeError("down")

        monkeypatch.setattr("core.database.SessionLocal", broken)
        assert auto._admin_recipient() is None


class TestNotify:
    def test_no_recipient_logs_and_returns(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_admin_recipient", lambda: None)
        asyncio.run(auto._notify("type", "title", "msg"))

    def test_send_notification_with_action_url(self, monkeypatch) -> None:
        service = MagicMock()
        service.send_notification = AsyncMock()
        monkeypatch.setattr(
            "core.notification_service.NotificationService",
            lambda: service,
        )
        monkeypatch.setattr(auto, "_admin_recipient", lambda: "admin-1")
        asyncio.run(auto._notify("type", "title", "msg", action_url="/api/x"))
        assert service.send_notification.await_count == 1
        kwargs = service.send_notification.await_args.kwargs
        assert kwargs["user_id"] == "admin-1"
        assert kwargs["data"]["action_url"] == "/api/x"

    def test_send_notification_without_action_url(self, monkeypatch) -> None:
        service = MagicMock()
        service.send_notification = AsyncMock()
        monkeypatch.setattr(
            "core.notification_service.NotificationService",
            lambda: service,
        )
        monkeypatch.setattr(auto, "_admin_recipient", lambda: "admin-1")
        asyncio.run(auto._notify("type", "title", "msg"))
        data = service.send_notification.await_args.kwargs["data"]
        assert "action_url" not in data

    def test_notification_failure_never_raises(self, monkeypatch) -> None:
        def broken():
            raise RuntimeError("svc down")

        monkeypatch.setattr(
            "core.notification_service.NotificationService", broken
        )
        monkeypatch.setattr(auto, "_admin_recipient", lambda: "admin-1")
        asyncio.run(auto._notify("type", "title", "msg"))


class TestSpawnNotification:
    def test_running_loop_creates_task(self, monkeypatch) -> None:
        async def scenario():
            auto._spawn_notification("t", "title", "msg")
            await asyncio.sleep(0)

        monkeypatch.setattr(auto, "_notify", AsyncMock())
        asyncio.run(scenario())

    def test_sync_context_runs_inline(self, monkeypatch) -> None:
        notified = []

        async def fake_notify(*args, **kwargs):
            notified.append(args)

        monkeypatch.setattr(auto, "_notify", fake_notify)
        auto._spawn_notification("t", "title", "msg")
        assert notified

    def test_get_event_loop_failure_falls_back_inline(self, monkeypatch) -> None:
        notified = []

        async def fake_notify(*args, **kwargs):
            notified.append(args)

        monkeypatch.setattr(auto, "_notify", fake_notify)
        monkeypatch.setattr(asyncio, "get_event_loop", lambda: (_ for _ in ()).throw(RuntimeError("no loop")))
        auto._spawn_notification("t", "title", "msg")
        assert notified


class TestRecordAndQueryHelpers:
    def test_record_action_persists(self) -> None:
        db = FakeDb()
        auto._record_action(db, "agent-1", "certify", "applied", {"n": 1})
        assert len(db.added) == 1
        assert db.added[0].agent_id == "agent-1"
        assert db.added[0].mode == auto._MODE

    def test_record_action_failure_never_raises(self, monkeypatch) -> None:
        db = FakeDb()

        class Boom:
            __name__ = "StageRouterAutomationAction"

            def __init__(self, **kwargs):
                raise RuntimeError("model broken")

        monkeypatch.setattr("core.models.StageRouterAutomationAction", Boom)
        auto._record_action(db, "agent-1", "certify", "applied", {})
        assert db.added == []

    def test_agent_query(self) -> None:
        agent = FakeAgent("a-1")
        db = FakeDb(first_rows={"AgentRegistry": agent})
        assert auto._agent_query(db, "a-1") is agent

    def test_latest_action(self) -> None:
        action = FakeAction("a-1")
        db = FakeDb(first_rows={"StageRouterAutomationAction": action})
        assert auto._latest_action(db, "a-1") is action

    def test_latest_action_failure_returns_none(self, monkeypatch) -> None:
        db = FakeDb()

        def boom():
            raise RuntimeError("x")

        db.query = boom
        assert auto._latest_action(db, "a-1") is None

    def test_stats_signature_stable(self) -> None:
        a = auto._stats_signature({"b": 1, "a": [1, 2]})
        b = auto._stats_signature({"a": [1, 2], "b": 1})
        assert a == b
        assert len(a) == 16

    def test_notify_cooldown(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_last_notified", {})
        assert auto._notify_cooldown_active("agent-1") is False
        auto._mark_notified("agent-1")
        assert auto._notify_cooldown_active("agent-1") is True

    def test_notify_cooldown_expired(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_NOTIFY_COOLDOWN_HOURS", 0.0)
        monkeypatch.setattr(auto, "_last_notified", {})
        auto._mark_notified("agent-1")
        assert auto._notify_cooldown_active("agent-1") is False


class TestCertifyWorkloads:
    def _db(self, agents: Dict[str, FakeAgent], actions: Optional[List[FakeAction]] = None) -> FakeDb:
        db = FakeDb(
            first_rows={
                "AgentRegistry": None,
                "StageRouterAutomationAction": None,
            },
            all_rows={"StageRouterAutomationAction": actions or []},
        )
        db.agents = agents
        db.actions = actions or []
        return db

    def test_off_mode_noop(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "off")
        db = self._db({"agent-1": FakeAgent("agent-1")})
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result == {"certified": [], "revoked": [], "queued": [], "notified": [], "kept": []}

    def test_approve_queues(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1")
        db = self._db({"agent-1": agent}, actions=[])
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["queued"] == ["agent-1"]
        assert agent.configuration == {}

    def test_approve_dedupe_while_waiting(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1")
        pending = FakeAction("agent-1", state="approval")
        db = self._db({"agent-1": agent}, actions=[pending])
        db.first_rows["AgentRegistry"] = agent
        db.first_rows["StageRouterAutomationAction"] = pending
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["queued"] == []
        assert result["kept"] == ["agent-1"]

    def test_approve_rejected_unchanged_respected(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1")
        rejected = FakeAction("agent-1", state="rejected")
        stats = workload(arm(40, 0.8), arm(35, 0.88))
        rejected.stats_json = stats
        db = self._db({"agent-1": agent}, actions=[rejected])
        db.first_rows["AgentRegistry"] = agent
        db.first_rows["StageRouterAutomationAction"] = rejected
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {"agent-1": stats})
        result = auto.certify_workloads(db)
        assert result["queued"] == []
        assert result["kept"] == ["agent-1"]

        changed = workload(arm(120, 0.8), arm(110, 0.92))
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {"agent-1": changed})
        result = auto.certify_workloads(db)
        assert result["queued"] == ["agent-1"]

    def test_auto_applies(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1")
        db = self._db({"agent-1": agent})
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["certified"] == ["agent-1"]
        assert agent.configuration["stage_routing"]["enforce"] is True

    def test_auto_manual_opt_out_never_overwritten(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1", {"stage_routing": {"enforce": False}})
        db = self._db({"agent-1": agent})
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["kept"] == ["agent-1"]
        assert result["certified"] == []

    def test_auto_already_applied_kept(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1", {"stage_routing": {"enforce": True}})
        applied = FakeAction("agent-1", state="applied")
        db = self._db({"agent-1": agent}, actions=[applied])
        db.first_rows["AgentRegistry"] = agent
        db.first_rows["StageRouterAutomationAction"] = applied
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["kept"] == ["agent-1"]
        assert result["certified"] == []

    def test_notify_mode(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "notify")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        monkeypatch.setattr(auto, "_last_notified", {})
        agent = FakeAgent("agent-1")
        db = self._db({"agent-1": agent})
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["notified"] == ["agent-1"]

    def test_notify_cooldown_active(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "notify")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        monkeypatch.setattr(auto, "_last_notified", {"agent-1": time.monotonic()})
        agent = FakeAgent("agent-1")
        db = self._db({"agent-1": agent})
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["kept"] == ["agent-1"]
        assert result["notified"] == []

    def test_revoke_applies_in_approve_mode(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1", {"stage_routing": {"enforce": True}})
        db = self._db({"agent-1": agent})
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.9), arm(35, 0.78)),
        })
        result = auto.certify_workloads(db)
        assert result["revoked"] == ["agent-1"]
        assert agent.configuration["stage_routing"]["enforce"] is False

    def test_revoke_already_revoked_kept(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1", {"stage_routing": {"enforce": False}})
        revoked = FakeAction("agent-1", verdict="revoke", state="revoked")
        db = self._db({"agent-1": agent}, actions=[revoked])
        db.first_rows["AgentRegistry"] = agent
        db.first_rows["StageRouterAutomationAction"] = revoked
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.9), arm(35, 0.78)),
        })
        result = auto.certify_workloads(db)
        assert result["revoked"] == []
        assert result["kept"] == ["agent-1"]

    def test_revoke_shadowed_audits_once(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1")  # not enforced → nothing to roll back
        db = self._db({"agent-1": agent})
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.9), arm(35, 0.78)),
        })
        result = auto.certify_workloads(db)
        assert result["kept"] == ["agent-1"]
        assert len([a for a in db.added if a.state == "revoked"]) == 1

    def test_keep_shadow_verdict(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        agent = FakeAgent("agent-1")
        db = self._db({"agent-1": agent})
        db.first_rows["AgentRegistry"] = agent
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "agent-1": workload(arm(40, 0.85), arm(35, 0.84)),
        })
        result = auto.certify_workloads(db)
        assert result["kept"] == ["agent-1"]

    def test_missing_agent_kept(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        db = self._db({})
        monkeypatch.setattr(auto, "_workload_stats", lambda d: {
            "ghost": workload(arm(40, 0.8), arm(35, 0.88)),
        })
        result = auto.certify_workloads(db)
        assert result["kept"] == ["ghost"]


class TestRunAutoCertification:
    def test_off_mode(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "off")
        assert auto.run_auto_certification() == {"enabled": False, "mode": "off"}

    def test_success_updates_last_run(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "certify_workloads", lambda db: {
            "certified": [], "revoked": [], "queued": ["agent-1"], "notified": [], "kept": [],
        })
        db = FakeDb()
        fake_session_patch(monkeypatch, db)
        result = auto.run_auto_certification()
        assert result["enabled"] is True
        assert result["queued"] == ["agent-1"]
        assert auto._last_run["mode"] == "approve"
        assert db.committed == 1

    def test_failure_returns_error(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")

        def broken():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken)
        result = auto.run_auto_certification()
        assert result["error"] == "pass failed"
        assert result["enabled"] is True


class TestApprovalManagement:
    def test_pending_approvals_lists(self) -> None:
        action = FakeAction("agent-1", state="approval")
        action.created_at = None
        db = FakeDb(all_rows={"StageRouterAutomationAction": [action]})
        pending = auto.pending_approvals(db)
        assert pending[0]["agent_id"] == "agent-1"
        assert pending[0]["created_at"] is None

    def test_pending_approvals_with_created_at(self) -> None:
        from datetime import datetime, timezone

        action = FakeAction("agent-1", state="approval")
        action.created_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        db = FakeDb(all_rows={"StageRouterAutomationAction": [action]})
        pending = auto.pending_approvals(db)
        assert pending[0]["created_at"] == "2026-08-01T00:00:00+00:00"

    def test_pending_approvals_failure_returns_empty(self, monkeypatch) -> None:
        db = FakeDb()

        def boom():
            raise RuntimeError("x")

        db.query = boom
        assert auto.pending_approvals(db) == []

    def test_apply_pending_approve(self) -> None:
        agent = FakeAgent("agent-1")
        action = FakeAction("agent-1", state="approval")
        db = FakeDb(
            first_rows={"AgentRegistry": agent, "StageRouterAutomationAction": action},
        )
        result = auto.apply_pending_decision(db, "agent-1", approve=True)
        assert result["applied"] is True
        assert agent.configuration["stage_routing"]["enforce"] is True
        assert action.state == "applied"
        assert action.decided_at is not None

    def test_apply_pending_reject(self) -> None:
        agent = FakeAgent("agent-1")
        action = FakeAction("agent-1", state="approval")
        db = FakeDb(
            first_rows={"AgentRegistry": agent, "StageRouterAutomationAction": action},
        )
        result = auto.apply_pending_decision(db, "agent-1", approve=False)
        assert result["state"] == "rejected"
        assert result["applied"] is False
        assert agent.configuration == {}

    def test_apply_pending_none_pending(self) -> None:
        db = FakeDb()
        result = auto.apply_pending_decision(db, "agent-1", approve=True)
        assert result["applied"] is False
        assert "no pending" in result["reason"]

    def test_apply_pending_agent_missing(self) -> None:
        action = FakeAction("agent-1", state="approval")
        db = FakeDb(first_rows={"StageRouterAutomationAction": action})
        result = auto.apply_pending_decision(db, "agent-1", approve=True)
        assert result["applied"] is False
        assert result["reason"] == "agent not found"

    def test_get_automation_status(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_INTERVAL_MIN", 60.0)
        monkeypatch.setattr(auto, "pending_approvals", lambda db: [{"agent_id": "a-1"}])
        db = FakeDb()
        fake_session_patch(monkeypatch, db)
        status = auto.get_automation_status()
        assert status["enabled"] is True
        assert status["mode"] == "approve"
        assert status["pending_approvals"][0]["agent_id"] == "a-1"

    def test_get_automation_status_db_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "off")

        def broken():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken)
        status = auto.get_automation_status()
        assert status["pending_approvals"] == []
        assert status["enabled"] is False


class TestAutomationLoop:
    def test_loop_runs_and_cancels(self, monkeypatch) -> None:
        calls = {"sleep": 0, "run": 0}

        async def fake_sleep(_):
            calls["sleep"] += 1
            if calls["sleep"] >= 2:
                raise asyncio.CancelledError()

        def fake_run():
            calls["run"] += 1
            return {"enabled": True}

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(auto, "run_auto_certification", fake_run)
        asyncio.run(auto.stage_router_automation_loop())
        assert calls["run"] >= 1

    def test_loop_iteration_failure_logged(self, monkeypatch) -> None:
        calls = {"sleep": 0}

        async def fake_sleep(_):
            calls["sleep"] += 1
            if calls["sleep"] >= 2:
                raise asyncio.CancelledError()
            raise RuntimeError("iteration boom")

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(auto, "run_auto_certification", lambda: {})
        asyncio.run(auto.stage_router_automation_loop())  # must not raise

    def test_ensure_task_already_started(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_automation_task", object())
        auto.ensure_automation_task()  # no-op

    def test_ensure_task_off_mode(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_automation_task", None)
        monkeypatch.setattr(auto, "_MODE", "off")
        auto.ensure_automation_task()

    def test_ensure_task_starts_in_running_loop(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_automation_task", None)
        monkeypatch.setattr(auto, "_MODE", "approve")

        async def scenario():
            auto.ensure_automation_task()
            assert auto._automation_task is not None
            auto._automation_task.cancel()
            try:
                await auto._automation_task
            except asyncio.CancelledError:
                pass
            monkeypatch.setattr(auto, "_automation_task", None)

        asyncio.run(scenario())

    def test_ensure_task_loop_failure_logged(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_automation_task", None)
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(asyncio, "get_event_loop", lambda: (_ for _ in ()).throw(RuntimeError("no loop")))
        auto.ensure_automation_task()
        monkeypatch.setattr(auto, "_automation_task", None)


# ===========================================================================
# Voter: _majority_vote empty-input guard is deliberately NOT tested (see report)
# ===========================================================================
