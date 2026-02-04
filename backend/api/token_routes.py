"""
Token Management Routes

Provides endpoints for JWT token revocation and management.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.auth_helpers import revoke_token, cleanup_expired_revoked_tokens
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.jwt_verifier import verify_token_string
from core.models import User, UserRole

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/auth/tokens", tags=["token-management"])
security = HTTPBearer()


class TokenRevokeRequest(BaseModel):
    """Request to revoke a specific token"""
    token: str
    reason: Optional[str] = "logout"


class TokenRevokeResponse(BaseModel):
    """Response from token revocation"""
    success: bool
    message: str


@router.post("/revoke", response_model=TokenRevokeResponse)
async def revoke_token_endpoint(
    request: Request,
    revoke_data: TokenRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a JWT token.

    Use this endpoint when a user logs out or when you need to invalidate
    a specific token (e.g., on security events).

    Args:
        revoke_data: Token to revoke and optional reason
        current_user: Authenticated user (from dependency)
        db: Database session

    Returns:
        Success confirmation

    Examples:
        POST /api/auth/tokens/revoke
        {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "reason": "logout"
        }
    """
    try:
        # Decode and verify the token
        payload = verify_token_string(revoke_data.token)

        # Verify the token belongs to the current user
        if payload.get('sub') != current_user.id:
            logger.warning(
                f"User {current_user.id} attempted to revoke token for user {payload.get('sub')}"
            )
            raise router.permission_denied_error(
                action="revoke_token",
                resource="Token",
                details={"reason": "You can only revoke your own tokens"}
            )

        # Check if JTI exists
        if 'jti' not in payload:
            raise router.validation_error(
                field="jti",
                message="Token does not have a JTI claim and cannot be revoked"
            )

        # Revoke the token
        was_revoked = revoke_token(
            jti=payload['jti'],
            expires_at=datetime.fromtimestamp(payload['exp']),
            db=db,
            user_id=current_user.id,
            revocation_reason=revoke_data.reason or "logout"
        )

        if was_revoked:
            logger.info(f"Token revoked for user {current_user.id} (reason: {revoke_data.reason})")
            return TokenRevokeResponse(
                success=True,
                message="Token revoked successfully"
            )
        else:
            return TokenRevokeResponse(
                success=True,
                message="Token was already revoked"
            )

    except Exception as e:
        logger.error(f"Error revoking token: {e}")
        raise router.internal_error(message="Failed to revoke token")


@router.post("/cleanup")
async def cleanup_expired_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    older_than_hours: int = 24
):
    """
    Cleanup expired revoked tokens from the database.

    This is a maintenance operation that should be run periodically
    to remove old revoked token entries.

    Args:
        current_user: Authenticated user (admin only in production)
        db: Database session
        older_than_hours: Delete tokens expired more than this many hours ago

    Returns:
        Number of tokens deleted

    Examples:
        POST /api/auth/tokens/cleanup?older_than_hours=24
    """
    # Enforce admin-only access for token cleanup
    if current_user.role != UserRole.SUPER_ADMIN:
        logger.warning(
            f"Non-admin user {current_user.id} (role: {current_user.role}) "
            f"attempted to cleanup expired tokens"
        )
        raise router.permission_denied_error(
            action="cleanup_expired_tokens",
            resource="Token",
            details={
                "reason": "Token cleanup requires super-admin privileges",
                "user_role": current_user.role,
                "required_role": UserRole.SUPER_ADMIN
            }
        )

    try:
        logger.info(
            f"Admin user {current_user.id} initiating token cleanup "
            f"(older_than_hours: {older_than_hours})"
        )
        deleted_count = cleanup_expired_revoked_tokens(db, older_than_hours)

        return router.success_response(
            data={"deleted_count": deleted_count},
            message=f"Cleaned up {deleted_count} expired revoked tokens"
        )

    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {e}")
        raise router.internal_error(message="Failed to cleanup expired tokens")


@router.get("/verify")
async def verify_token_endpoint(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify if a token is valid (not revoked).

    Args:
        token: JWT token to verify
        current_user: Authenticated user
        db: Database session

    Returns:
        Token validation status

    Examples:
        GET /api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """
    try:
        # Decode and verify the token
        payload = verify_token_string(token)

        # Check if token belongs to current user
        if payload.get('sub') != current_user.id:
            raise router.permission_denied_error(
                action="verify_token",
                resource="Token",
                details={"reason": "You can only verify your own tokens"}
            )

        # Check if token is revoked (requires db session)
        from core.jwt_verifier import get_jwt_verifier

        verifier = get_jwt_verifier()
        is_revoked = verifier._is_token_revoked(payload, db)

        return router.success_response(
            data={
                "valid": not is_revoked,
                "revoked": is_revoked,
                "expires_at": datetime.fromtimestamp(payload['exp']),
                "user_id": payload.get('sub'),
                "jti": payload.get('jti')
            },
            message="Token verification complete"
        )

    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return router.success_response(
            data={
                "valid": False,
                "error": str(e)
            },
            message="Token verification failed"
        )
