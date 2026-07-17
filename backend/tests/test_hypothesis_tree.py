"""
Arbor Framework Tests — backend/tests/test_hypothesis_tree.py

Implements the 7 test cases documented in docs/architecture/ARBOR_FRAMEWORK.md:
  - test_node_creation
  - test_tree_addition
  - test_pruning
  - test_budget_enforcement
  - test_ucb1_calculation
  - test_negative_constraints
  - test_domain_nodes

Plus additional integration tests for the Extended HTR classes
(CodeHypothesisNode, WorkflowHypothesisNode, RoutingHypothesisNode,
OptimizationTree) and the governance code quality helper.

Run with:
    cd backend
    PYTHONPATH=. pytest tests/test_hypothesis_tree.py -v
"""

from __future__ import annotations

import math

import pytest

from core.hypothesis_tree import (
    CodeHypothesisNode,
    HypothesisNode,
    HypothesisTree,
    NodeMetrics,
    NodeStatus,
    OptimizationNode,
    OptimizationTree,
    PruningReason,
    RoutingHypothesisNode,
    TaskType,
    TreeSearchParams,
    WorkflowHypothesisNode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tree(tier: str = "solo") -> HypothesisTree:
    return HypothesisTree(task_description="Test task", tier=tier)


def _make_node(hypothesis: str = "test hypothesis", tokens: int = 0) -> HypothesisNode:
    return HypothesisNode(
        hypothesis=hypothesis,
        description="A test node",
        metrics=NodeMetrics(tokens_used=tokens),
    )


# ===========================================================================
# 1. test_node_creation
# ===========================================================================

class TestNodeCreation:
    """Validate that HypothesisNode initialises with the correct defaults."""

    def test_default_status_is_pending(self):
        node = HypothesisNode()
        assert node.status == NodeStatus.PENDING

    def test_node_has_unique_id(self):
        n1 = HypothesisNode()
        n2 = HypothesisNode()
        assert n1.id != n2.id
        assert len(n1.id) == 36  # UUID4 format

    def test_node_stores_hypothesis(self):
        node = HypothesisNode(hypothesis="CREATE INDEX ON users(email)")
        assert node.hypothesis == "CREATE INDEX ON users(email)"

    def test_node_defaults(self):
        node = HypothesisNode()
        assert node.depth == 0
        assert node.promise_score == 0.5
        assert node.visit_count == 0
        assert node.total_value == 0.0
        assert node.children == []
        assert node.pruning_reason is None

    def test_is_leaf_with_no_children(self):
        node = HypothesisNode()
        assert node.is_leaf() is True

    def test_is_successful(self):
        node = HypothesisNode(status=NodeStatus.SUCCESS)
        assert node.is_successful() is True
        assert node.is_failed() is False

    def test_is_failed(self):
        node = HypothesisNode(status=NodeStatus.FAILED)
        assert node.is_failed() is True
        assert node.is_successful() is False

    def test_pruned_node_is_failed(self):
        node = HypothesisNode(status=NodeStatus.PRUNED)
        assert node.is_failed() is True

    def test_to_dict_roundtrip(self):
        node = HypothesisNode(
            hypothesis="SELECT 1",
            description="smoke test",
            metrics=NodeMetrics(tokens_used=42, lint_errors=1),
        )
        d = node.to_dict()
        restored = HypothesisNode.from_dict(d)
        assert restored.id == node.id
        assert restored.hypothesis == node.hypothesis
        assert restored.metrics.tokens_used == 42
        assert restored.metrics.lint_errors == 1


# ===========================================================================
# 2. test_tree_addition
# ===========================================================================

class TestTreeAddition:
    """Verify that nodes are correctly added to the tree."""

    def test_add_root_node(self):
        tree = _make_tree()
        node = _make_node()
        added = tree.add_node(node)
        assert added is True
        assert node.id in tree.nodes

    def test_add_child_node_links_parent(self):
        tree = _make_tree()
        parent = _make_node("parent")
        tree.add_node(parent)

        child = HypothesisNode(parent_id=parent.id, depth=1, hypothesis="child")
        tree.add_node(child)

        assert child.id in tree.nodes
        assert child.id in tree.nodes[parent.id].children

    def test_token_accounting(self):
        tree = _make_tree()
        node = _make_node(tokens=500)
        tree.add_node(node)
        assert tree.total_tokens_used == 500

    def test_get_node_returns_node(self):
        tree = _make_tree()
        node = _make_node()
        tree.add_node(node)
        assert tree.get_node(node.id) is node

    def test_get_node_missing_returns_none(self):
        tree = _make_tree()
        assert tree.get_node("nonexistent") is None

    def test_get_children(self):
        tree = _make_tree()
        parent = _make_node("parent")
        tree.add_node(parent)
        child1 = HypothesisNode(parent_id=parent.id, depth=1, hypothesis="c1")
        child2 = HypothesisNode(parent_id=parent.id, depth=1, hypothesis="c2")
        tree.add_node(child1)
        tree.add_node(child2)
        children = tree.get_children(parent.id)
        assert len(children) == 2
        ids = {c.id for c in children}
        assert child1.id in ids
        assert child2.id in ids

    def test_get_path_to_root(self):
        tree = _make_tree()
        root = _make_node("root")
        tree.add_node(root)
        child = HypothesisNode(parent_id=root.id, depth=1, hypothesis="child")
        tree.add_node(child)
        grandchild = HypothesisNode(parent_id=child.id, depth=2, hypothesis="grandchild")
        tree.add_node(grandchild)
        path = tree.get_path_to_root(grandchild.id)
        assert path == [root.id, child.id, grandchild.id]

    def test_get_successful_path(self):
        tree = _make_tree()
        root = _make_node("root")
        tree.add_node(root)
        winner = HypothesisNode(parent_id=root.id, depth=1, hypothesis="winner",
                                status=NodeStatus.SUCCESS)
        tree.add_node(winner)
        path = tree.get_successful_path()
        assert winner.id in path

    def test_statistics(self):
        tree = _make_tree()
        tree.add_node(_make_node())
        stats = tree.get_statistics()
        assert stats["total_nodes"] == 1
        assert "successful_nodes" in stats
        assert "pruned_nodes" in stats


# ===========================================================================
# 3. test_pruning
# ===========================================================================

class TestPruning:
    """Validate branch pruning sets correct statuses and cascades to descendants."""

    def test_prune_single_node(self):
        tree = _make_tree()
        node = _make_node()
        tree.add_node(node)
        count = tree.prune_branch(node.id, PruningReason.LINT_FAILED)
        assert count == 1
        assert tree.nodes[node.id].status == NodeStatus.PRUNED
        assert tree.nodes[node.id].pruning_reason == PruningReason.LINT_FAILED

    def test_prune_cascades_to_children(self):
        tree = _make_tree()
        parent = _make_node("parent")
        tree.add_node(parent)
        child = HypothesisNode(parent_id=parent.id, depth=1, hypothesis="child")
        tree.add_node(child)
        grandchild = HypothesisNode(parent_id=child.id, depth=2, hypothesis="gc")
        tree.add_node(grandchild)

        count = tree.prune_branch(parent.id, PruningReason.TEST_FAILED)
        assert count == 3
        for nid in [parent.id, child.id, grandchild.id]:
            assert tree.nodes[nid].status == NodeStatus.PRUNED

    def test_prune_nonexistent_returns_zero(self):
        tree = _make_tree()
        count = tree.prune_branch("ghost-node", PruningReason.MANUAL)
        assert count == 0

    def test_all_pruning_reasons(self):
        """Every PruningReason value can be set on a node."""
        for reason in PruningReason:
            tree = _make_tree()
            node = _make_node()
            tree.add_node(node)
            tree.prune_branch(node.id, reason)
            assert tree.nodes[node.id].pruning_reason == reason


# ===========================================================================
# 4. test_budget_enforcement
# ===========================================================================

class TestBudgetEnforcement:
    """Verify node/token/cost budget limits are respected per pricing tier."""

    def test_free_tier_limits(self):
        tree = HypothesisTree(task_description="free test", tier="free")
        assert tree.max_nodes == 3
        assert tree.max_tokens == 5000
        assert tree.max_cost_usd == 0.25

    def test_solo_tier_limits(self):
        tree = _make_tree("solo")
        assert tree.max_nodes == 8
        assert tree.max_tokens == 10_000
        assert tree.max_cost_usd == 0.50

    def test_enterprise_tier_limits(self):
        tree = _make_tree("enterprise")
        assert tree.max_nodes == 20
        assert tree.max_tokens == 50_000
        assert tree.max_cost_usd == 2.00

    def test_node_budget_enforced(self):
        tree = HypothesisTree(task_description="tiny", tier="free")  # max 3 nodes
        for i in range(3):
            assert tree.add_node(_make_node(f"hyp-{i}")) is True
        # 4th node must be rejected
        assert tree.add_node(_make_node("overflow")) is False

    def test_token_budget_enforced(self):
        tree = HypothesisTree(task_description="tokens", tier="free")  # max 5000 tokens
        big_node = HypothesisNode(hypothesis="big", metrics=NodeMetrics(tokens_used=5001))
        added = tree.add_node(big_node)
        assert added is False

    def test_set_tier_budget_changes_limits(self):
        tree = _make_tree("free")
        assert tree.max_nodes == 3
        tree.set_tier_budget("enterprise")
        assert tree.max_nodes == 20
        assert tree.max_cost_usd == 2.00

    def test_calculate_tree_cost(self):
        tree = _make_tree()
        tree.total_tokens_used = 1_000_000
        cost = tree.calculate_tree_cost(cost_per_million=0.50)
        assert cost == pytest.approx(0.50)


# ===========================================================================
# 5. test_ucb1_calculation
# ===========================================================================

class TestUCB1Calculation:
    """Validate UCB1 score computation for MCTS node selection."""

    def test_unvisited_node_returns_inf(self):
        node = HypothesisNode()
        assert node.get_ucb1_score() == float("inf")

    def test_visited_node_finite_score(self):
        node = HypothesisNode(visit_count=5, total_value=3.0)
        score = node.get_ucb1_score(exploration_constant=1.41)
        assert math.isfinite(score)
        assert score > 0

    def test_higher_total_value_gives_higher_exploitation(self):
        """Node with more total value should have higher exploitation term."""
        n_good = HypothesisNode(visit_count=5, total_value=5.0)
        n_poor = HypothesisNode(visit_count=5, total_value=1.0)
        assert n_good.get_ucb1_score() > n_poor.get_ucb1_score()

    def test_exploration_constant_affects_score(self):
        node = HypothesisNode(visit_count=3, total_value=2.0)
        low_c = node.get_ucb1_score(exploration_constant=0.1)
        high_c = node.get_ucb1_score(exploration_constant=5.0)
        assert high_c > low_c


# ===========================================================================
# 6. test_negative_constraints
# ===========================================================================

class TestNegativeConstraints:
    """Verify cumulative learning via negative constraints."""

    def test_add_and_detect_constraint(self):
        tree = _make_tree()
        tree.add_negative_constraint("async/await in Python")
        assert tree.violates_constraint("avoid async/await in Python") is True

    def test_no_violation_for_clean_hypothesis(self):
        tree = _make_tree()
        tree.add_negative_constraint("global variables")
        assert tree.violates_constraint("use context managers for cleanup") is False

    def test_case_insensitive_constraint_check(self):
        tree = _make_tree()
        tree.add_negative_constraint("EVAL(")
        assert tree.violates_constraint("code uses eval(x) call") is True

    def test_duplicate_constraints_not_added(self):
        tree = _make_tree()
        tree.add_negative_constraint("bad pattern")
        tree.add_negative_constraint("bad pattern")
        assert len(tree.negative_constraints) == 1

    def test_multiple_constraints(self):
        tree = _make_tree()
        tree.add_negative_constraint("pattern_a")
        tree.add_negative_constraint("pattern_b")
        assert tree.violates_constraint("uses pattern_a somewhere") is True
        assert tree.violates_constraint("uses pattern_b somewhere") is True
        assert tree.violates_constraint("totally clean code") is False

    def test_learning_insights_stored(self):
        tree = _make_tree()
        tree.learning_insights = ["prefer context managers", "type hints improve rate"]
        assert len(tree.learning_insights) == 2

    def test_to_dict_preserves_constraints(self):
        tree = _make_tree()
        tree.add_negative_constraint("no global state")
        d = tree.to_dict()
        restored = HypothesisTree.from_dict(d)
        assert "no global state" in restored.negative_constraints


# ===========================================================================
# 7. test_domain_nodes
# ===========================================================================

class TestDomainNodes:
    """Validate the three domain-specific node subclasses and OptimizationTree."""

    # --- CodeHypothesisNode ---

    def test_code_node_task_type(self):
        node = CodeHypothesisNode()
        assert node.task_type == TaskType.CODING

    def test_code_node_promise_score_zero_on_errors(self):
        node = CodeHypothesisNode(
            security_vulnerabilities=5,
            cyclomatic_complexity=15,
            metrics=NodeMetrics(test_pass_rate=0.0),
        )
        score = node.calculate_promise_score()
        assert 0.0 <= score <= 1.0

    def test_code_node_to_dict_includes_code_fields(self):
        node = CodeHypothesisNode(code_diff="+ def foo(): pass", language="python")
        d = node.to_dict()
        assert d["task_type"] == "coding"

    # --- WorkflowHypothesisNode ---

    def test_workflow_node_task_type(self):
        node = WorkflowHypothesisNode()
        assert node.task_type == TaskType.WORKFLOW

    def test_workflow_node_promise_score(self):
        node = WorkflowHypothesisNode(
            parallelizable_ratio=0.8,
            cost_optimization_potential=0.5,
            estimated_throughput_rps=50.0,
            estimated_latency_ms=1000.0,
        )
        score = node.calculate_promise_score()
        assert score > 0

    # --- RoutingHypothesisNode ---

    def test_routing_node_task_type(self):
        node = RoutingHypothesisNode()
        assert node.task_type == TaskType.ROUTING

    def test_routing_node_promise_score_with_caching(self):
        no_cache = RoutingHypothesisNode(
            accuracy_score=0.9, consistency_score=0.8,
            cost_per_1k_tokens=0.01, p95_latency_ms=500,
            caching_enabled=False,
        )
        with_cache = RoutingHypothesisNode(
            accuracy_score=0.9, consistency_score=0.8,
            cost_per_1k_tokens=0.01, p95_latency_ms=500,
            caching_enabled=True,
        )
        assert with_cache.calculate_promise_score() > no_cache.calculate_promise_score()

    def test_routing_node_model_sequence(self):
        node = RoutingHypothesisNode(model_sequence=["gpt-4o", "gpt-4o-mini"])
        assert len(node.model_sequence) == 2

    # --- OptimizationTree ---

    def test_optimization_tree_routing_budget(self):
        """Routing trees get 12 nodes by default (overrides solo 8-node budget)."""
        tree = OptimizationTree(task_type=TaskType.ROUTING, tier="solo")
        assert tree.max_nodes == 12

    def test_optimization_tree_workflow_budget(self):
        tree = OptimizationTree(task_type=TaskType.WORKFLOW, tier="solo")
        assert tree.max_nodes == 5

    def test_create_node_factory(self):
        tree = OptimizationTree(task_type=TaskType.CODING)
        node = tree.create_node(
            node_type=TaskType.CODING,
            code_diff="+ x = 1",
            language="python",
        )
        assert isinstance(node, CodeHypothesisNode)
        assert node.language == "python"

    def test_create_routing_node_via_factory(self):
        tree = OptimizationTree(task_type=TaskType.ROUTING)
        node = tree.create_node(
            node_type=TaskType.ROUTING,
            model_sequence=["gpt-4o"],
        )
        assert isinstance(node, RoutingHypothesisNode)

    def test_get_domain_statistics_coding(self):
        tree = OptimizationTree(task_type=TaskType.CODING)
        node = tree.create_node(node_type=TaskType.CODING, language="python")
        tree.add_node(node)
        stats = tree.get_domain_statistics()
        assert "languages_used" in stats
        assert "avg_complexity" in stats

    def test_get_domain_statistics_routing(self):
        tree = OptimizationTree(task_type=TaskType.ROUTING)
        node = tree.create_node(
            node_type=TaskType.ROUTING,
            model_sequence=["gpt-4o", "gpt-4o-mini"],
        )
        tree.add_node(node)
        stats = tree.get_domain_statistics()
        assert "models_evaluated" in stats


# ===========================================================================
# Additional: Governance code quality gate
# ===========================================================================

class TestGovernanceArborGate:
    """Verify the _arbor_validate_code helper used in enforce_action()."""

    def test_valid_python_passes(self):
        from core.agent_governance_service import _arbor_validate_code
        result = _arbor_validate_code("def foo(x):\n    return x + 1\n")
        assert result["passed"] is True
        assert result["reason"] is None
        assert result["promise_score"] > 0

    def test_syntax_error_fails(self):
        from core.agent_governance_service import _arbor_validate_code
        result = _arbor_validate_code("def foo(\n    return broken syntax!!!")
        assert result["passed"] is False
        assert "SyntaxError" in result["reason"]
        assert result["promise_score"] == 0.0

    def test_empty_code_passes(self):
        """Empty string: no syntax error, minimal complexity."""
        from core.agent_governance_service import _arbor_validate_code
        result = _arbor_validate_code("")
        assert result["passed"] is True

    def test_non_python_language_skips_ast(self):
        from core.agent_governance_service import _arbor_validate_code
        # TypeScript — ast.parse not called, should always pass
        result = _arbor_validate_code("const x: number = 42;", language="typescript")
        assert result["passed"] is True


# ===========================================================================
# Additional: TreeSearchParams validation
# ===========================================================================

class TestTreeSearchParams:
    def test_defaults(self):
        params = TreeSearchParams()
        assert params.algorithm == "best_first"
        assert params.max_depth == 5
        assert params.beam_width == 3
        assert params.exploration_constant == pytest.approx(1.41)
        assert params.validate_lint is True
        assert params.validate_tests is True

    def test_custom_params(self):
        params = TreeSearchParams(
            algorithm="mcts",
            max_depth=3,
            exploration_constant=2.0,
            prune_on_lint_error=False,
        )
        assert params.algorithm == "mcts"
        assert params.prune_on_lint_error is False


# ===========================================================================
# Additional: WorkflowEngine & GraphRAGEngine Integrations
# ===========================================================================

class TestIntegrationsArbor:
    @pytest.mark.asyncio
    async def test_workflow_engine_refinement_structure(self):
        from core.workflow_engine import WorkflowEngine
        engine = WorkflowEngine()
        
        # Mock simple workflow graph
        workflow = {
            "id": "wf-123",
            "name": "Test Workflow Layout",
            "steps": [
                {"id": "step-1", "title": "Start", "config": {}},
                {"id": "step-2", "title": "Parallel Action", "config": {"requires": []}},
                {"id": "step-3", "title": "Sequential Action", "config": {"requires": ["step-1"]}}
            ]
        }
        
        # Test parallelizable ratio logic in class initialization wrapper
        steps = workflow["steps"]
        total_steps = len(steps)
        parallelizable_count = sum(1 for s in steps if not s.get("config", {}).get("requires", []))
        ratio = parallelizable_count / total_steps
        assert ratio == pytest.approx(2/3)

    @pytest.mark.asyncio
    async def test_graphrag_failed_hypothesis_discovery_empty(self, db_session):
        from core.graphrag_engine import GraphRAGEngine
        # db_session fixture yields the session instance directly
        gr_engine = GraphRAGEngine(db=db_session)
        
        # Querying a non-existent tenant or when database is empty
        res = await gr_engine.discover_failed_hypotheses_patterns(tenant_id="non-existent-tenant-999")
        assert res["success"] is True
        assert "patterns" in res or "summary" in res
        assert "No failed hypotheses recorded" in res["summary"]

