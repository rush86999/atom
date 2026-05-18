from __future__ import annotations

import logging
from typing import Any, Dict, List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.database import get_db
from core.ingestion_crud_service import IngestionCRUDService
from core.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion-crud"])


# =============================================================================
# Request/Response Models
# =============================================================================


class DiscoveredEntityResponse(BaseModel):
    """Pydantic model representing discovered entity details."""

    id: str
    tenant_id: str
    workspace_id: Union[str, None] = None
    sync_job_id: Union[str, None] = None
    entity_type_id: Union[str, None] = None
    discovered_type: str = Field(alias="_discovered_type")
    entity_name: Union[str, None] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float
    source_record_id: Union[str, None] = None
    source_record_type: Union[str, None] = None
    status: str
    linked_to_graph_node_id: Union[str, None] = None
    processed_at: Union[str, None] = None
    created_at: str
    updated_at: Union[str, None] = None
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True



class PaginatedEntitiesResponse(BaseModel):
    """Paginated list response for discovered entities."""

    entities: List[DiscoveredEntityResponse]
    total: int


class IngestionJobResponse(BaseModel):
    """Pydantic model representing an ingestion sync job."""

    id: str
    tenant_id: str
    integration_id: str
    trigger_type: str
    source_connection_id: Union[str, None] = None
    status: str
    started_at: Union[str, None] = None
    completed_at: Union[str, None] = None
    records_fetched: int
    records_processed: int
    entities_extracted: int
    relationships_extracted: int
    error_message: Union[str, None] = None
    error_details: Dict[str, Any] = Field(default_factory=dict)
    total_records: Union[int, None] = None
    progress_percentage: int
    created_at: str
    updated_at: Union[str, None] = None


class PaginatedJobsResponse(BaseModel):
    """Paginated list response for ingestion sync jobs."""

    jobs: List[IngestionJobResponse]
    total: int


class IntegrationStatusResponse(BaseModel):
    """Status summary statistics for a given integration's pipeline."""

    integration_id: str
    status_counts: Dict[str, int]
    last_sync_time: Union[str, None] = None
    error_rate: float
    latest_job_status: Union[str, None] = None


class BulkDeleteRequest(BaseModel):
    """Payload to perform a bulk cascade deletion of entities."""

    entity_ids: List[UUID] = Field(..., min_items=1, description="List of entity UUIDs to delete")


class MutateSuccessResponse(BaseModel):
    """Success response for mutations (delete, unlink)."""

    success: bool
    message: str


# =============================================================================
# Helper Serializers
# =============================================================================


def serialize_entity(e) -> Dict[str, Any]:
    """Manually serializes a DiscoveredEntity instance to dictionary."""
    return {
        "id": str(e.id),
        "tenant_id": str(e.tenant_id),
        "workspace_id": str(e.workspace_id) if e.workspace_id else None,
        "sync_job_id": str(e.sync_job_id) if e.sync_job_id else None,
        "entity_type_id": str(e.entity_type_id) if e.entity_type_id else None,
        "_discovered_type": e._discovered_type,
        "entity_name": e.entity_name,
        "properties": e.properties or {},
        "confidence_score": e.confidence_score or 0.0,
        "source_record_id": e.source_record_id,
        "source_record_type": e.source_record_type,
        "status": e.status or "pending",
        "linked_to_graph_node_id": str(e.linked_to_graph_node_id) if e.linked_to_graph_node_id else None,
        "processed_at": e.processed_at.isoformat() if e.processed_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        "extraction_metadata": e.extraction_metadata or {},
    }


def serialize_job(j) -> Dict[str, Any]:
    """Manually serializes an IngestionJob instance to dictionary."""
    return {
        "id": str(j.id),
        "tenant_id": str(j.tenant_id),
        "integration_id": j.integration_id,
        "trigger_type": j.trigger_type,
        "source_connection_id": str(j.source_connection_id) if j.source_connection_id else None,
        "status": j.status,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "records_fetched": j.records_fetched or 0,
        "records_processed": j.records_processed or 0,
        "entities_extracted": j.entities_extracted or 0,
        "relationships_extracted": j.relationships_extracted or 0,
        "error_message": j.error_message,
        "error_details": j.error_details or {},
        "total_records": j.total_records,
        "progress_percentage": j.progress_percentage or 0,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


# =============================================================================
# API Route Controllers
# =============================================================================


@router.get(
    "/{integration_id}/entities",
    response_model=PaginatedEntitiesResponse,
    summary="List pipeline discovered entities",
    description="Retrieve all entities extracted by this integration pipeline, filtered by status and type.",
)
async def list_pipeline_entities(
    integration_id: str,
    status: Union[str, None] = Query(default=None),
    type: Union[str, None] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Entity listing requires a valid tenant context")

    entities, total = IngestionCRUDService.list_entities(
        db=db,
        tenant_id=current_user.tenant_id,
        integration_id=integration_id,
        status=status,
        type=type,
        limit=limit,
        offset=offset,
    )
    return {
        "entities": [serialize_entity(e) for e in entities],
        "total": total,
    }


@router.get(
    "/{integration_id}/entities/{entity_id}",
    response_model=DiscoveredEntityResponse,
    summary="Get single discovered entity details",
)
async def get_pipeline_entity(
    integration_id: str,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Entity details require a valid tenant context")

    entity = IngestionCRUDService.get_entity(
        db=db,
        tenant_id=current_user.tenant_id,
        entity_id=entity_id,
    )
    if not entity or entity.source_record_type != integration_id:
        raise HTTPException(status_code=404, detail="Discovered entity not found")

    return serialize_entity(entity)


@router.delete(
    "/{integration_id}/entities/{entity_id}",
    response_model=MutateSuccessResponse,
    summary="Delete entity cascadingly",
)
async def delete_pipeline_entity(
    integration_id: str,
    entity_id: UUID,
    performed_by: str = Query(default="system"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Entity deletion requires a valid tenant context")

    # Get entity first to verify integration type
    entity = IngestionCRUDService.get_entity(db, current_user.tenant_id, entity_id)
    if not entity or entity.source_record_type != integration_id:
        raise HTTPException(status_code=404, detail="Discovered entity not found")

    success = IngestionCRUDService.delete_entity(
        db=db,
        tenant_id=current_user.tenant_id,
        entity_id=entity_id,
        performed_by=performed_by,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Entity deletion failed")

    return {
        "success": True,
        "message": f"Entity {entity_id} and its associated graph nodes/edges deleted successfully.",
    }


@router.post(
    "/{integration_id}/entities/{entity_id}/unlink",
    response_model=MutateSuccessResponse,
    summary="Unlink promoted entity",
)
async def unlink_pipeline_entity(
    integration_id: str,
    entity_id: UUID,
    performed_by: str = Query(default="system"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Entity unlinking requires a valid tenant context")

    # Verify entity exists and belongs to this integration
    entity = IngestionCRUDService.get_entity(db, current_user.tenant_id, entity_id)
    if not entity or entity.source_record_type != integration_id:
        raise HTTPException(status_code=404, detail="Discovered entity not found")

    success = IngestionCRUDService.unlink_entity(
        db=db,
        tenant_id=current_user.tenant_id,
        entity_id=entity_id,
        performed_by=performed_by,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Entity unlinking failed")

    return {
        "success": True,
        "message": f"Entity {entity_id} unlinked successfully from its promoted graph node.",
    }


@router.post(
    "/{integration_id}/entities/bulk-delete",
    response_model=MutateSuccessResponse,
    summary="Bulk cascade delete entities",
)
async def bulk_delete_pipeline_entities(
    integration_id: str,
    request: BulkDeleteRequest,
    performed_by: str = Query(default="system"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Bulk deletion requires a valid tenant context")

    # Filter out entities that are not mapped to this integration first
    valid_ids = []
    for eid in request.entity_ids:
        ent = IngestionCRUDService.get_entity(db, current_user.tenant_id, eid)
        if ent and ent.source_record_type == integration_id:
            valid_ids.append(eid)

    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid entity IDs for this integration provided")

    deleted_count = IngestionCRUDService.bulk_delete_entities(
        db=db,
        tenant_id=current_user.tenant_id,
        entity_ids=valid_ids,
        performed_by=performed_by,
    )
    return {
        "success": True,
        "message": f"Successfully deleted {deleted_count} out of {len(request.entity_ids)} entities.",
    }


@router.get(
    "/{integration_id}/jobs",
    response_model=PaginatedJobsResponse,
    summary="List ingestion background jobs",
    description="Retrieve historical backfill and scheduled sync jobs under workspace or tenant boundaries.",
)
async def list_pipeline_jobs(
    integration_id: str,
    status: Union[str, None] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    personal_scoped = {"gmail", "outlook", "slack"}
    is_personal = integration_id.lower() in personal_scoped

    if is_personal:
        if not current_user.workspace_id:
            raise HTTPException(
                status_code=403,
                detail="Sync jobs query for personal integrations requires a valid workspace context",
            )
    else:
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Sync jobs query requires a valid tenant context",
            )

    jobs, total = IngestionCRUDService.list_jobs(
        db=db,
        tenant_id=current_user.tenant_id,
        workspace_id=current_user.workspace_id,
        integration_id=integration_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "jobs": [serialize_job(j) for j in jobs],
        "total": total,
    }


@router.get(
    "/{integration_id}/status",
    response_model=IntegrationStatusResponse,
    summary="Get pipeline status metrics",
)
async def get_pipeline_status(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Pipeline status requires a valid tenant context")

    stats = IngestionCRUDService.get_status(
        db=db,
        tenant_id=current_user.tenant_id,
        integration_id=integration_id,
    )
    return stats
