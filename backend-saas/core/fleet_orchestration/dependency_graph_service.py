"""
Dependency graph service for task coordination.

This service provides NetworkX-based graph operations for:
- Building directed acyclic graphs (DAGs) from subtask dependencies
- Validating for circular dependencies
- Generating parallel execution groups via topological sort
- Identifying critical paths for duration estimation
"""

import logging
from typing import List, Tuple
import networkx as nx

# Import SubTask from task_decomposition_service
# This import is safe because both are in the same package
from .task_decomposition_service import SubTask

logger = logging.getLogger(__name__)


class DependencyGraphService:
    """
    Service for building and analyzing task dependency graphs.

    Uses NetworkX for graph algorithms:
    - build_graph(): Construct DiGraph from subtask dependencies
    - validate_cycles(): Detect circular dependencies
    - get_execution_groups(): Generate parallel execution groups
    - detect_critical_path(): Find longest execution path
    """

    def __init__(self, logger_instance=None):
        """
        Initialize dependency graph service.

        Args:
            logger_instance: Optional logger for testing
        """
        self.logger = logger_instance or logger

    def build_graph(self, subtasks: List[SubTask]) -> nx.DiGraph:
        """
        Build NetworkX DiGraph from subtask dependencies.

        Creates a directed graph where:
        - Nodes: subtask IDs
        - Edges: dependencies (from depends_on to subtask.id)
        - Node attributes: description, domain, tokens

        Args:
            subtasks: List of SubTask objects with depends_on fields

        Returns:
            NetworkX DiGraph with subtask IDs as nodes

        Raises:
            ValueError: If circular dependencies detected
        """
        if not subtasks:
            self.logger.warning("build_graph: Empty subtask list, returning empty graph")
            return nx.DiGraph()

        G = nx.DiGraph()

        # Add all subtasks as nodes with attributes
        for subtask in subtasks:
            G.add_node(
                subtask.id,
                description=subtask.description,
                domain=subtask.required_domain,
                tokens=subtask.estimated_tokens
            )

        # Add dependency edges
        edge_count = 0
        for subtask in subtasks:
            for dep_id in subtask.depends_on:
                # Only add edge if dependency node exists
                if G.has_node(dep_id):
                    G.add_edge(dep_id, subtask.id)
                    edge_count += 1
                else:
                    self.logger.warning(
                        f"build_graph: Dependency '{dep_id}' not found in subtasks, skipping edge to '{subtask.id}'"
                    )

        self.logger.info(f"build_graph: Built graph with {G.number_of_nodes()} nodes, {edge_count} edges")

        return G

    def validate_cycles(self, graph: nx.DiGraph) -> List[List[str]]:
        """
        Validate that graph is acyclic (no circular dependencies).

        Args:
            graph: NetworkX DiGraph to validate

        Returns:
            Empty list if valid (no cycles)

        Raises:
            ValueError: If cycles detected, with cycle details
        """
        if not graph or graph.number_of_nodes() == 0:
            return []

        if not nx.is_directed_acyclic_graph(graph):
            # Get cycle details for debugging
            cycles = list(nx.simple_cycles(graph))
            self.logger.error(f"validate_cycles: Circular dependencies detected: {cycles}")
            raise ValueError(
                f"Circular dependencies detected: {cycles}. "
                "Tasks cannot form dependency loops."
            )

        self.logger.debug("validate_cycles: Graph is acyclic")
        return []

    def get_execution_groups(self, graph: nx.DiGraph) -> List[List[str]]:
        """
        Generate parallel execution groups using topological sort.

        Groups nodes by depth (distance from root):
        - Group 0: Root nodes (no dependencies)
        - Group 1: Nodes that depend on Group 0
        - Group N: Nodes at depth N

        Nodes within each group can execute in parallel.
        Groups execute sequentially (Group N+1 starts after Group N completes).

        Args:
            graph: Validated DAG

        Returns:
            List of groups where each group is List[str] of subtask IDs
        """
        if not graph or graph.number_of_nodes() == 0:
            return []

        # Get topological order
        topo_order = list(nx.topological_sort(graph))

        # Calculate longest path depth for each node
        node_depths = {}
        for node in topo_order:
            predecessors = list(graph.predecessors(node))
            if not predecessors:
                node_depths[node] = 0
            else:
                node_depths[node] = max(node_depths[p] for p in predecessors) + 1

        # Group nodes by depth
        depth_to_nodes = {}
        for node, depth in node_depths.items():
            if depth not in depth_to_nodes:
                depth_to_nodes[depth] = []
            depth_to_nodes[depth].append(node)

        # Convert to ordered list of groups
        max_depth = max(depth_to_nodes.keys()) if depth_to_nodes else 0
        groups = [depth_to_nodes[d] for d in range(max_depth + 1)]

        self.logger.info(
            f"get_execution_groups: Generated {len(groups)} execution groups "
            f"({sum(len(g) for g in groups)} total tasks)"
        )

        return groups

    def detect_critical_path(
        self,
        graph: nx.DiGraph,
        subtasks: List[SubTask]
    ) -> Tuple[List[str], int]:
        """
        Identify critical path (longest execution time through graph).

        The critical path determines the minimum execution time because:
        - All tasks on the critical path must execute sequentially
        - Parallel tasks off the critical path don't affect total duration

        Args:
            graph: Validated DAG
            subtasks: List with token estimates for weighting

        Returns:
            Tuple of (critical_path_node_ids, total_tokens_on_path)
        """
        if not graph or graph.number_of_nodes() == 0:
            return [], 0

        # Use token estimates as node weights
        subtask_map = {s.id: s for s in subtasks}
        for node in graph.nodes():
            if node in subtask_map:
                graph.nodes[node]['weight'] = subtask_map[node].estimated_tokens
            else:
                graph.nodes[node]['weight'] = 0

        # Find longest path by token weight
        critical_path = nx.dag_longest_path(graph, weight='weight')
        total_tokens = sum(graph.nodes[n]['weight'] for n in critical_path)

        self.logger.info(
            f"detect_critical_path: Critical path has {len(critical_path)} nodes, "
            f"{total_tokens} total tokens"
        )

        return critical_path, total_tokens


# Convenience functions for direct import (matching plan requirements)

def build_graph(subtasks: List[SubTask]) -> nx.DiGraph:
    """
    Convenience function to build dependency graph.

    Args:
        subtasks: List of SubTask objects

    Returns:
        NetworkX DiGraph with dependencies
    """
    service = DependencyGraphService()
    return service.build_graph(subtasks)


def validate_cycles(graph: nx.DiGraph) -> List[List[str]]:
    """
    Convenience function to validate graph has no cycles.

    Args:
        graph: NetworkX DiGraph

    Returns:
        Empty list if valid, list of cycles if invalid

    Raises:
        ValueError: If circular dependencies detected
    """
    service = DependencyGraphService()
    return service.validate_cycles(graph)


def get_execution_groups(graph: nx.DiGraph) -> List[List[str]]:
    """
    Convenience function to generate execution groups.

    Args:
        graph: NetworkX DiGraph (must be acyclic)

    Returns:
        List of execution groups

    Raises:
        ValueError: If graph has cycles
    """
    service = DependencyGraphService()
    return service.get_execution_groups(graph)


def detect_critical_path(
    graph: nx.DiGraph,
    subtasks: List[SubTask]
) -> Tuple[List[str], int]:
    """
    Convenience function to detect critical path.

    Args:
        graph: NetworkX DiGraph (must be acyclic)
        subtasks: List of SubTask objects with token estimates

    Returns:
        Tuple of (critical_path_nodes, total_tokens)

    Raises:
        ValueError: If graph has cycles
    """
    service = DependencyGraphService()
    return service.detect_critical_path(graph, subtasks)
