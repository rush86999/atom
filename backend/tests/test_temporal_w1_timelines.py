"""
W1 — timeline behaviors in multi-hop expansion + community detection.

RED: `MultiHopExpander.expand`/`SQLMultiHopExpander.expand_sql` accept no
`as_of`, and `CommunityDetectionService.detect_communities`/`_build_graph`
accept no rolling window — the keyword args below raise TypeError = RED.

Contracts pinned here:
  - expansion with as_of excludes edges that did not exist yet
    (valid_from > as_of) or were already invalidated (invalid_at <= as_of);
    None = legacy behavior (no filter). Metadata records the as_of used.
  - SQL expander threads the same cutoff into the recursive CTE and the
    relationship listing; params are injected only with the clause (SQLAlchemy
    text() rejects unused bound params).
  - community detection rolling window [window_start, window_end]: only edges
    whose validity interval overlaps the window participate
    (valid_from <= end and invalid_at > start, open on either side); nodes
    participate when created within the window (created_at <= end). Both None
    = legacy (all edges/nodes). Window is recorded in result metadata.
"""

import re
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.graphrag.community_detection import (
    CommunityDetectionService,
    DetectionResult,
)
from core.graphrag.multi_hop_expansion import MultiHopExpander, SQLMultiHopExpander
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


def _seed_node(db, nid: str, created_at=None):
    node = GraphNode(id=nid, workspace_id="ws-1", name=nid, type="company",
                     created_at=created_at or _utc(2026, 1, 1))
    db.add(node)
    return node


def _seed_edge(db, eid: str, src: str, tgt: str, valid_from, invalid_at=None):
    edge = GraphEdge(
        id=eid, workspace_id="ws-1", source_node_id=src, target_node_id=tgt,
        relationship_type="related_to", valid_from=valid_from, invalid_at=invalid_at,
    )
    db.add(edge)
    return edge


# ============================================================================
# Multi-hop expansion — as_of timeline cutoff (ORM path)
# ============================================================================

class TestMultiHopExpansionAsOf:
    def _seed(self, db):
        for nid in ("A", "B", "C", "D"):
            _seed_node(db, nid)
        _seed_edge(db, "e-ab", "A", "B", _utc(2026, 1, 1))
        _seed_edge(db, "e-ac", "A", "C", _utc(2026, 7, 1))          # born later
        _seed_edge(db, "e-ad", "A", "D", _utc(2026, 1, 1), _utc(2026, 5, 1))  # invalidated
        db.commit()

    def test_as_of_excludes_future_edges(self, db):
        self._seed(db)
        result = MultiHopExpander().expand("A", "ws-1", session=db, as_of=_utc(2026, 6, 1))
        found = {n.id for n in result.nodes}
        assert found == {"A", "B"}  # C not born yet, D already invalidated

    def test_as_of_includes_before_invalidation(self, db):
        self._seed(db)
        result = MultiHopExpander().expand("A", "ws-1", session=db, as_of=_utc(2026, 3, 1))
        found = {n.id for n in result.nodes}
        assert found == {"A", "B", "D"}

    def test_invalidation_boundary_is_exclusive(self, db):
        self._seed(db)
        # invalid_at=2026-05-01 means the edge was gone BY that instant.
        result = MultiHopExpander().expand("A", "ws-1", session=db, as_of=_utc(2026, 5, 1))
        found = {n.id for n in result.nodes}
        assert found == {"A", "B"}

    def test_no_as_of_is_legacy_all_edges(self, db):
        self._seed(db)
        result = MultiHopExpander().expand("A", "ws-1", session=db)
        found = {n.id for n in result.nodes}
        assert found == {"A", "B", "C", "D"}

    def test_as_of_recorded_in_metadata(self, db):
        self._seed(db)
        result = MultiHopExpander().expand("A", "ws-1", session=db, as_of=_utc(2026, 6, 1))
        assert result.metadata.get("as_of") == _utc(2026, 6, 1).isoformat()

    def test_edges_with_null_valid_from_are_always_visible(self, db):
        _seed_node(db, "A")
        _seed_node(db, "B")
        _seed_edge(db, "e-ab", "A", "B", None)  # legacy rows: validity unknown
        db.commit()
        result = MultiHopExpander().expand("A", "ws-1", session=db, as_of=_utc(2020, 1, 1))
        found = {n.id for n in result.nodes}
        assert found == {"A", "B"}


class TestSQLExpanderAsOf:
    """SQL path: assert the cutoff reaches the CTE + relationship query, and
    that parameters are bound only when the clause is present."""

    class _RecordingSession:
        def __init__(self, rows=None):
            self.rows = rows or []
            self.calls = []

        def execute(self, sql, params=None):
            self.calls.append((str(sql), dict(params or {})))
            return _Result(self.rows)

        def close(self):
            pass

    def test_as_of_clause_emitted_with_param(self):
        sess = self._RecordingSession()
        SQLMultiHopExpander().expand_sql("A", "ws-1", session=sess, as_of=_utc(2026, 6, 1))
        sql, params = sess.calls[0]
        assert "invalid_at" in sql
        assert "as_of" in params

    def test_legacy_sql_has_no_as_of_clause_or_param(self):
        sess = self._RecordingSession()
        SQLMultiHopExpander().expand_sql("A", "ws-1", session=sess)
        sql, params = sess.calls[0]
        assert "invalid_at" not in sql
        assert "as_of" not in params

    def test_relationship_listing_filtered_too(self):
        row = SimpleNamespace(
            id="B", name="B", type="company", description=None,
            properties={}, hop_level=1, relevance_score=0.9,
        )
        sess = self._RecordingSession(rows=[row])
        SQLMultiHopExpander().expand_sql("A", "ws-1", session=sess, as_of=_utc(2026, 6, 1))
        assert len(sess.calls) >= 2
        rel_sql, rel_params = sess.calls[1]
        assert "invalid_at" in rel_sql
        assert rel_params.get("as_of_rel") == _utc(2026, 6, 1)

    def test_sql_metadata_records_as_of(self):
        sess = self._RecordingSession()
        result = SQLMultiHopExpander().expand_sql("A", "ws-1", session=sess, as_of=_utc(2026, 6, 1))
        assert result.metadata.get("as_of") == _utc(2026, 6, 1).isoformat()
        legacy = SQLMultiHopExpander().expand_sql("A", "ws-1", session=self._RecordingSession())
        assert "as_of" not in legacy.metadata


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


# ============================================================================
# Community detection — rolling window
# ============================================================================

class TestCommunityDetectionWindow:
    def _seed(self, db):
        _seed_node(db, "A", created_at=_utc(2026, 1, 1))
        _seed_node(db, "B", created_at=_utc(2026, 1, 1))
        _seed_node(db, "C", created_at=_utc(2026, 7, 1))
        _seed_edge(db, "e-ab", "A", "B", _utc(2026, 1, 1))
        _seed_edge(db, "e-bc", "B", "C", _utc(2026, 7, 1))
        db.commit()

    def test_window_end_filters_edges_and_nodes(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        graph = svc._build_graph("ws-1", db, window_start=_utc(2026, 4, 1),
                                 window_end=_utc(2026, 6, 1))
        assert graph.number_of_nodes() == 2  # A, B (C created after window)
        assert graph.number_of_edges() == 1  # A-B only

    def test_full_window_includes_everything(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        graph = svc._build_graph("ws-1", db, window_start=_utc(2026, 1, 1),
                                 window_end=_utc(2026, 12, 31))
        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 2

    def test_window_start_excludes_invalidated_edges(self, db):
        self._seed(db)
        _seed_edge(db, "e-ac", "A", "C", _utc(2026, 1, 1), _utc(2026, 5, 1))
        db.commit()
        svc = CommunityDetectionService()
        after = svc._build_graph("ws-1", db, window_start=_utc(2026, 6, 1),
                                 window_end=_utc(2026, 12, 31))
        # e-ac invalidated before window start → absent; e-ab and e-bc alive.
        assert after.number_of_edges() == 2
        before = svc._build_graph("ws-1", db, window_start=_utc(2026, 3, 1),
                                  window_end=_utc(2026, 12, 31))
        assert before.number_of_edges() == 3  # all three alive in this window

    def test_no_window_is_legacy_all_edges(self, db):
        self._seed(db)
        graph = CommunityDetectionService()._build_graph("ws-1", db)
        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 2

    def test_detect_communities_records_window_metadata(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        with patch.object(
            svc.leiden, "detect",
            return_value=DetectionResult(num_communities=1, modularity=0.5, coverage=1.0),
        ):
            result = svc.detect_communities(
                "ws-1", session=db, store_results=False,
                window_start=_utc(2026, 4, 1), window_end=_utc(2026, 8, 1),
            )
        assert result.metadata["window_start"] == _utc(2026, 4, 1).isoformat()
        assert result.metadata["window_end"] == _utc(2026, 8, 1).isoformat()
        # A, B (Jan) and C (Jul) all fall inside the window; both edges too.
        assert result.metadata["graph_nodes"] == 3
        assert result.metadata["graph_edges"] == 2

    def test_windowed_graph_too_small_reason(self, db):
        # Window before anything exists → empty graph → graph_too_small.
        self._seed(db)
        svc = CommunityDetectionService()
        result = svc.detect_communities(
            "ws-1", session=db, store_results=False,
            window_start=_utc(2025, 1, 1), window_end=_utc(2025, 12, 31),
        )
        assert result.num_communities == 0
        assert result.metadata.get("reason") == "graph_too_small"