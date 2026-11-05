import logging
from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.audit_service import audit_service
from core.auth import get_current_user
from core.auth_2fa_write_service import (
    disable_2fa_verified,
    enable_2fa_verified,
    generate_backup_codes as _generate_backup_codes,
    setup_2fa_verified,
    verify_action_2fa_verified,
    verify_backup_code_verified,
)
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.security.auth_rate_limit import AuthRateLimiter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/auth/2fa", tags=["Authentication-2FA"])

# Rate limiter for 2FA code verification endpoints — prevents brute-forcing
# TOTP codes (6 digits = 1M combinations in a 30s window).
_2fa_limiter = AuthRateLimiter(limit=5, window_seconds=60)


def totp_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit 2FA code verification."""
    allowed, _ = _2fa_limiter.check(request)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many 2FA attempts. Try again in a minute.",
            headers={"Retry-After": "60"},
        )


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    operation_id: Optional[str] = None
    status: Optional[str] = None
    verification: Optional[dict] = None


class TwoFactorVerifyRequest(BaseModel):
    code: str


class TwoFactorStatusResponse(BaseModel):
    enabled: bool


class BackupCodeRequest(BaseModel):
    code: str


class Action2FAVerifyRequest(BaseModel):
    code: str


def _raise_refusal(result: dict):
    error = str(result.get("error") or "2FA request refused")
    http_status = int(result.get("http_status") or 422)
    field = result.get("field")
    if http_status == 409:
        raise router.conflict_error(
            error, details={"field": field} if field else None)
    if http_status == 403:
        raise router.permission_denied_error(
            "2FA request", details={"reason": error})
    if http_status == 404:
        raise HTTPException(status_code=404, detail=error)
    raise router.validation_error(field or "code", error)


def _raise_unverified(result: dict):
    raise HTTPException(
        status_code=503,
        detail={
            "error": {
                "code": (
                    "2FA_EFFECT_UNKNOWN"
                    if result.get("status") == "effect_unknown"
                    else "2FA_COMMITTED_UNVERIFIED"),
                "message": result.get("message") or (
                    "2FA state was committed but its verification is "
                    "unresolved. Do not repeat the effect blindly."),
            },
            "status": result.get("status"),
            "verification": result.get("verification"),
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id"),
            "action_id": result.get("action_id"),
            "replay": "do_not_repeat",
        },
    )


def _success(result: dict, default_message: str) -> dict:
    response = router.success_response(
        data=result.get("data"),
        message=result.get("message") or default_message,
    )
    response["verification"] = result.get("verification")
    for key in ("operation_id", "audit_id", "action_id"):
        if result.get(key):
            response[key] = result[key]
    return response


def _handle_factor_result(
    result: dict, default_message: str, *, auth_grant: bool = False,
) -> dict:
    if result.get("status") == "refused":
        _raise_refusal(result)
    if result.get("status") == "effect_unknown":
        _raise_unverified(result)
    verification = result.get("verification") or {}
    if verification.get("status") == "refuted":
        _raise_unverified(result)
    if auth_grant and result.get("status") in (
            "committed_unverified", "effect_unknown"):
        _raise_unverified(result)
    return _success(result, default_message)


@router.get("/status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    """Check if 2FA is enabled for the current user"""
    return {"enabled": current_user.two_factor_enabled}


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    request: Request,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate or recover the pending 2FA secret and provisioning URL.

    A retry while setup is pending returns the SAME scanned enrollment. Once
    2FA is enabled, a replay refuses and never exposes or replaces the secret.
    """
    result = setup_2fa_verified(
        user_id=str(current_user.id),
        request=request,
        operation_id=operation_id,
        audit_logger=audit_service,
    )
    if result.get("status") == "refused":
        _raise_refusal(result)
    if result.get("status") == "effect_unknown":
        _raise_unverified(result)
    verification = result.get("verification") or {}
    if verification.get("status") == "refuted":
        _raise_unverified(result)
    return {
        "secret": result["secret"],
        "otpauth_url": result["otpauth_url"],
        "operation_id": result.get("operation_id"),
        "status": result.get("status"),
        "verification": verification,
    }


@router.post("/enable")
async def enable_2fa(
    request: Request,
    verify_data: TwoFactorVerifyRequest,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl=Depends(totp_rate_limit),
):
    """Verify code and enable 2FA; recovery codes are delivered once."""
    result = enable_2fa_verified(
        user_id=str(current_user.id),
        code=verify_data.code,
        request=request,
        operation_id=operation_id,
        audit_logger=audit_service,
    )
    return _handle_factor_result(
        result, "2FA enabled successfully", auth_grant=False)


@router.post("/disable")
async def disable_2fa(
    request: Request,
    verify_data: TwoFactorVerifyRequest,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl=Depends(totp_rate_limit),
):
    """Disable 2FA after verifying a current TOTP code."""
    result = disable_2fa_verified(
        user_id=str(current_user.id),
        code=verify_data.code,
        request=request,
        operation_id=operation_id,
        audit_logger=audit_service,
    )
    return _handle_factor_result(
        result, "2FA disabled successfully", auth_grant=False)


@router.post("/backup/verify")
async def verify_backup_code(
    request: Request,
    verify_data: BackupCodeRequest,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify and conditionally consume one single-use backup code."""
    result = verify_backup_code_verified(
        user_id=str(current_user.id),
        code=verify_data.code,
        request=request,
        operation_id=operation_id,
        audit_logger=audit_service,
    )
    return _handle_factor_result(
        result, "Backup code verified and consumed", auth_grant=True)


@router.post("/verify-action/{action_id}")
async def verify_action_2fa(
    action_id: str,
    verify_data: Action2FAVerifyRequest,
    request: Request,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl=Depends(totp_rate_limit),
):
    """Verify 2FA and durably approve the exact scoped HITL action.

    A pending/rejected/foreign/stale/duplicate review never releases the
    action. A committed-but-unverified approval returns 503 with the action
    identity; it is not a successful authentication grant.
    """
    result = await verify_action_2fa_verified(
        user_id=str(current_user.id),
        action_id=str(action_id),
        code=verify_data.code,
        request=request,
        operation_id=operation_id,
        audit_logger=audit_service,
    )
    return _handle_factor_result(
        result, "Action approved successfully via 2FA", auth_grant=True)
