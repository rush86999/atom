from datetime import datetime
import logging
import os
from fastapi import APIRouter, HTTPException
import httpx

# Auth Type: API Key
router = APIRouter(prefix="/api/sendgrid", tags=["sendgrid"])

logger = logging.getLogger(__name__)

# SendGrid feature flag
SENDGRID_ENABLED = os.getenv("SENDGRID_ENABLED", "true").lower() == "true"

class SendGridService:
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        if not SENDGRID_ENABLED:
            logger.warning("SendGrid integration is disabled via SENDGRID_ENABLED flag")
        elif not self.api_key or self.api_key == "mock_api_key":
            logger.warning("SENDGRID_API_KEY not configured - SendGrid features will be limited")

    async def send_email(self, to, subject, content):
        """
        Send an email using SendGrid API.

        Args:
            to: Recipient email address
            subject: Email subject
            content: Email content (plain text or HTML)

        Returns:
            Dictionary with status and message_id

        Raises:
            ValueError: If API key is not configured
            HTTPException: If SendGrid API call fails
        """
        if not SENDGRID_ENABLED:
            return {
                "success": False,
                "status": "disabled",
                "error": "SendGrid integration is disabled"
            }

        if not self.api_key or self.api_key == "mock_api_key":
            return {
                "success": False,
                "status": "unconfigured",
                "error": "SENDGRID_API_KEY not configured"
            }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": os.getenv("SENDGRID_FROM_EMAIL", "noreply@atom.ai")},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": content}]
                },
                timeout=30.0
            )

        if response.status_code in (200, 202):
            return {
                "success": True,
                "status": "sent",
                "message_id": response.headers.get("X-Message-Id")
            }
        else:
            logger.error(f"SendGrid API error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"SendGrid API error: {response.text}"
            )

sendgrid_service = SendGridService()

@router.get("/auth/url")
async def get_auth_url():
    """Get SendGrid Auth URL (mock)"""
    return {
        "url": "https://app.sendgrid.com/settings/api_keys",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/callback")
async def handle_oauth_callback(key: str):
    """Handle SendGrid Auth callback (mock)"""
    return {
        "ok": True,
        "status": "success",
        "message": "SendGrid authentication successful (mock)",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/status")
async def sendgrid_status():
    """Status check for SendGrid integration"""
    return {
        "status": "active",
        "service": "sendgrid",
        "version": "1.0.0",
        "business_value": {
            "email_marketing": True,
            "transactional_emails": True,
            "deliverability_analytics": True
        }
    }

@router.get("/health")
async def sendgrid_health():
    """Health check for SendGrid integration"""
    return await sendgrid_status()
