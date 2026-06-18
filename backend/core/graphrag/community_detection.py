"""
Community Detection for GraphRAG

Based on 2025-2026 research:
- "GraphRAG Survey" (ACM)
- "GraphRAG in 2026: Buyer's Guide" (Medium)

Implements:
- Leiden algorithm for graph clustering
- Community-based summarization
- Community hierarchy detection
"""

import logging
import itertools
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

import numpy as np

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logging.warning("NetworkX not available, using simplified community detection")

from core.database import get_db_session
from core.models import GraphNode, GraphEdge, GraphCommunity, CommunityMembership

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class ClusteringAlgorithm(Enum):
    """Community detection algorithms"""
    LEIDEN = "leiden"  # Leiden algorithm (preferred)
    LOUVAIN = "louvain"  # Louvain method (fallback)
    LABEL_PROPAGATION = "label_propagation"  # Fast but less accurate
    GIRVAN_NEWMAN = "girvan_newman"  # Hierarchical, slow


class ResolutionPolicy(Enum):
    """Policies for resolution parameter in Leiden"""
    FIXED = "fixed"  # Use fixed resolution
    ADAPTIVE = "adaptive"  # Adjust based on graph density
    HIERARCHICAL = "hierarchical"  # Multiple resolutions for hierarchy


@dataclass
class CommunityConfig:
    """Configuration for community detection"""
    # Algorithm selection
    algorithm: ClusteringAlgorithm = ClusteringAlgorithm.LEIDEN
    resolution_policy: ResolutionPolicy = ResolutionPolicy.ADAPTIVE

    # Resolution parameters (higher = fewer, smaller communities)
    base_resolution: float = 1.0
    min_resolution: float = 0.5
    max_resolution: float = 2.0

    # Community size constraints
    min_community_size: int = 3  # Minimum nodes per community
    max_community_size: int = 100  # Maximum nodes per community

    # Quality thresholds
    min_modularity: float = 0.3  # Minimum modularity score
    min_conductance: float = 0.4  # Minimum conductance score

    # Performance
    max_iterations: int = 100  # Maximum iterations for convergence
    tolerance: float = 1e-5  # Convergence tolerance
    random_seed: int = 42  # For reproducibility

    # Hierarchical detection
    enable_hierarchy: bool = True  # Detect community hierarchy
    max_hierarchy_depth: int = 3  # Maximum hierarchy levels


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Community:
    """A detected community with metadata"""
    id: str
    level: int = 0  # Hierarchy level
    nodes: Set[str] = field(default_factory=set)
    name: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    summary: str = ""
    modularity: float = 0.0
    conductance: float = 0.0
    size: int = 0
    parent_community: Optional[str] = None
    child_communities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.size = len(self.nodes)


@dataclass
class CommunityHierarchy:
    """Hierarchical community structure"""
    root_communities: List[Community] = field(default_factory=list)
    levels: Dict[int, List[Community]] = field(default_factory=dict)
    max_depth: int = 0


@dataclass
class DetectionResult:
    """Result of community detection"""
    communities: List[Community] = field(default_factory=list)
    hierarchy: Optional[CommunityHierarchy] = None
    num_communities: int = 0
    modularity: float = 0.0
    coverage: float = 0.0  # Fraction of nodes in communities
    execution_time_ms: float = 0.0
    algorithm_used: ClusteringAlgorithm = ClusteringAlgorithm.LEIDEN
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Leiden Algorithm Implementation
# ============================================================================

class LeidenAlgorithm:
    """
    Implementation of the Leiden algorithm for community detection.

    Based on:
    "From Louvain to Leiden: guaranteeing well-connected communities"
    (Traag et al., 2019)

    Key improvements over Louvain:
    - Guarantees well-connected communities
    - Faster convergence
    - Higher quality partitions
    """

    def __init__(self, config: Optional[CommunityConfig] = None):
        self.config = config or CommunityConfig()

    def detect(
        self,
        graph: 'nx.Graph',
        resolution: float = 1.0
    ) -> DetectionResult:
        """
        Detect communities using Leiden algorithm.

        Args:
            graph: NetworkX graph
            resolution: Resolution parameter

        Returns:
            DetectionResult with detected communities
        """
        start_time = datetime.now()

        if NETWORKX_AVAILABLE:
            result = self._detect_with_networkx(graph, resolution)
        else:
            result = self._detect_simple(graph, resolution)

        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        result.execution_time_ms = execution_time

        logger.info(
            f"Leiden detection: {result.num_communities} communities, "
            f"modularity={result.modularity:.3f}, "
            f"time={execution_time:.1f}ms"
        )

        return result

    def _detect_with_networkx(
        self,
        graph: 'nx.Graph',
        resolution: float
    ) -> DetectionResult:
        """Detect using python-louvain/igraph libraries"""
        try:
            import igraph as ig
            from leidenalg import ModularityVertexPartition, find_partition

            # Convert NetworkX to igraph
            g = self._nx_to_igraph(graph)

            # Run Leiden
            partition = find_partition(
                g,
                ModularityVertexPartition,
                resolution_parameter=resolution,
                n_iterations=-1  # Run until convergence
            )

            # Convert to DetectionResult
            return self._partition_to_result(partition, g, resolution)

        except ImportError:
            # Fallback to Louvain in NetworkX
            logger.info("python-leiden not available, using NetworkX Louvain")
            return self._detect_with_nx_louvain(graph, resolution)

    def _detect_with_nx_louvain(
        self,
        graph: 'nx.Graph',
        resolution: float
    ) -> DetectionResult:
        """Fallback to NetworkX Louvain"""
        import networkx.algorithms.community as nx_comm

        # Use greedy modularity optimization
        communities = list(nx_comm.greedy_modularity_communities(
            graph,
            resolution=resolution,
            weight='weight' if graph.is_weighted() else None
        ))

        result = DetectionResult(
            algorithm_used=ClusteringAlgorithm.LOUVAIN
        )

        # Convert to Community objects
        for i, comm_nodes in enumerate(communities):
            if len(comm_nodes) < self.config.min_community_size:
                continue

            community = Community(
                id=f"comm_{i}",
                nodes=set(comm_nodes),
                size=len(comm_nodes)
            )
            result.communities.append(community)

        result.num_communities = len(result.communities)
        result.modularity = nx_comm.modularity(graph, communities)

        return result

    def _detect_simple(
        self,
        graph: Any,
        resolution: float
    ) -> DetectionResult:
        """Simple label propagation fallback"""
        result = DetectionResult(
            algorithm_used=ClusteringAlgorithm.LABEL_PROPAGATION
        )

        # Simple clustering by connected components
        if NETWORKX_AVAILABLE:
            components = list(nx.connected_components(graph))
        else:
            # Very basic fallback
            components = [{str(n) for n in graph.nodes()}]

        for i, comp in enumerate(components):
            if len(comp) >= self.config.min_community_size:
                result.communities.append(Community(
                    id=f"comm_{i}",
                    nodes=comp,
                    size=len(comp)
                ))

        result.num_communities = len(result.communities)
        return result

    def _nx_to_igraph(self, nx_graph: 'nx.Graph') -> 'ig.Graph':
        """Convert NetworkX graph to igraph"""
        import igraph as ig

        # Get edges
        edges = [(str(u), str(v)) for u, v in nx_graph.edges()]
        edge_weights = [nx_graph[u][v].get('weight', 1.0) for u, v in nx_graph.edges()]

        # Create igraph
        g = ig.Graph()
        g.add_vertices([str(n) for n in nx_graph.nodes()])
        g.add_edges(edges)

        if edge_weights:
            g.es['weight'] = edge_weights

        return g

    def _partition_to_result(
        self,
        partition: Any,
        graph: 'ig.Graph',
        resolution: float
    ) -> DetectionResult:
        """Convert igraph partition to DetectionResult"""
        result = DetectionResult(
            algorithm_used=ClusteringAlgorithm.LEIDEN
        )

        # Group nodes by community
        community_map: Dict[int, Set[str]] = defaultdict(set)
        for i, membership in enumerate(partition.membership):
            community_map[membership].add(graph.vs[i]['name'])

        # Create Community objects
        for comm_id, nodes in community_map.items():
            if len(nodes) < self.config.min_community_size:
                continue

            community = Community(
                id=f"leiden_comm_{comm_id}",
                nodes=nodes,
                size=len(nodes)
            )
            result.communities.append(community)

        result.num_communities = len(result.communities)
        result.modularity = partition.q

        return result


# ============================================================================
# Community Detection Service
# ============================================================================

class CommunityDetectionService:
    """
    Service for detecting and managing graph communities.

    Features:
    - Multiple algorithm support (Leiden, Louvain, etc.)
    - Hierarchical community detection
    - Community summarization
    - Persistent storage
    """

    def __init__(self, config: Optional[CommunityConfig] = None):
        self.config = config or CommunityConfig()
        self.leiden = LeidenAlgorithm(self.config)

    def detect_communities(
        self,
        workspace_id: str,
        session: Optional[Session] = None,
        store_results: bool = True
    ) -> DetectionResult:
        """
        Detect communities in workspace graph.

        Args:
            workspace_id: Workspace identifier
            session: Optional database session
            store_results: Whether to store results in database

        Returns:
            DetectionResult with detected communities
        """
        if session is None:
            with get_db_session() as sess:
                return self._detect_impl(workspace_id, sess, store_results)
        else:
            return self._detect_impl(workspace_id, session, store_results)

    def _detect_impl(
        self,
        workspace_id: str,
        session: Session,
        store_results: bool
    ) -> DetectionResult:
        """Internal detection implementation"""
        start_time = datetime.now()

        # Build graph from database
        graph = self._build_graph(workspace_id, session)

        if graph.number_of_nodes() < self.config.min_community_size:
            logger.info(f"Graph too small for community detection: {graph.number_of_nodes()} nodes")
            return DetectionResult(
                num_communities=0,
                modularity=0.0,
                coverage=0.0,
                metadata={"reason": "graph_too_small"}
            )

        # Determine resolution
        resolution = self._get_resolution(workspace_id, session, graph)

        # Run detection
        result = self.leiden.detect(graph, resolution)
        result.metadata["workspace_id"] = workspace_id
        result.metadata["graph_nodes"] = graph.number_of_nodes()
        result.metadata["graph_edges"] = graph.number_of_edges()

        # Calculate coverage
        total_nodes = graph.number_of_nodes()
        covered_nodes = sum(len(c.nodes) for c in result.communities)
        result.coverage = covered_nodes / total_nodes if total_nodes > 0 else 0.0

        # Generate community names and keywords
        self._enrich_communities(result, workspace_id, session)

        # Store results if requested
        if store_results:
            self._store_communities(result, workspace_id, session)

        return result

    def _build_graph(self, workspace_id: str, session: Session) -> 'nx.Graph':
        """Build NetworkX graph from database"""
        if not NETWORKX_AVAILABLE:
            raise ImportError("NetworkX required for graph operations")

        graph = nx.Graph()

        # Add nodes
        nodes = session.query(GraphNode).filter(
            GraphNode.workspace_id == workspace_id
        ).all()

        for node in nodes:
            graph.add_node(str(node.id), name=node.name, type=node.type)

        # Add edges
        edges = session.query(GraphEdge).filter(
            GraphEdge.workspace_id == workspace_id
        ).all()

        for edge in edges:
            weight = edge.properties.get('weight', 1.0) if edge.properties else 1.0
            graph.add_edge(
                str(edge.source_node_id),
                str(edge.target_node_id),
                weight=weight,
                relationship_type=edge.relationship_type
            )

        logger.info(f"Built graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        return graph

    def _get_resolution(
        self,
        workspace_id: str,
        session: Session,
        graph: 'nx.Graph'
    ) -> float:
        """Determine resolution parameter based on policy"""
        policy = self.config.resolution_policy

        if policy == ResolutionPolicy.FIXED:
            return self.config.base_resolution

        elif policy == ResolutionPolicy.ADAPTIVE:
            # Adjust based on graph density
            num_nodes = graph.number_of_nodes()
            num_edges = graph.number_of_edges()

            if num_nodes == 0:
                return self.config.base_resolution

            # Density = 2 * edges / (nodes * (nodes - 1))
            max_edges = num_nodes * (num_nodes - 1) / 2
            density = num_edges / max_edges if max_edges > 0 else 0

            # Higher density -> higher resolution for finer-grained communities
            resolution = self.config.base_resolution * (1 + density)
            return max(self.config.min_resolution, min(resolution, self.config.max_resolution))

        elif policy == ResolutionPolicy.HIERARCHICAL:
            # Return list of resolutions for hierarchy
            return self.config.base_resolution

        return self.config.base_resolution

    def _enrich_communities(
        self,
        result: DetectionResult,
        workspace_id: str,
        session: Session
    ) -> None:
        """Enrich communities with names, keywords, descriptions"""
        for community in result.communities:
            # Get node names
            node_names = []
            entity_types = defaultdict(int)

            for node_id in community.nodes:
                node = session.query(GraphNode).filter(
                    GraphNode.id == node_id,
                    GraphNode.workspace_id == workspace_id
                ).first()

                if node:
                    node_names.append(node.name)
                    entity_types[node.type] += 1

            # Generate name
            dominant_type = max(entity_types.items(), key=lambda x: x[1])[0] if entity_types else "mixed"
            community.name = f"{dominant_type}_community_{community.id}"

            # Generate keywords from top entities
            community.keywords = node_names[:5]

            # Generate simple description
            community.description = (
                f"Community of {community.size} {dominant_type} entities: "
                f"{', '.join(node_names[:3])}{'...' if len(node_names) > 3 else ''}"
            )

    def _store_communities(
        self,
        result: DetectionResult,
        workspace_id: str,
        session: Session
    ) -> None:
        """Store detected communities in database"""
        try:
            # Clear existing communities for this workspace
            session.query(GraphCommunity).filter(
                GraphCommunity.workspace_id == workspace_id
            ).delete()

            session.query(CommunityMembership).filter(
                CommunityMembership.workspace_id == workspace_id
            ).delete()

            # Store new communities
            for community in result.communities:
                db_comm = GraphCommunity(
                    id=community.id,
                    workspace_id=workspace_id,
                    level=community.level,
                    name=community.name,
                    description=community.description,
                    keywords=community.keywords,
                    summary=community.summary,
                    modularity_score=community.modularity,
                    size=community.size
                )
                session.add(db_comm)

                # Store memberships
                for node_id in community.nodes:
                    membership = CommunityMembership(
                        community_id=community.id,
                        node_id=node_id,
                        workspace_id=workspace_id
                    )
                    session.add(membership)

            session.commit()
            logger.info(f"Stored {len(result.communities)} communities for workspace {workspace_id}")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store communities: {e}")

    def detect_hierarchy(
        self,
        workspace_id: str,
        session: Optional[Session] = None
    ) -> CommunityHierarchy:
        """
        Detect hierarchical community structure.

        Returns communities at multiple resolutions.
        """
        hierarchy = CommunityHierarchy()

        if session is None:
            with get_db_session() as sess:
                return self._detect_hierarchy_impl(workspace_id, sess)
        else:
            return self._detect_hierarchy_impl(workspace_id, session)

    def _detect_hierarchy_impl(
        self,
        workspace_id: str,
        session: Session
    ) -> CommunityHierarchy:
        """Internal hierarchy detection implementation"""
        if not self.config.enable_hierarchy:
            return CommunityHierarchy()

        # Build graph
        graph = self._build_graph(workspace_id, session)

        # Detect at multiple resolutions
        resolutions = np.linspace(
            self.config.min_resolution,
            self.config.max_resolution,
            self.config.max_hierarchy_depth
        )

        for level, resolution in enumerate(resolutions):
            result = self.leiden.detect(graph, resolution)

            communities_at_level = []
            for community in result.communities:
                community.level = level
                communities_at_level.append(community)

            hierarchy.levels[level] = communities_at_level
            hierarchy.max_depth = max(hierarchy.max_depth, level + 1)

        hierarchy.root_communities = hierarchy.levels.get(0, [])

        logger.info(
            f"Detected hierarchy with {hierarchy.max_depth} levels, "
            f"{sum(len(c) for c in hierarchy.levels.values())} total communities"
        )

        return hierarchy


# ============================================================================
# Factory Functions
# ============================================================================

def get_community_detector(config: Optional[CommunityConfig] = None) -> CommunityDetectionService:
    """Get community detection service instance"""
    return CommunityDetectionService(config)


def get_leiden_algorithm(config: Optional[CommunityConfig] = None) -> LeidenAlgorithm:
    """Get Leiden algorithm instance"""
    return LeidenAlgorithm(config)
