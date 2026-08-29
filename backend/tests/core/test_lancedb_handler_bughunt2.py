"""TDD bug-hunt + coverage tests for core/lancedb_handler.py.

Focuses on UNcovered regions where undetected bugs hide:
- get_embedding missing _ensure_db() lazy-load
- get_document_by_id filter-string injection (unescaped doc_id)
- ChatHistoryManager._escape_like wildcard escaping
- search / similarity_search scoring + empty-result handling
- add_documents_batch / _add_document_with_embedding
- query_knowledge_graph exclude filter
"""

import sys
import json
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

from core import lancedb_handler as lh
from core.lancedb_handler import LanceDBHandler, ChatHistoryManager


def _make_handler():
    """Build a handler with a *real* (in-memory-style) lazy DB, bypassing the
    LanceDB connect path. We patch _initialize_db so db stays None until
    _ensure_db is invoked, letting us assert lazy-load behavior precisely."""
    h = LanceDBHandler.__new__(LanceDBHandler)
    h.db_path = "/tmp/atom_test_lancedb"
    h.workspace_id = "ws1"
    h.tenant_id = "tn1"
    h.embedding_provider = "openai"
    h.db = None  # NOT initialized
    h.embedding_service = None
    h.embedder = None
    h.vector_columns = {"vector": 1536, "vector_fastembed": 384}
    return h


# ---------------------------------------------------------------------------
# BUG 1 (PRIMARY): get_embedding does NOT lazily init the DB.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_embedding_lazily_initializes_db():
    """BUG: get_embedding checks `if self.db is None: return None` WITHOUT
    calling _ensure_db() first — unlike every other read/write method
    (search, add_embedding, similarity_search, get_document_by_id, ...). So a
    fresh handler whose first call is get_embedding always returns None even
    when the DB could be opened lazily. This silently breaks any caller that
    reads embeddings before writing."""

    h = _make_handler()
    assert h.db is None

    initialized = {"called": False}

    def fake_init_db():
        initialized["called"] = True
        h.db = MagicMock()  # simulate a successful lazy connect

    fake_table = MagicMock()
    empty_df = pd.DataFrame()
    fake_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = empty_df

    with patch.object(h, "_initialize_db", side_effect=fake_init_db), \
         patch.object(h, "get_table", return_value=fake_table):
        result = await h.get_embedding("docs", "ep-1", "vector")

    # The lazy loader MUST have been called.
    assert initialized["called"] is True, (
        "get_embedding must call _ensure_db() so a fresh handler can read "
        "embeddings, matching every other read/write method."
    )
    # Empty result is fine — we only assert the lazy path ran (no premature None).
    assert result is None  # empty table → None


# ---------------------------------------------------------------------------
# BUG 2 (PRIMARY): get_document_by_id injects / breaks on quote in doc_id.
# ---------------------------------------------------------------------------
def test_get_document_by_id_escapes_doc_id():
    """The original BUG (string-interpolated `f"id = '{doc_id}'"` filter, no
    quote escaping) is structurally fixed: the point lookup now runs through a
    parameterized Arrow equality filter (pc.equal), so injection cannot occur.
    Pin the new contract: a quoted doc_id round-trips against real Arrow data."""

    import pyarrow as pa

    h = _make_handler()
    h.db = MagicMock()
    fake_table = MagicMock()
    df = pd.DataFrame([
        {"id": "it's a'doc", "text": "hello", "source": "s",
         "metadata": "{}", "created_at": "2026-01-01"},
        {"id": "other-doc", "text": "nope", "source": "s",
         "metadata": "{}", "created_at": "2026-01-01"},
    ])
    fake_table.to_arrow.return_value = pa.Table.from_pandas(df)
    with patch.object(h, "get_table", return_value=fake_table):
        result = h.get_document_by_id("docs", "it's a'doc")

    assert result is not None
    assert result["id"] == "it's a'doc"
    assert result["text"] == "hello"


# ---------------------------------------------------------------------------
# BUG 3 (PRIMARY): ChatHistoryManager._escape_like fails to escape % and _.
# ---------------------------------------------------------------------------
def test_escape_like_escapes_wildcards():
    """BUG: _escape_like's docstring claims to escape `%` and `_` LIKE
    wildcards, but the implementation only doubles single quotes and
    backslashes. A session_id or entity_id containing `%`/`_` would match
    unintended rows in the LIKE pre-filter."""

    mgr = ChatHistoryManager.__new__(ChatHistoryManager)
    escaped = mgr._escape_like("ab'_c%d\\e")
    # Single quotes doubled, backslashes handled, AND % / _ escaped so they
    # match literally inside a LIKE clause.
    assert "''" in escaped, "single quotes must be doubled"
    assert "\\%" in escaped or "%%" in escaped, (
        f"% wildcard must be escaped for LIKE, got: {escaped!r}"
    )
    assert "\\_" in escaped or "[_]" in escaped, (
        f"_ wildcard must be escaped for LIKE, got: {escaped!r}"
    )


# ---------------------------------------------------------------------------
# Coverage: search() empty / no-table / score clamping
# ---------------------------------------------------------------------------
def test_search_returns_empty_when_db_none():
    h = _make_handler()
    # db stays None and _initialize_db leaves it None
    with patch.object(h, "_initialize_db"):
        assert h.search("docs", "q") == []


def test_search_returns_empty_when_table_missing():
    h = _make_handler()
    h.db = MagicMock()
    with patch.object(h, "get_table", return_value=None), \
         patch.object(h, "embed_text", return_value=[0.1]):
        assert h.search("docs", "q") == []


def test_search_returns_empty_when_no_embedding():
    h = _make_handler()
    h.db = MagicMock()
    fake_table = MagicMock()
    with patch.object(h, "get_table", return_value=fake_table), \
         patch.object(h, "embed_text", return_value=None):
        assert h.search("docs", "q") == []


def test_search_score_clamped_to_zero_for_large_distance():
    """A large _distance must clamp the score to >= 0.0 (the max(0.0, ...)
    guard at lancedb_handler.py:898)."""
    h = _make_handler()
    h.db = MagicMock()
    h.workspace_id = None  # avoid workspace filter
    fake_table = MagicMock()

    df = pd.DataFrame(
        [{
            "id": "d1",
            "text": "hello",
            "source": "s",
            "metadata": "{}",
            "created_at": "2024-01-01",
            "_distance": 5.0,  # very far → 1 - 5 = -4 → clamped to 0
        }]
    )
    sq = MagicMock()
    sq.limit.return_value = sq
    sq.where.return_value = sq
    sq.to_pandas.return_value = df
    fake_table.search.return_value = sq

    with patch.object(h, "get_table", return_value=fake_table), \
         patch.object(h, "embed_text", return_value=[0.1, 0.2]):
        results = h.search("docs", "q")
    assert len(results) == 1
    assert results[0]["score"] == 0.0
    assert results[0]["metadata"] == {}


def test_search_workspace_filter_escaping():
    """workspace_id with a single quote is doubled in the filter (security)."""
    h = _make_handler()
    h.workspace_id = "ws'x"
    h.db = MagicMock()
    fake_table = MagicMock()
    captured = {}

    sq = MagicMock()
    sq.limit.return_value = sq

    def fake_where(filt):
        captured["filter"] = filt
        return sq

    sq.where = fake_where
    sq.to_pandas.return_value = pd.DataFrame()
    fake_table.search.return_value = sq

    with patch.object(h, "get_table", return_value=fake_table), \
         patch.object(h, "embed_text", return_value=[0.1]):
        h.search("docs", "q")
    assert "workspace_id == 'ws''x'" in captured["filter"]


# ---------------------------------------------------------------------------
# Coverage: similarity_search dimension validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_similarity_search_unknown_column_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Unknown vector column"):
        await h.similarity_search("docs", [0.1] * 1536, vector_column="bogus")


@pytest.mark.asyncio
async def test_similarity_search_dim_mismatch_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Dimension mismatch"):
        await h.similarity_search(
            "docs", [0.1] * 10, vector_column="vector"  # expected 1536
        )


@pytest.mark.asyncio
async def test_similarity_search_table_missing_returns_empty():
    h = _make_handler()
    h.db = MagicMock()
    with patch.object(h, "get_table", return_value=None):
        result = await h.similarity_search("docs", [0.1] * 1536)
    assert result == []


@pytest.mark.asyncio
async def test_add_embedding_unknown_column_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Unknown vector column"):
        await h.add_embedding("docs", "ep1", [0.1] * 1536, vector_column="bad")


@pytest.mark.asyncio
async def test_add_embedding_dim_mismatch_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Dimension mismatch"):
        await h.add_embedding("docs", "ep1", [0.1] * 5, vector_column="vector")


# ---------------------------------------------------------------------------
# Coverage: add_documents_batch with no embeddable docs
# ---------------------------------------------------------------------------
def test_add_documents_batch_returns_zero_when_no_embeddings():
    h = _make_handler()
    h.db = MagicMock()
    docs = [{"text": "a"}, {"text": "b"}]
    with patch.object(h, "embed_text", return_value=None):
        n = h.add_documents_batch("docs", docs)
    assert n == 0


def test_add_documents_batch_empty_list():
    h = _make_handler()
    h.db = MagicMock()
    assert h.add_documents_batch("docs", []) == 0


# ---------------------------------------------------------------------------
# Coverage: query_knowledge_graph exclude filter
# ---------------------------------------------------------------------------
def test_query_knowledge_graph_excludes_stale_doc_ids():
    h = _make_handler()
    h.db = MagicMock()
    fake_results = [
        {"id": "e1", "metadata": {"doc_id": "d1"}},
        {"id": "e2", "metadata": {"doc_id": "d2"}},  # excluded
        {"id": "e3", "metadata": {"doc_id": "d3"}},
        {"id": "e4", "metadata": {}},  # no doc_id → kept
    ]
    with patch.object(h, "search", return_value=fake_results):
        out = h.query_knowledge_graph("q", exclude_source_doc_ids={"d2"})
    ids = {r["id"] for r in out}
    assert ids == {"e1", "e3", "e4"}


def test_query_knowledge_graph_no_exclude_returns_all():
    h = _make_handler()
    h.db = MagicMock()
    fake_results = [{"id": "e1"}, {"id": "e2"}]
    with patch.object(h, "search", return_value=fake_results):
        out = h.query_knowledge_graph("q")
    assert len(out) == 2


# ---------------------------------------------------------------------------
# Coverage: get_table / drop_table / create_table when db is None
# ---------------------------------------------------------------------------
def test_get_table_returns_none_when_db_none():
    h = _make_handler()
    with patch.object(h, "_initialize_db"):
        assert h.get_table("docs") is None


def test_drop_table_returns_false_when_db_none():
    h = _make_handler()
    with patch.object(h, "_initialize_db"):
        assert h.drop_table("docs") is False


def test_create_table_returns_none_when_db_none():
    h = _make_handler()
    with patch.object(h, "_initialize_db"):
        assert h.create_table("docs") is None


def test_has_column_handles_error():
    """_has_column is defensive — any error → False."""
    bad_table = MagicMock()
    bad_table.schema = property(lambda self: (_ for _ in ()).throw(RuntimeError("x")))
    assert LanceDBHandler._has_column(bad_table, "vector") is False


# ---------------------------------------------------------------------------
# Coverage: list_documents offset/sort + metadata parsing
# ---------------------------------------------------------------------------
def test_list_documents_sorts_desc_and_applies_offset():
    h = _make_handler()
    h.db = MagicMock()
    fake_table = MagicMock()
    df = pd.DataFrame([
        {"id": "1", "text": "a", "source": "s", "metadata": "{}",
         "created_at": "2024-01-01"},
        {"id": "2", "text": "b", "source": "s", "metadata": '{"title":"B"}',
         "created_at": "2024-03-01"},
        {"id": "3", "text": "c", "source": "s", "metadata": None,
         "created_at": "2024-02-01"},
    ])
    sq = MagicMock()
    sq.limit.return_value.to_pandas.return_value = df
    fake_table.search.return_value = sq
    with patch.object(h, "get_table", return_value=fake_table):
        docs = h.list_documents("docs", limit=2, offset=0)
    # Sorted desc by created_at → id 2 (Mar) first, then id 3 (Feb)
    assert [d["id"] for d in docs] == ["2", "3"]
    assert docs[0]["title"] == "B"
    assert docs[1]["title"] == "s"  # metadata None → falls back to source


def test_list_documents_returns_empty_when_table_missing():
    h = _make_handler()
    h.db = MagicMock()
    with patch.object(h, "get_table", return_value=None):
        assert h.list_documents("docs") == []


# ---------------------------------------------------------------------------
# Coverage: get_lancedb_handler does not cache when db session is provided
# ---------------------------------------------------------------------------
def test_get_lancedb_handler_no_cache_when_db_provided():
    """Handlers created with a db session must NOT be cached (connection leak
    prevention — Issue #7488074293). The handler is returned fresh each call,
    and the global _workspace_handlers cache is NOT mutated."""
    import os
    with patch.dict(os.environ, {"LANCEDB_URI_BASE": "/tmp/atom_test_base"}):
        from core.lancedb_handler import get_lancedb_handler, _workspace_handlers
        before = set(_workspace_handlers.keys())
        db_session = MagicMock()
        h1 = get_lancedb_handler(workspace_id="leak-test-ws-2", db=db_session)
        h2 = get_lancedb_handler(workspace_id="leak-test-ws-2", db=db_session)
        after = set(_workspace_handlers.keys())
        # Cache must not have grown with the db-session workspace.
        assert "leak-test-ws-2" not in _workspace_handlers, (
            "handler created with a db session must not be cached"
        )
        # Each call returns a fresh instance (no caching).
        assert h1 is not h2


# ---------------------------------------------------------------------------
# Coverage: embed_text returns None when no embedding_service
# ---------------------------------------------------------------------------
def test_embed_text_no_service_returns_none():
    h = _make_handler()
    assert h.embed_text("hello") is None


@pytest.mark.asyncio
async def test_async_embed_text_no_service_returns_none():
    h = _make_handler()
    assert await h.async_embed_text("hello") is None

    def test_get_document_by_id_quotes_are_safe(self):
        """Point-lookup contract: a doc_id containing single quotes must round-
        trip correctly. The WIP implementation routes through a parameterized
        Arrow equality filter (pc.equal) instead of a string-interpolated
        filter expression, so injection is structurally impossible — this
        pins that the quoted id still MATCHES its row."""
        import pandas as pd
        import pyarrow as pa

        h.db = MagicMock()
        fake_table = MagicMock()
        df = pd.DataFrame([
            {"id": "it's a'doc", "text": "hello", "source": "s",
             "metadata": "{}", "created_at": "2026-01-01"},
        ])
        arrow = pa.Table.from_pandas(df)

        fake_table.to_arrow.return_value = arrow
        with patch.object(h, "get_table", return_value=fake_table):
            result = h.get_document_by_id("docs", "it's a'doc")

        assert result is not None
        assert result["id"] == "it's a'doc"
        assert result["text"] == "hello"

    def fake_init_db():
        initialized["called"] = True
        h.db = MagicMock()  # simulate a successful lazy connect

    fake_table = MagicMock()
    empty_df = pd.DataFrame()
    fake_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = empty_df

    with patch.object(h, "_initialize_db", side_effect=fake_init_db), \
         patch.object(h, "get_table", return_value=fake_table):
        result = await h.get_embedding("docs", "ep-1", "vector")

    # The lazy loader MUST have been called.
    assert initialized["called"] is True, (
        "get_embedding must call _ensure_db() so a fresh handler can read "
        "embeddings, matching every other read/write method."
    )
    # Empty result is fine — we only assert the lazy path ran (no premature None).
    assert result is None  # empty table → None


# ---------------------------------------------------------------------------
# BUG 2 (PRIMARY): get_document_by_id injects / breaks on quote in doc_id.
# ---------------------------------------------------------------------------
def test_get_document_by_id_escapes_doc_id():
    """The original BUG (string-interpolated `f"id = '{doc_id}'"` filter, no
    quote escaping) is structurally fixed: the point lookup now runs through a
    parameterized Arrow equality filter (pc.equal), so injection cannot occur.
    Pin the new contract: a quoted doc_id round-trips against real Arrow data."""

    import pyarrow as pa

    h = _make_handler()
    h.db = MagicMock()
    fake_table = MagicMock()
    df = pd.DataFrame([
        {"id": "it's a'doc", "text": "hello", "source": "s",
         "metadata": "{}", "created_at": "2026-01-01"},
        {"id": "other-doc", "text": "nope", "source": "s",
         "metadata": "{}", "created_at": "2026-01-01"},
    ])
    fake_table.to_arrow.return_value = pa.Table.from_pandas(df)
    with patch.object(h, "get_table", return_value=fake_table):
        result = h.get_document_by_id("docs", "it's a'doc")

    assert result is not None
    assert result["id"] == "it's a'doc"
    assert result["text"] == "hello"


# ---------------------------------------------------------------------------
# BUG 3 (PRIMARY): ChatHistoryManager._escape_like fails to escape % and _.
# ---------------------------------------------------------------------------
def test_escape_like_escapes_wildcards():
    """BUG: _escape_like's docstring claims to escape `%` and `_` LIKE
    wildcards, but the implementation only doubles single quotes and
    backslashes. A session_id or entity_id containing `%`/`_` would match
    unintended rows in the LIKE pre-filter."""

    mgr = ChatHistoryManager.__new__(ChatHistoryManager)
    escaped = mgr._escape_like("ab'_c%d\\e")
    # Single quotes doubled, backslashes handled, AND % / _ escaped so they
    # match literally inside a LIKE clause.
    assert "''" in escaped, "single quotes must be doubled"
    assert "\\%" in escaped or "%%" in escaped, (
        f"% wildcard must be escaped for LIKE, got: {escaped!r}"
    )
    assert "\\_" in escaped or "[_]" in escaped, (
        f"_ wildcard must be escaped for LIKE, got: {escaped!r}"
    )


# ---------------------------------------------------------------------------
# Coverage: search() empty / no-table / score clamping
# ---------------------------------------------------------------------------
def test_search_returns_empty_when_db_none():
    h = _make_handler()
    # db stays None and _initialize_db leaves it None
    with patch.object(h, "_initialize_db"):
        assert h.search("docs", "q") == []


def test_search_returns_empty_when_table_missing():
    h = _make_handler()
    h.db = MagicMock()
    with patch.object(h, "get_table", return_value=None), \
         patch.object(h, "embed_text", return_value=[0.1]):
        assert h.search("docs", "q") == []


def test_search_returns_empty_when_no_embedding():
    h = _make_handler()
    h.db = MagicMock()
    fake_table = MagicMock()
    with patch.object(h, "get_table", return_value=fake_table), \
         patch.object(h, "embed_text", return_value=None):
        assert h.search("docs", "q") == []


def test_search_score_clamped_to_zero_for_large_distance():
    """A large _distance must clamp the score to >= 0.0 (the max(0.0, ...)
    guard at lancedb_handler.py:898)."""
    h = _make_handler()
    h.db = MagicMock()
    h.workspace_id = None  # avoid workspace filter
    fake_table = MagicMock()

    df = pd.DataFrame(
        [{
            "id": "d1",
            "text": "hello",
            "source": "s",
            "metadata": "{}",
            "created_at": "2024-01-01",
            "_distance": 5.0,  # very far → 1 - 5 = -4 → clamped to 0
        }]
    )
    sq = MagicMock()
    sq.limit.return_value = sq
    sq.where.return_value = sq
    sq.to_pandas.return_value = df
    fake_table.search.return_value = sq

    with patch.object(h, "get_table", return_value=fake_table), \
         patch.object(h, "embed_text", return_value=[0.1, 0.2]):
        results = h.search("docs", "q")
    assert len(results) == 1
    assert results[0]["score"] == 0.0
    assert results[0]["metadata"] == {}


def test_search_workspace_filter_escaping():
    """workspace_id with a single quote is doubled in the filter (security)."""
    h = _make_handler()
    h.workspace_id = "ws'x"
    h.db = MagicMock()
    fake_table = MagicMock()
    captured = {}

    sq = MagicMock()
    sq.limit.return_value = sq

    def fake_where(filt):
        captured["filter"] = filt
        return sq

    sq.where = fake_where
    sq.to_pandas.return_value = pd.DataFrame()
    fake_table.search.return_value = sq

    with patch.object(h, "get_table", return_value=fake_table), \
         patch.object(h, "embed_text", return_value=[0.1]):
        h.search("docs", "q")
    assert "workspace_id == 'ws''x'" in captured["filter"]


# ---------------------------------------------------------------------------
# Coverage: similarity_search dimension validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_similarity_search_unknown_column_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Unknown vector column"):
        await h.similarity_search("docs", [0.1] * 1536, vector_column="bogus")


@pytest.mark.asyncio
async def test_similarity_search_dim_mismatch_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Dimension mismatch"):
        await h.similarity_search(
            "docs", [0.1] * 10, vector_column="vector"  # expected 1536
        )


@pytest.mark.asyncio
async def test_similarity_search_table_missing_returns_empty():
    h = _make_handler()
    h.db = MagicMock()
    with patch.object(h, "get_table", return_value=None):
        result = await h.similarity_search("docs", [0.1] * 1536)
    assert result == []


@pytest.mark.asyncio
async def test_add_embedding_unknown_column_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Unknown vector column"):
        await h.add_embedding("docs", "ep1", [0.1] * 1536, vector_column="bad")


@pytest.mark.asyncio
async def test_add_embedding_dim_mismatch_raises():
    h = _make_handler()
    h.db = MagicMock()
    with pytest.raises(ValueError, match="Dimension mismatch"):
        await h.add_embedding("docs", "ep1", [0.1] * 5, vector_column="vector")


# ---------------------------------------------------------------------------
# Coverage: add_documents_batch with no embeddable docs
# ---------------------------------------------------------------------------
def test_add_documents_batch_returns_zero_when_no_embeddings():
    h = _make_handler()
    h.db = MagicMock()
    docs = [{"text": "a"}, {"text": "b"}]
    with patch.object(h, "embed_text", return_value=None):
        n = h.add_documents_batch("docs", docs)
    assert n == 0


def test_add_documents_batch_empty_list():
    h = _make_handler()
    h.db = MagicMock()
    assert h.add_documents_batch("docs", []) == 0


# ---------------------------------------------------------------------------
# Coverage: query_knowledge_graph exclude filter
# ---------------------------------------------------------------------------
def test_query_knowledge_graph_excludes_stale_doc_ids():
    h = _make_handler()
    h.db = MagicMock()
    fake_results = [
        {"id": "e1", "metadata": {"doc_id": "d1"}},
        {"id": "e2", "metadata": {"doc_id": "d2"}},  # excluded
        {"id": "e3", "metadata": {"doc_id": "d3"}},
        {"id": "e4", "metadata": {}},  # no doc_id → kept
    ]
    with patch.object(h, "search", return_value=fake_results):
        out = h.query_knowledge_graph("q", exclude_source_doc_ids={"d2"})
    ids = {r["id"] for r in out}
    assert ids == {"e1", "e3", "e4"}


def test_query_knowledge_graph_no_exclude_returns_all():
    h = _make_handler()
    h.db = MagicMock()
    fake_results = [{"id": "e1"}, {"id": "e2"}]
    with patch.object(h, "search", return_value=fake_results):
        out = h.query_knowledge_graph("q")
    assert len(out) == 2


# ---------------------------------------------------------------------------
# Coverage: get_table / drop_table / create_table when db is None
# ---------------------------------------------------------------------------
def test_get_table_returns_none_when_db_none():
    h = _make_handler()
    with patch.object(h, "_initialize_db"):
        assert h.get_table("docs") is None


def test_drop_table_returns_false_when_db_none():
    h = _make_handler()
    with patch.object(h, "_initialize_db"):
        assert h.drop_table("docs") is False


def test_create_table_returns_none_when_db_none():
    h = _make_handler()
    with patch.object(h, "_initialize_db"):
        assert h.create_table("docs") is None


def test_has_column_handles_error():
    """_has_column is defensive — any error → False."""
    bad_table = MagicMock()
    bad_table.schema = property(lambda self: (_ for _ in ()).throw(RuntimeError("x")))
    assert LanceDBHandler._has_column(bad_table, "vector") is False


# ---------------------------------------------------------------------------
# Coverage: list_documents offset/sort + metadata parsing
# ---------------------------------------------------------------------------
def test_list_documents_sorts_desc_and_applies_offset():
    h = _make_handler()
    h.db = MagicMock()
    fake_table = MagicMock()
    df = pd.DataFrame([
        {"id": "1", "text": "a", "source": "s", "metadata": "{}",
         "created_at": "2024-01-01"},
        {"id": "2", "text": "b", "source": "s", "metadata": '{"title":"B"}',
         "created_at": "2024-03-01"},
        {"id": "3", "text": "c", "source": "s", "metadata": None,
         "created_at": "2024-02-01"},
    ])
    sq = MagicMock()
    sq.limit.return_value.to_pandas.return_value = df
    fake_table.search.return_value = sq
    with patch.object(h, "get_table", return_value=fake_table):
        docs = h.list_documents("docs", limit=2, offset=0)
    # Sorted desc by created_at → id 2 (Mar) first, then id 3 (Feb)
    assert [d["id"] for d in docs] == ["2", "3"]
    assert docs[0]["title"] == "B"
    assert docs[1]["title"] == "s"  # metadata None → falls back to source


def test_list_documents_returns_empty_when_table_missing():
    h = _make_handler()
    h.db = MagicMock()
    with patch.object(h, "get_table", return_value=None):
        assert h.list_documents("docs") == []


# ---------------------------------------------------------------------------
# Coverage: get_lancedb_handler does not cache when db session is provided
# ---------------------------------------------------------------------------
def test_get_lancedb_handler_no_cache_when_db_provided():
    """Handlers created with a db session must NOT be cached (connection leak
    prevention — Issue #7488074293). The handler is returned fresh each call,
    and the global _workspace_handlers cache is NOT mutated."""
    import os
    with patch.dict(os.environ, {"LANCEDB_URI_BASE": "/tmp/atom_test_base"}):
        from core.lancedb_handler import get_lancedb_handler, _workspace_handlers
        before = set(_workspace_handlers.keys())
        db_session = MagicMock()
        h1 = get_lancedb_handler(workspace_id="leak-test-ws-2", db=db_session)
        h2 = get_lancedb_handler(workspace_id="leak-test-ws-2", db=db_session)
        after = set(_workspace_handlers.keys())
        # Cache must not have grown with the db-session workspace.
        assert "leak-test-ws-2" not in _workspace_handlers, (
            "handler created with a db session must not be cached"
        )
        # Each call returns a fresh instance (no caching).
        assert h1 is not h2


# ---------------------------------------------------------------------------
# Coverage: embed_text returns None when no embedding_service
# ---------------------------------------------------------------------------
def test_embed_text_no_service_returns_none():
    h = _make_handler()
    assert h.embed_text("hello") is None


@pytest.mark.asyncio
async def test_async_embed_text_no_service_returns_none():
    h = _make_handler()
    assert await h.async_embed_text("hello") is None
