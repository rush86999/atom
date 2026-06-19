"""
Hypothesis Tree Data Structures

Arbor-style optimization framework for LLM code generation with tree-based refinement.
Supports Hypothesis Tree Refinement (HTR) with cumulative learning across sessions.

Phase 2026-06-19: Initial implementation for atom-upstream integration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from functools import total_ordering


class NodeStatus(Enum):
    """Status of a hypothesis node in the search tree."""
    PENDING = "pending"
    EXPANDING = "expanding"
    SUCCESS = "success"
    FAILED = "failed"
    PRUNED = "pruned"


class PruningReason(Enum):
    """Reasons why a node was pruned from the search tree."""
    LINT_FAILED = "lint_failed"
    TEST_FAILED = "test_failed"
    LATENCY_REGRESSION = "latency_regression"
    RESOURCE_EXCEEDED = "resource_exceeded"
    NEGATIVE_CONSTRAINT = "negative_constraint"
    BUDGET_EXCEEDED = "budget_exceeded"
    DUPLICATE_HYPOTHESIS = "duplicate_hypothesis"
    LOW_PROMISE = "low_promise"
    MANUAL = "manual"


@total_ordering
@dataclass
class NodeMetrics:
    """Performance metrics for a hypothesis node."""
    execution_time_ms: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    tokens_used: int = 0
    test_pass_rate: float = 0.0
    lint_errors: int = 0
    lint_warnings: int = 0
    lines_changed: int = 0

    def __lt__(self, other: NodeMetrics) -> bool:
        """Compare metrics for ranking nodes."""
        # Prefer faster execution, lower resource usage, higher test pass rate
        return (
            self.execution_time_ms < other.execution_time_ms and
            self.test_pass_rate >= other.test_pass_rate and
            self.cpu_percent <= other.cpu_percent
        )


@dataclass
class HypothesisNode:
    """
    A node in the hypothesis tree representing a potential solution.

    Each node contains:
    - The hypothesis (code diff, configuration change, etc.)
    - Validation state (lint, tests, performance)
    - Parent/child references for tree structure
    - Metrics for cost/quality tradeoff analysis
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    depth: int = 0
    status: NodeStatus = NodeStatus.PENDING
    pruning_reason: Optional[PruningReason] = None

    # Hypothesis content
    hypothesis: str = ""  # Code diff or configuration change
    description: str = ""  # Human-readable description
    file_path: Optional[str] = None  # Affected file (for code changes)

    # Validation results
    lint_output: Optional[str] = None
    test_results: Optional[Dict[str, bool]] = None
    error_message: Optional[str] = None

    # Performance metrics
    metrics: NodeMetrics = field(default_factory=NodeMetrics)

    # Search optimization
    promise_score: float = 0.5  # 0.0 to 1.0, estimated potential
    visit_count: int = 0  # For MCTS
    total_value: float = 0.0  # For MCTS UCB1 calculation

    # Children node IDs
    children: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Cumulative learning linkage
    session_id: Optional[str] = None
    learning_tags: List[str] = field(default_factory=list)

    def is_leaf(self) -> bool:
        """Check if this is a leaf node (no children)."""
        return len(self.children) == 0

    def is_successful(self) -> bool:
        """Check if this node represents a successful solution."""
        return self.status == NodeStatus.SUCCESS

    def is_failed(self) -> bool:
        """Check if this node failed validation."""
        return self.status in (NodeStatus.FAILED, NodeStatus.PRUNED)

    def get_ucb1_score(self, exploration_constant: float = 1.41) -> float:
        """
        Calculate UCB1 score for MCTS node selection.

        UCB1 = average_reward + c * sqrt(ln(parent_visits) / visits)

        Args:
            exploration_constant: Controls exploration vs exploitation (default: sqrt(2))

        Returns:
            UCB1 score for node selection
        """
        if self.visit_count == 0:
            return float('inf')

        exploitation = self.total_value / self.visit_count
        exploration = exploration_constant * (2 * (self.visit_count + 1)) ** 0.5 / self.visit_count

        return exploitation + exploration

    def calculate_promise_score(
        self,
        metrics_weight: float = 0.4,
        tests_weight: float = 0.3,
        depth_penalty: float = 0.2,
        lint_penalty: float = 0.1
    ) -> float:
        """
        Calculate promise score for Best-First Search ranking.

        Args:
            metrics_weight: Weight for performance metrics
            tests_weight: Weight for test pass rate
            depth_penalty: Penalty for deeper nodes
            lint_penalty: Penalty for lint issues

        Returns:
            Promise score between 0.0 and 1.0
        """
        # Normalize metrics (lower is better for execution time)
        execution_score = max(0.0, 1.0 - min(self.metrics.execution_time_ms / 10000, 1.0))
        test_score = self.metrics.test_pass_rate

        # Apply depth penalty (deeper nodes are less promising)
        depth_factor = 1.0 / (1.0 + self.depth * 0.1)

        # Apply lint penalty
        lint_factor = 1.0 / (1.0 + self.metrics.lint_errors * lint_penalty)

        # Combine scores
        score = (
            (execution_score * metrics_weight) +
            (test_score * tests_weight)
        ) * depth_factor * lint_factor

        return max(0.0, min(1.0, score))

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary for serialization."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "status": self.status.value,
            "pruning_reason": self.pruning_reason.value if self.pruning_reason else None,
            "hypothesis": self.hypothesis,
            "description": self.description,
            "file_path": self.file_path,
            "lint_output": self.lint_output,
            "test_results": self.test_results,
            "error_message": self.error_message,
            "metrics": {
                "execution_time_ms": self.metrics.execution_time_ms,
                "cpu_percent": self.metrics.cpu_percent,
                "memory_mb": self.metrics.memory_mb,
                "tokens_used": self.metrics.tokens_used,
                "test_pass_rate": self.metrics.test_pass_rate,
                "lint_errors": self.metrics.lint_errors,
                "lint_warnings": self.metrics.lint_warnings,
                "lines_changed": self.metrics.lines_changed,
            },
            "promise_score": self.promise_score,
            "visit_count": self.visit_count,
            "total_value": self.total_value,
            "children": self.children,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "session_id": self.session_id,
            "learning_tags": self.learning_tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HypothesisNode:
        """Create node from dictionary."""
        metrics_data = data.get("metrics", {})
        metrics = NodeMetrics(
            execution_time_ms=metrics_data.get("execution_time_ms", 0.0),
            cpu_percent=metrics_data.get("cpu_percent", 0.0),
            memory_mb=metrics_data.get("memory_mb", 0.0),
            tokens_used=metrics_data.get("tokens_used", 0),
            test_pass_rate=metrics_data.get("test_pass_rate", 0.0),
            lint_errors=metrics_data.get("lint_errors", 0),
            lint_warnings=metrics_data.get("lint_warnings", 0),
            lines_changed=metrics_data.get("lines_changed", 0),
        )

        return cls(
            id=data["id"],
            parent_id=data.get("parent_id"),
            depth=data.get("depth", 0),
            status=NodeStatus(data.get("status", NodeStatus.PENDING.value)),
            pruning_reason=PruningReason(data["pruning_reason"]) if data.get("pruning_reason") else None,
            hypothesis=data.get("hypothesis", ""),
            description=data.get("description", ""),
            file_path=data.get("file_path"),
            lint_output=data.get("lint_output"),
            test_results=data.get("test_results"),
            error_message=data.get("error_message"),
            metrics=metrics,
            promise_score=data.get("promise_score", 0.5),
            visit_count=data.get("visit_count", 0),
            total_value=data.get("total_value", 0.0),
            children=data.get("children", []),
            session_id=data.get("session_id"),
            learning_tags=data.get("learning_tags", []),
        )


@dataclass
class HypothesisTree:
    """
    Tree structure for organizing and exploring hypothesis nodes.

    Features:
    - Root node representing the initial problem state
    - Hierarchical branching for solution space exploration
    - Path tracking for cumulative learning
    - Budget enforcement per pricing tier
    - Cumulative learning from previous sessions
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root_id: Optional[str] = None
    task_id: Optional[str] = None
    task_description: str = ""
    complexity_level: str = "standard"  # standard, high, critical

    # Nodes storage
    nodes: Dict[str, HypothesisNode] = field(default_factory=dict)

    # Search state
    winning_path: List[str] = field(default_factory=list)
    total_nodes_expanded: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0

    # Budget limits (per pricing tier)
    max_nodes: int = 8  # Default Solo tier
    max_tokens: int = 10000
    max_cost_usd: float = 0.50

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Cumulative learning
    session_id: Optional[str] = None
    learning_insights: List[str] = field(default_factory=list)
    negative_constraints: List[str] = field(default_factory=list)

    # Tier configuration
    tier: str = "solo"  # free, solo, enterprise

    def __post_init__(self):
        """Initialize tree with root node if needed."""
        if self.tier == "free":
            self.max_nodes = 3
            self.max_tokens = 5000
            self.max_cost_usd = 0.25
        elif self.tier == "enterprise":
            self.max_nodes = 20
            self.max_tokens = 50000
            self.max_cost_usd = 2.00

    def set_tier_budget(self, tier: str):
        """
        Set budget limits based on pricing tier.

        Args:
            tier: Pricing tier (free, solo, enterprise)
        """
        self.tier = tier
        tier_budgets = {
            "free": {"max_nodes": 3, "max_tokens": 5000, "max_cost": 0.25},
            "solo": {"max_nodes": 8, "max_tokens": 10000, "max_cost": 0.50},
            "enterprise": {"max_nodes": 20, "max_tokens": 50000, "max_cost": 2.00},
        }

        if tier in tier_budgets:
            budget = tier_budgets[tier]
            self.max_nodes = budget["max_nodes"]
            self.max_tokens = budget["max_tokens"]
            self.max_cost_usd = budget["max_cost"]

    def add_node(self, node: HypothesisNode) -> bool:
        """
        Add a node to the tree.

        Args:
            node: Node to add

        Returns:
            True if node was added, False if budget exceeded
        """
        # Check budget limits
        if len(self.nodes) >= self.max_nodes:
            return False

        if self.total_tokens_used + node.metrics.tokens_used > self.max_tokens:
            return False

        if self.total_cost_usd > self.max_cost_usd:
            return False

        # Add node
        self.nodes[node.id] = node
        self.total_tokens_used += node.metrics.tokens_used

        # Update parent's children list
        if node.parent_id and node.parent_id in self.nodes:
            self.nodes[node.parent_id].children.append(node.id)

        self.updated_at = datetime.utcnow()
        return True

    def get_node(self, node_id: str) -> Optional[HypothesisNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_children(self, node_id: str) -> List[HypothesisNode]:
        """Get all children of a node."""
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.nodes[child_id] for child_id in node.children if child_id in self.nodes]

    def get_path_to_root(self, node_id: str) -> List[str]:
        """
        Get the path from a node to the root.

        Args:
            node_id: Starting node ID

        Returns:
            List of node IDs from node to root (inclusive)
        """
        path = []
        current_id = node_id

        while current_id:
            path.append(current_id)
            node = self.get_node(current_id)
            if not node or not node.parent_id:
                break
            current_id = node.parent_id

        return list(reversed(path))

    def get_successful_path(self) -> List[str]:
        """
        Get the path from root to the first successful node.

        Returns:
            List of node IDs representing the winning path
        """
        for node_id, node in self.nodes.items():
            if node.is_successful():
                return self.get_path_to_root(node_id)
        return []

    def prune_branch(self, node_id: str, reason: PruningReason) -> int:
        """
        Prune a branch from the tree.

        Args:
            node_id: Root node of the branch to prune
            reason: Reason for pruning

        Returns:
            Number of nodes pruned
        """
        if node_id not in self.nodes:
            return 0

        count = 0
        to_prune = [node_id]

        while to_prune:
            current_id = to_prune.pop()
            node = self.get_node(current_id)

            if not node:
                continue

            # Mark as pruned
            node.status = NodeStatus.PRUNED
            node.pruning_reason = reason
            count += 1

            # Add children to prune list
            to_prune.extend(node.children)

        return count

    def add_negative_constraint(self, constraint: str):
        """Add a negative constraint learned from failed hypotheses."""
        if constraint not in self.negative_constraints:
            self.negative_constraints.append(constraint)

    def violates_constraint(self, hypothesis: str) -> bool:
        """
        Check if a hypothesis violates any negative constraints.

        Args:
            hypothesis: Hypothesis content to check

        Returns:
            True if hypothesis violates a constraint
        """
        for constraint in self.negative_constraints:
            if constraint.lower() in hypothesis.lower():
                return True
        return False

    def calculate_tree_cost(self, cost_per_million: float = 0.50) -> float:
        """
        Calculate total cost of tree exploration.

        Args:
            cost_per_million: Cost per million tokens

        Returns:
            Total cost in USD
        """
        return (self.total_tokens_used / 1_000_000) * cost_per_million

    def get_statistics(self) -> Dict[str, Any]:
        """Get tree statistics for monitoring."""
        successful_nodes = sum(1 for n in self.nodes.values() if n.is_successful())
        failed_nodes = sum(1 for n in self.nodes.values() if n.is_failed())
        pruned_nodes = sum(1 for n in self.nodes.values() if n.status == NodeStatus.PRUNED)

        # Calculate average depth
        depths = [n.depth for n in self.nodes.values()]
        avg_depth = sum(depths) / len(depths) if depths else 0

        return {
            "tree_id": self.id,
            "total_nodes": len(self.nodes),
            "total_nodes_expanded": self.total_nodes_expanded,
            "successful_nodes": successful_nodes,
            "failed_nodes": failed_nodes,
            "pruned_nodes": pruned_nodes,
            "pending_nodes": len(self.nodes) - successful_nodes - failed_nodes - pruned_nodes,
            "average_depth": avg_depth,
            "max_depth": max(depths) if depths else 0,
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": self.total_cost_usd,
            "winning_path_length": len(self.winning_path),
            "tier": self.tier,
            "complexity_level": self.complexity_level,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert tree to dictionary for serialization."""
        return {
            "id": self.id,
            "root_id": self.root_id,
            "task_id": self.task_id,
            "task_description": self.task_description,
            "complexity_level": self.complexity_level,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "winning_path": self.winning_path,
            "total_nodes_expanded": self.total_nodes_expanded,
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": self.total_cost_usd,
            "max_nodes": self.max_nodes,
            "max_tokens": self.max_tokens,
            "max_cost_usd": self.max_cost_usd,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "session_id": self.session_id,
            "learning_insights": self.learning_insights,
            "negative_constraints": self.negative_constraints,
            "tier": self.tier,
            "statistics": self.get_statistics(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HypothesisTree:
        """Create tree from dictionary."""
        tree = cls(
            id=data["id"],
            root_id=data.get("root_id"),
            task_id=data.get("task_id"),
            task_description=data.get("task_description", ""),
            complexity_level=data.get("complexity_level", "standard"),
            winning_path=data.get("winning_path", []),
            total_nodes_expanded=data.get("total_nodes_expanded", 0),
            total_tokens_used=data.get("total_tokens_used", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            session_id=data.get("session_id"),
            learning_insights=data.get("learning_insights", []),
            negative_constraints=data.get("negative_constraints", []),
            tier=data.get("tier", "solo"),
        )

        # Restore nodes
        for node_id, node_data in data.get("nodes", {}).items():
            tree.nodes[node_id] = HypothesisNode.from_dict(node_data)

        return tree


@dataclass
class TreeSearchParams:
    """Parameters for tree-based refinement search."""

    # Search algorithm
    algorithm: str = "best_first"  # best_first, mcts, beam_search

    # Budget limits (overrides tree defaults)
    max_nodes: Optional[int] = None
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    max_depth: int = 5

    # Search strategy
    beam_width: int = 3  # For beam search
    exploration_constant: float = 1.41  # For MCTS
    promise_threshold: float = 0.3  # Minimum promise score to expand

    # Validation strategy
    validate_lint: bool = True
    validate_tests: bool = True
    validate_performance: bool = True

    # Pruning criteria
    prune_on_lint_error: bool = True
    prune_on_test_failure: bool = True
    prune_on_latency_regression: bool = False
    latency_threshold_ms: float = 1000.0

    # Parallel execution
    parallel_validation: bool = True
    max_parallel_tasks: int = 4

    # Cumulative learning
    use_historical_insights: bool = True
    negative_constraints: List[str] = field(default_factory=list)

    # Telemetry
    track_metrics: bool = True
    export_tree: bool = True


# ============================================================================
# Extended HTR: Generic Optimization Node (Phase 2026-06-19 Extension)
# ============================================================================

class TaskType(Enum):
    """Types of tasks that can be optimized with HTR."""
    CODING = "coding"
    WORKFLOW = "workflow"
    ROUTING = "routing"


@dataclass
class OptimizationNode(HypothesisNode):
    """
    Generic base class for optimization nodes across different domains.

    Extends HypothesisNode with domain-agnostic optimization features:
    - Generic task type classification
    - Cost/quality tradeoff metrics
    - Execution budget tracking
    - Multi-objective scoring

    Subclasses: CodeHypothesisNode, WorkflowHypothesisNode, RoutingHypothesisNode
    """
    # Task type classification
    task_type: TaskType = TaskType.CODING

    # Multi-objective optimization scores
    quality_score: float = 0.0  # 0.0 to 1.0
    cost_score: float = 0.0  # Normalized cost (lower is better)
    latency_score: float = 0.0  # Normalized latency (lower is better)

    # Budget tracking
    budget_used: float = 0.0
    budget_remaining: float = 0.0

    # Domain-specific metadata (extensible by subclasses)
    domain_metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_multi_objective_score(
        self,
        quality_weight: float = 0.4,
        cost_weight: float = 0.3,
        latency_weight: float = 0.2,
        depth_penalty: float = 0.1
    ) -> float:
        """
        Calculate multi-objective score for node ranking.

        Args:
            quality_weight: Weight for quality score
            cost_weight: Weight for cost score (inverted)
            latency_weight: Weight for latency score (inverted)
            depth_penalty: Penalty for deeper nodes

        Returns:
            Combined score between 0.0 and 1.0
        """
        # Depth factor (deeper nodes are less promising)
        depth_factor = 1.0 / (1.0 + self.depth * 0.1)

        # Combine scores with weights
        score = (
            (self.quality_score * quality_weight) +
            ((1.0 - self.cost_score) * cost_weight) +
            ((1.0 - self.latency_score) * latency_weight)
        ) * depth_factor

        return max(0.0, min(1.0, score))

    def to_dict(self) -> Dict[str, Any]:
        """Convert optimization node to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            "task_type": self.task_type.value if isinstance(self.task_type, TaskType) else self.task_type,
            "quality_score": self.quality_score,
            "cost_score": self.cost_score,
            "latency_score": self.latency_score,
            "budget_used": self.budget_used,
            "budget_remaining": self.budget_remaining,
            "domain_metadata": self.domain_metadata,
        })
        return base_dict


@dataclass
class CodeHypothesisNode(OptimizationNode):
    """
    Hypothesis node for code generation tasks.

    Domain-specific metrics:
    - Code quality indicators (lint, test coverage)
    - Performance characteristics (execution time, resource usage)
    - Code complexity metrics (lines changed, cyclomatic complexity)
    """
    task_type: TaskType = TaskType.CODING

    # Code-specific metrics
    code_diff: str = ""  # Unified diff format
    language: str = ""  # python, typescript, rust, etc.
    cyclomatic_complexity: int = 0
    code_coverage: float = 0.0  # 0.0 to 1.0
    technical_debt_ratio: float = 0.0  # 0.0 to 1.0

    # Security metrics
    security_vulnerabilities: int = 0
    security_hotspots: int = 0

    def calculate_promise_score(self) -> float:
        """Calculate promise score for code hypotheses."""
        # Base promise from multi-objective score
        base_score = self.calculate_multi_objective_score(
            quality_weight=0.4,  # Test pass rate, coverage
            cost_weight=0.3,  # Token cost
            latency_weight=0.2,  # Execution time
            depth_penalty=0.1
        )

        # Apply code-specific penalties
        complexity_penalty = min(1.0, self.cyclomatic_complexity / 20.0)
        security_penalty = min(1.0, (self.security_vulnerabilities * 0.2) +
                                     (self.security_hotspots * 0.1))

        return base_score * (1.0 - complexity_penalty * 0.3) * (1.0 - security_penalty * 0.5)


@dataclass
class WorkflowHypothesisNode(OptimizationNode):
    """
    Hypothesis node for workflow orchestration optimization.

    Domain-specific metrics:
    - Step configuration and parallelization
    - Rate limit and API quota headroom
    - Caching opportunities
    - Execution latency and throughput
    """
    task_type: TaskType = TaskType.WORKFLOW

    # Workflow-specific configuration
    steps_configuration: Dict[str, Any] = field(default_factory=dict)
    parallel_steps: List[str] = field(default_factory=list)
    sequential_steps: List[str] = field(default_factory=list)

    # Performance metrics
    estimated_latency_ms: float = 0.0
    estimated_throughput_rps: float = 0.0  # Requests per second
    parallelizable_ratio: float = 0.0  # 0.0 to 1.0

    # Resource constraints
    rate_limit_headroom: float = 0.0  # Remaining API quota
    cache_hit_rate_improvement: float = 0.0
    cost_optimization_potential: float = 0.0  # 0.0 to 1.0

    def calculate_promise_score(self) -> float:
        """Calculate promise score for workflow hypotheses."""
        # Prioritize parallelization and cost savings
        parallelization_bonus = self.parallelizable_ratio * 0.3
        cost_savings_bonus = self.cost_optimization_potential * 0.2
        cache_bonus = self.cache_hit_rate_improvement * 0.1

        # Base quality from throughput and latency
        quality_score = (
            min(1.0, self.estimated_throughput_rps / 100.0) * 0.5 +
            max(0.0, 1.0 - (self.estimated_latency_ms / 10000.0)) * 0.5
        )

        return quality_score + parallelization_bonus + cost_savings_bonus + cache_bonus


@dataclass
class RoutingHypothesisNode(OptimizationNode):
    """
    Hypothesis node for LLM/model routing optimization.

    Domain-specific metrics:
    - Model selection and pipeline configuration
    - Quality vs cost tradeoffs
    - Latency characteristics
    - Token usage optimization
    """
    task_type: TaskType = TaskType.ROUTING

    # Routing-specific configuration
    model_sequence: List[str] = field(default_factory=list)
    fallback_enabled: bool = True
    caching_enabled: bool = False
    streaming_enabled: bool = False

    # Quality metrics
    accuracy_score: float = 0.0  # 0.0 to 1.0
    consistency_score: float = 0.0  # 0.0 to 1.0
    hallucination_risk: float = 0.0  # 0.0 to 1.0 (lower is better)

    # Cost metrics
    cost_per_1k_tokens: float = 0.0  # USD
    estimated_tokens_per_request: int = 0
    monthly_cost_estimate: float = 0.0

    # Performance metrics
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    def calculate_promise_score(self) -> float:
        """Calculate promise score for routing hypotheses."""
        # Quality component (accuracy, consistency, low hallucination)
        quality = (
            self.accuracy_score * 0.5 +
            self.consistency_score * 0.3 +
            (1.0 - self.hallucination_risk) * 0.2
        )

        # Cost efficiency (lower cost is better)
        cost_efficiency = 1.0 - min(1.0, self.cost_per_1k_tokens / 0.1)

        # Latency performance (lower latency is better)
        latency_score = 1.0 - min(1.0, self.p95_latency_ms / 5000.0)

        # Feature bonuses
        caching_bonus = 0.1 if self.caching_enabled else 0.0
        streaming_bonus = 0.05 if self.streaming_enabled else 0.0

        return (
            quality * 0.5 +
            cost_efficiency * 0.3 +
            latency_score * 0.15 +
            caching_bonus +
            streaming_bonus
        )


@dataclass
class OptimizationTree(HypothesisTree):
    """
    Extended tree for multi-domain optimization.

    Supports different task types (coding, workflow, routing)
    with domain-specific node types and validation strategies.
    """
    # Task type for this tree
    task_type: TaskType = TaskType.CODING

    # Domain-specific configuration
    domain_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize optimization tree."""
        super().__post_init__()
        # Set default budget limits based on task type
        if self.task_type == TaskType.WORKFLOW:
            self.max_nodes = 5  # Workflow optimization needs fewer nodes
            self.max_cost_usd = 0.30
        elif self.task_type == TaskType.ROUTING:
            self.max_nodes = 12  # Routing can explore more options
            self.max_cost_usd = 0.80

    def create_node(
        self,
        node_type: TaskType = TaskType.CODING,
        **kwargs
    ) -> OptimizationNode:
        """
        Create a domain-specific node for this tree.

        Args:
            node_type: Type of node to create
            **kwargs: Node-specific parameters

        Returns:
            Appropriate node subclass
        """
        node_classes = {
            TaskType.CODING: CodeHypothesisNode,
            TaskType.WORKFLOW: WorkflowHypothesisNode,
            TaskType.ROUTING: RoutingHypothesisNode,
        }

        node_class = node_classes.get(node_type, OptimizationNode)
        return node_class(task_type=node_type, **kwargs)

    def get_domain_statistics(self) -> Dict[str, Any]:
        """Get domain-specific statistics."""
        base_stats = self.get_statistics()

        if self.task_type == TaskType.CODING:
            code_stats = {
                "total_lines_changed": sum(
                    n.domain_metadata.get("lines_changed", 0)
                    for n in self.nodes.values()
                    if isinstance(n, CodeHypothesisNode)
                ),
                "languages_used": list(set(
                    n.language
                    for n in self.nodes.values()
                    if isinstance(n, CodeHypothesisNode) and n.language
                )),
                "avg_complexity": (
                    sum(n.cyclomatic_complexity for n in self.nodes.values()
                        if isinstance(n, CodeHypothesisNode)) /
                    max(1, sum(1 for n in self.nodes.values()
                              if isinstance(n, CodeHypothesisNode)))
                ),
            }
            base_stats.update(code_stats)

        elif self.task_type == TaskType.WORKFLOW:
            workflow_stats = {
                "total_parallel_steps": sum(
                    len(n.parallel_steps)
                    for n in self.nodes.values()
                    if isinstance(n, WorkflowHypothesisNode)
                ),
                "avg_latency_reduction": sum(
                    n.domain_metadata.get("latency_reduction", 0)
                    for n in self.nodes.values()
                    if isinstance(n, WorkflowHypothesisNode)
                ) / max(1, len([n for n in self.nodes.values()
                               if isinstance(n, WorkflowHypothesisNode)])),
            }
            base_stats.update(workflow_stats)

        elif self.task_type == TaskType.ROUTING:
            routing_stats = {
                "models_evaluated": list(set(
                    m
                    for n in self.nodes.values()
                    if isinstance(n, RoutingHypothesisNode)
                    for m in n.model_sequence
                )),
                "avg_cost_savings": sum(
                    n.cost_optimization_potential
                    for n in self.nodes.values()
                    if isinstance(n, RoutingHypothesisNode)
                ) / max(1, len([n for n in self.nodes.values()
                               if isinstance(n, RoutingHypothesisNode)])),
            }
            base_stats.update(routing_stats)

        return base_stats
