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

class Action2FAVerifyRequest(BaseModel):
    code: str

@router.post("/verify-action/{action_id}")
async def verify_action_2fa(
    action_id: str,
    verify_data: Action2FAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify 2FA code and resolve a high-stakes HITL action"""
    if not current_user.two_factor_enabled:
        raise router.validation_error("two_factor_enabled", "2FA is not enabled for your account")

    # 1. Verify TOTP Code
    import pyotp
    totp = pyotp.TOTP(current_user.two_factor_secret)
    if not totp.verify(verify_data.code):
        raise router.validation_error("code", "Invalid verification code")

    # 2. Resolve Action via HITLService
    from core.hitl_service import hitl_service
    try:
        result = await hitl_service.resolve_action(
            action_id=action_id,
            resolution="approved",
            resolver_id=current_user.id,
            metadata={"verified_2fa": True}
        )
        
        # Log to Audit
        from core.models import AuditEventType, SecurityLevel
        audit_service.log_event(
            db,
            event_type=AuditEventType.UPDATE.value,
            action="hitl_action_verified_2fa",
            description=f"HITL Action {action_id} approved via 2FA by {current_user.email}",
            user_id=current_user.id,
            user_email=current_user.email,
            security_level=SecurityLevel.HIGH.value
        )
        
        return router.success_response(data=result, message="Action approved successfully via 2FA")
    except Exception as e:
        logger.error(f"Failed to verify action via 2FA: {e}")
        raise router.server_error(f"Failed to resolve action: {str(e)}")
