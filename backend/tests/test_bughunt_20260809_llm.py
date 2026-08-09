"""Bughunt 2026-08-09 — LLM routing + orchestration + hybrid search bugs.

Targets (see task scope):
  A. Learning router live-path cache-key mismatch — predictors trained under
     "{tenant}:{task}" (record_feedback/_retrain_router) but the BYOK live
     path looks them up under "{tenant}:{task}:{intent}" — a guaranteed miss,
     so ATOM_LEARNING_ROUTER=true never re-ranks (feature inert).
  B. Lexical ranker stopword-query regression — FTS5 prefix semantics + PG
     english stopword drop make "and"/"or"-style queries return [] while the
     ILIKE fallback matches (same function, DB-state-dependent results).
  C. Hybrid search vector leg ignores the source filter — source="knowledge"
     still surfaces bridged IngestedDocument hits from the vector leg.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests.test_covpush_bigfour_byok import make_handler

# ============================================================================
# A. Learning router live path
# ============================================================================

def _router_with_predictor(key: str):
    """A LearningBasedRouter-shaped mock whose predictor lives at ``key`` —
    exactly what record_feedback -> _retrain_router -> _get_per_model_router
    produce (2-part "{tenant}:{task}" keys; no intent dimension exists on the
    training side)."""
    router = Mock()
    per_model = Mock()
    per_model.predict_satisfaction = Mock(side_effect=[0.9, 0.1])
    per_model.confidence = Mock(return_value=0.3)
    router._per_model_routers = {key: per_model}
    router._extract_request_features = Mock(return_value={"f": 1})
    router.stash_decision = Mock(return_value="dec-1")
    router._ema_scores = {}
    router._EMA_SCORE_WEIGHT = 0.3
    return router, per_model


@pytest.mark.asyncio
async def test_rerank_uses_predictor_trained_under_tenant_task_key(monkeypatch):
    """Trained predictors live under "t-1:question_answering" (training has no
    intent dimension). The live path must find them there — intent must not
    create a key the training side never writes."""
    monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
    h = make_handler()
    router, per_model = _router_with_predictor("t-1:question_answering")
    with patch("core.llm.learning_router_registry.get_learning_router_instance",
               return_value=router), \
         patch("core.llm.learning_router_registry.ema_router_enabled",
               return_value=False):
        result = await h._rerank_with_learning(
            [("a", "m1"), ("b", "m2")], "p", "chat", intent="coding")
    per_model.predict_satisfaction.assert_called()
    assert result[0] == ("a", "m1"), (
        "predictor gave m1 0.9 vs m2 0.1; m1 must rank first — got "
        f"{result}"
    )


@pytest.mark.asyncio
async def test_rerank_uses_predictor_when_intent_none(monkeypatch):
    """intent=None must also resolve the trained 2-part key (no '_' suffix)."""
    monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
    h = make_handler()
    router, per_model = _router_with_predictor("t-1:question_answering")
    with patch("core.llm.learning_router_registry.get_learning_router_instance",
               return_value=router), \
         patch("core.llm.learning_router_registry.ema_router_enabled",
               return_value=False):
        result = await h._rerank_with_learning(
            [("a", "m1"), ("b", "m2")], "p", "chat")
    per_model.predict_satisfaction.assert_called()
    assert result[0] == ("a", "m1")


# ============================================================================
# B. Lexical ranker stopword-query consistency
# ============================================================================

FTS_INGESTED_SQL = (
    "CREATE VIRTUAL TABLE ingested_documents_fts USING fts5("
    "file_name, content_preview, content='ingested_documents', content_rowid='rowid')"
)
FTS_KNOWLEDGE_SQL = (
    "CREATE VIRTUAL TABLE knowledge_documents_fts USING fts5("
    "title, content, content='knowledge_documents', content_rowid='rowid')"
)


@pytest.fixture
def stopword_db():
    """In-memory DB with FTS tables + a doc where 'and' occurs ONLY inside
    another word ('understand') — ILIKE matches it, FTS5 prefix 'and*' cannot."""
    from core.models import Base, IngestedDocument

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        IngestedDocument(
            id="doc_stand",
            workspace_id="default",
            file_name="standalone.txt",
            file_path="/standalone.txt",
            file_type="txt",
            integration_id="google_drive",
            file_size_bytes=10,
            content_preview="Understand the quarterly revenue report.",
            external_id="e1",
            ingested_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    session.execute(text(FTS_INGESTED_SQL))
    session.execute(text(FTS_KNOWLEDGE_SQL))
    session.execute(
        text(
            "INSERT INTO ingested_documents_fts(rowid, file_name, content_preview) "
            "SELECT rowid, COALESCE(file_name,''), COALESCE(content_preview,'') "
            "FROM ingested_documents"
        )
    )
    session.commit()
    yield session
    session.close()


def test_stopword_query_consistent_with_iliike_fallback(stopword_db):
    """Query 'and' (English stopword): the ILIKE fallback matches
    'understand'; the FTS path must not silently return [] — same query must
    give the same result regardless of whether FTS tables exist (PG english
    config also drops 'and' from tsquery, making the FTS path return [])."""
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    results = search_documents_lexical(stopword_db, "and")
    ids = [r["id"] for r in results]
    assert "doc_stand" in ids, (
        "ILIKE semantics match 'understand'; FTS path must fall back to ILIKE "
        f"for stopword-only queries — got {ids}"
    )


@pytest.fixture
def stopword_db_without_fts():
    """Same doc, no FTS tables — the ILIKE fallback path."""
    from core.models import Base, IngestedDocument

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        IngestedDocument(
            id="doc_stand",
            workspace_id="default",
            file_name="standalone.txt",
            file_path="/standalone.txt",
            file_type="txt",
            integration_id="google_drive",
            file_size_bytes=10,
            content_preview="Understand the quarterly revenue report.",
            external_id="e1",
            ingested_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    yield session
    session.close()


def test_stopword_query_iliike_fallback_matches(stopword_db_without_fts):
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    results = search_documents_lexical(stopword_db_without_fts, "and")
    ids = [r["id"] for r in results]
    assert "doc_stand" in ids


# ============================================================================
# D. Community detection — generated community ids must be globally unique
# ============================================================================

@pytest.fixture
def community_db():
    """In-memory DB with two workspaces, each with two 4-cliques joined by a
    bridge edge (yields real communities under the default ADAPTIVE
    resolution)."""
    from core.models import Base, GraphNode, GraphEdge

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    for ws in ("ws_1", "ws_2"):
        ids = [f"{ws}_n{i}" for i in range(8)]
        for nid in ids:
            session.add(
                GraphNode(
                    id=nid, workspace_id=ws, name=f"node {nid}", type="task"
                )
            )
        # clique A: 0-3 fully connected; clique B: 4-7 fully connected
        for clique in ((0, 1, 2, 3), (4, 5, 6, 7)):
            for a_i in range(4):
                for b_i in range(a_i + 1, 4):
                    session.add(
                        GraphEdge(
                            id=f"{ws}_e{clique[0]}_{a_i}_{b_i}",
                            workspace_id=ws,
                            source_node_id=ids[clique[a_i]],
                            target_node_id=ids[clique[b_i]],
                            relationship_type="depends_on",
                        )
                    )
        # bridge
        session.add(
            GraphEdge(
                id=f"{ws}_bridge",
                workspace_id=ws,
                source_node_id=ids[0],
                target_node_id=ids[4],
                relationship_type="depends_on",
            )
        )
    session.commit()
    yield session
    session.close()


def test_community_storage_unique_ids_across_workspaces(community_db):
    """Community ids are generated as 'comm_<i>' / 'leiden_comm_<i>' — NOT
    unique across workspaces, but GraphCommunity.id is a global PK. The second
    workspace's insert collides -> IntegrityError -> rollback -> storage
    silently fails. Each workspace must persist its own communities."""
    from core.graphrag.community_detection import CommunityDetectionService
    from core.models import GraphCommunity

    svc = CommunityDetectionService()
    r1 = svc.detect_communities("ws_1", session=community_db, store_results=True)
    r2 = svc.detect_communities("ws_2", session=community_db, store_results=True)
    assert r1.num_communities >= 1 and r2.num_communities >= 1, (
        "both graphs must yield communities"
    )

    ws1_count = (
        community_db.query(GraphCommunity)
        .filter(GraphCommunity.workspace_id == "ws_1")
        .count()
    )
    ws2_count = (
        community_db.query(GraphCommunity)
        .filter(GraphCommunity.workspace_id == "ws_2")
        .count()
    )
    assert ws1_count >= 1, "ws_1 communities must persist"
    assert ws2_count >= 1, (
        "ws_2 communities must persist — 'comm_0' PK collides with ws_1's "
        "row and the whole store rolls back (got 0)"
    )


# ============================================================================
# C. Hybrid search vector leg must respect the source filter
# ============================================================================

class FakeLanceDB:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = rows

    def search(self, table_name, query, user_id=None, limit=10, filter_str=None, **kwargs):
        return [dict(r) for r in self.rows[:limit]]


@pytest.fixture
def hybrid_db():
    from core.models import Base, IngestedDocument, KnowledgeDocument

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            IngestedDocument(
                id="doc_a",
                workspace_id="default",
                tenant_id="default",
                file_name="revenue_report.pdf",
                file_path="/reports/revenue_report.pdf",
                file_type="pdf",
                integration_id="google_drive",
                file_size_bytes=100,
                content_preview="Quarterly revenue grew twenty percent.",
                external_id="e1",
                ingested_at=datetime.now(timezone.utc),
            ),
            KnowledgeDocument(
                id="kd_a",
                workspace_id="default",
                tenant_id="default",
                title="Growth strategy",
                content="Revenue growth strategy for the enterprise market segment.",
            ),
        ]
    )
    session.commit()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_vector_leg_respects_source_filter(hybrid_db, monkeypatch):
    """source='knowledge' must never surface ingested-doc vector hits."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([{"id": "doc_a", "_distance": 0.05, "metadata": {}}])
    svc = DocumentsHybridSearch(db=hybrid_db, lancedb=lancedb)

    res = await svc.search("revenue", source="knowledge")
    ids = [r["id"] for r in res["results"]]
    assert "doc_a" not in ids, (
        "source=knowledge must exclude ingested-doc vector hits — got "
        f"{ids}"
    )
    assert "kd_a" in ids, "knowledge docs must still be returned"

    res = await svc.search("revenue", source="ingested")
    ids = [r["id"] for r in res["results"]]
    assert "doc_a" in ids, "source=ingested must keep vector hits"
    assert "kd_a" not in ids
