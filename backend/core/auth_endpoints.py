from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import Optional
import uuid
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, update
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
from core.personal_scope import PERSONAL_TENANT_ID
from core.security.auth_rate_limit import (
    AuthRateLimiter,
    login_rate_limit,
    register_rate_limit,
)
from core.email_utils import send_smtp_email, smtp_delivery_configured
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
_password_change_limiter = AuthRateLimiter(limit=5, window_seconds=300)  # 5/5min (current-password guessing)


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

def _validate_password_bytes(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes when UTF-8 encoded")
    return password


class UserCreate(BaseModel):
    # SECURITY: email must be a well-formed address and password must meet the
    # same 8-char minimum the frontend enforces. Previously both were plain
    # `str`, so POST /register accepted "not-an-email" and 3-char passwords —
    # the backend is the enforcement boundary and cannot trust client-side checks.
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    # Names must be non-empty after stripping — whitespace-only values used to
    # pass validation and create accounts with blank display names.
    # R83: last_name is optional — a single-word name ("Plato") previously
    # guaranteed a 422 with no UI hint that two words were required.
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field("", max_length=100)
    role: str = "member"

    @field_validator("password")
    @classmethod
    def _check_password_bytes(cls, v: str) -> str:
        return _validate_password_bytes(v)

    @field_validator("first_name")
    @classmethod
    def _strip_names(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or whitespace-only")
        return stripped

    @field_validator("last_name")
    @classmethod
    def _strip_last_name(cls, v: str) -> str:
        return (v or "").strip()

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _check_password_bytes(cls, v: str) -> str:
        return _validate_password_bytes(v)

class VerifyTokenRequest(BaseModel):
    token: str

class ChangePasswordRequest(BaseModel):
    """Change password request (authenticated user).

    Field names match the frontend payload (settings/account.tsx sends
    current_password + new_password)."""
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_new_password_bytes(cls, v: str) -> str:
        return _validate_password_bytes(v)

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None

def change_password_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit POST /api/auth/change-password (5/5min/IP)."""
    allowed, _ = _password_change_limiter.check(request)
    if not allowed:
        logger.warning(
            "change-password rate limit exceeded for IP %s",
            _password_change_limiter._client_ip(request),
        )
        raise HTTPException(status_code=429, detail="Too many password change attempts. Please try again later.")


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
            data={"sub": user.id}, expires_delta=access_token_expires, user=user
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
    from core.deployment_audience import is_single_user
    if is_single_user():
        raise HTTPException(status_code=403, detail="Self-registration is disabled for this single-user pilot.")
    # Check if user exists
    # BUG FIX: compare emails case-insensitively — "USER@example.com" could
    # previously bypass the duplicate check and register a second account for
    # the same mailbox. Emails are stored lowercased to keep uniqueness
    # consistent.
    normalized_email = user_data.email.strip().lower()
    if db.query(User).filter(func.lower(User.email) == normalized_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    new_user = User(
        email=normalized_email,
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

        # ISOLATION (2026-10-11, journey J3): the workspace row alone is not
        # enough. Upload/search scope by the User.workspaces RELATIONSHIP
        # (secondary user_workspaces) — an empty association made
        # current_user.workspaces resolve [] for every registered user, so
        # their documents all landed in the shared "default_shared" LanceDB
        # store: any registered user could read any other's uploads. Populate
        # the association the same commit that sets users.workspace_id.
        new_user.workspaces.append(workspace)
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
        data={"sub": new_user.id}, expires_delta=access_token_expires, user=new_user
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

def _recovery_user_allowed(user, reset_token=None) -> bool:
    if user is None or not user.is_active:
        return False
    if getattr(user.status, "value", user.status) != UserStatus.ACTIVE.value:
        return False
    if not isinstance(user.hashed_password, str) or not user.hashed_password:
        return False
    return reset_token is None or reset_token.tenant_id == (user.tenant_id or PERSONAL_TENANT_ID)


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _rl=Depends(forgot_password_rate_limit),
):
    """Accept a recovery request using the existing SMTP transport."""
    # Global readiness precedes account lookup, so missing configuration cannot
    # distinguish an existing address or mint an unusable recovery credential.
    if not smtp_delivery_configured():
        raise HTTPException(status_code=503, detail="Password recovery email is unavailable. Ask the app administrator to configure delivery.")
    user = db.query(User).filter(User.email == request.email).first()
    
    # We return success even if user not found to prevent user enumeration
    success_msg = {"success": True, "message": "If the account is eligible, its recovery request has been accepted. Check your email for the next step."}
    
    if not _recovery_user_allowed(user):
        return success_msg
    
    # Serialize issuance with credential recovery. Freeze the current authority
    # before generating the credential; a peer reset/scope change must win.
    snapshot = {name: getattr(user, name) for name in (
        "id", "hashed_password", "tenant_id", "workspace_id", "email", "role", "status")}
    token = secrets.token_urlsafe(32)
    claim = db.execute(update(User).where(
        *(getattr(User, name) == value for name, value in snapshot.items()),
        User.is_active.is_(True),
    ).values(updated_at=User.updated_at).execution_options(synchronize_session=False))
    if claim.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Recovery authorization changed. Request a new reset link.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    # Save to DB (SHA-256 digest at rest — DB read does not yield usable tokens)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token_hash,
        tenant_id=user.tenant_id or PERSONAL_TENANT_ID,
        expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()
    
    # Send email asynchronously
    config = get_config()
    app_url = config.server.app_url.rstrip("/")
    reset_link = f"{app_url}/auth/reset-password?token={token}"
    subject = "Password Reset Request"
    # Escape user-controlled input to prevent stored XSS (CWE-79)
    import html as html_module
    safe_first_name = html_module.escape(user.first_name or 'User')
    body = f"Hello {safe_first_name},\n\nYou requested a password reset. Please use the link below to reset your password:\n\n{reset_link}\n\nThis link will expire in 1 hour."
    html_body = f"<p>Hello {safe_first_name},</p><p>You requested a password reset. Please click the link below to reset your password:</p><p><a href='{reset_link}'>{reset_link}</a></p><p>This link will expire in 1 hour.</p>"

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
        PasswordResetToken.token == token_hash,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()
    
    user = db.query(User).filter(User.id == reset_token.user_id).first() if reset_token else None
    if not reset_token or not _recovery_user_allowed(user, reset_token):
        return {"valid": False, "message": "Invalid or expired token"}
    
    return {"valid": True, "message": "Token is valid"}

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _rl=Depends(reset_password_rate_limit),
):
    """Consume one exact recovery token and update its current account atomically."""
    from fastapi.responses import JSONResponse
    from sqlalchemy.exc import IntegrityError
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token_hash,
        PasswordResetToken.used.is_(False),
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()
    user = db.query(User).filter(User.id == reset_token.user_id).first() if reset_token else None
    if not reset_token or not _recovery_user_allowed(user, reset_token):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Freeze scalar material BEFORE hashing. ORM instances may expire/reload
    # while a peer commits; they must never silently refresh our expectation.
    reset_id, user_id = reset_token.id, user.id
    expiry, token_tenant = reset_token.expires_at, reset_token.tenant_id
    old_hash, tenant, workspace = user.hashed_password, user.tenant_id, user.workspace_id
    email, role, user_status = user.email, user.role, user.status
    operation_id = "password-reset:" + str(reset_id)
    commit_attempted = commit_confirmed = False
    stage = "hash"
    try:
        new_hash = get_password_hash(request.password)
        if not verify_password(request.password, new_hash):
            raise ValueError("credential proof failed")
        stage = "claim"
        actor = db.execute(update(User).where(
            User.id == user_id, User.hashed_password == old_hash,
            User.tenant_id == tenant, User.workspace_id == workspace,
            User.email == email, User.role == role, User.status == user_status,
            User.is_active.is_(True),
        ).values(hashed_password=new_hash).execution_options(synchronize_session=False))
        if actor.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Recovery authorization changed. Request a new reset link.")
        token = db.execute(update(PasswordResetToken).where(
            PasswordResetToken.id == reset_id, PasswordResetToken.user_id == user_id,
            PasswordResetToken.token == token_hash, PasswordResetToken.tenant_id == token_tenant,
            PasswordResetToken.used.is_(False), PasswordResetToken.expires_at == expiry,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        ).values(used=True, used_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False))
        if token.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Reset link has changed or was already used. Request a new link.")
        # A successful recovery invalidates every other outstanding link.
        # Issuance claims this same account first, serializing concurrent writers.
        db.execute(update(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used.is_(False),
        ).values(used=True, used_at=datetime.now(timezone.utc))
          .execution_options(synchronize_session=False))
        # No dirty ORM assignment may issue an unconditional credential update.
        db.expire_all()
        stage = "commit"
        commit_attempted = True
        db.commit()
        commit_confirmed = True
        stage = "readback"
        with Session(bind=db.get_bind()) as fresh:
            current = fresh.get(User, user_id)
            receipt = fresh.get(PasswordResetToken, reset_id)
            verified = bool(current and receipt and receipt.used
                and receipt.user_id == user_id and receipt.tenant_id == token_tenant
                and _recovery_user_allowed(current, receipt)
                and current.tenant_id == tenant and current.workspace_id == workspace
                and current.email == email and current.role == role
                and current.hashed_password == new_hash
                and verify_password(request.password, current.hashed_password))
        if not verified:
            raise ValueError("credential readback mismatch")
        return {"success": True, "message": "Password reset successfully. Sign in with your new password.",
                "operation_id": operation_id, "verification": {"status": "verified", "effect": "committed"}}
    except HTTPException:
        raise
    except Exception as error:
        rolled_back = False
        try:
            db.rollback()
            rolled_back = True
        except Exception:
            pass
        logger.warning("Password recovery failed stage=%s error_class=%s", stage, type(error).__name__)
        no_effect = not commit_confirmed and rolled_back and (not commit_attempted or isinstance(error, IntegrityError))
        effect = "none" if no_effect else "committed" if commit_confirmed else "unknown"
        return JSONResponse(status_code=409 if no_effect else 503, content={
            "success": False, "detail": "Password change could not be confirmed. Try signing in before requesting another reset.",
            "operation_id": operation_id, "replay": "do_not_repeat",
            "verification": {"status": "refused" if no_effect else "unavailable", "effect": effect},
        })

@router.post("/refresh")
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh the access token"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.id}, expires_delta=access_token_expires, user=current_user
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
        # NOTE: oauth2_scheme is async (OAuth2PasswordBearer.__call__) — the
        # missing `await` made `raw_token` a truthy coroutine, so decode always
        # failed and the bare except swallowed it: logout NEVER revoked the
        # token (24h reuse window). Wave-75 security bug.
        raw_token = await oauth2_scheme(request)
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

@router.post("/change-password")
async def change_password(
    request: Request,
    change_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl=Depends(change_password_rate_limit),
):
    """Change the authenticated user's password.

    Requires the current password. Credential-bound sessions all require a
    fresh sign-in after the committed change, including this browser. The
    existing token ledger is reconciled as well; it is not the revocation
    authority. Rate-limited to blunt current-password guessing.
    """
    from core.auth_helpers import revoke_all_user_tokens

    if not verify_password(change_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if verify_password(change_data.new_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="New password must be different from the current password")

    # Freeze the same credential/authority snapshot used by recovery. An
    # already-authenticated request must not overwrite a concurrent reset.
    snapshot = {name: getattr(current_user, name) for name in (
        "id", "hashed_password", "tenant_id", "workspace_id", "email", "role", "status")}
    new_hash = get_password_hash(change_data.new_password)
    if not verify_password(change_data.new_password, new_hash):
        raise HTTPException(status_code=409, detail="Password change refused. No credential was changed.")
    claim = db.execute(update(User).where(
        *(getattr(User, name) == value for name, value in snapshot.items()),
        User.is_active.is_(True),
    ).values(hashed_password=new_hash).execution_options(synchronize_session=False))
    if claim.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account changed. Sign in again before changing your password.")
    db.expire_all()
    db.commit()

    revoked = revoke_all_user_tokens(
        user_id=current_user.id,
        db=db,
        revocation_reason="password_change",
    )

    audit_service.log_event(
        db,
        event_type=AuditEventType.UPDATE.value,
        action="change_password",
        description="User changed their password",
        user_id=current_user.id,
        user_email=current_user.email,
        security_level=SecurityLevel.MEDIUM.value,
        request=request,
    )

    logger.info("Password changed for user %s (%d other sessions revoked)", current_user.id, revoked)
    return {"success": True, "message": "Password updated successfully. Sign in again with your new password.",
            "revoked_sessions": revoked, "requires_reauthentication": True}

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
