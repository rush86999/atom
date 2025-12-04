import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .shopify_service import ShopifyService

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/shopify", tags=["shopify"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Shopify OAuth URL"""
    return {
        "url": "https://{shop}.myshopify.com/admin/oauth/authorize?client_id=INSERT_CLIENT_ID&scope=read_products,read_orders&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fshopify%2Fcallback",
        "timestamp": datetime.now().isoformat()
    }

# Initialize service
shopify_service = ShopifyService()

class ShopifyAuthRequest(BaseModel):
    code: str
    shop: str

@router.post("/auth/callback")
async def shopify_auth_callback(auth_request: ShopifyAuthRequest):
    """Exchange authorization code for access token"""
    try:
        token_data = await shopify_service.exchange_token(auth_request.code, auth_request.shop)
        return {
            "ok": True,
            "access_token": token_data["access_token"],
            "scope": token_data.get("scope"),
            "service": "shopify"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/shop")
async def get_shop_info(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain (e.g. my-shop.myshopify.com)")
):
    """Get shop information"""
    info = await shopify_service.get_shop_info(access_token, shop)
    return {"ok": True, "data": info}

@router.get("/products")
async def list_products(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Shopify products"""
    products = await shopify_service.get_products(access_token, shop, limit)
    return {"ok": True, "data": products, "count": len(products)}

@router.get("/orders")
async def list_orders(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Shopify orders"""
    orders = await shopify_service.get_orders(access_token, shop, limit)
    return {"ok": True, "data": orders, "count": len(orders)}

@router.get("/status")
async def shopify_status():
    """Get Shopify integration status"""
    return {
        "ok": True,
        "service": "shopify",
        "status": "active",
        "version": "1.0.0",
        "mode": "real"
    }

@router.get("/")
async def shopify_root():
    """Shopify integration root endpoint"""
    return {
        "service": "shopify",
        "status": "active",
        "endpoints": [
            "/auth/callback",
            "/shop",
            "/products",
            "/orders",
            "/status"
        ]
    }
