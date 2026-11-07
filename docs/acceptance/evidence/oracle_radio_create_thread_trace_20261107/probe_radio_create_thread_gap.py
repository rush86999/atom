"""Failure-first probe for the selected ORACLE row: radio.create_thread.

This probe states the end state the shared consumer needs, not a workaround:

  * the REAL registered action + REAL radio service persist an AgentThread;
  * the REAL GenericAgent mutation consumer must be able to independently
    certify the exact thread/material from a fresh session.

On the current source (36fa4ce39) it fails because no postcondition verifier is
registered for radio.create_thread; the consumer correctly reports
"no registered postcondition verifier" and stamps oracle_verified=False.  That
is the gap this trace proposes to close with the existing Oracle mechanisms.

It also records the authority boundary: a roster that names an agent from a
different tenant is persisted today, and the consumer has no verifier that can
evaluate the tenant/member contradiction.

Run through the shared bounded gate (never a bare heavy pytest).
"""
from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
import core.models  # noqa: F401 - register every model on the base
from core.action_registry import action_registry
from core.agent_radio import radio_actions  # noqa: F401 - registers actions
from core.agent_radio import radio_server
from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentThread
from core.models_registration import Base


@contextlib.contextmanager
def _session_factory(path):
    engine = create_engine(f"sqlite:///{path}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _reset_radio_server():
    radio_server.reset_radio_server()
    yield
    radio_server.reset_radio_server()


@pytest.fixture(autouse=True)
def _oracle_on(monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.setenv("ATOM_RADIO_ENABLED", "true")


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / "radio_thread.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        return _session_factory(path)

    monkeypatch.setattr(ga, "get_db_session", _session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr("core.database.get_db_session", _session)

    with Session() as db:
        db.add_all([
            AgentRegistry(
                id="agent-a", name="Agent A", category="operations",
                module_path="x.a", class_name="A",
                tenant_id="tenant-1", workspace_id="ws-1",
                status="autonomous"),
            AgentRegistry(
                id="agent-b", name="Agent B", category="operations",
                module_path="x.b", class_name="B",
                tenant_id="tenant-1", workspace_id="ws-1",
                status="autonomous"),
        ])
        db.commit()
    return {"path": str(path), "Session": Session}


def _agent():
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "agent-a"
    agent.workspace_id = "ws-1"
    agent.tenant_id = "tenant-1"
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=registry_leaf)
    return agent


def _context(operation_id, *, tenant_id="tenant-1"):
    return {
        "operation_id": operation_id,
        "workspace_id": "ws-1",
        "tenant_id": tenant_id,
        "execution_id": "exec-radio-thread",
        "user_id": "user-radio",
        "agent_id": "agent-a",
        "tier": "autonomous",
    }


def _call(agent, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        "radio.create_thread", arguments, context=context,
        pre_approved=True))


def _threads(env):
    with env["Session"]() as db:
        return db.query(AgentThread).all()


def test_create_thread_is_independently_verified(env):
    operation_id = "op-radio-thread-exact"
    result = _call(
        _agent(),
        {
            "name": "alpha",
            "member_agent_ids": ["agent-b"],
            "scope_hint": "task",
            "operation_id": operation_id,
        },
        _context(operation_id),
    )

    thread_id = result.get("thread_id") or result.get("remote_id")
    assert thread_id, result
    rows = _threads(env)
    assert len(rows) == 1, rows
    thread = rows[0]
    assert thread.name == "alpha"
    assert thread.created_by_agent_id == "agent-a"
    assert sorted(thread.member_agent_ids or []) == ["agent-a", "agent-b"]
    assert thread.tenant_id == "tenant-1"
    assert (thread.metadata_json or {}).get("scope") == "task"

    # The end state: the shared consumer independently certifies the exact row.
    assert result.get("oracle_verified") is True, result.get("oracle_evidence")
    assert result.get("success") is True, result
    assert result.get("action_result") == "applied", result


def test_cross_tenant_roster_cannot_be_certified(env):
    with env["Session"]() as db:
        db.add(AgentRegistry(
            id="agent-other", name="Other Tenant Agent", category="operations",
            module_path="x.o", class_name="O",
            tenant_id="tenant-2", workspace_id="ws-2",
            status="autonomous"))
        db.commit()

    operation_id = "op-radio-thread-cross-tenant"
    result = _call(
        _agent(),
        {
            "name": "cross-tenant",
            "member_agent_ids": ["agent-other"],
            "scope_hint": "task",
            "operation_id": operation_id,
        },
        _context(operation_id),
    )

    # A pre-effect refusal is acceptable.  Otherwise the consumer must evaluate
    # the tenant/member contradiction, not merely say "no verifier".
    evidence = str(result.get("oracle_evidence") or "").lower()
    refused_before_effect = (
        result.get("success") is False
        and str(result.get("action_result") or "").lower()
        in {"proven_not_applied", "failed_before_effect", "not_applied"})
    contradiction_named = (
        result.get("oracle_verified") is False
        and any(term in evidence for term in ("tenant", "member", "cross")))
    assert refused_before_effect or contradiction_named, result
