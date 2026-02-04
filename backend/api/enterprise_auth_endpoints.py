"""
Enterprise Authentication API Endpoints
FastAPI-based REST API for user registration, login, and session management.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/auth", tags=["authentication"])

# OAuth2 scheme for token-based auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token/login")


# Request/Response Models
class UserRegister(BaseModel):
    """User registration request"""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    role: str = Field("member", description="User role")


class UserLogin(BaseModel):
    """User login request"""
    username: str = Field(..., description="Email or username")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    username: str
    email: str
    roles: List[str]
    security_level: str


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    old_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/register", status_code=201)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user.

    Requirements:
    - Email must be unique
    - Password minimum 8 characters
    - Password hashed with bcrypt (cost factor 12)
    """
    try:
        from core.enterprise_auth_service import EnterpriseAuthService
        from core.models import User

        auth_service = EnterpriseAuthService()

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise router.conflict_error(
                message="User with this email already exists",
                conflicting_resource=user_data.email
            )

        # Hash password
        password_hash = auth_service.hash_password(user_data.password)

        # Create user
        user = User(
            email=user_data.email,
            password_hash=password_hash,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            status="active",
            created_at=datetime.now(timezone.utc)
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"User registered: {user.email}")

        return router.success_response(
            data={
                "user_id": user.id,
                "email": user.email
            },
            message="User registered successfully"
        )

    except Exception as e:
        if e.__class__.__name__ == 'HTTPException':
            raise
        logger.error(f"Registration error: {e}")
        raise router.internal_error(
            message="Failed to register user",
            details={"error": str(e)}
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.

    Returns access_token (1 hour expiry) and refresh_token (7 days expiry).
    """
    try:
        from core.enterprise_auth_service import EnterpriseAuthService

        auth_service = EnterpriseAuthService()

        # Verify credentials
        user_creds = await _verify_enterprise_credentials(
            credentials.username,
            credentials.password
        )

        if not user_creds:
            raise router.unauthorized_error(
                message="Invalid username or password"
            )

        # Update last login
        from core.models import User
        user = db.query(User).filter(User.id == user_creds['user_id']).first()
        if user:
            user.last_login = datetime.now(timezone.utc)
            db.commit()

        # Create tokens
        access_token = auth_service.create_access_token(
            user_creds['user_id'],
            {
                "username": user_creds['username'],
                "email": user_creds['email'],
                "roles": user_creds['roles'],
                "security_level": user_creds['security_level']
            }
        )

        refresh_token = auth_service.create_refresh_token(user_creds['user_id'])

        # Calculate expiry in seconds
        expires_in = int(auth_service.access_token_expiry.total_seconds())

        logger.info(f"User logged in: {user_creds['email']}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            user_id=user_creds['user_id'],
            username=user_creds['username'],
            email=user_creds['email'],
            roles=user_creds['roles'],
            security_level=user_creds['security_level']
        )

    except Exception as e:
        if e.__class__.__name__ == 'HTTPException':
            raise
        logger.error(f"Login error: {e}")
        raise router.internal_error(
            message="Login failed",
            details={"error": str(e)}
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Validates the refresh token and issues new access token.
    """
    try:
        from core.enterprise_auth_service import EnterpriseAuthService
        from core.models import User

        auth_service = EnterpriseAuthService()

        # Verify refresh token
        claims = auth_service.verify_token(refresh_token)
        if not claims or claims.get('type') != 'refresh':
            raise router.unauthorized_error(
                message="Invalid or expired refresh token"
            )

        user_id = claims.get('user_id')

        # Check user still exists and is active
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.status != "active":
            raise router.unauthorized_error(
                message="User not found or inactive"
            )

        # Get user credentials for token creation
        user_creds = auth_service.verify_credentials(db, user.email, "")  # No password needed for refresh
        if not user_creds:
            # Fallback: create basic credentials
            user_creds = {
                'user_id': user.id,
                'username': user.email,
                'email': user.email,
                'roles': [user.role],
                'security_level': 'standard',
                'permissions': []
            }

        # Create new access token
        access_token = auth_service.create_access_token(
            user_id,
            {
                "username": user_creds['username'],
                "email": user_creds['email'],
                "roles": user_creds['roles'],
                "security_level": user_creds['security_level']
            }
        )

        # Calculate expiry
        expires_in = int(auth_service.access_token_expiry.total_seconds())

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # Return same refresh token
            token_type="bearer",
            expires_in=expires_in,
            user_id=user_creds['user_id'],
            username=user_creds['username'],
            email=user_creds['email'],
            roles=user_creds['roles'],
            security_level=user_creds['security_level']
        )

    except HTTPException:
        raise
    except Exception as e:
        if e.__class__.__name__ == 'HTTPException':
            raise
        logger.error(f"Token refresh error: {e}")
        raise router.unauthorized_error(
            message="Invalid refresh token",
            details={"error": str(e)}
        )


@router.get("/me")
async def get_current_user(
    current_user: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Get current user info from JWT token.
    """
    try:
        from core.enterprise_auth_service import EnterpriseAuthService
        from core.models import User

        auth_service = EnterpriseAuthService()

        # Verify token and get claims
        claims = auth_service.verify_token(current_user)
        if not claims:
            raise router.unauthorized_error(
                message="Invalid token"
            )

        user_id = claims.get('user_id')

        # Get full user info
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise router.not_found_error(
                resource="User",
                resource_id=user_id
            )

        return router.success_response(
            data={
                "user_id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None
            },
            message="User info retrieved successfully"
        )

    except Exception as e:
        if e.__class__.__name__ == 'HTTPException':
            raise
        logger.error(f"Get current user error: {e}")
        raise router.internal_error(
            message="Failed to get user info",
            details={"error": str(e)}
        )


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Change user password.
    """
    try:
        from core.enterprise_auth_service import EnterpriseAuthService
        from core.models import User

        auth_service = EnterpriseAuthService()

        # Verify current user
        claims = auth_service.verify_token(current_user)
        if not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        user_id = claims.get('user_id')

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise router.not_found_error(
                resource="User",
                resource_id=user_id
            )

        # Verify old password
        if not auth_service.verify_password(data.old_password, user.password_hash):
            raise router.unauthorized_error(
                message="Current password is incorrect"
            )

        # Hash new password
        user.password_hash = auth_service.hash_password(data.new_password)
        user.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(f"Password changed for user: {user.email}")

        return router.success_response(
            message="Password changed successfully"
        )

    except Exception as e:
        if e.__class__.__name__ == 'HTTPException':
            raise
        logger.error(f"Change password error: {e}")
        raise router.internal_error(
            message="Failed to change password",
            details={"error": str(e)}
        )


# Dependency for protected routes
async def get_current_user_dependency(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current user from JWT token for dependency injection"""
    from core.enterprise_auth_service import EnterpriseAuthService

    auth_service = EnterpriseAuthService()
    claims = auth_service.verify_token(token)

    if not claims:
        raise router.unauthorized_error(
            message="Invalid token"
        )

    return claims


# RBAC Middleware
def require_role(required_roles: List[str]):
    """Decorator to require specific roles"""
    def decorator(func):
        async def wrapper(current_user: Dict[str, Any] = Depends(get_current_user_dependency)):
            user_roles = current_user.get('roles', [])

            # Check if user has any of the required roles
            if not any(role in user_roles for role in required_roles):
                raise router.permission_denied_error(
                    action="access_resource",
                    resource="protected_endpoint",
                    details={"required_roles": required_roles, "user_roles": user_roles}
                )

            return await func(current_user)
        return wrapper
    return decorator


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        async def wrapper(current_user: Dict[str, Any] = Depends(get_current_user_dependency)):
            user_permissions = current_user.get('permissions', [])

            # Admin users have all permissions
            if "all" in user_permissions:
                return await func(current_user)

            # Check for specific permission
            if permission not in user_permissions:
                raise router.permission_denied_error(
                    action=f"require_permission_{permission}",
                    resource="protected_endpoint",
                    details={"required_permission": permission}
                )

            return await func(current_user)
        return wrapper
    return decorator


@router.get("/test-auth")
async def test_auth_endpoint(current_user: Dict[str, Any] = Depends(get_current_user_dependency)):
    """
    Test authentication endpoint.
    """
    return {
        "message": "Authentication working",
        "user": current_user
    }


# Keep original function for backward compatibility
async def _verify_enterprise_credentials(username: str, password: str) -> Dict[str, Any]:
    """Legacy function - kept for backward compatibility"""
    return await _verify_enterprise_credentials_new(username, password)


async def _verify_enterprise_credentials_new(username: str, password: str) -> Dict[str, Any]:
    """
    Verify enterprise credentials using the enterprise auth service.

    Args:
        username: Username or email
        password: Plain text password

    Returns:
        User credentials dict if valid, None if invalid
    """
    try:
        from core.database import get_db
        from core.enterprise_auth_service import EnterpriseAuthService

        auth_service = EnterpriseAuthService()

        # Get database session
        db = next(get_db())

        try:
            # Verify credentials
            user_creds = auth_service.verify_credentials(db, username, password)

            if not user_creds:
                return None

            # Convert to expected format
            return {
                'user_id': user_creds.user_id,
                'username': user_creds.username,
                'email': user_creds.email,
                'roles': user_creds.roles,
                'security_level': user_creds.security_level,
                'permissions': user_creds.permissions
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Enterprise credential verification error: {e}")
        return None
