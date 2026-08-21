"""
Tests for the berd gap closures: ACP bridge, experiment registry,
edition seams, API version pin.
"""

import os
os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocketDisconnect


# --------------------------------------------------------------------------- #
# G1 — ACP bridge
# --------------------------------------------------------------------------- #

class TestACPBridge:
    def _make_ws(self):
        from api import acp_routes

        ws = MagicMock()
        ws.query_params = {"token": "t"}
        received = []

        async def send_json(msg):
            received.append(msg)

        async def receive_json():
            item = receive_json.queue.pop(0)
            if item is WebSocketDisconnect:
                raise item
            return item

        receive_json.queue = []
        ws.send_json = send_json
        ws.receive_json = receive_json

        async def accept():
            pass

        async def close():
            pass

        ws.accept = accept
        ws.close = close
        return acp_routes, ws, received

    @pytest.mark.asyncio
    async def test_initialize_handshake(self):
        acp, ws, received = self._make_ws()
        ws.receive_json.queue = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": 1}},
            {"jsonrpc": "2.0", "id": 2, "method": "session/new", "params": {"cwd": "/tmp"}},
            WebSocketDisconnect,
        ]
        fake_user = MagicMock(); fake_user.id = "u1"
        with patch("api.acp_routes.get_current_user_ws", AsyncMock(return_value=fake_user)), \
             patch("api.acp_routes.SessionLocal", return_value=MagicMock()):
            await acp.acp_websocket(ws)  # exits via WebSocketDisconnect sentinel

        init = next(m for m in received if m.get("id") == 1)
        assert init["result"]["protocolVersion"] == 1
        assert init["result"]["agentCapabilities"]["loadSession"] is True
        assert init["result"]["agentInfo"]["name"] == "Atom"

        new_session = next(m for m in received if m.get("id") == 2)
        assert new_session["result"]["sessionId"]

    @pytest.mark.asyncio
    async def test_prompt_streams_update_then_stop_reason(self):
        acp, ws, received = self._make_ws()
        ws.receive_json.queue = [
            {"jsonrpc": "2.0", "id": 3, "method": "session/prompt",
             "params": {"sessionId": "s1", "prompt": [{"type": "text", "text": "hi"}]}},
            WebSocketDisconnect,
        ]
        fake_user = MagicMock(); fake_user.id = "u1"
        fake_orch = MagicMock()
        fake_orch.process_chat_message = AsyncMock(return_value={
            "message": "the answer", "session_id": "s1",
        })

        class _FakeOrch:
            def __init__(self, *a, **k): pass

        with patch("api.acp_routes.get_current_user_ws", AsyncMock(return_value=fake_user)), \
             patch("api.acp_routes.SessionLocal", return_value=MagicMock()), \
             patch("integrations.chat_orchestrator.ChatOrchestrator", _FakeOrch), \
             patch("integrations.chat_orchestrator.ChatOrchestrator") as orch_cls:
            orch_cls.return_value = fake_orch
            await acp.acp_websocket(ws)  # exits via WebSocketDisconnect sentinel

        update = next(m for m in received if m.get("method") == "session/update")
        assert update["params"]["sessionId"] == "s1"
        assert update["params"]["update"]["sessionUpdate"] == "agent_message_chunk"
        assert update["params"]["update"]["content"]["text"] == "the answer"
        result = next(m for m in received if m.get("id") == 3)
        assert result["result"]["stopReason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_rejects_missing_token(self):
        from api import acp_routes

        ws = MagicMock()
        ws.query_params = {}
        ws.close = AsyncMock()
        await acp_routes.acp_websocket(ws)
        ws.close.assert_awaited_once()


# --------------------------------------------------------------------------- #
# G5 — experiment registry
# --------------------------------------------------------------------------- #

class TestExperimentRegistry:
    def test_registered_defaults_prod(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("NODE_ENV", raising=False)
        monkeypatch.delenv("TELEGRAM_POLLING_ENABLED", raising=False)  # .env sets it
        from core.experiments import is_enabled

        assert is_enabled("memory_context_assembly") is True   # default True
        assert is_enabled("telegram_polling") is False          # default False (no override)

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "false")
        from core.experiments import is_enabled

        assert is_enabled("memory_context_assembly") is False

    def test_unknown_experiment_off(self):
        from core.experiments import is_enabled

        assert is_enabled("no_such_experiment") is False

    def test_summary_includes_all(self):
        from core.experiments import registry_summary

        s = registry_summary()
        assert "memory_rerank" in s and "enabled" in s["memory_rerank"]


# --------------------------------------------------------------------------- #
# G6 — edition seams
# --------------------------------------------------------------------------- #

class TestEditionSeams:
    def test_community_defaults_without_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_DISTRIBUTION_FILE", str(tmp_path / "none.json"))
        import core.edition as ed
        ed._cache = None
        assert ed.seam("edition") == "community"
        assert ed.provider_allowed("anything") is True

    def test_distribution_overrides(self, tmp_path, monkeypatch):
        f = tmp_path / "distribution.json"
        f.write_text('{"edition": "client-hosted", "provider_policy": {"allowed_providers": ["opencode-go"]}, "branding": {"name": "Acme Agent"}}')
        monkeypatch.setenv("ATOM_DISTRIBUTION_FILE", str(f))
        import core.edition as ed
        ed._cache = None
        assert ed.seam("edition") == "client-hosted"
        assert ed.provider_allowed("opencode-go") is True
        assert ed.provider_allowed("openai") is False
        assert ed.seam("branding")["name"] == "Acme Agent"

    def test_invalid_file_falls_back(self, tmp_path, monkeypatch):
        f = tmp_path / "distribution.json"
        f.write_text("{ not json")
        monkeypatch.setenv("ATOM_DISTRIBUTION_FILE", str(f))
        import core.edition as ed
        ed._cache = None
        assert ed.seam("edition") == "community"

    def test_unknown_seam_ignored(self, tmp_path, monkeypatch):
        f = tmp_path / "distribution.json"
        f.write_text('{"totally_unknown": 1}')
        monkeypatch.setenv("ATOM_DISTRIBUTION_FILE", str(f))
        import core.edition as ed
        ed._cache = None
        assert ed.seam("edition") == "community"
