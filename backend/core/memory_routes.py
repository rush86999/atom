"""
Memory Management API Routes for ATOM Platform
Provides LanceDB integration for conversation memory storage and retrieval
"""

import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

# Pydantic models
class MemoryStoreRequest(BaseModel):
    user_id: str
    conversation_id: str
    content: str
    content_type: str = "text"
    metadata: Dict[str, Any] = {}
    timestamp: Optional[str] = None

class MemorySearchRequest(BaseModel):
    user_id: str
    query: str
    limit: int = 10
    similarity_threshold: float = 0.7

class MemoryResponse(BaseModel):
    success: bool
    vector_id: Optional[str] = None
    message: str

class MemorySearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    count: int

# Global LanceDB handler instance
lancedb_handler = None

def get_lancedb_handler():
    """Get or create LanceDB handler instance"""
    global lancedb_handler
    if lancedb_handler is None:
        try:
            from core.lancedb_handler import LanceDBHandler
            # Initialize with database path from environment
            db_path = os.getenv('LANCEDB_PATH', './data/lancedb')
            lancedb_handler = LanceDBHandler(db_path=db_path)
            logger.info("LanceDB handler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB handler: {e}")
            raise HTTPException(
                status_code=500,
                detail="LanceDB not available"
            )
    return lancedb_handler

@router.post("/store")
async def store_memory(request: MemoryStoreRequest):
    """Store conversation memory in LanceDB"""
    try:
        handler = get_lancedb_handler()

        # Convert timestamp to datetime object
        timestamp = datetime.now()
        if request.timestamp:
            try:
                timestamp = datetime.fromisoformat(request.timestamp)
            except ValueError:
                timestamp = datetime.now()

        # Store in LanceDB
        vector_id = await handler.store_conversation_context(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            content=request.content,
            content_type=request.content_type,
            metadata=request.metadata,
            timestamp=timestamp
        )

        logger.info(f"Stored memory for user {request.user_id}, vector_id: {vector_id}")

        return MemoryResponse(
            success=True,
            vector_id=vector_id,
            message="Memory stored successfully"
        )

    except Exception as e:
        logger.error(f"Error storing memory: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store memory: {str(e)}"
        )

@router.post("/search")
async def search_memories(request: MemorySearchRequest):
    """Search conversation memories using semantic similarity"""
    try:
        handler = get_lancedb_handler()

        # Search in LanceDB
        results = await handler.search_conversation_context(
            user_id=request.user_id,
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold
        )

        logger.info(f"Search completed for user {request.user_id}, found {len(results)} results")

            return MemorySearchResponse(
            results=results,
            count=len(results)
        )

    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search memories: {str(e)}"
        )

@router.get("/user/{user_id}")
async def get_user_memories(user_id: str, limit: int = 50):
    """Get all memories for a specific user"""
    try:
        handler = get_lancedb_handler()

        # Retrieve user's conversation contexts
        memories = await handler.get_user_conversation_contexts(
            user_id=user_id,
            limit=limit
        )

        logger.info(f"Retrieved {len(memories)} memories for user {user_id}")

        return {
            "user_id": user_id,
            "memories": memories,
            "count": len(memories)
        }

    except Exception as e:
        logger.error(f"Error retrieving user memories: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve memories: {str(e)}"
        )

@router.get("/conversation/{conversation_id}")
async def get_conversation_memories(conversation_id: str):
    """Get all memories for a specific conversation"""
    try:
        handler = get_lancedb_handler()

        # Retrieve conversation memories
        memories = await handler.get_conversation_context(
            conversation_id=conversation_id
        )

        logger.info(f"Retrieved {len(memories)} memories for conversation {conversation_id}")

        return {
            "conversation_id": conversation_id,
            "memories": memories,
            "count": len(memories)
        }

    except Exception as e:
        logger.error(f"Error retrieving conversation memories: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation memories: {str(e)}"
        )

@router.delete("/{vector_id}")
async def delete_memory(vector_id: str):
    """Delete a specific memory by vector ID"""
    try:
        handler = get_lancedb_handler()

        # Delete memory from LanceDB
        success = await handler.delete_conversation_context(vector_id)

        if success:
            logger.info(f"Deleted memory with vector_id: {vector_id}")
            return MemoryResponse(
                success=True,
                message="Memory deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="Memory not found"
            )

    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete memory: {str(e)}"
        )

@router.get("/stats")
async def get_memory_stats():
    """Get memory statistics"""
    try:
        handler = get_lancedb_handler()

        # Get database statistics
        stats = await handler.get_database_stats()

        return {
            "database_path": handler.db_path,
            "total_conversations": stats.get("total_conversations", 0),
            "total_memories": stats.get("total_memories", 0),
            "unique_users": stats.get("unique_users", 0),
            "last_updated": datetime.now().isoformat(),
            "lancedb_available": True
        }

    except Exception as e:
        logger.error(f"Error retrieving memory stats: {e}")
        return {
            "database_path": "unknown",
            "total_conversations": 0,
            "total_memories": 0,
            "unique_users": 0,
            "last_updated": datetime.now().isoformat(),
            "lancedb_available": False,
            "error": str(e)
        }