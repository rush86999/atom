"""
Gmail Service for ATOM Platform
Provides comprehensive Gmail integration functionality
"""

import json
import logging
import os
import base64
import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

# Make Google APIs optional for Gmail integration
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    GOOGLE_APIS_AVAILABLE = True
except ImportError:
    GOOGLE_APIS_AVAILABLE = False
    # Create dummy classes to prevent type errors
    class Request: pass
    class Credentials: pass
    class Flow: pass
    class HttpError(Exception): pass
    def build(*args, **kwargs): return None
from core.token_storage import token_storage
from core.oauth_handler import GOOGLE_OAUTH_CONFIG
from core.integration_service import IntegrationService, IntegrationErrorCode

logger = logging.getLogger(__name__)

class GmailService(IntegrationService):
    """Gmail API integration service"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Gmail service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with credentials_path, token_path
        """
        super().__init__(tenant_id, config)
        self.credentials_path = config.get('credentials_path') or os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')
        self.token_path = config.get('token_path') or os.getenv('GMAIL_TOKEN_PATH', 'token.json')
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/calendar.readonly'
        ]
        self.service = None
        # Only auto-authenticate if credentials path exists or tokens are present
        if os.path.exists(self.credentials_path) or os.path.exists(self.token_path):
             self._authenticate()

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Gmail integration capabilities"""
        return {
            "operations": [
                {"id": "send_email", "description": "Send an email"},
                {"id": "list_messages", "description": "List email messages"},
                {"id": "get_message", "description": "Get a specific message"},
                {"id": "search_messages", "description": "Search for messages"},
                {"id": "reply_to_message", "description": "Reply to a message thread"},
                {"id": "draft_message", "description": "Create a draft email"},
                {"id": "modify_message", "description": "Modify message labels"},
                {"id": "delete_message", "description": "Delete a message"},
                {"id": "sync_calendar", "description": "Sync calendar events"},
            ],
            "required_params": ["access_token"],
            "optional_params": ["query", "max_results", "thread_id"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True
        }

    def health_check(self) -> Dict[str, Any]:
        """Check if Gmail service is healthy"""
        try:
            if not self.service:
                return {
                    "healthy": False,
                    "message": "Gmail service not initialized",
                    "last_check": datetime.now(timezone.utc).isoformat()
                }

            result = self.service.users().getProfile(userId='me').execute()
            return {
                "healthy": True,
                "message": "Gmail connection successful",
                "email": result.get('emailAddress'),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Gmail health check failed: {e}")
            return {
                "healthy": False,
                "message": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
    
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
    

    def _get_service_with_token(self, token: Optional[str] = None):
        """Get a Gmail service instance, potentially with a dynamic token"""
        if not token:
            return self.service
            
        try:
            # Create credentials from the access token
            creds = Credentials(
                token=token,
                token_uri=GOOGLE_OAUTH_CONFIG.token_url,
                client_id=GOOGLE_OAUTH_CONFIG.client_id,
                client_secret=GOOGLE_OAUTH_CONFIG.client_secret,
                scopes=self.scopes
            )
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to create service with dynamic token: {e}")
            return None

    def _get_calendar_service(self, token: Optional[str] = None):
        """Get a Google Calendar service instance"""
        try:
            if token:
                creds = Credentials(
                    token=token,
                    token_uri=GOOGLE_OAUTH_CONFIG.token_url,
                    client_id=GOOGLE_OAUTH_CONFIG.client_id,
                    client_secret=GOOGLE_OAUTH_CONFIG.client_secret,
                    scopes=self.scopes
                )
                return build('calendar', 'v3', credentials=creds)
            
            # Fallback to default service
            # (Note: we need to recreate the service for calendar if it's not gmail)
            # Re-using internal credentials if available
            stored_token = token_storage.get_token("google")
            if stored_token:
                creds = Credentials(
                    token=stored_token.get("access_token"),
                    refresh_token=stored_token.get("refresh_token"),
                    token_uri=GOOGLE_OAUTH_CONFIG.token_url,
                    client_id=GOOGLE_OAUTH_CONFIG.client_id,
                    client_secret=GOOGLE_OAUTH_CONFIG.client_secret,
                    scopes=self.scopes
                )
                return build('calendar', 'v3', credentials=creds)
            return None
        except Exception as e:
            logger.error(f"Failed to create calendar service: {e}")
            return None

    def get_messages(self, query: str = "", max_results: int = 50, include_spam_trash: bool = False, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get messages from Gmail"""
        try:
            service = self._get_service_with_token(token)
            if not service:
                logger.warning("Gmail service not available")
                return []

            messages = []
            page_token = None
            
            while len(messages) < max_results:
                try:
                    result = service.users().messages().list(
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
                full_msg = self.get_message(msg['id'], token=token)
                if full_msg:
                    full_messages.append(full_msg)
            
            return full_messages
            
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    def get_message(self, message_id: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific message by ID"""
        try:
            service = self._get_service_with_token(token)
            if not service:
                return None

            message = service.users().messages().get(
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
                'internalDate': message.get('internalDate'),
                'attachments': self._extract_attachments(message['payload'])
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

    def _extract_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract attachment metadata from payload"""
        attachments = []
        try:
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('filename') and part.get('body') and 'attachmentId' in part['body']:
                        attachments.append({
                            'filename': part['filename'],
                            'mimeType': part['mimeType'],
                            'attachmentId': part['body']['attachmentId'],
                            'size': part['body'].get('size', 0)
                        })
                    
                    # Recursive check for nested parts
                    if 'parts' in part:
                        attachments.extend(self._extract_attachments(part))
        except Exception as e:
            logger.error(f"Error extracting attachments: {e}")
        return attachments

    def get_attachment_content(self, message_id: str, attachment_id: str, token: Optional[str] = None) -> Optional[bytes]:
        """Fetch attachment content as bytes"""
        try:
            service = self._get_service_with_token(token)
            if not service:
                return None
            
            attachment = service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            data = attachment.get('data')
            if data:
                return base64.urlsafe_b64decode(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get attachment content: {e}")
            return None
    
    def send_message(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "", thread_id: str = None, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Send an email"""
        try:
            service = self._get_service_with_token(token)
            if not service:
                logger.error("Cannot send email: No Gmail service available")
                return None

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
                result = service.users().messages().send(
                    userId='me',
                    body=message_data
                ).execute()
            else:
                result = service.users().messages().send(
                    userId='me',
                    body={'raw': raw}
                ).execute()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    def reply_to_message(self, thread_id: str, body: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Reply to a specific message thread"""
        try:
            service = self._get_service_with_token(token)
            if not service:
                return None
                
            # Get the thread to find the original message details
            thread = service.users().threads().get(userId='me', id=thread_id).execute()
            messages = thread.get('messages', [])
            if not messages:
                return None
                
            last_msg = messages[-1]
            headers = last_msg.get('payload', {}).get('headers', [])
            
            # Find necessary headers for replying
            msg_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)
            reply_to = next((h['value'] for h in headers if h['name'].lower() == 'reply-to'), None)
            if not reply_to:
                reply_to = next((h['value'] for h in headers if h['name'].lower() == 'from'), None)
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "Re: (no subject)")
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
                
            message = MIMEMultipart()
            message['to'] = reply_to
            message['subject'] = subject
            
            if msg_id:
                message['In-Reply-To'] = msg_id
                message['References'] = msg_id
                
            message.attach(MIMEText(body, 'plain'))
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            result = service.users().messages().send(
                userId='me',
                body={'raw': raw, 'threadId': thread_id}
            ).execute()
            
            return result
        except Exception as e:
            logger.error(f"Failed to reply to message: {e}")
            return None
    
    def draft_message(self, to: str, subject: str, body: str, thread_id: str = None, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a draft email"""
        try:
            service = self._get_service_with_token(token)
            if not service:
                return None

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
            
            result = service.users().drafts().create(
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
    
    def get_labels(self, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all labels"""
        try:
            service = self._get_service_with_token(token)
            if not service:
                return []
            result = service.users().labels().list(userId='me').execute()
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

    async def sync_to_postgres_cache(self, user_id: str = "me") -> Dict[str, Any]:
        """Sync Gmail analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            if not self.service:
                return {"success": False, "error": "Gmail service not initialized"}
                
            profile = self.service.users().getProfile(userId=user_id).execute()
            total_messages = profile.get('messagesTotal', 0)
            total_threads = profile.get('threadsTotal', 0)
            
            # Get unread count
            unread_res = self.service.users().messages().list(userId=user_id, q="is:unread", maxResults=1).execute()
            unread_count = unread_res.get('resultSizeEstimate', 0)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("gmail_total_messages", total_messages, "count"),
                    ("gmail_total_threads", total_threads, "count"),
                    ("gmail_unread_count", unread_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="gmail",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="gmail",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Gmail metrics to PostgreSQL cache")
            except Exception as e:
                logger.error(f"Error saving Gmail metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Gmail PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str = "me") -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Gmail"""
        # Pipeline 1: Atom Memory
        # Triggered via gmail_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # --- NATIVE HUB SYNC METHODS (PHASE 37) ---

    async def fetch_recent_messages(self, user_id: str, max_results: int = 50, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch recent Gmail messages and ingest them into the Communication Hub pipeline"""
        from integrations.atom_communication_ingestion_pipeline import get_ingestion_pipeline
        
        try:
            # We use the existing get_messages method but we need full details
            messages_list = self.get_messages(max_results=max_results, token=token)
            if not messages_list:
                return []
            
            pipeline = get_ingestion_pipeline()
            full_messages = []
            
            for msg_summary in messages_list:
                msg = self.get_message_details(msg_summary['id'], token=token)
                if msg:
                    # Ingest into pipeline
                    # Pipeline expects Dict[str, Any] which it then normalizes
                    pipeline.ingest_message("gmail", msg)
                    full_messages.append(msg)
            
            return full_messages
        except Exception as e:
            logger.error(f"Error in fetch_recent_messages: {e}")
            return []

    async def sync_calendar_events(self, user_id: str, days_ahead: int = 7, token: Optional[str] = None):
        """Sync Google Calendar events and ingest them into the Calendar Hub pipeline"""
        try:
            from core.database import SessionLocal
            from core.collaboration_hub_service import CollaborationHubService
            
            service = self._get_calendar_service(token)
            if not service:
                logger.error("Failed to get Google Calendar service for sync")
                return
                
            now = datetime.now(timezone.utc).isoformat() + 'Z'
            end_time = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId='primary', timeMin=now, timeMax=end_time,
                singleEvents=True, orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            db = SessionLocal()
            hub_service = CollaborationHubService(db)
            
            from integrations.atom_communication_ingestion_pipeline import get_ingestion_pipeline
            pipeline = get_ingestion_pipeline()
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                # Ingest into unified hub (Postgres)
                hub_service.upsert_calendar_event(
                    tenant_id=user_id, # Using user_id as tenant_id for now in this context
                    provider="google_calendar",
                    external_id=event['id'],
                    data={
                        "title": event.get('summary', 'No Title'),
                        "description": event.get('description', ''),
                        "location": event.get('location', ''),
                        "start_time": datetime.fromisoformat(start.replace('Z', '+00:00')),
                        "end_time": datetime.fromisoformat(end.replace('Z', '+00:00')),
                        "is_all_day": 'date' in event['start'],
                        "organizer": event.get('organizer', {}).get('email', ''),
                        "attendees": event.get('attendees', []),
                        "status": event.get('status', 'confirmed'),
                        "metadata_json": event
                    }
                )
                
                # Ingest into memory pipeline (LanceDB)
                try:
                    pipeline.ingest_calendar_event("google_calendar", {
                        "id": event['id'],
                        "title": event.get('summary', 'No Title'),
                        "description": event.get('description', ''),
                        "location": event.get('location', ''),
                        "start_time": datetime.fromisoformat(start.replace('Z', '+00:00')),
                        "end_time": datetime.fromisoformat(end.replace('Z', '+00:00')),
                        "is_all_day": 'date' in event['start'],
                        "organizer": event.get('organizer', {}).get('email', ''),
                        "attendees": event.get('attendees', []),
                        "metadata": event,
                        "tenant_id": user_id
                    })
                except Exception as ex:
                    logger.error(f"Memory ingestion failed for Google event {event['id']}: {ex}")
                    
            db.close()
        except Exception as e:
            logger.error(f"Error syncing Google Calendar events: {e}")

    def create_calendar_event(self, event_data: Dict[str, Any], token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new calendar event in Google Calendar"""
        try:
            service = self._get_calendar_service(token)
            if not service:
                return None
            return service.events().insert(calendarId='primary', body=event_data).execute()
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            return None

    def update_calendar_event(self, event_id: str, event_data: Dict[str, Any], token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update an existing calendar event in Google Calendar"""
        try:
            service = self._get_calendar_service(token)
            if not service:
                return None
            return service.events().patch(calendarId='primary', eventId=event_id, body=event_data).execute()
        except Exception as e:
            logger.error(f"Failed to update Google Calendar event {event_id}: {e}")
            return None

    def get_operations(self) -> List[Dict[str, Any]]:
        """
        Return list of available Gmail operations for MCP tool registration.

        Each operation includes complexity level for governance mapping.

        Returns:
            List of operation definitions
        """
        return [
            {
                "name": "send_email",
                "description": "Send an email via Gmail",
                "parameters": {'to': {'type': 'string', 'required': True}, 'subject': {'type': 'string', 'required': True}, 'body': {'type': 'string', 'required': True}},
                "complexity": 3
            },
            {
                "name": "list_messages",
                "description": "List email messages from Gmail",
                "parameters": {'max_results': {'type': 'integer', 'required': False}, 'query': {'type': 'string', 'required': False}},
                "complexity": 1
            },
        ]

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Gmail operation with tenant context.

        Args:
            operation: Operation name (e.g., "send_email", "list_messages")
            parameters: Operation parameters
            context: Tenant context dict with tenant_id, agent_id, workspace_id

        Returns:
            Dict with success status and result

        CRITICAL: Validates tenant_id from context to prevent cross-tenant access.
        """
        # Validate tenant context
        if context and 'tenant_id' in context:
            tenant_id = context.get('tenant_id')
            if tenant_id != self.tenant_id:
                logger.error(f"Tenant ID mismatch: expected {self.tenant_id}, got {tenant_id}")
                return {
                    "success": False,
                    "error": "Tenant ID mismatch",
                    "operation": operation
                }

        # Execute operation based on operation name
        try:
            if operation == "send_email":
                result = self.send_message(
                    to=parameters.get('to'),
                    subject=parameters.get('subject'),
                    body=parameters.get('body'),
                    cc=parameters.get('cc', ''),
                    bcc=parameters.get('bcc', ''),
                    thread_id=parameters.get('thread_id'),
                    token=parameters.get('token')
                )
                return {"success": bool(result), "result": result}
            elif operation == "list_messages":
                messages = self.get_messages(
                    query=parameters.get('query', ''),
                    max_results=parameters.get('max_results', 50),
                    token=parameters.get('token')
                )
                return {"success": True, "result": messages}
            elif operation == "get_message":
                message = self.get_message(
                    message_id=parameters.get('message_id'),
                    token=parameters.get('token')
                )
                return {"success": bool(message), "result": message}
            elif operation == "search_messages":
                messages = self.search_messages(
                    query=parameters.get('query', ''),
                    max_results=parameters.get('max_results', 50)
                )
                return {"success": True, "result": messages}
            elif operation == "reply_to_message":
                result = self.reply_to_message(
                    thread_id=parameters.get('thread_id'),
                    body=parameters.get('body'),
                    token=parameters.get('token')
                )
                return {"success": bool(result), "result": result}
            elif operation == "draft_message":
                result = self.draft_message(
                    to=parameters.get('to'),
                    subject=parameters.get('subject'),
                    body=parameters.get('body'),
                    thread_id=parameters.get('thread_id'),
                    token=parameters.get('token')
                )
                return {"success": bool(result), "result": result}
            elif operation == "modify_message":
                result = self.modify_message(
                    message_id=parameters.get('message_id'),
                    add_labels=parameters.get('add_labels'),
                    remove_labels=parameters.get('remove_labels')
                )
                return {"success": result, "result": result}
            elif operation == "delete_message":
                result = self.delete_message(
                    message_id=parameters.get('message_id')
                )
                return {"success": result, "result": result}
            elif operation == "sync_calendar":
                await self.sync_calendar_events(
                    user_id=parameters.get('user_id', self.tenant_id),
                    days_ahead=parameters.get('days_ahead', 7),
                    token=parameters.get('token')
                )
                return {"success": True, "result": "Calendar synced"}
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "operation": operation
                }
        except Exception as e:
            logger.error(f"Error executing Gmail operation {operation}: {e}")
            error_code = IntegrationErrorCode.UNKNOWN
            e_str = str(e).lower()
            if "invalid" in e_str and ("credentials" in e_str or "auth" in e_str):
                error_code = IntegrationErrorCode.AUTH_INVALID
            elif "rate limit" in e_str or "quotalimit" in e_str or "429" in e_str:
                error_code = IntegrationErrorCode.RATE_LIMIT
            elif "not found" in e_str or "404" in e_str:
                error_code = IntegrationErrorCode.NOT_FOUND
            elif "permission" in e_str or "forbidden" in e_str or "403" in e_str:
                error_code = IntegrationErrorCode.FORBIDDEN
                
            return {
                "success": False,
                "error": error_code.value,
                "message": str(e),
                "operation": operation
            }

    async def fetch_recent_messages(self, user_id: str, max_results: int = 20, token: Optional[str] = None):
        """Fetch recent Gmail messages and ingest them into the pipeline (hub_sync_service compatibility)"""
        from integrations.atom_communication_ingestion_pipeline import get_ingestion_pipeline
        try:
            # Note: get_messages returns a list of parsed message dicts
            messages = await self.get_messages(max_results=max_results, token=token)
            pipeline = get_ingestion_pipeline()
            for msg in messages:
                pipeline.ingest_message("google", msg)
            return messages
        except Exception as e:
            logger.error(f"Error in GmailService.fetch_recent_messages: {e}")
            return []

    async def sync_calendar_events(self, user_id: str, days_ahead: int = 7, token: Optional[str] = None):
        """Sync Google Calendar events and ingest into pipeline (hub_sync_service compatibility)"""
        # Placeholder compatible with hub_sync_service
        logger.info(f"GmailService.sync_calendar_events: Syncing for {user_id}")
        return []

def get_gmail_service(tenant_id: str = "default", config: Dict[str, Any] = {}) -> GmailService:
    """Factory function for GmailService (hub_sync_service compatibility)"""
    return GmailService(tenant_id, config)
