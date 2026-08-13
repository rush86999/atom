# -*- coding: utf-8 -*-
"""Coverage wave W71a — 5 backend modules (standalone >=95% each).

Targets:
1. integrations/adapters/notion_adapter.py      (43% baseline)
2. integrations/adapters/line_adapter.py        (22% baseline)
3. integrations/adapters/signal_adapter.py      (0% baseline — never imported)
4. integrations/adapters/asana_adapter.py       (44% baseline)
5. integrations/bridge/external_integration_routes.py (0% baseline)

Pattern: pure unit tests, mocked deps, ZERO LLM spend, no network (httpx
mocked via `patch("...httpx.AsyncClient")`), no DB. All async methods driven
via asyncio.run from sync tests (matching test_covpush_w69b/w70a style).
Routes exercised via FastAPI TestClient with the router mounted on a fresh
app (no auth deps on these routes — see notes below).

Bugs found + fixed in the assigned modules (regression tests below):
1. notion_adapter.py:81-83 — `asyncio.to_thread(self.service.query_database,
   database_id, **parameters)` re-passed `database_id` as a keyword
   (parameters always contains it), so every query_database call raised
   `TypeError: multiple values for argument 'database_id'` and the success
   branch was dead code. Fix: strip already-bound keys from **parameters.
   Regression: test_query_database_success_with_database_id_param.
2. notion_adapter.py:91-93 — same defect for `search`: parameters containing
   `query` collided with the explicit `query=query` keyword. Fix: strip
   `query` from **parameters. Regression:
   test_search_success_with_query_in_parameters.
3. external_integration_routes.py:37-38 — the 400 HTTPException for missing
   pieceName/actionName was raised INSIDE the try whose `except Exception`
   swallows it, so callers always got a 500 instead of the intended 400.
   Fix: `except HTTPException: raise` before the generic handler.
   Regression: test_execute_missing_fields_400.

Notes / N/A:
- external_integration_routes.py routes carry NO auth dependency (mounted
  raw in main_api_app.py:2670), so 401/403 paths are not applicable.
- line/signal adapter `except ImportError: HTTPX_AVAILABLE = False` module
  blocks are unreachable while httpx is installed (both branches still
  exercised via runtime patching of the flag).
- signal_adapter.verify_webhook's `except Exception` (lines 221-223) is
  genuinely unreachable — the try body only builds a dict and can't raise.
"""
import asyncio
import base64
import hashlib
import hmac
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

LINE_TOKEN = "line-token-123"
LINE_SECRET = "line-secret-456"


def _resp(json_data=None, raise_error=False):
    resp = MagicMock()
    if json_data is not None:
        resp.json.return_value = json_data
    if raise_error:
        resp.raise_for_status.side_effect = RuntimeError("HTTP 400")
    else:
        resp.raise_for_status.return_value = None
    return resp


def _http_client(post_return=None, get_return=None, post_side_effect=None, get_side_effect=None):
    client = AsyncMock()
    if post_return is not None:
        client.post = AsyncMock(return_value=post_return)
    if post_side_effect is not None:
        client.post = AsyncMock(side_effect=post_side_effect)
    if get_return is not None:
        client.get = AsyncMock(return_value=get_return)
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    return client


def _line_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


# ===========================================================================
# integrations/adapters/notion_adapter.py
# ===========================================================================

class TestNotionAdapter:
    def _adapter(self, **kwargs):
        from integrations.adapters.notion_adapter import NotionAdapter
        adapter = NotionAdapter(tenant_id="t1", config={"access_token": "tok"}, **kwargs)
        adapter.service = MagicMock()
        return adapter

    def test_init_defaults(self):
        from integrations.adapters.notion_adapter import NotionAdapter
        adapter = NotionAdapter()
        assert adapter.tenant_id == "default"
        assert adapter.config == {}
        assert adapter.workspace_id == "default"
        assert adapter.service is not None

    def test_init_with_tenant_and_config(self):
        from integrations.adapters.notion_adapter import NotionAdapter
        adapter = NotionAdapter(tenant_id="t9", config={"access_token": "tok"})
        assert adapter.tenant_id == "t9"
        assert adapter.workspace_id == "t9"

    def test_get_capabilities(self):
        adapter = self._adapter()
        caps = adapter.get_capabilities()
        assert caps["operations"] == adapter.get_supported_operations()
        assert caps["required_params"] == ["access_token"]
        assert caps["optional_params"] == []
        assert caps["rate_limits"] == {}
        assert caps["supports_webhooks"] is False

    def test_health_check(self):
        adapter = self._adapter()
        assert adapter.health_check()["healthy"] is True

    def test_get_supported_operations(self):
        adapter = self._adapter()
        assert adapter.get_supported_operations() == [
            "create_page", "query_database", "search", "update_page", "get_page",
        ]

    def test_create_page_missing_parent(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.execute_operation("create_page", {"properties": {}}))
        assert result.success is False
        assert result.error.value == "INVALID_PARAMETERS"
        assert "parent" in result.message

    def test_create_page_missing_properties(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.execute_operation("create_page", {"parent": {"page_id": "p"}}))
        assert result.success is False
        assert result.error.value == "INVALID_PARAMETERS"

    def test_create_page_success(self):
        adapter = self._adapter()
        adapter.service.create_page.return_value = {"id": "page-1"}
        result = asyncio.run(adapter.execute_operation(
            "create_page", {"parent": {"page_id": "p"}, "properties": {"t": {"title": []}}, "children": []}))
        assert result.success is True
        assert result.data == {"id": "page-1"}
        adapter.service.create_page.assert_called_once_with(
            {"page_id": "p"}, {"t": {"title": []}}, [])

    def test_create_page_none_result_api_error(self):
        adapter = self._adapter()
        adapter.service.create_page.return_value = None
        result = asyncio.run(adapter.execute_operation(
            "create_page", {"parent": {"page_id": "p"}, "properties": {"title": {}}}))
        assert result.success is False
        assert result.error.value == "API_ERROR"
        assert result.data is None

    def test_query_database_missing_database_id(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.execute_operation("query_database", {}))
        assert result.success is False
        assert result.error.value == "INVALID_PARAMETERS"

    def test_query_database_success_with_database_id_param(self):
        """Regression: database_id keyword collision broke the success path."""
        from integrations.adapters.notion_adapter import NotionAdapter
        adapter = NotionAdapter(tenant_id="t1", config={"access_token": "x"})
        adapter.service.session = MagicMock()
        adapter.service.session.post.return_value.raise_for_status.return_value = None
        adapter.service.session.post.return_value.json.return_value = {
            "results": [{"id": "p1"}], "has_more": True,
        }
        result = asyncio.run(adapter.execute_operation(
            "query_database", {"database_id": "db1", "page_size": 10}))
        assert result.success is True
        assert result.data == {"results": [{"id": "p1"}], "has_more": True}
        _, kwargs = adapter.service.session.post.call_args
        assert kwargs["json"]["page_size"] == 10

    def test_query_database_success_with_filter(self):
        adapter = self._adapter()
        adapter.service.query_database.return_value = {"results": [], "has_more": False}
        result = asyncio.run(adapter.execute_operation(
            "query_database", {"database_id": "db1", "filter": {"property": "x"}}))
        assert result.success is True
        assert result.data == {"results": [], "has_more": False}

    def test_search_success_with_query_in_parameters(self):
        """Regression: query keyword collision broke the success path."""
        from integrations.adapters.notion_adapter import NotionAdapter
        adapter = NotionAdapter(tenant_id="t1", config={"access_token": "x"})
        adapter.service.session = MagicMock()
        adapter.service.session.post.return_value.raise_for_status.return_value = None
        adapter.service.session.post.return_value.json.return_value = {
            "results": [{"id": "p9"}], "has_more": False,
        }
        result = asyncio.run(adapter.execute_operation("search", {"query": "hello", "page_size": 5}))
        assert result.success is True
        assert result.data == {"results": [{"id": "p9"}], "has_more": False}
        _, kwargs = adapter.service.session.post.call_args
        assert kwargs["json"]["query"] == "hello"
        assert kwargs["json"]["page_size"] == 5

    def test_search_success_without_query_key(self):
        adapter = self._adapter()
        adapter.service.search.return_value = {"results": [{"id": "s1"}], "has_more": True}
        result = asyncio.run(adapter.execute_operation("search", {"page_size": 3}))
        assert result.success is True
        assert result.data == {"results": [{"id": "s1"}], "has_more": True}

    def test_unknown_operation(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.execute_operation("explode", {}))
        assert result.success is False
        assert result.error.value == "NOT_FOUND"
        assert "explode" in result.message

    def test_service_exception_maps_to_execution_exception(self):
        adapter = self._adapter()
        adapter.service.create_page.side_effect = RuntimeError("boom")
        result = asyncio.run(adapter.execute_operation(
            "create_page", {"parent": {"page_id": "p"}, "properties": {"title": {}}}))
        assert result.success is False
        assert result.error.value == "EXECUTION_EXCEPTION"
        assert result.message == "boom"

    def test_access_token_in_parameters_reinitializes_service(self):
        from integrations.adapters import notion_adapter as mod
        adapter = self._adapter()
        new_service = MagicMock()
        new_service.create_page.return_value = {"id": "new"}
        with patch.object(mod, "NotionService", return_value=new_service) as ns:
            result = asyncio.run(adapter.execute_operation(
                "create_page",
                {"access_token": "tok2", "parent": {"page_id": "p"}, "properties": {"title": {}}},
            ))
        ns.assert_called_once_with(tenant_id="t1", config={"access_token": "tok2"})
        assert result.success is True
        assert adapter.service is new_service


# ===========================================================================
# integrations/adapters/asana_adapter.py
# ===========================================================================

class TestAsanaAdapter:
    def _adapter(self, config=None):
        from integrations.adapters.asana_adapter import AsanaAdapter
        cfg = config if config is not None else {"access_token": "tok"}
        adapter = AsanaAdapter(tenant_id="t1", config=cfg)
        return adapter

    def test_init_defaults(self):
        from integrations.adapters.asana_adapter import AsanaAdapter
        adapter = AsanaAdapter()
        assert adapter.tenant_id == "default"
        assert adapter.workspace_id == "default"
        assert adapter.service is not None

    def test_init_with_tenant_and_config(self):
        from integrations.adapters.asana_adapter import AsanaAdapter
        adapter = AsanaAdapter(tenant_id="t2", config={"access_token": "x"})
        assert adapter.tenant_id == "t2"
        assert adapter.workspace_id == "t2"

    def test_get_capabilities(self):
        adapter = self._adapter()
        caps = adapter.get_capabilities()
        assert caps["operations"] == adapter.get_supported_operations()
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is False

    def test_health_check(self):
        adapter = self._adapter()
        assert adapter.health_check()["healthy"] is True

    def test_get_supported_operations(self):
        adapter = self._adapter()
        assert adapter.get_supported_operations() == [
            "create_task", "get_tasks", "get_projects", "create_project",
        ]

    def test_missing_access_token_auth_expired(self):
        adapter = self._adapter(config={})
        result = asyncio.run(adapter.execute_operation("create_task", {"task_data": {}}))
        assert result.success is False
        assert result.error.value == "AUTH_EXPIRED"
        assert "Missing access token" in result.message

    def test_token_from_parameters(self):
        adapter = self._adapter(config={})
        adapter.service.create_task = AsyncMock(return_value={"ok": True, "task": {"gid": "1"}})
        result = asyncio.run(adapter.execute_operation(
            "create_task", {"access_token": "param-tok", "task_data": {"name": "t"}}))
        adapter.service.create_task.assert_called_once_with("param-tok", {"name": "t"})
        assert result.success is True

    def test_create_task_missing_task_data(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.execute_operation("create_task", {}))
        assert result.success is False
        assert result.error.value == "INVALID_PARAMETERS"

    def test_create_task_success(self):
        adapter = self._adapter()
        adapter.service.create_task = AsyncMock(return_value={"ok": True, "task": {"gid": "t1"}})
        result = asyncio.run(adapter.execute_operation(
            "create_task", {"task_data": {"name": "Task"}}))
        assert result.success is True
        assert result.data == {"gid": "t1"}
        assert result.error is None

    def test_create_task_api_error(self):
        adapter = self._adapter()
        adapter.service.create_task = AsyncMock(return_value={"ok": False, "error": "denied"})
        result = asyncio.run(adapter.execute_operation("create_task", {"task_data": {"name": "t"}}))
        assert result.success is False
        assert result.error.value == "API_ERROR"
        assert result.message == "denied"

    def test_get_tasks_success(self):
        adapter = self._adapter()
        adapter.service.get_tasks = AsyncMock(return_value={"ok": True, "tasks": [{"gid": "a"}]})
        result = asyncio.run(adapter.execute_operation("get_tasks", {"project_gid": "prj"}))
        adapter.service.get_tasks.assert_called_once_with("tok", project_gid="prj")
        assert result.success is True
        assert result.data == {"tasks": [{"gid": "a"}]}

    def test_get_tasks_api_error(self):
        adapter = self._adapter()
        adapter.service.get_tasks = AsyncMock(return_value={"ok": False, "error": "nope"})
        result = asyncio.run(adapter.execute_operation("get_tasks", {}))
        assert result.success is False
        assert result.error.value == "API_ERROR"
        assert result.message == "nope"

    def test_get_projects_success(self):
        adapter = self._adapter()
        adapter.service.get_projects = AsyncMock(return_value={"ok": True, "projects": [{"gid": "p1"}]})
        result = asyncio.run(adapter.execute_operation("get_projects", {"workspace_gid": "ws"}))
        adapter.service.get_projects.assert_called_once_with("tok", workspace_gid="ws")
        assert result.success is True
        assert result.data == {"projects": [{"gid": "p1"}]}

    def test_get_projects_api_error(self):
        adapter = self._adapter()
        adapter.service.get_projects = AsyncMock(return_value={"ok": False, "error": "x"})
        result = asyncio.run(adapter.execute_operation("get_projects", {}))
        assert result.success is False
        assert result.error.value == "API_ERROR"

    def test_unknown_operation(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.execute_operation("nope", {}))
        assert result.success is False
        assert result.error.value == "NOT_FOUND"

    def test_service_exception_maps_to_execution_exception(self):
        adapter = self._adapter()
        adapter.service.get_tasks = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(adapter.execute_operation("get_tasks", {}))
        assert result.success is False
        assert result.error.value == "EXECUTION_EXCEPTION"
        assert result.message == "boom"


# ===========================================================================
# integrations/adapters/line_adapter.py
# ===========================================================================

class TestLineAdapter:
    def _adapter(self, config=None):
        from integrations.adapters.line_adapter import LineAdapter
        cfg = config if config is not None else {
            "channel_access_token": LINE_TOKEN,
            "channel_secret": LINE_SECRET,
        }
        return LineAdapter(config=cfg)

    def test_init_configured(self):
        adapter = self._adapter()
        assert adapter.is_enabled is True
        assert adapter.channel_access_token == LINE_TOKEN
        assert adapter.channel_secret == LINE_SECRET
        assert adapter.client is None
        assert adapter.api_url == "https://api.line.me/v2/bot"

    def test_init_unconfigured_warns(self):
        with patch.dict(os.environ, {"LINE_CHANNEL_ACCESS_TOKEN": "", "LINE_CHANNEL_SECRET": ""}):
            from integrations.adapters.line_adapter import LineAdapter
            adapter = LineAdapter(config={})
        assert adapter.is_enabled is False
        assert not adapter.channel_access_token
        assert not adapter.channel_secret

    def test_init_env_fallback(self):
        with patch.dict(os.environ, {
            "LINE_CHANNEL_ACCESS_TOKEN": "env-tok",
            "LINE_CHANNEL_SECRET": "env-sec",
        }):
            from integrations.adapters.line_adapter import LineAdapter
            adapter = LineAdapter()
        assert adapter.channel_access_token == "env-tok"
        assert adapter.channel_secret == "env-sec"
        assert adapter.is_enabled is True

    def test_get_client_creates_lazily(self):
        adapter = self._adapter()
        client = AsyncMock()
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client) as ac:
            result = asyncio.run(adapter._get_client())
            again = asyncio.run(adapter._get_client())
        assert result is client
        assert again is client
        ac.assert_called_once_with(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {LINE_TOKEN}",
                "Content-Type": "application/json",
            },
        )

    def test_get_client_httpx_unavailable(self):
        adapter = self._adapter()
        with patch("integrations.adapters.line_adapter.HTTPX_AVAILABLE", False):
            assert asyncio.run(adapter._get_client()) is None

    def test_close_with_client(self):
        adapter = self._adapter()
        client = AsyncMock()
        adapter.client = client
        asyncio.run(adapter.close())
        client.aclose.assert_awaited_once_with()
        assert adapter.client is None

    def test_close_without_client(self):
        adapter = self._adapter()
        asyncio.run(adapter.close())
        assert adapter.client is None

    def test_verify_signature_without_secret_returns_true(self):
        adapter = self._adapter(config={"channel_access_token": LINE_TOKEN})
        assert adapter.verify_signature(b"body", "whatever") is True

    def test_verify_signature_valid(self):
        adapter = self._adapter()
        body = b'{"events": []}'
        sig = _line_signature(LINE_SECRET, body)
        assert adapter.verify_signature(body, sig) is True

    def test_verify_signature_invalid(self):
        adapter = self._adapter()
        assert adapter.verify_signature(b"body", _line_signature(LINE_SECRET, b"other")) is False

    def test_verify_signature_bad_base64(self):
        adapter = self._adapter()
        assert adapter.verify_signature(b"body", "!!!not-base64!!!") is False

    def test_send_message_no_client(self):
        adapter = self._adapter()
        with patch("integrations.adapters.line_adapter.HTTPX_AVAILABLE", False):
            result = asyncio.run(adapter.send_message("U1", "hi"))
        assert result == {"ok": False, "error": "httpx not available or LINE not configured"}

    def test_send_message_reply_token(self):
        adapter = self._adapter()
        client = _http_client(post_return=_resp())
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("U1", "hi", reply_token="rt"))
        assert result == {"ok": True, "sent": True}
        args, kwargs = client.post.call_args
        assert args[0] == "https://api.line.me/v2/bot/message/reply"
        assert kwargs["json"] == {"replyToken": "rt", "messages": [{"type": "text", "text": "hi"}]}

    def test_send_message_push(self):
        adapter = self._adapter()
        client = _http_client(post_return=_resp())
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("U1", "hi"))
        assert result == {"ok": True, "sent": True}
        args, kwargs = client.post.call_args
        assert args[0] == "https://api.line.me/v2/bot/message/push"
        assert kwargs["json"] == {"to": "U1", "messages": [{"type": "text", "text": "hi"}]}

    def test_send_message_http_error(self):
        adapter = self._adapter()
        client = _http_client(post_return=_resp(raise_error=True))
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("U1", "hi"))
        assert result["ok"] is False
        assert "HTTP 400" in result["error"]

    def test_send_message_client_exception(self):
        adapter = self._adapter()
        client = _http_client(post_side_effect=RuntimeError("conn refused"))
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("U1", "hi"))
        assert result == {"ok": False, "error": "conn refused"}

    def test_send_messages_no_client(self):
        adapter = self._adapter()
        with patch("integrations.adapters.line_adapter.HTTPX_AVAILABLE", False):
            result = asyncio.run(adapter.send_messages("U1", [{"type": "text", "text": "x"}]))
        assert result == {"ok": False, "error": "Client not available"}

    def test_send_messages_reply(self):
        adapter = self._adapter()
        msgs = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
        client = _http_client(post_return=_resp())
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_messages("U1", msgs, reply_token="rt"))
        assert result == {"ok": True, "sent": True, "count": 2}
        args, kwargs = client.post.call_args
        assert args[0] == "https://api.line.me/v2/bot/message/reply"
        assert kwargs["json"] == {"replyToken": "rt", "messages": msgs}

    def test_send_messages_push(self):
        adapter = self._adapter()
        msgs = [{"type": "text", "text": "a"}]
        client = _http_client(post_return=_resp())
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_messages("U1", msgs))
        assert result == {"ok": True, "sent": True, "count": 1}
        args, kwargs = client.post.call_args
        assert args[0] == "https://api.line.me/v2/bot/message/push"

    def test_send_messages_error(self):
        adapter = self._adapter()
        client = _http_client(post_side_effect=RuntimeError("boom"))
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_messages("U1", [{"type": "text", "text": "a"}]))
        assert result == {"ok": False, "error": "boom"}

    def test_send_quick_reply_delegates(self):
        adapter = self._adapter()
        items = [{"type": "action", "label": "Yes", "text": "yes"}]
        with patch.object(adapter, "send_messages",
                          new=AsyncMock(return_value={"ok": True, "sent": True, "count": 1})) as sm:
            result = asyncio.run(adapter.send_quick_reply("U1", "pick", items))
        sm.assert_awaited_once_with("U1", [{
            "type": "text",
            "text": "pick",
            "quickReply": {"items": items},
        }], None)
        assert result == {"ok": True, "sent": True, "count": 1}

    def test_send_quick_reply_exception(self):
        adapter = self._adapter()
        with patch.object(adapter, "send_messages",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio.run(adapter.send_quick_reply("U1", "pick", []))
        assert result == {"ok": False, "error": "boom"}

    def test_send_template_message_delegates(self):
        adapter = self._adapter()
        template = {"type": "buttons", "text": "t"}
        with patch.object(adapter, "send_messages",
                          new=AsyncMock(return_value={"ok": True, "sent": True, "count": 1})) as sm:
            result = asyncio.run(adapter.send_template_message("U1", "alt", template))
        sm.assert_awaited_once_with("U1", [{
            "type": "template",
            "altText": "alt",
            "template": template,
        }], None)
        assert result == {"ok": True, "sent": True, "count": 1}

    def test_send_template_message_exception(self):
        adapter = self._adapter()
        with patch.object(adapter, "send_messages",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio.run(adapter.send_template_message("U1", "alt", {}))
        assert result == {"ok": False, "error": "boom"}

    def test_get_user_profile_no_client(self):
        adapter = self._adapter()
        with patch("integrations.adapters.line_adapter.HTTPX_AVAILABLE", False):
            result = asyncio.run(adapter.get_user_profile("U1"))
        assert result == {"ok": False, "error": "Client not available"}

    def test_get_user_profile_success(self):
        adapter = self._adapter()
        client = _http_client(get_return=_resp({
            "userId": "U1", "displayName": "Bob", "pictureUrl": "http://p",
            "statusMessage": "hi",
        }))
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.get_user_profile("U1"))
        assert result == {
            "ok": True, "user_id": "U1", "display_name": "Bob",
            "picture_url": "http://p", "status_message": "hi",
        }
        client.get.assert_awaited_once_with("https://api.line.me/v2/bot/profile/U1")

    def test_get_user_profile_error(self):
        adapter = self._adapter()
        client = _http_client(get_side_effect=RuntimeError("boom"))
        with patch("integrations.adapters.line_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.get_user_profile("U1"))
        assert result == {"ok": False, "error": "boom"}

    def test_webhook_no_events(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.handle_webhook_event({}))
        assert result == {"ok": False, "error": "No events in webhook"}

    def test_webhook_text_message(self):
        adapter = self._adapter()
        event = {
            "type": "message", "source": {"type": "user", "userId": "U1"},
            "replyToken": "rt", "timestamp": 123,
            "message": {"type": "text", "id": "m1", "text": "hello"},
        }
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "message"
        assert result["source_id"] == "U1"
        assert result["text"] == "hello"
        assert result["message_id"] == "m1"
        assert result["timestamp"] == 123
        assert result["raw_data"] == event

    def test_webhook_non_text_message(self):
        adapter = self._adapter()
        event = {
            "type": "message", "source": {"type": "group", "groupId": "G1"},
            "replyToken": "rt", "timestamp": 1,
            "message": {"type": "image", "id": "m2", "contentProvider": {"type": "line"}},
        }
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["message_type"] == "image"
        assert result["source_id"] == "G1"
        assert result["content_provider"] == {"type": "line"}

    def test_webhook_follow(self):
        adapter = self._adapter()
        event = {"type": "follow", "source": {"type": "user", "userId": "U1"},
                 "replyToken": "rt", "timestamp": 1}
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "follow"

    def test_webhook_unfollow(self):
        adapter = self._adapter()
        event = {"type": "unfollow", "source": {"type": "user", "userId": "U1"}, "timestamp": 1}
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "unfollow"
        assert result.get("reply_token") is None

    def test_webhook_join(self):
        adapter = self._adapter()
        event = {"type": "join", "source": {"type": "room", "roomId": "R1"},
                 "replyToken": "rt", "timestamp": 1}
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "join"
        assert result["source_id"] == "R1"

    def test_webhook_leave(self):
        adapter = self._adapter()
        event = {"type": "leave", "source": {"type": "group", "groupId": "G1"}, "timestamp": 1}
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "leave"

    def test_webhook_postback(self):
        adapter = self._adapter()
        event = {"type": "postback", "source": {"type": "user", "userId": "U1"},
                 "replyToken": "rt", "timestamp": 1,
                 "postback": {"data": "action=1", "params": {"date": "20260101"}}}
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "postback"
        assert result["data"] == "action=1"
        assert result["params"] == {"date": "20260101"}

    def test_webhook_beacon(self):
        adapter = self._adapter()
        event = {"type": "beacon", "source": {"type": "user", "userId": "U1"},
                 "replyToken": "rt", "timestamp": 1,
                 "beacon": {"hwid": "hw-1", "type": "enter"}}
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "beacon"
        assert result["hwid"] == "hw-1"

    def test_webhook_unknown_type(self):
        adapter = self._adapter()
        event = {"type": "accountLink", "source": {"type": "user", "userId": "U1"},
                 "timestamp": 1, "link": {"result": "ok"}}
        result = asyncio.run(adapter.handle_webhook_event({"events": [event]}))
        assert result["ok"] is True
        assert result["event_type"] == "accountLink"
        assert result["raw_data"] == event

    def test_webhook_exception(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.handle_webhook_event({"events": [123]}))
        assert result["ok"] is False
        assert "error" in result

    def test_get_capabilities(self):
        adapter = self._adapter()
        caps = asyncio.run(adapter.get_capabilities())
        assert caps["platform"] == "LINE"
        assert caps["features"]["messaging"] is True
        assert caps["governance"]["student"] == {"blocked": True}

    def test_get_service_status_enabled(self):
        adapter = self._adapter()
        status = asyncio.run(adapter.get_service_status())
        assert status == {"status": "active", "service": "LINE",
                          "configured": True, "api_version": "v2"}

    def test_get_service_status_disabled(self):
        adapter = self._adapter(config={})
        status = asyncio.run(adapter.get_service_status())
        assert status["status"] == "inactive"
        assert status["configured"] is False


# ===========================================================================
# integrations/adapters/signal_adapter.py
# ===========================================================================

class TestSignalAdapter:
    def _adapter(self, config=None):
        from integrations.adapters.signal_adapter import SignalAdapter
        cfg = config if config is not None else {"signal_phone_number": "+15551234567"}
        return SignalAdapter(config=cfg)

    def test_init_configured(self):
        adapter = self._adapter()
        assert adapter.is_enabled is True
        assert adapter.phone_number == "+15551234567"
        assert adapter.api_url == "http://localhost:8080"
        assert adapter.account_number is None

    def test_init_unconfigured_warns(self):
        with patch.dict(os.environ, {"SIGNAL_PHONE_NUMBER": "", "SIGNAL_ACCOUNT_NUMBER": ""}):
            from integrations.adapters.signal_adapter import SignalAdapter
            adapter = SignalAdapter(config={})
        assert adapter.is_enabled is False
        assert not adapter.phone_number

    def test_init_env_fallback(self):
        with patch.dict(os.environ, {
            "SIGNAL_API_URL": "http://sig:9090",
            "SIGNAL_PHONE_NUMBER": "+19990000000",
            "SIGNAL_ACCOUNT_NUMBER": "acct-1",
        }):
            from integrations.adapters.signal_adapter import SignalAdapter
            adapter = SignalAdapter()
        assert adapter.api_url == "http://sig:9090"
        assert adapter.phone_number == "+19990000000"
        assert adapter.account_number == "acct-1"
        assert adapter.is_enabled is True

    def test_get_client_creates_lazily(self):
        adapter = self._adapter()
        client = AsyncMock()
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client) as ac:
            result = asyncio.run(adapter._get_client())
            again = asyncio.run(adapter._get_client())
        assert result is client
        assert again is client
        ac.assert_called_once_with(base_url="http://localhost:8080", timeout=30.0)

    def test_get_client_httpx_unavailable(self):
        adapter = self._adapter()
        with patch("integrations.adapters.signal_adapter.HTTPX_AVAILABLE", False):
            assert asyncio.run(adapter._get_client()) is None

    def test_close_with_client(self):
        adapter = self._adapter()
        client = AsyncMock()
        adapter.client = client
        asyncio.run(adapter.close())
        client.aclose.assert_awaited_once_with()
        assert adapter.client is None

    def test_close_without_client(self):
        adapter = self._adapter()
        asyncio.run(adapter.close())
        assert adapter.client is None

    def test_send_message_no_client(self):
        adapter = self._adapter()
        with patch("integrations.adapters.signal_adapter.HTTPX_AVAILABLE", False):
            result = asyncio.run(adapter.send_message("+1", "hi"))
        assert result == {"ok": False, "error": "httpx not available or Signal not configured"}

    def test_send_message_success_with_timestamp(self):
        adapter = self._adapter()
        client = _http_client(post_return=_resp({"timestamp": "123456"}))
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("+1555", "hello"))
        assert result == {"ok": True, "message_id": "123456", "recipient": "+1555",
                          "timestamp": "123456", "payload": {"timestamp": "123456"}}
        args, kwargs = client.post.call_args
        assert args[0] == "/v2/send"
        assert kwargs["json"] == {"message": "hello", "number": "+1555", "recipients": ["+1555"]}

    def test_send_message_success_without_timestamp_uses_fallback(self):
        adapter = self._adapter()
        client = _http_client(post_return=_resp({}))
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("+1555", "hello"))
        assert result["ok"] is True
        assert isinstance(result["message_id"], str)
        assert float(result["message_id"]) > 0

    def test_send_message_with_attachments(self):
        adapter = self._adapter()
        attachments = [{"filename": "a.png", "contentType": "image/png"}]
        client = _http_client(post_return=_resp({"timestamp": "1"}))
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("+1555", "hi", attachments=attachments))
        assert result["ok"] is True
        _, kwargs = client.post.call_args
        assert kwargs["json"]["attachments"] == attachments

    def test_send_message_error(self):
        adapter = self._adapter()
        client = _http_client(post_side_effect=RuntimeError("boom"))
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_message("+1555", "hi"))
        assert result == {"ok": False, "error": "boom"}

    def test_send_receipt_no_client(self):
        adapter = self._adapter()
        with patch("integrations.adapters.signal_adapter.HTTPX_AVAILABLE", False):
            result = asyncio.run(adapter.send_receipt("+1555", "123"))
        assert result == {"ok": False, "error": "Client not available"}

    def test_send_receipt_success(self):
        adapter = self._adapter()
        client = _http_client(post_return=_resp())
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_receipt("+1555", "123", "read"))
        assert result == {"ok": True, "recipient": "+1555", "type": "read"}
        args, kwargs = client.post.call_args
        assert args[0] == "/v1/receipt"
        assert kwargs["json"] == {"recipient": "+1555", "timestamp": "123", "type": "read"}

    def test_send_receipt_error(self):
        adapter = self._adapter()
        client = _http_client(post_side_effect=RuntimeError("boom"))
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.send_receipt("+1555", "123"))
        assert result == {"ok": False, "error": "boom"}

    def test_get_account_info_no_client(self):
        adapter = self._adapter()
        with patch("integrations.adapters.signal_adapter.HTTPX_AVAILABLE", False):
            result = asyncio.run(adapter.get_account_info())
        assert result == {"ok": False, "error": "Client not available"}

    def test_get_account_info_success(self):
        adapter = self._adapter()
        client = _http_client(get_return=_resp({"number": "+1555"}))
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.get_account_info())
        assert result == {"ok": True, "data": {"number": "+1555"}}
        client.get.assert_awaited_once_with("/v1/about")

    def test_get_account_info_error(self):
        adapter = self._adapter()
        client = _http_client(get_side_effect=RuntimeError("boom"))
        with patch("integrations.adapters.signal_adapter.httpx.AsyncClient", return_value=client):
            result = asyncio.run(adapter.get_account_info())
        assert result == {"ok": False, "error": "boom"}

    def test_verify_webhook(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.verify_webhook("challenge-1"))
        assert result == {"ok": True, "challenge": "challenge-1"}

    def test_webhook_message_event(self):
        adapter = self._adapter()
        event = {
            "type": "message",
            "envelope": {"timestamp": "123", "data": {
                "source": {"number": "+1555"},
                "message": {"body": "hi there"},
            }},
        }
        result = asyncio.run(adapter.handle_webhook_event(event))
        assert result == {
            "ok": True, "event_type": "message", "sender_number": "+1555",
            "message": "hi there", "timestamp": "123", "raw_data": event,
        }

    def test_webhook_receipt_event(self):
        adapter = self._adapter()
        event = {
            "type": "receipt",
            "envelope": {"data": {"receipt": {"type": "read", "timestamp": "9"}}},
        }
        result = asyncio.run(adapter.handle_webhook_event(event))
        assert result["ok"] is True
        assert result["event_type"] == "receipt"
        assert result["type"] == "read"
        assert result["timestamp"] == "9"

    def test_webhook_unknown_event(self):
        adapter = self._adapter()
        event = {"type": "ping"}
        result = asyncio.run(adapter.handle_webhook_event(event))
        assert result == {"ok": True, "event_type": "ping", "raw_data": event}

    def test_webhook_exception(self):
        adapter = self._adapter()
        result = asyncio.run(adapter.handle_webhook_event({"type": "message", "envelope": 1}))
        assert result["ok"] is False
        assert "error" in result

    def test_get_capabilities(self):
        adapter = self._adapter()
        caps = asyncio.run(adapter.get_capabilities())
        assert caps["platform"] == "Signal"
        assert caps["features"]["attachments"] is True
        assert caps["governance"]["intern"] == {"requires_approval": True}

    def test_get_service_status_active_with_account_info(self):
        adapter = self._adapter()
        with patch.object(adapter, "get_account_info",
                          new=AsyncMock(return_value={"ok": True, "data": {"number": "+1"}})):
            status = asyncio.run(adapter.get_service_status())
        assert status["status"] == "active"
        assert status["configured"] is True
        assert status["account_info"] == {"ok": True, "data": {"number": "+1"}}

    def test_get_service_status_account_info_not_ok(self):
        adapter = self._adapter()
        with patch.object(adapter, "get_account_info",
                          new=AsyncMock(return_value={"ok": False, "error": "x"})):
            status = asyncio.run(adapter.get_service_status())
        assert status["status"] == "active"
        assert status["account_info"] is None

    def test_get_service_status_inactive(self):
        adapter = self._adapter(config={})
        with patch.object(adapter, "get_account_info",
                          new=AsyncMock(return_value={"ok": True})):
            status = asyncio.run(adapter.get_service_status())
        assert status["status"] == "inactive"
        assert status["configured"] is False

    def test_get_service_status_exception(self):
        adapter = self._adapter()
        with patch.object(adapter, "get_account_info",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            status = asyncio.run(adapter.get_service_status())
        assert status["status"] == "error"
        assert status["error"] == "boom"


# ===========================================================================
# integrations/bridge/external_integration_routes.py
# ===========================================================================

class TestExternalIntegrationRoutes:
    """Routes carry NO auth dependency (mounted raw in main_api_app.py), so
    401/403 paths are N/A for this router."""

    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from integrations.bridge.external_integration_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)

    def test_list_integrations_success(self):
        from integrations.bridge import external_integration_routes as mod
        c = self._client()
        with patch.object(mod.external_integration_service, "get_all_integrations",
                          new=AsyncMock(return_value=[{"name": "slack"}, {"name": "asana"}])):
            resp = c.get("/api/v1/external-integrations/")
        assert resp.status_code == 200
        assert resp.json() == [{"name": "slack"}, {"name": "asana"}]

    def test_get_details_success(self):
        from integrations.bridge import external_integration_routes as mod
        c = self._client()
        details = {"name": "slack", "actions": [{"name": "send_message"}]}
        with patch.object(mod.external_integration_service, "get_piece_details",
                          new=AsyncMock(return_value=details)):
            resp = c.get("/api/v1/external-integrations/slack")
        assert resp.status_code == 200
        assert resp.json() == details

    def test_get_details_not_found(self):
        from integrations.bridge import external_integration_routes as mod
        c = self._client()
        with patch.object(mod.external_integration_service, "get_piece_details",
                          new=AsyncMock(return_value=None)):
            resp = c.get("/api/v1/external-integrations/ghost")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Integration not found"

    def test_execute_success(self):
        from integrations.bridge import external_integration_routes as mod
        c = self._client()
        with patch.object(mod.external_integration_service, "execute_integration_action",
                          new=AsyncMock(return_value={"ok": True})) as ex:
            resp = c.post("/api/v1/external-integrations/execute", json={
                "pieceName": "slack", "actionName": "send_message",
                "props": {"text": "hi"}, "auth": {"token": "x"},
            })
        ex.assert_awaited_once_with(
            integration_id="slack", action_id="send_message",
            params={"text": "hi"}, credentials={"token": "x"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "output": {"ok": True}}

    def test_execute_missing_fields_400(self):
        """Regression: 400 was swallowed by except Exception -> 500."""
        from integrations.bridge import external_integration_routes as mod
        c = self._client()
        with patch.object(mod.external_integration_service, "execute_integration_action",
                          new=AsyncMock(return_value={})):
            resp = c.post("/api/v1/external-integrations/execute", json={"pieceName": "slack"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Missing pieceName or actionName"

    def test_execute_service_exception_500(self):
        from integrations.bridge import external_integration_routes as mod
        c = self._client()
        with patch.object(mod.external_integration_service, "execute_integration_action",
                          new=AsyncMock(side_effect=RuntimeError("node down"))):
            resp = c.post("/api/v1/external-integrations/execute", json={
                "pieceName": "p", "actionName": "a",
            })
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"

    def test_execute_invalid_payload_422(self):
        c = self._client()
        resp = c.post("/api/v1/external-integrations/execute", json=[])
        assert resp.status_code == 422

    def test_get_execute_path_hits_details_piece(self):
        """GET /execute routes to get_piece_details(piece_name='execute')."""
        from integrations.bridge import external_integration_routes as mod
        c = self._client()
        with patch.object(mod.external_integration_service, "get_piece_details",
                          new=AsyncMock(return_value=None)) as details:
            resp = c.get("/api/v1/external-integrations/execute")
        details.assert_awaited_once_with("execute")
        assert resp.status_code == 404
