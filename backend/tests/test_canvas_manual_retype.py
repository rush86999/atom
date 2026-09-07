"""
Manual canvas retype tests (tools/canvas_crud_tool.py).

The chat→canvas classifier picks a canvas type structurally and can guess
wrong. The UI's escape hatch is PUT /api/canvas/{id}?retype=true →
update_canvas_content(manual_retype=True), which pins the human's choice on
the audit row (details.type_pinned). These tests guard the pin contract:

- a pinned type is never flipped back by read-time email coercion;
- the pin survives later (non-retype) content updates;
- unpinned canvases keep the historical coercion behavior;
- a content update no longer retypes the canvas to the "generic" default.
"""

import pytest
from datetime import datetime, timedelta

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


# Email-shaped body: "Subject:" header near the top + enough body — exactly
# what coerce_email_canvas upgrades doc-like canvases for.
EMAIL_SHAPED_BODY = (
    "Subject: Quarterly update\n"
    "\n"
    "Here is the quarterly update with more than enough body text to pass\n"
    "the classifier's minimum, so an unpinned document WOULD flip to email."
)


def _seed_canvas(db, canvas_id: str, owner_id: str = "user-A", canvas_type: str = "document",
                 content=None, details_extra: dict | None = None):
    """Create the Canvas row + one audit row carrying the given type/content."""
    tenant_id = "t1"
    if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
        db.add(Tenant(id=tenant_id, name="T", subdomain="t-retype"))
        db.flush()
    from core.models import Workspace
    ws_id = f"ws-{canvas_id}"
    if not db.query(Workspace).filter(Workspace.id == ws_id).first():
        db.add(Workspace(id=ws_id, tenant_id=tenant_id, name="WS"))
        db.flush()
    db.add(Canvas(
        id=canvas_id,
        tenant_id=tenant_id,
        workspace_id=ws_id,
        created_by=owner_id,
        name="Test Canvas",
    ))
    details = {"content": content if content is not None else "original", "title": "Test"}
    if details_extra:
        details.update(details_extra)
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        action_type="create",
        user_id=owner_id,
        canvas_type=canvas_type,
        details_json=details,
        # Force strict ordering: rows created within the same second tie on
        # created_at and "latest row" reads become ambiguous otherwise.
        created_at=datetime.utcnow() - timedelta(hours=1),
    ))
    db.commit()


class TestManualRetype:
    @pytest.mark.asyncio
    async def test_manual_retype_pins_type_against_read_coercion(self, db):
        """A human retype to document must survive read_canvas even when the
        body still LOOKS like an email draft (the classifier would flip an
        unpinned canvas back to email)."""
        from tools.canvas_crud_tool import read_canvas, update_canvas_content
        _seed_canvas(db, "canvas-retype-1", canvas_type="email",
                     content={"to": "a@b.c", "subject": "Quarterly update", "body": EMAIL_SHAPED_BODY})

        result = await update_canvas_content(
            "user-A", "canvas-retype-1", EMAIL_SHAPED_BODY, "document",
            manual_retype=True,
        )
        assert result["success"] is True
        assert result["canvas_type"] == "document"

        read = await read_canvas("user-A", "canvas-retype-1")
        assert read["success"] is True
        assert read["canvas_type"] == "document", (
            "Read-time email coercion overrode the user's manual type choice"
        )

    @pytest.mark.asyncio
    async def test_pin_survives_later_non_retype_updates(self, db):
        """After a pin, ordinary content saves (no retype flag, default
        canvas_type) must keep the pinned type — not retype to 'generic' and
        not coerce the email-shaped body back to the composer."""
        from tools.canvas_crud_tool import read_canvas, update_canvas_content
        _seed_canvas(db, "canvas-retype-2", canvas_type="email",
                     content={"to": "a@b.c", "subject": "Quarterly update", "body": EMAIL_SHAPED_BODY})
        await update_canvas_content(
            "user-A", "canvas-retype-2", EMAIL_SHAPED_BODY, "document",
            manual_retype=True,
        )

        # Later save as the co-editor/chat flow might issue it (default type).
        result = await update_canvas_content(
            "user-A", "canvas-retype-2", EMAIL_SHAPED_BODY + "\nMore edits.", "generic",
        )
        assert result["success"] is True
        assert result["canvas_type"] == "document"

        read = await read_canvas("user-A", "canvas-retype-2")
        assert read["canvas_type"] == "document"

    @pytest.mark.asyncio
    async def test_unpinned_doc_still_coerces_to_email_on_read(self, db):
        """Regression guard: without a pin, the historical read-time repair
        keeps upgrading email-shaped documents to the composer."""
        from tools.canvas_crud_tool import read_canvas
        _seed_canvas(db, "canvas-retype-3", canvas_type="document", content=EMAIL_SHAPED_BODY)

        read = await read_canvas("user-A", "canvas-retype-3")

        assert read["success"] is True
        assert read["canvas_type"] == "email", (
            "Unpinned email-shaped documents must still coerce to email on read"
        )

    @pytest.mark.asyncio
    async def test_update_without_type_preserves_canvas_type(self, db):
        """A content update issued with the endpoint's default canvas_type
        must not retype the canvas to 'generic' (callers like the agent
        action registry omit the type)."""
        from tools.canvas_crud_tool import read_canvas, update_canvas_content
        _seed_canvas(db, "canvas-retype-4", canvas_type="document",
                     content="plain document body")

        result = await update_canvas_content(
            "user-A", "canvas-retype-4", "edited document body", "generic",
        )
        assert result["success"] is True
        assert result["canvas_type"] == "document", (
            "Content update retyped the canvas to the 'generic' default"
        )

        read = await read_canvas("user-A", "canvas-retype-4")
        assert read["canvas_type"] == "document"

    @pytest.mark.asyncio
    async def test_manual_retype_to_email_is_not_renormalized_away(self, db):
        """Retyping INTO email stores the composer payload verbatim — the
        subject the user typed stays the subject (no classifier rewrite)."""
        from tools.canvas_crud_tool import read_canvas, update_canvas_content
        _seed_canvas(db, "canvas-retype-5", canvas_type="document",
                     content="A plain document that was never an email at all.")
        payload = {"to": "x@y.z", "cc": "", "subject": "Typed subject", "body": "Typed body."}

        result = await update_canvas_content(
            "user-A", "canvas-retype-5", payload, "email", manual_retype=True,
        )
        assert result["success"] is True
        assert result["canvas_type"] == "email"

        read = await read_canvas("user-A", "canvas-retype-5")
        assert read["canvas_type"] == "email"
        assert read["content"] == payload


class TestPinnedUpdateMergesContent:
    """Sept 6 incident: for a type-pinned canvas the update path resolved the
    type but SKIPPED the content merge — every co-editor PUT on a
    chat-created (pinned) email canvas wrote a no-op audit row with empty
    content, silently shadowing newer content on recency. Content merges are
    orthogonal to type resolution: a pinned update must land the new body."""

    @pytest.mark.asyncio
    async def test_pinned_update_with_explicit_type_merges_content(self, db):
        from tools.canvas_crud_tool import read_canvas, update_canvas_content

        _seed_canvas(db, "canvas-pinned-merge-1", canvas_type="email",
                     content={"to": "a@b.c", "subject": "s", "body": "old body"},
                     details_extra={"type_pinned": True})

        styled = {"to": "a@b.c", "cc": "", "subject": "s",
                  "body": '<table style="border:1px solid #8A8A8A"><tr>'
                          '<th style="background-color:#1F497D">H</th></tr></table>'}
        result = await update_canvas_content(
            "user-A", "canvas-pinned-merge-1", styled, "email",
        )
        assert result["success"] is True

        read = await read_canvas("user-A", "canvas-pinned-merge-1")
        assert read["content"]["body"] == styled["body"], (
            "Pinned canvas dropped the caller's content — merge was skipped"
        )

    @pytest.mark.asyncio
    async def test_pinned_update_default_type_merges_content(self, db):
        from tools.canvas_crud_tool import read_canvas, update_canvas_content

        _seed_canvas(db, "canvas-pinned-merge-2", canvas_type="email",
                     content={"to": "a@b.c", "subject": "s", "body": "old body"},
                     details_extra={"type_pinned": True})

        result = await update_canvas_content(
            "user-A", "canvas-pinned-merge-2", {"to": "a@b.c", "subject": "s",
                                                "body": "new body"}, "generic",
        )
        assert result["success"] is True
        assert result["canvas_type"] == "email", "pin must keep the type"

        read = await read_canvas("user-A", "canvas-pinned-merge-2")
        assert read["content"]["body"] == "new body"
