"""Coverage wave 35 — core/workflow_ui_endpoints.py routes (TDD, mocked db/auth).

Drives the full workflow UI surface in both mock and DB modes: templates
list/filter/import, services, definitions, workflow CRUD, execute-by-id
(gated), history, executions (orchestrator contexts + persisted merge),
the /execute mock-bridge (template → orchestrator definition mapping),
cancel (mock/db/orchestrator/404), and the debug/state endpoint — zero
LLM, zero network, zero spend.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.workflow_ui_endpoints import (
    MOCK_EXECUTIONS,
    MOCK_TEMPLATES,
    MOCK_WORKFLOWS,
    WorkflowDefinition,
    WorkflowExecution,
    cancel_execution,
    create_workflow,
    create_workflow_definition,
    delete_workflow,
    execute_workflow,
    execute_workflow_by_id,
    get_executions,
    get_orchestrator_state,
    get_services,
    get_templates,
    get_workflow_by_id,
    get_workflow_history,
    get_workflows,
    import_template,
    list_workflows,
    update_workflow,
)


def make_template(**kw):
    defaults = dict(
        id="tpl-1", template_id="tpl-1", tenant_id="t-1", name="T", description="d",
        category="automation", complexity="beginner", tags=[],
        is_public=True, icon="icon", steps=[], input_schema={},
        steps_schema=[], inputs_schema={}, output_schema={},
        template_json={}, rating=4.5, usage_count=10, author_id="u1",
        version="1.0", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc))
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_db(template=None, rows=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = template
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = rows or []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = rows or []
    db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = rows or []
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.delete = MagicMock()
    db.close = MagicMock()
    return db


def patch_mock_flag(value=True):
    return patch("core.workflow_ui_endpoints.WORKFLOW_MOCK_ENABLED", value)


def patch_db(db):
    return patch("core.workflow_ui_endpoints.get_db", return_value=iter([db]))


class TestTemplates:
    async def test_mock_mode(self):
        with patch_mock_flag(True):
            result = await get_templates(db=None)
        assert result["success"] is True
        assert result["count"] == len(MOCK_TEMPLATES)

    async def test_db_mode(self):
        with patch_mock_flag(False):
            db = make_db(rows=[make_template()])
            query = db.query.return_value.filter.return_value
            query.order_by.return_value.limit.return_value.all.return_value = [make_template()]
            with patch_db(db):
                result = await get_templates(db=db)
        assert result["count"] == 1
        assert result["templates"][0]["name"] == "T"

    async def test_db_mode_category_filter(self):
        with patch_mock_flag(False):
            db = make_db(rows=[make_template()])
            with patch_db(db):
                result = await get_templates(category="automation", db=db)
        assert result["count"] == 1
        assert result["templates"][0]["name"] == "T"

    async def test_import_mock_found(self):
        with patch_mock_flag(True):
            result = await import_template("tpl_marketing_campaign", db=None)
        assert result["success"] is True
        assert result["workflow_id"].startswith("imported_")

    async def test_import_mock_missing(self):
        with patch_mock_flag(True):
            with pytest.raises(Exception) as exc:
                await import_template("ghost", db=None)
        assert exc.value.status_code == 404

    async def test_import_db_success(self):
        with patch_mock_flag(False):
            source = make_template()
            db = make_db(template=source)
            with patch_db(db), \
                 patch("core.workflow_ui_endpoints.WorkflowTemplate",
                       MagicMock(return_value=make_template(id="new-1"))):
                result = await import_template("tpl-1", db=db)
        assert result["success"] is True
        assert result["workflow_id"] == "new-1"
        assert source.usage_count == 11
        db.add.assert_called_once()

    async def test_import_db_missing(self):
        with patch_mock_flag(False):
            db = make_db(template=None)
            with patch_db(db):
                with pytest.raises(Exception) as exc:
                    await import_template("ghost", db=db)
        assert exc.value.status_code == 404

class TestDefinitionsAndWorkflows:
    async def test_get_services(self):
        result = await get_services()
        assert result["success"] is True
        assert "asana" in result["services"][0]["name"].lower() or len(result["services"]) > 5

    async def test_get_workflows_mock(self):
        with patch_mock_flag(True):
            result = await get_workflows(db=None)
        assert result["success"] is True
        assert len(result["workflows"]) == len(MOCK_WORKFLOWS)

    async def test_get_workflows_db(self):
        with patch_mock_flag(False):
            tpl = make_template(id="tpl-9")
            db = make_db(rows=[tpl])
            with patch_db(db):
                result = await get_workflows(limit=10, offset=0, db=db)
        assert result["count"] == 1
        assert result["workflows"][0]["id"] == "tpl-9"

    async def test_list_workflows_alias(self):
        with patch_mock_flag(True):
            result = await list_workflows(db=None)
        assert result["success"] is True

    async def test_get_workflow_by_id_mock_found(self):
        with patch_mock_flag(True):
            result = await get_workflow_by_id("wf_1", db=None)
        assert result["success"] is True
        assert result["workflow"]["id"] == "wf_1"

    async def test_get_workflow_by_id_mock_missing(self):
        with patch_mock_flag(True):
            with pytest.raises(Exception) as exc:
                await get_workflow_by_id("ghost", db=None)
        assert exc.value.status_code == 404

    async def test_get_workflow_by_id_db(self):
        with patch_mock_flag(False):
            tpl = make_template(id="w-1")
            db = make_db(template=tpl)
            with patch_db(db):
                result = await get_workflow_by_id("w-1", db=db)
        assert result["success"] is True
        assert result["workflow"]["id"] == "w-1"

    async def test_get_workflow_by_id_db_missing(self):
        with patch_mock_flag(False):
            db = make_db(template=None)
            with patch_db(db):
                with pytest.raises(Exception) as exc:
                    await get_workflow_by_id("ghost", db=db)
        assert exc.value.status_code == 404

    async def test_create_workflow_mock(self):
        with patch_mock_flag(True):
            result = await create_workflow({"name": "N", "steps": [{"id": "s1"}]}, db=None)
        assert result["success"] is True
        assert result["workflow"]["steps_count"] == 1
        assert MOCK_WORKFLOWS[0].id == result["workflow"]["id"]

    async def test_create_workflow_db(self):
        with patch_mock_flag(False):
            db = make_db()
            with patch_db(db), \
                 patch("core.workflow_ui_endpoints.WorkflowTemplate",
                       lambda **kw: make_template(**kw)):
                result = await create_workflow({"name": "N"}, author_id="u1", db=db)
        assert result["success"] is True
        assert result["workflow"]["name"] == "N"
        db.add.assert_called_once()

    async def test_update_workflow_mock(self):
        with patch_mock_flag(True):
            result = await update_workflow("wf_1", {"name": "Renamed"}, db=None)
            assert result["success"] is True
            assert result["workflow"]["name"] == "Renamed"
            with pytest.raises(Exception) as exc:
                await update_workflow("ghost", {}, db=None)
            assert exc.value.status_code == 404

    async def test_update_workflow_db(self):
        with patch_mock_flag(False):
            tpl = make_template(template_id="tpl-1")
            db = make_db(template=tpl)
            with patch_db(db):
                result = await update_workflow(
                    "tpl-1", {"name": "X", "category": "ops", "is_public": False,
                              "steps": [{"id": "s"}], "input_schema": {},
                              "output_schema": {}, "tags": ["a"], "complexity": "advanced",
                              "description": "d2"}, db=db)
        assert result["success"] is True
        assert tpl.name == "X"

    async def test_update_workflow_db_missing(self):
        with patch_mock_flag(False):
            db = make_db(template=None)
            with patch_db(db):
                with pytest.raises(Exception) as exc:
                    await update_workflow("ghost", {}, db=db)
        assert exc.value.status_code == 404

    async def test_delete_workflow_mock(self):
        with patch_mock_flag(True):
            result = await delete_workflow("wf_1", db=None)
            assert result["success"] is True
            with pytest.raises(Exception) as exc:
                await delete_workflow("ghost", db=None)
            assert exc.value.status_code == 404

    async def test_delete_workflow_db(self):
        with patch_mock_flag(False):
            tpl = make_template()
            db = make_db(template=tpl)
            with patch_db(db):
                result = await delete_workflow("tpl-1", db=db)
        assert result["success"] is True
        db.delete.assert_called_once()

    async def test_create_workflow_definition(self):
        with patch_mock_flag(True):
            result = await create_workflow_definition(
                {"name": "V", "definition": {"nodes": [{"id": "n1"}, {"id": "n2"}]}})
        assert result["success"] is True
        assert result["workflow"]["steps_count"] == 2


class TestExecute:
    async def test_execute_workflow_by_id(self):
        orchestrator = MagicMock()
        orchestrator.execute_workflow = AsyncMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                   new=AsyncMock()) as gate:
            bt = MagicMock()
            result = await execute_workflow_by_id(
                "wf-1", bt, {"x": 1}, current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert result["execution_id"].startswith("exec_")
        gate.assert_called_once()
        bt.add_task.assert_called_once()

    async def test_execute_workflow_bridge(self):
        orchestrator = MagicMock()
        orchestrator.workflows = {}
        orchestrator.active_contexts = {}
        orchestrator.execute_workflow = AsyncMock()

        class _WorkflowContext:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)

        class _WorkflowDefinition:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)

        class _WorkflowStep:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)

        class _StepType:
            UNIVERSAL_INTEGRATION = "ui"
            NLU_ANALYSIS = "nlu"
            SLACK_NOTIFICATION = "slack"
            EMAIL_SEND = "email"
            DELAY = "delay"

        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                   new=AsyncMock()), \
             patch("advanced_workflow_orchestrator.WorkflowContext", _WorkflowContext), \
             patch("advanced_workflow_orchestrator.WorkflowDefinition", _WorkflowDefinition), \
             patch("advanced_workflow_orchestrator.WorkflowStep", _WorkflowStep), \
             patch("advanced_workflow_orchestrator.WorkflowStatus",
                   SimpleNamespace(PENDING="pending", FAILED="failed")), \
             patch("advanced_workflow_orchestrator.WorkflowStepType", _StepType):
            bt = MagicMock()
            result = await execute_workflow(
                {"workflow_id": "tpl_marketing_campaign", "input": {"product": "X"}},
                bt, current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert "tpl_marketing_campaign" in orchestrator.workflows
        assert result["total_steps"] == 3
        bt.add_task.assert_called_once()

    async def test_execute_workflow_known_id(self):
        orchestrator = MagicMock()
        orchestrator.workflows = {"wf-real": MagicMock(steps=[1, 2, 3])}
        orchestrator.active_contexts = {}
        orchestrator.execute_workflow = AsyncMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                   new=AsyncMock()), \
             patch("advanced_workflow_orchestrator.WorkflowContext",
                   lambda **kw: SimpleNamespace(**kw, status="pending",
                                               started_at=datetime.now())), \
             patch("advanced_workflow_orchestrator.WorkflowStatus",
                   SimpleNamespace(PENDING="pending", FAILED="failed")):
            bt = MagicMock()
            result = await execute_workflow(
                {"workflow_id": "wf-real", "input": {}}, bt,
                current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert result["total_steps"] == 3

    async def test_execute_workflow_not_found(self):
        orchestrator = MagicMock()
        orchestrator.workflows = {}
        orchestrator.active_contexts = {}
        orchestrator.execute_workflow = AsyncMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                   new=AsyncMock()), \
             patch("advanced_workflow_orchestrator.WorkflowContext",
                   lambda **kw: SimpleNamespace(**kw, status="pending",
                                               started_at=datetime.now())), \
             patch("advanced_workflow_orchestrator.WorkflowStatus",
                   SimpleNamespace(PENDING="pending", FAILED="failed")):
            bt = MagicMock()
            result = await execute_workflow(
                {"workflow_id": "ghost", "input": {}}, bt,
                current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert result["total_steps"] == 0


class TestExecutions:
    async def test_get_executions_orchestrator_contexts(self):
        context = SimpleNamespace(
            workflow_id="wf-1", input_data={"_ui_workflow_id": "ui-1"},
            status=SimpleNamespace(value="running"),
            started_at=datetime.now(timezone.utc),
            completed_at=None, results={"step1": 1},
            error_message=None)
        orchestrator = MagicMock()
        orchestrator.active_contexts = {"c1": context}
        orchestrator.memory_snapshots = {}
        db = make_db()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.WorkflowExecution",
                   WorkflowExecution), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert result["executions"][0]["workflow_id"] == "ui-1"

    async def test_get_executions_import_error_fallback(self):
        db = make_db()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   side_effect=ImportError("no orchestrator")), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True

    async def test_get_executions_with_persisted_rows(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        row = SimpleNamespace(
            execution_id="ex-9", workflow_id="wf-9", status="COMPLETED",
            input_data='{"a": 1}', outputs='{"o": 2}', steps='[{"id": "s1"}]',
            error=None, created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc))
        db = make_db()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        ex = next(e for e in result["executions"] if e["execution_id"] == "ex-9")
        assert ex["status"] == "completed"
        assert ex["total_steps"] == 1

    async def test_get_executions_bad_json_rows(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        row = SimpleNamespace(
            execution_id="ex-9", workflow_id="wf-9", status="RUNNING",
            input_data="{bad", outputs="{bad", steps="{bad",
            error="boom", created_at=datetime.now(timezone.utc),
            completed_at=None)
        db = make_db()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        ex = next(e for e in result["executions"] if e["execution_id"] == "ex-9")
        assert ex["errors"] == ["boom"]
        assert ex["total_steps"] == 0

    async def test_cancel_mock(self):
        result = await cancel_execution("exec_1", current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert MOCK_EXECUTIONS[0].status == "cancelled"
        MOCK_EXECUTIONS[0].status = "completed"  # restore

    async def test_cancel_db(self):
        db = make_db()
        row = SimpleNamespace(execution_id="ex-db")
        db.query.return_value.filter.return_value.first.return_value = row
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await cancel_execution("ex-db", current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert row.status == "CANCELLED"
        db.commit.assert_called_once()

    async def test_cancel_orchestrator_context(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        orchestrator = MagicMock()
        orchestrator.active_contexts = {"ex-ctx": SimpleNamespace()}
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await cancel_execution("ex-ctx", current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True

    async def test_cancel_not_found(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution("ghost", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 404

    async def test_get_orchestrator_state(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {"c1": "ctx"}
        orchestrator.memory_snapshots = {
            "s1": {"current_step": "st1", "variables": {"a": 1}}}
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await get_orchestrator_state(
                current_user=SimpleNamespace(id="u1"))
        assert result["active_contexts"] == ["c1"]
        assert result["snapshot_details"]["s1"]["step"] == "st1"

    async def test_get_workflow_history(self):
        result = await get_workflow_history("wf_1")
        assert result["success"] is True
        assert len(result["history"]) == 1
