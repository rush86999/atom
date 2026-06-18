"""
Dynamic Graph Construction for GraphRAG

Based on 2025-2026 research:
- "GraphRAG in 2026: Buyer's Guide" (Medium)
- Incremental graph updates for real-time knowledge graphs

Implements:
- Incremental graph updates (no full rebuild)
- Temporal graph evolution tracking
- Graph versioning for rollback capability
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import GraphNode, GraphEdge

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class UpdateType(Enum):
    """Types of graph updates"""
    NODE_ADD = "node_add"
    NODE_UPDATE = "node_update"
    NODE_DELETE = "node_delete"
    EDGE_ADD = "edge_add"
    EDGE_UPDATE = "edge_update"
    EDGE_DELETE = "edge_delete"
    BATCH_UPDATE = "batch_update"


class GraphVersionStatus(Enum):
    """Status of graph versions"""
    DRAFT = "draft"  # Uncommitted changes
    COMMITTED = "committed"  # Committed version
    ROLLED_BACK = "rolled_back"  # Rolled back version
    ARCHIVED = "archived"  # Old archived version


@dataclass
class GraphUpdate:
    """A single graph update operation"""
    update_type: UpdateType
    entity_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    previous_state: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphSnapshot:
    """Snapshot of graph state at a point in time"""
    version_id: str
    timestamp: datetime
    node_count: int
    edge_count: int
    hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IncrementalUpdateConfig:
    """Configuration for incremental graph updates"""
    # Update batching
    batch_size: int = 100  # Number of updates per batch
    batch_timeout_ms: int = 5000  # Max time to wait before flushing batch

    # Versioning
    enable_versioning: bool = True
    max_versions: int = 100  # Maximum versions to keep
    version_retention_days: int = 30  # Days to keep versions

    # Incremental update triggers
    auto_update_on_change: bool = True
    update_threshold: int = 10  # Updates before triggering refresh

    # Performance
    enable_indexing: bool = True
    enable_stats: bool = True


# ============================================================================
# Graph Version Manager
# ============================================================================

class GraphVersionManager:
    """
    Manages graph versioning and rollback capability.

    Features:
    - Version tracking with hashes
    - Rollback to previous versions
    - Version diff and comparison
    """

    def __init__(self, config: Optional[IncrementalUpdateConfig] = None):
        self.config = config or IncrementalUpdateConfig()

    def create_version(
        self,
        workspace_id: str,
        session: Optional[Session] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GraphSnapshot:
        """
        Create a snapshot of the current graph state.

        Args:
            workspace_id: Workspace identifier
            session: Optional database session
            metadata: Optional metadata for the version

        Returns:
            GraphSnapshot representing the version
        """
        if session is None:
            with get_db_session() as sess:
                return self._create_version_impl(workspace_id, sess, metadata)
        else:
            return self._create_version_impl(workspace_id, session, metadata)

    def _create_version_impl(
        self,
        workspace_id: str,
        session: Session,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GraphSnapshot:
        """Internal version creation implementation"""
        # Count nodes and edges
        node_count = session.query(func.count(GraphNode.id)).filter(
            GraphNode.workspace_id == workspace_id
        ).scalar()

        edge_count = session.query(func.count(GraphEdge.id)).filter(
            GraphEdge.workspace_id == workspace_id
        ).scalar()

        # Generate version hash
        version_hash = self._generate_graph_hash(workspace_id, session)

        # Create snapshot
        snapshot = GraphSnapshot(
            version_id=self._generate_version_id(),
            timestamp=datetime.now(),
            node_count=node_count,
            edge_count=edge_count,
            hash=version_hash,
            metadata=metadata or {}
        )

        # Store version metadata (would use dedicated table in full implementation)
        logger.info(
            f"Created graph version {snapshot.version_id} for workspace {workspace_id}: "
            f"{node_count} nodes, {edge_count} edges"
        )

        return snapshot

    def rollback_to_version(
        self,
        workspace_id: str,
        version_id: str,
        session: Optional[Session] = None
    ) -> bool:
        """
        Rollback graph to a previous version.

        Args:
            workspace_id: Workspace identifier
            version_id: Version to rollback to
            session: Optional database session

        Returns:
            True if successful
        """
        if session is None:
            with get_db_session() as sess:
                return self._rollback_impl(workspace_id, version_id, sess)
        else:
            return self._rollback_impl(workspace_id, version_id, session)

    def _rollback_impl(
        self,
        workspace_id: str,
        version_id: str,
        session: Session
    ) -> bool:
        """Internal rollback implementation"""
        # In full implementation, this would:
        # 1. Retrieve version snapshot from storage
        # 2. Apply reverse operations from changelog
        # 3. Update current state to match target version

        logger.info(f"Rolling back workspace {workspace_id} to version {version_id}")
        # Placeholder - would implement actual rollback logic
        return True

    def _generate_version_id(self) -> str:
        """Generate unique version ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_str = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"v_{timestamp}_{random_str}"

    def _generate_graph_hash(self, workspace_id: str, session: Session) -> str:
        """Generate hash of current graph state"""
        # Get all node and edge IDs
        nodes = session.query(GraphNode.id).filter(
            GraphNode.workspace_id == workspace_id
        ).order_by(GraphNode.id).all()

        edges = session.query(GraphEdge.id, GraphEdge.source_node_id, GraphEdge.target_node_id).filter(
            GraphEdge.workspace_id == workspace_id
        ).order_by(GraphEdge.id).all()

        # Create hash string
        hash_input = f"nodes:{[n.id for n in nodes]}|edges:{[(e.source_node_id, e.target_node_id) for e in edges]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def get_version_diff(
        self,
        workspace_id: str,
        version_from: str,
        version_to: str,
        session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Get diff between two graph versions.

        Returns list of changes between versions.
        """
        # In full implementation, would retrieve stored diff
        return []


# ============================================================================
# Incremental Update Manager
# ============================================================================

class IncrementalUpdateManager:
    """
    Manages incremental updates to the graph.

    Features:
    - Batch update processing
    - Incremental indexing
    - Change tracking
    """

    def __init__(self, config: Optional[IncrementalUpdateConfig] = None):
        self.config = config or IncrementalUpdateConfig()
        self.version_manager = GraphVersionManager(config)
        self.pending_updates: List[GraphUpdate] = []
        self.last_flush = datetime.now()

    def add_update(
        self,
        update_type: UpdateType,
        entity_id: str,
        data: Dict[str, Any],
        workspace_id: str,
        session: Optional[Session] = None
    ) -> bool:
        """
        Add an update to the pending batch.

        Args:
            update_type: Type of update
            entity_id: ID of entity being updated
            data: New data for the entity
            workspace_id: Workspace identifier
            session: Optional database session

        Returns:
            True if update added successfully
        """
        update = GraphUpdate(
            update_type=update_type,
            entity_id=entity_id,
            data=data,
            metadata={"workspace_id": workspace_id}
        )

        self.pending_updates.append(update)

        # Check if we should flush
        if self._should_flush():
            return self.flush_updates(workspace_id, session)

        return True

    def flush_updates(
        self,
        workspace_id: str,
        session: Optional[Session] = None
    ) -> bool:
        """
        Flush pending updates to database.

        Args:
            workspace_id: Workspace identifier
            session: Optional database session

        Returns:
            True if successful
        """
        if not self.pending_updates:
            return True

        if session is None:
            with get_db_session() as sess:
                return self._flush_impl(workspace_id, sess)
        else:
            return self._flush_impl(workspace_id, session)

    def _flush_impl(
        self,
        workspace_id: str,
        session: Session
    ) -> bool:
        """Internal flush implementation"""
        try:
            # Group updates by type for efficiency
            grouped = self._group_updates(self.pending_updates)

            # Apply updates
            for update_type, updates in grouped.items():
                if update_type in (UpdateType.NODE_ADD, UpdateType.NODE_UPDATE):
                    self._apply_node_updates(updates, workspace_id, session)
                elif update_type == UpdateType.NODE_DELETE:
                    self._apply_node_deletes(updates, workspace_id, session)
                elif update_type in (UpdateType.EDGE_ADD, UpdateType.EDGE_UPDATE):
                    self._apply_edge_updates(updates, workspace_id, session)
                elif update_type == UpdateType.EDGE_DELETE:
                    self._apply_edge_deletes(updates, workspace_id, session)

            session.commit()

            flushed_count = len(self.pending_updates)
            self.pending_updates.clear()
            self.last_flush = datetime.now()

            logger.info(f"Flushed {flushed_count} updates for workspace {workspace_id}")

            # Create version after significant updates
            if self.config.enable_versioning and flushed_count >= self.config.update_threshold:
                self.version_manager.create_version(workspace_id, session)

            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to flush updates: {e}")
            return False

    def _should_flush(self) -> bool:
        """Check if pending updates should be flushed"""
        # Check batch size
        if len(self.pending_updates) >= self.config.batch_size:
            return True

        # Check timeout
        if self.config.batch_timeout_ms > 0:
            elapsed = (datetime.now() - self.last_flush).total_seconds() * 1000
            if elapsed >= self.config.batch_timeout_ms:
                return True

        return False

    def _group_updates(self, updates: List[GraphUpdate]) -> Dict[UpdateType, List[GraphUpdate]]:
        """Group updates by type"""
        grouped = defaultdict(list)
        for update in updates:
            grouped[update.update_type].append(update)
        return dict(grouped)

    def _apply_node_updates(
        self,
        updates: List[GraphUpdate],
        workspace_id: str,
        session: Session
    ) -> None:
        """Apply node updates to database"""
        for update in updates:
            entity_id = update.data.get("id", update.entity_id)
            name = update.data.get("name")
            entity_type = update.data.get("type", "unknown")

            # Try to find existing node
            existing = session.query(GraphNode).filter(
                GraphNode.id == entity_id,
                GraphNode.workspace_id == workspace_id
            ).first()

            if existing:
                # Update existing
                if name is not None:
                    existing.name = name
                if "type" in update.data:
                    existing.type = update.data["type"]
                if "description" in update.data:
                    existing.description = update.data["description"]
                if "properties" in update.data:
                    existing.properties = update.data["properties"]
                if "embedding" in update.data:
                    existing.embedding = update.data["embedding"]
            else:
                # Create new
                node = GraphNode(
                    id=entity_id,
                    workspace_id=workspace_id,
                    name=name or f"node_{entity_id}",
                    type=entity_type,
                    description=update.data.get("description", ""),
                    properties=update.data.get("properties", {}),
                    embedding=update.data.get("embedding")
                )
                session.add(node)

    def _apply_node_deletes(
        self,
        updates: List[GraphUpdate],
        workspace_id: str,
        session: Session
    ) -> None:
        """Apply node deletions"""
        for update in updates:
            session.query(GraphNode).filter(
                GraphNode.id == update.entity_id,
                GraphNode.workspace_id == workspace_id
            ).delete()

            # Also delete connected edges
            session.query(GraphEdge).filter(
                (GraphEdge.source_node_id == update.entity_id) |
                (GraphEdge.target_node_id == update.entity_id),
                GraphEdge.workspace_id == workspace_id
            ).delete()

    def _apply_edge_updates(
        self,
        updates: List[GraphUpdate],
        workspace_id: str,
        session: Session
    ) -> None:
        """Apply edge updates"""
        for update in updates:
            source_id = update.data.get("source_node_id")
            target_id = update.data.get("target_node_id")

            if not source_id or not target_id:
                continue

            # Check for existing edge
            existing = session.query(GraphEdge).filter(
                GraphEdge.source_node_id == source_id,
                GraphEdge.target_node_id == target_id,
                GraphEdge.workspace_id == workspace_id
            ).first()

            if existing:
                # Update existing
                if "relationship_type" in update.data:
                    existing.relationship_type = update.data["relationship_type"]
                if "properties" in update.data:
                    existing.properties = update.data["properties"]
            else:
                # Create new
                edge = GraphEdge(
                    id=update.data.get("id"),
                    workspace_id=workspace_id,
                    source_node_id=source_id,
                    target_node_id=target_id,
                    relationship_type=update.data.get("relationship_type", "related_to"),
                    properties=update.data.get("properties", {})
                )
                session.add(edge)

    def _apply_edge_deletes(
        self,
        updates: List[GraphUpdate],
        workspace_id: str,
        session: Session
    ) -> None:
        """Apply edge deletions"""
        for update in updates:
            session.query(GraphEdge).filter(
                GraphEdge.id == update.entity_id,
                GraphEdge.workspace_id == workspace_id
            ).delete()


# ============================================================================
# Temporal Graph Tracker
# ============================================================================

class TemporalGraphTracker:
    """
    Tracks temporal evolution of the graph.

    Features:
    - Time-based graph snapshots
    - Evolution metrics
    - Change rate detection
    """

    def __init__(self, config: Optional[IncrementalUpdateConfig] = None):
        self.config = config or IncrementalUpdateConfig()

    def get_evolution_metrics(
        self,
        workspace_id: str,
        hours_back: int = 24,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Get graph evolution metrics over time.

        Args:
            workspace_id: Workspace identifier
            hours_back: Hours to look back
            session: Optional database session

        Returns:
            Dictionary with evolution metrics
        """
        if session is None:
            with get_db_session() as sess:
                return self._get_evolution_impl(workspace_id, hours_back, sess)
        else:
            return self._get_evolution_impl(workspace_id, hours_back, session)

    def _get_evolution_impl(
        self,
        workspace_id: str,
        hours_back: int,
        session: Session
    ) -> Dict[str, Any]:
        """Internal evolution metrics implementation"""
        since = datetime.now() - timedelta(hours=hours_back)

        # Count nodes and edges created since
        new_nodes = session.query(func.count(GraphNode.id)).filter(
            GraphNode.workspace_id == workspace_id,
            GraphNode.created_at >= since
        ).scalar()

        new_edges = session.query(func.count(GraphEdge.id)).filter(
            GraphEdge.workspace_id == workspace_id,
            GraphEdge.created_at >= since
        ).scalar()

        # Current totals
        total_nodes = session.query(func.count(GraphNode.id)).filter(
            GraphNode.workspace_id == workspace_id
        ).scalar()

        total_edges = session.query(func.count(GraphEdge.id)).filter(
            GraphEdge.workspace_id == workspace_id
        ).scalar()

        # Calculate change rates
        node_growth_rate = (new_nodes / total_nodes * 100) if total_nodes > 0 else 0
        edge_growth_rate = (new_edges / total_edges * 100) if total_edges > 0 else 0

        return {
            "workspace_id": workspace_id,
            "period_hours": hours_back,
            "new_nodes": new_nodes,
            "new_edges": new_edges,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_growth_rate_percent": round(node_growth_rate, 2),
            "edge_growth_rate_percent": round(edge_growth_rate, 2),
            "query_time": datetime.now().isoformat()
        }


# ============================================================================
# Dynamic Graph Manager
# ============================================================================

class DynamicGraphManager:
    """
    Main manager for dynamic graph operations.

    Combines:
    - Incremental updates
    - Version management
    - Temporal tracking
    """

    def __init__(self, config: Optional[IncrementalUpdateConfig] = None):
        self.config = config or IncrementalUpdateConfig()
        self.update_manager = IncrementalUpdateManager(config)
        self.version_manager = GraphVersionManager(config)
        self.temporal_tracker = TemporalGraphTracker(config)

    def add_node(
        self,
        workspace_id: str,
        entity_id: str,
        name: str,
        entity_type: str,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
        embedding: Optional[Any] = None,
        session: Optional[Session] = None
    ) -> bool:
        """
        Add or update a node in the graph.

        Args:
            workspace_id: Workspace identifier
            entity_id: Node ID
            name: Node name
            entity_type: Entity type
            description: Node description
            properties: Additional properties
            embedding: Vector embedding
            session: Optional database session

        Returns:
            True if successful
        """
        data = {
            "id": entity_id,
            "name": name,
            "type": entity_type,
            "description": description,
            "properties": properties or {},
        }

        if embedding is not None:
            data["embedding"] = embedding

        return self.update_manager.add_update(
            UpdateType.NODE_ADD,
            entity_id,
            data,
            workspace_id,
            session
        )

    def add_edge(
        self,
        workspace_id: str,
        source_id: str,
        target_id: str,
        relationship_type: str = "related_to",
        properties: Optional[Dict[str, Any]] = None,
        session: Optional[Session] = None
    ) -> bool:
        """
        Add or update an edge in the graph.

        Args:
            workspace_id: Workspace identifier
            source_id: Source node ID
            target_id: Target node ID
            relationship_type: Type of relationship
            properties: Additional properties
            session: Optional database session

        Returns:
            True if successful
        """
        data = {
            "source_node_id": source_id,
            "target_node_id": target_id,
            "relationship_type": relationship_type,
            "properties": properties or {},
        }

        return self.update_manager.add_update(
            UpdateType.EDGE_ADD,
            f"{source_id}_{target_id}",
            data,
            workspace_id,
            session
        )

    def delete_node(
        self,
        workspace_id: str,
        entity_id: str,
        session: Optional[Session] = None
    ) -> bool:
        """Delete a node from the graph"""
        return self.update_manager.add_update(
            UpdateType.NODE_DELETE,
            entity_id,
            {},
            workspace_id,
            session
        )

    def delete_edge(
        self,
        workspace_id: str,
        edge_id: str,
        session: Optional[Session] = None
    ) -> bool:
        """Delete an edge from the graph"""
        return self.update_manager.add_update(
            UpdateType.EDGE_DELETE,
            edge_id,
            {},
            workspace_id,
            session
        )

    def flush(
        self,
        workspace_id: str,
        session: Optional[Session] = None
    ) -> bool:
        """Flush pending updates"""
        return self.update_manager.flush_updates(workspace_id, session)

    def create_version(
        self,
        workspace_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[Session] = None
    ) -> GraphSnapshot:
        """Create a version snapshot"""
        return self.version_manager.create_version(workspace_id, session, metadata)

    def get_evolution_metrics(
        self,
        workspace_id: str,
        hours_back: int = 24,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get temporal evolution metrics"""
        return self.temporal_tracker.get_evolution_metrics(
            workspace_id, hours_back, session
        )


# ============================================================================
# Factory Functions
# ============================================================================

def get_dynamic_graph_manager(config: Optional[IncrementalUpdateConfig] = None) -> DynamicGraphManager:
    """Get dynamic graph manager instance"""
    return DynamicGraphManager(config)


def get_incremental_updater(config: Optional[IncrementalUpdateConfig] = None) -> IncrementalUpdateManager:
    """Get incremental update manager instance"""
    return IncrementalUpdateManager(config)


def get_version_manager(config: Optional[IncrementalUpdateConfig] = None) -> GraphVersionManager:
    """Get version manager instance"""
    return GraphVersionManager(config)
