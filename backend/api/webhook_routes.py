"""
Webhook API Routes for Real-Time Communication Ingestion
Provides endpoints for Slack, Teams, and Gmail webhooks.
"""

import hmac
import logging
import os
from typing import Optional
from fastapi import BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from core.base_routes import BaseAPIRouter
from core.webhook_handlers import get_webhook_processor

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Get webhook processor
webhook_processor = get_webhook_processor()


def _require_webhook_secret(env_var: str):
    """Shared-secret dependency for external webhook endpoints.

    R69: these endpoints previously had no auth and handlers never called the
    (weak, dev-only) platform verifiers. Require a Bearer token compared in
    constant time against an env secret; FAIL CLOSED (401) when unset.
    """
    async def _check(authorization: Optional[str] = Header(None)):
        secret = os.getenv(env_var)
        if not secret:
            raise HTTPException(status_code=401, detail="Webhook not configured")
        token = (authorization or "").strip().removeprefix("Bearer ").strip()
        if not token or not hmac.compare_digest(token, secret):
            raise HTTPException(status_code=401, detail="Invalid webhook token")
    return _check


@router.post("/slack")
async def slack_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Receive Slack webhook events for real-time message processing.

    Slack sends events when:
    - New messages are posted
    - Messages are edited/deleted
    - Reactions are added/removed
    - Channels are created/archived

    Expected headers:
    - X-Slack-Request-Timestamp: Timestamp of request
    - X-Slack-Signature: HMAC signature for verification
    """
    result = await webhook_processor.process_slack_webhook(request, background_tasks)

    # Handle URL verification challenge
    if "challenge" in result:
        return JSONResponse(content={"challenge": result["challenge"]})

    return result


@router.post("/teams")
async def teams_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_require_webhook_secret("ATOM_TEAMS_WEBHOOK_SECRET")),
):
    """
    Receive Microsoft Teams webhook events for real-time message processing.

    Teams sends events when:
    - New chat messages are posted
    - Channel messages are posted
    - Message updates occur

    Note: This endpoint requires proper Microsoft Graph webhook subscription.
    """
    result = await webhook_processor.process_teams_webhook(request, background_tasks)
    return result


@router.post("/gmail")
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_require_webhook_secret("ATOM_GMAIL_WEBHOOK_SECRET")),
):
    """
    Receive Gmail push notifications for real-time email processing.

    Gmail sends push notifications when:
    - New emails arrive
    - Email labels change
    - Emails are deleted

    Note: This endpoint requires Google Cloud Pub/Sub subscription.
    """
    result = await webhook_processor.process_gmail_webhook(request, background_tasks)
    return result


@router.get("/health")
async def webhook_health():
    """Check webhook endpoint health"""
    return router.success_response(
        data={
            "status": "healthy",
            "webhooks": {
                "slack": "enabled",
                "teams": "enabled",
                "gmail": "enabled"
            },
            "processed_events": len(webhook_processor.processed_events)
        },
        message="Webhook endpoints are healthy"
    )
