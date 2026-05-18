from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import delete, func, or_
from sqlalchemy.orm import Session

from core.models import DiscoveredEntity, GraphEdge, GraphNode, IngestionAuditLog, IngestionJob

logger = logging.getLogger(__name__)


class IngestionCRUDService:
    """Service layer for Ingestion Pipeline CRUD APIs and lifecycle management.

    Handles read operations, cascading deletions, audit logging, unlinking,
    stable content hashing, and downstream Knowledge Graph syncing.
    """

    @staticmethod
    def calculate_content_hash(
        entity_name: Optional[str],
        discovered_type: str,
        properties: Optional[Dict[str, Any]],
    ) -> str:
        """Calculate a stable SHA-256 content hash for duplicate/idempotency checks.

        Recursively sorts properties dictionary keys to ensure stable signatures.
        """
        props = properties or {}
        # Stable JSON serialization with sorted keys
        serialized_props = json.dumps(props, sort_keys=True, default=str)
        raw_string = f"{entity_name or ''}:{discovered_type}:{serialized_props}"
        return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()

    @staticmethod
    def list_entities(
        db: Session,
        tenant_id: Union[str, uuid.UUID],
        integration_id: Optional[str] = None,
        status: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[DiscoveredEntity], int]:
        """List DiscoveredEntity records for a tenant with filters and pagination."""
        query = db.query(DiscoveredEntity).filter(DiscoveredEntity.tenant_id == tenant_id)

        if integration_id:
            query = query.filter(DiscoveredEntity.source_record_type == integration_id)
        if status:
            query = query.filter(DiscoveredEntity.status == status)
        if type:
            query = query.filter(DiscoveredEntity._discovered_type == type)

        total_count = query.count()
        results = query.order_by(DiscoveredEntity.created_at.desc()).offset(offset).limit(limit).all()
        return results, total_count

    @staticmethod
    def get_entity(
        db: Session,
        tenant_id: Union[str, uuid.UUID],
        entity_id: Union[str, uuid.UUID],
    ) -> Optional[DiscoveredEntity]:
        """Retrieve a single DiscoveredEntity record with strict tenant isolation."""
        return (
            db.query(DiscoveredEntity)
            .filter(
                DiscoveredEntity.id == entity_id,
                DiscoveredEntity.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def list_jobs(
        db: Session,
        tenant_id: Union[str, uuid.UUID],
        workspace_id: Union[str, uuid.UUID, None] = None,
        integration_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[IngestionJob], int]:
        """List IngestionJobs with tenant or workspace scoping filters.

        Tenant-scoped integrations are visible to all members of the tenant across workspaces,
        while personal-scoped integrations are locked to individual workspace boundaries.
        """
        from core.models import Workspace

        personal_scoped = {"gmail", "outlook", "slack"}
        is_personal = (
            integration_id.lower() in personal_scoped
            if integration_id
            else False
        )

        if is_personal and workspace_id:
            query = db.query(IngestionJob).filter(IngestionJob.tenant_id == workspace_id)
        else:
            # Tenant-scoped: retrieve jobs for all workspaces belonging to the tenant
            workspaces = db.query(Workspace).filter(Workspace.tenant_id == tenant_id).all()
            workspace_ids = [w.id for w in workspaces]
            query = db.query(IngestionJob).filter(IngestionJob.tenant_id.in_(workspace_ids))

        if integration_id:
            query = query.filter(IngestionJob.integration_id == integration_id)
        if status:
            query = query.filter(IngestionJob.status == status)

        total_count = query.count()
        results = query.order_by(IngestionJob.created_at.desc()).offset(offset).limit(limit).all()
        return results, total_count

    @staticmethod
    def get_status(
        db: Session,
        tenant_id: Union[str, uuid.UUID],
        integration_id: str,
    ) -> Dict[str, Any]:
        """Aggregate high-level pipeline status and metrics for an integration.

        Calculates counts, error rates, and latest sync timestamps.
        """
        # Count discovered entities by status
        entity_stats = (
            db.query(DiscoveredEntity.status, func.count(DiscoveredEntity.id))
            .filter(
                DiscoveredEntity.tenant_id == tenant_id,
                DiscoveredEntity.source_record_type == integration_id,
            )
            .group_by(DiscoveredEntity.status)
            .all()
        )
        status_counts = {status: count for status, count in entity_stats}

        # Query latest job metrics for this integration
        latest_job = (
            db.query(IngestionJob)
            .filter(
                # Note: IngestionJob uses tenant_id for workspace mapping in db schema
                IngestionJob.integration_id == integration_id,
            )
            .order_by(IngestionJob.created_at.desc())
            .first()
        )

        last_sync_time = None
        if latest_job:
            last_sync_time = latest_job.completed_at or latest_job.created_at

        # Calculate error rate of ingestion jobs
        total_jobs = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.integration_id == integration_id,
            )
            .count()
        )

        failed_jobs = (
            db.query(IngestionJob)
            .filter(
                IngestionJob.integration_id == integration_id,
                IngestionJob.status == "failed",
            )
            .count()
        )

        error_rate = 0.0
        if total_jobs > 0:
            error_rate = float(failed_jobs) / total_jobs

        return {
            "integration_id": integration_id,
            "status_counts": {
                "pending": status_counts.get("pending", 0),
                "linked": status_counts.get("linked", 0),
                "rejected": status_counts.get("rejected", 0),
                "expired": status_counts.get("expired", 0),
            },
            "last_sync_time": last_sync_time.isoformat() if last_sync_time else None,
            "error_rate": error_rate,
            "latest_job_status": latest_job.status if latest_job else None,
        }

    @classmethod
    def delete_entity(
        cls,
        db: Session,
        tenant_id: Union[str, uuid.UUID],
        entity_id: Union[str, uuid.UUID],
        performed_by: Optional[str] = "system",
        bypass_sync: bool = False,
    ) -> bool:
        """Atomically delete a DiscoveredEntity and perform a cascading cleanup of the Knowledge Graph.

        Cascading Rules:
        1. Remove the DiscoveredEntity record.
        2. If it was promoted/linked to a GraphNode, check the GraphNode's source references.
        3. Remove the entity reference from GraphNode.source_ids.
        4. If source_ids becomes empty (or had only this entity's reference), delete the GraphNode.
        5. If GraphNode is deleted, remove all orphaned incident GraphEdges.
        6. Append IngestionAuditLog record of 'delete' mutation.
        """
        entity = cls.get_entity(db, tenant_id, entity_id)
        if not entity:
            return False

        integration_id = entity.source_record_type or "unknown"
        source_record_id = entity.source_record_id
        linked_node_id = entity.linked_to_graph_node_id

        # 1. Cascading Graph Cleanup (if linked)
        if linked_node_id and not bypass_sync:
            graph_node = (
                db.query(GraphNode)
                .filter(
                    GraphNode.id == linked_node_id,
                    GraphNode.tenant_id == tenant_id,
                )
                .first()
            )

            if graph_node:
                # Remove entity reference from source_ids list
                source_ids = graph_node.source_ids or []
                str_entity_id = str(entity_id)

                # Clean any matches out of source_ids
                updated_sources = [
                    sid
                    for sid in source_ids
                    if str(sid) != str_entity_id and str(sid) != str(source_record_id)
                ]

                if not updated_sources:
                    # Deleting GraphNode cascaded via foreign keys or manual cleanup of edges
                    node_id = graph_node.id
                    # 1.1 Delete incident edges
                    db.query(GraphEdge).filter(
                        or_(
                            GraphEdge.source_node_id == node_id,
                            GraphEdge.target_node_id == node_id,
                        )
                    ).delete(synchronize_session=False)

                    # 1.2 Delete GraphNode itself
                    db.delete(graph_node)
                    logger.info(f"Cascaded delete GraphNode {node_id} and its edges")
                else:
                    graph_node.source_ids = updated_sources
                    db.add(graph_node)
                    logger.info(f"Updated GraphNode source list: {updated_sources}")

        # 2. Log deletion in IngestionAuditLog
        audit = IngestionAuditLog(
            tenant_id=tenant_id,
            integration_id=integration_id,
            operation="delete",
            entity_id=entity_id,
            source_record_id=source_record_id,
            idempotency_key=entity.content_hash,
            performed_by=performed_by,
        )
        db.add(audit)

        # 3. Delete the DiscoveredEntity record itself
        db.delete(entity)
        db.commit()
        return True

    @classmethod
    def bulk_delete_entities(
        cls,
        db: Session,
        tenant_id: Union[str, uuid.UUID],
        entity_ids: List[Union[str, uuid.UUID]],
        performed_by: Optional[str] = "system",
    ) -> int:
        """Bulk delete list of entity IDs with cascading Knowledge Graph cleanup and audit logging."""
        count = 0
        try:
            for eid in entity_ids:
                # Delete each entity cleanly inside transaction
                success = cls.delete_entity(
                    db,
                    tenant_id=tenant_id,
                    entity_id=eid,
                    performed_by=performed_by,
                )
                if success:
                    count += 1
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Bulk entity delete failed: {e}")
            raise

    @classmethod
    def unlink_entity(
        cls,
        db: Session,
        tenant_id: Union[str, uuid.UUID],
        entity_id: Union[str, uuid.UUID],
        performed_by: Optional[str] = "system",
    ) -> bool:
        """Unlink a DiscoveredEntity from its promotional GraphNode without deleting it.

        Unlinking Rules:
        1. Set status back to 'pending'.
        2. Set linked_to_graph_node_id to None.
        3. Remove references from GraphNode.source_ids.
        4. Log 'unlink' operation to IngestionAuditLog.
        """
        entity = cls.get_entity(db, tenant_id, entity_id)
        if not entity:
            return False

        linked_node_id = entity.linked_to_graph_node_id
        integration_id = entity.source_record_type or "unknown"
        source_record_id = entity.source_record_id

        # 1. Update DiscoveredEntity state
        entity.status = "pending"
        entity.linked_to_graph_node_id = None
        db.add(entity)

        # 2. Update linked GraphNode source references
        if linked_node_id:
            graph_node = (
                db.query(GraphNode)
                .filter(
                    GraphNode.id == linked_node_id,
                    GraphNode.tenant_id == tenant_id,
                )
                .first()
            )

            if graph_node:
                source_ids = graph_node.source_ids or []
                str_entity_id = str(entity_id)
                updated_sources = [
                    sid
                    for sid in source_ids
                    if str(sid) != str_entity_id and str(sid) != str(source_record_id)
                ]
                graph_node.source_ids = updated_sources
                db.add(graph_node)

        # 3. Log unlink in IngestionAuditLog
        audit = IngestionAuditLog(
            tenant_id=tenant_id,
            integration_id=integration_id,
            operation="unlink",
            entity_id=entity_id,
            source_record_id=source_record_id,
            idempotency_key=entity.content_hash,
            performed_by=performed_by,
        )
        db.add(audit)
        db.commit()
        return True

    @staticmethod
    def stale_entities_cleanup(
        db: Session,
        max_age_days: int = 30,
    ) -> int:
        """Purge pending or rejected DiscoveredEntity records older than standard threshold (defaults to 30 days)."""
        cutoff_date = datetime.now(timezone.utc) - datetime.timedelta(days=max_age_days)
        deleted_count = (
            db.query(DiscoveredEntity)
            .filter(
                DiscoveredEntity.status.in_(["pending", "rejected"]),
                DiscoveredEntity.created_at < cutoff_date,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"Purged {deleted_count} stale pending/rejected discovered entities")
        return deleted_count

    @staticmethod
    def sync_properties_to_graph_node(
        connection: Any,
        target: DiscoveredEntity,
    ) -> None:
        """Sync property updates from DiscoveredEntity to promoted GraphNode (SQLAlchemy event helper)."""
        if not target.linked_to_graph_node_id:
            return

        try:
            # SQLAlchemy connection execution for listeners
            stmt = (
                GraphNode.__table__.update()
                .where(GraphNode.__table__.c.id == target.linked_to_graph_node_id)
                .values(
                    properties=target.properties,
                    name=target.entity_name,
                    updated_at=func.now(),
                )
            )
            connection.execute(stmt)
            logger.info(f"Automatically synchronized properties to GraphNode {target.linked_to_graph_node_id}")
        except Exception as e:
            logger.error(f"Failed to auto-sync properties to graph node: {e}")

    @staticmethod
    def cleanup_graph_node_reference(
        connection: Any,
        target: DiscoveredEntity,
    ) -> None:
        """Cleanup GraphNode and Edges when a DiscoveredEntity is directly deleted (SQLAlchemy event helper)."""
        if not target.linked_to_graph_node_id:
            return

        try:
            # Query the linked GraphNode using SQL expression
            node_stmt = GraphNode.__table__.select().where(
                GraphNode.__table__.c.id == target.linked_to_graph_node_id
            )
            node_result = connection.execute(node_stmt).fetchone()

            if node_result:
                # Load current source_ids
                # Depending on driver, node_result.source_ids might be a list or serialized json string
                source_ids = node_result.source_ids or []
                if isinstance(source_ids, str):
                    try:
                        source_ids = json.loads(source_ids)
                    except Exception:
                        source_ids = []

                str_entity_id = str(target.id)
                updated_sources = [
                    sid
                    for sid in source_ids
                    if str(sid) != str_entity_id and str(sid) != str(target.source_record_id)
                ]

                if not updated_sources:
                    node_id = target.linked_to_graph_node_id
                    # 1. Delete incident edges
                    edge_del = GraphEdge.__table__.delete().where(
                        or_(
                            GraphEdge.__table__.c.source_node_id == node_id,
                            GraphEdge.__table__.c.target_node_id == node_id,
                        )
                    )
                    connection.execute(edge_del)

                    # 2. Delete GraphNode
                    node_del = GraphNode.__table__.delete().where(
                        GraphNode.__table__.c.id == node_id
                    )
                    connection.execute(node_del)
                    logger.info(f"[Listener] Automatically deleted GraphNode {node_id} and its edges")
                else:
                    # Update sources
                    stmt = (
                        GraphNode.__table__.update()
                        .where(GraphNode.__table__.c.id == target.linked_to_graph_node_id)
                        .values(
                            source_ids=updated_sources,
                            updated_at=func.now(),
                        )
                    )
                    connection.execute(stmt)
                    logger.info(f"[Listener] Automatically updated GraphNode source references to {updated_sources}")
        except Exception as e:
            logger.error(f"Failed to auto-clean GraphNode reference on delete event: {e}")
