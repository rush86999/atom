"""
Workflow Composition Primitives

Based on 2025-2026 research:
- Enterprise Agent Workflows (Medium.com)
- AgentOrchestra patterns

Implements:
- Composition primitives (sequence, parallel, choice)
- Workflow composition strategies
- Composed workflow validation
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class CompositionPrimitive(Enum):
    """Basic workflow composition primitives"""
    SEQUENCE = "sequence"  # Sequential execution
    PARALLEL = "parallel"  # Parallel execution
    CHOICE = "choice"  # Conditional branch
    MERGE = "merge"  # Merge parallel branches
    SPLIT = "split"  # Split into parallel
    JOIN = "join"  # Wait for multiple inputs
    LOOP = "loop"  # Iterative execution
    TRY_CATCH = "try_catch"  # Error handling
    COMPENSATE = "compensate"  # Compensation action


class CompositionStrategy(Enum):
    """Strategies for composing workflows"""
    SEQUENTIAL = "sequential"  # All in sequence
    PARALLEL_FIRST = "parallel_first"  # Maximize parallelization
    DEPENDENCY_AWARE = "dependency_aware"  # Based on dependencies
    OPTIMAL = "optimal"  # Calculate optimal execution


@dataclass
class ComposerConfig:
    """Configuration for workflow composer"""
    # Composition
    max_depth: int = 10
    max_parallel_branches: int = 5
    max_loop_iterations: int = 100

    # Validation
    validate_composition: bool = True
    check_acyclic_deps: bool = True
    validate_primitives: bool = True

    # Optimization
    enable_optimization: bool = True
    auto_merge_steps: bool = True


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CompositionNode:
    """A node in a composed workflow"""
    node_id: str = ""
    primitive: CompositionPrimitive = CompositionPrimitive.SEQUENCE
    name: str = ""

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)

    # Children (for sequence, parallel, choice, etc.)
    children: List['CompositionNode'] = field(default_factory=list)

    # Branches (for choice)
    branches: Dict[str, 'CompositionNode'] = field(default_factory=dict)

    # Loop config
    loop_condition: Optional[str] = None
    max_iterations: int = 100

    # Error handling
    error_handler: Optional[str] = None

    # Metadata
    depth: int = 0
    estimated_duration_ms: float = 0.0


@dataclass
class ComposedWorkflow:
    """A workflow composed from primitives"""
    workflow_id: str = ""
    name: str = ""
    description: str = ""

    # Structure
    root: Optional[CompositionNode] = None

    # Metadata
    composer_type: CompositionStrategy = CompositionStrategy.DEPENDENCY_AWARE
    composed_at: datetime = field(default_factory=datetime.now)
    estimated_duration_ms: float = 0.0
    node_count: int = 0

    # Validation
    validated: bool = False
    validation_errors: List[str] = field(default_factory=list)


# ============================================================================
# Workflow Composer
# ============================================================================

class WorkflowComposer:
    """
    Composes workflows from primitives.

    Features:
    - Primitive composition (sequence, parallel, choice, etc.)
    - Dependency analysis
    - Cycle detection
    - Optimization
    """

    def __init__(self, config: Optional[ComposerConfig] = None):
        self.config = config or ComposerConfig()

    def compose(
        self,
        primitives: List[Tuple[CompositionPrimitive, Dict[str, Any]]],
        strategy: CompositionStrategy = CompositionStrategy.DEPENDENCY_AWARE,
        workflow_id: Optional[str] = None,
        name: str = "Composed Workflow"
    ) -> ComposedWorkflow:
        """
        Compose a workflow from primitives.

        Args:
            primitives: List of (primitive_type, config) tuples
            strategy: Composition strategy
            workflow_id: Optional workflow ID
            name: Workflow name

        Returns:
            Composed workflow
        """
        if not workflow_id:
            workflow_id = f"comp_wf_{uuid.uuid4().hex[:16]}"

        # Build composition tree
        root = self._build_composition_tree(primitives, strategy)

        # Calculate metrics
        node_count = self._count_nodes(root)
        duration = self._estimate_duration(root)

        workflow = ComposedWorkflow(
            workflow_id=workflow_id,
            name=name,
            root=root,
            composer_type=strategy,
            estimated_duration_ms=duration,
            node_count=node_count
        )

        # Validate if enabled
        if self.config.validate_composition:
            is_valid, errors = self._validate_composition(root)
            workflow.validated = is_valid
            workflow.validation_errors = errors

        logger.info(f"Composed workflow {workflow_id}: {node_count} nodes, {duration/1000:.2f}s estimated")

        return workflow

    def _build_composition_tree(
        self,
        primitives: List[Tuple[CompositionPrimitive, Dict[str, Any]]],
        strategy: CompositionStrategy
    ) -> CompositionNode:
        """Build composition tree from primitives"""
        if not primitives:
            raise ValueError("No primitives to compose")

        # Start with first primitive
        root = CompositionNode(
            node_id=f"node_0_{primitives[0][0].value}",
            primitive=primitives[0][0],
            name=primitives[0][0].value,
            config=primitives[0][1],
            depth=0
        )

        # Process remaining primitives
        node_id_counter = 1
        for primitive, config in primitives[1:]:
            node = CompositionNode(
                node_id=f"node_{node_id_counter}_{primitive.value}",
                primitive=primitive,
                name=primitive.value,
                config=config,
                depth=0
            )
            node_id_counter += 1

            # Add based on primitive type
            if primitive == CompositionPrimitive.SEQUENCE:
                root.children.append(node)

            elif primitive == CompositionPrimitive.PARALLEL:
                # Create new parallel root
                parallel_root = CompositionNode(
                    node_id=f"par_{node_id_counter}",
                    primitive=CompositionPrimitive.PARALLEL,
                    name="parallel_execution",
                    config={},
                    children=[root, node]
                )
                root = parallel_root
                node_id_counter += 1

            elif primitive == CompositionPrimitive.CHOICE:
                root.children.append(node)

            elif primitive == CompositionPrimitive.LOOP:
                root.children.append(node)

        return root

    def _count_nodes(self, root: CompositionNode) -> int:
        """Count total nodes in composition tree"""
        count = 1  # Count root
        for child in root.children:
            count += self._count_nodes(child)
        return count

    def _estimate_duration(self, root: CompositionNode) -> float:
        """Estimate workflow execution duration"""
        # Simple estimation based on primitives
        base_duration = 1000  # 1 second per primitive

        def estimate(node: CompositionNode) -> float:
            duration = base_duration

            if node.primitive == CompositionPrimitive.PARALLEL:
                # Parallel: take max of children
                child_durations = [estimate(child) for child in node.children]
                duration = max(child_durations) if child_durations else base_duration
            elif node.primitive == CompositionPrimitive.SEQUENCE:
                # Sequence: sum of children
                child_durations = [estimate(child) for child in node.children]
                duration = sum(child_durations)
            elif node.primitive == CompositionPrimitive.LOOP:
                # Loop: iterations * child duration
                iterations = node.config.get("iterations", 10)
                child_durations = [estimate(child) for child in node.children]
                duration = sum(child_durations) * iterations

            # Add custom duration if specified
            if "duration_ms" in node.config:
                duration = node.config["duration_ms"]

            node.estimated_duration_ms = duration
            return duration

        return estimate(root)

    def _validate_composition(self, root: CompositionNode) -> Tuple[bool, List[str]]:
        """Validate composed workflow"""
        errors = []

        # Check depth
        max_depth = self._get_max_depth(root)
        if max_depth > self.config.max_depth:
            errors.append(f"Composition depth {max_depth} exceeds maximum {self.config.max_depth}")

        # Check for cycles
        if self.config.check_acyclic_deps:
            cycles = self._detect_cycles(root)
            if cycles:
                errors.append(f"Cyclic dependencies detected: {cycles}")

        # Validate primitives
        if self.config.validate_primitives:
            self._validate_primitives(root, errors)

        return len(errors) == 0, errors

    def _get_max_depth(self, root: CompositionNode) -> int:
        """Get maximum depth of composition tree"""
        max_depth = root.depth

        for child in root.children:
            child_depth = self._get_max_depth(child)
            max_depth = max(max_depth, child_depth)

        return max_depth

    def _detect_cycles(self, root: CompositionNode) -> List[str]:
        """Detect cyclic dependencies"""
        cycles = []
        visited = set()
        path = []

        def dfs(node: CompositionNode) -> bool:
            if node.node_id in path:
                # Found cycle
                cycle_start = path.index(node.node_id)
                cycle = path[cycle_start:] + [node.node_id]
                cycles.append(" -> ".join(cycle))
                return True

            if node.node_id in visited:
                return False

            visited.add(node.node_id)
            path.append(node.node_id)

            for child in node.children:
                if dfs(child):
                    return True

            path.pop()
            return False

        dfs(root)
        return cycles

    def _validate_primitives(self, root: CompositionNode, errors: List[str]) -> None:
        """Validate primitive usage"""
        # Check for required children
        if root.primitive == CompositionPrimitive.PARALLEL:
            if len(root.children) < 2:
                errors.append(f"Parallel primitive {root.node_id} requires at least 2 children")

        # Check loop configuration
        if root.primitive == CompositionPrimitive.LOOP:
            if not root.loop_condition:
                errors.append(f"Loop primitive {root.node_id} requires condition")

        # Recursively validate children
        for child in root.children:
            self._validate_primitives(child, errors)

    def decompose(self, workflow: ComposedWorkflow) -> List[Tuple[CompositionPrimitive, Dict[str, Any]]]:
        """
        Decompose composed workflow into primitives.

        Args:
            workflow: Composed workflow to decompose

        Returns:
            List of (primitive, config) tuples in execution order
        """
        if not workflow.root:
            return []

        primitives = []

        def extract(node: CompositionNode) -> None:
            primitives.append((node.primitive, node.config))
            for child in node.children:
                extract(child)

        extract(workflow.root)
        return primitives

    def get_statistics(self) -> Dict[str, Any]:
        """Get composer statistics"""
        return {
            "config": {
                "max_depth": self.config.max_depth,
                "max_parallel_branches": self.config.max_parallel_branches,
                "max_loop_iterations": self.config.max_loop_iterations
            },
            "validation_enabled": self.config.validate_composition,
            "optimization_enabled": self.config.enable_optimization
        }


# ============================================================================
# Factory
# ============================================================================

_composer_instance: Optional[WorkflowComposer] = None


def get_workflow_composer(config: Optional[ComposerConfig] = None) -> WorkflowComposer:
    """Get or create workflow composer instance"""
    global _composer_instance
    if _composer_instance is None:
        _composer_instance = WorkflowComposer(config)
    return _composer_instance
