"""Focused tests for cooperative workflow cancellation.

These tests import the real orchestrator module. Persistence and external
services are replaced only inside individual test bodies with scoped mocks, so
no test depends on a running database or live integration.
"""

import asyncio
import datetime
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import advanced_workflow_orchestrator as orchestrator_module


class _FakeWorkflowExecution:
    # ORM query expressions read model attributes from the class, not just
    # from instances; mirror the mapped column so filters can be built.
    execution_id = None

    def __init__(self, **fields):
        self.execution_id = fields.get("execution_id")
        self.workflow_id = fields.get("workflow_id")
        self.user_id = fields.get("user_id")
        self.status = fields.get("status")
        self.completed_at = fields.get("completed_at")
        self.input_data = fields.get("input_data")
        self.outputs = fields.get("outputs")
        self.context = fields.get("context")
        self.error = fields.get("error")


class _FakeQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *_args):
        return self

    def first(self):
        return self.row


class _FakeDB:
    def __init__(self, row=None):
        self.row = row
        self.added = []
        self.commits = 0

    def query(self, _model):
        return _FakeQuery(self.row)

    def add(self, obj):
        self.added.append(obj)
        self.row = obj

    def commit(self):
        self.commits += 1


class _FakeSession:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *_exc):
        return False


class CancelWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Keep orchestration construction deterministic: no durable restore or
        # live AI session initialization. These patches live only for setUp.
        with mock.patch.object(
                orchestrator_module.AdvancedWorkflowOrchestrator,
                "_restore_active_executions"), mock.patch.object(
                    orchestrator_module.AdvancedWorkflowOrchestrator,
                    "_initialize_ai_service"):
            self.orchestrator = (
                orchestrator_module.AdvancedWorkflowOrchestrator())

    def _register_two_delay_workflow(self, workflow_id):
        workflow = orchestrator_module.WorkflowDefinition(
            workflow_id=workflow_id,
            name="Cancel synthetic workflow",
            description="Two no-effect delay steps",
            steps=[
                orchestrator_module.WorkflowStep(
                    step_id="first",
                    step_type=orchestrator_module.WorkflowStepType.DELAY,
                    description="Controlled hold",
                    next_steps=["second"],
                ),
                orchestrator_module.WorkflowStep(
                    step_id="second",
                    step_type=orchestrator_module.WorkflowStepType.DELAY,
                    description="Must not run after cancel",
                    next_steps=[],
                ),
            ],
            start_step="first",
        )
        self.orchestrator.register_workflow(workflow)
        return workflow

    async def test_cancel_running_first_step_persists_and_skips_second(self):
        WorkflowStatus = orchestrator_module.WorkflowStatus
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        second_calls = []
        saves = []

        async def fake_delay(step, _context):
            if step.step_id == "first":
                first_started.set()
                await release_first.wait()
                return {"status": "completed", "step": "first"}
            second_calls.append(step.step_id)
            return {"status": "completed", "step": step.step_id}

        def fake_save(context):
            saves.append((context.status, context.completed_at))
            return True

        self.orchestrator._execute_delay = fake_delay
        self.orchestrator._save_execution_state = fake_save
        workflow = self._register_two_delay_workflow("cancel-running-first")
        execution_id = "exec-cancel-running-first"

        task = asyncio.create_task(self.orchestrator.execute_workflow(
            workflow.workflow_id, {}, execution_id=execution_id))
        await asyncio.wait_for(first_started.wait(), timeout=1)
        context = self.orchestrator.active_contexts[execution_id]
        self.assertEqual(context.status, WorkflowStatus.RUNNING)

        acknowledged = await self.orchestrator.cancel_workflow(context)
        self.assertTrue(acknowledged)
        self.assertEqual(context.status, WorkflowStatus.CANCELLED)
        self.assertIsNotNone(context.completed_at)
        self.assertEqual(saves[0][0], WorkflowStatus.CANCELLED)

        release_first.set()
        result = await asyncio.wait_for(task, timeout=1)

        self.assertEqual(result.status, WorkflowStatus.CANCELLED)
        self.assertEqual(second_calls, [])
        self.assertEqual(saves[-1][0], WorkflowStatus.CANCELLED)
        self.assertEqual(
            result.results["first"]["status"], "completed",
            "late in-flight result may be recorded but not reversed")

    async def test_cancel_without_confirmed_persistence_is_not_acknowledged(self):
        WorkflowStatus = orchestrator_module.WorkflowStatus
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        second_calls = []

        async def fake_delay(step, _context):
            if step.step_id == "first":
                first_started.set()
                await release_first.wait()
                return {"status": "completed", "step": "first"}
            second_calls.append(step.step_id)
            return {"status": "completed", "step": step.step_id}

        self.orchestrator._execute_delay = fake_delay
        self.orchestrator._save_execution_state = lambda _context: False
        workflow = self._register_two_delay_workflow("cancel-save-fails")
        execution_id = "exec-cancel-save-fails"

        task = asyncio.create_task(self.orchestrator.execute_workflow(
            workflow.workflow_id, {}, execution_id=execution_id))
        await asyncio.wait_for(first_started.wait(), timeout=1)
        context = self.orchestrator.active_contexts[execution_id]

        acknowledged = await self.orchestrator.cancel_workflow(context)
        self.assertFalse(acknowledged)
        self.assertEqual(context.status, WorkflowStatus.CANCELLED)

        release_first.set()
        result = await asyncio.wait_for(task, timeout=1)
        self.assertEqual(result.status, WorkflowStatus.CANCELLED)
        self.assertEqual(second_calls, [])

    async def test_cancel_persists_durable_cancelled_receipt(self):
        WorkflowStatus = orchestrator_module.WorkflowStatus
        execution_id = "exec-durable-receipt"
        context = orchestrator_module.WorkflowContext(
            workflow_id=execution_id,
            status=WorkflowStatus.RUNNING,
        )
        self.orchestrator.active_contexts[execution_id] = context
        db = _FakeDB()

        with mock.patch.object(
                orchestrator_module, "MODELS_AVAILABLE", True), \
                mock.patch.object(
                    orchestrator_module, "get_db_session",
                    lambda: _FakeSession(db), create=True), \
                mock.patch.object(
                    orchestrator_module, "WorkflowExecution",
                    _FakeWorkflowExecution, create=True):
            acknowledged = await self.orchestrator.cancel_workflow(context)

        self.assertTrue(acknowledged)
        self.assertEqual(db.commits, 1)
        self.assertEqual(len(db.added), 1)
        stored = db.added[0]
        self.assertEqual(stored.status, WorkflowStatus.CANCELLED.value)
        self.assertEqual(stored.completed_at, context.completed_at)
        self.assertIsNotNone(stored.completed_at)

    async def test_save_preserves_durable_cancelled_over_terminal_result(self):
        WorkflowStatus = orchestrator_module.WorkflowStatus
        execution_id = "exec-durable-already-cancelled"
        cancelled_at = datetime.datetime(2026, 1, 1)
        context = orchestrator_module.WorkflowContext(
            workflow_id=execution_id,
            status=WorkflowStatus.RUNNING,
        )
        existing = _FakeWorkflowExecution(
            execution_id=execution_id,
            workflow_id="workflow-definition",
            status=WorkflowStatus.CANCELLED.value,
            completed_at=cancelled_at,
        )
        db = _FakeDB(row=existing)

        with mock.patch.object(
                orchestrator_module, "MODELS_AVAILABLE", True), \
                mock.patch.object(
                    orchestrator_module, "get_db_session",
                    lambda: _FakeSession(db), create=True), \
                mock.patch.object(
                    orchestrator_module, "WorkflowExecution",
                    _FakeWorkflowExecution, create=True):
            persisted = self.orchestrator._save_execution_state(context)

        self.assertFalse(persisted)
        self.assertEqual(db.commits, 0)
        self.assertEqual(existing.status, WorkflowStatus.CANCELLED.value)
        self.assertEqual(existing.completed_at, cancelled_at)

    async def test_cancel_refuses_to_overwrite_terminal_state(self):
        WorkflowStatus = orchestrator_module.WorkflowStatus

        for terminal in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
            with self.subTest(terminal=terminal):
                execution_id = f"exec-terminal-{terminal.value}"
                completed_at = datetime.datetime(2026, 1, 1)
                context = orchestrator_module.WorkflowContext(
                    workflow_id=execution_id,
                    status=terminal,
                    completed_at=completed_at,
                )
                self.orchestrator.active_contexts[execution_id] = context
                saves = []
                self.orchestrator._save_execution_state = (
                    lambda saved: saves.append(saved) or True)

                acknowledged = await self.orchestrator.cancel_workflow(context)

                self.assertFalse(acknowledged)
                self.assertEqual(context.status, terminal)
                self.assertEqual(context.completed_at, completed_at)
                self.assertEqual(saves, [])

    async def test_cancel_rejects_missing_stale_or_replaced_context(self):
        WorkflowStatus = orchestrator_module.WorkflowStatus
        execution_id = "exec-not-live"
        saves = []
        self.orchestrator._save_execution_state = (
            lambda saved: saves.append(saved) or True)

        missing = orchestrator_module.WorkflowContext(
            workflow_id=execution_id,
            status=WorkflowStatus.RUNNING,
        )
        self.assertFalse(await self.orchestrator.cancel_workflow(missing))
        self.assertEqual(missing.status, WorkflowStatus.RUNNING)
        self.assertEqual(saves, [])

        live = orchestrator_module.WorkflowContext(
            workflow_id=execution_id,
            status=WorkflowStatus.RUNNING,
        )
        self.orchestrator.active_contexts[execution_id] = live
        stale = orchestrator_module.WorkflowContext(
            workflow_id=execution_id,
            status=WorkflowStatus.RUNNING,
        )

        self.assertFalse(await self.orchestrator.cancel_workflow(stale))
        self.assertEqual(stale.status, WorkflowStatus.RUNNING)
        self.assertEqual(live.status, WorkflowStatus.RUNNING)
        self.assertEqual(saves, [])

    async def test_pending_context_cancelled_before_dispatch_is_kept(self):
        WorkflowStatus = orchestrator_module.WorkflowStatus
        workflow = self._register_two_delay_workflow("cancel-before-dispatch")
        execution_id = "exec-cancel-before-dispatch"
        pending = orchestrator_module.WorkflowContext(
            workflow_id=execution_id,
            status=WorkflowStatus.PENDING,
        )
        self.orchestrator.active_contexts[execution_id] = pending
        saves = []
        dispatched = []

        async def fake_delay(step, _context):
            dispatched.append(step.step_id)
            return {"status": "completed", "step": step.step_id}

        self.orchestrator._execute_delay = fake_delay
        self.orchestrator._save_execution_state = (
            lambda saved: saves.append(saved) or True)

        self.assertEqual(pending.status, WorkflowStatus.PENDING)
        self.assertTrue(await self.orchestrator.cancel_workflow(pending))
        self.assertEqual(pending.status, WorkflowStatus.CANCELLED)
        self.assertIsNotNone(pending.completed_at)
        self.assertEqual(saves, [pending])

        result = await self.orchestrator.execute_workflow(
            workflow.workflow_id, {}, execution_id=execution_id)

        self.assertIs(result, pending)
        self.assertIs(self.orchestrator.active_contexts[execution_id], pending)
        self.assertEqual(result.status, WorkflowStatus.CANCELLED)
        self.assertEqual(dispatched, [])
        self.assertEqual(
            saves, [pending],
            "execute_workflow must not rewrite a cancelled durable state")


if __name__ == "__main__":
    unittest.main()
