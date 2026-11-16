"""Honest actor/audit rows for mini-app run-authority tests.

``core.mini_app_service.run_stateful`` authorizes through the shared canvas
gate (``core.canvas_authority`` → ``tools.canvas_crud_tool``), which resolves
the acting user from the authoritative ``User`` row and the canvas policy from
``Canvas.created_by`` / the newest ``CanvasAudit`` row. Fixtures that created a
canvas for the bare string ``"u1"`` were asserting against an imaginary actor:
there was no User row, no tenant, no audit trail. Those fixtures now seed the
rows a real scaffold/install produces, so the tests exercise the same
authorization every production caller does.

Scratch-DB only — every helper reads/writes the caller's session. No live DB,
no network.
"""
from __future__ import annotations

import contextlib
import uuid
from typing import Any, Optional


def ensure_tenant(db: Any, tenant_id: str = "t1") -> None:
    """Get-or-create the tenant the fixture actor belongs to."""
    from core.models import Tenant

    if db.query(Tenant.id).filter(Tenant.id == tenant_id).first() is not None:
        return
    db.add(Tenant(
        id=tenant_id,
        name=f"Tenant {tenant_id}",
        subdomain=f"tenant-{tenant_id}-{uuid.uuid4().hex[:8]}",
        edition="personal",
        is_active=True,
    ))
    db.flush()


def ensure_workspace(db: Any, tenant_id: str, workspace_id: Optional[str]) -> None:
    """Get-or-create the workspace the fixture actor belongs to (when scoped)."""
    if not workspace_id:
        return
    from core.models import Workspace

    if db.query(Workspace.id).filter(Workspace.id == workspace_id).first() is not None:
        return
    db.add(Workspace(
        id=workspace_id,
        name=f"Workspace {workspace_id}",
        tenant_id=tenant_id,
        status="active",
    ))
    db.flush()


def ensure_actor(
    db: Any,
    user_id: str = "u1",
    tenant_id: str = "t1",
    workspace_id: Optional[str] = "w1",
    *,
    active: bool = True,
) -> Any:
    """Get-or-create the authoritative ``User`` (and its tenant/workspace).

    Returns the User row so callers can assert on the exact actor the service
    resolves. ``active=False`` seeds a deactivated actor for refusal tests.
    """
    from core.models import User

    ensure_tenant(db, tenant_id)
    ensure_workspace(db, tenant_id, workspace_id)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            email=f"{user_id}@mini-app.test",
            hashed_password="x",
            first_name="Mini",
            last_name="App",
            role="member",
            status="active",
            is_active=active,
        )
        db.add(user)
    else:
        user.is_active = bool(active)
    db.flush()
    return user


def ensure_canvas_audit(
    db: Any,
    canvas_id: str,
    *,
    user_id: str = "u1",
    tenant_id: str = "t1",
    canvas_type: str = "mini_app",
    action_type: str = "create",
) -> None:
    """Append the authorship audit row every real mini-app canvas carries.

    ``scaffold`` and ``install`` both write one (they are also the read source
    for the canvas page), and the shared lifecycle/scope gate requires a
    newest audit row to exist. Content is irrelevant to authority.
    """
    from core.models import CanvasAudit

    if db.query(CanvasAudit.id).filter(
        CanvasAudit.canvas_id == canvas_id
    ).first() is not None:
        return
    db.add(CanvasAudit(
        id=str(uuid.uuid4()),
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        user_id=user_id,
        canvas_type=canvas_type,
        action_type=action_type,
        details_json={
            "canvas_id": canvas_id,
            "tenant_id": tenant_id,
            "actor_id": user_id,
        },
    ))
    db.flush()


@contextlib.contextmanager
def patched_canvas_gate(actor_id: str = "fake-actor"):
    """Opt handler-plumbing UNIT tests out of the DB-backed canvas gate.

    Those tests drive the handlers with fake sessions (MagicMock / single-row
    stubs) that cannot answer the actor/scope queries. The REAL gate is
    covered against a scratch DB by ``tests/test_mini_app_run_authority.py``
    (foreign owner, missing/inactive actor, tombstone, installed copy), so
    these unit tests isolate handler plumbing explicitly instead of asserting
    authorization against an imaginary session.
    """
    from unittest.mock import patch

    from core import canvas_authority

    def _actor(_db: Any, user_id: Any) -> Dict[str, Any]:
        # Mirror the caller id so identity-based owner checks still apply.
        return {
            "ok": True,
            "user": None,
            "id": str(user_id),
            "tenant_id": None,
            "workspace_id": None,
            "status": "active",
            "is_active": True,
            "effective_tenant_id": "default",
            "effective_workspace_id": "default",
        }

    with patch.object(
            canvas_authority, "require_active_actor", side_effect=_actor), \
        patch.object(canvas_authority, "require_canvas_read"), \
        patch.object(canvas_authority, "require_canvas_active"), \
        patch.object(canvas_authority, "require_canvas_write"):
        yield
