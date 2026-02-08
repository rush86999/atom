from datetime import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

from core.connection_service import connection_service
from core.database import get_db_session
from core.models import IngestedDocument, IntegrationMetric

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
        """Fetch access token for user using ConnectionService"""
        try:
            # Find a zoho_workdrive or generic zoho connection
            connections = connection_service.get_connections(user_id, "zoho_workdrive")
            if not connections:
                connections = connection_service.get_connections(user_id, "zoho")
            
            if not connections:
                return None
            
            # Use the first active connection
            conn_id = connections[0]["id"]
            creds = await connection_service.get_connection_credentials(conn_id, user_id)
            
            if creds and creds.get("access_token"):
                return creds["access_token"]
            return None
        except Exception as e:
            logger.error(f"Error getting Zoho access token: {e}")
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
            
            # Use AutoDocumentIngestionService
            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()
            
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

    async def sync_files_to_db(self, user_id: str, tenant_id: str = "default", workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Sync Zoho WorkDrive file metadata to the persistent IngestedDocument table."""
        try:
            files = await self.list_files(user_id)
            if not files:
                return {"success": True, "files_synced": 0}
            
            with get_db_session() as db:
            synced_count = 0
            try:
                for f in files:
                    if f["type"] == "folder":
                        continue
                        
                    # Check if already exists
                    existing = db.query(IngestedDocument).filter_by(
                        integration_id="zoho_workdrive",
                        external_id=f["id"]
                    ).first()
                    
                    modified_at = None
                    if f.get("modified_at"):
                        try:
                            modified_at = datetime.fromisoformat(f["modified_at"].replace("Z", "+00:00"))
                        except Exception as e:
                            pass

                    if existing:
                        existing.file_name = f["name"]
                        existing.file_type = f.get("extension", "file")
                        existing.file_size_bytes = f.get("size", 0)
                        existing.external_modified_at = modified_at
                        existing.updated_at = datetime.utcnow()
                    else:
                        doc = IngestedDocument(
                            workspace_id=workspace_id or "default",
                            tenant_id=tenant_id,
                            file_name=f["name"],
                            file_path=f["name"],
                            file_type=f.get("extension", "file"),
                            integration_id="zoho_workdrive",
                            file_size_bytes=f.get("size", 0),
                            external_id=f["id"],
                            external_modified_at=modified_at
                        )
                        db.add(doc)
                    synced_count += 1
                
                db.commit()
                logger.info(f"Synced {synced_count} Zoho WorkDrive files for user {user_id}")
            except Exception as e:
                db.rollback()
                logger.error(f"Error syncing Zoho files to DB: {e}")
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "files_synced": synced_count}
        except Exception as e:
            logger.error(f"Zoho WorkDrive file sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, user_id: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Sync Zoho WorkDrive analytics to PostgreSQL IntegrationMetric table."""
        try:
            # List files to get counts
            files = await self.list_files(user_id)
            file_count = len(files)
            
            # Count by type
            docs_count = sum(1 for f in files if f.get("type") == "files")
            
            with get_db_session() as db:
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_workdrive_file_count", file_count, "count"),
                    ("zoho_workdrive_docs_count", docs_count, "count"),
                ]
                
                ws_id = workspace_id or "default"
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=ws_id,
                        integration_type="zoho_workdrive",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = value
                        existing.last_synced_at = datetime.utcnow()
                    else:
                        metric = IntegrationMetric(
                            workspace_id=ws_id,
                            integration_type="zoho_workdrive",
                            metric_key=key,
                            value=value,
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Zoho WorkDrive metrics to PostgreSQL cache")
            except Exception as e:
                logger.error(f"Error saving Zoho WorkDrive metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho WorkDrive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str, tenant_id: str = "default", workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho WorkDrive"""
        # Pipeline 1: Persistent Cache & Metrics
        cache_result = await self.sync_to_postgres_cache(user_id, workspace_id)
        
        # Pipeline 2: File Metadata Sync
        file_sync_result = await self.sync_files_to_db(user_id, tenant_id, workspace_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "postgres_cache": cache_result,
            "file_sync": file_sync_result,
            "timestamp": datetime.utcnow().isoformat()
        }

# Singleton instance
zoho_workdrive_service = ZohoWorkDriveService()
