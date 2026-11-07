"""Board ownership boundary — peer/owner twins, authority races, readback.

The board schema has no membership/sharing relation, so ``Board.owner_user_id``
is the authoritative collaboration boundary.  These tests exercise the real
FastAPI board/comment/decompose routers, the real BoardService/comment/
decomposer/command-router consumers, and the registered ``tasks.create`` tool
against scratch SQLite rows.  No live model/provider/DB is used.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentMessage, Artifact, Canvas, Tenant, User, Workspace
from core.models_board import Board, BoardColumn, BoardTask

import api.board_comment_routes as board_comment_routes
import api.board_decompose_routes as board_decompose_routes
import api.board_routes as board_routes


BOARD_TABLES = [
    "tenants", "users", "workspaces", "boards", "board_columns", "board_tasks",
    "canvases", "canvas_audit", "agent_canvas_presence", "artifacts",
    "agent_messages", "artifact_comments", "agent_registry",
]

OWNER = "owner-1"
PEER = "peer-1"
INACTIVE = "inactive-1"


def _make_user(user_id: str, status: str = "active", first_name: str = "Test") -> User:
    return User(
        id=user_id,
        email=f"{user_id}@example.test",
        hashed_password="not-a-login-secret",
        first_name=first_name,
        last_name="User",
        role="member",
        status=status,
        is_active=status == "active",
    )


@pytest.fixture()
def world(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "board-owner.db"),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables[n] for n in BOARD_TABLES if n in Base.metadata.tables],
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    owner_board = str(uuid.uuid4())
    peer_board = str(uuid.uuid4())
    owner_col = str(uuid.uuid4())
    owner_todo = str(uuid.uuid4())
    peer_col = str(uuid.uuid4())
    owner_task = str(uuid.uuid4())
    peer_task = str(uuid.uuid4())

    with Session() as db:
        db.add_all([_make_user(OWNER), _make_user(PEER)])
        db.add(_make_user(INACTIVE, status="suspended"))
        db.add_all([
            Board(id=owner_board, name="Owner board", owner_user_id=OWNER),
            Board(id=peer_board, name="Peer board", owner_user_id=PEER),
            BoardColumn(id=owner_col, board_id=owner_board, name="Backlog", position=0),
            BoardColumn(id=owner_todo, board_id=owner_board, name="To Do", position=1),
            BoardColumn(id=peer_col, board_id=peer_board, name="Backlog", position=0),
            BoardTask(
                id=owner_task, board_id=owner_board, column_id=owner_col,
                title="Owner task", status="backlog", sort_order=0.0,
                created_by_user_id=OWNER,
            ),
            BoardTask(
                id=peer_task, board_id=peer_board, column_id=peer_col,
                title="Peer task", status="backlog", sort_order=0.0,
                created_by_user_id=PEER,
            ),
        ])
        db.commit()

    app = FastAPI()
    app.include_router(board_routes.router)
    app.include_router(board_comment_routes.router)
    app.include_router(board_decompose_routes.router)

    holder = {"user_id": OWNER}

    def session_dep():
        with Session() as db:
            yield db

    def actor_dep():
        with Session() as db:
            return db.get(User, holder["user_id"])

    app.dependency_overrides[get_db] = session_dep
    app.dependency_overrides[get_current_user] = actor_dep

    created = AsyncMock()
    moved = AsyncMock()
    transitioned = AsyncMock()
    updated = AsyncMock()
    deleted = AsyncMock()
    comment_posted = AsyncMock()
    emitter = SimpleNamespace(
        emit_task_created=created,
        emit_task_moved=moved,
        emit_task_transitioned=transitioned,
        emit_task_updated=updated,
        emit_task_deleted=deleted,
        emit_comment_posted=comment_posted,
    )
    monkeypatch.setattr(board_routes, "_emitter", emitter)
    monkeypatch.setattr(board_comment_routes, "_emitter", emitter)
    monkeypatch.setattr(board_decompose_routes, "_emitter", emitter)

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            holder=holder,
            Session=Session,
            engine=engine,
            emitter=emitter,
            owner_board=owner_board,
            peer_board=peer_board,
            owner_col=owner_col,
            owner_todo=owner_todo,
            peer_col=peer_col,
            owner_task=owner_task,
            peer_task=peer_task,
        )


def _as(world, user_id: str) -> TestClient:
    world.holder["user_id"] = user_id
    return world.client


def _counts(world) -> dict:
    with world.Session() as db:
        return {
            "columns": db.query(BoardColumn).count(),
            "tasks": db.query(BoardTask).count(),
            "comments": db.query(AgentMessage).filter(
                AgentMessage.message_type == "board_comment"
            ).count(),
        }


def _owner_task_state(world) -> tuple:
    with world.Session() as db:
        task = db.query(BoardTask).filter(BoardTask.id == world.owner_task).first()
        return (task.title, task.status, task.version_id)


# --------------------------------------------------------------------------- #
# Peer negative twins
# --------------------------------------------------------------------------- #
def test_peer_read_and_write_twins_are_denied_without_side_effects(world):
    peer = _as(world, PEER)
    before = _counts(world)
    before_task = _owner_task_state(world)

    # Read paths
    assert peer.get(f"/api/boards/{world.owner_board}").status_code == 404
    assert peer.get(f"/api/boards/{world.owner_board}/tasks").status_code == 404
    assert peer.get(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}/canvas"
    ).status_code == 404
    assert peer.get(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}/comments"
    ).status_code == 404
    assert peer.get(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}/artifact-comments"
    ).status_code == 404

    # Write paths
    assert peer.post(
        f"/api/boards/{world.owner_board}/columns", json={"name": "Injected"}
    ).status_code == 404
    created = peer.post(
        f"/api/boards/{world.owner_board}/tasks",
        json={"title": "Injected", "column_id": world.owner_col},
    )
    assert created.status_code == 404
    assert peer.patch(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}",
        json={"expected_version": 1, "title": "Hijacked"},
    ).status_code == 404
    assert peer.delete(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}"
    ).status_code == 404
    assert peer.post(
        f"/api/boards/{world.owner_board}/rebalance", json={}
    ).status_code == 404

    # Comment paths (including a comment that already exists on the board)
    owner = _as(world, OWNER)
    comment = owner.post(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}/comments",
        json={"content": "owner note"},
    )
    assert comment.status_code == 201
    comment_id = comment.json()["id"]

    # The owner's legitimate comment emitted one event; reset before checking
    # that every denied peer request is silent.
    for method in (
        world.emitter.emit_task_created,
        world.emitter.emit_task_moved,
        world.emitter.emit_task_transitioned,
        world.emitter.emit_task_updated,
        world.emitter.emit_task_deleted,
        world.emitter.emit_comment_posted,
    ):
        method.reset_mock()

    peer = _as(world, PEER)
    assert peer.post(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}/comments",
        json={"content": "peer note"},
    ).status_code == 404
    assert peer.patch(
        f"/api/comments/{comment_id}", json={"content": "hijacked"}
    ).status_code == 404
    assert peer.delete(f"/api/comments/{comment_id}").status_code == 404

    # Decomposition paths deny before the LLM/BYOK stage.
    assert peer.post(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}/decompose",
        json={},
    ).status_code == 404
    assert peer.post(
        f"/api/boards/{world.owner_board}/tasks/{world.owner_task}/decompose/commit",
        json={"proposals": [{"title": "child"}]},
    ).status_code == 404

    # Listing only shows the peer's own board.
    listing = peer.get("/api/boards").json()
    assert [b["id"] for b in listing] == [world.peer_board]

    after = _counts(world)
    assert after["columns"] == before["columns"]
    assert after["tasks"] == before["tasks"]
    # Exactly the owner's one comment was added; peer attempts added nothing.
    assert after["comments"] == before["comments"] + 1
    assert _owner_task_state(world) == before_task
    with world.Session() as db:
        assert db.query(AgentMessage).filter(AgentMessage.id == comment_id).first().content == "owner note"

    # No live event was dispatched by any denied request.
    for method in (
        world.emitter.emit_task_created,
        world.emitter.emit_task_moved,
        world.emitter.emit_task_transitioned,
        world.emitter.emit_task_updated,
        world.emitter.emit_task_deleted,
        world.emitter.emit_comment_posted,
    ):
        method.assert_not_awaited()


def test_peer_command_router_and_registered_tool_are_denied(world):
    from core.action_registry import action_registry
    from core.board_command_router import BoardCommandRouter

    with world.Session() as db:
        router = BoardCommandRouter(db, actor_user_id=PEER)
        reply = router.route(
            action_type="board_create",
            parameters={"title": "Injected", "column": "Backlog"},
            user_id=PEER,
            board_id=world.owner_board,
        )
    assert reply.ok is False
    assert "Couldn't do that" in reply.reply or "Couldn't find" in reply.reply

    @contextmanager
    def session_cm():
        with world.Session() as db:
            yield db

    before = _counts(world)["tasks"]
    with patch("core.database.get_db_session", session_cm):
        peer_out = _run_action(
            action_registry, "tasks.create",
            {"title": "Injected", "board_id": world.owner_board, "column_id": world.owner_col},
            {"user_id": PEER},
        )
    assert peer_out["success"] is False
    assert _counts(world)["tasks"] == before

    with patch("core.database.get_db_session", session_cm):
        owner_out = _run_action(
            action_registry, "tasks.create",
            {"title": "Allowed", "board_id": world.owner_board, "column_id": world.owner_col},
            {"user_id": OWNER},
        )
    assert owner_out["success"] is True
    assert _counts(world)["tasks"] == before + 1


def _run_action(action_registry, name, args, context):
    import asyncio

    return asyncio.run(action_registry.execute_action(name, args, context))


# --------------------------------------------------------------------------- #
# Valid-owner twins + fresh-session readback
# --------------------------------------------------------------------------- #
def test_owner_twins_and_fresh_session_readback(world):
    owner = _as(world, OWNER)

    column = owner.post(
        f"/api/boards/{world.owner_board}/columns", json={"name": "In Review"}
    )
    assert column.status_code == 201
    new_col = column.json()["id"]

    task = owner.post(
        f"/api/boards/{world.owner_board}/tasks",
        json={"title": "Owned task", "column_id": new_col},
    )
    assert task.status_code == 201
    task_id = task.json()["id"]
    assert task.json()["board_id"] == world.owner_board
    assert task.json()["column_id"] == new_col
    assert task.json()["canvas"] is None

    detail = owner.get(f"/api/boards/{world.owner_board}")
    assert detail.status_code == 200
    assert any(c["id"] == new_col for c in detail.json()["columns"])
    assert owner.get(f"/api/boards/{world.owner_board}/tasks").status_code == 200

    # Existing optimistic-locking and state-machine contracts still apply.
    assert owner.patch(
        f"/api/boards/{world.owner_board}/tasks/{task_id}",
        json={"expected_version": 999, "title": "stale"},
    ).status_code == 409
    assert owner.patch(
        f"/api/boards/{world.owner_board}/tasks/{task_id}",
        json={"expected_version": 1, "status": "done"},
    ).status_code == 422
    moved = owner.patch(
        f"/api/boards/{world.owner_board}/tasks/{task_id}",
        json={"expected_version": 1, "status": "todo"},
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "todo"

    # A brand-new session (not the request session) sees the committed state.
    with world.Session() as db:
        row = db.query(BoardTask).filter(BoardTask.id == task_id).first()
        assert row is not None
        assert row.status == "todo"
        assert str(row.board_id) == world.owner_board
        assert db.query(BoardColumn).filter(BoardColumn.id == new_col).first() is not None

    assert owner.delete(
        f"/api/boards/{world.owner_board}/tasks/{task_id}"
    ).status_code == 204
    with world.Session() as db:
        assert db.query(BoardTask).filter(BoardTask.id == task_id).first() is None


# --------------------------------------------------------------------------- #
# Authority races: owner transfer + actor deactivation
# --------------------------------------------------------------------------- #
def test_owner_transfer_is_authoritative_at_mutation(world):
    # The former owner can read before the transfer.
    owner = _as(world, OWNER)
    assert owner.get(f"/api/boards/{world.owner_board}").status_code == 200

    with world.Session() as db:
        board = db.query(Board).filter(Board.id == world.owner_board).first()
        board.owner_user_id = PEER
        db.commit()

    before = _counts(world)["columns"]
    stale_owner = _as(world, OWNER)
    assert stale_owner.get(f"/api/boards/{world.owner_board}").status_code == 404
    assert stale_owner.post(
        f"/api/boards/{world.owner_board}/columns", json={"name": "After transfer"}
    ).status_code == 404
    assert _counts(world)["columns"] == before

    new_owner = _as(world, PEER)
    assert new_owner.get(f"/api/boards/{world.owner_board}").status_code == 200
    created = new_owner.post(
        f"/api/boards/{world.owner_board}/columns", json={"name": "After transfer"}
    )
    assert created.status_code == 201
    with world.Session() as db:
        assert db.query(BoardColumn).filter(BoardColumn.id == created.json()["id"]).first() is not None


def test_deactivated_actor_has_zero_effect(world):
    owner = _as(world, OWNER)
    before = _counts(world)["columns"]

    with world.Session() as db:
        user = db.query(User).filter(User.id == OWNER).first()
        user.status = "suspended"
        user.is_active = False
        db.commit()

    denied = owner.post(
        f"/api/boards/{world.owner_board}/columns", json={"name": "While suspended"}
    )
    assert denied.status_code == 403
    assert _counts(world)["columns"] == before
    world.emitter.emit_task_created.assert_not_awaited()

    with world.Session() as db:
        user = db.query(User).filter(User.id == OWNER).first()
        user.status = "active"
        user.is_active = True
        db.commit()

    recovered = owner.post(
        f"/api/boards/{world.owner_board}/columns", json={"name": "After reactivation"}
    )
    assert recovered.status_code == 201
    assert _counts(world)["columns"] == before + 1
