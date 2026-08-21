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
from datetime import datetime, timezone
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

try:
    import igraph as ig
    IGRAPH_AVAILABLE = True
except ImportError:
    ig = None  # type: ignore[assignment]
    IGRAPH_AVAILABLE = False

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
    metadata: Dict[str, Any] = field(default_factory=dict)


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
            # leidenalg 0.10+ removed resolution_parameter from
            # ModularityVertexPartition; RBConfigurationVertexPartition is the
            # resolution-carrying partition type (compatible across versions).
            from leidenalg import RBConfigurationVertexPartition, find_partition

            # Convert NetworkX to igraph
            g = self._nx_to_igraph(graph)

            # Run Leiden
            partition = find_partition(
                g,
                RBConfigurationVertexPartition,
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

        # Use greedy modularity optimization. NOTE: nx.Graph has no
        # is_weighted() method (AttributeError — the fallback crashed for any
        # deployment without python-leiden/igraph, which is the default pip
        # install). Detect edge weights directly.
        has_weights = any("weight" in d for _, _, d in graph.edges(data=True))
        communities = list(nx_comm.greedy_modularity_communities(
            graph,
            resolution=resolution,
            weight='weight' if has_weights else None
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
        store_results: bool = True,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None
    ) -> DetectionResult:
        """
        Detect communities in workspace graph.

        Args:
            workspace_id: Workspace identifier
            session: Optional database session
            store_results: Whether to store results in database
            window_start: Optional W1 time-window start (exclusive for edge
                validity: edges invalidated at or before it are pruned)
            window_end: Optional W1 time-window end (inclusive: only edges
                born at or before it, and nodes created at or before it)

        Returns:
            DetectionResult with detected communities
        """
        if session is None:
            with get_db_session() as sess:
                return self._detect_impl(workspace_id, sess, store_results, window_start, window_end)
        else:
            return self._detect_impl(workspace_id, session, store_results, window_start, window_end)

    def _detect_impl(
        self,
        workspace_id: str,
        session: Session,
        store_results: bool,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None
    ) -> DetectionResult:
        """Internal detection implementation"""
        start_time = datetime.now()

        # Build graph from database (W1: window filters apply here)
        graph = self._build_graph(workspace_id, session, window_start, window_end)

        def _with_window_meta(metadata: Dict[str, Any]) -> Dict[str, Any]:
            if window_start is not None:
                metadata["window_start"] = window_start.isoformat()
            if window_end is not None:
                metadata["window_end"] = window_end.isoformat()
            return metadata

        if graph.number_of_nodes() < self.config.min_community_size:
            logger.info(f"Graph too small for community detection: {graph.number_of_nodes()} nodes")
            return DetectionResult(
                num_communities=0,
                modularity=0.0,
                coverage=0.0,
                metadata=_with_window_meta({"reason": "graph_too_small"})
            )

        # Determine resolution
        resolution = self._get_resolution(workspace_id, session, graph)

        # Run detection
        result = self.leiden.detect(graph, resolution)
        result.metadata = _with_window_meta(result.metadata)
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

    def _build_graph(
        self,
        workspace_id: str,
        session: Session,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None
    ) -> 'nx.Graph':
        """Build NetworkX graph from database.

        With a W1 window the graph snapshots the network as it was at that
        point in time: nodes must have been created at or before
        ``window_end``, and edges must overlap the window interval
        (born at or before ``window_end`` and never invalidated before
        ``window_start``). NULL bi-temporal fields are treated as always
        valid so legacy rows are never dropped.
        """
        if not NETWORKX_AVAILABLE:
            raise ImportError("NetworkX required for graph operations")

        windowed = window_start is not None or window_end is not None

        graph = nx.Graph()

        # Add nodes
        nodes_query = session.query(GraphNode).filter(
            GraphNode.workspace_id == workspace_id
        )
        if windowed and window_end is not None:
            nodes_query = nodes_query.filter(
                (GraphNode.created_at.is_(None)) | (GraphNode.created_at <= window_end)
            )
        nodes = nodes_query.all()

        for node in nodes:
            graph.add_node(str(node.id), name=node.name, type=node.type)

        # Add edges
        edges_query = session.query(GraphEdge).filter(
            GraphEdge.workspace_id == workspace_id
        )
        if windowed:
            edge_conds = []
            if window_end is not None:
                edge_conds.append(
                    (GraphEdge.valid_from.is_(None)) | (GraphEdge.valid_from <= window_end)
                )
            if window_start is not None:
                edge_conds.append(
                    (GraphEdge.invalid_at.is_(None)) | (GraphEdge.invalid_at > window_start)
                )
            if edge_conds:
                edges_query = edges_query.filter(*edge_conds)
        edges = edges_query.all()

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
        # Compare by enum VALUE, not identity: test suites that reload this
        # module (importlib.reload for import-path coverage) mint NEW
        # ResolutionPolicy classes with identical values, and identity
        # comparison against a stale instance would silently fall through
        # to the base_resolution default.
        policy_value = policy.value if isinstance(policy, Enum) else str(policy)

        if policy_value == ResolutionPolicy.FIXED.value:
            return self.config.base_resolution

        elif policy_value == ResolutionPolicy.ADAPTIVE.value:
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

        elif policy_value == ResolutionPolicy.HIERARCHICAL.value:
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
            entity_types: "defaultdict[str, int]" = defaultdict(int)

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
        """Store detected communities in database (replace-wipe per workspace)."""
        self._persist_communities(result.communities, workspace_id, session)

    def _clear_workspace_communities(
        self,
        session: Session,
        workspace_id: str,
        replaced_at: Optional[datetime] = None
    ) -> None:
        """Archive then delete all GraphCommunity + membership rows for a
        workspace (W7: the outgoing generation lands in
        graph_community_snapshots with [valid_from, invalid_at) so
        global_search(as_of=...) can travel back). ``replaced_at`` is the
        single generation instant — the archive's invalid_at AND the
        replacement's created_at — so consecutive intervals chain exactly."""
        from core.models import GraphCommunitySnapshot

        now = replaced_at or datetime.now(timezone.utc)
        # Capture the ids BEFORE deleting so the membership cleanup can target
        # them (the delete below removes the rows the subquery would read).
        old_rows = session.query(GraphCommunity).filter(
            GraphCommunity.workspace_id == workspace_id
        ).all()
        old_ids = [r.id for r in old_rows]
        if not old_ids:
            return

        member_map: Dict[str, List[str]] = {}
        memberships = session.query(CommunityMembership).filter(
            CommunityMembership.community_id.in_(old_ids)
        ).all()
        for m in memberships:
            member_map.setdefault(m.community_id, []).append(m.node_id)

        for row in old_rows:
            valid_from = getattr(row, "created_at", None) or now
            if valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=timezone.utc)
            session.add(GraphCommunitySnapshot(
                # getattr defaults: these columns are nullable and some duck-
                # typed row doubles (tests) predate them.
                tenant_id=getattr(row, "tenant_id", None),
                workspace_id=workspace_id,
                level=getattr(row, "level", 0) or 0,
                summary=getattr(row, "summary", None) or "community",
                keywords=getattr(row, "keywords", None) or [],
                node_ids=member_map.get(row.id, []),
                parent_label=getattr(row, "parent_community_id", None),
                valid_from=valid_from,
                invalid_at=now,
            ))

        session.query(CommunityMembership).filter(
            CommunityMembership.community_id.in_(old_ids)
        ).delete(synchronize_session=False)
        session.query(GraphCommunity).filter(
            GraphCommunity.workspace_id == workspace_id
        ).delete()

    def _persist_communities(
        self,
        communities: List[Community],
        workspace_id: str,
        session: Session
    ) -> None:
        """Persist communities (replace-wipe) resolving parent lineage.

        Generated ids ("comm_<i>", "leiden_comm_<i>") are per-run counters that
        recur at EVERY hierarchy level, so the persisted-id map is keyed by
        (id, level) — a bare id map would let a child resolve its own freshly
        minted uuid (self-parenting). Parents resolve to the community at
        level-1 with the same id, or stay NULL (never a dangling id).
        """
        try:
            # One generation instant: archived rows' invalid_at AND the
            # incoming rows' created_at (exact interval chaining, W7).
            generation_at = datetime.now(timezone.utc)
            self._clear_workspace_communities(session, workspace_id, generation_at)

            import uuid as _uuid

            id_map: Dict[Tuple[str, int], str] = {}
            for community in communities:
                # Generated ids are NOT unique across workspaces — but
                # GraphCommunity.id is a global PK, so the second workspace's
                # insert would collide and roll back the whole store. Mint a
                # fresh UUID for persistence; the in-memory id keeps its
                # display value.
                comm_id = (
                    str(_uuid.uuid4())
                    if community.id.startswith(("comm_", "leiden_comm_"))
                    else community.id
                )
                id_map[(community.id, community.level)] = comm_id
                parent_id = None
                if community.parent_community:
                    parent_id = id_map.get(
                        (community.parent_community, community.level - 1)
                    )
                db_comm = GraphCommunity(
                    id=comm_id,
                    workspace_id=workspace_id,
                    level=community.level,
                    parent_community_id=parent_id,
                    # Model columns only (create_all authority): summary is the
                    # single free-text field — fall back to description/name so
                    # the community's identity survives persistence.
                    summary=(
                        community.summary
                        or community.description
                        or community.name
                        or "community"
                    ),
                    keywords=community.keywords,
                    created_at=generation_at,  # W7: exact generation instant
                )
                session.add(db_comm)

                # Store memberships
                for node_id in community.nodes:
                    membership = CommunityMembership(
                        community_id=comm_id,
                        node_id=node_id,
                    )
                    session.add(membership)

            session.commit()
            logger.info(f"Stored {len(communities)} communities for workspace {workspace_id}")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store communities: {e}")

    def _link_hierarchy(self, hierarchy: CommunityHierarchy) -> None:
        """Link each child community to the previous-level community with
        MAXIMAL node overlap (containment heuristic — multi-resolution
        partitions are not guaranteed nested). Ties resolve to the first
        parent; children with zero overlap stay unparented. Populates
        ``Community.parent_community`` and ``Community.child_communities``
        in-memory; the persisted column mirrors it via ``_store_hierarchy``.
        """
        if hierarchy.max_depth < 2:
            return
        for level in range(1, hierarchy.max_depth):
            parents = hierarchy.levels.get(level - 1, [])
            if not parents:
                continue
            for child in hierarchy.levels.get(level, []):
                child_nodes = child.nodes
                if not child_nodes:
                    continue
                best_parent = None
                best_overlap = 0.0
                for parent in parents:
                    if not parent.nodes:
                        continue
                    overlap = len(child_nodes & parent.nodes) / len(child_nodes)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_parent = parent
                if best_parent is not None:
                    child.parent_community = best_parent.id
                    best_parent.child_communities.append(child.id)

    def _store_hierarchy(
        self,
        hierarchy: CommunityHierarchy,
        workspace_id: str,
        session: Session
    ) -> None:
        """Persist every hierarchy level with parent lineage (replace-wipe)."""
        flattened: List[Community] = []
        for level in sorted(hierarchy.levels):
            flattened.extend(hierarchy.levels[level])
        self._persist_communities(flattened, workspace_id, session)

    def detect_hierarchy(
        self,
        workspace_id: str,
        session: Optional[Session] = None,
        store_results: bool = True,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None
    ) -> CommunityHierarchy:
        """
        Detect hierarchical community structure.

        Detects communities at multiple resolutions (``min_resolution`` ->
        ``max_resolution`` over ``max_hierarchy_depth`` levels), links each
        child to the previous-level community with maximal node overlap
        (W2 lineage), and with ``store_results`` persists every level into
        ``graph_communities`` with ``parent_community_id`` lineage.

        With a W3 time window the graph snapshots the network as it was at
        that point in time before EVERY resolution runs (same semantics as
        W1's ``detect_communities``: nodes created at or before
        ``window_end``; edges overlapping the interval). The window is
        recorded in ``CommunityHierarchy.metadata``.

        Returns communities at multiple resolutions (with lineage when stored).
        """
        hierarchy = CommunityHierarchy()

        if session is None:
            with get_db_session() as sess:
                return self._detect_hierarchy_impl(
                    workspace_id, sess, store_results, window_start, window_end
                )
        else:
            return self._detect_hierarchy_impl(
                workspace_id, session, store_results, window_start, window_end
            )

    def _detect_hierarchy_impl(
        self,
        workspace_id: str,
        session: Session,
        store_results: bool = True,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None
    ) -> CommunityHierarchy:
        """Internal hierarchy detection implementation"""
        if not self.config.enable_hierarchy:
            return CommunityHierarchy()

        hierarchy = CommunityHierarchy()

        # Build graph (W3: window filters apply here, before every resolution)
        graph = self._build_graph(workspace_id, session, window_start, window_end)
        if window_start is not None:
            hierarchy.metadata["window_start"] = window_start.isoformat()
        if window_end is not None:
            hierarchy.metadata["window_end"] = window_end.isoformat()
        hierarchy.metadata["graph_nodes"] = graph.number_of_nodes()
        hierarchy.metadata["graph_edges"] = graph.number_of_edges()

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

        # W2: lineage (max-overlap parent/child nesting) + optional persistence
        self._link_hierarchy(hierarchy)
        if store_results and hierarchy.max_depth > 0:
            self._store_hierarchy(hierarchy, workspace_id, session)

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
