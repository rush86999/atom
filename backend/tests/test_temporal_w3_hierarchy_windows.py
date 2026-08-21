"""
W3 — detect_hierarchy rolling-window parity (W1 semantics on the hierarchy path).

RED: `detect_hierarchy`/`_detect_hierarchy_impl` accept no
`window_start`/`window_end` — the keyword args below raise TypeError = RED.

Contracts pinned here:
  - window [window_start, window_end] filters the graph BEFORE hierarchy
    detection at every resolution — identical semantics to W1's
    detect_communities (`_build_graph`: nodes created <= window_end; edges
    whose validity interval overlaps the window; NULL bi-temporal fields
    always pass).
  - the window is recorded in `hierarchy.metadata` ("window_start" /
    "window_end" ISO strings when present) plus graph_nodes/graph_edges
    counts; absent when no window is given.
  - no window = legacy behavior (unfiltered graph), verified by a control:
    the same DB produces identical node/edge counts with no window and a
    full-range window.
  - lineage (W2 max-overlap parent links) still resolves on windowed graphs;
    store_results=True persists parents, store_results=False keeps it
    in-memory with zero DB rows.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.graphrag.community_detection import (
    Community,
    CommunityDetectionService,
    CommunityHierarchy,
    DetectionResult,
)
from core.models import GraphCommunity, GraphEdge, GraphNode

UTC = timezone.utc


def _utc(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


def _one_level_result(nodes, level: int) -> DetectionResult:
    """DetectionResult with a single community containing every node."""
    c = Community(id=f"c_{level}", level=level, nodes=set(nodes))
    c.__post_init__()
    return DetectionResult(
        communities=[c],
        num_communities=1,
        modularity=0.5,
        coverage=1.0,
    )


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


class _CaptureDetect:
    """leiden.detect spy: records the graph handed in, returns per-level
    communities (one community per call containing the full node set)."""

    def __init__(self, extra_levels: int = 0):
        self.calls = 0
        self.graphs: list = []
        self.extra_levels = extra_levels

    def detect(self, graph, resolution):
        self.calls += 1
        self.graphs.append(graph)
        return _one_level_result(graph.nodes(), self.calls - 1)


class TestHierarchyWindowParity:
    def _seed(self, db):
        _seed_node(db, "A", created_at=_utc(2026, 1, 1))
        _seed_node(db, "B", created_at=_utc(2026, 1, 1))
        _seed_node(db, "C", created_at=_utc(2026, 7, 1))
        _seed_edge(db, "e-ab", "A", "B", _utc(2026, 1, 1))
        _seed_edge(db, "e-bc", "B", "C", _utc(2026, 7, 1))
        db.commit()

    def test_window_end_filters_graph_before_detection(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        spy = _CaptureDetect()
        with patch.object(svc.leiden, "detect", side_effect=spy.detect):
            svc.detect_hierarchy(
                "ws-1", session=db, store_results=False,
                window_start=_utc(2026, 4, 1), window_end=_utc(2026, 6, 1),
            )
        assert spy.graphs, "leiden.detect must be called"
        # the graph every resolution ran on excluded C + e-bc
        for g in spy.graphs:
            assert g.number_of_nodes() == 2  # A, B
            assert g.number_of_edges() == 1  # e-ab

    def test_window_start_excludes_invalidated_edges(self, db):
        self._seed(db)
        _seed_edge(db, "e-ac", "A", "C", _utc(2026, 1, 1), _utc(2026, 5, 1))
        db.commit()
        svc = CommunityDetectionService()
        spy = _CaptureDetect()
        with patch.object(svc.leiden, "detect", side_effect=spy.detect):
            svc.detect_hierarchy(
                "ws-1", session=db, store_results=False,
                window_start=_utc(2026, 6, 1), window_end=_utc(2026, 12, 31),
            )
        assert spy.graphs[0].number_of_edges() == 2  # e-ac invalidated before start

    def test_hierarchy_metadata_records_window(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        spy = _CaptureDetect()
        with patch.object(svc.leiden, "detect", side_effect=spy.detect):
            hierarchy = svc.detect_hierarchy(
                "ws-1", session=db, store_results=False,
                window_start=_utc(2026, 4, 1), window_end=_utc(2026, 8, 1),
            )
        assert hierarchy.metadata["window_start"] == _utc(2026, 4, 1).isoformat()
        assert hierarchy.metadata["window_end"] == _utc(2026, 8, 1).isoformat()
        assert hierarchy.metadata["graph_nodes"] == 3  # A, B (Jan) + C (Jul)
        assert hierarchy.metadata["graph_edges"] == 2

    def test_no_window_is_legacy_no_metadata(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        spy = _CaptureDetect()
        with patch.object(svc.leiden, "detect", side_effect=spy.detect):
            hierarchy = svc.detect_hierarchy("ws-1", session=db, store_results=False)
        assert "window_start" not in hierarchy.metadata
        assert "window_end" not in hierarchy.metadata
        assert spy.graphs[0].number_of_nodes() == 3
        assert spy.graphs[0].number_of_edges() == 2

    def test_full_window_matches_legacy_counts(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        legacy = _CaptureDetect()
        windowed = _CaptureDetect()
        with patch.object(svc.leiden, "detect", side_effect=legacy.detect):
            svc.detect_hierarchy("ws-1", session=db, store_results=False)
        with patch.object(svc.leiden, "detect", side_effect=windowed.detect):
            svc.detect_hierarchy(
                "ws-1", session=db, store_results=False,
                window_start=_utc(2026, 1, 1), window_end=_utc(2026, 12, 31),
            )
        for g_l, g_w in zip(legacy.graphs, windowed.graphs):
            assert g_w.number_of_nodes() == g_l.number_of_nodes()
            assert g_w.number_of_edges() == g_l.number_of_edges()


class _TwoLevelDetect:
    """leiden.detect spy: level 0 = one community with all graph nodes;
    levels 1+ = {A} and {B} (max_hierarchy_depth default is 3, so the split
    repeats — that is intentional; each level's communities carry their own
    level so memberships never collide in the persisted path)."""

    def __init__(self):
        self.calls = 0

    def detect(self, graph, resolution):
        level = self.calls
        self.calls += 1
        if level == 0:
            return _one_level_result(graph.nodes(), 0)
        ca = Community(id=f"comm_a_l{level}", level=level, nodes={"A"})
        cb = Community(id=f"comm_b_l{level}", level=level, nodes={"B"})
        ca.__post_init__()
        cb.__post_init__()
        return DetectionResult(
            communities=[ca, cb], num_communities=2, modularity=0.5, coverage=1.0,
        )


class TestHierarchyWindowLineage:
    def _seed(self, db):
        _seed_node(db, "A", created_at=_utc(2026, 1, 1))
        _seed_node(db, "B", created_at=_utc(2026, 1, 1))
        _seed_node(db, "C", created_at=_utc(2026, 7, 1))
        _seed_edge(db, "e-ab", "A", "B", _utc(2026, 1, 1))
        _seed_edge(db, "e-ac", "A", "C", _utc(2026, 7, 1))
        db.commit()

    def _assert_lineage(self, hierarchy):
        """Window [Apr, Jun] excludes C (created Jul): level-0 community holds
        {A, B}; level-1 {A}/{B} children parent to it; deeper levels parent
        into the level right above. ``comm_``-prefixed ids are per-level
        counters, so the persisted layer mints fresh UUIDs per (id, level)."""
        assert hierarchy.max_depth == 3
        level0 = {c.id: c for c in hierarchy.levels[0]}
        assert set(level0["c_0"].nodes) == {"A", "B"}  # C outside window
        level1_children = {}
        for c in hierarchy.levels[1]:
            assert c.parent_community == "c_0", f"{c.id} must parent to c_0"
            level1_children[c.id] = c.nodes
        assert level1_children["comm_a_l1"] == {"A"}
        assert level1_children["comm_b_l1"] == {"B"}
        for c in hierarchy.levels[2]:
            assert c.parent_community in ("comm_a_l1", "comm_b_l1")

    @staticmethod
    def _detect_side_effect():
        return _TwoLevelDetect().detect

    def test_parent_lineage_resolves_within_windowed_graph(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        with patch.object(svc.leiden, "detect", side_effect=self._detect_side_effect()):
            hierarchy = svc.detect_hierarchy(
                "ws-1", session=db, store_results=False,
                window_start=_utc(2026, 4, 1), window_end=_utc(2026, 6, 1),
            )
        self._assert_lineage(hierarchy)

    def test_store_true_persists_lineage_with_window(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        with patch.object(svc.leiden, "detect", side_effect=self._detect_side_effect()):
            hierarchy = svc.detect_hierarchy(
                "ws-1", session=db, store_results=True,
                window_start=_utc(2026, 4, 1), window_end=_utc(2026, 6, 1),
            )
        self._assert_lineage(hierarchy)
        rows = db.query(GraphCommunity).filter(GraphCommunity.workspace_id == "ws-1").all()
        # 3 levels: 1 + 2 + 2 communities (C excluded from level 0)
        assert len(rows) == 5
        ids = {r.id for r in rows}
        level0 = next(r for r in rows if r.level == 0)
        assert level0.id in ids
        for ch in [r for r in rows if r.level == 1]:
            assert ch.parent_community_id == level0.id

    def test_store_false_writes_nothing(self, db):
        self._seed(db)
        svc = CommunityDetectionService()
        with patch.object(svc.leiden, "detect", side_effect=self._detect_side_effect()):
            svc.detect_hierarchy(
                "ws-1", session=db, store_results=False,
                window_start=_utc(2026, 4, 1), window_end=_utc(2026, 6, 1),
            )
        assert db.query(GraphCommunity).filter(
            GraphCommunity.workspace_id == "ws-1"
        ).count() == 0