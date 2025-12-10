"""
Gmail Service for ATOM Platform
Provides comprehensive Gmail integration functionality
"""

import json
import logging
import os
import base64
import re
import asyncio
import aiohttp
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.token_storage import token_storage
from core.oauth_handler import GOOGLE_OAUTH_CONFIG

logger = logging.getLogger(__name__)

class GmailService:
    """Gmail API integration service with async support"""

    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')
        self.token_path = token_path or os.getenv('GMAIL_TOKEN_PATH', 'token.json')
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
        self.service = None
        self._session = None
        self._authenticate()

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
        return self._session

    async def close_session(self):
        """Close aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()
    
    def _authenticate(self):
        """Authenticate with Gmail API"""
        try:
            creds = None
            
            # 1. Try to load from secure token storage first
            stored_token = token_storage.get_token("google")
            if stored_token:
                logger.info("Found Google token in secure storage")
                creds = Credentials(
                    token=stored_token.get("access_token"),
                    refresh_token=stored_token.get("refresh_token"),
                    token_uri=GOOGLE_OAUTH_CONFIG.token_url,
                    client_id=GOOGLE_OAUTH_CONFIG.client_id,
                    client_secret=GOOGLE_OAUTH_CONFIG.client_secret,
                    scopes=self.scopes
                )
            
            # 2. Fallback to file-based token (legacy)
            elif os.path.exists(self.token_path):
                logger.info(f"Loading Google token from file: {self.token_path}")
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired Google token")
                    creds.refresh(Request())
                    
                    # Update storage if we used it
                    if stored_token:
                        new_token_data = {
                            "access_token": creds.token,
                            "refresh_token": creds.refresh_token,
                            "token_uri": creds.token_uri,
                            "client_id": creds.client_id,
                            "client_secret": creds.client_secret,
                            "scopes": creds.scopes
                        }
                        token_storage.save_token("google", new_token_data)
                else:
                    if not os.path.exists(self.credentials_path):
                        # If we have OAUTH config, we might not need credentials file
                        if not GOOGLE_OAUTH_CONFIG.is_configured():
                            raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
                    
                    if os.path.exists(self.credentials_path):
                        flow = Flow.from_client_secrets_file(self.credentials_path, self.scopes)
                        flow.redirect_uri = 'http://localhost:8080/oauth/gmail/callback'
                        auth_url, _ = flow.authorization_url(prompt='consent')
                        raise Exception(f"Authorization required. Visit: {auth_url}")
                    else:
                         if GOOGLE_OAUTH_CONFIG.is_configured():
                             logger.info("Google OAuth configured but no token found. Waiting for authentication.")
                         else:
                             raise Exception("Google OAuth not configured and no credentials found.")
                
                # Save to file if we are using file mode
                if not stored_token and self.token_path and creds:
                     with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
            
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail authentication successful")
            
        except Exception as e:
            logger.warning(f"Gmail authentication failed during initialization: {e}")
            self.service = None
            # Do not raise exception to allow app startup without Gmail credentials
            # Operations requiring Gmail will fail later if not authenticated
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Gmail API connection"""
        try:
            if not self.service:
                return {
                    "status": "error",
                    "message": "Gmail service not initialized",
                    "authenticated": False
                }
            
            # Try to get user profile
            result = self.service.users().getProfile(userId='me').execute()
            return {
                "status": "success",
                "message": "Gmail connection successful",
                "email": result['emailAddress'],
                "messages_total": result['messagesTotal'],
                "threads_total": result['threadsTotal'],
                "history_id": result['historyId'],
                "authenticated": True
            }
        except Exception as e:
            logger.error(f"Gmail connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def get_messages(self, query: str = "", max_results: int = 50, include_spam_trash: bool = False) -> List[Dict[str, Any]]:
        """Get messages from Gmail"""
        try:
            messages = []
            page_token = None
            
            while len(messages) < max_results:
                try:
                    result = self.service.users().messages().list(
                        userId='me',
                        q=query,
                        maxResults=min(max_results - len(messages), 50),
                        pageToken=page_token,
                        includeSpamTrash=include_spam_trash
                    ).execute()
                    
                    messages.extend(result.get('messages', []))
                    page_token = result.get('nextPageToken')
                    
                    if not page_token:
                        break
                        
                except HttpError as e:
                    logger.error(f"Error fetching messages: {e}")
                    break
            
            # Fetch full message details for each message
            full_messages = []
            for msg in messages[:max_results]:
                full_msg = self.get_message(msg['id'])
                if full_msg:
                    full_messages.append(full_msg)
            
            return full_messages
            
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message by ID"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Parse message
            return self._parse_message(message)
            
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None
    
    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gmail message into readable format"""
        try:
            headers = message['payload'].get('headers', [])
            subject = ""
            sender = ""
            date = ""
            
            for header in headers:
                if header['name'].lower() == 'subject':
                    subject = header['value']
                elif header['name'].lower() == 'from':
                    sender = header['value']
                elif header['name'].lower() == 'date':
                    date = header['value']
            
            # Extract body
            body = self._extract_body(message['payload'])
            
            return {
                'id': message['id'],
                'threadId': message['threadId'],
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body,
                'snippet': message.get('snippet', ''),
                'labelIds': message.get('labelIds', []),
                'historyId': message.get('historyId'),
                'internalDate': message.get('internalDate')
            }
            
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return {}
    
    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from payload"""
        try:
            if 'body' in payload and 'data' in payload['body']:
                return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    elif 'parts' in part:
                        body = self._extract_body(part)
                        if body:
                            return body
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting body: {e}")
            return ""
    
    def send_message(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "", thread_id: str = None) -> Optional[Dict[str, Any]]:
        """Send an email"""
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            
            if cc:
                message['cc'] = cc
            if bcc:
                message['bcc'] = bcc
            
            message.attach(MIMEText(body, 'plain'))
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            message_data = {
                'raw': raw,
                'threadId': thread_id
            }
            
            if thread_id:
                result = self.service.users().messages().send(
                    userId='me',
                    body=message_data
                ).execute()
            else:
                result = self.service.users().messages().send(
                    userId='me',
                    body={'raw': raw}
                ).execute()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    def draft_message(self, to: str, subject: str, body: str, thread_id: str = None) -> Optional[Dict[str, Any]]:
        """Create a draft email"""
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            message.attach(MIMEText(body, 'plain'))
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            message_data = {
                'message': {
                    'raw': raw,
                    'threadId': thread_id
                }
            }
            
            result = self.service.users().drafts().create(
                userId='me',
                body=message_data
            ).execute()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create draft: {e}")
            return None
    
    def search_messages(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for messages"""
        return self.get_messages(query=query, max_results=max_results)
    
    def get_threads(self, query: str = "", max_results: int = 20) -> List[Dict[str, Any]]:
        """Get email threads"""
        try:
            threads = []
            page_token = None
            
            while len(threads) < max_results:
                try:
                    result = self.service.users().threads().list(
                        userId='me',
                        q=query,
                        maxResults=min(max_results - len(threads), 50),
                        pageToken=page_token
                    ).execute()
                    
                    threads.extend(result.get('threads', []))
                    page_token = result.get('nextPageToken')
                    
                    if not page_token:
                        break
                        
                except HttpError as e:
                    logger.error(f"Error fetching threads: {e}")
                    break
            
            # Fetch full thread details
            full_threads = []
            for thread in threads[:max_results]:
                try:
                    full_thread = self.service.users().threads().get(
                        userId='me',
                        id=thread['id'],
                        format='full'
                    ).execute()
                    full_threads.append(full_thread)
                except Exception as e:
                    logger.error(f"Error fetching thread {thread['id']}: {e}")
            
            return full_threads
            
        except Exception as e:
            logger.error(f"Failed to get threads: {e}")
            return []
    
    def modify_message(self, message_id: str, add_labels: List[str] = None, remove_labels: List[str] = None) -> bool:
        """Modify message labels"""
        try:
            body = {}
            if add_labels:
                body['addLabelIds'] = add_labels
            if remove_labels:
                body['removeLabelIds'] = remove_labels
            
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body=body
            ).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to modify message {message_id}: {e}")
            return False
    
    def delete_message(self, message_id: str) -> bool:
        """Delete a message"""
        try:
            self.service.users().messages().delete(
                userId='me',
                id=message_id
            ).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
            return False
    
    def get_labels(self) -> List[Dict[str, Any]]:
        """Get all labels"""
        try:
            result = self.service.users().labels().list(userId='me').execute()
            return result.get('labels', [])
        except Exception as e:
            logger.error(f"Failed to get labels: {e}")
            return []
    
    def create_label(self, name: str, color: Dict[str, str] = None) -> Optional[Dict[str, Any]]:
        """Create a new label"""
        try:
            label_data = {
                'name': name,
                'messageListVisibility': 'show',
                'labelListVisibility': 'labelShow'
            }
            
            if color:
                label_data['color'] = color
            
            result = self.service.users().labels().create(
                userId='me',
                body=label_data
            ).execute()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create label {name}: {e}")
            return None

    # Async methods for enhanced performance
    async def async_get_messages(self, query: str = "", max_results: int = 50, include_spam_trash: bool = False) -> List[Dict[str, Any]]:
        """Async version of get_messages"""
        session = await self.get_session()

        try:
            stored_token = token_storage.get_token("google")
            if not stored_token:
                logger.error("No Google token found for async requests")
                return []

            headers = {
                'Authorization': f"Bearer {stored_token['access_token']}",
                'Content-Type': 'application/json'
            }

            # Build Gmail API URL
            url = f"https://www.googleapis.com/gmail/v1/users/me/messages"
            params = {
                'q': query,
                'maxResults': max_results,
                'includeSpamTrash': str(include_spam_trash).lower()
            }

            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    messages = data.get('messages', [])

                    # Fetch full message details
                    full_messages = []
                    for message in messages[:min(max_results, 10)]:  # Limit concurrent requests
                        message_url = f"https://www.googleapis.com/gmail/v1/users/me/messages/{message['id']}"
                        async with session.get(message_url, headers=headers) as msg_response:
                            if msg_response.status == 200:
                                msg_data = await msg_response.json()
                                full_messages.append(self._parse_message(msg_data))

                    return full_messages
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch messages async: {response.status} - {error_text}")
                    return []

        except Exception as e:
            logger.error(f"Async get_messages failed: {e}")
            return []

    async def async_send_message(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "", thread_id: str = None) -> Optional[Dict[str, Any]]:
        """Async version of send_message"""
        session = await self.get_session()

        try:
            stored_token = token_storage.get_token("google")
            if not stored_token:
                logger.error("No Google token found for async requests")
                return None

            headers = {
                'Authorization': f"Bearer {stored_token['access_token']}",
                'Content-Type': 'application/json'
            }

            # Create email message
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            if cc:
                message['cc'] = cc
            if bcc:
                message['bcc'] = bcc
            if thread_id:
                message['References'] = thread_id
                message['In-Reply-To'] = thread_id

            message.attach(MIMEText(body, 'plain'))

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            url = f"https://www.googleapis.com/gmail/v1/users/me/messages/send"
            data = {
                'raw': raw_message,
                'threadId': thread_id
            }

            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message async: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Async send_message failed: {e}")
            return None

    async def async_search_messages(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Async version of search_messages"""
        return await self.async_get_messages(query, max_results)

    async def async_health_check(self) -> Dict[str, Any]:
        """Async health check"""
        try:
            stored_token = token_storage.get_token("google")
            if not stored_token:
                return {
                    "status": "unhealthy",
                    "error": "No Google token found",
                    "service": "gmail_async",
                    "timestamp": datetime.now().isoformat()
                }

            session = await self.get_session()
            headers = {
                'Authorization': f"Bearer {stored_token['access_token']}",
                'Content-Type': 'application/json'
            }

            url = f"https://www.googleapis.com/gmail/v1/users/me/profile"

            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    profile = await response.json()
                    return {
                        "status": "healthy",
                        "service": "gmail_async",
                        "user_email": profile.get("emailAddress"),
                        "history_id": profile.get("historyId"),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"API call failed: {response.status}",
                        "service": "gmail_async",
                        "timestamp": datetime.now().isoformat()
                    }

        except Exception as e:
            logger.error(f"Async health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "service": "gmail_async",
                "timestamp": datetime.now().isoformat()
            }

# Singleton instance for global access
gmail_service = GmailService()

def get_gmail_service() -> GmailService:
    """Get Gmail service instance"""
    return gmail_service