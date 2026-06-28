"""Tests for core.board_decomposer.BoardDecomposer (Phase 4)."""
from __future__ import annotations

import os
import sys
import uuid
from typing import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.schemas.board_schemas import BoardCreate, TaskCreate
from core.board_decomposer import (
    MAX_ROOT_DEPTH,
    BoardDecomposer,
    DecompositionResult,
    SubtaskProposal,
)
from core.board_service import BoardService
from core.database import Base
from core.models import Canvas, Tenant, User, Workspace
from core.models_board import BoardTask


@pytest.fixture
def db_session() -> Iterator:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    tables_for_board_tests = [
        "tenants", "users", "workspaces", "boards", "board_columns", "board_tasks",
        "canvases", "canvas_audit", "agent_canvas_presence", "artifacts",
        "agent_messages", "artifact_comments", "agent_registry",
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
def populated(db_session):
    tid = "default-tenant"
    uid = str(uuid.uuid4())
    db_session.add(Tenant(id=tid, name="T", subdomain="t-default"))
    db_session.add(User(id=uid, tenant_id=tid, email=f"u-{uid[:8]}@x.com", first_name="A", last_name="B", hashed_password="pw", role="admin", status="active"))
    db_session.commit()
    board = BoardService(db_session).create_board(
        owner_user_id=uid, payload=BoardCreate(name="B"),
    )
    return {"tenant_id": tid, "user_id": uid, "board_id": str(board.id)}


@pytest.fixture
def parent_task(db_session, populated):
    service = BoardService(db_session)
    cols = service.list_columns(populated["board_id"])
    backlog = next(c for c in cols if c.name == "Backlog")
    task = service.create_task(
        populated["board_id"], populated["user_id"],
        TaskCreate(title="Build feature X", column_id=str(backlog.id), description="A big task"),
    )
    return str(task.id)


# --------------------------------------------------------------------------- #
# Fake handlers
# --------------------------------------------------------------------------- #
class _FakeHandlerWithKey:
    clients = {"openrouter": object()}

    def __init__(self, payload: DecompositionResult):
        self._payload = payload

    async def generate_structured_response(self, **kwargs):
        return self._payload


class _FakeHandlerNoKey:
    clients = {}

    async def generate_structured_response(self, **kwargs):
        raise AssertionError("Should not be called when clients is empty")


class _FakeHandlerMalformed:
    clients = {"openrouter": object()}

    async def generate_structured_response(self, **kwargs):
        return {"rationale": "x", "subtasks": [{"title": "", "bogus_field": True}]}


class _FakeHandlerRaises:
    clients = {"openrouter": object()}

    async def generate_structured_response(self, **kwargs):
        raise RuntimeError("LLM provider timed out")


# --------------------------------------------------------------------------- #
# Propose
# --------------------------------------------------------------------------- #
class TestPropose:
    @pytest.mark.asyncio
    async def test_propose_returns_subtasks_when_handler_has_key(
        self, db_session, populated, parent_task
    ):
        proposals = [
            SubtaskProposal(title="Write tests", column_name="To Do", priority="high"),
            SubtaskProposal(title="Implement core", column_name="To Do"),
            SubtaskProposal(title="Update docs", column_name="Done"),
        ]
        result_obj = DecompositionResult(
            rationale="split by concern", subtasks=proposals,
        )
        handler = _FakeHandlerWithKey(result_obj)

        decomposer = BoardDecomposer(db_session)
        result = await decomposer.propose(
            populated["board_id"], parent_task, handler,
        )

        assert len(result.subtasks) == 3
        assert result.rationale == "split by concern"
        assert result.subtasks[0].title == "Write tests"

    @pytest.mark.asyncio
    async def test_propose_no_byok_key_returns_424(
        self, db_session, populated, parent_task
    ):
        handler = _FakeHandlerNoKey()
        decomposer = BoardDecomposer(db_session)
        with pytest.raises(HTTPException) as exc:
            await decomposer.propose(
                populated["board_id"], parent_task, handler,
            )
        assert exc.value.status_code == 424
        assert exc.value.detail["error"] == "no_byok_key"
        assert exc.value.headers["X-Setup-Hint"] == "byok-required"

    @pytest.mark.asyncio
    async def test_propose_malformed_llm_json_returns_502(
        self, db_session, populated, parent_task
    ):
        handler = _FakeHandlerMalformed()
        decomposer = BoardDecomposer(db_session)
        with pytest.raises(HTTPException) as exc:
            await decomposer.propose(
                populated["board_id"], parent_task, handler,
            )
        assert exc.value.status_code == 502
        assert exc.value.detail["error"] == "decompose_llm_malformed"

    @pytest.mark.asyncio
    async def test_propose_llm_call_exception_returns_502(
        self, db_session, populated, parent_task
    ):
        handler = _FakeHandlerRaises()
        decomposer = BoardDecomposer(db_session)
        with pytest.raises(HTTPException) as exc:
            await decomposer.propose(
                populated["board_id"], parent_task, handler,
            )
        assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_propose_caps_at_8_subtasks(
        self, db_session, populated, parent_task
    ):
        too_many = [SubtaskProposal(title=f"ST{i}") for i in range(15)]
        handler = _FakeHandlerWithKey(DecompositionResult(subtasks=too_many))

        decomposer = BoardDecomposer(db_session)
        result = await decomposer.propose(
            populated["board_id"], parent_task, handler,
        )
        assert len(result.subtasks) == 8

    @pytest.mark.asyncio
    async def test_propose_empty_proposals_rejected(
        self, db_session, populated, parent_task
    ):
        handler = _FakeHandlerWithKey(DecompositionResult(subtasks=[]))
        decomposer = BoardDecomposer(db_session)
        with pytest.raises(HTTPException) as exc:
            await decomposer.propose(
                populated["board_id"], parent_task, handler,
            )
        assert exc.value.status_code == 502
        assert exc.value.detail["error"] == "decompose_empty"


# --------------------------------------------------------------------------- #
# Depth cap
# --------------------------------------------------------------------------- #
class TestDepthCap:
    def _build_chain(self, db_session, populated, depth):
        service = BoardService(db_session)
        cols = service.list_columns(populated["board_id"])
        backlog = next(c for c in cols if c.name == "Backlog")

        root = service.create_task(
            populated["board_id"], populated["user_id"],
            TaskCreate(title="root", column_id=str(backlog.id)),
        )
        current_id = str(root.id)
        for i in range(1, depth):
            child = BoardTask(
                board_id=populated["board_id"],
                column_id=backlog.id,
                title=f"depth-{i}",
                status="backlog",
                sort_order=float(i),
                parent_task_id=current_id,
                root_task_id=root.id,
            )
            db_session.add(child)
            db_session.commit()
            current_id = str(child.id)
        return current_id

    @pytest.mark.asyncio
    async def test_decompose_refused_at_depth_cap(self, db_session, populated):
        leaf_id = self._build_chain(db_session, populated, MAX_ROOT_DEPTH)
        handler = _FakeHandlerWithKey(DecompositionResult(subtasks=[SubtaskProposal(title="x")]))

        decomposer = BoardDecomposer(db_session)
        with pytest.raises(HTTPException) as exc:
            await decomposer.propose(
                populated["board_id"], leaf_id, handler,
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "depth_cap_exceeded"
        assert exc.value.detail["current_depth"] == MAX_ROOT_DEPTH

    @pytest.mark.asyncio
    async def test_decompose_allowed_below_cap(self, db_session, populated):
        leaf_id = self._build_chain(db_session, populated, MAX_ROOT_DEPTH - 1)
        handler = _FakeHandlerWithKey(DecompositionResult(subtasks=[SubtaskProposal(title="x")]))

        decomposer = BoardDecomposer(db_session)
        result = await decomposer.propose(
            populated["board_id"], leaf_id, handler,
        )
        assert len(result.subtasks) == 1


# --------------------------------------------------------------------------- #
# Commit
# --------------------------------------------------------------------------- #
class TestCommit:
    def test_commit_creates_subtasks_atomically(
        self, db_session, populated, parent_task
    ):
        decomposer = BoardDecomposer(db_session)
        proposals = [
            SubtaskProposal(title="A", column_name="To Do"),
            SubtaskProposal(title="B", column_name="Backlog"),
            SubtaskProposal(title="C", column_name="Done"),
        ]
        children = decomposer.commit(
            populated["board_id"], parent_task,
            proposals, created_by_user_id=populated["user_id"],
        )
        assert len(children) == 3

        for c in children:
            assert str(c.parent_task_id) == parent_task
            assert str(c.root_task_id) == parent_task

        service = BoardService(db_session)
        cols = {c.name.lower(): c for c in service.list_columns(populated["board_id"])}
        assert str(children[0].column_id) == str(cols["to do"].id)
        assert str(children[1].column_id) == str(cols["backlog"].id)
        assert str(children[2].column_id) == str(cols["done"].id)

    def test_commit_hallucinated_column_falls_back_to_backlog(
        self, db_session, populated, parent_task
    ):
        decomposer = BoardDecomposer(db_session)
        proposals = [
            SubtaskProposal(title="X", column_name="Nonexistent Column"),
        ]
        children = decomposer.commit(
            populated["board_id"], parent_task,
            proposals, created_by_user_id=populated["user_id"],
        )
        service = BoardService(db_session)
        backlog = next(c for c in service.list_columns(populated["board_id"]) if c.name == "Backlog")
        assert str(children[0].column_id) == str(backlog.id)

    def test_commit_with_spawn_workspaces_creates_canvas_per_subtask(
        self, db_session, populated, parent_task
    ):
        ws = Workspace(
            tenant_id=populated["tenant_id"],
            name="WS",
        )
        db_session.add(ws)
        db_session.commit()

        decomposer = BoardDecomposer(db_session)
        proposals = [
            SubtaskProposal(title="A"),
            SubtaskProposal(title="B"),
        ]
        children = decomposer.commit(
            populated["board_id"], parent_task,
            proposals, created_by_user_id=populated["user_id"],
            spawn_workspaces=True,
        )
        for c in children:
            assert c.canvas_id is not None
            canvas = db_session.query(Canvas).filter(Canvas.id == str(c.canvas_id)).first()
            assert canvas is not None
            assert canvas.canvas_type == "kanban"

    def test_commit_without_spawn_workspaces_leaves_canvas_null(
        self, db_session, populated, parent_task
    ):
        decomposer = BoardDecomposer(db_session)
        proposals = [SubtaskProposal(title="A")]
        children = decomposer.commit(
            populated["board_id"], parent_task,
            proposals, created_by_user_id=populated["user_id"],
            spawn_workspaces=False,
        )
        assert children[0].canvas_id is None

    def test_commit_rollbacks_on_failure(
        self, db_session, populated, parent_task
    ):
        decomposer = BoardDecomposer(db_session)
        proposals = [SubtaskProposal(title="A"), SubtaskProposal(title="B")]

        original_flush = db_session.flush
        call_count = {"n": 0}

        def flaky_flush(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise RuntimeError("synthetic failure")
            return original_flush(*args, **kwargs)

        db_session.flush = flaky_flush
        try:
            with pytest.raises(Exception):
                decomposer.commit(
                    populated["board_id"], parent_task,
                    proposals, created_by_user_id=populated["user_id"],
                )
        finally:
            db_session.flush = original_flush

        rows = db_session.query(BoardTask).filter(BoardTask.parent_task_id == parent_task).all()
        assert rows == []
