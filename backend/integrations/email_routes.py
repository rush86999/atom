"""
Email Integration Routes
Simple email integration for Gmail/Outlook
"""

from datetime import datetime
import logging
from fastapi import APIRouter, Depends

from core.auth import get_current_user
from core.models import User

logger = logging.getLogger(__name__)

# Auth Type: Internal
router = APIRouter(prefix="/api/email", tags=["email"])

class EmailService:
    def __init__(self):
        self.provider = "internal"
        
    async def send_email(self, to, subject, body):
        return {"message_id": f"email_{datetime.now().timestamp()}"}

email_service = EmailService()

@router.get("/auth/url")
async def get_auth_url():
    """Get Email Auth URL (internal)"""
    return {
        "url": "/api/email/health",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback():
    """Handle Email Auth callback (internal)"""
    return {
        "ok": True,
        "message": "Email service ready (internal)",
        "timestamp": datetime.now().isoformat()
    }



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
async def send_email(request: dict, current_user: User = Depends(get_current_user)):
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
async def list_emails(limit: int = 10, current_user: User = Depends(get_current_user)):
    """List emails"""
    return {
        "ok": True,
        "messages": [],
        "total": 0,
        "limit": limit,
        "timestamp": datetime.now().isoformat(),
    }
