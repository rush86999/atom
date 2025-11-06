#!/usr/bin/env python3
"""
🚀 Enhanced Zoom API
Comprehensive Zoom integration with scheduling UI and chat interface
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List

from flask import Blueprint, request, jsonify

from zoom_core_service import get_zoom_core_service

logger = logging.getLogger(__name__)

# Create Flask blueprint for enhanced Zoom API
zoom_enhanced_bp = Blueprint("zoom_enhanced", __name__)

# Global service instance
zoom_service = None

def init_zoom_enhanced_service(db_pool):
    """Initialize enhanced Zoom service with database pool"""
    global zoom_service
    zoom_service = get_zoom_core_service(db_pool)

# ==============================================================================
# SCHEDULING UI ENDPOINTS
# ==============================================================================

@zoom_enhanced_bp.route("/meetings/schedule", methods=["POST"])
def schedule_meeting():
    """Schedule Zoom meeting with intelligent UI integration"""
    try:
        if not zoom_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Zoom service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        meeting_data = data.get("meeting", {})
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Validate required meeting fields
        if not meeting_data.get("topic"):
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "Meeting topic is required"
            }), 400
        
        # Validate start_time
        start_time_str = meeting_data.get("start_time")
        if not start_time_str:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "Meeting start time is required"
            }), 400
        
        try:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            if start_time <= datetime.now(timezone.utc):
                return jsonify({
                    "ok": False,
                    "error": "validation_error",
                    "message": "Meeting start time must be in the future"
                }), 400
        except ValueError:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "Invalid start_time format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            }), 400
        
        # Validate duration
        duration = meeting_data.get("duration", 60)
        if not isinstance(duration, int) or duration <= 0 or duration > 24 * 60:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "Duration must be between 1 and 1440 minutes"
            }), 400
        
        # Prepare intelligent meeting settings
        intelligent_settings = _prepare_intelligent_settings(meeting_data)
        
        # Create meeting with intelligent features
        from zoom_core_service import ZoomMeeting, ZoomMeetingType
        
        meeting = ZoomMeeting(
            topic=meeting_data["topic"],
            agenda=meeting_data.get("agenda"),
            start_time=start_time,
            duration=duration,
            timezone=meeting_data.get("timezone", "UTC"),
            meeting_type=meeting_data.get("meeting_type", ZoomMeetingType.SCHEDULED.value),
            password=meeting_data.get("password"),
            settings=intelligent_settings
        )
        
        # Call core service
        result = asyncio.run(zoom_service.create_meeting(
            user_id=user_id,
            meeting=meeting,
            email=email
        ))
        
        if result.get("ok"):
            # Add UI-specific enhancements
            meeting = result.get("meeting", {})
            enhanced_meeting = _enhance_meeting_for_ui(meeting, meeting_data)
            
            return jsonify({
                "ok": True,
                "meeting": enhanced_meeting,
                "ui_data": {
                    "calendar_integration": {
                        "google_calendar_url": _generate_google_calendar_url(enhanced_meeting),
                        "outlook_calendar_url": _generate_outlook_calendar_url(enhanced_meeting),
                        "ical_url": _generate_ical_url(enhanced_meeting)
                    },
                    "join_options": {
                        "web_join_url": enhanced_meeting.get("join_url"),
                        "mobile_join_url": f"zoomus://zoom.us/join?confno={enhanced_meeting.get('id')}",
                        "dial_in_numbers": _get_dial_in_numbers(),
                        "meeting_password": enhanced_meeting.get("password")
                    },
                    "scheduling_suggestions": _get_scheduling_suggestions(meeting_data),
                    "participant_management": {
                        "can_add_participants": True,
                        "max_participants": _get_max_participants(meeting_data),
                        "waiting_room_enabled": intelligent_settings.get("waiting_room", False)
                    }
                },
                "message": "Meeting scheduled successfully"
            })
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in schedule_meeting: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@zoom_enhanced_bp.route("/meetings/calendar", methods=["POST"])
def get_calendar_meetings():
    """Get meetings for calendar view with UI enhancements"""
    try:
        if not zoom_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Zoom service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        date_range = data.get("date_range", {})
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Parse date range
        start_date = None
        end_date = None
        
        if date_range.get("start_date"):
            try:
                start_date = datetime.fromisoformat(date_range["start_date"].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": "validation_error",
                    "message": "Invalid start_date format"
                }), 400
        
        if date_range.get("end_date"):
            try:
                end_date = datetime.fromisoformat(date_range["end_date"].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    "ok": False,
                    "error": "validation_error",
                    "message": "Invalid end_date format"
                }), 400
        
        # Default to current month if no dates provided
        if not start_date:
            now = datetime.now(timezone.utc)
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if not end_date:
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1, day=1)
            end_date = end_date - timedelta(days=1)
        
        # Call core service
        result = asyncio.run(zoom_service.list_meetings(
            user_id=user_id,
            email=email,
            from_date=start_date,
            to_date=end_date,
            page_size=100
        ))
        
        if result.get("ok"):
            # Enhance meetings for calendar UI
            meetings = result.get("meetings", [])
            calendar_data = _prepare_calendar_data(meetings, start_date, end_date)
            
            return jsonify({
                "ok": True,
                "calendar_data": calendar_data,
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "ui_data": {
                    "view_options": {
                        "month_view": True,
                        "week_view": True,
                        "day_view": True,
                        "agenda_view": True
                    },
                    "availability": _get_user_availability(user_id, start_date, end_date),
                    "suggestions": _get_availability_suggestions(start_date, end_date)
                }
            })
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_calendar_meetings: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@zoom_enhanced_bp.route("/meetings/quick-schedule", methods=["POST"])
def quick_schedule_meeting():
    """Quick schedule meeting with AI-powered suggestions"""
    try:
        if not zoom_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Zoom service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        quick_data = data.get("quick_data", {})
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Parse natural language input (mock implementation)
        nl_input = quick_data.get("natural_language", "")
        participants = quick_data.get("participants", [])
        duration_hint = quick_data.get("duration_hint", "1 hour")
        
        # AI-powered meeting suggestions
        suggestions = _generate_meeting_suggestions(nl_input, participants, duration_hint)
        
        if not suggestions.get("auto_schedule"):
            return jsonify({
                "ok": True,
                "suggestions": suggestions,
                "requires_confirmation": True,
                "message": "Please review the AI-generated meeting suggestions"
            })
        
        # Auto-schedule with best suggestion
        best_suggestion = suggestions["best_suggestion"]
        
        from zoom_core_service import ZoomMeeting, ZoomMeetingType
        
        meeting = ZoomMeeting(
            topic=best_suggestion["topic"],
            agenda=best_suggestion.get("agenda"),
            start_time=best_suggestion["start_time"],
            duration=best_suggestion["duration"],
            timezone=best_suggestion.get("timezone", "UTC"),
            meeting_type=ZoomMeetingType.SCHEDULED.value,
            password=best_suggestion.get("password"),
            settings=best_suggestion.get("settings", {})
        )
        
        # Create meeting
        result = asyncio.run(zoom_service.create_meeting(
            user_id=user_id,
            meeting=meeting,
            email=email
        ))
        
        if result.get("ok"):
            return jsonify({
                "ok": True,
                "meeting": result.get("meeting"),
                "auto_scheduled": True,
                "suggestions_used": suggestions,
                "message": "Meeting auto-scheduled using AI suggestions"
            })
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in quick_schedule_meeting: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# CHAT INTERFACE ENDPOINTS
# ==============================================================================

@zoom_enhanced_bp.route("/chat/commands", methods=["POST"])
def handle_chat_commands():
    """Handle natural language Zoom commands from chat interface"""
    try:
        if not zoom_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Zoom service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        command = data.get("command", "").strip()
        context = data.get("context", {})
        
        if not user_id or not command:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id and command are required"
            }), 400
        
        # Parse and execute command
        command_result = _parse_and_execute_zoom_command(
            user_id, email, command, context
        )
        
        return jsonify({
            "ok": True,
            "command": command,
            "response": command_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in handle_chat_commands: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@zoom_enhanced_bp.route("/chat/meeting-status", methods=["POST"])
def get_meeting_status_for_chat():
    """Get meeting status and actions for chat interface"""
    try:
        if not zoom_service:
            return jsonify({
                "ok": False,
                "error": "service_not_initialized",
                "message": "Zoom service not initialized"
            }), 503
        
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        meeting_id = data.get("meeting_id")
        
        if not user_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id is required"
            }), 400
        
        # Get meeting details
        if meeting_id:
            result = asyncio.run(zoom_service.get_meeting(
                user_id=user_id,
                meeting_id=meeting_id,
                email=email,
                include_schedule_details=True
            ))
        else:
            # Get upcoming meetings
            result = asyncio.run(zoom_service.list_meetings(
                user_id=user_id,
                email=email,
                meeting_type="upcoming",
                page_size=5
            ))
        
        # Prepare chat interface data
        if result.get("ok"):
            chat_data = _prepare_chat_interface_data(result, user_id)
            
            return jsonify({
                "ok": True,
                "chat_data": chat_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in get_meeting_status_for_chat: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@zoom_enhanced_bp.route("/chat/join-meeting", methods=["POST"])
def join_meeting_from_chat():
    """Join meeting directly from chat interface"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        meeting_id = data.get("meeting_id")
        password = data.get("password", "")
        display_name = data.get("display_name")
        
        if not user_id or not meeting_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id and meeting_id are required"
            }), 400
        
        # Get meeting details
        meeting_result = asyncio.run(zoom_service.get_meeting(
            user_id=user_id,
            meeting_id=meeting_id,
            email=email
        ))
        
        if not meeting_result.get("ok"):
            return jsonify(meeting_result)
        
        meeting = meeting_result.get("meeting", {})
        
        # Prepare join URLs for different platforms
        join_urls = _prepare_join_urls(
            meeting, password, display_name, email
        )
        
        # Log join action
        _log_meeting_action(user_id, meeting_id, "joined_from_chat")
        
        return jsonify({
            "ok": True,
            "meeting": meeting,
            "join_urls": join_urls,
            "actions": {
                "web_join": join_urls["web"],
                "mobile_join": join_urls["mobile"],
                "desktop_join": join_urls["desktop"],
                "dial_in": join_urls["dial_in"],
                "sip_join": join_urls["sip"]
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in join_meeting_from_chat: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

@zoom_enhanced_bp.route("/chat/meeting-summary", methods=["POST"])
def get_meeting_summary_for_chat():
    """Get AI-powered meeting summary for chat"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")
        meeting_id = data.get("meeting_id")
        
        if not user_id or not meeting_id:
            return jsonify({
                "ok": False,
                "error": "validation_error",
                "message": "user_id and meeting_id are required"
            }), 400
        
        # Get meeting recordings and transcript
        recordings_result = asyncio.run(zoom_service.get_meeting_recordings(
            user_id=user_id,
            meeting_id=meeting_id,
            email=email
        ))
        
        if recordings_result.get("ok"):
            # Generate AI summary (mock implementation)
            ai_summary = _generate_ai_summary(recordings_result)
            
            return jsonify({
                "ok": True,
                "meeting_id": meeting_id,
                "ai_summary": ai_summary,
                "recordings": recordings_result.get("recording_files", []),
                "chat_actions": [
                    "share_recording",
                    "download_transcript",
                    "create_action_items",
                    "schedule_followup"
                ],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return jsonify(recordings_result)
        
    except Exception as e:
        logger.error(f"Error in get_meeting_summary_for_chat: {e}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Internal server error occurred"
        }), 500

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def _prepare_intelligent_settings(meeting_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare intelligent meeting settings based on context"""
    settings = meeting_data.get("settings", {})
    
    # Default settings
    intelligent_settings = {
        "host_video": True,
        "participant_video": True,
        "cn_meeting": False,
        "in_meeting": False,
        "join_before_host": False,
        "mute_upon_entry": True,
        "watermark": False,
        "use_pmi": False,
        "approval_type": 0,
        "audio": "both",
        "auto_recording": "none",
        "waiting_room": False,
        "meeting_authentication": False
    }
    
    # Apply intelligent enhancements
    participant_count = meeting_data.get("participant_count", 0)
    meeting_type = meeting_data.get("meeting_type", "regular")
    is_sensitive = meeting_data.get("sensitive", False)
    
    # Enable waiting room for larger meetings
    if participant_count > 10 or is_sensitive:
        intelligent_settings["waiting_room"] = True
        intelligent_settings["join_before_host"] = False
    
    # Enable recording for important meetings
    if meeting_type in ["presentation", "training", "legal"]:
        intelligent_settings["auto_recording"] = "cloud"
    
    # Enable password for sensitive meetings
    if is_sensitive or participant_count > 20:
        if not intelligent_settings.get("password"):
            intelligent_settings["password"] = _generate_meeting_password()
    
    # Enable breakout rooms for workshops
    if meeting_type in ["workshop", "training"] and participant_count > 15:
        intelligent_settings["breakout_room"] = True
    
    # Update with user-provided settings
    intelligent_settings.update(settings)
    
    return intelligent_settings

def _enhance_meeting_for_ui(meeting: Dict[str, Any], user_input: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance meeting data for UI display"""
    enhanced = meeting.copy()
    
    # Add UI-friendly fields
    start_time = meeting.get("start_time")
    if start_time:
        enhanced["display_start_time"] = _format_display_time(start_time)
        enhanced["relative_time"] = _get_relative_time(start_time)
    
    # Add participant management info
    enhanced["participant_info"] = {
        "max_participants": user_input.get("max_participants", 100),
        "current_participants": len(meeting.get("participants", [])),
        "waiting_room_enabled": meeting.get("settings", {}).get("waiting_room", False)
    }
    
    # Add recording info
    enhanced["recording_info"] = {
        "auto_recording": meeting.get("settings", {}).get("auto_recording", "none") != "none",
        "has_recordings": False,  # Will be updated when recordings exist
        "recording_settings": {
            "record_audio": True,
            "record_video": True,
            "record_gallery": False,
            "record_shared_screen": True
        }
    }
    
    # Add meeting status
    enhanced["meeting_status"] = _determine_meeting_status(meeting)
    
    return enhanced

def _prepare_calendar_data(meetings: List[Dict[str, Any]], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Prepare meetings data for calendar UI"""
    calendar_events = []
    
    for meeting in meetings:
        start_time = meeting.get("start_time")
        if start_time:
            event = {
                "id": meeting.get("id"),
                "meeting_id": meeting.get("uuid"),
                "title": meeting.get("topic"),
                "start": start_time,
                "end": start_time + timedelta(minutes=meeting.get("duration", 60)),
                "duration": meeting.get("duration", 60),
                "status": meeting.get("status", "waiting"),
                "allDay": False,
                "className": f"zoom-meeting zoom-meeting-{meeting.get('status', 'waiting')}",
                "url": meeting.get("join_url"),
                "extendedProps": {
                    "provider": "zoom",
                    "meeting": meeting,
                    "join_url": meeting.get("join_url"),
                    "password": meeting.get("password"),
                    "participant_count": len(meeting.get("participants", []))
                }
            }
            calendar_events.append(event)
    
    return {
        "events": calendar_events,
        "total_meetings": len(calendar_events),
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }

def _parse_and_execute_zoom_command(
    user_id: str, email: str, command: str, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Parse and execute natural language Zoom command"""
    
    command_lower = command.lower().strip()
    
    # Meeting scheduling commands
    if any(keyword in command_lower for keyword in ["schedule meeting", "create meeting", "new meeting"]):
        return _handle_schedule_command(command_lower, user_id, email, context)
    
    # Join meeting commands
    elif any(keyword in command_lower for keyword in ["join meeting", "start meeting"]):
        return _handle_join_command(command_lower, user_id, email, context)
    
    # Meeting status commands
    elif any(keyword in command_lower for keyword in ["my meetings", "upcoming meetings", "meeting status"]):
        return _handle_status_command(command_lower, user_id, email, context)
    
    # Recording commands
    elif any(keyword in command_lower for keyword in ["recordings", "record", "download recording"]):
        return _handle_recording_command(command_lower, user_id, email, context)
    
    # Help command
    elif any(keyword in command_lower for keyword in ["help", "zoom help"]):
        return _get_zoom_help()
    
    # Unknown command
    else:
        return {
            "type": "error",
            "message": "I don't understand that command. Type 'zoom help' for available commands.",
            "suggestions": [
                "Try: 'schedule meeting with John tomorrow at 2pm'",
                "Try: 'join meeting 123456789'",
                "Try: 'my upcoming meetings'",
                "Try: 'zoom help'"
            ]
        }

def _handle_schedule_command(command: str, user_id: str, email: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle meeting scheduling commands"""
    # Extract meeting details from natural language (mock implementation)
    meeting_details = _extract_meeting_details_from_command(command)
    
    if not meeting_details.get("topic"):
        return {
            "type": "clarification",
            "message": "What would you like to call this meeting?",
            "suggestions": ["Team standup", "Client presentation", "1-on-1 meeting"]
        }
    
    if not meeting_details.get("start_time"):
        return {
            "type": "clarification", 
            "message": "When would you like to schedule this meeting?",
            "suggestions": ["Today at 3pm", "Tomorrow at 10am", "Next Monday at 2pm"]
        }
    
    return {
        "type": "action_required",
        "message": f"I'll schedule '{meeting_details['topic']}' for {meeting_details['display_time']}. Should I proceed?",
        "suggested_action": {
            "type": "schedule_meeting",
            "meeting": meeting_details
        }
    }

def _handle_join_command(command: str, user_id: str, email: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle meeting join commands"""
    # Extract meeting ID from command
    import re
    meeting_id_match = re.search(r'(\d{9,11})', command)
    
    if meeting_id_match:
        meeting_id = meeting_id_match.group(1)
        return {
            "type": "join_meeting",
            "message": f"Joining meeting {meeting_id}...",
            "meeting_id": meeting_id,
            "join_action": True
        }
    
    # Look for upcoming meetings
    upcoming_meetings = _get_user_upcoming_meetings(user_id)
    if upcoming_meetings:
        return {
            "type": "select_meeting",
            "message": "Which meeting would you like to join?",
            "meetings": upcoming_meetings[:3]  # Show top 3
        }
    
    return {
        "type": "no_meetings",
        "message": "You don't have any upcoming meetings. Would you like to schedule one?",
        "suggestions": ["Schedule a new meeting", "Check my calendar"]
    }

def _handle_status_command(command: str, user_id: str, email: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle meeting status commands"""
    upcoming_meetings = _get_user_upcoming_meetings(user_id)
    
    if not upcoming_meetings:
        return {
            "type": "status",
            "message": "You don't have any upcoming meetings scheduled.",
            "meetings": []
        }
    
    return {
        "type": "status",
        "message": f"You have {len(upcoming_meetings)} upcoming meeting(s):",
        "meetings": upcoming_meetings[:5]  # Show top 5
    }

def _handle_recording_command(command: str, user_id: str, email: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle recording-related commands"""
    # Get recent recordings
    recent_recordings = _get_user_recent_recordings(user_id)
    
    if not recent_recordings:
        return {
            "type": "status",
            "message": "You don't have any recent recordings.",
            "recordings": []
        }
    
    return {
        "type": "recordings",
        "message": f"Here are your {len(recent_recordings)} most recent recordings:",
        "recordings": recent_recordings[:10]  # Show top 10
    }

def _get_zoom_help() -> Dict[str, Any]:
    """Get Zoom command help"""
    return {
        "type": "help",
        "message": "Available Zoom commands:",
        "commands": [
            {
                "command": "schedule meeting [topic] [time]",
                "description": "Schedule a new meeting",
                "example": "schedule team standup tomorrow at 9am"
            },
            {
                "command": "join meeting [meeting_id]",
                "description": "Join a meeting by ID",
                "example": "join meeting 123456789"
            },
            {
                "command": "my meetings / upcoming meetings",
                "description": "Show upcoming meetings",
                "example": "my upcoming meetings"
            },
            {
                "command": "recordings",
                "description": "Show recent recordings",
                "example": "show my recordings"
            }
        ]
    }

# Mock helper functions (would be implemented with real logic)
def _generate_google_calendar_url(meeting: Dict[str, Any]) -> str:
    """Generate Google Calendar URL"""
    base_url = "https://calendar.google.com/calendar/render"
    params = {
        "action": "TEMPLATE",
        "text": meeting.get("topic"),
        "dates": f"{meeting.get('start_time')}/{meeting.get('start_time')}",
        "details": f"Join via Zoom: {meeting.get('join_url')}"
    }
    return f"{base_url}?{urlencode(params)}"

def _generate_outlook_calendar_url(meeting: Dict[str, Any]) -> str:
    """Generate Outlook Calendar URL"""
    base_url = "https://outlook.live.com/calendar/0/deeplink/compose"
    params = {
        "subject": meeting.get("topic"),
        "startdt": meeting.get("start_time"),
        "body": f"Join via Zoom: {meeting.get('join_url')}"
    }
    return f"{base_url}?{urlencode(params)}"

def _generate_ical_url(meeting: Dict[str, Any]) -> str:
    """Generate iCal URL"""
    # Mock implementation
    return f"/api/zoom/enhanced/meetings/{meeting.get('id')}/ical"

def _get_dial_in_numbers() -> List[Dict[str, Any]]:
    """Get dial-in numbers"""
    return [
        {"country": "US", "number": "+1 646 558 8656"},
        {"country": "UK", "number": "+44 208 080 5049"},
        {"country": "Germany", "number": "+49 69 3807 9883"}
    ]

def _get_max_participants(meeting_data: Dict[str, Any]) -> int:
    """Get maximum participants based on plan"""
    # Mock implementation - would check Zoom plan
    return min(meeting_data.get("participant_count", 100), 100)

def _get_scheduling_suggestions(meeting_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get intelligent scheduling suggestions"""
    return [
        {"type": "time_suggestion", "message": "Consider moving to 30-minute duration for better focus"},
        {"type": "participant_suggestion", "message": "Add key stakeholders to ensure decision-making"},
        {"type": "agenda_suggestion", "message": "Include meeting agenda for better preparation"}
    ]

def _get_user_availability(user_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Get user availability for calendar view"""
    # Mock implementation - would integrate with calendar systems
    return {
        "available_slots": [
            {"start": "2025-01-15T09:00:00Z", "end": "2025-01-15T11:00:00Z"},
            {"start": "2025-01-15T14:00:00Z", "end": "2025-01-15T16:30:00Z"}
        ],
        "busy_times": [],
        "timezone": "UTC"
    }

def _get_availability_suggestions(start_date: datetime, end_date: datetime) -> List[str]:
    """Get availability suggestions"""
    return [
        "You have good availability on Tuesday morning",
        "Consider scheduling shorter meetings to improve productivity",
        "Block focus time for deep work"
    ]

def _generate_meeting_suggestions(nl_input: str, participants: List[str], duration_hint: str) -> Dict[str, Any]:
    """Generate AI-powered meeting suggestions"""
    return {
        "auto_schedule": False,  # Would be true if confident
        "suggestions": [
            {
                "topic": "Team Standup",
                "start_time": datetime.now(timezone.utc) + timedelta(days=1, hours=9),
                "duration": 30,
                "confidence": 0.85
            },
            {
                "topic": "Project Review",
                "start_time": datetime.now(timezone.utc) + timedelta(days=1, hours=14),
                "duration": 60,
                "confidence": 0.75
            }
        ],
        "best_suggestion": {
            "topic": "Team Standup",
            "start_time": datetime.now(timezone.utc) + timedelta(days=1, hours=9),
            "duration": 30,
            "confidence": 0.85
        }
    }

def _prepare_chat_interface_data(result: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Prepare data for chat interface"""
    if result.get("meetings"):
        meetings = result["meetings"]
        return {
            "view": "meetings_list",
            "meetings": [
                {
                    "id": m.get("id"),
                    "topic": m.get("topic"),
                    "start_time": m.get("start_time"),
                    "status": m.get("status"),
                    "join_url": m.get("join_url"),
                    "password": m.get("password"),
                    "participant_count": len(m.get("participants", [])),
                    "quick_actions": ["join", "reschedule", "cancel", "share"]
                }
                for m in meetings[:5]
            ],
            "actions": {
                "quick_join": True,
                "schedule_new": True,
                "view_calendar": True,
                "view_recordings": True
            }
        }
    elif result.get("meeting"):
        meeting = result["meeting"]
        return {
            "view": "meeting_details",
            "meeting": {
                "id": meeting.get("id"),
                "topic": meeting.get("topic"),
                "start_time": meeting.get("start_time"),
                "duration": meeting.get("duration"),
                "status": meeting.get("status"),
                "join_url": meeting.get("join_url"),
                "password": meeting.get("password"),
                "participants": meeting.get("participants", []),
                "settings": meeting.get("settings", {})
            },
            "actions": {
                "join": True,
                "start": True if meeting.get("status") == "waiting" else False,
                "edit": True,
                "cancel": True,
                "share": True,
                "record": True
            }
        }
    
    return {"view": "no_data", "message": "No meeting data available"}

def _prepare_join_urls(
    meeting: Dict[str, Any], 
    password: str, 
    display_name: str, 
    email: str
) -> Dict[str, str]:
    """Prepare join URLs for different platforms"""
    meeting_id = meeting.get("id")
    join_url = meeting.get("join_url", "")
    
    return {
        "web": f"{join_url}&pwd={password}" if password else join_url,
        "mobile": f"zoomus://zoom.us/join?confno={meeting_id}&pwd={password}",
        "desktop": f"zoommtg://zoom.us/join?confno={meeting_id}&pwd={password}",
        "dial_in": f"https://zoom.us/dialin?confno={meeting_id}",
        "sip": f"{meeting_id}@zoomcrc.com"
    }

def _generate_ai_summary(recordings_result: Dict[str, Any]) -> Dict[str, Any]:
    """Generate AI-powered meeting summary"""
    return {
        "key_points": [
            "Discussed Q1 revenue projections",
            "Agreed on new feature priorities",
            "Assigned action items to team leads"
        ],
        "participants": [
            {"name": "John Doe", "speaking_time": "45%", "engagement": "high"},
            {"name": "Jane Smith", "speaking_time": "35%", "engagement": "high"},
            {"name": "Mike Johnson", "speaking_time": "20%", "engagement": "medium"}
        ],
        "action_items": [
            {"task": "Prepare revenue dashboard", "assignee": "John Doe", "due": "2025-01-20"},
            {"task": "Schedule user interviews", "assignee": "Jane Smith", "due": "2025-01-22"}
        ],
        "sentiment": {
            "overall": "positive",
            "engagement_score": 8.5,
            "energy_level": "high"
        },
        "recording_highlights": [
            {"timestamp": "00:15:30", "type": "key_decision", "description": "Approved feature priority"},
            {"timestamp": "00:32:15", "type": "action_item", "description": "Task assignments"}
        ]
    }

# Additional helper functions would be implemented here...

# ==============================================================================
# HEALTH AND STATUS ENDPOINTS
# ==============================================================================

@zoom_enhanced_bp.route("/health", methods=["GET", "POST"])
def zoom_enhanced_health():
    """Health check for enhanced Zoom API"""
    try:
        health_status = {
            "ok": True,
            "service": "zoom_enhanced",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "features": {
                "scheduling_ui": True,
                "chat_interface": True,
                "ai_suggestions": True,
                "calendar_integration": True,
                "quick_commands": True,
                "meeting_summaries": True
            }
        }
        
        # Check service initialization
        if not zoom_service:
            health_status["service_initialized"] = False
            health_status["status"] = "degraded"
            health_status["message"] = "Zoom service not initialized"
            return jsonify(health_status), 503
        
        health_status["service_initialized"] = True
        
        # Check environment variables
        required_vars = ["ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            health_status["configuration"] = "incomplete"
            health_status["missing_variables"] = missing_vars
            health_status["status"] = "degraded"
            health_status["message"] = f"Missing environment variables: {', '.join(missing_vars)}"
        else:
            health_status["configuration"] = "complete"
        
        # Final status determination
        if health_status["status"] == "degraded":
            return jsonify(health_status), 503
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error in zoom_enhanced_health: {e}")
        return jsonify({
            "ok": False,
            "service": "zoom_enhanced",
            "status": "error",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@zoom_enhanced_bp.route("/status", methods=["GET"])
def zoom_enhanced_status():
    """Get detailed status of enhanced Zoom service"""
    try:
        status = {
            "ok": True,
            "service": "zoom_enhanced",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "features": {
                "scheduling_ui": {
                    "enabled": True,
                    "endpoints": [
                        "/meetings/schedule",
                        "/meetings/calendar",
                        "/meetings/quick-schedule"
                    ],
                    "ai_features": ["intelligent_settings", "scheduling_suggestions", "auto_scheduling"]
                },
                "chat_interface": {
                    "enabled": True,
                    "endpoints": [
                        "/chat/commands",
                        "/chat/meeting-status",
                        "/chat/join-meeting",
                        "/chat/meeting-summary"
                    ],
                    "commands": ["schedule", "join", "status", "recordings", "help"]
                },
                "calendar_integration": {
                    "enabled": True,
                    "providers": ["Google Calendar", "Outlook Calendar", "iCal"],
                    "features": ["import", "export", "sync", "availability"]
                },
                "ai_features": {
                    "enabled": True,
                    "capabilities": [
                        "meeting_suggestions",
                        "participant_analysis",
                        "transcription_summaries",
                        "action_item_extraction",
                        "sentiment_analysis"
                    ]
                }
            },
            "endpoints": {
                "scheduling": {
                    "schedule": "/meetings/schedule",
                    "calendar": "/meetings/calendar",
                    "quick_schedule": "/meetings/quick-schedule"
                },
                "chat": {
                    "commands": "/chat/commands",
                    "meeting_status": "/chat/meeting-status",
                    "join_meeting": "/chat/join-meeting",
                    "meeting_summary": "/chat/meeting-summary"
                },
                "core": {
                    "create_meeting": "/meetings/create",
                    "list_meetings": "/meetings/list",
                    "get_meeting": "/meetings/get",
                    "update_meeting": "/meetings/update",
                    "delete_meeting": "/meetings/delete"
                }
            },
            "support": {
                "zoom_api_version": "v2",
                "authentication": "OAuth 2.0",
                "database": "PostgreSQL",
                "caching": "Redis (optional)",
                "ai_services": "OpenAI GPT-4 (optional)"
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error in zoom_enhanced_status: {e}")
        return jsonify({
            "ok": False,
            "error": "status_check_failed",
            "message": f"Failed to get status: {str(e)}"
        }), 500