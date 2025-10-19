import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import uuid
import json

from workflow_execution_service import workflow_execution_service, WorkflowStatus

# Create blueprint
workflow_api_bp = Blueprint("workflow_api", __name__, url_prefix="/api/workflows")

logger = logging.getLogger(__name__)

# Sample workflow templates for the UI
WORKFLOW_TEMPLATES = {
    "meeting_scheduler": {
        "id": "meeting_scheduler",
        "name": "Meeting Scheduler",
        "description": "Automatically schedule meetings based on availability",
        "category": "calendar",
        "icon": "calendar",
        "steps": [
            {
                "id": "find_availability",
                "type": "service_action",
                "service": "calendar",
                "action": "find_available_time",
                "parameters": {
                    "duration": 60,
                    "participants": ["{{input.participants}}"],
                    "time_range": "next_week",
                },
                "name": "Find Available Time",
            },
            {
                "id": "create_event",
                "type": "service_action",
                "service": "calendar",
                "action": "create_event",
                "parameters": {
                    "title": "{{input.meeting_title}}",
                    "description": "{{input.meeting_description}}",
                    "start_time": "{{find_availability.result.best_slot.start}}",
                    "end_time": "{{find_availability.result.best_slot.end}}",
                    "attendees": "{{input.participants}}",
                },
                "name": "Create Calendar Event",
            },
            {
                "id": "send_invites",
                "type": "service_action",
                "service": "email",
                "action": "send_email",
                "parameters": {
                    "to": "{{input.participants}}",
                    "subject": "Meeting Invitation: {{input.meeting_title}}",
                    "body": "You have been invited to a meeting: {{input.meeting_title}}\n\nTime: {{find_availability.result.best_slot.start}}\n\nDescription: {{input.meeting_description}}",
                },
                "name": "Send Meeting Invites",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_title": {
                    "type": "string",
                    "title": "Meeting Title",
                    "required": True,
                },
                "meeting_description": {
                    "type": "string",
                    "title": "Meeting Description",
                    "required": False,
                },
                "participants": {
                    "type": "array",
                    "title": "Participants",
                    "items": {"type": "string", "format": "email"},
                    "required": True,
                },
            },
        },
    },
    "task_automation": {
        "id": "task_automation",
        "name": "Task Automation",
        "description": "Create tasks across multiple platforms",
        "category": "tasks",
        "icon": "tasks",
        "steps": [
            {
                "id": "create_asana_task",
                "type": "service_action",
                "service": "tasks",
                "action": "create_task",
                "parameters": {
                    "title": "{{input.task_title}}",
                    "description": "{{input.task_description}}",
                    "due_date": "{{input.due_date}}",
                    "assignee": "{{input.assignee}}",
                },
                "name": "Create Asana Task",
            },
            {
                "id": "create_trello_card",
                "type": "service_action",
                "service": "tasks",
                "action": "create_card",
                "parameters": {
                    "title": "{{input.task_title}}",
                    "description": "{{input.task_description}}",
                    "due_date": "{{input.due_date}}",
                    "list_id": "{{input.trello_list}}",
                },
                "name": "Create Trello Card",
            },
            {
                "id": "notify_team",
                "type": "service_action",
                "service": "slack",
                "action": "send_message",
                "parameters": {
                    "platform": "slack",
                    "to": "{{input.slack_channel}}",
                    "body": "New task created: {{input.task_title}}\nAssigned to: {{input.assignee}}\nDue: {{input.due_date}}",
                },
                "name": "Notify Team on Slack",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "title": "Task Title",
                    "required": True,
                },
                "task_description": {
                    "type": "string",
                    "title": "Task Description",
                    "required": False,
                },
                "due_date": {
                    "type": "string",
                    "title": "Due Date",
                    "format": "date",
                    "required": True,
                },
                "assignee": {"type": "string", "title": "Assignee", "required": True},
                "trello_list": {
                    "type": "string",
                    "title": "Trello List ID",
                    "required": False,
                },
                "slack_channel": {
                    "type": "string",
                    "title": "Slack Channel",
                    "required": False,
                },
            },
        },
    },
    "document_workflow": {
        "id": "document_workflow",
        "name": "Document Processing",
        "description": "Process and distribute documents",
        "category": "documents",
        "icon": "document",
        "steps": [
            {
                "id": "create_document",
                "type": "service_action",
                "service": "notion",
                "action": "create_page",
                "parameters": {
                    "title": "{{input.document_title}}",
                    "content": "{{input.document_content}}",
                    "template": "{{input.template}}",
                },
                "name": "Create Document",
            },
            {
                "id": "upload_to_dropbox",
                "type": "service_action",
                "service": "dropbox",
                "action": "upload_file",
                "parameters": {
                    "file_path": "/Documents/{{input.document_title}}.txt",
                    "file_content": "{{create_document.result.content}}",
                },
                "name": "Upload to Dropbox",
            },
            {
                "id": "share_document",
                "type": "service_action",
                "service": "dropbox",
                "action": "share_file",
                "parameters": {
                    "file_path": "/Documents/{{input.document_title}}.txt",
                    "recipients": "{{input.recipients}}",
                },
                "name": "Share Document",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "document_title": {
                    "type": "string",
                    "title": "Document Title",
                    "required": True,
                },
                "document_content": {
                    "type": "string",
                    "title": "Document Content",
                    "required": True,
                },
                "template": {"type": "string", "title": "Template", "required": False},
                "recipients": {
                    "type": "array",
                    "title": "Recipients",
                    "items": {"type": "string", "format": "email"},
                    "required": True,
                },
            },
        },
    },
}


@workflow_api_bp.route("/templates", methods=["GET"])
def get_workflow_templates():
    """Get all available workflow templates"""
    try:
        templates = list(WORKFLOW_TEMPLATES.values())

        return jsonify(
            {"success": True, "templates": templates, "count": len(templates)}
        )
    except Exception as e:
        logger.error(f"Error getting workflow templates: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Additional comprehensive workflow templates to cover all services
ADDITIONAL_WORKFLOW_TEMPLATES = {
    "team_communication": {
        "id": "team_communication",
        "name": "Team Communication",
        "description": "Send messages across multiple communication platforms",
        "category": "communication",
        "icon": "message",
        "steps": [
            {
                "id": "slack_announcement",
                "type": "service_action",
                "service": "slack",
                "action": "send_message",
                "parameters": {
                    "to": "{{input.slack_channel}}",
                    "body": "{{input.announcement}}",
                },
                "name": "Send Slack Announcement",
            },
            {
                "id": "teams_message",
                "type": "service_action",
                "service": "teams",
                "action": "send_message",
                "parameters": {
                    "to": "{{input.teams_channel}}",
                    "body": "{{input.announcement}}",
                },
                "name": "Send Teams Message",
            },
            {
                "id": "discord_notification",
                "type": "service_action",
                "service": "discord",
                "action": "send_message",
                "parameters": {
                    "to": "{{input.discord_channel}}",
                    "body": "{{input.announcement}}",
                },
                "name": "Send Discord Notification",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "announcement": {
                    "type": "string",
                    "title": "Announcement",
                    "required": True,
                },
                "slack_channel": {
                    "type": "string",
                    "title": "Slack Channel",
                    "required": False,
                },
                "teams_channel": {
                    "type": "string",
                    "title": "Teams Channel",
                    "required": False,
                },
                "discord_channel": {
                    "type": "string",
                    "title": "Discord Channel",
                    "required": False,
                },
            },
        },
    },
    "file_management": {
        "id": "file_management",
        "name": "File Management",
        "description": "Upload and manage files across cloud storage platforms",
        "category": "storage",
        "icon": "cloud",
        "steps": [
            {
                "id": "upload_to_gdrive",
                "type": "service_action",
                "service": "gdrive",
                "action": "upload_file",
                "parameters": {
                    "file_content": "{{input.file_content}}",
                    "file_path": "/{{input.folder}}/{{input.filename}}",
                },
                "name": "Upload to Google Drive",
            },
            {
                "id": "upload_to_dropbox",
                "type": "service_action",
                "service": "dropbox",
                "action": "upload_file",
                "parameters": {
                    "file_content": "{{input.file_content}}",
                    "file_path": "/{{input.folder}}/{{input.filename}}",
                },
                "name": "Upload to Dropbox",
            },
            {
                "id": "notify_upload_complete",
                "type": "service_action",
                "service": "notifications",
                "action": "send_notification",
                "parameters": {
                    "message": "Files uploaded successfully to Google Drive and Dropbox",
                },
                "name": "Send Upload Notification",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "file_content": {
                    "type": "string",
                    "title": "File Content",
                    "required": True,
                },
                "filename": {
                    "type": "string",
                    "title": "Filename",
                    "required": True,
                },
                "folder": {
                    "type": "string",
                    "title": "Folder",
                    "required": False,
                    "default": "Documents",
                },
            },
        },
    },
    "github_workflow": {
        "id": "github_workflow",
        "name": "GitHub Issue Management",
        "description": "Create and manage GitHub issues with notifications",
        "category": "development",
        "icon": "code",
        "steps": [
            {
                "id": "create_github_issue",
                "type": "service_action",
                "service": "github",
                "action": "create_issue",
                "parameters": {
                    "title": "{{input.issue_title}}",
                    "description": "{{input.issue_description}}",
                    "repository": "{{input.repository}}",
                },
                "name": "Create GitHub Issue",
            },
            {
                "id": "notify_slack_issue",
                "type": "service_action",
                "service": "slack",
                "action": "send_message",
                "parameters": {
                    "to": "{{input.slack_channel}}",
                    "body": "New GitHub issue created: {{input.issue_title}}\nRepository: {{input.repository}}",
                },
                "name": "Notify Team on Slack",
            },
            {
                "id": "schedule_reminder",
                "type": "service_action",
                "service": "calendar",
                "action": "create_event",
                "parameters": {
                    "title": "Follow up on GitHub issue: {{input.issue_title}}",
                    "description": "Check progress on the GitHub issue",
                    "start_time": "{{input.follow_up_date}}T09:00:00",
                    "end_time": "{{input.follow_up_date}}T09:30:00",
                },
                "name": "Schedule Follow-up",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_title": {
                    "type": "string",
                    "title": "Issue Title",
                    "required": True,
                },
                "issue_description": {
                    "type": "string",
                    "title": "Issue Description",
                    "required": False,
                },
                "repository": {
                    "type": "string",
                    "title": "Repository",
                    "required": True,
                },
                "slack_channel": {
                    "type": "string",
                    "title": "Slack Channel",
                    "required": False,
                },
                "follow_up_date": {
                    "type": "string",
                    "title": "Follow-up Date",
                    "format": "date",
                    "required": True,
                },
            },
        },
    },
    "notion_content_workflow": {
        "id": "notion_content_workflow",
        "name": "Notion Content Creation",
        "description": "Create and organize content in Notion with cross-platform sharing",
        "category": "productivity",
        "icon": "document",
        "steps": [
            {
                "id": "create_notion_page",
                "type": "service_action",
                "service": "notion",
                "action": "create_page",
                "parameters": {
                    "title": "{{input.page_title}}",
                    "content": "{{input.page_content}}",
                },
                "name": "Create Notion Page",
            },
            {
                "id": "share_via_email",
                "type": "service_action",
                "service": "email",
                "action": "send_email",
                "parameters": {
                    "to": "{{input.recipients}}",
                    "subject": "New Notion Page: {{input.page_title}}",
                    "body": "A new Notion page has been created: {{input.page_title}}\n\nContent: {{input.page_content}}",
                },
                "name": "Share via Email",
            },
            {
                "id": "notify_teams",
                "type": "service_action",
                "service": "teams",
                "action": "send_message",
                "parameters": {
                    "to": "{{input.teams_channel}}",
                    "body": "New Notion page created: {{input.page_title}}",
                },
                "name": "Notify Teams Channel",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "page_title": {
                    "type": "string",
                    "title": "Page Title",
                    "required": True,
                },
                "page_content": {
                    "type": "string",
                    "title": "Page Content",
                    "required": True,
                },
                "recipients": {
                    "type": "array",
                    "title": "Email Recipients",
                    "items": {"type": "string", "format": "email"},
                    "required": False,
                },
                "teams_channel": {
                    "type": "string",
                    "title": "Teams Channel",
                    "required": False,
                },
            },
        },
    },
    "workflow_automation_demo": {
        "id": "workflow_automation_demo",
        "name": "Workflow Automation Demo",
        "description": "Demonstrate workflow automation capabilities with multiple services",
        "category": "automation",
        "icon": "workflow",
        "steps": [
            {
                "id": "create_demo_workflow",
                "type": "service_action",
                "service": "workflow",
                "action": "create_workflow",
                "parameters": {
                    "name": "{{input.demo_name}}",
                    "description": "{{input.demo_description}}",
                },
                "name": "Create Demo Workflow",
            },
            {
                "id": "schedule_demo",
                "type": "service_action",
                "service": "calendar",
                "action": "create_event",
                "parameters": {
                    "title": "Workflow Demo: {{input.demo_name}}",
                    "description": "{{input.demo_description}}",
                    "start_time": "{{input.demo_date}}T10:00:00",
                    "end_time": "{{input.demo_date}}T11:00:00",
                },
                "name": "Schedule Demo",
            },
            {
                "id": "send_demo_invites",
                "type": "service_action",
                "service": "email",
                "action": "send_email",
                "parameters": {
                    "to": "{{input.attendees}}",
                    "subject": "Workflow Automation Demo: {{input.demo_name}}",
                    "body": "You're invited to a workflow automation demo on {{input.demo_date}} at 10:00 AM.\n\nDescription: {{input.demo_description}}",
                },
                "name": "Send Demo Invites",
            },
            {
                "id": "notify_all_channels",
                "type": "service_action",
                "service": "notifications",
                "action": "send_notification",
                "parameters": {
                    "message": "Workflow automation demo scheduled for {{input.demo_date}}",
                },
                "name": "Send Notifications",
            },
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "demo_name": {
                    "type": "string",
                    "title": "Demo Name",
                    "required": True,
                },
                "demo_description": {
                    "type": "string",
                    "title": "Demo Description",
                    "required": True,
                },
                "demo_date": {
                    "type": "string",
                    "title": "Demo Date",
                    "format": "date",
                    "required": True,
                },
                "attendees": {
                    "type": "array",
                    "title": "Attendees",
                    "items": {"type": "string", "format": "email"},
                    "required": True,
                },
            },
        },
    },
}

# Merge additional templates with existing ones
WORKFLOW_TEMPLATES.update(ADDITIONAL_WORKFLOW_TEMPLATES)


@workflow_api_bp.route("/templates/<template_id>", methods=["GET"])
def get_workflow_template(template_id):
    """Get a specific workflow template"""
    try:
        if template_id not in WORKFLOW_TEMPLATES:
            return jsonify(
                {"success": False, "error": f"Template {template_id} not found"}
            ), 404

        template = WORKFLOW_TEMPLATES[template_id]
        return jsonify({"success": True, "template": template})
    except Exception as e:
        logger.error(f"Error getting workflow template {template_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/definitions", methods=["GET"])
def list_workflow_definitions():
    """List all registered workflow definitions"""
    try:
        workflow_ids = workflow_execution_service.list_workflows()
        workflows = []

        for workflow_id in workflow_ids:
            workflow = workflow_execution_service.get_workflow(workflow_id)
            if workflow:
                workflows.append(
                    {
                        "id": workflow_id,
                        "name": workflow.get("name", workflow_id),
                        "description": workflow.get("description", ""),
                        "steps_count": len(workflow.get("steps", [])),
                        "created_at": workflow.get("created_at"),
                        "updated_at": workflow.get("updated_at"),
                    }
                )

        return jsonify(
            {"success": True, "workflows": workflows, "count": len(workflows)}
        )
    except Exception as e:
        logger.error(f"Error listing workflow definitions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/definitions", methods=["POST"])
def create_workflow_definition():
    """Create a new workflow definition"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        workflow_id = data.get("id") or str(uuid.uuid4())
        workflow_definition = {
            "id": workflow_id,
            "name": data.get("name", "Unnamed Workflow"),
            "description": data.get("description", ""),
            "steps": data.get("steps", []),
            "input_schema": data.get("input_schema", {}),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        # Validate workflow definition
        validation_result = _validate_workflow_definition(workflow_definition)
        if not validation_result["valid"]:
            return jsonify(
                {
                    "success": False,
                    "error": f"Invalid workflow definition: {validation_result['errors']}",
                }
            ), 400

        workflow_execution_service.register_workflow(workflow_id, workflow_definition)

        logger.info(f"Created workflow definition: {workflow_id}")

        return jsonify(
            {
                "success": True,
                "workflow_id": workflow_id,
                "workflow": workflow_definition,
            }
        )
    except Exception as e:
        logger.error(f"Error creating workflow definition: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/definitions/<workflow_id>", methods=["GET"])
def get_workflow_definition(workflow_id):
    """Get a specific workflow definition"""
    try:
        workflow = workflow_execution_service.get_workflow(workflow_id)

        if not workflow:
            return jsonify(
                {"success": False, "error": f"Workflow {workflow_id} not found"}
            ), 404

        return jsonify({"success": True, "workflow": workflow})
    except Exception as e:
        logger.error(f"Error getting workflow definition {workflow_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/definitions/<workflow_id>", methods=["PUT"])
def update_workflow_definition(workflow_id):
    """Update a workflow definition"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        existing_workflow = workflow_execution_service.get_workflow(workflow_id)
        if not existing_workflow:
            return jsonify(
                {"success": False, "error": f"Workflow {workflow_id} not found"}
            ), 404

        # Update workflow definition
        updated_workflow = {
            **existing_workflow,
            "name": data.get("name", existing_workflow.get("name")),
            "description": data.get(
                "description", existing_workflow.get("description")
            ),
            "steps": data.get("steps", existing_workflow.get("steps", [])),
            "input_schema": data.get(
                "input_schema", existing_workflow.get("input_schema", {})
            ),
            "updated_at": datetime.now().isoformat(),
        }

        # Validate updated workflow definition
        validation_result = _validate_workflow_definition(updated_workflow)
        if not validation_result["valid"]:
            return jsonify(
                {
                    "success": False,
                    "error": f"Invalid workflow definition: {validation_result['errors']}",
                }
            ), 400

        workflow_execution_service.register_workflow(workflow_id, updated_workflow)

        logger.info(f"Updated workflow definition: {workflow_id}")

        return jsonify(
            {"success": True, "workflow_id": workflow_id, "workflow": updated_workflow}
        )
    except Exception as e:
        logger.error(f"Error updating workflow definition {workflow_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/definitions/<workflow_id>", methods=["DELETE"])
def delete_workflow_definition(workflow_id):
    """Delete a workflow definition"""
    try:
        # Note: In a real implementation, we would remove from the service
        # For now, we'll just return success
        logger.info(f"Deleted workflow definition: {workflow_id}")

        return jsonify({"success": True, "message": f"Workflow {workflow_id} deleted"})
    except Exception as e:
        logger.error(f"Error deleting workflow definition {workflow_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/execute", methods=["POST"])
async def execute_workflow():
    """Execute a workflow"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        workflow_id = data.get("workflow_id")
        input_data = data.get("input", {})
        trigger_data = data.get("trigger_data", {})

        if not workflow_id:
            return jsonify({"success": False, "error": "workflow_id is required"}), 400

        # Merge input data with trigger data
        execution_data = {**input_data, **trigger_data}

        # Execute the workflow
        execution_result = await workflow_execution_service.execute_workflow(
            workflow_id, execution_data
        )

        return jsonify(
            {
                "success": True,
                "execution_id": execution_result["execution_id"],
                "status": execution_result["status"].value,
                "workflow_id": workflow_id,
                "start_time": execution_result["start_time"].isoformat(),
                "end_time": execution_result["end_time"].isoformat()
                if execution_result["end_time"]
                else None,
                "current_step": execution_result["current_step"],
                "total_steps": execution_result["total_steps"],
                "results": execution_result["results"],
                "errors": execution_result["errors"],
            }
        )
    except Exception as e:
        logger.error(f"Error executing workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/executions", methods=["GET"])
def list_executions():
    """List all workflow executions"""
    try:
        executions = workflow_execution_service.list_active_executions()

        # Format executions for API response
        formatted_executions = []
        for execution in executions:
            formatted_executions.append(
                {
                    "execution_id": execution["execution_id"],
                    "workflow_id": execution["workflow_id"],
                    "status": execution["status"].value,
                    "start_time": execution["start_time"].isoformat(),
                    "end_time": execution["end_time"].isoformat()
                    if execution["end_time"]
                    else None,
                    "current_step": execution["current_step"],
                    "total_steps": execution["total_steps"],
                    "has_errors": len(execution["errors"]) > 0,
                }
            )

        return jsonify(
            {
                "success": True,
                "executions": formatted_executions,
                "count": len(formatted_executions),
            }
        )
    except Exception as e:
        logger.error(f"Error listing workflow executions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/executions/<execution_id>", methods=["GET"])
def get_execution(execution_id):
    """Get details of a specific workflow execution"""
    try:
        execution = workflow_execution_service.get_execution_status(execution_id)

        if not execution:
            return jsonify(
                {"success": False, "error": f"Execution {execution_id} not found"}
            ), 404

        return jsonify(
            {
                "success": True,
                "execution": {
                    "execution_id": execution["execution_id"],
                    "workflow_id": execution["workflow_id"],
                    "status": execution["status"].value,
                    "start_time": execution["start_time"].isoformat(),
                    "end_time": execution["end_time"].isoformat()
                    if execution["end_time"]
                    else None,
                    "current_step": execution["current_step"],
                    "total_steps": execution["total_steps"],
                    "trigger_data": execution["trigger_data"],
                    "results": execution["results"],
                    "errors": execution["errors"],
                },
            }
        )
    except Exception as e:
        logger.error(f"Error getting execution {execution_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/executions/<execution_id>/cancel", methods=["POST"])
def cancel_execution(execution_id):
    """Cancel a workflow execution"""
    try:
        success = workflow_execution_service.cancel_execution(execution_id)

        if not success:
            return jsonify(
                {"success": False, "error": f"Cannot cancel execution {execution_id}"}
            ), 400

        return jsonify(
            {"success": True, "message": f"Execution {execution_id} cancelled"}
        )
    except Exception as e:
        logger.error(f"Error cancelling execution {execution_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/services", methods=["GET"])
def list_available_services():
    """List all available services for workflow actions"""
    try:
        services = workflow_execution_service.service_registry

        formatted_services = {}
        for service_name, actions in services.items():
            formatted_services[service_name] = {
                "name": service_name,
                "actions": list(actions.keys()),
                "description": f"{service_name.title()} service integration",
            }

        return jsonify({"success": True, "services": formatted_services})
    except Exception as e:
        logger.error(f"Error listing available services: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_api_bp.route("/health", methods=["GET"])
def workflow_health():
    """Workflow service health check"""
    try:
        workflow_count = len(workflow_execution_service.list_workflows())
        execution_count = len(workflow_execution_service.list_active_executions())
        service_count = len(workflow_execution_service.service_registry)

        return jsonify(
            {
                "success": True,
                "status": "healthy",
                "workflows_registered": workflow_count,
                "active_executions": execution_count,
                "available_services": service_count,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Workflow health check failed: {e}")
        return jsonify({"success": False, "status": "unhealthy", "error": str(e)}), 500


def _validate_workflow_definition(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a workflow definition"""
    errors = []

    # Check required fields
    if not workflow.get("id"):
        errors.append("Workflow ID is required")

    if not workflow.get("name"):
        errors.append("Workflow name is required")

    # Validate steps
    steps = workflow.get("steps", [])
    if not steps:
        errors.append("Workflow must have at least one step")

    for i, step in enumerate(steps):
        step_errors = _validate_workflow_step(step, i)
        errors.extend(step_errors)

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_workflow_step(step: Dict[str, Any], index: int) -> List[str]:
    """Validate a single workflow step"""
    errors = []

    if not step.get("id"):
        errors.append(f"Step {index}: ID is required")

    if not step.get("type"):
        errors.append(f"Step {index}: Type is required")

    step_type = step.get("type")
    if step_type == "service_action":
        if not step.get("service"):
            errors.append(f"Step {index}: Service is required for service_action type")
        if not step.get("action"):
            errors.append(f"Step {index}: Action is required for service_action type")

    elif step_type == "condition":
        if not step.get("condition"):
            errors.append(f"Step {index}: Condition is required for condition type")

    elif step_type == "delay":
        if not step.get("delay_seconds"):
            errors.append(f"Step {index}: delay_seconds is required for delay type")

    elif step_type == "webhook":
        if not step.get("url"):
            errors.append(f"Step {index}: URL is required for webhook type")

    elif step_type == "data_transform":
        if not step.get("transform_type"):
            errors.append(
                f"Step {index}: transform_type is required for data_transform type"
            )

    return errors
