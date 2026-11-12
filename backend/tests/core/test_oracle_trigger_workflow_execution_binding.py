"""Trigger-workflow oracle must be bound to a committed execution.

The old verifier certified an active ``Workflow`` definition alone.  These
controls use a real scratch SQLite store (never the dev DB) to prove that an
active definition with no execution is refuted, that a genuine execution is
required, and that an execution for another definition/input/scope cannot
certify this request.  Definition readiness remains a separate precondition,
and verify-before-retry still blocks duplicates only when the execution exists.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Workflow, WorkflowExecution
from core.oracle import validate, verify_before_retry
from core.oracle.request_expectations import build_request_expectations
from core.workflow_engine import EXECUTION_SCOPE_KEY
import core.oracle.postcondition_verifiers  # noqa: F401 - registers checks


@contextmanager
def _session_scope(session):
    """Yield the caller-owned scratch session (it is closed by its fixture)."""
    yield session



@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool)
    Workflow.__table__.create(engine)
    WorkflowExecution.__table__.create(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _expected(workflow_id="wf-1", input_data=None,
              workspace_id="ws-1", tenant_id="tenant-1",
              operation_id="exec-1"):
    return build_request_expectations(
        "trigger_workflow",
        {"workflow_id": workflow_id, "input_data": input_data or {}},
        operation_id=operation_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        actor_id="user-1",
        agent_id="agent-1",
    )


def _ctx(db, expected, execution_id="exec-1", workflow_id="wf-1"):
    return {
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "db": db,
        **expected,
    }


def _definition(db, workflow_id="wf-1", status="active"):
    row = Workflow(
        id=workflow_id, name=f"Workflow {workflow_id}",
        tenant_id="tenant-1", status=status)
    db.add(row)
    db.commit()
    return row


def _execution(db, execution_id="exec-1", workflow_id="wf-1", *,
               input_data=None, scope=None, status="RUNNING"):
    payload = dict(input_data or {})
    if scope is not None:
        payload[EXECUTION_SCOPE_KEY] = scope
    row = WorkflowExecution(
        execution_id=execution_id,
        workflow_id=workflow_id,
        status=status,
        input_data=json.dumps(payload),
    )
    db.add(row)
    db.commit()
    return row


@pytest.mark.asyncio
async def test_genuine_committed_execution_verifies(db):
    expected = _expected(input_data={"customer": "acme"})
    assert expected["_oracle_expected_workflow_id"] == "wf-1"
    assert expected["_oracle_expected_workflow_input_sha256"]

    _definition(db)
    _execution(
        db, input_data={"customer": "acme"},
        scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"},
        status="COMPLETED")

    result = await validate("trigger_workflow", _ctx(db, expected))

    assert result is not None
    assert result.verified is True, result.evidence
    assert "exec-1" in result.evidence
    assert "committed" in result.evidence


@pytest.mark.asyncio
async def test_active_definition_without_execution_is_refuted(db):
    """The old active-definition-only check would pass; the trigger must not."""
    expected = _expected(operation_id="exec-missing")
    definition = _definition(db)
    assert definition.status == "active"

    result = await validate(
        "trigger_workflow",
        _ctx(db, expected, execution_id="exec-missing"))

    assert result is not None
    assert result.verified is False
    assert "not committed" in result.evidence


@pytest.mark.asyncio
async def test_active_definition_alone_is_not_enough_without_frozen_request(db):
    """A caller that only supplies workflow_id must not be certified."""
    _definition(db)

    result = await validate("trigger_workflow", {
        "workflow_id": "wf-1", "execution_id": "exec-1", "db": db})

    assert result is not None
    assert result.verified is False
    assert "no frozen workflow identity" in result.evidence


@pytest.mark.asyncio
async def test_execution_bound_to_another_definition_is_refuted(db):
    expected = _expected()
    _definition(db)
    _definition(db, workflow_id="wf-other")
    _execution(
        db, workflow_id="wf-other", input_data={},
        scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    result = await validate("trigger_workflow", _ctx(db, expected))

    assert result is not None
    assert result.verified is False
    assert "bound to workflow 'wf-other'" in result.evidence


@pytest.mark.asyncio
async def test_execution_for_another_frozen_input_is_refuted(db):
    expected = _expected(input_data={"customer": "acme"})
    _definition(db)
    _execution(
        db, input_data={"customer": "other"},
        scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    result = await validate("trigger_workflow", _ctx(db, expected))

    assert result is not None
    assert result.verified is False
    assert "does not match the frozen authorized request" in result.evidence


@pytest.mark.asyncio
async def test_execution_for_another_frozen_scope_is_refuted(db):
    expected = _expected()
    _definition(db)
    _execution(
        db, input_data={},
        scope={"workspace_id": "ws-other", "tenant_id": "tenant-1"})

    result = await validate("trigger_workflow", _ctx(db, expected))

    assert result is not None
    assert result.verified is False
    assert "workspace 'ws-other' != 'ws-1'" in result.evidence


@pytest.mark.asyncio
async def test_execution_without_frozen_scope_is_refuted(db):
    expected = _expected()
    _definition(db)
    _execution(db, input_data={})

    result = await validate("trigger_workflow", _ctx(db, expected))

    assert result is not None
    assert result.verified is False
    assert "no frozen caller scope" in result.evidence


@pytest.mark.asyncio
async def test_missing_result_execution_id_is_refuted(db):
    """No result id and no frozen operation identity cannot prove a run."""
    expected = _expected(operation_id="")
    _definition(db)
    _execution(
        db, input_data={},
        scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    result = await validate(
        "trigger_workflow", _ctx(db, expected, execution_id=""))

    assert result is not None
    assert result.verified is False
    assert "no exact execution id" in result.evidence


@pytest.mark.asyncio
async def test_forged_result_execution_id_is_refuted(db):
    """A result id that contradicts the frozen operation identity is refused."""
    expected = _expected(operation_id="exec-durable")
    _definition(db)
    _execution(
        db, execution_id="exec-durable", input_data={},
        scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    result = await validate(
        "trigger_workflow",
        _ctx(db, expected, execution_id="exec-forged"))

    assert result is not None
    assert result.verified is False
    assert "does not match the server-owned operation identity" in result.evidence


@pytest.mark.asyncio
async def test_inactive_definition_stays_unready_even_with_execution(db):
    expected = _expected()
    _definition(db, status="paused")
    _execution(
        db, input_data={},
        scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    result = await validate("trigger_workflow", _ctx(db, expected))

    assert result is not None
    assert result.verified is False
    assert "not active" in result.evidence


@pytest.mark.asyncio
async def test_verify_before_retry_committed_execution_blocks_retry(
        db, monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    expected = _expected()
    _definition(db)
    _execution(
        db, input_data={},
        scope={"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    assert await verify_before_retry(
        "trigger_workflow", _ctx(db, expected)) is True


@pytest.mark.asyncio
async def test_verify_before_retry_missing_execution_allows_retry(
        db, monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    expected = _expected(operation_id="exec-missing")
    _definition(db)

    assert await verify_before_retry(
        "trigger_workflow",
        _ctx(db, expected, execution_id="exec-missing")) is False


@pytest.mark.asyncio
async def test_mcp_trigger_freezes_scope_and_operation_identity(monkeypatch):
    """The dispatch path binds the same server-owned identity the oracle uses."""
    from types import SimpleNamespace

    from integrations.mcp_service import mcp_service

    calls = {}

    class _FakeOrchestrator:
        async def execute_workflow(self, workflow_id, input_data,
                                   execution_context=None,
                                   execution_id=None):
            calls["workflow_id"] = workflow_id
            calls["input_data"] = input_data
            calls["execution_context"] = execution_context
            calls["execution_id"] = execution_id
            return SimpleNamespace(
                status=SimpleNamespace(value="COMPLETED"),
                workflow_id=execution_id or "exec-scope-1",
                results={},
                error_message=None,
            )

    monkeypatch.setattr(
        "advanced_workflow_orchestrator.get_orchestrator",
        lambda: _FakeOrchestrator())
    monkeypatch.setattr(
        "core.workflow_security.resolve_orchestrator_steps",
        lambda orchestrator, workflow_id: [])

    result = await mcp_service.execute_tool(
        "local-tools", "trigger_workflow",
        {"workflow_id": "wf-1", "input_data": {"customer": "acme"}},
        context={
            "workspace_id": "ws-1", "tenant_id": "tenant-1",
            "user_id": "user-1", "operation_id": "auto-op-mcp-1",
        })

    assert calls["workflow_id"] == "wf-1"
    assert calls["input_data"]["customer"] == "acme"
    assert calls["input_data"][EXECUTION_SCOPE_KEY] == {
        "workspace_id": "ws-1", "tenant_id": "tenant-1"}
    assert calls["execution_context"] == {
        "workspace_id": "ws-1", "tenant_id": "tenant-1",
        "user_id": "user-1"}
    assert calls["execution_id"] == "auto-op-mcp-1"
    assert result["execution_id"] == "auto-op-mcp-1"


# ---------------------------------------------------------------------------
# Caller-level lost-response reconciliation (GenericAgent timeout path)
# ---------------------------------------------------------------------------
class _LostResponseMCP:
    """Dispatch commits an execution row, then the response is lost."""

    def __init__(self, session_factory, *, commit=True,
                 workflow_id="wf-1", scope=("ws-1", "tenant-1")):
        self.session_factory = session_factory
        self.commit = commit
        self.workflow_id = workflow_id
        self.scope = scope
        self.calls = []

    async def call_tool(self, tool_name, arguments, context=None):
        self.calls.append((tool_name, dict(arguments), dict(context or {})))
        if self.commit:
            operation_id = str((context or {}).get("operation_id") or "")
            with self.session_factory() as db:
                _execution(
                    db, execution_id=operation_id or "exec-fallback",
                    workflow_id=self.workflow_id,
                    input_data=arguments.get("input_data") or {},
                    scope={
                        "workspace_id": self.scope[0],
                        "tenant_id": self.scope[1],
                    })
        raise asyncio.TimeoutError("connection lost after dispatch")


def _caller_agent(mcp):
    from core.generic_agent import GenericAgent

    agent = GenericAgent.__new__(GenericAgent)
    agent.mcp = mcp
    agent._custom_actions = {}
    agent.id = "agent-1"
    agent.workspace_id = "ws-1"
    agent.tenant_id = "tenant-1"
    return agent


def _caller_context(operation_id="auto-op-commit-1"):
    return {
        "operation_id": operation_id,
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "execution_id": "run-1",
        "user_id": "user-1",
    }


async def _dispatch(_agent, context):
    return await _agent._step_act_unaudited(
        "trigger_workflow",
        {"workflow_id": "wf-1", "input_data": {"customer": "acme"}},
        context=context,
        pre_approved=True,
    )


@pytest.mark.asyncio
async def test_lost_response_after_commit_reconciles_without_duplicate(
        db, monkeypatch):
    """Commit succeeded but the result was lost → caller proves it, no retry."""
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.setattr(ga, "get_db_session", lambda: _session_scope(db))
    _definition(db)
    mcp = _LostResponseMCP(lambda: _session_scope(db))
    agent = _caller_agent(mcp)

    out = await _dispatch(agent, _caller_context())

    assert len(mcp.calls) == 1, "the caller must not dispatch a duplicate"
    assert isinstance(out, str)
    assert "verified" in out and "Do NOT retry" in out
    # The dispatch context, not the test, supplied the durable identity.
    assert mcp.calls[0][2]["operation_id"] == "auto-op-commit-1"


@pytest.mark.asyncio
async def test_lost_response_without_committed_proof_is_uncertain_no_retry(
        db, monkeypatch):
    """No committed execution → unproven, and no automatic retry invitation."""
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.setattr(ga, "get_db_session", lambda: _session_scope(db))
    _definition(db)
    mcp = _LostResponseMCP(lambda: _session_scope(db), commit=False)
    agent = _caller_agent(mcp)

    out = await _dispatch(agent, _caller_context())

    assert len(mcp.calls) == 1
    assert isinstance(out, dict)
    assert out["retryable"] is False
    assert out["requires_reconciliation"] is True
    assert out["oracle_verified"] is False
    assert "try once more" not in out["message"]


@pytest.mark.asyncio
async def test_lost_response_with_foreign_execution_is_refused(
        db, monkeypatch):
    """A committed but foreign execution never certifies this trigger."""
    import core.generic_agent as ga

    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    monkeypatch.setattr(ga, "get_db_session", lambda: _session_scope(db))
    _definition(db)
    _definition(db, workflow_id="wf-other")
    mcp = _LostResponseMCP(
        lambda: _session_scope(db), workflow_id="wf-other")
    agent = _caller_agent(mcp)

    out = await _dispatch(agent, _caller_context())

    assert len(mcp.calls) == 1
    assert isinstance(out, dict)
    assert out["retryable"] is False
    assert out["oracle_verified"] is False


# ---------------------------------------------------------------------------
# Meta-agent direct dispatch: committed execution readback
# ---------------------------------------------------------------------------
class _CommittingEngine:
    def __init__(self, session_factory, *, commit=True,
                 execution_id="exec-meta-1", stored_workflow_id="wf-1",
                 stored_scope=None):
        self.session_factory = session_factory
        self.commit = commit
        self.execution_id = execution_id
        self.stored_workflow_id = stored_workflow_id
        self.stored_scope = stored_scope
        self.calls = []

    async def start_workflow(self, workflow, input_data, *, scope=None):
        self.calls.append((workflow, dict(input_data), dict(scope or {})))
        if self.commit:
            with self.session_factory() as db:
                _execution(
                    db, execution_id=self.execution_id,
                    workflow_id=self.stored_workflow_id,
                    input_data=input_data,
                    scope=self.stored_scope or scope or {})
        return self.execution_id


def _meta_agent():
    from core.atom_meta_agent import AtomMetaAgent

    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.workspace_id = "ws-1"
    agent.tenant_id = "tenant-1"
    return agent


def _patch_meta_runtime(monkeypatch, db, engine):
    import core.database as database
    import core.workflow_engine as workflow_engine

    monkeypatch.setattr(
        workflow_engine, "get_workflow_engine", lambda: engine)
    monkeypatch.setattr(
        database, "get_db_session", lambda: _session_scope(db))


@pytest.mark.asyncio
async def test_meta_agent_direct_dispatch_requires_committed_execution(
        db, monkeypatch):
    _definition(db)
    engine = _CommittingEngine(lambda: _session_scope(db))
    _patch_meta_runtime(monkeypatch, db, engine)

    out = await _meta_agent()._trigger_workflow(
        "wf-1", {"customer": "acme"},
        {"workspace_id": "ws-1", "tenant_id": "tenant-1",
         "user_id": "user-1"})

    assert "exec-meta-1" in out
    assert "not confirmed" not in out
    assert engine.calls[0][2] == {
        "workspace_id": "ws-1", "tenant_id": "tenant-1"}


@pytest.mark.asyncio
async def test_meta_agent_direct_dispatch_refuses_uncommitted_execution(
        db, monkeypatch):
    _definition(db)
    engine = _CommittingEngine(lambda: _session_scope(db), commit=False)
    _patch_meta_runtime(monkeypatch, db, engine)

    out = await _meta_agent()._trigger_workflow(
        "wf-1", {"customer": "acme"},
        {"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    assert "not confirmed" in out
    assert "Do NOT retry" in out
    assert "exec-meta-1" in out


@pytest.mark.asyncio
async def test_meta_agent_direct_dispatch_refuses_foreign_execution(
        db, monkeypatch):
    _definition(db)
    _definition(db, workflow_id="wf-other")
    engine = _CommittingEngine(
        lambda: _session_scope(db), stored_workflow_id="wf-other")
    _patch_meta_runtime(monkeypatch, db, engine)

    out = await _meta_agent()._trigger_workflow(
        "wf-1", {"customer": "acme"},
        {"workspace_id": "ws-1", "tenant_id": "tenant-1"})

    assert "not confirmed" in out
    assert "bound to workflow 'wf-other'" in out
