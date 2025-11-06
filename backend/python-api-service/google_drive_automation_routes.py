"""
Google Drive Automation API Routes
Flask routes for Google Drive automation workflows
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import asyncio
import json
from loguru import logger

# Import Google Drive automation services
from google_drive_automation import (
    GoogleDriveAutomationService,
    AutomationWorkflow,
    AutomationTrigger,
    AutomationAction,
    WorkflowExecution,
    WorkflowTemplate,
    TriggerType,
    ActionType,
    Operator,
    ConditionLogic,
    get_google_drive_automation_service
)

# Import Google Drive services
from google_drive_service import GoogleDriveService, get_google_drive_service

# Import ATOM automation services
from automation.workflow_engine import WorkflowEngine
from automation.trigger_manager import TriggerManager
from automation.action_executor import ActionExecutor
from automation.workflow_scheduler import WorkflowScheduler

# Create Flask blueprint
google_drive_automation_bp = Blueprint("google_drive_automation_bp", __name__)

# Database pool (will be set from main app)
db_pool = None

# Service instance
automation_service: Optional[GoogleDriveAutomationService] = None

def set_database_pool(pool):
    """Set database connection pool"""
    global db_pool
    db_pool = pool

def initialize_automation_service(db_conn_pool=None):
    """Initialize Google Drive automation service"""
    global automation_service, db_pool
    
    db_pool = db_conn_pool
    
    try:
        # Initialize core services
        drive_service = get_google_drive_service()
        
        # Initialize automation services
        workflow_engine = WorkflowEngine()
        trigger_manager = TriggerManager()
        action_executor = ActionExecutor()
        workflow_scheduler = WorkflowScheduler()
        
        # Initialize automation service
        automation_service = get_google_drive_automation_service(
            drive_service=drive_service,
            workflow_engine=workflow_engine,
            trigger_manager=trigger_manager,
            action_executor=action_executor,
            workflow_scheduler=workflow_scheduler,
            db_pool=db_pool
        )
        
        logger.info("Google Drive Automation service initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Google Drive automation service: {e}")
        return False

# =============================================================================
# Workflow Management Routes
# =============================================================================

@google_drive_automation_bp.route('/api/google-drive/automation/workflows', methods=['POST'])
async def create_automation_workflow():
    """Create automation workflow"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        name = data.get('name')
        description = data.get('description', '')
        triggers = data.get('triggers', [])
        actions = data.get('actions', [])
        enabled = data.get('enabled', True)
        
        if not all([user_id, name]):
            return jsonify({
                "ok": False,
                "error": "user_id and name are required"
            }), 400
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Create workflow
        workflow = await automation_service.create_workflow(
            user_id=user_id,
            name=name,
            description=description,
            triggers=triggers,
            actions=actions,
            enabled=enabled
        )
        
        return jsonify({
            "ok": True,
            "workflow": {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "user_id": workflow.user_id,
                "triggers": [
                    {
                        "id": trigger.id,
                        "type": trigger.type.value,
                        "config": trigger.config,
                        "conditions": trigger.conditions,
                        "enabled": trigger.enabled
                    }
                    for trigger in workflow.triggers
                ],
                "actions": [
                    {
                        "id": action.id,
                        "type": action.type.value,
                        "config": action.config,
                        "retry_count": action.retry_count,
                        "max_retries": action.max_retries,
                        "timeout": action.timeout,
                        "enabled": action.enabled
                    }
                    for action in workflow.actions
                ],
                "enabled": workflow.enabled,
                "run_count": workflow.run_count,
                "success_count": workflow.success_count,
                "error_count": workflow.error_count,
                "last_run": workflow.last_run.isoformat() if workflow.last_run else None,
                "last_success": workflow.last_success.isoformat() if workflow.last_success else None,
                "last_error": workflow.last_error.isoformat() if workflow.last_error else None,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat()
            },
            "message": f"Workflow '{name}' created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating automation workflow: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/workflows', methods=['GET'])
async def get_automation_workflows():
    """Get automation workflows"""
    try:
        user_id = request.args.get('user_id')
        workflow_id = request.args.get('workflow_id')
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        
        if not user_id and not workflow_id:
            return jsonify({
                "ok": False,
                "error": "user_id or workflow_id is required"
            }), 400
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Get workflows
        if workflow_id:
            workflow = await automation_service.get_workflow(workflow_id)
            workflows = [workflow] if workflow else []
        else:
            workflows = await automation_service.get_workflows(
                user_id=user_id,
                enabled_only=enabled_only
            )
        
        # Convert to JSON-friendly format
        workflows_json = []
        for workflow in workflows:
            workflow_dict = {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "user_id": workflow.user_id,
                "triggers": [
                    {
                        "id": trigger.id,
                        "type": trigger.type.value,
                        "config": trigger.config,
                        "conditions": trigger.conditions,
                        "enabled": trigger.enabled
                    }
                    for trigger in workflow.triggers
                ],
                "actions": [
                    {
                        "id": action.id,
                        "type": action.type.value,
                        "config": action.config,
                        "retry_count": action.retry_count,
                        "max_retries": action.max_retries,
                        "timeout": action.timeout,
                        "enabled": action.enabled
                    }
                    for action in workflow.actions
                ],
                "enabled": workflow.enabled,
                "run_count": workflow.run_count,
                "success_count": workflow.success_count,
                "error_count": workflow.error_count,
                "last_run": workflow.last_run.isoformat() if workflow.last_run else None,
                "last_success": workflow.last_success.isoformat() if workflow.last_success else None,
                "last_error": workflow.last_error.isoformat() if workflow.last_error else None,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat()
            }
            workflows_json.append(workflow_dict)
        
        return jsonify({
            "ok": True,
            "workflows": workflows_json,
            "total": len(workflows_json)
        })
        
    except Exception as e:
        logger.error(f"Error getting automation workflows: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/workflows/<workflow_id>', methods=['PUT'])
async def update_automation_workflow(workflow_id: str):
    """Update automation workflow"""
    try:
        data = request.get_json()
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Update workflow
        success = await automation_service.update_workflow(
            workflow_id=workflow_id,
            updates=data
        )
        
        if success:
            # Get updated workflow
            workflow = await automation_service.get_workflow(workflow_id)
            
            if workflow:
                return jsonify({
                    "ok": True,
                    "workflow": {
                        "id": workflow.id,
                        "name": workflow.name,
                        "description": workflow.description,
                        "user_id": workflow.user_id,
                        "triggers": [
                            {
                                "id": trigger.id,
                                "type": trigger.type.value,
                                "config": trigger.config,
                                "conditions": trigger.conditions,
                                "enabled": trigger.enabled
                            }
                            for trigger in workflow.triggers
                        ],
                        "actions": [
                            {
                                "id": action.id,
                                "type": action.type.value,
                                "config": action.config,
                                "retry_count": action.retry_count,
                                "max_retries": action.max_retries,
                                "timeout": action.timeout,
                                "enabled": action.enabled
                            }
                            for action in workflow.actions
                        ],
                        "enabled": workflow.enabled,
                        "updated_at": workflow.updated_at.isoformat()
                    },
                    "message": f"Workflow '{workflow.name}' updated successfully"
                })
            else:
                return jsonify({
                    "ok": False,
                    "error": "Workflow not found after update"
                }), 404
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to update workflow"
            }), 500
        
    except Exception as e:
        logger.error(f"Error updating automation workflow: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/workflows/<workflow_id>', methods=['DELETE'])
async def delete_automation_workflow(workflow_id: str):
    """Delete automation workflow"""
    try:
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Delete workflow
        success = await automation_service.delete_workflow(workflow_id)
        
        if success:
            return jsonify({
                "ok": True,
                "message": f"Workflow {workflow_id} deleted successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Workflow not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error deleting automation workflow: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Workflow Execution Routes
# =============================================================================

@google_drive_automation_bp.route('/api/google-drive/automation/workflows/<workflow_id>/execute', methods=['POST'])
async def execute_automation_workflow(workflow_id: str):
    """Execute automation workflow manually"""
    try:
        data = request.get_json()
        trigger_data = data.get('trigger_data', {})
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Execute workflow
        execution = await automation_service.execute_workflow(
            workflow_id=workflow_id,
            trigger_type=TriggerType.MANUAL,
            trigger_data=trigger_data,
            manual_trigger=True
        )
        
        if execution:
            return jsonify({
                "ok": True,
                "execution": {
                    "id": execution.id,
                    "workflow_id": execution.workflow_id,
                    "user_id": execution.user_id,
                    "trigger_type": execution.trigger_type.value,
                    "trigger_data": execution.trigger_data,
                    "status": execution.status,
                    "started_at": execution.started_at.isoformat(),
                    "input_data": execution.input_data,
                    "variables": execution.variables
                },
                "message": f"Workflow execution started: {execution.id}"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to start workflow execution"
            }), 500
        
    except Exception as e:
        logger.error(f"Error executing automation workflow: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/executions', methods=['GET'])
async def get_workflow_executions():
    """Get workflow executions"""
    try:
        workflow_id = request.args.get('workflow_id')
        user_id = request.args.get('user_id')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Get executions
        executions = await automation_service.get_executions(
            workflow_id=workflow_id,
            user_id=user_id,
            status=status,
            limit=limit
        )
        
        # Convert to JSON-friendly format
        executions_json = []
        for execution in executions:
            execution_dict = {
                "id": execution.id,
                "workflow_id": execution.workflow_id,
                "user_id": execution.user_id,
                "trigger_type": execution.trigger_type.value,
                "trigger_data": execution.trigger_data,
                "status": execution.status,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "duration": execution.duration,
                "input_data": execution.input_data,
                "output_data": execution.output_data,
                "error_message": execution.error_message,
                "actions_executed": execution.actions_executed,
                "variables": execution.variables,
                "logs": execution.logs[-10] if len(execution.logs) > 10 else execution.logs  # Last 10 logs
            }
            executions_json.append(execution_dict)
        
        return jsonify({
            "ok": True,
            "executions": executions_json,
            "total": len(executions_json)
        })
        
    except Exception as e:
        logger.error(f"Error getting workflow executions: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/executions/<execution_id>', methods=['GET'])
async def get_workflow_execution(execution_id: str):
    """Get specific workflow execution"""
    try:
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Get execution
        execution = await automation_service.get_execution(execution_id)
        
        if execution:
            return jsonify({
                "ok": True,
                "execution": {
                    "id": execution.id,
                    "workflow_id": execution.workflow_id,
                    "user_id": execution.user_id,
                    "trigger_type": execution.trigger_type.value,
                    "trigger_data": execution.trigger_data,
                    "status": execution.status,
                    "started_at": execution.started_at.isoformat(),
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "duration": execution.duration,
                    "input_data": execution.input_data,
                    "output_data": execution.output_data,
                    "error_message": execution.error_message,
                    "actions_executed": execution.actions_executed,
                    "variables": execution.variables,
                    "logs": execution.logs
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Execution not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting workflow execution: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Workflow Templates Routes
# =============================================================================

@google_drive_automation_bp.route('/api/google-drive/automation/templates', methods=['POST'])
async def create_automation_template():
    """Create workflow template"""
    try:
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')
        category = data.get('category')
        triggers = data.get('triggers', [])
        actions = data.get('actions', [])
        variables = data.get('variables', [])
        icon = data.get('icon', '')
        tags = data.get('tags', [])
        public = data.get('public', False)
        created_by = data.get('created_by', '')
        
        if not all([name, category]):
            return jsonify({
                "ok": False,
                "error": "name and category are required"
            }), 400
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Create template
        template = await automation_service.create_template(
            name=name,
            description=description,
            category=category,
            triggers=triggers,
            actions=actions,
            variables=variables,
            icon=icon,
            tags=tags,
            public=public,
            created_by=created_by
        )
        
        return jsonify({
            "ok": True,
            "template": {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "triggers": template.triggers,
                "actions": template.actions,
                "variables": template.variables,
                "icon": template.icon,
                "tags": template.tags,
                "public": template.public,
                "created_by": template.created_by,
                "created_at": template.created_at.isoformat(),
                "usage_count": template.usage_count
            },
            "message": f"Template '{name}' created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating automation template: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/templates', methods=['GET'])
async def get_automation_templates():
    """Get workflow templates"""
    try:
        category = request.args.get('category')
        public_only = request.args.get('public_only', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 50))
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Get templates
        templates = await automation_service.get_templates(
            category=category,
            public_only=public_only,
            limit=limit
        )
        
        # Convert to JSON-friendly format
        templates_json = []
        for template in templates:
            template_dict = {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "triggers": template.triggers,
                "actions": template.actions,
                "variables": template.variables,
                "icon": template.icon,
                "tags": template.tags,
                "public": template.public,
                "created_by": template.created_by,
                "created_at": template.created_at.isoformat(),
                "usage_count": template.usage_count
            }
            templates_json.append(template_dict)
        
        return jsonify({
            "ok": True,
            "templates": templates_json,
            "total": len(templates_json)
        })
        
    except Exception as e:
        logger.error(f"Error getting automation templates: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/templates/<template_id>/create-workflow', methods=['POST'])
async def create_workflow_from_template(template_id: str):
    """Create workflow from template"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        name = data.get('name')
        description = data.get('description', '')
        variable_values = data.get('variable_values', {})
        
        if not all([user_id, name]):
            return jsonify({
                "ok": False,
                "error": "user_id and name are required"
            }), 400
        
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Create workflow from template
        workflow = await automation_service.create_workflow_from_template(
            template_id=template_id,
            user_id=user_id,
            name=name,
            description=description,
            variable_values=variable_values
        )
        
        if workflow:
            return jsonify({
                "ok": True,
                "workflow": {
                    "id": workflow.id,
                    "name": workflow.name,
                    "description": workflow.description,
                    "user_id": workflow.user_id,
                    "triggers": [
                        {
                            "id": trigger.id,
                            "type": trigger.type.value,
                            "config": trigger.config,
                            "conditions": trigger.conditions,
                            "enabled": trigger.enabled
                        }
                        for trigger in workflow.triggers
                    ],
                    "actions": [
                        {
                            "id": action.id,
                            "type": action.type.value,
                            "config": action.config,
                            "retry_count": action.retry_count,
                            "max_retries": action.max_retries,
                            "timeout": action.timeout,
                            "enabled": action.enabled
                        }
                        for action in workflow.actions
                    ],
                    "enabled": workflow.enabled,
                    "created_at": workflow.created_at.isoformat()
                },
                "message": f"Workflow '{name}' created from template successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Template not found or workflow creation failed"
            }), 404
        
    except Exception as e:
        logger.error(f"Error creating workflow from template: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Automation Statistics Routes
# =============================================================================

@google_drive_automation_bp.route('/api/google-drive/automation/statistics', methods=['GET'])
async def get_automation_statistics():
    """Get automation service statistics"""
    try:
        if not automation_service:
            return jsonify({
                "ok": False,
                "error": "Automation service not initialized"
            }), 500
        
        # Get statistics
        statistics = automation_service.get_automation_statistics()
        
        return jsonify({
            "ok": True,
            "statistics": statistics
        })
        
    except Exception as e:
        logger.error(f"Error getting automation statistics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Automation Configuration Routes
# =============================================================================

@google_drive_automation_bp.route('/api/google-drive/automation/triggers/types', methods=['GET'])
async def get_trigger_types():
    """Get available trigger types"""
    try:
        trigger_types = [
            {
                "type": trigger_type.value,
                "name": trigger_type.value.replace("_", " ").title(),
                "description": f"Triggers when a {trigger_type.value.replace('_', ' ')} occurs in Google Drive"
            }
            for trigger_type in TriggerType
        ]
        
        return jsonify({
            "ok": True,
            "trigger_types": trigger_types
        })
        
    except Exception as e:
        logger.error(f"Error getting trigger types: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/actions/types', methods=['GET'])
async def get_action_types():
    """Get available action types"""
    try:
        action_types = [
            {
                "type": action_type.value,
                "name": action_type.value.replace("_", " ").title(),
                "category": _get_action_category(action_type),
                "description": _get_action_description(action_type),
                "config_schema": _get_action_config_schema(action_type)
            }
            for action_type in ActionType
        ]
        
        # Group by category
        categories = {}
        for action_type in action_types:
            category = action_type["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(action_type)
        
        return jsonify({
            "ok": True,
            "action_types": action_types,
            "categories": categories
        })
        
    except Exception as e:
        logger.error(f"Error getting action types: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@google_drive_automation_bp.route('/api/google-drive/automation/operators', methods=['GET'])
async def get_operators():
    """Get available operators for conditions"""
    try:
        operators = [
            {
                "operator": operator.value,
                "name": operator.value.replace("_", " ").title(),
                "description": _get_operator_description(operator),
                "data_types": _get_operator_data_types(operator),
                "example": _get_operator_example(operator)
            }
            for operator in Operator
        ]
        
        return jsonify({
            "ok": True,
            "operators": operators
        })
        
    except Exception as e:
        logger.error(f"Error getting operators: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Helper Functions
# =============================================================================

def _get_action_category(action_type: ActionType) -> str:
    """Get action category"""
    categories = {
        ActionType.COPY_FILE: "File Operations",
        ActionType.MOVE_FILE: "File Operations",
        ActionType.DELETE_FILE: "File Operations",
        ActionType.RENAME_FILE: "File Operations",
        ActionType.CREATE_FOLDER: "File Operations",
        ActionType.SHARE_FILE: "File Operations",
        ActionType.UNSHARE_FILE: "File Operations",
        
        ActionType.EXTRACT_TEXT: "Content Operations",
        ActionType.COMPRESS_FILE: "Content Operations",
        ActionType.CONVERT_FILE: "Content Operations",
        ActionType.WATERMARK_FILE: "Content Operations",
        ActionType.ENCRYPT_FILE: "Content Operations",
        ActionType.DECRYPT_FILE: "Content Operations",
        
        ActionType.SEND_EMAIL: "Integration",
        ActionType.POST_TO_SLACK: "Integration",
        ActionType.ADD_TO_TRELLO: "Integration",
        ActionType.CREATE_JIRA_TICKET: "Integration",
        ActionType.UPDATE_DATABASE: "Integration",
        ActionType.CALL_WEBHOOK: "Integration",
        ActionType.EXECUTE_SCRIPT: "Integration",
        
        ActionType.START_WORKFLOW: "Workflow",
        ActionType.STOP_WORKFLOW: "Workflow",
        ActionType.DELAY: "Workflow",
        ActionType.CONDITION_CHECK: "Workflow",
        ActionType.PARALLEL_EXECUTION: "Workflow"
    }
    
    return categories.get(action_type, "Other")

def _get_action_description(action_type: ActionType) -> str:
    """Get action description"""
    descriptions = {
        ActionType.COPY_FILE: "Create a copy of a file",
        ActionType.MOVE_FILE: "Move a file to a different location",
        ActionType.DELETE_FILE: "Permanently delete a file",
        ActionType.RENAME_FILE: "Change the name of a file",
        ActionType.CREATE_FOLDER: "Create a new folder",
        ActionType.SHARE_FILE: "Share a file with specified users",
        ActionType.UNSHARE_FILE: "Remove sharing permissions from a file",
        
        ActionType.EXTRACT_TEXT: "Extract text content from a file",
        ActionType.COMPRESS_FILE: "Compress file to reduce size",
        ActionType.CONVERT_FILE: "Convert file to a different format",
        ActionType.WATERMARK_FILE: "Add watermark to image files",
        ActionType.ENCRYPT_FILE: "Encrypt file with password protection",
        ActionType.DECRYPT_FILE: "Decrypt password-protected files",
        
        ActionType.SEND_EMAIL: "Send email notification",
        ActionType.POST_TO_SLACK: "Post message to Slack channel",
        ActionType.ADD_TO_TRELLO: "Create card in Trello board",
        ActionType.CREATE_JIRA_TICKET: "Create ticket in Jira project",
        ActionType.UPDATE_DATABASE: "Update database record",
        ActionType.CALL_WEBHOOK: "Make HTTP request to webhook URL",
        ActionType.EXECUTE_SCRIPT: "Execute custom script",
        
        ActionType.START_WORKFLOW: "Start another workflow",
        ActionType.STOP_WORKFLOW: "Stop a running workflow",
        ActionType.DELAY: "Pause execution for specified duration",
        ActionType.CONDITION_CHECK: "Check conditions and branch logic",
        ActionType.PARALLEL_EXECUTION: "Execute actions in parallel"
    }
    
    return descriptions.get(action_type, "No description available")

def _get_action_config_schema(action_type: ActionType) -> Dict[str, Any]:
    """Get action configuration schema"""
    schemas = {
        ActionType.COPY_FILE: {
            "file_id": {"type": "string", "required": True, "description": "Source file ID"},
            "new_name": {"type": "string", "required": False, "description": "New file name"},
            "parent_ids": {"type": "array", "required": False, "description": "Destination folder IDs"}
        },
        
        ActionType.SEND_EMAIL: {
            "to": {"type": "array", "required": True, "description": "Recipient email addresses"},
            "subject": {"type": "string", "required": True, "description": "Email subject"},
            "body": {"type": "string", "required": True, "description": "Email body"},
            "attachments": {"type": "array", "required": False, "description": "File attachments"}
        },
        
        ActionType.POST_TO_SLACK: {
            "channel": {"type": "string", "required": True, "description": "Slack channel name"},
            "message": {"type": "string", "required": True, "description": "Message to post"},
            "webhook_url": {"type": "string", "required": False, "description": "Slack webhook URL"}
        },
        
        ActionType.DELAY: {
            "duration": {"type": "integer", "required": True, "description": "Delay duration in seconds"}
        },
        
        ActionType.CONDITION_CHECK: {
            "conditions": {"type": "array", "required": True, "description": "Conditions to check"},
            "logic": {"type": "string", "required": False, "default": "and", "description": "Logic operator"}
        }
    }
    
    return schemas.get(action_type, {})

def _get_operator_description(operator: Operator) -> str:
    """Get operator description"""
    descriptions = {
        Operator.EQUALS: "Values are exactly equal",
        Operator.NOT_EQUALS: "Values are not equal",
        Operator.CONTAINS: "Value contains the specified text",
        Operator.NOT_CONTAINS: "Value does not contain the specified text",
        Operator.STARTS_WITH: "Value starts with the specified text",
        Operator.ENDS_WITH: "Value ends with the specified text",
        Operator.GREATER_THAN: "Value is greater than the specified value",
        Operator.LESS_THAN: "Value is less than the specified value",
        Operator.GREATER_EQUAL: "Value is greater than or equal to the specified value",
        Operator.LESS_EQUAL: "Value is less than or equal to the specified value",
        Operator.REGEX_MATCH: "Value matches the regular expression",
        Operator.IN: "Value is in the specified list",
        Operator.NOT_IN: "Value is not in the specified list",
        Operator.IS_EMPTY: "Value is empty",
        Operator.IS_NOT_EMPTY: "Value is not empty",
        Operator.IS_TRUE: "Value is true",
        Operator.IS_FALSE: "Value is false"
    }
    
    return descriptions.get(operator, "No description available")

def _get_operator_data_types(operator: Operator) -> List[str]:
    """Get compatible data types for operator"""
    data_types = {
        Operator.EQUALS: ["string", "number", "boolean", "date"],
        Operator.NOT_EQUALS: ["string", "number", "boolean", "date"],
        Operator.CONTAINS: ["string", "array"],
        Operator.NOT_CONTAINS: ["string", "array"],
        Operator.STARTS_WITH: ["string"],
        Operator.ENDS_WITH: ["string"],
        Operator.GREATER_THAN: ["number", "date"],
        Operator.LESS_THAN: ["number", "date"],
        Operator.GREATER_EQUAL: ["number", "date"],
        Operator.LESS_EQUAL: ["number", "date"],
        Operator.REGEX_MATCH: ["string"],
        Operator.IN: ["string", "number"],
        Operator.NOT_IN: ["string", "number"],
        Operator.IS_EMPTY: ["string", "array", "object"],
        Operator.IS_NOT_EMPTY: ["string", "array", "object"],
        Operator.IS_TRUE: ["boolean"],
        Operator.IS_FALSE: ["boolean"]
    }
    
    return data_types.get(operator, ["string"])

def _get_operator_example(operator: Operator) -> str:
    """Get operator example"""
    examples = {
        Operator.EQUALS: 'file_name == "document.pdf"',
        Operator.NOT_EQUALS: 'file_size != 0',
        Operator.CONTAINS: 'mime_type contains "image/"',
        Operator.NOT_CONTAINS: 'file_name not contains "temp"',
        Operator.STARTS_WITH: 'file_name starts_with "Report_"',
        Operator.ENDS_WITH: 'file_name ends_with ".pdf"',
        Operator.GREATER_THAN: 'file_size > 1048576',
        Operator.LESS_THAN: 'file_size < 10485760',
        Operator.GREATER_EQUAL: 'file_size >= 1048576',
        Operator.LESS_EQUAL: 'file_size <= 10485760',
        Operator.REGEX_MATCH: 'file_name matches "^Report_\\d{4}.pdf$"',
        Operator.IN: 'file_extension in ["pdf", "doc", "docx"]',
        Operator.NOT_IN: 'file_extension not in ["tmp", "temp"]',
        Operator.IS_EMPTY: 'description is empty',
        Operator.IS_NOT_EMPTY: 'description is not empty',
        Operator.IS_TRUE: 'shared is true',
        Operator.IS_FALSE: 'trashed is false'
    }
    
    return examples.get(operator, "No example available")

# Export blueprint and registration function
def register_google_drive_automation_blueprint(app):
    """Register Google Drive automation blueprint with Flask app"""
    app.register_blueprint(google_drive_automation_bp, url_prefix='/api/google-drive')
    
    logger.info("Google Drive Automation blueprint registered successfully")
    return True

# Export blueprint for direct registration
__all__ = [
    "register_google_drive_automation_blueprint",
    "google_drive_automation_bp",
    "set_database_pool",
    "initialize_automation_service"
]