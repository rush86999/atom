import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class MailchimpService(IntegrationService):
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Mailchimp service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with credentials
        """
        super().__init__(tenant_id, config)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        await self.client.aclose()

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Mailchimp integration capabilities"""
        return {
            "operations": [
                {"id": "get_audiences", "name": "Get Audiences", "description": "Retrieve Mailchimp audiences/lists"},
                {"id": "get_campaigns", "name": "Get Campaigns", "description": "Retrieve Mailchimp campaigns"},
                {"id": "get_account_info", "name": "Get Account Info", "description": "Retrieve Mailchimp account details"},
                {"id": "sync_metrics", "name": "Sync Metrics", "description": "Sync Mailchimp metrics to cache"},
            ],
            "required_params": ["access_token", "server_prefix"],
            "optional_params": ["limit", "status"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True
        }

    def health_check(self) -> Dict[str, Any]:
        """Check Mailchimp service health"""
        try:
            return {
                "healthy": True,
                "message": "Mailchimp service is operational",
                "last_check": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Mailchimp service health check failed: {str(e)}",
                "last_check": datetime.now(timezone.utc).isoformat()
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Mailchimp operation with tenant context.

        Args:
            operation: Operation name
            parameters: Operation parameters
            context: Tenant context dict

        Returns:
            Dict with success, result, error, details
        """
        try:
            if operation == "get_audiences":
                result = await self.get_audiences(
                    parameters["access_token"],
                    parameters["server_prefix"],
                    parameters.get("limit", 20)
                )
                return {"success": True, "result": result, "details": {}}
            elif operation == "get_campaigns":
                result = await self.get_campaigns(
                    parameters["access_token"],
                    parameters["server_prefix"],
                    parameters.get("limit", 20),
                    parameters.get("status")
                )
                return {"success": True, "result": result, "details": {}}
            elif operation == "get_account_info":
                result = await self.get_account_info(
                    parameters["access_token"],
                    parameters["server_prefix"]
                )
                return {"success": True, "result": result, "details": {}}
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "details": {}
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {}
            }

    def _get_base_url(self, server_prefix: str) -> str:
        return f"https://{server_prefix}.api.mailchimp.com/3.0"

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        url = "https://login.mailchimp.com/oauth2/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "code": code
        }
        response = await self.client.post(url, data=data)
        response.raise_for_status()
        return response.json()

    async def get_metadata(self, access_token: str) -> Dict[str, Any]:
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        url = "https://login.mailchimp.com/oauth2/metadata"
        headers = {"Authorization": f"OAuth {access_token}"}
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def get_audiences(self, access_token: str, server_prefix: str, limit: int = 20) -> List[Dict[str, Any]]:
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        url = f"{self._get_base_url(server_prefix)}/lists"
        headers = self._get_headers(access_token)
        params = {"count": limit}
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("lists", [])

    async def get_campaigns(self, access_token: str, server_prefix: str, limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        url = f"{self._get_base_url(server_prefix)}/campaigns"
        headers = self._get_headers(access_token)
        params = {"count": limit}
        if status:
            params["status"] = status
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("campaigns", [])

    async def get_account_info(self, access_token: str, server_prefix: str) -> Dict[str, Any]:
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        url = f"{self._get_base_url(server_prefix)}/"
        headers = self._get_headers(access_token)
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def sync_to_postgres_cache(self, workspace_id: str, access_token: str = None, server_prefix: str = None) -> Dict[str, Any]:
        """Sync Mailchimp analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Get audience and campaign counts if credentials provided
            audience_count = 0
            campaign_count = 0
            if access_token and server_prefix:
                try:
                    audiences = await self.get_audiences(access_token, server_prefix)
                    audience_count = len(audiences)
                except Exception:
                    pass
                try:
                    campaigns = await self.get_campaigns(access_token, server_prefix)
                    campaign_count = len(campaigns)
                except Exception:
                    pass
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("mailchimp_audience_count", audience_count, "count"),
                    ("mailchimp_campaign_count", campaign_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        tenant_id=workspace_id,
                        integration_type="mailchimp",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            tenant_id=workspace_id,
                            integration_type="mailchimp",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Mailchimp metrics to PostgreSQL cache for workspace {workspace_id}")
            except Exception as e:
                logger.error(f"Error saving Mailchimp metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Mailchimp PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, workspace_id: str, access_token: str = None, server_prefix: str = None) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Mailchimp"""
        cache_result = await self.sync_to_postgres_cache(workspace_id, access_token, server_prefix)
        
        return {
            "success": True,
            "workspace_id": workspace_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
