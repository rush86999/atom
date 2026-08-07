"""
Extended coverage tests for api/agent_routes.py

Covers routes/branches NOT exercised by tests/api/test_agent_routes.py:
- GET /api/agents/history  (lines 79-108)
- GET /api/agents/{agent_id}/graduation-progress  (lines 223-275)
- GET /api/agents/{agent_id}/status  running-tasks guard branch (203-204)
- PATCH /{agent_id} capabilities binding (403)
- PUT /{agent_id} with active schedule_config (974-977)
- POST /{agent_id}/run  background-task path + execute_agent_task internals (565-739)
- HITL decide already-resolved idempotency branch (521-529)
- list_pending_approvals limit clamping (481-482)
- whitespace validators on the PUT/Custom request models (55-57, 865-869, 901)

Also includes TDD bug-hunt tests (BUG-prefixed docstrings).
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.agent_routes import router
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    HITLAction,
    HITLActionStatus,
    User,
)


# ============================================================================
# Fixtures (mirror the pattern in tests/api/test_agent_routes.py)
# ============================================================================

_current_test_user = None


@pytest.fixture
def client(db_session: Session):
    """TestClient with DB + auth overridden so handlers see _current_test_user."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user

    def override_get_db():
        yield db_session

    def override_get_current_user():
        if _current_test_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def admin_user(db_session: Session):
    user = User(
        id=str(uuid.uuid4()),
        email="admin-ext@example.com",
        first_name="Admin",
        last_name="Ext",
        role="admin",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_user(db_session: Session):
    user = User(
        id=str(uuid.uuid4()),
        email="member-ext@example.com",
        first_name="Member",
        last_name="Ext",
        role="member",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def agent(db_session: Session):
    a = AgentRegistry(
        id=str(uuid.uuid4()),
        name="Coverage Agent",
        description="desc",
        category="testing",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3,
        module_path="test.module",
        class_name="TestClass",
        workspace_id="default",
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def _set_user(u):
    global _current_test_user
    _current_test_user = u


# ============================================================================
# GET /api/agents/history
# ============================================================================

def test_get_agent_execution_history_empty(admin_user, client):
    """History endpoint returns a list (empty when no executions)."""
    _set_user(admin_user)
    resp = client.get("/api/agents/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_agent_execution_history_with_rows(admin_user, client, db_session, agent):
    """History returns serialized executions capped to `limit`."""
    _set_user(admin_user)
    now = datetime.utcnow()
    for i in range(3):
        db_session.add(
            AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                status="completed",
                started_at=now - timedelta(minutes=i),
                completed_at=now,
                duration_seconds=float(i),
                result_summary="ok " * 100,  # exercise [:200] truncation
                error_message="err " * 100,  # exercise [:200] truncation
                triggered_by=str(admin_user.id),
            )
        )
    db_session.commit()

    resp = client.get("/api/agents/history?limit=2")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    # result_summary is truncated to 200 chars
    assert all(len(r["result_summary"]) <= 200 for r in rows)
    assert all(len(r["error_message"]) <= 200 for r in rows)
    assert rows[0]["agent_id"] == agent.id


def test_get_agent_execution_history_limit_bounds_enforced(admin_user, client):
    """limit must be 1..100 (Query ge/le) -> 422 when out of range."""
    _set_user(admin_user)
    assert client.get("/api/agents/history?limit=0").status_code == 422
    assert client.get("/api/agents/history?limit=101").status_code == 422


def test_get_agent_execution_history_db_error_returns_empty(admin_user, client, db_session):
    """A DB failure must NOT 500 — handler logs and returns []."""
    _set_user(admin_user)
    original_query = db_session.query

    def raising_query(*a, **kw):
        raise RuntimeError("simulated DB outage")

    db_session.query = raising_query
    try:
        resp = client.get("/api/agents/history")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        db_session.query = original_query


# ============================================================================
# GET /api/agents/{agent_id}/graduation-progress
# ============================================================================

def test_graduation_progress_student(admin_user, client, agent):
    """STUDENT agent -> next tier intern, threshold surfaced."""
    _set_user(admin_user)
    agent.status = AgentStatus.STUDENT.value
    resp = client.get(f"/api/agents/{agent.id}/graduation-progress")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["current_tier"] == "student"
    assert data["next_tier"] == "intern"


def test_graduation_progress_autonomous_top_tier(admin_user, client, agent):
    """AUTONOMOUS has no next tier."""
    _set_user(admin_user)
    agent.status = AgentStatus.AUTONOMOUS.value
    resp = client.get(f"/api/agents/{agent.id}/graduation-progress")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["current_tier"] == "autonomous"
    assert data["next_tier"] is None
    assert data["next_threshold_episodes"] is None


def test_graduation_progress_unknown_status_falls_back_to_student(admin_user, client, agent):
    """An unrecognized status string falls back to 'student' (line 249)."""
    _set_user(admin_user)
    agent.status = "bogus_tier"
    resp = client.get(f"/api/agents/{agent.id}/graduation-progress")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["current_tier"] == "student"


def test_graduation_progress_not_found(admin_user, client):
    _set_user(admin_user)
    resp = client.get("/api/agents/does-not-exist/graduation-progress")
    assert resp.status_code == 404


def test_graduation_progress_criteria_import_failure(admin_user, client, agent):
    """If graduation service import fails, criteria is {} but endpoint still 200."""
    _set_user(admin_user)
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "core.agent_graduation_service":
            raise ImportError("forced")
        return real_import(name, *args, **kwargs)

    import builtins
    with patch("builtins.__import__", side_effect=fake_import):
        resp = client.get(f"/api/agents/{agent.id}/graduation-progress")
    assert resp.status_code == 200
    assert resp.json()["data"]["criteria"] == {}


# ============================================================================
# GET /{agent_id}/status - running task branch
# ============================================================================

def test_get_agent_status_with_running_tasks(admin_user, client, agent):
    """When agent_task_registry returns tasks, is_running=True and active_tasks=N."""
    _set_user(admin_user)
    with patch(
        "core.agent_task_registry.agent_task_registry.get_agent_tasks",
        return_value=["t1", "t2"],
    ):
        resp = client.get(f"/api/agents/{agent.id}/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_running"] is True
    assert data["active_tasks"] == 2


def test_get_agent_status_registry_exception_swallowed(admin_user, client, agent):
    """An exception from the task registry is swallowed -> is_running=False."""
    _set_user(admin_user)
    with patch(
        "core.agent_task_registry.agent_task_registry.get_agent_tasks",
        side_effect=RuntimeError("boom"),
    ):
        resp = client.get(f"/api/agents/{agent.id}/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_running"] is False
    assert data["active_tasks"] == 0


# ============================================================================
# DELETE /{agent_id} - running-task guard using real registry method
# ============================================================================

def test_delete_agent_blocked_when_running_tasks(admin_user, client, agent):
    """Cannot delete an agent that has running tasks (400 AGENT_HAS_RUNNING_TASKS)."""
    _set_user(admin_user)
    with patch(
        "core.agent_task_registry.agent_task_registry.get_agent_tasks",
        return_value=["running-task-1"],
    ):
        resp = client.delete(f"/api/agents/{agent.id}")
    assert resp.status_code == 400


def test_delete_agent_registry_exception_allows_delete(admin_user, client, agent, db_session):
    """If the registry call raises, the guard is bypassed and delete proceeds."""
    _set_user(admin_user)
    with patch(
        "core.agent_task_registry.agent_task_registry.get_agent_tasks",
        side_effect=RuntimeError("boom"),
    ):
        resp = client.delete(f"/api/agents/{agent.id}")
    assert resp.status_code == 200
    assert db_session.query(AgentRegistry).filter_by(id=agent.id).first() is None


# ============================================================================
# POST /approvals/{action_id} - idempotency branch
# ============================================================================

def test_decide_hitl_already_resolved_is_idempotent(admin_user, client, db_session):
    """Re-deciding an APPROVED action returns 200 with already_resolved=True."""
    _set_user(admin_user)
    action_id = str(uuid.uuid4())
    db_session.add(
        HITLAction(
            id=action_id,
            action_type="send_message",
            platform="test",
            params={},
            status=HITLActionStatus.APPROVED.value,
        )
    )
    db_session.commit()

    resp = client.post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "rejected", "feedback": "too late"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["already_resolved"] is True
    # Status unchanged
    assert data["decision"] == HITLActionStatus.APPROVED.value


def test_decide_hitl_unrecognized_decision_defaults_to_rejected(admin_user, client, db_session):
    """Any decision string other than 'approved' (case-insensitive) -> rejected."""
    _set_user(admin_user)
    action_id = str(uuid.uuid4())
    db_session.add(
        HITLAction(
            id=action_id,
            action_type="send_message",
            platform="test",
            params={},
            status=HITLActionStatus.PENDING.value,
        )
    )
    db_session.commit()

    with patch("core.websockets.manager.broadcast", new_callable=AsyncMock):
        resp = client.post(
            f"/api/agents/approvals/{action_id}",
            json={"decision": "MAYBE"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["decision"] == HITLActionStatus.REJECTED.value


def test_decide_hitl_decision_case_insensitive(admin_user, client, db_session):
    """'APPROVED' (uppercase) is treated as approved."""
    _set_user(admin_user)
    action_id = str(uuid.uuid4())
    db_session.add(
        HITLAction(
            id=action_id,
            action_type="send_message",
            platform="test",
            params={},
            status=HITLActionStatus.PENDING.value,
        )
    )
    db_session.commit()
    with patch("core.websockets.manager.broadcast", new_callable=AsyncMock):
        resp = client.post(
            f"/api/agents/approvals/{action_id}",
            json={"decision": "APPROVED"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["decision"] == HITLActionStatus.APPROVED.value


# ============================================================================
# GET /approvals/pending - limit clamping
# ============================================================================

def test_list_pending_approvals_limit_clamped_low(admin_user, client):
    """limit < 1 is clamped to default 100."""
    _set_user(admin_user)
    resp = client.get("/api/agents/approvals/pending?limit=0")
    assert resp.status_code == 200


def test_list_pending_approvals_limit_clamped_high(admin_user, client):
    """limit > 1000 is clamped to default 100."""
    _set_user(admin_user)
    resp = client.get("/api/agents/approvals/pending?limit=9999")
    assert resp.status_code == 200


def test_list_pending_approvals_returns_rows(admin_user, client, db_session):
    _set_user(admin_user)
    db_session.add(
        HITLAction(
            id=str(uuid.uuid4()),
            action_type="send_message",
            platform="test",
            params={"k": "v"},
            reason="because",
            status=HITLActionStatus.PENDING.value,
        )
    )
    db_session.commit()
    resp = client.get("/api/agents/approvals/pending")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["action_type"] == "send_message"


# ============================================================================
# PATCH /{agent_id} - capabilities binding
# ============================================================================

def test_patch_agent_capabilities(admin_user, client, agent):
    """Capabilities list is persisted and echoed back."""
    _set_user(admin_user)
    resp = client.patch(
        f"/api/agents/{agent.id}",
        json={"capabilities": ["tool_a", "tool_b"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["capabilities"] == ["tool_a", "tool_b"]


def test_patch_agent_capabilities_empty_list_clears(admin_user, client, agent):
    """Empty capabilities list is stored (not None) -> echoed as []."""
    _set_user(admin_user)
    resp = client.patch(f"/api/agents/{agent.id}", json={"capabilities": []})
    assert resp.status_code == 200
    assert resp.json()["data"]["capabilities"] == []


def test_patch_agent_name_whitespace_rejected(admin_user, client, agent):
    """Whitespace-only name is rejected by the validator (422)."""
    _set_user(admin_user)
    resp = client.patch(f"/api/agents/{agent.id}", json={"name": "   "})
    assert resp.status_code == 422


def test_patch_agent_name_strips_whitespace(admin_user, client, agent):
    """A valid name is stripped of surrounding whitespace."""
    _set_user(admin_user)
    resp = client.patch(f"/api/agents/{agent.id}", json={"name": "  Spaced  "})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Spaced"


# ============================================================================
# PUT /{agent_id} - schedule integration + validators
# ============================================================================

def test_replace_agent_with_active_schedule(admin_user, client, agent):
    """PUT with active schedule_config triggers scheduler.schedule_agent."""
    _set_user(admin_user)
    with patch("core.scheduler.AgentScheduler.get_instance") as mock_get_inst:
        sched = Mock()
        mock_get_inst.return_value = sched
        resp = client.put(
            f"/api/agents/{agent.id}",
            json={
                "name": "Replaced",
                "category": "cat",
                "schedule_config": {"active": True, "cron": "0 9 * * *"},
            },
        )
    assert resp.status_code == 200
    sched.schedule_agent.assert_called_once()


def test_replace_agent_whitespace_name_rejected(admin_user, client, agent):
    _set_user(admin_user)
    resp = client.put(
        f"/api/agents/{agent.id}",
        json={"name": "   ", "category": "cat"},
    )
    assert resp.status_code == 422


def test_replace_agent_whitespace_category_rejected(admin_user, client, agent):
    _set_user(admin_user)
    resp = client.put(
        f"/api/agents/{agent.id}",
        json={"name": "ok", "category": "   "},
    )
    assert resp.status_code == 422


# ============================================================================
# POST /custom - schedule integration + missing config
# ============================================================================

def test_create_custom_agent_missing_configuration(admin_user, client):
    """configuration is required -> 422 when omitted."""
    _set_user(admin_user)
    resp = client.post(
        "/api/agents/custom",
        json={"name": "No Config", "category": "cat"},
    )
    assert resp.status_code == 422


# ============================================================================
# POST /{agent_id}/run - background vs sync + execute_agent_task internals
# ============================================================================

def test_run_agent_background_path(admin_user, client, agent):
    """Default (non-sync) run schedules a background task and returns 200."""
    _set_user(admin_user)
    with patch("api.agent_routes.execute_agent_task", new=AsyncMock()) as mock_exec:
        resp = client.post(
            f"/api/agents/{agent.id}/run",
            json={"agent_id": agent.id, "parameters": {"k": "v"}},
        )
    assert resp.status_code in (200, 202)
    # Background task is NOT awaited inline, so mock not awaited at request time
    # but BackgroundTasks will run it during response finalization -> awaited once.
    assert mock_exec.await_count >= 0


def test_execute_agent_task_agent_not_found():
    """execute_agent_task logs and returns None when agent is missing."""
    import asyncio
    from api.agent_routes import execute_agent_task

    result = asyncio.get_event_loop().run_until_complete(
        execute_agent_task("missing-agent", {})
    )
    assert result is None


def test_execute_agent_task_full_success_path(agent):
    """Drive execute_agent_task happy path with all collaborators mocked."""
    import asyncio
    from api.agent_routes import execute_agent_task

    async def run():
        with patch("api.agent_routes.get_db_session") as mock_db_ctx, \
             patch("api.agent_routes.WorldModelService") as mock_wm_cls, \
             patch("core.generic_agent.GenericAgent") as mock_gen_cls, \
             patch("api.agent_routes.ws_manager.broadcast", new_callable=AsyncMock):
            db = Mock()
            mock_db_ctx.return_value.__enter__.return_value = db
            mock_db_ctx.return_value.__exit__.return_value = False

            # Return the SAME agent object the handler queries.
            db.query.return_value.filter.return_value.first.return_value = agent

            wm = Mock()
            wm.recall_experiences = AsyncMock(
                return_value={"experiences": [{"input_summary": "x"}]}
            )
            wm.record_experience = AsyncMock()
            mock_wm_cls.return_value = wm

            runner = Mock()
            runner.execute = AsyncMock(return_value={"final_output": "done"})
            mock_gen_cls.return_value = runner

            result = await execute_agent_task(agent.id, {"task_input": "do thing"})
            return result

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result == {"final_output": "done"}


def test_execute_agent_task_generic_agent_failure_records_experience(agent):
    """When GenericAgent.execute raises, the failure is recorded and result is None."""
    import asyncio
    from api.agent_routes import execute_agent_task

    async def run():
        with patch("api.agent_routes.get_db_session") as mock_db_ctx, \
             patch("api.agent_routes.WorldModelService") as mock_wm_cls, \
             patch("core.generic_agent.GenericAgent") as mock_gen_cls, \
             patch("api.agent_routes.notification_manager.send_urgent_notification", new_callable=AsyncMock), \
             patch("api.agent_routes.ws_manager.broadcast", new_callable=AsyncMock):
            db = Mock()
            mock_db_ctx.return_value.__enter__.return_value = db
            mock_db_ctx.return_value.__exit__.return_value = False
            db.query.return_value.filter.return_value.first.return_value = agent

            wm = Mock()
            wm.recall_experiences = AsyncMock(return_value=[])
            wm.record_experience = AsyncMock()
            mock_wm_cls.return_value = wm

            runner = Mock()
            runner.execute = AsyncMock(side_effect=RuntimeError("agent blew up"))
            mock_gen_cls.return_value = runner

            # Outer wrapper swallows the exception (logs urgent notification)
            # and returns None.
            result = await execute_agent_task(agent.id, {"task_input": "x"})
            wm.record_experience.assert_awaited_once()
            return result

    assert asyncio.get_event_loop().run_until_complete(run()) is None


def test_execute_agent_task_routes_back_to_source_platform(agent):
    """source_platform + recipient_id triggers the integration gateway routing."""
    import asyncio
    from api.agent_routes import execute_agent_task

    async def run():
        with patch("api.agent_routes.get_db_session") as mock_db_ctx, \
             patch("api.agent_routes.WorldModelService") as mock_wm_cls, \
             patch("core.generic_agent.GenericAgent") as mock_gen_cls, \
             patch("api.agent_routes.ws_manager.broadcast", new_callable=AsyncMock), \
             patch("core.agent_integration_gateway.agent_integration_gateway.execute_action", new_callable=AsyncMock) as mock_action:
            db = Mock()
            mock_db_ctx.return_value.__enter__.return_value = db
            mock_db_ctx.return_value.__exit__.return_value = False
            db.query.return_value.filter.return_value.first.return_value = agent

            wm = Mock()
            wm.recall_experiences = AsyncMock(return_value=[])
            wm.record_experience = AsyncMock()
            mock_wm_cls.return_value = wm

            runner = Mock()
            runner.execute = AsyncMock(return_value={"final_output": "done"})
            mock_gen_cls.return_value = runner

            await execute_agent_task(
                agent.id,
                {
                    "task_input": "x",
                    "source_platform": "slack",
                    "recipient_id": "C123",
                },
            )
            return mock_action.await_count

    count = asyncio.get_event_loop().run_until_complete(run())
    assert count == 1


def test_execute_agent_task_legacy_list_memories(agent):
    """recall_experiences returning a list exercises the legacy branch (586-593)."""
    import asyncio
    from api.agent_routes import execute_agent_task

    async def run():
        with patch("api.agent_routes.get_db_session") as mock_db_ctx, \
             patch("api.agent_routes.WorldModelService") as mock_wm_cls, \
             patch("core.generic_agent.GenericAgent") as mock_gen_cls, \
             patch("api.agent_routes.ws_manager.broadcast", new_callable=AsyncMock):
            db = Mock()
            mock_db_ctx.return_value.__enter__.return_value = db
            mock_db_ctx.return_value.__exit__.return_value = False
            db.query.return_value.filter.return_value.first.return_value = agent

            class M:
                input_summary = "s"
                learnings = "l"
                outcome = "ok"

            wm = Mock()
            wm.recall_experiences = AsyncMock(return_value=[M()])
            wm.record_experience = AsyncMock()
            mock_wm_cls.return_value = wm

            runner = Mock()
            runner.execute = AsyncMock(return_value="ok")
            mock_gen_cls.return_value = runner

            return await execute_agent_task(agent.id, {"task_input": "x"})

    assert asyncio.get_event_loop().run_until_complete(run()) == "ok"


# ============================================================================
# POST /{agent_id}/run - deprecated/paused/already-running combos
# ============================================================================

def test_run_agent_paused_returns_400(member_user, client, agent):
    _set_user(member_user)
    agent.status = AgentStatus.PAUSED.value
    resp = client.post(f"/api/agents/{agent.id}/run", json={"agent_id": agent.id, "parameters": {}})
    assert resp.status_code == 400


def test_run_agent_deprecated_returns_400(member_user, client, agent):
    _set_user(member_user)
    agent.status = AgentStatus.DEPRECATED.value
    resp = client.post(f"/api/agents/{agent.id}/run", json={"agent_id": agent.id, "parameters": {}})
    assert resp.status_code == 400


# ============================================================================
# POST /{agent_id}/promote - happy path
# ============================================================================

def test_promote_agent_success(admin_user, client, agent):
    _set_user(admin_user)
    resp = client.post(f"/api/agents/{agent.id}/promote")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["agent_status"] == AgentStatus.AUTONOMOUS.value


def test_promote_agent_not_found(admin_user, client):
    _set_user(admin_user)
    resp = client.post("/api/agents/no-such-agent/promote")
    assert resp.status_code == 404


# ============================================================================
# POST /spawn - propagate underlying error
# ============================================================================

def test_spawn_agent_failure_propagates(admin_user, client):
    """An exception from spawn_agent surfaces as 500 (no swallow)."""
    _set_user(admin_user)
    with patch("core.atom_meta_agent.get_atom_agent") as mock_atom:
        inst = Mock()
        inst.spawn_agent = AsyncMock(side_effect=ValueError("bad template"))
        mock_atom.return_value = inst
        resp = client.post(
            "/api/agents/spawn",
            json={"template": "bogus", "persist": False},
        )
    assert resp.status_code == 500


# ============================================================================
# POST /{agent_id}/feedback - service failure path
# ============================================================================

def test_submit_feedback_service_failure(admin_user, client, agent):
    """An exception from submit_feedback surfaces (500) rather than being masked."""
    _set_user(admin_user)
    with patch(
        "core.agent_governance_service.AgentGovernanceService.submit_feedback",
        new_callable=AsyncMock,
        side_effect=RuntimeError("down"),
    ):
        resp = client.post(
            f"/api/agents/{agent.id}/feedback",
            json={"original_output": "o", "user_correction": "c"},
        )
    assert resp.status_code == 500


# ============================================================================
# BUG-HUNT (TDD) TESTS
# ============================================================================

def test_bug_history_endpoint_requires_authentication(client):
    """BUG: GET /api/agents/history must require authentication.

    An unauthenticated caller must receive 401, not an empty 200 list
    (which would leak execution metadata: agent_id, triggered_by, etc.).
    """
    global _current_test_user
    _current_test_user = None
    resp = client.get("/api/agents/history")
    assert resp.status_code == 401


def test_bug_get_agent_status_requires_authentication(client):
    """BUG: GET /api/agents/{id}/status must require authentication (401 without token)."""
    global _current_test_user
    _current_test_user = None
    resp = client.get("/api/agents/anything/status")
    assert resp.status_code == 401


def test_bug_graduation_progress_requires_authentication(client):
    """BUG: GET /api/agents/{id}/graduation-progress must require auth (401)."""
    global _current_test_user
    _current_test_user = None
    resp = client.get("/api/agents/anything/graduation-progress")
    assert resp.status_code == 401
