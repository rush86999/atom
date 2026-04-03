
import logging
import os
import base64
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException
from datetime import datetime, timezone

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class XeroService(IntegrationService):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(tenant_id, config)
        self.base_url = "https://api.xero.com/api.xro/2.0"
        self.client_id = config.get("client_id") or os.getenv("XERO_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("XERO_CLIENT_SECRET")
        self.access_token = config.get("access_token") or os.getenv("XERO_ACCESS_TOKEN")
        self.xero_tenant_id = config.get("xero_tenant_id") or os.getenv("XERO_TENANT_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self, access_token: str, tenant_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        if tenant_id:
            headers["Xero-tenant-id"] = tenant_id
        return headers

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            url = "https://identity.xero.com/connect/token"
            
            # Xero requires Basic Auth with client_id:client_secret for token exchange
            auth_str = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }
            
            response = await self.client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Xero token exchange failed: {e}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

    async def get_tenants(self, access_token: str) -> List[Dict[str, Any]]:
        """Get connected tenants (organizations)"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = "https://api.xero.com/connections"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get tenants: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch tenants: {str(e)}")

    async def get_invoices(self, access_token: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of invoices"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/Invoices"
            headers = self._get_headers(access_token, tenant_id)
            # Xero doesn't support 'limit' param directly in same way, but we can filter or just take top N
            # For simplicity, we'll just fetch and slice
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            invoices = data.get("Invoices", [])
            return invoices[:limit]
        except Exception as e:
            logger.error(f"Failed to get invoices: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {str(e)}")

    async def get_contacts(self, access_token: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of contacts"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            url = f"{self.base_url}/Contacts"
            headers = self._get_headers(access_token, tenant_id)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            contacts = data.get("Contacts", [])
            return contacts[:limit]
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch contacts: {str(e)}")

<<<<<<< HEAD
=======
    def health_check(self) -> Dict[str, Any]:
        """Health check for Xero service"""
        return {
            "healthy": bool(self.client_id and self.client_secret),
            "status": "operational" if self.client_id else "incomplete_config",
            "service": "xero",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a Xero operation with tenant context."""
        try:
            access_token = parameters.get("access_token") or self.access_token
            xero_tenant_id = parameters.get("xero_tenant_id") or self.xero_tenant_id

            if operation == "get_tenants":
                result = await self.get_tenants(access_token)
                return {"success": True, "result": result}
            elif operation == "get_invoices":
                result = await self.get_invoices(
                    access_token, 
                    xero_tenant_id, 
                    limit=parameters.get("limit", 20)
                )
                return {"success": True, "result": result}
            elif operation == "get_contacts":
                result = await self.get_contacts(
                    access_token, 
                    xero_tenant_id, 
                    limit=parameters.get("limit", 20)
                )
                return {"success": True, "result": result}
            elif operation == "full_sync":
                result = await self.full_sync(
                    user_id=parameters.get("user_id", self.tenant_id),
                    access_token=access_token,
                    tenant_id=xero_tenant_id
                )
                return {"success": True, "result": result}
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}"
                }
        except Exception as e:
            logger.error(f"Error executing Xero operation {operation}: {e}")
            return {"success": False, "error": str(e)}
    async def sync_to_postgres_cache(self, user_id: str, access_token: str) -> Dict[str, Any]:
        """Sync Xero analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            from datetime import datetime, timezone
            
            # Fetch invoices to get counts
            invoices = await self.get_invoices(access_token, tenant_id, limit=100)
            invoice_count = len(invoices)
            
            # Fetch contacts to get counts
            contacts = await self.get_contacts(access_token, tenant_id, limit=100)
            contact_count = len(contacts)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("xero_invoice_count", invoice_count, "count"),
                    ("xero_contact_count", contact_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="xero",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="xero",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Xero metrics to PostgreSQL cache for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving Xero metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Xero PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str, access_token: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Xero"""
        # Pipeline 1: Atom Memory
        # Triggered via xero_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(user_id, access_token, tenant_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# NOTE: Legacy singleton instance removed - use IntegrationRegistry instead
# xero_service = XeroService("default", {})
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
