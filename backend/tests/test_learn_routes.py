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
    SkillExecution,
    UserRole,
    Base,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
        assert db.query(SkillCandidate).count() == 0


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
        from fastapi.testclient import TestClient
        from main_api_app import app
        from core.auth import get_current_tenant, get_current_user
        from core.database import get_db
        import core.security_dependencies as sec_deps

        fake_user = MagicMock()
        fake_user.id = "user-1"
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
