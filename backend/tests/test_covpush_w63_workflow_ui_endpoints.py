"""Coverage wave 63 — core/workflow_ui_endpoints.py (88% → 95%+).

Closes the remaining holes: update_workflow icon payload (515), DB-mode
delete 404 (561), execute-by-id background task run + schedule failure
(590/594-595), persisted-execution dedup (648), dict-form orchestrator
contexts (698-741), context parse failure + orchestrator failure +
merge failure tolerance (758-767/775-776), finance/project template id
mapping (808/810), email/delay bridge step types (836/838), execute
background failure path (889-898), found-mock step-count fallback (908),
cancel dict-context/setter-failure/orchestrator-error (959/963-967).
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.workflow_ui_endpoints import (
    MOCK_EXECUTIONS,
    MOCK_TEMPLATES,
    MOCK_WORKFLOWS,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
    WorkflowTemplateResponse,
    _merge_persisted_executions,
    cancel_execution,
    delete_workflow,
    execute_workflow,
    execute_workflow_by_id,
    get_executions,
    get_workflow_history,
    update_workflow,
)


def make_template(**kw):
    defaults = dict(
        id="tpl-1", template_id="tpl-1", tenant_id="t-1", name="T", description="d",
        category="automation", complexity="beginner", tags=[],
        is_public=True, icon="icon", steps=[], input_schema={},
        steps_schema=[], inputs_schema={}, output_schema={},
        template_json={}, rating=4.5, usage_count=10, author_id="u1",
        version="1.0", created_at=datetime.now(),
        updated_at=datetime.now())
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_db(template=None, rows=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = template
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = rows or []
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


class TestUpdateDeleteBranches:
    async def test_update_workflow_icon_payload(self):
        with patch_mock_flag(False):
            tpl = make_template()
            db = make_db(template=tpl)
            with patch_db(db):
                result = await update_workflow(
                    "tpl-1", {"icon": "rocket"}, db=db)
        assert result["workflow"]["icon"] == "rocket"

    async def test_delete_workflow_db_404(self):
        with patch_mock_flag(False):
            db = make_db(template=None)
            with patch_db(db):
                with pytest.raises(Exception) as exc:
                    await delete_workflow("ghost", db=db)
        assert exc.value.status_code == 404


class TestExecuteByIdBranches:
    async def test_background_task_runs(self):
        orchestrator = MagicMock()
        orchestrator.execute_workflow = AsyncMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                   new=AsyncMock()):
            bt = MagicMock()
            result = await execute_workflow_by_id(
                "wf-1", bt, {"x": 1}, current_user=SimpleNamespace(id="u1"))
        task = bt.add_task.call_args[0][0]
        await task()
        orchestrator.execute_workflow.assert_awaited_once_with(
            "wf-1", {"x": 1, "_ui_workflow_id": "wf-1"},
            execution_id=result["execution_id"])

    async def test_schedule_failure_tolerated(self):
        orchestrator = MagicMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                   new=AsyncMock()):
            bt = MagicMock()
            bt.add_task.side_effect = RuntimeError("scheduler down")
            result = await execute_workflow_by_id(
                "wf-1", bt, {}, current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True  # failure swallowed, exec id returned


class TestMergeDedup:
    def test_duplicate_rows_skipped(self):
        db = make_db()
        row = SimpleNamespace(
            execution_id="ex-1", workflow_id="wf-1", status="COMPLETED",
            input_data=None, outputs=None, steps=None, error=None,
            created_at=datetime.now(), completed_at=None)
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            existing = [WorkflowExecution(
                execution_id="ex-1", workflow_id="wf-1", status="completed",
                start_time=datetime.now().isoformat(), current_step=0,
                total_steps=0)]
            result = _merge_persisted_executions(existing)
        assert len(result) == 1  # deduped, no append


class TestExecutionsDictContexts:
    async def test_dict_contexts_and_errors(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {
            "c1": {
                "workflow_id": "wf-d1",
                "input_data": {"_ui_workflow_id": "ui-1"},
                "status": "running",
                "started_at": "2026-08-01T10:00:00",
                "completed_at": "2026-08-01T11:00:00",
                "results": {"a": 1},
                "error_message": None,
            },
            "c2": {"status": "done",
                   "started_at": datetime.now(),
                   "completed_at": datetime.now(),
                   "results": None,
                   "error_message": "boom",
                   "workflow_id": "wf-d2",
                   "input_data": {}},
        }
        db = make_db()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        by_id = {e["execution_id"]: e for e in result["executions"]}
        assert by_id["wf-d1"]["workflow_id"] == "ui-1"
        assert by_id["wf-d1"]["status"] == "running"
        assert by_id["wf-d1"]["start_time"] == "2026-08-01T10:00:00"
        assert by_id["wf-d1"]["end_time"] == "2026-08-01T11:00:00"
        assert by_id["wf-d2"]["errors"] == ["boom"]

    async def test_bad_context_skipped(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {
            "bad": SimpleNamespace(**{"workflow_id": "w"}),
        }
        # make processing raise: results is a non-dict without len()
        orchestrator.active_contexts["bad"].input_data = None
        db = make_db()
        db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert len(result["executions"]) == 0  # bad context skipped, no crash

    async def test_orchestrator_failure_falls_back_empty(self):
        class _BadOrch:
            @property
            def active_contexts(self):
                raise RuntimeError("boom")

        orchestrator = _BadOrch()
        db = make_db()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert result["executions"] == []

    async def test_merge_failure_tolerated(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        db = make_db()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("core.workflow_ui_endpoints._merge_persisted_executions",
                   side_effect=RuntimeError("db down")):
            result = await get_executions(current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True


class TestExecuteMappingBranches:
    def _orchestrator(self, workflow_ids):
        orchestrator = MagicMock()
        orchestrator.workflows = {
            wid: SimpleNamespace(steps=[1, 2]) for wid in workflow_ids}
        orchestrator.active_contexts = {}
        orchestrator.execute_workflow = AsyncMock()
        return orchestrator

    async def test_finance_and_project_mapping(self):
        for tpl_id, mapped_id in [
                ("tpl_o365_finance", "financial_reporting_automation"),
                ("tpl_o365_project", "project_inception_workflow")]:
            orchestrator = self._orchestrator([mapped_id])
            with patch("advanced_workflow_orchestrator.get_orchestrator",
                       return_value=orchestrator), \
                 patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                       new=AsyncMock()) as gate, \
                 patch("advanced_workflow_orchestrator.WorkflowContext",
                       lambda **kw: SimpleNamespace(**kw, status="p",
                                                   started_at=datetime.now())), \
                 patch("advanced_workflow_orchestrator.WorkflowStatus",
                       SimpleNamespace(PENDING="pending", FAILED="failed")):
                bt = MagicMock()
                result = await execute_workflow(
                    {"workflow_id": tpl_id, "input": {}}, bt,
                    current_user=SimpleNamespace(id="u1"))
            assert result["success"] is True
            assert result["total_steps"] == 2
            gate.assert_called_with(SimpleNamespace(id="u1"), orchestrator,
                                    mapped_id)

    async def test_bridge_email_and_delay_step_types(self):
        template = WorkflowTemplateResponse(
            id="tpl_edges", name="Edges", description="d", category="c",
            icon="i",
            steps=[
                WorkflowStep(id="s1", type="action", service="gmail",
                             action="send_email", name="Mail"),
                WorkflowStep(id="s2", type="action", service="delay",
                             action="wait", name="Wait"),
            ],
            input_schema={})
        orchestrator = MagicMock()
        orchestrator.workflows = {}
        orchestrator.active_contexts = {}
        orchestrator.execute_workflow = AsyncMock()

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
             patch("advanced_workflow_orchestrator.WorkflowContext",
                   lambda **kw: SimpleNamespace(**kw, status="p",
                                               started_at=datetime.now())), \
             patch("advanced_workflow_orchestrator.WorkflowStatus",
                   SimpleNamespace(PENDING="pending", FAILED="failed")), \
             patch("advanced_workflow_orchestrator.WorkflowStep",
                   lambda **kw: SimpleNamespace(**kw)), \
             patch("advanced_workflow_orchestrator.WorkflowDefinition",
                   lambda **kw: SimpleNamespace(**kw)), \
             patch("advanced_workflow_orchestrator.WorkflowStepType", _StepType):
            MOCK_TEMPLATES.append(template)
            try:
                bt = MagicMock()
                result = await execute_workflow(
                    {"workflow_id": "tpl_edges", "input": {}}, bt,
                    current_user=SimpleNamespace(id="u1"))
            finally:
                MOCK_TEMPLATES.pop()
        steps = orchestrator.workflows["tpl_edges"].steps
        assert steps[0].step_type == _StepType.EMAIL_SEND
        assert steps[1].step_type == _StepType.DELAY
        assert result["total_steps"] == 2

    async def test_background_execution_failure_marks_failed(self):
        orchestrator = MagicMock()
        orchestrator.workflows = {"wf-real": SimpleNamespace(steps=[1, 2])}
        orchestrator.active_contexts = {}
        orchestrator.execute_workflow = AsyncMock(
            side_effect=RuntimeError("boom"))

        class _Ctx:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)

        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                   new=AsyncMock()), \
             patch("advanced_workflow_orchestrator.WorkflowContext", _Ctx), \
             patch("advanced_workflow_orchestrator.WorkflowStatus",
                   SimpleNamespace(PENDING="pending", FAILED="failed")):
            bt = MagicMock()
            result = await execute_workflow(
                {"workflow_id": "wf-real", "input": {}}, bt,
                current_user=SimpleNamespace(id="u1"))
        task = bt.add_task.call_args[0][0]
        await task()
        ctx = orchestrator.active_contexts[result["execution_id"]]
        assert ctx.status == "failed"
        assert ctx.error_message == "boom"

    async def test_found_mock_step_count_fallback(self):
        # MagicMock workflows: __contains__ is False, so the bridge registers
        # but the post-bridge `in` check is False -> falls to the mock branch
        orchestrator = MagicMock()
        orchestrator.workflows = MagicMock()
        orchestrator.active_contexts = {}
        orchestrator.execute_workflow = AsyncMock()

        class _Ctx:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)

        mock_wf = WorkflowDefinition(
            id="wf_1", name="Weekly Report", description="d", steps=[],
            input_schema={}, created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(), steps_count=0)
        MOCK_WORKFLOWS.insert(0, mock_wf)
        try:
            with patch("advanced_workflow_orchestrator.get_orchestrator",
                       return_value=orchestrator), \
                 patch("core.workflow_ui_endpoints.require_workflow_executor_orchestrator",
                       new=AsyncMock()), \
                 patch("advanced_workflow_orchestrator.WorkflowContext", _Ctx), \
                 patch("advanced_workflow_orchestrator.WorkflowStatus",
                       SimpleNamespace(PENDING="pending", FAILED="failed")), \
                 patch("advanced_workflow_orchestrator.WorkflowStep",
                       lambda **kw: SimpleNamespace(**kw)), \
                 patch("advanced_workflow_orchestrator.WorkflowDefinition",
                       lambda **kw: SimpleNamespace(**kw)):
                bt = MagicMock()
                result = await execute_workflow(
                    {"workflow_id": "wf_1", "input": {}}, bt,
                    current_user=SimpleNamespace(id="u1"))
        finally:
            MOCK_WORKFLOWS.remove(mock_wf)
        assert result["success"] is True
        assert result["total_steps"] == 0  # len(found_mock.steps) == 0


class TestCancelBranches:
    async def test_cancel_dict_context(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        orchestrator = MagicMock()
        orchestrator.active_contexts = {"ex-dict": {"status": "running"}}
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await cancel_execution(
                "ex-dict", current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert orchestrator.active_contexts["ex-dict"]["status"] == "cancelled"

    async def test_cancel_context_setter_failure(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        orchestrator = MagicMock()
        orchestrator.active_contexts = {"ex-frozen": _FrozenCtx()}
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await cancel_execution(
                "ex-frozen", current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True  # setattr failure swallowed

    async def test_cancel_orchestrator_error_404(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   side_effect=RuntimeError("boom")):
            with pytest.raises(Exception) as exc:
                await cancel_execution("ghost", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 404

    async def test_get_workflow_history_empty(self):
        result = await get_workflow_history("wf_nope")
        assert result["success"] is True
        assert result["history"] == []


class _FrozenCtx:
    def __setattr__(self, name, value):
        raise AttributeError("frozen")
