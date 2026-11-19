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
import json
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
            execution_id=result["execution_id"],
            execution_context={"user_id": "u1", "tenant_id": None})

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
            created_at=datetime.now(), completed_at=None,
            owner_id="u1", user_id="u1", tenant_id=None)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            existing = [WorkflowExecution(
                execution_id="ex-1", workflow_id="wf-1", status="completed",
                start_time=datetime.now().isoformat(), current_step=0,
                total_steps=0)]
            result = _merge_persisted_executions(
                existing, SimpleNamespace(id="u1", tenant_id=None))
        assert len(result) == 1  # deduped, no append
        db.query.return_value.filter.assert_called()  # actor scope applied


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
                "user_id": "u1",
                "tenant_id": None,
            },
            "c2": {"status": "done",
                   "started_at": datetime.now(),
                   "completed_at": datetime.now(),
                   "results": None,
                   "error_message": "boom",
                   "workflow_id": "wf-d2",
                   "input_data": {},
                   "user_id": "u1",
                   "tenant_id": None},
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
        orchestrator.active_contexts["bad"].user_id = "u1"
        orchestrator.active_contexts["bad"].tenant_id = None
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
    async def test_cancel_legacy_dict_context_is_not_mutated(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        cancel_workflow = AsyncMock(return_value=True)
        orchestrator = SimpleNamespace(
            active_contexts={
                "ex-dict": {
                    "status": "running", "user_id": "u1", "tenant_id": None,
                },
            },
            cancel_workflow=cancel_workflow,
        )
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "ex-dict", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 503
        assert orchestrator.active_contexts["ex-dict"]["status"] == "running"
        cancel_workflow.assert_not_called()

    async def test_cancel_live_typed_context_uses_cooperative_method(self):
        context = SimpleNamespace(
            workflow_id="ex-live", status="running",
            user_id="u1", tenant_id=None,
        )
        cancel_workflow = AsyncMock(return_value=True)
        orchestrator = SimpleNamespace(
            active_contexts={"ex-live": context},
            cancel_workflow=cancel_workflow,
        )
        fake_db = make_db()
        with patch("core.workflow_ui_endpoints.get_db",
                   return_value=iter([fake_db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await cancel_execution(
                "ex-live", current_user=SimpleNamespace(id="u1"))
        assert result == {"success": True}
        cancel_workflow.assert_awaited_once_with(context)
        fake_db.query.assert_not_called()  # live context wins over SQL

    async def test_cancel_local_cancelled_retry_uses_cooperative_method(self):
        # The engine marks the typed context CANCELLED before persisting, so a
        # retry after a failed save must call the cooperative method again and
        # refuse when it cannot confirm the durable receipt.
        context = SimpleNamespace(
            workflow_id="ex-cancel-retry", status="CANCELLED",
            user_id="u1", tenant_id=None,
        )
        cancel_workflow = AsyncMock(return_value=False)
        orchestrator = SimpleNamespace(
            active_contexts={"ex-cancel-retry": context},
            cancel_workflow=cancel_workflow,
        )
        fake_db = make_db()
        with patch("core.workflow_ui_endpoints.get_db",
                   return_value=iter([fake_db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "ex-cancel-retry", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 409
        cancel_workflow.assert_awaited_once_with(context)
        fake_db.query.assert_not_called()

    async def test_cancel_live_context_declined_is_409(self):
        context = SimpleNamespace(
            workflow_id="ex-declined", status="running",
            user_id="u1", tenant_id=None,
        )
        orchestrator = SimpleNamespace(
            active_contexts={"ex-declined": context},
            cancel_workflow=AsyncMock(return_value=False),
        )
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "ex-declined", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 409
        assert context.status == "running"

    async def test_cancel_live_context_failure_is_503(self):
        context = SimpleNamespace(
            workflow_id="ex-frozen", status="running",
            user_id="u1", tenant_id=None,
        )
        orchestrator = SimpleNamespace(
            active_contexts={"ex-frozen": context},
            cancel_workflow=AsyncMock(side_effect=RuntimeError("frozen")),
        )
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "ex-frozen", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 503
        assert context.status == "running"

    async def test_cancel_live_context_without_method_is_503(self):
        context = SimpleNamespace(
            workflow_id="ex-nocancel", status="running",
            user_id="u1", tenant_id=None,
        )
        orchestrator = SimpleNamespace(
            active_contexts={"ex-nocancel": context},
            cancel_workflow=None,
        )
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "ex-nocancel", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 503
        assert context.status == "running"

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


class TestExecutionAuthorization:
    async def test_get_executions_only_returns_actor_same_tenant(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {
            "owned": {
                "workflow_id": "wf-owned", "input_data": {},
                "status": "running", "user_id": "u1", "tenant_id": "t1",
            },
            "other-user": {
                "workflow_id": "wf-other-user", "input_data": {},
                "status": "running", "user_id": "u2", "tenant_id": "t1",
            },
            "other-tenant": {
                "workflow_id": "wf-other-tenant", "input_data": {},
                "status": "running", "user_id": "u1", "tenant_id": "t2",
            },
            "ownerless": {
                "workflow_id": "wf-legacy", "input_data": {},
                "status": "running",
            },
        }
        db = make_db()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(
                current_user=SimpleNamespace(id="u1", tenant_id="t1"))
        assert [e["execution_id"] for e in result["executions"]] == ["wf-owned"]

    async def test_get_executions_ignores_nested_identity(self):
        orchestrator = MagicMock()
        orchestrator.active_contexts = {
            "nested": {
                "workflow_id": "wf-nested", "input_data": {},
                "status": "running",
                "execution_context": {"user_id": "u1", "tenant_id": "t1"},
                "variables": {"user_id": "u1", "tenant_id": "t1"},
            },
            "top-level": {
                "workflow_id": "wf-top", "input_data": {},
                "status": "running", "user_id": "u1", "tenant_id": "t1",
            },
        }
        db = make_db()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])):
            result = await get_executions(
                current_user=SimpleNamespace(id="u1", tenant_id="t1"))
        assert [e["execution_id"] for e in result["executions"]] == ["wf-top"]

    async def test_cancel_owned_active_row_and_reject_terminal(self):
        orchestrator = SimpleNamespace(
            active_contexts={}, cancel_workflow=AsyncMock())
        active = SimpleNamespace(
            status="RUNNING", owner_id="u1", user_id=None, tenant_id=None,
            context=None)
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = active
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await cancel_execution(
                "exec-active", current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        db.commit.assert_called_once()
        db.query.return_value.filter.return_value.update.assert_called_once()
        orchestrator.cancel_workflow.assert_not_called()

        terminal = SimpleNamespace(
            status="COMPLETED", owner_id="u1", user_id=None, tenant_id=None,
            context=None)
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = terminal
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "exec-done", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 409
        assert terminal.status == "COMPLETED"
        db.commit.assert_not_called()

    async def test_cancel_already_cancelled_is_idempotent(self):
        orchestrator = SimpleNamespace(
            active_contexts={}, cancel_workflow=AsyncMock())
        cancelled = SimpleNamespace(
            status="CANCELLED", owner_id="u1", user_id=None, tenant_id=None,
            context=None)
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = cancelled
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await cancel_execution(
                "exec-cancelled", current_user=SimpleNamespace(id="u1"))
        assert result["success"] is True
        db.commit.assert_not_called()

    async def test_partial_is_terminal(self):
        from core.workflow_ui_endpoints import _is_terminal_status

        orchestrator = SimpleNamespace(
            active_contexts={}, cancel_workflow=AsyncMock())
        assert _is_terminal_status("PARTIAL") is True
        partial = SimpleNamespace(
            status="PARTIAL", owner_id="u1", user_id=None, tenant_id=None,
            context=None)
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = partial
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "exec-partial", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 409
        db.commit.assert_not_called()

    async def test_cancel_orchestrator_owned_row_without_live_context_is_503(self):
        row = SimpleNamespace(
            status="RUNNING", owner_id="u1", user_id=None, tenant_id=None,
            context=json.dumps({
                "variables": {},
                "execution_history": [],
                "results": {},
            }),
        )
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = row
        orchestrator = SimpleNamespace(
            active_contexts={}, cancel_workflow=AsyncMock())
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "exec-orch", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 503
        assert row.status == "RUNNING"
        db.commit.assert_not_called()
        db.query.return_value.filter.return_value.update.assert_not_called()

    async def test_cancel_live_typed_context_precedes_checkpoint_row(self):
        context = SimpleNamespace(
            workflow_id="exec-checkpoint", status="running",
            user_id="u1", tenant_id=None,
        )
        cancel_workflow = AsyncMock(return_value=True)
        orchestrator = SimpleNamespace(
            active_contexts={"exec-checkpoint": context},
            cancel_workflow=cancel_workflow,
        )
        row = SimpleNamespace(
            status="RUNNING", owner_id="u1", user_id=None, tenant_id=None,
            context=json.dumps({
                "variables": {},
                "execution_history": [],
                "results": {},
            }),
        )
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = row
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            result = await cancel_execution(
                "exec-checkpoint", current_user=SimpleNamespace(id="u1"))
        assert result == {"success": True}
        cancel_workflow.assert_awaited_once_with(context)
        assert row.status == "RUNNING"
        db.query.assert_not_called()  # live context wins over checkpoint row
        db.commit.assert_not_called()

    async def test_cancel_rejects_unowned_row_even_if_query_returns_it(self):
        foreign = SimpleNamespace(
            status="RUNNING", owner_id="u2", user_id="u2", tenant_id=None)
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = foreign
        orchestrator = MagicMock()
        orchestrator.active_contexts = {}
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "exec-foreign", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 404
        assert foreign.status == "RUNNING"
        db.commit.assert_not_called()

    async def test_cancel_skips_ownerless_context(self):
        db = make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        orchestrator = MagicMock()
        orchestrator.active_contexts = {"ex-legacy": {"status": "running"}}
        with patch("core.workflow_ui_endpoints.get_db", return_value=iter([db])), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator):
            with pytest.raises(Exception) as exc:
                await cancel_execution(
                    "ex-legacy", current_user=SimpleNamespace(id="u1"))
        assert exc.value.status_code == 404
        assert orchestrator.active_contexts["ex-legacy"]["status"] == "running"
