"""
Communication Webhooks - Receive and process incoming events from messaging platforms.
"""

import json
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Header, Request, BackgroundTasks, Query
from core.communication_service import communication_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

@router.post("/slack")
async def slack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_slack_signature: str = Header(None),
    x_slack_request_timestamp: str = Header(None)
):
    """
    Handle Slack Events and Interactivity (Button Clicks).
    """
    body = await request.body()
    form_data = await request.form()
    adapter = communication_service.get_adapter("slack")

    # 1. Handle Interactivity (Button Clicks)
    if "payload" in form_data:
        payload = json.loads(form_data["payload"])
        logger.info(f"Received Slack interactivity payload: {payload.get('type')}")
        
        normalized = adapter.normalize_payload(payload)
        if not normalized:
            return {"status": "ignored"}
            
        # Dispatch to CommunicationService
        return await communication_service.handle_incoming_message(
            source="slack",
            payload=normalized,
            background_tasks=background_tasks
        )

    # 2. Handle Events (Message mentions, etc.)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}

    # Slack URL Verification (Challenge)
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # Verify Signature
    if not await adapter.verify_request(request, body):
        logger.warning("Slack signature verification failed")
        return {"status": "error", "message": "Signature mismatch"}

    logger.info(f"Received Slack event: {data.get('type')}")
    
    normalized = adapter.normalize_payload(data)
    if not normalized:
        return {"status": "ignored"}

    return await communication_service.handle_incoming_message(
        source="slack",
        payload=normalized,
        background_tasks=background_tasks
    )

@router.post("/discord")
async def discord_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature_ed25519: str = Header(None),
    x_signature_timestamp: str = Header(None)
):
    """
    Handle Discord Interactions (Buttons, Commands).
    """
    body = await request.body()
    adapter = communication_service.get_adapter("discord")
    
    # 1. Verify Signature
    if not await adapter.verify_request(request, body):
        logger.warning("Discord signature verification failed")
        return {"status": "error", "message": "Signature mismatch"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}

    logger.info(f"Received Discord interaction: {data.get('type')}")
    
    normalized = adapter.normalize_payload(data)
    if not normalized:
        return {"status": "ignored"}
        
    # Support Discord PING/PONG challenge in normalization
    if normalized.get("type") == "challenge":
        return normalized.get("response")

    return await communication_service.handle_incoming_message(
        source="discord",
        payload=normalized,
        background_tasks=background_tasks
    )

@router.get("/whatsapp")
async def whatsapp_verify(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """Handle Meta/WhatsApp Webhook Verification (Handshake)"""
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("WhatsApp webhook verified successfully")
        return int(hub_challenge)
    
    logger.warning("WhatsApp webhook verification failed")
    return {"status": "error", "message": "Verification failed"}

@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None)
):
    """Handle WhatsApp Message Events and Interactivity"""
    body = await request.body()
    
    # 1. Verify Signature
    adapter = communication_service.get_adapter("whatsapp")
    if not await adapter.verify_request(request, body):
        logger.warning("WhatsApp signature verification failed")
        return {"status": "error", "message": "Signature mismatch"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}

    logger.info("Received WhatsApp webhook event")
    
    normalized = adapter.normalize_payload(data)
    if not normalized:
        return {"status": "ignored"}
        
    return await communication_service.handle_incoming_message(
        source="whatsapp",
        payload=normalized,
        background_tasks=background_tasks
    )

@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """Handle Telegram Message Events"""
    body = await request.body()
    adapter = communication_service.get_adapter("telegram")
    
    # 1. Verify Signature
    if not await adapter.verify_request(request, body):
        logger.warning("Telegram verification failed")
        return {"status": "error", "message": "Verification failed"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}

    logger.info("Received Telegram webhook event")
    
    normalized = await adapter.normalize_payload(request, body)
    if not normalized:
        return {"status": "ignored"}
    
    return await communication_service.handle_incoming_message(
        source="telegram",
        payload=normalized,
        background_tasks=background_tasks
    )

@router.post("/teams")
async def teams_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(None)
):
    """Handle Microsoft Teams Interactions"""
    body = await request.body()
    adapter = communication_service.get_adapter("teams")
    
    # 1. Verify Signature
    if not await adapter.verify_request(request, body):
        logger.warning("Teams verification failed")
        return {"status": "error", "message": "Verification failed"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}

    logger.info("Received Teams webhook event")
    
    normalized = await adapter.normalize_payload(request, body)
    if not normalized:
        return {"status": "ignored"}
        
    return await communication_service.handle_incoming_message(
        source="teams",
        payload=normalized,
        background_tasks=background_tasks
    )

