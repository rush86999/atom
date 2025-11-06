"""
🔧 Zoom API Manager
Enterprise-grade Zoom API wrapper with comprehensive operations
"""

import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

from zoom_token_manager import ZoomTokenManager
from zoom_data_synchronizer import ZoomDataSynchronizer

logger = logging.getLogger(__name__)

# Zoom API endpoints
ZOOM_API_BASE_URL = "https://api.zoom.us/v2"
REQUEST_TIMEOUT = 30
RATE_LIMIT_DELAY = 0.1  # seconds between requests

@dataclass
class ZoomMeetingRequest:
    """Zoom meeting creation request"""
    topic: str
    type: int = 2  # Scheduled meeting
    start_time: str
    duration: int = 60
    timezone: str = 'UTC'
    agenda: Optional[str] = None
    password: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

@dataclass
class ZoomMeetingResponse:
    """Zoom meeting response"""
    id: str
    uuid: str
    topic: str
    type: int
    start_time: str
    duration: int
    timezone: str
    agenda: Optional[str]
    password: Optional[str]
    join_url: str
    start_url: str
    settings: Dict[str, Any]
    host_id: str
    host_email: str

@dataclass
class ZoomMeetingUpdate:
    """Zoom meeting update request"""
    topic: Optional[str] = None
    type: Optional[int] = None
    start_time: Optional[str] = None
    duration: Optional[int] = None
    timezone: Optional[str] = None
    agenda: Optional[str] = None
    password: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

@dataclass
class ZoomWebinarRequest:
    """Zoom webinar creation request"""
    topic: str
    type: int = 5  # Webinar
    start_time: str
    duration: int = 60
    timezone: str = 'UTC'
    agenda: Optional[str] = None
    password: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

@dataclass
class ZoomRecordingSettings:
    """Zoom recording settings"""
    auto_recording: str = 'cloud'
    host_video: bool = True
    participant_video: bool = True
    waiting_room: bool = False
    in_meeting: bool = False
    watermarks: bool = False
    audio_transcript: bool = False

@dataclass
class ZoomReportRequest:
    """Zoom report request"""
    report_type: str  # 'meetings', 'webinars', 'participants', 'quality', etc.
    from_date: str
    to_date: str
    user_ids: Optional[List[str]] = None
    meeting_ids: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None

class ZoomAPIManager:
    """Enterprise-grade Zoom API manager"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.client_id = os.getenv('ZOOM_CLIENT_ID')
        self.client_secret = os.getenv('ZOOM_CLIENT_SECRET')
        
        # Initialize managers
        self.token_manager = ZoomTokenManager(
            db_pool, 
            os.getenv('ENCRYPTION_KEY')
        )
        self.data_synchronizer = ZoomDataSynchronizer(
            db_pool, 
            self.token_manager
        )
        
        # HTTP client for API requests
        self.http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        
        # API configuration
        self.rate_limit_delay = RATE_LIMIT_DELAY
        self.max_retries = 3
        self.default_page_size = 100
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate API configuration"""
        if not self.client_id:
            raise ValueError("ZOOM_CLIENT_ID is required")
        
        if not self.client_secret:
            raise ValueError("ZOOM_CLIENT_SECRET is required")
    
    async def initialize(self) -> bool:
        """Initialize API manager"""
        try:
            # Initialize token manager
            await self.token_manager.init_database()
            
            # Initialize data synchronizer
            await self.data_synchronizer.initialize()
            
            logger.info("Zoom API manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Zoom API manager: {e}")
            return False
    
    async def _make_authenticated_request(
        self, 
        user_id: str, 
        method: str, 
        endpoint: str, 
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request"""
        try:
            # Get fresh access token
            token = await self.token_manager.refresh_token_if_needed(user_id)
            if not token:
                raise ValueError(f"No valid token for user {user_id}")
            
            # Prepare headers
            request_headers = {
                'Authorization': f'Bearer {token.access_token}',
                'Content-Type': 'application/json'
            }
            
            if headers:
                request_headers.update(headers)
            
            url = f"{ZOOM_API_BASE_URL}{endpoint}"
            
            # Make request with retries
            for attempt in range(self.max_retries):
                try:
                    if method.upper() == 'GET':
                        response = await self.http_client.get(url, headers=request_headers, params=params)
                    elif method.upper() == 'POST':
                        response = await self.http_client.post(url, headers=request_headers, json=data, params=params)
                    elif method.upper() == 'PUT':
                        response = await self.http_client.put(url, headers=request_headers, json=data, params=params)
                    elif method.upper() == 'DELETE':
                        response = await self.http_client.delete(url, headers=request_headers, params=params)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                    
                    response.raise_for_status()
                    
                    # Rate limiting
                    await asyncio.sleep(self.rate_limit_delay)
                    
                    return response.json()
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        # Token expired, try refresh once
                        if attempt == 0:
                            await self.token_manager.refresh_token_if_needed(user_id)
                            continue
                    elif e.response.status_code == 429:
                        # Rate limited, wait and retry
                        retry_after = int(e.response.headers.get('Retry-After', '60'))
                        await asyncio.sleep(retry_after)
                        continue
                    
                    raise e
            
            raise Exception(f"Max retries exceeded for {endpoint}")
            
        except Exception as e:
            logger.error(f"API request failed for {endpoint}: {e}")
            raise
    
    # === MEETINGS MANAGEMENT ===
    
    async def create_meeting(
        self, 
        user_id: str, 
        meeting_request: ZoomMeetingRequest
    ) -> Optional[ZoomMeetingResponse]:
        """Create a Zoom meeting"""
        try:
            # Prepare meeting data
            meeting_data = asdict(meeting_request)
            
            # Set default settings if not provided
            if not meeting_data.get('settings'):
                meeting_data['settings'] = {
                    'host_video': True,
                    'participant_video': True,
                    'join_before_host': False,
                    'mute_upon_entry': True,
                    'auto_recording': 'cloud'
                }
            
            # Make API request
            response_data = await self._make_authenticated_request(
                user_id, 'POST', '/users/me/meetings', data=meeting_data
            )
            
            # Parse response
            meeting_response = ZoomMeetingResponse(
                id=response_data['id'],
                uuid=response_data.get('uuid', ''),
                topic=response_data.get('topic', ''),
                type=response_data.get('type', 2),
                start_time=response_data.get('start_time', ''),
                duration=response_data.get('duration', 60),
                timezone=response_data.get('timezone', 'UTC'),
                agenda=response_data.get('agenda'),
                password=response_data.get('password'),
                join_url=response_data.get('join_url', ''),
                start_url=response_data.get('start_url', ''),
                settings=response_data.get('settings', {}),
                host_id=response_data.get('host_id', ''),
                host_email=response_data.get('host_email', '')
            )
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_meetings(user_id)
            
            logger.info(f"Created Zoom meeting {meeting_response.id} for user {user_id}")
            return meeting_response
            
        except Exception as e:
            logger.error(f"Failed to create meeting for user {user_id}: {e}")
            return None
    
    async def get_meeting(
        self, 
        user_id: str, 
        meeting_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get meeting details"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'GET', f'/meetings/{meeting_id}'
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get meeting {meeting_id}: {e}")
            return None
    
    async def update_meeting(
        self, 
        user_id: str, 
        meeting_id: str, 
        meeting_update: ZoomMeetingUpdate
    ) -> Optional[Dict[str, Any]]:
        """Update meeting details"""
        try:
            # Prepare update data
            update_data = asdict(meeting_update)
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            response_data = await self._make_authenticated_request(
                user_id, 'PATCH', f'/meetings/{meeting_id}', data=update_data
            )
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_meetings(user_id)
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to update meeting {meeting_id}: {e}")
            return None
    
    async def delete_meeting(
        self, 
        user_id: str, 
        meeting_id: str
    ) -> bool:
        """Delete a meeting"""
        try:
            await self._make_authenticated_request(
                user_id, 'DELETE', f'/meetings/{meeting_id}'
            )
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_meetings(user_id)
            
            logger.info(f"Deleted Zoom meeting {meeting_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete meeting {meeting_id}: {e}")
            return False
    
    async def list_meetings(
        self, 
        user_id: str, 
        meeting_type: str = 'scheduled',
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List user meetings"""
        try:
            params = {
                'type': meeting_type,
                'page_size': page_size or self.default_page_size
            }
            
            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', '/users/me/meetings', params=params
            )
            
            meetings = response_data.get('meetings', [])
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_meetings(user_id)
            
            return meetings
            
        except Exception as e:
            logger.error(f"Failed to list meetings for user {user_id}: {e}")
            return []
    
    async def get_meeting_participants(
        self, 
        user_id: str, 
        meeting_id: str
    ) -> List[Dict[str, Any]]:
        """Get meeting participants"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'GET', f'/meetings/{meeting_id}/participants'
            )
            
            return response_data.get('participants', [])
            
        except Exception as e:
            logger.error(f"Failed to get participants for meeting {meeting_id}: {e}")
            return []
    
    async def get_meeting_registrants(
        self, 
        user_id: str, 
        meeting_id: str
    ) -> List[Dict[str, Any]]:
        """Get meeting registrants"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'GET', f'/meetings/{meeting_id}/registrants'
            )
            
            return response_data.get('registrants', [])
            
        except Exception as e:
            logger.error(f"Failed to get registrants for meeting {meeting_id}: {e}")
            return []
    
    # === WEBINARS MANAGEMENT ===
    
    async def create_webinar(
        self, 
        user_id: str, 
        webinar_request: ZoomWebinarRequest
    ) -> Optional[Dict[str, Any]]:
        """Create a Zoom webinar"""
        try:
            # Prepare webinar data
            webinar_data = asdict(webinar_request)
            
            # Set default settings if not provided
            if not webinar_data.get('settings'):
                webinar_data['settings'] = {
                    'host_video': True,
                    'panelists_video': True,
                    'practice_session': True,
                    'hd_video': True,
                    'on_demand': True,
                    'auto_recording': 'cloud'
                }
            
            # Make API request
            response_data = await self._make_authenticated_request(
                user_id, 'POST', '/users/me/webinars', data=webinar_data
            )
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_webinars(user_id)
            
            logger.info(f"Created Zoom webinar {response_data.get('id')} for user {user_id}")
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to create webinar for user {user_id}: {e}")
            return None
    
    async def list_webinars(
        self, 
        user_id: str, 
        webinar_type: str = 'scheduled',
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List user webinars"""
        try:
            params = {
                'type': webinar_type,
                'page_size': page_size or self.default_page_size
            }
            
            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', '/users/me/webinars', params=params
            )
            
            webinars = response_data.get('webinars', [])
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_webinars(user_id)
            
            return webinars
            
        except Exception as e:
            logger.error(f"Failed to list webinars for user {user_id}: {e}")
            return []
    
    # === RECORDINGS MANAGEMENT ===
    
    async def get_recordings(
        self, 
        user_id: str, 
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        meeting_id: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get user recordings"""
        try:
            params = {
                'page_size': page_size or self.default_page_size
            }
            
            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date
            if meeting_id:
                params['meetingId'] = meeting_id
            
            endpoint = f'/users/me/recordings'
            if meeting_id:
                endpoint = f'/meetings/{meeting_id}/recordings'
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', endpoint, params=params
            )
            
            recordings = response_data.get('meetings', [])
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_recordings(user_id)
            
            return recordings
            
        except Exception as e:
            logger.error(f"Failed to get recordings for user {user_id}: {e}")
            return []
    
    async def delete_recording(
        self, 
        user_id: str, 
        meeting_id: str, 
        recording_id: str
    ) -> bool:
        """Delete a recording"""
        try:
            await self._make_authenticated_request(
                user_id, 'DELETE', f'/meetings/{meeting_id}/recordings/{recording_id}'
            )
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_recordings(user_id)
            
            logger.info(f"Deleted Zoom recording {recording_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete recording {recording_id}: {e}")
            return False
    
    # === USERS MANAGEMENT ===
    
    async def get_user_info(
        self, 
        user_id: str, 
        target_user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get user information"""
        try:
            endpoint = f'/users/me'
            if target_user_id:
                endpoint = f'/users/{target_user_id}'
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', endpoint
            )
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_info(user_id)
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get user info for user {user_id}: {e}")
            return None
    
    async def update_user_info(
        self, 
        user_id: str, 
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update user information"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'PATCH', '/users/me', data=update_data
            )
            
            # Sync with data synchronizer
            await self.data_synchronizer.sync_user_info(user_id)
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to update user info for user {user_id}: {e}")
            return None
    
    async def list_users(
        self, 
        user_id: str, 
        page_size: Optional[int] = None,
        status: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List users (requires admin permissions)"""
        try:
            params = {
                'page_size': page_size or self.default_page_size
            }
            
            if status:
                params['status'] = status
            if role_id:
                params['role_id'] = role_id
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', '/users', params=params
            )
            
            return response_data.get('users', [])
            
        except Exception as e:
            logger.error(f"Failed to list users for user {user_id}: {e}")
            return []
    
    # === REPORTS MANAGEMENT ===
    
    async def get_meeting_report(
        self, 
        user_id: str, 
        meeting_id: str, 
        report_type: str = 'participants'
    ) -> Optional[Dict[str, Any]]:
        """Get meeting report"""
        try:
            endpoint = f'/report/meetings/{meeting_id}'
            if report_type == 'participants':
                endpoint += '/participants'
            elif report_type == 'polls':
                endpoint += '/polls'
            elif report_type == 'qa':
                endpoint += '/qa'
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', endpoint
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get {report_type} report for meeting {meeting_id}: {e}")
            return None
    
    async def get_user_report(
        self, 
        user_id: str, 
        report_request: ZoomReportRequest
    ) -> Optional[Dict[str, Any]]:
        """Get user report"""
        try:
            params = {
                'from': report_request.from_date,
                'to': report_request.to_date
            }
            
            if report_request.user_ids:
                params['user_ids'] = ','.join(report_request.user_ids)
            if report_request.meeting_ids:
                params['meeting_ids'] = ','.join(report_request.meeting_ids)
            
            endpoint = f'/report/{report_request.report_type}'
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', endpoint, params=params
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get {report_request.report_type} report: {e}")
            return None
    
    # === CHAT MANAGEMENT ===
    
    async def get_chat_channels(
        self, 
        user_id: str, 
        page_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get chat channels"""
        try:
            params = {
                'page_size': page_size or self.default_page_size
            }
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', '/chat/users/me/channels', params=params
            )
            
            return response_data.get('channels', [])
            
        except Exception as e:
            logger.error(f"Failed to get chat channels for user {user_id}: {e}")
            return []
    
    async def get_chat_messages(
        self, 
        user_id: str, 
        channel_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get chat messages"""
        try:
            params = {
                'page_size': page_size or self.default_page_size
            }
            
            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date
            
            response_data = await self._make_authenticated_request(
                user_id, 'GET', f'/chat/channels/{channel_id}/messages', params=params
            )
            
            return response_data.get('messages', [])
            
        except Exception as e:
            logger.error(f"Failed to get chat messages for channel {channel_id}: {e}")
            return []
    
    # === DASHBOARD AND ANALYTICS ===
    
    async def get_user_dashboard(
        self, 
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get user dashboard data"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'GET', '/dashboard/users/me'
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get dashboard for user {user_id}: {e}")
            return None
    
    async def get_meeting_analytics(
        self, 
        user_id: str,
        meeting_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get meeting analytics"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'GET', f'/metrics/meetings/{meeting_id}'
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get analytics for meeting {meeting_id}: {e}")
            return None
    
    # === UTILITY METHODS ===
    
    async def get_api_usage(
        self, 
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get API usage statistics"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'GET', '/report/zoomdashboard/getusage'
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get API usage for user {user_id}: {e}")
            return None
    
    async def validate_access_token(
        self, 
        user_id: str
    ) -> bool:
        """Validate if access token is valid"""
        try:
            response_data = await self._make_authenticated_request(
                user_id, 'GET', '/users/me'
            )
            
            return response_data.get('id') is not None
            
        except Exception as e:
            logger.error(f"Failed to validate access token for user {user_id}: {e}")
            return False
    
    def get_default_meeting_settings(self) -> Dict[str, Any]:
        """Get default meeting settings"""
        return {
            'host_video': True,
            'participant_video': True,
            'join_before_host': False,
            'mute_upon_entry': True,
            'auto_recording': 'cloud',
            'waiting_room': False,
            'in_meeting': False,
            'watermarks': False,
            'audio_transcript': False
        }
    
    def get_default_webinar_settings(self) -> Dict[str, Any]:
        """Get default webinar settings"""
        return {
            'host_video': True,
            'panelists_video': True,
            'practice_session': True,
            'hd_video': True,
            'on_demand': True,
            'auto_recording': 'cloud',
            'enforce_login': False,
            'allow_multiple_devices': True
        }
    
    # === TOKEN MANAGEMENT ===
    
    async def generate_oauth_url(
        self, 
        user_id: str, 
        state: Optional[str] = None
    ) -> str:
        """Generate OAuth authorization URL"""
        return await self.token_manager.generate_auth_url(user_id, state)
    
    async def exchange_code_for_token(
        self, 
        code: str, 
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for token"""
        try:
            token = await self.token_manager.exchange_code_for_token(code, user_id)
            
            if token:
                return {
                    'success': True,
                    'user_id': token.user_id,
                    'email': token.email,
                    'display_name': token.display_name,
                    'zoom_user_id': token.zoom_user_id
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to exchange code for token'
                }
                
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def revoke_token(self, user_id: str) -> bool:
        """Revoke user token"""
        return await self.token_manager.revoke_token(user_id)
    
    async def close(self):
        """Close API manager"""
        await self.data_synchronizer.close()
        await self.token_manager.close()
        await self.http_client.aclose()
        
        logger.info("Zoom API manager closed")