import logging
import sqlite3
from flask import Blueprint, jsonify, request
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

# Create blueprint
message_bp = Blueprint("messages", __name__, url_prefix="/api/messages")

logger = logging.getLogger(__name__)

# Database configuration
SQLITE_DB_PATH = os.getenv(
    "DATABASE_URL", "sqlite:///./data/atom_development.db"
).replace("sqlite:///", "")


def get_db_connection():
    """Get SQLite database connection"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable dict-like access

        # Create messages table if it doesn't exist
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted INTEGER DEFAULT 0
            )
        """)
        conn.commit()

        return conn
    except Exception as e:
        logger.error(f"Failed to connect to SQLite database: {e}")
        return None


@message_bp.route("", methods=["GET"])
def get_messages():
    """Get messages from all platforms for the authenticated user"""
    try:
        # In production, this would be extracted from JWT token
        user_id = request.args.get(
            "user_id", "11111111-1111-1111-1111-111111111111"
        )  # Demo user ID

        # Parse query parameters
        platform = request.args.get("platform")
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        priority = request.args.get("priority")
        limit = int(request.args.get("limit", "50"))
        offset = int(request.args.get("offset", "0"))

        conn = get_db_connection()
        if not conn:
            return jsonify(
                {
                    "error": "Database connection not available",
                    "messages": [],
                    "success": False,
                }
            ), 500

        cursor = conn.cursor()

        # Build base query
        query = """
            SELECT id, user_id, content, message_type, created_at, updated_at
            FROM messages
            WHERE user_id = ? AND deleted = 0
        """
        params = [user_id]

        # Add filters
        if platform:
            query += " AND platform = ?"
            params.append(platform)

        if unread_only:
            query += " AND unread = 1"

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        # Add sorting and pagination
        query += " ORDER BY created_at DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert rows to dictionaries
        messages = []
        for row in rows:
            message = dict(row)
            # Convert datetime objects to strings for JSON serialization
            if message.get("created_at"):
                message["created_at"] = message["created_at"]
            if message.get("updated_at"):
                message["updated_at"] = message["updated_at"]
            messages.append(message)

        conn.close()

        return jsonify(
            {"messages": messages, "total": len(messages), "success": True}
        ), 200

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({"error": str(e), "messages": [], "success": False}), 500


@message_bp.route("", methods=["POST"])
def create_message():
    """Create a new message"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided", "success": False}), 400

        # Required fields
        content = data.get("content")
        user_id = data.get(
            "user_id", "11111111-1111-1111-1111-111111111111"
        )  # Demo user ID
        message_type = data.get("message_type", "text")

        if not content:
            return jsonify({"error": "Content is required", "success": False}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        cursor = conn.cursor()

        # Generate message ID
        import uuid

        message_id = str(uuid.uuid4())

        # Insert message
        cursor.execute(
            """
            INSERT INTO messages (id, user_id, content, message_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
            (message_id, user_id, content, message_type),
        )

        conn.commit()
        conn.close()

        return jsonify(
            {
                "message": {
                    "id": message_id,
                    "user_id": user_id,
                    "content": content,
                    "message_type": message_type,
                    "created_at": datetime.now().isoformat(),
                },
                "success": True,
            }
        ), 201

    except Exception as e:
        logger.error(f"Error creating message: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@message_bp.route("/<message_id>", methods=["GET"])
def get_message(message_id):
    """Get a specific message by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, content, message_type, created_at, updated_at
            FROM messages
            WHERE id = ? AND deleted = 0
        """,
            (message_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Message not found", "success": False}), 404

        message = dict(row)
        # Convert datetime objects to strings for JSON serialization
        if message.get("created_at"):
            message["created_at"] = message["created_at"]
        if message.get("updated_at"):
            message["updated_at"] = message["updated_at"]

        return jsonify({"message": message, "success": True}), 200

    except Exception as e:
        logger.error(f"Error fetching message: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@message_bp.route("/<message_id>", methods=["PUT"])
def update_message(message_id):
    """Update a message"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided", "success": False}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        cursor = conn.cursor()

        # Check if message exists
        cursor.execute(
            "SELECT id FROM messages WHERE id = ? AND deleted = 0", (message_id,)
        )
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Message not found", "success": False}), 404

        # Build update query
        updates = []
        params = []

        if "content" in data:
            updates.append("content = ?")
            params.append(data["content"])

        if "message_type" in data:
            updates.append("message_type = ?")
            params.append(data["message_type"])

        if not updates:
            conn.close()
            return jsonify({"error": "No fields to update", "success": False}), 400

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(message_id)

        query = f"UPDATE messages SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)

        conn.commit()
        conn.close()

        return jsonify(
            {"message": "Message updated successfully", "success": True}
        ), 200

    except Exception as e:
        logger.error(f"Error updating message: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@message_bp.route("/<message_id>", methods=["DELETE"])
def delete_message(message_id):
    """Soft delete a message"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        cursor = conn.cursor()

        # Check if message exists
        cursor.execute(
            "SELECT id FROM messages WHERE id = ? AND deleted = 0", (message_id,)
        )
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Message not found", "success": False}), 404

        # Soft delete
        cursor.execute(
            "UPDATE messages SET deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (message_id,),
        )

        conn.commit()
        conn.close()

        return jsonify(
            {"message": "Message deleted successfully", "success": True}
        ), 200

    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@message_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for messages service"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(
                {
                    "service": "messages",
                    "status": "unhealthy",
                    "message": "Database connection failed",
                    "success": False,
                }
            ), 500

        # Test database connection
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages WHERE deleted = 0")
        message_count = cursor.fetchone()[0]
        conn.close()

        return jsonify(
            {
                "service": "messages",
                "status": "healthy",
                "message_count": message_count,
                "database": "sqlite",
                "success": True,
                "timestamp": datetime.now().isoformat(),
            }
        ), 200

    except Exception as e:
        logger.error(f"Messages health check failed: {e}")
        return jsonify(
            {
                "service": "messages",
                "status": "unhealthy",
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat(),
            }
        ), 500
