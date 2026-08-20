"""
SCIM v2 user provisioning routes (RFC 7644 subset used by Okta/Entra ID).

Endpoints under /api/scim/v2:
    GET    /Users            list (+ simple userName/email filter, pagination)
    GET    /Users/{id}       fetch
    POST   /Users            create (provisions like SSO auto-provisioning)
    PATCH  /Users/{id}       partial update (active, displayName)
    PUT    /Users/{id}       full replace (userName, name, active)
    DELETE /Users/{id}       deactivate (soft delete — never hard-delete)

Auth: dedicated bearer token from env ATOM_SCIM_TOKEN. If the env var is
unset, SCIM is disabled and every endpoint returns 503. Token comparison is
constant time (hmac.compare_digest), mirroring the SSO state-token check.

User model notes:
    - No externalId column exists on User, so externalId is accepted but
      not persisted.
    - Provisioning mirrors api/sso_oidc_routes.py: hashed_password=None,
      role=UserRole.MEMBER, status=UserStatus.ACTIVE, is_active=True,
      tenant_id=PERSONAL_TENANT_ID.
    - Soft delete follows platform conventions (is_active flag, as in
      tools/platform_management_tool.py) plus UserStatus.DELETED/SUSPENDED.
"""
import hmac
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User, UserRole, UserStatus
from core.personal_scope import PERSONAL_TENANT_ID

router = APIRouter(prefix="/api/scim/v2", tags=["SCIM v2"])

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


def scim_error(status_code: int, detail: str) -> Dict[str, Any]:
    return {
        "schemas": [SCIM_ERROR_SCHEMA],
        "status": str(status_code),
        "detail": detail,
    }


class ScimError(Exception):
    """Raised to emit a raw SCIM Error body (not wrapped in FastAPI's detail)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.body = scim_error(status_code, detail)


def install_scim_exception_handlers(app) -> None:
    """Register the SCIM Error handler on the FastAPI app (call from main app setup)."""

    @app.exception_handler(ScimError)
    async def _scim_error_handler(_req, exc: ScimError):
        return JSONResponse(status_code=exc.status_code, content=exc.body)


def _raise(status_code: int, detail: str) -> None:
    raise ScimError(status_code, detail)


def _scim_token() -> Optional[str]:
    token = os.getenv("ATOM_SCIM_TOKEN")
    return token if token else None


async def require_scim_token(request: Request) -> None:
    """Dependency enforcing the dedicated SCIM bearer token."""
    token = _scim_token()
    if not token:
        # SCIM provisioning disabled — surface as 503 with a SCIM Error body.
        _raise(503, "SCIM provisioning is disabled (ATOM_SCIM_TOKEN not configured)")
    auth = request.headers.get("Authorization") or ""
    supplied = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not supplied or not hmac.compare_digest(supplied, token):
        _raise(401, "Invalid or missing SCIM bearer token")


def _is_active(user: User) -> bool:
    return bool(user.is_active) and user.status != UserStatus.DELETED.value


def _scim_user(request: Request, user: User) -> Dict[str, Any]:
    return {
        "schemas": [SCIM_USER_SCHEMA],
        "id": user.id,
        "userName": user.email,
        "name": {
            "givenName": user.first_name or "",
            "familyName": user.last_name or "",
        },
        "displayName": " ".join(p for p in [user.first_name, user.last_name] if p),
        "active": _is_active(user),
        "meta": {"location": f"/api/scim/v2/Users/{user.id}"},
    }


_FILTER_RE = re.compile(
    r'^\s*(userName|emails(?:\.value)?(?:\[value\])?)\s+(eq|co)\s+"([^"]*)"\s*$',
    re.IGNORECASE,
)


def _apply_filter(query, filter_str: str):
    """Support only userName/email eq/co (case-insensitive value match)."""
    match = _FILTER_RE.match(filter_str or "")
    if not match:
        raise ValueError(f"Unsupported filter: {filter_str!r}")
    attr, op, value = match.groups()
    value = value.strip().lower()
    if attr.startswith("emails"):
        # emails.value is equivalent to userName for this platform (email login).
        pass
    if op.lower() == "eq":
        return query.filter(func.lower(User.email) == value)
    return query.filter(func.lower(User.email).like(f"%{value}%"))


def _get_user_or_none(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _apply_active(user: User, active: bool) -> None:
    if active:
        user.is_active = True
        user.status = UserStatus.ACTIVE.value
    else:
        user.is_active = False
        user.status = UserStatus.SUSPENDED.value


@router.get("/Users")
async def list_users(
    request: Request,
    startIndex: int = 1,
    count: int = 100,
    filter: Optional[str] = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_scim_token),
):

    query = db.query(User)
    if filter:
        try:
            query = _apply_filter(query, filter)
        except ValueError as exc:
            _raise(400, str(exc))
    users: List[User] = query.order_by(User.created_at, User.id).all()
    total = len(users)
    start = max(startIndex, 1)
    page = users[start - 1 : start - 1 + max(count, 0)]
    return {
        "schemas": [SCIM_LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start,
        "itemsPerPage": len(page),
        "Resources": [_scim_user(request, u) for u in page],
    }


@router.get("/Users/{user_id}")
async def get_user(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_scim_token),
):

    user = _get_user_or_none(db, user_id)
    if not user:
        _raise(404, "User not found")
    return _scim_user(request, user)


@router.post("/Users", status_code=201)
async def create_user(
    request: Request,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _: None = Depends(require_scim_token),
):

    user_name = (payload.get("userName") or "").strip().lower()
    if not user_name:
        _raise(400, "userName is required")

    existing = db.query(User).filter(func.lower(User.email) == user_name).first()
    if existing:
        _raise(409, "User already exists")

    name = payload.get("name") or {}
    active = payload.get("active", True)
    user = User(
        email=user_name,
        hashed_password=None,  # SCIM-provisioned users have no local password (same as SSO)
        first_name=(name.get("givenName") or "SCIM")[:255],
        last_name=(name.get("familyName") or "User")[:255],
        role=UserRole.MEMBER.value,
        tenant_id=PERSONAL_TENANT_ID,
    )
    _apply_active(user, bool(active))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _scim_user(request, user)


def _patch_user_fields(user: User, values: Dict[str, Any]) -> None:
    if "active" in values and values["active"] is not None:
        _apply_active(user, bool(values["active"]))
    if "displayName" in values and values["displayName"]:
        parts = str(values["displayName"]).strip().split(" ", 1)
        user.first_name = parts[0][:255]
        user.last_name = (parts[1] if len(parts) > 1 else "")[:255]


@router.patch("/Users/{user_id}")
async def patch_user(
    request: Request,
    user_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _: None = Depends(require_scim_token),
):

    user = _get_user_or_none(db, user_id)
    if not user:
        _raise(404, "User not found")

    operations = payload.get("Operations") or []
    if not isinstance(operations, list):
        _raise(400, "Operations must be a list")
    for op in operations:
        op_name = (op.get("op") or "replace").lower()
        if op_name != "replace":
            _raise(400, f"Unsupported patch op: {op_name!r}")
        path = (op.get("path") or "").strip()
        value = op.get("value")
        if path == "active":
            _apply_active(user, bool(value))
        elif path == "displayName":
            _patch_user_fields(user, {"displayName": value})
        elif not path and isinstance(value, dict):
            _patch_user_fields(user, value)
        elif path:
            _raise(400, f"Unsupported patch path: {path!r}")
    db.commit()
    db.refresh(user)
    return _scim_user(request, user)


@router.put("/Users/{user_id}")
async def replace_user(
    request: Request,
    user_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    _: None = Depends(require_scim_token),
):

    user = _get_user_or_none(db, user_id)
    if not user:
        _raise(404, "User not found")

    user_name = (payload.get("userName") or "").strip().lower()
    if user_name and user_name != user.email.lower():
        clash = db.query(User).filter(func.lower(User.email) == user_name).first()
        if clash and clash.id != user.id:
            _raise(409, "userName already in use")
        user.email = user_name
    name = payload.get("name") or {}
    if name.get("givenName"):
        user.first_name = str(name["givenName"])[:255]
    if name.get("familyName"):
        user.last_name = str(name["familyName"])[:255]
    if "active" in payload and payload["active"] is not None:
        _apply_active(user, bool(payload["active"]))
    db.commit()
    db.refresh(user)
    return _scim_user(request, user)


@router.delete("/Users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_scim_token),
):

    user = _get_user_or_none(db, user_id)
    if not user:
        _raise(404, "User not found")
    # Soft delete (platform convention: is_active flag + status, never hard-delete).
    user.is_active = False
    user.status = UserStatus.DELETED.value
    db.commit()
    return None
