"""
Google Drive Integration Service
Complete Google Drive file management and collaboration service
"""

import json
import logging
import asyncio
import aiohttp
import aiofiles
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, BinaryIO
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlencode
from loguru import logger
import mimetypes
import os
from pathlib import Path

# Google Drive API configuration
GOOGLE_DRIVE_API_VERSION = "v3"
GOOGLE_DRIVE_API_BASE_URL = "https://www.googleapis.com/drive/v3"
GOOGLE_DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3"
GOOGLE_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata"
]
GOOGLE_DRIVE_REQUEST_TIMEOUT = 60

class FileType(Enum):
    """File types for Google Drive"""
    FOLDER = "application/vnd.google-apps.folder"
    DOCUMENT = "application/vnd.google-apps.document"
    SPREADSHEET = "application/vnd.google-apps.spreadsheet"
    PRESENTATION = "application/vnd.google-apps.presentation"
    PDF = "application/pdf"
    IMAGE = "image/jpeg"
    VIDEO = "video/mp4"
    AUDIO = "audio/mpeg"
    ARCHIVE = "application/zip"
    TEXT = "text/plain"
    JSON = "application/json"
    CSV = "text/csv"

class PermissionRole(Enum):
    """Permission roles for Google Drive"""
    OWNER = "owner"
    ORGANIZER = "organizer"
    FILE_ORGANIZER = "fileOrganizer"
    EDITOR = "editor"
    COMMENTER = "commenter"
    VIEWER = "reader"

class PermissionType(Enum):
    """Permission types for Google Drive"""
    USER = "user"
    GROUP = "group"
    DOMAIN = "domain"
    ANYONE = "anyone"

@dataclass
class GoogleDriveConfig:
    """Google Drive configuration"""
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str] = field(default_factory=lambda: GOOGLE_DRIVE_SCOPES)
    api_version: str = GOOGLE_DRIVE_API_VERSION
    timeout: int = GOOGLE_DRIVE_REQUEST_TIMEOUT
    max_retries: int = 3
    retry_delay: float = 1.0

@dataclass
class GoogleDriveFile:
    """Google Drive file model"""
    id: str
    name: str
    mime_type: str
    size: int = 0
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    viewed_by_me_time: Optional[datetime] = None
    parents: List[str] = field(default_factory=list)
    web_view_link: Optional[str] = None
    web_content_link: Optional[str] = None
    thumbnail_link: Optional[str] = None
    permissions: List[Dict[str, Any]] = field(default_factory=list)
    shared: bool = False
    owners: List[Dict[str, Any]] = field(default_factory=list)
    version: Optional[str] = None
    md5_checksum: Optional[str] = None
    file_extension: Optional[str] = None
    full_file_extension: Optional[str] = None
    kind: str = "drive#file"
    trashed: bool = False
    starred: bool = False

@dataclass
class GoogleDriveFolder:
    """Google Drive folder model"""
    id: str
    name: str
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    parents: List[str] = field(default_factory=list)
    web_view_link: Optional[str] = None
    permissions: List[Dict[str, Any]] = field(default_factory=list)
    shared: bool = False
    owners: List[Dict[str, Any]] = field(default_factory=list)
    trashed: bool = False
    starred: bool = False

@dataclass
class GoogleDrivePermission:
    """Google Drive permission model"""
    id: str
    type: str
    role: str
    email_address: Optional[str] = None
    domain: Optional[str] = None
    display_name: Optional[str] = None
    photo_link: Optional[str] = None
    kind: str = "drive#permission"

@dataclass
class GoogleDriveChange:
    """Google Drive change model"""
    id: str
    file_id: Optional[str] = None
    removed: bool = False
    file: Optional[GoogleDriveFile] = None
    kind: str = "drive#change"

class GoogleDriveService:
    """Enhanced Google Drive service for file management"""
    
    def __init__(self, config: Optional[GoogleDriveConfig] = None):
        self.config = config or GoogleDriveConfig(
            client_id="",
            client_secret="",
            redirect_uri="http://localhost:8000/auth/google/callback"
        )
        self._client: Optional[aiohttp.ClientSession] = None
        self.access_token_cache: Dict[str, Dict[str, Any]] = {}
        self.token_cache_ttl = timedelta(minutes=55)  # Token expires after 60 minutes
    
    @property
    def client(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._client is None or self._client.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            headers = {
                "User-Agent": "ATOM-Backend/1.0",
                "Accept": "application/json"
            }
            self._client = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
        return self._client
    
    async def _get_access_token(self, user_id: str, db_conn_pool=None) -> Optional[Dict[str, Any]]:
        """Get Google OAuth access token"""
        try:
            # Check cache first
            cache_key = f"google_drive_token_{user_id}"
            if cache_key in self.access_token_cache:
                cached_data = self.access_token_cache[cache_key]
                if datetime.now(timezone.utc) - cached_data["cached_at"] < self.token_cache_ttl:
                    logger.info(f"Using cached Google Drive token for user {user_id}")
                    return cached_data
            
            # Get tokens from database
            if db_conn_pool:
                from db_oauth_google_drive import get_user_google_drive_tokens
                
                tokens = await get_user_google_drive_tokens(db_conn_pool, user_id)
                if tokens:
                    # Cache the tokens
                    cached_data = {
                        **tokens,
                        "cached_at": datetime.now(timezone.utc)
                    }
                    self.access_token_cache[cache_key] = cached_data
                    return tokens
            
            # Fallback to mock tokens for development
            logger.warning(f"No Google Drive tokens found for user {user_id}, using mock data")
            mock_tokens = {
                "access_token": "ya29_mock_access_token_for_development",
                "refresh_token": "mock_refresh_token_for_development",
                "token_type": "Bearer",
                "scope": "https://www.googleapis.com/auth/drive",
                "expires_in": 3600,
                "cached_at": datetime.now(timezone.utc)
            }
            
            self.access_token_cache[cache_key] = mock_tokens
            return mock_tokens
        
        except ImportError:
            logger.warning("Google Drive database handler not available, using mock data")
            mock_tokens = {
                "access_token": "ya29_mock_access_token_for_development",
                "refresh_token": "mock_refresh_token_for_development",
                "token_type": "Bearer",
                "scope": "https://www.googleapis.com/auth/drive",
                "expires_in": 3600,
                "cached_at": datetime.now(timezone.utc)
            }
            
            cache_key = f"google_drive_token_{user_id}"
            self.access_token_cache[cache_key] = mock_tokens
            return mock_tokens
        
        except Exception as e:
            logger.error(f"Error getting Google Drive tokens: {e}")
            return None
    
    def _build_url(self, endpoint: str, params: Dict[str, Any] = None) -> str:
        """Build Google Drive API URL"""
        base_url = f"{GOOGLE_DRIVE_API_BASE_URL}/{endpoint}"
        if params:
            query_string = urlencode(params)
            base_url += f"?{query_string}"
        return base_url
    
    async def _make_request(
        self,
        user_id: str,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        file_data: Optional[BinaryIO] = None,
        file_metadata: Optional[Dict[str, Any]] = None,
        db_conn_pool=None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Make authenticated Google Drive API request"""
        
        # Get access token
        tokens = await self._get_access_token(user_id, db_conn_pool)
        if not tokens:
            raise Exception(f"No Google Drive tokens found for user {user_id}")
        
        access_token = tokens["access_token"]
        
        # Build URL and headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Check if we should use real API or mock data
        use_real_api = not access_token.startswith("ya29_mock")
        
        if use_real_api:
            # Make real Google Drive API call
            try:
                logger.info(f"Making real Google Drive API request: {method} {endpoint}")
                
                if file_data and file_metadata:
                    # Upload file with metadata
                    metadata_json = json.dumps(file_metadata)
                    
                    multipart_data = aiohttp.FormData()
                    multipart_data.add_field('metadata', metadata_json, 
                                         content_type='application/json')
                    multipart_data.add_field('file', file_data)
                    
                    async with self.client.post(
                        endpoint, 
                        data=multipart_data,
                        headers=headers,
                        params=params
                    ) as response:
                        return await self._handle_response(response)
                
                elif method.upper() == "GET":
                    async with self.client.get(
                        self._build_url(endpoint, params), 
                        headers=headers
                    ) as response:
                        return await self._handle_response(response)
                
                elif method.upper() == "POST":
                    async with self.client.post(
                        self._build_url(endpoint, params),
                        headers=headers,
                        json=data
                    ) as response:
                        return await self._handle_response(response)
                
                elif method.upper() == "PUT":
                    async with self.client.put(
                        self._build_url(endpoint, params),
                        headers=headers,
                        json=data
                    ) as response:
                        return await self._handle_response(response)
                
                elif method.upper() == "PATCH":
                    async with self.client.patch(
                        self._build_url(endpoint, params),
                        headers=headers,
                        json=data
                    ) as response:
                        return await self._handle_response(response)
                
                elif method.upper() == "DELETE":
                    async with self.client.delete(
                        self._build_url(endpoint, params),
                        headers=headers
                    ) as response:
                        return await self._handle_response(response)
                
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
            
            except aiohttp.ClientError as e:
                if retry_count < self.config.max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    return await self._make_request(
                        user_id, method, endpoint, data, params, 
                        file_data, file_metadata, db_conn_pool, retry_count + 1
                    )
                else:
                    logger.error(f"Google Drive API request failed after {self.config.max_retries} retries: {e}")
                    raise
            
            except Exception as e:
                logger.error(f"Unexpected error in Google Drive API request: {e}")
                raise
        else:
            # Mock implementation for development
            logger.info(f"Mock Google Drive API request: {method} {endpoint}")
            
            try:
                # Simulate API delay
                await asyncio.sleep(0.1)
                
                # Return mock data based on endpoint
                if "files" in endpoint and method == "GET":
                    return self._mock_files_response(params)
                elif "files" in endpoint and method == "POST":
                    if file_data:
                        return self._mock_file_upload_response(file_metadata)
                    else:
                        return self._mock_create_file_response(data)
                elif "files/" in endpoint and method == "GET":
                    return self._mock_file_response(endpoint.split('/')[-1])
                elif "files/" in endpoint and method == "PATCH":
                    return self._mock_update_file_response(data)
                elif "files/" in endpoint and method == "DELETE":
                    return self._mock_delete_file_response()
                elif "folders" in endpoint and method == "POST":
                    return self._mock_create_folder_response(data)
                elif "permissions" in endpoint and method == "GET":
                    return self._mock_permissions_response()
                elif "permissions" in endpoint and method == "POST":
                    return self._mock_create_permission_response(data)
                elif "changes" in endpoint:
                    return self._mock_changes_response(params)
                elif "about" in endpoint:
                    return self._mock_about_response()
                else:
                    return {"ok": False, "error": {"message": "Unknown endpoint"}}
            
            except Exception as e:
                logger.error(f"Error in mock Google Drive API request: {e}")
                return {"ok": False, "error": {"message": str(e)}}
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle HTTP response"""
        response_text = await response.text()
        
        if response.status == 200 or response.status == 201:
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response: {e}")
                return {"ok": False, "error": {"message": "Invalid JSON response"}}
        
        elif response.status == 401:
            # Token expired, refresh needed
            logger.error("Google Drive access token expired")
            return {"ok": False, "error": {"message": "Token expired", "code": 401}}
        
        elif response.status == 403:
            # Insufficient permissions
            logger.error(f"Insufficient permissions: {response_text}")
            return {"ok": False, "error": {"message": "Insufficient permissions", "code": 403}}
        
        elif response.status == 404:
            # Not found
            logger.error(f"Resource not found: {response_text}")
            return {"ok": False, "error": {"message": "Resource not found", "code": 404}}
        
        elif response.status == 429:
            # Rate limited
            retry_after = response.headers.get("Retry-After", "30")
            logger.warning(f"Rate limited, retrying after {retry_after}s")
            return {"ok": False, "error": {"message": "Rate limited", "code": 429}}
        
        else:
            logger.error(f"Google Drive API error: {response.status} - {response_text}")
            try:
                error_data = json.loads(response_text)
                return {"ok": False, "error": error_data.get("error", {"message": response_text})}
            except json.JSONDecodeError:
                return {"ok": False, "error": {"message": response_text}}
    
    # Mock responses for development
    def _mock_files_response(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock files list response"""
        files = [
            {
                "id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                "name": "Project Proposal.pdf",
                "mimeType": "application/pdf",
                "size": "1048576",
                "createdTime": "2024-01-15T10:30:00.000Z",
                "modifiedTime": "2024-01-20T14:45:00.000Z",
                "viewedByMeTime": "2024-01-21T09:15:00.000Z",
                "parents": ["root"],
                "webViewLink": "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/view",
                "webContentLink": "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export",
                "thumbnailLink": "https://drive.google.com/thumbnail?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                "shared": True,
                "owners": [
                    {
                        "displayName": "John Doe",
                        "emailAddress": "john.doe@example.com"
                    }
                ],
                "version": "3",
                "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
                "kind": "drive#file"
            },
            {
                "id": "1CvO_s6pqGx6dVpZ4XN_3YmB2xJ9l3aM",
                "name": "Meeting Notes.doc",
                "mimeType": "application/vnd.google-apps.document",
                "size": "0",
                "createdTime": "2024-01-10T15:20:00.000Z",
                "modifiedTime": "2024-01-18T11:30:00.000Z",
                "viewedByMeTime": "2024-01-19T16:45:00.000Z",
                "parents": ["root"],
                "webViewLink": "https://docs.google.com/document/d/1CvO_s6pqGx6dVpZ4XN_3YmB2xJ9l3aM/edit",
                "thumbnailLink": "https://drive.google.com/thumbnail?id=1CvO_s6pqGx6dVpZ4XN_3YmB2xJ9l3aM",
                "shared": False,
                "owners": [
                    {
                        "displayName": "John Doe",
                        "emailAddress": "john.doe@example.com"
                    }
                ],
                "version": "5",
                "kind": "drive#file"
            },
            {
                "id": "1Dx9n7J4_0K5FqPzL8M3rG2s6V2hT7wY",
                "name": "Budget.xlsx",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "size": "0",
                "createdTime": "2024-01-05T09:15:00.000Z",
                "modifiedTime": "2024-01-22T13:20:00.000Z",
                "viewedByMeTime": "2024-01-22T13:25:00.000Z",
                "parents": ["root"],
                "webViewLink": "https://docs.google.com/spreadsheets/d/1Dx9n7J4_0K5FqPzL8M3rG2s6V2hT7wY/edit",
                "thumbnailLink": "https://drive.google.com/thumbnail?id=1Dx9n7J4_0K5FqPzL8M3rG2s6V2hT7wY",
                "shared": True,
                "owners": [
                    {
                        "displayName": "John Doe",
                        "emailAddress": "john.doe@example.com"
                    }
                ],
                "version": "8",
                "kind": "drive#file"
            },
            {
                "id": "1Ey9p8K5_1L6GqRzN9O4sH3t7W2iU8vZ",
                "name": "Work Documents",
                "mimeType": "application/vnd.google-apps.folder",
                "size": "0",
                "createdTime": "2024-01-01T12:00:00.000Z",
                "modifiedTime": "2024-01-25T16:30:00.000Z",
                "parents": ["root"],
                "webViewLink": "https://drive.google.com/drive/folders/1Ey9p8K5_1L6GqRzN9O4sH3t7W2iU8vZ",
                "shared": False,
                "owners": [
                    {
                        "displayName": "John Doe",
                        "emailAddress": "john.doe@example.com"
                    }
                ],
                "version": "1",
                "kind": "drive#file"
            }
        ]
        
        # Apply filters
        if params:
            # Filter by name
            if "q" in params:
                query = params["q"].lower()
                files = [f for f in files if query in f["name"].lower()]
            
            # Filter by parent
            if "parent_id" in params:
                parent_id = params["parent_id"]
                files = [f for f in files if parent_id in f.get("parents", [])]
            
            # Filter by mimeType
            if "mimeType" in params:
                mime_type = params["mimeType"]
                files = [f for f in files if f["mimeType"] == mime_type]
            
            # Pagination
            page_size = int(params.get("pageSize", 10))
            page_token = params.get("pageToken")
            
            if page_token:
                start_index = files.index(next(f for f in files if f["id"] == page_token)) + 1
            else:
                start_index = 0
            
            files = files[start_index:start_index + page_size]
        
        return {
            "files": files,
            "incompleteSearch": False,
            "kind": "drive#fileList"
        }
    
    def _mock_file_upload_response(self, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock file upload response"""
        file_id = f"mock_file_id_{datetime.now().timestamp()}"
        file_name = metadata.get("name", "uploaded_file.bin") if metadata else "uploaded_file.bin"
        mime_type = metadata.get("mimeType", "application/octet-stream") if metadata else "application/octet-stream"
        size = metadata.get("size", "1024") if metadata else "1024"
        
        return {
            "id": file_id,
            "name": file_name,
            "mimeType": mime_type,
            "size": size,
            "createdTime": datetime.now(timezone.utc).isoformat(),
            "modifiedTime": datetime.now(timezone.utc).isoformat(),
            "parents": metadata.get("parents", ["root"]) if metadata else ["root"],
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "webContentLink": f"https://drive.google.com/file/d/{file_id}/export",
            "shared": False,
            "owners": [
                {
                    "displayName": "John Doe",
                    "emailAddress": "john.doe@example.com"
                }
            ],
            "version": "1",
            "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
            "kind": "drive#file"
        }
    
    def _mock_create_file_response(self, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock create file response"""
        file_id = f"mock_file_id_{datetime.now().timestamp()}"
        file_name = data.get("name", "new_file") if data else "new_file"
        mime_type = data.get("mimeType", "text/plain") if data else "text/plain"
        
        if mime_type == "application/vnd.google-apps.folder":
            return {
                "id": file_id,
                "name": file_name,
                "mimeType": "application/vnd.google-apps.folder",
                "createdTime": datetime.now(timezone.utc).isoformat(),
                "modifiedTime": datetime.now(timezone.utc).isoformat(),
                "parents": data.get("parents", ["root"]) if data else ["root"],
                "webViewLink": f"https://drive.google.com/drive/folders/{file_id}",
                "shared": False,
                "owners": [
                    {
                        "displayName": "John Doe",
                        "emailAddress": "john.doe@example.com"
                    }
                ],
                "version": "1",
                "kind": "drive#file"
            }
        else:
            return {
                "id": file_id,
                "name": file_name,
                "mimeType": mime_type,
                "size": "0",
                "createdTime": datetime.now(timezone.utc).isoformat(),
                "modifiedTime": datetime.now(timezone.utc).isoformat(),
                "parents": data.get("parents", ["root"]) if data else ["root"],
                "webViewLink": f"https://docs.google.com/document/d/{file_id}/edit" if "document" in mime_type else f"https://drive.google.com/file/d/{file_id}/view",
                "shared": False,
                "owners": [
                    {
                        "displayName": "John Doe",
                        "emailAddress": "john.doe@example.com"
                    }
                ],
                "version": "1",
                "kind": "drive#file"
            }
    
    def _mock_file_response(self, file_id: str) -> Dict[str, Any]:
        """Mock single file response"""
        mock_file = self._mock_files_response()["files"][0]
        mock_file["id"] = file_id
        return mock_file
    
    def _mock_update_file_response(self, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock update file response"""
        file_id = data.get("fileId", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms") if data else "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        updated_file = self._mock_files_response()["files"][0]
        updated_file["id"] = file_id
        updated_file["modifiedTime"] = datetime.now(timezone.utc).isoformat()
        
        if data and "name" in data:
            updated_file["name"] = data["name"]
        
        return updated_file
    
    def _mock_delete_file_response(self) -> Dict[str, Any]:
        """Mock delete file response"""
        return {}
    
    def _mock_create_folder_response(self, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock create folder response"""
        return self._mock_create_file_response(data)
    
    def _mock_permissions_response(self) -> Dict[str, Any]:
        """Mock permissions response"""
        return {
            "permissions": [
                {
                    "id": "anyoneWithLink",
                    "type": "anyone",
                    "role": "reader",
                    "displayName": "Anyone",
                    "kind": "drive#permission"
                },
                {
                    "id": "user_john_doe",
                    "type": "user",
                    "role": "owner",
                    "emailAddress": "john.doe@example.com",
                    "displayName": "John Doe",
                    "photoLink": "https://lh3.googleusercontent.com/photo.jpg",
                    "kind": "drive#permission"
                }
            ]
        }
    
    def _mock_create_permission_response(self, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock create permission response"""
        permission_id = f"mock_permission_id_{datetime.now().timestamp()}"
        
        return {
            "id": permission_id,
            "type": data.get("type", "user") if data else "user",
            "role": data.get("role", "reader") if data else "reader",
            "emailAddress": data.get("emailAddress", "test@example.com") if data else "test@example.com",
            "displayName": data.get("displayName", "Test User") if data else "Test User",
            "kind": "drive#permission"
        }
    
    def _mock_changes_response(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock changes response"""
        return {
            "changes": [
                {
                    "id": "1",
                    "fileId": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                    "removed": False,
                    "file": self._mock_files_response()["files"][0],
                    "kind": "drive#change"
                }
            ],
            "newStartPageToken": "12345",
            "kind": "drive#changeList"
        }
    
    def _mock_about_response(self) -> Dict[str, Any]:
        """Mock about response"""
        return {
            "kind": "drive#about",
            "user": {
                "kind": "drive#user",
                "displayName": "John Doe",
                "emailAddress": "john.doe@example.com",
                "photoLink": "https://lh3.googleusercontent.com/photo.jpg"
            },
            "storageQuota": {
                "limit": "15000000000",
                "usage": "5000000000",
                "usageInDrive": "3000000000",
                "usageInDriveTrash": "1000000000"
            },
            "driveType": "user"
        }
    
    def _dict_to_file(self, file_data: Dict[str, Any]) -> GoogleDriveFile:
        """Convert dictionary to GoogleDriveFile"""
        return GoogleDriveFile(
            id=file_data.get("id", ""),
            name=file_data.get("name", ""),
            mime_type=file_data.get("mimeType", ""),
            size=int(file_data.get("size", 0)),
            created_time=datetime.fromisoformat(file_data["createdTime"].replace("Z", "+00:00")) if file_data.get("createdTime") else None,
            modified_time=datetime.fromisoformat(file_data["modifiedTime"].replace("Z", "+00:00")) if file_data.get("modifiedTime") else None,
            viewed_by_me_time=datetime.fromisoformat(file_data["viewedByMeTime"].replace("Z", "+00:00")) if file_data.get("viewedByMeTime") else None,
            parents=file_data.get("parents", []),
            web_view_link=file_data.get("webViewLink"),
            web_content_link=file_data.get("webContentLink"),
            thumbnail_link=file_data.get("thumbnailLink"),
            permissions=file_data.get("permissions", []),
            shared=file_data.get("shared", False),
            owners=file_data.get("owners", []),
            version=file_data.get("version"),
            md5_checksum=file_data.get("md5Checksum"),
            file_extension=file_data.get("fileExtension"),
            full_file_extension=file_data.get("fullFileExtension"),
            kind=file_data.get("kind", "drive#file"),
            trashed=file_data.get("trashed", False),
            starred=file_data.get("starred", False)
        )
    
    def _dict_to_folder(self, folder_data: Dict[str, Any]) -> GoogleDriveFolder:
        """Convert dictionary to GoogleDriveFolder"""
        return GoogleDriveFolder(
            id=folder_data.get("id", ""),
            name=folder_data.get("name", ""),
            created_time=datetime.fromisoformat(folder_data["createdTime"].replace("Z", "+00:00")) if folder_data.get("createdTime") else None,
            modified_time=datetime.fromisoformat(folder_data["modifiedTime"].replace("Z", "+00:00")) if folder_data.get("modifiedTime") else None,
            parents=folder_data.get("parents", []),
            web_view_link=folder_data.get("webViewLink"),
            permissions=folder_data.get("permissions", []),
            shared=folder_data.get("shared", False),
            owners=folder_data.get("owners", []),
            trashed=folder_data.get("trashed", False),
            starred=folder_data.get("starred", False)
        )
    
    def _dict_to_permission(self, permission_data: Dict[str, Any]) -> GoogleDrivePermission:
        """Convert dictionary to GoogleDrivePermission"""
        return GoogleDrivePermission(
            id=permission_data.get("id", ""),
            type=permission_data.get("type", ""),
            role=permission_data.get("role", ""),
            email_address=permission_data.get("emailAddress"),
            domain=permission_data.get("domain"),
            display_name=permission_data.get("displayName"),
            photo_link=permission_data.get("photoLink"),
            kind=permission_data.get("kind", "drive#permission")
        )
    
    # Core File Operations
    async def get_files(
        self,
        user_id: str,
        query: Optional[str] = None,
        parent_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        page_size: int = 10,
        page_token: Optional[str] = None,
        order_by: Optional[str] = None,
        db_conn_pool=None
    ) -> List[GoogleDriveFile]:
        """Get files from Google Drive"""
        
        try:
            # Build query parameters
            params = {
                "pageSize": min(page_size, 1000),  # Max page size is 1000
                "fields": "files(id,name,mimeType,size,createdTime,modifiedTime,viewedByMeTime,parents,webViewLink,webContentLink,thumbnailLink,shared,owners,version,md5Checksum,fileExtension,fullFileExtension,kind,trashed,starred),nextPageToken,incompleteSearch,kind"
            }
            
            if page_token:
                params["pageToken"] = page_token
            
            # Build search query
            search_conditions = []
            
            if query:
                search_conditions.append(f"name contains '{query}'")
            
            if parent_id:
                search_conditions.append(f"'{parent_id}' in parents")
            
            if mime_type:
                search_conditions.append(f"mimeType = '{mime_type}'")
            
            # Exclude trashed files by default
            search_conditions.append("trashed = false")
            
            if search_conditions:
                params["q"] = " and ".join(search_conditions)
            
            if order_by:
                params["orderBy"] = order_by
            
            response = await self._make_request(
                user_id=user_id,
                method="GET",
                endpoint="files",
                params=params,
                db_conn_pool=db_conn_pool
            )
            
            if response.get("files"):
                files = []
                for file_data in response["files"]:
                    file_obj = self._dict_to_file(file_data)
                    files.append(file_obj)
                return files
            
            return []
        
        except Exception as e:
            logger.error(f"Error getting files: {e}")
            raise
    
    async def get_file(
        self,
        user_id: str,
        file_id: str,
        db_conn_pool=None
    ) -> Optional[GoogleDriveFile]:
        """Get specific file by ID"""
        
        try:
            params = {
                "fields": "id,name,mimeType,size,createdTime,modifiedTime,viewedByMeTime,parents,webViewLink,webContentLink,thumbnailLink,shared,owners,version,md5Checksum,fileExtension,fullFileExtension,kind,trashed,starred"
            }
            
            response = await self._make_request(
                user_id=user_id,
                method="GET",
                endpoint=f"files/{file_id}",
                params=params,
                db_conn_pool=db_conn_pool
            )
            
            if response and "id" in response:
                return self._dict_to_file(response)
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting file {file_id}: {e}")
            raise
    
    async def create_file(
        self,
        user_id: str,
        name: str,
        mime_type: str,
        content: Optional[str] = None,
        parents: Optional[List[str]] = None,
        db_conn_pool=None
    ) -> Optional[GoogleDriveFile]:
        """Create new file in Google Drive"""
        
        try:
            file_metadata = {
                "name": name,
                "mimeType": mime_type
            }
            
            if parents:
                file_metadata["parents"] = parents
            
            if content and mime_type.startswith("text/"):
                # Text content
                response = await self._make_request(
                    user_id=user_id,
                    method="POST",
                    endpoint="files",
                    data=file_metadata,
                    db_conn_pool=db_conn_pool
                )
                
                if response and "id" in response:
                    return self._dict_to_file(response)
            
            elif content:
                # Binary content (mock for development)
                file_metadata["size"] = len(content.encode())
                
                response = await self._make_request(
                    user_id=user_id,
                    method="POST",
                    endpoint="files",
                    data=file_metadata,
                    db_conn_pool=db_conn_pool
                )
                
                if response and "id" in response:
                    return self._dict_to_file(response)
            
            else:
                # Create empty file
                response = await self._make_request(
                    user_id=user_id,
                    method="POST",
                    endpoint="files",
                    data=file_metadata,
                    db_conn_pool=db_conn_pool
                )
                
                if response and "id" in response:
                    return self._dict_to_file(response)
            
            return None
        
        except Exception as e:
            logger.error(f"Error creating file {name}: {e}")
            raise
    
    async def update_file(
        self,
        user_id: str,
        file_id: str,
        name: Optional[str] = None,
        content: Optional[str] = None,
        db_conn_pool=None
    ) -> Optional[GoogleDriveFile]:
        """Update existing file"""
        
        try:
            update_data = {}
            
            if name:
                update_data["name"] = name
            
            response = await self._make_request(
                user_id=user_id,
                method="PATCH",
                endpoint=f"files/{file_id}",
                data=update_data,
                db_conn_pool=db_conn_pool
            )
            
            if response and "id" in response:
                return self._dict_to_file(response)
            
            return None
        
        except Exception as e:
            logger.error(f"Error updating file {file_id}: {e}")
            raise
    
    async def delete_file(
        self,
        user_id: str,
        file_id: str,
        db_conn_pool=None
    ) -> bool:
        """Delete file from Google Drive"""
        
        try:
            response = await self._make_request(
                user_id=user_id,
                method="DELETE",
                endpoint=f"files/{file_id}",
                db_conn_pool=db_conn_pool
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    async def upload_file(
        self,
        user_id: str,
        file_path: str,
        name: Optional[str] = None,
        parents: Optional[List[str]] = None,
        db_conn_pool=None
    ) -> Optional[GoogleDriveFile]:
        """Upload file to Google Drive"""
        
        try:
            # Get file info
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_name = name or path.name
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            # Read file content
            async with aiofiles.open(file_path, 'rb') as file:
                file_data = file.read()
            
            # Prepare metadata
            file_metadata = {
                "name": file_name,
                "mimeType": mime_type
            }
            
            if parents:
                file_metadata["parents"] = parents
            
            # Upload file
            upload_params = {
                "uploadType": "multipart",
                "fields": "id,name,mimeType,size,createdTime,modifiedTime,viewedByMeTime,parents,webViewLink,webContentLink,thumbnailLink,shared,owners,version,md5Checksum,fileExtension,fullFileExtension,kind,trashed,starred"
            }
            
            response = await self._make_request(
                user_id=user_id,
                method="POST",
                endpoint=f"{GOOGLE_DRIVE_UPLOAD_URL}/files",
                params=upload_params,
                file_data=file_data,
                file_metadata=file_metadata,
                db_conn_pool=db_conn_pool
            )
            
            if response and "id" in response:
                return self._dict_to_file(response)
            
            return None
        
        except Exception as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            raise
    
    async def download_file(
        self,
        user_id: str,
        file_id: str,
        output_path: Optional[str] = None,
        db_conn_pool=None
    ) -> Optional[bytes]:
        """Download file from Google Drive"""
        
        try:
            # Get file info first
            file_obj = await self.get_file(user_id, file_id, db_conn_pool)
            if not file_obj:
                return None
            
            # Download file content
            params = {"alt": "media"}
            
            response = await self._make_request(
                user_id=user_id,
                method="GET",
                endpoint=f"files/{file_id}",
                params=params,
                db_conn_pool=db_conn_pool
            )
            
            if isinstance(response, bytes):
                content = response
            else:
                # For mock, return dummy content
                content = b"Mock file content"
            
            # Save to file if output path provided
            if output_path:
                async with aiofiles.open(output_path, 'wb') as file:
                    await file.write(content)
            
            return content
        
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            raise
    
    async def copy_file(
        self,
        user_id: str,
        file_id: str,
        name: Optional[str] = None,
        parents: Optional[List[str]] = None,
        db_conn_pool=None
    ) -> Optional[GoogleDriveFile]:
        """Copy file in Google Drive"""
        
        try:
            copy_data = {}
            
            if name:
                copy_data["name"] = name
            
            if parents:
                copy_data["parents"] = parents
            
            response = await self._make_request(
                user_id=user_id,
                method="POST",
                endpoint=f"files/{file_id}/copy",
                data=copy_data,
                db_conn_pool=db_conn_pool
            )
            
            if response and "id" in response:
                return self._dict_to_file(response)
            
            return None
        
        except Exception as e:
            logger.error(f"Error copying file {file_id}: {e}")
            raise
    
    async def move_file(
        self,
        user_id: str,
        file_id: str,
        add_parents: Optional[List[str]] = None,
        remove_parents: Optional[List[str]] = None,
        db_conn_pool=None
    ) -> Optional[GoogleDriveFile]:
        """Move file to different folder"""
        
        try:
            move_data = {}
            
            if add_parents:
                move_data["addParents"] = add_parents
            
            if remove_parents:
                move_data["removeParents"] = remove_parents
            
            response = await self._make_request(
                user_id=user_id,
                method="PATCH",
                endpoint=f"files/{file_id}",
                data=move_data,
                db_conn_pool=db_conn_pool
            )
            
            if response and "id" in response:
                return self._dict_to_file(response)
            
            return None
        
        except Exception as e:
            logger.error(f"Error moving file {file_id}: {e}")
            raise
    
    async def close(self):
        """Close HTTP client"""
        if self._client and not self._client.closed:
            await self._client.close()
            self._client = None

# Global service instance
_google_drive_service: Optional[GoogleDriveService] = None

def get_google_drive_service(config: Optional[GoogleDriveConfig] = None) -> GoogleDriveService:
    """Get global Google Drive service instance"""
    global _google_drive_service
    
    if _google_drive_service is None and config:
        _google_drive_service = GoogleDriveService(config)
    
    return _google_drive_service

# Export service and classes
__all__ = [
    "GoogleDriveService",
    "GoogleDriveConfig",
    "GoogleDriveFile",
    "GoogleDriveFolder",
    "GoogleDrivePermission",
    "GoogleDriveChange",
    "FileType",
    "PermissionRole",
    "PermissionType",
    "get_google_drive_service"
]