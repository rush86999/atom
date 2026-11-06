"""ORCH-02 controlled response-consumption proof for recruited specialists.

The enforced AtomMetaAgent TASK path must execute the recruited roster through
the shared GenericAgent/BYOK path and return a response that cites their actual
work. A recruitment list, a shadow calculation or an audit row alone is not a
pass. Missing/foreign/wrong-capability specialists, failures, cancellation,
duplicate continuation and no-suitable rosters are explicit.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.models import AgentRegistry, DelegationChain
from tests.test_orch07_fleet_audit_consumer import (  # noqa: F401 — fixture
    REQUEST,
    TENANT,
    WORKSPACE,
    _summary,
    env,
)


class FakeSpecialist:
    calls = []
    behavior = {}

    def __init__(self, agent_model, workspace_id="default", **kwargs):
        self.agent = agent_model
        self.workspace_id = workspace_id

    async def execute(self, task_input, context=None, step_callback=None):
        FakeSpecialist.calls.append({
            "agent_id": self.agent.id,
            "task_input": task_input,
            "context": context or {},
        })
        mode = FakeSpecialist.behavior.get(self.agent.id, "success")
        if mode == "raise":
            raise RuntimeError("specialist transport failed")
        if mode == "fail":
            return {"success": False, "error": "specialist returned failure"}
        return {
            "success": True,
            "final_output": (
                f"{self.agent.name} finding for {self.agent.id}: "
                f"concrete contribution"
            ),
        }


@pytest.fixture(autouse=True)
def _fake_specialist(monkeypatch):
    FakeSpecialist.calls = []
    FakeSpecialist.behavior = {}
    monkeypatch.setattr(
        "core.generic_agent.GenericAgent", FakeSpecialist)
    yield


def _seed_fleet(
    env, *, a1_tenant=TENANT, a1_workspace=WORKSPACE,
    a1_caps=("sales",), a2_tenant=TENANT, a2_workspace=WORKSPACE,
    a2_caps=("analysis",),
):
    db = env.Session()
    try:
        db.add(DelegationChain(
            id="chain-controlled", tenant_id=TENANT,
            root_agent_id="atom_main", root_task=REQUEST,
            status="active"))
        db.add_all([
            AgentRegistry(
                id="a1", name="Analyst", display_name="Analyst",
                category="Sales", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=a1_tenant,
                workspace_id=a1_workspace, status="intern", enabled=True,
                capabilities=list(a1_caps), specialty=a1_caps[0] if a1_caps else None),
            AgentRegistry(
                id="a2", name="Reviewer", display_name="Reviewer",
                category="Analysis", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=a2_tenant,
                workspace_id=a2_workspace, status="intern", enabled=True,
                capabilities=list(a2_caps), specialty=a2_caps[0] if a2_caps else None),
        ])
        db.commit()
    finally:
        db.close()


def _audit(env, execution_id):
    return env.row_for(execution_id)


def test_enforced_response_consumes_specialist_work(env):
    _seed_fleet(env)
    result = env.run(enforced=True)
    assert result["success"] is True
    assert result["status"] == "specialists_executed"
    assert result["enforced"] is True
    assert result["failure_reason"] is None
    assert result["specialists_count"] == 2
    assert len(result["specialist_results"]) == 2
    assert "Specialist contributions" in result["final_output"]
    assert "Analyst" in result["final_output"]
    assert "Reviewer" in result["final_output"]
    assert "concrete contribution" in result["final_output"]
    assert len(FakeSpecialist.calls) == 2
    assert all(REQUEST in call["task_input"] for call in FakeSpecialist.calls)
    assert all(call["context"]["chain_id"] == "chain-controlled"
               for call in FakeSpecialist.calls)

    row = _audit(env, result["execution_id"])
    assert row.enforced is True
    assert row.success is True
    assert row.error is None
    assert row.actual_model == "controlled-model"
    assert row.actual_provider == "controlled-provider"

    db = env.Session()
    try:
        chain = db.query(DelegationChain).filter(
            DelegationChain.id == "chain-controlled").one()
        assert chain.status == "completed"
        assert chain.metadata_json["specialist_execution"]["status"] == (
            "completed")
    finally:
        db.close()


def test_partial_success_preserves_failed_specialist(env):
    _seed_fleet(env)
    FakeSpecialist.behavior = {"a2": "fail"}
    result = env.run(enforced=True)
    assert result["success"] is True
    assert result["status"] == "specialists_executed"
    assert result["failure_reason"] is None
    assert "Analyst finding" in result["final_output"]
    assert "Not completed" in result["final_output"]
    assert "Reviewer" in result["final_output"]
    statuses = {item["agent_id"]: item["status"]
                for item in result["specialist_results"]}
    assert statuses == {"a1": "success", "a2": "failed"}
    assert _audit(env, result["execution_id"]).success is True


def test_all_failed_is_explicit_non_success(env):
    _seed_fleet(env)
    FakeSpecialist.behavior = {"a1": "fail", "a2": "raise"}
    result = env.run(enforced=True)
    assert result["success"] is False
    assert result["status"] == "specialists_failed"
    assert result["failure_reason"] == "fleet_specialists_failed"
    assert "could not complete" in result["final_output"]
    assert "Analyst finding" not in result["final_output"]
    assert len(FakeSpecialist.calls) == 2
    row = _audit(env, result["execution_id"])
    assert row.success is False
    assert row.error == "all_recruited_specialists_failed"


def test_missing_or_foreign_specialist_is_no_suitable(env):
    _seed_fleet(env, a1_tenant="tenant-2", a2_workspace="workspace-2")
    result = env.run(enforced=True)
    assert result["success"] is False
    assert result["status"] == "no_suitable_specialists"
    assert result["failure_reason"] == "fleet_no_suitable_specialist"
    assert "No suitable specialist" in result["final_output"]
    assert FakeSpecialist.calls == []
    statuses = {item["agent_id"]: item["status"]
                for item in result["specialist_results"]}
    assert statuses == {"a1": "scope_mismatch", "a2": "scope_mismatch"}
    row = _audit(env, result["execution_id"])
    assert row.success is False
    assert row.error == "no_suitable_specialist_available"


def test_wrong_capability_is_not_dispatched(env):
    _seed_fleet(env, a1_caps=("finance",))
    result = env.run(enforced=True)
    assert result["success"] is True
    assert [call["agent_id"] for call in FakeSpecialist.calls] == ["a2"]
    statuses = {item["agent_id"]: item["status"]
                for item in result["specialist_results"]}
    assert statuses["a1"] == "capability_mismatch"
    assert statuses["a2"] == "success"
    assert "Not completed" in result["final_output"]
    assert "capability_mismatch" in result["final_output"]


def test_disabled_specialist_is_not_dispatched(env):
    _seed_fleet(env)
    db = env.Session()
    try:
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "a1").one()
        agent.enabled = False
        db.commit()
    finally:
        db.close()
    result = env.run(enforced=True)
    assert result["success"] is True
    assert [call["agent_id"] for call in FakeSpecialist.calls] == ["a2"]
    statuses = {item["agent_id"]: item["status"]
                for item in result["specialist_results"]}
    assert statuses["a1"] == "unavailable"
    assert "specialist_disabled" in result["final_output"]


def test_cancellation_stops_before_next_specialist(env):
    _seed_fleet(env)
    result = env.run(
        enforced=True,
        context={"fleet_cancel_check": lambda: len(FakeSpecialist.calls) >= 1},
    )
    assert result["success"] is False
    assert result["status"] == "cancelled"
    assert result["failure_reason"] == "fleet_cancelled"
    assert result["result"]["cancelled"] is True
    assert len(FakeSpecialist.calls) == 1
    assert "cancelled" in result["final_output"].lower()
    assert "Analyst finding" in result["final_output"]
    row = _audit(env, result["execution_id"])
    assert row.success is False
    assert row.error == "fleet_specialist_execution_cancelled"


def test_duplicate_continuation_uses_cached_result(env):
    _seed_fleet(env)
    first = env.run(enforced=True)
    assert first["success"] is True
    assert first["result"].get("cached") is False
    assert len(FakeSpecialist.calls) == 2
    second = env.run(enforced=True)
    assert second["success"] is True
    assert second["result"].get("cached") is True
    assert len(FakeSpecialist.calls) == 2
    assert second["final_output"] == first["final_output"]


def test_chat_handler_returns_specialist_work_as_user_message(env):
    _seed_fleet(env)
    from integrations.chat_orchestrator import ChatOrchestrator

    orchestrator = object.__new__(ChatOrchestrator)
    orchestrator._emit_agent_step = AsyncMock()
    orchestrator._emit_agent_status = AsyncMock()
    env.monkeypatch.setattr(
        "core.atom_meta_agent.get_atom_agent", lambda: env.agent)
    env.monkeypatch.setattr(
        "core.fleet_orchestration.fleet_router_automation.resolved_fleet_enforce",
        lambda db=None: True)
    env.agent.route_with_governance = AsyncMock(return_value=_summary())
    response = asyncio.run(orchestrator._handle_agent_request(
        REQUEST, {"intent": "TASK"}, {"id": "session-1", "user_id": "user-1"},
        {}))
    assert response["success"] is True
    assert response["status"] == "success"
    assert "Specialist contributions" in response["message"]
    assert "Analyst finding" in response["message"]
    assert "Reviewer finding" in response["message"]
    assert len(FakeSpecialist.calls) == 2


def test_empty_roster_is_explicit_no_suitable(env):
    _seed_fleet(env)
    result = env.run(enforced=True, summary=_summary(count=0))
    assert result["success"] is False
    assert result["status"] == "no_suitable_specialists"
    assert result["failure_reason"] == "fleet_no_suitable_specialist"
    assert FakeSpecialist.calls == []
    row = _audit(env, result["execution_id"])
    assert row.success is False
