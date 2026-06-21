"""
TDD Tests for GraphRAG Hybrid pgvector-Anchored Search (Open Source Port)

Mirrors atom-saas test_graphrag_hybrid_search.py.
The open-source engine uses get_db_session() context managers rather than
injecting a shared session, so tests mock get_db_session at the module level.
"""

from __future__ import annotations
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock, call
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from core.models import Base, GraphNode, Tenant, Workspace
from core.graphrag_engine import GraphRAGEngine, Entity, Relationship


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sqlite_db():
    """Return (engine, Session) backed by in-memory SQLite."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    return eng, Session


@contextmanager
def sqlite_session_ctx(Session):
    """Context manager that yields one SQLite session (mimics get_db_session)."""
    s = Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class TestGraphRAGHybridSearch:
    """Test Suite for pgvector-anchored hybrid search and ingestion (open-source)."""

    @pytest.fixture
    def db_setup(self):
        """Create SQLite engine + session factory and yield (Session, tenant_id, workspace_id)."""
        eng, Session = make_sqlite_db()

        s = Session()
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name="Test Tenant",
            subdomain=f"test-{uuid.uuid4().hex[:8]}",
        )
        s.add(tenant)
        s.flush()

        workspace = Workspace(
            id=str(uuid.uuid4()),
            name="Test Workspace",
            tenant_id=tenant.id,
        )
        s.add(workspace)
        s.commit()
        tenant_id = tenant.id
        workspace_id = workspace.id
        s.close()

        yield Session, tenant_id, workspace_id

        eng.dispose()

    @pytest.fixture
    def mock_embedding(self):
        return [0.1] * 1536

    # ------------------------------------------------------------------
    # Embedding stored during ingest_structured_data
    # ------------------------------------------------------------------

    def test_ingest_structured_data_saves_embedding(self, db_setup):
        """Verify structured ingestion writes embedding into the dedicated column."""
        Session, tenant_id, workspace_id = db_setup
        mock_emb = [0.2] * 1536

        engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)

        def _fake_ctx():
            return sqlite_session_ctx(Session)

        with patch("core.graphrag_engine.get_db_session", _fake_ctx):
            engine.ingest_structured_data(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                entities=[
                    {
                        "name": "Integration Entity",
                        "type": "technology",
                        "description": "Used for data transfer",
                        "properties": {"embedding": mock_emb},
                    }
                ],
                relationships=[],
            )

        # Verify via a fresh session
        s = Session()
        node = s.query(GraphNode).filter_by(name="Integration Entity").first()
        s.close()

        assert node is not None, "GraphNode not found"
        assert list(node.embedding) == pytest.approx(mock_emb)

    # ------------------------------------------------------------------
    # Embedding stored during add_entity
    # ------------------------------------------------------------------

    def test_add_entity_saves_embedding(self, db_setup):
        """Verify manual add_entity writes the embedding to the dedicated column."""
        Session, tenant_id, workspace_id = db_setup
        mock_emb = [0.3] * 1536

        engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)

        def _fake_ctx():
            return sqlite_session_ctx(Session)

        entity = Entity(
            id=str(uuid.uuid4()),
            name="Manual Entity",
            entity_type="concept",
            description="Manually created concept",
            properties={"embedding": mock_emb},
        )

        with patch("core.graphrag_engine.get_db_session", _fake_ctx):
            engine.add_entity(entity, workspace_id=workspace_id, tenant_id=tenant_id)

        s = Session()
        node = s.query(GraphNode).filter_by(name="Manual Entity").first()
        s.close()

        assert node is not None, "GraphNode not found"
        assert list(node.embedding) == pytest.approx(mock_emb)

    # ------------------------------------------------------------------
    # Tenant isolation
    # ------------------------------------------------------------------

    def test_ingest_preserves_tenant_id(self, db_setup):
        """Verify tenant_id is written on new graph nodes."""
        Session, tenant_id, workspace_id = db_setup

        engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)

        def _fake_ctx():
            return sqlite_session_ctx(Session)

        with patch("core.graphrag_engine.get_db_session", _fake_ctx):
            engine.ingest_structured_data(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                entities=[
                    {
                        "name": "Tenant Node",
                        "type": "concept",
                        "description": "Tests tenant_id propagation",
                        "properties": {},
                    }
                ],
                relationships=[],
            )

        s = Session()
        node = s.query(GraphNode).filter_by(name="Tenant Node").first()
        s.close()

        assert node is not None
        assert node.tenant_id == tenant_id

    # ------------------------------------------------------------------
    # local_search falls back to LIKE on SQLite
    # ------------------------------------------------------------------

    def test_local_search_hybrid_both_legs_run(self, db_setup):
        """
        True hybrid: keyword leg ALWAYS runs even when embeddings succeed.
        Nodes matched by name but not by vector (e.g. IDs, acronyms) must appear.
        """
        Session, tenant_id, workspace_id = db_setup

        # Node that ONLY matches by keyword (no embedding similarity)
        # Node that ONLY matches by vector (name doesn't contain query text)
        s = Session()
        keyword_only_node = GraphNode(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name="ACME-001",          # exact code — keyword will find it
            type="contract",
            description="Contract entity found by name only",
        )
        semantic_only_node = GraphNode(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name="contract management",   # name also contains query so both find it — OK
            type="concept",
            description="Concept entity",
        )
        s.add(keyword_only_node)
        s.add(semantic_only_node)
        s.commit()
        s.close()

        engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)

        # Mock engine.llm_service.generate_embedding to return a valid embedding.
        # Previously this patched core.graphrag_engine.BYOKHandler, but that
        # import was removed; local_search now calls self.llm_service.generate_embedding.
        mock_llm = MagicMock()
        mock_llm.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
        engine.llm_service = mock_llm

        def _fake_ctx():
            return sqlite_session_ctx(Session)

        with patch("core.graphrag_engine.get_db_session", _fake_ctx):
            # Query that keyword-matches "ACME-001" by substring
            results = engine.local_search(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                query="ACME-001",
            )

        assert results is not None
        assert results.get("mode") == "local"
        # ACME-001 must be in results (keyword leg)
        names = {e["name"] for e in results["entities"]}
        assert "ACME-001" in names, f"Keyword-only match missing. Got: {names}"

        # GAP-8: Verify workspace_id / tenant_id are forwarded to
        # generate_embedding — required for BYOK key resolution on
        # non-default tenants. If a future refactor drops these kwargs,
        # multi-tenant BYOK silently breaks.
        assert mock_llm.generate_embedding.called
        _, emb_kwargs = mock_llm.generate_embedding.call_args
        assert emb_kwargs.get("workspace_id") == workspace_id
        assert emb_kwargs.get("tenant_id") == tenant_id

    def test_local_search_fallback_on_sqlite(self, db_setup):
        """local_search keyword leg works on SQLite even when pgvector is unavailable."""
        Session, tenant_id, workspace_id = db_setup

        s = Session()
        node = GraphNode(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name="SQLite Node",
            type="database",
            description="Relational database fallback",
        )
        s.add(node)
        s.commit()
        s.close()

        engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)

        # Mock engine.llm_service.generate_embedding to raise, exercising the
        # keyword-fallback branch. Previously patched BYOKHandler module-level.
        mock_llm = MagicMock()
        mock_llm.generate_embedding = AsyncMock(side_effect=Exception("no embedding"))
        engine.llm_service = mock_llm

        def _fake_ctx():
            return sqlite_session_ctx(Session)

        with patch("core.graphrag_engine.get_db_session", _fake_ctx):
            results = engine.local_search(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                query="SQLite Node",
            )

        assert results is not None
        assert results.get("mode") == "local"
        assert len(results["entities"]) > 0
        assert results["entities"][0]["name"] == "SQLite Node"


    # ------------------------------------------------------------------
    # embedding column is nullable (no embedding = node still inserted)
    # ------------------------------------------------------------------

    def test_node_without_embedding_is_stored(self, db_setup):
        """Nodes without embeddings should still be created (embedding is nullable)."""
        Session, tenant_id, workspace_id = db_setup

        engine = GraphRAGEngine(workspace_id=workspace_id, tenant_id=tenant_id)

        def _fake_ctx():
            return sqlite_session_ctx(Session)

        with patch("core.graphrag_engine.get_db_session", _fake_ctx):
            engine.ingest_structured_data(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                entities=[
                    {
                        "name": "No-Embedding Node",
                        "type": "concept",
                        "description": "Node with no embedding",
                        "properties": {},
                    }
                ],
                relationships=[],
            )

        s = Session()
        node = s.query(GraphNode).filter_by(name="No-Embedding Node").first()
        s.close()

        assert node is not None
        assert node.embedding is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
