# -*- coding: utf-8 -*-
"""
Round 72 — Workstream B: /learn endpoint (workflow→skill distillation).

Covers MementoEngine.analyze_execution / learn_from_execution plus the
POST /api/v1/learn route.

2026-11 hardening contract: the execution lookup is tenant+owner scoped
(fail closed, authenticated actor) BEFORE any model/storage/sandbox
operation, and distillation stores a PENDING Auto-Dev SkillCandidate —
generated material is never executed, packaged or registered until a
supervisor approves it via the Auto-Dev review surface.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auto_dev.memento_engine import MementoEngine
from core.auto_dev.models import SkillCandidate
from core.models import (
    AgentExecution,
    AgentReasoningStep,
    AgentRegistry,
    Skill,
    SkillExecution,
    Tenant,
    UserRole,
    Workspace,
    Base,
    workspace_skills,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_mounted_app_overrides():
    """Keep per-test dependency overrides from leaking into other files."""
    import sys

    module = sys.modules.get("main_api_app")
    before = dict(module.app.dependency_overrides) if module else None
    yield
    if module is not None:
        module.app.dependency_overrides.clear()
        if before:
            module.app.dependency_overrides.update(before)


def _make_session():
    """In-memory SQLite session with only the tables this test needs."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            AgentExecution.__table__,
            AgentReasoningStep.__table__,
            AgentRegistry.__table__,
            SkillCandidate.__table__,
            SkillExecution.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    return Session(), engine


def _seed_agent(
    db, agent_id="agent-1", tenant_id="tenant-1", workspace_id="ws-1"
):
    """Insert the owning AgentRegistry row for an execution."""
    agent = AgentRegistry(
        id=agent_id,
        name="Test Agent",
        category="Operations",
        module_path="test.module",
        class_name="TestAgent",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    db.add(agent)
    db.commit()
    return agent


def _seed_execution(
    db,
    status="completed",
    agent_id="agent-1",
    tenant_id="tenant-1",
    exec_id=None,
) -> str:
    """Insert an AgentExecution + reasoning steps; return the execution id."""
    execution = AgentExecution(
        id=exec_id,
        agent_id=agent_id,
        tenant_id=tenant_id,
        status=status,
        input_summary="Summarize the quarterly sales report",
        result_summary="done",
    )
    db.add(execution)
    db.flush()

    db.add_all(
        [
            AgentReasoningStep(
                execution_id=execution.id,
                step_number=0,
                step_type="thought",
                thought="I should read the report",
            ),
            AgentReasoningStep(
                execution_id=execution.id,
                step_number=1,
                step_type="action",
                action={"tool": "read_codebase", "params": {"file_path": "q3.csv"}},
            ),
            AgentReasoningStep(
                execution_id=execution.id,
                step_number=2,
                step_type="observation",
                observation="rows=42",
                verified="verified",
            ),
        ]
    )
    db.commit()
    return execution.id


def _actor(role=UserRole.TEAM_LEAD, workspace_id="ws-1"):
    """Lightweight authenticated-actor stand-in (inert test data)."""
    return SimpleNamespace(id="user-1", role=role, workspace_id=workspace_id)


class TestMementoAnalyzeExecution:
    def test_builds_success_step_trace(self):
        db, _ = _make_session()
        exec_id = _seed_execution(db)

        engine = MementoEngine(db=db)
        result = asyncio_run(engine.analyze_execution(exec_id))

        assert "error" not in result  # success trace carries no error key
        assert result["execution_id"] == exec_id
        assert result["status"] == "completed"
        assert result["task_description"] == "Summarize the quarterly sales report"
        assert result["step_count"] == 3
        assert result["steps"][0]["step_type"] == "thought"
        assert result["tool_calls_attempted"] == [
            {"tool": "read_codebase", "params": {"file_path": "q3.csv"}}
        ]
        assert result["suggested_skill_name"].startswith("auto_")

    def test_missing_execution_returns_error(self):
        db, _ = _make_session()
        engine = MementoEngine(db=db)
        result = asyncio_run(engine.analyze_execution("nope"))
        assert "error" in result


class TestMementoLearnFromExecution:
    """Hardened contract: authorized lookup → pending candidate; the
    generated code is never executed, packaged or registered pre-approval."""

    def test_success_stores_pending_candidate_without_packaging(self):
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db)

        engine = MementoEngine(db=db)
        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
            new=AsyncMock(return_value="def summarize(x):\n    return x"),
        ) as mock_propose, patch(
            "core.skill_builder_service.SkillBuilderService"
        ) as MockBuilder, patch(
            "core.skill_registry_service.SkillRegistryService"
        ) as MockReg:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1",
                agent_id="agent-1",
                execution_id=exec_id,
                actor=_actor(role=UserRole.TEAM_LEAD, workspace_id="ws-1"),
            ))

        assert result["success"] is True, result
        assert result["status"] == "pending_approval"
        assert result["skill_name"].startswith("auto_")
        assert result["candidate_id"]

        candidate = (
            db.query(SkillCandidate)
            .filter(SkillCandidate.tenant_id == "tenant-1")
            .one()
        )
        assert candidate.validation_status == "pending"
        assert candidate.generated_code == "def summarize(x):\n    return x"
        assert candidate.agent_id == "agent-1"
        assert candidate.skill_name == result["skill_name"]

        # Unapproved generated material must not become runnable: no disk
        # package, no registry import, no sandbox execution on this path.
        MockBuilder.assert_not_called()
        MockReg.assert_not_called()
        mock_propose.assert_awaited_once()

    def test_honors_skill_name_override(self):
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db)
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
            new=AsyncMock(return_value="def x():\n    return 1"),
        ):
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                skill_name="My Custom Skill",
                actor=_actor(role=UserRole.TEAM_LEAD, workspace_id="ws-1"),
            ))

        assert result["success"] is True
        assert result["skill_name"] == "My Custom Skill"
        candidate = db.query(SkillCandidate).one()
        assert candidate.skill_name == "My Custom Skill"
        assert candidate.validation_status == "pending"

    def test_missing_execution_denies_before_llm(self):
        db, _ = _make_session()
        _seed_agent(db)
        engine = MementoEngine(db=db)
        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id="nope",
                actor=_actor(),
            ))
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["authorization"]["code"] == "not_found"
        assert result["authorization"]["http_status"] == 404
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_cross_tenant_execution_denied_before_llm(self):
        """Another tenant's execution id is indistinguishable from a missing
        one (404 semantics) and must never reach the LLM or storage."""
        db, _ = _make_session()
        exec_id = _seed_execution(db, tenant_id="tenant-2")
        _seed_agent(db, tenant_id="tenant-2", workspace_id="ws-9")
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.SUPER_ADMIN),
            ))
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["authorization"]["code"] == "not_found"
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_null_tenant_execution_denied(self):
        """Fail closed: a NULL-tenant execution can never match the
        authenticated tenant."""
        db, _ = _make_session()
        exec_id = _seed_execution(db, tenant_id=None)
        engine = MementoEngine(db=db)
        result = asyncio_run(engine.learn_from_execution(
            tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
            actor=_actor(role=UserRole.SUPER_ADMIN),
        ))
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["authorization"]["code"] == "not_found"
        assert db.query(SkillCandidate).count() == 0

    def test_execution_without_owning_agent_denied(self):
        """No owning agent → ownership cannot be established → deny."""
        db, _ = _make_session()
        exec_id = _seed_execution(db, agent_id=None)
        engine = MementoEngine(db=db)
        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.SUPER_ADMIN),
            ))
        assert result["success"] is False
        assert "not permitted" in result["error"].lower()
        assert result["authorization"]["code"] == "forbidden"
        assert result["authorization"]["http_status"] == 403
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_cross_workspace_actor_denied_before_llm(self):
        """Non-admin actor may only distill executions of agents their
        workspace owns (same policy as autodev_review_routes
        _candidate_agent)."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db, workspace_id="ws-1")
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.TEAM_LEAD, workspace_id="ws-2"),
            ))
        assert result["success"] is False
        assert "not permitted" in result["error"].lower()
        assert result["authorization"]["code"] == "forbidden"
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_admin_actor_may_operate_across_workspace(self):
        """Explicit tenant-admin policy (mirrors _candidate_agent): ADMIN+
        may distill within their tenant across workspaces."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db, workspace_id="ws-1")
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
            new=AsyncMock(return_value="def x():\n    return 1"),
        ):
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.ADMIN, workspace_id="ws-2"),
            ))
        assert result["success"] is True
        candidate = db.query(SkillCandidate).one()
        assert candidate.validation_status == "pending"

    def test_missing_owning_agent_row_denied(self):
        """Execution points at an agent id with no registry row (or a
        cross-tenant agent) → same answer as a missing execution."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        # No AgentRegistry row seeded at all.
        engine = MementoEngine(db=db)
        result = asyncio_run(engine.learn_from_execution(
            tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
            actor=_actor(role=UserRole.SUPER_ADMIN),
        ))
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["authorization"]["code"] == "not_found"
        assert db.query(SkillCandidate).count() == 0

    def test_blank_tenant_denied(self):
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db)
        engine = MementoEngine(db=db)
        result = asyncio_run(engine.learn_from_execution(
            tenant_id="", agent_id="agent-1", execution_id=exec_id,
            actor=_actor(),
        ))
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["authorization"]["code"] == "not_found"
        assert db.query(SkillCandidate).count() == 0

    def test_missing_actor_denied_before_storage_access(self):
        """Authenticated actor context is REQUIRED at the service boundary:
        a missing/anonymous actor is denied before any DB model or storage
        lookup."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db)
        engine = MementoEngine(db=db)

        with patch.object(
            db, "query", side_effect=AssertionError("storage accessed")
        ), patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=None,
            ))

        assert result["success"] is False
        assert result["authorization"]["code"] == "unauthenticated"
        assert result["authorization"]["http_status"] == 403
        mock_propose.assert_not_awaited()

    def test_non_admin_blank_actor_workspace_denied(self):
        """A populated owner scope cannot be claimed by an actor with no
        workspace scope."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db, workspace_id="ws-1")
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.TEAM_LEAD, workspace_id=""),
            ))

        assert result["success"] is False
        assert result["authorization"]["code"] == "forbidden"
        assert "unpopulated workspace" in result["authorization"]["message"]
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_non_admin_blank_owner_workspace_denied(self):
        """An owner with no workspace scope cannot be distilled by a
        non-admin actor, even one that has a workspace."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db, workspace_id="")
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.TEAM_LEAD, workspace_id="ws-1"),
            ))

        assert result["success"] is False
        assert result["authorization"]["code"] == "forbidden"
        assert "unpopulated workspace" in result["authorization"]["message"]
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_non_admin_blank_scopes_do_not_collide(self):
        """Regression: two empty scopes compare equal; that must NOT be
        treated as ownership. Both sides must be populated."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db, workspace_id="")
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
        ) as mock_propose:
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.MEMBER, workspace_id=""),
            ))

        assert result["success"] is False
        assert result["authorization"]["code"] == "forbidden"
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_admin_may_operate_with_blank_workspace_scopes(self):
        """ADMIN+ is the explicit tenant-admin policy: workspace scope is
        not part of the decision for them."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db, workspace_id="")
        engine = MementoEngine(db=db)

        with patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
            new=AsyncMock(return_value="def x():\n    return 1"),
        ):
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(role=UserRole.ADMIN, workspace_id=""),
            ))

        assert result["success"] is True
        assert db.query(SkillCandidate).one().validation_status == "pending"

    def test_analyzes_already_authorized_row_without_second_lookup(self):
        """The distillation path must analyze the row returned by the
        authorized lookup, not re-fetch it through the unscoped
        ``analyze_execution`` helper."""
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        _seed_agent(db)
        engine = MementoEngine(db=db)

        with patch.object(
            MementoEngine, "analyze_execution",
            side_effect=AssertionError("second unscoped lookup"),
        ), patch(
            "core.auto_dev.memento_engine.MementoEngine.propose_code_change",
            new=AsyncMock(return_value="def x():\n    return 1"),
        ):
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                actor=_actor(),
            ))

        assert result["success"] is True
        candidate = db.query(SkillCandidate).one()
        assert candidate.failure_pattern["execution_id"] == exec_id
        assert candidate.failure_pattern["step_count"] == 3


def _mounted_client(db_session, monkeypatch, role=UserRole.SUPER_ADMIN,
                    workspace_id="ws-1", user_id="user-1"):
    """Full mounted app with authenticated actor/tenant/DB overrides."""
    from fastapi.testclient import TestClient
    from main_api_app import app
    from core.auth import get_current_tenant, get_current_user
    from core.database import get_db
    import core.security_dependencies as sec_deps

    fake_user = MagicMock()
    fake_user.id = user_id
    fake_user.role = role
    fake_user.workspace_id = workspace_id
    fake_tenant = MagicMock()
    fake_tenant.id = "tenant-1"

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_current_tenant] = lambda: fake_tenant
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(
        sec_deps.RBACService, "check_permission", staticmethod(lambda u, p: True)
    )
    return TestClient(app)


class TestLearnRoute:
    """Route-level: authorized behavior + denial mapping after the fix."""

    def _memory_db(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            engine,
            tables=[
                AgentExecution.__table__,
                AgentReasoningStep.__table__,
                AgentRegistry.__table__,
                SkillCandidate.__table__,
            ],
        )
        Session = sessionmaker(bind=engine)
        return Session()

    def _client(self, db_session, monkeypatch, role=UserRole.SUPER_ADMIN,
                workspace_id="ws-1"):
        return _mounted_client(
            db_session, monkeypatch, role=role, workspace_id=workspace_id
        )

    def test_401_unauth(self):
        from fastapi.testclient import TestClient
        from main_api_app import app
        client = TestClient(app)
        resp = client.post("/api/v1/learn", json={"execution_id": "e1"})
        assert resp.status_code in (401, 403)

    def test_success_stores_pending_candidate(self, monkeypatch):
        db = self._memory_db()
        _seed_agent(db)
        _seed_execution(db, exec_id="e1")

        with patch.object(MementoEngine, "propose_code_change",
                          new=AsyncMock(return_value="def learn():\n    return 1")), \
             patch("core.skill_builder_service.SkillBuilderService") as MockBuilder, \
             patch("core.skill_registry_service.SkillRegistryService") as MockReg:
            client = self._client(db, monkeypatch)
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "e1"},
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "pending_approval"
        assert body["data"]["candidate_id"]
        assert body["data"]["skill_name"].startswith("auto_")
        candidate = (
            db.query(SkillCandidate)
            .filter(SkillCandidate.tenant_id == "tenant-1")
            .one()
        )
        assert candidate.validation_status == "pending"
        assert candidate.agent_id == "agent-1"
        # Unapproved generated material must not become runnable.
        MockBuilder.assert_not_called()
        MockReg.assert_not_called()

    def test_missing_execution_404(self, monkeypatch):
        db = self._memory_db()
        _seed_agent(db)
        client = self._client(db, monkeypatch)
        resp = client.post(
            "/api/v1/learn",
            json={"execution_id": "nope"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 404, resp.text
        assert db.query(SkillCandidate).count() == 0

    def test_cross_tenant_execution_404(self, monkeypatch):
        """Another tenant's execution is denied (indistinguishable from
        missing) and never reaches the LLM."""
        db = self._memory_db()
        _seed_agent(db, tenant_id="tenant-2", workspace_id="ws-9")
        _seed_execution(db, tenant_id="tenant-2", exec_id="e1")

        with patch.object(MementoEngine, "propose_code_change",
                          new=AsyncMock(return_value="def x():\n    return 1")):
            client = self._client(db, monkeypatch)
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "e1"},
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 404, resp.text
        assert db.query(SkillCandidate).count() == 0

    def test_cross_workspace_403_and_no_candidate(self, monkeypatch):
        """Non-admin actor distilling another workspace's execution → 403,
        no LLM work, no candidate."""
        db = self._memory_db()
        _seed_agent(db, workspace_id="ws-1")
        _seed_execution(db, exec_id="e1")

        with patch.object(MementoEngine, "propose_code_change",
                          new=AsyncMock(return_value="def x():\n    return 1")) as mock_propose:
            client = self._client(
                db, monkeypatch, role=UserRole.TEAM_LEAD, workspace_id="ws-2"
            )
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "e1"},
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 403, resp.text
        assert "not permitted" in resp.json()["detail"].lower()
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_non_admin_blank_workspace_403(self, monkeypatch):
        """Unpopulated actor scope on the route is a policy denial (403)."""
        db = self._memory_db()
        _seed_agent(db, workspace_id="ws-1")
        _seed_execution(db, exec_id="e1")

        with patch.object(MementoEngine, "propose_code_change",
                          new=AsyncMock(return_value="def x():\n    return 1")) as mock_propose:
            client = self._client(
                db, monkeypatch, role=UserRole.TEAM_LEAD, workspace_id=""
            )
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "e1"},
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 403, resp.text
        mock_propose.assert_not_awaited()
        assert db.query(SkillCandidate).count() == 0

    def test_route_uses_structured_outcome_not_error_text(self, monkeypatch):
        """A forbidden outcome whose text happens to say "not found" must
        still map 403 — the route may not infer policy from message text."""
        db = self._memory_db()
        client = self._client(db, monkeypatch)
        denial = {
            "allowed": False,
            "code": "forbidden",
            "http_status": 403,
            "message": "workspace policy denied",
        }
        with patch.object(
            MementoEngine, "learn_from_execution",
            new=AsyncMock(return_value={
                "success": False,
                "error": "Execution e1 not found",
                "authorization": denial,
            }),
        ):
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "e1"},
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"] == "workspace policy denied"

    def test_route_uses_not_found_outcome_despite_policy_text(self, monkeypatch):
        """Inverse: a not_found outcome whose text says "not permitted"
        maps 404, again proving code-based mapping."""
        db = self._memory_db()
        client = self._client(db, monkeypatch)
        denial = {
            "allowed": False,
            "code": "not_found",
            "http_status": 404,
            "message": "Execution e1 not found",
        }
        with patch.object(
            MementoEngine, "learn_from_execution",
            new=AsyncMock(return_value={
                "success": False,
                "error": "distillation not permitted",
                "authorization": denial,
            }),
        ):
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "e1"},
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 404, resp.text


class TestLearnReviewApplyChain:
    """The mounted learn → approve → apply chain on scratch storage.

    Unapproved material must stay pending and unusable; after explicit
    review+apply the only persisted skill artifact is the supported typed
    prompt skill (SKILL.md), never the generated executable code.
    """

    GENERATED = (
        "def inert_generated_marker():\n"
        "    return 'INERT_GENERATED_CODE_MARKER'\n"
    )

    def _chain_db(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            engine,
            tables=[
                Tenant.__table__,
                Workspace.__table__,
                AgentExecution.__table__,
                AgentReasoningStep.__table__,
                AgentRegistry.__table__,
                SkillCandidate.__table__,
                SkillExecution.__table__,
                Skill.__table__,
                workspace_skills,
            ],
        )
        Session = sessionmaker(bind=engine)
        return Session()

    def _seed_chain(self, db):
        db.add(Tenant(id="tenant-1", name="Tenant One", subdomain="chain-one"))
        db.add(Workspace(id="ws-1", name="Workspace One", tenant_id="tenant-1"))
        db.add(AgentRegistry(
            id="agent-chain", name="Chain Agent", category="Operations",
            module_path="test.chain", class_name="ChainAgent",
            tenant_id="tenant-1", workspace_id="ws-1",
        ))
        db.add(AgentExecution(
            id="chain-exec", agent_id="agent-chain", tenant_id="tenant-1",
            status="completed", input_summary="Inert fixture task",
            result_summary="done",
        ))
        db.commit()

    def test_pending_is_unavailable_then_approved_apply_persists_prompt_only(
        self, tmp_path, monkeypatch
    ):
        store = tmp_path / "scratch-skill-store"
        monkeypatch.setenv("ATOM_WORKSPACE_SKILLS_ROOT", str(store))
        db = self._chain_db()
        self._seed_chain(db)
        client = _mounted_client(
            db, monkeypatch, role=UserRole.TEAM_LEAD, workspace_id="ws-1"
        )

        with patch.object(
            MementoEngine, "propose_code_change",
            new=AsyncMock(return_value=self.GENERATED),
        ):
            learned = client.post(
                "/api/v1/learn", json={"execution_id": "chain-exec"})
            assert learned.status_code == 200, learned.text
            candidate_id = learned.json()["data"]["candidate_id"]
            assert learned.json()["data"]["status"] == "pending_approval"

            # 1. Pending is not permission: apply is refused and nothing
            #    runnable is written.
            refused = client.post(
                f"/api/autodev/skills/{candidate_id}/apply")
            assert refused.status_code == 409, refused.text
            assert "candidate_not_reviewed" in refused.text

            db.expire_all()
            assert db.query(Skill).count() == 0
            assert db.query(SkillExecution).count() == 0
            assert not store.exists() or not list(store.rglob("*"))

            # 2. Explicit review, then explicit apply.
            approved = client.post(
                f"/api/autodev/skills/{candidate_id}/approve")
            assert approved.status_code == 200, approved.text
            applied = client.post(
                f"/api/autodev/skills/{candidate_id}/apply")
            assert applied.status_code == 200, applied.text

        data = applied.json()["data"]
        assert data["status"] == "promoted"
        assert data["generated_code_applied"] is False

        db.expire_all()
        skills = db.query(Skill).all()
        assert len(skills) == 1
        skill = skills[0]
        # Only the supported typed prompt skill is persisted.
        assert skill.type == "prompt"
        assert self.GENERATED.strip() not in (skill.long_description or "")
        assert "INERT_GENERATED_CODE_MARKER" not in str(skill.config)
        assert (
            db.query(workspace_skills)
            .filter(workspace_skills.c.skill_id == skill.id)
            .count()
            == 1
        )
        candidate = (
            db.query(SkillCandidate)
            .filter(SkillCandidate.id == candidate_id)
            .one()
        )
        assert candidate.validation_status == "promoted"

        files = [p for p in store.rglob("*") if p.is_file()]
        assert [p.name for p in files] == ["SKILL.md"]
        markdown = files[0].read_text(encoding="utf-8")
        assert "INERT_GENERATED_CODE_MARKER" not in markdown
        assert "## Instructions" in markdown
        assert not list(store.rglob("*.py"))


class TestRegistryListability:
    """A distilled skill becomes listable via SkillRegistryService.list_skills."""

    @pytest.mark.asyncio
    async def test_imported_skill_is_listable(self):
        db, _ = _make_session()
        from core.skill_registry_service import SkillRegistryService

        content = (
            "---\n"
            "name: auto_sales_reporter\n"
            "description: Summarize sales reports\n"
            "---\n\n"
            "# auto_sales_reporter\n\n"
            "```python\n"
            "def summarize(x):\n"
            "    return x\n"
            "```\n"
        )
        registry = SkillRegistryService(db)
        result = await registry.import_skill(
            source="raw_content", content=content,
            metadata={"imported_by": "test"},
        )
        assert result.get("skill_id")

        listed = registry.list_skills()
        names = [s["skill_name"] for s in listed]
        assert "auto_sales_reporter" in names


def asyncio_run(coro):
    """Run an async method from a sync test."""
    import asyncio
    return asyncio.run(coro)
