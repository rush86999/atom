# -*- coding: utf-8 -*-
"""W85C — coverage push: core/integrations/adapters/{monday,onedrive,stripe,zoho}
+ core/integrations/zoho_oauth_service.py.

Baselines (existing suites only): monday 0%, onedrive 0%, stripe 0%,
zoho 40%, zoho_oauth_service 82%. Style: mocked httpx.AsyncClient, zero
network, zero LLM spend, fake DB session (no real DB).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from core.integrations.adapters.monday import MondayAdapter
from core.integrations.adapters.onedrive import OneDriveAdapter
from core.integrations.adapters.stripe import StripeAdapter
from core.integrations.adapters.zoho import ZohoAdapter
from core.integrations.zoho_oauth_service import ZohoOAuthService


def _run(coro):
    return asyncio.run(coro)


class _Resp:
    def __init__(self, payload=None, status=200, content=b"bytes"):
        self._payload = payload if payload is not None else {}
        self.status_code = status
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"{self.status_code} error", request=None, response=self)

    def json(self):
        return self._payload


class _Client:
    def __init__(self, responses=None, responder=None):
        self.queue = list(responses or [])
        self.responder = responder
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _next(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if self.responder:
            return self.responder(method, url, **kw)
        return self.queue.pop(0) if self.queue else _Resp()

    async def get(self, url, headers=None, params=None):
        return self._next("get", url, headers=headers, params=params)

    async def post(self, url, data=None, json=None, headers=None, params=None):
        return self._next("post", url, headers=headers, data=data, json=json, params=params)

    async def patch(self, url, headers=None, json=None):
        return self._next("patch", url, headers=headers, json=json)

    async def put(self, url, headers=None, json=None, content=None):
        return self._next("put", url, headers=headers, json=json, content=content)

    async def delete(self, url, headers=None):
        return self._next("delete", url, headers=headers)


def _use_client(monkeypatch, client):
    monkeypatch.setattr(httpx, "AsyncClient", lambda: client)


class _FakeToken:
    def __init__(self, **kw):
        self.access_token = kw.get("access_token", kw.get("access", "at"))
        self.refresh_token = kw.get("refresh_token", kw.get("refresh", "rt"))
        self.expires_at = kw.get("expires_at", kw.get("expires"))
        self.credential_metadata = {}
        self.instance_url = kw.get("instance_url")
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeQuery:
    def __init__(self, first=None):
        self._first = first

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._first


class _FakeDB:
    def __init__(self, token=None):
        self.token = token
        self.committed = False
        self.added = []

    def query(self, model):
        return _FakeQuery(self.token)

    def add(self, obj):
        self.added.append(obj)
        if self.token is None:
            self.token = obj

    def commit(self):
        self.committed = True


# ===========================================================================
# Monday.com
# ===========================================================================
class TestMonday:
    MON_ENV = {
        "MONDAY_CLIENT_ID": "cid",
        "MONDAY_CLIENT_SECRET": "csec",
        "MONDAY_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, use_env=True):
        if use_env:
            for k, v in self.MON_ENV.items():
                monkeypatch.setenv(k, v)
        else:
            for k in self.MON_ENV:
                monkeypatch.delenv(k, raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return MondayAdapter(db=None, workspace_id="ws1")

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.service_name == "monday"
        assert adapter.client_id == "cid"
        assert adapter.base_url == "https://api.monday.com/v2"

    def test_get_oauth_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://auth.monday.com/oauth2/authorize?")
        assert "state=ws1" in url

    def test_get_oauth_url_missing_client_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter.client_id = None
        with pytest.raises(ValueError):
            _run(adapter.get_oauth_url())

    def test_exchange_code_for_token(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        data = _run(adapter.exchange_code_for_token("code"))
        assert data["access_token"] == "at"
        assert adapter._access_token == "at"
        assert adapter._token_expires_at is not None

    def test_exchange_code_for_token_no_expiry(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at"})])
        adapter = self._adapter(monkeypatch, client=client)
        assert _run(adapter.exchange_code_for_token("code")) == {"access_token": "at"}
        assert adapter._token_expires_at is None

    def test_exchange_code_for_token_missing_creds(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_code_for_token_http_error(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=400)]))
        adapter = self._adapter(monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.exchange_code_for_token("code"))

    def test_test_connection_no_token_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp({"data": {"users": []}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True
        assert client.calls[0][2]["headers"]["Authorization"] == "at"

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_get_boards(self, monkeypatch):
        client = _Client([_Resp({"data": {"boards": [{"id": "b1"}]}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_boards(limit=5)) == [{"id": "b1"}]
        assert client.calls[0][2]["json"]["variables"] == {"limit": 5}

    def test_get_boards_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_boards())

    def test_get_boards_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_boards())

    def test_get_items_with_boards(self, monkeypatch):
        client = _Client([_Resp({"data": {"boards": [{"items": [{"id": "i1"}]}]}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_items("b1")) == [{"id": "i1"}]

    def test_get_items_empty_boards(self, monkeypatch):
        client = _Client([_Resp({"data": {"boards": []}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_items("b1")) == []

    def test_get_items_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_items("b1"))

    def test_get_items_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_items("b1"))

    def test_get_item_found(self, monkeypatch):
        client = _Client([_Resp({"data": {"items": [{"id": "i1"}]}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_item("i1")) == {"id": "i1"}

    def test_get_item_not_found(self, monkeypatch):
        client = _Client([_Resp({"data": {"items": []}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_item("i1")) is None

    def test_get_item_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_item("i1"))

    def test_get_item_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_item("i1"))

    def test_create_item_with_columns(self, monkeypatch):
        client = _Client([_Resp({"data": {"create_item": {"id": "i1"}}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        item = _run(adapter.create_item("b1", "g1", "New", {"status": "Done"}))
        assert item == {"id": "i1"}
        variables = client.calls[0][2]["json"]["variables"]
        assert variables["columnValues"] == {"status": "Done"}

    def test_create_item_without_columns(self, monkeypatch):
        client = _Client([_Resp({"data": {"create_item": {"id": "i1"}}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        item = _run(adapter.create_item("b1", "g1", "New"))
        assert item == {"id": "i1"}
        assert client.calls[0][2]["json"]["variables"]["columnValues"] == {}

    def test_create_item_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_item("b1", "g1", "New"))

    def test_create_item_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_item("b1", "g1", "New"))

    def test_update_item(self, monkeypatch):
        client = _Client([_Resp({"data": {"change_multiple_column_values": {"id": "i1"}}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        item = _run(adapter.update_item("i1", {"status": "In Progress"}))
        assert item == {"id": "i1"}
        assert client.calls[0][2]["json"]["variables"]["columnValues"] == {"status": "In Progress"}

    def test_update_item_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.update_item("i1", {}))

    def test_update_item_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.update_item("i1", {}))

    def test_add_update(self, monkeypatch):
        client = _Client([_Resp({"data": {"create_update": {"id": "u1"}}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        update = _run(adapter.add_update("i1", "great work"))
        assert update == {"id": "u1"}

    def test_add_update_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.add_update("i1", "text"))

    def test_add_update_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.add_update("i1", "text"))

    def test_get_groups_with_boards(self, monkeypatch):
        client = _Client([_Resp({"data": {"boards": [{"groups": [{"id": "g1"}]}]}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_groups("b1")) == [{"id": "g1"}]

    def test_get_groups_empty_boards(self, monkeypatch):
        client = _Client([_Resp({"data": {"boards": []}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_groups("b1")) == []

    def test_get_groups_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_groups("b1"))

    def test_get_groups_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_groups("b1"))


# ===========================================================================
# OneDrive
# ===========================================================================
class TestOneDrive:
    OD_ENV = {
        "MICROSOFT_CLIENT_ID": "cid",
        "MICROSOFT_CLIENT_SECRET": "csec",
        "MICROSOFT_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, use_env=True):
        if use_env:
            for k, v in self.OD_ENV.items():
                monkeypatch.setenv(k, v)
        else:
            for k in self.OD_ENV:
                monkeypatch.delenv(k, raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return OneDriveAdapter(db=None, workspace_id="ws1")

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.service_name == "onedrive"
        assert adapter.client_id == "cid"
        assert adapter.base_url == "https://graph.microsoft.com/v1.0"

    def test_get_oauth_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?")
        assert "state=ws1" in url

    def test_get_oauth_url_missing_client_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter.client_id = None
        with pytest.raises(ValueError):
            _run(adapter.get_oauth_url())

    def test_exchange_code_for_token(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        data = _run(adapter.exchange_code_for_token("code"))
        assert data["access_token"] == "at"
        assert adapter._refresh_token == "rt"

    def test_exchange_code_for_token_missing_creds(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_code_for_token_http_error(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=400)]))
        adapter = self._adapter(monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.exchange_code_for_token("code"))

    def test_refresh_access_token_no_refresh(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.refresh_access_token()) is None

    def test_refresh_access_token_no_creds(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_access_token()) is None

    def test_refresh_access_token_success(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_access_token()) == "new-at"
        assert adapter._refresh_token == "new-rt"

    def test_refresh_access_token_without_new_refresh(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_access_token()) == "new-at"
        assert adapter._refresh_token == "rt"

    def test_refresh_access_token_exception_none(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_access_token()) is None

    def test_test_connection_no_token_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp({"id": "d1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_list_files_with_path(self, monkeypatch):
        client = _Client([_Resp({"value": [{"id": "f1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.list_files("docs/2026")) == [{"id": "f1"}]
        assert client.calls[0][1].endswith("/me/drive/root:/docs/2026:/children")

    def test_list_files_root(self, monkeypatch):
        client = _Client([_Resp({"value": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.list_files()) == []
        assert client.calls[0][1].endswith("/me/drive/root/children")

    def test_list_files_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.list_files())

    def test_list_files_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.list_files())

    def test_get_file(self, monkeypatch):
        client = _Client([_Resp({"id": "f1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_file("f1")) == {"id": "f1"}

    def test_get_file_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_file("f1"))

    def test_get_file_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_file("f1"))

    def test_upload_file_with_folder(self, monkeypatch):
        client = _Client([_Resp({"id": "f1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        file_obj = SimpleFile(b"data")
        result = _run(adapter.upload_file(file_obj, "notes.txt", folder_path="docs"))
        assert result == {"id": "f1"}
        assert client.calls[0][0] == "put"
        assert client.calls[0][1].endswith("/me/drive/root:/docs/notes.txt:/content")
        assert client.calls[0][2]["content"] == b"data"

    def test_upload_file_root(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.upload_file(SimpleFile(b"x"), "a.txt"))
        assert client.calls[0][1].endswith("/me/drive/root:/a.txt:/content")

    def test_upload_file_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.upload_file(SimpleFile(b"x"), "a.txt"))

    def test_upload_file_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.upload_file(SimpleFile(b"x"), "a.txt"))

    def test_download_file(self, monkeypatch):
        client = _Client([_Resp(content=b"file-bytes")])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.download_file("f1")) == b"file-bytes"

    def test_download_file_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.download_file("f1"))

    def test_download_file_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.download_file("f1"))

    def test_create_folder_with_parent(self, monkeypatch):
        client = _Client([_Resp({"id": "folder1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.create_folder("NewFolder", parent_path="docs")) == {"id": "folder1"}
        assert client.calls[0][1].endswith("/me/drive/root:/docs:/children")

    def test_create_folder_root(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_folder("NewFolder"))
        assert client.calls[0][1].endswith("/me/drive/root/children")

    def test_create_folder_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_folder("NewFolder"))

    def test_create_folder_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_folder("NewFolder"))

    def test_delete_file_success(self, monkeypatch):
        client = _Client([_Resp(status=204)])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.delete_file("f1")) is True

    def test_delete_file_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.delete_file("f1"))

    def test_delete_file_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.delete_file("f1")) is False

    def test_share_file(self, monkeypatch):
        client = _Client([_Resp({"link": {"webUrl": "https://1drv.ms/x"}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        link = _run(adapter.share_file("f1", scope="view"))
        assert link["link"]["webUrl"] == "https://1drv.ms/x"
        assert client.calls[0][2]["json"] == {"type": "view", "scope": "anonymous"}

    def test_share_file_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.share_file("f1"))

    def test_share_file_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.share_file("f1"))

    def test_search_files(self, monkeypatch):
        client = _Client([_Resp({"value": [{"id": "f1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.search_files("quarterly")) == [{"id": "f1"}]
        assert client.calls[0][1].endswith("/me/drive/root/search(q='quarterly')")

    def test_search_files_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.search_files("q"))

    def test_search_files_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.search_files("q"))


class SimpleFile:
    def __init__(self, content: bytes):
        self._content = content

    def read(self):
        return self._content


# ===========================================================================
# Stripe
# ===========================================================================
class TestStripe:
    ST_ENV = {
        "STRIPE_CLIENT_ID": "cid",
        "STRIPE_SECRET_KEY": "sk_test_x",
        "STRIPE_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, use_env=True):
        if use_env:
            for k, v in self.ST_ENV.items():
                monkeypatch.setenv(k, v)
        else:
            for k in self.ST_ENV:
                monkeypatch.delenv(k, raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return StripeAdapter(db=None, workspace_id="ws1")

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.service_name == "stripe"
        assert adapter.client_id == "cid"
        assert adapter.client_secret == "sk_test_x"
        assert adapter.base_url == "https://api.stripe.com/v1"

    def test_get_oauth_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://connect.stripe.com/oauth/authorize?")
        assert "state=ws1" in url

    def test_get_oauth_url_missing_client_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter.client_id = None
        with pytest.raises(ValueError):
            _run(adapter.get_oauth_url())

    def test_exchange_code_for_token(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "stripe_user_id": "acct_1"})])
        adapter = self._adapter(monkeypatch, client=client)
        data = _run(adapter.exchange_code_for_token("code"))
        assert data["access_token"] == "at"
        assert data["stripe_user_id"] == "acct_1"
        assert adapter._access_token == "at"

    def test_exchange_code_for_token_missing_creds(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_code_for_token_http_error(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=400)]))
        adapter = self._adapter(monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.exchange_code_for_token("code"))

    def test_test_connection_no_token_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp({"id": "acct_1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_get_customers_with_starting_after(self, monkeypatch):
        client = _Client([_Resp({"data": [{"id": "c1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_customers(limit=5, starting_after="c0")) == [{"id": "c1"}]
        assert client.calls[0][2]["params"] == {"limit": 5, "starting_after": "c0"}

    def test_get_customers_default(self, monkeypatch):
        client = _Client([_Resp({"data": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_customers()) == []
        assert client.calls[0][2]["params"] == {"limit": 20}

    def test_get_customers_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_customers())

    def test_get_customers_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_customers())

    def test_get_customer(self, monkeypatch):
        client = _Client([_Resp({"id": "c1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_customer("c1")) == {"id": "c1"}

    def test_get_customer_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_customer("c1"))

    def test_get_customer_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_customer("c1"))

    def test_create_customer_full(self, monkeypatch):
        client = _Client([_Resp({"id": "c1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        customer = _run(adapter.create_customer(name="Jane", email="j@x.io", description="VIP", source="web"))
        assert customer == {"id": "c1"}
        sent = client.calls[0][2]["json"]
        assert sent["name"] == "Jane"
        assert sent["email"] == "j@x.io"
        assert sent["description"] == "VIP"
        assert sent["metadata"] == {"source": "web"}

    def test_create_customer_minimal(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_customer())
        assert client.calls[0][2]["json"] == {}

    def test_create_customer_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_customer())

    def test_create_customer_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_customer())

    def test_get_charges_with_created(self, monkeypatch):
        client = _Client([_Resp({"data": [{"id": "ch1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_charges(created={"gte": 100, "lte": 200})) == [{"id": "ch1"}]
        assert client.calls[0][2]["params"] == {"limit": 20, "created[gte]": 100, "created[lte]": 200}

    def test_get_charges_default(self, monkeypatch):
        client = _Client([_Resp({"data": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_charges()) == []
        assert client.calls[0][2]["params"] == {"limit": 20}

    def test_get_charges_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_charges())

    def test_get_charges_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_charges())

    def test_create_charge_full(self, monkeypatch):
        client = _Client([_Resp({"id": "ch1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        charge = _run(adapter.create_charge(1000, "usd", customer="c1", description="test", ref="r1"))
        assert charge == {"id": "ch1"}
        sent = client.calls[0][2]["json"]
        assert sent["amount"] == 1000
        assert sent["currency"] == "usd"
        assert sent["customer"] == "c1"
        assert sent["description"] == "test"
        assert sent["metadata"] == {"ref": "r1"}

    def test_create_charge_minimal(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_charge(1000, "usd"))
        assert client.calls[0][2]["json"] == {"amount": 1000, "currency": "usd"}

    def test_create_charge_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_charge(1000, "usd"))

    def test_create_charge_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_charge(1000, "usd"))

    def test_get_invoices_with_customer(self, monkeypatch):
        client = _Client([_Resp({"data": [{"id": "inv1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_invoices(customer="c1")) == [{"id": "inv1"}]
        assert client.calls[0][2]["params"] == {"limit": 20, "customer": "c1"}

    def test_get_invoices_default(self, monkeypatch):
        client = _Client([_Resp({"data": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_invoices()) == []
        assert client.calls[0][2]["params"] == {"limit": 20}

    def test_get_invoices_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_invoices())

    def test_get_invoices_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_invoices())

    def test_get_subscriptions_with_customer(self, monkeypatch):
        client = _Client([_Resp({"data": [{"id": "sub1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_subscriptions(customer="c1")) == [{"id": "sub1"}]

    def test_get_subscriptions_default(self, monkeypatch):
        client = _Client([_Resp({"data": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_subscriptions()) == []
        assert client.calls[0][2]["params"] == {"limit": 20}

    def test_get_subscriptions_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_subscriptions())

    def test_get_subscriptions_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_subscriptions())

    def test_create_payment_intent_full(self, monkeypatch):
        client = _Client([_Resp({"id": "pi1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        intent = _run(adapter.create_payment_intent(5000, "usd", customer="c1", metadata={"k": "v"}))
        assert intent == {"id": "pi1"}
        sent = client.calls[0][2]["json"]
        assert sent == {"amount": 5000, "currency": "usd", "customer": "c1", "metadata": {"k": "v"}}

    def test_create_payment_intent_minimal(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_payment_intent(5000, "usd"))
        assert client.calls[0][2]["json"] == {"amount": 5000, "currency": "usd"}

    def test_create_payment_intent_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_payment_intent(5000, "usd"))

    def test_create_payment_intent_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_payment_intent(5000, "usd"))


# ===========================================================================
# ZohoAdapter
# ===========================================================================
class TestZoho:
    Z_ENV = {
        "ZOHO_CLIENT_ID": "cid",
        "ZOHO_CLIENT_SECRET": "csec",
        "ZOHO_REDIRECT_URI": "https://app/cb",
        "ZOHO_DEFAULT_API_DOMAIN": "https://www.zohoapis.com",
    }

    def _adapter(self, monkeypatch, client=None, db=None, instance_url=None, use_env=True):
        if use_env:
            for k, v in self.Z_ENV.items():
                monkeypatch.setenv(k, v)
        if client is not None:
            _use_client(monkeypatch, client)
        return ZohoAdapter(db=db, workspace_id="ws1", instance_url=instance_url)

    def test_init_defaults(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.service_name == "zoho"
        assert adapter.instance_url == "https://www.zohoapis.com"
        assert adapter.client_id == "cid"

    def test_init_custom_instance_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch, instance_url="https://www.zohoapis.eu")
        assert adapter.instance_url == "https://www.zohoapis.eu"

    def test_get_base_url_crm(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter._get_base_url("crm") == "https://www.zohoapis.com/crm/v2"

    def test_get_base_url_books(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter._get_base_url("books") == "https://www.zohoapis.com/books/v3"

    def test_get_base_url_inventory(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter._get_base_url("inventory") == "https://www.zohoapis.com/inventory/v1"

    def test_get_base_url_projects(self, monkeypatch):
        adapter = self._adapter(monkeypatch, instance_url="https://www.zohoapis.eu")
        assert adapter._get_base_url("projects") == "https://projectsapi.zoho.eu/restapi/v1"

    def test_get_base_url_unknown_module_defaults_crm(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter._get_base_url("bogus") == "https://www.zohoapis.com/crm/v2"

    def test_get_base_url_upper_module(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter._get_base_url("CRM") == "https://www.zohoapis.com/crm/v2"

    def test_load_token_no_db(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        _run(adapter._load_token())
        assert adapter._access_token is None

    def test_load_token_with_instance_url(self, monkeypatch):
        db = _FakeDB(_FakeToken(
            access="plain-at", refresh="plain-rt", expires=datetime.now(timezone.utc),
            instance_url="https://www.zohoapis.eu"))
        adapter = self._adapter(monkeypatch, db=db)
        _run(adapter._load_token())
        assert adapter._access_token == "plain-at"
        assert adapter._refresh_token == "plain-rt"
        assert adapter.instance_url == "https://www.zohoapis.eu"

    def test_load_token_without_instance_url(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="plain-at", refresh=None, instance_url=None))
        adapter = self._adapter(monkeypatch, db=db)
        _run(adapter._load_token())
        assert adapter._access_token == "plain-at"
        assert adapter.instance_url == "https://www.zohoapis.com"

    def test_refresh_token_no_refresh_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.refresh_token()) is False

    def test_refresh_token_success_no_db(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert adapter._access_token == "new-at"

    def test_refresh_token_success_with_db(self, monkeypatch):
        token = _FakeToken(access="at", refresh="rt")
        db = _FakeDB(token)
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client, db=db)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert db.committed is True
        assert token.access_token != "new-at"

    def test_refresh_token_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is False

    def test_ensure_token_valid_noop(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter._access_token = "at"
        adapter._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
        _run(adapter.ensure_token())
        assert adapter._access_token == "at"

    def test_ensure_token_expired_refreshes(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "old-at"
        adapter._refresh_token = "rt"
        adapter._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        _run(adapter.ensure_token())
        assert adapter._access_token == "new-at"

    def test_ensure_token_loads_from_db(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="db-at", refresh="db-rt"))
        adapter = self._adapter(monkeypatch, db=db)
        _run(adapter.ensure_token())
        assert adapter._access_token == "db-at"

    def test_get_oauth_url_default_scopes(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://accounts.zoho.com/oauth/v2/auth?")
        assert "ZohoCRM.modules.ALL" in url
        assert "state=ws1" in url

    def test_get_oauth_url_custom_scopes(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url(scopes=["ZohoCRM.modules.ALL"]))
        assert "scope=ZohoCRM.modules.ALL" in url

    def test_get_leads_success(self, monkeypatch):
        client = _Client([_Resp({"data": [{"id": "1", "Full_Name": "A", "Email": "a@x.io"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        leads = _run(adapter.get_leads())
        assert leads[0]["type"] == "lead"
        assert leads[0]["name"] == "A"
        assert client.calls[0][2]["params"] == {"per_page": 100}
        assert client.calls[0][1] == "https://www.zohoapis.com/crm/v2/Leads"

    def test_get_leads_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_leads()) == []

    def test_get_deals_success(self, monkeypatch):
        client = _Client([_Resp({"data": [{"id": "1", "Deal_Name": "D", "Amount": 100}]})])
        adapter = self._adapter(monkeypatch, client=client)
        deals = _run(adapter.get_deals())
        assert deals[0]["type"] == "deal"
        assert deals[0]["name"] == "D"

    def test_get_deals_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_deals()) == []

    def test_get_invoices_success(self, monkeypatch):
        client = _Client([_Resp({"invoices": [{"invoice_id": "1", "invoice_number": "INV-1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        invoices = _run(adapter.get_invoices("org-1"))
        assert invoices[0]["type"] == "invoice"
        # Books/Inventory paginate with page/per_page (page_size was never a
        # documented Books param) and stop when has_more_page is absent.
        assert client.calls[0][2]["params"] == {
            "organization_id": "org-1", "page": 1, "per_page": 100,
        }

    def test_get_invoices_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_invoices("org-1")) == []

    def test_get_portals_success(self, monkeypatch):
        client = _Client([_Resp({"portals": [{"id_string": "p1", "name": "Portal"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        portals = _run(adapter.get_portals())
        assert portals[0]["type"] == "portal"
        assert client.calls[0][1] == "https://projectsapi.zoho.com/restapi/v1/portals/"

    def test_get_portals_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_portals()) == []

    def test_get_projects_success(self, monkeypatch):
        client = _Client([_Resp({"projects": [{"id_string": "pr1", "name": "Proj"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        projects = _run(adapter.get_projects("portal-1"))
        assert projects[0]["type"] == "project"
        assert client.calls[0][1] == "https://projectsapi.zoho.com/restapi/v1/portal/portal-1/projects/"

    def test_get_projects_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_projects("portal-1")) == []

    def test_get_tasks_success(self, monkeypatch):
        client = _Client([_Resp({"tasks": [{"id_string": "t1", "name": "Task", "status": {"name": "Open"}}]})])
        adapter = self._adapter(monkeypatch, client=client)
        tasks = _run(adapter.get_tasks("portal-1", "pr1"))
        assert tasks[0]["type"] == "task"
        assert tasks[0]["status"] == "Open"
        assert client.calls[0][1] == "https://projectsapi.zoho.com/restapi/v1/portal/portal-1/projects/pr1/tasks/"

    def test_get_tasks_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_tasks("portal-1", "pr1")) == []

    def test_get_items_success(self, monkeypatch):
        client = _Client([_Resp({"items": [{"item_id": "i1", "name": "Item"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        items = _run(adapter.get_items("org-1"))
        assert items[0]["type"] == "inventory_item"
        assert client.calls[0][1] == "https://www.zohoapis.com/inventory/v1/items"

    def test_get_items_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_items("org-1")) == []

    def test_get_sales_orders_success(self, monkeypatch):
        client = _Client([_Resp({"salesorders": [{"salesorder_id": "s1", "salesorder_number": "SO-1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        orders = _run(adapter.get_sales_orders("org-1"))
        assert orders[0]["type"] == "sales_order"
        assert client.calls[0][1] == "https://www.zohoapis.com/inventory/v1/salesorders"

    def test_get_sales_orders_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_sales_orders("org-1")) == []

    def test_map_helpers(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        lead = adapter._map_lead({"id": "1", "Full_Name": "A", "Email": "e", "Company": "C", "Lead_Status": "New"})
        assert lead["id"] == "1" and lead["company"] == "C"
        deal = adapter._map_deal({"id": "2", "Deal_Name": "D", "Amount": 5, "Stage": "S", "Closing_Date": "d"})
        assert deal["stage"] == "S"
        inv = adapter._map_invoice({"invoice_id": "3", "invoice_number": "N", "customer_name": "C", "total": 9, "status": "paid", "due_date": "d"})
        assert inv["number"] == "N"
        portal = adapter._map_portal({"id_string": "4", "name": "P"})
        assert portal["is_default"] is False
        project = adapter._map_project({"id_string": "5", "name": "Pr", "status": "active", "owner_name": "o", "created_date_format": "d"})
        assert project["created_at"] == "d"
        task = adapter._map_task({"id_string": "6", "name": "T", "description": "d", "priority": "high", "end_date": "e"})
        assert task["description"] == "d"
        item = adapter._map_inventory_item({"item_id": "7", "name": "I", "sku": "s", "description": "d", "rate": 1, "stock_on_hand": 2, "unit": "u"})
        assert item["sku"] == "s"
        order = adapter._map_sales_order({"salesorder_id": "8", "salesorder_number": "N", "customer_name": "C", "total": 3, "status": "open", "date": "d"})
        assert order["date"] == "d"
        assert adapter._map_portal({})["is_default"] is False


# ===========================================================================
# ZohoOAuthService
# ===========================================================================
class TestZohoOAuthService:
    Z_ENV = {
        "ZOHO_CLIENT_ID": "cid",
        "ZOHO_CLIENT_SECRET": "csec",
        "ZOHO_REDIRECT_URI": "https://app/cb",
        "ZOHO_DEFAULT_API_DOMAIN": "https://www.zohoapis.com",
    }

    def _set_env(self, monkeypatch):
        for k, v in self.Z_ENV.items():
            monkeypatch.setenv(k, v)

    def _db(self, token=None):
        return _FakeDB(token)

    def test_exchange_code_instance_url_from_api_domain(self, monkeypatch):
        self._set_env(monkeypatch)
        token = _FakeToken(access="at", refresh="rt", instance_url="https://old.com")
        db = self._db(token)
        client = _Client([_Resp({"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600})])
        _use_client(monkeypatch, client)
        result = _run(ZohoOAuthService.exchange_code_for_token(db, "code", "t1", api_domain="https://www.zohoapis.eu"))
        assert result["success"] is True
        assert result["instance_url"] == "https://www.zohoapis.eu"
        assert db.committed is True
        assert token.access_token != "new-at"
        assert token.instance_url == "https://www.zohoapis.eu"
        assert token.last_used_at is not None

    def test_exchange_code_instance_url_from_location_with_http_prefix(self, monkeypatch):
        self._set_env(monkeypatch)
        db = self._db(None)
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 60})])
        _use_client(monkeypatch, client)
        result = _run(ZohoOAuthService.exchange_code_for_token(db, "code", "t1", location="zohoapis.in"))
        assert result["instance_url"] == "https://zohoapis.in"
        assert result["expires_at"] is not None

    def test_exchange_code_env_default_instance_url(self, monkeypatch):
        self._set_env(monkeypatch)
        db = self._db(None)
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt"})])
        _use_client(monkeypatch, client)
        result = _run(ZohoOAuthService.exchange_code_for_token(db, "code", "t1"))
        assert result["instance_url"] == "https://www.zohoapis.com"
        assert db.token is not None
        assert db.token.provider == "zoho"
        assert db.token.status == "active"

    def test_exchange_code_existing_token_keeps_refresh_when_absent(self, monkeypatch):
        self._set_env(monkeypatch)
        token = _FakeToken(access="old-at", refresh="old-rt")
        db = self._db(token)
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 3600})])
        _use_client(monkeypatch, client)
        result = _run(ZohoOAuthService.exchange_code_for_token(db, "code", "t1"))
        assert result["success"] is True
        assert token.access_token != "new-at"
        assert token.refresh_token == "old-rt"

    def test_exchange_code_failure_raises_value_error(self, monkeypatch):
        self._set_env(monkeypatch)
        db = self._db(None)

        def boom(method, url, **kw):
            raise OSError("net down")

        _use_client(monkeypatch, _Client(responder=boom))
        with pytest.raises(ValueError):
            _run(ZohoOAuthService.exchange_code_for_token(db, "code", "t1"))

    def test_refresh_token_no_refresh_returns_none(self, monkeypatch):
        self._set_env(monkeypatch)
        token = _FakeToken(refresh_token=None)
        assert _run(ZohoOAuthService.refresh_token(self._db(token), token)) is None

    def test_refresh_token_decrypt_empty_returns_none(self, monkeypatch):
        self._set_env(monkeypatch)
        token = _FakeToken(refresh_token="rt")
        db = self._db(token)
        with patch_token_encryption_decrypt(""):
            assert _run(ZohoOAuthService.refresh_token(db, token)) is None

    def test_refresh_token_success(self, monkeypatch):
        self._set_env(monkeypatch)
        token = _FakeToken(access="at", refresh="rt")
        db = self._db(token)
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 3600})])
        _use_client(monkeypatch, client)
        result = _run(ZohoOAuthService.refresh_token(db, token))
        assert result is not None
        assert result == token.access_token
        assert db.committed is True

    def test_refresh_token_exception_returns_none(self, monkeypatch):
        self._set_env(monkeypatch)
        token = _FakeToken(access="at", refresh="rt")
        db = self._db(token)

        def boom(method, url, **kw):
            raise OSError("net down")

        _use_client(monkeypatch, _Client(responder=boom))
        assert _run(ZohoOAuthService.refresh_token(db, token)) is None


class _DecryptPatch:
    """Patches core.privsec.token_encryption.decrypt_token in-process."""

    def __init__(self, value):
        self.value = value
        self._orig = None

    def __enter__(self):
        import core.privsec.token_encryption as te
        self._orig = te.decrypt_token
        te.decrypt_token = lambda ciphertext, key=None, allow_plaintext=True: self.value
        return self

    def __exit__(self, *a):
        import core.privsec.token_encryption as te
        te.decrypt_token = self._orig
        return False


def patch_token_encryption_decrypt(value):
    return _DecryptPatch(value)
