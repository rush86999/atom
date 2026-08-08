"""
Bug-hunt + coverage tests for core/atom_agent_endpoints.py (round 2).

Each ``BUG:`` test is written first (TDD), verified to FAIL for the right
reason, then the source is fixed and the test passes.

Focus: HTTP input validation, IDOR/scoping, error-leak in responses,
mass-assignment, and robustness against workflow dicts that use either the
``id`` or ``workflow_id`` key (the codebase is inconsistent about which).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from core.atom_agent_endpoints import (
    ChatRequest,
    fallback_intent_classification,
    handle_list_workflows,
    handle_run_workflow,
    handle_schedule_workflow,
    handle_crm_intent,
    handle_send_email,
    handle_create_event,
    handle_get_history,
    handle_search_emails,
    handle_knowledge_query,
    handle_task_intent,
    handle_finance_intent,
    handle_resolve_conflicts,
    handle_set_goal,
    handle_goal_status,
    handle_cancel_schedule,
    handle_get_status,
    handle_platform_search,
    handle_silent_stakeholders,
)


# =============================================================================
# BUG 1 (CRITICAL): handle_run_workflow raises an UNHANDLED KeyError when a
# workflow dict lacks the ``workflow_id`` key. The lookup at line 1001 uses a
# direct subscript ``w['workflow_id']``; if the workflow only has ``id`` (a
# valid state — the codebase elsewhere defensively checks both keys with
# ``.get('id') or .get('workflow_id')``), the generator crashes BEFORE the
# try/except, producing an unhandled 500 instead of a clean not-found / run
# response.
# =============================================================================

@pytest.mark.asyncio
async def test_bug_handle_run_workflow_missing_workflow_id_key():
    """BUG: workflow matched by name but missing 'workflow_id' key raises
    KeyError instead of running or returning not-found."""
    with patch("core.atom_agent_endpoints.load_workflows") as mock_load:
        # Workflow has only 'id' (valid per defensive .get() pattern elsewhere).
        mock_load.return_value = [{"name": "Daily Report", "id": "wf-123"}]

        with patch("core.atom_agent_endpoints.AutomationEngine") as mock_engine:
            mock_engine.return_value.execute_workflow_definition = AsyncMock(
                return_value={"status": "running"}
            )

            request = ChatRequest(message="run daily report", user_id="u1")
            # Should NOT raise; should either run or return a structured result.
            try:
                result = await handle_run_workflow(
                    request, {"workflow_ref": "daily report"}
                )
            except KeyError as e:  # pragma: no cover - the bug we are fixing
                pytest.fail(f"handle_run_workflow raised KeyError: {e}")

            # The workflow exists, so it should be able to run.
            assert "success" in result


@pytest.mark.asyncio
async def test_bug_handle_run_workflow_id_only_lookup_by_id():
    """BUG: looking up a workflow purely by its 'id' value crashes with
    KeyError because the code does ``workflow_ref in w['workflow_id']``."""
    with patch("core.atom_agent_endpoints.load_workflows") as mock_load:
        mock_load.return_value = [{"name": "Unrelated", "id": "wf-abc"}]

        with patch("core.atom_agent_endpoints.AutomationEngine") as mock_engine:
            mock_engine.return_value.execute_workflow_definition = AsyncMock(
                return_value={"status": "running"}
            )

            request = ChatRequest(message="run", user_id="u1")
            # workflow_ref matches the 'id' field, name does not match.
            try:
                result = await handle_run_workflow(
                    request, {"workflow_ref": "wf-abc"}
                )
            except KeyError as e:  # pragma: no cover - the bug we are fixing
                pytest.fail(f"handle_run_workflow raised KeyError: {e}")

            # Either it runs (matched by id) or reports not-found; never raises.
            assert "success" in result


# =============================================================================
# BUG 2 (CRITICAL): handle_list_workflows raises KeyError on 'workflow_id'
# inside the actions list comprehension when workflows only carry 'id'.
# Caught by the broad except, it returns the generic 'Failed to load workflows'
# even though workflows DO exist.
# =============================================================================

@pytest.mark.asyncio
async def test_bug_handle_list_workflows_id_only_no_keyerror():
    """BUG: handle_list_workflows must not crash when workflow dicts only
    have 'id' (no 'workflow_id' key)."""
    with patch("core.atom_agent_endpoints.load_workflows") as mock_load:
        mock_load.return_value = [
            {"name": "WF1", "id": "w1"},
            {"name": "WF2", "id": "w2"},
            {"name": "WF3", "id": "w3"},
        ]

        request = ChatRequest(message="list workflows", user_id="u1")
        result = await handle_list_workflows(request)

        assert result["success"] is True, (
            "Listing valid workflows must succeed, not return generic failure"
        )
        assert "Found 3 workflows" in result["response"]["message"]


# =============================================================================
# BUG 3 (HIGH): handle_schedule_workflow has the same KeyError-prone lookup
# (line 1044) as handle_run_workflow. Verify it tolerates id-only workflows.
# =============================================================================

@pytest.mark.asyncio
async def test_bug_handle_schedule_workflow_id_only_no_keyerror():
    """BUG: handle_schedule_workflow must not raise KeyError when the matched
    workflow only has 'id'."""
    with patch("core.atom_agent_endpoints.load_workflows") as mock_load:
        mock_load.return_value = [{"name": "Backup", "id": "wf-backup"}]

        with patch("core.time_expression_parser.parse_time_expression", new=AsyncMock(
            return_value={
                "schedule_type": "interval",
                "interval_minutes": 60,
                "human_readable": "every 60 minutes",
            }
        )):
            with patch("core.atom_agent_endpoints.workflow_scheduler") as mock_sched:
                mock_sched.schedule_workflow_interval = MagicMock()

                request = ChatRequest(message="schedule", user_id="u1")
                try:
                    result = await handle_schedule_workflow(
                        request,
                        {"workflow_ref": "Backup", "time_expression": "hourly"},
                    )
                except KeyError as e:  # pragma: no cover - the bug we are fixing
                    pytest.fail(f"handle_schedule_workflow raised KeyError: {e}")

                # The workflow matched; scheduling should succeed.
                assert result["success"] is True


# =============================================================================
# BUG 4 (MEDIUM): handle_crm_intent leaks internal exception text to the
# client via ``error: f"Failed to process sales query: {str(e)}"``. Errors
# returned to chat users must be generic (no internal detail leak).
# =============================================================================

@pytest.mark.asyncio
async def test_bug_handle_crm_intent_does_not_leak_exception():
    """BUG: handle_crm_intent returns the raw exception string in the response,
    leaking internal details to the end user."""
    # get_db_session is imported inside the handler from core.database.
    with patch("core.database.get_db_session") as mock_db_ctx:
        # Force the context manager to blow up with a revealing message.
        mock_db_ctx.side_effect = RuntimeError(
            "DB connection string postgres://user:SECRETPW@host"
        )

        request = ChatRequest(message="show pipeline", user_id="u1")
        result = await handle_crm_intent(request, {})

        assert result["success"] is False
        error_text = result.get("error", "")
        # Must NOT echo the raw exception (which contains the secret).
        assert "SECRETPW" not in error_text, (
            "Raw exception detail must not leak into the user-facing error"
        )
        assert "postgres://" not in error_text


# =============================================================================
# Coverage tests (secondary goal): exercise untested-correct handler branches.
# =============================================================================

class TestHandlerCoverage:
    """Cover the smaller intent handlers that were previously untested."""

    @pytest.mark.asyncio
    async def test_handle_send_email_default_recipient(self):
        req = ChatRequest(message="send email", user_id="u")
        result = await handle_send_email(req, {})
        assert result["success"] is True
        assert "No Subject" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_create_event_defaults(self):
        req = ChatRequest(message="create event", user_id="u")
        result = await handle_create_event(req, {})
        assert result["success"] is True
        # default summary is "New Meeting"
        assert "New Meeting" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_get_history_missing_and_present(self):
        req = ChatRequest(message="history", user_id="u")
        # missing ref -> structured failure
        r1 = await handle_get_history(req, {})
        assert r1["success"] is False
        # present ref -> success
        r2 = await handle_get_history(req, {"workflow_ref": "wf1"})
        assert r2["success"] is True

    @pytest.mark.asyncio
    async def test_handle_cancel_schedule_paths(self):
        req = ChatRequest(message="cancel", user_id="u")
        # no schedule_id / workflow_ref -> ask to specify
        r1 = await handle_cancel_schedule(req, {})
        assert r1["success"] is False

        # workflow_ref only -> suggests going to schedule tab
        r2 = await handle_cancel_schedule(req, {"workflow_ref": "wf1"})
        assert r2["success"] is True

        # schedule_id, scheduler remove succeeds
        with patch("core.atom_agent_endpoints.workflow_scheduler") as mock_sched:
            mock_sched.remove_job.return_value = True
            r3 = await handle_cancel_schedule(req, {"schedule_id": "job1"})
            assert r3["success"] is True
            assert "cancelled" in r3["response"]["message"].lower()

            # schedule_id, scheduler remove fails
            mock_sched.remove_job.return_value = False
            r4 = await handle_cancel_schedule(req, {"schedule_id": "job1"})
            assert r4["success"] is False

    @pytest.mark.asyncio
    async def test_handle_get_status(self):
        req = ChatRequest(message="status", user_id="u")
        result = await handle_get_status(req, {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handle_search_emails_empty_and_found(self):
        req = ChatRequest(message="search emails", user_id="u")
        with patch("core.atom_agent_endpoints.GmailService") as mock_gmail:
            # empty result
            mock_gmail.return_value.search_messages.return_value = []
            r1 = await handle_search_emails(req, {"query": "x"})
            assert r1["success"] is True
            assert "No emails" in r1["response"]["message"]

            # found result
            mock_gmail.return_value.search_messages.return_value = [{"id": "1"}, {"id": "2"}]
            r2 = await handle_search_emails(req, {"query": "x"})
            assert r2["success"] is True
            assert "Found 2 emails" in r2["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_search_emails_exception(self):
        req = ChatRequest(message="search", user_id="u")
        with patch("core.atom_agent_endpoints.GmailService") as mock_gmail:
            mock_gmail.side_effect = RuntimeError("boom")
            r = await handle_search_emails(req, {"query": "x"})
            assert r["success"] is False
            assert "Failed to search" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_knowledge_query_success_and_failure(self):
        req = ChatRequest(message="who?", user_id="u")
        with patch("core.atom_agent_endpoints.get_knowledge_query_manager") as mock_mgr:
            mock_mgr.return_value.answer_query = AsyncMock(
                return_value={"answer": "Alice worked on it."}
            )
            r1 = await handle_knowledge_query(req, {"query": "who?"})
            assert r1["success"] is True
            assert "Alice" in r1["response"]["message"]

            # failure path
            mock_mgr.return_value.answer_query = AsyncMock(side_effect=RuntimeError("x"))
            r2 = await handle_knowledge_query(req, {"query": "who?"})
            assert r2["success"] is False

    @pytest.mark.asyncio
    async def test_handle_task_intent_create_asana_and_list(self):
        req = ChatRequest(message="create task", user_id="u")
        with patch("core.atom_agent_endpoints.create_task", new=AsyncMock(
            return_value={"id": "t1"}
        )) as mock_create, patch(
            "core.atom_agent_endpoints.get_tasks", new=AsyncMock(
                return_value={"tasks": [{"id": "1"}, {"id": "2"}]}
            )
        ):
            # local platform
            r1 = await handle_task_intent("CREATE_TASK", {"title": "My Task"}, req)
            assert r1["success"] is True
            assert "local" in r1["response"]["message"]

            # asana platform (title contains 'asana')
            r2 = await handle_task_intent("CREATE_TASK", {"title": "asana task"}, req)
            assert r2["success"] is True
            assert "asana" in r2["response"]["message"]

            # list
            r3 = await handle_task_intent("LIST_TASKS", {}, req)
            assert r3["success"] is True
            assert "Found 2 tasks" in r3["response"]["message"]

            # unknown intent
            r4 = await handle_task_intent("OTHER", {}, req)
            assert r4["success"] is False

    @pytest.mark.asyncio
    async def test_handle_finance_intent_paths(self):
        req = ChatRequest(message="finance", user_id="u")
        r1 = await handle_finance_intent("GET_TRANSACTIONS", {}, req)
        assert r1["success"] is True
        assert "transactions" in r1["response"]["data"]

        r2 = await handle_finance_intent("CHECK_BALANCE", {}, req)
        assert r2["success"] is True
        assert r2["response"]["data"]["balance"] == 12450.00

    @pytest.mark.asyncio
    async def test_handle_resolve_conflicts(self):
        req = ChatRequest(message="conflicts", user_id="u")
        r = await handle_resolve_conflicts(req, {})
        assert r["success"] is True
        assert "conflicts" in r["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_set_goal(self):
        req = ChatRequest(message="set goal", user_id="u")
        r = await handle_set_goal(req, {"goal_text": "Double revenue"})
        assert r["success"] is True
        assert "Double revenue" in r["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_goal_status(self):
        req = ChatRequest(message="goal status", user_id="u")
        r = await handle_goal_status(req, {})
        assert r["success"] is True
        assert "active goal" in r["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_silent_stakeholders_empty_and_found(self):
        req = ChatRequest(message="silent", user_id="u")
        with patch("core.stakeholder_engine.get_stakeholder_engine") as mock_eng:
            mock_eng.return_value.identify_silent_stakeholders = AsyncMock(return_value=[])
            r1 = await handle_silent_stakeholders(req)
            assert r1["success"] is True
            assert "actively engaged" in r1["response"]["message"]

            mock_eng.return_value.identify_silent_stakeholders = AsyncMock(return_value=[
                {"name": "Bob", "email": "b@x.com", "days_since": 10, "suggested_outreach": "hi"},
            ])
            r2 = await handle_silent_stakeholders(req)
            assert r2["success"] is True
            assert "Bob" in r2["response"]["message"]


class TestFallbackClassificationCoverage:
    """Cover fallback_intent_classification branches not exercised elsewhere."""

    def test_schedule_workflow_extraction(self):
        # Note: line 810 requires 'workflow' or 'run' in msg for SCHEDULE_WORKFLOW.
        result = fallback_intent_classification("schedule the daily report workflow every weekday at 9am")
        assert result["intent"] == "SCHEDULE_WORKFLOW"
        assert "workflow_ref" in result["entities"]
        assert "time_expression" in result["entities"]

    def test_follow_up_emails(self):
        assert fallback_intent_classification("follow up on emails")["intent"] == "FOLLOW_UP_EMAILS"
        assert fallback_intent_classification("follow-up emails")["intent"] == "FOLLOW_UP_EMAILS"

    def test_invoice_status(self):
        assert fallback_intent_classification("what is the invoice status")["intent"] == "INVOICE_STATUS"

    def test_goal_intents(self):
        assert fallback_intent_classification("set a new goal")["intent"] == "SET_GOAL"
        assert fallback_intent_classification("goal progress")["intent"] == "GOAL_STATUS"

    def test_wellness(self):
        assert fallback_intent_classification("I'm experiencing burnout")["intent"] == "WELLNESS_CHECK"
        assert fallback_intent_classification("wellness check please")["intent"] == "WELLNESS_CHECK"

    def test_search_platform(self):
        r = fallback_intent_classification("find documents")
        assert r["intent"] == "SEARCH_PLATFORM"
        assert "query" in r["entities"]

    def test_knowledge_query(self):
        assert fallback_intent_classification("who is alice")["intent"] == "KNOWLEDGE_QUERY"

    def test_run_workflow_ref_extraction(self):
        r = fallback_intent_classification("run the backup workflow")
        assert r["intent"] == "RUN_WORKFLOW"
        assert "workflow_ref" in r["entities"]
