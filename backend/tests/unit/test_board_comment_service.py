"""Tests for core.board_comment_service + core.board_command_router (Phase 3)."""
from __future__ import annotations

import uuid
from typing import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.schemas.board_schemas import BoardCreate
from core.board_comment_service import BoardCommentService, task_conversation_id
from core.board_command_router import BoardCommandRouter, parse_slash
from core.board_service import BoardService
from core.database import Base
from core.models import AgentMessage, Artifact, ArtifactComment, Canvas, Tenant, User, Workspace
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
def task_with_canvas(db_session, populated):
    service = BoardService(db_session)
    cols = service.list_columns(populated["board_id"])
    todo = next(c for c in cols if c.name == "To Do")
    ws = Workspace(
        tenant_id=populated["tenant_id"],
        name="WS",
    )
    db_session.add(ws)
    db_session.flush()
    canvas = Canvas(
        tenant_id=populated["tenant_id"],
        workspace_id=ws.id,
        created_by=populated["user_id"],
        name="Task: X",
        canvas_type="kanban",
    )
    db_session.add(canvas)
    db_session.flush()
    task = BoardTask(
        board_id=populated["board_id"],
        column_id=todo.id,
        title="Sample",
        status="todo",
        sort_order=0.0,
        canvas_id=canvas.id,
    )
    db_session.add(task)
    db_session.flush()
    db_session.add(Artifact(
        tenant_id=populated["tenant_id"],
        workspace_id=ws.id,
        canvas_id=canvas.id,
        name="out.md",
        type="markdown",
        content="hello",
    ))
    db_session.commit()
    return {"task_id": str(task.id), "canvas_id": str(canvas.id)}


# --------------------------------------------------------------------------- #
# Task-level comments
# --------------------------------------------------------------------------- #
class TestTaskComments:
    def test_create_and_list_comment(self, db_session, populated):
        svc = BoardCommentService(db_session)
        service = BoardService(db_session)
        cols = service.list_columns(populated["board_id"])
        col_id = str(cols[0].id)
        task = service.create_task(
            populated["board_id"], populated["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="T", column_id=col_id,
            ),
        )

        msg = svc.create_comment(
            populated["board_id"], str(task.id),
            author_user_id=populated["user_id"], content="hello world",
        )
        assert msg.content == "hello world"
        assert str(msg.from_user_id) == populated["user_id"]
        assert msg.from_agent_id is None
        assert msg.conversation_id == task_conversation_id(str(task.id))

        listed = svc.list_comments(
            populated["board_id"], str(task.id),
        )
        assert len(listed) == 1
        assert listed[0].content == "hello world"

    def test_create_reply_builds_threaded_tree_in_O_N(self, db_session, populated):
        svc = BoardCommentService(db_session)
        service = BoardService(db_session)
        cols = service.list_columns(populated["board_id"])
        col_id = str(cols[0].id)
        task = service.create_task(
            populated["board_id"], populated["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="T", column_id=col_id,
            ),
        )

        parent = svc.create_comment(
            populated["board_id"], str(task.id),
            author_user_id=populated["user_id"], content="parent",
        )
        reply1 = svc.create_comment(
            populated["board_id"], str(task.id),
            author_user_id=populated["user_id"], content="reply1",
            parent_message_id=str(parent.id),
        )
        svc.create_comment(
            populated["board_id"], str(task.id),
            author_user_id=populated["user_id"], content="reply2",
            parent_message_id=str(parent.id),
        )
        svc.create_comment(
            populated["board_id"], str(task.id),
            author_user_id=populated["user_id"], content="reply1.sub",
            parent_message_id=str(reply1.id),
        )

        flat = svc.list_comments(populated["board_id"], str(task.id))
        tree = svc.build_thread_tree(flat)

        assert len(tree) == 1
        root = tree[0]
        assert root["content"] == "parent"
        assert len(root["replies"]) == 2
        r1 = next(r for r in root["replies"] if r["content"] == "reply1")
        assert len(r1["replies"]) == 1
        assert r1["replies"][0]["content"] == "reply1.sub"

    def test_only_author_can_patch_their_comment(self, db_session, populated):
        svc = BoardCommentService(db_session)
        service = BoardService(db_session)
        cols = service.list_columns(populated["board_id"])
        task = service.create_task(
            populated["board_id"], populated["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="T", column_id=str(cols[0].id),
            ),
        )
        msg = svc.create_comment(
            populated["board_id"], str(task.id),
            author_user_id=populated["user_id"], content="orig",
        )

        other_uid = str(uuid.uuid4())
        with pytest.raises(HTTPException) as exc:
            svc.patch_comment(
                str(msg.id),
                author_user_id=other_uid, new_content="hack",
            )
        assert exc.value.status_code == 403

        edited = svc.patch_comment(
            str(msg.id),
            author_user_id=populated["user_id"], new_content="fixed",
        )
        assert edited.content == "fixed"

    def test_only_author_can_delete_their_comment(self, db_session, populated):
        svc = BoardCommentService(db_session)
        service = BoardService(db_session)
        cols = service.list_columns(populated["board_id"])
        task = service.create_task(
            populated["board_id"], populated["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="T", column_id=str(cols[0].id),
            ),
        )
        msg = svc.create_comment(
            populated["board_id"], str(task.id),
            author_user_id=populated["user_id"], content="orig",
        )

        with pytest.raises(HTTPException) as exc:
            svc.delete_comment(
                str(msg.id),
                author_user_id=str(uuid.uuid4()),
            )
        assert exc.value.status_code == 403

        svc.delete_comment(
            str(msg.id),
            author_user_id=populated["user_id"],
        )
        listed = svc.list_comments(
            populated["board_id"], str(task.id),
        )
        assert listed == []

    def test_author_invariant_exactly_one_of_user_or_agent(self, db_session, populated):
        svc = BoardCommentService(db_session)
        service = BoardService(db_session)
        cols = service.list_columns(populated["board_id"])
        task = service.create_task(
            populated["board_id"], populated["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="T", column_id=str(cols[0].id),
            ),
        )
        with pytest.raises(HTTPException) as exc:
            svc.create_comment(
                populated["board_id"], str(task.id),
                author_user_id=populated["user_id"],
                author_agent_id=str(uuid.uuid4()),
                content="x",
            )
        assert exc.value.status_code == 422

        with pytest.raises(HTTPException) as exc:
            svc.create_comment(
                populated["board_id"], str(task.id),
                author_user_id=None, author_agent_id=None, content="x",
            )
        assert exc.value.status_code == 422


# --------------------------------------------------------------------------- #
# Artifact-level comments
# --------------------------------------------------------------------------- #
class TestArtifactCommentAggregation:
    def test_artifact_comments_returned_for_task_with_canvas(
        self, db_session, populated, task_with_canvas
    ):
        svc = BoardCommentService(db_session)
        artifact = db_session.query(Artifact).first()
        ac = ArtifactComment(
            tenant_id=populated["tenant_id"],
            artifact_id=artifact.id,
            user_id=populated["user_id"],
            content="typo in line 3",
        )
        db_session.add(ac)
        db_session.commit()

        rows = svc.list_artifact_comments_for_task(
            populated["board_id"], task_with_canvas["task_id"],
        )
        assert len(rows) == 1
        assert rows[0]["content"] == "typo in line 3"
        assert rows[0]["canvas_id"] == task_with_canvas["canvas_id"]
        assert rows[0]["artifact_id"] == str(artifact.id)

    def test_artifact_comments_empty_when_task_has_no_canvas(self, db_session, populated):
        svc = BoardCommentService(db_session)
        service = BoardService(db_session)
        cols = service.list_columns(populated["board_id"])
        task = service.create_task(
            populated["board_id"], populated["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="No workspace", column_id=str(cols[0].id), workspace=False,
            ),
        )
        rows = svc.list_artifact_comments_for_task(
            populated["board_id"], str(task.id),
        )
        assert rows == []


# --------------------------------------------------------------------------- #
# Slash parsing
# --------------------------------------------------------------------------- #
class TestSlashParser:
    def test_parse_create(self):
        result = parse_slash("/task create Buy milk")
        assert result is not None
        action, params = result
        assert action == "board_create"
        assert params["title"] == "Buy milk"

    def test_parse_create_with_column(self):
        result = parse_slash("/task create Buy milk in To Do")
        assert result is not None
        action, params = result
        assert action == "board_create"
        assert "To Do" in params["column"]

    def test_parse_move(self):
        result = parse_slash("/task move T-123 to in_progress")
        assert result is not None
        action, params = result
        assert action == "board_move"
        assert params["task_id"] == "T-123"
        assert params["target"] == "in_progress"

    def test_parse_assign(self):
        result = parse_slash("/task assign T-1 to alice")
        assert result is not None
        action, params = result
        assert action == "board_assign"
        assert params["task_id"] == "T-1"
        assert params["assignee"] == "alice"

    def test_parse_comment(self):
        result = parse_slash("/task comment T-1 please review")
        assert result is not None
        action, params = result
        assert action == "board_comment"
        assert params["task_id"] == "T-1"
        assert params["content"] == "please review"

    def test_parse_list_no_filter(self):
        result = parse_slash("/task list")
        assert result is not None
        action, _ = result
        assert action == "board_list"

    def test_parse_list_with_status(self):
        result = parse_slash("/task list done")
        assert result is not None
        action, params = result
        assert action == "board_list"
        assert params["status"] == "done"

    def test_parse_decompose(self):
        result = parse_slash("/task decompose T-42")
        assert result is not None
        action, params = result
        assert action == "board_decompose"
        assert params["task_id"] == "T-42"

    def test_parse_non_command_returns_none(self):
        assert parse_slash("hello world") is None
        assert parse_slash("/run Finance do something") is None
        assert parse_slash("") is None

    def test_parse_case_insensitive(self):
        result = parse_slash("/TASK MOVE abc TO Done")
        assert result is not None
        action, _ = result
        assert action == "board_move"


# --------------------------------------------------------------------------- #
# BoardCommandRouter behavior
# --------------------------------------------------------------------------- #
class TestCommandRouterBehavior:
    def _router(self, db_session, populated):
        return BoardCommandRouter(db_session), populated

    def test_unknown_command_returns_friendly_reply(self, db_session, populated):
        router, ctx = self._router(db_session, populated)
        reply = router.route(
            action_type="board_nonsense",
            parameters={},
            user_id=ctx["user_id"],
            board_id=ctx["board_id"],
        )
        assert reply.ok is False
        assert "Unknown" in reply.reply

    def test_unknown_task_returns_friendly_reply_not_500(self, db_session, populated):
        router, ctx = self._router(db_session, populated)
        reply = router.route(
            action_type="board_move",
            parameters={"task_id": str(uuid.uuid4()), "target": "done"},
            user_id=ctx["user_id"],
            board_id=ctx["board_id"],
        )
        assert reply.ok is False
        assert "Couldn't find" in reply.reply

    def test_move_via_command_uses_state_machine(self, db_session, populated):
        router, ctx = self._router(db_session, populated)
        service = BoardService(db_session)
        cols = service.list_columns(ctx["board_id"])
        task = service.create_task(
            ctx["board_id"], ctx["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="T", column_id=str(cols[0].id), status="todo",
            ),
        )

        reply = router.route(
            action_type="board_move",
            parameters={"task_id": str(task.id), "target": "done"},
            user_id=ctx["user_id"],
            board_id=ctx["board_id"],
        )
        assert reply.ok is False
        assert "Can't move" in reply.reply
        assert reply.extra.get("allowed_next") is not None

    def test_legal_move_succeeds(self, db_session, populated):
        router, ctx = self._router(db_session, populated)
        service = BoardService(db_session)
        cols = service.list_columns(ctx["board_id"])
        task = service.create_task(
            ctx["board_id"], ctx["user_id"],
            __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                title="T", column_id=str(cols[0].id), status="todo",
            ),
        )
        reply = router.route(
            action_type="board_move",
            parameters={"task_id": str(task.id), "target": "in_progress"},
            user_id=ctx["user_id"],
            board_id=ctx["board_id"],
        )
        assert reply.ok is True
        assert "Moved" in reply.reply

    def test_create_via_command(self, db_session, populated):
        router, ctx = self._router(db_session, populated)
        reply = router.route(
            action_type="board_create",
            parameters={"title": "New from chat", "column": "Backlog"},
            user_id=ctx["user_id"],
            board_id=ctx["board_id"],
        )
        assert reply.ok is True
        assert reply.task_id is not None

    def test_list_via_command_returns_bullets(self, db_session, populated):
        router, ctx = self._router(db_session, populated)
        service = BoardService(db_session)
        cols = service.list_columns(ctx["board_id"])
        for i in range(3):
            service.create_task(
                ctx["board_id"], ctx["user_id"],
                __import__("api.schemas.board_schemas", fromlist=["TaskCreate"]).TaskCreate(
                    title=f"T{i}", column_id=str(cols[0].id),
                ),
            )

        reply = router.route(
            action_type="board_list",
            parameters={},
            user_id=ctx["user_id"],
            board_id=ctx["board_id"],
        )
        assert reply.ok is True
        assert reply.reply.count("•") == 3

    def test_decompose_stub_returns_phase4_message(self, db_session, populated):
        router, ctx = self._router(db_session, populated)
        reply = router.route(
            action_type="board_decompose",
            parameters={"task_id": "T-1"},
            user_id=ctx["user_id"],
            board_id=ctx["board_id"],
        )
        assert reply.ok is False
        assert "Phase 4" in reply.reply
