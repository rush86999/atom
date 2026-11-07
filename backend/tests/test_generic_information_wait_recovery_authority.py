"""Authority controls for startup recovery of accepted information waits.

The defect under test is late authority drift: an answer is durably accepted,
the process dies before the resume claim, and the original actor is then moved
to another workspace, demoted out of ``AGENT_RUN`` or otherwise made
unavailable. Startup recovery must not dispatch the descendant run under the
old frozen workspace on the strength of the already-approved wait row.

These are real scratch-SQLite rows through the production startup helper and
the real ``resume_information_wait_action`` consumer. Only the descendant
dispatch boundary (``execute_agent_task``) is doubled, so the test can prove
whether any model/tool work was started; authority checks and the durable
job/execution writes are the production ones.
"""
from __future__ import annotations

import asyncio
import json
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
# The real public-route/Generic fixture is shared with the existing wait test.
from tests.test_agent_generic_information_wait import real_env  # noqa: F401

ANSWER = "Quarterly close checklist"


@pytest.fixture
def world(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recovery-authority.db'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(database, "engine", engine)
    with Session() as db:
        db.add_all([
            Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
            Tenant(id="t2", name="Tenant Two", subdomain="tenant-two"),
            Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
            Workspace(id="ws2", name="Workspace Two", tenant_id="t1"),
            User(
                id="member-1", tenant_id="t1", workspace_id="ws1",
                email="member@example.com", first_name="M", last_name="One",
                role="member", status="active", is_active=True),
            User(
                id="admin-1", tenant_id="t1", workspace_id="ws1",
                email="admin@t1.example.com", first_name="A", last_name="One",
                role="admin", status="active", is_active=True),
            # Personal Edition bootstrap shape: both scope columns are NULL.
            User(
                id="personal-admin", tenant_id=None, workspace_id=None,
                email="admin@example.com", first_name="A", last_name="User",
                role="workspace_admin", status="active", is_active=True),
            AgentRegistry(
                id="a1", name="Agent One", description="first",
                category="operations", module_path="agents.one",
                class_name="AgentOne", status="autonomous",
                capabilities=[], tenant_id="t1", workspace_id="ws1",
                configuration={}, enabled=True),
            AgentRegistry(
                id="personal-agent", name="Personal Agent", description="p",
                category="operations", module_path="agents.personal",
                class_name="PersonalAgent", status="autonomous",
                capabilities=[], tenant_id=None, workspace_id=None,
                configuration={}, enabled=True),
        ])
        db.commit()
    return SimpleNamespace(engine=engine, SessionLocal=Session)


def _wait(
    world,
    *,
    actor_id="member-1",
    agent_id="a1",
    workspace_id="ws1",
    tenant_id="t1",
    status="approved",
    feedback=ANSWER,
    job_status="waiting",
    execution_status="waiting",
    action_type="agent_information_request",
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
    snapshot = {
        "job_id": job_id,
        "execution_id": execution_id,
        "run_id": execution_id,
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "user_id": actor_id,
        "correlation_id": correlation_id,
        "channel": f"user:{actor_id}",
        "question": "What title?",
        "subject": subject,
    }
    params = {
        "question": "What title?",
        "subject": subject,
        "correlation_id": correlation_id,
        "channel": f"user:{actor_id}",
    }
    with world.SessionLocal() as db:
        db.add(AgentJob(
            id=job_id, tenant_id=tenant_id, agent_id=agent_id,
            status=job_status, result_summary=json.dumps(payload)))
        db.add(AgentExecution(
            id=execution_id, agent_id=agent_id, workspace_id=workspace_id,
            tenant_id=tenant_id, status=execution_status,
            metadata_json={}))
        db.add(HITLAction(
            id=action_id, workspace_id=workspace_id, tenant_id=tenant_id,
            agent_id=agent_id, user_id=actor_id,
            action_type=action_type, platform="internal", params=params,
            reason="What title?", status=status,
            user_feedback=feedback,
            context_snapshot=snapshot))
        db.commit()
    return SimpleNamespace(
        job_id=job_id, execution_id=execution_id, action_id=action_id,
        correlation_id=correlation_id, actor_id=actor_id,
        workspace_id=workspace_id)


def _install_dispatch_double(monkeypatch, calls):
    """Double only the descendant dispatch boundary, never authority."""
    from api import agent_routes

    async def sentinel(agent_id, params, execution_context=None):
        calls.append({
            "agent_id": agent_id,
            "params": dict(params or {}),
            "context": dict(execution_context or {}),
        })
        return {"status": "success", "output": "descendant work completed"}

    async def no_broadcast(*args, **kwargs):
        return None

    monkeypatch.setattr(agent_routes, "execute_agent_task", sentinel)
    monkeypatch.setattr(agent_routes, "_broadcast_agent_outcome", no_broadcast)


def _recover(monkeypatch, calls):
    """Run the production startup helper with the real resume consumer."""
    _install_dispatch_double(monkeypatch, calls)
    from core.information_wait import recover_accepted_information_waits

    return asyncio.run(recover_accepted_information_waits())


def _resume_direct(world, target, monkeypatch, calls, *, reviewer_id=None):
    """Exercise the shared normal-answer resume consumer directly."""
    _install_dispatch_double(monkeypatch, calls)
    from api import agent_routes

    return asyncio.run(agent_routes.resume_information_wait_action(
        target.action_id,
        approved=True,
        answer=ANSWER,
        reviewer_id=reviewer_id,
        bind=world.engine,
    ))


def _set_user(world, user_id, **values):
    with world.SessionLocal() as db:
        user = db.get(User, user_id)
        for key, value in values.items():
            setattr(user, key, value)
        db.commit()


def _durable_state(world, target):
    with world.SessionLocal() as db:
        job = db.get(AgentJob, target.job_id)
        execution = db.get(AgentExecution, target.execution_id)
        action = db.get(HITLAction, target.action_id)
        return {
            "job_status": job.status,
            "job_payload": json.loads(job.result_summary or "{}"),
            "execution_status": execution.status,
            "action_status": action.status,
        }


def _assert_refused_without_dispatch(world, target, result, calls, reason):
    assert calls == [], (
        "wrong authority must dispatch zero descendant model/tool work")
    assert result["resumed"] == 0, result
    assert result["details"], result
    detail = result["details"][0]
    assert detail["status"] == "refused", detail
    assert detail["reason"] == reason, detail
    state = _durable_state(world, target)
    assert state["job_status"] == "waiting", state
    assert state["execution_status"] == "waiting", state
    assert state["action_status"] == "approved", state


def test_actor_moved_to_another_workspace_does_not_resume(
        world, monkeypatch):
    target = _wait(world)
    _set_user(world, target.actor_id, workspace_id="ws2")
    calls = []

    result = _recover(monkeypatch, calls)

    _assert_refused_without_dispatch(
        world, target, result, calls, "actor_workspace_mismatch")


def test_actor_demoted_out_of_agent_run_permission_does_not_resume(
        world, monkeypatch):
    target = _wait(world)
    _set_user(world, target.actor_id, role="viewer")
    calls = []

    result = _recover(monkeypatch, calls)

    _assert_refused_without_dispatch(
        world, target, result, calls, "actor_permission_revoked")


def test_actor_moved_to_another_tenant_does_not_resume(world, monkeypatch):
    target = _wait(world)
    _set_user(world, target.actor_id, tenant_id="t2")
    calls = []

    result = _recover(monkeypatch, calls)

    _assert_refused_without_dispatch(
        world, target, result, calls, "actor_tenant_mismatch")


def test_deactivated_actor_does_not_resume(world, monkeypatch):
    target = _wait(world)
    _set_user(world, target.actor_id, is_active=False, status="suspended")
    calls = []

    result = _recover(monkeypatch, calls)

    _assert_refused_without_dispatch(
        world, target, result, calls, "actor_unavailable")


def test_unchanged_scoped_authority_still_resumes(world, monkeypatch):
    target = _wait(world)
    calls = []

    result = _recover(monkeypatch, calls)

    assert result["resumed"] == 1, result
    assert len(calls) == 1, calls
    assert calls[0]["agent_id"] == "a1"
    assert calls[0]["context"]["workspace_id"] == "ws1"
    assert calls[0]["context"]["actor_id"] == target.actor_id
    state = _durable_state(world, target)
    assert state["job_status"] == "success", state
    assert state["execution_status"] == "waiting", state


def test_tenant_absence_remains_compatible_with_a_matching_workspace(
        world, monkeypatch):
    """A missing tenant is legacy/personal scope, not a moved workspace."""
    target = _wait(world)
    _set_user(world, target.actor_id, tenant_id=None)
    calls = []

    result = _recover(monkeypatch, calls)

    assert result["resumed"] == 1, result
    assert len(calls) == 1, calls
    assert calls[0]["context"]["workspace_id"] == "ws1"
    assert _durable_state(world, target)["job_status"] == "success"


def test_personal_null_bootstrap_still_resumes_its_default_workspace(
        world, monkeypatch):
    target = _wait(
        world, actor_id="personal-admin", agent_id="personal-agent",
        workspace_id="default", tenant_id=None)
    calls = []

    result = _recover(monkeypatch, calls)

    assert result["resumed"] == 1, result
    assert len(calls) == 1, calls
    assert calls[0]["context"]["workspace_id"] == "default"
    assert calls[0]["context"]["actor_id"] == "personal-admin"
    assert _durable_state(world, target)["job_status"] == "success"


def _assert_direct_refused(world, target, result, calls, reason):
    assert calls == [], (
        "the normal answer path must not dispatch under wrong authority")
    assert result["resumed"] is False, result
    assert result["status"] == "refused", result
    assert result["reason"] == reason, result
    state = _durable_state(world, target)
    assert state["job_status"] == "waiting", state
    assert state["execution_status"] == "waiting", state
    assert state["action_status"] == "approved", state


def test_normal_answer_path_refuses_moved_actor_before_dispatch(
        world, monkeypatch):
    target = _wait(world)
    _set_user(world, target.actor_id, workspace_id="ws2")
    calls = []

    result = _resume_direct(world, target, monkeypatch, calls)

    _assert_direct_refused(
        world, target, result, calls, "actor_workspace_mismatch")


def test_admin_answerer_cannot_replace_the_moved_admitted_actor(
        world, monkeypatch):
    """An admin answering is not authority for the original actor's run."""
    target = _wait(world)
    _set_user(world, target.actor_id, workspace_id="ws2")
    calls = []

    result = _resume_direct(
        world, target, monkeypatch, calls, reviewer_id="admin-1")

    _assert_direct_refused(
        world, target, result, calls, "actor_workspace_mismatch")


def test_move_committed_after_precheck_still_loses_the_claim(
        world, monkeypatch):
    """Force the real check-then-claim window the claim CAS must close.

    The pre-claim authority read returns the still-valid actor, then the
    User row moves before the conditional job claim executes. A read-only
    guard would resume here; the authority predicate bound into the same
    claim UPDATE must refuse.
    """
    target = _wait(world)
    import core.information_wait as information_wait

    real_current_actor_authority = information_wait.current_actor_authority
    moved = {"done": False}

    def move_after_precheck(session, **kwargs):
        actor, reason = real_current_actor_authority(session, **kwargs)
        if not moved["done"]:
            user = session.get(User, target.actor_id)
            user.workspace_id = "ws2"
            session.commit()
            moved["done"] = True
        return actor, reason

    monkeypatch.setattr(
        information_wait, "current_actor_authority", move_after_precheck)
    calls = []

    result = _resume_direct(world, target, monkeypatch, calls)

    assert moved["done"] is True
    _assert_direct_refused(
        world, target, result, calls, "actor_workspace_mismatch")


@pytest.mark.parametrize("moved", [False, True])
def test_real_generic_registered_effect_respects_current_actor_workspace(
        real_env, monkeypatch, moved):
    """Permanent twin of the supplied production probe.

    Real public admission, real GenericAgent loop, real registered
    ``tasks.create`` and the default oracle against scratch board rows. The
    moved twin must produce zero BoardTask rows and must not mark the job
    success; the unchanged twin still completes the registered effect.
    """
    from core.models_board import BoardTask
    from core.react_models import InformationWaitRequest, ReActStep, ToolCall
    from tests.test_agent_generic_information_wait import (
        _install_model,
        _run,
        _seed_board,
    )

    board, column = _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need title",
            information_wait=InformationWaitRequest(
                question="Which title?", missing_fact="title",
                subject="closing task"))

    def resumed(task_input, history, context):
        return ReActStep(
            thought="Create accepted task",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board,
                    "column_id": column,
                    "title": context["information_answer"],
                    "status": "backlog",
                }))

    def finished(task_input, history, context):
        return ReActStep(thought="Verified task", final_answer="Created")

    calls = _install_model(monkeypatch, [first, resumed, finished])
    response = _run(
        real_env,
        operation_id=f"authority-real-{moved}",
        parameters={"sync": True, "task_input": "Create the closing task"},
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    with real_env.SessionLocal() as db:
        action = db.get(HITLAction, data["wait_receipt"]["hitl_action_id"])
        action.status = "approved"
        action.user_feedback = "Scoped recovery task"
        if moved:
            db.add(Workspace(
                id="ws-reassigned", name="Reassigned", tenant_id="t1"))
            db.flush()
            db.get(User, "member-1").workspace_id = "ws-reassigned"
        db.commit()

    import core.database as database

    monkeypatch.setattr(database, "SessionLocal", real_env.SessionLocal)
    monkeypatch.setattr(database, "engine", real_env.engine)
    from core.information_wait import recover_accepted_information_waits

    result = asyncio.run(recover_accepted_information_waits())
    with real_env.SessionLocal() as db:
        created = db.query(BoardTask).filter(
            BoardTask.title == "Scoped recovery task").count()
        status = db.get(AgentJob, data["job_id"]).status
        action_status = db.get(
            HITLAction, data["wait_receipt"]["hitl_action_id"]).status

    if moved:
        assert len(calls) == 1, calls
        assert created == 0, created
        assert status != "success", status
        assert result["resumed"] == 0, result
        assert action_status == "approved", action_status
    else:
        assert created == 1, created
        assert status == "success", status
        assert result["resumed"] == 1, result
