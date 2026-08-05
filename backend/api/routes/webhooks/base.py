from typing import Dict, Any, List, Optional, Callable
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Header, Request
from core.integration_registry import IntegrationRegistry
from core.database import get_db
from sqlalchemy.orm import Session
import hmac
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)

def get_webhook_registry(db: Session = Depends(get_db)) -> IntegrationRegistry:
    """Dependency for obtaining the IntegrationRegistry for webhook processing."""
    return IntegrationRegistry(db)

def verify_hmac_signature(data: bytes, signature: str, secret: str, algorithm=hashlib.sha256) -> bool:
    """Utility to verify HMAC signatures for incoming webhooks."""
    if not secret or not signature:
        return False
        
    digest = hmac.new(secret.encode('utf-8'), data, algorithm).digest()
    
    # BUG-087: The old heuristic (`len(signature) > 64` → base64) was inverted
    # for Shopify: Shopify sends base64-encoded HMAC-SHA256 (44 chars), which
    # the heuristic classified as hex → always mismatched → rejected every
    # legitimate Shopify webhook. Now tries BOTH encodings and accepts if
    # either matches.
    try:
        hex_sig = hmac.new(secret.encode('utf-8'), data, algorithm).hexdigest()
        b64_sig = base64.b64encode(digest).decode('utf-8')

        return hmac.compare_digest(hex_sig, signature) or hmac.compare_digest(b64_sig, signature)
    except Exception as e:
        logger.error(f"HMAC verification failed: {e}")
        return False

# Re-exporting for standard route usage
__all__ = ["get_webhook_registry", "verify_hmac_signature"]
