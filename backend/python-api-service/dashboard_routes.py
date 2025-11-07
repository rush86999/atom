from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import random

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/api/dashboard", methods=["GET"])
def get_dashboard_data():
    """Get dashboard data for the frontend"""

    # Mock data for demonstration - in production this would come from real services
    calendar_events = [
        {
            "id": "1",
            "title": "Team Standup",
            "start": datetime.now()
            .replace(hour=9, minute=0, second=0, microsecond=0)
            .isoformat(),
            "end": datetime.now()
            .replace(hour=9, minute=30, second=0, microsecond=0)
            .isoformat(),
            "description": "Daily team sync meeting",
            "location": "Conference Room A",
            "attendees": ["team@company.com"],
            "status": "confirmed",
        },
        {
            "id": "2",
            "title": "Client Meeting",
            "start": datetime.now()
            .replace(hour=14, minute=0, second=0, microsecond=0)
            .isoformat(),
            "end": datetime.now()
            .replace(hour=15, minute=0, second=0, microsecond=0)
            .isoformat(),
            "description": "Quarterly review with client",
            "location": "Zoom",
            "attendees": ["client@company.com"],
            "status": "confirmed",
        },
        {
            "id": "3",
            "title": "Project Planning",
            "start": datetime.now()
            .replace(hour=16, minute=0, second=0, microsecond=0)
            .isoformat(),
            "end": datetime.now()
            .replace(hour=17, minute=0, second=0, microsecond=0)
            .isoformat(),
            "description": "Next sprint planning session",
            "location": "Team Room",
            "attendees": ["dev-team@company.com"],
            "status": "tentative",
        },
    ]

    tasks = [
        {
            "id": "1",
            "title": "Complete project documentation",
            "description": "Write comprehensive documentation for the new feature",
            "dueDate": datetime.now()
            .replace(hour=23, minute=59, second=59, microsecond=0)
            .isoformat(),
            "priority": "high",
            "status": "todo",
            "project": "Atom Development",
            "tags": ["documentation", "feature"],
        },
        {
            "id": "2",
            "title": "Review pull requests",
            "description": "Review and merge pending pull requests",
            "dueDate": (datetime.now() + timedelta(days=1))
            .replace(hour=23, minute=59, second=59, microsecond=0)
            .isoformat(),
            "priority": "medium",
            "status": "todo",
            "project": "Atom Development",
            "tags": ["code-review", "merge"],
        },
        {
            "id": "3",
            "title": "Update dependencies",
            "description": "Update project dependencies to latest versions",
            "dueDate": (datetime.now() + timedelta(days=2))
            .replace(hour=23, minute=59, second=59, microsecond=0)
            .isoformat(),
            "priority": "low",
            "status": "in-progress",
            "project": "Atom Development",
            "tags": ["maintenance", "dependencies"],
        },
        {
            "id": "4",
            "title": "Write unit tests",
            "description": "Add unit tests for new workflow automation features",
            "dueDate": (datetime.now() - timedelta(days=1))
            .replace(hour=23, minute=59, second=59, microsecond=0)
            .isoformat(),
            "priority": "high",
            "status": "todo",
            "project": "Atom Development",
            "tags": ["testing", "quality"],
        },
        {
            "id": "5",
            "title": "Deploy to staging",
            "description": "Deploy latest changes to staging environment",
            "dueDate": datetime.now()
            .replace(hour=23, minute=59, second=59, microsecond=0)
            .isoformat(),
            "priority": "medium",
            "status": "completed",
            "project": "Atom Development",
            "tags": ["deployment", "staging"],
        },
    ]

    messages = [
        {
            "id": "1",
            "platform": "email",
            "from": "manager@company.com",
            "subject": "Project Update Required",
            "preview": "Please provide an update on the current project status by EOD",
            "timestamp": datetime.now()
            .replace(hour=8, minute=30, second=0, microsecond=0)
            .isoformat(),
            "unread": True,
            "priority": "high",
        },
        {
            "id": "2",
            "platform": "slack",
            "from": "Team Channel",
            "subject": "New messages in #general",
            "preview": "Team discussion about upcoming features and timeline",
            "timestamp": datetime.now()
            .replace(hour=7, minute=45, second=0, microsecond=0)
            .isoformat(),
            "unread": True,
            "priority": "normal",
        },
        {
            "id": "3",
            "platform": "teams",
            "from": "Dev Team",
            "subject": "Code Review Completed",
            "preview": "Your pull request has been reviewed and approved",
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "unread": False,
            "priority": "normal",
        },
        {
            "id": "4",
            "platform": "email",
            "from": "system@company.com",
            "subject": "Weekly Report Generated",
            "preview": "Your weekly activity report is now available for review",
            "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(),
            "unread": False,
            "priority": "low",
        },
        {
            "id": "5",
            "platform": "discord",
            "from": "Community Server",
            "subject": "New Announcement",
            "preview": "Important update about the community guidelines",
            "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(),
            "unread": False,
            "priority": "low",
        },
    ]

    # Calculate stats
    upcoming_events = len(
        [
            e
            for e in calendar_events
            if datetime.fromisoformat(e["start"]).date() == datetime.now().date()
        ]
    )
    overdue_tasks = len(
        [
            t
            for t in tasks
            if t["status"] != "completed"
            and datetime.fromisoformat(t["dueDate"]) < datetime.now()
        ]
    )
    unread_messages = len([m for m in messages if m["unread"]])
    completed_tasks = len([t for t in tasks if t["status"] == "completed"])

    dashboard_data = {
        "calendar": calendar_events,
        "tasks": tasks,
        "messages": messages,
        "stats": {
            "upcomingEvents": upcoming_events,
            "overdueTasks": overdue_tasks,
            "unreadMessages": unread_messages,
            "completedTasks": completed_tasks,
        },
        "serviceStatus": {
            "calendar": "connected",
            "tasks": "connected",
            "email": "connected",
            "slack": "connected",
            "teams": "connected",
            "discord": "connected",
            "workflow": "active",
            "notifications": "active",
            "figma": "connected",
            "shopify": "connected",
        },
        "lastUpdated": datetime.now().isoformat(),
    }

    return jsonify(dashboard_data)


@dashboard_bp.route("/api/dashboard-dev", methods=["GET"])
def get_dashboard_dev_data():
    """Development dashboard endpoint for frontend testing"""
    return get_dashboard_data()


@dashboard_bp.route("/api/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    """Get dashboard statistics only"""
    dashboard_data = get_dashboard_data()
    return jsonify(dashboard_data.get_json()["stats"])


@dashboard_bp.route("/api/dashboard/calendar", methods=["GET"])
def get_calendar_events():
    """Get calendar events only"""
    dashboard_data = get_dashboard_data()
    return jsonify(dashboard_data.get_json()["calendar"])


@dashboard_bp.route("/api/dashboard/tasks", methods=["GET"])
def get_tasks():
    """Get tasks only"""
    dashboard_data = get_dashboard_data()
    return jsonify(dashboard_data.get_json()["tasks"])


@dashboard_bp.route("/api/dashboard/messages", methods=["GET"])
def get_messages():
    """Get messages only"""
    dashboard_data = get_dashboard_data()
    return jsonify(dashboard_data.get_json()["messages"])
