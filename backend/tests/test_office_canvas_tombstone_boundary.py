"""Office boundaries must respect the canonical canvas tombstone.

The observed defect (2026-11-14 evidence): after the user deleted the canvas
through the shipped control, ``GET /api/v1/office/download`` still returned the
workbook with HTTP 200. ``download_office_file`` checked ownership and the
file→canvas binding but never asked whether the canvas had been deleted.

These tests run the REAL routes and services against a real scratch SQLite
file (no mocks for the authorization/DB path), and pin the whole boundary:

* active canvas: download/read/write/present/sync keep working;
* deleted canvas: download, path-only read/write, sync, upload-to-canvas,
  present-with-id and canvas data upload are refused with NO file byte change
  and NO audit append;
* the refusal is the canonical tombstone (newest ``CanvasAudit`` row), not a
  download-only or message-regex special case;
* ownership and active-state stay distinct gates, so undelete (the existing
  canonical restore) makes every boundary work again and history survives.

Scratch DB only: the shared ``probe`` fixture creates its own SQLite file and
monkeypatches ``core.database.get_db_session`` before any route runs.
"""
from __future__ import annotations

import contextlib
import hashlib
from datetime import datetime, timedelta, timezone

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_canvas_lifecycle_verified import (  # noqa: F401 — fixtures
    _audit,
    _canvas,
    _user,
    app_client,
    broadcast_spy,
    probe,
)

OFFICE_PREFIX = "/api/v1/office"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def office_root(tmp_path, monkeypatch):
    root = tmp_path / "office"
    root.mkdir()
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(root))
    return root


@pytest.fixture()
def quiet_office_side_effects(monkeypatch):
    """Keep office broadcasts/ingestion off the network in a unit test."""
    from unittest.mock import AsyncMock, MagicMock

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "core.office_sync_service.OfficeSyncService._ingest_document_to_memory",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr("core.websockets.manager.broadcast", _noop)
    monkeypatch.setattr(
        "core.notification_manager.notification_manager.broadcast", _noop)
    monkeypatch.setattr(
        "api.canvas_routes.manager.broadcast_message", MagicMock())


@pytest.fixture()
def office_client(probe, app_client):
    """The real office router on the same scratch DB/session as canvas routes."""
    from api.office_routes import get_db_session_dep, router as office_router
    from core.auth import get_current_user

    app = FastAPI()
    app.include_router(office_router, prefix=OFFICE_PREFIX)

    def _override_db():
        session = probe.Session()
        try:
            yield session
        finally:
            session.close()

    def _override_user():
        return app_client.users["current"]

    app.dependency_overrides[get_db_session_dep] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture()
def owner(app_client, probe):
    session = probe.Session()
    try:
        row = _user(session, user_id="tomb-owner", tenant_id="default")
    finally:
        session.close()
    app_client.users["current"] = row
    return row


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit_count(probe, canvas_id):
    from core.models import CanvasAudit

    session = probe.Session()
    try:
        return session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id).count()
    finally:
        session.close()


def _make_xlsx(path, value=12):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = value
    ws["B1"] = 7
    ws["C1"] = "=A1+B1"
    wb.save(path)
    return path


def _make_docx(path):
    import docx

    doc = docx.Document()
    doc.add_paragraph("Synthetic office tombstone control")
    doc.save(path)
    return path


def _make_pptx(path):
    import pptx

    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Synthetic"
    slide.placeholders[1].text = "Tombstone control"
    prs.save(path)
    return path


def _bind_canvas(probe, *, canvas_id, owner_id, file_path, canvas_type="sheets"):
    """Insert the Canvas row + one content-bearing audit row (pre-delete)."""
    session = probe.Session()
    try:
        content = {
            "office_file": str(file_path),
            "format": file_path.suffix.lstrip("."),
        }
        canvas = _canvas(
            session, canvas_id=canvas_id, owner_id=owner_id,
            content=content, canvas_type=canvas_type,
        )
        _audit(
            session, canvas_id=canvas_id, action_type="create",
            user_id=owner_id, canvas_type=canvas_type,
            details={"content": content, "title": file_path.name},
            created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
    finally:
        session.close()
    return canvas


def _bind_canvas_to_content(
    probe, *, canvas_id, owner_id, content, canvas_type="sheets",
):
    """Insert a Canvas row with an exact (possibly legacy/alias) binding."""
    session = probe.Session()
    try:
        canvas = _canvas(
            session, canvas_id=canvas_id, owner_id=owner_id,
            content=dict(content), canvas_type=canvas_type,
        )
        _audit(
            session, canvas_id=canvas_id, action_type="create",
            user_id=owner_id, canvas_type=canvas_type,
            details={"content": dict(content), "title": "bound"},
            created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
    finally:
        session.close()
    return canvas


def _tombstone(probe, *, canvas_id, owner_id, canvas_type="sheets"):
    """Append the canonical delete tombstone exactly as delete_canvas does."""
    session = probe.Session()
    try:
        _audit(
            session, canvas_id=canvas_id, action_type="delete",
            user_id=owner_id, canvas_type=canvas_type,
            details={"operation_id": f"test-delete-{canvas_id}"},
            created_at=datetime.now(timezone.utc),
        )
    finally:
        session.close()


def _upload_xlsx(client, canvas_id, path):
    with path.open("rb") as fh:
        return client.post(
            f"/api/canvas/{canvas_id}/data/upload",
            files={"file": (path.name, fh.read(),
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet")},
        )


# ---------------------------------------------------------------------------
# Positive controls — a live canvas keeps every boundary available
# ---------------------------------------------------------------------------
class TestActiveCanvasStillWorks:
    def test_download_path_only_read_and_sync_succeed(
        self, office_client, probe, owner, office_root, quiet_office_side_effects,
    ):
        path = _make_xlsx(office_root / "active.xlsx")
        cid = "canvas-active-control"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)

        download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert download.status_code == 200, download.text
        assert download.content == path.read_bytes()

        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 200, read.text
        assert read.json()["success"] is True

        before = _audit_count(probe, cid)
        sync = office_client.post(
            f"{OFFICE_PREFIX}/sync-update",
            json={
                "canvas_id": cid, "file_path": str(path), "user_id": "forged",
                "edit_type": "cell",
                "data": {"cell_path": "/Sheet1/A1", "value": 21},
            },
        )
        assert sync.status_code == 200, sync.text
        assert sync.json()["success"] is True
        wb = openpyxl.load_workbook(path, data_only=False)
        assert wb["Sheet1"]["A1"].value == 21
        assert _audit_count(probe, cid) > before

    def test_upload_without_canvas_id_remains_legitimate(
        self, office_client, owner, office_root,
    ):
        """An unbound upload is not a canvas operation and must keep working."""
        source = office_root.parent / "manual.xlsx"
        _make_xlsx(source)
        response = office_client.post(
            f"{OFFICE_PREFIX}/upload",
            files={"file": (source.name, source.read_bytes(),
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet")},
        )
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        assert (office_root / response.json()["file_name"]).is_file()


# ---------------------------------------------------------------------------
# Deleted canvas — download and every write boundary refuse without effect
# ---------------------------------------------------------------------------
class TestDeletedCanvasDownload:
    def test_deleted_canvas_download_is_404(
        self, office_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "deleted.xlsx")
        cid = "canvas-deleted-download"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)

        response = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert response.status_code == 404, response.text
        assert b"PK" not in response.content[:2]
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_deleted_canvas_path_only_read_is_404(
        self, office_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "read-deleted.xlsx")
        cid = "canvas-deleted-read"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)

        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 404, read.text
        formula = office_client.get(
            f"{OFFICE_PREFIX}/excel/formula-result",
            params={"file_path": str(path), "cell_path": "/Sheet1/C1"},
        )
        assert formula.status_code == 404, formula.text

    def test_deleted_canvas_sync_update_refuses_without_effect(
        self, office_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "write-deleted.xlsx")
        cid = "canvas-deleted-write"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)

        response = office_client.post(
            f"{OFFICE_PREFIX}/sync-update",
            json={
                "canvas_id": cid, "file_path": str(path), "user_id": "forged",
                "edit_type": "cell",
                "data": {"cell_path": "/Sheet1/A1", "value": 999},
            },
        )
        assert response.status_code == 404, response.text
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_deleted_canvas_path_only_write_is_404(
        self, office_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "path-write-deleted.xlsx")
        cid = "canvas-deleted-path-write"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)

        response = office_client.post(
            f"{OFFICE_PREFIX}/excel",
            json={
                "file_path": str(path), "cell_path": "/Sheet1/A1",
                "value": 999, "is_formula": False,
            },
        )
        assert response.status_code == 404, response.text
        assert _sha(path) == before_sha

    def test_present_and_upload_with_deleted_canvas_id_are_refused(
        self, office_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "present-deleted.xlsx")
        cid = "canvas-deleted-present"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_audit = _audit_count(probe, cid)

        present = office_client.post(
            f"{OFFICE_PREFIX}/present",
            json={"file_path": str(path), "canvas_id": cid,
                  "user_id": "forged"},
        )
        assert present.status_code == 404, present.text
        assert _audit_count(probe, cid) == before_audit

        files_before = sorted(p.name for p in office_root.iterdir())
        upload = office_client.post(
            f"{OFFICE_PREFIX}/upload",
            data={"canvas_id": cid},
            files={"file": ("new.xlsx", path.read_bytes(),
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet")},
        )
        assert upload.status_code == 404, upload.text
        assert sorted(p.name for p in office_root.iterdir()) == files_before
        assert _audit_count(probe, cid) == before_audit

    def test_canvas_data_upload_to_deleted_canvas_is_refused(
        self, app_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "data-upload.xlsx")
        cid = "canvas-deleted-data-upload"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_audit = _audit_count(probe, cid)

        response = _upload_xlsx(app_client.client, cid, path)
        assert response.status_code == 404, response.text
        assert _audit_count(probe, cid) == before_audit


# ---------------------------------------------------------------------------
# Scope / IDOR / optional-id negative controls
# ---------------------------------------------------------------------------
class TestScopeNegatives:
    def test_missing_and_foreign_canvas_download_are_refused(
        self, office_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "scope.xlsx")
        foreign = _make_xlsx(office_root / "foreign.xlsx")
        foreign_cid = "canvas-foreign"
        _bind_canvas(probe, canvas_id=foreign_cid, owner_id="someone-else",
                     file_path=foreign)
        before_sha = _sha(path)

        missing = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": "canvas-does-not-exist"},
        )
        assert missing.status_code == 404, missing.text

        idor = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(foreign), "canvas_id": foreign_cid},
        )
        assert idor.status_code == 404, idor.text

        # An omitted canvas id cannot downgrade the download to a path-only read.
        omitted = office_client.get(
            f"{OFFICE_PREFIX}/download", params={"file_path": str(path)})
        assert omitted.status_code == 422, omitted.text
        assert _sha(path) == before_sha

    def test_shared_file_bound_to_live_canvas_stays_available(
        self, office_client, probe, owner, office_root,
    ):
        """A deleted binding must not shadow a legitimate live binding."""
        path = _make_xlsx(office_root / "shared.xlsx")
        deleted_cid = "canvas-shared-deleted"
        live_cid = "canvas-shared-live"
        _bind_canvas(probe, canvas_id=deleted_cid, owner_id=owner.id,
                     file_path=path)
        _bind_canvas(probe, canvas_id=live_cid, owner_id=owner.id,
                     file_path=path)
        _tombstone(probe, canvas_id=deleted_cid, owner_id=owner.id)

        download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": live_cid},
        )
        assert download.status_code == 200, download.text
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 200, read.text


# ---------------------------------------------------------------------------
# Restore keeps the lifecycle contract (ownership != active state)
# ---------------------------------------------------------------------------
class TestRestoreAndHistory:
    def test_tombstone_gates_are_distinct_and_restore_reopens_boundaries(
        self, app_client, office_client, probe, owner, office_root,
        quiet_office_side_effects,
    ):
        from api.office_routes import _require_canvas_active, _require_canvas_owner
        from fastapi import HTTPException

        path = _make_xlsx(office_root / "restored.xlsx")
        cid = "canvas-restore-control"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)

        # Ownership still resolves for the owner on a deleted canvas...
        session = probe.Session()
        try:
            _require_canvas_owner(session, cid, owner)
            # ...while the separate active-state gate prevents effect.
            with pytest.raises(HTTPException) as refusal:
                _require_canvas_active(session, cid)
            assert refusal.value.status_code == 404
        finally:
            session.close()

        # Deleted: history survives and office boundaries refuse.
        history = app_client.client.get(f"/api/canvas/{cid}/history")
        assert history.status_code == 200, history.text
        assert history.json()["count"] >= 2
        assert any(row["action_type"] == "delete"
                   for row in history.json()["history"])
        assert office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        ).status_code == 404

        # Restore through the EXISTING canonical undelete route.
        restored = app_client.client.post(f"/api/canvas/{cid}/undelete")
        assert restored.status_code == 200, restored.text
        assert restored.json()["success"] is True

        download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert download.status_code == 200, download.text
        before = _audit_count(probe, cid)
        sync = office_client.post(
            f"{OFFICE_PREFIX}/sync-update",
            json={
                "canvas_id": cid, "file_path": str(path), "user_id": "x",
                "edit_type": "cell",
                "data": {"cell_path": "/Sheet1/A1", "value": 33},
            },
        )
        assert sync.status_code == 200, sync.text
        assert _audit_count(probe, cid) > before
        assert openpyxl.load_workbook(path)["Sheet1"]["A1"].value == 33


# ---------------------------------------------------------------------------
# Binding resolution must be COMPLETE (no serialized-JSON/name prefilter)
# ---------------------------------------------------------------------------
class TestCompleteBindingResolution:
    """A real canonical binding is never excluded by encoding or alias form.

    Observed 2026-11-14: SQLite stores JSON with ``ensure_ascii`` escapes, so
    the old text-``LIKE`` candidate filter missed ``résumé.xlsx`` after the
    canvas was deleted and ``GET /excel`` kept returning 200. Legacy relative
    and symlink aliases fail the same filter for a different reason: the
    stored string differs from the request even though ``_office_path_key``
    resolves both to one real target.
    """

    def test_unicode_filename_binding_is_found_and_refused_when_deleted(
        self, office_client, probe, owner, office_root,
    ):
        from api.office_routes import _bound_canvas_ids

        path = _make_xlsx(office_root / "résumé.xlsx")
        cid = "canvas-unicode-binding"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)

        session = probe.Session()
        try:
            assert _bound_canvas_ids(session, str(path)) == [cid]
        finally:
            session.close()

        live = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert live.status_code == 200, live.text
        assert live.json()["value"] == 12

        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)

        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 404, read.text
        formula = office_client.get(
            f"{OFFICE_PREFIX}/excel/formula-result",
            params={"file_path": str(path), "cell_path": "/Sheet1/C1"},
        )
        assert formula.status_code == 404, formula.text
        write = office_client.post(
            f"{OFFICE_PREFIX}/excel",
            json={
                "file_path": str(path), "cell_path": "/Sheet1/A1",
                "value": 999,
            },
        )
        assert write.status_code == 404, write.text
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_legacy_relative_binding_is_a_real_binding(
        self, office_client, probe, owner, tmp_path, monkeypatch,
    ):
        """A CWD-relative legacy binding resolves to the same real target."""
        from api.office_routes import _bound_canvas_ids

        office_dir = tmp_path / "data" / "office"
        office_dir.mkdir(parents=True)
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(office_dir))
        monkeypatch.chdir(tmp_path)

        path = _make_xlsx(office_dir / "legacy-relative.xlsx")
        legacy = "data/office/legacy-relative.xlsx"
        cid = "canvas-legacy-relative"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"office_file": legacy, "format": "xlsx"},
        )

        session = probe.Session()
        try:
            assert _bound_canvas_ids(session, str(path)) == [cid]
        finally:
            session.close()

        live_read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert live_read.status_code == 200, live_read.text
        live_download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert live_download.status_code == 200, live_download.text
        assert live_download.content == path.read_bytes()

        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)

        dead_read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert dead_read.status_code == 404, dead_read.text
        dead_download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert dead_download.status_code == 404, dead_download.text
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_symlink_alias_binding_resolves_to_real_target(
        self, office_client, probe, owner, office_root,
    ):
        from api.office_routes import _bound_canvas_ids

        real = _make_xlsx(office_root / "real-target.xlsx")
        alias = office_root / "alias-name.xlsx"
        alias.symlink_to(real)

        cid = "canvas-symlink-alias"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"office_file": str(alias), "format": "xlsx"},
        )

        session = probe.Session()
        try:
            assert _bound_canvas_ids(session, str(real)) == [cid]
        finally:
            session.close()

        live = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(real), "cell_path": "/Sheet1/A1"},
        )
        assert live.status_code == 200, live.text

        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(real)
        before_audit = _audit_count(probe, cid)

        dead = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(real), "cell_path": "/Sheet1/A1"},
        )
        assert dead.status_code == 404, dead.text
        dead_write = office_client.post(
            f"{OFFICE_PREFIX}/excel",
            json={
                "file_path": str(real), "cell_path": "/Sheet1/A1",
                "value": 999,
            },
        )
        assert dead_write.status_code == 404, dead_write.text
        assert _sha(real) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_unicode_and_alias_bindings_count_as_live_when_any_is_live(
        self, office_client, probe, owner, office_root,
    ):
        """A deleted alias binding must not shadow a live canonical binding."""
        real = _make_xlsx(office_root / "partagé.xlsx")
        alias = office_root / "shared-alias.xlsx"
        alias.symlink_to(real)

        deleted_cid = "canvas-shared-unicode-deleted"
        live_cid = "canvas-shared-alias-live"
        _bind_canvas_to_content(
            probe, canvas_id=deleted_cid, owner_id=owner.id,
            content={"office_file": str(real), "format": "xlsx"},
        )
        _bind_canvas_to_content(
            probe, canvas_id=live_cid, owner_id=owner.id,
            content={"office_file": str(alias), "format": "xlsx"},
        )
        _tombstone(probe, canvas_id=deleted_cid, owner_id=owner.id)

        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(real), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 200, read.text
        assert read.json()["value"] == 12

    def test_unbound_unicode_file_stays_available(
        self, office_client, owner, office_root,
    ):
        """No binding means no lifecycle to enforce — new/legacy files work."""
        path = _make_xlsx(office_root / "unbound-résumé.xlsx", value=5)
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 200, read.text
        assert read.json()["value"] == 5

    def test_binding_projection_ignores_non_mapping_content(
        self, probe, owner, office_root,
    ):
        """The projection is total: odd JSON shapes cannot hide a binding."""
        from api.office_routes import _bound_canvas_ids

        path = _make_xlsx(office_root / "shape-š.xlsx")
        cid = "canvas-shape-unicode"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        session = probe.Session()
        try:
            # Unrelated rows with list/string/scalar content are real legacy
            # shapes seen in the world; they must not abort the projection.
            for other_id, content in (
                ("canvas-list-content", ["résumé.xlsx"]),
                ("canvas-string-content", "office_file"),
                ("canvas-scalar-content", 42),
            ):
                _canvas(
                    session, canvas_id=other_id, owner_id=owner.id,
                    content=content,
                )
            session.commit()
            assert _bound_canvas_ids(session, str(path)) == [cid]
        finally:
            session.close()


class TestBindingLookupFailsClosed:
    def test_db_error_on_binding_lookup_refuses_path_only_read(
        self, office_client, probe, owner, office_root,
    ):
        """A DB failure is "cannot prove live" — refuse, never allow."""
        from core.models import Canvas

        path = _make_xlsx(office_root / "db-error.xlsx")
        cid = "canvas-db-error"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id, file_path=path)
        before_sha = _sha(path)

        # Simulate a real DB error after the request path is validated.
        Canvas.__table__.drop(bind=probe.engine)

        response = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "File binding lookup unavailable"
        assert _sha(path) == before_sha


# ---------------------------------------------------------------------------
# Capability exports are recognized READ bindings for lifecycle purposes
# ---------------------------------------------------------------------------
class TestCapabilityExportBindings:
    """A saved capability export is a recognized binding, but never a primary
    edit binding.

    ``core.canvas_capability_service.export_operation`` writes a saved XLSX
    target under ``ATOM_OFFICE_DIR`` and appends it to
    ``content["capability_exports"]``; ``download_office_file`` explicitly
    authorizes those paths. The path-only tombstone gate must resolve the
    same inventory, or a deleted export stays readable as "unbound" — the
    real negative observed at the previous head. Sync-update must keep
    requiring the primary ``office_file``/``file_path`` binding.
    """

    def test_export_only_binding_is_gated_after_tombstone(
        self, office_client, probe, owner, office_root,
    ):
        from api.office_routes import _bound_canvas_ids

        path = _make_xlsx(office_root / "capability-export.xlsx")
        cid = "canvas-export-only"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"capability_exports": [str(path)]},
        )

        session = probe.Session()
        try:
            assert _bound_canvas_ids(session, str(path)) == [cid]
        finally:
            session.close()

        active_download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert active_download.status_code == 200, active_download.text
        active_read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert active_read.status_code == 200, active_read.text

        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)

        download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert download.status_code == 404, download.text
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 404, read.text
        formula = office_client.get(
            f"{OFFICE_PREFIX}/excel/formula-result",
            params={"file_path": str(path), "cell_path": "/Sheet1/C1"},
        )
        assert formula.status_code == 404, formula.text
        write = office_client.post(
            f"{OFFICE_PREFIX}/excel",
            json={
                "file_path": str(path), "cell_path": "/Sheet1/A1",
                "value": 999,
            },
        )
        assert write.status_code == 404, write.text
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_export_only_is_readable_but_not_primary_editable(
        self, office_client, probe, owner, office_root,
    ):
        """Exported READ reference must not become a sync-update binding."""
        path = _make_xlsx(office_root / "export-read-only.xlsx")
        cid = "canvas-export-read-only"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"capability_exports": [str(path)]},
        )
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)

        assert office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        ).status_code == 200
        assert office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        ).status_code == 200

        sync = office_client.post(
            f"{OFFICE_PREFIX}/sync-update",
            json={
                "canvas_id": cid, "file_path": str(path), "user_id": "forged",
                "edit_type": "cell",
                "data": {"cell_path": "/Sheet1/A1", "value": 777},
            },
        )
        assert sync.status_code == 403, sync.text
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_unicode_export_path_is_gated(
        self, office_client, probe, owner, office_root,
    ):
        from api.office_routes import _bound_canvas_ids

        path = _make_xlsx(office_root / "résumé-export.xlsx")
        cid = "canvas-export-unicode"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"capability_exports": [str(path)]},
        )
        session = probe.Session()
        try:
            assert _bound_canvas_ids(session, str(path)) == [cid]
        finally:
            session.close()

        assert office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        ).status_code == 200

        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 404, read.text
        write = office_client.post(
            f"{OFFICE_PREFIX}/excel",
            json={
                "file_path": str(path), "cell_path": "/Sheet1/A1",
                "value": 999,
            },
        )
        assert write.status_code == 404, write.text
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_symlink_export_alias_is_gated(
        self, office_client, probe, owner, office_root,
    ):
        from api.office_routes import _bound_canvas_ids

        real = _make_xlsx(office_root / "export-real.xlsx")
        alias = office_root / "export-alias.xlsx"
        alias.symlink_to(real)
        cid = "canvas-export-alias"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"capability_exports": [str(alias)]},
        )
        session = probe.Session()
        try:
            assert _bound_canvas_ids(session, str(real)) == [cid]
        finally:
            session.close()

        assert office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(real), "cell_path": "/Sheet1/A1"},
        ).status_code == 200

        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(real)
        before_audit = _audit_count(probe, cid)
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(real), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 404, read.text
        assert _sha(real) == before_sha
        assert _audit_count(probe, cid) == before_audit

    def test_shared_live_primary_or_export_binding_keeps_file_available(
        self, office_client, probe, owner, office_root,
    ):
        # Deleted export + live primary: the primary keeps it live.
        primary_file = _make_xlsx(office_root / "shared-primary.xlsx")
        deleted_export_cid = "canvas-shared-deleted-export"
        live_primary_cid = "canvas-shared-live-primary"
        _bind_canvas_to_content(
            probe, canvas_id=deleted_export_cid, owner_id=owner.id,
            content={"capability_exports": [str(primary_file)]},
        )
        _bind_canvas(probe, canvas_id=live_primary_cid, owner_id=owner.id,
                     file_path=primary_file)
        _tombstone(probe, canvas_id=deleted_export_cid, owner_id=owner.id)
        assert office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(primary_file), "cell_path": "/Sheet1/A1"},
        ).status_code == 200

        # Deleted primary + live export: the export keeps it live too.
        export_file = _make_xlsx(office_root / "shared-export.xlsx")
        deleted_primary_cid = "canvas-shared-deleted-primary"
        live_export_cid = "canvas-shared-live-export"
        _bind_canvas(probe, canvas_id=deleted_primary_cid, owner_id=owner.id,
                     file_path=export_file)
        _bind_canvas_to_content(
            probe, canvas_id=live_export_cid, owner_id=owner.id,
            content={"capability_exports": [str(export_file)]},
        )
        _tombstone(probe, canvas_id=deleted_primary_cid, owner_id=owner.id)
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(export_file), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 200, read.text
        download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(export_file), "canvas_id": live_export_cid},
        )
        assert download.status_code == 200, download.text

    def test_restore_reopens_export_only_boundary(
        self, app_client, office_client, probe, owner, office_root,
        quiet_office_side_effects,
    ):
        path = _make_xlsx(office_root / "export-restored.xlsx")
        cid = "canvas-export-restore"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"capability_exports": [str(path)]},
        )
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        assert office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        ).status_code == 404

        restored = app_client.client.post(f"/api/canvas/{cid}/undelete")
        assert restored.status_code == 200, restored.text
        assert restored.json()["success"] is True

        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 200, read.text
        download = office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        )
        assert download.status_code == 200, download.text

        # Restore reopens READ access; it does not promote the export to a
        # primary edit binding.
        sync = office_client.post(
            f"{OFFICE_PREFIX}/sync-update",
            json={
                "canvas_id": cid, "file_path": str(path), "user_id": "x",
                "edit_type": "cell",
                "data": {"cell_path": "/Sheet1/A1", "value": 33},
            },
        )
        assert sync.status_code == 403, sync.text

    def test_export_array_is_complete_not_first_n(
        self, office_client, probe, owner, office_root,
    ):
        """The target at index 0 must be resolved; no reader-side slice."""
        from api.office_routes import _bound_canvas_ids

        path = _make_xlsx(office_root / "export-first-of-many.xlsx")
        exports = [str(path)] + [
            str(office_root / f"other-export-{index}.xlsx")
            for index in range(1, 13)
        ]
        cid = "canvas-export-first"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={"capability_exports": exports},
        )
        session = probe.Session()
        try:
            assert _bound_canvas_ids(session, str(path)) == [cid]
        finally:
            session.close()

        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 404, read.text

    def test_malformed_export_shapes_do_not_hide_string_members(
        self, office_client, probe, owner, office_root,
    ):
        from api.office_routes import _bound_canvas_ids, _export_keys_from_value

        path = _make_xlsx(office_root / "export-malformed.xlsx")

        # Non-string members beside a real reference must not hide it.
        junk_cid = "canvas-export-junk-members"
        _bind_canvas_to_content(
            probe, canvas_id=junk_cid, owner_id=owner.id,
            content={"capability_exports": [None, 7, {"path": "x"}, "", str(path)]},
        )
        # A legacy bare-string value is one reference, not invisible.
        bare_cid = "canvas-export-bare-string"
        _bind_canvas_to_content(
            probe, canvas_id=bare_cid, owner_id=owner.id,
            content={"capability_exports": str(path)},
        )
        session = probe.Session()
        try:
            assert set(_bound_canvas_ids(session, str(path))) == {
                junk_cid, bare_cid}
            assert _export_keys_from_value(None) == set()
            assert _export_keys_from_value([None, 3, "", " "]) == set()
            for shape in (42, {"path": str(path)}, [["nested"]]):
                # Malformed shapes are not invented references and must not
                # raise; valid string members are what count.
                _export_keys_from_value(shape)
        finally:
            session.close()

        _tombstone(probe, canvas_id=junk_cid, owner_id=owner.id)
        _tombstone(probe, canvas_id=bare_cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audits = {
            cid: _audit_count(probe, cid) for cid in (junk_cid, bare_cid)}
        read = office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        )
        assert read.status_code == 404, read.text
        assert _sha(path) == before_sha
        assert {cid: _audit_count(probe, cid) for cid in before_audits} == before_audits

    def test_primary_and_export_on_same_canvas_refuse_after_tombstone(
        self, office_client, probe, owner, office_root,
    ):
        path = _make_xlsx(office_root / "primary-and-export.xlsx")
        cid = "canvas-primary-and-export"
        _bind_canvas_to_content(
            probe, canvas_id=cid, owner_id=owner.id,
            content={
                "office_file": str(path),
                "capability_exports": [str(path)],
                "format": "xlsx",
            },
        )
        _tombstone(probe, canvas_id=cid, owner_id=owner.id)
        before_sha = _sha(path)
        before_audit = _audit_count(probe, cid)
        assert office_client.get(
            f"{OFFICE_PREFIX}/excel",
            params={"file_path": str(path), "cell_path": "/Sheet1/A1"},
        ).status_code == 404
        assert office_client.get(
            f"{OFFICE_PREFIX}/download",
            params={"file_path": str(path), "canvas_id": cid},
        ).status_code == 404
        assert _sha(path) == before_sha
        assert _audit_count(probe, cid) == before_audit


# ---------------------------------------------------------------------------
# Shared guard across DOCX / XLSX / PPTX (not a download-only fix)
# ---------------------------------------------------------------------------
class TestSharedFormatGuard:
    @pytest.mark.parametrize(
        "kind,path_name,canvas_type,read_route,make",
        [
            ("xlsx", "guard.xlsx", "sheets", "/excel", _make_xlsx),
            ("docx", "guard.docx", "docs", "/word", _make_docx),
            ("pptx", "guard.pptx", "presentation", "/pptx", _make_pptx),
        ],
    )
    def test_reads_are_refused_only_while_tombstoned(
        self, office_client, probe, owner, office_root,
        kind, path_name, canvas_type, read_route, make,
    ):
        path = make(office_root / path_name)
        cid = f"canvas-guard-{kind}"
        _bind_canvas(probe, canvas_id=cid, owner_id=owner.id,
                     file_path=path, canvas_type=canvas_type)

        live = office_client.get(
            f"{OFFICE_PREFIX}{read_route}", params={"file_path": str(path)})
        assert live.status_code == 200, live.text

        _tombstone(probe, canvas_id=cid, owner_id=owner.id,
                   canvas_type=canvas_type)
        dead = office_client.get(
            f"{OFFICE_PREFIX}{read_route}", params={"file_path": str(path)})
        assert dead.status_code == 404, dead.text


# ---------------------------------------------------------------------------
# The fix lives in the shared core gate, not in the download route
# ---------------------------------------------------------------------------
def test_core_authority_gate_refuses_deleted_canvas(probe, owner):
    from core.canvas_authority import CanvasAuthorityError, require_canvas_active
    from tools.canvas_crud_tool import deleted_canvas_ids

    session = probe.Session()
    try:
        _canvas(session, canvas_id="core-gate", owner_id=owner.id)
        _audit(session, canvas_id="core-gate", action_type="create",
               user_id=owner.id, details={"content": {"x": 1}},
               created_at=datetime.now(timezone.utc) - timedelta(minutes=2))
        require_canvas_active(session, "core-gate")  # live: no raise
        _audit(session, canvas_id="core-gate", action_type="delete",
               user_id=owner.id, details={},
               created_at=datetime.now(timezone.utc))
        assert deleted_canvas_ids(session, ["core-gate"]) == {"core-gate"}
        with pytest.raises(CanvasAuthorityError) as refusal:
            require_canvas_active(session, "core-gate")
        assert refusal.value.status_code == 404
        assert refusal.value.code == "CANVAS_DELETED"
    finally:
        session.close()
