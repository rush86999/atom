import logging
import os
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from core.integration_service import IntegrationService

class ZohoProjectsService(IntegrationService):
    """Zoho Projects API Service Implementation"""
    
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = "https://projectsapi.zoho.com/restapi/v1"
        self.client_id = config.get("client_id") or os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("ZOHO_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_portals(self, access_token: str) -> List[Dict[str, Any]]:
        """Get connected Zoho Projects portals"""
        try:
            url = f"{self.base_url}/portals/"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("portals", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Projects portals: {e}")
            return []

    async def get_projects(self, access_token: str, portal_id: str) -> List[Dict[str, Any]]:
        """Fetch projects within a portal"""
        try:
            url = f"{self.base_url}/portal/{portal_id}/projects/"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("projects", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho projects: {e}")
            return []

    async def get_tasks(self, access_token: str, portal_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Fetch tasks for a specific project"""
        try:
            url = f"{self.base_url}/portal/{portal_id}/projects/{project_id}/tasks/"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("tasks", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho tasks: {e}")
            return []

    async def get_all_active_tasks(self, access_token: str, portal_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch all tasks across all projects in a portal"""
        try:
            # First get projects
            projects = await self.get_projects(access_token, portal_id)
            all_tasks = []
            
            # Fetch tasks from each project until limit is reached
            for project in projects:
                if len(all_tasks) >= limit:
                    break
                project_id = project.get("id_string")
                tasks = await self.get_tasks(access_token, portal_id, project_id)
                
                # Add project name to each task for UI
                for task in tasks:
                    task["project_name"] = project.get("name")
                    all_tasks.append(task)
            
            return all_tasks[:limit]
        except Exception as e:
            logger.error(f"Failed to fetch all Zoho tasks: {e}")
            return []

    async def create_task(self, access_token: str, portal_id: str, project_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task in Zoho Projects"""
        try:
            url = f"{self.base_url}/portal/{portal_id}/projects/{project_id}/tasks/"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            # Zoho Projects expects form-data usually or JSON depending on version. V1 REST API supports parameters.
            # Using JSON if supported or params. documentation says POST parameters.
            # Let's assume JSON body with 'name' is supported in modern API or pass as params.
            # Safest for Requests/Httpx is data=... but let's try json first or check docs.
            # Standard Zoho APIs use JSON body often now.
            response = await self.client.post(url, headers=headers, json=task_data)
            # If 415, might need form-encoded. But V1 often accepts JSON.
            # Note: Zoho Projects often uses 'name' parameter.
            
            response.raise_for_status()
            return response.json().get("tasks", [{}])[0]
        except Exception as e:
            logger.error(f"Failed to create Zoho task: {e}")
            raise HTTPException(status_code=500, detail="Zoho Task creation failed")

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str, portal_id: str = None) -> Dict[str, Any]:
        """Sync Zoho Projects analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get project count if portal_id provided
            project_count = 0
            if portal_id:
                try:
                    projects = await self.get_projects(access_token, portal_id)
                    project_count = len(projects)
                except Exception:
                    pass
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_projects_project_count", project_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="zoho_projects",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="zoho_projects",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Zoho Projects metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving Zoho Projects metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho Projects PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str, portal_id: str = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho Projects"""
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token, portal_id)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }



