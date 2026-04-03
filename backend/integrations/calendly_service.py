"""
Calendly Service for ATOM Platform
Provides comprehensive Calendly scheduling integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class CalendlyService(IntegrationService):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(tenant_id, config)
        self.base_url = "https://api.calendly.com"
        self.auth_url = "https://auth.calendly.com/oauth/authorize"
        self.token_url = "https://auth.calendly.com/oauth/token"
        self.client_id = config.get("client_id") or os.getenv("CALENDLY_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("CALENDLY_CLIENT_SECRET")
        self.access_token = config.get("access_token") or os.getenv("CALENDLY_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for API requests"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri
        }
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            response = await self.client.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Calendly token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_current_user(self, access_token: str = None) -> Dict[str, Any]:
        """Get current user information"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            response = await self.client.get(f"{self.base_url}/users/me", headers=headers)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get current user: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get user info: {str(e)}"
            )

    async def get_event_types(
        self, 
        user_uri: str,
        access_token: str = None,
        count: int = 20
    ) -> List[Dict[str, Any]]:
        """Get event types for a user"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"user": user_uri, "count": count}
            
            response = await self.client.get(
                f"{self.base_url}/event_types",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("collection", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get event types: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get event types: {str(e)}"
            )

    async def get_scheduled_events(
        self,
        user_uri: str = None,
        access_token: str = None,
        count: int = 20,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """Get scheduled events"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"count": count, "status": status}
            
            if user_uri:
                params["user"] = user_uri
            
            response = await self.client.get(
                f"{self.base_url}/scheduled_events",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("collection", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get scheduled events: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get scheduled events: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Calendly service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "calendly",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "calendly",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

<<<<<<< HEAD
# Singleton instance
calendly_service = CalendlyService()

def get_calendly_service() -> CalendlyService:
    """Get Calendly service instance"""
=======
    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a Calendly operation with tenant context."""
        try:
            token = parameters.get("access_token") or self.access_token

            if operation == "get_current_user":
                result = await self.get_current_user(token)
                return {"success": True, "result": result}
            elif operation == "get_event_types":
                result = await self.get_event_types(
                    user_uri=parameters["user_uri"],
                    access_token=token,
                    count=parameters.get("count", 20)
                )
                return {"success": True, "result": result}
            elif operation == "get_scheduled_events":
                result = await self.get_scheduled_events(
                    user_uri=parameters.get("user_uri"),
                    access_token=token,
                    count=parameters.get("count", 20),
                    status=parameters.get("status", "active")
                )
                return {"success": True, "result": result}
            elif operation == "full_sync":
                result = await self.full_sync(
                    workspace_id=parameters.get("workspace_id", self.tenant_id),
                    access_token=token
                )
                return {"success": True, "result": result}
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}"
                }
        except Exception as e:
            logger.error(f"Error executing Calendly operation {operation}: {e}")
            return {"success": False, "error": str(e)}
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str = None) -> Dict[str, Any]:
        """Sync Calendly analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get scheduled events
            try:
                events = await self.get_scheduled_events(access_token=access_token)
                event_count = len(events)
            except Exception:
                event_count = 0
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("calendly_event_count", event_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="calendly",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="calendly",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Calendly metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving Calendly metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Calendly PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Calendly"""
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# NOTE: Legacy singleton instance removed - use IntegrationRegistry instead
# calendly_service = CalendlyService("default", {})
# 
# def get_calendly_service() -> CalendlyService:
#     """Get Calendly service instance"""
#     return calendly_service
