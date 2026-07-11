import os
import json
import logging
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from core.database import SessionLocal
from core.connection_service import connection_service
from core.models import IntegrationMetric
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class ZohoWorkDriveService(IntegrationService):
    """
    Zoho WorkDrive Service
    Handles file listing, downloading, and ingestion from Zoho WorkDrive.
    """

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        
        # Use regional overrides if present (from HEAD)
        accounts_base = os.getenv("ZOHO_CRM_ACCOUNTS_URL", "https://accounts.zoho.com").rstrip("/")
        workdrive_base = "https://workdrive.zoho.com"
        
        # If accounts is .in, workdrive is likely .in
        if ".zoho.in" in accounts_base:
            workdrive_base = "https://workdrive.zoho.in"
        elif ".zoho.eu" in accounts_base:
            workdrive_base = "https://workdrive.zoho.eu"
        elif ".zoho.com.au" in accounts_base:
            workdrive_base = "https://workdrive.zoho.com.au"

        self.base_url = f"{workdrive_base}/api/v1"
        self.accounts_url = f"{accounts_base}/oauth/v2"
        self.client_id = config.get("client_id") or os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("ZOHO_CLIENT_SECRET")
        self.redirect_uri = config.get("redirect_uri") or os.getenv("ZOHO_REDIRECT_URI")
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
        """List WorkDrive teams for the user (Team Folders root).

        Required by the /teams route and the frontend ingestion picker.
        Hits GET /api/v1/teams and normalizes the JSON:API response.
        """
        token = await self.get_access_token(user_id)
        if not token:
            return []

        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            response = await self.client.get(f"{self.base_url}/teams", headers=headers)
            response.raise_for_status()
            data = response.json()

            teams = []
            for item in data.get("data", []):
                attrs = item.get("attributes", {})
                teams.append(
                    {
                        "id": item.get("id"),
                        "name": attrs.get("name") or attrs.get("display_name"),
                        "type": item.get("type", "teams"),
                        "status": attrs.get("status"),
                        "role": attrs.get("role"),
                    }
                )
            return teams
        except Exception as e:
            logger.error(f"Failed to list Zoho WorkDrive teams: {e}")
            return []

    async def list_files(self, user_id: str, parent_id: str = "root") -> List[Dict[str, Any]]:
        """List files in a specific folder or 'root'"""
        token = await self.get_access_token(user_id)
        if not token:
            return []
        
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
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
        token = await self.get_access_token(user_id)
        if not token:
            return {"success": False, "error": "No Zoho WorkDrive access token. Connect the integration first."}

        content = await self.download_file(user_id, file_id)
        if not content:
            return {"success": False, "error": "Failed to download file"}

        try:
            # Fetch file metadata to get the real name (reuse the already-resolved token).
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            resp = await self.client.get(f"{self.base_url}/files/{file_id}", headers=headers)
            resp.raise_for_status()
            meta = resp.json().get("data", {}).get("attributes", {})
            file_name = meta.get("name", "unknown")

            from core.auto_document_ingestion import AutoDocumentIngestionService
            ingestor = AutoDocumentIngestionService()

            result = await ingestor.process_file_bytes(
                content,
                file_name=file_name,
                source="zoho_workdrive",
                user_id=user_id,
            )

            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Failed to ingest Zoho WorkDrive file: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, user_id: str) -> Dict[str, Any]:
        """Sync Zoho WorkDrive analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            files = await self.list_files(user_id)
            file_count = len(files)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_workdrive_file_count", file_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="zoho_workdrive",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="zoho_workdrive",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
            except Exception as e:
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho WorkDrive PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho WorkDrive.

        Pipeline 1: Ingest parseable files into Atom memory (LanceDB + GraphRAG)
        via AutoDocumentIngestionService.
        Pipeline 2: Refresh the Postgres metrics cache.
        """
        ws_id = workspace_id or user_id
        files = await self.list_files(user_id)
        parseable_exts = (".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".md", ".pptx")

        ingested = 0
        errors: list[str] = []
        try:
            from core.auto_document_ingestion import AutoDocumentIngestionService

            ingestor = AutoDocumentIngestionService()
            for f in files:
                name = f.get("name", "") or ""
                if not name.lower().endswith(parseable_exts):
                    continue
                try:
                    res = await self.ingest_file_to_memory(user_id, f.get("id"))
                    if res.get("success"):
                        ingested += 1
                    elif res.get("error"):
                        errors.append(f"{name}: {res['error']}")
                except Exception as file_err:
                    errors.append(f"{name}: {file_err}")
        except Exception as e:
            logger.error(f"Zoho WorkDrive memory ingestion failed: {e}")
            errors.append(str(e))

        cache_result = await self.sync_to_postgres_cache(user_id)
        return {
            "success": True,
            "workspace_id": ws_id,
            "files_found": len(files),
            "files_ingested": ingested,
            "postgres_cache": cache_result,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -------------------------------------------------------------------------
    # IntegrationService abstract-method implementations
    # -------------------------------------------------------------------------
    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of the Zoho WorkDrive service."""
        return {
            "operations": [
                {"id": "list_files", "name": "List Files"},
                {"id": "download_file", "name": "Download File"},
                {"id": "ingest_file_to_memory", "name": "Ingest File to Memory"},
                {"id": "get_teams", "name": "Get Teams"},
                {"id": "full_sync", "name": "Full Sync"},
            ],
            "required_params": ["access_token"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": False,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check if the Zoho WorkDrive service is healthy."""
        return {
            "healthy": True,
            "status": "healthy",
            "service": "zoho_workdrive",
            "message": "Zoho WorkDrive service is operational",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a Zoho WorkDrive operation."""
        operations = {
            "list_files": self.list_files,
            "download_file": self.download_file,
            "ingest_file_to_memory": self.ingest_file_to_memory,
            "get_teams": self.get_teams,
            "full_sync": self.full_sync,
        }
        if operation not in operations:
            return {"success": False, "error": f"Unknown operation: {operation}"}
        try:
            user_id = (context or {}).get("user_id") or parameters.get("user_id") or self.tenant_id
            fn = operations[operation]
            result = await fn(user_id, **{k: v for k, v in parameters.items() if k != "user_id"})
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Zoho WorkDrive operation {operation} failed: {e}")
            return {"success": False, "error": str(e)}


# Create a default instance for hub_sync_service compatibility
zoho_workdrive_service = ZohoWorkDriveService("default", {})

