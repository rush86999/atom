"""Reviewed *benign executable* skill lifecycle (Docker-independent).

The prompt-only reviewed flow is the regression control (see
``tests/test_reviewed_improvement_apply.py``).  This module covers the explicit
executable exception and the properties the acceptance brief asks for:

* approval happens through the public ``/api/autodev`` approval route and binds
  the exact candidate digest + reviewer authority;
* only benign deterministic code (``execute(inputs)``) can be applied
  executably; anything with imports/I/O/dunders/top-level effects is refused;
* the registered package, the registry row and the ``Skill`` row all match the
  approved review revision and digests;
* after a fresh session/application, execution goes through the ordinary
  authorized ``POST /api/skills/execute`` entry point and the computed result
  plus a durable execution receipt are asserted;
* unapproved, changed (candidate or registry artifact) and cross-workspace
  artifacts are refused before any execution record is written.

Docker is replaced by a deterministic in-process stand-in that executes the
SAME registered source through the SAME wrapper (including the nonce echo).
The real container replay lives in ``test_reviewed_executable_skill_docker.py``
(hosted CI, ``ATOM_REQUIRE_DOCKER_SANDBOX=1``).  Consequently this file records
``sandbox_simulated=True``, ``provider_simulated=True`` — the LLM security
scanner is also stubbed and no provider/network is contacted.
"""
from __future__ import annotations

import contextlib
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auto_dev.models import SkillCandidate
from core.models import (
    AgentRegistry,
    Skill,
    SkillExecution,
    User,
    Workspace,
)
from core.reviewed_executable import (
    EXECUTABLE_RECEIPT_SCHEMA,
    assess_benign_code,
    registered_executable_code,
    sha256_text,
)
from core.reviewed_improvement import mark_reviewed
from core.skill_registry_service import SkillRegistryService
from tests.test_reviewed_improvement_apply import env as _reviewed_env  # noqa: F401

BENIGN_CODE = (
    "def execute(inputs):\n"
    "    values = inputs.get(\"values\", [])\n"
    "    return {\"count\": len(values), \"sum\": sum(values), "
    "\"maximum\": max(values) if values else None}\n"
)
SYNTHETIC_INPUTS = {"values": [3, 5, 7, 11]}
EXPECTED_RESULT = {"count": 4, "maximum": 11, "sum": 26}


class _FakeScanner:
    """No provider/network: import-time security scan is simulated LOW."""

    async def scan_skill(self, skill_name, skill_content):
        return {"safe": True, "risk_level": "LOW", "findings": []}


class _FakeDockerSandbox:
    """Executes the registered source through HazardSandbox's real wrapper.

    This is explicitly a *simulation* of container isolation: the code runs in
    the test process.  It still proves the registered artifact computes the
    expected result and that the execution layer persists the nonce receipt.
    """

    def __init__(self):
        self.calls = []

    def execute_python_receipt(
        self, code, inputs, timeout_seconds=30, memory_limit="256m",
        cpu_limit=0.5, nonce=None,
    ):
        from core.skill_sandbox import HazardSandbox

        self.calls.append({
            "code": code,
            "inputs": dict(inputs or {}),
            "nonce": nonce,
            "timeout_seconds": timeout_seconds,
        })
        wrapper = HazardSandbox.__new__(HazardSandbox)._create_wrapper_script(
            code, inputs or {}, nonce=nonce)
        buffer = io.StringIO()
        namespace = {"__name__": "__fake_docker__"}
        try:
            with contextlib.redirect_stdout(buffer):
                exec(compile(wrapper, "<fake-docker-wrapper>", "exec"), namespace)
        except SystemExit:
            return {
                "ok": False,
                "stdout": buffer.getvalue(),
                "stderr": "sandboxed code exited",
                "error": "EXECUTION_ERROR: sandboxed code exited",
                "exit_code": 1,
                "container_id": "skill_" + str(nonce)[:8],
                "image": "python:3.11-slim",
                "backend": "docker",
                "network_disabled": True,
                "read_only": True,
                "ephemeral": True,
                "nonce": nonce,
            }
        return {
            "ok": True,
            "stdout": buffer.getvalue(),
            "stderr": "",
            "exit_code": 0,
            "container_id": "skill_" + str(nonce)[:8],
            "image": "python:3.11-slim",
            "backend": "docker",
            "network_disabled": True,
            "read_only": True,
            "ephemeral": True,
            "nonce": nonce,
        }


@pytest.fixture()
def review_env(_reviewed_env, monkeypatch, tmp_path):  # noqa: F811
    """env fixture + isolated package root and simulated import scanner."""
    env = _reviewed_env
    skills_root = tmp_path / "reviewed-executable-skills"
    monkeypatch.setenv("ATOM_WORKSPACE_SKILLS_ROOT", str(skills_root))
    monkeypatch.setattr(
        "core.skill_registry_service.SkillSecurityScanner", _FakeScanner)
    env["skills_root"] = skills_root
    return env


def _pending_candidate(env, *, code=BENIGN_CODE, name="summarize_values"):
    row = SkillCandidate(
        id=f"cand-{name}",
        tenant_id=env["tenant"].id,
        agent_id=env["agent"].id,
        source_episode_id="episode-executable-1",
        skill_name=name,
        skill_description="deterministically summarize a list of integers",
        generated_code=code,
        failure_pattern={"failure_summary": "could not summarize values"},
        validation_status="pending",
    )
    env["db"].add(row)
    env["db"].commit()
    return row


def _autodev_client(env, role="team_lead", user=None, db=None):
    from api.autodev_review_routes import router
    from core.auth import get_current_tenant, get_current_user
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)
    session = db or env["db"]
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_tenant] = lambda: env["tenant"]
    app.dependency_overrides[get_current_user] = lambda: (
        user or SimpleNamespace(
            id="reviewer", role=role,
            workspace_id=env["workspace"].id,
            tenant_id=env["tenant"].id,
            email="reviewer@example.invalid"))
    return TestClient(app)


def _skill_client(db, tenant, workspace, *, user_id="reviewer"):
    from api.skill_routes import router, get_skill_service
    from core.auth import get_current_user
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_skill_service] = lambda: (
        SkillRegistryService(db))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id, role="workspace_admin",
        workspace_id=workspace.id, tenant_id=tenant.id,
        email="reviewer@example.invalid")
    return TestClient(app)


def _approve_and_apply(env, candidate):
    client = _autodev_client(env)
    approved = client.post(f"/api/autodev/skills/{candidate.id}/approve")
    assert approved.status_code == 200, approved.text
    applied = client.post(
        f"/api/autodev/skills/{candidate.id}/apply-executable")
    assert applied.status_code == 200, applied.text
    return approved.json()["data"], applied.json()["data"]


def _execution_row(db, execution_id):
    db.expire_all()
    return db.query(SkillExecution).filter(
        SkillExecution.id == execution_id).one()


def test_benign_policy_is_an_ast_allowlist():
    assessment = assess_benign_code(BENIGN_CODE)
    assert assessment["eligible"] is True, assessment
    assert assessment["entrypoint"] == "execute"

    refused = {
        "import": "import os\n\ndef execute(inputs):\n    return 1\n",
        "io": "def execute(inputs):\n    return open('/etc/passwd').read()\n",
        "dynamic": "def execute(inputs):\n    return eval('1+1')\n",
        "dunder": (
            "def execute(inputs):\n"
            "    return ().__class__.__bases__\n"),
        "format_traversal": (
            "def execute(inputs):\n"
            "    return '{0.__class__}'.format(inputs)\n"),
        "frame_attribute": (
            "def execute(inputs):\n"
            "    return (x for x in [1]).gi_frame\n"),
        "top_level": "print('side effect')\n\ndef execute(inputs):\n    return 1\n",
        "unbounded": "def execute(inputs):\n    while True:\n        pass\n",
        "signature": "def execute(inputs, extra=1):\n    return 1\n",
    }
    for label, code in refused.items():
        result = assess_benign_code(code)
        assert result["eligible"] is False, (label, result)


def test_candidate_listing_reports_executable_eligibility(review_env):
    candidate = _pending_candidate(review_env, name="listing_executable")
    response = _autodev_client(review_env).get(
        "/api/autodev/candidates?status=pending")
    assert response.status_code == 200, response.text
    items = response.json()["data"]["candidates"]
    item = next(i for i in items if i["id"] == candidate.id)
    assert item["executable_eligibility"]["eligible"] is True
    assert item["executable_eligibility"]["entrypoint"] == "execute"

    unsafe = _pending_candidate(
        review_env, name="listing_unsafe",
        code="import os\n\ndef execute(inputs):\n    return 1\n")
    response = _autodev_client(review_env).get(
        "/api/autodev/candidates?status=pending")
    items = response.json()["data"]["candidates"]
    item = next(i for i in items if i["id"] == unsafe.id)
    assert item["executable_eligibility"]["eligible"] is False
    assert item["executable_eligibility"]["reasons"]


def test_pending_candidate_cannot_be_applied_executably(review_env):
    candidate = _pending_candidate(review_env)
    client = _autodev_client(review_env)
    response = client.post(
        f"/api/autodev/skills/{candidate.id}/apply-executable")
    assert response.status_code == 409, response.text
    assert "candidate_not_reviewed" in response.text
    assert review_env["db"].query(SkillExecution).count() == 0
    assert not list(review_env["skills_root"].rglob("SKILL.md"))


def test_reviewer_authority_is_required_for_executable_apply(review_env):
    candidate = _pending_candidate(review_env, name="viewer_blocked")
    app = _autodev_client(review_env, role="viewer")
    response = app.post(
        f"/api/autodev/skills/{candidate.id}/approve")
    assert response.status_code == 403, response.text
    response = app.post(
        f"/api/autodev/skills/{candidate.id}/apply-executable")
    assert response.status_code == 403, response.text


def test_non_benign_code_is_refused_and_leaves_no_artifact(review_env):
    candidate = _pending_candidate(
        review_env, name="unsafe_candidate",
        code="import os\n\ndef execute(inputs):\n    return os.getcwd()\n")
    client = _autodev_client(review_env)
    assert client.post(
        f"/api/autodev/skills/{candidate.id}/approve").status_code == 200
    response = client.post(
        f"/api/autodev/skills/{candidate.id}/apply-executable")
    assert response.status_code == 422, response.text
    assert "executable_policy_rejected" in response.text

    review_env["db"].refresh(candidate)
    assert candidate.validation_status == "validated"
    assert review_env["db"].query(SkillExecution).count() == 0
    assert not list(review_env["skills_root"].rglob("SKILL.md"))


def test_apply_binds_exact_review_and_registered_artifact(review_env):
    candidate = _pending_candidate(review_env)
    approved, applied = _approve_and_apply(review_env, candidate)

    review_env["db"].refresh(candidate)
    assert approved["review_digest"] == (
        candidate.validation_result["review"]["digest"])
    assert approved["review_revision"] == applied["review_revision"]
    assert applied["status"] == "promoted"
    assert applied["generated_code_applied"] is True
    assert applied["execution_kind"] == "reviewed_executable"
    assert applied["sandbox_backend"] == "docker"

    expected_code = registered_executable_code(candidate.generated_code)
    assert applied["candidate_code_sha256"] == sha256_text(
        candidate.generated_code)
    assert applied["executable_code_sha256"] == sha256_text(expected_code)

    execution = _execution_row(
        review_env["db"], applied["registry_execution_id"])
    binding = execution.input_params["reviewed_executable"]
    assert binding["candidate_id"] == candidate.id
    assert binding["review_revision"] == approved["review_revision"]
    assert binding["review_digest"] == approved["review_digest"]
    assert binding["executable_code_sha256"] == sha256_text(expected_code)
    assert binding["tenant_id"] == review_env["tenant"].id
    assert binding["workspace_id"] == review_env["workspace"].id
    assert binding["agent_id"] == review_env["agent"].id
    assert execution.sandbox_enabled is True

    # The registered SKILL.md contains exactly the approved code + harness.
    assert expected_code in execution.input_params["skill_body"]
    skill = review_env["db"].query(Skill).filter(
        Skill.id == applied["skill_id"]).one()
    assert skill.type == "script"
    assert skill.code == expected_code
    assert skill.config["entrypoint"] == "execute"
    assert skill.config["sandbox"] == "docker"
    assert skill.config["reviewed_executable"] == binding

    stored = candidate.validation_result["applied"]
    assert stored["execution_kind"] == "reviewed_executable"
    assert stored["registry_execution_id"] == applied["registry_execution_id"]
    assert stored["executable_code_sha256"] == sha256_text(expected_code)


def test_duplicate_executable_apply_is_idempotent(review_env):
    candidate = _pending_candidate(review_env, name="duplicate_executable")
    _approved, first = _approve_and_apply(review_env, candidate)
    response = _autodev_client(review_env).post(
        f"/api/autodev/skills/{candidate.id}/apply-executable")
    assert response.status_code == 200, response.text
    second = response.json()["data"]
    assert second["already_applied"] is True
    assert second["registry_execution_id"] == first["registry_execution_id"]
    assert second["generated_code_applied"] is True
    assert review_env["db"].query(SkillExecution).count() == 1
    assert review_env["db"].query(Skill).count() == 1


def test_ordinary_execute_after_fresh_session_computes_and_receipts(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env)
    _approved, applied = _approve_and_apply(review_env, candidate)

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)

    # "Restart": brand-new session + new application instance.  Durable state
    # is the shared engine/database; no request objects are reused.
    fresh = review_env["factory"]()
    try:
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
        assert fake_sandbox.calls[0]["code"] == (
            registered_executable_code(candidate.generated_code))

        execution = _execution_row(fresh, data["execution_id"])
        assert execution.status == "success"
        assert execution.output_result["result"] == data["result"]
        assert execution.container_id.startswith("skill_")
        assert execution.exit_code == 0

        receipt = execution.audit_metadata["reviewed_executable"]
        assert receipt["schema"] == EXECUTABLE_RECEIPT_SCHEMA
        assert receipt["status"] == "success"
        assert receipt["binding"]["review_digest"] == applied["review_digest"]
        assert receipt["binding"]["review_revision"] == (
            applied["review_revision"])
        assert receipt["binding"]["executable_code_sha256"] == (
            applied["executable_code_sha256"])
        assert receipt["sandbox"]["backend"] == "docker"
        assert receipt["sandbox"]["ran"] is True
        assert receipt["sandbox"]["network_disabled"] is True
        assert receipt["sandbox"]["read_only"] is True
        assert receipt["sandbox"]["nonce"] == (
            receipt["sandbox"]["nonce_echo"])
        assert receipt["inputs_sha256"]
        assert receipt["result_sha256"]
    finally:
        fresh.close()


def test_sandbox_must_prove_it_ran_with_the_execution_nonce(
        review_env, monkeypatch):
    """A container-shaped result without the nonce echo is not certified."""
    candidate = _pending_candidate(review_env, name="no_nonce_echo")
    _approved, applied = _approve_and_apply(review_env, candidate)

    class _NoEchoSandbox:
        def execute_python_receipt(
            self, code, inputs, timeout_seconds=30, memory_limit="256m",
            cpu_limit=0.5, nonce=None,
        ):
            return {
                "ok": True,
                "stdout": '{"count": 4, "maximum": 11, "sum": 26}\n',
                "stderr": "",
                "exit_code": 0,
                "container_id": "skill_noecho",
                "image": "python:3.11-slim",
                "backend": "docker",
                "network_disabled": True,
                "read_only": True,
                "ephemeral": True,
                "nonce": nonce,
            }

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _NoEchoSandbox)
    client = _skill_client(
        review_env["db"], review_env["tenant"], review_env["workspace"])
    response = client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code in (200, 202), response.text
    data = response.json()["data"]
    assert data["success"] is False
    assert "sandbox_unverified" in data["error"]
    assert "result" not in data
    execution = _execution_row(review_env["db"], data["execution_id"])
    assert execution.status == "failed"
    receipt = execution.audit_metadata["reviewed_executable"]
    assert receipt["sandbox"]["ran"] is True
    assert receipt["sandbox"]["nonce"]
    assert receipt["sandbox"]["nonce_echo"] is None
    assert receipt["status"] == "failed"


def test_changed_registered_artifact_is_refused_before_execution(
        review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="tampered_registry")
    _approved, applied = _approve_and_apply(review_env, candidate)

    db = review_env["db"]
    execution = _execution_row(db, applied["registry_execution_id"])
    params = json.loads(json.dumps(execution.input_params))
    params["skill_body"] = params["skill_body"].replace(
        "\"sum\": sum(values)", "\"sum\": sum(values) + 1")
    execution.input_params = params
    db.commit()

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)
    client = _skill_client(db, review_env["tenant"], review_env["workspace"])
    response = client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code == 409, response.text
    assert "reviewed_executable_artifact_changed" in response.text
    assert fake_sandbox.calls == []


def test_changed_linked_skill_code_is_refused(review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="tampered_linked_skill")
    _approved, applied = _approve_and_apply(review_env, candidate)

    skill = review_env["db"].query(Skill).filter(
        Skill.id == applied["skill_id"]).one()
    skill.code = skill.code + "\n# changed\n"
    review_env["db"].commit()

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)
    client = _skill_client(
        review_env["db"], review_env["tenant"], review_env["workspace"])
    response = client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code == 409, response.text
    assert "reviewed_executable_artifact_changed" in response.text
    assert fake_sandbox.calls == []


def test_changed_candidate_is_refused_after_apply(review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="tampered_candidate")
    _approved, applied = _approve_and_apply(review_env, candidate)

    candidate.generated_code = candidate.generated_code + "\n# changed\n"
    review_env["db"].commit()

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)
    client = _skill_client(
        review_env["db"], review_env["tenant"], review_env["workspace"])
    response = client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code == 409, response.text
    assert "reviewed_executable_artifact_changed" in response.text
    assert fake_sandbox.calls == []


def test_unapproved_artifact_is_refused(review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="revoked_candidate")
    _approved, applied = _approve_and_apply(review_env, candidate)

    candidate.validation_status = "validated"
    review_env["db"].commit()

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)
    client = _skill_client(
        review_env["db"], review_env["tenant"], review_env["workspace"])
    response = client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code == 409, response.text
    assert "reviewed_executable_not_approved" in response.text
    assert fake_sandbox.calls == []


def test_cross_workspace_artifact_is_refused(review_env, monkeypatch):
    candidate = _pending_candidate(review_env, name="cross_workspace")
    _approved, applied = _approve_and_apply(review_env, candidate)

    db = review_env["db"]
    other_ws = Workspace(
        id="ws-executable-other", name="Other Executable",
        tenant_id=review_env["tenant"].id)
    other_agent = AgentRegistry(
        id="agent-executable-other", name="Other Employee",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration={}, capabilities=[], workspace_id=other_ws.id,
        tenant_id=review_env["tenant"].id)
    other_user = User(
        id="other-reviewer", email="other@example.invalid",
        hashed_password="x", first_name="O", last_name="T",
        role="workspace_admin", status="active",
        workspace_id=other_ws.id, tenant_id=review_env["tenant"].id,
        is_active=True)
    db.add_all([other_ws, other_agent, other_user])
    db.commit()

    fake_sandbox = _FakeDockerSandbox()
    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", lambda: fake_sandbox)

    # Same employee id, caller from another workspace.
    cross_user_client = _skill_client(
        db, review_env["tenant"], other_ws, user_id=other_user.id)
    response = cross_user_client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code == 403, response.text
    assert "reviewed_executable_workspace_mismatch" in response.text

    # Real employee from the other workspace, same tenant.
    response = _skill_client(
        db, review_env["tenant"], other_ws, user_id=other_user.id,
    ).post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": other_agent.id,
    })
    assert response.status_code == 403, response.text
    assert fake_sandbox.calls == []


def test_unavailable_docker_fails_closed_without_a_host_run(review_env, monkeypatch):
    """No daemon => unverified failed receipt; never a host execution."""
    candidate = _pending_candidate(review_env, name="docker_unavailable")
    _approved, applied = _approve_and_apply(review_env, candidate)

    class _UnavailableSandbox:
        def __init__(self):
            raise RuntimeError(
                "Docker daemon is not running or not accessible")

    monkeypatch.setattr(
        "core.skill_registry_service.HazardSandbox", _UnavailableSandbox)
    client = _skill_client(
        review_env["db"], review_env["tenant"], review_env["workspace"])
    response = client.post("/api/skills/execute", json={
        "skill_id": applied["registry_execution_id"],
        "inputs": SYNTHETIC_INPUTS,
        "agent_id": review_env["agent"].id,
    })
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["success"] is False
    assert "result" not in data
    assert "reviewed_executable_sandbox_unverified" in data["error"]
    assert data["reviewed_executable"]["sandbox"]["ran"] is False
    assert data["reviewed_executable"]["sandbox"]["nonce"]

    execution = _execution_row(review_env["db"], data["execution_id"])
    assert execution.status == "failed"
    assert execution.container_id is None
    assert "reviewed_executable_sandbox_unverified" in (
        execution.error_message or "")


def test_cross_workspace_reviewer_cannot_apply_executably(review_env):
    candidate = _pending_candidate(review_env, name="cross_apply")
    db = review_env["db"]
    other_ws = Workspace(
        id="ws-executable-apply-other", name="Other Apply",
        tenant_id=review_env["tenant"].id)
    db.add(other_ws)
    db.commit()
    other_user = SimpleNamespace(
        id="other-apply-reviewer", role="team_lead",
        workspace_id=other_ws.id, tenant_id=review_env["tenant"].id,
        email="other-apply@example.invalid")
    client = _autodev_client(review_env, user=other_user)
    assert client.post(
        f"/api/autodev/skills/{candidate.id}/approve").status_code == 403
    assert client.post(
        f"/api/autodev/skills/{candidate.id}/apply-executable"
    ).status_code == 403


def test_prompt_applied_candidate_cannot_become_executable(review_env):
    """An already-promoted prompt skill is not retroactively executable."""
    import asyncio

    from core.reviewed_improvement import apply_reviewed_skill
    from core.skill_builder_service import SkillBuilderService

    candidate = _pending_candidate(review_env, name="prompt_then_executable")
    mark_reviewed(
        candidate, reviewer_id="reviewer",
        tenant_id=review_env["tenant"].id,
        workspace_id=review_env["workspace"].id)
    review_env["db"].commit()
    asyncio.run(apply_reviewed_skill(
        review_env["db"], candidate,
        tenant_id=review_env["tenant"].id,
        workspace_id=review_env["workspace"].id,
        builder=SkillBuilderService(
            workspace_root=str(review_env["skills_root"])),
        registry=SkillRegistryService(review_env["db"]),
    ))
    response = _autodev_client(review_env).post(
        f"/api/autodev/skills/{candidate.id}/apply-executable")
    assert response.status_code == 409, response.text
    assert "candidate_state_conflict" in response.text


def test_prompt_flow_remains_the_non_executable_control(review_env):
    """The prompt apply still records generated_code_applied=False."""
    import asyncio

    from core.reviewed_improvement import apply_reviewed_skill
    from core.skill_builder_service import SkillBuilderService

    candidate = _pending_candidate(review_env, name="prompt_control")
    mark_reviewed(
        candidate, reviewer_id="reviewer",
        tenant_id=review_env["tenant"].id,
        workspace_id=review_env["workspace"].id)
    review_env["db"].commit()
    result = asyncio.run(apply_reviewed_skill(
        review_env["db"], candidate,
        tenant_id=review_env["tenant"].id,
        workspace_id=review_env["workspace"].id,
        builder=SkillBuilderService(
            workspace_root=str(review_env["skills_root"])),
        registry=SkillRegistryService(review_env["db"]),
    ))
    assert result["generated_code_applied"] is False
    assert result["execution_kind"] == "prompt"
    assert "executable_code_sha256" not in result
    skill = review_env["db"].query(Skill).filter(
        Skill.id == result["skill_id"]).one()
    assert skill.type == "prompt"
    assert skill.code is None
    package = next(
        (review_env["skills_root"] / review_env["tenant"].id / "skills").glob(
            "prompt_control_r*"))
    markdown = (package / "SKILL.md").read_text()
    assert "def execute" not in markdown
