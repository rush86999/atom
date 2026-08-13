# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/board_routes.py (Kanban board API).

Real BoardService + real in-memory SQLite (no network, no LLM). Covers all
11 endpoints x {success, 401 unauth, 404 missing, 409 stale-version,
422 validation/illegal transition, task-canvas summary serialization,
redirect} plus the three serializer helpers.

Security regression surface checked this wave: every endpoint rejects
anonymous callers with 401 (no anonymous board read/write).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.board_routes import router as board_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentCanvasPresence, Artifact, Canvas, User

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1"):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="T",
        last_name="U",
        role="admin",
        status="active",
        tenant_id="t1",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def client(db):
    app = FastAPI()
    app.include_router(board_router)
    user = _make_user(db)

    def _override_db():
        yield db

    def _override_user():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def anon_client(db):
    app = FastAPI()
    app.include_router(board_router)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


def _create_board(client, name="Board A", slug="board-a"):
    resp = client.post("/api/boards", json={
        "name": name, "slug": slug, "description": "desc",
    }, headers=AUTH_HEADERS)
    assert resp.status_code == 201
    return resp.json()


def _create_column(client, board_id, name="Todo", position=0):
    resp = client.post(f"/api/boards/{board_id}/columns", json={
        "name": name, "position": position,
    }, headers=AUTH_HEADERS)
    assert resp.status_code == 201
    return resp.json()


def _create_task(client, board_id, column_id, title="Task 1"):
    resp = client.post(f"/api/boards/{board_id}/tasks", json={
        "title": title, "column_id": column_id, "status": "backlog",
    }, headers=AUTH_HEADERS)
    assert resp.status_code == 201
    return resp.json()


ENDPOINTS = [
    ("post", "/api/boards", {"name": "N", "seed_default_columns": False}),
    ("get", "/api/boards", None),
    ("get", "/api/boards/board-1", None),
    ("post", "/api/boards/board-1/columns", {"name": "C"}),
    ("post", "/api/boards/board-1/tasks", {"title": "T", "column_id": "col-1"}),
    ("get", "/api/boards/board-1/tasks", None),
    ("patch", "/api/boards/board-1/tasks/task-1", {"expected_version": 1}),
    ("delete", "/api/boards/board-1/tasks/task-1", None),
    ("get", "/api/boards/board-1/tasks/task-1/canvas", None),
    ("post", "/api/boards/board-1/rebalance", {"column_id": "col-1"}),
]


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path,body", ENDPOINTS)
    def test_anonymous_requests_rejected(self, anon_client, method, path, body):
        kwargs = {"json": body} if body is not None else {}
        resp = getattr(anon_client, method)(path, **kwargs)
        assert resp.status_code == 401


class TestBoardCRUD:
    def test_create_board_success(self, client):
        board = _create_board(client, name="New", slug="new-slug")
        assert board["name"] == "New"
        assert board["slug"] == "new-slug"
        assert board["owner_user_id"] == "user-1"
        assert board["version_id"] == 1
        assert board["created_at"] is not None

    def test_create_board_empty_name_422(self, client):
        resp = client.post("/api/boards", json={"name": ""}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_list_boards_success(self, client):
        _create_board(client, "A")
        _create_board(client, "B")
        resp = client.get("/api/boards", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_boards_excludes_archived(self, client, db):
        from core.board_service import BoardService
        board = _create_board(client, "A")
        service = BoardService(db)
        obj = service.get_board(board["id"])
        obj.archived_at = datetime.now(timezone.utc)
        db.commit()
        resp = client.get("/api/boards", headers=AUTH_HEADERS)
        assert resp.json() == []
        resp = client.get("/api/boards?include_archived=true", headers=AUTH_HEADERS)
        assert len(resp.json()) == 1

    def test_get_board_success_with_columns_and_counts(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"], "Todo")
        _create_task(client, board["id"], col["id"])
        resp = client.get(f"/api/boards/{board['id']}", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Board A"
        assert len(body["columns"]) >= 1
        todo = next(c for c in body["columns"] if c["name"] == "Todo")
        assert todo["task_count"] == 1
        assert todo["wip_limit"] is None

    def test_get_board_404(self, client):
        resp = client.get("/api/boards/nonexistent", headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestColumnCRUD:
    def test_create_column_success(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"], "In Progress", position=3)
        assert col["name"] == "In Progress"
        assert col["position"] == 3
        assert col["version_id"] == 1

    def test_create_column_missing_board_404(self, client):
        resp = client.post("/api/boards/nope/columns", json={"name": "C"},
                           headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_create_column_empty_name_422(self, client):
        board = _create_board(client)
        resp = client.post(f"/api/boards/{board['id']}/columns", json={"name": ""},
                           headers=AUTH_HEADERS)
        assert resp.status_code == 422


class TestTaskCRUD:
    def test_create_task_success(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"], "First task")
        assert task["title"] == "First task"
        assert task["column_id"] == col["id"]
        assert task["sort_order"] == 0.0
        assert task["labels"] == []
        assert task["metadata_json"] == {}
        assert task["canvas"] is None

    def test_create_task_unknown_status_422(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        resp = client.post(f"/api/boards/{board['id']}/tasks", json={
            "title": "T", "column_id": col["id"], "status": "bogus",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_create_task_missing_column_404(self, client):
        board = _create_board(client)
        resp = client.post(f"/api/boards/{board['id']}/tasks", json={
            "title": "T", "column_id": "missing-col",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_create_task_missing_board_404(self, client):
        resp = client.post("/api/boards/nope/tasks", json={
            "title": "T", "column_id": "col-1",
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_create_task_empty_title_422(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        resp = client.post(f"/api/boards/{board['id']}/tasks", json={
            "title": "", "column_id": col["id"],
        }, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_list_tasks_success(self, client):
        board = _create_board(client)
        col1 = _create_column(client, board["id"], "Todo", 0)
        col2 = _create_column(client, board["id"], "Done", 1)
        _create_task(client, board["id"], col1["id"], "T1")
        _create_task(client, board["id"], col2["id"], "T2")
        resp = client.get(f"/api/boards/{board['id']}/tasks", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get(
            f"/api/boards/{board['id']}/tasks?column_id={col1['id']}",
            headers=AUTH_HEADERS)
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "T1"

    def test_list_tasks_empty(self, client):
        board = _create_board(client)
        resp = client.get(f"/api/boards/{board['id']}/tasks", headers=AUTH_HEADERS)
        assert resp.json() == []

    def test_patch_task_title_emits_updated(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"])
        with patch("api.board_routes._emitter", new=AsyncMock()) as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "title": "Renamed"},
                headers=AUTH_HEADERS)
            emitter.emit_task_updated.assert_awaited_once()
        assert resp.status_code == 200
        assert resp.json()["title"] == "Renamed"
        assert resp.json()["version_id"] == 2

    def test_patch_task_move_emits_moved(self, client):
        board = _create_board(client)
        col1 = _create_column(client, board["id"], "Todo", 0)
        col2 = _create_column(client, board["id"], "Done", 1)
        task = _create_task(client, board["id"], col1["id"])
        with patch("api.board_routes._emitter", new=AsyncMock()) as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "column_id": col2["id"]},
                headers=AUTH_HEADERS)
            emitter.emit_task_moved.assert_awaited_once()
            emitter.emit_task_updated.assert_not_awaited()
        assert resp.json()["column_id"] == col2["id"]

    def test_patch_task_status_transition_emits_transitioned(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"])
        with patch("api.board_routes._emitter", new=AsyncMock()) as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "status": "todo"},
                headers=AUTH_HEADERS)
            emitter.emit_task_transitioned.assert_awaited_once()
            emitter.emit_task_updated.assert_not_awaited()
        assert resp.json()["status"] == "todo"

    def test_patch_task_move_and_transition_no_updated(self, client):
        board = _create_board(client)
        col1 = _create_column(client, board["id"], "Todo", 0)
        col2 = _create_column(client, board["id"], "Done", 1)
        task = _create_task(client, board["id"], col1["id"])
        with patch("api.board_routes._emitter", new=AsyncMock()) as emitter:
            client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "column_id": col2["id"],
                      "status": "todo"},
                headers=AUTH_HEADERS)
            emitter.emit_task_updated.assert_not_awaited()

    def test_patch_task_stale_version_409(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"])
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/{task['id']}",
            json={"expected_version": 99, "title": "X"},
            headers=AUTH_HEADERS)
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "stale_version"

    def test_patch_task_illegal_transition_422(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"])
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/{task['id']}",
            json={"expected_version": 1, "status": "archived"},
            headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"] == "illegal_transition"

    def test_patch_task_missing_404(self, client):
        board = _create_board(client)
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/nope",
            json={"expected_version": 1, "title": "X"},
            headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_patch_task_missing_expected_version_422(self, client):
        board = _create_board(client)
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/nope",
            json={"title": "X"},
            headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_delete_task_success_204(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"])
        with patch("api.board_routes._emitter", new=AsyncMock()) as emitter:
            resp = client.delete(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                headers=AUTH_HEADERS)
            emitter.emit_task_deleted.assert_awaited_once()
        assert resp.status_code == 204

    def test_delete_task_missing_404(self, client):
        board = _create_board(client)
        resp = client.delete(
            f"/api/boards/{board['id']}/tasks/nope", headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestTaskCanvas:
    def test_get_task_canvas_redirect(self, client, db):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        canvas = Canvas(
            id="canvas-1", name="WS", canvas_type="kanban", status="active",
            tenant_id="t1", created_by="user-1",
        )
        db.add(canvas)
        db.commit()
        task = _create_task(client, board["id"], col["id"])
        from core.models_board import BoardTask
        obj = db.query(BoardTask).filter(BoardTask.id == task["id"]).first()
        obj.canvas_id = "canvas-1"
        db.commit()
        resp = client.get(
            f"/api/boards/{board['id']}/tasks/{task['id']}/canvas",
            headers=AUTH_HEADERS, follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "/canvas/canvas-1"

    def test_get_task_canvas_404_when_task_missing(self, client):
        board = _create_board(client)
        resp = client.get(
            f"/api/boards/{board['id']}/tasks/nope/canvas",
            headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_get_task_canvas_404_when_no_canvas(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"])
        resp = client.get(
            f"/api/boards/{board['id']}/tasks/{task['id']}/canvas",
            headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_serialize_task_with_canvas_summary(self, client, db):
        """_canvas_summary path: canvas row exists with artifacts + presence."""
        board = _create_board(client)
        col = _create_column(client, board["id"])
        canvas = Canvas(
            id="canvas-2", name="WS2", canvas_type="kanban", status="active",
            tenant_id="t1", created_by="user-1",
        )
        db.add(canvas)
        db.add(Artifact(id="art-1", canvas_id="canvas-2", type="doc",
                        tenant_id="t1", workspace_id="ws-1", name="a1", content="c"))
        db.add(AgentCanvasPresence(
            id="pres-1", canvas_id="canvas-2", agent_id="agent-9",
            tenant_id="t1", status="active"))
        db.add(AgentCanvasPresence(
            id="pres-2", canvas_id="canvas-2", agent_id="agent-8",
            tenant_id="t1", status="inactive"))
        db.commit()
        task = _create_task(client, board["id"], col["id"])
        from core.models_board import BoardTask
        obj = db.query(BoardTask).filter(BoardTask.id == task["id"]).first()
        obj.canvas_id = "canvas-2"
        db.commit()
        resp = client.get(f"/api/boards/{board['id']}/tasks", headers=AUTH_HEADERS)
        summary = resp.json()[0]["canvas"]
        assert summary["canvas_id"] == "canvas-2"
        assert summary["name"] == "WS2"
        assert summary["artifact_count"] == 1
        assert summary["presence_count"] == 1

    def test_serialize_task_canvas_row_missing(self, client, db):
        """_canvas_summary: task.canvas_id set but Canvas row deleted -> None."""
        board = _create_board(client)
        col = _create_column(client, board["id"])
        task = _create_task(client, board["id"], col["id"])
        from core.models_board import BoardTask
        obj = db.query(BoardTask).filter(BoardTask.id == task["id"]).first()
        obj.canvas_id = "ghost-canvas"
        db.commit()
        resp = client.get(f"/api/boards/{board['id']}/tasks", headers=AUTH_HEADERS)
        assert resp.json()[0]["canvas"] is None


class TestRebalance:
    def test_rebalance_specific_column(self, client):
        board = _create_board(client)
        col = _create_column(client, board["id"])
        _create_task(client, board["id"], col["id"])
        resp = client.post(f"/api/boards/{board['id']}/rebalance",
                           json={"column_id": col["id"]}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["moved_tasks"] == 0
        assert body["rebalanced_columns"] == [col["id"]]

    def test_rebalance_all_columns(self, client):
        resp = client.post("/api/boards", json={
            "name": "NoSeed", "seed_default_columns": False}, headers=AUTH_HEADERS)
        board = resp.json()
        _create_column(client, board["id"], "Todo", 0)
        _create_column(client, board["id"], "Done", 1)
        resp = client.post(f"/api/boards/{board['id']}/rebalance",
                           json={"column_id": None}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()["rebalanced_columns"]) == 2

    def test_rebalance_missing_board_404(self, client):
        resp = client.post("/api/boards/nope/rebalance",
                           json={"column_id": None}, headers=AUTH_HEADERS)
        assert resp.status_code == 404
