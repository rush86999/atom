# -*- coding: utf-8 -*-
"""W85A — coverage push: core/integrations/adapters/airtable, apollo, clickup, confluence.

EXTENDS test_covpush_acctrio.py (airtable 99% — closes line 475) and adds
full suites for apollo (0%) and clickup (0%) and confluence (0%).

Style: mocked httpx.AsyncClient (fake async client + fake responses), zero
network, zero LLM spend, no real DB. Env vars via monkeypatch.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from core.integrations.adapters.airtable import AirtableAdapter
from core.integrations.adapters.apollo import ApolloAdapter
from core.integrations.adapters.clickup import ClickUpAdapter
from core.integrations.adapters.confluence import ConfluenceAdapter


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# Shared fakes
# ===========================================================================
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
    """Async-context httpx client; responds from a per-call queue or a callable."""

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
# Airtable (EXTENDS acctrio — closes line 475 + refresh-db + PAT fallback)
# ===========================================================================
class TestAirtableExtend:
    def _adapter(self, monkeypatch, client=None, db=None, env=None):
        defaults = {
            "AIRTABLE_CLIENT_ID": "cid",
            "AIRTABLE_CLIENT_SECRET": "csec",
            "AIRTABLE_REDIRECT_URI": "https://app/cb",
            "AIRTABLE_PAT": "",
        }
        for k, v in defaults.items():
            monkeypatch.setenv(k, v)
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, v)
        if client is not None:
            _use_client(monkeypatch, client)
        return AirtableAdapter(db=db, workspace_id="ws1")

    def test_delete_record_no_token_raises(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.delete_record("b1", "t1", "r1"))

    def test_delete_record_success(self, monkeypatch):
        client = _Client([_Resp({"deleted": True})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.delete_record("b1", "t1", "r1")) is True
        assert client.calls[0][0] == "delete"

    def test_delete_record_failure_returns_false(self, monkeypatch):
        client = _Client([_Resp(status=500)])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.delete_record("b1", "t1", "r1")) is False

    def test_refresh_token_persists_to_db(self, monkeypatch):
        token = _FakeToken(access="plain-at", refresh="plain-rt")
        db = _FakeDB(token)
        client = _Client([_Resp({"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client, db=db)
        adapter._refresh_token = "plain-rt"
        assert _run(adapter.refresh_token()) is True
        assert db.committed is True
        assert token.access_token != "new-at"  # encrypted at rest
        assert token.refresh_token is not None
        assert token.expires_at is not None

    def test_refresh_token_db_row_without_refresh(self, monkeypatch):
        db = _FakeDB(_FakeToken(access="at", refresh="rt"))
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 60})])
        adapter = self._adapter(monkeypatch, client=client, db=db)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert token_is_none_or_encrypted(db.token.refresh_token)

    def test_refresh_token_exception_returns_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("net down")

        client = _Client(responder=boom)
        adapter = self._adapter(monkeypatch, client=client)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is False

    def test_ensure_token_pat_fallback(self, monkeypatch):
        adapter = self._adapter(monkeypatch, env={"AIRTABLE_PAT": "pat-key"})
        _run(adapter.ensure_token())
        assert adapter._access_token == "pat-key"

    def test_ensure_token_expired_triggers_refresh(self, monkeypatch):
        client = _Client([_Resp({"access_token": "new-at", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "old-at"
        adapter._refresh_token = "rt"
        adapter._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        _run(adapter.ensure_token())
        assert adapter._access_token == "new-at"

    def test_ensure_token_valid_noop(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter._access_token = "at"
        adapter._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
        _run(adapter.ensure_token())
        assert adapter._access_token == "at"

    def test_ensure_token_loads_from_db(self, monkeypatch):
        adapter = self._adapter(monkeypatch, db=_FakeDB(_FakeToken(access="db-at", refresh="db-rt")))
        _run(adapter.ensure_token())
        assert adapter._access_token == "db-at"

    def test_exchange_code_http_error_reraised(self, monkeypatch):
        client = _Client([_Resp(status=401)])
        adapter = self._adapter(monkeypatch, client=client)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_code_missing_creds(self, monkeypatch):
        adapter = self._adapter(monkeypatch, env={"AIRTABLE_CLIENT_ID": ""})
        adapter.client_id = None
        with pytest.raises(ValueError):
            _run(adapter.exchange_code_for_token("code"))

    def test_get_available_schemas_skips_failing_base(self, monkeypatch):
        def responder(method, url, **kw):
            if url.endswith("/meta/bases"):
                return _Resp({"bases": [{"id": "b1", "name": "Base1"}, {"id": "b2", "name": "Base2"}]})
            if "tables" in url and "/b1/" in url:
                return _Resp(status=403)
            return _Resp({"tables": [{"id": "t2", "name": "Table2"}]})

        client = _Client(responder=responder)
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        schemas = _run(adapter.get_available_schemas())
        assert len(schemas) == 1
        assert schemas[0]["base_id"] == "b2"

    def test_fetch_records_invalid_entity_type(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        adapter._access_token = "at"
        assert _run(adapter.fetch_records("not-a-composite")) == {"results": [], "paging": {}}

    def test_fetch_records_success_with_offset(self, monkeypatch):
        client = _Client([_Resp({"records": [{"id": "r1"}], "offset": "next"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.fetch_records("b1:t1", limit=50, after="cursor"))
        assert result["results"] == [{"id": "r1"}]
        assert result["paging"] == {"after": "next"}
        assert client.calls[0][2]["params"] == {"maxRecords": 50, "offset": "cursor"}

    def test_fetch_records_no_offset(self, monkeypatch):
        client = _Client([_Resp({"records": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        result = _run(adapter.fetch_records("b1:t1"))
        assert result["paging"] == {}

    def test_fetch_records_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.fetch_records("b1:t1")) == {"results": [], "paging": {}}

    def test_search_records_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.search_records("b1", "t1", "field", "val"))

    def test_test_connection_pat_token(self, monkeypatch):
        client = _Client([_Resp({"id": "u1"})])
        adapter = self._adapter(monkeypatch, client=client, env={"AIRTABLE_PAT": "pat"})
        assert _run(adapter.test_connection()) is True
        assert client.calls[0][1] == "https://api.airtable.com/v0/meta/whoami"


def token_is_none_or_encrypted(v):
    return v is None or (isinstance(v, str) and v.startswith("gAAAA"))


# ===========================================================================
# Apollo
# ===========================================================================
class TestApollo:
    def _adapter(self, monkeypatch, api_key="key-1"):
        if api_key is None:
            monkeypatch.delenv("APOLLO_API_KEY", raising=False)
        else:
            monkeypatch.setenv("APOLLO_API_KEY", api_key)
        return ApolloAdapter()

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch, api_key="env-key")
        assert adapter.service_name == "apollo"
        assert adapter._api_key == "env-key"
        assert adapter.base_url == "https://api.apollo.io/v1"
        assert adapter.workspace_id is None

    def test_init_no_env_key(self, monkeypatch):
        adapter = self._adapter(monkeypatch, api_key=None)
        assert adapter._api_key is None

    def test_test_connection_no_key_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch, api_key=None)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp(status=200)])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is True
        assert client.calls[0][2]["params"] == {"api_key": "key-1"}

    def test_test_connection_non_200_false(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=500)]))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        _use_client(monkeypatch, _Client(responder=boom))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_get_data_no_key_raises(self, monkeypatch):
        adapter = self._adapter(monkeypatch, api_key=None)
        with pytest.raises(ValueError):
            _run(adapter.get_data("people"))

    def test_get_data_people(self, monkeypatch):
        client = _Client([_Resp({"people": [{"id": "p1"}]})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        result = _run(adapter.get_data("people", query="john"))
        assert result == {"ok": True, "data": [{"id": "p1"}]}
        method, url, kw = client.calls[0]
        assert method == "post" and url.endswith("/mixed_people/search")
        assert kw["json"] == {"q_description": "john"}
        assert kw["params"] == {"api_key": "key-1"}

    def test_get_data_search_alias_with_kwargs_description(self, monkeypatch):
        client = _Client([_Resp({"people": []})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        result = _run(adapter.get_data("search", q_description="desc"))
        assert result == {"ok": True, "data": []}
        assert client.calls[0][2]["json"] == {"q_description": "desc"}

    def test_get_data_people_http_error(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=500)]))
        adapter = self._adapter(monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.get_data("people", query="q"))

    def test_get_data_enrichment(self, monkeypatch):
        client = _Client([_Resp({"person": {"id": "p1", "name": "Jane"}})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        result = _run(adapter.get_data("enrichment", query="jane@x.io"))
        assert result == {"ok": True, "data": {"id": "p1", "name": "Jane"}}
        method, url, kw = client.calls[0]
        assert method == "get" and url.endswith("/people/match")
        assert kw["params"] == {"api_key": "key-1", "email": "jane@x.io"}

    def test_get_data_enrichment_email_from_kwargs(self, monkeypatch):
        client = _Client([_Resp({"person": {}})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        result = _run(adapter.get_data("enrichment", email="kw@x.io"))
        assert result == {"ok": True, "data": {}}

    def test_get_data_enrichment_no_email_raises(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_data("enrichment"))

    def test_get_data_unsupported_type(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_data("bogus"))

    def test_search_people_delegates(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp({"people": [{"id": "p1"}]})]))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.search_people("john")) == [{"id": "p1"}]

    def test_enrich_person_delegates(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp({"person": {"id": "p1"}})]))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.enrich_person("jane@x.io")) == {"id": "p1"}


# ===========================================================================
# ClickUp
# ===========================================================================
class TestClickUp:
    def _adapter(self, monkeypatch, token="tok-1"):
        monkeypatch.setenv("CLICKUP_CLIENT_ID", "cid")
        monkeypatch.setenv("CLICKUP_CLIENT_SECRET", "csec")
        if token is None:
            monkeypatch.delenv("CLICKUP_ACCESS_TOKEN", raising=False)
        else:
            monkeypatch.setenv("CLICKUP_ACCESS_TOKEN", token)
        return ClickUpAdapter()

    def test_init(self, monkeypatch):
        adapter = self._adapter(monkeypatch, token="env-tok")
        assert adapter.service_name == "clickup"
        assert adapter.client_id == "cid"
        assert adapter._access_token == "env-tok"
        assert adapter.base_url == "https://api.clickup.com/api/v2"

    def test_test_connection_no_token_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch, token=None)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp(status=200)])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is True
        assert client.calls[0][1].endswith("/user")
        assert client.calls[0][2]["headers"] == {"Authorization": "tok-1"}

    def test_test_connection_non_200_false(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=401)]))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        _use_client(monkeypatch, _Client(responder=boom))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_get_data_no_token_raises(self, monkeypatch):
        adapter = self._adapter(monkeypatch, token=None)
        with pytest.raises(ValueError):
            _run(adapter.get_data("teams"))

    def test_get_data_teams(self, monkeypatch):
        client = _Client([_Resp({"teams": [{"id": "t1"}]})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.get_data("teams")) == {"ok": True, "data": [{"id": "t1"}]}
        assert client.calls[0][1].endswith("/team")

    def test_get_data_spaces(self, monkeypatch):
        client = _Client([_Resp({"spaces": [{"id": "s1"}]})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.get_data("spaces", query="team-9")) == {"ok": True, "data": [{"id": "s1"}]}
        assert client.calls[0][1].endswith("/team/team-9/space")

    def test_get_data_spaces_team_id_kwarg(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp({"spaces": []})]))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.get_data("spaces", team_id="team-2")) == {"ok": True, "data": []}

    def test_get_data_spaces_missing_team_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_data("spaces"))

    def test_get_data_tasks(self, monkeypatch):
        client = _Client([_Resp({"tasks": [{"id": "task-1"}]})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.get_data("tasks", query="list-4")) == {"ok": True, "data": [{"id": "task-1"}]}
        assert client.calls[0][1].endswith("/list/list-4/task")

    def test_get_data_tasks_list_id_kwarg(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp({"tasks": []})]))
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.get_data("tasks", list_id="list-8")) == {"ok": True, "data": []}

    def test_get_data_tasks_missing_list_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_data("tasks"))

    def test_get_data_user(self, monkeypatch):
        client = _Client([_Resp({"user": {"id": "u1"}})])
        _use_client(monkeypatch, client)
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.get_data("user")) == {"ok": True, "data": {"id": "u1"}}
        assert client.calls[0][1].endswith("/user")

    def test_get_data_unsupported(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        with pytest.raises(ValueError):
            _run(adapter.get_data("bogus"))

    def test_get_data_http_error_propagates(self, monkeypatch):
        _use_client(monkeypatch, _Client([_Resp(status=403)]))
        adapter = self._adapter(monkeypatch)
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.get_data("teams"))


# ===========================================================================
# Confluence
# ===========================================================================
class TestConfluence:
    CONFLUENCE_ENV = {
        "CONFLUENCE_SITE_URL": "https://acme.atlassian.net",
        "CONFLUENCE_CLIENT_ID": "cid",
        "CONFLUENCE_CLIENT_SECRET": "csec",
        "CONFLUENCE_REDIRECT_URI": "https://app/cb",
    }

    def _adapter(self, monkeypatch, client=None, env=None, use_env=True):
        if use_env:
            for k, v in self.CONFLUENCE_ENV.items():
                monkeypatch.setenv(k, v)
            for k, v in (env or {}).items():
                monkeypatch.setenv(k, v)
        else:
            monkeypatch.delenv("CONFLUENCE_SITE_URL", raising=False)
            monkeypatch.delenv("CONFLUENCE_CLIENT_ID", raising=False)
            monkeypatch.delenv("CONFLUENCE_CLIENT_SECRET", raising=False)
            monkeypatch.delenv("CONFLUENCE_REDIRECT_URI", raising=False)
        if client is not None:
            _use_client(monkeypatch, client)
        return ConfluenceAdapter(db=None, workspace_id="ws1")

    def test_init_no_site_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        assert adapter.base_url is None
        assert adapter.client_id is None

    def test_get_oauth_url(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://acme.atlassian.net/wiki/rest/oauth2/latest/authorization?")
        assert "client_id=cid" in url
        assert "state=ws1" in url

    def test_get_oauth_url_missing_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_oauth_url())

    def test_exchange_code_for_token(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        token_data = _run(adapter.exchange_code_for_token("code-1"))
        assert token_data["access_token"] == "at"
        assert adapter._access_token == "at"
        assert adapter._token_expires_at is not None
        assert client.calls[0][2]["data"]["grant_type"] == "authorization_code"

    def test_exchange_code_for_token_no_expiry(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at"})])
        adapter = self._adapter(monkeypatch, client=client)
        token_data = _run(adapter.exchange_code_for_token("code-1"))
        assert token_data == {"access_token": "at"}
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

    def test_test_connection_no_config_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_no_token_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_success(self, monkeypatch):
        client = _Client([_Resp({"accountId": "u1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True
        assert client.calls[0][1].endswith("/user/current")

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is False

    def test_search_content_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.search_content("query"))

    def test_search_content_with_space(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "c1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        results = _run(adapter.search_content("hello", limit=5, space_key="KB"))
        assert results == [{"id": "c1"}]
        method, url, kw = client.calls[0]
        assert method == "get" and url.endswith("/content/search")
        assert "space.key = 'KB'" in kw["params"]["cql"]
        assert kw["params"]["limit"] == 5

    def test_search_content_without_space(self, monkeypatch):
        client = _Client([_Resp({"results": []})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        results = _run(adapter.search_content("hello", type="blogpost"))
        assert results == []
        assert "space.key" not in client.calls[0][2]["params"]["cql"]

    def test_search_content_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.search_content("q"))

    def test_get_page(self, monkeypatch):
        client = _Client([_Resp({"id": "p1", "title": "T"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        page = _run(adapter.get_page("p1"))
        assert page["id"] == "p1"
        assert client.calls[0][2]["params"] == {"expand": "body.storage,version,space"}

    def test_get_page_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_page("p1"))

    def test_get_page_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_page("p1"))

    def test_create_page_with_parent(self, monkeypatch):
        client = _Client([_Resp({"id": "new-page"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        page = _run(adapter.create_page("KB", "Title", "<p>body</p>", parent_id="par-1"))
        assert page["id"] == "new-page"
        body = client.calls[0][2]["json"]
        assert body["space"] == {"key": "KB"}
        assert body["ancestors"] == [{"id": "par-1"}]

    def test_create_page_without_parent(self, monkeypatch):
        client = _Client([_Resp({"id": "new-page"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        page = _run(adapter.create_page("KB", "Title", "<p>body</p>"))
        assert page["id"] == "new-page"
        assert "ancestors" not in client.calls[0][2]["json"]

    def test_create_page_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.create_page("KB", "T", "c"))

    def test_create_page_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.create_page("KB", "T", "c"))

    def test_update_page_with_version(self, monkeypatch):
        client = _Client([_Resp({"id": "p1", "version": {"number": 4}})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        page = _run(adapter.update_page("p1", title="New", content="body", version=4))
        assert page["version"] == {"number": 4}
        sent = client.calls[0][2]["json"]
        assert sent["version"] == {"number": 4}
        assert sent["title"] == "New"
        assert sent["body"]["storage"]["value"] == "body"

    def test_update_page_without_version_fetches_current(self, monkeypatch):
        client = _Client([_Resp({"version": {"number": 3}}), _Resp({"id": "p1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        page = _run(adapter.update_page("p1"))
        assert len(client.calls) == 2
        assert client.calls[0][0] == "get"
        assert client.calls[1][0] == "put"
        assert client.calls[1][2]["json"]["version"] == {"number": 4}
        assert "title" not in client.calls[1][2]["json"]
        assert "body" not in client.calls[1][2]["json"]
        assert page["id"] == "p1"

    def test_update_page_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.update_page("p1"))

    def test_update_page_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.update_page("p1", version=2))

    def test_delete_page_success(self, monkeypatch):
        client = _Client([_Resp(status=204)])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.delete_page("p1")) is True
        assert client.calls[0][0] == "delete"

    def test_delete_page_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.delete_page("p1"))

    def test_delete_page_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        assert _run(adapter.delete_page("p1")) is False

    def test_get_spaces(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "sp1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_spaces()) == [{"id": "sp1"}]
        assert client.calls[0][2]["params"]["limit"] == 25

    def test_get_spaces_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_spaces())

    def test_get_spaces_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_spaces())

    def test_add_comment(self, monkeypatch):
        client = _Client([_Resp({"id": "cm1"})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        comment = _run(adapter.add_comment("p1", "nice"))
        assert comment == {"id": "cm1"}
        assert client.calls[0][1].endswith("/content/p1/child/comment")

    def test_add_comment_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.add_comment("p1", "nice"))

    def test_add_comment_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.add_comment("p1", "nice"))

    def test_get_attachments(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "a1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_attachments("p1")) == [{"id": "a1"}]

    def test_get_attachments_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_attachments("p1"))

    def test_get_attachments_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_attachments("p1"))

    def test_get_page_children(self, monkeypatch):
        client = _Client([_Resp({"results": [{"id": "c1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        adapter._access_token = "at"
        assert _run(adapter.get_page_children("p1")) == [{"id": "c1"}]
        assert client.calls[0][1].endswith("/content/p1/child/page")

    def test_get_page_children_no_config(self, monkeypatch):
        adapter = self._adapter(monkeypatch, use_env=False)
        with pytest.raises(ValueError):
            _run(adapter.get_page_children("p1"))

    def test_get_page_children_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        adapter._access_token = "at"
        with pytest.raises(OSError):
            _run(adapter.get_page_children("p1"))


# ===========================================================================
# Airtable full-surface (standalone >=95% without test_covpush_acctrio.py)
# ===========================================================================
class TestAirtableFull:
    """Re-derives full AirtableAdapter coverage standalone (acctrio covers the
    same lines in a partner suite; this class keeps w85a self-sufficient)."""

    def _adapter(self, monkeypatch, client=None, db=None, pat="pat-key", env=None):
        defaults = {
            "AIRTABLE_CLIENT_ID": "cid",
            "AIRTABLE_CLIENT_SECRET": "csec",
            "AIRTABLE_REDIRECT_URI": "https://app/cb",
        }
        if pat is None:
            monkeypatch.delenv("AIRTABLE_PAT", raising=False)
        else:
            defaults["AIRTABLE_PAT"] = pat
        for k, v in defaults.items():
            monkeypatch.setenv(k, v)
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, v)
        if client is not None:
            _use_client(monkeypatch, client)
        return AirtableAdapter(db=db, workspace_id="ws1")

    def test_refresh_token_without_refresh_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        assert _run(adapter.refresh_token()) is False

    def test_get_oauth_url_missing_client_id(self, monkeypatch):
        adapter = self._adapter(monkeypatch, env={"AIRTABLE_CLIENT_ID": ""})
        adapter.client_id = None
        with pytest.raises(ValueError):
            _run(adapter.get_oauth_url())

    def test_get_oauth_url_success(self, monkeypatch):
        adapter = self._adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert url.startswith("https://airtable.com/oauth2/v1/authorize?")
        assert "state=ws1" in url

    def test_exchange_code_for_token_success(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})])
        adapter = self._adapter(monkeypatch, client=client)
        data = _run(adapter.exchange_code_for_token("code"))
        assert data["access_token"] == "at"
        assert adapter._access_token == "at"
        assert adapter._token_expires_at is not None

    def test_exchange_code_for_token_no_expiry(self, monkeypatch):
        client = _Client([_Resp({"access_token": "at"})])
        adapter = self._adapter(monkeypatch, client=client)
        data = _run(adapter.exchange_code_for_token("code"))
        assert data == {"access_token": "at"}
        assert adapter._token_expires_at is None

    def test_test_connection_no_token_false(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        assert _run(adapter.test_connection()) is False

    def test_test_connection_exception_false(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.test_connection()) is False

    def test_list_bases_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        with pytest.raises(ValueError):
            _run(adapter.list_bases())

    def test_list_bases_success(self, monkeypatch):
        client = _Client([_Resp({"bases": [{"id": "b1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        assert _run(adapter.list_bases()) == [{"id": "b1"}]

    def test_list_bases_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        with pytest.raises(OSError):
            _run(adapter.list_bases())

    def test_list_tables_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        with pytest.raises(ValueError):
            _run(adapter.list_tables("b1"))

    def test_list_tables_success(self, monkeypatch):
        client = _Client([_Resp({"tables": [{"id": "t1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        assert _run(adapter.list_tables("b1")) == [{"id": "t1"}]
        assert client.calls[0][1] == "https://api.airtable.com/v0/meta/bases/b1/tables"

    def test_list_tables_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        with pytest.raises(OSError):
            _run(adapter.list_tables("b1"))

    def test_get_records_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        with pytest.raises(ValueError):
            _run(adapter.get_records("b1", "t1"))

    def test_get_records_with_filters(self, monkeypatch):
        client = _Client([_Resp({"records": [{"id": "r1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        records = _run(adapter.get_records(
            "b1", "t1", filter_by_formula="status='Done'",
            sort=[{"field": "Name", "direction": "desc"}, {"field": "Age"}],
            max_records=10))
        assert records == [{"id": "r1"}]
        params = client.calls[0][2]["params"]
        assert params["max_records"] == 10
        assert params["filter_by_formula"] == "status='Done'"
        assert params["sort[]"] == ["Name:desc", "Age:asc"]

    def test_get_records_plain(self, monkeypatch):
        client = _Client([_Resp({"records": []})])
        adapter = self._adapter(monkeypatch, client=client)
        assert _run(adapter.get_records("b1", "t1")) == []
        assert client.calls[0][2]["params"] == {"max_records": 100}

    def test_get_records_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        with pytest.raises(OSError):
            _run(adapter.get_records("b1", "t1"))

    def test_get_record_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        with pytest.raises(ValueError):
            _run(adapter.get_record("b1", "t1", "r1"))

    def test_get_record_success(self, monkeypatch):
        client = _Client([_Resp({"id": "r1", "fields": {}})])
        adapter = self._adapter(monkeypatch, client=client)
        assert _run(adapter.get_record("b1", "t1", "r1")) == {"id": "r1", "fields": {}}

    def test_get_record_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        with pytest.raises(OSError):
            _run(adapter.get_record("b1", "t1", "r1"))

    def test_create_record_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        with pytest.raises(ValueError):
            _run(adapter.create_record("b1", "t1", {"Name": "X"}))

    def test_create_record_success(self, monkeypatch):
        client = _Client([_Resp({"records": [{"id": "r-new", "fields": {"Name": "X"}}]})])
        adapter = self._adapter(monkeypatch, client=client)
        record = _run(adapter.create_record("b1", "t1", {"Name": "X"}))
        assert record["id"] == "r-new"
        assert client.calls[0][2]["json"]["records"][0]["fields"] == {"Name": "X"}

    def test_create_record_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        with pytest.raises(OSError):
            _run(adapter.create_record("b1", "t1", {"Name": "X"}))

    def test_update_record_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        with pytest.raises(ValueError):
            _run(adapter.update_record("b1", "t1", "r1", {"Name": "Y"}))

    def test_update_record_success(self, monkeypatch):
        client = _Client([_Resp({"id": "r1", "fields": {"Name": "Y"}})])
        adapter = self._adapter(monkeypatch, client=client)
        record = _run(adapter.update_record("b1", "t1", "r1", {"Name": "Y"}))
        assert record["fields"] == {"Name": "Y"}
        assert client.calls[0][0] == "patch"

    def test_update_record_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        with pytest.raises(OSError):
            _run(adapter.update_record("b1", "t1", "r1", {"Name": "Y"}))

    def test_search_records_success(self, monkeypatch):
        client = _Client([_Resp({"records": [{"id": "r1"}]})])
        adapter = self._adapter(monkeypatch, client=client)
        records = _run(adapter.search_records("b1", "t1", "Name", "jane", max_records=5))
        assert records == [{"id": "r1"}]
        params = client.calls[0][2]["params"]
        assert params["filter_by_formula"] == "FIND('jane', LOWER({Name})) > 0"
        assert params["max_records"] == 5

    def test_search_records_exception(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        with pytest.raises(OSError):
            _run(adapter.search_records("b1", "t1", "Name", "jane"))

    def test_get_available_schemas_outer_exception_empty(self, monkeypatch):
        def boom(method, url, **kw):
            raise OSError("down")

        adapter = self._adapter(monkeypatch, client=_Client(responder=boom))
        assert _run(adapter.get_available_schemas()) == []

    def test_fetch_records_no_token(self, monkeypatch):
        adapter = self._adapter(monkeypatch, pat=None)
        with pytest.raises(ValueError):
            _run(adapter.fetch_records("b1:t1"))
