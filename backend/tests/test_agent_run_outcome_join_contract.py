"""Admitted execution outcome + trusted context join contracts.

The public run route, the real admission service, the real
``_dispatch_admitted_run`` wrapper and the real ``execute_agent_task`` leaf
are exercised against a scratch SQLite database. Only the GenericAgent
transport is doubled, so the evidence is about the caller/outcome/scope join
— not model quality or admission-policy qualification.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import api.agent_routes as agent_routes
from api.agent_routes import router as agent_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AgentExecution,
    AgentJob,
    AgentRegistry,
    AuditLog,
    Tenant,
    User,
    Workspace,
)


class _FakeGenericAgent:
    def __init__(self, agent_model, workspace_id="default", managed_overrides=None):
        self.agent = agent_model
        self.id = agent_model.id
        self.name = agent_model.name
        self.workspace_id = workspace_id
        self.managed_overrides = managed_overrides

    async def execute(self, task_input, context=None, step_callback=None):
        env = _FakeGenericAgent.env
        env.executions.append({
            "agent_id": self.agent.id,
            "workspace_id": self.workspace_id,
            "tenant_id": getattr(self, "tenant_id", None),
            "task_input": task_input,
            "context": dict(context or {}),
        })
        if step_callback is not None:
            await step_callback({"type": "observation", "output": "a step"})
        behavior = env.behavior
        if behavior is not None:
            return behavior(context or {})
        return env.result


class _WSManager:
    def __init__(self):
        self.calls = []

    async def broadcast(self, channel, message):
        self.calls.append((channel, message))


def _build_route_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/outcome-join.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    seed = SessionLocal()
    seed.add_all([
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Tenant(id="t2", name="Tenant Two", subdomain="tenant-two"),
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        Workspace(id="ws2", name="Workspace Two", tenant_id="t1"),
        Workspace(id="ws3", name="Workspace Three", tenant_id="t2"),
        User(
            id="member-1", tenant_id="t1", workspace_id="ws1",
            email="member@example.com", first_name="M", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="admin-2", tenant_id="t2", workspace_id="ws3",
            email="admin2@example.com", first_name="A", last_name="Two",
            role="admin", status="active", is_active=True),
        AgentRegistry(
            id="a1", name="Agent One", description="first",
            category="operations", module_path="agents.one",
            class_name="AgentOne", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws1", configuration={},
            enabled=True),
        AgentRegistry(
            id="a2", name="Agent Two", description="second",
            category="operations", module_path="agents.two",
            class_name="AgentTwo", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id="ws2", configuration={},
            enabled=True),
        AgentRegistry(
            id="a-global", name="Global Agent", description="unscoped",
            category="operations", module_path="agents.global",
            class_name="GlobalAgent", status="student",
            capabilities=[], promotion_episode_floor=None,
            tenant_id="t1", workspace_id=None, configuration={},
            enabled=True),
    ])
    seed.commit()
    seed.close()

    @contextmanager
    def _session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(agent_routes, "get_db_session", _session)

    world_model = MagicMock()
    world_model.recall_experiences = AsyncMock(
        return_value={"experiences": []})
    world_model.record_experience = AsyncMock()
    monkeypatch.setattr(
        agent_routes, "WorldModelService",
        MagicMock(return_value=world_model))

    ws = _WSManager()
    monkeypatch.setattr(agent_routes, "ws_manager", ws)
    notification = AsyncMock()
    monkeypatch.setattr(
        agent_routes.notification_manager,
        "send_urgent_notification", notification)

    state = SimpleNamespace(
        engine=engine,
        Session=SessionLocal,
        SessionLocal=SessionLocal,
        db_session=_session,
        executions=[],
        result={"status": "success", "output": "done"},
        behavior=None,
        ws=ws,
        notification=notification,
    )

    app = FastAPI()
    app.include_router(agent_router)

    def _db_override():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db_override
    state.app = app
    state.actors = {}
    for actor_id in ("member-1", "admin-2"):
        session = SessionLocal()
        try:
            state.actors[actor_id] = session.get(User, actor_id)
        finally:
            session.close()
    return state


@pytest.fixture()
def env(tmp_path, monkeypatch):
    state = _build_route_env(tmp_path, monkeypatch)
    fake_module = ModuleType("core.generic_agent")
    fake_module.GenericAgent = _FakeGenericAgent
    monkeypatch.setitem(sys.modules, "core.generic_agent", fake_module)
    _FakeGenericAgent.env = state
    yield state
    state.engine.dispose()


@pytest.fixture()
def real_env(tmp_path, monkeypatch):
    """Public route + real wrapper + real GenericAgent.

    Only the model/MCP transport (``_react_step``), the budget preflight and
    the unrelated episodic-memory model are doubled; the execution row and
    audit-bracket producers are the real ones.
    """
    state = _build_route_env(tmp_path, monkeypatch)
    import core.database as core_database
    import core.generic_agent as real_generic
    from core.episode_service import EpisodeService
    from core.react_models import ReActStep

    # Real GenericAgent and the action-audit writer open their own sessions
    # through core.database; point that seam at the same scratch database.
    monkeypatch.setattr(core_database, "get_db_session", state.db_session)
    monkeypatch.setattr(real_generic, "get_db_session", state.db_session)

    class _EpisodicWorldModel:
        def __init__(self, workspace_id="default"):
            self.workspace_id = workspace_id

        async def recall_experiences(self, *args, **kwargs):
            return {"experiences": []}

        async def record_experience(self, *args, **kwargs):
            return None

    async def _real_react_step(self, *args, **kwargs):
        return ReActStep(
            thought="plan", action=None, final_answer="real done")

    async def _budget_allowed(self, *args, **kwargs):
        return {"allowed": True}

    monkeypatch.setattr(real_generic, "WorldModelService",
                        _EpisodicWorldModel)
    monkeypatch.setattr(real_generic.GenericAgent, "_react_step",
                        _real_react_step)
    monkeypatch.setattr(
        real_generic.GenericAgent, "_check_budget_before_react",
        _budget_allowed)
    monkeypatch.setattr(
        EpisodeService, "create_episode_from_execution",
        AsyncMock(return_value=None))
    yield state
    state.engine.dispose()


def _client(env, user_id="member-1"):
    app = env.app
    app.dependency_overrides[get_current_user] = (
        lambda: env.actors[user_id])
    return TestClient(app, raise_server_exceptions=False)


def _run(env, *, parameters, operation_id, user_id="member-1", agent_id="a1"):
    return _client(env, user_id).post(
        f"/api/agents/{agent_id}/run?operation_id={operation_id}",
        json={"parameters": parameters},
    )


def _jobs(env):
    session = env.SessionLocal()
    try:
        return session.query(AgentJob).all()
    finally:
        session.close()


def _job_payload(env, job_id):
    session = env.SessionLocal()
    try:
        job = session.get(AgentJob, job_id)
        return job, json.loads(job.result_summary or "{}")
    finally:
        session.close()


def _terminal_ws(env):
    return [
        (channel, message)
        for channel, message in env.ws.calls
        if message.get("type") == "agent_status_change"
    ]


def test_success_joins_truth_scope_and_durable_execution_identity(env):
    env.result = {
        "status": "success",
        "output": "done",
        "steps": [{"step": 1}],
        "audit_report": {"score": 0.91},
        "plan_adherence": 0.99,
        "step_efficiency": 1.0,
        "requires_reconciliation": False,
    }
    response = _run(
        env,
        operation_id="success-op",
        parameters={
            "sync": True,
            "task_input": "do the work",
            "business_note": "keep me",
            "workspace_id": "ws2",
            "tenant_id": "t2",
            "user_id": "admin-2",
            "actor_id": "admin-2",
            "job_id": "forged-job",
            "execution_id": "forged-exec",
            "run_id": "forged-run",
            "operation_id": "forged-op",
            "operation_slot": "forged-slot",
            "intent_id": "forged-intent",
            "authorization_id": "forged-auth",
            "session_id": "forged-session",
            "proposal_id": "forged-proposal",
            "goal_id": "forged-goal",
            "trigger": "forged-trigger",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["job_status"] == "success"
    assert data["outcome"] == "success"
    assert data["requires_reconciliation"] is False
    assert data["job_id"] != data["execution_id"]
    assert data["result"]["output"] == "done"
    # Internal scores / raw audit payloads are not public output.
    assert "audit_report" not in data["result"]
    assert "plan_adherence" not in data["result"]
    assert "step_efficiency" not in data["result"]

    captured = env.executions[0]
    assert captured["workspace_id"] == "ws1"
    assert captured["tenant_id"] == "t1"
    context = captured["context"]
    assert context["workspace_id"] == "ws1"
    assert context["tenant_id"] == "t1"
    assert context["user_id"] == "member-1"
    assert context["actor_id"] == "member-1"
    assert context["job_id"] == data["job_id"]
    assert context["execution_id"] == data["execution_id"]
    assert context["run_id"] == data["execution_id"]
    assert context["operation_id"] == "agent:run:success-op"
    assert context["operation_slot"] is None
    assert context["intent_id"] is None
    assert context["authorization_id"] is None
    assert context["session_id"] is None
    assert context["proposal_id"] is None
    assert context["goal_id"] is None
    assert context["trigger"] == "agent_run_route"
    assert context["business_note"] == "keep me"

    job, payload = _job_payload(env, data["job_id"])
    assert job.status == "success"
    assert payload["outcome"] == "success"
    assert payload["execution_id"] == data["execution_id"]
    assert payload["finished"] is True
    serialized = json.dumps(payload)
    for forged in (
        "forged-job", "forged-exec", "forged-run", "forged-op",
        "forged-slot", "ws2", "t2", "admin-2",
    ):
        assert forged not in serialized

    terminal = _terminal_ws(env)
    assert terminal
    channels = {channel for channel, _ in terminal}
    assert "workspace:ws1" in channels
    assert "user:member-1" in channels
    assert "workspace:default" not in channels
    messages = [message for _, message in terminal]
    assert all(message["status"] == "success" for message in messages)
    assert all(message["outcome"] == "success" for message in messages)
    assert all(message["job_id"] == data["job_id"] for message in messages)
    assert all(
        message["execution_id"] == data["execution_id"]
        for message in messages)
    assert all(
        message["workspace_id"] == "ws1" for message in messages)
    assert all(
        message["tenant_id"] == "t1" for message in messages)
    assert all("audit_report" not in json.dumps(message)
               for message in messages)
    assert messages[0]["result"]["output"] == "done"
    assert all(
        channel != "workspace:default" for channel, _ in env.ws.calls)

    capture_path = os.environ.get("ATOM_OUTCOME_CAPTURE_PATH")
    if capture_path:
        Path(capture_path).write_text(
            json.dumps({
                "public_response": data,
                "generic_constructor": {
                    "workspace_id": captured["workspace_id"],
                    "tenant_id": captured["tenant_id"],
                },
                "generic_context": context,
                "durable_job": payload,
                "ws_channels": sorted(
                    {channel for channel, _ in env.ws.calls}),
                "ws_terminal": messages[0],
            }, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )


@pytest.mark.parametrize(
    "result,expected_outcome,expected_code,expected_next,requires",
    [
        ({"status": "uncertain", "requires_reconciliation": True},
         "uncertain", "AGENT_EXECUTION_UNCERTAIN",
         "reconcile_operation", True),
        ({"status": "failed", "output": "internal detail"},
         "failed", "AGENT_EXECUTION_NOT_SUCCESSFUL",
         "review_failure", False),
        ({"status": "blocked"}, "blocked",
         "AGENT_EXECUTION_NOT_SUCCESSFUL", "resolve_blocker", False),
        ({"status": "cancelled"}, "cancelled",
         "AGENT_EXECUTION_NOT_SUCCESSFUL", "none", False),
        ({"status": "waiting"}, "waiting",
         "AGENT_EXECUTION_NOT_SUCCESSFUL", "review_execution", False),
        ({"output": "no status"}, "unknown",
         "AGENT_EXECUTION_NOT_SUCCESSFUL", "review_execution", False),
        ({}, "unknown", "AGENT_EXECUTION_NOT_SUCCESSFUL",
         "review_execution", False),
        ({"status": "success", "success": False},
         "contradictory", "AGENT_EXECUTION_UNCERTAIN",
         "reconcile_operation", True),
        ({"status": "success", "requires_reconciliation": True},
         "success", "AGENT_EXECUTION_UNCERTAIN",
         "reconcile_operation", True),
    ],
)
def test_non_success_matrix_never_completes_a_job(
    env, result, expected_outcome, expected_code, expected_next, requires,
):
    env.result = result
    response = _run(
        env,
        operation_id="matrix-op",
        parameters={"sync": True, "task_input": "work"},
    )
    assert response.status_code != 200, response.text
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error"]["code"] == expected_code
    assert detail["data"]["outcome"] == expected_outcome
    assert detail["data"]["next_action"] == expected_next
    assert detail["data"]["requires_reconciliation"] is requires

    job, payload = _job_payload(env, detail["data"]["job_id"])
    assert job.status != "success"
    assert payload["outcome"] == expected_outcome
    assert payload["next_action"] == expected_next
    assert payload["requires_reconciliation"] is requires
    assert "internal detail" not in json.dumps(payload)

    terminal = _terminal_ws(env)
    assert terminal
    messages = [message for _, message in terminal]
    assert all(message["status"] != "success" for message in messages)
    assert all(message["outcome"] == expected_outcome
               for message in messages)
    assert all("result" not in message for message in messages)
    assert all(message.get("error") for message in messages)
    assert all("audit_report" not in json.dumps(message)
               for message in messages)


def test_replay_and_cold_read_do_not_dispatch_again(env):
    first = _run(
        env,
        operation_id="replay-op",
        parameters={"sync": True, "task_input": "same"},
    )
    assert first.status_code == 200, first.text
    job_id = first.json()["data"]["job_id"]
    execution_id = first.json()["data"]["execution_id"]

    replay = _run(
        env,
        operation_id="replay-op",
        parameters={"sync": True, "task_input": "same"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == (
        "already_applied")
    assert replay.json()["data"]["execution_id"] == execution_id
    assert replay.json()["data"]["outcome"] == "success"
    assert replay.json()["data"]["requires_reconciliation"] is False
    assert len(env.executions) == 1
    assert len(_jobs(env)) == 1

    changed = _run(
        env,
        operation_id="replay-op",
        parameters={"sync": True, "task_input": "different"},
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == (
        "OPERATION_CONFLICT")
    assert len(env.executions) == 1

    # Cold read through a brand-new session preserves the required state.
    session = env.SessionLocal()
    try:
        job = session.get(AgentJob, job_id)
        payload = json.loads(job.result_summary or "{}")
    finally:
        session.close()
    assert job.status == "success"
    assert payload["execution_id"] == execution_id
    assert payload["outcome"] == "success"


def test_continued_read_preserves_running_state(env):
    session = env.SessionLocal()
    try:
        session.add(AgentJob(
            id="running-job", agent_id="a1", status="running",
            result_summary=json.dumps({
                "dispatch_execution_id": "exec-live",
            })))
        session.commit()
    finally:
        session.close()

    view = agent_routes._job_outcome_projection(
        "running-job", env.engine)
    assert view["job_status"] == "running"
    assert view["outcome"] == "in_progress"
    assert view["next_action"] == "await_completion"
    assert view["execution_id"] == "exec-live"


def test_unscoped_agent_uses_the_scoped_actor_workspace(env):
    response = _run(
        env,
        agent_id="a-global",
        operation_id="global-agent-op",
        parameters={"sync": True, "task_input": "work"},
    )
    assert response.status_code == 200, response.text
    assert env.executions[0]["workspace_id"] == "ws1"
    assert env.executions[0]["context"]["workspace_id"] == "ws1"
    assert env.executions[0]["context"]["tenant_id"] == "t1"


def test_backed_wait_is_non_terminal_and_does_not_consume_the_slot(env):
    env.result = {
        "status": "waiting",
        "waiting_for": "the customer's account id",
        "hitl_action_id": "act-wait-42",
        "requires_reconciliation": False,
    }
    response = _run(
        env,
        operation_id="wait-op",
        parameters={"sync": True, "task_input": "long task"},
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["job_status"] == "waiting"
    assert data["outcome"] == "waiting"
    assert data["next_action"] == "await_information"
    assert data["requires_reconciliation"] is False
    assert data["wait_receipt"]["hitl_action_id"] == "act-wait-42"
    assert data["wait_receipt"]["waiting_for"] == (
        "the customer's account id")

    job, payload = _job_payload(env, data["job_id"])
    assert job.status == "waiting"
    assert payload["waiting"] is True
    assert payload["finished"] is False
    assert payload["wait_receipt"]["hitl_action_id"] == "act-wait-42"
    assert job.end_time is None

    terminal = _terminal_ws(env)
    assert terminal
    messages = [message for _, message in terminal]
    assert all(message["status"] == "waiting" for message in messages)
    assert all("result" not in message for message in messages)
    assert all("error" not in message for message in messages)
    assert all(message["wait_receipt"]["hitl_action_id"] == "act-wait-42"
               for message in messages)

    # A wait does not occupy the single active-run allowance; unrelated new
    # work can still be admitted while the original task stays resumable.
    replay = _run(
        env,
        operation_id="wait-op",
        parameters={"sync": True, "task_input": "long task"},
    )
    assert replay.status_code == 202, replay.text
    assert replay.json()["data"]["job_status"] == "waiting"
    assert len(env.executions) == 1

    env.result = {"status": "success", "output": "next work"}
    second = _run(
        env,
        operation_id="after-wait-op",
        parameters={"sync": True, "task_input": "other work"},
    )
    assert second.status_code == 200, second.text
    assert len(env.executions) == 2
    jobs = _jobs(env)
    assert len(jobs) == 2
    assert {job.agent_id for job in jobs} == {"a1"}


def test_foreign_scope_is_refused_before_any_dispatch(env):
    response = _run(
        env,
        operation_id="foreign-op",
        parameters={"sync": True},
        agent_id="a2",
    )
    assert response.status_code == 404, response.text
    assert env.executions == []
    assert _jobs(env) == []

    forged = _run(
        env,
        operation_id="forged-scope-op",
        parameters={
            "sync": True,
            "workspace_id": "ws2",
            "tenant_id": "t2",
            "user_id": "admin-2",
        },
    )
    assert forged.status_code == 200, forged.text
    assert env.executions[0]["context"]["workspace_id"] == "ws1"
    assert env.executions[0]["context"]["tenant_id"] == "t1"
    assert env.executions[0]["context"]["user_id"] == "member-1"


def test_late_success_cannot_overwrite_peer_cancellation(env):
    def cancel_then_succeed(context):
        session = env.SessionLocal()
        try:
            job = session.get(AgentJob, context["job_id"])
            job.status = "cancelled"
            session.commit()
        finally:
            session.close()
        return {"status": "success", "output": "late success"}

    env.behavior = cancel_then_succeed
    response = _run(
        env,
        operation_id="cancel-race-op",
        parameters={"sync": True, "task_input": "work"},
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["data"]["outcome"] == "cancelled"
    assert detail["data"]["next_action"] == "none"

    job, payload = _job_payload(env, detail["data"]["job_id"])
    assert job.status == "cancelled"
    assert payload.get("outcome") != "success"
    terminal = _terminal_ws(env)
    assert terminal
    assert all(message["status"] != "success"
               for _, message in terminal)
    assert all(message["outcome"] == "cancelled"
               for _, message in terminal)


def test_duplicate_dispatch_claims_one_run_slot(env):
    session = env.SessionLocal()
    try:
        job = AgentJob(id="race-job", agent_id="a1", status="pending")
        session.add(job)
        session.commit()
    finally:
        session.close()

    async def both():
        return await asyncio.gather(
            agent_routes._dispatch_admitted_run(
                "a1", {"task_input": "x"}, "race-job", "student",
                env.engine),
            agent_routes._dispatch_admitted_run(
                "a1", {"task_input": "x"}, "race-job", "student",
                env.engine),
        )

    results = asyncio.run(both())
    assert len(env.executions) == 1
    assert sum(result is not None for result in results) == 1
    job, payload = _job_payload(env, "race-job")
    assert job.status == "success"
    assert payload["outcome"] == "success"


def test_execution_exception_is_failed_without_public_leak(env):
    secret = "provider-secret-sk-live-123"

    def explode(context):
        raise RuntimeError(f"provider failed: {secret}")

    env.behavior = explode
    response = _run(
        env,
        operation_id="error-op",
        parameters={"sync": True, "task_input": "work"},
    )
    assert response.status_code == 409, response.text
    jobs = _jobs(env)
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert secret not in response.text
    assert secret not in (jobs[0].result_summary or "")
    assert secret not in json.dumps(env.ws.calls, default=str)
    assert env.notification.await_count == 1
    notification_kwargs = env.notification.await_args.kwargs
    assert secret not in notification_kwargs["message"]


def test_stale_dispatcher_cannot_finish_the_winning_run_slot(env):
    session = env.SessionLocal()
    try:
        session.add(AgentJob(
            id="winner-job", agent_id="a1", status="running",
            result_summary=json.dumps({
                "dispatch_execution_id": "winner-exec",
                "operation_id": "agent:run:winner",
            })))
        session.commit()
    finally:
        session.close()

    success = agent_routes._execution_outcome({
        "status": "success", "output": "winner output"})
    stale_status = agent_routes._finish_job(
        "winner-job", success, env.engine,
        execution_id="stale-exec", agent_id="a1")
    assert stale_status == "running"
    job, payload = _job_payload(env, "winner-job")
    assert job.status == "running"
    assert "outcome" not in payload

    winner_status = agent_routes._finish_job(
        "winner-job", success, env.engine,
        execution_id="winner-exec", agent_id="a1")
    assert winner_status == "success"
    job, payload = _job_payload(env, "winner-job")
    assert job.status == "success"
    assert payload["outcome"] == "success"


def test_changed_parameters_after_admission_are_refused(env):
    from core.agent_decision_write_service import _canonical, _fingerprint

    expected = _fingerprint(
        "agent-run-parameters", _canonical({"task_input": "admitted"}))
    session = env.SessionLocal()
    try:
        session.add(AgentJob(
            id="digest-job", agent_id="a1", status="running",
            result_summary=json.dumps({
                "parameters_digest": expected,
            })))
        session.commit()
    finally:
        session.close()

    result = asyncio.run(agent_routes._dispatch_admitted_run(
        "a1", {"task_input": "changed"}, "digest-job", "student",
        env.engine))
    assert result is None
    assert env.executions == []
    job, payload = _job_payload(env, "digest-job")
    assert job.status == "failed"
    assert payload["reason"] == "admission_material_changed"
    assert payload["next_action"] == "refresh_required_state"


def test_receipt_freezes_original_actor_and_workspace(env):
    response = _run(
        env,
        operation_id="receipt-op",
        parameters={"sync": True, "task_input": "work"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    # Another active actor cannot borrow the same admitted job.
    foreign = agent_routes._trusted_execution_context(
        env.engine,
        agent_id="a1",
        job_id=data["job_id"],
        actor_id="admin-2",
        execution_id="borrowed-exec",
    )
    assert foreign is None

    # A later agent/workspace move cannot relabel the admitted run.
    session = env.SessionLocal()
    try:
        agent = session.get(AgentRegistry, "a1")
        agent.workspace_id = "ws2"
        session.commit()
    finally:
        session.close()
    frozen = agent_routes._trusted_execution_context(
        env.engine,
        agent_id="a1",
        job_id=data["job_id"],
        actor_id="member-1",
        execution_id="frozen-exec",
    )
    assert frozen is not None
    assert frozen["workspace_id"] == "ws1"
    assert frozen["tenant_id"] == "t1"
    assert frozen["actor_id"] == "member-1"


def test_inactive_admission_actor_refuses_dispatch(env):
    session = env.SessionLocal()
    try:
        job = AgentJob(id="authority-job", agent_id="a1", status="pending")
        session.add(job)
        actor = session.get(User, "member-1")
        actor.is_active = False
        actor.status = "inactive"
        session.commit()
    finally:
        session.close()

    result = asyncio.run(agent_routes._dispatch_admitted_run(
        "a1", {"task_input": "x"}, "authority-job", "student",
        env.engine, actor_id="member-1"))
    assert result is None
    assert env.executions == []
    job, payload = _job_payload(env, "authority-job")
    assert job.status == "failed"
    assert payload["reason"] == "execution_authority_unavailable"
    assert payload["next_action"] == "refresh_required_state"


def test_real_generic_agent_binds_execution_and_audit_identity(real_env):
    response = _run(
        real_env,
        operation_id="real-generic-op",
        parameters={"sync": True, "task_input": "real work"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["job_status"] == "success"
    assert data["result"]["output"] == "real done"
    assert data["execution_id"] != data["job_id"]

    session = real_env.SessionLocal()
    try:
        execution = session.get(AgentExecution, data["execution_id"])
        assert execution is not None
        assert execution.workspace_id == "ws1"
        assert execution.tenant_id == "t1"
        assert execution.status == "success"
        audits = session.query(AuditLog).filter(
            AuditLog.metadata_json.like(
                f'%"agent_execution_id": "{data["execution_id"]}"%')
        ).all()
        assert audits, "audit bracket must use the canonical execution id"
        capture = {
            "public_response": data,
            "agent_execution": {
                "id": execution.id,
                "agent_id": execution.agent_id,
                "workspace_id": execution.workspace_id,
                "tenant_id": execution.tenant_id,
                "status": execution.status,
            },
            "audit_execution_ids": sorted({
                json.loads(row.metadata_json).get("agent_execution_id")
                for row in audits
            }),
            "audit_row_count": len(audits),
        }
    finally:
        session.close()

    capture_path = os.environ.get("ATOM_REAL_CONSUMER_CAPTURE_PATH")
    if capture_path:
        Path(capture_path).write_text(
            json.dumps(capture, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8")

    job, payload = _job_payload(real_env, data["job_id"])
    assert job.status == "success"
    assert payload["execution_id"] == data["execution_id"]
    assert payload["outcome"] == "success"


def test_background_run_uses_the_same_truthful_join(env):
    response = _run(
        env,
        operation_id="background-op",
        parameters={"task_input": "work"},
    )
    assert response.status_code == 200, response.text
    assert "started" in response.json()["message"].lower()
    jobs = _jobs(env)
    assert len(jobs) == 1
    assert jobs[0].status == "success"
    assert len(env.executions) == 1
