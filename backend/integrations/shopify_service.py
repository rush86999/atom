
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

    # ==================== FULL BUSINESS LIFECYCLE ====================

    # --- CUSTOMERS ---
    async def get_customers(self, access_token: str, shop: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of customers"""
        try:
            url = f"{self._get_base_url(shop)}/customers.json"
            headers = self._get_headers(access_token)
            params = {"limit": limit}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json().get("customers", [])
        except Exception as e:
            logger.error(f"Failed to get customers: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch customers: {str(e)}")

    async def get_customer(self, access_token: str, shop: str, customer_id: str) -> Dict[str, Any]:
        """Get a specific customer by ID"""
        try:
            url = f"{self._get_base_url(shop)}/customers/{customer_id}.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("customer", {})
        except Exception as e:
            logger.error(f"Failed to get customer {customer_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch customer: {str(e)}")

    async def search_customers(self, access_token: str, shop: str, query: str) -> List[Dict[str, Any]]:
        """Search customers by email, name, etc."""
        try:
            url = f"{self._get_base_url(shop)}/customers/search.json"
            headers = self._get_headers(access_token)
            params = {"query": query}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json().get("customers", [])
        except Exception as e:
            logger.error(f"Failed to search customers: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to search customers: {str(e)}")

    # --- FULFILLMENTS ---
    async def get_fulfillments(self, access_token: str, shop: str, order_id: str) -> List[Dict[str, Any]]:
        """Get fulfillments for an order"""
        try:
            url = f"{self._get_base_url(shop)}/orders/{order_id}/fulfillments.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("fulfillments", [])
        except Exception as e:
            logger.error(f"Failed to get fulfillments: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch fulfillments: {str(e)}")

    async def create_fulfillment(self, access_token: str, shop: str, order_id: str, 
                                  location_id: str, tracking_number: Optional[str] = None,
                                  tracking_company: Optional[str] = None) -> Dict[str, Any]:
        """Create a fulfillment for an order"""
        try:
            url = f"{self._get_base_url(shop)}/orders/{order_id}/fulfillments.json"
            headers = self._get_headers(access_token)
            
            fulfillment_data = {
                "fulfillment": {
                    "location_id": location_id,
                    "notify_customer": True
                }
            }
            
            if tracking_number:
                fulfillment_data["fulfillment"]["tracking_number"] = tracking_number
            if tracking_company:
                fulfillment_data["fulfillment"]["tracking_company"] = tracking_company
            
            response = await self.client.post(url, headers=headers, json=fulfillment_data)
            response.raise_for_status()
            
            return response.json().get("fulfillment", {})
        except Exception as e:
            logger.error(f"Failed to create fulfillment: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create fulfillment: {str(e)}")

    # --- REFUNDS ---
    async def get_refunds(self, access_token: str, shop: str, order_id: str) -> List[Dict[str, Any]]:
        """Get refunds for an order"""
        try:
            url = f"{self._get_base_url(shop)}/orders/{order_id}/refunds.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("refunds", [])
        except Exception as e:
            logger.error(f"Failed to get refunds: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch refunds: {str(e)}")

    async def calculate_refund(self, access_token: str, shop: str, order_id: str, 
                                line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate refund amount for specified line items"""
        try:
            url = f"{self._get_base_url(shop)}/orders/{order_id}/refunds/calculate.json"
            headers = self._get_headers(access_token)
            
            data = {
                "refund": {
                    "refund_line_items": line_items
                }
            }
            
            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            return response.json().get("refund", {})
        except Exception as e:
            logger.error(f"Failed to calculate refund: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to calculate refund: {str(e)}")

    # --- DRAFT ORDERS ---
    async def get_draft_orders(self, access_token: str, shop: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of draft orders"""
        try:
            url = f"{self._get_base_url(shop)}/draft_orders.json"
            headers = self._get_headers(access_token)
            params = {"limit": limit}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json().get("draft_orders", [])
        except Exception as e:
            logger.error(f"Failed to get draft orders: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch draft orders: {str(e)}")

    async def create_draft_order(self, access_token: str, shop: str, 
                                  line_items: List[Dict[str, Any]], 
                                  customer_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new draft order"""
        try:
            url = f"{self._get_base_url(shop)}/draft_orders.json"
            headers = self._get_headers(access_token)
            
            draft_data = {
                "draft_order": {
                    "line_items": line_items
                }
            }
            
            if customer_id:
                draft_data["draft_order"]["customer"] = {"id": customer_id}
            
            response = await self.client.post(url, headers=headers, json=draft_data)
            response.raise_for_status()
            
            return response.json().get("draft_order", {})
        except Exception as e:
            logger.error(f"Failed to create draft order: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create draft order: {str(e)}")

    async def complete_draft_order(self, access_token: str, shop: str, draft_order_id: str) -> Dict[str, Any]:
        """Convert draft order to a real order"""
        try:
            url = f"{self._get_base_url(shop)}/draft_orders/{draft_order_id}/complete.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.put(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("draft_order", {})
        except Exception as e:
            logger.error(f"Failed to complete draft order: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to complete draft order: {str(e)}")

    # --- TRANSACTIONS ---
    async def get_transactions(self, access_token: str, shop: str, order_id: str) -> List[Dict[str, Any]]:
        """Get transactions for an order"""
        try:
            url = f"{self._get_base_url(shop)}/orders/{order_id}/transactions.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("transactions", [])
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")

    # --- ANALYTICS & REPORTS ---
    async def get_order_count(self, access_token: str, shop: str, status: str = "any") -> int:
        """Get total order count"""
        try:
            url = f"{self._get_base_url(shop)}/orders/count.json"
            headers = self._get_headers(access_token)
            params = {"status": status}
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json().get("count", 0)
        except Exception as e:
            logger.error(f"Failed to get order count: {e}")
            return 0

    async def get_product_count(self, access_token: str, shop: str) -> int:
        """Get total product count"""
        try:
            url = f"{self._get_base_url(shop)}/products/count.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("count", 0)
        except Exception as e:
            logger.error(f"Failed to get product count: {e}")
            return 0

    async def get_customer_count(self, access_token: str, shop: str) -> int:
        """Get total customer count"""
        try:
            url = f"{self._get_base_url(shop)}/customers/count.json"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("count", 0)
        except Exception as e:
            logger.error(f"Failed to get customer count: {e}")
            return 0

    async def get_shop_analytics(self, access_token: str, shop: str) -> Dict[str, Any]:
        """Get comprehensive shop analytics summary"""
        try:
            order_count = await self.get_order_count(access_token, shop)
            product_count = await self.get_product_count(access_token, shop)
            customer_count = await self.get_customer_count(access_token, shop)
            shop_info = await self.get_shop_info(access_token, shop)
            
            return {
                "shop_name": shop_info.get("name", shop),
                "shop_domain": shop_info.get("domain", shop),
                "currency": shop_info.get("currency", "USD"),
                "metrics": {
                    "total_orders": order_count,
                    "total_products": product_count,
                    "total_customers": customer_count
                },
                "plan": shop_info.get("plan_name", "unknown"),
                "created_at": shop_info.get("created_at")
            }
        except Exception as e:
            logger.error(f"Failed to get shop analytics: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")
