# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/external_pm_sync (standalone, zero LLM spend,
no network; fake db session + mocked integration services).

- sync_project_to_external: project-not-found error; unsupported platform
  error; platform name case-insensitivity; success + error dispatch to the
  right backend.
- _sync_to_asana: full success (project + milestones + tasks pushed, external
  id returned, description fallback when the project has none); create_project
  returning falsy → error; exception → error with a GENERIC message (BUG 87-3:
  str(e) leaked to the caller — project error-handling standard violation).
- _sync_to_linear: no-teams error; create_project success=False → error; full
  success (team id from first team, project + issues created); exception →
  generic message (BUG 87-3 same leak at line 106).
- milestone without tasks: no task pushes, sync still succeeds.
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.external_pm_sync import ExternalPMSyncService
from service_delivery.models import Milestone, Project, ProjectTask


def _proj(project_id="p1", name="Website", description=None):
    return SimpleNamespace(id=project_id, name=name, description=description)


def _ms(ms_id="ms1", project_id="p1", name="Phase 1"):
    return SimpleNamespace(id=ms_id, project_id=project_id, name=name)


def _task(task_id="t1", milestone_id="ms1", name="Build", description=None):
    return SimpleNamespace(
        id=task_id, milestone_id=milestone_id, name=name, description=description
    )


def _bind(exprs):
    for e in exprs:
        if hasattr(e, "right") and hasattr(e.right, "value"):
            return e.right.value
    return None


class _FakeQuery:
    def __init__(self, model, resolver):
        self.model = model
        self.exprs = []
        self._resolver = resolver

    def filter(self, *exprs):
        self.exprs.extend(exprs)
        return self

    def first(self):
        return self._resolver(self)

    def all(self):
        return self._resolver(self)


class _FakeDB:
    """Minimal project/milestone/task store keyed on the filter bind value."""

    def __init__(self, project=None, milestones=None, tasks=None):
        self.project = project
        self.milestones = milestones or []
        self.tasks = tasks or []

    def query(self, model):
        return _FakeQuery(model, self._resolve)

    def _resolve(self, q):
        b = _bind(q.exprs)
        if q.model is Project:
            if self.project and self.project.id == b:
                return self.project
            return None
        if q.model is Milestone:
            return [m for m in self.milestones if m.project_id == b]
        if q.model is ProjectTask:
            return [t for t in self.tasks if t.milestone_id == b]
        return []


@contextmanager
def _cm(value):
    yield value


def _run(coro):
    import asyncio
    return asyncio.run(coro)


@pytest.fixture()
def asana_cls():
    cls = MagicMock()
    cls.return_value.create_project = AsyncMock(
        return_value={"id": "asana-1", "name": "Website"}
    )
    cls.return_value.create_task = AsyncMock(return_value={"id": "task-1"})
    with patch("integrations.asana_real_service.AsanaRealService", cls):
        yield cls


@pytest.fixture()
def linear_cls():
    cls = MagicMock()
    cls.return_value.get_teams = AsyncMock(return_value=[{"id": "team-1"}])
    cls.return_value.create_project = AsyncMock(
        return_value={"success": True, "project": {"id": "lin-1"}}
    )
    cls.return_value.create_issue = AsyncMock(return_value={"id": "issue-1"})
    with patch("integrations.linear_service.LinearService", cls):
        yield cls


class TestSyncProjectToExternal:
    def test_project_not_found(self):
        fake_db = _FakeDB(project=None)
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p-missing", "asana"))
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_unsupported_platform(self):
        fake_db = _FakeDB(project=_proj())
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "jira"))
        assert result["status"] == "error"
        assert "not supported" in result["message"]

    def test_platform_case_insensitive_asana(self, asana_cls):
        fake_db = _FakeDB(
            project=_proj(),
            milestones=[_ms()],
            tasks=[_task()],
        )
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "ASANA"))
        assert result["status"] == "success"
        assert result["external_id"] == "asana-1"


class TestSyncToAsana:
    def test_success_pushes_project_tasks_and_milestones(self, asana_cls):
        fake_db = _FakeDB(
            project=_proj(),
            milestones=[_ms(), _ms("ms2", "p1", "Phase 2")],
            tasks=[_task(), _task("t2", "ms2", "Deploy")],
        )
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "asana"))
        assert result["status"] == "success"
        assert result["platform"] == "asana"
        svc = asana_cls.return_value
        svc.create_project.assert_awaited_once()
        assert svc.create_task.await_count == 2
        first_task = svc.create_task.await_args_list[0].args[0]
        assert first_task["title"] == "[Phase 1] Build"
        assert first_task["project"] == "asana-1"

    def test_milestone_without_tasks_still_succeeds(self, asana_cls):
        fake_db = _FakeDB(project=_proj(), milestones=[_ms()], tasks=[])
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "asana"))
        assert result["status"] == "success"
        asana_cls.return_value.create_task.assert_not_called()

    def test_description_fallback_when_none(self, asana_cls):
        fake_db = _FakeDB(project=_proj(description=None))
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            _run(ExternalPMSyncService().sync_project_to_external("p1", "asana"))
        kwargs = asana_cls.return_value.create_project.await_args.args[0]
        assert "Synced from Atom" in kwargs["description"]

    def test_create_project_falsy_returns_error(self, asana_cls):
        asana_cls.return_value.create_project = AsyncMock(return_value=None)
        fake_db = _FakeDB(project=_proj())
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "asana"))
        assert result["status"] == "error"
        assert "Failed to create project in Asana" in result["message"]

    def test_exception_returns_generic_message(self, asana_cls):
        """BUG 87-3 regression: the raw exception (str(e)) must not leak into
        the client-facing message."""
        asana_cls.return_value.create_project = AsyncMock(
            side_effect=RuntimeError("asana_api_key_secret_broken")
        )
        fake_db = _FakeDB(project=_proj())
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "asana"))
        assert result["status"] == "error"
        assert "asana_api_key_secret_broken" not in result["message"]


class TestSyncToLinear:
    def test_success_creates_project_and_issues(self, linear_cls):
        fake_db = _FakeDB(
            project=_proj(),
            milestones=[_ms()],
            tasks=[_task()],
        )
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "linear"))
        assert result["status"] == "success"
        assert result["external_id"] == "lin-1"
        svc = linear_cls.return_value
        svc.create_project.assert_awaited_once_with(
            name="Website", team_ids=["team-1"],
            description="Synced from Atom",
        )
        issue = svc.create_issue.await_args.kwargs
        assert issue["title"] == "[Phase 1] Build"
        assert issue["team_id"] == "team-1"

    def test_no_teams_returns_error(self, linear_cls):
        linear_cls.return_value.get_teams = AsyncMock(return_value=[])
        fake_db = _FakeDB(project=_proj())
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "linear"))
        assert result["status"] == "error"
        assert "No teams found" in result["message"]

    def test_create_project_unsuccessful_returns_error(self, linear_cls):
        linear_cls.return_value.create_project = AsyncMock(
            return_value={"success": False}
        )
        fake_db = _FakeDB(project=_proj())
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "linear"))
        assert result["status"] == "error"
        assert "Failed to create project in Linear" in result["message"]

    def test_exception_returns_generic_message(self, linear_cls):
        linear_cls.return_value.get_teams = AsyncMock(
            side_effect=RuntimeError("linear_oauth_token_secret")
        )
        fake_db = _FakeDB(project=_proj())
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            result = _run(ExternalPMSyncService().sync_project_to_external("p1", "linear"))
        assert result["status"] == "error"
        assert "linear_oauth_token_secret" not in result["message"]

    def test_description_fallback(self, linear_cls):
        fake_db = _FakeDB(project=_proj(description=None))
        with patch("core.external_pm_sync.get_db_session", return_value=_cm(fake_db)):
            _run(ExternalPMSyncService().sync_project_to_external("p1", "linear"))
        kwargs = linear_cls.return_value.create_project.await_args.kwargs
        assert kwargs["description"] == "Synced from Atom"
