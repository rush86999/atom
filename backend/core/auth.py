# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
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
from core.models import User, MobileDevice, UserStatus

# Configuration
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET")
if not SECRET_KEY:
    if os.getenv("ENVIRONMENT") == "production" or os.getenv("NODE_ENV") == "production":
        raise ValueError("SECRET_KEY environment variable is required in production")
    else:
        # Dev fallback: generate once and PERSIST under data/, so a backend
        # restart doesn't mint a new secret and invalidate every issued JWT
        # (users were logged out on every restart before this). Set SECRET_KEY
        # in the environment to override.
        _secret_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", ".dev_secret_key"
        )
        try:
            if os.path.exists(_secret_file):
                with open(_secret_file) as f:
                    SECRET_KEY = f.read().strip()
            if not SECRET_KEY:
                SECRET_KEY = secrets.token_urlsafe(48)
                os.makedirs(os.path.dirname(_secret_file), exist_ok=True)
                with open(_secret_file, "w") as f:
                    f.write(SECRET_KEY)
                try:
                    os.chmod(_secret_file, 0o600)
                except OSError:
                    pass
        except OSError as e:
            # Read-only filesystem or similar: fall back to the historical
            # per-process key rather than failing startup.
            SECRET_KEY = secrets.token_urlsafe(32)
            logger.warning(f"Could not persist dev secret key ({e}); sessions reset on restart.")
        logger.info("Dev secret key loaded (persisted for restart survival). Set SECRET_KEY to override.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt"""
    # Reject non-string/non-bytes inputs up front. Without this, ``None``
    # reaches ``plain_password[:71]`` below and raises TypeError OUTSIDE the
    # try/except — surfacing as a 500 to callers (e.g. a malformed login
    # request) instead of a clean "wrong password" False. bcrypt.checkpw
    # requires bytes, so any other type is a no-match.
    if not isinstance(plain_password, (str, bytes)):
        return False
    if not isinstance(hashed_password, (str, bytes)):
        return False

    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')

    # Truncate to 72 bytes to match bcrypt's hard 72-byte input limit
    # (hashpw/checkpw both accept exactly 72 bytes). Truncating to 71 here
    # made a valid 72-byte password hash (accepted by get_password_hash)
    # never verify — 72-byte registration succeeded but login always failed.
    plain_password = plain_password[:72]

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
        encoded = password.encode('utf-8')
        if len(encoded) > 72:
            # Fail closed: bcrypt silently truncates past 72 bytes, which makes
            # distinct long passwords collide to the same hash (entropy loss,
            # and an old long password keeps working after a change).
            raise ValueError("Password exceeds 72-byte bcrypt limit")
        password = encoded

    # Generate salt and hash
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # Add a unique token ID (jti) so individual tokens can be revoked (logout).
    import uuid as _uuid
    to_encode.update({"exp": expire, "jti": str(_uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- Token revocation (logout) ---
# Lightweight in-memory denylist of revoked jti claims. Single-process
# single-tenant — sufficient without Redis. Bounded; expired entries are
# pruned on access. Without this, a stolen JWT stays valid for 24h after
# logout (ACCESS_TOKEN_EXPIRE_MINUTES = 60*24).
_revoked_tokens: set = set()
_revoked_expiry: dict = {}  # jti -> exp timestamp (for pruning)


def revoke_token(jti: str, exp: int) -> None:
    """Mark a token as revoked (used by /logout)."""
    _revoked_tokens.add(jti)
    _revoked_expiry[jti] = exp


def is_token_revoked(jti: Optional[str]) -> bool:
    """Check if a token has been revoked. Prunes expired entries."""
    if not jti:
        return False
    # Prune expired revocations.
    now = datetime.now(timezone.utc).timestamp()
    expired = [k for k, exp in _revoked_expiry.items() if exp < now]
    for k in expired:
        _revoked_tokens.discard(k)
        _revoked_expiry.pop(k, None)
    return jti in _revoked_tokens




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
        # Check query params for direct browser redirects
        if not token:
            token = request.query_params.get("token") or request.query_params.get("auth_token")
            
    if not token:
        raise credentials_exception

    if token.startswith('"') and token.endswith('"'):
        token = token[1:-1]
        
    # Early validation: Skip obviously invalid tokens before JWT decode
    # Valid JWTs must have 2 dots separating 3 segments: header.payload.signature
    if token.count('.') != 2:
        logger.warning("JWT validation skipped: invalid token format")
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Support multiple JWT claim conventions:
        #   - "sub"     : standard OIDC/JWT claim
        #   - "id"      : NextAuth fallback
        #   - "user_id" : Atom enterprise_auth_endpoints token format (issued at
        #                 api/enterprise_auth_endpoints.py:109). Without this,
        #                 every token issued by /api/auth/login fails validation
        #                 here, breaking /api/users/me and any endpoint using
        #                 get_current_user as a dependency.
        user_id: str = payload.get("sub") or payload.get("id") or payload.get("user_id")

        if user_id is None:
            logger.warning(
                "JWT validation failed: token payload missing 'sub', 'id', and 'user_id' claims"
            )
            raise credentials_exception

        # Token revocation check (logout). If the token's jti is in the
        # denylist, reject it — even if the JWT hasn't expired yet.
        token_jti = payload.get("jti")
        if is_token_revoked(token_jti):
            logger.warning(f"Rejected revoked token (jti={token_jti}) for user {user_id}")
            raise credentials_exception
    except JWTError as e:
        logger.warning("JWT decode error during user lookup")
        raise credentials_exception
    except Exception as e:
        logger.warning("Unexpected error during token validation")
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning("Token referenced non-existent user_id=%s", user_id)
        raise credentials_exception

    # Round 43: reject tokens for non-ACTIVE accounts. Login already blocks
    # suspended/deleted users, but an already-issued JWT (24h lifetime) kept
    # working after an admin soft-deleted the account — every get_current_user
    # protected endpoint was affected. Mirrors the login status check.
    if user.status != UserStatus.ACTIVE:
        logger.warning(
            "Rejected token for non-active user %s (status=%s)", user_id, user.status
        )
        raise credentials_exception
    return user

async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve the authenticated user's Tenant.

    Single-tenant (Personal Edition): prefers the user's tenant_id (falling
    back to the personal default via personal_scope), then the first Tenant
    row. Round 47: previously core.auth never exported this, so callers that
    imported it with a silent None fallback (api/byok_routes.py) had their
    tenant parameter become a required query param via Depends(None) — every
    tenant-scoped BYOK endpoint returned 422 on every call.
    """
    from core.models import Tenant
    from core.personal_scope import resolve_tenant_id

    tenant_id = resolve_tenant_id(current_user)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        tenant = db.query(Tenant).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="No tenant configured")
    return tenant


async def get_current_user_ws(token: str, db: Session) -> Optional[User]:
    """Get user from token for WebSocket connections"""
    # Early validation: Skip obviously invalid tokens before JWT decode
    if not token or token.count('.') != 2:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Same fallback chain as get_current_user: sub → id → user_id
        user_id: str = payload.get("sub") or payload.get("id") or payload.get("user_id")
        if user_id is None:
            return None
        # Token revocation check (logout). Mirrors get_current_user — without
        # this, a logged-out / revoked JWT stayed valid for every WS endpoint
        # until the 24h expiry.
        token_jti = payload.get("jti")
        if is_token_revoked(token_jti):
            logger.warning(f"Rejected revoked WS token (jti={token_jti}) for user {user_id}")
            return None
        user = db.query(User).filter(User.id == user_id).first()
        # Round 43: reject non-ACTIVE accounts (deleted/suspended users)
        if user is None or user.status != UserStatus.ACTIVE:
            return None
        return user
    except JWTError:
        return None

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify JWT token.

    Returns the token payload if valid, None otherwise.
    This is a synchronous version for use in non-async contexts.
    """
    # Early validation: Skip obviously invalid tokens before JWT decode
    if not token or token.count('.') != 2:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Token revocation check (logout). Mirrors get_current_user and
        # get_current_user_ws — without this, a revoked (logged-out) JWT stayed
        # valid for any code path using this synchronous helper
        # (security_dependencies, auth_helpers, device_websocket).
        token_jti = payload.get("jti")
        if is_token_revoked(token_jti):
            logger.warning(f"Rejected revoked token in decode_token (jti={token_jti})")
            return None
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
        # Reject non-ACTIVE accounts. Mirrors get_current_user (line ~190),
        # get_current_user_ws, and authenticate_mobile_user — without this,
        # a suspended/deleted user's existing 24h mobile JWT kept
        # authenticating them after their account was revoked.
        if user is None or user.status != UserStatus.ACTIVE:
            return None
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
        # Decode signature; the public key is passed as PEM text (base64-
        # decoding it here corrupts the DER body with the header/footer
        # alphabet chars, so every verification failed with MalformedFraming).
        signature_bytes = base64.b64decode(signature)
        public_key_bytes = public_key.encode('utf-8')
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
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user.id),
        "email": user.email,
        "device_id": device_id,
        "platform": "mobile",
        "exp": expire
    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Create refresh token (longer-lived)
    refresh_expire = datetime.now(timezone.utc) + timedelta(days=30)
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

    # R60: reject deactivated/suspended accounts — mirrors login_for_access_token
    # (R43). Without this, a deactivated user keeps authenticating via mobile.
    if user.status != UserStatus.ACTIVE:
        return None

    if not verify_password(password, user.hashed_password):
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
            device_info={"registered_at": datetime.now(timezone.utc).isoformat()}
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        # Update existing device
        device.platform = platform
        device.status = "active"
        device.last_active = datetime.now(timezone.utc)
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
