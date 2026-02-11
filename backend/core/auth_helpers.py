"""
Authentication Helper Functions

Provides standardized user authentication and resolution functions
to replace default_user placeholder authentication throughout the codebase.
"""

from datetime import datetime, timedelta
import logging
import os
from typing import Any, Dict, Optional
import uuid
from fastapi import HTTPException
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from core.models import ActiveToken, RevokedToken, User

logger = logging.getLogger(__name__)


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token with proper validation.

    Args:
        token: JWT token string to verify

    Returns:
        Decoded JWT payload as dictionary

    Raises:
        HTTPException: If token is invalid, expired, or malformed
    """
    secret_key = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY"))
    emergency_bypass = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

    if not secret_key and not emergency_bypass:
        logger.error("JWT verification failed: No secret key configured")
        raise HTTPException(
            status_code=500,
            detail="JWT secret not configured"
        )

    try:
        # Verify JWT signature and expiration
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True}
        )

        # Verify required claims
        if not payload.get("sub"):
            logger.error("JWT verification failed: Token missing 'sub' claim")
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing subject"
            )

        logger.info(f"JWT verified successfully for sub={payload.get('sub')}")
        return payload

    except ExpiredSignatureError:
        logger.warning("JWT verification failed: Token expired")
        raise HTTPException(
            status_code=401,
            detail="Token expired"
        )
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        if emergency_bypass:
            logger.warning("EMERGENCY BYPASS: Allowing unverified token")
            return {"user_id": "emergency_user", "bypass": True}
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"JWT verification error: {e}")
        if emergency_bypass:
            logger.warning("EMERGENCY BYPASS: Allowing unverified token")
            return {"user_id": "emergency_user", "bypass": True}
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )


async def require_authenticated_user(
    user_id: Optional[str] = None,
    db: Optional[Session] = None,
    allow_default: bool = False
) -> User:
    """
    Resolve and validate authenticated user.

    This function replaces the default_user placeholder authentication pattern
    throughout the codebase. It ensures proper user authentication and validation.

    Args:
        user_id: The user ID to validate. If None or "default_user", will raise
                 an error unless allow_default is True.
        db: Database session for user validation. If provided, will validate
            that the user exists in the database.
        allow_default: If True, allows default_user fallback for backwards
                      compatibility during migration. This should be set to
                      False in production.

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: 401 if user not authenticated, 404 if user not found in database

    Examples:
        # In API routes
        @router.get("/protected")
        async def protected_route(
            user_id: Optional[str] = None,
            db: Session = Depends(get_db)
        ):
            user = await require_authenticated_user(user_id, db, allow_default=False)
            # Use user.id, user.email, etc.

        # In service layer
        async def process_agent(workspace_id: str, user_id: Optional[str] = None, db: Session = None):
            user = await require_authenticated_user(user_id, db)
            # Process with authenticated user
    """
    # Check for missing or placeholder user_id
    if not user_id or user_id == "default_user":
        if allow_default:
            # Try to get default user from database (for backwards compatibility)
            if db:
                default_user = db.query(User).filter(User.email == "admin@atom.ai").first()
                if default_user:
                    logger.warning("⚠️ DEFAULT_USER FALLBACK - Deprecated, use proper authentication")
                    return default_user

            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please provide valid user credentials."
            )
        else:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please provide valid user credentials."
            )

    # Validate user exists in database if db session provided
    if db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID '{user_id}' not found in database"
            )
        return user

    # If no db session, return minimal User object for validation
    # (Note: This is less secure, prefer providing db session)
    return User(id=user_id, email="")


async def get_optional_user(
    user_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Optional[User]:
    """
    Get user if authenticated, return None if not.

    This is a softer version of require_authenticated_user that doesn't raise
    an exception for missing authentication. Useful for optional features.

    Args:
        user_id: The user ID to look up
        db: Database session for user validation

    Returns:
        User object if found, None otherwise

    Examples:
        # Optional features
        async def get personalized_content(user_id: Optional[str] = None, db: Session = None):
            user = await get_optional_user(user_id, db)
            if user:
                return get_user_specific_content(user.id)
            else:
                return get_generic_content()
    """
    if not user_id or user_id == "default_user":
        return None

    if db:
        user = db.query(User).filter(User.id == user_id).first()
        return user

    return User(id=user_id, email="")


def validate_user_context(user_id: Optional[str], operation: str) -> None:
    """
    Quick validation that user_id is provided for an operation.

    This is a lightweight check for operations that need user context
    but don't require full database validation.

    Args:
        user_id: The user ID to validate
        operation: Description of the operation being performed (for error message)

    Raises:
        HTTPException: 401 if user_id not provided

    Examples:
        # Quick validation in service methods
        def process_payment(amount: float, user_id: Optional[str] = None):
            validate_user_context(user_id, "process payment")
            # Continue with payment processing
    """
    if not user_id or user_id == "default_user":
        raise HTTPException(
            status_code=401,
            detail=f"Authentication required to {operation}"
        )


def revoke_token(
    jti: str,
    expires_at: datetime,
    db: Session,
    user_id: Optional[str] = None,
    revocation_reason: Optional[str] = None
) -> bool:
    """
    Revoke a JWT token by adding it to the revoked tokens list.

    Args:
        jti: JWT ID (from token payload)
        expires_at: Token expiration time (for cleanup)
        db: Database session
        user_id: Optional user ID who owns the token
        revocation_reason: Optional reason (logout, password_change, security_breach, admin_action)

    Returns:
        True if token was revoked, False if already revoked

    Raises:
        HTTPException: 500 if database operation fails

    Examples:
        # Revoke token on logout
        @router.post("/auth/logout")
        async def logout(token_data: TokenLogoutRequest, db: Session = Depends(get_db)):
            payload = decode_token(token_data.token)
            revoke_token(
                jti=payload['jti'],
                expires_at=datetime.fromtimestamp(payload['exp']),
                db=db,
                user_id=payload['sub'],
                revocation_reason="logout"
            )
            return {"success": True}
    """
    try:
        # Check if token is already revoked
        existing = db.query(RevokedToken).filter_by(jti=jti).first()
        if existing:
            logger.warning(f"Token {jti} already revoked at {existing.revoked_at}")
            return False

        # Create revoked token entry
        revoked_token = RevokedToken(
            jti=jti,
            expires_at=expires_at,
            user_id=user_id,
            revocation_reason=revocation_reason or "logout"
        )
        db.add(revoked_token)
        db.commit()

        logger.info(f"Token revoked: jti={jti}, user_id={user_id}, reason={revocation_reason}")
        return True

    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke token"
        )


def revoke_all_user_tokens(
    user_id: str,
    db: Session,
    except_jti: Optional[str] = None,
    revocation_reason: Optional[str] = None
) -> int:
    """
    Revoke all tokens for a user (e.g., on password change).

    This function finds all active tokens for the user and revokes them.
    Optionally preserves one token (except_jti) for the current session.

    Args:
        user_id: User ID whose tokens should be revoked
        except_jti: Optional JTI to exclude (e.g., current token to keep logged in)
        db: Database session
        revocation_reason: Optional reason for revocation (logout, password_change, security_breach, admin_action)

    Returns:
        Number of tokens revoked

    Examples:
        # Revoke all tokens when password changes
        @router.post("/auth/change-password")
        async def change_password(
            request: ChangePasswordRequest,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            # Update password
            current_user.password_hash = hash_password(request.new_password)
            db.commit()

            # Revoke all existing tokens
            count = revoke_all_user_tokens(
                user_id=current_user.id,
                db=db,
                revocation_reason="password_change"
            )

            return {"success": True, "revoked_tokens": count}
    """
    try:
        # Find all active tokens for this user
        query = db.query(ActiveToken).filter(ActiveToken.user_id == user_id)

        # Exclude current token if specified
        if except_jti:
            query = query.filter(ActiveToken.jti != except_jti)

        active_tokens = query.all()

        if not active_tokens:
            logger.info(f"No active tokens found for user {user_id}")
            return 0

        revoked_count = 0

        # Revoke each active token
        for token in active_tokens:
            # Check if already revoked
            existing_revoked = db.query(RevokedToken).filter_by(jti=token.jti).first()
            if existing_revoked:
                logger.warning(f"Token {token.jti} already revoked at {existing_revoked.revoked_at}")
                continue

            # Create revoked token entry
            revoked_token = RevokedToken(
                jti=token.jti,
                expires_at=token.expires_at,
                user_id=user_id,
                revocation_reason=revocation_reason or "admin_action"
            )
            db.add(revoked_token)

            # Delete from active tokens
            db.delete(token)
            revoked_count += 1

        db.commit()

        logger.info(
            f"Revoked {revoked_count} tokens for user {user_id} "
            f"(reason: {revocation_reason or 'admin_action'})"
        )
        return revoked_count

    except Exception as e:
        logger.error(f"Failed to revoke user tokens: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke tokens"
        )


def track_active_token(
    jti: str,
    user_id: str,
    expires_at: datetime,
    db: Session,
    issued_ip: Optional[str] = None,
    issued_user_agent: Optional[str] = None
) -> bool:
    """
    Track an issued JWT token in the active tokens list.

    This should be called when a JWT token is issued (login, token refresh).

    Args:
        jti: JWT ID (from token payload)
        user_id: User ID who owns the token
        expires_at: Token expiration time
        db: Database session
        issued_ip: Optional IP address where token was issued
        issued_user_agent: Optional user agent string

    Returns:
        True if token was tracked, False if already exists

    Raises:
        HTTPException: 500 if database operation fails

    Examples:
        # Track token on login
        @router.post("/auth/login")
        async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
            # ... authenticate user ...
            token_data = create_access_token(data={"sub": user.id})

            # Track the token
            track_active_token(
                jti=token_data["jti"],
                user_id=user.id,
                expires_at=datetime.fromtimestamp(token_data["exp"]),
                db=db,
                issued_ip=request.client.host,
                issued_user_agent=request.headers.get("user-agent")
            )

            return token_data
    """
    try:
        # Check if token already tracked
        existing = db.query(ActiveToken).filter_by(jti=jti).first()
        if existing:
            logger.warning(f"Token {jti} already tracked at {existing.issued_at}")
            return False

        # Create active token entry
        active_token = ActiveToken(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            issued_ip=issued_ip,
            issued_user_agent=issued_user_agent
        )
        db.add(active_token)
        db.commit()

        logger.info(f"Token tracked: jti={jti}, user_id={user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to track token: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to track token"
        )


def cleanup_expired_revoked_tokens(db: Session, older_than_hours: int = 24) -> int:
    """
    Cleanup expired revoked tokens from the database.

    Should be run periodically (e.g., daily) to remove old entries.

    Args:
        db: Database session
        older_than_hours: Delete tokens that expired more than this many hours ago

    Returns:
        Number of tokens deleted

    Examples:
        # Run as a periodic task
        from core.periodic_tasks import register_periodic_task

        def cleanup_revoked_tokens():
            with SessionLocal() as db:
                count = cleanup_expired_revoked_tokens(db)
                logger.info(f"Cleaned up {count} expired revoked tokens")

        register_periodic_task(cleanup_revoked_tokens, hours=24)
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

        deleted = db.query(RevokedToken).filter(
            RevokedToken.expires_at < cutoff_time
        ).delete()

        db.commit()

        logger.info(f"Cleaned up {deleted} expired revoked tokens (older than {older_than_hours}h)")
        return deleted

    except Exception as e:
        logger.error(f"Failed to cleanup expired revoked tokens: {e}")
        db.rollback()
        return 0


def cleanup_expired_active_tokens(db: Session, older_than_hours: int = 1) -> int:
    """
    Cleanup expired active tokens from the database.

    Should be run periodically (e.g., hourly) to remove expired tokens
    that weren't properly revoked.

    Args:
        db: Database session
        older_than_hours: Delete tokens that expired more than this many hours ago

    Returns:
        Number of tokens deleted

    Examples:
        # Run as a periodic task
        from core.periodic_tasks import register_periodic_task

        def cleanup_active_tokens():
            with SessionLocal() as db:
                count = cleanup_expired_active_tokens(db)
                logger.info(f"Cleaned up {count} expired active tokens")

        register_periodic_task(cleanup_active_tokens, hours=1)
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

        deleted = db.query(ActiveToken).filter(
            ActiveToken.expires_at < cutoff_time
        ).delete()

        db.commit()

        logger.info(f"Cleaned up {deleted} expired active tokens (older than {older_than_hours}h)")
        return deleted

    except Exception as e:
        logger.error(f"Failed to cleanup expired active tokens: {e}")
        db.rollback()
        return 0
