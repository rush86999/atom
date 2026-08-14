# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/unified_task_endpoints.py.

TestClient-based coverage of the /api/v1/tasks + /api/v1/projects surface:
- auth: POST/PUT/DELETE tasks are user-gated (anonymous -> 401); GET
  tasks + all project endpoints are intentionally unauthenticated.
- GET tasks: mock fallback, Asana fetch (dates parsed, bad dates tolerated,
  combine on "all"), Asana error -> mock fallback.
- POST tasks: local create + project count bump + behavior-analyzer hook,
  Asana success/not-ok/exception paths (falling back to local).
- PUT/DELETE tasks: 404s, updates, analytics tracking for automated
  (workflow_id) tasks, project-count decrement floor.
- Projects: dynamic progress/task_count recalculation, create, update, 404.

REAL BUG (TDD RED -> GREEN):
  W104-7: a REAL Asana personal-access token was hardcoded at module level
  (CWE-798) and used for every Asana call. Now read from the
  ASANA_ACCESS_TOKEN env var (the convention used everywhere else in the
  repo: workflow_engine.py, asana_routes.py, asana_real_service.py);
  Asana calls without the env var fail over to the local mock store.
  NOTE: the leaked token must be ROTATED (it has shipped in git history).

No LLM spend, no network.
"""
import importlib
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.unified_task_endpoints as m
from core.auth import get_current_user
from core.unified_task_endpoints import (
    MOCK_PROJECTS,
    MOCK_TASKS,
    project_router,
    router,
)


@pytest.fixture()
def user():
    u = MagicMock()
    u.id = "user-1"
    return u


@pytest.fixture()
def app(user):
    app = FastAPI()
    app.include_router(router)
    app.include_router(project_router)
    app.dependency_overrides[get_current_user] = lambda: user
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def anon_app():
    app = FastAPI()
    app.include_router(router)
    app.include_router(project_router)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(anon_app):
    return TestClient(anon_app)


@pytest.fixture(autouse=True)
def _restore_state():
    """Snapshot/restore the mutable module-level stores per test.

    deepcopy because delete_task REBINDS m.MOCK_TASKS (global) and project
    objects are mutated in place (task_count/status/progress).
    """
    import copy

    tasks = copy.deepcopy(m.MOCK_TASKS)
    projects = copy.deepcopy(m.MOCK_PROJECTS)
    yield
    m.MOCK_TASKS = tasks
    m.MOCK_PROJECTS = projects


def _asana_patch(monkeypatch, service=None):
    service = service or MagicMock()
    monkeypatch.setattr(m, "ASANA_AVAILABLE", True)
    monkeypatch.setattr(m, "asana_service", service)
    monkeypatch.setattr(m, "ASANA_ACCESS_TOKEN", "env-token")
    return service


def _task(**kw):
    base = dict(
        id="t-x",
        title="t",
        dueDate=datetime(2026, 8, 1),
        priority="medium",
        status="todo",
        createdAt=datetime(2026, 8, 1),
        updatedAt=datetime(2026, 8, 1),
    )
    base.update(kw)
    return m.Task(**base)


def _asana_task(**kw):
    base = {
        "gid": "a1",
        "name": "Asana task",
        "notes": "notes",
        "completed": False,
        "due_on": "2026-08-01",
        "created_at": "2026-07-01T10:00:00Z",
        "tags": [{"name": "dev"}],
        "assignee": {"name": "Rishi"},
    }
    base.update(kw)
    return base


class TestAuth:
    def test_create_task_anonymous_401(self, anon_client):
        resp = anon_client.post("/api/v1/tasks/", json={"title": "t", "dueDate": "2026-08-01T00:00:00"})
        assert resp.status_code == 401

    def test_update_task_anonymous_401(self, anon_client):
        resp = anon_client.put("/api/v1/tasks/1", json={"title": "x"})
        assert resp.status_code == 401

    def test_delete_task_anonymous_401(self, anon_client):
        resp = anon_client.delete("/api/v1/tasks/1")
        assert resp.status_code == 401


class TestGetTasks:
    def test_asana_unavailable_mock_source(self, client, monkeypatch):
        monkeypatch.setattr(m, "ASANA_AVAILABLE", False)
        resp = client.get("/api/v1/tasks/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["source"] == "mock"
        assert len(body["tasks"]) == len(m.MOCK_TASKS)

    def test_asana_platform(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.return_value = {"data": [_asana_task()]}
        resp = client.get("/api/v1/tasks/?platform=asana")
        body = resp.json()
        assert body["source"] == "asana"
        (task,) = body["tasks"]
        assert task["platform"] == "asana"
        assert task["id"] == "a1"
        assert task["title"] == "Asana task"
        assert task["status"] == "in-progress"
        assert task["tags"] == ["dev"]
        assert task["assignee"] == "Rishi"

    def test_all_combines_with_mock(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.return_value = {"data": [_asana_task()]}
        resp = client.get("/api/v1/tasks/")
        body = resp.json()
        assert body["source"] == "asana"
        assert len(body["tasks"]) == len(m.MOCK_TASKS) + 1

    def test_completed_asana_task(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.return_value = {"data": [_asana_task(completed=True)]}
        resp = client.get("/api/v1/tasks/?platform=asana")
        assert resp.json()["tasks"][0]["status"] == "completed"

    def test_missing_due_on_uses_now(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        task = _asana_task()
        del task["due_on"]
        svc._make_request.return_value = {"data": [task]}
        resp = client.get("/api/v1/tasks/?platform=asana")
        assert resp.status_code == 200

    def test_bad_due_on_uses_now(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.return_value = {"data": [_asana_task(due_on="not-a-date")]}
        resp = client.get("/api/v1/tasks/?platform=asana")
        assert resp.status_code == 200

    def test_bad_created_at_tolerated(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.return_value = {"data": [_asana_task(created_at="garbage")]}
        resp = client.get("/api/v1/tasks/?platform=asana")
        assert resp.status_code == 200

    def test_no_assignee(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        task = _asana_task()
        task["assignee"] = None
        svc._make_request.return_value = {"data": [task]}
        resp = client.get("/api/v1/tasks/?platform=asana")
        assert resp.json()["tasks"][0]["assignee"] is None

    def test_empty_tags(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.return_value = {"data": [_asana_task(tags=[])]}
        resp = client.get("/api/v1/tasks/?platform=asana")
        assert resp.json()["tasks"][0]["tags"] == []

    def test_asana_error_falls_back_to_mock(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.side_effect = RuntimeError("asana down")
        resp = client.get("/api/v1/tasks/")
        body = resp.json()
        assert body["source"] == "mock"
        assert len(body["tasks"]) == len(m.MOCK_TASKS)

    def test_asana_result_without_data_falls_back(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc._make_request.return_value = {}
        resp = client.get("/api/v1/tasks/?platform=asana")
        assert resp.json()["source"] == "mock"


class TestCreateTask:
    def test_local_create(self, client, monkeypatch):
        analyzer = MagicMock()
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: analyzer
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "New task",
                "dueDate": "2026-08-20T00:00:00",
                "priority": "high",
                "project": "project-1",
                "tags": ["frontend"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["platform"] == "local"
        task = body["task"]
        assert task["title"] == "New task"
        assert task["priority"] == "high"
        assert task["tags"] == ["frontend"]
        analyzer.log_user_action.assert_called_once()
        args = analyzer.log_user_action.call_args[1]
        assert args["user_id"] == "user-1"
        assert args["action_type"] == "task_created"
        # project task_count bumped
        proj = next(p for p in m.MOCK_PROJECTS if p.id == "project-1")
        assert proj.task_count == 3

    def test_local_create_no_project_no_count_bump(self, client, monkeypatch):
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": "t", "dueDate": "2026-08-20T00:00:00"},
        )
        assert resp.json()["task"]["platform"] == "local"

    def test_asana_success(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc.create_task = AsyncMock(return_value={
            "ok": True,
            "task": {
                "gid": "a99",
                "name": "A task",
                "notes": "n",
                "created_at": "2026-07-01T10:00:00Z",
                "due_on": "2026-08-05",
            },
        })
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": "A task", "dueDate": "2026-08-05T00:00:00", "platform": "asana"},
        )
        body = resp.json()
        assert body["platform"] == "asana"
        assert body["task"]["id"] == "a99"
        assert body["task"]["status"] == "todo"
        assert svc.create_task.await_args[0][0] == "env-token"

    def test_asana_bad_created_at_tolerated(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc.create_task = AsyncMock(return_value={
            "ok": True,
            "task": {
                "gid": "a99",
                "name": "A",
                "notes": "n",
                "created_at": "junk",
                "due_on": "2026-08-05",
            },
        })
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": "A", "dueDate": "2026-08-05T00:00:00", "platform": "asana"},
        )
        assert resp.status_code == 200

    def test_asana_missing_due_on(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc.create_task = AsyncMock(return_value={
            "ok": True,
            "task": {"gid": "a99", "name": "A", "notes": "n"},
        })
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": "A", "dueDate": "2026-08-05T00:00:00", "platform": "asana"},
        )
        assert resp.status_code == 200

    def test_asana_not_ok_falls_back_to_local(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc.create_task = AsyncMock(return_value={"ok": False})
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": "A", "dueDate": "2026-08-05T00:00:00", "platform": "asana"},
        )
        body = resp.json()
        assert body["platform"] == "local"
        assert body["task"]["title"] == "A"

    def test_asana_exception_falls_back_to_local(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        svc.create_task = AsyncMock(side_effect=RuntimeError("asana exploded"))
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": "A", "dueDate": "2026-08-05T00:00:00", "platform": "asana"},
        )
        assert resp.json()["platform"] == "local"

    def test_asana_unavailable_platform_asana_local_fallback(self, client, monkeypatch):
        monkeypatch.setattr(m, "ASANA_AVAILABLE", False)
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": "A", "dueDate": "2026-08-05T00:00:00", "platform": "asana"},
        )
        assert resp.json()["platform"] == "local"


class TestUpdateTask:
    def test_not_found_404(self, client):
        resp = client.put("/api/v1/tasks/nope", json={"title": "x"})
        assert resp.status_code == 404

    def test_update_success(self, client):
        resp = client.put(
            "/api/v1/tasks/1", json={"title": "Updated", "priority": "low"}
        )
        assert resp.status_code == 200
        task = resp.json()["task"]
        assert task["title"] == "Updated"
        assert task["priority"] == "low"
        # other fields untouched
        assert task["status"] == "in-progress"

    def test_update_tracks_automated_override(self, client, monkeypatch):
        task = _task(
            id="auto-1",
            metadata={"workflow_id": "wf-1", "execution_id": "ex-1"},
        )
        m.MOCK_TASKS.append(task)
        analytics = MagicMock()
        monkeypatch.setattr(
            "core.workflow_analytics_engine.get_analytics_engine", lambda: analytics
        )
        resp = client.put("/api/v1/tasks/auto-1", json={"status": "completed"})
        assert resp.status_code == 200
        analytics.track_manual_override.assert_called_once_with(
            workflow_id="wf-1",
            execution_id="ex-1",
            resource_id="auto-1",
            action="task_updated",
            user_id="user-1",
            metadata={"updates": {"status": "completed"}},
        )

    def test_update_metadata_only(self, client):
        resp = client.put(
            "/api/v1/tasks/1", json={"metadata": {"workflow_id": "wf-9"}}
        )
        assert resp.status_code == 200
        assert resp.json()["task"]["metadata"]["workflow_id"] == "wf-9"


class TestDeleteTask:
    def test_not_found_404(self, client):
        resp = client.delete("/api/v1/tasks/nope")
        assert resp.status_code == 404

    def test_delete_success(self, client):
        resp = client.delete("/api/v1/tasks/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "1"
        assert len(m.MOCK_TASKS) == 1

    def test_delete_updates_project_count(self, client):
        proj = next(p for p in m.MOCK_PROJECTS if p.id == "project-1")
        proj.task_count = 5
        resp = client.delete("/api/v1/tasks/1")
        assert resp.status_code == 200
        assert proj.task_count == 4

    def test_delete_project_count_floor_at_zero(self, client):
        task = _task(id="t-orphan", project="project-2")
        m.MOCK_TASKS.append(task)
        proj = next(p for p in m.MOCK_PROJECTS if p.id == "project-2")
        proj.task_count = 0
        resp = client.delete("/api/v1/tasks/t-orphan")
        assert resp.status_code == 200
        assert proj.task_count == 0

    def test_delete_tracks_automated_override(self, client, monkeypatch):
        task = _task(id="auto-2", metadata={"workflow_id": "wf-2"})
        m.MOCK_TASKS.append(task)
        analytics = MagicMock()
        monkeypatch.setattr(
            "core.workflow_analytics_engine.get_analytics_engine", lambda: analytics
        )
        resp = client.delete("/api/v1/tasks/auto-2")
        assert resp.status_code == 200
        analytics.track_manual_override.assert_called_once_with(
            workflow_id="wf-2",
            execution_id="manual",
            resource_id="auto-2",
            action="task_deleted",
        )


class TestProjects:
    def test_get_projects_recalculates(self, client):
        resp = client.get("/api/v1/projects/")
        body = resp.json()
        assert body["success"] is True
        project_1 = next(p for p in body["projects"] if p["id"] == "project-1")
        # 2 mock tasks, 0 completed -> 0% progress, task_count from store
        assert project_1["progress"] == 0
        assert project_1["task_count"] == 2

    def test_get_projects_with_completed_tasks(self, client):
        m.MOCK_TASKS[0].status = "completed"
        m.MOCK_TASKS[1].status = "completed"
        resp = client.get("/api/v1/projects/")
        project_1 = next(p for p in resp.json()["projects"] if p["id"] == "project-1")
        assert project_1["task_count"] == 2
        assert project_1["progress"] == 100

    def test_get_projects_partial_progress(self, client):
        m.MOCK_TASKS[0].status = "completed"
        resp = client.get("/api/v1/projects/")
        project_1 = next(p for p in resp.json()["projects"] if p["id"] == "project-1")
        assert project_1["progress"] == 50

    def test_create_project(self, client):
        resp = client.post(
            "/api/v1/projects/", json={"name": "Mobile", "description": "app"}
        )
        body = resp.json()
        assert body["success"] is True
        assert body["project"]["name"] == "Mobile"
        assert body["project"]["task_count"] == 0
        assert body["project"]["progress"] == 0

    def test_update_project(self, client):
        resp = client.put("/api/v1/projects/project-1", json={"name": "Renamed"})
        body = resp.json()
        assert body["success"] is True
        assert body["project"]["name"] == "Renamed"
        assert body["project"]["description"] == "Main web application development"

    def test_update_project_not_found(self, client):
        resp = client.put("/api/v1/projects/nope", json={"name": "x"})
        assert resp.status_code == 404


class TestAsanaCredential:
    """W104-7: the hardcoded Asana PAT must be gone; env-driven instead."""

    def test_token_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("ASANA_ACCESS_TOKEN", "env-token-123")
        reloaded = importlib.reload(m)
        try:
            assert reloaded.ASANA_ACCESS_TOKEN == "env-token-123"
        finally:
            monkeypatch.delenv("ASANA_ACCESS_TOKEN")
            importlib.reload(m)

    def test_token_empty_without_env(self, monkeypatch):
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        reloaded = importlib.reload(m)
        try:
            assert reloaded.ASANA_ACCESS_TOKEN == ""
        finally:
            importlib.reload(m)

    def test_hardcoded_token_not_in_source(self):
        with open(m.__file__) as fh:
            source = fh.read()
        assert "2/1211551477617044" not in source
        assert "04904fb3621a011e810dc1c21ef41890" not in source

    def test_token_used_in_asana_request(self, client, monkeypatch):
        svc = _asana_patch(monkeypatch)
        monkeypatch.setattr(m, "ASANA_ACCESS_TOKEN", "custom-tok")
        svc.create_task = AsyncMock(return_value={"ok": True, "task": {"gid": "a1", "name": "n"}})
        monkeypatch.setattr(
            "core.behavior_analyzer.get_behavior_analyzer", lambda: MagicMock()
        )
        client.post(
            "/api/v1/tasks/",
            json={"title": "n", "dueDate": "2026-08-05T00:00:00", "platform": "asana"},
        )
        assert svc.create_task.await_args[0][0] == "custom-tok"


class TestModuleBootstrap:
    """Lines 17 / 25-28: sys.path insert + the guarded asana import."""

    def test_backend_root_inserted_when_missing(self, monkeypatch):
        backend_root = m.backend_root
        assert str(backend_root) in sys.path
        monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(backend_root)])
        reloaded = importlib.reload(m)
        try:
            assert str(backend_root) in sys.path
        finally:
            importlib.reload(m)

    def test_asana_import_error_sets_unavailable(self, monkeypatch):
        import sys as _sys

        with patch.dict(_sys.modules, {"integrations.asana_service": None}):
            reloaded = importlib.reload(m)
            assert reloaded.ASANA_AVAILABLE is False
            assert reloaded.asana_service is None
        importlib.reload(m)
