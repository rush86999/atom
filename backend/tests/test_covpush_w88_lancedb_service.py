# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/lancedb_service (52 stmts, never wave-tested).

- LanceDBService stub: init defaults + workspace_id/db_path/tenant_id args,
  db stays None, stub-mode warning logged.
- create_table / table_exists / insert / search / delete: stub no-ops with
  expected return shapes and warnings.
- get_or_create_reflection_pool_table: returns None (callers guard).
- get_lancedb_handler: returns a stub wired with workspace_id/tenant_id.

No network / no real LanceDB / no LLM.
"""
import logging

from core.lancedb_service import LanceDBService, get_lancedb_handler


class TestLanceDBService:
    def test_init_defaults(self):
        svc = LanceDBService()
        assert svc.workspace_id == "default"
        assert svc.tenant_id is None
        assert svc.db is None

    def test_init_with_args(self):
        svc = LanceDBService(workspace_id="ws-9", db_path="/tmp/x", tenant_id="t-1")
        assert svc.workspace_id == "ws-9"
        assert svc.tenant_id == "t-1"
        assert svc.db is None

    def test_init_warns_stub_mode(self, caplog):
        with caplog.at_level(logging.WARNING, logger="core.lancedb_service"):
            LanceDBService()
        assert "stub mode (no-op)" in caplog.text

    def test_create_table_noop(self, caplog):
        svc = LanceDBService()
        assert svc.create_table("items", {"name": "str"}) is None
        assert "create_table(items)" in caplog.text

    def test_table_exists_always_false(self):
        assert LanceDBService().table_exists("items") is False

    def test_insert_noop(self, caplog):
        svc = LanceDBService()
        assert svc.insert("items", [{"a": 1}]) is None
        assert "insert(items)" in caplog.text

    def test_search_returns_empty(self, caplog):
        svc = LanceDBService()
        assert svc.search("items", "hello") == []
        assert svc.search("items", "hello", limit=3) == []
        assert "search(items)" in caplog.text

    def test_delete_noop(self, caplog):
        svc = LanceDBService()
        assert svc.delete("items", ["id-1"]) is None
        assert "delete(items)" in caplog.text

    def test_reflection_pool_returns_none(self, caplog):
        svc = LanceDBService()
        assert svc.get_or_create_reflection_pool_table() is None
        assert "no table" in caplog.text


class TestGetLancedbHandler:
    def test_defaults(self):
        svc = get_lancedb_handler()
        assert isinstance(svc, LanceDBService)
        assert svc.workspace_id == "default"
        assert svc.tenant_id is None

    def test_passes_through_args(self):
        svc = get_lancedb_handler(workspace_id="ws-7", tenant_id="t-7")
        assert svc.workspace_id == "ws-7"
        assert svc.tenant_id == "t-7"
