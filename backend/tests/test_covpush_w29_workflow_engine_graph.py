"""Coverage wave 29 — core/workflow_engine.py graph-execution branches + arbor refinement (TDD).

Picks up where waves 21 (w21_workflow_engine) left off. W21 brought the
module from 39% to 89%; the remaining 159 lines live in:
- ``_execute_workflow_graph`` branch work: resume-with-completed-steps
  (268-273), empty-condition connection (261), get_ready_steps skipping
  non-PENDING statuses (280), step failure → FAILED (391-397),
  continue_on_error downstream activation (417-432), workflow failure
  propagation (449-462), COMPLETED + analytics (467-489), PARTIAL (490-505).
  NOTE: existing graph tests died with a KeyError('status') in the mock
  state (the code reads ``current_state["status"]``), so the completion /
  PARTIAL paths were never reached — this wave fixes the mock states too.
- ``_run_execution`` guards: governance fail-open (710-711), step-record
  create/update failures (735-736, 793-794), snapshot failure (775-776),
  marketplace tracking on failure (857), outer exception → FAILED (905-912).
- ``run_workflow_with_arbor_refinement`` (0% → exercised end-to-end with a
  mocked state manager + persisted tree): success, FAILED prune, exception
  prune + re-raise, previous-tree negative-constraint inheritance, and the
  parallel-ratio > 0.3 / <= 0.3 cost-potential branches.
- One-liners: _publish_orchestration_event (invalid type / exception),
  _evaluate_condition (generic exception), _get_value_from_path
  (non-dict mid-path in step-output branch), _execute_step fallback timeout
  (StepTimeoutError), gmail/slack/github/zoom/notion/zoho executor edges.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.workflow_engine import (
    StepTimeoutError,
    WorkflowEngine,
)

from tests.test_covpush_w21_workflow_engine import make_engine, step_dict


def _graph_env(state_sequence):
    """Mock env for _execute_workflow_graph: sm, ws, analytics, db."""
    sm = MagicMock()
    sm.get_execution_state = AsyncMock(side_effect=state_sequence)
    sm.update_execution_status = AsyncMock()
    sm.update_step_status = AsyncMock()
    ws = MagicMock()
    ws.notify_workflow_status = AsyncMock()
    analytics = MagicMock()
    db = MagicMock()
    return sm, ws, analytics, db


def _running_state(**steps):
    return {"status": "RUNNING", "steps": steps, "input_data": {}, "outputs": {}}


class TestPublishOrchestrationEvent:
    def test_invalid_event_type_returns(self):
        engine = make_engine()
        with patch("core.orchestration.event_bus.get_event_bus") as mock_bus:
            result = engine._publish_orchestration_event("NOT_A_REAL_EVENT", "wf-1", "ex-1")
        assert result is None
        mock_bus.return_value.publish.assert_not_called()

    def test_event_bus_failure_swallowed(self):
        engine = make_engine()
        with patch("core.orchestration.event_bus.get_event_bus", side_effect=RuntimeError("bus down")):
            engine._publish_orchestration_event("WORKFLOW_STARTED", "wf-1", "ex-1")


class TestEvaluateCondition:
    def test_generic_exception_returns_false(self):
        engine = make_engine()
        with patch("core.safe_evaluator.safe_eval", side_effect=RuntimeError("eval boom")):
            assert engine._evaluate_condition("${input.x} > 1", {"input_data": {"x": 5}}) is False


class TestGetValueFromPath:
    def test_step_output_branch_non_dict_mid_path(self):
        engine = make_engine()
        state = {"outputs": {"step1": {"a": 1}}, "input_data": {}}
        assert engine._get_value_from_path("step1.a.b", state) is None

    def test_input_branch_non_dict_mid_path(self):
        engine = make_engine()
        state = {"outputs": {}, "input_data": {"a": 1}}
        assert engine._get_value_from_path("input.a.b", state) is None


class TestExecuteStepFallbackTimeout:
    async def test_fallback_timeout_raises_step_timeout(self):
        # The fallback's asyncio.TimeoutError is converted to StepTimeoutError
        # (lines 1257-1260), then re-wrapped by the fallback guard into a
        # ValueError naming both the primary and fallback failures.
        engine = make_engine()
        step = step_dict(
            service="email",
            action="send",
            fallback_service="slack",
            timeout=0.05,
        )

        async def slow_slack(*a, **k):
            raise asyncio.TimeoutError("timed out in wait_for")

        with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()), \
             patch.object(engine, "_execute_email_action", new=AsyncMock(side_effect=RuntimeError("primary down"))), \
             patch.object(engine, "_execute_slack_action", new=slow_slack):
            with pytest.raises(ValueError) as exc_info:
                await engine._execute_step(step, {})
        message = str(exc_info.value)
        assert "primary down" in message
        assert "slack" in message
        assert "timed out" in message


class TestGraphExecutorBranches:
    """_execute_workflow_graph: the completion/PARTIAL/resume/failure paths."""

    async def test_graph_success_path_completed(self):
        engine = make_engine()
        engine.state_manager = MagicMock()

        def _state(*a, **k):
            return _running_state()

        sm, ws, analytics, db = _graph_env([_running_state()])
        sm.get_execution_state = AsyncMock(side_effect=_state)
        engine.state_manager = sm
        workflow = {
            "id": "wf-g1",
            "workspace_id": "ws-1",
            "tenant_id": "t-1",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [],
        }
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            await engine._execute_workflow_graph(
                "ex-g1", workflow, _running_state(), ws, "user-1",
                start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        completed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert completed
        analytics.track_workflow_execution.assert_called_once()
        assert analytics.track_workflow_execution.call_args.kwargs["success"] is True

    async def test_graph_success_activates_connection(self):
        """Success with a true condition → downstream connection activated (line 383)."""
        engine = make_engine()
        sm, ws, analytics, db = _graph_env([_running_state()])
        sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: _running_state())
        engine.state_manager = sm
        workflow = {
            "id": "wf-g1b",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
                {"id": "b", "title": "B", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [{"source": "a", "target": "b", "condition": "${input.go} == true"}],
        }
        state = _running_state()
        state["input_data"] = {"go": True}
        sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: {
            "status": "RUNNING", "steps": {}, "input_data": {"go": True}, "outputs": {}
        })
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            await engine._execute_workflow_graph(
                "ex-g1b", workflow, state, ws, "user-1",
                start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        assert exec_mock.call_count == 2
        step_b = [c.args for c in sm.update_step_status.call_args_list if c.args[1] == "b"]
        assert any(c[2] == "COMPLETED" for c in step_b)

    async def test_graph_partial_when_step_blocked(self):
        engine = make_engine()
        sm, ws, analytics, db = _graph_env([_running_state()])
        sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: _running_state())
        engine.state_manager = sm
        workflow = {
            "id": "wf-g2",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
                {"id": "b", "title": "B", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            # condition always false → b never becomes ready → PARTIAL
            "connections": [{"source": "a", "target": "b", "condition": "${input.go} == true"}],
        }
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch.object(engine, "_execute_step", new=exec_mock):
            await engine._execute_workflow_graph(
                "ex-g2", workflow, _running_state(), ws, "user-1",
                start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        partial = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "PARTIAL"]
        assert partial
        analytics.track_workflow_execution.assert_called_once()
        assert analytics.track_workflow_execution.call_args.kwargs["success"] is False

    async def test_graph_step_failure_fails_workflow(self):
        engine = make_engine()
        sm, ws, analytics, db = _graph_env([_running_state()])
        sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: _running_state())
        engine.state_manager = sm
        workflow = {
            "id": "wf-g3",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [],
        }
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch.object(engine, "_execute_step", new=AsyncMock(side_effect=RuntimeError("step boom"))), \
             patch("core.workflow_notifier.notifier.notify_failure", new=AsyncMock()):
            await engine._execute_workflow_graph(
                "ex-g3", workflow, _running_state(), ws, "user-1",
                start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        failed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "FAILED"]
        assert failed

    async def test_graph_continue_on_error_activates_downstream(self):
        engine = make_engine()
        sm, ws, analytics, db = _graph_env([_running_state()])
        sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: _running_state())
        engine.state_manager = sm
        workflow = {
            "id": "wf-g4",
            "nodes": [
                {"id": "a", "title": "A", "type": "action",
                 "config": {"service": "email", "action": "send", "continue_on_error": True}},
                {"id": "b", "title": "B", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [{"source": "a", "target": "b"}],
        }

        async def _exec(step, params):
            if step["id"] == "a":
                raise RuntimeError("step a boom")
            return {"status": "success", "result": {}}

        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch.object(engine, "_execute_step", new=_exec):
            await engine._execute_workflow_graph(
                "ex-g4", workflow, _running_state(), ws, "user-1",
                start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        # a marked FAILED, b still ran, execution ends PARTIAL (a not COMPLETED)
        step_calls = [c.args for c in sm.update_step_status.call_args_list if c.args[1] == "a"]
        assert any(c[2] == "FAILED" for c in step_calls)
        step_b = [c.args for c in sm.update_step_status.call_args_list if c.args[1] == "b"]
        assert any(c[2] == "COMPLETED" for c in step_b)
        partial = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "PARTIAL"]
        assert partial

    async def test_graph_resume_activates_completed_step_connections(self):
        engine = make_engine()
        sm, ws, analytics, db = _graph_env([_running_state()])
        sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: _running_state())
        engine.state_manager = sm
        workflow = {
            "id": "wf-g5",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
                {"id": "b", "title": "B", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [{"source": "a", "target": "b", "condition": ""}],
        }
        state = _running_state(a={"status": "COMPLETED", "output": {}})
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            await engine._execute_workflow_graph(
                "ex-g5", workflow, state, ws, "user-1",
                start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        # a's empty-condition connection activated on resume → b executed
        step_b = [c.args for c in sm.update_step_status.call_args_list if c.args[1] == "b"]
        assert any(c[2] == "COMPLETED" for c in step_b)
        completed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert completed

    async def test_graph_skips_non_pending_steps(self):
        engine = make_engine()
        sm, ws, analytics, db = _graph_env([_running_state()])
        sm.get_execution_state = AsyncMock(side_effect=lambda *a, **k: _running_state())
        engine.state_manager = sm
        workflow = {
            "id": "wf-g6",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [],
        }
        # Step already RUNNING → get_ready_steps must skip it → PARTIAL
        state = _running_state(a={"status": "RUNNING"})
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch.object(engine, "_execute_step", new=exec_mock):
            await engine._execute_workflow_graph(
                "ex-g6", workflow, state, ws, "user-1",
                start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
        exec_mock.assert_not_called()
        partial = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "PARTIAL"]
        assert partial


class TestRunExecutionGuards:
    def _env(self):
        sm = MagicMock()
        sm.get_execution_state = AsyncMock()
        sm.update_execution_status = AsyncMock()
        sm.update_step_status = AsyncMock()
        ws = MagicMock()
        ws.notify_workflow_status = AsyncMock()
        analytics = MagicMock()
        db = MagicMock()
        governance = MagicMock()
        governance.can_perform_action_async = AsyncMock(return_value={"allowed": True, "reason": "ok"})
        return sm, ws, analytics, db, governance

    def _step_state(self, n):
        calls = {"n": 0}

        def _state(*a, **k):
            calls["n"] += 1
            if calls["n"] <= n:
                return {"status": "RUNNING", "steps": {}, "input_data": {}, "outputs": {}}
            return {"status": "RUNNING", "steps": {"s1": {"status": "COMPLETED", "output": {}}},
                    "input_data": {}, "outputs": {}}

        return _state

    async def test_governance_fail_open(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        sm.get_execution_state = AsyncMock(side_effect=self._step_state(2))
        engine.state_manager = sm
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_engine.ServiceFactory.get_governance_service",
                   side_effect=RuntimeError("governance down")), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-gov", {"id": "wf-gov", "steps": [step_dict()]})
        # fail-open: step still executed, workflow COMPLETED
        assert exec_mock.call_count == 1
        completed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert completed

    async def test_step_record_create_failure_logged(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        sm.get_execution_state = AsyncMock(side_effect=self._step_state(2))
        engine.state_manager = sm
        db.add.side_effect = RuntimeError("db add boom")
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-rec", {"id": "wf-rec", "steps": [step_dict()]})
        assert exec_mock.call_count == 1
        completed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert completed

    async def test_snapshot_failure_logged(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        sm.get_execution_state = AsyncMock(side_effect=self._step_state(2))
        engine.state_manager = sm
        # First add (step exec record) succeeds; second (snapshot) raises
        add_calls = {"n": 0}

        def _add(obj):
            add_calls["n"] += 1
            if add_calls["n"] == 2:
                raise RuntimeError("snapshot boom")

        db.add.side_effect = _add
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-snap", {"id": "wf-snap", "steps": [step_dict()]})
        completed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert completed

    async def test_step_record_update_failure_logged(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        sm.get_execution_state = AsyncMock(side_effect=self._step_state(2))
        engine.state_manager = sm
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            status="running", start_time=None)
        db.commit.side_effect = RuntimeError("db commit boom")
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-upd", {"id": "wf-upd", "steps": [step_dict()]})
        completed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert completed

    async def test_failure_path_marketplace_tracking(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        sm.get_execution_state = AsyncMock(return_value={"status": "RUNNING", "steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=AsyncMock(side_effect=RuntimeError("boom"))), \
             patch("core.workflow_engine.MarketplaceUsageTracker.track_usage") as track, \
             patch("core.workflow_notifier.notifier.notify_failure", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-mkt", {"id": "wf-mkt", "created_from_template": "tmpl-1", "steps": [step_dict()]})
        track.assert_called_once()
        assert track.call_args.kwargs["success"] is False
        assert track.call_args.kwargs["item_id"] == "tmpl-1"

    async def test_outer_exception_marks_failed(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        calls = {"n": 0}

        def _update_status(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("status boom")
            return MagicMock()

        sm.update_execution_status = AsyncMock(side_effect=_update_status)
        sm.get_execution_state = AsyncMock(return_value={"status": "RUNNING", "steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-outer", {"id": "wf-outer", "steps": [step_dict()]})
        analytics.track_workflow_execution.assert_called_once()
        assert analytics.track_workflow_execution.call_args.kwargs["success"] is False


class TestArborRefinement:
    """run_workflow_with_arbor_refinement — full lifecycle with mocked exec."""

    def _workflow(self, n_steps=3, requires=True):
        steps = []
        for i in range(n_steps):
            cfg = {"service": "email", "action": "send"}
            if requires:
                cfg["requires"] = ["other"]
            steps.append({"id": f"s{i}", "name": f"S{i}", "type": "action", "config": cfg})
        return {"id": "wf-arbor", "name": "Arbor WF", "steps": steps}

    async def test_success_path(self):
        engine = make_engine()
        engine.start_workflow = AsyncMock(return_value="ex-arbor")
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "COMPLETED"})
        fake_db = MagicMock()
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine.run_workflow_with_arbor_refinement("t-1", self._workflow(requires=False), {"x": 1})
        assert result["success"] is True
        assert result["execution_id"] == "ex-arbor"
        assert result["promise_score"] > 0
        assert result["parallel_ratio"] == 1.0
        mock_persist.assert_called_once()
        args = mock_persist.call_args.args
        assert args[1] == result["tree_id"]
        assert args[3] == "t-1"
        assert args[4] == "workflow"

    async def test_failure_path_prunes_test_failed(self):
        engine = make_engine()
        engine.start_workflow = AsyncMock(return_value="ex-arbor")
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "FAILED", "error": "boom"})
        fake_db = MagicMock()
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine.run_workflow_with_arbor_refinement("t-1", self._workflow(), {})
        assert result["success"] is False
        assert result["promise_score"] == 0.0
        mock_persist.assert_called_once()

    async def test_exception_prunes_manual_and_reraises(self):
        engine = make_engine()
        engine.start_workflow = AsyncMock(side_effect=RuntimeError("exec boom"))
        fake_db = MagicMock()
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist:
            mock_session.return_value.__enter__.return_value = fake_db
            with pytest.raises(RuntimeError, match="exec boom"):
                await engine.run_workflow_with_arbor_refinement("t-1", self._workflow(), {})
        mock_persist.assert_called_once()

    async def test_previous_tree_negative_constraints_inherited(self):
        engine = make_engine()
        engine.start_workflow = AsyncMock(return_value="ex-arbor")
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "COMPLETED"})
        prev_record = SimpleNamespace(id="prev-1", negative_constraints=["nc-1", "nc-2"])
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = prev_record
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine.run_workflow_with_arbor_refinement(
                "t-1", self._workflow(requires=False), {}, previous_tree_id="prev-1")
        assert result["success"] is True
        tree = mock_persist.call_args.args[2]
        assert set(tree.negative_constraints) == {"nc-1", "nc-2"}

    async def test_low_parallel_ratio_uses_low_cost_potential(self):
        engine = make_engine()
        engine.start_workflow = AsyncMock(return_value="ex-arbor")
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "COMPLETED"})
        fake_db = MagicMock()
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine.run_workflow_with_arbor_refinement(
                "t-1", self._workflow(n_steps=4, requires=True), {})
        assert result["parallel_ratio"] == 0.0
        assert result["success"] is True
        tree = mock_persist.call_args.args[2]
        node = tree.nodes[tree.get_path_to_root(result["node_id"])[0]]
        assert node.cost_optimization_potential == 0.05

    async def test_polling_loop_break_on_empty_state(self):
        """get_execution_state returns None → poll breaks, run pruned TEST_FAILED."""
        engine = make_engine()
        engine.start_workflow = AsyncMock(return_value="ex-arbor")
        engine.state_manager.get_execution_state = AsyncMock(return_value=None)
        fake_db = MagicMock()
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine.run_workflow_with_arbor_refinement("t-1", self._workflow(requires=False), {})
        assert result["success"] is False
        assert result["execution_id"] == "ex-arbor"
        mock_persist.assert_called_once()

    async def test_polling_loop_sleep_continue(self):
        """Non-terminal status first → loop sleeps and re-polls (2698)."""
        engine = make_engine()
        engine.start_workflow = AsyncMock(return_value="ex-arbor")
        states = iter([{"status": "RUNNING"}, {"status": "COMPLETED"}])
        engine.state_manager.get_execution_state = AsyncMock(side_effect=lambda *a, **k: next(states))
        fake_db = MagicMock()
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist, \
             patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine.run_workflow_with_arbor_refinement("t-1", self._workflow(requires=False), {})
        assert result["success"] is True
        mock_sleep.assert_awaited_once()

    async def test_persist_failure_in_exception_path_swallowed(self):
        """_persist_tree raising inside the exception path is swallowed (2735-2736)."""
        engine = make_engine()
        engine.start_workflow = AsyncMock(side_effect=RuntimeError("exec boom"))
        fake_db = MagicMock()
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree",
                   side_effect=RuntimeError("persist boom")):
            mock_session.return_value.__enter__.return_value = fake_db
            with pytest.raises(RuntimeError, match="exec boom"):
                await engine.run_workflow_with_arbor_refinement("t-1", self._workflow(), {})

    async def test_graph_format_workflow_measures_converted_steps(self):
        """BUG (W29): arbor measured workflow['steps'] BEFORE start_workflow
        normalized nodes→steps, so graph-format workflows always reported
        parallel_ratio=0 and zero estimated latency. Must measure the
        converted step list."""
        engine = make_engine()
        engine.start_workflow = AsyncMock(return_value="ex-arbor")
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "COMPLETED"})
        fake_db = MagicMock()
        workflow = {
            "id": "wf-arbor-graph",
            "name": "Arbor Graph WF",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
                {"id": "b", "title": "B", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [{"source": "a", "target": "b"}],
        }
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.hypothesis_tree_endpoints._persist_tree") as mock_persist:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine.run_workflow_with_arbor_refinement("t-1", workflow, {})
        assert result["success"] is True
        # both steps have no requires → both parallelizable → ratio 1.0
        assert result["parallel_ratio"] == 1.0
        tree = mock_persist.call_args.args[2]
        node = tree.nodes[tree.get_path_to_root(result["node_id"])[0]]
        assert node.estimated_latency_ms == 250.0 * 2
        # start_workflow must receive the normalized workflow
        engine.start_workflow.assert_awaited_once()
        assert len(engine.start_workflow.call_args.args[0]["steps"]) == 2


class TestExecutorEdges:
    async def test_slack_get_channel_history_success(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.get_channel_history",
                   create=True, new=AsyncMock(return_value={"messages": []})):
            result = await engine._execute_slack_action("get_channel_history", {"channel_id": "c"}, "c1")
        assert result["status"] == "success"
        assert result["result"] == {"messages": []}

    async def test_gmail_send_email_no_token(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(Exception, match="Gmail authentication"):
                await engine._execute_gmail_action("send_email", {}, None)

    async def test_gmail_token_fallback_to_google(self):
        """connection_id lookup empty → falls back to 'google' token store (1746)."""
        engine = make_engine()
        tokens = {"google": {"access_token": "g-tok"}}
        with patch("core.workflow_engine.token_storage.get_token",
                   side_effect=lambda conn: tokens.get(conn)), \
             patch("integrations.gmail_service.GmailService.send_message",
                   create=True, new=MagicMock(return_value={"id": "msg-1"})):
            result = await engine._execute_gmail_action("send_email", {"to": "a@b.c", "subject": "s", "body": "b"}, "c1")
        assert result["authenticated"] is True
        assert result["result"]["id"] == "msg-1"

    async def test_gmail_create_draft_no_token(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(Exception, match="Gmail authentication"):
                await engine._execute_gmail_action("create_draft", {}, None)

    async def test_github_exception_reraises(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.github_service.GitHubService", side_effect=RuntimeError("gh down")):
            with pytest.raises(RuntimeError, match="gh down"):
                await engine._execute_github_action("create_issue", {}, "c1")

    async def test_zoom_exception_reraises(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.zoom_service.ZoomService", side_effect=RuntimeError("zoom down")):
            with pytest.raises(RuntimeError, match="zoom down"):
                await engine._execute_zoom_action("create_meeting", {}, "c1")

    async def test_notion_exception_reraises(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.notion_service.NotionService", side_effect=RuntimeError("notion down")):
            with pytest.raises(RuntimeError, match="notion down"):
                await engine._execute_notion_action("create_page", {}, "c1")

    async def test_zoho_unknown_actions(self):
        engine = make_engine()
        for executor, name in [
            ("_execute_zoho_crm_action", "Zoho CRM"),
            ("_execute_zoho_books_action", "Zoho Books"),
            ("_execute_zoho_inventory_action", "Zoho Inventory"),
        ]:
            with pytest.raises(ValueError, match=f"Unknown {name} action"):
                await getattr(engine, executor)("nonexistent_action", {}, None)

    async def test_zoho_sync_method_calls(self):
        """Zoho executors call sync methods via plain invocation (2405/2435/2464)."""
        engine = make_engine()
        for executor, module, cls in [
            ("_execute_zoho_crm_action", "integrations.zoho_crm_service", "ZohoCRMService"),
            ("_execute_zoho_books_action", "integrations.zoho_books_service", "ZohoBooksService"),
            ("_execute_zoho_inventory_action", "integrations.zoho_inventory_service", "ZohoInventoryService"),
        ]:
            service = MagicMock()
            service.list_records.return_value = {"records": []}
            with patch(f"{module}.{cls}", return_value=service):
                result = await getattr(engine, executor)("list_records", {"page": 1}, None)
            assert result["status"] == "success"
            assert result["result"] == {"records": []}
