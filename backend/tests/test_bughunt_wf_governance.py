"""TDD bug-hunt: workflow governance interlock (R82 follow-up).

The linear step executor called ``governance.can_perform_action(action=...)``
with the wrong kwarg (signature is ``action_type``) and destructured the
returned dict as a 2-tuple — every step raised TypeError, the except clause
logged "failing open", and governance was NEVER enforced for linear
workflows. Unknown agents are denied by the sync path, so enforcement must
apply only to registry-backed agents (unbound ``system_agent`` workflows
have no governance identity).
"""
from __future__ import annotations

import asyncio

import pytest

from tests.test_covpush_wfengine import (
    FakeAnalytics,
    FakeStateManager,
    FakeWSManager,
    _step,
    _workflow,
)


class _DenyGovernance:
    """Governance service that denies everything."""

    async def can_perform_action_async(
        self, agent_id, action_type, require_approval=False, chain_id=None
    ):
        return {"allowed": False, "reason": "denied by policy"}


class _AllowGovernance:
    """Governance service that allows everything."""

    async def can_perform_action_async(
        self, agent_id, action_type, require_approval=False, chain_id=None
    ):
        return {"allowed": True, "reason": "ok"}


class _FakeFactory:
    def __init__(self, governance):
        self._gov = governance

    def get_governance_service(self, db, tenant_id="default"):
        return self._gov


def _run(engine, wf, agent_id):
    async def _go():
        eid = await engine.state_manager.create_execution(wf["id"], {})
        await engine._run_execution(eid, {**wf, "agent_id": agent_id})
        state = await engine.state_manager.get_execution_state(eid)
        return state

    return asyncio.run(_go())


@pytest.fixture
def env(monkeypatch):
    sm = FakeStateManager()
    ws = FakeWSManager()
    analytics = FakeAnalytics()
    monkeypatch.setattr("core.workflow_engine.get_state_manager", lambda: sm)
    monkeypatch.setattr("core.workflow_engine.get_connection_manager", lambda: ws)
    monkeypatch.setattr("core.analytics_engine.get_analytics_engine", lambda: analytics)
    return sm


def _patch_registry_lookup(monkeypatch, agent_record):
    """Make the interlock's AgentRegistry lookup return a record."""
    import contextlib
    from unittest.mock import MagicMock

    @contextlib.contextmanager
    def _cm():
        db = MagicMock()
        query = MagicMock()
        query.filter.return_value = query
        query.first.return_value = agent_record
        db.query.return_value = query
        yield db

    monkeypatch.setattr("core.workflow_engine.get_db_session", _cm)


def _registry_agent(agent_id="agent-1"):
    from types import SimpleNamespace

    return SimpleNamespace(id=agent_id)


def test_governance_denial_blocks_linear_step(monkeypatch, env):
    """A denial from the governance service must FAIL the step, not fail open."""
    from core.workflow_engine import WorkflowEngine

    _patch_registry_lookup(monkeypatch, _registry_agent())
    monkeypatch.setattr("core.workflow_engine.ServiceFactory", _FakeFactory(_DenyGovernance()))
    engine = WorkflowEngine()
    wf = _workflow([_step("s1", service="email", action="send")])

    state = _run(engine, wf, agent_id="agent-1")

    assert state["status"] == "FAILED", state
    assert state["steps"]["s1"]["status"] == "FAILED"
    assert "Governance" in (state["steps"]["s1"].get("error") or "")


def test_governance_allow_proceeds_with_registered_agent(monkeypatch, env):
    """An allow from the governance service must let the step execute."""
    from core.workflow_engine import WorkflowEngine

    _patch_registry_lookup(monkeypatch, _registry_agent())
    monkeypatch.setattr("core.workflow_engine.ServiceFactory", _FakeFactory(_AllowGovernance()))
    engine = WorkflowEngine()
    wf = _workflow([_step("s1", service="email", action="send")])

    state = _run(engine, wf, agent_id="agent-1")

    assert state["status"] != "FAILED"
    assert state["steps"]["s1"]["status"] not in ("FAILED",)


def test_system_agent_workflow_not_governed(monkeypatch, env):
    """Unbound system_agent workflows must NOT be blocked by governance."""
    from core.workflow_engine import WorkflowEngine

    monkeypatch.setattr("core.workflow_engine.ServiceFactory", _FakeFactory(_DenyGovernance()))
    engine = WorkflowEngine()
    wf = _workflow([_step("s1", service="email", action="send")])

    state = _run(engine, wf, agent_id="system_agent")

    assert state["steps"]["s1"]["status"] not in ("FAILED",)
