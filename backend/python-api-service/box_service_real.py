# Real Box service implementation using Box SDK 10.0.0+
# This provides real implementations for Box API functionality

import os
from typing import Dict, Any, Optional, List
from box_sdk_gen import BoxClient, BoxOAuth, OAuthConfig
from box_sdk_gen.networking.network import NetworkSession
from box_sdk_gen.schemas.access_token import AccessToken
import db_oauth_box, crypto_utils
import logging

logger = logging.getLogger(__name__)

from mcp_base import MCPBase

class BoxServiceReal(MCPBase):
    def __init__(self, client: BoxClient):
        self.client = client
        self.is_mock = False

    def list_files(
        self,
        folder_id: str = '0',
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get files from a Box folder with optional search filtering"""
        try:
            if query:
                # Use Box search API
                search_manager = self.client.search()
                search_results = search_manager.search(
                    query=query,
                    limit=page_size,
                    offset=int(page_token) if page_token else 0
                )

                files = []
                for item in search_results.entries:
                    files.append({
                        "id": item.id,
                        "name": item.name,
                        "type": item.type,
                        "size": item.size if hasattr(item, 'size') else None,
                        "modified_at": item.modified_at if hasattr(item, 'modified_at') else None,
                        "url": item.url if hasattr(item, 'url') else None
                    })

                next_page_token = str(int(page_token or '0') + len(files)) if len(files) == page_size else None
            else:
                # List files in specific folder
                folder_manager = self.client.folders()
                folder_items = folder_manager.get_folder_items(
                    folder_id=folder_id,
                    limit=page_size,
                    offset=int(page_token) if page_token else 0
                )

                files = []
                for item in folder_items.entries:
                    files.append({
                        "id": item.id,
                        "name": item.name,
                        "type": item.type,
                        "size": item.size if hasattr(item, 'size') else None,
                        "modified_at": item.modified_at if hasattr(item, 'modified_at') else None,
                        "url": item.url if hasattr(item, 'url') else None
                    })

                next_page_token = str(int(page_token or '0') + len(files)) if len(files) == page_size else None

            return {
                "status": "success",
                "data": {
                    "files": files,
                    "nextPageToken": next_page_token,
                    "total_count": len(files)
                }
            }
        except Exception as e:
            logger.error(f"Error listing Box files: {e}")
            return {"status": "error", "message": str(e)}

    def get_file_metadata(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Get detailed information about a specific Box file"""
        try:
            file_manager = self.client.files()
            file_info = file_manager.get_file(file_id)

            return {
                "status": "success",
                "data": {
                    "id": file_info.id,
                    "name": file_info.name,
                    "type": file_info.type,
                    "size": file_info.size if hasattr(file_info, 'size') else None,
                    "modified_at": file_info.modified_at if hasattr(file_info, 'modified_at') else None,
                    "created_at": file_info.created_at if hasattr(file_info, 'created_at') else None,
                    "description": file_info.description if hasattr(file_info, 'description') else None,
                    "url": file_info.url if hasattr(file_info, 'url') else None,
                    "parent": {
                        "id": file_info.parent.id,
                        "name": file_info.parent.name
                    } if hasattr(file_info, 'parent') and file_info.parent else None
                }
            }
        except Exception as e:
            logger.error(f"Error getting Box file metadata: {e}")
            return {"status": "error", "message": str(e)}

    def download_file(
        self,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Download a file from Box"""
        try:
            file_manager = self.client.files()
            file_info = file_manager.get_file(file_id)
            file_content = file_manager.download_file(file_id)

            return {
                "status": "success",
                "data": {
                    "file_name": file_info.name,
                    "content_bytes": file_content.content,
                    "mime_type": file_info.type,
                    "size": file_info.size if hasattr(file_info, 'size') else None
                }
            }
        except Exception as e:
            logger.error(f"Error downloading Box file: {e}")
            return {"status": "error", "message": str(e)}

    def get_service_status(self) -> Dict[str, Any]:
        """Get Box service status and connectivity information"""
        try:
            # Test connectivity by getting current user info
            user_manager = self.client.users()
            current_user = user_manager.get_user('me')

            return {
                "status": "connected",
                "message": "Box service connected successfully",
                "available": True,
                "mock_data": False,
                "user": {
                    "id": current_user.id,
                    "name": current_user.name,
                    "login": current_user.login if hasattr(current_user, 'login') else None,
                    "email": current_user.email if hasattr(current_user, 'email') else None
                }
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "message": f"Box service connection failed: {str(e)}",
                "available": False,
                "mock_data": False
            }

def get_box_client_real(access_token: str, refresh_token: Optional[str] = None) -> BoxServiceReal:
    """
    Create a real Box client with OAuth2 tokens
    """
    try:
        # Create OAuth configuration
        client_id = os.getenv("BOX_CLIENT_ID")
        client_secret = os.getenv("BOX_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.error("Box client credentials not configured")
            return None

        # Create OAuth config
        oauth_config = OAuthConfig(
            client_id=client_id,
            client_secret=client_secret
        )

        # Create BoxOAuth authentication
        box_oauth = BoxOAuth(oauth_config)

        # Set the access token directly (simplified approach)
        # In a real implementation, you'd use proper token management
        box_oauth.access_token = access_token
        if refresh_token:
            box_oauth.refresh_token = refresh_token

        # Create Box client
        box_client = BoxClient(box_oauth)

        return BoxServiceReal(box_client)

    except Exception as e:
        logger.error(f"Error creating Box client: {e}")
        return None
