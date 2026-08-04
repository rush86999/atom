"""
IDOR / ownership tests for the canvas CRUD tool (tools/canvas_crud_tool.py).

read_canvas, update_canvas_content, and delete_canvas query by canvas_id only —
the user_id parameter is accepted but never used to verify ownership. Any
authenticated user who knows (or guesses) a canvas_id can read, overwrite, or
delete another user's canvas. These tests guard against that IDOR by asserting
a non-owner is denied.
"""

import pytest
from datetime import datetime, timezone

from core.models import Canvas, CanvasAudit, Tenant


@pytest.fixture
def db(worker_database, monkeypatch):
    """Patch core.database.SessionLocal to the in-memory factory so the tool's
    get_db_session() sees the seeded data."""
    import core.database as db_mod
    monkeypatch.setattr(db_mod, "SessionLocal", worker_database)
    SessionLocal = worker_database
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _seed_canvas(db, canvas_id: str, owner_id: str, tenant_id: str = "t1"):
    """Create the Canvas row + an initial 'create' CanvasAudit row owned by owner_id."""
    # Ensure tenant exists (Canvas.tenant_id FK).
    if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
        db.add(Tenant(id=tenant_id, name="T", subdomain=f"t-{tenant_id}"))
        db.flush()
    from core.models import Workspace
    ws_id = f"ws-{canvas_id}"
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if not ws:
        ws = Workspace(id=ws_id, tenant_id=tenant_id, name="WS")
        db.add(ws)
        db.flush()
    canvas = Canvas(
        id=canvas_id,
        tenant_id=tenant_id,
        workspace_id=ws.id,
        created_by=owner_id,
        name="Test Canvas",
    )
    db.add(canvas)
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        action_type="create",
        user_id=owner_id,
        canvas_type="generic",
        details_json={"content": "original", "title": "Test"},
    ))
    db.commit()
    return canvas


# ============================================================================
# read_canvas
# ============================================================================

class TestReadCanvasOwnership:
    @pytest.mark.asyncio
    async def test_non_owner_cannot_read_canvas(self, db):
        """User B must NOT be able to read user A's canvas by id."""
        from tools.canvas_crud_tool import read_canvas
        _seed_canvas(db, "canvas-read-1", owner_id="user-A")

        result = await read_canvas("user-B", "canvas-read-1")

        assert result["success"] is False, (
            "Non-owner was allowed to read another user's canvas (IDOR)"
        )


# ============================================================================
# update_canvas_content
# ============================================================================

class TestUpdateCanvasOwnership:
    @pytest.mark.asyncio
    async def test_non_owner_cannot_update_canvas(self, db):
        """User B must NOT be able to overwrite user A's canvas."""
        from tools.canvas_crud_tool import update_canvas_content
        _seed_canvas(db, "canvas-update-1", owner_id="user-A")

        result = await update_canvas_content(
            "user-B", "canvas-update-1", {"content": "hijacked"}, "generic"
        )

        assert result["success"] is False, (
            "Non-owner was allowed to update another user's canvas (IDOR)"
        )


# ============================================================================
# delete_canvas
# ============================================================================

class TestDeleteCanvasOwnership:
    @pytest.mark.asyncio
    async def test_non_owner_cannot_delete_canvas(self, db):
        """User B must NOT be able to delete user A's canvas."""
        from tools.canvas_crud_tool import delete_canvas
        _seed_canvas(db, "canvas-delete-1", owner_id="user-A")

        result = await delete_canvas("user-B", "canvas-delete-1")

        assert result["success"] is False, (
            "Non-owner was allowed to delete another user's canvas (IDOR)"
        )

    @pytest.mark.asyncio
    async def test_owner_can_delete_own_canvas(self, db):
        """Sanity: the actual owner can still delete their canvas."""
        from tools.canvas_crud_tool import delete_canvas
        _seed_canvas(db, "canvas-delete-2", owner_id="user-A")

        result = await delete_canvas("user-A", "canvas-delete-2")

        assert result["success"] is True
