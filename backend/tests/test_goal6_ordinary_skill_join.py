"""GOAL-6 joined public boundary: ordinary agent -> qualification -> skill loop.

Creation, qualification review/approval and promotion use the real public
FastAPI routes from the existing positive control. After a fresh session the
same promoted agent is the exact scope for an approved reviewed executable
skill, consumed through the NORMAL ``GenericAgent.execute`` loop. Unapproved
and foreign-scope twins must be denied before the sandbox.

Controlled limits: training evidence is synthetic scratch data; model decision,
scanner and Docker are deterministic test doubles; no live model/network/owner
data and no learned-capability/quality/UI claim.
"""
from __future__ import annotations

import asyncio
import json

from core.models import (
    AgentRegistry, SkillExecution, Tenant, User, Workspace,
)
from core.reviewed_executable import registered_executable_code
from tests.test_goal6_ordinary_creation_positive import (
    ADMIN, COMPANY, SUPERVISOR, WS_A, World, add_evidence, approve,
    create_agent, promote, request_review,
)
from tests.test_reviewed_executable_skill_agent_dispatch import (
    REQUEST, SYNTHETIC_INPUTS, _FakeDockerSandbox, _ReflectionStub,
    _SimulatedDecisionModel, _TripwireSandbox, _WorldModelStub,
    _execution_row, _fresh_agent, _patch_db, _patch_full_run, _scope,
)
from tests.test_reviewed_executable_skill import (
    _FakeScanner, _approve_and_apply, _pending_candidate,
)


def _ordinary_promoted_scope(world, tmp_path):
    client = world.client()
    admin = world.token(ADMIN)
    sup = world.token(SUPERVISOR)
    created = create_agent(client, admin)
    assert created["status"] == 201, created
    agent_id = created["json"]["data"]["agent_id"]
    add_evidence(world, agent_id)

    requested = request_review(client, sup, agent_id, [
        {"kind": "agent_episode", "id": f"goal6-ep-{agent_id[:8]}-00"},
        {"kind": "agent_execution", "id": f"goal6-exec-{agent_id[:8]}-00"},
    ])
    assert requested["status"] == 200, requested
    assert approve(client, admin, requested["json"]["data"]["action_id"])[
        "status"] == 200
    promoted = promote(client, sup, agent_id)
    assert promoted["status"] == 200, promoted
    assert promoted["json"]["data"]["promoted"] is True

    db = world.Session()
    return {
        "db": db, "factory": world.Session, "engine": world.engine,
        "tenant": db.query(Tenant).filter_by(id=COMPANY).one(),
        "workspace": db.query(Workspace).filter_by(id=WS_A).one(),
        "agent": db.get(AgentRegistry, agent_id),
        "user": db.get(User, ADMIN), "tmp_path": tmp_path,
        "agent_id": agent_id,
    }


def test_ordinary_promoted_agent_consumes_approved_skill_via_generic_execute(
        tmp_path, monkeypatch):
    world = World(tmp_path, episodes=0)
    env = _ordinary_promoted_scope(world, tmp_path)
    skills_root = tmp_path / "reviewed-goal6-skills"
    monkeypatch.setenv("ATOM_WORKSPACE_SKILLS_ROOT", str(skills_root))
    monkeypatch.setattr(
        "core.skill_registry_service.SkillSecurityScanner", _FakeScanner)

    candidate = _pending_candidate(env)
    _approved, applied = _approve_and_apply(env, candidate)
    _patch_full_run(monkeypatch, env)

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)
    _TripwireSandbox.calls = []

    before = env["db"].query(SkillExecution).count()
    fresh = env["factory"]()
    try:
        agent = _fresh_agent(env, fresh)
        model = _SimulatedDecisionModel(candidate.skill_name)
        agent.llm = model
        agent.world_model = _WorldModelStub()
        agent.reflection_service = _ReflectionStub()
        result = asyncio.run(agent.execute(
            REQUEST, context={"user_id": env["user"].id}))
    finally:
        fresh.close()

    assert result["status"] == "success", result
    assert len(model.calls) == 2
    assert len(result["steps"]) == 2
    tool_step = result["steps"][0]
    assert tool_step["action"]["tool"] == "skills.execute"
    assert tool_step["dispatch_evidence"]["dispatched"] is True
    observation = tool_step["output"]
    assert observation["success"] is True, observation
    assert observation["skill"] == f"{candidate.skill_name}_r1"
    assert observation["execution_id"]
    assert "Approved executable skill completed." in result["output"]
    assert "count=4" in result["output"]
    assert "maximum=11" in result["output"]
    assert "sum=26" in result["output"]
    assert len(fake_sandbox.calls) == 1
    assert fake_sandbox.calls[0]["code"] == registered_executable_code(
        candidate.generated_code)

    verify = env["factory"]()
    try:
        assert verify.query(SkillExecution).count() == before + 1
        execution = _execution_row(verify, observation["execution_id"])
        assert execution.status == "success"
        assert execution.agent_id == env["agent_id"]
        assert execution.skill_id == applied["skill_id"]
        assert execution.tenant_id == COMPANY
        assert execution.workspace_id == WS_A
        assert execution.output_result["result"] == observation["result"]
        receipt = execution.audit_metadata["reviewed_executable"]
        assert receipt["status"] == "success"
        assert receipt["binding"]["verified"] is True
        assert receipt["binding"]["review_revision"] == applied["review_revision"]
        assert receipt["binding"]["review_digest"] == applied["review_digest"]
        assert receipt["binding"]["executable_code_sha256"] == (
            applied["executable_code_sha256"])
        assert receipt["binding"]["candidate_code_sha256"] == (
            applied["candidate_code_sha256"])
        assert receipt["binding"]["registry_execution_id"] == (
            applied["registry_execution_id"])
        assert receipt["sandbox"]["nonce"] == receipt["sandbox"]["nonce_echo"]
        assert receipt["executed_by"] == env["user"].id
    finally:
        verify.close()

    # Unapproved twin: same created agent, candidate not approved/applied.
    unapproved = _pending_candidate(env, name="goal6_unapproved")
    _patch_db(monkeypatch, env)
    from core.action_registry import action_registry
    listed = asyncio.run(action_registry.execute_action(
        "skills.list", {}, _scope(env)))
    assert listed["success"] is True
    assert unapproved.skill_name not in json.dumps(listed)
    assert listed["skills"] == [next(
        item for item in listed["skills"]
        if item["name"] == f"{candidate.skill_name}_r1")]

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)
    refused = asyncio.run(action_registry.execute_action(
        "skills.execute",
        {"skill": unapproved.skill_name, "inputs": SYNTHETIC_INPUTS},
        _scope(env)))
    assert refused["success"] is False, refused
    assert refused["blocked_by"] == "skill_authorization"
    assert _TripwireSandbox.calls == []

    # Foreign-scope twin: approved skill is not invocable for another agent id.
    foreign = asyncio.run(action_registry.execute_action(
        "skills.execute",
        {"skill": candidate.skill_name, "inputs": SYNTHETIC_INPUTS},
        _scope(env, agent_id="foreign-agent")))
    assert foreign["success"] is False, foreign
    assert foreign["blocked_by"] == "skill_authorization"
    assert _TripwireSandbox.calls == []
    env["db"].close()


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    import pytest

    with tempfile.TemporaryDirectory(prefix="goal6-skill-") as td:
        with pytest.MonkeyPatch.context() as mp:
            test_ordinary_promoted_agent_consumes_approved_skill_via_generic_execute(
                Path(td), mp)
    print("GOAL6_SKILL_PASS")
