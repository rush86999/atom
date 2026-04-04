import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from core.integration_service import IntegrationService

class ZohoInventoryService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = "https://inventory.zoho.com/api/v1"
        self.client_id = config.get("client_id") or os.getenv("ZOHO_INVENTORY_CLIENT_ID") or os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = config.get("client_secret") or os.getenv("ZOHO_INVENTORY_CLIENT_SECRET") or os.getenv("ZOHO_CLIENT_SECRET")
        self.access_token = config.get("access_token")
        self.organization_id = config.get("organization_id") or os.getenv("ZOHO_ORG_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _get_active_token(self, tenant_id: Optional[str] = None) -> Optional[str]:
        """Get a valid access token for the tenant, refreshing if necessary"""
        tid = tenant_id or self.session_id or self.tenant_id
        if not tid:
            return self.access_token or os.getenv("ZOHO_INVENTORY_ACCESS_TOKEN")

        from core.database import SessionLocal
        from core.models import IntegrationToken
        from datetime import datetime, timezone, timedelta

        db = SessionLocal()
        try:
            token_record = db.query(IntegrationToken).filter(
                IntegrationToken.tenant_id == tid,
                IntegrationToken.provider == "zoho_inventory"
            ).first()

            if not token_record:
                return None

            now = datetime.now(timezone.utc)
            expires_at = token_record.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if not expires_at or expires_at < (now + timedelta(minutes=2)):
                if token_record.refresh_token:
                    new_tokens = await self.refresh_token(token_record.refresh_token)
                    if new_tokens:
                        token_record.access_token = new_tokens["access_token"]
                        token_record.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_tokens.get("expires_in", 3600))
                        db.commit()
                        return token_record.access_token
                return None

            return token_record.access_token
        except Exception as e:
            logger.error(f"Error retrieving Zoho Inventory token for tenant {tid}: {e}")
            return None
        finally:
            db.close()

    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh Zoho Inventory access token using refresh token"""
        try:
            token_url = "https://accounts.zoho.com/oauth/v2/token"
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            }

            response = await self.client.post(token_url, data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to refresh Zoho Inventory token: {e}")
            return None

    async def get_items(self, token: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch items list for pricing and availability checks"""
        try:
            active_token = token or self.access_token
            active_org = organization_id or self.organization_id
            
            if not active_token:
                 raise HTTPException(status_code=401, detail="Not authenticated")
            if not active_org:
                 raise HTTPException(status_code=400, detail="Organization ID required")

            params = {"organization_id": active_org}
            headers = {"Authorization": f"Zoho-oauthtoken {active_token}"}
            response = await self.client.get(f"{self.base_url}/items", headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Inventory items: {e}")
            return []

    async def check_stock(self, item_id: str, token: Optional[str] = None, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Check current stock levels for an item"""
        try:
            active_token = token or self.access_token
            active_org = organization_id or self.organization_id

            if not active_token:
                 raise HTTPException(status_code=401, detail="Not authenticated")
            if not active_org:
                 raise HTTPException(status_code=400, detail="Organization ID required")

            params = {"organization_id": active_org}
            headers = {"Authorization": f"Zoho-oauthtoken {active_token}"}
            response = await self.client.get(f"{self.base_url}/items/{item_id}", headers=headers, params=params)
            response.raise_for_status()
            item = response.json().get("item", {})
            return {
                "item_id": item_id,
                "name": item.get("name"),
                "stock_on_hand": item.get("stock_on_hand", 0),
                "available_stock": item.get("available_stock", 0)
            }
        except Exception as e:
            logger.error(f"Failed to check stock for {item_id}: {e}")
            return {"error": str(e)}

    async def get_inventory_levels(self, token: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch inventory levels for all active items"""
        try:
            items = await self.get_items(token, organization_id)
            inventory = []
            for item in items:
                inventory.append({
                    "sku": item.get("sku"),
                    "name": item.get("name"),
                    "available": item.get("stock_on_hand", 0),
                    "platform": "zoho"
                })
            return inventory
        except Exception as e:
            logger.error(f"Failed to get Zoho inventory levels: {e}")
            return []

    async def sync_to_postgres_cache(self, user_id: str, access_token: str, organization_id: str) -> Dict[str, Any]:
        """Sync Zoho Inventory analytics to PostgreSQL IntegrationMetric table."""
        try:
            from core.database import SessionLocal
            from core.models import IntegrationMetric
            
            # Fetch Items to get total count
            items = await self.get_items(access_token, organization_id)
            item_count = len(items)
            
            db = SessionLocal()
            metrics_synced = 0
            try:
                metrics_to_save = [
                    ("zoho_inventory_item_count", item_count, "count"),
                ]
                
                for key, value, unit in metrics_to_save:
                    existing = db.query(IntegrationMetric).filter_by(
                        workspace_id=user_id,
                        integration_type="zoho_inventory",
                        metric_key=key
                    ).first()
                    
                    if existing:
                        existing.value = float(value)
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        metric = IntegrationMetric(
                            workspace_id=user_id,
                            integration_type="zoho_inventory",
                            metric_key=key,
                            value=float(value),
                            unit=unit
                        )
                        db.add(metric)
                    metrics_synced += 1
                
                db.commit()
                logger.info(f"Synced {metrics_synced} Zoho Inventory metrics to PostgreSQL cache for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving Zoho Inventory metrics to Postgres: {e}")
                db.rollback()
                return {"success": False, "error": str(e)}
            finally:
                db.close()
                
            return {"success": True, "metrics_synced": metrics_synced}
        except Exception as e:
            logger.error(f"Zoho Inventory PostgreSQL cache sync failed: {e}")
            return {"success": False, "error": str(e)}

    async def full_sync(self, user_id: str, access_token: str, organization_id: str) -> Dict[str, Any]:
        """Trigger full dual-pipeline sync for Zoho Inventory"""
        # Pipeline 1: Atom Memory
        # Triggered via zoho_inventory_memory_ingestion or similar
        
        # Pipeline 2: Postgres Cache
        cache_result = await self.sync_to_postgres_cache(user_id, access_token, organization_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "postgres_cache": cache_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }



def get_zoho_inventory_service(config: Dict[str, Any]) -> ZohoInventoryService:
    return ZohoInventoryService(tenant_id, config)

zoho_inventory_service = ZohoInventoryService(tenant_id="default", config={})
