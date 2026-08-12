"""Coverage wave 52 — api/document_routes.py (TDD).

Picks up from 31% (existing suite is smoke-only with wide status assertions).
Targets:
- ingest_document (success incl. empty content + workspace resolution,
  handler-missing 500, add failure 500, exception 500)
- upload_document (success, declared-size 413, unsupported ext 415,
  post-read 413, empty parse placeholder, add failure 500, exception 500,
  HTTPException passthrough)
- search_documents (results, string metadata, bad-JSON metadata, empty,
  handler-missing 500, exception 500)
- get_document (success, not-found 404 [RED: was 500 via bogus
  `raise router.not_found(...)` — Starlette internal method], handler-missing
  500, exception 500)
- delete_document (user-initiated success, agent_id governance path,
  handler-missing 500)
- list_documents (success, handler-missing empty, exception 500)
"""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api.document_routes import router
from core.database import Base
from core.models import User


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
    uid = f"du-{uuid.uuid4().hex[:8]}"
    u = User(
        id=uid, email=f"{uid}@x.com",
        hashed_password="h", first_name="D", last_name="U",
        role="member", status="active", tenant_id="t-1")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, user):
    app = FastAPI()
    app.include_router(router)

    from core.security_dependencies import get_current_user

    def _get_current_user():
        return user

    app.dependency_overrides[get_current_user] = _get_current_user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def handler():
    h = MagicMock()
    h.add_document.return_value = True
    h.search.return_value = []
    h.get_document_by_id.return_value = None
    h.list_documents.return_value = []
    with patch("api.document_routes.get_lancedb_handler", return_value=h):
        yield h


def _doc_result(doc_id="doc-1", title="T", text="hello world", meta=None):
    m = meta or {"title": title, "file_type": "text"}
    return {"id": doc_id, "metadata": m, "text": text,
            "_score": 0.9, "created_at": "2026-08-11T00:00:00"}


class TestIngestDocument:
    def test_ingest_success(self, client, handler):
        response = client.post("/api/documents/ingest", json={
            "content": "x" * 600, "type": "text", "title": "Doc"})
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_count"] == 1
        handler.add_document.assert_called_once()
        kwargs = handler.add_document.call_args.kwargs
        assert kwargs["doc_id"] == data["id"]
        assert kwargs["metadata"]["source"] == "api_ingest"

    def test_ingest_empty_content_placeholder(self, client, handler):
        response = client.post("/api/documents/ingest", json={
            "content": "", "type": "text"})
        assert response.status_code == 200
        assert handler.add_document.call_args.kwargs["text"] == "(Empty document)"
        assert response.json()["title"].startswith("Document ")

    def test_ingest_workspace_resolution(self, client, db, user, handler):
        from core.models import Workspace
        ws = Workspace(id="ws-primary", tenant_id="t-1", name="Primary")
        db.add(ws)
        db.commit()
        user.workspaces.append(ws)
        db.commit()
        with patch("api.document_routes.get_lancedb_handler",
                   return_value=handler) as glh:
            response = client.post("/api/documents/ingest", json={
                "content": "abc", "type": "text"})
        assert response.status_code == 200
        assert glh.call_args.args == ("ws-primary",)

    def test_ingest_handler_missing_500(self, client):
        with patch("api.document_routes.get_lancedb_handler", return_value=None):
            response = client.post("/api/documents/ingest", json={
                "content": "abc", "type": "text"})
        assert response.status_code == 500

    def test_ingest_add_failure_500(self, client, handler):
        handler.add_document.return_value = False
        response = client.post("/api/documents/ingest", json={
            "content": "abc", "type": "text"})
        assert response.status_code == 500

    def test_ingest_exception_500(self, client, handler):
        handler.add_document.side_effect = RuntimeError("boom")
        response = client.post("/api/documents/ingest", json={
            "content": "abc", "type": "text"})
        assert response.status_code == 500


class TestUploadDocument:
    def test_upload_success(self, client, handler):
        with patch("api.document_routes.DocumentParser.parse_document",
                   new=AsyncMock(return_value="parsed body")):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("note.txt", b"raw bytes", "text/plain")})
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_count"] == 1
        kwargs = handler.add_document.call_args.kwargs
        assert kwargs["text"] == "parsed body"
        assert kwargs["metadata"]["source"] == "upload"
        assert kwargs["metadata"]["filename"] == "note.txt"

    def test_upload_declared_too_large_413(self, client, handler):
        with patch("api.document_routes.DocumentParser.parse_document",
                   new=AsyncMock(return_value="x")):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("big.txt", b"0" * (50 * 1024 * 1024 + 1),
                                "text/plain")})
        assert response.status_code == 413
        assert handler.add_document.called is False

    def test_upload_unsupported_ext_415(self, client, handler):
        response = client.post(
            "/api/documents/upload",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
        assert response.status_code == 415
        assert handler.add_document.called is False

    def test_upload_empty_parse_placeholder(self, client, handler):
        with patch("api.document_routes.DocumentParser.parse_document",
                   new=AsyncMock(return_value="")):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("blank.txt", b"", "text/plain")})
        assert response.status_code == 200
        assert handler.add_document.call_args.kwargs["text"].startswith(
            "[Empty or unparseable file")

    def test_upload_add_failure_500(self, client, handler):
        handler.add_document.return_value = False
        with patch("api.document_routes.DocumentParser.parse_document",
                   new=AsyncMock(return_value="parsed")):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("a.txt", b"x", "text/plain")})
        assert response.status_code == 500

    def test_upload_parse_exception_500(self, client, handler):
        with patch("api.document_routes.DocumentParser.parse_document",
                   new=AsyncMock(side_effect=RuntimeError("parse fail"))):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("a.pdf", b"%PDF", "application/pdf")})
        assert response.status_code == 500


class TestSearchDocuments:
    def test_search_success(self, client, handler):
        handler.search.return_value = [_doc_result()]
        response = client.get("/api/documents/search?q=hello")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["results"][0]["title"] == "T"
        assert data["results"][0]["score"] == 0.9

    def test_search_string_metadata_parsed(self, client, handler):
        handler.search.return_value = [{
            "id": "d1", "text": "body",
            "metadata": '{"title": "StrDoc", "file_type": "text"}',
            "_score": 0.5}]
        response = client.get("/api/documents/search?q=x")
        assert response.status_code == 200
        assert response.json()["results"][0]["title"] == "StrDoc"

    def test_search_bad_json_metadata_empty(self, client, handler):
        handler.search.return_value = [{
            "id": "d1", "text": "body",
            "metadata": "{not json", "_score": 0.5}]
        response = client.get("/api/documents/search?q=x")
        assert response.status_code == 200
        assert response.json()["results"][0]["metadata"] == {}
        assert response.json()["results"][0]["title"] == "Untitled"

    def test_search_empty_results(self, client, handler):
        response = client.get("/api/documents/search?q=nothing")
        assert response.status_code == 200
        assert response.json()["total_count"] == 0

    def test_search_limit_query_validation(self, client, handler):
        assert client.get("/api/documents/search?q=x&limit=0").status_code == 422
        assert client.get("/api/documents/search?q=x&limit=500").status_code == 422

    def test_search_handler_missing_500(self, client):
        with patch("api.document_routes.get_lancedb_handler", return_value=None):
            response = client.get("/api/documents/search?q=x")
        assert response.status_code == 500

    def test_search_exception_500(self, client, handler):
        handler.search.side_effect = RuntimeError("search down")
        response = client.get("/api/documents/search?q=x")
        assert response.status_code == 500


class TestGetDocument:
    def test_get_success(self, client, handler):
        handler.get_document_by_id.return_value = _doc_result(
            doc_id="doc-1", text="full content")
        response = client.get("/api/documents/doc-1")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == "doc-1"
        assert data["content"] == "full content"
        assert data["title"] == "T"

    def test_get_not_found_404(self, client, handler):
        """RED: previously 500 — `raise router.not_found(...)` is Starlette's
        internal response-sender, not an exception factory."""
        response = client.get("/api/documents/ghost")
        assert response.status_code == 404

    def test_get_handler_missing_500(self, client):
        with patch("api.document_routes.get_lancedb_handler", return_value=None):
            response = client.get("/api/documents/doc-1")
        assert response.status_code == 500

    def test_get_exception_500(self, client, handler):
        handler.get_document_by_id.side_effect = RuntimeError("boom")
        response = client.get("/api/documents/doc-1")
        assert response.status_code == 500


class TestDeleteDocument:
    def test_delete_user_initiated_success(self, client, handler):
        response = client.delete("/api/documents/doc-1")
        assert response.status_code == 200
        assert "deletion scheduled" in response.json()["message"]

    def test_delete_with_agent_id_governance(self, client, db, handler):
        with patch("core.api_governance.perform_governance_check",
                   new=AsyncMock()) as gov:
            response = client.delete("/api/documents/doc-1?agent_id=agent-1")
        gov.assert_awaited_once()
        assert response.status_code == 200

    def test_delete_handler_missing_500(self, client):
        with patch("api.document_routes.get_lancedb_handler", return_value=None):
            response = client.delete("/api/documents/doc-1")
        assert response.status_code == 500


class TestListDocuments:
    def test_list_success(self, client, handler):
        handler.list_documents.return_value = [
            _doc_result(doc_id="a"), _doc_result(doc_id="b")]
        response = client.get("/api/documents")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2
        assert response.json()["metadata"]["total"] == 2

    def test_list_handler_missing_empty(self, client):
        with patch("api.document_routes.get_lancedb_handler", return_value=None):
            response = client.get("/api/documents")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_list_exception_500(self, client, handler):
        handler.list_documents.side_effect = RuntimeError("boom")
        response = client.get("/api/documents")
        assert response.status_code == 500


class TestWorkspaceBranches:
    def _attach_workspace(self, db, user, ws_id=None):
        from core.models import Workspace
        ws_id = ws_id or f"ws-b{uuid.uuid4().hex[:6]}"
        ws = Workspace(id=ws_id, tenant_id="t-1", name="Branch WS")
        db.add(ws)
        db.commit()
        user.workspaces.append(ws)
        db.commit()
        return ws_id

    def test_upload_workspace_resolution_exception_warned(
            self, client, db, user, handler):
        """workspaces[0] raises → caught, logged, continues with None."""
        user.__dict__["workspaces"] = [object()]  # truthy, .id raises
        with patch("api.document_routes.DocumentParser.parse_document",
                   new=AsyncMock(return_value="parsed")):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("a.txt", b"x", "text/plain")})
        assert response.status_code == 200
        assert handler.add_document.call_args.kwargs["workspace_id"] is None

    def test_search_workspace_branch(self, client, db, user, handler):
        ws_id = self._attach_workspace(db, user)
        handler.search.return_value = [_doc_result()]
        with patch("api.document_routes.get_lancedb_handler",
                   return_value=handler) as glh:
            response = client.get("/api/documents/search?q=x")
        assert response.status_code == 200
        assert glh.call_args.args == (ws_id,)

    def test_get_workspace_branch(self, client, db, user, handler):
        ws_id = self._attach_workspace(db, user)
        handler.get_document_by_id.return_value = _doc_result(doc_id="doc-ws")
        with patch("api.document_routes.get_lancedb_handler",
                   return_value=handler) as glh:
            response = client.get("/api/documents/doc-ws")
        assert response.status_code == 200
        assert glh.call_args.args == (ws_id,)

    def test_delete_workspace_branch(self, client, db, user, handler):
        ws_id = self._attach_workspace(db, user)
        with patch("api.document_routes.get_lancedb_handler",
                   return_value=handler) as glh:
            response = client.delete("/api/documents/doc-1")
        assert response.status_code == 200
        assert glh.call_args.args == (ws_id,)

    def test_list_workspace_branch(self, client, db, user, handler):
        ws_id = self._attach_workspace(db, user)
        with patch("api.document_routes.get_lancedb_handler",
                   return_value=handler) as glh:
            response = client.get("/api/documents")
        assert response.status_code == 200
        assert glh.call_args.args == (ws_id,)


class TestUploadHandlerMissing:
    def test_upload_handler_missing_500(self, client):
        with patch("api.document_routes.get_lancedb_handler",
                   return_value=None):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("a.txt", b"x", "text/plain")})
        assert response.status_code == 500
