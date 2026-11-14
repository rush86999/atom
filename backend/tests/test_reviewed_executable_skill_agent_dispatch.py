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
* one joined ordinary public ``GenericAgent.execute`` run: a deterministic
  model-decision stub selects ``skills.execute``, the real loop dispatches it,
  the next decision answers from the actual tool observation, and a fresh
  session re-reads the durable exact receipt;
* the real ``SkillRegistryService`` authorization and durable receipts in a
  fresh DB session.

Simulated (stated limit): the model decision is a deterministic stub, not a
live-model competence claim; the Docker sandbox is the deterministic
in-process stand-in already used by the executable controls (same registered
wrapper and nonce echo). The real-container twin is
``test_reviewed_executable_skill_agent_dispatch_docker.py``. No provider/network
is contacted, and the LLM security scanner is stubbed.
"""
from __future__ import annotations

import asyncio
import ast
import json
from types import SimpleNamespace

import pytest

from core.models import AgentRegistry, SkillExecution
from core.react_models import ReActStep, ToolCall
from core.reviewed_executable import registered_executable_code
from tests.test_reviewed_improvement_apply import env as _reviewed_env  # noqa: F401
from tests.test_reviewed_executable_skill import (  # noqa: F401
    BENIGN_CODE,
    EXPECTED_RESULT,
    SYNTHETIC_INPUTS,
    _FakeDockerSandbox,
    _approve_and_apply,
    _execution_row,
    _pending_candidate,
    review_env,
)

REQUEST = "deterministically summarize a list of integers"


class _WorldModelStub:
    """Only the memory legs the public run needs; no DB/network."""

    def __init__(self):
        self.experiences = []

    async def recall_experiences(self, **_kwargs):
        return {}

    async def record_experience(self, experience):
        self.experiences.append(experience)


class _ReflectionStub:
    async def get_relevant_critiques(self, **_kwargs):
        return []

    async def add_critique(self, **_kwargs):
        return None


class _SimulatedDecisionModel:
    """Deterministic test double for the model decision step.

    This is a simulated decision model, not a live-model competence claim. It
    is given the exact ordinary ReAct prompts the agent builds: call 1 selects
    the advertised ``skills.execute`` tool; call 2 must parse the ACTUAL tool
    observation out of the execution history and answer from those values.
    """

    def __init__(self, skill_name):
        self.skill_name = skill_name
        self.calls = []
        self._handler = SimpleNamespace(
            analyze_query_complexity=lambda _query: SimpleNamespace(
                value="simple"))

    def _get_handler(self):
        return self._handler

    async def generate_structured(self, **kwargs):
        prompt = str(kwargs.get("prompt") or "")
        system = str(kwargs.get("system_instruction") or "")
        self.calls.append({"prompt": prompt, "system": system})

        if len(self.calls) == 1:
            assert "skills.execute" in system
            assert self.skill_name in system
            assert "def execute" not in system
            assert "atom reviewed executable harness" not in system
            assert "Observation:" not in prompt
            return ReActStep(
                thought="Use the approved executable skill for this request.",
                action=ToolCall(
                    tool="skills.execute",
                    params={
                        "skill": self.skill_name,
                        "inputs": SYNTHETIC_INPUTS,
                    },
                ),
            )

        assert len(self.calls) == 2, self.calls
        observation = _observation_from_prompt(prompt)
        assert observation["success"] is True, observation
        result = json.loads(observation["result"])
        assert result == EXPECTED_RESULT, result
        execution_id = str(observation["execution_id"])
        return ReActStep(
            thought="The tool observation carries the computed result.",
            final_answer=(
                "Approved executable skill completed. "
                f"count={result['count']}, maximum={result['maximum']}, "
                f"sum={result['sum']} (execution_id={execution_id})."
            ),
        )

    async def generate(self, **kwargs):
        raise AssertionError(f"unexpected raw LLM fallback: {kwargs}")


def _observation_from_prompt(prompt: str) -> dict:
    """Parse the actual observation line the loop appended to history."""
    marker = prompt.rfind("Observation: ")
    assert marker >= 0, prompt[-2000:]
    line = prompt[marker + len("Observation: "):].splitlines()[0].strip()
    try:
        observation = ast.literal_eval(line)
    except Exception as exc:  # noqa: BLE001 - surfaced in the run result
        raise AssertionError(
            f"observation line is not a literal: {exc}: {line[:2000]}"
        ) from exc
    assert isinstance(observation, dict), observation
    return observation


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


def _patch_full_run(monkeypatch, env):
    """Isolate the ordinary ``GenericAgent.execute`` run from live services.

    The DB session factories are redirected to the scratch engine; optional
    background legs (budget spend aggregation, BPE workspace persistence,
    turn-fact extraction) are disabled. The tool registry, governance and
    dispatch path remain real.
    """
    from core.generic_agent import GenericAgent

    _patch_db(monkeypatch, env)
    monkeypatch.setattr("core.database.SessionLocal", env["factory"])
    monkeypatch.setattr("core.generic_agent.SessionLocal", env["factory"])
    monkeypatch.setattr(
        "core.bpe.actions.bpe_enabled", lambda: False)
    try:
        import core.turn_fact_extractor as turn_fact_extractor

        monkeypatch.setattr(
            turn_fact_extractor, "TURN_FACT_EXTRACTION_ENABLED", False,
            raising=False)
        monkeypatch.setattr(
            turn_fact_extractor, "TURN_FACT_VECTOR_RECALL_ENABLED", False,
            raising=False)
    except Exception:  # noqa: BLE001 - optional module
        pass

    async def _budget_allowed(_self):
        return {"allowed": True, "reason": "test-budget"}

    monkeypatch.setattr(
        GenericAgent, "_check_budget_before_react", _budget_allowed)


def _scope(env, *, tenant_id=None, workspace_id=None, agent_id=None):
    return {"_skill_scope": {
        "tenant_id": tenant_id or env["tenant"].id,
        "workspace_id": workspace_id or env["workspace"].id,
        "agent_id": agent_id or env["agent"].id,
        "user_id": env["user"].id,
    }}


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


def test_intern_dispatch_surface_admits_skill_actions(review_env):
    """P9 tier floor must admit the actions the intern loop advertises."""
    from core.capability_resolver import build_dispatch_tool_predicate

    intern_predicate = build_dispatch_tool_predicate(
        review_env["agent"], tier="intern")
    assert intern_predicate("skills.list") is True
    assert intern_predicate("skills.execute") is True

    student_predicate = build_dispatch_tool_predicate(
        review_env["agent"], tier="student")
    assert student_predicate("skills.list") is True
    assert student_predicate("skills.execute") is False


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


def test_one_ordinary_agent_run_selects_executes_and_answers_from_result(
        review_env, monkeypatch):
    """Joined normal loop: decision -> real dispatch -> result -> grounded answer.

    The model is explicitly SIMULATED (deterministic decision stub). Everything
    else is the ordinary public ``GenericAgent.execute`` path: the real ReAct
    loop, action registry/MCP dispatch, governance, SkillRegistryService
    authorization and durable receipt. The second decision parses the actual
    observation out of the prompt history, so the final answer is grounded in
    the tool result rather than in the test's expected constant.
    """
    candidate = _pending_candidate(review_env)
    _approved, applied = _approve_and_apply(review_env, candidate)
    _patch_full_run(monkeypatch, review_env)

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)

    before = review_env["db"].query(SkillExecution).count()
    fresh = review_env["factory"]()
    try:
        agent = _fresh_agent(review_env, fresh)
        model = _SimulatedDecisionModel(candidate.skill_name)
        agent.llm = model
        agent.world_model = _WorldModelStub()
        agent.reflection_service = _ReflectionStub()

        result = asyncio.run(agent.execute(
            REQUEST,
            context={"user_id": review_env["user"].id},
        ))
    finally:
        fresh.close()

    assert result["status"] == "success", result
    assert len(model.calls) == 2
    assert len(result["steps"]) == 2, result["steps"]

    tool_step = result["steps"][0]
    assert tool_step["action"]["tool"] == "skills.execute"
    assert tool_step["dispatch_evidence"]["dispatched"] is True
    assert tool_step["dispatch_evidence"]["tool"] == "skills.execute"
    observation = tool_step["output"]
    assert observation["success"] is True, observation
    assert json.loads(observation["result"]) == EXPECTED_RESULT
    assert observation["skill"] == f"{candidate.skill_name}_r1"
    execution_id = str(observation["execution_id"])

    # The answer came from values the stub parsed out of the observation.
    assert "count=4" in result["output"]
    assert "maximum=11" in result["output"]
    assert "sum=26" in result["output"]
    assert f"execution_id={execution_id}" in result["output"]
    assert len(fake_sandbox.calls) == 1
    assert fake_sandbox.calls[0]["code"] == registered_executable_code(
        candidate.generated_code)

    # Fresh session re-reads the durable exact receipt after the run.
    verify = review_env["factory"]()
    try:
        assert verify.query(SkillExecution).count() == before + 1
        execution = _execution_row(verify, execution_id)
        assert execution.status == "success"
        assert execution.agent_id == review_env["agent"].id
        assert execution.skill_id == applied["skill_id"]
        assert execution.tenant_id == review_env["tenant"].id
        assert execution.workspace_id == review_env["workspace"].id
        assert execution.output_result["result"] == observation["result"]
        receipt = execution.audit_metadata["reviewed_executable"]
        assert receipt["status"] == "success"
        assert receipt["binding"]["verified"] is True
        assert receipt["binding"]["review_revision"] == (
            applied["review_revision"])
        assert receipt["binding"]["review_digest"] == applied["review_digest"]
        assert receipt["binding"]["executable_code_sha256"] == (
            applied["executable_code_sha256"])
        assert receipt["binding"]["candidate_code_sha256"] == (
            applied["candidate_code_sha256"])
        assert receipt["binding"]["registry_execution_id"] == (
            applied["registry_execution_id"])
        assert receipt["sandbox"]["nonce"] == receipt["sandbox"]["nonce_echo"]
        assert receipt["executed_by"] == review_env["user"].id
    finally:
        verify.close()


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


def test_changed_candidate_is_not_advertised_and_refused_before_the_sandbox(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="changed_candidate")
    _approved, applied = _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    # The registry binding is intact, but the reviewed material no longer
    # matches: discovery must stop advertising it and execution must refuse.
    candidate.generated_code = candidate.generated_code + "\n# changed\n"
    review_env["db"].commit()
    before = review_env["db"].query(SkillExecution).count()

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    from core.action_registry import action_registry

    scope = _scope(review_env)
    listed = asyncio.run(action_registry.execute_action("skills.list", {}, scope))
    assert listed["success"] is True
    assert listed["skills"] == []

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
        assert "skills_execute_not_available" in result["error"]
        assert _TripwireSandbox.calls == []
        assert fresh.query(SkillExecution).count() == before
    finally:
        fresh.close()

    # Actual execution must re-authorize even when a caller bypasses
    # discovery and asks the existing service directly.
    from core.skill_registry_service import SkillRegistryService

    with pytest.raises(
            ValueError, match="reviewed_executable_artifact_changed"):
        asyncio.run(SkillRegistryService(review_env["db"]).execute_skill(
            skill_id=applied["registry_execution_id"],
            inputs=SYNTHETIC_INPUTS,
            agent_id=review_env["agent"].id,
            tenant_id=review_env["tenant"].id,
            workspace_id=review_env["workspace"].id,
            user_id=review_env["user"].id,
        ))
    assert _TripwireSandbox.calls == []
    assert review_env["db"].query(SkillExecution).count() == before


def test_changed_registered_code_is_not_advertised_or_executable(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="changed_registered_code")
    _approved, applied = _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    from core.models import Skill

    linked = review_env["db"].query(Skill).filter(
        Skill.id == applied["skill_id"]).one()
    linked.code = linked.code + "\n# tampered after review\n"
    review_env["db"].commit()
    before = review_env["db"].query(SkillExecution).count()

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    from core.action_registry import action_registry

    scope = _scope(review_env)
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
    assert review_env["db"].query(SkillExecution).count() == before

    from core.skill_registry_service import SkillRegistryService

    with pytest.raises(
            ValueError, match="reviewed_executable_artifact_changed"):
        asyncio.run(SkillRegistryService(review_env["db"]).execute_skill(
            skill_id=applied["registry_execution_id"],
            inputs=SYNTHETIC_INPUTS,
            agent_id=review_env["agent"].id,
            tenant_id=review_env["tenant"].id,
            workspace_id=review_env["workspace"].id,
            user_id=review_env["user"].id,
        ))
    assert _TripwireSandbox.calls == []
    assert review_env["db"].query(SkillExecution).count() == before


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

    scope = _scope(review_env)
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

    # Direct service invocation cannot downgrade into the generic path.
    from core.skill_registry_service import SkillRegistryService

    with pytest.raises(
            ValueError, match="reviewed_executable_not_approved"):
        asyncio.run(SkillRegistryService(db).execute_skill(
            skill_id=applied["registry_execution_id"],
            inputs=SYNTHETIC_INPUTS,
            agent_id=review_env["agent"].id,
            tenant_id=review_env["tenant"].id,
            workspace_id=review_env["workspace"].id,
            user_id=review_env["user"].id,
        ))
    assert _TripwireSandbox.calls == []
    assert db.query(SkillExecution).count() == before


def test_revoked_candidate_is_not_advertised_or_executable(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="revoked_candidate")
    _approved, applied = _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    # Revoke the reviewed promotion (the exact binding is otherwise intact).
    candidate.validation_status = "validated"
    review_env["db"].commit()
    before = review_env["db"].query(SkillExecution).count()

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    from core.action_registry import action_registry

    scope = _scope(review_env)
    listed = asyncio.run(action_registry.execute_action("skills.list", {}, scope))
    assert listed["success"] is True
    assert listed["skills"] == []

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
        assert _TripwireSandbox.calls == []
        assert fresh.query(SkillExecution).count() == before
    finally:
        fresh.close()

    from core.skill_registry_service import SkillRegistryService

    with pytest.raises(ValueError, match="candidate is not promoted"):
        asyncio.run(SkillRegistryService(review_env["db"]).execute_skill(
            skill_id=applied["registry_execution_id"],
            inputs=SYNTHETIC_INPUTS,
            agent_id=review_env["agent"].id,
            tenant_id=review_env["tenant"].id,
            workspace_id=review_env["workspace"].id,
            user_id=review_env["user"].id,
        ))
    assert _TripwireSandbox.calls == []
    assert review_env["db"].query(SkillExecution).count() == before


def test_unassigned_workspace_skill_is_not_advertised_or_executable(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="unassigned_skill")
    _approved, applied = _approve_and_apply(review_env, candidate)
    _patch_db(monkeypatch, review_env)

    from core.models import workspace_skills

    review_env["db"].execute(
        workspace_skills.delete().where(
            workspace_skills.c.workspace_id == review_env["workspace"].id,
            workspace_skills.c.skill_id == applied["skill_id"],
        )
    )
    review_env["db"].commit()
    before = review_env["db"].query(SkillExecution).count()

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)

    from core.action_registry import action_registry

    scope = _scope(review_env)
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
    assert review_env["db"].query(SkillExecution).count() == before

    # Existing service callers are re-authorized too (not only discovery).
    from core.skill_registry_service import SkillRegistryService

    with pytest.raises(
            ValueError, match="not assigned to the authenticated workspace"):
        asyncio.run(SkillRegistryService(review_env["db"]).execute_skill(
            skill_id=applied["registry_execution_id"],
            inputs=SYNTHETIC_INPUTS,
            agent_id=review_env["agent"].id,
            tenant_id=review_env["tenant"].id,
            workspace_id=review_env["workspace"].id,
            user_id=review_env["user"].id,
        ))
    assert _TripwireSandbox.calls == []
    assert review_env["db"].query(SkillExecution).count() == before


def test_hostile_model_arguments_cannot_reach_another_workspace_skill(
        review_env, monkeypatch):
    """Model-supplied scope/identity args are never authority."""
    from core.auto_dev.models import SkillCandidate
    from core.models import Workspace
    from core.reviewed_improvement import apply_reviewed_skill, mark_reviewed
    from core.skill_builder_service import SkillBuilderService
    from core.skill_registry_service import SkillRegistryService

    db = review_env["db"]
    other_workspace = Workspace(
        id="hostile-other-workspace", name="Hostile Other",
        tenant_id=review_env["tenant"].id)
    other_agent = AgentRegistry(
        id="hostile-other-agent", name="Hostile Other Employee",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration={}, capabilities=[],
        workspace_id=other_workspace.id,
        tenant_id=review_env["tenant"].id)
    db.add_all([other_workspace, other_agent])
    db.commit()

    other_candidate = SkillCandidate(
        id="cand-hostile-other",
        tenant_id=review_env["tenant"].id,
        agent_id=other_agent.id,
        source_episode_id="episode-hostile-other",
        skill_name="hostile_other",
        skill_description="synthetic other-workspace computation",
        generated_code=BENIGN_CODE,
        failure_pattern={"failure_summary": "synthetic hostile probe"},
        validation_status="pending",
    )
    db.add(other_candidate)
    db.commit()
    mark_reviewed(
        other_candidate,
        reviewer_id=review_env["user"].id,
        tenant_id=review_env["tenant"].id,
        workspace_id=other_workspace.id,
    )
    db.commit()
    applied = asyncio.run(apply_reviewed_skill(
        db, other_candidate,
        tenant_id=review_env["tenant"].id,
        workspace_id=other_workspace.id,
        builder=SkillBuilderService(
            workspace_root=str(review_env["tmp_path"])),
        registry=SkillRegistryService(db),
        executable=True,
    ))
    assert applied["generated_code_applied"] is True

    _patch_db(monkeypatch, review_env)
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)
    before = db.query(SkillExecution).count()

    fresh = review_env["factory"]()
    try:
        agent = _fresh_agent(review_env, fresh)
        hostile_args = {
            "skill": other_candidate.skill_name,
            "inputs": SYNTHETIC_INPUTS,
            # Every one of these is model-authored. None may become scope.
            "_skill_scope": {
                "tenant_id": review_env["tenant"].id,
                "workspace_id": other_workspace.id,
                "agent_id": other_agent.id,
                "user_id": "attacker",
            },
            "tenant_id": review_env["tenant"].id,
            "workspace_id": other_workspace.id,
            "agent_id": other_agent.id,
        }
        result = asyncio.run(agent._step_act(
            "skills.execute", hostile_args, _context(review_env)))
        assert result["success"] is False, result
        assert result["blocked_by"] == "skill_authorization"
        assert "skills_execute_not_available" in result["error"]
        assert _TripwireSandbox.calls == []
        assert fresh.query(SkillExecution).count() == before
    finally:
        fresh.close()


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
