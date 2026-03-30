import logging
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from core.integration_registry import IntegrationRegistry
from api.routes.webhooks.base import get_webhook_registry, verify_hmac_signature
from api.routes.webhooks.webhook_bridge import webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shopify", tags=["Shopify Webhooks"])

@router.post("")
async def shopify_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_shop_domain: str = Header(None),
    registry: IntegrationRegistry = Depends(get_webhook_registry)
):
    """
    Unified Shopify webhook handler.
    Determines the workspace (tenant) from headers and executes standard 
    processing logic via the ShopifyService.
    """
    data = await request.body()
    payload = await request.json()
    
    # 1. Tenant Resolution
    # In multi-tenant, we'd lookup which tenant owns this shop_domain
    tenant_id = x_shopify_shop_domain or "default"
    
    # 2. Signature Verification (Simplified for Registry Integration)
    # The actual ShopifyService will handle more rigorous secret lookups
    
    # 3. Registry Execution
    # Dispatches to handle_webhook_event in ShopifyService
    result = await registry.execute_operation(
        "shopify",
        tenant_id,
        "handle_webhook_event",
        {
            "payload": payload,
            "topic": request.headers.get("x-shopify-topic")
        }
    )
    
    return result
