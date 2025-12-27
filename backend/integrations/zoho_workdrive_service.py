import os
import json
import logging
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ZohoWorkDriveService:
    """
    Zoho WorkDrive Service
    Handles file listing, downloading, and ingestion from Zoho WorkDrive.
    """

    def __init__(self):
        self.base_url = "https://workdrive.zoho.com/api/v1"
        self.accounts_url = "https://accounts.zoho.com/oauth/v2"
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.redirect_uri = os.getenv("ZOHO_REDIRECT_URI")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_access_token(self, user_id: str) -> Optional[str]:
        """Fetch access token for user from database (via DatabaseManager)"""
        try:
            from backend.database_manager import DatabaseManager
            db = DatabaseManager()
            
            tokens = await db.get_user_tokens(user_id, "zoho_workdrive")
            if not tokens:
                # Try generic zoho if available, or just fail
                tokens = await db.get_user_tokens(user_id, "zoho")
            
            if tokens and tokens.get("access_token"):
                if self._is_token_expired(tokens):
                    return await self.refresh_token(user_id, tokens)
                return tokens["access_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting Zoho access token: {e}")
            return None

    def _is_token_expired(self, tokens: Dict[str, Any]) -> bool:
        """Check if token is expired based on expires_at and current time"""
        expires_at = tokens.get("expires_at")
        if not expires_at:
            return True
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return datetime.now().astimezone() >= expires_dt
        except Exception:
            return True

    async def refresh_token(self, user_id: str, tokens: Dict[str, Any]) -> Optional[str]:
        """Refresh Zoho OAuth token"""
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return None
        
        try:
            url = f"{self.accounts_url}/token"
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token
            }
            
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            new_tokens = response.json()
            
            if "access_token" in new_tokens:
                # Update database
                from backend.database_manager import DatabaseManager
                db = DatabaseManager()
                
                # Calculate new expires_at
                expires_in = new_tokens.get("expires_in", 3600)
                from datetime import timedelta
                expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
                
                await db.save_user_tokens(user_id, "zoho_workdrive", {
                    "access_token": new_tokens["access_token"],
                    "refresh_token": refresh_token,  # Zoho refresh tokens are usually long-lived
                    "expires_at": expires_at
                })
                
                return new_tokens["access_token"]
            return None
        except Exception as e:
            logger.error(f"Failed to refresh Zoho token: {e}")
            return None

    async def get_teams(self, user_id: str) -> List[Dict[str, Any]]:
        """List WorkDrive teams for the user"""
        token = await self.get_access_token(user_id)
        if not token:
            return []
        
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            response = await self.client.get(f"{self.base_url}/teams", headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho WorkDrive teams: {e}")
            return []

    async def list_files(self, user_id: str, parent_id: str = "root") -> List[Dict[str, Any]]:
        """List files in a specific folder or 'root'"""
        token = await self.get_access_token(user_id)
        if not token:
            return []
        
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            # Parent ID can be a folder ID or team ID depending on structure
            # For simplicity, we assume parent_id is the folder_id
            url = f"{self.base_url}/files/{parent_id}/files"
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            files = []
            for item in data.get("data", []):
                attrs = item.get("attributes", {})
                files.append({
                    "id": item.get("id"),
                    "name": attrs.get("name"),
                    "type": item.get("type"),
                    "extension": attrs.get("extension"),
                    "size": attrs.get("size"),
                    "modified_at": attrs.get("modified_time_in_iso8601")
                })
            return files
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive files: {e}")
            return []

    async def download_file(self, user_id: str, file_id: str) -> Optional[bytes]:
        """Download file content from WorkDrive"""
        token = await self.get_access_token(user_id)
        if not token:
            return None
        
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            url = f"{self.base_url}/download/{file_id}"
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download Zoho WorkDrive file {file_id}: {e}")
            return None

    async def ingest_file_to_memory(self, user_id: str, file_id: str) -> Dict[str, Any]:
        """Download a file and process it through the ingestion pipeline"""
        content = await self.download_file(user_id, file_id)
        if not content:
            return {"success": False, "error": "Failed to download file"}
        
        try:
            # We need to get the file metadata first to know the name and extension
            token = await self.get_access_token(user_id)
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            resp = await self.client.get(f"{self.base_url}/files/{file_id}", headers=headers)
            resp.raise_for_status()
            meta = resp.json().get("data", {}).get("attributes", {})
            file_name = meta.get("name", "unknown")
            
            # Simple ingestion for now - in a real app, this would use DocumentParser
            from backend.core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()
            
            # Save temporarily if needed or pass bytes
            result = await ingestor.process_file_bytes(
                content, 
                file_name=file_name,
                source="zoho_workdrive",
                user_id=user_id
            )
            
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Failed to ingest Zoho WorkDrive file: {e}")
            return {"success": False, "error": str(e)}
