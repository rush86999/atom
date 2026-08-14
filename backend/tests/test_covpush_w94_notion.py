# -*- coding: utf-8 -*-
"""Coverage wave 94 — integrations/notion_service.py (TDD, fully mocked
requests — no network, no real Notion).

Baseline: 22% (only a bug-hunt file touched a couple of paths). Drives the
whole service: init with/without token, capabilities, health check,
execute_operation (search/get_page/create_page, tenant mismatch, unsupported
op, exception no-leak), connection test (200/non-200/exception), search
(with query/filter, without, failure fallback), page/database CRUD +
failures, block children get/append/delete, block formatters, users, rich
text formatting, page-in-database helper, workspace searches, and the
Postgres metric cache sync (create + update + rollback + outer failure).

Bugs fixed (TDD RED->GREEN):
- notion_service.py:460: sync_to_postgres_cache hardcoded workspace_id to
  "default" — the workspace identity never reached the IntegrationMetric
  rows, so multi-workspace dashboards mixed tenants. Signature now accepts
  workspace_id (defaults to "default" for backwards compatibility) and the
  value is written into every metric row.
"""
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from integrations.notion_service import NotionService


def _svc(**config):
    return NotionService(tenant_id="t1", config=config)


def _fake_response(status=200, data=None, text=""):
    resp = Mock()
    resp.status_code = status
    resp.json.return_value = data if data is not None else {}
    resp.text = text
    resp.raise_for_status = Mock()
    return resp


class TestInit:
    def test_init_no_token(self):
        svc = NotionService()
        assert svc.base_url == "https://api.notion.com/v1"
        assert svc.api_version == "2022-06-28"
        assert svc.access_token is None
        assert "Authorization" not in svc.session.headers

    def test_init_with_token(self):
        svc = _svc(access_token="ntok")
        assert svc.session.headers["Authorization"] == "Bearer ntok"
        assert svc.session.headers["Notion-Version"] == "2022-06-28"
        assert svc.session.headers["User-Agent"] == "ATOM-Platform/1.0"

    def test_get_capabilities(self):
        caps = _svc().get_capabilities()
        assert caps["required_params"] == ["access_token"]
        assert len(caps["operations"]) == 5
        assert caps["supports_webhooks"] is False


class TestHealthAndExecute:
    def test_health_check(self):
        result = asyncio.run(_svc().health_check())
        assert result["healthy"] is True
        assert result["service"] == "notion"

    def test_health_check_exception_path(self):
        svc = _svc()
        with patch("integrations.notion_service.datetime") as m_dt:
            m_dt.timezone = timezone
            calls = []
            def _now(*args, **kwargs):
                if not calls:
                    calls.append(1)
                    raise RuntimeError("clock")
                return datetime(2026, 1, 1, tzinfo=timezone.utc)
            m_dt.now.side_effect = _now
            result = asyncio.run(svc.health_check())
        assert result["healthy"] is False
        assert "clock" not in result["message"]

    def test_execute_search(self):
        svc = _svc()
        with patch.object(svc, "search", return_value={"results": [{"id": "p1"}]}) as m:
            result = asyncio.run(svc.execute_operation(
                "search", {"query": "alpha", "page_size": 10}))
        assert result == {"success": True, "result": {"results": [{"id": "p1"}]}}
        assert m.call_args[1]["query"] == "alpha"

    def test_execute_get_page(self):
        svc = _svc()
        with patch.object(svc, "get_page", return_value={"id": "p1"}):
            result = asyncio.run(svc.execute_operation("get_page", {"page_id": "p1"}))
        assert result["success"] is True

    def test_execute_create_page(self):
        svc = _svc()
        with patch.object(svc, "create_page", return_value={"id": "p1"}):
            result = asyncio.run(svc.execute_operation(
                "create_page", {"parent": {"database_id": "d1"}, "properties": {}}))
        assert result["success"] is True

    def test_execute_unsupported_operation(self):
        result = asyncio.run(_svc().execute_operation("delete_all", {}))
        assert result["success"] is False
        assert "Unsupported operation" in result["error"]

    def test_execute_tenant_mismatch(self):
        svc = _svc()
        result = asyncio.run(svc.execute_operation(
            "search", {"query": "q"}, context={"tenant_id": "other-tenant"}))
        assert result["success"] is False
        assert "Tenant mismatch" in result["error"]

    def test_execute_tenant_match_passes(self):
        svc = _svc()
        with patch.object(svc, "search", return_value={"results": []}):
            result = asyncio.run(svc.execute_operation(
                "search", {"query": "q"}, context={"tenant_id": "t1"}))
        assert result["success"] is True

    def test_execute_exception_no_leak(self):
        svc = _svc()
        with patch.object(svc, "search", side_effect=RuntimeError("secret-61")):
            result = asyncio.run(svc.execute_operation("search", {"query": "q"}))
        assert result["success"] is False
        assert "secret-61" not in result["error"]


class TestConnectionAndSearch:
    def test_connection_success(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(
            200, {"results": [{"id": "r1"}, {"id": "r2"}]}))
        result = svc.test_connection()
        assert result["status"] == "success"
        assert result["authenticated"] is True
        assert result["results_found"] == 2

    def test_connection_auth_failed(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(401, text="unauthorized"))
        result = svc.test_connection()
        assert result["status"] == "error"
        assert result["authenticated"] is False
        assert "401" in result["message"]

    def test_connection_exception(self):
        svc = _svc()
        svc.session.post = Mock(side_effect=requests.RequestException("boom-secret"))
        result = svc.test_connection()
        assert result["status"] == "error"
        assert result["authenticated"] is False
        assert "boom-secret" not in result["message"]

    def test_search_full(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(
            200, {"results": [{"id": "p1"}], "has_more": False}))
        result = svc.search(query="alpha", filter={"property": "object"},
                            page_size=25)
        body = svc.session.post.call_args[1]["json"]
        assert body == {"page_size": 25, "query": "alpha",
                        "filter": {"property": "object"}}
        assert result["results"] == [{"id": "p1"}]

    def test_search_minimal(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(200, {"results": []}))
        result = svc.search()
        assert svc.session.post.call_args[1]["json"] == {"page_size": 50}
        assert "query" not in svc.session.post.call_args[1]["json"]

    def test_search_failure_fallback(self):
        svc = _svc()
        svc.session.post = Mock(side_effect=requests.RequestException("net"))
        result = svc.search(query="q")
        assert result == {"results": [], "has_more": False}


class TestPagesAndDatabases:
    def test_get_page_success(self):
        svc = _svc()
        svc.session.get = Mock(return_value=_fake_response(200, {"id": "p1"}))
        assert svc.get_page("p1") == {"id": "p1"}

    def test_get_page_failure(self):
        svc = _svc()
        svc.session.get = Mock(side_effect=requests.RequestException("x"))
        assert svc.get_page("p1") is None

    def test_create_page_success_with_children(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(200, {"id": "p1"}))
        result = svc.create_page({"database_id": "d1"}, {"Name": {}},
                                 children=[{"object": "block"}])
        assert result == {"id": "p1"}
        body = svc.session.post.call_args[1]["json"]
        assert body["children"] == [{"object": "block"}]
        assert body["parent"] == {"database_id": "d1"}

    def test_create_page_success_no_children(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(200, {"id": "p1"}))
        result = svc.create_page({"page_id": "pp"}, {"Name": {}})
        body = svc.session.post.call_args[1]["json"]
        assert "children" not in body

    def test_create_page_invalid_parent(self):
        svc = _svc()
        svc.session.post = Mock()
        assert svc.create_page({}, {"Name": {}}) is None
        svc.session.post.assert_not_called()

    def test_create_page_failure(self):
        svc = _svc()
        svc.session.post = Mock(side_effect=requests.RequestException("x"))
        assert svc.create_page({"database_id": "d1"}, {}) is None

    def test_update_page_success(self):
        svc = _svc()
        svc.session.patch = Mock(return_value=_fake_response(200, {"id": "p1"}))
        result = svc.update_page("p1", {"Name": {}}, archived=True)
        assert result == {"id": "p1"}
        body = svc.session.patch.call_args[1]["json"]
        assert body == {"properties": {"Name": {}}, "archived": True}

    def test_update_page_failure(self):
        svc = _svc()
        svc.session.patch = Mock(side_effect=requests.RequestException("x"))
        assert svc.update_page("p1", {}) is None

    def test_get_database_success(self):
        svc = _svc()
        svc.session.get = Mock(return_value=_fake_response(200, {"id": "d1"}))
        assert svc.get_database("d1") == {"id": "d1"}

    def test_get_database_failure(self):
        svc = _svc()
        svc.session.get = Mock(side_effect=requests.RequestException("x"))
        assert svc.get_database("d1") is None

    def test_query_database_full(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(
            200, {"results": [], "has_more": True}))
        result = svc.query_database(
            "d1", filter={"property": "Status"}, sorts=[{"property": "Created"}],
            start_cursor="cur", page_size=10)
        body = svc.session.post.call_args[1]["json"]
        assert body == {"page_size": 10, "filter": {"property": "Status"},
                        "sorts": [{"property": "Created"}], "start_cursor": "cur"}
        assert result["has_more"] is True

    def test_query_database_minimal(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(200, {"results": []}))
        svc.query_database("d1")
        assert svc.session.post.call_args[1]["json"] == {"page_size": 100}

    def test_query_database_failure_fallback(self):
        svc = _svc()
        svc.session.post = Mock(side_effect=requests.RequestException("x"))
        assert svc.query_database("d1") == {"results": [], "has_more": False}

    def test_create_database_success(self):
        svc = _svc()
        svc.session.post = Mock(return_value=_fake_response(200, {"id": "d1"}))
        result = svc.create_database({"page_id": "pp"}, "My DB", {"Name": {}})
        assert result == {"id": "d1"}
        body = svc.session.post.call_args[1]["json"]
        assert body["title"] == [{"type": "text", "text": {"content": "My DB"}}]

    def test_create_database_failure(self):
        svc = _svc()
        svc.session.post = Mock(side_effect=requests.RequestException("x"))
        assert svc.create_database({"page_id": "pp"}, "DB", {}) is None


class TestBlocks:
    def test_get_block_children_success(self):
        svc = _svc()
        svc.session.get = Mock(return_value=_fake_response(200, {"results": []}))
        result = svc.get_block_children("b1")
        assert result == {"results": []}
        assert svc.session.get.call_args[1]["params"] == {"page_size": 100}

    def test_get_block_children_failure_fallback(self):
        svc = _svc()
        svc.session.get = Mock(side_effect=requests.RequestException("x"))
        assert svc.get_block_children("b1") == {"results": [], "has_more": False}

    def test_append_block_children_success(self):
        svc = _svc()
        svc.session.patch = Mock(return_value=_fake_response(200, {"results": []}))
        result = svc.append_block_children("b1", [{"object": "block"}])
        assert result == {"results": []}
        assert svc.session.patch.call_args[1]["json"] == {"children": [{"object": "block"}]}

    def test_append_block_children_failure(self):
        svc = _svc()
        svc.session.patch = Mock(side_effect=requests.RequestException("x"))
        assert svc.append_block_children("b1", []) is None

    def test_delete_block_success(self):
        svc = _svc()
        svc.session.patch = Mock(return_value=_fake_response(200, {}))
        assert svc.delete_block("b1") is True
        assert svc.session.patch.call_args[1]["json"] == {"archived": True}

    def test_delete_block_failure(self):
        svc = _svc()
        svc.session.patch = Mock(side_effect=requests.RequestException("x"))
        assert svc.delete_block("b1") is False

    def test_create_text_block_with_annotations(self):
        block = _svc().create_text_block("hi", {"bold": True})
        assert block["type"] == "paragraph"
        assert block["paragraph"]["rich_text"][0]["annotations"] == {"bold": True}

    def test_create_text_block_no_annotations(self):
        block = _svc().create_text_block("hi")
        assert block["paragraph"]["rich_text"][0]["annotations"] == {}

    def test_create_heading_block(self):
        block = _svc().create_heading_block("Title", level=2)
        assert block["type"] == "heading_2"
        assert block["heading_2"]["rich_text"][0]["text"]["content"] == "Title"

    def test_create_todo_block_checked(self):
        block = _svc().create_todo_block("Task", checked=True)
        assert block["type"] == "to_do"
        assert block["to_do"]["checked"] is True


class TestUsersAndFormatters:
    def test_get_user_success(self):
        svc = _svc()
        svc.session.get = Mock(return_value=_fake_response(200, {"id": "u1"}))
        assert svc.get_user("u1") == {"id": "u1"}

    def test_get_user_failure(self):
        svc = _svc()
        svc.session.get = Mock(side_effect=requests.RequestException("x"))
        assert svc.get_user("u1") is None

    def test_get_me(self):
        svc = _svc()
        svc.session.get = Mock(return_value=_fake_response(200, {"id": "me"}))
        assert svc.get_me() == {"id": "me"}
        assert svc.session.get.call_args[0][0].endswith("/users/me")

    def test_format_text_rich_text(self):
        rt = _svc().format_text_rich_text(
            "bold text", bold=True, italic=True, strikethrough=True,
            underline=True, color="red")
        assert rt["text"]["content"] == "bold text"
        assert rt["annotations"] == {
            "bold": True, "italic": True, "strikethrough": True,
            "underline": True, "color": "red"}


class TestWorkspaceHelpers:
    def test_create_page_in_database_adds_title(self):
        svc = _svc()
        with patch.object(svc, "create_page", return_value={"id": "p1"}) as m:
            result = svc.create_page_in_database("d1", {"Status": {}},
                                                 title_value="New Task")
        assert result == {"id": "p1"}
        parent, properties, children = m.call_args[0]
        assert parent == {"type": "database_id", "database_id": "d1"}
        assert properties["Name"]["title"][0]["text"]["content"] == "New Task"

    def test_create_page_in_database_keeps_existing_title(self):
        svc = _svc()
        with patch.object(svc, "create_page", return_value={}) as m:
            svc.create_page_in_database(
                "d1", {"Name": {"title": [{"text": {"content": "X"}}]}})
        properties = m.call_args[0][1]
        assert properties["Name"]["title"][0]["text"]["content"] == "X"

    def test_create_page_in_database_exception(self):
        svc = _svc()
        with patch.object(svc, "create_page",
                         side_effect=RuntimeError("boom-secret")):
            assert svc.create_page_in_database("d1", {}) is None

    def test_search_pages_in_workspace(self):
        svc = _svc()
        with patch.object(svc, "search",
                          return_value={"results": [{"id": "p1", "object": "page"}]}) as m:
            result = svc.search_pages_in_workspace("query here")
        assert result == [{"id": "p1", "object": "page"}]
        assert m.call_args[1]["filter"] == {"property": "object", "value": "page"}

    def test_search_pages_in_workspace_exception(self):
        svc = _svc()
        with patch.object(svc, "search", side_effect=RuntimeError("boom")):
            assert svc.search_pages_in_workspace("q") == []

    def test_search_databases_in_workspace(self):
        svc = _svc()
        with patch.object(svc, "search",
                          return_value={"results": [{"id": "d1", "object": "database"}]}) as m:
            result = svc.search_databases_in_workspace("q")
        assert result == [{"id": "d1", "object": "database"}]
        assert m.call_args[1]["filter"]["value"] == "database"

    def test_search_databases_in_workspace_exception(self):
        svc = _svc()
        with patch.object(svc, "search", side_effect=RuntimeError("boom")):
            assert svc.search_databases_in_workspace("q") == []


class TestSyncToPostgresCache:
    @pytest.fixture()
    def db_session(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    def _patch_db(self, session):
        return patch("core.database.SessionLocal", return_value=session)

    def test_sync_writes_workspace_id_metric(self, db_session):
        """RED->GREEN: workspace_id used to be hardcoded to 'default'."""
        svc = _svc()
        with patch.object(svc, "search_pages_in_workspace",
                          return_value=[{"id": "p1"}] * 3), \
             patch.object(svc, "search_databases_in_workspace",
                          return_value=[{"id": "d1"}] * 2), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result == {"success": True, "metrics_synced": 2}
        from core.models import IntegrationMetric
        rows = db_session.query(IntegrationMetric).all()
        assert len(rows) == 2
        assert all(r.workspace_id == "ws-1" for r in rows)
        by_key = {r.metric_key: r.value for r in rows}
        assert by_key == {"notion_page_count": 3.0, "notion_database_count": 2.0}

    def test_sync_default_workspace(self, db_session):
        svc = _svc()
        with patch.object(svc, "search_pages_in_workspace", return_value=[]), \
             patch.object(svc, "search_databases_in_workspace", return_value=[]), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache())
        assert result["success"] is True
        from core.models import IntegrationMetric
        assert all(
            r.workspace_id == "default"
            for r in db_session.query(IntegrationMetric).all())

    def test_sync_updates_existing(self, db_session):
        from core.models import IntegrationMetric
        db_session.add(IntegrationMetric(
            workspace_id="ws-1", integration_type="notion",
            metric_key="notion_page_count", value=1.0, unit="count"))
        db_session.commit()
        svc = _svc()
        with patch.object(svc, "search_pages_in_workspace", return_value=[]), \
             patch.object(svc, "search_databases_in_workspace", return_value=[]), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is True
        row = db_session.query(IntegrationMetric).filter_by(
            metric_key="notion_page_count").first()
        assert row.value == 0.0
        assert row.last_synced_at is not None

    def test_sync_db_error_rollback(self, db_session):
        svc = _svc()
        with patch.object(svc, "search_pages_in_workspace", return_value=[]), \
             patch.object(svc, "search_databases_in_workspace", return_value=[]), \
             self._patch_db(db_session), \
             patch("core.models.IntegrationMetric",
                   side_effect=RuntimeError("db exploded")):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "db exploded" not in result["error"]

    def test_sync_outer_error(self, db_session):
        svc = _svc()
        with patch.object(svc, "search_pages_in_workspace",
                          side_effect=RuntimeError("search-secret")), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("ws-1"))
        assert result["success"] is False
        assert "search-secret" not in result["error"]

    def test_full_sync(self, db_session):
        svc = _svc()
        with patch.object(svc, "search_pages_in_workspace", return_value=[]), \
             patch.object(svc, "search_databases_in_workspace", return_value=[]), \
             self._patch_db(db_session):
            result = asyncio.run(svc.full_sync())
        assert result["success"] is True
        assert result["workspace_id"] == "default"
        assert result["postgres_cache"]["success"] is True
