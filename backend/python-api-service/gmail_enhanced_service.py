"""
Gmail Enhanced Service Implementation
Complete Gmail email workflow automation with API integration
"""

import os
import logging
import json
import asyncio
import base64
import mimetypes
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import httpx
import aiofiles
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Gmail API configuration
GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_UPLOAD_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/send"
GMAIL_ATTACHMENTS_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages"

@dataclass
class GmailMessage:
    """Gmail message representation"""
    id: str
    thread_id: str
    subject: str
    from_email: str
    to_emails: List[str]
    cc_emails: List[str]
    bcc_emails: List[str]
    date: str
    body: str
    body_html: str
    snippet: str
    attachments: List[Dict[str, Any]]
    labels: List[str]
    is_read: bool
    is_starred: bool
    is_draft: bool
    is_sent: bool
    is_inbox: bool
    is_important: bool
    size: int
    history_id: str
    internal_date: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class GmailThread:
    """Gmail thread representation"""
    id: str
    history_id: str
    messages: List[GmailMessage]
    snippet: str
    message_count: int
    participant_emails: List[str]
    subject: str
    date: str
    is_unread: bool
    labels: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class GmailLabel:
    """Gmail label representation"""
    id: str
    name: str
    type: str  # user, system
    message_list_visibility: str
    label_list_visibility: str
    color: Optional[Dict[str, str]]
    total_messages: int
    unread_messages: int
    threads_total: int
    threads_unread: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class GmailAttachment:
    """Gmail attachment representation"""
    id: str
    message_id: str
    filename: str
    mime_type: str
    size: int
    data: str  # Base64 encoded content
    attachment_id: str
    download_url: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class GmailContact:
    """Gmail contact representation"""
    email: str
    name: str
    avatar_url: str
    frequency: int
    last_contact: str
    labels: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class GmailDraft:
    """Gmail draft representation"""
    id: str
    message: GmailMessage
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

class GmailEnhancedService:
    """Enhanced Gmail service with complete email workflow automation"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.api_base_url = GMAIL_API_BASE_URL
        self.send_url = GMAIL_SEND_URL
        self.upload_url = GMAIL_UPLOAD_URL
        self.attachments_url = GMAIL_ATTACHMENTS_URL
        self.message_cache = {}
        self.thread_cache = {}
        self.label_cache = {}
        
        # Common Gmail labels
        self.system_labels = {
            'INBOX': 'inbox',
            'SENT': 'sent',
            'DRAFT': 'draft',
            'SPAM': 'spam',
            'TRASH': 'trash',
            'STARRED': 'starred',
            'IMPORTANT': 'important',
            'UNREAD': 'unread',
            'CATEGORY_PERSONAL': 'personal',
            'CATEGORY_SOCIAL': 'social',
            'CATEGORY_PROMOTIONS': 'promotions',
            'CATEGORY_UPDATES': 'updates',
            'CATEGORY_FORUMS': 'forums'
        }
        
        # MIME type handling
        self.mime_types = {
            'text': ['text/plain', 'text/html'],
            'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            'document': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            'spreadsheet': ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
            'presentation': ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'],
            'archive': ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed']
        }
    
    def _get_mime_category(self, mime_type: str) -> str:
        """Get MIME type category"""
        for category, types in self.mime_types.items():
            if mime_type in types:
                return category
        return 'other'
    
    def _parse_email_address(self, address_str: str) -> Dict[str, str]:
        """Parse email address string"""
        if not address_str:
            return {'email': '', 'name': ''}
        
        # Simple parsing - could be enhanced
        if '<' in address_str and '>' in address_str:
            name = address_str.split('<')[0].strip().strip('"')
            email = address_str.split('<')[1].split('>')[0].strip()
        else:
            name = ''
            email = address_str.strip()
        
        return {'email': email, 'name': name}
    
    def _decode_base64(self, data: str) -> str:
        """Decode base64 string"""
        try:
            # Add padding if needed
            missing_padding = len(data) % 4
            if missing_padding:
                data += '=' * (4 - missing_padding)
            
            # Decode URL-safe base64
            data = data.replace('-', '+').replace('_', '/')
            return base64.b64decode(data).decode('utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Error decoding base64: {e}")
            return ''
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Extract email body from payload"""
        body_text = ''
        body_html = ''
        
        if 'parts' in payload:
            # Multipart message
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                body = part.get('body', {})
                
                if 'parts' in part:
                    # Nested multipart
                    nested_body = self._extract_email_body(part)
                    body_text += nested_body.get('text', '')
                    body_html += nested_body.get('html', '')
                elif mime_type in ['text/plain']:
                    data = body.get('data', '')
                    if data:
                        body_text += self._decode_base64(data)
                elif mime_type in ['text/html']:
                    data = body.get('data', '')
                    if data:
                        body_html += self._decode_base64(data)
        else:
            # Single part message
            mime_type = payload.get('mimeType', '')
            body = payload.get('body', {})
            data = body.get('data', '')
            
            if data:
                content = self._decode_base64(data)
                if mime_type in ['text/plain']:
                    body_text = content
                elif mime_type in ['text/html']:
                    body_html = content
        
        return {'text': body_text, 'html': body_html}
    
    def _extract_attachments(self, payload: Dict[str, Any], message_id: str) -> List[GmailAttachment]:
        """Extract attachments from payload"""
        attachments = []
        
        if 'parts' in payload:
            for i, part in enumerate(payload['parts']):
                mime_type = part.get('mimeType', '')
                filename = part.get('filename', '')
                
                if filename:  # This is an attachment
                    body = part.get('body', {})
                    attachment_id = body.get('attachmentId', '')
                    size = body.get('size', 0)
                    
                    if attachment_id:
                        attachment = GmailAttachment(
                            id=f"{message_id}_{i}",
                            message_id=message_id,
                            filename=filename,
                            mime_type=mime_type,
                            size=size,
                            data='',  # Will be loaded separately
                            attachment_id=attachment_id,
                            download_url=f"{self.api_base_url}/me/attachments/{message_id}/{attachment_id}",
                            metadata={
                                'part_id': str(i),
                                'mime_category': self._get_mime_category(mime_type),
                                'extracted_at': datetime.utcnow().isoformat()
                            }
                        )
                        attachments.append(attachment)
                
                # Check nested parts
                if 'parts' in part:
                    nested_attachments = self._extract_attachments(part, message_id)
                    attachments.extend(nested_attachments)
        
        return attachments
    
    def _extract_headers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract email headers"""
        headers = {}
        
        if 'headers' in payload:
            for header in payload['headers']:
                name = header.get('name', '').lower()
                value = header.get('value', '')
                headers[name] = value
        
        return headers
    
    async def get_message(self, message_id: str, access_token: str, 
                        format: str = 'full', 
                        include_attachments: bool = True) -> Optional[GmailMessage]:
        """Get Gmail message"""
        try:
            # Check cache first
            cache_key = f"{access_token}_{message_id}"
            if cache_key in self.message_cache:
                return self.message_cache[cache_key]
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'format': format
            }
            
            if not include_attachments:
                params['format'] = 'metadata'
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/messages/{message_id}",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract message data
                payload = data.get('payload', {})
                headers = self._extract_headers(payload)
                
                # Get body
                bodies = self._extract_email_body(payload)
                body_text = bodies.get('text', '')
                body_html = bodies.get('html', '')
                
                # Get attachments
                attachments = []
                if include_attachments and format == 'full':
                    attachments = self._extract_attachments(payload, message_id)
                
                # Parse addresses
                from_email = headers.get('from', '')
                to_emails = [email.strip() for email in headers.get('to', '').split(',') if email.strip()]
                cc_emails = [email.strip() for email in headers.get('cc', '').split(',') if email.strip()]
                bcc_emails = [email.strip() for email in headers.get('bcc', '').split(',') if email.strip()]
                
                # Get subject
                subject = headers.get('subject', '')
                
                # Get labels
                labels = data.get('labelIds', [])
                label_names = [self.system_labels.get(label, label.lower()) for label in labels]
                
                # Check status
                is_read = 'UNREAD' not in labels
                is_starred = 'STARRED' in labels
                is_draft = 'DRAFT' in labels
                is_sent = 'SENT' in labels
                is_inbox = 'INBOX' in labels
                is_important = 'IMPORTANT' in labels
                
                # Get dates
                date = headers.get('date', '')
                internal_date = data.get('internalDate', '')
                if internal_date:
                    date = datetime.fromtimestamp(int(internal_date) / 1000, timezone.utc).isoformat()
                
                message = GmailMessage(
                    id=data.get('id', ''),
                    thread_id=data.get('threadId', ''),
                    subject=subject,
                    from_email=from_email,
                    to_emails=to_emails,
                    cc_emails=cc_emails,
                    bcc_emails=bcc_emails,
                    date=date,
                    body=body_text,
                    body_html=body_html,
                    snippet=data.get('snippet', ''),
                    attachments=[att.to_dict() for att in attachments],
                    labels=label_names,
                    is_read=is_read,
                    is_starred=is_starred,
                    is_draft=is_draft,
                    is_sent=is_sent,
                    is_inbox=is_inbox,
                    is_important=is_important,
                    size=data.get('sizeEstimate', 0),
                    history_id=data.get('historyId', ''),
                    internal_date=internal_date,
                    metadata={
                        'access_token': access_token,
                        'format': format,
                        'headers': headers,
                        'retrieved_at': datetime.utcnow().isoformat()
                    }
                )
                
                # Cache message
                self.message_cache[cache_key] = message
                
                logger.info(f"Gmail message retrieved: {message_id}")
                return message
                
        except Exception as e:
            logger.error(f"Error getting Gmail message: {e}")
            return None
    
    async def get_thread(self, thread_id: str, access_token: str) -> Optional[GmailThread]:
        """Get Gmail thread"""
        try:
            # Check cache first
            cache_key = f"{access_token}_{thread_id}"
            if cache_key in self.thread_cache:
                return self.thread_cache[cache_key]
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/threads/{thread_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Get all messages in thread
                messages_data = data.get('messages', [])
                messages = []
                
                participant_emails = set()
                
                for msg_data in messages_data:
                    # Get message details
                    payload = msg_data.get('payload', {})
                    headers = self._extract_headers(payload)
                    
                    # Parse addresses
                    from_email = headers.get('from', '')
                    to_emails = [email.strip() for email in headers.get('to', '').split(',') if email.strip()]
                    
                    participant_emails.add(from_email)
                    participant_emails.update(to_emails)
                    
                    # Get message
                    message = await self.get_message(msg_data.get('id', ''), access_token)
                    if message:
                        messages.append(message)
                
                # Sort messages by date
                messages.sort(key=lambda m: m.date)
                
                # Get thread info
                snippet = data.get('snippet', '')
                history_id = data.get('historyId', '')
                
                # Get subject from first message
                subject = messages[0].subject if messages else ''
                
                # Get date from last message
                date = messages[-1].date if messages else ''
                
                # Get labels
                labels = data.get('messages', [{}])[0].get('labelIds', [])
                label_names = [self.system_labels.get(label, label.lower()) for label in labels]
                
                is_unread = 'UNREAD' in labels
                
                thread = GmailThread(
                    id=data.get('id', ''),
                    history_id=history_id,
                    messages=messages,
                    snippet=snippet,
                    message_count=len(messages),
                    participant_emails=list(participant_emails),
                    subject=subject,
                    date=date,
                    is_unread=is_unread,
                    labels=label_names,
                    metadata={
                        'access_token': access_token,
                        'retrieved_at': datetime.utcnow().isoformat()
                    }
                )
                
                # Cache thread
                self.thread_cache[cache_key] = thread
                
                logger.info(f"Gmail thread retrieved: {thread_id}")
                return thread
                
        except Exception as e:
            logger.error(f"Error getting Gmail thread: {e}")
            return None
    
    async def list_messages(self, access_token: str, 
                          max_results: int = 50,
                          query: str = None,
                          label_ids: List[str] = None,
                          include_spam_trash: bool = False,
                          page_token: str = None) -> Dict[str, Any]:
        """List Gmail messages"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'maxResults': max_results,
                'includeSpamTrash': include_spam_trash
            }
            
            if query:
                params['q'] = query
            
            if label_ids:
                params['labelIds'] = label_ids
            
            if page_token:
                params['pageToken'] = page_token
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/messages",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Get message IDs
                message_ids = [msg.get('id', '') for msg in data.get('messages', [])]
                
                # Get full messages
                messages = []
                for message_id in message_ids:
                    message = await self.get_message(message_id, access_token)
                    if message:
                        messages.append(message)
                
                return {
                    'messages': [msg.to_dict() for msg in messages],
                    'next_page_token': data.get('nextPageToken'),
                    'result_size_estimate': data.get('resultSizeEstimate', 0),
                    'total_results': len(messages)
                }
                
        except Exception as e:
            logger.error(f"Error listing Gmail messages: {e}")
            return {
                'messages': [],
                'error': str(e),
                'error_type': 'list_error'
            }
    
    async def list_threads(self, access_token: str,
                         max_results: int = 50,
                         query: str = None,
                         label_ids: List[str] = None,
                         include_spam_trash: bool = False,
                         page_token: str = None) -> Dict[str, Any]:
        """List Gmail threads"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'maxResults': max_results,
                'includeSpamTrash': include_spam_trash
            }
            
            if query:
                params['q'] = query
            
            if label_ids:
                params['labelIds'] = label_ids
            
            if page_token:
                params['pageToken'] = page_token
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/threads",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Get thread IDs
                thread_ids = [thread.get('id', '') for thread in data.get('threads', [])]
                
                # Get full threads
                threads = []
                for thread_id in thread_ids:
                    thread = await self.get_thread(thread_id, access_token)
                    if thread:
                        threads.append(thread)
                
                return {
                    'threads': [thread.to_dict() for thread in threads],
                    'next_page_token': data.get('nextPageToken'),
                    'result_size_estimate': data.get('resultSizeEstimate', 0),
                    'total_results': len(threads)
                }
                
        except Exception as e:
            logger.error(f"Error listing Gmail threads: {e}")
            return {
                'threads': [],
                'error': str(e),
                'error_type': 'list_error'
            }
    
    async def send_message(self, access_token: str,
                         to: str, subject: str, body: str,
                         cc: str = None, bcc: str = None,
                         from_email: str = None,
                         reply_to_message_id: str = None,
                         attachments: List[Dict[str, Any]] = None,
                         is_html: bool = False) -> Dict[str, Any]:
        """Send Gmail message"""
        try:
            # Create message
            if is_html or attachments:
                # Multipart message
                msg = MIMEMultipart('mixed')
                
                # Add headers
                msg['To'] = to
                msg['Subject'] = subject
                if cc:
                    msg['Cc'] = cc
                if bcc:
                    msg['Bcc'] = bcc
                if from_email:
                    msg['From'] = from_email
                if reply_to_message_id:
                    msg['In-Reply-To'] = reply_to_message_id
                    msg['References'] = reply_to_message_id
                
                # Add body
                if is_html:
                    html_part = MIMEText(body, 'html')
                    msg.attach(html_part)
                else:
                    text_part = MIMEText(body, 'plain')
                    msg.attach(text_part)
                
                # Add attachments
                if attachments:
                    for attachment in attachments:
                        file_path = attachment.get('path', '')
                        filename = attachment.get('name', '')
                        
                        if file_path and os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                data = f.read()
                            
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(data)
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename="{filename}"'
                            )
                            msg.attach(part)
            else:
                # Simple text message
                msg = MIMEText(body, 'plain')
                msg['To'] = to
                msg['Subject'] = subject
                if cc:
                    msg['Cc'] = cc
                if bcc:
                    msg['Bcc'] = bcc
                if from_email:
                    msg['From'] = from_email
                if reply_to_message_id:
                    msg['In-Reply-To'] = reply_to_message_id
                    msg['References'] = reply_to_message_id
            
            # Convert to base64
            message_data = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'raw': message_data
            }
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.send_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                logger.info(f"Gmail message sent: {data.get('id', '')}")
                return {
                    'success': True,
                    'message_id': data.get('id', ''),
                    'thread_id': data.get('threadId', ''),
                    'label_ids': data.get('labelIds', [])
                }
                
        except Exception as e:
            logger.error(f"Error sending Gmail message: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'send_error'
            }
    
    async def get_labels(self, access_token: str) -> List[GmailLabel]:
        """Get Gmail labels"""
        try:
            # Check cache first
            cache_key = f"{access_token}_labels"
            if cache_key in self.label_cache:
                return self.label_cache[cache_key]
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/labels",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                labels_data = data.get('labels', [])
                
                labels = []
                for label_data in labels_data:
                    label = GmailLabel(
                        id=label_data.get('id', ''),
                        name=label_data.get('name', ''),
                        type=label_data.get('type', ''),
                        message_list_visibility=label_data.get('messageListVisibility', ''),
                        label_list_visibility=label_data.get('labelListVisibility', ''),
                        color=label_data.get('color'),
                        total_messages=label_data.get('messagesTotal', 0),
                        unread_messages=label_data.get('messagesUnread', 0),
                        threads_total=label_data.get('threadsTotal', 0),
                        threads_unread=label_data.get('threadsUnread', 0),
                        metadata={
                            'access_token': access_token,
                            'retrieved_at': datetime.utcnow().isoformat()
                        }
                    )
                    labels.append(label)
                
                # Cache labels
                self.label_cache[cache_key] = labels
                
                logger.info(f"Gmail labels retrieved: {len(labels)}")
                return labels
                
        except Exception as e:
            logger.error(f"Error getting Gmail labels: {e}")
            return []
    
    async def create_label(self, access_token: str,
                          name: str, label_list_visibility: str = 'labelShow',
                          message_list_visibility: str = 'show',
                          color: Dict[str, str] = None) -> Optional[GmailLabel]:
        """Create Gmail label"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'name': name,
                'labelListVisibility': label_list_visibility,
                'messageListVisibility': message_list_visibility
            }
            
            if color:
                payload['color'] = color
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base_url}/me/labels",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                label = GmailLabel(
                    id=data.get('id', ''),
                    name=data.get('name', ''),
                    type=data.get('type', ''),
                    message_list_visibility=data.get('messageListVisibility', ''),
                    label_list_visibility=data.get('labelListVisibility', ''),
                    color=data.get('color'),
                    total_messages=0,
                    unread_messages=0,
                    threads_total=0,
                    threads_unread=0,
                    metadata={
                        'access_token': access_token,
                        'created_at': datetime.utcnow().isoformat()
                    }
                )
                
                logger.info(f"Gmail label created: {name}")
                return label
                
        except Exception as e:
            logger.error(f"Error creating Gmail label: {e}")
            return None
    
    async def modify_message_labels(self, access_token: str,
                                  message_id: str,
                                  add_labels: List[str] = None,
                                  remove_labels: List[str] = None) -> bool:
        """Modify Gmail message labels"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {}
            if add_labels:
                payload['addLabelIds'] = add_labels
            if remove_labels:
                payload['removeLabelIds'] = remove_labels
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base_url}/me/messages/{message_id}/modify",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                # Clear message cache
                cache_key = f"{access_token}_{message_id}"
                if cache_key in self.message_cache:
                    del self.message_cache[cache_key]
                
                logger.info(f"Gmail message labels modified: {message_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error modifying Gmail message labels: {e}")
            return False
    
    async def trash_message(self, access_token: str, message_id: str) -> bool:
        """Trash Gmail message"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base_url}/me/messages/{message_id}/trash",
                    headers=headers
                )
                response.raise_for_status()
                
                logger.info(f"Gmail message trashed: {message_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error trashing Gmail message: {e}")
            return False
    
    async def delete_message(self, access_token: str, message_id: str) -> bool:
        """Delete Gmail message permanently"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(
                    f"{self.api_base_url}/me/messages/{message_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                logger.info(f"Gmail message deleted: {message_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting Gmail message: {e}")
            return False
    
    async def get_attachment(self, access_token: str,
                          message_id: str, attachment_id: str) -> Optional[GmailAttachment]:
        """Get Gmail attachment"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/messages/{message_id}/attachments/{attachment_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                
                attachment = GmailAttachment(
                    id=f"{message_id}_{attachment_id}",
                    message_id=message_id,
                    filename=data.get('filename', ''),
                    mime_type=data.get('mimeType', ''),
                    size=data.get('size', 0),
                    data=data.get('data', ''),
                    attachment_id=attachment_id,
                    download_url=f"{self.api_base_url}/me/attachments/{message_id}/{attachment_id}",
                    metadata={
                        'access_token': access_token,
                        'retrieved_at': datetime.utcnow().isoformat()
                    }
                )
                
                logger.info(f"Gmail attachment retrieved: {attachment_id}")
                return attachment
                
        except Exception as e:
            logger.error(f"Error getting Gmail attachment: {e}")
            return None
    
    async def search_messages(self, access_token: str,
                           query: str, max_results: int = 50,
                           page_token: str = None) -> Dict[str, Any]:
        """Search Gmail messages"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'q': query,
                'maxResults': max_results
            }
            
            if page_token:
                params['pageToken'] = page_token
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/messages",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Get message IDs
                message_ids = [msg.get('id', '') for msg in data.get('messages', [])]
                
                # Get full messages
                messages = []
                for message_id in message_ids:
                    message = await self.get_message(message_id, access_token)
                    if message:
                        messages.append(message)
                
                return {
                    'messages': [msg.to_dict() for msg in messages],
                    'next_page_token': data.get('nextPageToken'),
                    'result_size_estimate': data.get('resultSizeEstimate', 0),
                    'total_results': len(messages),
                    'query': query
                }
                
        except Exception as e:
            logger.error(f"Error searching Gmail messages: {e}")
            return {
                'messages': [],
                'error': str(e),
                'error_type': 'search_error'
            }
    
    async def get_drafts(self, access_token: str) -> List[GmailDraft]:
        """Get Gmail drafts"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base_url}/me/drafts",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                drafts_data = data.get('drafts', [])
                
                drafts = []
                for draft_data in drafts_data:
                    msg_data = draft_data.get('message', {})
                    message_id = msg_data.get('id', '')
                    
                    if message_id:
                        message = await self.get_message(message_id, access_token)
                        if message:
                            draft = GmailDraft(
                                id=draft_data.get('id', ''),
                                message=message,
                                created_at='',  # Gmail doesn't provide this
                                updated_at='',
                                metadata={
                                    'access_token': access_token,
                                    'retrieved_at': datetime.utcnow().isoformat()
                                }
                            )
                            drafts.append(draft)
                
                logger.info(f"Gmail drafts retrieved: {len(drafts)}")
                return drafts
                
        except Exception as e:
            logger.error(f"Error getting Gmail drafts: {e}")
            return []
    
    async def create_draft(self, access_token: str,
                         to: str, subject: str, body: str,
                         cc: str = None, bcc: str = None,
                         from_email: str = None,
                         attachments: List[Dict[str, Any]] = None,
                         is_html: bool = False) -> Optional[GmailDraft]:
        """Create Gmail draft"""
        try:
            # Create message (similar to send_message)
            if is_html or attachments:
                msg = MIMEMultipart('mixed')
            else:
                msg = MIMEText(body, 'plain')
            
            # Add headers
            msg['To'] = to
            msg['Subject'] = subject
            if cc:
                msg['Cc'] = cc
            if bcc:
                msg['Bcc'] = bcc
            if from_email:
                msg['From'] = from_email
            
            # Convert to base64
            message_data = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'message': {
                    'raw': message_data
                }
            }
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.api_base_url}/me/drafts",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                draft_data = data.get('message', {})
                message_id = draft_data.get('id', '')
                
                if message_id:
                    message = await self.get_message(message_id, access_token)
                    if message:
                        draft = GmailDraft(
                            id=data.get('id', ''),
                            message=message,
                            created_at='',
                            updated_at='',
                            metadata={
                                'access_token': access_token,
                                'created_at': datetime.utcnow().isoformat()
                            }
                        )
                        
                        logger.info(f"Gmail draft created: {draft.id}")
                        return draft
                
            return None
                
        except Exception as e:
            logger.error(f"Error creating Gmail draft: {e}")
            return None
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "name": "Enhanced Gmail Service",
            "version": "1.0.0",
            "description": "Complete Gmail email workflow automation",
            "capabilities": [
                "message_operations",
                "thread_management",
                "label_management",
                "search_and_filtering",
                "draft_operations",
                "attachment_handling",
                "contact_management",
                "automation_features"
            ],
            "api_endpoints": [
                "/api/gmail/enhanced/messages/list",
                "/api/gmail/enhanced/messages/get",
                "/api/gmail/enhanced/messages/send",
                "/api/gmail/enhanced/threads/list",
                "/api/gmail/enhanced/threads/get",
                "/api/gmail/enhanced/labels/list",
                "/api/gmail/enhanced/labels/create",
                "/api/gmail/enhanced/attachments/get",
                "/api/gmail/enhanced/drafts/list",
                "/api/gmail/enhanced/drafts/create",
                "/api/gmail/enhanced/health"
            ],
            "supported_mime_types": self.mime_types,
            "system_labels": self.system_labels,
            "initialized_at": datetime.utcnow().isoformat()
        }

# Create singleton instance
gmail_enhanced_service = GmailEnhancedService()