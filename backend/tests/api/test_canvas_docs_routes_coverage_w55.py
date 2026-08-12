"""Coverage wave 55 — api/canvas_docs_routes.py (TDD).

Existing suite (tests/unit/api/test_canvas_docs_routes.py) is a phantom smoke
suite. This wave tests the real endpoints: ownership gate
(_get_owned_docs_canvas_or_error — R66) + DocumentationCanvasService delegation:
- create (success, service-failure 400, 422)
- get (success, ownership 403, canvas-missing 404)
- update (success, 400, ownership 403)
- comment (success, 400, ownership 403)
- resolve (success, 400, ownership 403)
- versions (success, not-found 404, ownership 403)
- restore (success, 400, ownership 403)
- toc (success, not-found 404, ownership 403)
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api.canvas_docs_routes import router
from core.database import Base
from core.models import Canvas, CanvasAudit, User


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

    from core.database import get_db
    from core.security_dependencies import get_current_user

    def _get_db():
        try:
            yield db
        finally:
            pass

    def _get_current_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def svc():
    s = MagicMock()
    s.create_document_canvas.return_value = {"success": True,
                                              "canvas_id": "dc-1"}
    s.update_document_content.return_value = {"success": True}
    s.add_comment.return_value = {"success": True}
    s.resolve_comment.return_value = {"success": True}
    s.get_document_versions.return_value = {"success": True,
                                             "versions": []}
    s.restore_version.return_value = {"success": True}
    s.get_table_of_contents.return_value = {"success": True,
                                             "toc": []}
    with patch("api.canvas_docs_routes.DocumentationCanvasService",
               return_value=s):
        yield s


def _doc_canvas(db, user, canvas_id=None):
    cid = canvas_id or f"dc-{uuid.uuid4().hex[:8]}"
    canvas = Canvas(
        id=cid, tenant_id="t-1", workspace_id="ws-1",
        created_by=user.id, name="Doc", description="d",
        canvas_type="docs", content={}, style={},
        is_collaborative=False, is_public=False, status="active")
    db.add(canvas)
    audit = CanvasAudit(
        id=f"ca-{uuid.uuid4().hex[:8]}", canvas_id=cid,
        tenant_id="t-1", action_type="canvas_open",
        user_id=user.id, canvas_type="docs",
        details_json={"title": "My Doc", "content": "hello",
                       "layout": "document"})
    db.add(audit)
    db.commit()
    return cid


def _other_canvas(db, user, canvas_id=None):
    oid = f"other-{uuid.uuid4().hex[:8]}"
    other = User(
        id=oid, email=f"{oid}@x.com",
        hashed_password="h", first_name="O", last_name="U",
        role="member", status="active", tenant_id="t-1")
    db.add(other)
    db.commit()
    return _doc_canvas(db, other, canvas_id)


class TestCreate:
    def test_create_success(self, client, svc, user):
        response = client.post("/api/canvas/docs/create", json={
            "user_id": "spoofed",  # must be ignored
            "title": "My Doc", "content": "body"})
        assert response.status_code == 200
        assert svc.create_document_canvas.call_args.kwargs["user_id"] == user.id
        assert svc.create_document_canvas.call_args.kwargs["title"] == "My Doc"

    def test_create_service_failure_400(self, client, svc):
        svc.create_document_canvas.return_value = {
            "success": False, "error": "boom"}
        response = client.post("/api/canvas/docs/create", json={
            "user_id": "x", "title": "My Doc", "content": "body"})
        assert response.status_code == 400

    def test_create_missing_fields_422(self, client, svc):
        assert client.post("/api/canvas/docs/create",
                           json={}).status_code == 422


class TestGet:
    def test_get_success(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        response = client.get(f"/api/canvas/docs/{cid}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["title"] == "My Doc"
        assert data["content"] == "hello"
        assert data["canvas_id"] == cid

    def test_get_ownership_denied_403(self, client, db, user, svc):
        cid = _other_canvas(db, user)
        response = client.get(f"/api/canvas/docs/{cid}")
        assert response.status_code == 403

    def test_get_canvas_missing_404(self, client, db, user, svc):
        response = client.get("/api/canvas/docs/ghost")
        assert response.status_code == 404


class TestUpdate:
    def test_update_success(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        response = client.put(f"/api/canvas/docs/{cid}", json={
            "user_id": "spoofed", "content": "new body", "changes": "edit"})
        assert response.status_code == 200
        kwargs = svc.update_document_content.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["content"] == "new body"

    def test_update_failure_400(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        svc.update_document_content.return_value = {
            "success": False, "error": "x"}
        response = client.put(f"/api/canvas/docs/{cid}", json={
            "user_id": "x", "content": "new"})
        assert response.status_code == 400

    def test_update_ownership_denied_403(self, client, db, user, svc):
        cid = _other_canvas(db, user)
        response = client.put(f"/api/canvas/docs/{cid}", json={
            "user_id": "x", "content": "new"})
        assert response.status_code == 403


class TestComment:
    def test_comment_success(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        response = client.post(f"/api/canvas/docs/{cid}/comment", json={
            "user_id": "spoofed", "content": "nice"})
        assert response.status_code == 200
        assert svc.add_comment.call_args.kwargs["user_id"] == user.id
        assert svc.add_comment.call_args.kwargs["content"] == "nice"

    def test_comment_failure_400(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        svc.add_comment.return_value = {"success": False, "error": "x"}
        response = client.post(f"/api/canvas/docs/{cid}/comment", json={
            "user_id": "x", "content": "nice"})
        assert response.status_code == 400

    def test_comment_ownership_denied_403(self, client, db, user, svc):
        cid = _other_canvas(db, user)
        response = client.post(f"/api/canvas/docs/{cid}/comment", json={
            "user_id": "x", "content": "nice"})
        assert response.status_code == 403


class TestResolve:
    def test_resolve_success(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        response = client.post(f"/api/canvas/docs/{cid}/comment/resolve", json={
            "user_id": "spoofed", "comment_id": "cm-1"})
        assert response.status_code == 200
        kwargs = svc.resolve_comment.call_args.kwargs
        assert kwargs["comment_id"] == "cm-1"
        assert kwargs["user_id"] == user.id

    def test_resolve_failure_400(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        svc.resolve_comment.return_value = {"success": False, "error": "x"}
        response = client.post(f"/api/canvas/docs/{cid}/comment/resolve", json={
            "user_id": "x", "comment_id": "cm-1"})
        assert response.status_code == 400

    def test_resolve_ownership_denied_403(self, client, db, user, svc):
        cid = _other_canvas(db, user)
        response = client.post(f"/api/canvas/docs/{cid}/comment/resolve", json={
            "user_id": "x", "comment_id": "cm-1"})
        assert response.status_code == 403


class TestVersions:
    def test_versions_success(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        response = client.get(f"/api/canvas/docs/{cid}/versions")
        assert response.status_code == 200
        svc.get_document_versions.assert_called_once_with(cid)

    def test_versions_failure_404(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        svc.get_document_versions.return_value = {
            "success": False, "error": "none"}
        response = client.get(f"/api/canvas/docs/{cid}/versions")
        assert response.status_code == 404

    def test_versions_ownership_denied_403(self, client, db, user, svc):
        cid = _other_canvas(db, user)
        response = client.get(f"/api/canvas/docs/{cid}/versions")
        assert response.status_code == 403


class TestRestore:
    def test_restore_success(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        response = client.post(f"/api/canvas/docs/{cid}/restore", json={
            "user_id": "spoofed", "version_id": "v-2"})
        assert response.status_code == 200
        kwargs = svc.restore_version.call_args.kwargs
        assert kwargs["version_id"] == "v-2"
        assert kwargs["user_id"] == user.id

    def test_restore_failure_400(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        svc.restore_version.return_value = {"success": False, "error": "x"}
        response = client.post(f"/api/canvas/docs/{cid}/restore", json={
            "user_id": "x", "version_id": "v-2"})
        assert response.status_code == 400

    def test_restore_ownership_denied_403(self, client, db, user, svc):
        cid = _other_canvas(db, user)
        response = client.post(f"/api/canvas/docs/{cid}/restore", json={
            "user_id": "x", "version_id": "v-2"})
        assert response.status_code == 403


class TestTOC:
    def test_toc_success(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        response = client.get(f"/api/canvas/docs/{cid}/toc")
        assert response.status_code == 200
        svc.get_table_of_contents.assert_called_once_with(cid)

    def test_toc_failure_404(self, client, db, user, svc):
        cid = _doc_canvas(db, user)
        svc.get_table_of_contents.return_value = {
            "success": False, "error": "none"}
        response = client.get(f"/api/canvas/docs/{cid}/toc")
        assert response.status_code == 404

    def test_toc_ownership_denied_403(self, client, db, user, svc):
        cid = _other_canvas(db, user)
        response = client.get(f"/api/canvas/docs/{cid}/toc")
        assert response.status_code == 403
