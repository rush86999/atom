"""
Outlook service handler for email and calendar operations
Follows the same pattern as other service handlers
"""

import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from auth_handler_outlook_new import OutlookOAuthHandler

logger = logging.getLogger(__name__)

class OutlookServiceHandler:
    """Handler for Outlook email and calendar operations"""
    
    def __init__(self):
        self.oauth_handler = OutlookOAuthHandler()
        self.api_base_url = 'https://graph.microsoft.com/v1.0'
        
    async def get_user_emails(self, db_pool, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get user's Outlook emails"""
        try:
            # Get valid access token
            from db_oauth_outlook import refresh_outlook_tokens_if_needed
            tokens = await refresh_outlook_tokens_if_needed(db_pool, user_id)
            
            if not tokens:
                return {
                    'success': False,
                    'error': 'No valid Outlook access token available',
                    'service': 'outlook',
                    'user_id': user_id
                }
            
            # Get emails
            result = self.oauth_handler.get_emails(tokens['access_token'], limit)
            
            if result.get('success'):
                result['user_id'] = user_id
                logger.info(f"Retrieved {result.get('total', 0)} emails for user {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Outlook emails for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Outlook email retrieval error: {str(e)}',
                'service': 'outlook',
                'user_id': user_id
            }
    
    async def send_email(self, db_pool, user_id: str, to: List[str], subject: str, 
                        body: str, cc: List[str] = None, bcc: List[str] = None) -> Dict[str, Any]:
        """Send an email using Outlook"""
        try:
            # Get valid access token
            from db_oauth_outlook import refresh_outlook_tokens_if_needed
            tokens = await refresh_outlook_tokens_if_needed(db_pool, user_id)
            
            if not tokens:
                return {
                    'success': False,
                    'error': 'No valid Outlook access token available',
                    'service': 'outlook',
                    'user_id': user_id
                }
            
            # Send email
            result = self.oauth_handler.send_email(tokens['access_token'], to, subject, body, cc, bcc)
            
            if result.get('success'):
                result['user_id'] = user_id
                logger.info(f"Sent email to {len(to)} recipients for user {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending Outlook email for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Outlook email send error: {str(e)}',
                'service': 'outlook',
                'user_id': user_id
            }
    
    async def get_calendar_events(self, db_pool, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get user's Outlook calendar events"""
        try:
            # Get valid access token
            from db_oauth_outlook import refresh_outlook_tokens_if_needed
            tokens = await refresh_outlook_tokens_if_needed(db_pool, user_id)
            
            if not tokens:
                return {
                    'success': False,
                    'error': 'No valid Outlook access token available',
                    'service': 'outlook',
                    'user_id': user_id
                }
            
            # Get calendar events
            result = self.oauth_handler.get_calendar_events(tokens['access_token'], limit)
            
            if result.get('success'):
                result['user_id'] = user_id
                logger.info(f"Retrieved {result.get('total', 0)} calendar events for user {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Outlook calendar events for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Outlook calendar events error: {str(e)}',
                'service': 'outlook',
                'user_id': user_id
            }
    
    async def get_user_profile(self, db_pool, user_id: str) -> Dict[str, Any]:
        """Get user's Outlook profile"""
        try:
            # Get valid access token
            from db_oauth_outlook import refresh_outlook_tokens_if_needed
            tokens = await refresh_outlook_tokens_if_needed(db_pool, user_id)
            
            if not tokens:
                return {
                    'success': False,
                    'error': 'No valid Outlook access token available',
                    'service': 'outlook',
                    'user_id': user_id
                }
            
            # Get user profile
            result = self.oauth_handler.get_user_info(tokens['access_token'])
            
            if result.get('success'):
                result['user_id'] = user_id
                logger.info(f"Retrieved Outlook profile for user {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting Outlook profile for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Outlook profile error: {str(e)}',
                'service': 'outlook',
                'user_id': user_id
            }
    
    async def search_emails(self, db_pool, user_id: str, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search Outlook emails by subject or content"""
        try:
            # Get valid access token
            from db_oauth_outlook import refresh_outlook_tokens_if_needed
            tokens = await refresh_outlook_tokens_if_needed(db_pool, user_id)
            
            if not tokens:
                return {
                    'success': False,
                    'error': 'No valid Outlook access token available',
                    'service': 'outlook',
                    'user_id': user_id
                }
            
            # Search emails using Microsoft Graph API
            headers = {
                'Authorization': f'Bearer {tokens["access_token"]}',
                'Content-Type': 'application/json'
            }
            
            # Build search query
            search_params = {
                '$search': f'"subject:{query}" OR "body:{query}"',
                '$top': limit,
                '$orderby': 'receivedDateTime desc'
            }
            
            response = requests.get(
                f'{self.api_base_url}/me/messages',
                headers=headers,
                params=search_params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                emails = data.get('value', [])
                
                return {
                    'success': True,
                    'service': 'outlook',
                    'user_id': user_id,
                    'query': query,
                    'emails': [
                        {
                            'id': email.get('id'),
                            'subject': email.get('subject'),
                            'from': email.get('from', {}).get('emailAddress', {}),
                            'toRecipients': [recipient.get('emailAddress', {}) for recipient in email.get('toRecipients', [])],
                            'body': email.get('body', {}).get('content', ''),
                            'bodyContentType': email.get('body', {}).get('contentType', 'text'),
                            'receivedDateTime': email.get('receivedDateTime'),
                            'isRead': email.get('isRead', False),
                            'importance': email.get('importance', 'normal'),
                            'hasAttachments': email.get('hasAttachments', False),
                            'webLink': email.get('webLink')
                        } for email in emails
                    ],
                    'total': len(emails),
                    'access_granted': True
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to search Outlook emails',
                    'status_code': response.status_code,
                    'response': response.text,
                    'service': 'outlook',
                    'user_id': user_id
                }
                
        except Exception as e:
            logger.error(f"Error searching Outlook emails for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Outlook email search error: {str(e)}',
                'service': 'outlook',
                'user_id': user_id
            }
    
    async def create_calendar_event(self, db_pool, user_id: str, subject: str, 
                                 start_time: str, end_time: str, body: str = None,
                                 location: str = None, attendees: List[str] = None) -> Dict[str, Any]:
        """Create a calendar event in Outlook"""
        try:
            # Get valid access token
            from db_oauth_outlook import refresh_outlook_tokens_if_needed
            tokens = await refresh_outlook_tokens_if_needed(db_pool, user_id)
            
            if not tokens:
                return {
                    'success': False,
                    'error': 'No valid Outlook access token available',
                    'service': 'outlook',
                    'user_id': user_id
                }
            
            # Prepare event data
            headers = {
                'Authorization': f'Bearer {tokens["access_token"]}',
                'Content-Type': 'application/json'
            }
            
            # Prepare attendees
            attendee_list = []
            if attendees:
                for email in attendees:
                    attendee_list.append({
                        'emailAddress': {
                            'address': email,
                            'name': email.split('@')[0].replace('.', ' ').title()
                        },
                        'type': 'required'
                    })
            
            event_data = {
                'subject': subject,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC'
                }
            }
            
            if body:
                event_data['body'] = {
                    'contentType': 'HTML' if '<' in body and '>' in body else 'Text',
                    'content': body
                }
            
            if location:
                event_data['location'] = {
                    'displayName': location
                }
            
            if attendee_list:
                event_data['attendees'] = attendee_list
            
            # Create event
            response = requests.post(
                f'{self.api_base_url}/me/events',
                headers=headers,
                json=event_data,
                timeout=10
            )
            
            if response.status_code == 201:  # Created
                event_data = response.json()
                return {
                    'success': True,
                    'service': 'outlook',
                    'user_id': user_id,
                    'event': {
                        'id': event_data.get('id'),
                        'subject': event_data.get('subject'),
                        'start': event_data.get('start', {}),
                        'end': event_data.get('end', {}),
                        'location': event_data.get('location', {}).get('displayName', ''),
                        'webLink': event_data.get('webLink')
                    },
                    'message': 'Calendar event created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to create Outlook calendar event',
                    'status_code': response.status_code,
                    'response': response.text,
                    'service': 'outlook',
                    'user_id': user_id
                }
                
        except Exception as e:
            logger.error(f"Error creating Outlook calendar event for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Outlook calendar event creation error: {str(e)}',
                'service': 'outlook',
                'user_id': user_id
            }
    
    async def get_unread_emails(self, db_pool, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get unread Outlook emails"""
        try:
            # Get valid access token
            from db_oauth_outlook import refresh_outlook_tokens_if_needed
            tokens = await refresh_outlook_tokens_if_needed(db_pool, user_id)
            
            if not tokens:
                return {
                    'success': False,
                    'error': 'No valid Outlook access token available',
                    'service': 'outlook',
                    'user_id': user_id
                }
            
            # Get unread emails using Microsoft Graph API
            headers = {
                'Authorization': f'Bearer {tokens["access_token"]}',
                'Content-Type': 'application/json'
            }
            
            params = {
                '$filter': "isRead eq false",
                '$top': limit,
                '$orderby': 'receivedDateTime desc'
            }
            
            response = requests.get(
                f'{self.api_base_url}/me/messages',
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                emails = data.get('value', [])
                
                return {
                    'success': True,
                    'service': 'outlook',
                    'user_id': user_id,
                    'emails': [
                        {
                            'id': email.get('id'),
                            'subject': email.get('subject'),
                            'from': email.get('from', {}).get('emailAddress', {}),
                            'toRecipients': [recipient.get('emailAddress', {}) for recipient in email.get('toRecipients', [])],
                            'body': email.get('body', {}).get('content', ''),
                            'bodyContentType': email.get('body', {}).get('contentType', 'text'),
                            'receivedDateTime': email.get('receivedDateTime'),
                            'importance': email.get('importance', 'normal'),
                            'hasAttachments': email.get('hasAttachments', False),
                            'webLink': email.get('webLink')
                        } for email in emails
                    ],
                    'total': len(emails),
                    'access_granted': True
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get unread Outlook emails',
                    'status_code': response.status_code,
                    'response': response.text,
                    'service': 'outlook',
                    'user_id': user_id
                }
                
        except Exception as e:
            logger.error(f"Error getting unread Outlook emails for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Outlook unread emails error: {str(e)}',
                'service': 'outlook',
                'user_id': user_id
            }

# Global service handler instance
outlook_service_handler = OutlookServiceHandler()