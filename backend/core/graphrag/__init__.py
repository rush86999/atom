"""
GraphRAG Enhancement Modules

Phase 2 of ATOM_ENHANCEMENT_PLAN - GraphRAG Enhancement with 2026 Techniques.

Modules:
- multi_hop_expansion: Cue-driven multi-hop traversal
- community_detection: Leiden algorithm for graph clustering
- dynamic_graph: Incremental updates and versioning
"""

from core.graphrag.multi_hop_expansion import (
    MultiHopExpander,
    SQLMultiHopExpander,
    ExpansionConfig,
    ExpansionStrategy,
    ActivationCue,
    ExpansionNode,
    ExpansionPath,
    ExpansionResult,
    get_multi_hop_expander,
    get_sql_expander,
)

from core.graphrag.community_detection import (
    CommunityDetectionService,
    LeidenAlgorithm,
    CommunityConfig,
    ClusteringAlgorithm,
    ResolutionPolicy,
    Community,
    CommunityHierarchy,
    DetectionResult,
    get_community_detector,
    get_leiden_algorithm,
)

from core.graphrag.dynamic_graph import (
    DynamicGraphManager,
    IncrementalUpdateManager,
    GraphVersionManager,
    TemporalGraphTracker,
    IncrementalUpdateConfig,
    UpdateType,
    GraphVersionStatus,
    GraphUpdate,
    GraphSnapshot,
    get_dynamic_graph_manager,
    get_incremental_updater,
    get_version_manager,
)

__all__ = [
    # Multi-hop expansion
    "MultiHopExpander",
    "SQLMultiHopExpander",
    "ExpansionConfig",
    "ExpansionStrategy",
    "ActivationCue",
    "ExpansionNode",
    "ExpansionPath",
    "ExpansionResult",
    "get_multi_hop_expander",
    "get_sql_expander",

    # Community detection
    "CommunityDetectionService",
    "LeidenAlgorithm",
    "CommunityConfig",
    "ClusteringAlgorithm",
    "ResolutionPolicy",
    "Community",
    "CommunityHierarchy",
    "DetectionResult",
    "get_community_detector",
    "get_leiden_algorithm",

    # Dynamic graph
    "DynamicGraphManager",
    "IncrementalUpdateManager",
    "GraphVersionManager",
    "TemporalGraphTracker",
    "IncrementalUpdateConfig",
    "UpdateType",
    "GraphVersionStatus",
    "GraphUpdate",
    "GraphSnapshot",
    "get_dynamic_graph_manager",
    "get_incremental_updater",
    "get_version_manager",
]
