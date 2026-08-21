"""
P2 tests: bi-temporal edges (P2.2) + consolidation worker rules (P2.1).
"""

import os
os.environ.setdefault("TESTING", "1")
os.environ["DATABASE_URL"] = "sqlite:///./test_p2.db"

import pytest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def hermetic_db(monkeypatch):
    """Isolate P2 tests from the shared dev DB.

    The session engine binds at first `core.database` import (conftest /
    module order), so the module-top DATABASE_URL override above never
    takes effect and these tests would write fixed-PK rows into the real
    dev store. Patching core.database's SessionLocal/engine routes every
    call (incl. GraphRAGEngine's shared get_db_session) to a throwaway
    in-memory SQLite.
    """
    import core.database as db
    from core.models_registration import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", SessionLocal)
    monkeypatch.setattr(db, "get_db_session", _session)


# --------------------------------------------------------------------------- #
# P2.2 — bi-temporal edges
# --------------------------------------------------------------------------- #

class TestBiTemporalEdges:
    def test_model_has_bi_temporal_columns(self):
        from core.models import GraphEdge

        for col in ("valid_from", "invalid_at", "invalidation_reason"):
            assert col in GraphEdge.__table__.columns

    def test_reads_filter_invalidated_edges(self):
        """local_search/edges SQL must exclude invalidated edges."""
        import inspect
        from core.graphrag_engine import GraphRAGEngine

        src = inspect.getsource(GraphRAGEngine.local_search)
        assert src.count("invalid_at IS NULL") >= 3  # traversal (pg+sqlite) + edges legs

    def test_invalidate_and_as_of(self, tmp_path):
        import uuid as _uuid
        from core.graphrag_engine import GraphRAGEngine
        from core.database import get_db_session, Base, engine
        from core.models import GraphNode, GraphEdge

        Base.metadata.create_all(bind=engine)
        ws = f"p2-bitemporal-{_uuid.uuid4().hex[:8]}"
        n1, n2 = f"{ws}-n1", f"{ws}-n2"
        with get_db_session() as s:
            s.add(GraphNode(id=n1, workspace_id=ws, name="A", type="x"))
            s.add(GraphNode(id=n2, workspace_id=ws, name="B", type="x"))
            s.commit()
            e = GraphEdge(
                workspace_id=ws, source_node_id=n1, target_node_id=n2,
                relationship_type="supplies", valid_from=datetime.utcnow() - timedelta(days=30),
            )
            s.add(e)
            s.commit()
            edge_id = e.id

        g = GraphRAGEngine(workspace_id=ws)
        # Active as of now
        assert any(r["id"] == edge_id for r in g.edges_as_of(datetime.utcnow(), ws))
        # Not yet valid 60 days ago
        assert not any(r["id"] == edge_id for r in g.edges_as_of(datetime.utcnow() - timedelta(days=60), ws))

        assert g.invalidate_edge(edge_id, "test supersede") is True
        # Invalidated → not visible now, but WAS visible before invalidation
        assert not any(r["id"] == edge_id for r in g.edges_as_of(datetime.utcnow(), ws))
        assert any(r["id"] == edge_id for r in g.edges_as_of(datetime.utcnow() - timedelta(days=1), ws))
        # Idempotent
        assert g.invalidate_edge(edge_id, "again") is False


# --------------------------------------------------------------------------- #
# P2.1 — consolidation rules
# --------------------------------------------------------------------------- #

class TestConsolidationRules:
    def test_edge_contradiction_newest_wins(self):
        import uuid as _uuid
        from core.memory_consolidator import consolidate_edges
        from core.database import get_db_session, Base, engine
        from core.models import GraphNode, GraphEdge

        Base.metadata.create_all(bind=engine)
        ws = f"p2-consolidation-{_uuid.uuid4().hex[:8]}"
        n_old, n_new = f"{ws}-old", f"{ws}-new"
        with get_db_session() as s:
            s.add(GraphNode(id=n_old, workspace_id=ws, name="old", type="x"))
            s.add(GraphNode(id=n_new, workspace_id=ws, name="new", type="x"))
            s.commit()
            old_e = GraphEdge(workspace_id=ws, source_node_id=n_old, target_node_id=n_new,
                              relationship_type="priced_at",
                              properties={"price": 100},
                              created_at=datetime.utcnow() - timedelta(days=10))
            new_e = GraphEdge(workspace_id=ws, source_node_id=n_old, target_node_id=n_new,
                              relationship_type="priced_at",
                              properties={"price": 200},
                              created_at=datetime.utcnow())
            s.add(old_e); s.add(new_e)
            s.commit()
            old_id, new_id = old_e.id, new_e.id

        report = consolidate_edges(ws)
        assert report["invalidated"] == 1
        with get_db_session() as s:
            old = s.get(GraphEdge, old_id)
            new = s.get(GraphEdge, new_id)
            assert old.invalid_at is not None and "superseded" in (old.invalidation_reason or "")
            assert new.invalid_at is None

    def test_fact_supersede_rule(self):
        from core.memory_consolidator import _fact_subject_prefix, _fact_value

        assert _fact_value("ACME budget is around $80,000 USD") == "$80,000"
        assert _fact_value("no numbers here") is None
        assert _fact_subject_prefix("ACME Fabrication budget is 80k").startswith("acme fabrication")

    def test_consolidate_workspace_never_raises(self):
        from core.memory_consolidator import consolidate_workspace

        r = consolidate_workspace("default")
        assert "workspace" in r and "ran_at" in r
