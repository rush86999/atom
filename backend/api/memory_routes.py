"""
Memory Routes - API endpoints for memory storage and retrieval
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# Governance feature flags
MEMORY_GOVERNANCE_ENABLED = os.getenv("MEMORY_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

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
    return {"query": q, "results": results, "count": len(results)}

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
async def update_context(session_id: str, context: Dict[str, Any], agent_id: Optional[str] = None):
    """
    Update context for a session.

    **Governance**: Requires INTERN+ maturity for context modification.
    """
    # Governance check for context modification
    if MEMORY_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="update_context",
                resource_type="memory_context",
                complexity=2  # MODERATE - context modification
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for update_context by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    _context_store[session_id] = {
        **_context_store.get(session_id, {}),
        **context,
        "_updated_at": datetime.now().isoformat()
    }
    logger.info(f"Context updated for session {session_id} by agent {agent_id or 'system'}")
    return {"message": "Context updated", "session_id": session_id}

@router.post("", response_model=MemoryResponse)
async def store_memory(request: MemoryStoreRequest, agent_id: Optional[str] = None):
    """
    Store a memory entry.

    **Governance**: Requires INTERN+ maturity for memory storage.
    """
    # Governance check for memory storage
    if MEMORY_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="store_memory",
                resource_type="memory",
                complexity=2  # MODERATE - data storage
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for store_memory by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    try:
        entry = {
            "key": request.key,
            "value": request.value,
            "metadata": request.metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        _memory_store[request.key] = entry
        logger.info(f"Memory stored: {request.key} by agent {agent_id or 'system'}")
        return MemoryResponse(**entry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Parameterized routes MUST come after static routes
@router.get("/{key}", response_model=MemoryResponse)
async def retrieve_memory(key: str):
    """Retrieve a memory entry by key"""
    if key not in _memory_store:
        raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found")
    return MemoryResponse(**_memory_store[key])

@router.delete("/{key}")
async def delete_memory(key: str, agent_id: Optional[str] = None):
    """
    Delete a memory entry.

    **Governance**: Requires SUPERVISED+ maturity for memory deletion.
    """
    # Governance check for memory deletion
    if MEMORY_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="delete_memory",
                resource_type="memory",
                complexity=3  # HIGH - data deletion
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for delete_memory by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    if key not in _memory_store:
        raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found")

    del _memory_store[key]
    logger.info(f"Memory deleted: {key} by agent {agent_id or 'system'}")
    return {"message": f"Memory key '{key}' deleted"}
