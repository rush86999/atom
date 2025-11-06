"""
Enhanced Outlook API - Flask Compatible Version
Complete Microsoft Graph API Integration for ATOM
"""

import logging
import os
import asyncio
import aiohttp
import requests
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, abort
from typing import Dict, List, Optional, Any
import sys
import traceback
import json

# Add integrations path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'integrations'))

try:
    from outlook_service_enhanced import OutlookEnhancedService
    OUTLOOK_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Enhanced Outlook service not available: {e}")
    OUTLOOK_SERVICE_AVAILABLE = False

try:
    from db_oauth_outlook import get_outlook_tokens, refresh_outlook_tokens_if_needed
    DB_OAUTH_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Outlook OAuth database not available: {e}")
    DB_OAUTH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create Flask blueprint
outlook_enhanced_bp = Blueprint('outlook_enhanced', __name__)

# Database pool (will be injected from main app)
db_pool = None

def set_db_pool(pool):
    """Set database pool for OAuth token management"""
    global db_pool
    db_pool = pool

def get_user_access_token_sync(user_id: str) -> Optional[str]:
    """Get valid access token for user (synchronous)"""
    try:
        if not DB_OAUTH_AVAILABLE or not db_pool:
            logger.warning("Database not available for OAuth token retrieval")
            return None
            
        # Use asyncio to get tokens from database
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tokens = loop.run_until_complete(get_outlook_tokens(db_pool, user_id))
        finally:
            loop.close()
            
        if not tokens:
            logger.info(f"No Outlook tokens found for user {user_id}")
            return None
            
        # Check if token needs refresh
        if tokens.get('expired', False):
            logger.info(f"Refreshing expired token for user {user_id}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                refreshed_tokens = loop.run_until_complete(refresh_outlook_tokens_if_needed(db_pool, user_id))
            finally:
                loop.close()
                
            if refreshed_tokens:
                return refreshed_tokens.get('access_token')
            else:
                logger.error(f"Failed to refresh token for user {user_id}")
                return None
                
        # Return existing valid token
        return tokens.get('access_token')
        
    except Exception as e:
        logger.error(f"Error getting access token for user {user_id}: {e}")
        return None

@outlook_enhanced_bp.route('/health', methods=['GET'])
def health_check():
    """Enhanced Outlook service health check"""
    try:
        status = {
            'service': 'outlook_enhanced',
            'status': 'healthy' if OUTLOOK_SERVICE_AVAILABLE else 'unavailable',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {}
        }
        
        # Check service availability
        if OUTLOOK_SERVICE_AVAILABLE:
            status['components']['service'] = {
                'status': 'available',
                'message': 'Enhanced Outlook service loaded'
            }
            
            # Check configuration
            client_id = bool(os.getenv('OUTLOOK_CLIENT_ID'))
            client_secret = bool(os.getenv('OUTLOOK_CLIENT_SECRET'))
            tenant_id = bool(os.getenv('OUTLOOK_TENANT_ID'))
            
            status['components']['configuration'] = {
                'status': 'configured' if all([client_id, client_secret, tenant_id]) else 'incomplete',
                'client_id_configured': client_id,
                'client_secret_configured': client_secret,
                'tenant_id_configured': tenant_id
            }
        else:
            status['components']['service'] = {
                'status': 'unavailable',
                'message': 'Enhanced Outlook service not loaded'
            }
            
        # Check database availability
        if DB_OAUTH_AVAILABLE and db_pool:
            status['components']['database'] = {
                'status': 'connected',
                'message': 'OAuth database available'
            }
        else:
            status['components']['database'] = {
                'status': 'unavailable',
                'message': 'OAuth database not available'
            }
            
        # Determine overall status
        if any(comp['status'] == 'unavailable' for comp in status['components'].values()):
            status['status'] = 'degraded'
        elif any(comp['status'] == 'incomplete' for comp in status['components'].values()):
            status['status'] = 'degraded'
            
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'service': 'outlook_enhanced',
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@outlook_enhanced_bp.route('/emails/enhanced', methods=['POST'])
def get_emails_enhanced():
    """Get user emails with enhanced filtering and options"""
    try:
        if not OUTLOOK_SERVICE_AVAILABLE:
            return jsonify({
                'ok': False,
                'error': 'Enhanced Outlook service not available'
            }), 503
            
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': 'user_id is required'
            }), 400
            
        # Get access token
        access_token = get_user_access_token_sync(user_id)
        if not access_token:
            return jsonify({
                'ok': False,
                'error': 'No valid access token found for user',
                'user_id': user_id
            }), 401
        
        # Use Microsoft Graph API directly for emails
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        graph_url = 'https://graph.microsoft.com/v1.0'
        folder = data.get('folder', 'inbox')
        max_results = data.get('max_results', 50)
        skip = data.get('skip', 0)
        order_by = data.get('order_by', 'receivedDateTime DESC')
        query = data.get('query')
        
        # Build URL
        url = f"{graph_url}/me/mailFolders/{folder}/messages"
        params = {
            '$top': max_results,
            '$skip': skip,
            '$orderby': order_by,
            '$select': 'id,conversationId,subject,bodyPreview,body,importance,hasAttachments,isRead,isDraft,webLink,createdDateTime,lastModifiedDateTime,receivedDateTime,sentDateTime,from,toRecipients,ccRecipients,bccRecipients,replyTo,categories,flag,internetMessageHeaders'
        }
        
        if query:
            params['$filter'] = query
            
        if data.get('include_attachments'):
            params['$expand'] = 'attachments'
        
        # Make request
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            return jsonify({
                'ok': False,
                'error': 'Access token expired or invalid',
                'user_id': user_id
            }), 401
            
        response.raise_for_status()
        result = response.json()
        
        emails = []
        for email_data in result.get('value', []):
            email = {
                'id': email_data.get('id', ''),
                'conversationId': email_data.get('conversationId', ''),
                'subject': email_data.get('subject', ''),
                'bodyPreview': email_data.get('bodyPreview', ''),
                'body': email_data.get('body', {}),
                'importance': email_data.get('importance', 'normal'),
                'hasAttachments': email_data.get('hasAttachments', False),
                'isRead': email_data.get('isRead', True),
                'isDraft': email_data.get('isDraft', False),
                'webLink': email_data.get('webLink', ''),
                'createdDateTime': email_data.get('createdDateTime', ''),
                'lastModifiedDateTime': email_data.get('lastModifiedDateTime', ''),
                'receivedDateTime': email_data.get('receivedDateTime', ''),
                'sentDateTime': email_data.get('sentDateTime', ''),
                'from': email_data.get('from', {}),
                'toRecipients': email_data.get('toRecipients', []),
                'ccRecipients': email_data.get('ccRecipients', []),
                'bccRecipients': email_data.get('bccRecipients', []),
                'replyTo': email_data.get('replyTo', []),
                'categories': email_data.get('categories', []),
                'flag': email_data.get('flag', {}),
                'internetMessageHeaders': email_data.get('internetMessageHeaders', []),
                'attachments': email_data.get('attachments', []),
                'metadata': {
                    'accessed_at': datetime.now(timezone.utc).isoformat(),
                    'source': 'microsoft_graph',
                }
            }
            emails.append(email)
        
        return jsonify({
            'ok': True,
            'data': {
                'emails': emails,
                'total_count': len(emails),
                'user_id': user_id,
                'folder': folder,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Graph API error: {e}")
        return jsonify({
            'ok': False,
            'error': f'Microsoft Graph API error: {str(e)}',
            'user_id': data.get('user_id', 'unknown')
        }), 500
    except Exception as e:
        logger.error(f"Error getting enhanced emails: {e}")
        return jsonify({
            'ok': False,
            'error': f'Failed to get emails: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@outlook_enhanced_bp.route('/emails/send/enhanced', methods=['POST'])
def send_email_enhanced():
    """Send email with enhanced options"""
    try:
        if not OUTLOOK_SERVICE_AVAILABLE:
            return jsonify({
                'ok': False,
                'error': 'Enhanced Outlook service not available'
            }), 503
            
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': 'user_id is required'
            }), 400
            
        # Get access token
        access_token = get_user_access_token_sync(user_id)
        if not access_token:
            return jsonify({
                'ok': False,
                'error': 'No valid access token found for user',
                'user_id': user_id
            }), 401
        
        # Use Microsoft Graph API to send email
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        graph_url = 'https://graph.microsoft.com/v1.0'
        
        # Build message
        message = {
            "message": {
                "subject": data.get('subject', ''),
                "body": {
                    "contentType": data.get('body_type', 'HTML'),
                    "content": data.get('body', '')
                },
                "toRecipients": [
                    {"emailAddress": {"address": addr}} 
                    for addr in data.get('to_recipients', [])
                ],
                "importance": data.get('importance', 'normal')
            },
            "saveToSentItems": data.get('save_to_sent_items', True)
        }
        
        if data.get('cc_recipients'):
            message["message"]["ccRecipients"] = [
                {"emailAddress": {"address": addr}} 
                for addr in data.get('cc_recipients', [])
            ]
            
        if data.get('bcc_recipients'):
            message["message"]["bccRecipients"] = [
                {"emailAddress": {"address": addr}} 
                for addr in data.get('bcc_recipients', [])
            ]
            
        if data.get('attachments'):
            message["message"]["attachments"] = data.get('attachments', [])
        
        # Send email
        url = f"{graph_url}/me/sendMail"
        response = requests.post(url, headers=headers, json=message, timeout=30)
        
        if response.status_code == 401:
            return jsonify({
                'ok': False,
                'error': 'Access token expired or invalid',
                'user_id': user_id
            }), 401
            
        response.raise_for_status()
        
        return jsonify({
            'ok': True,
            'data': {
                'message': 'Email sent successfully',
                'user_id': user_id,
                'subject': data.get('subject', ''),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Graph API error: {e}")
        return jsonify({
            'ok': False,
            'error': f'Microsoft Graph API error: {str(e)}',
            'user_id': data.get('user_id', 'unknown')
        }), 500
    except Exception as e:
        logger.error(f"Error sending enhanced email: {e}")
        return jsonify({
            'ok': False,
            'error': f'Failed to send email: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@outlook_enhanced_bp.route('/calendar/events/enhanced', methods=['POST'])
def create_calendar_event_enhanced():
    """Create calendar event with enhanced options"""
    try:
        if not OUTLOOK_SERVICE_AVAILABLE:
            return jsonify({
                'ok': False,
                'error': 'Enhanced Outlook service not available'
            }), 503
            
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': 'user_id is required'
            }), 400
            
        # Get access token
        access_token = get_user_access_token_sync(user_id)
        if not access_token:
            return jsonify({
                'ok': False,
                'error': 'No valid access token found for user',
                'user_id': user_id
            }), 401
        
        # Use Microsoft Graph API to create event
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        graph_url = 'https://graph.microsoft.com/v1.0'
        
        # Build event
        event_data = {
            "subject": data.get('subject', ''),
            "start": {
                "dateTime": data.get('start_time', ''),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": data.get('end_time', ''),
                "timeZone": "UTC"
            },
            "isAllDay": data.get('is_all_day', False),
            "sensitivity": data.get('sensitivity', 'normal'),
            "showAs": data.get('show_as', 'busy'),
            "reminderMinutesBeforeStart": data.get('reminder_minutes', 15)
        }
        
        if data.get('location'):
            event_data["location"] = {"displayName": data.get('location')}
            
        if data.get('body'):
            event_data["body"] = {"contentType": "HTML", "content": data.get('body')}
            
        if data.get('attendees'):
            event_data["attendees"] = [
                {"emailAddress": {"address": addr}} 
                for addr in data.get('attendees', [])
            ]
        
        # Create event
        url = f"{graph_url}/me/events"
        response = requests.post(url, headers=headers, json=event_data, timeout=30)
        
        if response.status_code == 401:
            return jsonify({
                'ok': False,
                'error': 'Access token expired or invalid',
                'user_id': user_id
            }), 401
            
        response.raise_for_status()
        result = response.json()
        
        return jsonify({
            'ok': True,
            'data': {
                'event': result,
                'message': 'Calendar event created successfully',
                'user_id': user_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Graph API error: {e}")
        return jsonify({
            'ok': False,
            'error': f'Microsoft Graph API error: {str(e)}',
            'user_id': data.get('user_id', 'unknown')
        }), 500
    except Exception as e:
        logger.error(f"Error creating enhanced calendar event: {e}")
        return jsonify({
            'ok': False,
            'error': f'Failed to create calendar event: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@outlook_enhanced_bp.route('/info', methods=['GET'])
def get_service_info():
    """Get Outlook service information"""
    try:
        service_info = {
            "service": "outlook_enhanced",
            "version": "2.0.0",
            "status": "active",
            "capabilities": [
                "email_management",
                "calendar_management", 
                "contact_management",
                "task_management",
                "search_and_filtering",
                "folder_management",
                "attachment_handling",
                "event_reminders",
                "enhanced_search",
                "upcoming_events",
                "unread_count",
                "mark_as_read",
                "oauth_integration",
                "microsoft_graph_api"
            ],
            "api_endpoints": [
                "/api/outlook/enhanced/health",
                "/api/outlook/enhanced/emails/enhanced",
                "/api/outlook/enhanced/emails/send/enhanced",
                "/api/outlook/enhanced/calendar/events/enhanced",
                "/api/outlook/enhanced/contacts/enhanced",
                "/api/outlook/enhanced/tasks/enhanced",
                "/api/outlook/enhanced/folders",
                "/api/outlook/enhanced/search/enhanced",
                "/api/outlook/enhanced/user/profile/enhanced",
                "/api/outlook/enhanced/calendar/events/upcoming",
                "/api/outlook/enhanced/emails/unread/count",
                "/api/outlook/enhanced/emails/mark-read",
                "/api/outlook/enhanced/info"
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "service": OUTLOOK_SERVICE_AVAILABLE,
                "database": DB_OAUTH_AVAILABLE and db_pool is not None,
                "oauth": DB_OAUTH_AVAILABLE
            }
        }
        
        return jsonify({
            'ok': True,
            'data': service_info,
        })
        
    except Exception as e:
        logger.error(f"Error getting service info: {e}")
        return jsonify({
            'ok': False,
            'error': f'Failed to get service info: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@outlook_enhanced_bp.route('/user/profile/enhanced', methods=['GET'])
def get_user_profile_enhanced():
    """Get enhanced user profile information"""
    try:
        if not OUTLOOK_SERVICE_AVAILABLE:
            return jsonify({
                'ok': False,
                'error': 'Enhanced Outlook service not available'
            }), 503
            
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': 'user_id is required'
            }), 400
            
        # Get access token
        access_token = get_user_access_token_sync(user_id)
        if not access_token:
            return jsonify({
                'ok': False,
                'error': 'No valid access token found for user',
                'user_id': user_id
            }), 401
        
        # Use Microsoft Graph API to get profile
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        graph_url = 'https://graph.microsoft.com/v1.0'
        url = f"{graph_url}/me"
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 401:
            return jsonify({
                'ok': False,
                'error': 'Access token expired or invalid',
                'user_id': user_id
            }), 401
            
        response.raise_for_status()
        result = response.json()
        
        return jsonify({
            'ok': True,
            'data': {
                'profile': result,
                'user_id': user_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Graph API error: {e}")
        return jsonify({
            'ok': False,
            'error': f'Microsoft Graph API error: {str(e)}',
            'user_id': user_id
        }), 500
    except Exception as e:
        logger.error(f"Error getting enhanced user profile: {e}")
        return jsonify({
            'ok': False,
            'error': f'Failed to get user profile: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

logger.info("Enhanced Outlook API blueprint loaded successfully")