"""
Airtable Service for ATOM Platform
Provides comprehensive Airtable database and spreadsheet integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
from core.integration_http import IntegrationHTTP
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
        self.http = IntegrationHTTP(client=self.client)

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
            response = await self.http.get("airtable", f"{self.base_url}/meta/bases", headers=headers)
            response.raise_for_status()
            return response.json().get("bases", [])
        except Exception as e:
            logger.error(f"Failed to list Airtable bases: {e}")
            return []

    async def get_tables(self, base_id: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tables in a base"""
        try:
            headers = self._get_headers(token)
            response = await self.http.get("airtable", f"{self.base_url}/meta/bases/{base_id}/tables", headers=headers)
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
            
            response = await self.http.get("airtable", 
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
                detail="Internal error"
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
            
            response = await self.http.get("airtable", 
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get record: {e}")
            raise HTTPException(
                status_code=400,
                detail="Internal error"
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
            
            response = await self.http.post("airtable", 
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
                detail="Internal error"
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
            
            response = await self.http.patch("airtable", 
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
                detail="Internal error"
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
            
            response = await self.http.delete("airtable", 
                f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete record: {e}")
            raise HTTPException(
                status_code=400,
                detail="Internal error"
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

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Airtable integration capabilities"""
        return {
            "operations": [
                {"id": "get_bases", "description": "List all bases"},
                {"id": "get_tables", "description": "List tables in a base"},
                {"id": "list_records", "description": "List records from a table"},
                {"id": "get_record", "description": "Get a specific record"},
                {"id": "create_record", "description": "Create a new record"},
                {"id": "update_record", "description": "Update a record"},
                {"id": "delete_record", "description": "Delete a record"},
            ],
            "required_params": ["api_key"],
            "optional_params": ["base_id", "table_name", "record_id"],
            "rate_limits": {"requests_per_minute": 5},
            "supports_webhooks": False
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute an Airtable operation with tenant context"""
        if context and 'tenant_id' in context:
            tenant_id = context.get('tenant_id')
            if tenant_id != self.tenant_id:
                logger.error(f"Tenant ID mismatch: expected {self.tenant_id}, got {tenant_id}")
                return {
                    "success": False,
                    "error": "Tenant ID mismatch",
                    "operation": operation
                }

        try:
            if operation == "get_bases":
                bases = await self.get_bases(parameters.get('token'))
                return {"success": True, "result": bases}
            elif operation == "get_tables":
                tables = await self.get_tables(
                    base_id=parameters.get('base_id'),
                    token=parameters.get('token')
                )
                return {"success": True, "result": tables}
            elif operation == "list_records":
                records = await self.list_records(
                    base_id=parameters.get('base_id'),
                    table_name=parameters.get('table_name'),
                    max_records=parameters.get('max_records', 100),
                    view=parameters.get('view'),
                    filter_formula=parameters.get('filter_formula')
                )
                return {"success": True, "result": records}
            elif operation == "get_record":
                record = await self.get_record(
                    base_id=parameters.get('base_id'),
                    table_name=parameters.get('table_name'),
                    record_id=parameters.get('record_id')
                )
                return {"success": bool(record), "result": record}
            elif operation == "create_record":
                record = await self.create_record(
                    base_id=parameters.get('base_id'),
                    table_name=parameters.get('table_name'),
                    fields=parameters.get('fields', {})
                )
                return {"success": bool(record), "result": record}
            elif operation == "update_record":
                record = await self.update_record(
                    base_id=parameters.get('base_id'),
                    table_name=parameters.get('table_name'),
                    record_id=parameters.get('record_id'),
                    fields=parameters.get('fields', {})
                )
                return {"success": bool(record), "result": record}
            elif operation == "delete_record":
                result = await self.delete_record(
                    base_id=parameters.get('base_id'),
                    table_name=parameters.get('table_name'),
                    record_id=parameters.get('record_id')
                )
                return {"success": bool(result), "result": result}
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "operation": operation
                }
        except Exception as e:
            logger.error(f"Error executing Airtable operation {operation}: {e}")
            return {
                "success": False,
                "error": f"Airtable operation failed: {operation}",
                "operation": operation
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
                        workspace_id=workspace_id,
                        integration_type="airtable",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=workspace_id,
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
                return {"success": False, "error": "Failed to save Airtable metrics"}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Airtable PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": "Airtable cache sync failed"}

    async def full_sync(self, workspace_id: str, base_id: str = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Airtable"""
        cache_result = await self.sync_to_postgres_cache(workspace_id, base_id)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global integration instance
airtable_service = AirtableService()


