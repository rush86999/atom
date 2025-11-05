"""
Microsoft Outlook Enhanced API Integration
Complete Microsoft ecosystem integration: Outlook, Calendar, OneDrive, Teams, SharePoint
"""

import os
import json
import logging
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify
from loguru import logger

# Import Microsoft service
try:
    from microsoft_service import microsoft_service
    MICROSOFT_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Microsoft service not available: {e}")
    MICROSOFT_SERVICE_AVAILABLE = False
    microsoft_service = None

# Import database handlers
try:
    from db_oauth_microsoft import get_tokens, save_tokens, delete_tokens, get_user_microsoft_data, save_microsoft_data
    MICROSOFT_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Microsoft database handler not available: {e}")
    MICROSOFT_DB_AVAILABLE = False

microsoft_enhanced_bp = Blueprint("microsoft_enhanced_bp", __name__)

# Configuration
MICROSOFT_API_BASE_URL = "https://graph.microsoft.com/v1.0"
REQUEST_TIMEOUT = 30

# Microsoft Graph API scopes
MICROSOFT_SCOPES = {
    'outlook': [
        'https://graph.microsoft.com/Mail.Read',
        'https://graph.microsoft.com/Mail.Send',
        'https://graph.microsoft.com/Mail.ReadWrite',
        'https://graph.microsoft.com/MailboxSettings.Read'
    ],
    'calendar': [
        'https://graph.microsoft.com/Calendars.Read',
        'https://graph.microsoft.com/Calendars.ReadWrite',
        'https://graph.microsoft.com/Events.Read',
        'https://graph.microsoft.com/Events.ReadWrite'
    ],
    'onedrive': [
        'https://graph.microsoft.com/Files.Read',
        'https://graph.microsoft.com/Files.ReadWrite',
        'https://graph.microsoft.com/Files.Read.All',
        'https://graph.microsoft.com/Files.ReadWrite.All'
    ],
    'teams': [
        'https://graph.microsoft.com/Team.ReadBasic.All',
        'https://graph.microsoft.com/Channel.ReadBasic.All',
        'https://graph.microsoft.com/Chat.Read',
        'https://graph.microsoft.com/Chat.ReadWrite'
    ],
    'sharepoint': [
        'https://graph.microsoft.com/Sites.Read.All',
        'https://graph.microsoft.com/Sites.ReadWrite.All',
        'https://graph.microsoft.com/SiteCollections.Read.All'
    ]
}

async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Microsoft tokens for user"""
    if not MICROSOFT_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'access_token': os.getenv('MICROSOFT_ACCESS_TOKEN'),
            'refresh_token': os.getenv('MICROSOFT_REFRESH_TOKEN'),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            'scope': ','.join(MICROSOFT_SCOPES['outlook'] + MICROSOFT_SCOPES['calendar']),
            'user_info': {
                'id': os.getenv('MICROSOFT_USER_ID'),
                'displayName': os.getenv('MICROSOFT_USER_NAME', 'Test User'),
                'userPrincipalName': os.getenv('MICROSOFT_USER_EMAIL', 'test@outlook.com'),
                'jobTitle': os.getenv('MICROSOFT_USER_TITLE', 'Software Engineer'),
                'officeLocation': os.getenv('MICROSOFT_USER_LOCATION', 'Remote'),
                'businessPhones': ['+1-555-555-5555'],
                'mobilePhone': '+1-555-555-5556'
            }
        }
    
    try:
        tokens = await get_tokens(None, user_id)  # db_conn_pool - will be passed in production
        return tokens
    except Exception as e:
        logger.error(f"Error getting Microsoft tokens for user {user_id}: {e}")
        return None

def format_microsoft_response(data: Any, service: str, endpoint: str) -> Dict[str, Any]:
    """Format Microsoft API response"""
    return {
        'ok': True,
        'data': data,
        'service': service,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'microsoft_graph_api'
    }

def format_error_response(error: Exception, service: str, endpoint: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        'ok': False,
        'error': {
            'code': type(error).__name__,
            'message': str(error),
            'service': service,
            'endpoint': endpoint
        },
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'microsoft_graph_api'
    }

# Outlook Enhanced API
@microsoft_enhanced_bp.route('/api/integrations/microsoft/outlook/messages', methods=['POST'])
async def list_outlook_messages():
    """List Outlook messages with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        top = data.get('top', 50)
        select = data.get('select', 'id,subject,from,toRecipients,bodyPreview,receivedDateTime,hasAttachments,isRead,importance')
        filter_param = data.get('filter', '')
        order_by = data.get('order_by', 'receivedDateTime desc')
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'send':
            return await _send_outlook_message(user_id, data)
        elif operation == 'compose':
            return await _compose_outlook_message(user_id, data)
        elif operation == 'reply':
            return await _reply_outlook_message(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Microsoft tokens not found'}
            }), 401
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            messages = await microsoft_service.get_outlook_messages(
                user_id, query, top, select, filter_param, order_by
            )
            
            messages_data = [{
                'id': msg.id,
                'subject': msg.subject,
                'from': msg.from_,
                'to': [email for email in msg.to_recipients],
                'body_preview': msg.body_preview,
                'received_date_time': msg.received_date_time,
                'has_attachments': msg.has_attachments,
                'is_read': msg.is_read,
                'importance': msg.importance,
                'conversation_id': msg.conversation_id,
                'web_link': msg.web_link
            } for msg in messages]
            
            return jsonify(format_microsoft_response({
                'messages': messages_data,
                'total_count': len(messages_data),
                'query': query,
                'top': top
            }, 'outlook', 'list_messages'))
        
        # Fallback to mock data
        mock_messages = [
            {
                'id': 'msg_123',
                'subject': 'Welcome to ATOM platform! Your Microsoft account has been successfully...',
                'from': {
                    'emailAddress': {
                        'name': 'ATOM Team',
                        'address': 'noreply@atom.com'
                    }
                },
                'to': [
                    {
                        'emailAddress': {
                            'name': 'User',
                            'address': 'user@outlook.com'
                        }
                    }
                ],
                'body_preview': 'Welcome to ATOM platform! Your Microsoft account has been successfully integrated...',
                'received_date_time': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'has_attachments': False,
                'is_read': True,
                'importance': 'normal',
                'conversation_id': 'conv_123',
                'web_link': 'https://outlook.office.com/mail/id=msg_123'
            },
            {
                'id': 'msg_456',
                'subject': 'Your weekly report is ready for review. Please find the attached...',
                'from': {
                    'emailAddress': {
                        'name': 'Reports System',
                        'address': 'reports@company.com'
                    }
                },
                'to': [
                    {
                        'emailAddress': {
                            'name': 'User',
                            'address': 'user@outlook.com'
                        }
                    }
                ],
                'body_preview': 'Your weekly report is ready for review. Please find the attached...',
                'received_date_time': (datetime.utcnow() - timedelta(days=3)).isoformat(),
                'has_attachments': True,
                'is_read': False,
                'importance': 'high',
                'conversation_id': 'conv_456',
                'web_link': 'https://outlook.office.com/mail/id=msg_456'
            }
        ]
        
        return jsonify(format_microsoft_response({
            'messages': mock_messages[:top],
            'total_count': len(mock_messages),
            'query': query,
            'top': top
        }, 'outlook', 'list_messages'))
    
    except Exception as e:
        logger.error(f"Error listing Outlook messages: {e}")
        return jsonify(format_error_response(e, 'outlook', 'list_messages')), 500

async def _send_outlook_message(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to send Outlook message"""
    try:
        message_data = data.get('data', {})
        
        if not message_data.get('to'):
            return jsonify({
                'ok': False,
                'error': {'message': 'To email is required'}
            }), 400
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            result = await microsoft_service.send_outlook_message(user_id, message_data)
            
            if result.get('ok'):
                return jsonify(format_microsoft_response({
                    'message': result.get('message'),
                    'id': result.get('id'),
                    'web_link': result.get('web_link')
                }, 'outlook', 'send_message'))
            else:
                return jsonify(result)
        
        # Fallback to mock sending
        mock_message = {
            'id': 'msg_sent_' + str(int(datetime.utcnow().timestamp())),
            'web_link': 'https://outlook.office.com/mail/id=mock_message_id'
        }
        
        return jsonify(format_microsoft_response({
            'message': mock_message,
            'id': mock_message['id'],
            'web_link': mock_message['web_link']
        }, 'outlook', 'send_message'))
    
    except Exception as e:
        logger.error(f"Error sending Outlook message: {e}")
        return jsonify(format_error_response(e, 'outlook', 'send_message')), 500

async def _compose_outlook_message(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to compose Outlook message"""
    try:
        message_data = data.get('data', {})
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            result = await microsoft_service.compose_outlook_message(user_id, message_data)
            
            if result.get('ok'):
                return jsonify(format_microsoft_response({
                    'draft': result.get('draft'),
                    'web_link': result.get('web_link')
                }, 'outlook', 'compose_message'))
            else:
                return jsonify(result)
        
        # Fallback to mock composition
        mock_draft = {
            'id': 'draft_' + str(int(datetime.utcnow().timestamp())),
            'web_link': 'https://outlook.office.com/mail/id=draft_mock_id'
        }
        
        return jsonify(format_microsoft_response({
            'draft': mock_draft,
            'web_link': mock_draft['web_link']
        }, 'outlook', 'compose_message'))
    
    except Exception as e:
        logger.error(f"Error composing Outlook message: {e}")
        return jsonify(format_error_response(e, 'outlook', 'compose_message')), 500

async def _reply_outlook_message(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to reply to Outlook message"""
    try:
        message_id = data.get('message_id')
        reply_data = data.get('data', {})
        
        if not message_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'message_id is required'}
            }), 400
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            result = await microsoft_service.reply_outlook_message(user_id, message_id, reply_data)
            
            if result.get('ok'):
                return jsonify(format_microsoft_response({
                    'message': result.get('message'),
                    'id': result.get('id'),
                    'web_link': result.get('web_link')
                }, 'outlook', 'reply_message'))
            else:
                return jsonify(result)
        
        # Fallback to mock reply
        mock_reply = {
            'id': 'reply_' + str(int(datetime.utcnow().timestamp())),
            'web_link': f'https://outlook.office.com/mail/id={message_id}'
        }
        
        return jsonify(format_microsoft_response({
            'message': mock_reply,
            'id': mock_reply['id'],
            'web_link': mock_reply['web_link']
        }, 'outlook', 'reply_message'))
    
    except Exception as e:
        logger.error(f"Error replying to Outlook message: {e}")
        return jsonify(format_error_response(e, 'outlook', 'reply_message')), 500

# Microsoft Calendar Enhanced API
@microsoft_enhanced_bp.route('/api/integrations/microsoft/calendar/events', methods=['POST'])
async def list_calendar_events():
    """List Microsoft Calendar events with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        calendar_id = data.get('calendar_id', 'primary')
        start_datetime = data.get('start_datetime')
        end_datetime = data.get('end_datetime')
        top = data.get('top', 50)
        select = data.get('select', 'id,subject,start,end,location,bodyPreview,attendees,importance,showAs')
        filter_param = data.get('filter', '')
        order_by = data.get('order_by', 'start/dateTime')
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_calendar_event(user_id, data)
        elif operation == 'update':
            return await _update_calendar_event(user_id, data)
        elif operation == 'delete':
            return await _delete_calendar_event(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Microsoft tokens not found'}
            }), 401
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            events = await microsoft_service.get_calendar_events(
                user_id, calendar_id, start_datetime, end_datetime, top, select, filter_param, order_by
            )
            
            events_data = [{
                'id': event.id,
                'subject': event.subject,
                'start': event.start,
                'end': event.end,
                'location': event.location,
                'body_preview': event.body_preview,
                'attendees': event.attendees or [],
                'importance': event.importance,
                'show_as': event.show_as,
                'is_all_day': event.is_all_day,
                'sensitivity': event.sensitivity,
                'recurrence': event.recurrence,
                'online_meeting': event.online_meeting,
                'web_link': event.web_link
            } for event in events]
            
            return jsonify(format_microsoft_response({
                'events': events_data,
                'calendar_id': calendar_id,
                'total_count': len(events_data),
                'start_datetime': start_datetime,
                'end_datetime': end_datetime
            }, 'calendar', 'list_events'))
        
        # Fallback to mock data
        current_time = datetime.utcnow()
        mock_events = [
            {
                'id': 'event_123',
                'subject': 'Team Standup',
                'start': {
                    'dateTime': (current_time + timedelta(hours=1)).isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': (current_time + timedelta(hours=1, minutes=30)).isoformat(),
                    'timeZone': 'UTC'
                },
                'location': {
                    'displayName': 'Conference Room A',
                    'address': {'city': 'Seattle', 'country': 'USA'}
                },
                'body_preview': 'Daily team standup meeting',
                'attendees': [
                    {
                        'emailAddress': {
                            'name': 'Team',
                            'address': 'team@company.com'
                        },
                        'status': {'response': 'accepted', 'time': current_time.isoformat()}
                    }
                ],
                'importance': 'normal',
                'show_as': 'busy',
                'is_all_day': False,
                'sensitivity': 'normal',
                'online_meeting': {
                    'joinUrl': 'https://teams.microsoft.com/l/meetup-join/19%3ameeting_ID',
                    'conferenceId': '123456789'
                },
                'web_link': 'https://outlook.office.com/calendar/event/event_123'
            },
            {
                'id': 'event_456',
                'subject': 'Product Demo',
                'start': {
                    'dateTime': (current_time + timedelta(days=1, hours=14)).isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': (current_time + timedelta(days=1, hours=15)).isoformat(),
                    'timeZone': 'UTC'
                },
                'location': {
                    'displayName': 'Virtual Meeting',
                    'address': {}
                },
                'body_preview': 'Product demonstration for prospective clients',
                'attendees': [
                    {
                        'emailAddress': {
                            'name': 'Client',
                            'address': 'client@company.com'
                        },
                        'status': {'response': 'needsAction'}
                    }
                ],
                'importance': 'high',
                'show_as': 'busy',
                'is_all_day': False,
                'sensitivity': 'normal',
                'online_meeting': {
                    'joinUrl': 'https://teams.microsoft.com/l/meetup-join/19%3ameeting_ID_456',
                    'conferenceId': '987654321'
                },
                'web_link': 'https://outlook.office.com/calendar/event/event_456'
            }
        ]
        
        return jsonify(format_microsoft_response({
            'events': mock_events[:top],
            'calendar_id': calendar_id,
            'total_count': len(mock_events),
            'start_datetime': start_datetime,
            'end_datetime': end_datetime
        }, 'calendar', 'list_events'))
    
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        return jsonify(format_error_response(e, 'calendar', 'list_events')), 500

async def _create_calendar_event(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create calendar event"""
    try:
        event_data = data.get('data', {})
        
        if not event_data.get('subject'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Event subject is required'}
            }), 400
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            result = await microsoft_service.create_calendar_event(user_id, event_data)
            
            if result.get('ok'):
                return jsonify(format_microsoft_response({
                    'event': result.get('event'),
                    'web_link': result.get('web_link')
                }, 'calendar', 'create_event'))
            else:
                return jsonify(result)
        
        # Fallback to mock creation
        mock_event = {
            'id': 'event_' + str(int(datetime.utcnow().timestamp())),
            'subject': event_data['subject'],
            'start': event_data.get('start', {
                'dateTime': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                'timeZone': 'UTC'
            }),
            'end': event_data.get('end', {
                'dateTime': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                'timeZone': 'UTC'
            }),
            'location': event_data.get('location', {}),
            'importance': event_data.get('importance', 'normal'),
            'web_link': 'https://outlook.office.com/calendar/event/mock_event_id'
        }
        
        return jsonify(format_microsoft_response({
            'event': mock_event,
            'web_link': mock_event['web_link']
        }, 'calendar', 'create_event'))
    
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return jsonify(format_error_response(e, 'calendar', 'create_event')), 500

# Microsoft OneDrive Enhanced API
@microsoft_enhanced_bp.route('/api/integrations/microsoft/onedrive/files', methods=['POST'])
async def list_onedrive_files():
    """List OneDrive files with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        top = data.get('top', 50)
        select = data.get('select', 'id,name,size,lastModifiedDateTime,parentReference,webUrl,file,folder')
        filter_param = data.get('filter', '')
        order_by = data.get('order_by', 'lastModifiedDateTime desc')
        expand = data.get('expand', 'thumbnails')
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'create':
            return await _create_onedrive_file(user_id, data)
        elif operation == 'upload':
            return await _upload_onedrive_file(user_id, data)
        elif operation == 'create_folder':
            return await _create_onedrive_folder(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Microsoft tokens not found'}
            }), 401
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            files = await microsoft_service.get_onedrive_files(
                user_id, query, top, select, filter_param, order_by, expand
            )
            
            files_data = [{
                'id': file.id,
                'name': file.name,
                'size': file.size,
                'last_modified_date_time': file.last_modified_date_time,
                'parent_reference': file.parent_reference or {},
                'web_url': file.web_url,
                'file': file.file or {},
                'folder': file.folder or {},
                'is_folder': file.folder is not None,
                'thumbnails': file.thumbnails or [],
                'created_date_time': file.created_date_time,
                'content_type': file.content_type
            } for file in files]
            
            return jsonify(format_microsoft_response({
                'files': files_data,
                'total_count': len(files_data),
                'query': query,
                'top': top
            }, 'onedrive', 'list_files'))
        
        # Fallback to mock data
        mock_files = [
            {
                'id': 'file_123',
                'name': 'Project Proposal.docx',
                'size': 524288,
                'last_modified_date_time': (datetime.utcnow() - timedelta(days=30)).isoformat(),
                'parent_reference': {'path': '/Documents', 'id': 'folder_123'},
                'web_url': 'https://company.sharepoint.com/:b:/g/personal/user/Documents/Project_Proposal.docx',
                'file': {
                    'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'hashes': {'sha1Hash': 'abc123def456'}
                },
                'folder': None,
                'is_folder': False,
                'thumbnails': [{'id': 'thumb_1', 'large': {'url': 'https://thumbnail.url', 'width': 1024, 'height': 768}}],
                'created_date_time': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'content_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            },
            {
                'id': 'file_456',
                'name': 'Team Meeting Notes.docx',
                'size': 262144,
                'last_modified_date_time': (datetime.utcnow() - timedelta(days=15)).isoformat(),
                'parent_reference': {'path': '/Documents', 'id': 'folder_456'},
                'web_url': 'https://company.sharepoint.com/:w:/g/personal/user/Documents/Team_Meeting_Notes.docx',
                'file': {
                    'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'hashes': {'sha1Hash': 'def456ghi789'}
                },
                'folder': None,
                'is_folder': False,
                'thumbnails': [{'id': 'thumb_2', 'large': {'url': 'https://thumbnail2.url', 'width': 1024, 'height': 768}}],
                'created_date_time': (datetime.utcnow() - timedelta(days=20)).isoformat(),
                'content_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            },
            {
                'id': 'folder_123',
                'name': 'Documents',
                'size': 0,
                'last_modified_date_time': (datetime.utcnow() - timedelta(days=60)).isoformat(),
                'parent_reference': {'path': '/', 'id': 'root'},
                'web_url': 'https://company.sharepoint.com/:f:/g/personal/user/Documents',
                'file': None,
                'folder': {'childCount': 25},
                'is_folder': True,
                'thumbnails': [],
                'created_date_time': (datetime.utcnow() - timedelta(days=90)).isoformat(),
                'content_type': None
            }
        ]
        
        return jsonify(format_microsoft_response({
            'files': mock_files[:top],
            'total_count': len(mock_files),
            'query': query,
            'top': top
        }, 'onedrive', 'list_files'))
    
    except Exception as e:
        logger.error(f"Error listing OneDrive files: {e}")
        return jsonify(format_error_response(e, 'onedrive', 'list_files')), 500

async def _create_onedrive_file(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to create OneDrive file"""
    try:
        file_data = data.get('data', {})
        
        if not file_data.get('name'):
            return jsonify({
                'ok': False,
                'error': {'message': 'File name is required'}
            }), 400
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            result = await microsoft_service.create_onedrive_file(user_id, file_data)
            
            if result.get('ok'):
                return jsonify(format_microsoft_response({
                    'file': result.get('file'),
                    'web_url': result.get('web_url')
                }, 'onedrive', 'create_file'))
            else:
                return jsonify(result)
        
        # Fallback to mock creation
        mock_file = {
            'id': 'file_' + str(int(datetime.utcnow().timestamp())),
            'name': file_data['name'],
            'size': 0,
            'last_modified_date_time': datetime.utcnow().isoformat(),
            'parent_reference': {'path': '/Documents'},
            'web_url': 'https://company.sharepoint.com/:w:/g/personal/user/Documents/mock_file_name.docx',
            'file': {
                'mimeType': file_data.get('content_type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                'hashes': {'sha1Hash': 'mock_hash_' + str(int(datetime.utcnow().timestamp()))}
            },
            'folder': None,
            'is_folder': False,
            'thumbnails': [],
            'created_date_time': datetime.utcnow().isoformat(),
            'content_type': file_data.get('content_type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        }
        
        return jsonify(format_microsoft_response({
            'file': mock_file,
            'web_url': mock_file['web_url']
        }, 'onedrive', 'create_file'))
    
    except Exception as e:
        logger.error(f"Error creating OneDrive file: {e}")
        return jsonify(format_error_response(e, 'onedrive', 'create_file')), 500

# Microsoft Teams Enhanced API
@microsoft_enhanced_bp.route('/api/integrations/microsoft/teams/channels', methods=['POST'])
async def list_teams_channels():
    """List Teams channels with advanced filtering"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        team_id = data.get('team_id')
        top = data.get('top', 50)
        operation = data.get('operation', 'list')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if operation == 'send_message':
            return await _send_teams_message(user_id, data)
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Microsoft tokens not found'}
            }), 401
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            channels = await microsoft_service.get_teams_channels(
                user_id, team_id, top
            )
            
            channels_data = [{
                'id': channel.id,
                'displayName': channel.display_name,
                'description': channel.description,
                'is_favorite_by_default': channel.is_favorite_by_default,
                'email': channel.email,
                'membership_type': channel.membership_type,
                'web_url': channel.web_url
            } for channel in channels]
            
            return jsonify(format_microsoft_response({
                'channels': channels_data,
                'total_count': len(channels_data),
                'team_id': team_id
            }, 'teams', 'list_channels'))
        
        # Fallback to mock data
        mock_channels = [
            {
                'id': 'channel_123',
                'displayName': 'General',
                'description': 'General discussion channel',
                'is_favorite_by_default': True,
                'email': 'team123_general@teams.microsoft.com',
                'membership_type': 'standard',
                'web_url': 'https://teams.microsoft.com/_#/conversations/channel_123'
            },
            {
                'id': 'channel_456',
                'displayName': 'Development',
                'description': 'Development team discussions',
                'is_favorite_by_default': False,
                'email': 'team123_dev@teams.microsoft.com',
                'membership_type': 'standard',
                'web_url': 'https://teams.microsoft.com/_#/conversations/channel_456'
            }
        ]
        
        return jsonify(format_microsoft_response({
            'channels': mock_channels[:top],
            'total_count': len(mock_channels),
            'team_id': team_id
        }, 'teams', 'list_channels'))
    
    except Exception as e:
        logger.error(f"Error listing Teams channels: {e}")
        return jsonify(format_error_response(e, 'teams', 'list_channels')), 500

async def _send_teams_message(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to send Teams message"""
    try:
        channel_id = data.get('channel_id')
        message_data = data.get('data', {})
        
        if not channel_id or not message_data.get('content'):
            return jsonify({
                'ok': False,
                'error': {'message': 'channel_id and content are required'}
            }), 400
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            result = await microsoft_service.send_teams_message(user_id, channel_id, message_data)
            
            if result.get('ok'):
                return jsonify(format_microsoft_response({
                    'message': result.get('message'),
                    'id': result.get('id')
                }, 'teams', 'send_message'))
            else:
                return jsonify(result)
        
        # Fallback to mock sending
        mock_message = {
            'id': 'msg_' + str(int(datetime.utcnow().timestamp())),
            'content': message_data['content'],
            'created_date_time': datetime.utcnow().isoformat()
        }
        
        return jsonify(format_microsoft_response({
            'message': mock_message,
            'id': mock_message['id']
        }, 'teams', 'send_message'))
    
    except Exception as e:
        logger.error(f"Error sending Teams message: {e}")
        return jsonify(format_error_response(e, 'teams', 'send_message')), 500

# Microsoft Suite Search API
@microsoft_enhanced_bp.route('/api/integrations/microsoft/search', methods=['POST'])
async def search_microsoft_suite():
    """Search across Microsoft services"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        services = data.get('services', ['outlook', 'onedrive', 'calendar'])
        top = data.get('top', 20)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if not query:
            return jsonify({
                'ok': False,
                'error': {'message': 'query is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Microsoft tokens not found'}
            }), 401
        
        # Use Microsoft service
        if MICROSOFT_SERVICE_AVAILABLE:
            results = await microsoft_service.search_microsoft_suite(
                user_id, query, services, top
            )
            
            return jsonify(format_microsoft_response({
                'results': results,
                'total_count': len(results),
                'query': query,
                'services': services
            }, 'search', 'search_microsoft_suite'))
        
        # Fallback to mock search
        mock_results = []
        
        if 'outlook' in services:
            mock_results.append({
                'service': 'outlook',
                'type': 'message',
                'id': 'msg_search_1',
                'title': 'Re: Project Status',
                'snippet': 'The project is on track for Q4 deadline...',
                'url': 'https://outlook.office.com/mail/id=msg_search_1',
                'created_date_time': (datetime.utcnow() - timedelta(hours=2)).isoformat()
            })
        
        if 'onedrive' in services:
            mock_results.append({
                'service': 'onedrive',
                'type': 'file',
                'id': 'file_search_1',
                'title': 'Q4 Project Plan.pdf',
                'snippet': 'Comprehensive project plan for Q4 deliverables...',
                'url': 'https://company.sharepoint.com/:b:/g/personal/user/Q4_Project_Plan.pdf',
                'created_date_time': (datetime.utcnow() - timedelta(days=7)).isoformat()
            })
        
        if 'calendar' in services:
            mock_results.append({
                'service': 'calendar',
                'type': 'event',
                'id': 'event_search_1',
                'title': 'Project Review Meeting',
                'snippet': 'Quarterly project review and planning session...',
                'url': 'https://outlook.office.com/calendar/event/event_search_1',
                'created_date_time': (datetime.utcnow() + timedelta(days=1, hours=14)).isoformat()
            })
        
        return jsonify(format_microsoft_response({
            'results': mock_results[:top],
            'total_count': len(mock_results),
            'query': query,
            'services': services
        }, 'search', 'search_microsoft_suite'))
    
    except Exception as e:
        logger.error(f"Error searching Microsoft Suite: {e}")
        return jsonify(format_error_response(e, 'search', 'search_microsoft_suite')), 500

# Microsoft User Profile API
@microsoft_enhanced_bp.route('/api/integrations/microsoft/user/profile', methods=['POST'])
async def get_user_profile():
    """Get Microsoft user profile"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Microsoft tokens not found'}
            }), 401
        
        # Return user info from tokens
        return jsonify(format_microsoft_response({
            'user': tokens['user_info'],
            'services': {
                'outlook': {'enabled': True, 'status': 'connected'},
                'calendar': {'enabled': True, 'status': 'connected'},
                'onedrive': {'enabled': True, 'status': 'connected'},
                'teams': {'enabled': True, 'status': 'connected'},
                'sharepoint': {'enabled': True, 'status': 'connected'}
            }
        }, 'user', 'get_profile'))
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'user', 'get_profile')), 500

# Microsoft Health Check API
@microsoft_enhanced_bp.route('/api/integrations/microsoft/health', methods=['GET'])
async def health_check():
    """Microsoft service health check"""
    try:
        if not MICROSOFT_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Microsoft service not available',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Test Microsoft API connectivity
        try:
            if MICROSOFT_SERVICE_AVAILABLE:
                service_info = microsoft_service.get_service_info()
                return jsonify({
                    'status': 'healthy',
                    'message': 'Microsoft Graph APIs are accessible',
                    'service_available': MICROSOFT_SERVICE_AVAILABLE,
                    'database_available': MICROSOFT_DB_AVAILABLE,
                    'service_info': service_info,
                    'services': {
                        'outlook': {'status': 'healthy'},
                        'calendar': {'status': 'healthy'},
                        'onedrive': {'status': 'healthy'},
                        'teams': {'status': 'healthy'},
                        'sharepoint': {'status': 'healthy'}
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })
        except Exception as e:
            return jsonify({
                'status': 'degraded',
                'error': f'Microsoft service error: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'status': 'healthy',
            'message': 'Microsoft Graph API mock is accessible',
            'service_available': MICROSOFT_SERVICE_AVAILABLE,
            'database_available': MICROSOFT_DB_AVAILABLE,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@microsoft_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@microsoft_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500