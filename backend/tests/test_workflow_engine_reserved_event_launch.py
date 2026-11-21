"""Focused synthetic tests for the reserved event execution launch entry.

The real engine is imported. Only the state manager, the orchestration event
publisher, the runner boundary and the dispatch preflight are replaced, so the
tests exercise the production launch logic without a database or network.
"""

import asyncio
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.workflow_engine import WorkflowEngine  # noqa: E402


def _step_workflow(workflow_id="wf_one"):
    return {
        "id": workflow_id,
        "name": "Synthetic event workflow",
        "steps": [{
            "id": "step_one",
            "service": "email",
            "action": "send",
            "parameters": {},
        }],
    }


def _reserved_state(execution_id="evt_one", workflow_id="wf_one", workflow=None):
    """Build the persisted PENDING state a reservation hands to the engine."""
    if workflow is None:
        workflow = _step_workflow(workflow_id)
    return {
        "execution_id": execution_id,
        "workflow_id": workflow_id,
        "status": "PENDING",
        "context": {
            "_atom_event_admission": {
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "workflow_snapshot": workflow,
            },
        },
        "input_data": {},
        "steps": {},
        "outputs": {},
    }


def _admission(state):
    return state["context"]["_atom_event_admission"]


def _new_engine(claim_results=(True,)):
    engine = WorkflowEngine()
    state_manager = AsyncMock()
    state_manager.claim_event_execution.side_effect = list(claim_results)
    engine.state_manager = state_manager
    engine._publish_orchestration_event = Mock()
    engine._run_execution = AsyncMock()
    return engine


class ReservedEventLaunchTests(unittest.IsolatedAsyncioTestCase):
    async def test_claim_winner_publishes_and_dispatches_once(self):
        state = _reserved_state()
        snapshot = _admission(state)["workflow_snapshot"]
        engine = _new_engine([True])
        preflight = AsyncMock(return_value=True)

        launched = await engine.launch_reserved_event_execution(
            "evt_one", state, preflight)
        await asyncio.sleep(0)

        self.assertTrue(launched)
        engine.state_manager.claim_event_execution.assert_awaited_once_with(
            "evt_one")

        preflight.assert_awaited_once()
        execution_id, preflight_state, preflight_workflow = (
            preflight.await_args.args)
        self.assertEqual(execution_id, "evt_one")
        self.assertIs(preflight_state, state)
        self.assertEqual(preflight_workflow, snapshot)
        self.assertIsNot(preflight_workflow, snapshot)

        engine._publish_orchestration_event.assert_called_once_with(
            "WORKFLOW_STARTED", "wf_one", "evt_one",
            data={"step_count": 1},
        )
        engine._run_execution.assert_awaited_once_with("evt_one", snapshot)

    async def test_only_the_first_claim_wins(self):
        state = _reserved_state()
        engine = _new_engine([True, False])
        preflight = AsyncMock(return_value=True)

        first = await engine.launch_reserved_event_execution(
            "evt_one", state, preflight)
        second = await engine.launch_reserved_event_execution(
            "evt_one", state, preflight)
        await asyncio.sleep(0)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(
            engine.state_manager.claim_event_execution.await_count, 2)
        engine._publish_orchestration_event.assert_called_once()
        engine._run_execution.assert_awaited_once()

    async def test_invalid_or_missing_state_is_rejected_before_preflight(self):
        cases = [("state is None", None, "evt_one")]

        state = _reserved_state()
        state.pop("execution_id")
        cases.append(("missing state execution id", state, "evt_one"))

        state = _reserved_state()
        state["execution_id"] = "evt_other"
        cases.append(("mismatched state execution id", state, "evt_one"))

        state = _reserved_state()
        state.pop("workflow_id")
        cases.append(("missing state workflow id", state, "evt_one"))

        state = _reserved_state()
        state["workflow_id"] = "wf_other"
        cases.append(("mismatched state workflow id", state, "evt_one"))

        state = _reserved_state()
        state["status"] = "RUNNING"
        cases.append(("non-pending state", state, "evt_one"))

        state = _reserved_state()
        state["context"] = {}
        cases.append(("missing admission", state, "evt_one"))

        state = _reserved_state()
        _admission(state).pop("execution_id")
        cases.append(("missing admission execution id", state, "evt_one"))

        state = _reserved_state()
        _admission(state)["execution_id"] = "evt_other"
        cases.append(("mismatched admission execution id", state, "evt_one"))

        state = _reserved_state()
        _admission(state).pop("workflow_id")
        cases.append(("missing admission workflow id", state, "evt_one"))

        state = _reserved_state()
        _admission(state)["workflow_id"] = "wf_other"
        cases.append(("mismatched admission workflow id", state, "evt_one"))

        state = _reserved_state()
        _admission(state).pop("workflow_snapshot")
        cases.append(("missing workflow snapshot", state, "evt_one"))

        state = _reserved_state()
        _admission(state)["workflow_snapshot"]["id"] = "wf_other"
        cases.append(("mismatched snapshot workflow id", state, "evt_one"))

        state = _reserved_state()
        state["_atom_event_admission"] = _admission(state)
        state["context"] = {}
        cases.append(("alternate admission location", state, "evt_one"))

        state = _reserved_state()
        state["workflow_snapshot"] = _admission(state).pop(
            "workflow_snapshot")
        cases.append(("alternate snapshot location", state, "evt_one"))

        cases.append(
            ("non-reserved execution id", _reserved_state(), "job_one"))

        for label, state, token in cases:
            with self.subTest(label=label):
                engine = _new_engine([True])
                preflight = AsyncMock(return_value=True)

                launched = await engine.launch_reserved_event_execution(
                    token, state, preflight)

                self.assertFalse(launched)
                preflight.assert_not_awaited()
                engine.state_manager.claim_event_execution.assert_not_awaited()
                engine._publish_orchestration_event.assert_not_called()
                engine._run_execution.assert_not_awaited()

    async def test_denied_preflight_does_not_claim_or_dispatch(self):
        state = _reserved_state()
        preflights = (
            ("false", AsyncMock(return_value=False)),
            ("exception", AsyncMock(side_effect=RuntimeError("denied"))),
        )

        for label, preflight in preflights:
            with self.subTest(label=label):
                engine = _new_engine([True])

                launched = await engine.launch_reserved_event_execution(
                    "evt_one", state, preflight)

                self.assertFalse(launched)
                preflight.assert_awaited_once()
                engine.state_manager.claim_event_execution.assert_not_awaited()
                engine._publish_orchestration_event.assert_not_called()
                engine._run_execution.assert_not_awaited()

    async def test_graph_snapshot_is_copied_before_conversion(self):
        snapshot = {
            "id": "wf_graph",
            "name": "Graph event workflow",
            "nodes": [{
                "id": "node_one",
                "title": "One",
                "config": {"service": "email", "action": "send"},
            }],
            "connections": [],
        }
        original = copy.deepcopy(snapshot)
        state = _reserved_state(
            "evt_graph", "wf_graph", workflow=snapshot)
        engine = _new_engine([True])
        preflight = AsyncMock(return_value=True)

        launched = await engine.launch_reserved_event_execution(
            "evt_graph", state, preflight)
        await asyncio.sleep(0)

        self.assertTrue(launched)
        frozen = _admission(state)["workflow_snapshot"]
        self.assertEqual(frozen, original)
        self.assertNotIn("steps", frozen)

        preflight_workflow = preflight.await_args.args[2]
        self.assertIsNot(preflight_workflow, frozen)
        self.assertIn("steps", preflight_workflow)
        self.assertNotIn("steps", frozen)

        run_workflow = engine._run_execution.await_args.args[1]
        self.assertIn("steps", run_workflow)
        self.assertNotIn("steps", frozen)


if __name__ == "__main__":
    unittest.main()
