"""Coverage wave 64g — canvas-family route modules to >=95% (TDD).

Targets (standalone probe = this file only):
- api/canvas_email_routes.py    (~81 stmts, before ~81%)
- api/canvas_coding_routes.py   (~58 stmts, before ~90%)
- api/canvas_terminal_routes.py (~54 stmts, before ~54% — existing suite is
  broken: real main app, no auth override → every POST 401)
- api/canvas_sheets_routes.py   (~59 stmts, before ~90%)
- api/canvas_skill_routes.py    (~26 stmts, before ~62% — existing unit suite
  is phantom: /execute endpoints don't exist, module-level skip)
- api/debug_routes.py           (~322 stmts, stamped 92% in W49; remaining
  gaps: error-patterns first/last_seen updates (655/657), disabled-mode for
  error-rate (816) and ai/query (847))
- api/canvas_recording_routes.py(~133 stmts, stamped 92% in wave 10f; the
  w56/w10f suites are separate files so this file re-covers the surface
  standalone)

Pattern: FastAPI TestClient with one app hosting all 7 routers,
dependency_overrides on core.auth.get_current_user (the canonical function
object — core.security_dependencies re-exports the same object, so the
override applies to every router) + core.database.get_db. Real SQLite
in-memory DB via StaticPool; zero LLM spend / no network / no real writes.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api import (
    canvas_coding_routes,
    canvas_email_routes,
    canvas_recording_routes,
    canvas_sheets_routes,
    canvas_skill_routes,
    canvas_terminal_routes,
    debug_routes,
)
from core.database import Base
from core.models import (
    CanvasAudit,
    CanvasComponent,
    CanvasRecording,
    DebugEvent,
    DebugInsight,
    DebugSession,
    Skill,
    User,
)


@pytest.fixture(scope="module")
def engine():
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(path)


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user(db):
    uid = f"w64g-{uuid.uuid4().hex[:8]}"
    u = User(
        id=uid, email=f"{uid}@x.com",
        hashed_password="h", first_name="G", last_name="U",
        role="member", status="active", tenant_id="t-1")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, user):
    app = FastAPI()
    app.include_router(canvas_email_routes.router)
    app.include_router(canvas_coding_routes.router)
    app.include_router(canvas_terminal_routes.router)
    app.include_router(canvas_sheets_routes.router)
    app.include_router(canvas_skill_routes.router)
    app.include_router(debug_routes.router)
    app.include_router(canvas_recording_routes.router)

    from core.auth import get_current_user
    from core.database import get_db

    def _get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


def _audit(db, user, canvas_id, canvas_type, details=None, action_type="canvas_open"):
    row = CanvasAudit(
        id=f"ca-{uuid.uuid4().hex[:8]}", canvas_id=canvas_id,
        tenant_id="t-1", action_type=action_type,
        user_id=user.id, canvas_type=canvas_type,
        details_json=details)
    db.add(row)
    db.commit()
    return row


def _other_user(db):
    uid = f"other-{uuid.uuid4().hex[:8]}"
    u = User(
        id=uid, email=f"{uid}@x.com",
        hashed_password="h", first_name="O", last_name="U",
        role="member", status="active", tenant_id="t-1")
    db.add(u)
    db.commit()
    return u


# ============================================================================
# api/canvas_email_routes.py
# ============================================================================

class TestEmailCreate:
    def test_create_success(self, client, user):
        svc = MagicMock()
        svc.create_email_canvas.return_value = {"success": True,
                                                "canvas_id": "ec-1"}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/create", json={
                "user_id": "spoofed",
                "subject": "Hello", "recipients": ["a@x.com"],
                "canvas_id": "c-1", "agent_id": "ag-1",
                "layout": "conversation", "template": "tpl"})
        assert response.status_code == 200
        assert response.json()["canvas_id"] == "ec-1"
        kwargs = svc.create_email_canvas.call_args.kwargs
        assert kwargs["user_id"] == user.id  # body user_id ignored
        assert kwargs["subject"] == "Hello"
        assert kwargs["recipients"] == ["a@x.com"]
        assert kwargs["layout"] == "conversation"

    def test_create_failure_400(self, client):
        svc = MagicMock()
        svc.create_email_canvas.return_value = {"success": False,
                                                "error": "boom"}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/create", json={
                "user_id": "u", "subject": "S", "recipients": ["a@x.com"]})
        assert response.status_code == 400
        assert "EMAIL_CANVAS_CREATE_FAILED" in response.text

    def test_create_missing_fields_422(self, client):
        response = client.post("/api/canvas/email/create", json={})
        assert response.status_code == 422


class TestEmailMessage:
    def test_message_success(self, client, user):
        svc = MagicMock()
        svc.add_message_to_thread.return_value = {"success": True}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/ec-1/message", json={
                "user_id": "spoofed", "from_email": "me@x.com",
                "to_emails": ["a@x.com"], "subject": "re", "body": "b",
                "attachments": [{"name": "f.txt"}]})
        assert response.status_code == 200
        kwargs = svc.add_message_to_thread.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["canvas_id"] == "ec-1"
        assert kwargs["attachments"] == [{"name": "f.txt"}]

    def test_message_failure_400(self, client):
        svc = MagicMock()
        svc.add_message_to_thread.return_value = {"success": False,
                                                  "error": "nope"}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/ec-1/message", json={
                "user_id": "u", "from_email": "me@x.com",
                "to_emails": ["a@x.com"], "subject": "re", "body": "b"})
        assert response.status_code == 400
        assert "EMAIL_MESSAGE_ADD_FAILED" in response.text

    def test_message_missing_fields_422(self, client):
        response = client.post("/api/canvas/email/ec-1/message", json={
            "user_id": "u", "from_email": "m@x.com"})
        assert response.status_code == 422


class TestEmailDraft:
    def test_draft_success(self, client, user):
        svc = MagicMock()
        svc.save_draft.return_value = {"success": True}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/ec-1/draft", json={
                "user_id": "spoofed", "to_emails": ["a@x.com"],
                "cc_emails": ["b@x.com"], "subject": "d", "body": "x"})
        assert response.status_code == 200
        kwargs = svc.save_draft.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["cc_emails"] == ["b@x.com"]

    def test_draft_failure_400(self, client):
        svc = MagicMock()
        svc.save_draft.return_value = {"success": False, "error": "boom"}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/ec-1/draft", json={
                "user_id": "u", "to_emails": ["a@x.com"]})
        assert response.status_code == 400
        assert "EMAIL_DRAFT_SAVE_FAILED" in response.text

    def test_draft_missing_fields_422(self, client):
        response = client.post("/api/canvas/email/ec-1/draft", json={
            "user_id": "u"})
        assert response.status_code == 422


class TestEmailCategorize:
    def test_categorize_success(self, client, user):
        svc = MagicMock()
        svc.categorize_email.return_value = {"success": True}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/ec-1/categorize", json={
                "user_id": "spoofed", "category": "work", "color": "#fff"})
        assert response.status_code == 200
        kwargs = svc.categorize_email.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["category"] == "work"
        assert kwargs["color"] == "#fff"

    def test_categorize_failure_400(self, client):
        svc = MagicMock()
        svc.categorize_email.return_value = {"success": False,
                                             "error": "no"}
        with patch("api.canvas_email_routes.EmailCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/email/ec-1/categorize", json={
                "user_id": "u", "category": "work"})
        assert response.status_code == 400
        assert "EMAIL_CATEGORIZE_FAILED" in response.text

    def test_categorize_missing_fields_422(self, client):
        response = client.post("/api/canvas/email/ec-1/categorize", json={
            "user_id": "u"})
        assert response.status_code == 422


class TestEmailGet:
    def test_get_success_details(self, client, db, user):
        _audit(db, user, "ec-2", "email",
               details={"subject": "S", "messages": []})
        response = client.get("/api/canvas/email/ec-2")
        assert response.status_code == 200
        assert response.json()["subject"] == "S"

    def test_get_success_empty_details(self, client, db, user):
        _audit(db, user, "ec-3", "email", details=None)
        response = client.get("/api/canvas/email/ec-3")
        assert response.status_code == 200
        assert response.json() == {}

    def test_get_not_found_404(self, client, db):
        response = client.get("/api/canvas/email/ghost")
        assert response.status_code == 404

    def test_get_ownership_denied_403(self, client, db, user):
        other = _other_user(db)
        _audit(db, other, "ec-4", "email", details={"x": 1})
        response = client.get("/api/canvas/email/ec-4")
        assert response.status_code == 403

    def test_get_wrong_canvas_type_404(self, client, db, user):
        # audit rows exist but none with canvas_type="email"
        _audit(db, user, "ec-5", "sheets", details={"x": 1})
        response = client.get("/api/canvas/email/ec-5")
        assert response.status_code == 404


# ============================================================================
# api/canvas_coding_routes.py
# ============================================================================

class TestCodingCreate:
    def test_create_success(self, client, user):
        svc = MagicMock()
        svc.create_coding_canvas.return_value = {"success": True,
                                                 "canvas_id": "cc-1"}
        with patch("api.canvas_coding_routes.CodingCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/coding/create", json={
                "user_id": "spoofed", "repo": "acme/app", "branch": "main",
                "canvas_id": "c-1", "agent_id": "ag-1", "layout": "repo_view"})
        assert response.status_code == 200
        assert response.json()["data"]["canvas_id"] == "cc-1"
        kwargs = svc.create_coding_canvas.call_args.kwargs
        assert kwargs["user_id"] == str(user.id)  # body user_id ignored
        assert kwargs["repo"] == "acme/app"
        assert kwargs["layout"] == "repo_view"

    def test_create_failure_400(self, client):
        svc = MagicMock()
        svc.create_coding_canvas.return_value = {"success": False,
                                                 "error": "boom"}
        with patch("api.canvas_coding_routes.CodingCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/coding/create", json={
                "user_id": "u", "repo": "r", "branch": "b"})
        assert response.status_code == 400
        assert "CODING_CANVAS_CREATE_FAILED" in response.text

    def test_create_missing_fields_422(self, client):
        response = client.post("/api/canvas/coding/create", json={
            "user_id": "u"})
        assert response.status_code == 422


class TestCodingFile:
    def test_add_file_success(self, client, user):
        svc = MagicMock()
        svc.add_file.return_value = {"success": True}
        with patch("api.canvas_coding_routes.CodingCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/coding/cc-1/file", json={
                "user_id": "spoofed", "path": "src/main.py",
                "content": "print(1)", "language": "python"})
        assert response.status_code == 200
        assert response.json()["message"].startswith("File src/main.py")
        kwargs = svc.add_file.call_args.kwargs
        assert kwargs["user_id"] == str(user.id)
        assert kwargs["language"] == "python"

    def test_add_file_failure_400(self, client):
        svc = MagicMock()
        svc.add_file.return_value = {"success": False, "error": "x"}
        with patch("api.canvas_coding_routes.CodingCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/coding/cc-1/file", json={
                "user_id": "u", "path": "a.py", "content": "c"})
        assert response.status_code == 400
        assert "ADD_FILE_FAILED" in response.text

    def test_add_file_missing_fields_422(self, client):
        response = client.post("/api/canvas/coding/cc-1/file", json={
            "user_id": "u", "path": "a.py"})
        assert response.status_code == 422


class TestCodingDiff:
    def test_add_diff_success(self, client, user):
        svc = MagicMock()
        svc.add_diff.return_value = {"success": True}
        with patch("api.canvas_coding_routes.CodingCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/coding/cc-1/diff", json={
                "user_id": "spoofed", "file_path": "a.py",
                "old_content": "x", "new_content": "y"})
        assert response.status_code == 200
        assert response.json()["message"].startswith("Diff for a.py")
        kwargs = svc.add_diff.call_args.kwargs
        assert kwargs["user_id"] == str(user.id)
        assert kwargs["file_path"] == "a.py"

    def test_add_diff_failure_400(self, client):
        svc = MagicMock()
        svc.add_diff.return_value = {"success": False, "error": "x"}
        with patch("api.canvas_coding_routes.CodingCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/coding/cc-1/diff", json={
                "user_id": "u", "file_path": "a.py",
                "old_content": "x", "new_content": "y"})
        assert response.status_code == 400
        assert "ADD_DIFF_FAILED" in response.text

    def test_add_diff_missing_fields_422(self, client):
        response = client.post("/api/canvas/coding/cc-1/diff", json={
            "user_id": "u", "file_path": "a.py"})
        assert response.status_code == 422


class TestCodingGet:
    def test_get_success(self, client, db, user):
        _audit(db, user, "cc-2", "coding",
               details={"repo": "acme/app", "files": ["a.py"]})
        response = client.get("/api/canvas/coding/cc-2")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["repo"] == "acme/app"
        assert data["message"] == "Coding canvas retrieved successfully"

    def test_get_success_empty_details(self, client, db, user):
        _audit(db, user, "cc-3", "coding", details=None)
        response = client.get("/api/canvas/coding/cc-3")
        assert response.status_code == 200
        assert response.json()["data"] == {}

    def test_get_not_found_404(self, client, db):
        response = client.get("/api/canvas/coding/ghost")
        assert response.status_code == 404

    def test_get_wrong_canvas_type_404(self, client, db, user):
        _audit(db, user, "cc-4", "email", details={"x": 1})
        response = client.get("/api/canvas/coding/cc-4")
        assert response.status_code == 404


# ============================================================================
# api/canvas_terminal_routes.py
# ============================================================================

class TestTerminalCreate:
    def test_create_success(self, client, user):
        svc = MagicMock()
        svc.create_terminal_canvas.return_value = {"success": True,
                                                   "canvas_id": "tc-1"}
        with patch("api.canvas_terminal_routes.TerminalCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/terminal/create", json={
                "user_id": "spoofed", "command": "ls -la",
                "canvas_id": "c-1", "agent_id": "ag-1",
                "working_dir": "/home"})
        assert response.status_code == 200
        assert response.json()["data"]["canvas_id"] == "tc-1"
        kwargs = svc.create_terminal_canvas.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["working_dir"] == "/home"

    def test_create_failure_400(self, client):
        svc = MagicMock()
        svc.create_terminal_canvas.return_value = {"success": False,
                                                   "error": "boom"}
        with patch("api.canvas_terminal_routes.TerminalCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/terminal/create", json={
                "user_id": "u", "command": "ls"})
        assert response.status_code == 400
        assert "TERMINAL_CANVAS_CREATE_FAILED" in response.text

    def test_create_missing_fields_422(self, client):
        response = client.post("/api/canvas/terminal/create", json={
            "user_id": "u"})
        assert response.status_code == 422


class TestTerminalOutput:
    def _patch_svc(self, **kw):
        svc = MagicMock()
        svc.add_output.return_value = {"success": True}
        for k, v in kw.items():
            setattr(svc, k, v)
        return patch("api.canvas_terminal_routes.TerminalCanvasService",
                     return_value=svc), svc

    def test_add_output_success(self, client, db, user):
        _audit(db, user, "tc-2", "terminal", details={})
        p, svc = self._patch_svc()
        with p:
            response = client.post("/api/canvas/terminal/tc-2/output", json={
                "user_id": "spoofed", "command": "ls", "output": "out",
                "exit_code": 0})
        assert response.status_code == 200
        kwargs = svc.add_output.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["exit_code"] == 0

    def test_add_output_failure_400(self, client, db, user):
        _audit(db, user, "tc-3", "terminal", details={})
        p, svc = self._patch_svc()
        svc.add_output.return_value = {"success": False, "error": "x"}
        with p:
            response = client.post("/api/canvas/terminal/tc-3/output", json={
                "user_id": "u", "command": "ls", "output": "o"})
        assert response.status_code == 400
        assert "ADD_OUTPUT_FAILED" in response.text

    def test_add_output_gate_not_found_404(self, client, db):
        p, svc = self._patch_svc()
        with p:
            response = client.post("/api/canvas/terminal/ghost/output", json={
                "user_id": "u", "command": "ls", "output": "o"})
        assert response.status_code == 404

    def test_add_output_gate_ownership_403(self, client, db, user):
        other = _other_user(db)
        _audit(db, other, "tc-4", "terminal", details={})
        p, svc = self._patch_svc()
        with p:
            response = client.post("/api/canvas/terminal/tc-4/output", json={
                "user_id": "u", "command": "ls", "output": "o"})
        assert response.status_code == 403

    def test_add_output_missing_fields_422(self, client, db, user):
        _audit(db, user, "tc-5", "terminal", details={})
        response = client.post("/api/canvas/terminal/tc-5/output", json={
            "user_id": "u", "command": "ls"})
        assert response.status_code == 422


class TestTerminalGet:
    def test_get_success(self, client, db, user):
        _audit(db, user, "tc-6", "terminal",
               details={"command": "ls", "output": "x"})
        response = client.get("/api/canvas/terminal/tc-6")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["command"] == "ls"
        assert data["message"] == "Terminal canvas retrieved successfully"

    def test_get_success_empty_details(self, client, db, user):
        _audit(db, user, "tc-7", "terminal", details=None)
        response = client.get("/api/canvas/terminal/tc-7")
        assert response.status_code == 200
        assert response.json()["data"] == {}

    def test_get_gate_not_found_404(self, client, db):
        response = client.get("/api/canvas/terminal/ghost")
        assert response.status_code == 404

    def test_get_gate_ownership_403(self, client, db, user):
        other = _other_user(db)
        _audit(db, other, "tc-8", "terminal", details={})
        response = client.get("/api/canvas/terminal/tc-8")
        assert response.status_code == 403

    def test_get_wrong_canvas_type_404(self, client, db, user):
        _audit(db, user, "tc-9", "email", details={})
        response = client.get("/api/canvas/terminal/tc-9")
        assert response.status_code == 404


# ============================================================================
# api/canvas_sheets_routes.py
# ============================================================================

class TestSheetsCreate:
    def test_create_success(self, client, user):
        svc = MagicMock()
        svc.create_spreadsheet_canvas.return_value = {"success": True,
                                                      "canvas_id": "sc-1"}
        with patch("api.canvas_sheets_routes.SpreadsheetCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/sheets/create", json={
                "user_id": "spoofed", "title": "Budget",
                "data": {"A1": 1}, "canvas_id": "c-1", "agent_id": "ag-1",
                "layout": "sheet", "formulas": ["=SUM(A1)"]})
        assert response.status_code == 200
        assert response.json()["canvas_id"] == "sc-1"
        kwargs = svc.create_spreadsheet_canvas.call_args.kwargs
        assert kwargs["user_id"] == user.id  # body user_id ignored
        assert kwargs["formulas"] == ["=SUM(A1)"]

    def test_create_failure_400(self, client):
        svc = MagicMock()
        svc.create_spreadsheet_canvas.return_value = {"success": False,
                                                      "error": "boom"}
        with patch("api.canvas_sheets_routes.SpreadsheetCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/sheets/create", json={
                "user_id": "u", "title": "T", "data": {}})
        assert response.status_code == 400
        assert "SPREADSHEET_CREATE_FAILED" in response.text

    def test_create_missing_fields_422(self, client):
        response = client.post("/api/canvas/sheets/create", json={
            "user_id": "u", "title": "T"})
        assert response.status_code == 422


class TestSheetsCell:
    def test_update_cell_success(self, client, user):
        svc = MagicMock()
        svc.update_cell.return_value = {"success": True}
        with patch("api.canvas_sheets_routes.SpreadsheetCanvasService",
                   return_value=svc):
            response = client.put("/api/canvas/sheets/sc-1/cell", json={
                "user_id": "spoofed", "cell_ref": "A1", "value": 5,
                "cell_type": "number", "formula": None})
        assert response.status_code == 200
        kwargs = svc.update_cell.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["cell_ref"] == "A1"
        assert kwargs["value"] == 5

    def test_update_cell_failure_400(self, client):
        svc = MagicMock()
        svc.update_cell.return_value = {"success": False, "error": "x"}
        with patch("api.canvas_sheets_routes.SpreadsheetCanvasService",
                   return_value=svc):
            response = client.put("/api/canvas/sheets/sc-1/cell", json={
                "user_id": "u", "cell_ref": "A1", "value": 5})
        assert response.status_code == 400
        assert "CELL_UPDATE_FAILED" in response.text

    def test_update_cell_missing_fields_422(self, client):
        response = client.put("/api/canvas/sheets/sc-1/cell", json={
            "user_id": "u"})
        assert response.status_code == 422


class TestSheetsChart:
    def test_add_chart_success(self, client, user):
        svc = MagicMock()
        svc.add_chart.return_value = {"success": True}
        with patch("api.canvas_sheets_routes.SpreadsheetCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/sheets/sc-1/chart", json={
                "user_id": "spoofed", "chart_type": "bar",
                "data_range": "A1:B4", "title": "T"})
        assert response.status_code == 200
        kwargs = svc.add_chart.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["chart_type"] == "bar"
        assert kwargs["data_range"] == "A1:B4"

    def test_add_chart_failure_400(self, client):
        svc = MagicMock()
        svc.add_chart.return_value = {"success": False, "error": "x"}
        with patch("api.canvas_sheets_routes.SpreadsheetCanvasService",
                   return_value=svc):
            response = client.post("/api/canvas/sheets/sc-1/chart", json={
                "user_id": "u", "chart_type": "bar", "data_range": "A1:B4"})
        assert response.status_code == 400
        assert "CHART_ADD_FAILED" in response.text

    def test_add_chart_missing_fields_422(self, client):
        response = client.post("/api/canvas/sheets/sc-1/chart", json={
            "user_id": "u", "chart_type": "bar"})
        assert response.status_code == 422


class TestSheetsGet:
    def test_get_success(self, client, db, user):
        _audit(db, user, "sc-2", "sheets",
               details={"title": "Budget", "cells": {"A1": 1}})
        response = client.get("/api/canvas/sheets/sc-2")
        assert response.status_code == 200
        assert response.json()["cells"]["A1"] == 1

    def test_get_success_empty_details(self, client, db, user):
        _audit(db, user, "sc-3", "sheets", details=None)
        response = client.get("/api/canvas/sheets/sc-3")
        assert response.status_code == 200
        assert response.json() == {}

    def test_get_not_found_404(self, client, db):
        response = client.get("/api/canvas/sheets/ghost")
        assert response.status_code == 404

    def test_get_wrong_canvas_type_404(self, client, db, user):
        _audit(db, user, "sc-4", "docs", details={"x": 1})
        response = client.get("/api/canvas/sheets/sc-4")
        assert response.status_code == 404


# ============================================================================
# api/canvas_skill_routes.py
# ============================================================================

class TestSkillCreate:
    def test_create_success(self, client, user):
        svc = MagicMock()
        svc.create_component_with_skill = AsyncMock(
            return_value={"success": True, "component_id": "comp-1"})
        with patch("api.canvas_skill_routes.CanvasSkillIntegrationService",
                   return_value=svc):
            response = client.post(
                "/canvas-skills/create?tenant_id=t-1&agent_id=ag-1",
                json={"component_data": {"name": "Chart", "type": "html"},
                      "skill_data": {"name": "draw", "type": "function"}})
        assert response.status_code == 200
        assert response.json()["component_id"] == "comp-1"
        kwargs = svc.create_component_with_skill.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["tenant_id"] == "t-1"
        assert kwargs["agent_id"] == "ag-1"
        assert kwargs["component_data"]["name"] == "Chart"

    def test_create_missing_fields_422(self, client):
        response = client.post(
            "/canvas-skills/create?tenant_id=t-1&agent_id=ag-1", json={})
        assert response.status_code == 422


class TestSkillInstall:
    def test_install_success(self, client, user):
        svc = MagicMock()
        svc.install_component_to_tenant = AsyncMock(
            return_value={"success": True, "installed": True})
        with patch("api.canvas_skill_routes.CanvasSkillIntegrationService",
                   return_value=svc):
            response = client.post(
                "/canvas-skills/install/comp-1?tenant_id=t-1&canvas_id=c-1")
        assert response.status_code == 200
        kwargs = svc.install_component_to_tenant.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["component_id"] == "comp-1"
        assert kwargs["canvas_id"] == "c-1"
        assert kwargs["config"] is None

    def test_install_success_with_config(self, client, user):
        svc = MagicMock()
        svc.install_component_to_tenant = AsyncMock(return_value={})
        with patch("api.canvas_skill_routes.CanvasSkillIntegrationService",
                   return_value=svc):
            response = client.post(
                "/canvas-skills/install/comp-2?tenant_id=t-1")
        assert response.status_code == 200
        assert svc.install_component_to_tenant.call_args.kwargs[
            "canvas_id"] is None

    def test_install_missing_fields_422(self, client):
        response = client.post("/canvas-skills/install/comp-1", json={})
        assert response.status_code == 422


class TestSkillList:
    def test_list_skills(self, client, db):
        db.add(Skill(
            id=f"sk-{uuid.uuid4().hex[:8]}", tenant_id="t-1",
            name="Draw", description="d", version="1.0.0",
            type="function", input_schema={}, config={},
            is_public=True, is_approved=True, category="prod"))
        db.add(Skill(
            id=f"sk-{uuid.uuid4().hex[:8]}", tenant_id="other-tenant",
            name="Other", description="d", version="1.0.0",
            type="api", input_schema={}, config={}))
        db.commit()
        response = client.get("/canvas-skills/skills?tenant_id=t-1")
        assert response.status_code == 200
        names = [s["name"] for s in response.json()]
        assert "Draw" in names
        assert "Other" not in names

    def test_list_skills_empty(self, client, db):
        db.query(Skill).filter(Skill.tenant_id == "no-such-tenant").delete()
        db.commit()
        response = client.get("/canvas-skills/skills?tenant_id=no-such-tenant")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_components(self, client, db):
        db.add(CanvasComponent(
            id=f"cp-{uuid.uuid4().hex[:8]}", tenant_id="t-1",
            author_id=user_id_placeholder("x"), name="Widget",
            category="widget", component_type="html", code="<div/>",
            is_public=False))
        db.add(CanvasComponent(
            id=f"cp-{uuid.uuid4().hex[:8]}", tenant_id=None,
            author_id=user_id_placeholder("y"), name="Public Widget",
            category="widget", component_type="html", code="<div/>",
            is_public=True))
        db.add(CanvasComponent(
            id=f"cp-{uuid.uuid4().hex[:8]}", tenant_id="other-tenant",
            author_id=user_id_placeholder("z"), name="Other Widget",
            category="widget", component_type="html", code="<div/>",
            is_public=False))
        db.commit()
        response = client.get("/canvas-skills/components?tenant_id=t-1")
        assert response.status_code == 200
        names = [c["name"] for c in response.json()]
        assert "Widget" in names
        assert "Public Widget" in names
        assert "Other Widget" not in names

    def test_list_components_empty(self, client, db):
        db.query(CanvasComponent).delete()
        db.commit()
        response = client.get(
            "/canvas-skills/components?tenant_id=no-such-tenant")
        assert response.status_code == 200
        assert response.json() == []


def user_id_placeholder(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ============================================================================
# api/canvas_recording_routes.py
# ============================================================================

def _recording_dict(user_id="u-1", recording_id="rec-1"):
    return {
        "recording_id": recording_id,
        "agent_id": "agent-1",
        "user_id": user_id,
        "canvas_id": "c-1",
        "session_id": "s-1",
        "reason": "manual",
        "status": "recording",
        "tags": ["test"],
        "started_at": "2026-08-12T00:00:00Z",
        "stopped_at": None,
        "duration_seconds": 12.5,
        "event_count": 2,
        "summary": None,
        "events": [{"type": "update"}],
        "recording_metadata": {"source": "test"},
        "expires_at": None,
        "flagged_for_review": False,
    }


@pytest.fixture
def rec_svc():
    s = MagicMock()
    s.start_recording = AsyncMock(return_value="rec-1")
    s.record_event = AsyncMock()
    s.stop_recording = AsyncMock()
    s.get_recording = AsyncMock(return_value=_recording_dict())
    s.list_recordings = AsyncMock(return_value=[])
    s.flag_for_review = AsyncMock()
    with patch("api.canvas_recording_routes.get_canvas_recording_service",
               return_value=s):
        yield s


def _rec_row(db, user, recording_id=None):
    rid = recording_id or f"rec-{uuid.uuid4().hex[:8]}"
    row = CanvasRecording(
        id=f"cr-{uuid.uuid4().hex[:8]}", recording_id=rid,
        tenant_id="t-1", user_id=user.id, agent_id="agent-1",
        reason="manual", status="recording")
    db.add(row)
    db.commit()
    return rid


class TestRecordingHealth:
    def test_health(self, client):
        response = client.get("/api/canvas/recording/health")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "healthy"


class TestRecordingStart:
    def test_start_success(self, client, rec_svc, user):
        response = client.post("/api/canvas/recording/start", json={
            "agent_id": "agent-1", "canvas_id": "c-1",
            "reason": "manual", "session_id": "s-1",
            "tags": ["a", "b"]})
        assert response.status_code == 200
        data = response.json()
        assert data["recording_id"] == "rec-1"
        assert data["user_id"] == user.id
        assert data["status"] == "recording"
        kwargs = rec_svc.start_recording.call_args.kwargs
        assert kwargs["tags"] == ["a", "b"]
        assert kwargs["canvas_id"] == "c-1"

    def test_start_service_error_500(self, client, rec_svc):
        rec_svc.start_recording.side_effect = RuntimeError("boom")
        response = client.post("/api/canvas/recording/start", json={
            "agent_id": "agent-1", "reason": "manual"})
        assert response.status_code == 500

    def test_start_missing_fields_422(self, client):
        response = client.post("/api/canvas/recording/start", json={})
        assert response.status_code == 422


class TestRecordingEvent:
    def test_event_success(self, client, rec_svc):
        response = client.post("/api/canvas/recording/rec-1/event", json={
            "event_type": "update", "event_data": {"x": 1}})
        assert response.status_code == 200
        rec_svc.record_event.assert_awaited_once_with(
            recording_id="rec-1", event_type="update", event_data={"x": 1})

    def test_event_service_error_500(self, client, rec_svc):
        rec_svc.record_event.side_effect = RuntimeError("boom")
        response = client.post("/api/canvas/recording/rec-1/event", json={
            "event_type": "update", "event_data": {}})
        assert response.status_code == 500


class TestRecordingStop:
    def test_stop_success(self, client, rec_svc):
        response = client.post("/api/canvas/recording/rec-1/stop", json={
            "status": "completed", "summary": "done"})
        assert response.status_code == 200
        rec_svc.stop_recording.assert_awaited_once_with(
            recording_id="rec-1", status="completed", summary="done")

    def test_stop_default_status(self, client, rec_svc):
        response = client.post("/api/canvas/recording/rec-1/stop", json={})
        assert response.status_code == 200
        assert rec_svc.stop_recording.call_args.kwargs["status"] == "completed"

    def test_stop_service_error_500(self, client, rec_svc):
        rec_svc.stop_recording.side_effect = RuntimeError("boom")
        response = client.post("/api/canvas/recording/rec-1/stop", json={})
        assert response.status_code == 500


class TestRecordingGet:
    def test_get_success(self, client, rec_svc, user):
        rec_svc.get_recording.return_value = _recording_dict(user_id=user.id)
        response = client.get("/api/canvas/recording/rec-1")
        assert response.status_code == 200
        data = response.json()
        assert data["recording_id"] == "rec-1"
        assert data["event_count"] == 2
        assert data["events"] == [{"type": "update"}]

    def test_get_not_found_404(self, client, rec_svc):
        rec_svc.get_recording.return_value = None
        response = client.get("/api/canvas/recording/ghost")
        assert response.status_code == 404

    def test_get_ownership_denied_403(self, client, rec_svc, user):
        rec_svc.get_recording.return_value = _recording_dict(
            user_id="someone-else")
        response = client.get("/api/canvas/recording/rec-1")
        assert response.status_code == 403

    def test_get_service_error_500(self, client, rec_svc):
        rec_svc.get_recording.side_effect = RuntimeError("boom")
        response = client.get("/api/canvas/recording/rec-1")
        assert response.status_code == 500


class TestRecordingList:
    def test_list_success(self, client, rec_svc, user):
        rec_svc.list_recordings.return_value = [
            _recording_dict(user_id=user.id, recording_id="a"),
            _recording_dict(user_id=user.id, recording_id="b")]
        response = client.get("/api/canvas/recording")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["total"] == 2
        assert len(data["data"]) == 2
        rec_svc.list_recordings.assert_awaited_once_with(
            user_id=user.id, agent_id=None, limit=50, offset=0)

    def test_list_with_filters(self, client, rec_svc, user):
        response = client.get(
            "/api/canvas/recording?agent_id=agent-1&limit=10&offset=5")
        assert response.status_code == 200
        rec_svc.list_recordings.assert_awaited_once_with(
            user_id=user.id, agent_id="agent-1", limit=10, offset=5)

    def test_list_service_error_500(self, client, rec_svc):
        rec_svc.list_recordings.side_effect = RuntimeError("boom")
        response = client.get("/api/canvas/recording")
        assert response.status_code == 500


class TestRecordingFlag:
    def test_flag_success(self, client, db, user, rec_svc):
        rid = _rec_row(db, user)
        response = client.post(f"/api/canvas/recording/{rid}/flag", json={
            "flag_reason": "suspicious_activity"})
        assert response.status_code == 200
        rec_svc.flag_for_review.assert_awaited_once_with(
            recording_id=rid, flag_reason="suspicious_activity",
            flagged_by=user.id)

    def test_flag_not_found_404(self, client, db, user, rec_svc):
        response = client.post("/api/canvas/recording/ghost/flag", json={
            "flag_reason": "x"})
        assert response.status_code == 404
        rec_svc.flag_for_review.assert_not_awaited()

    def test_flag_other_users_recording_404(self, client, db, user, rec_svc):
        other = _other_user(db)
        rid = _rec_row(db, other)
        response = client.post(f"/api/canvas/recording/{rid}/flag", json={
            "flag_reason": "x"})
        assert response.status_code == 404

    def test_flag_service_error_500(self, client, db, user, rec_svc):
        rid = _rec_row(db, user)
        rec_svc.flag_for_review.side_effect = RuntimeError("boom")
        response = client.post(f"/api/canvas/recording/{rid}/flag", json={
            "flag_reason": "x"})
        assert response.status_code == 500


class TestRecordingReplay:
    def test_replay_success(self, client, rec_svc, user):
        rec_svc.get_recording.return_value = _recording_dict(user_id=user.id)
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["recording_id"] == "rec-1"
        assert data["events"] == [{"type": "update"}]
        assert data["recording_metadata"] == {"source": "test"}
        assert data["duration_seconds"] == 12.5

    def test_replay_not_found_404(self, client, rec_svc):
        rec_svc.get_recording.return_value = None
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 404

    def test_replay_ownership_denied_403(self, client, rec_svc, user):
        rec_svc.get_recording.return_value = _recording_dict(
            user_id="someone-else")
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 403

    def test_replay_service_error_500(self, client, rec_svc):
        rec_svc.get_recording.side_effect = RuntimeError("boom")
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 500


# ============================================================================
# api/debug_routes.py
# ============================================================================

def _debug_collector():
    c = MagicMock()
    c.collect_event = AsyncMock(return_value=MagicMock(id="ev-1"))
    c.collect_batch_events = AsyncMock(
        return_value=[MagicMock(id="ev-1"), MagicMock(id="ev-2")])
    c.collect_state_snapshot = AsyncMock(
        return_value=MagicMock(id="snap-1"))
    return c


def _storage():
    s = MagicMock()
    s.query_events = AsyncMock(return_value=[{"id": "ev-1"}])
    s.get_event = AsyncMock(return_value={"id": "ev-1"})
    s.get_state_snapshot = AsyncMock(
        return_value={"component_id": "c-1"})
    s.query_insights = AsyncMock(return_value=[{"id": "ins-1"}])
    s.get_insight = AsyncMock(return_value={"id": "ins-1"})
    return s


class TestDebugEvents:
    def test_collect_event(self, client):
        with patch("api.debug_routes.get_debug_collector",
                   return_value=_debug_collector()):
            response = client.post("/api/debug/events", json={
                "event_type": "error", "component_type": "core",
                "component_id": "c-1", "correlation_id": "corr-1",
                "message": "boom", "level": "ERROR", "data": {},
                "event_metadata": {"k": "v"}, "parent_event_id": "p-1"})
        assert response.status_code == 200
        assert response.json()["data"]["event_id"] == "ev-1"

    def test_collect_event_none_result(self, client):
        c = _debug_collector()
        c.collect_event = AsyncMock(return_value=None)
        with patch("api.debug_routes.get_debug_collector", return_value=c):
            response = client.post("/api/debug/events", json={
                "event_type": "log", "component_type": "core",
                "correlation_id": "c"})
        assert response.status_code == 200
        assert response.json()["data"]["event_id"] is None

    def test_collect_event_inits_collector(self, client):
        c = _debug_collector()
        with patch("api.debug_routes.get_debug_collector", return_value=None), \
             patch("api.debug_routes.init_debug_collector", return_value=c):
            response = client.post("/api/debug/events", json={
                "event_type": "log", "component_type": "core",
                "correlation_id": "c"})
        assert response.status_code == 200
        assert response.json()["data"]["event_id"] == "ev-1"

    def test_collect_event_missing_fields_422(self, client):
        response = client.post("/api/debug/events", json={
            "event_type": "log"})
        assert response.status_code == 422

    def test_collect_batch(self, client):
        with patch("api.debug_routes.get_debug_collector",
                   return_value=_debug_collector()):
            response = client.post("/api/debug/events/batch", json={
                "events": [{"event_type": "a", "component_type": "x",
                            "correlation_id": "c-1"},
                           {"event_type": "b", "component_type": "y",
                            "correlation_id": "c-1"}]})
        assert response.status_code == 200
        assert response.json()["data"]["collected_count"] == 2
        assert response.json()["data"]["event_ids"] == ["ev-1", "ev-2"]

    def test_collect_batch_with_none_ids(self, client):
        c = _debug_collector()
        c.collect_batch_events = AsyncMock(return_value=[MagicMock(id="e1"),
                                                         None])
        with patch("api.debug_routes.get_debug_collector", return_value=c):
            response = client.post("/api/debug/events/batch", json={
                "events": [{"event_type": "a", "component_type": "x",
                            "correlation_id": "c"},
                           {"event_type": "b", "component_type": "y",
                            "correlation_id": "c"}]})
        assert response.status_code == 200
        assert response.json()["data"]["event_ids"] == ["e1", None]

    def test_collect_batch_inits_collector(self, client):
        c = _debug_collector()
        with patch("api.debug_routes.get_debug_collector", return_value=None), \
             patch("api.debug_routes.init_debug_collector", return_value=c):
            response = client.post("/api/debug/events/batch", json={
                "events": [{"event_type": "a", "component_type": "x",
                            "correlation_id": "c"}]})
        assert response.status_code == 200
        assert response.json()["data"]["collected_count"] == 2

    def test_query_events(self, client):
        with patch("api.debug_routes._get_storage", return_value=_storage()):
            response = client.get(
                "/api/debug/events?component_type=core&component_id=c1"
                "&correlation_id=corr&event_type=error&level=ERROR"
                "&time_range=last_24h&limit=10&offset=5")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1

    def test_query_events_empty(self, client):
        s = _storage()
        s.query_events = AsyncMock(return_value=[])
        with patch("api.debug_routes._get_storage", return_value=s):
            response = client.get("/api/debug/events")
        assert response.status_code == 200
        assert response.json()["data"]["events"] == []

    def test_get_event_found(self, client):
        with patch("api.debug_routes._get_storage", return_value=_storage()):
            response = client.get("/api/debug/events/ev-1")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == "ev-1"

    def test_get_event_not_found(self, client):
        s = _storage()
        s.get_event = AsyncMock(return_value=None)
        with patch("api.debug_routes._get_storage", return_value=s):
            response = client.get("/api/debug/events/ghost")
        assert response.status_code == 404


class TestDebugState:
    def test_collect_state_snapshot(self, client):
        with patch("api.debug_routes.get_debug_collector",
                   return_value=_debug_collector()):
            response = client.post("/api/debug/state", json={
                "component_type": "core", "component_id": "c-1",
                "operation_id": "op-1", "state_data": {"x": 1},
                "checkpoint_name": "cp-1", "snapshot_type": "full",
                "diff_from_previous": {}})
        assert response.status_code == 200
        assert response.json()["data"]["snapshot_id"] == "snap-1"

    def test_collect_state_snapshot_none(self, client):
        c = _debug_collector()
        c.collect_state_snapshot = AsyncMock(return_value=None)
        with patch("api.debug_routes.get_debug_collector", return_value=c):
            response = client.post("/api/debug/state", json={
                "component_type": "core", "component_id": "c-1",
                "operation_id": "op-1", "state_data": {}})
        assert response.status_code == 200
        assert response.json()["data"]["snapshot_id"] is None

    def test_collect_state_snapshot_inits_collector(self, client):
        c = _debug_collector()
        with patch("api.debug_routes.get_debug_collector", return_value=None), \
             patch("api.debug_routes.init_debug_collector", return_value=c):
            response = client.post("/api/debug/state", json={
                "component_type": "core", "component_id": "c-1",
                "operation_id": "op-1", "state_data": {}})
        assert response.status_code == 200

    def test_get_component_state(self, client):
        with patch("api.debug_routes._get_storage", return_value=_storage()):
            response = client.get(
                "/api/debug/state/core/c-1?operation_id=op-1&checkpoint_name=cp")
        assert response.status_code == 200
        assert response.json()["data"]["component_id"] == "c-1"

    def test_get_component_state_missing_operation_id(self, client):
        response = client.get("/api/debug/state/core/c-1")
        assert response.status_code == 400

    def test_get_component_state_not_found(self, client):
        s = _storage()
        s.get_state_snapshot = AsyncMock(return_value=None)
        with patch("api.debug_routes._get_storage", return_value=s):
            response = client.get(
                "/api/debug/state/core/c-1?operation_id=op-1")
        assert response.status_code == 404


class TestDebugInsights:
    def test_query_insights(self, client):
        with patch("api.debug_routes._get_storage", return_value=_storage()):
            response = client.get(
                "/api/debug/insights?insight_type=error&severity=critical"
                "&scope=core&resolved=true&time_range=last_24h&limit=5")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1

    def test_get_insight_found(self, client):
        with patch("api.debug_routes._get_storage", return_value=_storage()):
            response = client.get("/api/debug/insights/ins-1")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == "ins-1"

    def test_get_insight_not_found(self, client):
        s = _storage()
        s.get_insight = AsyncMock(return_value=None)
        with patch("api.debug_routes._get_storage", return_value=s):
            response = client.get("/api/debug/insights/ghost")
        assert response.status_code == 404

    def test_generate_insights(self, client):
        engine = MagicMock()
        engine.generate_insights_from_events = AsyncMock(
            return_value=[{"id": "gen-1", "type": "error"}])
        engine._insight_to_dict = MagicMock(side_effect=lambda i: i)
        with patch("api.debug_routes.DebugInsightEngine",
                   return_value=engine):
            response = client.post("/api/debug/insights/generate", json={
                "correlation_id": "corr", "component_type": "core",
                "component_id": "c-1", "time_range": "last_24h"})
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1

    def test_generate_insights_empty(self, client):
        engine = MagicMock()
        engine.generate_insights_from_events = AsyncMock(return_value=[])
        engine._insight_to_dict = MagicMock(side_effect=lambda i: i)
        with patch("api.debug_routes.DebugInsightEngine",
                   return_value=engine):
            response = client.post("/api/debug/insights/generate", json={
                "component_type": "core"})
        assert response.status_code == 200
        assert response.json()["data"]["insights"] == []

    def test_resolve_insight_success(self, client, db):
        row = DebugInsight(id=f"ins-{uuid.uuid4().hex[:8]}",
                           insight_type="error", severity="critical",
                           title="t", resolved=False)
        db.add(row)
        db.commit()
        response = client.put(
            f"/api/debug/insights/{row.id}/resolve?resolution_notes=fixed")
        assert response.status_code == 200
        assert response.json()["data"]["resolved"] is True
        db.refresh(row)
        assert row.resolved is True
        assert row.resolution_notes == "fixed"

    def test_resolve_insight_not_found(self, client):
        response = client.put(
            "/api/debug/insights/ghost/resolve?resolution_notes=x")
        assert response.status_code == 404


class TestDebugSessions:
    @staticmethod
    def _clear(db):
        db.query(DebugSession).delete()
        db.commit()

    def test_create_session(self, client, db):
        response = client.post("/api/debug/sessions", json={
            "session_name": "dbg-1", "description": "d",
            "filters": {"level": "ERROR"}, "scope": {"component": "core"}})
        assert response.status_code == 200
        sid = response.json()["data"]["session_id"]
        assert db.query(DebugSession).filter(
            DebugSession.id == sid).first() is not None

    def test_create_session_missing_fields_422(self, client):
        response = client.post("/api/debug/sessions", json={})
        assert response.status_code == 422

    def test_list_sessions(self, client, db):
        self._clear(db)
        now = datetime.now(timezone.utc)
        s1 = DebugSession(session_name="active-1", active=True,
                          resolved=False, event_count=3, insight_count=1)
        s1.created_at = now
        s2 = DebugSession(session_name="resolved-1", active=False,
                          resolved=True)
        s2.created_at = now - timedelta(minutes=1)
        db.add_all([s1, s2])
        db.commit()
        response = client.get("/api/debug/sessions")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 2
        names = {s["session_name"] for s in data["sessions"]}
        assert names == {"active-1", "resolved-1"}
        assert data["sessions"][0]["created_at"]
        assert data["sessions"][0]["event_count"] == 3
        assert data["sessions"][0]["insight_count"] == 1

    def test_list_sessions_active_filter(self, client, db):
        self._clear(db)
        db.add(DebugSession(session_name="active-2", active=True,
                            resolved=False))
        db.add(DebugSession(session_name="closed-2", active=False,
                            resolved=True))
        db.commit()
        response = client.get("/api/debug/sessions?active=true")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["sessions"][0]["session_name"] == "active-2"

    def test_list_sessions_resolved_filter(self, client, db):
        self._clear(db)
        db.add(DebugSession(session_name="r-3", active=False,
                            resolved=True))
        db.add(DebugSession(session_name="open-3", active=True,
                            resolved=False))
        db.commit()
        response = client.get("/api/debug/sessions?resolved=true")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1
        assert response.json()["data"]["sessions"][0]["session_name"] == "r-3"

    def test_list_sessions_created_at_none(self, client, db):
        self._clear(db)
        s = DebugSession(session_name="no-ts", active=True, resolved=False)
        db.add(s)
        db.commit()
        s.created_at = None
        db.commit()
        response = client.get("/api/debug/sessions")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1
        assert response.json()["data"]["sessions"][0]["created_at"] is None

    def test_list_sessions_empty(self, client, db):
        self._clear(db)
        response = client.get("/api/debug/sessions")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 0

    def test_close_session_success(self, client, db):
        self._clear(db)
        s = DebugSession(session_name="to-close", active=True)
        db.add(s)
        db.commit()
        response = client.put(f"/api/debug/sessions/{s.id}/close")
        assert response.status_code == 200
        assert response.json()["data"]["closed"] is True
        db.refresh(s)
        assert s.active is False
        assert s.closed_at is not None

    def test_close_session_not_found(self, client):
        response = client.put("/api/debug/sessions/ghost/close")
        assert response.status_code == 404


class TestDebugAnalytics:
    def test_component_health(self, client):
        query = MagicMock()
        query.get_component_health = AsyncMock(return_value={"healthy": True})
        with patch("api.debug_routes.DebugQuery", return_value=query):
            response = client.post("/api/debug/analytics/component-health",
                                   json={"component_type": "core",
                                         "component_id": "c-1",
                                         "time_range": "1h"})
        assert response.status_code == 200
        assert response.json()["data"]["healthy"] is True

    def _error_event(self, db, message, level, timestamp):
        row = DebugEvent(
            id=f"de-{uuid.uuid4().hex[:8]}", event_type="error",
            component_type="core", component_id="c-1",
            correlation_id="corr-1", level=level, message=message,
            timestamp=timestamp)
        db.add(row)
        return row

    def test_error_patterns(self, client, db):
        now = datetime.now(timezone.utc)
        self._error_event(db, "boom in module", "ERROR", now - timedelta(hours=2))
        self._error_event(db, "boom in module", "ERROR", now - timedelta(hours=1))
        self._error_event(db, "boom in module", "CRITICAL",
                          now - timedelta(hours=3))
        self._error_event(db, "other message", "ERROR", now - timedelta(hours=1))
        db.commit()
        response = client.get("/api/debug/analytics/error-patterns")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_errors"] == 4
        assert data["time_range"] == "last_24h"
        by_msg = {p["message"]: p for p in data["error_patterns"]}
        assert by_msg["boom in module"]["count"] == 3
        assert len(data["error_patterns"]) == 2

    def test_error_patterns_empty(self, client, db):
        db.query(DebugEvent).delete()
        db.commit()
        response = client.get("/api/debug/analytics/error-patterns")
        assert response.status_code == 200
        assert response.json()["data"]["total_errors"] == 0

    def test_error_patterns_first_seen_update(self, client):
        """The real-DB path scans the timestamp index ascending (verified via
        EXPLAIN QUERY PLAN), so the first processed event is always the
        minimum and `event.timestamp < first_seen` can never fire. Drive the
        route with a mocked DB whose row order is newest-first instead."""
        from core.database import get_db
        from core.models import DebugEvent

        now = datetime.now(timezone.utc)
        e_newer = MagicMock(spec=DebugEvent)
        e_newer.component_type = "core"
        e_newer.message = "boom"
        e_newer.timestamp = now - timedelta(hours=1)
        e_older = MagicMock(spec=DebugEvent)
        e_older.component_type = "core"
        e_older.message = "boom"
        e_older.timestamp = now - timedelta(hours=3)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            e_newer, e_older]

        from core.database import get_db as real_get_db
        original = client.app.dependency_overrides[real_get_db]
        client.app.dependency_overrides[real_get_db] = lambda: mock_db
        try:
            response = client.get("/api/debug/analytics/error-patterns")
        finally:
            client.app.dependency_overrides[real_get_db] = original
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_errors"] == 2
        assert data["error_patterns"][0]["count"] == 2
        assert data["error_patterns"][0]["first_seen"] == \
            e_older.timestamp.isoformat()
        mock_db.query.assert_called_once_with(DebugEvent)

    def _monitor(self, method, result):
        m = MagicMock()
        setattr(m, method, AsyncMock(return_value=result))
        return m

    def test_system_health(self, client):
        m = self._monitor("get_system_health", {"healthy": True})
        with patch("core.debug_monitor.DebugMonitor", return_value=m):
            response = client.get("/api/debug/analytics/system-health")
        assert response.status_code == 200
        assert response.json()["data"]["healthy"] is True

    def test_active_operations(self, client):
        m = self._monitor("get_active_operations", [{"op": "o"}])
        with patch("core.debug_monitor.DebugMonitor", return_value=m):
            response = client.get(
                "/api/debug/analytics/active-operations?limit=10")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1

    def test_throughput(self, client):
        m = self._monitor("get_throughput_metrics", {"tps": 5})
        with patch("core.debug_monitor.DebugMonitor", return_value=m):
            response = client.get("/api/debug/analytics/throughput")
        assert response.status_code == 200
        assert response.json()["data"]["tps"] == 5

    def test_insights_summary(self, client):
        m = self._monitor("get_insight_summary", {"count": 3})
        with patch("core.debug_monitor.DebugMonitor", return_value=m):
            response = client.get("/api/debug/analytics/insights-summary")
        assert response.status_code == 200
        assert response.json()["data"]["count"] == 3

    def test_error_rate(self, client):
        m = self._monitor("get_error_rate_by_component", {"core": 0.1})
        with patch("core.debug_monitor.DebugMonitor", return_value=m):
            response = client.get("/api/debug/analytics/error-rate")
        assert response.status_code == 200
        assert response.json()["data"]["error_rates"]["core"] == 0.1

    def test_performance_analytics(self, client):
        gen = MagicMock()
        insight = MagicMock()
        insight.id = "i-1"
        insight.insight_type = "performance"
        insight.severity = "warning"
        insight.title = "slow"
        insight.summary = "s"
        insight.description = "d"
        insight.evidence = {"x": 1}
        insight.confidence_score = 0.8
        insight.suggestions = ["a"]
        gen.analyze_component_latency = AsyncMock(return_value=insight)
        with patch("core.debug_insights.performance.PerformanceInsightGenerator",
                   return_value=gen):
            response = client.post("/api/debug/analytics/performance", json={
                "component_type": "core", "component_id": "c-1"})
        assert response.status_code == 200
        data = response.json()["data"]["insight"]
        assert data["id"] == "i-1"
        assert data["type"] == "performance"

    def test_performance_analytics_no_data(self, client):
        gen = MagicMock()
        gen.analyze_component_latency = AsyncMock(return_value=None)
        with patch("core.debug_insights.performance.PerformanceInsightGenerator",
                   return_value=gen):
            response = client.post("/api/debug/analytics/performance", json={
                "component_type": "core", "component_id": "c-1"})
        assert response.status_code == 200
        assert response.json()["data"]["insight"] is None


class TestDebugNaturalLanguage:
    def test_ai_query(self, client):
        assistant = MagicMock()
        assistant.ask = AsyncMock(return_value={"answer": "42"})
        with patch("api.debug_routes.DebugAIAssistant",
                   return_value=assistant):
            response = client.post("/api/debug/ai/query", json={
                "question": "what failed?", "context": {"component_id": "c"}})
        assert response.status_code == 200
        assert response.json()["data"]["answer"] == "42"

    def test_ai_query_missing_question_422(self, client):
        response = client.post("/api/debug/ai/query", json={})
        assert response.status_code == 422


class TestDebugOpencodeUsage:
    def _tracker(self, models=None):
        tracker = MagicMock()
        tracker.usage_summary = MagicMock(return_value={
            "provider": "opencode-go", "headroom": 0.5,
            "requests_in_window": 10, "tokens_in_window": 5000.0,
            "limits": {"rpm": 60}, "monthly": {"used": 100},
            "models": models,
        })
        tracker.window_seconds = 60
        tracker.get_model_headroom = MagicMock(return_value=0.6)
        return tracker

    def test_success_fills_registry_models(self, client):
        # summary.models None → registry-only model exercises the fill-in
        # branch (weight/limits/headroom/zeroed window counters).
        tracker = self._tracker(models=None)
        registry = MagicMock()
        registry.summary = MagicMock(return_value={
            "weights": {"deepseek-v4-flash": 1.0},
            "model_limits": {"deepseek-v4-flash": {"rpm": 60}}})
        with patch("core.llm.provider_rate_limits.get_provider_rate_tracker",
                   return_value=tracker), \
             patch("core.llm.opencode_model_limits.get_opencode_model_limits",
                   return_value=registry):
            response = client.get("/api/debug/opencode-usage")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["provider"] == "opencode-go"
        entry = data["models"]["deepseek-v4-flash"]
        assert entry["weight"] == 1.0
        assert entry["headroom"] == 0.6
        assert entry["requests_in_window"] == 0
        assert entry["tokens_in_window"] == 0.0
        assert data["limits"] == {"rpm": 60}
        assert data["monthly"] == {"used": 100}

    def test_model_filter(self, client):
        tracker = self._tracker(models={
            "deepseek-v4-flash": {"requests_in_window": 5,
                                  "tokens_in_window": 100.0, "headroom": 0.6,
                                  "limits": {}, "weight": 1.0},
            "kimi-k2.7-code": {"requests_in_window": 2,
                               "tokens_in_window": 50.0, "headroom": 0.3,
                               "limits": {}, "weight": 2.0}})
        registry = MagicMock()
        registry.summary = MagicMock(return_value={
            "weights": {"deepseek-v4-flash": 1.0, "kimi-k2.7-code": 2.0},
            "model_limits": {}})
        with patch("core.llm.provider_rate_limits.get_provider_rate_tracker",
                   return_value=tracker), \
             patch("core.llm.opencode_model_limits.get_opencode_model_limits",
                   return_value=registry):
            response = client.get(
                "/api/debug/opencode-usage?model=kimi-k2.7-code")
        assert response.status_code == 200
        assert list(response.json()["data"]["models"].keys()) == [
            "kimi-k2.7-code"]

    def test_error_500(self, client):
        with patch("core.llm.provider_rate_limits.get_provider_rate_tracker",
                   side_effect=RuntimeError("tracker down")):
            response = client.get("/api/debug/opencode-usage")
        assert response.status_code == 500
        assert "OPCODE_USAGE_UNAVAILABLE" in response.text


class TestDebugHelpers:
    def test_parse_time_range_variants(self):
        from api.debug_routes import _parse_time_range
        for tr in ("last_1h", "last_24h", "last_7d", "last_30d", "bogus"):
            result = _parse_time_range(tr)
            assert isinstance(result, datetime)

    def test_get_storage_success(self):
        config = MagicMock()
        config.redis_url = "redis://localhost:6379"
        with patch("api.debug_routes.get_config", return_value=config):
            storage = debug_routes._get_storage(MagicMock())
        assert storage is not None

    def test_get_storage_config_error(self):
        with patch("api.debug_routes.get_config",
                   side_effect=RuntimeError("no config")):
            storage = debug_routes._get_storage(MagicMock())
        assert storage is not None


class TestDebugDisabledMode:
    """All 22 flag-gated endpoints when DEBUG_SYSTEM_ENABLED=false: 16 return
    enabled:False, 6 raise 400 DEBUG_DISABLED. Includes the two endpoints
    missing from the W49 sweep (error-rate, ai/query)."""

    @staticmethod
    def _endpoints():
        returns_enabled_false = [
            ("post", "/api/debug/events", {"event_type": "log",
             "component_type": "core", "correlation_id": "c"}),
            ("post", "/api/debug/events/batch", {"events": []}),
            ("get", "/api/debug/events", None),
            ("post", "/api/debug/state", {"component_type": "core",
             "component_id": "c", "operation_id": "op", "state_data": {}}),
            ("get", "/api/debug/insights", None),
            ("post", "/api/debug/insights/generate",
             {"component_type": "core"}),
            ("get", "/api/debug/sessions", None),
            ("post", "/api/debug/analytics/component-health",
             {"component_type": "core", "component_id": "c"}),
            ("get", "/api/debug/analytics/error-patterns", None),
            ("get", "/api/debug/analytics/system-health", None),
            ("get", "/api/debug/analytics/active-operations", None),
            ("get", "/api/debug/analytics/throughput", None),
            ("get", "/api/debug/analytics/insights-summary", None),
            ("post", "/api/debug/analytics/performance",
             {"component_type": "core", "component_id": "c"}),
            ("get", "/api/debug/analytics/error-rate", None),
            ("post", "/api/debug/ai/query", {"question": "q"}),
        ]
        raises_disabled = [
            ("get", "/api/debug/events/ev-1", None),
            ("get", "/api/debug/state/core/c?operation_id=op", None),
            ("get", "/api/debug/insights/ins-1", None),
            ("put", "/api/debug/insights/ins-1/resolve?resolution_notes=x",
             None),
            ("post", "/api/debug/sessions", {"session_name": "s"}),
            ("put", "/api/debug/sessions/s-1/close", None),
        ]
        return returns_enabled_false, raises_disabled

    def test_disabled_returns_enabled_false(self, client):
        endpoints, _ = self._endpoints()
        with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
            for method, path, body in endpoints:
                response = (getattr(client, method)(path, json=body)
                            if body else getattr(client, method)(path))
                assert response.status_code == 200, path
                assert response.json()["data"]["enabled"] is False, path

    def test_disabled_raises_400(self, client):
        _, endpoints = self._endpoints()
        with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
            for method, path, body in endpoints:
                response = (getattr(client, method)(path, json=body)
                            if body else getattr(client, method)(path))
                assert response.status_code == 400, path
                assert "DEBUG_DISABLED" in response.text, path
