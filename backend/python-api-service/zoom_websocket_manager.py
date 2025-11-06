"""
🔄 Zoom WebSocket Manager
Real-time WebSocket integration for live Zoom events and updates
"""

import os
import json
import logging
import asyncio
import websockets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque

import asyncpg
import redis.asyncio as redis
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class WebSocketEvent(Enum):
    """WebSocket event types"""
    MEETING_STARTED = "meeting_started"
    MEETING_ENDED = "meeting_ended"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    PARTICIPANT_STATUS_CHANGED = "participant_status_changed"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_PROCESSED = "recording_processed"
    CHAT_MESSAGE = "chat_message"
    REACTION_ADDED = "reaction_added"
    REACTION_REMOVED = "reaction_removed"
    SCREEN_SHARE_STARTED = "screen_share_started"
    SCREEN_SHARE_STOPPED = "screen_share_stopped"
    BREAKOUT_ROOM_CREATED = "breakout_room_created"
    BREAKOUT_ROOM_UPDATED = "breakout_room_updated"
    POLL_STARTED = "poll_started"
    POLL_ENDED = "poll_ended"
    Q_A_SESSION_STARTED = "q_a_session_started"
    Q_A_SESSION_ENDED = "q_a_session_ended"
    USER_STATUS_CHANGED = "user_status_changed"
    MEETING_SETTINGS_CHANGED = "meeting_settings_changed"
    LIVE_STREAM_STARTED = "live_stream_started"
    LIVE_STREAM_STOPPED = "live_stream_stopped"
    CO_HOST_ASSIGNED = "co_host_assigned"
    CO_HOST_REMOVED = "co_host_removed"
    WAITING_ROOM_USER_JOINED = "waiting_room_user_joined"
    WAITING_ROOM_USER_LEFT = "waiting_room_user_left"

class ConnectionStatus(Enum):
    """WebSocket connection status"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RECONNECTING = "reconnecting"

class ParticipantStatus(Enum):
    """Participant status"""
    IN_MEETING = "in_meeting"
    WAITING_ROOM = "waiting_room"
    AWAY = "away"
    ON_HOLD = "on_hold"
    IN_BREAKOUT_ROOM = "in_breakout_room"

@dataclass
class WebSocketMessage:
    """WebSocket message structure"""
    event_type: WebSocketEvent
    data: Dict[str, Any]
    timestamp: datetime
    meeting_id: Optional[str] = None
    user_id: Optional[str] = None
    account_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class WebSocketConnection:
    """WebSocket connection information"""
    connection_id: str
    user_id: str
    account_id: str
    websocket: Any
    status: ConnectionStatus
    connected_at: datetime
    last_ping: datetime
    subscribed_meetings: Set[str]
    subscribed_events: Set[WebSocketEvent]
    metadata: Dict[str, Any]
    message_count: int = 0
    error_count: int = 0

@dataclass
class MeetingState:
    """Current meeting state"""
    meeting_id: str
    topic: str
    host_id: str
    status: str
    start_time: datetime
    participants: Dict[str, Dict[str, Any]]
    recording_status: str
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

@dataclass
class RealTimeEvent:
    """Real-time event data"""
    event_id: str
    event_type: WebSocketEvent
    source: str
    timestamp: datetime
    user_id: Optional[str] = None
    meeting_id: Optional[str] = None
    account_id: Optional[str] = None
    data: Dict[str, Any] = None
    processed: bool = False
    retry_count: int = 0

class ZoomWebSocketManager:
    """Enterprise-grade Zoom WebSocket manager"""
    
    def __init__(self, db_pool: asyncpg.Pool, redis_url: Optional[str] = None, encryption_key: Optional[str] = None):
        self.db_pool = db_pool
        self.redis_url = redis_url
        self.encryption_key = encryption_key
        
        # Initialize encryption
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            self.fernet = Fernet(os.getenv('ENCRYPTION_KEY', Fernet.generate_key()).encode())
        
        # Connection management
        self.connections: Dict[str, WebSocketConnection] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)
        self.meeting_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self.event_handlers: Dict[WebSocketEvent, List[Callable]] = defaultdict(list)
        
        # State management
        self.meeting_states: Dict[str, MeetingState] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.connection_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Redis for distributed WebSocket management
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
        # WebSocket server
        self.websocket_server: Optional[Any] = None
        
        # Configuration
        self.config = {
            'max_connections': 10000,
            'ping_interval': 30,
            'ping_timeout': 10,
            'message_queue_size': 10000,
            'connection_queue_size': 1000,
            'reconnect_attempts': 5,
            'reconnect_delay': 5,
            'event_retention_hours': 24,
            'state_sync_interval': 30,
            'distributed_mode': bool(redis_url)
        }
        
        # Performance metrics
        self.metrics = {
            'total_connections': 0,
            'active_connections': 0,
            'total_messages': 0,
            'total_events': 0,
            'failed_connections': 0,
            'average_message_time': 0,
            'connection_uptime': 0,
            'event_processing_rate': 0,
            'memory_usage': 0,
            'cpu_usage': 0
        }
        
        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()
        self.is_running = False
        
        # Initialize components
        asyncio.create_task(self._init_components())
    
    async def _init_components(self) -> None:
        """Initialize WebSocket components"""
        try:
            # Initialize database tables
            await self._init_database()
            
            # Initialize Redis if in distributed mode
            if self.redis_url:
                await self._init_redis()
            
            # Load existing meeting states
            await self._load_meeting_states()
            
            logger.info("Zoom WebSocket manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Zoom WebSocket manager: {e}")
            raise
    
    async def _init_database(self) -> None:
        """Initialize WebSocket database tables"""
        if not self.db_pool:
            logger.warning("Database pool not available for WebSocket state management")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create websockets connections table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_websocket_connections (
                        connection_id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        account_id VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        connected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        last_ping TIMESTAMP WITH TIME ZONE,
                        last_message TIMESTAMP WITH TIME ZONE,
                        message_count INTEGER DEFAULT 0,
                        error_count INTEGER DEFAULT 0,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create real-time events table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_realtime_events (
                        event_id VARCHAR(255) PRIMARY KEY,
                        event_type VARCHAR(100) NOT NULL,
                        source VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255),
                        meeting_id VARCHAR(255),
                        account_id VARCHAR(255),
                        data JSONB DEFAULT '{}'::jsonb,
                        processed BOOLEAN DEFAULT false,
                        retry_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        processed_at TIMESTAMP WITH TIME ZONE
                    );
                """)
                
                # Create meeting states table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_meeting_states (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        topic VARCHAR(255) NOT NULL,
                        host_id VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        start_time TIMESTAMP WITH TIME ZONE,
                        participants JSONB DEFAULT '{}'::jsonb,
                        recording_status VARCHAR(50) DEFAULT 'none',
                        settings JSONB DEFAULT '{}'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_zoom_websocket_connections_user_id ON zoom_websocket_connections(user_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_websocket_connections_status ON zoom_websocket_connections(status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_websocket_connections_connected_at ON zoom_websocket_connections(connected_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_events_type ON zoom_realtime_events(event_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_events_meeting_id ON zoom_realtime_events(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_events_user_id ON zoom_realtime_events(user_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_events_processed ON zoom_realtime_events(processed);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_realtime_events_created_at ON zoom_realtime_events(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_states_status ON zoom_meeting_states(status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_states_host_id ON zoom_meeting_states(host_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_states_updated_at ON zoom_meeting_states(updated_at);"
                ]
                
                for index_sql in indexes:
                    await conn.execute(index_sql)
                
                logger.info("WebSocket database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket database: {e}")
    
    async def _init_redis(self) -> None:
        """Initialize Redis for distributed WebSocket management"""
        try:
            self.redis = redis.from_url(self.redis_url)
            self.pubsub = self.redis.pubsub()
            
            # Subscribe to WebSocket channels
            await self.pubsub.subscribe("zoom_websocket_events")
            await self.pubsub.subscribe("zoom_meeting_state_updates")
            await self.pubsub.subscribe("zoom_connection_management")
            
            logger.info("Redis initialized for distributed WebSocket management")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.config['distributed_mode'] = False
    
    async def _load_meeting_states(self) -> None:
        """Load existing meeting states from database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT meeting_id, topic, host_id, status, start_time,
                           participants, recording_status, settings, metadata,
                           created_at, updated_at
                    FROM zoom_meeting_states
                    WHERE status IN ('started', 'waiting')
                """)
                
                for row in rows:
                    meeting_state = MeetingState(
                        meeting_id=row['meeting_id'],
                        topic=row['topic'],
                        host_id=row['host_id'],
                        status=row['status'],
                        start_time=row['start_time'],
                        participants=json.loads(row['participants']) if row['participants'] else {},
                        recording_status=row['recording_status'],
                        settings=json.loads(row['settings']) if row['settings'] else {},
                        metadata=json.loads(row['metadata']) if row['metadata'] else {},
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    
                    self.meeting_states[row['meeting_id']] = meeting_state
                
                logger.info(f"Loaded {len(self.meeting_states)} meeting states from database")
                
        except Exception as e:
            logger.error(f"Failed to load meeting states: {e}")
    
    def generate_connection_id(self, user_id: str) -> str:
        """Generate unique connection ID"""
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        random_part = secrets.token_hex(16)
        connection_id = f"{user_id}_{timestamp}_{random_part}"
        return hashlib.sha256(connection_id.encode()).hexdigest()[:32]
    
    async def register_event_handler(self, event_type: WebSocketEvent, handler: Callable) -> None:
        """Register event handler for specific event type"""
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered event handler for {event_type.value}")
    
    async def unregister_event_handler(self, event_type: WebSocketEvent, handler: Callable) -> None:
        """Unregister event handler for specific event type"""
        if handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
            logger.info(f"Unregistered event handler for {event_type.value}")
    
    async def start_websocket_server(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """Start WebSocket server"""
        try:
            self.is_running = True
            
            # Start background tasks
            self.background_tasks.add(asyncio.create_task(self._connection_handler()))
            self.background_tasks.add(asyncio.create_task(self._event_processor()))
            self.background_tasks.add(asyncio.create_task(self._state_synchronizer()))
            self.background_tasks.add(asyncio.create_task(self._redis_listener()))
            self.background_tasks.add(asyncio.create_task(self._metrics_collector()))
            
            # Start WebSocket server
            logger.info(f"Starting Zoom WebSocket server on {host}:{port}")
            
            async with websockets.serve(self._websocket_handler, host, port) as server:
                self.websocket_server = server
                await server.wait_closed()
                
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def stop_websocket_server(self) -> None:
        """Stop WebSocket server"""
        try:
            self.is_running = False
            
            # Close all connections
            for connection in list(self.connections.values()):
                await self._close_connection(connection.connection_id, "Server shutting down")
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Close Redis connection
            if self.redis:
                await self.redis.close()
            
            # Close WebSocket server
            if self.websocket_server:
                self.websocket_server.close()
                await self.websocket_server.wait_closed()
            
            logger.info("Zoom WebSocket server stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop WebSocket server: {e}")
    
    async def _websocket_handler(self, websocket, path: str) -> None:
        """Handle WebSocket connections"""
        connection_id = None
        
        try:
            # Parse connection parameters from path
            path_parts = path.strip('/').split('/')
            if len(path_parts) >= 2:
                user_id, account_id = path_parts[0], path_parts[1]
                connection_id = self.generate_connection_id(user_id)
                
                # Create connection object
                connection = WebSocketConnection(
                    connection_id=connection_id,
                    user_id=user_id,
                    account_id=account_id,
                    websocket=websocket,
                    status=ConnectionStatus.CONNECTED,
                    connected_at=datetime.now(timezone.utc),
                    last_ping=datetime.now(timezone.utc),
                    subscribed_meetings=set(),
                    subscribed_events=set(),
                    metadata={'path': path, 'remote_address': websocket.remote_address}
                )
                
                # Add to connection management
                self.connections[connection_id] = connection
                self.user_connections[user_id].add(connection_id)
                
                # Store in database
                await self._store_connection(connection)
                
                # Send welcome message
                welcome_message = WebSocketMessage(
                    event_type=WebSocketEvent.USER_STATUS_CHANGED,
                    data={
                        'status': 'connected',
                        'connection_id': connection_id,
                        'server_time': datetime.now(timezone.utc).isoformat()
                    },
                    timestamp=datetime.now(timezone.utc),
                    user_id=user_id,
                    account_id=account_id,
                    session_id=connection_id
                )
                
                await self._send_message(connection_id, welcome_message)
                
                # Update metrics
                self.metrics['total_connections'] += 1
                self.metrics['active_connections'] = len(self.connections)
                
                logger.info(f"WebSocket connection established: {connection_id} for user {user_id}")
                
                # Handle messages
                async for message in websocket:
                    await self._handle_websocket_message(connection_id, message)
            
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed: {connection_id}")
        except Exception as e:
            logger.error(f"WebSocket error for connection {connection_id}: {e}")
        finally:
            if connection_id:
                await self._cleanup_connection(connection_id)
    
    async def _handle_websocket_message(self, connection_id: str, message: str) -> None:
        """Handle incoming WebSocket message"""
        try:
            connection = self.connections.get(connection_id)
            if not connection:
                return
            
            # Parse message
            message_data = json.loads(message)
            
            # Update message count and last message time
            connection.message_count += 1
            connection.last_ping = datetime.now(timezone.utc)
            
            # Handle different message types
            message_type = message_data.get('type')
            
            if message_type == 'subscribe':
                await self._handle_subscription(connection_id, message_data)
            elif message_type == 'unsubscribe':
                await self._handle_unsubscription(connection_id, message_data)
            elif message_type == 'ping':
                await self._handle_ping(connection_id, message_data)
            elif message_type == 'get_meeting_state':
                await self._handle_get_meeting_state(connection_id, message_data)
            elif message_type == 'get_user_status':
                await self._handle_get_user_status(connection_id, message_data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
            
            # Update metrics
            self.metrics['total_messages'] += 1
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message from connection {connection_id}: {e}")
            await self._send_error(connection_id, "Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self._send_error(connection_id, "Internal server error")
    
    async def _handle_subscription(self, connection_id: str, message_data: Dict[str, Any]) -> None:
        """Handle subscription message"""
        try:
            connection = self.connections[connection_id]
            
            # Subscribe to meetings
            meetings = message_data.get('meetings', [])
            for meeting_id in meetings:
                connection.subscribed_meetings.add(meeting_id)
                self.meeting_subscribers[meeting_id].add(connection_id)
            
            # Subscribe to events
            events = message_data.get('events', [])
            for event_name in events:
                try:
                    event_type = WebSocketEvent(event_name)
                    connection.subscribed_events.add(event_type)
                except ValueError:
                    logger.warning(f"Unknown event type: {event_name}")
            
            # Send subscription confirmation
            subscription_message = WebSocketMessage(
                event_type=WebSocketEvent.USER_STATUS_CHANGED,
                data={
                    'type': 'subscription_confirmed',
                    'meetings': list(connection.subscribed_meetings),
                    'events': [e.value for e in connection.subscribed_events]
                },
                timestamp=datetime.now(timezone.utc),
                user_id=connection.user_id,
                account_id=connection.account_id,
                session_id=connection_id
            )
            
            await self._send_message(connection_id, subscription_message)
            
            logger.info(f"Connection {connection_id} subscribed to {len(meetings)} meetings and {len(events)} events")
            
        except Exception as e:
            logger.error(f"Error handling subscription: {e}")
            await self._send_error(connection_id, "Subscription failed")
    
    async def _handle_unsubscription(self, connection_id: str, message_data: Dict[str, Any]) -> None:
        """Handle unsubscription message"""
        try:
            connection = self.connections[connection_id]
            
            # Unsubscribe from meetings
            meetings = message_data.get('meetings', [])
            for meeting_id in meetings:
                connection.subscribed_meetings.discard(meeting_id)
                self.meeting_subscribers[meeting_id].discard(connection_id)
            
            # Unsubscribe from events
            events = message_data.get('events', [])
            for event_name in events:
                try:
                    event_type = WebSocketEvent(event_name)
                    connection.subscribed_events.discard(event_type)
                except ValueError:
                    logger.warning(f"Unknown event type: {event_name}")
            
            # Send unsubscription confirmation
            unsubscription_message = WebSocketMessage(
                event_type=WebSocketEvent.USER_STATUS_CHANGED,
                data={
                    'type': 'unsubscription_confirmed',
                    'meetings': list(connection.subscribed_meetings),
                    'events': [e.value for e in connection.subscribed_events]
                },
                timestamp=datetime.now(timezone.utc),
                user_id=connection.user_id,
                account_id=connection.account_id,
                session_id=connection_id
            )
            
            await self._send_message(connection_id, unsubscription_message)
            
            logger.info(f"Connection {connection_id} unsubscribed from {len(meetings)} meetings and {len(events)} events")
            
        except Exception as e:
            logger.error(f"Error handling unsubscription: {e}")
            await self._send_error(connection_id, "Unsubscription failed")
    
    async def _handle_ping(self, connection_id: str, message_data: Dict[str, Any]) -> None:
        """Handle ping message"""
        try:
            connection = self.connections[connection_id]
            connection.last_ping = datetime.now(timezone.utc)
            
            # Send pong response
            pong_message = WebSocketMessage(
                event_type=WebSocketEvent.USER_STATUS_CHANGED,
                data={
                    'type': 'pong',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'latency': (datetime.now(timezone.utc) - connection.last_ping).total_seconds()
                },
                timestamp=datetime.now(timezone.utc),
                user_id=connection.user_id,
                account_id=connection.account_id,
                session_id=connection_id
            )
            
            await self._send_message(connection_id, pong_message)
            
        except Exception as e:
            logger.error(f"Error handling ping: {e}")
    
    async def _handle_get_meeting_state(self, connection_id: str, message_data: Dict[str, Any]) -> None:
        """Handle get meeting state request"""
        try:
            meeting_id = message_data.get('meeting_id')
            
            if not meeting_id:
                await self._send_error(connection_id, "Meeting ID is required")
                return
            
            meeting_state = self.meeting_states.get(meeting_id)
            
            if meeting_state:
                state_message = WebSocketMessage(
                    event_type=WebSocketEvent.MEETING_SETTINGS_CHANGED,
                    data={
                        'type': 'meeting_state_response',
                        'meeting_state': asdict(meeting_state)
                    },
                    timestamp=datetime.now(timezone.utc),
                    meeting_id=meeting_id,
                    user_id=self.connections[connection_id].user_id,
                    account_id=self.connections[connection_id].account_id,
                    session_id=connection_id
                )
                
                await self._send_message(connection_id, state_message)
            else:
                await self._send_error(connection_id, "Meeting state not found")
            
        except Exception as e:
            logger.error(f"Error handling get meeting state: {e}")
            await self._send_error(connection_id, "Failed to get meeting state")
    
    async def _handle_get_user_status(self, connection_id: str, message_data: Dict[str, Any]) -> None:
        """Handle get user status request"""
        try:
            target_user_id = message_data.get('user_id')
            
            if not target_user_id:
                await self._send_error(connection_id, "User ID is required")
                return
            
            # Check if user is connected
            user_connection_ids = self.user_connections.get(target_user_id, set())
            user_connections = [self.connections[cid] for cid in user_connection_ids if cid in self.connections]
            
            status_message = WebSocketMessage(
                event_type=WebSocketEvent.USER_STATUS_CHANGED,
                data={
                    'type': 'user_status_response',
                    'user_id': target_user_id,
                    'is_online': len(user_connections) > 0,
                    'connection_count': len(user_connections),
                    'connections': [
                        {
                            'connection_id': conn.connection_id,
                            'connected_at': conn.connected_at.isoformat(),
                            'last_ping': conn.last_ping.isoformat()
                        }
                        for conn in user_connections
                    ]
                },
                timestamp=datetime.now(timezone.utc),
                user_id=target_user_id,
                session_id=connection_id
            )
            
            await self._send_message(connection_id, status_message)
            
        except Exception as e:
            logger.error(f"Error handling get user status: {e}")
            await self._send_error(connection_id, "Failed to get user status")
    
    async def _send_message(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Send message to WebSocket connection"""
        try:
            connection = self.connections.get(connection_id)
            if not connection or connection.status != ConnectionStatus.CONNECTED:
                return False
            
            # Serialize message
            message_data = {
                'event_type': message.event_type.value,
                'data': message.data,
                'timestamp': message.timestamp.isoformat(),
                'meeting_id': message.meeting_id,
                'user_id': message.user_id,
                'account_id': message.account_id,
                'session_id': message.session_id,
                'correlation_id': message.correlation_id,
                'metadata': message.metadata
            }
            
            # Send message
            await connection.websocket.send(json.dumps(message_data))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to connection {connection_id}: {e}")
            connection.error_count += 1
            return False
    
    async def _send_error(self, connection_id: str, error_message: str) -> None:
        """Send error message to WebSocket connection"""
        try:
            error_data = {
                'type': 'error',
                'message': error_message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            connection = self.connections.get(connection_id)
            if connection:
                await connection.websocket.send(json.dumps(error_data))
            
        except Exception as e:
            logger.error(f"Failed to send error message to connection {connection_id}: {e}")
    
    async def broadcast_event(self, event: WebSocketMessage, target_meeting_id: Optional[str] = None, target_user_ids: Optional[List[str]] = None) -> int:
        """Broadcast event to subscribed connections"""
        sent_count = 0
        
        try:
            # Determine target connections
            target_connections = set()
            
            if target_meeting_id:
                # Send to meeting subscribers
                target_connections.update(self.meeting_subscribers.get(target_meeting_id, set()))
            
            if target_user_ids:
                # Send to specific users
                for user_id in target_user_ids:
                    target_connections.update(self.user_connections.get(user_id, set()))
            
            # Send to all subscribers of this event type
            for connection_id, connection in self.connections.items():
                if (connection.status == ConnectionStatus.CONNECTED and 
                    connection_id not in target_connections and
                    event.event_type in connection.subscribed_events):
                    target_connections.add(connection_id)
            
            # Send event to target connections
            for connection_id in target_connections:
                if await self._send_message(connection_id, event):
                    sent_count += 1
            
            # Add to Redis for distributed broadcasting
            if self.redis and self.config['distributed_mode']:
                event_data = json.dumps({
                    'event_type': event.event_type.value,
                    'data': event.data,
                    'timestamp': event.timestamp.isoformat(),
                    'meeting_id': event.meeting_id,
                    'user_id': event.user_id,
                    'account_id': event.account_id,
                    'session_id': event.session_id,
                    'correlation_id': event.correlation_id,
                    'metadata': event.metadata,
                    'target_meeting_id': target_meeting_id,
                    'target_user_ids': target_user_ids
                })
                
                await self.redis.publish("zoom_websocket_events", event_data)
            
            # Store event in database
            await self._store_event(event)
            
            # Update metrics
            self.metrics['total_events'] += 1
            
            logger.info(f"Broadcasted event {event.event_type.value} to {sent_count} connections")
            
            return sent_count
            
        except Exception as e:
            logger.error(f"Failed to broadcast event: {e}")
            return 0
    
    async def update_meeting_state(self, meeting_id: str, updates: Dict[str, Any]) -> None:
        """Update meeting state and notify subscribers"""
        try:
            # Get current meeting state
            meeting_state = self.meeting_states.get(meeting_id)
            
            if meeting_state:
                # Update meeting state
                for key, value in updates.items():
                    if hasattr(meeting_state, key):
                        setattr(meeting_state, key, value)
                
                meeting_state.updated_at = datetime.now(timezone.utc)
                
                # Update in database
                await self._update_meeting_state_db(meeting_state)
                
                # Broadcast state change
                state_change_event = WebSocketMessage(
                    event_type=WebSocketEvent.MEETING_SETTINGS_CHANGED,
                    data={
                        'type': 'meeting_state_updated',
                        'meeting_id': meeting_id,
                        'updates': updates,
                        'full_state': asdict(meeting_state)
                    },
                    timestamp=datetime.now(timezone.utc),
                    meeting_id=meeting_id
                )
                
                await self.broadcast_event(state_change_event, target_meeting_id=meeting_id)
                
                # Publish to Redis for distributed sync
                if self.redis and self.config['distributed_mode']:
                    state_data = json.dumps({
                        'meeting_id': meeting_id,
                        'updates': updates,
                        'full_state': asdict(meeting_state),
                        'updated_at': meeting_state.updated_at.isoformat()
                    })
                    
                    await self.redis.publish("zoom_meeting_state_updates", state_data)
            
        except Exception as e:
            logger.error(f"Failed to update meeting state: {e}")
    
    async def _connection_handler(self) -> None:
        """Handle connection management (ping, cleanup, etc.)"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config['ping_interval'])
                
                # Check for inactive connections
                current_time = datetime.now(timezone.utc)
                inactive_connections = []
                
                for connection_id, connection in self.connections.items():
                    time_since_ping = (current_time - connection.last_ping).total_seconds()
                    
                    if time_since_ping > self.config['ping_timeout'] * 2:
                        inactive_connections.append(connection_id)
                    elif time_since_ping > self.config['ping_interval']:
                        # Send ping
                        ping_message = WebSocketMessage(
                            event_type=WebSocketEvent.USER_STATUS_CHANGED,
                            data={
                                'type': 'ping',
                                'timestamp': current_time.isoformat()
                            },
                            timestamp=current_time,
                            session_id=connection_id
                        )
                        
                        await self._send_message(connection_id, ping_message)
                
                # Close inactive connections
                for connection_id in inactive_connections:
                    await self._close_connection(connection_id, "Connection timeout")
                
                # Update metrics
                self.metrics['active_connections'] = len(self.connections)
                
            except Exception as e:
                logger.error(f"Error in connection handler: {e}")
    
    async def _event_processor(self) -> None:
        """Process events from queue"""
        while self.is_running:
            try:
                # Get event from queue
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Process event
                await self._process_event(event)
                
                # Trigger event handlers
                for handler in self.event_handlers[event.event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
                
                # Update metrics
                self.metrics['total_events'] += 1
                
            except asyncio.TimeoutError:
                # No events in queue
                continue
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
    
    async def _process_event(self, event: RealTimeEvent) -> None:
        """Process real-time event"""
        try:
            # Update meeting state if needed
            if event.meeting_id and event.event_type in [
                WebSocketEvent.MEETING_STARTED,
                WebSocketEvent.MEETING_ENDED,
                WebSocketEvent.PARTICIPANT_JOINED,
                WebSocketEvent.PARTICIPANT_LEFT,
                WebSocketEvent.RECORDING_STARTED,
                WebSocketEvent.RECORDING_STOPPED
            ]:
                await self._update_meeting_state_from_event(event)
            
            # Mark event as processed
            event.processed = True
            
            # Update in database
            await self._mark_event_processed(event.event_id)
            
        except Exception as e:
            logger.error(f"Failed to process event {event.event_id}: {e}")
            event.retry_count += 1
            
            # Re-queue event if retry count is within limits
            if event.retry_count < 3:
                await asyncio.sleep(2 ** event.retry_count)  # Exponential backoff
                await self.event_queue.put(event)
    
    async def _state_synchronizer(self) -> None:
        """Synchronize states with database and other services"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config['state_sync_interval'])
                
                # Sync connection states
                await self._sync_connection_states()
                
                # Sync meeting states
                await self._sync_meeting_states()
                
                # Cleanup old events
                await self._cleanup_old_events()
                
            except Exception as e:
                logger.error(f"Error in state synchronizer: {e}")
    
    async def _redis_listener(self) -> None:
        """Listen to Redis for distributed events"""
        if not self.redis or not self.pubsub:
            return
        
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel']
                    data = message['data']
                    
                    if channel == 'zoom_websocket_events':
                        # Handle distributed WebSocket event
                        await self._handle_distributed_event(data)
                    elif channel == 'zoom_meeting_state_updates':
                        # Handle distributed meeting state update
                        await self._handle_distributed_state_update(data)
                    elif channel == 'zoom_connection_management':
                        # Handle distributed connection management
                        await self._handle_distributed_connection_management(data)
        
        except Exception as e:
            logger.error(f"Error in Redis listener: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collect and report performance metrics"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Collect metrics every minute
                
                # Calculate metrics
                current_time = datetime.now(timezone.utc)
                total_uptime = (current_time - current_time.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
                
                self.metrics.update({
                    'active_connections': len(self.connections),
                    'total_meeting_states': len(self.meeting_states),
                    'connection_uptime': total_uptime,
                    'event_processing_rate': self.metrics['total_events'] / max(total_uptime / 60, 1)
                })
                
                # Log metrics
                logger.info(f"WebSocket metrics: {self.metrics}")
                
                # Store metrics in database
                await self._store_metrics(self.metrics)
                
            except Exception as e:
                logger.error(f"Error in metrics collector: {e}")
    
    async def _store_connection(self, connection: WebSocketConnection) -> None:
        """Store connection in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_websocket_connections (
                        connection_id, user_id, account_id, status,
                        connected_at, last_ping, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (connection_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_ping = EXCLUDED.last_ping,
                        message_count = zoom_websocket_connections.message_count + 1,
                        updated_at = NOW()
                """,
                connection.connection_id, connection.user_id, connection.account_id,
                connection.status.value, connection.connected_at, connection.last_ping,
                json.dumps(connection.metadata or {})
                )
                
        except Exception as e:
            logger.error(f"Failed to store connection: {e}")
    
    async def _update_connection(self, connection_id: str, updates: Dict[str, Any]) -> None:
        """Update connection in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                set_clauses = []
                values = []
                param_index = 1
                
                for field, value in updates.items():
                    set_clauses.append(f"{field} = ${param_index}")
                    values.append(value)
                    param_index += 1
                
                values.append(connection_id)
                
                await conn.execute(f"""
                    UPDATE zoom_websocket_connections 
                    SET {', '.join(set_clauses)}, updated_at = NOW()
                    WHERE connection_id = ${param_index}
                """, *values)
                
        except Exception as e:
            logger.error(f"Failed to update connection: {e}")
    
    async def _cleanup_connection(self, connection_id: str) -> None:
        """Clean up connection"""
        try:
            connection = self.connections.get(connection_id)
            if connection:
                # Remove from data structures
                del self.connections[connection_id]
                self.user_connections[connection.user_id].discard(connection_id)
                
                # Remove from meeting subscriptions
                for meeting_id in connection.subscribed_meetings:
                    self.meeting_subscribers[meeting_id].discard(connection_id)
                
                # Update database
                if self.db_pool:
                    async with self.db_pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE zoom_websocket_connections 
                            SET status = 'disconnected', disconnected_at = NOW()
                            WHERE connection_id = $1
                        """, connection_id)
                
                logger.info(f"Cleaned up connection {connection_id}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup connection {connection_id}: {e}")
    
    async def _close_connection(self, connection_id: str, reason: str) -> None:
        """Close WebSocket connection"""
        try:
            connection = self.connections.get(connection_id)
            if connection:
                connection.status = ConnectionStatus.DISCONNECTED
                
                # Send close message if still connected
                if connection.websocket and connection.websocket.open:
                    close_message = WebSocketMessage(
                        event_type=WebSocketEvent.USER_STATUS_CHANGED,
                        data={
                            'type': 'connection_closed',
                            'reason': reason,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        },
                        timestamp=datetime.now(timezone.utc),
                        session_id=connection_id
                    )
                    
                    try:
                        await connection.websocket.send(json.dumps({
                            'event_type': close_message.event_type.value,
                            'data': close_message.data,
                            'timestamp': close_message.timestamp.isoformat()
                        }))
                    except:
                        pass  # Connection already closed
                
                # Close WebSocket
                if connection.websocket:
                    try:
                        await connection.websocket.close()
                    except:
                        pass  # Connection already closed
                
                # Clean up connection
                await self._cleanup_connection(connection_id)
                
                # Update metrics
                self.metrics['active_connections'] = len(self.connections)
                
                logger.info(f"Closed connection {connection_id}: {reason}")
                
        except Exception as e:
            logger.error(f"Failed to close connection {connection_id}: {e}")
    
    async def _store_event(self, event: WebSocketMessage) -> None:
        """Store event in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                event_id = f"{event.event_type.value}_{event.timestamp.timestamp()}_{secrets.token_hex(8)}"
                
                await conn.execute("""
                    INSERT INTO zoom_realtime_events (
                        event_id, event_type, source, user_id, meeting_id,
                        account_id, data, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                event_id, event.event_type.value, 'websocket_server',
                event.user_id, event.meeting_id, event.account_id,
                json.dumps(event.data), event.timestamp
                )
                
        except Exception as e:
            logger.error(f"Failed to store event: {e}")
    
    async def _mark_event_processed(self, event_id: str) -> None:
        """Mark event as processed in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE zoom_realtime_events 
                    SET processed = true, processed_at = NOW()
                    WHERE event_id = $1
                """, event_id)
                
        except Exception as e:
            logger.error(f"Failed to mark event as processed: {e}")
    
    async def _update_meeting_state_db(self, meeting_state: MeetingState) -> None:
        """Update meeting state in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_meeting_states (
                        meeting_id, topic, host_id, status, start_time,
                        participants, recording_status, settings, metadata,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (meeting_id) DO UPDATE SET
                        topic = EXCLUDED.topic,
                        host_id = EXCLUDED.host_id,
                        status = EXCLUDED.status,
                        start_time = EXCLUDED.start_time,
                        participants = EXCLUDED.participants,
                        recording_status = EXCLUDED.recording_status,
                        settings = EXCLUDED.settings,
                        metadata = EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                """,
                meeting_state.meeting_id, meeting_state.topic, meeting_state.host_id,
                meeting_state.status, meeting_state.start_time,
                json.dumps(meeting_state.participants), meeting_state.recording_status,
                json.dumps(meeting_state.settings), json.dumps(meeting_state.metadata),
                meeting_state.created_at, meeting_state.updated_at
                )
                
        except Exception as e:
            logger.error(f"Failed to update meeting state: {e}")
    
    async def _store_metrics(self, metrics: Dict[str, Any]) -> None:
        """Store performance metrics"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zoom_websocket_metrics (
                        timestamp, active_connections, total_connections,
                        total_messages, total_events, failed_connections,
                        average_message_time, connection_uptime,
                        event_processing_rate, memory_usage, cpu_usage
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                datetime.now(timezone.utc), metrics['active_connections'],
                metrics['total_connections'], metrics['total_messages'],
                metrics['total_events'], metrics['failed_connections'],
                metrics['average_message_time'], metrics['connection_uptime'],
                metrics['event_processing_rate'], metrics['memory_usage'],
                metrics['cpu_usage']
                )
                
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current WebSocket metrics"""
        return self.metrics.copy()
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get connection information"""
        connection = self.connections.get(connection_id)
        if connection:
            return {
                'connection_id': connection.connection_id,
                'user_id': connection.user_id,
                'account_id': connection.account_id,
                'status': connection.status.value,
                'connected_at': connection.connected_at.isoformat(),
                'last_ping': connection.last_ping.isoformat(),
                'message_count': connection.message_count,
                'error_count': connection.error_count,
                'subscribed_meetings': list(connection.subscribed_meetings),
                'subscribed_events': [e.value for e in connection.subscribed_events],
                'metadata': connection.metadata
            }
        return None
    
    def get_meeting_state(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get meeting state information"""
        meeting_state = self.meeting_states.get(meeting_id)
        if meeting_state:
            return asdict(meeting_state)
        return None
    
    async def create_event(self, event_type: WebSocketEvent, data: Dict[str, Any], 
                         user_id: Optional[str] = None, meeting_id: Optional[str] = None,
                         account_id: Optional[str] = None) -> str:
        """Create and queue a real-time event"""
        try:
            event = WebSocketMessage(
                event_type=event_type,
                data=data,
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                meeting_id=meeting_id,
                account_id=account_id,
                correlation_id=secrets.token_hex(16),
                metadata={'created_by': 'websocket_manager'}
            )
            
            # Add to queue
            await self.event_queue.put(event)
            
            logger.info(f"Created event {event_type.value} with correlation_id {event.correlation_id}")
            return event.correlation_id
            
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return ""