"""
Integrations API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import db, Integration, User
from ..utils import generate_uuid
from datetime import datetime
import logging

integrations_bp = Blueprint('integrations', __name__)
logger = logging.getLogger(__name__)

@integrations_bp.route('', methods=['GET'])
@jwt_required()
def get_integrations():
    """Get all integrations for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        integrations = Integration.query.filter_by(user_id=user_id).all()
        return jsonify([integration.to_dict() for integration in integrations])
    except Exception as e:
        logger.error(f'Error fetching integrations: {str(e)}')
        return jsonify({'error': 'Failed to fetch integrations'}), 500

@integrations_bp.route('/<integration_id>', methods=['GET'])
@jwt_required()
def get_integration(integration_id):
    """Get a specific integration"""
    try:
        user_id = get_jwt_identity()
        integration = Integration.query.filter_by(id=integration_id, user_id=user_id).first()
        if not integration:
            return jsonify({'error': 'Integration not found'}), 404

        return jsonify(integration.to_dict())
    except Exception as e:
        logger.error(f'Error fetching integration {integration_id}: {str(e)}')
        return jsonify({'error': 'Failed to fetch integration'}), 500

@integrations_bp.route('/<integration_id>/connect', methods=['POST'])
@jwt_required()
def connect_integration(integration_id):
    """Connect an integration"""
    try:
        user_id = get_jwt_identity()
        integration = Integration.query.filter_by(id=integration_id, user_id=user_id).first()
        if not integration:
            return jsonify({'error': 'Integration not found'}), 404

        data = request.get_json() or {}

        # Here you would implement actual OAuth/connection logic for each service
        # For now, we'll simulate connection
        integration.connected = True
        integration.last_sync = datetime.utcnow()
        integration.sync_status = 'success'
        integration.config = data.get('config', {})

        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('integration:connected', integration.to_dict(), room=user_id)

        logger.info(f'Integration connected: {integration_id} for user {user_id}')
        return jsonify(integration.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error connecting integration {integration_id}: {str(e)}')
        return jsonify({'error': 'Failed to connect integration'}), 500

@integrations_bp.route('/<integration_id>/disconnect', methods=['POST'])
@jwt_required()
def disconnect_integration(integration_id):
    """Disconnect an integration"""
    try:
        user_id = get_jwt_identity()
        integration = Integration.query.filter_by(id=integration_id, user_id=user_id).first()
        if not integration:
            return jsonify({'error': 'Integration not found'}), 404

        integration.connected = False
        integration.sync_status = None
        integration.config = {}

        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('integration:disconnected', integration.to_dict(), room=user_id)

        logger.info(f'Integration disconnected: {integration_id} for user {user_id}')
        return jsonify(integration.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error disconnecting integration {integration_id}: {str(e)}')
        return jsonify({'error': 'Failed to disconnect integration'}), 500

@integrations_bp.route('/<integration_id>/sync', methods=['POST'])
@jwt_required()
def sync_integration(integration_id):
    """Sync data from an integration"""
    try:
        user_id = get_jwt_identity()
        integration = Integration.query.filter_by(id=integration_id, user_id=user_id).first()
        if not integration:
            return jsonify({'error': 'Integration not found'}), 404

        if not integration.connected:
            return jsonify({'error': 'Integration is not connected'}), 400

        # Update sync status
        integration.sync_status = 'in_progress'
        db.session.commit()

        # Here you would implement actual sync logic for each service
        # For now, simulate sync completion
        import time
        time.sleep(1)  # Simulate sync time

        integration.last_sync = datetime.utcnow()
        integration.sync_status = 'success'
        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('integration:sync:completed', integration.to_dict(), room=user_id)

        logger.info(f'Integration synced: {integration_id} for user {user_id}')
        return jsonify({
            'integration': integration.to_dict(),
            'sync_result': {
                'status': 'success',
                'items_synced': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error syncing integration {integration_id}: {str(e)}')

        # Update sync status to failed
        integration.sync_status = 'failed'
        db.session.commit()

        # Emit real-time update
        from ..app import socketio
        socketio.emit('integration:sync:failed', integration.to_dict(), room=user_id)

        return jsonify({'error': 'Failed to sync integration'}), 500

@integrations_bp.route('/categories', methods=['GET'])
def get_integration_categories():
    """Get available integration categories"""
    categories = [
        'Communication & Collaboration',
        'Calendar & Scheduling',
        'Task & Project Management',
        'Finance & Accounting',
        'Social Media',
        'Development & Technical',
        'Planned Integrations'
    ]
    return jsonify(categories)

@integrations_bp.route('/available', methods=['GET'])
def get_available_integrations():
    """Get all available integrations with their metadata"""
    available_integrations = [
        # Communication & Collaboration
        {
            'service_type': 'gmail',
            'display_name': 'Gmail',
            'category': 'Communication & Collaboration',
            'description': 'Connect your Gmail account to sync emails and manage communications.',
            'features': ['Email sync', 'Send emails', 'Label management'],
            'dev_status': 'implemented'
        },
        {
            'service_type': 'slack',
            'display_name': 'Slack',
            'category': 'Communication & Collaboration',
            'description': 'Integrate with Slack for team communication and notifications.',
            'features': ['Message sync', 'Channel management', 'Real-time notifications'],
            'dev_status': 'implemented'
        },
        {
            'service_type': 'teams',
            'display_name': 'Microsoft Teams',
            'category': 'Communication & Collaboration',
            'description': 'Connect Microsoft Teams for unified communication.',
            'features': ['Chat sync', 'Meeting integration', 'File sharing'],
            'dev_status': 'implemented'
        },
        # Calendar & Scheduling
        {
            'service_type': 'google_calendar',
            'display_name': 'Google Calendar',
            'category': 'Calendar & Scheduling',
            'description': 'Sync your Google Calendar events and manage your schedule.',
            'features': ['Event sync', 'Availability checking', 'Meeting creation'],
            'dev_status': 'implemented'
        },
        {
            'service_type': 'outlook_calendar',
            'display_name': 'Outlook Calendar',
            'category': 'Calendar & Scheduling',
            'description': 'Connect Outlook Calendar for comprehensive scheduling.',
            'features': ['Event sync', 'Meeting management', 'Reminder integration'],
            'dev_status': 'implemented'
        },
        # Task & Project Management
        {
            'service_type': 'notion',
            'display_name': 'Notion',
            'category': 'Task & Project Management',
            'description': 'Integrate with Notion for workspace and task management.',
            'features': ['Database sync', 'Page management', 'Task tracking'],
            'dev_status': 'implemented'
        },
        # Finance & Accounting
        {
            'service_type': 'plaid',
            'display_name': 'Plaid',
            'category': 'Finance & Accounting',
            'description': 'Connect financial accounts for transaction tracking.',
            'features': ['Account sync', 'Transaction import', 'Balance monitoring'],
            'dev_status': 'implemented'
        },
        # Development & Technical
        {
            'service_type': 'github',
            'display_name': 'GitHub',
            'category': 'Development & Technical',
            'description': 'Connect GitHub for repository management and issue tracking.',
            'features': ['Repository sync', 'Issue tracking', 'Pull request management'],
            'dev_status': 'implemented'
        }
    ]

    return jsonify(available_integrations)

@integrations_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_integration_stats():
    """Get integration statistics for the current user"""
    try:
        user_id = get_jwt_identity()
        integrations = Integration.query.filter_by(user_id=user_id).all()

        stats = {
            'total': len(integrations),
            'connected': len([i for i in integrations if i.connected]),
            'by_category': {},
            'by_status': {
                'success': len([i for i in integrations if i.sync_status == 'success']),
                'failed': len([i for i in integrations if i.sync_status == 'failed']),
                'in_progress': len([i for i in integrations if i.sync_status == 'in_progress'])
            }
        }

        # Group by category
        for integration in integrations:
            category = integration.category
            if category not in stats['by_category']:
                stats['by_category'][category] = {
                    'total': 0,
                    'connected': 0
                }
            stats['by_category'][category]['total'] += 1
            if integration.connected:
                stats['by_category'][category]['connected'] += 1

        return jsonify(stats)
    except Exception as e:
        logger.error(f'Error fetching integration stats: {str(e)}')
        return jsonify({'error': 'Failed to fetch integration statistics'}), 500
