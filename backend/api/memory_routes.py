"""
Memory Routes - API endpoints for scoped memory storage and retrieval.

The key/value and session-context mutations are durable and tenant/user/agent
scoped. They use the existing ``TenantSetting`` store and ``AuditLog`` ledger;
no process-global dictionaries are shared across callers.
"""
from datetime import datetime
import logging
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.memory_write_service import (
    delete_memory as _delete_memory,
    read_context as _read_context,
    read_memory as _read_memory,
    search_memory as _search_memory,
    store_memory as _store_memory,
    update_context as _update_context,
)

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/memory", tags=["Memory"])


# Pydantic Models
class MemoryStoreRequest(BaseModel):
    key: str = Field(..., min_length=1, description="Memory key")
    value: Any = Field(..., description="Memory value")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata")


class MemoryResponse(BaseModel):
    key: str
    value: Any
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str
    verification: Optional[Dict[str, Any]] = None
    operation_id: Optional[str] = None
    audit_id: Optional[str] = None


class ContextResponse(BaseModel):
    session_id: str
    context: Dict[str, Any]
    timestamp: str
    verification: Optional[Dict[str, Any]] = None
    operation_id: Optional[str] = None
    audit_id: Optional[str] = None


def _raise_memory_write(result: Dict[str, Any]) -> None:
    """Map the verified-write envelope to a safe HTTP error."""
    status_value = str(result.get("status") or "")
    if status_value == "refused":
        raise HTTPException(
            status_code=int(result.get("http_status") or 409),
            detail={
                "error": {
                    "code": result.get("error_code") or "CONFLICT",
                    "message": result.get("error") or "Request refused",
                },
                "field": result.get("field"),
                "verification": result.get("verification"),
            },
        )
    if status_value == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": result.get("error_code") or "STALE_TARGET",
                    "message": result.get("error") or "Conflict",
                },
                "verification": result.get("verification"),
            },
        )
    if status_value == "not_applied":
        raise HTTPException(
            status_code=int(result.get("http_status") or 409),
            detail={
                "error": {
                    "code": result.get("error_code")
                    or "MEMORY_TRANSACTION_ROLLED_BACK",
                    "message": result.get("error")
                    or "The memory operation did not apply.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
            },
        )
    if status_value in ("committed_unverified", "effect_unknown"):
        code = (
            "MEMORY_EFFECT_UNKNOWN"
            if status_value == "effect_unknown"
            else "MEMORY_COMMITTED_UNVERIFIED")
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": code,
                    "message": result.get("message")
                    or "The memory operation outcome is uncertain.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "target_id": result.get("target_id"),
            },
        )


# Static routes MUST come before parameterized routes
@router.get("/stats")
async def get_memory_stats(
    workspace_id: str = "default",
    current_user: User = Depends(get_current_user),
):
    """
    Get memory statistics from LanceDB.

    Returns aggregated entity counts from all integrations, broken down by
    integration and entity type. This is a read-only statistics surface and is
    outside the scoped key/value memory contract.
    """
    try:
        try:
            from core.lancedb_handler import get_lancedb_handler

            lancedb = get_lancedb_handler(workspace_id)
            docs = lancedb.list_documents("documents", limit=10000)

            by_integration: Dict[str, int] = {}
            for doc in docs:
                integration = (doc.get("metadata") or {}).get(
                    "integration_id", "unknown")
                by_integration[integration] = (
                    by_integration.get(integration, 0) + 1)

            stats = {
                "total_entities": len(docs),
                "by_integration": by_integration,
                "by_entity_type": {},
                "last_updated": datetime.now().isoformat(),
            }
        except ImportError:
            stats = {
                "total_entities": 0,
                "by_integration": {},
                "by_entity_type": {},
                "last_updated": datetime.now().isoformat(),
                "error": "LanceDB not available",
            }

        return router.success_response(
            data=stats, message="Memory statistics retrieved")

    except Exception:
        logger.error("Failed to get memory stats")
        return router.success_response(
            data={
                "total_entities": 0,
                "by_integration": {},
                "by_entity_type": {},
                "error": "Failed to retrieve statistics",
            },
            message="Failed to retrieve statistics",
        )


@router.get("/search")
async def search_memory(
    q: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None,
):
    """Search only the caller's scoped memory entries."""
    results = _search_memory(
        db, actor=current_user, q=q, limit=limit, agent_id=agent_id)
    return router.success_response(
        data=results,
        metadata={"query": q, "count": len(results)},
    )


@router.get(
    "/context/{session_id}", response_model=ContextResponse,
    response_model_exclude_none=True)
async def get_context(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None,
):
    """Get context for a session in the caller's scope."""
    context = _read_context(
        db, actor=current_user, session_id=session_id, agent_id=agent_id)
    if context is None:
        return ContextResponse(
            session_id=session_id,
            context={},
            timestamp=datetime.now().isoformat(),
        )
    return ContextResponse(**context)


@router.post("/context/{session_id}")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="update_context",
    feature="memory",
)
async def update_context(
    session_id: str,
    context: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    """
    Merge context for a session in the caller's scope.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    """
    result = _update_context(
        db,
        actor=current_user,
        session_id=session_id,
        context=context,
        agent_id=agent_id,
        operation_id=operation_id,
    )
    _raise_memory_write(result)
    return router.success_response(
        data=result.get("data"), message="Context updated")


@router.post("", response_model=MemoryResponse)
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="store_memory",
    feature="memory",
)
async def store_memory(
    request: MemoryStoreRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    """
    Store a memory entry in the caller's scope.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    """
    result = _store_memory(
        db,
        actor=current_user,
        key=request.key,
        value=request.value,
        metadata=request.metadata,
        agent_id=agent_id,
        operation_id=operation_id,
    )
    _raise_memory_write(result)
    return MemoryResponse(**result["data"])


# Parameterized routes MUST come after static routes
@router.get(
    "/{key}", response_model=MemoryResponse,
    response_model_exclude_none=True)
async def retrieve_memory(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None,
):
    """Retrieve a memory entry by key in the caller's scope."""
    entry = _read_memory(
        db, actor=current_user, key=key, agent_id=agent_id)
    if entry is None:
        raise router.not_found_error("Memory key", key)
    return MemoryResponse(**entry)


@router.delete("/{key}")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="delete_memory",
    feature="memory",
)
async def delete_memory(
    key: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None,
    operation_id: Optional[str] = None,
):
    """
    Delete a memory entry in the caller's scope.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    """
    result = _delete_memory(
        db,
        actor=current_user,
        key=key,
        agent_id=agent_id,
        operation_id=operation_id,
    )
    _raise_memory_write(result)
    return router.success_response(
        data=result.get("data"),
        message=f"Memory key '{key}' deleted",
    )
