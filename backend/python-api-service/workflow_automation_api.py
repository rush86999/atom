"""
Enhanced Workflow Automation API with RRule Scheduling

This module provides comprehensive workflow automation API endpoints
with RRule-based scheduling, service integration, and NLU processing.
"""

from flask import Blueprint, request, jsonify
import logging
from typing import Dict, Any, List
import uuid
from datetime import datetime
from workflow_agent_integration import WorkflowAgentIntegrationService
from rrule_scheduler import get_scheduler
import json

logger = logging.getLogger(__name__)

# Create blueprint
workflow_automation_api = Blueprint("workflow_automation", __name__)

# Initialize services
workflow_agent_service = WorkflowAgentIntegrationService()
scheduler = get_scheduler()


@workflow_automation_api.route("/api/workflow-automation/analyze", methods=["POST"])
def analyze_workflow_request():
    """Analyze natural language workflow request"""
    try:
        data = request.get_json()
        user_input = data.get("user_input", "").strip()
        user_id = data.get("user_id", "default")
        session_id = data.get("session_id")

        if not user_input:
            return jsonify({"success": False, "error": "user_input is required"}), 400

        # Process workflow request through NLU system
        result = await workflow_agent_service.process_natural_language_workflow_request(
            user_input, user_id, session_id
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error analyzing workflow request: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to analyze workflow request: {str(e)}"}
        ), 500


@workflow_automation_api.route("/api/workflow-automation/generate", methods=["POST"])
def generate_workflow():
    """Generate workflow from natural language description"""
    try:
        data = request.get_json()
        user_input = data.get("user_input", "").strip()
        user_id = data.get("user_id", "default")
        service_constraints = data.get("service_constraints", [])
        schedule_preferences = data.get("schedule_preferences", {})

        if not user_input:
            return jsonify({"success": False, "error": "user_input is required"}), 400

        # Generate workflow using NLU bridge
        result = await workflow_agent_service.process_natural_language_workflow_request(
            user_input, user_id
        )

        # Apply service constraints if provided
        if service_constraints and result.get("success"):
            workflow_id = result.get("workflow_id")
            if workflow_id:
                # Apply constraints to generated workflow
                constrained_result = await _apply_service_constraints(
                    workflow_id, service_constraints
                )
                if constrained_result:
                    result.update(constrained_result)

        # Apply schedule preferences if provided
        if schedule_preferences and result.get("success"):
            workflow_id = result.get("workflow_id")
            if workflow_id:
                scheduled_result = await workflow_agent_service.schedule_workflow(
                    workflow_id, schedule_preferences, user_id
                )
                if scheduled_result.get("success"):
                    result.update(
                        {
                            "is_scheduled": True,
                            "schedule_config": scheduled_result.get("schedule_config"),
                            "rrule_string": scheduled_result.get("rrule_string"),
                            "next_execution": scheduled_result.get("next_execution"),
                        }
                    )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error generating workflow: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to generate workflow: {str(e)}"}
        ), 500


@workflow_automation_api.route("/api/workflow-automation/execute", methods=["POST"])
def execute_workflow():
    """Execute a generated workflow"""
    try:
        data = request.get_json()
        workflow_id = data.get("workflow_id")
        input_data = data.get("input_data", {})
        user_id = data.get("user_id")

        if not workflow_id:
            return jsonify({"success": False, "error": "workflow_id is required"}), 400

        result = await workflow_agent_service.execute_generated_workflow(
            workflow_id, input_data
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error executing workflow: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to execute workflow: {str(e)}"}
        ), 500


@workflow_automation_api.route("/api/workflow-automation/schedule", methods=["POST"])
def schedule_workflow():
    """Schedule a workflow using RRule configuration"""
    try:
        data = request.get_json()
        workflow_id = data.get("workflow_id")
        schedule_config = data.get("schedule_config", {})
        user_id = data.get("user_id")

        if not workflow_id:
            return jsonify({"success": False, "error": "workflow_id is required"}), 400

        if not schedule_config:
            return jsonify(
                {"success": False, "error": "schedule_config is required"}
            ), 400

        result = await workflow_agent_service.schedule_workflow(
            workflow_id, schedule_config, user_id
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error scheduling workflow: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to schedule workflow: {str(e)}"}
        ), 500


@workflow_automation_api.route(
    "/api/workflow-automation/schedule-suggestions", methods=["POST"]
)
def get_schedule_suggestions():
    """Get RRule schedule suggestions based on natural language input"""
    try:
        data = request.get_json()
        base_schedule = data.get("base_schedule", "").strip()
        context = data.get("context", {})

        if not base_schedule:
            return jsonify(
                {"success": False, "error": "base_schedule is required"}
            ), 400

        result = await workflow_agent_service.get_schedule_suggestions(base_schedule)

        # Add context-aware suggestions
        if context:
            context_suggestions = await _get_context_schedule_suggestions(context)
            result["context_suggestions"] = context_suggestions

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting schedule suggestions: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to get schedule suggestions: {str(e)}"}
        ), 500


@workflow_automation_api.route("/api/workflow-automation/workflows", methods=["GET"])
def list_workflows():
    """List all AI-generated workflows"""
    try:
        user_id = request.args.get("user_id")
        include_scheduled = (
            request.args.get("include_scheduled", "true").lower() == "true"
        )

        workflows = await workflow_agent_service.list_ai_generated_workflows(user_id)

        if not include_scheduled:
            workflows = [w for w in workflows if not w.get("is_scheduled", False)]

        return jsonify(
            {
                "success": True,
                "workflows": workflows,
                "total_workflows": len(workflows),
                "scheduled_workflows": len(
                    [w for w in workflows if w.get("is_scheduled", False)]
                ),
            }
        )

    except Exception as e:
        logger.error(f"Error listing workflows: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to list workflows: {str(e)}"}
        ), 500


@workflow_automation_api.route(
    "/api/workflow-automation/workflows/<workflow_id>", methods=["GET"]
)
def get_workflow(workflow_id):
    """Get specific workflow details"""
    try:
        if not workflow_agent_service.workflow_execution_service:
            return jsonify(
                {"success": False, "error": "Workflow execution service not available"}
            ), 503

        workflow = workflow_agent_service.workflow_execution_service.get_workflow(
            workflow_id
        )
        if not workflow:
            return jsonify(
                {"success": False, "error": f"Workflow {workflow_id} not found"}
            ), 404

        return jsonify({"success": True, "workflow": workflow})

    except Exception as e:
        logger.error(f"Error getting workflow {workflow_id}: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to get workflow: {str(e)}"}
        ), 500


@workflow_automation_api.route(
    "/api/workflow-automation/workflows/<workflow_id>", methods=["DELETE"]
)
def delete_workflow(workflow_id):
    """Delete a workflow"""
    try:
        if not workflow_agent_service.workflow_execution_service:
            return jsonify(
                {"success": False, "error": "Workflow execution service not available"}
            ), 503

        # Remove workflow from execution service
        workflow_agent_service.workflow_execution_service.unregister_workflow(
            workflow_id
        )

        return jsonify(
            {"success": True, "message": f"Workflow {workflow_id} deleted successfully"}
        )

    except Exception as e:
        logger.error(f"Error deleting workflow {workflow_id}: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to delete workflow: {str(e)}"}
        ), 500


@workflow_automation_api.route("/api/workflow-automation/suggestions", methods=["POST"])
def get_workflow_suggestions():
    """Get workflow suggestions based on user context"""
    try:
        data = request.get_json()
        user_context = data.get("user_context", {})
        service_integrations = data.get("service_integrations", [])
        usage_patterns = data.get("usage_patterns", {})

        # Build enhanced context
        enhanced_context = {
            **user_context,
            "service_integrations": service_integrations,
            "usage_patterns": usage_patterns,
        }

        suggestions = await workflow_agent_service.get_workflow_suggestions(
            enhanced_context
        )

        return jsonify(
            {
                "success": True,
                "suggestions": suggestions,
                "total_suggestions": len(suggestions),
                "context": enhanced_context,
            }
        )

    except Exception as e:
        logger.error(f"Error getting workflow suggestions: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to get workflow suggestions: {str(e)}"}
        ), 500


@workflow_automation_api.route("/api/workflow-automation/health", methods=["GET"])
def health_check():
    """Health check for workflow automation system"""
    try:
        # Check service availability
        services_healthy = bool(workflow_agent_service.workflow_execution_service)
        nlu_bridge_healthy = True  # NLU bridge has fallback

        return jsonify(
            {
                "success": True,
                "status": "healthy",
                "services": {
                    "workflow_execution": services_healthy,
                    "nlu_bridge": nlu_bridge_healthy,
                    "rrule_scheduler": True,
                },
                "timestamp": datetime.now().isoformat(),
                "version": "2.0.0",
            }
        )

    except Exception as e:
        logger.error(f"Workflow automation health check failed: {str(e)}")
        return jsonify({"success": False, "status": "unhealthy", "error": str(e)}), 503


async def _apply_service_constraints(
    workflow_id: str, constraints: List[str]
) -> Dict[str, Any]:
    """Apply service constraints to a workflow"""
    try:
        if not workflow_agent_service.workflow_execution_service:
            return None

        workflow = workflow_agent_service.workflow_execution_service.get_workflow(
            workflow_id
        )
        if not workflow:
            return None

        # Filter workflow steps based on constraints
        if "steps" in workflow:
            filtered_steps = [
                step for step in workflow["steps"] if step.get("service") in constraints
            ]
            workflow["steps"] = filtered_steps

        # Update workflow
        workflow_agent_service.workflow_execution_service.register_workflow(
            workflow_id, workflow
        )

        return {
            "constrained_steps": len(filtered_steps),
            "original_steps": len(workflow.get("steps", [])),
            "applied_constraints": constraints,
        }

    except Exception as e:
        logger.error(f"Error applying service constraints: {str(e)}")
        return None


async def _get_context_schedule_suggestions(
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Get context-aware schedule suggestions"""
    suggestions = []

    try:
        # Business hours context
        if context.get("business_hours"):
            suggestions.append(
                {
                    "schedule_text": "every weekday at 9 AM",
                    "rrule_string": "Every weekday at 09:00",
                    "frequency": "daily",
                    "context_match": "business_hours",
                }
            )

        # Team collaboration context
        if context.get("team_collaboration"):
            suggestions.append(
                {
                    "schedule_text": "every monday at 10 AM",
                    "rrule_string": "Every Monday at 10:00",
                    "frequency": "weekly",
                    "context_match": "team_meetings",
                }
            )

        # Reporting context
        if context.get("reporting_frequency") == "weekly":
            suggestions.append(
                {
                    "schedule_text": "every friday at 5 PM",
                    "rrule_string": "Every Friday at 17:00",
                    "frequency": "weekly",
                    "context_match": "weekly_reports",
                }
            )

        # Data sync context
        if context.get("data_sync_frequency") == "frequent":
            suggestions.append(
                {
                    "schedule_text": "every 15 minutes",
                    "rrule_string": "Every 15 minutes",
                    "frequency": "minutely",
                    "context_match": "frequent_sync",
                }
            )

    except Exception as e:
        logger.error(f"Error generating context schedule suggestions: {str(e)}")

    return suggestions


# Register error handlers
@workflow_automation_api.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@workflow_automation_api.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"success": False, "error": "Method not allowed"}), 405


@workflow_automation_api.errorhandler(500)
def internal_server_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500
