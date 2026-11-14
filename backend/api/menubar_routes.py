"""
Menu Bar Companion API Routes

HTTP surface for the macOS menu bar companion (``menubar/``). The native client
contracts live in ``menubar/src-tauri/src/commands.rs``:

- ``POST /api/menubar/auth/login``   → ``MenuBarLoginResponse``
- ``GET  /api/menubar/status``      → ``ConnectionStatus``
- ``GET  /api/menubar/recent``      → ``RecentItemsResponse``
- ``POST /api/menubar/quick/chat``  → ``QuickChatResponse``

The original router was deleted in 8bf4e3237 as "dead" because it had never
been mounted.  This is a rewrite against the CURRENT shared services, not a
restore of that code:

- Authentication goes through the same primitives as ``/api/auth/login``:
  ``verify_password``, active-account enforcement, the ``login_rate_limit``
  dependency, ``create_access_token(..., user=user)`` (which adds the
  credential-binding claim ``get_current_user`` requires) and
  ``register_session`` inventory. An enabled second factor is verified through
  ``core.auth_2fa_write_service.verify_login_totp_verified`` — the shared
  time-step replay fence, not a local ``pyotp`` check.
- Sign-in is the only companion path that runs before a bearer exists, so it is
  the one exact-path CSRF credential-exchange exception (mirroring
  ``/api/auth/login``). Every other companion mutation keeps the normal check.
- Reads are scoped by the current principal's workspace/tenant using the same
  visibility rules as ``api.agent_routes`` and
  ``core.agent_governance_service.agent_workspace_scope_condition``.
- Quick chat reuses ``core.agent_execution_service.execute_agent_chat`` — the
  central agent-chat path (also used by mobile/web) — after a scoped agent
  lookup and a real ``AgentGovernanceService`` decision. No response is
  fabricated here.
- Devices are always looked up with ``user_id == current_user.id``; an
  ``X-Device-ID`` belonging to another account is treated as unknown.

The WebSocket surface is deliberately out of scope (owned by the menubar WS
client and the device websocket router).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.agent_governance_service import (
    AgentGovernanceService,
    agent_workspace_scope_condition,
)
from core.auth import create_access_token, verify_password
from core.auth_2fa_write_service import verify_login_totp_verified
from core.database import get_db
from core.deployment_audience import require_pilot_user
from core.models import (
    AgentExecution,
    AgentRegistry,
    CanvasAudit,
    DeviceNode,
    MenuBarAudit,
    User,
    UserStatus,
)
from core.personal_scope import (
    PERSONAL_TENANT_ID,
    PERSONAL_WORKSPACE_ID,
    resolve_tenant_id,
    resolve_workspace_id,
)
from core.rbac_service import Permission
from core.security.auth_rate_limit import login_rate_limit
from core.security_dependencies import require_permission
from tools.canvas_crud_tool import _EVENT_ONLY_ACTIONS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/menubar", tags=["menubar"])

# Maturity bands that are live (not paused/stopped/deleted). Case-insensitive
# matching is deliberate: ``AgentStatus`` values are lowercase, while some
# historical API writes stored uppercase names.
_ACTIVE_MATURITY_LEVELS = ("student", "intern", "supervised", "autonomous")

# Governance complexity for quick chat defaults to 2 (INTERN). Auto-select
# prefers the most mature agent, mirroring the removed router's intent without
# its global (unscoped) query.
_AUTO_SELECT_LEVELS = ("autonomous", "supervised", "intern")


# ============================================================================
# Pydantic models — field names mirror commands.rs
# ============================================================================


class MenuBarUser(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str


class MenuBarLoginRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., max_length=128)  # bcrypt CPU-exhaustion guard
    device_name: str = Field(default="MenuBar", max_length=200)
    platform: str = Field(default="darwin", max_length=50)
    app_version: Optional[str] = Field(default=None, max_length=50)
    totp_code: Optional[str] = Field(default=None, max_length=10)


class MenuBarLoginResponse(BaseModel):
    success: bool
    access_token: Optional[str] = None
    device_id: Optional[str] = None
    user: Optional[MenuBarUser] = None
    error: Optional[str] = None
    #: Present only when the password was accepted but a second factor is
    #: still required. The companion retries the same request with totp_code.
    two_factor_required: Optional[bool] = None


class MenuBarAgentSummary(BaseModel):
    id: str
    name: str
    maturity_level: str
    status: str
    last_execution: Optional[datetime] = None
    execution_count: int = 0


class MenuBarCanvasSummary(BaseModel):
    id: str
    canvas_type: str
    created_at: datetime
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None


class RecentItemsResponse(BaseModel):
    agents: List[MenuBarAgentSummary]
    canvases: List[MenuBarCanvasSummary]


class ConnectionStatusResponse(BaseModel):
    status: str  # connected, disconnected, error
    device_id: Optional[str] = None
    last_seen: Optional[datetime] = None
    server_time: datetime


class QuickChatRequest(BaseModel):
    message: str = Field(..., max_length=8000)
    agent_id: Optional[str] = Field(default=None, max_length=100)
    session_id: Optional[str] = Field(default=None, max_length=255)
    context: Optional[Dict[str, Any]] = None


class QuickChatResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    execution_id: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# Scope helpers
# ============================================================================


def _utcnow() -> datetime:
    """Naive UTC, matching the timestamps SQLite returns for these columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_scope(user: User) -> tuple[str, str]:
    """Resolve the authenticated user's workspace/tenant once per request.

    ``resolve_*`` is the Personal-Edition single source of truth and handles
    bootstrap users whose ``workspace_id``/``tenant_id`` are NULL.
    """
    return resolve_workspace_id(user), resolve_tenant_id(user)


def _legacy_or_exact(column, value: str):
    """Match an exact scope plus the documented Personal-Edition aliases.

    Mirrors ``api.agent_routes._legacy_or_exact``: NULL/""/"default" are the
    shared single-tenant rows; a contradictory real value never matches.
    """
    return or_(
        column.is_(None),
        column == "",
        column == PERSONAL_TENANT_ID,
        column == value,
    )


def _agent_visibility(
    workspace_id: str, tenant_id: str, user_id: Optional[str] = None
):
    """Agents visible to one authenticated scope.

    Workspace visibility is the shared governance rule; the tenant predicate
    keeps a real multi-tenant row from leaking across tenants. When
    ``user_id`` is supplied, another user's private agent is excluded even
    inside the same workspace — only the caller's own agents, shared system
    agents, and legacy unowned (``user_id IS NULL``) registry rows remain.
    """
    conditions = [
        agent_workspace_scope_condition(workspace_id),
        _legacy_or_exact(AgentRegistry.tenant_id, tenant_id),
    ]
    if user_id is not None:
        conditions.append(
            or_(
                AgentRegistry.user_id == user_id,
                AgentRegistry.user_id.is_(None),
                AgentRegistry.is_system_agent.is_(True),
            )
        )
    return and_(*conditions)


def _execution_visibility(workspace_id: str, tenant_id: str):
    """Execution history frozen to the caller's scope.

    Mirrors ``api.agent_routes._execution_reader_condition``: a real workspace
    reads only rows stamped with it; the Personal-Edition default additionally
    accepts legacy NULL/"" rows.
    """
    if workspace_id == PERSONAL_WORKSPACE_ID:
        workspace_condition = or_(
            AgentExecution.workspace_id.is_(None),
            AgentExecution.workspace_id == "",
            AgentExecution.workspace_id == workspace_id,
        )
    else:
        workspace_condition = AgentExecution.workspace_id == workspace_id
    return and_(
        workspace_condition,
        _legacy_or_exact(AgentExecution.tenant_id, tenant_id),
    )


def _owned_menubar_device(
    db: Session, user: User, device_id: Optional[str]
) -> Optional[DeviceNode]:
    """Return the caller's own menubar device; never another account's.

    Ownership is ``user_id`` equality, the same check the device capability
    API uses. ``app_type`` narrows this to the menu bar companion.
    """
    if not device_id:
        return None
    return (
        db.query(DeviceNode)
        .filter(
            DeviceNode.device_id == device_id,
            DeviceNode.app_type == "menubar",
            DeviceNode.user_id == str(user.id),
        )
        .first()
    )


def _record_menubar_audit(db: Session, **fields: Any) -> None:
    """Best-effort MenuBarAudit write.

    Auditing must never turn a completed sign-in/chat into an error, so a
    failure is logged and rolled back. Callers commit their own durable work
    first.
    """
    try:
        db.add(MenuBarAudit(**fields))
        db.commit()
    except Exception as exc:  # noqa: BLE001 — audit is best-effort
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning(
            "Menu bar audit write failed action=%s error_class=%s",
            fields.get("action"),
            type(exc).__name__,
        )


def _record_login_audit_failure(
    db: Session,
    *,
    user: Optional[User],
    email: str,
    request: Request,
    platform: Optional[str],
    error_message: str,
) -> None:
    """Audit a failed login.

    ``MenuBarAudit.user_id`` is NOT NULL, so an unknown email cannot be written
    there. It goes to the shared authentication audit ledger instead, which
    accepts an email without a resolved principal.
    """
    if user is not None:
        _record_menubar_audit(
            db,
            tenant_id=getattr(user, "tenant_id", None),
            user_id=str(user.id),
            action="login",
            endpoint="/api/menubar/auth/login",
            request_params={"email": email},
            success=False,
            error_message=error_message,
            platform=platform,
            ip_address=request.client.host if request.client else None,
        )
        return

    try:
        from core.audit_service import audit_service
        from core.models import AuditEventType, SecurityLevel, ThreatLevel

        audit_service.log_event(
            db,
            event_type=AuditEventType.LOGIN.value,
            action="login_failed",
            description="Failed menu bar login attempt",
            user_email=email,
            security_level=SecurityLevel.MEDIUM.value,
            threat_level=ThreatLevel.LOW.value,
            success=False,
            error_message=error_message,
            request=request,
        )
    except Exception as exc:  # noqa: BLE001 — audit is best-effort
        logger.warning(
            "Menu bar login failure audit unavailable error_class=%s",
            type(exc).__name__,
        )


# ============================================================================
# Authentication
# ============================================================================


@router.post("/auth/login", response_model=MenuBarLoginResponse)
async def menubar_login(
    request: Request,
    payload: MenuBarLoginRequest,
    x_platform: Optional[str] = Header(None),
    _rl: Any = Depends(login_rate_limit),
    db: Session = Depends(get_db),
):
    """Authenticate the companion and mint a device-bound session token.

    Unauthenticated by design (it *is* the credential exchange), but it uses
    the shared login primitives — rate limiting, password verification, active
    status, 2FA, credential-bound JWT, durable session inventory.
    """
    email = (payload.email or "").strip()
    platform = (payload.platform or x_platform or "darwin").strip() or "darwin"
    client_ip = request.client.host if request.client else None

    user: Optional[User] = None
    try:
        user = db.query(User).filter(User.email == email).first()

        if user is None or not verify_password(payload.password, user.hashed_password):
            _record_login_audit_failure(
                db,
                user=user,
                email=email,
                request=request,
                platform=platform,
                error_message="Invalid email or password",
            )
            # Deliberately identical for unknown email and bad password.
            return MenuBarLoginResponse(
                success=False, error="Invalid email or password"
            )

        if user.status != UserStatus.ACTIVE or not bool(user.is_active):
            _record_login_audit_failure(
                db,
                user=user,
                email=email,
                request=request,
                platform=platform,
                error_message="Account is not active",
            )
            return MenuBarLoginResponse(success=False, error="Account is not active")

        # Same deployment-audience boundary the protected routes enforce via
        # require_pilot_user — do not mint a session the companion can never use.
        from core.deployment_audience import is_single_user, pilot_email

        if is_single_user() and (user.email or "").strip().lower() != pilot_email():
            _record_login_audit_failure(
                db,
                user=user,
                email=email,
                request=request,
                platform=platform,
                error_message="Not the declared single-user pilot account",
            )
            return MenuBarLoginResponse(
                success=False,
                error="This deployment is a single-user pilot; this account is not the declared owner",
            )

        # Honor an enabled second factor through the shared replay-fenced TOTP
        # verifier. It consumes the accepted time-step with the same
        # conditional write the canonical 2FA mutations use, so a code that
        # signed in once can never sign in again. Missing/invalid/replayed
        # codes all fail closed.
        if bool(getattr(user, "two_factor_enabled", False)):
            totp_result = verify_login_totp_verified(
                user=user, code=payload.totp_code, db=db
            )
            if str(totp_result.get("status") or "") != "verified":
                error_code = str(totp_result.get("error_code") or "")
                if error_code == "CONFLICT":
                    message = "This two-factor code has already been used"
                elif error_code == "INVALID_2FA_CODE":
                    message = "Invalid two-factor code"
                elif error_code == "PERMISSION_DENIED":
                    message = "Account is not active"
                elif error_code == "TWO_FACTOR_UNAVAILABLE":
                    message = "Two-factor authentication is not configured"
                elif error_code == "TWO_FACTOR_REQUIRED":
                    message = "Two-factor authentication required"
                else:
                    # effect_unknown / unexpected: never retry a code blindly.
                    message = "Unable to verify two-factor authentication"
                _record_login_audit_failure(
                    db,
                    user=user,
                    email=email,
                    request=request,
                    platform=platform,
                    error_message=message,
                )
                return MenuBarLoginResponse(
                    success=False,
                    error=message,
                    two_factor_required=(
                        error_code in {
                            "TWO_FACTOR_REQUIRED",
                            "INVALID_2FA_CODE",
                            "CONFLICT",
                        }
                    ),
                )

        workspace_id, _tenant_id = _user_scope(user)
        device_id = f"menubar_{user.id}_{platform}"

        device = (
            db.query(DeviceNode)
            .filter(
                DeviceNode.device_id == device_id,
                DeviceNode.user_id == str(user.id),
            )
            .first()
        )
        if device is None:
            device = DeviceNode(
                device_id=device_id,
                name=payload.device_name or "MenuBar",
                platform=platform,
                app_version=payload.app_version,
                node_type=(
                    "desktop_mac" if platform == "darwin" else f"desktop_{platform}"
                ),
                app_type="menubar",
                status="online",
                last_seen=_utcnow(),
                capabilities=["quick_chat", "notification", "hotkey"],
                workspace_id=workspace_id,
                tenant_id=getattr(user, "tenant_id", None),
                user_id=str(user.id),
            )
            db.add(device)
        else:
            device.name = payload.device_name or device.name
            device.platform = platform
            if payload.app_version:
                device.app_version = payload.app_version
            device.app_type = "menubar"
            device.status = "online"
            device.last_seen = _utcnow()
            device.workspace_id = workspace_id
            device.tenant_id = getattr(user, "tenant_id", None)
        db.commit()
        db.refresh(device)

        # ``user=user`` is mandatory: get_current_user rejects tokens without
        # the credential-binding claim (credential_session_matches).
        access_token = create_access_token(
            data={"sub": str(user.id)}, user=user
        )

        user.last_login = _utcnow()
        db.commit()

        # Inventory row for Settings → Active Sessions (best effort inside).
        try:
            from core.session_registry import register_session

            register_session(db, user, access_token, request=request)
        except Exception as exc:  # noqa: BLE001 — inventory never blocks login
            logger.warning(
                "Menu bar session inventory unavailable error_class=%s",
                type(exc).__name__,
            )

        _record_menubar_audit(
            db,
            tenant_id=getattr(user, "tenant_id", None),
            user_id=str(user.id),
            device_id=device_id,
            action="login",
            endpoint="/api/menubar/auth/login",
            request_params={"email": email},
            response_summary={"device_id": device_id},
            success=True,
            platform=platform,
            ip_address=client_ip,
        )

        logger.info("Menu bar login succeeded for user=%s device=%s", user.id, device_id)
        return MenuBarLoginResponse(
            success=True,
            access_token=access_token,
            device_id=device_id,
            user=MenuBarUser(
                id=str(user.id),
                email=user.email,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
            ),
        )

    except Exception as exc:  # noqa: BLE001 — never leak internals to the client
        logger.error(
            "Menu bar login failed error_class=%s", type(exc).__name__, exc_info=True
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        _record_login_audit_failure(
            db,
            user=user,
            email=email,
            request=request,
            platform=platform,
            error_message="Internal login error",
        )
        return MenuBarLoginResponse(
            success=False, error="Unable to complete sign-in"
        )


# ============================================================================
# Connection status
# ============================================================================


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    x_device_id: Optional[str] = Header(None),
    current_user: User = Depends(require_pilot_user),
    db: Session = Depends(get_db),
):
    """Report (and refresh) this companion's connection state.

    A missing or foreign device id is reported as ``disconnected`` — no
    existence oracle and no last_seen write against another user's device.
    """
    try:
        device = _owned_menubar_device(db, current_user, x_device_id)
        if device is None:
            return ConnectionStatusResponse(
                status="disconnected", server_time=_utcnow()
            )

        device.last_seen = _utcnow()
        device.status = "online"
        db.commit()
        return ConnectionStatusResponse(
            status="connected",
            device_id=device.device_id,
            last_seen=device.last_seen,
            server_time=_utcnow(),
        )
    except Exception as exc:  # noqa: BLE001 — contract has an "error" state
        logger.error(
            "Menu bar status check failed error_class=%s", type(exc).__name__
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return ConnectionStatusResponse(status="error", server_time=_utcnow())


# ============================================================================
# Recent items
# ============================================================================


def _recent_agents(
    db: Session, current_user: User, limit: int
) -> List[MenuBarAgentSummary]:
    workspace_id, tenant_id = _user_scope(current_user)

    rows = (
        db.query(
            AgentRegistry.id,
            AgentRegistry.name,
            AgentRegistry.status,
            func.max(AgentExecution.started_at).label("last_execution"),
            func.count(AgentExecution.id).label("execution_count"),
        )
        .join(AgentExecution, AgentRegistry.id == AgentExecution.agent_id)
        .filter(
            _agent_visibility(workspace_id, tenant_id, str(current_user.id)),
            _execution_visibility(workspace_id, tenant_id),
            func.lower(AgentRegistry.status).in_(_ACTIVE_MATURITY_LEVELS),
            or_(AgentRegistry.enabled.is_(None), AgentRegistry.enabled.is_(True)),
        )
        .group_by(AgentRegistry.id, AgentRegistry.name, AgentRegistry.status)
        .order_by(func.max(AgentExecution.started_at).desc())
        .limit(limit)
        .all()
    )

    return [
        MenuBarAgentSummary(
            id=str(row.id),
            name=row.name,
            maturity_level=row.status or "unknown",
            status=row.status or "unknown",
            last_execution=row.last_execution,
            execution_count=int(row.execution_count or 0),
        )
        for row in rows
    ]


def _recent_canvases(
    db: Session, current_user: User, limit: int
) -> List[MenuBarCanvasSummary]:
    """Latest authoring event per canvas for this user, newest first.

    Ownership follows the canvas gallery: ``CanvasAudit.user_id`` on an
    authoring action (``_EVENT_ONLY_ACTIONS`` such as form submits never grant
    ownership). The tenant predicate prevents a shared audit table from
    crossing tenants.
    """
    workspace_id, tenant_id = _user_scope(current_user)

    row_number = (
        func.row_number()
        .over(
            partition_by=CanvasAudit.canvas_id,
            order_by=(CanvasAudit.created_at.desc(), CanvasAudit.id.desc()),
        )
        .label("rn")
    )
    latest = (
        db.query(CanvasAudit.id.label("audit_id"), row_number)
        .filter(
            CanvasAudit.user_id == str(current_user.id),
            CanvasAudit.action_type.notin_(_EVENT_ONLY_ACTIONS),
            _legacy_or_exact(CanvasAudit.tenant_id, tenant_id),
        )
        .subquery()
    )

    audits = (
        db.query(CanvasAudit)
        .join(latest, CanvasAudit.id == latest.c.audit_id)
        .filter(latest.c.rn == 1, CanvasAudit.action_type != "delete")
        .order_by(CanvasAudit.created_at.desc(), CanvasAudit.id.desc())
        .limit(limit)
        .all()
    )

    agent_ids = {audit.agent_id for audit in audits if audit.agent_id}
    agent_names: Dict[str, str] = {}
    if agent_ids:
        agent_names = dict(
            db.query(AgentRegistry.id, AgentRegistry.name)
            .filter(
                AgentRegistry.id.in_(agent_ids),
                _agent_visibility(workspace_id, tenant_id, str(current_user.id)),
            )
            .all()
        )

    summaries: List[MenuBarCanvasSummary] = []
    for audit in audits:
        if audit.created_at is None:  # legacy rows without a usable timestamp
            continue
        summaries.append(
            MenuBarCanvasSummary(
                id=str(audit.canvas_id),
                canvas_type=audit.canvas_type or "generic",
                created_at=audit.created_at,
                agent_id=str(audit.agent_id) if audit.agent_id else None,
                agent_name=agent_names.get(audit.agent_id),
            )
        )
    return summaries


@router.get("/recent/agents", response_model=List[MenuBarAgentSummary])
async def get_recent_agents(
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(require_pilot_user),
    _perm: User = Depends(require_permission(Permission.AGENT_VIEW)),
    db: Session = Depends(get_db),
):
    """Recently executed agents visible in the caller's workspace/tenant."""
    return _recent_agents(db, current_user, limit)


@router.get("/recent/canvases", response_model=List[MenuBarCanvasSummary])
async def get_recent_canvases(
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(require_pilot_user),
    db: Session = Depends(get_db),
):
    """The caller's most recently authored canvases."""
    return _recent_canvases(db, current_user, limit)


@router.get("/recent", response_model=RecentItemsResponse)
async def get_recent_items(
    agent_limit: int = Query(5, ge=1, le=20),
    canvas_limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(require_pilot_user),
    _perm: User = Depends(require_permission(Permission.AGENT_VIEW)),
    db: Session = Depends(get_db),
):
    """Both recent lists in a single companion poll."""
    return RecentItemsResponse(
        agents=_recent_agents(db, current_user, agent_limit),
        canvases=_recent_canvases(db, current_user, canvas_limit),
    )


# ============================================================================
# Quick chat
# ============================================================================


def _select_agent(
    db: Session, current_user: User, requested_agent_id: Optional[str]
) -> Optional[AgentRegistry]:
    """Resolve the requested agent inside the caller's scope.

    An explicit id outside the scope resolves to ``None`` (same observable
    result as a nonexistent id) instead of letting the execution service look
    it up globally.
    """
    workspace_id, tenant_id = _user_scope(current_user)
    visibility = _agent_visibility(
        workspace_id, tenant_id, str(current_user.id)
    )
    enabled = or_(AgentRegistry.enabled.is_(None), AgentRegistry.enabled.is_(True))

    if requested_agent_id:
        return (
            db.query(AgentRegistry)
            .filter(AgentRegistry.id == requested_agent_id, visibility, enabled)
            .first()
        )

    for maturity in _AUTO_SELECT_LEVELS:
        agent = (
            db.query(AgentRegistry)
            .filter(
                visibility,
                enabled,
                func.lower(AgentRegistry.status) == maturity,
            )
            .order_by(AgentRegistry.confidence_score.desc())
            .first()
        )
        if agent is not None:
            return agent
    return None


@router.post("/quick/chat", response_model=QuickChatResponse)
async def quick_chat(
    payload: QuickChatRequest,
    x_device_id: Optional[str] = Header(None),
    x_platform: Optional[str] = Header(None),
    current_user: User = Depends(require_pilot_user),
    _perm: User = Depends(require_permission(Permission.AGENT_RUN)),
    db: Session = Depends(get_db),
):
    """Send one message to a scoped agent through the shared chat service.

    Governance is evaluated BEFORE execution using the request's own DB
    session; the resulting decision is recorded in ``MenuBarAudit`` alongside
    the outcome. The response is whatever the real execution service returns —
    success or failure — never a synthesized reply.
    """
    message = (payload.message or "").strip()
    workspace_id, tenant_id = _user_scope(current_user)
    platform = x_platform
    audit_base = dict(
        tenant_id=getattr(current_user, "tenant_id", None),
        user_id=str(current_user.id),
        device_id=x_device_id,
        action="quick_chat",
        endpoint="/api/menubar/quick/chat",
        request_params={
            "message": message[:200],
            "agent_id": payload.agent_id,
        },
        platform=platform,
    )

    if not message:
        _record_menubar_audit(
            db, **audit_base, success=False, error_message="Message is required"
        )
        return QuickChatResponse(success=False, error="Message is required")

    agent = _select_agent(db, current_user, payload.agent_id)
    if agent is None:
        error = (
            "Agent not available"
            if payload.agent_id
            else "No agents available"
        )
        _record_menubar_audit(
            db, **audit_base, success=False, error_message=error
        )
        return QuickChatResponse(success=False, error=error)

    agent_id = str(agent.id)
    audit_base["agent_id"] = agent_id
    audit_base["agent_maturity"] = agent.status

    governance = AgentGovernanceService(
        db, workspace_id=workspace_id, tenant_id=tenant_id
    )
    decision = governance.can_perform_action(
        agent_id=agent_id,
        action_type="quick_chat",
        require_approval=False,
    )
    governance_allowed = bool(decision.get("allowed", False))
    audit_base["governance_check_passed"] = governance_allowed

    if not governance_allowed:
        reason = decision.get("reason") or "Governance policy denied this action"
        _record_menubar_audit(
            db,
            **audit_base,
            success=False,
            error_message=f"Governance blocked quick chat: {reason}",
        )
        return QuickChatResponse(
            success=False,
            error="Agent not authorized for quick chat",
            agent_id=agent_id,
        )

    # Touch the caller's own device only (a foreign id was already ignored by
    # the ownership-scoped lookup inside this helper).
    device = _owned_menubar_device(db, current_user, x_device_id)
    if device is not None:
        device.last_command_at = _utcnow()
        device.last_seen = _utcnow()
        device.status = "online"
        try:
            db.commit()
        except Exception:  # noqa: BLE001 — device telemetry is not execution
            db.rollback()

    try:
        # Imported lazily so app boot does not pull the LLM stack for a router
        # that may be unused in headless deployments.
        from core.agent_execution_service import execute_agent_chat

        result = await execute_agent_chat(
            agent_id=agent_id,
            message=message,
            user_id=str(current_user.id),
            session_id=payload.session_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            stream=False,  # companion uses request/response; WS is separate
        )
    except Exception as exc:  # noqa: BLE001 — observed, audited, not leaked
        logger.error(
            "Menu bar quick chat failed error_class=%s", type(exc).__name__,
            exc_info=True,
        )
        _record_menubar_audit(
            db,
            **audit_base,
            success=False,
            error_message=f"Execution error: {type(exc).__name__}",
        )
        return QuickChatResponse(
            success=False,
            error="Agent execution failed",
            agent_id=agent_id,
        )

    if not result.get("success"):
        error = result.get("error") or "Agent execution failed"
        _record_menubar_audit(
            db,
            **audit_base,
            agent_execution_id=result.get("execution_id"),
            success=False,
            error_message=str(error),
        )
        return QuickChatResponse(
            success=False,
            error=str(error),
            agent_id=agent_id,
        )

    response_text = result.get("response") or ""
    _record_menubar_audit(
        db,
        **audit_base,
        agent_execution_id=result.get("execution_id"),
        success=True,
        response_summary={"response_length": len(response_text)},
    )
    return QuickChatResponse(
        success=True,
        response=response_text,
        execution_id=result.get("execution_id"),
        agent_id=str(result.get("agent_id") or agent_id),
        session_id=result.get("session_id"),
    )


# ============================================================================
# Health
# ============================================================================


@router.get("/health")
async def menubar_health():
    """Unauthenticated liveness probe for the companion."""
    return {"status": "healthy", "timestamp": _utcnow().isoformat()}
