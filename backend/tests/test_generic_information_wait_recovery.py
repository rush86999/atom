"""Selection/authority controls for the accepted-information wait recovery.

These are fast in-process controls around the exact durable-row checks. The
actual process restart/answer paths are covered separately by
``test_agent_generic_information_wait_process.py``.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.database as database
from core.models import (
    AgentExecution,
    AgentJob,
    AgentRegistry,
    Base,
    HITLAction,
    Tenant,
    User,
    Workspace,
)

ANSWER = "Quarterly close checklist"


@pytest.fixture
def world(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recovery.db'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(database, "engine", engine)
    with Session() as db:
        db.add_all([
            Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
            Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
            User(
                id="member-1", tenant_id="t1", workspace_id="ws1",
                email="member@example.com", first_name="M", last_name="One",
                role="member", status="active", is_active=True),
            AgentRegistry(
                id="a1", name="Agent One", description="first",
                category="operations", module_path="agents.one",
                class_name="AgentOne", status="autonomous",
                capabilities=[], tenant_id="t1", workspace_id="ws1",
                enabled=True),
        ])
        db.commit()
    return SimpleNamespace(engine=engine, SessionLocal=Session)


def _wait(
    world,
    *,
    status="approved",
    feedback=ANSWER,
    job_status="waiting",
    execution_status="waiting",
    action_type="agent_information_request",
    workspace_id="ws1",
    tenant_id="t1",
    agent_id="a1",
    answer_present=True,
    resume_claim=False,
    claim_owner=None,
    owner=None,
):
    job_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    action_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    subject = {
        "job_id": job_id,
        "execution_id": execution_id,
        "agent_id": agent_id,
        "workspace_id": workspace_id,
    }
    payload = {
        "execution_id": execution_id,
        "dispatch_execution_id": execution_id,
        "wait_receipt": {
            "hitl_action_id": action_id,
            "correlation_id": correlation_id,
            "verified": True,
            "kind": "information_request",
        },
        "resume_parameters": {"sync": True, "task_input": "create a task"},
    }
    if resume_claim:
        payload["resume_claim"] = {
            "action_id": action_id,
            "execution_id": execution_id,
        }
        if claim_owner is not None:
            payload["resume_claim"]["claim_owner"] = claim_owner
    snapshot = {
        "job_id": job_id,
        "execution_id": execution_id,
        "run_id": execution_id,
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "actor_id": "member-1",
        "user_id": "member-1",
        "correlation_id": correlation_id,
        "channel": "user:member-1",
        "question": "What title?",
        "subject": subject,
    }
    params = {
        "question": "What title?",
        "subject": subject,
        "correlation_id": correlation_id,
        "channel": "user:member-1",
    }
    metadata = {}
    if owner is not None:
        metadata["owner"] = owner
    with world.SessionLocal() as db:
        db.add(AgentJob(
            id=job_id, tenant_id=tenant_id, agent_id=agent_id,
            status=job_status, result_summary=json.dumps(payload)))
        db.add(AgentExecution(
            id=execution_id, agent_id=agent_id, workspace_id=workspace_id,
            tenant_id=tenant_id, status=execution_status,
            metadata_json=metadata))
        db.add(HITLAction(
            id=action_id, workspace_id=workspace_id, tenant_id=tenant_id,
            agent_id=agent_id, user_id="member-1",
            action_type=action_type, platform="internal", params=params,
            reason="What title?", status=status,
            user_feedback=(feedback if answer_present else None),
            context_snapshot=snapshot))
        db.commit()
    return SimpleNamespace(
        job_id=job_id, execution_id=execution_id, action_id=action_id,
        correlation_id=correlation_id)


def _recover(monkeypatch, calls=None):
    from api import agent_routes

    calls = calls if calls is not None else []

    async def spy(action_id, **kwargs):
        calls.append({"action_id": action_id, **kwargs})
        return {"handled": True, "resumed": True, "job_status": "success"}

    monkeypatch.setattr(agent_routes, "resume_information_wait_action", spy)
    from core.information_wait import recover_accepted_information_waits

    result = asyncio.run(recover_accepted_information_waits())
    return result, calls


def test_recovery_refuses_unbound_unapproved_or_foreign_waits(
        world, monkeypatch):
    _wait(world, answer_present=False)
    _wait(world, status="pending")
    _wait(world, status="rejected")
    _wait(world, status="expired")
    _wait(world, job_status="cancelled")
    _wait(world, workspace_id="foreign-ws")
    _wait(world, action_type="send_message", status="approved")

    result, calls = _recover(monkeypatch)

    assert calls == [], "no invalid wait may reach the resume consumer"
    assert result["resumed"] == 0, result
    reasons = {item.get("reason") for item in result["details"]}
    assert "wait_binding_or_answer_missing" in reasons, result
    assert "workspace_mismatch" in reasons, result


def test_recovery_refuses_an_old_wait_that_is_not_the_current_receipt(
        world, monkeypatch):
    target = _wait(world)
    with world.SessionLocal() as db:
        job = db.get(AgentJob, target.job_id)
        payload = json.loads(job.result_summary)
        payload["wait_receipt"]["hitl_action_id"] = str(uuid.uuid4())
        job.result_summary = json.dumps(payload)
        db.commit()

    result, calls = _recover(monkeypatch)

    assert calls == [], "an old settled wait must not answer the current one"
    assert result["resumed"] == 0, result
    assert result["examined"] == 0, result
    assert result["details"] == [], result


def test_recovery_does_not_rebuild_missing_scope_from_the_action_row(
        world, monkeypatch):
    target = _wait(world)
    with world.SessionLocal() as db:
        action = db.get(HITLAction, target.action_id)
        snapshot = dict(action.context_snapshot)
        snapshot.pop("workspace_id")
        action.context_snapshot = snapshot
        db.commit()

    result, calls = _recover(monkeypatch)

    assert calls == [], "a partial snapshot must not gain authority from the row"
    assert result["resumed"] == 0, result
    assert result["details"][0]["reason"] == "wait_binding_or_answer_missing", (
        result)


def test_recovery_refuses_an_unavailable_actor(world, monkeypatch):
    _wait(world)
    with world.SessionLocal() as db:
        user = db.get(User, "member-1")
        user.is_active = False
        db.commit()

    result, calls = _recover(monkeypatch)

    assert calls == [], "a deactivated principal must not resume on startup"
    assert result["resumed"] == 0, result
    assert result["details"][0]["reason"] == "actor_unavailable", result


def test_recovery_skips_an_already_terminal_job(world, monkeypatch):
    _wait(world, job_status="success", execution_status="completed")

    result, calls = _recover(monkeypatch)

    assert calls == [], result
    assert result["resumed"] == 0, result
    assert result["examined"] == 0, result
    assert result["details"] == [], result
    with world.SessionLocal() as db:
        job = db.query(AgentJob).one()
        assert job.status == "success"


def test_recovery_selects_a_new_wait_behind_twenty_terminal_waits(
        world, monkeypatch):
    """Terminal approved history must not starve the 21st accepted wait."""
    for _ in range(20):
        _wait(world, job_status="success", execution_status="completed")
    target = _wait(world)

    result, calls = _recover(monkeypatch)

    assert result["examined"] == 1, result
    assert result["resumed"] == 1, result
    assert [call["action_id"] for call in calls] == [target.action_id], calls
    with world.SessionLocal() as db:
        historical = db.query(HITLAction).filter(
            HITLAction.id != target.action_id).all()
        assert len(historical) == 20
        assert {row.status for row in historical} == {"approved"}


def test_recovery_marks_dead_claimed_resume_uncertain_without_resend(
        world, monkeypatch):
    target = _wait(
        world, job_status="running", execution_status="waiting",
        resume_claim=True,
        claim_owner={
            "pid": 999999,
            "token": "dead",
            "host": socket.gethostname(),
        },
        owner={"pid": 999999, "token": "dead", "host": "test"})

    result, calls = _recover(monkeypatch)

    assert calls == [], "an uncertain interruption must never be re-dispatched"
    assert result["resumed"] == 0, result
    assert result["uncertain"] == 1, result
    detail = result["details"][0]
    assert detail["status"] == "uncertain", detail
    assert detail["reason"] == "resume_claim_interrupted_uncertain", detail
    with world.SessionLocal() as db:
        job = db.get(AgentJob, target.job_id)
        assert job.status == "failed", job.status
        payload = json.loads(job.result_summary)
        assert payload["requires_reconciliation"] is True, payload
        assert payload["reason"] == "execution_uncertain", payload
        execution = db.get(AgentExecution, target.execution_id)
        assert execution.status == "failed", execution.status
        assert execution.metadata_json["recovery"]["reason"] == (
            "resume_claim_interrupted_uncertain")


def test_recovery_leaves_a_live_concurrent_claim_owner_alone(world, monkeypatch):
    """A successor actively resuming must not be mistaken for a crash."""
    target = _wait(
        world, job_status="running", execution_status="waiting",
        resume_claim=True,
        claim_owner={
            "pid": os.getpid(),
            "token": "peer-process",
            "host": socket.gethostname(),
        },
        owner={"pid": 999999, "token": "original-waiter", "host": "test"})

    result, calls = _recover(monkeypatch)

    assert calls == [], result
    assert result["resumed"] == 0, result
    assert result["uncertain"] == 0, result
    detail = result["details"][0]
    assert detail["reason"] == "live_owner", detail
    assert detail["owner_source"] == "resume_claim", detail
    with world.SessionLocal() as db:
        job = db.get(AgentJob, target.job_id)
        assert job.status == "running", job.status
        execution = db.get(AgentExecution, target.execution_id)
        assert execution.status == "waiting", execution.status


@pytest.mark.parametrize(
    "owner_state, expected_reason",
    [("live", "live_owner"), ("unknown", "unknown_owner")])
def test_recovery_leaves_live_or_unknown_claimed_owner_alone(
        world, monkeypatch, owner_state, expected_reason):
    target = _wait(
        world, job_status="running", execution_status="waiting",
        resume_claim=True,
        owner={"pid": os.getpid(), "token": "owner", "host": "test"})

    import core.execution_ownership as ownership

    monkeypatch.setattr(
        ownership, "owner_liveness",
        lambda metadata: (owner_state, {"pid": 4242, "host": "test"}))

    result, calls = _recover(monkeypatch)

    assert calls == [], result
    assert result["resumed"] == 0, result
    assert result["uncertain"] == 0, result
    assert result["details"][0]["reason"] == expected_reason, result
    with world.SessionLocal() as db:
        job = db.get(AgentJob, target.job_id)
        assert job.status == "running", job.status
        payload = json.loads(job.result_summary)
        assert "requires_reconciliation" not in payload, payload
        execution = db.get(AgentExecution, target.execution_id)
        assert execution.status == "waiting", execution.status
