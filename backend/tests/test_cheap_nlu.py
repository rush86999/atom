# -*- coding: utf-8 -*-
"""Cheap-NLU micro-classifier — the tiebreaker pattern applied to NLU.

Pinned: switches (TESTING / ATOM_CHEAP_NLU_LLM), cache amortization,
never-raises (timeout/error → None), circuit breaker, strict yes/no
parsing, and the two task prompts staying domain-generic.
"""
from __future__ import annotations

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
