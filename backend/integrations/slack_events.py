"""
Slack Event Handler - Real-time Event Processing
Handles Slack webhooks and real-time events
"""

import os
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from flask import Request, Response
import hmac
import hashlib

# Configure logging
logger = logging.getLogger(__name__)

class SlackEventHandler:
    """Handles Slack real-time events"""
    
    def __init__(self, signing_secret: str):
        self.signing_secret = signing_secret
        self.event_handlers: Dict[str, Callable] = self._initialize_handlers()
        self.message_handlers: Dict[str, Callable] = {}
        self.file_handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
        
        # Event statistics
        self.stats = {
            'events_received': 0,
            'events_processed': 0,
            'events_failed': 0,
            'last_event': None
        }
    
    def _initialize_handlers(self) -> Dict[str, Callable]:
        """Initialize default event handlers"""
        return {
            'url_verification': self._handle_url_verification,
            'event_callback': self._handle_event_callback,
            'app_rate_limited': self._handle_rate_limited
        }
    
    def verify_request(self, request: Request) -> bool:
        """Verify Slack request signature"""
        try:
            # Get headers
            timestamp = request.headers.get('X-Slack-Request-Timestamp')
            signature = request.headers.get('X-Slack-Signature')
            
            if not timestamp or not signature:
                self.logger.warning("Missing timestamp or signature headers")
                return False
            
            # Check timestamp (prevent replay attacks)
            current_time = int(datetime.now().timestamp())
            request_time = int(timestamp)
            if abs(current_time - request_time) > 300:  # 5 minutes
                self.logger.warning(f"Timestamp too old: {timestamp}")
                return False
            
            # Get body
            body = request.get_data()
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            
            # Create signature
            sig_basestring = f"v0:{timestamp}:{body}"
            expected_signature = 'v0=' + hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(expected_signature, signature)
            if not is_valid:
                self.logger.warning("Invalid signature")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error verifying request: {e}")
            return False
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register event handler"""
        self.event_handlers[event_type] = handler
        self.logger.info(f"Registered handler for {event_type}")
    
    def register_message_handler(self, message_subtype: str, handler: Callable):
        """Register message subtype handler"""
        self.message_handlers[message_subtype] = handler
        self.logger.info(f"Registered message handler for {message_subtype}")
    
    def register_file_handler(self, file_event: str, handler: Callable):
        """Register file event handler"""
        self.file_handlers[file_event] = handler
        self.logger.info(f"Registered file handler for {file_event}")
    
    async def handle_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Slack event"""
        try:
            self.stats['events_received'] += 1
            self.stats['last_event'] = datetime.utcnow().isoformat()
            
            event_type = event_data.get('type')
            
            # Handle main event types
            if event_type in self.event_handlers:
                result = await self.event_handlers[event_type](event_data)
                self.stats['events_processed'] += 1
                return result
            
            # Handle unknown events
            self.logger.warning(f"Unknown event type: {event_type}")
            self.stats['events_failed'] += 1
            return {'status': 'ignored', 'reason': 'Unknown event type'}
            
        except Exception as e:
            self.logger.error(f"Error handling event: {e}")
            self.stats['events_failed'] += 1
            return {'status': 'error', 'message': str(e)}
    
    async def _handle_url_verification(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle URL verification challenge"""
        challenge = event_data.get('challenge')
        self.logger.info("URL verification challenge received")
        return {'challenge': challenge}
    
    async def _handle_event_callback(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle event callback"""
        event = event_data.get('event', {})
        event_type = event.get('type')
        event_subtype = event.get('subtype')
        
        self.logger.info(f"Processing event callback: {event_type} (subtype: {event_subtype})")
        
        # Handle message events
        if event_type == 'message':
            return await self._handle_message_event(event)
        
        # Handle file events
        elif event_type in ['file_shared', 'file_deleted', 'file_public']:
            return await self._handle_file_event(event)
        
        # Handle channel events
        elif event_type in ['channel_created', 'channel_deleted', 'channel_archive', 'channel_unarchive']:
            return await self._handle_channel_event(event)
        
        # Handle team events
        elif event_type in ['team_join', 'team_leave']:
            return await self._handle_team_event(event)
        
        # Handle app events
        elif event_type in ['app_home_opened', 'app_mention']:
            return await self._handle_app_event(event)
        
        # Default handling
        return {'status': 'processed', 'event_type': event_type}
    
    async def _handle_rate_limited(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rate limiting notification"""
        self.logger.warning(f"Rate limited: {event_data}")
        return {'status': 'rate_limited', 'retry_after': event_data.get('retry_after')}
    
    async def _handle_message_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message events"""
        event_subtype = event.get('subtype')
        
        # Handle specific message subtypes
        if event_subtype and event_subtype in self.message_handlers:
            return await self.message_handlers[event_subtype](event)
        
        # Default message handling
        message_data = {
            'type': 'message',
            'subtype': event_subtype,
            'channel': event.get('channel'),
            'user': event.get('user'),
            'text': event.get('text', ''),
            'ts': event.get('ts'),
            'thread_ts': event.get('thread_ts'),
            'edited': event.get('edited'),
            'files': event.get('files', []),
            'reactions': event.get('reactions', [])
        }
        
        # Log message details
        self.logger.info(f"Message in channel {event.get('channel')} from user {event.get('user')}")
        
        return {'status': 'processed', 'event': 'message', 'data': message_data}
    
    async def _handle_file_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file events"""
        event_type = event.get('type')
        file_id = event.get('file_id')
        
        # Handle specific file events
        if event_type in self.file_handlers:
            return await self.file_handlers[event_type](event)
        
        file_data = {
            'type': event_type,
            'file_id': file_id,
            'user_id': event.get('user_id'),
            'channel_id': event.get('channel_id'),
            'file_details': event.get('file', {})
        }
        
        self.logger.info(f"File event {event_type} for file {file_id}")
        
        return {'status': 'processed', 'event': 'file', 'data': file_data}
    
    async def _handle_channel_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel events"""
        event_type = event.get('type')
        channel = event.get('channel')
        user = event.get('user')
        
        channel_data = {
            'type': event_type,
            'channel_id': channel.get('id') if isinstance(channel, dict) else channel,
            'channel_name': channel.get('name') if isinstance(channel, dict) else None,
            'user_id': user,
            'timestamp': event.get('event_ts')
        }
        
        self.logger.info(f"Channel event {event_type} for channel {channel}")
        
        return {'status': 'processed', 'event': 'channel', 'data': channel_data}
    
    async def _handle_team_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle team events"""
        event_type = event.get('type')
        user = event.get('user')
        
        team_data = {
            'type': event_type,
            'user_id': user,
            'user_details': event.get('user', {}),
            'timestamp': event.get('event_ts')
        }
        
        self.logger.info(f"Team event {event_type} for user {user}")
        
        return {'status': 'processed', 'event': 'team', 'data': team_data}
    
    async def _handle_app_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle app events"""
        event_type = event.get('type')
        user = event.get('user')
        channel = event.get('channel')
        
        app_data = {
            'type': event_type,
            'user_id': user,
            'channel_id': channel,
            'event_ts': event.get('event_ts'),
            'app_id': event.get('app_id')
        }
        
        self.logger.info(f"App event {event_type} in channel {channel}")
        
        return {'status': 'processed', 'event': 'app', 'data': app_data}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event handler statistics"""
        return {
            'events_received': self.stats['events_received'],
            'events_processed': self.stats['events_processed'],
            'events_failed': self.stats['events_failed'],
            'success_rate': (
                self.stats['events_processed'] / max(self.stats['events_received'], 1)
            ) * 100,
            'last_event': self.stats['last_event'],
            'registered_handlers': list(self.event_handlers.keys()),
            'registered_message_handlers': list(self.message_handlers.keys()),
            'registered_file_handlers': list(self.file_handlers.keys())
        }

# Default message handlers
async def handle_bot_message(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle bot messages"""
    logger.info(f"Bot message: {event.get('text', '')[:100]}")
    return {'status': 'processed', 'event': 'bot_message'}

async def handle_message_changed(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle message edits"""
    logger.info(f"Message changed in channel {event.get('channel')}")
    return {'status': 'processed', 'event': 'message_changed'}

async def handle_message_deleted(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle message deletions"""
    logger.info(f"Message deleted in channel {event.get('channel')}")
    return {'status': 'processed', 'event': 'message_deleted'}

async def handle_channel_join(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle channel joins"""
    user = event.get('user')
    channel = event.get('channel')
    logger.info(f"User {user} joined channel {channel}")
    return {'status': 'processed', 'event': 'channel_join'}

async def handle_channel_leave(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle channel leaves"""
    user = event.get('user')
    channel = event.get('channel')
    logger.info(f"User {user} left channel {channel}")
    return {'status': 'processed', 'event': 'channel_leave'}

# Default file handlers
async def handle_file_shared(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle file sharing"""
    file_id = event.get('file_id')
    user_id = event.get('user_id')
    logger.info(f"File {file_id} shared by user {user_id}")
    return {'status': 'processed', 'event': 'file_shared'}

# Create event handler instance
def create_slack_event_handler() -> Optional[SlackEventHandler]:
    """Create and configure Slack event handler"""
    try:
        signing_secret = os.getenv('SLACK_SIGNING_SECRET')
        if not signing_secret:
            logger.warning("SLACK_SIGNING_SECRET not configured")
            return None
        
        handler = SlackEventHandler(signing_secret)
        
        # Register default message handlers
        handler.register_message_handler('bot_message', handle_bot_message)
        handler.register_message_handler('message_changed', handle_message_changed)
        handler.register_message_handler('message_deleted', handle_message_deleted)
        handler.register_message_handler('channel_join', handle_channel_join)
        handler.register_message_handler('channel_leave', handle_channel_leave)
        
        # Register default file handlers
        handler.register_file_handler('file_shared', handle_file_shared)
        
        return handler
        
    except Exception as e:
        logger.error(f"Failed to create Slack event handler: {e}")
        return None

# Global instance
slack_event_handler = create_slack_event_handler()