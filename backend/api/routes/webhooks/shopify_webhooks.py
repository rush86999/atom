import hashlib
import hmac
import logging
import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from core.integration_registry import IntegrationRegistry
from api.routes.webhooks.base import get_webhook_registry, verify_hmac_signature
from api.routes.webhooks.webhook_bridge import webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shopify", tags=["Shopify Webhooks"])

# Per-tenant Shopify webhook secret. In a multi-tenant deployment this should be
# looked up from the integration config in the DB; the env var is the fallback.
def _shopify_secret() -> Optional[str]:
    return os.getenv("SHOPIFY_WEBHOOK_SECRET") or os.getenv("SHOPIFY_API_SECRET")


@router.post("")
async def shopify_webhook(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None),
    registry: IntegrationRegistry = Depends(get_webhook_registry),
):
    """
    Unified Shopify webhook handler.
    Determines the workspace (tenant) from headers and executes standard
    processing logic via the ShopifyService.

    Security: HMAC-SHA256 signature is mandatory. Requests without a valid
    signature are rejected (fail closed).
    """
    # Fail closed: signature header must be present
    if not x_shopify_hmac_sha256:
        raise HTTPException(status_code=401, detail="Missing Shopify webhook signature")

    # Raw body is required for HMAC verification — read before JSON decode.
    data = await request.body()

    # Resolve secret (env fallback; a real deployment resolves per-tenant)
    secret = _shopify_secret()
    if not secret:
        # No secret configured → fail closed. Do not process untrusted webhooks.
        raise HTTPException(status_code=503, detail="Shopify webhook verification not configured")

    # Verify HMAC-SHA256 using the shared helper (constant-time compare under the hood)
    if not verify_hmac_signature(data, x_shopify_hmac_sha256, secret, algorithm=hashlib.sha256):
        logger.error("Shopify webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")

    # Signature verified — safe to parse the body
    import json as _json
    try:
        payload = _json.loads(data)
    except Exception:
        logger.error("Shopify webhook body was not valid JSON")
        raise HTTPException(status_code=400, detail="Malformed webhook body")

    # 1. Tenant Resolution — domain header is only trusted AFTER signature verifies
    tenant_id = x_shopify_shop_domain or "default"

    # 2. Registry Execution
    result = await registry.execute_operation(
        "shopify",
        tenant_id,
        "handle_webhook_event",
        {
            "payload": payload,
            "topic": request.headers.get("x-shopify-topic"),
        },
    )

    return result
