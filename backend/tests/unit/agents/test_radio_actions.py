"""radio_actions tests — the 3 radio.* Unified-Action-Registry primitives.

Covers what the spec mandates for the action surface:
  - registration via @register_action (they appear in action_registry),
  - maturity floors: create_thread/send_message INTERN+, wait STUDENT+,
  - the ATOM_RADIO_ENABLED kill switch degrades gracefully (success:false),
  - happy path: create_thread -> send_message (mention-first) -> wait resolves.

These call the handlers directly through the registry's execute_action so the
test exercises the same code path as POST /api/rpc/radio.* (minus the HTTP and
auth layers, which have their own coverage).
"""

from __future__ import annotations

import asyncio

import pytest

from core.action_registry import action_registry
from core.agent_radio import radio_actions  # noqa: F401 — registers on import
from core.agent_radio import radio_server
from core.models import AgentThread, LateralMessage


@pytest.fixture(autouse=True)
def _reset_server():
    radio_server.reset_radio_server()
    yield
    radio_server.reset_radio_server()


def _ctx(agent_id="agent_a", tier="autonomous", tenant_id="t1"):
    return {"agent_id": agent_id, "tier": tier, "tenant_id": tenant_id}


class TestRegistration:
    def test_all_three_actions_registered(self):
        for name in ("radio.create_thread", "radio.send_message", "radio.wait_for_mention"):
            assert action_registry.get_action(name) is not None, f"{name} missing"


class TestTierFloors:
    @pytest.mark.asyncio
    async def test_student_cannot_create_thread(self, db_session):
        res = await action_registry.execute_action(
            "radio.create_thread",
            {"name": "t", "member_agent_ids": ["agent_b"]},
            _ctx(tier="student"),
        )
        assert res["success"] is False
        assert "INTERN" in res["error"]

    @pytest.mark.asyncio
    async def test_student_cannot_send(self, db_session):
        res = await action_registry.execute_action(
            "radio.send_message",
            {"thread_id": "x", "content": "hi", "mention_agent_ids": ["b"]},
            _ctx(tier="student"),
        )
        assert res["success"] is False and "INTERN" in res["error"]

    @pytest.mark.asyncio
    async def test_student_can_wait(self, db_session, monkeypatch):
        # wait_for_mention is STUDENT+ (read-only). With a tiny timeout it must
        # simply time out cleanly — no tier error.
        monkeypatch.setattr(
            "core.agent_radio.radio_config.wait_timeout_seconds", lambda: 0
        )
        res = await action_registry.execute_action(
            "radio.wait_for_mention",
            {"thread_id": "does-not-exist", "timeout": 0},
            _ctx(agent_id="agent_a", tier="student"),
        )
        assert res["success"] is True
        assert res.get("timed_out") is True


class TestKillSwitch:
    @pytest.mark.asyncio
    async def test_disabled_returns_graceful_note(self, db_session, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.radio_enabled", lambda: False)
        for name, args in [
            ("radio.create_thread", {"name": "t", "member_agent_ids": ["b"]}),
            ("radio.send_message", {"thread_id": "x", "content": "hi", "mention_agent_ids": ["b"]}),
            ("radio.wait_for_mention", {"thread_id": "x"}),
        ]:
            res = await action_registry.execute_action(name, args, _ctx())
            assert res["success"] is False
            assert res["error"] == "radio_disabled"


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_create_send_wait(self, db_session, monkeypatch):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield db_session

        monkeypatch.setattr("core.database.get_db_session", _cm)

        # 1) create a thread with two members.
        created = await action_registry.execute_action(
            "radio.create_thread",
            {"name": "alpha", "member_agent_ids": ["agent_b"], "scope_hint": "task"},
            _ctx(agent_id="agent_a"),
        )
        assert created["success"] is True
        thread_id = created["thread_id"]
        assert "agent_a" in created["member_agent_ids"]

        # 2) agent_b sends a mention to agent_a.
        sent = await action_registry.execute_action(
            "radio.send_message",
            {
                "thread_id": thread_id,
                "content": "found the bug at app.py:42",
                "mention_agent_ids": ["agent_a"],
                "requires_response": True,
            },
            _ctx(agent_id="agent_b"),
        )
        assert sent["success"] is True
        assert "agent_a" in sent["mentions"]

        # 3) agent_a waits (mention already pending) — resolves immediately.
        waited = await action_registry.execute_action(
            "radio.wait_for_mention",
            {"thread_id": thread_id, "timeout": 1},
            _ctx(agent_id="agent_a"),
        )
        assert waited["success"] is True
        assert waited.get("content") == "found the bug at app.py:42"

    @pytest.mark.asyncio
    async def test_send_without_mention_is_policy_error(self, db_session, monkeypatch):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield db_session

        monkeypatch.setattr("core.database.get_db_session", _cm)
        created = await action_registry.execute_action(
            "radio.create_thread",
            {"name": "beta", "member_agent_ids": ["agent_b"]},
            _ctx(agent_id="agent_a"),
        )
        res = await action_registry.execute_action(
            "radio.send_message",
            {"thread_id": created["thread_id"], "content": "hello team"},
            _ctx(agent_id="agent_a"),
        )
        assert res["success"] is False
        assert res["error"] == "policy_error"

    @pytest.mark.asyncio
    async def test_missing_agent_context_rejected(self, db_session):
        res = await action_registry.execute_action(
            "radio.create_thread",
            {"name": "no-actor", "member_agent_ids": ["b"]},
            {"tier": "autonomous"},  # no agent_id
        )
        assert res["success"] is False
        assert "agent_id" in res["error"]
