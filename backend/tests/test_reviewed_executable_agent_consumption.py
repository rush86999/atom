"""Ordinary-agent consumption of a reviewed harmless executable skill.

The reviewed-executable lifecycle is proved in
``tests/test_reviewed_executable_skill.py``.  This control exercises the two
boundaries an ordinary agent actually crosses:

* prompt-time consumption: a fresh GenericAgent/DB session sees the reviewed
  skill's name/description (never its generated code), because the apply step
  assigned it to the reviewed workspace;
* invocation: the ordinary ``POST /api/skills/execute`` route runs the bound
  artifact for that employee and persists a verified receipt.

The negative controls prove authorization happens *before* the sandbox leaf:
an unreviewed pending candidate cannot be applied, and a registry record that
lost its reviewed binding is refused instead of silently falling through to
the generic community-skill execution path.

Real: approval/apply routes, candidate/Skill/SkillExecution rows, workspace
assignment, the ordinary execute route, and the durable receipt.
Simulated: the LLM security scanner (deterministic LOW) and the Docker sandbox
(deterministic in-process stand-in that runs the same wrapper); Docker is not
reachable in this environment, so the host-container replay remains the
separate ``test_reviewed_executable_skill_docker.py`` lane.
"""
from __future__ import annotations

import json

import pytest

from core.models import AgentRegistry, SkillExecution
from tests.test_reviewed_executable_skill import (  # noqa: F401
    EXPECTED_RESULT,
    SYNTHETIC_INPUTS,
    _FakeDockerSandbox,
    _approve_and_apply,
    _autodev_client,
    _execution_row,
    _pending_candidate,
    _skill_client,
    review_env,
)
from tests.test_reviewed_improvement_apply import env as _reviewed_env  # noqa: F401

REQUEST = "deterministically summarize a list of integers"


class _TripwireSandbox:
    """A denial must be reached before this leaf is even constructed."""

    calls = []

    def __init__(self):
        self.calls = _TripwireSandbox.calls

    def execute_python(self, code, inputs):
        self.calls.append(("execute_python", code))
        raise AssertionError("generic python path reached for a refused skill")

    def execute_python_receipt(self, code, inputs, **kwargs):
        self.calls.append(("execute_python_receipt", code))
        raise AssertionError("receipt path reached for a refused skill")


@pytest.fixture(autouse=True)
def _reset_tripwire():
    _TripwireSandbox.calls = []
    yield


def _fresh_agent(env, db):
    from core.generic_agent import GenericAgent

    row = db.query(AgentRegistry).filter(
        AgentRegistry.id == env["agent"].id).one()
    agent = GenericAgent(row, workspace_id=env["workspace"].id)
    agent.tenant_id = env["tenant"].id
    return agent


def test_fresh_agent_session_consumes_reviewed_executable(review_env, monkeypatch):
    candidate = _pending_candidate(review_env)
    _approved, applied = _approve_and_apply(review_env, candidate)

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)
    monkeypatch.setattr(
        "core.database.get_db_session", review_env["factory"])

    fresh = review_env["factory"]()
    try:
        agent = _fresh_agent(review_env, fresh)

        # Prompt-time consumption is real: the fresh agent reads the applied
        # workspace assignment, but the generated code never reaches the prompt.
        block = agent._retrieve_skill_instructions(REQUEST)
        assert candidate.skill_name in block
        assert "def execute" not in block
        assert "atom reviewed executable harness" not in block

        workspace_block = agent._workspace_context_block()
        assert "WORKSPACE-ASSIGNED SKILLS" in workspace_block
        assert candidate.skill_name in workspace_block

        # Invocation is the ordinary authorized route, as the reviewed
        # employee, from the new session.
        client = _skill_client(
            fresh, review_env["tenant"], review_env["workspace"])
        response = client.post("/api/skills/execute", json={
            "skill_id": applied["registry_execution_id"],
            "inputs": SYNTHETIC_INPUTS,
            "agent_id": review_env["agent"].id,
        })
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["success"] is True, data
        assert json.loads(data["result"]) == EXPECTED_RESULT
        assert len(fake_sandbox.calls) == 1

        execution = _execution_row(fresh, data["execution_id"])
        receipt = execution.audit_metadata["reviewed_executable"]
        assert receipt["status"] == "success"
        assert receipt["binding"]["verified"] is True
        assert receipt["binding"]["review_digest"] == applied["review_digest"]
        assert receipt["sandbox"]["nonce"] == receipt["sandbox"]["nonce_echo"]
    finally:
        fresh.close()


def test_unreviewed_pending_candidate_is_denied_before_invocation(review_env):
    candidate = _pending_candidate(review_env, name="unreviewed_fixture")
    response = _autodev_client(review_env).post(
        f"/api/autodev/skills/{candidate.id}/apply-executable")
    assert response.status_code == 409, response.text
    assert "candidate_not_reviewed" in response.text

    review_env["db"].expire_all()
    assert review_env["db"].query(SkillExecution).count() == 0
    assert not list(review_env["skills_root"].rglob("SKILL.md"))


def test_binding_removed_artifact_is_denied_before_invocation(
        review_env, monkeypatch):
    """A reviewed artifact that lost its registry binding is unreviewed.

    Preserve the package digest / linked-Skill markers but delete only the
    registry binding: the record must be refused, never run on the generic
    community-skill path.
    """
    candidate = _pending_candidate(review_env, name="binding_removed")
    _approved, applied = _approve_and_apply(review_env, candidate)

    db = review_env["db"]
    execution = _execution_row(db, applied["registry_execution_id"])
    params = json.loads(json.dumps(execution.input_params))
    assert params.pop("reviewed_executable", None)
    execution.input_params = params
    db.commit()
    before = db.query(SkillExecution).count()

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)
    client = _skill_client(db, review_env["tenant"], review_env["workspace"])
    response = client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code == 409, response.text
    assert "reviewed_executable_not_approved" in response.text
    assert _TripwireSandbox.calls == []
    assert db.query(SkillExecution).count() == before
