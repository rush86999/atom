"""
Enhanced Dropbox Services Implementation
Complete Dropbox integration with advanced features
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import aiohttp
from cryptography.fernet import Fernet

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class DropboxUser:
    """Dropbox user information"""
    account_id: str
    name: Dict[str, str]
    email: str
    email_verified: bool
    profile_photo_url: Optional[str] = None
    disabled: bool = False
    country: Optional[str] = None
    locale: str = 'en'
    referral_link: Optional[str] = None
    is_paired: bool = False
    account_type: Dict[str, str] = None
    root_info: Dict[str, str] = None
    team_id: Optional[str] = None
    team_member_id: Optional[str] = None

@dataclass
class DropboxFile:
    """Dropbox file information"""
    id: str
    name: str
    path_lower: str
    path_display: str
    id_mapping: Dict[str, str]
    client_modified: str
    server_modified: str
    rev: str
    size: int
    is_downloadable: bool
    content_hash: str
    file_lock_info: Optional[Dict[str, Any]] = None
    has_explicit_shared_members: bool = False
    sharing_info: Optional[Dict[str, Any]] = None
    is_file: bool = True
    is_folder: bool = False
    property_groups: List[Dict[str, Any]] = None

@dataclass
class DropboxFolder:
    """Dropbox folder information"""
    id: str
    name: str
    path_lower: str
    path_display: str
    id_mapping: Dict[str, str]
    sharing_info: Optional[Dict[str, Any]] = None
    property_groups: List[Dict[str, Any]] = None
    is_file: bool = False
    is_folder: bool = True

@dataclass
class DropboxSharedLink:
    """Dropbox shared link information"""
    url: str
    name: str
    path_lower: str
    id: str
    expires: Optional[str] = None
    link_permissions: Dict[str, Any] = None
    team_member_info: Optional[Dict[str, str]] = None
    content_owner_team_info: Optional[Dict[str, str]] = None
    content_owner_display_name: Optional[str] = None

@dataclass
class DropboxUploadSession:
    """Dropbox upload session information"""
    session_id: str
    expires: str

class DropboxServicesEnhanced:
    """Enhanced Dropbox Services implementation with advanced capabilities"""
    
    def __init__(self):
        self.encryption_key = os.getenv('ATOM_OAUTH_ENCRYPTION_KEY')
        self.mock_mode = not os.getenv('DROPBOX_APP_KEY') or not os.getenv('DROPBOX_APP_SECRET')
        self.base_url = 'https://api.dropboxapi.com/2'
        self.content_url = 'https://content.dropboxapi.com/2'
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _make_request(self, endpoint: str, method: str = 'POST', 
                           access_token: str = None, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Dropbox API"""
        if self.mock_mode:
            return await self._mock_response(endpoint, method, **kwargs)
        
        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        headers = {'Authorization': f'Bearer {access_token}'} if access_token else {}
        headers['Content-Type'] = 'application/json'
        
        try:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Dropbox API error: {response.status} - {error_text}")
                    return {"error": error_text, "status": response.status}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}

    async def _make_content_request(self, endpoint: str, method: str = 'POST',
                                  access_token: str = None, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Dropbox content API"""
        if self.mock_mode:
            return await self._mock_response(endpoint, method, content_request=True, **kwargs)
        
        session = await self._get_session()
        url = f"{self.content_url}/{endpoint}"
        headers = {'Authorization': f'Bearer {access_token}'} if access_token else {}
        
        # Handle Dropbox-API-Arg header for content requests
        if 'data' in kwargs and 'args' in kwargs['data']:
            headers['Dropbox-API-Arg'] = json.dumps(kwargs['data']['args'])
        
        try:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status == 200:
                    # Try to parse as JSON, otherwise return raw content
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        return await response.json()
                    else:
                        return {"content": await response.read()}
                else:
                    error_text = await response.text()
                    logger.error(f"Dropbox content API error: {response.status} - {error_text}")
                    return {"error": error_text, "status": response.status}
        except Exception as e:
            logger.error(f"Content request failed: {e}")
            return {"error": str(e)}

    async def _mock_response(self, endpoint: str, method: str, content_request: bool = False, **kwargs) -> Dict[str, Any]:
        """Mock response for development/testing"""
        if 'users/get_current_account' in endpoint:
            return {
                "account_id": "dbid:AAH4f99T0taONIb-OurWxbNQ6ywGRopQngc",
                "name": {
                    "given_name": "Test",
                    "surname": "User",
                    "familiar_name": "Test",
                    "display_name": "Test User",
                    "abbreviated_name": "TU"
                },
                "email": "test@example.com",
                "email_verified": True,
                "disabled": False,
                "locale": "en",
                "referral_link": "https://db.tt/AJdhb2Ft",
                "is_paired": False,
                "account_type": {".tag": "basic"},
                "root_info": {
                    ".tag": "user",
                    "root_namespace_id": "1234567890",
                    "home_namespace_id": "1234567890"
                }
            }
        
        elif 'files/list_folder' in endpoint:
            return {
                "entries": [
                    {
                        ".tag": "file",
                        "id": "id:abc123",
                        "name": "Document.pdf",
                        "path_lower": "/documents/document.pdf",
                        "path_display": "/Documents/Document.pdf",
                        "id_mapping": {".tag": "individual", "content_hash": "abc123"},
                        "client_modified": "2024-01-01T00:00:00Z",
                        "server_modified": "2024-01-01T12:00:00Z",
                        "rev": "abc123def",
                        "size": 1024000,
                        "is_downloadable": True,
                        "content_hash": "abc123def456789",
                        "file_lock_info": {
                            "is_lockholder": False,
                            "created": "2024-01-01T10:00:00Z"
                        }
                    },
                    {
                        ".tag": "folder",
                        "id": "id:xyz789",
                        "name": "Projects",
                        "path_lower": "/projects",
                        "path_display": "/Projects",
                        "id_mapping": {".tag": "individual"},
                        "sharing_info": {
                            "read_only": False,
                            "parent_shared_folder_id": "shared123",
                            "shared_folder_id": "folder456",
                            "traverse_only": False,
                            "no_access": False
                        }
                    }
                ],
                "cursor": "mock_cursor_123",
                "has_more": False
            }
        
        elif 'files/upload' in endpoint:
            return {
                ".tag": "file",
                "id": "id:uploaded_" + str(int(datetime.utcnow().timestamp())),
                "name": kwargs.get('headers', {}).get('Dropbox-API-Arg', '{}').split('"')[3] or "UploadedFile.txt",
                "path_lower": "/uploaded_file.txt",
                "path_display": "/UploadedFile.txt",
                "id_mapping": {".tag": "individual", "content_hash": "upload_hash"},
                "client_modified": datetime.utcnow().isoformat(),
                "server_modified": datetime.utcnow().isoformat(),
                "rev": "new_rev_" + str(int(datetime.utcnow().timestamp())),
                "size": len(kwargs.get('data', b'')),
                "is_downloadable": True,
                "content_hash": "upload_hash_" + str(int(datetime.utcnow().timestamp()))
            }
        
        elif 'files/create_folder' in endpoint:
            folder_name = kwargs.get('json', {}).get('path', 'New Folder').split('/')[-1]
            return {
                ".tag": "folder",
                "id": "id:folder_" + str(int(datetime.utcnow().timestamp())),
                "name": folder_name,
                "path_lower": kwargs.get('json', {}).get('path', '/new_folder').lower(),
                "path_display": kwargs.get('json', {}).get('path', '/New Folder'),
                "id_mapping": {".tag": "individual"}
            }
        
        elif 'sharing/create_shared_link_with_settings' in endpoint:
            return {
                "url": "https://www.dropbox.com/s/mock_shared_link?dl=0",
                "name": "SharedFile.txt",
                "path_lower": "/sharedfile.txt",
                "id": "id:shared_" + str(int(datetime.utcnow().timestamp())),
                "link_permissions": {
                    "can_revoke": True,
                    "resolved_visibility": {
                        ".tag": "public"
                    },
                    "require_password": False,
                    "allow_download": True,
                    "allow_uploads": False,
                    "effective_audience": {
                        ".tag": "public"
                    },
                    "link_access_level": {
                        ".tag": "viewer"
                    }
                }
            }
        
        elif 'files/search_v2' in endpoint:
            return {
                "matches": [
                    {
                        "metadata": {
                            ".tag": "file",
                            "id": "id:search123",
                            "name": "SearchResult.txt",
                            "path_lower": "/searchresult.txt",
                            "path_display": "/SearchResult.txt",
                            "size": 5120
                        }
                    }
                ],
                "has_more": False
            }
        
        elif 'users/get_space_usage' in endpoint:
            return {
                "used": 10737418240,  # 10GB
                "allocation": {
                    ".tag": "individual",
                    "allocated": 21474836480,  # 20GB
                    "user_specified": {
                        ".tag": "individual",
                        "used": 10737418240,
                        "allocated": 21474836480
                    }
                }
            }
        
        return {"mock": True, "endpoint": endpoint, "method": method}

    # User Management
    async def get_current_user(self, access_token: str) -> Optional[DropboxUser]:
        """Get current Dropbox user information"""
        data = await self._make_request('users/get_current_account', access_token=access_token)
        if 'error' in data:
            return None
        
        return DropboxUser(
            account_id=data.get('account_id', ''),
            name=data.get('name', {}),
            email=data.get('email', ''),
            email_verified=data.get('email_verified', False),
            profile_photo_url=data.get('profile_photo_url'),
            disabled=data.get('disabled', False),
            country=data.get('country'),
            locale=data.get('locale', 'en'),
            referral_link=data.get('referral_link'),
            is_paired=data.get('is_paired', False),
            account_type=data.get('account_type', {}),
            root_info=data.get('root_info', {}),
            team_id=data.get('team_id'),
            team_member_id=data.get('team_member_id')
        )

    # Enhanced File Operations
    async def list_files(self, access_token: str, path: str = '', recursive: bool = False) -> List[Union[DropboxFile, DropboxFolder]]:
        """List files and folders with advanced options"""
        payload = {'path': path, 'recursive': recursive}
        
        data = await self._make_request('files/list_folder', access_token=access_token, json=payload)
        if 'error' in data:
            return []
        
        items = []
        for entry in data.get('entries', []):
            if entry.get('.tag') == 'file':
                file_obj = DropboxFile(
                    id=entry.get('id', ''),
                    name=entry.get('name', ''),
                    path_lower=entry.get('path_lower', ''),
                    path_display=entry.get('path_display', ''),
                    id_mapping=entry.get('id_mapping', {}),
                    client_modified=entry.get('client_modified', ''),
                    server_modified=entry.get('server_modified', ''),
                    rev=entry.get('rev', ''),
                    size=entry.get('size', 0),
                    is_downloadable=entry.get('is_downloadable', True),
                    content_hash=entry.get('content_hash', ''),
                    file_lock_info=entry.get('file_lock_info'),
                    has_explicit_shared_members=entry.get('has_explicit_shared_members', False),
                    sharing_info=entry.get('sharing_info'),
                    is_file=True,
                    is_folder=False,
                    property_groups=entry.get('property_groups', [])
                )
                items.append(file_obj)
            elif entry.get('.tag') == 'folder':
                folder_obj = DropboxFolder(
                    id=entry.get('id', ''),
                    name=entry.get('name', ''),
                    path_lower=entry.get('path_lower', ''),
                    path_display=entry.get('path_display', ''),
                    id_mapping=entry.get('id_mapping', {}),
                    sharing_info=entry.get('sharing_info'),
                    is_file=False,
                    is_folder=True,
                    property_groups=entry.get('property_groups', [])
                )
                items.append(folder_obj)
        
        return items

    async def upload_file(self, access_token: str, file_content: bytes, 
                         file_path: str, autorename: bool = True) -> Optional[DropboxFile]:
        """Upload file to Dropbox"""
        args = {
            'path': file_path,
            'mode': 'add',
            'autorename': autorename,
            'mute': False,
            'strict_conflict': False
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/octet-stream',
            'Dropbox-API-Arg': json.dumps(args)
        }
        
        session = await self._get_session()
        url = f"{self.content_url}/files/upload"
        
        try:
            async with session.post(url, headers=headers, data=file_content) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    return DropboxFile(
                        id=data.get('id', ''),
                        name=data.get('name', ''),
                        path_lower=data.get('path_lower', ''),
                        path_display=data.get('path_display', ''),
                        id_mapping=data.get('id_mapping', {}),
                        client_modified=data.get('client_modified', ''),
                        server_modified=data.get('server_modified', ''),
                        rev=data.get('rev', ''),
                        size=data.get('size', 0),
                        is_downloadable=data.get('is_downloadable', True),
                        content_hash=data.get('content_hash', ''),
                        is_file=True,
                        is_folder=False
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Dropbox upload error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Dropbox upload failed: {e}")
            return None

    async def download_file(self, access_token: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Download file from Dropbox"""
        args = {'path': file_path}
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Dropbox-API-Arg': json.dumps(args)
        }
        
        session = await self._get_session()
        url = f"{self.content_url}/files/download"
        
        try:
            async with session.post(url, headers=headers) as response:
                if response.status == 200:
                    content = await response.read()
                    metadata_header = response.headers.get('dropbox-api-result')
                    metadata = json.loads(metadata_header) if metadata_header else {}
                    
                    return {
                        'content': content,
                        'metadata': metadata
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Dropbox download error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Dropbox download failed: {e}")
            return None

    async def create_folder(self, access_token: str, folder_path: str, autorename: bool = False) -> Optional[DropboxFolder]:
        """Create folder in Dropbox"""
        payload = {
            'path': folder_path,
            'autorename': autorename
        }
        
        data = await self._make_request('files/create_folder', access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        return DropboxFolder(
            id=data.get('id', ''),
            name=data.get('name', ''),
            path_lower=data.get('path_lower', ''),
            path_display=data.get('path_display', ''),
            id_mapping=data.get('id_mapping', {}),
            is_file=False,
            is_folder=True,
            sharing_info=data.get('sharing_info'),
            property_groups=data.get('property_groups', [])
        )

    async def delete_item(self, access_token: str, path: str) -> bool:
        """Delete file or folder from Dropbox"""
        payload = {'path': path}
        
        data = await self._make_request('files/delete', access_token=access_token, json=payload)
        return 'error' not in data

    async def move_item(self, access_token: str, from_path: str, to_path: str, 
                        autorename: bool = False) -> Optional[Union[DropboxFile, DropboxFolder]]:
        """Move file or folder in Dropbox"""
        payload = {
            'from_path': from_path,
            'to_path': to_path,
            'autorename': autorename
        }
        
        data = await self._make_request('files/move', access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        # Return appropriate object type based on tag
        if data.get('.tag') == 'file':
            return DropboxFile(
                id=data.get('id', ''),
                name=data.get('name', ''),
                path_lower=data.get('path_lower', ''),
                path_display=data.get('path_display', ''),
                id_mapping=data.get('id_mapping', {}),
                client_modified=data.get('client_modified', ''),
                server_modified=data.get('server_modified', ''),
                rev=data.get('rev', ''),
                size=data.get('size', 0),
                is_downloadable=data.get('is_downloadable', True),
                content_hash=data.get('content_hash', ''),
                is_file=True,
                is_folder=False
            )
        else:
            return DropboxFolder(
                id=data.get('id', ''),
                name=data.get('name', ''),
                path_lower=data.get('path_lower', ''),
                path_display=data.get('path_display', ''),
                id_mapping=data.get('id_mapping', {}),
                is_file=False,
                is_folder=True
            )

    async def copy_item(self, access_token: str, from_path: str, to_path: str,
                       autorename: bool = False) -> Optional[Union[DropboxFile, DropboxFolder]]:
        """Copy file or folder in Dropbox"""
        payload = {
            'from_path': from_path,
            'to_path': to_path,
            'autorename': autorename
        }
        
        data = await self._make_request('files/copy', access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        # Return appropriate object type based on tag
        if data.get('.tag') == 'file':
            return DropboxFile(
                id=data.get('id', ''),
                name=data.get('name', ''),
                path_lower=data.get('path_lower', ''),
                path_display=data.get('path_display', ''),
                id_mapping=data.get('id_mapping', {}),
                client_modified=data.get('client_modified', ''),
                server_modified=data.get('server_modified', ''),
                rev=data.get('rev', ''),
                size=data.get('size', 0),
                is_downloadable=data.get('is_downloadable', True),
                content_hash=data.get('content_hash', ''),
                is_file=True,
                is_folder=False
            )
        else:
            return DropboxFolder(
                id=data.get('id', ''),
                name=data.get('name', ''),
                path_lower=data.get('path_lower', ''),
                path_display=data.get('path_display', ''),
                id_mapping=data.get('id_mapping', {}),
                is_file=False,
                is_folder=True
            )

    # Search Operations
    async def search_files(self, access_token: str, query: str, path: str = '',
                          mode: str = 'filename', limit: int = 100) -> Dict[str, Any]:
        """Search for files and folders"""
        payload = {
            'query': query,
            'include_highlights': False,
            'include_media_info': False,
            'include_deleted': False,
            'limit': limit
        }
        
        if path:
            payload['options'] = {
                'path': path,
                'filename_only': mode == 'filename'
            }
        
        data = await self._make_request('files/search_v2', access_token=access_token, json=payload)
        if 'error' in data:
            return {'matches': [], 'has_more': False}
        
        return {
            'matches': data.get('matches', []),
            'has_more': data.get('has_more', False),
            'cursor': data.get('cursor')
        }

    # Sharing Operations
    async def create_shared_link(self, access_token: str, path: str, 
                               settings: Dict[str, Any] = None) -> Optional[DropboxSharedLink]:
        """Create shared link for file or folder"""
        if settings is None:
            settings = {
                'requested_visibility': 'public',
                'allow_download': True,
                'allow_uploads': False
            }
        
        payload = {
            'path': path,
            'settings': settings
        }
        
        data = await self._make_request('sharing/create_shared_link_with_settings', 
                                      access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        return DropboxSharedLink(
            url=data.get('url', ''),
            name=data.get('name', ''),
            path_lower=data.get('path_lower', ''),
            id=data.get('id', ''),
            expires=data.get('expires'),
            link_permissions=data.get('link_permissions', {}),
            team_member_info=data.get('team_member_info'),
            content_owner_team_info=data.get('content_owner_team_info'),
            content_owner_display_name=data.get('content_owner_display_name')
        )

    async def get_space_usage(self, access_token: str) -> Dict[str, Any]:
        """Get Dropbox space usage information"""
        data = await self._make_request('users/get_space_usage', access_token=access_token)
        if 'error' in data:
            return {}
        
        return data

    # File Versioning
    async def list_file_versions(self, access_token: str, path: str, limit: int = 10) -> List[Dict[str, Any]]:
        """List file versions"""
        payload = {
            'path': path,
            'limit': limit
        }
        
        data = await self._make_request('files/list_revisions', access_token=access_token, json=payload)
        if 'error' in data:
            return []
        
        return data.get('entries', [])

    async def restore_file(self, access_token: str, path: str, rev: str) -> Optional[DropboxFile]:
        """Restore file to specific revision"""
        payload = {
            'path': path,
            'rev': rev
        }
        
        data = await self._make_request('files/restore', access_token=access_token, json=payload)
        if 'error' in data:
            return None
        
        return DropboxFile(
            id=data.get('id', ''),
            name=data.get('name', ''),
            path_lower=data.get('path_lower', ''),
            path_display=data.get('path_display', ''),
            id_mapping=data.get('id_mapping', {}),
            client_modified=data.get('client_modified', ''),
            server_modified=data.get('server_modified', ''),
            rev=data.get('rev', ''),
            size=data.get('size', 0),
            is_downloadable=data.get('is_downloadable', True),
            content_hash=data.get('content_hash', ''),
            is_file=True,
            is_folder=False
        )

    # File Metadata
    async def get_file_metadata(self, access_token: str, path: str, 
                              include_media_info: bool = False,
                              include_deleted: bool = False,
                              include_has_explicit_shared_members: bool = False,
                              include_mounted_folders: bool = False) -> Dict[str, Any]:
        """Get file or folder metadata"""
        payload = {
            'path': path,
            'include_media_info': include_media_info,
            'include_deleted': include_deleted,
            'include_has_explicit_shared_members': include_has_explicit_shared_members,
            'include_mounted_folders': include_mounted_folders
        }
        
        data = await self._make_request('files/get_metadata', access_token=access_token, json=payload)
        if 'error' in data:
            return {}
        
        return data

    # File Properties
    async def add_file_properties(self, access_token: str, path: str, 
                                 property_groups: List[Dict[str, Any]]) -> bool:
        """Add custom properties to file"""
        payload = {
            'path': path,
            'property_groups': property_groups
        }
        
        data = await self._make_request('file_properties/properties/add', 
                                      access_token=access_token, json=payload)
        return 'error' not in data

    # File Preview
    async def get_file_preview(self, access_token: str, path: str, 
                             format: str = 'png', size: str = 'm') -> Optional[str]:
        """Get file preview URL"""
        args = {
            'path': path,
            'format': format,
            'size': size
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Dropbox-API-Arg': json.dumps(args)
        }
        
        session = await self._get_session()
        url = f"{self.content_url}/files/get_preview"
        
        try:
            async with session.post(url, headers=headers) as response:
                if response.status == 200:
                    # Return the preview URL (in real implementation, would handle differently)
                    return f"https://www.dropbox.com/preview{path}"
                else:
                    error_text = await response.text()
                    logger.error(f"Dropbox preview error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Dropbox preview failed: {e}")
            return None

    # Sharing Information
    async def get_sharing_info(self, access_token: str, path: str) -> Dict[str, Any]:
        """Get sharing information for file or folder"""
        payload = {
            'path': path,
            'include_has_explicit_shared_members': False,
            'include_mounted_folders': False
        }
        
        data = await self._make_request('sharing/get_shared_link_metadata', 
                                      access_token=access_token, json=payload)
        if 'error' in data:
            return {}
        
        return data

    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "service": "dropbox-services-enhanced",
            "version": "2.0.0",
            "mock_mode": self.mock_mode,
            "capabilities": [
                "user_management",
                "file_operations",
                "folder_operations",
                "search_operations",
                "sharing_operations",
                "versioning",
                "metadata_operations",
                "property_operations",
                "preview_operations",
                "space_usage"
            ],
            "base_urls": {
                "api": self.base_url,
                "content": self.content_url
            }
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None

# Singleton instance
dropbox_services_enhanced = DropboxServicesEnhanced()

# Export main class and instance
__all__ = [
    'DropboxServicesEnhanced',
    'dropbox_services_enhanced',
    'DropboxUser',
    'DropboxFile',
    'DropboxFolder',
    'DropboxSharedLink',
    'DropboxUploadSession'
]