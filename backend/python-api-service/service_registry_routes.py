from flask import Blueprint, jsonify
import logging

logger = logging.getLogger(__name__)

service_registry_bp = Blueprint("service_registry", __name__)

# Service registry data
SERVICE_REGISTRY = {
    "calendar": {
        "name": "Calendar",
        "status": "connected",
        "type": "integration",
        "description": "Google Calendar integration for event management",
        "capabilities": ["create_event", "find_availability", "list_events"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "tasks": {
        "name": "Task Management",
        "status": "connected",
        "type": "integration",
        "description": "Asana and Trello task management",
        "capabilities": ["create_task", "update_task", "list_tasks"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "email": {
        "name": "Email",
        "status": "connected",
        "type": "integration",
        "description": "Gmail email integration",
        "capabilities": ["send_email", "list_emails", "search_emails"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "slack": {
        "name": "Slack",
        "status": "connected",
        "type": "integration",
        "description": "Slack messaging integration",
        "capabilities": ["send_message", "list_channels", "search_messages"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "teams": {
        "name": "Microsoft Teams",
        "status": "connected",
        "type": "integration",
        "description": "Microsoft Teams integration",
        "capabilities": ["send_message", "list_channels"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "discord": {
        "name": "Discord",
        "status": "connected",
        "type": "integration",
        "description": "Discord messaging integration",
        "capabilities": ["send_message", "list_channels"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "notion": {
        "name": "Notion",
        "status": "connected",
        "type": "integration",
        "description": "Notion workspace integration",
        "capabilities": ["create_page", "update_page", "search_pages"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "dropbox": {
        "name": "Dropbox",
        "status": "connected",
        "type": "integration",
        "description": "Dropbox file storage integration",
        "capabilities": ["upload_file", "download_file", "list_files"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "gdrive": {
        "name": "Google Drive",
        "status": "connected",
        "type": "integration",
        "description": "Google Drive file storage integration",
        "capabilities": ["upload_file", "download_file", "list_files"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "github": {
        "name": "GitHub",
        "status": "connected",
        "type": "integration",
        "description": "GitHub repository integration",
        "capabilities": ["create_issue", "list_repos", "search_code"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "workflow": {
        "name": "Workflow Automation",
        "status": "active",
        "type": "core",
        "description": "Workflow automation engine with natural language processing",
        "capabilities": ["create_workflow", "execute_workflow", "schedule_workflow"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
    "notifications": {
        "name": "Notifications",
        "status": "active",
        "type": "core",
        "description": "Unified notification system",
        "capabilities": ["send_notification", "manage_preferences"],
        "health": "healthy",
        "last_checked": "2025-10-19T12:30:00Z",
    },
}


@service_registry_bp.route("/api/services", methods=["GET"])
def get_services():
    """Get all registered services and their status"""
    try:
        services_list = []

        for service_id, service_data in SERVICE_REGISTRY.items():
            service_info = {"id": service_id, **service_data}
            services_list.append(service_info)

        response = {
            "success": True,
            "services": services_list,
            "total_services": len(services_list),
            "active_services": len(
                [
                    s
                    for s in services_list
                    if s["status"] == "connected" or s["status"] == "active"
                ]
            ),
            "timestamp": "2025-10-19T12:30:00Z",
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting services: {str(e)}")
        return jsonify(
            {
                "success": False,
                "error": "Failed to retrieve services",
                "services": [],
                "total_services": 0,
                "active_services": 0,
            }
        ), 500


@service_registry_bp.route("/api/services/<service_id>", methods=["GET"])
def get_service(service_id):
    """Get specific service details"""
    try:
        if service_id not in SERVICE_REGISTRY:
            return jsonify(
                {"success": False, "error": f"Service '{service_id}' not found"}
            ), 404

        service_data = SERVICE_REGISTRY[service_id]
        response = {"success": True, "service": {"id": service_id, **service_data}}

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting service {service_id}: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to retrieve service {service_id}"}
        ), 500


@service_registry_bp.route("/api/services/health", methods=["GET"])
def get_services_health():
    """Get overall services health status"""
    try:
        services_list = []
        healthy_count = 0

        for service_id, service_data in SERVICE_REGISTRY.items():
            is_healthy = service_data["health"] == "healthy"
            if is_healthy:
                healthy_count += 1

            services_list.append(
                {
                    "id": service_id,
                    "name": service_data["name"],
                    "health": service_data["health"],
                    "status": service_data["status"],
                }
            )

        total_services = len(services_list)
        health_percentage = (
            (healthy_count / total_services) * 100 if total_services > 0 else 0
        )

        overall_health = (
            "healthy"
            if health_percentage >= 80
            else "degraded"
            if health_percentage >= 50
            else "unhealthy"
        )

        response = {
            "success": True,
            "overall_health": overall_health,
            "health_percentage": health_percentage,
            "healthy_services": healthy_count,
            "total_services": total_services,
            "services": services_list,
            "timestamp": "2025-10-19T12:30:00Z",
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting services health: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retrieve services health"}
        ), 500


@service_registry_bp.route("/api/services/status", methods=["GET"])
def get_services_status():
    """Get services status summary"""
    try:
        status_counts = {"connected": 0, "active": 0, "disconnected": 0, "error": 0}

        for service_data in SERVICE_REGISTRY.values():
            status = service_data["status"]
            if status in status_counts:
                status_counts[status] += 1

        response = {
            "success": True,
            "status_summary": status_counts,
            "total_services": len(SERVICE_REGISTRY),
            "timestamp": "2025-10-19T12:30:00Z",
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting services status: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retrieve services status"}
        ), 500
