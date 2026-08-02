"""
Round 72 — Workstream B: /learn endpoint (workflow→skill distillation).

Covers MementoEngine.analyze_execution / learn_from_execution plus the
POST /api/v1/learn route (success, missing execution → 404, unauth → 401,
and the registry listability of a distilled skill).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auto_dev.memento_engine import MementoEngine
from core.models import AgentExecution, AgentReasoningStep, SkillExecution, Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    """In-memory SQLite session with only the tables this test needs."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(
        engine,
        tables=[
            AgentExecution.__table__,
            AgentReasoningStep.__table__,
            SkillExecution.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    return Session(), engine


def _seed_execution(db, status="completed") -> str:
    """Insert an AgentExecution + reasoning steps; return the execution id."""
    execution = AgentExecution(
        agent_id="agent-1",
        tenant_id="tenant-1",
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
    @patch("core.auto_dev.memento_engine.MementoEngine.propose_code_change",
           new=AsyncMock(return_value="def summarize(x):\n    return x"))
    @patch("core.auto_dev.memento_engine.MementoEngine.validate_change",
           new=AsyncMock(return_value={"passed": True}))
    def test_success_writes_package_and_registers(self):
        db, _ = _make_session()
        exec_id = _seed_execution(db)

        engine = MementoEngine(db=db)

        with patch("core.skill_builder_service.SkillBuilderService") as MockBuilder, \
             patch("core.skill_registry_service.SkillRegistryService") as MockReg:
            MockBuilder.return_value.create_skill_package.return_value = {
                "success": True, "path": "/tmp/skill", "scripts": ["auto_summarize.py"]
            }
            MockReg.return_value.import_skill = AsyncMock(return_value={
                "skill_id": "s-1", "skill_name": "auto_summarize", "status": "Active"
            })

            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1",
                agent_id="agent-1",
                execution_id=exec_id,
            ))

        assert result["success"] is True
        assert result["execution_id"] == exec_id
        assert result["skill_name"].startswith("auto_")
        MockBuilder.return_value.create_skill_package.assert_called_once()
        MockReg.return_value.import_skill.assert_called_once()

    @patch("core.auto_dev.memento_engine.MementoEngine.propose_code_change",
           new=AsyncMock(return_value="def summarize(x):\n    return x"))
    @patch("core.auto_dev.memento_engine.MementoEngine.validate_change",
           new=AsyncMock(return_value={"passed": True}))
    def test_honors_skill_name_override(self):
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        engine = MementoEngine(db=db)

        with patch("core.skill_builder_service.SkillBuilderService") as MockBuilder, \
             patch("core.skill_registry_service.SkillRegistryService") as MockReg:
            MockBuilder.return_value.create_skill_package.return_value = {"success": True}
            MockReg.return_value.import_skill = AsyncMock(return_value={})
            result = asyncio_run(engine.learn_from_execution(
                tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
                skill_name="My Custom Skill",
            ))

        assert result["skill_name"] == "My Custom Skill"

    @patch("core.auto_dev.memento_engine.MementoEngine.propose_code_change",
           new=AsyncMock(return_value="def x():\n    return 1"))
    @patch("core.auto_dev.memento_engine.MementoEngine.validate_change",
           new=AsyncMock(return_value={"passed": False, "error": "sandbox"}))
    def test_validation_failure_returns_error(self):
        db, _ = _make_session()
        exec_id = _seed_execution(db)
        engine = MementoEngine(db=db)
        result = asyncio_run(engine.learn_from_execution(
            tenant_id="tenant-1", agent_id="agent-1", execution_id=exec_id,
        ))
        assert result["success"] is False
        assert "validation failed" in result["error"]

    def test_missing_execution_returns_error(self):
        db, _ = _make_session()
        engine = MementoEngine(db=db)
        result = asyncio_run(engine.learn_from_execution(
            tenant_id="tenant-1", agent_id="agent-1", execution_id="nope",
        ))
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestLearnRoute:
    def _client(self, db_session, monkeypatch):
        from fastapi.testclient import TestClient
        from main_api_app import app
        from core.auth import get_current_tenant, get_current_user
        from core.database import get_db
        import core.security_dependencies as sec_deps

        fake_user = MagicMock()
        fake_user.id = "user-1"
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

    def test_success_endpoint(self, db_session, monkeypatch):
        db_session.add(AgentExecution(id="e1", status="completed", input_summary="t"))
        db_session.commit()

        with patch.object(MementoEngine, "analyze_execution",
                          new=AsyncMock(return_value={
                              "execution_id": "e1", "task_description": "t",
                              "suggested_skill_name": "auto_learn", "failure_summary": "f",
                          })), \
             patch.object(MementoEngine, "propose_code_change",
                          new=AsyncMock(return_value="def learn():\n    return 1")), \
             patch.object(MementoEngine, "validate_change",
                          new=AsyncMock(return_value={"passed": True})), \
             patch("core.skill_builder_service.SkillBuilderService") as MockBuilder, \
             patch("core.skill_registry_service.SkillRegistryService") as MockReg:
            MockBuilder.return_value.create_skill_package.return_value = {"success": True}
            MockReg.return_value.import_skill = AsyncMock(return_value={
                "skill_id": "s-1", "skill_name": "auto_learn", "status": "Active"
            })

            client = self._client(db_session, monkeypatch)
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "e1"},
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["skill_name"] == "auto_learn"
        assert body["data"]["registry"]["skill_id"] == "s-1"

    def test_missing_execution_404(self, db_session, monkeypatch):
        with patch.object(MementoEngine, "analyze_execution",
                          new=AsyncMock(return_value={"error": "Execution nope not found"})):
            client = self._client(db_session, monkeypatch)
            resp = client.post(
                "/api/v1/learn",
                json={"execution_id": "nope"},
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 404, resp.text


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
