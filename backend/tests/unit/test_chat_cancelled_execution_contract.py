"""Cancellation/timeout lifecycle at the Atom and chat boundaries."""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.atom_meta_agent as ama
import integrations.chat_orchestrator as co
from core.agent_action_audit import (  # noqa: F401 — patch targets
    bind_audit_context, log_agent_action,
)
from core.database import Base
from core.models import AgentExecution, ExecutionStatus


@pytest.fixture()
def scratch(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cancel.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    yield Session
    engine.dispose()


@pytest.mark.asyncio
async def test_execute_cancellation_finalizes_owned_running_row(
        scratch, monkeypatch):
    exec_id = str(uuid.uuid4())
    with scratch() as db:
        db.add(AgentExecution(
            id=exec_id, agent_id="atom_main", tenant_id="tenant-1",
            workspace_id="ws-1", status=ExecutionStatus.RUNNING.value,
            input_summary="synthetic cancel", triggered_by="manual",
            started_at=datetime.now(timezone.utc)))
        db.commit()

    agent = ama.AtomMetaAgent.__new__(ama.AtomMetaAgent)
    agent.workspace_id = "ws-1"
    agent.tenant_id = "tenant-1"
    agent.user = None
    monkeypatch.setattr(ama, "SessionLocal", scratch)
    monkeypatch.setattr("core.agent_action_audit.bind_audit_context",
                        lambda *a, **k: None)
    monkeypatch.setattr("core.agent_action_audit.log_agent_action",
                        lambda *a, **k: None)
    monkeypatch.setattr("core.bpe.actions.bind_trusted_scope",
                        lambda *a, **k: None)
    audit_status = []
    agent._close_audit_bracket = lambda *a, **k: audit_status.append(
        (k.get("status"), k.get("success")))

    entered = asyncio.Event()

    async def blocking(*_a, **_k):
        entered.set()
        await asyncio.Event().wait()

    agent.execute_unaudited = blocking
    task = asyncio.create_task(agent.execute("synthetic", execution_id=exec_id))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with scratch() as db:
        row = db.query(AgentExecution).filter(
            AgentExecution.id == exec_id).one()
        assert row.status == "cancelled"
        assert "cancelled before completion" in (row.result_summary or "")
        assert "exact effects unknown" in (row.error_message or "")
    assert audit_status == [("cancelled", False)]


def test_already_finalized_run_is_not_overwritten(scratch):
    exec_id = str(uuid.uuid4())
    with scratch() as db:
        db.add(AgentExecution(
            id=exec_id, agent_id="atom_main", tenant_id="tenant-1",
            workspace_id="ws-1", status="completed",
            input_summary="done", triggered_by="manual",
            started_at=datetime.now(timezone.utc)))
        db.commit()
    agent = ama.AtomMetaAgent.__new__(ama.AtomMetaAgent)
    agent.workspace_id = "ws-1"
    agent.tenant_id = "tenant-1"
    import types
    agent.__dict__["_unused"] = None
    orig = ama.SessionLocal
    ama.SessionLocal = scratch
    try:
        changed = agent._finalize_cancelled_execution(
            exec_id, reason="run_cancelled_before_settlement")
    finally:
        ama.SessionLocal = orig
    assert changed is False
    with scratch() as db:
        assert db.query(AgentExecution).filter(
            AgentExecution.id == exec_id).one().status == "completed"


def test_chat_deadline_partial_only_for_admitted_attempt():
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    assert orch._admitted_agent_deadline_response({}) is None
    session = {"_current_execution_id": "turn-9",
               "_agent_attempt": {"turn_id": "turn-9",
                                  "execution_id": "exec-9"}}
    response = orch._admitted_agent_deadline_response(session)
    assert response["handled"] is True
    assert response["outcome"] == "partial"
    assert response["execution_id"] == "exec-9"
    assert "exact progress is unknown" in response["message"]
    assert "_agent_attempt" not in session


@pytest.mark.asyncio
async def test_agent_handler_uses_server_execution_id_and_propagates_cancel(
        monkeypatch):
    entered = asyncio.Event()
    seen = {}

    class FakeAtom:
        async def execute(self, **kwargs):
            seen.update(kwargs)
            entered.set()
            await asyncio.Event().wait()

    import core.atom_meta_agent as atom_mod
    import core.request_scope as rs
    monkeypatch.setattr(atom_mod, "get_atom_agent", lambda *a, **k: FakeAtom())
    monkeypatch.setattr(rs, "current_request_scope", lambda: {})

    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    async def noop(*_a, **_k):
        return None
    orch._emit_agent_status = noop
    orch._emit_agent_step = noop
    session = {"id": "s-1", "user_id": "u-1"}
    task = asyncio.create_task(orch._handle_agent_request(
        "synthetic", {"primary_intent": co.ChatIntent.AGENT_REQUEST,
                      "confidence": 0.9}, session, {}))
    await entered.wait()
    attempt = session.get("_agent_attempt") or {}
    assert attempt.get("execution_id") == seen.get("execution_id")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # The same cancelled attempt's immediate deadline still needs this state.
    assert session.get("_agent_attempt", {}).get("execution_id") == \
        seen.get("execution_id")


def _cancelled_agent(tenant="tenant-1", workspace="ws-1"):
    agent = ama.AtomMetaAgent.__new__(ama.AtomMetaAgent)
    agent.tenant_id = tenant
    agent.workspace_id = workspace
    agent.user = None
    return agent


def _row(scratch, *, tenant, workspace, status="running"):
    exec_id = str(uuid.uuid4())
    with scratch() as db:
        db.add(AgentExecution(
            id=exec_id, agent_id="atom_main", tenant_id=tenant,
            workspace_id=workspace, status=status,
            input_summary="synthetic", triggered_by="manual",
            started_at=datetime.now(timezone.utc)))
        db.commit()
    return exec_id


def test_cancel_scope_rejects_same_tenant_different_workspace(scratch):
    exec_id = _row(scratch, tenant="tenant-1", workspace="ws-other")
    agent = _cancelled_agent(tenant="tenant-1", workspace="ws-1")
    orig = ama.SessionLocal
    ama.SessionLocal = scratch
    try:
        assert agent._finalize_cancelled_execution(
            exec_id, reason="run_cancelled_before_settlement") is False
    finally:
        ama.SessionLocal = orig
    with scratch() as db:
        assert db.query(AgentExecution).filter(
            AgentExecution.id == exec_id).one().status == "running"


def test_cancel_scope_rejects_different_tenant(scratch):
    exec_id = _row(scratch, tenant="tenant-other", workspace="ws-1")
    agent = _cancelled_agent(tenant="tenant-1", workspace="ws-1")
    orig = ama.SessionLocal
    ama.SessionLocal = scratch
    try:
        assert agent._finalize_cancelled_execution(
            exec_id, reason="run_cancelled_before_settlement") is False
    finally:
        ama.SessionLocal = orig
    with scratch() as db:
        assert db.query(AgentExecution).filter(
            AgentExecution.id == exec_id).one().status == "running"


def test_cancel_scope_unknown_scope_fails_closed(scratch):
    exec_id = _row(scratch, tenant="tenant-1", workspace="ws-1")
    for tenant, workspace in (("", "ws-1"), ("tenant-1", "")):
        agent = _cancelled_agent(tenant=tenant, workspace=workspace)
        orig = ama.SessionLocal
        ama.SessionLocal = scratch
        try:
            assert agent._finalize_cancelled_execution(
                exec_id, reason="run_cancelled_before_settlement") is False
        finally:
            ama.SessionLocal = orig
    with scratch() as db:
        assert db.query(AgentExecution).filter(
            AgentExecution.id == exec_id).one().status == "running"


def test_stale_turn_attempt_is_not_consumed_or_erased():
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    session = {
        "_current_execution_id": "turn-2",
        "_agent_attempt": {"turn_id": "turn-1", "execution_id": "exec-old"},
    }
    assert orch._admitted_agent_deadline_response(session) is None
    assert session["_agent_attempt"]["execution_id"] == "exec-old"
    session["_current_execution_id"] = "turn-1"
    response = orch._admitted_agent_deadline_response(session)
    assert response["outcome"] == "partial"
    assert response["execution_id"] == "exec-old"
    assert "_agent_attempt" not in session


def test_clear_agent_attempt_only_matching_turn():
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    session = {"_agent_attempt": {"turn_id": "t1", "execution_id": "e1"}}
    orch._clear_agent_attempt(session, "e2", "t1")
    assert "_agent_attempt" in session
    orch._clear_agent_attempt(session, "e1", "t1")
    assert "_agent_attempt" not in session


@pytest.mark.asyncio
async def test_success_clears_attempt(monkeypatch):
    class FakeAtom:
        async def execute(self, **_kwargs):
            return {"success": True, "status": "success",
                    "final_output": "done", "execution_id": "exec-ok"}

    import core.atom_meta_agent as atom_mod
    import core.request_scope as rs
    monkeypatch.setattr(atom_mod, "get_atom_agent", lambda *a, **k: FakeAtom())
    monkeypatch.setattr(rs, "current_request_scope", lambda: {})
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    async def noop(*_a, **_k):
        return None
    orch._emit_agent_status = noop
    orch._emit_agent_step = noop
    session = {"id": "s", "user_id": "u",
               "_current_execution_id": "turn-1"}
    result = await orch._handle_agent_request(
        "synthetic", {"primary_intent": co.ChatIntent.AGENT_REQUEST,
                      "confidence": 0.9}, session, {})
    assert result["success"] is True
    assert "_agent_attempt" not in session
