"""Board authority is claimed by the first DML, not by an earlier SELECT.

The supplied root probe (``test_lead_board_atomic_scope``) showed that a peer
could win an owner transfer or deactivate the actor *after* the request had
already read a valid board and *before* its first INSERT/UPDATE/DELETE.  The
old ``SELECT ... FOR UPDATE`` did not help on SQLite, which ignores row-locking
clauses, so the write still produced a 201.

These tests reproduce that exact boundary against the real routers/services
and then exercise the same first-DML race across every board mutation consumer:
column/task create, task patch/delete, rebalance, comments, decomposition and
board creation (actor-only claim).  A ``none`` twin proves the normal write is
still admitted; the two race twins prove the effect is refused and no row or
event is left behind.

Scratch SQLite only.  No live model/provider/world is used.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import sessionmaker

from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentMessage, User
from core.models_board import Board, BoardColumn, BoardTask

import api.board_comment_routes as board_comment_routes
import api.board_decompose_routes as board_decompose_routes
import api.board_routes as board_routes

RACES = ("none", "owner_transfer", "actor_deactivated")


class World:
    def __init__(self, tmp_path, monkeypatch):
        self.engine = create_engine(
            "sqlite:///" + str(tmp_path / "board-authority.db"),
            connect_args={"check_same_thread": False, "timeout": 2},
        )
        Base.metadata.create_all(self.engine)
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

        self.actor = str(uuid.uuid4())
        self.peer = str(uuid.uuid4())
        self.board_id = str(uuid.uuid4())
        self.column_id = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        self.task_two_id = str(uuid.uuid4())
        self.comment_id = str(uuid.uuid4())

        with self.Session() as setup:
            for uid in (self.actor, self.peer):
                setup.add(
                    User(
                        id=uid,
                        email=uid + "@example.test",
                        first_name="Scratch",
                        last_name="User",
                        hashed_password="not-a-login-secret",
                        role="member",
                        status="active",
                        is_active=True,
                    )
                )
            setup.add(
                Board(
                    id=self.board_id,
                    name="Atomic owned board",
                    owner_user_id=self.actor,
                )
            )
            setup.add(
                BoardColumn(
                    id=self.column_id,
                    board_id=self.board_id,
                    name="Backlog",
                    position=0,
                )
            )
            setup.add_all(
                [
                    BoardTask(
                        id=self.task_id,
                        board_id=self.board_id,
                        column_id=self.column_id,
                        title="Original task",
                        status="backlog",
                        sort_order=10.0,
                        created_by_user_id=self.actor,
                    ),
                    BoardTask(
                        id=self.task_two_id,
                        board_id=self.board_id,
                        column_id=self.column_id,
                        title="Second task",
                        status="backlog",
                        sort_order=20.0,
                        created_by_user_id=self.actor,
                    ),
                    AgentMessage(
                        id=self.comment_id,
                        tenant_id="default",
                        from_user_id=self.actor,
                        message_type="board_comment",
                        content="original comment",
                        task_id=self.task_id,
                        conversation_id=f"board_task:{self.task_id}",
                        status="delivered",
                    ),
                ]
            )
            setup.commit()

        self.app = FastAPI()
        self.app.include_router(board_routes.router)
        self.app.include_router(board_comment_routes.router)
        self.app.include_router(board_decompose_routes.router)

        emitter = SimpleNamespace(
            emit_task_created=AsyncMock(),
            emit_task_moved=AsyncMock(),
            emit_task_transitioned=AsyncMock(),
            emit_task_updated=AsyncMock(),
            emit_task_deleted=AsyncMock(),
            emit_comment_posted=AsyncMock(),
        )
        monkeypatch.setattr(board_routes, "_emitter", emitter)
        monkeypatch.setattr(board_comment_routes, "_emitter", emitter)
        monkeypatch.setattr(board_decompose_routes, "_emitter", emitter)
        self.emitter = emitter

    def request(self, race, method, url, **kwargs):
        """Run one request whose peer wins immediately before its first DML."""
        writer = self.Session()
        writer_connection = writer.connection()
        fired = []
        engine = self.engine

        def before_first_dml(conn, cursor, statement, parameters, context, executemany):
            if conn is not writer_connection or fired:
                return
            if not statement.lstrip().upper().startswith(("UPDATE ", "INSERT ", "DELETE ")):
                return
            fired.append(True)
            if race == "none":
                return
            with self.Session() as winner:
                if race == "owner_transfer":
                    winner.execute(
                        update(Board)
                        .where(Board.id == self.board_id)
                        .values(owner_user_id=self.peer)
                    )
                else:
                    winner.execute(
                        update(User)
                        .where(User.id == self.actor)
                        .values(is_active=False)
                    )
                winner.commit()

        event.listen(engine, "before_cursor_execute", before_first_dml)
        self.app.dependency_overrides[get_db] = lambda: writer
        self.app.dependency_overrides[get_current_user] = lambda: writer.get(
            User, self.actor
        )
        try:
            with TestClient(self.app, raise_server_exceptions=False) as client:
                response = client.request(method, url, **kwargs)
        finally:
            event.remove(engine, "before_cursor_execute", before_first_dml)
            self.app.dependency_overrides.clear()
            writer.close()
        assert fired, "the request must reach the real first-DML claim"
        return response

    def read(self, model, **filters):
        with self.Session() as db:
            query = db.query(model)
            for key, value in filters.items():
                query = query.filter(getattr(model, key) == value)
            return query.all()

    def count(self, model, **filters):
        return len(self.read(model, **filters))

    def close(self):
        self.engine.dispose()


def _assert_refused(response):
    assert response.status_code in (403, 404, 409), (
        response.status_code,
        response.text,
    )


# --------------------------------------------------------------------------- #
# Exact supplied boundary: column creation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("race", RACES)
def test_column_create_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "POST",
            f"/api/boards/{world.board_id}/columns",
            json={"name": "Authorized only before peer wins"},
        )
        count = world.count(BoardColumn, board_id=world.board_id) - 1
        if race == "none":
            assert response.status_code == 201, response.text
            assert count == 1
        else:
            _assert_refused(response)
            assert count == 0
        with world.Session() as db:
            if race == "owner_transfer":
                assert db.get(Board, world.board_id).owner_user_id == world.peer
            elif race == "actor_deactivated":
                assert db.get(User, world.actor).is_active is False
    finally:
        world.close()


# --------------------------------------------------------------------------- #
# Task create / patch / delete
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("race", RACES)
def test_task_create_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "POST",
            f"/api/boards/{world.board_id}/tasks",
            json={"title": "Raced task", "column_id": world.column_id},
        )
        if race == "none":
            assert response.status_code == 201, response.text
            assert world.count(BoardTask, board_id=world.board_id) == 3
        else:
            _assert_refused(response)
            assert world.count(BoardTask, board_id=world.board_id) == 2
    finally:
        world.close()


@pytest.mark.parametrize("race", RACES)
def test_task_patch_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "PATCH",
            f"/api/boards/{world.board_id}/tasks/{world.task_id}",
            json={"expected_version": 1, "title": "Raced title"},
        )
        task = world.read(BoardTask, id=world.task_id)[0]
        if race == "none":
            assert response.status_code == 200, response.text
            assert task.title == "Raced title"
        else:
            _assert_refused(response)
            assert task.title == "Original task"
    finally:
        world.close()


@pytest.mark.parametrize("race", RACES)
def test_task_delete_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "DELETE",
            f"/api/boards/{world.board_id}/tasks/{world.task_id}",
        )
        if race == "none":
            assert response.status_code == 204, response.text
            assert world.count(BoardTask, id=world.task_id) == 0
        else:
            _assert_refused(response)
            assert world.count(BoardTask, id=world.task_id) == 1
    finally:
        world.close()


@pytest.mark.parametrize("race", RACES)
def test_rebalance_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "POST",
            f"/api/boards/{world.board_id}/rebalance",
            json={"column_id": world.column_id},
        )
        tasks = world.read(BoardTask, board_id=world.board_id)
        orders = sorted(float(t.sort_order) for t in tasks)
        if race == "none":
            assert response.status_code == 200, response.text
            assert orders == [0.0, 1.0]
        else:
            _assert_refused(response)
            assert orders == [10.0, 20.0]
    finally:
        world.close()


# --------------------------------------------------------------------------- #
# Comments (create / patch / delete)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("race", RACES)
def test_comment_create_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "POST",
            f"/api/boards/{world.board_id}/tasks/{world.task_id}/comments",
            json={"content": "raced comment"},
        )
        count = world.count(
            AgentMessage, message_type="board_comment", task_id=world.task_id
        )
        if race == "none":
            assert response.status_code == 201, response.text
            assert count == 2
        else:
            _assert_refused(response)
            assert count == 1
    finally:
        world.close()


@pytest.mark.parametrize("race", RACES)
def test_comment_patch_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "PATCH",
            f"/api/comments/{world.comment_id}",
            json={"content": "raced edit"},
        )
        msg = world.read(AgentMessage, id=world.comment_id)[0]
        if race == "none":
            assert response.status_code == 200, response.text
            assert msg.content == "raced edit"
        else:
            _assert_refused(response)
            assert msg.content == "original comment"
    finally:
        world.close()


@pytest.mark.parametrize("race", RACES)
def test_comment_delete_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "DELETE",
            f"/api/comments/{world.comment_id}",
        )
        if race == "none":
            assert response.status_code == 204, response.text
            assert world.count(AgentMessage, id=world.comment_id) == 0
        else:
            _assert_refused(response)
            assert world.count(AgentMessage, id=world.comment_id) == 1
    finally:
        world.close()


# --------------------------------------------------------------------------- #
# Decomposition commit
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("race", RACES)
def test_decompose_commit_rechecks_authority_in_first_dml(tmp_path, race, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        response = world.request(
            race,
            "POST",
            f"/api/boards/{world.board_id}/tasks/{world.task_id}/decompose/commit",
            json={
                "proposals": [
                    {
                        "title": "Raced child",
                        "column_name": "Backlog",
                        "priority": "normal",
                    }
                ]
            },
        )
        children = [
            t for t in world.read(BoardTask, board_id=world.board_id)
            if str(t.parent_task_id) == world.task_id
        ]
        if race == "none":
            assert response.status_code == 201, response.text
            assert len(children) == 1
        else:
            _assert_refused(response)
            assert children == []
    finally:
        world.close()


# --------------------------------------------------------------------------- #
# Board creation: actor-only claim, no board exists yet
# --------------------------------------------------------------------------- #
def test_board_create_claims_actor_in_first_dml(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    try:
        before = world.count(Board)
        response = world.request(
            "actor_deactivated",
            "POST",
            "/api/boards",
            json={"name": "Should never exist", "seed_default_columns": False},
        )
        assert response.status_code == 403, response.text
        assert world.count(Board) == before
    finally:
        world.close()
