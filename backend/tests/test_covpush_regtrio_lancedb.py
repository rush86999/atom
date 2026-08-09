"""Coverage push for core/lancedb_handler.py."""

import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import asyncio
import numpy as np
import pytest

from core.lancedb_handler import LanceDBHandler


class _FakeLLMService4:
    def __init__(self, tenant_id=None, workspace_id=None, db=None):
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id

    async def generate_embedding(self, text):
        return [0.01, 0.02, 0.03, 0.04]


class _FakeLLMService1536:
    def __init__(self, tenant_id=None, workspace_id=None, db=None):
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id

    async def generate_embedding(self, text):
        return [0.01] * 1536


class _FakeRedactor:
    def redact(self, text):
        return SimpleNamespace(
            has_secrets=True,
            redacted_text="REDACTED TEXT",
            redactions=[{"type": "api_key"}, {"type": "password"}],
        )


def _set_1536_embedding(handler):
    handler.embedding_service.generate_embedding = AsyncMock(
        return_value=[0.01] * 1536
    )


@pytest.fixture
def lh_env(monkeypatch, tmp_path):
    monkeypatch.setattr("core.lancedb_handler.LLMService", _FakeLLMService4)
    monkeypatch.setattr("core.lancedb_config.LANCEDB_CLOUD_ENABLED", False)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
    return tmp_path


@pytest.fixture
def real_handler(lh_env):
    handler = LanceDBHandler(db_path=str(lh_env / "lancedb"), workspace_id="ws-1")
    handler._initialize_db()
    assert handler.db is not None
    return handler


class TestLanceDBMockEmbedder:
    def test_mock_embedder_numpy_path(self):
        from core.lancedb_handler import MockEmbedder

        embedder = MockEmbedder(3)
        vec = embedder.encode("hello world", convert_to_numpy=True)
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (3,)
        vec_list = embedder.encode("hello world")
        assert len(vec_list) == 3

    def test_mock_embedder_no_numpy_path(self):
        from core.lancedb_handler import MockEmbedder

        embedder = MockEmbedder(3)
        saved = sys.modules.get("numpy")
        sys.modules["numpy"] = None
        try:
            vec = embedder.encode("hello", convert_to_numpy=True)
        finally:
            if saved is None:
                del sys.modules["numpy"]
            else:
                sys.modules["numpy"] = saved
        assert len(vec) == 3
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_deprecated_init_helpers(self, lh_env):
        handler = LanceDBHandler(db_path=str(lh_env / "x"))
        assert handler._initialize_embedder() is None
        assert handler._init_local_embedder() is None


class TestLanceDBRealTableOps:
    def test_create_table_knowledge_graph_schema(self, real_handler):
        assert real_handler.create_table("knowledge_graph") is not None
        names = {f.name for f in real_handler.db.open_table("knowledge_graph").schema}
        assert {"from_id", "to_id", "type"} <= names

    def test_create_table_dual_vector(self, real_handler):
        assert real_handler.create_table("dual", vector_size=4, dual_vector=True) is not None
        names = {f.name for f in real_handler.db.open_table("dual").schema}
        assert "vector_fastembed" in names

    def test_create_table_custom_schema(self, real_handler):
        import pyarrow as pa

        schema = pa.schema([pa.field("id", pa.string()), pa.field("vector", pa.list_(pa.float32(), 4))])
        table = real_handler.create_table("custom", schema=schema)
        assert table is not None

    def test_get_table_existing_and_missing(self, real_handler):
        real_handler.create_table("docs_t", vector_size=4)
        assert real_handler.get_table("docs_t") is not None
        assert real_handler.get_table("nope") is None

    def test_get_table_exception(self, real_handler):
        real_handler.db.table_names = Mock(side_effect=RuntimeError("boom"))
        assert real_handler.get_table("docs_t") is None

    def test_drop_table(self, real_handler):
        real_handler.create_table("dropme", vector_size=4)
        assert real_handler.drop_table("dropme") is True
        assert "dropme" not in real_handler.db.table_names()
        assert real_handler.drop_table("dropme") is True

    def test_drop_table_exception(self, real_handler):
        real_handler.create_table("dropme2", vector_size=4)
        real_handler.db.drop_table = Mock(side_effect=RuntimeError("boom"))
        assert real_handler.drop_table("dropme2") is False


class TestLanceDBEmbedding:
    @pytest.mark.asyncio
    async def test_embed_text_from_async_context_warns(self, real_handler):
        assert real_handler.embed_text("hello") is None

    @pytest.mark.asyncio
    async def test_embed_text_other_thread_loop_path(self, real_handler):
        # The handler's "other thread" path calls asyncio.run(), which cannot
        # run inside pytest's async context — exercise it on a real thread.
        fake_loop = SimpleNamespace(_thread_id=-1)
        with patch("asyncio.get_running_loop", return_value=fake_loop):
            out = await asyncio.to_thread(real_handler.embed_text, "hello")
        assert out is not None
        assert isinstance(out, np.ndarray)

    def test_embed_text_asyncio_run_failure(self, real_handler):
        with patch("asyncio.run", side_effect=RuntimeError("no loop")):
            assert real_handler.embed_text("hello") is None

    @pytest.mark.asyncio
    async def test_async_embed_text_numpy_conversion(self, real_handler):
        out = await real_handler.async_embed_text("hello")
        assert isinstance(out, np.ndarray)
        assert out.shape == (4,)

    @pytest.mark.asyncio
    async def test_async_embed_text_no_numpy_returns_list(self, real_handler, monkeypatch):
        import core.lancedb_handler as lh

        monkeypatch.setattr(lh, "NUMPY_AVAILABLE", False)
        out = await real_handler.async_embed_text("hello")
        assert isinstance(out, list)
        assert len(out) == 4

    @pytest.mark.asyncio
    async def test_async_embed_text_no_service(self, lh_env):
        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
            assert await handler.async_embed_text("hello") is None

    @pytest.mark.asyncio
    async def test_async_embed_text_exception(self, real_handler):
        real_handler.embedding_service.generate_embedding = AsyncMock(
            side_effect=RuntimeError("embed boom")
        )
        assert await real_handler.async_embed_text("hello") is None


class TestLanceDBKnowledgeEdges:
    def test_add_knowledge_edge_success(self, real_handler):
        _set_1536_embedding(real_handler)
        assert real_handler.add_knowledge_edge("a", "b", "knows", description="edge d")
        assert real_handler.add_knowledge_edge("a", "c", "knows", metadata={"k": "v"})

    def test_add_knowledge_edge_zero_vector_fallback(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.LLMService", None)
        monkeypatch.setattr("core.lancedb_handler.NUMPY_AVAILABLE", False)
        handler = LanceDBHandler(db_path=str(lh_env / "kg"))
        handler._initialize_db()
        assert handler.add_knowledge_edge("a", "b", "knows", description="d")

    def test_add_knowledge_edge_db_none_returns_false(self, lh_env):
        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.db = None
        assert handler.add_knowledge_edge("a", "b", "knows") is False


class TestLanceDBAddDocument:
    def test_add_document_success_with_extra_columns(self, real_handler):
        ok = real_handler.add_document(
            "documents",
            "Some text to remember",
            source="test",
            metadata={"title": "doc"},
            doc_id="doc-1",
            workspace_id="ws-1",
            extra_columns={"outcome": "pass"},
        )
        assert ok is True
        doc = real_handler.get_document_by_id("documents", "doc-1")
        assert doc is not None
        assert doc["id"] == "doc-1"
        assert doc["metadata"]["title"] == "doc"

    def test_add_document_generated_id_and_second_add(self, real_handler):
        assert real_handler.add_document("documents", "second doc", doc_id="doc-2")
        assert real_handler.add_document("documents", "third doc", doc_id="doc-3")
        assert real_handler.get_document_by_id("documents", "doc-2") is not None

    def test_add_document_empty_text_skipped(self, real_handler):
        assert real_handler.add_document("documents", "   ") is False

    def test_add_document_no_embedding_service(self, lh_env):
        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler._initialize_db()
        assert handler.add_document("documents", "text") is False

    def test_add_document_secrets_redacted(self, real_handler):
        with patch(
            "core.secrets_redactor.get_secrets_redactor", return_value=_FakeRedactor()
        ):
            ok = real_handler.add_document(
                "documents", "my api key is super-secret", doc_id="doc-secret"
            )
        assert ok is True
        doc = real_handler.get_document_by_id("documents", "doc-secret")
        assert doc["text"] == "REDACTED TEXT"
        assert doc["metadata"]["_redacted_types"] == ["api_key", "password"]
        assert doc["metadata"]["_redaction_count"] == 2

    def test_add_document_redactor_import_error(self, real_handler):
        with patch(
            "core.secrets_redactor.get_secrets_redactor",
            side_effect=ImportError("no module"),
        ):
            ok = real_handler.add_document("documents", "plain text", doc_id="doc-imp")
        assert ok is True

    def test_add_document_redactor_failure_proceeds(self, real_handler):
        with patch(
            "core.secrets_redactor.get_secrets_redactor",
            side_effect=RuntimeError("redactor boom"),
        ):
            ok = real_handler.add_document("documents", "plain text", doc_id="doc-red")
        assert ok is True

    def test_add_document_table_add_failure(self, real_handler):
        real_handler.create_table("documents", vector_size=4)
        real_handler.db.open_table = Mock(side_effect=RuntimeError("open boom"))
        assert real_handler.add_document("documents", "text", doc_id="doc-fail") is False

    def test_add_document_db_uninitialized(self, lh_env):
        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.db = None
        with patch("core.lancedb_handler.LANCEDB_AVAILABLE", True):
            handler._ensure_db = Mock()
        assert handler.add_document("documents", "text") is False


class TestLanceDBBatch:
    def test_add_documents_batch_new_table(self, real_handler):
        docs = [
            {"text": "first", "source": "s1", "id": "b1"},
            {"text": "second", "source": "s2", "id": "b2"},
        ]
        assert real_handler.add_documents_batch("batch_t", docs) == 2

    def test_add_documents_batch_existing_table(self, real_handler):
        docs = [{"text": "one", "id": "e1"}, {"text": "two", "id": "e2"}]
        real_handler.add_documents_batch("batch_t", docs)
        assert real_handler.add_documents_batch("batch_t", docs) == 2

    def test_add_documents_batch_all_embeddings_fail(self, lh_env):
        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler._initialize_db()
        assert handler.add_documents_batch("batch_t", [{"text": "t"}]) == 0

    def test_add_documents_batch_create_failure(self, real_handler):
        real_handler.get_table = Mock(return_value=None)
        real_handler.db.create_table = Mock(side_effect=RuntimeError("create boom"))
        assert real_handler.add_documents_batch("batch_t", [{"text": "t", "id": "x"}]) == 0

    def test_add_documents_batch_outer_exception(self, real_handler):
        real_handler.embed_text = Mock(side_effect=RuntimeError("embed boom"))
        assert real_handler.add_documents_batch("batch_t", [{"text": "t"}]) == 0


class TestLanceDBSearch:
    def test_search_full_flow_with_filters(self, real_handler):
        real_handler.add_document("documents", "alpha content", doc_id="s1", user_id="u1")
        real_handler.add_document("documents", "beta content", doc_id="s2", user_id="u2")
        results = real_handler.search("documents", "alpha", user_id="u1", limit=5)
        assert len(results) >= 1
        assert results[0]["id"] == "s1"
        assert results[0]["metadata"] == {}
        assert 0.0 <= results[0]["score"] <= 1.0

    def test_search_custom_filter(self, real_handler):
        real_handler.add_document(
            "documents", "outcome text", doc_id="f1", extra_columns={"outcome": "pass"}
        )
        results = real_handler.search(
            "documents", "outcome", filter_str="outcome == 'pass'", limit=5
        )
        assert results and results[0]["id"] == "f1"

    def test_search_freshness_filter(self, real_handler):
        real_handler.add_document(
            "documents", "fresh doc", doc_id="fresh-1",
            extra_columns={"freshness_status": "fresh"},
        )
        real_handler.add_document(
            "documents", "stale doc", doc_id="stale-1",
            extra_columns={"freshness_status": "stale"},
        )
        fresh = real_handler.search("documents", "doc", limit=10)
        assert {r["id"] for r in fresh} == {"fresh-1"}
        all_docs = real_handler.search("documents", "doc", limit=10, include_stale=True)
        assert {r["id"] for r in all_docs} == {"fresh-1", "stale-1"}

    def test_search_table_missing_returns_empty(self, real_handler):
        assert real_handler.search("missing_table", "q") == []

    def test_search_embedding_failure_returns_empty(self, real_handler):
        real_handler.add_document("documents", "text", doc_id="s3")
        real_handler.embedding_service.generate_embedding = AsyncMock(
            side_effect=RuntimeError("embed boom")
        )
        assert real_handler.search("documents", "q") == []

    def test_search_pandas_unavailable(self, real_handler, monkeypatch):
        real_handler.add_document("documents", "text", doc_id="s4")
        monkeypatch.setattr("core.lancedb_handler.PANDAS_AVAILABLE", False)
        assert real_handler.search("documents", "q") == []

    def test_search_exception_returns_empty(self, real_handler):
        real_handler.get_table = Mock(side_effect=RuntimeError("boom"))
        assert real_handler.search("documents", "q") == []

    def test_search_db_none_returns_empty(self, lh_env):
        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.db = None
        assert handler.search("documents", "q") == []

    def test_search_metadata_bad_json_skipped(self, real_handler):
        table = real_handler.create_table("docs_bad", vector_size=4)
        table.add(
            [
                {
                    "id": "bad-1", "user_id": "u", "workspace_id": "w", "text": "t",
                    "source": "s", "metadata": "{not json", "created_at": "c",
                    "vector": [0.01, 0.02, 0.03, 0.04],
                }
            ]
        )
        assert real_handler.search("docs_bad", "t") == []


class TestLanceDBGetAndList:
    def test_get_document_by_id_metadata_variants(self, real_handler):
        real_handler.add_document("documents", "text", doc_id="g1", metadata={"a": 1})
        doc = real_handler.get_document_by_id("documents", "g1")
        assert doc["metadata"] == {"a": 1}
        assert real_handler.get_document_by_id("documents", "missing") is None
        assert real_handler.get_document_by_id("missing_table", "g1") is None

    def test_get_document_by_id_bad_json_metadata(self, real_handler):
        table = real_handler.create_table("docs_bad2", vector_size=4)
        table.add(
            [
                {
                    "id": "bad-2", "user_id": "u", "workspace_id": "w", "text": "t",
                    "source": "s", "metadata": "{bad", "created_at": "c",
                    "vector": [0.01, 0.02, 0.03, 0.04],
                }
            ]
        )
        doc = real_handler.get_document_by_id("docs_bad2", "bad-2")
        assert doc["metadata"] == {}

    def test_get_document_by_id_exception(self, real_handler):
        fake_table = Mock()
        builder = Mock()
        builder.where.return_value.limit.return_value.to_pandas.side_effect = RuntimeError("boom")
        fake_table.search.return_value = builder
        real_handler.get_table = Mock(return_value=fake_table)
        assert real_handler.get_document_by_id("docs_x", "any") is None

    def test_list_documents_sort_and_metadata(self, real_handler):
        real_handler.add_document("documents", "old text", doc_id="l1", metadata={"title": "Old"})
        real_handler.add_document("documents", "new text", doc_id="l2", metadata={"title": "New"})
        docs = real_handler.list_documents("documents", limit=1, offset=0)
        assert len(docs) == 1
        assert docs[0]["title"] in ("Old", "New")
        assert docs[0]["text_preview"] in ("old text", "new text")

    def test_list_documents_empty_table(self, real_handler):
        assert real_handler.list_documents("missing_table") == []

    def test_list_documents_exception(self, real_handler):
        fake_table = Mock()
        builder = Mock()
        builder.limit.return_value.to_pandas.side_effect = RuntimeError("boom")
        fake_table.search.return_value = builder
        real_handler.get_table = Mock(return_value=fake_table)
        assert real_handler.list_documents("docs_l") == []

    def test_list_documents_metadata_none(self, real_handler):
        real_handler.add_document("documents", "text", doc_id="l9")
        table = real_handler.db.open_table("documents")
        table.add(
            [
                {
                    "id": "null-meta", "user_id": "u", "workspace_id": "w", "text": "t",
                    "source": "s", "metadata": None, "created_at": "2026-01-02",
                    "vector": [0.01, 0.02, 0.03, 0.04],
                }
            ]
        )
        docs = real_handler.list_documents("documents", limit=10)
        assert any(d["id"] == "null-meta" for d in docs)

    def test_list_documents_bad_json_metadata(self, real_handler):
        table = real_handler.create_table("docs_bad3", vector_size=4)
        table.add(
            [
                {
                    "id": "bad-3", "user_id": "u", "workspace_id": "w", "text": "t",
                    "source": "s", "metadata": "{bad", "created_at": "2026-01-01",
                    "vector": [0.01, 0.02, 0.03, 0.04],
                }
            ]
        )
        docs = real_handler.list_documents("docs_bad3")
        assert docs[0]["metadata"] == {}


class TestLanceDBKnowledgeGraphQuery:
    def test_query_knowledge_graph_excludes_source_docs(self, real_handler):
        _set_1536_embedding(real_handler)
        real_handler.add_knowledge_edge("a", "b", "knows", metadata={"doc_id": "stale-doc"})
        real_handler.add_knowledge_edge("c", "d", "knows", metadata={"doc_id": "fresh-doc"})
        all_edges = real_handler.query_knowledge_graph("knows", limit=10)
        assert len(all_edges) >= 1
        filtered = real_handler.query_knowledge_graph(
            "knows", limit=10, exclude_source_doc_ids={"stale-doc"}
        )
        ids = [r["id"] for r in filtered]
        assert "a_knows_b" not in ids


class TestLanceDBDualVector:
    @pytest.mark.asyncio
    async def test_add_embedding_and_similarity_and_get(self, real_handler):
        real_handler.create_table("episodes_single", vector_size=1536)
        vec = [0.01 * (i + 1) for i in range(1536)]
        ok = await real_handler.add_embedding(
            "episodes_single", "ep-1", vec,
            metadata={"user_id": "u1", "text": "episode text", "source": "episode"},
        )
        assert ok is True
        results = await real_handler.similarity_search(
            "episodes_single", vec, top_k=5, agent_id=None
        )
        assert results and results[0]["episode_id"] == "ep-1"
        assert results[0]["vector_column"] == "vector"
        got = await real_handler.get_embedding("episodes_single", "ep-1")
        assert got is not None
        assert len(got) == 1536

    @pytest.mark.asyncio
    async def test_add_embedding_fastembed_column(self, real_handler):
        vec = [0.01 * (i + 1) for i in range(384)]
        ok = await real_handler.add_embedding(
            "episodes_fast", "ep-f", vec, vector_column="vector_fastembed",
            metadata={"user_id": "u1", "text": "t", "source": "episode"},
        )
        assert ok is True
        got = await real_handler.get_embedding(
            "episodes_fast", "ep-f", vector_column="vector_fastembed"
        )
        assert got is not None
        assert len(got) == 384

    @pytest.mark.asyncio
    async def test_add_embedding_unknown_column_raises(self, real_handler):
        with pytest.raises(ValueError):
            await real_handler.add_embedding(
                "episodes", "ep-2", [0.1] * 1536, vector_column="bogus"
            )

    @pytest.mark.asyncio
    async def test_add_embedding_dim_mismatch_raises(self, real_handler):
        with pytest.raises(ValueError):
            await real_handler.add_embedding("episodes", "ep-2", [0.1] * 3)

    @pytest.mark.asyncio
    async def test_add_embedding_table_create_failure(self, real_handler):
        real_handler.get_table = Mock(return_value=None)
        real_handler.create_table = Mock(return_value=None)
        assert (await real_handler.add_embedding("episodes", "ep-3", [0.1] * 1536)) is False

    @pytest.mark.asyncio
    async def test_add_embedding_existing_table_failure(self, real_handler):
        fake_table = Mock()
        fake_table.add = Mock(side_effect=RuntimeError("add boom"))
        real_handler.get_table = Mock(return_value=fake_table)
        assert (await real_handler.add_embedding("episodes", "ep-4", [0.1] * 1536)) is False

    @pytest.mark.asyncio
    async def test_similarity_search_table_missing(self, real_handler):
        assert (await real_handler.similarity_search("missing_table", [0.1] * 1536)) == []

    @pytest.mark.asyncio
    async def test_similarity_search_unknown_column_raises(self, real_handler):
        with pytest.raises(ValueError):
            await real_handler.similarity_search(
                "episodes", [0.1] * 1536, vector_column="bogus"
            )

    @pytest.mark.asyncio
    async def test_similarity_search_dim_mismatch_raises(self, real_handler):
        with pytest.raises(ValueError):
            await real_handler.similarity_search("episodes", [0.1] * 4)

    @pytest.mark.asyncio
    async def test_similarity_search_exception(self, real_handler):
        fake_table = Mock()
        builder = Mock()
        builder.limit.return_value.to_pandas.side_effect = RuntimeError("boom")
        fake_table.search.return_value = builder
        real_handler.get_table = Mock(return_value=fake_table)
        assert (await real_handler.similarity_search("episodes", [0.1] * 1536)) == []

    @pytest.mark.asyncio
    async def test_similarity_search_row_parse_error_skipped(self, real_handler):
        import pandas as pd

        fake_table = Mock()
        builder = Mock()
        builder.limit.return_value.to_pandas.return_value = pd.DataFrame(
            {"id": ["a"], "_distance": ["not-a-number"]}
        )
        fake_table.search.return_value = builder
        real_handler.get_table = Mock(return_value=fake_table)
        assert (await real_handler.similarity_search("episodes", [0.1] * 1536)) == []

    @pytest.mark.asyncio
    async def test_get_embedding_missing_column_returns_none(self, real_handler):
        await real_handler.add_embedding(
            "episodes", "ep-5", [0.1] * 384, vector_column="vector_fastembed"
        )
        assert (
            await real_handler.get_embedding("episodes", "ep-5", vector_column="vector")
        ) is None

    @pytest.mark.asyncio
    async def test_get_embedding_table_missing(self, real_handler):
        assert await real_handler.get_embedding("missing_table", "x") is None

    @pytest.mark.asyncio
    async def test_get_embedding_exception(self, real_handler):
        real_handler.create_table("episodes", vector_size=1536)
        real_handler.db.open_table = Mock(side_effect=RuntimeError("boom"))
        assert await real_handler.get_embedding("episodes", "x") is None


class TestChatHistoryManager:
    def test_ensure_table_exception(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        real_handler.db.table_names = Mock(side_effect=RuntimeError("boom"))
        manager = ChatHistoryManager(real_handler)
        assert manager.table_name == "chat_messages"

    def test_save_message_success_and_get_history(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.LLMService", _FakeLLMService1536)
        handler = LanceDBHandler(db_path=str(lh_env / "chat"), workspace_id="ws-1")
        handler._initialize_db()
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(handler)
        assert manager.save_message("sess-1", "u1", "user", "hello there")
        assert manager.save_message("sess-1", "u1", "assistant", "hi back")
        history = manager.get_session_history("sess-1", limit=10)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_save_message_db_none(self, lh_env):
        from core.lancedb_handler import ChatHistoryManager

        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.db = None
        manager = ChatHistoryManager(handler)
        assert manager.save_message("s1", "u1", "user", "hi") is False

    def test_save_message_exception(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        real_handler.add_document = Mock(side_effect=RuntimeError("boom"))
        assert manager.save_message("s1", "u1", "user", "hi") is False

    def test_escape_like(self):
        from core.lancedb_handler import ChatHistoryManager

        assert ChatHistoryManager._escape_like("a'b") == "a''b"
        assert ChatHistoryManager._escape_like("50%_x") == "50\\%\\_x"
        assert ChatHistoryManager._escape_like("a\\b") == "a\\\\b"

    def test_get_session_history_db_none(self, lh_env):
        from core.lancedb_handler import ChatHistoryManager

        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.db = None
        manager = ChatHistoryManager(handler)
        assert manager.get_session_history("s1") == []

    def test_get_session_history_table_missing(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        real_handler.get_table = Mock(return_value=None)
        assert manager.get_session_history("s1") == []

    def test_get_session_history_pandas_unavailable(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.LLMService", _FakeLLMService1536)
        handler = LanceDBHandler(db_path=str(lh_env / "chatp"), workspace_id="ws-1")
        handler._initialize_db()
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(handler)
        manager.save_message("s1", "u1", "user", "hello")
        monkeypatch.setattr("core.lancedb_handler.PANDAS_AVAILABLE", False)
        assert manager.get_session_history("s1") == []

    def test_get_session_history_skips_prefix_collision(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        manager.save_message("sess", "u1", "user", "short session")
        manager.save_message("sess_longer", "u1", "user", "longer session")
        history = manager.get_session_history("sess", limit=10)
        assert all(m["metadata"]["session_id"] == "sess" for m in history)

    def test_get_session_history_bad_json_row_skipped(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        table = real_handler.db.open_table("chat_messages")
        table.add(
            [
                {
                    "id": "bad", "user_id": "u", "workspace_id": "w", "text": "t",
                    "source": "chat_user", "metadata": "{not json sess-9",
                    "created_at": "2026-01-01", "vector": [0.01] * 1536,
                }
            ]
        )
        history = manager.get_session_history("sess-9", limit=10)
        assert all(m["metadata"]["session_id"] != "bad" for m in history)

    def test_get_session_history_metadata_none_row(self, real_handler):
        import pandas as pd

        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        fake_table = Mock()
        builder = Mock()
        builder.where.return_value.limit.return_value.to_pandas.return_value = pd.DataFrame(
            [
                {"id": "m1", "text": "t", "created_at": "2026-01-01", "metadata": None},
            ]
        )
        fake_table.search.return_value = builder
        real_handler.get_table = Mock(return_value=fake_table)
        assert manager.get_session_history("s1", limit=10) == []

    def test_search_relevant_context_with_session(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.LLMService", _FakeLLMService1536)
        handler = LanceDBHandler(db_path=str(lh_env / "chat2"), workspace_id="ws-1")
        handler._initialize_db()
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(handler)
        manager.save_message("sess-a", "u1", "user", "about pandas")
        manager.save_message("sess-b", "u1", "user", "about pandas too")
        results = manager.search_relevant_context("pandas", session_id="sess-a", limit=5)
        assert results
        assert all(r["metadata"]["session_id"] == "sess-a" for r in results)
        results_all = manager.search_relevant_context("pandas", limit=5)
        assert len(results_all) >= 1

    def test_search_relevant_context_exception(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        real_handler.search = Mock(side_effect=RuntimeError("boom"))
        assert manager.search_relevant_context("q") == []

    def test_search_relevant_context_db_none(self, lh_env):
        from core.lancedb_handler import ChatHistoryManager

        with patch("core.lancedb_handler.LLMService", None):
            handler = LanceDBHandler(db_path=str(lh_env / "x"))
        handler.db = None
        manager = ChatHistoryManager(handler)
        assert manager.search_relevant_context("q") == []

    def test_get_entity_mentions(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.LLMService", _FakeLLMService1536)
        handler = LanceDBHandler(db_path=str(lh_env / "chat3"), workspace_id="ws-1")
        handler._initialize_db()
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(handler)
        manager.save_message("sess-1", "u1", "user", "workflow wf-42")
        table = handler.db.open_table("chat_messages")
        table.add(
            [
                {
                    "id": "wf-msg", "user_id": "u1", "workspace_id": "ws-1", "text": "t",
                    "source": "chat_user", "metadata": json.dumps(
                        {"session_id": "sess-1", "user_id": "u1", "role": "user",
                         "workflow_id": "wf-42"}
                    ),
                    "created_at": "2026-01-01", "vector": [0.01] * 1536,
                }
            ]
        )
        found = manager.get_entity_mentions("workflow_id", "wf-42", session_id="sess-1")
        assert len(found) == 1
        assert found[0]["role"] == "user"

    def test_get_entity_mentions_no_session_filter(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        manager.save_message("sess-1", "u1", "user", "task t-1")
        table = real_handler.db.open_table("chat_messages")
        table.add(
            [
                {
                    "id": "t-msg", "user_id": "u1", "workspace_id": "ws-1", "text": "t",
                    "source": "chat_user", "metadata": json.dumps(
                        {"session_id": "sess-1", "user_id": "u1", "role": "user",
                         "task_id": "t-1"}
                    ),
                    "created_at": "2026-01-01", "vector": [0.01] * 1536,
                }
            ]
        )
        found = manager.get_entity_mentions("task_id", "t-1")
        assert len(found) == 1

    def test_get_entity_mentions_table_missing(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        real_handler.get_table = Mock(return_value=None)
        assert manager.get_entity_mentions("task_id", "t-1") == []

    def test_get_entity_mentions_pandas_unavailable(self, lh_env, monkeypatch):
        monkeypatch.setattr("core.lancedb_handler.LLMService", _FakeLLMService1536)
        handler = LanceDBHandler(db_path=str(lh_env / "chatp2"), workspace_id="ws-1")
        handler._initialize_db()
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(handler)
        manager.save_message("s1", "u1", "user", "hello")
        monkeypatch.setattr("core.lancedb_handler.PANDAS_AVAILABLE", False)
        assert manager.get_entity_mentions("task_id", "t-1") == []

    def test_get_entity_mentions_exception(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        real_handler.get_table = Mock(side_effect=RuntimeError("boom"))
        assert manager.get_entity_mentions("task_id", "t-1") == []

    def test_get_entity_mentions_bad_json_row(self, real_handler):
        from core.lancedb_handler import ChatHistoryManager

        manager = ChatHistoryManager(real_handler)
        table = real_handler.db.open_table("chat_messages")
        table.add(
            [
                {
                    "id": "bad", "user_id": "u", "workspace_id": "w", "text": "t",
                    "source": "chat_user", "metadata": "{not json", "created_at": "2026-01-01",
                    "vector": [0.01] * 1536,
                }
            ]
        )
        assert manager.get_entity_mentions("workflow_id", "bad") == []


class TestLanceDBUtilities:
    def test_embed_documents_batch_unavailable(self, monkeypatch):
        import core.lancedb_handler as lh

        monkeypatch.setattr(lh, "SENTENCE_TRANSFORMERS_AVAILABLE", False)
        assert lh.embed_documents_batch(["a"]) is None

    def _fake_sentence_transformers_module(self, fake_cls):
        import types

        fake_mod = types.ModuleType("sentence_transformers")
        fake_mod.SentenceTransformer = fake_cls
        saved = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = fake_mod
        return saved

    def test_embed_documents_batch_numpy_path(self, monkeypatch):
        import core.lancedb_handler as lh

        monkeypatch.setattr(lh, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
        monkeypatch.setattr(lh, "NUMPY_AVAILABLE", True)
        fake = Mock()
        fake.encode = Mock(return_value="embedded")
        saved = self._fake_sentence_transformers_module(Mock(return_value=fake))
        try:
            assert lh.embed_documents_batch(["a"]) == "embedded"
        finally:
            if saved is None:
                del sys.modules["sentence_transformers"]
            else:
                sys.modules["sentence_transformers"] = saved
        fake.encode.assert_called_once_with(["a"], convert_to_numpy=True)

    def test_embed_documents_batch_no_numpy_path(self, monkeypatch):
        import core.lancedb_handler as lh

        monkeypatch.setattr(lh, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
        monkeypatch.setattr(lh, "NUMPY_AVAILABLE", False)
        fake = Mock()
        fake.encode = Mock(return_value="embedded")
        saved = self._fake_sentence_transformers_module(Mock(return_value=fake))
        try:
            assert lh.embed_documents_batch(["a"]) == "embedded"
        finally:
            if saved is None:
                del sys.modules["sentence_transformers"]
            else:
                sys.modules["sentence_transformers"] = saved
        fake.encode.assert_called_once_with(["a"], convert_to_numpy=False)

    def test_embed_documents_batch_exception(self, monkeypatch):
        import core.lancedb_handler as lh

        monkeypatch.setattr(lh, "SENTENCE_TRANSFORMERS_AVAILABLE", True)
        saved = self._fake_sentence_transformers_module(
            Mock(side_effect=RuntimeError("boom"))
        )
        try:
            assert lh.embed_documents_batch(["a"]) is None
        finally:
            if saved is None:
                del sys.modules["sentence_transformers"]
            else:
                sys.modules["sentence_transformers"] = saved

    def test_create_memory_schema_real(self):
        import core.lancedb_handler as lh

        schema = lh.create_memory_schema(384)
        assert schema["id"] is str
        assert schema["vector"] is not None

    def test_create_memory_schema_fallback(self):
        import core.lancedb_handler as lh

        saved = sys.modules.get("lancedb.pydantic")
        sys.modules["lancedb.pydantic"] = None
        try:
            schema = lh.create_memory_schema(384)
        finally:
            if saved is None:
                del sys.modules["lancedb.pydantic"]
            else:
                sys.modules["lancedb.pydantic"] = saved
        assert "List" in str(schema["vector"])

    def test_seed_mock_data(self, real_handler):
        assert real_handler.seed_mock_data([{"text": "seed one", "id": "sd1"}]) == 1

    def test_import_fallback_paths_then_restore(self, monkeypatch):
        import core.lancedb_handler as lh

        real_find_spec = importlib.util.find_spec
        real_import = __import__

        blocked = {"numpy", "pandas", "lancedb", "sentence_transformers", "openai", "pyarrow"}

        def fake_find_spec(name, *a, **kw):
            if name in blocked:
                return None
            return real_find_spec(name, *a, **kw)

        def fake_import(name, *a, **kw):
            if name in ("core.byok_endpoints", "core.llm_service", "pyarrow"):
                raise ImportError(f"blocked: {name}")
            return real_import(name, *a, **kw)

        with patch("importlib.util.find_spec", side_effect=fake_find_spec), patch(
            "builtins.__import__", side_effect=fake_import
        ):
            mod = importlib.reload(lh)
            assert mod.NUMPY_AVAILABLE is False
            assert mod.PANDAS_AVAILABLE is False
            assert mod.LANCEDB_AVAILABLE is False
            assert mod.SENTENCE_TRANSFORMERS_AVAILABLE is False
            assert mod.OPENAI_AVAILABLE is False
            assert mod.pa is None
            assert mod.get_byok_manager is None
            assert mod.LLMService is None

        importlib.reload(lh)
        assert lh.LANCEDB_AVAILABLE is True
        assert lh.pa is not None
        assert lh.LLMService is not None
