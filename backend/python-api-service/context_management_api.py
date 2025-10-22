import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List, Any, Optional
import uuid
from datetime import datetime

from context_management_service import context_management_service

# Create blueprint
context_management_api_bp = Blueprint(
    "context_management_api", __name__, url_prefix="/api/context"
)

logger = logging.getLogger(__name__)


@context_management_api_bp.route("/preferences", methods=["GET"])
def get_user_preferences():
    """Get user preferences"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "user_id is required"}), 400

        preferences = context_management_service.get_user_preferences(user_id)

        return jsonify(
            {
                "success": True,
                "preferences": preferences,
                "user_id": user_id,
            }
        )

    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/preferences", methods=["POST"])
def save_user_preferences():
    """Save or update user preferences"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        user_id = data.get("user_id")
        preferences = data.get("preferences", {})

        if not user_id:
            return jsonify({"success": False, "error": "user_id is required"}), 400

        success = context_management_service.save_user_preferences(user_id, preferences)

        return jsonify(
            {
                "success": success,
                "message": "Preferences saved successfully"
                if success
                else "Failed to save preferences",
                "user_id": user_id,
            }
        )

    except Exception as e:
        logger.error(f"Error saving user preferences: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/conversation/history", methods=["GET"])
def get_conversation_history():
    """Get conversation history for a user"""
    try:
        user_id = request.args.get("user_id")
        session_id = request.args.get("session_id")
        limit = int(request.args.get("limit", 50))

        if not user_id:
            return jsonify({"success": False, "error": "user_id is required"}), 400

        history = context_management_service.get_conversation_history(
            user_id, session_id, limit
        )

        return jsonify(
            {
                "success": True,
                "history": history,
                "user_id": user_id,
                "session_id": session_id,
                "count": len(history),
            }
        )

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/conversation/message", methods=["POST"])
def add_conversation_message():
    """Add a message to conversation history"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        user_id = data.get("user_id")
        session_id = data.get("session_id")
        role = data.get("role")
        content = data.get("content")

        if not all([user_id, session_id, role, content]):
            return jsonify(
                {
                    "success": False,
                    "error": "user_id, session_id, role, and content are required",
                }
            ), 400

        success = context_management_service.add_conversation_message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            message_type=data.get("message_type", "text"),
            metadata=data.get("metadata"),
        )

        return jsonify(
            {
                "success": success,
                "message": "Message added to history"
                if success
                else "Failed to add message",
                "user_id": user_id,
                "session_id": session_id,
            }
        )

    except Exception as e:
        logger.error(f"Error adding conversation message: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/conversation/history", methods=["DELETE"])
def clear_conversation_history():
    """Clear conversation history for a user"""
    try:
        user_id = request.args.get("user_id")
        session_id = request.args.get("session_id")

        if not user_id:
            return jsonify({"success": False, "error": "user_id is required"}), 400

        success = context_management_service.clear_conversation_history(
            user_id, session_id
        )

        return jsonify(
            {
                "success": success,
                "message": "History cleared successfully"
                if success
                else "Failed to clear history",
                "user_id": user_id,
                "session_id": session_id,
            }
        )

    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/chat-context", methods=["GET"])
def get_chat_context():
    """Get chat context for a user"""
    try:
        user_id = request.args.get("user_id")
        session_id = request.args.get("session_id", str(uuid.uuid4()))

        if not user_id:
            return jsonify({"success": False, "error": "user_id is required"}), 400

        context = context_management_service.get_or_create_chat_context(
            user_id, session_id
        )

        return jsonify(
            {
                "success": True,
                "context": context,
                "user_id": user_id,
                "session_id": session_id,
            }
        )

    except Exception as e:
        logger.error(f"Error getting chat context: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/chat-context", methods=["POST"])
def update_chat_context():
    """Update chat context for a user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        user_id = data.get("user_id")
        session_id = data.get("session_id")
        active_workflows = data.get("active_workflows", [])
        context_data = data.get("context_data", {})

        if not all([user_id, session_id]):
            return jsonify(
                {"success": False, "error": "user_id and session_id are required"}
            ), 400

        success = context_management_service.update_chat_context(
            user_id, session_id, active_workflows, context_data
        )

        return jsonify(
            {
                "success": success,
                "message": "Context updated successfully"
                if success
                else "Failed to update context",
                "user_id": user_id,
                "session_id": session_id,
            }
        )

    except Exception as e:
        logger.error(f"Error updating chat context: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/suggestions", methods=["GET"])
def get_workflow_suggestions():
    """Get context-aware workflow suggestions"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "user_id is required"}), 400

        suggestions = context_management_service.get_context_aware_workflow_suggestions(
            user_id
        )

        return jsonify(
            {
                "success": True,
                "suggestions": suggestions,
                "user_id": user_id,
                "count": len(suggestions),
            }
        )

    except Exception as e:
        logger.error(f"Error getting workflow suggestions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/summary", methods=["GET"])
def get_user_context_summary():
    """Get comprehensive user context summary"""
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "user_id is required"}), 400

        summary = context_management_service.get_user_context_summary(user_id)

        return jsonify(
            {
                "success": True,
                "summary": summary,
                "user_id": user_id,
            }
        )

    except Exception as e:
        logger.error(f"Error getting user context summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@context_management_api_bp.route("/health", methods=["GET"])
def context_management_health():
    """Health check for context management system"""
    try:
        # Test basic functionality
        test_user_id = "health_check_user"
        preferences = context_management_service.get_user_preferences(test_user_id)
        history = context_management_service.get_conversation_history(test_user_id)

        return jsonify(
            {
                "success": True,
                "status": "healthy",
                "service": "context-management",
                "test_user_preferences": bool(preferences),
                "test_user_history_count": len(history),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Context management health check failed: {e}")
        return jsonify({"success": False, "status": "unhealthy", "error": str(e)}), 500
