"""Coverage wave 22 — core/atom_agent_endpoints.py handlers + helpers (TDD).

All LLM-heavy paths (chat/stream, /chat, retrieve-*) are exercised only via
mocked services — zero LLM calls, zero OpenCode Go spend. Covers the pure
classifier, workflow handlers, calendar/email/task/finance/system handlers,
save_chat_interaction and the execute-generated route.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.atom_agent_endpoints import (
    chat_with_agent,
    classify_intent_with_llm,
    create_new_session,
    get_session_history,
    ChatRequest,
    _workflow_id_of,
    _workflow_matches_ref,
    execute_generated_workflow,
    fallback_intent_classification,
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
    save_chat_interaction,
)


def req(message="hello", user_id="u-1", **kw):
    return ChatRequest(message=message, user_id=user_id, **kw)


# ---------------------------------------------------------------------------
# fallback_intent_classification — pure classifier, all branches
# ---------------------------------------------------------------------------


class TestFallbackIntentClassification:
    @pytest.mark.parametrize(
        "message,expected",
        [
            ("schedule the daily report workflow to run every weekday", "SCHEDULE_WORKFLOW"),
            ("create a new workflow for invoicing", "CREATE_WORKFLOW"),
            ("list my workflows", "LIST_WORKFLOWS"),
            ("run workflow for lead enrichment", "RUN_WORKFLOW"),
            ("show me the execution history", "GET_HISTORY"),
            ("find calendar conflicts this week", "RESOLVE_CONFLICTS"),
            ("schedule a meeting tomorrow", "CREATE_EVENT"),
            ("list events next week", "LIST_EVENTS"),
            ("send an email to the team", "SEND_EMAIL"),
            ("search emails for the invoice", "SEARCH_EMAILS"),
            ("follow up on pending emails", "FOLLOW_UP_EMAILS"),
            ("create task for the design review", "CREATE_TASK"),
            ("list my tasks", "LIST_TASKS"),
            ("show recent transactions", "GET_TRANSACTIONS"),
            ("what is my balance", "CHECK_BALANCE"),
            ("invoice status please", "INVOICE_STATUS"),
            ("set a goal to close the deal", "SET_GOAL"),
            ("goal progress report", "GOAL_STATUS"),
            ("system health check", "GET_SYSTEM_STATUS"),
            ("wellness check", "WELLNESS_CHECK"),
            ("any new leads this week", "CRM_QUERY"),
            ("search for the quarterly doc", "SEARCH_PLATFORM"),
            ("what projects are active", "KNOWLEDGE_QUERY"),
            ("random gibberish", "UNKNOWN"),
        ],
    )
    def test_branches(self, message, expected):
        result = fallback_intent_classification(message)
        assert result["intent"] == expected

    def test_schedule_extracts_workflow_ref_with_time(self):
        result = fallback_intent_classification("schedule the report workflow to run daily at 9am")
        assert result["intent"] == "SCHEDULE_WORKFLOW"
        entities = result["entities"]
        assert "report" in entities.get("workflow_ref", "")
        assert entities.get("time_expression")

    def test_wellness_check_before_crm(self):
        # "stress" hits WELLNESS_CHECK before the CRM keyword list
        assert fallback_intent_classification("I feel stress about deals")["intent"] == "WELLNESS_CHECK"

    def test_send_email_extracts_subject(self):
        result = fallback_intent_classification("send email to the client")
        assert result["entities"]["subject"] == "New Email"

    def test_search_platform_extracts_query(self):
        result = fallback_intent_classification("search for budget docs")
        assert result["entities"]["query"] == "for budget docs"


# ---------------------------------------------------------------------------
# workflow helper functions
# ---------------------------------------------------------------------------


class TestWorkflowHelpers:
    def test_workflow_id_of(self):
        assert _workflow_id_of({"workflow_id": "w1"}) == "w1"
        assert _workflow_id_of({"id": "w2"}) == "w2"
        assert _workflow_id_of({"workflow_id": "w3", "id": "w3b"}) == "w3"
        assert _workflow_id_of({}) == ""

    def test_workflow_matches_ref(self):
        assert _workflow_matches_ref({"name": "Daily Report"}, "daily")
        assert _workflow_matches_ref({"workflow_id": "rep-123"}, "rep-123")
        assert _workflow_matches_ref({"id": "wf-9"}, "wf-9")
        assert not _workflow_matches_ref({"name": "Other"}, "daily")
        assert not _workflow_matches_ref({"id": "x"}, "")
        assert not _workflow_matches_ref({}, "anything")


# ---------------------------------------------------------------------------
# simple stateless handlers
# ---------------------------------------------------------------------------


class TestSimpleHandlers:
    async def test_help_request(self):
        result = handle_help_request()
        assert result["success"] is True
        assert "Universal ATOM Assistant" in result["response"]["message"]

    async def test_get_status(self):
        result = await handle_get_status(req(), {})
        assert result["success"] is True

    async def test_create_event(self):
        result = await handle_create_event(req(), {"summary": "Standup", "start_time": "tomorrow 9am"})
        assert result["success"] is True
        assert "Standup" in result["response"]["message"]

    async def test_send_email(self):
        result = await handle_send_email(req(), {"recipient": "a@b.c", "subject": "Hi"})
        assert result["success"] is True
        assert "a@b.c" in result["response"]["message"]

    async def test_resolve_conflicts(self):
        result = await handle_resolve_conflicts(req(), {})
        assert result["success"] is True

    async def test_get_history(self):
        assert (await handle_get_history(req(), {}))["success"] is False
        result = await handle_get_history(req(), {"workflow_ref": "daily"})
        assert result["success"] is True

    async def test_cancel_schedule(self):
        scheduler = MagicMock()
        scheduler.remove_job = MagicMock(return_value=True)
        with patch("core.atom_agent_endpoints.workflow_scheduler", scheduler):
            result = await handle_cancel_schedule(req(), {"schedule_id": "job-1"})
        assert result["success"] is True
        scheduler.remove_job.assert_called_once_with("job-1")

    async def test_cancel_schedule_missing_job(self):
        scheduler = MagicMock()
        scheduler.remove_job = MagicMock(return_value=False)
        with patch("core.atom_agent_endpoints.workflow_scheduler", scheduler):
            result = await handle_cancel_schedule(req(), {"schedule_id": "job-x"})
        assert result["success"] is False

    async def test_cancel_schedule_by_workflow_ref(self):
        result = await handle_cancel_schedule(req(), {"workflow_ref": "daily"})
        assert result["success"] is True
        result2 = await handle_cancel_schedule(req(), {})
        assert result2["success"] is False


# ---------------------------------------------------------------------------
# workflow creation/run handlers (mocked orchestrator / automation engine)
# ---------------------------------------------------------------------------


class TestWorkflowHandlers:
    async def test_create_workflow_none(self):
        orchestrator = MagicMock()
        orchestrator.generate_dynamic_workflow = AsyncMock(return_value=None)
        with patch("core.atom_agent_endpoints.get_orchestrator", return_value=orchestrator):
            result = await handle_create_workflow(req("make a workflow"), {"description": "d"})
        assert result["success"] is False

    async def test_create_workflow_success(self):
        orchestrator = MagicMock()
        orchestrator.generate_dynamic_workflow = AsyncMock(return_value={"id": "wf-1", "name": "Gen"})
        with patch("core.atom_agent_endpoints.get_orchestrator", return_value=orchestrator), \
             patch("core.atom_agent_endpoints.save_workflows", return_value=True):
            result = await handle_create_workflow(req("make a workflow"), {"description": "d"})
        assert result["success"] is True

    async def test_list_workflows(self):
        workflows = [
            {"id": "w1", "name": "Daily Report"},
            {"id": "w2", "name": "Lead Enrichment"},
        ]
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows):
            result = await handle_list_workflows(req())
        assert result["success"] is True
        assert "Found 2 workflows" in result["response"]["message"]
        assert len(result["response"]["actions"]) == 2

    async def test_list_workflows_empty(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            result = await handle_list_workflows(req())
        assert result["success"] is True
        assert "No workflows" in result["response"]["message"]

    async def test_list_workflows_exception(self):
        with patch("core.atom_agent_endpoints.load_workflows", side_effect=RuntimeError("disk")):
            result = await handle_list_workflows(req())
        assert result["success"] is False

    async def test_run_workflow_no_ref(self):
        result = await handle_run_workflow(req(), {}, None)
        assert result["success"] is False

    async def test_run_workflow_not_found(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            result = await handle_run_workflow(req(), {"workflow_ref": "ghost"}, None)
        assert result["success"] is False
        assert "not found" in result["response"]["message"]

    async def test_run_workflow_gated(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        refusal = {"success": False, "response": {"message": "Permission denied"}}
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=refusal)):
            result = await handle_run_workflow(req(), {"workflow_ref": "Daily"}, None)
        assert result["success"] is False

    async def test_run_workflow_engine_missing(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=None)), \
             patch("core.atom_agent_endpoints.AutomationEngine", None):
            result = await handle_run_workflow(req(), {"workflow_ref": "Daily"}, None)
        assert result["success"] is False
        assert "not available" in result["response"]["message"]

    async def test_run_workflow_success(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        engine_cls = MagicMock()
        engine_cls.return_value.execute_workflow_definition = AsyncMock(return_value={"ok": True})
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=None)), \
             patch("core.atom_agent_endpoints.AutomationEngine", engine_cls):
            result = await handle_run_workflow(req(), {"workflow_ref": "Daily"}, None)
        assert result["success"] is True
        assert "Daily" in result["response"]["message"]

    async def test_run_workflow_exception(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        engine_cls = MagicMock()
        engine_cls.return_value.execute_workflow_definition = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=None)), \
             patch("core.atom_agent_endpoints.AutomationEngine", engine_cls):
            result = await handle_run_workflow(req(), {"workflow_ref": "Daily"}, None)
        assert result["success"] is False
        assert "boom" in result["response"]["message"]

    async def test_schedule_workflow_missing_parts(self):
        result = await handle_schedule_workflow(req(), {}, None)
        assert result["success"] is False
        result2 = await handle_schedule_workflow(req(), {"workflow_ref": "x"}, None)
        assert result2["success"] is False

    async def test_schedule_workflow_not_found(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            result = await handle_schedule_workflow(req(), {"workflow_ref": "ghost", "time_expression": "daily at 9am"}, None)
        assert result["success"] is False

    async def test_schedule_workflow_unparseable(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.time_expression_parser.parse_time_expression", new=AsyncMock(return_value=None)):
            result = await handle_schedule_workflow(req(), {"workflow_ref": "Daily", "time_expression": "whenever"}, None)
        assert result["success"] is False

    async def test_schedule_workflow_gated(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        refusal = {"success": False, "response": {"message": "denied"}}
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.time_expression_parser.parse_time_expression",
                   new=AsyncMock(return_value={"schedule_type": "cron", "cron_expression": "0 9 * * *", "human_readable": "daily at 9am"})), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=refusal)):
            result = await handle_schedule_workflow(req(), {"workflow_ref": "Daily", "time_expression": "daily at 9am"}, None)
        assert result["success"] is False

    async def test_schedule_workflow_cron(self):
        workflows = [{"workflow_id": "w1", "name": "Daily", "steps": []}]
        scheduler = MagicMock()
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.time_expression_parser.parse_time_expression",
                   new=AsyncMock(return_value={"schedule_type": "cron", "cron_expression": "0 9 * * *", "human_readable": "daily at 9am"})), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=None)), \
             patch("core.atom_agent_endpoints.workflow_scheduler", scheduler):
            result = await handle_schedule_workflow(req(), {"workflow_ref": "Daily", "time_expression": "daily at 9am"}, None)
        assert result["success"] is True
        assert scheduler.schedule_workflow_cron.called

    async def test_schedule_workflow_interval_and_date(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        scheduler = MagicMock()
        for info in [
            {"schedule_type": "interval", "interval_minutes": 30, "human_readable": "every 30 min"},
            {"schedule_type": "date", "run_date": "2026-09-01", "human_readable": "on Sep 1"},
        ]:
            with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
                 patch("core.time_expression_parser.parse_time_expression", new=AsyncMock(return_value=info)), \
                 patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=None)), \
                 patch("core.atom_agent_endpoints.workflow_scheduler", scheduler):
                result = await handle_schedule_workflow(req(), {"workflow_ref": "Daily", "time_expression": "x"}, None)
            assert result["success"] is True
        assert scheduler.schedule_workflow_interval.called
        assert scheduler.schedule_workflow_once.called

    async def test_schedule_workflow_exception(self):
        workflows = [{"id": "w1", "name": "Daily", "steps": []}]
        scheduler = MagicMock()
        scheduler.schedule_workflow_cron.side_effect = RuntimeError("sched down")
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.time_expression_parser.parse_time_expression",
                   new=AsyncMock(return_value={"schedule_type": "cron", "cron_expression": "0 9 * * *", "human_readable": "daily"})), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=None)), \
             patch("core.atom_agent_endpoints.workflow_scheduler", scheduler):
            result = await handle_schedule_workflow(req(), {"workflow_ref": "Daily", "time_expression": "daily"}, None)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# CRM / calendar / email / knowledge handlers
# ---------------------------------------------------------------------------


class TestCrmAndIntegrationHandlers:
    async def test_crm_success(self):
        assistant_cls = MagicMock()
        assistant_cls.return_value.answer_sales_query = AsyncMock(return_value="Here are your leads")
        db = MagicMock()
        with patch("sales.assistant.SalesAssistant", assistant_cls), \
             patch("core.database.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            result = await handle_crm_intent(req("lead status"), {"workspace_id": "ws-1"})
        assert result["success"] is True
        assert "leads" in result["response"]["message"].lower()

    async def test_crm_exception(self):
        assistant_cls = MagicMock()
        assistant_cls.return_value.answer_sales_query = AsyncMock(side_effect=RuntimeError("crm down"))
        db = MagicMock()
        with patch("sales.assistant.SalesAssistant", assistant_cls), \
             patch("core.database.get_db_session") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            result = await handle_crm_intent(req("lead status"), {})
        assert result["success"] is False

    async def test_list_events_empty(self):
        with patch("integrations.google_calendar_service.GoogleCalendarService.get_events", new=AsyncMock(return_value=[])):
            result = await handle_list_events(req(), {})
        assert result["success"] is True
        assert "No upcoming" in result["response"]["message"]

    async def test_list_events_with_events(self):
        events = [{"summary": "Standup", "start": {"dateTime": "2026-08-11T09:00:00"}}]
        with patch("integrations.google_calendar_service.GoogleCalendarService.get_events", new=AsyncMock(return_value=events)):
            result = await handle_list_events(req(), {})
        assert result["success"] is True
        assert "Standup" in result["response"]["message"]

    async def test_list_events_exception(self):
        with patch("integrations.google_calendar_service.GoogleCalendarService.get_events",
                   new=AsyncMock(side_effect=RuntimeError("cal down"))):
            result = await handle_list_events(req(), {})
        assert result["success"] is False

    async def test_search_emails_empty(self):
        with patch("integrations.gmail_service.GmailService.search_messages", return_value=[]):
            result = await handle_search_emails(req(), {"query": "invoice"})
        assert result["success"] is True
        assert "No emails" in result["response"]["message"]

    async def test_search_emails_with_results(self):
        with patch("integrations.gmail_service.GmailService.search_messages", return_value=[{"id": "1"}, {"id": "2"}]):
            result = await handle_search_emails(req(), {"query": "invoice"})
        assert result["success"] is True
        assert "Found 2 emails" in result["response"]["message"]

    async def test_search_emails_exception(self):
        with patch("integrations.gmail_service.GmailService.search_messages", side_effect=RuntimeError("gmail down")):
            result = await handle_search_emails(req(), {"query": "invoice"})
        assert result["success"] is False

    async def test_knowledge_query_success(self):
        manager = MagicMock()
        manager.answer_query = AsyncMock(return_value={"answer": "Project Alpha is on track"})
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager", return_value=manager):
            result = await handle_knowledge_query(req("what is project alpha"), {"query": "project alpha"})
        assert result["success"] is True
        assert "Project Alpha" in result["response"]["message"]

    async def test_knowledge_query_exception(self):
        manager = MagicMock()
        manager.answer_query = AsyncMock(side_effect=RuntimeError("graph down"))
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager", return_value=manager):
            result = await handle_knowledge_query(req("q"), {"query": "q"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# task / finance / follow-up / wellness / insights / goals / stakeholders
# ---------------------------------------------------------------------------


class TestTaskFinanceHandlers:
    async def test_create_task_success(self):
        with patch("core.atom_agent_endpoints.create_task", new=AsyncMock(return_value={"id": "t1"})):
            result = await handle_task_intent("CREATE_TASK", {"title": "Review design"}, req())
        assert result["success"] is True
        assert "Review design" in result["response"]["message"]

    async def test_create_task_asana_platform(self):
        with patch("core.atom_agent_endpoints.create_task", new=AsyncMock(return_value={"id": "t1"})):
            result = await handle_task_intent("CREATE_TASK", {"title": "Add to asana board"}, req())
        assert result["response"]["message"].endswith("on asana.")

    async def test_create_task_exception(self):
        with patch("core.atom_agent_endpoints.create_task", new=AsyncMock(side_effect=RuntimeError("task down"))):
            result = await handle_task_intent("CREATE_TASK", {"title": "x"}, req())
        assert result["success"] is False

    async def test_list_tasks(self):
        with patch("core.atom_agent_endpoints.get_tasks", new=AsyncMock(return_value={"tasks": [{"id": "a"}, {"id": "b"}]})):
            result = await handle_task_intent("LIST_TASKS", {}, req())
        assert result["success"] is True
        assert "Found 2 tasks" in result["response"]["message"]

    async def test_list_tasks_exception(self):
        with patch("core.atom_agent_endpoints.get_tasks", new=AsyncMock(side_effect=RuntimeError("no"))):
            result = await handle_task_intent("LIST_TASKS", {}, req())
        assert result["success"] is False

    async def test_task_unknown_intent(self):
        result = await handle_task_intent("BOGUS", {}, req())
        assert result["success"] is False

    async def test_finance_transactions(self):
        result = await handle_finance_intent("GET_TRANSACTIONS", {}, req())
        assert result["success"] is True
        assert len(result["response"]["data"]["transactions"]) == 2

    async def test_finance_balance(self):
        result = await handle_finance_intent("CHECK_BALANCE", {}, req())
        assert result["success"] is True
        assert result["response"]["data"]["balance"] == 12450.00

    async def test_finance_invoice_status(self):
        with patch("core.atom_agent_endpoints.list_quickbooks_items", new=AsyncMock(return_value={"items": [{"id": 1}]})):
            result = await handle_finance_intent("INVOICE_STATUS", {}, req())
        assert result["success"] is True
        assert "Found 1 active invoices" in result["response"]["message"]

    async def test_finance_invoice_exception(self):
        with patch("core.atom_agent_endpoints.list_quickbooks_items", new=AsyncMock(side_effect=RuntimeError("qb down"))):
            result = await handle_finance_intent("INVOICE_STATUS", {}, req())
        assert result["success"] is False

    async def test_finance_unknown_intent(self):
        result = await handle_finance_intent("BOGUS", {}, req())
        assert result["success"] is False


class TestTemplateAndInsightHandlers:
    async def test_follow_up_success(self):
        tm = MagicMock()
        tm.get_template.return_value = {"id": "email_followup"}
        with patch("core.workflow_template_system.template_manager", tm, create=True):
            result = await handle_follow_up_emails(req(), {})
        assert result["success"] is True
        assert "follow up" in result["response"]["message"].lower()

    async def test_follow_up_no_template(self):
        tm = MagicMock()
        tm.get_template.return_value = None
        with patch("core.workflow_template_system.template_manager", tm, create=True):
            result = await handle_follow_up_emails(req(), {})
        assert result["success"] is False

    async def test_follow_up_exception(self):
        with patch("core.workflow_template_system.template_manager",
                         MagicMock(get_template=MagicMock(side_effect=RuntimeError("x"))), create=True):
            result = await handle_follow_up_emails(req(), {})
        assert result["success"] is False

    async def test_wellness_check(self):
        with patch("core.workflow_template_system.template_manager", MagicMock(), create=True):
            result = await handle_wellness_check(req(), {})
        assert result["success"] is True
        assert "Burnout" in result["response"]["message"]

    async def test_wellness_exception(self):
        with patch("core.workflow_template_system.template_manager",
                         MagicMock(get_template=MagicMock(side_effect=RuntimeError("x"))), create=True):
            result = await handle_wellness_check(req(), {})
        assert result["success"] is False

    async def test_set_goal(self):
        with patch("core.workflow_template_system.template_manager", MagicMock(), create=True):
            result = await handle_set_goal(req("close the deal"), {"goal_text": "close the deal"})
        assert result["success"] is True
        assert "close the deal" in result["response"]["message"]

    async def test_set_goal_exception(self):
        with patch("core.workflow_template_system.template_manager", None, create=True), \
             patch("core.workflow_template_system.WorkflowTemplateManager",
                   side_effect=RuntimeError("ctor boom")):
            result = await handle_set_goal(req("goal"), {})
        assert result["success"] is False

    async def test_goal_status(self):
        result = await handle_goal_status(req(), {})
        assert result["success"] is True
        assert "active goal" in result["response"]["message"]

    async def test_automation_insights_with_drift(self):
        insight_manager = MagicMock()
        insight_manager.generate_all_insights.return_value = {
            "drift_insights": [
                {"workflow_id": "w1", "drift_score": 0.9},
                {"workflow_id": "w2", "drift_score": 0.2},
            ],
            "summary": {},
        }
        behavior = MagicMock()
        behavior.detect_patterns.return_value = [
            {"description": "Batch your emails", "name": "Batch emails", "suggested_actions": ["wf-batch"]}
        ]
        with patch("core.automation_insight_manager.get_insight_manager", return_value=insight_manager), \
             patch("core.behavior_analyzer.get_behavior_analyzer", return_value=behavior):
            result = await handle_automation_insights(req())
        assert result["success"] is True
        assert "Drift Detected" in result["response"]["message"]
        assert len(result["response"]["actions"]) >= 2

    async def test_automation_insights_clean(self):
        insight_manager = MagicMock()
        insight_manager.generate_all_insights.return_value = {
            "drift_insights": [], "summary": {}}
        behavior = MagicMock()
        behavior.detect_patterns.return_value = []
        with patch("core.automation_insight_manager.get_insight_manager", return_value=insight_manager), \
             patch("core.behavior_analyzer.get_behavior_analyzer", return_value=behavior):
            result = await handle_automation_insights(req())
        assert result["success"] is True
        assert "expected parameters" in result["response"]["message"]

    async def test_automation_insights_exception(self):
        with patch("core.automation_insight_manager.get_insight_manager",
                   side_effect=RuntimeError("insights down")):
            result = await handle_automation_insights(req())
        assert result["success"] is False

    async def test_silent_stakeholders_none(self):
        engine = MagicMock()
        engine.identify_silent_stakeholders = AsyncMock(return_value=[])
        with patch("core.stakeholder_engine.get_stakeholder_engine", return_value=engine):
            result = await handle_silent_stakeholders(req())
        assert result["success"] is True
        assert "actively engaged" in result["response"]["message"]

    async def test_silent_stakeholders_with_data(self):
        engine = MagicMock()
        engine.identify_silent_stakeholders = AsyncMock(return_value=[
            {"name": "Alice", "email": "a@b.c", "days_since": 12, "suggested_outreach": "Hi Alice"}
        ])
        with patch("core.stakeholder_engine.get_stakeholder_engine", return_value=engine):
            result = await handle_silent_stakeholders(req())
        assert result["success"] is True
        assert "Alice" in result["response"]["message"]
        assert result["response"]["actions"][0]["recipient"] == "a@b.c"

    async def test_silent_stakeholders_exception(self):
        engine = MagicMock()
        engine.identify_silent_stakeholders = AsyncMock(side_effect=RuntimeError("x"))
        with patch("core.stakeholder_engine.get_stakeholder_engine", return_value=engine):
            result = await handle_silent_stakeholders(req())
        assert result["success"] is False


# ---------------------------------------------------------------------------
# system status / platform search
# ---------------------------------------------------------------------------


class TestSystemSearchHandlers:
    async def test_system_status(self):
        status = MagicMock()
        status.get_overall_status.return_value = "healthy"
        status.get_system_info.return_value = {"platform": {"system": "Darwin"}}
        status.get_resource_usage.return_value = {"cpu": {"percent": 10.5}, "memory": {"percent": 42.0}}
        status.get_service_status.return_value = {"api": {"status": "healthy"}, "db": {"status": "operational"}}
        with patch("core.atom_agent_endpoints.SystemStatus", status):
            result = await handle_system_status(req())
        assert result["success"] is True
        assert "2/2 healthy" in result["response"]["message"]

    async def test_system_status_exception(self):
        status = MagicMock()
        status.get_overall_status.side_effect = RuntimeError("no status")
        with patch("core.atom_agent_endpoints.SystemStatus", status):
            result = await handle_system_status(req())
        assert result["success"] is False

    async def test_platform_search_with_results(self):
        result_item = SimpleNamespace(
            metadata={"type": "document"}, text="A" * 50,
            dict=lambda: {"text": "A" * 50})
        response = SimpleNamespace(success=True, results=[result_item], total_count=1)
        with patch("core.atom_agent_endpoints.unified_hybrid_search", new=AsyncMock(return_value=response)):
            result = await handle_platform_search(req("find docs"), {"query": "docs"})
        assert result["success"] is True
        assert "Found 1 results" in result["response"]["message"]

    async def test_platform_search_no_results(self):
        response = SimpleNamespace(success=True, results=[], total_count=0)
        with patch("core.atom_agent_endpoints.unified_hybrid_search", new=AsyncMock(return_value=response)):
            result = await handle_platform_search(req("find docs"), {"query": "docs"})
        assert result["success"] is True
        assert "No results" in result["response"]["message"]

    async def test_platform_search_exception(self):
        with patch("core.atom_agent_endpoints.unified_hybrid_search", new=AsyncMock(side_effect=RuntimeError("search down"))):
            result = await handle_platform_search(req("find docs"), {"query": "docs"})
        assert result["success"] is False


# ---------------------------------------------------------------------------
# save_chat_interaction + sessions route + execute-generated route
# ---------------------------------------------------------------------------


class TestSaveChatInteraction:
    def test_full_metadata_path(self):
        chat = MagicMock()
        sess = MagicMock()
        save_chat_interaction(
            session_id="s1", user_id="u1", user_message="hi", assistant_message="yo",
            intent="RUN_WORKFLOW", entities={"x": 1},
            result_data={"response": {"workflow_id": "w1", "workflow_name": "Daily",
                                      "task_id": "t1", "schedule_id": "j1"}},
            chat_history_mgr=chat, session_mgr=sess,
        )
        assert chat.save_message.call_count == 2
        user_meta = chat.save_message.call_args_list[0].kwargs["metadata"]
        assert user_meta["intent"] == "RUN_WORKFLOW"
        asst_meta = chat.save_message.call_args_list[1].kwargs["metadata"]
        assert asst_meta["workflow_id"] == "w1"
        assert asst_meta["task_id"] == "t1"
        assert asst_meta["schedule_id"] == "j1"
        sess.update_session_activity.assert_called_once_with("s1")

    def test_default_managers_and_exception_tolerance(self):
        with patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=MagicMock()):
            save_chat_interaction("s1", "u1", "m", "r", chat_history_mgr=None, session_mgr=None)

        chat = MagicMock()
        chat.save_message.side_effect = RuntimeError("db down")
        save_chat_interaction("s1", "u1", "m", "r", chat_history_mgr=chat, session_mgr=MagicMock())


class TestSessionsRoute:
    async def test_list_sessions(self):
        mgr = MagicMock()
        mgr.list_user_sessions.return_value = [
            {"session_id": "sess-1", "metadata": {"title": "My Session", "last_message": "preview"},
             "last_active": "2026-08-10T00:00:00Z"},
        ]
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=mgr):
            result = await list_sessions(user, limit=10)
        assert result["success"] is True
        assert result["sessions"][0]["title"] == "My Session"
        assert result["sessions"][0]["preview"] == "preview"

    async def test_list_sessions_exception(self):
        mgr = MagicMock()
        mgr.list_user_sessions.side_effect = RuntimeError("boom")
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=mgr):
            result = await list_sessions(user, limit=10)
        assert result["success"] is False


class TestExecuteGeneratedWorkflow:
    async def test_workflow_not_found(self):
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[]):
            result = await execute_generated_workflow(
                SimpleNamespace(workflow_id="missing", input_data={}),
                SimpleNamespace(id="u1"),
            )
        assert result["success"] is False
        assert result["error"] == "Workflow not found"

    async def test_workflow_found_and_executed(self):
        workflows = [{"id": "w1", "name": "Gen", "steps": []}]
        engine_cls = MagicMock()
        engine_cls.return_value.execute_workflow_definition = AsyncMock(return_value={"ok": True})
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()), \
             patch("core.atom_agent_endpoints.AutomationEngine", engine_cls):
            result = await execute_generated_workflow(
                SimpleNamespace(workflow_id="w1", input_data={}),
                SimpleNamespace(id="u1"),
            )
        assert result["success"] is True
        assert result["status"] == "completed"

    async def test_workflow_id_variant_match(self):
        workflows = [{"workflow_id": "w2", "name": "Gen2", "steps": []}]
        engine_cls = MagicMock()
        engine_cls.return_value.execute_workflow_definition = AsyncMock(return_value={"ok": True})
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()), \
             patch("core.atom_agent_endpoints.AutomationEngine", engine_cls):
            result = await execute_generated_workflow(
                SimpleNamespace(workflow_id="w2", input_data={}),
                SimpleNamespace(id="u1"),
            )
        assert result["success"] is True

    async def test_engine_missing(self):
        workflows = [{"id": "w1", "steps": []}]
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()), \
             patch("core.atom_agent_endpoints.AutomationEngine", None):
            result = await execute_generated_workflow(
                SimpleNamespace(workflow_id="w1", input_data={}),
                SimpleNamespace(id="u1"),
            )
        assert result["success"] is False
        assert "not available" in result["error"]

    async def test_execution_exception_internal_error(self):
        workflows = [{"id": "w1", "steps": []}]
        engine_cls = MagicMock()
        engine_cls.return_value.execute_workflow_definition = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.atom_agent_endpoints.load_workflows", return_value=workflows), \
             patch("core.atom_agent_endpoints.require_workflow_executor", new=AsyncMock()), \
             patch("core.atom_agent_endpoints.AutomationEngine", engine_cls):
            result = await execute_generated_workflow(
                SimpleNamespace(workflow_id="w1", input_data={}),
                SimpleNamespace(id="u1"),
            )
        assert result["success"] is False
        assert result["error"] == "Internal server error"


# ---------------------------------------------------------------------------
# wave-22b — session routes + chat route (classifier mocked — zero LLM spend)
# ---------------------------------------------------------------------------


class TestSessionRoutes:
    async def test_create_session_success(self):
        mgr = MagicMock()
        mgr.create_session.return_value = "sess-new"
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=mgr):
            result = await create_new_session(user)
        assert result["success"] is True
        assert result["session_id"] == "sess-new"

    async def test_create_session_exception(self):
        mgr = MagicMock()
        mgr.create_session.side_effect = RuntimeError("boom")
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=mgr):
            result = await create_new_session(user)
        assert result["success"] is False

    async def test_get_history_success(self):
        sess_mgr = MagicMock()
        sess_mgr.get_session.return_value = {"session_id": "s1", "user_id": "u1", "created_at": "now"}
        chat = MagicMock()
        chat.get_session_history.return_value = [
            {"id": "m1", "role": "user", "text": "hi", "created_at": "t1", "metadata": '{"intent": "HELP"}'},
            {"id": "m2", "role": "assistant", "text": "yo", "created_at": "t2", "metadata": {"intent": "HELP"}},
        ]
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=sess_mgr), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=chat):
            result = await get_session_history("s1", user)
        assert result["success"] is True
        assert result["count"] == 2
        assert result["messages"][0]["metadata"]["intent"] == "HELP"

    async def test_get_history_not_found(self):
        sess_mgr = MagicMock()
        sess_mgr.get_session.return_value = None
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=sess_mgr):
            result = await get_session_history("ghost", user)
        assert result["success"] is False
        assert result["error"] == "Session not found"

    async def test_get_history_forbidden(self):
        sess_mgr = MagicMock()
        sess_mgr.get_session.return_value = {"session_id": "s1", "user_id": "other"}
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=sess_mgr):
            with pytest.raises(Exception) as exc_info:
                await get_session_history("s1", user)
        assert exc_info.value.status_code == 403

    async def test_get_history_bad_metadata_json(self):
        sess_mgr = MagicMock()
        sess_mgr.get_session.return_value = {"session_id": "s1", "user_id": "u1"}
        chat = MagicMock()
        chat.get_session_history.return_value = [
            {"id": "m1", "role": "user", "text": "hi", "created_at": "t1", "metadata": "{broken"},
        ]
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=sess_mgr), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=chat):
            result = await get_session_history("s1", user)
        assert result["success"] is True
        assert result["messages"][0]["metadata"] == "{broken"

    async def test_get_history_internal_error(self):
        sess_mgr = MagicMock()
        sess_mgr.get_session.side_effect = RuntimeError("db")
        user = SimpleNamespace(id="u1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=sess_mgr):
            result = await get_session_history("s1", user)
        assert result["success"] is False
        assert result["error"] == "Internal server error"


class TestChatRoute:
    async def test_slash_command_path(self):
        reply = SimpleNamespace(ok=True, reply="Task created", task_id="t1")
        router = MagicMock()
        router.return_value.route.return_value = reply
        db = MagicMock()
        session_manager = MagicMock()
        session_manager.create_session.return_value = "sess-1"
        with patch("core.board_command_router.parse_slash", return_value=("create_task", {"title": "X"})), \
             patch("core.board_command_router.BoardCommandRouter", router), \
             patch("core.database.get_db_session") as mock_session, \
             patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=session_manager), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.save_chat_interaction", new=MagicMock()):
            mock_session.return_value.__enter__.return_value = db
            result = await chat_with_agent(req("/task create X"), SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert result["response"]["intent"] == "create_task"

    async def test_existing_session_ownership_violation(self):
        session_manager = MagicMock()
        session_manager.get_session.return_value = {"session_id": "s1", "user_id": "other-user"}
        request = req("hello", session_id="s1")
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=session_manager), \
             patch("core.board_command_router.parse_slash", return_value=None):
            with pytest.raises(Exception) as exc_info:
                await chat_with_agent(request, SimpleNamespace(id="u1"))
        assert exc_info.value.status_code == 403

    async def test_llm_intent_dispatch_list_workflows(self):
        session_manager = MagicMock()
        session_manager.create_session.return_value = "sess-new"
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=session_manager), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_context_manager", return_value=MagicMock()), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "LIST_WORKFLOWS", "entities": {}})), \
             patch("core.atom_agent_endpoints.load_workflows", return_value=[{"id": "w1", "name": "Daily"}]), \
             patch("core.atom_agent_endpoints.save_chat_interaction", new=MagicMock()), \
             patch("core.behavior_analyzer.get_behavior_analyzer", return_value=MagicMock()):
            result = await chat_with_agent(req("list workflows"), SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert "Found 1 workflows" in result["response"]["message"]
        assert result["session_id"] == "sess-new"

    async def test_reference_resolution_for_run_workflow(self):
        session_manager = MagicMock()
        session_manager.create_session.return_value = "sess-new"
        context_manager = MagicMock()
        context_manager.resolve_reference = AsyncMock(return_value={"id": "wf-resolved", "name": "Daily"})
        engine_cls = MagicMock()
        engine_cls.return_value.execute_workflow_definition = AsyncMock(return_value={"ok": True})
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=session_manager), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_context_manager", return_value=context_manager), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "RUN_WORKFLOW",
                                               "entities": {"workflow_ref": "that"}})), \
             patch("core.atom_agent_endpoints.load_workflows",
                   return_value=[{"id": "wf-resolved", "name": "Daily", "steps": []}]), \
             patch("core.atom_agent_endpoints._gate_workflow_permission", new=AsyncMock(return_value=None)), \
             patch("core.atom_agent_endpoints.AutomationEngine", engine_cls), \
             patch("core.atom_agent_endpoints.save_chat_interaction", new=MagicMock()), \
             patch("core.behavior_analyzer.get_behavior_analyzer", return_value=MagicMock()):
            result = await chat_with_agent(req("run that workflow"), SimpleNamespace(id="u1"))
        assert result["success"] is True
        context_manager.resolve_reference.assert_called_once()

    async def test_default_intent_suggestions(self):
        session_manager = MagicMock()
        session_manager.create_session.return_value = "sess-new"
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=session_manager), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_context_manager", return_value=MagicMock()), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "BOGUS", "entities": {}})), \
             patch("core.atom_agent_endpoints.save_chat_interaction", new=MagicMock()), \
             patch("core.behavior_analyzer.get_behavior_analyzer", return_value=MagicMock()):
            result = await chat_with_agent(req("anything"), SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert "Try asking me something" in result["response"]["message"]

    async def test_episode_trigger_with_agent_id(self):
        session_manager = MagicMock()
        session_manager.create_session.return_value = "sess-new"
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=session_manager), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_context_manager", return_value=MagicMock()), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "BOGUS", "entities": {}})), \
             patch("core.atom_agent_endpoints.save_chat_interaction", new=MagicMock()), \
             patch("core.atom_agent_endpoints.trigger_episode_creation", new=MagicMock()) as trigger, \
             patch("core.behavior_analyzer.get_behavior_analyzer", return_value=MagicMock()):
            result = await chat_with_agent(req("hello", agent_id="ag-1"), SimpleNamespace(id="u1"))
        assert result["success"] is True
        trigger.assert_called_once()

    async def test_behavior_suggestions_injected(self):
        session_manager = MagicMock()
        session_manager.create_session.return_value = "sess-new"
        analyzer = MagicMock()
        analyzer.detect_patterns.return_value = [
            {"name": "Batch", "description": "d", "suggested_actions": ["wf-batch"]}
        ]
        with patch("core.atom_agent_endpoints.get_chat_session_manager", return_value=session_manager), \
             patch("core.atom_agent_endpoints.get_chat_history_manager", return_value=MagicMock()), \
             patch("core.atom_agent_endpoints.get_chat_context_manager", return_value=MagicMock()), \
             patch("core.board_command_router.parse_slash", return_value=None), \
             patch("core.atom_agent_endpoints.classify_intent_with_llm",
                   new=AsyncMock(return_value={"intent": "BOGUS", "entities": {}})), \
             patch("core.atom_agent_endpoints.save_chat_interaction", new=MagicMock()), \
             patch("core.behavior_analyzer.get_behavior_analyzer", return_value=analyzer):
            result = await chat_with_agent(req("anything"), SimpleNamespace(id="u1"))
        assert result["success"] is True
        assert result["response"]["actions"][0]["type"] == "run_workflow"

    async def test_chat_internal_error(self):
        with patch("core.atom_agent_endpoints.get_chat_session_manager", side_effect=RuntimeError("db")):
            result = await chat_with_agent(req("hello"), SimpleNamespace(id="u1"))
        assert result["success"] is False
        assert result["error"] == "Internal server error"


class TestClassifyIntentWithLlm:
    async def test_plain_json(self):
        llm = MagicMock()
        llm.return_value.generate = AsyncMock(return_value='{"intent": "HELP", "entities": {}}')
        with patch("core.atom_agent_endpoints.LLMService", llm):
            result = await classify_intent_with_llm("help me", [])
        assert result["intent"] == "HELP"

    async def test_fenced_json(self):
        llm = MagicMock()
        llm.return_value.generate = AsyncMock(
            return_value='```json\n{"intent": "SEND_EMAIL", "entities": {"recipient": "a"}}\n```')
        with patch("core.atom_agent_endpoints.LLMService", llm):
            result = await classify_intent_with_llm("email a", [])
        assert result["intent"] == "SEND_EMAIL"

    async def test_fenced_plain(self):
        llm = MagicMock()
        llm.return_value.generate = AsyncMock(return_value='```\n{"intent": "HELP", "entities": {}}\n```')
        with patch("core.atom_agent_endpoints.LLMService", llm):
            result = await classify_intent_with_llm("help", [])
        assert result["intent"] == "HELP"

    async def test_invalid_json_falls_back(self):
        llm = MagicMock()
        llm.return_value.generate = AsyncMock(return_value="not json at all")
        with patch("core.atom_agent_endpoints.LLMService", llm):
            result = await classify_intent_with_llm("list my workflows", [])
        assert result["intent"] == "LIST_WORKFLOWS"

    async def test_llm_exception_falls_back(self):
        llm = MagicMock()
        llm.return_value.generate = AsyncMock(side_effect=RuntimeError("no api"))
        with patch("core.atom_agent_endpoints.LLMService", llm):
            result = await classify_intent_with_llm("list my workflows", [])
        assert result["intent"] == "LIST_WORKFLOWS"

    async def test_knowledge_context_included(self):
        km = MagicMock()
        km.answer_query = AsyncMock(return_value={"relevant_facts": ["Fact 1"]})
        llm = MagicMock()
        llm.return_value.generate = AsyncMock(return_value='{"intent": "HELP", "entities": {}}')
        with patch("core.atom_agent_endpoints.LLMService", llm), \
             patch("core.knowledge_query_endpoints.get_knowledge_query_manager", return_value=km):
            result = await classify_intent_with_llm("help", [], system_context="ctx")
        assert result["intent"] == "HELP"
        prompt = llm.return_value.generate.call_args.kwargs["system_instruction"]
        assert "Knowledge Context" in prompt

    async def test_knowledge_fetch_exception_tolerated(self):
        km = MagicMock()
        km.answer_query = AsyncMock(side_effect=RuntimeError("km down"))
        llm = MagicMock()
        llm.return_value.generate = AsyncMock(return_value='{"intent": "HELP", "entities": {}}')
        with patch("core.atom_agent_endpoints.LLMService", llm), \
             patch("core.knowledge_query_endpoints.get_knowledge_query_manager", return_value=km):
            result = await classify_intent_with_llm("help", [])
        assert result["intent"] == "HELP"
