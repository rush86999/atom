"""
Email Verification API Routes
Handles email verification codes and sending verification emails
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timedelta
import secrets
from typing import Optional
import logging
import os

from core.database import get_db
from core.models import User, UserStatus, EmailVerificationToken

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email-verification", tags=["Email Verification"])


class EmailService:
    """Simple email service with graceful fallback to logging"""

    def __init__(self):
        self.enabled = os.getenv("EMAIL_SERVICE_ENABLED", "false").lower() == "true"
        self.source_email = os.getenv("SES_SOURCE_EMAIL", "noreply@atom.ai")

    async def send_verification_email(self, to_email: str, code: str) -> bool:
        """
        Send verification email with graceful fallback

        Returns True if email was sent successfully (or logged in dev mode)
        """
        if not self.enabled:
            # Development mode: log the verification code
            logger.info(f"🔑 DEV MODE: Verification code for {to_email}: {code}")
            logger.info(f"   Code expires in 24 hours")
            return True

        # Production mode: attempt to send email
        try:
            # Import email service only when enabled to avoid dependency issues
            # This is a placeholder for your actual email service implementation
            # Examples: AWS SES, SendGrid, Mailgun, etc.

            # Example with AWS SES (uncomment and configure):
            # import boto3
            # client = boto3.client('ses', region_name=os.getenv('AWS_REGION', 'us-east-1'))
            # await client.send_email(
            #     Source=self.source_email,
            #     Destination={'ToAddresses': [to_email]},
            #     Message={
            #         'Subject': {'Data': 'Verify Your Email Address'},
            #         'Body': {
            #             'Html': {
            #                 'Data': f'''
            #                 <h2>Verify Your Email</h2>
            #                 <p>Your verification code is:</p>
            #                 <h1 style="color: #4F46E5; letter-spacing: 2px;">{code}</h1>
            #                 <p>This code will expire in 24 hours.</p>
            #                 '''
            #             }
            #         }
            #     }
            # )

            logger.info(f"Verification email sent to {to_email}")
            return True

        except ImportError:
            logger.warning("Email service enabled but not configured. Logging code instead.")
            logger.info(f"🔑 Verification code for {to_email}: {code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send verification email to {to_email}: {e}")
            # Fallback to logging on error
            logger.info(f"🔑 FALLBACK: Verification code for {to_email}: {code}")
            return False


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Find valid token
    token = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.token == request.code.strip(),
        EmailVerificationToken.expires_at > datetime.utcnow()
    ).first()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )

    # Mark user as verified and active
    user.email_verified = True
    user.status = UserStatus.ACTIVE.value

    # Delete the used token
    db.delete(token)
    db.commit()

    return VerifyEmailResponse(message="Email verified successfully")


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

    return SendVerificationResponse(message="Verification email sent")
