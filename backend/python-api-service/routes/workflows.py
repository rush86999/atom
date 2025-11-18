"""
Workflows API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Workflow, User
from utils import generate_uuid, validate_workflow_data
from datetime import datetime
import logging

workflows_bp = Blueprint('workflows', __name__)
logger = logging.getLogger(__name__)

@workflows_bp.route('', methods=['GET'])
@jwt_required()
def get_workflows():
    """Get all workflows for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        workflows = Workflow.query.filter_by(user_id=user_id).all()
        return jsonify([workflow.to_dict() for workflow in workflows])
    except Exception as e:
        logger.error(f'Error fetching workflows: {str(e)}')
        return jsonify({'error': 'Failed to fetch workflows'}), 500

@workflows_bp.route('', methods=['POST'])
@jwt_required()
def create_workflow():
    """Create a new workflow"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('name') or not data.get('triggers') or not data.get('actions'):
            return jsonify({'error': 'Name, triggers, and actions are required'}), 400

        # Validate workflow data
        validation_error = validate_workflow_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        workflow = Workflow(
            id=generate_uuid(),
            user_id=user_id,
            name=data['name'],
            description=data.get('description', ''),
            enabled=data.get('enabled', True),
            triggers=data['triggers'],
            actions=data['actions'],
            execution_count=0,
            last_executed=None
        )

        db.session.add(workflow)
        db.session.commit()

        logger.info(f'Workflow created: {workflow.id} for user {user_id}')
        return jsonify(workflow.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating workflow: {str(e)}')
        return jsonify({'error': 'Failed to create workflow'}), 500

@workflows_bp.route('/<workflow_id>', methods=['GET'])
@jwt_required()
def get_workflow(workflow_id):
    """Get a specific workflow"""
    try:
        user_id = get_jwt_identity()
        workflow = Workflow.query.filter_by(id=workflow_id, user_id=user_id).first()
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404

        return jsonify(workflow.to_dict())
    except Exception as e:
        logger.error(f'Error fetching workflow {workflow_id}: {str(e)}')
        return jsonify({'error': 'Failed to fetch workflow'}), 500

@workflows_bp.route('/<workflow_id>', methods=['PUT'])
@jwt_required()
def update_workflow(workflow_id):
    """Update a workflow"""
    try:
        user_id = get_jwt_identity()
        workflow = Workflow.query.filter_by(id=workflow_id, user_id=user_id).first()
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate workflow data
        validation_error = validate_workflow_data(data, partial=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        # Update workflow fields
        for field in ['name', 'description', 'enabled', 'triggers', 'actions']:
            if field in data:
                setattr(workflow, field, data[field])

        db.session.commit()

        logger.info(f'Workflow updated: {workflow_id} for user {user_id}')
        return jsonify(workflow.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating workflow {workflow_id}: {str(e)}')
        return jsonify({'error': 'Failed to update workflow'}), 500

@workflows_bp.route('/<workflow_id>', methods=['DELETE'])
@jwt_required()
def delete_workflow(workflow_id):
    """Delete a workflow"""
    try:
        user_id = get_jwt_identity()
        workflow = Workflow.query.filter_by(id=workflow_id, user_id=user_id).first()
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404

        db.session.delete(workflow)
        db.session.commit()

        logger.info(f'Workflow deleted: {workflow_id} for user {user_id}')
        return jsonify({'message': 'Workflow deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting workflow {workflow_id}: {str(e)}')
        return jsonify({'error': 'Failed to delete workflow'}), 500

@workflows_bp.route('/<workflow_id>/execute', methods=['POST'])
@jwt_required()
def execute_workflow(workflow_id):
    """Execute a workflow manually"""
    try:
        user_id = get_jwt_identity()
        workflow = Workflow.query.filter_by(id=workflow_id, user_id=user_id).first()
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404

        if not workflow.enabled:
            return jsonify({'error': 'Workflow is disabled'}), 400

        # Here you would implement actual workflow execution logic
        # For now, simulate execution
        import time
        start_time = time.time()

        # Simulate workflow execution
        time.sleep(0.5)

        execution_time = time.time() - start_time

        # Update workflow stats
        workflow.execution_count += 1
        workflow.last_executed = datetime.utcnow()
        db.session.commit()

        result = {
            'workflow_id': workflow_id,
            'status': 'success',
            'execution_time': execution_time,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Emit real-time update
        from app import socketio
        socketio.emit('workflow:executed:realtime', result, room=user_id)

        logger.info(f'Workflow executed: {workflow_id} for user {user_id}')
        return jsonify(result)
    except Exception as e:
        logger.error(f'Error executing workflow {workflow_id}: {str(e)}')

        # Emit failure event
        from app import socketio
        socketio.emit('workflow:execution:failed', {
            'workflow_id': workflow_id,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, room=user_id)

        return jsonify({'error': 'Failed to execute workflow'}), 500

@workflows_bp.route('/<workflow_id>/toggle', methods=['POST'])
@jwt_required()
def toggle_workflow(workflow_id):
    """Enable or disable a workflow"""
    try:
        user_id = get_jwt_identity()
        workflow = Workflow.query.filter_by(id=workflow_id, user_id=user_id).first()
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404

        workflow.enabled = not workflow.enabled
        db.session.commit()

        logger.info(f'Workflow {"enabled" if workflow.enabled else "disabled"}: {workflow_id} for user {user_id}')
        return jsonify(workflow.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error toggling workflow {workflow_id}: {str(e)}')
        return jsonify({'error': 'Failed to toggle workflow'}), 500

@workflows_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_workflow_stats():
    """Get workflow statistics for the current user"""
    try:
        user_id = get_jwt_identity()
        workflows = Workflow.query.filter_by(user_id=user_id).all()

        stats = {
            'total': len(workflows),
            'enabled': len([w for w in workflows if w.enabled]),
            'disabled': len([w for w in workflows if not w.enabled]),
            'total_executions': sum(w.execution_count for w in workflows),
            'recently_executed': len([w for w in workflows if w.last_executed and
                                     (datetime.utcnow() - w.last_executed).days <= 7])
        }

        return jsonify(stats)
    except Exception as e:
        logger.error(f'Error fetching workflow stats: {str(e)}')
        return jsonify({'error': 'Failed to fetch workflow statistics'}), 500

@workflows_bp.route('/templates', methods=['GET'])
def get_workflow_templates():
    """Get available workflow templates"""
    templates = [
        {
            'id': 'sync-github-jira',
            'name': 'Sync GitHub Issues to Jira',
            'description': 'Automatically create Jira tickets when GitHub issues are opened',
            'category': 'Development',
            'triggers': [
                {
                    'type': 'github_issue_opened',
                    'config': {
                        'repository': 'your-repo'
                    }
                }
            ],
            'actions': [
                {
                    'type': 'jira_create_ticket',
                    'config': {
                        'project': 'PROJ',
                        'issue_type': 'Task'
                    }
                }
            ]
        },
        {
            'id': 'email-notification',
            'name': 'Email Notification on Task Due',
            'description': 'Send email reminders when tasks are approaching their due date',
            'category': 'Productivity',
            'triggers': [
                {
                    'type': 'task_due_soon',
                    'config': {
                        'hours_before': 24
                    }
                }
            ],
            'actions': [
                {
                    'type': 'send_email',
                    'config': {
                        'template': 'task_reminder'
                    }
                }
            ]
        },
        {
            'id': 'calendar-sync',
            'name': 'Sync Calendar Events',
            'description': 'Automatically sync calendar events across different platforms',
            'category': 'Scheduling',
            'triggers': [
                {
                    'type': 'calendar_event_created',
                    'config': {
                        'calendar': 'primary'
                    }
                }
            ],
            'actions': [
                {
                    'type': 'sync_to_external_calendar',
                    'config': {
                        'target_calendar': 'work'
                    }
                }
            ]
        }
    ]

    return jsonify(templates)
