"""
Mobile Authentication Routes

Provides mobile-specific authentication endpoints:
- Mobile login with device registration
- Biometric authentication registration
- Mobile token refresh
- Device management
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import (
    authenticate_mobile_user,
    create_access_token,
    create_mobile_token,
    get_current_user,
    get_mobile_device,
    verify_biometric_signature,
    verify_password,
)
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import MobileDevice, User, UserStatus
from core.security.auth_rate_limit import login_rate_limit

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/auth", tags=["Authentication"])

# ============================================================================
# Request/Response Models
# ============================================================================

class MobileLoginRequest(BaseModel):
    # BUG FIX: email accepted unbounded input (a 10k-char email flowed into
    # the user lookup instead of being rejected with 422). Cap at 254, the
    # RFC 5321 practical limit for an email address.
    email: str = Field(..., max_length=254)
    password: str
    device_token: str
    # BUG FIX: platform was a free-form string, so arbitrary values (e.g.
    # "invalid_platform") were accepted and stored on the MobileDevice row.
    # Push notifications only work for the two documented platforms.
    platform: Literal["ios", "android"]
    device_info: Optional[Dict[str, Any]] = None


class MobileLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: str
    token_type: str
    user: Dict[str, Any]


class BiometricRegisterRequest(BaseModel):
    public_key: str
    device_token: str
    platform: str


class BiometricRegisterResponse(BaseModel):
    success: bool
    challenge: str
    message: str


class BiometricAuthRequest(BaseModel):
    device_id: str
    signature: str
    challenge: str


class BiometricAuthResponse(BaseModel):
    success: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    message: str


class RefreshTokenRequest(BaseModel):
    # BUG FIX: an empty refresh_token passed schema validation and surfaced
    # as a 401 "Invalid refresh token" from the JWT decoder instead of the
    # documented 422 validation error.
    refresh_token: str = Field(..., min_length=1)


class DeviceInfoResponse(BaseModel):
    device_id: str
    platform: str
    status: str
    notification_enabled: bool
    last_active: str
    created_at: str

# ============================================================================
# Mobile Authentication Routes
# ============================================================================

@router.post("/mobile/login", response_model=MobileLoginResponse)
async def mobile_login(
    request: Request,
    login_data: MobileLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Mobile login with automatic device registration.

    Args:
        request: HTTP request (for rate-limit enforcement)
        login_data: Login credentials and device information
        db: Database session

    Returns:
        Access token, refresh token, and user information

    Raises:
        401: Invalid credentials
        400: Invalid request data
    """
    limiter = request.app.dependency_overrides.get(login_rate_limit, login_rate_limit)
    limiter(request)
    try:
        # Authenticate user
        result = await authenticate_mobile_user(
            email=login_data.email,
            password=login_data.password,
            device_token=login_data.device_token,
            platform=login_data.platform,
            db=db
        )

        if not result:
            # Invalid credentials are an authentication failure (401), not a
            # schema validation error (422): the mobile client maps 400/401 to
            # "Invalid credentials" but falls through to a generic message on
            # 422, and the documented contract is 401.
            raise router.unauthorized_error(
                "Invalid email or password"
            )

        # Update device info if provided
        if login_data.device_info and result.get("user"):
            user_id = result["user"]["id"]
            device = db.query(MobileDevice).filter(
                MobileDevice.device_token == login_data.device_token
            ).first()

            if device:
                device.device_info = login_data.device_info
                device.last_active = datetime.now(timezone.utc)
                db.commit()

        logger.info(f"Mobile login successful for {login_data.email}")

        return MobileLoginResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mobile login error: {e}")
        raise router.internal_error("Internal error")


@router.post("/mobile/biometric/register", response_model=BiometricRegisterResponse)
async def register_biometric(
    request: BiometricRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register device for biometric authentication (Face ID, Touch ID).

    Args:
        request: Biometric registration data
        current_user: Authenticated user
        db: Database session

    Returns:
        Challenge string for device to sign

    Raises:
        400: Invalid request
        404: Device not found
    """
    try:
        # Find device by token
        device = db.query(MobileDevice).filter(
            MobileDevice.device_token == request.device_token,
            MobileDevice.user_id == str(current_user.id)
        ).first()

        if not device:
            raise router.not_found_error("Device", request.device_token)

        # Generate challenge
        import secrets
        challenge = secrets.token_urlsafe(32)

        # Store public key (in production, this should be encrypted)
        # For now, we'll store it in device_info
        # NOTE: copy the dict before mutating — SQLAlchemy holds the committed
        # JSON value by reference, so in-place mutation is never detected and
        # the UPDATE silently omits device_info (row never changes).
        device_info = dict(device.device_info or {})
        device_info["biometric_public_key"] = request.public_key
        device_info["biometric_challenge"] = challenge
        device_info["biometric_enabled"] = False  # Will be enabled after first successful auth
        device.device_info = device_info
        device.last_active = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Biometric registration initiated for device {device.id}")

        return BiometricRegisterResponse(
            success=True,
            challenge=challenge,
            message="Biometric registration initiated. Please sign the challenge."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Biometric registration error: {e}")
        raise router.internal_error("Internal error")


@router.post("/mobile/biometric/authenticate", response_model=BiometricAuthResponse)
async def authenticate_with_biometric(
    request: BiometricAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate using biometric signature.

    Args:
        request: Biometric authentication data
        db: Database session

    Returns:
        Access tokens if authentication successful

    Raises:
        401: Invalid signature
        404: Device not found
    """
    try:
        # Get device
        device = get_mobile_device(request.device_id, request.signature, db)
        if not device:
            # Try to get device by ID
            device = db.query(MobileDevice).filter(
                MobileDevice.id == request.device_id
            ).first()

        if not device:
            raise router.not_found_error("Device", request.device_id)

        # Get stored public key and challenge
        device_info = device.device_info or {}
        public_key = device_info.get("biometric_public_key")
        stored_challenge = device_info.get("biometric_challenge")

        if not public_key:
            # Well-formed request but the device has no biometric registration
            # yet — a client state error (400), not a schema violation (422).
            raise router.error_response(
                error_code="BIOMETRIC_NOT_REGISTERED",
                message="Biometric not registered for this device",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # SECURITY: the signature must be over the challenge the server issued
        # at registration. Previously the client-supplied challenge was used
        # verbatim, so any captured (challenge, signature) pair replayed — the
        # server never checked the registered challenge.
        if not stored_challenge or request.challenge != stored_challenge:
            raise router.validation_error(
                "challenge",
                "Invalid authentication challenge"
            )

        # Verify signature
        if not verify_biometric_signature(request.signature, public_key, request.challenge):
            logger.warning(f"Biometric authentication failed for device {device.id}")
            return BiometricAuthResponse(
                success=False,
                message="Invalid signature"
            )

        # Signature is valid, get user
        user = db.query(User).filter(User.id == device.user_id).first()
        if not user:
            raise router.not_found_error("User", device.user_id)

        # R60: reject deactivated/suspended accounts — mirrors the R43 status
        # check; a deactivated user must not authenticate via biometrics.
        if user.status != UserStatus.ACTIVE:
            raise router.validation_error(
                "account", "Account is deactivated"
            )

        # Generate tokens
        tokens = create_mobile_token(user, device.id)

        # Mark biometric as enabled (copy first — see register_biometric note:
        # in-place JSON mutation is invisible to SQLAlchemy's change detection)
        device_info = dict(device.device_info or {})
        device_info["biometric_enabled"] = True
        device_info["last_biometric_auth"] = datetime.now(timezone.utc).isoformat()
        device.device_info = device_info
        device.last_active = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Biometric authentication successful for user {user.email}")

        return BiometricAuthResponse(
            success=True,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            message="Authentication successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Biometric authentication error: {e}")
        raise router.internal_error("Internal error")


@router.post("/mobile/refresh")
async def refresh_mobile_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh mobile access token using refresh token.

    Args:
        request: Refresh token
        db: Database session

    Returns:
        New access and refresh tokens

    Raises:
        401: Invalid refresh token
    """
    try:
        from jose import JWTError, jwt

        # Decode refresh token
        try:
            payload = jwt.decode(
                request.refresh_token,
                router.auth_module.SECRET_KEY if hasattr(router, 'auth_module') else os.getenv("SECRET_KEY"),
                algorithms=["HS256"]
            )
        except JWTError:
            raise router.unauthorized_error("Invalid refresh token")

        user_id = payload.get("sub")
        token_type = payload.get("type")
        device_id = payload.get("device_id")

        if not user_id or token_type != "refresh":
            raise router.unauthorized_error("Invalid refresh token")

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise router.not_found_error("User", user_id)

        # R60: reject deactivated/suspended accounts — mirrors the R43 status
        # check; a deactivated user must not keep renewing sessions.
        if user.status != UserStatus.ACTIVE:
            raise router.validation_error(
                "account", "Account is deactivated"
            )

        # Verify device exists and is active
        device = get_mobile_device(device_id, user_id, db)
        if not device:
            raise router.error_response(
                error_code="INVALID_DEVICE",
                message="Device not found or inactive",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Generate new tokens
        tokens = create_mobile_token(user, device_id)

        logger.info(f"Token refresh successful for user {user.email}")

        return tokens

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise router.internal_error("Internal error")


@router.get("/mobile/device", response_model=DeviceInfoResponse)
async def get_mobile_device_info(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get mobile device information.

    Args:
        device_id: Device ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Device information

    Raises:
        404: Device not found
    """
    try:
        device = get_mobile_device(device_id, str(current_user.id), db)

        if not device:
            raise router.not_found_error("Device", device_id)

        return DeviceInfoResponse(
            device_id=device.id,
            platform=device.platform,
            status=device.status,
            notification_enabled=device.notification_enabled,
            last_active=device.last_active.isoformat(),
            created_at=device.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get device info error: {e}")
        raise router.internal_error("Internal error")


@router.delete("/mobile/device")
async def delete_mobile_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unregister mobile device.

    Args:
        device_id: Device ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Success message
    """
    try:
        device = get_mobile_device(device_id, str(current_user.id), db)

        if not device:
            raise router.not_found_error("Device", device_id)

        # Mark as inactive instead of deleting
        device.status = "inactive"
        device.notification_enabled = False
        device.last_active = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Device {device_id} unregistered by user {current_user.email}")

        return router.success_response(message="Device unregistered successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete device error: {e}")
        raise router.internal_error("Internal error")
