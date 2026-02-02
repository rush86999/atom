"""
Enterprise Authentication API Endpoints
FastAPI-based REST API for user registration, login, and session management.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, EmailStr
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.database import get_db

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

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
        from core.models import User
        from core.enterprise_auth_service import EnterpriseAuthService

        auth_service = EnterpriseAuthService()

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
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

        return {
            "message": "User registered successfully",
            "user_id": user.id,
            "email": user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        user_id = claims.get('user_id')

        # Check user still exists and is active
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
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
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        user_id = claims.get('user_id')

        # Get full user info
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get current user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user info"
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Verify old password
        if not auth_service.verify_password(data.old_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )

        # Hash new password
        user.password_hash = auth_service.hash_password(data.new_password)
        user.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(f"Password changed for user: {user.email}")

        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


# Dependency for protected routes
async def get_current_user_dependency(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Get current user from JWT token for dependency injection"""
    from core.enterprise_auth_service import EnterpriseAuthService

    auth_service = EnterpriseAuthService()
    claims = auth_service.verify_token(token)

    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
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
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {required_roles}"
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
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permission: {permission}"
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
        from core.enterprise_auth_service import EnterpriseAuthService
        from core.database import get_db

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
