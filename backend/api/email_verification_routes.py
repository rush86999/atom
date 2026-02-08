"""
Email Verification API Routes
Handles email verification codes and sending verification emails via Mailgun
"""
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import logging
import os
import secrets
from typing import Dict, Optional
from fastapi import Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import EmailVerificationToken, User, UserStatus

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/email-verification", tags=["Email Verification"])

# Rate limiting: Track email sending per user (in-memory for simplicity)
# For production, use Redis or similar
_email_rate_tracker: Dict[str, list] = {}
_RATE_LIMIT_MAX = 3  # Max emails per hour
_RATE_LIMIT_WINDOW = timedelta(hours=1)


class EmailService:
    """Email service using Mailgun with graceful fallback to logging"""

    def __init__(self):
        self.enabled = os.getenv("EMAIL_SERVICE_ENABLED", "false").lower() == "true"
        self.provider = os.getenv("EMAIL_PROVIDER", "mailgun").lower()
        self.mailgun_api_key = os.getenv("MAILGUN_API_KEY", "")
        self.mailgun_domain = os.getenv("MAILGUN_DOMAIN", "")
        self.source_email = os.getenv("SOURCE_EMAIL", "noreply@atom.ai")

        # Validate Mailgun configuration if enabled
        if self.enabled and self.provider == "mailgun":
            if not self.mailgun_api_key:
                logger.warning("EMAIL_SERVICE_ENABLED=true but MAILGUN_API_KEY not set")
                self.enabled = False
            if not self.mailgun_domain:
                logger.warning("EMAIL_SERVICE_ENABLED=true but MAILGUN_DOMAIN not set")
                self.enabled = False

        logger.info(f"EmailService initialized: enabled={self.enabled}, provider={self.provider}")

    def _check_rate_limit(self, email: str) -> tuple[bool, str]:
        """
        Check if user has exceeded rate limit for email sending

        Returns: (allowed, reason)
        """
        now = datetime.utcnow()

        # Clean up old entries outside the rate limit window
        if email in _email_rate_tracker:
            _email_rate_tracker[email] = [
                timestamp for timestamp in _email_rate_tracker[email]
                if now - timestamp < _RATE_LIMIT_WINDOW
            ]

        # Check if limit exceeded
        if email in _email_rate_tracker and len(_email_rate_tracker[email]) >= _RATE_LIMIT_MAX:
            return False, f"Rate limit exceeded: max {_RATE_LIMIT_MAX} emails per {_RATE_LIMIT_WINDOW.total_seconds() / 3600:.0f} hours"

        return True, ""

    def _record_email_sent(self, email: str):
        """Record that an email was sent to this user"""
        if email not in _email_rate_tracker:
            _email_rate_tracker[email] = []
        _email_rate_tracker[email].append(datetime.utcnow())

    async def send_verification_email(self, to_email: str, code: str) -> bool:
        """
        Send verification email with graceful fallback

        Returns True if email was sent successfully (or logged in dev mode)
        """
        # Check rate limit
        allowed, reason = self._check_rate_limit(to_email)
        if not allowed:
            logger.warning(f"Rate limit exceeded for {to_email}: {reason}")
            # Still allow in dev mode, but log warning
            if not self.enabled:
                logger.warning(f"🔑 DEV MODE (rate limit bypassed): Verification code for {to_email}: {code}")
                return True
            raise router.rate_limit_error()

        if not self.enabled:
            # Development mode: log the verification code
            logger.info(f"🔑 DEV MODE: Verification code for {to_email}: {code}")
            logger.info(f"   Code expires in 24 hours")
            return True

        # Production mode: attempt to send email
        try:
            if self.provider == "mailgun":
                success = await self._send_via_mailgun(to_email, code)
            else:
                logger.error(f"Unsupported email provider: {self.provider}")
                success = False

            if success:
                self._record_email_sent(to_email)
                logger.info(f"Verification email sent to {to_email} via {self.provider}")
                return True
            else:
                # Fallback to logging on failure
                logger.warning(f"Email sending failed, falling back to logging for {to_email}")
                logger.info(f"🔑 FALLBACK: Verification code for {to_email}: {code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send verification email to {to_email}: {e}", exc_info=True)
            # Fallback to logging on error
            logger.info(f"🔑 FALLBACK: Verification code for {to_email}: {code}")
            return False

    async def _send_via_mailgun(self, to_email: str, code: str) -> bool:
        """
        Send email via Mailgun API

        Returns True if successful, False otherwise
        """
        try:
            import aiohttp

            # Mailgun API endpoint
            url = f"https://api.mailgun.net/v3/{self.mailgun_domain}/messages"

            # Prepare email data
            data = {
                "from": f"Atom <{self.source_email}>",
                "to": [to_email],
                "subject": "Verify Your Email Address",
                "html": self._get_email_html(code),
                "text": self._get_email_text(code)
            }

            # Send via Mailgun API
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth("api", self.mailgun_api_key)
                async with session.post(url, data=data, auth=auth) as response:
                    if response.status in (200, 201):
                        result = await response.json()
                        logger.debug(f"Mailgun response: {result}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Mailgun API error (status {response.status}): {error_text}")
                        return False

        except ImportError:
            logger.error("aiohttp not installed, cannot send email via Mailgun")
            return False
        except Exception as e:
            logger.error(f"Mailgun API call failed: {e}", exc_info=True)
            return False

    def _get_email_html(self, code: str) -> str:
        """Generate HTML email body"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600;">Verify Your Email</h1>
                </div>
                <div style="padding: 40px 30px;">
                    <p style="font-size: 16px; color: #555; margin-bottom: 20px;">Thank you for signing up for Atom! Please use the verification code below to complete your registration:</p>
                    <div style="background-color: #f8f9fa; border: 2px dashed #667eea; border-radius: 8px; padding: 20px; text-align: center; margin: 30px 0;">
                        <p style="font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 4px; margin: 0;">{code}</p>
                    </div>
                    <p style="font-size: 14px; color: #888; margin-top: 30px;">This code will expire in 24 hours.</p>
                    <p style="font-size: 14px; color: #888; margin-top: 10px;">If you didn't request this verification code, please ignore this email.</p>
                </div>
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #e9ecef;">
                    <p style="font-size: 12px; color: #999; margin: 0;">&copy; 2026 Atom. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_email_text(self, code: str) -> str:
        """Generate plain text email body"""
        return f"""
Verify Your Email Address

Thank you for signing up for Atom!

Your verification code is: {code}

This code will expire in 24 hours.

If you didn't request this verification code, please ignore this email.

© 2026 Atom. All rights reserved.
        """.strip()


# Global email service instance
email_service = EmailService()


# Request/Response Models
class VerifyEmailRequest(BaseModel):
    """Email verification request with code"""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class VerifyEmailResponse(BaseModel):
    """Response after successful verification"""
    message: str


class SendVerificationRequest(BaseModel):
    """Request to send verification email"""
    email: EmailStr


class SendVerificationResponse(BaseModel):
    """Response after sending verification email"""
    message: str


# Endpoints
@router.post("/verify", response_model=VerifyEmailResponse, status_code=status.HTTP_200_OK)
async def verify_email(
    request: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verify user email with 6-digit code

    Validates the verification code and activates the user account.
    Codes expire after 24 hours.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise router.not_found_error("User", request.email)

    # Find valid token
    token = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.token == request.code.strip(),
        EmailVerificationToken.expires_at > datetime.utcnow()
    ).first()

    if not token:
        raise router.validation_error(
            field="code",
            message="Invalid or expired verification code"
        )

    # Mark user as verified and active
    user.email_verified = True
    user.status = UserStatus.ACTIVE.value

    # Delete the used token
    db.delete(token)
    db.commit()

    return router.success_response(
        data={"verified": True},
        message="Email verified successfully"
    )


@router.post("/send", response_model=SendVerificationResponse)
async def send_verification_email(
    request: SendVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Send verification email to user

    Generates a 6-digit verification code and sends it via email.
    Invalid/expired codes are replaced with new ones.

    Note: Actual email sending implementation depends on your email service.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        # Return success to prevent email enumeration
        return SendVerificationResponse(
            message="If user exists, verification email sent"
        )

    # Generate 6-digit code
    code = secrets.token_hex(3)  # 6 characters
    expires_at = datetime.utcnow() + timedelta(hours=24)

    # Delete existing tokens for this user
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id
    ).delete()

    # Create new token
    token = EmailVerificationToken(
        user_id=user.id,
        token=code,
        expires_at=expires_at
    )
    db.add(token)
    db.commit()

    # Send verification email (with graceful fallback to logging)
    await email_service.send_verification_email(user.email, code)

    return router.success_response(
        message="Verification email sent"
    )
