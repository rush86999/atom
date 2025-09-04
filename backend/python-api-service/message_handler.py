import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from db_utils import get_db_pool, execute_query, execute_insert, execute_update

# Create blueprint
message_bp = Blueprint('messages', __name__, url_prefix='/api/messages')

logger = logging.getLogger(__name__)

@message_bp.route('', methods=['GET'])
async def get_messages():
    """Get messages from all platforms for the authenticated user"""
    try:
        # In production, this would be extracted from JWT token
        user_id = request.args.get('user_id', 'demo_user')  # For development

        # Parse query parameters
        platform = request.args.get('platform')
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        priority = request.args.get('priority')
        limit = int(request.args.get('limit', '50'))
        offset = int(request.args.get('offset', '0'))

        # Build base query
        query = """
            SELECT id, platform, sender, subject, preview, timestamp,
                   unread, priority, thread_id, conversation_id,
                   created_at, updated_at
            FROM messages
            WHERE user_id = %s AND deleted = false
        """
        params = [user_id]

        # Add filters
        if platform:
            query += " AND platform = %s"
            params.append(platform)

        if unread_only:
            query += " AND unread = true"

        if priority:
            query += " AND priority = %s"
            params.append(priority)

        # Add sorting and pagination
        query += " ORDER BY timestamp DESC, priority DESC"
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        # Execute query
        messages = await execute_query(query, tuple(params))

        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages),
            'total': await _get_total_message_count(user_id, platform, unread_only, priority)
        })

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'messages': []
        }), 500

async def _get_total_message_count(user_id: str, platform: Optional[str] = None,
                                 unread_only: bool = False, priority: Optional[str] = None) -> int:
    """Get total count of messages for pagination"""
    try:
        query = "SELECT COUNT(*) as total FROM messages WHERE user_id = %s AND deleted = false"
        params = [user_id]

        if platform:
            query += " AND platform = %s"
            params.append(platform)

        if unread_only:
            query += " AND unread = true"

        if priority:
            query += " AND priority = %s"
            params.append(priority)

        result = await execute_query(query, tuple(params))
        return result[0]['total'] if result else 0

    except Exception as e:
        logger.error(f"Error getting message count: {e}")
        return 0

@message_bp.route('/<message_id>/read', methods=['POST'])
async def mark_as_read(message_id):
    """Mark a message as read"""
    try:
        user_id = request.json.get('user_id', 'demo_user')

        query = """
            UPDATE messages
            SET unread = false, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """

        rows_affected = await execute_update(query, (message_id, user_id))

        if rows_affected == 0:
            return jsonify({
                'success': False,
                'error': 'Message not found or access denied'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Message marked as read'
        })

    except Exception as e:
        logger.error(f"Error marking message as read: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@message_bp.route('/batch/read', methods=['POST'])
async def mark_batch_as_read():
    """Mark multiple messages as read"""
    try:
        user_id = request.json.get('user_id', 'demo_user')
        message_ids = request.json.get('message_ids', [])

        if not message_ids:
            return jsonify({
                'success': False,
                'error': 'No message IDs provided'
            }), 400

        # Create placeholders for the message IDs
        placeholders = ','.join(['%s'] * len(message_ids))
        query = f"""
            UPDATE messages
            SET unread = false, updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders}) AND user_id = %s
        """

        params = message_ids + [user_id]
        rows_affected = await execute_update(query, tuple(params))

        return jsonify({
            'success': True,
            'message': f'Marked {rows_affected} messages as read'
        })

    except Exception as e:
        logger.error(f"Error marking batch messages as read: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@message_bp.route('/<message_id>', methods=['DELETE'])
async def delete_message(message_id):
    """Soft delete a message"""
    try:
        user_id = request.json.get('user_id', 'demo_user')

        query = """
            UPDATE messages
            SET deleted = true, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """

        rows_affected = await execute_update(query, (message_id, user_id))

        if rows_affected == 0:
            return jsonify({
                'success': False,
                'error': 'Message not found or access denied'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Message deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@message_bp.route('/stats', methods=['GET'])
async def get_message_stats():
    """Get message statistics for dashboard"""
    try:
        user_id = request.args.get('user_id', 'demo_user')

        # Get total messages
        total_query = """
            SELECT COUNT(*) as total FROM messages
            WHERE user_id = %s AND deleted = false
        """
        total_result = await execute_query(total_query, (user_id,))
        total_messages = total_result[0]['total'] if total_result else 0

        # Get unread messages
        unread_query = """
            SELECT COUNT(*) as unread FROM messages
            WHERE user_id = %s AND unread = true AND deleted = false
        """
        unread_result = await execute_query(unread_query, (user_id,))
        unread_messages = unread_result[0]['unread'] if unread_result else 0

        # Get messages by platform
        platform_query = """
            SELECT platform, COUNT(*) as count FROM messages
            WHERE user_id = %s AND deleted = false
            GROUP BY platform
        """
        platform_result = await execute_query(platform_query, (user_id,))
        platform_counts = {row['platform']: row['count'] for row in platform_result}

        # Get messages by priority
        priority_query = """
            SELECT priority, COUNT(*) as count FROM messages
            WHERE user_id = %s AND deleted = false
            GROUP BY priority
        """
        priority_result = await execute_query(priority_query, (user_id,))
        priority_counts = {row['priority']: row['count'] for row in priority_result}

        # Get recent activity
        recent_query = """
            SELECT platform, COUNT(*) as count FROM messages
            WHERE user_id = %s AND timestamp >= NOW() - INTERVAL '24 hours'
            AND deleted = false
            GROUP BY platform
        """
        recent_result = await execute_query(recent_query, (user_id,))
        recent_activity = {row['platform']: row['count'] for row in recent_result}

        return jsonify({
            'success': True,
            'stats': {
                'total_messages': total_messages,
                'unread_messages': unread_messages,
                'platform_counts': platform_counts,
                'priority_counts': priority_counts,
                'recent_activity': recent_activity
            }
        })

    except Exception as e:
        logger.error(f"Error getting message stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@message_bp.route('/search', methods=['GET'])
async def search_messages():
    """Search messages across all platforms"""
    try:
        user_id = request.args.get('user_id', 'demo_user')
        query_text = request.args.get('q')
        platform = request.args.get('platform')
        limit = int(request.args.get('limit', '20'))
        offset = int(request.args.get('offset', '0'))

        if not query_text:
            return jsonify({
                'success': False,
                'error': 'Search query is required'
            }), 400

        # Build search query
        query = """
            SELECT id, platform, sender, subject, preview, timestamp,
                   unread, priority, created_at
            FROM messages
            WHERE user_id = %s AND deleted = false
            AND (subject ILIKE %s OR preview ILIKE %s OR sender ILIKE %s)
        """
        params = [user_id, f'%{query_text}%', f'%{query_text}%', f'%{query_text}%']

        if platform:
            query += " AND platform = %s"
            params.append(platform)

        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        messages = await execute_query(query, tuple(params))

        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages),
            'query': query_text
        })

    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'messages': []
        }), 500

# Error handlers
@message_bp.errorhandler(400)
def bad_request(error):
    return jsonify({
        'success': False,
        'error': 'Bad request',
        'message': str(error)
    }), 400

@message_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not found',
        'message': str(error)
    }), 404

@message_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': str(error)
    }), 500
