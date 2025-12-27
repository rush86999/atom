"""
Memory Routes - API endpoints for memory storage and retrieval
"""
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

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
async def update_context(session_id: str, context: Dict[str, Any]):
    """Update context for a session"""
    _context_store[session_id] = {
        **_context_store.get(session_id, {}),
        **context,
        "_updated_at": datetime.now().isoformat()
    }
    return {"message": "Context updated", "session_id": session_id}

@router.post("", response_model=MemoryResponse)
async def store_memory(request: MemoryStoreRequest):
    """Store a memory entry"""
    try:
        entry = {
            "key": request.key,
            "value": request.value,
            "metadata": request.metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        _memory_store[request.key] = entry
        return MemoryResponse(**entry)
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
async def delete_memory(key: str):
    """Delete a memory entry"""
    if key not in _memory_store:
        raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found")
    del _memory_store[key]
    return {"message": f"Memory key '{key}' deleted"}
