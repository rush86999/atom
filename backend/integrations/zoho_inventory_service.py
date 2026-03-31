import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
from core.audit_logger import log_integration_call, log_integration_error, log_integration_attempt, log_integration_complete
from fastapi import HTTPException


logger = logging.getLogger(__name__)

class ZohoInventoryService:
    def __init__(self):
        self.base_url = "https://inventory.zoho.com/api/v1"
        self.access_token = os.getenv("ZOHO_INVENTORY_ACCESS_TOKEN")
        self.organization_id = os.getenv("ZOHO_ORG_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

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
        # Start audit logging
        audit_ctx = log_integration_attempt("zoho_inventory", "get_items", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("zoho_inventory"):
                logger.warning(f"Circuit breaker is open for zoho_inventory")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Zoho_inventory integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("zoho_inventory")
            if is_limited:
                logger.warning(f"Rate limit exceeded for zoho_inventory")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for zoho_inventory"
                )

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
        # Start audit logging
        audit_ctx = log_integration_attempt("zoho_inventory", "check_stock", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("zoho_inventory"):
                logger.warning(f"Circuit breaker is open for zoho_inventory")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Zoho_inventory integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("zoho_inventory")
            if is_limited:
                logger.warning(f"Rate limit exceeded for zoho_inventory")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for zoho_inventory"
                )

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

# Singleton instance
zoho_inventory_service = ZohoInventoryService()

        # Start audit logging
        audit_ctx = log_integration_attempt("zoho_inventory", "get_inventory_levels", locals())
        try:
            # Check circuit breaker
            if not await circuit_breaker.is_enabled("zoho_inventory"):
                logger.warning(f"Circuit breaker is open for zoho_inventory")
                log_integration_complete(audit_ctx, error=Exception("Circuit breaker open"))
                raise HTTPException(
                    status_code=503,
                    detail=f"Zoho_inventory integration temporarily disabled"
                )

            # Check rate limiter
            is_limited, remaining = await rate_limiter.is_rate_limited("zoho_inventory")
            if is_limited:
                logger.warning(f"Rate limit exceeded for zoho_inventory")
                log_integration_complete(audit_ctx, error=Exception("Rate limit exceeded"))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for zoho_inventory"
                )
