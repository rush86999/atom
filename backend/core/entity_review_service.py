"""
Entity Review Service

Human-in-the-loop workflow for reviewing low-confidence and novel entity types.
Flags entities for review, tracks approval/rejection, provides feedback for prompt improvement.

Phase 323-04: Human-in-the-Loop Review System
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.models import DiscoveredEntity, GraphNode, EntityTypeDefinition
from core.entity_linking_service import EntityLinkingService
from core.schema_discovery_service import SchemaDiscoveryService

logger = logging.getLogger(__name__)


class EntityReviewService:
    """
    Human-in-the-loop review workflow for discovered entities.

    Features:
    - Flag low-confidence entities (<0.7) for review
    - Flag novel types (<5 samples) for review
    - Approval workflow with graph linking
    - Rejection workflow with reason tracking
    - Bulk approval by type for efficiency
    - Feedback collection for prompt improvement

    Review Workflow:
    1. Extract entities via LLM → DiscoveredEntity(status="pending")
    2. Flag for review → DiscoveredEntity(status="needs_review")
    3. Human review → approve/reject
    4. If approved → link to graph (status="linked")
    5. If rejected → store rejection reason (status="rejected")
    """

    def __init__(
        self,
        db: Session,
        entity_linking_service: Optional[EntityLinkingService] = None,
        schema_discovery_service: Optional[SchemaDiscoveryService] = None
    ):
        """
        Initialize Entity Review Service.

        Args:
            db: Database session
            entity_linking_service: Entity linking service instance
            schema_discovery_service: Schema discovery service instance
        """
        self.db = db
        self.entity_linking = entity_linking_service
        self.schema_discovery = schema_discovery_service

    async def flag_entities_for_review(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        confidence_threshold: float = 0.7,
        min_sample_count: int = 5
    ) -> int:
        """
        Flag low-confidence and novel-type entities for human review.

        Flagging Rules:
        - Confidence < 0.7 → Flag for review
        - Novel types (<5 samples) → Flag for review
        - Already reviewed → Skip

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            confidence_threshold: Minimum confidence score (default: 0.7)
            min_sample_count: Minimum samples for type familiarity (default: 5)

        Returns:
            Number of entities flagged
        """
        # Find low-confidence entities
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "pending",
            DiscoveredEntity.confidence_score < confidence_threshold
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        low_confidence_entities = query.all()

        # Find novel types (types with <5 samples)
        novel_type_counts = self.db.query(
            DiscoveredEntity._discovered_type,
            self.db.func.count(DiscoveredEntity.id).label('count')
        ).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "pending"
        ).group_by(
            DiscoveredEntity._discovered_type
        ).having(
            self.db.func.count(DiscoveredEntity.id) < min_sample_count
        ).all()

        novel_types = [row._discovered_type for row in novel_type_counts]

        # Flag novel type entities
        novel_type_entities = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == "pending",
            DiscoveredEntity._discovered_type.in_(novel_types)
        )

        if workspace_id:
            novel_type_entities = novel_type_entities.filter(
                DiscoveredEntity.workspace_id == workspace_id
            )

        novel_type_entities = novel_type_entities.all()

        # Combine and deduplicate
        entities_to_flag = list(set(low_confidence_entities + novel_type_entities))

        # Update status to needs_review
        for entity in entities_to_flag:
            entity.status = "needs_review"
            entity.extraction_metadata = entity.extraction_metadata or {}
            entity.extraction_metadata["flagged_at"] = datetime.now(timezone.utc).isoformat()
            entity.extraction_metadata["flag_reason"] = self._get_flag_reason(entity, novel_types)

        self.db.commit()

        logger.info(
            f"Flagged {len(entities_to_flag)} entities for review "
            f"({len(low_confidence_entities)} low-confidence, {len(novel_type_entities)} novel types)"
        )

        return len(entities_to_flag)

    def _get_flag_reason(self, entity: DiscoveredEntity, novel_types: List[str]) -> str:
        """
        Get flag reason for entity.

        Args:
            entity: DiscoveredEntity instance
            novel_types: List of novel type names

        Returns:
            Flag reason string
        """
        reasons = []

        if entity.confidence_score < 0.7:
            reasons.append(f"low_confidence ({entity.confidence_score:.2f})")

        if entity._discovered_type in novel_types:
            reasons.append("novel_type")

        return "; ".join(reasons) if reasons else "manual_review"

    async def approve_entity(
        self,
        entity_id: str,
        entity_type_slug: str,
        reviewer_user_id: str,
        notes: Optional[str] = None,
        create_type_if_missing: bool = True
    ) -> Optional[GraphNode]:
        """
        Approve a discovered entity and link it to the graph.

        Args:
            entity_id: DiscoveredEntity UUID
            entity_type_slug: Target entity type slug
            reviewer_user_id: Reviewer user UUID
            notes: Optional review notes
            create_type_if_missing: Create EntityTypeDefinition if missing

        Returns:
            Created GraphNode or None if approval failed
        """
        # Fetch entity
        entity = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.id == entity_id
        ).first()

        if not entity:
            logger.error(f"DiscoveredEntity {entity_id} not found")
            return None

        # Initialize linking service if needed
        if not self.entity_linking:
            self.entity_linking = EntityLinkingService(
                self.db,
                self.schema_discovery or SchemaDiscoveryService(self.db)
            )

        # Link to graph
        graph_node = await self.entity_linking.link_single_entity(
            entity_id=entity_id,
            entity_type_slug=entity_type_slug,
            create_type_if_missing=create_type_if_missing
        )

        if graph_node:
            # Update review metadata
            entity.extraction_metadata = entity.extraction_metadata or {}
            entity.extraction_metadata.update({
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": reviewer_user_id,
                "review_decision": "approved",
                "review_notes": notes
            })

            self.db.commit()

            logger.info(f"✓ Approved entity {entity_id} by {reviewer_user_id}")
            return graph_node
        else:
            logger.error(f"Failed to approve entity {entity_id}")
            return None

    async def reject_entity(
        self,
        entity_id: str,
        reviewer_user_id: str,
        reason: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Reject a discovered entity with reason tracking.

        Args:
            entity_id: DiscoveredEntity UUID
            reviewer_user_id: Reviewer user UUID
            reason: Rejection reason (hallucination, incorrect_type, missing_data, other)
            notes: Optional review notes

        Returns:
            True if rejected successfully
        """
        # Fetch entity
        entity = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.id == entity_id
        ).first()

        if not entity:
            logger.error(f"DiscoveredEntity {entity_id} not found")
            return False

        # Update status and metadata
        entity.status = "rejected"
        entity.extraction_metadata = entity.extraction_metadata or {}
        entity.extraction_metadata.update({
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": reviewer_user_id,
            "review_decision": "rejected",
            "rejection_reason": reason,
            "review_notes": notes
        })

        self.db.commit()

        logger.info(f"✗ Rejected entity {entity_id} by {reviewer_user_id} (reason: {reason})")
        return True

    async def bulk_approve_by_type(
        self,
        discovered_type: str,
        entity_type_slug: str,
        reviewer_user_id: str,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        confidence_min: Optional[float] = None
    ) -> int:
        """
        Bulk approve all entities of a given discovered type.

        Use Cases:
        - Review confirms 50 PurchaseOrder entities are valid
    - Bulk approve all to avoid manual approval

        Args:
            discovered_type: PascalCase discovered type (e.g., "PurchaseOrder")
            entity_type_slug: Target entity type slug (e.g., "purchase_order")
            reviewer_user_id: Reviewer user UUID
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            confidence_min: Minimum confidence score (optional filter)

        Returns:
            Number of entities approved
        """
        # Find entities to approve
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity._discovered_type == discovered_type,
            DiscoveredEntity.status.in_(["pending", "needs_review"])
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        if confidence_min is not None:
            query = query.filter(DiscoveredEntity.confidence_score >= confidence_min)

        entities = query.all()

        if not entities:
            logger.info(f"No entities found for bulk approval (type: {discovered_type})")
            return 0

        # Initialize linking service if needed
        if not self.entity_linking:
            self.entity_linking = EntityLinkingService(
                self.db,
                self.schema_discovery or SchemaDiscoveryService(self.db)
            )

        # Approve each entity
        approved_count = 0
        for entity in entities:
            graph_node = await self.entity_linking.link_single_entity(
                entity_id=entity.id,
                entity_type_slug=entity_type_slug,
                create_type_if_missing=True
            )

            if graph_node:
                # Update review metadata
                entity.extraction_metadata = entity.extraction_metadata or {}
                entity.extraction_metadata.update({
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "reviewed_by": reviewer_user_id,
                    "review_decision": "bulk_approved",
                    "bulk_approval_type": discovered_type
                })

                approved_count += 1

        self.db.commit()

        logger.info(
            f"Bulk approved {approved_count}/{len(entities)} entities "
            f"(type: {discovered_type} → {entity_type_slug})"
        )

        return approved_count

    async def bulk_reject_by_type(
        self,
        discovered_type: str,
        reviewer_user_id: str,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        reason: str = "bulk_rejection"
    ) -> int:
        """
        Bulk reject all entities of a given discovered type.

        Use Cases:
        - Review confirms entity type is invalid (e.g., "GenericEmail")
        - Bulk reject all to clean up dataset

        Args:
            discovered_type: PascalCase discovered type
            reviewer_user_id: Reviewer user UUID
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            reason: Rejection reason

        Returns:
            Number of entities rejected
        """
        # Find entities to reject
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity._discovered_type == discovered_type,
            DiscoveredEntity.status.in_(["pending", "needs_review"])
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        entities = query.all()

        if not entities:
            logger.info(f"No entities found for bulk rejection (type: {discovered_type})")
            return 0

        # Reject each entity
        for entity in entities:
            entity.status = "rejected"
            entity.extraction_metadata = entity.extraction_metadata or {}
            entity.extraction_metadata.update({
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": reviewer_user_id,
                "review_decision": "bulk_rejected",
                "rejection_reason": reason
            })

        self.db.commit()

        logger.info(f"Bulk rejected {len(entities)} entities (type: {discovered_type})")
        return len(entities)

    def get_review_stats(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get review statistics for dashboard.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID

        Returns:
            Statistics dict
        """
        # Base query
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        # Count by status
        stats = {
            "pending": query.filter(DiscoveredEntity.status == "pending").count(),
            "needs_review": query.filter(DiscoveredEntity.status == "needs_review").count(),
            "linked": query.filter(DiscoveredEntity.status == "linked").count(),
            "rejected": query.filter(DiscoveredEntity.status == "rejected").count(),
        }

        stats["total"] = sum(stats.values())

        # Calculate approval rate
        if stats["total"] > 0:
            stats["approval_rate"] = stats["linked"] / stats["total"]
        else:
            stats["approval_rate"] = 0.0

        # Get unique discovered types
        unique_types = self.db.query(
            DiscoveredEntity._discovered_type
        ).filter(
            DiscoveredEntity.tenant_id == tenant_id
        ).distinct().all()

        stats["unique_types"] = len(unique_types)

        return stats

    def get_entities_for_review(
        self,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        status: str = "needs_review",
        limit: int = 50,
        offset: int = 0
    ) -> List[DiscoveredEntity]:
        """
        Get entities pending review.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Optional workspace UUID
            status: Entity status (default: "needs_review")
            limit: Max entities to return
            offset: Pagination offset

        Returns:
            List of DiscoveredEntity instances
        """
        query = self.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.tenant_id == tenant_id,
            DiscoveredEntity.status == status
        )

        if workspace_id:
            query = query.filter(DiscoveredEntity.workspace_id == workspace_id)

        return query.order_by(
            DiscoveredEntity.created_at.desc()
        ).limit(limit).offset(offset).all()
