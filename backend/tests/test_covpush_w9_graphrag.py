# -*- coding: utf-8 -*-
"""Coverage wave 9 — GraphRAG expansion + community detection.

Pushes core/graphrag/multi_hop_expansion.py (44% -> ~95%) and
core/graphrag/community_detection.py (36% -> ~95%) to high coverage with an
expression-evaluating fake session (no DB, no network).

BUGS FIXED (TDD, RED -> GREEN):
1. multi_hop `max_total_nodes` soft cap: the cap check ``break`` only exited
   the inner neighbor loop — the outer node loop AND the hop loop kept
   expanding, so the limit was exceeded by up to a full extra hop.
2. `ExpansionPath.add_hop` built a fresh default `ExpansionConfig()` for the
   decay factor, ignoring the expander's actual config (dead method, broken).
3. `_calculate_activation_score` read "confidence" from the NEIGHBOR NODE's
   properties while the docstring promised edge properties — edge confidence
   (the natural carrier, GraphEdge.weight/properties) never influenced the
   activation score.
"""

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

from core.graphrag.community_detection import (
    ClusteringAlgorithm,
    Community,
    CommunityConfig,
    CommunityDetectionService,
    CommunityHierarchy,
    DetectionResult,
    LeidenAlgorithm,
    ResolutionPolicy,
    get_community_detector,
    get_leiden_algorithm,
)
from core.models import GraphNode, GraphEdge, GraphCommunity, CommunityMembership

from core.graphrag.multi_hop_expansion import (
    ActivationCue,
    ExpansionConfig,
    ExpansionNode,
    ExpansionPath,
    ExpansionResult,
    ExpansionStrategy,
    MultiHopExpander,
    SQLMultiHopExpander,
    TraversalConstraint,
    get_multi_hop_expander,
    get_sql_expander,
)

NETWORKX_AVAILABLE = True


# ============================================================================
# Fake session: evaluates SQLAlchemy BinaryExpression / BooleanClauseList
# filters against in-memory rows.
# ============================================================================

def _bound_value(expr):
    v = getattr(expr.right, "effective_value", None)
    if v is None:
        v = getattr(expr.right, "value", None)
    return v


def _matches(expr, row):
    """Evaluate a filter expression against a row object."""
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
        self._seq = 0
        self._fail_commit = False
        self._fail_add = False
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
        if getattr(self, "_fail_add", False):
            raise RuntimeError("add boom")

    def commit(self):
        if getattr(self, "_fail_commit", False):
            raise RuntimeError("commit boom")

    def rollback(self):
        self.rolled_back = True

    def execute(self, stmt, params=None):
        return self


# ============================================================================
# Helpers
# ============================================================================

def node(nid, name=None, ntype="user", props=None, ws="ws-1"):
    return SimpleNamespace(
        id=nid, name=name or nid, type=ntype,
        properties=props or {}, workspace_id=ws,
    )


def edge(src, tgt, rel="related_to", ws="ws-1", props=None):
    return SimpleNamespace(
        source_node_id=src, target_node_id=tgt, relationship_type=rel,
        workspace_id=ws, properties=props or {},
    )


def chain_graph(ws="ws-1"):
    n1 = node("n1", ws=ws)
    n2 = node("n2", ws=ws)
    n3 = node("n3", ws=ws)
    n4 = node("n4", ws=ws)
    return {
        "nodes": [n1, n2, n3, n4],
        "edges": [
            edge("n1", "n2", ws=ws),
            edge("n2", "n3", ws=ws),
            edge("n3", "n4", ws=ws),
        ],
    }


# ============================================================================
# multi_hop_expansion
# ============================================================================

class TestExpansionDataclasses:
    def test_expansion_node_eq_hash(self):
        a = ExpansionNode(id="x", name="x", entity_type="t")
        b = ExpansionNode(id="x", name="x", entity_type="t")
        c = ExpansionNode(id="y", name="y", entity_type="t")
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert a in {b}

    def test_expansion_path_add_hop_applies_given_decay(self):
        path = ExpansionPath()
        node_x = ExpansionNode(id="x", name="x", entity_type="t",
                               relevance_score=0.8, confidence=0.9)
        path.add_hop(node_x, "related_to", decay=0.5)
        assert path.nodes == [node_x]
        assert path.relationships == ["related_to"]
        assert path.total_relevance == pytest.approx(0.8 * 0.5)
        assert path.confidence == pytest.approx(0.9)

    def test_expansion_path_add_hop_default_decay(self):
        path = ExpansionPath()
        node_x = ExpansionNode(id="x", name="x", entity_type="t",
                               relevance_score=0.8, confidence=0.9)
        path.add_hop(node_x, "related_to")
        from core.graphrag.multi_hop_expansion import ExpansionConfig as EC
        assert path.total_relevance == pytest.approx(0.8 * EC().relevance_decay)


class TestMultiHopExpander:
    def _expander(self, **over):
        cfg = ExpansionConfig(
            max_hop_depth=over.get("max_hop_depth", 4),
            max_nodes_per_hop=over.get("max_nodes_per_hop", 50),
            max_total_nodes=over.get("max_total_nodes", 200),
            min_relevance_score=over.get("min_relevance", 0.3),
            relevance_decay=over.get("decay", 0.85),
            enable_early_termination=over.get("early_term", True),
        )
        return MultiHopExpander(cfg)

    def test_expand_start_node_missing_returns_empty(self):
        sess = FakeSession({GraphNode: [node("n2"), node("n3")],
                            GraphEdge: []})
        result = self._expander().expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 0
        assert result.max_depth_reached == 0
        assert result.metadata == {}

    def test_expand_start_node_in_other_workspace_not_found(self):
        sess = FakeSession({GraphNode: [node("n1", ws="ws-2")], GraphEdge: []})
        result = self._expander().expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 0

    def test_expand_chain_finds_all_nodes_and_paths(self):
        g = chain_graph()
        sess = FakeSession({
            GraphNode: [n for n in g["nodes"]],
            GraphEdge: g["edges"],
        })
        result = self._expander().expand("n1", "ws-1", session=sess)
        ids = {n.id for n in result.nodes}
        assert ids == {"n1", "n2", "n3", "n4"}
        assert result.max_depth_reached == 3
        assert result.total_nodes_found == 4
        assert len(result.relationships) == 3
        # Each path grows by one node per hop.
        assert {len(p.nodes) for p in result.paths} == {2, 3, 4}
        assert result.metadata["visited_count"] == 4
        assert result.metadata["workspace_id"] == "ws-1"
        assert "completed_at" in result.metadata

    def test_max_total_nodes_cap_is_hard(self):
        """BUG 1: the cap used to `break` only the inner loop — the outer
        node/hop loops kept expanding, exceeding the limit by a full hop."""
        g = chain_graph()
        sess = FakeSession({
            GraphNode: [n for n in g["nodes"]],
            GraphEdge: g["edges"],
        })
        result = self._expander(max_total_nodes=3).expand("n1", "ws-1", session=sess)
        # start + n2 + n3 = 3, then STOP (n4 must NOT be added)
        assert len(result.nodes) == 3
        assert {n.id for n in result.nodes} == {"n1", "n2", "n3"}

    def test_visited_nodes_not_re_expanded(self):
        # n1 -> n2 and n2 -> n1 (cycle); n2 -> n3
        sess = FakeSession({
            GraphNode: [node("n1"), node("n2"),
                        node("n3")],
            GraphEdge: [edge("n1", "n2"), edge("n2", "n1"),
                        edge("n2", "n3")],
        })
        result = self._expander().expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 3

    def test_low_relevance_neighbors_pruned(self):
        n1 = node("n1")
        n2 = node("n2", ntype="user")
        n3 = node("n3", ntype="formula")
        sess = FakeSession({
            GraphNode: [n1, n2, n3],
            GraphEdge: [edge("n1", "n2"), edge("n1", "n3", rel="similar_to")],
        })
        # min_relevance 0.9: hop-1 relevance for both is ~0.7-0.76 -> pruned
        result = self._expander(min_relevance=0.9).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 1
        assert result.nodes[0].id == "n1"

    def test_early_termination_when_avg_relevance_drops(self):
        # All neighbors get pruned by relevance -> next_level empty at hop 1
        n1 = node("n1")
        n2 = node("n2", ntype="ticket")
        sess = FakeSession({
            GraphNode: [n1, n2],
            GraphEdge: [edge("n1", "n2", rel="references")],
        })
        result = self._expander(min_relevance=0.99).expand("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 1

    def test_early_termination_disabled(self):
        g = chain_graph()
        sess = FakeSession({
            GraphNode: [n for n in g["nodes"]],
            GraphEdge: g["edges"],
        })
        result = self._expander(early_term=False, max_hop_depth=1).expand(
            "n1", "ws-1", session=sess)
        assert {n.id for n in result.nodes} == {"n1", "n2"}

    def test_expand_without_session_uses_db_context(self):
        g = chain_graph()
        sess = FakeSession({
            GraphNode: [n for n in g["nodes"]],
            GraphEdge: g["edges"],
        })
        with patch("core.graphrag.multi_hop_expansion.get_db_session",
                   return_value=sess):
            result = self._expander().expand("n1", "ws-1")
        assert result.total_nodes_found == 4

    def test_get_neighbors_activation_sort_and_cap(self):
        n1 = node("n1")
        n2 = node("n2", ntype="user")
        n3 = node("n3", ntype="ticket")
        n4 = node("n4", ntype="workspace")
        sess = FakeSession({
            GraphNode: [n1, n2, n3, n4],
            GraphEdge: [edge("n1", "n2", rel="belongs_to"),
                      edge("n1", "n3", rel="depends_on"),
                      edge("n4", "n1", rel="related_to")],
        })
        expander = self._expander(max_nodes_per_hop=2)
        start = ExpansionNode(id="n1", name="n1", entity_type="user")
        neighbors = expander._get_neighbors_with_cues(start, "ws-1", sess, None)
        assert len(neighbors) == 2  # capped
        assert neighbors[0][2] >= neighbors[1][2]  # sorted desc

    def test_neighbors_skip_missing_nodes_and_default_rel(self):
        # edge referencing a node not in the workspace -> skipped
        n1 = node("n1")
        n2 = node("n2", ws="ws-2")
        sess = FakeSession({
            GraphNode: [n1, n2],
            GraphEdge: [edge("n1", "n2", rel=None)],
        })
        start = ExpansionNode(id="n1", name="n1", entity_type="user")
        neighbors = self._expander()._get_neighbors_with_cues(start, "ws-1", sess, None)
        assert neighbors == []

    def test_calculate_activation_score_edge_confidence_wins(self):
        """BUG 3: confidence was read from the neighbor NODE's properties;
        the edge's confidence (the natural carrier) was ignored."""
        expander = self._expander()
        from_node = ExpansionNode(id="n1", name="n1", entity_type="user")
        to_node = node("n2", ntype="user", props={"confidence": 1.0})

        score_with_edge = expander._calculate_activation_score(
            from_node, to_node, "related_to", "outgoing",
            edge_properties={"confidence": 0.2})
        score_without_edge = expander._calculate_activation_score(
            from_node, to_node, "related_to", "outgoing", None)

        # base = 0.5 + 0.8*0.3 + 1.0*0.2 + 0.1 = 1.04
        assert score_without_edge == pytest.approx(min(1.04 * 1.0, 1.0))
        assert score_with_edge == pytest.approx(min(1.04 * 0.2, 1.0))
        assert score_with_edge < score_without_edge

    def test_calculate_hop_relevance_decays_with_depth(self):
        expander = self._expander(decay=0.5)
        from_node = ExpansionNode(id="n1", name="n1", entity_type="user")
        to_node = node("n2", ntype="user")
        r1 = expander._calculate_hop_relevance(from_node, to_node, "related_to", 1, None)
        r3 = expander._calculate_hop_relevance(from_node, to_node, "related_to", 3, None)
        assert r1 == pytest.approx(0.5 * 0.9 * 1.0)
        assert r3 == pytest.approx(0.125 * 0.9 * 1.0)
        assert r3 < r1


class TestSQLMultiHopExpander:
    def test_expand_sql_with_session(self):
        sess = FakeSession()
        sess.rows = [
            SimpleNamespace(id="n1", name="n1", type="user", hop_level=0,
                            relevance_score=1.0, properties={"k": "v"}),
            SimpleNamespace(id="n2", name="n2", type="user", hop_level=1,
                            relevance_score=0.7, properties=None),
        ]
        rel_rows = [
            SimpleNamespace(source_node_id="n1", target_node_id="n2",
                            relationship_type="related_to", properties={"w": 1}),
        ]
        sess.fetchall_results = [sess.rows, rel_rows]

        orig_execute = sess.execute

        def execute(stmt, params=None):
            nonlocal call_count
            call_count += 1
            return SimpleNamespace(fetchall=lambda: sess.fetchall_results[call_count - 1])

        call_count = 0
        sess.execute = execute

        result = SQLMultiHopExpander().expand_sql("n1", "ws-1", max_depth=2, session=sess)
        assert result.total_nodes_found == 2
        assert result.max_depth_reached == 1
        assert len(result.relationships) == 1
        assert result.strategy_used == ExpansionStrategy.BFS

    def test_expand_sql_exception_records_metadata_error(self):
        sess = FakeSession()

        def boom(stmt, params=None):
            raise RuntimeError("cte exploded")

        sess.execute = boom
        result = SQLMultiHopExpander().expand_sql("n1", "ws-1", session=sess)
        assert result.total_nodes_found == 0
        assert result.metadata["error"] == "expansion_failed"

    def test_expand_sql_without_session_uses_db_context(self):
        sess = FakeSession()

        def execute(stmt, params=None):
            return SimpleNamespace(fetchall=lambda: [])

        sess.execute = execute
        with patch("core.graphrag.multi_hop_expansion.get_db_session",
                   return_value=sess):
            result = SQLMultiHopExpander().expand_sql("n1", "ws-1")
        assert result.total_nodes_found == 0

    def test_default_config_used_when_none(self):
        assert SQLMultiHopExpander().config.max_hop_depth == 4
        assert MultiHopExpander().config.max_hop_depth == 4


class TestEnumsAndFactories:
    def test_strategies_and_cues_values(self):
        assert ExpansionStrategy.BFS.value == "bfs"
        assert ExpansionStrategy.DFS.value == "dfs"
        assert ExpansionStrategy.BIDIRECTIONAL.value == "bidirectional"
        assert ExpansionStrategy.ADAPTIVE.value == "adaptive"
        assert ActivationCue.RELATIONSHIP_TYPE.value == "relationship_type"
        assert ActivationCue.ENTITY_TYPE.value == "entity_type"
        assert ActivationCue.CONFIDENCE_THRESHOLD.value == "confidence"
        assert ActivationCue.TEMPORAL_RELEVANCE.value == "temporal"
        assert TraversalConstraint.MAX_HOPS.value == "max_hops"
        assert TraversalConstraint.MAX_NODES.value == "max_nodes"
        assert TraversalConstraint.MAX_TIME_MS.value == "max_time_ms"
        assert TraversalConstraint.RELEVANCE_THRESHOLD.value == "relevance_threshold"

    def test_factories(self):
        assert isinstance(get_multi_hop_expander(), MultiHopExpander)
        assert isinstance(get_sql_expander(), SQLMultiHopExpander)
        assert isinstance(get_multi_hop_expander(ExpansionConfig()),
                          MultiHopExpander)


# ============================================================================
# community_detection
# ============================================================================

def detection_graph(ws="ws-1", n=6):
    """n nodes in a dense-ish cluster + 1 isolated node."""
    nodes = [node(f"n{i}", ws=ws) for i in range(1, n + 1)]
    isolated = node("isolated", ws=ws, ntype="ticket")
    edges = [edge(f"n{i}", f"n{i + 1}", rel="depends_on", ws=ws) for i in range(1, n)]
    edges += [edge(f"n1", f"n3", ws=ws), edge("n2", f"n4", ws=ws)]
    return nodes + [isolated], edges


class TestCommunityDataclasses:
    def test_community_post_init_computes_size(self):
        c = Community(id="c1", nodes={"a", "b", "c"})
        assert c.size == 3
        # explicit size is overwritten by the nodes-derived value
        c2 = Community(id="c2", nodes={"a", "b"}, size=99)
        assert c2.size == 2

    def test_detection_result_defaults(self):
        r = DetectionResult()
        assert r.communities == []
        assert r.hierarchy is None
        assert r.num_communities == 0
        assert r.algorithm_used.value == ClusteringAlgorithm.LEIDEN.value


class TestLeidenAlgorithm:
    def test_detect_falls_back_to_louvain_when_leidenalg_missing(self):
        # igraph/leidenalg are NOT installed in this venv -> _detect_with_networkx
        # raises ImportError -> Louvain fallback runs.
        import networkx as nx

        g = nx.Graph()
        g.add_nodes_from(["a", "b", "c", "d", "e"])
        g.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("a", "c")])
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=2))
        result = algo.detect(g, resolution=1.0)
        assert result.algorithm_used.value == ClusteringAlgorithm.LOUVAIN.value
        assert result.num_communities >= 1
        assert result.execution_time_ms >= 0.0

    def test_detect_with_networkx_leiden_path(self):
        # Simulate leidenalg+igraph being installed: _detect_with_networkx
        # returns a partitioned result directly.
        import networkx as nx

        class FakePartition:
            membership = [0, 0, 0, 1, 1, 1]
            q = 0.42

        class FakeGraph:
            vs = [{"name": n} for n in ["a", "b", "c", "d", "e", "f"]]

            def add_vertices(self, names):
                self.vertices = names

            def add_edges(self, pairs):
                self.edges_list = pairs

        class FakeLeidenAlg:
            @staticmethod
            def find_partition(g, cls, **kw):
                assert kw["resolution_parameter"] == 1.0
                assert kw["n_iterations"] == -1
                return FakePartition()

            ModularityVertexPartition = object

        fake_mod = SimpleNamespace(
            find_partition=FakeLeidenAlg.find_partition,
            ModularityVertexPartition=object,
        )
        fake_igraph_mod = SimpleNamespace(Graph=lambda: FakeGraph())
        real_ig = sys.modules.get("igraph")
        real_leiden = sys.modules.get("leidenalg")
        sys.modules["leidenalg"] = fake_mod
        sys.modules["igraph"] = fake_igraph_mod
        try:
            algo = LeidenAlgorithm(CommunityConfig(min_community_size=2))
            g = nx.Graph()
            g.add_nodes_from(["a", "b", "c", "d", "e", "f"])
            result = algo._detect_with_networkx(g, 1.0)
            assert result.algorithm_used.value == ClusteringAlgorithm.LEIDEN.value
            assert result.num_communities == 2
            assert result.modularity == 0.42
        finally:
            if real_ig is not None:
                sys.modules["igraph"] = real_ig
            else:
                sys.modules.pop("igraph", None)
            if real_leiden is not None:
                sys.modules["leidenalg"] = real_leiden
            else:
                sys.modules.pop("leidenalg", None)

    def test_nx_to_igraph(self):
        import networkx as nx

        class FakeIGraph:
            def __init__(self):
                self.vertices = []
                self.edges_list = []
                self.es = {}

            def add_vertices(self, names):
                self.vertices = names

            def add_edges(self, pairs):
                self.edges_list = pairs

        g = nx.Graph()
        g.add_nodes_from(["a", "b"])
        g.add_edge("a", "b", weight=0.7)
        fake_igraph_mod = SimpleNamespace(Graph=FakeIGraph)
        real_ig = sys.modules.get("igraph")
        sys.modules["igraph"] = fake_igraph_mod
        try:
            ig = LeidenAlgorithm()._nx_to_igraph(g)
            assert ig.vertices == ["a", "b"]
            assert ig.edges_list == [("a", "b")]
            assert ig.es["weight"] == [0.7]
        finally:
            if real_ig is not None:
                sys.modules["igraph"] = real_ig
            else:
                sys.modules.pop("igraph", None)

    def test_detect_simple_with_networkx(self):
        import networkx as nx

        g = nx.Graph()
        g.add_edges_from([("a", "b"), ("b", "c"), ("d", "e")])
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=2))
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", True):
            result = algo._detect_simple(g, 1.0)
        assert result.algorithm_used.value == ClusteringAlgorithm.LABEL_PROPAGATION.value
        assert result.num_communities == 2

    def test_detect_simple_without_networkx(self):
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=2))
        graph = SimpleNamespace(nodes=lambda: ["a", "b", "c"])
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", False):
            result = algo._detect_simple(graph, 1.0)
        assert result.num_communities == 1

    def test_detect_simple_min_size_filters(self):
        import networkx as nx

        g = nx.Graph()
        g.add_edges_from([("a", "b"), ("c", "d")])
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=3))
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", True):
            result = algo._detect_simple(g, 1.0)
        assert result.num_communities == 0

    def test_louvain_min_size_filters(self):
        import networkx as nx

        g = nx.Graph()
        g.add_edges_from([("a", "b"), ("c", "d")])
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=5))
        result = algo._detect_with_nx_louvain(g, 1.0)
        assert result.num_communities == 0

    def test_partition_to_result(self):
        class FakePartition:
            membership = [0, 0, 1, 1, 1]
            q = 0.3

        graph = SimpleNamespace(vs=[{"name": "a"}, {"name": "b"}, {"name": "c"},
                                    {"name": "d"}, {"name": "e"}])
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=2))
        result = algo._partition_to_result(FakePartition(), graph, 1.0)
        assert result.num_communities == 2
        assert result.algorithm_used.value == ClusteringAlgorithm.LEIDEN.value
        assert result.modularity == 0.3

    def test_partition_to_result_min_size_filters(self):
        class FakePartition:
            membership = [0, 1, 2]
            q = 0.1

        graph = SimpleNamespace(vs=[{"name": "a"}, {"name": "b"}, {"name": "c"}])
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=2))
        result = algo._partition_to_result(FakePartition(), graph, 1.0)
        assert result.num_communities == 0


class TestCommunityDetectionService:
    def _service(self, **over):
        cfg = CommunityConfig(
            min_community_size=over.get("min_size", 3),
            max_community_size=over.get("max_size", 100),
            resolution_policy=over.get("policy", ResolutionPolicy.ADAPTIVE),
            enable_hierarchy=over.get("hierarchy", True),
            max_hierarchy_depth=over.get("h_depth", 3),
            base_resolution=over.get("base_res", 1.0),
        )
        return CommunityDetectionService(cfg)

    def _sess(self, ws="ws-1"):
        nodes, edges = detection_graph(ws=ws)
        return FakeSession({
            GraphNode: nodes,
            GraphEdge: edges,
        })

    def test_detect_communities_store_true(self):
        sess = self._sess()
        result = self._service().detect_communities("ws-1", session=sess, store_results=True)
        assert result.num_communities >= 1
        assert result.coverage > 0.0
        assert result.metadata["workspace_id"] == "ws-1"
        assert result.metadata["graph_nodes"] == 7
        # communities persisted
        added_communities = [o for o in sess.added
                             if o.__class__.__name__ == "GraphCommunity"]
        assert len(added_communities) == result.num_communities

    def test_detect_communities_store_false(self):
        sess = self._sess()
        result = self._service().detect_communities("ws-1", session=sess, store_results=False)
        assert result.num_communities >= 1
        assert sess.added == []

    def test_graph_too_small_early_return(self):
        sess = FakeSession({GraphNode: [node("a"), node("b")], GraphEdge: []})
        result = self._service().detect_communities("ws-1", session=sess)
        assert result.num_communities == 0
        assert result.metadata["reason"] == "graph_too_small"

    def test_detect_without_session_uses_db_context(self):
        sess = self._sess()
        with patch("core.graphrag.community_detection.get_db_session",
                   return_value=sess):
            result = self._service().detect_communities("ws-1")
        assert result.num_communities >= 1

    def test_get_resolution_fixed(self):
        svc = self._service(policy=ResolutionPolicy.FIXED, base_res=1.5)
        import networkx as nx
        g = nx.Graph()
        g.add_nodes_from(["a", "b", "c"])
        assert svc._get_resolution("ws-1", FakeSession({}), g) == 1.5

    def test_get_resolution_adaptive_dense_graph(self):
        svc = self._service(policy=ResolutionPolicy.ADAPTIVE)
        import networkx as nx
        g = nx.Graph()
        g.add_nodes_from(["a", "b", "c", "d"])
        g.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"),
                          ("a", "c"), ("b", "d")])
        r = svc._get_resolution("ws-1", FakeSession({}), g)
        # density 6/6 = 1 -> base*(1+1) = 2.0 clamped to max 2.0
        assert r == pytest.approx(2.0)

    def test_get_resolution_adaptive_empty_graph(self):
        svc = self._service(policy=ResolutionPolicy.ADAPTIVE)
        import networkx as nx
        g = nx.Graph()
        assert svc._get_resolution("ws-1", FakeSession({}), g) == 1.0

    def test_get_resolution_hierarchical(self):
        svc = self._service(policy=ResolutionPolicy.HIERARCHICAL, base_res=0.8)
        import networkx as nx
        g = nx.Graph()
        g.add_nodes_from(["a", "b"])
        assert svc._get_resolution("ws-1", FakeSession({}), g) == 0.8

    def test_build_graph_weights_from_edge_properties(self):
        import networkx as nx
        sess = FakeSession({
            GraphNode: [node("a"), node("b")],
            GraphEdge: [edge("a", "b", props={"weight": 0.5})],
        })
        g = self._service()._build_graph("ws-1", sess)
        assert g["a"]["b"]["weight"] == 0.5
        assert g["a"]["b"]["relationship_type"] == "related_to"
        assert g.nodes["a"]["name"] == "a"

    def test_enrich_communities(self):
        import networkx as nx
        nodes, edges = detection_graph()
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        result = self._service(min_size=2).detect_communities(
            "ws-1", session=sess, store_results=False)
        assert all(c.name for c in result.communities)
        assert all(c.keywords for c in result.communities)
        assert all(c.description for c in result.communities)

    def test_store_communities_replaces_previous(self):
        nodes, edges = detection_graph()
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        svc = self._service(min_size=2)
        svc.detect_communities("ws-1", session=sess, store_results=True)
        first_count = len(sess.added)
        svc.detect_communities("ws-1", session=sess, store_results=True)
        # second run: old GraphCommunity + memberships deleted, new ones added
        assert len(sess.added) > first_count

    def test_store_communities_rolls_back_on_failure(self):
        nodes, edges = detection_graph()
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        result = self._service(min_size=2).detect_communities(
            "ws-1", session=sess, store_results=False)
        sess._fail_commit = True
        # no exception escapes; rollback is recorded
        svc = self._service(min_size=2)
        svc._store_communities(result, "ws-1", sess)
        assert getattr(sess, "rolled_back", False) is True

    def test_detect_hierarchy(self):
        nodes, edges = detection_graph()
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        hierarchy = self._service().detect_hierarchy("ws-1", session=sess)
        assert hierarchy.max_depth == 3
        assert len(hierarchy.levels) == 3
        assert hierarchy.root_communities == hierarchy.levels[0]

    def test_detect_hierarchy_disabled(self):
        sess = self._sess()
        hierarchy = self._service(hierarchy=False).detect_hierarchy("ws-1", session=sess)
        assert hierarchy.max_depth == 0
        assert hierarchy.levels == {}

    def test_detect_hierarchy_without_session(self):
        sess = self._sess()
        with patch("core.graphrag.community_detection.get_db_session",
                   return_value=sess):
            hierarchy = self._service().detect_hierarchy("ws-1")
        assert hierarchy.max_depth == 3

    def test_factories(self):
        # Compare by class NAME, not identity — w77b's importlib.reload of
        # community_detection mints new class objects with the same names,
        # so isinstance against a pre-reload reference fails in batch runs.
        assert get_community_detector().__class__.__name__ == "CommunityDetectionService"
        assert get_leiden_algorithm().__class__.__name__ == "LeidenAlgorithm"
        assert get_community_detector(CommunityConfig()).__class__.__name__ == "CommunityDetectionService"


class TestCommunityDetectionRemainingGaps:
    def test_detect_uses_simple_fallback_when_networkx_unavailable(self):
        """detect() routes to _detect_simple when NETWORKX_AVAILABLE is False."""
        import networkx as nx

        g = nx.Graph()
        g.add_nodes_from(["a", "b", "c"])
        g.add_edge("a", "b")
        algo = LeidenAlgorithm(CommunityConfig(min_community_size=2))
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", False):
            result = algo.detect(g, 1.0)
        assert result.algorithm_used.value == ClusteringAlgorithm.LABEL_PROPAGATION.value

    def test_build_graph_raises_without_networkx(self):
        sess = FakeSession({GraphNode: [node("a")], GraphEdge: []})
        with patch("core.graphrag.community_detection.NETWORKX_AVAILABLE", False):
            with pytest.raises(ImportError, match="NetworkX required"):
                CommunityDetectionService()._build_graph("ws-1", sess)

    def test_get_resolution_unknown_policy_falls_back_to_base(self):
        svc = CommunityDetectionService(CommunityConfig())
        import networkx as nx

        g = nx.Graph()
        g.add_nodes_from(["a", "b", "c"])
        svc.config.resolution_policy = "unknown_policy"  # type: ignore[assignment]
        assert svc._get_resolution("ws-1", FakeSession({}), g) == 1.0

    def test_store_communities_cleans_previous_memberships(self):
        """Pre-existing GraphCommunity rows -> their CommunityMembership rows
        are deleted before the new communities are stored."""
        import uuid

        class Row:
            def __init__(self, **kw):
                self.__dict__.update(kw)

            def __getitem__(self, k):
                if k == 0:
                    return self.id
                if isinstance(k, str):
                    return self.__dict__[k]
                raise KeyError(k)

        nodes, edges = detection_graph()
        old_comm_id = str(uuid.uuid4())
        sess = FakeSession({
            GraphNode: nodes,
            GraphEdge: edges,
            GraphCommunity: [Row(id=old_comm_id, workspace_id="ws-1",
                                 level=0, summary="old", keywords=["k"])],
            CommunityMembership: [Row(community_id=old_comm_id,
                                      node_id="n1")],
        })
        svc = CommunityDetectionService(CommunityConfig(min_community_size=2))
        result = svc.detect_communities("ws-1", session=sess, store_results=False)
        svc._store_communities(result, "ws-1", sess)
        # old community + membership purged; new memberships added
        assert sess.rows_for(GraphCommunity) == []
        assert sess.rows_for(CommunityMembership) == []
        assert len(sess.added) >= result.num_communities

    def test_store_communities_keeps_custom_community_id(self):
        nodes, edges = detection_graph()
        sess = FakeSession({GraphNode: nodes, GraphEdge: edges})
        result = DetectionResult(communities=[
            Community(id="custom-1", nodes={"n1", "n2"}, size=2)
        ])
        svc = CommunityDetectionService(CommunityConfig(min_community_size=1))
        svc._store_communities(result, "ws-1", sess)
        comms = [o for o in sess.added if o.__class__.__name__ == "GraphCommunity"]
        assert comms[0].id == "custom-1"
        assert comms[0].summary == "community"
        memberships = [o for o in sess.added
                       if o.__class__.__name__ == "CommunityMembership"]
        assert len(memberships) == 2

    def test_module_reload_networkx_missing_sets_fallback_flags(self):
        """Module-level import fallbacks (NETWORKX_AVAILABLE/IGRAPH_AVAILABLE)
        when networkx cannot be imported."""
        import importlib
        import core.graphrag.community_detection as cd

        real_nx = sys.modules.get("networkx")
        try:
            sys.modules["networkx"] = None  # type: ignore[assignment]
            importlib.reload(cd)
            assert cd.NETWORKX_AVAILABLE is False
            assert cd.IGRAPH_AVAILABLE is False
        finally:
            if real_nx is not None:
                sys.modules["networkx"] = real_nx
            importlib.reload(cd)
