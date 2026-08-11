"""Coverage wave 33 — core/productivity/notion_service.py (TDD, mocked httpx/db).

Drives the Notion integration: API-key + OAuth token resolution (missing
key, expired token, decryption), the request pipeline (success, 429 rate
limit, 401/404/400/other error mapping, JSON error extraction, network
failure → 502), OAuth URL generation + code exchange (create/update
token paths), workspace search (page/database parent branches), database
listing/schema, query pagination, page get/blocks pagination, create/
update/append, and all property/block formatters — no network, zero spend.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.productivity.notion_service import (
    NotionService,
    create_page as module_create_page,
    get_database as module_get_database,
    query_database as module_query_database,
    update_page as module_update_page,
)


class _FakeResponse:
    def __init__(self, data=None, status=200, text="", headers=None):
        self._data = data
        self.status_code = status
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data

    def raise_for_status(self):
        pass


def make_service(user_id="u1", use_api_key=False):
    return NotionService(user_id, use_api_key=use_api_key)


class TestGetAccessToken:
    async def test_api_key_mode(self, monkeypatch):
        monkeypatch.setenv("NOTION_API_KEY", "secret-ntn")
        svc = make_service(use_api_key=True)
        assert await svc._get_access_token() == "secret-ntn"
        monkeypatch.delenv("NOTION_API_KEY")

    async def test_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        svc = make_service(use_api_key=True)
        with pytest.raises(Exception) as exc:
            await svc._get_access_token()
        assert exc.value.status_code == 401
        assert "NOTION_API_KEY" in exc.value.detail

    async def test_oauth_success(self):
        svc = make_service()
        token = SimpleNamespace(expires_at=None, access_token="encrypted")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = token
        with patch("core.productivity.notion_service.get_db_session") as gdb, \
             patch("core.productivity.notion_service.decrypt_token",
                   return_value="plain") as dt:
            gdb.return_value.__enter__.return_value = db
            assert await svc._get_access_token() == "plain"
        dt.assert_called_once()

    async def test_oauth_missing_token(self):
        svc = make_service()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.productivity.notion_service.get_db_session") as gdb:
            gdb.return_value.__enter__.return_value = db
            with pytest.raises(Exception) as exc:
                await svc._get_access_token()
        assert exc.value.status_code == 401
        assert "authorize" in exc.value.detail

    async def test_oauth_expired_token(self):
        svc = make_service()
        token = SimpleNamespace(
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            access_token="x")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = token
        with patch("core.productivity.notion_service.get_db_session") as gdb:
            gdb.return_value.__enter__.return_value = db
            with pytest.raises(Exception) as exc:
                await svc._get_access_token()
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail


class TestMakeRequest:
    def _client(self, response):
        client = MagicMock()
        client.request = AsyncMock(return_value=response)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        return client

    async def test_success(self):
        svc = make_service()
        svc.access_token = "tok"
        client = self._client(_FakeResponse({"ok": True}))
        with patch("core.productivity.notion_service.httpx.AsyncClient",
                   return_value=client):
            result = await svc._make_request("GET", "/test")
        assert result == {"ok": True}
        req_kwargs = client.request.call_args.kwargs
        assert req_kwargs["headers"]["Authorization"] == "Bearer tok"

    async def test_rate_limited(self):
        svc = make_service()
        svc.access_token = "tok"
        client = self._client(_FakeResponse(
            status=429, headers={"Retry-After": "3"}))
        with patch("core.productivity.notion_service.httpx.AsyncClient",
                   return_value=client):
            with pytest.raises(Exception) as exc:
                await svc._make_request("GET", "/test")
        assert exc.value.status_code == 429
        assert exc.value.headers["Retry-After"] == "3"

    @pytest.mark.parametrize("status,detail_frag", [
        (401, "Invalid Notion token"),
        (404, "not found"),
        (400, "Invalid request"),
        (500, "Internal error"),
    ])
    async def test_error_mapping(self, status, detail_frag):
        svc = make_service()
        svc.access_token = "tok"
        client = self._client(_FakeResponse(status=status, text="err body"))
        with patch("core.productivity.notion_service.httpx.AsyncClient",
                   return_value=client):
            with pytest.raises(Exception) as exc:
                await svc._make_request("GET", "/test")
        assert exc.value.status_code == status
        assert detail_frag in exc.value.detail

    async def test_error_json_message_extracted(self):
        svc = make_service()
        svc.access_token = "tok"
        client = self._client(_FakeResponse(
            status=400, data={"message": "Real message"}))
        with patch("core.productivity.notion_service.httpx.AsyncClient",
                   return_value=client):
            with pytest.raises(Exception) as exc:
                await svc._make_request("GET", "/test")
        assert "Real message" in exc.value.detail

    async def test_network_failure(self):
        svc = make_service()
        svc.access_token = "tok"
        client = self._client(None)
        client.request = AsyncMock(side_effect=httpx.ConnectError("down"))
        with patch("core.productivity.notion_service.httpx.AsyncClient",
                   return_value=client):
            with pytest.raises(Exception) as exc:
                await svc._make_request("GET", "/test")
        assert exc.value.status_code == 502

    async def test_lazy_token_resolution(self):
        svc = make_service()
        client = self._client(_FakeResponse({"ok": True}))
        with patch.object(svc, "_get_access_token",
                          new=AsyncMock(return_value="resolved")) as gat, \
             patch("core.productivity.notion_service.httpx.AsyncClient",
                   return_value=client):
            await svc._make_request("GET", "/test")
        gat.assert_called_once()


class TestOAuth:
    async def test_get_authorization_url_with_state(self):
        handler = MagicMock()
        handler.get_authorization_url.return_value = "https://auth?state=s1"
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        with patch.object(NotionService, "get_oauth_handler",
                          return_value=handler), \
             patch("core.productivity.notion_service.get_db_session") as gdb, \
             patch("core.models.OAuthState",
                   lambda **kw: SimpleNamespace(**kw)):
            gdb.return_value.__enter__.return_value = db
            url = await NotionService.get_authorization_url("u1", state="s1")
        assert url == "https://auth?state=s1"
        handler.get_authorization_url.assert_called_once_with(state="s1")

    async def test_get_authorization_url_generates_state(self):
        handler = MagicMock()
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        with patch.object(NotionService, "get_oauth_handler",
                          return_value=handler), \
             patch("core.productivity.notion_service.get_db_session") as gdb, \
             patch("core.models.OAuthState",
                   lambda **kw: SimpleNamespace(**kw)):
            gdb.return_value.__enter__.return_value = db
            await NotionService.get_authorization_url("u1")
        assert handler.get_authorization_url.call_args.kwargs["state"]

    async def test_exchange_code_new_token(self):
        handler = MagicMock()
        handler.exchange_code_for_tokens = AsyncMock(return_value={
            "access_token": "ntn-tok", "workspace_id": "ws-1",
            "workspace_name": "Acme", "workspace_icon": "icon",
            "bot_id": "bot-1", "owner": {"type": "workspace"}})
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = SimpleNamespace(tenant_id="t-1")
        db.query.return_value.filter.return_value.first.side_effect = [user, None]
        with patch.object(NotionService, "get_oauth_handler",
                          return_value=handler), \
             patch("core.productivity.notion_service.get_db_session") as gdb, \
             patch("core.productivity.notion_service.encrypt_token",
                   return_value="enc") as et, \
             patch("core.productivity.notion_service.IntegrationToken",
                   MagicMock(return_value=SimpleNamespace(**{}))):
            gdb.return_value.__enter__.return_value = db
            result = await NotionService.exchange_code_for_tokens("code", "u1")
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
        et.assert_called_once_with("ntn-tok")
        db.add.assert_called_once()

    async def test_exchange_code_updates_existing(self):
        handler = MagicMock()
        handler.exchange_code_for_tokens = AsyncMock(return_value={
            "access_token": "ntn-tok", "workspace_id": "ws-2"})
        db = MagicMock()
        db.commit = MagicMock()
        user = SimpleNamespace(tenant_id=None)
        existing = SimpleNamespace()
        db.query.return_value.filter.return_value.first.side_effect = [user, existing]
        with patch.object(NotionService, "get_oauth_handler",
                          return_value=handler), \
             patch("core.productivity.notion_service.get_db_session") as gdb, \
             patch("core.productivity.notion_service.encrypt_token",
                   return_value="enc"):
            gdb.return_value.__enter__.return_value = db
            result = await NotionService.exchange_code_for_tokens("code", "u1")
        assert result["success"] is True
        assert existing.access_token == "enc"
        assert existing.status == "active"
        assert existing.workspace_id == "ws-2"


class TestWorkspaceMethods:
    async def test_search_workspace_page_and_database(self):
        svc = make_service()
        svc._make_request = AsyncMock(return_value={"results": [
            {"id": "p1", "object": "page", "url": "u1",
             "properties": {"title": {"type": "title",
                                      "title": [{"plain_text": "Page One"}]}},
             "parent": {"type": "database_id", "database_id": "db-1"}},
            {"id": "p2", "object": "page", "url": "u2",
             "properties": {"title": {"type": "title", "title": []}},
             "parent": {"type": "workspace"}},
            {"id": "d1", "object": "database", "url": "u3",
             "title": [{"plain_text": "DB One"}]},
        ]})
        results = await svc.search_workspace("query")
        assert results[0]["title"] == "Page One"
        assert results[0]["parent_id"] == "db-1"
        assert results[1]["title"] == "Untitled"
        assert results[1]["parent_id"] == "workspace"
        assert results[2]["title"] == "DB One"

    async def test_list_databases(self):
        svc = make_service()
        svc._make_request = AsyncMock(return_value={"results": [
            {"id": "d1", "title": [{"plain_text": "Tasks"}],
             "description": [{"plain_text": "All tasks"}], "url": "u"},
            {"id": "d2", "title": [], "description": []},
        ]})
        dbs = await svc.list_databases()
        assert dbs[0]["title"] == "Tasks"
        assert dbs[0]["description"] == "All tasks"
        assert dbs[1]["title"] == "Untitled"


class TestDatabaseMethods:
    async def test_query_database_with_pagination(self):
        svc = make_service()
        svc._make_request = AsyncMock(side_effect=[
            {"results": [{"id": "pg1", "created_time": "t", "properties": {}}],
             "has_more": True, "next_cursor": "cur-2"},
            {"results": [{"id": "pg2", "created_time": "t", "properties": {}}],
             "has_more": False},
        ])
        pages = await svc.query_database("db-1", filter={"property": "x"})
        assert [p["id"] for p in pages] == ["pg1", "pg2"]
        assert svc._make_request.call_count == 2

    async def test_get_database_schema(self):
        svc = make_service()
        svc._make_request = AsyncMock(return_value={
            "id": "db-1", "title": [{"plain_text": "Schema DB"}],
            "description": [{"plain_text": "desc"}],
            "url": "u",
            "properties": {"Name": {"type": "title", "id": "p1"},
                           "Amount": {"type": "number", "id": "p2"}}})
        schema = await svc.get_database_schema("db-1")
        assert schema["title"] == "Schema DB"
        assert schema["properties"]["Name"]["type"] == "title"


class TestPageMethods:
    async def test_get_page_with_blocks(self):
        svc = make_service()
        svc._make_request = AsyncMock(side_effect=[
            {"id": "pg1", "created_time": "t", "properties": {}},
            {"results": [{"id": "b1", "type": "paragraph",
                          "paragraph": {"rich_text": [{"plain_text": "hello"}]}}],
             "has_more": False},
        ])
        page = await svc.get_page("pg1")
        assert page["id"] == "pg1"
        assert page["blocks"][0]["text"] == "hello"

    async def test_get_page_blocks_pagination(self):
        svc = make_service()
        svc._make_request = AsyncMock(side_effect=[
            {"results": [{"id": "b1", "type": "divider"}],
             "has_more": True, "next_cursor": "c2"},
            {"results": [{"id": "b2", "type": "divider"}],
             "has_more": False},
        ])
        blocks = await svc.get_page_blocks("pg1")
        assert [b["id"] for b in blocks] == ["b1", "b2"]
        assert svc._make_request.call_count == 2

    async def test_create_update_append(self):
        svc = make_service()
        svc._make_request = AsyncMock(return_value={
            "id": "pg1", "created_time": "t",
            "properties": {"Name": {"type": "title",
                                    "title": [{"plain_text": "New"}]}}})
        page = await svc.create_page("db-1", {"Name": {"title": [{"text": {"content": "New"}}]}})
        assert page["id"] == "pg1"
        updated = await svc.update_page("pg1", {"Name": {}})
        assert updated["id"] == "pg1"

        svc._make_request = AsyncMock(return_value={
            "results": [{"id": "b1", "type": "to_do",
                         "to_do": {"rich_text": [{"plain_text": "x"}],
                                   "checked": True}}]})
        result = await svc.append_page_blocks("pg1", [{"object": "block"}])
        assert result["success"] is True
        assert result["blocks"][0]["checked"] is True


class TestFormatters:
    def test_format_page_properties_all_types(self):
        svc = make_service()
        page = {
            "id": "pg1", "created_time": "t", "last_edited_time": "t2",
            "archived": False, "url": "u",
            "properties": {
                "t": {"type": "title", "title": [{"plain_text": "T"}]},
                "r": {"type": "rich_text", "rich_text": [{"plain_text": "R"}]},
                "n": {"type": "number", "number": 42},
                "s": {"type": "select", "select": {"name": "S"}},
                "s2": {"type": "select", "select": None},
                "m": {"type": "multi_select",
                      "multi_select": [{"name": "A"}, {"name": "B"}]},
                "d": {"type": "date", "date": {"start": "2026-01-01"}},
                "d2": {"type": "date", "date": None},
                "c": {"type": "checkbox", "checkbox": True},
                "u": {"type": "url", "url": "https://x"},
                "e": {"type": "email", "email": "a@b.c"},
                "p": {"type": "phone", "phone": "555"},
                "f1": {"type": "formula",
                       "formula": {"type": "string", "string": "formula!"}},
                "f2": {"type": "formula",
                       "formula": {"type": "number", "number": 7}},
                "rel": {"type": "relation",
                        "relation": [{"id": "r1"}, {"id": "r2"}]},
                "roll": {"type": "rollup",
                         "rollup": {"type": "number", "number": 3}},
                "other": {"type": "unknown_type", "foo": "bar"},
                "empty_title": {"type": "title", "title": []},
            },
        }
        props = svc._format_page_properties(page)["properties"]
        assert props["t"] == "T"
        assert props["r"] == "R"
        assert props["n"] == 42
        assert props["s"] == "S"
        assert props["s2"] is None
        assert props["m"] == ["A", "B"]
        assert props["d"] == "2026-01-01"
        assert props["d2"] is None
        assert props["c"] is True
        assert props["u"] == "https://x"
        assert props["e"] == "a@b.c"
        assert props["p"] == "555"
        assert props["f1"] == "formula!"
        assert props["f2"] == 7
        assert props["rel"] == ["r1", "r2"]
        assert props["roll"] == 3
        assert "unknown_type" in str(props["other"])
        assert props["empty_title"] == ""

    def test_format_block_all_types(self):
        svc = make_service()
        cases = [
            ("paragraph", {"paragraph": {"rich_text": [{"plain_text": "p"}]}}),
            ("heading_1", {"heading_1": {"rich_text": [{"plain_text": "h"}]}}),
            ("heading_2", {"heading_2": {"rich_text": []}}),
            ("heading_3", {"heading_3": {"rich_text": []}}),
            ("bulleted_list_item", {"bulleted_list_item": {"rich_text": [{"plain_text": "b"}]}}),
            ("numbered_list_item", {"numbered_list_item": {"rich_text": [], "number": 3}}),
            ("to_do", {"to_do": {"rich_text": [{"plain_text": "t"}], "checked": True}}),
            ("code", {"code": {"rich_text": [{"plain_text": "c"}], "language": "py"}}),
            ("quote", {"quote": {"rich_text": [{"plain_text": "q"}]}}),
            ("callout", {"callout": {"rich_text": [{"plain_text": "co"}],
                                     "icon": {"emoji": "🔥"}}}),
            ("divider", {}),
            ("mystery", {}),
        ]
        for i, (btype, data) in enumerate(cases):
            block = {"id": f"b{i}", "type": btype, "has_children": False, **data}
            fmt = svc._format_block(block)
            assert fmt["type"] == btype
        assert svc._format_block(cases[0][1] and {
            "id": "x", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [], "number": 5}})["number"] == 5

    def test_extract_rich_text(self):
        svc = make_service()
        assert svc._extract_rich_text([
            {"plain_text": "Hello "}, {"plain_text": "World"}]) == "Hello World"
        assert svc._extract_rich_text([]) == ""
        assert svc._extract_rich_text([{"no_text": True}]) == ""


class TestModuleHelpers:
    async def test_helpers(self):
        with patch.object(NotionService, "get_database_schema",
                          new=AsyncMock(return_value={"id": "d1"})), \
             patch.object(NotionService, "query_database",
                          new=AsyncMock(return_value=[])), \
             patch.object(NotionService, "create_page",
                          new=AsyncMock(return_value={"id": "p1"})), \
             patch.object(NotionService, "update_page",
                          new=AsyncMock(return_value={"id": "p1"})):
            assert (await module_get_database("u1", "d1")) == {"id": "d1"}
            assert await module_query_database("u1", "d1") == []
            assert (await module_create_page("u1", "d1", {})) == {"id": "p1"}
            assert (await module_update_page("u1", "p1", {})) == {"id": "p1"}
