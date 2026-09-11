"""Office canvas ↔ file binding identity (Sep 10, 2026 — canvas 7f078cea).

Root-cause chain pinned here, one test per gap:

1. The chat-draft materializer (``_office_draft``) seeded the Canvas row with
   a CWD-RELATIVE ``office_file`` ("data/office/chat-….xlsx") while every
   office API validates to an ABSOLUTE path. Raw ``==`` comparisons then
   missed the binding: ``ensure_canvas_for_file`` created a DUPLICATE canvas
   row for the same file, and ``notify_file_canvases`` skipped the original —
   so agent edits to the file never reached the canvas the user had open.
2. That same canvas carried the registry canvas_type "sheets" (legacy alias
   for the generic GRID app) with office-file content; the co-editor then
   planned a grid edit, reproduced the content and falsely replied that the
   canvas "already reflects" the requested change (see
   ``test_canvas_app_editor_fixes.py`` for the classification half).
"""
import os

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base


@pytest.fixture()
def office_root(tmp_path, monkeypatch):
    office_dir = tmp_path / "office"
    office_dir.mkdir()
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(office_dir))
    return office_dir


@pytest.fixture()
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def xlsx_file(office_root):
    p = office_root / "quote.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Machine", "CAD", "Freight"])
    ws.append(["Trumatic-L3030S", 20000, 5000])
    wb.save(p)
    return p


# ── 1. path identity helper ──────────────────────────────────────────────

def test_office_path_key_matches_relative_and_absolute(tmp_path, monkeypatch):
    from core.office_sync_service import _office_path_key

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "data" / "office"))
    (tmp_path / "data" / "office").mkdir(parents=True)
    rel = "data/office/quote.xlsx"
    absolute = str(tmp_path / "data" / "office" / "quote.xlsx")
    assert _office_path_key(rel) == _office_path_key(absolute)
    assert _office_path_key(None) == ""
    assert _office_path_key("") == ""


# ── 2. seeding writes an absolute binding ────────────────────────────────

def test_office_draft_binds_absolute_path(office_root):
    """The chat-draft materializer must return the SAME absolute path the
    office APIs validate against — a relative binding orphaned the canvas."""
    from integrations.chat_routes import _office_draft

    materialized = _office_draft(
        "| Machine | CAD |\n|---|---|\n| L3030S | 20000 |", "table", "Quote"
    )
    assert materialized is not None
    _canvas_type, content, _title = materialized
    assert os.path.isabs(content["office_file"]), (
        f"office_file must be absolute, got {content['office_file']!r}"
    )
    assert os.path.isabs(content["file_path"])
    assert os.path.exists(content["office_file"])


# ── 3. legacy relative rows still match the file ─────────────────────────

def test_notify_file_canvases_matches_legacy_relative_binding(
    test_db, office_root, xlsx_file, monkeypatch
):
    """A row seeded before the absolute-path fix must still receive agent
    edits to its file instead of being silently skipped."""
    from core.models import Canvas
    from core.office_sync_service import OfficeSyncService

    monkeypatch.chdir(office_root.parent)
    rel = os.path.relpath(str(xlsx_file), os.getcwd())
    cid = "canvas_legacy_relative"
    test_db.add(Canvas(
        id=cid, tenant_id="default", created_by="u1", name="quote.xlsx",
        canvas_type="sheets",
        content={"office_file": rel, "format": "xlsx"},
    ))
    test_db.commit()

    svc = OfficeSyncService(test_db)
    notified = []
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        svc, "broadcast_file_update",
        side_effect=lambda canvas_id, file_path, user_id: notified.append(canvas_id),
    ):
        ids = svc.notify_file_canvases(str(xlsx_file), "u1")

    assert ids == [cid], f"legacy relative binding was skipped: {ids}"
    assert notified == [cid]


def test_ensure_canvas_for_file_reuses_and_repairs_legacy_row(
    test_db, office_root, xlsx_file, monkeypatch
):
    """A relative-bound row is the SAME file, not a new one — reuse it AND
    rewrite the binding to the absolute path (no duplicate canvas)."""
    from core.models import Canvas
    from core.office_sync_service import OfficeSyncService

    monkeypatch.chdir(office_root.parent)
    rel = os.path.relpath(str(xlsx_file), os.getcwd())
    cid = "canvas_legacy_relative_2"
    test_db.add(Canvas(
        id=cid, tenant_id="default", created_by="u1", name="quote.xlsx",
        canvas_type="sheets",
        content={"office_file": rel, "format": "xlsx"},
    ))
    test_db.commit()

    result = OfficeSyncService(test_db).ensure_canvas_for_file(
        None, str(xlsx_file), "u1"
    )
    assert result["id"] == cid and result["created"] is False

    rows = test_db.query(Canvas).filter(Canvas.status == "active").all()
    same_file = [
        r for r in rows
        if isinstance(r.content, dict) and r.content.get("office_file")
    ]
    assert len(same_file) == 1, "duplicate canvas created for the same file"
    assert os.path.isabs(same_file[0].content["office_file"])


# ── 4. a delete tombstone survives the file → canvas fan-out ─────────────
#
# The delete path is append-only: a deleted canvas keeps status "active" and
# is recognized only by its NEWEST CanvasAudit row. The office fan-out filtered
# on ``Canvas.status`` alone, so an agent file edit appended an "update" row on
# top of a tombstone and the card came back — live 2026-09-10: the duplicate
# canvas_c7b3491aebf8 was deleted at 13:46:10 and resurrected at 14:04:10
# (both canvases bound to the file were updated 9ms apart).

def _tombstone(db, canvas_id):
    from datetime import datetime, timezone

    from core.models import CanvasAudit

    db.add(CanvasAudit(
        canvas_id=canvas_id, tenant_id="default", action_type="delete",
        user_id="u1", canvas_type="sheets",
        details_json={"deleted": True, "previous_action": "update"},
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()


def _bound_canvas(db, canvas_id, path):
    from core.models import Canvas

    db.add(Canvas(
        id=canvas_id, tenant_id="default", created_by="u1", name="quote.xlsx",
        canvas_type="sheets",
        content={"office_file": str(path), "format": "xlsx"},
    ))
    db.commit()


def test_notify_file_canvases_skips_deleted_canvas(test_db, office_root, xlsx_file):
    """An agent edit to the file must NOT revive a canvas the user deleted."""
    from unittest.mock import patch

    from core.office_sync_service import OfficeSyncService

    cid = "canvas_tombstoned"
    _bound_canvas(test_db, cid, xlsx_file)
    _tombstone(test_db, cid)

    svc = OfficeSyncService(test_db)
    with patch.object(svc, "broadcast_file_update") as broadcast:
        ids = svc.notify_file_canvases(str(xlsx_file), "u1")

    assert ids == [], f"deleted canvas was notified and revived: {ids}"
    broadcast.assert_not_called()


def test_notify_file_canvases_still_reaches_the_live_canvas(
    test_db, office_root, xlsx_file
):
    """The duplicate case: deleting one of two canvases bound to the same file
    must leave the other one receiving edits."""
    from unittest.mock import patch

    from core.office_sync_service import OfficeSyncService

    _bound_canvas(test_db, "canvas_duplicate", xlsx_file)
    _bound_canvas(test_db, "canvas_original", xlsx_file)
    _tombstone(test_db, "canvas_duplicate")

    svc = OfficeSyncService(test_db)
    notified = []
    with patch.object(
        svc, "broadcast_file_update",
        side_effect=lambda canvas_id, file_path, user_id: notified.append(canvas_id),
    ):
        ids = svc.notify_file_canvases(str(xlsx_file), "u1")

    assert ids == ["canvas_original"], f"expected only the live canvas, got {ids}"
    assert notified == ["canvas_original"]


def test_ensure_canvas_for_file_ignores_tombstoned_binding(
    test_db, office_root, xlsx_file
):
    """Re-presenting a file whose canvas was deleted starts a FRESH canvas —
    reopening the tombstoned one would silently un-delete it."""
    from core.models import Canvas
    from core.office_sync_service import OfficeSyncService

    cid = "canvas_deleted_binding"
    _bound_canvas(test_db, cid, xlsx_file)
    _tombstone(test_db, cid)

    result = OfficeSyncService(test_db).ensure_canvas_for_file(
        None, str(xlsx_file), "u1"
    )
    assert result["id"] != cid, "re-presenting reused a deleted canvas"
    assert result["created"] is True
    assert test_db.query(Canvas).filter(Canvas.id == cid).count() == 1


def test_broadcast_file_update_refuses_deleted_canvas(
    test_db, office_root, xlsx_file
):
    """The last line of defence: the audit-row writer itself must refuse, so no
    caller (present with an explicit id, sync-update, agent fan-out) can revive a
    deleted canvas."""
    from core.models import CanvasAudit
    from core.office_sync_service import OfficeSyncService

    cid = "canvas_deleted_broadcast"
    _bound_canvas(test_db, cid, xlsx_file)
    _tombstone(test_db, cid)

    OfficeSyncService(test_db).broadcast_file_update(cid, str(xlsx_file), "u1")

    actions = [
        r.action_type
        for r in test_db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == cid)
        .order_by(CanvasAudit.created_at, CanvasAudit.id)
        .all()
    ]
    assert actions == ["delete"], (
        f"an update row was written over the tombstone — canvas revived: {actions}"
    )
