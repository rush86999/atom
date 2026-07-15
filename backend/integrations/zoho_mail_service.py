import logging
import os
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from core.integration_service import IntegrationService

class ZohoMailService(IntegrationService):
    """Zoho Mail API Service Implementation"""
    
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = "https://mail.zoho.com/api/v1"
        self.client_id = config.get("client_id") or os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("ZOHO_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    # ---- IntegrationService abstract-method implementations ----
    # Satisfies the ABC contract from core.integration_service so the class
    # can be instantiated by ServiceFactory / routers.

    def get_capabilities(self) -> Dict[str, Any]:
        """Return the operations this Zoho service exposes."""
        return {
            "operations": ['get_accounts', 'get_messages', 'get_recent_inbox'],
            "required_params": ["access_token"],
            "optional_params": ["organization_id", "tenant_id"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": False,
        }

    def health_check(self) -> Dict[str, Any]:
        """Return a basic health snapshot (token presence + base URL)."""
        from datetime import datetime, timezone
        return {
            "healthy": bool(getattr(self, "access_token", None)),
            "message": "connected" if getattr(self, "access_token", None) else "no access token configured",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "base_url": getattr(self, "base_url", None),
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatch a named operation to the service's existing methods."""
        try:
            if operation == "get_accounts":
                return {"success": True, "result": await self.get_accounts(parameters.get("access_token") or self.access_token)}
            if operation == "get_recent_inbox":
                return {"success": True, "result": await self.get_recent_inbox(parameters.get("access_token") or self.access_token)}
            return {
                "success": False,
                "error": f"Unsupported operation: {operation}",
                "supported": ['get_accounts', 'get_recent_inbox'],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get Zoho Mail accounts"""
        try:
            url = f"{self.base_url}/accounts"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Mail accounts: {e}")
            return []

    async def get_messages(self, access_token: str, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent messages for a specific account"""
        try:
            # We look at the 'inbox' folder by default (folderId: 1 usually)
            url = f"{self.base_url}/accounts/{account_id}/messages/view"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            params = {"limit": limit}
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Mail messages: {e}")
            return []

    async def get_recent_inbox(self, access_token: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch messages from the primary account's inbox"""
        try:
            accounts = await self.get_accounts(access_token)
            if not accounts:
                return []
            
            # Use the first account (primary)
            account_id = accounts[0].get("accountId")
            return await self.get_messages(access_token, account_id, limit=limit)
        except Exception as e:
            logger.error(f"Failed to fetch recent Zoho Mail: {e}")
            return []
    async def sync_to_postgres_cache(self, user_id: str, access_token: str) -> Dict[str, Any]:
        """Sync Zoho Mail analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Fetch accounts to get basic info
            accounts = await self.get_accounts(access_token)
            if not accounts:
                return {"success": False, "error": "No accounts found"}
                
            account_id = accounts[0].get("accountId")
            
            # Fetch messages to get a sense of volume
            messages = await self.get_messages(access_token, account_id, limit=100)
            message_count = len(messages)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_mail_account_count", len(accounts), "count"),
                    ("zoho_mail_recent_messages", message_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="zoho_mail",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="zoho_mail",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Zoho Mail metrics to PostgreSQL cache for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving Zoho Mail metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho Mail PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str, access_token: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho Mail"""
        # Pipeline 1: Atom Memory
        # Triggered via zoho_mail_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(user_id, access_token)
        
        return {
            "success": True,
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


