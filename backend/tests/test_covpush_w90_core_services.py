# -*- coding: utf-8 -*-
"""Coverage wave 90 — core.lancedb_handler (main gap: 16%) plus residual
error branches in core.atom_saas_client.

No network, no LLM, no real LanceDB writes: every external boundary is
mocked (LLMService embeddings, the lancedb connection object, HTTP).

Re-collects the established waves for the other target modules so this file
alone reaches the >=80% bar (same star-import pattern as wave 89):

* fleet_coordinator_service — tests/test_covpush_w64_fleet_coordinator.py
* office_service            — tests/test_covpush_w61_office_service.py
* atom_saas_client          — tests/test_covpush_w31_saas_client.py +
                              tests/test_atom_saas_client.py
* lancedb_handler (conn)    — tests/test_lancedb_handler_connection_leak.py

New coverage here focuses on core.lancedb_handler: table CRUD, search with
filter/freshness branches, batch embedding, knowledge-graph edges, chat
history manager, workspace handler cache, cold-storage (S3/R2) init
branches, and error paths — with the LanceDB connection fully mocked.
"""
import asyncio
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import httpx
import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Extend the established waves (collection only — no duplication).
# ---------------------------------------------------------------------------
from tests.test_covpush_w64_fleet_coordinator import *  # noqa: F401,F403
from tests.test_covpush_w61_office_service import *  # noqa: F401,F403
from tests.test_covpush_w31_saas_client import *  # noqa: F401,F403
from tests.test_atom_saas_client import *  # noqa: F401,F403
from tests.test_lancedb_handler_connection_leak import *  # noqa: F401,F403

import core.lancedb_handler as lancedb_mod
from core.lancedb_handler import (
    ChatHistoryManager,
    LanceDBHandler,
    MockEmbedder,
    create_memory_schema,
    embed_documents_batch,
    get_chat_history_manager,
    get_lancedb_handler,
)
from core.atom_saas_client import AtomAgentOSMarketplaceClient, AtomSaaSConfig


# =========================================================================== #
# atom_saas_client — residual error/branch lines (292-294, 313, 352, 370-372,
# 386-388, 588-590)
# =========================================================================== #

def _saas_client_with_http_error(method_url_pair=None):
    client = AtomAgentOSMarketplaceClient(AtomSaaSConfig(
        ws_url="wss://example.com/ws", api_url="https://example.com/api",
        api_token="tok", instance_id="inst"))
    http = MagicMock()
    http.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    http.delete = AsyncMock(side_effect=httpx.ConnectError("boom"))
    client._http_client = http
    return client


class TestW90SaasResidual:
    async def test_fetch_workflows_with_category_and_error(self):
        client = _saas_client_with_http_error()
        out = await client.fetch_workflows(query="q", category="cat")
        assert out == {"workflows": [], "total": 0, "page": 1, "page_size": 20}

    async def test_fetch_domains_with_category_and_error(self):
        client = _saas_client_with_http_error()
        out = await client.fetch_domains(query="q", category="cat")
        assert out == {"domains": [], "total": 0, "page": 1, "page_size": 20}

    async def test_install_agent_http_error(self):
        client = _saas_client_with_http_error()
        out = await client.install_agent("tpl-1", "tenant-1")
        assert out["success"] is False

    async def test_get_domain_template_http_error(self):
        client = _saas_client_with_http_error()
        assert await client.get_domain_template("dom-1") is None

    async def test_install_domain_http_error(self):
        client = _saas_client_with_http_error()
        out = await client.install_domain("dom-1", "tenant-1")
        assert out["success"] is False

    async def test_install_component_http_error(self):
        client = _saas_client_with_http_error()
        out = await client.install_component("comp-1", "canvas-1")
        assert out["success"] is False


# =========================================================================== #
# lancedb_handler — helpers
# =========================================================================== #

def _embed_service(dim=4, value=0.1, side_effect=None):
    svc = MagicMock()
    if side_effect is not None:
        svc.generate_embedding = AsyncMock(side_effect=side_effect)
    else:
        svc.generate_embedding = AsyncMock(return_value=[value] * dim)
    return svc


def _make_handler(tmp_path=None, workspace_id="ws1", tenant_id="t1", db_path=None):
    """Build a handler with LLMService neutered; db left None."""
    with patch.object(lancedb_mod, "LLMService", side_effect=lambda *a, **k: None):
        h = LanceDBHandler(
            db_path=db_path or (str(tmp_path / "db") if tmp_path else None),
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            db=None,
        )
    return h


class MockLanceDB:
    """In-memory stand-in for the lancedb connection object."""

    def __init__(self):
        self.tables = {}
        self.dropped = []
        self.connect_kwargs = None

    def table_names(self):
        return list(self.tables)

    def open_table(self, name):
        return self.tables[name]

    def create_table(self, name, schema=None, data=None, mode=None):
        table = self.tables.get(name)
        if table is None:
            table = _table_mock()
            self.tables[name] = table
        table.last_create = (schema, data, mode)
        return table

    def drop_table(self, name):
        self.dropped.append(name)
        self.tables.pop(name, None)


def _table_mock(df=None, schema_names=None):
    t = MagicMock()
    chain = MagicMock()
    if df is not None:
        chain.to_pandas.return_value = df
    else:
        chain.to_pandas.return_value = pd.DataFrame()
    chain.limit.return_value = chain
    chain.where.return_value = chain
    t.search.return_value = chain
    if schema_names is not None:
        t.schema = [SimpleNamespace(name=n) for n in schema_names]
    return t


def _handler_with_db(tmp_path, tables=None, embed_dim=4):
    h = _make_handler(tmp_path)
    h.db = MockLanceDB()
    for name, table in (tables or {}).items():
        h.db.tables[name] = table
    h.embedding_service = _embed_service(dim=embed_dim)
    return h


# =========================================================================== #
# lancedb_handler — construction & MockEmbedder
# =========================================================================== #

class TestW90Init:
    def test_defaults(self, tmp_path):
        h = _make_handler(tmp_path)
        assert h.workspace_id == "ws1"
        assert h.tenant_id == "t1"
        assert h.vector_columns == {"vector": 1536, "vector_fastembed": 384}
        assert h.embedder is None
        assert h.db is None

    def test_env_overrides_provider(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
        monkeypatch.setenv("EMBEDDING_MODEL", "bge-small")
        h = _make_handler(tmp_path)
        assert h.embedding_provider == "fastembed"
        assert h.embedding_model == "bge-small"

    def test_mock_embedder_numpy(self):
        vec = MockEmbedder(8).encode("hello", convert_to_numpy=True)
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (8,)

    def test_mock_embedder_no_numpy(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "numpy", None)
        vec = MockEmbedder(6).encode("hello")
        assert len(vec) == 6


# =========================================================================== #
# _initialize_db — local + S3/R2 cold-storage branches
# =========================================================================== #

class TestW90InitializeDb:
    def test_local_connect_success(self, tmp_path):
        h = _make_handler(tmp_path)
        h._initialize_db()
        assert h.db is not None  # real lancedb connect on local dir

    def test_local_connect_failure(self, tmp_path, monkeypatch):
        import lancedb as real_lancedb
        h = _make_handler(tmp_path, db_path=str(tmp_path / "db"))
        with patch.object(real_lancedb, "connect", side_effect=OSError("nope")):
            h._initialize_db()
        assert h.db is None

    def test_s3_downgraded_when_cloud_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", False)
        monkeypatch.setattr(lancedb_mod, "LOCAL_DB_PATH_FALLBACK", str(tmp_path / "fallback"))
        import lancedb as real_lancedb
        h = _make_handler(db_path="s3://bucket/db")
        with patch.object(real_lancedb, "connect", return_value=object()) as connect:
            h._initialize_db()
            assert not str(connect.call_args[0][0]).startswith("s3://")
        assert h.db is not None

    def _run_s3_cloud_init(self, tmp_path, monkeypatch, env):
        monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", True)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        import lancedb as real_lancedb
        h = _make_handler(db_path="s3://bucket/db")
        with patch.object(real_lancedb, "connect", return_value=object()) as connect:
            h._initialize_db()
        opts = connect.call_args.kwargs.get("storage_options") or {}
        return h, opts

    def test_s3_cloud_endpoint_and_creds(self, tmp_path, monkeypatch):
        h, opts = self._run_s3_cloud_init(tmp_path, monkeypatch, {
            "S3_ENDPOINT": "https://r2.example.com",
            "R2_ACCESS_KEY_ID": "key12345678",
            "R2_SECRET_ACCESS_KEY": "secret",
        })
        assert h.db is not None
        assert opts["endpoint"] == "https://r2.example.com"
        assert opts["aws_access_key_id"] == "key12345678"
        assert opts["region"] == "auto"

    def test_s3_cloud_account_id_autoconstructed(self, tmp_path, monkeypatch):
        h, opts = self._run_s3_cloud_init(tmp_path, monkeypatch, {
            "CLOUDFLARE_R2_ACCOUNT_ID": "acct123",
            "R2_ACCESS_KEY_ID": "keyabcd1234",
            "R2_SECRET_ACCESS_KEY": "secret",
        })
        assert opts["endpoint"] == "https://acct123.r2.cloudflarestorage.com"

    def test_s3_cloud_missing_endpoint_and_creds(self, tmp_path, monkeypatch):
        for var in ("S3_ENDPOINT", "R2_ENDPOINT", "AWS_ENDPOINT_URL",
                    "AWS_S3_ENDPOINT", "CLOUDFLARE_R2_ACCOUNT_ID",
                    "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(var, raising=False)
        h, opts = self._run_s3_cloud_init(tmp_path, monkeypatch, {})
        assert "endpoint" not in opts
        assert "aws_access_key_id" not in opts
        assert h.db is not None


# =========================================================================== #
# test_connection / create_table / get_table / drop_table
# =========================================================================== #

class TestW90TableCrud:
    def test_connection_not_available(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        out = h.test_connection()
        assert out["connected"] is False

    def test_connection_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", True)
        h = _make_handler(tmp_path)
        h._initialize_db = lambda: None  # keep db None
        out = h.test_connection()
        assert out["connected"] is False

    def test_connection_success(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.db.tables["t"] = _table_mock()
        out = h.test_connection()
        assert out["connected"] is True
        assert "t" in out["tables"]

    def test_connection_raises(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.db.table_names = Mock(side_effect=RuntimeError("boom"))
        out = h.test_connection()
        assert out["connected"] is False

    def test_create_table_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h.create_table("t") is None

    def test_create_table_default_schema(self, tmp_path):
        h = _handler_with_db(tmp_path)
        t = h.create_table("docs")
        assert t is not None
        schema = h.db.tables["docs"].last_create[0]
        names = [f.name for f in schema]
        assert "vector" in names and "text" in names

    def test_create_table_knowledge_graph_schema(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.create_table("knowledge_graph")
        names = [f.name for f in h.db.tables["knowledge_graph"].last_create[0]]
        assert {"from_id", "to_id", "type"} <= set(names)

    def test_create_table_dual_vector(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.create_table("dual", dual_vector=True)
        names = [f.name for f in h.db.tables["dual"].last_create[0]]
        assert "vector_fastembed" in names

    def test_create_table_custom_schema(self, tmp_path):
        import pyarrow as pa
        h = _handler_with_db(tmp_path)
        t = h.create_table("custom", schema=pa.schema([pa.field("x", pa.int64())]))
        assert t is not None

    def test_create_table_exception(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.db.create_table = Mock(side_effect=RuntimeError("nope"))
        assert h.create_table("bad") is None

    def test_get_table_found_and_missing(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"there": _table_mock()})
        assert h.get_table("there") is not None
        assert h.get_table("missing") is None

    def test_get_table_exception(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.db.table_names = Mock(side_effect=RuntimeError("boom"))
        assert h.get_table("x") is None

    def test_has_column(self, tmp_path):
        t = _table_mock(schema_names=["id", "freshness_status"])
        assert LanceDBHandler._has_column(t, "freshness_status") is True
        assert LanceDBHandler._has_column(t, "nope") is False
        broken = MagicMock()
        type(broken).schema = PropertyMock(side_effect=RuntimeError("x"))
        assert LanceDBHandler._has_column(broken, "x") is False

    def test_drop_table_variants(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock()})
        assert h.drop_table("t") is True
        assert h.db.dropped == ["t"]
        assert h.drop_table("other") is True  # not present — still True
        h.db.drop_table = Mock(side_effect=RuntimeError("boom"))
        h.db.tables["t2"] = _table_mock()
        assert h.drop_table("t2") is False

    def test_drop_table_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h.drop_table("t") is False


# =========================================================================== #
# embed_text / async_embed_text
# =========================================================================== #

class TestW90EmbedText:
    def test_embed_text_no_service(self, tmp_path):
        h = _make_handler(tmp_path)
        h.embedding_service = None
        assert h.embed_text("hi") is None

    async def test_embed_text_same_thread_async(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h.embed_text("hi") is None  # sync call inside running loop

    def test_embed_text_from_executor(self, tmp_path):
        h = _handler_with_db(tmp_path)
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("v", h.embed_text("hi")))
        t.start()
        t.join(timeout=10)
        assert isinstance(out["v"], np.ndarray)

    def test_embed_text_generic_failure(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.embedding_service = None
        h.async_embed_text = Mock(side_effect=RuntimeError("boom"))
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
            assert h.embed_text("hi") is None

    async def test_async_embed_no_service(self, tmp_path):
        h = _make_handler(tmp_path)
        h.embedding_service = None
        assert await h.async_embed_text("x") is None

    async def test_async_embed_success(self, tmp_path):
        h = _handler_with_db(tmp_path)
        vec = await h.async_embed_text("x")
        assert isinstance(vec, np.ndarray)

    async def test_async_embed_failure(self, tmp_path):
        h = _make_handler(tmp_path)
        h.embedding_service = _embed_service(side_effect=RuntimeError("boom"))
        assert await h.async_embed_text("x") is None


# =========================================================================== #
# knowledge-graph edges & add_document family
# =========================================================================== #

class TestW90KnowledgeEdge:
    def test_db_none(self, tmp_path):
        h = _make_handler(tmp_path)
        assert h.add_knowledge_edge("a", "b", "rel") is False

    def test_create_fails(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.create_table = Mock(return_value=None)
        assert h.add_knowledge_edge("a", "b", "rel") is False

    def test_success_with_embedding(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h.add_knowledge_edge("a", "b", "causes", description="d", metadata={"m": 1}) is True
        rec = h.db.tables["knowledge_graph"].add.call_args[0][0][0]
        assert rec["from_id"] == "a" and rec["type"] == "causes"

    def test_success_zero_vector_fallback(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.embedding_service = None  # embed_text -> None -> zero vector
        assert h.add_knowledge_edge("a", "b", "rel") is True

    def test_add_raises(self, tmp_path):
        h = _handler_with_db(tmp_path)
        table = _table_mock()
        table.add = Mock(side_effect=RuntimeError("boom"))
        h.db.tables["knowledge_graph"] = table
        assert h.add_knowledge_edge("a", "b", "rel") is False


class TestW90AddDocument:
    def test_db_stays_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h.add_document("t", "text") is False

    def test_empty_text_skipped(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h.add_document("t", "   ") is False

    def test_embed_none(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.embedding_service = None
        assert h.add_document("t", "text") is False

    def test_creates_inferred_table(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h.add_document("newtable", "hello", source="s",
                              metadata={"a": 1}, doc_id="d1",
                              extra_columns={"outcome": "pass"}) is True
        data = h.db.tables["newtable"].last_create[1]
        assert data[0]["outcome"] == "pass"

    def test_adds_to_existing(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock()})
        assert h.add_document("t", "hello") is True
        h.db.tables["t"].add.assert_called_once()

    def test_inner_add_raises(self, tmp_path):
        table = _table_mock()
        table.add = Mock(side_effect=RuntimeError("boom"))
        h = _handler_with_db(tmp_path, tables={"t": table})
        assert h.add_document("t", "hello") is False

    def test_outer_raises(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.add_document("t", "hello") is False

    def test_add_document_with_embedding(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h._add_document_with_embedding("t2", "txt", [0.1, 0.2]) is True
        assert "t2" in h.db.tables

    def test_add_document_with_embedding_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h._add_document_with_embedding("t", "txt", [0.1]) is False


class TestW90Batch:
    def test_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h.add_documents_batch("t", [{"text": "x"}]) == 0

    def test_all_embeddings_fail(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.embedding_service = None
        assert h.add_documents_batch("t", [{"text": "x"}, {"text": "y"}]) == 0

    def test_creates_table(self, tmp_path):
        h = _handler_with_db(tmp_path)
        n = h.add_documents_batch("batch", [{"text": "a"}, {"text": "b", "id": "d2"}])
        assert n == 2

    def test_create_fails(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.db.create_table = Mock(side_effect=RuntimeError("boom"))
        assert h.add_documents_batch("t", [{"text": "a"}]) == 0

    def test_adds_to_existing(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock()})
        assert h.add_documents_batch("t", [{"text": "a"}]) == 1
        h.db.tables["t"].add.assert_called_once()

    def test_outer_exception(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.embed_text = Mock(side_effect=RuntimeError("boom"))
        assert h.add_documents_batch("t", [{"text": "a"}]) == 0

    def test_seed_mock_data(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.add_documents_batch = Mock(return_value=3)
        assert h.seed_mock_data([{"text": "x"}]) == 3


# =========================================================================== #
# search / get_document_by_id / list_documents
# =========================================================================== #

def _search_df():
    return pd.DataFrame({
        "id": ["1", "2", "3", "4"],
        "text": ["a", "b", "c", "d"],
        "source": ["s1", "s2", "s3", "s4"],
        "metadata": ['{"k": 1}', None, "not-json", {"dict": True}],
        "created_at": ["t1", "t2", "t3", "t4"],
        "_distance": [0.1, 0.5, 0.0, 2.0],
    })


class TestW90Search:
    def test_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h.search("t", "q") == []

    def test_table_none(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h.search("missing", "q") == []

    def test_query_embed_none(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock()})
        h.embedding_service = None
        assert h.search("t", "q") == []

    def test_search_full(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock(df=_search_df())})
        h.workspace_id = "ws'1"  # exercises quote escaping
        out = h.search("t", "q", user_id="us'er", filter_str="outcome == 'pass'")
        assert len(out) == 3  # the "not-json" metadata row is skipped
        assert out[0]["metadata"] == {"k": 1}
        assert 0.0 <= out[0]["score"] <= 1.0
        where = h.db.tables["t"].search.return_value.limit.return_value.where.call_args[0][0]
        assert "outcome == 'pass'" in where

    def test_search_freshness_filter(self, tmp_path):
        table = _table_mock(df=_search_df(), schema_names=["id", "freshness_status"])
        h = _handler_with_db(tmp_path, tables={"documents": table})
        h.search("documents", "q")
        where = table.search.return_value.limit.return_value.where.call_args[0][0]
        assert "freshness_status == 'fresh'" in where

    def test_search_include_stale(self, tmp_path):
        table = _table_mock(df=_search_df(), schema_names=["id", "freshness_status"])
        h = _handler_with_db(tmp_path, tables={"documents": table})
        h.search("documents", "q", include_stale=True)
        where = table.search.return_value.limit.return_value.where.call_args[0][0]
        assert "freshness_status" not in where

    def test_search_no_workspace_no_user(self, tmp_path):
        table = _table_mock(df=_search_df())
        h = _handler_with_db(tmp_path, tables={"t": table})
        h.workspace_id = None
        h.search("t", "q")
        table.search.return_value.limit.return_value.where.assert_not_called()

    def test_search_pandas_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "PANDAS_AVAILABLE", False)
        table = _table_mock(df=_search_df())
        h = _handler_with_db(tmp_path, tables={"t": table})
        assert h.search("t", "q") == []

    def test_search_exception(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.embed_text = Mock(side_effect=RuntimeError("boom"))
        assert h.search("t", "q") == []

    def test_query_knowledge_graph_no_exclusions(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.search = Mock(return_value=[{"metadata": {"doc_id": "d1"}}])
        out = h.query_knowledge_graph("q")
        assert out == [{"metadata": {"doc_id": "d1"}}]

    def test_query_knowledge_graph_exclusions(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.search = Mock(return_value=[
            {"metadata": {"doc_id": "d1"}},
            {"metadata": {"doc_id": "d2"}},
            {"metadata": None},
            {"metadata": "str"},
        ])
        out = h.query_knowledge_graph("q", exclude_source_doc_ids={"d1"})
        doc_ids = {r["metadata"].get("doc_id")
                   for r in out if isinstance(r["metadata"], dict)}
        assert doc_ids == {"d2"}
        assert len(out) == 3  # None/"str" metadata kept (no doc_id to match)


class TestW90GetDocument:
    def _handler(self, tmp_path, df):
        table = _table_mock(df=df)
        return _handler_with_db(tmp_path, tables={"t": table}), table

    def test_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h.get_document_by_id("t", "x") is None

    def test_table_none(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h.get_document_by_id("missing", "x") is None

    def test_not_found(self, tmp_path):
        h, _ = self._handler(tmp_path, pd.DataFrame())
        assert h.get_document_by_id("t", "x") is None

    def test_found_metadata_variants(self, tmp_path):
        df = pd.DataFrame({
            "id": ["a'b", "d2"],
            "text": ["t1", "t2"],
            "source": ["s", "s"],
            "metadata": ['{"m": 1}', "bad-json"],
            "created_at": ["t", "t"],
            "vector": [[0.1], [0.2]],
        })
        h, table = self._handler(tmp_path, df)
        doc = h.get_document_by_id("t", "a'b")
        assert doc["metadata"] == {"m": 1}
        where = table.search.return_value.where.call_args[0][0]
        assert "a''b" in where
        # Bad-JSON metadata falls back to {} (mock returns full df; row 0 only).
        df_bad = pd.DataFrame({
            "id": ["d9"], "text": ["t"], "source": ["s"],
            "metadata": ["bad-json"], "created_at": ["t"], "vector": [[0.1]],
        })
        h2, _ = self._handler(tmp_path, df_bad)
        assert h2.get_document_by_id("t", "d9")["metadata"] == {}

    def test_exception(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.get_document_by_id("t", "x") is None


class TestW90ListDocuments:
    def test_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert h.list_documents("t") == []

    def test_table_none(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert h.list_documents("missing") == []

    def test_empty_df(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock()})
        assert h.list_documents("t") == []

    def test_listing(self, tmp_path):
        df = pd.DataFrame({
            "id": ["1", "2", "3"],
            "text": ["aaa", "bbb", "ccc"],
            "source": ["s1", "s2", "s3"],
            "metadata": ['{"title": "T"}', None, "bad"],
            "created_at": ["2024-01-01", "2024-01-03", "2024-01-02"],
        })
        h = _handler_with_db(tmp_path, tables={"t": _table_mock(df=df)})
        docs = h.list_documents("t", limit=2, offset=1)
        # Sorted desc (01-03, 01-02, 01-01) then offset 1, limit 2:
        assert [d["created_at"] for d in docs] == ["2024-01-02", "2024-01-01"]

    def test_exception(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.list_documents("t") == []


# =========================================================================== #
# dual-vector embedding APIs
# =========================================================================== #

class TestW90DualVector:
    async def test_add_embedding_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert await h.add_embedding("t", "e1", [0.1] * 1536) is False

    async def test_add_embedding_unknown_column(self, tmp_path):
        h = _handler_with_db(tmp_path)
        with pytest.raises(ValueError):
            await h.add_embedding("t", "e1", [0.1], vector_column="bogus")

    async def test_add_embedding_dim_mismatch(self, tmp_path):
        h = _handler_with_db(tmp_path)
        with pytest.raises(ValueError):
            await h.add_embedding("t", "e1", [0.1] * 10)

    async def test_add_embedding_create_fails(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.create_table = Mock(return_value=None)
        assert await h.add_embedding("t", "e1", [0.1] * 1536) is False

    async def test_add_embedding_success(self, tmp_path):
        h = _handler_with_db(tmp_path)
        ok = await h.add_embedding("t", "e1", [0.1] * 384,
                                   vector_column="vector_fastembed",
                                   metadata={"text": "hello"})
        assert ok is True

    async def test_add_embedding_generic_failure(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock()})
        h.db.tables["t"].add = Mock(side_effect=RuntimeError("boom"))
        assert await h.add_embedding("t", "e1", [0.1] * 1536) is False

    async def test_similarity_search_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert await h.similarity_search("t", [0.1] * 1536) == []

    async def test_similarity_search_unknown_column(self, tmp_path):
        h = _handler_with_db(tmp_path)
        with pytest.raises(ValueError):
            await h.similarity_search("t", [0.1], vector_column="bogus")

    async def test_similarity_search_dim_mismatch(self, tmp_path):
        h = _handler_with_db(tmp_path)
        with pytest.raises(ValueError):
            await h.similarity_search("t", [0.1] * 7)

    async def test_similarity_search_table_none(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert await h.similarity_search("missing", [0.1] * 1536) == []

    async def test_similarity_search_success(self, tmp_path):
        df = pd.DataFrame({"id": ["e1"], "_distance": [0.25]})
        h = _handler_with_db(tmp_path, tables={"t": _table_mock(df=df)})
        out = await h.similarity_search("t", [0.1] * 1536, top_k=5)
        assert out[0]["episode_id"] == "e1"
        assert out[0]["vector_column"] == "vector"
        assert abs(out[0]["score"] - 0.75) < 1e-9

    async def test_similarity_search_generic_failure(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert await h.similarity_search("t", [0.1] * 1536) == []

    async def test_get_embedding_db_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "LANCEDB_AVAILABLE", False)
        h = _make_handler(tmp_path)
        assert await h.get_embedding("t", "e1") is None

    async def test_get_embedding_table_none(self, tmp_path):
        h = _handler_with_db(tmp_path)
        assert await h.get_embedding("missing", "e1") is None

    async def test_get_embedding_not_found(self, tmp_path):
        h = _handler_with_db(tmp_path, tables={"t": _table_mock()})
        assert await h.get_embedding("t", "e1") is None

    async def test_get_embedding_success_and_missing_column(self, tmp_path):
        df = pd.DataFrame({"id": ["e1"], "vector": [np.array([0.1, 0.2])],
                           "vector_fastembed": [None]})
        h = _handler_with_db(tmp_path, tables={"t": _table_mock(df=df)})
        assert await h.get_embedding("t", "e1") == [0.1, 0.2]
        assert await h.get_embedding("t", "e1", vector_column="vector_fastembed") is None

    async def test_get_embedding_exception(self, tmp_path):
        h = _handler_with_db(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert await h.get_embedding("t", "e1") is None


# =========================================================================== #
# ChatHistoryManager
# =========================================================================== #

def _chat_history(tmp_path, tables=None):
    h = _handler_with_db(tmp_path, tables=tables)
    return ChatHistoryManager(h), h


class TestW90ChatHistory:
    def test_ensure_table_db_none(self, tmp_path):
        h = _make_handler(tmp_path)
        mgr = ChatHistoryManager(h)
        assert mgr.db.db is None

    def test_ensure_table_creates(self, tmp_path):
        mgr, _ = _chat_history(tmp_path)
        assert "chat_messages" in mgr.db.db.tables

    def test_save_message_db_none(self, tmp_path):
        h = _make_handler(tmp_path)
        mgr = ChatHistoryManager(h)
        assert mgr.save_message("s1", "u1", "user", "hi") is False

    def test_save_message_success_and_failure(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.add_document = Mock(return_value=True)
        assert mgr.save_message("s1", "u1", "user", "hi") is True
        h.add_document = Mock(return_value=False)
        assert mgr.save_message("s1", "u1", "user", "hi") is False

    def test_save_message_exception(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.add_document = Mock(side_effect=RuntimeError("boom"))
        assert mgr.save_message("s1", "u1", "user", "hi") is False

    def test_escape_like(self):
        assert ChatHistoryManager._escape_like("a\\b'c%d_e") == "a\\\\b''c\\%d\\_e"

    def test_get_session_history_db_none(self, tmp_path):
        h = _make_handler(tmp_path)
        mgr = ChatHistoryManager(h)
        assert mgr.get_session_history("s") == []

    def test_get_session_history_table_none(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.db.tables.pop("chat_messages", None)
        assert mgr.get_session_history("s") == []

    def test_get_session_history_success(self, tmp_path):
        rows = [
            ("m3", "third", "user", "2024-01-03T00:00:00"),
            ("m1", "first", "user", "2024-01-01T00:00:00"),
            ("m2", "other-session", "user", "2024-01-02T00:00:00"),
            ("m4", "bad-json", "user", "2024-01-04T00:00:00"),
        ]
        df = pd.DataFrame({
            "id": [r[0] for r in rows],
            "text": [r[1] for r in rows],
            "created_at": [r[3] for r in rows],
            "metadata": [
                json_dumps({"session_id": "sess", "role": "user"}),
                json_dumps({"session_id": "sess", "role": "user"}),
                json_dumps({"session_id": "other", "role": "user"}),
                "not-json",
            ],
        })
        table = _table_mock(df=df)
        mgr, h = _chat_history(tmp_path, tables={"chat_messages": table})
        out = mgr.get_session_history("sess", limit=10)
        # m2 is another session, m4 has bad metadata → both skipped; sorted asc.
        assert [m["id"] for m in out] == ["m1", "m3"]

    def test_get_session_history_exception(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert mgr.get_session_history("s") == []

    def test_search_relevant_context_db_none(self, tmp_path):
        h = _make_handler(tmp_path)
        mgr = ChatHistoryManager(h)
        assert mgr.search_relevant_context("q") == []

    def test_search_relevant_context_with_session(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.search = Mock(return_value=[
            {"metadata": {"session_id": "s1"}, "text": "a"},
            {"metadata": {"session_id": "s2"}, "text": "b"},
            {"metadata": "not-a-dict", "text": "c"},
        ])
        out = mgr.search_relevant_context("q", session_id="s1")
        assert len(out) == 1 and out[0]["text"] == "a"
        where = h.search.call_args.kwargs["filter_str"]
        assert "s1" in where

    def test_search_relevant_context_exception(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.search = Mock(side_effect=RuntimeError("boom"))
        assert mgr.search_relevant_context("q") == []

    def test_get_entity_mentions_db_none(self, tmp_path):
        h = _make_handler(tmp_path)
        mgr = ChatHistoryManager(h)
        assert mgr.get_entity_mentions("workflow_id", "w1") == []

    def test_get_entity_mentions_no_table(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.db.tables.pop("chat_messages", None)
        assert mgr.get_entity_mentions("workflow_id", "w1") == []

    def test_get_entity_mentions_success(self, tmp_path):
        df = pd.DataFrame({
            "id": ["m1", "m2"],
            "text": ["ran", "other"],
            "created_at": ["2024-01-02", "2024-01-01"],
            "metadata": [
                json_dumps({"workflow_id": "w1", "session_id": "s1", "role": "user"}),
                json_dumps({"workflow_id": "w9", "role": "user"}),
            ],
        })
        table = _table_mock(df=df)
        mgr, h = _chat_history(tmp_path, tables={"chat_messages": table})
        out = mgr.get_entity_mentions("workflow_id", "w1", session_id="s1")
        assert [m["id"] for m in out] == ["m1"]

    def test_get_entity_mentions_pandas_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "PANDAS_AVAILABLE", False)
        table = _table_mock(df=pd.DataFrame())
        mgr, _ = _chat_history(tmp_path, tables={"chat_messages": table})
        assert mgr.get_entity_mentions("workflow_id", "w1") == []

    def test_get_entity_mentions_exception(self, tmp_path):
        mgr, h = _chat_history(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert mgr.get_entity_mentions("workflow_id", "w1") == []


def json_dumps(obj):
    import json as _json
    return _json.dumps(obj)


# =========================================================================== #
# module-level helpers
# =========================================================================== #

class TestW90ModuleHelpers:
    def test_get_lancedb_handler_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "_workspace_handlers", {})
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        h1 = get_lancedb_handler(workspace_id="w90")
        h2 = get_lancedb_handler(workspace_id="w90")
        assert h1 is h2

    def test_get_lancedb_handler_with_db_not_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "_workspace_handlers", {})
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        h1 = get_lancedb_handler(workspace_id="w90b", db=Mock())
        h2 = get_lancedb_handler(workspace_id="w90b", db=Mock())
        assert h1 is not h2

    def test_get_chat_history_manager(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "_workspace_handlers", {})
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        mgr = get_chat_history_manager(workspace_id="w90c")
        assert isinstance(mgr, ChatHistoryManager)

    def test_embed_documents_batch_unavailable(self, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "SENTENCE_TRANSFORMERS_AVAILABLE", False)
        assert embed_documents_batch(["a"]) is None

    def test_embed_documents_batch_mocked(self, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
        fake_st = MagicMock()
        fake_st.SentenceTransformer = MagicMock(
            return_value=MagicMock(encode=Mock(return_value=np.ones((2, 3)))))
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
        out = embed_documents_batch(["a", "b"])
        assert out is not None

    def test_embed_documents_batch_exception(self, monkeypatch):
        monkeypatch.setattr(lancedb_mod, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
        fake_st = MagicMock()
        fake_st.SentenceTransformer = MagicMock(side_effect=RuntimeError("boom"))
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
        assert embed_documents_batch(["a"]) is None

    def test_create_memory_schema(self):
        schema = create_memory_schema(64)
        assert schema["id"] is str and schema["text"] is str

    def test_create_memory_schema_no_lancedb_pydantic(self, monkeypatch):
        import typing
        monkeypatch.setitem(sys.modules, "lancedb.pydantic", None)
        schema = create_memory_schema()
        assert schema["vector"] is typing.List[float]
