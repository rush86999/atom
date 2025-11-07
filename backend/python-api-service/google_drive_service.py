"""
Google Drive Service - Core API Integration
Handles authentication, file operations, and API interactions
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import aiofiles
import aiohttp
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

# Google Drive API imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logging.warning("Google Drive API libraries not available")

# Local imports
from loguru import logger
from config import get_config_instance

@dataclass
class GoogleDriveFile:
    """Google Drive file data model"""
    id: str
    name: str
    mime_type: str
    size: int
    created_time: datetime
    modified_time: datetime
    viewed_time: Optional[datetime] = None
    description: Optional[str] = None
    checksum: Optional[str] = None
    version: Optional[str] = None
    web_view_link: Optional[str] = None
    web_content_link: Optional[str] = None
    thumbnail_link: Optional[str] = None
    file_extension: Optional[str] = None
    is_folder: bool = False
    is_shared: bool = False
    is_starred: bool = False
    is_trashed: bool = False
    parents: List[str] = None
    permissions: List[Dict] = None
    owners: List[Dict] = None
    last_modified_by: Optional[str] = None
    quota_used: int = 0
    checksum_md5: Optional[str] = None
    checksum_sha1: Optional[str] = None
    checksum_sha256: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization"""
        if self.parents is None:
            self.parents = []
        if self.permissions is None:
            self.permissions = []
        if self.owners is None:
            self.owners = []

@dataclass
class GoogleDriveUser:
    """Google Drive user data model"""
    user_id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    total_quota: int = 0
    used_quota: int = 0
    remaining_quota: int = 0
    
    @property
    def quota_percentage(self) -> float:
        """Calculate quota usage percentage"""
        if self.total_quota == 0:
            return 0.0
        return (self.used_quota / self.total_quota) * 100.0

class GoogleDriveService:
    """Google Drive Service - Main API integration"""
    
    def __init__(self, config=None):
        self.config = config or get_config_instance()
        self.google_drive_config = self.config.google_drive
        
        if not GOOGLE_DRIVE_AVAILABLE:
            raise ImportError("Google Drive API libraries not available. Install: pip install google-api-python-client google-auth-oauthlib")
        
        # OAuth flow
        self.flow: Optional[Flow] = None
        self.credentials: Optional[Credentials] = None
        self.service: Optional[Any] = None
        
        # Session for HTTP requests
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Cache for performance
        self._files_cache: Dict[str, GoogleDriveFile] = {}
        self._user_cache: Optional[GoogleDriveUser] = None
        
        logger.info("Google Drive Service initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.google_drive_config.api_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close service and cleanup resources"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
        self.service = None
        self.credentials = None
        logger.debug("Google Drive Service closed")
    
    # ==================== AUTHENTICATION ====================
    
    def create_oauth_flow(self, redirect_uri: Optional[str] = None, state: Optional[str] = None) -> str:
        """Create OAuth flow and return authorization URL"""
        
        try:
            self.flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": self.google_drive_config.client_id,
                        "client_secret": self.google_drive_config.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token"
                    }
                },
                scopes=self.google_drive_config.scopes,
                redirect_uri=redirect_uri or self.google_drive_config.redirect_uri
            )
            
            if state:
                self.flow.state = state
            
            # Generate authorization URL
            authorization_url, state = self.flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            logger.info(f"OAuth flow created for redirect: {redirect_uri}")
            return authorization_url
        
        except Exception as e:
            logger.error(f"Failed to create OAuth flow: {e}")
            raise
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        
        try:
            await self._ensure_session()
            
            if not self.flow:
                self.flow = Flow.from_client_config(
                    client_config={
                        "web": {
                            "client_id": self.google_drive_config.client_id,
                            "client_secret": self.google_drive_config.client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token"
                        }
                    },
                    scopes=self.google_drive_config.scopes,
                    redirect_uri=redirect_uri or self.google_drive_config.redirect_uri
                )
            
            # Exchange code for tokens
            self.flow.fetch_token(code=code)
            
            # Get credentials
            credentials = self.flow.credentials
            
            # Store credentials
            await self._store_credentials(credentials)
            
            # Initialize service
            await self._initialize_service(credentials)
            
            # Get user info
            user = await self.get_user_info()
            
            return {
                "success": True,
                "user": asdict(user) if user else None,
                "tokens": {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "expires_at": credentials.expiry.isoformat() if credentials.expiry else None,
                    "scope": credentials.scopes
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        
        try:
            await self._ensure_session()
            
            # Create credentials from refresh token
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.google_drive_config.client_id,
                client_secret=self.google_drive_config.client_secret,
                scopes=self.google_drive_config.scopes
            )
            
            # Refresh the token
            request = Request()
            credentials.refresh(request)
            
            # Store new credentials
            await self._initialize_service(credentials)
            await self._store_credentials(credentials)
            
            return {
                "success": True,
                "access_token": credentials.token,
                "expires_at": credentials.expiry.isoformat() if credentials.expiry else None
            }
        
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_credentials(self, credentials: Credentials, user_id: Optional[str] = None):
        """Store credentials in cache or database"""
        # This would integrate with your token storage system
        # For now, store in memory
        self.credentials = credentials
        logger.debug(f"Credentials stored for user: {user_id}")
    
    async def _initialize_service(self, credentials: Credentials):
        """Initialize Google Drive API service"""
        try:
            self.service = build('drive', 'v3', credentials=credentials)
            self.credentials = credentials
            logger.info("Google Drive API service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise
    
    # ==================== USER OPERATIONS ====================
    
    async def get_user_info(self) -> Optional[GoogleDriveUser]:
        """Get current user information"""
        
        try:
            if not self.service:
                raise ValueError("Google Drive service not initialized")
            
            # Get user info
            about_result = self.service.about().get(fields="user, storageQuota").execute()
            
            about_data = about_result.get('about', {})
            user_data = about_data.get('user', {})
            storage_data = about_data.get('storageQuota', {})
            
            # Create user object
            user = GoogleDriveUser(
                user_id=user_data.get('emailAddress', ''),
                email=user_data.get('emailAddress', ''),
                name=user_data.get('displayName', ''),
                avatar_url=user_data.get('photo', {}).get('link'),
                locale=user_data.get('locale'),
                timezone=user_data.get('timezone'),
                total_quota=int(storage_data.get('limit', 0)),
                used_quota=int(storage_data.get('usage', 0)),
                remaining_quota=int(storage_data.get('usageInDrive', 0))
            )
            
            self._user_cache = user
            return user
        
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None
    
    async def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status"""
        
        try:
            if not self.credentials or not self.service:
                return {
                    "connected": False,
                    "authenticated": False,
                    "error": "Not authenticated"
                }
            
            # Check if token is expired
            if self.credentials.expired and self.credentials.refresh_token:
                # Try to refresh
                refresh_result = await self.refresh_token(self.credentials.refresh_token)
                if not refresh_result["success"]:
                    return {
                        "connected": False,
                        "authenticated": False,
                        "error": "Token refresh failed"
                    }
            
            # Test API connection
            user = await self.get_user_info()
            
            if not user:
                return {
                    "connected": False,
                    "authenticated": True,
                    "error": "API test failed"
                }
            
            return {
                "connected": True,
                "authenticated": True,
                "user": asdict(user),
                "quota_usage": user.quota_percentage,
                "expires_at": self.credentials.expiry.isoformat() if self.credentials.expiry else None
            }
        
        except Exception as e:
            logger.error(f"Failed to get connection status: {e}")
            return {
                "connected": False,
                "authenticated": False,
                "error": str(e)
            }
    
    # ==================== FILE OPERATIONS ====================
    
    async def list_files(self, 
                        query: Optional[str] = None,
                        page_size: int = 100,
                        page_token: Optional[str] = None,
                        order_by: str = "modifiedTime desc",
                        fields: str = None) -> Dict[str, Any]:
        """List files from Google Drive"""
        
        try:
            if not self.service:
                raise ValueError("Google Drive service not initialized")
            
            # Default fields
            if not fields:
                fields = "nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, viewedTime, description, version, webViewLink, webContentLink, thumbnailLink, fileExtension, shared, starred, trashed, parents, permissions, owners, lastModifyingUser, quotaBytesUsed, md5Checksum, sha1Checksum, sha256Checksum)"
            
            # Build request
            request = self.service.files().list(
                q=query,
                pageSize=page_size,
                pageToken=page_token,
                orderBy=order_by,
                fields=fields,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True
            )
            
            # Execute request
            result = request.execute()
            
            # Convert to file objects
            files = []
            for file_data in result.get('files', []):
                file_obj = await self._parse_file_data(file_data)
                if file_obj:
                    files.append(asdict(file_obj))
                    # Cache file
                    self._files_cache[file_obj.id] = file_obj
            
            return {
                "success": True,
                "files": files,
                "total_count": len(files),
                "next_page_token": result.get('nextPageToken'),
                "has_more": 'nextPageToken' in result
            }
        
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            return {
                "success": False,
                "error": f"API Error: {e.error_code}",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_file(self, file_id: str, fields: str = None) -> Dict[str, Any]:
        """Get file metadata"""
        
        try:
            # Check cache first
            if file_id in self._files_cache:
                return {
                    "success": True,
                    "file": asdict(self._files_cache[file_id])
                }
            
            if not self.service:
                raise ValueError("Google Drive service not initialized")
            
            # Default fields
            if not fields:
                fields = "id, name, mimeType, size, createdTime, modifiedTime, viewedTime, description, version, webViewLink, webContentLink, thumbnailLink, fileExtension, shared, starred, trashed, parents, permissions, owners, lastModifyingUser, quotaBytesUsed, md5Checksum, sha1Checksum, sha256Checksum"
            
            # Get file
            file_result = self.service.files().get(
                fileId=file_id,
                fields=fields,
                supportsAllDrives=True
            ).execute()
            
            # Convert to file object
            file_obj = await self._parse_file_data(file_result)
            if not file_obj:
                return {
                    "success": False,
                    "error": "File not found"
                }
            
            # Cache file
            self._files_cache[file_id] = file_obj
            
            return {
                "success": True,
                "file": asdict(file_obj)
            }
        
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            if e.resp.status == 404:
                return {
                    "success": False,
                    "error": "File not found",
                    "not_found": True
                }
            return {
                "success": False,
                "error": f"API Error: {e.error_code}",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Failed to get file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def download_file(self, file_id: str, file_path: str, chunk_size: int = 1024*1024) -> Dict[str, Any]:
        """Download file from Google Drive"""
        
        try:
            if not self.service:
                raise ValueError("Google Drive service not initialized")
            
            # Get file metadata first
            file_result = await self.get_file(file_id)
            if not file_result["success"]:
                return file_result
            
            file_data = file_result["file"]
            
            # Create directory if needed
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            
            with open(file_path, 'wb') as file:
                downloader = MediaIoBaseDownload(file, chunksize=chunk_size)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download {int(status.progress() * 100)}%")
            
            logger.info(f"File downloaded: {file_data['name']} -> {file_path}")
            
            return {
                "success": True,
                "file_id": file_id,
                "file_name": file_data["name"],
                "file_path": file_path,
                "file_size": file_data.get("size", 0),
                "mime_type": file_data.get("mime_type", "")
            }
        
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            return {
                "success": False,
                "error": f"API Error: {e.error_code}",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_file(self, 
                        file_path: str, 
                        file_name: Optional[str] = None,
                        parent_id: Optional[str] = None,
                        mime_type: Optional[str] = None,
                        chunk_size: int = 1024*1024) -> Dict[str, Any]:
        """Upload file to Google Drive"""
        
        try:
            if not self.service:
                raise ValueError("Google Drive service not initialized")
            
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {
                    "success": False,
                    "error": "File not found"
                }
            
            # File metadata
            file_name = file_name or file_path_obj.name
            file_metadata = {
                "name": file_name,
            }
            
            if parent_id:
                file_metadata["parents"] = [parent_id]
            
            # Determine mime type
            if not mime_type:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = "application/octet-stream"
            
            # Create media upload
            media = MediaIoBaseUpload(
                open(file_path, 'rb'),
                mimetype=mime_type,
                chunksize=chunk_size,
                resumable=True
            )
            
            # Upload file
            file_result = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, parents"
            ).execute()
            
            # Parse result
            uploaded_file = await self._parse_file_data(file_result)
            
            logger.info(f"File uploaded: {file_name} -> {uploaded_file.id}")
            
            # Clear cache
            self._files_cache.clear()
            
            return {
                "success": True,
                "file": asdict(uploaded_file) if uploaded_file else None
            }
        
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            return {
                "success": False,
                "error": f"API Error: {e.error_code}",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        """Delete file from Google Drive"""
        
        try:
            if not self.service:
                raise ValueError("Google Drive service not initialized")
            
            # Delete file
            self.service.files().delete(
                fileId=file_id,
                supportsAllDrives=True
            ).execute()
            
            # Remove from cache
            if file_id in self._files_cache:
                del self._files_cache[file_id]
            
            logger.info(f"File deleted: {file_id}")
            
            return {
                "success": True,
                "file_id": file_id
            }
        
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            if e.resp.status == 404:
                return {
                    "success": False,
                    "error": "File not found",
                    "not_found": True
                }
            return {
                "success": False,
                "error": f"API Error: {e.error_code}",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_file(self, 
                        file_id: str,
                        file_path: Optional[str] = None,
                        file_name: Optional[str] = None,
                        parent_id: Optional[str] = None,
                        add_parents: Optional[str] = None,
                        remove_parents: Optional[str] = None,
                        mime_type: Optional[str] = None,
                        chunk_size: int = 1024*1024) -> Dict[str, Any]:
        """Update file in Google Drive"""
        
        try:
            if not self.service:
                raise ValueError("Google Drive service not initialized")
            
            # Prepare file metadata
            file_metadata = {}
            
            if file_name:
                file_metadata["name"] = file_name
            
            if parent_id:
                file_metadata["parents"] = [parent_id]
            
            # Determine mime type for file upload
            media = None
            if file_path:
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    return {
                        "success": False,
                        "error": "File not found"
                    }
                
                if not mime_type:
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(file_path)
                    if not mime_type:
                        mime_type = "application/octet-stream"
                
                media = MediaIoBaseUpload(
                    open(file_path, 'rb'),
                    mimetype=mime_type,
                    chunksize=chunk_size,
                    resumable=True
                )
            
            # Update file
            if add_parents or remove_parents:
                # Handle parent changes
                if add_parents:
                    self.service.files().update(
                        fileId=file_id,
                        addParents=add_parents
                    ).execute()
                
                if remove_parents:
                    self.service.files().update(
                        fileId=file_id,
                        removeParents=remove_parents
                    ).execute()
            
            # Update file content/metadata
            fields = "id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, parents"
            file_result = self.service.files().update(
                fileId=file_id,
                body=file_metadata if file_metadata else None,
                media_body=media,
                fields=fields,
                supportsAllDrives=True
            ).execute()
            
            # Parse result
            updated_file = await self._parse_file_data(file_result)
            
            # Update cache
            if updated_file:
                self._files_cache[file_id] = updated_file
            
            logger.info(f"File updated: {file_id}")
            
            return {
                "success": True,
                "file": asdict(updated_file) if updated_file else None
            }
        
        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            if e.resp.status == 404:
                return {
                    "success": False,
                    "error": "File not found",
                    "not_found": True
                }
            return {
                "success": False,
                "error": f"API Error: {e.error_code}",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Failed to update file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_files(self, 
                         query: str,
                         page_size: int = 100,
                         page_token: Optional[str] = None,
                         order_by: str = "relevance desc",
                         fields: str = None) -> Dict[str, Any]:
        """Search files in Google Drive"""
        
        try:
            # Build search query
            if query:
                search_query = f"name contains '{query}' or fullText contains '{query}'"
            else:
                search_query = None
            
            return await self.list_files(
                query=search_query,
                page_size=page_size,
                page_token=page_token,
                order_by=order_by,
                fields=fields
            )
        
        except Exception as e:
            logger.error(f"Failed to search files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== UTILITY METHODS ====================
    
    async def _parse_file_data(self, file_data: Dict[str, Any]) -> Optional[GoogleDriveFile]:
        """Parse file data from API response"""
        
        try:
            # Handle both string and datetime for time fields
            def parse_time(time_value):
                if isinstance(time_value, str):
                    return datetime.fromisoformat(time_value.replace('Z', '+00:00'))
                elif isinstance(time_value, datetime):
                    return time_value
                return None
            
            return GoogleDriveFile(
                id=file_data.get('id', ''),
                name=file_data.get('name', ''),
                mime_type=file_data.get('mimeType', ''),
                size=int(file_data.get('size', 0)),
                created_time=parse_time(file_data.get('createdTime')),
                modified_time=parse_time(file_data.get('modifiedTime')),
                viewed_time=parse_time(file_data.get('viewedTime')),
                description=file_data.get('description'),
                checksum=file_data.get('checksum'),
                version=file_data.get('version'),
                web_view_link=file_data.get('webViewLink'),
                web_content_link=file_data.get('webContentLink'),
                thumbnail_link=file_data.get('thumbnailLink'),
                file_extension=file_data.get('fileExtension'),
                is_folder=file_data.get('mimeType') == 'application/vnd.google-apps.folder',
                is_shared=file_data.get('shared', False),
                is_starred=file_data.get('starred', False),
                is_trashed=file_data.get('trashed', False),
                parents=file_data.get('parents', []),
                permissions=file_data.get('permissions', []),
                owners=file_data.get('owners', []),
                last_modified_by=file_data.get('lastModifyingUser', {}).get('emailAddress'),
                quota_used=int(file_data.get('quotaBytesUsed', 0)),
                checksum_md5=file_data.get('md5Checksum'),
                checksum_sha1=file_data.get('sha1Checksum'),
                checksum_sha256=file_data.get('sha256Checksum')
            )
        
        except Exception as e:
            logger.error(f"Failed to parse file data: {e}")
            return None
    
    def clear_cache(self):
        """Clear file and user cache"""
        self._files_cache.clear()
        self._user_cache = None
        logger.debug("Google Drive cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "files_cached": len(self._files_cache),
            "user_cached": self._user_cache is not None
        }

# Global service instance
_google_drive_service: Optional[GoogleDriveService] = None

async def get_google_drive_service() -> Optional[GoogleDriveService]:
    """Get global Google Drive service instance"""
    
    global _google_drive_service
    
    if _google_drive_service is None:
        try:
            config = get_config_instance()
            _google_drive_service = GoogleDriveService(config)
            logger.info("Google Drive service created")
        except Exception as e:
            logger.error(f"Failed to create Google Drive service: {e}")
            _google_drive_service = None
    
    return _google_drive_service

def clear_google_drive_service():
    """Clear global Google Drive service instance"""
    
    global _google_drive_service
    _google_drive_service = None
    logger.info("Google Drive service cleared")

# Export classes and functions
__all__ = [
    'GoogleDriveService',
    'GoogleDriveFile',
    'GoogleDriveUser',
    'get_google_drive_service',
    'clear_google_drive_service'
]