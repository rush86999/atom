import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.audit_service import audit_service
from core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from core.database import get_db
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

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str

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
    db: Session = Depends(get_db)
):
    import traceback
    import pyotp
    from fastapi.responses import JSONResponse
    try:
        user = db.query(User).filter(User.email == login_data.username).first()
        if not user or not verify_password(login_data.password, user.password_hash):
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
        if user.two_factor_enabled:
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
            totp = pyotp.TOTP(user.two_factor_secret)
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
        user.last_login = datetime.utcnow()
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
            content={
                "detail": "Internal Server Error", 
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.post("/register", response_model=Token)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        status=UserStatus.ACTIVE
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
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
async def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Generate a password reset token and send an email to the user."""
    user = db.query(User).filter(User.email == request.email).first()
    
    # We return success even if user not found to prevent user enumeration
    success_msg = {"success": True, "message": "If your email is in our system, you will receive a reset link shortly."}
    
    if not user:
        return success_msg
    
    # Generate token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Save to DB
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()
    
    # Send email asynchronously
    reset_link = f"https://atom.app/reset-password?token={token}" # Placeholder domain
    subject = "Password Reset Request"
    body = f"Hello {user.first_name or 'User'},\n\nYou requested a password reset. Please use the link below to reset your password:\n\n{reset_link}\n\nThis link will expire in 1 hour."
    html_body = f"<p>Hello {user.first_name or 'User'},</p><p>You requested a password reset. Please click the link below to reset your password:</p><p><a href='{reset_link}'>{reset_link}</a></p><p>This link will expire in 1 hour.</p>"
    
    background_tasks.add_task(send_smtp_email, user.email, subject, body, html_body)
    
    return success_msg

@router.post("/verify-token")
async def verify_token(request: VerifyTokenRequest, db: Session = Depends(get_db)):
    """Verify if a password reset token is valid and not expired."""
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()
    
    if not reset_token:
        return {"valid": False, "message": "Invalid or expired token"}
    
    return {"valid": True, "message": "Token is valid"}

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset the user's password using a valid token."""
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()
    
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update password
    user.password_hash = get_password_hash(request.password)
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
    """Logout the current user (client should discard token)"""
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

