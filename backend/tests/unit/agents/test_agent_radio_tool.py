"""AgentRadio tool tests — registry actions, tier gates, and RPC surface.

The tools are registered in the Unified Action Registry (radio.* namespace),
which is what both `POST /api/rpc/{action}` and `mcp_service.call_tool`
dispatch through — so capability (P2) and sandbox (P9) gating apply
automatically. Maturity floors are enforced inside the handlers.
"""

import pytest
from unittest.mock import patch

from core.action_registry import action_registry
from tools.agent_radio_tool import (
    RADIO_TOOL_NAMES,
    radio_create_thread,
    radio_read_inbox,
    radio_send_message,
)


class TestRegistrySurface:
    def test_all_radio_actions_registered(self):
        for name in RADIO_TOOL_NAMES:
            assert action_registry.get_action(name) is not None, name

    def test_rpc_params_schemas(self):
        for name, cert in [("radio.create_thread", ("member_agent_ids",)),
                           ("radio.send_message", ("thread_id", "content", "mention_agent_ids")),
                           ("radio.wait_for_mention", ("thread_id",))]:
            defn = action_registry.get_action(name)
            props = defn.parameters_schema["properties"]
            for key in cert:
                assert key in props, f"{name} missing {key}"


class TestTierGates:
    async def test_create_thread_student_denied(self):
        result = await radio_create_thread(
            {"name": "t", "member_agent_ids": ["agent_b"]},
            {"tier": "student"})
        assert result["success"] is False
        assert "INTERN+" in result["error"]

    async def test_send_message_student_denied(self):
        result = await radio_send_message(
            {"thread_id": "x", "content": "hi", "mention_agent_ids": ["agent_b"]},
            {"tier": "student"})
        assert result["success"] is False

    async def test_read_inbox_student_allowed(self, db_session, monkeypatch):
        monkeypatch.setattr("core.database.get_db_session", lambda: db_session)
        result = await radio_read_inbox(
            {"thread_id": "missing"}, {"tier": "student", "agent_id": "agent_a"})
        assert result["success"] is True
        assert result["found"] is False


class TestExplicitDisabled:
    async def test_tools_degrade_when_flag_off(self, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.radio_enabled",
                            lambda: False)
        result = await radio_create_thread(
            {"name": "t", "member_agent_ids": ["agent_b"]},
            {"tier": "intern"})
        assert result["success"] is False
        assert "disabled" in result["error"]


class TestToolHandlers:
    async def test_create_send_read_round_trip(self, db_session, monkeypatch):
        from core.agent_radio import radio_service

        monkeypatch.setattr("core.database.get_db_session", lambda: db_session)

        created = await radio_create_thread(
            {"name": "algo", "member_agent_ids": ["agent_b"]},
            {"tier": "intern", "agent_id": "agent_a"})
        assert created["success"] is True
        thread_id = created["thread_id"]

        sent = await radio_send_message(
            {"thread_id": thread_id, "content": "evidence located",
             "mention_agent_ids": ["agent_b"]},
            {"tier": "intern", "agent_id": "agent_a"})
        assert sent["success"] is True

        inbox = radio_service.inbox_drain_text("agent_b", thread_id, max_items=5)
        assert "evidence located" in inbox

    async def test_broadcast_rejected_via_tool(self, db_session, monkeypatch):
        from core.agent_radio.radio_server import get_radio_server

        monkeypatch.setattr("core.database.get_db_session", lambda: db_session)
        created = await radio_create_thread(
            {"name": "t", "member_agent_ids": ["agent_b"]},
            {"tier": "intern", "agent_id": "agent_a"})
        result = await radio_send_message(
            {"thread_id": created["thread_id"], "content": "to everyone"},
            {"tier": "intern", "agent_id": "agent_a"})
        assert result["success"] is False
        assert result["error"] in ("policy_error", "access_error")
        assert "mention" in result.get("message", "").lower()