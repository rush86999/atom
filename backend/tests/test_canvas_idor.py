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


# ============================================================================
# Gallery visibility must agree with per-canvas authorization.
#
# Discovery (list_canvases) scopes by CanvasAudit.user_id; authorization
# (_verify_canvas_owner) trusted ONLY Canvas.created_by whenever a Canvas row
# existed. So a canvas CREATED by one user and later EDITED by another (normal
# co-editing; the office /present flow reuses one Canvas row per file; a
# second operator account) was listed in the editor's gallery yet 404'd on
# every per-canvas endpoint.
#
# Observed live 2026-09-10: canvas_formulacheck01 — Canvas.created_by = a test
# member, newest CanvasAudit row = the admin. GET /api/canvas/<id> 404'd with
# "Canvas ... not found", then the gallery's DELETE returned the same 404
# (AxiosError overlay at pages/canvas/index.tsx:146).
# ============================================================================


def _add_audit(db, canvas_id: str, user_id: str, action_type: str,
               tenant_id: str = "t1", content: str = "edited"):
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        action_type=action_type,
        user_id=user_id,
        canvas_type="generic",
        details_json={"content": content},
    ))
    db.commit()


class TestCoEditorOwnership:
    """A user recorded as an author on a canvas may act on it, even when the
    Canvas row was created by somebody else."""

    @pytest.mark.asyncio
    async def test_co_editor_can_read_canvas_created_by_another_user(self, db):
        from tools.canvas_crud_tool import read_canvas
        _seed_canvas(db, "canvas-coedit-read", owner_id="user-A")
        _add_audit(db, "canvas-coedit-read", "user-B", "update")

        result = await read_canvas("user-B", "canvas-coedit-read")

        assert result["success"] is True, (
            "A canvas listed in the co-editor's gallery 404'd on read: "
            f"{result.get('error')}"
        )

    @pytest.mark.asyncio
    async def test_co_editor_can_delete_canvas_created_by_another_user(self, db):
        from tools.canvas_crud_tool import delete_canvas
        _seed_canvas(db, "canvas-coedit-del", owner_id="user-A")
        _add_audit(db, "canvas-coedit-del", "user-B", "update")

        result = await delete_canvas("user-B", "canvas-coedit-del")

        assert result["success"] is True, (
            "Gallery delete of a co-edited canvas 404'd: "
            f"{result.get('error')}"
        )

    @pytest.mark.asyncio
    async def test_form_submitter_does_not_gain_ownership(self, db):
        """A ``submit`` row is an event stamp (public/shared form canvases
        accept submissions from non-owners) — it must NOT grant read/delete on
        the owner's canvas."""
        from tools.canvas_crud_tool import delete_canvas, read_canvas
        _seed_canvas(db, "canvas-submit-only", owner_id="user-A")
        _add_audit(db, "canvas-submit-only", "user-B", "submit",
                   content=None)

        read = await read_canvas("user-B", "canvas-submit-only")
        delete = await delete_canvas("user-B", "canvas-submit-only")

        assert read["success"] is False, "a form submitter read the owner's canvas (IDOR)"
        assert delete["success"] is False, "a form submitter deleted the owner's canvas (IDOR)"


class TestGalleryListingMatchesAuthorization:
    """Whatever the gallery lists for a user, that user must be able to act on."""

    @pytest.mark.asyncio
    async def test_listed_canvases_are_all_actionable(self, db):
        from tools.canvas_crud_tool import _verify_canvas_owner, list_canvases

        # user-B: co-editor of a canvas created by user-A ...
        _seed_canvas(db, "canvas-consistency-coedit", owner_id="user-A")
        _add_audit(db, "canvas-consistency-coedit", "user-B", "update")
        # ... and a bare form submitter on another of user-A's canvases.
        _seed_canvas(db, "canvas-consistency-submit", owner_id="user-A")
        _add_audit(db, "canvas-consistency-submit", "user-B", "submit",
                   content=None)

        listed = await list_canvases("user-B")
        assert listed["success"] is True
        ids = [c["canvas_id"] for c in listed["canvases"]]

        assert "canvas-consistency-coedit" in ids, (
            "co-edited canvas missing from the gallery the user must act on it from"
        )
        assert "canvas-consistency-submit" not in ids, (
            "a form submission must not surface somebody else's canvas in the "
            "submitter's gallery"
        )
        for canvas_id in ids:
            assert _verify_canvas_owner(db, canvas_id, "user-B") is True, (
                f"gallery listed {canvas_id} but the owner guard denies it — "
                "the card is a dead end (404 on open/delete)"
            )
