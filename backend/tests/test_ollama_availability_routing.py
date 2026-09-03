"""Ollama availability gating — route to the local runtime only when it's up.

The local runtime answers /api/tags; routing (BPC candidates and the
cross-provider fallback chain) must include Ollama ONLY in that case. Free
local models rank well on value, so an unreachable runtime sitting in the
pool made every request pay its connection-failure tax before failing over.
"""
import time
from unittest.mock import MagicMock

import httpx
import pytest


@pytest.fixture()
def handler():
    from core.llm.byok_handler import BYOKHandler

    return BYOKHandler()


def _fake_tags_response(models):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"models": [{"name": n} for n in models]})
    return resp


class TestRuntimeState:
    def test_up_returns_pulled_names_with_base_names(self, handler, monkeypatch):
        calls = []

        def fake_get(url, **kw):
            calls.append(url)
            return _fake_tags_response(["llama3.1:8b", "qwen2.5vl:3b"])

        monkeypatch.setattr(httpx, "get", fake_get)
        state, pulled = handler._ollama_runtime_state()
        assert state == "up"
        # Tagged names AND tag-stripped base names (catalog ids often carry
        # no tag: 'llama3.1' must match the pulled 'llama3.1:8b').
        assert {"llama3.1:8b", "llama3.1", "qwen2.5vl:3b", "qwen2.5vl"} <= pulled
        assert calls == ["http://localhost:11434/api/tags"]

    def test_down_runtime_reports_down(self, handler, monkeypatch):
        def refused(url, **kw):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "get", refused)
        state, pulled = handler._ollama_runtime_state()
        assert state == "down"
        assert pulled is None

    def test_probe_is_cached_while_down(self, handler, monkeypatch):
        calls = []

        def refused(url, **kw):
            calls.append(url)
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "get", refused)
        handler._ollama_runtime_state()
        handler._ollama_runtime_state()
        handler._ollama_runtime_state()
        # One probe per down-window (60 s TTL) — routing must not re-probe
        # per call or a dead runtime would stall every routing decision.
        assert len(calls) == 1

    def test_down_cache_expires_and_reprobes(self, handler, monkeypatch):
        def refused(url, **kw):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "get", refused)
        handler._ollama_runtime_state()
        # Age the cached probe past the down TTL — the runtime must be
        # re-checked (a restarted Ollama rejoins without a backend restart).
        checked_at, _, _ = handler._ollama_probe_cache
        handler._ollama_probe_cache = (
            checked_at - (handler._OLLAMA_PROBE_TTL_DOWN + 1),
            "down",
            None,
        )
        monkeypatch.setattr(
            httpx, "get", lambda url, **kw: _fake_tags_response(["llama3.1:8b"])
        )
        state, pulled = handler._ollama_runtime_state()
        assert state == "up"
        assert "llama3.1:8b" in pulled

    def test_unreachable_runtime_excluded_from_fallback_order(self, handler, monkeypatch):
        handler.clients = {"openai": MagicMock(), "ollama": MagicMock()}
        monkeypatch.setattr(
            handler, "_ollama_runtime_state", lambda: ("down", None)
        )
        order = handler._get_provider_fallback_order("openai")
        assert "openai" in order
        assert "ollama" not in order

    def test_available_runtime_stays_in_fallback_order(self, handler, monkeypatch):
        handler.clients = {"openai": MagicMock(), "ollama": MagicMock()}
        monkeypatch.setattr(
            handler,
            "_ollama_runtime_state",
            lambda: ("up", {"llama3.1:8b", "llama3.1"}),
        )
        order = handler._get_provider_fallback_order("openai")
        assert "ollama" in order
