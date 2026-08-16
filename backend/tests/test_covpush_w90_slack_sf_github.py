# -*- coding: utf-8 -*-
"""Coverage wave 90 — integrations/salesforce_routes.py,
integrations/slack_workflow_automation.py, integrations/slack_workflow_engine.py,
integrations/slack_routes.py, integrations/github_routes.py.

No network / no LLM / no real DB: every external boundary (Salesforce auth
handler + client, GitHub service, Slack SDK / OAuth handlers, HTTP clients,
governance helpers) is mocked. Plain pytest + unittest.mock with FastAPI
TestClient and dependency_overrides for get_current_user / get_db.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac as hmac_mod
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import integrations.github_routes as gr
import integrations.salesforce_routes as sr
import integrations.slack_routes as sl
import integrations.slack_workflow_automation as wa
import integrations.slack_workflow_engine as we
from core.database import get_db
from core.auth import get_current_user

USER = SimpleNamespace(id="user-1", email="u@example.com")


def make_client(module, db=None, extra_overrides=None):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    for dep, fn in (extra_overrides or {}).items():
        app.dependency_overrides[dep] = fn
    return TestClient(app, raise_server_exceptions=False)


def mock_db(result=None):
    db = MagicMock()
    chain = MagicMock()
    chain.filter.return_value.first.return_value = result
    db.query.return_value = chain
    return db


# ============================================================================
# Salesforce routes
# ============================================================================

def sf_client(query_result=None):
    sf = MagicMock()
    sf.query.return_value = query_result or {"totalSize": 0, "records": []}
    sf.search.return_value = {"searchRecords": []}
    sf.restful.return_value = {"id": "me", "name": "Test User"}
    return sf


def sf_token_patch(ok=True):
    handler = sr.salesforce_auth_handler
    if ok:
        return patch.object(handler, "ensure_valid_token", AsyncMock(return_value="tok"))
    return patch.object(
        handler, "ensure_valid_token",
        AsyncMock(side_effect=HTTPException(status_code=401, detail="no token")))


class TestSalesforceAuth:
    def test_auth_url(self):
        with patch.object(sr.salesforce_auth_handler, "get_authorization_url",
                          return_value="https://sf/login"):
            r = make_client(sr).get("/api/salesforce/auth/url")
        assert r.status_code == 200 and r.json()["url"].startswith("https://sf")

    def test_callback_success(self):
        with patch.object(sr.salesforce_auth_handler, "exchange_code_for_token",
                          AsyncMock(return_value={"instance_url": "https://x"})):
            r = make_client(sr).get("/api/salesforce/callback",
                                    params={"code": "c", "state": "s"})
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_callback_http_exception_reraised(self):
        with patch.object(sr.salesforce_auth_handler, "exchange_code_for_token",
                          AsyncMock(side_effect=HTTPException(400, "bad code"))):
            r = make_client(sr).get("/api/salesforce/callback", params={"code": "c"})
        assert r.status_code == 400

    def test_callback_generic_500(self):
        with patch.object(sr.salesforce_auth_handler, "exchange_code_for_token",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            r = make_client(sr).get("/api/salesforce/callback", params={"code": "c"})
        assert r.status_code == 500

    def test_revoke(self):
        for ok in (True, False):
            with patch.object(sr.salesforce_auth_handler, "revoke_token",
                              AsyncMock(return_value=ok)):
                r = make_client(sr).post("/api/salesforce/auth/revoke")
            assert r.status_code == 200 and r.json()["ok"] is ok

    def test_status(self):
        with patch.object(sr.salesforce_auth_handler, "get_connection_status",
                          return_value={"connected": True}):
            r = make_client(sr).get("/api/salesforce/status")
        assert r.json()["status"] == {"connected": True}

    def test_get_access_token_dependency_unauthorized(self):
        c = make_client(sr)
        with sf_token_patch(ok=False):
            r = c.get("/api/salesforce/accounts")
        assert r.status_code == 401


class TestSalesforceHealth:
    def test_degraded_without_client(self):
        with patch.object(sr, "get_salesforce_client_from_env", return_value=None):
            r = make_client(sr).get("/api/salesforce/health")
        assert r.status_code == 200 and r.json()["status"] == "degraded"

    def test_connected(self):
        with patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()):
            r = make_client(sr).get("/api/salesforce/health")
        assert r.json()["status"] == "healthy"

    def test_query_failure_degraded(self):
        sf = sf_client()
        sf.query.side_effect = RuntimeError("down")
        with patch.object(sr, "get_salesforce_client_from_env", return_value=sf):
            r = make_client(sr).get("/api/salesforce/health")
        assert r.json()["status"] == "degraded"

    def test_init_exception_degraded(self):
        with patch.object(sr, "get_salesforce_client_from_env",
                          side_effect=RuntimeError("init")):
            r = make_client(sr).get("/api/salesforce/health")
        assert r.json()["status"] == "degraded"


class TestSalesforceUnavailable:
    def test_endpoints_503_when_unavailable(self):
        c = make_client(sr)
        with sf_token_patch(), patch.object(sr, "SALESFORCE_AVAILABLE", False):
            for method, path in [
                ("get", "/api/salesforce/accounts"),
                ("get", "/api/salesforce/contacts"),
                ("get", "/api/salesforce/opportunities"),
                ("get", "/api/salesforce/leads"),
                ("get", "/api/salesforce/search?query=x"),
                ("get", "/api/salesforce/analytics/pipeline"),
                ("get", "/api/salesforce/analytics/leads"),
                ("get", "/api/salesforce/profile"),
            ]:
                assert getattr(c, method)(path).status_code == 503, path
            assert c.post("/api/salesforce/accounts", json={"name": "A"}).status_code == 503
            assert c.post("/api/salesforce/contacts",
                          json={"first_name": "a", "last_name": "b",
                                "email": "a@b.c"}).status_code == 503
            assert c.post("/api/salesforce/opportunities",
                          json={"name": "o", "account_id": "a", "stage": "s",
                                "amount": 1, "close_date": "2026-01-01"}).status_code == 503
            assert c.post("/api/salesforce/leads",
                          json={"first_name": "a", "last_name": "b",
                                "company": "c", "email": "a@b.c"}).status_code == 503
            assert c.post("/api/salesforce/integrations/stripe/payments",
                          json={"payment_data": {"id": "p1"}}).status_code == 503


class TestSalesforceListEndpoints:
    def test_accounts_401_without_client(self):
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).get("/api/salesforce/accounts")
        assert r.status_code == 401

    def test_accounts_success_with_ingestion(self):
        ingest = AsyncMock()
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "list_accounts",
                          AsyncMock(return_value=[{"Id": "A1", "Name": "Acme"}])), \
             patch.object(sr.atom_ingestion_pipeline, "ingest_record", ingest):
            r = make_client(sr).get("/api/salesforce/accounts?name=x&industry=y")
        assert r.json()["ok"] and r.json()["data"]["accounts"][0]["Id"] == "A1"
        ingest.assert_awaited_once()

    def test_accounts_ingestion_failure_swallowed(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "list_accounts",
                          AsyncMock(return_value=[{"Id": "A1"}])), \
             patch.object(sr.atom_ingestion_pipeline, "ingest_record",
                          AsyncMock(side_effect=RuntimeError("pipe"))):
            r = make_client(sr).get("/api/salesforce/accounts")
        assert r.json()["ok"] is True

    def test_accounts_generic_error(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "list_accounts",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            r = make_client(sr).get("/api/salesforce/accounts")
        assert r.json()["ok"] is False

    def test_account_by_id_invalid_format(self):
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).get("/api/salesforce/accounts/bad!!id")
        assert r.json()["ok"] is False and "Invalid" in r.json()["error"]["message"]

    def test_account_by_id_no_credentials(self):
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).get("/api/salesforce/accounts/001XXXXXXXXXXXXXXX")
        assert r.json()["ok"] is False

    def test_account_by_id_found_and_missing(self):
        sf = sf_client()
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(sr, "execute_soql_query",
                          AsyncMock(side_effect=[
                              {"records": [{"Id": "001XXXXXXXXXXXXXXX"}]},
                              {"records": []},
                          ])):
            c = make_client(sr)
            assert c.get("/api/salesforce/accounts/001XXXXXXXXXXXXXXX").json()["ok"] is True
            assert c.get("/api/salesforce/accounts/001XXXXXXXXXXXXXXX").json()["ok"] is False

    def test_account_by_id_exception(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env", return_value=sf_client()), \
             patch.object(sr, "execute_soql_query",
                          AsyncMock(side_effect=RuntimeError("x"))):
            r = make_client(sr).get("/api/salesforce/accounts/001XXXXXXXXXXXXXXX")
        assert r.json()["ok"] is False

    def test_contacts_filters_and_401(self):
        contacts = [
            {"AccountId": "A1", "Email": "a@x.c"}, {"AccountId": "A2", "Email": "b@x.c"}]
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).get("/api/salesforce/contacts")
        assert r.status_code == 401
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "list_contacts", AsyncMock(return_value=contacts)), \
             patch.object(sr.atom_ingestion_pipeline, "ingest_record", AsyncMock()):
            r = make_client(sr).get("/api/salesforce/contacts?account_id=A1&email=a@x.c")
        assert len(r.json()["data"]) == 1

    def test_opportunities(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "list_opportunities",
                          AsyncMock(return_value=[{"Id": "O1"}])), \
             patch.object(sr.atom_ingestion_pipeline, "ingest_record",
                          AsyncMock(side_effect=RuntimeError("swallow"))):
            r = make_client(sr).get("/api/salesforce/opportunities")
        assert r.json()["ok"] is True
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).get("/api/salesforce/opportunities")
        assert r.status_code == 401

    def test_leads(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "list_leads", AsyncMock(return_value=[])):
            r = make_client(sr).get("/api/salesforce/leads")
        assert r.json()["ok"] is True
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).get("/api/salesforce/leads")
        assert r.json()["ok"] is False  # no creds -> error envelope


class TestSalesforceCreate:
    def _body(self):
        return {"name": "Acme", "industry": "Tech"}

    def test_create_account_no_credentials(self):
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).post("/api/salesforce/accounts", json=self._body())
        assert r.json()["ok"] is False

    def test_create_account_success(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "create_account",
                          AsyncMock(return_value={"id": "A9"})):
            r = make_client(sr).post("/api/salesforce/accounts", json=self._body())
        assert r.json()["data"] == {"id": "A9"}

    def test_create_account_governance_blocked(self):
        with sf_token_patch(), \
             patch.object(sr, "with_governance_check",
                          AsyncMock(return_value=(None, {"allowed": False,
                                                         "reason": "no perm"}))):
            r = make_client(sr, post := None) if False else make_client(sr).post(
                "/api/salesforce/accounts?agent_id=ag1", json=self._body())
        assert r.status_code == 403

    def test_create_account_governance_exception_continues(self):
        with sf_token_patch(), \
             patch.object(sr, "with_governance_check",
                          AsyncMock(side_effect=RuntimeError("gov down"))), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "create_account", AsyncMock(return_value={"id": "A"})):
            r = make_client(sr).post("/api/salesforce/accounts?agent_id=ag1",
                                     json=self._body())
        assert r.json()["ok"] is True

    def test_create_contact_lead_opportunity(self):
        c = make_client(sr)
        sfp = patch.object(sr, "get_salesforce_client_from_env",
                           return_value=sf_client())
        with sf_token_patch(), sfp, \
             patch.object(sr, "create_contact", AsyncMock(return_value={"id": "C"})), \
             patch.object(sr, "create_lead", AsyncMock(return_value={"id": "L"})), \
             patch.object(sr, "create_opportunity",
                          AsyncMock(return_value={"id": "O"})):
            assert c.post("/api/salesforce/contacts",
                          json={"first_name": "a", "last_name": "b",
                                "email": "a@b.c"}).json()["ok"]
            assert c.post("/api/salesforce/leads",
                          json={"first_name": "a", "last_name": "b",
                                "company": "c", "email": "a@b.c"}).json()["ok"]
            assert c.post("/api/salesforce/opportunities",
                          json={"name": "o", "account_id": "a", "stage": "s",
                                "amount": 5, "close_date": "2026-01-01"}).json()["ok"]

    def test_create_contact_error(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "create_contact",
                          AsyncMock(side_effect=RuntimeError("x"))):
            r = make_client(sr).post("/api/salesforce/contacts",
                                     json={"first_name": "a", "last_name": "b",
                                           "email": "a@b.c"})
        assert r.json()["ok"] is False


class TestSalesforceSearchAnalytics:
    def test_search_invalid_object_type(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()):
            r = make_client(sr).get("/api/salesforce/search",
                                    params={"query": "x",
                                            "object_types": "bad;type"})
        assert r.json()["ok"] is False

    def test_search_success_and_no_creds(self):
        c = make_client(sr)
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()):
            r = c.get("/api/salesforce/search?query=acme")
            assert r.json()["ok"] is True
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = c.get("/api/salesforce/search?query=acme")
        assert r.json()["ok"] is False

    def test_search_inner_exception(self):
        sf = sf_client()
        sf.search.side_effect = RuntimeError("boom")
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env", return_value=sf):
            r = make_client(sr).get("/api/salesforce/search?query=acme")
        assert r.json()["ok"] is False

    def test_pipeline_analytics(self):
        result = {"records": [{"Amount": 100}, {"Amount": 50}, {"Amount": None}]}
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "execute_soql_query", AsyncMock(return_value=result)):
            r = make_client(sr).get("/api/salesforce/analytics/pipeline")
        assert r.json()["data"]["pipeline_value"] == 150.0
        assert r.json()["data"]["opportunities_count"] == 3

    def test_pipeline_no_records(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "execute_soql_query", AsyncMock(return_value={})):
            r = make_client(sr).get("/api/salesforce/analytics/pipeline")
        assert r.json()["data"]["pipeline_value"] == 0.0

    def test_leads_analytics(self):
        result = {"records": [{"IsConverted": True}, {"IsConverted": False}]}
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()), \
             patch.object(sr, "execute_soql_query", AsyncMock(return_value=result)):
            r = make_client(sr).get("/api/salesforce/analytics/leads")
        assert r.json()["data"]["leads_count"] == 2
        assert r.json()["data"]["conversion_rate"] == 50.0

    def test_analytics_no_creds(self):
        c = make_client(sr)
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            assert c.get("/api/salesforce/analytics/pipeline").json()["ok"] is False
            assert c.get("/api/salesforce/analytics/leads").json()["ok"] is False


class TestSalesforceProfileRoot:
    def test_profile_chatter(self):
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env",
                          return_value=sf_client()):
            r = make_client(sr).get("/api/salesforce/profile")
        assert r.json()["data"]["id"] == "me"

    def test_profile_fallback_user_query(self):
        sf = sf_client()
        sf.restful.side_effect = RuntimeError("no chatter")
        sf.query.return_value = {"totalSize": 1,
                                 "records": [{"Id": "U1", "Name": "N"}]}
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env", return_value=sf):
            r = make_client(sr).get("/api/salesforce/profile")
        assert r.json()["data"]["Id"] == "U1"

    def test_profile_fallback_not_found_and_error(self):
        sf = sf_client()
        sf.restful.side_effect = RuntimeError("no chatter")
        sf.query.return_value = {"totalSize": 0, "records": []}
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env", return_value=sf):
            r = make_client(sr).get("/api/salesforce/profile")
        assert r.json()["ok"] is False
        sf.query.side_effect = RuntimeError("boom")
        with sf_token_patch(), \
             patch.object(sr, "get_salesforce_client_from_env", return_value=sf):
            r = make_client(sr).get("/api/salesforce/profile")
        assert r.json()["ok"] is False

    def test_profile_no_creds(self):
        with sf_token_patch(), patch.object(sr, "get_salesforce_client_from_env",
                                            return_value=None):
            r = make_client(sr).get("/api/salesforce/profile")
        assert r.json()["ok"] is False

    def test_stripe_sync_and_root(self):
        c = make_client(sr)
        with sf_token_patch():
            r = c.post("/api/salesforce/integrations/stripe/payments",
                       json={"payment_data": {"id": "pay_1", "amount": 100},
                             "opportunity_id": "O1"})
        assert r.json()["data"]["synced"] is True
        r = c.get("/api/salesforce/")
        assert r.json()["service"] == "salesforce"


# ============================================================================
# Slack workflow automation
# ============================================================================

def make_auto(memory=None, search=None, comm=None):
    auto = wa.SlackWorkflowAutomation({})
    if memory is not None:
        auto.memory_service = memory
    if search is not None:
        auto.search_service = search
    if comm is not None:
        auto.communication_service = comm
    return auto


def wf(wid="wf1", triggers=None, actions=None, active=True):
    return wa.SlackWorkflow(
        id=wid, name=f"WF {wid}", description="d",
        triggers=triggers or [wa.SlackWorkflowTrigger(
            id="t1", type=wa.WorkflowTriggerType.MESSAGE, conditions={},
            workspace_id="", channel_ids=[], user_ids=[], keywords=[])],
        actions=actions or [], created_by="u", active=active,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def action(aid="a1", atype=None, parameters=None, retry=0, delay=0):
    return wa.SlackWorkflowAction(id=aid, type=atype or wa.WorkflowActionType.SEND_MESSAGE,
                                  parameters=parameters or {}, delay_seconds=delay,
                                  retry_count=retry)


class TestSlackAutomationRegistry:
    def test_register_unregister(self):
        auto = make_auto(memory=MagicMock())
        assert auto.register_workflow(wf()) is True
        auto.memory_service.store.assert_called_once()
        assert auto.get_workflow("wf1") is not None
        listed = auto.list_workflows(active_only=False)
        assert len(listed) == 1
        assert auto.list_workflows(workspace_id="nope") == []
        assert auto.unregister_workflow("wf1") is True
        assert auto.unregister_workflow("wf1") is False
        assert auto.get_workflow("wf1") is None

    def test_register_failure(self):
        mem = MagicMock()
        mem.store.side_effect = RuntimeError("nope")
        auto = make_auto(memory=mem)
        assert auto.register_workflow(wf()) is False

    def test_unregister_memory_delete_failure(self):
        mem = MagicMock()
        mem.delete.side_effect = RuntimeError("nope")
        auto = make_auto(memory=mem)
        auto.register_workflow(wf(wid="x"))
        assert auto.unregister_workflow("x") is False

    def test_list_active_filter(self):
        auto = make_auto()
        auto.register_workflow(wf("on", active=True))
        auto.register_workflow(wf("off", active=False))
        assert [w.id for w in auto.list_workflows()] == ["on"]
        assert len(auto.list_workflows(active_only=False)) == 2


class TestSlackAutomationExecution:
    async def test_execute_not_found(self):
        auto = make_auto()
        with pytest.raises(ValueError):
            await auto.execute_workflow("missing", {})

    async def test_execute_success_with_delay(self):
        auto = make_auto()
        auto.register_workflow(wf(actions=[
            action(atype=wa.WorkflowActionType.CREATE_TASK)]))
        with patch.object(wa.asyncio, "sleep", AsyncMock()):
            exec_ = await auto.execute_workflow("wf1", {"workspace_id": "W"})
        assert exec_.status == "completed"
        assert exec_.action_results[0]["status"] == "success"

    async def test_execute_action_failure_and_retry(self):
        auto = make_auto()
        act = action(retry=1)
        auto.register_workflow(wf(actions=[act]))
        with patch.object(wa.asyncio, "sleep", AsyncMock()), \
             patch.object(auto, "execute_action",
                          AsyncMock(side_effect=[
                              {"status": "failed"},
                              {"status": "success"},
                          ])):
            exec_ = await auto.execute_workflow("wf1", {})
        assert exec_.status == "completed"
        assert act.retry_count == 0

    async def test_execute_action_non_success_fails_execution(self):
        auto = make_auto()
        auto.register_workflow(wf(actions=[action(retry=0)]))
        with patch.object(wa.asyncio, "sleep", AsyncMock()), \
             patch.object(auto, "execute_action",
                          AsyncMock(return_value={"status": "failed"})):
            exec_ = await auto.execute_workflow("wf1", {})
        assert exec_.status == "failed"
        assert "failed" in exec_.error_message

    async def test_execute_with_memory_store(self):
        auto = make_auto(memory=MagicMock())
        auto.register_workflow(wf(actions=[]))
        exec_ = await auto.execute_workflow("wf1", {})
        assert exec_.status == "completed"
        stored_types = [c.args[0]["type"] for c in auto.memory_service.store.call_args_list]
        assert "workflow_execution" in stored_types

    def test_stats_and_listing(self):
        auto = make_auto()
        auto.register_workflow(wf("wf1"))
        stats = auto.get_workflow_stats("wf1")
        assert stats["total_executions"] == 0 and stats["success_rate"] == 0
        assert auto.get_workflow_stats("missing") == {}
        e1 = wa.WorkflowExecution(id="e1", workflow_id="wf1", trigger_data={},
                                  status="completed",
                                  started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                                  completed_at=datetime(2026, 1, 1, 0, 0, 10,
                                                        tzinfo=timezone.utc))
        e2 = wa.WorkflowExecution(id="e2", workflow_id="wf1", trigger_data={},
                                  status="failed",
                                  started_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        auto.executions.update({"e1": e1, "e2": e2})
        assert auto.get_workflow_execution("e1") is e1
        assert len(auto.list_workflow_executions()) == 2
        assert len(auto.list_workflow_executions(workflow_id="wf1", limit=1)) == 1
        stats = auto.get_workflow_stats("wf1")
        assert stats["successful_executions"] == 1
        assert stats["average_duration"] == 10.0


class TestSlackAutomationActions:
    async def _run(self, atype, params, client=None, comm=None, trigger=None):
        auto = make_auto(comm=comm)
        auto._get_slack_client = MagicMock(return_value=client)
        return auto, await auto.execute_action(action(atype=atype, parameters=params),
                                               trigger or {})

    async def test_send_message(self):
        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "123.456"}
        auto, r = await self._run(
            wa.WorkflowActionType.SEND_MESSAGE,
            {"channel": "C1", "message": "hi {user}", "blocks": None},
            client=client, trigger={"user": "bob"})
        assert r["status"] == "success" and r["message_id"] == "123.456"
        assert r["message"] == "hi bob"

    async def test_send_message_no_client(self):
        auto, r = await self._run(wa.WorkflowActionType.SEND_MESSAGE,
                                  {"channel": "C1", "message": "hi"})
        assert r["status"] == "failed"

    async def test_create_channel(self):
        client = MagicMock()
        client.conversations_create.return_value = {"channel": {"id": "C9"}}
        auto, r = await self._run(wa.WorkflowActionType.CREATE_CHANNEL,
                                  {"name": "new-chan", "is_private": True},
                                  client=client)
        assert r["channel_id"] == "C9" and r["is_private"] is True

    async def test_create_channel_no_client(self):
        _, r = await self._run(wa.WorkflowActionType.CREATE_CHANNEL, {"name": "x"})
        assert r["status"] == "failed"

    async def test_invite_user(self):
        client = MagicMock()
        client.conversations_invite.return_value = {"ok": True}
        _, r = await self._run(wa.WorkflowActionType.INVITE_USER,
                               {"channel": "C1", "user": "U1"}, client=client)
        assert r["invited"] is True

    async def test_invite_user_no_client(self):
        _, r = await self._run(wa.WorkflowActionType.INVITE_USER,
                               {"channel": "C1", "user": "U1"})
        assert r["status"] == "failed"

    async def test_upload_file(self):
        client = MagicMock()
        client.files_upload_v2.return_value = {"file": {"id": "F1", "name": "f.txt"}}
        _, r = await self._run(wa.WorkflowActionType.UPLOAD_FILE,
                               {"channel": "C1", "file_path": "/tmp/f",
                                "comment": "c"}, client=client)
        assert r["file_id"] == "F1"

    async def test_upload_file_no_client(self):
        _, r = await self._run(wa.WorkflowActionType.UPLOAD_FILE,
                               {"channel": "C1", "file_path": "/tmp/f"})
        assert r["status"] == "failed"

    async def test_update_status(self):
        client = MagicMock()
        client.users_profile_set.return_value = {"ok": True}
        _, r = await self._run(wa.WorkflowActionType.UPDATE_STATUS,
                               {"status": "away", "emoji": ":zzz:"}, client=client)
        assert r["updated"] is True

    async def test_update_status_no_client(self):
        _, r = await self._run(wa.WorkflowActionType.UPDATE_STATUS,
                               {"status": "away"})
        assert r["status"] == "failed"

    async def test_create_task_and_email(self):
        _, r = await self._run(wa.WorkflowActionType.CREATE_TASK,
                               {"title": "T", "description": "D"})
        assert r["created"] is True
        _, r = await self._run(wa.WorkflowActionType.SEND_EMAIL,
                               {"to": "a@b.c", "subject": "S", "body": "B"})
        assert r["sent"] is True

    async def test_api_call_json_and_text(self):
        resp_json = MagicMock(status_code=200, content_type="application/json")
        resp_json.json.return_value = {"ok": 1}
        resp_text = MagicMock(status_code=201, content_type="text/plain")
        resp_text.text = "hello"
        for resp, expected in [(resp_json, {"ok": 1}), (resp_text, "hello")]:
            http = MagicMock()
            http.__aenter__ = AsyncMock(return_value=http)
            http.__aexit__ = AsyncMock(return_value=False)
            http.request = AsyncMock(return_value=resp)
            with patch.object(wa.httpx, "AsyncClient", return_value=http):
                _, r = await self._run(wa.WorkflowActionType.API_CALL,
                                       {"url": "http://x", "method": "POST",
                                        "headers": {}, "data": {"a": 1}})
            assert r["response"] == expected

    async def test_unknown_action_type(self):
        _, r = await self._run("not_a_type", {})
        assert r["status"] == "failed"

    async def test_communication_log_and_exception(self):
        comm = MagicMock()
        _, r = await self._run(wa.WorkflowActionType.CREATE_TASK, {"title": "T"},
                               comm=comm)
        comm.log_event.assert_called_once()
        auto = make_auto()
        auto._get_slack_client = MagicMock(side_effect=RuntimeError("boom"))
        r = await auto.execute_action(
            action(atype=wa.WorkflowActionType.SEND_MESSAGE), {})
        assert r["status"] == "failed"


class TestSlackAutomationTriggers:
    async def test_trigger_type_mismatches(self):
        auto = make_auto()
        cases = [
            (wa.WorkflowTriggerType.MESSAGE, "file_shared"),
            (wa.WorkflowTriggerType.FILE_UPLOAD, "message"),
            (wa.WorkflowTriggerType.CHANNEL_CREATED, "message"),
            (wa.WorkflowTriggerType.USER_JOIN, "message"),
            (wa.WorkflowTriggerType.MENTION, {}),
        ]
        for ttype, event in cases:
            trig = wa.SlackWorkflowTrigger(
                id="t", type=ttype, conditions={}, workspace_id="",
                channel_ids=[], user_ids=[], keywords=[])
            assert await auto._evaluate_trigger(trig, event) is False, ttype

    async def test_mention_match(self):
        auto = make_auto()
        trig = wa.SlackWorkflowTrigger(
            id="t", type=wa.WorkflowTriggerType.MENTION, conditions={},
            workspace_id="", channel_ids=[], user_ids=[], keywords=[])
        assert await auto._evaluate_trigger(trig, {"text": "hello"}) is True

    async def test_workspace_channel_user_keyword_filters(self):
        auto = make_auto()
        def trig(**kw):
            fields = dict(id="t", conditions={}, active=True,
                          workspace_id="", channel_ids=[], user_ids=[],
                          keywords=[], type=wa.WorkflowTriggerType.MESSAGE)
            fields.update(kw)
            return wa.SlackWorkflowTrigger(**fields)

        ev = {"type": "message", "team_id": "T1", "channel": "C1", "user": "U1",
              "text": "deploy now"}
        assert await auto._evaluate_trigger(trig(workspace_id="T1"), ev) is True
        assert await auto._evaluate_trigger(trig(workspace_id="T2"), ev) is False
        assert await auto._evaluate_trigger(trig(channel_ids=["C1"]), ev) is True
        assert await auto._evaluate_trigger(trig(channel_ids=["C9"]), ev) is False
        assert await auto._evaluate_trigger(trig(user_ids=["U1"]), ev) is True
        assert await auto._evaluate_trigger(trig(user_ids=["U9"]), ev) is False
        assert await auto._evaluate_trigger(trig(keywords=["deploy"]), ev) is True
        assert await auto._evaluate_trigger(trig(keywords=["ship"]), ev) is False

    async def test_condition_time_range_and_field(self):
        auto = make_auto()
        trig = wa.SlackWorkflowTrigger(
            id="t", type=wa.WorkflowTriggerType.MESSAGE,
            conditions={"time_range": {"start": 0, "end": 23},
                        "priority": "high", "user_role": "admin"},
            workspace_id="", channel_ids=[], user_ids=[], keywords=[])
        ev = {"type": "message", "priority": "high"}
        assert await auto._evaluate_trigger(trig, ev) is True
        trig.conditions["priority"] = "low"
        assert await auto._evaluate_trigger(trig, ev) is False
        trig.conditions["time_range"] = {"start": 0, "end": 0}
        assert await auto._evaluate_trigger(trig, ev) is False

    async def test_trigger_exception_returns_false(self):
        auto = make_auto()
        trig = wa.SlackWorkflowTrigger(
            id="t", type=wa.WorkflowTriggerType.MESSAGE,
            conditions={"time_range": "not-a-dict"},
            workspace_id="", channel_ids=[], user_ids=[], keywords=[])
        assert await auto._evaluate_trigger(
            trig, {"type": "message", "text": "x"}) is False

    async def test_handle_slack_event_executes_and_indexes(self):
        auto = make_auto(search=MagicMock())
        auto.search_service.index = AsyncMock()
        act = action(atype=wa.WorkflowActionType.CREATE_TASK)
        auto.register_workflow(wf(actions=[act]))
        execs = await auto.handle_slack_event(
            {"type": "message", "team_id": "T1", "channel": "C1", "user": "U1",
             "text": "hi"})
        assert len(execs) == 1 and execs[0].status == "completed"
        auto.search_service.index.assert_awaited_once()

    async def test_handle_event_skips_inactive_and_indexes_files(self):
        auto = make_auto(search=MagicMock())
        auto.search_service.index = AsyncMock()
        auto.register_workflow(wf("dead", active=False))
        # non-indexable event type: no execution, no indexing
        execs = await auto.handle_slack_event({"type": "channel_created",
                                               "team_id": "T"})
        assert execs == []
        auto.search_service.index.assert_not_awaited()
        # file_shared events are indexed even without matching workflows
        await auto.handle_slack_event({"type": "file_shared", "team_id": "T",
                                       "file": {"id": "F"}, "event_ts": "1"})
        auto.search_service.index.assert_awaited_once()

    async def test_handle_event_exception(self):
        auto = make_auto()
        auto._evaluate_trigger = AsyncMock(side_effect=RuntimeError("boom"))
        assert await auto.handle_slack_event({"type": "message"}) == []

    async def test_index_exception_swallowed(self):
        auto = make_auto(search=MagicMock())
        auto.search_service.index = AsyncMock(side_effect=RuntimeError("x"))
        assert await auto._index_slack_content({"type": "message"}) is None

    async def test_index_without_service(self):
        auto = make_auto()
        assert await auto._index_slack_content({"type": "message"}) is None


class TestSlackAutomationHelpers:
    def test_resolve_parameter(self):
        auto = make_auto()
        data = {"user": "bob", "payload": {"a": 1}}
        assert auto._resolve_parameter("hi {user}", data) == "hi bob"
        assert auto._resolve_parameter("p={payload}", data) == 'p={"a": 1}'
        assert auto._resolve_parameter("plain", data) == "plain"
        assert auto._resolve_parameter(None, data) is None

    def test_get_slack_client_token_paths(self):
        auto = make_auto()
        with patch.dict("os.environ", {"SLACK_TOKEN_WS1": "xox-1"}):
            c1 = auto._get_slack_client("WS1")
            assert c1 is not None
            # cached
            assert auto._get_slack_client("WS1") is c1
        assert auto._get_slack_client("NOPE") is None


# ============================================================================
# Slack workflow engine
# ============================================================================

def make_engine(slack=None):
    eng = we.WorkflowExecutionEngine({})
    eng.slack_service = slack
    return eng


def eng_action(aid="a1", atype=None, parameters=None, delay=0, timeout=30,
               continue_on_error=False):
    wrapped = {
        name: p if isinstance(p, we.WorkflowActionParameter)
        else we.WorkflowActionParameter(name=name, value=p)
        for name, p in (parameters or {}).items()
    }
    return we.WorkflowAction(
        id=aid, type=atype or we.WorkflowActionType.SEND_MESSAGE,
        parameters=wrapped, delay=delay, retry_count=0, timeout=timeout,
        continue_on_error=continue_on_error)


def eng_workflow(actions):
    return we.WorkflowDefinition(
        id="wf1", name="WF", description="d",
        triggers=[], actions=actions, created_by="u",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


class TestDataclassesAndTemplates:
    def test_workflow_definition_post_init_defaults(self):
        w = eng_workflow([])
        w2 = we.WorkflowDefinition(
            id="x", name="n", description="d", triggers=[], actions=[],
            created_by="u", created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1))
        assert w2.created_at.tzinfo is timezone.utc
        assert w.tags == [] and w.variables == {} and w.settings == {}

    def test_execution_post_init_defaults(self):
        e = we.WorkflowExecution(
            id="e", workflow_id="w",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime(2026, 1, 1),
            completed_at=datetime(2026, 1, 1))
        assert e.started_at.tzinfo is timezone.utc
        assert e.action_results == [] and e.logs == []

    def test_templates(self):
        assert we.WorkflowTemplate.welcome_message().id == "welcome_message_template"
        assert we.WorkflowTemplate.message_summary().id == "message_summary_template"


class TestEngineExecution:
    async def test_execute_workflow_queues(self):
        eng = make_engine()
        eid = await eng.execute_workflow(eng_workflow([]), {"type": "message"})
        assert eid.startswith("exec_")

    async def test_instance_success_with_delay(self):
        eng = make_engine()
        execution = we.WorkflowExecution(
            id="e1", workflow_id="wf1",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        wfl = eng_workflow([eng_action(delay=1)])
        with patch.object(we.asyncio, "sleep", AsyncMock()), \
             patch.object(eng, "_get_workflow_definition", AsyncMock(return_value=wfl)):
            result = await eng._execute_workflow_instance(execution)
        assert result.status is we.WorkflowExecutionStatus.COMPLETED
        assert result.action_results[0]["status"] == "success"
        assert eng.get_execution_stats()["successful_executions"] == 1

    async def test_instance_definition_not_found(self):
        eng = make_engine()
        execution = we.WorkflowExecution(
            id="e2", workflow_id="wf1",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        with patch.object(eng, "_get_workflow_definition", AsyncMock(return_value=None)):
            result = await eng._execute_workflow_instance(execution)
        assert result.status is we.WorkflowExecutionStatus.FAILED
        assert "not found" in result.error_message

    async def test_instance_action_failure(self):
        eng = make_engine()
        execution = we.WorkflowExecution(
            id="e3", workflow_id="wf1",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        wfl = eng_workflow([eng_action()])
        with patch.object(eng, "_get_workflow_definition", AsyncMock(return_value=wfl)), \
             patch.object(eng, "_execute_action",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            result = await eng._execute_workflow_instance(execution)
        assert result.status is we.WorkflowExecutionStatus.FAILED

    async def test_instance_action_failure_continue_on_error(self):
        eng = make_engine()
        execution = we.WorkflowExecution(
            id="e4", workflow_id="wf1",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        wfl = eng_workflow([eng_action(continue_on_error=True)])
        with patch.object(eng, "_get_workflow_definition", AsyncMock(return_value=wfl)), \
             patch.object(eng, "_execute_action",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            result = await eng._execute_workflow_instance(execution)
        assert result.status is we.WorkflowExecutionStatus.COMPLETED
        assert result.action_results[0]["status"] == "failed"

    async def test_instance_timeout_paths(self):
        eng = make_engine()
        for cont in (False, True):
            execution = we.WorkflowExecution(
                id=f"e-t{cont}", workflow_id="wf1",
                trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
                status=we.WorkflowExecutionStatus.PENDING,
                priority=we.WorkflowExecutionPriority.NORMAL,
                started_at=datetime.now(timezone.utc))
            wfl = eng_workflow([eng_action(timeout=0, continue_on_error=cont)])

            async def slow(exec_, act):
                await asyncio.sleep(5)
            with patch.object(eng, "_get_workflow_definition",
                              AsyncMock(return_value=wfl)), \
                 patch.object(eng, "_execute_action", slow):
                result = await eng._execute_workflow_instance(execution)
            if cont:
                assert result.status is we.WorkflowExecutionStatus.COMPLETED
                assert result.action_results[0]["status"] == "timeout"
            else:
                assert result.status is we.WorkflowExecutionStatus.FAILED
                assert "timed out" in result.error_message

    async def test_history_trim_and_lookup(self):
        eng = make_engine()
        old = we.WorkflowExecution(
            id="old", workflow_id="w",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.COMPLETED,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        eng.execution_history = [old] * 1001
        execution = we.WorkflowExecution(
            id="new", workflow_id="w",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        with patch.object(eng, "_get_workflow_definition",
                          AsyncMock(return_value=eng_workflow([]))):
            await eng._execute_workflow_instance(execution)
        assert len(eng.execution_history) == 1000
        assert eng.get_execution_status("new").id == "new"
        assert eng.get_execution_status("missing") is None
        assert eng.get_workflow_executions("w", limit=1)[0].id == "new"
        eng.running_executions["live"] = MagicMock()
        assert eng.get_execution_status("live").status is we.WorkflowExecutionStatus.RUNNING
        assert eng.cancel_execution("live") is True
        assert eng.cancel_execution("gone") is False

    async def test_cleanup(self):
        eng = make_engine()
        task = MagicMock()
        eng.running_executions["x"] = task
        await eng.cleanup()
        task.cancel.assert_called_once()
        assert eng.running_executions == {}

    async def test_execute_action_missing_handler(self):
        eng = make_engine()
        act = eng_action()
        eng.action_handlers.pop(act.type)
        with pytest.raises(ValueError):
            await eng._execute_action(MagicMock(), act)

    async def test_register_custom_handler_and_unknown(self):
        eng = make_engine()
        handler = AsyncMock(return_value={"custom": True})
        await eng.register_action_handler(we.WorkflowActionType.SEND_MESSAGE, handler)
        assert eng.action_handlers[we.WorkflowActionType.SEND_MESSAGE] is handler
        with pytest.raises(ValueError):
            await eng._handle_unknown_action(MagicMock(), eng_action())

    def test_default_handler_map(self):
        eng = make_engine()
        for atype in we.WorkflowActionType:
            assert eng.action_handlers[atype] is not eng._handle_unknown_action


class TestEngineVariablesTemplates:
    async def test_process_variables_substitutes(self):
        eng = make_engine()
        execution = we.WorkflowExecution(
            id="e", workflow_id="w",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        act = eng_action(parameters={"message": we.WorkflowActionParameter(
            name="message", value="Hello {{trigger.user_name}} / {{missing}}" )})
        await eng._process_variables(execution, eng_workflow([act]),
                                     {"user_name": "Bob"})
        assert act.parameters["message"].value == "Hello Bob / "

    async def test_substitute_template_paths(self):
        eng = make_engine()
        assert await eng._substitute_template(
            "a {{x.y}} b", {"x": {"y": 7}}) == "a 7 b"
        with patch.object(we.re, "sub", side_effect=RuntimeError("nope")):
            assert await eng._substitute_template("t", {}) == "t"

    def test_get_nested_variable(self):
        eng = make_engine()
        assert eng._get_nested_variable({"a": {"b": 1}}, "a.b") == 1
        assert eng._get_nested_variable({"a": 1}, "a.z", "d") == "d"
        assert eng._get_nested_variable("notdict", "a", "d") == "d"

    def test_log_execution_trim(self):
        eng = make_engine()
        execution = we.WorkflowExecution(
            id="e", workflow_id="w",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        for i in range(105):
            eng._log_execution(execution, "info", f"m{i}")
        assert len(execution.logs) == 100


class TestEngineHandlers:
    async def _handle(self, atype, params, slack=None, trigger=None):
        eng = make_engine(slack=slack)
        execution = MagicMock()
        execution.trigger_data = trigger or {}
        handler = eng.action_handlers[atype]
        return await handler(execution, eng_action(atype=atype, parameters=params))

    async def test_send_message_slack_ok(self):
        slack = MagicMock()
        slack.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        r = await self._handle(we.WorkflowActionType.SEND_MESSAGE,
                               {"channel": "C1", "message": "hi"},
                               slack=slack, trigger={"workspace_id": "W"})
        assert r["method"] == "slack_api"

    async def test_send_message_slack_not_ok_and_exception(self):
        slack = MagicMock()
        slack.send_message = AsyncMock(return_value={"ok": False})
        r = await self._handle(we.WorkflowActionType.SEND_MESSAGE,
                               {"channel": "C1", "message": "hi"},
                               slack=slack, trigger={"workspace_id": "W"})
        assert r["method"] == "mock"
        slack.send_message = AsyncMock(side_effect=RuntimeError("x"))
        r = await self._handle(we.WorkflowActionType.SEND_MESSAGE,
                               {"channel": "C1", "message": "hi"},
                               slack=slack, trigger={"workspace_id": "W"})
        assert r["method"] == "mock"

    async def test_simple_mock_handlers(self):
        cases = [
            (we.WorkflowActionType.SEND_MESSAGE, {"channel": "C", "message": "m"}),
            (we.WorkflowActionType.SEND_DM, {"user_id": "U", "message": "m"}),
            (we.WorkflowActionType.CREATE_CHANNEL, {"name": "n"}),
            (we.WorkflowActionType.INVITE_USER, {"channel": "C", "user_ids": "U1"}),
            (we.WorkflowActionType.ADD_REACTION,
             {"channel": "C", "message_ts": "1", "emoji": ":x:"}),
            (we.WorkflowActionType.PIN_MESSAGE, {"channel": "C", "message_ts": "1"}),
            (we.WorkflowActionType.CREATE_TASK, {"title": "t", "description": "d"}),
            (we.WorkflowActionType.UPDATE_STATUS, {"status": "s", "emoji": ":e:"}),
            (we.WorkflowActionType.CALL_API,
             {"endpoint": "/x", "method": "POST", "headers": {}, "data": {}}),
            (we.WorkflowActionType.SEND_EMAIL,
             {"to": "a@b.c", "subject": "s", "body": "b"}),
            (we.WorkflowActionType.EXECUTE_SCRIPT,
             {"script": "ls", "args": ["-l"]}),
            (we.WorkflowActionType.UPDATE_SPREADSHEET,
             {"spreadsheet_id": "s", "range": "A1", "values": [1, 2]}),
            (we.WorkflowActionType.CREATE_MEETING,
             {"title": "t", "attendees": ["a"], "start_time": "s", "duration": 30}),
        ]
        for atype, params in cases:
            r = await self._handle(atype, params)
            assert r, atype

    async def test_slack_api_paths_for_all_service_actions(self):
        ok = {"ok": True}
        slack = MagicMock()
        slack.send_message = AsyncMock(return_value=ok)
        slack.send_dm = AsyncMock(return_value=ok)
        slack.create_channel = AsyncMock(return_value=ok)
        slack.invite_to_channel = AsyncMock(return_value=ok)
        slack.add_reaction = AsyncMock(return_value=ok)
        slack.pin_message = AsyncMock(return_value=ok)
        cases = [
            (we.WorkflowActionType.SEND_MESSAGE, {"channel": "C", "message": "m"}),
            (we.WorkflowActionType.SEND_DM, {"user_id": "U", "message": "m"}),
            (we.WorkflowActionType.CREATE_CHANNEL, {"name": "n"}),
            (we.WorkflowActionType.INVITE_USER, {"channel": "C", "user_ids": ["U"]}),
            (we.WorkflowActionType.ADD_REACTION,
             {"channel": "C", "message_ts": "1", "emoji": ":x:"}),
            (we.WorkflowActionType.PIN_MESSAGE, {"channel": "C", "message_ts": "1"}),
        ]
        for atype, params in cases:
            r = await self._handle(atype, params, slack=slack,
                                   trigger={"workspace_id": "W"})
            assert r["method"] == "slack_api", atype

    async def test_worker_loop_executes_queued(self):
        eng = make_engine()
        execution = we.WorkflowExecution(
            id="w-e1", workflow_id="wf1",
            trigger_type=we.WorkflowTriggerType.MESSAGE, trigger_data={},
            status=we.WorkflowExecutionStatus.PENDING,
            priority=we.WorkflowExecutionPriority.NORMAL,
            started_at=datetime.now(timezone.utc))
        with patch.object(eng, "_get_workflow_definition",
                          AsyncMock(return_value=eng_workflow([]))):
            worker = asyncio.create_task(eng._execution_worker("w0"))
            await eng.execution_queue.put((2, execution))
            for _ in range(100):
                if eng.execution_history:
                    break
                await asyncio.sleep(0.02)
            worker.cancel()
            assert eng.execution_history[0].status is we.WorkflowExecutionStatus.COMPLETED


# ============================================================================
# Slack routes
# ============================================================================

def slack_sig(secret, body: bytes, ts=None):
    ts = str(int(time.time()) if ts is None else ts)
    base = f"v0:{ts}:{body.decode()}"
    sig = "v0=" + hmac_mod.new(secret.encode(), base.encode(),
                               hashlib.sha256).hexdigest()
    return {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig}


def interactive_payload(payload: dict, secret="sekrit"):
    body = "payload=" + json.dumps(payload)
    return body.encode(), slack_sig(secret, body.encode())


class TestSlackRoutesBasic:
    def test_status_mock_mode(self):
        with patch.object(sl, "get_slack_client", return_value=None):
            r = make_client(sl).get("/api/slack/status")
        assert r.json()["status"] == "mock_mode"

    def test_status_connected(self):
        with patch.object(sl, "get_slack_client", return_value=MagicMock()), \
             patch.object(sl, "SLACK_SDK_AVAILABLE", True):
            r = make_client(sl).get("/api/slack/health")
        assert r.json()["status"] == "connected"

    def test_channels_users_reactions(self):
        c = make_client(sl)
        assert c.get("/api/slack/channels").json()["total_channels"] == 7
        assert c.get("/api/slack/channels/C123").json()["name"] == "Channel C123"
        assert c.get("/api/slack/users/U1").json()["user"]["id"] == "U1"
        assert c.get("/api/slack/users/bot1").json()["user"]["is_bot"] is True
        r = c.post("/api/slack/reactions/add?channel=C1&timestamp=1&reaction=:x:")
        assert r.json()["ok"] is True


class TestSlackMessages:
    def _post(self, client_mock):
        with patch.object(sl, "get_slack_client", return_value=client_mock):
            return make_client(sl).post(
                "/api/slack/messages",
                json={"channel": "C1", "text": "hi", "user_id": "u1"})

    def test_real_client_success(self):
        client = MagicMock()
        client.chat_postMessage.return_value = {"channel": "C1", "ts": "123"}
        r = self._post(client)
        assert r.json()["ok"] is True and r.json()["message_id"] == "123"

    def test_real_client_slack_api_error_400(self):
        from slack_sdk.errors import SlackApiError
        client = MagicMock()
        err = SlackApiError("fail", {"error": "channel_not_found"})
        client.chat_postMessage.side_effect = err
        r = self._post(client)
        assert r.status_code == 400

    def test_mock_fallback(self):
        r = self._post(None)
        assert r.json()["ok"] is True and r.json()["message_id"].startswith("msg_")

    def test_governance_blocked_403(self):
        with patch.object(sl, "with_governance_check",
                          AsyncMock(return_value=(None, {"allowed": False,
                                                         "reason": "no"}))):
            r = make_client(sl).post("/api/slack/messages?agent_id=ag1",
                                     json={"channel": "C1", "text": "hi"})
        assert r.status_code == 403

    def test_governance_exception_degrades(self):
        with patch.object(sl, "with_governance_check",
                          AsyncMock(side_effect=RuntimeError("gov"))), \
             patch.object(sl, "create_execution_record", MagicMock()), \
             patch.object(sl, "get_slack_client", return_value=None):
            r = make_client(sl).post("/api/slack/messages?agent_id=ag1",
                                     json={"channel": "C1", "text": "hi"})
        assert r.json()["ok"] is True


class TestSlackSearchHistory:
    def _ingest(self, exc=None):
        import integrations.atom_ingestion_pipeline as aip
        pipe = MagicMock()
        pipe.ingest_record = AsyncMock(side_effect=exc)
        return patch.object(aip, "atom_ingestion_pipeline", pipe)

    def test_search_with_ingestion(self):
        with self._ingest(exc=RuntimeError("swallow")):
            r = make_client(sl).post("/api/slack/search",
                                     json={"query": "deploy", "max_results": 2})
        assert r.json()["total_results"] == 2

    def test_search_governance_blocked(self):
        with patch.object(sl, "with_governance_check",
                          AsyncMock(return_value=(None, {"allowed": False,
                                                         "reason": "no"}))):
            r = make_client(sl).post("/api/slack/search?agent_id=ag1",
                                     json={"query": "x"})
        assert r.status_code == 403

    def test_history(self):
        with self._ingest():
            r = make_client(sl).get(
                "/api/slack/conversations/history?channel=C1&limit=3")
        assert len(r.json()["messages"]) == 3

    def test_history_governance_blocked(self):
        with patch.object(sl, "with_governance_check",
                          AsyncMock(return_value=(None, {"allowed": False,
                                                         "reason": "no"}))):
            r = make_client(sl).get(
                "/api/slack/conversations/history?channel=C1&agent_id=ag1")
        assert r.status_code == 403

    def test_history_governance_exception(self):
        with patch.object(sl, "with_governance_check",
                          AsyncMock(side_effect=RuntimeError("gov"))), \
             self._ingest():
            r = make_client(sl).get(
                "/api/slack/conversations/history?channel=C1&agent_id=ag1")
        assert r.json()["ok"] is True


class TestSlackInteractive:
    def _post(self, payload_body, headers=None, secret="sekrit", path="/api/slack/interactive"):
        with patch.object(sl, "SLACK_SIGNING_SECRET", secret):
            return make_client(sl).post(path, content=payload_body,
                                        headers={"content-type":
                                                 "application/x-www-form-urlencoded",
                                                 **(headers or {})})

    def test_signature_verify_helper(self):
        ts = str(int(time.time()))
        with patch.object(sl, "SLACK_SIGNING_SECRET", "sekrit"):
            ok, _ = sl._verify_slack_signature(
                b"payload=x", ts, slack_sig("sekrit", b"payload=x", ts=ts)
                ["X-Slack-Signature"])
            assert ok is True
            bad, _ = sl._verify_slack_signature(b"payload=x", "1", "v0=bad")
            assert bad is False
            old_ts = str(int(time.time()) - 1000)
            old, _ = sl._verify_slack_signature(b"x", old_ts, "v0=x")
            assert old is False
            future, _ = sl._verify_slack_signature(
                b"x", str(int(time.time()) + 120), "v0=x")
            assert future is False
            nosec, _ = sl._verify_slack_signature(b"x", "abc", "v0=x")
            assert nosec is False

    def test_rate_limited_returns_200(self):
        body, headers = interactive_payload({"type": "block_actions"})
        with patch.object(sl, "_check_rate_limit", return_value=False):
            r = self._post(body, headers)
        assert r.status_code == 200 and r.json() == {"ok": True}

    def test_fail_closed_without_secret(self):
        body, headers = interactive_payload({"type": "block_actions"})
        r = self._post(body, headers, secret="")
        assert r.json() == {"ok": True}

    def test_bad_signature_rejected(self):
        body, _ = interactive_payload({"type": "block_actions"})
        r = self._post(body, {"X-Slack-Request-Timestamp": "1",
                              "X-Slack-Signature": "v0=bad"})
        assert r.json() == {"ok": True}

    def test_missing_payload_field(self):
        body = b"other=1"
        r = self._post(body, slack_sig("sekrit", body))
        assert r.json() == {"ok": True}

    def test_invalid_payload_json(self):
        body = b"payload=not-json"
        r = self._post(body, slack_sig("sekrit", body))
        assert r.json() == {"ok": True}

    def test_unexpected_payload_type(self):
        body, headers = interactive_payload({"type": "mystery"})
        r = self._post(body, headers)
        assert r.json() == {"ok": True}

    def test_valid_block_actions_dispatch(self):
        body, headers = interactive_payload({
            "type": "block_actions", "user": {"id": "U1"},
            "trigger_id": "trg",
            "actions": [{"action_id": "approve"}, {"action_id": "other"}]})
        handler = MagicMock(return_value={"done": True})
        with patch.dict(sl._SLACK_ACTION_HANDLERS, {"approve": handler}):
            r = self._post(body, headers)
        assert r.json() == {"ok": True}
        handler.assert_called_once()
        # handler raising is caught by dispatcher
        boom = MagicMock(side_effect=RuntimeError("boom"))
        with patch.dict(sl._SLACK_ACTION_HANDLERS, {"approve": boom}):
            r = self._post(body, headers)
        assert r.json() == {"ok": True}

    def test_dispatcher_direct(self):
        assert sl._dispatch_slack_action({}, {"id": "U"}, "t")["status"] == "unhandled"
        res = sl._dispatch_slack_action({"action_id": "a"}, {"id": "U"}, "t")
        assert res["status"] == "unhandled" and res["action_id"] == "a"

    def test_rate_limit_helper(self):
        assert sl._check_rate_limit("ip-a") is True
        sl._rate_limit_store["ip-b"].extend([time.time()] * sl._RATE_LIMIT_MAX)
        assert sl._check_rate_limit("ip-b") is False


class TestSlackOAuth:
    def test_auth_url(self):
        mgr = MagicMock()
        mgr.generate_state.return_value = "state123"
        handler = MagicMock()
        handler.get_authorization_url.return_value = "https://slack/auth"
        with patch.object(sl, "get_oauth_state_manager", return_value=mgr), \
             patch.object(sl, "OAuthHandler", return_value=handler):
            r = make_client(sl).get("/api/slack/auth/url")
        assert r.json()["url"] == "https://slack/auth"
        assert r.json()["state"] == "state123"

    def test_auth_url_error_500(self):
        with patch.object(sl, "get_oauth_state_manager",
                          side_effect=RuntimeError("boom")):
            r = make_client(sl).get("/api/slack/auth/url")
        assert r.status_code == 500

    def test_callback_missing_code_and_state(self):
        c = make_client(sl)
        assert c.post("/api/slack/callback", json={}).status_code == 400
        assert c.post("/api/slack/callback",
                      json={"code": "c"}).status_code == 400

    def test_callback_invalid_state(self):
        mgr = MagicMock()
        mgr.validate_state.side_effect = ValueError("tampered")
        with patch.object(sl, "get_oauth_state_manager", return_value=mgr):
            r = make_client(sl).post("/api/slack/callback",
                                     json={"code": "c", "state": "s"})
        assert r.status_code == 400

    def test_callback_success(self):
        mgr = MagicMock()
        mgr.validate_state.return_value = {"user_id": "user-1"}
        handler = MagicMock()
        handler.exchange_code_for_tokens = AsyncMock(
            return_value={"access_token": "xox"})
        conn_svc = MagicMock()
        conn_svc.return_value.save_connection.return_value = SimpleNamespace(
            id="conn-1")
        import core.connection_service as cs
        with patch.object(sl, "get_oauth_state_manager", return_value=mgr), \
             patch.object(sl, "OAuthHandler", return_value=handler), \
             patch.dict(sys_modules(), {}), \
             patch.object(cs, "ConnectionService", conn_svc):
            r = make_client(sl).post("/api/slack/callback",
                                     json={"code": "c", "state": "s"})
        assert r.json()["connection_id"] == "conn-1"

    def test_callback_generic_error_500(self):
        with patch.object(sl, "get_oauth_state_manager",
                          side_effect=RuntimeError("boom")):
            r = make_client(sl).post("/api/slack/callback",
                                     json={"code": "c", "state": "s"})
        assert r.status_code == 500


def sys_modules():
    import sys
    return sys.modules


# ============================================================================
# GitHub routes
# ============================================================================

GH_TOKENS = {"access_token": "tok", "user_info": {"login": "dev", "id": "1"}}


def gh_client(tokens=GH_TOKENS, available=True):
    c = make_client(gr)
    gr._token_patcher = patch.object(gr, "get_github_tokens", return_value=tokens)
    gr._avail_patcher = patch.object(gr, "GITHUB_AVAILABLE", available)
    gr._token_patcher.start()
    gr._avail_patcher.start()
    return c


@pytest.fixture
def gh_svc():
    svc = MagicMock()
    svc.test_connection.return_value = {"ok": True}
    svc.get_user_repositories.return_value = [{
        "id": 1, "name": "r", "full_name": "o/r", "private": True,
        "owner": {"login": "o", "avatar_url": "a"}, "topics": [], "fork": False}]
    svc.get_repository_issues.return_value = [{
        "id": 2, "number": 1, "title": "bug", "user": {"login": "u"},
        "assignee": {"login": "a"}, "assignees": [{"login": "b"}], "labels": []}]
    svc.get_repository_pulls.return_value = [{"id": 3, "number": 5, "title": "pr"}]
    svc.create_issue.return_value = {"id": 4, "number": 2, "html_url": "u"}
    svc.create_pull_request.return_value = {"id": 5, "number": 6,
                                            "html_url": "u", "diff_url": "d"}
    svc.search_repositories.return_value = {"ok": True, "data": []}
    with patch.object(gr, "github_service", svc):
        yield svc


class TestGithubHealth:
    def test_healthy(self):
        with patch.object(gr, "GITHUB_AVAILABLE", True), \
             patch.object(gr, "github_service", MagicMock(
                 test_connection=lambda: {"ok": True})):
            r = make_client(gr).get("/api/github/health")
        assert r.json()["ok"] is True

    def test_unavailable(self):
        with patch.object(gr, "GITHUB_AVAILABLE", False):
            r = make_client(gr).get("/api/github/health")
        assert r.json()["status"] == "unhealthy"

    def test_degraded(self):
        with patch.object(gr, "GITHUB_AVAILABLE", True), \
             patch.object(gr, "github_service", MagicMock(
                 test_connection=MagicMock(side_effect=RuntimeError("x")))):
            r = make_client(gr).get("/api/github/health")
        assert r.json()["status"] == "degraded"


class TestGithubTokens:
    def test_db_token_success(self):
        rec = MagicMock(expires_at=None, access_token="enc", token_type="bearer",
                        scope="repo", user_info={"login": "d"})
        db = mock_db(rec)
        with patch.object(gr, "OAUTH_STRICT_MODE", True):
            tokens = gr.get_github_tokens("u1", db=db)
        assert tokens["access_token"] == "enc" and tokens["source"] == "database"

    def test_expired_token_strict_401(self):
        rec = MagicMock(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        db = mock_db(rec)
        with patch.object(gr, "OAUTH_STRICT_MODE", True):
            with pytest.raises(HTTPException) as ei:
                gr.get_github_tokens("u1", db=db)
        assert ei.value.status_code == 401

    def test_expired_token_non_strict_returns_none(self):
        rec = MagicMock(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        db = mock_db(rec)
        with patch.object(gr, "OAUTH_STRICT_MODE", False):
            assert gr.get_github_tokens("u1", db=db) is None

    def test_env_fallback_no_record_non_strict(self):
        db = mock_db(None)
        with patch.object(gr, "OAUTH_STRICT_MODE", False), \
             patch.dict("os.environ", {"GITHUB_ACCESS_TOKEN": "env-tok"}):
            tokens = gr.get_github_tokens("u1", db=db)
        assert tokens["access_token"] == "env-tok"
        assert tokens["source"] == "environment"

    def test_no_token_strict_401(self):
        db = mock_db(None)
        with patch.object(gr, "OAUTH_STRICT_MODE", True):
            with pytest.raises(HTTPException) as ei:
                gr.get_github_tokens("u1", db=db)
        assert ei.value.status_code == 401

    def test_no_token_non_strict_none(self):
        db = mock_db(None)
        with patch.object(gr, "OAUTH_STRICT_MODE", False):
            assert gr.get_github_tokens("u1", db=db) is None

    def test_db_query_error_falls_through_to_strict_401(self):
        # Inner query exception is logged; strict mode then fails closed 401.
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with patch.object(gr, "OAUTH_STRICT_MODE", True):
            with pytest.raises(HTTPException) as ei:
                gr.get_github_tokens("u1", db=db)
        assert ei.value.status_code == 401


class TestGithubRepos:
    def test_list_success(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/repositories",
                       json={"user_id": "hacker"})
        finally:
            teardown_gh()
        assert r.json()["ok"] is True
        assert r.json()["data"]["repositories"][0]["visibility"] == "private"
        # user_id pinned to authenticated user
        assert gh_svc.get_user_repositories.called

    def test_list_unavailable_503(self):
        c = gh_client(available=False)
        try:
            r = c.post("/api/github/repositories", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.status_code == 503

    def test_list_no_tokens_401(self):
        c = gh_client(tokens=None)
        try:
            r = c.post("/api/github/repositories", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.status_code == 401

    def test_list_operation_create_missing_name_422(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/repositories",
                       json={"user_id": "u", "operation": "create"})
        finally:
            teardown_gh()
        assert r.status_code == 422

    def test_list_operation_create_delegates(self, gh_svc):
        session = MagicMock()
        resp = MagicMock()
        resp.json.return_value = {"id": 9, "name": "new", "private": False,
                                  "owner": {"login": "o"}}
        session.post.return_value = resp
        gh_svc.session = session
        gh_svc.base_url = "https://api.github.com"
        c = gh_client()
        try:
            r = c.post("/api/github/repositories",
                       json={"user_id": "u", "operation": "create", "name": "new"})
        finally:
            teardown_gh()
        assert r.json()["ok"] is True

    def test_create_endpoint(self, gh_svc):
        session = MagicMock()
        resp = MagicMock()
        resp.json.return_value = {"id": 10, "name": "repo2", "private": True}
        session.post.return_value = resp
        gh_svc.session = session
        gh_svc.base_url = "https://api.github.com"
        c = gh_client()
        try:
            r = c.post("/api/github/repositories/create",
                       json={"user_id": "u", "name": "repo2"})
        finally:
            teardown_gh()
        assert r.json()["data"]["repository"]["repo_id"] == 10

    def test_create_http_error_500(self, gh_svc):
        session = MagicMock()
        session.post.side_effect = RuntimeError("boom")
        gh_svc.session = session
        gh_svc.base_url = "https://api.github.com"
        c = gh_client()
        try:
            r = c.post("/api/github/repositories/create",
                       json={"user_id": "u", "name": "x"})
        finally:
            teardown_gh()
        assert r.status_code == 500

    def test_list_generic_error_500(self, gh_svc):
        gh_svc.get_user_repositories.side_effect = RuntimeError("x")
        c = gh_client()
        try:
            r = c.post("/api/github/repositories", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.status_code == 500


def teardown_gh():
    try:
        gr._token_patcher.stop()
        gr._avail_patcher.stop()
    except Exception:
        pass


class TestGithubIssuesPullsSearchProfile:
    def test_list_issues(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/issues", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.json()["ok"] is True
        assert r.json()["data"]["issues"][0]["assignee"]["login"] == "a"

    def test_list_issues_unavailable_and_no_tokens(self):
        c = gh_client(available=False)
        try:
            r = c.post("/api/github/issues", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.status_code == 503
        c = gh_client(tokens=None)
        try:
            r = c.post("/api/github/issues", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.status_code == 401

    def test_issues_create_via_operation_422_then_delegate(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/issues",
                       json={"user_id": "u", "operation": "create"})
            assert r.status_code == 422
            r = c.post("/api/github/issues",
                       json={"user_id": "u", "operation": "create", "title": "t"})
            assert r.json()["ok"] is True
        finally:
            teardown_gh()

    def test_create_issue_endpoint(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/issues/create",
                       json={"user_id": "u", "title": "t"})
        finally:
            teardown_gh()
        assert r.json()["data"]["issue"]["issue_id"] == 4

    def test_create_issue_empty_result_500(self, gh_svc):
        gh_svc.create_issue.return_value = None
        c = gh_client()
        try:
            r = c.post("/api/github/issues/create",
                       json={"user_id": "u", "title": "t"})
        finally:
            teardown_gh()
        assert r.status_code == 500

    def test_list_pulls(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/pulls", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.json()["ok"] is True

    def test_pulls_create_via_operation(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/pulls",
                       json={"user_id": "u", "operation": "create",
                             "title": "t"})
            assert r.status_code == 422  # missing head
            r = c.post("/api/github/pulls",
                       json={"user_id": "u", "operation": "create",
                             "title": "t", "head": "branch"})
            assert r.json()["ok"] is True
        finally:
            teardown_gh()

    def test_create_pull_endpoint(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/pulls/create",
                       json={"user_id": "u", "title": "t", "head": "h"})
        finally:
            teardown_gh()
        assert r.json()["data"]["pull_request"]["pr_id"] == 5

    def test_create_pull_empty_result_500(self, gh_svc):
        gh_svc.create_pull_request.return_value = None
        c = gh_client()
        try:
            r = c.post("/api/github/pulls/create",
                       json={"user_id": "u", "title": "t", "head": "h"})
        finally:
            teardown_gh()
        assert r.status_code == 500

    def test_list_pulls_error_500(self, gh_svc):
        gh_svc.get_repository_pulls.side_effect = RuntimeError("x")
        c = gh_client()
        try:
            r = c.post("/api/github/pulls", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.status_code == 500

    def test_search(self, gh_svc):
        c = gh_client()
        try:
            r = c.post("/api/github/search",
                       json={"user_id": "u", "query": "atom"})
        finally:
            teardown_gh()
        assert r.json()["ok"] is True

    def test_search_error_500(self, gh_svc):
        gh_svc.search_repositories.side_effect = RuntimeError("x")
        c = gh_client()
        try:
            r = c.post("/api/github/search",
                       json={"user_id": "u", "query": "atom"})
        finally:
            teardown_gh()
        assert r.status_code == 500

    def test_profile(self):
        c = gh_client()
        try:
            r = c.post("/api/github/user/profile", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.json()["data"]["user"]["login"] == "dev"

    def test_profile_missing_user_info_500(self):
        # tokens without 'user_info' key -> KeyError inside handler -> 500
        c = gh_client(tokens={"access_token": "t"})
        try:
            r = c.post("/api/github/user/profile", json={"user_id": "u"})
        finally:
            teardown_gh()
        assert r.status_code == 500

    def test_issues_unavailable_503_create_endpoint(self):
        c = gh_client(available=False)
        try:
            assert c.post("/api/github/issues/create",
                          json={"user_id": "u", "title": "t"}).status_code == 503
            assert c.post("/api/github/pulls/create",
                          json={"user_id": "u", "title": "t",
                                "head": "h"}).status_code == 503
            assert c.post("/api/github/search",
                          json={"user_id": "u", "query": "q"}).status_code == 503
            assert c.post("/api/github/user/profile",
                          json={"user_id": "u"}).status_code == 503
            assert c.post("/api/github/repositories/create",
                          json={"user_id": "u", "name": "n"}).status_code == 503
        finally:
            teardown_gh()
