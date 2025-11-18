"""
Voice API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, VoiceCommand, User
from utils import generate_uuid
from datetime import datetime
import logging

voice_bp = Blueprint('voice', __name__)
logger = logging.getLogger(__name__)

@voice_bp.route('/commands', methods=['GET'])
@jwt_required()
def get_voice_commands():
    """Get all voice commands for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        commands = VoiceCommand.query.filter_by(user_id=user_id).all()
        return jsonify([command.to_dict() for command in commands])
    except Exception as e:
        logger.error(f'Error fetching voice commands: {str(e)}')
        return jsonify({'error': 'Failed to fetch voice commands'}), 500

@voice_bp.route('/commands', methods=['POST'])
@jwt_required()
def create_voice_command():
    """Create a new voice command"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('phrase'):
            return jsonify({'error': 'Command phrase is required'}), 400

        command = VoiceCommand(
            id=generate_uuid(),
            user_id=user_id,
            phrase=data['phrase'],
            description=data.get('description', ''),
            enabled=data.get('enabled', True),
            usage_count=0,
            average_confidence=data.get('average_confidence')
        )

        db.session.add(command)
        db.session.commit()

        logger.info(f'Voice command created: {command.id} for user {user_id}')
        return jsonify(command.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating voice command: {str(e)}')
        return jsonify({'error': 'Failed to create voice command'}), 500

@voice_bp.route('/commands/<command_id>', methods=['PUT'])
@jwt_required()
def update_voice_command(command_id):
    """Update a voice command"""
    try:
        user_id = get_jwt_identity()
        command = VoiceCommand.query.filter_by(id=command_id, user_id=user_id).first()
        if not command:
            return jsonify({'error': 'Voice command not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Update command fields
        for field in ['phrase', 'description', 'enabled', 'average_confidence']:
            if field in data:
                setattr(command, field, data[field])

        db.session.commit()

        logger.info(f'Voice command updated: {command_id} for user {user_id}')
        return jsonify(command.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating voice command {command_id}: {str(e)}')
        return jsonify({'error': 'Failed to update voice command'}), 500

@voice_bp.route('/commands/<command_id>', methods=['DELETE'])
@jwt_required()
def delete_voice_command(command_id):
    """Delete a voice command"""
    try:
        user_id = get_jwt_identity()
        command = VoiceCommand.query.filter_by(id=command_id, user_id=user_id).first()
        if not command:
            return jsonify({'error': 'Voice command not found'}), 404

        db.session.delete(command)
        db.session.commit()

        logger.info(f'Voice command deleted: {command_id} for user {user_id}')
        return jsonify({'message': 'Voice command deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting voice command {command_id}: {str(e)}')
        return jsonify({'error': 'Failed to delete voice command'}), 500

@voice_bp.route('/process', methods=['POST'])
@jwt_required()
def process_voice_command():
    """Process a voice command"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('transcript'):
            return jsonify({'error': 'Voice transcript is required'}), 400

        transcript = data['transcript'].lower()
        confidence = data.get('confidence', 0.8)

        # Find matching command
        commands = VoiceCommand.query.filter_by(user_id=user_id, enabled=True).all()
        matched_command = None
        best_match_score = 0

        for command in commands:
            # Simple fuzzy matching - in production, use proper NLP
            command_phrase = command.phrase.lower()
            if command_phrase in transcript or transcript in command_phrase:
                match_score = len(set(command_phrase.split()) & set(transcript.split())) / len(set(command_phrase.split()) | set(transcript.split()))
                if match_score > best_match_score:
                    best_match_score = match_score
                    matched_command = command

        if matched_command and best_match_score > 0.5:  # 50% match threshold
            # Update command statistics
            matched_command.usage_count += 1
            matched_command.last_used = datetime.utcnow()
            if matched_command.average_confidence:
                matched_command.average_confidence = (matched_command.average_confidence + confidence) / 2
            else:
                matched_command.average_confidence = confidence
            db.session.commit()

            # Execute command based on type (this is simplified)
            result = execute_voice_command(matched_command, data)

            logger.info(f'Voice command executed: {matched_command.id} for user {user_id}')
            return jsonify({
                'command': matched_command.to_dict(),
                'result': result,
                'match_score': best_match_score
            })
        else:
            return jsonify({
                'error': 'No matching command found',
                'transcript': transcript,
                'suggestions': [cmd.phrase for cmd in commands[:5]]  # Suggest first 5 commands
            }), 404
    except Exception as e:
        logger.error(f'Error processing voice command: {str(e)}')
        return jsonify({'error': 'Failed to process voice command'}), 500

@voice_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_voice_stats():
    """Get voice command statistics for the current user"""
    try:
        user_id = get_jwt_identity()
        commands = VoiceCommand.query.filter_by(user_id=user_id).all()

        stats = {
            'total_commands': len(commands),
            'enabled_commands': len([c for c in commands if c.enabled]),
            'total_usage': sum(c.usage_count for c in commands),
            'most_used': max(commands, key=lambda c: c.usage_count).phrase if commands else None,
            'average_confidence': sum(c.average_confidence or 0 for c in commands) / max(1, len(commands))
        }

        return jsonify(stats)
    except Exception as e:
        logger.error(f'Error fetching voice stats: {str(e)}')
        return jsonify({'error': 'Failed to fetch voice statistics'}), 500

@voice_bp.route('/wake-words', methods=['GET'])
def get_wake_words():
    """Get available wake words"""
    wake_words = [
        'hey atom',
        'atom',
        'okay atom',
        'listen atom',
        'atom listen'
    ]
    return jsonify(wake_words)

@voice_bp.route('/languages', methods=['GET'])
def get_supported_languages():
    """Get supported languages for voice recognition"""
    languages = [
        {'code': 'en-US', 'name': 'English (US)'},
        {'code': 'en-GB', 'name': 'English (UK)'},
        {'code': 'es-ES', 'name': 'Spanish (Spain)'},
        {'code': 'fr-FR', 'name': 'French (France)'},
        {'code': 'de-DE', 'name': 'German (Germany)'},
        {'code': 'it-IT', 'name': 'Italian (Italy)'},
        {'code': 'pt-BR', 'name': 'Portuguese (Brazil)'},
        {'code': 'ja-JP', 'name': 'Japanese (Japan)'},
        {'code': 'ko-KR', 'name': 'Korean (Korea)'},
        {'code': 'zh-CN', 'name': 'Chinese (Mandarin)'}
    ]
    return jsonify(languages)

def execute_voice_command(command, data):
    """Execute a voice command based on its type/configuration"""
    # This is a simplified implementation
    # In production, this would integrate with various services

    phrase = command.phrase.lower()

    if 'create task' in phrase or 'add task' in phrase:
        # Create a task
        return {
            'action': 'create_task',
            'message': 'Task created successfully',
            'task': {
                'title': data.get('task_title', 'Voice-created task'),
                'description': 'Created via voice command'
            }
        }

    elif 'schedule' in phrase or 'meeting' in phrase:
        # Schedule a meeting
        return {
            'action': 'schedule_meeting',
            'message': 'Meeting scheduled successfully',
            'meeting': {
                'title': data.get('meeting_title', 'Voice-scheduled meeting'),
                'time': data.get('meeting_time', 'TBD')
            }
        }

    elif 'email' in phrase or 'send' in phrase:
        # Send an email
        return {
            'action': 'send_email',
            'message': 'Email sent successfully',
            'email': {
                'to': data.get('recipient', 'unknown@example.com'),
                'subject': data.get('subject', 'Voice-sent email')
            }
        }

    elif 'remind' in phrase or 'reminder' in phrase:
        # Set a reminder
        return {
            'action': 'set_reminder',
            'message': 'Reminder set successfully',
            'reminder': {
                'title': data.get('reminder_title', 'Voice reminder'),
                'time': data.get('reminder_time', 'in 1 hour')
            }
        }

    else:
        # Generic response
        return {
            'action': 'generic',
            'message': f'Executed command: {command.phrase}',
            'response': 'Command completed successfully'
        }
