"""
Enhanced Dropbox Service
Complete Dropbox integration service for the ATOM platform
"""

import os
import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import base64
import dropbox
from dropbox.exceptions import ApiError, AuthError

logger = logging.getLogger(__name__)


@dataclass
class DropboxUser:
    """Dropbox user profile information"""

    account_id: str
    name: Dict[str, str]
    email: str
    email_verified: bool
    profile_photo_url: Optional[str] = None
    disabled: bool = False
    country: Optional[str] = None
    locale: Optional[str] = None
    referral_link: Optional[str] = None


@dataclass
class DropboxFile:
    """Dropbox file metadata representation"""

    id: str
    name: str
    path_lower: str
    path_display: str
    client_modified: str
    server_modified: str
    rev: str
    size: int
    is_downloadable: bool
    content_hash: Optional[str] = None
    media_info: Optional[Dict[str, Any]] = None


@dataclass
class DropboxFolder:
    """Dropbox folder metadata representation"""

    id: str
    name: str
    path_lower: str
    path_display: str
    shared_folder_id: Optional[str] = None
    sharing_info: Optional[Dict[str, Any]] = None


@dataclass
class DropboxSharedLink:
    """Dropbox shared link information"""

    url: str
    name: str
    path_lower: str
    link_permissions: Dict[str, Any]
    preview_type: str
    client_modified: str
    server_modified: str


@dataclass
class DropboxSpaceUsage:
    """Dropbox space usage information"""

    used: int
    allocation: Dict[str, Any]


class DropboxEnhancedService:
    """Enhanced Dropbox service for comprehensive file operations"""

    def __init__(self):
        self.base_url = "https://api.dropboxapi.com/2"
        self.content_url = "https://content.dropboxapi.com/2"
        self.client_id = os.getenv("DROPBOX_APP_KEY")
        self.client_secret = os.getenv("DROPBOX_APP_SECRET")
        self.redirect_uri = os.getenv("DROPBOX_REDIRECT_URI")

    async def _get_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user from database"""
        try:
            from backend.database_manager import DatabaseManager

            db = DatabaseManager()

            # Get user tokens from database
            tokens = await db.get_user_tokens(user_id, "dropbox")
            if tokens and tokens.get("access_token"):
                # Check if token needs refresh
                if self._is_token_expired(tokens):
                    return await self._refresh_access_token(user_id, tokens)
                return tokens["access_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting access token for user {user_id}: {e}")
            return None

    def _is_token_expired(self, tokens: Dict[str, Any]) -> bool:
        """Check if access token is expired"""
        expires_at = tokens.get("expires_at")
        if not expires_at:
            return True

        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return datetime.now().astimezone() >= expires_dt
        except Exception:
            return True

    async def _refresh_access_token(
        self, user_id: str, tokens: Dict[str, Any]
    ) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                return None

            # Refresh token logic would go here
            # For now, return the existing token
            return tokens.get("access_token")
        except Exception as e:
            logger.error(f"Error refreshing token for user {user_id}: {e}")
            return None

    def _get_dropbox_client(self, access_token: str) -> dropbox.Dropbox:
        """Get Dropbox client instance"""
        return dropbox.Dropbox(access_token)

    # File Operations
    async def list_files(
        self,
        user_id: str,
        path: str = "/",
        recursive: bool = False,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List files and folders with pagination"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return []

            dbx = self._get_dropbox_client(access_token)

            if cursor:
                result = dbx.files_list_folder_continue(cursor)
            else:
                result = dbx.files_list_folder(path, recursive=recursive, limit=limit)

            entries = []
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    file = DropboxFile(
                        id=entry.id,
                        name=entry.name,
                        path_lower=entry.path_lower,
                        path_display=entry.path_display,
                        client_modified=entry.client_modified.isoformat(),
                        server_modified=entry.server_modified.isoformat(),
                        rev=entry.rev,
                        size=entry.size,
                        is_downloadable=entry.is_downloadable,
                        content_hash=entry.content_hash,
                        media_info=entry.media_info.to_dict()
                        if entry.media_info
                        else None,
                    )
                    entries.append(asdict(file))
                elif isinstance(entry, dropbox.files.FolderMetadata):
                    folder = DropboxFolder(
                        id=entry.id,
                        name=entry.name,
                        path_lower=entry.path_lower,
                        path_display=entry.path_display,
                        shared_folder_id=entry.shared_folder_id,
                        sharing_info=entry.sharing_info.to_dict()
                        if entry.sharing_info
                        else None,
                    )
                    entries.append(asdict(folder))

            return {
                "entries": entries,
                "cursor": result.cursor,
                "has_more": result.has_more,
            }

        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return {"entries": [], "cursor": None, "has_more": False}

    async def upload_file(
        self,
        user_id: str,
        file_name: str,
        file_content: str,
        path: str = "/",
        autorename: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Upload file to Dropbox"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            # Decode base64 content
            try:
                file_bytes = base64.b64decode(file_content)
            except Exception as decode_error:
                logger.error(f"Error decoding base64 content: {decode_error}")
                return None
            full_path = f"{path.rstrip('/')}/{file_name}"

            # Upload file
            result = dbx.files_upload(
                file_bytes,
                full_path,
                mode=dropbox.files.WriteMode.overwrite,
                autorename=autorename,
            )

            if isinstance(result, dropbox.files.FileMetadata):
                file = DropboxFile(
                    id=result.id,
                    name=result.name,
                    path_lower=result.path_lower,
                    path_display=result.path_display,
                    client_modified=result.client_modified.isoformat(),
                    server_modified=result.server_modified.isoformat(),
                    rev=result.rev,
                    size=result.size,
                    is_downloadable=result.is_downloadable,
                    content_hash=result.content_hash,
                    media_info=result.media_info.to_dict()
                    if result.media_info
                    else None,
                )
                return asdict(file)

            return None

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return None

    async def download_file(
        self, user_id: str, path: str, rev: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Download file from Dropbox"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            # Download file
            metadata, response = dbx.files_download(path, rev=rev)

            # Encode content to base64
            content_bytes = response.content
            content_base64 = base64.b64encode(content_bytes).decode("utf-8")

            return {
                "file_name": metadata.name,
                "content_bytes": content_base64,
                "mime_type": getattr(metadata, "media_info", {}).get(
                    "mime_type", "application/octet-stream"
                ),
                "rev": metadata.rev,
                "size": metadata.size,
            }

        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None

    async def search_files(
        self,
        user_id: str,
        query: str,
        path: str = "/",
        max_results: int = 50,
        file_extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Search files in Dropbox"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return []

            dbx = self._get_dropbox_client(access_token)

            # Prepare search options
            options = dropbox.files.SearchOptions(
                path=path, max_results=max_results, file_extensions=file_extensions
            )

            result = dbx.files_search_v2(query, options=options)

            matches = []
            for match in result.matches:
                metadata = match.metadata.get_metadata()
                if isinstance(metadata, dropbox.files.FileMetadata):
                    file = DropboxFile(
                        id=metadata.id,
                        name=metadata.name,
                        path_lower=metadata.path_lower,
                        path_display=metadata.path_display,
                        client_modified=metadata.client_modified.isoformat(),
                        server_modified=metadata.server_modified.isoformat(),
                        rev=metadata.rev,
                        size=metadata.size,
                        is_downloadable=metadata.is_downloadable,
                        content_hash=metadata.content_hash,
                        media_info=metadata.media_info.to_dict()
                        if metadata.media_info
                        else None,
                    )
                    matches.append(asdict(file))

            return {"matches": matches, "more": result.has_more, "start": result.start}

        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return {"matches": [], "more": False, "start": 0}

    # Folder Operations
    async def create_folder(
        self, user_id: str, path: str, autorename: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Create folder in Dropbox"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.files_create_folder_v2(path, autorename=autorename)

            if result.metadata:
                folder = DropboxFolder(
                    id=result.metadata.id,
                    name=result.metadata.name,
                    path_lower=result.metadata.path_lower,
                    path_display=result.metadata.path_display,
                    shared_folder_id=result.metadata.shared_folder_id,
                    sharing_info=result.metadata.sharing_info.to_dict()
                    if result.metadata.sharing_info
                    else None,
                )
                return asdict(folder)

            return None

        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return None

    # Item Management Operations
    async def delete_item(self, user_id: str, path: str) -> Optional[Dict[str, Any]]:
        """Delete file or folder from Dropbox"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.files_delete_v2(path)

            if result.metadata:
                if isinstance(result.metadata, dropbox.files.FileMetadata):
                    file = DropboxFile(
                        id=result.metadata.id,
                        name=result.metadata.name,
                        path_lower=result.metadata.path_lower,
                        path_display=result.metadata.path_display,
                        client_modified=result.metadata.client_modified.isoformat(),
                        server_modified=result.metadata.server_modified.isoformat(),
                        rev=result.metadata.rev,
                        size=result.metadata.size,
                        is_downloadable=result.metadata.is_downloadable,
                        content_hash=result.metadata.content_hash,
                    )
                    return {"metadata": asdict(file)}
                elif isinstance(result.metadata, dropbox.files.FolderMetadata):
                    folder = DropboxFolder(
                        id=result.metadata.id,
                        name=result.metadata.name,
                        path_lower=result.metadata.path_lower,
                        path_display=result.metadata.path_display,
                        shared_folder_id=result.metadata.shared_folder_id,
                    )
                    return {"metadata": asdict(folder)}

            return None

        except Exception as e:
            logger.error(f"Error deleting item: {e}")
            return None

    async def move_item(
        self,
        user_id: str,
        from_path: str,
        to_path: str,
        autorename: bool = True,
        allow_ownership_transfer: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Move file or folder in Dropbox"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.files_move_v2(
                from_path,
                to_path,
                autorename=autorename,
                allow_ownership_transfer=allow_ownership_transfer,
            )

            if result.metadata:
                if isinstance(result.metadata, dropbox.files.FileMetadata):
                    file = DropboxFile(
                        id=result.metadata.id,
                        name=result.metadata.name,
                        path_lower=result.metadata.path_lower,
                        path_display=result.metadata.path_display,
                        client_modified=result.metadata.client_modified.isoformat(),
                        server_modified=result.metadata.server_modified.isoformat(),
                        rev=result.metadata.rev,
                        size=result.metadata.size,
                        is_downloadable=result.metadata.is_downloadable,
                        content_hash=result.metadata.content_hash,
                    )
                    return {"metadata": asdict(file)}
                elif isinstance(result.metadata, dropbox.files.FolderMetadata):
                    folder = DropboxFolder(
                        id=result.metadata.id,
                        name=result.metadata.name,
                        path_lower=result.metadata.path_lower,
                        path_display=result.metadata.path_display,
                        shared_folder_id=result.metadata.shared_folder_id,
                    )
                    return {"metadata": asdict(folder)}

            return None

        except Exception as e:
            logger.error(f"Error moving item: {e}")
            return None

    async def copy_item(
        self,
        user_id: str,
        from_path: str,
        to_path: str,
        autorename: bool = True,
        allow_ownership_transfer: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Copy file or folder in Dropbox"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.files_copy_v2(
                from_path,
                to_path,
                autorename=autorename,
                allow_ownership_transfer=allow_ownership_transfer,
            )

            if result.metadata:
                if isinstance(result.metadata, dropbox.files.FileMetadata):
                    file = DropboxFile(
                        id=result.metadata.id,
                        name=result.metadata.name,
                        path_lower=result.metadata.path_lower,
                        path_display=result.metadata.path_display,
                        client_modified=result.metadata.client_modified.isoformat(),
                        server_modified=result.metadata.server_modified.isoformat(),
                        rev=result.metadata.rev,
                        size=result.metadata.size,
                        is_downloadable=result.metadata.is_downloadable,
                        content_hash=result.metadata.content_hash,
                    )
                    return {"metadata": asdict(file)}
                elif isinstance(result.metadata, dropbox.files.FolderMetadata):
                    folder = DropboxFolder(
                        id=result.metadata.id,
                        name=result.metadata.name,
                        path_lower=result.metadata.path_lower,
                        path_display=result.metadata.path_display,
                        shared_folder_id=result.metadata.shared_folder_id,
                    )
                    return {"metadata": asdict(folder)}

            return None

        except Exception as e:
            logger.error(f"Error copying item: {e}")
            return None

    # Sharing Operations
    async def create_shared_link(
        self, user_id: str, path: str, settings: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create shared link for file or folder"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            # Convert settings to Dropbox SharedLinkSettings
            link_settings = None
            if settings:
                link_settings = dropbox.sharing.SharedLinkSettings(**settings)

            result = dbx.sharing_create_shared_link_with_settings(path, link_settings)

            shared_link = DropboxSharedLink(
                url=result.url,
                name=result.name,
                path_lower=result.path_lower,
                link_permissions=result.link_permissions.to_dict(),
                preview_type=result.preview_type,
                client_modified=result.client_modified.isoformat()
                if result.client_modified
                else datetime.now().isoformat(),
                server_modified=result.server_modified.isoformat()
                if result.server_modified
                else datetime.now().isoformat(),
            )
            return asdict(shared_link)

        except Exception as e:
            logger.error(f"Error creating shared link: {e}")
            return None

    # User Operations
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get Dropbox user information"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.users_get_current_account()

            user = DropboxUser(
                account_id=result.account_id,
                name={
                    "given_name": result.name.given_name,
                    "surname": result.name.surname,
                    "familiar_name": result.name.familiar_name,
                    "display_name": result.name.display_name,
                    "abbreviated_name": result.name.abbreviated_name,
                },
                email=result.email,
                email_verified=result.email_verified,
                profile_photo_url=result.profile_photo_url,
                disabled=result.disabled,
                country=result.country,
                locale=result.locale,
                referral_link=result.referral_link,
            )
            return asdict(user)

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    async def get_space_usage(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get Dropbox space usage information"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.users_get_space_usage()

            space_usage = DropboxSpaceUsage(
                used=result.used, allocation=result.allocation.to_dict()
            )
            return asdict(space_usage)

        except Exception as e:
            logger.error(f"Error getting space usage: {e}")
            return None

    async def get_file_metadata(
        self,
        user_id: str,
        path: str,
        include_media_info: bool = False,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get detailed file metadata"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.files_get_metadata(
                path,
                include_media_info=include_media_info,
                include_deleted=include_deleted,
            )

            if isinstance(result, dropbox.files.FileMetadata):
                file = DropboxFile(
                    id=result.id,
                    name=result.name,
                    path_lower=result.path_lower,
                    path_display=result.path_display,
                    client_modified=result.client_modified.isoformat(),
                    server_modified=result.server_modified.isoformat(),
                    rev=result.rev,
                    size=result.size,
                    is_downloadable=result.is_downloadable,
                    content_hash=result.content_hash,
                    media_info=result.media_info.to_dict()
                    if result.media_info
                    else None,
                )
                return asdict(file)

            return None

        except Exception as e:
            logger.error(f"Error getting file metadata: {e}")
            return None

    async def list_file_versions(
        self, user_id: str, path: str, limit: int = 10
    ) -> Dict[str, Any]:
        """List file versions"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return []

            dbx = self._get_dropbox_client(access_token)

            result = dbx.files_list_revisions(path, limit=limit)

            versions = []
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    file = DropboxFile(
                        id=entry.id,
                        name=entry.name,
                        path_lower=entry.path_lower,
                        path_display=entry.path_display,
                        client_modified=entry.client_modified.isoformat(),
                        server_modified=entry.server_modified.isoformat(),
                        rev=entry.rev,
                        size=entry.size,
                        is_downloadable=entry.is_downloadable,
                        content_hash=entry.content_hash,
                    )
                    versions.append(asdict(file))

            return {"versions": versions, "is_deleted": result.is_deleted}

        except Exception as e:
            logger.error(f"Error listing file versions: {e}")
            return {"versions": [], "is_deleted": False}

    async def restore_file_version(
        self, user_id: str, path: str, rev: str
    ) -> Optional[Dict[str, Any]]:
        """Restore file to specific version"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            result = dbx.files_restore(path, rev)

            if isinstance(result, dropbox.files.FileMetadata):
                file = DropboxFile(
                    id=result.id,
                    name=result.name,
                    path_lower=result.path_lower,
                    path_display=result.path_display,
                    client_modified=result.client_modified.isoformat(),
                    server_modified=result.server_modified.isoformat(),
                    rev=result.rev,
                    size=result.size,
                    is_downloadable=result.is_downloadable,
                    content_hash=result.content_hash,
                )
                return asdict(file)

            return None

        except Exception as e:
            logger.error(f"Error restoring file version: {e}")
            return None

    async def get_file_preview(
        self, user_id: str, path: str
    ) -> Optional[Dict[str, Any]]:
        """Get file preview"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return None

            dbx = self._get_dropbox_client(access_token)

            metadata, response = dbx.files_get_preview(path)

            # Encode preview content to base64
            content_bytes = response.content
            content_base64 = base64.b64encode(content_bytes).decode("utf-8")

            return {
                "file_name": metadata.name,
                "content_bytes": content_base64,
                "mime_type": getattr(metadata, "media_info", {}).get(
                    "mime_type", "application/octet-stream"
                ),
                "rev": metadata.rev,
                "size": metadata.size,
            }

        except Exception as e:
            logger.error(f"Error getting file preview: {e}")
            return None

    async def get_service_status(self, user_id: str) -> Dict[str, Any]:
        """Get Dropbox service status"""
        try:
            access_token = await self._get_access_token(user_id)
            if not access_token:
                logger.error(f"No access token available for user {user_id}")
                return {"status": "unavailable", "message": "No access token"}

            # Test basic API connectivity
            dbx = self._get_dropbox_client(access_token)
            user_info = dbx.users_get_current_account()

            return {
                "status": "healthy",
                "service": "dropbox",
                "user": user_info.name.display_name,
                "email": user_info.email,
                "timestamp": datetime.now().isoformat(),
            }

        except AuthError:
            return {"status": "unauthenticated", "message": "Authentication failed"}
        except ApiError as e:
            return {"status": "error", "message": f"API error: {str(e)}"}
        except Exception as e:
            return {"status": "unavailable", "message": f"Service error: {str(e)}"}
