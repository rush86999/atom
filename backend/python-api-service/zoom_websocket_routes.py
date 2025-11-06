"""
🔄 Zoom WebSocket API Routes
Real-time WebSocket API endpoints for Zoom integration
"""

import os
import json
import logging
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, abort

from zoom_websocket_manager import ZoomWebSocketManager, WebSocketEvent, ConnectionStatus
from zoom_realtime_event_handler import ZoomRealTimeEventHandler

logger = logging.getLogger(__name__)

# Create blueprint
zoom_websocket_bp = Blueprint("zoom_websocket", __name__)

# Global managers
websocket_manager: Optional[ZoomWebSocketManager] = None
event_handler: Optional[ZoomRealTimeEventHandler] = None

def init_zoom_websocket_services(db_pool: asyncpg.Pool, redis_url: Optional[str] = None):
    """Initialize Zoom WebSocket services"""
    global websocket_manager, event_handler

    try:
        # Initialize WebSocket manager
        encryption_key = os.getenv('ENCRYPTION_KEY')
        websocket_manager = ZoomWebSocketManager(db_pool, redis_url, encryption_key)

        # Initialize event handler
        zoom_api_base_url = os.getenv('ZOOM_API_BASE_URL', 'https://api.zoom.us/v2')
        event_handler = ZoomRealTimeEventHandler(db_pool, zoom_api_base_url)

        # Start event processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(event_handler.start_processing(websocket_manager))
        loop.close()

        logger.info("Zoom WebSocket services initialized successfully")
        return websocket_manager, event_handler

    except Exception as e:
        logger.error(f"Failed to initialize Zoom WebSocket services: {e}")
        raise

def format_response(data: Any, endpoint: str, status: str = 'success') -> Dict[str, Any]:
    """Format API response"""
    return {
        'ok': status == 'success',
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_websocket_api'
    }

def format_error_response(error: str, endpoint: str, status_code: int = 500) -> tuple:
    """Format error response"""
    error_response = {
        'ok': False,
        'error': {
            'code': 'WEBSOCKET_ERROR',
            'message': error,
            'endpoint': endpoint
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_websocket_api'
    }
    return jsonify(error_response), status_code

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> tuple:
    """Validate required fields in request data"""
    missing_fields = [field for field in required_fields if field not in data or not data[field]]

    if missing_fields:
        error_msg = f"Missing required fields: {', '.join(missing_fields)}"
        return False, error_msg

    return True, None

def get_client_info() -> Dict[str, str]:
    """Get client information for security"""
    return {
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'ip_address': request.environ.get('REMOTE_ADDR', request.headers.get('X-Forwarded-For', 'Unknown')),
        'referer': request.headers.get('Referer', 'Unknown'),
        'origin': request.headers.get('Origin', 'Unknown'),
        'accept_language': request.headers.get('Accept-Language', 'Unknown')
    }

# === WEBSOCKET CONNECTION ENDPOINTS ===

@zoom_websocket_bp.route("/api/zoom/websocket/connect", methods=["POST"])
def websocket_connect_info():
    """Get WebSocket connection information"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id', 'account_id'])
        if not is_valid:
            return format_error_response(error, '/websocket/connect', 400)

        user_id = request_data['user_id']
        account_id = request_data['account_id']

        # Generate WebSocket connection URL
        websocket_host = os.getenv('WEBSOCKET_HOST', 'localhost')
        websocket_port = os.getenv('WEBSOCKET_PORT', '8765')
        websocket_protocol = 'wss' if request.is_secure else 'ws'

        websocket_url = f"{websocket_protocol}://{websocket_host}:{websocket_port}/{user_id}/{account_id}"

        # Get connection status
        user_connections = websocket_manager.user_connections.get(user_id, set())
        active_connections = [
            websocket_manager.connections[cid]
            for cid in user_connections
            if cid in websocket_manager.connections
        ]

        response_data = {
            'websocket_url': websocket_url,
            'connection_info': {
                'user_id': user_id,
                'account_id': account_id,
                'protocol': websocket_protocol,
                'host': websocket_host,
                'port': websocket_port
            },
            'current_connections': [
                {
                    'connection_id': conn.connection_id,
                    'status': conn.status.value,
                    'connected_at': conn.connected_at.isoformat(),
                    'message_count': conn.message_count,
                    'subscribed_meetings': list(conn.subscribed_meetings),
                    'subscribed_events': [e.value for e in conn.subscribed_events]
                }
                for conn in active_connections
            ],
            'server_info': {
                'max_connections': websocket_manager.config['max_connections'],
                'ping_interval': websocket_manager.config['ping_interval'],
                'distributed_mode': websocket_manager.config['distributed_mode']
            },
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/connect')

    except Exception as e:
        logger.error(f"Failed to get WebSocket connect info: {e}")
        return format_error_response(str(e), '/websocket/connect', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/broadcast", methods=["POST"])
def websocket_broadcast():
    """Broadcast message to WebSocket connections"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['event_type'])
        if not is_valid:
            return format_error_response(error, '/websocket/broadcast', 400)

        event_type_str = request_data['event_type']
        message_data = request_data.get('data', {})
        target_meeting_id = request_data.get('meeting_id')
        target_user_ids = request_data.get('user_ids')
        user_id = request_data.get('user_id')
        account_id = request_data.get('account_id')
        correlation_id = request_data.get('correlation_id')
        metadata = request_data.get('metadata', {})

        # Parse event type
        try:
            event_type = WebSocketEvent(event_type_str)
        except ValueError:
            return format_error_response(f'Invalid event type: {event_type_str}', '/websocket/broadcast', 400)

        # Create WebSocket message
        from zoom_websocket_manager import WebSocketMessage
        message = WebSocketMessage(
            event_type=event_type,
            data=message_data,
            timestamp=datetime.now(timezone.utc),
            meeting_id=target_meeting_id,
            user_id=user_id,
            account_id=account_id,
            correlation_id=correlation_id or f"broadcast_{secrets.token_hex(16)}",
            metadata={**metadata, 'source': 'websocket_api'}
        )

        # Broadcast message
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sent_count = loop.run_until_complete(websocket_manager.broadcast_event(
            message,
            target_meeting_id=target_meeting_id,
            target_user_id=target_user_id
        ))
        loop.close()

        response_data = {
            'success': True,
            'event_type': event_type_str,
            'message_sent': True,
            'sent_count': sent_count,
            'target_meeting_id': target_meeting_id,
            'target_user_ids': target_user_ids,
            'correlation_id': message.correlation_id,
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/broadcast')

    except Exception as e:
        logger.error(f"Failed to broadcast WebSocket message: {e}")
        return format_error_response(str(e), '/websocket/broadcast', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/connections/list", methods=["POST"])
def list_websocket_connections():
    """List WebSocket connections"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/websocket/connections/list', 400)

        user_id = request_data['user_id']
        include_inactive = request_data.get('include_inactive', False)

        # Get user connections
        user_connection_ids = websocket_manager.user_connections.get(user_id, set())
        connections = []

        for connection_id in user_connection_ids:
            connection = websocket_manager.connections.get(connection_id)
            if connection and (include_inactive or connection.status == ConnectionStatus.CONNECTED):
                connections.append(websocket_manager.get_connection_info(connection_id))

        response_data = {
            'user_id': user_id,
            'connections': connections,
            'total_count': len(connections),
            'active_count': len([c for c in connections if c['status'] == 'connected']),
            'include_inactive': include_inactive
        }

        return format_response(response_data, '/websocket/connections/list')

    except Exception as e:
        logger.error(f"Failed to list WebSocket connections: {e}")
        return format_error_response(str(e), '/websocket/connections/list', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/connections/info", methods=["POST"])
def get_connection_info():
    """Get specific WebSocket connection information"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['connection_id'])
        if not is_valid:
            return format_error_response(error, '/websocket/connections/info', 400)

        connection_id = request_data['connection_id']

        # Get connection info
        connection_info = websocket_manager.get_connection_info(connection_id)

        if not connection_info:
            return format_error_response('Connection not found', '/websocket/connections/info', 404)

        response_data = {
            'connection_info': connection_info,
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/connections/info')

    except Exception as e:
        logger.error(f"Failed to get connection info: {e}")
        return format_error_response(str(e), '/websocket/connections/info', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/meeting-state/update", methods=["POST"])
def update_meeting_state():
    """Update meeting state and notify subscribers"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['meeting_id', 'updates'])
        if not is_valid:
            return format_error_response(error, '/websocket/meeting-state/update', 400)

        meeting_id = request_data['meeting_id']
        updates = request_data['updates']

        # Update meeting state
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(websocket_manager.update_meeting_state(meeting_id, updates))
        loop.close()

        response_data = {
            'success': True,
            'meeting_id': meeting_id,
            'updates': updates,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/meeting-state/update')

    except Exception as e:
        logger.error(f"Failed to update meeting state: {e}")
        return format_error_response(str(e), '/websocket/meeting-state/update', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/meeting-state/get", methods=["POST"])
def get_meeting_state():
    """Get current meeting state"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['meeting_id'])
        if not is_valid:
            return format_error_response(error, '/websocket/meeting-state/get', 400)

        meeting_id = request_data['meeting_id']

        # Get meeting state
        meeting_state = websocket_manager.get_meeting_state(meeting_id)

        if not meeting_state:
            return format_error_response('Meeting state not found', '/websocket/meeting-state/get', 404)

        response_data = {
            'meeting_state': meeting_state,
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/meeting-state/get')

    except Exception as e:
        logger.error(f"Failed to get meeting state: {e}")
        return format_error_response(str(e), '/websocket/meeting-state/get', 500)

# === REAL-TIME EVENT ENDPOINTS ===

@zoom_websocket_bp.route("/api/zoom/websocket/events/create", methods=["POST"])
def create_realtime_event():
    """Create and queue a real-time event"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['event_type', 'data'])
        if not is_valid:
            return format_error_response(error, '/websocket/events/create', 400)

        event_type_str = request_data['event_type']
        event_data = request_data['data']
        user_id = request_data.get('user_id')
        meeting_id = request_data.get('meeting_id')
        account_id = request_data.get('account_id')

        # Parse event type
        try:
            event_type = WebSocketEvent(event_type_str)
        except ValueError:
            return format_error_response(f'Invalid event type: {event_type_str}', '/websocket/events/create', 400)

        # Create event
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        correlation_id = loop.run_until_complete(websocket_manager.create_event(
            event_type=event_type,
            data=event_data,
            user_id=user_id,
            meeting_id=meeting_id,
            account_id=account_id
        )

        response_data = {
            'success': True,
            'event_type': event_type_str,
            'correlation_id': correlation_id,
            'event_data': event_data,
            'user_id': user_id,
            'meeting_id': meeting_id,
            'account_id': account_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/events/create')

    except Exception as e:
        logger.error(f"Failed to create real-time event: {e}")
        return format_error_response(str(e), '/websocket/events/create', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/events/webhook", methods=["POST"])
def handle_webhook_event():
    """Handle incoming Zoom webhook event"""
    try:
        # Get webhook data
        webhook_data = request.get_json()

        # Verify webhook signature if configured
        webhook_secret = os.getenv('ZOOM_WEBHOOK_SECRET')
        if webhook_secret:
            signature = request.headers.get('x-zm-signature')
            if not signature:
                return format_error_response('Missing webhook signature', '/websocket/events/webhook', 401)

            # TODO: Implement signature verification
            # This would involve creating a signature from the payload and comparing with header

        # Process webhook event
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(event_handler.handle_webhook_event(webhook_data))
        loop.close()

        response_data = {
            'success': success,
            'webhook_data': webhook_data,
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'client_info': get_client_info()
        }

        if success:
            return format_response(response_data, '/websocket/events/webhook')
        else:
            return format_error_response('Failed to process webhook event', '/websocket/events/webhook', 500)

    except Exception as e:
        logger.error(f"Failed to handle webhook event: {e}")
        return format_error_response(str(e), '/websocket/events/webhook', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/events/stats", methods=["GET"])
def get_event_stats():
    """Get real-time event processing statistics"""
    try:
        # Get event handler stats
        event_stats = event_handler.get_stats()

        # Get WebSocket manager stats
        websocket_stats = websocket_manager.get_metrics()

        response_data = {
            'event_handler_stats': event_stats,
            'websocket_manager_stats': websocket_stats,
            'combined_stats': {
                'total_connections': websocket_stats.get('active_connections', 0),
                'total_events_processed': event_stats.get('events_processed', 0),
                'total_meetings_tracked': event_stats.get('meetings_tracked', 0),
                'total_participants_tracked': event_stats.get('participants_tracked', 0),
                'event_processing_rate': event_stats.get('processing_rate', 0),
                'websocket_messages_sent': websocket_stats.get('total_messages', 0),
                'last_event_time': event_stats.get('last_event_time'),
                'server_uptime': websocket_stats.get('connection_uptime', 0)
            },
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/events/stats')

    except Exception as e:
        logger.error(f"Failed to get event stats: {e}")
        return format_error_response(str(e), '/websocket/events/stats', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/events/history", methods=["POST"])
def get_event_history():
    """Get real-time event history"""
    try:
        request_data = request.get_json()

        # Validate required fields
        required_fields = ['user_id']
        if 'meeting_id' not in request_data:
            required_fields.append('meeting_id')

        is_valid, error = validate_required_fields(request_data, required_fields)
        if not is_valid:
            return format_error_response(error, '/websocket/events/history', 400)

        user_id = request_data['user_id']
        meeting_id = request_data.get('meeting_id')
        event_types = request_data.get('event_types')
        from_date = request_data.get('from_date')
        to_date = request_data.get('to_date')
        limit = request_data.get('limit', 100)

        # Query events from database
        if not event_handler.db_pool:
            return format_error_response('Database not available', '/websocket/events/history', 503)

        async with event_handler.db_pool.acquire() as conn:
            # Build query
            query = """
                SELECT event_id, event_type, event_ts, meeting_id, account_id,
                       user_id, participant, payload, processed, created_at
                FROM zoom_meeting_events
                WHERE user_id = $1
            """
            params = [user_id]
            param_index = 2

            if meeting_id:
                query += f" AND meeting_id = ${param_index}"
                params.append(meeting_id)
                param_index += 1

            if event_types:
                placeholders = []
                for event_type in event_types:
                    placeholders.append(f"${param_index}")
                    params.append(event_type)
                    param_index += 1
                query += f" AND event_type IN ({', '.join(placeholders)})"

            if from_date:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                query += f" AND created_at >= ${param_index}"
                params.append(from_dt)
                param_index += 1

            if to_date:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                query += f" AND created_at <= ${param_index}"
                params.append(to_dt)
                param_index += 1

            query += " ORDER BY created_at DESC"

            if limit:
                query += f" LIMIT ${param_index}"
                params.append(limit)

            rows = conn.fetch(query, *params)

        # Format events
        events = []
        for row in rows:
            event = {
                'event_id': row['event_id'],
                'event_type': row['event_type'],
                'event_ts': row['event_ts'],
                'meeting_id': row['meeting_id'],
                'account_id': row['account_id'],
                'user_id': row['user_id'],
                'participant': json.loads(row['participant']) if row['participant'] else None,
                'payload': json.loads(row['payload']) if row['payload'] else {},
                'processed': row['processed'],
                'created_at': row['created_at'].isoformat()
            }
            events.append(event)

        response_data = {
            'user_id': user_id,
            'meeting_id': meeting_id,
            'event_types': event_types,
            'from_date': from_date,
            'to_date': to_date,
            'limit': limit,
            'events': events,
            'total_count': len(events)
        }

        return format_response(response_data, '/websocket/events/history')

    except Exception as e:
        logger.error(f"Failed to get event history: {e}")
        return format_error_response(str(e), '/websocket/events/history', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/participants/list", methods=["POST"])
def get_participants_list():
    """Get current participants for a meeting"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['meeting_id'])
        if not is_valid:
            return format_error_response(error, '/websocket/participants/list', 400)

        meeting_id = request_data['meeting_id']
        include_status = request_data.get('include_status', True)
        include_metadata = request_data.get('include_metadata', False)

        # Get meeting state
        meeting_state = websocket_manager.get_meeting_state(meeting_id)

        if not meeting_state:
            return format_error_response('Meeting not found', '/websocket/participants/list', 404)

        # Format participants
        participants = []
        for participant_id, participant_data in meeting_state.get('participants', {}).items():
            participant = {
                'participant_id': participant_id,
                'user_id': participant_data.get('user_id'),
                'name': participant_data.get('name'),
                'email': participant_data.get('email'),
                'joined_at': participant_data.get('joined_at'),
                'is_host': participant_data.get('is_host', False),
                'is_co_host': participant_data.get('is_co_host', False)
            }

            if include_status:
                participant['status'] = participant_data.get('status')
                participant['audio_status'] = participant_data.get('audio_status', {})
                participant['video_status'] = participant_data.get('video_status', {})
                participant['screen_share_status'] = participant_data.get('screen_share_status', {})

            if include_metadata:
                participant['metadata'] = participant_data.get('metadata', {})

            participants.append(participant)

        response_data = {
            'meeting_id': meeting_id,
            'participants': participants,
            'total_count': len(participants),
            'host_count': len([p for p in participants if p['is_host']]),
            'co_host_count': len([p for p in participants if p['is_co_host']]),
            'meeting_status': meeting_state.get('status'),
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/participants/list')

    except Exception as e:
        logger.error(f"Failed to get participants list: {e}")
        return format_error_response(str(e), '/websocket/participants/list', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/participants/status", methods=["POST"])
def get_participant_status():
    """Get specific participant status"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['meeting_id', 'participant_id'])
        if not is_valid:
            return format_error_response(error, '/websocket/participants/status', 400)

        meeting_id = request_data['meeting_id']
        participant_id = request_data['participant_id']

        # Get participant state from event handler
        participant_state = event_handler.get_participant_state(meeting_id, participant_id)

        if not participant_state:
            return format_error_response('Participant not found', '/websocket/participants/status', 404)

        response_data = {
            'meeting_id': meeting_id,
            'participant_id': participant_id,
            'participant_state': participant_state,
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/participants/status')

    except Exception as e:
        logger.error(f"Failed to get participant status: {e}")
        return format_error_response(str(e), '/websocket/participants/status', 500)

@zoom_websocket_bp.route("/api/zoom/websocket/analytics/realtime", methods=["POST"])
def get_realtime_analytics():
    """Get real-time analytics data"""
    try:
        request_data = request.get_json()

        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['meeting_id'])
        if not is_valid:
            return format_error_response(error, '/websocket/analytics/realtime', 400)

        meeting_id = request_data['meeting_id']
        metric_types = request_data.get('metric_types', ['all'])
        time_window = request_data.get('time_window', 60)  # minutes

        # Get real-time analytics from database
        if not event_handler.db_pool:
            return format_error_response('Database not available', '/websocket/analytics/realtime', 503)

        async with event_handler.db_pool.acquire() as conn:
            # Build query
            query = """
                SELECT metric_type, metric_value, metric_data, timestamp
                FROM zoom_realtime_analytics
                WHERE meeting_id = $1 AND timestamp >= NOW() - INTERVAL '%s minutes'
            """ % time_window

            params = [meeting_id]

            if 'all' not in metric_types:
                placeholders = []
                param_index = 2
                for metric_type in metric_types:
                    placeholders.append(f"${param_index}")
                    params.append(metric_type)
                    param_index += 1
                query += f" AND metric_type IN ({', '.join(placeholders)})"

            query += " ORDER BY timestamp DESC"

            rows = conn.fetch(query, *params)

        # Group metrics by type
        analytics = {}
        for row in rows:
            metric_type = row['metric_type']
            if metric_type not in analytics:
                analytics[metric_type] = []

            analytics[metric_type].append({
                'metric_value': float(row['metric_value']),
                'metric_data': json.loads(row['metric_data']) if row['metric_data'] else {},
                'timestamp': row['timestamp'].isoformat()
            })

        # Calculate summary statistics
        summary = {}
        for metric_type, metrics_list in analytics.items():
            values = [m['metric_value'] for m in metrics_list]
            summary[metric_type] = {
                'count': len(values),
                'latest': values[0] if values else None,
                'average': sum(values) / len(values) if values else None,
                'min': min(values) if values else None,
                'max': max(values) if values else None
            }

        response_data = {
            'meeting_id': meeting_id,
            'metric_types': metric_types,
            'time_window_minutes': time_window,
            'analytics': analytics,
            'summary': summary,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'client_info': get_client_info()
        }

        return format_response(response_data, '/websocket/analytics/realtime')

    except Exception as e:
        logger.error(f"Failed to get real-time analytics: {e}")
        return format_error_response(str(e), '/websocket/analytics/realtime', 500)

# === ERROR HANDLING ===

@zoom_websocket_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request"""
    return format_error_response('Bad Request', 'global', 400)

@zoom_websocket_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized"""
    return format_error_response('Unauthorized', 'global', 401)

@zoom_websocket_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden"""
    return format_error_response('Forbidden', 'global', 403)

@zoom_websocket_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found"""
    return format_error_response('Not Found', 'global', 404)

@zoom_websocket_bp.errorhandler(429)
def rate_limited(error):
    """Handle 429 Too Many Requests"""
    return format_error_response('Rate Limit Exceeded', 'global', 429)

@zoom_websocket_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server Error"""
    logger.error(f"Internal server error: {error}")
    return format_error_response('Internal Server Error', 'global', 500)

# === HEALTH CHECK ===

@zoom_websocket_bp.route("/api/zoom/websocket/health", methods=["GET"])
async def websocket_health():
    """Health check for WebSocket services"""
    try:
        health_status = {
            'websocket_manager': websocket_manager is not None,
            'event_handler': event_handler is not None,
            'is_running': websocket_manager.is_running if websocket_manager else False,
            'total_connections': len(websocket_manager.connections) if websocket_manager else 0,
            'active_connections': len([
                c for c in websocket_manager.connections.values()
                if c.status == ConnectionStatus.CONNECTED
            ]) if websocket_manager else 0,
            'meeting_states': len(websocket_manager.meeting_states) if websocket_manager else 0,
            'last_check': datetime.now(timezone.utc).isoformat()
        }

        # Add detailed metrics if available
        if websocket_manager:
            health_status['metrics'] = websocket_manager.get_metrics()

        if event_handler:
            health_status['event_stats'] = event_handler.get_stats()

        # Determine overall health
        is_healthy = (
            health_status['websocket_manager'] and
            health_status['event_handler'] and
            health_status['is_running']
        )

        if is_healthy:
            return format_response(health_status, '/websocket/health')
        else:
            return format_error_response('WebSocket services unhealthy', '/websocket/health', 503)

    except Exception as e:
        logger.error(f"WebSocket health check failed: {e}")
        return format_error_response(f'Health check failed: {e}', '/websocket/health', 500)
