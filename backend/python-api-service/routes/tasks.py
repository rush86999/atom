"""
Tasks API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import db, Task, User
from ..utils import generate_uuid, validate_task_data
import logging

tasks_bp = Blueprint('tasks', __name__)
logger = logging.getLogger(__name__)

@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    """Get all tasks for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        tasks = Task.query.filter_by(user_id=user_id).all()
        return jsonify([task.to_dict() for task in tasks])
    except Exception as e:
        logger.error(f'Error fetching tasks: {str(e)}')
        return jsonify({'error': 'Failed to fetch tasks'}), 500

@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    """Create a new task"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('title'):
            return jsonify({'error': 'Task title is required'}), 400

        # Validate task data
        validation_error = validate_task_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        task = Task(
            id=generate_uuid(),
            user_id=user_id,
            title=data['title'],
            description=data.get('description', ''),
            status=data.get('status', 'pending'),
            priority=data.get('priority', 'medium'),
            due_date=data.get('due_date'),
            is_important=data.get('is_important', False),
            assignee=data.get('assignee'),
            tags=data.get('tags', []),
            subtasks=data.get('subtasks', [])
        )

        db.session.add(task)
        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('task:created', task.to_dict(), room=user_id)

        logger.info(f'Task created: {task.id} for user {user_id}')
        return jsonify(task.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating task: {str(e)}')
        return jsonify({'error': 'Failed to create task'}), 500

@tasks_bp.route('/<task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """Get a specific task"""
    try:
        user_id = get_jwt_identity()
        task = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        return jsonify(task.to_dict())
    except Exception as e:
        logger.error(f'Error fetching task {task_id}: {str(e)}')
        return jsonify({'error': 'Failed to fetch task'}), 500

@tasks_bp.route('/<task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    """Update a task"""
    try:
        user_id = get_jwt_identity()
        task = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate task data
        validation_error = validate_task_data(data, partial=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        # Update task fields
        for field in ['title', 'description', 'status', 'priority', 'due_date',
                     'is_important', 'assignee', 'tags', 'subtasks']:
            if field in data:
                setattr(task, field, data[field])

        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('task:updated', task.to_dict(), room=user_id)

        logger.info(f'Task updated: {task_id} for user {user_id}')
        return jsonify(task.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating task {task_id}: {str(e)}')
        return jsonify({'error': 'Failed to update task'}), 500

@tasks_bp.route('/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """Delete a task"""
    try:
        user_id = get_jwt_identity()
        task = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        db.session.delete(task)
        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('task:deleted', {'id': task_id}, room=user_id)

        logger.info(f'Task deleted: {task_id} for user {user_id}')
        return jsonify({'message': 'Task deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting task {task_id}: {str(e)}')
        return jsonify({'error': 'Failed to delete task'}), 500

@tasks_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_task_stats():
    """Get task statistics for the current user"""
    try:
        user_id = get_jwt_identity()
        tasks = Task.query.filter_by(user_id=user_id).all()

        stats = {
            'total': len(tasks),
            'completed': len([t for t in tasks if t.status == 'completed']),
            'pending': len([t for t in tasks if t.status == 'pending']),
            'in_progress': len([t for t in tasks if t.status == 'in_progress']),
            'overdue': len([t for t in tasks if t.due_date and t.due_date < datetime.utcnow() and t.status != 'completed'])
        }

        return jsonify(stats)
    except Exception as e:
        logger.error(f'Error fetching task stats: {str(e)}')
        return jsonify({'error': 'Failed to fetch task statistics'}), 500
