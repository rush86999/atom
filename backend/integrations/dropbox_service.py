
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

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.api_base_url = "https://api.dropboxapi.com/2"
        self.client_id = self.config.get("dropbox_client_id") or os.getenv("DROPBOX_APP_KEY")
        self.client_secret = self.config.get("dropbox_client_secret") or os.getenv("DROPBOX_APP_SECRET")
        self.access_token = self.config.get("access_token")

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
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            token = parameters.get("access_token") or self.access_token
            if not token:
                return {"success": False, "error": "Missing Dropbox access token"}
                
            dbx = dropbox.Dropbox(token)
            
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
            return {"ok": False, "status": "unhealthy", "healthy": False, "service": "dropbox", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
