
import os
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import base64
import dropbox
from dropbox.exceptions import ApiError, AuthError

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class DropboxService(IntegrationService):
    """Standardized Dropbox API integration service"""

<<<<<<< HEAD
    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for API requests"""
=======
    def __init__(self, config: Dict[str, Any]):
        super().__init__(tenant_id, config)
        self.api_base_url = "https://api.dropboxapi.com/2"
        self.client_id = self.config.get("dropbox_client_id") or os.getenv("DROPBOX_APP_KEY")
        self.client_secret = self.config.get("dropbox_client_secret") or os.getenv("DROPBOX_APP_SECRET")
        self.access_token = self.config.get("access_token")
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": [
                {"id": "list_files", "name": "List Files"},
                {"id": "search_files", "name": "Search Files"},
                {"id": "download_file", "name": "Download File"},
                {"id": "upload_file", "name": "Upload File"},
                {"id": "create_folder", "name": "Create Folder"},
                {"id": "delete_item", "name": "Delete Item"},
                {"id": "get_space_usage", "name": "Get Space Usage"}
            ],
            "required_params": [],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True
        }

    async def execute_operation(
        self,
<<<<<<< HEAD
        path: str = "",
        access_token: str = None,
        recursive: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List files and folders"""

        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {
                "path": path,
                "recursive": recursive,
                "limit": limit
            }
            
            response = await self.client.post(
                f"{self.base_url}/files/list_folder",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("entries", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list folder: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to list folder: {str(e)}"
            )

    async def search(
        self,
        query: str,
        access_token: str = None,
        path: str = "",
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for files and folders"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {
                "query": query,
                "options": {
                    "path": path,
                    "max_results": max_results
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/files/search_v2",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            matches = data.get("matches", [])
            return [match.get("metadata", {}).get("metadata", {}) for match in matches]
        except httpx.HTTPError as e:
            logger.error(f"Failed to search: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to search: {str(e)}"
            )

    async def get_metadata(
        self,
        path: str,
        access_token: str = None
=======
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
    ) -> Dict[str, Any]:
        try:
            token = parameters.get("access_token") or self.access_token
            if not token:
                return {"success": False, "error": "Missing Dropbox access token"}
                
            dbx = dropbox.Dropbox(token)
            
<<<<<<< HEAD
            headers = self._get_headers(token)
            payload = {"path": path}
            
            response = await self.client.post(
                f"{self.base_url}/files/get_metadata",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get metadata: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get metadata: {str(e)}"
            )

    async def create_folder(
        self,
        path: str,
        access_token: str = None
    ) -> Dict[str, Any]:
        """Create a new folder"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {"path": path}
            
            response = await self.client.post(
                f"{self.base_url}/files/create_folder_v2",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to create folder: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create folder: {str(e)}"
            )

    async def upload_file(
        self,
        path: str,
        file_content: bytes,
        access_token: str = None,
        autorename: bool = True
    ) -> Dict[str, Any]:
        """Upload a file to Dropbox"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            import json
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps({
                    "path": path,
                    "mode": "add",
                    "autorename": autorename,
                    "mute": False,
                    "strict_conflict": False
                })
            }
            
            response = await self.client.post(
                f"{self.content_url}/files/upload",
                headers=headers,
                content=file_content
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to upload file: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to upload file: {str(e)}"
            )

    async def download_file(
        self,
        path: str,
        access_token: str = None
    ) -> bytes:
        """Download a file from Dropbox"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            import json
            headers = {
                "Authorization": f"Bearer {token}",
                "Dropbox-API-Arg": json.dumps({"path": path})
            }
            
            response = await self.client.post(
                f"{self.content_url}/files/download",
                headers=headers
            )
            response.raise_for_status()
            
            return response.content
        except httpx.HTTPError as e:
            logger.error(f"Failed to download file: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download file: {str(e)}"
            )

    async def delete_item(
        self,
        path: str,
        access_token: str = None
    ) -> Dict[str, Any]:
        """Delete a file or folder"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {"path": path}
            
            response = await self.client.post(
                f"{self.base_url}/files/delete_v2",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete item: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to delete item: {str(e)}"
            )

    async def move_item(
        self,
        from_path: str,
        to_path: str,
        access_token: str = None,
        autorename: bool = True
    ) -> Dict[str, Any]:
        """Move a file or folder"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {
                "from_path": from_path,
                "to_path": to_path,
                "autorename": autorename
            }
            
            response = await self.client.post(
                f"{self.base_url}/files/move_v2",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to move item: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to move item: {str(e)}"
            )

    async def copy_item(
        self,
        from_path: str,
        to_path: str,
        access_token: str = None,
        autorename: bool = True
    ) -> Dict[str, Any]:
        """Copy a file or folder"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {
                "from_path": from_path,
                "to_path": to_path,
                "autorename": autorename
            }
            
            response = await self.client.post(
                f"{self.base_url}/files/copy_v2",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to copy item: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to copy item: {str(e)}"
            )

    async def create_shared_link(
        self,
        path: str,
        access_token: str = None,
        settings: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a shared link for a file or folder"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {"path": path}
            if settings:
                payload["settings"] = settings
            
            response = await self.client.post(
                f"{self.base_url}/sharing/create_shared_link_with_settings",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to create shared link: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create shared link: {str(e)}"
            )

    async def get_account_info(self, access_token: str = None) -> Dict[str, Any]:
        """Get current account information"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.post(
                f"{self.base_url}/users/get_current_account",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get account info: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get account info: {str(e)}"
            )

    async def get_space_usage(self, access_token: str = None) -> Dict[str, Any]:
        """Get account space usage"""

        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.post(
                f"{self.base_url}/users/get_space_usage",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get space usage: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get space usage: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Dropbox service"""
=======
            if operation == "list_files":
                path = parameters.get("path", "")
                res = dbx.files_list_folder(path)
                entries = [{"id": e.id if hasattr(e, "id") else None, "name": e.name, "path": e.path_display, "type": "folder" if isinstance(e, dropbox.files.FolderMetadata) else "file"} for e in res.entries]
                return {"success": True, "result": {"entries": entries, "cursor": res.cursor, "has_more": res.has_more}}
                
            elif operation == "search_files":
                query = parameters.get("query", "")
                res = dbx.files_search_v2(query)
                matches = [{"name": m.metadata.get_metadata().name, "path": m.metadata.get_metadata().path_display} for m in res.matches]
                return {"success": True, "result": {"matches": matches, "has_more": res.has_more}}
                
            elif operation == "get_space_usage":
                res = dbx.users_get_space_usage()
                return {"success": True, "result": {"used": res.used, "allocation": str(res.allocation)}}
                
            else:
                raise NotImplementedError(f"Operation {operation} not supported for Dropbox")
        except Exception as e:
            return {"success": False, "error": str(e)}
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31

    def health_check(self) -> Dict[str, Any]:
        """Synchronous health check for Dropbox service"""
        try:
            is_healthy = bool(self.access_token or self.client_id)
            return {
                "ok": is_healthy,
                "status": "healthy" if is_healthy else "unhealthy",
                "healthy": is_healthy,
                "service": "dropbox",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
<<<<<<< HEAD
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "dropbox",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
dropbox_service = DropboxService()

def get_dropbox_service() -> DropboxService:
    """Get Dropbox service instance"""

    return dropbox_service
=======
            return {"ok": False, "status": "unhealthy", "healthy": False, "service": "dropbox", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
