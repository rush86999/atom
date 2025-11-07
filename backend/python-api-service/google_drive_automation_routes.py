"""
Google Drive Automation API Routes
Endpoints for workflow management, triggers, and automation execution
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from contextlib import asynccontextmanager

# Google Drive imports
try:
    from google_drive_service import get_google_drive_service
    from google_drive_auth import get_google_drive_auth
    from google_drive_automation_engine import get_automation_engine, Workflow, TriggerType, ActionType
    from google_drive_trigger_system import get_google_drive_trigger_system
    from google_drive_action_system import get_google_drive_action_system
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logging.warning("Google Drive services not available")

# Local imports
from loguru import logger

# Create Blueprint
automation_bp = Blueprint('automation', __name__, url_prefix='/api/google-drive/automation')

# ==================== DECORATORS ====================

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.headers.get('X-Session-ID') or request.json.get('session_id') if request.json else None
        
        if not session_id:
            return jsonify({
                "success": False,
                "error": "Session ID required"
            }), 401
        
        # Validate session
        async def validate():
            auth_service = await get_google_drive_auth()
            if not auth_service:
                return None
            
            return await auth_service.validate_session(session_id)
        
        # Run validation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(validate())
        finally:
            loop.close()
        
        if not result or not result.get("valid"):
            return jsonify({
                "success": False,
                "error": result.get("error", "Invalid session")
            }), 401
        
        # Store session in request context
        request.google_drive_session = result
        
        return f(*args, **kwargs)
    
    return decorated_function

def async_route(f):
    """Decorator for async routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(f(*args, **kwargs))
            return result
        finally:
            loop.close()
    
    return decorated_function

# ==================== WORKFLOW MANAGEMENT ROUTES ====================

@automation_bp.route('/workflows', methods=['POST'])
@require_auth
@async_route
async def create_workflow():
    """Create new automation workflow"""
    
    try:
        data = request.json or {}
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({
                "success": False,
                "error": "Workflow name is required"
            }), 400
        
        if not data.get('triggers'):
            return jsonify({
                "success": False,
                "error": "At least one trigger is required"
            }), 400
        
        if not data.get('actions'):
            return jsonify({
                "success": False,
                "error": "At least one action is required"
            }), 400
        
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # Set creator
        session_data = request.google_drive_session
        data['created_by'] = session_data['session']['user_id']
        
        # Create workflow
        result = await automation_engine.create_workflow(data)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/workflows/<workflow_id>', methods=['GET'])
@require_auth
@async_route
async def get_workflow(workflow_id: str):
    """Get workflow by ID"""
    
    try:
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # Get workflow
        result = await automation_engine.get_workflow(workflow_id)
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to get workflow: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/workflows/<workflow_id>', methods=['PUT'])
@require_auth
@async_route
async def update_workflow(workflow_id: str):
    """Update existing workflow"""
    
    try:
        data = request.json or {}
        
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # Update workflow
        result = await automation_engine.update_workflow(workflow_id, data)
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to update workflow: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/workflows/<workflow_id>', methods=['DELETE'])
@require_auth
@async_route
async def delete_workflow(workflow_id: str):
    """Delete workflow"""
    
    try:
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # Delete workflow
        result = await automation_engine.delete_workflow(workflow_id)
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/workflows', methods=['GET'])
@require_auth
@async_route
async def list_workflows():
    """List automation workflows"""
    
    try:
        # Get query parameters
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        tags = request.args.getlist('tags')
        created_by = request.args.get('created_by')
        
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # List workflows
        result = await automation_engine.list_workflows(
            enabled_only=enabled_only,
            page=page,
            limit=limit,
            tags=tags,
            created_by=created_by
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== WORKFLOW EXECUTION ROUTES ====================

@automation_bp.route('/workflows/<workflow_id>/execute', methods=['POST'])
@require_auth
@async_route
async def execute_workflow(workflow_id: str):
    """Manually execute workflow"""
    
    try:
        data = request.json or {}
        trigger_data = data.get('trigger_data', {})
        
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # Execute workflow
        result = await automation_engine.execute_workflow(
            workflow_id=workflow_id,
            trigger_data=trigger_data,
            manual_trigger=True
        )
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/executions/<execution_id>', methods=['GET'])
@require_auth
@async_route
async def get_execution(execution_id: str):
    """Get workflow execution by ID"""
    
    try:
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # Get execution
        result = await automation_engine.get_execution(execution_id)
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to get execution: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/executions/<execution_id>/cancel', methods=['POST'])
@require_auth
@async_route
async def cancel_execution(execution_id: str):
    """Cancel workflow execution"""
    
    try:
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # Cancel execution
        result = await automation_engine.cancel_execution(execution_id)
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to cancel execution: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/executions', methods=['GET'])
@require_auth
@async_route
async def list_executions():
    """List workflow executions"""
    
    try:
        # Get query parameters
        workflow_id = request.args.get('workflow_id')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        # Get automation engine
        automation_engine = await get_automation_engine()
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Automation engine not available"
            }), 500
        
        # List executions
        result = await automation_engine.list_executions(
            workflow_id=workflow_id,
            status=status,
            page=page,
            limit=limit
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to list executions: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== TRIGGER SYSTEM ROUTES ====================

@automation_bp.route('/triggers/webhook', methods=['POST'])
@async_route
async def handle_webhook_trigger():
    """Handle webhook trigger from Google Drive"""
    
    try:
        # Get request data
        request_data = request.json or {}
        headers = dict(request.headers)
        
        # Get trigger system
        trigger_system = await get_google_drive_trigger_system()
        if not trigger_system:
            return jsonify({
                "success": False,
                "error": "Trigger system not available"
            }), 500
        
        # Handle webhook
        result, status_code = trigger_system.handle_webhook(request_data, headers)
        
        return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Failed to handle webhook: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/triggers/webhooks', methods=['POST'])
@require_auth
@async_route
async def create_webhook_subscription():
    """Create webhook subscription"""
    
    try:
        data = request.json or {}
        
        webhook_url = data.get('webhook_url')
        resource_id = data.get('resource_id', 'root')
        resource_type = data.get('resource_type', 'folder')
        
        if not webhook_url:
            return jsonify({
                "success": False,
                "error": "webhook_url is required"
            }), 400
        
        # Get trigger system
        trigger_system = await get_google_drive_trigger_system()
        if not trigger_system:
            return jsonify({
                "success": False,
                "error": "Trigger system not available"
            }), 500
        
        # Create subscription
        result = await trigger_system.create_webhook_subscription(
            webhook_url=webhook_url,
            resource_id=resource_id,
            resource_type=resource_type
        )
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to create webhook subscription: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/triggers/webhooks/<subscription_id>/renew', methods=['POST'])
@require_auth
@async_route
async def renew_webhook_subscription(subscription_id: str):
    """Renew webhook subscription"""
    
    try:
        # Get trigger system
        trigger_system = await get_google_drive_trigger_system()
        if not trigger_system:
            return jsonify({
                "success": False,
                "error": "Trigger system not available"
            }), 500
        
        # Renew subscription
        result = await trigger_system.renew_webhook_subscription(subscription_id)
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to renew webhook subscription: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/triggers/webhooks/<subscription_id>', methods=['DELETE'])
@require_auth
@async_route
async def delete_webhook_subscription(subscription_id: str):
    """Delete webhook subscription"""
    
    try:
        # Get trigger system
        trigger_system = await get_google_drive_trigger_system()
        if not trigger_system:
            return jsonify({
                "success": False,
                "error": "Trigger system not available"
            }), 500
        
        # Delete subscription
        result = await trigger_system.delete_webhook_subscription(subscription_id)
        
        if not result['success']:
            if 'not found' in result.get('error', '').lower():
                return jsonify(result), 404
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Failed to delete webhook subscription: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/triggers/webhooks', methods=['GET'])
@require_auth
@async_route
async def list_webhook_subscriptions():
    """List webhook subscriptions"""
    
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        # Get trigger system
        trigger_system = await get_google_drive_trigger_system()
        if not trigger_system:
            return jsonify({
                "success": False,
                "error": "Trigger system not available"
            }), 500
        
        # Get subscriptions
        subscriptions = await trigger_system.get_webhook_subscriptions(active_only=active_only)
        
        return jsonify({
            "success": True,
            "subscriptions": subscriptions,
            "count": len(subscriptions)
        })
    
    except Exception as e:
        logger.error(f"Failed to list webhook subscriptions: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== ACTION SYSTEM ROUTES ====================

@automation_bp.route('/actions/copy-file', methods=['POST'])
@require_auth
@async_route
async def action_copy_file():
    """Execute copy file action"""
    
    try:
        data = request.json or {}
        
        file_id = data.get('file_id')
        target_locations = data.get('target_locations', [])
        new_name_pattern = data.get('new_name_pattern')
        
        if not file_id:
            return jsonify({
                "success": False,
                "error": "file_id is required"
            }), 400
        
        if not target_locations:
            return jsonify({
                "success": False,
                "error": "target_locations is required"
            }), 400
        
        # Get action system
        action_system = await get_google_drive_action_system()
        if not action_system:
            return jsonify({
                "success": False,
                "error": "Action system not available"
            }), 500
        
        # Create action context
        from google_drive_action_system import ActionContext
        
        session_data = request.google_drive_session
        context = ActionContext(
            execution_id=f"manual_{datetime.utcnow().isoformat()}",
            workflow_id="manual_action",
            action_type="copy_file",
            user_context={
                "user_id": session_data['session']['user_id'],
                "session_id": session_data['session']['session_id']
            }
        )
        
        # Execute action
        result = await action_system.copy_file_to_multiple_locations(
            context=context,
            file_id=file_id,
            target_locations=target_locations,
            new_name_pattern=new_name_pattern
        )
        
        return jsonify({
            "success": result.success,
            "result": result.to_dict(),
            "message": result.message
        })
    
    except Exception as e:
        logger.error(f"Failed to execute copy file action: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/actions/send-notification', methods=['POST'])
@require_auth
@async_route
async def action_send_notification():
    """Execute send notification action"""
    
    try:
        data = request.json or {}
        
        notification_type_str = data.get('notification_type', 'info')
        title = data.get('title', 'Notification')
        message = data.get('message', '')
        recipients = data.get('recipients', [])
        delivery_methods = data.get('delivery_methods', ['webhook'])
        priority = data.get('priority', 'normal')
        
        if not message:
            return jsonify({
                "success": False,
                "error": "message is required"
            }), 400
        
        if not recipients:
            return jsonify({
                "success": False,
                "error": "recipients is required"
            }), 400
        
        # Convert notification type
        from google_drive_action_system import NotificationType
        
        try:
            notification_type = NotificationType(notification_type_str)
        except ValueError:
            notification_type = NotificationType.INFO
        
        # Get action system
        action_system = await get_google_drive_action_system()
        if not action_system:
            return jsonify({
                "success": False,
                "error": "Action system not available"
            }), 500
        
        # Create action context
        from google_drive_action_system import ActionContext
        
        session_data = request.google_drive_session
        context = ActionContext(
            execution_id=f"manual_{datetime.utcnow().isoformat()}",
            workflow_id="manual_action",
            action_type="send_notification",
            user_context={
                "user_id": session_data['session']['user_id'],
                "session_id": session_data['session']['session_id']
            }
        )
        
        # Execute action
        result = await action_system.send_notification(
            context=context,
            notification_type=notification_type,
            title=title,
            message=message,
            recipients=recipients,
            delivery_methods=delivery_methods,
            priority=priority
        )
        
        return jsonify({
            "success": result.success,
            "result": result.to_dict(),
            "message": result.message
        })
    
    except Exception as e:
        logger.error(f"Failed to execute send notification action: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/actions/process-content-batch', methods=['POST'])
@require_auth
@async_route
async def action_process_content_batch():
    """Execute process content batch action"""
    
    try:
        data = request.json or {}
        
        file_ids = data.get('file_ids', [])
        processing_options = data.get('processing_options', {
            "generate_embeddings": True,
            "extract_text": True
        })
        
        if not file_ids:
            return jsonify({
                "success": False,
                "error": "file_ids is required"
            }), 400
        
        # Get action system
        action_system = await get_google_drive_action_system()
        if not action_system:
            return jsonify({
                "success": False,
                "error": "Action system not available"
            }), 500
        
        # Create action context
        from google_drive_action_system import ActionContext
        
        session_data = request.google_drive_session
        context = ActionContext(
            execution_id=f"manual_{datetime.utcnow().isoformat()}",
            workflow_id="manual_action",
            action_type="process_content_batch",
            user_context={
                "user_id": session_data['session']['user_id'],
                "session_id": session_data['session']['session_id']
            }
        )
        
        # Execute action
        result = await action_system.process_content_batch(
            context=context,
            file_ids=file_ids,
            processing_options=processing_options
        )
        
        return jsonify({
            "success": result.success,
            "result": result.to_dict(),
            "message": result.message
        })
    
    except Exception as e:
        logger.error(f"Failed to execute process content batch action: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/actions/execute-script', methods=['POST'])
@require_auth
@async_route
async def action_execute_script():
    """Execute custom script action"""
    
    try:
        data = request.json or {}
        
        script_path = data.get('script_path')
        script_args = data.get('script_args', {})
        working_directory = data.get('working_directory')
        
        if not script_path:
            return jsonify({
                "success": False,
                "error": "script_path is required"
            }), 400
        
        # Get action system
        action_system = await get_google_drive_action_system()
        if not action_system:
            return jsonify({
                "success": False,
                "error": "Action system not available"
            }), 500
        
        # Create action context
        from google_drive_action_system import ActionContext
        
        session_data = request.google_drive_session
        context = ActionContext(
            execution_id=f"manual_{datetime.utcnow().isoformat()}",
            workflow_id="manual_action",
            action_type="execute_script",
            user_context={
                "user_id": session_data['session']['user_id'],
                "session_id": session_data['session']['session_id']
            }
        )
        
        # Execute action
        result = await action_system.execute_custom_script(
            context=context,
            script_path=script_path,
            script_args=script_args,
            working_directory=working_directory
        )
        
        return jsonify({
            "success": result.success,
            "result": result.to_dict(),
            "message": result.message
        })
    
    except Exception as e:
        logger.error(f"Failed to execute script action: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==================== UTILITY ROUTES ====================

@automation_bp.route('/automation-stats', methods=['GET'])
@require_auth
@async_route
async def get_automation_stats():
    """Get automation system statistics"""
    
    try:
        stats = {
            "automation_engine": {},
            "trigger_system": {},
            "action_system": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get automation engine stats
        automation_engine = await get_automation_engine()
        if automation_engine:
            stats["automation_engine"] = await automation_engine.get_engine_stats()
        
        # Get trigger system stats
        trigger_system = await get_google_drive_trigger_system()
        if trigger_system:
            stats["trigger_system"] = await trigger_system.get_trigger_stats()
        
        # Get action system stats
        action_system = await get_google_drive_action_system()
        if action_system:
            stats["action_system"] = action_system.get_action_stats()
        
        return jsonify({
            "success": True,
            "stats": stats
        })
    
    except Exception as e:
        logger.error(f"Failed to get automation stats: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/recent-actions', methods=['GET'])
@require_auth
@async_route
async def get_recent_actions():
    """Get recent action executions"""
    
    try:
        limit = int(request.args.get('limit', 50))
        
        # Get action system
        action_system = await get_google_drive_action_system()
        if not action_system:
            return jsonify({
                "success": False,
                "error": "Action system not available"
            }), 500
        
        # Get recent actions
        actions = action_system.get_recent_actions(limit=limit)
        
        return jsonify({
            "success": True,
            "actions": actions,
            "count": len(actions)
        })
    
    except Exception as e:
        logger.error(f"Failed to get recent actions: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/supported-triggers', methods=['GET'])
def get_supported_triggers():
    """Get list of supported trigger types"""
    
    try:
        triggers = [
            {
                "type": "file_created",
                "description": "Triggered when a new file is created",
                "data_available": ["file_id", "file_name", "mime_type", "size", "parent_folder"]
            },
            {
                "type": "file_updated",
                "description": "Triggered when an existing file is modified",
                "data_available": ["file_id", "file_name", "mime_type", "size", "modified_time"]
            },
            {
                "type": "file_deleted",
                "description": "Triggered when a file is deleted",
                "data_available": ["file_id", "file_name", "mime_type"]
            },
            {
                "type": "file_shared",
                "description": "Triggered when a file is shared",
                "data_available": ["file_id", "file_name", "shared_with", "permission_level"]
            },
            {
                "type": "scheduled",
                "description": "Triggered on a schedule",
                "data_available": ["schedule", "last_run", "next_run"]
            },
            {
                "type": "manual",
                "description": "Triggered manually",
                "data_available": ["user_id", "manual_trigger", "custom_data"]
            }
        ]
        
        return jsonify({
            "success": True,
            "triggers": triggers,
            "count": len(triggers)
        })
    
    except Exception as e:
        logger.error(f"Failed to get supported triggers: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@automation_bp.route('/supported-actions', methods=['GET'])
def get_supported_actions():
    """Get list of supported action types"""
    
    try:
        actions = [
            {
                "type": "copy_file",
                "description": "Copy file to one or more locations",
                "config": ["file_id", "target_locations", "new_name_pattern"],
                "returns": ["copied_files", "file_ids"]
            },
            {
                "type": "move_file",
                "description": "Move file to different folder",
                "config": ["file_id", "target_folder_id"],
                "returns": ["moved_file", "new_location"]
            },
            {
                "type": "delete_file",
                "description": "Delete file permanently or move to trash",
                "config": ["file_id", "permanent"],
                "returns": ["deleted_file"]
            },
            {
                "type": "rename_file",
                "description": "Rename file with new name or pattern",
                "config": ["file_id", "new_name", "name_pattern"],
                "returns": ["renamed_file", "new_name"]
            },
            {
                "type": "create_folder",
                "description": "Create new folder",
                "config": ["folder_name", "parent_folder_id"],
                "returns": ["created_folder", "folder_id"]
            },
            {
                "type": "send_notification",
                "description": "Send notification via email, Slack, Teams, webhook",
                "config": ["message", "title", "recipients", "delivery_methods", "priority"],
                "returns": ["notification_sent", "delivery_results"]
            },
            {
                "type": "extract_text",
                "description": "Extract text content from file",
                "config": ["file_id", "ocr_enabled", "language"],
                "returns": ["extracted_text", "content_length", "processing_method"]
            },
            {
                "type": "generate_embeddings",
                "description": "Generate vector embeddings for file content",
                "config": ["file_id", "text_content", "embedding_model"],
                "returns": ["embedding_id", "vector_dimension", "model_used"]
            },
            {
                "type": "add_labels",
                "description": "Add labels or metadata to file",
                "config": ["file_id", "labels", "properties"],
                "returns": ["added_labels", "updated_metadata"]
            },
            {
                "type": "set_permissions",
                "description": "Set file sharing permissions",
                "config": ["file_id", "permissions", "remove_existing"],
                "returns": ["updated_permissions", "access_granted"]
            },
            {
                "type": "webhook_call",
                "description": "Make HTTP webhook call to external service",
                "config": ["webhook_url", "method", "headers", "payload"],
                "returns": ["webhook_response", "status_code", "response_data"]
            },
            {
                "type": "custom_script",
                "description": "Execute custom script with file data",
                "config": ["script_path", "script_args", "timeout", "working_directory"],
                "returns": ["script_output", "exit_code", "execution_time"]
            }
        ]
        
        return jsonify({
            "success": True,
            "actions": actions,
            "count": len(actions)
        })
    
    except Exception as e:
        logger.error(f"Failed to get supported actions: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Register routes with app
def register_automation_routes(app):
    """Register automation routes with Flask app"""
    
    if GOOGLE_DRIVE_AVAILABLE:
        app.register_blueprint(automation_bp)
        logger.info("Google Drive automation routes registered")
    else:
        logger.warning("Google Drive automation routes not registered - services not available")

# Export blueprint and registration function
__all__ = [
    'automation_bp',
    'register_automation_routes'
]