"""Coverage-push + bug-hunt: airtable adapter + ai accounting engine + mini_app_service.

Owned modules (may fix): core/integrations/adapters/airtable.py,
core/ai_accounting_engine.py. Read-only (report-only): core/mini_app_service.py.

Bugs hunted here (red tests first, then minimal fixes):
  * airtable.search_records builds a filter formula but never calls the API —
    it always returns None (a search that cannot search).
  * airtable.test_connection builds ``base_url + "/v0/meta/whoami"`` where
    base_url already ends in ``/v0`` — the whoami probe always 404s.
  * airtable.exchange_code_for_token stores a NAIVE ``datetime.now()``
    expiry; ensure_token compares against ``datetime.now(timezone.utc)`` —
    offset-naive vs offset-aware comparison raises TypeError, crashing every
    post-exchange token check.
  * ai_accounting_engine: transactions ingested with a float amount crash
    export_trial_balance_json (Decimal + float TypeError).
  * ai_accounting_engine.run_scenario takes the FIRST digit run in the
    description ("hire 2 engineers at $50,000" → impact -2) instead of the
    dollar amount (→ -50000).

mini_app_service is read-only here; uncovered branches are exercised and any
observations are reported in the final summary, never edited.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from core.integrations.adapters.airtable import AirtableAdapter

from core.ai_accounting_engine import (
    AIAccountingEngine,
    Transaction,
    TransactionStatus,
    TransactionSource,
)


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# Airtable adapter — fake httpx transport
# ===========================================================================
class _FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, respond=None):
        self.calls = []
        self._respond = respond or (lambda *a, **k: _FakeResponse())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _record(self, method, url, **kw):
        self.calls.append((method, url, kw))

    async def get(self, url, headers=None, params=None):
        self._record("get", url, headers=headers, params=params)
        return self._respond("get", url, headers=headers, params=params)

    async def post(self, url, data=None, json=None, headers=None):
        self._record("post", url, headers=headers, data=data, json=json)
        return self._respond("post", url, headers=headers, data=data, json=json)

    async def patch(self, url, headers=None, json=None):
        self._record("patch", url, headers=headers, json=json)
        return self._respond("patch", url, headers=headers, json=json)

    async def delete(self, url, headers=None):
        self._record("delete", url, headers=headers)
        return self._respond("delete", url, headers=headers)


class _FakeToken:
    def __init__(self, access="at", refresh="rt", expires=None):
        self.access_token = access
        self.refresh_token = refresh
        self.expires_at = expires


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

    def query(self, model):
        return _FakeQuery(self.token)

    def commit(self):
        self.committed = True


def _adapter(monkeypatch, client=None, db=None, env=None):
    env = dict(env or {})
    env.setdefault("AIRTABLE_CLIENT_ID", "cid")
    env.setdefault("AIRTABLE_CLIENT_SECRET", "csec")
    env.setdefault("AIRTABLE_REDIRECT_URI", "https://app/cb")
    env.setdefault("AIRTABLE_PAT", "")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    if client is not None:
        monkeypatch.setattr(httpx, "AsyncClient", lambda: client)
    return AirtableAdapter(db=db, workspace_id="ws1")


def _records_client(payload=None):
    def respond(method, url, **kw):
        if method == "get":
            return _FakeResponse(payload if payload is not None else {"records": [{"id": "rec1", "fields": {}}]})
        if method == "post":
            return _FakeResponse({"records": [{"id": "rec-new", "fields": {}}]})
        if method == "patch":
            return _FakeResponse({"id": "rec1", "fields": {}})
        return _FakeResponse({"deleted": True})

    return _FakeClient(respond)


def _token_client(token_data):
    def respond(method, url, **kw):
        assert method == "post" and "oauth2/v1/token" in url
        return _FakeResponse(token_data)

    return _FakeClient(respond)


class TestAirtableInitAndTokens:
    def test_init_reads_env(self, monkeypatch):
        adapter = _adapter(monkeypatch)
        assert adapter.client_id == "cid"
        assert adapter.client_secret == "csec"
        assert adapter.redirect_uri == "https://app/cb"
        assert adapter.personal_access_token == ""
        assert adapter.service_name == "airtable"
        assert adapter.base_url == "https://api.airtable.com/v0"

    def test_load_token_no_db_is_noop(self, monkeypatch):
        adapter = _adapter(monkeypatch)
        fresh = AirtableAdapter(db=None, workspace_id="ws1")
        # db=None path must return immediately without touching tokens
        _run(fresh._load_token())
        assert fresh._access_token is None

    def test_load_token_reads_db_row(self, monkeypatch):
        adapter = _adapter(monkeypatch, db=_FakeDB(_FakeToken(
            access="plain-at", refresh="plain-rt", expires=datetime.now(timezone.utc),
        )))
        _run(adapter._load_token())
        assert adapter._access_token == "plain-at"
        assert adapter._refresh_token == "plain-rt"

    def test_refresh_token_no_refresh_returns_false(self, monkeypatch):
        adapter = _adapter(monkeypatch)
        assert _run(adapter.refresh_token()) is False

    def test_refresh_token_success_no_db(self, monkeypatch):
        client = _token_client({"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600})
        adapter = _adapter(monkeypatch, client=client)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert adapter._access_token == "new-at"
        assert adapter._refresh_token == "new-rt"
        assert adapter._token_expires_at.tzinfo is not None

    def test_refresh_token_updates_db(self, monkeypatch):
        import core.privsec.token_encryption as te

        monkeypatch.setattr(te, "encrypt_token", lambda v: f"enc:{v}")
        monkeypatch.setattr(te, "stamp_credential_metadata", lambda r: None)
        db = _FakeDB(_FakeToken())
        client = _token_client({"access_token": "db-at", "refresh_token": "db-rt", "expires_in": 300})
        adapter = _adapter(monkeypatch, client=client, db=db)
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is True
        assert db.token.access_token == "enc:db-at"
        assert db.token.refresh_token == "enc:db-rt"
        assert db.committed is True

    def test_refresh_token_failure_returns_false(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=400)

        adapter = _adapter(monkeypatch, client=_FakeClient(respond))
        adapter._refresh_token = "rt"
        assert _run(adapter.refresh_token()) is False

    def test_ensure_token_loads_missing(self, monkeypatch):
        adapter = _adapter(monkeypatch, db=_FakeDB(_FakeToken(access="from-db")))
        _run(adapter.ensure_token())
        assert adapter._access_token == "from-db"

    def test_ensure_token_expired_refreshes(self, monkeypatch):
        client = _token_client({"access_token": "fresh", "refresh_token": "rt2", "expires_in": 3600})
        adapter = _adapter(monkeypatch, client=client)
        adapter._access_token = "stale"
        adapter._refresh_token = "rt"
        adapter._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        _run(adapter.ensure_token())
        assert adapter._access_token == "fresh"

    def test_ensure_token_pat_fallback(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": "pat-tok"})
        _run(adapter.ensure_token())
        assert adapter._access_token == "pat-tok"


class TestAirtableOAuth:
    def test_get_oauth_url_missing_client_id(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_CLIENT_ID": "", "AIRTABLE_CLIENT_SECRET": ""})
        with pytest.raises(ValueError, match="AIRTABLE_CLIENT_ID"):
            _run(adapter.get_oauth_url())

    def test_get_oauth_url_builds_auth_url(self, monkeypatch):
        adapter = _adapter(monkeypatch)
        url = _run(adapter.get_oauth_url())
        assert "airtable.com/oauth2/v1/authorize" in url
        assert "client_id=cid" in url
        assert "redirect_uri=https%3A%2F%2Fapp%2Fcb" in url
        assert "state=ws1" in url
        assert "data.records%3Aread" in url

    def test_exchange_code_missing_credentials(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_CLIENT_ID": "", "AIRTABLE_CLIENT_SECRET": ""})
        with pytest.raises(ValueError, match="credentials"):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_code_success(self, monkeypatch):
        client = _token_client({"access_token": "ex-at", "refresh_token": "ex-rt", "expires_in": 3600})
        adapter = _adapter(monkeypatch, client=client)
        token_data = _run(adapter.exchange_code_for_token("the-code"))
        assert token_data["access_token"] == "ex-at"
        assert adapter._access_token == "ex-at"
        method, url, kw = client.calls[0]
        assert method == "post" and "oauth2/v1/token" in url
        assert kw["data"]["code"] == "the-code"

    def test_exchange_code_http_error_reraises(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        adapter = _adapter(monkeypatch, client=_FakeClient(respond))
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.exchange_code_for_token("code"))

    def test_exchange_then_ensure_token_no_crash(self, monkeypatch):
        """BUG (HIGH): exchange stored a naive datetime; ensure_token compares
        against timezone-aware now -> TypeError on every post-exchange check."""
        client = _token_client({"access_token": "ex-at", "refresh_token": "ex-rt", "expires_in": 100})
        adapter = _adapter(monkeypatch, client=client)
        _run(adapter.exchange_code_for_token("code"))
        _run(adapter.ensure_token())
        assert adapter._access_token == "ex-at"


class TestAirtableConnectionAndBases:
    def test_connection_no_token_false(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        assert _run(adapter.test_connection()) is False

    def test_connection_success_uses_correct_url(self, monkeypatch):
        """BUG (HIGH): URL doubled the /v0 prefix -> whoami always 404s."""
        client = _records_client({"id": "usr-1"})
        adapter = _adapter(monkeypatch, client=client, env={"AIRTABLE_PAT": "pat"})
        adapter._access_token = "at"
        assert _run(adapter.test_connection()) is True
        method, url, kw = client.calls[0]
        assert url == "https://api.airtable.com/v0/meta/whoami"
        assert kw["headers"]["Authorization"] == "Bearer at"

    def test_connection_failure_false(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=403)

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        assert _run(adapter.test_connection()) is False

    def test_list_bases_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError, match="not configured"):
            _run(adapter.list_bases())

    def test_list_bases_success_and_error(self, monkeypatch):
        client = _records_client({"bases": [{"id": "b1", "name": "Base1"}]})
        adapter = _adapter(monkeypatch, client=client, env={"AIRTABLE_PAT": "pat"})
        bases = _run(adapter.list_bases())
        assert bases == [{"id": "b1", "name": "Base1"}]

        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        bad = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        with pytest.raises(httpx.HTTPStatusError):
            _run(bad.list_bases())

    def test_list_tables_success(self, monkeypatch):
        client = _records_client({"tables": [{"id": "tbl1", "name": "T1"}]})
        adapter = _adapter(monkeypatch, client=client, env={"AIRTABLE_PAT": "pat"})
        tables = _run(adapter.list_tables("b1"))
        assert tables == [{"id": "tbl1", "name": "T1"}]
        method, url, kw = client.calls[0]
        assert url == "https://api.airtable.com/v0/meta/bases/b1/tables"

    def test_list_tables_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError):
            _run(adapter.list_tables("b1"))

    def test_list_tables_error_raises(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.list_tables("b1"))


class TestAirtableRecords:
    def _adapter_with(self, monkeypatch, client):
        return _adapter(monkeypatch, client=client, env={"AIRTABLE_PAT": "pat"})

    def test_get_records_params(self, monkeypatch):
        client = _records_client({"records": [{"id": "r1"}]})
        adapter = self._adapter_with(monkeypatch, client)
        records = _run(adapter.get_records(
            "b1", "t1", filter_by_formula="X", sort=[{"field": "Name", "direction": "asc"}], max_records=50,
        ))
        assert records == [{"id": "r1"}]
        method, url, kw = client.calls[0]
        assert url == "https://api.airtable.com/v0/b1/t1"
        assert kw["params"]["max_records"] == 50
        assert kw["params"]["filter_by_formula"] == "X"
        assert kw["params"]["sort[]"] == ["Name:asc"]

    def test_get_records_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError):
            _run(adapter.get_records("b1", "t1"))

    def test_get_records_error_raises(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        adapter = self._adapter_with(monkeypatch, _FakeClient(respond))
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.get_records("b1", "t1"))

    def test_get_record_success(self, monkeypatch):
        client = _records_client({"id": "r1", "fields": {"Name": "x"}})
        adapter = self._adapter_with(monkeypatch, client)
        rec = _run(adapter.get_record("b1", "t1", "r1"))
        assert rec["id"] == "r1"
        method, url, _ = client.calls[0]
        assert url == "https://api.airtable.com/v0/b1/t1/r1"

    def test_get_record_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError):
            _run(adapter.get_record("b1", "t1", "r1"))

    def test_create_record_sends_fields(self, monkeypatch):
        client = _records_client()
        adapter = self._adapter_with(monkeypatch, client)
        rec = _run(adapter.create_record("b1", "t1", {"Name": "x"}))
        assert rec["id"] == "rec-new"
        method, url, kw = client.calls[0]
        assert method == "post" and url == "https://api.airtable.com/v0/b1/t1"
        assert kw["json"] == {"records": [{"fields": {"Name": "x"}}]}

    def test_create_record_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError):
            _run(adapter.create_record("b1", "t1", {}))

    def test_update_record_success(self, monkeypatch):
        client = _records_client()
        adapter = self._adapter_with(monkeypatch, client)
        rec = _run(adapter.update_record("b1", "t1", "r1", {"Name": "y"}))
        assert rec["id"] == "rec1"
        method, url, kw = client.calls[0]
        assert method == "patch" and url == "https://api.airtable.com/v0/b1/t1/r1"
        assert kw["json"] == {"fields": {"Name": "y"}}

    def test_update_record_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError):
            _run(adapter.update_record("b1", "t1", "r1", {}))

    def test_delete_record_success_and_failure(self, monkeypatch):
        client = _records_client()
        adapter = self._adapter_with(monkeypatch, client)
        assert _run(adapter.delete_record("b1", "t1", "r1")) is True

        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        bad = self._adapter_with(monkeypatch, _FakeClient(respond))
        assert _run(bad.delete_record("b1", "t1", "r1")) is False

    def test_search_records_actually_searches(self, monkeypatch):
        """BUG (HIGH): search_records built the FIND() formula but never
        called the API — always returned None."""
        client = _records_client({"records": [{"id": "hit1", "fields": {"Name": "acme"}}]})
        adapter = self._adapter_with(monkeypatch, client)
        results = _run(adapter.search_records("b1", "t1", "Name", "acme"))
        assert results == [{"id": "hit1", "fields": {"Name": "acme"}}]
        method, url, kw = client.calls[0]
        assert method == "get" and url == "https://api.airtable.com/v0/b1/t1"
        assert "FIND('acme', LOWER({Name}))" in kw["params"]["filter_by_formula"]
        assert kw["params"]["max_records"] == 20

    def test_search_records_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError):
            _run(adapter.search_records("b1", "t1", "Name", "x"))

    def test_single_record_ops_error_paths_raise(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.get_record("b1", "t1", "r1"))
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.create_record("b1", "t1", {"Name": "x"}))
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.update_record("b1", "t1", "r1", {"Name": "y"}))
        with pytest.raises(httpx.HTTPStatusError):
            _run(adapter.search_records("b1", "t1", "Name", "acme"))


class TestAirtableSchemasAndFetch:
    def test_get_available_schemas_enriches_tables(self, monkeypatch):
        def respond(method, url, **kw):
            if "meta/bases/b1/tables" in url:
                return _FakeResponse({"tables": [{"id": "tbl1", "name": "T1"}]})
            if "meta/bases" in url:
                return _FakeResponse({"bases": [{"id": "b1", "name": "Base1"}]})
            return _FakeResponse()

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        schemas = _run(adapter.get_available_schemas())
        assert schemas == [{"id": "tbl1", "name": "T1", "base_id": "b1", "base_name": "Base1"}]

    def test_get_available_schemas_skips_broken_base(self, monkeypatch):
        def respond(method, url, **kw):
            if "meta/bases/b1/tables" in url:
                return _FakeResponse(status_code=500)
            if "meta/bases/b2/tables" in url:
                return _FakeResponse({"tables": [{"id": "tbl2"}]})
            return _FakeResponse({"bases": [{"id": "b1", "name": "Broken"}, {"id": "b2", "name": "Good"}]})

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        schemas = _run(adapter.get_available_schemas())
        assert len(schemas) == 1 and schemas[0]["base_name"] == "Good"

    def test_get_available_schemas_list_failure_returns_empty(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        assert _run(adapter.get_available_schemas()) == []

    def test_fetch_records_invalid_entity_type(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": "pat"})
        assert _run(adapter.fetch_records("b1")) == {"results": [], "paging": {}}

    def test_fetch_records_success_with_and_without_offset(self, monkeypatch):
        def respond(method, url, **kw):
            if kw.get("params", {}).get("offset"):
                return _FakeResponse({"records": [{"id": "r2"}], "offset": "pg2"})
            return _FakeResponse({"records": [{"id": "r1"}], "offset": "pg1"})

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        first = _run(adapter.fetch_records("b1:t1", limit=50))
        assert first["results"] == [{"id": "r1"}] and first["paging"] == {"after": "pg1"}
        second = _run(adapter.fetch_records("b1:t1", after="pg1"))
        assert second["results"] == [{"id": "r2"}]

        def respond2(method, url, **kw):
            return _FakeResponse({"records": [{"id": "r1"}]})

        adapter2 = _adapter(monkeypatch, client=_FakeClient(respond2), env={"AIRTABLE_PAT": "pat"})
        res = _run(adapter2.fetch_records("b1:t1"))
        assert res["paging"] == {}

    def test_fetch_records_error_returns_empty(self, monkeypatch):
        def respond(method, url, **kw):
            return _FakeResponse(status_code=500)

        adapter = _adapter(monkeypatch, client=_FakeClient(respond), env={"AIRTABLE_PAT": "pat"})
        assert _run(adapter.fetch_records("b1:t1")) == {"results": [], "paging": {}}

    def test_fetch_records_no_token_raises(self, monkeypatch):
        adapter = _adapter(monkeypatch, env={"AIRTABLE_PAT": ""})
        with pytest.raises(ValueError):
            _run(adapter.fetch_records("b1:t1"))


# ===========================================================================
# AI Accounting Engine — edge branches + bug regressions
# ===========================================================================
def _tx(engine, tx_id="tx-1", merchant="AWS", description="Software", amount=Decimal("100.00"), **kw):
    tx = Transaction(
        id=tx_id, date=datetime.now(), amount=amount,
        description=description, merchant=merchant, **kw,
    )
    return engine.ingest_transaction(tx)


class TestAccountingCsvSanitize:
    def test_csv_cell_sanitize_injection_prefixes(self):
        from core.ai_accounting_engine import _sanitize_csv_cell

        for evil in ("=SUM(A1)", "+1+1", "-2+3", "@cmd", "\tcmd", "\rcmd"):
            assert _sanitize_csv_cell(evil) == "'" + evil
        assert _sanitize_csv_cell("safe") == "safe"
        assert _sanitize_csv_cell("") == ""
        assert _sanitize_csv_cell(Decimal("12.5")) == Decimal("12.5")
        assert _sanitize_csv_cell(None) is None

    def test_gl_export_sanitizes_cells(self):
        engine = AIAccountingEngine()
        _tx(engine, merchant="=", description="cmd")
        csv = engine.export_general_ledger_csv()
        assert "'=," in csv or "'=" in csv


class TestAccountingLearningAndUpdate:
    def test_learn_categorization_missing_tx(self, engine_factory):
        engine = engine_factory()
        engine.learn_categorization("nope", "6300", "u1")  # no crash

    def test_learn_categorization_missing_account(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="tx-1", merchant="AWS")
        engine.learn_categorization("tx-1", "9999", "u1")  # unknown account -> no-op
        assert engine._transactions["tx-1"].category_id != "9999"

    def test_categorize_uses_merchant_history(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="Acme Supplies", description="paper")
        for _ in range(3):
            engine.learn_categorization("t1", "6700", "u1")
        t2 = Transaction(id="t2", date=datetime.now(), amount=Decimal("10"), description="misc", merchant="Acme Supplies")
        engine.ingest_transaction(t2)
        assert t2.category_id == "6700"
        assert t2.confidence == 0.90
        assert "Historical" in (t2.reasoning or "")

    def test_categorize_merchant_history_low_count(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="Corner Bodega", description="snacks")
        engine.learn_categorization("t1", "6500", "u1")
        engine.learn_categorization("t1", "6500", "u1")
        t2 = Transaction(id="t2", date=datetime.now(), amount=Decimal("10"), description="misc", merchant="Corner Bodega")
        engine.ingest_transaction(t2)
        assert t2.category_id == "6500"
        assert t2.confidence == 0.75

    def test_update_transaction_missing_returns_false(self, engine_factory):
        engine = engine_factory()
        assert engine.update_transaction("nope", {"merchant": "x"}, "u1") is False

    def test_update_transaction_date_only(self, engine_factory):
        engine = engine_factory()
        _tx(engine)
        assert engine.update_transaction("tx-1", {"date": "2026-02-01"}, "u1") is True
        assert engine._transactions["tx-1"].date == datetime(2026, 2, 1)

    def test_update_transaction_low_conf_enters_review(self, engine_factory):
        engine = engine_factory()
        _tx(engine, merchant="AWS")
        assert engine._transactions["tx-1"].status == TransactionStatus.CATEGORIZED
        engine.update_transaction("tx-1", {"merchant": "Weird Vendor", "description": "opaque"}, "u1")
        tx = engine._transactions["tx-1"]
        assert tx.status == TransactionStatus.REVIEW_REQUIRED
        assert "tx-1" in engine._pending_review
        assert tx.reasoning.startswith("Re-categorized after update")

    def test_update_transaction_high_conf_leaves_review(self, engine_factory):
        engine = engine_factory()
        _tx(engine, merchant="Mystery Vendor", description="opaque")
        assert "tx-1" in engine._pending_review
        engine.update_transaction("tx-1", {"merchant": "AWS"}, "u1")
        tx = engine._transactions["tx-1"]
        assert tx.status == TransactionStatus.CATEGORIZED
        assert "tx-1" not in engine._pending_review

    def test_delete_transaction_missing_returns_false(self, engine_factory):
        engine = engine_factory()
        assert engine.delete_transaction("nope", "u1") is False

    def test_get_audit_log_unfiltered(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="a")
        _tx(engine, tx_id="b")
        assert len(engine.get_audit_log()) == 2
        assert len(engine.get_audit_log(tx_id="a")) == 1


class TestAccountingForecastAndScenario:
    def test_forecast_with_history(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="AWS", amount=Decimal("-1000.00"))
        _tx(engine, tx_id="t2", merchant="GitHub", amount=Decimal("-500.00"))
        forecast = engine.get_13_week_forecast(current_balance=1000.0)
        assert len(forecast["projection"]) == 13
        assert forecast["projection"][0]["week"] == 1
        assert forecast["projection"][12]["week_start"] > forecast["projection"][0]["week_start"]
        assert forecast["historical_weekly_avg"] != 0
        # weekly burn is negative and balances decline
        assert forecast["projection"][-1]["projected_balance"] < forecast["projection"][0]["projected_balance"]

    def test_forecast_cash_only_falls_back(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="AWS", amount=Decimal("-1000.00"))
        engine._transactions["t1"].category_id = "1000"  # cash transfer excluded
        forecast = engine.get_13_week_forecast(current_balance=1000.0)
        assert forecast["historical_weekly_avg"] == -2500.0

    def test_forecast_no_transactions_falls_back(self, engine_factory):
        engine = engine_factory()
        forecast = engine.get_13_week_forecast()
        assert forecast["historical_weekly_avg"] == -2500.0
        assert len(forecast["projection"]) == 13

    def test_scenario_expense(self, engine_factory):
        engine = engine_factory()
        res = engine.run_scenario("Hire 3 engineers costing $12,000 per week", [])
        assert res["impact_value"] == -12000
        assert res["risk_level"] == "medium"
        assert "burn" in res["analysis"]

    def test_scenario_expense_small_low_risk(self, engine_factory):
        engine = engine_factory()
        res = engine.run_scenario("buy equipment for $5,000", [])
        assert res["impact_value"] == -5000 and res["risk_level"] == "low"

    def test_scenario_expense_no_number_default(self, engine_factory):
        engine = engine_factory()
        res = engine.run_scenario("buy a new computer", [])
        assert res["impact_value"] == -5000 and res["risk_level"] == "low"

    def test_scenario_revenue(self, engine_factory):
        engine = engine_factory()
        res = engine.run_scenario("Sell 100 units for $5,000", [])
        assert res["impact_value"] == 5000
        assert "Improves cash" in res["analysis"]

    def test_scenario_revenue_no_number_default(self, engine_factory):
        engine = engine_factory()
        res = engine.run_scenario("raise a round", [])
        assert res["impact_value"] == 10000

    def test_scenario_lose_client_high_risk(self, engine_factory):
        engine = engine_factory()
        res = engine.run_scenario("lose client contract $10k", [])
        assert res["risk_level"] == "high"
        assert res["impact_value"] == -10000

    def test_scenario_no_signal_default(self, engine_factory):
        engine = engine_factory()
        res = engine.run_scenario("unrelated", [])
        assert res["impact_value"] == -1000

    def test_scenario_prefers_dollar_amount_over_count(self, engine_factory):
        """BUG (MED): regex took the FIRST digit run — a headcount ("2") —
        instead of the dollar amount, under-estimating impact 1000x."""
        engine = engine_factory()
        res = engine.run_scenario("hire 2 engineers at $50,000", [])
        assert res["impact_value"] == -50000


class TestAccountingTrialBalanceFloat:
    def test_trial_balance_float_amount_no_crash(self, engine_factory):
        """BUG (HIGH): float amounts crash export_trial_balance_json
        (Decimal('0.0') + float -> TypeError)."""
        engine = engine_factory()
        tx = Transaction(id="f1", date=datetime.now(), amount=100.5, description="Soft", merchant="AWS")
        engine.ingest_transaction(tx)
        report = engine.export_trial_balance_json()
        assert any(acc["name"] == "Software" and acc["net_balance"] == 100.5 for acc in report["accounts"])

    def test_trial_balance_excludes_pending(self, engine_factory):
        engine = engine_factory()
        low = Transaction(id="p1", date=datetime.now(), amount=Decimal("-10"), description="opaque")
        engine.ingest_transaction(low)
        report = engine.export_trial_balance_json()
        assert report["accounts"] == []


class TestAccountingPostToLedger:
    def test_post_to_ledger_missing_tx(self, engine_factory):
        engine = engine_factory()
        res = engine.post_to_ledger("nope")
        assert res["status"] == "failed" and "not found" in res["error"]

    def test_post_to_ledger_review_required(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="Mystery Vendor", description="opaque")
        res = engine.post_to_ledger("t1")
        assert res["status"] == "failed" and "review" in res["error"]

    def test_post_to_ledger_already_posted(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="AWS")
        engine.post_transaction("t1")
        res = engine.post_to_ledger("t1")
        assert res["status"] == "skipped"

    def test_post_to_ledger_mock_mode(self, engine_factory):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="AWS")
        res = engine.post_to_ledger("t1", db_session=None)
        assert res["status"] == "posted" and res["mode"] == "mock"
        assert engine._transactions["t1"].status == TransactionStatus.POSTED

    def test_post_to_ledger_import_error_fallback(self, engine_factory, monkeypatch):
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="AWS")
        monkeypatch.setitem(sys.modules, "accounting.ledger", None)
        monkeypatch.setitem(sys.modules, "accounting.models", None)
        res = engine.post_to_ledger("t1", db_session=object())
        assert res["status"] == "posted" and res["mode"] == "standalone"

    def test_post_to_ledger_db_path(self, engine_factory, monkeypatch):
        import accounting.ledger as ledger_mod
        import accounting.models as models_mod

        class FakeLedger:
            def __init__(self, db):
                self.db = db

            def record_transaction(self, **kw):
                return SimpleNamespace(id="ltx-9")

        class FakeDEE:
            @staticmethod
            def create_payment_entry(**kw):
                return ["entry1", "entry2"]

        monkeypatch.setattr(ledger_mod, "EventSourcedLedger", FakeLedger)
        monkeypatch.setattr(ledger_mod, "DoubleEntryEngine", FakeDEE)
        monkeypatch.setattr(models_mod, "EntryType", SimpleNamespace)
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="AWS")
        res = engine.post_to_ledger("t1", db_session=object())
        assert res["status"] == "posted" and res["ledger_tx_id"] == "ltx-9"
        assert engine._transactions["t1"].status == TransactionStatus.POSTED

    def test_post_to_ledger_exception_generic_error(self, engine_factory, monkeypatch):
        """No str(e) leaks: internal exception detail must not reach the caller."""
        import accounting.ledger as ledger_mod

        class BoomLedger:
            def __init__(self, db):
                raise OSError("disk on fire: secret-path")

        monkeypatch.setattr(ledger_mod, "EventSourcedLedger", BoomLedger)
        engine = engine_factory()
        _tx(engine, tx_id="t1", merchant="AWS")
        res = engine.post_to_ledger("t1", db_session=object())
        assert res["status"] == "failed"
        assert "disk on fire" not in res["error"]
        assert len([e for e in engine._audit_log if e["action"] == "post_failed"]) == 1


@pytest.fixture
def engine_factory():
    def _make():
        return AIAccountingEngine()
    return _make


# ===========================================================================
# mini_app_service — READ-ONLY module. Remaining uncovered branches exercised;
# observations reported in the summary, no edits to core/mini_app_service.py.
# ===========================================================================
def _viewer(user_id="u1", tenant_id="t1", workspace_id="w1", tier="autonomous"):
    return SimpleNamespace(
        id=user_id, tenant_id=tenant_id, workspace_id=workspace_id, tier=tier,
    )


def _mini_app(db, name="calc", scopes=None, status="draft"):
    canvas_id = f"mc-{uuid.uuid4().hex[:12]}"
    app_id = f"mapp-{uuid.uuid4().hex[:12]}"
    from core.models import Canvas, CanvasLogic, CanvasState, MiniApp

    db.add(Canvas(
        id=canvas_id, tenant_id="t1", workspace_id="w1", created_by="u1",
        name=name, canvas_type="mini_app", content={"blocks": []}, style={},
        status="active", mini_app_id=app_id,
    ))
    db.add(CanvasLogic(
        canvas_id=canvas_id, language="python",
        source="state = {**state, 'n': state.get('n', 0) + 1}",
        created_by="u1",
    ))
    manifest = {
        "declared_scopes": scopes or ["*"],
        "skills": [], "mcp_servers": [], "entrypoint": "logic",
        "dependencies": [], "base_image": "python:3.11-slim", "assets": [],
        "storage": {"enabled": True, "backend": "local", "max_bytes_per_object": 1024 * 1024},
        "db": {"enabled": True, "max_records_per_series": 10, "max_record_bytes": 100 * 1024, "record_queries": []},
        "initial_state": {}, "blueprint": {},
    }
    app = MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by="u1",
        name=name, manifest=manifest, blueprint_canvas_id=canvas_id,
        status=status, runtime_version=0,
    )
    db.add(app)
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={"n": 0}, version=1))
    db.commit()
    return app, canvas_id


class TestMiniAppManifestBranches:
    def test_known_scope_names_import_failure_falls_back_to_raw(self, monkeypatch):
        from core.mini_app_service import validate_manifest

        monkeypatch.setitem(sys.modules, "core.action_registry", None)
        validate_manifest({"declared_scopes": ["canvas_render"], "base_image": "python:3.11-slim"})
        with pytest.raises(ValueError, match="unknown declared scope"):
            validate_manifest({"declared_scopes": ["documents.search"]})

    def test_base_image_not_allowed(self, monkeypatch):
        from core.mini_app_service import validate_manifest

        monkeypatch.delenv("MINIAPP_BASE_IMAGE_ALLOWLIST", raising=False)
        with pytest.raises(ValueError, match="base_image"):
            validate_manifest({"declared_scopes": ["*"], "base_image": "ubuntu:latest"})

    def test_storage_not_dict(self):
        from core.mini_app_service import validate_manifest

        with pytest.raises(ValueError, match="storage must be an object"):
            validate_manifest({"declared_scopes": ["*"], "storage": "local"})

    def test_storage_bad_backend(self):
        from core.mini_app_service import validate_manifest

        with pytest.raises(ValueError, match="storage.backend"):
            validate_manifest({"declared_scopes": ["*"], "storage": {"backend": "s3"}})

    def test_storage_bad_max_bytes(self):
        from core.mini_app_service import validate_manifest

        with pytest.raises(ValueError, match="max_bytes_per_object"):
            validate_manifest({"declared_scopes": ["*"], "storage": {"max_bytes_per_object": 0}})

    def test_data_sources_not_list(self):
        from core.mini_app_service import validate_manifest

        with pytest.raises(ValueError, match="data_sources must be a list"):
            validate_manifest({"declared_scopes": ["*"], "data_sources": {"type": "documents.search"}})

    def test_resolve_effective_scopes_declared_caps(self):
        from core.mini_app_service import resolve_effective_scopes

        scopes = resolve_effective_scopes({"declared_scopes": ["canvas_render"]}, viewer=_viewer())
        assert scopes == ("canvas_render",)


class TestMiniAppAsyncAndInstall:
    def test_run_async_error_reraises(self):
        from core.mini_app_service import _run_async

        async def boom():
            raise ValueError("coro boom")

        with pytest.raises(ValueError, match="coro boom"):
            _run_async(boom())

    def test_install_miniappinstallation_write_failure_swallowed(self, db_session, monkeypatch):
        from core.mini_app_service import install

        app, canvas_id = _mini_app(db_session, status="published")
        app.manifest = {
            **app.manifest,
            "blueprint": {
                "content": {"blocks": []}, "style": {},
                "logic_source": "state = {**state}", "logic_language": "python",
                "component_installations": [],
            },
            "initial_state": {"n": 1},
        }
        db_session.commit()

        class BoomInstallation:
            def __init__(self, *a, **k):
                raise OSError("boom")

        from core import models as models_mod
        monkeypatch.setattr(models_mod, "MiniAppInstallation", BoomInstallation)
        new_canvas = install(app, _viewer(), db_session)
        assert new_canvas != canvas_id
        from core.models import Canvas, CanvasAudit
        row = db_session.query(Canvas).filter(Canvas.id == new_canvas).first()
        assert row is not None and row.mini_app_id == app.id
        audit = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == new_canvas, CanvasAudit.action_type == "mini_app_install",
        ).count()
        assert audit == 1


class TestMiniAppReadBridgeBranches:
    @pytest.mark.asyncio
    async def test_inject_assets_retrieve_raises(self, monkeypatch):
        from core.mini_app_service import _inject_assets

        class BadStorage:
            def retrieve(self, key):
                raise OSError("disk")

        monkeypatch.setattr(
            "core.mini_app_storage.get_mini_app_storage", lambda *a, **k: BadStorage(),
        )
        out = _inject_assets({"assets": ["a.txt"]}, "t1", "c1")
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_record_queries_raises(self, db_session, monkeypatch):
        from core.mini_app_service import _inject_record_queries
        import core.mini_app_db_service as dbsvc

        def boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr(dbsvc, "query_records", boom)
        out = _inject_record_queries({"db": {"record_queries": ["s1"]}}, db_session, "c1")
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_data_sources_bad_limit_skipped(self, monkeypatch):
        from core.mini_app_service import _inject_data_sources

        out = await _inject_data_sources(
            {"data_sources": [{"type": "documents.search", "query": "q", "limit": "abc"}]},
            "t1", "w1", "a1",
        )
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_integration_missing_fields_skipped(self, monkeypatch):
        from core.mini_app_service import _inject_integration_sources

        out = await _inject_integration_sources(
            {"integrations": [{"service": "notion"}, {"action": "search"}, {}]},
            "t1", "w1", "a1",
        )
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_integration_dispatch_raises(self, monkeypatch):
        from core.mini_app_service import _inject_integration_sources
        import core.mini_app_integration_dispatch as dispatch_mod

        async def boom(*a, **k):
            raise RuntimeError("down")

        monkeypatch.setattr(dispatch_mod, "dispatch", boom)
        out = await _inject_integration_sources(
            {"integrations": [{"service": "notion", "action": "search"}]},
            "t1", "w1", "a1",
        )
        assert out == {}

    @pytest.mark.asyncio
    async def test_callback_mcp_scope_gate_allowed(self, db_session, monkeypatch):
        from core.mini_app_service import _make_callback_handler
        import core.mini_app_integration_dispatch as dispatch_mod

        async def fake_resolve(service, action):
            return ("mcp", "srv-1")

        async def fake_dispatch(service, action, params, tenant_id=None, db=None):
            return {"ok": True, "data": {"ok": 1}}

        monkeypatch.setattr(dispatch_mod, "resolve_backend", fake_resolve)
        monkeypatch.setattr(dispatch_mod, "dispatch", fake_dispatch)
        h = _make_callback_handler(db_session, "t1", ("mcp.srv-1",), "w1", "a1")
        res = await h({"kind": "fetch_integration", "service": "notion", "action": "search"})
        assert res["ok"] is True and res["data"] == {"ok": 1}


class TestMiniAppExecutionBranches:
    @pytest.mark.asyncio
    async def test_run_stateful_dry_run_proposes_storage_ops(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import run_stateful
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT

        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        monkeypatch.setenv("MINIAPP_ROOTFS_DIR", str(tmp_path / "rootfs"))
        import core.mini_app_service as svc

        @contextlib.contextmanager
        def _cm():
            yield db_session

        monkeypatch.setattr("core.database.get_db_session", _cm)

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None,
                                     image=None, callback_handler=None, **kw):
                env = {"state": {"n": 2}, "storage_ops": [{"op": "put", "key": "k", "data": "x"}]}
                return type("R", (), {
                    "success": True, "exit_code": 0, "stderr": "",
                    "stdout": "__MINIAPP_STATE__:" + json.dumps(env),
                    "truncated": False, "metadata": {},
                })()

        monkeypatch.setattr(svc, "get_miniapp_runtime", lambda: FakeRuntime())
        app, canvas_id = _mini_app(db_session)
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",), persist=False)
        assert res["success"]
        assert res["op_results"] == [{"op": "put", "key": "k", "ok": True, "proposed": True}]
        assert res["proposed_ops"] == res["op_results"]
        from core.models import CanvasState
        row = db_session.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).first()
        assert row.state == {"n": 0}  # dry-run never commits

    def test_execute_storage_op_unknown_op(self, db_session):
        from core.mini_app_service import _execute_storage_op

        res = _execute_storage_op({"op": "bogus", "key": "k"}, None, None, None, None)
        assert res == {"op": "bogus", "key": "k", "ok": False, "error": "unknown_op"}

    def test_validate_record_op_update_many_bad_filter(self):
        from core.mini_app_service import _validate_record_op

        assert _validate_record_op(
            {"op": "update_many", "series": "s1", "filter": {"a": []}, "data": {"b": 1}}, 1000,
        ) is None

    def test_execute_record_op_get_and_update_success(self, db_session):
        from core.mini_app_service import _execute_record_op
        from core.mini_app_db_service import append_record

        app, canvas_id = _mini_app(db_session)
        row = append_record(db_session, canvas_id, "t1", app.id, "s1", {"a": 1}, created_by="u1")
        rid = row["id"]
        canvas = SimpleNamespace(id=canvas_id, tenant_id="t1")
        got = _execute_record_op({"op": "get", "series": "s1", "id": rid}, db_session, canvas, app, "u1")
        assert got["ok"] is True and got["record"]["data"] == {"a": 1}
        updated = _execute_record_op(
            {"op": "update", "series": "s1", "id": rid, "data": {"b": 2}},
            db_session, canvas, app, "u1",
        )
        assert updated["ok"] is True and updated["record"]["data"] == {"a": 1, "b": 2}

    def test_execute_record_op_cap_valueerror(self, db_session):
        from core.mini_app_service import _execute_record_op
        from core.mini_app_db_service import append_record

        app, canvas_id = _mini_app(db_session)
        append_record(db_session, canvas_id, "t1", app.id, "s1", {"a": 1}, created_by="u1")
        canvas = SimpleNamespace(id=canvas_id, tenant_id="t1")
        res = _execute_record_op(
            {"op": "append", "series": "s1", "data": {"a": 2}},
            db_session, canvas, app, "u1", max_records=1,
        )
        assert res["ok"] is False and res["error"] == "series_cap"

    def test_execute_record_op_generic_exception(self, db_session, monkeypatch):
        from core.mini_app_service import _execute_record_op
        import core.mini_app_db_service as dbsvc

        def boom(*a, **k):
            raise RuntimeError("db on fire")

        monkeypatch.setattr(dbsvc, "append_record", boom)
        app, canvas_id = _mini_app(db_session)
        canvas = SimpleNamespace(id=canvas_id, tenant_id="t1")
        res = _execute_record_op(
            {"op": "append", "series": "s1", "data": {"a": 2}},
            db_session, canvas, app, "u1",
        )
        assert res["ok"] is False and res["error"] == "failed"


class TestMiniAppCredentialsAndProbe:
    def test_resolve_integration_credentials_lookup(self, db_session):
        from core.mini_app_service import _resolve_integration_credentials
        from core.models import IntegrationToken

        db_session.add(IntegrationToken(
            tenant_id="t1", provider="notion", access_token="ptok",
            token_type="Bearer", refresh_token=None, instance_url=None,
        ))
        db_session.commit()
        creds = _resolve_integration_credentials("t1", "notion", db_session)
        assert creds["access_token"] == "ptok"
        assert creds["token_type"] == "Bearer"

    def test_resolve_integration_credentials_missing_and_error(self, db_session, monkeypatch):
        from core.mini_app_service import _resolve_integration_credentials
        from core.models import IntegrationToken
        import core.privsec.token_encryption as te

        assert _resolve_integration_credentials("t1", "ghost", db_session) == {}
        db_session.add(IntegrationToken(
            tenant_id="t1", provider="jira", access_token="enc:jira",
            token_type="Bearer", refresh_token=None, instance_url=None,
        ))
        db_session.commit()
        monkeypatch.setattr(te, "decrypt_token", lambda *a, **k: (_ for _ in ()).throw(ValueError("no key")))
        assert _resolve_integration_credentials("t1", "jira", db_session) == {}

    def test_resolve_integration_credentials_no_db_session(self, db_session, monkeypatch):
        from core.mini_app_service import _resolve_integration_credentials
        from core.models import IntegrationToken

        db_session.add(IntegrationToken(
            tenant_id="t1", provider="slack", access_token="stok",
            token_type="Bearer", refresh_token=None, instance_url=None,
        ))
        db_session.commit()

        @contextlib.contextmanager
        def _cm():
            yield db_session

        monkeypatch.setattr("core.database.get_db_session", _cm)
        creds = _resolve_integration_credentials("t1", "slack", None)
        assert creds["access_token"] == "stok"

    def test_status_probe_runtime_generic_exception(self, db_session, monkeypatch):
        from core.mini_app_service import status_probe

        app, _ = _mini_app(db_session)
        monkeypatch.setattr(
            "core.mini_app_runtime.get_miniapp_runtime",
            lambda: (_ for _ in ()).throw(ValueError("boom")),
        )
        probe = status_probe(app, db_session)
        assert probe["runtime"]["available"] is False
        assert probe["runtime"]["reason"] == "runtime init failed"
