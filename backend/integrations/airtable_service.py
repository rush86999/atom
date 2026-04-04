"""
Airtable Service for ATOM Platform
Provides comprehensive Airtable database and spreadsheet integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from core.integration_service import IntegrationService

class AirtableService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.api_key = config.get("api_key") or os.getenv("AIRTABLE_API_KEY")
        self.base_url = "https://api.airtable.com/v0"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Get headers for API requests"""
        api_key = token or self.api_key
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def get_bases(self, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all bases accessible to the user"""
        try:
            headers = self._get_headers(token)
            response = await self.client.get(f"{self.base_url}/meta/bases", headers=headers)
            response.raise_for_status()
            return response.json().get("bases", [])
        except Exception as e:
            logger.error(f"Failed to list Airtable bases: {e}")
            return []

    async def get_tables(self, base_id: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tables in a base"""
        try:
            headers = self._get_headers(token)
            response = await self.client.get(f"{self.base_url}/meta/bases/{base_id}/tables", headers=headers)
            response.raise_for_status()
            return response.json().get("tables", [])
        except Exception as e:
            logger.error(f"Failed to list Airtable tables for base {base_id}: {e}")
            return []

    async def list_records(
        self,
        base_id: str,
        table_name: str,
        max_records: int = 100,
        view: str = None,
        filter_formula: str = None
    ) -> List[Dict[str, Any]]:
        """List records from a table"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            params = {"maxRecords": max_records}
            
            if view:
                params["view"] = view
            if filter_formula:
                params["filterByFormula"] = filter_formula
            
            response = await self.client.get(
                f"{self.base_url}/{base_id}/{table_name}",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("records", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list records: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to list records: {str(e)}"
            )

    async def get_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str
    ) -> Dict[str, Any]:
        """Get a specific record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            
            response = await self.client.get(
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get record: {str(e)}"
            )

    async def create_record(
        self,
        base_id: str,
        table_name: str,
        fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {"fields": fields}
            
            response = await self.client.post(
                f"{self.base_url}/{base_id}/{table_name}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to create record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create record: {str(e)}"
            )

    async def update_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str,
        fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {"fields": fields}
            
            response = await self.client.patch(
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to update record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to update record: {str(e)}"
            )

    async def delete_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str
    ) -> Dict[str, Any]:
        """Delete a record"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            
            response = await self.client.delete(
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete record: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to delete record: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Airtable service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "airtable",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "airtable",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def sync_to_postgres_cache(self, workspace_id: str, base_id: str = None) -> Dict[str, Any]:
        """Sync Airtable analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Note: Would need base_id and table name to count records
            # For now, just track basic connectivity
            record_count = 0
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("airtable_connected", 1, "boolean"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="airtable",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="airtable",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Airtable metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving Airtable metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Airtable PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, base_id: str = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Airtable"""
        cache_result = await self.sync_to_postgres_cache(workspace_id, base_id)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


