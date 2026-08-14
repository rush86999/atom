# -*- coding: utf-8 -*-
"""W85B — coverage push: core/integrations/adapters/figma, hubspot, jira, microsoft365.

Baselines (existing suites only): figma 0%, hubspot 10%, jira 20%,
microsoft365 0%. Style: mocked httpx.AsyncClient, zero network, zero LLM
spend, no real DB. Env vars via monkeypatch.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from core.integrations.adapters.figma import FigmaAdapter
from core.integrations.adapters.hubspot import HubSpotAdapter
from core.integrations.adapters.jira import JiraAdapter
from core.integrations.adapters.microsoft365 import Microsoft365Adapter


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


def _expired():
    return datetime.now(timezone.utc) - timedelta(seconds=10)


def _fresh():
    return datetime.now(timezone.utc) + timedelta(seconds=3600)


# ===========================================================================
# Figma
# ===========================================================================
class TestFigma:
    FIGMA_ENV = {
        "FIGMA_CLIENT_ID": "cid",
        "FIGMA_CLIENT_SECRET": "csec",
        "FIGMA_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, use_env=True, no_creds=False):
        if use_env:
            for k, v in self.FIGMA_ENV.items():
                monkeypatch.setenv(k, v)
        else:
            for k in self.FIGMA_ENV:
                monkeypatch.delenv(k, raising=False)
        if no_creds:
            monkeypatch.delenv("FIGMA_CLIENT_ID", raising=False)
            monkeypatch.delenv("FIGMA_CLIENT_SECRET", raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return FigmaAdapter(db=None, workspace_id="ws1")

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.service_name == "figma"
        assert adapter.client_id == "cid"
        assert adapter.base_url == "https://api.figma.com"

    def test_get_oauth_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://www.figma.com/oauth?")
        assert "state=ws1" in url

    def test_get_oauth_url_missing_client_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch, no_creds=True)
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
        adapter = self._adapter(monkeypatch, no_creds=True)
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
        client = _Client([_Resp({"id": "u1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True
        assert client.calls[0][2]["headers"] == {"X-Figma-Token": "at"}

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_get_files_without_team(self, monkeypatch):
        client = _Client([_Resp({"id": "u1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_files()) == {"id": "u1"}
        assert client.calls[0][1].endswith("/v1/me")

    def test_get_files_with_team(self, monkeypatch):
        client = _Client([
            _Resp({"projects": [{"id": "p1"}, {"id": "p2"}]}),
            _Resp({"files": [{"key": "f1"}]}),
            _Resp({"files": [{"key": "f2"}]}),
        ])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        files = _run(adapter.get_files(team_id="team-1"))
        assert files == [{"key": "f1"}, {"key": "f2"}]
        assert client.calls[0][1].endswith("/v1/teams/team-1/projects")
        assert client.calls[1][1].endswith("/v1/projects/p1/files")

    def test_get_files_team_without_projects_key(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_files(team_id="team-1")) == {}

    def test_get_files_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_files())

    def test_get_files_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_files())

    def test_get_project_files_no_token_returns_empty(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter._get_project_files("p1")) == []

    def test_get_project_files_exception_returns_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter._get_project_files("p1")) == []

    def test_get_file(self, monkeypatch):
        client = _Client([_Resp({"key": "f1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_file("f1")) == {"key": "f1"}
        assert client.calls[0][2]["params"] == {"depth": "none"}

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

    def test_get_file_nodes(self, monkeypatch):
        client = _Client([_Resp({"nodes": {}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_file_nodes("f1", ["n1", "n2"])) == {"nodes": {}}
        assert client.calls[0][2]["params"] == {"ids": "n1,n2"}

    def test_get_file_nodes_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_file_nodes("f1", ["n1"]))

    def test_get_file_nodes_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_file_nodes("f1", ["n1"]))

    def test_get_components(self, monkeypatch):
        client = _Client([_Resp({"meta": {"components": [{"id": "c1"}]}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_components("f1")) == [{"id": "c1"}]

    def test_get_components_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_components("f1"))

    def test_get_components_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_components("f1"))

    def test_get_comments(self, monkeypatch):
        client = _Client([_Resp([{"id": "cm1"}])])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_comments("f1")) == [{"id": "cm1"}]

    def test_get_comments_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_comments("f1"))

    def test_get_comments_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_comments("f1"))

    def test_post_comment_with_node_id(self, monkeypatch):
        client = _Client([_Resp({"id": "cm1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        comment = _run(adapter.post_comment("f1", "hello", client_id="cli-1", node_id="n1"))
        assert comment == {"id": "cm1"}
        assert client.calls[0][2]["json"] == {"message": "hello", "client_id": "cli-1", "node_id": "n1"}

    def test_post_comment_default_client_id(self, monkeypatch):
        client = _Client([_Resp({"id": "cm1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        comment = _run(adapter.post_comment("f1", "hello"))
        sent = client.calls[0][2]["json"]
        assert sent["message"] == "hello"
        assert sent["client_id"].startswith("ws1_")
        assert "node_id" not in sent
        assert comment == {"id": "cm1"}

    def test_post_comment_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.post_comment("f1", "hello"))

    def test_post_comment_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.post_comment("f1", "hello"))

    def test_get_teams(self, monkeypatch):
        client = _Client([_Resp({"teams": [{"id": "t1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_teams()) == [{"id": "t1"}]

    def test_get_teams_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_teams())

    def test_get_teams_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_teams())

    def test_get_projects(self, monkeypatch):
        client = _Client([_Resp({"projects": [{"id": "p1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_projects("team-1")) == [{"id": "p1"}]

    def test_get_projects_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_projects("team-1"))

    def test_get_projects_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_projects("team-1"))

    def test_get_image_with_nodes(self, monkeypatch):
        client = _Client([_Resp({"images": {"n1": "url"}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_image("f1", ["n1"], format="svg", scale=2)) == {"images": {"n1": "url"}}
        assert client.calls[0][2]["params"] == {"format": "svg", "scale": 2, "ids": "n1"}

    def test_get_image_without_nodes(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_image("f1")) == {}
        assert client.calls[0][2]["params"] == {"format": "png", "scale": 1}

    def test_get_image_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_image("f1"))

    def test_get_image_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_image("f1"))


# ===========================================================================
# HubSpot
# ===========================================================================
class TestHubSpot:
    HS_ENV = {
        "HUBSPOT_CLIENT_ID": "cid",
        "HUBSPOT_CLIENT_SECRET": "csec",
        "HUBSPOT_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, db=None, use_env=True):
        if use_env:
            for k, v in self.HS_ENV.items():
                monkeypatch.setenv(k, v)
        else:
            for k in self.HS_ENV:
                monkeypatch.delenv(k, raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return HubSpotAdapter(db=db, workspace_id="ws1")

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.service_name == "hubspot"
        assert adapter.client_id == "cid"
        assert adapter.base_url == "https://api.hubapi.com"

    def test_load_token_no_db(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        _run(adapter._load_token())
        assert adapter._access_token is None

    def test_load_token_with_db(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="plain-at", refresh="plain-rt", expires=datetime.now(timezone.utc)))
        adapter = self._adapter(monkeypatch, db=db)
        _run(adapter._load_token())
        assert adapter._access_token == "plain-at"
        assert adapter._refresh_token == "plain-rt"

    def test_load_token_db_no_refresh(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="plain-at", refresh=None))
        adapter = self._adapter(monkeypatch, db=db)
        _run(adapter._load_token())
        assert adapter._access_token == "plain-at"
        assert adapter._refresh_token is None

    def test_refresh_token_no_refresh_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.refresh_token()) is False

    def test_refresh_token_success_no_db(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 1800})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert adapter._access_token == "new-at"
        assert adapter._token_expires_at is not None

    def test_refresh_token_success_with_db(self, monkeypatch):
        token = _FakeToken(access="at", refresh="rt")
        db = _FakeDB(token)
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 1800})])
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
        adapter._token_expires_at = _fresh()
        _run(adapter.ensure_token())
        assert adapter._access_token == "at"

    def test_ensure_token_expired_refreshes(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 1800})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "old-at"
        adapter._refresh_token = "rt"
        adapter._token_expires_at = _expired()
        _run(adapter.ensure_token())
        assert adapter._access_token == "new-at"

    def test_ensure_token_loads_from_db(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="db-at", refresh="db-rt"))
        adapter = self._adapter(monkeypatch, db=db)
        _run(adapter.ensure_token())
        assert adapter._access_token == "db-at"

    def test_get_oauth_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://app.hubspot.com/oauth/authorize?")
        assert "state=ws1" in url

    def test_get_oauth_url_missing_client_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter.client_id = None
        with pytest.raises(ValueError):
            _run(adapter.get_oauth_url())

    def test_exchange_code_for_token(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 1800})])
        adapter = self._adapter(monkeypatch, client=client)
        data = _run(adapter.exchange_code_for_token("code"))
        assert data["access_token"] == "at"
        assert adapter._access_token == "at"

    def test_exchange_code_for_token_missing_creds(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter.client_id = None
        with pytest.raises(ValueError):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_code_for_token_http_error(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=401)]))
        adapter = self._adapter(monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.exchange_code_for_token("code"))

    def test_test_connection_no_token_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp({"results": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_search_contacts(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "c1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.search_contacts("jane@x.io")) == [{"id": "c1"}]
        assert client.calls[0][2]["json"]["filterGroups"][0]["filters"][0]["value"] == "jane@x.io"

    def test_search_contacts_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.search_contacts("q"))

    def test_search_contacts_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.search_contacts("q"))

    def test_get_contact(self, monkeypatch):
        client = _Client([_Resp({"id": "c1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_contact("c1")) == {"id": "c1"}

    def test_get_contact_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_contact("c1"))

    def test_get_contact_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_contact("c1"))

    def test_create_contact_full(self, monkeypatch):
        client = _Client([_Resp({"id": "new1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        contact = _run(adapter.create_contact("a@b.io", first_name="A", last_name="B", company="ACME", jobtitle="CEO"))
        assert contact == {"id": "new1"}
        props = client.calls[0][2]["json"]["properties"]
        assert props["email"] == "a@b.io"
        assert props["firstname"] == "A"
        assert props["lastname"] == "B"
        assert props["company"] == "ACME"
        assert props["jobtitle"] == "CEO"

    def test_create_contact_minimal(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_contact("a@b.io"))
        assert client.calls[0][2]["json"]["properties"] == {"email": "a@b.io"}

    def test_create_contact_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_contact("a@b.io"))

    def test_create_contact_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_contact("a@b.io"))

    def test_update_contact(self, monkeypatch):
        client = _Client([_Resp({"id": "c1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.update_contact("c1", {"firstname": "X"})) == {"id": "c1"}
        assert client.calls[0][0] == "patch"

    def test_update_contact_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.update_contact("c1", {"firstname": "X"}))

    def test_update_contact_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.update_contact("c1", {"firstname": "X"}))

    def test_get_deals(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "d1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_deals(limit=5)) == [{"id": "d1"}]
        assert client.calls[0][2]["params"]["limit"] == 5

    def test_get_deals_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_deals())

    def test_get_deals_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_deals())

    def test_create_deal_full(self, monkeypatch):
        client = _Client([_Resp({"id": "d1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        deal = _run(adapter.create_deal("Big", amount=100.0, pipeline="p1", stage="s1", note="n"))
        assert deal == {"id": "d1"}
        props = client.calls[0][2]["json"]["properties"]
        assert props["dealname"] == "Big"
        assert props["amount"] == 100.0
        assert props["pipeline"] == "p1"
        assert props["dealstage"] == "s1"
        assert props["note"] == "n"

    def test_create_deal_minimal(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_deal("Big"))
        props = client.calls[0][2]["json"]["properties"]
        assert props == {"dealname": "Big", "pipeline": "default"}

    def test_create_deal_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_deal("Big"))

    def test_create_deal_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_deal("Big"))

    def test_get_available_schemas(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "s1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_available_schemas()) == [{"id": "s1"}]

    def test_get_available_schemas_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_available_schemas())

    def test_get_available_schemas_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.get_available_schemas()) == []

    def test_fetch_records_standard_entity(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "r1"}], "paging": {}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.fetch_records("contact", limit=50))
        assert result["results"] == [{"id": "r1"}]
        assert client.calls[0][1].endswith("/crm/v3/objects/contacts")
        assert client.calls[0][2]["params"] == {"limit": 50}

    def test_fetch_records_custom_entity_with_after(self, monkeypatch):
        client = _Client([_Resp({"results": [], "paging": {}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.fetch_records("2-12345", after="cursor"))
        assert client.calls[0][1].endswith("/crm/v3/objects/2-12345")
        assert client.calls[0][2]["params"] == {"limit": 100, "after": "cursor"}

    def test_fetch_records_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.fetch_records("contacts"))

    def test_fetch_records_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.fetch_records("contacts")) == {"results": [], "paging": {}}


# ===========================================================================
# Jira
# ===========================================================================
class TestJira:
    JIRA_ENV = {
        "JIRA_SITE_URL": "https://acme.atlassian.net",
        "JIRA_CLIENT_ID": "cid",
        "JIRA_CLIENT_SECRET": "csec",
        "JIRA_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, db=None, site_url=None, use_env=True):
        if use_env:
            for k, v in self.JIRA_ENV.items():
                monkeypatch.setenv(k, v)
        else:
            monkeypatch.delenv("JIRA_SITE_URL", raising=False)
            monkeypatch.delenv("JIRA_CLIENT_ID", raising=False)
            monkeypatch.delenv("JIRA_CLIENT_SECRET", raising=False)
            monkeypatch.delenv("JIRA_REDIRECT_URI", raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return JiraAdapter(db=db, workspace_id="ws1", site_url=site_url)

    def test_init_with_site(self, monkeypatch):
        adapter = self._adapter(monkeypatch, site_url="https://custom.atlassian.net")
        assert adapter.base_url == "https://custom.atlassian.net/rest/api/3"

    def test_init_no_site(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        assert adapter.base_url is None
        assert adapter.site_url is None

    def test_load_token_sets_site_from_instance_url(self, monkeypatch):
        db = _FakeDB(_FakeToken(
            access="plain-at", refresh="plain-rt", expires=datetime.now(timezone.utc),
            instance_url="https://db.atlassian.net",
        ))
        adapter = self._adapter(monkeypatch, db=db, use_env=False)
        _run(adapter._load_token())
        assert adapter._access_token == "plain-at"
        assert adapter.site_url == "https://db.atlassian.net"
        assert adapter.base_url == "https://db.atlassian.net/rest/api/3"

    def test_load_token_no_db(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        _run(adapter._load_token())
        assert adapter._access_token is None

    def test_load_token_token_without_refresh(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="plain-at", refresh=None, instance_url=None))
        adapter = self._adapter(monkeypatch, db=db)
        _run(adapter._load_token())
        assert adapter._access_token == "plain-at"
        assert adapter._refresh_token is None

    def test_refresh_token_no_refresh_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.refresh_token()) is False

    def test_refresh_token_success_no_db(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert adapter._access_token == "new-at"
        assert adapter._refresh_token == "new-rt"

    def test_refresh_token_success_with_db(self, monkeypatch):
        token = _FakeToken(access="at", refresh="rt")
        db = _FakeDB(token)
        client = _Client([_Resp({"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client, db=db)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert db.committed is True
        assert token.access_token != "new-at"
        assert token.refresh_token is not None

    def test_refresh_token_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is False

    def test_ensure_token_expired_refreshes(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "old-at"
        adapter._refresh_token = "rt"
        adapter._token_expires_at = _expired()
        _run(adapter.ensure_token())
        assert adapter._access_token == "new-at"

    def test_ensure_token_without_token_loads_from_db(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="db-at", refresh="db-rt", instance_url="https://db.atlassian.net"))
        adapter = self._adapter(monkeypatch, db=db, use_env=False)
        _run(adapter.ensure_token())
        assert adapter._access_token == "db-at"
        assert adapter.site_url == "https://db.atlassian.net"

    def test_ensure_token_valid_noop(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter._access_token = "at"
        adapter._token_expires_at = _fresh()
        _run(adapter.ensure_token())
        assert adapter._access_token == "at"

    def test_get_oauth_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://acme.atlassian.net/rest/oauth2/latest/authorization?")
        assert "state=ws1" in url

    def test_get_oauth_url_missing_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_oauth_url())

    def test_exchange_code_for_token(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        data = _run(adapter.exchange_code_for_token("code"))
        assert data["access_token"] == "at"
        assert adapter._access_token == "at"
        assert adapter._token_expires_at is not None

    def test_exchange_code_for_token_missing_creds(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_code_for_token_http_error(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=401)]))
        adapter = self._adapter(monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.exchange_code_for_token("code"))

    def test_test_connection_no_config_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp({"accountId": "u1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True
        assert client.calls[0][1].endswith("/myself")

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_search_issues(self, monkeypatch):
        client = _Client([_Resp({"issues": [{"key": "PROJ-1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.search_issues("project = PROJ")) == [{"key": "PROJ-1"}]
        assert client.calls[0][2]["json"]["maxResults"] == 50

    def test_search_issues_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.search_issues("jql"))

    def test_search_issues_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.search_issues("jql"))

    def test_get_issue_success(self, monkeypatch):
        client = _Client([_Resp({"key": "PROJ-1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        issue = _run(adapter.get_issue("PROJ-1"))
        assert issue == {"key": "PROJ-1"}
        assert client.calls[0][2]["headers"]["Authorization"] == "Bearer at"

    def test_get_issue_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_issue("PROJ-1"))

    def test_get_issue_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_issue("PROJ-1"))

    def test_create_issue(self, monkeypatch):
        client = _Client([_Resp({"key": "PROJ-2"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        issue = _run(adapter.create_issue("PROJ", "Sum", "Desc", issue_type="Bug", priority="High"))
        assert issue == {"key": "PROJ-2"}
        fields = client.calls[0][2]["json"]["fields"]
        assert fields["project"] == {"key": "PROJ"}
        assert fields["issuetype"] == {"name": "Bug"}
        assert fields["priority"] == {"name": "High"}

    def test_create_issue_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.create_issue("PROJ", "S", "D"))

    def test_create_issue_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_issue("PROJ", "S", "D"))

    def test_update_issue(self, monkeypatch):
        client = _Client([_Resp({"key": "PROJ-1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.update_issue("PROJ-1", {"fields": {}})) == {"key": "PROJ-1"}
        assert client.calls[0][0] == "put"

    def test_update_issue_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.update_issue("PROJ-1", {}))

    def test_update_issue_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.update_issue("PROJ-1", {}))

    def test_add_comment(self, monkeypatch):
        client = _Client([_Resp({"id": "c1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.add_comment("PROJ-1", "looks good"))
        assert result is None
        sent = client.calls[0][2]["json"]
        assert sent["body"]["content"]["text"] == "looks good"

    def test_add_comment_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.add_comment("PROJ-1", "c"))

    def test_add_comment_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.add_comment("PROJ-1", "c"))

    def test_get_available_schemas(self, monkeypatch):
        client = _Client([_Resp([
            {"key": "PROJ", "name": "Project", "issueTypes": [{"name": "Bug", "id": "1", "description": "d"}]},
            {"key": "KAN", "name": "Kanban", "issueTypes": []},
        ])])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        schemas = _run(adapter.get_available_schemas())
        assert len(schemas) == 1
        assert schemas[0]["project_key"] == "PROJ"
        assert schemas[0]["issue_type"] == "Bug"

    def test_get_available_schemas_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_available_schemas())

    def test_get_available_schemas_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.get_available_schemas()) == []

    def test_fetch_records_success_with_paging(self, monkeypatch):
        client = _Client([_Resp({"issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}], "total": 10})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.fetch_records("PROJ:Bug", limit=2, after="2"))
        assert len(result["results"]) == 2
        assert result["paging"] == {"after": "4"}
        sent = client.calls[0][2]["json"]
        assert sent["jql"] == "project = 'PROJ' AND issuetype = 'Bug' ORDER BY created DESC"
        assert sent["startAt"] == 2

    def test_fetch_records_no_paging_when_done(self, monkeypatch):
        client = _Client([_Resp({"issues": [{"key": "PROJ-1"}], "total": 1})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.fetch_records("PROJ:Bug", after="non-digit"))
        assert result["paging"] == {}
        assert client.calls[0][2]["json"]["startAt"] == 0

    def test_fetch_records_invalid_entity(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter._access_token = "at"
        assert _run(adapter.fetch_records("no-colon")) == {"results": [], "paging": {}}

    def test_fetch_records_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.fetch_records("PROJ:Bug"))

    def test_fetch_records_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.fetch_records("PROJ:Bug")) == {"results": [], "paging": {}}


# ===========================================================================
# Microsoft 365
# ===========================================================================
class TestMicrosoft365:
    M365_ENV = {
        "MICROSOFT_CLIENT_ID": "cid",
        "MICROSOFT_CLIENT_SECRET": "csec",
        "MICROSOFT_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, use_env=True):
        if use_env:
            for k, v in self.M365_ENV.items():
                monkeypatch.setenv(k, v)
        else:
            for k in self.M365_ENV:
                monkeypatch.delenv(k, raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return Microsoft365Adapter(db=None, workspace_id="ws1")

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert adapter.service_name == "microsoft365"
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
        assert adapter._token_expires_at is not None

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
        assert adapter._token_expires_at is not None

    def test_refresh_access_token_no_new_refresh(self, monkeypatch):
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
        client = _Client([_Resp({"id": "u1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_get_emails_with_folder(self, monkeypatch):
        client = _Client([_Resp({"value": [{"id": "m1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_emails(folder_id="f1")) == [{"id": "m1"}]
        assert client.calls[0][1].endswith("/me/mailFolders/f1/messages")

    def test_get_emails_default_inbox(self, monkeypatch):
        client = _Client([_Resp({"value": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_emails()) == []
        assert client.calls[0][1].endswith("/me/mailFolders/Inbox/messages")

    def test_get_emails_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_emails())

    def test_get_emails_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_emails())

    def test_send_email_with_cc_and_attachments(self, monkeypatch):
        client = _Client([_Resp(status=202)])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.send_email(
            ["a@b.io"], "Subj", "<p>body</p>", cc=["c@b.io"],
            attachments=[{"@odata.type": "#microsoft.graph.fileAttachment"}]))
        assert result == {"status": "sent"}
        msg = client.calls[0][2]["json"]["message"]
        assert msg["toRecipients"] == [{"emailAddress": {"address": "a@b.io"}}]
        assert msg["ccRecipients"] == [{"emailAddress": {"address": "c@b.io"}}]
        assert "attachments" in msg

    def test_send_email_minimal(self, monkeypatch):
        client = _Client([_Resp(status=202)])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.send_email(["a@b.io"], "Subj", "body"))
        assert result == {"status": "sent"}
        msg = client.calls[0][2]["json"]["message"]
        assert msg["ccRecipients"] == []
        assert "attachments" not in msg

    def test_send_email_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.send_email(["a@b.io"], "S", "b"))

    def test_send_email_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.send_email(["a@b.io"], "S", "b"))

    def test_get_calendar_events_with_dates(self, monkeypatch):
        client = _Client([_Resp({"value": [{"id": "e1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        events = _run(adapter.get_calendar_events(start_date="2026-01-01", end_date="2026-01-02"))
        assert events == [{"id": "e1"}]
        params = client.calls[0][2]["params"]
        assert params["startDateTime"] == "2026-01-01"
        assert params["endDateTime"] == "2026-01-02"

    def test_get_calendar_events_without_dates(self, monkeypatch):
        client = _Client([_Resp({"value": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_calendar_events()) == []
        assert "startDateTime" not in client.calls[0][2]["params"]

    def test_get_calendar_events_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_calendar_events())

    def test_get_calendar_events_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_calendar_events())

    def test_create_calendar_event_full(self, monkeypatch):
        client = _Client([_Resp({"id": "e1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        event = _run(adapter.create_calendar_event("Meeting", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z",
                                                   body="agenda", attendees=["a@b.io"]))
        assert event == {"id": "e1"}
        sent = client.calls[0][2]["json"]
        assert sent["body"]["content"] == "agenda"
        assert sent["attendees"][0]["emailAddress"]["address"] == "a@b.io"

    def test_create_calendar_event_minimal(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_calendar_event("Meeting", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z"))
        sent = client.calls[0][2]["json"]
        assert "body" not in sent
        assert "attendees" not in sent

    def test_create_calendar_event_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_calendar_event("M", "s", "e"))

    def test_create_calendar_event_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_calendar_event("M", "s", "e"))

    def test_get_tasks_with_list(self, monkeypatch):
        client = _Client([_Resp({"value": [{"id": "t1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_tasks(list_id="L1")) == [{"id": "t1"}]
        assert client.calls[0][1].endswith("/me/todo/lists/L1/tasks")

    def test_get_tasks_default(self, monkeypatch):
        client = _Client([_Resp({"value": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_tasks()) == []
        assert client.calls[0][1].endswith("/me/todo/tasks")

    def test_get_tasks_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_tasks())

    def test_get_tasks_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_tasks())

    def test_create_task_full(self, monkeypatch):
        client = _Client([_Resp({"id": "t1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        task = _run(adapter.create_task("Title", body="desc", due_date="2026-01-01T10:00:00Z", list_id="L1"))
        assert task == {"id": "t1"}
        sent = client.calls[0][2]["json"]
        assert sent["body"] == {"content": "desc", "contentType": "text"}
        assert sent["dueDateTime"] == {"dateTime": "2026-01-01T10:00:00Z", "timeZone": "UTC"}
        assert client.calls[0][1].endswith("/me/todo/lists/L1/tasks")

    def test_create_task_minimal(self, monkeypatch):
        client = _Client([_Resp({})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        _run(adapter.create_task("Title"))
        sent = client.calls[0][2]["json"]
        assert sent == {"title": "Title"}
        assert client.calls[0][1].endswith("/me/todo/tasks")

    def test_create_task_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.create_task("Title"))

    def test_create_task_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_task("Title"))

    def test_get_teams_chats(self, monkeypatch):
        client = _Client([_Resp({"value": [{"id": "c1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_teams_chats()) == [{"id": "c1"}]
        assert client.calls[0][2]["params"] == {"$top": 20}

    def test_get_teams_chats_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_teams_chats())

    def test_get_teams_chats_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_teams_chats())
