"""
Chat Memory API Routes for ATOM Backend

Provides REST API endpoints for chat memory operations including:
- Storing conversation memories
- Retrieving memory context
- Managing short-term and long-term memory
- Memory statistics and management
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from .chat_memory_service import ChatMemoryService, ConversationMemory, MemoryContext

# Initialize blueprint and service
chat_memory_bp = Blueprint("chat_memory", __name__)
memory_service = ChatMemoryService()

logger = logging.getLogger(__name__)


@chat_memory_bp.route("/api/chat/memory/store", methods=["POST"])
async def store_conversation_memory():
    """
    Store a conversation memory

    Request body:
    {
        "user_id": "user123",
        "session_id": "session456",
        "role": "user|assistant|system",
        "content": "The message content",
        "message_type": "text|voice|command",
        "metadata": {
            "workflow_id": "wf_123",
            "intent": "schedule_meeting",
            "sentiment": 0.8,
            "entities": ["meeting", "tomorrow"]
        }
    }
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["user_id", "session_id", "role", "content"]
        for field in required_fields:
            if field not in data:
                return jsonify(
                    {"status": "error", "message": f"Missing required field: {field}"}
                ), 400

        # Create conversation memory
        memory = ConversationMemory(
            user_id=data["user_id"],
            session_id=data["session_id"],
            role=data["role"],
            content=data["content"],
            message_type=data.get("message_type", "text"),
            metadata=data.get("metadata", {}),
        )

        # Store memory
        result = await memory_service.store_conversation(memory)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error storing conversation memory: {e}")
        return jsonify(
            {
                "status": "error",
                "message": f"Failed to store conversation memory: {str(e)}",
            }
        ), 500


@chat_memory_bp.route("/api/chat/memory/context", methods=["POST"])
async def get_memory_context():
    """
    Get memory context for chat response generation

    Request body:
    {
        "user_id": "user123",
        "session_id": "session456",
        "current_message": "What meetings do I have tomorrow?",
        "context_window": 10
    }
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["user_id", "session_id", "current_message"]
        for field in required_fields:
            if field not in data:
                return jsonify(
                    {"status": "error", "message": f"Missing required field: {field}"}
                ), 400

        # Get memory context
        context_window = data.get("context_window", 10)
        memory_context = await memory_service.get_memory_context(
            user_id=data["user_id"],
            session_id=data["session_id"],
            current_message=data["current_message"],
            context_window=context_window,
        )

        return jsonify({"status": "success", "context": memory_context.to_dict()})

    except Exception as e:
        logger.error(f"Error getting memory context: {e}")
        return jsonify(
            {"status": "error", "message": f"Failed to get memory context: {str(e)}"}
        ), 500


@chat_memory_bp.route("/api/chat/memory/history", methods=["GET"])
async def get_conversation_history():
    """
    Get conversation history for user/session

    Query parameters:
    - user_id (required): User identifier
    - session_id (optional): Session identifier
    - limit (optional): Maximum number of memories (default: 50)
    """
    try:
        user_id = request.args.get("user_id")
        session_id = request.args.get("session_id")
        limit = int(request.args.get("limit", 50))

        if not user_id:
            return jsonify(
                {"status": "error", "message": "user_id parameter is required"}
            ), 400

        # Get conversation history
        memories = await memory_service.get_conversation_history(
            user_id=user_id, session_id=session_id, limit=limit
        )

        return jsonify(
            {
                "status": "success",
                "memories": [memory.to_dict() for memory in memories],
                "count": len(memories),
            }
        )

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return jsonify(
            {
                "status": "error",
                "message": f"Failed to get conversation history: {str(e)}",
            }
        ), 500


@chat_memory_bp.route("/api/chat/memory/session/<session_id>", methods=["DELETE"])
async def clear_session_memory(session_id: str):
    """
    Clear short-term memory for a session

    Path parameters:
    - session_id: Session identifier to clear
    """
    try:
        result = await memory_service.clear_session_memory(session_id)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error clearing session memory: {e}")
        return jsonify(
            {"status": "error", "message": f"Failed to clear session memory: {str(e)}"}
        ), 500


@chat_memory_bp.route("/api/chat/memory/stats", methods=["GET"])
async def get_memory_stats():
    """
    Get memory statistics

    Query parameters:
    - user_id (optional): User identifier for user-specific stats
    """
    try:
        user_id = request.args.get("user_id")
        stats = memory_service.get_memory_stats(user_id)
        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        return jsonify(
            {"status": "error", "message": f"Failed to get memory stats: {str(e)}"}
        ), 500


@chat_memory_bp.route("/api/chat/memory/health", methods=["GET"])
async def memory_health_check():
    """
    Health check for memory service
    """
    try:
        stats = memory_service.get_memory_stats()

        health_status = {
            "service": "chat_memory",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "features": {
                "short_term_memory": True,
                "long_term_memory": stats.get("lancedb_available", False),
                "user_patterns": True,
                "context_retrieval": True,
            },
        }

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return jsonify(
            {
                "service": "chat_memory",
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }
        ), 500


@chat_memory_bp.route("/api/chat/memory/batch-store", methods=["POST"])
async def batch_store_memories():
    """
    Store multiple conversation memories in batch

    Request body:
    {
        "memories": [
            {
                "user_id": "user123",
                "session_id": "session456",
                "role": "user",
                "content": "Message 1",
                "metadata": {...}
            },
            {
                "user_id": "user123",
                "session_id": "session456",
                "role": "assistant",
                "content": "Response 1",
                "metadata": {...}
            }
        ]
    }
    """
    try:
        data = request.get_json()

        if "memories" not in data or not isinstance(data["memories"], list):
            return jsonify(
                {"status": "error", "message": "memories array is required"}
            ), 400

        results = []
        for memory_data in data["memories"]:
            try:
                # Validate required fields
                required_fields = ["user_id", "session_id", "role", "content"]
                for field in required_fields:
                    if field not in memory_data:
                        results.append(
                            {
                                "status": "error",
                                "message": f"Missing required field: {field}",
                                "memory_data": memory_data,
                            }
                        )
                        continue

                # Create and store memory
                memory = ConversationMemory(
                    user_id=memory_data["user_id"],
                    session_id=memory_data["session_id"],
                    role=memory_data["role"],
                    content=memory_data["content"],
                    message_type=memory_data.get("message_type", "text"),
                    metadata=memory_data.get("metadata", {}),
                )

                result = await memory_service.store_conversation(memory)
                results.append(result)

            except Exception as e:
                results.append(
                    {"status": "error", "message": str(e), "memory_data": memory_data}
                )

        # Count successes and failures
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = len(results) - success_count

        return jsonify(
            {
                "status": "success",
                "results": results,
                "summary": {
                    "total": len(results),
                    "successful": success_count,
                    "failed": error_count,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error in batch store memories: {e}")
        return jsonify(
            {"status": "error", "message": f"Failed to batch store memories: {str(e)}"}
        ), 500


@chat_memory_bp.route("/api/chat/memory/search", methods=["POST"])
async def search_memories():
    """
    Search memories by content similarity

    Request body:
    {
        "user_id": "user123",
        "query": "search query",
        "limit": 10,
        "similarity_threshold": 0.6
    }
    """
    try:
        data = request.get_json()

        if "user_id" not in data or "query" not in data:
            return jsonify(
                {"status": "error", "message": "user_id and query are required"}
            ), 400

        # Search long-term memories
        memories = await memory_service._search_long_term_memories(
            user_id=data["user_id"], query=data["query"]
        )

        # Apply limit
        limit = data.get("limit", 10)
        memories = memories[:limit]

        return jsonify(
            {
                "status": "success",
                "memories": [memory.to_dict() for memory in memories],
                "count": len(memories),
            }
        )

    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        return jsonify(
            {"status": "error", "message": f"Failed to search memories: {str(e)}"}
        ), 500


# Register the blueprint in your main Flask app
def register_chat_memory_routes(app):
    """Register chat memory routes with the Flask application"""
    app.register_blueprint(chat_memory_bp)
    logger.info("Chat memory routes registered")
