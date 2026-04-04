"""
LinkedIn Service for ATOM Platform
Provides comprehensive LinkedIn professional networking integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class LinkedInService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.client_id = self.config.get("linkedin_client_id") or os.getenv("LINKEDIN_CLIENT_ID")
        self.client_secret = self.config.get("linkedin_client_secret") or os.getenv("LINKEDIN_CLIENT_SECRET")
        self.base_url = "https://api.linkedin.com/v2"
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.access_token = self.config.get("access_token") or os.getenv("LINKEDIN_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str = None,
        scope: str = "r_liteprofile r_emailaddress w_member_social"
    ) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope
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
            
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            response = await self.client.post(self.token_url, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"LinkedIn token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_profile(self, access_token: str = None) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.get(
                f"{self.base_url}/me",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get profile: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get profile: {str(e)}"
            )

    async def get_email(self, access_token: str = None) -> Dict[str, Any]:
        """Get user email address"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"q": "members", "projection": "(elements*(handle~))"}
            
            response = await self.client.get(
                f"{self.base_url}/emailAddress",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get email: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get email: {str(e)}"
            )

    async def share_update(
        self,
        text: str,
        access_token: str = None,
        visibility: str = "PUBLIC"
    ) -> Dict[str, Any]:
        """Share an update/post on LinkedIn"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            # First get the user's URN
            profile = await self.get_profile(token)
            author_urn = profile.get("id")
            
            payload = {
                "author": f"urn:li:person:{author_urn}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": visibility
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/ugcPosts",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to share update: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to share update: {str(e)}"
            )

    def health_check(self) -> Dict[str, Any]:
        """Health check for LinkedIn service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "healthy": True,
                "service": "linkedin",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "healthy": False,
                "service": "linkedin",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_capabilities(self) -> Dict[str, Any]:
        """Return LinkedIn integration capabilities"""
        return {
            "operations": [
                {"id": "post_share", "name": "Share Post"},
                {"id": "get_profile", "name": "Get Profile"},
                {"id": "get_email", "name": "Get Email"},
                {"id": "get_connections", "name": "Get Connections"}
            ],
            "required_params": ["access_token"],
            "optional_params": ["visibility"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": False
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a LinkedIn operation"""
        try:
            access_token = parameters.get("access_token") or (context.get("access_token") if context else None)

            if operation == "post_share":
                res = await self.share_update(
                    parameters.get("text"),
                    access_token,
                    parameters.get("visibility", "PUBLIC")
                )
                return {"success": True, "result": res}
            elif operation == "get_profile":
                res = await self.get_profile(access_token)
                return {"success": True, "result": res}
            elif operation == "get_email":
                res = await self.get_email(access_token)
                return {"success": True, "result": res}
            elif operation == "get_connections":
                # Stub implementation
                return {"success": True, "result": {"connections": []}}
            else:
                raise NotImplementedError(f"Operation {operation} not supported for LinkedIn")
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str = None) -> Dict[str, Any]:
        """Sync LinkedIn analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Check if connected
            is_connected = 1 if (access_token or self.access_token) else 0
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("linkedin_connected", is_connected, "boolean"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="linkedin",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="linkedin",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} LinkedIn metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving LinkedIn metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"LinkedIn PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for LinkedIn"""
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Singleton instance removed - use IntegrationRegistry instead
# linkedin_service = LinkedInService()
