"""
Communications API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import db, Message, User
from ..utils import generate_uuid
from datetime import datetime
import logging

communications_bp = Blueprint('communications', __name__)
logger = logging.getLogger(__name__)

@communications_bp.route('/messages', methods=['GET'])
@jwt_required()
def get_messages():
    """Get all messages for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get query parameters
        platform = request.args.get('platform')
        unread_only = request.args.get('unread_only', type=bool)
        limit = request.args.get('limit', 50, type=int)

        query = Message.query.filter_by(user_id=user_id)

        if platform:
            query = query.filter_by(platform=platform)

        if unread_only:
            query = query.filter_by(unread=True)

        messages = query.order_by(Message.timestamp.desc()).limit(limit).all()
        return jsonify([message.to_dict() for message in messages])
    except Exception as e:
        logger.error(f'Error fetching messages: {str(e)}')
        return jsonify({'error': 'Failed to fetch messages'}), 500

@communications_bp.route('/messages/<message_id>', methods=['GET'])
@jwt_required()
def get_message(message_id):
    """Get a specific message"""
    try:
        user_id = get_jwt_identity()
        message = Message.query.filter_by(id=message_id, user_id=user_id).first()
        if not message:
            return jsonify({'error': 'Message not found'}), 404

        return jsonify(message.to_dict())
    except Exception as e:
        logger.error(f'Error fetching message {message_id}: {str(e)}')
        return jsonify({'error': 'Failed to fetch message'}), 500

@communications_bp.route('/messages/<message_id>/read', methods=['PUT'])
@jwt_required()
def mark_message_read(message_id):
    """Mark a message as read"""
    try:
        user_id = get_jwt_identity()
        message = Message.query.filter_by(id=message_id, user_id=user_id).first()
        if not message:
            return jsonify({'error': 'Message not found'}), 404

        message.unread = False
        message.read = True
        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('message:read', {'id': message_id}, room=user_id)

        logger.info(f'Message marked as read: {message_id} for user {user_id}')
        return jsonify(message.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error marking message as read {message_id}: {str(e)}')
        return jsonify({'error': 'Failed to mark message as read'}), 500

@communications_bp.route('/messages/<message_id>', methods=['DELETE'])
@jwt_required()
def delete_message(message_id):
    """Delete a message"""
    try:
        user_id = get_jwt_identity()
        message = Message.query.filter_by(id=message_id, user_id=user_id).first()
        if not message:
            return jsonify({'error': 'Message not found'}), 404

        db.session.delete(message)
        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('message:deleted', {'id': message_id}, room=user_id)

        logger.info(f'Message deleted: {message_id} for user {user_id}')
        return jsonify({'message': 'Message deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting message {message_id}: {str(e)}')
        return jsonify({'error': 'Failed to delete message'}), 500

@communications_bp.route('/messages/send', methods=['POST'])
@jwt_required()
def send_message():
    """Send a new message"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('platform') or not data.get('to') or not data.get('subject') or not data.get('body'):
            return jsonify({'error': 'Platform, to, subject, and body are required'}), 400

        # Here you would integrate with actual email/SMS services
        # For now, we'll just create a sent message record
        message = Message(
            id=generate_uuid(),
            user_id=user_id,
            platform=data['platform'],
            from_name=user.name,
            from_email=user.email,
            subject=data['subject'],
            preview=data['body'][:100] + '...' if len(data['body']) > 100 else data['body'],
            body=data['body'],
            timestamp=datetime.utcnow(),
            unread=False,
            read=True
        )

        db.session.add(message)
        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('message:sent', message.to_dict(), room=user_id)

        logger.info(f'Message sent: {message.id} for user {user_id}')
        return jsonify(message.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error sending message: {str(e)}')
        return jsonify({'error': 'Failed to send message'}), 500

@communications_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_communication_stats():
    """Get communication statistics for the current user"""
    try:
        user_id = get_jwt_identity()
        messages = Message.query.filter_by(user_id=user_id).all()

        stats = {
            'total': len(messages),
            'unread': len([m for m in messages if m.unread]),
            'by_platform': {}
        }

        # Group by platform
        for message in messages:
            platform = message.platform
            if platform not in stats['by_platform']:
                stats['by_platform'][platform] = {
                    'total': 0,
                    'unread': 0
                }
            stats['by_platform'][platform]['total'] += 1
            if message.unread:
                stats['by_platform'][platform]['unread'] += 1

        return jsonify(stats)
    except Exception as e:
        logger.error(f'Error fetching communication stats: {str(e)}')
        return jsonify({'error': 'Failed to fetch communication statistics'}), 500

@communications_bp.route('/sync', methods=['POST'])
@jwt_required()
def sync_communications():
    """Sync communications from external services"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        platform = data.get('platform') if data else None

        # Here you would implement actual sync logic for each platform
        # For now, return a mock response
        sync_result = {
            'platform': platform or 'all',
            'status': 'success',
            'messages_synced': 0,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Emit real-time update
        from ..app import socketio
        socketio.emit('communications:synced', sync_result, room=user_id)

        logger.info(f'Communications sync completed for user {user_id}')
        return jsonify(sync_result)
    except Exception as e:
        logger.error(f'Error syncing communications: {str(e)}')
        return jsonify({'error': 'Failed to sync communications'}), 500
