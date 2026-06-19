"""
Tree Search Algorithms for Hypothesis Tree Refinement

Implements Best-First Search, MCTS, and Beam Search optimized for LLM token usage.
Provides pruning criteria and cost-aware search strategies.

Phase 2026-06-19: Initial implementation for atom-upstream integration.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor

from core.hypothesis_tree import (
    HypothesisTree,
    HypothesisNode,
    NodeStatus,
    PruningReason,
    TreeSearchParams,
    NodeMetrics,
)

logger = logging.getLogger(__name__)


class SearchAlgorithm(Enum):
    """Available search algorithms."""
    BEST_FIRST = "best_first"
    MCTS = "mcts"
    BEAM_SEARCH = "beam_search"
    BREADTH_FIRST = "breadth_first"
    DEPTH_FIRST = "depth_first"


@dataclass
class SearchResult:
    """Result of a tree search operation."""
    success: bool
    winning_path: List[str]
    winning_node: Optional[HypothesisNode]
    total_nodes_explored: int
    total_tokens_used: int
    total_cost_usd: float
    execution_time_ms: float
    pruning_events: List[Dict[str, Any]]
    search_metadata: Dict[str, Any]


class TreeValidator(ABC):
    """Abstract base class for hypothesis validation."""

    @abstractmethod
    async def validate_lint(self, hypothesis: str, file_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validate hypothesis for lint errors.

        Args:
            hypothesis: Code diff or content to validate
            file_path: Optional file path for context

        Returns:
            Tuple of (passed, output)
        """
        pass

    @abstractmethod
    async def validate_tests(self, hypothesis: str) -> Tuple[bool, Dict[str, bool]]:
        """
        Validate hypothesis against test suite.

        Args:
            hypothesis: Code diff or content to test

        Returns:
            Tuple of (all_passed, test_results)
        """
        pass

    @abstractmethod
    async def validate_performance(self, hypothesis: str) -> NodeMetrics:
        """
        Validate hypothesis performance characteristics.

        Args:
            hypothesis: Code diff or content to measure

        Returns:
            Performance metrics
        """
        pass


class DefaultValidator(TreeValidator):
    """Default validator implementation for testing."""

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode

    async def validate_lint(self, hypothesis: str, file_path: Optional[str] = None) -> Tuple[bool, str]:
        """Default lint validation - checks for common issues."""
        # Check for common anti-patterns
        issues = []

        if "TODO:" in hypothesis or "FIXME:" in hypothesis:
            issues.append("Contains TODO/FIXME markers")

        if "print(" in hypothesis and "logger" not in hypothesis:
            issues.append("Contains print statement instead of logger")

        if hypothesis.count("try:") != hypothesis.count("except:"):
            issues.append("Unbalanced try/except blocks")

        passed = len(issues) == 0
        output = "No issues" if passed else "; ".join(issues)

        return passed, output

    async def validate_tests(self, hypothesis: str) -> Tuple[bool, Dict[str, bool]]:
        """Default test validation - basic checks."""
        # Simulated test results
        test_results = {
            "syntax_check": True,
            "import_check": "import " in hypothesis or not any(hyp.startswith(kw) for kw in ["def ", "class ", "async def "]),
            "naming_convention": all(not k.startswith("_") or k.startswith("__") for k in ["_temp", "_cache"]),
        }

        all_passed = all(test_results.values())
        return all_passed, test_results

    async def validate_performance(self, hypothesis: str) -> NodeMetrics:
        """Default performance validation - estimate metrics."""
        return NodeMetrics(
            execution_time_ms=100.0,
            cpu_percent=5.0,
            memory_mb=50.0,
            tokens_used=len(hypothesis) // 4,  # Rough estimate
            lines_changed=hypothesis.count("\n"),
        )


class BaseTreeSearch(ABC):
    """Abstract base class for tree search algorithms."""

    def __init__(
        self,
        params: TreeSearchParams,
        validator: Optional[TreeValidator] = None,
    ):
        self.params = params
        self.validator = validator or DefaultValidator()
        self.pruning_events: List[Dict[str, Any]] = []

    @abstractmethod
    async def search(
        self,
        tree: HypothesisTree,
        hypothesis_generator: Callable[[HypothesisNode], List[str]],
    ) -> SearchResult:
        """
        Execute the search algorithm.

        Args:
            tree: Hypothesis tree to search
            hypothesis_generator: Function to generate child hypotheses from a node

        Returns:
            Search result with winning path and metrics
        """
        pass

    async def validate_node(
        self,
        node: HypothesisNode,
    ) -> HypothesisNode:
        """
        Validate a hypothesis node.

        Args:
            node: Node to validate

        Returns:
            Updated node with validation results
        """
        node.status = NodeStatus.EXPANDING

        # Run lint validation
        if self.params.validate_lint:
            lint_passed, lint_output = await self.validator.validate_lint(
                node.hypothesis,
                node.file_path
            )
            node.lint_output = lint_output

            if not lint_passed and self.params.prune_on_lint_error:
                node.status = NodeStatus.PRUNED
                node.pruning_reason = PruningReason.LINT_FAILED
                node.metrics.lint_errors += 1
                self._record_pruning(node, PruningReason.LINT_FAILED, lint_output)
                return node

        # Run test validation
        if self.params.validate_tests:
            test_passed, test_results = await self.validator.validate_tests(node.hypothesis)
            node.test_results = test_results

            if not test_passed and self.params.prune_on_test_failure:
                node.status = NodeStatus.PRUNED
                node.pruning_reason = PruningReason.TEST_FAILED
                self._record_pruning(node, PruningReason.TEST_FAILED, str(test_results))
                return node

            # Update test pass rate
            if test_results:
                passed_count = sum(1 for r in test_results.values() if r)
                node.metrics.test_pass_rate = passed_count / len(test_results)

        # Run performance validation
        if self.params.validate_performance:
            node.metrics = await self.validator.validate_performance(node.hypothesis)

            # Check latency regression
            if self.params.prune_on_latency_regression:
                if node.metrics.execution_time_ms > self.params.latency_threshold_ms:
                    node.status = NodeStatus.PRUNED
                    node.pruning_reason = PruningReason.LATENCY_REGRESSION
                    self._record_pruning(
                        node,
                        PruningReason.LATENCY_REGRESSION,
                        f"Latency {node.metrics.execution_time_ms}ms exceeds threshold {self.params.latency_threshold_ms}ms"
                    )
                    return node

        # All validations passed
        node.status = NodeStatus.SUCCESS
        return node

    def _record_pruning(self, node: HypothesisNode, reason: PruningReason, details: str):
        """Record a pruning event for analysis."""
        self.pruning_events.append({
            "node_id": node.id,
            "depth": node.depth,
            "reason": reason.value,
            "details": details,
            "hypothesis_preview": node.hypothesis[:100] if node.hypothesis else "",
        })

    def _check_constraints(self, hypothesis: str) -> bool:
        """Check if hypothesis violates negative constraints."""
        for constraint in self.params.negative_constraints:
            if constraint.lower() in hypothesis.lower():
                return True
        return False


class BestFirstSearch(BaseTreeSearch):
    """
    Best-First Search algorithm for hypothesis tree exploration.

    Prioritizes nodes with highest promise scores, expanding the most
    promising hypotheses first for efficient search.
    """

    def __init__(
        self,
        params: TreeSearchParams,
        validator: Optional[TreeValidator] = None,
    ):
        super().__init__(params, validator)
        self.max_depth = params.max_depth
        self.promise_threshold = params.promise_threshold

    async def search(
        self,
        tree: HypothesisTree,
        hypothesis_generator: Callable[[HypothesisNode], List[str]],
    ) -> SearchResult:
        """
        Execute Best-First Search.

        Args:
            tree: Hypothesis tree to search
            hypothesis_generator: Function to generate child hypotheses

        Returns:
            Search result with winning path
        """
        start_time = time.time()
        nodes_explored = 0
        tokens_used = 0
        cost_usd = 0.0

        # Priority queue: (promise_score, node_id)
        # Use negative for max-heap behavior
        priority_queue: List[Tuple[float, str]] = []

        # Initialize with root node
        if tree.root_id and tree.root_id in tree.nodes:
            root = tree.nodes[tree.root_id]
            priority_queue.append((root.promise_score, root.id))
        elif tree.nodes:
            # Use first node as root
            root_id = next(iter(tree.nodes))
            priority_queue.append((tree.nodes[root_id].promise_score, root_id))

        winning_node: Optional[HypothesisNode] = None
        winning_path: List[str] = []

        while priority_queue and nodes_explored < self.params.max_nodes:
            # Get highest promise node
            promise_score, node_id = priority_queue.pop(0)

            # Check if we've exceeded token budget
            if tokens_used > tree.max_tokens:
                logger.info(f"Token budget exceeded: {tokens_used} > {tree.max_tokens}")
                break

            node = tree.get_node(node_id)
            if not node or node.status != NodeStatus.PENDING:
                continue

            # Check depth limit
            if node.depth >= self.max_depth:
                continue

            nodes_explored += 1
            tree.total_nodes_expanded += 1

            # Validate the node
            if node.hypothesis:
                validated_node = await self.validate_node(node)
                tokens_used += validated_node.metrics.tokens_used

                if validated_node.is_successful():
                    winning_node = validated_node
                    winning_path = tree.get_path_to_root(node_id)
                    break
                elif validated_node.is_failed() and self.params.prune_on_test_failure:
                    tree.prune_branch(node_id, validated_node.pruning_reason)
                    continue

            # Generate child hypotheses
            try:
                new_hypotheses = hypothesis_generator(node)

                for hyp_text in new_hypotheses:
                    # Check constraints
                    if self._check_constraints(hyp_text):
                        self._record_pruning(node, PruningReason.NEGATIVE_CONSTRAINT, hyp_text[:50])
                        continue

                    # Create child node
                    child = HypothesisNode(
                        parent_id=node_id,
                        depth=node.depth + 1,
                        hypothesis=hyp_text,
                        description=f"Hypothesis from node {node_id}",
                    )

                    # Calculate promise score
                    child.promise_score = child.calculate_promise_score()

                    # Check threshold
                    if child.promise_score >= self.promise_threshold:
                        if tree.add_node(child):
                            node.children.append(child.id)
                            priority_queue.append((child.promise_score, child.id))

            except Exception as e:
                logger.error(f"Error generating hypotheses for node {node_id}: {e}")

        execution_time = (time.time() - start_time) * 1000

        # Update tree
        tree.winning_path = winning_path
        tree.total_tokens_used = tokens_used
        tree.total_cost_usd = tree.calculate_tree_cost()

        return SearchResult(
            success=winning_node is not None,
            winning_path=winning_path,
            winning_node=winning_node,
            total_nodes_explored=nodes_explored,
            total_tokens_used=tokens_used,
            total_cost_usd=tree.total_cost_usd,
            execution_time_ms=execution_time,
            pruning_events=self.pruning_events,
            search_metadata={
                "algorithm": "best_first",
                "max_depth": self.max_depth,
                "promise_threshold": self.promise_threshold,
            },
        )


class MCTSSearch(BaseTreeSearch):
    """
    Monte Carlo Tree Search for hypothesis tree exploration.

    Uses UCB1 (Upper Confidence Bound) to balance exploration and exploitation.
    Well-suited for large search spaces with uncertain outcomes.
    """

    def __init__(
        self,
        params: TreeSearchParams,
        validator: Optional[TreeValidator] = None,
    ):
        super().__init__(params, validator)
        self.exploration_constant = params.exploration_constant
        self.max_depth = params.max_depth

    async def search(
        self,
        tree: HypothesisTree,
        hypothesis_generator: Callable[[HypothesisNode], List[str]],
    ) -> SearchResult:
        """
        Execute MCTS search.

        Args:
            tree: Hypothesis tree to search
            hypothesis_generator: Function to generate child hypotheses

        Returns:
            Search result with winning path
        """
        start_time = time.time()
        iterations = 0
        max_iterations = self.params.max_nodes * 2  # MCTS needs more iterations
        tokens_used = 0

        winning_node: Optional[HypothesisNode] = None
        winning_path: List[str] = []

        while iterations < max_iterations and tokens_used < tree.max_tokens:
            # Selection: traverse tree using UCB1
            selected_path = self._select(tree)

            if not selected_path:
                break

            leaf_id = selected_path[-1]
            leaf_node = tree.get_node(leaf_id)

            if not leaf_node:
                break

            # Expansion: generate new hypotheses if leaf is promising
            if leaf_node.status == NodeStatus.PENDING and leaf_node.depth < self.max_depth:
                new_hypotheses = hypothesis_generator(leaf_node)

                for hyp_text in new_hypotheses[:3]:  # Limit expansion
                    child = HypothesisNode(
                        parent_id=leaf_id,
                        depth=leaf_node.depth + 1,
                        hypothesis=hyp_text,
                        description=f"MCTS hypothesis {iterations}",
                    )

                    if tree.add_node(child):
                        leaf_node.children.append(child.id)

            # Simulation: validate leaf node
            if leaf_node.hypothesis:
                validated = await self.validate_node(leaf_node)
                tokens_used += validated.metrics.tokens_used

                # Backpropagation: update values up the tree
                reward = 1.0 if validated.is_successful() else 0.0
                self._backpropagate(tree, selected_path, reward)

                if validated.is_successful():
                    winning_node = validated
                    winning_path = tree.get_path_to_root(leaf_id)

            iterations += 1
            tree.total_nodes_expanded += 1

        execution_time = (time.time() - start_time) * 1000

        # Update tree
        tree.winning_path = winning_path
        tree.total_tokens_used = tokens_used
        tree.total_cost_usd = tree.calculate_tree_cost()

        return SearchResult(
            success=winning_node is not None,
            winning_path=winning_path,
            winning_node=winning_node,
            total_nodes_explored=tree.total_nodes_expanded,
            total_tokens_used=tokens_used,
            total_cost_usd=tree.total_cost_usd,
            execution_time_ms=execution_time,
            pruning_events=self.pruning_events,
            search_metadata={
                "algorithm": "mcts",
                "iterations": iterations,
                "exploration_constant": self.exploration_constant,
            },
        )

    def _select(self, tree: HypothesisTree) -> List[str]:
        """
        Select a path using UCB1.

        Args:
            tree: Hypothesis tree

        Returns:
            List of node IDs from root to selected leaf
        """
        path = []
        current_id = tree.root_id

        if not current_id and tree.nodes:
            current_id = next(iter(tree.nodes))

        while current_id:
            path.append(current_id)
            node = tree.get_node(current_id)

            if not node or node.is_leaf() or node.status == NodeStatus.SUCCESS:
                break

            # Select child with highest UCB1
            best_child_id = None
            best_score = -float('inf')

            for child_id in node.children:
                child = tree.get_node(child_id)
                if child:
                    score = child.get_ucb1_score(self.exploration_constant)
                    if score > best_score:
                        best_score = score
                        best_child_id = child_id

            if best_child_id:
                current_id = best_child_id
            else:
                break

        return path

    def _backpropagate(self, tree: HypothesisTree, path: List[str], reward: float):
        """
        Backpropagate reward up the tree.

        Args:
            tree: Hypothesis tree
            path: Path from root to leaf
            reward: Reward to backpropagate
        """
        for node_id in path:
            node = tree.get_node(node_id)
            if node:
                node.visit_count += 1
                node.total_value += reward


class BeamSearch(BaseTreeSearch):
    """
    Beam Search for hypothesis tree exploration.

    Maintains a fixed-width beam of most promising nodes at each level.
    More memory-efficient than Best-First for large search spaces.
    """

    def __init__(
        self,
        params: TreeSearchParams,
        validator: Optional[TreeValidator] = None,
    ):
        super().__init__(params, validator)
        self.beam_width = params.beam_width
        self.max_depth = params.max_depth

    async def search(
        self,
        tree: HypothesisTree,
        hypothesis_generator: Callable[[HypothesisNode], List[str]],
    ) -> SearchResult:
        """
        Execute Beam Search.

        Args:
            tree: Hypothesis tree to search
            hypothesis_generator: Function to generate child hypotheses

        Returns:
            Search result with winning path
        """
        start_time = time.time()
        tokens_used = 0

        # Initialize beam with root
        current_beam: List[HypothesisNode] = []

        if tree.root_id and tree.root_id in tree.nodes:
            current_beam = [tree.nodes[tree.root_id]]
        elif tree.nodes:
            current_beam = [next(iter(tree.nodes.values()))]

        winning_node: Optional[HypothesisNode] = None
        winning_path: List[str] = []
        depth = 0

        while current_beam and depth < self.max_depth:
            next_beam: List[HypothesisNode] = []

            for node in current_beam:
                if tokens_used >= tree.max_tokens:
                    break

                # Validate node if not already validated
                if node.hypothesis and node.status == NodeStatus.PENDING:
                    validated = await self.validate_node(node)
                    tokens_used += validated.metrics.tokens_used

                    if validated.is_successful():
                        winning_node = validated
                        winning_path = tree.get_path_to_root(node.id)
                        break

                # Generate children
                hypotheses = hypothesis_generator(node)

                for hyp_text in hypotheses:
                    if self._check_constraints(hyp_text):
                        continue

                    child = HypothesisNode(
                        parent_id=node.id,
                        depth=node.depth + 1,
                        hypothesis=hyp_text,
                        description=f"Beam hypothesis depth {depth + 1}",
                    )

                    child.promise_score = child.calculate_promise_score()

                    if tree.add_node(child):
                        next_beam.append(child)
                        node.children.append(child.id)

                tree.total_nodes_expanded += 1

            if winning_node:
                break

            # Keep top-k nodes for next beam
            next_beam.sort(key=lambda n: n.promise_score, reverse=True)
            current_beam = next_beam[:self.beam_width]
            depth += 1

        execution_time = (time.time() - start_time) * 1000

        # Update tree
        tree.winning_path = winning_path
        tree.total_tokens_used = tokens_used
        tree.total_cost_usd = tree.calculate_tree_cost()

        return SearchResult(
            success=winning_node is not None,
            winning_path=winning_path,
            winning_node=winning_node,
            total_nodes_explored=tree.total_nodes_expanded,
            total_tokens_used=tokens_used,
            total_cost_usd=tree.total_cost_usd,
            execution_time_ms=execution_time,
            pruning_events=self.pruning_events,
            search_metadata={
                "algorithm": "beam_search",
                "beam_width": self.beam_width,
                "max_depth": self.max_depth,
            },
        )


def create_tree_search(
    algorithm: str = "best_first",
    params: Optional[TreeSearchParams] = None,
    validator: Optional[TreeValidator] = None,
) -> BaseTreeSearch:
    """
    Factory function to create tree search instances.

    Args:
        algorithm: Search algorithm to use
        params: Search parameters
        validator: Validator for hypothesis validation

    Returns:
        Tree search instance
    """
    if params is None:
        params = TreeSearchParams()

    algorithm_map = {
        SearchAlgorithm.BEST_FIRST.value: BestFirstSearch,
        SearchAlgorithm.MCTS.value: MCTSSearch,
        SearchAlgorithm.BEAM_SEARCH.value: BeamSearch,
    }

    search_class = algorithm_map.get(algorithm, BestFirstSearch)
    return search_class(params, validator)


async def search_with_refinement(
    task_description: str,
    hypothesis_generator: Callable[[HypothesisNode], List[str]],
    algorithm: str = "best_first",
    tier: str = "solo",
    complexity: str = "standard",
    validator: Optional[TreeValidator] = None,
) -> SearchResult:
    """
    High-level function for tree-based hypothesis refinement.

    Args:
        task_description: Description of the coding task
        hypothesis_generator: Function to generate hypotheses
        algorithm: Search algorithm to use
        tier: Pricing tier for budget limits
        complexity: Task complexity level
        validator: Optional custom validator

    Returns:
        Search result with winning hypothesis
    """
    # Create tree
    tree = HypothesisTree(
        task_description=task_description,
        complexity_level=complexity,
        tier=tier,
    )

    # Create root node
    root = HypothesisNode(
        hypothesis="// Initial solution",
        description=f"Root hypothesis for: {task_description}",
        depth=0,
    )

    tree.add_node(root)
    tree.root_id = root.id

    # Configure search parameters
    params = TreeSearchParams(
        algorithm=algorithm,
        max_nodes=tree.max_nodes,
        max_tokens=tree.max_tokens,
        max_cost_usd=tree.max_cost_usd,
    )

    # Create search instance
    search = create_tree_search(algorithm, params, validator)

    # Execute search
    return await search.search(tree, hypothesis_generator)
