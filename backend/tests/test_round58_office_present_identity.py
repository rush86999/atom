"""
Round 58 — Office /present + /sync-update: client-supplied user_id attribution
(Red-Green-Refactor).

present_coedit and sync_update pass req.user_id (client-supplied) into
broadcast_file_update / sync_canvas_to_file, which attribute CanvasAudit
records AND agent-memory ingestion to that user_id. Any authenticated user
can:

  - forge audit trails (canvas updates attributed to another user)
  - poison another user's memory store (document content ingested under a
    victim's user_id)

Fix: use the token identity (current_user.id); body field kept for backward
compat but ignored.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db_session


def make_client(monkeypatch, user_id="u-58"):
    from api.office_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
        id=user_id, email="u@example.com"
    )
    app.dependency_overrides[get_db_session] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


class TestOfficePresentIdentity:
    def test_present_uses_token_identity(self, monkeypatch):
        # R53 path containment: /present validates file_path against
        # ATOM_OFFICE_DIR (default ./data/office) before broadcasting.
        monkeypatch.setenv("ATOM_OFFICE_DIR", "/")
        client = make_client(monkeypatch)

        from core.office_sync_service import OfficeSyncService

        with patch.object(OfficeSyncService, "broadcast_file_update") as broadcast:
            resp = client.post(
                "/present",
                json={
                    "file_path": "/data/office/doc.docx",
                    "canvas_id": "c1",
                    "user_id": "victim-999",
                    "title": "Doc",
                },
            )

        assert resp.status_code == 200, resp.text
        broadcast.assert_called_once()
        assert broadcast.call_args.kwargs.get("user_id") == "u-58", (
            "broadcast_file_update was attributed to the client-supplied "
            f"user_id {broadcast.call_args.kwargs.get('user_id')!r} instead "
            "of the token identity"
        )

    def test_sync_update_uses_token_identity(self, monkeypatch):
        client = make_client(monkeypatch)

        from core.office_sync_service import OfficeSyncService

        with patch.object(
            OfficeSyncService, "sync_canvas_to_file",
            return_value={"success": True},
        ) as sync:
            resp = client.post(
                "/sync-update",
                json={
                    "canvas_id": "c1",
                    "file_path": "/data/office/book.xlsx",
                    "user_id": "victim-999",
                    "edit_type": "cell",
                    "data": {"cell_path": "/Sheet1/A1", "value": 1},
                },
            )

        assert resp.status_code == 200, resp.text
        sync.assert_called_once()
        assert sync.call_args.kwargs.get("user_id") == "u-58", (
            "sync_canvas_to_file was attributed to the client-supplied "
            f"user_id {sync.call_args.kwargs.get('user_id')!r} instead of "
            "the token identity"
        )

    def test_broadcast_audits_token_identity(self, monkeypatch, tmp_path):
        """End-to-end: the CanvasAudit row carries the authenticated user."""
        monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
        f = tmp_path / "office" / "doc.docx"
        f.parent.mkdir()
        f.write_bytes(b"dummy")

        db = MagicMock()
        from core.office_sync_service import OfficeSyncService

        with patch(
            "core.office_service.DocumentRenderer.render_to_html",
            return_value={"success": True, "html": "<p>hi</p>"},
        ), patch.object(OfficeSyncService, "_ingest_document_to_memory_sync"), patch(
            "core.office_sync_service.ws_manager.broadcast", new=AsyncMock()
        ):
            OfficeSyncService(db).broadcast_file_update("c1", str(f), "u-58")

        added = [a.args[0] for a in db.add.call_args_list]
        assert added, "CanvasAudit row was not written"
        audit = added[0]
        assert getattr(audit, "user_id", None) == "u-58", (
            f"CanvasAudit attributed to {getattr(audit, 'user_id', None)!r}"
        )
