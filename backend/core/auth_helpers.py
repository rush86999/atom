"""
Authentication Helper Functions

Provides standardized user authentication and resolution functions
to replace default_user placeholder authentication throughout the codebase.
"""

import logging
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models import User

logger = logging.getLogger(__name__)


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
