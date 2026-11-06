"""Agent 3 independent probes for merged PR675 run admission (2026-11-06).

Independent review of the merged #675 admission contract at main ``33b8d6472``
(squash of ``codex/oracle01-agent-run-20261106``, PR head ``684f1a2c6``).
Reuses the submitted suite's environment fixture unchanged and adds only the
interleavings the submitted controls do not cover:

1. target ``enabled``/``configuration`` change before the guarded claim
   (the submitted suite covers a ``name`` change only);
2. a losing admission whose target was claimed by a concurrent winner
   between load and claim must leave zero trace (no job, no audit, no
   dispatch) while the winner's state is preserved;
3. replay after the lifecycle completed acknowledges the original result via
   fresh-session durable state without a second dispatch, and the durable job
   receipt carries only the operation id and parameters digest.

Execution is stubbed at the documented leaf (``api.agent_routes.execute_agent_task``).
Qualifies admission and lifecycle handoff only — not real model work.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import update

from core.models import AgentJob, AgentRegistry, AuditLog

from tests.test_agent_run_admission_contract import env as _env

env = _env


def _agent(env, agent_id):
    db = env.Session()
    try:
        return db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
    finally:
        db.close()


def _jobs(env, agent_id=None):
    db = env.Session()
    try:
        query = db.query(AgentJob)
        if agent_id is not None:
            query = query.filter(AgentJob.agent_id == agent_id)
        return query.all()
    finally:
        db.close()


def _audits(env, operation_id=None):
    db = env.Session()
    try:
        query = db.query(AuditLog)
        if operation_id is not None:
            query = query.filter(AuditLog.id == operation_id)
        return query.all()
    finally:
        db.close()


def _run(env, user_id, agent_id, operation_id=None, parameters=None):
    suffix = f"?operation_id={operation_id}" if operation_id else ""
    return env.client(env.actors[user_id]).post(
        f"/api/agents/{agent_id}/run{suffix}",
        json={"parameters": parameters or {}})


def test_enabled_and_configuration_change_before_claim_refuses(env):
    """Peer flips enabled/configuration between load and guarded claim."""
    import core.agent_decision_write_service as service

    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if row is not None and agent_id == "a1" and not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(AgentRegistry).where(
                    AgentRegistry.id == "a1").values(
                        enabled=False,
                        configuration={"secret": "PEER-CHANGED"}))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _run(env, "admin-1", "a1", "agent3-stale-material")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    now = _agent(env, "a1")
    assert now.enabled is False
    assert now.configuration == {"secret": "PEER-CHANGED"}
    assert now.status == "student"
    assert _jobs(env) == []
    assert _audits(env) == []
    assert len(env.dispatch_calls) == 0


def test_concurrent_winner_preserved_losing_admission_traceless(env):
    """A winner claim between load and claim loses cleanly: ALREADY_RUNNING,
    winner status preserved, and the loser emits no job, audit or dispatch."""
    import core.agent_decision_write_service as service

    original = service._load_agent
    changed = {"done": False}

    def load_then_win(db, agent_id):
        row = original(db, agent_id)
        if row is not None and agent_id == "a1" and not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(AgentRegistry).where(
                    AgentRegistry.id == "a1").values(status="running"))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(service, "_load_agent", load_then_win)
    loser = _run(env, "admin-1", "a1", "agent3-loser")
    assert loser.status_code == 409, loser.text
    assert loser.json()["detail"]["error"]["code"] == "ALREADY_RUNNING"
    assert _agent(env, "a1").status == "running"
    assert _jobs(env) == []
    assert _audits(env) == []
    assert len(env.dispatch_calls) == 0


def test_replay_after_completion_acknowledges_without_redispatch(env):
    """Replay after lifecycle completion acknowledges the durable original:
    no second dispatch, one job, one audit, no raw parameters in the job
    receipt, tenant scope bound to the target."""
    first = _run(
        env, "admin-1", "a1", "agent3-replay", {"task_input": "once"})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["verification"]["status"] == "verified"

    jobs = _jobs(env, "a1")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.status == "success"
    assert job.tenant_id == "t1"
    payload = json.loads(job.result_summary or "{}")
    assert payload["operation_id"] == "agent:run:agent3-replay"
    assert payload["parameters_digest"]
    assert "once" not in job.result_summary

    replay = _run(
        env, "admin-1", "a1", "agent3-replay", {"task_input": "once"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == (
        "already_applied")
    assert replay.json()["data"]["verification"].get("replay") == (
        "do_not_repeat")
    assert len(_jobs(env, "a1")) == 1
    assert len(_audits(env, "agent:run:agent3-replay")) == 1
    assert len(env.dispatch_calls) == 1
    assert _agent(env, "a1").status == "student"
