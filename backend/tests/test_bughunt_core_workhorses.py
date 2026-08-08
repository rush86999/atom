"""Bug-hunt tests (TDD) for the core workhorse modules:
workflow_engine, atom_agent_endpoints, byok_handler, generic_agent,
atom_meta_agent, learning_llm_router, agent_world_model.

Every test in the BUG classes asserts CORRECT behavior and was written
failing-first (RED) against the pre-fix source.
"""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


# ============================================================================
# atom_agent_endpoints
# ============================================================================

class TestAtomAgentEndpointsAuth:
    """The hybrid retrieval endpoints (/agents/{id}/retrieve-hybrid and
    retrieve-baseline) carried NO auth dependency — a bogus Bearer header
    bypassed CSRF and returned 200 for any agent_id (unauthenticated IDOR
    into episode retrieval)."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main_api_app import app
        return TestClient(app)

    def test_retrieve_baseline_rejects_bogus_token(self, client):
        resp = client.post(
            "/api/atom-agent/agents/any-agent-xyz/retrieve-baseline",
            params={"query": "test", "top_k": 5},
            headers={"Authorization": "Bearer bogus-token-12345"},
        )
        assert resp.status_code == 401, (
            "unauthenticated episode retrieval must be rejected, got "
            f"{resp.status_code}: {resp.text[:200]}"
        )

    def test_retrieve_hybrid_rejects_bogus_token(self, client):
        resp = client.post(
            "/api/atom-agent/agents/any-agent-xyz/retrieve-hybrid",
            params={"query": "test"},
            headers={"Authorization": "Bearer bogus-token-12345"},
        )
        assert resp.status_code == 401

    def test_retrieve_baseline_no_auth_header_rejected(self, client):
        resp = client.post(
            "/api/atom-agent/agents/any-agent-xyz/retrieve-baseline",
            params={"query": "test", "top_k": 5},
        )
        assert resp.status_code in (401, 403)


# ============================================================================
# atom_agent_endpoints (streaming)
# ============================================================================

class TestStreamChatAgentResolutionBug:
    """chat_stream_agent passes workspace_id= to resolve_agent_for_request,
    which does not accept it -> TypeError -> every governance-enabled stream
    chat crashes with 'Internal server error'."""

    def _make_resolver_stub(self):
        resolver = AsyncMock()
        resolver.resolve_agent_for_request = AsyncMock(
            return_value=(None, {"method": "none"})
        )
        return resolver

    @pytest.mark.asyncio
    async def test_stream_chat_resolves_without_workspace_id_kwarg(self):
        from core.atom_agent_endpoints import chat_stream_agent, ChatRequest
        from types import SimpleNamespace

        with patch("core.agent_context_resolver.AgentContextResolver") as res_cls, \
             patch("core.agent_governance_service.AgentGovernanceService") as gov_cls, \
             patch("core.database.get_db_session") as db, \
             patch("core.atom_agent_endpoints.LLMService") as llm_cls, \
             patch("core.websockets.manager") as ws:
            resolver = self._make_resolver_stub()
            res_cls.return_value = resolver

            gov = Mock()
            gov.can_perform_action = Mock(
                return_value={"allowed": True, "reason": ""}
            )
            gov_cls.return_value = gov

            class _Ctx:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def query(self, model):
                    q = Mock()
                    q.filter.return_value.first.return_value = None
                    return q

            db.side_effect = lambda: _Ctx()

            llm = Mock()
            llm.analyze_query_complexity = Mock(return_value="low")
            llm.get_optimal_provider = Mock(return_value=("openai", "gpt-4o"))
            llm.stream_completion = AsyncMock(return_value=iter(["hi", " there"]))
            llm_cls.return_value = llm

            ws.broadcast = AsyncMock()
            ws.STREAMING_UPDATE = "streaming:update"
            ws.STREAMING_COMPLETE = "streaming:complete"
            ws.STREAMING_ERROR = "streaming:error"

            with patch("core.atom_agent_endpoints.get_chat_history_manager") as hist, \
                 patch("core.atom_agent_endpoints.get_chat_session_manager") as sess, \
                 patch("core.atom_agent_endpoints.SystemIntelligenceService") as intel:
                hist.return_value.add_message = Mock()
                sess.return_value.create_session = Mock(return_value="s1")
                intel.return_value.get_aggregated_context = Mock(return_value="")

                request = ChatRequest(
                    message="hello", user_id="u1", workspace_id="default",
                    agent_id="agent-1",
                )
                result = await chat_stream_agent(
                    request, current_user=SimpleNamespace(id="u1")
                )

            assert result.get("success") is True, f"stream chat crashed: {result}"
            resolver.resolve_agent_for_request.assert_awaited_once()
            kwargs = resolver.resolve_agent_for_request.call_args.kwargs
            assert "workspace_id" not in kwargs, (
                "resolve_agent_for_request does not accept workspace_id"
            )
            assert kwargs.get("action_type") == "stream_chat"


class TestAutomationInsightsHandlerBug:
    """handle_automation_insights iterates generate_all_insights()'s return
    value as a list of records, but the service returns a dict
    {drift_insights: [...], summary: {...}} -> iterating yields string keys ->
    crash. Every 'show automation insights' chat request 500s."""

    @pytest.mark.asyncio
    async def test_insights_handler_accepts_service_dict_shape(self):
        from core.atom_agent_endpoints import handle_automation_insights, ChatRequest

        drift = [
            {"workflow_id": "wf_001", "success_steps": 5, "overrides": 4,
             "drift_score": 0.9, "recommendation": "OPTIMIZE (High Overrides)"},
            {"workflow_id": "wf_002", "success_steps": 20, "overrides": 0,
             "drift_score": 0.1, "recommendation": "HIGH_CONFIDENCE"},
        ]
        with patch("core.automation_insight_manager.get_insight_manager") as mgr, \
             patch("core.behavior_analyzer.get_behavior_analyzer"):
            mgr.return_value.generate_all_insights = Mock(return_value={
                "timestamp": "2026-08-07T00:00:00",
                "drift_insights": drift,
                "summary": {"total_monitored": 2, "needs_optimization": 1, "stable": 0},
            })
            result = await handle_automation_insights(
                ChatRequest(message="Show insights", user_id="u1")
            )

        assert result["success"] is True, f"insights handler crashed: {result}"
        assert "wf_001" in result["response"]["message"]


class TestExecuteGeneratedWorkflowBug:
    """execute_generated_workflow looks up workflows by w['id'], but every
    persisted workflow in workflows.json uses the 'workflow_id' key ->
    KeyError -> 500 on every execute-generated request."""

    @pytest.mark.asyncio
    async def test_execute_generated_accepts_workflow_id_key(self):
        from core.atom_agent_endpoints import execute_generated_workflow
        from types import SimpleNamespace

        wf = {
            "name": "Daily Report", "workflow_id": "wf_daily_001",
            "steps": [{"id": "s1", "service": "email", "action": "send"}],
        }
        engine = AsyncMock()
        engine.execute_workflow_definition = AsyncMock(return_value={"ok": True})

        with patch("core.atom_agent_endpoints.load_workflows", return_value=[wf]), \
             patch("core.atom_agent_endpoints.AutomationEngine", return_value=engine), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()):
            result = await execute_generated_workflow(
                SimpleNamespace(workflow_id="wf_daily_001", input_data={}),
                current_user=SimpleNamespace(id="u1"),
            )

        assert result.get("success") is True, f"execute-generated crashed: {result}"


# ============================================================================
# agent_world_model
# ============================================================================

class TestWorldModelServiceInit:
    """WorldModelService() with no workspace must resolve to the canonical
    'default' workspace handler — passing None meant the service silently
    bound a different (global) LanceDB handler than WorldModelService('default')."""

    def test_init_defaults_to_default_workspace_handler(self):
        from core.agent_world_model import WorldModelService
        with patch("core.agent_world_model.get_lancedb_handler") as mock_get_handler:
            mock_db = Mock()
            mock_db.db = Mock()
            mock_db.db.table_names = Mock(return_value=[])
            mock_get_handler.return_value = mock_db
            WorldModelService()
            assert mock_get_handler.call_args.args == ("default",), (
                "no-workspace service must bind the 'default' workspace handler"
            )


# ============================================================================
# byok_handler
# ============================================================================

class TestProviderComparisonFallback:
    """get_provider_comparison returns {} when the pricing fetcher yields no
    data (all-zero costs in the cache) — the static fallback only fired on
    exceptions, so the pricing UI got an empty comparison."""

    def test_empty_dynamic_data_uses_static_fallback(self):
        from core.llm.byok_handler import BYOKHandler
        handler = BYOKHandler.__new__(BYOKHandler)

        with patch("core.llm.byok_handler.get_pricing_fetcher") as fetcher_cls:
            fetcher = Mock()
            fetcher.compare_providers.return_value = {}
            fetcher_cls.return_value = fetcher

            comparison = handler.get_provider_comparison()

        assert isinstance(comparison, dict)
        assert len(comparison) > 0, "empty comparison must fall back to static table"
        assert "openai" in comparison
        assert "deepseek" in comparison

    def test_populated_dynamic_data_wins(self):
        from core.llm.byok_handler import BYOKHandler
        handler = BYOKHandler.__new__(BYOKHandler)

        with patch("core.llm.byok_handler.get_pricing_fetcher") as fetcher_cls:
            fetcher = Mock()
            fetcher.compare_providers.return_value = {"openai": {"avg_cost_per_token": 0.00003}}
            fetcher_cls.return_value = fetcher

            comparison = handler.get_provider_comparison()

        assert comparison == {"openai": {"avg_cost_per_token": 0.00003}}


# ============================================================================
# workflow_engine
# ============================================================================

class TestWorkflowEngineBugs:
    def _engine(self):
        from core.workflow_engine import WorkflowEngine
        return WorkflowEngine()

    # --- BUG A: _resolve_parameters never recurses into nested dicts/lists ---
    # Real-world workflow steps pass nested parameter structures (HTTP config,
    # MCP arguments, etc.); ${...} refs inside them were sent to integrations
    # as literal strings.
    def test_nested_dict_parameters_resolved(self):
        engine = self._engine()
        params = {"config": {"source": "${step1.output.url}",
                             "headers": {"auth": "${step1.token}"}}}
        state = {"outputs": {"step1": {"output": {"url": "https://api.example.com"},
                                       "token": "Bearer abc123"}}}
        resolved = engine._resolve_parameters(params, state)
        assert resolved["config"]["source"] == "https://api.example.com"
        assert resolved["config"]["headers"]["auth"] == "Bearer abc123"

    def test_list_parameters_resolved(self):
        engine = self._engine()
        params = {"targets": ["${step1.output.email1}", "${step1.output.email2}"]}
        state = {"outputs": {"step1": {"output": {"email1": "user1@example.com",
                                                  "email2": "user2@example.com"}}}}
        resolved = engine._resolve_parameters(params, state)
        assert resolved["targets"] == ["user1@example.com", "user2@example.com"]

    def test_nested_missing_variable_raises(self):
        engine = self._engine()
        from core.workflow_engine import MissingInputError
        params = {"config": {"source": "${missing_step.output.url}"}}
        with pytest.raises(MissingInputError):
            engine._resolve_parameters(params, {"outputs": {}})

    # --- BUG B: schema validation error-message formatting crashed with
    # KeyError('id') when the step dict has no 'id', masking the real
    # SchemaValidationError ---
    def test_input_schema_error_without_step_id(self):
        engine = self._engine()
        from core.workflow_engine import SchemaValidationError
        step = {"input_schema": {"type": "object",
                                 "properties": {"name": {"type": "string"}},
                                 "required": ["name"]}}
        with pytest.raises(SchemaValidationError):
            engine._validate_input_schema(step, {"age": 30})

    def test_output_schema_error_without_step_id(self):
        engine = self._engine()
        from core.workflow_engine import SchemaValidationError
        step = {"output_schema": {"type": "object",
                                  "properties": {"name": {"type": "string"}},
                                  "required": ["name"]}}
        with pytest.raises(SchemaValidationError):
            engine._validate_output_schema(step, {"age": 30})

    # --- BUG C: a step output whose value is legitimately None was treated as
    # "missing" -> spurious MissingInputError -> workflow paused forever ---
    def test_none_output_value_not_treated_as_missing(self):
        engine = self._engine()
        params = {"value": "${step1.data}"}
        state = {"outputs": {"step1": {"data": None}}}
        resolved = engine._resolve_parameters(params, state)
        assert resolved["value"] is None

    def test_truly_missing_variable_still_raises(self):
        engine = self._engine()
        from core.workflow_engine import MissingInputError
        params = {"value": "${ghost.data}"}
        with pytest.raises(MissingInputError):
            engine._resolve_parameters(params, {"outputs": {"step1": {"data": None}}})

    # --- GOVERNANCE: linear-run interlock must block when agent lacks
    # permission (R70 regression guard) ---
    @pytest.mark.asyncio
    async def test_linear_run_governance_block_fails_execution(self):
        from core.workflow_engine import WorkflowEngine
        engine = WorkflowEngine()
        engine.state_manager = Mock()
        engine.state_manager.update_execution_status = AsyncMock()
        engine.state_manager.update_step_status = AsyncMock()
        engine.state_manager.get_execution_state = AsyncMock(
            return_value={"status": "RUNNING", "steps": {}, "outputs": {},
                          "input_data": {}})

        governance = AsyncMock()
        governance.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "maturity too low"})

        agent = SimpleNamespace(id="agent-1", maturity_level="INTERN")

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def query(self, model):
                q = Mock()
                q.filter.return_value.first.return_value = agent
                return q

        ws_manager = Mock()
        ws_manager.notify_workflow_status = AsyncMock()

        step = {"id": "s1", "service": "test", "action": "do_thing",
                "sequence_order": 1, "parameters": {}}

        with patch("core.workflow_engine.get_db_session", side_effect=lambda: FakeSession()), \
             patch("core.workflow_engine.get_connection_manager", return_value=ws_manager), \
             patch("core.workflow_engine.ServiceFactory") as sf:
            sf.get_governance_service.return_value = governance
            await engine._run_execution("exec-1", {
                "id": "wf-1", "steps": [step], "agent_id": "agent-1",
                "created_by": "user-1", "tenant_id": "t1", "workspace_id": "w1",
            })

        governance.can_perform_action_async.assert_awaited_once()
        assert governance.can_perform_action_async.call_args.kwargs["action_type"] == "do_thing"
        # Execution must be FAILED, not COMPLETED
        failed_calls = [c for c in engine.state_manager.update_execution_status.call_args_list
                        if c.args[1] == "FAILED"]
        assert failed_calls, "governance denial must fail the execution"
