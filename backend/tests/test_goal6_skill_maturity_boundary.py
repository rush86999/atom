"""Maturity/error-contract controls through the real /api/skills/execute route.

The scoped governance path denies a non-default STUDENT before sandbox and row
creation, while same-scope INTERN remains allowed. Two additional injected
service-fault controls pin the route's redaction contract: unknown ValueError /
RuntimeError responses must remain the generic "Internal error" and must not
echo the injected marker. Fault injection is an error-contract control, not a
full runtime-proof claim.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.skill_registry_service import SkillRegistryService

from core.models import AgentRegistry, SkillExecution, Tenant, User, Workspace
from tests.test_goal6_ordinary_creation_positive import (
    ADMIN, COMPANY, SUPERVISOR, WS_A, World, add_evidence, approve,
    create_agent, promote, request_review,
)
from tests.test_reviewed_executable_skill import (
    SYNTHETIC_INPUTS, _FakeDockerSandbox, _FakeScanner, _approve_and_apply,
    _pending_candidate, _skill_client,
)
from tests.test_reviewed_executable_skill_agent_dispatch import (
    _TripwireSandbox, _execution_row,
)

def _env_for_agent(world, tmp_path, *, promote_agent=False):
    client = world.client()
    admin = world.token(ADMIN)
    sup = world.token(SUPERVISOR)
    created = create_agent(client, admin)
    assert created["status"] == 201, created
    agent_id = created["json"]["data"]["agent_id"]
    if promote_agent:
        add_evidence(world, agent_id)
        requested = request_review(client, sup, agent_id, [
            {"kind": "agent_episode", "id": f"goal6-ep-{agent_id[:8]}-00"},
            {"kind": "agent_execution",
             "id": f"goal6-exec-{agent_id[:8]}-00"},
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
        "user": db.get(User, ADMIN),
        "tmp_path": tmp_path, "agent_id": agent_id,
    }


def _prepare_skill(env, tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_WORKSPACE_SKILLS_ROOT",
                       str(tmp_path / "reviewed-maturity-skills"))
    monkeypatch.setattr(
        "core.skill_registry_service.SkillSecurityScanner", _FakeScanner)
    candidate = _pending_candidate(env)
    _approved, applied = _approve_and_apply(env, candidate)
    return candidate, applied


def _execute(client, applied, agent_id):
    return client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": agent_id,
    })


def test_candidate_scoped_student_denied_before_sandbox_and_row(
        tmp_path, monkeypatch):
    world = World(tmp_path, episodes=0)
    env = _env_for_agent(world, tmp_path)
    candidate, applied = _prepare_skill(env, tmp_path, monkeypatch)
    _TripwireSandbox.calls = []
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _TripwireSandbox)
    before = env["db"].query(SkillExecution).count()
    response = _execute(
        _skill_client(env["db"], env["tenant"], env["workspace"],
                      user_id=env["user"].id),
        applied, env["agent_id"])
    assert response.status_code == 400, response.text
    detail = response.json().get("detail")
    assert "STUDENT agents cannot execute Python skills" in str(detail), detail
    assert _TripwireSandbox.calls == []
    assert env["db"].query(SkillExecution).count() == before


def test_same_scope_intern_still_executes(tmp_path, monkeypatch):
    world = World(tmp_path, episodes=0)
    env = _env_for_agent(world, tmp_path, promote_agent=True)
    candidate, applied = _prepare_skill(env, tmp_path, monkeypatch)
    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)
    before = env["db"].query(SkillExecution).count()
    response = _execute(
        _skill_client(env["db"], env["tenant"], env["workspace"],
                      user_id=env["user"].id),
        applied, env["agent_id"])
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["success"] is True, payload
    assert len(fake_sandbox.calls) == 1
    execution = _execution_row(env["db"], payload["execution_id"])
    assert execution.agent_id == env["agent_id"]
    assert execution.tenant_id == COMPANY
    assert execution.workspace_id == WS_A
    receipt = execution.audit_metadata["reviewed_executable"]
    assert receipt["status"] == "success"
    assert receipt["binding"]["verified"] is True
    assert receipt["executed_by"] == env["user"].id
    assert env["db"].query(SkillExecution).count() == before + 1


@pytest.mark.parametrize("fault,status", [
    (ValueError, 400),
    (RuntimeError, 500),
])
def test_unknown_service_errors_remain_redacted(
        tmp_path, monkeypatch, fault, status):
    """Error-contract control: only known maturity refusals expose detail."""
    marker = "SYNTHETIC_UNKNOWN_SKILL_ERROR_MARKER_7f3c"
    world = World(tmp_path, episodes=0)
    env = _env_for_agent(world, tmp_path)
    monkeypatch.setattr(
        SkillRegistryService, "execute_skill",
        AsyncMock(side_effect=fault(marker)))
    response = _execute(
        _skill_client(env["db"], env["tenant"], env["workspace"],
                      user_id=env["user"].id),
        {"registry_execution_id": "synthetic-skill-id"},
        env["agent_id"])
    assert response.status_code == status, response.text
    assert response.json().get("detail") == "Internal error", response.text
    assert marker not in response.text


if __name__ == "__main__":
    import tempfile
    import pytest

    with tempfile.TemporaryDirectory(prefix="goal6-maturity-") as td:
        with pytest.MonkeyPatch.context() as mp:
            test_candidate_scoped_student_denied_before_sandbox_and_row(
                Path(td), mp)
    print("GOAL6_MATURITY_BOUNDARY_PASS")
