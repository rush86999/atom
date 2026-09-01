"""POST /api/chat/to-canvas — owner's canvas_type override.

Regression context (Sep 1, 2026): "Open latest draft in canvas" classified
an email-shaped draft as a document canvas with no way to change it. The
route now accepts canvas_type "email"/"document" to force the type ("auto"
keeps the classifier), and the chat UI carries a type picker.
"""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from integrations.chat_routes import router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.models import Base, Canvas


EMAIL_SHAPED = (
    "To: mark@example.com\n"
    "Subject: Quote follow-up\n\n"
    "Hi Mark, following up on the quote — the lead time is 6 weeks."
)
PLAIN_DOC = "Here is a summary of the meeting notes for the team."


@pytest.fixture()
def db_session():
    """Thread-safe sqlite session (TestClient runs the app off-thread)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)
    session = Sess()
    try:
        yield session
    finally:
        session.close()
        eng.dispose()
        os.unlink(path)


def _make_client(db_session):
    app = FastAPI()
    app.include_router(router)

    user = type("U", (), {
        "id": "type-user-1",
        "tenant_id": None,
        "workspaces": [],
        "status": "active",
    })()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=False)


def _last_canvas(db_session) -> Canvas:
    return (
        db_session.query(Canvas)
        .order_by(Canvas.created_at.desc())
        .first()
    )


def test_explicit_email_type_forces_email_canvas(db_session):
    """A plain (non-email-detected) draft opened with the Email choice must
    still land in a typed email canvas the composer can render."""
    client = _make_client(db_session)
    resp = client.post("/api/chat/to-canvas", json={
        "content": PLAIN_DOC,
        "title": "Draft — meeting notes",
        "canvas_type": "email",
    })
    assert resp.status_code == 200, resp.text

    canvas = _last_canvas(db_session)
    assert canvas.canvas_type == "email"
    assert isinstance(canvas.content, dict)
    assert "body" in canvas.content


def test_explicit_document_type_keeps_document(db_session):
    """Email-SHAPED content with the Document choice stays a plain document —
    the owner's pick outranks the classifier."""
    client = _make_client(db_session)
    resp = client.post("/api/chat/to-canvas", json={
        "content": EMAIL_SHAPED,
        "title": "Draft — quote follow-up",
        "canvas_type": "document",
    })
    assert resp.status_code == 200, resp.text

    canvas = _last_canvas(db_session)
    assert canvas.canvas_type == "document"
    assert isinstance(canvas.content, dict)
    assert canvas.content.get("content") == EMAIL_SHAPED


def test_auto_still_classifies_email(db_session):
    """Default (no canvas_type) keeps the existing email-draft heuristic."""
    client = _make_client(db_session)
    resp = client.post("/api/chat/to-canvas", json={
        "content": EMAIL_SHAPED,
        "title": "Draft — quote follow-up",
    })
    assert resp.status_code == 200, resp.text

    canvas = _last_canvas(db_session)
    assert canvas.canvas_type == "email"
    assert canvas.content.get("to") == "mark@example.com"


def test_forced_specialized_app_type_passthrough(db_session):
    """The full canvas-app vocabulary is accepted (recommended-first UI):
    a forced non-email app takes the draft as text content."""
    client = _make_client(db_session)
    resp = client.post("/api/chat/to-canvas", json={
        "content": "step,owner\n1,me",
        "title": "Draft — tracker",
        "canvas_type": "sheet",
    })
    assert resp.status_code == 200, resp.text
    canvas = _last_canvas(db_session)
    assert canvas.canvas_type == "sheet"


def test_unknown_canvas_type_rejected(db_session):
    client = _make_client(db_session)
    resp = client.post("/api/chat/to-canvas", json={
        "content": "x", "title": "t", "canvas_type": "hologram",
    })
    assert resp.status_code == 400
    assert "Unsupported canvas_type" in resp.json()["detail"]
