import os
import hmac
import hashlib
import json
import base64
from datetime import datetime
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.messaging_action_dispatcher import MessagingActionDispatcher, RateLimiter

logger = logging.getLogger(__name__)

# Teams Actions Dispatcher and Sentinel Rate Limiter
teams_dispatcher = MessagingActionDispatcher(platform="teams")
teams_rate_limiter = RateLimiter(limit=30, window=60)
TEAMS_WEBHOOK_SECRET = os.getenv("TEAMS_WEBHOOK_SECRET", "")

# Auth Type: OAuth2
router = APIRouter(prefix="/api/teams", tags=["teams"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Teams OAuth URL"""
    return {
        "url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=INSERT_CLIENT_ID&response_type=code&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fteams%2Fcallback&response_mode=query&scope=User.Read%20Team.ReadBasic.All",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(code: str):
    """Handle Teams OAuth callback"""
    return {
        "ok": True,
        "status": "success",
        "code": code,
        "message": "Teams authentication received",
        "timestamp": datetime.now().isoformat()
    }

class TeamsSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class TeamsSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

@router.get("/status")
async def teams_status(user_id: str = "test_user"):
    """Get Teams integration status"""
    return {
        "ok": True,
        "service": "teams",
        "user_id": user_id,
        "status": "connected",
        "message": "Teams integration is available",
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/search")
async def teams_search(request: TeamsSearchRequest):
    """Search Teams content"""
    logger.info(f"Searching Teams for: {request.query}")

    sample_results = [
        {
            "id": "item_001",
            "title": f"Teams Result - {request.query}",
            "type": "item",
            "snippet": f"Result for query: {request.query}",
        }
    ]

    return TeamsSearchResponse(
        ok=True,
        query=request.query,
        results=sample_results,
        timestamp=datetime.now().isoformat(),
    )


def verify_teams_signature(raw_body: bytes, auth_header: str) -> bool:
    """Verify Teams Outbound Webhook HMAC signature."""
    if not TEAMS_WEBHOOK_SECRET or not auth_header.startswith("HMAC "):
        return False
    
    try:
        signature = auth_header[5:]  # Remove 'HMAC '
        
        expected_mac = hmac.new(
            base64.b64decode(TEAMS_WEBHOOK_SECRET),
            raw_body,
            hashlib.sha256
        ).digest()
        
        expected_sig = base64.b64encode(expected_mac).decode()
        return hmac.compare_digest(expected_sig, signature)
    except Exception:
        return False


@router.post("/webhook")
async def teams_webhook(request: Request):
    """
    Handle Microsoft Teams outgoing webhooks & adaptive cards.
    Doc: https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-outgoing-webhook
    """
    client_ip = request.client.host if request.client else "unknown"
    if not teams_rate_limiter.check(client_ip):
        logger.warning(f"Teams interactive rate limit exceeded for IP {client_ip}")
        raise HTTPException(status_code=429, detail="Too many requests")

    raw_body = await request.body()
    auth_header = request.headers.get("Authorization", "")

    if not verify_teams_signature(raw_body, auth_header):
        logger.warning(f"Teams signature verification failed for IP {client_ip}")
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Adaptive Card Submit Action
    if "value" in payload and isinstance(payload["value"], dict):
        action_value = payload["value"]
        action_id = action_value.get("action_id", "")
        if action_id:
            user_info = {"id": payload.get("from", {}).get("id", "unknown")}
            # Dispatch to interactive agent handler securely 
            teams_dispatcher.dispatch(action_id, payload, user_info)

    return {"type": "message", "text": ""}
