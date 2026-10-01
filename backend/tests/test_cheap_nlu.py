# -*- coding: utf-8 -*-
"""Cheap-NLU micro-classifier — the tiebreaker pattern applied to NLU.

Pinned: switches (TESTING / ATOM_CHEAP_NLU_LLM), cache amortization,
never-raises (timeout/error → None), circuit breaker, strict yes/no
parsing, and the two task prompts staying domain-generic.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

import core.llm.cheap_nlu as cheap


class _FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    async def generate_completion(self, **kwargs):
        self.calls += 1
        reply = self.replies.pop(0) if self.replies else "NO"
        if isinstance(reply, Exception):
            raise reply
        return {"text": reply}


def _enable(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    cheap.reset_for_tests()


class TestSwitches:
    async def test_disabled_returns_none_without_llm(self):
        # TESTING=1 (set by every suite) must block all LLM calls even
        # when the module was imported before it was set.
        cheap.reset_for_tests()
        assert cheap.switch_enabled() is False
        llm = _FakeLLM([])
        assert await cheap.binary("k", "q?", "s", llm) is None
        assert llm.calls == 0

    async def test_kill_switch_env(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setenv("ATOM_CHEAP_NLU_LLM", "false")
        cheap.reset_for_tests()
        llm = _FakeLLM([])
        assert await cheap.binary("k", "q?", "s", llm) is None
        assert llm.calls == 0

    async def test_enabled_passes_strict_prompt(self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM(["YES"])
        assert await cheap.binary("k", "the question", "subj", llm) is True
        assert llm.calls == 1


class TestParsing:
    @pytest.mark.parametrize("reply,expected", [
        ("YES", True), ("yes.", True), ("YES — it names a source", True),
        ("NO", False), ("no.", False), ("No, it is a row attribute", False),
        ("MAYBE", None), ("", None), (
            "The phrase refers to a message sender.", None),
    ])
    async def test_yes_no_parsing(self, monkeypatch, reply, expected):
        _enable(monkeypatch)
        llm = _FakeLLM([reply])
        assert await cheap.binary("k", "q", "s", llm) is expected


class TestCacheAndBreaker:
    async def test_repeat_subject_is_cached(self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM(["YES"])
        first = await cheap.binary("k", "q", "s", llm)
        second = await cheap.binary("k", "q", "s", llm)
        assert (first, second) == (True, True)
        assert llm.calls == 1, "second call must amortize from cache"

    async def test_error_then_none_never_raises(self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM([RuntimeError("provider down"), "UNCLEAR"])
        assert await cheap.binary("k", "q", "s", llm) is None
        assert await cheap.binary("k", "q2", "s", llm) is None

    async def test_breaker_opens_after_consecutive_failures(
            self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM([RuntimeError("x")] * 10)
        for i in range(3):
            assert await cheap.binary("k", f"q{i}", "s", llm) is None
        # breaker open: no further LLM calls at all
        assert await cheap.binary("k", "q-after", "s", llm) is None
        assert llm.calls == 3


class TestTaskPrompts:
    async def test_possessive_prompt_is_domain_generic(self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM(["YES"])
        out = await cheap.is_source_reference("Meera", "Notion page", llm)
        assert out is True

    async def test_file_reference_prompt(self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM(["NO"])
        out = await cheap.refers_to_resolved_file(
            "find this in the thing", "prices.xlsx", llm)
        assert out is False


class TestTriggerMetrics:
    """Expansion-trigger observability (RESEARCH_ollaya_jev.md): counters
    + one grep-able JSON log line per event, with NO behavior change —
    every verdict here must match the pre-metric contract."""

    async def test_ok_call_counts_once_with_latency(self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM(["YES"])
        assert await cheap.binary("kind_a", "q", "s", llm) is True
        snap = cheap.metrics_snapshot()
        assert snap["counters"]["llm_call"] == 1
        assert snap["counters"].get("cache_hit", 0) == 0
        assert snap["by_kind"]["kind_a"]["llm_call"] == 1
        assert snap["llm_latency"]["n"] == 1
        assert snap["llm_latency"]["max_ms"] >= 0.0

    async def test_cache_hit_amortizes_without_llm(self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM(["YES"])
        await cheap.binary("k", "q", "s", llm)
        assert await cheap.binary("k", "q", "s", llm) is True
        assert llm.calls == 1
        snap = cheap.metrics_snapshot()
        assert snap["counters"]["cache_hit"] == 1
        assert snap["counters"]["llm_call"] == 1

    async def test_disabled_demand_is_counted(self, monkeypatch):
        # TESTING=1 stays set: every attempt must be visible as
        # suppressed demand, not silently dropped.
        cheap.reset_for_tests()
        llm = _FakeLLM([])
        assert await cheap.binary("k", "q", "s", llm) is None
        assert llm.calls == 0
        snap = cheap.metrics_snapshot()
        assert snap["counters"]["skipped_disabled"] == 1
        assert "llm_call" not in snap["counters"]

    async def test_breaker_open_and_suppressed_demand_counted(
            self, monkeypatch):
        _enable(monkeypatch)
        llm = _FakeLLM([RuntimeError("provider down")] * 10)
        for i in range(3):
            assert await cheap.binary("k", f"q{i}", "s", llm) is None
        assert await cheap.binary("k", "q-after", "s", llm) is None
        snap = cheap.metrics_snapshot()
        assert snap["counters"]["breaker_open"] == 1
        assert snap["counters"]["skipped_breaker_open"] == 1
        assert snap["counters"]["llm_call"] == 3
        # breaker_open is a global event (no question kind attached);
        # per-kind counters carry the kind-tagged events.
        assert snap["by_kind"]["k"]["llm_call"] == 3
        assert snap["by_kind"]["k"]["skipped_breaker_open"] == 1

    async def test_timeout_and_unparseable_outcomes(self, monkeypatch,
                                                    caplog):
        import logging as _logging

        _enable(monkeypatch)
        monkeypatch.setattr(cheap, "_CHEAP_NLU_TIMEOUT_S", 0.01)

        class _SlowLLM:
            async def generate_completion(self, **kwargs):
                await asyncio.sleep(0.05)
                return {"text": "YES"}

        with caplog.at_level(_logging.INFO, logger="core.llm.cheap_nlu"):
            assert await cheap.binary(
                "k", "slow", "s", _SlowLLM()) is None
            assert await cheap.binary("k", "muddy", "s",
                                      _FakeLLM(["MAYBE"])) is None
        snap = cheap.metrics_snapshot()
        assert snap["counters"]["llm_call"] == 2
        outcomes = {e["outcome"] for e in _metric_events(caplog.records)}
        assert {"timeout", "unparseable"} <= outcomes

    async def test_metric_lines_are_json_and_prefixed(self, monkeypatch,
                                                      caplog):
        import json as _json
        import logging as _logging

        _enable(monkeypatch)
        llm = _FakeLLM(["YES"])
        with caplog.at_level(_logging.INFO, logger="core.llm.cheap_nlu"):
            await cheap.binary("kind_x", "q", "s", llm)
        lines = [r.getMessage() for r in caplog.records
                 if r.getMessage().startswith(cheap._METRIC_PREFIX)]
        assert lines, "expected at least one cheap-nlu-metric log line"
        payload = _json.loads(lines[0].split(" ", 1)[1])
        assert payload["event"] == "llm_call"
        assert payload["kind"] == "kind_x"
        assert payload["outcome"] == "ok"
        assert "latency_ms" in payload


def _metric_events(records):
    out = []
    for r in records:
        msg = r.getMessage()
        if msg.startswith(cheap._METRIC_PREFIX):
            out.append(json.loads(msg.split(" ", 1)[1]))
    return out
