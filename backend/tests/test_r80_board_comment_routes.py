# -*- coding: utf-8 -*-
"""
Round 80 — gap coverage: api/board_comment_routes.py (task-level comment
CRUD + thread tree + artifact-comment aggregation; zero test references
before this file — the only api/r80 module with a live importer, minimal_app.py).

Standalone FastAPI app with ``get_db`` (in-memory SQLite, StaticPool for the
TestClient worker thread) and ``get_current_user`` overridden. Board/column/
task rows are seeded via ORM for determinism.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.board_comment_service import task_conversation_id
from core.models import (
    AgentMessage,
    Artifact,
    ArtifactComment,
    Canvas,
    Tenant,
    User,
    Workspace,
)
from core.models_board import Board, BoardColumn, BoardTask


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        "tenants", "users", "workspaces", "boards", "board_columns", "board_tasks",
        "canvases", "canvas_audit", "agent_canvas_presence", "artifacts",
        "agent_messages", "artifact_comments", "agent_registry",
    ]
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables[n] for n in tables if n in Base.metadata.tables],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture()
def populated(db_session):
    db_session.add(Tenant(id="t1", name="T", subdomain="t-default"))
    db_session.add(User(
        id="user-1", tenant_id="t1", email="u1@x.com",
        first_name="A", last_name="B", hashed_password="pw",
        role="admin", status="active",
    ))
    db_session.add(User(
        id="user-2", tenant_id="t1", email="u2@x.com",
        first_name="Other", last_name="User", hashed_password="pw",
        role="member", status="active",
    ))
    db_session.add(Board(id="board-1", name="B", owner_user_id="user-1"))
    db_session.add(BoardColumn(id="col-1", board_id="board-1", name="To Do", position=0))
    db_session.add(BoardTask(
        id="task-1", board_id="board-1", column_id="col-1",
        title="T", status="todo", sort_order=0.0,
    ))
    db_session.commit()


@pytest.fixture()
def task_with_canvas(db_session, populated):
    ws = Workspace(id="ws-1", tenant_id="t1", name="WS")
    db_session.add(ws)
    canvas = Canvas(
        id="canvas-1", tenant_id="t1", workspace_id="ws-1",
        created_by="user-1", name="Task: X", canvas_type="kanban",
    )
    db_session.add(canvas)
    db_session.add(BoardTask(
        id="task-canvas", board_id="board-1", column_id="col-1",
        title="With canvas", status="todo", sort_order=1.0, canvas_id="canvas-1",
    ))
    db_session.add(Artifact(
        id="artifact-1", tenant_id="t1", workspace_id="ws-1", canvas_id="canvas-1",
        name="out.md", type="markdown", content="hello",
    ))
    db_session.commit()
    return {"task_id": "task-canvas", "canvas_id": "canvas-1"}


@pytest.fixture()
def client(db_session, populated):
    from core.database import get_db
    from core.security_dependencies import get_current_user
    from api.board_comment_routes import router

    holder = {"user_id": "user-1"}
    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db_session

    def override_user():
        return SimpleNamespace(id=holder["user_id"])

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as c:
        yield c, holder


@pytest.fixture()
def anon_client(db_session, populated):
    from core.database import get_db
    from api.board_comment_routes import router

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c


def _create_comment(client, task_id="task-1", content="hello", parent_message_id=None):
    payload = {"content": content}
    if parent_message_id is not None:
        payload["parent_message_id"] = parent_message_id
    return client.post(
        f"/api/boards/board-1/tasks/{task_id}/comments",
        json=payload,
    )


def _seed_comment(db, task_id, content, created_at, mid, from_user_id="user-1"):
    db.add(AgentMessage(
        id=mid, tenant_id="t1", from_user_id=from_user_id,
        message_type="board_comment", content=content,
        task_id=task_id, conversation_id=task_conversation_id(task_id),
        status="delivered", created_at=created_at,
    ))
    db.commit()


class TestAuth:
    def test_routes_require_authentication(self, anon_client):
        assert anon_client.get("/api/boards/board-1/tasks/task-1/comments").status_code == 401
        assert anon_client.patch("/api/comments/x", json={"content": "x"}).status_code == 401
        assert anon_client.delete("/api/comments/x").status_code == 401


class TestCreateTaskComment:
    def test_create_comment_201_with_author_display(self, client):
        c, _ = client
        r = _create_comment(c, content="hello world")
        assert r.status_code == 201
        body = r.json()
        assert body["content"] == "hello world"
        assert body["task_id"] == "task-1"
        assert body["author"]["user_id"] == "user-1"
        assert body["author"]["display_name"] == "A B"
        assert body["replies"] == []

    def test_create_comment_emits_board_event(self, client):
        c, _ = client
        with patch("api.board_comment_routes._emitter", new=AsyncMock()) as emitter:
            r = _create_comment(c, content="ping")
        assert r.status_code == 201
        emitter.emit_comment_posted.assert_awaited_once()
        kwargs = emitter.emit_comment_posted.await_args.kwargs
        assert kwargs["comment_id"] == r.json()["id"]

    def test_create_reply_threads_to_parent(self, client):
        c, _ = client
        parent = _create_comment(c, content="parent")
        reply = _create_comment(c, content="reply", parent_message_id=parent.json()["id"])
        assert reply.status_code == 201
        assert reply.json()["parent_message_id"] == parent.json()["id"]

    def test_create_missing_task_404(self, client):
        c, _ = client
        r = _create_comment(c, task_id="no-such-task")
        assert r.status_code == 404

    def test_create_unknown_parent_404(self, client):
        c, _ = client
        r = _create_comment(c, content="x", parent_message_id="no-such-parent")
        assert r.status_code == 404

    def test_create_empty_content_422(self, client):
        c, _ = client
        assert _create_comment(c, content="").status_code == 422


class TestListTaskComments:
    def test_list_empty_returns_200_empty(self, client):
        c, _ = client
        r = c.get("/api/boards/board-1/tasks/task-1/comments")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_returns_thread_tree(self, client, db_session):
        c, _ = client
        parent = _create_comment(c, content="parent").json()["id"]
        r1 = _create_comment(c, content="reply-1", parent_message_id=parent).json()["id"]
        _create_comment(c, content="reply-2", parent_message_id=parent)
        _create_comment(c, content="nested", parent_message_id=r1)

        r = c.get("/api/boards/board-1/tasks/task-1/comments")
        assert r.status_code == 200
        tree = r.json()
        assert len(tree) == 1
        root = tree[0]
        assert root["content"] == "parent"
        assert len(root["replies"]) == 2
        r1_node = next(x for x in root["replies"] if x["content"] == "reply-1")
        assert len(r1_node["replies"]) == 1
        assert r1_node["replies"][0]["content"] == "nested"

    def test_list_before_id_pagination(self, client, db_session):
        c, _ = client
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _seed_comment(db_session, "task-1", "old", base, "m-old")
        _seed_comment(db_session, "task-1", "mid", base + timedelta(minutes=1), "m-mid")
        _seed_comment(db_session, "task-1", "new", base + timedelta(minutes=2), "m-new")

        r = c.get("/api/boards/board-1/tasks/task-1/comments", params={"before_id": "m-mid"})
        assert r.status_code == 200
        assert [x["content"] for x in r.json()] == ["old"]

        r = c.get("/api/boards/board-1/tasks/task-1/comments")
        assert [x["content"] for x in r.json()] == ["old", "mid", "new"]

    def test_list_limit_validation(self, client):
        c, _ = client
        assert c.get(
            "/api/boards/board-1/tasks/task-1/comments", params={"limit": 0}
        ).status_code == 422
        assert c.get(
            "/api/boards/board-1/tasks/task-1/comments", params={"limit": 501}
        ).status_code == 422


class TestPatchComment:
    def test_patch_own_comment_200(self, client, db_session):
        c, _ = client
        cid = _create_comment(c, content="orig").json()["id"]
        r = c.patch(f"/api/comments/{cid}", json={"content": "fixed"})
        assert r.status_code == 200
        assert r.json()["content"] == "fixed"

    def test_patch_foreign_comment_403(self, client):
        c, holder = client
        cid = _create_comment(c, content="mine").json()["id"]
        holder["user_id"] = "user-2"
        r = c.patch(f"/api/comments/{cid}", json={"content": "hack"})
        assert r.status_code == 403

    def test_patch_missing_comment_404(self, client):
        c, _ = client
        assert c.patch("/api/comments/nope", json={"content": "x"}).status_code == 404


class TestDeleteComment:
    def test_delete_own_comment_204(self, client, db_session):
        c, _ = client
        cid = _create_comment(c, content="bye").json()["id"]
        r = c.delete(f"/api/comments/{cid}")
        assert r.status_code == 204
        remaining = db_session.query(AgentMessage).filter(AgentMessage.id == cid).first()
        assert remaining is None

    def test_delete_foreign_comment_403(self, client):
        c, holder = client
        cid = _create_comment(c, content="mine").json()["id"]
        holder["user_id"] = "user-2"
        assert c.delete(f"/api/comments/{cid}").status_code == 403

    def test_delete_missing_comment_404(self, client):
        c, _ = client
        assert c.delete("/api/comments/nope").status_code == 404


class TestArtifactComments:
    def test_artifact_comments_aggregated_for_task_canvas(self, client, db_session, task_with_canvas):
        c, _ = client
        db_session.add(ArtifactComment(
            id="ac-1", tenant_id="t1", artifact_id="artifact-1",
            user_id="user-1", content="typo in line 3",
        ))
        db_session.commit()

        r = c.get("/api/boards/board-1/tasks/task-canvas/artifact-comments")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["content"] == "typo in line 3"
        assert rows[0]["artifact_id"] == "artifact-1"
        assert rows[0]["canvas_id"] == "canvas-1"
        assert rows[0]["user_id"] == "user-1"

    def test_artifact_comments_empty_when_task_has_no_canvas(self, client):
        c, _ = client
        r = c.get("/api/boards/board-1/tasks/task-1/artifact-comments")
        assert r.status_code == 200
        assert r.json() == []

    def test_artifact_comments_missing_task_404(self, client):
        c, _ = client
        r = c.get("/api/boards/board-1/tasks/nope/artifact-comments")
        assert r.status_code == 404
