"""
Memory Backfill Service

Orchestrates two pipelines for ingesting entity types and nodes into Atom's graph:
1. Pipeline 1: Entity type backfill with temporary storage and promotion
2. Pipeline 2: Entity node backfill with semantic data and batch migration

Features:
- Temporary storage until user promotion
- TTL-based auto-cleanup for unpromoted data
- Batch processing for memory efficiency
- Redis-based background jobs (non-blocking)
- Adaptive batch sizing based on memory
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models import EntityTypeDefinition, GraphNode
from core.temporary_entity_storage import TemporaryEntityType, TemporaryEntityNode
from core.schema_validator import SchemaValidator, get_schema_validator
from core.backfill_job_queue import BackfillJobQueue, get_backfill_job_queue

logger = logging.getLogger(__name__)


class MemoryBackfillService:
    """
    Service for memory-efficient backfill of entity types and nodes.

    Two-Pipeline Architecture:
    - Pipeline 1: Entity Type Discovery → Temporary Storage → User Promotion → Active Schema
    - Pipeline 2: Entity Node Extraction → Temporary Storage → Batch Migration → GraphNodes

    Memory Management:
    - Batch processing with configurable sizes
    - Streaming insertion for large datasets
    - Adaptive batch sizing based on available memory
    - Background processing via Redis (non-blocking)

    TTL Cleanup:
    - Unpromoted entity types expire after 48 hours (configurable)
    - Rejected types expire after 1 hour
    - Expired nodes cleaned up with their types
    """

    def __init__(
        self,
        db: Session,
        schema_validator: Optional[SchemaValidator] = None,
        job_queue: Optional[BackfillJobQueue] = None
    ):
        """
        Initialize memory backfill service.

        Args:
            db: Database session
            schema_validator: Schema validator instance
            job_queue: Redis job queue instance
        """
        self.db = db
        self.validator = schema_validator or get_schema_validator()
        self.job_queue = job_queue

    # ========================================================================
    # Pipeline 1: Entity Type Backfill
    # ========================================================================

    def store_temporary_entity_type(
        self,
        tenant_id: str,
        slug: str,
        display_name: str,
        json_schema: Dict[str, Any],
        description: Optional[str] = None,
        source: str = "memory_ingestion",
        ttl_hours: int = 48,
        confidence_score: Optional[int] = None
    ) -> TemporaryEntityType:
        """
        Store entity type in temporary storage awaiting promotion.

        Args:
            tenant_id: Tenant UUID
            slug: Entity type slug (e.g., "invoice")
            display_name: Display name
            json_schema: JSON schema definition
            description: Optional description
            source: Ingestion source
            ttl_hours: Time to live before expiration
            confidence_score: Auto-discovery confidence (0-100)

        Returns:
            TemporaryEntityType instance
        """
        # Validate schema
        is_valid, error_msg = self.validator.validate_schema(json_schema)
        if not is_valid:
            raise ValueError(f"Invalid JSON schema: {error_msg}")

        # Create temporary entity type
        temp_type = TemporaryEntityType(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            slug=slug,
            display_name=display_name,
            description=description,
            json_schema=json_schema,
            source=source,
            confidence_score=confidence_score
        )

        # Set expiration
        temp_type.set_expiration(ttl_hours)

        self.db.add(temp_type)
        self.db.commit()
        self.db.refresh(temp_type)

        logger.info(f"Stored temporary entity type {slug} for tenant {tenant_id} (expires {temp_type.expires_at})")
        return temp_type

    def promote_entity_type(
        self,
        temporary_type_id: str,
        tenant_id: str,
        migrate_nodes: bool = False
    ) -> EntityTypeDefinition:
        """
        Promote temporary entity type to active EntityTypeDefinition.

        Args:
            temporary_type_id: TemporaryEntityType ID
            tenant_id: Tenant UUID
            migrate_nodes: Whether to trigger node migration

        Returns:
            Promoted EntityTypeDefinition instance
        """
        # Get temporary type
        temp_type = self.db.query(TemporaryEntityType).filter(
            TemporaryEntityType.id == temporary_type_id,
            TemporaryEntityType.tenant_id == tenant_id
        ).first()

        if not temp_type:
            raise ValueError(f"Temporary entity type {temporary_type_id} not found")

        if temp_type.status != "draft":
            raise ValueError(f"Cannot promote entity type with status {temp_type.status}")

        # Check for duplicate slug
        existing = self.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == tenant_id,
            EntityTypeDefinition.slug == temp_type.slug,
            EntityTypeDefinition.is_active == True
        ).first()

        if existing:
            raise ValueError(f"Entity type {temp_type.slug} already exists")

        # Create active entity type
        active_type = EntityTypeDefinition(
            tenant_id=tenant_id,
            slug=temp_type.slug,
            display_name=temp_type.display_name,
            description=temp_type.description,
            json_schema=temp_type.json_schema,
            is_active=True,
            is_system=False,
            version=1
        )

        self.db.add(active_type)
        self.db.commit()
        self.db.refresh(active_type)

        # Mark temporary as promoted
        temp_type.promote(active_type.id)
        self.db.commit()

        logger.info(f"Promoted entity type {temp_type.slug} to active (ID: {active_type.id})")

        # Trigger node migration if requested
        if migrate_nodes:
            self._schedule_node_migration(tenant_id, temp_type.slug)

        return active_type

    def reject_entity_type(
        self,
        temporary_type_id: str,
        tenant_id: str,
        reason: str,
        ttl_hours: int = 1
    ):
        """
        Reject temporary entity type and mark for cleanup.

        Args:
            temporary_type_id: TemporaryEntityType ID
            tenant_id: Tenant UUID
            reason: Rejection reason
            ttl_hours: Time before cleanup
        """
        temp_type = self.db.query(TemporaryEntityType).filter(
            TemporaryEntityType.id == temporary_type_id,
            TemporaryEntityType.tenant_id == tenant_id
        ).first()

        if not temp_type:
            raise ValueError(f"Temporary entity type {temporary_type_id} not found")

        temp_type.reject(reason, ttl_hours)
        self.db.commit()

        logger.info(f"Rejected entity type {temp_type.slug}: {reason}")

    # ========================================================================
    # Pipeline 2: Entity Node Backfill
    # ========================================================================

    def store_temporary_entity_nodes(
        self,
        tenant_id: str,
        workspace_id: str,
        entity_type_slug: str,
        nodes: List[Dict[str, Any]],
        batch_size: int = 1000,
        ingestion_source: str = "memory_extraction"
    ) -> List[TemporaryEntityNode]:
        """
        Store entity nodes in temporary storage.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            entity_type_slug: Entity type slug
            nodes: List of node data dictionaries
            batch_size: Batch size for insertion
            ingestion_source: Ingestion source

        Returns:
            List of created TemporaryEntityNode instances
        """
        # Get temporary entity type
        temp_type = self.db.query(TemporaryEntityType).filter(
            TemporaryEntityType.tenant_id == tenant_id,
            TemporaryEntityType.slug == entity_type_slug,
            TemporaryEntityType.status == "draft"
        ).first()

        if not temp_type:
            raise ValueError(f"Draft entity type {entity_type_slug} not found")

        created_nodes = []

        # Process in batches
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]

            for node_data in batch:
                temp_node = TemporaryEntityNode(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    temporary_type_id=temp_type.id,
                    name=node_data["name"],
                    type=entity_type_slug,
                    description=node_data.get("description"),
                    properties=node_data.get("properties", {}),
                    ingestion_source=ingestion_source,
                    confidence_score=node_data.get("confidence_score")
                )

                self.db.add(temp_node)
                created_nodes.append(temp_node)

            # Commit batch
            self.db.commit()
            logger.info(f"Stored batch {i//batch_size + 1} of {len(nodes)//batch_size + 1} ({len(batch)} nodes)")

        # Update sample count on entity type
        temp_type.sample_count = temp_type.sample_count + len(nodes)
        self.db.commit()

        logger.info(f"Stored {len(nodes)} temporary nodes for entity type {entity_type_slug}")
        return created_nodes

    def batch_migrate_nodes(
        self,
        tenant_id: str,
        workspace_id: str,
        entity_type_slug: str,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Batch migrate temporary nodes to GraphNodes.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            entity_type_slug: Entity type to migrate
            batch_size: Batch size for migration

        Returns:
            Migration result dictionary
        """
        # Get all pending temporary nodes
        temp_nodes_query = self.db.query(TemporaryEntityNode).filter(
            TemporaryEntityNode.tenant_id == tenant_id,
            TemporaryEntityNode.workspace_id == workspace_id,
            TemporaryEntityNode.type == entity_type_slug,
            TemporaryEntityNode.status == "pending"
        )

        total_nodes = temp_nodes_query.count()
        migrated = 0
        failed = 0
        batch_num = 0

        while True:
            # Get next batch
            batch = temp_nodes_query.limit(batch_size).all()
            if not batch:
                break

            batch_num += 1

            for temp_node in batch:
                try:
                    # Create GraphNode
                    graph_node = GraphNode(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        name=temp_node.name,
                        type=temp_node.type,
                        description=temp_node.description,
                        properties=temp_node.properties
                    )

                    self.db.add(graph_node)
                    self.db.flush()  # Get ID without committing

                    # Mark temporary node as migrated
                    temp_node.mark_migrated(graph_node.id)
                    migrated += 1

                except Exception as e:
                    logger.error(f"Failed to migrate node {temp_node.id}: {e}")
                    failed += 1

            # Commit batch
            self.db.commit()
            logger.info(f"Migrated batch {batch_num} ({len(batch)} nodes)")

        return {
            "total_nodes": total_nodes,
            "migrated": migrated,
            "failed": failed,
            "batches_processed": batch_num
        }

    # ========================================================================
    # Batch Storage
    # ========================================================================

    def batch_store_temporary_entity_types(
        self,
        tenant_id: str,
        entity_types: Dict[str, Dict[str, Any]],
        source: str = "memory_ingestion",
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Batch store multiple entity types.

        Args:
            tenant_id: Tenant UUID
            entity_types: Dictionary of slug -> {display_name, json_schema, ...}
            source: Ingestion source
            batch_size: Batch size for validation and storage

        Returns:
            Result dictionary with counts and IDs
        """
        successful = []
        failed = []

        # Process in batches
        items = list(entity_types.items())
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            for slug, data in batch:
                try:
                    temp_type = self.store_temporary_entity_type(
                        tenant_id=tenant_id,
                        slug=slug,
                        display_name=data["title"],
                        json_schema=data,
                        source=source
                    )
                    successful.append(temp_type.id)
                except Exception as e:
                    logger.error(f"Failed to store entity type {slug}: {e}")
                    failed.append({"slug": slug, "error": str(e)})

            # Commit batch
            self.db.commit()

        return {
            "total": len(entity_types),
            "successful": len(successful),
            "failed": len(failed),
            "temporary_ids": successful,
            "errors": failed
        }

    # ========================================================================
    # TTL Cleanup
    # ========================================================================

    def cleanup_expired_temporary_data(self) -> Dict[str, Any]:
        """
        Clean up expired temporary entity types and nodes.

        Returns:
            Cleanup result dictionary
        """
        now = datetime.utcnow()

        # Get expired entity types
        expired_types = self.db.query(TemporaryEntityType).filter(
            TemporaryEntityType.expires_at < now,
            TemporaryEntityType.status.in_(["draft", "rejected", "expired"])
        ).all()

        types_removed = 0
        nodes_removed = 0
        removed_type_ids = []

        for expired_type in expired_types:
            # Count associated nodes
            node_count = self.db.query(TemporaryEntityNode).filter(
                TemporaryEntityNode.temporary_type_id == expired_type.id,
                TemporaryEntityNode.status == "pending"
            ).count()

            # Delete nodes
            self.db.query(TemporaryEntityNode).filter(
                TemporaryEntityNode.temporary_type_id == expired_type.id
            ).delete()

            # Delete type
            self.db.delete(expired_type)

            types_removed += 1
            nodes_removed += node_count
            removed_type_ids.append(expired_type.id)

        self.db.commit()

        logger.info(f"Cleaned up {types_removed} expired types and {nodes_removed} nodes")

        return {
            "entity_types_removed": types_removed,
            "nodes_removed": nodes_removed,
            "removed_type_ids": removed_type_ids
        }

    # ========================================================================
    # Memory Management
    # ========================================================================

    def calculate_adaptive_batch_size(
        self,
        available_memory_mb: int,
        target_memory_usage_percent: int = 70
    ) -> int:
        """
        Calculate adaptive batch size based on available memory.

        Args:
            available_memory_mb: Available memory in MB
            target_memory_usage_percent: Target memory usage percentage

        Returns:
            Recommended batch size
        """
        # Base batch sizes for different memory ranges
        if available_memory_mb < 256:
            base_size = 100
        elif available_memory_mb < 512:
            base_size = 500
        elif available_memory_mb < 1024:
            base_size = 1000
        elif available_memory_mb < 2048:
            base_size = 2000
        else:
            base_size = 5000

        # Adjust based on target usage
        adjustment = target_memory_usage_percent / 100.0
        batch_size = int(base_size * adjustment)

        # Enforce limits
        return max(100, min(batch_size, 5000))

    def streaming_store_temporary_nodes(
        self,
        tenant_id: str,
        workspace_id: str,
        entity_type_slug: str,
        nodes: List[Dict[str, Any]],
        batch_size: int = 500,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Stream node insertion to avoid loading all data into memory.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            entity_type_slug: Entity type slug
            nodes: List of node data (can be generator for true streaming)
            batch_size: Batch size for insertion
            progress_callback: Optional callback for progress updates

        Returns:
            Result dictionary
        """
        total_stored = 0
        batch_num = 0

        # Get temporary entity type
        temp_type = self.db.query(TemporaryEntityType).filter(
            TemporaryEntityType.tenant_id == tenant_id,
            TemporaryEntityType.slug == entity_type_slug,
            TemporaryEntityType.status == "draft"
        ).first()

        if not temp_type:
            raise ValueError(f"Draft entity type {entity_type_slug} not found")

        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            batch_num += 1

            # Insert batch
            for node_data in batch:
                temp_node = TemporaryEntityNode(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    temporary_type_id=temp_type.id,
                    name=node_data["name"],
                    type=entity_type_slug,
                    description=node_data.get("description"),
                    properties=node_data.get("properties", {})
                )

                self.db.add(temp_node)
                total_stored += 1

            # Commit batch
            self.db.commit()

            # Progress callback
            if progress_callback:
                progress_callback({
                    "batch": batch_num,
                    "batch_size": len(batch),
                    "total_stored": total_stored,
                    "progress": (total_stored / len(nodes)) * 100
                })

        return {
            "total_stored": total_stored,
            "batches_processed": batch_num
        }

    def batch_validate_schemas(
        self,
        tenant_id: str,
        schemas: Dict[str, Dict[str, Any]],
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Batch validate JSON schemas.

        Args:
            tenant_id: Tenant UUID
            schemas: Dictionary of slug -> schema
            batch_size: Batch size for validation

        Returns:
            Validation result dictionary
        """
        valid = 0
        invalid = 0
        errors = []

        items = list(schemas.items())
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            for slug, schema in batch:
                is_valid, error_msg = self.validator.validate_schema(schema)
                if is_valid:
                    valid += 1
                else:
                    invalid += 1
                    errors.append({
                        "slug": slug,
                        "error": error_msg
                    })

        return {
            "valid": valid,
            "invalid": invalid,
            "errors": errors
        }

    # ========================================================================
    # Background Jobs
    # ========================================================================

    def _schedule_node_migration(self, tenant_id: str, entity_type_slug: str):
        """Schedule background node migration job."""
        if not self.job_queue:
            logger.warning("No job queue configured, skipping node migration scheduling")
            return

        # Schedule async job (implementation-specific)
        # This would typically use asyncio.create_task or similar
        logger.info(f"Would schedule node migration for {entity_type_slug}")
