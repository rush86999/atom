"""Unit tests for core.board_service.BoardService.

Single-Tenant version for Upstream.
"""
from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.schemas.board_schemas import (
    BoardCreate,
    ColumnCreate,
    TaskCreate,
    TaskPatch,
)
from core.board_service import BoardService
from core.board_state_machine import BoardStatus
from core.database import Base
import core.models
from core.models import Canvas, Tenant, User, Workspace
from core.models_board import Board, BoardColumn, BoardTask


# --------------------------------------------------------------------------- #
# Session fixture
# --------------------------------------------------------------------------- #
@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    tables_for_board_tests = [
        "tenants",
        "users",
        "workspaces",
        "boards",
        "board_columns",
        "board_tasks",
        "canvases",
        "canvas_audit",
        "agent_canvas_presence",
        "artifacts",
    ]
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables[name]
            for name in tables_for_board_tests
            if name in Base.metadata.tables
        ],
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def default_tenant(db_session: Session) -> str:
    """Insert a default tenant row for Canvas/User constraints."""
    tid = "default-tenant"
    db_session.add(Tenant(id=tid, name="Default Tenant", subdomain="default"))
    db_session.commit()
    return tid


@pytest.fixture
def user_a(db_session: Session, default_tenant: str) -> str:
    uid = str(uuid.uuid4())
    db_session.add(User(
        id=uid,
        tenant_id=default_tenant,
        email=f"a-{uid[:8]}@example.com",
        first_name="First",
        last_name="Last",
        hashed_password="hashed_password",
        role="admin",
        status="active",
    ))
    db_session.commit()
    return uid


@pytest.fixture
def board_a(db_session: Session, user_a: str) -> Board:
    """Pre-create a board with the default 6 columns."""
    service = BoardService(db_session)
    return service.create_board(
        owner_user_id=user_a,
        payload=BoardCreate(name="Board A", seed_default_columns=True),
    )


# --------------------------------------------------------------------------- #
# Board CRUD
# --------------------------------------------------------------------------- #
class TestBoardCRUD:
    def test_create_board_seeds_default_columns(self, db_session, user_a):
        service = BoardService(db_session)
        board = service.create_board(
            owner_user_id=user_a,
            payload=BoardCreate(name="My Board"),
        )
        cols = service.list_columns(board.id)
        assert [c.name for c in cols] == [
            "Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done",
        ]
        assert all(c.position == i for i, c in enumerate(cols))

    def test_create_board_without_seeding_columns(self, db_session, user_a):
        service = BoardService(db_session)
        board = service.create_board(
            owner_user_id=user_a,
            payload=BoardCreate(name="Bare", seed_default_columns=False),
        )
        cols = service.list_columns(board.id)
        assert cols == []

    def test_list_boards(self, db_session, user_a):
        service = BoardService(db_session)
        service.create_board(
            owner_user_id=user_a,
            payload=BoardCreate(name="A1"),
        )
        boards = service.list_boards()
        assert "A1" in [b.name for b in boards]

    def test_get_board(self, db_session, board_a):
        service = BoardService(db_session)
        board = service.get_board(board_a.id)
        assert board.name == "Board A"


# --------------------------------------------------------------------------- #
# Task CRUD + state machine + optimistic locking
# --------------------------------------------------------------------------- #
class TestTaskCRUD:
    def _first_column_id(self, db_session, board_a) -> str:
        cols = BoardService(db_session).list_columns(board_a.id)
        return str(cols[0].id)

    def test_create_task_appends_to_end_of_column(self, db_session, board_a, user_a):
        service = BoardService(db_session)
        col_id = self._first_column_id(db_session, board_a)

        t1 = service.create_task(board_a.id, user_a, TaskCreate(title="T1", column_id=col_id))
        t2 = service.create_task(board_a.id, user_a, TaskCreate(title="T2", column_id=col_id))
        t3 = service.create_task(board_a.id, user_a, TaskCreate(title="T3", column_id=col_id))

        assert t1.sort_order < t2.sort_order < t3.sort_order
        assert t1.sort_order == 0.0
        assert t2.sort_order == 1.0
        assert t3.sort_order == 2.0

    def test_patch_unknown_status_returns_422(self, db_session, board_a, user_a):
        service = BoardService(db_session)
        col_id = self._first_column_id(db_session, board_a)
        task = service.create_task(board_a.id, user_a, TaskCreate(title="T", column_id=col_id))

        with pytest.raises(HTTPException) as exc:
            service.patch_task(
                board_a.id, task.id,
                TaskPatch(expected_version=task.version_id, status="bogus"),
            )
        assert exc.value.status_code == 422

    def test_patch_illegal_transition_returns_422_with_allowed_set(self, db_session, board_a, user_a):
        service = BoardService(db_session)
        col_id = self._first_column_id(db_session, board_a)
        task = service.create_task(
            board_a.id, user_a,
            TaskCreate(title="T", column_id=col_id, status=BoardStatus.BACKLOG),
        )

        with pytest.raises(HTTPException) as exc:
            service.patch_task(
                board_a.id, task.id,
                TaskPatch(expected_version=task.version_id, status=BoardStatus.DONE),
            )
        assert exc.value.status_code == 422
        body = exc.value.detail
        assert body["error"] == "illegal_transition"
        assert body["current"] == BoardStatus.BACKLOG
        assert body["requested"] == BoardStatus.DONE
        assert "todo" in [s.lower() for s in body["allowed_next"]]

    def test_patch_legal_transition_moves_status(self, db_session, board_a, user_a):
        service = BoardService(db_session)
        col_id = self._first_column_id(db_session, board_a)
        task = service.create_task(
            board_a.id, user_a,
            TaskCreate(title="T", column_id=col_id, status=BoardStatus.BACKLOG),
        )

        updated, _meta = service.patch_task(
            board_a.id, task.id,
            TaskPatch(expected_version=task.version_id, status=BoardStatus.TODO),
        )
        assert updated.status == BoardStatus.TODO
        assert updated.version_id > task.version_id

    def test_patch_with_stale_version_returns_409(self, db_session, board_a, user_a):
        service = BoardService(db_session)
        col_id = self._first_column_id(db_session, board_a)
        task = service.create_task(
            board_a.id, user_a, TaskCreate(title="T", column_id=col_id),
        )

        service.patch_task(
            board_a.id, task.id,
            TaskPatch(expected_version=task.version_id, title="updated by B"),
        )
        with pytest.raises(HTTPException) as exc:
            service.patch_task(
                board_a.id, task.id,
                TaskPatch(expected_version=1, title="updated by A"),
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["error"] == "stale_version"

    def test_patch_move_column_updates_sort_order(self, db_session, board_a, user_a):
        service = BoardService(db_session)
        cols = service.list_columns(board_a.id)
        col_a_id = str(cols[0].id)
        col_b_id = str(cols[1].id)

        task = service.create_task(
            board_a.id, user_a,
            TaskCreate(title="T", column_id=col_a_id),
        )
        original_sort = task.sort_order
        moved, _meta = service.patch_task(
            board_a.id, task.id,
            TaskPatch(expected_version=task.version_id, column_id=col_b_id),
        )
        assert str(moved.column_id) == col_b_id
        assert moved.sort_order == 0.0
        assert moved.sort_order != original_sort or original_sort == 0.0


# --------------------------------------------------------------------------- #
# Sort rebalance
# --------------------------------------------------------------------------- #
class TestRebalance:
    def test_rebalance_column_renumbers_monotonically(
        self, db_session, board_a, user_a
    ):
        service = BoardService(db_session)
        cols = service.list_columns(board_a.id)
        col_id = str(cols[0].id)

        t1 = service.create_task(board_a.id, user_a, TaskCreate(title="1", column_id=col_id))
        t2 = service.create_task(board_a.id, user_a, TaskCreate(title="2", column_id=col_id))
        t3 = service.create_task(board_a.id, user_a, TaskCreate(title="3", column_id=col_id))
        service.patch_task(
            board_a.id, t3.id,
            TaskPatch(expected_version=t3.version_id, sort_order=(t1.sort_order + t2.sort_order) / 2.0),
        )

        moved = service.rebalance_column(board_a.id, col_id)
        assert moved >= 1
        tasks = service.list_tasks(board_a.id, column_id=col_id)
        sort_orders = [t.sort_order for t in tasks]
        assert sort_orders == sorted(sort_orders)
        assert sort_orders == [0.0, 1.0, 2.0]


# --------------------------------------------------------------------------- #
# Canvas workspace lifecycle
# --------------------------------------------------------------------------- #
class TestTaskWorkspace:
    def test_task_create_with_workspace_true_creates_canvas(self, db_session, board_a, default_tenant, user_a):
        service = BoardService(db_session)
        cols = service.list_columns(board_a.id)
        col_id = str(cols[0].id)

        task = service.create_task(
            board_a.id, user_a,
            TaskCreate(title="Code refactor", column_id=col_id, workspace=True),
            tenant_id=default_tenant,
        )
        assert task.canvas_id is not None
        canvas = db_session.query(Canvas).filter(Canvas.id == str(task.canvas_id)).first()
        assert canvas is not None
        assert canvas.canvas_type == "kanban"
        assert canvas.name == "Task: Code refactor"

    def test_task_create_without_workspace_has_null_canvas(self, db_session, board_a, user_a):
        service = BoardService(db_session)
        cols = service.list_columns(board_a.id)
        col_id = str(cols[0].id)

        task = service.create_task(
            board_a.id, user_a,
            TaskCreate(title="Plain task", column_id=col_id, workspace=False),
        )
        assert task.canvas_id is None

    def test_patch_workspace_true_idempotently_creates_canvas(
        self, db_session, board_a, default_tenant, user_a
    ):
        service = BoardService(db_session)
        cols = service.list_columns(board_a.id)
        col_id = str(cols[0].id)

        task = service.create_task(
            board_a.id, user_a,
            TaskCreate(title="T", column_id=col_id, workspace=False),
        )
        assert task.canvas_id is None

        updated, _meta = service.patch_task(
            board_a.id, task.id,
            TaskPatch(expected_version=task.version_id, workspace=True),
            tenant_id=default_tenant,
        )
        assert updated.canvas_id is not None

        updated_again, _meta2 = service.patch_task(
            board_a.id, task.id,
            TaskPatch(expected_version=updated.version_id, workspace=True),
            tenant_id=default_tenant,
        )
        assert updated_again.canvas_id == updated.canvas_id

    def test_completing_task_archives_canvas(self, db_session, board_a, default_tenant, user_a):
        service = BoardService(db_session)
        cols = service.list_columns(board_a.id)
        col_id = str(cols[0].id)

        task = service.create_task(
            board_a.id, user_a,
            TaskCreate(
                title="T",
                column_id=col_id,
                status=BoardStatus.IN_PROGRESS,
                workspace=True,
            ),
            tenant_id=default_tenant,
        )
        canvas_id = task.canvas_id
        assert canvas_id is not None

        in_review, _meta1 = service.patch_task(
            board_a.id, task.id,
            TaskPatch(expected_version=task.version_id, status=BoardStatus.IN_REVIEW),
        )
        done, _meta2 = service.patch_task(
            board_a.id, task.id,
            TaskPatch(expected_version=in_review.version_id, status=BoardStatus.DONE),
        )
        assert done.status == BoardStatus.DONE

        canvas = db_session.query(Canvas).filter(Canvas.id == str(canvas_id)).first()
        assert canvas is not None
        assert canvas.status == "archived"
