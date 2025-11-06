"""
🔄 Zoom Real-Time Event Handlers
Handlers for processing real-time Zoom events and WebSocket communications
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict

import asyncpg
import httpx

from zoom_websocket_manager import (
    ZoomWebSocketManager, WebSocketMessage, WebSocketEvent, 
    ParticipantStatus, MeetingState
)

logger = logging.getLogger(__name__)

@dataclass
class ZoomMeetingEvent:
    """Zoom meeting event structure"""
    event_id: str
    event_type: str
    event_ts: int
    meeting_id: str
    account_id: str
    user_id: str
    participant: Optional[Dict[str, Any]] = None
    payload: Dict[str, Any] = None
    signature: Optional[str] = None
    timestamp: datetime = None

class ZoomRealTimeEventHandler:
    """Real-time Zoom event handler"""
    
    def __init__(self, db_pool: asyncpg.Pool, zoom_api_base_url: str, 
                 zoom_api_manager=None):
        self.db_pool = db_pool
        self.zoom_api_base_url = zoom_api_base_url
        self.zoom_api_manager = zoom_api_manager
        
        # Event processing
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self.processed_events: Dict[str, datetime] = {}
        
        # Meeting state cache
        self.meeting_states: Dict[str, MeetingState] = {}
        self.participant_states: Dict[str, Dict[str, Any]] = {}
        
        # Configuration
        self.config = {
            'event_retention_hours': 24,
            'max_retries': 3,
            'retry_delay': 2,
            'batch_size': 100,
            'processing_interval': 1,
            'state_sync_interval': 30,
            'event_deduplication_window': 300  # 5 minutes
        }
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # Statistics
        self.stats = {
            'events_processed': 0,
            'events_failed': 0,
            'meetings_tracked': 0,
            'participants_tracked': 0,
            'average_processing_time': 0,
            'last_event_time': None,
            'processing_rate': 0
        }
        
        # Initialize components
        asyncio.create_task(self._init_database())
    
    async def _init_database(self) -> None:
        """Initialize real-time event database tables"""
        if not self.db_pool:
            logger.warning("Database pool not available for real-time event handling")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create meeting events table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_meeting_events (
                        event_id VARCHAR(255) PRIMARY KEY,
                        event_type VARCHAR(100) NOT NULL,
                        event_ts BIGINT NOT NULL,
                        meeting_id VARCHAR(255) NOT NULL,
                        account_id VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        participant JSONB,
                        payload JSONB DEFAULT '{}'::jsonb,
                        signature TEXT,
                        processed BOOLEAN DEFAULT false,
                        retry_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        processed_at TIMESTAMP WITH TIME ZONE
                    );
                """)
                
                # Create participant states table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_participant_states (
                        participant_id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        account_id VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        joined_at TIMESTAMP WITH TIME ZONE,
                        left_at TIMESTAMP WITH TIME ZONE,
                        duration_seconds INTEGER,
                        is_host BOOLEAN DEFAULT false,
                        is_co_host BOOLEAN DEFAULT false,
                        audio_status JSONB DEFAULT '{}'::jsonb,
                        video_status JSONB DEFAULT '{}'::jsonb,
                        screen_share_status JSONB DEFAULT '{}'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create real-time analytics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_realtime_analytics (
                        analytics_id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        account_id VARCHAR(255) NOT NULL,
                        metric_type VARCHAR(100) NOT NULL,
                        metric_value NUMERIC NOT NULL,
                        metric_data JSONB DEFAULT '{}'::jsonb,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        metadata JSONB DEFAULT '{}'::jsonb
                    );
                """)
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_events_type ON zoom_meeting_events(event_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_events_meeting ON zoom_meeting_events(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_events_account ON zoom_meeting_events(account_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_events_user ON zoom_meeting_events(user_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_events_processed ON zoom_meeting_events(processed);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_events_created_at ON zoom_meeting_events(created_at);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_events_event_ts ON zoom_meeting_events(event_ts);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participant_states_meeting ON zoom_participant_states(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participant_states_user ON zoom_participant_states(user_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participant_states_status ON zoom_participant_states(status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participant_states_joined_at ON zoom_participant_states(joined_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_analytics_meeting ON zoom_realtime_analytics(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_analytics_type ON zoom_realtime_analytics(metric_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_analytics_timestamp ON zoom_realtime_analytics(timestamp);"
                ]
                
                for index_sql in indexes:
                    await conn.execute(index_sql)
                
                logger.info("Real-time event database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize real-time event database: {e}")
    
    async def start_processing(self, websocket_manager: ZoomWebSocketManager) -> None:
        """Start real-time event processing"""
        try:
            self.is_running = True
            self.websocket_manager = websocket_manager
            
            # Register event handlers
            await self._register_event_handlers()
            
            # Start background tasks
            self.background_tasks = [
                asyncio.create_task(self._event_processor()),
                asyncio.create_task(self._state_synchronizer()),
                asyncio.create_task(self._analytics_collector()),
                asyncio.create_task(self._cleanup_processor())
            ]
            
            logger.info("Real-time event handler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start real-time event handler: {e}")
            raise
    
    async def stop_processing(self) -> None:
        """Stop real-time event processing"""
        try:
            self.is_running = False
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Real-time event handler stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop real-time event handler: {e}")
    
    async def _register_event_handlers(self) -> None:
        """Register event handlers with WebSocket manager"""
        if not self.websocket_manager:
            return
        
        # Register meeting lifecycle events
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.MEETING_STARTED, self._handle_meeting_started
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.MEETING_ENDED, self._handle_meeting_ended
        )
        
        # Register participant events
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.PARTICIPANT_JOINED, self._handle_participant_joined
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.PARTICIPANT_LEFT, self._handle_participant_left
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.PARTICIPANT_STATUS_CHANGED, self._handle_participant_status_changed
        )
        
        # Register recording events
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.RECORDING_STARTED, self._handle_recording_started
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.RECORDING_STOPPED, self._handle_recording_stopped
        )
        
        # Register collaboration events
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.CHAT_MESSAGE, self._handle_chat_message
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.REACTION_ADDED, self._handle_reaction_added
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.SCREEN_SHARE_STARTED, self._handle_screen_share_started
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.SCREEN_SHARE_STOPPED, self._handle_screen_share_stopped
        )
        
        # Register meeting feature events
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.BREAKOUT_ROOM_CREATED, self._handle_breakout_room_created
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.POLL_STARTED, self._handle_poll_started
        )
        
        await self.websocket_manager.register_event_handler(
            WebSocketEvent.Q_A_SESSION_STARTED, self._handle_qa_session_started
        )
        
        logger.info("Event handlers registered successfully")
    
    async def handle_webhook_event(self, event_data: Dict[str, Any]) -> bool:
        """Handle incoming Zoom webhook event"""
        try:
            # Parse Zoom event
            zoom_event = ZoomMeetingEvent(
                event_id=event_data.get('event_ts') or f"{event_data['event']}_{datetime.now(timezone.utc).timestamp()}",
                event_type=event_data.get('event'),
                event_ts=event_data.get('event_ts', int(datetime.now(timezone.utc).timestamp())),
                meeting_id=event_data.get('meeting', {}).get('id', ''),
                account_id=event_data.get('object', {}).get('account_id', ''),
                user_id=event_data.get('object', {}).get('id', ''),
                participant=event_data.get('participant'),
                payload=event_data.get('payload', {}),
                signature=event_data.get('x-zm-signature'),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Check for duplicate events
            if self._is_duplicate_event(zoom_event.event_id):
                logger.debug(f"Ignoring duplicate event: {zoom_event.event_id}")
                return True
            
            # Add to processing queue
            await self.event_queue.put(zoom_event)
            
            # Track for deduplication
            self.processed_events[zoom_event.event_id] = zoom_event.timestamp
            
            logger.info(f"Queued Zoom webhook event: {zoom_event.event_type} for meeting {zoom_event.meeting_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle webhook event: {e}")
            return False
    
    def _is_duplicate_event(self, event_id: str) -> bool:
        """Check if event is duplicate"""
        if event_id in self.processed_events:
            time_diff = datetime.now(timezone.utc) - self.processed_events[event_id]
            return time_diff.total_seconds() < self.config['event_deduplication_window']
        return False
    
    async def _event_processor(self) -> None:
        """Process events from queue"""
        while self.is_running:
            try:
                # Get event from queue
                zoom_event = await asyncio.wait_for(
                    self.event_queue.get(), 
                    timeout=self.config['processing_interval']
                )
                
                start_time = datetime.now(timezone.utc)
                
                # Store event in database
                await self._store_event(zoom_event)
                
                # Process event
                await self._process_zoom_event(zoom_event)
                
                # Update statistics
                processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.stats['events_processed'] += 1
                self.stats['last_event_time'] = zoom_event.timestamp
                self.stats['average_processing_time'] = (
                    (self.stats['average_processing_time'] * (self.stats['events_processed'] - 1) + processing_time) /
                    self.stats['events_processed']
                )
                
                logger.debug(f"Processed event {zoom_event.event_type} in {processing_time:.3f}s")
                
            except asyncio.TimeoutError:
                # No events in queue
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                self.stats['events_failed'] += 1
    
    async def _process_zoom_event(self, zoom_event: ZoomMeetingEvent) -> None:
        """Process individual Zoom event"""
        try:
            # Map Zoom event to WebSocket event
            websocket_event = self._map_zoom_to_websocket_event(zoom_event)
            
            if websocket_event:
                # Create WebSocket message
                message = WebSocketMessage(
                    event_type=websocket_event,
                    data={
                        'zoom_event_type': zoom_event.event_type,
                        'zoom_event_id': zoom_event.event_id,
                        'meeting_id': zoom_event.meeting_id,
                        'account_id': zoom_event.account_id,
                        'user_id': zoom_event.user_id,
                        'participant': zoom_event.participant,
                        'payload': zoom_event.payload,
                        'timestamp': zoom_event.timestamp.isoformat()
                    },
                    timestamp=zoom_event.timestamp,
                    meeting_id=zoom_event.meeting_id,
                    user_id=zoom_event.user_id,
                    account_id=zoom_event.account_id,
                    correlation_id=zoom_event.event_id
                )
                
                # Broadcast to WebSocket subscribers
                await self.websocket_manager.broadcast_event(
                    message,
                    target_meeting_id=zoom_event.meeting_id
                )
                
                # Trigger specific handlers
                await self._trigger_event_handlers(zoom_event, message)
                
            # Update meeting and participant states
            await self._update_states(zoom_event)
            
            # Log processing
            await self._mark_event_processed(zoom_event.event_id)
            
        except Exception as e:
            logger.error(f"Failed to process Zoom event {zoom_event.event_id}: {e}")
            await self._mark_event_failed(zoom_event.event_id)
    
    def _map_zoom_to_websocket_event(self, zoom_event: ZoomMeetingEvent) -> Optional[WebSocketEvent]:
        """Map Zoom webhook event to WebSocket event"""
        event_mapping = {
            'meeting.started': WebSocketEvent.MEETING_STARTED,
            'meeting.ended': WebSocketEvent.MEETING_ENDED,
            'meeting.participant_joined': WebSocketEvent.PARTICIPANT_JOINED,
            'meeting.participant_left': WebSocketEvent.PARTICIPANT_LEFT,
            'meeting.participant_status_changed': WebSocketEvent.PARTICIPANT_STATUS_CHANGED,
            'meeting.recording_started': WebSocketEvent.RECORDING_STARTED,
            'meeting.recording_stopped': WebSocketEvent.RECORDING_STOPPED,
            'meeting.recording_completed': WebSocketEvent.RECORDING_PROCESSED,
            'meeting.chat_message': WebSocketEvent.CHAT_MESSAGE,
            'meeting.reaction_added': WebSocketEvent.REACTION_ADDED,
            'meeting.reaction_removed': WebSocketEvent.REACTION_REMOVED,
            'meeting.sharing_started': WebSocketEvent.SCREEN_SHARE_STARTED,
            'meeting.sharing_stopped': WebSocketEvent.SCREEN_SHARE_STOPPED,
            'meeting.breakout_room_created': WebSocketEvent.BREAKOUT_ROOM_CREATED,
            'meeting.breakout_room_updated': WebSocketEvent.BREAKOUT_ROOM_UPDATED,
            'meeting.poll_started': WebSocketEvent.POLL_STARTED,
            'meeting.poll_ended': WebSocketEvent.POLL_ENDED,
            'meeting.q_and_a_started': WebSocketEvent.Q_A_SESSION_STARTED,
            'meeting.q_and_a_ended': WebSocketEvent.Q_A_SESSION_ENDED,
            'meeting.co_host_assigned': WebSocketEvent.CO_HOST_ASSIGNED,
            'meeting.co_host_removed': WebSocketEvent.CO_HOST_REMOVED,
            'meeting.live_stream_started': WebSocketEvent.LIVE_STREAM_STARTED,
            'meeting.live_stream_stopped': WebSocketEvent.LIVE_STREAM_STOPPED,
            'meeting.waiting_room_user_joined': WebSocketEvent.WAITING_ROOM_USER_JOINED,
            'meeting.waiting_room_user_left': WebSocketEvent.WAITING_ROOM_USER_LEFT
        }
        
        return event_mapping.get(zoom_event.event_type)
    
    async def _trigger_event_handlers(self, zoom_event: ZoomMeetingEvent, message: WebSocketMessage) -> None:
        """Trigger specific event handlers"""
        try:
            # Get registered handlers for this event type
            websocket_event = self._map_zoom_to_websocket_event(zoom_event)
            if websocket_event:
                handlers = self.websocket_manager.event_handlers.get(websocket_event, [])
                
                # Call all registered handlers
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
        
        except Exception as e:
            logger.error(f"Failed to trigger event handlers: {e}")
    
    async def _update_states(self, zoom_event: ZoomMeetingEvent) -> None:
        """Update meeting and participant states"""
        try:
            # Update meeting state
            if zoom_event.event_type in ['meeting.started', 'meeting.ended']:
                await self._update_meeting_state(zoom_event)
            
            # Update participant state
            if zoom_event.event_type in [
                'meeting.participant_joined', 
                'meeting.participant_left',
                'meeting.participant_status_changed'
            ]:
                await self._update_participant_state(zoom_event)
            
            # Update recording state
            if zoom_event.event_type in ['meeting.recording_started', 'meeting.recording_stopped']:
                await self._update_recording_state(zoom_event)
            
            # Update collaboration state
            if zoom_event.event_type in [
                'meeting.sharing_started',
                'meeting.sharing_stopped'
            ]:
                await self._update_collaboration_state(zoom_event)
        
        except Exception as e:
            logger.error(f"Failed to update states: {e}")
    
    async def _update_meeting_state(self, zoom_event: ZoomMeetingEvent) -> None:
        """Update meeting state"""
        try:
            meeting_id = zoom_event.meeting_id
            
            if zoom_event.event_type == 'meeting.started':
                # Create or update meeting state
                meeting_state = MeetingState(
                    meeting_id=meeting_id,
                    topic=zoom_event.payload.get('topic', 'Untitled Meeting'),
                    host_id=zoom_event.user_id,
                    status='started',
                    start_time=zoom_event.timestamp,
                    participants={},
                    recording_status='none',
                    settings=zoom_event.payload.get('settings', {}),
                    metadata=zoom_event.payload,
                    created_at=zoom_event.timestamp,
                    updated_at=zoom_event.timestamp
                )
                
                self.meeting_states[meeting_id] = meeting_state
                
                # Update WebSocket manager
                await self.websocket_manager.update_meeting_state(meeting_id, asdict(meeting_state))
                
                self.stats['meetings_tracked'] += 1
                
            elif zoom_event.event_type == 'meeting.ended':
                # Update meeting state to ended
                if meeting_id in self.meeting_states:
                    self.meeting_states[meeting_id].status = 'ended'
                    self.meeting_states[meeting_id].updated_at = zoom_event.timestamp
                    
                    # Update WebSocket manager
                    await self.websocket_manager.update_meeting_state(
                        meeting_id, 
                        {'status': 'ended', 'updated_at': zoom_event.timestamp.isoformat()}
                    )
        
        except Exception as e:
            logger.error(f"Failed to update meeting state: {e}")
    
    async def _update_participant_state(self, zoom_event: ZoomMeetingEvent) -> None:
        """Update participant state"""
        try:
            participant = zoom_event.participant
            if not participant:
                return
            
            meeting_id = zoom_event.meeting_id
            participant_id = participant.get('id', participant.get('user_id'))
            
            if not participant_id:
                return
            
            participant_key = f"{meeting_id}_{participant_id}"
            
            if zoom_event.event_type == 'meeting.participant_joined':
                # Create participant state
                participant_state = {
                    'participant_id': participant_id,
                    'meeting_id': meeting_id,
                    'user_id': participant.get('id', participant.get('user_id')),
                    'account_id': zoom_event.account_id,
                    'name': participant.get('name', participant.get('display_name')),
                    'email': participant.get('email'),
                    'status': ParticipantStatus.IN_MEETING.value,
                    'joined_at': zoom_event.timestamp,
                    'left_at': None,
                    'is_host': participant.get('host', False),
                    'is_co_host': participant.get('co_host', False),
                    'audio_status': {
                        'muted': participant.get('muted', True),
                        'audio_on': participant.get('audio_on', False)
                    },
                    'video_status': {
                        'video_on': participant.get('video_on', False),
                        'screen_share_on': participant.get('screen_share_on', False)
                    },
                    'screen_share_status': {
                        'sharing': participant.get('screen_share_on', False)
                    },
                    'metadata': participant
                }
                
                self.participant_states[participant_key] = participant_state
                
                # Update meeting state
                if meeting_id in self.meeting_states:
                    self.meeting_states[meeting_id].participants[participant_id] = participant_state
                    self.meeting_states[meeting_id].updated_at = zoom_event.timestamp
                    
                    # Update WebSocket manager
                    await self.websocket_manager.update_meeting_state(
                        meeting_id,
                        {
                            'participants': self.meeting_states[meeting_id].participants,
                            'updated_at': zoom_event.timestamp.isoformat()
                        }
                    )
                
                # Store in database
                await self._store_participant_state(participant_state)
                
                self.stats['participants_tracked'] += 1
                
            elif zoom_event.event_type == 'meeting.participant_left':
                # Update participant state
                if participant_key in self.participant_states:
                    self.participant_states[participant_key]['status'] = ParticipantStatus.AWAY.value
                    self.participant_states[participant_key]['left_at'] = zoom_event.timestamp
                    
                    # Calculate duration
                    joined_at = self.participant_states[participant_key].get('joined_at')
                    if joined_at:
                        duration = (zoom_event.timestamp - joined_at).total_seconds()
                        self.participant_states[participant_key]['duration_seconds'] = int(duration)
                    
                    # Update meeting state
                    if meeting_id in self.meeting_states:
                        self.meeting_states[meeting_id].participants.pop(participant_id, None)
                        self.meeting_states[meeting_id].updated_at = zoom_event.timestamp
                        
                        # Update WebSocket manager
                        await self.websocket_manager.update_meeting_state(
                            meeting_id,
                            {
                                'participants': self.meeting_states[meeting_id].participants,
                                'updated_at': zoom_event.timestamp.isoformat()
                            }
                        )
                    
                    # Update in database
                    await self._update_participant_state(participant_key, {
                        'status': ParticipantStatus.AWAY.value,
                        'left_at': zoom_event.timestamp,
                        'duration_seconds': self.participant_states[participant_key].get('duration_seconds'),
                        'updated_at': zoom_event.timestamp
                    })
                    
                    # Remove from cache after some time
                    await asyncio.sleep(300)  # 5 minutes
                    self.participant_states.pop(participant_key, None)
                
            elif zoom_event.event_type == 'meeting.participant_status_changed':
                # Update participant status
                if participant_key in self.participant_states:
                    # Update specific fields
                    if 'muted' in participant:
                        self.participant_states[participant_key]['audio_status']['muted'] = participant['muted']
                    if 'audio_on' in participant:
                        self.participant_states[participant_key]['audio_status']['audio_on'] = participant['audio_on']
                    if 'video_on' in participant:
                        self.participant_states[participant_key]['video_status']['video_on'] = participant['video_on']
                    if 'screen_share_on' in participant:
                        self.participant_states[participant_key]['screen_share_status']['sharing'] = participant['screen_share_on']
                        self.participant_states[participant_key]['video_status']['screen_share_on'] = participant['screen_share_on']
                    
                    self.participant_states[participant_key]['updated_at'] = zoom_event.timestamp
                    
                    # Update in database
                    await self._update_participant_state(participant_key, {
                        'audio_status': self.participant_states[participant_key]['audio_status'],
                        'video_status': self.participant_states[participant_key]['video_status'],
                        'screen_share_status': self.participant_states[participant_key]['screen_share_status'],
                        'updated_at': zoom_event.timestamp
                    })
        
        except Exception as e:
            logger.error(f"Failed to update participant state: {e}")
    
    async def _store_event(self, zoom_event: ZoomMeetingEvent) -> None:
        """Store event in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_meeting_events (
                        event_id, event_type, event_ts, meeting_id, account_id,
                        user_id, participant, payload, signature, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (event_id) DO NOTHING
                """,
                zoom_event.event_id, zoom_event.event_type, zoom_event.event_ts,
                zoom_event.meeting_id, zoom_event.account_id, zoom_event.user_id,
                json.dumps(zoom_event.participant) if zoom_event.participant else None,
                json.dumps(zoom_event.payload), zoom_event.signature, zoom_event.timestamp
                )
        
        except Exception as e:
            logger.error(f"Failed to store event: {e}")
    
    async def _store_participant_state(self, participant_state: Dict[str, Any]) -> None:
        """Store participant state in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_participant_states (
                        participant_id, meeting_id, user_id, account_id,
                        status, joined_at, left_at, is_host, is_co_host,
                        audio_status, video_status, screen_share_status,
                        metadata, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (participant_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        left_at = EXCLUDED.left_at,
                        duration_seconds = EXCLUDED.duration_seconds,
                        audio_status = EXCLUDED.audio_status,
                        video_status = EXCLUDED.video_status,
                        screen_share_status = EXCLUDED.screen_share_status,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                """,
                participant_state['participant_id'],
                participant_state['meeting_id'],
                participant_state['user_id'],
                participant_state['account_id'],
                participant_state['status'],
                participant_state['joined_at'],
                participant_state['left_at'],
                participant_state['is_host'],
                participant_state['is_co_host'],
                json.dumps(participant_state['audio_status']),
                json.dumps(participant_state['video_status']),
                json.dumps(participant_state['screen_share_status']),
                json.dumps(participant_state['metadata']),
                participant_state['joined_at'],
                participant_state['updated_at']
                )
        
        except Exception as e:
            logger.error(f"Failed to store participant state: {e}")
    
    async def _update_participant_state(self, participant_key: str, updates: Dict[str, Any]) -> None:
        """Update participant state in database"""
        if not self.db_pool:
            return
        
        try:
            participant_id = participant_key.split('_')[-1]
            
            async with self.db_pool.acquire() as conn:
                # Build update query
                set_clauses = []
                values = []
                param_index = 1
                
                for field, value in updates.items():
                    if field in ['status', 'left_at', 'duration_seconds', 'audio_status', 'video_status', 'screen_share_status']:
                        if isinstance(value, dict):
                            set_clauses.append(f"{field} = ${param_index}")
                            values.append(json.dumps(value))
                        else:
                            set_clauses.append(f"{field} = ${param_index}")
                            values.append(value)
                        param_index += 1
                
                values.append(participant_id)
                
                if set_clauses:
                    await conn.execute(f"""
                        UPDATE zoom_participant_states 
                        SET {', '.join(set_clauses)}, updated_at = NOW()
                        WHERE participant_id = ${param_index}
                    """, *values)
        
        except Exception as e:
            logger.error(f"Failed to update participant state: {e}")
    
    async def _mark_event_processed(self, event_id: str) -> None:
        """Mark event as processed in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_meeting_events 
                    SET processed = true, processed_at = NOW()
                    WHERE event_id = $1
                """, event_id)
        
        except Exception as e:
            logger.error(f"Failed to mark event as processed: {e}")
    
    async def _mark_event_failed(self, event_id: str) -> None:
        """Mark event as failed in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_meeting_events 
                    SET processed = false, retry_count = retry_count + 1, processed_at = NOW()
                    WHERE event_id = $1
                """, event_id)
        
        except Exception as e:
            logger.error(f"Failed to mark event as failed: {e}")
    
    # WebSocket Event Handlers
    async def _handle_meeting_started(self, message: WebSocketMessage) -> None:
        """Handle meeting started event"""
        logger.info(f"Meeting started: {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_meeting_ended(self, message: WebSocketMessage) -> None:
        """Handle meeting ended event"""
        logger.info(f"Meeting ended: {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_participant_joined(self, message: WebSocketMessage) -> None:
        """Handle participant joined event"""
        logger.info(f"Participant joined meeting {message.meeting_id}: {message.user_id}")
        # Additional custom logic can be added here
    
    async def _handle_participant_left(self, message: WebSocketMessage) -> None:
        """Handle participant left event"""
        logger.info(f"Participant left meeting {message.meeting_id}: {message.user_id}")
        # Additional custom logic can be added here
    
    async def _handle_participant_status_changed(self, message: WebSocketMessage) -> None:
        """Handle participant status changed event"""
        logger.info(f"Participant status changed in meeting {message.meeting_id}: {message.user_id}")
        # Additional custom logic can be added here
    
    async def _handle_recording_started(self, message: WebSocketMessage) -> None:
        """Handle recording started event"""
        logger.info(f"Recording started for meeting: {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_recording_stopped(self, message: WebSocketMessage) -> None:
        """Handle recording stopped event"""
        logger.info(f"Recording stopped for meeting: {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_chat_message(self, message: WebSocketMessage) -> None:
        """Handle chat message event"""
        logger.info(f"Chat message in meeting {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_reaction_added(self, message: WebSocketMessage) -> None:
        """Handle reaction added event"""
        logger.info(f"Reaction added in meeting {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_screen_share_started(self, message: WebSocketMessage) -> None:
        """Handle screen share started event"""
        logger.info(f"Screen share started in meeting {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_screen_share_stopped(self, message: WebSocketMessage) -> None:
        """Handle screen share stopped event"""
        logger.info(f"Screen share stopped in meeting {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_breakout_room_created(self, message: WebSocketMessage) -> None:
        """Handle breakout room created event"""
        logger.info(f"Breakout room created in meeting {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_poll_started(self, message: WebSocketMessage) -> None:
        """Handle poll started event"""
        logger.info(f"Poll started in meeting {message.meeting_id}")
        # Additional custom logic can be added here
    
    async def _handle_qa_session_started(self, message: WebSocketMessage) -> None:
        """Handle Q&A session started event"""
        logger.info(f"Q&A session started in meeting {message.meeting_id}")
        # Additional custom logic can be added here
    
    # Background Tasks
    async def _state_synchronizer(self) -> None:
        """Synchronize states with database"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config['state_sync_interval'])
                
                # Sync meeting states to database
                await self._sync_meeting_states()
                
                # Clean up old events from memory
                await self._cleanup_processed_events()
                
            except Exception as e:
                logger.error(f"Error in state synchronizer: {e}")
    
    async def _analytics_collector(self) -> None:
        """Collect and store analytics"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Collect analytics every minute
                
                # Calculate metrics
                current_time = datetime.now(timezone.utc)
                processing_rate = self.stats['events_processed'] / max(
                    ((current_time - current_time.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()) / 60, 1
                )
                
                # Store analytics
                await self._store_analytics('event_processing_rate', processing_rate)
                await self._store_analytics('active_meetings', len(self.meeting_states))
                await self._store_analytics('active_participants', len(self.participant_states))
                
            except Exception as e:
                logger.error(f"Error in analytics collector: {e}")
    
    async def _cleanup_processor(self) -> None:
        """Clean up old data"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Cleanup every hour
                
                # Clean up old events from database
                await self._cleanup_old_events()
                
                # Clean up old analytics from database
                await self._cleanup_old_analytics()
                
            except Exception as e:
                logger.error(f"Error in cleanup processor: {e}")
    
    async def _sync_meeting_states(self) -> None:
        """Synchronize meeting states with database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                for meeting_id, meeting_state in self.meeting_states.items():
                    await conn.execute("""
                        INSERT INTO zoom_meeting_states (
                            meeting_id, topic, host_id, status, start_time,
                            participants, recording_status, settings, metadata,
                            created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (meeting_id) DO UPDATE SET
                            status = EXCLUDED.status,
                            participants = EXCLUDED.participants,
                            recording_status = EXCLUDED.recording_status,
                            settings = EXCLUDED.settings,
                            metadata = EXCLUDED.metadata,
                            updated_at = EXCLUDED.updated_at
                    """,
                    meeting_id, meeting_state.topic, meeting_state.host_id,
                    meeting_state.status, meeting_state.start_time,
                    json.dumps(meeting_state.participants), meeting_state.recording_status,
                    json.dumps(meeting_state.settings), json.dumps(meeting_state.metadata),
                    meeting_state.created_at, meeting_state.updated_at
                    )
        
        except Exception as e:
            logger.error(f"Failed to sync meeting states: {e}")
    
    async def _store_analytics(self, metric_type: str, metric_value: float, metric_data: Dict[str, Any] = None) -> None:
        """Store analytics data"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                analytics_id = f"{metric_type}_{datetime.now(timezone.utc).timestamp()}"
                
                await conn.execute("""
                    INSERT INTO zoom_realtime_analytics (
                        analytics_id, metric_type, metric_value, metric_data, timestamp
                    ) VALUES ($1, $2, $3, $4, $5)
                """,
                analytics_id, metric_type, metric_value, 
                json.dumps(metric_data or {}), datetime.now(timezone.utc)
                )
        
        except Exception as e:
            logger.error(f"Failed to store analytics: {e}")
    
    async def _cleanup_processed_events(self) -> None:
        """Clean up old processed events from memory"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            # Remove events older than cutoff time
            to_remove = [
                event_id for event_id, timestamp in self.processed_events.items()
                if timestamp < cutoff_time
            ]
            
            for event_id in to_remove:
                del self.processed_events[event_id]
            
            logger.debug(f"Cleaned up {len(to_remove)} processed events from memory")
        
        except Exception as e:
            logger.error(f"Failed to cleanup processed events: {e}")
    
    async def _cleanup_old_events(self) -> None:
        """Clean up old events from database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.config['event_retention_hours'])
                
                result = await conn.execute("""
                    DELETE FROM zoom_meeting_events 
                    WHERE created_at < $1
                """, cutoff_time)
                
                # Extract count from result
                count = 0
                if result:
                    count_str = result.split(' ')[-1]
                    try:
                        count = int(count_str)
                    except ValueError:
                        count = 0
                
                if count > 0:
                    logger.info(f"Cleaned up {count} old events from database")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")
    
    async def _cleanup_old_analytics(self) -> None:
        """Clean up old analytics from database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)  # Keep 7 days
                
                result = await conn.execute("""
                    DELETE FROM zoom_realtime_analytics 
                    WHERE timestamp < $1
                """, cutoff_time)
                
                # Extract count from result
                count = 0
                if result:
                    count_str = result.split(' ')[-1]
                    try:
                        count = int(count_str)
                    except ValueError:
                        count = 0
                
                if count > 0:
                    logger.info(f"Cleaned up {count} old analytics from database")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old analytics: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self.stats.copy()
    
    def get_meeting_state(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get current meeting state"""
        meeting_state = self.meeting_states.get(meeting_id)
        if meeting_state:
            return asdict(meeting_state)
        return None
    
    def get_participant_state(self, meeting_id: str, participant_id: str) -> Optional[Dict[str, Any]]:
        """Get current participant state"""
        participant_key = f"{meeting_id}_{participant_id}"
        return self.participant_states.get(participant_key)
    
    async def create_custom_event(self, event_type: str, data: Dict[str, Any], 
                                 meeting_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
        """Create and broadcast custom event"""
        try:
            # Create WebSocket message
            message = WebSocketMessage(
                event_type=WebSocketEvent.USER_STATUS_CHANGED,  # Use generic event type for custom events
                data={
                    'type': 'custom_event',
                    'custom_event_type': event_type,
                    'custom_data': data
                },
                timestamp=datetime.now(timezone.utc),
                meeting_id=meeting_id,
                user_id=user_id,
                correlation_id=f"custom_{datetime.now(timezone.utc).timestamp()}_{secrets.token_hex(8)}"
            )
            
            # Broadcast event
            sent_count = await self.websocket_manager.broadcast_event(
                message,
                target_meeting_id=meeting_id
            )
            
            logger.info(f"Created custom event {event_type} sent to {sent_count} connections")
            return message.correlation_id
            
        except Exception as e:
            logger.error(f"Failed to create custom event: {e}")
            return ""