"""Temporal Evolution W2: community hierarchy lineage (parent/child nesting).

RED tests for the W2 contract:
- detect_hierarchy persists every level into ``graph_communities`` with the new
  ``parent_community_id`` column (replace-wipe per workspace, same semantics as
  the flat ``_store_communities`` path).
- Parents are chosen for child communities by MAXIMAL node overlap with the
  previous level (containment heuristic — partitions at different resolutions
  are not guaranteed nested).
- In-memory ``Community.parent_community`` / ``child_communities`` populated on
  the hierarchy before persistence.
- Structural invariants: every stored level-0 row has no parent; every stored
  level-L row's parent either is NULL or references a community stored in the
  same pass (never a dangling id).

FakeSession mirrors tests/test_covpush_w9_graphrag.py::FakeSession (in-memory
filter evaluation); partitions are stubbed via a FakeLeiden so parent selection
is deterministic.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.graphrag.community_detection import (
    ClusteringAlgorithm,
    Community,
    CommunityConfig,
    CommunityDetectionService,
    CommunityHierarchy,
    DetectionResult,
    LeidenAlgorithm,
)
from core.models import CommunityMembership, GraphCommunity, GraphNode, GraphEdge


# ============================================================================
# Fake session (mirrors test_covpush_w9_graphrag.py — in-memory filter eval)
# ============================================================================

def _bound_value(expr):
    v = getattr(expr.right, "effective_value", None)
    if v is None:
        v = getattr(expr.right, "value", None)
    return v


def _matches(expr, row):
    from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

    if isinstance(expr, BooleanClauseList):
        return any(_matches(c, row) for c in expr.clauses)
    if isinstance(expr, BinaryExpression):
        left, right = expr.left, expr.right
        op_name = getattr(expr.operator, "__name__", "")
        if op_name == "in_op":
            vals = _bound_value(expr)
            return getattr(row, left.name, None) in (vals or [])
        if hasattr(left, "name"):
            left_val = getattr(row, left.name, None)
        else:
            left_val = _bound_value(expr)
        if hasattr(right, "name"):
            return left_val == getattr(row, right.name, None)
        return left_val == _bound_value(expr)
    return True


def _model_key(model):
    tablename = getattr(model, "__tablename__", None)
    if tablename:
        return tablename
    table = getattr(model, "table", None)
    if table is not None:
        return table.name
    return str(model)


class FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model

    def filter(self, *criteria):
        q = FakeQuery(self._session, self._model)
        q._criteria = list(criteria)
        return q

    def _rows(self):
        return self._session.rows_for(self._model)

    def all(self):
        return [r for r in self._rows() if self._applies(r)]

    def first(self):
        for r in self._rows():
            if self._applies(r):
                return r
        return None

    def delete(self, synchronize_session=False):
        remaining = [r for r in self._rows() if not self._applies(r)]
        self._session.replace_rows(self._model, remaining)
        return len(self._rows()) - len(remaining)

    def _applies(self, row):
        return all(_matches(c, row) for c in getattr(self, "_criteria", []))


class FakeSession:
    def __init__(self, model_rows=None):
        self._data = {}
        self.added = []
        for model, rows in (model_rows or {}).items():
            self._data[_model_key(model)] = list(rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def rows_for(self, model):
        return self._data.setdefault(_model_key(model), [])

    def replace_rows(self, model, rows):
        self._data[_model_key(model)] = rows

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if getattr(self, "_fail_commit", False):
            raise RuntimeError("commit boom")

    def rollback(self):
        self.rolled_back = True

    def execute(self, stmt, params=None):
        return self


def node(nid, ws="ws-1"):
    return type("N", (), {
        "id": nid, "name": nid, "type": "user",
        "properties": {}, "workspace_id": ws,
    })()


def edge(src, tgt, ws="ws-1", rel="related_to"):
    return type("E", (), {
        "source_node_id": src, "target_node_id": tgt,
        "relationship_type": rel, "workspace_id": ws, "properties": {},
    })()


def triangle_graph(ws="ws-1"):
    """6 nodes in one coherent component (a-b-c-d-e-f path + chords)."""
    return {
        "nodes": [node(f"n{i}", ws=ws) for i in range(1, 7)],
        "edges": [
            edge(f"n{i}", f"n{i + 1}", ws=ws) for i in range(1, 6)
        ] + [
            edge("n1", "n3", ws=ws), edge("n2", "n4", ws=ws),
            edge("n3", "n5", ws=ws), edge("n4", "n6", ws=ws),
        ],
    }


# ============================================================================
# Deterministic partition stub
# ============================================================================

class FakeLeiden:
    """Returns hand-built partitions per resolution (bypasses real detection).

    Partitions (mirror-image hierarchy so every level-2 child has exactly one
    max-overlap parent, incl. the 0.667-vs-0.333 tie-break on comm_l2_2):
      res 0.5  -> level 0: [{n1..n6}]
      res 1.25 -> level 1: [{n1,n2,n3}, {n4,n5,n6}]
      res 2.0  -> level 2: [{n1,n2}, {n3,n4,n5}, {n6}]
    """

    def detect(self, graph, resolution: float = 1.0) -> DetectionResult:
        parts = {
            0.5: (0, [{"n1", "n2", "n3", "n4", "n5", "n6"}]),
            1.25: (1, [{"n1", "n2", "n3"}, {"n4", "n5", "n6"}]),
            2.0: (2, [{"n1", "n2"}, {"n3", "n4", "n5"}, {"n6"}]),
        }
        level, subsets = parts.get(resolution, parts[0.5])
        communities = []
        for i, nodes in enumerate(subsets):
            # level-distinct ids ("comm_l1_0") — a bare level counter would
            # collide across levels ("comm_0" at L0/L1/L2) and make lineage
            # resolution ambiguous (ids are the in-memory parent reference).
            communities.append(
                Community(id=f"comm_l{level}_{i}", nodes=set(nodes)))
        return DetectionResult(communities=communities,
                               algorithm_used=ClusteringAlgorithm.LOUVAIN)


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getitem__(self, k):
        if k == 0:
            return self.id
        if isinstance(k, str):
            return self.__dict__[k]
        raise KeyError(k)


# ============================================================================
# Tests
# ============================================================================

class TestHierarchyPersistence:
    def _svc(self, **over):
        cfg = CommunityConfig(
            min_community_size=over.get("min_size", 1),
            max_hierarchy_depth=over.get("h_depth", 3),
            enable_hierarchy=over.get("hierarchy", True),
            min_resolution=0.5,
            max_resolution=2.0,
        )
        svc = CommunityDetectionService(cfg)
        svc.leiden = FakeLeiden()
        return svc

    def _sess(self, ws="ws-1"):
        g = triangle_graph(ws=ws)
        return FakeSession({GraphNode: g["nodes"], GraphEdge: g["edges"]})

    @staticmethod
    def _community_rows(sess):
        return [o for o in sess.added if o.__class__.__name__ == "GraphCommunity"]

    @staticmethod
    def _membership_rows(sess):
        return [o for o in sess.added if o.__class__.__name__ == "CommunityMembership"]

    @staticmethod
    def _nodes_by_community(sess):
        mapping = {}
        for m in TestHierarchyPersistence._membership_rows(sess):
            mapping.setdefault(m.community_id, set()).add(m.node_id)
        return mapping

    def test_detect_hierarchy_persists_all_levels_with_parents(self):
        sess = self._sess()
        hierarchy = self._svc().detect_hierarchy("ws-1", session=sess)

        rows = self._community_rows(sess)
        assert len(rows) == 6  # 1 + 2 + 3 communities
        assert {r.level for r in rows} == {0, 1, 2}

        memberships = self._nodes_by_community(sess)
        assert len(memberships) == 6
        assert set().union(*memberships.values()) == {f"n{i}" for i in range(1, 7)}

        # level 0: the single coarse community has NO parent
        root = rows_0 = [r for r in rows if r.level == 0]
        assert len(rows_0) == 1
        assert rows_0[0].parent_community_id is None
        # level 1 children nested under the root
        l1 = {r.id: r for r in rows if r.level == 1}
        by_nodes = {frozenset(v): cid for cid, v in memberships.items()}
        assert l1[by_nodes[frozenset({"n1", "n2", "n3"})]].parent_community_id == rows_0[0].id
        assert l1[by_nodes[frozenset({"n4", "n5", "n6"})]].parent_community_id == rows_0[0].id
        # level 2: {n1,n2} -> {n1,n2,n3}; {n3,n4,n5} -> {n4,n5,n6} (max overlap
        # 2/3 beats 1/3 — NOT first-match); {n6} -> {n4,n5,n6}
        l2 = {r.id: r for r in rows if r.level == 2}
        assert l2[by_nodes[frozenset({"n1", "n2"})]].parent_community_id == \
            l1[by_nodes[frozenset({"n1", "n2", "n3"})]].id
        assert l2[by_nodes[frozenset({"n3", "n4", "n5"})]].parent_community_id == \
            l1[by_nodes[frozenset({"n4", "n5", "n6"})]].id
        assert l2[by_nodes[frozenset({"n6"})]].parent_community_id == \
            l1[by_nodes[frozenset({"n4", "n5", "n6"})]].id
        # in-memory dataclass linkage mirrors persistence exactly
        assert hierarchy.levels[2][1].parent_community == \
            hierarchy.levels[1][1].id
        assert hierarchy.levels[1][1].child_communities == [
            hierarchy.levels[2][1].id, hierarchy.levels[2][2].id,
        ]

    def test_detect_hierarchy_store_false_keeps_in_memory_lineage_only(self):
        sess = self._sess()
        hierarchy = self._svc().detect_hierarchy(
            "ws-1", session=sess, store_results=False)
        assert sess.added == []
        assert hierarchy.max_depth == 3
        assert hierarchy.levels[2][1].parent_community == hierarchy.levels[1][1].id

    def test_detect_hierarchy_disabled_stores_nothing(self):
        sess = self._sess()
        hierarchy = self._svc(hierarchy=False).detect_hierarchy(
            "ws-1", session=sess)
        assert hierarchy.max_depth == 0
        assert hierarchy.levels == {}
        assert sess.added == []

    def test_detect_hierarchy_without_session_uses_db_context(self):
        sess = self._sess()
        with patch("core.graphrag.community_detection.get_db_session",
                   return_value=sess):
            hierarchy = self._svc().detect_hierarchy("ws-1")
        assert hierarchy.max_depth == 3
        assert len(self._community_rows(sess)) == 6

    def test_store_hierarchy_replaces_previous_run(self):
        sess = self._sess()
        svc = self._svc()
        svc.detect_hierarchy("ws-1", session=sess)
        first_count = len(self._community_rows(sess))
        svc.detect_hierarchy("ws-1", session=sess)
        # wipe purges old GraphCommunity rows + memberships; added accumulates
        assert sess.rows_for(GraphCommunity) == []
        # the SECOND pass added exactly 6 fresh communities (1 + 2 + 3)
        second_pass = self._community_rows(sess)[first_count:]
        assert len(second_pass) == 6
        assert {r.level for r in second_pass} == {0, 1, 2}
        # every parent reference in the second pass resolves to a sibling row
        ids = {r.id for r in second_pass}
        for r in second_pass:
            assert r.parent_community_id is None or r.parent_community_id in ids

    def test_hierarchy_store_rolls_back_on_commit_failure(self):
        sess = self._sess()
        sess._fail_commit = True
        self._svc().detect_hierarchy("ws-1", session=sess)
        assert getattr(sess, "rolled_back", False) is True

    def test_real_detection_path_stores_valid_lineage(self):
        """No stubs: real louvain path on the 6-node graph. Enforces the
        structural invariants that hold regardless of partition shape."""
        sess = FakeSession({GraphNode: triangle_graph()["nodes"],
                            GraphEdge: triangle_graph()["edges"]})
        svc = CommunityDetectionService(CommunityConfig(
            min_community_size=2, max_hierarchy_depth=3))
        hierarchy = svc.detect_hierarchy("ws-1", session=sess)
        assert hierarchy.max_depth >= 1
        rows = self._community_rows(sess)
        assert len(rows) >= 1
        ids = {r.id for r in rows}
        for r in rows:
            assert r.parent_community_id is None or r.parent_community_id in ids
        for level1_rows in hierarchy.levels.get(0, []):
            assert level1_rows.parent_community is None

    def test_graph_community_model_has_parent_column(self):
        assert hasattr(GraphCommunity, "parent_community_id")


class TestHierarchySingleLevel:
    def test_max_depth_one_stores_roots_without_parents(self):
        g = triangle_graph()
        sess = FakeSession({GraphNode: g["nodes"], GraphEdge: g["edges"]})
        svc = CommunityDetectionService(CommunityConfig(
            min_community_size=1, max_hierarchy_depth=1, min_resolution=0.5,
            max_resolution=2.0))
        svc.leiden = FakeLeiden()
        hierarchy = svc.detect_hierarchy("ws-1", session=sess)
        assert hierarchy.max_depth == 1
        rows = [o for o in sess.added if o.__class__.__name__ == "GraphCommunity"]
        assert len(rows) == 1
        assert rows[0].parent_community_id is None

    def test_empty_levels_are_persisted_safely(self):
        """A resolution producing no communities (min-size filter) must not
        crash storage or leave dangling parents."""

        class SparseLeiden(FakeLeiden):
            def detect(self, graph, resolution: float = 1.0) -> DetectionResult:
                if resolution > 1.0:
                    return DetectionResult(
                        communities=[],
                        algorithm_used=ClusteringAlgorithm.LOUVAIN,
                    )
                return super().detect(graph, resolution)

        g = triangle_graph()
        sess = FakeSession({GraphNode: g["nodes"], GraphEdge: g["edges"]})
        svc = CommunityDetectionService(CommunityConfig(
            min_community_size=1, max_hierarchy_depth=3, min_resolution=0.5,
            max_resolution=2.0))
        svc.leiden = SparseLeiden()
        hierarchy = svc.detect_hierarchy("ws-1", session=sess)
        assert hierarchy.max_depth == 3
        rows = [o for o in sess.added if o.__class__.__name__ == "GraphCommunity"]
        # only the level-0 community survived detection
        assert len(rows) == 1
        assert rows[0].parent_community_id is None