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


@pytest.fixture(autouse=True)
def _reset_shared_down_memo():
    """Each test starts with no process-wide DOWN memo (see
    BYOKHandler._OLLAMA_DOWN_MEMO) — otherwise verdicts leak between tests."""
    from core.llm.byok_handler import BYOKHandler

    BYOKHandler._OLLAMA_DOWN_MEMO = None
    yield
    BYOKHandler._OLLAMA_DOWN_MEMO = None


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
        from core.llm.byok_handler import BYOKHandler

        def refused(url, **kw):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "get", refused)
        handler._ollama_runtime_state()
        # Age the cached probe past the down TTL — the runtime must be
        # re-checked (a restarted Ollama rejoins without a backend restart).
        # The shared DOWN memo must be aged too, or it answers before the
        # probe can re-run.
        checked_at, _, _ = handler._ollama_probe_cache
        handler._ollama_probe_cache = (
            checked_at - (handler._OLLAMA_PROBE_TTL_DOWN + 1),
            "down",
            None,
        )
        BYOKHandler._OLLAMA_DOWN_MEMO = (
            time.time() - (handler._OLLAMA_DOWN_MEMO_TTL + 1)
        )
        monkeypatch.setattr(
            httpx, "get", lambda url, **kw: _fake_tags_response(["llama3.1:8b"])
        )
        state, pulled = handler._ollama_runtime_state()
        assert state == "up"
        assert "llama3.1:8b" in pulled
        assert BYOKHandler._OLLAMA_DOWN_MEMO is None

    def test_down_memo_shared_across_instances(self, monkeypatch):
        """The chat path builds several BYOKHandlers per message; a dead
        Ollama must be probed once for all of them, not once per handler
        (each probe is blocking sync httpx inside the request path)."""
        from core.llm.byok_handler import BYOKHandler

        calls = []

        def refused(url, **kw):
            calls.append(url)
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "get", refused)
        first = BYOKHandler()
        first._ollama_runtime_state()
        second = BYOKHandler()
        state, pulled = second._ollama_runtime_state()
        assert state == "down"
        assert pulled is None
        assert len(calls) == 1

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
