"""
Entity Review API Routes

REST API endpoints for human-in-the-loop review workflow.
Endpoints support listing, approving, rejecting, and bulk operations.

Phase 323-04: Human-in-the-Loop Review System
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.database import get_db
from core.auth import get_current_user
from core.models import User, DiscoveredEntity
from core.entity_review_service import EntityReviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/discovered", tags=["Entity Review"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ApproveEntityRequest(BaseModel):
    """Request model for approving an entity."""
    entity_type_slug: str = Field(..., description="Target entity type slug (e.g., 'purchase_order')")
    notes: Optional[str] = Field(None, description="Optional review notes")


class RejectEntityRequest(BaseModel):
    """Request model for rejecting an entity."""
    reason: str = Field(..., description="Rejection reason (hallucination, incorrect_type, missing_data, other)")
    notes: Optional[str] = Field(None, description="Optional review notes")


class BulkApproveRequest(BaseModel):
    """Request model for bulk approving entities."""
    discovered_type: str = Field(..., description="PascalCase discovered type (e.g., 'PurchaseOrder')")
    entity_type_slug: str = Field(..., description="Target entity type slug (e.g., 'purchase_order')")
    confidence_min: Optional[float] = Field(None, description="Minimum confidence score")


class BulkRejectRequest(BaseModel):
    """Request model for bulk rejecting entities."""
    discovered_type: str = Field(..., description="PascalCase discovered type")
    reason: str = Field(..., description="Rejection reason")


class FlagEntitiesRequest(BaseModel):
    """Request model for flagging entities for review."""
    confidence_threshold: float = Field(0.7, description="Minimum confidence score")
    min_sample_count: int = Field(5, description="Minimum samples for type familiarity")


class EntityReviewResponse(BaseModel):
    """Response model for entity review."""
    id: str
    _discovered_type: str
    properties: Dict[str, Any]
    confidence_score: float
    status: str
    source_record_id: str
    source_record_type: str
    created_at: str
    extraction_metadata: Dict[str, Any] = {}


class ReviewStatsResponse(BaseModel):
    """Response model for review statistics."""
    pending: int
    needs_review: int
    linked: int
    rejected: int
    total: int
    approval_rate: float
    unique_types: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("", response_model=List[EntityReviewResponse])
async def list_entities_for_review(
    status: str = Query("needs_review", description="Entity status filter"),
    limit: int = Query(50, ge=1, le=100, description="Max entities to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List entities pending review.

    Filters by status (pending, needs_review, linked, rejected).
    Returns paginated list (default: 50 entities).
    """
    service = EntityReviewService(db)

    entities = service.get_entities_for_review(
        tenant_id=current_user.tenant_id,
        status=status,
        limit=limit,
        offset=offset
    )

    return [
        EntityReviewResponse(
            id=e.id,
            _discovered_type=e._discovered_type,
            properties=e.properties,
            confidence_score=e.confidence_score,
            status=e.status,
            source_record_id=e.source_record_id,
            source_record_type=e.source_record_type,
            created_at=e.created_at.isoformat(),
            extraction_metadata=e.extraction_metadata or {}
        )
        for e in entities
    ]


@router.post("/flag", response_model=Dict[str, Any])
async def flag_entities_for_review(
    request: FlagEntitiesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Flag low-confidence and novel-type entities for review.

    Flagging Rules:
    - Confidence < threshold → Flag
    - Novel types (<min_sample_count) → Flag
    """
    service = EntityReviewService(db)

    flagged_count = await service.flag_entities_for_review(
        tenant_id=current_user.tenant_id,
        confidence_threshold=request.confidence_threshold,
        min_sample_count=request.min_sample_count
    )

    return {
        "success": True,
        "flagged_count": flagged_count,
        "message": f"Flagged {flagged_count} entities for review"
    }


@router.post("/{entity_id}/approve", response_model=Dict[str, Any])
async def approve_entity(
    entity_id: str,
    request: ApproveEntityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve a discovered entity and link it to the graph.

    Approval Action:
    1. Validates entity exists
    2. Links to GraphNode with specified type
    3. Updates status to 'linked'
    4. Tracks reviewer and notes
    """
    service = EntityReviewService(db)

    graph_node = await service.approve_entity(
        entity_id=entity_id,
        entity_type_slug=request.entity_type_slug,
        reviewer_user_id=current_user.id,
        notes=request.notes,
        create_type_if_missing=True
    )

    if not graph_node:
        raise HTTPException(status_code=404, detail="Internal error")

    return {
        "success": True,
        "graph_node_id": graph_node.id,
        "entity_type": graph_node.type,
        "message": "Entity approved and linked to graph"
    }


@router.post("/{entity_id}/reject", response_model=Dict[str, Any])
async def reject_entity(
    entity_id: str,
    request: RejectEntityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reject a discovered entity with reason tracking.

    Rejection Action:
    1. Validates entity exists
    2. Updates status to 'rejected'
    3. Tracks rejection reason and notes
    """
    service = EntityReviewService(db)

    success = await service.reject_entity(
        entity_id=entity_id,
        reviewer_user_id=current_user.id,
        reason=request.reason,
        notes=request.notes
    )

    if not success:
        raise HTTPException(status_code=404, detail="Internal error")

    return {
        "success": True,
        "message": "Entity rejected",
        "rejection_reason": request.reason
    }


@router.post("/bulk-approve", response_model=Dict[str, Any])
async def bulk_approve_entities(
    request: BulkApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk approve all entities of a given discovered type.

    Use Cases:
    - Review confirms 50 PurchaseOrder entities are valid
    - Bulk approve all to avoid manual approval

    Performance:
    - Processes 50+ entities efficiently
    - Creates EntityTypeDefinition if missing
    - Links all entities to graph
    """
    service = EntityReviewService(db)

    approved_count = await service.bulk_approve_by_type(
        discovered_type=request.discovered_type,
        entity_type_slug=request.entity_type_slug,
        reviewer_user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        confidence_min=request.confidence_min
    )

    return {
        "success": True,
        "approved_count": approved_count,
        "message": f"Bulk approved {approved_count} entities (type: {request.discovered_type})"
    }


@router.post("/bulk-reject", response_model=Dict[str, Any])
async def bulk_reject_entities(
    request: BulkRejectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk reject all entities of a given discovered type.

    Use Cases:
    - Review confirms entity type is invalid (e.g., "GenericEmail")
    - Bulk reject all to clean up dataset
    """
    service = EntityReviewService(db)

    rejected_count = await service.bulk_reject_by_type(
        discovered_type=request.discovered_type,
        reviewer_user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        reason=request.reason
    )

    return {
        "success": True,
        "rejected_count": rejected_count,
        "message": f"Bulk rejected {rejected_count} entities (type: {request.discovered_type})"
    }


@router.get("/stats", response_model=ReviewStatsResponse)
async def get_review_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get review statistics for dashboard.

    Returns counts by status, approval rate, and unique type count.
    """
    service = EntityReviewService(db)

    stats = service.get_review_stats(tenant_id=current_user.tenant_id)

    return ReviewStatsResponse(**stats)
