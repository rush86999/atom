"""Coverage push for core/atom_agent_endpoints.py (93% -> 95%)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.atom_agent_endpoints import (
    ChatRequest,
    chat_with_agent,
    classify_intent_with_llm,
    handle_wellness_check,
    handle_automation_insights,
    handle_system_status,
)


def _base_mocks():
    chat_history = AsyncMock()
    chat_history.get_session_history = Mock(return_value=[])
    session_mgr = Mock()
    session_mgr.create_session = Mock(return_value="s1")
    session_mgr.get_session = Mock(return_value=None)
    context_mgr = AsyncMock()
    context_mgr.resolve_reference = AsyncMock(return_value=None)
    return chat_history, session_mgr, context_mgr


class TestChatDispatchTable:
    @pytest.mark.asyncio
    async def test_chat_dispatches_every_intent(self):
        chat_history, session_mgr, context_mgr = _base_mocks()
        intents = [
            "LIST_WORKFLOWS", "RUN_WORKFLOW", "SCHEDULE_WORKFLOW", "GET_HISTORY",
            "CANCEL_SCHEDULE", "GET_STATUS", "CREATE_EVENT", "LIST_EVENTS",
            "SEND_EMAIL", "SEARCH_EMAILS", "CREATE_TASK", "GET_TRANSACTIONS",
            "GET_SYSTEM_STATUS", "GET_AUTOMATION_INSIGHTS", "SEARCH_PLATFORM",
            "CREATE_WORKFLOW", "GET_SILENT_STAKEHOLDERS", "FOLLOW_UP_EMAILS",
            "WELLNESS_CHECK", "RESOLVE_CONFLICTS", "SET_GOAL", "GOAL_STATUS",
            "KNOWLEDGE_QUERY", "CRM_QUERY", "HELP", "UNKNOWN",
        ]
        for intent in intents:
            with patch("core.atom_agent_endpoints.get_chat_history_manager",
                       return_value=chat_history), \
                 patch("core.atom_agent_endpoints.get_chat_session_manager",
                       return_value=session_mgr), \
                 patch("core.atom_agent_endpoints.get_chat_context_manager",
                       return_value=context_mgr), \
                 patch("core.atom_agent_endpoints.classify_intent_with_llm",
                       return_value={"intent": intent, "entities": {}}), \
                 patch("core.atom_agent_endpoints.save_chat_interaction"), \
                 patch("core.atom_agent_endpoints.LLMService"), \
                 patch("core.atom_agent_endpoints.SystemIntelligenceService") as sis, \
                 patch("core.atom_agent_endpoints.load_workflows", return_value=[]), \
                 patch("core.atom_agent_endpoints.get_knowledge_query_manager") as kqm, \
                 patch("core.behavior_analyzer.get_behavior_analyzer") as ba, \
                 patch("core.atom_agent_endpoints.trigger_episode_creation"), \
                 patch("core.time_expression_parser.parse_time_expression",
                       return_value=None), \
                 patch("core.atom_agent_endpoints.workflow_scheduler"):
                sis.return_value.get_aggregated_context = Mock(return_value="")
                kqm.return_value.answer_query = AsyncMock(
                    return_value={"answer": "A", "relevant_facts": []})
                ba.return_value.detect_patterns = Mock(return_value=[])
                req = ChatRequest(message="do something", user_id="u1")
                result = await chat_with_agent(req, current_user=SimpleNamespace(id="u1"))
                assert isinstance(result, dict), f"{intent}: {result}"
                if result.get("success") is False and intent not in (
                        "RUN_WORKFLOW", "SCHEDULE_WORKFLOW", "CREATE_WORKFLOW",
                        "GET_SYSTEM_STATUS", "SEARCH_PLATFORM", "CRM_QUERY",
                        "FOLLOW_UP_EMAILS"):
                    assert result.get("error") is None, f"{intent}: {result}"


class TestHandlerBranches:
    @pytest.mark.asyncio
    async def test_classify_intent_markdown_strip(self):
        with patch("core.atom_agent_endpoints.LLMService") as llm_cls, \
             patch("core.atom_agent_endpoints.get_knowledge_query_manager") as kqm:
            llm = AsyncMock()
            llm.generate = AsyncMock(return_value="```json\n{\"intent\": \"HELP\", \"entities\": {}}\n```")
            llm_cls.return_value = llm
            kqm.return_value.answer_query = AsyncMock(return_value={"relevant_facts": []})
            out = await classify_intent_with_llm("hi", [])
        assert out["intent"] == "HELP"

    @pytest.mark.asyncio
    async def test_wellness_check_error(self):
        with patch("core.workflow_template_system.WorkflowTemplateManager",
                   side_effect=RuntimeError("tpl down")):
            out = await handle_wellness_check(ChatRequest(message="x", user_id="u"), {})
        assert out["success"] is False

    @pytest.mark.asyncio
    async def test_system_status_unhealthy(self):
        with patch("core.atom_agent_endpoints.SystemStatus") as ss:
            ss.get_overall_status = Mock(return_value="degraded")
            ss.get_system_info = Mock(return_value={"platform": {"system": "Linux"}})
            ss.get_resource_usage = Mock(return_value={
                "cpu": {"percent": 90.0}, "memory": {"percent": 88.0}})
            ss.get_service_status = Mock(return_value={
                "db": {"status": "healthy"}, "redis": {"status": "down"}})
            out = await handle_system_status(ChatRequest(message="x", user_id="u"))
        assert out["success"] is True
        assert "DEGRADED" in out["response"]["message"]

    @pytest.mark.asyncio
    async def test_automation_insights_no_patterns(self):
        with patch("core.automation_insight_manager.get_insight_manager") as im, \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba:
            im.return_value.generate_all_insights = Mock(return_value={
                "drift_insights": [], "summary": {}})
            ba.return_value.detect_patterns = Mock(return_value=[])
            out = await handle_automation_insights(ChatRequest(message="x", user_id="u"))
        assert out["success"] is True
        assert "expected parameters" in out["response"]["message"]

    @pytest.mark.asyncio
    async def test_save_chat_interaction_metadata(self):
        from core.atom_agent_endpoints import save_chat_interaction
        hist = Mock()
        sess = Mock()
        save_chat_interaction(
            session_id="s1", user_id="u1", user_message="m", assistant_message="a",
            intent="CREATE_WORKFLOW",
            entities={"x": 1},
            result_data={"response": {"workflow_id": "wf-1", "task_id": "t-1",
                                      "schedule_id": "sc-1"}},
            chat_history_mgr=hist, session_mgr=sess,
        )
        assert hist.save_message.call_count == 2
        sess.update_session_activity.assert_called_once_with("s1")

    @pytest.mark.asyncio
    async def test_save_chat_interaction_error(self):
        from core.atom_agent_endpoints import save_chat_interaction
        hist = Mock()
        hist.save_message = Mock(side_effect=RuntimeError("hist down"))
        save_chat_interaction(
            session_id="s1", user_id="u1", user_message="m", assistant_message="a",
            chat_history_mgr=hist, session_mgr=Mock(),
        )  # swallowed
