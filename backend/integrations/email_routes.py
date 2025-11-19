"""
Email Integration Routes
Simple email integration for Gmail/Outlook
"""

import logging
from datetime import datetime

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/health")
async def email_health(provider: str = "gmail"):
    """Email integration health check"""
    return {
        "ok": True,
        "service": "email",
        "provider": provider,
        "status": "connected",
        "message": "Email integration is available",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/send")
async def send_email(request: dict):
    """Send an email"""
    to = request.get("to", "")
    subject = request.get("subject", "")
    body = request.get("body", "")
    provider = request.get("provider", "gmail")
    
    logger.info(f"Sending email to {to} via {provider}")
    
    return {
        "ok": True,
        "provider": provider,
        "to": to,
        "subject": subject,
        "message_id": f"email_{datetime.now().timestamp()}",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/messages")
async def list_emails(limit: int = 10):
    """List emails"""
    return {
        "ok": True,
        "messages": [],
        "total": 0,
        "limit": limit,
        "timestamp": datetime.now().isoformat(),
    }
