"""
🔄 Zoom Data Synchronizer
Enterprise-grade real-time synchronization for Zoom data
"""

import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict

import asyncpg
from zoom_token_manager import ZoomTokenManager

logger = logging.getLogger(__name__)

# Zoom API endpoints
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"
REQUEST_TIMEOUT = 30
RATE_LIMIT_DELAY = 0.1  # seconds between requests

@dataclass
class ZoomMeeting:
    """Zoom meeting data structure"""
    id: str
    uuid: str
    topic: str
    type: int
    status: str
    start_time: str
    duration: int
    timezone: str
    agenda: Optional[str]
    join_url: str
    start_url: str
    password: Optional[str]
    settings: Dict[str, Any]
    host_id: str
    host_email: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class ZoomRecording:
    """Zoom recording data structure"""
    uuid: str
    meeting_uuid: str
    topic: str
    start_time: str
    timezone: str
    duration: int
    share_url: str
    recording_files: List[Dict[str, Any]]
    recording_count: int
    total_size: int
    password: Optional[str]
    download_url: Optional[str]
    play_url: Optional[str]
    meeting_id: Optional[str] = None
    host_id: Optional[str] = None

@dataclass
class ZoomUser:
    """Zoom user data structure"""
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: str
    pic_url: Optional[str]
    type: int
    role_name: str
    pmi: Optional[int]
    use_pmi: bool
    vanity_url: Optional[str]
    personal_meeting_url: Optional[str]
    timezone: Optional[str]
    verified: int
    dept: Optional[str]
    created_at: str
    last_login_time: Optional[str]
    status: str = 'active'

@dataclass
class ZoomWebinar:
    """Zoom webinar data structure"""
    id: str
    uuid: str
    topic: str
    type: int
    status: str
    start_time: str
    duration: int
    timezone: str
    agenda: Optional[str]
    join_url: str
    start_url: str
    password: Optional[str]
    settings: Dict[str, Any]
    host_id: str
    host_email: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class ZoomChat:
    """Zoom chat data structure"""
    id: str
    topic: str
    type: str
    members: List[str]
    channel_id: str
    created_at: str
    updated_at: str
    last_message: Optional[Dict[str, Any]]
    message_count: int = 0

@dataclass
class ZoomReport:
    """Zoom report data structure"""
    id: str
    type: str
    date_from: str
    date_to: str
    total_meetings: int
    total_participants: int
    total_minutes: int
    data: Dict[str, Any]
    created_at: str
    updated_at: str

class ZoomDataSynchronizer:
    """Enterprise-grade Zoom data synchronizer"""
    
    def __init__(self, db_pool: asyncpg.Pool, token_manager: ZoomTokenManager):
        self.db_pool = db_pool
        self.token_manager = token_manager
        
        # HTTP client for API requests
        self.http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        
        # Sync configuration
        self.sync_interval = int(os.getenv('ZOOM_SYNC_INTERVAL', '300'))  # 5 minutes
        self.batch_size = int(os.getenv('ZOOM_SYNC_BATCH_SIZE', '100'))
        self.max_retries = int(os.getenv('ZOOM_SYNC_MAX_RETRIES', '3'))
        
        # Sync state
        self.sync_active = False
        self.last_sync_time = None
        self.sync_stats = {
            'meetings_synced': 0,
            'recordings_synced': 0,
            'users_synced': 0,
            'webinars_synced': 0,
            'chats_synced': 0,
            'reports_synced': 0,
            'errors_count': 0,
            'last_sync_duration': 0
        }
        
        # Event callbacks
        self.event_callbacks = defaultdict(list)
    
    async def initialize(self) -> bool:
        """Initialize synchronizer"""
        try:
            # Initialize database tables
            await self._init_database_tables()
            
            # Start background sync task
            asyncio.create_task(self._background_sync())
            
            logger.info("Zoom data synchronizer initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Zoom data synchronizer: {e}")
            return False
    
    async def _init_database_tables(self):
        """Initialize database tables for Zoom data"""
        async with self.db_pool.acquire() as conn:
            # Meetings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_meetings (
                    id VARCHAR(255) PRIMARY KEY,
                    uuid VARCHAR(255) UNIQUE,
                    topic TEXT,
                    type INTEGER,
                    status VARCHAR(50),
                    start_time TIMESTAMP WITH TIME ZONE,
                    duration INTEGER,
                    timezone VARCHAR(100),
                    agenda TEXT,
                    join_url TEXT,
                    start_url TEXT,
                    password VARCHAR(50),
                    settings JSONB DEFAULT '{}'::jsonb,
                    host_id VARCHAR(255),
                    host_email VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Recordings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_recordings (
                    id SERIAL PRIMARY KEY,
                    uuid VARCHAR(255) UNIQUE,
                    meeting_uuid VARCHAR(255),
                    topic TEXT,
                    start_time TIMESTAMP WITH TIME ZONE,
                    timezone VARCHAR(100),
                    duration INTEGER,
                    share_url TEXT,
                    recording_files JSONB DEFAULT '[]'::jsonb,
                    recording_count INTEGER DEFAULT 0,
                    total_size BIGINT DEFAULT 0,
                    password VARCHAR(50),
                    download_url TEXT,
                    play_url TEXT,
                    meeting_id VARCHAR(255),
                    host_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_users (
                    id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    display_name VARCHAR(255),
                    pic_url TEXT,
                    type INTEGER,
                    role_name VARCHAR(255),
                    pmi VARCHAR(255),
                    use_pmi BOOLEAN DEFAULT false,
                    vanity_url TEXT,
                    personal_meeting_url TEXT,
                    timezone VARCHAR(100),
                    verified INTEGER DEFAULT 0,
                    dept VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE,
                    last_login_time TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(50) DEFAULT 'active',
                    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Webinars table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_webinars (
                    id VARCHAR(255) PRIMARY KEY,
                    uuid VARCHAR(255) UNIQUE,
                    topic TEXT,
                    type INTEGER,
                    status VARCHAR(50),
                    start_time TIMESTAMP WITH TIME ZONE,
                    duration INTEGER,
                    timezone VARCHAR(100),
                    agenda TEXT,
                    join_url TEXT,
                    start_url TEXT,
                    password VARCHAR(50),
                    settings JSONB DEFAULT '{}'::jsonb,
                    host_id VARCHAR(255),
                    host_email VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Chats table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_chats (
                    id VARCHAR(255) PRIMARY KEY,
                    topic TEXT,
                    type VARCHAR(50),
                    members JSONB DEFAULT '[]'::jsonb,
                    channel_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    last_message JSONB DEFAULT '{}'::jsonb,
                    message_count INTEGER DEFAULT 0,
                    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Reports table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zoom_reports (
                    id SERIAL PRIMARY KEY,
                    type VARCHAR(100),
                    date_from DATE,
                    date_to DATE,
                    total_meetings INTEGER DEFAULT 0,
                    total_participants INTEGER DEFAULT 0,
                    total_minutes BIGINT DEFAULT 0,
                    data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Create indexes
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_zoom_meetings_host_id ON zoom_meetings(host_id);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_meetings_start_time ON zoom_meetings(start_time);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_meetings_status ON zoom_meetings(status);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_recordings_meeting_uuid ON zoom_recordings(meeting_uuid);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_recordings_start_time ON zoom_recordings(start_time);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_users_email ON zoom_users(email);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_users_status ON zoom_users(status);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_webinars_host_id ON zoom_webinars(host_id);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_webinars_start_time ON zoom_webinars(start_time);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_webinars_status ON zoom_webinars(status);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_chats_channel_id ON zoom_chats(channel_id);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_chats_type ON zoom_chats(type);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_reports_type ON zoom_reports(type);",
                "CREATE INDEX IF NOT EXISTS idx_zoom_reports_date_range ON zoom_reports(date_from, date_to);"
            ]
            
            for index_sql in indexes:
                await conn.execute(index_sql)
            
            logger.info("Zoom database tables initialized successfully")
    
    async def _make_api_request(self, user_id: str, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated API request to Zoom"""
        try:
            # Get fresh access token
            token = await self.token_manager.refresh_token_if_needed(user_id)
            if not token:
                raise ValueError(f"No valid token for user {user_id}")
            
            headers = {
                'Authorization': f'Bearer {token.access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{ZOOM_API_BASE_URL}{endpoint}"
            response = await self.http_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            # Update token usage
            await self.token_manager.update_last_used(user_id)
            
            # Rate limiting
            await asyncio.sleep(RATE_LIMIT_DELAY)
            
            return response.json()
            
        except Exception as e:
            logger.error(f"API request failed for {endpoint}: {e}")
            raise
    
    async def sync_user_meetings(self, user_id: str, from_date: Optional[datetime] = None) -> int:
        """Synchronize user meetings"""
        try:
            meetings_synced = 0
            
            # Get user meetings from Zoom API
            params = {
                'type': 'scheduled',
                'page_size': min(self.batch_size, 300)
            }
            
            if from_date:
                params['from'] = from_date.isoformat()
            
            response = await self._make_api_request(user_id, '/users/me/meetings', params)
            meetings_data = response.get('meetings', [])
            
            for meeting_data in meetings_data:
                # Parse meeting data
                meeting = ZoomMeeting(
                    id=meeting_data['id'],
                    uuid=meeting_data.get('uuid', ''),
                    topic=meeting_data.get('topic', ''),
                    type=meeting_data.get('type', 2),
                    status=meeting_data.get('status', ''),
                    start_time=meeting_data.get('start_time', ''),
                    duration=meeting_data.get('duration', 0),
                    timezone=meeting_data.get('timezone', ''),
                    agenda=meeting_data.get('agenda'),
                    join_url=meeting_data.get('join_url', ''),
                    start_url=meeting_data.get('start_url', ''),
                    password=meeting_data.get('password'),
                    settings=meeting_data.get('settings', {}),
                    host_id=meeting_data.get('host_id', ''),
                    host_email=meeting_data.get('host_email', ''),
                    created_at=meeting_data.get('created_at'),
                    updated_at=meeting_data.get('updated_at')
                )
                
                # Store in database
                await self._store_meeting(meeting)
                meetings_synced += 1
                
                # Trigger event
                await self._trigger_event('meeting_synced', meeting)
            
            logger.info(f"Synced {meetings_synced} meetings for user {user_id}")
            self.sync_stats['meetings_synced'] += meetings_synced
            
            return meetings_synced
            
        except Exception as e:
            logger.error(f"Failed to sync meetings for user {user_id}: {e}")
            self.sync_stats['errors_count'] += 1
            return 0
    
    async def sync_user_recordings(self, user_id: str, from_date: Optional[datetime] = None) -> int:
        """Synchronize user recordings"""
        try:
            recordings_synced = 0
            
            # Get user recordings from Zoom API
            params = {
                'page_size': min(self.batch_size, 300),
                'from': from_date.isoformat() if from_date else None,
                'to': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            response = await self._make_api_request(user_id, '/users/me/recordings', params)
            recordings_data = response.get('meetings', [])
            
            for recording_data in recordings_data:
                # Parse recording data
                recording = ZoomRecording(
                    uuid=recording_data.get('uuid', ''),
                    meeting_uuid=recording_data.get('uuid', ''),
                    topic=recording_data.get('topic', ''),
                    start_time=recording_data.get('start_time', ''),
                    timezone=recording_data.get('timezone', ''),
                    duration=recording_data.get('duration', 0),
                    share_url=recording_data.get('share_url', ''),
                    recording_files=recording_data.get('recording_files', []),
                    recording_count=len(recording_data.get('recording_files', [])),
                    total_size=sum(f.get('file_size', 0) for f in recording_data.get('recording_files', [])),
                    password=recording_data.get('password'),
                    download_url=recording_data.get('download_url'),
                    play_url=recording_data.get('play_url'),
                    meeting_id=recording_data.get('id'),
                    host_id=recording_data.get('host_id')
                )
                
                # Store in database
                await self._store_recording(recording)
                recordings_synced += 1
                
                # Trigger event
                await self._trigger_event('recording_synced', recording)
            
            logger.info(f"Synced {recordings_synced} recordings for user {user_id}")
            self.sync_stats['recordings_synced'] += recordings_synced
            
            return recordings_synced
            
        except Exception as e:
            logger.error(f"Failed to sync recordings for user {user_id}: {e}")
            self.sync_stats['errors_count'] += 1
            return 0
    
    async def sync_user_info(self, user_id: str) -> bool:
        """Synchronize user information"""
        try:
            # Get user info from Zoom API
            response = await self._make_api_request(user_id, '/users/me')
            user_data = response
            
            # Parse user data
            user = ZoomUser(
                id=user_data.get('id', ''),
                email=user_data.get('email', ''),
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                display_name=user_data.get('display_name', ''),
                pic_url=user_data.get('pic_url'),
                type=user_data.get('type', 1),
                role_name=user_data.get('role_name', ''),
                pmi=user_data.get('pmi'),
                use_pmi=user_data.get('use_pmi', False),
                vanity_url=user_data.get('vanity_url'),
                personal_meeting_url=user_data.get('personal_meeting_url'),
                timezone=user_data.get('timezone'),
                verified=user_data.get('verified', 0),
                dept=user_data.get('dept'),
                created_at=user_data.get('created_at', ''),
                last_login_time=user_data.get('last_login_time')
            )
            
            # Store in database
            await self._store_user(user)
            
            # Trigger event
            await self._trigger_event('user_synced', user)
            
            logger.info(f"Synced user info for {user_id}")
            self.sync_stats['users_synced'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync user info for {user_id}: {e}")
            self.sync_stats['errors_count'] += 1
            return False
    
    async def sync_user_webinars(self, user_id: str, from_date: Optional[datetime] = None) -> int:
        """Synchronize user webinars"""
        try:
            webinars_synced = 0
            
            # Get user webinars from Zoom API
            params = {
                'page_size': min(self.batch_size, 300),
                'type': 'scheduled'
            }
            
            if from_date:
                params['from'] = from_date.isoformat()
            
            response = await self._make_api_request(user_id, '/users/me/webinars', params)
            webinars_data = response.get('webinars', [])
            
            for webinar_data in webinars_data:
                # Parse webinar data
                webinar = ZoomWebinar(
                    id=webinar_data['id'],
                    uuid=webinar_data.get('uuid', ''),
                    topic=webinar_data.get('topic', ''),
                    type=webinar_data.get('type', 5),
                    status=webinar_data.get('status', ''),
                    start_time=webinar_data.get('start_time', ''),
                    duration=webinar_data.get('duration', 0),
                    timezone=webinar_data.get('timezone', ''),
                    agenda=webinar_data.get('agenda'),
                    join_url=webinar_data.get('join_url', ''),
                    start_url=webinar_data.get('start_url', ''),
                    password=webinar_data.get('password'),
                    settings=webinar_data.get('settings', {}),
                    host_id=webinar_data.get('host_id', ''),
                    host_email=webinar_data.get('host_email', ''),
                    created_at=webinar_data.get('created_at'),
                    updated_at=webinar_data.get('updated_at')
                )
                
                # Store in database
                await self._store_webinar(webinar)
                webinars_synced += 1
                
                # Trigger event
                await self._trigger_event('webinar_synced', webinar)
            
            logger.info(f"Synced {webinars_synced} webinars for user {user_id}")
            self.sync_stats['webinars_synced'] += webinars_synced
            
            return webinars_synced
            
        except Exception as e:
            logger.error(f"Failed to sync webinars for user {user_id}: {e}")
            self.sync_stats['errors_count'] += 1
            return 0
    
    async def _store_meeting(self, meeting: ZoomMeeting):
        """Store meeting in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO zoom_meetings (
                    id, uuid, topic, type, status, start_time, duration,
                    timezone, agenda, join_url, start_url, password,
                    settings, host_id, host_email, created_at, updated_at, synced_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                          $13, $14, $15, $16, $17, $18)
                ON CONFLICT (id) DO UPDATE SET
                    uuid = EXCLUDED.uuid,
                    topic = EXCLUDED.topic,
                    status = EXCLUDED.status,
                    start_time = EXCLUDED.start_time,
                    duration = EXCLUDED.duration,
                    timezone = EXCLUDED.timezone,
                    agenda = EXCLUDED.agenda,
                    join_url = EXCLUDED.join_url,
                    start_url = EXCLUDED.start_url,
                    password = EXCLUDED.password,
                    settings = EXCLUDED.settings,
                    updated_at = EXCLUDED.updated_at,
                    synced_at = NOW()
            """, *asdict(meeting).values())
    
    async def _store_recording(self, recording: ZoomRecording):
        """Store recording in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO zoom_recordings (
                    uuid, meeting_uuid, topic, start_time, timezone, duration,
                    share_url, recording_files, recording_count, total_size,
                    password, download_url, play_url, meeting_id, host_id, synced_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                          $11, $12, $13, $14, $15, $16)
                ON CONFLICT (uuid) DO UPDATE SET
                    meeting_uuid = EXCLUDED.meeting_uuid,
                    topic = EXCLUDED.topic,
                    start_time = EXCLUDED.start_time,
                    timezone = EXCLUDED.timezone,
                    duration = EXCLUDED.duration,
                    share_url = EXCLUDED.share_url,
                    recording_files = EXCLUDED.recording_files,
                    recording_count = EXCLUDED.recording_count,
                    total_size = EXCLUDED.total_size,
                    password = EXCLUDED.password,
                    download_url = EXCLUDED.download_url,
                    play_url = EXCLUDED.play_url,
                    synced_at = NOW()
            """, *asdict(recording).values())
    
    async def _store_user(self, user: ZoomUser):
        """Store user in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO zoom_users (
                    id, email, first_name, last_name, display_name, pic_url,
                    type, role_name, pmi, use_pmi, vanity_url,
                    personal_meeting_url, timezone, verified, dept,
                    created_at, last_login_time, status, synced_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                          $12, $13, $14, $15, $16, $17, $18, $19)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    display_name = EXCLUDED.display_name,
                    pic_url = EXCLUDED.pic_url,
                    type = EXCLUDED.type,
                    role_name = EXCLUDED.role_name,
                    pmi = EXCLUDED.pmi,
                    use_pmi = EXCLUDED.use_pmi,
                    vanity_url = EXCLUDED.vanity_url,
                    personal_meeting_url = EXCLUDED.personal_meeting_url,
                    timezone = EXCLUDED.timezone,
                    verified = EXCLUDED.verified,
                    dept = EXCLUDED.dept,
                    last_login_time = EXCLUDED.last_login_time,
                    status = EXCLUDED.status,
                    synced_at = NOW()
            """, *asdict(user).values())
    
    async def _store_webinar(self, webinar: ZoomWebinar):
        """Store webinar in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO zoom_webinars (
                    id, uuid, topic, type, status, start_time, duration,
                    timezone, agenda, join_url, start_url, password,
                    settings, host_id, host_email, created_at, updated_at, synced_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                          $13, $14, $15, $16, $17, $18)
                ON CONFLICT (id) DO UPDATE SET
                    uuid = EXCLUDED.uuid,
                    topic = EXCLUDED.topic,
                    status = EXCLUDED.status,
                    start_time = EXCLUDED.start_time,
                    duration = EXCLUDED.duration,
                    timezone = EXCLUDED.timezone,
                    agenda = EXCLUDED.agenda,
                    join_url = EXCLUDED.join_url,
                    start_url = EXCLUDED.start_url,
                    password = EXCLUDED.password,
                    settings = EXCLUDED.settings,
                    updated_at = EXCLUDED.updated_at,
                    synced_at = NOW()
            """, *asdict(webinar).values())
    
    def add_event_callback(self, event_type: str, callback: Callable):
        """Add event callback"""
        self.event_callbacks[event_type].append(callback)
    
    async def _trigger_event(self, event_type: str, data: Any):
        """Trigger event callbacks"""
        for callback in self.event_callbacks[event_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Event callback error for {event_type}: {e}")
    
    async def _background_sync(self):
        """Background synchronization task"""
        while True:
            try:
                if not self.sync_active:
                    await asyncio.sleep(self.sync_interval)
                    continue
                
                start_time = datetime.now(timezone.utc)
                
                # Get all active users
                users = await self.token_manager.get_all_active_tokens()
                
                for user_token in users:
                    try:
                        # Sync user data
                        await self.sync_user_info(user_token.user_id)
                        await self.sync_user_meetings(user_token.user_id, from_date=datetime.now(timezone.utc) - timedelta(days=7))
                        await self.sync_user_recordings(user_token.user_id, from_date=datetime.now(timezone.utc) - timedelta(days=7))
                        await self.sync_user_webinars(user_token.user_id, from_date=datetime.now(timezone.utc) - timedelta(days=7))
                        
                    except Exception as e:
                        logger.error(f"Failed to sync for user {user_token.user_id}: {e}")
                
                # Update sync stats
                self.last_sync_time = datetime.now(timezone.utc)
                sync_duration = (self.last_sync_time - start_time).total_seconds()
                self.sync_stats['last_sync_duration'] = sync_duration
                
                # Trigger sync completed event
                await self._trigger_event('sync_completed', self.sync_stats)
                
                logger.info(f"Background sync completed in {sync_duration:.2f} seconds")
                
            except Exception as e:
                logger.error(f"Background sync error: {e}")
                self.sync_stats['errors_count'] += 1
            
            # Wait before next sync
            await asyncio.sleep(self.sync_interval)
    
    async def start_sync(self):
        """Start synchronization"""
        self.sync_active = True
        logger.info("Zoom data synchronization started")
    
    async def stop_sync(self):
        """Stop synchronization"""
        self.sync_active = False
        logger.info("Zoom data synchronization stopped")
    
    async def force_sync(self, user_id: Optional[str] = None):
        """Force immediate sync for user or all users"""
        try:
            if user_id:
                await self.sync_user_info(user_id)
                await self.sync_user_meetings(user_id)
                await self.sync_user_recordings(user_id)
                await self.sync_user_webinars(user_id)
            else:
                # Sync all active users
                users = await self.token_manager.get_all_active_tokens()
                for user_token in users:
                    await self.force_sync(user_token.user_id)
            
            logger.info(f"Force sync completed for {user_id or 'all users'}")
            
        except Exception as e:
            logger.error(f"Force sync error: {e}")
            raise
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        return {
            'sync_active': self.sync_active,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'sync_interval': self.sync_interval,
            'stats': self.sync_stats.copy()
        }
    
    async def close(self):
        """Close synchronizer"""
        await self.stop_sync()
        await self.http_client.aclose()
        await self.token_manager.close()
        
        logger.info("Zoom data synchronizer closed")