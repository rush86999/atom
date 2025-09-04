import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from calendar_service import CalendarEvent, UnifiedCalendarService, sync_user_calendars, find_available_time_slots
from db_utils import get_db_pool, get_user_tokens

# Create blueprint
calendar_bp = Blueprint('calendar', __name__, url_prefix='/api/calendar')

logger = logging.getLogger(__name__)

@calendar_bp.route('/events', methods=['GET'])
async def get_calendar_events():
    """Get calendar events for the authenticated user"""
    try:
        # In production, this would be extracted from JWT token
        user_id = request.args.get('user_id', 'demo_user')  # For development

        # Parse date range parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Default to current week if no dates provided
        if not start_date_str:
            start_date = datetime.now() - timedelta(days=7)
        else:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))

        if not end_date_str:
            end_date = datetime.now() + timedelta(days=30)
        else:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

        # Get calendar service instance
        calendar_service = UnifiedCalendarService()

        # Fetch events from all configured providers
        events = await calendar_service.get_events(user_id, start_date, end_date)

        # Convert events to dictionary format for JSON serialization
        events_data = [event.to_dict() for event in events]

        return jsonify({
            'success': True,
            'events': events_data,
            'count': len(events_data),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })

    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'events': []
        }), 500

@calendar_bp.route('/sync', methods=['POST'])
async def sync_calendars():
    """Force synchronization of all calendar providers"""
    try:
        user_id = request.json.get('user_id', 'demo_user')  # For development

        # Sync calendars
        result = await sync_user_calendars(user_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error syncing calendars: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@calendar_bp.route('/available-slots', methods=['GET'])
async def get_available_slots():
    """Find available time slots for scheduling"""
    try:
        user_id = request.args.get('user_id', 'demo_user')
        duration_minutes = int(request.args.get('duration', '30'))
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Parse duration
        duration = timedelta(minutes=duration_minutes)

        # Parse date range
        if not start_date_str:
            start_date = datetime.now()
        else:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))

        if not end_date_str:
            end_date = datetime.now() + timedelta(days=7)
        else:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

        # Find available slots
        available_slots = await find_available_time_slots(user_id, duration, start_date, end_date)

        # Convert datetime objects to ISO strings for JSON serialization
        slots_data = []
        for slot in available_slots:
            slots_data.append({
                'start': slot['start'].isoformat(),
                'end': slot['end'].isoformat(),
                'duration_minutes': slot['duration'].total_seconds() / 60
            })

        return jsonify({
            'success': True,
            'available_slots': slots_data,
            'count': len(slots_data),
            'duration_minutes': duration_minutes
        })

    except Exception as e:
        logger.error(f"Error finding available slots: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'available_slots': []
        }), 500

@calendar_bp.route('/providers', methods=['GET'])
async def get_calendar_providers():
    """Get list of configured calendar providers for the user"""
    try:
        user_id = request.args.get('user_id', 'demo_user')

        # Check which providers have configured credentials
        providers = []

        # Check Google Calendar
        google_tokens = await get_user_tokens(user_id, 'google_calendar')
        if google_tokens:
            providers.append({
                'provider': 'google',
                'connected': True,
                'last_sync': google_tokens.get('updated_at')
            })
        else:
            providers.append({
                'provider': 'google',
                'connected': False
            })

        # Check Outlook Calendar
        outlook_tokens = await get_user_tokens(user_id, 'outlook_calendar')
        if outlook_tokens:
            providers.append({
                'provider': 'outlook',
                'connected': True,
                'last_sync': outlook_tokens.get('updated_at')
            })
        else:
            providers.append({
                'provider': 'outlook',
                'connected': False
            })

        # Check CalDAV Calendar
        caldav_tokens = await get_user_tokens(user_id, 'caldav_calendar')
        if caldav_tokens:
            providers.append({
                'provider': 'caldav',
                'connected': True,
                'last_sync': caldav_tokens.get('updated_at')
            })
        else:
            providers.append({
                'provider': 'caldav',
                'connected': False
            })

        return jsonify({
            'success': True,
            'providers': providers
        })

    except Exception as e:
        logger.error(f"Error getting calendar providers: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'providers': []
        }), 500

@calendar_bp.route('/health', methods=['GET'])
async def calendar_health():
    """Health check for calendar service"""
    try:
        # Check database connection
        db_pool = get_db_pool()
        db_status = 'healthy' if db_pool else 'unhealthy'

        return jsonify({
            'status': 'ok',
            'database': db_status,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Calendar health check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Error handlers
@calendar_bp.errorhandler(400)
def bad_request(error):
    return jsonify({
        'success': False,
        'error': 'Bad request',
        'message': str(error)
    }), 400

@calendar_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not found',
        'message': str(error)
    }), 404

@calendar_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': str(error)
    }), 500
