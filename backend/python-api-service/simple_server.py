import os
import logging
from flask import Flask, jsonify, request
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_simple_app():
    """
    Simple Flask application for Atom API service
    Bypasses problematic imports and provides basic functionality
    """
    app = Flask(__name__)

    # Basic configuration
    app.secret_key = os.getenv(
        "FLASK_SECRET_KEY", "dev-secret-key-change-in-production"
    )

    # Health check endpoint
    @app.route("/healthz")
    def healthz():
        return jsonify(
            {
                "status": "ok",
                "service": "atom-python-api-simple",
                "database": "not_configured",
                "real_services": False,
                "message": "Simple server running - database features disabled",
                "version": "1.0.0",
            }
        )

    # Unified dashboard endpoint with mock data
    @app.route("/api/dashboard")
    def dashboard():
        """Mock dashboard data"""
        try:
            # Get current date range for events (next 7 days)
            now = datetime.now()
            start_date = now
            end_date = now + timedelta(days=7)

            dashboard_data = {
                "calendar": _get_mock_calendar_events(start_date, end_date),
                "tasks": _get_mock_tasks(),
                "messages": _get_mock_messages(),
                "stats": _get_mock_dashboard_stats(),
            }

            return jsonify(dashboard_data)

        except Exception as e:
            logger.error(f"Error in dashboard endpoint: {e}")
            return jsonify(
                {"error": "Failed to fetch dashboard data", "details": str(e)}
            ), 500

    def _get_mock_calendar_events(start_date, end_date):
        """Get mock calendar events"""
        return [
            {
                "id": "1",
                "title": "Team Meeting",
                "start": start_date.isoformat() + "Z",
                "end": (start_date + timedelta(hours=1)).isoformat() + "Z",
                "status": "scheduled",
                "provider": "mock",
                "location": "Conference Room A",
            },
            {
                "id": "2",
                "title": "Project Review",
                "start": (start_date + timedelta(days=1)).isoformat() + "Z",
                "end": (start_date + timedelta(days=1, hours=2)).isoformat() + "Z",
                "status": "confirmed",
                "provider": "mock",
                "location": "Virtual",
            },
        ]

    def _get_mock_tasks():
        """Get mock tasks"""
        return [
            {
                "id": "1",
                "title": "Complete project documentation",
                "dueDate": (datetime.now() + timedelta(days=1)).isoformat() + "Z",
                "priority": "high",
                "status": "todo",
                "project": "Atom Development",
            },
            {
                "id": "2",
                "title": "Review pull requests",
                "dueDate": (datetime.now() + timedelta(days=2)).isoformat() + "Z",
                "priority": "medium",
                "status": "in-progress",
                "project": "Atom Development",
            },
        ]

    def _get_mock_messages():
        """Get mock messages"""
        return [
            {
                "id": "1",
                "platform": "email",
                "from": "team@example.com",
                "subject": "Weekly Update",
                "preview": "Here's this week's progress report...",
                "timestamp": datetime.now().isoformat() + "Z",
                "unread": True,
                "priority": "normal",
            },
            {
                "id": "2",
                "platform": "slack",
                "from": "@product-team",
                "subject": "Design Review",
                "preview": "Can you review the latest designs?",
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat() + "Z",
                "unread": False,
                "priority": "high",
            },
        ]

    def _get_mock_dashboard_stats():
        """Get mock dashboard statistics"""
        return {
            "upcomingEvents": 2,
            "overdueTasks": 0,
            "unreadMessages": 1,
            "completedTasks": 5,
            "totalTasks": 7,
        }

    # Calendar endpoints
    @app.route("/api/calendar/events")
    def calendar_events():
        """Get calendar events"""
        start_date = request.args.get("start", datetime.now().isoformat())
        end_date = request.args.get(
            "end", (datetime.now() + timedelta(days=7)).isoformat()
        )

        return jsonify(
            _get_mock_calendar_events(
                datetime.fromisoformat(start_date.replace("Z", "+00:00")),
                datetime.fromisoformat(end_date.replace("Z", "+00:00")),
            )
        )

    # Task endpoints
    @app.route("/api/tasks")
    def tasks():
        """Get tasks"""
        return jsonify(_get_mock_tasks())

    @app.route("/api/tasks", methods=["POST"])
    def create_task():
        """Create a new task"""
        try:
            data = request.get_json()
            return jsonify(
                {
                    "success": True,
                    "message": "Task created (mock)",
                    "task": {"id": str(len(_get_mock_tasks()) + 1), **data},
                }
            )
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    # Message endpoints
    @app.route("/api/messages")
    def messages():
        """Get messages"""
        return jsonify(_get_mock_messages())

    # Integration status endpoints
    @app.route("/api/integrations/status")
    def integrations_status():
        """Get status of all integrations"""
        return jsonify(
            {
                "google": {"connected": False, "status": "mock_mode"},
                "outlook": {"connected": False, "status": "mock_mode"},
                "slack": {"connected": False, "status": "mock_mode"},
                "notion": {"connected": False, "status": "mock_mode"},
                "trello": {"connected": False, "status": "mock_mode"},
                "asana": {"connected": False, "status": "mock_mode"},
                "github": {"connected": False, "status": "mock_mode"},
                "dropbox": {"connected": False, "status": "mock_mode"},
            }
        )

    # Root endpoint
    @app.route("/")
    def root():
        return jsonify(
            {
                "service": "Atom Python API (Simple)",
                "version": "1.0.0",
                "status": "running",
                "mode": "mock_data",
                "endpoints": {
                    "dashboard": "/api/dashboard",
                    "calendar": "/api/calendar/events",
                    "tasks": "/api/tasks",
                    "messages": "/api/messages",
                    "integrations": "/api/integrations/status",
                    "health": "/healthz",
                },
            }
        )

    logger.info("Simple Atom API app created with mock data")
    return app


if __name__ == "__main__":
    app = create_simple_app()
    port = int(os.environ.get("PYTHON_API_PORT", 5059))
    logger.info(f"Starting simple Atom API server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
