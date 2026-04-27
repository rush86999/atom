"""
Memory Routes - API endpoints for memory storage and retrieval
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.base_routes import BaseAPIRouter
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/memory", tags=["Memory"])

# Pydantic Models
class MemoryStoreRequest(BaseModel):
    key: str = Field(..., description="Memory key")
    value: Any = Field(..., description="Memory value")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class MemoryResponse(BaseModel):
    key: str
    value: Any
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str

class ContextResponse(BaseModel):
    session_id: str
    context: Dict[str, Any]
    timestamp: str

# In-memory storage (would use LanceDB or Redis in production)
_memory_store: Dict[str, Dict[str, Any]] = {}
_context_store: Dict[str, Dict[str, Any]] = {}

# Static routes MUST come before parameterized routes
@router.get("/stats")
async def get_memory_stats(workspace_id: str = "default"):
    """
    Get memory statistics from LanceDB.

    Returns aggregated entity counts from all integrations,
    broken down by integration and entity type.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "total_entities": 12345,
            "by_integration": {
                "outlook": {"total": 123, "last_synced": "2026-04-26T10:00:00Z"},
                "gmail": {"total": 456, "last_synced": "2026-04-26T09:00:00Z"}
            },
            "by_entity_type": {
                "person": 234,
                "organization": 56,
                "task": 789
            }
        }
    }
    ```
    """
    try:
        # Try to get stats from LanceDB
        try:
            from core.lancedb_handler import get_lancedb_handler

            lancedb = get_lancedb_handler(workspace_id)

            # Query LanceDB for stats (implementation depends on LanceDBHandler)
            # For now, return placeholder stats
            stats = {
                "total_entities": 0,
                "by_integration": {},
                "by_entity_type": {},
                "last_updated": datetime.now().isoformat()
            }

            # TODO: Implement actual stats query
            # Example:
            # all_docs = lancedb.get_all_documents()
            # stats["total_entities"] = len(all_docs)
            # for doc in all_docs:
            #     integration = doc.metadata.get("integration", "unknown")
            #     stats["by_integration"][integration] = stats["by_integration"].get(integration, 0) + 1

        except ImportError:
            # LanceDB not available, return empty stats
            stats = {
                "total_entities": 0,
                "by_integration": {},
                "by_entity_type": {},
                "last_updated": datetime.now().isoformat(),
                "error": "LanceDB not available"
            }

        return router.success_response(
            data=stats,
            message="Memory statistics retrieved"
        )

    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        return router.success_response(
            data={
                "total_entities": 0,
                "by_integration": {},
                "by_entity_type": {},
                "error": str(e)
            },
            message="Failed to retrieve statistics"
        )

@router.get("/search")
async def search_memory(q: str, limit: int = 10):
    """Search memory entries"""
    results = []
    for key, entry in _memory_store.items():
        # Simple text search
        if q.lower() in str(entry.get("value", "")).lower():
            results.append(entry)
        if len(results) >= limit:
            break
    return router.success_response(
        data=results,
        metadata={"query": q, "count": len(results)}
    )

@router.get("/context/{session_id}", response_model=ContextResponse)
async def get_context(session_id: str):
    """Get context for a session"""
    context = _context_store.get(session_id, {})
    return ContextResponse(
        session_id=session_id,
        context=context,
        timestamp=datetime.now().isoformat()
    )

@router.post("/context/{session_id}")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="update_context",
    feature="memory"
)
async def update_context(
    session_id: str,
    context: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Update context for a session.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Context modification is a moderate action
    - Requires INTERN maturity or higher
    """
    _context_store[session_id] = {
        **_context_store.get(session_id, {}),
        **context,
        "_updated_at": datetime.now().isoformat()
    }
    logger.info(f"Context updated for session {session_id}")
    return router.success_response(
        data={"session_id": session_id},
        message="Context updated"
    )

@router.post("", response_model=MemoryResponse)
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="store_memory",
    feature="memory"
)
async def store_memory(
    request: MemoryStoreRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Store a memory entry.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Memory storage is a moderate action
    - Requires INTERN maturity or higher
    """
    try:
        entry = {
            "key": request.key,
            "value": request.value,
            "metadata": request.metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        _memory_store[request.key] = entry
        logger.info(f"Memory stored: {request.key}")
        return MemoryResponse(**entry)
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise router.internal_error(detail=str(e))

# Parameterized routes MUST come after static routes
@router.get("/{key}", response_model=MemoryResponse)
async def retrieve_memory(key: str):
    """Retrieve a memory entry by key"""
    if key not in _memory_store:
        raise router.not_found_error("Memory key", key)
    return MemoryResponse(**_memory_store[key])

@router.delete("/{key}")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="delete_memory",
    feature="memory"
)
async def delete_memory(
    key: str,
    request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Delete a memory entry.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Memory deletion is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    if key not in _memory_store:
        raise router.not_found_error("Memory key", key)

    del _memory_store[key]
    logger.info(f"Memory deleted: {key}")
    return router.success_response(message=f"Memory key '{key}' deleted")
