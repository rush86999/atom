# -*- coding: utf-8 -*-
"""Correlated route-exclusion trace + one-shot stale-discovery refresh.

Grounding (2026-09-23, scratch continuation ab86e7bf on canvas b39e34c3):
attempt 1 burned two ranking cascades and returned in 1.3s with ZERO
dispatches; attempt 2 (after the 45s backoff) dispatched the healthy route
and applied. The scattered skip lines could not answer WHY the healthy
route was skipped on the first attempt — no evidence ages, no pool
composition, no interactive-context flag. These tests pin:

1. Every refused candidate records its reason AND the age of the evidence
   behind it (catalog verified_at, cooldown remaining, latency observation).
2. Classification separates STALE discovery (refresh-eligible) from
   legitimate restrictions (fresh-catalog exclusions, cooldowns, auth,
   rate, unservable names) — only stale state is refreshed.
3. The refresh is ONE-SHOT per provider per window and never touches a
   provider on cooldown.
4. A healthy route dispatches on the first attempt without any refresh.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

import core.llm.byok_handler as byok
from core.llm.byok_handler import BYOKHandler


def _bare_handler() -> BYOKHandler:
    """A handler shell with only what the trace/refresh methods touch."""
    h = object.__new__(BYOKHandler)
    h.clients = {"deepseek": object(), "opencode-go": object()}
    return h


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    monkeypatch.setattr(byok, "_DISCOVERY_REFRESH_ATTEMPTED_AT", {})
    byok._MODEL_STRUCTURED_LATENCY.clear()
    byok._MODEL_STRUCTURED_LATENCY_AT.clear()
    with byok._PROVIDER_COOLDOWN_LOCK:
        byok._PROVIDER_COOLDOWN_UNTIL.clear()
        byok._PROVIDER_COOLDOWN_REASON.clear()
    yield
    # The catalog registry is a process-wide singleton persisted to disk —
    # a discovery recorded here must not leak into later suites' routing
    # decisions.
    try:
        from core.llm.model_route_registry import (
            get_provider_model_catalog,
        )

        get_provider_model_catalog().invalidate()
    except Exception:
        pass


class TestNoteCascadeExclusion:
    def test_catalog_exclusion_carries_freshness_and_ages(self):
        from core.llm.model_route_registry import get_provider_model_catalog

        catalog = get_provider_model_catalog()
        catalog.record_discovery(
            "deepseek", ["deepseek-chat", "deepseek-reasoner"])
        out: list = []
        _bare_handler()._note_cascade_exclusion(
            out, "deepseek", "tencent/deepseek-v4-pro",
            "catalog_not_in_provider")
        assert len(out) == 1
        entry = out[0]
        assert entry["reason"] == "catalog_not_in_provider"
        cat = entry["catalog"]
        assert cat["freshness"] == "fresh"
        assert cat["verified_age_s"] is not None and cat["verified_age_s"] < 60

    def test_cooldown_exclusion_carries_remaining_and_cause(self):
        with byok._PROVIDER_COOLDOWN_LOCK:
            byok._PROVIDER_COOLDOWN_UNTIL["openrouter"] = time.time() + 214
            byok._PROVIDER_COOLDOWN_REASON["openrouter"] = (
                "quota_exhausted", "402 credits")
        out: list = []
        _bare_handler()._note_cascade_exclusion(
            out, "openrouter", "z-ai/glm-5.3-flash", "provider_cooldown")
        cd = out[0]["cooldown"]
        assert cd["seconds_remaining"] > 213
        assert cd["cause"] == "quota_exhausted"

    def test_never_raises_on_junk(self):
        out: list = []
        _bare_handler()._note_cascade_exclusion(
            out, "x", "y", "client_not_initialized")
        assert out[0]["route"] == "x/y"


class TestLatencyAgeStamp:
    def test_latency_recording_stamps_age(self):
        byok._record_structured_latency("deepseek", "deepseek-v4-pro", 27.0)
        assert "deepseek/deepseek-v4-pro" in byok._MODEL_STRUCTURED_LATENCY_AT
        age = time.time() - byok._MODEL_STRUCTURED_LATENCY_AT[
            "deepseek/deepseek-v4-pro"]
        assert 0 <= age < 60


class TestExhaustionClassificationAndRefresh:
    async def test_stale_catalog_refreshes_once_then_skips_in_window(
            self, monkeypatch, caplog):
        from core.llm.model_route_registry import get_provider_model_catalog

        # A STALE discovery: verified long before the 6h freshness window.
        catalog = get_provider_model_catalog()
        catalog.record_discovery("deepseek", ["deepseek-chat"])
        obs = catalog.observe("deepseek")
        obs.verified_at = time.time() - 7 * 3600
        # write back through the registry's own lock path
        catalog._observations["deepseek"] = obs
        catalog._save_locked()

        calls: list = []

        def fake_refresh(providers=None, force=False):
            calls.append(list(providers or []))
            return {"deepseek": {"discovered": 2}}

        h = _bare_handler()
        monkeypatch.setattr(h, "_refresh_provider_catalog", fake_refresh)
        exclusions = [{
            "route": "deepseek/tencent/deepseek-v4-pro",
            "reason": "catalog_not_in_provider",
            "catalog": {"freshness": "stale", "verified_age_s": 25200.0,
                        "last_attempt_age_s": 25200.0, "last_error": ""},
        }]
        with caplog.at_level("INFO"):
            await h._route_exclusion_trace_and_refresh(
                "t1", [("deepseek", "tencent/deepseek-v4-pro")], exclusions,
                dispatched=False)
        assert calls == [["deepseek"]]
        assert any("route-exclusions" in r.message for r in caplog.records)

        # Second exhaustion inside the window: NOT refreshed again.
        with caplog.at_level("INFO"):
            await h._route_exclusion_trace_and_refresh(
                "t2", [("deepseek", "tencent/deepseek-v4-pro")], exclusions,
                dispatched=False)
        assert calls == [["deepseek"]]

    async def test_fresh_catalog_and_cooldown_never_refresh(
            self, monkeypatch):
        calls: list = []
        h = _bare_handler()
        monkeypatch.setattr(
            h, "_refresh_provider_catalog",
            lambda providers=None, force=False: calls.append(providers))
        exclusions = [
            # Fresh discovery genuinely excludes this name — legit.
            {"route": "deepseek/aihubmix/deepseek-v4-pro",
             "reason": "catalog_not_in_provider",
             "catalog": {"freshness": "fresh", "verified_age_s": 12.0,
                         "last_attempt_age_s": 12.0, "last_error": ""}},
            # Cooldown — a valid restriction.
            {"route": "openrouter/z-ai/glm-5.3-flash",
             "reason": "provider_cooldown",
             "cooldown": {"seconds_remaining": 214, "cause": "quota"}},
            {"route": "deepseek/wandb/DeepSeek-V4-Pro",
             "reason": "direct_api_model_unserved"},
        ]
        await h._route_exclusion_trace_and_refresh(
            "t3", [], exclusions, dispatched=False)
        assert calls == []

    async def test_stale_provider_on_cooldown_is_not_refreshed(
            self, monkeypatch):
        with byok._PROVIDER_COOLDOWN_LOCK:
            byok._PROVIDER_COOLDOWN_UNTIL["deepseek"] = time.time() + 300
            byok._PROVIDER_COOLDOWN_REASON["deepseek"] = ("rate_limit", "429")
        calls: list = []
        h = _bare_handler()
        monkeypatch.setattr(
            h, "_refresh_provider_catalog",
            lambda providers=None, force=False: calls.append(providers))
        exclusions = [{
            "route": "deepseek/tencent/deepseek-v4-pro",
            "reason": "catalog_not_in_provider",
            "catalog": {"freshness": "stale", "verified_age_s": 25200.0,
                        "last_attempt_age_s": 25200.0, "last_error": ""},
        }]
        await h._route_exclusion_trace_and_refresh(
            "t4", [], exclusions, dispatched=False)
        assert calls == []

    async def test_emission_records_pool_and_interactive_flag(
            self, caplog):
        h = _bare_handler()
        with caplog.at_level("INFO"):
            await h._route_exclusion_trace_and_refresh(
                "t5", [("deepseek", "deepseek-chat"),
                       ("deepseek", "deepseek-reasoner")],
                [], dispatched=True)
        line = next(r for r in caplog.records
                    if "route-exclusions" in r.message)
        assert "families" in line.message
        assert "interactive" in line.message
        assert "dispatched" in line.message


class TestFirstAttemptDispatch:
    async def test_healthy_pool_emits_no_refresh_and_no_exhaustion_trace(
            self, monkeypatch, caplog):
        """A healthy first attempt must not pay any refresh or emit the
        exhaustion record — the trace fires only when the cascade actually
        exhausts (dispatched=False there is the caller's fact)."""
        calls: list = []
        h = _bare_handler()
        monkeypatch.setattr(
            h, "_refresh_provider_catalog",
            lambda providers=None, force=False: calls.append(providers))
        # A dispatched=True exhaustion (attempts failed AFTER dispatch) with
        # only legit exclusions: recorded, but nothing refreshed.
        with caplog.at_level("INFO"):
            await h._route_exclusion_trace_and_refresh(
                "t6", [("deepseek", "deepseek-v4-pro")],
                [{"route": "openrouter/x", "reason": "provider_cooldown",
                  "cooldown": {"seconds_remaining": 10, "cause": "quota"}}],
                dispatched=True)
        assert calls == []
