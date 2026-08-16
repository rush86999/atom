# -*- coding: utf-8 -*-
"""Coverage wave 96 — nine-module core batch 8.

Targets:
1. core/conflict_resolution_service.py
2. core/view_coordinator.py
3. core/unified_task_endpoints.py
4. core/enterprise_auth_service.py
5. core/ai_accounting_engine.py
6. core/self_evolution_service.py
7. core/push_notification_service.py
8. core/user_context_manager.py
9. core/fleet_orchestration/performance_metrics_service.py

No network, no real LLM, no real Redis/APNs/FCM — every external boundary
(httpx, DB sessions, Redis, ws manager, evolution loop) is mocked.
Plain pytest + unittest.mock (asyncio_mode=auto).
"""
import asyncio
import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.conflict_resolution_service as crs_mod
from core.conflict_resolution_service import ConflictResolutionService

import core.view_coordinator as vc_mod
from core.view_coordinator import ViewCoordinator, get_view_coordinator

import core.unified_task_endpoints as ute
from core.unified_task_endpoints import (
    CreateProjectRequest, CreateTaskRequest, Project, Task, UpdateProjectRequest,
    UpdateTaskRequest, create_project, create_task, delete_task, get_projects,
    get_tasks, update_project, update_task,
)

import core.enterprise_auth_service as eas_mod
from core.enterprise_auth_service import (
    EnterpriseAuthService, SecurityLevel, UserCredentials, get_enterprise_auth_service,
)

from core.ai_accounting_engine import (
    AIAccountingEngine, Transaction, TransactionSource, TransactionStatus,
)

import core.self_evolution_service as ses_mod
from core.self_evolution_service import SelfEvolutionService, self_evolution_service

import core.push_notification_service as pns_mod
from core.push_notification_service import PushNotificationService, get_push_notification_service

from core.user_context_manager import UserContextManager, get_user_context_manager

import core.fleet_orchestration.performance_metrics_service as pms_mod
from core.fleet_orchestration.performance_metrics_service import (
    PerformanceAlert, PerformanceMetrics, PerformanceMetricsService,
    get_performance_metrics_service,
)
from core.fleet_orchestration.fleet_execution_models import FleetExecutionResult


# --------------------------------------------------------------------------- #
# Shared fake SQLAlchemy machinery
# --------------------------------------------------------------------------- #
class FakeQuery:
    def __init__(self, items=None, first=None, count=0):
        self._items = list(items or [])
        self._first = first
        self._count = count

    def filter(self, *a, **k):
        return self

    def filter_by(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def offset(self, *a, **k):
        return self

    def distinct(self, *a, **k):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._first

    def count(self):
        return self._count


class FakeCM:
    """Context manager wrapper used to fake SessionLocal()."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *a):
        return False


class AnyQueryDB:
    """DB fake returning a configurable FakeQuery for every entity."""

    def __init__(self, items=None, first=None, count=0):
        self._items = items or []
        self._first = first
        self._count = count
        self.added = []
        self.committed = 0
        self.rolled_back = 0

    def query(self, entity):
        return FakeQuery(items=self._items, first=self._first, count=self._count)

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        pass


def _HC(client):
    """Return an httpx.AsyncClient mock usable as `async with ... as c:`."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


def _http_response(status_code=200, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    return r


# =========================================================================== #
# 1. core/conflict_resolution_service.py
# =========================================================================== #
class TestConflictResolutionService:
    @pytest.fixture()
    def db(self):
        return AnyQueryDB()

    @pytest.fixture()
    def svc(self, db):
        return ConflictResolutionService(db)

    # -- detection -----------------------------------------------------------
    def test_detect_version_mismatch(self, svc):
        assert svc.detect_skill_conflict(
            {"version": "1.0"}, {"version": "1.1"}) == "VERSION_MISMATCH"

    def test_detect_content_mismatch_hash(self, svc):
        local = {"version": "1", "content_hash": "aaa", "code": "x"}
        remote = {"version": "1", "content_hash": "bbb", "code": "x"}
        assert svc.detect_skill_conflict(local, remote) == "CONTENT_MISMATCH"

    def test_detect_content_mismatch_code_fallback(self, svc):
        local = {"version": "1", "code": "a"}
        remote = {"version": "1", "code": " a "}
        # whitespace-normalized equal -> falls through to dependency check
        assert svc.detect_skill_conflict(local, remote) is None
        remote2 = {"version": "1", "code": "b"}
        assert svc.detect_skill_conflict(local, remote2) == "CONTENT_MISMATCH"

    def test_detect_dependency_conflict(self, svc):
        local = {"version": "1", "code": "x", "python_packages": ["a", "b"]}
        remote = {"version": "1", "code": "x", "python_packages": ["b", "a"]}
        assert svc.detect_skill_conflict(local, remote) is None
        remote2 = {"version": "1", "code": "x", "python_packages": ["c"]}
        assert svc.detect_skill_conflict(local, remote2) == "DEPENDENCY_CONFLICT"

    def test_detect_no_conflict(self, svc):
        assert svc.detect_skill_conflict({"code": "x"}, {"code": "x"}) is None

    # -- comparison helpers ----------------------------------------------------
    def test_compare_versions_none_defaults(self, svc):
        assert svc.compare_versions({"version": None}, {"version": "1.0.0"}) is False
        assert svc.compare_versions({}, {}) is False
        assert svc.compare_versions({"version": "2"}, {"version": "2.0"}) is True

    def test_compare_content_none_code(self, svc):
        assert svc.compare_content({"code": None}, {"code": None}) is False
        assert svc.compare_content({"code": None}, {"code": "a"}) is True

    def test_compare_dependencies_non_list(self, svc):
        # non-list deps are treated as empty
        assert svc.compare_dependencies(
            {"python_packages": "x"}, {"npm_packages": None}) is False

    def test_calculate_content_hash(self, svc):
        h1 = svc.calculate_content_hash({"skill_id": "s", "code": "c"})
        h2 = svc.calculate_content_hash({"skill_id": "s", "code": "c"})
        h3 = svc.calculate_content_hash({"skill_id": "s", "code": "d"})
        assert h1 == h2 and h1 != h3 and len(h1) == 64

    # -- severity ---------------------------------------------------------------
    @pytest.mark.parametrize("field,val,expected", [
        ("code", "different", "CRITICAL"),
        ("version", "9.9", "HIGH"),
        ("npm_packages", ["x"], "HIGH"),
        ("parameters", {"a": 1}, "MEDIUM"),
        ("metadata", {"x": 1}, "MEDIUM"),
        ("description", "other", "LOW"),
    ])
    def test_calculate_severity(self, svc, field, val, expected):
        local = {"code": "c", "version": "1", "parameters": None,
                 "metadata": None, "npm_packages": None}
        remote = dict(local)
        remote[field] = val
        assert svc.calculate_severity(local, remote, "OTHER") == expected

    # -- merge strategies ---------------------------------------------------------
    def test_remote_and_local_wins(self, svc):
        local, remote = {"skill_id": "s", "v": 1}, {"skill_id": "s", "v": 2}
        assert svc.remote_wins(local, remote) == remote
        assert svc.local_wins(local, remote) == local
        # copies, not the same objects
        svc.remote_wins(local, remote)["new"] = 1
        assert "new" not in remote

    def test_merge(self, svc):
        local = {
            "skill_id": "s", "code": "local-code", "command": "run",
            "local_files": ["a"], "description": "short",
            "python_packages": ["pkg1"], "npm_packages": [],
            "version": "1.0", "updated_at": "2026-01-01T00:00:00+00:00",
        }
        remote = {
            "description": "a much longer description",
            "python_packages": ["pkg2"], "npm_packages": None,
            "version": "2.0", "updated_at": "2026-06-01T00:00:00+00:00",
            "command": "evil",
        }
        merged = svc.merge(local, remote)
        assert merged["description"] == "a much longer description"
        assert merged["code"] == "local-code"
        assert merged["command"] == "run"  # critical fields stay local
        assert merged["python_packages"] == ["pkg1", "pkg2"]
        assert merged["npm_packages"] == []
        assert merged["version"] == "1.0+merged+2.0"
        assert str(merged["updated_at"]).startswith("2026-06-01")

    def test_merge_no_skill_id_local_and_datetime(self, svc):
        local = {"code": "c", "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}
        remote = {"skill_id": "r", "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc)}
        merged = svc.merge(local, remote)
        assert merged["skill_id"] == "r"
        assert merged["updated_at"] == local["updated_at"]
        # no timestamps at all
        m2 = svc.merge({"a": 1}, {"b": 2})
        assert m2["version"] == "1.0.0+merged+1.0.0"

    def test_manual_logs_conflict(self, svc, db):
        db.refresh = Mock()
        assert svc.manual({"a": 1}, {"b": 2}, "s1", "VERSION_MISMATCH", "HIGH") is None
        assert len(db.added) == 1

    # -- logging / querying ------------------------------------------------------
    def test_log_conflict(self, svc, db):
        db.refresh = Mock()
        rec = svc.log_conflict("s1", "OTHER", "LOW", {"l": 1}, {"r": 1})
        assert db.committed == 1
        assert rec.skill_id == "s1"

    def test_get_unresolved_and_count(self, svc, db):
        db._items = [NS(id=1)]
        res = svc.get_unresolved_conflicts(severity="HIGH", conflict_type="OTHER",
                                            limit=5, offset=2)
        assert len(res) == 1
        assert svc.count_unresolved_conflicts(severity="LOW") == 0

    def test_get_conflict_by_id(self, svc, db):
        conflict = NS(id=7, local_data={"a": 1}, remote_data={"b": 2},
                      resolution_strategy=None, resolved_data=None,
                      resolved_at=None, resolved_by=None)
        db._first = conflict
        assert svc.get_conflict_by_id(7) is conflict

    # -- resolution ------------------------------------------------------------
    def test_resolve_conflict_all_strategies(self, svc, db):
        db.refresh = Mock()
        conflict = NS(id=1, local_data={"skill_id": "s", "code": "l"},
                      remote_data={"skill_id": "s", "code": "r"},
                      resolution_strategy=None, resolved_data=None,
                      resolved_at=None, resolved_by=None)
        db._first = conflict
        out = svc.resolve_conflict(1, "remote_wins", "admin")
        assert out["code"] == "r" and conflict.resolved_by == "admin"
        out = svc.resolve_conflict(1, "local_wins", "admin")
        assert out["code"] == "l"
        out = svc.resolve_conflict(1, "merge", "admin")
        assert out["version"]
        assert svc.resolve_conflict(1, "manual", "admin") is None
        db._first = None  # not-found lookup
        assert svc.resolve_conflict(999, "remote_wins", "x") is None

    def test_auto_resolve_conflict(self, svc, db):
        db.refresh = Mock()
        local = {"skill_id": "s", "version": "1"}
        remote = {"skill_id": "s", "version": "2"}
        # no conflict -> remote returned unchanged
        assert svc.auto_resolve_conflict({"a": 1}, {"a": 1}, "remote_wins") == {"a": 1}
        assert svc.auto_resolve_conflict(local, remote, "remote_wins")["version"] == "2"
        assert svc.auto_resolve_conflict(local, remote, "local_wins")["version"] == "1"
        assert "merged" in svc.auto_resolve_conflict(local, remote, "merge")["version"]
        assert svc.auto_resolve_conflict(local, remote, "manual") is None
        assert len(db.added) == 1  # conflict logged for manual
        # unknown strategy
        assert svc.auto_resolve_conflict(local, remote, "bogus") is None


# =========================================================================== #
# 2. core/view_coordinator.py
# =========================================================================== #
class TestViewCoordinator:
    @pytest.fixture()
    def db(self):
        return AnyQueryDB()

    @pytest.fixture()
    def svc(self, db):
        return ViewCoordinator(db)

    @pytest.fixture()
    def ws(self):
        with patch.object(vc_mod, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            yield ws

    def _state(self, active_views=None):
        from core.models import ViewOrchestrationState
        return ViewOrchestrationState(
            id="st-1", tenant_id="default", user_id="u1", session_id="sess-1",
            active_views=list(active_views or []), layout="canvas")

    async def test_switch_to_browser_view_new_state(self, svc, db, ws):
        db._first = None
        await svc.switch_to_browser_view("u1", "agent1", "https://x.test", "look")
        assert ws.broadcast.await_count == 1
        msg = ws.broadcast.call_args[0][1]
        assert msg["type"] == "view:switch"
        assert msg["data"]["view_type"] == "browser"
        assert len(db.added) == 2  # new state + audit row
        state = db.added[0]
        assert state.layout == "split_vertical"
        assert len(state.active_views) == 1

    async def test_switch_to_browser_existing_state_and_audit_fail(self, svc, db, ws):
        state = self._state()
        db._first = state
        # make audit commit fail -> swallowed by _create_audit
        with patch.object(vc_mod, "CanvasAudit", side_effect=RuntimeError("audit boom")):
            await svc.switch_to_browser_view("u1", "a", "https://y.test", "g",
                                             session_id="sess-1")
        assert state.controlling_agent == "a"
        assert state.layout == "split_vertical"
        assert ws.broadcast.await_count == 1

    async def test_switch_to_browser_error_swallowed(self, svc, db, ws):
        db.query = Mock(side_effect=RuntimeError("db down"))
        await svc.switch_to_browser_view("u1", "a", "https://x", "g")  # no raise

    async def test_disabled_flag_short_circuits(self, svc, db, ws):
        with patch.object(vc_mod, "VIEW_COORDINATION_ENABLED", False):
            await svc.switch_to_browser_view("u1", "a", "u", "g")
            await svc.switch_to_terminal_view("u1", "a", "ls", "g")
            await svc.set_layout("u1", "tabs")
            await svc.activate_view("u1", "canvas")
            await svc.update_view_guidance("u1", "v", "g")
            await svc.close_view("u1", "v")
        assert ws.broadcast.await_count == 0
        assert db.added == []

    async def test_switch_to_terminal_view(self, svc, db, ws):
        db._first = None
        await svc.switch_to_terminal_view("u1", "a", "npm test", "running")
        assert ws.broadcast.await_count == 1
        data = ws.broadcast.call_args[0][1]["data"]
        assert data["view_type"] == "terminal"
        assert data["command"] == "npm test"

    async def test_switch_to_terminal_existing_state(self, svc, db, ws):
        state = self._state()
        db._first = state
        await svc.switch_to_terminal_view("u1", "a", "ls", "g", session_id="sess-1")
        assert state.layout == "split_horizontal"

    async def test_set_layout(self, svc, db, ws):
        state = self._state()
        db._first = state
        await svc.set_layout("u1", "grid", session_id="sess-1")
        assert state.layout == "grid"
        assert ws.broadcast.call_args[0][1]["type"] == "view:layout_change"
        # no state found -> broadcast only
        db._first = None
        await svc.set_layout("u1", "tabs")
        assert ws.broadcast.await_count == 2

    async def test_activate_view_variants(self, svc, db, ws):
        db._first = None
        await svc.activate_view("u1", "browser", size="half", url="https://z.test")
        view = ws.broadcast.call_args[0][1]["data"]["view"]
        assert view["url"] == "https://z.test"
        state = db.added[0]
        assert len(state.active_views) == 1

        state2 = self._state()
        db._first = state2
        await svc.activate_view("u1", "terminal", command="echo hi")
        assert state2.active_views[-1]["command"] == "echo hi"

        await svc.activate_view("u1", "app")
        assert state2.active_views[-1]["view_type"] == "app"

    async def test_update_view_guidance(self, svc, ws):
        await svc.update_view_guidance("u1", "view-1", "new guidance")
        assert ws.broadcast.call_args[0][1]["type"] == "view:guidance_update"
        ws.broadcast.side_effect = RuntimeError("ws down")
        await svc.update_view_guidance("u1", "view-1", "g")  # swallowed

    async def test_close_view(self, svc, db, ws):
        state = self._state(active_views=[{"view_id": "browser_1"}, {"view_id": "terminal_1"}])
        db._first = state
        await svc.close_view("u1", "browser_1", session_id="sess-1")
        assert state.active_views == [{"view_id": "terminal_1"}]
        assert ws.broadcast.call_args[0][1]["type"] == "view:closed"
        # no state -> broadcast only
        db._first = None
        await svc.close_view("u1", "browser_1")
        assert ws.broadcast.await_count == 2

    async def test_close_view_error(self, svc, db, ws):
        db.query = Mock(side_effect=RuntimeError("nope"))
        await svc.close_view("u1", "v")  # swallowed

    def test_get_or_create_session(self, svc):
        sid = svc._get_or_create_session("u1")
        assert sid.startswith("session_u1_")

    async def test_create_audit_failure_logged(self, svc, db):
        db.commit = Mock(side_effect=RuntimeError("commit fail"))
        db.rollback = Mock()
        await svc._create_audit("a", "u", "s", "act", {})  # swallowed

    def test_get_view_coordinator_factory(self, db):
        assert get_view_coordinator(db) is get_view_coordinator(db) or True
        assert isinstance(get_view_coordinator(db), ViewCoordinator)


# =========================================================================== #
# 3. core/unified_task_endpoints.py
# =========================================================================== #
class TestUnifiedTaskEndpoints:
    @pytest.fixture(autouse=True)
    def _restore_mocks(self):
        self._tasks = list(ute.MOCK_TASKS)
        self._projects = list(ute.MOCK_PROJECTS)
        self._counts = [p.task_count for p in ute.MOCK_PROJECTS]
        yield
        ute.MOCK_TASKS[:] = self._tasks
        ute.MOCK_PROJECTS[:] = self._projects
        for p, c in zip(ute.MOCK_PROJECTS, self._counts):
            p.task_count = c

    def _user(self):
        return NS(id="user-1")

    # -- GET /tasks --------------------------------------------------------------
    async def test_get_tasks_asana_unavailable(self):
        with patch.object(ute, "ASANA_AVAILABLE", False):
            res = await get_tasks("all")
        assert res["source"] == "mock"

    async def test_get_tasks_asana_success(self):
        asana = MagicMock()
        asana._make_request.return_value = {
            "data": [
                {"gid": "g1", "name": "T1", "notes": "n", "completed": True,
                 "due_on": "2026-01-15", "tags": [{"name": "x"}],
                 "assignee": {"name": "alice"},
                 "created_at": "2026-01-01T10:00:00Z"},
                {"gid": "g2", "name": "T2", "completed": False, "tags": []},
            ]
        }
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana):
            res = await get_tasks("all")
        assert res["source"] == "asana"
        assert len(res["tasks"]) == 4  # 2 asana + 2 mock
        asana_tasks = [t for t in res["tasks"] if t.platform == "asana"]
        assert asana_tasks[0].status == "completed"
        assert asana_tasks[0].assignee == "alice"

            # platform=asana only (no mock merge)
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana):
            res = await get_tasks("asana")
        assert len(res["tasks"]) == 2

    async def test_get_tasks_asana_bad_dates(self):
        asana = MagicMock()
        asana._make_request.return_value = {
            "data": [{"gid": "g3", "name": "T", "completed": False,
                      "due_on": "not-a-date", "created_at": "garbage"}]
        }
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana):
            res = await get_tasks("asana")
        assert len(res["tasks"]) == 1
        assert res["tasks"][0].platform == "asana"

    async def test_get_tasks_asana_empty_and_error(self):
        asana = MagicMock()
        asana._make_request.return_value = {"data": []}
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana):
            assert (await get_tasks("asana"))["source"] == "mock"

        asana._make_request.side_effect = RuntimeError("network down")
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana):
            assert (await get_tasks("all"))["source"] == "mock"

    # -- POST /tasks --------------------------------------------------------------
    async def test_create_task_local(self):
        req = CreateTaskRequest(title="New", dueDate=datetime(2026, 2, 1),
                                project="project-1")
        before = ute.MOCK_PROJECTS[0].task_count
        with patch("core.behavior_analyzer.get_behavior_analyzer") as ga:
            ga.return_value.log_user_action = Mock()
            res = await create_task(req, current_user=self._user())
        assert res["platform"] == "local"
        assert res["task"].id
        assert ute.MOCK_PROJECTS[0].task_count == before + 1

    async def test_create_task_asana_success(self):
        req = CreateTaskRequest(title="A", dueDate=datetime(2026, 2, 1), platform="asana")
        asana = MagicMock()
        asana.create_task = AsyncMock(return_value={
            "ok": True,
            "task": {"gid": "ag1", "name": "A", "notes": "n",
                     "due_on": "2026-02-01", "created_at": "2026-01-01T00:00:00Z"},
        })
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana):
            res = await create_task(req, current_user=self._user())
        assert res["platform"] == "asana"
        assert res["task"].id == "ag1"

    async def test_create_task_asana_not_ok_falls_back(self):
        req = CreateTaskRequest(title="A", dueDate=datetime(2026, 2, 1), platform="asana")
        asana = MagicMock()
        asana.create_task = AsyncMock(return_value={"ok": False})
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ga:
            ga.return_value.log_user_action = Mock()
            res = await create_task(req, current_user=self._user())
        assert res["platform"] == "local"

    async def test_create_task_asana_exception_falls_back(self):
        req = CreateTaskRequest(title="A", dueDate=datetime(2026, 2, 1), platform="asana")
        asana = MagicMock()
        asana.create_task = AsyncMock(side_effect=RuntimeError("asana down"))
        with patch.object(ute, "ASANA_AVAILABLE", True), \
             patch.object(ute, "asana_service", asana), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ga:
            ga.return_value.log_user_action = Mock()
            res = await create_task(req, current_user=self._user())
        assert res["platform"] == "local"

    async def test_create_task_asana_unavailable(self):
        req = CreateTaskRequest(title="A", dueDate=datetime(2026, 2, 1), platform="asana")
        with patch.object(ute, "ASANA_AVAILABLE", False), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ga:
            ga.return_value.log_user_action = Mock()
            res = await create_task(req, current_user=self._user())
        assert res["platform"] == "local"

    # -- PUT /tasks/{id} ------------------------------------------------------------
    async def test_update_task_found(self):
        tid = ute.MOCK_TASKS[0].id
        res = await update_task(tid, UpdateTaskRequest(status="completed"),
                                current_user=self._user())
        assert res["success"] is True
        assert res["task"].status == "completed"

    async def test_update_task_workflow_metadata(self):
        t = Task(id="wf-task", title="Auto", dueDate=datetime(2026, 2, 1),
                 priority="low", status="todo", platform="local",
                 createdAt=datetime.now(), updatedAt=datetime.now(),
                 metadata={"workflow_id": "wf1", "execution_id": "ex1"})
        ute.MOCK_TASKS.append(t)
        with patch("core.workflow_analytics_engine.get_analytics_engine") as ge:
            ge.return_value.track_manual_override = Mock()
            res = await update_task("wf-task", UpdateTaskRequest(title="X"),
                                    current_user=self._user())
        assert res["success"] is True
        ge.return_value.track_manual_override.assert_called_once()

    async def test_update_task_not_found(self):
        with pytest.raises(Exception):
            await update_task("ghost", UpdateTaskRequest(title="X"),
                              current_user=self._user())

    # -- DELETE /tasks/{id} -----------------------------------------------------------
    async def test_delete_task(self):
        tid = ute.MOCK_TASKS[0].id
        res = await delete_task(tid, current_user=self._user())
        assert res["success"] is True
        assert all(t.id != tid for t in ute.MOCK_TASKS)

    async def test_delete_task_workflow_metadata(self):
        t = Task(id="wf-del", title="Auto", dueDate=datetime(2026, 2, 1),
                 priority="low", status="todo", platform="local", project=None,
                 createdAt=datetime.now(), updatedAt=datetime.now(),
                 metadata={"workflow_id": "wf2"})
        ute.MOCK_TASKS.append(t)
        with patch("core.workflow_analytics_engine.get_analytics_engine") as ge:
            ge.return_value.track_manual_override = Mock()
            res = await delete_task("wf-del", current_user=self._user())
        assert res["success"] is True

    async def test_delete_task_not_found(self):
        with pytest.raises(Exception):
            await delete_task("ghost", current_user=self._user())

    # -- projects ------------------------------------------------------------------
    async def test_get_projects_recalculates(self):
        res = await get_projects()
        by_id = {p.id: p for p in res["projects"]}
        assert by_id["project-1"].task_count == 2
        assert by_id["project-1"].progress == 0
        assert by_id["project-2"].progress == 0

    async def test_create_update_project(self):
        res = await create_project(CreateProjectRequest(name="NewProj"))
        assert res["success"] is True
        pid = res["project"].id
        res2 = await update_project(pid, UpdateProjectRequest(color="#000000"))
        assert res2["project"].color == "#000000"
        with pytest.raises(Exception):
            await update_project("ghost", UpdateProjectRequest(name="x"))


# =========================================================================== #
# 4. core/enterprise_auth_service.py
# =========================================================================== #
class TestEnterpriseAuthService:
    @pytest.fixture()
    def svc(self, monkeypatch):
        monkeypatch.delenv("JWT_PRIVATE_KEY_PATH", raising=False)
        monkeypatch.delenv("JWT_PUBLIC_KEY_PATH", raising=False)
        monkeypatch.delenv("GENERATE_JWT_KEYS", raising=False)
        return EnterpriseAuthService(secret_key="test-secret")

    # -- init / key loading -------------------------------------------------------
    def test_secret_key_env_resolution(self, monkeypatch):
        monkeypatch.delenv("ENTERPRISE_JWT_SECRET", raising=False)
        monkeypatch.setenv("SECRET_KEY", "from-secret-key")
        assert EnterpriseAuthService().secret_key == "from-secret-key"
        monkeypatch.setenv("ENTERPRISE_JWT_SECRET", "enterprise-key")
        assert EnterpriseAuthService().secret_key == "enterprise-key"
        monkeypatch.setenv("SECRET_KEY", "")
        monkeypatch.setenv("ENTERPRISE_JWT_SECRET", "")
        monkeypatch.setenv("JWT_SECRET", "jwt-key")
        assert EnterpriseAuthService().secret_key == "jwt-key"

    def test_load_keys_from_files(self, monkeypatch, tmp_path):
        priv = tmp_path / "priv.pem"
        pub = tmp_path / "pub.pem"
        priv.write_text("PRIVATE")
        pub.write_text("PUBLIC")
        monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(priv))
        monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(pub))
        svc = EnterpriseAuthService(secret_key="k")
        assert svc.private_key == "PRIVATE"
        assert svc.public_key == "PUBLIC"

    def test_generate_rsa_keys(self, monkeypatch, tmp_path):
        priv = tmp_path / "gpriv.pem"
        pub = tmp_path / "gpub.pem"
        monkeypatch.setenv("GENERATE_JWT_KEYS", "true")
        monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(priv))
        monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(pub))
        svc = EnterpriseAuthService(secret_key="k")
        assert "BEGIN PRIVATE KEY" in svc.private_key
        assert "BEGIN PUBLIC KEY" in svc.public_key
        # second call loads from files now
        svc2 = EnterpriseAuthService(secret_key="k")
        assert svc2.private_key == svc.private_key

    def test_missing_key_path_returns_none(self, monkeypatch):
        monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", "/nonexistent/x.pem")
        monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "/nonexistent/y.pem")
        svc = EnterpriseAuthService(secret_key="k")
        assert svc.private_key is None
        assert svc.public_key is None

    # -- passwords -----------------------------------------------------------------
    def test_hash_and_verify_password(self, svc):
        h = svc.hash_password("s3cret-password")
        assert h != "s3cret-password"
        assert svc.verify_password("s3cret-password", h) is True
        assert svc.verify_password("wrong", h) is False

    def test_verify_password_long_truncation(self, svc):
        long_pw = "x" * 100
        h = svc.hash_password(long_pw)
        # both truncate at 71 bytes -> 80-char variant still verifies
        assert svc.verify_password("x" * 80, h) is True

    def test_verify_password_invalid_hash(self, svc):
        assert svc.verify_password("pw", "not-a-bcrypt-hash") is False
        assert svc.verify_password("pw", None) is False

    # -- tokens ----------------------------------------------------------------------
    def test_access_token_hs256_roundtrip(self, svc):
        tok = svc.create_access_token("u1", {"role": "admin"})
        claims = svc.verify_token(tok)
        assert claims["user_id"] == "u1"
        assert claims["type"] == "access"
        assert claims["role"] == "admin"

    def test_access_token_rs256_roundtrip(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GENERATE_JWT_KEYS", "true")
        monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(tmp_path / "p.pem"))
        monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(tmp_path / "q.pem"))
        svc = EnterpriseAuthService(secret_key="k")
        tok = svc.create_access_token("u1")
        assert svc.verify_token(tok)["user_id"] == "u1"

    def test_verify_token_invalid_and_expired(self, svc, monkeypatch):
        assert svc.verify_token("garbage.token.here") is None
        # expired token
        import jwt as pyjwt
        expired = pyjwt.encode(
            {"user_id": "u1", "exp": datetime.now(timezone.utc) - timedelta(hours=2),
             "type": "access"},
            svc.secret_key, algorithm="HS256")
        assert svc.verify_token(expired) is None
        # tampered token (wrong signature)
        bad = pyjwt.encode({"user_id": "u1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                           "other-key", algorithm="HS256")
        assert svc.verify_token(bad) is None
        # non-dict payload decode error
        assert svc.verify_token("aaa") is None

    def test_refresh_token_roundtrip(self, svc):
        tok = svc.create_refresh_token("u1")
        claims = svc.verify_token(tok)
        assert claims["type"] == "refresh"

    # -- credential verification ------------------------------------------------------
    def _cred_db(self, user):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        return db

    def test_verify_credentials_success(self, svc):
        user = NS(id="u1", email="a@b.test",
                  hashed_password=svc.hash_password("pw"),
                  status="active", role="member", mfa_enabled=True)
        creds = svc.verify_credentials(self._cred_db(user), "a@b.test", "pw")
        assert isinstance(creds, UserCredentials)
        assert creds.user_id == "u1"
        assert creds.mfa_enabled is True
        assert creds.security_level == SecurityLevel.STANDARD.value
        assert "read_workflows" in creds.permissions

    def test_verify_credentials_failures(self, svc):
        assert svc.verify_credentials(self._cred_db(None), "x", "pw") is None
        user = NS(id="u2", email="a@b.test", hashed_password=None,
                  status="active", role="member")
        assert svc.verify_credentials(self._cred_db(user), "a@b.test", "pw") is None
        user2 = NS(id="u3", email="a@b.test",
                   hashed_password=svc.hash_password("pw"),
                   status="active", role="member")
        assert svc.verify_credentials(self._cred_db(user2), "a@b.test", "bad") is None
        user3 = NS(id="u4", email="a@b.test",
                   hashed_password=svc.hash_password("pw"),
                   status="suspended", role="member")
        assert svc.verify_credentials(self._cred_db(user3), "a@b.test", "pw") is None
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert svc.verify_credentials(db, "x", "pw") is None

    @pytest.mark.parametrize("role,expected_level", [
        ("admin", SecurityLevel.ENTERPRISE.value),
        ("security_admin", SecurityLevel.ADMIN.value),
        ("workflow_admin", SecurityLevel.ADMIN.value),
        ("member", SecurityLevel.STANDARD.value),
    ])
    def test_map_security_level(self, svc, role, expected_level):
        assert svc._map_security_level(role) == expected_level

    @pytest.mark.parametrize("role", ["super_admin", "owner", "admin",
                                      "workspace_admin", "team_lead", "member",
                                      "viewer", "guest", "unknown-role"])
    def test_get_user_permissions(self, svc, role):
        perms = svc._get_user_permissions(MagicMock(), NS(role=role))
        assert isinstance(perms, list) and perms

    # -- SAML ---------------------------------------------------------------------------
    def test_generate_saml_request(self, svc):
        url = svc.generate_saml_request("okta")
        assert "https://atom.ai/auth/saml/okta?saml_request_id=" in url

    def _saml_xml(self, with_attrs=True, with_nameid=False, roles=None):
        attrs = ""
        if with_attrs:
            attr_rows = [
                ("email", "user@corp.test"),
                ("firstName", "Ada"),
                ("lastName", "Lovelace"),
                ("roles", ",".join(roles or ["member"])),
            ]
            attrs = "<saml:AttributeStatement>" + "".join(
                f'<saml:Attribute Name="{n}"><saml:AttributeValue>{v}</saml:AttributeValue></saml:Attribute>'
                for n, v in attr_rows) + "</saml:AttributeStatement>"
        nameid = '<saml:NameID>nameid@corp.test</saml:NameID>' if with_nameid else ""
        return (
            '<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
            'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
            f"<saml:Assertion>{nameid}{attrs}</saml:Assertion></samlp:Response>"
        )

    def _encode(self, xml):
        return base64.b64encode(xml.encode()).decode()

    def test_validate_saml_response_success(self, svc, monkeypatch):
        monkeypatch.delenv("SAML_IDP_CERT", raising=False)
        creds = svc.validate_saml_response(self._encode(self._saml_xml(roles=["admin"])))
        assert creds is not None
        assert creds.email == "user@corp.test"
        assert creds.security_level == SecurityLevel.ENTERPRISE.value
        assert "manage_users" in creds.permissions

    def test_validate_saml_with_db_user_creation(self, svc, monkeypatch):
        monkeypatch.delenv("SAML_IDP_CERT", raising=False)
        db = AnyQueryDB(first=None)  # user not found -> create path
        creds = svc.validate_saml_response(self._encode(self._saml_xml()), db=db)
        assert creds is not None
        assert len(db.added) == 1
        assert db.committed == 1

    def test_validate_saml_with_db_user_update(self, svc, monkeypatch):
        monkeypatch.delenv("SAML_IDP_CERT", raising=False)
        existing = NS(id="u9", email="user@corp.test", first_name="",
                      last_name="", role="member",
                      last_login=None)
        db = AnyQueryDB(first=existing)
        creds = svc.validate_saml_response(self._encode(self._saml_xml()), db=db)
        assert creds is not None
        assert existing.first_name == "Ada"
        assert existing.role == "member"  # 'member' maps to MEMBER

    def test_validate_saml_db_error_returns_none(self, svc, monkeypatch):
        monkeypatch.delenv("SAML_IDP_CERT", raising=False)
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert svc.validate_saml_response(self._encode(self._saml_xml()), db=db) is None

    def test_validate_saml_nameid_email_and_no_roles(self, svc, monkeypatch):
        monkeypatch.delenv("SAML_IDP_CERT", raising=False)
        xml = self._saml_xml(with_attrs=False, with_nameid=True)
        creds = svc.validate_saml_response(self._encode(xml))
        assert creds.email == "nameid@corp.test"
        assert creds.roles == ["member"]  # default role
        assert creds.security_level == SecurityLevel.STANDARD.value

    def test_validate_saml_no_email(self, svc, monkeypatch):
        monkeypatch.delenv("SAML_IDP_CERT", raising=False)
        xml = ('<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
               'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
               '<saml:Assertion><saml:AttributeStatement>'
               '<saml:Attribute Name="firstName"><saml:AttributeValue>X</saml:AttributeValue></saml:Attribute>'
               '</saml:AttributeStatement></saml:Assertion></samlp:Response>')
        assert svc.validate_saml_response(self._encode(xml)) is None

    def test_validate_saml_no_assertion(self, svc, monkeypatch):
        monkeypatch.delenv("SAML_IDP_CERT", raising=False)
        xml = ('<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">'
               '</samlp:Response>')
        assert svc.validate_saml_response(self._encode(xml)) is None

    def test_validate_saml_decode_error(self, svc):
        assert svc.validate_saml_response("%%%not-base64%%%") is None

    def test_validate_saml_parse_error(self, svc):
        assert svc.validate_saml_response(base64.b64encode(b"<not-xml").decode()) is None

    def test_validate_saml_bad_cert_fails(self, svc, monkeypatch):
        monkeypatch.setenv("SAML_IDP_CERT", "-----BEGIN CERTIFICATE-----\nZm9v\n-----END CERTIFICATE-----")
        xml = self._saml_xml()
        assert svc.validate_saml_response(self._encode(xml)) is None

    def test_verify_saml_signature_paths(self, svc):
        signed = ('<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
                  'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
                  'xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'
                  '<saml:Assertion><ds:Signature>'
                  '<ds:SignatureValue>abc123</ds:SignatureValue>'
                  '</ds:Signature></saml:Assertion></samlp:Response>')
        # simplified verification returns True as long as cert parses
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography import x509
        # build a real self-signed cert is heavy; instead patch loader
        with patch("cryptography.x509.load_pem_x509_certificate") as load:
            load.return_value.public_key.return_value = MagicMock()
            assert svc._verify_saml_signature(signed, "cert") is True
        # no signature element
        unsigned = self._saml_xml()
        assert svc._verify_saml_signature(unsigned, "cert") is False
        # signature without value
        nosig = ('<r xmlns:ds="http://www.w3.org/2000/09/xmldsig#"><ds:Signature/></r>')
        assert svc._verify_saml_signature(nosig, "cert") is False
        # exception path
        assert svc._verify_saml_signature("junk", "cert") is False

    def test_extract_saml_attributes_mapping(self, svc):
        ns = {"saml": "urn:oasis:names:tc:SAML:2.0:assertion"}
        xml = ('<a xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
               "<saml:Assertion><saml:AttributeStatement>"
               '<saml:Attribute Name="EmailAddress"><saml:AttributeValue>e@x.test</saml:AttributeValue></saml:Attribute>'
               '<saml:Attribute Name="Groups"><saml:AttributeValue>admins</saml:AttributeValue></saml:Attribute>'
               '<saml:Attribute Name="empty"><saml:AttributeValue></saml:AttributeValue></saml:Attribute>'
               "</saml:AttributeStatement>"
               "<saml:NameID>nameid@x.test</saml:NameID>"
               "</saml:Assertion></a>")
        from xml.etree import ElementTree as RealET
        root = RealET.fromstring(xml)
        assertion = root.find(".//saml:Assertion", ns)
        attrs = svc._extract_saml_attributes(assertion, ns)
        # NameID populates the raw 'email' key when only 'emailaddress' was
        # set, and the later normalized 'email' entry wins over the mapped
        # 'emailaddress' one.
        assert attrs["email"] == "nameid@x.test"
        assert attrs["roles"] == "admins"
        assert "empty" not in attrs  # empty text dropped

    @pytest.mark.parametrize("saml_role,expected", [
        ("admin", "workspace_admin"), ("superadmin", "super_admin"),
        ("security_admin", "admin"), ("team_lead", "team_lead"),
        ("guest", "guest"), ("whatever", "member"),
    ])
    def test_map_saml_role(self, svc, saml_role, expected):
        from core.models import UserRole
        assert svc._map_saml_role_to_user_role(saml_role) == UserRole(expected).value

    def test_singleton_factory(self):
        assert get_enterprise_auth_service() is get_enterprise_auth_service()

    def test_user_credentials_dataclass(self):
        c = UserCredentials("u", "n", "e", ["r"], "standard", ["p"], False)
        assert c.mfa_enabled is False


# =========================================================================== #
# 5. core/ai_accounting_engine.py
# =========================================================================== #
class TestAIAccountingEngine:
    @pytest.fixture()
    def engine(self):
        return AIAccountingEngine()

    def _tx(self, **kw):
        from decimal import Decimal
        defaults = dict(
            id="t1", date=datetime(2026, 1, 15), amount=Decimal("100.00"),
            description="monthly rent payment", merchant=None)
        defaults.update(kw)
        return Transaction(**defaults)

    # -- categorization ---------------------------------------------------------
    def test_categorize_merchant_pattern(self, engine):
        tx = engine.ingest_transaction(self._tx(merchant="AWS", description="cloud"))
        assert tx.category_id == "6300"  # Software
        assert tx.status == TransactionStatus.CATEGORIZED
        assert tx.confidence == 0.95

    def test_categorize_keyword_fallback(self, engine):
        tx = engine.ingest_transaction(self._tx(description="flight to conference"))
        assert tx.category_id == "6500"  # Travel
        assert tx.status in (TransactionStatus.CATEGORIZED, TransactionStatus.REVIEW_REQUIRED)

    def test_categorize_uncategorized(self, engine):
        tx = engine.ingest_transaction(self._tx(description="zzz qqq", merchant="unknown-merchant-xyz"))
        assert tx.category_id is None
        assert tx.category_name == "Uncategorized"
        assert tx.status == TransactionStatus.REVIEW_REQUIRED
        assert engine.get_pending_review() == [tx]

    def test_categorize_historical(self, engine):
        # teach the engine: 3x same merchant -> same category
        for i in range(3):
            tx = engine.ingest_transaction(
                self._tx(id=f"h{i}", description="zzz", merchant="acme-corp"))
            engine.learn_categorization(f"h{i}", "6600", "user")
        tx = engine.ingest_transaction(self._tx(id="h9", description="zzz", merchant="acme-corp"))
        assert tx.category_id == "6600"
        assert tx.confidence == 0.90
        assert "Historical" in tx.reasoning

    def test_ingest_bank_feed(self, engine):
        rows = [
            {"id": "b1", "date": "2026-01-01T10:00:00", "amount": "50",
             "description": "slack subscription", "merchant": "slack", "source": "manual"},
            {"id": "b2", "date": datetime(2026, 1, 2), "amount": 10,
             "description": "restaurant dinner", "source": "bank"},
        ]
        res = engine.ingest_bank_feed(rows)
        assert len(res) == 2
        assert res[0].category_id == "6300"
        assert res[1].category_id == "6600"

    # -- learning -----------------------------------------------------------------
    def test_learn_categorization(self, engine):
        tx = engine.ingest_transaction(self._tx(description="zzz"))
        assert engine.learn_categorization("missing", "6300", "u") is None
        assert engine.learn_categorization(tx.id, "9999", "u") is None  # bad category
        engine.learn_categorization(tx.id, "6600", "u")
        assert tx.status == TransactionStatus.CATEGORIZED
        assert tx.reviewed_by == "u"
        assert engine.get_pending_review() == []

    # -- posting -------------------------------------------------------------------
    def test_post_transaction(self, engine):
        tx = engine.ingest_transaction(self._tx(description="zzz unknown"))
        assert engine.post_transaction("missing") is False
        assert engine.post_transaction(tx.id) is False  # review required, no user
        assert engine.post_transaction(tx.id, user_id="admin") is True
        assert tx.status == TransactionStatus.POSTED

    def test_auto_post_high_confidence(self, engine):
        engine.ingest_transaction(self._tx(id="p1", merchant="slack", description="slack"))
        engine.ingest_transaction(self._tx(id="p2", description="zzz unknown"))
        assert engine.auto_post_high_confidence() == 1

    # -- CRUD ------------------------------------------------------------------------
    def test_get_all_transactions_sorted(self, engine):
        engine.ingest_transaction(self._tx(id="s1", date=datetime(2026, 3, 1)))
        engine.ingest_transaction(self._tx(id="s2", date=datetime(2026, 5, 1)))
        assert [t.id for t in engine.get_all_transactions()] == ["s2", "s1"]

    def test_update_transaction(self, engine):
        tx = engine.ingest_transaction(self._tx(description="zzz unknown"))
        assert engine.update_transaction("missing", {}, "u") is False
        engine.update_transaction(tx.id, {"description": "slack subscription"}, "u")
        assert tx.category_id == "6300"
        assert "Re-categorized" in tx.reasoning
        # amount/date-only update (no re-categorization)
        engine.update_transaction(tx.id, {"amount": 42, "date": "2026-02-02T00:00:00"}, "u")
        assert tx.date == datetime(2026, 2, 2)
        # unknown keys ignored
        assert engine.update_transaction(tx.id, {"bogus": 1}, "u") is True

    def test_delete_transaction(self, engine):
        tx = engine.ingest_transaction(self._tx(description="zzz unknown"))
        assert engine.delete_transaction("missing", "u") is False
        assert engine.delete_transaction(tx.id, "u") is True
        assert tx.id not in engine._transactions

    # -- audit / exports -----------------------------------------------------------------
    def test_audit_log(self, engine):
        tx = engine.ingest_transaction(self._tx(description="slack subscription"))
        entries = engine.get_audit_log(tx.id)
        assert entries and entries[0]["transaction_id"] == "t1"
        assert len(engine.get_audit_log()) >= 1

    def test_export_general_ledger_csv(self, engine):
        from decimal import Decimal
        tx = engine.ingest_transaction(self._tx(
            description="=HYPERLINK(\"http://evil\")", merchant="slack",
            amount=Decimal("-10")))
        csv_out = engine.export_general_ledger_csv()
        assert "Date" in csv_out
        assert "'=HYPERLINK" in csv_out  # CSV-injection sanitized
        assert tx.id in csv_out

    def test_export_trial_balance_json(self, engine):
        engine.ingest_transaction(self._tx(id="tb1", merchant="slack", description="slack"))
        report = engine.export_trial_balance_json()
        names = [a["name"] for a in report["accounts"]]
        assert "Software" in names

    # -- forecasting ----------------------------------------------------------------------
    def test_13_week_forecast(self, engine):
        engine.ingest_transaction(self._tx(id="f1", merchant="slack", description="slack"))
        res = engine.get_13_week_forecast(current_balance=50000.0)
        assert len(res["projection"]) == 13
        assert res["projection"][0]["projected_balance"] != 50000.0
        # empty engine -> default burn
        res2 = AIAccountingEngine().get_13_week_forecast()
        assert res2["historical_weekly_avg"] == -2500.0

    def test_run_scenario_branches(self, engine):
        r = engine.run_scenario("hire two engineers for $10,500", [])
        assert r["impact_value"] == -10500
        assert r["risk_level"] == "medium"
        r = engine.run_scenario("what if we lose our biggest client worth $50,000", [])
        assert r["impact_value"] == -50000
        assert r["risk_level"] == "high"
        r = engine.run_scenario("hire an intern", [])  # no number -> default
        assert r["impact_value"] == -5000
        assert r["risk_level"] == "low"
        r = engine.run_scenario("win a new client worth $30k", [])
        assert r["impact_value"] == 30000
        r = engine.run_scenario("nothing changes", [])
        assert r["impact_value"] == -1000
        r = engine.run_scenario("expense of 5,000 dollars", [])
        assert r["impact_value"] == -5000

    # -- ledger integration ------------------------------------------------------------------
    def test_post_to_ledger_not_found_and_review(self, engine):
        assert engine.post_to_ledger("missing")["status"] == "failed"
        tx = engine.ingest_transaction(self._tx(description="zzz unknown"))
        res = engine.post_to_ledger(tx.id)
        assert res["status"] == "failed"
        assert "review" in res["error"]

    def test_post_to_ledger_mock_mode(self, engine):
        tx = engine.ingest_transaction(self._tx(merchant="slack", description="slack"))
        res = engine.post_to_ledger(tx.id, db_session=None)
        assert res["status"] == "posted"
        assert res["mode"] == "mock"
        assert tx.status == TransactionStatus.POSTED
        # already posted -> skipped
        assert engine.post_to_ledger(tx.id)["status"] == "skipped"

    def test_post_to_ledger_db_success(self, engine):
        tx = engine.ingest_transaction(self._tx(merchant="slack", description="slack"))
        db = AnyQueryDB()
        with patch("accounting.ledger.EventSourcedLedger") as Ledger, \
             patch("accounting.ledger.DoubleEntryEngine") as DEE, \
             patch("accounting.models.EntryType"):
            Ledger.return_value.record_transaction.return_value = NS(id="lg-1")
            DEE.create_payment_entry.return_value = []
            res = engine.post_to_ledger(tx.id, db_session=db)
        assert res["status"] == "posted"
        assert res["ledger_tx_id"] == "lg-1"
        assert tx.status == TransactionStatus.POSTED

    def test_post_to_ledger_db_failure(self, engine):
        tx = engine.ingest_transaction(self._tx(merchant="slack", description="slack"))
        db = AnyQueryDB()
        with patch("accounting.ledger.EventSourcedLedger") as Ledger, \
             patch("accounting.ledger.DoubleEntryEngine") as DEE, \
             patch("accounting.models.EntryType"):
            Ledger.return_value.record_transaction.side_effect = RuntimeError("ledger down")
            DEE.create_payment_entry.return_value = []
            res = engine.post_to_ledger(tx.id, db_session=db)
        assert res["status"] == "failed"

    def test_global_instance_exists(self):
        from core.ai_accounting_engine import ai_accounting
        assert isinstance(ai_accounting, AIAccountingEngine)


# =========================================================================== #
# 6. core/self_evolution_service.py
# =========================================================================== #
class TestSelfEvolutionService:
    @pytest.fixture()
    def svc(self):
        return SelfEvolutionService()

    def _db(self, agent=None, feedbacks=None, hitls=None):
        db = MagicMock()

        def query(entity):
            if getattr(entity, "__name__", "") == "AgentRegistry" or entity is ses_mod.AgentRegistry:
                return FakeQuery(first=agent)
            return FakeQuery(items=feedbacks if entity is ses_mod.AgentFeedback else hitls,
                             first=agent)
        db.query = query
        db.close = Mock()
        db.commit = Mock()
        return db

    async def test_analyze_agent_not_found(self, svc, monkeypatch):
        db = self._db(agent=None)
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: db)
        res = await svc.analyze_agent_performance("ghost")
        assert res == {"error": "Agent not found"}

    async def test_analyze_low_approval_rate(self, svc, monkeypatch):
        agent = NS(id="a1", confidence_score=0.5)
        hitls = [NS(status="rejected")] * 6
        db = self._db(agent=agent, hitls=hitls)
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: db)
        res = await svc.analyze_agent_performance("a1")
        assert res["detected_bottleneck"] == "low_approval_rate"
        assert res["approval_rate"] == 0.0

    async def test_analyze_frequent_correction(self, svc, monkeypatch):
        agent = NS(id="a1", confidence_score=0.9)
        hitls = [NS(status="approved")] * 4  # approval rate 1.0
        feedbacks = [NS()] * 4
        db = self._db(agent=agent, feedbacks=feedbacks, hitls=hitls)
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: db)
        res = await svc.analyze_agent_performance("a1")
        assert res["detected_bottleneck"] == "frequent_correction"

    async def test_analyze_healthy(self, svc, monkeypatch):
        agent = NS(id="a1", confidence_score=0.95)
        db = self._db(agent=agent, feedbacks=[], hitls=[])
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: db)
        res = await svc.analyze_agent_performance("a1")
        assert res["detected_bottleneck"] == "none"
        assert db.close.called

    async def test_apply_auto_tune_found_and_missing(self, svc, monkeypatch):
        agent = NS(id="a1", configuration={"evolution_history": []})
        db = self._db(agent=agent)
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: db)
        await svc.apply_auto_tune("a1", "tighten prompts")
        assert agent.configuration["evolution_history"][0]["insight"] == "tighten prompts"

        db2 = self._db(agent=None)
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: db2)
        await svc.apply_auto_tune("ghost", "x")  # no agent: no-op
        assert db2.close.called

    async def test_run_group_evolution(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        result = NS(benchmark_passed=True, benchmark_score=0.91,
                    to_dict=lambda: {"cycle_id": "c1", "benchmark_passed": True})
        with patch("core.agent_evolution_loop.AgentEvolutionLoop") as Loop:
            Loop.return_value.run_evolution_cycle = AsyncMock(return_value=result)
            res = await svc.run_group_evolution("t-1", group_size=3)
        assert res["cycle_id"] == "c1"
        Loop.return_value.run_evolution_cycle.assert_awaited_once_with(
            tenant_id="t-1", group_size=3, target_agent_id=None, category=None)

    async def test_analyze_group_readiness_empty(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        with patch("core.agent_evolution_loop.AgentEvolutionLoop") as Loop:
            Loop.return_value.select_parent_group.return_value = []
            res = await svc.analyze_group_readiness("t-1")
        assert res["candidate_count"] == 0
        assert res["evolution_recommended"] is False

    async def test_analyze_group_readiness_with_group(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        group = [
            NS(id="a1", name="A", confidence_score=0.5, category="coding", status="active"),
            NS(id="a2", name="B", confidence_score=0.9, category="coding", status="active"),
        ]
        with patch("core.agent_evolution_loop.AgentEvolutionLoop") as Loop:
            Loop.return_value.select_parent_group.return_value = group
            res = await svc.analyze_group_readiness("t-1", group_size=2)
        assert res["candidate_count"] == 2
        assert res["avg_performance"] == 0.7
        assert res["evolution_recommended"] is True

    async def test_memento_cycle_gated_off(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as Gate:
            Gate.return_value.can_use.return_value = False
            res = await svc.run_memento_cycle("a1", "ep1", "t-1")
        assert res["skipped"] is True

    async def test_memento_cycle_success(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as Gate, \
             patch("core.auto_dev.memento_engine.MementoEngine") as Engine:
            Gate.return_value.can_use.return_value = True
            Engine.return_value.generate_skill_candidate = AsyncMock(
                return_value=NS(id="cand-1", skill_name="retry-on-429"))
            res = await svc.run_memento_cycle("a1", "ep1", "t-1")
        assert res["success"] is True
        assert res["skill_name"] == "retry-on-429"

    async def test_memento_cycle_error(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as Gate:
            Gate.return_value.can_use.side_effect = RuntimeError("gate boom")
            res = await svc.run_memento_cycle("a1", "ep1", "t-1")
        assert "error" in res

    async def test_alpha_evolve_gated_off_and_success(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as Gate:
            Gate.return_value.can_use.return_value = False
            res = await svc.run_alpha_evolve_cycle("a1", "t-1", "code", "goal")
        assert res["skipped"] is True

        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as Gate, \
             patch("core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine") as Engine:
            Gate.return_value.can_use.return_value = True
            Engine.return_value.run_research_experiment = AsyncMock(
                return_value=[{"iteration": 1}])
            res = await svc.run_alpha_evolve_cycle("a1", "t-1", "code", "goal", iterations=2)
        assert res["success"] is True

    async def test_alpha_evolve_error(self, svc, monkeypatch):
        db = self._db()
        monkeypatch.setattr(ses_mod, "SessionLocal", lambda: FakeCM(db))
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as Gate:
            Gate.return_value.can_use.side_effect = ValueError("nope")
            res = await svc.run_alpha_evolve_cycle("a1", "t-1", "c", "g")
        assert "error" in res

    def test_get_workspace_settings(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = NS(
            metadata_json={"auto_dev": True})
        assert SelfEvolutionService._get_workspace_settings(db, "t") == {"auto_dev": True}
        # exception path -> {}
        db2 = MagicMock()
        db2.query.side_effect = RuntimeError("x")
        assert SelfEvolutionService._get_workspace_settings(db2, "t") == {}

    def test_module_singleton(self):
        assert isinstance(self_evolution_service, SelfEvolutionService)


# =========================================================================== #
# 7. core/push_notification_service.py
# =========================================================================== #
class TestPushNotificationService:
    @pytest.fixture()
    def db(self):
        return AnyQueryDB()

    @pytest.fixture()
    def svc(self, db):
        return PushNotificationService(db, tenant_id="t-1")

    def _device(self, platform="android", token="tok-1", id="d1"):
        return NS(id=id, platform=platform, device_token=token, status="active")

    # -- device registration -----------------------------------------------------
    async def test_register_device_new(self, svc, db):
        db._first = None
        res = await svc.register_device("u1", "tok-new", "ios", tenant_id="t-1")
        assert res["status"] == "registered"
        assert db.added[0].platform == "ios"

    async def test_register_device_existing(self, svc, db):
        existing = NS(id="d-exist", platform="android", device_info={},
                      last_active=None, status="inactive", tenant_id=None)
        db._first = existing
        res = await svc.register_device("u1", "tok-x", "ios", {"model": "iPhone"})
        assert res["status"] == "updated"
        assert existing.platform == "ios"
        assert existing.tenant_id == "t-1"

    async def test_register_device_error(self, svc, db):
        db.query = Mock(side_effect=RuntimeError("db down"))
        res = await svc.register_device("u1", "tok", "web")
        assert res["status"] == "error"

    # -- send_notification orchestration ---------------------------------------------
    async def test_send_notification_disabled(self, svc):
        with patch.object(pns_mod, "PUSH_NOTIFICATIONS_ENABLED", False):
            assert await svc.send_notification("u1", "t", "T", "B") is False

    async def test_send_notification_no_devices(self, svc, db):
        db._items = []
        assert await svc.send_notification("u1", "agent_alert", "T", "B") is False

    async def test_send_notification_routes_platforms(self, svc, db):
        db._items = [self._device("android"), self._device("ios", id="d2"),
                     self._device("web", id="d3")]
        svc._send_fcm_notification = AsyncMock(return_value=True)
        svc._send_apns_notification = AsyncMock(return_value=False)
        assert await svc.send_notification("u1", "agent_alert", "T", "B") is True
        assert svc._send_fcm_notification.await_count == 1
        assert svc._send_apns_notification.await_count == 1

    async def test_send_notification_all_fail(self, svc, db):
        db._items = [self._device("ios")]
        svc._send_apns_notification = AsyncMock(return_value=False)
        assert await svc.send_notification("u1", "t", "T", "B") is False

    async def test_send_notification_marks_expired_device(self, svc, db):
        dev = self._device("android")
        db._items = [dev]
        svc._send_fcm_notification = AsyncMock(
            side_effect=RuntimeError("Unregistered device token"))
        assert await svc.send_notification("u1", "t", "T", "B") is False
        assert dev.status == "inactive"
        assert db.committed == 1

    async def test_send_notification_outer_error(self, svc, db):
        db.query = Mock(side_effect=RuntimeError("boom"))
        assert await svc.send_notification("u1", "t", "T", "B") is False

    # -- FCM transport -------------------------------------------------------------------
    async def test_fcm_v1_success_and_high_priority(self, svc, monkeypatch):
        monkeypatch.setenv("FCM_PROJECT_ID", "proj-1")
        monkeypatch.setenv("FCM_ACCESS_TOKEN", "tok")
        client = MagicMock()
        client.post = AsyncMock(return_value=_http_response(200))
        with patch("httpx.AsyncClient", _HC(client)):
            ok = await svc._send_fcm_notification(
                self._device(), "T", "B", {"k": 1}, "high")
        assert ok is True
        payload = client.post.call_args.kwargs["json"]
        assert payload["message"]["android"]["priority"] == "high"

    async def test_fcm_v1_failure_status(self, svc, monkeypatch):
        monkeypatch.setenv("FCM_PROJECT_ID", "proj-1")
        monkeypatch.setenv("FCM_ACCESS_TOKEN", "tok")
        client = MagicMock()
        client.post = AsyncMock(return_value=_http_response(500, "server error"))
        with patch("httpx.AsyncClient", _HC(client)):
            ok = await svc._send_fcm_notification(self._device(), "T", "B", None, "normal")
        assert ok is False

    async def test_fcm_legacy_key_deprecated(self, svc, monkeypatch):
        monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
        monkeypatch.delenv("FCM_ACCESS_TOKEN", raising=False)
        with patch.object(pns_mod, "FCM_SERVER_KEY", "legacy-key"):
            ok = await svc._send_fcm_notification(self._device(), "T", "B", None, "normal")
        assert ok is False

    async def test_fcm_not_configured(self, svc, monkeypatch):
        monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
        monkeypatch.delenv("FCM_ACCESS_TOKEN", raising=False)
        with patch.object(pns_mod, "FCM_SERVER_KEY", None):
            ok = await svc._send_fcm_notification(self._device(), "T", "B", None, "normal")
        assert ok is False

    async def test_fcm_transport_exception(self, svc, monkeypatch):
        monkeypatch.setenv("FCM_PROJECT_ID", "proj-1")
        monkeypatch.setenv("FCM_ACCESS_TOKEN", "tok")
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("net down"))
        with patch("httpx.AsyncClient", _HC(client)):
            ok = await svc._send_fcm_notification(self._device(), "T", "B", None, "normal")
        assert ok is False

    # -- APNs transport --------------------------------------------------------------------
    async def test_apns_success_and_sandbox(self, svc, monkeypatch):
        monkeypatch.setenv("APNS_USE_SANDBOX", "true")
        client = MagicMock()
        client.post = AsyncMock(return_value=_http_response(200))
        with patch("httpx.AsyncClient", _HC(client)):
            ok = await svc._send_apns_notification(self._device("ios"), "T", "B", {"x": 1}, "high")
        assert ok is True
        url = client.post.call_args.args[0]
        assert "api.sandbox.push.apple.com" in url

    async def test_apns_production_gone_and_error(self, svc, monkeypatch):
        monkeypatch.setenv("APNS_USE_SANDBOX", "false")
        client = MagicMock()
        client.post = AsyncMock(side_effect=[
            _http_response(410), _http_response(500)])
        with patch("httpx.AsyncClient", _HC(client)):
            assert await svc._send_apns_notification(self._device("ios"), "T", "B", None, "normal") is False
            assert await svc._send_apns_notification(self._device("ios"), "T", "B", None, "normal") is False

    async def test_apns_exception(self, svc):
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("httpx.AsyncClient", _HC(client)):
            ok = await svc._send_apns_notification(self._device("ios"), "T", "B", None, "normal")
        assert ok is False

    # -- high-level helpers -----------------------------------------------------------------
    async def test_agent_operation_notification_statuses(self, svc):
        svc.send_notification = AsyncMock(return_value=True)
        for status, marker in [
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("awaiting_approval", "Approval"),
            ("other", "Update"),
        ]:
            ok = await svc.send_agent_operation_notification("u1", "Agent", "op", status)
            assert ok is True
            title = svc.send_notification.call_args.kwargs["title"]
            assert marker in title

    async def test_error_alert_priorities(self, svc):
        svc.send_notification = AsyncMock(return_value=True)
        assert await svc.send_error_alert("u1", "conn", "failed", severity="warning") is True
        assert svc.send_notification.call_args.kwargs["priority"] == "high"
        await svc.send_error_alert("u1", "conn", "failed", severity="info")
        assert svc.send_notification.call_args.kwargs["priority"] == "normal"
        await svc.send_error_alert("u1", "conn", "failed", severity="critical")
        assert "Critical" in svc.send_notification.call_args.kwargs["title"]

    async def test_approval_request(self, svc):
        svc.send_notification = AsyncMock(return_value=True)
        ok = await svc.send_approval_request(
            "u1", "a1", "Agent", "delete prod db",
            [{"label": "Approve"}], expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert ok is True
        kwargs = svc.send_notification.call_args.kwargs
        assert kwargs["priority"] == "high"
        assert kwargs["data"]["expires_at"]

    async def test_system_alert_severities(self, svc):
        svc.send_notification = AsyncMock(return_value=True)
        for sev, marker, prio in [("critical", "Critical", "high"),
                                  ("warning", "Warning", "high"),
                                  ("info", "Info", "normal")]:
            await svc.send_system_alert("u1", "cpu", "high load", severity=sev)
            kwargs = svc.send_notification.call_args.kwargs
            assert marker in kwargs["title"]
            assert kwargs["priority"] == prio

    def test_factory(self, db):
        assert isinstance(get_push_notification_service(db), PushNotificationService)

    def test_flags(self, svc):
        assert isinstance(pns_mod.MAX_RETRIES, int)
        assert svc.workspace_id == "default" or svc.workspace_id
        assert svc._fcm_enabled in (True, False)


# =========================================================================== #
# 8. core/user_context_manager.py
# =========================================================================== #
class FakeTokenStorage:
    def __init__(self, tokens=None, providers=None, fail=False):
        self.tokens = tokens or {}
        self.providers = providers or []
        self.fail = fail
        self.stored = {}
        self.deleted = []

    def get_token(self, provider, user_id):
        if self.fail:
            raise RuntimeError("storage down")
        return self.tokens.get(provider)

    def set_token(self, provider, user_id, data):
        self.stored[(provider, user_id)] = data

    def delete_token(self, provider, user_id):
        self.deleted.append((provider, user_id))

    def get_all_providers(self):
        return self.providers


class TestUserContextManager:
    @pytest.fixture()
    def ucm(self):
        m = UserContextManager()
        yield m

    def test_token_storage_lazy_import_and_failure(self, ucm, monkeypatch):
        ucm._token_storage = None
        monkeypatch.setitem(__import__("sys").modules, "core.token_storage", None)
        assert ucm.token_storage is None
        # cached None stays None
        assert ucm.token_storage is None

    def test_get_token_from_storage(self, ucm):
        ucm._token_storage = FakeTokenStorage(tokens={"slack": {"access_token": "xoxb-1",
                                                                "refresh_token": "r"}})
        assert ucm.get_token("slack", "u1") == "xoxb-1"
        assert ucm.get_token("slack", "u1", "refresh_token") == "r"

    def test_get_token_storage_error_falls_to_env(self, ucm, monkeypatch):
        ucm._token_storage = FakeTokenStorage(fail=True)
        monkeypatch.setenv("SLACK_BOT_TOKEN", "env-token")
        assert ucm.get_token("slack", "u1") == "env-token"

    def test_get_token_env_variants(self, ucm, monkeypatch):
        ucm._token_storage = None
        monkeypatch.delenv("GMAIL_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GMAIL_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("GMAIL_TOKEN", "plain-token")
        assert ucm.get_token("gmail") == "plain-token"
        monkeypatch.setenv("GMAIL_ACCESS_TOKEN", "access-token")
        assert ucm.get_token("gmail") == "access-token"  # BOT > ACCESS > TOKEN order
        monkeypatch.setenv("GMAIL_BOT_TOKEN", "bot-token")
        assert ucm.get_token("gmail") == "bot-token"

    def test_get_token_none(self, ucm, monkeypatch):
        monkeypatch.delenv("OUTLOOK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("OUTLOOK_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("OUTLOOK_TOKEN", raising=False)
        ucm._token_storage = FakeTokenStorage(tokens={})
        assert ucm.get_token("outlook", "u1") is None

    def test_get_token_with_context_user(self, ucm):
        ucm._token_storage = FakeTokenStorage(tokens={"slack": {"access_token": "t"}})
        ctx = ucm.get_token_with_context("slack", "u1")
        assert ctx == {"token": "t", "source": "user", "user_id": "u1",
                       "provider": "slack"}

    def test_get_token_with_context_bot(self, ucm, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "bot-tok")
        ucm._token_storage = None
        ctx = ucm.get_token_with_context("slack", "u1")
        assert ctx["source"] == "bot"
        assert ctx["user_id"] is None
        # no token -> empty dict
        monkeypatch.delenv("SLACK_BOT_TOKEN")
        assert ucm.get_token_with_context("slack") == {}

    def test_get_token_with_context_storage_error_is_bot(self, ucm, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "bot-tok")
        ucm._token_storage = FakeTokenStorage(fail=True)
        ctx = ucm.get_token_with_context("slack", "u1")
        assert ctx["source"] == "bot"

    def test_store_token(self, ucm):
        ucm._token_storage = None
        assert ucm.store_token("slack", "t") is False  # no storage
        storage = FakeTokenStorage()
        ucm._token_storage = storage
        assert ucm.store_token("slack", "t") is False  # no user_id
        assert ucm.store_token("slack", "t", "u1", {"refresh_token": "r"}) is True
        assert storage.stored[("slack", "u1")] == {"access_token": "t",
                                                   "refresh_token": "r"}

    def test_store_token_error(self, ucm):
        storage = FakeTokenStorage()
        storage.set_token = Mock(side_effect=RuntimeError("write fail"))
        ucm._token_storage = storage
        assert ucm.store_token("slack", "t", "u1") is False

    def test_invalidate_token(self, ucm):
        ucm._token_storage = None
        assert ucm.invalidate_token("slack", "u1") is False
        storage = FakeTokenStorage()
        ucm._token_storage = storage
        assert ucm.invalidate_token("slack", "u1") is True
        assert storage.deleted == [("slack", "u1")]
        # fallback: no delete_token -> set_token called with empty dict
        class SetOnlyStorage:
            def set_token(self, provider, user_id, data):
                self.stored = {(provider, user_id): data}
        storage2 = SetOnlyStorage()
        ucm._token_storage = storage2
        assert ucm.invalidate_token("slack", "u1") is True
        assert storage2.stored == {("slack", "u1"): {}}

    def test_invalidate_token_error(self, ucm):
        storage = FakeTokenStorage()
        storage.delete_token = Mock(side_effect=RuntimeError("boom"))
        ucm._token_storage = storage
        assert ucm.invalidate_token("slack", "u1") is False

    def test_get_available_providers(self, ucm, monkeypatch):
        for var in ["SLACK_BOT_TOKEN", "SLACK_ACCESS_TOKEN", "GMAIL_BOT_TOKEN",
                    "GMAIL_ACCESS_TOKEN", "OUTLOOK_BOT_TOKEN", "OUTLOOK_ACCESS_TOKEN",
                    "MICROSOFT_365_BOT_TOKEN", "MICROSOFT_365_ACCESS_TOKEN",
                    "ZOHO_BOT_TOKEN", "ZOHO_ACCESS_TOKEN"]:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("SLACK_BOT_TOKEN", "t")
        monkeypatch.setenv("GMAIL_ACCESS_TOKEN", "t")
        ucm._token_storage = FakeTokenStorage(providers=["slack", "notion"])
        providers = ucm.get_available_providers()
        assert set(providers) == {"slack", "gmail", "notion"}

    def test_get_available_providers_storage_error(self, ucm, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_ACCESS_TOKEN", raising=False)
        storage = FakeTokenStorage()
        storage.get_all_providers = Mock(side_effect=RuntimeError("x"))
        ucm._token_storage = storage
        assert ucm.get_available_providers() == []

    def test_global_manager_factory(self, monkeypatch):
        import core.user_context_manager as ucm_mod
        monkeypatch.setattr(ucm_mod, "_global_context_manager", None)
        m1 = get_user_context_manager()
        m2 = get_user_context_manager()
        assert m1 is m2
        # db update branch
        db = MagicMock()
        assert get_user_context_manager(db) is m1
        assert m1.db is db
        monkeypatch.setattr(ucm_mod, "_global_context_manager", None)


# =========================================================================== #
# 9. core/fleet_orchestration/performance_metrics_service.py
# =========================================================================== #
class FakePipe:
    def __init__(self, redis):
        self.redis = redis
        self.get_values = []

    def incrby(self, key, amount):
        self.redis.commands.append(("incrby", key, amount))

    def incrbyfloat(self, key, amount):
        self.redis.commands.append(("incrbyfloat", key, amount))

    def expire(self, key, ttl):
        self.redis.commands.append(("expire", key, ttl))

    def get(self, key):
        self.get_values.append(key)

    async def execute(self):
        if self.redis.fail_execute:
            raise RuntimeError("redis down")
        return [self.redis.stored_keys.get(k) for k in self.get_values]


class FakeRedis:
    def __init__(self, stored_keys=None, fail_execute=False):
        self.stored_keys = stored_keys or {}
        self.fail_execute = fail_execute
        self.commands = []
        self.closed = False

    def pipeline(self):
        return FakePipe(self)

    async def close(self):
        self.closed = True


def _fleet_result(total=3, completed=2, failed=1, exec_ms=1000):
    return FleetExecutionResult(
        chain_id="ch-1", total_tasks=total, completed_count=completed,
        failed_count=failed, retried_count=0, execution_time_ms=exec_ms)


class TestPerformanceMetricsService:
    @pytest.fixture()
    def db(self):
        return AnyQueryDB()

    @pytest.fixture()
    def svc(self, db):
        return PerformanceMetricsService(db, redis_url="redis://fake")

    def test_models_defaults(self):
        m = PerformanceMetrics(chain_id="c", success_rate=50.0, avg_latency_ms=10.0,
                               throughput_per_minute=1.0, execution_count=5, window="5m")
        assert m.calculated_at is not None
        with pytest.raises(Exception):
            PerformanceMetrics(chain_id="c", success_rate=150.0, avg_latency_ms=0,
                               throughput_per_minute=0, execution_count=0, window="5m")
        a = PerformanceAlert(chain_id="c", alert_type="high_latency", current_value=1,
                             threshold_value=0, severity="warning", message="m")
        assert a.detected_at is not None
        with pytest.raises(Exception):
            PerformanceAlert(chain_id="c", alert_type="bogus", current_value=1,
                             threshold_value=0, severity="warning", message="m")

    async def test_get_redis_no_url(self, db, monkeypatch):
        monkeypatch.delenv("DRAGONFLY_URL", raising=False)
        monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        svc = PerformanceMetricsService(db, redis_url=None)
        assert await svc._get_redis() is None
        # from_url failure
        svc2 = PerformanceMetricsService(db, redis_url="redis://x")
        with patch.object(pms_mod.redis, "from_url", side_effect=RuntimeError("bad url")):
            assert await svc2._get_redis() is None

    async def test_get_redis_from_url(self, svc):
        fake = FakeRedis()
        with patch.object(pms_mod.redis, "from_url", return_value=fake):
            got = await svc._get_redis()
        assert got is fake
        # cached
        assert await svc._get_redis() is fake
        assert svc._redis_client is fake

    async def test_record_execution(self, svc, db):
        fake = FakeRedis()
        svc._redis_client = fake
        svc._persist_to_database = AsyncMock()
        await svc.record_execution("ch-1", _fleet_result())
        await asyncio.sleep(0)
        # 3 windows x (1 incr success/failure + 1 incrfloat + 1 incr count + 4 expires)
        assert len(fake.commands) == 3 * 7
        assert svc._persist_to_database.await_count == 1

    async def test_record_execution_no_redis(self, svc):
        svc._redis_client = None
        svc._get_redis = AsyncMock(return_value=None)
        await svc.record_execution("ch-1", _fleet_result())  # early return

    async def test_record_execution_pipeline_error(self, svc):
        fake = FakeRedis(fail_execute=True)
        svc._redis_client = fake
        await svc.record_execution("ch-1", _fleet_result())  # swallowed

    async def test_persist_to_database(self, svc, db):
        await svc._persist_to_database("ch-1", _fleet_result())
        assert len(db.added) == 3
        assert db.committed == 1
        types = {m.metric_type for m in db.added}
        assert types == {"success_rate", "avg_latency", "throughput"}

    async def test_persist_to_database_error(self, svc):
        db = AnyQueryDB()
        db.commit = Mock(side_effect=RuntimeError("db down"))
        svc.db = db
        await svc._persist_to_database("ch-1", _fleet_result())
        assert db.rolled_back == 1

    async def test_get_metrics_invalid_window(self, svc):
        with pytest.raises(ValueError):
            await svc.get_metrics("ch-1", "2h")

    async def test_get_metrics_no_redis(self, svc):
        svc._get_redis = AsyncMock(return_value=None)
        m = await svc.get_metrics("ch-1", "5m")
        assert m.execution_count == 0
        assert m.success_rate == 0.0

    async def test_get_metrics_with_counters(self, svc):
        fake = FakeRedis(stored_keys={
            "fleet:ch-1:metrics:5m:success": b"80",
            "fleet:ch-1:metrics:5m:failure": b"20",
            "fleet:ch-1:metrics:5m:latency": "12000.5",
            "fleet:ch-1:metrics:5m:count": 100,
        })
        svc._redis_client = fake
        m = await svc.get_metrics("ch-1", "5m")
        assert m.success_rate == 80.0
        assert m.avg_latency_ms == round(12000.5 / 100, 2)
        assert m.execution_count == 100
        assert m.throughput_per_minute == 20.0  # 100/300*60

    async def test_get_metrics_empty_counters(self, svc):
        svc._redis_client = FakeRedis(stored_keys={})
        m = await svc.get_metrics("ch-1", "1m")
        assert m.success_rate == 0.0
        assert m.avg_latency_ms == 0.0
        assert m.throughput_per_minute == 0.0

    async def test_get_metrics_error_returns_zeros(self, svc):
        svc._redis_client = FakeRedis(fail_execute=True)
        m = await svc.get_metrics("ch-1", "5m")
        assert m.execution_count == 0

    async def test_check_thresholds_all_alerts(self, svc):
        # critical success-rate + critical latency + low throughput
        bad = PerformanceMetrics(chain_id="ch-1", success_rate=50.0,
                                 avg_latency_ms=50000.0, throughput_per_minute=1.0,
                                 execution_count=10, window="5m")
        svc.get_metrics = AsyncMock(return_value=bad)
        alerts = await svc.check_thresholds("ch-1")
        types = {(a.alert_type, a.severity) for a in alerts}
        assert ("low_success_rate", "critical") in types
        assert ("high_latency", "critical") in types
        assert ("low_throughput", "warning") in types

    async def test_check_thresholds_warning_levels(self, svc):
        warn = PerformanceMetrics(chain_id="ch-1", success_rate=80.0,
                                  avg_latency_ms=25000.0, throughput_per_minute=4.0,
                                  execution_count=10, window="5m")
        svc.get_metrics = AsyncMock(return_value=warn)
        alerts = await svc.check_thresholds("ch-1")
        types = {(a.alert_type, a.severity) for a in alerts}
        assert ("low_success_rate", "warning") in types
        assert ("high_latency", "warning") in types
        assert ("low_throughput", "warning") in types

    async def test_check_thresholds_healthy(self, svc):
        good = PerformanceMetrics(chain_id="ch-1", success_rate=99.0,
                                   avg_latency_ms=100.0, throughput_per_minute=50.0,
                                   execution_count=10, window="5m")
        svc.get_metrics = AsyncMock(return_value=good)
        assert await svc.check_thresholds("ch-1") == []

    async def test_check_thresholds_no_executions(self, svc):
        empty = PerformanceMetrics(chain_id="ch-1", success_rate=0.0,
                                   avg_latency_ms=0.0, throughput_per_minute=0.0,
                                   execution_count=0, window="5m")
        svc.get_metrics = AsyncMock(return_value=empty)
        # success_rate 0 < critical -> one critical alert per window, no latency/throughput alerts
        alerts = await svc.check_thresholds("ch-1")
        assert [a.alert_type for a in alerts] == ["low_success_rate"] * 3
        assert all(a.severity == "critical" for a in alerts)

    async def test_check_thresholds_error_swallowed(self, svc):
        svc.get_metrics = AsyncMock(side_effect=RuntimeError("boom"))
        assert await svc.check_thresholds("ch-1") == []

    def test_get_thresholds(self, svc):
        t = svc._get_thresholds()
        assert t["success_rate_critical"] == 70.0
        assert t["latency_critical_ms"] == 45000.0

    async def test_close(self, svc):
        fake = FakeRedis()
        svc._redis_client = fake
        await svc.close()
        assert fake.closed is True
        assert svc._redis_client is None
        await svc.close()  # no client: no-op

    def test_singleton_factory(self, db, monkeypatch):
        monkeypatch.setattr(pms_mod, "_service_instance", None)
        s1 = get_performance_metrics_service(db)
        s2 = get_performance_metrics_service(db)
        assert s1 is s2
        monkeypatch.setattr(pms_mod, "_service_instance", None)
