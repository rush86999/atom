"""
Hybrid search Step 3 — DocumentsHybridSearch: vector leg + lexical leg → RRF.

Verifies the fusion service that makes documents.search semantic. Matches the
async contract in core/hybrid_search/documents_hybrid.py: ``search()`` returns
``{success, query, results, hybrid, stats}`` where ``hybrid`` is the
degradation label (bm25_vector_rrf | lexical_only | semantic_only | no_results).
"""
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from core.hybrid_search.documents_hybrid import DocumentsHybridSearch


def _svc():
    return DocumentsHybridSearch(db=None, lancedb=MagicMock())


# ---------------------------------------------------------------------------
# Degradation ladder
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_both_legs_empty_returns_no_results():
    svc = _svc()
    with patch.object(svc, "_lexical_leg", return_value=[]), \
         patch.object(svc, "_vector_leg", new=AsyncMock(return_value=[])):
        resp = await svc.search("obscure query")
    assert resp["hybrid"] == "no_results"
    assert resp["results"] == []


@pytest.mark.asyncio
async def test_vector_empty_falls_back_to_lexical_only():
    svc = _svc()
    lexical = [{"source": "ingested", "id": "doc_1", "title": "R", "preview": "...", "score": 0.9}]

    # Explicitly empty vector leg (AsyncMock(return_value=[]) still yields a
    # truthy MagicMock if not awaited correctly — define a real coroutine).
    async def _empty_vector(*a, **kw):
        return []

    with patch.object(svc, "_lexical_leg", return_value=lexical), \
         patch.object(svc, "_vector_leg", side_effect=_empty_vector):
        resp = await svc.search("revenue")
    assert resp["hybrid"] == "lexical_only", (
        "empty vector leg must degrade to lexical_only, not bm25_vector_rrf"
    )
    assert len(resp["results"]) >= 1
    assert resp["results"][0]["id"] == "doc_1"


@pytest.mark.asyncio
async def test_short_query_returns_no_results():
    """Queries <3 chars are trivial → no_results without calling either leg."""
    svc = _svc()
    resp = await svc.search("x")
    assert resp["hybrid"] == "no_results"


# ---------------------------------------------------------------------------
# RRF fusion: docs in both legs rank higher
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fused_doc_in_both_legs_ranks_higher():
    """A doc appearing in both lexical + vector legs outranks single-leg docs."""
    svc = _svc()
    # doc_both appears in both; doc_lex and doc_vec in one each.
    lexical = [
        {"source": "ingested", "id": "doc_both", "title": "B", "preview": "x", "score": 0.9},
        {"source": "ingested", "id": "doc_lex", "title": "L", "preview": "y", "score": 0.7},
    ]
    vector = [
        {"id": "doc_both", "score": 0.8, "metadata": {}},
        {"id": "doc_vec", "score": 0.6, "metadata": {}},
    ]
    # _fuse_rrf resolves vector ids against PG; stub the DB so doc_both + doc_vec resolve.
    fake_doc = MagicMock(file_name="x", content_preview="x", external_modified_at=None)
    fake_db = MagicMock()
    fake_db.__enter__ = lambda self: fake_db
    fake_db.__exit__ = lambda self, *a: None
    fake_db.query.return_value.filter.return_value.all.return_value = [fake_doc, fake_doc]
    svc._db = fake_db
    with patch.object(svc, "_lexical_leg", return_value=lexical), \
         patch.object(svc, "_vector_leg", new=AsyncMock(return_value=vector)):
        resp = await svc.search("revenue")
    ids = [r["id"] for r in resp["results"]]
    # doc_both is in both legs → highest RRF score → ranks first.
    assert ids[0] == "doc_both", "a doc in both legs must rank highest under RRF"


# ---------------------------------------------------------------------------
# Unbridged hits: vector hit with no PG row is counted, not silently lost
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unbridged_vector_hit_counted_in_stats():
    """Vector hits that don't resolve to a PG row are counted in stats.unbridged_hits."""
    svc = _svc()
    vector = [{"id": "ghost_doc", "score": 0.8, "metadata": {}}]
    fake_db = MagicMock()
    fake_db.__enter__ = lambda self: fake_db
    fake_db.__exit__ = lambda self, *a: None
    # No PG row for "ghost_doc".
    fake_db.query.return_value.filter.return_value.all.return_value = []
    svc._db = fake_db
    with patch.object(svc, "_lexical_leg", return_value=[]), \
         patch.object(svc, "_vector_leg", new=AsyncMock(return_value=vector)):
        resp = await svc.search("ghost content")
    assert resp["stats"]["unbridged_hits"] >= 1, (
        "unbridged vector hits must be counted in stats, not silently dropped"
    )
