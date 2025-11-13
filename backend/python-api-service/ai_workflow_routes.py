#!/usr/bin/env python3
"""
🚀 AI WORKFLOW ENHANCEMENT ROUTES
API endpoints for AI-powered workflow automation and cross-service intelligence
"""

import asyncio
import json
import logging
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

# Import the AI workflow enhancement system
try:
    from ai_workflow_enhancement_system import (
        AIWorkflowEnhancementSystem,
        CrossServiceWorkflow,
    )

    AI_WORKFLOW_AVAILABLE = True
except ImportError as e:
    AI_WORKFLOW_AVAILABLE = False
    logging.warning(f"AI Workflow Enhancement System not available: {e}")

# Create blueprint for AI workflow routes
ai_workflow_routes = Blueprint("ai_workflow_routes", __name__)

# Global instance of the AI workflow system
ai_workflow_system = None


def get_ai_workflow_system():
    """Get or initialize the AI workflow system"""
    global ai_workflow_system
    if ai_workflow_system is None and AI_WORKFLOW_AVAILABLE:
        ai_workflow_system = AIWorkflowEnhancementSystem()
        # Initialize asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ai_workflow_system.initialize())
    return ai_workflow_system


@ai_workflow_routes.route("/api/v2/ai-workflows/status", methods=["GET"])
def get_ai_workflow_status():
    """Get status of AI workflow enhancement system"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "available": False,
                    "message": "AI Workflow Enhancement System not available",
                }
            ), 503

        return jsonify(
            {
                "success": True,
                "available": True,
                "initialized": system.initialized,
                "workflow_count": len(system.workflows),
                "service_connections": len(system.service_connections),
                "system_status": "active" if system.initialized else "initializing",
            }
        )

    except Exception as e:
        logging.error(f"Error getting AI workflow status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows", methods=["GET"])
def list_ai_workflows():
    """List all AI-enhanced workflows"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        workflows = []
        for workflow_id, workflow in system.workflows.items():
            workflow_data = workflow.__dict__
            # Add AI prediction if available
            if workflow_id in system.ai_predictions:
                workflow_data["ai_prediction"] = system.ai_predictions[
                    workflow_id
                ].__dict__

            workflows.append(workflow_data)

        return jsonify(
            {"success": True, "workflows": workflows, "total_count": len(workflows)}
        )

    except Exception as e:
        logging.error(f"Error listing AI workflows: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows", methods=["POST"])
def create_ai_workflow():
    """Create a new AI-enhanced cross-service workflow"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        # Validate required fields
        required_fields = ["name", "trigger_service", "action_services"]
        for field in required_fields:
            if field not in data:
                return jsonify(
                    {"success": False, "error": f"Missing required field: {field}"}
                ), 400

        # Create workflow asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(system.create_cross_service_workflow(data))

        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 400

    except Exception as e:
        logging.error(f"Error creating AI workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows/<workflow_id>", methods=["GET"])
def get_ai_workflow(workflow_id):
    """Get details of a specific AI-enhanced workflow"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        if workflow_id not in system.workflows:
            return jsonify({"success": False, "error": "Workflow not found"}), 404

        workflow = system.workflows[workflow_id]
        workflow_data = workflow.__dict__

        # Add AI prediction if available
        if workflow_id in system.ai_predictions:
            workflow_data["ai_prediction"] = system.ai_predictions[workflow_id].__dict__

        # Add performance metrics if available
        if workflow_id in system.performance_metrics:
            workflow_data["performance_metrics"] = system.performance_metrics[
                workflow_id
            ][-10:]  # Last 10 executions

        return jsonify({"success": True, "workflow": workflow_data})

    except Exception as e:
        logging.error(f"Error getting AI workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route(
    "/api/v2/ai-workflows/<workflow_id>/execute", methods=["POST"]
)
def execute_ai_workflow(workflow_id):
    """Execute a specific AI-enhanced workflow"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        data = request.get_json() or {}

        # Execute workflow asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(system.execute_workflow(workflow_id, data))

        return jsonify(result)

    except Exception as e:
        logging.error(f"Error executing AI workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows/<workflow_id>/enable", methods=["POST"])
def enable_ai_workflow(workflow_id):
    """Enable a specific AI-enhanced workflow"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        if workflow_id not in system.workflows:
            return jsonify({"success": False, "error": "Workflow not found"}), 404

        system.workflows[workflow_id].enabled = True

        return jsonify(
            {
                "success": True,
                "message": f"Workflow {workflow_id} enabled",
                "workflow_id": workflow_id,
                "enabled": True,
            }
        )

    except Exception as e:
        logging.error(f"Error enabling AI workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route(
    "/api/v2/ai-workflows/<workflow_id>/disable", methods=["POST"]
)
def disable_ai_workflow(workflow_id):
    """Disable a specific AI-enhanced workflow"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        if workflow_id not in system.workflows:
            return jsonify({"success": False, "error": "Workflow not found"}), 404

        system.workflows[workflow_id].enabled = False

        return jsonify(
            {
                "success": True,
                "message": f"Workflow {workflow_id} disabled",
                "workflow_id": workflow_id,
                "enabled": False,
            }
        )

    except Exception as e:
        logging.error(f"Error disabling AI workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows/<workflow_id>", methods=["DELETE"])
def delete_ai_workflow(workflow_id):
    """Delete a specific AI-enhanced workflow"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        if workflow_id not in system.workflows:
            return jsonify({"success": False, "error": "Workflow not found"}), 404

        workflow_name = system.workflows[workflow_id].name
        del system.workflows[workflow_id]

        # Also remove associated AI predictions and metrics
        if workflow_id in system.ai_predictions:
            del system.ai_predictions[workflow_id]
        if workflow_id in system.performance_metrics:
            del system.performance_metrics[workflow_id]

        return jsonify(
            {
                "success": True,
                "message": f'Workflow "{workflow_name}" deleted',
                "workflow_id": workflow_id,
            }
        )

    except Exception as e:
        logging.error(f"Error deleting AI workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows/services/status", methods=["GET"])
def get_service_status():
    """Get status of all connected services"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        service_status = {}
        for service_name, service_info in system.service_connections.items():
            service_status[service_name] = {
                "connected": service_info.get("connected", False),
                "type": service_info.get("type", "unknown").value
                if hasattr(service_info.get("type"), "value")
                else str(service_info.get("type")),
                "last_checked": datetime.now().isoformat(),
            }

        return jsonify(
            {
                "success": True,
                "services": service_status,
                "total_services": len(service_status),
            }
        )

    except Exception as e:
        logging.error(f"Error getting service status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows/analytics", methods=["GET"])
def get_workflow_analytics():
    """Get analytics and performance metrics for all workflows"""
    try:
        system = get_ai_workflow_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "AI Workflow Enhancement System not available",
                }
            ), 503

        analytics = {
            "total_workflows": len(system.workflows),
            "enabled_workflows": sum(1 for w in system.workflows.values() if w.enabled),
            "ai_optimized_workflows": sum(
                1 for w in system.workflows.values() if w.ai_optimized
            ),
            "service_distribution": {},
            "performance_summary": {},
        }

        # Calculate service distribution
        for workflow in system.workflows.values():
            for service in [workflow.trigger_service] + workflow.action_services:
                if service not in analytics["service_distribution"]:
                    analytics["service_distribution"][service] = 0
                analytics["service_distribution"][service] += 1

        # Calculate performance summary
        total_executions = 0
        total_successful = 0
        for workflow_id, metrics in system.performance_metrics.items():
            for metric in metrics:
                total_executions += 1
                if metric.get("success_count", 0) > 0:
                    total_successful += 1

        analytics["performance_summary"] = {
            "total_executions": total_executions,
            "successful_executions": total_successful,
            "overall_success_rate": (total_successful / total_executions * 100)
            if total_executions > 0
            else 0,
        }

        return jsonify(
            {
                "success": True,
                "analytics": analytics,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting workflow analytics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ai_workflow_routes.route("/api/v2/ai-workflows/templates", methods=["GET"])
def get_workflow_templates():
    """Get predefined workflow templates for common use cases"""
    try:
        templates = [
            {
                "name": "GitHub PR → Slack Notification",
                "description": "Automatically notify Slack when a GitHub PR is created",
                "trigger_service": "github",
                "action_services": ["slack"],
                "conditions": {"event_type": "pull_request", "action": "opened"},
                "ai_optimized": True,
            },
            {
                "name": "Calendar Meeting → Trello Card",
                "description": "Create Trello card for scheduled team meetings",
                "trigger_service": "google_calendar",
                "action_services": ["trello"],
                "conditions": {"meeting_type": "team", "duration_min": 30},
                "ai_optimized": True,
            },
            {
                "name": "Salesforce Lead → Asana Task",
                "description": "Create Asana task when new lead is created in Salesforce",
                "trigger_service": "salesforce",
                "action_services": ["asana"],
                "conditions": {"object_type": "lead", "status": "new"},
                "ai_optimized": True,
            },
            {
                "name": "Dropbox File → Notion Page",
                "description": "Create Notion page when important file is uploaded to Dropbox",
                "trigger_service": "dropbox",
                "action_services": ["notion"],
                "conditions": {"file_type": "document", "folder": "important"},
                "ai_optimized": True,
            },
        ]

        return jsonify(
            {"success": True, "templates": templates, "total_templates": len(templates)}
        )

    except Exception as e:
        logging.error(f"Error getting workflow templates: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Health check endpoint
@ai_workflow_routes.route("/api/v2/ai-workflows/health", methods=["GET"])
def health_check():
    """Health check for AI workflow enhancement system"""
    try:
        system = get_ai_workflow_system()

        if not system:
            return jsonify(
                {
                    "status": "unavailable",
                    "message": "AI Workflow Enhancement System not available",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 503

        return jsonify(
            {
                "status": "healthy" if system.initialized else "initializing",
                "message": "AI Workflow Enhancement System is operational",
                "workflow_count": len(system.workflows),
                "service_count": len(system.service_connections),
                "initialized": system.initialized,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        ), 500
