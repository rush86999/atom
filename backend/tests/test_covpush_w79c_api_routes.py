"""Coverage wave W79C — 8 API modules to >=95% statement coverage standalone.

Targets (before → after):
1. api/workflow_template_routes.py        96% → 100% (fill get_template_manager
   body, import-template ValueError, execute ValueError/HTTPException paths)
2. api/workflow_versioning_endpoints.py   38% → 100% (stale api suite broken —
   missing `test_app` fixture — so rewritten standalone: every endpoint ×
   success/404/422/500 + get_workflow_data file branches)
3. api/workspace_context_routes.py        96% → 100% (string-coerced curated
   context + missing-skill 404)
4. api/zoho_workdrive_routes.py          100% → 100% (standalone re-cover)
5. api/admin_routes.py                    99% → 99% (lines 621/920 are dead code
   behind a hardcoded `user_maturity` local — documented in report)
6. api/schemas/board_comment_schemas.py  100% → 100% (standalone re-cover)
7. api/schemas/board_decompose_schemas.py  0% → 100%
8. api/schemas/board_schemas.py          100% → 100% (standalone re-cover)

Conventions (W75B/W78B): FastAPI TestClient + dependency_overrides, patches on
real module names (no `backend.` prefix), zero network / LLM spend, no real DB
(admin/template/versioning/zoho use mocked sessions; workspace_context uses the
in-memory `db_session` fixture). Schemas: direct Pydantic validation tests.
"""
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.admin_routes import router as admin_router
from api.workflow_template_routes import router as template_router
from api.workflow_versioning_endpoints import (
    VersionCreateRequest,
    VersionDiffResponse,
    RollbackRequest,
    BranchCreateRequest,
    MergeRequest,
    get_workflow_data,
    router as versioning_router,
)
from api.workspace_context_routes import router as workspace_router
from api.zoho_workdrive_routes import router as zoho_router
from core.auth import get_current_user
from core.database import get_db
from core.models import AdminRole, AdminUser, User, UserRole
from core.workflow_template_system import (
    TemplateCategory,
    TemplateComplexity,
)
from core.workflow_versioning_system import ChangeType, VersionType


# ============================================================================
# Shared user fixtures
# ============================================================================
@pytest.fixture
def admin_user():
    user = MagicMock()
    user.id = "admin-w79c"
    user.email = "admin@test.local"
    user.role = "super_admin"
    user.status = "active"
    return user


@pytest.fixture
def member_user():
    user = MagicMock()
    user.id = "member-w79c"
    user.email = "member@test.local"
    user.role = "member"
    user.status = "active"
    return user


def _app(router, user=None, mock_db=False):
    app = FastAPI()
    app.include_router(router)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    if mock_db:
        db = MagicMock()

        def _get_db():
            yield db

        app.dependency_overrides[get_db] = _get_db
        app.db = db
    return app


def _client(router, user=None, mock_db=False, raise_exc=False):
    app = _app(router, user=user, mock_db=mock_db)
    client = TestClient(app, raise_server_exceptions=raise_exc)
    client.app = app
    return client


# ============================================================================
# 1. api/schemas/board_comment_schemas.py
# ============================================================================
class TestCommentSchemas:
    def test_comment_create_valid(self):
        from api.schemas.board_comment_schemas import CommentCreate

        c = CommentCreate(content="hello", parent_message_id="p1")
        assert c.content == "hello"
        assert c.parent_message_id == "p1"

    def test_comment_create_defaults_parent_none(self):
        from api.schemas.board_comment_schemas import CommentCreate

        c = CommentCreate(content="x")
        assert c.parent_message_id is None

    def test_comment_create_empty_content_rejected(self):
        from pydantic import ValidationError

        from api.schemas.board_comment_schemas import CommentCreate

        with pytest.raises(ValidationError):
            CommentCreate(content="")
        with pytest.raises(ValidationError):
            CommentCreate(content="a" * 10_001)
        with pytest.raises(ValidationError):
            CommentCreate()

    def test_comment_patch_valid_and_defaults(self):
        from api.schemas.board_comment_schemas import CommentPatch

        p = CommentPatch(content="edit")
        assert p.expected_version is None
        p2 = CommentPatch(content="edit", expected_version=3)
        assert p2.expected_version == 3
        with pytest.raises(Exception):
            CommentPatch(content="")

    def test_author_info_all_optional(self):
        from api.schemas.board_comment_schemas import AuthorInfo

        a = AuthorInfo()
        assert a.user_id is None and a.agent_id is None and a.display_name is None
        a2 = AuthorInfo(user_id="u", agent_id="a", display_name="d")
        assert a2.user_id == "u" and a2.agent_id == "a" and a2.display_name == "d"

    def test_comment_read_from_attributes(self):
        from api.schemas.board_comment_schemas import CommentRead

        src = SimpleNamespace(
            id="c1",
            task_id="t1",
            conversation_id=None,
            content="body",
            author={"user_id": "u1", "agent_id": None, "display_name": "U"},
            parent_message_id=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        r = CommentRead.model_validate(src)
        assert r.id == "c1"
        assert r.author.user_id == "u1"
        assert r.replies == []

    def test_comment_read_with_replies(self):
        from api.schemas.board_comment_schemas import CommentRead

        reply_src = SimpleNamespace(
            id="c2",
            task_id="t1",
            conversation_id=None,
            content="reply",
            author={"user_id": None, "agent_id": "ag1", "display_name": "A"},
            parent_message_id="c1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        src = SimpleNamespace(
            id="c1",
            task_id="t1",
            conversation_id="conv-1",
            content="body",
            author={"user_id": "u1", "agent_id": None, "display_name": "U"},
            parent_message_id=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        r = CommentRead.model_validate(src)
        r.replies.append(CommentRead.model_validate(reply_src))
        assert len(r.replies) == 1
        assert r.replies[0].author.agent_id == "ag1"
        assert r.replies[0].parent_message_id == "c1"

    def test_artifact_comment_read_from_attributes(self):
        from api.schemas.board_comment_schemas import ArtifactCommentRead

        src = SimpleNamespace(
            id="a1",
            artifact_id="art-1",
            canvas_id=None,
            content="note",
            user_id="u1",
            agent_id=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=None,
        )
        r = ArtifactCommentRead.model_validate(src)
        assert r.artifact_id == "art-1"
        assert r.updated_at is None

    def test_artifact_comment_read_with_updated_at(self):
        from api.schemas.board_comment_schemas import ArtifactCommentRead

        src = SimpleNamespace(
            id="a2",
            artifact_id="art-2",
            canvas_id="cv-1",
            content="note",
            user_id=None,
            agent_id="ag9",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        r = ArtifactCommentRead.model_validate(src)
        assert r.canvas_id == "cv-1"
        assert r.updated_at is not None

    def test_slash_reply_defaults(self):
        from api.schemas.board_comment_schemas import SlashReply

        s = SlashReply(reply="ok", action_type="run")
        assert s.ok is True
        assert s.task_id is None
        assert s.extra == {}

    def test_slash_reply_full(self):
        from api.schemas.board_comment_schemas import SlashReply

        s = SlashReply(ok=False, reply="no", action_type="skip", task_id="t9", extra={"k": 1})
        assert s.ok is False and s.task_id == "t9" and s.extra == {"k": 1}


# ============================================================================
# 2. api/schemas/board_decompose_schemas.py
# ============================================================================
class TestBoardDecomposeSchemas:
    def test_decompose_request_defaults(self):
        from api.schemas.board_decompose_schemas import DecomposeRequest

        r = DecomposeRequest()
        assert r.spawn_workspaces is False
        assert r.model_hint is None

    def test_decompose_request_explicit(self):
        from api.schemas.board_decompose_schemas import DecomposeRequest

        r = DecomposeRequest(spawn_workspaces=True, model_hint="deepseek-v4-flash")
        assert r.spawn_workspaces is True
        assert r.model_hint == "deepseek-v4-flash"

    def test_decompose_commit_request_valid(self):
        from api.schemas.board_decompose_schemas import DecomposeCommitRequest
        from core.board_decomposer import SubtaskProposal

        proposals = [
            SubtaskProposal(title="Sub 1", description="d", column_name="Todo"),
            SubtaskProposal(title="Sub 2", priority="high", estimated_hours=2.5),
        ]
        r = DecomposeCommitRequest(proposals=proposals, spawn_workspaces=True)
        assert len(r.proposals) == 2
        assert r.proposals[1].priority == "high"
        assert r.spawn_workspaces is True

    def test_decompose_commit_request_default_spawn(self):
        from api.schemas.board_decompose_schemas import DecomposeCommitRequest
        from core.board_decomposer import SubtaskProposal

        r = DecomposeCommitRequest(proposals=[SubtaskProposal(title="t")])
        assert r.spawn_workspaces is False
        assert r.proposals[0].column_name == "Backlog"

    def test_decompose_commit_request_rejects_invalid_proposal(self):
        from pydantic import ValidationError

        from api.schemas.board_decompose_schemas import DecomposeCommitRequest
        from core.board_decomposer import SubtaskProposal

        with pytest.raises(ValidationError):
            DecomposeCommitRequest(proposals=[SubtaskProposal(title="")])
        with pytest.raises(ValidationError):
            DecomposeCommitRequest(proposals=[SubtaskProposal(title="x" * 501)])

    def test_decompose_preview(self):
        from api.schemas.board_decompose_schemas import DecomposePreview
        from core.board_decomposer import SubtaskProposal

        p = DecomposePreview(
            parent_task_id="pt1",
            rationale="too big",
            subtasks=[SubtaskProposal(title="a"), SubtaskProposal(title="b")],
            depth=2,
            max_depth=5,
        )
        assert p.depth == 2 and p.max_depth == 5
        assert len(p.subtasks) == 2

    def test_decompose_commit_result(self):
        from api.schemas.board_decompose_schemas import DecomposeCommitResult

        r = DecomposeCommitResult(
            parent_task_id="pt1",
            created_task_ids=["c1", "c2"],
            spawned_workspaces=True,
        )
        assert r.created_task_ids == ["c1", "c2"]
        assert r.spawned_workspaces is True

    def test_subtask_proposal_and_result_models(self):
        from core.board_decomposer import DecompositionResult, SubtaskProposal

        p = SubtaskProposal(title="x", description=None)
        assert p.description is None
        d = DecompositionResult(subtasks=[p])
        assert d.rationale == ""
        assert d.subtasks[0].title == "x"


# ============================================================================
# 3. api/schemas/board_schemas.py
# ============================================================================
class TestBoardSchemas:
    def test_column_create_valid_and_bounds(self):
        from pydantic import ValidationError

        from api.schemas.board_schemas import ColumnCreate

        c = ColumnCreate(name="Todo")
        assert c.position == 0 and c.wip_limit is None
        c2 = ColumnCreate(name="Done", position=3, wip_limit=5)
        assert c2.position == 3 and c2.wip_limit == 5
        with pytest.raises(ValidationError):
            ColumnCreate(name="")
        with pytest.raises(ValidationError):
            ColumnCreate(name="x" * 121)

    def test_column_read_from_attributes(self):
        from api.schemas.board_schemas import ColumnRead

        src = SimpleNamespace(
            id="col1", board_id="b1", name="Todo", position=0,
            wip_limit=None, version_id=7,
        )
        r = ColumnRead.model_validate(src)
        assert r.task_count == 0
        assert r.version_id == 7

    def test_column_read_with_wip_and_count(self):
        from api.schemas.board_schemas import ColumnRead

        src = SimpleNamespace(
            id="col2", board_id="b1", name="Done", position=1,
            wip_limit=3, version_id=8,
        )
        r = ColumnRead.model_validate(src)
        r.task_count = 2
        assert r.wip_limit == 3 and r.task_count == 2

    def test_board_create_defaults_and_bounds(self):
        from pydantic import ValidationError

        from api.schemas.board_schemas import BoardCreate

        b = BoardCreate(name="Board")
        assert b.slug is None and b.description is None
        assert b.seed_default_columns is True
        b2 = BoardCreate(name="B", slug="my-slug", description="d", seed_default_columns=False)
        assert b2.slug == "my-slug" and b2.seed_default_columns is False
        with pytest.raises(ValidationError):
            BoardCreate(name="")
        with pytest.raises(ValidationError):
            BoardCreate(name="b", slug="s" * 121)

    def test_board_read_from_attributes(self):
        from api.schemas.board_schemas import BoardRead

        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        src = SimpleNamespace(
            id="b1", name="Board", slug=None, description=None,
            owner_user_id=None, archived_at=None, version_id=1,
            created_at=ts, updated_at=ts,
        )
        r = BoardRead.model_validate(src)
        assert r.archived_at is None and r.version_id == 1

    def test_board_detail_defaults_columns(self):
        from api.schemas.board_schemas import BoardDetail

        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        src = SimpleNamespace(
            id="b2", name="B", slug="s", description="d", owner_user_id="u",
            archived_at=None, version_id=2, created_at=ts, updated_at=ts,
        )
        d = BoardDetail.model_validate(src)
        assert d.columns == []

    def test_task_create_defaults(self):
        from api.schemas.board_schemas import TaskCreate

        t = TaskCreate(title="T", column_id="col1")
        assert t.status == "backlog" and t.priority == "normal"
        assert t.labels == [] and t.metadata_json == {}
        assert t.workspace is False and t.assignee_user_id is None
        assert t.due_at is None and t.parent_task_id is None

    def test_task_create_full_and_bounds(self):
        from pydantic import ValidationError

        from api.schemas.board_schemas import TaskCreate

        t = TaskCreate(
            title="T", description="d", column_id="col1", status="in_progress",
            priority="high", assignee_user_id="u1", assignee_agent_id="a1",
            parent_task_id="pt1", due_at=datetime(2026, 2, 1),
            labels=["x"], metadata_json={"k": 1}, workspace=True,
        )
        assert t.workspace is True and t.metadata_json == {"k": 1}
        with pytest.raises(ValidationError):
            TaskCreate(title="", column_id="c")
        with pytest.raises(ValidationError):
            TaskCreate(title="t")

    def test_task_patch_expected_version_required(self):
        from pydantic import ValidationError

        from api.schemas.board_schemas import TaskPatch

        with pytest.raises(ValidationError):
            TaskPatch()
        p = TaskPatch(expected_version=4)
        assert p.column_id is None and p.workspace is None
        p2 = TaskPatch(expected_version=5, status="done", labels=["a"], workspace=True)
        assert p2.status == "done" and p2.labels == ["a"] and p2.workspace is True

    def test_canvas_summary_defaults(self):
        from api.schemas.board_schemas import CanvasSummary

        c = CanvasSummary(canvas_id="cv1", name="Canvas", status="active")
        assert c.artifact_count == 0 and c.presence_count == 0
        c2 = CanvasSummary(canvas_id="cv2", name="C", status="s", artifact_count=3, presence_count=1)
        assert c2.artifact_count == 3 and c2.presence_count == 1

    def test_task_read_from_attributes(self):
        from api.schemas.board_schemas import TaskRead

        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        src = SimpleNamespace(
            id="task1", board_id="b1", column_id="col1", title="T",
            description=None, status="backlog", priority="normal",
            assignee_user_id=None, assignee_agent_id=None, parent_task_id=None,
            root_task_id=None, sort_order=1.0, due_at=None, labels=[],
            metadata_json={}, created_by_user_id=None, canvas_id=None,
            version_id=1, created_at=ts, updated_at=ts,
        )
        r = TaskRead.model_validate(src)
        assert r.canvas is None and r.labels == []

    def test_task_read_with_canvas(self):
        from api.schemas.board_schemas import CanvasSummary, TaskRead

        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        src = SimpleNamespace(
            id="task2", board_id="b1", column_id="col2", title="T2",
            description="d", status="doing", priority="high",
            assignee_user_id="u1", assignee_agent_id=None, parent_task_id=None,
            root_task_id=None, sort_order=2.5, due_at=None, labels=["l"],
            metadata_json={"m": 1}, created_by_user_id="u1", canvas_id="cv1",
            version_id=3, created_at=ts, updated_at=ts,
        )
        r = TaskRead.model_validate(src)
        r.canvas = CanvasSummary(canvas_id="cv1", name="C", status="active")
        assert r.canvas.canvas_id == "cv1" and r.sort_order == 2.5

    def test_rebalance_request_default_and_result(self):
        from api.schemas.board_schemas import RebalanceRequest, RebalanceResult

        r = RebalanceRequest()
        assert r.column_id is None
        r2 = RebalanceRequest(column_id="col1")
        assert r2.column_id == "col1"
        res = RebalanceResult(rebalanced_columns=["col1"], moved_tasks=4)
        assert res.moved_tasks == 4


# ============================================================================
# 4. api/zoho_workdrive_routes.py
# ============================================================================
@pytest.fixture
def zoho_client(admin_user):
    return _client(zoho_router, user=admin_user)


class TestZohoTeams:
    def test_teams_success(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service.get_teams",
                   new=AsyncMock(return_value=[{"id": "t1"}])):
            resp = zoho_client.get("/api/zoho-workdrive/teams")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"id": "t1"}]

    def test_teams_error_500(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service.get_teams",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = zoho_client.get("/api/zoho-workdrive/teams")
        assert resp.status_code == 500
        assert resp.json()["detail"]["error"]["code"] == "INTERNAL_ERROR"

    def test_teams_unauthenticated_401(self):
        resp = _client(zoho_router).get("/api/zoho-workdrive/teams")
        assert resp.status_code == 401


class TestZohoListFiles:
    def test_list_files_success(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(return_value=[{"id": "f1"}])):
            resp = zoho_client.post("/api/zoho-workdrive/files/list", json={
                "user_id": "u1", "parent_id": "root"})
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"id": "f1"}]

    def test_list_files_default_parent(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(return_value=[])) as m:
            resp = zoho_client.post("/api/zoho-workdrive/files/list", json={})
        assert resp.status_code == 200
        m.assert_awaited_once_with("admin-w79c", "root", None, None, False)

    def test_list_files_error_500(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = zoho_client.post("/api/zoho-workdrive/files/list", json={"user_id": "u1"})
        assert resp.status_code == 500

    def test_list_files_empty_body_is_valid(self, zoho_client):
        # user_id removed from the schema (token-derived identity): all fields
        # are optional now, so an empty body defaults to the root folder.
        with patch("api.zoho_workdrive_routes.zoho_service.list_files",
                   new=AsyncMock(return_value=[])) as m:
            resp = zoho_client.post("/api/zoho-workdrive/files/list", json={})
        assert resp.status_code == 200
        m.assert_awaited_once_with("admin-w79c", "root", None, None, False)


class TestZohoIngest:
    @staticmethod
    def _await_ingest_job(zoho_client, job_id, timeout=5.0):
        # Ingest runs as a background task; poll the job-status endpoint
        # until it leaves "running" (mocked service calls resolve fast).
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = zoho_client.get(f"/api/zoho-workdrive/ingest/jobs/{job_id}")
            assert resp.status_code == 200
            job = resp.json()["data"]
            if job["status"] != "running":
                return job
            time.sleep(0.02)
        raise AssertionError(f"ingest job {job_id} never finished")

    def test_ingest_starts_background_job_and_completes(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service.ingest_file_to_memory",
                   new=AsyncMock(return_value={"success": True, "doc_id": "d1"})):
            resp = zoho_client.post("/api/zoho-workdrive/ingest", json={
                "user_id": "u1", "file_id": "f1"})
        assert resp.status_code == 200
        job = self._await_ingest_job(zoho_client, resp.json()["data"]["job_id"])
        assert job["status"] == "completed"
        assert job["result"]["doc_id"] == "d1"

    def test_ingest_service_error_becomes_failed_job(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service.ingest_file_to_memory",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = zoho_client.post("/api/zoho-workdrive/ingest", json={
                "user_id": "u1", "file_id": "f1"})
        assert resp.status_code == 200
        job = self._await_ingest_job(zoho_client, resp.json()["data"]["job_id"])
        assert job["status"] == "failed"
        assert "boom" in job["error"]

    def test_ingest_validation_422(self, zoho_client):
        resp = zoho_client.post("/api/zoho-workdrive/ingest", json={})
        assert resp.status_code == 422


class TestZohoHealth:
    def test_health_configured(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.client_id = "id"
            svc.client_secret = "sec"
            svc.redirect_uri = "uri"
            resp = zoho_client.get("/api/zoho-workdrive/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "configured"

    def test_health_unconfigured(self, zoho_client):
        with patch("api.zoho_workdrive_routes.zoho_service") as svc:
            svc.client_id = None
            svc.client_secret = None
            svc.redirect_uri = None
            resp = zoho_client.get("/api/zoho-workdrive/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "unconfigured"


# ============================================================================
# 5. api/workspace_context_routes.py
# ============================================================================
def _ws_ctx_client(db_session, user):
    from api.workspace_context_routes import router
    from core.admin_endpoints import get_super_admin
    from core.auth import get_current_user as get_current_user_fn
    from core.database import get_db as get_db_fn

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db_fn] = override_get_db
    app.dependency_overrides[get_current_user_fn] = override_get_current_user
    return TestClient(app)


def _ws_model(db_session, ws_id="ws-1", curated=None, meta_extra=None):
    from core.models import Workspace

    meta = dict(meta_extra or {})
    if curated is not None:
        meta["curated_context"] = curated
    ws = Workspace(id=ws_id, name="WS", metadata_json=meta)
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)
    return ws


def _skill_model(db_session, skill_id="sk-1", name="invoice_parser"):
    from core.models import Skill

    skill = Skill(id=skill_id, name=name, description="d", type="api",
                  is_approved=True, is_public=True)
    db_session.add(skill)
    db_session.flush()
    return skill


class TestWorkspaceContextGet:
    def test_get_context_success(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-g1", curated=["blob a", ""])
        admin = MagicMock()
        admin.id = "admin-ctx"
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["curated_context"] == ["blob a"]
        assert body["data"]["skill_names"] == []

    def test_get_context_string_coercion(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-g2", curated="single string blob")
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert resp.status_code == 200
        assert resp.json()["data"]["curated_context"] == ["single string blob"]

    def test_get_context_none_metadata(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-g3")
        ws.metadata_json = None
        db_session.commit()
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert resp.status_code == 200
        assert resp.json()["data"]["curated_context"] == []

    def test_get_context_missing_workspace_404(self, db_session):
        from core.models import UserRole

        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.get("/api/workspaces/nope/context")
        assert resp.status_code == 404

    def test_get_context_non_admin_403(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-g4")
        member = MagicMock()
        member.role = UserRole.MEMBER.value
        client = _ws_ctx_client(db_session, member)
        assert client.get(f"/api/workspaces/{ws.id}/context").status_code == 403

    def test_get_context_skill_names_sorted_unique(self, db_session):
        from core.models import UserRole, workspace_skills

        ws = _ws_model(db_session, "ws-g5")
        _skill_model(db_session, "sk-b", "zeta_skill")
        _skill_model(db_session, "sk-a", "alpha_skill")
        db_session.execute(workspace_skills.insert().values(
            workspace_id=ws.id, skill_id="sk-a"))
        db_session.execute(workspace_skills.insert().values(
            workspace_id=ws.id, skill_id="sk-b"))
        db_session.commit()
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.get(f"/api/workspaces/{ws.id}/context")
        assert resp.json()["data"]["skill_names"] == ["alpha_skill", "zeta_skill"]


class TestWorkspaceContextPut:
    def test_put_context_success(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-p1", curated=["old"])
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.put(f"/api/workspaces/{ws.id}/context",
                          json={"curated_context": ["new blob", "", "other"]})
        assert resp.status_code == 200
        db_session.refresh(ws)
        assert ws.metadata_json["curated_context"] == ["new blob", "other"]

    def test_put_context_empty_list(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-p2", curated=["old"])
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.put(f"/api/workspaces/{ws.id}/context", json={"curated_context": []})
        assert resp.status_code == 200
        db_session.refresh(ws)
        assert ws.metadata_json["curated_context"] == []

    def test_put_context_preserves_other_metadata(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-p3", curated=["old"], meta_extra={"foo": "bar"})
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.put(f"/api/workspaces/{ws.id}/context",
                          json={"curated_context": ["updated"]})
        assert resp.status_code == 200
        db_session.refresh(ws)
        assert ws.metadata_json["foo"] == "bar"
        assert ws.metadata_json["curated_context"] == ["updated"]

    def test_put_context_missing_workspace_404(self, db_session):
        from core.models import UserRole

        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.put("/api/workspaces/nope/context", json={"curated_context": ["x"]})
        assert resp.status_code == 404


class TestWorkspaceContextSkills:
    def test_assign_skill_success(self, db_session):
        from core.models import UserRole, workspace_skills

        ws = _ws_model(db_session, "ws-s1")
        _skill_model(db_session, "sk-s1", "parser")
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.post(f"/api/workspaces/{ws.id}/skills/sk-s1")
        assert resp.status_code == 200
        assert resp.json()["data"]["assigned"] is True
        row = db_session.execute(workspace_skills.select().where(
            workspace_skills.c.workspace_id == ws.id)).first()
        assert row.skill_id == "sk-s1"

    def test_assign_skill_idempotent(self, db_session):
        from core.models import UserRole, workspace_skills

        ws = _ws_model(db_session, "ws-s2")
        _skill_model(db_session, "sk-s2", "parser")
        db_session.execute(workspace_skills.insert().values(
            workspace_id=ws.id, skill_id="sk-s2"))
        db_session.commit()
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.post(f"/api/workspaces/{ws.id}/skills/sk-s2")
        assert resp.status_code == 200
        rows = db_session.execute(workspace_skills.select()).fetchall()
        assert len([r for r in rows if r.workspace_id == ws.id]) == 1

    def test_assign_skill_missing_skill_404(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-s3")
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.post(f"/api/workspaces/{ws.id}/skills/no-such-skill")
        assert resp.status_code == 404

    def test_assign_skill_missing_workspace_404(self, db_session):
        from core.models import UserRole

        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        assert client.post("/api/workspaces/nope/skills/sk-1").status_code == 404

    def test_unassign_skill_success(self, db_session):
        from core.models import UserRole, workspace_skills

        ws = _ws_model(db_session, "ws-s4")
        _skill_model(db_session, "sk-s4", "parser")
        db_session.execute(workspace_skills.insert().values(
            workspace_id=ws.id, skill_id="sk-s4"))
        db_session.commit()
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.delete(f"/api/workspaces/{ws.id}/skills/sk-s4")
        assert resp.status_code == 200
        assert resp.json()["data"]["assigned"] is False
        rows = db_session.execute(workspace_skills.select()).fetchall()
        assert len([r for r in rows if r.workspace_id == ws.id]) == 0

    def test_unassign_skill_idempotent(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-s5")
        _skill_model(db_session, "sk-s5", "parser")
        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        resp = client.delete(f"/api/workspaces/{ws.id}/skills/sk-s5")
        assert resp.status_code == 200

    def test_unassign_skill_missing_workspace_404(self, db_session):
        from core.models import UserRole

        admin = MagicMock()
        admin.role = UserRole.SUPER_ADMIN.value
        client = _ws_ctx_client(db_session, admin)
        assert client.delete("/api/workspaces/nope/skills/sk-1").status_code == 404

    def test_skills_non_admin_403(self, db_session):
        from core.models import UserRole

        ws = _ws_model(db_session, "ws-s6")
        member = MagicMock()
        member.role = UserRole.MEMBER.value
        client = _ws_ctx_client(db_session, member)
        assert client.post(f"/api/workspaces/{ws.id}/skills/sk-1").status_code == 403
        assert client.delete(f"/api/workspaces/{ws.id}/skills/sk-1").status_code == 403


# ============================================================================
# 6. api/workflow_template_routes.py
# ============================================================================
def _tpl(**kw):
    t = SimpleNamespace(
        template_id=kw.get("template_id", "tpl-1"),
        name=kw.get("name", "Template"),
        description=kw.get("description", "desc"),
        category=kw.get("category", TemplateCategory("automation")),
        complexity=kw.get("complexity", TemplateComplexity("intermediate")),
        tags=kw.get("tags", ["a"]),
        usage_count=kw.get("usage_count", 3),
        rating=kw.get("rating", 4.5),
        is_featured=kw.get("is_featured", False),
    )
    t.steps = kw.get("steps", [SimpleNamespace(model_dump=lambda: {"id": "s1"})])
    return t


def _tpl_client(monkeypatch):
    """Real get_template_manager() body runs; WorkflowTemplateManager class is
    replaced so the manager is a MagicMock (no disk/network)."""
    manager = MagicMock()
    manager_cls = MagicMock(return_value=manager)
    monkeypatch.setattr(
        "core.workflow_template_system.WorkflowTemplateManager", manager_cls)
    app = _app(template_router, user=MagicMock(id="u1"), mock_db=True)
    client = TestClient(app, raise_server_exceptions=False)
    client.manager = manager
    return client


class TestTemplateGetTemplateManager:
    def test_get_template_manager_returns_manager(self, monkeypatch):
        manager_cls = MagicMock(return_value="the-manager")
        monkeypatch.setattr(
            "core.workflow_template_system.WorkflowTemplateManager", manager_cls)
        from api.workflow_template_routes import get_template_manager

        assert get_template_manager() == "the-manager"
        manager_cls.assert_called_once_with()

    def test_template_client_runs_real_manager_ctor(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_template.return_value = SimpleNamespace(
            template_id="t1", name="N")
        resp = client.post("/api/workflow-templates/", json={
            "name": "N", "description": "d"})
        assert resp.status_code == 200


class TestTemplateCreate:
    def test_create_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        created = SimpleNamespace(template_id="tpl-new", name="My Template")
        client.manager.create_template.return_value = created
        resp = client.post("/api/workflow-templates/", json={
            "name": "My Template", "description": "d", "category": "automation",
            "complexity": "intermediate", "tags": ["t"],
            "steps": [{"step_id": "s1", "name": "S1", "step_type": "agent_execution",
                       "parameters": [{"name": "p"}], "depends_on": []}],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success" and body["template_id"] == "tpl-new"
        call_data = client.manager.create_template.call_args[0][0]
        assert call_data["steps"][0]["step_id"] == "s1"
        assert call_data["steps"][0]["step_type"] == "agent_execution"

    def test_create_default_step_fields(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_template.return_value = SimpleNamespace(
            template_id="t2", name="N")
        resp = client.post("/api/workflow-templates/", json={
            "name": "N", "description": "d",
            "steps": [{}],
        })
        assert resp.status_code == 200
        step = client.manager.create_template.call_args[0][0]["steps"][0]
        assert step["step_id"] == "step_0"
        assert step["name"] == "Step 0"
        assert step["step_type"] == "agent_execution"

    def test_create_invalid_category_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.post("/api/workflow-templates/", json={
            "name": "N", "description": "d", "category": "bogus"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["detail"]["error"]["code"] == "VALIDATION_ERROR"
        assert body["detail"]["error"]["details"]["provided_category"] == "bogus"

    def test_create_invalid_complexity_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.post("/api/workflow-templates/", json={
            "name": "N", "description": "d", "complexity": "bogus"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["details"]["provided_complexity"] == "bogus"

    def test_create_empty_name_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.post("/api/workflow-templates/", json={
            "name": "", "description": "d"})
        assert resp.status_code == 422

    def test_create_missing_name_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.post("/api/workflow-templates/", json={"description": "d"})
        assert resp.status_code == 422

    def test_create_manager_exception_500(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_template.side_effect = RuntimeError("boom")
        resp = client.post("/api/workflow-templates/", json={
            "name": "N", "description": "d"})
        assert resp.status_code == 500

    def test_create_unauthenticated_401(self):
        resp = _client(template_router).post("/api/workflow-templates/", json={
            "name": "N", "description": "d"})
        assert resp.status_code == 401


class TestTemplateList:
    def test_list_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.list_templates.return_value = [_tpl()]
        resp = client.get("/api/workflow-templates/")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["template_id"] == "tpl-1"
        assert data[0]["category"] == "automation"
        assert data[0]["is_featured"] is False
        client.manager.list_templates.assert_called_once_with(limit=50)

    def test_list_with_category(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.list_templates.return_value = []
        resp = client.get("/api/workflow-templates/?category=data_processing")
        assert resp.status_code == 200
        call = client.manager.list_templates.call_args
        assert call.kwargs["category"] == TemplateCategory("data_processing")
        assert call.kwargs["limit"] == 50

    def test_list_invalid_category_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.get("/api/workflow-templates/?category=bogus")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_list_steps_dict_branch(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        step = SimpleNamespace()
        tpl = _tpl(steps=[step])
        client.manager.list_templates.return_value = [tpl]
        resp = client.get("/api/workflow-templates/")
        assert resp.status_code == 200

    def test_list_manager_exception_500(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.list_templates.side_effect = RuntimeError("boom")
        resp = client.get("/api/workflow-templates/")
        assert resp.status_code == 500

    def test_list_unauthenticated_401(self):
        assert _client(template_router).get("/api/workflow-templates/").status_code == 401


class TestTemplateSearch:
    def test_search_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.search_templates.return_value = [_tpl()]
        resp = client.get("/api/workflow-templates/search?query=email")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["name"] == "Template"
        client.manager.search_templates.assert_called_once_with("email", limit=20)

    def test_search_with_limit(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.search_templates.return_value = []
        resp = client.get("/api/workflow-templates/search?query=q&limit=5")
        assert resp.status_code == 200
        assert client.manager.search_templates.call_args.kwargs["limit"] == 5

    def test_search_exception_500(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.search_templates.side_effect = RuntimeError("boom")
        resp = client.get("/api/workflow-templates/search?query=q")
        assert resp.status_code == 500


class TestTemplateGet:
    def test_get_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        tpl = MagicMock()
        tpl.dict.return_value = {"template_id": "tpl-1", "name": "T"}
        client.manager.get_template.return_value = tpl
        resp = client.get("/api/workflow-templates/tpl-1")
        assert resp.status_code == 200
        assert resp.json()["template_id"] == "tpl-1"

    def test_get_not_found_404(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.get_template.return_value = None
        resp = client.get("/api/workflow-templates/nope")
        assert resp.status_code == 404


class TestTemplateUpdate:
    def test_update_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        updated = MagicMock()
        updated.dict.return_value = {"name": "Renamed"}
        client.manager.update_template.return_value = updated
        resp = client.put("/api/workflow-templates/tpl-1", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["template"]["name"] == "Renamed"
        client.manager.update_template.assert_called_once_with(
            "tpl-1", {"name": "Renamed"})

    def test_update_with_steps(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        updated = MagicMock()
        updated.dict.return_value = {"steps": []}
        client.manager.update_template.return_value = updated
        resp = client.put("/api/workflow-templates/tpl-1", json={
            "steps": [{"step_id": "s1", "name": "S1", "step_type": "action",
                       "parameters": [], "depends_on": [], "condition": "c"}]
        })
        assert resp.status_code == 200
        sent = client.manager.update_template.call_args[0][1]["steps"]
        assert sent[0]["id"] == "s1"
        assert sent[0]["condition"] == "c"

    def test_update_no_updates_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.put("/api/workflow-templates/tpl-1", json={})
        assert resp.status_code == 422

    def test_update_blocked_fields_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.put("/api/workflow-templates/tpl-1", json={
            "category": "automation", "is_featured": True, "rating": 5})
        assert resp.status_code == 422

    def test_update_value_error_404(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.update_template.side_effect = ValueError("not found")
        resp = client.put("/api/workflow-templates/nope", json={"name": "X"})
        assert resp.status_code == 404

    def test_update_generic_exception_500(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.update_template.side_effect = RuntimeError("boom")
        resp = client.put("/api/workflow-templates/tpl-1", json={"name": "X"})
        assert resp.status_code == 500

    def test_update_http_exception_re_raised(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.update_template.side_effect = HTTPException(418, "teapot")
        resp = client.put("/api/workflow-templates/tpl-1", json={"name": "X"})
        assert resp.status_code == 418


class TestTemplateInstantiate:
    def test_instantiate_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.return_value = {
            "workflow_id": "wf-1", "workflow_definition": {}}
        resp = client.post("/api/workflow-templates/tpl-1/instantiate", json={
            "workflow_name": "W", "parameters": {"p": 1}, "customizations": {"c": 2}})
        assert resp.status_code == 200
        assert resp.json()["workflow_id"] == "wf-1"
        call = client.manager.create_workflow_from_template.call_args
        assert call.kwargs["template_id"] == "tpl-1"
        assert call.kwargs["template_parameters"] == {"p": 1}

    def test_instantiate_value_error_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.side_effect = ValueError("bad params")
        resp = client.post("/api/workflow-templates/tpl-1/instantiate", json={
            "workflow_name": "W"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_instantiate_generic_exception_500(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.side_effect = RuntimeError("boom")
        resp = client.post("/api/workflow-templates/tpl-1/instantiate", json={
            "workflow_name": "W"})
        assert resp.status_code == 500

    def test_instantiate_missing_name_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        resp = client.post("/api/workflow-templates/tpl-1/instantiate", json={})
        assert resp.status_code == 422


class TestTemplateImport:
    def test_import_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.get_template.return_value = _tpl(name="Imported T")
        client.manager.create_workflow_from_template.return_value = {
            "workflow_id": "wf-2", "workflow_name": "Imported T"}
        resp = client.post("/api/workflow-templates/tpl-1/import")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success" and body["workflow_id"] == "wf-2"

    def test_import_template_not_found_404(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.get_template.return_value = None
        resp = client.post("/api/workflow-templates/nope/import")
        assert resp.status_code == 404

    def test_import_value_error_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.get_template.return_value = _tpl()
        client.manager.create_workflow_from_template.side_effect = ValueError("bad")
        resp = client.post("/api/workflow-templates/tpl-1/import")
        assert resp.status_code == 422

    def test_import_generic_exception_500(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.get_template.return_value = _tpl()
        client.manager.create_workflow_from_template.side_effect = RuntimeError("boom")
        resp = client.post("/api/workflow-templates/tpl-1/import")
        assert resp.status_code == 500


class TestTemplateExecute:
    def test_execute_success(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.return_value = {
            "workflow_id": "wf-3", "workflow_definition": {"steps": []}}
        context = SimpleNamespace(workflow_id="wf-3", status=SimpleNamespace(value="completed"))
        orchestrator = MagicMock()
        orchestrator.execute_workflow = AsyncMock(return_value=context)
        with patch("api.workflow_template_routes.require_workflow_executor_definition",
                   new=AsyncMock()) as gate, \
                patch("advanced_workflow_orchestrator.get_orchestrator",
                      return_value=orchestrator):
            resp = client.post("/api/workflow-templates/tpl-1/execute")
        assert resp.status_code == 200
        body = resp.json()
        assert body["execution_id"] == "wf-3"
        assert body["workflow_status"] == "completed"
        gate.assert_awaited_once()
        orchestrator.execute_workflow.assert_awaited_once()

    def test_execute_with_parameters(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.return_value = {
            "workflow_id": "wf-4", "workflow_definition": {}}
        context = SimpleNamespace(workflow_id="wf-4", status=SimpleNamespace(value="running"))
        orchestrator = MagicMock()
        orchestrator.execute_workflow = AsyncMock(return_value=context)
        with patch("api.workflow_template_routes.require_workflow_executor_definition",
                   new=AsyncMock()), \
                patch("advanced_workflow_orchestrator.get_orchestrator",
                      return_value=orchestrator):
            resp = client.post("/api/workflow-templates/tpl-1/execute?parameters="
                               + '{"a":1}')
        assert resp.status_code == 200
        assert resp.json()["workflow_status"] == "running"

    def test_execute_value_error_template_not_found_404(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.side_effect = ValueError(
            "Template not found")
        resp = client.post("/api/workflow-templates/nope/execute")
        assert resp.status_code == 404

    def test_execute_value_error_other_422(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.side_effect = ValueError(
            "parameters invalid")
        resp = client.post("/api/workflow-templates/tpl-1/execute")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_execute_http_exception_re_raised_403(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.return_value = {
            "workflow_id": "wf-5", "workflow_definition": {"critical": True}}
        with patch("api.workflow_template_routes.require_workflow_executor_definition",
                   new=AsyncMock(side_effect=HTTPException(403, "WORKFLOW_MANAGE"))):
            resp = client.post("/api/workflow-templates/tpl-1/execute")
        assert resp.status_code == 403

    def test_execute_generic_exception_500(self, monkeypatch):
        client = _tpl_client(monkeypatch)
        client.manager.create_workflow_from_template.side_effect = RuntimeError("boom")
        resp = client.post("/api/workflow-templates/tpl-1/execute")
        assert resp.status_code == 500


# ============================================================================
# 7. api/workflow_versioning_endpoints.py
# ============================================================================
def _version(version="1.0.0"):
    return SimpleNamespace(
        workflow_id="wf-1",
        version=version,
        version_type=VersionType.MINOR,
        change_type=ChangeType.STRUCTURAL,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        created_by="user-1",
        commit_message="msg",
        tags=["t"],
        workflow_data={"steps": []},
        parent_version=None,
        branch_name="main",
        is_active=True,
        checksum="abc123",
        metadata={"meta": 1},
    )


def _branch():
    return SimpleNamespace(
        branch_name="feature",
        workflow_id="wf-1",
        base_version="1.0.0",
        current_version="1.1.0",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        created_by="user-1",
        is_protected=False,
        merge_strategy="merge_commit",
    )


@pytest.fixture
def versioning_client(admin_user, monkeypatch):
    vs = AsyncMock()
    vm = AsyncMock()
    monkeypatch.setattr("api.workflow_versioning_endpoints.versioning_system", vs)
    monkeypatch.setattr("api.workflow_versioning_endpoints.version_manager", vm)
    # Defensive: tests/unit/test_workflow_versioning_endpoints.py permanently
    # replaces router.success_response/not_found_error/validation_error with
    # MagicMocks on the shared BaseAPIRouter instance — restore the real ones.
    from core.base_routes import BaseAPIRouter

    for method in ("success_response", "not_found_error", "validation_error"):
        if not isinstance(getattr(versioning_router, method), type(
                getattr(BaseAPIRouter, method))):
            setattr(versioning_router, method,
                    getattr(BaseAPIRouter, method).__get__(versioning_router))
    client = _client(versioning_router, user=admin_user)
    client.versioning_system = vs
    client.version_manager = vm
    return client


class TestGetWorkflowData:
    @pytest.mark.asyncio
    async def test_missing_file(self):
        with patch("os.path.exists", return_value=False):
            data = await get_workflow_data("wf-1")
        assert data["steps"] == []

    @pytest.mark.asyncio
    async def test_workflow_not_found_in_file(self):
        content = '[{"id": "other", "steps": [{"id": "s"}]}]'
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data=content)):
            data = await get_workflow_data("wf-1")
        assert data["steps"] == []

    @pytest.mark.asyncio
    async def test_steps_passthrough(self):
        content = ('[{"id": "wf-1", "steps": [{"id": "s1"}], "parameters": {"p": 1},'
                   ' "name": "N", "description": "D", "category": "c",'
                   ' "created_at": "2026-01-01", "updated_at": "2026-01-02"}]')
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data=content)):
            data = await get_workflow_data("wf-1")
        assert data["steps"] == [{"id": "s1"}]
        assert data["metadata"]["name"] == "N"
        assert data["parameters"] == {"p": 1}

    @pytest.mark.asyncio
    async def test_nodes_to_steps_conversion(self):
        content = ('[{"id": "wf-1", "nodes": ['
                   '{"id": "n1", "title": "T1", "config": {"service": "s", "action": "a",'
                   ' "parameters": {"p": 1}}, "type": "action"},'
                   '{"id": "n2"}]}]')
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data=content)):
            data = await get_workflow_data("wf-1")
        assert len(data["steps"]) == 2
        assert data["steps"][0]["id"] == "n1"
        assert data["steps"][0]["sequence_order"] == 1
        assert data["steps"][0]["service"] == "s"
        assert data["steps"][1]["name"] == "n2"

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        with patch("os.path.exists", side_effect=RuntimeError("boom")):
            data = await get_workflow_data("wf-1")
        assert data["steps"] == []


class TestVersionCreate:
    def test_create_success(self, versioning_client):
        versioning_client.version_manager.create_workflow_version.return_value = {
            "version": "1.1.0"}
        versioning_client.versioning_system.get_version.return_value = _version("1.1.0")
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions", json={
            "version_type": "minor", "commit_message": "add feature"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "1.1.0"
        assert body["change_type"] == "structural"

    def test_create_version_not_found_500(self, versioning_client):
        versioning_client.version_manager.create_workflow_version.return_value = {
            "version": "1.1.0"}
        versioning_client.versioning_system.get_version.return_value = None
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions", json={
            "version_type": "patch", "commit_message": "fix"})
        assert resp.status_code == 500

    def test_create_exception_500(self, versioning_client):
        versioning_client.version_manager.create_workflow_version.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions", json={
            "version_type": "minor", "commit_message": "m"})
        assert resp.status_code == 500

    def test_create_invalid_version_type_422(self, versioning_client):
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions", json={
            "version_type": "bogus", "commit_message": "m"})
        assert resp.status_code == 422

    def test_create_missing_fields_422(self, versioning_client):
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions", json={})
        assert resp.status_code == 422

    def test_create_unauthenticated_401(self):
        assert _client(versioning_router).post(
            "/api/v1/workflows/wf-1/versions",
            json={"version_type": "minor", "commit_message": "m"}).status_code == 401


class TestGetVersions:
    def test_get_versions_success(self, versioning_client):
        versioning_client.versioning_system.get_version_history.return_value = [
            _version("1.1.0"), _version("1.0.0")]
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["version"] == "1.1.0"
        assert data[0]["parent_version"] is None

    def test_get_versions_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version_history.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions")
        assert resp.status_code == 500

    def test_get_versions_branch_and_limit_query(self, versioning_client):
        versioning_client.versioning_system.get_version_history.return_value = []
        resp = versioning_client.get(
            "/api/v1/workflows/wf-1/versions?branch_name=dev&limit=10")
        assert resp.status_code == 200
        versioning_client.versioning_system.get_version_history.assert_awaited_once_with(
            workflow_id="wf-1", branch_name="dev", limit=10)

    def test_get_versions_limit_bounds_422(self, versioning_client):
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions?limit=0")
        assert resp.status_code == 422


class TestCompareVersions:
    def test_compare_success(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = _version()
        changes = {
            "from_version": "1.0.0", "to_version": "1.1.0",
            "impact_level": "medium", "added_steps_count": 1,
            "removed_steps_count": 0, "modified_steps_count": 2,
            "structural_changes": ["added step"], "dependency_changes": [],
            "parametric_changes": {"p": (1, 2)}, "metadata_changes": {},
        }
        versioning_client.version_manager.get_workflow_changes.return_value = changes
        resp = versioning_client.get(
            "/api/v1/workflows/wf-1/versions/compare?from_version=1.0.0&to_version=1.1.0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["impact_level"] == "medium"
        assert body["added_steps_count"] == 1

    def test_compare_from_not_found_404(self, versioning_client):
        def fake_get_version(workflow_id, version):
            return _version() if version == "1.1.0" else None

        versioning_client.versioning_system.get_version.side_effect = fake_get_version
        resp = versioning_client.get(
            "/api/v1/workflows/wf-1/versions/compare?from_version=0.9.0&to_version=1.1.0")
        assert resp.status_code == 404

    def test_compare_to_not_found_404(self, versioning_client):
        def fake_get_version(workflow_id, version):
            return _version() if version == "1.0.0" else None

        versioning_client.versioning_system.get_version.side_effect = fake_get_version
        resp = versioning_client.get(
            "/api/v1/workflows/wf-1/versions/compare?from_version=1.0.0&to_version=9.9.9")
        assert resp.status_code == 404

    def test_compare_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = _version()
        versioning_client.version_manager.get_workflow_changes.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get(
            "/api/v1/workflows/wf-1/versions/compare?from_version=1.0.0&to_version=1.1.0")
        assert resp.status_code == 500

    def test_compare_missing_query_422(self, versioning_client):
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/compare")
        assert resp.status_code == 422


class TestLatestVersion:
    def test_latest_success(self, versioning_client):
        versioning_client.versioning_system.get_version_history.return_value = [
            _version("1.2.0")]
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/latest")
        assert resp.status_code == 200
        assert resp.json()["version"] == "1.2.0"

    def test_latest_empty_404(self, versioning_client):
        versioning_client.versioning_system.get_version_history.return_value = []
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/latest")
        assert resp.status_code == 404

    def test_latest_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version_history.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/latest")
        assert resp.status_code == 500


class TestVersionSummary:
    def test_summary_success(self, versioning_client):
        v1 = _version("1.0.0")
        v2 = _version("1.1.0")
        v2.version_type = VersionType.MAJOR
        v2.change_type = ChangeType.FEATURE
        v2.created_by = "user-2"
        versioning_client.versioning_system.get_version_history.return_value = [v2, v1]
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_versions"] == 2
        assert data["version_types"] == {"minor": 1, "major": 1}
        assert data["unique_contributors"] == 2
        assert data["latest_version"] == "1.1.0"
        assert data["oldest_version"] == "1.0.0"
        assert data["date_range"]["first_created"] is not None

    def test_summary_empty(self, versioning_client):
        versioning_client.versioning_system.get_version_history.return_value = []
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_versions"] == 0
        assert data["latest_version"] is None
        assert data["oldest_version"] is None
        assert data["date_range"] == {"first_created": None, "last_created": None}

    def test_summary_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version_history.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/summary")
        assert resp.status_code == 500


class TestGetVersion:
    def test_get_version_success(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = _version()
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/1.0.0")
        assert resp.status_code == 200
        assert resp.json()["version"] == "1.0.0"

    def test_get_version_not_found_404(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = None
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/9.9.9")
        assert resp.status_code == 404

    def test_get_version_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/1.0.0")
        assert resp.status_code == 500


class TestVersionData:
    def test_version_data_success(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = _version()
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/1.0.0/data")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["workflow_data"] == {"steps": []}
        assert data["checksum"] == "abc123"

    def test_version_data_not_found_404(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = None
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/9.9.9/data")
        assert resp.status_code == 404

    def test_version_data_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/1.0.0/data")
        assert resp.status_code == 500


class TestRollback:
    def test_rollback_success(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = _version()
        versioning_client.version_manager.rollback_workflow.return_value = {
            "rollback_version": "1.0.1", "target_version": "1.0.0",
            "created_at": "2026-01-02T00:00:00"}
        resp = versioning_client.post("/api/v1/workflows/wf-1/rollback", json={
            "target_version": "1.0.0", "rollback_reason": "bad release"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["rollback_version"] == "1.0.1"

    def test_rollback_target_not_found_404(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = None
        resp = versioning_client.post("/api/v1/workflows/wf-1/rollback", json={
            "target_version": "9.9.9", "rollback_reason": "r"})
        assert resp.status_code == 404

    def test_rollback_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version.return_value = _version()
        versioning_client.version_manager.rollback_workflow.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.post("/api/v1/workflows/wf-1/rollback", json={
            "target_version": "1.0.0", "rollback_reason": "r"})
        assert resp.status_code == 500

    def test_rollback_missing_fields_422(self, versioning_client):
        resp = versioning_client.post("/api/v1/workflows/wf-1/rollback", json={})
        assert resp.status_code == 422


class TestDeleteVersion:
    def test_delete_success(self, versioning_client):
        versioning_client.versioning_system.delete_version.return_value = True
        resp = versioning_client.delete(
            "/api/v1/workflows/wf-1/versions/1.0.0?delete_reason=cleanup")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Version 1.0.0 marked as deleted"

    def test_delete_failed_422(self, versioning_client):
        versioning_client.versioning_system.delete_version.return_value = False
        resp = versioning_client.delete(
            "/api/v1/workflows/wf-1/versions/1.0.0?delete_reason=cleanup")
        assert resp.status_code == 422

    def test_delete_exception_500(self, versioning_client):
        versioning_client.versioning_system.delete_version.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.delete(
            "/api/v1/workflows/wf-1/versions/1.0.0?delete_reason=cleanup")
        assert resp.status_code == 500

    def test_delete_missing_reason_422(self, versioning_client):
        resp = versioning_client.delete("/api/v1/workflows/wf-1/versions/1.0.0")
        assert resp.status_code == 422


class TestBranches:
    def test_create_branch_success(self, versioning_client):
        versioning_client.versioning_system.create_branch.return_value = _branch()
        resp = versioning_client.post("/api/v1/workflows/wf-1/branches", json={
            "branch_name": "feature", "base_version": "1.0.0"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["branch_name"] == "feature"
        assert body["merge_strategy"] == "merge_commit"

    def test_create_branch_exception_500(self, versioning_client):
        versioning_client.versioning_system.create_branch.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.post("/api/v1/workflows/wf-1/branches", json={
            "branch_name": "f", "base_version": "1.0.0"})
        assert resp.status_code == 500

    def test_create_branch_missing_fields_422(self, versioning_client):
        resp = versioning_client.post("/api/v1/workflows/wf-1/branches", json={})
        assert resp.status_code == 422

    def test_list_branches_success(self, versioning_client):
        versioning_client.versioning_system.get_branches.return_value = [
            _branch(), _branch()]
        resp = versioning_client.get("/api/v1/workflows/wf-1/branches")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_branches_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_branches.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get("/api/v1/workflows/wf-1/branches")
        assert resp.status_code == 500

    def test_merge_success(self, versioning_client):
        merged = SimpleNamespace(version="2.0.0",
                                 created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        versioning_client.versioning_system.merge_branch.return_value = merged
        resp = versioning_client.post("/api/v1/workflows/wf-1/branches/merge", json={
            "source_branch": "feature", "target_branch": "main",
            "merge_message": "merge it"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["merged_version"] == "2.0.0"

    def test_merge_exception_500(self, versioning_client):
        versioning_client.versioning_system.merge_branch.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.post("/api/v1/workflows/wf-1/branches/merge", json={
            "source_branch": "f", "target_branch": "m", "merge_message": "x"})
        assert resp.status_code == 500

    def test_merge_missing_fields_422(self, versioning_client):
        resp = versioning_client.post("/api/v1/workflows/wf-1/branches/merge", json={})
        assert resp.status_code == 422


class TestVersionMetrics:
    def test_get_metrics_success(self, versioning_client):
        versioning_client.versioning_system.get_version_metrics.return_value = {
            "avg_latency_ms": 100}
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/1.0.0/metrics")
        assert resp.status_code == 200
        assert resp.json()["data"]["metrics"]["avg_latency_ms"] == 100

    def test_get_metrics_empty(self, versioning_client):
        versioning_client.versioning_system.get_version_metrics.return_value = None
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/1.0.0/metrics")
        assert resp.status_code == 200
        assert resp.json()["data"]["metrics"] == {}

    def test_get_metrics_exception_500(self, versioning_client):
        versioning_client.versioning_system.get_version_metrics.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.get("/api/v1/workflows/wf-1/versions/1.0.0/metrics")
        assert resp.status_code == 500

    def test_update_metrics_success(self, versioning_client):
        versioning_client.versioning_system.update_version_metrics.return_value = True
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions/1.0.0/metrics",
                                      json={"success": True, "latency_ms": 50})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Metrics updated successfully"

    def test_update_metrics_failed(self, versioning_client):
        versioning_client.versioning_system.update_version_metrics.return_value = False
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions/1.0.0/metrics",
                                      json={"success": False})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Failed to update metrics"

    def test_update_metrics_exception_500(self, versioning_client):
        versioning_client.versioning_system.update_version_metrics.side_effect = \
            RuntimeError("boom")
        resp = versioning_client.post("/api/v1/workflows/wf-1/versions/1.0.0/metrics",
                                      json={"success": True})
        assert resp.status_code == 500


class TestVersioningHealth:
    def test_health_success(self, versioning_client):
        resp = versioning_client.get("/api/v1/workflows/versioning/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["versioning_system"] == "operational"

    def test_health_exception_503(self, versioning_client):
        with patch.object(versioning_router, "success_response",
                          side_effect=RuntimeError("boom")):
            resp = versioning_client.get("/api/v1/workflows/versioning/health")
        assert resp.status_code == 503
        assert resp.json()["detail"]["error"]["code"] == "VERSIONING_UNAVAILABLE"


class TestVersioningModels:
    def test_version_create_request_valid(self):
        r = VersionCreateRequest(version_type="hotfix", commit_message="m")
        assert r.tags is None and r.branch_name == "main"
        r2 = VersionCreateRequest(version_type="auto", commit_message="m",
                                  tags=["a"], branch_name="dev")
        assert r2.tags == ["a"] and r2.branch_name == "dev"

    def test_version_create_request_invalid_type(self):
        with pytest.raises(Exception):
            VersionCreateRequest(version_type="nope", commit_message="m")

    def test_rollback_request(self):
        r = RollbackRequest(target_version="1.0.0", rollback_reason="r")
        assert r.target_version == "1.0.0"
        with pytest.raises(Exception):
            RollbackRequest(target_version="1.0.0")

    def test_branch_create_request(self):
        r = BranchCreateRequest(branch_name="b", base_version="1.0.0")
        assert r.merge_strategy == "merge_commit"

    def test_merge_request(self):
        r = MergeRequest(source_branch="s", target_branch="t", merge_message="m")
        assert r.target_branch == "t"

    def test_version_diff_response(self):
        r = VersionDiffResponse(
            workflow_id="wf-1", from_version="1.0.0", to_version="1.1.0",
            impact_level="low", added_steps_count=1, removed_steps_count=0,
            modified_steps_count=0, structural_changes=[], dependency_changes=[],
            parametric_changes={}, metadata_changes={})
        assert r.impact_level == "low"


# ============================================================================
# 8. api/admin_routes.py
# ============================================================================
def _admin_model(**kw):
    a = MagicMock()
    a.id = kw.get("id", "adm-1")
    a.email = kw.get("email", "a@test.local")
    a.name = kw.get("name", "Admin One")
    a.role_id = kw.get("role_id", "role-1")
    a.role = MagicMock()
    a.role.name = kw.get("role_name", "Super Admin")
    a.role.permissions = kw.get("permissions", {"users": True})
    a.status = kw.get("status", "active")
    a.last_login = kw.get("last_login")
    a.created_at = kw.get("created_at")
    return a


def _role_model(**kw):
    r = MagicMock()
    r.id = kw.get("id", "role-1")
    r.name = kw.get("name", "Super Admin")
    r.permissions = kw.get("permissions", {"users": True})
    r.description = kw.get("description", "desc")
    return r


def _admin_client(admin_user, raise_exc=False):
    client = _client(admin_router, user=admin_user, mock_db=True,
                     raise_exc=raise_exc)

    def _refresh(obj):
        if getattr(obj, "id", None) is None:
            obj.id = "gen-id"

    client.app.db.refresh.side_effect = _refresh
    return client


class TestAdminUsers:
    def test_list_users_success(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.join.return_value.all.return_value = [
            _admin_model(), _admin_model(id="adm-2", role_name="Viewer",
                                         permissions={"users": False})]
        resp = client.get("/api/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["role_name"] == "Super Admin"
        assert data[0]["permissions"] == {"users": True}
        assert data[1]["permissions"] == {"users": False}

    def test_list_users_member_403(self, member_user):
        resp = _admin_client(member_user).get("/api/admin/users")
        assert resp.status_code == 403

    def test_list_users_401(self):
        resp = _client(admin_router, mock_db=True).get("/api/admin/users")
        assert resp.status_code == 401

    def test_get_user_success(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = \
            _admin_model(created_at=datetime(2026, 1, 1))
        resp = client.get("/api/admin/users/adm-1")
        assert resp.status_code == 200
        assert resp.json()["email"] == "a@test.local"

    def test_get_user_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.get("/api/admin/users/nope")
        assert resp.status_code == 404

    def test_create_user_success(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.side_effect = [
            _role_model(), None]
        with patch("core.auth.get_password_hash", return_value="hashed!"):
            resp = client.post("/api/admin/users", json={
                "email": "new@example.com", "name": "New", "password": "password1",
                "role_id": "role-1"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@example.com"
        assert body["status"] == "active"
        created = client.app.db.add.call_args[0][0]
        assert created.password_hash == "hashed!"
        client.app.db.commit.assert_called()

    def test_create_user_role_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.post("/api/admin/users", json={
            "email": "n@example.com", "name": "N", "password": "password1",
            "role_id": "no-role"})
        assert resp.status_code == 404

    def test_create_user_email_conflict_409(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.side_effect = [
            _role_model(), _admin_model()]
        resp = client.post("/api/admin/users", json={
            "email": "dup@example.com", "name": "N", "password": "password1",
            "role_id": "role-1"})
        assert resp.status_code == 409

    def test_create_user_invalid_email_422(self, admin_user):
        client = _admin_client(admin_user)
        resp = client.post("/api/admin/users", json={
            "email": "not-an-email", "name": "N", "password": "password1",
            "role_id": "role-1"})
        assert resp.status_code == 422

    def test_create_user_short_password_422(self, admin_user):
        client = _admin_client(admin_user)
        resp = client.post("/api/admin/users", json={
            "email": "a@b.com", "name": "N", "password": "short", "role_id": "r"})
        assert resp.status_code == 422

    def test_update_user_success(self, admin_user):
        client = _admin_client(admin_user)
        admin = _admin_model()
        client.app.db.query.return_value.filter.return_value.first.return_value = admin
        resp = client.patch("/api/admin/users/adm-1", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert admin.name == "Renamed"
        client.app.db.commit.assert_called()

    def test_update_user_with_role(self, admin_user):
        client = _admin_client(admin_user)
        admin = _admin_model()
        client.app.db.query.return_value.filter.return_value.first.side_effect = [
            admin, _role_model(id="role-2")]
        resp = client.patch("/api/admin/users/adm-1", json={"role_id": "role-2",
                                                            "status": "inactive"})
        assert resp.status_code == 200
        assert admin.role_id == "role-2"
        assert admin.status == "inactive"

    def test_update_user_bad_role_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.side_effect = [
            _admin_model(), None]
        resp = client.patch("/api/admin/users/adm-1", json={"role_id": "nope"})
        assert resp.status_code == 404

    def test_update_user_bad_status_422(self, admin_user):
        client = _admin_client(admin_user)
        resp = client.patch("/api/admin/users/adm-1", json={"status": "superadmin"})
        assert resp.status_code == 422

    def test_update_user_status_whitespace_normalized(self, admin_user):
        client = _admin_client(admin_user)
        admin = _admin_model()
        client.app.db.query.return_value.filter.return_value.first.return_value = admin
        resp = client.patch("/api/admin/users/adm-1", json={"status": "  ACTIVE "})
        assert resp.status_code == 200
        assert admin.status == "active"

    def test_update_user_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.patch("/api/admin/users/nope", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_user_success(self, admin_user):
        client = _admin_client(admin_user)
        admin = _admin_model()
        client.app.db.query.return_value.filter.return_value.first.return_value = admin
        resp = client.delete("/api/admin/users/adm-1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Admin user deleted successfully"
        client.app.db.delete.assert_called_once_with(admin)

    def test_delete_user_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.delete("/api/admin/users/nope")
        assert resp.status_code == 404

    def test_update_last_login_success(self, admin_user):
        client = _admin_client(admin_user)
        admin = _admin_model()
        client.app.db.query.return_value.filter.return_value.first.return_value = admin
        resp = client.patch("/api/admin/users/adm-1/last-login")
        assert resp.status_code == 200
        assert admin.last_login is not None
        client.app.db.commit.assert_called()

    def test_update_last_login_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.patch("/api/admin/users/nope/last-login")
        assert resp.status_code == 404

    def test_admin_user_validator_allowed_statuses(self):
        from api.admin_routes import UpdateAdminUserRequest

        assert UpdateAdminUserRequest(status="active").status == "active"
        assert UpdateAdminUserRequest(status="inactive").status == "inactive"
        assert UpdateAdminUserRequest().status is None
        assert UpdateAdminUserRequest(status=None).status is None
        assert UpdateAdminUserRequest(status="Active").status == "active"


class TestAdminRoles:
    def test_list_roles_success(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.all.return_value = [_role_model(), _role_model(id="r2")]
        resp = client.get("/api/admin/roles")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_role_success(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = \
            _role_model()
        resp = client.get("/api/admin/roles/role-1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Super Admin"

    def test_get_role_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.get("/api/admin/roles/nope")
        assert resp.status_code == 404

    def test_create_role_success(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.post("/api/admin/roles", json={
            "name": "Analyst", "permissions": {"reports": True}, "description": "d"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Analyst"
        assert body["permissions"] == {"reports": True}

    def test_create_role_conflict_409(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = \
            _role_model()
        resp = client.post("/api/admin/roles", json={
            "name": "Super Admin", "permissions": {}})
        assert resp.status_code == 409

    def test_create_role_missing_permissions_422(self, admin_user):
        client = _admin_client(admin_user)
        resp = client.post("/api/admin/roles", json={"name": "Analyst"})
        assert resp.status_code == 422

    def test_update_role_success(self, admin_user):
        client = _admin_client(admin_user)
        role = _role_model()
        client.app.db.query.return_value.filter.return_value.first.side_effect = [role, None]
        resp = client.patch("/api/admin/roles/role-1", json={
            "name": "Renamed", "permissions": {"x": True}, "description": "new"})
        assert resp.status_code == 200
        assert role.name == "Renamed"
        assert role.permissions == {"x": True}
        assert role.description == "new"

    def test_update_role_name_conflict_409(self, admin_user):
        client = _admin_client(admin_user)
        role = _role_model(name="Current")
        other = MagicMock()
        client.app.db.query.return_value.filter.return_value.first.side_effect = [role, other]
        resp = client.patch("/api/admin/roles/role-1", json={"name": "Taken"})
        assert resp.status_code == 409

    def test_update_role_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.patch("/api/admin/roles/nope", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_role_success(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = \
            _role_model()
        client.app.db.query.return_value.filter.return_value.count.return_value = 0
        resp = client.delete("/api/admin/roles/role-1")
        assert resp.status_code == 200
        client.app.db.delete.assert_called_once()

    def test_delete_role_in_use_409(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = \
            _role_model()
        client.app.db.query.return_value.filter.return_value.count.return_value = 2
        resp = client.delete("/api/admin/roles/role-1")
        assert resp.status_code == 409

    def test_delete_role_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.delete("/api/admin/roles/nope")
        assert resp.status_code == 404


class TestAdminWebSocket:
    def test_status_no_state(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.first.return_value = None
        resp = client.get("/api/admin/websocket/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is False
        assert body["reconnect_attempts"] == 0

    def test_status_with_state_full_dates(self, admin_user):
        client = _admin_client(admin_user)
        ws = MagicMock()
        ws.connected = True
        ws.last_connected_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ws.last_message_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        ws.reconnect_attempts = 3
        ws.consecutive_failures = 1
        ws.disconnect_reason = "timeout"
        ws.fallback_to_polling = True
        client.app.db.query.return_value.first.return_value = ws
        resp = client.get("/api/admin/websocket/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is True
        assert body["last_connected_at"] is not None
        assert body["fallback_to_polling"] is True

    def test_status_with_null_dates(self, admin_user):
        client = _admin_client(admin_user)
        ws = MagicMock()
        ws.connected = False
        ws.last_connected_at = None
        ws.last_message_at = None
        ws.reconnect_attempts = 0
        ws.consecutive_failures = 0
        ws.disconnect_reason = None
        ws.fallback_to_polling = False
        client.app.db.query.return_value.first.return_value = ws
        resp = client.get("/api/admin/websocket/status")
        assert resp.status_code == 200
        assert resp.json()["last_connected_at"] is None

    def test_reconnect_creates_state(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.first.return_value = None
        resp = client.post("/api/admin/websocket/reconnect")
        assert resp.status_code == 200
        assert resp.json()["reconnect_triggered"] is True
        client.app.db.add.assert_called_once()
        client.app.db.commit.assert_called()

    def test_reconnect_existing_state(self, admin_user):
        client = _admin_client(admin_user)
        ws = MagicMock()
        ws.reconnect_attempts = 5
        ws.consecutive_failures = 4
        ws.fallback_to_polling = True
        client.app.db.query.return_value.first.return_value = ws
        resp = client.post("/api/admin/websocket/reconnect")
        assert resp.status_code == 200
        assert ws.reconnect_attempts == 0
        assert ws.fallback_to_polling is False

    def test_disable_creates_state(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.first.return_value = None
        resp = client.post("/api/admin/websocket/disable")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["websocket_enabled"] is False
        created = client.app.db.add.call_args[0][0]
        assert created.websocket_enabled is False

    def test_disable_existing_state(self, admin_user):
        client = _admin_client(admin_user)
        ws = MagicMock()
        client.app.db.query.return_value.first.return_value = ws
        resp = client.post("/api/admin/websocket/disable")
        assert resp.status_code == 200
        assert ws.fallback_to_polling is True
        assert ws.websocket_enabled is False
        assert ws.disconnect_reason == "disabled_by_admin"

    def test_enable_creates_state(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.first.return_value = None
        resp = client.post("/api/admin/websocket/enable")
        assert resp.status_code == 200
        assert resp.json()["websocket_enabled"] is True
        created = client.app.db.add.call_args[0][0]
        assert created.websocket_enabled is True

    def test_enable_existing_state(self, admin_user):
        client = _admin_client(admin_user)
        ws = MagicMock()
        client.app.db.query.return_value.first.return_value = ws
        resp = client.post("/api/admin/websocket/enable")
        assert resp.status_code == 200
        assert ws.websocket_enabled is True
        assert ws.reconnect_attempts == 0

    def test_websocket_member_403(self, member_user):
        resp = _admin_client(member_user).get("/api/admin/websocket/status")
        assert resp.status_code == 403


class TestAdminRatingSync:
    def _sync_mocks(self, client, pending=2, result=None):
        import core.rating_sync_service as rss_mod
        import core.atom_saas_client as asc_mod

        with patch.object(rss_mod, "RatingSyncService") as svc_cls, \
                patch.object(asc_mod, "AtomSaaSClient"):
            sync = MagicMock()
            sync._sync_in_progress = False
            sync.get_pending_ratings.return_value = [{"id": 1}] * pending
            sync.sync_ratings = AsyncMock(return_value=result or {
                "success": True, "uploaded": 2, "failed": 0, "skipped": 1,
                "message": "done", "error": None})
            svc_cls.return_value = sync
            resp = client.post("/api/admin/sync/ratings", json={"upload_all": True})
        assert resp.status_code == 200
        return resp

    def test_sync_success(self, admin_user):
        client = _admin_client(admin_user)
        resp = self._sync_mocks(client)
        body = resp.json()
        assert body["success"] is True
        assert body["uploaded"] == 2
        assert body["pending_count"] == 2

    def test_sync_default_upload_all(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.rating_sync_service.RatingSyncService") as svc_cls, \
                patch("core.atom_saas_client.AtomSaaSClient"):
            sync = MagicMock()
            sync._sync_in_progress = False
            sync.get_pending_ratings.return_value = []
            sync.sync_ratings = AsyncMock(return_value={"success": True, "uploaded": 0})
            svc_cls.return_value = sync
            resp = client.post("/api/admin/sync/ratings", json={})
        assert resp.status_code == 200
        sync.sync_ratings.assert_awaited_once_with(upload_all=False)

    def test_sync_in_progress_503(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.rating_sync_service.RatingSyncService") as svc_cls, \
                patch("core.atom_saas_client.AtomSaaSClient"):
            sync = MagicMock()
            sync._sync_in_progress = True
            svc_cls.return_value = sync
            resp = client.post("/api/admin/sync/ratings", json={})
        assert resp.status_code == 503

    def test_failed_uploads_success(self, admin_user):
        client = _admin_client(admin_user)
        failed = MagicMock()
        failed.id = "f1"
        failed.rating_id = "r1"
        failed.error_message = "err"
        failed.failed_at = datetime(2026, 1, 1)
        failed.retry_count = 1
        failed.last_retry_at = None
        client.app.db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            failed]
        resp = client.get("/api/admin/ratings/failed-uploads")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["id"] == "f1"
        assert data[0]["last_retry_at"] is None

    def test_failed_uploads_empty(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        resp = client.get("/api/admin/ratings/failed-uploads")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_retry_success(self, admin_user):
        client = _admin_client(admin_user)
        failed = MagicMock()
        failed.id = "f1"
        failed.rating_id = "r1"
        client.app.db.query.return_value.filter.return_value.first.return_value = failed
        rating = MagicMock()
        rating.id = "r1"
        rating.retry_count = 0

        def _first():
            return rating

        client.app.db.query.return_value.filter.return_value.first.side_effect = [failed, rating]
        with patch("core.rating_sync_service.RatingSyncService") as svc_cls, \
                patch("core.atom_saas_client.AtomSaaSClient"):
            sync = MagicMock()
            sync.upload_rating = AsyncMock(
                return_value={"success": True, "rating_id": "remote-1"})
            svc_cls.return_value = sync
            resp = client.post("/api/admin/ratings/failed-uploads/f1/retry")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True and body["retry_triggered"] is True
        sync.mark_as_synced.assert_called_once_with("r1", "remote-1")
        client.app.db.delete.assert_called_once_with(failed)

    def test_retry_upload_fails_again(self, admin_user):
        client = _admin_client(admin_user)
        failed = MagicMock()
        failed.id = "f1"
        failed.rating_id = "r1"
        failed.retry_count = 0
        rating = MagicMock()
        rating.id = "r1"

        def _first():
            return rating

        client.app.db.query.return_value.filter.return_value.first.side_effect = [failed, rating]
        with patch("core.rating_sync_service.RatingSyncService") as svc_cls, \
                patch("core.atom_saas_client.AtomSaaSClient"):
            sync = MagicMock()
            sync.upload_rating = AsyncMock(return_value={"success": False, "error": "boom"})
            svc_cls.return_value = sync
            resp = client.post("/api/admin/ratings/failed-uploads/f1/retry")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert failed.retry_count == 1
        assert failed.error_message == "boom"

    def test_retry_rating_missing_removes_record(self, admin_user):
        client = _admin_client(admin_user)
        failed = MagicMock()
        failed.id = "f1"
        failed.rating_id = "gone"
        client.app.db.query.return_value.filter.return_value.first.side_effect = [failed, None]
        resp = client.post("/api/admin/ratings/failed-uploads/f1/retry")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "no longer exists" in body["message"]
        client.app.db.delete.assert_called_once_with(failed)

    def test_retry_failed_record_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        resp = client.post("/api/admin/ratings/failed-uploads/nope/retry")
        assert resp.status_code == 404

    def test_retry_member_403(self, member_user):
        resp = _admin_client(member_user).post("/api/admin/ratings/failed-uploads/f1/retry")
        assert resp.status_code == 403


class TestAdminConflicts:
    def _conflict_model(self):
        c = MagicMock()
        c.id = 1
        c.skill_id = "sk-1"
        c.conflict_type = "field_mismatch"
        c.severity = "high"
        c.local_data = {"a": 1}
        c.remote_data = {"a": 2}
        c.resolution_strategy = None
        c.resolved_data = None
        c.resolved_at = None
        c.resolved_by = None
        c.created_at = datetime(2026, 1, 1)
        return c

    def test_list_conflicts_success(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.count_unresolved_conflicts.return_value = 1
            resolver.get_unresolved_conflicts.return_value = [self._conflict_model()]
            crs.return_value = resolver
            resp = client.get("/api/admin/conflicts?severity=high&conflict_type=field_mismatch")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 1
        assert body["conflicts"][0]["severity"] == "high"
        resolver.count_unresolved_conflicts.assert_called_once_with(
            severity="high", conflict_type="field_mismatch")

    def test_list_conflicts_page_bounds(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.count_unresolved_conflicts.return_value = 0
            resolver.get_unresolved_conflicts.return_value = []
            crs.return_value = resolver
            resp = client.get("/api/admin/conflicts?page=0&page_size=999")
        assert resp.status_code == 200
        assert resp.json()["page"] == 1
        assert resp.json()["page_size"] == 200

    def test_get_conflict_success(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.get_conflict_by_id.return_value = self._conflict_model()
            crs.return_value = resolver
            resp = client.get("/api/admin/conflicts/1")
        assert resp.status_code == 200
        assert resp.json()["skill_id"] == "sk-1"

    def test_get_conflict_not_found_404(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.get_conflict_by_id.return_value = None
            crs.return_value = resolver
            resp = client.get("/api/admin/conflicts/99")
        assert resp.status_code == 404

    def test_resolve_conflict_success_with_cache(self, admin_user):
        client = _admin_client(admin_user)
        cache_row = MagicMock()
        client.app.db.query.return_value.filter.return_value.first.return_value = cache_row
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.resolve_conflict.return_value = {"skill_id": "sk-1", "data": "merged"}
            crs.return_value = resolver
            resp = client.post("/api/admin/conflicts/1/resolve", json={
                "strategy": "merge", "resolved_by": "admin-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert cache_row.skill_data == {"skill_id": "sk-1", "data": "merged"}
        assert cache_row.expires_at is not None
        client.app.db.commit.assert_called()

    def test_resolve_conflict_success_no_cache_row(self, admin_user):
        client = _admin_client(admin_user)
        client.app.db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.resolve_conflict.return_value = {"id": "sk-9", "data": "x"}
            crs.return_value = resolver
            resp = client.post("/api/admin/conflicts/1/resolve", json={
                "strategy": "local_wins", "resolved_by": "admin-1"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_resolve_conflict_failed(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.resolve_conflict.return_value = None
            crs.return_value = resolver
            resp = client.post("/api/admin/conflicts/1/resolve", json={
                "strategy": "merge", "resolved_by": "admin-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["message"] == "Failed to resolve conflict"

    def test_resolve_conflict_invalid_strategy_422(self, admin_user):
        client = _admin_client(admin_user)
        resp = client.post("/api/admin/conflicts/1/resolve", json={
            "strategy": "nuke", "resolved_by": "admin-1"})
        assert resp.status_code == 422

    def test_bulk_resolve_success(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()
            resolver.resolve_conflict.return_value = {"skill_id": "sk-1"}
            crs.return_value = resolver
            resp = client.post("/api/admin/conflicts/bulk-resolve", json={
                "conflict_ids": [1, 2, 3], "strategy": "remote_wins",
                "resolved_by": "admin-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved_count"] == 3
        assert body["failed_count"] == 0
        assert body["success"] is True

    def test_bulk_resolve_partial_failures(self, admin_user):
        client = _admin_client(admin_user)
        with patch("core.conflict_resolution_service.ConflictResolutionService") as crs:
            resolver = MagicMock()

            def _resolve(conflict_id, strategy, resolved_by):
                if conflict_id == 1:
                    return None
                if conflict_id == 2:
                    raise RuntimeError("boom")
                return {"skill_id": "sk-3"}

            resolver.resolve_conflict.side_effect = _resolve
            crs.return_value = resolver
            resp = client.post("/api/admin/conflicts/bulk-resolve", json={
                "conflict_ids": [1, 2, 3], "strategy": "merge",
                "resolved_by": "admin-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved_count"] == 1
        assert body["failed_count"] == 2
        assert body["success"] is False
        assert len(body["errors"]) == 2

    def test_bulk_resolve_invalid_strategy_422(self, admin_user):
        client = _admin_client(admin_user)
        resp = client.post("/api/admin/conflicts/bulk-resolve", json={
            "conflict_ids": [1], "strategy": "nuke", "resolved_by": "x"})
        assert resp.status_code == 422

    def test_bulk_resolve_empty_ids_422(self, admin_user):
        client = _admin_client(admin_user)
        resp = client.post("/api/admin/conflicts/bulk-resolve", json={
            "conflict_ids": [], "strategy": "merge", "resolved_by": "x"})
        assert resp.status_code == 422

    def test_conflicts_member_403(self, member_user):
        resp = _admin_client(member_user).get("/api/admin/conflicts")
        assert resp.status_code == 403
