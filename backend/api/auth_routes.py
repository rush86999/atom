"""
Mobile Authentication Routes

Provides mobile-specific authentication endpoints:
- Mobile login with device registration
- Biometric authentication registration
- Mobile token refresh
- Device management
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
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
from core.models import MobileDevice, User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/auth", tags=["Authentication"])

# ============================================================================
# Request/Response Models
# ============================================================================

class MobileLoginRequest(BaseModel):
    email: str
    password: str
    device_token: str
    platform: str  # ios, android
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
    refresh_token: str


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
    request: MobileLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Mobile login with automatic device registration.

    Args:
        request: Login credentials and device information
        db: Database session

    Returns:
        Access token, refresh token, and user information

    Raises:
        401: Invalid credentials
        400: Invalid request data
    """
    try:
        # Authenticate user
        result = await authenticate_mobile_user(
            email=request.email,
            password=request.password,
            device_token=request.device_token,
            platform=request.platform,
            db=db
        )

        if not result:
            raise router.validation_error(
                "credentials",
                "Invalid email or password"
            )

        # Update device info if provided
        if request.device_info and result.get("user"):
            user_id = result["user"]["id"]
            device = db.query(MobileDevice).filter(
                MobileDevice.device_token == request.device_token
            ).first()

            if device:
                device.device_info = request.device_info
                device.last_active = datetime.utcnow()
                db.commit()

        logger.info(f"Mobile login successful for {request.email}")

        return MobileLoginResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mobile login error: {e}")
        raise router.internal_error(f"Login failed: {str(e)}")


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
        device_info = device.device_info or {}
        device_info["biometric_public_key"] = request.public_key
        device_info["biometric_challenge"] = challenge
        device_info["biometric_enabled"] = False  # Will be enabled after first successful auth
        device.device_info = device_info
        device.last_active = datetime.utcnow()
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
        raise router.internal_error(f"Registration failed: {str(e)}")


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
            raise router.validation_error(
                "biometric",
                "Biometric not registered for this device"
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

        # Generate tokens
        tokens = create_mobile_token(user, device.id)

        # Mark biometric as enabled
        device_info["biometric_enabled"] = True
        device_info["last_biometric_auth"] = datetime.utcnow().isoformat()
        device.device_info = device_info
        device.last_active = datetime.utcnow()
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
        raise router.internal_error(f"Authentication failed: {str(e)}")


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
            raise router.validation_error("token", "Invalid refresh token")

        user_id = payload.get("sub")
        token_type = payload.get("type")
        device_id = payload.get("device_id")

        if not user_id or token_type != "refresh":
            raise router.validation_error("token", "Invalid refresh token")

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise router.not_found_error("User", user_id)

        # Verify device exists and is active
        device = get_mobile_device(device_id, user_id, db)
        if not device:
            raise router.validation_error("device", "Device not found or inactive")

        # Generate new tokens
        tokens = create_mobile_token(user, device_id)

        logger.info(f"Token refresh successful for user {user.email}")

        return tokens

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise router.internal_error(f"Refresh failed: {str(e)}")


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
        raise router.internal_error(f"Failed to get device info: {str(e)}")


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
        device.last_active = datetime.utcnow()
        db.commit()

        logger.info(f"Device {device_id} unregistered by user {current_user.email}")

        return router.success_response(message="Device unregistered successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete device error: {e}")
        raise router.internal_error(f"Failed to unregister device: {str(e)}")
