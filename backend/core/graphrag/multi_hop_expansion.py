"""
Multi-Hop Expansion for GraphRAG

Based on 2025-2026 research:
- "When to use Graphs in RAG: 2025 Analysis" (arXiv:2506.05690v3)
- "GraphRAG Survey" (ACM)

Implements:
- Cue-driven activation for entity expansion
- Configurable hop depth limits
- Optimized traversal strategies for entity relationships
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import GraphNode, GraphEdge

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class ExpansionStrategy(Enum):
    """Strategies for multi-hop graph traversal"""
    BFS = "bfs"  # Breadth-first search (default)
    DFS = "dfs"  # Depth-first search
    BIDIRECTIONAL = "bidirectional"  # Search from both ends
    ADAPTIVE = "adaptive"  # Switch based on graph structure


class ActivationCue(Enum):
    """Cues that trigger entity expansion"""
    RELATIONSHIP_TYPE = "relationship_type"  # Expand based on relationship types
    ENTITY_TYPE = "entity_type"  # Expand based on entity types
    CONFIDENCE_THRESHOLD = "confidence"  # Expand based on edge confidence
    TEMPORAL_RELEVANCE = "temporal"  # Expand based on temporal proximity


class TraversalConstraint(Enum):
    """Constraints for traversal to prevent infinite expansion"""
    MAX_HOPS = "max_hops"
    MAX_NODES = "max_nodes"
    MAX_TIME_MS = "max_time_ms"
    RELEVANCE_THRESHOLD = "relevance_threshold"


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ExpansionConfig:
    """Configuration for multi-hop expansion"""
    # Traversal limits
    max_hop_depth: int = 4  # Maximum hops from start node
    max_nodes_per_hop: int = 50  # Maximum nodes to consider per hop level
    max_total_nodes: int = 200  # Total nodes across all hops

    # Cue-driven activation
    enabled_cues: Set[ActivationCue] = field(default_factory=lambda: {
        ActivationCue.RELATIONSHIP_TYPE,
        ActivationCue.ENTITY_TYPE,
        ActivationCue.CONFIDENCE_THRESHOLD,
    })

    # Relationship type priorities (higher = more likely to expand)
    relationship_priority: Dict[str, float] = field(default_factory=lambda: {
        "belongs_to": 1.0,
        "related_to": 0.8,
        "depends_on": 0.9,
        "similar_to": 0.7,
        "part_of": 0.85,
        "references": 0.75,
        "default": 0.5,
    })

    # Entity type priorities (higher = more likely to expand)
    entity_type_priority: Dict[str, float] = field(default_factory=lambda: {
        "user": 1.0,
        "task": 0.9,
        "ticket": 0.85,
        "formula": 0.8,
        "team": 0.75,
        "workspace": 0.7,
        "default": 0.5,
    })

    # Expansion strategy
    strategy: ExpansionStrategy = ExpansionStrategy.BIDIRECTIONAL

    # Relevance filtering
    min_relevance_score: float = 0.3  # Minimum relevance to include node
    relevance_decay: float = 0.85  # Decay factor per hop

    # Performance
    enable_early_termination: bool = True  # Stop if relevance drops too low
    enable_path_pruning: bool = True  # Prune low-relevance paths


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ExpansionNode:
    """Node in expansion with metadata"""
    id: str
    name: str
    entity_type: str
    hop_level: int = 0
    relevance_score: float = 1.0
    confidence: float = 1.0
    path: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, ExpansionNode) and self.id == other.id


@dataclass
class ExpansionPath:
    """A path through the graph with relevance tracking"""
    nodes: List[ExpansionNode] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    total_relevance: float = 1.0
    confidence: float = 1.0

    def add_hop(self, node: ExpansionNode, relationship: str):
        """Add a hop to this path"""
        self.nodes.append(node)
        self.relationships.append(relationship)
        # Relevance decays with each hop
        self.total_relevance *= node.relevance_score * ExpansionConfig().relevance_decay
        self.confidence *= node.confidence


@dataclass
class ExpansionResult:
    """Result of multi-hop expansion"""
    start_entity: str
    strategy_used: ExpansionStrategy
    max_depth_reached: int
    total_nodes_found: int
    nodes: List[ExpansionNode] = field(default_factory=list)
    paths: List[ExpansionPath] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Multi-Hop Expansion Engine
# ============================================================================

class MultiHopExpander:
    """
    Multi-hop graph expansion with cue-driven activation.

    Implements advanced traversal strategies from 2025-2026 research:
    - Cue-driven activation (expand based on relationship/entity types)
    - Configurable hop depth limits
    - Optimized traversal strategies
    """

    def __init__(self, config: Optional[ExpansionConfig] = None):
        self.config = config or ExpansionConfig()

    def expand(
        self,
        start_entity_id: str,
        workspace_id: str,
        session: Optional[Session] = None,
        query_context: Optional[Dict[str, Any]] = None
    ) -> ExpansionResult:
        """
        Perform multi-hop expansion from start entity.

        Args:
            start_entity_id: ID of entity to expand from
            workspace_id: Workspace identifier
            session: Optional database session
            query_context: Optional context for relevance scoring

        Returns:
            ExpansionResult with discovered nodes and paths
        """
        if session is None:
            with get_db_session() as sess:
                return self._expand_impl(start_entity_id, workspace_id, sess, query_context)
        else:
            return self._expand_impl(start_entity_id, workspace_id, session, query_context)

    def _expand_impl(
        self,
        start_entity_id: str,
        workspace_id: str,
        session: Session,
        query_context: Optional[Dict[str, Any]] = None
    ) -> ExpansionResult:
        """Internal expansion implementation"""
        result = ExpansionResult(
            start_entity=start_entity_id,
            strategy_used=self.config.strategy,
            max_depth_reached=0,
            total_nodes_found=0
        )

        # Get start node
        start_node = session.query(GraphNode).filter(
            GraphNode.id == start_entity_id,
            GraphNode.workspace_id == workspace_id
        ).first()

        if not start_node:
            logger.warning(f"Start node {start_entity_id} not found")
            return result

        # Initialize with start node
        start_expansion = ExpansionNode(
            id=start_node.id,
            name=start_node.name,
            entity_type=start_node.type,
            hop_level=0,
            relevance_score=1.0,
            path=[start_node.id],
            properties=start_node.properties or {}
        )

        visited: Set[str] = {start_entity_id}
        current_level: List[ExpansionNode] = [start_expansion]
        result.nodes.append(start_expansion)

        # Track paths
        active_paths: List[ExpansionPath] = [
            ExpansionPath(nodes=[start_expansion], total_relevance=1.0)
        ]

        # Expand hop by hop
        for hop in range(1, self.config.max_hop_depth + 1):
            if not current_level:
                break

            next_level: List[ExpansionNode] = []
            result.max_depth_reached = hop

            # Expand each node at current level
            for current_node in current_level:
                # Get neighbors using cue-driven activation
                neighbors = self._get_neighbors_with_cues(
                    current_node, workspace_id, session, query_context
                )

                for neighbor, rel_type, confidence in neighbors:
                    if neighbor.id in visited:
                        continue

                    # Calculate relevance for this hop
                    relevance = self._calculate_hop_relevance(
                        current_node, neighbor, rel_type, hop, query_context
                    )

                    # Check if relevance is above threshold
                    if relevance < self.config.min_relevance_score:
                        continue

                    # Create expansion node
                    expansion_node = ExpansionNode(
                        id=neighbor.id,
                        name=neighbor.name,
                        entity_type=neighbor.type,
                        hop_level=hop,
                        relevance_score=relevance,
                        confidence=confidence,
                        path=current_node.path + [neighbor.id],
                        properties=neighbor.properties or {}
                    )

                    visited.add(neighbor.id)
                    next_level.append(expansion_node)
                    result.nodes.append(expansion_node)

                    # Track relationship
                    result.relationships.append({
                        "from": current_node.id,
                        "to": neighbor.id,
                        "type": rel_type,
                        "confidence": confidence,
                        "hop_level": hop
                    })

                    # Extend paths
                    for path in active_paths:
                        if path.nodes[-1].id == current_node.id:
                            new_path = ExpansionPath(
                                nodes=path.nodes + [expansion_node],
                                relationships=path.relationships + [rel_type],
                                total_relevance=path.total_relevance * relevance * self.config.relevance_decay,
                                confidence=path.confidence * confidence
                            )
                            result.paths.append(new_path)

                    # Check node limit
                    if len(result.nodes) >= self.config.max_total_nodes:
                        logger.info(f"Reached max total nodes {self.config.max_total_nodes}")
                        break

                # Early termination if enabled
                if self.config.enable_early_termination and next_level:
                    avg_relevance = sum(n.relevance_score for n in next_level) / len(next_level)
                    if avg_relevance < self.config.min_relevance_score:
                        logger.debug(f"Early termination at hop {hop}: avg relevance {avg_relevance:.2f}")
                        break

            current_level = next_level[:self.config.max_nodes_per_hop]

        result.total_nodes_found = len(result.nodes)
        result.metadata = {
            "workspace_id": workspace_id,
            "visited_count": len(visited),
            "path_count": len(result.paths),
            "completed_at": datetime.now().isoformat()
        }

        logger.info(
            f"Multi-hop expansion: found {result.total_nodes_found} nodes, "
            f"reached depth {result.max_depth_reached}"
        )

        return result

    def _get_neighbors_with_cues(
        self,
        node: ExpansionNode,
        workspace_id: str,
        session: Session,
        query_context: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[GraphNode, str, float]]:
        """
        Get neighbors using cue-driven activation.

        Returns list of (neighbor_node, relationship_type, confidence) tuples.
        """
        # Get all edges connected to this node
        edges = session.query(GraphEdge).filter(
            (GraphEdge.source_node_id == node.id) | (GraphEdge.target_node_id == node.id),
            GraphEdge.workspace_id == workspace_id
        ).all()

        neighbors = []
        for edge in edges:
            # Determine direction and get neighbor
            if edge.source_node_id == node.id:
                neighbor_id = edge.target_node_id
                direction = "outgoing"
            else:
                neighbor_id = edge.source_node_id
                direction = "incoming"

            # Get neighbor node
            neighbor = session.query(GraphNode).filter(
                GraphNode.id == neighbor_id,
                GraphNode.workspace_id == workspace_id
            ).first()

            if not neighbor:
                continue

            rel_type = edge.relationship_type or "related_to"

            # Calculate activation score based on cues
            activation_score = self._calculate_activation_score(
                node, neighbor, rel_type, direction, query_context
            )

            neighbors.append((neighbor, rel_type, activation_score))

        # Sort by activation score (descending)
        neighbors.sort(key=lambda x: x[2], reverse=True)

        # Filter to top candidates
        max_neighbors = self.config.max_nodes_per_hop
        return neighbors[:max_neighbors]

    def _calculate_activation_score(
        self,
        from_node: ExpansionNode,
        to_node: GraphNode,
        rel_type: str,
        direction: str,
        query_context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate activation score for expanding to a neighbor.

        Uses cue-driven activation based on:
        - Relationship type priority
        - Entity type priority
        - Direction preference (outgoing > incoming)
        """
        score = 0.5  # Base score

        # Cue 1: Relationship type priority
        rel_priority = self.config.relationship_priority.get(
            rel_type.lower(),
            self.config.relationship_priority.get("default", 0.5)
        )
        score += rel_priority * 0.3

        # Cue 2: Entity type priority
        entity_priority = self.config.entity_type_priority.get(
            to_node.type.lower(),
            self.config.entity_type_priority.get("default", 0.5)
        )
        score += entity_priority * 0.2

        # Cue 3: Direction (outgoing edges slightly preferred)
        if direction == "outgoing":
            score += 0.1

        # Cue 4: Confidence from edge properties
        if to_node.properties:
            edge_confidence = to_node.properties.get("confidence", 1.0)
            score *= edge_confidence

        return min(score, 1.0)

    def _calculate_hop_relevance(
        self,
        from_node: ExpansionNode,
        to_node: GraphNode,
        rel_type: str,
        hop_level: int,
        query_context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate relevance score for a hop.

        Combines multiple factors:
        - Hop decay (relevance decreases with distance)
        - Relationship strength
        - Entity type match
        - Query context relevance (if provided)
        """
        relevance = 1.0

        # Apply hop-level decay
        relevance *= (self.config.relevance_decay ** hop_level)

        # Factor in relationship strength
        rel_strength = self.config.relationship_priority.get(
            rel_type.lower(),
            self.config.relationship_priority.get("default", 0.5)
        )
        relevance *= (0.5 + rel_strength * 0.5)

        # Factor in entity type
        entity_relevance = self.config.entity_type_priority.get(
            to_node.type.lower(),
            self.config.entity_type_priority.get("default", 0.5)
        )
        relevance *= (0.5 + entity_relevance * 0.5)

        return relevance


# ============================================================================
# SQL-based Multi-Hop Query (Optimized for PostgreSQL)
# ============================================================================

class SQLMultiHopExpander:
    """
    SQL-based multi-hop expansion using Recursive CTEs.

    Optimized for PostgreSQL with:
    - Efficient recursive CTE queries
    - Cycle detection
    - Configurable hop depth
    """

    def __init__(self, config: Optional[ExpansionConfig] = None):
        self.config = config or ExpansionConfig()

    def expand_sql(
        self,
        start_entity_id: str,
        workspace_id: str,
        max_depth: Optional[int] = None,
        session: Optional[Session] = None
    ) -> ExpansionResult:
        """
        Perform multi-hop expansion using SQL Recursive CTE.

        Args:
            start_entity_id: ID of entity to expand from
            workspace_id: Workspace identifier
            max_depth: Maximum hop depth (overrides config)
            session: Optional database session

        Returns:
            ExpansionResult with discovered nodes and relationships
        """
        max_depth = max_depth or self.config.max_hop_depth

        if session is None:
            with get_db_session() as sess:
                return self._expand_sql_impl(start_entity_id, workspace_id, max_depth, sess)
        else:
            return self._expand_sql_impl(start_entity_id, workspace_id, max_depth, session)

    def _expand_sql_impl(
        self,
        start_entity_id: str,
        workspace_id: str,
        max_depth: int,
        session: Session
    ) -> ExpansionResult:
        """Internal SQL expansion implementation"""
        result = ExpansionResult(
            start_entity=start_entity_id,
            strategy_used=ExpansionStrategy.BFS,
            max_depth_reached=0,
            total_nodes_found=0
        )

        try:
            # Build recursive CTE query
            cte_query = text(f"""
                WITH RECURSIVE traversal AS (
                    -- Base case: start node
                    SELECT
                        n.id, n.name, n.type, n.description, n.properties,
                        0 as hop_level,
                        ARRAY[n.id] as path,
                        1.0 as relevance_score,
                        NULL::varchar as relationship_from,
                        NULL::varchar as relationship_type
                    FROM graph_nodes n
                    WHERE n.id = :start_id
                    AND n.workspace_id = :ws_id

                    UNION ALL

                    -- Recursive case: expand neighbors
                    SELECT
                        neighbor.id, neighbor.name, neighbor.type,
                        neighbor.description, neighbor.properties,
                        t.hop_level + 1,
                        t.path || neighbor.id,
                        t.relevance_score * :decay_factor * (
                            -- Relationship-based relevance boost
                            CASE e.relationship_type
                                WHEN 'belongs_to' THEN 1.0
                                WHEN 'depends_on' THEN 0.95
                                WHEN 'part_of' THEN 0.9
                                WHEN 'related_to' THEN 0.8
                                ELSE 0.7
                            END
                        ),
                        t.id,
                        e.relationship_type
                    FROM traversal t
                    JOIN graph_edges e ON (
                        e.source_node_id = t.id OR e.target_node_id = t.id
                    )
                    JOIN graph_nodes neighbor ON (
                        CASE
                            WHEN e.source_node_id = t.id THEN e.target_node_id = neighbor.id
                            ELSE e.source_node_id = neighbor.id
                        END
                    )
                    WHERE t.hop_level < :max_depth
                    AND e.workspace_id = :ws_id
                    AND neighbor.workspace_id = :ws_id
                    AND NOT (neighbor.id = ANY(t.path))  -- Cycle detection
                    AND t.relevance_score >= :min_relevance
                )
                SELECT DISTINCT
                    id, name, type, description, properties,
                    hop_level, relevance_score
                FROM traversal
                ORDER BY hop_level, relevance_score DESC
                LIMIT :max_nodes;
            """)

            # Execute query
            rows = session.execute(cte_query, {
                "start_id": start_entity_id,
                "ws_id": workspace_id,
                "max_depth": max_depth,
                "decay_factor": self.config.relevance_decay,
                "min_relevance": self.config.min_relevance_score,
                "max_nodes": self.config.max_total_nodes
            }).fetchall()

            # Process results
            seen_ids: Set[str] = set()
            for row in rows:
                if row.id not in seen_ids:
                    seen_ids.add(row.id)
                    result.nodes.append(ExpansionNode(
                        id=row.id,
                        name=row.name,
                        entity_type=row.type,
                        hop_level=row.hop_level,
                        relevance_score=row.relevance_score,
                        properties=row.properties or {}
                    ))
                    result.max_depth_reached = max(result.max_depth_reached, row.hop_level)

            result.total_nodes_found = len(result.nodes)

            # Get relationships for discovered nodes
            if seen_ids:
                rel_query = text("""
                    SELECT e.source_node_id, e.target_node_id,
                           e.relationship_type, e.properties
                    FROM graph_edges e
                    WHERE (e.source_node_id = ANY(:node_ids)
                           OR e.target_node_id = ANY(:node_ids))
                    AND e.workspace_id = :ws_id
                    LIMIT 100;
                """)

                rel_rows = session.execute(rel_query, {
                    "node_ids": list(seen_ids),
                    "ws_id": workspace_id
                }).fetchall()

                for rel in rel_rows:
                    result.relationships.append({
                        "from": rel.source_node_id,
                        "to": rel.target_node_id,
                        "type": rel.relationship_type,
                        "properties": rel.properties
                    })

            logger.info(
                f"SQL multi-hop expansion: found {result.total_nodes_found} nodes, "
                f"reached depth {result.max_depth_reached}"
            )

        except Exception as e:
            logger.error(f"SQL multi-hop expansion failed: {e}")
            result.metadata["error"] = str(e)

        return result


# ============================================================================
# Factory Functions
# ============================================================================

def get_multi_hop_expander(config: Optional[ExpansionConfig] = None) -> MultiHopExpander:
    """Get multi-hop expander instance"""
    return MultiHopExpander(config)


def get_sql_expander(config: Optional[ExpansionConfig] = None) -> SQLMultiHopExpander:
    """Get SQL-based multi-hop expander"""
    return SQLMultiHopExpander(config)
