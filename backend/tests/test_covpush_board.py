"""Coverage-push + bug-hunt tests for core.board_* modules and AITriggerCoordinator."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.schemas.board_schemas import (
    BoardCreate,
    ColumnCreate,
    TaskCreate,
    TaskPatch,
)
from core.ai_trigger_coordinator import (
    AITriggerCoordinator,
    DataCategory,
    TriggerDecision,
    get_ai_trigger_coordinator,
    on_data_ingested,
)
from core.board_command_router import BoardCommandRouter, parse_slash
from core.board_comment_service import (
    BoardCommentService,
    task_conversation_id,
)
from core.board_decomposer import (
    BoardDecomposer,
    DecompositionResult,
    MAX_ROOT_DEPTH,
    SubtaskProposal,
)
from core.board_dispatcher import BoardDispatcher
from core.board_events import (
    BOARD_TASK_CREATED,
    BOARD_TASK_DELETED,
    BOARD_TASK_MOVED,
    BOARD_TASK_TRANSITIONED,
    BOARD_TASK_UPDATED,
    BOARD_COMMENT_POSTED,
    BoardEventEmitter,
    _attach_constants_to_manager,
    board_channel,
    canvas_channel,
)
from core.board_service import BoardService
from core.board_state_machine import (
    BoardStatus,
    IllegalBoardTransition,
    STATUS_GRAPH,
    allowed_next_statuses,
    assert_transition,
    is_transition_allowed,
)
from core.models import (
    AgentCanvasPresence,
    AgentMessage,
    AgentRegistry,
    Artifact,
    ArtifactComment,
    Canvas,
    CanvasAudit,
    Tenant,
    User,
    UUID as CoreUUID,
    Workspace,
)
from core.models_board import Board, BoardColumn, BoardTask


# The repo UUID type binds strings but converts results to uuid.UUID objects,
# which breaks SQLAlchemy 2.0.51 INSERT..RETURNING sentinel matching on SQLite
# (KeyError on every insert). Normalize results to str for the SQLite test
# environment; Postgres behavior is untouched.
def _uuid_result_as_str(self, value, dialect):
    if value is None:
        return value
    if dialect.name == "postgresql":
        return value
    return str(value)


CoreUUID.process_result_value = _uuid_result_as_str


# The conftest db_session fixture wraps each test in a SAVEPOINT, but services
# commit explicitly, which releases the savepoint and commits the outer
# transaction — data then survives the teardown rollback on the shared
# in-memory engine. Use a module-scoped engine + explicit per-test cleanup
# instead so committed rows never leak between tests.
@pytest.fixture(scope="module")
def board_engine():
    from core.models_registration import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(board_engine):
    from sqlalchemy import inspect as sa_inspect

    from core.models_registration import Base

    SessionLocal = sessionmaker(bind=board_engine)
    session = SessionLocal()
    yield session
    session.close()
    existing = set(sa_inspect(board_engine).get_table_names())
    with board_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in existing:
                conn.execute(table.delete())
        conn.commit()


# --------------------------------------------------------------------------- #
# board_state_machine
# --------------------------------------------------------------------------- #

class TestBoardStateMachine:
    def test_status_constants(self):
        assert BoardStatus.ALL == (
            "backlog", "todo", "in_progress", "in_review", "blocked", "done",
        )
        assert BoardStatus.BACKLOG == "backlog"
        assert BoardStatus.TODO == "todo"
        assert BoardStatus.IN_PROGRESS == "in_progress"
        assert BoardStatus.IN_REVIEW == "in_review"
        assert BoardStatus.BLOCKED == "blocked"
        assert BoardStatus.DONE == "done"

    def test_assert_transition_valid(self):
        for current, allowed in STATUS_GRAPH.items():
            for nxt in allowed:
                assert_transition(current, nxt)
                assert is_transition_allowed(current, nxt) is True

    def test_assert_transition_same_status(self):
        for status in BoardStatus.ALL:
            assert_transition(status, status)
            assert is_transition_allowed(status, status)

    def test_assert_transition_invalid(self):
        with pytest.raises(IllegalBoardTransition) as ei:
            assert_transition(BoardStatus.BACKLOG, BoardStatus.DONE)
        assert ei.value.current == "backlog"
        assert ei.value.requested == "done"
        assert ei.value.allowed_next == frozenset({"todo", "blocked"})
        assert "backlog" in str(ei.value)

    def test_assert_transition_unknown_requested(self):
        with pytest.raises(IllegalBoardTransition):
            assert_transition(BoardStatus.TODO, "nonsense")

    def test_assert_transition_unknown_current(self):
        with pytest.raises(IllegalBoardTransition) as ei:
            assert_transition("nonsense", BoardStatus.TODO)
        assert ei.value.allowed_next == frozenset()

    def test_is_transition_allowed_invalid(self):
        assert is_transition_allowed(BoardStatus.DONE, BoardStatus.BACKLOG) is False

    def test_allowed_next_statuses(self):
        assert allowed_next_statuses(BoardStatus.BACKLOG) == frozenset({"todo", "blocked"})
        assert allowed_next_statuses(BoardStatus.IN_PROGRESS) == frozenset(
            {"in_review", "done", "blocked", "todo"}
        )
        assert allowed_next_statuses("bogus") == frozenset()

    def test_done_only_reopens_to_todo(self):
        assert allowed_next_statuses(BoardStatus.DONE) == frozenset({"todo"})


# --------------------------------------------------------------------------- #
# board_events
# --------------------------------------------------------------------------- #

class _FakeTask:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class TestBoardEvents:
    def test_channels(self):
        assert board_channel("b1") == "board:b1"
        assert canvas_channel("c1") == "canvas:c1"

    def test_attach_constants_idempotent(self):
        from core.websockets import ConnectionManager

        _attach_constants_to_manager()
        for name in (
            "BOARD_TASK_CREATED",
            "BOARD_TASK_MOVED",
            "BOARD_TASK_TRANSITIONED",
            "BOARD_TASK_UPDATED",
            "BOARD_TASK_DELETED",
            "BOARD_COMMENT_POSTED",
        ):
            assert hasattr(ConnectionManager, name)
        _attach_constants_to_manager()
        assert ConnectionManager.BOARD_TASK_CREATED == "board:task:created"

    def test_task_summary_orm(self):
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c1", title="T", status="todo",
            sort_order=0, version_id=3, canvas_id="cv1",
        )
        summary = BoardEventEmitter._task_summary(task)
        assert summary == {
            "id": "t1", "board_id": "b1", "column_id": "c1", "title": "T",
            "status": "todo", "sort_order": 0.0, "version_id": 3, "canvas_id": "cv1",
        }

    def test_task_summary_orm_no_canvas(self):
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c1", title="T", status="todo",
            sort_order=None, version_id=1, canvas_id=None,
        )
        summary = BoardEventEmitter._task_summary(task)
        assert summary["sort_order"] == 0.0
        assert summary["canvas_id"] is None

    def test_task_summary_dict(self):
        task = {
            "id": "t1", "board_id": "b1", "column_id": "c1", "title": "T",
            "status": "todo", "sort_order": 2.5, "version_id": 1, "canvas_id": None,
        }
        summary = BoardEventEmitter._task_summary(task)
        assert summary["sort_order"] == 2.5
        assert summary["canvas_id"] is None

    @pytest.mark.asyncio
    async def test_emit_task_created(self):
        mgr = MagicMock()
        mgr.broadcast_event = AsyncMock()
        emitter = BoardEventEmitter(manager=mgr)
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c1", title="T", status="todo",
            sort_order=0.0, version_id=1, canvas_id="cv1",
        )
        await emitter.emit_task_created(task)
        assert mgr.broadcast_event.await_count == 2
        mgr.broadcast_event.assert_any_await("board:b1", BOARD_TASK_CREATED, {"task": emitter._task_summary(task)})
        mgr.broadcast_event.assert_any_await("canvas:cv1", BOARD_TASK_CREATED, {"task": emitter._task_summary(task)})

    @pytest.mark.asyncio
    async def test_emit_task_moved(self):
        mgr = MagicMock()
        mgr.broadcast_event = AsyncMock()
        emitter = BoardEventEmitter(manager=mgr)
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c2", title="T", status="todo",
            sort_order=1.0, version_id=1, canvas_id=None,
        )
        await emitter.emit_task_moved(task, "c1", "c2")
        assert mgr.broadcast_event.await_count == 1
        _, event_type, payload = mgr.broadcast_event.await_args.args
        assert event_type == BOARD_TASK_MOVED
        assert payload["from_column_id"] == "c1"
        assert payload["to_column_id"] == "c2"

    @pytest.mark.asyncio
    async def test_emit_task_transitioned(self):
        mgr = MagicMock()
        mgr.broadcast_event = AsyncMock()
        emitter = BoardEventEmitter(manager=mgr)
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c1", title="T", status="done",
            sort_order=0.0, version_id=2, canvas_id="cv1",
        )
        await emitter.emit_task_transitioned(task, "todo", "done")
        assert mgr.broadcast_event.await_count == 2
        assert all(
            call.args[1] == BOARD_TASK_TRANSITIONED
            for call in mgr.broadcast_event.await_args_list
        )
        payload = mgr.broadcast_event.await_args_list[0].args[2]
        assert payload["from_status"] == "todo"
        assert payload["to_status"] == "done"

    @pytest.mark.asyncio
    async def test_emit_task_updated(self):
        mgr = MagicMock()
        mgr.broadcast_event = AsyncMock()
        emitter = BoardEventEmitter(manager=mgr)
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c1", title="T2", status="todo",
            sort_order=0.0, version_id=4, canvas_id=None,
        )
        await emitter.emit_task_updated(task)
        assert mgr.broadcast_event.await_count == 1
        mgr.broadcast_event.assert_any_await("board:b1", BOARD_TASK_UPDATED, {"task": emitter._task_summary(task)})

    @pytest.mark.asyncio
    async def test_emit_task_deleted(self):
        mgr = MagicMock()
        mgr.broadcast_event = AsyncMock()
        emitter = BoardEventEmitter(manager=mgr)
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c1", title="T", status="todo",
            sort_order=0.0, version_id=1, canvas_id=None,
        )
        await emitter.emit_task_deleted(task)
        mgr.broadcast_event.assert_any_await(
            "board:b1", BOARD_TASK_DELETED, {"task_id": "t1", "board_id": "b1"}
        )

    @pytest.mark.asyncio
    async def test_emit_comment_posted(self):
        mgr = MagicMock()
        mgr.broadcast_event = AsyncMock()
        emitter = BoardEventEmitter(manager=mgr)
        task = _FakeTask(
            id="t1", board_id="b1", column_id="c1", title="T", status="todo",
            sort_order=0.0, version_id=1, canvas_id="cv1",
        )
        await emitter.emit_comment_posted(task, "m1", {"content": "hi"})
        assert mgr.broadcast_event.await_count == 2
        payload = mgr.broadcast_event.await_args_list[0].args[2]
        assert payload["task_id"] == "t1"
        assert payload["comment_id"] == "m1"


# --------------------------------------------------------------------------- #
# board_comment_service
# --------------------------------------------------------------------------- #

class TestBoardCommentService:
    def _board_and_task(self, db, title="Task A"):
        board = BoardService(db).create_board(None, BoardCreate(name="B", seed_default_columns=True))
        col = db.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        task = BoardService(db).create_task(
            board.id, None, TaskCreate(title=title, column_id=str(col.id))
        )
        return board, task

    def test_task_conversation_id(self):
        assert task_conversation_id("abc") == "board_task:abc"

    def test_create_comment_user(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        user = User(
            id="u1", email="alice@example.com", first_name="Alice", last_name="Smith",
            role="admin", status="active",
        )
        db_session.add(user)
        db_session.commit()
        msg = svc.create_comment(str(board.id), str(task.id), "u1", "hello")
        assert msg.conversation_id == f"board_task:{task.id}"
        assert msg.message_type == "board_comment"
        assert msg.from_user_id == "u1"
        assert msg.tenant_id == "default"

    def test_create_comment_agent(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        msg = svc.create_comment(
            str(board.id), str(task.id), None, "from agent", author_agent_id="ag1"
        )
        assert msg.from_agent_id == "ag1"
        assert msg.from_user_id is None

    def test_create_comment_both_identities_rejected(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.create_comment(str(board.id), str(task.id), "u1", "x", author_agent_id="ag1")
        assert ei.value.status_code == 422

    def test_create_comment_no_identity_rejected(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.create_comment(str(board.id), str(task.id), None, "x")
        assert ei.value.status_code == 422

    def test_create_comment_task_not_found(self, db_session):
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.create_comment("b1", "nope", "u1", "x")
        assert ei.value.status_code == 404

    def test_create_comment_wrong_board_scoped(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.create_comment("other-board", str(task.id), "u1", "x")
        assert ei.value.status_code == 404

    def test_create_reply(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        parent = svc.create_comment(str(board.id), str(task.id), None, "parent", author_agent_id="ag1")
        reply = svc.create_comment(
            str(board.id), str(task.id), None, "reply", parent_message_id=str(parent.id),
            author_agent_id="ag1",
        )
        assert reply.parent_message_id == str(parent.id)

    def test_create_reply_parent_missing(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.create_comment(
                str(board.id), str(task.id), None, "reply",
                parent_message_id="ghost", author_agent_id="ag1",
            )
        assert ei.value.status_code == 404

    def test_list_comments_and_before_id(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        c1 = svc.create_comment(str(board.id), str(task.id), None, "first", author_agent_id="ag1")
        c2 = svc.create_comment(str(board.id), str(task.id), None, "second", author_agent_id="ag1")
        c3 = svc.create_comment(str(board.id), str(task.id), None, "third", author_agent_id="ag1")
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i, msg in enumerate((c1, c2, c3)):
            msg.created_at = base + timedelta(seconds=i)
        db_session.commit()
        rows = svc.list_comments(str(board.id), str(task.id))
        assert [r.content for r in rows] == ["first", "second", "third"]
        before_c3 = svc.list_comments(str(board.id), str(task.id), before_id=str(c3.id))
        assert [r.content for r in before_c3] == ["first", "second"]
        before_c1 = svc.list_comments(str(board.id), str(task.id), before_id=str(c1.id))
        assert before_c1 == []
        before_ghost = svc.list_comments(str(board.id), str(task.id), before_id="ghost")
        assert [r.content for r in before_ghost] == ["first", "second", "third"]

    def test_list_comments_limit_clamped(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        for i in range(5):
            svc.create_comment(str(board.id), str(task.id), None, f"c{i}", author_agent_id="ag1")
        rows = svc.list_comments(str(board.id), str(task.id), limit=2)
        assert len(rows) == 2
        rows = svc.list_comments(str(board.id), str(task.id), limit=10000)
        assert len(rows) == 5

    def test_list_comments_task_missing(self, db_session):
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.list_comments("b1", "nope")
        assert ei.value.status_code == 404

    def test_resolve_author_display_user(self, db_session):
        db_session.add(
            User(
                id="u1", email="alice@example.com", first_name="Alice", last_name="",
                role="admin", status="active",
            )
        )
        db_session.commit()
        msg = AgentMessage(
            tenant_id="default", from_user_id="u1", message_type="board_comment",
            content="x", status="delivered",
        )
        svc = BoardCommentService(db_session)
        user_id, agent_id, display = svc._resolve_author_display(msg)
        assert user_id == "u1"
        assert agent_id is None
        assert display == "Alice"

    def test_resolve_author_display_user_email_fallback(self, db_session):
        msg = AgentMessage(
            tenant_id="default", from_user_id="ghost", message_type="board_comment",
            content="x", status="delivered",
        )
        svc = BoardCommentService(db_session)
        user_id, agent_id, display = svc._resolve_author_display(msg)
        assert display is None

    def test_resolve_author_display_agent(self, db_session):
        msg = AgentMessage(
            tenant_id="default", from_agent_id="ag1", message_type="board_comment",
            content="x", status="delivered",
        )
        svc = BoardCommentService(db_session)
        user_id, agent_id, display = svc._resolve_author_display(msg)
        assert user_id is None
        assert agent_id == "ag1"
        assert display == "Agent"

    def test_serialize(self, db_session):
        msg = AgentMessage(
            tenant_id="default", from_agent_id="ag1", message_type="board_comment",
            content="hello", status="delivered", task_id="t1", conversation_id="board_task:t1",
        )
        db_session.add(msg)
        db_session.flush()
        out = BoardCommentService(db_session)._serialize(msg)
        assert out["id"] == str(msg.id)
        assert out["task_id"] == "t1"
        assert out["content"] == "hello"
        assert out["author"] == {"user_id": None, "agent_id": "ag1", "display_name": "Agent"}
        assert out["parent_message_id"] is None

    def test_build_thread_tree(self, db_session):
        parent = AgentMessage(
            tenant_id="default", from_agent_id="ag1", message_type="board_comment",
            content="p", status="delivered",
        )
        db_session.add(parent)
        db_session.flush()
        child = AgentMessage(
            tenant_id="default", from_agent_id="ag1", message_type="board_comment",
            content="c", status="delivered", parent_message_id=str(parent.id),
        )
        db_session.add(child)
        db_session.flush()
        orphan = AgentMessage(
            tenant_id="default", from_agent_id="ag1", message_type="board_comment",
            content="o", status="delivered", parent_message_id="missing",
        )
        db_session.add(orphan)
        db_session.flush()
        roots = BoardCommentService(db_session).build_thread_tree([parent, child, orphan])
        assert len(roots) == 2
        by_id = {r["id"]: r for r in roots}
        assert len(by_id[str(parent.id)]["replies"]) == 1
        assert by_id[str(parent.id)]["replies"][0]["content"] == "c"

    def test_patch_comment(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        db_session.add(
            User(id="u1", email="a@x.com", first_name="A", last_name="", role="admin", status="active")
        )
        db_session.commit()
        msg = svc.create_comment(str(board.id), str(task.id), "u1", "orig")
        updated = svc.patch_comment(str(msg.id), "u1", "edited")
        assert updated.content == "edited"

    def test_patch_comment_missing(self, db_session):
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.patch_comment("ghost", "u1", "x")
        assert ei.value.status_code == 404

    def test_patch_comment_not_author(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        msg = svc.create_comment(str(board.id), str(task.id), None, "orig", author_agent_id="ag1")
        with pytest.raises(HTTPException) as ei:
            svc.patch_comment(str(msg.id), "u1", "hijack")
        assert ei.value.status_code == 403

    def test_delete_comment(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        db_session.add(
            User(id="u1", email="a@x.com", first_name="A", last_name="", role="admin", status="active")
        )
        db_session.commit()
        msg = svc.create_comment(str(board.id), str(task.id), "u1", "bye")
        svc.delete_comment(str(msg.id), "u1")
        assert db_session.query(AgentMessage).filter(AgentMessage.id == str(msg.id)).first() is None

    def test_delete_comment_missing(self, db_session):
        svc = BoardCommentService(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.delete_comment("ghost", "u1")
        assert ei.value.status_code == 404

    def test_delete_comment_forbidden(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        msg = svc.create_comment(str(board.id), str(task.id), None, "x", author_agent_id="ag1")
        with pytest.raises(HTTPException) as ei:
            svc.delete_comment(str(msg.id), "u1")
        assert ei.value.status_code == 403

    def test_list_artifact_comments_no_canvas(self, db_session):
        board, task = self._board_and_task(db_session)
        svc = BoardCommentService(db_session)
        assert svc.list_artifact_comments_for_task(str(board.id), str(task.id)) == []

    def test_list_artifact_comments(self, db_session):
        board, task = self._board_and_task(db_session)
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.add(Workspace(id="w1", tenant_id="t1", name="ws"))
        db_session.commit()
        canvas = Canvas(
            tenant_id="t1", created_by="system", name="ws", canvas_type="kanban",
            is_collaborative=True,
        )
        db_session.add(canvas)
        db_session.flush()
        task.canvas_id = canvas.id
        db_session.commit()
        art = Artifact(
            tenant_id="t1", workspace_id="w1", canvas_id=str(canvas.id),
            name="a1", type="doc", content="{}",
        )
        db_session.add(art)
        db_session.flush()
        db_session.add(
            ArtifactComment(
                artifact_id=str(art.id), tenant_id="t1", user_id="u1", content="note"
            )
        )
        db_session.commit()
        svc = BoardCommentService(db_session)
        rows = svc.list_artifact_comments_for_task(str(board.id), str(task.id))
        assert len(rows) == 1
        assert rows[0]["content"] == "note"
        assert rows[0]["canvas_id"] == str(canvas.id)
        assert rows[0]["user_id"] == "u1"


# --------------------------------------------------------------------------- #
# board_service
# --------------------------------------------------------------------------- #

class TestBoardService:
    def _svc(self, db):
        return BoardService(db)

    def _board(self, db, seed=True):
        svc = BoardService(db)
        board = svc.create_board("u1", BoardCreate(name="Board", seed_default_columns=seed))
        return board

    def _task(self, db, board=None, col=None, title="T", **kw):
        svc = BoardService(db)
        board = board or self._board(db)
        col = col or db.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        payload = TaskCreate(title=title, column_id=str(col.id), **kw)
        return svc.create_task(str(board.id), "u1", payload)

    def test_create_board_seeded(self, db_session):
        board = self._board(db_session)
        cols = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).all()
        assert [c.name for c in cols] == ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"]
        assert board.owner_user_id == "u1"

    def test_create_board_no_seed(self, db_session):
        board = self._board(db_session, seed=False)
        assert db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).count() == 0

    def test_list_boards(self, db_session):
        svc = BoardService(db_session)
        b1 = self._board(db_session)
        b2 = self._board(db_session)
        assert {b.id for b in svc.list_boards()} == {b1.id, b2.id}
        assert len(svc.list_boards(owner_user_id="u1")) == 2
        assert svc.list_boards(owner_user_id="other") == []
        b2.archived_at = datetime.now(timezone.utc)
        db_session.commit()
        assert [b.id for b in svc.list_boards()] == [b1.id]
        assert len(svc.list_boards(include_archived=True)) == 2

    def test_get_board(self, db_session):
        board = self._board(db_session)
        assert self._svc(db_session).get_board(str(board.id)).id == board.id

    def test_get_board_missing(self, db_session):
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).get_board("nope")
        assert ei.value.status_code == 404

    def test_create_column(self, db_session):
        board = self._board(db_session, seed=False)
        col = self._svc(db_session).create_column(str(board.id), ColumnCreate(name="New", position=0, wip_limit=3))
        assert col.name == "New"
        assert col.wip_limit == 3

    def test_create_column_missing_board(self, db_session):
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).create_column("nope", ColumnCreate(name="X"))
        assert ei.value.status_code == 404

    def test_list_columns(self, db_session):
        board = self._board(db_session)
        cols = self._svc(db_session).list_columns(str(board.id))
        assert [c.position for c in cols] == [0, 1, 2, 3, 4, 5]

    def test_create_task_sort_order_appends(self, db_session):
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        svc = self._svc(db_session)
        t1 = svc.create_task(str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id)))
        t2 = svc.create_task(str(board.id), "u1", TaskCreate(title="B", column_id=str(col.id)))
        assert t1.sort_order == 0.0
        assert t2.sort_order == 1.0

    def test_create_task_bad_status(self, db_session):
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).create_task(
                str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id), status="bogus")
            )
        assert ei.value.status_code == 422

    def test_create_task_bad_column(self, db_session):
        board = self._board(db_session)
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).create_task(
                str(board.id), "u1", TaskCreate(title="A", column_id="nope")
            )
        assert ei.value.status_code == 404

    def test_create_task_with_parent_resolves_root(self, db_session):
        svc = self._svc(db_session)
        board = self._board(db_session)
        parent = self._task(db_session, board=board, title="Parent")
        child = self._task(db_session, board=board, title="Child", parent_task_id=str(parent.id))
        assert child.root_task_id == str(parent.id)
        grand = self._task(db_session, board=board, title="Grand", parent_task_id=str(child.id))
        assert grand.root_task_id == str(parent.id)

    def test_create_task_workspace_requires_tenant(self, db_session):
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).create_task(
                str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id), workspace=True)
            )
        assert ei.value.status_code == 400

    def test_create_task_with_workspace(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        task = self._svc(db_session).create_task(
            str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id), workspace=True),
            tenant_id="t1",
        )
        assert task.canvas_id is not None
        canvas = db_session.query(Canvas).filter(Canvas.id == str(task.canvas_id)).first()
        assert canvas is not None
        assert canvas.canvas_type == "kanban"
        audit = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == str(canvas.id))
            .all()
        )
        assert audit

    def test_patch_task_stale_version(self, db_session):
        task = self._task(db_session)
        svc = self._svc(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.patch_task(str(task.board_id), str(task.id), TaskPatch(expected_version=999))
        assert ei.value.status_code == 409
        assert ei.value.detail["error"] == "stale_version"

    def test_patch_task_illegal_transition(self, db_session):
        task = self._task(db_session)  # backlog
        svc = self._svc(db_session)
        with pytest.raises(HTTPException) as ei:
            svc.patch_task(
                str(task.board_id), str(task.id),
                TaskPatch(expected_version=1, status="done"),
            )
        assert ei.value.status_code == 422
        assert ei.value.detail["error"] == "illegal_transition"
        assert "allowed_next" in ei.value.detail

    def test_patch_task_scalars(self, db_session):
        task = self._task(db_session, title="Old")
        svc = self._svc(db_session)
        updated, meta = svc.patch_task(
            str(task.board_id), str(task.id),
            TaskPatch(
                expected_version=1,
                title="New title with padding" * 100,
                description="d",
                priority="high",
                assignee_user_id="u9",
                assignee_agent_id="ag9",
                due_at=datetime.now(timezone.utc),
                labels=["x"],
                metadata_json={"k": "v"},
                sort_order=4.5,
            ),
        )
        assert updated.title[:500] == ("New title with padding" * 100)[:500]
        assert updated.priority == "high"
        assert updated.assignee_user_id == "u9"
        assert updated.assignee_agent_id == "ag9"
        assert updated.labels == ["x"]
        assert updated.metadata_json == {"k": "v"}
        assert updated.sort_order == 4.5
        assert "title" in meta["fields"]
        assert "sort_order" in meta["fields"]
        assert meta["from_column_id"] is None

    def test_patch_task_legal_transition(self, db_session):
        task = self._task(db_session)
        svc = self._svc(db_session)
        updated, meta = svc.patch_task(
            str(task.board_id), str(task.id),
            TaskPatch(expected_version=1, status="todo"),
        )
        assert updated.status == "todo"
        assert meta["from_status"] == "backlog"
        assert meta["to_status"] == "todo"

    def test_patch_task_move_column(self, db_session):
        board = self._board(db_session)
        col1, col2 = (
            db_session.query(BoardColumn)
            .filter(BoardColumn.board_id == board.id)
            .order_by(BoardColumn.position)
            .all()
        )[:2]
        svc = self._svc(db_session)
        task = svc.create_task(str(board.id), "u1", TaskCreate(title="A", column_id=str(col1.id)))
        updated, meta = svc.patch_task(
            str(board.id), str(task.id),
            TaskPatch(expected_version=1, column_id=str(col2.id)),
        )
        assert updated.column_id == col2.id
        assert meta["from_column_id"] == str(col1.id)
        assert meta["to_column_id"] == str(col2.id)
        assert updated.sort_order == 0.0

    def test_patch_task_move_column_with_sort(self, db_session):
        board = self._board(db_session)
        col1, col2 = (
            db_session.query(BoardColumn)
            .filter(BoardColumn.board_id == board.id)
            .order_by(BoardColumn.position)
            .all()
        )[:2]
        svc = self._svc(db_session)
        task = svc.create_task(str(board.id), "u1", TaskCreate(title="A", column_id=str(col1.id)))
        updated, _ = svc.patch_task(
            str(board.id), str(task.id),
            TaskPatch(expected_version=1, column_id=str(col2.id), sort_order=7.5),
        )
        assert updated.sort_order == 7.5

    def test_patch_task_bad_target_column(self, db_session):
        task = self._task(db_session)
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).patch_task(
                str(task.board_id), str(task.id),
                TaskPatch(expected_version=1, column_id="nope"),
            )
        assert ei.value.status_code == 404

    def test_patch_task_archive_canvas_on_done(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        svc = self._svc(db_session)
        task = svc.create_task(
            str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id)), tenant_id="t1"
        )
        svc.patch_task(str(board.id), str(task.id), TaskPatch(expected_version=1, workspace=True), tenant_id="t1")
        db_session.refresh(task)
        svc.patch_task(str(board.id), str(task.id), TaskPatch(expected_version=task.version_id, status="todo"))
        db_session.refresh(task)
        svc.patch_task(str(board.id), str(task.id), TaskPatch(expected_version=task.version_id, status="in_progress"))
        db_session.refresh(task)
        svc.patch_task(str(board.id), str(task.id), TaskPatch(expected_version=task.version_id, status="done"))
        db_session.refresh(task)
        canvas = db_session.query(Canvas).filter(Canvas.id == str(task.canvas_id)).first()
        assert canvas.status == "archived"

    def test_patch_task_workspace_via_patch(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        task = self._task(db_session)
        svc = self._svc(db_session)
        updated, meta = svc.patch_task(
            str(task.board_id), str(task.id),
            TaskPatch(expected_version=1, workspace=True), tenant_id="t1",
        )
        assert updated.canvas_id is not None
        assert "canvas_id" in meta["fields"]

    def test_patch_task_workspace_no_tenant(self, db_session):
        task = self._task(db_session)
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).patch_task(
                str(task.board_id), str(task.id), TaskPatch(expected_version=1, workspace=True)
            )
        assert ei.value.status_code == 400

    def test_patch_task_flush_conflict_409(self, db_session, monkeypatch):
        task = self._task(db_session)
        svc = self._svc(db_session)
        from sqlalchemy.orm.exc import StaleDataError

        calls = {"n": 0}

        def boom(*a, **k):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise StaleDataError("stale")

        monkeypatch.setattr(svc.db, "flush", boom)
        with pytest.raises(HTTPException) as ei:
            svc.patch_task(
                str(task.board_id), str(task.id),
                TaskPatch(expected_version=1, title="x"),
            )
        assert ei.value.status_code == 409
        assert ei.value.detail["error"] == "stale_version"

    def test_delete_task_snapshot(self, db_session):
        task = self._task(db_session)
        svc = self._svc(db_session)
        snap = svc.delete_task(str(task.board_id), str(task.id))
        assert snap["id"] == str(task.id)
        assert snap["board_id"] == str(task.board_id)
        assert snap["status"] == "backlog"
        assert snap["version_id"] == 1
        assert db_session.query(BoardTask).filter(BoardTask.id == str(task.id)).first() is None

    def test_delete_task_missing(self, db_session):
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).delete_task("b1", "nope")
        assert ei.value.status_code == 404

    def test_list_tasks_filter(self, db_session):
        board = self._board(db_session)
        col1, col2 = (
            db_session.query(BoardColumn)
            .filter(BoardColumn.board_id == board.id)
            .order_by(BoardColumn.position)
            .all()
        )[:2]
        svc = self._svc(db_session)
        svc.create_task(str(board.id), "u1", TaskCreate(title="A", column_id=str(col1.id)))
        svc.create_task(str(board.id), "u1", TaskCreate(title="B", column_id=str(col2.id)))
        assert len(svc.list_tasks(str(board.id))) == 2
        assert [t.title for t in svc.list_tasks(str(board.id), column_id=str(col1.id))] == ["A"]

    def test_rebalance_column_all(self, db_session):
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        svc = self._svc(db_session)
        t1 = svc.create_task(str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id)))
        t2 = svc.create_task(str(board.id), "u1", TaskCreate(title="B", column_id=str(col.id)))
        svc.patch_task(str(board.id), str(t1.id), TaskPatch(expected_version=1, sort_order=10.0))
        moved = svc.rebalance_column(str(board.id), None)
        db_session.refresh(t1)
        db_session.refresh(t2)
        assert moved == 2
        assert t1.sort_order == 1.0
        assert t2.sort_order == 0.0

    def test_rebalance_single_column(self, db_session):
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        svc = self._svc(db_session)
        svc.create_task(str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id)))
        assert svc.rebalance_column(str(board.id), str(col.id)) == 0

    def test_rebalance_missing_board(self, db_session):
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).rebalance_column("nope", None)
        assert ei.value.status_code == 404

    def test_rebalance_missing_column(self, db_session):
        board = self._board(db_session)
        with pytest.raises(HTTPException) as ei:
            self._svc(db_session).rebalance_column(str(board.id), "nope")
        assert ei.value.status_code == 404

    def test_next_sort_order(self, db_session):
        board = self._board(db_session)
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        svc = self._svc(db_session)
        assert svc._next_sort_order(str(col.id)) == 0.0
        svc.create_task(str(board.id), "u1", TaskCreate(title="A", column_id=str(col.id)))
        assert svc._next_sort_order(str(col.id)) == 1.0

    def test_create_task_workspace_existing(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        task = self._task(db_session)
        svc = self._svc(db_session)
        c1 = svc.create_task_workspace(task, "t1")
        c2 = svc.create_task_workspace(task, "t1")
        assert c1.id == c2.id
        assert db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == str(c1.id)).count() == 1

    def test_lookup_workspace_id(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.add(Workspace(id="w1", tenant_id="t1", name="ws"))
        db_session.commit()
        svc = self._svc(db_session)
        assert svc._lookup_workspace_id("t1") == "w1"
        assert svc._lookup_workspace_id("missing") is None

    def test_archive_task_canvas(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        canvas = Canvas(tenant_id="t1", created_by="system", name="ws", canvas_type="kanban")
        db_session.add(canvas)
        db_session.flush()
        task = self._task(db_session)
        task.canvas_id = canvas.id
        svc = self._svc(db_session)
        svc._archive_task_canvas(task)
        db_session.commit()
        assert db_session.query(Canvas).filter(Canvas.id == str(canvas.id)).first().status == "archived"

    def test_archive_task_canvas_no_canvas(self, db_session):
        task = self._task(db_session)
        self._svc(db_session)._archive_task_canvas(task)

    def test_archive_task_canvas_already_archived(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        canvas = Canvas(
            tenant_id="t1", created_by="system", name="ws", canvas_type="kanban", status="archived"
        )
        db_session.add(canvas)
        db_session.flush()
        task = self._task(db_session)
        task.canvas_id = canvas.id
        self._svc(db_session)._archive_task_canvas(task)
        db_session.commit()
        assert db_session.query(Canvas).filter(Canvas.id == str(canvas.id)).first().status == "archived"

    def test_create_task_workspace_created_by_user(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        task = self._task(db_session)
        svc = self._svc(db_session)
        c = svc.create_task_workspace(task, "t1")
        assert c.created_by == "u1"


# --------------------------------------------------------------------------- #
# board_decomposer
# --------------------------------------------------------------------------- #

class TestBoardDecomposer:
    def _board_task(self, db):
        board = BoardService(db).create_board(None, BoardCreate(name="B", seed_default_columns=True))
        col = db.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        task = BoardService(db).create_task(
            str(board.id), None, TaskCreate(title="Parent", column_id=str(col.id))
        )
        return board, task

    @staticmethod
    def _handler(subtask_payload=None):
        handler = MagicMock()
        handler.clients = {"openai": "key"}
        if subtask_payload is not None:
            handler.generate_structured_response = AsyncMock(
                return_value=DecompositionResult(
                    rationale="r", subtasks=[SubtaskProposal(**subtask_payload)]
                )
            )
        return handler

    def test_subtask_proposal_validation(self):
        with pytest.raises(Exception):
            SubtaskProposal(title="")
        p = SubtaskProposal(title="Ship it", description=None, column_name="To Do")
        assert p.priority == "normal"
        assert p.estimated_hours is None

    def test_decomposition_result_defaults(self):
        r = DecompositionResult(subtasks=[])
        assert r.rationale == ""

    def test_root_depth_chain(self, db_session):
        decomposer = BoardDecomposer(db_session)
        board, task = self._board_task(db_session)
        svc = BoardService(db_session)
        child = svc.create_task(
            str(board.id), None, TaskCreate(title="c", column_id=str(task.column_id),
                                            parent_task_id=str(task.id))
        )
        db_session.refresh(child)
        assert decomposer._root_depth(task) == 1
        assert decomposer._root_depth(child) == 2

    def test_check_depth_raises(self, db_session):
        decomposer = BoardDecomposer(db_session)
        board, task = self._board_task(db_session)
        svc = BoardService(db_session)
        c1 = svc.create_task(
            str(board.id), None, TaskCreate(title="c1", column_id=str(task.column_id),
                                            parent_task_id=str(task.id))
        )
        c2 = svc.create_task(
            str(board.id), None, TaskCreate(title="c2", column_id=str(task.column_id),
                                            parent_task_id=str(c1.id))
        )
        with pytest.raises(HTTPException) as ei:
            decomposer._check_depth(c2)
        assert ei.value.status_code == 422
        assert ei.value.detail["error"] == "depth_cap_exceeded"

    def test_check_depth_root_ok(self, db_session):
        board, task = self._board_task(db_session)
        BoardDecomposer(db_session)._check_depth(task)

    def test_check_byok_no_clients(self, db_session):
        handler = MagicMock()
        handler.clients = {}
        with pytest.raises(HTTPException) as ei:
            BoardDecomposer._check_byok(handler)
        assert ei.value.status_code == 424
        assert ei.value.detail["error"] == "no_byok_key"

    def test_check_byok_missing_attr(self, db_session):
        handler = MagicMock()
        del handler.clients
        with pytest.raises(HTTPException) as ei:
            BoardDecomposer._check_byok(handler)
        assert ei.value.status_code == 424

    def test_check_byok_ok(self, db_session):
        BoardDecomposer._check_byok(self._handler())

    def test_build_prompt(self, db_session):
        board, task = self._board_task(db_session)
        prompt = BoardDecomposer._build_prompt(task, "CANVAS: (none)")
        assert "TASK TITLE: Parent" in prompt
        assert "CANVAS: (none)" in prompt

    def test_canvas_artifact_summary_none(self, db_session):
        board, task = self._board_task(db_session)
        assert BoardDecomposer(db_session)._canvas_artifact_summary(task) == "CANVAS: (none)"

    def test_canvas_artifact_summary_no_artifacts(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        canvas = Canvas(tenant_id="t1", created_by="system", name="ws", canvas_type="kanban")
        db_session.add(canvas)
        db_session.flush()
        board, task = self._board_task(db_session)
        task.canvas_id = canvas.id
        db_session.commit()
        assert BoardDecomposer(db_session)._canvas_artifact_summary(task) == (
            "CANVAS: present, no artifacts yet"
        )

    def test_canvas_artifact_summary_with_artifacts(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.add(Workspace(id="w1", tenant_id="t1", name="ws"))
        db_session.commit()
        canvas = Canvas(tenant_id="t1", created_by="system", name="ws", canvas_type="kanban")
        db_session.add(canvas)
        db_session.flush()
        db_session.add(
            Artifact(tenant_id="t1", workspace_id="w1", canvas_id=str(canvas.id),
                     name="spec.md", type="markdown", content="x")
        )
        db_session.commit()
        board, task = self._board_task(db_session)
        task.canvas_id = canvas.id
        db_session.commit()
        summary = BoardDecomposer(db_session)._canvas_artifact_summary(task)
        assert "spec.md" in summary

    @pytest.mark.asyncio
    async def test_propose_success(self, db_session):
        board, task = self._board_task(db_session)
        handler = self._handler({"title": "Subtask one"})
        decomposer = BoardDecomposer(db_session)
        result = await decomposer.propose(str(board.id), str(task.id), handler)
        assert result.subtasks[0].title == "Subtask one"

    @pytest.mark.asyncio
    async def test_propose_accepts_dict(self, db_session):
        board, task = self._board_task(db_session)
        handler = MagicMock()
        handler.clients = {"openai": "k"}
        handler.generate_structured_response = AsyncMock(
            return_value={"rationale": "r", "subtasks": [{"title": "T"}]}
        )
        result = await BoardDecomposer(db_session).propose(str(board.id), str(task.id), handler)
        assert result.subtasks[0].title == "T"

    @pytest.mark.asyncio
    async def test_propose_malformed_dict(self, db_session):
        board, task = self._board_task(db_session)
        handler = MagicMock()
        handler.clients = {"openai": "k"}
        handler.generate_structured_response = AsyncMock(
            return_value={"rationale": "r", "subtasks": [{"title": ""}]}
        )
        with pytest.raises(HTTPException) as ei:
            await BoardDecomposer(db_session).propose(str(board.id), str(task.id), handler)
        assert ei.value.status_code == 502
        assert ei.value.detail["error"] == "decompose_llm_malformed"

    @pytest.mark.asyncio
    async def test_propose_llm_raises(self, db_session):
        board, task = self._board_task(db_session)
        handler = MagicMock()
        handler.clients = {"openai": "k"}
        handler.generate_structured_response = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(HTTPException) as ei:
            await BoardDecomposer(db_session).propose(str(board.id), str(task.id), handler)
        assert ei.value.status_code == 502
        assert ei.value.detail["error"] == "decompose_llm_failed"

    @pytest.mark.asyncio
    async def test_propose_none_response(self, db_session):
        board, task = self._board_task(db_session)
        handler = MagicMock()
        handler.clients = {"openai": "k"}
        handler.generate_structured_response = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as ei:
            await BoardDecomposer(db_session).propose(str(board.id), str(task.id), handler)
        assert ei.value.status_code == 502
        assert ei.value.detail["error"] == "decompose_llm_no_response"

    @pytest.mark.asyncio
    async def test_propose_empty_subtasks(self, db_session):
        board, task = self._board_task(db_session)
        handler = MagicMock()
        handler.clients = {"openai": "k"}
        handler.generate_structured_response = AsyncMock(
            return_value=DecompositionResult(rationale="r", subtasks=[])
        )
        with pytest.raises(HTTPException) as ei:
            await BoardDecomposer(db_session).propose(str(board.id), str(task.id), handler)
        assert ei.value.status_code == 502
        assert ei.value.detail["error"] == "decompose_empty"

    @pytest.mark.asyncio
    async def test_propose_truncates_over_8(self, db_session):
        board, task = self._board_task(db_session)
        handler = MagicMock()
        handler.clients = {"openai": "k"}
        handler.generate_structured_response = AsyncMock(
            return_value=DecompositionResult(
                rationale="r",
                subtasks=[SubtaskProposal(title=f"s{i}") for i in range(10)],
            )
        )
        result = await BoardDecomposer(db_session).propose(str(board.id), str(task.id), handler)
        assert len(result.subtasks) == 8

    @pytest.mark.asyncio
    async def test_propose_task_missing(self, db_session):
        handler = self._handler({"title": "T"})
        with pytest.raises(HTTPException) as ei:
            await BoardDecomposer(db_session).propose("b1", "nope", handler)
        assert ei.value.status_code == 404

    @pytest.mark.asyncio
    async def test_propose_no_byok(self, db_session):
        board, task = self._board_task(db_session)
        handler = MagicMock()
        handler.clients = {}
        with pytest.raises(HTTPException) as ei:
            await BoardDecomposer(db_session).propose(str(board.id), str(task.id), handler)
        assert ei.value.status_code == 424

    def test_commit_basic(self, db_session):
        board, task = self._board_task(db_session)
        decomposer = BoardDecomposer(db_session)
        created = decomposer.commit(
            str(board.id), str(task.id),
            [SubtaskProposal(title="s1", column_name="To Do"),
             SubtaskProposal(title="s2", column_name="Nope Column")],
            created_by_user_id=None,
        )
        assert len(created) == 2
        col_todo = db_session.query(BoardColumn).filter(
            BoardColumn.board_id == board.id, BoardColumn.name == "To Do"
        ).first()
        assert created[0].column_id == col_todo.id
        assert created[1].status == "backlog"
        assert created[1].root_task_id == str(task.id)
        assert created[0].sort_order == 0.0

    def test_commit_user_tenant(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.add(
            User(id="u1", email="a@x.com", first_name="A", last_name="", role="admin",
                 status="active", tenant_id="t1")
        )
        db_session.commit()
        board, task = self._board_task(db_session)
        created = BoardDecomposer(db_session).commit(
            str(board.id), str(task.id), [SubtaskProposal(title="s1")], created_by_user_id="u1"
        )
        assert created[0].created_by_user_id == "u1"

    def test_commit_default_tenant_fallback(self, db_session):
        db_session.add(Tenant(id="t2", name="T2", subdomain="t2"))
        db_session.commit()
        board, task = self._board_task(db_session)
        created = BoardDecomposer(db_session).commit(
            str(board.id), str(task.id), [SubtaskProposal(title="s1")], created_by_user_id=None
        )
        assert created[0].id

    def test_commit_spawn_workspaces(self, db_session):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        board, task = self._board_task(db_session)
        created = BoardDecomposer(db_session).commit(
            str(board.id), str(task.id), [SubtaskProposal(title="s1")],
            created_by_user_id=None, spawn_workspaces=True,
        )
        assert created[0].canvas_id is not None

    def test_commit_rolls_back_on_error(self, db_session):
        board, task = self._board_task(db_session)
        db_session.add(
            User(id="u1", email="a@x.com", first_name="A", last_name="", role="admin",
                 status="active", tenant_id="t1")
        )
        db_session.commit()
        decomposer = BoardDecomposer(db_session)
        with patch.object(BoardService, "create_task_workspace", side_effect=RuntimeError("x")):
            with pytest.raises(RuntimeError):
                decomposer.commit(
                    str(board.id), str(task.id), [SubtaskProposal(title="s1")],
                    created_by_user_id="u1", spawn_workspaces=True,
                )
        assert db_session.query(BoardTask).count() == 1

    def test_commit_parent_missing(self, db_session):
        with pytest.raises(HTTPException) as ei:
            BoardDecomposer(db_session).commit("b1", "nope", [], None)
        assert ei.value.status_code == 404

    def test_commit_depth_cap(self, db_session):
        board, task = self._board_task(db_session)
        svc = BoardService(db_session)
        c1 = svc.create_task(
            str(board.id), None, TaskCreate(title="c1", column_id=str(task.column_id),
                                            parent_task_id=str(task.id))
        )
        c2 = svc.create_task(
            str(board.id), None, TaskCreate(title="c2", column_id=str(task.column_id),
                                            parent_task_id=str(c1.id))
        )
        with pytest.raises(HTTPException) as ei:
            BoardDecomposer(db_session).commit(str(board.id), str(c2.id), [SubtaskProposal(title="x")], None)
        assert ei.value.status_code == 422


# --------------------------------------------------------------------------- #
# board_command_router
# --------------------------------------------------------------------------- #

class TestParseSlash:
    def test_parse_create(self):
        assert parse_slash("/task create Build a widget") == (
            "board_create", {"title": "Build a widget", "column": None},
        )

    def test_parse_create_with_column(self):
        action, params = parse_slash("/task create Build in To Do")
        assert action == "board_create"
        assert params["title"] == "Build"
        assert params["column"] == "To Do"

    def test_parse_move(self):
        assert parse_slash("/task move 1234 to done") == (
            "board_move", {"task_id": "1234", "target": "done"},
        )

    def test_parse_assign(self):
        assert parse_slash("/task assign abc to bob") == (
            "board_assign", {"task_id": "abc", "assignee": "bob"},
        )

    def test_parse_comment(self):
        action, params = parse_slash("/task comment abc hello world")
        assert action == "board_comment"
        assert params["task_id"] == "abc"
        assert params["content"] == "hello world"

    def test_parse_list(self):
        assert parse_slash("/task list") == ("board_list", {"status": None})
        assert parse_slash("/task list in_progress") == ("board_list", {"status": "in_progress"})

    def test_parse_decompose(self):
        assert parse_slash("/task decompose abc") == ("board_decompose", {"task_id": "abc"})

    def test_parse_case_insensitive(self):
        assert parse_slash("/TASK MOVE 1 to DONE")[0] == "board_move"

    def test_parse_no_match(self):
        assert parse_slash("hello world") is None
        assert parse_slash("") is None
        assert parse_slash("   ") is None


class TestBoardCommandRouter:
    def _setup(self, db):
        router = BoardCommandRouter(db)
        board = BoardService(db).create_board("u1", BoardCreate(name="B", seed_default_columns=True))
        return router, board

    def _task(self, db, board):
        col = db.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        return BoardService(db).create_task(
            str(board.id), "u1", TaskCreate(title="Task", column_id=str(col.id))
        )

    def test_status_aliases(self):
        router = BoardCommandRouter.__new__(BoardCommandRouter)
        assert router._resolve_status("IN_PROGRESS") == "in_progress"
        assert router._resolve_status(" doing ") == "in_progress"
        assert router._resolve_status("complete") == "done"
        assert router._resolve_status("bogus") is None
        assert router._resolve_status("") is None

    def test_resolve_column_by_name(self, db_session):
        router, board = self._setup(db_session)
        col = router._resolve_column_by_name(str(board.id), "TO DO")
        assert col is not None
        assert router._resolve_column_by_name(str(board.id), "nope") is None

    def test_resolve_task_by_full_uuid(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        resolved = router._resolve_task(str(board.id), str(task.id))
        assert resolved.id == task.id

    def test_resolve_task_short_id(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        short = str(task.id)[-6:]
        resolved = router._resolve_task(str(board.id), short)
        assert resolved.id == task.id

    def test_resolve_task_ambiguous_short_id(self, db_session):
        router, board = self._setup(db_session)
        task1 = self._task(db_session, board)
        task2 = BoardService(db_session).create_task(
            str(board.id), "u1", TaskCreate(title="T2", column_id=str(task1.column_id))
        )
        suffix = str(task1.id)[-4:]
        if str(task2.id).endswith(suffix):
            assert router._resolve_task(str(board.id), suffix) is None
        else:
            resolved = router._resolve_task(str(board.id), suffix)
            assert resolved is not None and resolved.id == task1.id
        assert router._resolve_task(str(board.id), str(task1.id)) is not None
        assert router._resolve_task(None, "not-a-uuid") is None

    def test_route_unknown_action(self, db_session):
        router, _ = self._setup(db_session)
        reply = router.route("bogus_action", {}, "u1")
        assert reply.ok is False
        assert "Unknown board command" in reply.reply

    def test_route_http_exception_wrapped(self, db_session):
        router, _ = self._setup(db_session)
        with patch.object(
            router.board_service, "list_tasks", side_effect=HTTPException(500, "boom")
        ):
            reply = router.route("board_list", {}, "u1", board_id="b1")
        assert reply.ok is False
        assert "boom" in reply.reply

    def test_route_generic_exception_wrapped(self, db_session):
        router, _ = self._setup(db_session)
        with patch.object(
            router.board_service, "list_tasks", side_effect=RuntimeError("bad")
        ):
            reply = router.route("board_list", {}, "u1", board_id="b1")
        assert reply.ok is False
        assert "notified" in reply.reply

    def test_cmd_create(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_create", {"title": "New task"}, "u1", board_id=str(board.id))
        assert reply.ok is True
        assert "Created" in reply.reply
        assert reply.task_id

    def test_cmd_create_missing_title(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_create", {}, "u1", board_id=str(board.id))
        assert reply.ok is False
        assert "Title is required" in reply.reply

    def test_cmd_create_no_board(self, db_session):
        router, _ = self._setup(db_session)
        reply = router.route("board_create", {"title": "x"}, "u1")
        assert reply.ok is False
        assert "No board context" in reply.reply

    def test_cmd_create_unknown_column(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_create", {"title": "x", "column": "Nowhere"}, "u1", board_id=str(board.id))
        assert reply.ok is False
        assert "No column named" in reply.reply
        assert len(reply.extra["available_columns"]) == 6

    def test_cmd_move_success(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        reply = router.route(
            "board_move", {"task_id": str(task.id), "target": "todo"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is True
        assert "Moved" in reply.reply

    def test_cmd_move_missing_params(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_move", {"task_id": "1"}, "u1", board_id=str(board.id))
        assert reply.ok is False
        assert "Usage" in reply.reply

    def test_cmd_move_unknown_status(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        reply = router.route(
            "board_move", {"task_id": str(task.id), "target": "nowhere"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is False
        assert "Unknown status" in reply.reply

    def test_cmd_move_task_missing(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route(
            "board_move", {"task_id": "zzzz", "target": "todo"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is False
        assert "Couldn't find a task" in reply.reply

    def test_cmd_move_already_in_status(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        reply = router.route(
            "board_move", {"task_id": str(task.id), "target": "backlog"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is True
        assert "already" in reply.reply

    def test_cmd_move_illegal_transition(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        reply = router.route(
            "board_move", {"task_id": str(task.id), "target": "done"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is False
        assert "Can't move" in reply.reply
        assert reply.extra["allowed_next"] == ["blocked", "todo"]

    def test_cmd_assign_by_uuid(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        reply = router.route(
            "board_assign", {"task_id": str(task.id), "assignee": "11111111-2222-3333-4444-555555555555"},
            "u1", board_id=str(board.id),
        )
        assert reply.ok is True
        assert "Assigned" in reply.reply

    def test_cmd_assign_by_email(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        db_session.add(
            User(id="u9", email="alice@example.com", first_name="Alice", last_name="",
                 role="admin", status="active")
        )
        db_session.commit()
        reply = router.route(
            "board_assign", {"task_id": str(task.id), "assignee": "alice"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is True
        assert reply.task_id == str(task.id)

    def test_cmd_assign_user_missing(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        reply = router.route(
            "board_assign", {"task_id": str(task.id), "assignee": "nobody"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is False
        assert "Couldn't find user" in reply.reply

    def test_cmd_assign_missing_params(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_assign", {"task_id": "1"}, "u1", board_id=str(board.id))
        assert reply.ok is False

    def test_cmd_assign_task_missing(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route(
            "board_assign", {"task_id": "nope", "assignee": "u1"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is False

    def test_cmd_comment(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        reply = router.route(
            "board_comment", {"task_id": str(task.id), "content": "nice"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is True
        assert reply.extra["comment_id"]

    def test_cmd_comment_missing(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_comment", {"task_id": "1"}, "u1", board_id=str(board.id))
        assert reply.ok is False

    def test_cmd_comment_task_missing(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route(
            "board_comment", {"task_id": "ghost", "content": "x"}, "u1", board_id=str(board.id)
        )
        assert reply.ok is False

    def test_cmd_list(self, db_session):
        router, board = self._setup(db_session)
        self._task(db_session, board)
        reply = router.route("board_list", {}, "u1", board_id=str(board.id))
        assert reply.ok is True
        assert "Task" in reply.reply

    def test_cmd_list_no_board(self, db_session):
        router, _ = self._setup(db_session)
        reply = router.route("board_list", {}, "u1")
        assert reply.ok is False
        assert "No board context" in reply.reply

    def test_cmd_list_unknown_status(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_list", {"status": "bogus"}, "u1", board_id=str(board.id))
        assert reply.ok is False
        assert "Unknown status" in reply.reply

    def test_cmd_list_empty(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_list", {}, "u1", board_id=str(board.id))
        assert reply.ok is True
        assert reply.reply == "No tasks."
        reply2 = router.route("board_list", {"status": "done"}, "u1", board_id=str(board.id))
        assert reply2.reply == "No done tasks."

    def test_cmd_list_filtered(self, db_session):
        router, board = self._setup(db_session)
        task = self._task(db_session, board)
        BoardService(db_session).patch_task(
            str(board.id), str(task.id), TaskPatch(expected_version=1, status="todo")
        )
        reply = router.route("board_list", {"status": "todo"}, "u1", board_id=str(board.id))
        assert reply.ok is True
        assert "Task" in reply.reply

    def test_cmd_list_trailer_over_10(self, db_session):
        router, board = self._setup(db_session)
        for i in range(12):
            self._task(db_session, board)
        reply = router.route("board_list", {}, "u1", board_id=str(board.id))
        assert "…and 2 more" in reply.reply

    def test_cmd_decompose_stub(self, db_session):
        router, board = self._setup(db_session)
        reply = router.route("board_decompose", {"task_id": "1"}, "u1", board_id=str(board.id))
        assert reply.ok is False
        assert "Phase 4" in reply.reply


# --------------------------------------------------------------------------- #
# board_dispatcher
# --------------------------------------------------------------------------- #

@pytest.fixture
def session_factory(board_engine):
    from core.models_registration import Base

    SessionLocal = sessionmaker(bind=board_engine)
    return SessionLocal


class _FakeQueue:
    def __init__(self, client=None):
        self._client = client

    @property
    async def async_client(self):
        return self._client


def _make_patchable_queue():
    return _FakeQueue(None)


class TestBoardDispatcher:
    def test_init_defaults(self):
        d = BoardDispatcher()
        assert d._machine_id.startswith("machine-")
        assert d._tick_interval == BoardDispatcher.TICK_INTERVAL_SECONDS

    def test_init_explicit(self):
        d = BoardDispatcher(tick_interval_seconds=1, machine_id="m1")
        assert d._machine_id == "m1"
        assert d._tick_interval == 1

    @pytest.mark.asyncio
    async def test_start_stop(self, session_factory):
        d = BoardDispatcher(session_factory=session_factory, tick_interval_seconds=1)
        await d.start()
        assert d._task is not None
        await d.start()
        task = d._task
        await d.start()
        assert d._task is task
        await d.stop()
        assert d._task is None

    @pytest.mark.asyncio
    async def test_stop_no_task(self):
        d = BoardDispatcher()
        await d.stop()

    @pytest.mark.asyncio
    async def test_acquire_lock_no_redis(self, session_factory):
        d = BoardDispatcher(session_factory=session_factory)
        with patch("core.board_dispatcher._sync_job_queue", _make_patchable_queue()):
            assert await d._acquire_lock() is True
            await d._release_lock()

    @pytest.mark.asyncio
    async def test_acquire_lock_with_redis(self, session_factory):
        client = AsyncMock()
        client.set = AsyncMock(return_value=True)
        client.get = AsyncMock(return_value="m1")
        client.delete = AsyncMock()
        d = BoardDispatcher(session_factory=session_factory, machine_id="m1")
        with patch("core.board_dispatcher._sync_job_queue", _FakeQueue(client)):
            assert await d._acquire_lock() is True
            client.set.assert_awaited_once()
            await d._release_lock()
            client.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_denied(self, session_factory):
        client = AsyncMock()
        client.set = AsyncMock(return_value=False)
        d = BoardDispatcher(session_factory=session_factory)
        with patch("core.board_dispatcher._sync_job_queue", _FakeQueue(client)):
            assert await d._acquire_lock() is False

    @pytest.mark.asyncio
    async def test_release_lock_other_machine(self, session_factory):
        client = AsyncMock()
        client.get = AsyncMock(return_value="other-machine")
        client.delete = AsyncMock()
        d = BoardDispatcher(session_factory=session_factory, machine_id="m1")
        with patch("core.board_dispatcher._sync_job_queue", _FakeQueue(client)):
            await d._release_lock()
        client.get.assert_awaited_once()
        client.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_acquire_lock_exception(self, session_factory):
        class BoomQueue:
            @property
            async def async_client(self):
                raise RuntimeError("redis down")

        d = BoardDispatcher(session_factory=session_factory)
        with patch("core.board_dispatcher._sync_job_queue", BoomQueue()):
            assert await d._acquire_lock() is True

    def _claim_fixture(self, db, status="todo"):
        board = BoardService(db).create_board(None, BoardCreate(name="B", seed_default_columns=True))
        col = db.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        task = BoardService(db).create_task(
            str(board.id), None,
            TaskCreate(title="T", column_id=str(col.id), status=status,
                       assignee_agent_id="ag1"),
        )
        return board, task

    @staticmethod
    def _allow_governance():
        gov = MagicMock()
        gov.can_perform_action = MagicMock(return_value={"allowed": True})
        return patch("core.agent_governance_service.AgentGovernanceService", return_value=gov)

    def test_claim_ready_tasks(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        claimed = d._claim_ready_tasks(db_session)
        assert [t.id for t in claimed] == [task.id]
        db_session.query(BoardTask).filter(BoardTask.id == str(task.id)).update(
            {"assignee_agent_id": None}
        )
        db_session.commit()
        assert d._claim_ready_tasks(db_session) == []

    def test_claim_ready_tasks_fallback(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        orig_query = db_session.query
        state = {"n": 0}

        def flaky_query(*a, **k):
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("SELECT ... FOR UPDATE skipped due to ... near")
            return orig_query(*a, **k)

        db_session.query = flaky_query
        claimed = d._claim_ready_tasks(db_session)
        assert [t.id for t in claimed] == [task.id]

    def test_claim_ready_tasks_other_error_propagates(self, db_session, session_factory):
        d = BoardDispatcher(session_factory=session_factory)

        def broken(*a, **k):
            raise RuntimeError("totally different")

        db_session.query = broken
        with pytest.raises(RuntimeError):
            d._claim_ready_tasks(db_session)

    def test_governance_allows_agent(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        db_session.add(
            AgentRegistry(id="ag1", name="A", category="Ops", module_path="m", class_name="c",
                          workspace_id="w1")
        )
        db_session.commit()
        d = BoardDispatcher(session_factory=session_factory)
        gov = MagicMock()
        gov.can_perform_action = MagicMock(return_value={"allowed": True})
        with patch(
            "core.agent_governance_service.AgentGovernanceService", return_value=gov
        ) as cls:
            assert d._governance_allows(db_session, task) is True
            cls.assert_called_once()
            args, kwargs = cls.call_args
            assert kwargs["workspace_id"] == "w1"

    def test_governance_allows_denied(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        gov = MagicMock()
        gov.can_perform_action = MagicMock(return_value={"allowed": False})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov):
            assert d._governance_allows(db_session, task) is False

    def test_governance_allows_exception(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        with patch(
            "core.agent_governance_service.AgentGovernanceService",
            side_effect=RuntimeError("gov down"),
        ):
            assert d._governance_allows(db_session, task) is True

    def test_dispatch_one_success(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        with self._allow_governance():
            d._dispatch_one(db_session, task)
        db_session.refresh(task)
        assert task.status == "in_progress"

    def test_dispatch_one_governance_denies(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        gov = MagicMock()
        gov.can_perform_action = MagicMock(return_value={"allowed": False})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov):
            d._dispatch_one(db_session, task)
        assert task.status == "todo"

    def test_dispatch_one_illegal_transition(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session, status="done")
        d = BoardDispatcher(session_factory=session_factory)
        with self._allow_governance():
            d._dispatch_one(db_session, task)
        assert task.status == "done"

    def test_dispatch_one_flush_failure_rolls_back(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        orig_flush = db_session.flush

        def flaky_flush(*a, **k):
            if db_session.dirty or db_session.new or db_session.deleted:
                raise RuntimeError("flush boom")
            return orig_flush(*a, **k)

        db_session.flush = flaky_flush
        with self._allow_governance():
            d._dispatch_one(db_session, task)
        assert task.status == "todo"

    def test_join_canvas_existing(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        canvas = Canvas(tenant_id="t1", created_by="system", name="ws", canvas_type="kanban")
        db_session.add(canvas)
        db_session.flush()
        task.canvas_id = canvas.id
        db_session.add(
            AgentCanvasPresence(
                agent_id="ag1", canvas_id=str(canvas.id), tenant_id="t1",
                role="contributor", status="active", current_action="old",
            )
        )
        db_session.commit()
        d = BoardDispatcher(session_factory=session_factory)
        d._join_canvas(db_session, task)
        p = (
            db_session.query(AgentCanvasPresence)
            .filter(AgentCanvasPresence.agent_id == "ag1")
            .first()
        )
        assert p.current_action.startswith("Working on:")
        assert db_session.query(AgentCanvasPresence).count() == 1

    def test_join_canvas_new_with_canvas(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        canvas = Canvas(tenant_id="t1", created_by="system", name="ws", canvas_type="kanban")
        db_session.add(canvas)
        db_session.flush()
        task.canvas_id = canvas.id
        db_session.commit()
        d = BoardDispatcher(session_factory=session_factory)
        d._join_canvas(db_session, task)
        p = db_session.query(AgentCanvasPresence).first()
        assert p.canvas_id == str(canvas.id)
        assert p.tenant_id == "t1"

    def test_join_canvas_new_tenant_fallback(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        task.canvas_id = "00000000-0000-0000-0000-000000000001"
        db_session.commit()
        d = BoardDispatcher(session_factory=session_factory)
        d._join_canvas(db_session, task)
        p = db_session.query(AgentCanvasPresence).first()
        assert p.tenant_id == "default"

    def test_reap_stale(self, db_session, session_factory):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        canvas = Canvas(tenant_id="t1", created_by="system", name="ws", canvas_type="kanban")
        db_session.add(canvas)
        db_session.flush()
        old = datetime.now(timezone.utc) - timedelta(minutes=20)
        db_session.add(
            AgentCanvasPresence(
                agent_id="ag1", canvas_id=str(canvas.id), tenant_id="t1",
                role="contributor", status="active", joined_at=old,
            )
        )
        fresh = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.add(
            AgentCanvasPresence(
                agent_id="ag2", canvas_id=str(canvas.id), tenant_id="t1",
                role="contributor", status="active", joined_at=fresh,
            )
        )
        db_session.commit()
        d = BoardDispatcher(session_factory=session_factory)
        d._reap_stale(db_session)
        statuses = {
            p.agent_id: p.status for p in db_session.query(AgentCanvasPresence).all()
        }
        assert statuses == {"ag1": "left", "ag2": "active"}

    @pytest.mark.asyncio
    async def test_tick_full_flow(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        d = BoardDispatcher(session_factory=session_factory)
        with patch("core.board_dispatcher._sync_job_queue", _make_patchable_queue()), \
             self._allow_governance():
            await d._tick()
        db_session.refresh(task)
        assert task.status == "in_progress"

    @pytest.mark.asyncio
    async def test_tick_lock_denied_skips(self, db_session, session_factory):
        board, task = self._claim_fixture(db_session)
        client = AsyncMock()
        client.set = AsyncMock(return_value=False)
        d = BoardDispatcher(session_factory=session_factory)
        with patch("core.board_dispatcher._sync_job_queue", _FakeQueue(client)):
            await d._tick()
        assert task.status == "todo"

    @pytest.mark.asyncio
    async def test_tick_dispatch_error_continues(self, db_session, session_factory):
        board, task1 = self._claim_fixture(db_session)
        task2 = BoardService(db_session).create_task(
            str(board.id), None,
            TaskCreate(title="T2", column_id=str(task1.column_id),
                       status="todo", assignee_agent_id="ag2"),
        )
        d = BoardDispatcher(session_factory=session_factory)
        orig = d._dispatch_one

        def flaky(sess, tk):
            if str(tk.id) == str(task1.id):
                raise RuntimeError("dispatch boom")
            return orig(sess, tk)

        d._dispatch_one = flaky
        with patch("core.board_dispatcher._sync_job_queue", _make_patchable_queue()), \
             self._allow_governance():
            await d._tick()
        db_session.refresh(task2)
        assert task2.status == "in_progress"

    @pytest.mark.asyncio
    async def test_run_loop_stops(self, session_factory):
        d = BoardDispatcher(session_factory=session_factory, tick_interval_seconds=0)
        d._tick = AsyncMock()
        await d.start()
        await asyncio.sleep(0.05)
        await d.stop()
        assert d._tick.await_count >= 1


# --------------------------------------------------------------------------- #
# ai_trigger_coordinator
# --------------------------------------------------------------------------- #

class TestAITriggerCoordinator:
    def _coord(self, **kw):
        return AITriggerCoordinator(workspace_id=kw.pop("workspace_id", "ws"), user_id="u1", **kw)

    @pytest.mark.asyncio
    async def test_is_enabled_cached(self):
        coord = self._coord()
        coord._enabled = False
        assert await coord.is_enabled() is False

    @pytest.mark.asyncio
    async def test_is_enabled_from_preference(self):
        coord = self._coord()
        coord._enabled = None
        pref = MagicMock()
        pref.get_preference = MagicMock(return_value=True)
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        with patch("core.database.get_db_session", return_value=cm), patch(
            "core.user_preference_service.UserPreferenceService", return_value=pref
        ):
            assert await coord.is_enabled() is True
            pref.get_preference.assert_called_once_with(
                user_id="u1", workspace_id="ws", key="ai_auto_trigger_enabled", default=True
            )

    @pytest.mark.asyncio
    async def test_is_enabled_pref_not_bool(self):
        coord = self._coord()
        coord._enabled = None
        pref = MagicMock()
        pref.get_preference = MagicMock(return_value="yes")
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        with patch("core.database.get_db_session", return_value=cm), patch(
            "core.user_preference_service.UserPreferenceService", return_value=pref
        ):
            assert await coord.is_enabled() is True

    @pytest.mark.asyncio
    async def test_is_enabled_error_defaults_true(self):
        coord = self._coord()
        coord._enabled = None
        with patch(
            "core.database.get_db_session", side_effect=RuntimeError("db down")
        ):
            assert await coord.is_enabled() is True

    @pytest.mark.asyncio
    async def test_evaluate_data_disabled(self):
        coord = self._coord()
        coord._enabled = False
        result = await coord.evaluate_data({"text": "invoice"}, "doc")
        assert result["decision"] == "no_action"
        assert "disabled" in result["reasoning"]
        assert result["category"] == "general"

    @pytest.mark.asyncio
    async def test_evaluate_data_triggers(self):
        coord = self._coord()
        coord._enabled = True
        with patch.object(coord, "_query_memory_for_insights", new_callable=AsyncMock) as mem, \
             patch.object(coord, "_trigger_agent", new_callable=AsyncMock) as trig:
            mem.return_value = {"experiences": [], "success_count": 0, "failure_count": 0}
            result = await coord.evaluate_data(
                {"text": "invoice payment reconciliation expense budget payroll"}, "webhook"
            )
        assert result["decision"] == "trigger_agent"
        assert result["agent_template"] == "finance_analyst"
        assert result["source"] == "webhook"
        assert result["memory_used"] is False
        trig.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_data_no_agent_template(self):
        coord = self._coord()
        coord._enabled = True
        with patch.object(coord, "_query_memory_for_insights", new_callable=AsyncMock) as mem:
            mem.return_value = {"experiences": [], "success_count": 0, "failure_count": 0}
            result = await coord.evaluate_data(
                {"text": "legal contract compliance nda license"}, "webhook"
            )
        assert result["decision"] == "no_action"
        assert "No agent template" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_evaluate_data_queue_for_review(self):
        coord = self._coord()
        coord._enabled = True
        with patch.object(coord, "_query_memory_for_insights", new_callable=AsyncMock) as mem:
            mem.return_value = {"experiences": [], "success_count": 0, "failure_count": 0}
            result = await coord.evaluate_data({"text": "invoice"}, "webhook")
        assert result["decision"] == "queue_for_review"
        assert result["agent_template"] == "finance_analyst"

    @pytest.mark.asyncio
    async def test_query_memory_for_insights(self):
        coord = self._coord()
        exp_ok = MagicMock(outcome="Success")
        exp_bad = MagicMock(outcome="Failure")
        wm = MagicMock()
        wm.recall_experiences = AsyncMock(
            return_value={"experiences": [exp_ok, exp_bad], "knowledge": [{"k": 1}]}
        )
        with patch("core.agent_world_model.WorldModelService", return_value=wm):
            insights = await coord._query_memory_for_insights("invoice text", DataCategory.FINANCE)
        assert insights["success_count"] == 1
        assert insights["failure_count"] == 1
        assert insights["has_similar_history"] is True

    @pytest.mark.asyncio
    async def test_query_memory_for_insights_error(self):
        coord = self._coord()
        with patch(
            "core.agent_world_model.WorldModelService", side_effect=RuntimeError("no wm")
        ):
            insights = await coord._query_memory_for_insights("x", DataCategory.GENERAL)
        assert insights == {
            "experiences": [], "success_count": 0, "failure_count": 0, "knowledge": [],
        }

    def test_adjust_confidence_boost(self):
        coord = self._coord()
        assert coord._adjust_confidence_with_memory(0.5, {"success_count": 2}) == 0.6
        assert coord._adjust_confidence_with_memory(0.5, {"success_count": 100}) == 0.65

    def test_adjust_confidence_reduction_and_clamp(self):
        coord = self._coord()
        assert coord._adjust_confidence_with_memory(
            0.5, {"success_count": 1, "failure_count": 3}
        ) == pytest.approx(0.45)
        assert coord._adjust_confidence_with_memory(0.95, {"success_count": 5}) == 1.0
        assert coord._adjust_confidence_with_memory(
            0.05, {"success_count": 0, "failure_count": 5}
        ) == pytest.approx(0.0)

    def test_extract_text(self):
        coord = self._coord()
        assert coord._extract_text("plain") == "plain"
        assert coord._extract_text({"content": "body text"}) == "body text"
        assert coord._extract_text({"subject": "subj"}) == "subj"
        assert coord._extract_text({"nested": [1, 2]}) == "{'nested': [1, 2]}"
        assert coord._extract_text({}) == "{}"

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("invoice payment", DataCategory.FINANCE),
            ("new lead pipeline prospect", DataCategory.SALES),
            ("inventory warehouse shipping order", DataCategory.OPERATIONS),
            ("employee onboarding benefits", DataCategory.HR),
            ("campaign audience engagement", DataCategory.MARKETING),
            ("contract nda compliance", DataCategory.LEGAL),
            ("ticket bug support issue", DataCategory.SUPPORT),
            ("hello world", DataCategory.GENERAL),
        ],
    )
    def test_classify_category(self, text, expected):
        category, _ = self._coord()._classify_category(text)
        assert category == expected

    def test_classify_confidence(self):
        coord = self._coord()
        cat, conf = coord._classify_category("invoice payment expense")
        assert cat == DataCategory.FINANCE
        assert conf == 1.0
        _, conf0 = coord._classify_category("")
        assert conf0 == 0.0

    def test_make_decision_low_confidence(self):
        coord = self._coord()
        decision, agent, reasoning = coord._make_decision(
            DataCategory.FINANCE, 0.2, "doc", None, {}
        )
        assert decision == TriggerDecision.NO_ACTION
        assert agent is None

    def test_make_decision_no_template(self):
        coord = self._coord()
        decision, agent, reasoning = coord._make_decision(
            DataCategory.LEGAL, 0.9, "doc", None, {}
        )
        assert decision == TriggerDecision.NO_ACTION

    def test_make_decision_medium_review(self):
        coord = self._coord()
        decision, agent, _ = coord._make_decision(
            DataCategory.SALES, 0.4, "doc", None, {"success_count": 1}
        )
        assert decision == TriggerDecision.QUEUE_FOR_REVIEW
        assert agent == "sales_assistant"

    def test_make_decision_medium_boosted_by_history(self):
        coord = self._coord()
        decision, agent, reasoning = coord._make_decision(
            DataCategory.SALES, 0.4, "doc", None, {"success_count": 3}
        )
        assert decision == TriggerDecision.TRIGGER_AGENT
        assert "success history" in reasoning

    def test_make_decision_high_confidence_memory_note(self):
        coord = self._coord()
        decision, agent, reasoning = coord._make_decision(
            DataCategory.FINANCE, 0.8, "doc", None,
            {"success_count": 2, "has_similar_history": True},
        )
        assert decision == TriggerDecision.TRIGGER_AGENT
        assert "memory-informed" in reasoning

    def test_make_decision_high_confidence_no_history(self):
        coord = self._coord()
        decision, agent, reasoning = coord._make_decision(
            DataCategory.FINANCE, 0.8, "doc", None, {"has_similar_history": False}
        )
        assert decision == TriggerDecision.TRIGGER_AGENT
        assert "memory-informed" not in reasoning

    @pytest.mark.asyncio
    async def test_trigger_agent_executes(self):
        coord = self._coord()
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value=MagicMock(id="ag1", name="Fin"))
        atom.execute = AsyncMock(return_value={"final_output": "ok"})
        decision = MagicMock()
        decision.execute = True
        decision.routing_decision.value = "supervision"
        decision.agent_maturity = "SUPERVISED"
        decision.confidence_score = 0.8
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.atom_meta_agent.AgentTriggerMode", MagicMock()), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.trigger_interceptor.TriggerSource", MagicMock()):
            await coord._trigger_agent("finance_analyst", {"text": "invoice"}, None, {})
        atom.execute.assert_awaited_once()
        atom.spawn_agent.assert_awaited_once_with("finance_analyst", persist=False)

    @pytest.mark.asyncio
    async def test_trigger_agent_blocked_training(self):
        coord = self._coord()
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value=MagicMock(id="ag1", name="Fin"))
        decision = MagicMock()
        decision.execute = False
        decision.routing_decision.value = "training"
        decision.agent_maturity = "STUDENT"
        decision.confidence_score = 0.4
        decision.reason = "needs training"
        decision.proposal = MagicMock(id="p1")
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.atom_meta_agent.AgentTriggerMode", MagicMock()), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.trigger_interceptor.TriggerSource", MagicMock()):
            result = await coord._trigger_agent("finance_analyst", {"text": "x"}, None, {})
        assert result == {
            "blocked": True, "reason": decision.reason,
            "routing_decision": "training", "proposal_id": "p1",
        }

    @pytest.mark.asyncio
    async def test_trigger_agent_blocked_proposal(self):
        coord = self._coord()
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value=MagicMock(id="ag1", name="Fin"))
        decision = MagicMock()
        decision.execute = False
        decision.routing_decision.value = "proposal"
        decision.agent_maturity = "INTERN"
        decision.confidence_score = 0.6
        decision.reason = "needs approval"
        decision.blocked_context = MagicMock(id="ctx1")
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.atom_meta_agent.AgentTriggerMode", MagicMock()), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.trigger_interceptor.TriggerSource", MagicMock()):
            result = await coord._trigger_agent("finance_analyst", {"text": "x"}, None, {})
        assert result["blocked"] is True
        assert result["routing_decision"] == "proposal"
        assert result["blocked_context_id"] == "ctx1"

    @pytest.mark.asyncio
    async def test_trigger_agent_execution_error_swallowed(self):
        coord = self._coord()
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value=MagicMock(id="ag1", name="Fin"))
        atom.execute = AsyncMock(side_effect=RuntimeError("exec fail"))
        decision = MagicMock()
        decision.execute = True
        decision.routing_decision.value = "supervision"
        decision.agent_maturity = "SUPERVISED"
        decision.confidence_score = 0.8
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.atom_meta_agent.AgentTriggerMode", MagicMock()), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.trigger_interceptor.TriggerSource", MagicMock()):
            await coord._trigger_agent("finance_analyst", {"text": "x"}, None, {})
        atom.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_data_ingested(self):
        with patch.object(AITriggerCoordinator, "evaluate_data", new_callable=AsyncMock) as ev:
            ev.return_value = {"decision": "no_action"}
            result = await on_data_ingested({"text": "hi"}, "webhook", "ws1", "u1")
        assert result["decision"] == "no_action"

    def test_get_coordinator_singleton(self):
        c1 = get_ai_trigger_coordinator("ws1")
        c2 = get_ai_trigger_coordinator("ws1")
        c3 = get_ai_trigger_coordinator("ws2")
        assert c1 is c2
        assert c1 is not c3
        assert c3.workspace_id == "ws2"


class TestCoverageEdgeCases:
    def test_root_depth_cycle_break(self, db_session):
        board = BoardService(db_session).create_board(None, BoardCreate(name="B", seed_default_columns=True))
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        task = BoardService(db_session).create_task(
            str(board.id), None, TaskCreate(title="T", column_id=str(col.id))
        )
        task.parent_task_id = task.id
        db_session.commit()
        assert BoardDecomposer(db_session)._root_depth(task) == 1

    @pytest.mark.asyncio
    async def test_release_lock_no_client(self, session_factory):
        d = BoardDispatcher(session_factory=session_factory)
        with patch("core.board_dispatcher._sync_job_queue", _make_patchable_queue()):
            await d._release_lock()

    @pytest.mark.asyncio
    async def test_run_loop_tick_exception_continues(self, session_factory):
        d = BoardDispatcher(session_factory=session_factory, tick_interval_seconds=0)
        calls = {"n": 0}

        async def flaky_tick():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("tick boom")

        d._tick = flaky_tick
        await d.start()
        await asyncio.sleep(0.05)
        await d.stop()
        assert calls["n"] >= 2

    @pytest.mark.asyncio
    async def test_trigger_agent_with_injected_db(self):
        coord = AITriggerCoordinator(workspace_id="ws", user_id="u1")
        coord.db = MagicMock()
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value=MagicMock(id="ag1", name="Fin"))
        atom.execute = AsyncMock(return_value={"final_output": "ok"})
        decision = MagicMock()
        decision.execute = True
        decision.routing_decision.value = "supervision"
        decision.agent_maturity = "SUPERVISED"
        decision.confidence_score = 0.8
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.atom_meta_agent.AgentTriggerMode", MagicMock()), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.trigger_interceptor.TriggerSource", MagicMock()):
            await coord._trigger_agent("finance_analyst", {"text": "invoice"}, None, {})
        atom.execute.assert_awaited_once()
        interceptor.intercept_trigger.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_trigger_agent_supervised_blocked_still_executes(self):
        coord = AITriggerCoordinator(workspace_id="ws", user_id="u1")
        coord.db = MagicMock()
        atom = MagicMock()
        atom.spawn_agent = AsyncMock(return_value=MagicMock(id="ag1", name="Fin"))
        atom.execute = AsyncMock(return_value={"final_output": "ok"})
        decision = MagicMock()
        decision.execute = False
        decision.routing_decision.value = "supervision"
        decision.agent_maturity = "SUPERVISED"
        decision.confidence_score = 0.8
        interceptor = MagicMock()
        interceptor.intercept_trigger = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.get_atom_agent", return_value=atom), \
             patch("core.atom_meta_agent.AgentTriggerMode", MagicMock()), \
             patch("core.trigger_interceptor.TriggerInterceptor", return_value=interceptor), \
             patch("core.trigger_interceptor.TriggerSource", MagicMock()):
            await coord._trigger_agent("finance_analyst", {"text": "invoice"}, None, {})
        atom.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_release_lock_exception_swallowed(self, session_factory):
        class BoomQueue:
            @property
            async def async_client(self):
                raise RuntimeError("redis down")

        d = BoardDispatcher(session_factory=session_factory, machine_id="m1")
        with patch("core.board_dispatcher._sync_job_queue", BoomQueue()):
            await d._release_lock()

    def test_dispatch_one_joins_canvas(self, db_session, session_factory):
        db_session.add(Tenant(id="t1", name="T", subdomain="t1"))
        db_session.commit()
        canvas = Canvas(tenant_id="t1", created_by="system", name="ws", canvas_type="kanban")
        db_session.add(canvas)
        db_session.flush()
        board = BoardService(db_session).create_board(
            None, BoardCreate(name="B", seed_default_columns=True)
        )
        col = db_session.query(BoardColumn).filter(BoardColumn.board_id == board.id).first()
        task = BoardService(db_session).create_task(
            str(board.id), None,
            TaskCreate(title="T", column_id=str(col.id), status="todo",
                       assignee_agent_id="ag1"),
        )
        task.canvas_id = canvas.id
        db_session.commit()
        d = BoardDispatcher(session_factory=session_factory)
        with TestBoardDispatcher._allow_governance():
            d._dispatch_one(db_session, task)
        presence = db_session.query(AgentCanvasPresence).first()
        assert presence is not None
        assert presence.canvas_id == str(canvas.id)
        assert task.status == "in_progress"
