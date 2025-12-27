
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ShopifyService:
    """Shopify API Service Implementation"""
    
    def __init__(self):
        self.api_key = os.getenv("SHOPIFY_API_KEY")
        self.api_secret = os.getenv("SHOPIFY_API_SECRET")
        self.shop_name = os.getenv("SHOPIFY_SHOP_NAME") # Default shop name if available
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_base_url(self, shop: str) -> str:
        # Shop should be "my-shop.myshopify.com"
        if not shop.endswith(".myshopify.com"):
            shop = f"{shop}.myshopify.com"
        return f"https://{shop}/admin/api/2023-10"

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        return {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }

    async def exchange_token(self, code: str, shop: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            url = f"https://{shop}/admin/oauth/access_token"
            
            data = {
                "client_id": self.api_key,
                "client_secret": self.api_secret,
                "code": code
            }
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Shopify token exchange failed: {e}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

    async def get_products(self, access_token: str, shop: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of products"""
        try:
            url = f"{self._get_base_url(shop)}/products.json"
            headers = self._get_headers(access_token)
            params = {"limit": limit}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("products", [])
        except Exception as e:
            logger.error(f"Failed to get products: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch products: {str(e)}")

    async def get_orders(self, access_token: str, shop: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of orders"""
        try:
            url = f"{self._get_base_url(shop)}/orders.json"
            headers = self._get_headers(access_token)
            params = {"limit": limit, "status": "any"}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("orders", [])
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(e)}")

    async def get_shop_info(self, access_token: str, shop: str) -> Dict[str, Any]:
        """Get shop information"""
        try:
            url = f"{self._get_base_url(shop)}/shop.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get("shop", {})
        except Exception as e:
            logger.error(f"Failed to get shop info: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch shop info: {str(e)}")

    async def register_webhooks(self, access_token: str, shop: str, webhook_url: str) -> List[Dict[str, Any]]:
        """Register required webhooks for Phase 13 automation"""
        topics = ["orders/create", "orders/updated", "refunds/create"]
        results = []
        
        for topic in topics:
            try:
                url = f"{self._get_base_url(shop)}/webhooks.json"
                headers = self._get_headers(access_token)
                
                data = {
                    "webhook": {
                        "topic": topic,
                        "address": f"{webhook_url}/{topic.replace('/', '-')}",
                        "format": "json"
                    }
                }
                
                response = await self.client.post(url, headers=headers, json=data)
                # Shopify returns 422 if webhook already exists
                if response.status_code == 422:
                    logger.info(f"Webhook for topic {topic} already exists for shop {shop}")
                    results.append({"topic": topic, "status": "already_exists"})
                else:
                    response.raise_for_status()
                    results.append({"topic": topic, "status": "registered", "data": response.json()})
                    
            except Exception as e:
                logger.error(f"Failed to register webhook {topic}: {e}")
                results.append({"topic": topic, "status": "failed", "error": str(e)})
                
        return results

    async def get_inventory_levels(self, access_token: str, shop: str, location_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get inventory levels for shop"""
        try:
            url = f"{self._get_base_url(shop)}/inventory_levels.json"
            headers = self._get_headers(access_token)
            params = {}
            if location_id:
                params["location_ids"] = location_id
                
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json().get("inventory_levels", [])
        except Exception as e:
            logger.error(f"Failed to get inventory levels: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch inventory: {str(e)}")

    async def get_locations(self, access_token: str, shop: str) -> List[Dict[str, Any]]:
        """Get shop locations"""
        try:
            url = f"{self._get_base_url(shop)}/locations.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("locations", [])
        except Exception as e:
            logger.error(f"Failed to get locations: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch locations: {str(e)}")
