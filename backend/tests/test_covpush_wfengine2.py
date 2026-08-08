"""Coverage push for core/workflow_engine.py 90% -> 95%.

Targets the service-executor error paths, simulated executors, condition
evaluation failure paths, workflow loading, and the engine singleton.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from core.workflow_engine import WorkflowEngine, MissingInputError


def _engine():
    e = WorkflowEngine()
    e.state_manager = Mock()
    e.state_manager.get_execution_state = AsyncMock(
        return_value={"status": "RUNNING", "steps": {}, "outputs": {},
                      "input_data": {}}
    )
    e.state_manager.update_execution_status = AsyncMock()
    e.state_manager.update_step_status = AsyncMock()
    e.cancellation_requests = set()
    e.semaphore = asyncio.Semaphore(5)
    e.max_concurrent_steps = 5
    e._background_tasks = set()
    return e


# ============================================================================
# Simulated service executors (calendar/database/ai/webhook/email)
# ============================================================================

class TestSimulatedExecutors:
    @pytest.mark.asyncio
    async def test_simulated_executors(self):
        e = _engine()
        assert (await e._execute_email_action("a", {}))["status"] == "success"
        assert (await e._execute_calendar_action("a", {}))["status"] == "success"
        assert (await e._execute_database_action("a", {}))["status"] == "success"
        assert (await e._execute_ai_action("a", {}))["status"] == "success"
        assert (await e._execute_webhook_action("a", {}))["status"] == "success"

    @pytest.mark.asyncio
    async def test_discord_send_and_fallback(self):
        e = _engine()
        with patch("integrations.discord_service.discord_service") as ds:
            ds.bot_token = "bot"
            ds.send_message = AsyncMock(return_value={"ok": True})
            out = await e._execute_discord_action("send_message", {"channel_id": "c"})
            assert out["status"] == "success"
            ds.send_message.assert_awaited_once()
            out2 = await e._execute_discord_action("other", {})
            assert out2["status"] == "success"

    @pytest.mark.asyncio
    async def test_discord_no_token_raises(self):
        e = _engine()
        with patch("integrations.discord_service.discord_service") as ds:
            ds.bot_token = None
            with pytest.raises(Exception):
                await e._execute_discord_action("send_message", {"channel_id": "c"})


# ============================================================================
# Error branches of the integration executors
# ============================================================================

class TestExecutorErrorBranches:
    @pytest.mark.asyncio
    async def test_slack_no_token_raises(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts:
            ts.get_token.return_value = None
            with pytest.raises(Exception):
                await e._execute_slack_action("chat_postMessage", {})

    @pytest.mark.asyncio
    async def test_slack_unknown_action_raises(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts:
            ts.get_token.return_value = {"access_token": "tok"}
            with pytest.raises(ValueError):
                await e._execute_slack_action("bogus_action", {}, connection_id="conn")

    @pytest.mark.asyncio
    async def test_asana_no_token_raises(self):
        e = _engine()
        e._get_token = Mock(return_value=None)
        with patch("os.getenv", return_value=None):
            with pytest.raises(Exception):
                await e._execute_asana_action("create_task", {})

    @pytest.mark.asyncio
    async def test_asana_unknown_action_raises(self):
        e = _engine()
        e._get_token = Mock(return_value="tok")
        with patch("integrations.asana_service.asana_service"):
            with pytest.raises(ValueError):
                await e._execute_asana_action("bogus", {})

    @pytest.mark.asyncio
    async def test_hubspot_unknown_action(self):
        e = _engine()
        e._get_token = Mock(return_value="tok")
        with patch("integrations.hubspot_service.HubSpotService") as hs:
            svc = hs.return_value
            svc.access_token = "tok"
            out = await e._execute_hubspot_action("bogus", {})
            assert out["status"] == "success"
            assert "simulated" in out["result"]

    @pytest.mark.asyncio
    async def test_salesforce_no_token_raises(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts:
            ts.get_token.return_value = None
            with pytest.raises(Exception):
                await e._execute_salesforce_action("create_lead", {})

    @pytest.mark.asyncio
    async def test_github_unknown_action(self):
        e = _engine()
        e._get_token = Mock(return_value="tok")
        with patch("integrations.github_service.GitHubService"):
            out = await e._execute_github_action("bogus", {})
            assert out["status"] == "success"

    @pytest.mark.asyncio
    async def test_zoom_unknown_action(self):
        e = _engine()
        e._get_token = Mock(return_value="tok")
        with patch("integrations.zoom_service.ZoomService"):
            out = await e._execute_zoom_action("bogus", {})
            assert out["status"] == "success"

    @pytest.mark.asyncio
    async def test_notion_unknown_action(self):
        e = _engine()
        e._get_token = Mock(return_value="tok")
        with patch("integrations.notion_service.NotionService"):
            out = await e._execute_notion_action("bogus", {})
            assert out["status"] == "success"

    @pytest.mark.asyncio
    async def test_gmail_no_token_raises(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts:
            ts.get_token.return_value = None
            with pytest.raises(Exception):
                await e._execute_gmail_action("send_email", {})

    @pytest.mark.asyncio
    async def test_email_automation_draft_nudge(self):
        e = _engine()
        with patch("core.email_followup_engine.followup_engine"):
            out = await e._execute_email_automation_action("draft_nudge", {})
            assert out["status"] == "success"
            out2 = await e._execute_email_automation_action("unknown", {})
            assert out2["status"] == "error"

    @pytest.mark.asyncio
    async def test_mcp_action_missing_server_id(self):
        e = _engine()
        out = await e._execute_mcp_action("x", {})
        assert out["status"] == "error"


# ============================================================================
# _evaluate_condition failure paths + _get_token + load_workflow
# ============================================================================

class TestConditionAndHelpers:
    def test_evaluate_condition_injection_blocked(self):
        e = _engine()
        assert e._evaluate_condition(
            "${step1.output} == 'x' and __import__('os').system('id')",
            {"outputs": {"step1": {"output": "y"}}},
        ) is False

    def test_evaluate_condition_missing_var(self):
        e = _engine()
        assert e._evaluate_condition("${ghost.value} > 5", {"outputs": {}}) is False

    def test_get_token_helpers(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts:
            ts.get_token.return_value = {"access_token": "abc"}
            assert e._get_token("conn", "svc") == "abc"
            ts.get_token.side_effect = [None, {"access_token": "def"}]
            assert e._get_token("conn", "svc") == "def"
            ts.get_token.side_effect = [None, None]
            assert e._get_token("conn", "svc") is None

    def test_load_workflow_by_id_missing_file(self):
        e = _engine()
        with patch("os.path.exists", return_value=False):
            assert e._load_workflow_by_id("wf-1") is None

    def test_load_workflow_by_id_json_error(self):
        e = _engine()
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", Mock(side_effect=RuntimeError("boom"))):
            assert e._load_workflow_by_id("wf-1") is None

    def test_get_workflow_engine_singleton_locked(self):
        from core import workflow_engine as we
        old = we._workflow_engine
        we._workflow_engine = None
        try:
            e1 = we.get_workflow_engine()
            e2 = we.get_workflow_engine()
            assert e1 is e2
        finally:
            we._workflow_engine = old


# ============================================================================
# execute-generated workflow graph error branch (507-515) + sub-workflow statuses
# ============================================================================

class TestGraphAndSubworkflow:
    @pytest.mark.asyncio
    async def test_workflow_action_missing_id(self):
        e = _engine()
        with patch.object(WorkflowEngine, "_load_workflow_by_id", return_value=None):
            out = await e._execute_workflow_action("run", {"workflow_id": "missing"})
        assert out["status"] == "error"

    @pytest.mark.asyncio
    async def test_workflow_action_no_workflow_id(self):
        e = _engine()
        out = await e._execute_workflow_action("run", {})
        assert out["status"] == "error"

    @pytest.mark.asyncio
    async def test_workflow_action_completed_status(self):
        e = _engine()
        e.start_workflow = AsyncMock(return_value="exec-1")
        e.state_manager.get_execution_state = AsyncMock(
            return_value={"status": "COMPLETED", "outputs": {"a": 1}}
        )
        wf = {"id": "sub", "steps": [], "nodes": []}
        with patch.object(WorkflowEngine, "_load_workflow_by_id", return_value=wf):
            out = await e._execute_workflow_action("run", {"workflow_id": "sub"})
        assert out["status"] == "success"

    @pytest.mark.asyncio
    async def test_workflow_action_failed_status(self):
        e = _engine()
        e.start_workflow = AsyncMock(return_value="exec-1")
        e.state_manager.get_execution_state = AsyncMock(
            return_value={"status": "FAILED", "error": "nope"}
        )
        wf = {"id": "sub", "steps": [], "nodes": []}
        with patch.object(WorkflowEngine, "_load_workflow_by_id", return_value=wf):
            out = await e._execute_workflow_action("run", {"workflow_id": "sub"})
        assert out["status"] == "error"


# ============================================================================
# goal management + arbor refinement + main agent branches
# ============================================================================

class TestGoalManagementAndArbor:
    @pytest.mark.asyncio
    async def test_goal_management_actions(self):
        e = _engine()
        goal_engine = Mock()
        goal_engine.create_goal_from_text = AsyncMock(return_value=SimpleNamespace(
            dict=lambda: {"id": "g1", "title": "Goal"}
        ))
        goal_engine.check_for_escalations = AsyncMock(return_value=["esc-1"])
        goal = SimpleNamespace(
            sub_tasks=[SimpleNamespace(id="st1", status="pending")],
            dict=lambda: {"id": "g1", "sub_tasks": [{"id": "st1", "status": "done"}]},
        )
        goal_engine.goals = {"g1": goal}
        goal_engine.update_goal_progress = AsyncMock()

        with patch("core.goal_engine.goal_engine", goal_engine):
            out = await e._execute_goal_management_action(
                "create_goal", {"title": "T", "target_date": "2026-08-08T00:00:00Z"})
            assert out["id"] == "g1"

            out2 = await e._execute_goal_management_action("check_escalations", {})
            assert out2 == {"escalations": ["esc-1"]}

            out3 = await e._execute_goal_management_action(
                "update_subtask", {"goal_id": "g1", "sub_task_id": "st1", "status": "done"})
            assert out3["id"] == "g1"

            with pytest.raises(ValueError):
                await e._execute_goal_management_action("bogus", {})

    @pytest.mark.asyncio
    async def test_goal_management_missing_params(self):
        e = _engine()
        ge = Mock()
        ge.goals = {}
        with patch("core.goal_engine.goal_engine", ge):
            with pytest.raises(ValueError):
                await e._execute_goal_management_action("create_goal", {})
            with pytest.raises(ValueError):
                await e._execute_goal_management_action(
                    "update_subtask", {"goal_id": "missing", "sub_task_id": "x", "status": "done"})

    @pytest.mark.asyncio
    async def test_arbor_refinement_success(self):
        e = _engine()
        e.start_workflow = AsyncMock(return_value="exec-arbor")
        e.state_manager.get_execution_state = AsyncMock(
            return_value={"status": "COMPLETED", "outputs": {}}
        )
        wf = {"name": "Arbor WF", "id": "wf-arbor", "steps": [
            {"id": "s1", "config": {}},
            {"id": "s2", "config": {"requires": ["s1"]}},
        ]}
        with patch("core.hypothesis_tree_endpoints._persist_tree"), \
             patch("core.database.get_db_session"):
            result = await e.run_workflow_with_arbor_refinement(
                tenant_id="t1", workflow=wf, input_data={}, tier="solo")
        assert result["success"] is True
        assert result["tree_id"]

    @pytest.mark.asyncio
    async def test_arbor_refinement_failure(self):
        e = _engine()
        e.start_workflow = AsyncMock(return_value="exec-arbor2")
        e.state_manager.get_execution_state = AsyncMock(
            return_value={"status": "FAILED", "error": "boom"}
        )
        wf = {"name": "Arbor WF", "id": "wf-arbor2", "steps": [{"id": "s1", "config": {}}]}
        with patch("core.hypothesis_tree_endpoints._persist_tree"), \
             patch("core.database.get_db_session"):
            result = await e.run_workflow_with_arbor_refinement(
                tenant_id="t1", workflow=wf, input_data={})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_arbor_refinement_previous_tree(self):
        e = _engine()
        e.start_workflow = AsyncMock(return_value="exec-arbor3")
        e.state_manager.get_execution_state = AsyncMock(
            return_value={"status": "COMPLETED", "outputs": {}}
        )
        wf = {"name": "Arbor WF", "id": "wf-arbor3", "steps": []}
        prev = SimpleNamespace(negative_constraints=["no-x"])
        with patch("core.hypothesis_tree_endpoints._persist_tree"), \
             patch("core.database.get_db_session") as gds:
            db = Mock()
            q = Mock()
            q.filter.return_value.first.return_value = prev
            db.query.return_value = q
            gds.return_value.__enter__.return_value = db
            result = await e.run_workflow_with_arbor_refinement(
                tenant_id="t1", workflow=wf, input_data={}, previous_tree_id="prev-1")
        assert result["success"] is True


class TestMainAgentBranches:
    @pytest.mark.asyncio
    async def test_execute_main_agent_action_agent_not_found(self):
        e = _engine()
        with patch("core.database.get_db_session") as gds:
            db = Mock()
            q = Mock()
            q.filter.return_value.first.return_value = None
            db.query.return_value = q
            gds.return_value.__enter__.return_value = db
            out = await e._execute_main_agent_action("act", {"mcp_servers": []})
        # wrapper reports the inner agent-not-found result
        assert out["status"] == "success"
        assert out["result"]["success"] is False

    @pytest.mark.asyncio
    async def test_execute_agent_with_mcp_agent_not_found(self):
        e = _engine()
        with patch("core.database.get_db_session") as gds:
            db = Mock()
            q = Mock()
            q.filter.return_value.first.return_value = None
            db.query.return_value = q
            gds.return_value.__enter__.return_value = db
            out = await e._execute_agent_with_mcp({"agent_id": "ghost"})
        assert out["success"] is False

    @pytest.mark.asyncio
    async def test_execute_agent_with_mcp_llm_failure_fallback(self):
        e = _engine()
        agent = SimpleNamespace(id="a1", llm_provider="openai", llm_model="gpt-4o")
        with patch("core.database.get_db_session") as gds, \
             patch("core.llm_service.LLMService") as _LLM:
            db = Mock()
            q = Mock()
            q.filter.return_value.first.return_value = agent
            db.query.return_value = q
            gds.return_value.__enter__.return_value = db
            handler = Mock()
            handler.chat_completion = AsyncMock(side_effect=RuntimeError("llm down"))
            _LLM.return_value.handler = handler
            out = await e._execute_agent_with_mcp(
                {"agent_id": "a1", "action": "act", "input_data": {},
                 "mcp_connections": {}, "available_tools": []})
        assert out["success"] is True
        assert "fallback" in out["execution_method"]

    @pytest.mark.asyncio
    async def test_execute_agent_with_mcp_success(self):
        e = _engine()
        agent = SimpleNamespace(id="a1", llm_provider="openai", llm_model="gpt-4o")
        with patch("core.database.get_db_session") as gds, \
             patch("core.llm_service.LLMService") as _LLM:
            db = Mock()
            q = Mock()
            q.filter.return_value.first.return_value = agent
            db.query.return_value = q
            gds.return_value.__enter__.return_value = db
            handler = Mock()
            handler.chat_completion = AsyncMock(return_value={"content": "resp", "tool_calls": []})
            _LLM.return_value.handler = handler
            tools = [{"name": "t1", "description": "d", "input_schema": {}}]
            out = await e._execute_agent_with_mcp(
                {"agent_id": "a1", "action": "act", "input_data": "x",
                 "mcp_connections": {"s1": {}}, "available_tools": tools})
        assert out["success"] is True
        assert out["agent_response"] == "resp"
        assert out["tools_available"] == 1


# ============================================================================
# generic catalog executor (2455-2532) + slack/gmail branches + sub-workflow
# ============================================================================

class TestGenericExecutorAndBranches:
    @pytest.mark.asyncio
    async def test_generic_executor_cache_miss_db(self):
        e = _engine()
        catalog_item = SimpleNamespace(
            id="svc", actions=[{"name": "do_it", "method": "POST",
                                "url": "https://api.example.com/v1/{thing}"}]
        )
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        with patch("core.cache.cache", cache), \
             patch("core.workflow_engine.get_db_session") as gds, \
             patch("core.workflow_engine.httpx.AsyncClient") as _Client:
            db = Mock()
            q = Mock()
            q.filter.return_value.first.return_value = catalog_item
            db.query.return_value = q
            gds.return_value.__enter__.return_value = db
            resp = Mock()
            resp.raise_for_status = Mock()
            resp.json = Mock(return_value={"ok": True})
            _Client.return_value.__aenter__.return_value.request = AsyncMock(return_value=resp)
            out = await e._execute_generic_action(
                "svc", "do_it", {"thing": "abc", "x": 1}, connection_id="conn")
        assert out == {"ok": True}
        cache.set.assert_awaited_once()
        _Client.return_value.__aenter__.return_value.request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generic_executor_cached(self):
        e = _engine()
        cache = AsyncMock()
        cache.get = AsyncMock(return_value={"actions": [{"name": "a1", "method": "GET",
                                                         "url": "https://x.example/u"}]})
        with patch("core.cache.cache", cache), \
             patch("core.workflow_engine.httpx.AsyncClient") as _Client:
            resp = Mock()
            resp.raise_for_status = Mock()
            resp.json = Mock(return_value=["rows"])
            _Client.return_value.__aenter__.return_value.request = AsyncMock(return_value=resp)
            out = await e._execute_generic_action("svc", "a1", {"p": 1})
        assert out == ["rows"]

    @pytest.mark.asyncio
    async def test_generic_executor_missing_path_param(self):
        e = _engine()
        cache = AsyncMock()
        cache.get = AsyncMock(return_value={"actions": [{"name": "a1", "method": "GET",
                                                         "url": "https://x.example/{req}"}]})
        with patch("core.cache.cache", cache):
            with pytest.raises(ValueError):
                await e._execute_generic_action("svc", "a1", {})

    @pytest.mark.asyncio
    async def test_slack_message_actions(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts, \
             patch("integrations.slack_service_unified.slack_unified_service") as sus:
            ts.get_token.return_value = {"access_token": "tok"}
            sus.post_message = AsyncMock(return_value={"ok": True})
            sus.list_channels = AsyncMock(return_value=["c"])
            sus.get_team_info = AsyncMock(return_value={"team": 1})
            sus.get_channel_info = AsyncMock(return_value={"ch": 1})
            sus.get_channel_history = AsyncMock(return_value=["m"])
            sus.update_message = AsyncMock(return_value={"ok": True})
            sus.delete_message = AsyncMock(return_value={"ok": True})
            sus.search_messages = AsyncMock(return_value=["r"])
            sus.list_files = AsyncMock(return_value=["f"])

            assert (await e._execute_slack_action("chat_postMessage",
                    {"channel": "c", "text": "hi"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("list_channels", {}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("list_users", {}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("get_channel_info",
                    {"channel_id": "c"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("get_channel_history",
                    {"channel_id": "c"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("update_message",
                    {"channel_id": "c", "message_ts": "1", "text": "x"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("delete_message",
                    {"channel_id": "c", "message_ts": "1"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("search_messages",
                    {"query": "q"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("files_list",
                    {"channel_id": "c"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("files_get_upload_url_external",
                    {}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_slack_action("reactions_add", {}, connection_id="conn"))["status"] == "success"
            with pytest.raises(ValueError):
                await e._execute_slack_action("bogus", {}, connection_id="conn")

    @pytest.mark.asyncio
    async def test_slack_missing_param_raises(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts, \
             patch("integrations.slack_service_unified.slack_unified_service") as sus:
            ts.get_token.return_value = {"access_token": "tok"}
            sus.get_channel_info = AsyncMock()
            with pytest.raises(ValueError):
                await e._execute_slack_action("get_channel_info", {}, connection_id="conn")
            with pytest.raises(ValueError):
                await e._execute_slack_action("update_message", {}, connection_id="conn")

    @pytest.mark.asyncio
    async def test_gmail_draft_and_send_failure(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts, \
             patch("integrations.gmail_service.GmailService") as gs:
            ts.get_token.return_value = {"access_token": "tok"}
            svc = gs.return_value
            svc.send_message = Mock(return_value={"ok": True})
            svc.draft_message = Mock(return_value={"draft": 1})
            assert (await e._execute_gmail_action("send_email",
                    {"to": "a@b.c", "subject": "s", "body": "b"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_gmail_action("create_draft",
                    {"to": "a@b.c", "subject": "s", "body": "b"}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_gmail_action("whatever", {}))["status"] == "success"

            svc.send_message = Mock(return_value=None)
            with pytest.raises(Exception):
                await e._execute_gmail_action("send_email",
                    {"to": "a@b.c", "subject": "s", "body": "b"}, connection_id="conn")

    @pytest.mark.asyncio
    async def test_salesforce_actions(self):
        e = _engine()
        with patch("core.workflow_engine.token_storage") as ts, \
             patch("integrations.salesforce_service.SalesforceService") as ss:
            ts.get_token.return_value = {"access_token": "tok", "instance_url": "https://x"}
            svc = ss.return_value
            svc.create_client = Mock(return_value=object())
            svc.create_lead = AsyncMock(return_value={"id": 1})
            svc.create_contact = AsyncMock(return_value={"id": 2})
            svc.create_opportunity = AsyncMock(return_value={"id": 3})
            assert (await e._execute_salesforce_action("create_lead", {}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_salesforce_action("create_contact", {}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_salesforce_action("create_opportunity", {}, connection_id="conn"))["status"] == "success"
            assert (await e._execute_salesforce_action("other", {}, connection_id="conn"))["status"] == "success"

    @pytest.mark.asyncio
    async def test_github_notion_zoom_actions(self):
        e = _engine()
        e._get_token = Mock(return_value="tok")
        with patch("integrations.github_service.GitHubService") as gh:
            svc = gh.return_value
            svc.create_issue = Mock(return_value={"n": 1})
            out = await e._execute_github_action("create_issue",
                {"owner": "o", "repo": "r", "title": "t", "body": "b"})
            assert out["status"] == "success"
        with patch("integrations.notion_service.NotionService") as nn:
            svc = nn.return_value
            svc.create_page = Mock(return_value={"p": 1})
            out = await e._execute_notion_action("create_page",
                {"parent": {"database_id": "d"}, "properties": {}})
            assert out["status"] == "success"
        with patch("integrations.zoom_service.ZoomService") as zz:
            svc = zz.return_value
            svc.create_meeting = AsyncMock(return_value={"m": 1})
            out = await e._execute_zoom_action("create_meeting", {"topic": "t"})
            assert out["status"] == "success"

    @pytest.mark.asyncio
    async def test_workflow_action_cancelled_and_paused(self):
        e = _engine()
        e.start_workflow = AsyncMock(return_value="exec-x")
        wf = {"id": "sub", "steps": [], "nodes": []}
        with patch.object(WorkflowEngine, "_load_workflow_by_id", return_value=wf):
            e.state_manager.get_execution_state = AsyncMock(
                return_value={"status": "CANCELLED"})
            out = await e._execute_workflow_action("run", {"workflow_id": "sub"})
            assert out["status"] == "cancelled"

            e.state_manager.get_execution_state = AsyncMock(
                return_value={"status": "PAUSED"})
            out = await e._execute_workflow_action("run", {"workflow_id": "sub"})
            assert out["status"] == "paused"

            e.state_manager.get_execution_state = AsyncMock(
                return_value={"status": "RUNNING", "outputs": {}})
            out = await e._execute_workflow_action(
                "run", {"workflow_id": "sub", "timeout": 0.1})
            assert out["status"] in ("error", "timeout")
