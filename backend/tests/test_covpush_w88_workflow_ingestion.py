# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/workflow_engine.py + core/ingestion_pipeline.py.

No network / no LLM / no real DB: every external boundary (integration
services, token storage, state manager, websocket manager, analytics,
GraphRAG, LanceDB, Docling, usage tracker, httpx) is mocked.
"""
import asyncio
import contextlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.workflow_engine as we
import core.ingestion_pipeline as ip
from core.workflow_engine import (
    MissingInputError,
    SchemaValidationError,
    StepTimeoutError,
    WorkflowEngine,
    get_workflow_engine,
)
from core.hybrid_data_ingestion import SyncConfiguration
from core.ingestion_pipeline import IngestionPipelineService
from core.models import DocumentIngestion, IngestionJob, Tenant, UserConnection

LONG_TEXT = "This is a sufficiently long record text for ingestion here"


@pytest.fixture(autouse=True)
def _fast_retries():
    """The retry decorator on _execute_step sleeps 1s+2s+4s between attempts;
    collapse those delays so failure-path tests stay fast."""
    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()):
        yield


# ============================================================================
# Workflow engine — fixtures/helpers
# ============================================================================

def make_engine():
    sm = MagicMock()
    with patch("core.workflow_engine.get_state_manager", return_value=sm):
        engine = WorkflowEngine()
    engine.state_manager = sm
    return engine


def step_dict(**overrides):
    step = {
        "id": "s1", "name": "Step 1", "service": "email", "action": "send",
        "parameters": {}, "continue_on_error": False, "timeout": None,
        "input_schema": {}, "output_schema": {},
    }
    step.update(overrides)
    return step


class TestHelpers:
    def test_check_dependencies(self):
        e = make_engine()
        assert e._check_dependencies({"depends_on": ["a"]},
                                     {"steps": {"a": {"status": "COMPLETED"}}}) is True
        assert e._check_dependencies({"depends_on": ["a"]}, {"steps": {}}) is False
        assert e._check_dependencies({}, {}) is True

    def test_evaluate_condition(self):
        e = make_engine()
        assert e._evaluate_condition("", {}) is True
        assert e._evaluate_condition(None, {}) is True
        assert e._evaluate_condition("${missing.key} == 1", {}) is False
        st = {"outputs": {"s": {"status": "completed", "flag": True, "score": 3.5}},
              "input_data": {"count": 7, "name": "atom", "payload": "x"}}
        assert e._evaluate_condition("${s.status} == 'completed'", st) is True
        assert e._evaluate_condition("${input.count} > 5", st) is True
        assert e._evaluate_condition("${input.count} < 5", st) is False
        assert e._evaluate_condition("${s.flag} == true", st) is True
        assert e._evaluate_condition("${s.score} >= 3.0", st) is True
        assert e._evaluate_condition("${input.name}", st) is True
        # injection blocked; invalid python -> False
        assert e._evaluate_condition("${input.payload}.__class__", st) is False
        assert e._evaluate_condition("not valid python !!!", {}) is False
        # non-dict root lookup returns None -> not found -> False
        assert e._evaluate_condition("${outputs} > 1", {"outputs": 5}) is False

    def test_resolve_parameters(self):
        e = make_engine()
        st = {"input_data": {"x": 5, "name": "atom"},
              "outputs": {"step1": {"count": 3, "n": None}}}
        assert e._resolve_parameter_value(42, st) == 42
        assert e._resolve_parameter_value(None, st) is None
        assert e._resolve_parameter_value("plain", st) == "plain"
        assert e._resolve_parameter_value({"a": "${input.x}", "b": ["${step1.count}"]}, st) \
            == {"a": 5, "b": [3]}
        assert e._resolve_parameter_value("${step1.count}", st) == 3
        assert e._resolve_parameter_value("Hello ${input.name}", st) == "Hello atom"
        # None value that exists (path exists) is returned, not an error
        assert e._resolve_parameter_value("${step1.n}", st) is None
        with pytest.raises(MissingInputError):
            e._resolve_parameter_value("${ghost.path}", st)
        assert e._resolve_parameter_value("Hello ${input.name}#${input.x}", st) == "Hello atom#5"
        with pytest.raises(MissingInputError):
            e._resolve_parameter_value("x ${ghost.p} y", st)
        assert e._resolve_parameters({"k": "${input.x}"}, st) == {"k": 5}

    def test_path_and_value_helpers(self):
        e = make_engine()
        st = {"input_data": {"a": {"b": 1}}, "outputs": {"s1": {"o": 2}}}
        assert e._path_exists("input.a.b", st) is True
        assert e._path_exists("input.a.z", st) is False
        assert e._path_exists("s1.o", st) is True
        assert e._path_exists("ghost.o", st) is False
        assert e._get_value_from_path("input.a.b", st) == 1
        assert e._get_value_from_path("s1.o", st) == 2
        assert e._get_value_from_path("s1.deep.o", st) is None
        assert e._get_value_from_path("input.deep.o", st) is None
        # non-dict mid-path
        assert e._get_value_from_path("s1.o.x", st) is None
        assert e._get_value_from_path("input.a.b.c", st) is None

    def test_schema_validation(self):
        e = make_engine()
        e._validate_input_schema({}, {})
        e._validate_output_schema({}, {})
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        e._validate_input_schema(step_dict(input_schema=schema), {"a": "x"})
        with pytest.raises(SchemaValidationError):
            e._validate_input_schema(step_dict(input_schema=schema), {"a": 1})
        e._validate_output_schema(step_dict(output_schema=schema), {"a": "x"})
        with pytest.raises(SchemaValidationError):
            e._validate_output_schema(step_dict(output_schema=schema), {"a": 1})

    def test_get_token(self):
        e = make_engine()
        assert e._get_token(None, "slack") is None
        with patch.object(we, "token_storage") as ts:
            ts.get_token.return_value = {"access_token": "t"}
            assert e._get_token("c1", "slack") == "t"
            # miss on conn id -> fallback to service name
            ts.get_token.side_effect = lambda k: {"slack": {"access_token": "fb"}}.get(k)
            assert e._get_token("c1", "slack") == "fb"
            ts.get_token.side_effect = None
            ts.get_token.return_value = None
            assert e._get_token("c1", "slack") is None


class TestGraphBuilders:
    def test_build_and_convert(self):
        e = make_engine()
        wf = {
            "nodes": [
                {"id": "a", "title": "A", "type": "trigger", "config": {"service": "email"}},
                {"id": "b", "title": "B", "config": {"action": "send", "parameters": {"x": 1}}},
            ],
            "connections": [{"source": "a", "target": "b"},
                            {"source": None, "target": "b"},  # malformed, skipped
                            {"source": "a", "target": "ghost"}],  # unknown target
        }
        steps = e._convert_nodes_to_steps(wf)
        assert [s["id"] for s in steps] == ["a", "b"]
        assert steps[0]["type"] == "trigger"
        assert steps[0]["action"] == "manual_trigger"
        assert steps[1]["type"] == "action"
        g = e._build_execution_graph(wf)
        assert g["adjacency"]["a"][0]["target"] == "b"
        assert g["reverse_adjacency"]["b"]
        assert e._has_conditional_connections(wf) is False
        wf["connections"].append({"source": "a", "target": "b", "condition": "1 == 1"})
        assert e._has_conditional_connections(wf) is True

    def test_convert_cycle_raises(self):
        e = make_engine()
        wf = {"nodes": [{"id": "a"}, {"id": "b"}],
              "connections": [{"source": "a", "target": "b"},
                              {"source": "b", "target": "a"}]}
        with pytest.raises(ValueError, match="circular"):
            e._convert_nodes_to_steps(wf)


class TestExecuteStepDispatch:
    async def test_registry_success(self):
        e = make_engine()
        res = await e._execute_step(step_dict(), {})
        assert res["status"] == "success"
        assert res["execution_method"] == "service_registry"

    async def test_non_success_envelope(self):
        e = make_engine()
        async def boom(action, params, connection_id=None):
            return {"status": "error", "error": "nope"}
        with patch.object(e, "_execute_email_action", boom):
            with pytest.raises(Exception, match="nope"):
                await e._execute_step(step_dict(), {})

    async def test_timeout(self):
        e = make_engine()
        never = asyncio.Event()
        async def slow(action, params, connection_id=None):
            await never.wait()  # never set -> wait_for must fire
        with patch.object(e, "_execute_email_action", slow):
            with pytest.raises(StepTimeoutError):
                await e._execute_step(step_dict(timeout=0.01), {})

    async def test_unknown_service_generic_and_fallbacks(self):
        e = make_engine()
        # generic success
        with patch.object(e, "_execute_generic_action",
                          AsyncMock(return_value={"ok": 1})):
            res = await e._execute_step(step_dict(service="ghost"), {})
        assert res["execution_method"] == "generic_catalog_executor"
        # generic fail -> no fallback -> raise
        with patch.object(e, "_execute_generic_action",
                          AsyncMock(side_effect=RuntimeError("cat"))):
            with pytest.raises(ValueError, match="Unknown service"):
                await e._execute_step(step_dict(service="ghost"), {})
        # executor raises -> fallback succeeds
        with patch.object(e, "_execute_email_action",
                          AsyncMock(side_effect=RuntimeError("p"))), \
             patch.object(e, "_execute_calendar_action",
                          AsyncMock(return_value={"ok": 1})):
            res = await e._execute_step(
                step_dict(service="email", fallback_service="calendar"), {})
        assert res["execution_method"] == "fallback_service"
        assert res["fallback_used"] is True
        # fallback envelope error / both fail / no fallback -> primary raised
        with patch.object(e, "_execute_email_action",
                          AsyncMock(side_effect=RuntimeError("p"))), \
             patch.object(e, "_execute_calendar_action",
                          AsyncMock(return_value={"status": "error", "error": "f"})):
            with pytest.raises(ValueError, match="fallback"):
                await e._execute_step(
                    step_dict(service="email", fallback_service="calendar"), {})
        with patch.object(e, "_execute_email_action",
                          AsyncMock(side_effect=RuntimeError("p"))), \
             patch.object(e, "_execute_calendar_action",
                          AsyncMock(side_effect=RuntimeError("f"))):
            with pytest.raises(ValueError, match="also failed"):
                await e._execute_step(
                    step_dict(service="email", fallback_service="calendar"), {})
        with patch.object(e, "_execute_email_action",
                          AsyncMock(side_effect=RuntimeError("primary boom"))):
            with pytest.raises(RuntimeError, match="primary boom"):
                await e._execute_step(step_dict(), {})
        # fallback unknown -> raises primary
        with patch.object(e, "_execute_email_action",
                          AsyncMock(side_effect=RuntimeError("p2"))):
            with pytest.raises(RuntimeError, match="p2"):
                await e._execute_step(
                    step_dict(fallback_service="not_a_service"), {})

    async def test_mcp_step_kwarg(self):
        e = make_engine()
        with patch.object(e, "_execute_mcp_action",
                          AsyncMock(return_value={"ok": 1})) as m:
            await e._execute_step(
                step_dict(service="mcp", id="m1", execution_id="ex"), {})
        assert m.call_args[1]["step"]["id"] == "m1"


class TestSimpleExecutors:
    @pytest.mark.parametrize("fn,name", [
        ("_execute_email_action", "Email"),
        ("_execute_calendar_action", "Calendar"),
        ("_execute_database_action", "Database"),
        ("_execute_webhook_action", "Webhook"),
        ("_execute_ai_action", "AI"),
    ])
    async def test_simple(self, fn, name):
        e = make_engine()
        res = await getattr(e, fn)("any", {})
        assert res["status"] == "success"
        assert name in res["result"]


class TestSlackExecutor:
    async def test_actions(self):
        e = make_engine()
        tok = patch("core.workflow_engine.token_storage.get_token",
                    return_value={"access_token": "t"})
        svc = "integrations.slack_service_unified.slack_unified_service"
        with tok, patch(svc) as s:
            s.post_message = AsyncMock(return_value={"ok": True})
            s.list_channels = AsyncMock(return_value=[])
            s.get_team_info = AsyncMock(return_value={"team": "x"})
            s.get_channel_info = AsyncMock(return_value={"id": "c"})
            s.get_channel_history = AsyncMock(return_value=[])
            s.update_message = AsyncMock(return_value={"ok": True})
            s.delete_message = AsyncMock(return_value={"ok": True})
            s.search_messages = AsyncMock(return_value={"m": []})
            s.list_files = AsyncMock(return_value=[])
            assert (await e._execute_slack_action(
                "chat_postMessage", {"channel": "c", "text": "hi"}, "c1"))["status"] == "success"
            await e._execute_slack_action("list_channels", {}, "c1")
            await e._execute_slack_action("chat_getUsers", {}, "c1")
            r = await e._execute_slack_action("get_channel_info", {"channel_id": "c"}, "c1")
            assert r["result"] == {"id": "c"}
            await e._execute_slack_action("get_channel_history", {"channel_id": "c", "limit": 5}, "c1")
            await e._execute_slack_action(
                "update_message", {"channel_id": "c", "message_ts": "1", "text": "n"}, "c1")
            await e._execute_slack_action(
                "delete_message", {"channel_id": "c", "message_ts": "1"}, "c1")
            await e._execute_slack_action("search_messages", {"query": "q"}, "c1")
            await e._execute_slack_action("files_list", {"channel_id": "c"}, "c1")
            r = await e._execute_slack_action("files_get_upload_url_external", {}, "c1")
            assert r["result"]["ok"] is False
            r = await e._execute_slack_action("reactions_add", {}, "c1")
            assert r["result"]["ok"] is False

    async def test_slack_errors(self):
        e = make_engine()
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(Exception, match="Slack authentication"):
                await e._execute_slack_action("chat_postMessage", {}, None)
        tok = patch("core.workflow_engine.token_storage.get_token",
                    return_value={"access_token": "t"})
        with tok:
            for action, params, msg in [
                ("get_channel_info", {}, "channel_id is required"),
                ("get_channel_history", {}, "channel_id is required"),
                ("update_message", {"channel_id": "c"}, "update_message"),
                ("delete_message", {"channel_id": "c"}, "delete_message"),
                ("search_messages", {}, "query is required"),
                ("nope", {}, "Unsupported Slack action"),
            ]:
                with pytest.raises(ValueError, match=msg):
                    await e._execute_slack_action(action, params, "c1")

    async def test_slack_token_fallback_lookup(self):
        e = make_engine()
        def _get(ident):
            return {"slack": {"access_token": "fb"}}.get(ident)
        with patch("core.workflow_engine.token_storage.get_token", side_effect=_get), \
             patch("integrations.slack_service_unified.slack_unified_service.post_message",
                   create=True, new=AsyncMock(return_value={"ok": True})):
            r = await e._execute_slack_action(
                "chat_postMessage", {"channel": "c", "text": "x"}, "c1")
        assert r["authenticated"] is True


class TestAsanaExecutor:
    async def test_actions(self):
        e = make_engine()
        svc = "integrations.asana_service.asana_service"
        with patch.object(e, "_get_token", return_value="tok"), patch(svc) as s:
            s.create_task = AsyncMock(return_value={"gid": "1"})
            s.get_tasks = AsyncMock(return_value=[])
            s.get_projects = AsyncMock(return_value=[])
            s.update_task = AsyncMock(return_value={"gid": "1"})
            s.add_task_comment = AsyncMock(return_value={})
            s.get_workspaces = AsyncMock(return_value=[])
            s.get_users = AsyncMock(return_value=[])
            s.get_teams = AsyncMock(return_value=[])
            s.search_tasks = AsyncMock(return_value=[])
            assert (await e._execute_asana_action("create_task", {"name": "n"}, "c1"))["status"] == "success"
            await e._execute_asana_action("get_tasks", {"workspace": "w"}, "c1")
            await e._execute_asana_action("get_projects", {"workspace": "w"}, "c1")
            await e._execute_asana_action("update_task", {"task_gid": "t"}, "c1")
            await e._execute_asana_action("add_comment", {"task_gid": "t", "text": "x"}, "c1")
            await e._execute_asana_action("get_workspaces", {}, "c1")
            await e._execute_asana_action("get_users", {"workspace": "w"}, "c1")
            await e._execute_asana_action("get_teams", {"workspace": "w"}, "c1")
            await e._execute_asana_action("search_tasks", {"workspace": "w", "query": "q"}, "c1")
            r = await e._execute_asana_action("create_project", {}, "c1")
            assert r["result"]["ok"] is False

    async def test_asana_errors(self):
        e = make_engine()
        with patch.object(e, "_get_token", return_value=None), \
             patch.dict(os.environ, {}, clear=False), \
             patch("core.workflow_engine.os.getenv", return_value=None):
            with pytest.raises(Exception, match="Asana authentication"):
                await e._execute_asana_action("create_task", {}, None)
        with patch.object(e, "_get_token", return_value="tok"):
            for action, params, msg in [
                ("update_task", {}, "task_gid"),
                ("add_comment", {}, "task_gid and text"),
                ("get_users", {}, "workspace is required"),
                ("get_teams", {}, "workspace is required"),
                ("search_tasks", {}, "workspace and query"),
                ("nope", {}, "Unsupported Asana action"),
            ]:
                with pytest.raises(ValueError, match=msg):
                    await e._execute_asana_action(action, params, "c1")


class TestOtherRegistryExecutors:
    async def test_discord(self):
        e = make_engine()
        with patch.object(e, "_get_token", return_value=None), \
             patch("integrations.discord_service.discord_service") as ds:
            ds.bot_token = None
            with pytest.raises(Exception, match="Discord authentication"):
                await e._execute_discord_action("send_message", {}, "c1")
            ds.bot_token = "bot"
            ds.send_message = AsyncMock(return_value={"ok": 1})
            r = await e._execute_discord_action(
                "send_message", {"channel_id": "1", "content": "x"}, "c1")
            assert r["status"] == "success"
            r = await e._execute_discord_action("other", {}, "c1")
            assert "simulated" in r["result"]

    async def test_hubspot(self):
        e = make_engine()
        with patch.object(e, "_get_token", return_value=None), \
             patch("integrations.hubspot_service.HubSpotService") as HS:
            HS.return_value.access_token = None
            with pytest.raises(Exception, match="HubSpot authentication"):
                await e._execute_hubspot_action("create_contact", {}, "c1")
            HS.return_value.access_token = "tok"
            HS.return_value.create_contact = AsyncMock(return_value={"id": "1"})
            HS.return_value.create_deal = AsyncMock(return_value={"id": "2"})
            r = await e._execute_hubspot_action("create_contact", {"email": "a@b.c"}, "c1")
            assert r["status"] == "success"
            await e._execute_hubspot_action("create_deal", {"dealname": "d", "amount": 1}, "c1")
            r = await e._execute_hubspot_action("other", {}, "c1")
            assert "simulated" in r["result"]

    async def test_salesforce(self):
        e = make_engine()
        with patch("integrations.salesforce_service.SalesforceService") as SF:
            with patch.object(we, "token_storage") as ts:
                ts.get_token.return_value = None
                with pytest.raises(Exception, match="Salesforce authentication"):
                    await e._execute_salesforce_action("create_lead", {}, "c1")
                ts.get_token.return_value = {"access_token": "t", "instance_url": "u"}
                SF.return_value.create_client.return_value = object()
                SF.return_value.create_lead = AsyncMock(return_value={"id": "l"})
                SF.return_value.create_contact = AsyncMock(return_value={"id": "c"})
                SF.return_value.create_opportunity = AsyncMock(return_value={"id": "o"})
                assert (await e._execute_salesforce_action(
                    "create_lead", {"lastname": "x", "company": "y"}, "c1"))["status"] == "success"
                await e._execute_salesforce_action("create_contact", {}, "c1")
                await e._execute_salesforce_action(
                    "create_opportunity", {}, "c1")
                r = await e._execute_salesforce_action("other", {}, "c1")
                assert "simulated" in r["result"]

    async def test_github(self):
        e = make_engine()
        with patch.object(e, "_get_token", return_value="tok"), \
             patch("integrations.github_service.GitHubService") as GH:
            GH.return_value.create_issue.return_value = {"number": 1}
            r = await e._execute_github_action(
                "create_issue", {"owner": "o", "repo": "r", "title": "t"}, "c1")
            assert r["status"] == "success"
            r = await e._execute_github_action("other", {}, "c1")
            assert "simulated" in r["result"]

    async def test_zoom_notion(self):
        e = make_engine()
        with patch.object(e, "_get_token", return_value="tok"), \
             patch("integrations.zoom_service.ZoomService") as Z:
            Z.return_value.create_meeting = AsyncMock(return_value={"id": "m"})
            r = await e._execute_zoom_action("create_meeting", {"topic": "t"}, "c1")
            assert r["status"] == "success"
            r = await e._execute_zoom_action("other", {}, "c1")
            assert "simulated" in r["result"]
        with patch.object(e, "_get_token", return_value="tok"), \
             patch("integrations.notion_service.NotionService") as N:
            N.return_value.create_page.return_value = {"id": "p"}
            r = await e._execute_notion_action(
                "create_page", {"parent": {}, "properties": {}}, "c1")
            assert r["status"] == "success"
            r = await e._execute_notion_action("other", {}, "c1")
            assert "simulated" in r["result"]

    async def test_gmail(self):
        e = make_engine()
        with patch("integrations.gmail_service.GmailService") as G, \
             patch.object(we, "token_storage") as ts:
            G.return_value.send_message.return_value = {"id": "m"}
            G.return_value.draft_message.return_value = {"id": "d"}
            ts.get_token.return_value = None
            with pytest.raises(Exception, match="Gmail authentication"):
                await e._execute_gmail_action("send_email", {}, "c1")
            ts.get_token.return_value = {"access_token": "t"}
            r = await e._execute_gmail_action(
                "send_email", {"to": "a@b.c", "subject": "s", "body": "b"}, "c1")
            assert r["status"] == "success"
            await e._execute_gmail_action("create_draft", {}, "c1")
            r = await e._execute_gmail_action("other", {}, "c1")
            assert "simulated" in r["result"]
            # send failure -> ExternalServiceError
            G.return_value.send_message.return_value = None
            with pytest.raises(Exception, match="Gmail"):
                await e._execute_gmail_action("send_email", {}, "c1")

    async def test_outlook(self):
        e = make_engine()
        tok = patch("core.workflow_engine.token_storage.get_token",
                    return_value={"access_token": "t"})
        with tok, patch("integrations.outlook_service.OutlookService") as O:
            O.return_value.send_email = AsyncMock(return_value={"id": "m"})
            O.return_value.create_calendar_event = AsyncMock(return_value={"id": "e"})
            O.return_value.get_user_emails = AsyncMock(return_value=[])
            O.return_value.get_calendar = AsyncMock(return_value=[])
            r = await e._execute_outlook_action("send_email", {"to_recipients": ["a"]}, "c1")
            assert r["status"] == "success"
            await e._execute_outlook_action("create_event", {"subject": "s"}, "c1")
            await e._execute_outlook_action("get_emails", {}, "c1")
            r = await e._execute_outlook_action("get_calendar", {}, "c1")
            assert r["status"] == "success"
        with patch("core.workflow_engine.token_storage.get_token", return_value=None), \
             patch("integrations.outlook_service.OutlookService"):
            with pytest.raises(ValueError, match="Unknown Outlook action"):
                await e._execute_outlook_action("nope", {}, "c1")

    @pytest.mark.parametrize("svc,cls", [("jira", "JiraService"), ("trello", "TrelloService")])
    async def test_jira_trello(self, svc, cls):
        e = make_engine()
        mod = f"integrations.{svc}_service"
        with patch("core.workflow_engine.token_storage.get_token",
                   return_value={"access_token": "t"}), \
             patch(f"{mod}.{cls}.create_issue", create=True,
                   return_value={"id": 1}) as m:
            r = await getattr(e, f"_execute_{svc}_action")("create_issue", {"p": 1}, "c1")
            assert r["status"] == "success"
            assert m.call_args[1]["token"] == "t"
        with patch("core.workflow_engine.token_storage.get_token", return_value=None):
            with pytest.raises(ValueError, match=f"Unknown {svc.title()} action"):
                await getattr(e, f"_execute_{svc}_action")("nope", {}, "c1")

    async def test_stripe(self):
        e = make_engine()
        if not we.HAS_STRIPE:
            with pytest.raises(Exception, match="not available"):
                await e._execute_stripe_action("x", {}, "c1")
            return
        with patch.object(we, "token_storage") as ts:
            ts.get_token.return_value = None
            r = await e._execute_stripe_action("charge", {}, "c1")
            assert r["status"] == "error"
            ts.get_token.return_value = {"access_token": "t"}
            with patch("integrations.stripe_service.StripeService") as S:
                S.return_value.charge = MagicMock(return_value={"id": "ch"})
                r = await e._execute_stripe_action("charge", {}, "c1")
                assert r["status"] == "success"
                with pytest.raises(ValueError, match="Unknown Stripe action"):
                    await e._execute_stripe_action("nope", {}, "c1")

    async def test_shopify(self):
        e = make_engine()
        S = "integrations.shopify_service.ShopifyService"
        with patch.object(we, "token_storage") as ts, \
             patch(f"{S}.get_order", MagicMock(return_value={"id": 1}), create=True), \
             patch(f"{S}.list_orders", AsyncMock(return_value=[]), create=True):
            ts.get_token.return_value = None
            r = await e._execute_shopify_action("get_order", {}, "c1")
            assert r["status"] == "success"
            with pytest.raises(ValueError, match="Unknown Shopify action"):
                await e._execute_shopify_action("nope", {}, "c1")
            ts.get_token.return_value = {"access_token": "t", "shop_url": "sh"}
            r = await e._execute_shopify_action("list_orders", {}, "c1")
            assert r["status"] == "success"

    @pytest.mark.parametrize("svc,cls,method", [
        ("zoho_crm", "ZohoCRMService", "create_lead"),
        ("zoho_books", "ZohoBooksService", "create_invoice"),
        ("zoho_inventory", "ZohoInventoryService", "create_item"),
    ])
    async def test_zoho(self, svc, cls, method):
        e = make_engine()
        with patch.object(we, "token_storage") as ts, \
             patch(f"integrations.{svc}_service.{cls}.{method}", create=True,
                   new=AsyncMock(return_value={"id": "x"})):
            ts.get_token.return_value = {"access_token": "t", "organization_id": "o"}
            r = await getattr(e, f"_execute_{svc}_action")(method, {}, "c1")
            assert r["status"] == "success"
        with patch.object(we, "token_storage") as ts:
            ts.get_token.return_value = None
            with pytest.raises(ValueError, match="Unknown Zoho"):
                await getattr(e, f"_execute_{svc}_action")("nope", {}, "c1")

    async def test_mcp_action(self):
        e = make_engine()
        with patch("integrations.mcp_service.mcp_service") as ms:
            ms.call_tool = AsyncMock(return_value={"out": 1})
            r = await e._execute_mcp_action("tool1", {"server_id": "s1"}, "c1",
                                            step={"execution_id": "ex", "workspace_id": "w",
                                                  "tenant_id": "t", "tier": "pro"})
            assert r["status"] == "success"
            # missing server_id -> error envelope
            r = await e._execute_mcp_action("tool1", {}, "c1")
            assert r["status"] == "error"
            # exception -> error envelope
            ms.call_tool = AsyncMock(side_effect=RuntimeError("x"))
            r = await e._execute_mcp_action("tool1", {"server_id": "s"}, "c1")
            assert r["status"] == "error"

    async def test_main_agent_action(self):
        e = make_engine()
        with patch.object(e, "_execute_agent_with_mcp",
                          AsyncMock(return_value={"ok": 1})):
            r = await e._execute_main_agent_action("act", {"agent_action": "a"}, "c1")
            assert r["status"] == "success"
        with patch.object(e, "_execute_main_agent_action_inner", create=True), \
             patch.object(e, "_execute_agent_with_mcp",
                          AsyncMock(side_effect=RuntimeError("x"))):
            r = await e._execute_main_agent_action("act", {}, "c1")
            assert r["status"] == "error"
        # mcp_servers branch
        with patch("integrations.mcp_service.mcp_service") as ms, \
             patch.object(e, "_execute_agent_with_mcp",
                          AsyncMock(return_value={"ok": 1})):
            ms.get_active_connections = AsyncMock(
                return_value=[{"server_id": "s1", "connected_at": "now"}])
            ms.get_server_tools = AsyncMock(
                return_value=[{"name": "t", "description": "d", "input_schema": {}}])
            r = await e._execute_main_agent_action(
                "act", {"mcp_servers": ["s1"]}, "c1")
            assert r["status"] == "success"
            assert r["mcp_servers_used"] == ["s1"]

    async def test_agent_with_mcp(self):
        e = make_engine()
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.database.get_db_session") as ms:
            ms.return_value.__enter__.return_value = fake_db
            r = await e._execute_agent_with_mcp({"agent_id": "missing", "action": "a"})
            assert r["success"] is False
        agent = SimpleNamespace(llm_provider="openai", llm_model="gpt")
        fake_db.query.return_value.filter.return_value.first.return_value = agent
        handler = MagicMock()
        handler.chat_completion = AsyncMock(return_value={"content": "done"})
        with patch("core.database.get_db_session") as ms, \
             patch("core.llm_service.get_llm_service",
                   return_value=MagicMock(handler=handler)):
            ms.return_value.__enter__.return_value = fake_db
            r = await e._execute_agent_with_mcp({
                "agent_id": "a1", "action": "x",
                "available_tools": [{"name": "t", "description": "d",
                                     "input_schema": {}}]})
            assert r["execution_method"] == "main_agent_with_mcp"
        handler.chat_completion = AsyncMock(side_effect=RuntimeError("no api"))
        with patch("core.database.get_db_session") as ms, \
             patch("core.llm_service.get_llm_service",
                   return_value=MagicMock(handler=handler)):
            ms.return_value.__enter__.return_value = fake_db
            r = await e._execute_agent_with_mcp({"agent_id": "a1", "action": "x"})
            assert r["execution_method"] == "fallback"
        with patch("core.database.get_db_session", side_effect=RuntimeError("db")):
            with pytest.raises(Exception, match="db"):
                await e._execute_agent_with_mcp({"agent_id": "a"})

    async def test_email_automation(self):
        e = make_engine()
        with patch("core.email_followup_engine.followup_engine.detect_missing_replies",
                   new=AsyncMock(return_value=[])):
            r = await e._execute_email_automation_action("detect_followups", {}, None)
            assert r["status"] == "success"
        r = await e._execute_email_automation_action("draft_nudge", {"subject": "Q3"}, None)
        assert "Q3" in r["draft"]
        r = await e._execute_email_automation_action("nope", {}, None)
        assert r["status"] == "error"

    async def test_workflow_action(self):
        e = make_engine()
        assert (await e._execute_workflow_action("run", {}, None))["status"] == "error"
        with patch.object(e, "_load_workflow_by_id", return_value=None):
            r = await e._execute_workflow_action("run", {"workflow_id": "w1"}, None)
            assert r["status"] == "error"
        wf = {"id": "w1", "steps": []}
        cases = [
            ({"status": "COMPLETED", "outputs": {"o": 1}}, "success"),
            ({"status": "FAILED", "error": "boom"}, "error"),
            ({"status": "CANCELLED"}, "cancelled"),
            ({"status": "PAUSED"}, "paused"),
            (None, "error"),
        ]
        for state, expected in cases:
            e.state_manager.get_execution_state = AsyncMock(return_value=state)
            with patch.object(e, "_load_workflow_by_id", return_value=wf), \
                 patch.object(e, "start_workflow", new=AsyncMock(return_value="ex")):
                r = await e._execute_workflow_action("run", {"workflow_id": "w1"}, None)
            assert r["status"] == expected
        # RUNNING then COMPLETED; timeout; unknown status
        e.state_manager.get_execution_state = AsyncMock(side_effect=[
            {"status": "RUNNING"}, {"status": "COMPLETED", "outputs": {}}])
        with patch.object(e, "_load_workflow_by_id", return_value=wf), \
             patch.object(e, "start_workflow", new=AsyncMock(return_value="ex")):
            assert (await e._execute_workflow_action("run", {"workflow_id": "w1"}, None))["status"] == "success"
        e.state_manager.get_execution_state = AsyncMock(return_value={"status": "RUNNING"})
        with patch.object(e, "_load_workflow_by_id", return_value=wf), \
             patch.object(e, "start_workflow", new=AsyncMock(return_value="ex")):
            r = await e._execute_workflow_action("run", {"workflow_id": "w1", "timeout": 0.001}, None)
            assert r["status"] == "timeout"
        e.state_manager.get_execution_state = AsyncMock(side_effect=[
            {"status": "WEIRD"}, {"status": "COMPLETED", "outputs": {}}])
        with patch.object(e, "_load_workflow_by_id", return_value=wf), \
             patch.object(e, "start_workflow", new=AsyncMock(return_value="ex")):
            assert (await e._execute_workflow_action("run", {"workflow_id": "w1"}, None))["status"] == "success"

    def test_load_workflow_by_id(self, tmp_path, monkeypatch):
        e = make_engine()
        monkeypatch.setattr("core.workflow_engine.os.path.dirname", lambda p: str(tmp_path))
        assert e._load_workflow_by_id("w1") is None
        with open(tmp_path / "workflows.json", "w") as f:
            json.dump([{"id": "w1"}], f)
        assert e._load_workflow_by_id("w1") is not None
        assert e._load_workflow_by_id("zz") is None
        with open(tmp_path / "workflows.json", "w") as f:
            f.write("{bad")
        assert e._load_workflow_by_id("w1") is None

    async def test_goal_management(self):
        e = make_engine()
        with pytest.raises(ValueError, match="Missing title or target_date"):
            await e._execute_goal_management_action("create_goal", {}, None)
        goal = MagicMock()
        goal.dict.return_value = {"id": "g"}
        with patch("core.goal_engine.goal_engine.create_goal_from_text",
                   new=AsyncMock(return_value=goal)):
            r = await e._execute_goal_management_action(
                "create_goal", {"title": "T", "target_date": "2026-08-01T00:00:00Z"}, None)
            assert r == {"id": "g"}
        with patch("core.goal_engine.goal_engine.check_for_escalations",
                   new=AsyncMock(return_value=[])):
            r = await e._execute_goal_management_action("check_escalations", {}, None)
            assert r == {"escalations": []}
        with patch("core.goal_engine.goal_engine.goals", {}):
            with pytest.raises(ValueError, match="not found"):
                await e._execute_goal_management_action(
                    "update_subtask", {"goal_id": "g1"}, None)
        st = SimpleNamespace(id="st1", status="todo")
        g = SimpleNamespace(id="g1", sub_tasks=[st])
        g.dict = lambda: {"id": "g1"}
        with patch("core.goal_engine.goal_engine.goals", {"g1": g}), \
             patch("core.goal_engine.goal_engine.update_goal_progress", new=AsyncMock()):
            r = await e._execute_goal_management_action(
                "update_subtask",
                {"goal_id": "g1", "sub_task_id": "st1", "status": "done"}, None)
            assert st.status == "done"
        with pytest.raises(ValueError, match="Unknown goal_management"):
            await e._execute_goal_management_action("nope", {}, None)


class TestGenericExecutor:
    def _patches(self, catalog=None, cached=None):
        cache_obj = patch.object(we, "cache", MagicMock())
        # we.cache doesn't exist; patch via module attribute set
        import core.cache as cache_mod
        cache_mod.cache.get = MagicMock(return_value=cached)
        cache_mod.cache.set = MagicMock()
        return cache_obj

    async def test_generic_flow(self):
        e = make_engine()
        import core.cache as cache_mod
        item = SimpleNamespace(
            id="svc",
            actions=[{"name": "get_x", "method": "GET", "url": "https://x/{id}"},
                     {"name": "post_x", "method": "POST", "url": "https://x"},
                     {"name": "no_url", "method": "GET"},
                     {"name": "other"}],
        )
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = item
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"ok": True}
        cache_mod.cache.get = MagicMock(return_value=None)
        cache_mod.cache.set = MagicMock()
        with patch("core.workflow_engine.get_db_session") as ms, \
             patch("core.workflow_engine.httpx.AsyncClient") as mc, \
             patch("core.workflow_engine.token_storage") as ts:
            ts.get_token.return_value = {"access_token": "tok"}
            ms.return_value.__enter__.return_value = fake_db
            mc.return_value.__aenter__.return_value.request = AsyncMock(return_value=resp)
            r = await e._execute_generic_action("svc", "get_x", {"id": "42"}, "c1")
            assert r == {"ok": True}
            hdrs = mc.return_value.__aenter__.return_value.request.call_args[1]["headers"]
            assert hdrs["Authorization"] == "Bearer tok"
            r = await e._execute_generic_action("svc", "post_x", {"a": 1}, None)
            assert r == {"ok": True}
            # action missing / no url / missing path param
            with pytest.raises(ValueError, match="not found in catalog"):
                await e._execute_generic_action("svc", "missing", {}, None)
            with pytest.raises(ValueError, match="No URL/path"):
                await e._execute_generic_action("svc", "no_url", {}, None)
            with pytest.raises(ValueError, match="Missing path parameter"):
                await e._execute_generic_action("svc", "get_x", {}, None)
        # cached catalog
        cache_mod.cache.get = MagicMock(
            return_value={"id": "svc", "actions": [{"name": "ping", "method": "GET",
                                                    "url": "https://x/p"}]})
        with patch("core.workflow_engine.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.request = AsyncMock(return_value=resp)
            r = await e._execute_generic_action("svc", "ping", {}, None)
            assert r == {"ok": True}
        # catalog item not found / db error
        fake_db.query.return_value.filter.return_value.first.return_value = None
        cache_mod.cache.get = MagicMock(return_value=None)
        with patch("core.workflow_engine.get_db_session") as ms:
            ms.return_value.__enter__.return_value = fake_db
            with pytest.raises(ValueError, match="not found in Integration Catalog"):
                await e._execute_generic_action("ghost", "x", {}, None)
        with patch("core.workflow_engine.get_db_session", side_effect=RuntimeError("db")):
            with pytest.raises(RuntimeError, match="db"):
                await e._execute_generic_action("svc", "x", {}, None)


# ---------------------------------------------------------------------------
# Run-level orchestration
# ---------------------------------------------------------------------------

def _env(states):
    sm = MagicMock()
    if isinstance(states, list):
        def _next():
            yield from states
        gen = _next()

        def side_effect(*a, **k):
            try:
                return next(gen)
            except StopIteration:
                return states[-1]
        sm.get_execution_state = AsyncMock(side_effect=side_effect)
    else:
        sm.get_execution_state = AsyncMock(return_value=states)
    sm.update_execution_status = AsyncMock()
    sm.update_step_status = AsyncMock()
    sm.update_execution_inputs = AsyncMock()
    sm.create_execution = AsyncMock(return_value="ex-1")
    ws = MagicMock()
    ws.notify_workflow_status = AsyncMock()
    return sm, ws, MagicMock()


@contextmanager
def _run_env(ws, analytics, db=None, governance=None):
    db = db or MagicMock()
    db_cm = MagicMock()
    db_cm.__enter__.return_value = db
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value=governance if governance is not None
        else {"allowed": True, "reason": "ok"})
    ServiceFactory = MagicMock()
    ServiceFactory.get_governance_service.return_value = gov
    notifier = MagicMock()
    notifier.notify_completion = AsyncMock()
    notifier.notify_failure = AsyncMock()
    with patch("core.workflow_engine.get_connection_manager", return_value=ws), \
         patch("core.analytics_engine.get_analytics_engine", return_value=analytics), \
         patch("core.workflow_engine.get_db_session", return_value=db_cm), \
         patch.object(we, "ServiceFactory", ServiceFactory), \
         patch.object(we, "notifier", notifier):
        yield db


class TestStartResumeCancel:
    async def test_start_workflow_background_and_tasks(self):
        e = make_engine()
        e.state_manager.create_execution = AsyncMock(return_value="ex-1")
        wf = {"id": "w1", "steps": [step_dict()]}
        bt = MagicMock()
        with patch.object(e, "_run_execution", AsyncMock()) as run:
            eid = await e.start_workflow(wf, {}, background_tasks=bt)
            bt.add_task.assert_called_once()
            assert eid == "ex-1"
            # graph + workflow_id normalization, no background_tasks
            wf2 = {"workflow_id": "w2", "nodes": [{"id": "n1", "config": {}}]}
            await e.start_workflow(wf2, {})
            await asyncio.sleep(0)  # let created task start
            assert run.await_count == 2
            await asyncio.sleep(0)
            e._background_tasks.clear()

    async def test_resume(self):
        e = make_engine()
        e.state_manager.get_execution_state = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await e.resume_workflow("ex", {}, {})
        e.state_manager.get_execution_state = AsyncMock(return_value={"status": "RUNNING"})
        assert await e.resume_workflow("ex", {}, {}) is False
        e.state_manager.get_execution_state = AsyncMock(return_value={"status": "PAUSED"})
        e.state_manager.update_execution_status = AsyncMock()
        e.state_manager.update_execution_inputs = AsyncMock()
        with patch.object(e, "_run_execution", AsyncMock()):
            assert await e.resume_workflow("ex", {}, {"x": 1}) is True
        await asyncio.sleep(0)
        e._background_tasks.clear()

    async def test_cancel_execution(self):
        e = make_engine()
        e.state_manager.update_execution_status = AsyncMock()
        ws = MagicMock()
        ws.notify_workflow_status = AsyncMock()
        with patch("core.workflow_engine.get_connection_manager", return_value=ws):
            assert await e.cancel_execution("ex-9") is True
        assert "ex-9" in e.cancellation_requests
        e.cancellation_requests.discard("ex-9")

    async def test_get_workflow_engine_singleton(self):
        we._workflow_engine = None
        e1 = get_workflow_engine()
        assert get_workflow_engine() is e1
        we._workflow_engine = None


class TestRunExecution:
    async def test_success_linear(self):
        e = make_engine()
        states = [
            {"steps": {}, "input_data": {}, "outputs": {}},
            {"steps": {"s1": {"status": "COMPLETED"}}, "input_data": {}, "outputs": {}},
        ]
        sm, ws, analytics = _env(states)
        e.state_manager = sm
        with _run_env(ws, analytics):
            await e._run_execution("ex-1", {"id": "w1", "steps": [step_dict()]})
        assert any(c.args[1] == "COMPLETED"
                   for c in sm.update_execution_status.call_args_list)

    async def test_condition_skip_and_dep_skip(self):
        e = make_engine()
        state = {"steps": {}, "input_data": {"flag": False}, "outputs": {}}
        sm, ws, analytics = _env([state])
        e.state_manager = sm
        with _run_env(ws, analytics):
            await e._run_execution("ex-1", {"id": "w1", "steps": [
                step_dict(id="s1", condition="${input.flag} == true"),
                step_dict(id="s2", depends_on=["s1"]),
            ]})
        assert any(c.args[2] == "SKIPPED" for c in sm.update_step_status.call_args_list)

    async def test_missing_input_pauses(self):
        e = make_engine()
        sm, ws, analytics = _env([{"steps": {}, "input_data": {}, "outputs": {}}])
        e.state_manager = sm
        with _run_env(ws, analytics):
            await e._run_execution("ex-1", {"id": "w1", "steps": [
                step_dict(parameters={"x": "${input.missing_var}"})]})
        assert any(c.args[1] == "PAUSED" for c in sm.update_execution_status.call_args_list)

    async def test_cancellation(self):
        e = make_engine()
        sm, ws, analytics = _env([{"steps": {}, "input_data": {}, "outputs": {}}])
        e.state_manager = sm
        e.cancellation_requests.add("ex-1")
        with _run_env(ws, analytics):
            await e._run_execution("ex-1", {"id": "w1", "steps": [step_dict()]})
        assert any(c.args[1] == "CANCELLED" for c in sm.update_execution_status.call_args_list)
        assert "ex-1" not in e.cancellation_requests

    async def test_step_failure_and_continue_on_error(self):
        e = make_engine()
        sm, ws, analytics = _env([{"steps": {}, "input_data": {}, "outputs": {}}])
        e.state_manager = sm
        with _run_env(ws, analytics), \
             patch.object(e, "_execute_step", AsyncMock(side_effect=RuntimeError("boom"))):
            await e._run_execution("ex-1", {"id": "w1", "steps": [step_dict()]})
        assert any(c.args[1] == "FAILED" for c in sm.update_execution_status.call_args_list)
        # continue_on_error -> PARTIAL
        sm2, ws2, an2 = _env([{"steps": {}, "input_data": {}, "outputs": {}}])
        e.state_manager = sm2
        with _run_env(ws2, an2), \
             patch.object(e, "_execute_step", AsyncMock(side_effect=RuntimeError("boom"))):
            await e._run_execution("ex-1", {"id": "w1", "steps": [
                step_dict(continue_on_error=True)]})
        assert any(c.args[1] == "PARTIAL" for c in sm2.update_execution_status.call_args_list)

    async def test_error_status_envelope_fails_step(self):
        e = make_engine()
        sm, ws, analytics = _env([{"steps": {}, "input_data": {}, "outputs": {}}])
        e.state_manager = sm
        with _run_env(ws, analytics), \
             patch.object(e, "_execute_step",
                          AsyncMock(return_value={"status": "error", "error": "bad"})):
            await e._run_execution("ex-1", {"id": "w1", "steps": [step_dict()]})
        assert any(c.args[2] == "FAILED" for c in sm.update_step_status.call_args_list)

    async def test_governance_denied(self):
        e = make_engine()
        sm, ws, analytics = _env([{"steps": {}, "input_data": {}, "outputs": {}}])
        e.state_manager = sm
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = object()
        with _run_env(ws, analytics, db=db,
                      governance={"allowed": False, "reason": "quota"}):
            await e._run_execution("ex-1", {"id": "w1", "agent_id": "ag1",
                                            "steps": [step_dict()]})
        assert any(c.args[1] == "FAILED" and "Governance" in str(c.args)
                   for c in sm.update_execution_status.call_args_list)

    async def test_outer_exception(self):
        e = make_engine()
        sm, ws, analytics = _env([])
        e.state_manager = sm
        sm.update_execution_status = AsyncMock(side_effect=[None, RuntimeError("db")])
        with _run_env(ws, analytics):
            await e._run_execution("ex-1", {"id": "w1", "steps": []})
        ws.notify_workflow_status.assert_awaited()

    async def test_completed_step_skipped_and_marketplace(self):
        e = make_engine()
        sm, ws, analytics = _env([{"steps": {"s1": {"status": "COMPLETED"}},
                                   "input_data": {}, "outputs": {}}])
        e.state_manager = sm
        with _run_env(ws, analytics), \
             patch.object(e, "_execute_step", AsyncMock()) as ex, \
             patch.object(we, "MarketplaceUsageTracker") as mu:
            await e._run_execution("ex-1", {"id": "w1", "created_from_template": "tpl",
                                            "steps": [step_dict()]})
        assert ex.await_count == 0
        mu.track_usage.assert_called_once()
        # failure path marketplace tracking
        sm2, ws2, an2 = _env([{"steps": {}, "input_data": {}, "outputs": {}}])
        e.state_manager = sm2
        with _run_env(ws2, an2), \
             patch.object(e, "_execute_step", AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(we, "MarketplaceUsageTracker") as mu2:
            await e._run_execution("ex-1", {"id": "w1", "created_from_template": "tpl",
                                            "steps": [step_dict()]})
        mu2.track_usage.assert_called_once()


class TestGraphExecution:
    def _wf(self):
        return {
            "id": "w1", "name": "G",
            "nodes": [{"id": "a", "title": "A",
                       "config": {"service": "email", "action": "send"}},
                      {"id": "b", "title": "B",
                       "config": {"service": "email", "action": "send"}}],
            "connections": [{"source": "a", "target": "b"}],
        }

    async def _run(self, states, wf=None, execute=None, continue_on_error=False):
        e = make_engine()
        sm, ws, analytics = _env(states)
        e.state_manager = sm
        wf = wf or self._wf()
        if continue_on_error:
            for n in wf["nodes"]:
                n["config"]["continue_on_error"] = True
        ex = execute if execute is not None else AsyncMock(
            return_value={"status": "success", "result": {"id": "r1"}})
        with _run_env(ws, analytics), patch.object(e, "_execute_step", ex):
            await e._execute_workflow_graph(
                "ex-1", wf, states[0], ws, "u1", datetime.now(timezone.utc))
        return e, sm, ws

    async def test_success(self):
        running = {"status": "RUNNING", "steps": {}, "input_data": {}, "outputs": {}}
        _, sm, ws = await self._run([running] * 12)
        assert any(c.args[1] == "COMPLETED" for c in sm.update_execution_status.call_args_list)

    async def test_step_failure_fails_workflow(self):
        running = {"status": "RUNNING", "steps": {}, "input_data": {}, "outputs": {}}
        _, sm, ws = await self._run(
            [running] * 8, execute=AsyncMock(side_effect=RuntimeError("boom")))
        assert any(c.args[1] == "FAILED" for c in sm.update_execution_status.call_args_list)

    async def test_continue_on_error_activates_downstream(self):
        running = {"status": "RUNNING", "steps": {}, "input_data": {}, "outputs": {}}
        _, sm, ws = await self._run(
            [running] * 12, execute=AsyncMock(side_effect=RuntimeError("boom")),
            continue_on_error=True)
        assert any(c.args[1] == "FAILED" for c in sm.update_execution_status.call_args_list)

    async def test_paused_workflow(self):
        states = [{"status": "RUNNING", "steps": {}, "input_data": {}, "outputs": {}},
                  {"status": "PAUSED", "steps": {}, "input_data": {}, "outputs": {}}]
        e, sm, ws = await self._run(states)
        # paused returns early — no COMPLETED status call
        assert not any(c.args[1] == "COMPLETED"
                       for c in sm.update_execution_status.call_args_list)

    async def test_partial_when_conditions_unmet(self):
        wf = self._wf()
        wf["connections"] = [{"source": "a", "target": "b",
                              "condition": "${input.flag} == true"}]
        running = {"status": "RUNNING", "steps": {}, "input_data": {"flag": False},
                   "outputs": {}}
        _, sm, ws = await self._run([running] * 6, wf=wf)
        assert any(c.args[1] == "PARTIAL" for c in sm.update_execution_status.call_args_list)

    async def test_resume_with_completed_step(self):
        states = [{"status": "RUNNING",
                   "steps": {"a": {"status": "COMPLETED"}, "b": {"status": "PENDING"}},
                   "input_data": {}, "outputs": {}}] + \
                 [{"status": "RUNNING",
                   "steps": {"a": {"status": "COMPLETED"}, "b": {"status": "COMPLETED"}},
                   "input_data": {}, "outputs": {}}] * 8
        _, sm, ws = await self._run(states)
        assert any(c.args[1] == "COMPLETED" for c in sm.update_execution_status.call_args_list)

    async def test_cancelled(self):
        e = make_engine()
        sm, ws, analytics = _env([{"status": "RUNNING", "steps": {},
                                   "input_data": {}, "outputs": {}}])
        e.state_manager = sm
        e.cancellation_requests.add("ex-1")
        with _run_env(ws, analytics):
            await e._execute_workflow_graph(
                "ex-1", self._wf(), {"steps": {}}, ws, "u1",
                datetime.now(timezone.utc))
        assert any(c.args[1] == "CANCELLED"
                   for c in sm.update_execution_status.call_args_list)


class TestArborRefinement:
    async def test_arbor_success_and_failure(self):
        e = make_engine()
        node = SimpleNamespace(
            id="n1", status=None, promise_score=0.0,
            metrics=SimpleNamespace(execution_time_ms=0.0),
            calculate_promise_score=lambda: 1.2)
        tree = MagicMock()
        tree.get_path_to_root.return_value = ["n1"]
        tree.get_domain_statistics.return_value = {}
        with patch("core.hypothesis_tree.OptimizationTree", return_value=tree), \
             patch("core.hypothesis_tree.WorkflowHypothesisNode", return_value=node), \
             patch("core.hypothesis_tree.NodeMetrics", return_value=MagicMock()), \
             patch("core.hypothesis_tree_endpoints._persist_tree") as pt, \
             patch.object(e, "start_workflow", AsyncMock(return_value="ex-1")):
            e.state_manager.get_execution_state = AsyncMock(
                return_value={"status": "COMPLETED"})
            r = await e.run_workflow_with_arbor_refinement("t1", {"name": "W"}, {})
            assert r["success"] is True
            pt.assert_called_once()
            # failure prune
            e.state_manager.get_execution_state = AsyncMock(
                return_value={"status": "FAILED", "error": "x"})
            r = await e.run_workflow_with_arbor_refinement("t1", {"name": "W"}, {})
            assert r["success"] is False
            tree.prune_branch.assert_called()
            # exception prune + reraise
            with patch.object(e, "start_workflow",
                              AsyncMock(side_effect=RuntimeError("boom"))):
                with pytest.raises(RuntimeError):
                    await e.run_workflow_with_arbor_refinement("t1", {"name": "W"}, {})


# ============================================================================
# Ingestion pipeline
# ============================================================================

class _FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model

    def filter(self, *a, **k):
        return self

    def filter_by(self, **k):
        return self

    def first(self):
        mapping = {
            IngestionJob: self.session.job,
            DocumentIngestion: self.session.existing_doc,
            UserConnection: self.session.user_conn,
            Tenant: self.session.tenant,
        }
        return mapping.get(self.model)


class FakeSession:
    bind = None

    def __init__(self, job=None, existing_doc=None, user_conn=None, tenant=None):
        self.job = job
        self.existing_doc = existing_doc
        self.user_conn = user_conn
        self.tenant = tenant
        self.added = []
        self.committed = 0
        self.rolled_back = 0
        self.closed = 0

    def query(self, model):
        return _FakeQuery(self, model)

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def flush(self):
        pass

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed += 1

    def execute(self, *a, **k):
        return MagicMock()


@pytest.fixture
def pipeline(monkeypatch):
    fake_lancedb = MagicMock()
    fake_graphrag = MagicMock()
    fake_usage = MagicMock()
    fake_extractor = MagicMock()
    fake_schema = MagicMock()
    fake_linker = MagicMock()
    fake_meta = MagicMock()
    fake_llm = MagicMock()
    fake_registry = MagicMock()

    monkeypatch.setattr(ip, "LanceDBHandler", lambda *a, **k: fake_lancedb)
    monkeypatch.setattr(ip, "GraphRAGEngine", lambda *a, **k: fake_graphrag)
    monkeypatch.setattr(ip, "MultiEntityLLMExtractor", lambda *a, **k: fake_extractor)
    monkeypatch.setattr(ip, "SchemaDiscoveryService", lambda *a, **k: fake_schema)
    monkeypatch.setattr(ip, "EntityLinkingService", lambda *a, **k: fake_linker)
    monkeypatch.setattr("core.meta_agent_orchestrator.MetaAgentOrchestrator",
                        lambda *a, **k: fake_meta)
    monkeypatch.setattr(ip, "UsageTrackingService", lambda *a, **k: fake_usage)
    monkeypatch.setattr("core.llm_service.LLMService", lambda **k: fake_llm)

    session = FakeSession()
    monkeypatch.setattr(ip, "SessionLocal", lambda: session)

    svc = IngestionPipelineService(tenant_id="t1", workspace_id="ws1")
    svc.integration_registry = fake_registry

    fake_usage.track_acu_usage = AsyncMock(return_value=MagicMock(id="usage-1"))
    fake_usage.calculate_acu_consumed = MagicMock(return_value=1.5)
    fake_usage.check_quota_before_job = AsyncMock(
        return_value={"allowed": True, "remaining_quota": 10})
    fake_graphrag.ingest_structured_data = MagicMock()
    fake_graphrag.ingest_document = AsyncMock()
    return {"svc": svc, "session": session, "lancedb": fake_lancedb,
            "graphrag": fake_graphrag, "usage": fake_usage,
            "extractor": fake_extractor, "schema": fake_schema,
            "linker": fake_linker, "meta": fake_meta, "llm": fake_llm,
            "registry": fake_registry}


def make_record(text=LONG_TEXT):
    return {"id": "r1", "type": "slack_message", "text": text,
            "channel": "C1", "user": "U1"}


class TestSyncAndIngest:
    async def test_no_config(self, pipeline):
        r = await pipeline["svc"].sync_and_ingest("made_up")
        assert r["success"] is False

    async def test_no_records(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"])
        with patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(return_value=[])):
            r = await svc.sync_and_ingest("salesforce")
        assert r["success"] is True and r["records_fetched"] == 0

    async def test_full_success_and_idempotency_skip(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"])
        record = {"id": "c1", "type": "contact", "name": "Alice",
                  "email": "a@b.c", "company": "Acme", "text": LONG_TEXT}
        with patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(return_value=[record])), \
             patch.object(svc, "_process_multi_entity_extraction",
                          new=AsyncMock(return_value=2)), \
             patch.object(svc, "_run_schema_discovery", new=AsyncMock()):
            r = await svc.sync_and_ingest("salesforce")
        assert r["success"] is True
        assert r["entities_extracted"] == 1
        assert r["relationships_extracted"] == 1
        # second run with matching hash -> deduped
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text(
            svc._record_to_text(record, "salesforce"))
        pipeline["session"].existing_doc = existing
        with patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(return_value=[record])), \
             patch.object(svc, "_run_schema_discovery", new=AsyncMock()):
            r2 = await svc.sync_and_ingest("salesforce")
        assert r2["records_processed"] == 1
        assert r2["entities_extracted"] == 0

    async def test_record_error_and_global_error(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"])
        svc._record_to_text = MagicMock(side_effect=Exception("boom"))
        with patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(return_value=[make_record()])):
            r = await svc.sync_and_ingest("salesforce")
        assert r["success"] is True and len(r["errors"]) == 1
        svc._record_to_text = MagicMock(return_value=LONG_TEXT)
        with patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(side_effect=Exception("fetch fail"))):
            r = await svc.sync_and_ingest("salesforce")
        assert r["success"] is False

    async def test_usage_failure_tolerated(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"])
        pipeline["usage"].track_acu_usage = AsyncMock(side_effect=Exception("u"))
        with patch.object(svc, "_fetch_integration_data",
                          new=AsyncMock(return_value=[make_record()])), \
             patch.object(svc, "_run_schema_discovery", new=AsyncMock()):
            r = await svc.sync_and_ingest("salesforce")
        assert r["success"] is True
        assert "usage_tracking_error" in r


class TestPipelineHelpers:
    def test_extract_structured_entities(self, pipeline):
        record = {"id": "c1", "type": "contact", "name": "Alice", "email": "a@b.c",
                  "company": "Acme", "stage": "won", "amount": 100,
                  "subject": "Subj", "summary": "Sum"}
        entity, rel = pipeline["svc"]._extract_structured_entities(
            record, "salesforce", "text")
        assert entity["name"] == "Alice"
        assert entity["properties"]["summary"] == "Sum"
        assert rel["type"] == "synced_from"
        e2, _ = pipeline["svc"]._extract_structured_entities(
            {"id": 42, "type": "thing"}, "x", "text")
        assert e2["name"] == "thing_42"

    def test_doc_ingestion_and_checks(self, pipeline):
        svc = pipeline["svc"]
        svc._record_doc_ingestion("ws1", "d1", "text", "src")
        assert pipeline["session"].committed >= 1
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text("text")
        pipeline["session"].existing_doc = existing
        assert svc._is_doc_already_ingested("ws1", "d1", "text") is True
        assert svc._is_doc_already_ingested("ws1", "d1", "other") is False
        pipeline["session"].existing_doc = None
        assert svc._is_doc_already_ingested("ws1", "d1", "text") is False
        pipeline["session"].add = MagicMock(side_effect=Exception("x"))
        svc._record_doc_ingestion("ws1", "d1", "text", "src")
        assert pipeline["session"].rolled_back >= 1

    def test_get_user_credentials(self, pipeline):
        svc = pipeline["svc"]
        conn = MagicMock(id="conn-1", integration_id="slack", user_id="u1",
                         expires_at=datetime.now(timezone.utc))
        pipeline["session"].user_conn = conn
        assert svc._get_user_credentials("slack", "u1")["connection_id"] == "conn-1"
        pipeline["session"].user_conn = None
        assert svc._get_user_credentials("slack", "u1") is None
        pipeline["session"].query = MagicMock(side_effect=Exception("x"))
        assert svc._get_user_credentials("slack", "u1") is None

    def test_job_create_update(self, pipeline):
        svc = pipeline["svc"]
        job_id = svc._create_ingestion_job("slack", "manual", "conn-1")
        assert not job_id.startswith("fallback-")
        job = MagicMock()
        pipeline["session"].job = job
        assert svc._update_ingestion_job(
            "job-1", "completed", completed_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc), records_fetched=1,
            records_processed=1, entities_extracted=2,
            relationships_extracted=3, error_message="e",
            error_details={"x": 1}) is True
        pipeline["session"].job = None
        assert svc._update_ingestion_job("job-1", "failed") is False
        pipeline["session"].add = MagicMock(side_effect=Exception("x"))
        assert svc._create_ingestion_job("slack", "manual").startswith("fallback-")
        pipeline["session"].commit = MagicMock(side_effect=Exception("x"))
        assert svc._update_ingestion_job("job-1", "running") is False

    def test_acu_and_core_type(self, pipeline):
        svc = pipeline["svc"]
        assert svc._calculate_acu_consumed(1, 100, 1000) == 1.5
        svc._is_core_entity_type("Organization") in (True, False)  # smoke
        assert isinstance(svc._is_core_entity_type("zzz_unknown"), bool)

    async def test_process_extracted_entities(self, pipeline):
        svc = pipeline["svc"]
        svc.db = MagicMock()
        out = await svc._process_extracted_entities(
            [{"type": "Company", "properties": {"a": 1}, "confidence": 0.9}],
            {"id": "r1", "type": "email"})
        assert len(out) == 1
        svc.db.add_all.assert_called_once()

    async def test_run_schema_discovery(self, pipeline):
        svc = pipeline["svc"]
        pipeline["schema"].discover_schemas_from_entities = AsyncMock(return_value=[])
        pipeline["linker"].link_entities_to_graph = AsyncMock(return_value=[])
        pipeline["meta"].orchestrate_ontology_management = AsyncMock()
        results = {"entities_extracted": 0}
        await svc._run_schema_discovery(results)
        # linked nodes counted
        pipeline["linker"].link_entities_to_graph = AsyncMock(return_value=[object()])
        await svc._run_schema_discovery(results)
        assert results["entities_extracted"] == 1
        # orchestrator error swallowed; discovery failure swallowed
        pipeline["meta"].orchestrate_ontology_management = AsyncMock(
            side_effect=RuntimeError("x"))
        pipeline["schema"].discover_schemas_from_entities = AsyncMock(
            side_effect=RuntimeError("y"))
        await svc._run_schema_discovery(results)


class TestMultiEntityExtraction:
    async def test_extract_success_and_failure(self, pipeline):
        svc = pipeline["svc"]
        ex = pipeline["extractor"]
        ex.llm = MagicMock()
        ex.llm.generate = AsyncMock(return_value='{"entities": []}')
        ex._build_extraction_prompt = MagicMock(return_value="p")
        ent = MagicMock()
        ex._parse_llm_response = MagicMock(return_value=[ent])
        out = await svc._extract_multi_entity_only(
            {"id": "r1"}, "gmail", LONG_TEXT, "job1")
        assert out == [ent]
        # all attempts fail (generate raises)
        ex.llm.generate = AsyncMock(side_effect=RuntimeError("llm down"))
        assert await svc._extract_multi_entity_only(
            {"id": "r1"}, "gmail", LONG_TEXT, "job1") == []
        # empty responses -> []
        ex.llm.generate = AsyncMock(return_value="   ")
        assert await svc._extract_multi_entity_only(
            {"id": "r1"}, "gmail", LONG_TEXT, "job1") == []

    async def test_process_persists(self, pipeline):
        svc = pipeline["svc"]
        svc.db = MagicMock()
        with patch.object(svc, "_extract_multi_entity_only",
                          new=AsyncMock(return_value=[MagicMock()])):
            assert await svc._process_multi_entity_extraction(
                {"id": "r1"}, "gmail", LONG_TEXT, "j") == 1
        # db None -> SessionLocal path
        svc.db = None
        with patch.object(svc, "_extract_multi_entity_only",
                          new=AsyncMock(return_value=[MagicMock()])), \
             patch("core.database.SessionLocal", return_value=FakeSession()):
            assert await svc._process_multi_entity_extraction(
                {"id": "r1"}, "gmail", LONG_TEXT, "j") == 1
        with patch.object(svc, "_extract_multi_entity_only",
                          new=AsyncMock(return_value=[])):
            assert await svc._process_multi_entity_extraction(
                {"id": "r1"}, "gmail", LONG_TEXT, "j") == 0


class TestWebhookProcessing:
    async def test_no_records(self, pipeline):
        svc = pipeline["svc"]
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[])):
            r = await svc.process_webhook_payload("slack", {})
        assert r["success"] is True

    async def test_full_webhook_flow(self, pipeline):
        svc = pipeline["svc"]
        record = {"id": "r1", "type": "slack_message", "text": LONG_TEXT,
                  "timestamp": "now"}
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[record])), \
             patch.object(svc, "_prepare_record_text_async",
                          new=AsyncMock(return_value=LONG_TEXT)), \
             patch("core.lancedb_handler.LanceDBHandler") as LH, \
             patch.object(svc, "_process_multi_entity_extraction",
                          new=AsyncMock(return_value=2)):
            r = await svc.process_webhook_payload("slack", {}, "conn-1")
        assert r["success"] is True
        assert r["records_processed"] == 1
        assert r["entities_extracted"] == 3  # 1 structured + 2 multi
        LH.assert_called()
        # usage failure tolerated
        pipeline["usage"].track_acu_usage = AsyncMock(side_effect=Exception("u"))
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[])):
            r = await svc.process_webhook_payload("slack", {})
        assert r["success"] is True

    async def test_webhook_record_error_and_outer(self, pipeline):
        svc = pipeline["svc"]
        record = {"id": "r1", "type": "email", "text": LONG_TEXT,
                  "body": {"html": "x"}, "bodyPreview": "p"}
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[record])), \
             patch.object(svc, "_prepare_record_text_async",
                          new=AsyncMock(side_effect=RuntimeError("per-record"))):
            r = await svc.process_webhook_payload("outlook", {})
        assert r["errors"]
        # outer failure
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(side_effect=RuntimeError("transform"))):
            r = await svc.process_webhook_payload("slack", {})
        assert "error" in r

    async def test_tiered_basic_and_deep(self, pipeline):
        svc = pipeline["svc"]
        record = {"id": "r1", "type": "slack_message", "text": LONG_TEXT}
        pipeline["session"].tenant = None  # free plan -> skip LLM tier
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[record])):
            r = await svc.process_webhook_payload_tiered("slack", {})
        assert r["success"] is True
        assert r["tier"] == "deep"
        assert r["entities_extracted"] == 1
        # dedupe: record already ingested
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text(
            svc._record_to_text(record, "slack"))
        pipeline["session"].existing_doc = existing
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[record])):
            r = await svc.process_webhook_payload_tiered("slack", {})
        assert r["entities_extracted"] == 0
        assert r["tier"] == "basic"

    async def test_tiered_comm_pipeline_and_llm_tier(self, pipeline):
        svc = pipeline["svc"]
        record = {"id": "r1", "type": "email", "subject": "s", "content": LONG_TEXT}
        tenant = MagicMock(plan_type="team")
        pipeline["session"].tenant = tenant
        cp = MagicMock()
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[record])), \
             patch("integrations.atom_communication_ingestion_pipeline."
                   "get_ingestion_pipeline", return_value=cp):
            r = await svc.process_webhook_payload_tiered("outlook", {})
        assert r["success"] is True
        cp.ingest_message.assert_called_once()
        # bridge failure -> falls through to standard indexing
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[record])), \
             patch("integrations.atom_communication_ingestion_pipeline."
                   "get_ingestion_pipeline", side_effect=ImportError("x")):
            r = await svc.process_webhook_payload_tiered("outlook", {})
        assert r["success"] is True
        # no records
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(return_value=[])):
            r = await svc.process_webhook_payload_tiered("slack", {})
        assert r["success"] is True
        # outer error
        with patch.object(svc, "_transform_webhook_payload",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc.process_webhook_payload_tiered("slack", {})
        assert "error" in r


class TestTransformers:
    TRANSFORM_PAYLOADS = [
        ("slack", {"type": "event_callback", "team_id": "T",
                   "event": {"type": "message", "client_msg_id": "m1",
                             "text": "hi", "channel": "c", "user": "u", "ts": "1"}}),
        ("hubspot", [{"subscriptionType": "contact.creation",
                      "objectId": "1", "properties": {"a": 1}}]),
        ("salesforce", {"eventType": "e", "objectType": "Account",
                        "recordIds": ["a1"],
                        "changeEventHeader": {"changeTypes": ["UPDATE"]},
                        "payload": {"x": 1}}),
        ("notion", {"activity_type": "page", "id": "p", "title": "T",
                    "properties": {"k": 1}}),
        ("zoho_crm", {"module": {"api_name": "Leads"}, "key_id": "k1",
                      "data": {"a": 1}, "operation": "create"}),
        ("zoho_books", {"module": "Invoices", "IDs": {"entity_id": "e1"},
                        "payload": {}, "event_type": "create"}),
        ("zoho_projects", {"project_id": "p1", "module": "Tasks", "id": "t1",
                           "data": {}, "operation": "op"}),
        ("zoho_desk", {"ticketId": "t1", "ticket": {"s": 1}, "action": "a"}),
        ("zoho_recruit", {"module": "Candidates", "entityId": "e1",
                          "data": {}, "operation": "op"}),
        ("zoho_campaigns", {"campaign_id": "c1", "data": {}, "event_type": "e"}),
        ("zoho_forms", {"submission_id": "s1", "data": {}, "event_type": "e"}),
        ("zoho_showtime", {"session_id": "s1", "data": {}, "event_type": "e"}),
        ("zoho_meeting", {"meeting_id": "m1", "data": {}, "event_type": "e"}),
        ("zoho_assist", {"session_id": "s1", "data": {}, "event_type": "e"}),
        ("jira", {"issue": {"id": "i", "key": "K",
                            "fields": {"summary": "s", "status": {"name": "Open"},
                                       "assignee": {"displayName": "D"}}},
                  "webhookEvent": "created"}),
        ("asana", {"gid": "g1", "name": "task", "completed": False, "action": "a"}),
        ("trello", {"action": {"type": "card", "data": {
            "card": {"id": "c1", "name": "C"},
            "listAfter": {"id": "l1"}}}}),
        ("monday", {"event": {"type": "t"},
                    "payload": {"item_id": "i", "item_name": "N",
                                "board_id": "b", "column_values": {}}}),
        ("clickup", {"task": {"id": "t", "name": "T", "status": "open"},
                     "event": "e"}),
        ("linear", {"data": {"id": "i", "title": "T", "state": {"name": "S"}},
                    "action": "create"}),
        ("pipedrive", {"object": "deal", "current": {"id": "d", "title": "D",
                                                     "value": 1}, "event": "e"}),
        ("zendesk_sell", {"target_type": "lead", "target_id": "t", "payload": "p",
                          "trigger": "tr"}),
        ("insightly", {"object_name": "Contact", "record_id": "r", "data": {},
                       "event": "e"}),
        ("freshsales", {"entity_type": "deal", "payload": {"id": "d"},
                        "action": "a"}),
        ("salesloft", {"data": {"id": "d", "name": "N"},
                       "event": {"action": "a"}}),
        ("mailchimp", {"type": "Subscribe",
                       "data": {"id": "d", "email": "a@b.c"}}),
        ("activecampaign", {"contact": {"id": "c", "email": "a@b.c"},
                            "type": "subscribe"}),
        ("sendgrid", [{"sg_message_id": "m", "email": "a@b.c", "event": "open"}]),
        ("convertkit", {"subscriber": {"id": "s", "email_address": "a@b.c"},
                        "event": {"name": "n"}}),
        ("getresponse", {"contact": {"contact_id": "c", "email": "a@b.c"},
                         "event": {"name": "n"}}),
        ("discord", {"id": "d", "content": "hi", "author": {"username": "u"},
                     "channel_id": "c"}),
        ("teams", {"id": "m", "text": "hi",
                   "from": {"application": {"displayName": "App"}}}),
        ("telegram", {"message": {"message_id": 1, "text": "hi",
                                  "from": {"id": 1, "username": "u"},
                                  "chat": {"id": 1, "title": "C"},
                                  "photo": [{"file_id": "f"}]}}),
        ("telegram", {"channel_post": {"message_id": 2, "caption": "cap"}}),
        ("twilio", {"MessageSid": "SM1", "From": "+1", "To": "+2",
                    "MessageStatus": "received"}),
        ("twilio", {"CallSid": "CA1", "CallStatus": "done"}),
        ("intercom", {"data": {"id": "i",
                               "conversation_message": {"subject": "s"}},
                      "topic": "t"}),
        ("github", {"action": "opened", "pull_request": {"number": 1, "title": "T",
                                                         "state": "open"}}),
        ("github", {"action": "closed", "issue": {"number": 2, "title": "T",
                                                  "state": "closed"}}),
        ("github", {"after": "abcdef12345", "ref": "refs/heads/main"}),
        ("gitlab", {"object_kind": "merge_request",
                    "object_attributes": {"iid": 1, "title": "T", "state": "opened",
                                          "action": "open"}}),
        ("gitlab", {"object_kind": "issue",
                    "object_attributes": {"iid": 2, "title": "T", "state": "opened",
                                          "action": "update"}}),
        ("gitlab", {"object_kind": "push", "after": "abcdef123", "ref": "r"}),
        ("bitbucket", {"pullrequest": {"id": 1, "title": "T", "state": "OPEN"},
                       "action": "declined"}),
        ("bitbucket", {"changes": [{"toHash": "abcdef123",
                                    "ref": {"displayId": "main"}}]}),
        ("bitbucket", {"changes": []}),
        ("google_drive", {"file_id": "f", "name": "F", "action": "a"}),
        ("dropbox", {"file_id": "f", "name": "F", "event_type": "e"}),
        ("box", {"file_id": "f", "file_name": "F", "event_type": "e"}),
        ("onedrive", {"file_id": "f", "file_name": "F", "action": "a"}),
        ("shopify", {"id": "o1", "email": "a@b.c", "total_price": "9.99",
                     "topic": "orders/create"}),
        ("woocommerce", {"id": "o", "total": "1", "status": "paid",
                         "action": "a"}),
        ("bigcommerce", {"data": {"id": "o", "total_tax_inc": "1"},
                         "scope": "store/order/created"}),
        ("magento", {"entity_id": "o", "grand_total": "1", "event_name": "e"}),
        ("stripe", {"type": "charge.succeeded",
                    "data": {"object": {"object": "charge", "id": "ch",
                                        "amount": 100, "currency": "usd"}}}),
        ("airtable", {"record_id": "r", "base_id": "b", "table_id": "t",
                      "action": "a"}),
        ("webex", {"data": {"id": "m", "text": "hi", "personId": "p"},
                   "name": "created"}),
        ("zoom", {"id": "m", "topic": "T", "event": "meeting.started"}),
        ("freshdesk", {"ticket_id": "t", "subject": "s", "status": "open",
                       "trigger": "tr"}),
        ("figma", {"file_key": "f", "file_name": "F", "event_type": "e"}),
        ("whatsapp", {"entry": [{"changes": [{"value": {
            "messages": [{"id": "m1", "text": {"body": "hi"}, "from": "+1",
                          "timestamp": "1"}],
            "metadata": {"phone_number_id": "p"}}}]}]}),
        ("outlook", {"id": "m1", "subject": "S", "from": "a@b.c", "to": "c@d.e",
                     "content": LONG_TEXT, "direction": "inbound",
                     "metadata": {"conversation_id": "c1"}}),
    ]

    @pytest.mark.parametrize("integration,payload", TRANSFORM_PAYLOADS)
    async def test_transformer_produces_record(self, pipeline, integration, payload):
        svc = pipeline["svc"]
        records = await svc._transform_webhook_payload(integration, dict(payload)
                                                       if isinstance(payload, dict)
                                                       else payload)
        assert records, f"no records for {integration}"
        assert records[0]["id"] != None  # standardized id always present

    async def test_transform_no_transformer_and_error(self, pipeline):
        svc = pipeline["svc"]
        assert await svc._transform_webhook_payload("unknown_integration", {}) == []
        with patch.object(svc, "_transform_slack_payload",
                          AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc._transform_webhook_payload("slack", {}) == []

    async def test_standardizer_variants(self, pipeline):
        svc = pipeline["svc"]
        # non-dict records filtered out
        with patch.object(svc, "_transform_slack_payload",
                          AsyncMock(return_value=["str", {"id": "m"}])):
            recs = await svc._transform_webhook_payload("slack", {})
        assert len(recs) == 1
        r = recs[0]
        assert r["sender_id"] == ""
        assert r["timestamp"] == ""
        # dict body content extraction + UUID metadata + nested metadata merge
        u = uuid.uuid4()
        record = {"id": u, "user": "U", "body": {"content": "deep"},
                  "ts": "123", "properties": {"email": "a@b.c"},
                  "metadata": {"nested": u}, "changes": ["x"], "raw": "z",
                  "subject": "S"}
        with patch.object(svc, "_transform_slack_payload",
                          AsyncMock(return_value=[record])):
            recs = await svc._transform_webhook_payload("slack", {})
        r = recs[0]
        assert r["id"] == str(u)
        assert r["content"] == "deep"
        assert r["metadata"]["nested"] == str(u)
        assert r["metadata"]["changes"] == ["x"]
        assert r["metadata"]["raw"] == "z"
        assert r["sender_id"] == "U"

    async def test_gmail_transform_fallback_and_direct(self, pipeline):
        svc = pipeline["svc"]
        # fallback record when no connection
        recs = await svc._transform_gmail_payload({"historyId": 5,
                                                   "emailAddress": "a@b.c"})
        assert recs[0]["type"] == "gmail_message"
        recs = await svc._transform_gmail_payload({})
        assert recs[0]["id"] == "gmail_unknown"
        # direct fetch path
        history = {"history": [{"messagesAdded": [{"message": {"id": "m1"}}]}]}
        detail = {"id": "m1", "threadId": "t1", "snippet": "body text here",
                  "internalDate": "1700000000000",
                  "payload": {"headers": [{"name": "Subject", "value": "S"},
                                          {"name": "From", "value": "a@b.c"},
                                          {"name": "To", "value": "c@d.e"}]}}
        with patch.object(svc, "_fetch_gmail_resource_direct",
                          AsyncMock(side_effect=[history, detail])):
            recs = await svc._transform_gmail_payload(
                {"historyId": 5, "_source_connection_id": "conn"})
        assert recs[0]["subject"] == "S"
        assert recs[0]["timestamp"] is not None
        # exception -> fallback
        with patch.object(svc, "_fetch_gmail_resource_direct",
                          AsyncMock(side_effect=RuntimeError("x"))):
            recs = await svc._transform_gmail_payload(
                {"historyId": 5, "_source_connection_id": "conn"})
        assert recs[0]["subject"] == "New email notification"

    async def test_outlook_transform_variants(self, pipeline):
        svc = pipeline["svc"]
        # pre-normalized
        recs = await svc._transform_outlook_payload(
            {"id": "m1", "subject": "S", "from": "a@b.c", "content": "text"})
        assert recs[0]["type"] == "email"
        # raw notification: message
        msg = {"id": "m2", "from": {"emailAddress": {"address": "x@y.z"}},
               "subject": "S", "bodyPreview": "preview text", "receivedDateTime": "t"}
        with patch.object(svc, "_fetch_outlook_resource_direct",
                          AsyncMock(return_value=msg)):
            recs = await svc._transform_outlook_payload(
                {"resource": "Messages/m2", "_source_connection_id": "c",
                 "resourceData": {"@odata.type": "#Microsoft.Graph.Message"}})
        assert recs[0]["sender_id"] == "x@y.z"
        # calendar event
        ev = {"id": "e1", "subject": "E", "body": {"content": "b"},
              "start": "s", "end": "e", "location": "l"}
        with patch.object(svc, "_fetch_outlook_resource_direct",
                          AsyncMock(return_value=ev)):
            recs = await svc._transform_outlook_payload(
                {"resource": "Events/e1", "_source_connection_id": "c",
                 "resourceData": {"@odata.type": "#Microsoft.Graph.Event"}})
        assert recs[0]["type"] == "calendar_event"
        # generic fallback type
        with patch.object(svc, "_fetch_outlook_resource_direct",
                          AsyncMock(return_value={"id": "d1", "name": "N"})):
            recs = await svc._transform_outlook_payload(
                {"resource": "Items/d1", "_source_connection_id": "c",
                 "resourceData": {"@odata.type": "#Microsoft.Graph.DriveItem"}})
        assert recs[0]["type"] == "outlook_resource"
        # fetch failure -> [] ; fetch none -> []
        with patch.object(svc, "_fetch_outlook_resource_direct",
                          AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc._transform_outlook_payload(
                {"resource": "r", "resourceData": {}}) == []
        with patch.object(svc, "_fetch_outlook_resource_direct",
                          AsyncMock(return_value=None)):
            assert await svc._transform_outlook_payload(
                {"resource": "r", "resourceData": {}}) == []

    async def test_whatsapp_error_path(self, pipeline):
        svc = pipeline["svc"]
        recs = await svc._transform_whatsapp_payload({"entry": None})
        assert recs == []


class TestDirectFetchers:
    async def test_outlook_direct(self, pipeline):
        svc = pipeline["svc"]
        assert await svc._fetch_outlook_resource_direct(None, "p") is None
        svc.db = None
        conn = MagicMock(credentials="enc")
        session = FakeSession(user_conn=conn)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"id": "m"}
        resp.raise_for_status = MagicMock()
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=resp)
        with patch.object(ip, "SessionLocal", return_value=session), \
             patch("core.connection_service.ConnectionService") as CS, \
             patch("httpx.AsyncClient", return_value=client):
            CS.return_value._decrypt.return_value = {"access_token": "t"}
            CS.return_value._refresh_token_if_needed = AsyncMock(return_value=None)
            # no connection found
            session.user_conn = None
            assert await svc._fetch_outlook_resource_direct("conn", "p") is None
            session.user_conn = conn
            # no creds
            CS.return_value._decrypt.return_value = None
            assert await svc._fetch_outlook_resource_direct("conn", "p") is None
            CS.return_value._decrypt.return_value = {"access_token": "t"}
            # refreshed credentials saved
            CS.return_value._refresh_token_if_needed = AsyncMock(
                return_value={"access_token": "t2"})
            r = await svc._fetch_outlook_resource_direct("conn", "users/m")
            assert r == {"id": "m"}
            assert session.committed >= 1
            # full https URL passthrough
            await svc._fetch_outlook_resource_direct(
                "conn", "https://graph.microsoft.com/v1.0/me")
            assert client.get.call_args[0][0].startswith("https://graph")
            # 404 -> {}
            resp.status_code = 404
            assert await svc._fetch_outlook_resource_direct("conn", "p") == {}
            # http status error
            import httpx
            resp.status_code = 500
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("e", request=MagicMock(),
                                                  response=resp))
            assert await svc._fetch_outlook_resource_direct("conn", "p") is None
            # generic error
            client.get = AsyncMock(side_effect=RuntimeError("x"))
            assert await svc._fetch_outlook_resource_direct("conn", "p") is None
        assert session.closed >= 1

    async def test_gmail_direct(self, pipeline):
        svc = pipeline["svc"]
        assert await svc._fetch_gmail_resource_direct(None, "p") is None
        svc.db = None
        conn = MagicMock(credentials="enc")
        session = FakeSession(user_conn=conn)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"id": "g"}
        resp.raise_for_status = MagicMock()
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=resp)
        with patch.object(ip, "SessionLocal", return_value=session), \
             patch("core.connection_service.ConnectionService") as CS, \
             patch("httpx.AsyncClient", return_value=client):
            CS.return_value._decrypt.return_value = {"access_token": "t"}
            CS.return_value._refresh_token_if_needed = AsyncMock(return_value=None)
            session.user_conn = None
            assert await svc._fetch_gmail_resource_direct("conn", "p") is None
            session.user_conn = conn
            CS.return_value._decrypt.return_value = {}
            assert await svc._fetch_gmail_resource_direct("conn", "p") is None
            CS.return_value._decrypt.return_value = {"refresh": "r"}
            assert await svc._fetch_gmail_resource_direct("conn", "p") is None
            CS.return_value._decrypt.return_value = {"access_token": "t"}
            r = await svc._fetch_gmail_resource_direct("conn", "users/me/history")
            assert r == {"id": "g"}
            await svc._fetch_gmail_resource_direct(
                "conn", "https://gmail.googleapis.com/x")
            import httpx
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError("e", request=MagicMock(),
                                                  response=resp))
            assert await svc._fetch_gmail_resource_direct("conn", "p") is None
            client.get = AsyncMock(side_effect=RuntimeError("x"))
            assert await svc._fetch_gmail_resource_direct("conn", "p") is None


class TestPrepareRecordText:
    def _docling(self, supported=True, result=None):
        p = MagicMock()
        p.is_format_supported = MagicMock(return_value=supported)
        p.process_document = AsyncMock(return_value=result)
        return patch.object(ip, "get_docling_processor", return_value=p), p

    async def test_kill_switch_and_flags(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        monkeypatch.setenv("ENABLE_BINARY_INGESTION", "false")
        assert await svc._prepare_record_text_async(
            {"id": "f1", "type": "file"}, "gdrive") == svc._record_to_text(
            {"id": "f1", "type": "file"}, "gdrive")
        monkeypatch.setenv("ENABLE_BINARY_INGESTION", "true")
        monkeypatch.setenv("ENABLE_GDRIVE_FILE_PARSING", "false")
        assert await svc._prepare_record_text_async(
            {"id": "f1", "type": "file"}, "gdrive") is not None
        monkeypatch.setenv("ENABLE_GDRIVE_FILE_PARSING", "true")
        monkeypatch.setenv("ENABLE_WORKDRIVE_FILE_PARSING", "false")
        assert await svc._prepare_record_text_async(
            {"id": "f1", "type": "file"}, "zoho_workdrive") is not None
        monkeypatch.setenv("ENABLE_WORKDRIVE_FILE_PARSING", "true")

    async def test_file_branches(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        record = {"id": "f1", "type": "file", "name": "doc.pdf",
                  "extension": "pdf"}
        # unsupported extension
        dp, _ = self._docling(supported=False)
        with dp:
            r = await svc._prepare_record_text_async(record, "gdrive")
            assert isinstance(r, str)
        dp, proc = self._docling(result={"success": True, "content": "x" * 50})
        # service without download_file
        with dp:
            svc.integration_registry.get_service = AsyncMock(return_value=None)
            await svc._prepare_record_text_async(record, "gdrive")
        # empty bytes / oversize
        svc.integration_registry.get_service = AsyncMock(
            return_value=MagicMock(download_file=AsyncMock(return_value=b"")))
        with dp:
            await svc._prepare_record_text_async(record, "gdrive")
        svc.integration_registry.get_service = AsyncMock(
            return_value=MagicMock(download_file=AsyncMock(return_value=b"z" * 100)))
        monkeypatch.setenv("MAX_INGESTION_FILE_SIZE_MB", "0")
        with dp:
            await svc._prepare_record_text_async(record, "gdrive")
        monkeypatch.setenv("MAX_INGESTION_FILE_SIZE_MB", "50")
        # docling failure / short content / success / exception
        for result in ({"success": False, "error": "bad"},
                       {"success": True, "content": "tiny"}):
            dp, _ = self._docling(result=result)
            with dp:
                await svc._prepare_record_text_async(record, "gdrive")
        dp, _ = self._docling(result={"success": True, "content": "c" * 100})
        with dp:
            r = await svc._prepare_record_text_async(record, "gdrive")
            assert r == "c" * 100
            # exception during processing
            svc.integration_registry.get_service = AsyncMock(
                side_effect=RuntimeError("boom"))
            r = await svc._prepare_record_text_async(record, "gdrive")
            assert isinstance(r, str)
        # default (non-file) path
        dp, _ = self._docling()
        with dp:
            r = await svc._prepare_record_text_async(
                {"id": "m1", "type": "note", "text": "hello"}, "slack")
            assert isinstance(r, str)

    async def test_attachment_branches(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        base = {"id": "m1", "type": "email", "subject": "s", "content": LONG_TEXT}
        # flag off
        monkeypatch.setenv("ENABLE_OUTLOOK_ATTACHMENT_INGESTION", "false")
        r = await svc._prepare_record_text_async(dict(base, hasAttachments=True),
                                                 "outlook", "conn")
        assert isinstance(r, str)
        monkeypatch.setenv("ENABLE_OUTLOOK_ATTACHMENT_INGESTION", "true")
        # no message id
        r = await svc._prepare_record_text_async({"type": "email",
                                                  "hasAttachments": True},
                                                 "outlook", "conn")
        # service unavailable
        svc.integration_registry.get_service = AsyncMock(return_value=None)
        r = await svc._prepare_record_text_async(dict(base, hasAttachments=True),
                                                 "outlook", "conn")
        # full attachment flow
        svc_download = MagicMock()
        svc_download.get_attachment_metadata = AsyncMock(return_value=[
            {"id": "a1", "name": "doc.pdf", "size": 100, "contentType": "pdf"},
            {"id": "a2", "name": "img.xyz", "size": 100},
            {"id": "a3", "name": "big.pdf", "size": 999 * 1024 * 1024},
            {"id": "a4", "name": "dud.pdf", "size": 100},
            {"id": "a5", "name": "err.pdf", "size": 100},
        ])
        svc_download.download_attachment = AsyncMock(
            side_effect=[b"bytes", b"", RuntimeError("dl fail")])
        svc_download.config = {"access_token": "tok"}
        svc.integration_registry.get_service = AsyncMock(return_value=svc_download)
        dp, proc = self._docling(result={"success": True, "content": "parsed text!"})
        with dp:
            r = await svc._prepare_record_text_async(
                dict(base, hasAttachments=True), "outlook", "conn")
            assert "[Attachment: doc.pdf]" in r
        # parse failure for all attachments -> base text
        svc_download.download_attachment = AsyncMock(return_value=b"bytes")
        dp, _ = self._docling(result={"success": False, "error": "x"})
        with dp:
            r = await svc._prepare_record_text_async(
                dict(base, hasAttachments=True), "outlook", "conn")
            assert "[Attachment" not in r
        # metadata via nested metadata/raw_json dicts
        svc_download.get_attachment_metadata = AsyncMock(return_value=[
            {"id": "a1", "name": "doc.pdf", "size": 10}])
        dp, _ = self._docling(result={"success": True, "content": "parsed text!"})
        with dp:
            r = await svc._prepare_record_text_async(
                {"id": "m1", "type": "messages",
                 "metadata": {"hasAttachments": True},
                 "subject": "s", "content": LONG_TEXT}, "gmail", "conn")
            assert "[Attachment: doc.pdf]" in r
        # empty attachment list -> base text
        svc_download.get_attachment_metadata = AsyncMock(return_value=[])
        with dp:
            r = await svc._prepare_record_text_async(
                {"id": "m1", "type": "email", "hasAttachments": True,
                 "subject": "s", "content": LONG_TEXT}, "outlook", "conn")
            assert "[Attachment" not in r
        # exception in attachment processing -> fallback
        svc_download.get_attachment_metadata = AsyncMock(
            side_effect=RuntimeError("meta fail"))
        with dp:
            r = await svc._prepare_record_text_async(
                {"id": "m1", "type": "email", "hasAttachments": True,
                 "subject": "s", "content": LONG_TEXT}, "outlook", "conn")
            assert isinstance(r, str)
