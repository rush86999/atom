"""Tests for core.board_dispatcher.BoardDispatcher (Phase 2).

Single-Tenant version.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.models
from core.board_dispatcher import BoardDispatcher
from core.board_state_machine import BoardStatus
from core.database import Base
from core.models import AgentCanvasPresence, Canvas, Tenant, User
from core.models_board import Board, BoardColumn, BoardTask

# Import BoardService for fixture setup only.
from api.schemas.board_schemas import BoardCreate, TaskCreate
from core.board_service import BoardService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    tables_for_board_tests = [
        "tenants", "users", "workspaces", "boards", "board_columns", "board_tasks",
        "canvases", "canvas_audit", "agent_canvas_presence", "artifacts", "agent_registry",
    ]
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables[n] for n in tables_for_board_tests if n in Base.metadata.tables],
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def populated_board(db_session):
    tid = "default-tenant"
    uid = str(uuid.uuid4())
    db_session.add(Tenant(id=tid, name="T", subdomain="t-default"))
    db_session.add(User(
        id=uid,
        tenant_id=tid,
        email=f"u-{uid[:8]}@x.com",
        first_name="First",
        last_name="Last",
        hashed_password="hashed_password",
        role="admin",
        status="active",
    ))
    db_session.commit()

    service = BoardService(db_session)
    board = service.create_board(owner_user_id=uid, payload=BoardCreate(name="B"))
    cols = service.list_columns(board.id)
    todo_col = next(c for c in cols if c.name == "To Do")

    agent_id = str(uuid.uuid4())
    from core.models import AgentRegistry
    db_session.add(AgentRegistry(
        id=agent_id,
        name="Test Agent",
        category="Operations",
        role="agent",
        type="personal",
        capabilities=[],
        module_path="test_module",
        class_name="TestClass",
        workspace_id="default",
        tenant_id=tid,
        status="autonomous",
    ))
    task = BoardTask(
        board_id=board.id, column_id=todo_col.id,
        title="Dispatch me", status=BoardStatus.TODO,
        assignee_agent_id=agent_id,
        sort_order=0.0,
    )
    db_session.add(task)
    db_session.commit()

    return {
        "tenant_id": tid,
        "user_id": uid,
        "board_id": str(board.id),
        "todo_column_id": str(todo_col.id),
        "task_id": str(task.id),
        "agent_id": agent_id,
    }


# --------------------------------------------------------------------------- #
# Claim
# --------------------------------------------------------------------------- #
class TestClaimReadyTasks:
    def test_claim_returns_todo_tasks_with_agent_assignee(self, db_session, populated_board):
        dispatcher = BoardDispatcher(session_factory=lambda: db_session)
        claimed = dispatcher._claim_ready_tasks(db_session)
        assert len(claimed) == 1
        assert str(claimed[0].id) == populated_board["task_id"]

    def test_claim_excludes_tasks_without_agent_assignee(self, db_session, populated_board):
        db_session.add(BoardTask(
            board_id=populated_board["board_id"],
            column_id=populated_board["todo_column_id"],
            title="No agent", status=BoardStatus.TODO,
            assignee_agent_id=None,
            sort_order=1.0,
        ))
        db_session.commit()

        dispatcher = BoardDispatcher(session_factory=lambda: db_session)
        claimed = dispatcher._claim_ready_tasks(db_session)
        assert len(claimed) == 1
        assert str(claimed[0].id) == populated_board["task_id"]

    def test_claim_excludes_non_todo_statuses(self, db_session, populated_board):
        db_session.add(BoardTask(
            board_id=populated_board["board_id"],
            column_id=populated_board["todo_column_id"],
            title="Already running", status=BoardStatus.IN_PROGRESS,
            assignee_agent_id=populated_board["agent_id"],
            sort_order=1.0,
        ))
        db_session.commit()

        dispatcher = BoardDispatcher(session_factory=lambda: db_session)
        claimed = dispatcher._claim_ready_tasks(db_session)
        assert all(c.status == BoardStatus.TODO for c in claimed)
        assert len(claimed) == 1


# --------------------------------------------------------------------------- #
# Dispatch (single task lifecycle)
# --------------------------------------------------------------------------- #
class TestDispatchOne:
    def test_dispatch_transitions_todo_to_in_progress(self, db_session, populated_board):
        dispatcher = BoardDispatcher(session_factory=lambda: db_session)
        task = db_session.query(BoardTask).filter(BoardTask.id == populated_board["task_id"]).first()

        dispatcher._dispatch_one(db_session, task)

        db_session.refresh(task)
        assert task.status == BoardStatus.IN_PROGRESS

    def test_dispatch_without_canvas_does_not_create_presence(
        self, db_session, populated_board
    ):
        dispatcher = BoardDispatcher(session_factory=lambda: db_session)
        task = db_session.query(BoardTask).filter(BoardTask.id == populated_board["task_id"]).first()
        assert task.canvas_id is None

        dispatcher._dispatch_one(db_session, task)

        presences = db_session.query(AgentCanvasPresence).all()
        assert presences == []

    def test_dispatch_with_canvas_creates_active_presence_row(
        self, db_session, populated_board
    ):
        dispatcher = BoardDispatcher(session_factory=lambda: db_session)
        task = db_session.query(BoardTask).filter(BoardTask.id == populated_board["task_id"]).first()
        canvas = Canvas(
            tenant_id=populated_board["tenant_id"],
            created_by=populated_board["user_id"],
            name="Task: " + task.title,
            canvas_type="kanban",
        )
        db_session.add(canvas)
        db_session.flush()
        task.canvas_id = canvas.id
        db_session.commit()

        dispatcher._dispatch_one(db_session, task)

        print("DEBUG - All Canvases:", db_session.query(Canvas).all())
        print("DEBUG - All Agent Presences:", db_session.query(AgentCanvasPresence).all())
        print("DEBUG - Task Canvas ID:", task.canvas_id, type(task.canvas_id))

        presence = (
            db_session.query(AgentCanvasPresence)
            .filter(
                AgentCanvasPresence.agent_id == str(task.assignee_agent_id),
                AgentCanvasPresence.canvas_id == str(canvas.id),
                AgentCanvasPresence.status == "active",
            )
            .first()
        )
        assert presence is not None
        assert presence.role == "contributor"
        assert "Working on:" in (presence.current_action or "")

    def test_dispatch_with_canvas_is_idempotent(self, db_session, populated_board):
        dispatcher = BoardDispatcher(session_factory=lambda: db_session)
        task = db_session.query(BoardTask).filter(BoardTask.id == populated_board["task_id"]).first()
        canvas = Canvas(
            tenant_id=populated_board["tenant_id"],
            created_by=populated_board["user_id"],
            name="Task: " + task.title,
            canvas_type="kanban",
        )
        db_session.add(canvas)
        db_session.flush()
        task.canvas_id = canvas.id
        db_session.commit()

        dispatcher._join_canvas(db_session, task)
        dispatcher._join_canvas(db_session, task)

        count = (
            db_session.query(AgentCanvasPresence)
            .filter(
                AgentCanvasPresence.agent_id == str(task.assignee_agent_id),
                AgentCanvasPresence.canvas_id == str(canvas.id),
                AgentCanvasPresence.status == "active",
            )
            .count()
        )
        assert count == 1


# --------------------------------------------------------------------------- #
# Stale reap
# --------------------------------------------------------------------------- #
class TestStalePresenceReap:
    def test_reap_marks_old_active_presence_as_left(self, db_session, populated_board):
        dispatcher = BoardDispatcher(session_factory=lambda: db_session)

        stale_joined = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.add(AgentCanvasPresence(
            agent_id=populated_board["agent_id"],
            canvas_id="00000000-0000-0000-0000-000000000000",
            tenant_id=populated_board["tenant_id"],
            role="contributor",
            status="active",
            current_action="stale",
            joined_at=stale_joined,
        ))
        db_session.commit()

        dispatcher._reap_stale(db_session)

        reap = db_session.query(AgentCanvasPresence).filter(
            AgentCanvasPresence.current_action == "stale"
        ).first()
        assert reap.status == "left"
        assert reap.left_at is not None

    def test_reap_leaves_recent_active_presence_alone(self, db_session, populated_board):
        dispatcher = BoardDispatcher(session_factory=lambda: db_session)

        recent_joined = datetime.now(timezone.utc) - timedelta(seconds=30)
        db_session.add(AgentCanvasPresence(
            agent_id=populated_board["agent_id"],
            canvas_id="00000000-0000-0000-0000-000000000000",
            tenant_id=populated_board["tenant_id"],
            role="contributor",
            status="active",
            current_action="recent",
            joined_at=recent_joined,
        ))
        db_session.commit()

        dispatcher._reap_stale(db_session)

        recent = db_session.query(AgentCanvasPresence).filter(
            AgentCanvasPresence.current_action == "recent"
        ).first()
        assert recent.status == "active"
        assert recent.left_at is None


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
class TestDispatcherLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self):
        d = BoardDispatcher(tick_interval_seconds=100)
        try:
            await d.start()
            first_task = d._task
            await d.start()
            assert d._task is first_task
        finally:
            await d.stop()
        assert d._task is None
