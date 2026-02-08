import logging
from typing import List, Optional
from fastapi import Depends, Request
from pydantic import BaseModel
import pyotp
from sqlalchemy.orm import Session

from core.audit_service import audit_service
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AuditEventType, SecurityLevel, ThreatLevel, User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/auth/2fa", tags=["Authentication-2FA"])

class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str

class TwoFactorVerifyRequest(BaseModel):
    code: str

class TwoFactorStatusResponse(BaseModel):
    enabled: bool

@router.get("/status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    """Check if 2FA is enabled for the current user"""
    return {"enabled": current_user.two_factor_enabled}

@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a new 2FA secret and provisioning URL"""
    if current_user.two_factor_enabled:
        raise router.conflict_error("2FA is already enabled")
    
    secret = pyotp.random_base32()
    issuer_name = "Atom AI (Upstream)"
    otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email, 
        issuer_name=issuer_name
    )
    
    current_user.two_factor_secret = secret
    db.commit()
    
    return {
        "secret": secret,
        "otpauth_url": otpauth_url
    }

@router.post("/enable")
async def enable_2fa(
    request: Request,
    verify_data: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify code and enable 2FA"""
    if current_user.two_factor_enabled:
        raise router.conflict_error("2FA is already enabled")

    if not current_user.two_factor_secret:
        raise router.validation_error("two_factor_secret", "2FA setup not initiated")
    
    totp = pyotp.TOTP(current_user.two_factor_secret)
    if totp.verify(verify_data.code):
        current_user.two_factor_enabled = True
        current_user.two_factor_backup_codes = ["UP-BACKUP-1234-5678"] 
        db.commit()
        
        audit_service.log_event(
            db,
            event_type=AuditEventType.UPDATE.value,
            action="2fa_enabled",
            description=f"2FA enabled for user: {current_user.email}",
            user_id=current_user.id,
            user_email=current_user.email,
            security_level=SecurityLevel.HIGH.value,
            request=request
        )

        return router.success_response(
            data={"backup_codes": current_user.two_factor_backup_codes},
            message="2FA enabled successfully"
        )
    else:
        raise router.validation_error("code", "Invalid verification code")

@router.post("/disable")
async def disable_2fa(
    request: Request,
    verify_data: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable 2FA after verifying a code"""
    if not current_user.two_factor_enabled:
        raise router.validation_error("two_factor_enabled", "2FA is not enabled")
    
    totp = pyotp.TOTP(current_user.two_factor_secret)
    if totp.verify(verify_data.code):
        current_user.two_factor_enabled = False
        current_user.two_factor_secret = None
        current_user.two_factor_backup_codes = None
        db.commit()
        
        audit_service.log_event(
            db,
            event_type=AuditEventType.UPDATE.value,
            action="2fa_disabled",
            description=f"2FA disabled for user: {current_user.email}",
            user_id=current_user.id,
            user_email=current_user.email,
            security_level=SecurityLevel.HIGH.value,
            request=request
        )

        return router.success_response(message="2FA disabled successfully")
    else:
        raise router.validation_error("code", "Invalid verification code")
