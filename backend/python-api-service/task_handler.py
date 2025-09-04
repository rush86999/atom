import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from db_utils import get_db_pool, execute_query, execute_insert, execute_update

# Create blueprint
task_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

logger = logging.getLogger(__name__)

@task_bp.route('', methods=['GET'])
async def get_tasks():
    """Get tasks for the authenticated user"""
    try:
        # In production, this would be extracted from JWT token
        user_id = request.args.get('user_id', 'demo_user')  # For development

        # Parse query parameters
        status = request.args.get('status')
        priority = request.args.get('priority')
        project = request.args.get('project')
        due_date_from = request.args.get('due_date_from')
        due_date_to = request.args.get('due_date_to')

        # Build base query
        query = """
            SELECT id, title, description, due_date, priority, status,
                   project, tags, created_at, updated_at
            FROM tasks
            WHERE user_id = %s AND deleted = false
        """
        params = [user_id]

        # Add filters
        if status:
            query += " AND status = %s"
            params.append(status)

        if priority:
            query += " AND priority = %s"
            params.append(priority)

        if project:
            query += " AND project = %s"
            params.append(project)

        if due_date_from:
            query += " AND due_date >= %s"
            params.append(due_date_from)

        if due_date_to:
            query += " AND due_date <= %s"
            params.append(due_date_to)

        # Add sorting
        query += " ORDER BY due_date ASC, priority DESC, created_at DESC"

        # Execute query
        tasks = await execute_query(query, tuple(params))

        return jsonify({
            'success': True,
            'tasks': tasks,
            'count': len(tasks)
        })

    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'tasks': []
        }), 500

@task_bp.route('', methods=['POST'])
async def create_task():
    """Create a new task"""
    try:
        user_id = request.json.get('user_id', 'demo_user')
        task_data = request.json.get('task', {})

        # Validate required fields
        if not task_data.get('title'):
            return jsonify({
                'success': False,
                'error': 'Task title is required'
            }), 400

        # Build insert query
        query = """
            INSERT INTO tasks
            (user_id, title, description, due_date, priority, status, project, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """

        params = (
            user_id,
            task_data.get('title'),
            task_data.get('description'),
            task_data.get('due_date'),
            task_data.get('priority', 'medium'),
            task_data.get('status', 'todo'),
            task_data.get('project'),
            task_data.get('tags')
        )

        # Execute insert
        task_id = await execute_insert(query, params)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Task created successfully'
        })

    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@task_bp.route('/<task_id>', methods=['PUT'])
async def update_task(task_id):
    """Update an existing task"""
    try:
        user_id = request.json.get('user_id', 'demo_user')
        updates = request.json.get('updates', {})

        if not updates:
            return jsonify({
                'success': False,
                'error': 'No updates provided'
            }), 400

        # Build update query
        set_clauses = []
        params = []

        for field, value in updates.items():
            if field in ['title', 'description', 'due_date', 'priority', 'status', 'project', 'tags']:
                set_clauses.append(f"{field} = %s")
                params.append(value)

        if not set_clauses:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400

        query = f"""
            UPDATE tasks
            SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """

        params.extend([task_id, user_id])

        # Execute update
        rows_affected = await execute_update(query, tuple(params))

        if rows_affected == 0:
            return jsonify({
                'success': False,
                'error': 'Task not found or access denied'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Task updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@task_bp.route('/<task_id>/complete', methods=['POST'])
async def complete_task(task_id):
    """Mark a task as completed"""
    try:
        user_id = request.json.get('user_id', 'demo_user')

        query = """
            UPDATE tasks
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """

        rows_affected = await execute_update(query, (task_id, user_id))

        if rows_affected == 0:
            return jsonify({
                'success': False,
                'error': 'Task not found or access denied'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Task marked as completed'
        })

    except Exception as e:
        logger.error(f"Error completing task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@task_bp.route('/<task_id>', methods=['DELETE'])
async def delete_task(task_id):
    """Soft delete a task"""
    try:
        user_id = request.json.get('user_id', 'demo_user')

        query = """
            UPDATE tasks
            SET deleted = true, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """

        rows_affected = await execute_update(query, (task_id, user_id))

        if rows_affected == 0:
            return jsonify({
                'success': False,
                'error': 'Task not found or access denied'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Task deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@task_bp.route('/stats', methods=['GET'])
async def get_task_stats():
    """Get task statistics for dashboard"""
    try:
        user_id = request.args.get('user_id', 'demo_user')

        # Get total tasks
        total_query = """
            SELECT COUNT(*) as total FROM tasks
            WHERE user_id = %s AND deleted = false
        """
        total_result = await execute_query(total_query, (user_id,))
        total_tasks = total_result[0]['total'] if total_result else 0

        # Get completed tasks
        completed_query = """
            SELECT COUNT(*) as completed FROM tasks
            WHERE user_id = %s AND status = 'completed' AND deleted = false
        """
        completed_result = await execute_query(completed_query, (user_id,))
        completed_tasks = completed_result[0]['completed'] if completed_result else 0

        # Get overdue tasks
        overdue_query = """
            SELECT COUNT(*) as overdue FROM tasks
            WHERE user_id = %s AND status != 'completed'
            AND due_date < CURRENT_TIMESTAMP AND deleted = false
        """
        overdue_result = await execute_query(overdue_query, (user_id,))
        overdue_tasks = overdue_result[0]['overdue'] if overdue_result else 0

        # Get tasks by status
        status_query = """
            SELECT status, COUNT(*) as count FROM tasks
            WHERE user_id = %s AND deleted = false
            GROUP BY status
        """
        status_result = await execute_query(status_query, (user_id,))
        status_counts = {row['status']: row['count'] for row in status_result}

        # Get tasks by priority
        priority_query = """
            SELECT priority, COUNT(*) as count FROM tasks
            WHERE user_id = %s AND deleted = false
            GROUP BY priority
        """
        priority_result = await execute_query(priority_query, (user_id,))
        priority_counts = {row['priority']: row['count'] for row in priority_result}

        return jsonify({
            'success': True,
            'stats': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'overdue_tasks': overdue_tasks,
                'status_counts': status_counts,
                'priority_counts': priority_counts
            }
        })

    except Exception as e:
        logger.error(f"Error getting task stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@task_bp.errorhandler(400)
def bad_request(error):
    return jsonify({
        'success': False,
        'error': 'Bad request',
        'message': str(error)
    }), 400

@task_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not found',
        'message': str(error)
    }), 404

@task_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': str(error)
    }), 500
