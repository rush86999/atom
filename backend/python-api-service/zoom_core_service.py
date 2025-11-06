#!/usr/bin/env python3
"""
🚀 Zoom Core Service
Enterprise-grade Zoom API integration with comprehensive meeting management
"""

import os
import json
import logging
import requests
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlencode
from enum import Enum

import asyncpg

logger = logging.getLogger(__name__)

class ZoomMeetingType(Enum):
    """Zoom meeting types"""
    INSTANT = 1
    SCHEDULED = 2
    RECURRING_WITH_FIXED_TIME = 3
    RECURRING_WITH_NO_FIXED_TIME = 8

class ZoomRecordingType(Enum):
    """Zoom recording types"""
    SHARED_SCREEN_WITH_SPEAKER_VIEW = "shared_screen_with_speaker_view"
    SHARED_SCREEN_WITH_GALLERY_VIEW = "shared_screen_with_gallery_view"
    ACTIVE_SPEAKER = "active_speaker"
    GALLERY_VIEW = "gallery_view"
    AUDIO_ONLY = "audio_only"
    CHAT_FILE = "chat_file"
    TRANSCRIPT = "transcript"

@dataclass
class ZoomCredentials:
    """Zoom API credentials"""
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime
    user_id: str
    email: str
    account_id: str

@dataclass
class ZoomMeeting:
    """Zoom meeting object"""
    id: Optional[int] = None
    uuid: Optional[str] = None
    topic: str = ""
    agenda: Optional[str] = None
    start_time: Optional[datetime] = None
    duration: Optional[int] = None
    timezone: str = "UTC"
    meeting_type: int = ZoomMeetingType.SCHEDULED.value
    password: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

@dataclass
class ZoomRecordingFile:
    """Zoom recording file object"""
    id: str
    download_url: str
    play_url: str
    recording_type: str
    file_size: int
    file_type: str
    recording_start: datetime
    recording_end: datetime

class ZoomAPIError(Exception):
    """Zoom API specific error"""
    
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code

class ZoomCoreService:
    """Enterprise-grade Zoom API service"""
    
    def __init__(self, db_pool: asyncpg.Pool = None):
        self.db_pool = db_pool
        self.session = requests.Session()
        self.session.timeout = 30
        self._setup_session()
    
    def _setup_session(self):
        """Configure HTTP session for Zoom API"""
        self.session.headers.update({
            'User-Agent': 'ATOM-Enterprise-Zoom/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    async def get_credentials(self, user_id: str, email: str = None) -> Optional[ZoomCredentials]:
        """
        Retrieve Zoom credentials for user
        
        Args:
            user_id: Internal user identifier
            email: User email (alternative identifier)
            
        Returns:
            ZoomCredentials or None if not found
        """
        try:
            from db_oauth_zoom import get_user_zoom_tokens
            
            tokens = await get_user_zoom_tokens(self.db_pool, user_id)
            
            if not tokens:
                logger.warning(f"No Zoom tokens found for user: {user_id}")
                return None
            
            # Check if token is expired
            expires_at = datetime.fromisoformat(tokens["expires_at"].replace('Z', '+00:00'))
            if expires_at < datetime.now(timezone.utc):
                logger.warning(f"Zoom token expired for user: {user_id}")
                return None
            
            return ZoomCredentials(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_type=tokens["token_type"],
                expires_at=expires_at,
                user_id=tokens["zoom_user_id"],
                email=tokens["email"],
                account_id=tokens.get("account_id")
            )
            
        except Exception as e:
            logger.error(f"Error retrieving Zoom credentials: {e}")
            return None
    
    def _make_api_request(
        self,
        credentials: ZoomCredentials,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated API request to Zoom
        
        Args:
            credentials: Valid Zoom credentials
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            params: Query parameters
            
        Returns:
            API response dictionary
        """
        try:
            # Build full URL
            base_url = "https://api.zoom.us/v2"
            if not endpoint.startswith('/'):
                endpoint = f'/{endpoint}'
            
            url = urljoin(base_url, endpoint)
            
            # Prepare headers with authentication
            headers = {
                'Authorization': f'Bearer {credentials.access_token}'
            }
            
            # Make request
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=params
            )
            
            # Log API usage
            self._log_api_usage(
                credentials.user_id,
                credentials.email,
                f"{method} {endpoint}",
                len(str(data)) if data else 0,
                response.status_code < 400,
                None if response.status_code < 400 else response.text
            )
            
            # Handle response
            if response.status_code == 200:
                return response.json() if response.content else {}
            elif response.status_code == 201:  # Created
                return response.json() if response.content else {}
            elif response.status_code == 204:  # No content
                return {}
            else:
                # Parse error response
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', error_data.get('error', 'Unknown error'))
                    error_code = error_data.get('code', 'UNKNOWN_ERROR')
                except:
                    error_message = response.text
                    error_code = 'HTTP_ERROR'
                
                raise ZoomAPIError(
                    message=error_message,
                    status_code=response.status_code,
                    error_code=error_code
                )
        
        except ZoomAPIError:
            raise
        except requests.exceptions.Timeout:
            raise ZoomAPIError(
                message="Request timeout",
                status_code=408,
                error_code="TIMEOUT_ERROR"
            )
        except requests.exceptions.RequestException as e:
            raise ZoomAPIError(
                message=f"Network error: {str(e)}",
                error_code="NETWORK_ERROR"
            )
        except Exception as e:
            raise ZoomAPIError(
                message=f"Unexpected error: {str(e)}",
                error_code="UNKNOWN_ERROR"
            )
    
    async def refresh_credentials(self, credentials: ZoomCredentials) -> Optional[ZoomCredentials]:
        """
        Refresh expired Zoom credentials
        
        Args:
            credentials: Expired credentials
            
        Returns:
            New credentials or None if refresh failed
        """
        try:
            from auth_handler_zoom import get_zoom_oauth_handler
            from db_oauth_zoom import refresh_user_zoom_tokens
            
            # Use OAuth handler to refresh token
            oauth_handler = get_zoom_oauth_handler(self.db_pool)
            refresh_result = oauth_handler.refresh_token(credentials.refresh_token)
            
            if not refresh_result.get("ok"):
                logger.error(f"Zoom token refresh failed: {refresh_result}")
                return None
            
            # Update database with new tokens
            new_tokens = refresh_result["tokens"]
            new_expires_at = datetime.fromisoformat(new_tokens["expires_at"].replace('Z', '+00:00'))
            
            update_result = await refresh_user_zoom_tokens(
                self.db_pool,
                credentials.user_id,
                new_tokens["access_token"],
                new_tokens["refresh_token"],
                new_expires_at
            )
            
            if not update_result["success"]:
                logger.error(f"Failed to update Zoom tokens: {update_result}")
                return None
            
            # Return new credentials
            return ZoomCredentials(
                access_token=new_tokens["access_token"],
                refresh_token=new_tokens["refresh_token"],
                token_type=new_tokens.get("token_type", "Bearer"),
                expires_at=new_expires_at,
                user_id=credentials.user_id,
                email=credentials.email,
                account_id=credentials.account_id
            )
            
        except Exception as e:
            logger.error(f"Error refreshing Zoom credentials: {e}")
            return None
    
    def _log_api_usage(
        self,
        user_id: str,
        email: str,
        api_endpoint: str,
        data_transferred: int,
        success: bool,
        error_message: str
    ) -> None:
        """Log API usage for analytics"""
        try:
            if self.db_pool:
                asyncio.create_task(
                    self._log_api_usage_async(
                        user_id, email, api_endpoint, 
                        data_transferred, success, error_message
                    )
                )
        except Exception as e:
            logger.error(f"Failed to log API usage: {e}")
    
    async def _log_api_usage_async(
        self,
        user_id: str,
        email: str,
        api_endpoint: str,
        data_transferred: int,
        success: bool,
        error_message: str
    ) -> None:
        """Async API usage logging"""
        try:
            from db_oauth_zoom import log_api_usage
            await log_api_usage(
                self.db_pool, user_id, api_endpoint,
                data_transferred, success, error_message
            )
        except Exception as e:
            logger.error(f"Failed to log API usage async: {e}")
    
    # MEETING MANAGEMENT
    
    async def create_meeting(
        self,
        user_id: str,
        meeting: ZoomMeeting,
        email: str = None
    ) -> Dict[str, Any]:
        """
        Create new Zoom meeting
        
        Args:
            user_id: Internal user ID
            meeting: Meeting data
            email: User email (optional)
            
        Returns:
            Dictionary with creation result
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Prepare meeting data
            meeting_data = {
                "topic": meeting.topic,
                "type": meeting.meeting_type,
                "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
                "duration": meeting.duration,
                "timezone": meeting.timezone,
                "agenda": meeting.agenda,
                "password": meeting.password
            }
            
            # Add settings if provided
            if meeting.settings:
                meeting_data["settings"] = meeting.settings
            else:
                # Default settings
                meeting_data["settings"] = {
                    "host_video": True,
                    "participant_video": True,
                    "cn_meeting": False,
                    "in_meeting": False,
                    "join_before_host": False,
                    "mute_upon_entry": True,
                    "watermark": False,
                    "use_pmi": False,
                    "approval_type": 0,
                    "audio": "both",
                    "auto_recording": "none"
                }
            
            # Create meeting
            response = self._make_api_request(
                credentials=credentials,
                method="POST",
                endpoint="users/me/meetings",
                data=meeting_data
            )
            
            # Store meeting metadata
            if response.get("id"):
                from db_oauth_zoom import store_meeting_metadata
                await store_meeting_metadata(self.db_pool, user_id, response)
            
            logger.info(f"✅ Successfully created Zoom meeting: {response.get('id')}")
            
            return {
                "ok": True,
                "meeting": response,
                "message": "Meeting created successfully"
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom create meeting error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in create meeting: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    async def list_meetings(
        self,
        user_id: str,
        email: str = None,
        meeting_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page_size: int = 30,
        page_number: int = 1
    ) -> Dict[str, Any]:
        """
        List Zoom meetings
        
        Args:
            user_id: Internal user ID
            email: User email (optional)
            meeting_type: Filter by meeting type (scheduled, live, upcoming)
            from_date: Filter meetings from this date
            to_date: Filter meetings to this date
            page_size: Number of meetings per page
            page_number: Page number for pagination
            
        Returns:
            Dictionary with meetings list and metadata
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build query parameters
            params = {
                "page_size": min(page_size, 300),  # Zoom limit
                "page_number": page_number
            }
            
            if meeting_type:
                params["type"] = meeting_type
            if from_date:
                params["from"] = from_date.strftime("%Y-%m-%d")
            if to_date:
                params["to"] = to_date.strftime("%Y-%m-%d")
            
            # Get meetings
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint="users/me/meetings",
                params=params
            )
            
            # Store meeting metadata for each meeting
            if response.get("meetings"):
                from db_oauth_zoom import store_meeting_metadata
                for meeting in response["meetings"]:
                    await store_meeting_metadata(self.db_pool, user_id, meeting)
            
            logger.info(f"✅ Retrieved {len(response.get('meetings', []))} Zoom meetings")
            
            return {
                "ok": True,
                "meetings": response.get("meetings", []),
                "total_records": response.get("total_records", 0),
                "page_number": response.get("page_number", page_number),
                "page_size": response.get("page_size", page_size),
                "next_page_token": response.get("next_page_token")
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom list meetings error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in list meetings: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    async def get_meeting(
        self,
        user_id: str,
        meeting_id: int,
        email: str = None,
        include_schedule_details: bool = False
    ) -> Dict[str, Any]:
        """
        Get specific Zoom meeting
        
        Args:
            user_id: Internal user ID
            meeting_id: Zoom meeting ID
            email: User email (optional)
            include_schedule_details: Include scheduling details
            
        Returns:
            Dictionary with meeting data
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build endpoint with optional parameters
            endpoint = f"meetings/{meeting_id}"
            params = {}
            
            if include_schedule_details:
                params["include_schedule_details"] = "true"
            
            # Get meeting
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint=endpoint,
                params=params
            )
            
            logger.info(f"✅ Retrieved Zoom meeting: {meeting_id}")
            
            return {
                "ok": True,
                "meeting": response
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom get meeting error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in get meeting: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    async def update_meeting(
        self,
        user_id: str,
        meeting_id: int,
        meeting_updates: Dict[str, Any],
        email: str = None
    ) -> Dict[str, Any]:
        """
        Update Zoom meeting
        
        Args:
            user_id: Internal user ID
            meeting_id: Zoom meeting ID
            meeting_updates: Meeting data to update
            email: User email (optional)
            
        Returns:
            Dictionary with update result
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Update meeting
            response = self._make_api_request(
                credentials=credentials,
                method="PATCH",
                endpoint=f"meetings/{meeting_id}",
                data=meeting_updates
            )
            
            # Update meeting metadata
            from db_oauth_zoom import store_meeting_metadata
            updated_meeting = await self.get_meeting(user_id, meeting_id, email)
            if updated_meeting.get("ok"):
                await store_meeting_metadata(self.db_pool, user_id, updated_meeting["meeting"])
            
            logger.info(f"✅ Successfully updated Zoom meeting: {meeting_id}")
            
            return {
                "ok": True,
                "meeting": response,
                "message": "Meeting updated successfully"
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom update meeting error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in update meeting: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    async def delete_meeting(
        self,
        user_id: str,
        meeting_id: int,
        email: str = None,
        notify_users: bool = False
    ) -> Dict[str, Any]:
        """
        Delete Zoom meeting
        
        Args:
            user_id: Internal user ID
            meeting_id: Zoom meeting ID
            email: User email (optional)
            notify_users: Whether to notify registrants
            
        Returns:
            Dictionary with deletion result
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build query parameters
            params = {
                "schedule_for_reminder": "true" if notify_users else "false"
            }
            
            # Delete meeting
            response = self._make_api_request(
                credentials=credentials,
                method="DELETE",
                endpoint=f"meetings/{meeting_id}",
                params=params
            )
            
            # Update meeting status in database
            from db_oauth_zoom import update_meeting_status
            await update_meeting_status(
                self.db_pool,
                meeting_id,
                "deleted"
            )
            
            logger.info(f"✅ Successfully deleted Zoom meeting: {meeting_id}")
            
            return {
                "ok": True,
                "message": "Meeting deleted successfully",
                "meeting_id": meeting_id
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom delete meeting error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in delete meeting: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    async def get_meeting_invitation(
        self,
        user_id: str,
        meeting_id: int,
        email: str = None
    ) -> Dict[str, Any]:
        """
        Get meeting invitation details
        
        Args:
            user_id: Internal user ID
            meeting_id: Zoom meeting ID
            email: User email (optional)
            
        Returns:
            Dictionary with invitation details
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Get invitation
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint=f"meetings/{meeting_id}/invitation"
            )
            
            logger.info(f"✅ Retrieved Zoom meeting invitation: {meeting_id}")
            
            return {
                "ok": True,
                "invitation": response
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom get meeting invitation error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in get meeting invitation: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    # RECORDING MANAGEMENT
    
    async def get_meeting_recordings(
        self,
        user_id: str,
        meeting_id: int,
        email: str = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page_size: int = 30,
        include_download_token: bool = True
    ) -> Dict[str, Any]:
        """
        Get meeting recordings
        
        Args:
            user_id: Internal user ID
            meeting_id: Zoom meeting ID
            email: User email (optional)
            from_date: Filter recordings from this date
            to_date: Filter recordings to this date
            page_size: Number of recordings per page
            include_download_token: Include download token
            
        Returns:
            Dictionary with recordings
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build query parameters
            params = {
                "page_size": min(page_size, 300),  # Zoom limit
                "include_download_token": "true" if include_download_token else "false"
            }
            
            if from_date:
                params["from"] = from_date.strftime("%Y-%m-%d")
            if to_date:
                params["to"] = to_date.strftime("%Y-%m-%d")
            
            # Get recordings
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint=f"meetings/{meeting_id}/recordings",
                params=params
            )
            
            # Store recording metadata
            if response.get("recording_files"):
                from db_oauth_zoom import update_meeting_status
                recording_files = response["recording_files"]
                
                await update_meeting_status(
                    self.db_pool,
                    meeting_id,
                    "completed",
                    {"recording_files": recording_files}
                )
            
            logger.info(f"✅ Retrieved {len(response.get('recording_files', []))} Zoom recordings")
            
            return {
                "ok": True,
                "topic": response.get("topic"),
                "start_time": response.get("start_time"),
                "timezone": response.get("timezone"),
                "recording_files": response.get("recording_files", []),
                "password": response.get("password"),
                "share_url": response.get("share_url"),
                "download_url": response.get("download_url")
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom get recordings error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in get recordings: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    # USER MANAGEMENT
    
    async def get_user_profile(
        self,
        user_id: str,
        email: str = None
    ) -> Dict[str, Any]:
        """
        Get Zoom user profile information
        
        Args:
            user_id: Internal user ID
            email: User email (optional)
            
        Returns:
            Dictionary with user profile
        """
        try:
            credentials = await self.get_credentials(user_id, email)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Get user profile
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint="users/me"
            )
            
            logger.info(f"✅ Retrieved Zoom user profile for: {credentials.email}")
            
            return {
                "ok": True,
                "user": response
            }
            
        except ZoomAPIError as e:
            logger.error(f"Zoom get user profile error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in get user profile: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }

# Global Zoom service instance
zoom_core_service = None

def get_zoom_core_service(db_pool: asyncpg.Pool = None) -> ZoomCoreService:
    """Get or create Zoom service instance"""
    global zoom_core_service
    if zoom_core_service is None:
        zoom_core_service = ZoomCoreService(db_pool)
    return zoom_core_service