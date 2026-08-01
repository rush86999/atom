"""
Round 66 — Canvas docs/terminal/email: missing auth + identity spoofing + IDOR
(Red-Green-Refactor).

The canvas-family routers (mounted: /api/canvas/docs, /api/canvas/terminal,
/api/canvas/email) share the R24-era auth fix but still have gaps:

  A. canvas_docs add_comment + resolve_comment have NO auth dependency at
     all — unauthenticated comment write/resolve on any document canvas.
  B. canvas_docs create + update use the client-supplied request.user_id
     (attribution spoofing, R42 class).
  C. canvas_docs get, canvas_terminal get/add_output, canvas_email get —
     no ownership check: any authenticated user reads/writes any canvas
     (terminal output, email drafts, document content).

Fix: auth + token identity on docs comment endpoints; ownership gates on
all canvas-id endpoints (owner = earliest CanvasAudit row for the canvas).
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


def make_client(auth=True, db=None):
    from api.canvas_docs_routes import router as docs_router

    app = FastAPI()
    app.include_router(docs_router)
    if auth:
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-66", email="u@example.com"
        )
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    else:
        app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def _canvas_row(user_id="u-66", canvas_id="c1"):
    row = MagicMock()
    row.id = "audit-1"
    row.user_id = user_id
    row.canvas_id = canvas_id
    row.canvas_type = "docs"
    row.details_json = {"content": "hi"}
    return row


class TestCanvasDocsAuth:
    def test_add_comment_requires_auth(self):
        client = make_client(auth=False)
        resp = client.post(
            "/api/canvas/docs/c1/comment",
            json={"user_id": "u-66", "content": "hi"},
        )
        assert resp.status_code == 401, (
            f"add_comment allowed an unauthenticated write (got {resp.status_code})"
        )

    def test_resolve_comment_requires_auth(self):
        client = make_client(auth=False)
        resp = client.post(
            "/api/canvas/docs/c1/comment/resolve",
            json={"user_id": "u-66", "comment_id": "cm-1"},
        )
        assert resp.status_code == 401, (
            f"resolve_comment allowed an unauthenticated write "
            f"(got {resp.status_code})"
        )

    def test_create_uses_token_identity(self):
        client = make_client()

        with patch(
            "core.canvas_docs_service.DocumentationCanvasService.create_document_canvas",
            return_value={"success": True, "canvas_id": "c1"},
        ) as create:
            resp = client.post(
                "/api/canvas/docs/create",
                json={
                    "user_id": "victim-999",
                    "title": "Doc",
                    "content": "body",
                },
            )

        assert resp.status_code == 200, resp.text
        create.assert_called_once()
        assert create.call_args.kwargs.get("user_id") == "u-66", (
            "create_document_canvas was attributed to the client-supplied "
            f"user_id {create.call_args.kwargs.get('user_id')!r}"
        )

    def test_get_document_denies_other_users_canvas(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            _canvas_row(user_id="victim-999")
        )
        client = make_client(db=db)

        resp = client.get("/api/canvas/docs/c1")

        assert resp.status_code == 403, (
            f"get_document_canvas exposed another user's document (got {resp.status_code})"
        )


class TestCanvasTerminalOwnership:
    def _client(self, db):
        from api.canvas_terminal_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-66", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app, raise_server_exceptions=False)

    def test_get_terminal_denies_other_users_canvas(self):
        row = _canvas_row(user_id="victim-999", canvas_id="c1")
        row.canvas_type = "terminal"
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        client = self._client(db)

        resp = client.get("/api/canvas/terminal/c1")

        assert resp.status_code == 403, (
            f"get_terminal_canvas exposed another user's terminal output "
            f"(got {resp.status_code})"
        )

    def test_add_output_denies_other_users_canvas(self):
        row = _canvas_row(user_id="victim-999", canvas_id="c1")
        row.canvas_type = "terminal"
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        client = self._client(db)

        from core.canvas_terminal_service import TerminalCanvasService

        with patch.object(
            TerminalCanvasService, "add_output"
        ) as add:
            resp = client.post(
                "/api/canvas/terminal/c1/output",
                json={
                    "user_id": "victim-999",
                    "command": "ls",
                    "output": "secret",
                    "exit_code": 0,
                },
            )

        assert resp.status_code == 403, (
            f"add_output wrote to another user's terminal canvas (got {resp.status_code})"
        )
        add.assert_not_called()


class TestCanvasEmailOwnership:
    def test_get_email_denies_other_users_canvas(self):
        from api.canvas_email_routes import router

        row = _canvas_row(user_id="victim-999", canvas_id="c1")
        row.canvas_type = "email"
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-66", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/canvas/email/c1")

        assert resp.status_code == 403, (
            f"get_email_canvas exposed another user's email canvas (got {resp.status_code})"
        )
