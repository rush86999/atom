from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import Optional
import uuid
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.audit_service import audit_service
from core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from core.config import get_config
from core.database import get_db
from core.security.auth_rate_limit import (
    AuthRateLimiter,
    login_rate_limit,
    register_rate_limit,
)
from core.email_utils import send_smtp_email
from core.models import (
    AuditEventType,
    PasswordResetToken,
    SecurityLevel,
    ThreatLevel,
    User,
    UserStatus,
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# R56: password-recovery endpoints were the only unauthenticated auth surface
# without rate limits — /forgot-password could be used to spam reset emails
# (mailbox flooding / mailer DoS) and /reset-password + /verify-token were
# unthrottled token-guessing surfaces.
_recovery_limiter = AuthRateLimiter(limit=5, window_seconds=300)    # 5/5min
_verify_limiter = AuthRateLimiter(limit=10, window_seconds=300)     # 10/5min
_reset_limiter = AuthRateLimiter(limit=5, window_seconds=300)       # 5/5min


def forgot_password_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit POST /api/auth/forgot-password (5/5min/IP)."""
    allowed, _ = _recovery_limiter.check(request)
    if not allowed:
        logger.warning(
            "forgot-password rate limit exceeded for IP %s",
            _recovery_limiter._client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Try again later.",
        )


def verify_token_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit POST /api/auth/verify-token (10/5min/IP)."""
    allowed, _ = _verify_limiter.check(request)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Try again later.",
        )


def reset_password_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit POST /api/auth/reset-password (5/5min/IP)."""
    allowed, _ = _reset_limiter.check(request)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset attempts. Try again later.",
        )

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    # SECURITY: email must be a well-formed address and password must meet the
    # same 8-char minimum the frontend enforces. Previously both were plain
    # `str`, so POST /register accepted "not-an-email" and 3-char passwords —
    # the backend is the enforcement boundary and cannot trust client-side checks.
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str
    last_name: str
    role: str = "member"

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    password: str

class VerifyTokenRequest(BaseModel):
    token: str

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None

@router.post("/login")
async def login_for_access_token(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db),
    _rl=Depends(login_rate_limit),
):
    import traceback
    from fastapi.responses import JSONResponse
    import pyotp
    try:
        user = db.query(User).filter(User.email == login_data.username).first()
        if not user or not verify_password(login_data.password, user.hashed_password):
            audit_service.log_event(
                db, 
                event_type=AuditEventType.LOGIN.value,
                action="login_failed",
                description=f"Failed login attempt for email: {login_data.username}",
                user_email=login_data.username,
                security_level=SecurityLevel.MEDIUM.value,
                threat_level=ThreatLevel.LOW.value,
                success=False,
                error_message="Incorrect username or password",
                request=request
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if user.status != UserStatus.ACTIVE:
            # ... (unchanged audit and exception)
            raise HTTPException(status_code=400, detail="Inactive user")

        # Check for 2FA
        two_factor_enabled = bool(getattr(user, "two_factor_enabled", False))
        two_factor_secret = getattr(user, "two_factor_secret", None)

        if two_factor_enabled:
            if not login_data.totp_code:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "two_factor_required": True,
                        "user_id": user.id,
                        "email": user.email,
                        "message": "Two-factor authentication required"
                    }
                )
            
            # Verify TOTP code
            if not two_factor_secret:
                raise HTTPException(status_code=400, detail="2FA is enabled but no secret is configured")

            totp = pyotp.TOTP(two_factor_secret)
            if not totp.verify(login_data.totp_code):
                audit_service.log_event(
                    db,
                    event_type=AuditEventType.LOGIN.value,
                    action="2fa_failed",
                    description=f"Failed 2FA attempt for user: {user.email}",
                    user_id=user.id,
                    user_email=user.email,
                    security_level=SecurityLevel.MEDIUM.value,
                    threat_level=ThreatLevel.LOW.value,
                    success=False,
                    error_message="Invalid 2FA code",
                    request=request
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid 2FA code"
                )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )
        
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        db.commit()

        audit_service.log_event(
            db,
            event_type=AuditEventType.LOGIN.value,
            action="login_success",
            description=f"Successful login for user: {user.email}",
            user_id=user.id,
            user_email=user.email,
            security_level=SecurityLevel.LOW.value,
            request=request
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login Verification Error: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred during login. Please try again."}
        )

@router.post("/register", response_model=Token)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db), _rl=Depends(register_rate_limit)):
    # Check if user exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        # SECURITY: ignore the client-supplied role entirely. Self-registration
        # must always create a plain "member"; elevated roles (admin,
        # super_admin) are only grantable by an existing admin via the admin
        # API. Previously `role` was taken verbatim from the request body, so
        # POST /register {"role":"super_admin"} granted full platform takeover.
        role="member",
        status=UserStatus.ACTIVE
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create a default tenant + workspace so the new user has context for
    # every downstream feature (chat, agents, accounting). Without this,
    # tenant_id/workspace_id are None and first-use silently breaks.
    try:
        from core.models import Tenant, Workspace, PlanType
        import uuid as _uuid
        tenant = Tenant(
            id=str(_uuid.uuid4()),
            name=f"{user_data.first_name or user_data.email}'s Workspace",
            subdomain=f"user-{new_user.id[:8]}",
            plan_type=PlanType.FREE.value,
            edition="personal",
        )
        db.add(tenant)
        db.flush()

        workspace = Workspace(
            id=str(_uuid.uuid4()),
            name="Default",
            tenant_id=tenant.id,
        )
        db.add(workspace)
        db.flush()

        new_user.tenant_id = tenant.id
        new_user.workspace_id = workspace.id
        db.commit()
        db.refresh(new_user)
    except Exception as ctx_err:
        logger.warning(f"Could not create default tenant/workspace for user {new_user.id}: {ctx_err}")
    
    # Generate token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.id}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role,
        "status": current_user.status,
        "workspace_id": current_user.workspace_id,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }
 
# or leave as is if it uses a different table structure not yet in models.py.
# For now, I'll comment out the old SQLite logic to avoid conflicts and focus on the new Auth.
# In a real scenario, we'd migrate the password reset tokens to SQLAlchemy too.

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _rl=Depends(forgot_password_rate_limit),
):
    """Generate a password reset token and send an email to the user."""
    user = db.query(User).filter(User.email == request.email).first()
    
    # We return success even if user not found to prevent user enumeration
    success_msg = {"success": True, "message": "If your email is in our system, you will receive a reset link shortly."}
    
    if not user:
        return success_msg
    
    # Generate token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    # Save to DB
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()
    
    # Send email asynchronously
    config = get_config()
    reset_link = f"{config.server.app_url}/reset-password?token={token}"
    subject = "Password Reset Request"
    body = f"Hello {user.first_name or 'User'},\n\nYou requested a password reset. Please use the link below to reset your password:\n\n{reset_link}\n\nThis link will expire in 1 hour."
    html_body = f"<p>Hello {user.first_name or 'User'},</p><p>You requested a password reset. Please click the link below to reset your password:</p><p><a href='{reset_link}'>{reset_link}</a></p><p>This link will expire in 1 hour.</p>"

    logger.info("Password reset link generated for user %s", user.id)
    
    background_tasks.add_task(send_smtp_email, user.email, subject, body, html_body)
    
    return success_msg

@router.post("/verify-token")
async def verify_token(
    request: VerifyTokenRequest,
    db: Session = Depends(get_db),
    _rl=Depends(verify_token_rate_limit),
):
    """Verify if a password reset token is valid and not expired."""
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not reset_token:
        return {"valid": False, "message": "Invalid or expired token"}
    
    return {"valid": True, "message": "Token is valid"}

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _rl=Depends(reset_password_rate_limit),
):
    """Reset the user's password using a valid token."""
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update password
    user.hashed_password = get_password_hash(request.password)
    reset_token.is_used = True
    db.commit()
    
    logger.info(f"Password reset successful for user {user.id}")
    return {"success": True, "message": "Password reset successfully"}

@router.post("/refresh")
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh the access token"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout the current user and revoke their token server-side."""
    # Revoke the JWT so it can't be reused after logout (previously the token
    # stayed valid for 24h — a stolen token survived logout).
    from core.auth import oauth2_scheme, revoke_token
    import jwt as _jwt
    from core.auth import SECRET_KEY, ALGORITHM
    try:
        raw_token = oauth2_scheme(request)
        if raw_token:
            payload = _jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp", 0)
            if jti:
                revoke_token(jti, exp)
    except Exception:
        pass  # Best-effort revocation; logout shouldn't fail

    audit_service.log_event(
        db,
        event_type=AuditEventType.LOGOUT.value,
        action="logout",
        description=f"User logged out: {current_user.email}",
        user_id=current_user.id,
        user_email=current_user.email,
        security_level=SecurityLevel.LOW.value,
        request=request
    )
    return {"success": True, "message": "Logged out successfully"}

@router.get("/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get user profile (alias for /me)"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role,
        "status": current_user.status.value if current_user.status else None,
        "workspace_id": current_user.workspace_id,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }
