"""
Calendar API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, CalendarEvent, User
from utils import generate_uuid, validate_calendar_event_data
from datetime import datetime, timedelta
import logging

calendar_bp = Blueprint('calendar', __name__)
logger = logging.getLogger(__name__)

@calendar_bp.route('/events', methods=['GET'])
@jwt_required()
def get_events():
    """Get calendar events for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get query parameters
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = CalendarEvent.query.filter_by(user_id=user_id)

        if year and month:
            # Get events for specific month
            start_of_month = datetime(year, month, 1)
            if month == 12:
                end_of_month = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = datetime(year, month + 1, 1) - timedelta(days=1)
            query = query.filter(
                CalendarEvent.start_time >= start_of_month,
                CalendarEvent.start_time <= end_of_month
            )
        elif start_date and end_date:
            # Get events in date range
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(
                CalendarEvent.start_time >= start,
                CalendarEvent.start_time <= end
            )

        events = query.all()
        return jsonify([event.to_dict() for event in events])
    except Exception as e:
        logger.error(f'Error fetching calendar events: {str(e)}')
        return jsonify({'error': 'Failed to fetch calendar events'}), 500

@calendar_bp.route('/events', methods=['POST'])
@jwt_required()
def create_event():
    """Create a new calendar event"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('title') or not data.get('start_time') or not data.get('end_time'):
            return jsonify({'error': 'Title, start_time, and end_time are required'}), 400

        # Validate event data
        validation_error = validate_calendar_event_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        event = CalendarEvent(
            id=generate_uuid(),
            user_id=user_id,
            title=data['title'],
            start_time=datetime.fromisoformat(data['start_time'].replace('Z', '+00:00')),
            end_time=datetime.fromisoformat(data['end_time'].replace('Z', '+00:00')),
            color=data.get('color', 'blue'),
            description=data.get('description'),
            location=data.get('location'),
            attendees=data.get('attendees', []),
            recurrence=data.get('recurrence', {})
        )

        db.session.add(event)
        db.session.commit()

        # Emit real-time update
        from app import socketio
        socketio.emit('calendar:event:created', event.to_dict(), room=user_id)

        logger.info(f'Calendar event created: {event.id} for user {user_id}')
        return jsonify(event.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating calendar event: {str(e)}')
        return jsonify({'error': 'Failed to create calendar event'}), 500

@calendar_bp.route('/events/<event_id>', methods=['GET'])
@jwt_required()
def get_event(event_id):
    """Get a specific calendar event"""
    try:
        user_id = get_jwt_identity()
        event = CalendarEvent.query.filter_by(id=event_id, user_id=user_id).first()
        if not event:
            return jsonify({'error': 'Calendar event not found'}), 404

        return jsonify(event.to_dict())
    except Exception as e:
        logger.error(f'Error fetching calendar event {event_id}: {str(e)}')
        return jsonify({'error': 'Failed to fetch calendar event'}), 500

@calendar_bp.route('/events/<event_id>', methods=['PUT'])
@jwt_required()
def update_event(event_id):
    """Update a calendar event"""
    try:
        user_id = get_jwt_identity()
        event = CalendarEvent.query.filter_by(id=event_id, user_id=user_id).first()
        if not event:
            return jsonify({'error': 'Calendar event not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate event data
        validation_error = validate_calendar_event_data(data, partial=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        # Update event fields
        for field in ['title', 'start_time', 'end_time', 'color', 'description',
                     'location', 'attendees', 'recurrence']:
            if field in data:
                if field in ['start_time', 'end_time']:
                    setattr(event, field, datetime.fromisoformat(data[field].replace('Z', '+00:00')))
                else:
                    setattr(event, field, data[field])

        db.session.commit()

        # Emit real-time update
        from app import socketio
        socketio.emit('calendar:event:updated', event.to_dict(), room=user_id)

        logger.info(f'Calendar event updated: {event_id} for user {user_id}')
        return jsonify(event.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating calendar event {event_id}: {str(e)}')
        return jsonify({'error': 'Failed to update calendar event'}), 500

@calendar_bp.route('/events/<event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    """Delete a calendar event"""
    try:
        user_id = get_jwt_identity()
        event = CalendarEvent.query.filter_by(id=event_id, user_id=user_id).first()
        if not event:
            return jsonify({'error': 'Calendar event not found'}), 404

        db.session.delete(event)
        db.session.commit()

        # Emit real-time update
        from app import socketio
        socketio.emit('calendar:event:deleted', {'id': event_id}, room=user_id)

        logger.info(f'Calendar event deleted: {event_id} for user {user_id}')
        return jsonify({'message': 'Calendar event deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting calendar event {event_id}: {str(e)}')
        return jsonify({'error': 'Failed to delete calendar event'}), 500

@calendar_bp.route('/availability', methods=['GET'])
@jwt_required()
def get_availability():
    """Get user's availability for scheduling"""
    try:
        user_id = get_jwt_identity()
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'error': 'Date parameter is required'}), 400

        date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())

        events = CalendarEvent.query.filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time >= start_of_day,
            CalendarEvent.start_time <= end_of_day
        ).all()

        # Generate availability slots (assuming 9 AM - 5 PM working hours)
        working_hours_start = 9
        working_hours_end = 17
        slot_duration = 30  # minutes

        availability = []
        current_time = start_of_day.replace(hour=working_hours_start)

        while current_time.hour < working_hours_end:
            slot_end = current_time + timedelta(minutes=slot_duration)

            # Check if slot conflicts with any events
            is_available = True
            for event in events:
                if (event.start_time < slot_end and event.end_time > current_time):
                    is_available = False
                    break

            availability.append({
                'start_time': current_time.isoformat(),
                'end_time': slot_end.isoformat(),
                'available': is_available
            })

            current_time = slot_end

        return jsonify(availability)
    except Exception as e:
        logger.error(f'Error fetching availability: {str(e)}')
        return jsonify({'error': 'Failed to fetch availability'}), 500
