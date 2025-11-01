import logging
import sqlite3
from flask import Blueprint, jsonify, request
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import uuid

# Create blueprint
task_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

logger = logging.getLogger(__name__)

# Database configuration
SQLITE_DB_PATH = os.getenv(
    "DATABASE_URL", "sqlite:///./data/atom_development.db"
).replace("sqlite:///", "")

logger.info(f"Using database path: {SQLITE_DB_PATH}")


def get_db_connection():
    """Get SQLite database connection"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable dict-like access

        # Create tasks table if it doesn't exist
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        )
        table_exists = cursor.fetchone()
        logger.info(f"Tasks table exists: {bool(table_exists)}")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'medium',
                due_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted INTEGER DEFAULT 0
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)"
        )

        conn.commit()
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to SQLite database: {e}")
        return None


@task_bp.route("", methods=["GET"])
def get_tasks():
    """Get tasks for the authenticated user"""
    try:
        # In production, this would be extracted from JWT token
        user_id = request.args.get(
            "user_id", "11111111-1111-1111-1111-111111111111"
        )  # Demo user ID

        # Parse query parameters
        status = request.args.get("status")
        priority = request.args.get("priority")
        limit = int(request.args.get("limit", "50"))
        offset = int(request.args.get("offset", "0"))

        conn = get_db_connection()
        if not conn:
            return jsonify(
                {
                    "error": "Database connection not available",
                    "tasks": [],
                    "success": False,
                }
            ), 500

        cursor = conn.cursor()

        # Build base query
        query = """
            SELECT id, user_id, title, description, status, priority, due_date, created_at, updated_at
            FROM tasks
            WHERE user_id = ? AND deleted = 0
        """
        params = [user_id]

        # Add filters
        if status:
            query += " AND status = ?"
            params.append(status)

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        # Add sorting and pagination
        query += " ORDER BY created_at DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Debug logging
        logger.info(f"Query executed: {query}")
        logger.info(f"Params: {params}")
        logger.info(f"Rows fetched: {len(rows)}")

        # Check if tasks exist in database
        cursor.execute("SELECT COUNT(*) as count FROM tasks")
        total_tasks = cursor.fetchone()[0]
        logger.info(f"Total tasks in database: {total_tasks}")

        # Convert rows to dictionaries
        tasks = []
        for row in rows:
            task = dict(row)
            # Debug logging for each task
            logger.info(f"Task row: {dict(row)}")
            # Convert datetime objects to strings for JSON serialization
            if task.get("created_at"):
                task["created_at"] = task["created_at"]
            if task.get("updated_at"):
                task["updated_at"] = task["updated_at"]
            if task.get("due_date"):
                task["due_date"] = task["due_date"]
            tasks.append(task)

        conn.close()

        return jsonify({"tasks": tasks, "total": len(tasks), "success": True}), 200

    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return jsonify({"error": str(e), "tasks": [], "success": False}), 500


@task_bp.route("", methods=["POST"])
def create_task():
    """Create a new task"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided", "success": False}), 400

        # Required fields
        title = data.get("title")
        user_id = data.get(
            "user_id", "11111111-1111-1111-1111-111111111111"
        )  # Demo user ID

        if not title:
            return jsonify({"error": "Title is required", "success": False}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        cursor = conn.cursor()

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Optional fields
        description = data.get("description", "")
        status = data.get("status", "pending")
        priority = data.get("priority", "medium")
        due_date = data.get("due_date", None)

        # Insert task
        cursor.execute(
            """
            INSERT INTO tasks (id, user_id, title, description, status, priority, due_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
            (task_id, user_id, title, description, status, priority, due_date),
        )

        # Debug logging for task creation
        logger.info(f"Task created: id={task_id}, user_id={user_id}, title={title}")

        conn.commit()
        conn.close()

        return jsonify(
            {
                "task": {
                    "id": task_id,
                    "user_id": user_id,
                    "title": title,
                    "description": description,
                    "status": status,
                    "priority": priority,
                    "due_date": due_date,
                    "created_at": datetime.now().isoformat(),
                },
                "success": True,
            }
        ), 201

    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@task_bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    """Get a specific task by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, title, description, status, priority, due_date, created_at, updated_at
            FROM tasks
            WHERE id = ? AND deleted = 0
        """,
            (task_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Task not found", "success": False}), 404

        task = dict(row)
        # Convert datetime objects to strings for JSON serialization
        if task.get("created_at"):
            task["created_at"] = task["created_at"]
        if task.get("updated_at"):
            task["updated_at"] = task["updated_at"]
        if task.get("due_date"):
            task["due_date"] = task["due_date"]

        return jsonify({"task": task, "success": True}), 200

    except Exception as e:
        logger.error(f"Error fetching task: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@task_bp.route("/<task_id>", methods=["PUT"])
def update_task(task_id):
    """Update a task"""
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

        # Check if task exists
        cursor.execute("SELECT id FROM tasks WHERE id = ? AND deleted = 0", (task_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Task not found", "success": False}), 404

        # Build update query
        updates = []
        params = []

        if "title" in data:
            updates.append("title = ?")
            params.append(data["title"])

        if "description" in data:
            updates.append("description = ?")
            params.append(data["description"])

        if "status" in data:
            updates.append("status = ?")
            params.append(data["status"])

        if "priority" in data:
            updates.append("priority = ?")
            params.append(data["priority"])

        if "due_date" in data:
            updates.append("due_date = ?")
            params.append(data["due_date"])

        if not updates:
            conn.close()
            return jsonify({"error": "No fields to update", "success": False}), 400

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(task_id)

        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)

        conn.commit()
        conn.close()

        return jsonify({"message": "Task updated successfully", "success": True}), 200

    except Exception as e:
        logger.error(f"Error updating task: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@task_bp.route("/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    """Soft delete a task"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(
                {"error": "Database connection not available", "success": False}
            ), 500

        cursor = conn.cursor()

        # Check if task exists
        cursor.execute("SELECT id FROM tasks WHERE id = ? AND deleted = 0", (task_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Task not found", "success": False}), 404

        # Soft delete
        cursor.execute(
            "UPDATE tasks SET deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (task_id,),
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "Task deleted successfully", "success": True}), 200

    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return jsonify({"error": str(e), "success": False}), 500


@task_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for tasks service"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify(
                {
                    "service": "tasks",
                    "status": "unhealthy",
                    "message": "Database connection failed",
                    "success": False,
                }
            ), 500

        # Test database connection
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE deleted = 0")
        task_count = cursor.fetchone()[0]
        conn.close()

        return jsonify(
            {
                "service": "tasks",
                "status": "healthy",
                "task_count": task_count,
                "database": "sqlite",
                "success": True,
                "timestamp": datetime.now().isoformat(),
            }
        ), 200

    except Exception as e:
        logger.error(f"Tasks health check failed: {e}")
        return jsonify(
            {
                "service": "tasks",
                "status": "unhealthy",
                "error": str(e),
                "success": False,
                "timestamp": datetime.now().isoformat(),
            }
        ), 500
