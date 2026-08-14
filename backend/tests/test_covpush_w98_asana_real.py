"""Coverage wave 98 — integrations/asana_real_service.py (TDD, 0% baseline).

Fully mocked deps (aiohttp fake session, circuit_breaker, rate_limiter, audit
logger), zero network, zero LLM spend.

BUG 1 (FIXED, TDD RED->GREEN): `__init__` defaulted ASANA_ACCESS_TOKEN to a
REAL hardcoded credential ("2/1211551477617044/...") when the env var was
unset, leaking a production token into source + shipping it in every process.
Test test_no_env_token_no_hardcoded_credential asserts the token is falsy
when ASANA_ACCESS_TOKEN is unset — RED before the fix, GREEN after (defaults
changed to ""). Same for the hardcoded workspace_gid.

BUG 2 (FIXED, TDD RED->GREEN): `_make_request` DELETE branch returned
{"success": True} unconditionally without reading the HTTP status — deletes
reported success on 401/404/500 (fail-open). Test
test_make_request_delete_failure asserts {"success": False} on non-2xx — RED
before the fix, GREEN after.

Covers: __init__ (param/env/default), _make_request (GET/POST/PUT/DELETE
success, DELETE failure, exception -> {"errors": [...]}), get_tasks (project
gid / workspace search / no data), create_task (success, failure, circuit
breaker open -> 503, rate limited -> 429, exception -> None), update_task
(all field mappings + failure + breaker + rate + exception), delete_task
(success, failure, breaker, rate, exception), get_projects (success, failure,
breaker, rate, exception), create_project (success, failure, breaker, rate,
exception), both converters (completed/todo, tags, assignee, due_on, color map
hit/miss, defaults).
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from integrations import asana_real_service as ar
from integrations.asana_real_service import AsanaRealService


# ── Fake aiohttp plumbing (same shape as wave-98 zoom handler) ───────────────
class _FakeResponse:
    def __init__(self, status=200, payload=None, text="err"):
        self.status = status
        self._payload = payload
        self._text = text

    async def json(self):
        return self._payload or {}

    async def text(self):
        return self._text


class _FakeRespCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _next(self):
        if len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)

    def get(self, *a, **k):
        return _FakeRespCM(self._next())

    def post(self, *a, **k):
        return _FakeRespCM(self._next())

    def put(self, *a, **k):
        return _FakeRespCM(self._next())

    def delete(self, *a, **k):
        return _FakeRespCM(self._next())


def _mock_session(*responses):
    return patch.object(
        ar.aiohttp,
        "ClientSession",
        MagicMock(return_value=_FakeSession(responses)),
    )


def _asana_task(**over):
    task = {
        "gid": "t-1",
        "name": "Task One",
        "notes": "desc",
        "due_on": "2026-08-20",
        "completed": False,
        "assignee": {"name": "Rushi"},
        "tags": [{"name": "urgent"}],
        "created_at": "2026-08-01T00:00:00.000Z",
        "modified_at": "2026-08-02T00:00:00.000Z",
    }
    task.update(over)
    return task


def _asana_project(**over):
    proj = {
        "gid": "p-1",
        "name": "Project One",
        "notes": "pdesc",
        "color": "dark-pink",
    }
    proj.update(over)
    return proj


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ASANA_ACCESS_TOKEN", "tok-asana")
    monkeypatch.setenv("ASANA_WORKSPACE_GID", "ws-1")


@pytest.fixture
def svc():
    return AsanaRealService()


@pytest.fixture(autouse=True)
def _guards():
    """Circuit breaker open, rate limiter unlimited, audit stubbed."""
    with patch.object(ar.circuit_breaker, "is_enabled",
                      new=AsyncMock(return_value=True)), \
            patch.object(ar.rate_limiter, "is_rate_limited",
                         new=AsyncMock(return_value=(False, 100))), \
            patch.object(ar, "log_integration_attempt",
                         return_value={"start_time": 0.0}), \
            patch.object(ar, "log_integration_complete",
                         MagicMock(return_value=0.1)):
        yield


class TestInit:
    def test_params_override_env(self, svc):
        s = AsanaRealService(access_token="tok-p",
                             workspace_gid="ws-p")
        assert s.access_token == "tok-p"
        assert s.workspace_gid == "ws-p"
        assert s.BASE_URL == "https://app.asana.com/api/1.0"

    def test_env_used(self, svc):
        assert svc.access_token == "tok-asana"
        assert svc.workspace_gid == "ws-1"

    def test_no_env_token_no_hardcoded_credential(self, monkeypatch):
        """BUG 1 RED->GREEN: never fall back to a hardcoded real token."""
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("ASANA_WORKSPACE_GID", raising=False)
        s = AsanaRealService()
        assert not s.access_token
        assert not s.workspace_gid


class TestMakeRequest:
    async def test_get_success(self):
        with _mock_session(_FakeResponse(200, {"data": [{"gid": "t-1"}]})):
            out = await AsanaRealService()._make_request(
                "GET", "tasks")
        assert out == {"data": [{"gid": "t-1"}]}

    async def test_post_success(self):
        with _mock_session(_FakeResponse(200, {"data": {"gid": "t-1"}})):
            out = await AsanaRealService()._make_request(
                "POST", "tasks", {"data": {"name": "x"}})
        assert out == {"data": {"gid": "t-1"}}

    async def test_put_success(self):
        with _mock_session(_FakeResponse(200, {"data": {"gid": "t-1"}})):
            out = await AsanaRealService()._make_request(
                "PUT", "tasks/t-1", {"data": {}})
        assert out == {"data": {"gid": "t-1"}}

    async def test_delete_success(self):
        with _mock_session(_FakeResponse(200, {})):
            out = await AsanaRealService()._make_request(
                "DELETE", "tasks/t-1")
        assert out == {"success": True}

    async def test_delete_failure(self):
        """BUG 2 RED->GREEN: DELETE must fail closed on non-2xx status."""
        with _mock_session(_FakeResponse(404, {})):
            out = await AsanaRealService()._make_request(
                "DELETE", "tasks/missing")
        assert out["success"] is False

    async def test_exception_returns_errors(self):
        class _BoomSession(_FakeSession):
            def get(self, *a, **k):
                raise RuntimeError("net down")

        with patch.object(
                ar.aiohttp, "ClientSession",
                MagicMock(return_value=_BoomSession([]))):
            out = await AsanaRealService()._make_request(
                "GET", "tasks")
        assert "errors" in out


class TestGetTasks:
    async def test_with_project(self, svc):
        with _mock_session(_FakeResponse(
                200, {"data": [_asana_task(), _asana_task(completed=True)]})):
            out = await svc.get_tasks(limit=50, project_gid="prj-1")
        assert len(out) == 2
        assert out[0]["title"] == "Task One"
        assert out[0]["status"] == "todo"
        assert out[1]["status"] == "completed"
        assert out[0]["dueDate"] == "2026-08-20T00:00:00Z"
        assert out[0]["tags"] == ["urgent"]
        assert out[0]["assignee"] == "Rushi"
        assert out[0]["platform"] == "asana"

    async def test_without_project(self, svc):
        with _mock_session(_FakeResponse(200, {"data": [_asana_task()]})):
            out = await svc.get_tasks()
        assert len(out) == 1

    async def test_no_data_returns_empty(self, svc):
        with _mock_session(_FakeResponse(200, {"errors": []})):
            out = await svc.get_tasks()
        assert out == []


class TestCreateTask:
    async def test_success(self, svc):
        with _mock_session(_FakeResponse(200, {"data": _asana_task()})):
            out = await svc.create_task({
                "title": "Task One", "description": "d",
                "dueDate": "2026-08-20T10:00:00", "project": "prj-1"})
        assert out["id"] == "t-1"
        assert out["title"] == "Task One"

    async def test_failure_returns_none(self, svc):
        with _mock_session(_FakeResponse(400, {"errors": []})):
            out = await svc.create_task({"title": "x"})
        assert out is None

    async def test_circuit_breaker_open_503(self, svc):
        with patch.object(ar.circuit_breaker, "is_enabled",
                          new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as ei:
                await svc.create_task({"title": "x"})
        assert ei.value.status_code == 503

    async def test_rate_limited_429(self, svc):
        with patch.object(ar.rate_limiter, "is_rate_limited",
                          new=AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException) as ei:
                await svc.create_task({"title": "x"})
        assert ei.value.status_code == 429

    async def test_exception_returns_none(self, svc):
        with patch.object(svc, "_make_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            out = await svc.create_task({"title": "x"})
        assert out is None


class TestUpdateTask:
    async def test_success_all_fields(self, svc):
        with _mock_session(_FakeResponse(200, {"data": _asana_task()})):
            out = await svc.update_task("t-1", {
                "title": "New", "description": "nd",
                "status": "completed", "dueDate": "2026-09-01T00:00:00"})
        assert out["title"] == "Task One"

    async def test_failure_returns_none(self, svc):
        with _mock_session(_FakeResponse(500, {"errors": []})):
            out = await svc.update_task("t-1", {"title": "New"})
        assert out is None

    async def test_circuit_breaker_open_503(self, svc):
        with patch.object(ar.circuit_breaker, "is_enabled",
                          new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as ei:
                await svc.update_task("t-1", {"title": "x"})
        assert ei.value.status_code == 503

    async def test_rate_limited_429(self, svc):
        with patch.object(ar.rate_limiter, "is_rate_limited",
                          new=AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException) as ei:
                await svc.update_task("t-1", {"title": "x"})
        assert ei.value.status_code == 429

    async def test_exception_returns_none(self, svc):
        with patch.object(svc, "_make_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            out = await svc.update_task("t-1", {"title": "x"})
        assert out is None


class TestDeleteTask:
    async def test_success(self, svc):
        with patch.object(svc, "_make_request",
                          new=AsyncMock(
                              return_value={"success": True})):
            assert await svc.delete_task("t-1") is True

    async def test_failure_returns_false(self, svc):
        with patch.object(svc, "_make_request",
                          new=AsyncMock(
                              return_value={"success": False})):
            assert await svc.delete_task("t-1") is False

    async def test_circuit_breaker_open_503(self, svc):
        with patch.object(ar.circuit_breaker, "is_enabled",
                          new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as ei:
                await svc.delete_task("t-1")
        assert ei.value.status_code == 503

    async def test_rate_limited_429(self, svc):
        with patch.object(ar.rate_limiter, "is_rate_limited",
                          new=AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException) as ei:
                await svc.delete_task("t-1")
        assert ei.value.status_code == 429

    async def test_exception_returns_false(self, svc):
        with patch.object(svc, "_make_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc.delete_task("t-1") is False


class TestGetProjects:
    async def test_success(self, svc):
        with _mock_session(_FakeResponse(
                200, {"data": [_asana_project(),
                               _asana_project(color="unknown")]})):
            out = await svc.get_projects(limit=25)
        assert len(out) == 2
        assert out[0]["color"] == "#D53F8C"
        assert out[1]["color"] == "#3182CE"
        assert out[0]["tasks"] == []
        assert out[0]["progress"] == 0

    async def test_no_data_returns_empty(self, svc):
        with _mock_session(_FakeResponse(200, {"errors": []})):
            out = await svc.get_projects()
        assert out == []

    async def test_circuit_breaker_open_503(self, svc):
        with patch.object(ar.circuit_breaker, "is_enabled",
                          new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as ei:
                await svc.get_projects()
        assert ei.value.status_code == 503

    async def test_rate_limited_429(self, svc):
        with patch.object(ar.rate_limiter, "is_rate_limited",
                          new=AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException) as ei:
                await svc.get_projects()
        assert ei.value.status_code == 429

    async def test_exception_returns_empty(self, svc):
        with patch.object(svc, "_make_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            out = await svc.get_projects()
        assert out == []


class TestCreateProject:
    async def test_success(self, svc):
        with _mock_session(_FakeResponse(200, {"data": _asana_project()})):
            out = await svc.create_project({
                "name": "Project One", "description": "d", "color": "red"})
        assert out["id"] == "p-1"
        assert out["name"] == "Project One"

    async def test_failure_returns_none(self, svc):
        with _mock_session(_FakeResponse(400, {"errors": []})):
            out = await svc.create_project({"name": "x"})
        assert out is None

    async def test_circuit_breaker_open_503(self, svc):
        with patch.object(ar.circuit_breaker, "is_enabled",
                          new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as ei:
                await svc.create_project({"name": "x"})
        assert ei.value.status_code == 503

    async def test_rate_limited_429(self, svc):
        with patch.object(ar.rate_limiter, "is_rate_limited",
                          new=AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException) as ei:
                await svc.create_project({"name": "x"})
        assert ei.value.status_code == 429

    async def test_exception_returns_none(self, svc):
        with patch.object(svc, "_make_request",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            out = await svc.create_project({"name": "x"})
        assert out is None


class TestConverters:
    def test_task_completed_no_optional_fields(self):
        out = AsanaRealService()._convert_asana_to_unified({
            "gid": "t-2", "name": "Done", "completed": True})
        assert out["status"] == "completed"
        assert out["tags"] == []
        assert out["assignee"] is None
        assert "T" in out["dueDate"]
        assert not out["dueDate"].endswith("Z")

    def test_project_default_color(self):
        out = AsanaRealService()._convert_asana_project_to_unified({
            "gid": "p-2", "name": "P"})
        assert out["color"] == "#3182CE"
