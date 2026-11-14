"""Ordinary GenericAgent tool dispatch for approved executable skills.

The lifecycle/authorization control lives in
``test_reviewed_executable_skill.py`` and the defensive binding checks in
``test_reviewed_executable_agent_consumption.py``.  This control closes the
remaining product gap: an approved artifact must be discoverable and callable
through the normal agent tool surface, without a caller invoking
``POST /api/skills/execute``.

What is real here:

* approve + apply through the real ``/api/autodev`` routes;
* the real ``core.action_registry`` actions (``skills.list`` /
  ``skills.execute``) and the real ``integrations.mcp_service.call_tool``
  dispatch that the GenericAgent loop uses;
* the real ``GenericAgent._step_act`` governance + dispatch wrapper;
* the real ``SkillRegistryService`` authorization and durable receipts in a
  fresh DB session.

Simulated (stated limit): the Docker sandbox is the deterministic in-process
stand-in already used by the executable controls (same registered wrapper and
nonce echo).  The real container lane is ``test_reviewed_executable_skill_docker.py``.
No provider/network is contacted, and the LLM security scanner is stubbed.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from core.models import AgentRegistry, SkillExecution
from core.reviewed_executable import registered_executable_code
from tests.test_reviewed_improvement_apply import env as _reviewed_env  # noqa: F401
from tests.test_reviewed_executable_skill import (  # noqa: F401
    EXPECTED_RESULT,
    SYNTHETIC_INPUTS,
    _FakeDockerSandbox,
    _approve_and_apply,
    _execution_row,
    _pending_candidate,
    review_env,
)

REQUEST = "deterministically summarize a list of integers"


class _TripwireSandbox:
    """Authorization must refuse before this leaf is constructed or called."""

    calls = []

    def __init__(self):
        self.calls = _TripwireSandbox.calls

    def execute_python(self, code, inputs):
        self.calls.append(("execute_python", code))
        raise AssertionError("generic python path reached for a refused skill")

    def execute_python_receipt(self, code, inputs, **kwargs):
        self.calls.append(("execute_python_receipt", code))
        raise AssertionError("sandbox reached for a refused skill")


@pytest.fixture(autouse=True)
def _reset_tripwire():
    _TripwireSandbox.calls = []
    yield


def _patch_db(monkeypatch, env):
    """Point every dispatch-side session factory at the scratch engine."""
    monkeypatch.setattr("core.database.get_db_session", env["factory"])
    # generic_agent imports the symbol at module scope; the governance check
    # and several dispatch helpers use that binding.
    monkeypatch.setattr("core.generic_agent.get_db_session", env["factory"])


def _fresh_agent(env, db):
    from core.generic_agent import GenericAgent

    row = db.query(AgentRegistry).filter(
        AgentRegistry.id == env["agent"].id).one()
    agent = GenericAgent(row, workspace_id=env["workspace"].id)
    agent.tenant_id = env["tenant"].id
    return agent


def _context(env):
    return {"user_id": env["user"].id}


def test_approved_skill_is_discoverable_in_the_normal_tool_surface(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env)
    _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    from core.action_registry import action_registry
    from core.generic_agent import GenericAgent

    assert action_registry.get_action("skills.list") is not None
    assert action_registry.get_action("skills.execute") is not None
    assert "skills.list" in GenericAgent.CORE_TOOLS_NAMES
    assert "skills.execute" in GenericAgent.CORE_TOOLS_NAMES

    fresh = review_env["factory"]()
    try:
        agent = _fresh_agent(review_env, fresh)
        block = agent._retrieve_skill_instructions(REQUEST)
        assert candidate.skill_name in block
        assert "skills.execute" in block
        # Generated code never reaches the prompt.
        assert "def execute" not in block
        assert "atom reviewed executable harness" not in block

        workspace_block = agent._workspace_context_block()
        assert "WORKSPACE EXECUTABLE SKILLS" in workspace_block
        assert f"{candidate.skill_name}_r1" in workspace_block
    finally:
        fresh.close()


def test_react_prompt_advertises_the_skill_dispatch_tool(
        review_env, monkeypatch):
    """The model sees both the executable tool and the approved skill name."""
    from core.react_models import ReActStep

    candidate = _pending_candidate(review_env)
    _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    fresh = review_env["factory"]()
    try:
        agent = _fresh_agent(review_env, fresh)
        captured = {}

        async def capture_structured(**kwargs):
            captured.update(kwargs)
            return ReActStep(thought="pin", final_answer="PIN")

        monkeypatch.setattr(agent.llm, "generate_structured", capture_structured)
        step = asyncio.run(agent._react_step(
            REQUEST, memory={}, history="", context={}))
        assert step.final_answer == "PIN"

        system = str(captured.get("system_instruction") or "")
        assert "skills.execute" in system
        assert candidate.skill_name in system
        assert "def execute" not in system
        assert "atom reviewed executable harness" not in system
    finally:
        fresh.close()


def test_approved_skill_runs_through_generic_agent_dispatch(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env)
    _approved, applied = _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)

    fresh = review_env["factory"]()
    try:
        agent = _fresh_agent(review_env, fresh)
        result = asyncio.run(agent._step_act(
            "skills.execute",
            {"skill": candidate.skill_name, "inputs": SYNTHETIC_INPUTS},
            _context(review_env),
        ))

        assert isinstance(result, dict), result
        assert result["success"] is True, result
        assert json.loads(result["result"]) == EXPECTED_RESULT
        assert result["skill"] == f"{candidate.skill_name}_r1"
        assert len(fake_sandbox.calls) == 1
        assert fake_sandbox.calls[0]["code"] == registered_executable_code(
            candidate.generated_code)

        execution = _execution_row(fresh, result["execution_id"])
        assert execution.status == "success"
        assert execution.skill_id == applied["skill_id"]
        assert execution.tenant_id == review_env["tenant"].id
        assert execution.workspace_id == review_env["workspace"].id
        receipt = execution.audit_metadata["reviewed_executable"]
        assert receipt["status"] == "success"
        assert receipt["binding"]["verified"] is True
        assert receipt["binding"]["review_digest"] == applied["review_digest"]
        assert receipt["sandbox"]["nonce"] == receipt["sandbox"]["nonce_echo"]
        assert receipt["executed_by"] == review_env["user"].id
    finally:
        fresh.close()


def test_skills_list_reports_only_the_approved_artifact(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env)
    _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    from core.action_registry import action_registry

    result = asyncio.run(action_registry.execute_action(
        "skills.list", {},
        {"_skill_scope": {
            "tenant_id": review_env["tenant"].id,
            "workspace_id": review_env["workspace"].id,
            "agent_id": review_env["agent"].id,
            "user_id": review_env["user"].id,
        }},
    ))
    assert result["success"] is True, result
    assert result["count"] == 1, result
    entry = result["skills"][0]
    assert entry["name"] == f"{candidate.skill_name}_r1"
    assert entry["registry_name"] == candidate.skill_name
    assert entry["tool"] == "skills.execute"
    assert "def execute" not in json.dumps(entry)

    from core.skill_registry_service import SkillRegistryService

    service = SkillRegistryService(review_env["db"])
    scope = {
        "tenant_id": review_env["tenant"].id,
        "workspace_id": review_env["workspace"].id,
        "agent_id": review_env["agent"].id,
    }
    assert service.resolve_invocable_skill(entry["name"], **scope)
    assert service.resolve_invocable_skill(entry["registry_name"], **scope)
    assert service.resolve_invocable_skill("not-approved", **scope) is None


def test_changed_candidate_is_refused_before_the_sandbox(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="changed_candidate")
    _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    # The artifact is still advertised by its binding, but the reviewed
    # material no longer matches: authorization must fail before Docker.
    candidate.generated_code = candidate.generated_code + "\n# changed\n"
    review_env["db"].commit()
    before = review_env["db"].query(SkillExecution).count()

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    fresh = review_env["factory"]()
    try:
        agent = _fresh_agent(review_env, fresh)
        result = asyncio.run(agent._step_act(
            "skills.execute",
            {"skill": candidate.skill_name, "inputs": SYNTHETIC_INPUTS},
            _context(review_env),
        ))
        assert result["success"] is False, result
        assert result["blocked_by"] == "skill_authorization"
        assert "reviewed_executable_artifact_changed" in result["error"]
        assert _TripwireSandbox.calls == []
        assert fresh.query(SkillExecution).count() == before
    finally:
        fresh.close()


def test_binding_removed_skill_is_not_advertised_or_invocable(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="binding_removed_dispatch")
    _approved, applied = _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    db = review_env["db"]
    execution = _execution_row(db, applied["registry_execution_id"])
    params = json.loads(json.dumps(execution.input_params))
    params.pop("reviewed_executable", None)
    execution.input_params = params
    db.commit()
    before = db.query(SkillExecution).count()

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    from core.action_registry import action_registry

    scope = {"_skill_scope": {
        "tenant_id": review_env["tenant"].id,
        "workspace_id": review_env["workspace"].id,
        "agent_id": review_env["agent"].id,
        "user_id": review_env["user"].id,
    }}
    listed = asyncio.run(action_registry.execute_action("skills.list", {}, scope))
    assert listed["success"] is True
    assert listed["skills"] == []

    refused = asyncio.run(action_registry.execute_action(
        "skills.execute",
        {"skill": candidate.skill_name, "inputs": SYNTHETIC_INPUTS},
        scope,
    ))
    assert refused["success"] is False
    assert refused["blocked_by"] == "skill_authorization"
    assert "skills_execute_not_available" in refused["error"]
    assert _TripwireSandbox.calls == []
    assert db.query(SkillExecution).count() == before


def test_another_workspace_cannot_see_or_run_the_approved_skill(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env)
    _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    from core.action_registry import action_registry
    from core.models import Workspace

    other = Workspace(
        id="other-dispatch-workspace", name="Other",
        tenant_id=review_env["tenant"].id)
    review_env["db"].add(other)
    review_env["db"].commit()

    scope = {"_skill_scope": {
        "tenant_id": review_env["tenant"].id,
        "workspace_id": other.id,
        "agent_id": review_env["agent"].id,
        "user_id": review_env["user"].id,
    }}
    listed = asyncio.run(action_registry.execute_action("skills.list", {}, scope))
    assert listed["success"] is True
    assert listed["skills"] == []

    refused = asyncio.run(action_registry.execute_action(
        "skills.execute",
        {"skill": candidate.skill_name, "inputs": SYNTHETIC_INPUTS},
        scope,
    ))
    assert refused["success"] is False
    assert refused["blocked_by"] == "skill_authorization"
    assert _TripwireSandbox.calls == []


def test_unreviewed_community_skill_has_no_executable_dispatch_path(
        review_env, monkeypatch):
    _patch_db(monkeypatch, review_env)
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    db = review_env["db"]
    db.add(SkillExecution(
        id="community-unreviewed",
        agent_id=review_env["agent"].id,
        tenant_id=review_env["tenant"].id,
        workspace_id=review_env["workspace"].id,
        skill_id="community-unreviewed-skill",
        status="Active",
        input_params={
            "skill_name": "unreviewed_compute",
            "skill_type": "python_code",
            "skill_body": "def execute(inputs):\n    return 1\n",
            "skill_metadata": {"description": "not reviewed"},
        },
        skill_source="community",
        sandbox_enabled=True,
    ))
    db.commit()

    from core.action_registry import action_registry

    scope = {"_skill_scope": {
        "tenant_id": review_env["tenant"].id,
        "workspace_id": review_env["workspace"].id,
        "agent_id": review_env["agent"].id,
        "user_id": review_env["user"].id,
    }}
    listed = asyncio.run(action_registry.execute_action("skills.list", {}, scope))
    assert listed["skills"] == []

    refused = asyncio.run(action_registry.execute_action(
        "skills.execute",
        {"skill": "unreviewed_compute", "inputs": {}},
        scope,
    ))
    assert refused["success"] is False
    assert "skills_execute_not_available" in refused["error"]
    assert _TripwireSandbox.calls == []


def test_manual_rpc_style_scope_cannot_execute_skills():
    from core.action_registry import action_registry

    result = asyncio.run(action_registry.execute_action(
        "skills.execute",
        {"skill": "anything", "inputs": {}},
        {"user_id": "human-reviewer"},
    ))
    assert result["success"] is False
    assert result["blocked_by"] == "skill_scope"
