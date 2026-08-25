"""Coverage wave 21 — core/workflow_engine.py (TDD).

Targets the largest module in the repo (2766 lines, ~39% covered by the
existing suites). This suite drives the deterministic helpers, the
_execute_step dispatcher, the service executors (mocked token storage +
integration services — no network), and the run-level loop (mocked
state/ws/db/analytics).

Also repairs one stale test: test_topological_sort_with_cycle expected
graceful continuation but the code raises ValueError on cycles (documented
contract) — repaired to assert the new contract.
"""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.workflow_engine import (
    MissingInputError,
    SchemaValidationError,
    StepTimeoutError,
    WorkflowEngine,
)


def make_engine():
    sm = MagicMock()
    with patch("core.workflow_engine.get_state_manager", return_value=sm):
        engine = WorkflowEngine()
    engine.state_manager = sm
    return engine


def step_dict(**overrides):
    step = {
        "id": "s1",
        "name": "Step 1",
        "service": "email",
        "action": "send",
        "parameters": {},
        "continue_on_error": False,
        "timeout": None,
        "input_schema": {},
        "output_schema": {},
    }
    step.update(overrides)
    return step


# ---------------------------------------------------------------------------
# Part A — deterministic helpers
# ---------------------------------------------------------------------------


class TestCheckDependencies:
    def test_all_dependencies_met(self):
        engine = make_engine()
        state = {"steps": {"a": {"status": "COMPLETED"}, "b": {"status": "COMPLETED"}}}
        step = {"depends_on": ["a", "b"]}
        assert engine._check_dependencies(step, state) is True

    def test_missing_dependency(self):
        engine = make_engine()
        state = {"steps": {"a": {"status": "COMPLETED"}, "b": {"status": "RUNNING"}}}
        step = {"depends_on": ["a", "b"]}
        assert engine._check_dependencies(step, state) is False

    def test_no_dependencies(self):
        engine = make_engine()
        assert engine._check_dependencies({}, {}) is True


class TestEvaluateCondition:
    def test_empty_condition_always_true(self):
        engine = make_engine()
        assert engine._evaluate_condition("", {}) is True
        assert engine._evaluate_condition(None, {}) is True

    def test_variable_not_found_returns_false(self):
        engine = make_engine()
        assert engine._evaluate_condition("${missing.key} == 1", {}) is False

    def test_string_variable_comparison(self):
        engine = make_engine()
        state = {"outputs": {"step1": {"status": "completed"}}}
        assert engine._evaluate_condition("${step1.status} == 'completed'", state) is True

    def test_numeric_variable_comparison(self):
        engine = make_engine()
        state = {"input_data": {"count": 7}}
        assert engine._evaluate_condition("${input.count} > 5", state) is True
        assert engine._evaluate_condition("${input.count} < 5", state) is False

    def test_bool_and_float_values(self):
        engine = make_engine()
        state = {"outputs": {"s": {"flag": True, "score": 3.5}}}
        assert engine._evaluate_condition("${s.flag} == true", state) is True
        assert engine._evaluate_condition("${s.score} >= 3.0", state) is True

    def test_complex_object_uses_repr(self):
        engine = make_engine()
        state = {"outputs": {"s": {"data": {"k": 1}}}}
        # dict values are repr'd into the expression — but safe_eval forbids
        # function calls, so any expression requiring them evaluates False
        # (fail-safe). The important contract: no crash, and False returned.
        result = engine._evaluate_condition("len(${s.data}) == 1", state)
        assert result is False

    def test_non_boolean_result_truthiness(self):
        engine = make_engine()
        state = {"input_data": {"name": "atom"}}
        assert engine._evaluate_condition("${input.name}", state) is True

    def test_safe_eval_blocks_code_injection(self):
        engine = make_engine()
        state = {"input_data": {"payload": "x"}}
        assert engine._evaluate_condition("${input.payload}.__class__", state) is False

    def test_exception_falls_back_to_false(self):
        engine = make_engine()
        # invalid python → safe_eval raises → False
        assert engine._evaluate_condition("not valid python !!!", {}) is False


class TestResolveParameterValue:
    def test_plain_value_passthrough(self):
        engine = make_engine()
        assert engine._resolve_parameter_value(42, {}) == 42
        assert engine._resolve_parameter_value(None, {}) is None
        assert engine._resolve_parameter_value("no refs", {}) == "no refs"

    def test_dict_and_list_recursion(self):
        engine = make_engine()
        state = {"input_data": {"x": 5}}
        params = {"nested": {"a": "${input.x}", "b": [1, "${input.x}"]}}
        resolved = engine._resolve_parameter_value(params, state)
        assert resolved == {"nested": {"a": 5, "b": [1, 5]}}

    def test_pure_single_reference_preserves_type(self):
        engine = make_engine()
        state = {"outputs": {"step1": {"count": 3}}}
        assert engine._resolve_parameter_value("${step1.count}", state) == 3

    def test_pure_reference_missing_raises(self):
        engine = make_engine()
        with pytest.raises(MissingInputError) as exc_info:
            engine._resolve_parameter_value("${ghost.path}", {})
        assert exc_info.value.missing_var == "ghost.path"

    def test_interpolation_multiple_variables(self):
        engine = make_engine()
        state = {"input_data": {"greeting": "Hi", "name": "World"}}
        assert (
            engine._resolve_parameter_value("${input.greeting} ${input.name}!", state)
            == "Hi World!"
        )

    def test_interpolation_missing_raises(self):
        engine = make_engine()
        with pytest.raises(MissingInputError):
            engine._resolve_parameter_value("prefix ${ghost.x} suffix", {})

    def test_resolve_parameters_maps_keys(self):
        engine = make_engine()
        state = {"input_data": {"v": 1}}
        assert engine._resolve_parameters({"a": "${input.v}"}, state) == {"a": 1}


class TestPathHelpers:
    def test_path_exists_input(self):
        engine = make_engine()
        state = {"input_data": {"a": {"b": None}}}
        assert engine._path_exists("input.a.b", state) is True
        assert engine._path_exists("input.a.c", state) is False

    def test_path_exists_output(self):
        engine = make_engine()
        state = {"outputs": {"s": {"v": 1}}}
        assert engine._path_exists("s.v", state) is True
        assert engine._path_exists("missing.v", state) is False
        assert engine._path_exists("s.non_dict.x", {"outputs": {"s": "str"}}) is False

    def test_get_value_input(self):
        engine = make_engine()
        state = {"input_data": {"a": {"b": "val"}}}
        assert engine._get_value_from_path("input.a.b", state) == "val"

    def test_get_value_output(self):
        engine = make_engine()
        state = {"outputs": {"s": {"v": [1, 2]}}}
        assert engine._get_value_from_path("s.v", state) == [1, 2]

    def test_get_value_missing_returns_none(self):
        engine = make_engine()
        assert engine._get_value_from_path("ghost.v", {}) is None
        assert engine._get_value_from_path("s.x", {"outputs": {"s": 5}}) is None


class TestSchemaValidation:
    def test_no_schema_noop(self):
        engine = make_engine()
        engine._validate_input_schema({"input_schema": None}, {})
        engine._validate_output_schema({"output_schema": {}}, {})

    def test_valid_schema_passes(self):
        engine = make_engine()
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        engine._validate_input_schema({"id": "s", "input_schema": schema}, {"x": 1})

    def test_invalid_input_schema_raises(self):
        engine = make_engine()
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
        with pytest.raises(SchemaValidationError) as exc_info:
            engine._validate_input_schema({"id": "s1", "input_schema": schema}, {})
        assert exc_info.value.schema_type == "input"
        assert "s1" in str(exc_info.value)

    def test_invalid_output_schema_raises(self):
        engine = make_engine()
        schema = {"type": "object", "properties": {"y": {"type": "string"}}, "required": ["y"]}
        with pytest.raises(SchemaValidationError) as exc_info:
            engine._validate_output_schema({"id": "s2", "output_schema": schema}, {"y": 5})
        assert exc_info.value.schema_type == "output"
        assert exc_info.value.errors


class TestGetToken:
    def test_no_connection_id(self):
        engine = make_engine()
        assert engine._get_token(None, "slack") is None

    def test_connection_hit(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "tok"}):
            assert engine._get_token("conn-1", "slack") == "tok"

    def test_connection_miss_falls_back_to_service_name(self):
        engine = make_engine()
        side_effect = {"conn-1": None, "slack": {"access_token": "fb"}}

        def _get(ident):
            return side_effect[ident]

        with patch("core.workflow_engine.token_storage.get_token", side_effect=_get):
            assert engine._get_token("conn-1", "slack") == "fb"

    def test_no_token_data(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            assert engine._get_token("conn-1", "slack") is None


class TestGraphBuilders:
    def test_build_execution_graph(self):
        engine = make_engine()
        workflow = {
            "nodes": [{"id": "a"}, {"id": "b"}],
            "connections": [
                {"source": "a", "target": "b", "condition": "${x} > 1"},
                {"source": "ghost", "target": "a"},  # ignored (unknown source)
            ],
        }
        graph = engine._build_execution_graph(workflow)
        assert set(graph["nodes"]) == {"a", "b"}
        assert graph["adjacency"]["a"] == [workflow["connections"][0]]
        assert graph["reverse_adjacency"]["b"] == [workflow["connections"][0]]

    def test_has_conditional_connections(self):
        engine = make_engine()
        assert engine._has_conditional_connections({"connections": [{"source": "a", "target": "b"}]}) is False
        assert engine._has_conditional_connections({"connections": [{"source": "a", "target": "b", "condition": "1"}]}) is True
        assert engine._has_conditional_connections({}) is False

    def test_convert_nodes_skips_malformed_connection(self):
        engine = make_engine()
        workflow = {
            "nodes": [{"id": "a", "title": "A", "config": {}}, {"id": "b", "title": "B", "config": {}}],
            "connections": [{"source": None, "target": "b"}, {"source": "a"}, {}],
        }
        steps = engine._convert_nodes_to_steps(workflow)
        assert len(steps) == 2
        assert steps[0]["sequence_order"] == 1
        assert steps[1]["sequence_order"] == 2

    def test_convert_nodes_steps_shape(self):
        engine = make_engine()
        workflow = {
            "nodes": [{"id": "n1", "title": "Node", "type": "action", "config": {
                "service": "svc", "action": "act", "parameters": {"p": 1},
                "continue_on_error": True, "timeout": 5, "input_schema": {}, "output_schema": {}}}],
            "connections": [],
        }
        steps = engine._convert_nodes_to_steps(workflow)
        assert steps[0]["id"] == "n1"
        assert steps[0]["service"] == "svc"
        assert steps[0]["action"] == "act"
        assert steps[0]["parameters"] == {"p": 1}
        assert steps[0]["continue_on_error"] is True


# ---------------------------------------------------------------------------
# Part B — _execute_step dispatcher
# ---------------------------------------------------------------------------


class TestExecuteStep:
    async def test_registry_executor_success(self):
        engine = make_engine()
        with patch.object(engine, "_execute_email_action", new=AsyncMock(return_value={"ok": True})):
            output = await engine._execute_step(step_dict(), {})
        assert output["status"] == "success"
        assert output["execution_method"] == "service_registry"
        assert output["result"] == {"ok": True}

    async def test_non_success_envelope_raises(self):
        engine = make_engine()
        with patch.object(engine, "_execute_email_action", new=AsyncMock(return_value={"status": "timeout", "error": "slow"})):
            with pytest.raises(Exception, match="slow"):
                await engine._execute_step(step_dict(), {})

    async def test_timeout_raises_step_timeout(self):
        engine = make_engine()

        async def slow_executor(action, params, connection_id=None, **kwargs):
            await asyncio.sleep(2)
            return {"ok": True}

        step = step_dict(timeout=0.05)
        with patch.object(engine, "_execute_email_action", new=slow_executor):
            with pytest.raises(StepTimeoutError) as exc_info:
                await engine._execute_step(step, {})
        assert exc_info.value.step_id == "s1"
        assert exc_info.value.timeout == 0.05

    async def test_unknown_service_generic_success(self):
        engine = make_engine()
        with patch.object(engine, "_execute_generic_action", new=AsyncMock(return_value={"done": True})):
            output = await engine._execute_step(step_dict(service="custom_svc"), {})
        assert output["execution_method"] == "generic_catalog_executor"
        assert output["result"] == {"done": True}

    async def test_unknown_service_generic_fails_fallback_used(self):
        engine = make_engine()
        step = step_dict(service="custom_svc", fallback_service="email")

        async def generic_fail(service_name, action_name, params, connection_id=None):
            raise ValueError("not in catalog")

        with patch.object(engine, "_execute_generic_action", new=generic_fail), \
             patch.object(engine, "_execute_email_action", new=AsyncMock(return_value={"ok": 1})):
            output = await engine._execute_step(step, {})
        assert output["execution_method"] == "fallback_service"
        assert output["fallback_used"] is True
        assert output["original_service"] == "custom_svc"

    async def test_unknown_service_generic_fails_no_fallback_raises(self):
        engine = make_engine()

        async def generic_fail(service_name, action_name, params, connection_id=None):
            raise ValueError("not in catalog")

        with patch.object(engine, "_execute_generic_action", new=generic_fail):
            with pytest.raises(ValueError, match="Unknown service"):
                await engine._execute_step(step_dict(service="custom_svc"), {})

    async def test_executor_raises_fallback_succeeds(self):
        engine = make_engine()

        async def failing(action, params, connection_id=None, **kwargs):
            raise RuntimeError("boom")

        with patch.object(engine, "_execute_slack_action", new=failing), \
             patch.object(engine, "_execute_email_action", new=AsyncMock(return_value={"ok": True})):
            output = await engine._execute_step(step_dict(service="slack", fallback_service="email"), {})
        assert output["fallback_used"] is True

    async def test_both_fail_raises_combined_error(self):
        engine = make_engine()

        async def failing(action, params, connection_id=None, **kwargs):
            raise RuntimeError("primary fail")

        async def failing_fb(action, params, connection_id=None, **kwargs):
            raise RuntimeError("fallback fail")

        with patch.object(engine, "_execute_slack_action", new=failing), \
             patch.object(engine, "_execute_email_action", new=failing_fb):
            with pytest.raises(ValueError, match="fallback") as exc_info:
                await engine._execute_step(step_dict(service="slack", fallback_service="email"), {})
        assert "primary" in str(exc_info.value)

    async def test_fallback_non_success_envelope_raises(self):
        engine = make_engine()

        async def failing(action, params, connection_id=None, **kwargs):
            raise RuntimeError("primary fail")

        with patch.object(engine, "_execute_slack_action", new=failing), \
             patch.object(engine, "_execute_email_action", new=AsyncMock(return_value={"status": "error", "error": "nope"})):
            with pytest.raises(ValueError, match="nope"):
                await engine._execute_step(step_dict(service="slack", fallback_service="email"), {})

    async def test_no_fallback_raises_primary(self):
        engine = make_engine()

        async def failing(action, params, connection_id=None, **kwargs):
            raise RuntimeError("only primary")

        with patch.object(engine, "_execute_slack_action", new=failing):
            with pytest.raises(RuntimeError, match="only primary"):
                await engine._execute_step(step_dict(service="slack"), {})

    async def test_mcp_step_kwarg_passed(self):
        engine = make_engine()
        captured = {}

        async def mcp_executor(action, params, connection_id=None, **kwargs):
            captured["kwargs"] = kwargs
            return {"status": "success"}

        with patch.object(engine, "_execute_mcp_action", new=mcp_executor):
            await engine._execute_step(step_dict(service="mcp", execution_id="ex-1"), {})
        assert captured["kwargs"] == {"step": step_dict(service="mcp", execution_id="ex-1")}


# ---------------------------------------------------------------------------
# Part C — service executors
# ---------------------------------------------------------------------------


class TestSimpleExecutors:
    @pytest.mark.parametrize("service", ["email", "calendar", "database", "webhook", "ai"])
    def test_simple_executors(self, service):
        engine = make_engine()
        executor = getattr(engine, f"_execute_{service}_action")
        result = asyncio.run(executor("any_action", {"x": 1}, "conn-1"))
        assert result["status"] == "success"
        assert result["action"] == "any_action"


class TestSlackExecutor:
    def _token(self, token_data):
        return patch("core.workflow_engine.token_storage.get_token", return_value=token_data)

    async def test_no_token_raises_auth_error(self):
        engine = make_engine()
        with self._token(None):
            with pytest.raises(Exception, match="Slack authentication"):
                await engine._execute_slack_action("chat_postMessage", {}, None)

    async def test_chat_post_message(self):
        engine = make_engine()
        with self._token({"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.post_message", create=True, new=AsyncMock(return_value={"ok": True})):
            result = await engine._execute_slack_action("chat_postMessage", {"channel": "c", "text": "hi"}, "c1")
        assert result["authenticated"] is True

    async def test_list_channels_and_users(self):
        engine = make_engine()
        with self._token({"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.list_channels", create=True, new=AsyncMock()), \
             patch("integrations.slack_service_unified.slack_unified_service.get_team_info", create=True, new=AsyncMock()):
            await engine._execute_slack_action("list_channels", {}, "c1")
            await engine._execute_slack_action("chat_getUsers", {}, "c1")

    async def test_get_channel_info_missing_param(self):
        engine = make_engine()
        with self._token({"access_token": "t"}):
            with pytest.raises(ValueError, match="channel_id is required for get_channel_info"):
                await engine._execute_slack_action("get_channel_info", {}, "c1")

    async def test_get_channel_info_success(self):
        engine = make_engine()
        with self._token({"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.get_channel_info", create=True, new=AsyncMock(return_value={"id": "c"})):
            result = await engine._execute_slack_action("get_channel_info", {"channel_id": "c"}, "c1")
        assert result["result"] == {"id": "c"}

    async def test_get_channel_history_missing_param(self):
        engine = make_engine()
        with self._token({"access_token": "t"}):
            with pytest.raises(ValueError, match="channel_id is required for get_channel_history"):
                await engine._execute_slack_action("get_channel_history", {}, "c1")

    async def test_update_message_missing_param(self):
        engine = make_engine()
        with self._token({"access_token": "t"}):
            with pytest.raises(ValueError, match="update_message"):
                await engine._execute_slack_action("update_message", {"channel_id": "c"}, "c1")

    async def test_update_message_success(self):
        engine = make_engine()
        with self._token({"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.update_message", create=True, new=AsyncMock(return_value={"ok": True})):
            result = await engine._execute_slack_action("update_message", {"channel_id": "c", "message_ts": "1.1", "text": "new"}, "c1")
        assert result["status"] == "success"

    async def test_delete_message(self):
        engine = make_engine()
        with self._token({"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.delete_message", create=True, new=AsyncMock(return_value={"ok": True})):
            result = await engine._execute_slack_action("delete_message", {"channel_id": "c", "message_ts": "1.1"}, "c1")
        assert result["status"] == "success"
        with self._token({"access_token": "t"}):
            with pytest.raises(ValueError, match="delete_message"):
                await engine._execute_slack_action("delete_message", {"channel_id": "c"}, "c1")

    async def test_search_messages(self):
        engine = make_engine()
        with self._token({"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.search_messages", create=True, new=AsyncMock(return_value={"messages": []})):
            result = await engine._execute_slack_action("search_messages", {"query": "q"}, "c1")
        assert result["status"] == "success"
        with self._token({"access_token": "t"}):
            with pytest.raises(ValueError, match="query is required"):
                await engine._execute_slack_action("search_messages", {}, "c1")

    async def test_files_list(self):
        engine = make_engine()
        with self._token({"access_token": "t"}), \
             patch("integrations.slack_service_unified.slack_unified_service.list_files", create=True, new=AsyncMock(return_value={"files": []})):
            result = await engine._execute_slack_action("files_list", {"channel_id": "c"}, "c1")
        assert result["status"] == "success"

    async def test_upload_external_and_reactions(self):
        engine = make_engine()
        with self._token({"access_token": "t"}):
            result = await engine._execute_slack_action("files_get_upload_url_external", {}, "c1")
            assert result["result"]["ok"] is False
            result = await engine._execute_slack_action("reactions_add", {}, "c1")
            assert result["result"]["ok"] is False

    async def test_unknown_action(self):
        engine = make_engine()
        with self._token({"access_token": "t"}):
            with pytest.raises(ValueError, match="Unsupported Slack action"):
                await engine._execute_slack_action("nope", {}, "c1")

    async def test_fallback_token_lookup_by_service_name(self):
        engine = make_engine()
        side_effect = {"c1": None, "slack": {"access_token": "fb"}}

        def _get(ident):
            return side_effect.get(ident)

        with patch("core.workflow_engine.token_storage.get_token", side_effect=_get), \
             patch("integrations.slack_service_unified.slack_unified_service.post_message", create=True, new=AsyncMock()):
            result = await engine._execute_slack_action("chat_postMessage", {"channel": "c", "text": "x"}, "c1")
        assert result["authenticated"] is True


class TestAsanaExecutor:
    async def test_no_token_raises(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value=None), \
             patch.dict(os.environ, {}, clear=False), \
             patch("core.workflow_engine.os.getenv", return_value=None):
            with pytest.raises(Exception, match="Asana authentication"):
                await engine._execute_asana_action("create_task", {}, None)

    async def test_create_task(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.asana_service.asana_service.create_task", create=True, new=AsyncMock(return_value={"gid": "1"})):
            result = await engine._execute_asana_action(
                "create_task", {"name": "n", "workspace": "w", "notes": "n", "due_on": "2026-01-01", "assignee": "a"}, None)
        assert result["result"] == {"gid": "1"}

    async def test_get_tasks_and_projects(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.asana_service.asana_service.get_tasks", create=True, new=AsyncMock(return_value=[])), \
             patch("integrations.asana_service.asana_service.get_projects", create=True, new=AsyncMock(return_value=[])):
            await engine._execute_asana_action("get_tasks", {"project": "p"}, None)
            await engine._execute_asana_action("get_projects", {"workspace": "w"}, None)

    async def test_update_task(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.asana_service.asana_service.update_task", create=True, new=AsyncMock(return_value={"gid": "1"})):
            result = await engine._execute_asana_action("update_task", {"task_gid": "1", "completed": True}, None)
        assert result["status"] == "success"
        with pytest.raises(ValueError, match="task_gid is required"):
            await engine._execute_asana_action("update_task", {}, None)

    async def test_add_comment(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.asana_service.asana_service.add_task_comment", create=True, new=AsyncMock(return_value={"gid": "c"})):
            result = await engine._execute_asana_action("add_comment", {"task_gid": "1", "text": "hi"}, None)
        assert result["status"] == "success"
        with pytest.raises(ValueError, match="add_comment"):
            await engine._execute_asana_action("add_comment", {"task_gid": "1"}, None)

    async def test_get_workspaces_and_users(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.asana_service.asana_service.get_workspaces", create=True, new=AsyncMock(return_value=[])), \
             patch("integrations.asana_service.asana_service.get_users", create=True, new=AsyncMock(return_value=[])):
            await engine._execute_asana_action("get_workspaces", {}, None)
            await engine._execute_asana_action("get_users", {"workspace": "w"}, None)
        with pytest.raises(ValueError, match="workspace is required for get_users"):
            await engine._execute_asana_action("get_users", {}, None)

    async def test_get_teams(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.asana_service.asana_service.get_teams", create=True, new=AsyncMock(return_value=[])):
            await engine._execute_asana_action("get_teams", {"workspace": "w"}, None)
        with pytest.raises(ValueError, match="workspace is required for get_teams"):
            await engine._execute_asana_action("get_teams", {}, None)

    async def test_search_tasks(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.asana_service.asana_service.search_tasks", create=True, new=AsyncMock(return_value=[])):
            await engine._execute_asana_action("search_tasks", {"workspace": "w", "query": "q"}, None)
        with pytest.raises(ValueError, match="search_tasks"):
            await engine._execute_asana_action("search_tasks", {"workspace": "w"}, None)

    async def test_create_project_not_implemented(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"):
            result = await engine._execute_asana_action("create_project", {}, None)
        assert result["result"]["ok"] is False

    async def test_unknown_action(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"):
            with pytest.raises(ValueError, match="Unsupported Asana action"):
                await engine._execute_asana_action("nope", {}, None)

    async def test_env_token_fallback(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value=None), \
             patch("core.workflow_engine.os.getenv", return_value="envtok"), \
             patch("integrations.asana_service.asana_service.get_workspaces", create=True, new=AsyncMock(return_value=[])):
            result = await engine._execute_asana_action("get_workspaces", {}, None)
        assert result["authenticated"] is True


class TestDiscordExecutor:
    async def test_no_auth_raises(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value=None), \
             patch("integrations.discord_service.discord_service.bot_token", "", create=True):
            with pytest.raises(Exception, match="Discord authentication"):
                await engine._execute_discord_action("send_message", {}, None)

    async def test_send_message_with_bot(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value=None), \
             patch("integrations.discord_service.discord_service.bot_token", "bottok", create=True), \
             patch("integrations.discord_service.discord_service.send_message", create=True, new=AsyncMock(return_value={"id": "m"})):
            result = await engine._execute_discord_action("send_message", {"channel_id": "c", "content": "x"}, None)
        assert result["status"] == "success"

    async def test_send_message_with_token(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.discord_service.discord_service.send_message", create=True, new=AsyncMock(return_value={"id": "m"})):
            result = await engine._execute_discord_action("send_message", {"channel_id": "c", "content": "x"}, "c1")
        assert result["authenticated"] is True

    async def test_other_action_simulated(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"):
            result = await engine._execute_discord_action("get_guilds", {}, "c1")
        assert result["status"] == "success"


class TestHubspotExecutor:
    async def test_no_auth_raises(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value=None), \
             patch("integrations.hubspot_service.HubSpotService.access_token", "", create=True):
            with pytest.raises(Exception, match="HubSpot authentication"):
                await engine._execute_hubspot_action("create_contact", {}, None)

    async def test_create_contact_and_deal(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.hubspot_service.HubSpotService.create_contact", create=True, new=AsyncMock(return_value={"id": "c"})), \
             patch("integrations.hubspot_service.HubSpotService.create_deal", create=True, new=AsyncMock(return_value={"id": "d"})):
            r1 = await engine._execute_hubspot_action("create_contact", {"email": "e@x.com", "firstname": "F"}, None)
            r2 = await engine._execute_hubspot_action("create_deal", {"dealname": "D", "amount": "10"}, None)
        assert r1["status"] == "success"
        assert r2["status"] == "success"

    async def test_other_action_simulated(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"):
            result = await engine._execute_hubspot_action("list_deals", {}, None)
        assert result["status"] == "success"


class TestSalesforceExecutor:
    async def test_no_auth_raises(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(Exception, match="Salesforce authentication"):
                await engine._execute_salesforce_action("create_lead", {}, "c1")

    async def test_create_lead_and_contact(self):
        engine = make_engine()
        client = MagicMock()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t", "instance_url": "https://x"}):
            with patch("integrations.salesforce_service.SalesforceService.create_client", create=True, return_value=client):
                with patch("integrations.salesforce_service.SalesforceService.create_lead", create=True, new=AsyncMock(return_value={"id": "l"})), \
                     patch("integrations.salesforce_service.SalesforceService.create_contact", create=True, new=AsyncMock(return_value={"id": "c"})):
                    r1 = await engine._execute_salesforce_action("create_lead", {"lastname": "L"}, "c1")
                    r2 = await engine._execute_salesforce_action("create_contact", {"lastname": "L"}, "c1")
        assert r1["status"] == "success"
        assert r2["status"] == "success"

    async def test_create_opportunity_and_other(self):
        engine = make_engine()
        client = MagicMock()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t", "instance_url": "https://x"}):
            with patch("integrations.salesforce_service.SalesforceService.create_client", create=True, return_value=client), \
                 patch("integrations.salesforce_service.SalesforceService.create_opportunity", create=True, new=AsyncMock(return_value={"id": "o"})):
                r1 = await engine._execute_salesforce_action("create_opportunity", {"name": "N", "stage": "S", "closedate": "2026-01-01"}, "c1")
                r2 = await engine._execute_salesforce_action("list_accounts", {}, "c1")
        assert r1["status"] == "success"
        assert r2["status"] == "success"


class TestGithubExecutor:
    async def test_create_issue(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"):
            with patch("integrations.github_service.GitHubService.create_issue", return_value={"id": 1}):
                result = await engine._execute_github_action("create_issue", {"owner": "o", "repo": "r", "title": "t", "body": "b"}, None)
        assert result["status"] == "success"

    async def test_other_action_simulated(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value=None):
            result = await engine._execute_github_action("list_repos", {}, None)
        assert result["status"] == "success"


class TestZoomNotionExecutors:
    async def test_zoom_create_meeting(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"), \
             patch("integrations.zoom_service.ZoomService.create_meeting", create=True, new=AsyncMock(return_value={"id": "m"})):
            result = await engine._execute_zoom_action("create_meeting", {"topic": "t"}, None)
        assert result["status"] == "success"

    async def test_zoom_other(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"):
            result = await engine._execute_zoom_action("list_meetings", {}, None)
        assert result["status"] == "success"

    async def test_notion_create_page(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value="t"):
            with patch("integrations.notion_service.NotionService.create_page", return_value={"id": "p"}):
                result = await engine._execute_notion_action("create_page", {"parent": {"database_id": "d"}, "properties": {}}, None)
        assert result["status"] == "success"

    async def test_notion_other(self):
        engine = make_engine()
        with patch.object(engine, "_get_token", return_value=None):
            result = await engine._execute_notion_action("list_databases", {}, None)
        assert result["status"] == "success"


class TestGmailExecutor:
    async def test_send_email_no_token_raises(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(Exception, match="Gmail authentication"):
                await engine._execute_gmail_action("send_email", {}, None)

    async def test_send_email_success(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.gmail_service.GmailService.send_message", create=True, return_value={"id": "m"}):
            result = await engine._execute_gmail_action("send_email", {"to": "a@b.c", "subject": "s", "body": "b"}, "c1")
        assert result["status"] == "success"

    async def test_send_email_falsy_result_raises_external_error(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.gmail_service.GmailService.send_message", create=True, return_value=None):
            with pytest.raises(Exception, match="Failed to send email"):
                await engine._execute_gmail_action("send_email", {"to": "a@b.c", "subject": "s", "body": "b"}, "c1")

    async def test_create_draft(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.gmail_service.GmailService.draft_message", create=True, return_value={"id": "d"}):
            result = await engine._execute_gmail_action("create_draft", {"to": "a@b.c"}, "c1")
        assert result["status"] == "success"

    async def test_other_action_simulated(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}):
            result = await engine._execute_gmail_action("list_threads", {}, "c1")
        assert result["status"] == "success"


class TestMcpExecutor:
    async def test_missing_server_id_returns_error(self):
        engine = make_engine()
        result = await engine._execute_mcp_action("run", {"tool_name": "x"}, None)
        assert result["status"] == "error"

    async def test_success_with_step_context(self):
        engine = make_engine()
        with patch("integrations.mcp_service.mcp_service.call_tool", new=AsyncMock(return_value={"output": "ok"})):
            result = await engine._execute_mcp_action(
                "run", {"server_id": "srv", "tool_name": "tool", "arguments": {"a": 1}},
                None, step={"execution_id": "ex-1", "workspace_id": "ws", "tenant_id": "tnt", "agent_id": "ag", "tier": "AUTONOMOUS"})
        assert result["status"] == "success"
        assert result["result"] == {"output": "ok"}

    async def test_exception_returns_error_envelope(self):
        engine = make_engine()
        with patch("integrations.mcp_service.mcp_service.call_tool", new=AsyncMock(side_effect=RuntimeError("gate blocked"))):
            result = await engine._execute_mcp_action("run", {"server_id": "srv"}, None, step=None)
        assert result["status"] == "error"
        assert "MCP action failed" in result["error"]


class TestMainAgentExecutor:
    async def test_with_mcp_servers(self):
        engine = make_engine()
        with patch("integrations.mcp_service.mcp_service.get_active_connections", new=AsyncMock(return_value=[
            {"server_id": "srv", "connected_at": "now"}
        ])), patch("integrations.mcp_service.mcp_service.get_server_tools", new=AsyncMock(return_value=[
            {"name": "t1", "description": "d", "input_schema": {}}
        ])), patch.object(engine, "_execute_agent_with_mcp", new=AsyncMock(return_value={"success": True})):
            result = await engine._execute_main_agent_action("do_thing", {"mcp_servers": ["srv"], "input_data": {"x": 1}}, None)
        assert result["status"] == "success"
        assert result["mcp_servers_used"] == ["srv"]

    async def test_without_mcp_servers(self):
        engine = make_engine()
        with patch.object(engine, "_execute_agent_with_mcp", new=AsyncMock(return_value={"success": True})):
            result = await engine._execute_main_agent_action("do_thing", {}, None)
        assert result["status"] == "success"
        assert result["mcp_servers_used"] == []

    async def test_exception_returns_error_envelope(self):
        engine = make_engine()
        with patch.object(engine, "_execute_agent_with_mcp", new=AsyncMock(side_effect=RuntimeError("nope"))):
            result = await engine._execute_main_agent_action("do_thing", {}, None)
        assert result["status"] == "error"


class TestAgentWithMcp:
    async def test_agent_not_found(self):
        engine = make_engine()
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine._execute_agent_with_mcp({"agent_id": "missing", "action": "a"})
        assert result["success"] is False
        assert "not found" in result["error"]

    async def test_success_with_llm(self):
        engine = make_engine()
        agent = SimpleNamespace(
            id="ag-1", llm_provider="openai", llm_model="gpt-4o",
            llm_api_key="k", llm_base_url=None, workspace_id="default", tenant_id="default",
        )
        handler = MagicMock()
        handler.chat_completion = AsyncMock(return_value={"content": "done", "tool_calls": []})
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.llm_service.get_llm_service", return_value=MagicMock(handler=handler)):
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine._execute_agent_with_mcp({
                "agent_id": "ag-1", "action": "analyze", "input_data": {"q": 1},
                "available_tools": [{"name": "t1", "description": "d", "input_schema": {"type": "object"}}],
                "mcp_connections": {"srv": {}},
            })
        assert result["success"] is True
        assert result["execution_method"] == "main_agent_with_mcp"
        assert result["tools_available"] == 1

    async def test_llm_failure_fallback(self):
        engine = make_engine()
        agent = SimpleNamespace(
            id="ag-1", llm_provider="openai", llm_model="gpt-4o",
            llm_api_key="k", llm_base_url=None, workspace_id="default", tenant_id="default",
        )
        handler = MagicMock()
        handler.chat_completion = AsyncMock(side_effect=RuntimeError("no api"))
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.database.get_db_session") as mock_session, \
             patch("core.llm_service.get_llm_service", return_value=MagicMock(handler=handler)):
            mock_session.return_value.__enter__.return_value = fake_db
            result = await engine._execute_agent_with_mcp({"agent_id": "ag-1", "action": "analyze"})
        assert result["success"] is True
        assert result["execution_method"] == "fallback"
        assert "no api" in result["error"]

    async def test_outer_exception_raises_agent_error(self):
        engine = make_engine()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            with pytest.raises(Exception, match="db down"):
                await engine._execute_agent_with_mcp({"agent_id": "ag-1"})


class TestEmailAutomation:
    async def test_detect_followups(self):
        engine = make_engine()
        with patch("core.email_followup_engine.followup_engine.detect_missing_replies", new=AsyncMock(return_value=[])):
            result = await engine._execute_email_automation_action("detect_followups", {"days_threshold": 7}, None)
        assert result["status"] == "success"
        assert result["count"] == 0

    async def test_draft_nudge(self):
        engine = make_engine()
        result = await engine._execute_email_automation_action("draft_nudge", {"subject": "Q3"}, None)
        assert result["status"] == "success"
        assert "Q3" in result["draft"]

    async def test_unknown_action(self):
        engine = make_engine()
        result = await engine._execute_email_automation_action("nope", {}, None)
        assert result["status"] == "error"


class TestWorkflowSubAction:
    async def test_missing_workflow_id(self):
        engine = make_engine()
        result = await engine._execute_workflow_action("run", {}, None)
        assert result["status"] == "error"
        assert "workflow_id" in result["error"]

    async def test_workflow_not_found(self):
        engine = make_engine()
        with patch.object(engine, "_load_workflow_by_id", return_value=None):
            result = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
        assert result["status"] == "error"

    async def test_success(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "COMPLETED", "outputs": {"o": 1}})
        with patch.object(engine, "_load_workflow_by_id", return_value={"id": "w1", "steps": []}), \
             patch.object(engine, "start_workflow", new=AsyncMock(return_value="ex-1")):
            result = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
        assert result["status"] == "success"
        assert result["execution_id"] == "ex-1"

    async def test_failed(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "FAILED", "error": "boom"})
        with patch.object(engine, "_load_workflow_by_id", return_value={"id": "w1", "steps": []}), \
             patch.object(engine, "start_workflow", new=AsyncMock(return_value="ex-1")):
            result = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
        assert result["status"] == "error"
        assert result["error"] == "boom"

    async def test_cancelled_and_paused(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(side_effect=[
            {"status": "CANCELLED"},
            {"status": "PAUSED"},
        ])
        with patch.object(engine, "_load_workflow_by_id", return_value={"id": "w1", "steps": []}), \
             patch.object(engine, "start_workflow", new=AsyncMock(return_value="ex-1")):
            r1 = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
            r2 = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
        assert r1["status"] == "cancelled"
        assert r2["status"] == "paused"

    async def test_timeout(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "RUNNING"})
        with patch.object(engine, "_load_workflow_by_id", return_value={"id": "w1", "steps": []}), \
             patch.object(engine, "start_workflow", new=AsyncMock(return_value="ex-1")):
            result = await engine._execute_workflow_action("run", {"workflow_id": "w1", "timeout": 0.001}, None)
        assert result["status"] == "timeout"

    async def test_state_not_found(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(return_value=None)
        with patch.object(engine, "_load_workflow_by_id", return_value={"id": "w1", "steps": []}), \
             patch.object(engine, "start_workflow", new=AsyncMock(return_value="ex-1")):
            result = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
        assert result["status"] == "error"
        assert "not found" in result["error"]

    async def test_running_then_completed(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(side_effect=[
            {"status": "RUNNING"},
            {"status": "COMPLETED", "outputs": {"o": 2}},
        ])
        with patch.object(engine, "_load_workflow_by_id", return_value={"id": "w1", "steps": []}), \
             patch.object(engine, "start_workflow", new=AsyncMock(return_value="ex-1")):
            result = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
        assert result["status"] == "success"

    async def test_unknown_status_loops_to_success(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(side_effect=[
            {"status": "WEIRD"},
            {"status": "COMPLETED", "outputs": {}},
        ])
        with patch.object(engine, "_load_workflow_by_id", return_value={"id": "w1", "steps": []}), \
             patch.object(engine, "start_workflow", new=AsyncMock(return_value="ex-1")):
            result = await engine._execute_workflow_action("run", {"workflow_id": "w1"}, None)
        assert result["status"] == "success"


class TestLoadWorkflowById:
    def test_file_missing(self, tmp_path, monkeypatch):
        engine = make_engine()
        monkeypatch.setattr("core.workflow_engine.os.path.dirname", lambda p: str(tmp_path))
        assert engine._load_workflow_by_id("w1") is None

    def test_found(self, tmp_path, monkeypatch):
        engine = make_engine()
        monkeypatch.setattr("core.workflow_engine.os.path.dirname", lambda p: str(tmp_path))
        with open(tmp_path / "workflows.json", "w") as f:
            json.dump([{"id": "w1", "name": "One"}, {"id": "w2", "name": "Two"}], f)
        wf = engine._load_workflow_by_id("w2")
        assert wf["name"] == "Two"
        assert engine._load_workflow_by_id("missing") is None

    def test_invalid_json(self, tmp_path, monkeypatch):
        engine = make_engine()
        monkeypatch.setattr("core.workflow_engine.os.path.dirname", lambda p: str(tmp_path))
        with open(tmp_path / "workflows.json", "w") as f:
            f.write("{not json")
        assert engine._load_workflow_by_id("w1") is None


class TestOutlookExecutor:
    async def test_send_email(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.outlook_service.OutlookService.send_email", create=True, new=AsyncMock(return_value={"id": "m"})):
            result = await engine._execute_outlook_action("send_email", {"to_recipients": ["a@b.c"], "subject": "s", "body": "b"}, "c1")
        assert result["status"] == "success"

    async def test_create_event(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.outlook_service.OutlookService.create_calendar_event", create=True, new=AsyncMock(return_value={"id": "e"})):
            result = await engine._execute_outlook_action("create_event", {"subject": "s", "start": "2026-01-01"}, "c1")
        assert result["status"] == "success"

    async def test_get_emails(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.outlook_service.OutlookService.get_user_emails", create=True, new=AsyncMock(return_value=[])):
            result = await engine._execute_outlook_action("get_emails", {"folder": "sent"}, "c1")
        assert result["status"] == "success"

    async def test_generic_method_match(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None), \
             patch("integrations.outlook_service.OutlookService.get_calendar", new=AsyncMock(return_value=[]), create=True):
            result = await engine._execute_outlook_action("get_calendar", {"calendar_id": "c"}, "c1")
        assert result["status"] == "success"

    async def test_unknown_action(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(ValueError, match="Unknown Outlook action"):
                await engine._execute_outlook_action("nope", {}, "c1")


class TestJiraTrelloExecutors:
    @pytest.mark.parametrize("service", ["jira", "trello"])
    async def test_known_action(self, service):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch(f"integrations.{service}_service.{service.title()}Service.create_issue", return_value={"id": 1}, create=True):
            result = await engine._execute_jira_action("create_issue", {"project": "P"}, "c1") if service == "jira" \
                else await engine._execute_trello_action("create_issue", {"list": "L"}, "c1")
        assert result["status"] == "success"

    @pytest.mark.parametrize("service", ["jira", "trello"])
    async def test_unknown_action(self, service):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(ValueError, match=f"Unknown {service.title()} action"):
                await engine._execute_jira_action("nope", {}, "c1") if service == "jira" \
                    else await engine._execute_trello_action("nope", {}, "c1")


class TestStripeExecutor:
    async def test_not_available(self):
        engine = make_engine()
        with patch("core.workflow_engine.HAS_STRIPE", False), patch("core.workflow_engine.StripeService", None):
            with pytest.raises(Exception, match="Stripe service not available"):
                await engine._execute_stripe_action("list_products", {}, None)

    async def test_no_token_returns_error(self):
        engine = make_engine()
        with patch("core.workflow_engine.HAS_STRIPE", True), \
             patch("core.workflow_engine.StripeService", MagicMock()), \
             patch("core.workflow_engine.token_storage.get_token", return_value=None):
            result = await engine._execute_stripe_action("list_products", {}, "c1")
        assert result["status"] == "error"
        assert "access token" in result["error"]

    async def test_success(self):
        engine = make_engine()
        service_cls = MagicMock()
        service_cls.return_value.list_products.return_value = [{"id": "p"}]
        with patch("core.workflow_engine.HAS_STRIPE", True), \
             patch("core.workflow_engine.StripeService", service_cls), \
             patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}):
            result = await engine._execute_stripe_action("list_products", {}, "c1")
        assert result["status"] == "success"

    async def test_unknown_action(self):
        engine = make_engine()
        stub_cls = type("StubStripe", (), {"list_products": lambda self: [{"id": "p"}]})
        with patch("core.workflow_engine.HAS_STRIPE", True), \
             patch("core.workflow_engine.StripeService", stub_cls), \
             patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}):
            with pytest.raises(ValueError, match="Unknown Stripe action"):
                await engine._execute_stripe_action("nope", {}, "c1")


class TestShopifyExecutor:
    async def test_sync_method(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t", "shop_url": "x.myshopify.com"}), \
             patch("integrations.shopify_service.ShopifyService.list_products", create=True, return_value=[{"id": 1}]):
            result = await engine._execute_shopify_action("list_products", {}, "c1")
        assert result["status"] == "success"

    async def test_async_method(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.shopify_service.ShopifyService.create_order", create=True, new=AsyncMock(return_value={"id": 2})):
            result = await engine._execute_shopify_action("create_order", {}, "c1")
        assert result["status"] == "success"

    async def test_unknown_action(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(ValueError, match="Unknown Shopify action"):
                await engine._execute_shopify_action("nope", {}, "c1")


class TestZohoExecutors:
    async def test_zoho_crm_sync_and_async(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t"}), \
             patch("integrations.zoho_crm_service.ZohoCRMService.create_lead", create=True, return_value={"id": "l"}), \
             patch("integrations.zoho_crm_service.ZohoCRMService.list_deals", create=True, new=AsyncMock(return_value=[])):
            r1 = await engine._execute_zoho_crm_action("create_lead", {}, "c1")
            r2 = await engine._execute_zoho_crm_action("list_deals", {}, "c1")
        assert r1["status"] == "success"
        assert r2["status"] == "success"

    async def test_zoho_crm_unknown(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(ValueError, match="Unknown Zoho CRM action"):
                await engine._execute_zoho_crm_action("nope", {}, "c1")

    async def test_zoho_books(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t", "organization_id": "org1"}), \
             patch("integrations.zoho_books_service.ZohoBooksService.create_invoice", create=True, return_value={"id": "i"}):
            result = await engine._execute_zoho_books_action("create_invoice", {"customer_id": "c"}, "c1")
        assert result["status"] == "success"

    async def test_zoho_books_unknown(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(ValueError, match="Unknown Zoho Books action"):
                await engine._execute_zoho_books_action("nope", {}, "c1")

    async def test_zoho_inventory(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "t", "org_id": "org1"}), \
             patch("integrations.zoho_inventory_service.ZohoInventoryService.create_item", create=True, new=AsyncMock(return_value={"id": "it"})):
            result = await engine._execute_zoho_inventory_action("create_item", {"name": "n"}, "c1")
        assert result["status"] == "success"

    async def test_zoho_inventory_unknown(self):
        engine = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(ValueError, match="Unknown Zoho Inventory action"):
                await engine._execute_zoho_inventory_action("nope", {}, "c1")


class TestGoalManagement:
    async def test_create_goal_missing_fields(self):
        engine = make_engine()
        with pytest.raises(ValueError, match="Missing title or target_date"):
            await engine._execute_goal_management_action("create_goal", {}, None)

    async def test_create_goal_success(self):
        engine = make_engine()
        goal = MagicMock()
        goal.dict.return_value = {"id": "g1"}
        with patch("core.goal_engine.goal_engine.create_goal_from_text", new=AsyncMock(return_value=goal)):
            result = await engine._execute_goal_management_action(
                "create_goal", {"title": "T", "target_date": "2026-08-01T00:00:00Z", "owner_id": "o"}, None)
        assert result == {"id": "g1"}

    async def test_check_escalations(self):
        engine = make_engine()
        with patch("core.goal_engine.goal_engine.check_for_escalations", new=AsyncMock(return_value=[])):
            result = await engine._execute_goal_management_action("check_escalations", {}, None)
        assert result == {"escalations": []}

    async def test_update_subtask_goal_not_found(self):
        engine = make_engine()
        with patch("core.goal_engine.goal_engine.goals", {}):
            with pytest.raises(ValueError, match="Goal g1 not found"):
                await engine._execute_goal_management_action("update_subtask", {"goal_id": "g1"}, None)

    async def test_update_subtask_success(self):
        engine = make_engine()
        st = SimpleNamespace(id="st1", status="todo")
        goal = SimpleNamespace(id="g1", sub_tasks=[st])
        goal.dict = lambda: {"id": "g1", "sub_tasks": [{"id": "st1", "status": st.status}]}
        with patch("core.goal_engine.goal_engine.goals", {"g1": goal}), \
             patch("core.goal_engine.goal_engine.update_goal_progress", new=AsyncMock()):
            result = await engine._execute_goal_management_action("update_subtask", {"goal_id": "g1", "sub_task_id": "st1", "status": "done"}, None)
        assert st.status == "done"
        assert result["sub_tasks"][0]["status"] == "done"

    async def test_unknown_action(self):
        engine = make_engine()
        with pytest.raises(ValueError, match="Unknown goal_management action"):
            await engine._execute_goal_management_action("nope", {}, None)


class TestGenericExecutor:
    @staticmethod
    def _cache_patch(**kwargs):
        import core.cache as cache_mod
        cache_obj = cache_mod.cache
        defaults = {"get": None, "set": None}
        defaults.update(kwargs)
        ctxs = []
        if "get" in kwargs or "set" not in kwargs or kwargs.get("set") is None:
            pass
        return patch.object(cache_obj, "get", kwargs.get("get") or (lambda k: None)), \
               patch.object(cache_obj, "set", kwargs.get("set") or (lambda k, v, ttl=300: None))

    async def test_catalog_fetch_and_get(self):
        engine = make_engine()
        catalog_item = SimpleNamespace(
            id="custom_api",
            actions=[{"name": "get_items", "method": "GET", "url": "https://api.example.com/items/{id}"}],
        )
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = catalog_item
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"items": []}
        cache_get, cache_set = self._cache_patch()
        with cache_get, cache_set, \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch("core.workflow_engine.httpx.AsyncClient") as mock_client:
            mock_session.return_value.__enter__.return_value = fake_db
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=response)
            result = await engine._execute_generic_action("custom_api", "get_items", {"id": "42"}, "c1")
        assert result == {"items": []}

    async def test_cached_catalog(self):
        engine = make_engine()
        cached = {"id": "svc", "actions": [{"name": "ping", "method": "POST", "url": "https://x/ping"}]}
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"pong": True}
        cache_get, cache_set = self._cache_patch(get=lambda k: cached)
        with cache_get, cache_set, \
             patch("core.workflow_engine.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=response)
            result = await engine._execute_generic_action("svc", "ping", {"a": 1}, None)
        assert result == {"pong": True}

    async def test_catalog_not_found(self):
        engine = make_engine()
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        cache_get, cache_set = self._cache_patch()
        with cache_get, cache_set, \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = fake_db
            with pytest.raises(ValueError, match="not found in Integration Catalog"):
                await engine._execute_generic_action("ghost", "x", {}, None)

    async def test_action_not_found(self):
        engine = make_engine()
        catalog_item = SimpleNamespace(id="svc", actions=[{"name": "other"}])
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = catalog_item
        cache_get, cache_set = self._cache_patch()
        with cache_get, cache_set, \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = fake_db
            with pytest.raises(ValueError, match="not found in catalog for service"):
                await engine._execute_generic_action("svc", "missing_action", {}, None)

    async def test_no_url(self):
        engine = make_engine()
        catalog_item = SimpleNamespace(id="svc", actions=[{"name": "x", "method": "GET"}])
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = catalog_item
        cache_get, cache_set = self._cache_patch()
        with cache_get, cache_set, \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = fake_db
            with pytest.raises(ValueError, match="No URL/path"):
                await engine._execute_generic_action("svc", "x", {}, None)

    async def test_missing_path_param(self):
        engine = make_engine()
        catalog_item = SimpleNamespace(
            id="svc", actions=[{"name": "x", "method": "GET", "url": "https://x/{id}"}])
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = catalog_item
        cache_get, cache_set = self._cache_patch()
        with cache_get, cache_set, \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = fake_db
            with pytest.raises(ValueError, match="Missing path parameter"):
                await engine._execute_generic_action("svc", "x", {}, None)

    async def test_bearer_auth_header(self):
        engine = make_engine()
        catalog_item = SimpleNamespace(
            id="svc", actions=[{"name": "x", "method": "GET", "url": "https://x/ping"}])
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = catalog_item
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {}
        cache_get, cache_set = self._cache_patch()
        with cache_get, cache_set, \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch("core.workflow_engine.token_storage.get_token", return_value={"access_token": "secret-tok"}), \
             patch("core.workflow_engine.httpx.AsyncClient") as mock_client:
            mock_session.return_value.__enter__.return_value = fake_db
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=response)
            await engine._execute_generic_action("svc", "x", {}, "c1")
            captured_headers = mock_client.return_value.__aenter__.return_value.request.call_args[1]["headers"]
        assert captured_headers["Authorization"] == "Bearer secret-tok"

    async def test_db_fetch_error_reraises(self):
        engine = make_engine()
        cache_get, cache_set = self._cache_patch()
        with cache_get, cache_set, \
             patch("core.workflow_engine.get_db_session", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError, match="db down"):
                await engine._execute_generic_action("svc", "x", {}, None)


# ---------------------------------------------------------------------------
# Part D — run-level orchestration
# ---------------------------------------------------------------------------


class TestResumeCancel:
    async def test_resume_execution_not_found(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await engine.resume_workflow("ex-1", {}, {})

    async def test_resume_not_paused_returns_false(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "COMPLETED"})
        assert await engine.resume_workflow("ex-1", {}, {}) is False

    async def test_resume_paused(self):
        engine = make_engine()
        engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "PAUSED"})
        engine.state_manager.update_execution_inputs = AsyncMock()
        engine.state_manager.update_execution_status = AsyncMock()
        with patch.object(engine, "_run_execution", new=AsyncMock()):
            result = await engine.resume_workflow("ex-1", {}, {"x": 1})
        assert result is True

    async def test_cancel_execution(self):
        engine = make_engine()
        engine.state_manager.update_execution_status = AsyncMock()
        ws = MagicMock()
        ws.notify_workflow_status = AsyncMock()
        with patch("core.workflow_engine.get_connection_manager", return_value=ws):
            result = await engine.cancel_execution("ex-1")
        assert result is True
        assert "ex-1" in engine.cancellation_requests
        engine.cancellation_requests.discard("ex-1")


class TestRunExecution:
    def _state_manager(self):
        sm = MagicMock()
        sm.get_execution_state = AsyncMock()
        sm.update_execution_status = AsyncMock()
        sm.update_step_status = AsyncMock()
        sm.update_execution_inputs = AsyncMock()
        sm.create_execution = AsyncMock()
        return sm

    def _env(self, state_manager=None):
        sm = state_manager or self._state_manager()
        ws = MagicMock()
        ws.notify_workflow_status = AsyncMock()
        analytics = MagicMock()
        db = MagicMock()
        governance = MagicMock()
        governance.can_perform_action_async = AsyncMock(return_value={"allowed": True, "reason": "ok"})
        return sm, ws, analytics, db, governance

    async def test_success_linear_path(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict()

        def _state(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"steps": {}, "input_data": {}, "outputs": {}}
            return {"steps": {"s1": {"status": "COMPLETED", "output": {}}}, "input_data": {}, "outputs": {}}

        calls = {"n": 0}
        sm.get_execution_state = AsyncMock(side_effect=_state)
        engine.state_manager = sm
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        status_calls = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert status_calls
        assert exec_mock.call_count == 1

    async def test_condition_skip(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict(condition="${input.flag} == true")
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {"flag": False}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        skipped = [c.args for c in sm.update_step_status.call_args_list if c.args[2] == "SKIPPED"]
        assert skipped and skipped[0][0] == "ex-1"

    async def test_missing_input_pauses(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict(parameters={"x": "${input.missing_var}"})
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        paused = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "PAUSED"]
        assert paused

    async def test_cancellation_aborts(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict()
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        engine.cancellation_requests.add("ex-1")
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        cancelled = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "CANCELLED"]
        assert cancelled
        assert "ex-1" not in engine.cancellation_requests

    async def test_step_failure_continue_on_error_partial(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict(continue_on_error=True)
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=AsyncMock(side_effect=RuntimeError("step blew up"))), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        partial = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "PARTIAL"]
        assert partial

    async def test_step_failure_aborts_failed(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict()
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=AsyncMock(side_effect=RuntimeError("fatal"))), \
             patch("core.workflow_notifier.notifier.notify_failure", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        _dbg = sm.update_execution_status.call_args_list
        print("DBG", [_c for _c in _dbg], flush=True)
        failed = []
        for _c in _dbg:
            try:
                _a = _c.args
            except Exception as _e:
                print("DBG-ERR item:", repr(_c), "type:", type(_c).__name__, "exc:", _e, flush=True)
                raise
            print("DBG-OK item:", repr(_c), "args:", _a, flush=True)
            if _a[1] == "FAILED":
                failed.append(_a)
        assert failed
        analytics.track_workflow_execution.assert_called_once()

    async def test_error_envelope_output_fails_step(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict()
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=AsyncMock(return_value={"status": "error", "error": "nope"})), \
             patch("core.workflow_notifier.notifier.notify_failure", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        _dbg = sm.update_execution_status.call_args_list
        print("DBG", [_c for _c in _dbg], flush=True)
        failed = []
        for _c in _dbg:
            try:
                _a = _c.args
            except Exception as _e:
                print("DBG-ERR item:", repr(_c), "type:", type(_c).__name__, "exc:", _e, flush=True)
                raise
            print("DBG-OK item:", repr(_c), "args:", _a, flush=True)
            if _a[1] == "FAILED":
                failed.append(_a)
        assert failed

    async def test_governance_block_pauses_execution_for_hitl(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        governance.can_perform_action_async = AsyncMock(return_value={"allowed": False, "reason": "maturity too low"})
        governance.request_approval = MagicMock(return_value="hitl-1")
        step = step_dict()
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch("core.service_factory.ServiceFactory.get_governance_service", return_value=governance), \
             patch.object(engine, "_execute_step", new=AsyncMock(return_value={"status": "success"})):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution(
                "ex-1", {"id": "wf-1", "agent_id": "ag-1", "steps": [step]})
        # Trust-policy denial now pauses for human-in-the-loop review
        paused = [c for c in sm.update_execution_status.call_args_list if c.args[1] == "PAUSED"]
        assert paused
        assert any("Governance approval required" in (c.kwargs.get("error") or "") for c in paused)
        governance.request_approval.assert_called_once()

    async def test_completed_step_skipped(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict()
        sm.get_execution_state = AsyncMock(return_value={
            "steps": {"s1": {"status": "COMPLETED", "output": {}}}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        exec_mock = AsyncMock(return_value={"status": "success"})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        exec_mock.assert_not_called()
        completed = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "COMPLETED"]
        assert completed

    async def test_dependency_not_met_marks_skipped(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict(depends_on=["never"])
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "steps": [step]})
        skipped = [c for c in sm.update_step_status.call_args_list if c.args[2] == "SKIPPED"]
        assert skipped
        assert "Dependencies not met" in skipped[0].kwargs["error"]

    async def test_marketplace_usage_tracked(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        step = step_dict()
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        track_mock = MagicMock()
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=AsyncMock(return_value={"status": "success", "result": {}})), \
             patch("core.marketplace_usage_tracker.MarketplaceUsageTracker.track_usage", new=track_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-1", {"id": "wf-1", "created_from_template": "tpl-1", "steps": [step]})
        track_mock.assert_called_once()

    async def test_graph_execution_path(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        workflow = {
            "id": "wf-g",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
                {"id": "b", "title": "B", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [
                {"source": "a", "target": "b", "condition": "${input.go} == true"},
            ],
        }
        exec_mock = AsyncMock(return_value={"status": "success", "result": {}})
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session, \
             patch.object(engine, "_execute_step", new=exec_mock), \
             patch("core.workflow_notifier.notifier.notify_completion", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-g", workflow)
        assert exec_mock.call_count >= 1

    async def test_graph_cancellation(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()
        sm.get_execution_state = AsyncMock(return_value={"steps": {}, "input_data": {}, "outputs": {}})
        engine.state_manager = sm
        engine.cancellation_requests.add("ex-gc")
        workflow = {
            "id": "wf-gc",
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"service": "email", "action": "send"}},
            ],
            "connections": [{"source": "a", "target": "b", "condition": "${input.go} == true"}],
        }
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-gc", workflow)
        cancelled = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "CANCELLED"]
        assert cancelled

    async def test_graph_missing_input_pauses(self):
        engine = make_engine()
        sm, ws, analytics, db, governance = self._env()

        def _state(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"steps": {}, "input_data": {}, "outputs": {}}
            return {"steps": {}, "input_data": {}, "outputs": {}, "status": "PAUSED"}

        calls = {"n": 0}
        sm.get_execution_state = AsyncMock(side_effect=_state)
        engine.state_manager = sm
        workflow = {
            "id": "wf-gm",
            "nodes": [
                {"id": "a", "title": "A", "type": "action",
                 "config": {"service": "email", "action": "send", "parameters": {"x": "${input.ghost}"}}},
            ],
            "connections": [{"source": "a", "target": "b", "condition": "${input.go} == true"}],
        }
        with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
             patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
             patch("core.workflow_engine.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            await engine._run_execution("ex-gm", workflow)
        paused = [c.args for c in sm.update_execution_status.call_args_list if c.args[1] == "PAUSED"]
        assert paused


class TestStartWorkflow:
    async def test_start_workflow_converts_nodes(self):
        engine = make_engine()
        engine.state_manager.create_execution = AsyncMock(return_value="ex-1")
        engine.state_manager.update_execution_status = AsyncMock()
        workflow = {
            "workflow_id": "wf-1",
            "nodes": [{"id": "a", "title": "A", "type": "action", "config": {}}],
            "connections": [],
        }
        with patch.object(engine, "_run_execution", new=AsyncMock()):
            result = await engine.start_workflow(workflow, {"x": 1})
        assert result == "ex-1"
        assert workflow["id"] == "wf-1"
        assert workflow["steps"][0]["id"] == "a"

    async def test_start_workflow_steps_already_present(self):
        engine = make_engine()
        engine.state_manager.create_execution = AsyncMock(return_value="ex-2")
        with patch.object(engine, "_run_execution", new=AsyncMock()):
            result = await engine.start_workflow({"id": "wf-2", "steps": [step_dict()]}, {})
        assert result == "ex-2"


class TestExceptionsAndFactory:
    def test_missing_input_error_attrs(self):
        err = MissingInputError("Variable x not found", "x")
        assert err.missing_var == "x"
        assert "x" in str(err)

    def test_schema_validation_error_attrs(self):
        err = SchemaValidationError("bad", "input", ["e1"])
        assert err.schema_type == "input"
        assert err.errors == ["e1"]
        err2 = SchemaValidationError("bad", "output")
        assert err2.errors == []

    def test_step_timeout_error_attrs(self):
        err = StepTimeoutError("timed out", "s1", 5.0)
        assert err.step_id == "s1"
        assert err.timeout == 5.0

    def test_get_workflow_engine_singleton(self):
        with patch("core.workflow_engine._workflow_engine", None):
            from core.workflow_engine import get_workflow_engine
            e1 = get_workflow_engine()
            e2 = get_workflow_engine()
            assert e1 is e2
