"""
W6 — SQLMultiHopExpander SQLite portability.

RED: `_expand_sql_impl` emits Postgres-only syntax unconditionally
(`ARRAY[n.id]`, `NULL::varchar`, `= ANY(t.path)`, `ANY(:node_ids)`), so on
SQLite (Personal Edition default) every call raises OperationalError, the
except swallows it into `metadata["error"] = "expansion_failed"`, and the
engine's multi-hop augmentation silently degrades to nothing.

Contracts pinned here:
  - on a sqlite-bound session the expansion actually traverses: chain
    A->B->C resolves all three nodes with correct hop levels and the
    relationship listing returns the traversed edges (no error metadata).
  - the W1 as_of cutoff works on the sqlite variant too (future-born edge
    pruned; invalidated edge pruned; boundary exclusive).
  - bind-less sessions (legacy recording-session callers / Postgres prod)
    keep the byte-identical Postgres text — covered by W1's suite; here we
    additionally pin that a postgres-bound session still gets the ANY()
    variant.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.graphrag.multi_hop_expansion import SQLMultiHopExpander
from core.models import GraphEdge, GraphNode

UTC = timezone.utc


def _utc(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _seed(db):
    for nid in ("A", "B", "C", "D"):
        db.add(GraphNode(id=nid, workspace_id="ws-1", name=nid, type="company",
                         created_at=_utc(2026, 1, 1)))
    db.add(GraphEdge(id="e-ab", workspace_id="ws-1", source_node_id="A",
                     target_node_id="B", relationship_type="related_to",
                     valid_from=_utc(2026, 1, 1)))
    db.add(GraphEdge(id="e-bc", workspace_id="ws-1", source_node_id="B",
                     target_node_id="C", relationship_type="part_of",
                     valid_from=_utc(2026, 1, 1)))
    db.commit()


class TestSqliteExpansionWorks:
    def test_chain_traverses_on_sqlite(self, db):
        _seed(db)
        result = SQLMultiHopExpander().expand_sql("A", "ws-1", max_depth=3, session=db)
        assert "error" not in result.metadata
        found = {n.id for n in result.nodes}
        assert found == {"A", "B", "C"}
        hops = {n.id: n.hop_level for n in result.nodes}
        assert hops["B"] == 1 and hops["C"] == 2

    def test_relationships_returned_on_sqlite(self, db):
        _seed(db)
        result = SQLMultiHopExpander().expand_sql("A", "ws-1", max_depth=3, session=db)
        rel_types = {r["type"] for r in result.relationships}
        assert {"related_to", "part_of"} <= rel_types

    def test_as_of_prunes_future_edge_on_sqlite(self, db):
        _seed(db)
        # e-cd born after the cutoff -> D unreachable at that instant
        db.add(GraphEdge(id="e-cd", workspace_id="ws-1", source_node_id="C",
                         target_node_id="D", relationship_type="related_to",
                         valid_from=_utc(2026, 7, 1)))
        db.commit()
        result = SQLMultiHopExpander().expand_sql(
            "A", "ws-1", max_depth=3, session=db, as_of=_utc(2026, 6, 1),
        )
        assert "error" not in result.metadata
        assert {n.id for n in result.nodes} == {"A", "B", "C"}
        assert result.metadata.get("as_of") == _utc(2026, 6, 1).isoformat()

    def test_as_of_includes_edge_before_invalidation_on_sqlite(self, db):
        _seed(db)
        # e-ad alive only in Q1: reachable at Mar, gone by Jun
        db.add(GraphEdge(id="e-ad", workspace_id="ws-1", source_node_id="A",
                         target_node_id="D", relationship_type="related_to",
                         valid_from=_utc(2026, 1, 1), invalid_at=_utc(2026, 5, 1)))
        db.commit()
        march = SQLMultiHopExpander().expand_sql(
            "A", "ws-1", max_depth=3, session=db, as_of=_utc(2026, 3, 1),
        )
        assert {n.id for n in march.nodes} == {"A", "B", "C", "D"}
        june = SQLMultiHopExpander().expand_sql(
            "A", "ws-1", max_depth=3, session=db, as_of=_utc(2026, 6, 1),
        )
        assert {n.id for n in june.nodes} == {"A", "B", "C"}

    def test_no_as_of_is_legacy_unfiltered_on_sqlite(self, db):
        _seed(db)
        db.add(GraphEdge(id="e-ad", workspace_id="ws-1", source_node_id="A",
                         target_node_id="D", relationship_type="related_to",
                         valid_from=_utc(2026, 1, 1), invalid_at=_utc(2026, 5, 1)))
        db.commit()
        result = SQLMultiHopExpander().expand_sql("A", "ws-1", max_depth=3, session=db)
        # legacy = no validity filtering at all (W1 contract): everything reachable
        assert {n.id for n in result.nodes} == {"A", "B", "C", "D"}


class TestPostgresVariantUnchanged:
    def test_postgres_bind_keeps_any_syntax(self, db):
        """A postgres-bound session must still receive the ANY() CTE."""
        _seed(db)
        engine = db.bind
        # fake a postgres dialect marker without a real PG server: wrap the
        # session's bind dialect name just long enough to capture the SQL
        captured = {}

        class _PgDialect:
            name = "postgresql"

        class _PgBind:
            dialect = _PgDialect()

        orig_execute = db.execute

        def spy(sql, params=None):
            captured["sql"] = str(sql)
            return orig_execute(sql, params)

        db.execute = spy
        object.__setattr__(db, "bind", _PgBind()) if False else None
        # Session.bind is a plain attribute on a bound sessionmaker session;
        # monkeypatching it directly is safe for the duration of the call.
        real_bind = db.bind
        db.bind = _PgBind()
        try:
            SQLMultiHopExpander().expand_sql("A", "ws-1", max_depth=1, session=db)
        finally:
            db.bind = real_bind
        assert "ANY(t.path)" in captured["sql"]
        assert "ARRAY[" in captured["sql"]