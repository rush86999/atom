"""Thin integration router for stripe.

Auto-generated to expose the existing StripeAdapter service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
stripe_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.connection_service import connection_service
from core.database import get_db
from core.integrations.adapters.stripe import StripeAdapter
from core.models import Tenant, User, UserRole, Workspace
from core.security.rbac import user_meets_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/stripe", tags=["stripe"])

_STRIPE_ACCOUNT_URL = "https://api.stripe.com/v1/account"
_STRIPE_TIMEOUT_SECONDS = 10.0
_STRIPE_INTEGRATION_ID = "stripe"
_RESTRICTED_KEY_RE = re.compile(r"rk_(test|live)_[A-Za-z0-9_]+")
_STRIPE_ACCOUNT_ID_RE = re.compile(r"acct_[A-Za-z0-9]+")


@dataclass(frozen=True)
class _WorkspaceScope:
    user_id: str
    tenant_id: str
    workspace_id: str


@dataclass(frozen=True)
class _SetupInput:
    restricted_key: str
    account_id: str
    mode: str


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _current_user_id(current_user: Any) -> str:
    """Read the actor only from the authenticated principal, never from input."""
    if isinstance(current_user, dict):
        raw_id = current_user.get("id")
    else:
        raw_id = getattr(current_user, "id", None)
    if not _nonempty_str(raw_id):
        raise HTTPException(status_code=401, detail="Authentication required")
    return raw_id.strip()


def _resolve_active_workspace_admin_scope(
    db: Session, user_id: str
) -> _WorkspaceScope:
    """Resolve the actor's current active tenant/workspace admin scope from DB rows."""
    user = db.query(User).filter(User.id == user_id).first()
    if (
        user is None
        or not bool(getattr(user, "is_active", False))
        or getattr(user, "status", None) != "active"
        or not user_meets_role(user, UserRole.WORKSPACE_ADMIN)
    ):
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    tenant_id = getattr(user, "tenant_id", None)
    workspace_id = getattr(user, "workspace_id", None)
    if not _nonempty_str(tenant_id) or not _nonempty_str(workspace_id):
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )
    tenant_id = tenant_id.strip()
    workspace_id = workspace_id.strip()

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None or not bool(getattr(tenant, "is_active", False)):
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.tenant_id == tenant_id,
    ).first()
    if workspace is None or getattr(workspace, "status", None) != "active":
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    return _WorkspaceScope(
        user_id=user_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )


async def _parse_setup_input(request: Request) -> _SetupInput:
    """Validate manually so rejected secrets never reach validation error bodies."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid request")

    raw_key = payload.get("restricted_key")
    raw_account_id = payload.get("account_id")
    if not isinstance(raw_key, str) or not isinstance(raw_account_id, str):
        raise HTTPException(status_code=400, detail="Invalid request")

    restricted_key = raw_key.strip()
    account_id = raw_account_id.strip()
    if not _RESTRICTED_KEY_RE.fullmatch(restricted_key):
        raise HTTPException(status_code=400, detail="Invalid request")
    if not _STRIPE_ACCOUNT_ID_RE.fullmatch(account_id):
        raise HTTPException(status_code=400, detail="Invalid request")

    # The mode is pinned solely by the restricted-key prefix. No provider
    # permissions or write scope are inferred from the key.
    mode = "test" if restricted_key.startswith("rk_test_") else "live"
    return _SetupInput(
        restricted_key=restricted_key,
        account_id=account_id,
        mode=mode,
    )


async def _fetch_stripe_account(restricted_key: str) -> Dict[str, Any]:
    """Perform exactly one fixed Stripe GET; never follow redirects."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=_STRIPE_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(
                _STRIPE_ACCOUNT_URL,
                headers={"Authorization": f"Bearer {restricted_key}"},
            )
    except Exception as exc:
        logger.warning(
            "Stripe account verification request failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )

    if response.status_code != 200:
        logger.warning(
            "Stripe account verification failed with status %s",
            response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )

    try:
        data = response.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail="Stripe account verification failed",
        )
    return data


@router.post("/invoice-connection")
async def create_invoice_connection(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a scoped Stripe connection from a verified account restricted key."""
    actor_id = _current_user_id(current_user)

    # Resolve the scope before provider I/O, then prove it is still the same
    # active scope afterwards. None of these values come from the request body.
    initial_scope = _resolve_active_workspace_admin_scope(db, actor_id)
    setup = await _parse_setup_input(request)

    account = await _fetch_stripe_account(setup.restricted_key)
    returned_account_id = account.get("id")
    if returned_account_id != setup.account_id:
        raise HTTPException(
            status_code=400,
            detail="Stripe account verification failed",
        )

    # Force a fresh read so a role/tenant/workspace change committed while the
    # provider request was in flight cannot be hidden by the identity map.
    try:
        db.expire_all()
    except Exception as exc:
        logger.warning(
            "Stripe scope revalidation freshness check failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to verify workspace admin authorization",
        )
    rechecked_scope = _resolve_active_workspace_admin_scope(db, actor_id)
    if rechecked_scope != initial_scope:
        raise HTTPException(
            status_code=403,
            detail="Active workspace admin authorization required",
        )

    connection_id = str(uuid.uuid4())
    credentials = {
        "restricted_key": setup.restricted_key,
        "account_id": setup.account_id,
        "mode": setup.mode,
        "auth_type": "restricted_key",
    }

    try:
        created = connection_service.create_scoped_connection(
            user_id=initial_scope.user_id,
            tenant_id=initial_scope.tenant_id,
            workspace_id=initial_scope.workspace_id,
            integration_id=_STRIPE_INTEGRATION_ID,
            name=f"Stripe invoice connection ({setup.account_id})",
            credentials=credentials,
            connection_id=connection_id,
        )
    except Exception as exc:
        logger.warning(
            "Stripe scoped connection persistence failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to store Stripe connection",
        )

    if not created:
        raise HTTPException(
            status_code=409,
            detail="Unable to store Stripe connection",
        )

    return {
        "connection_id": connection_id,
        "account": setup.account_id,
        "mode": setup.mode,
    }


def _get_service(db: Session = None) -> StripeAdapter:
    """Build a StripeAdapter instance."""
    return StripeAdapter(db, workspace_id="default")


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the stripe integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "stripe service available (no health_check method)"}
    except Exception as exc:
        logger.warning("stripe health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this stripe service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


