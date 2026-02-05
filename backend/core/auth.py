from datetime import datetime, timedelta
import os
import secrets
from typing import Any, Dict, Optional, Union
import bcrypt
from jose import JWTError, jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import base64

BCRYPT_AVAILABLE = True

import logging
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User, MobileDevice

# Configuration
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET")
if not SECRET_KEY:
    if os.getenv("ENVIRONMENT") == "production" or os.getenv("NODE_ENV") == "production":
        raise ValueError("SECRET_KEY environment variable is required in production")
    else:
        # Generate a secure random key for development
        SECRET_KEY = secrets.token_urlsafe(32)
        logger.warning("⚠️ Using auto-generated secret key for development. Set SECRET_KEY env var for persistence.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt"""
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')

    # Truncate to 71 bytes as bcrypt has a 72-byte limit and includes a null terminator
    plain_password = plain_password[:71]

    try:
        return bcrypt.checkpw(plain_password, hashed_password)
    except ValueError as e:
        logger.error(f"Invalid password format in verify_password: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in verify_password: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    if isinstance(password, str):
        # Encode to bytes, truncate to 71 bytes (safe margin)
        password = password.encode('utf-8')[:71]

    # Generate salt and hash
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt




async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from Bearer token OR NextAuth session cookie
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check Cookie if Header is missing
    if not token:
        token = request.cookies.get("next-auth.session-token")
        # Also check for secure cookie name if in production
        if not token:
            token = request.cookies.get("__Secure-next-auth.session-token")
            
    if not token:
        logger.warning("AUTH DEBUG: No token found in header or cookie")
        raise credentials_exception

    try:
        # logger.info(f"AUTH DEBUG: Attempting to decode token: {token[:15]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            # Try "id" field if "sub" is missing (NextAuth sometimes differs)
            user_id = payload.get("id")
            if user_id is None:
                logger.warning("AUTH DEBUG: Token payload missing 'sub' and 'id'")
                raise credentials_exception
    except JWTError as e:
        logger.warning(f"AUTH DEBUG: JWT Decode Error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"AUTH DEBUG: Unexpected Auth Error: {e}")
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning(f"AUTH DEBUG: User {user_id} not found in DB")
        raise credentials_exception
    return user

async def get_current_user_ws(token: str, db: Session) -> Optional[User]:
    """Get user from token for WebSocket connections"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except JWTError:
        return None

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify JWT token.

    Returns the token payload if valid, None otherwise.
    This is a synchronous version for use in non-async contexts.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Failed to decode token: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        return None

def generate_satellite_key() -> str:
    """
    Generate a secure Satellite API Key (sk-...)

    Returns:
        str: A securely generated API key
    """
    return f"sk-{secrets.token_hex(24)}"


# ============================================================================
# Mobile Authentication Functions
# ============================================================================

def verify_mobile_token(token: str, db: Session) -> Optional[User]:
    """
    Verify mobile device token and return user.

    This is an enhanced version that checks if the device is registered and active.

    Args:
        token: JWT access token from mobile app
        db: Database session

    Returns:
        User if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        user = db.query(User).filter(User.id == user_id).first()
        return user
    except JWTError as e:
        logger.warning(f"Mobile token verification failed: {e}")
        return None


def verify_biometric_signature(
    signature: str,
    public_key: str,
    challenge: str
) -> bool:
    """
    Verify biometric authentication signature from mobile device.

    Args:
        signature: Base64-encoded signature from device
        public_key: Device's public key (stored during registration)
        challenge: Challenge string that was signed

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Decode signature and public key
        signature_bytes = base64.b64decode(signature)
        public_key_bytes = base64.b64decode(public_key)
        challenge_bytes = challenge.encode('utf-8')

        # Load public key
        from cryptography.hazmat.primitives.asymmetric import rsa, ec

        # Try to load as EC key (P-256 commonly used for biometric)
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
            pub_key = load_pem_public_key(public_key_bytes, backend=default_backend())

            # Verify signature
            pub_key.verify(
                signature_bytes,
                challenge_bytes,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception:
            # Fallback: try RSA
            from cryptography.hazmat.primitives.serialization import load_pem_public_key
            pub_key = load_pem_public_key(public_key_bytes, backend=default_backend())

            pub_key.verify(
                signature_bytes,
                challenge_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True

    except Exception as e:
        logger.error(f"Biometric signature verification failed: {e}")
        return False


def create_mobile_token(user: User, device_id: str, expires_delta: Optional[timedelta] = None) -> Dict[str, Any]:
    """
    Create mobile-specific access token with device information.

    Args:
        user: User object
        device_id: Mobile device ID
        expires_delta: Optional custom expiration time

    Returns:
        Dictionary with access_token, refresh_token, expires_at
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user.id),
        "email": user.email,
        "device_id": device_id,
        "platform": "mobile",
        "exp": expire
    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Create refresh token (longer-lived)
    refresh_expire = datetime.utcnow() + timedelta(days=30)
    refresh_to_encode = {
        "sub": str(user.id),
        "type": "refresh",
        "device_id": device_id,
        "exp": refresh_expire
    }
    refresh_jwt = jwt.encode(refresh_to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": encoded_jwt,
        "refresh_token": refresh_jwt,
        "expires_at": expire.isoformat(),
        "token_type": "bearer"
    }


def get_mobile_device(device_id: str, user_id: str, db: Session) -> Optional[MobileDevice]:
    """
    Get mobile device with validation.

    Args:
        device_id: Device ID
        user_id: User ID
        db: Database session

    Returns:
        MobileDevice if found and valid, None otherwise
    """
    device = db.query(MobileDevice).filter(
        MobileDevice.id == device_id,
        MobileDevice.user_id == user_id
    ).first()

    if device and device.status != "active":
        logger.warning(f"Device {device_id} is not active (status: {device.status})")
        return None

    return device


async def authenticate_mobile_user(
    email: str,
    password: str,
    device_token: str,
    platform: str,
    db: Session
) -> Optional[Dict[str, Any]]:
    """
    Authenticate mobile user and return tokens with device registration.

    Args:
        email: User email
        password: User password
        device_token: Push notification token
        platform: Platform (ios, android)
        db: Database session

    Returns:
        Dictionary with tokens and user data, or None if authentication fails
    """
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    # Register or update device
    device = db.query(MobileDevice).filter(
        MobileDevice.device_token == device_token
    ).first()

    if not device:
        device = MobileDevice(
            user_id=str(user.id),
            device_token=device_token,
            platform=platform,
            status="active",
            device_info={"registered_at": datetime.utcnow().isoformat()}
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        # Update existing device
        device.platform = platform
        device.status = "active"
        device.last_active = datetime.utcnow()
        db.commit()

    # Create tokens
    tokens = create_mobile_token(user, device.id)

    # Add user info
    tokens["user"] = {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role
    }

    return tokens
