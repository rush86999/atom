# -*- coding: utf-8 -*-
"""Coverage wave 95 — integrations/linear_service (LinearService).

Standalone, fully mocked (IntegrationHTTP + httpx.Response objects + in-memory
SQLite for sync), zero network, zero LLM spend.

Covers: __init__ (config + env fallbacks, empty), close, _get_headers,
get_authorization_url (state/scope variants), exchange_token (success stores
token, HTTPError -> 400), _graphql_query (success with/without variables,
no-token 401, HTTPError -> 400), get_viewer, get_issues (with/without team_id
filter), get_teams, get_projects, create_issue (all optional params),
create_project (with/without description), get_capabilities, health_check
(success/exception), execute_operation (all 6 ops, unknown op, inner exception
-> generic envelope — NO str(e) leak), sync_to_postgres_cache (success with
REAL IntegrationMetric model — was failing on the phantom `tenant_id` column;
existing-row update path; inner rollback; outer failure; generic error messages
— no str(e) leaks), full_sync.

Bugs found (TDD RED -> GREEN):
- execute_operation error path leaked str(e) to callers
- sync_to_postgres_cache used phantom IntegrationMetric.tenant_id column
  (real: workspace_id) -> every sync failed; both except paths leaked str(e)
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import IntegrationMetric  # noqa: F401 (register model)
from integrations.linear_service import LinearService


_EMPTY = object()


def _svc(config=None):
    if config is _EMPTY:
        config = {}
    elif config is None:
        config = {"access_token": "tok"}
    svc = LinearService(tenant_id="t1", config=config)
    svc.http = MagicMock()
    return svc


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("POST", "http://x"))


def _gql(payload):
    r = httpx.Response(200, json={"data": payload},
                       request=httpx.Request("POST", "http://x"))
    return r


class TestInit:
    def test_config(self):
        svc = LinearService(config={"client_id": "cid", "client_secret": "cs",
                                    "access_token": "tok"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.access_token == "tok"
        assert svc.base_url == "https://api.linear.app"
        assert svc.graphql_url == "https://api.linear.app/graphql"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("LINEAR_CLIENT_ID", "env-cid")
        monkeypatch.setenv("LINEAR_CLIENT_SECRET", "env-cs")
        monkeypatch.setenv("LINEAR_ACCESS_TOKEN", "env-tok")
        svc = LinearService()
        assert svc.client_id == "env-cid"
        assert svc.client_secret == "env-cs"
        assert svc.access_token == "env-tok"

    def test_empty_config_no_env(self, monkeypatch):
        monkeypatch.delenv("LINEAR_CLIENT_ID", raising=False)
        monkeypatch.delenv("LINEAR_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("LINEAR_ACCESS_TOKEN", raising=False)
        svc = LinearService(config={})
        assert svc.client_id is None
        assert svc.access_token is None

    async def test_close(self):
        svc = LinearService()
        await svc.close()
        assert svc.client.is_closed


class TestHeaders:
    def test_get_headers(self):
        svc = _svc()
        h = svc._get_headers("abc")
        assert h["Authorization"] == "abc"
        assert h["Content-Type"] == "application/json"


class TestAuthUrl:
    def test_default_scope(self):
        svc = _svc()
        url = svc.get_authorization_url("http://cb")
        assert url.startswith("https://linear.app/oauth/authorize?")
        assert "scope=read,write" in url
        assert "state" not in url

    def test_custom_scope_and_state(self):
        svc = _svc()
        url = svc.get_authorization_url("http://cb", state="st", scope="read")
        assert "scope=read" in url
        assert "state=st" in url


class TestExchangeToken:
    async def test_success(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(200, {"access_token": "newtok"}))
        data = await svc.exchange_token("code1", "http://cb")
        assert data["access_token"] == "newtok"
        assert svc.access_token == "newtok"
        kwargs = svc.http.post.call_args.kwargs
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["data"]["client_id"] is None  # config empty

    async def test_http_error_400(self):
        svc = _svc()
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("c", "u")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"


class TestGraphqlQuery:
    async def test_without_variables(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({"viewer": {"id": "v1"}}))
        out = await svc._graphql_query("query { viewer { id } }")
        assert out == {"data": {"viewer": {"id": "v1"}}}
        payload = svc.http.post.call_args.kwargs["json"]
        assert payload == {"query": "query { viewer { id } }"}

    async def test_with_variables(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({}))
        await svc._graphql_query("q", {"first": 5})
        payload = svc.http.post.call_args.kwargs["json"]
        assert payload["variables"] == {"first": 5}

    async def test_no_token_401(self):
        svc = _svc(_EMPTY)
        with pytest.raises(HTTPException) as ei:
            await svc._graphql_query("q")
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc()
        svc.http.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "429", request=httpx.Request("POST", "u"), response=httpx.Response(429)))
        with pytest.raises(HTTPException) as ei:
            await svc._graphql_query("q")
        assert ei.value.status_code == 400


class TestGetters:
    async def test_get_viewer(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({"viewer": {"id": "v1", "name": "A"}}))
        out = await svc.get_viewer()
        assert out == {"id": "v1", "name": "A"}

    async def test_get_viewer_missing_data(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({}))
        assert await svc.get_viewer() == {}

    async def test_get_issues_no_filter(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({"issues": {"nodes": [{"id": "i1"}]}}))
        out = await svc.get_issues()
        assert out == [{"id": "i1"}]
        assert "filter" not in svc.http.post.call_args.kwargs["json"]["query"]

    async def test_get_issues_with_team_filter(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({"issues": {"nodes": []}}))
        await svc.get_issues(team_id="t-42", first=10)
        query = svc.http.post.call_args.kwargs["json"]["query"]
        assert 'team: { id: { eq: "t-42" } }' in query
        assert svc.http.post.call_args.kwargs["json"]["variables"] == {"first": 10}

    async def test_get_teams(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({"teams": {"nodes": [{"id": "t1"}]}}))
        out = await svc.get_teams(first=100)
        assert out == [{"id": "t1"}]
        assert "teams(first: 100)" in svc.http.post.call_args.kwargs["json"]["query"]

    async def test_get_projects(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({"projects": {"nodes": []}}))
        assert await svc.get_projects() == []

    async def test_get_issues_missing_nodes(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({}))
        assert await svc.get_issues() == []


class TestCreateIssue:
    async def test_full(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql(
            {"issueCreate": {"success": True, "issue": {"id": "i1"}}}))
        out = await svc.create_issue("Bug", "team1", description="d",
                                     priority=2, assignee_id="u1")
        assert out == {"success": True, "issue": {"id": "i1"}}
        variables = svc.http.post.call_args.kwargs["json"]["variables"]
        assert variables == {"title": "Bug", "teamId": "team1", "description": "d",
                             "priority": 2, "assigneeId": "u1"}

    async def test_minimal(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({}))
        await svc.create_issue("Bug", "team1")
        variables = svc.http.post.call_args.kwargs["json"]["variables"]
        assert variables == {"title": "Bug", "teamId": "team1"}


class TestCreateProject:
    async def test_with_description(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql(
            {"projectCreate": {"success": True}}))
        out = await svc.create_project("P", ["t1", "t2"], description="desc")
        assert out == {"success": True}
        variables = svc.http.post.call_args.kwargs["json"]["variables"]
        assert variables == {"name": "P", "teamIds": ["t1", "t2"],
                             "state": "planned", "description": "desc"}

    async def test_without_description(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_gql({}))
        await svc.create_project("P", ["t1"], state="started")
        variables = svc.http.post.call_args.kwargs["json"]["variables"]
        assert variables == {"name": "P", "teamIds": ["t1"], "state": "started"}
        assert "description" not in variables


class TestCapabilities:
    def test_operations(self):
        caps = _svc().get_capabilities()
        ops = {o["id"] for o in caps["operations"]}
        assert ops == {"get_issues", "create_issue", "get_teams", "get_projects",
                       "create_project", "get_viewer"}
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is True


class TestHealthCheck:
    async def test_healthy(self):
        out = await _svc().health_check()
        assert out["healthy"] is True
        assert out["message"] == "Linear service is healthy"
        assert "last_check" in out

    async def test_exception_path(self):
        svc = _svc()
        with patch("integrations.linear_service.datetime") as dt:
            dt.now.side_effect = RuntimeError("clock broke")
            out = await svc.health_check()
        assert out["healthy"] is False
        assert "clock broke" not in out["message"]


class TestExecuteOperation:
    async def test_get_issues_op(self):
        svc = _svc()
        svc.get_issues = AsyncMock(return_value=[{"id": "i1"}])
        out = await svc.execute_operation("get_issues", {"team_id": "t1", "first": 5})
        assert out == {"success": True, "result": [{"id": "i1"}]}
        svc.get_issues.assert_awaited_once_with(access_token=None, first=5, team_id="t1")

    async def test_create_issue_op(self):
        svc = _svc()
        svc.create_issue = AsyncMock(return_value={"issue": {"id": "i"}})
        out = await svc.execute_operation("create_issue",
                                          {"title": "t", "team_id": "tid"})
        assert out["success"] is True
        assert out["result"] == {"issue": {"id": "i"}}

    async def test_get_teams_op(self):
        svc = _svc()
        svc.get_teams = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_teams", {})
        assert out["success"] is True

    async def test_get_projects_op(self):
        svc = _svc()
        svc.get_projects = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_projects", {})
        assert out["success"] is True

    async def test_create_project_op(self):
        svc = _svc()
        svc.create_project = AsyncMock(return_value={"project": {}})
        out = await svc.execute_operation("create_project", {"name": "n", "team_ids": ["t"]})
        assert out["success"] is True
        svc.create_project.assert_awaited_once_with(
            name="n", team_ids=["t"], access_token=None,
            description=None, state="planned")

    async def test_get_viewer_op(self):
        svc = _svc()
        svc.get_viewer = AsyncMock(return_value={"id": "v"})
        out = await svc.execute_operation("get_viewer", {})
        assert out["success"] is True

    async def test_unknown_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unknown operation" in out["error"]

    async def test_error_envelope_no_str_e_leak(self):
        """RED: error path leaked str(e); must be a generic message."""
        svc = _svc()
        svc.get_issues = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_issues", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]

    async def test_error_envelope_inner_keyerror(self):
        svc = _svc()
        out = await svc.execute_operation("create_issue", {})  # missing title/team_id
        assert out["success"] is False
        assert "secret" not in out["error"]


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestSyncToPostgresCache:
    async def test_success_writes_metrics(self, db_session_factory):
        """RED: used phantom IntegrationMetric(tenant_id=...) -> TypeError ->
        every sync failed."""
        svc = _svc()
        svc.get_issues = AsyncMock(return_value=[{"id": "i1"}, {"id": "i2"}])
        svc.get_teams = AsyncMock(return_value=[{"id": "t1"}])
        svc.get_projects = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws-1")
        assert out["success"] is True
        assert out["metrics_synced"] == 3
        db = db_session_factory()
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 3
        keys = {r.metric_key for r in rows}
        assert keys == {"linear_issue_count", "linear_team_count", "linear_project_count"}
        assert all(r.workspace_id == "ws-1" for r in rows)
        assert rows[0].integration_type == "linear"
        assert rows[0].value == 2.0
        db.close()

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_issues = AsyncMock(return_value=[{"id": "i1"}])
        svc.get_teams = AsyncMock(return_value=[])
        svc.get_projects = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("ws-1")
            await svc.sync_to_postgres_cache("ws-1")
        db = db_session_factory()
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 3
        issue = db.query(IntegrationMetric).filter_by(metric_key="linear_issue_count").first()
        assert issue.value == 1.0
        assert issue.last_synced_at is not None
        db.close()

    async def test_inner_error_rollback_generic(self, db_session_factory):
        """RED: inner except leaked str(e); must be generic."""
        svc = _svc()
        svc.get_issues = AsyncMock(return_value=[{"id": "i1"}])
        svc.get_teams = AsyncMock(return_value=[])
        svc.get_projects = AsyncMock(return_value=[])
        db_cls = db_session_factory

        real = db_cls()

        class Boom:
            def __init__(self, *a, **k):
                pass

            def query(self, *a, **k):
                raise RuntimeError("db explode detail")

            def add(self, *a, **k):
                pass

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        with patch("core.database.SessionLocal", Boom):
            out = await svc.sync_to_postgres_cache("ws-1")
        assert out["success"] is False
        assert "db explode detail" not in out["error"]

    async def test_outer_error_generic(self, db_session_factory):
        """RED: outer except leaked str(e); must be generic."""
        svc = _svc()
        svc.get_issues = AsyncMock(side_effect=RuntimeError("gql secret"))
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws-1")
        assert out["success"] is False
        assert "gql secret" not in out["error"]


class TestFullSync:
    async def test_success(self, db_session_factory):
        svc = _svc()
        svc.get_issues = AsyncMock(return_value=[])
        svc.get_teams = AsyncMock(return_value=[])
        svc.get_projects = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.full_sync("ws-1")
        assert out["success"] is True
        assert out["workspace_id"] == "ws-1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out
