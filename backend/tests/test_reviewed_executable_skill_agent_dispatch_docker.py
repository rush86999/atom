"""Joined ordinary-agent dispatch through a REAL Docker reviewed skill.

The unit control (``test_reviewed_executable_skill_agent_dispatch.py``) proves
the joined loop with the deterministic in-process sandbox stand-in. This twin
runs the same joined path with the real ``HazardSandbox`` container:

* the model decision is explicitly SIMULATED (deterministic decision stub);
* the public ``GenericAgent.execute`` ReAct loop is real;
* ``skills.execute`` dispatches through the real action registry / MCP path;
* the reviewed artifact is re-authorized and runs in a real ``skill_*``
  container (network disabled, read-only rootfs, nonce echo, removal observed);
* a fresh DB session re-reads the durable exact receipt.

There is deliberately no skip: a Docker-less host fails this test. Hosted CI
runs it in the existing ``backend-docker`` lane, which already requires Docker
and pulls ``python:3.11-slim``.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import AgentRegistry, SkillExecution, Tenant, User, Workspace
from tests.test_reviewed_executable_skill_agent_dispatch import (
    REQUEST,
    _ReflectionStub,
    _SimulatedDecisionModel,
    _WorldModelStub,
    _patch_full_run,
)
from tests.test_reviewed_executable_skill_docker import (
    BENIGN_CODE,
    EXPECTED_RESULT,
    PASSWORD,
    SYNTHETIC_INPUTS,
    _FakeScanner,
    _approve_via_public_route,
    _docker_unavailable_reason,
    _source_revision,
)

RESULT_PREFIX = "REVIEWED_EXECUTABLE_AGENT_DOCKER_ACCEPTANCE="


def _require_docker() -> None:
    reason = _docker_unavailable_reason()
    if reason is not None:
        pytest.fail(
            "the joined ordinary-agent Docker replay requires a reachable "
            f"Docker daemon: {reason}")


def test_joined_agent_loop_runs_in_real_docker(tmp_path, monkeypatch):
    _require_docker()

    from core.auth import get_password_hash
    from core.database import Base
    from core.reviewed_improvement import apply_reviewed_skill
    from core.skill_builder_service import SkillBuilderService
    from core.skill_registry_service import SkillRegistryService

    scratch = tmp_path / "joined-agent-docker"
    scratch.mkdir()
    db_path = scratch / "scratch.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()

    tenant_id = "tenant-joined-agent-docker"
    workspace_id = "ws-joined-agent-docker"
    agent_id = "agent-joined-agent-docker"
    user_id = "user-joined-agent-docker"
    viewer_id = "viewer-joined-agent-docker"
    email = "joined-agent@example.invalid"
    try:
        db.add_all([
            Tenant(id=tenant_id, name="Joined Agent Tenant",
                   subdomain="joined-agent-docker"),
            Workspace(id=workspace_id, name="Joined Agent Workspace",
                      tenant_id=tenant_id),
            AgentRegistry(
                id=agent_id, name="Joined Agent Employee",
                category="operations", module_path="core.generic_agent",
                class_name="GenericAgent", status="intern",
                confidence_score=0.5, configuration={}, capabilities=[],
                workspace_id=workspace_id, tenant_id=tenant_id),
            User(
                id=user_id, email=email,
                hashed_password=get_password_hash(PASSWORD),
                first_name="J", last_name="A", role="workspace_admin",
                status="active", workspace_id=workspace_id,
                tenant_id=tenant_id, is_active=True),
            User(
                id=viewer_id, email="joined-viewer@example.invalid",
                hashed_password=get_password_hash(PASSWORD),
                first_name="V", last_name="X", role="viewer",
                status="active", workspace_id=workspace_id,
                tenant_id=tenant_id, is_active=True),
        ])
        from core.auto_dev.models import SkillCandidate

        candidate = SkillCandidate(
            id=f"cand-joined-docker-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id, agent_id=agent_id,
            source_episode_id="episode-joined-agent-docker",
            skill_name="joined_docker_summarize_values",
            skill_description="deterministically summarize synthetic integers",
            generated_code=BENIGN_CODE,
            failure_pattern={"failure_summary": "joined docker replay"},
            validation_status="pending")
        db.add(candidate)
        db.commit()

        reviewer = db.query(User).filter(User.id == user_id).one()
        viewer = db.query(User).filter(User.id == viewer_id).one()
        approved = _approve_via_public_route(
            db, reviewer=reviewer, viewer=viewer, candidate_id=candidate.id)
        db.expire_all()
        candidate = db.query(SkillCandidate).filter(
            SkillCandidate.id == candidate.id).one()

        monkeypatch.setattr(
            "core.skill_registry_service.SkillSecurityScanner", _FakeScanner)
        applied = asyncio.run(apply_reviewed_skill(
            db, candidate, tenant_id=tenant_id, workspace_id=workspace_id,
            builder=SkillBuilderService(workspace_root=str(scratch / "skills")),
            registry=SkillRegistryService(db),
            executable=True,
        ))
        assert applied["generated_code_applied"] is True
        assert applied["review_digest"] == approved["review_digest"]

        row = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).one()
        _patch_full_run(monkeypatch, {"factory": factory})

        from core.generic_agent import GenericAgent

        agent = GenericAgent(row, workspace_id=workspace_id)
        agent.tenant_id = tenant_id
        model = _SimulatedDecisionModel(candidate.skill_name)
        agent.llm = model
        agent.world_model = _WorldModelStub()
        agent.reflection_service = _ReflectionStub()

        before = db.query(SkillExecution).count()
        result = asyncio.run(agent.execute(
            REQUEST, context={"user_id": user_id}))

        assert result["status"] == "success", result
        assert len(model.calls) == 2
        assert len(result["steps"]) == 2, result["steps"]
        tool_step = result["steps"][0]
        assert tool_step["action"]["tool"] == "skills.execute"
        assert tool_step["dispatch_evidence"]["dispatched"] is True
        observation = tool_step["output"]
        assert observation["success"] is True, observation
        assert json.loads(observation["result"]) == EXPECTED_RESULT
        execution_id = str(observation["execution_id"])

        assert "sum=26" in result["output"]
        assert f"execution_id={execution_id}" in result["output"]

        # Fresh session re-reads the durable exact receipt from the scratch
        # SQLite file after the ordinary agent run finished.
        verify = factory()
        try:
            assert verify.query(SkillExecution).count() == before + 1
            execution = verify.query(SkillExecution).filter(
                SkillExecution.id == execution_id).one()
            assert execution.status == "success"
            assert execution.agent_id == agent_id
            assert execution.skill_id == applied["skill_id"]
            assert execution.tenant_id == tenant_id
            assert execution.workspace_id == workspace_id
            assert execution.output_result["result"] == observation["result"]
            receipt = execution.audit_metadata["reviewed_executable"]
            assert receipt["status"] == "success"
            assert receipt["binding"]["verified"] is True
            assert receipt["binding"]["review_revision"] == (
                applied["review_revision"])
            assert receipt["binding"]["review_digest"] == (
                applied["review_digest"])
            assert receipt["binding"]["executable_code_sha256"] == (
                applied["executable_code_sha256"])
            assert receipt["binding"]["candidate_code_sha256"] == (
                applied["candidate_code_sha256"])
            assert receipt["binding"]["registry_execution_id"] == (
                applied["registry_execution_id"])
            assert receipt["executed_by"] == user_id
            sandbox = receipt["sandbox"]
            assert sandbox["backend"] == "docker"
            assert sandbox["ran"] is True
            assert sandbox["container_id"].startswith("skill_")
            assert sandbox["image"] == "python:3.11-slim"
            assert sandbox["network_disabled"] is True
            assert sandbox["read_only"] is True
            assert sandbox["ephemeral"] is True
            assert sandbox["removed"] is True
            assert not sandbox["cleanup_error"]
            assert sandbox["nonce"] == sandbox["nonce_echo"]
            assert execution.container_id == sandbox["container_id"]
        finally:
            verify.close()

        record = {
            "source_revision": _source_revision(),
            "model_decision_simulated": True,
            "model_detail": "deterministic joined ReAct decision stub",
            "docker_sandbox_real": True,
            "sandbox_backend": sandbox["backend"],
            "container_id": sandbox["container_id"],
            "image": sandbox["image"],
            "nonce_echo_verified": True,
            "result": json.loads(observation["result"]),
            "execution_id": execution_id,
            "registry_execution_id": applied["registry_execution_id"],
            "candidate_code_sha256": applied["candidate_code_sha256"],
            "executable_code_sha256": applied["executable_code_sha256"],
            "review_revision": applied["review_revision"],
            "review_digest": applied["review_digest"],
        }
        print(RESULT_PREFIX + json.dumps(record, sort_keys=True))
        output = os.getenv("ATOM_AGENT_DOCKER_ACCEPTANCE_OUTPUT")
        if output:
            Path(output).write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
    finally:
        db.close()
        engine.dispose()
