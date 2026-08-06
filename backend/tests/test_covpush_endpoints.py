"""Coverage-push tests for core/atom_agent_endpoints.py (TDD bug-hunt included)."""

import os

os.environ["TESTING"] = "1"

import contextlib
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.atom_agent_endpoints import (
    ChatMessage,
    ChatRequest,
    ExecuteGeneratedRequest,
    ExecuteGeneratedRequest as _EGR,
    _gate_workflow_permission,
    chat_stream_agent,
    chat_with_agent,
    classify_intent_with_llm,
    execute_generated_workflow,
    fallback_intent_classification,
    get_session_history,
    handle_automation_insights,
    handle_cancel_schedule,
    handle_create_event,
    handle_create_workflow,
    handle_crm_intent,
    handle_finance_intent,
    handle_follow_up_emails,
    handle_get_history,
    handle_get_status,
    handle_goal_status,
    handle_help_request,
    handle_knowledge_query,
    handle_list_events,
    handle_list_workflows,
    handle_platform_search,
    handle_resolve_conflicts,
    handle_run_workflow,
    handle_schedule_workflow,
    handle_search_emails,
    handle_send_email,
    handle_set_goal,
    handle_silent_stakeholders,
    handle_system_status,
    handle_task_intent,
    handle_wellness_check,
    list_sessions,
    retrieve_baseline,
    retrieve_hybrid,
    save_chat_interaction,
)


def _request(message="hi", user_id="u1", session_id=None, **kw):
    return ChatRequest(message=message, user_id=user_id, session_id=session_id, **kw)


def _user(uid="u1"):
    u = MagicMock()
    u.id = uid
    u.email = "u@example.com"
    return u


class TestSaveChatInteraction:
    def test_schedule_metadata(self):
        mgr = MagicMock()
        sess = MagicMock()
        save_chat_interaction(
            "s1", "u1", "m", "a", intent="x",
            result_data={"response": {"schedule_id": "sch-1"}},
            chat_history_mgr=mgr, session_mgr=sess,
        )
        meta = mgr.save_message.call_args_list[1][1]["metadata"]
        assert meta["schedule_id"] == "sch-1"

    def test_task_metadata(self):
        mgr = MagicMock()
        save_chat_interaction(
            "s1", "u1", "m", "a",
            result_data={"response": {"task_id": "t-1"}},
            chat_history_mgr=mgr, session_mgr=MagicMock(),
        )
        meta = mgr.save_message.call_args_list[1][1]["metadata"]
        assert meta["task_id"] == "t-1"

    def test_no_intent_metadata(self):
        mgr = MagicMock()
        save_chat_interaction(
            "s1", "u1", "m", "a", intent=None,
            chat_history_mgr=mgr, session_mgr=MagicMock(),
        )
        meta = mgr.save_message.call_args_list[1][1]["metadata"]
        assert meta == {"intent": None}

    def test_default_managers(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager") as g1, \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as g2:
            save_chat_interaction("s1", "u1", "m", "a")
        g1.assert_called_once_with("default")
        g2.assert_called_once_with("default")


class TestSessions:
    @patch("core.atom_agent_endpoints.get_chat_session_manager")
    def test_list_sessions_with_defaults(self, mgr_mock):
        sess = MagicMock()
        sess.list_user_sessions.return_value = [
            {"session_id": "s1", "last_active": "t", "metadata": {}}
        ]
        mgr_mock.return_value = sess
        result = list_sessions.__wrapped__(_user()) if hasattr(list_sessions, "__wrapped__") else None
        import asyncio
        result = asyncio.run(list_sessions(_user()))
        assert result["success"] is True
        assert result["sessions"][0]["title"] == "Session s1"

    @patch("core.atom_agent_endpoints.get_chat_session_manager")
    def test_list_sessions_error(self, mgr_mock):
        mgr_mock.return_value.list_user_sessions.side_effect = Exception("db")
        import asyncio
        result = asyncio.run(list_sessions(_user()))
        assert result["success"] is False

    @patch("core.atom_agent_endpoints.get_chat_session_manager")
    def test_get_history_not_found(self, mgr_mock):
        mgr_mock.return_value.get_session.return_value = None
        import asyncio
        result = asyncio.run(get_session_history("s1", _user()))
        assert result["success"] is False

    @patch("core.atom_agent_endpoints.get_chat_session_manager")
    def test_get_history_other_users_forbidden(self, mgr_mock):
        mgr_mock.return_value.get_session.return_value = {"user_id": "other"}
        import asyncio
        with pytest.raises(HTTPException):
            asyncio.run(get_session_history("s1", _user()))

    @patch("core.atom_agent_endpoints.get_chat_history_manager")
    @patch("core.atom_agent_endpoints.get_chat_session_manager")
    def test_get_history_parses_metadata(self, sess_mock, chat_mock):
        sess_mock.return_value.get_session.return_value = {"user_id": "u1"}
        chat_mock.return_value.get_session_history.return_value = [
            {"id": "m1", "role": "user", "text": "hi",
             "created_at": "now", "metadata": '{"intent": "X"}'}
        ]
        import asyncio
        result = asyncio.run(get_session_history("s1", _user()))
        assert result["messages"][0]["metadata"] == {"intent": "X"}

    @patch("core.atom_agent_endpoints.get_chat_history_manager")
    @patch("core.atom_agent_endpoints.get_chat_session_manager")
    def test_get_history_bad_json_metadata(self, sess_mock, chat_mock):
        sess_mock.return_value.get_session.return_value = {"user_id": "u1"}
        chat_mock.return_value.get_session_history.return_value = [
            {"id": "m1", "role": "user", "text": "hi", "metadata": "not-json{{"}
        ]
        import asyncio
        result = asyncio.run(get_session_history("s1", _user()))
        assert result["success"] is True

    @patch("core.atom_agent_endpoints.get_chat_history_manager")
    @patch("core.atom_agent_endpoints.get_chat_session_manager")
    def test_get_history_generic_exception(self, sess_mock, chat_mock):
        sess_mock.return_value.get_session.side_effect = Exception("boom")
        import asyncio
        result = asyncio.run(get_session_history("s1", _user()))
        assert result["success"] is False


class TestIntentClassification:
    @pytest.mark.asyncio
    async def test_classify_with_markdown_json(self):
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager") as km, \
             patch("core.atom_agent_endpoints.LLMService") as llm_cls:
            km.return_value.answer_query = AsyncMock(return_value={"relevant_facts": ["f1"]})
            llm = MagicMock()
            llm.generate = AsyncMock(return_value='```json\n{"intent": "HELP", "entities": {}}\n```')
            llm_cls.return_value = llm
            result = await classify_intent_with_llm("help", [])
        assert result["intent"] == "HELP"

    @pytest.mark.asyncio
    async def test_classify_plain_json(self):
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager") as km, \
             patch("core.atom_agent_endpoints.LLMService") as llm_cls:
            km.return_value.answer_query = AsyncMock(return_value=None)
            llm = MagicMock()
            llm.generate = AsyncMock(return_value='{"intent": "CREATE_EVENT", "entities": {"summary": "m"}}')
            llm_cls.return_value = llm
            result = await classify_intent_with_llm("meeting", [ChatMessage(role="user", content="x")])
        assert result["intent"] == "CREATE_EVENT"

    @pytest.mark.asyncio
    async def test_classify_invalid_json_falls_back(self):
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager") as km, \
             patch("core.atom_agent_endpoints.LLMService") as llm_cls:
            km.return_value.answer_query = AsyncMock(side_effect=Exception("km down"))
            llm = MagicMock()
            llm.generate = AsyncMock(return_value="not json")
            llm_cls.return_value = llm
            result = await classify_intent_with_llm("list workflows", [])
        assert result["intent"] == "LIST_WORKFLOWS"

    @pytest.mark.asyncio
    async def test_classify_llm_exception_falls_back(self):
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager") as km, \
             patch("core.atom_agent_endpoints.LLMService") as llm_cls:
            km.return_value.answer_query = AsyncMock(return_value={"relevant_facts": []})
            llm_cls.side_effect = Exception("no llm")
            result = await classify_intent_with_llm("send email to bob", [])
        assert result["intent"] == "SEND_EMAIL"


class TestFallbackIntentClassification:
    def test_schedule_with_parser(self):
        with patch("core.time_expression_parser.parse_with_patterns",
                   return_value={"matched_text": "every weekday at 9am"}):
            r = fallback_intent_classification("Schedule the report to run every weekday at 9am")
        assert r["intent"] == "SCHEDULE_WORKFLOW"
        assert r["entities"]["time_expression"] == "every weekday at 9am"

    def test_schedule_without_parser(self):
        with patch("core.time_expression_parser.parse_with_patterns", side_effect=ImportError):
            r = fallback_intent_classification("schedule backup workflow")
        assert r["intent"] == "SCHEDULE_WORKFLOW"

    def test_create_workflow(self):
        assert fallback_intent_classification("create a workflow")["intent"] == "CREATE_WORKFLOW"

    def test_list_workflows(self):
        assert fallback_intent_classification("list workflows")["intent"] == "LIST_WORKFLOWS"

    def test_run_workflow(self):
        r = fallback_intent_classification("run workflow daily")
        assert r["intent"] == "RUN_WORKFLOW"

    def test_get_history(self):
        assert fallback_intent_classification("show execution history")["intent"] == "GET_HISTORY"

    def test_conflicts(self):
        assert fallback_intent_classification("find calendar conflicts")["intent"] == "RESOLVE_CONFLICTS"

    def test_create_event(self):
        assert fallback_intent_classification("schedule a meeting tomorrow")["intent"] == "CREATE_EVENT"

    def test_list_events(self):
        assert fallback_intent_classification("whats on my calendar")["intent"] == "LIST_EVENTS"

    def test_send_email(self):
        assert fallback_intent_classification("send email to x")["intent"] == "SEND_EMAIL"

    def test_search_emails(self):
        assert fallback_intent_classification("search my inbox for invoices")["intent"] == "SEARCH_EMAILS"

    def test_follow_up(self):
        assert fallback_intent_classification("who should I follow up with")["intent"] == "FOLLOW_UP_EMAILS"

    def test_create_task(self):
        assert fallback_intent_classification("add a task")["intent"] == "CREATE_TASK"

    def test_list_tasks(self):
        assert fallback_intent_classification("list my tasks")["intent"] == "LIST_TASKS"

    def test_transactions(self):
        assert fallback_intent_classification("show my spending")["intent"] == "GET_TRANSACTIONS"

    def test_balance(self):
        assert fallback_intent_classification("what is my balance")["intent"] == "CHECK_BALANCE"

    def test_invoice(self):
        assert fallback_intent_classification("invoice status")["intent"] == "INVOICE_STATUS"

    def test_crm(self):
        assert fallback_intent_classification("how many leads do we have")["intent"] == "CRM_QUERY"

    def test_system_status(self):
        assert fallback_intent_classification("system status")["intent"] == "GET_SYSTEM_STATUS"

    def test_wellness(self):
        assert fallback_intent_classification("I feel burnout")["intent"] == "WELLNESS_CHECK"

    def test_set_goal(self):
        assert fallback_intent_classification("set a goal")["intent"] == "SET_GOAL"

    def test_goal_status(self):
        assert fallback_intent_classification("goal progress")["intent"] == "GOAL_STATUS"

    def test_search_platform(self):
        r = fallback_intent_classification("search for project docs")
        assert r["intent"] == "SEARCH_PLATFORM"
        assert "project docs" in r["entities"]["query"]

    def test_knowledge_query(self):
        assert fallback_intent_classification("who worked on project x")["intent"] == "KNOWLEDGE_QUERY"

    def test_unknown(self):
        assert fallback_intent_classification("gibberish zzz")["intent"] == "UNKNOWN"


class TestWorkflowHandlers:
    @pytest.mark.asyncio
    async def test_create_workflow_success(self):
        wf = {"id": "wf1", "name": "Daily", "nodes": [{"id": "n1"}], "connections": [], "template_id": "tpl"}
        with patch("core.atom_agent_endpoints.get_orchestrator") as orch, \
             patch("core.atom_agent_endpoints.load_workflows", return_value=[]), \
             patch("core.atom_agent_endpoints.save_workflows") as save:
            orch.return_value.generate_dynamic_workflow = AsyncMock(return_value=wf)
            result = await handle_create_workflow(_request(), {"description": "d"})
        assert result["success"] is True
        assert result["response"]["workflow_id"] == "wf1"
        save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_workflow_empty(self):
        with patch("core.atom_agent_endpoints.get_orchestrator") as orch:
            orch.return_value.generate_dynamic_workflow = AsyncMock(return_value=None)
            result = await handle_create_workflow(_request(), {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_create_workflow_exception(self):
        with patch("core.atom_agent_endpoints.get_orchestrator") as orch:
            orch.return_value.generate_dynamic_workflow = AsyncMock(side_effect=Exception("boom"))
            result = await handle_create_workflow(_request(), {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_workflows_empty(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            result = await handle_list_workflows(_request())
        assert result["success"] is True
        assert "No workflows" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_list_workflows_populated(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[
            {"name": "A", "workflow_id": "w1"}, {"name": "B", "workflow_id": "w2"},
        ]):
            result = await handle_list_workflows(_request())
        assert "Found 2 workflows" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_gate_permission_no_user_noncritical(self):
        assert await _gate_workflow_permission(None, {"steps": []}, "run") is None

    @pytest.mark.asyncio
    async def test_gate_permission_no_user_critical(self):
        with patch("core.atom_agent_endpoints.has_critical_step", return_value=True):
            r = await _gate_workflow_permission(None, {"steps": [{"config": {}}]}, "run")
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_gate_permission_user_ok(self):
        with patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()):
            assert await _gate_workflow_permission(_user(), {"steps": []}, "run") is None

    @pytest.mark.asyncio
    async def test_gate_permission_user_denied(self):
        with patch("core.atom_agent_endpoints.require_workflow_executor",
                   new=AsyncMock(side_effect=HTTPException(403))):
            r = await _gate_workflow_permission(_user(), {"steps": []}, "run")
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_run_workflow_no_ref(self):
        result = await handle_run_workflow(_request(), {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_run_workflow_not_found(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            result = await handle_run_workflow(_request(), {"workflow_ref": "x"})
        assert "not found" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_run_workflow_no_engine(self):
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1", "id": "w1"}]):
            result = await handle_run_workflow(_request(), {"workflow_ref": "daily"})
        assert result["success"] is False
        assert "AutomationEngine not available" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_run_workflow_success(self):
        engine = MagicMock()
        engine.execute_workflow_definition = AsyncMock(return_value={"ok": True})
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1", "id": "w1"}]), \
             patch("core.atom_agent_endpoints.AutomationEngine", return_value=engine):
            result = await handle_run_workflow(_request(), {"workflow_ref": "daily"}, user=_user())
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_workflow_exception(self):
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1", "id": "w1"}]), \
             patch("core.atom_agent_endpoints.AutomationEngine",
                   side_effect=Exception("engine down")):
            result = await handle_run_workflow(_request(), {"workflow_ref": "daily"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_schedule_missing_fields(self):
        result = await handle_schedule_workflow(_request(), {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_schedule_not_found(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            result = await handle_schedule_workflow(
                _request(), {"workflow_ref": "x", "time_expression": "daily"}
            )
        assert "not found" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_schedule_parse_failure(self):
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1"}]), \
             patch("core.time_expression_parser.parse_time_expression",
                   new=AsyncMock(return_value=None)):
            result = await handle_schedule_workflow(
                _request(), {"workflow_ref": "daily", "time_expression": "whenever"}
            )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_schedule_cron(self):
        schedule = {"schedule_type": "cron", "cron_expression": "0 9 * * 1-5", "human_readable": "every weekday at 9am"}
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1"}]), \
             patch("core.time_expression_parser.parse_time_expression", new=AsyncMock(return_value=schedule)), \
             patch("core.atom_agent_endpoints.workflow_scheduler") as sched, \
             patch("core.atom_agent_endpoints.RBACService.check_permission", return_value=True):
            result = await handle_schedule_workflow(
                _request(), {"workflow_ref": "daily", "time_expression": "weekdays 9am"}, user=_user()
            )
        assert result["success"] is True
        sched.schedule_workflow_cron.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_interval(self):
        schedule = {"schedule_type": "interval", "interval_minutes": 30, "human_readable": "every 30 minutes"}
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1"}]), \
             patch("core.time_expression_parser.parse_time_expression", new=AsyncMock(return_value=schedule)), \
             patch("core.atom_agent_endpoints.workflow_scheduler") as sched:
            result = await handle_schedule_workflow(
                _request(), {"workflow_ref": "daily", "time_expression": "every 30 min"}
            )
        assert result["success"] is True
        sched.schedule_workflow_interval.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_date(self):
        schedule = {"schedule_type": "date", "run_date": "2026-12-01", "human_readable": "on Dec 1"}
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1"}]), \
             patch("core.time_expression_parser.parse_time_expression", new=AsyncMock(return_value=schedule)), \
             patch("core.atom_agent_endpoints.workflow_scheduler") as sched:
            result = await handle_schedule_workflow(
                _request(), {"workflow_ref": "daily", "time_expression": "on dec 1"}
            )
        assert result["success"] is True
        sched.schedule_workflow_once.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_exception(self):
        schedule = {"schedule_type": "cron", "cron_expression": "* * * * *", "human_readable": "x"}
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Daily", "workflow_id": "w1"}]), \
             patch("core.time_expression_parser.parse_time_expression", new=AsyncMock(return_value=schedule)), \
             patch("core.atom_agent_endpoints.workflow_scheduler") as sched:
            sched.schedule_workflow_cron.side_effect = Exception("sched down")
            result = await handle_schedule_workflow(
                _request(), {"workflow_ref": "daily", "time_expression": "daily"}
            )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_history_no_ref(self):
        assert (await handle_get_history(_request(), {}))["success"] is False

    @pytest.mark.asyncio
    async def test_get_history_with_ref(self):
        assert (await handle_get_history(_request(), {"workflow_ref": "w1"}))["success"] is True

    @pytest.mark.asyncio
    async def test_cancel_schedule_by_id(self):
        with patch("core.atom_agent_endpoints.workflow_scheduler") as sched:
            sched.remove_job.return_value = True
            r = await handle_cancel_schedule(_request(), {"schedule_id": "j1"})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_cancel_schedule_missing(self):
        with patch("core.atom_agent_endpoints.workflow_scheduler") as sched:
            sched.remove_job.return_value = False
            r = await handle_cancel_schedule(_request(), {"schedule_id": "j1"})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_cancel_schedule_by_ref(self):
        r = await handle_cancel_schedule(_request(), {"workflow_ref": "w1"})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_cancel_schedule_none(self):
        r = await handle_cancel_schedule(_request(), {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_get_status(self):
        assert (await handle_get_status(_request(), {}))["success"] is True


class TestCrmCalendarEmail:
    @pytest.mark.asyncio
    async def test_crm_success(self):
        with patch("core.database.get_db_session"), \
             patch("sales.assistant.SalesAssistant") as sa:
            sa.return_value.answer_sales_query = AsyncMock(return_value="3 hot leads")
            r = await handle_crm_intent(_request("leads"), {"workspace_id": "w"})
        assert r["success"] is True
        assert "3 hot leads" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_crm_exception(self):
        with patch("core.database.get_db_session"), \
             patch("sales.assistant.SalesAssistant") as sa:
            sa.return_value.answer_sales_query = AsyncMock(side_effect=Exception("sales down"))
            r = await handle_crm_intent(_request("leads"), {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_create_event(self):
        r = await handle_create_event(_request(), {"summary": "Sync", "start_time": "tomorrow"})
        assert r["success"] is True
        assert "Sync" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_list_events_success(self):
        with patch("core.atom_agent_endpoints.GoogleCalendarService") as g:
            g.return_value.get_events = AsyncMock(return_value=[
                {"summary": "Standup", "start": {"dateTime": "2026-01-01T09:00"}}
            ])
            r = await handle_list_events(_request(), {})
        assert "Standup" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_list_events_empty(self):
        with patch("core.atom_agent_endpoints.GoogleCalendarService") as g:
            g.return_value.get_events = AsyncMock(return_value=[])
            r = await handle_list_events(_request(), {})
        assert "No upcoming events" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_list_events_exception(self):
        with patch("core.atom_agent_endpoints.GoogleCalendarService") as g:
            g.return_value.get_events = AsyncMock(side_effect=Exception("cal down"))
            r = await handle_list_events(_request(), {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_send_email(self):
        r = await handle_send_email(_request(), {"recipient": "a@b.c", "subject": "Hi"})
        assert r["success"] is True
        assert "a@b.c" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_search_emails_found(self):
        with patch("core.atom_agent_endpoints.GmailService") as g:
            g.return_value.search_messages = MagicMock(return_value=[{"id": 1}, {"id": 2}])
            r = await handle_search_emails(_request(), {"query": "invoice"})
        assert r["success"] is True
        assert "Found 2 emails" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_search_emails_none(self):
        with patch("core.atom_agent_endpoints.GmailService") as g:
            g.return_value.search_messages = MagicMock(return_value=[])
            r = await handle_search_emails(_request(), {"query": "invoice"})
        assert "No emails found" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_search_emails_exception(self):
        with patch("core.atom_agent_endpoints.GmailService") as g:
            g.return_value.search_messages = MagicMock(side_effect=Exception("gmail down"))
            r = await handle_search_emails(_request(), {"query": "invoice"})
        assert r["success"] is False


class TestKnowledgeTaskFinance:
    @pytest.mark.asyncio
    async def test_knowledge_query_success(self):
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager") as km:
            km.return_value.answer_query = AsyncMock(return_value={"answer": "the answer"})
            r = await handle_knowledge_query(_request(), {"query": "q"})
        assert r["success"] is True
        assert r["response"]["message"] == "the answer"

    @pytest.mark.asyncio
    async def test_knowledge_query_exception(self):
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager") as km:
            km.return_value.answer_query = AsyncMock(side_effect=Exception("kg down"))
            r = await handle_knowledge_query(_request(), {"query": "q"})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_task_create_success(self):
        with patch("core.atom_agent_endpoints.create_task", new=AsyncMock(return_value={"id": 1})):
            r = await handle_task_intent("CREATE_TASK", {"title": "Buy milk"}, _request())
        assert r["success"] is True
        assert "Buy milk" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_task_create_asana_platform(self):
        with patch("core.atom_agent_endpoints.create_task", new=AsyncMock(return_value={"id": 2})):
            r = await handle_task_intent("CREATE_TASK", {"title": "Sync in asana"}, _request())
        assert "asana" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_task_create_exception(self):
        with patch("core.atom_agent_endpoints.create_task",
                   new=AsyncMock(side_effect=Exception("task down"))):
            r = await handle_task_intent("CREATE_TASK", {"title": "x"}, _request())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_task_list_success(self):
        with patch("core.atom_agent_endpoints.get_tasks",
                   new=AsyncMock(return_value={"tasks": [{"id": 1}, {"id": 2}]})):
            r = await handle_task_intent("LIST_TASKS", {}, _request())
        assert "Found 2 tasks" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_task_list_exception(self):
        with patch("core.atom_agent_endpoints.get_tasks",
                   new=AsyncMock(side_effect=Exception("list down"))):
            r = await handle_task_intent("LIST_TASKS", {}, _request())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_task_unknown(self):
        r = await handle_task_intent("WEIRD", {}, _request())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_finance_transactions(self):
        r = await handle_finance_intent("GET_TRANSACTIONS", {}, _request())
        assert r["success"] is True
        assert len(r["response"]["data"]["transactions"]) == 2

    @pytest.mark.asyncio
    async def test_finance_balance(self):
        r = await handle_finance_intent("CHECK_BALANCE", {}, _request())
        assert r["response"]["data"]["balance"] == 12450.00

    @pytest.mark.asyncio
    async def test_finance_invoice(self):
        with patch("core.atom_agent_endpoints.list_quickbooks_items",
                   new=AsyncMock(return_value={"items": ["i1", "i2"]})):
            r = await handle_finance_intent("INVOICE_STATUS", {}, _request())
        assert "Found 2 active invoices" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_finance_invoice_exception(self):
        with patch("core.atom_agent_endpoints.list_quickbooks_items",
                   new=AsyncMock(side_effect=Exception("qb down"))):
            r = await handle_finance_intent("INVOICE_STATUS", {}, _request())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_finance_unknown(self):
        r = await handle_finance_intent("WEIRD", {}, _request())
        assert r["success"] is False

    def test_help_request(self):
        r = handle_help_request()
        assert r["success"] is True
        assert "Universal ATOM Assistant" in r["response"]["message"]


class TestExecuteGenerated:
    @pytest.mark.asyncio
    async def test_execute_generated_not_found(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            r = await execute_generated_workflow(_EGR(workflow_id="w1", input_data={}), _user())
        assert r["success"] is False
        assert r["error"] == "Workflow not found"

    @pytest.mark.asyncio
    async def test_execute_generated_gate_denied(self):
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"id": "w1", "name": "x", "steps": []}]), \
             patch("core.atom_agent_endpoints.require_workflow_executor",
                   new=AsyncMock(side_effect=HTTPException(403))):
            with pytest.raises(HTTPException):
                await execute_generated_workflow(_EGR(workflow_id="w1", input_data={}), _user())

    @pytest.mark.asyncio
    async def test_execute_generated_no_engine(self):
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"id": "w1", "name": "x", "steps": []}]), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()):
            r = await execute_generated_workflow(_EGR(workflow_id="w1", input_data={}), _user())
        assert r["success"] is False
        assert "AutomationEngine not available" in r["error"]

    @pytest.mark.asyncio
    async def test_execute_generated_success(self):
        engine = MagicMock()
        engine.execute_workflow_definition = AsyncMock(return_value={"ok": True})
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"id": "w1", "name": "x", "steps": []}]), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()), \
             patch("core.atom_agent_endpoints.AutomationEngine", return_value=engine):
            r = await execute_generated_workflow(_EGR(workflow_id="w1", input_data={}), _user())
        assert r["success"] is True
        assert r["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_generated_exception(self):
        with patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"id": "w1", "name": "x", "steps": []}]), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()), \
             patch("core.atom_agent_endpoints.AutomationEngine",
                   side_effect=Exception("engine down")):
            r = await execute_generated_workflow(_EGR(workflow_id="w1", input_data={}), _user())
        assert r["success"] is False
        assert r["error"] == "Internal server error"


class TestAdvancedHandlers:
    @pytest.mark.asyncio
    async def test_follow_up_no_template(self):
        with patch("core.workflow_template_system.template_manager", create=True) as tm:
            tm.get_template.return_value = None
            r = await handle_follow_up_emails(_request(), {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_follow_up_with_template(self):
        with patch("core.workflow_template_system.template_manager", create=True) as tm:
            tm.get_template.return_value = {"id": "t"}
            r = await handle_follow_up_emails(_request(), {})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_follow_up_exception(self):
        tm = MagicMock()
        tm.get_template.side_effect = Exception("tm down")
        with patch("core.workflow_template_system.template_manager", new=tm, create=True):
            r = await handle_follow_up_emails(_request(), {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_wellness_check(self):
        with patch("core.workflow_template_system.template_manager", create=True) as tm:
            tm.get_template.return_value = {"id": "t"}
            r = await handle_wellness_check(_request(), {})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_wellness_check_exception(self):
        tm = MagicMock()
        tm.get_template.side_effect = Exception("tm down")
        with patch("core.workflow_template_system.template_manager", new=tm, create=True):
            r = await handle_wellness_check(_request(), {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_automation_insights_drift(self):
        with patch("core.automation_insight_manager.get_insight_manager") as gi, \
             patch("core.behavior_analyzer.get_behavior_analyzer") as gb:
            gi.return_value.generate_all_insights.return_value = [
                {"drift_score": 0.9, "workflow_id": "w1"}
            ]
            gb.return_value.detect_patterns.return_value = [
                {"description": "d", "name": "n", "suggested_actions": ["w2"]}
            ]
            r = await handle_automation_insights(_request())
        assert r["success"] is True
        assert "Drift Detected" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_automation_insights_clean(self):
        with patch("core.automation_insight_manager.get_insight_manager") as gi, \
             patch("core.behavior_analyzer.get_behavior_analyzer") as gb:
            gi.return_value.generate_all_insights.return_value = []
            gb.return_value.detect_patterns.return_value = []
            r = await handle_automation_insights(_request())
        assert "running within expected parameters" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_automation_insights_exception(self):
        with patch("core.automation_insight_manager.get_insight_manager",
                   side_effect=Exception("boom")):
            r = await handle_automation_insights(_request())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_resolve_conflicts(self):
        r = await handle_resolve_conflicts(_request(), {})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_set_goal(self):
        with patch("core.workflow_template_system.template_manager", create=True) as tm:
            tm.get_template.return_value = {"id": "t"}
            r = await handle_set_goal(_request(), {"goal_text": "Win the deal"})
        assert r["success"] is True
        assert "Win the deal" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_set_goal_exception(self):
        with patch("core.workflow_template_system.WorkflowTemplateManager",
                   side_effect=Exception("tm init down")):
            r = await handle_set_goal(_request(), {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_silent_stakeholders_none(self):
        with patch("core.stakeholder_engine.get_stakeholder_engine") as ge:
            ge.return_value.identify_silent_stakeholders = AsyncMock(return_value=[])
            r = await handle_silent_stakeholders(_request())
        assert r["success"] is True
        assert "everyone seems to be actively engaged" in r["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_silent_stakeholders_some(self):
        with patch("core.stakeholder_engine.get_stakeholder_engine") as ge:
            ge.return_value.identify_silent_stakeholders = AsyncMock(return_value=[
                {"name": "Bob", "email": "b@x.com", "days_since": 10, "suggested_outreach": "hi"}
            ])
            r = await handle_silent_stakeholders(_request())
        assert r["success"] is True
        assert "Bob" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_silent_stakeholders_exception(self):
        with patch("core.stakeholder_engine.get_stakeholder_engine",
                   side_effect=Exception("boom")):
            r = await handle_silent_stakeholders(_request())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_goal_status(self):
        r = await handle_goal_status(_request(), {})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_system_status_success(self):
        with patch("core.atom_agent_endpoints.SystemStatus") as ss:
            ss.get_overall_status.return_value = "healthy"
            ss.get_system_info.return_value = {"platform": {"system": "Darwin"}}
            ss.get_resource_usage.return_value = {"cpu": {"percent": 12.3}, "memory": {"percent": 40.0}}
            ss.get_service_status.return_value = {"db": {"status": "healthy"}, "cache": {"status": "down"}}
            r = await handle_system_status(_request())
        assert r["success"] is True
        assert "healthy" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_system_status_exception(self):
        with patch("core.atom_agent_endpoints.SystemStatus") as ss:
            ss.get_overall_status.side_effect = Exception("boom")
            r = await handle_system_status(_request())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_platform_search_results(self):
        res = SimpleNamespace(
            success=True,
            results=[
                SimpleNamespace(**{"metadata": {"type": "doc"}, "text": "snippet text here",
                                  "dict": lambda: {"id": 1}}),
                SimpleNamespace(**{"metadata": {"type": "doc"}, "text": "short",
                                  "dict": lambda: {"id": 2}}),
            ],
            total_count=7,
        )
        with patch("core.atom_agent_endpoints.unified_hybrid_search", new=AsyncMock(return_value=res)):
            r = await handle_platform_search(_request(), {"query": "docs"})
        assert r["success"] is True
        assert "Found 2 results" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_platform_search_no_results(self):
        res = SimpleNamespace(success=True, results=[], total_count=0)
        with patch("core.atom_agent_endpoints.unified_hybrid_search", new=AsyncMock(return_value=res)):
            r = await handle_platform_search(_request(), {"query": "zzz"})
        assert "No results found" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_platform_search_exception(self):
        with patch("core.atom_agent_endpoints.unified_hybrid_search",
                   new=AsyncMock(side_effect=Exception("search down"))):
            r = await handle_platform_search(_request(), {"query": "zzz"})
        assert r["success"] is False


class TestChatWithAgent:
    @pytest.mark.asyncio
    async def test_chat_help_intent(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()) as ch, \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "HELP", "entities": {}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba:
            sm.return_value.create_session.return_value = "sess-1"
            ba.return_value.detect_patterns.return_value = []
            r = await chat_with_agent(_request("help me"), _user())
        assert r["success"] is True
        assert r["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_chat_unknown_intent(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "UNKNOWN", "entities": {}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba:
            sm.return_value.create_session.return_value = "sess-2"
            ba.return_value.detect_patterns.return_value = []
            r = await chat_with_agent(_request("whatever"), _user())
        assert r["success"] is True
        assert "Workflows, Calendar" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_chat_uses_existing_session(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()) as ch, \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "HELP", "entities": {}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba:
            sm.return_value.get_session.return_value = {"user_id": "u1"}
            ch.return_value.get_session_history.return_value = [
                {"role": "user", "text": "prev"}
            ]
            ba.return_value.detect_patterns.return_value = []
            r = await chat_with_agent(
                _request("help me", session_id="sess-9"), _user()
            )
        assert r["success"] is True
        assert r["session_id"] == "sess-9"

    @pytest.mark.asyncio
    async def test_chat_forbidden_session(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None):
            sm.return_value.get_session.return_value = {"user_id": "other"}
            with pytest.raises(HTTPException):
                await chat_with_agent(_request("help", session_id="s1"), _user())

    @pytest.mark.asyncio
    async def test_chat_list_workflows_dispatch(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()) as ch, \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "LIST_WORKFLOWS", "entities": {}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba, \
             patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            sm.return_value.create_session.return_value = "sess-3"
            ba.return_value.detect_patterns.return_value = []
            r = await chat_with_agent(_request("list workflows"), _user())
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_chat_with_reference_resolution(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()) as ch, \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager") as cm, \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "RUN_WORKFLOW", "entities": {"workflow_ref": "that"}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba, \
             patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"name": "Resolved", "workflow_id": "wf-42", "id": "wf-42"}]):
            engine = MagicMock()
            engine.execute_workflow_definition = AsyncMock(return_value={"ok": True})
            sm.return_value.create_session.return_value = "sess-4"
            cm.return_value.resolve_reference = AsyncMock(return_value={
                "id": "wf-42", "name": "Resolved"
            })
            ba.return_value.detect_patterns.return_value = []
            with patch("core.atom_agent_endpoints.AutomationEngine", return_value=engine):
                r = await chat_with_agent(_request("run that workflow"), _user())
        assert r["success"] is True
        cm.return_value.resolve_reference.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_behavior_suggestions(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "UNKNOWN", "entities": {}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba:
            sm.return_value.create_session.return_value = "sess-5"
            ba.return_value.detect_patterns.return_value = [
                {"name": "n", "description": "d", "suggested_actions": ["w1"]}
            ]
            r = await chat_with_agent(_request("hi"), _user())
        assert r["response"]["actions"][0]["workflow_id"] == "w1"

    @pytest.mark.asyncio
    async def test_chat_episode_trigger(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "HELP", "entities": {}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba, \
             patch("core.atom_agent_endpoints.trigger_episode_creation") as te:
            sm.return_value.create_session.return_value = "sess-6"
            ba.return_value.detect_patterns.return_value = []
            r = await chat_with_agent(
                _request("help", agent_id="agent-1"), _user()
            )
        assert r["success"] is True
        te.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_episode_trigger_error(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.LLMService"), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "HELP", "entities": {}})), \
             patch("core.behavior_analyzer.get_behavior_analyzer") as ba, \
             patch("core.atom_agent_endpoints.trigger_episode_creation",
                   side_effect=Exception("episode down")):
            sm.return_value.create_session.return_value = "sess-7"
            ba.return_value.detect_patterns.return_value = []
            r = await chat_with_agent(_request("help", agent_id="agent-1"), _user())
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_chat_exception_generic(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager",
                   side_effect=Exception("boom")):
            r = await chat_with_agent(_request("hi"), _user())
        assert r == {"success": False, "error": "Internal server error"}

    @pytest.mark.asyncio
    async def test_chat_slash_command(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()) as ch, \
             patch("core.atom_agent_endpoints.get_chat_session_manager") as sm, \
             patch("core.atom_agent_endpoints.get_chat_context_manager"), \
             patch("core.board_command_router.parse_slash", return_value=("CREATE_TASK", {"title": "x"})) as ps, \
             patch("core.database.get_db_session") as gdb, \
             patch("core.board_command_router.BoardCommandRouter") as bcr:
            sm.return_value.create_session.return_value = "sess-8"
            reply = SimpleNamespace(ok=True, reply="done", task_id="t1")
            bcr.return_value.route.return_value = reply
            r = await chat_with_agent(_request("/task x"), _user())
        assert r["success"] is True
        assert r["response"]["intent"] == "CREATE_TASK"


class TestChatStreamAgent:
    def _env(self, *, agent=None, gov_check=None, providers=("p1", "m1"),
             history=None, stream_tokens=("a", "b")):
        from core.atom_agent_endpoints import ChatRequest as CR
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "medium"
        if providers is None:
            llm.get_optimal_provider.side_effect = Exception("no providers")
        else:
            llm.get_optimal_provider.return_value = providers

        async def gen(**kwargs):
            for t in stream_tokens:
                yield t

        llm.stream_completion = gen
        llm_service_cls = MagicMock(return_value=llm)

        ws = MagicMock()
        ws.broadcast = AsyncMock()
        ws.STREAMING_UPDATE = "streaming:update"
        ws.STREAMING_COMPLETE = "streaming:complete"
        ws.STREAMING_ERROR = "streaming:error"

        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {"ctx": 1}))
        governance = MagicMock()
        governance.record_outcome = AsyncMock()
        if gov_check is not None:
            governance.can_perform_action.return_value = gov_check

        db = MagicMock()
        gdb = MagicMock()
        gdb.__enter__.return_value = db

        ch = MagicMock()
        sess = MagicMock()
        sess.create_session.return_value = "stream-sess"

        patches = [
            patch("core.agent_context_resolver.AgentContextResolver",
                  return_value=resolver),
            patch("core.agent_governance_service.AgentGovernanceService",
                  return_value=governance),
            patch("core.database.get_db_session", return_value=gdb),
            patch("core.llm_service.LLMService", llm_service_cls),
            patch("core.websockets.manager", ws),
            patch("core.atom_agent_endpoints.get_chat_history_manager",
                  return_value=ch),
            patch("core.atom_agent_endpoints.get_chat_session_manager",
                  return_value=sess),
        ]
        return patches, llm, ws, ch, sess

    @pytest.mark.asyncio
    async def test_stream_governance_blocked(self):
        import contextlib
        agent = SimpleNamespace(id="a1", name="Agent")
        patches, llm, ws, ch, sess = self._env(
            agent=agent, gov_check={"allowed": False, "reason": "not permitted"}
        )
        with contextlib.ExitStack() as es:
            for ptch in patches:
                es.enter_context(ptch)
            r = await chat_stream_agent(_request("hello"), _user())
        assert r["success"] is False
        assert "not permitted to stream chat" in r["error"]

    @pytest.mark.asyncio
    async def test_stream_no_providers_configured(self):
        patches, llm, ws, ch, sess = self._env(providers=None)
        from core.llm.byok_handler import NoProvidersConfiguredError
        llm.get_optimal_provider.side_effect = NoProvidersConfiguredError(
            message="No LLM providers configured.", recovery_url="/settings/ai"
        )
        with contextlib.ExitStack() as es:
            for ptch in patches:
                es.enter_context(ptch)
            r = await chat_stream_agent(_request("hello"), _user())
        assert r["success"] is False
        assert r["error_code"] == "no_llm_provider"

    @pytest.mark.asyncio
    async def test_stream_provider_generic_error(self):
        patches, llm, ws, ch, sess = self._env(providers=None)
        llm.get_optimal_provider.side_effect = ValueError("other error")
        with contextlib.ExitStack() as es:
            for ptch in patches:
                es.enter_context(ptch)
            r = await chat_stream_agent(_request("hello"), _user())
        assert r["success"] is False
        assert r["error_code"] == "llm_provider_error"

    @pytest.mark.asyncio
    async def test_stream_success(self):
        import contextlib
        patches, llm, ws, ch, sess = self._env()
        with contextlib.ExitStack() as es:
            for ptch in patches:
                es.enter_context(ptch)
            r = await chat_stream_agent(_request("hello"), _user())
        assert r["success"] is True
        assert r["streamed"] is True
        ws.broadcast.assert_awaited()
        ch.add_message.assert_any_call("stream-sess", "user", "hello")
        ch.add_message.assert_any_call("stream-sess", "assistant", "ab")

    @pytest.mark.asyncio
    async def test_stream_with_history_and_agent(self):
        import contextlib
        agent = SimpleNamespace(id="a1", name="Agent")
        patches, llm, ws, ch, sess = self._env(
            agent=agent, gov_check={"allowed": True, "reason": ""}
        )
        with contextlib.ExitStack() as es:
            for ptch in patches:
                es.enter_context(ptch)
            r = await chat_stream_agent(
                _request("hello", session_id="s1",
                         conversation_history=[
                             ChatMessage(role="user", content="prev")
                         ]),
                _user(),
            )
        assert r["success"] is True
        assert r["agent_id"] == "a1"

    @pytest.mark.asyncio
    async def test_stream_error_marks_failed(self):
        agent = SimpleNamespace(id="a1", name="Agent")
        patches, llm, ws, ch, sess = self._env(
            agent=agent, gov_check={"allowed": True, "reason": ""},
            stream_tokens=(),
        )

        async def boom():
            raise RuntimeError("stream broke")
            yield  # pragma: no cover

        llm.stream_completion = boom
        with contextlib.ExitStack() as es:
            for ptch in patches:
                es.enter_context(ptch)
            r = await chat_stream_agent(_request("hello"), _user())
        assert r == {"success": False, "error": "Internal server error"}

    @pytest.mark.asyncio
    async def test_stream_governance_disabled(self):
        import contextlib
        patches, llm, ws, ch, sess = self._env()
        with contextlib.ExitStack() as es:
            for ptch in patches:
                es.enter_context(ptch)
            es.enter_context(patch.dict(os.environ, {"STREAMING_GOVERNANCE_ENABLED": "false"}))
            r = await chat_stream_agent(_request("hello"), _user())
        assert r["success"] is True


class TestRetrievalEndpoints:
    @pytest.mark.asyncio
    async def test_retrieve_hybrid_success(self):
        svc = MagicMock()
        svc.retrieve_semantic_hybrid = AsyncMock(return_value=[("e1", 0.9, "rerank")])
        with patch("core.atom_agent_endpoints.HybridRetrievalService", return_value=svc):
            r = await retrieve_hybrid("a1", "q", db=MagicMock())
        assert r["success"] is True
        assert r["count"] == 1

    @pytest.mark.asyncio
    async def test_retrieve_hybrid_exception(self):
        with patch("core.atom_agent_endpoints.HybridRetrievalService",
                   side_effect=Exception("boom")):
            r = await retrieve_hybrid("a1", "q", db=MagicMock())
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_retrieve_baseline_success(self):
        svc = MagicMock()
        svc.retrieve_semantic_baseline = AsyncMock(return_value=[("e1", 0.8)])
        with patch("core.atom_agent_endpoints.HybridRetrievalService", return_value=svc):
            r = await retrieve_baseline("a1", "q", db=MagicMock())
        assert r["success"] is True
        assert r["method"] == "fastembed_baseline"

    @pytest.mark.asyncio
    async def test_retrieve_baseline_exception(self):
        with patch("core.atom_agent_endpoints.HybridRetrievalService",
                   side_effect=Exception("boom")):
            r = await retrieve_baseline("a1", "q", db=MagicMock())
        assert r["success"] is False
