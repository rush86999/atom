# -*- coding: utf-8 -*-
"""
Coverage-push tests for core/lancedb_handler.py (LanceDBHandler, ChatHistoryManager,
module helpers). LanceDB / embeddings fully mocked — no live LanceDB.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pyarrow as pa
import pytest

import core.lancedb_handler as lh
from core.lancedb_handler import (
    ChatHistoryManager,
    LanceDBHandler,
    get_lancedb_handler,
)


class _FakeLLMService:
    def __init__(self, *args, **kwargs):
        self.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])


class FakeLanceTable:
    def __init__(self, rows=None, with_freshness=True):
        self.rows = list(rows or [])
        self.added = list(self.rows)
        self._calls = []
        self.schema = pa.schema(
            [pa.field("freshness_status", pa.string()), pa.field("id", pa.string())]
            if with_freshness
            else [pa.field("id", pa.string())]
        )

    def search(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def where(self, expr):
        self._calls.append(expr)
        return self

    def to_pandas(self):
        return pd.DataFrame(self.rows)

    def add(self, records):
        self.added.extend(records)


class FakeLanceDB:
    def __init__(self, tables=None):
        self._tables = dict(tables or {})
        self.dropped = []

    def create_table(self, name, schema=None, data=None, mode="overwrite", **kwargs):
        table = FakeLanceTable(data or [])
        self._tables[name] = table
        return table

    def open_table(self, name):
        return self._tables.get(name)

    def table_names(self):
        return list(self._tables)

    def drop_table(self, name):
        self._tables.pop(name, None)
        self.dropped.append(name)


def make_rows():
    return [
        {
            "id": "d1",
            "text": "Alpha beta gamma delta epsilon",
            "source": "test",
            "metadata": json.dumps({"title": "Doc A", "doc_id": "d1"}),
            "created_at": "2026-01-02T00:00:00+00:00",
            "_distance": 0.2,
            "freshness_status": "fresh",
        },
        {
            "id": "d2",
            "text": "Second document body text here",
            "source": "test",
            "metadata": json.dumps({"title": "Doc B"}),
            "created_at": "2026-01-01T00:00:00+00:00",
            "_distance": 0.5,
            "freshness_status": "stale",
        },
    ]


@pytest.fixture
def lh_env(monkeypatch, tmp_path):
    monkeypatch.setattr(lh, "LLMService", _FakeLLMService)
    monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", False)
    monkeypatch.setattr(
        "lancedb.connect", MagicMock(side_effect=Exception("no live lancedb in tests"))
    )
    return tmp_path


@pytest.fixture
def lh_handler(lh_env):
    handler = LanceDBHandler(db_path=str(lh_env / "lancedb"), workspace_id="ws-1")
    handler.db = FakeLanceDB()
    return handler


class TestLanceDBInit:
    def test_initialization_defaults(self, lh_env):
        handler = LanceDBHandler(workspace_id="ws-x")
        assert handler.workspace_id == "ws-x"
        assert handler.tenant_id == "default"
        assert handler.embedding_service is not None

    def test_initialization_with_all_params(self, lh_env):
        handler = LanceDBHandler(
            db_path=str(lh_env / "x"), workspace_id="w", tenant_id="t", db=MagicMock()
        )
        assert handler.tenant_id == "t"
        assert handler.db_path == str(lh_env / "x")

    def test_embedding_provider_from_env(self, lh_env, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
        monkeypatch.setenv("EMBEDDING_MODEL", "model-x")
        handler = LanceDBHandler(db_path=str(lh_env / "y"))
        assert handler.embedding_provider == "fastembed"
        assert handler.embedding_model == "model-x"

    def test_llm_service_unavailable_fallback(self, lh_env, monkeypatch):
        monkeypatch.setattr(lh, "LLMService", None)
        handler = LanceDBHandler(db_path=str(lh_env / "z"))
        assert handler.embedding_service is None

    def test_ensure_db_lazy(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "lazy"))
        assert handler.db is None
        with patch("lancedb.connect", return_value=FakeLanceDB()) as connect:
            handler._ensure_db()
        connect.assert_called_once()

    def test_ensure_embedder_noop(self, lh_handler):
        lh_handler.embedder = None
        lh_handler._ensure_embedder()
        assert lh_handler.embedder is None


class TestLanceDBInitializeDb:
    def test_local_path_created(self, lh_env):
        target = str(lh_env / "sub" / "db")
        handler = LanceDBHandler(db_path=target)
        with patch("lancedb.connect", return_value=FakeLanceDB()) as connect:
            handler._initialize_db()
        assert connect.call_args.args[0] == target
        assert (lh_env / "sub" / "db").is_dir()

    def test_s3_with_cloud_disabled_downgrades(self, lh_env):
        handler = LanceDBHandler(db_path="s3://bucket/key")
        with patch("lancedb.connect", return_value=FakeLanceDB()) as connect:
            handler._initialize_db()
        path = connect.call_args.args[0]
        assert not path.startswith("s3://")
        assert path != "s3://bucket/key"

    def test_s3_with_cloud_enabled_r2_endpoint(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", True)
        monkeypatch.setenv("S3_ENDPOINT", "https://r2.example.com")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIA1234567")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        handler = LanceDBHandler(db_path="s3://bucket/key")
        with patch("lancedb.connect", return_value=FakeLanceDB()) as connect:
            handler._initialize_db()
        opts = connect.call_args.kwargs["storage_options"]
        assert opts["endpoint"] == "https://r2.example.com"
        assert opts["region"] == "auto"

    def test_s3_cloud_enabled_missing_creds(self, lh_env, monkeypatch, caplog):
        monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", True)
        monkeypatch.setenv("S3_ENDPOINT", "https://r2.example.com")
        handler = LanceDBHandler(db_path="s3://bucket/key")
        with patch("lancedb.connect", return_value=FakeLanceDB()):
            handler._initialize_db()
        assert "R2 credentials" in caplog.text

    def test_s3_cloud_enabled_autobuild_endpoint(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", True)
        monkeypatch.setenv("CLOUDFLARE_R2_ACCOUNT_ID", "acct123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIA1234567")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        handler = LanceDBHandler(db_path="s3://bucket/key")
        with patch("lancedb.connect", return_value=FakeLanceDB()) as connect:
            handler._initialize_db()
        endpoint = connect.call_args.kwargs["storage_options"]["endpoint"]
        assert endpoint == "https://acct123.r2.cloudflarestorage.com"

    def test_s3_cloud_enabled_no_endpoint(self, lh_env, monkeypatch, caplog):
        monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", True)
        handler = LanceDBHandler(db_path="s3://bucket/key")
        with patch("lancedb.connect", return_value=FakeLanceDB()) as connect:
            handler._initialize_db()
        assert connect.call_args.kwargs["storage_options"] == {"region": "auto"}
        assert "no R2 endpoint configured" in caplog.text

    def test_connect_failure_sets_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "fail"))
        with patch("lancedb.connect", side_effect=Exception("boom")):
            handler._initialize_db()
        assert handler.db is None


class TestLanceDBConnection:
    def test_test_connection_not_available(self, lh_env, monkeypatch):
        monkeypatch.setattr(lh, "LANCEDB_AVAILABLE", False)
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        result = handler.test_connection()
        assert result["connected"] is False

    def test_test_connection_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        result = handler.test_connection()
        assert result["connected"] is False

    def test_test_connection_success(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.db = FakeLanceDB(tables={"a": FakeLanceTable()})
        result = handler.test_connection()
        assert result["connected"] is True
        assert result["tables"] == ["a"]
        assert result["db_path"] == str(lh_env / "x")

    def test_test_connection_exception(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        db = MagicMock()
        db.table_names.side_effect = Exception("boom")
        handler.db = db
        result = handler.test_connection()
        assert result["connected"] is False


class TestLanceDBTableOps:
    def test_create_table_default_schema(self, lh_handler):
        table = lh_handler.create_table("docs")
        assert table is not None
        assert isinstance(lh_handler.db._tables["docs"], FakeLanceTable)

    def test_create_table_knowledge_graph_schema(self, lh_handler):
        table = lh_handler.create_table("knowledge_graph", schema={})
        assert table is not None

    def test_create_table_custom_schema_passthrough(self, lh_handler):
        schema = pa.schema([pa.field("id", pa.string())])
        lh_handler.create_table("custom", schema=schema, vector_size=8)
        assert "custom" in lh_handler.db._tables

    def test_create_table_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.create_table("t") is None

    def test_create_table_db_error(self, lh_handler):
        lh_handler.db.create_table = MagicMock(side_effect=Exception("boom"))
        assert lh_handler.create_table("t") is None

    def test_get_table_found(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable()
        assert lh_handler.get_table("docs") is not None

    def test_get_table_missing(self, lh_handler):
        assert lh_handler.get_table("nope") is None

    def test_get_table_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.get_table("t") is None

    def test_has_column_true(self, lh_handler):
        assert LanceDBHandler._has_column(FakeLanceTable(), "freshness_status") is True

    def test_has_column_false(self, lh_handler):
        assert LanceDBHandler._has_column(FakeLanceTable(with_freshness=False), "x") is False

    def test_has_column_error(self):
        class _BoomSchema:
            def __iter__(self):
                raise Exception("boom")

        table = MagicMock()
        table.schema = _BoomSchema()
        assert LanceDBHandler._has_column(table, "x") is False

    def test_drop_table_existing(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable()
        assert lh_handler.drop_table("docs") is True
        assert lh_handler.db.dropped == ["docs"]

    def test_drop_table_missing(self, lh_handler):
        assert lh_handler.drop_table("nope") is True

    def test_drop_table_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.drop_table("t") is False

    def test_drop_table_error(self, lh_handler):
        lh_handler.db.table_names = MagicMock(return_value=["docs"])
        lh_handler.db.drop_table = MagicMock(side_effect=Exception("boom"))
        assert lh_handler.drop_table("docs") is False


class TestLanceDBEmbed:
    def test_embed_text_no_service(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.embedding_service = None
        assert handler.embed_text("hello") is None

    def test_embed_text_no_loop(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.embed_text("hello") is not None

    def test_embed_text_in_async_context_returns_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))

        async def run():
            return handler.embed_text("hello")

        assert asyncio.run(run()) is None

    @pytest.mark.asyncio
    async def test_embed_text_other_thread(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        result = await asyncio.to_thread(handler.embed_text, "hello")
        assert result is not None

    def test_embed_text_exception(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.embedding_service.generate_embedding = AsyncMock(
            side_effect=Exception("boom")
        )
        assert handler.embed_text("hello") is None

    @pytest.mark.asyncio
    async def test_async_embed_text_success(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        vec = await handler.async_embed_text("hello")
        assert list(vec) == [0.1, 0.2, 0.3, 0.4]

    @pytest.mark.asyncio
    async def test_async_embed_text_no_service(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.embedding_service = None
        assert await handler.async_embed_text("hello") is None

    @pytest.mark.asyncio
    async def test_async_embed_text_exception(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.embedding_service.generate_embedding = AsyncMock(
            side_effect=Exception("boom")
        )
        assert await handler.async_embed_text("hello") is None


class TestLanceDBKnowledgeGraph:
    def test_add_edge_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.add_knowledge_edge("a", "b", "rel") is False

    def test_add_edge_create_table_failure(self, lh_handler):
        lh_handler.get_table = MagicMock(return_value=None)
        lh_handler.create_table = MagicMock(return_value=None)
        assert lh_handler.add_knowledge_edge("a", "b", "rel") is False

    def test_add_edge_success(self, lh_handler):
        lh_handler.db._tables["knowledge_graph"] = FakeLanceTable()
        assert (
            lh_handler.add_knowledge_edge("a", "b", "rel", description="is related to")
            is True
        )
        assert lh_handler.db._tables["knowledge_graph"].added

    def test_add_edge_embedding_failure_fallback(self, lh_handler):
        lh_handler.db._tables["knowledge_graph"] = FakeLanceTable()
        lh_handler.embed_text = MagicMock(return_value=None)
        assert lh_handler.add_knowledge_edge("a", "b", "rel", description="") is True
        record = lh_handler.db._tables["knowledge_graph"].added[0]
        assert record["id"] == "a_rel_b"

    def test_add_edge_exception(self, lh_handler):
        table = FakeLanceTable()
        table.add = MagicMock(side_effect=Exception("boom"))
        lh_handler.db._tables["knowledge_graph"] = table
        assert lh_handler.add_knowledge_edge("a", "b", "rel") is False


class TestLanceDBDocuments:
    def test_add_document_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.add_document("docs", "some text here") is False

    def test_add_document_empty_text(self, lh_handler):
        assert lh_handler.add_document("docs", "   ") is False

    def test_add_document_embed_failure(self, lh_handler):
        lh_handler.embed_text = MagicMock(return_value=None)
        assert lh_handler.add_document("docs", "some real text") is False

    def test_add_document_create_table(self, lh_handler):
        assert (
            lh_handler.add_document(
                "docs", "some real document text here", source="test", doc_id="d1"
            )
            is True
        )
        record = lh_handler.db._tables["docs"].added[0]
        assert record["id"] == "d1"
        assert "vector" in record

    def test_add_document_existing_table_with_extra_columns(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable()
        assert (
            lh_handler.add_document(
                "docs", "some real document text here", extra_columns={"outcome": "success"}
            )
            is True
        )
        record = lh_handler.db._tables["docs"].added[0]
        assert record["outcome"] == "success"

    def test_add_document_redaction(self, lh_handler):
        redactor = MagicMock()
        redactor.redact.return_value = MagicMock(
            has_secrets=True,
            redacted_text="REDACTED text",
            redactions=[{"type": "api_key"}],
        )
        with patch("core.secrets_redactor.get_secrets_redactor", return_value=redactor):
            assert lh_handler.add_document("docs", "sk-12345 secret here") is True
        record = lh_handler.db._tables["docs"].added[0]
        assert record["text"] == "REDACTED text"
        assert json.loads(record["metadata"]) == {
            "_redacted_types": ["api_key"],
            "_redaction_count": 1,
        }

    def test_add_document_redactor_missing(self, lh_handler):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "core.secrets_redactor":
                raise ImportError("no redactor")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            assert lh_handler.add_document("docs", "some real document text here") is True

    def test_add_document_redactor_error(self, lh_handler):
        redactor = MagicMock()
        redactor.redact.side_effect = Exception("boom")
        with patch("core.secrets_redactor.get_secrets_redactor", return_value=redactor):
            assert lh_handler.add_document("docs", "some real document text here") is True

    def test_add_document_table_add_error(self, lh_handler):
        table = FakeLanceTable()
        table.add = MagicMock(side_effect=Exception("boom"))
        lh_handler.db._tables["docs"] = table
        assert lh_handler.add_document("docs", "some real document text here") is False

    def test_add_document_embed_error(self, lh_handler):
        lh_handler.embed_text = MagicMock(side_effect=Exception("boom"))
        assert lh_handler.add_document("docs", "some real document text here") is False

    def test_add_with_embedding_success(self, lh_handler):
        assert lh_handler._add_document_with_embedding("docs", "text here", [0.1, 0.2]) is True
        assert "docs" in lh_handler.db._tables

    def test_add_with_embedding_existing_table(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable()
        assert lh_handler._add_document_with_embedding("docs", "text", [0.1]) is True
        assert lh_handler.db._tables["docs"].added

    def test_add_with_embedding_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler._add_document_with_embedding("docs", "text", [0.1]) is False

    def test_add_with_embedding_error(self, lh_handler):
        lh_handler.get_table = MagicMock(side_effect=Exception("boom"))
        assert lh_handler._add_document_with_embedding("docs", "text", [0.1]) is False

    def test_add_documents_batch(self, lh_handler):
        n = lh_handler.add_documents_batch(
            "docs",
            [{"text": "first doc text here", "id": "1"}, {"text": "second doc here", "id": "2"}],
        )
        assert n == 2
        assert len(lh_handler.db._tables["docs"].added) == 2

    def test_add_documents_batch_skip_bad_embeddings(self, lh_handler):
        lh_handler.embed_text = MagicMock(side_effect=[None, [0.1]])
        n = lh_handler.add_documents_batch(
            "docs", [{"text": "a", "id": "1"}, {"text": "b", "id": "2"}]
        )
        assert n == 1

    def test_add_documents_batch_create_failure(self, lh_handler):
        lh_handler.db.create_table = MagicMock(side_effect=Exception("boom"))
        n = lh_handler.add_documents_batch("docs", [{"text": "some text", "id": "1"}])
        assert n == 0

    def test_add_documents_batch_existing_table(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable()
        n = lh_handler.add_documents_batch("docs", [{"text": "some text here", "id": "1"}])
        assert n == 1

    def test_add_documents_batch_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.add_documents_batch("docs", [{"text": "x"}]) == 0

    def test_add_documents_batch_error(self, lh_handler):
        lh_handler.get_table = MagicMock(side_effect=Exception("boom"))
        assert lh_handler.add_documents_batch("docs", [{"text": "x", "id": "1"}]) == 0

    def test_seed_mock_data(self, lh_handler):
        assert lh_handler.seed_mock_data([{"text": "some text here"}]) == 1


class TestLanceDBSearch:
    def test_search_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.search("docs", "query") == []

    def test_search_table_none(self, lh_handler):
        assert lh_handler.search("docs", "query") == []

    def test_search_embed_failure(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=make_rows())
        lh_handler.embed_text = MagicMock(return_value=None)
        assert lh_handler.search("docs", "query") == []

    def test_search_with_filters(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=make_rows())
        results = lh_handler.search(
            "docs", "query", user_id="u1", limit=5, filter_str="source == 'x'"
        )
        assert len(results) == 2
        assert results[0]["id"] == "d1"
        assert results[0]["score"] == 0.8
        assert results[0]["metadata"]["title"] == "Doc A"

    def test_search_metadata_none(self, lh_handler):
        rows = make_rows()
        rows[0]["metadata"] = None
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=rows)
        results = lh_handler.search("docs", "query")
        assert results[0]["metadata"] == {}

    def test_search_row_parse_error_skipped(self, lh_handler):
        rows = make_rows()
        rows[0]["metadata"] = "{bad json"
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=rows)
        results = lh_handler.search("docs", "query")
        assert len(results) == 1

    def test_search_freshness_applied(self, lh_handler):
        table = FakeLanceTable(rows=make_rows())
        lh_handler.db._tables["documents"] = table
        lh_handler.search("documents", "query")
        assert any("freshness_status" in c for c in table._calls)

    def test_search_include_stale(self, lh_handler):
        table = FakeLanceTable(rows=make_rows())
        lh_handler.db._tables["documents"] = table
        lh_handler.search("documents", "query", include_stale=True)
        assert not any("freshness_status" in c for c in table._calls)

    def test_search_freshness_disabled(self, lh_handler, monkeypatch):
        monkeypatch.setattr(lh, "FRESHNESS_FILTER_ENABLED", False)
        table = FakeLanceTable(rows=make_rows())
        lh_handler.db._tables["documents"] = table
        lh_handler.search("documents", "query")
        assert not any("freshness_status" in c for c in table._calls)

    def test_search_freshness_missing_column(self, lh_handler):
        table = FakeLanceTable(rows=make_rows(), with_freshness=False)
        lh_handler.db._tables["documents"] = table
        lh_handler.search("documents", "query")
        assert not any("freshness_status" in c for c in table._calls)

    def test_search_exception(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=make_rows())
        lh_handler.embed_text = MagicMock(side_effect=Exception("boom"))
        assert lh_handler.search("docs", "query") == []

    def test_search_workspace_filter_escaping(self, lh_handler):
        table = FakeLanceTable(rows=make_rows())
        lh_handler.db._tables["docs"] = table
        lh_handler.workspace_id = "o'brien"
        lh_handler.search("docs", "query")
        assert any("o''brien" in c for c in table._calls)

    def test_get_document_by_id_found(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=make_rows())
        doc = lh_handler.get_document_by_id("docs", "d1")
        assert doc is not None
        assert doc["id"] == "d1"

    def test_get_document_by_id_not_found(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=[])
        assert lh_handler.get_document_by_id("docs", "d1") is None

    def test_get_document_by_id_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.get_document_by_id("docs", "d1") is None

    def test_get_document_by_id_metadata_invalid(self, lh_handler):
        rows = make_rows()
        rows[0]["metadata"] = "{broken json"
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=rows)
        doc = lh_handler.get_document_by_id("docs", "d1")
        assert doc["metadata"] == {}

    def test_get_document_by_id_metadata_none(self, lh_handler):
        rows = make_rows()
        rows[0]["metadata"] = None
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=rows)
        doc = lh_handler.get_document_by_id("docs", "d1")
        assert doc["metadata"] == {}

    def test_list_documents(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=make_rows())
        docs = lh_handler.list_documents("docs", limit=10, offset=0)
        assert len(docs) == 2
        assert docs[0]["id"] == "d1"
        assert docs[0]["title"] == "Doc A"
        assert docs[0]["text_preview"] == "Alpha beta gamma delta epsilon"

    def test_list_documents_empty(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=[])
        assert lh_handler.list_documents("docs") == []

    def test_list_documents_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler.list_documents("docs") == []

    def test_list_documents_offset(self, lh_handler):
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=make_rows())
        docs = lh_handler.list_documents("docs", limit=1, offset=1)
        assert len(docs) == 1
        assert docs[0]["id"] == "d2"

    def test_list_documents_untitled(self, lh_handler):
        rows = make_rows()
        rows[0]["metadata"] = json.dumps({})
        rows[0]["source"] = "the-source"
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=rows)
        docs = lh_handler.list_documents("docs")
        assert docs[0]["title"] == "the-source"

    def test_list_documents_no_created_at(self, lh_handler):
        rows = make_rows()
        for r in rows:
            r.pop("created_at", None)
        lh_handler.db._tables["docs"] = FakeLanceTable(rows=rows)
        assert len(lh_handler.list_documents("docs")) == 2

    def test_query_knowledge_graph_no_exclusion(self, lh_handler):
        lh_handler.db._tables["knowledge_graph"] = FakeLanceTable(rows=make_rows())
        results = lh_handler.query_knowledge_graph("query")
        assert len(results) == 2

    def test_query_knowledge_graph_exclusion(self, lh_handler):
        lh_handler.db._tables["knowledge_graph"] = FakeLanceTable(rows=make_rows())
        results = lh_handler.query_knowledge_graph("query", exclude_source_doc_ids={"d1"})
        assert len(results) == 1
        assert results[0]["id"] == "d2"

    def test_query_knowledge_graph_metadata_not_dict(self, lh_handler):
        rows = make_rows()
        rows[0]["metadata"] = {"title": "Doc A"}
        lh_handler.db._tables["knowledge_graph"] = FakeLanceTable(rows=rows)
        results = lh_handler.query_knowledge_graph("query", exclude_source_doc_ids={"d1"})
        assert len(results) == 2


class TestLanceDBDualVector:
    @pytest.mark.asyncio
    async def test_add_embedding_success(self, lh_handler):
        lh_handler.db._tables["episodes"] = FakeLanceTable()
        assert await lh_handler.add_embedding("episodes", "e1", [0.1] * 1536) is True
        assert lh_handler.db._tables["episodes"].added[0]["id"] == "e1"

    @pytest.mark.asyncio
    async def test_add_embedding_creates_table(self, lh_handler):
        assert await lh_handler.add_embedding("new_table", "e1", [0.1] * 1536) is True

    @pytest.mark.asyncio
    async def test_add_embedding_unknown_column(self, lh_handler):
        with pytest.raises(ValueError):
            await lh_handler.add_embedding("episodes", "e1", [0.1], vector_column="nope")

    @pytest.mark.asyncio
    async def test_add_embedding_dim_mismatch(self, lh_handler):
        with pytest.raises(ValueError):
            await lh_handler.add_embedding("episodes", "e1", [0.1, 0.2])

    @pytest.mark.asyncio
    async def test_add_embedding_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert await handler.add_embedding("episodes", "e1", [0.1] * 1536) is False

    @pytest.mark.asyncio
    async def test_add_embedding_create_failure(self, lh_handler):
        lh_handler.get_table = MagicMock(return_value=None)
        lh_handler.create_table = MagicMock(return_value=None)
        assert await lh_handler.add_embedding("new_table", "e1", [0.1] * 1536) is False

    @pytest.mark.asyncio
    async def test_add_embedding_error(self, lh_handler):
        table = FakeLanceTable()
        table.add = MagicMock(side_effect=Exception("boom"))
        lh_handler.db._tables["episodes"] = table
        assert await lh_handler.add_embedding("episodes", "e1", [0.1] * 1536) is False

    @pytest.mark.asyncio
    async def test_similarity_search(self, lh_handler):
        rows = [{"id": "e1", "_distance": 0.1}, {"id": "e2", "_distance": 0.6}]
        lh_handler.db._tables["episodes"] = FakeLanceTable(rows=rows)
        results = await lh_handler.similarity_search("episodes", [0.1] * 1536, top_k=2)
        assert len(results) == 2
        assert results[0]["episode_id"] == "e1"
        assert results[0]["score"] == 0.9
        assert results[0]["vector_column"] == "vector"

    @pytest.mark.asyncio
    async def test_similarity_search_table_none(self, lh_handler):
        assert await lh_handler.similarity_search("episodes", [0.1] * 1536) == []

    @pytest.mark.asyncio
    async def test_similarity_search_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert await handler.similarity_search("episodes", [0.1] * 1536) == []

    @pytest.mark.asyncio
    async def test_similarity_search_unknown_column(self, lh_handler):
        with pytest.raises(ValueError):
            await lh_handler.similarity_search("episodes", [0.1], vector_column="nope")

    @pytest.mark.asyncio
    async def test_similarity_search_dim_mismatch(self, lh_handler):
        with pytest.raises(ValueError):
            await lh_handler.similarity_search("episodes", [0.1])

    @pytest.mark.asyncio
    async def test_get_embedding(self, lh_handler):
        rows = [{"id": "e1", "vector": [0.1, 0.2, 0.3], "_distance": 0.5}]
        lh_handler.db._tables["episodes"] = FakeLanceTable(rows=rows)
        assert await lh_handler.get_embedding("episodes", "e1") == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_get_embedding_not_found(self, lh_handler):
        lh_handler.db._tables["episodes"] = FakeLanceTable(rows=[])
        assert await lh_handler.get_embedding("episodes", "e1") is None

    @pytest.mark.asyncio
    async def test_get_embedding_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert await handler.get_embedding("episodes", "e1") is None

    @pytest.mark.asyncio
    async def test_get_embedding_error(self, lh_handler):
        table = FakeLanceTable(rows=[{"id": "e1"}])
        table.to_pandas = MagicMock(side_effect=Exception("boom"))
        lh_handler.db._tables["episodes"] = table
        assert await lh_handler.get_embedding("episodes", "e1") is None


class TestChatHistoryManager:
    @pytest.fixture
    def manager(self, lh_handler):
        return ChatHistoryManager(lh_handler)

    def test_ensure_table_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        mgr = ChatHistoryManager(handler)
        assert mgr.table_name == "chat_messages"

    def test_ensure_table_creates(self, manager):
        assert "chat_messages" in manager.db.db._tables

    def test_ensure_table_error(self, manager):
        manager.db.db.create_table = MagicMock(side_effect=Exception("boom"))
        manager._ensure_table()

    def test_save_message_success(self, manager):
        manager.db.db._tables["chat_messages"] = FakeLanceTable()
        assert manager.save_message("s1", "u1", "user", "hello there") is True
        assert manager.db.db._tables["chat_messages"].added

    def test_save_message_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        mgr = ChatHistoryManager(handler)
        assert mgr.save_message("s1", "u1", "user", "hi") is False

    def test_escape_like(self):
        # Hardened escaping: backslash, quote, and LIKE wildcards %/_ are all
        # escaped so session_id values match literally inside LIKE filters.
        assert ChatHistoryManager._escape_like("a'b\\c%d") == "a''b\\\\c\\%d"

    def test_get_session_history(self, manager):
        rows = [
            {
                "id": "m1",
                "text": "hello",
                "created_at": "2026-01-01T00:00:00+00:00",
                "metadata": json.dumps({"session_id": "s1", "role": "user"}),
            },
            {
                "id": "m2",
                "text": "world",
                "created_at": "2026-01-02T00:00:00+00:00",
                "metadata": json.dumps({"session_id": "s1", "role": "assistant"}),
            },
            {
                "id": "m3",
                "text": "other",
                "created_at": "2026-01-03T00:00:00+00:00",
                "metadata": json.dumps({"session_id": "s1other", "role": "user"}),
            },
        ]
        manager.db.db._tables["chat_messages"] = FakeLanceTable(rows=rows)
        msgs = manager.get_session_history("s1")
        assert [m["id"] for m in msgs] == ["m1", "m2"]

    def test_get_session_history_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        mgr = ChatHistoryManager(handler)
        assert mgr.get_session_history("s1") == []

    def test_get_session_history_error(self, manager):
        table = FakeLanceTable()
        table.to_pandas = MagicMock(side_effect=Exception("boom"))
        manager.db.db._tables["chat_messages"] = table
        assert manager.get_session_history("s1") == []

    def test_search_relevant_context_with_session(self, manager):
        rows = [
            {
                "id": "m1",
                "text": "hello",
                "source": "chat_user",
                "created_at": "t1",
                "metadata": json.dumps({"session_id": "s1", "role": "user"}),
            },
            {
                "id": "m2",
                "text": "leak",
                "source": "chat_user",
                "created_at": "t2",
                "metadata": json.dumps({"session_id": "s1other", "role": "user"}),
            },
        ]
        manager.db.db._tables["chat_messages"] = FakeLanceTable(rows=rows)
        results = manager.search_relevant_context("hello", session_id="s1")
        assert len(results) == 1
        assert results[0]["id"] == "m1"

    def test_search_relevant_context_no_session(self, manager):
        rows = [
            {
                "id": "m1",
                "text": "hello",
                "source": "chat_user",
                "created_at": "t1",
                "metadata": json.dumps({}),
            }
        ]
        manager.db.db._tables["chat_messages"] = FakeLanceTable(rows=rows)
        assert len(manager.search_relevant_context("hello")) == 1

    def test_search_relevant_context_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        mgr = ChatHistoryManager(handler)
        assert mgr.search_relevant_context("hello") == []

    def test_get_entity_mentions(self, manager):
        rows = [
            {
                "id": "m1",
                "text": "hello",
                "created_at": "t1",
                "metadata": json.dumps({"workflow_id": "wf1", "session_id": "s1"}),
            },
            {
                "id": "m2",
                "text": "other",
                "created_at": "t2",
                "metadata": json.dumps({"workflow_id": "wf2"}),
            },
        ]
        manager.db.db._tables["chat_messages"] = FakeLanceTable(rows=rows)
        msgs = manager.get_entity_mentions("workflow_id", "wf1")
        assert len(msgs) == 1

    def test_get_entity_mentions_session_filter(self, manager):
        rows = [
            {
                "id": "m1",
                "text": "hello",
                "created_at": "t1",
                "metadata": json.dumps({"workflow_id": "wf1", "session_id": "s1"}),
            },
            {
                "id": "m2",
                "text": "other",
                "created_at": "t2",
                "metadata": json.dumps({"workflow_id": "wf1", "session_id": "s2"}),
            },
        ]
        manager.db.db._tables["chat_messages"] = FakeLanceTable(rows=rows)
        msgs = manager.get_entity_mentions("workflow_id", "wf1", session_id="s1")
        assert len(msgs) == 1

    def test_get_entity_mentions_db_none(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        mgr = ChatHistoryManager(handler)
        assert mgr.get_entity_mentions("workflow_id", "wf1") == []

    def test_get_entity_mentions_no_table(self, manager):
        assert manager.get_entity_mentions("workflow_id", "wf1") == []

    def test_get_entity_mentions_parse_error(self, manager):
        rows = [{"id": "m1", "text": "hello", "created_at": "t1", "metadata": "{bad"}]
        manager.db.db._tables["chat_messages"] = FakeLanceTable(rows=rows)
        assert manager.get_entity_mentions("workflow_id", "wf1") == []


class TestLanceDBModuleFunctions:
    def test_get_lancedb_handler_with_db_not_cached(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lh, "LLMService", _FakeLLMService)
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        h1 = get_lancedb_handler("ws-unique-1", tenant_id="t1", db=MagicMock())
        h2 = get_lancedb_handler("ws-unique-1", tenant_id="t1", db=MagicMock())
        assert h1 is not h2
        assert h1.workspace_id == "ws-unique-1"
        assert h1.tenant_id == "t1"

    def test_get_lancedb_handler_cached(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lh, "LLMService", _FakeLLMService)
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        h1 = get_lancedb_handler("ws-cached-1")
        h2 = get_lancedb_handler("ws-cached-1")
        assert h1 is h2

    def test_get_lancedb_handler_default_shared(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lh, "LLMService", _FakeLLMService)
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        h1 = get_lancedb_handler(None)
        assert h1.workspace_id == "default_shared"

    def test_get_chat_history_manager(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lh, "LLMService", _FakeLLMService)
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        mgr = lh.get_chat_history_manager("ws-chm-1")
        assert isinstance(mgr, ChatHistoryManager)

    def test_get_chat_context_manager(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lh, "LLMService", _FakeLLMService)
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        ctx = lh.get_chat_context_manager("ws-ccm-1")
        assert ctx is not None

    def test_embed_documents_batch_not_available(self, monkeypatch):
        monkeypatch.setattr(lh, "SENTENCE_TRANSFORMERS_AVAILABLE", False)
        assert lh.embed_documents_batch(["a", "b"]) is None

    def test_embed_documents_batch_error(self, monkeypatch):
        monkeypatch.setattr(lh, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
        fake_mod = types.ModuleType("sentence_transformers")

        class _Boom:
            def __init__(self, *a, **k):
                raise RuntimeError("model load failed")

        fake_mod.SentenceTransformer = _Boom
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)
        assert lh.embed_documents_batch(["a"]) is None

    def test_create_memory_schema(self):
        schema = lh.create_memory_schema(vector_size=384)
        assert schema["id"] is str
        assert schema["text"] is str
        assert schema["metadata"] is str
