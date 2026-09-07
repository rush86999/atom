# -*- coding: utf-8 -*-
"""Coverage wave 88 — core.hybrid_data_ingestion, core.agent_world_model,
core.atom_meta_agent.

No network, no LLM: all integration/LLM boundaries are mocked; LanceDB
handlers and DB sessions are plain fakes/mocks.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.hybrid_data_ingestion as hybrid_mod
from core.hybrid_data_ingestion import (
    HybridDataIngestionService,
    SyncConfiguration,
    SyncMode,
    record_integration_call,
)
import core.agent_world_model as wm_mod
from core.agent_world_model import (
    AgentExperience,
    BusinessFact,
    DetailLevel,
    WorldModelService,
)
import core.atom_meta_agent as ama
from core.atom_meta_agent import (
    AtomMetaAgent,
    IntentCategory,
    ToolCall,
    handle_data_event_trigger,
    handle_manual_trigger,
)

DT = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


# ============================================================================
# HYBRID DATA INGESTION — fixtures
# ============================================================================

class FakeLance:
    def __init__(self):
        self.workspace_id = "ws"
        self.db = object()
        self.add_document = Mock(return_value=True)
        self.search = Mock(return_value=[])


class FakeGraphrag:
    def __init__(self, result=None):
        self.ingest_document = AsyncMock(return_value=result or {"entities": 2, "relationships": 1})


@pytest.fixture()
def ing():
    with patch("core.lancedb_handler.get_lancedb_handler", return_value=None), \
         patch("core.graphrag_engine.GraphRAGEngine", side_effect=ImportError), \
         patch("core.llm_service.get_llm_service", side_effect=ImportError):
        svc = HybridDataIngestionService(workspace_id="ws", tenant_id="t1")
    svc.memory_handler = FakeLance()
    return svc


def cfg(integration_id="zoho", entity_types=None, max_records=1000, **kw):
    return SyncConfiguration(
        integration_id=integration_id,
        entity_types=entity_types if entity_types is not None else ["records"],
        max_records_per_sync=max_records, **kw)


# ============================================================================
# HYBRID — usage tracking / auto-sync
# ============================================================================

def test_hybrid_record_usage_and_auto_enable_threshold(ing):
    # Auto-sync defaults ON; the usage threshold only governs RE-enabling
    # after an explicit opt-out.
    ing.AUTO_SYNC_USAGE_THRESHOLD = 3
    ing.record_integration_usage("zoho", "Zoho", success=True, user_id="u1")
    ing.disable_auto_sync("zoho")
    ing.record_integration_usage("zoho", "Zoho", success=True, user_id="u1")
    # total_calls 2 < threshold 3 -> stays opted out
    assert not ing.usage_stats["zoho"].auto_sync_enabled
    ing.record_integration_usage("zoho", "Zoho", success=False)
    # threshold reached -> auto-enabled with default config
    assert ing.usage_stats["zoho"].auto_sync_enabled is True
    from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS
    assert ing.sync_configs["zoho"].entity_types == \
        DEFAULT_SYNC_CONFIGS["zoho"].entity_types
    st = ing.usage_stats["zoho"]
    assert st.total_calls == 3 and st.successful_calls == 2


def test_hybrid_enable_auto_sync_custom_and_basic(ing):
    ing.enable_auto_sync("custom1", config=cfg("custom1"))
    assert ing.sync_configs["custom1"].integration_id == "custom1"
    ing.enable_auto_sync("brand_new")  # not in defaults -> basic config
    assert ing.sync_configs["brand_new"].entity_types == ["records"]
    ing.enable_auto_sync("slack")  # default config
    assert ing.sync_configs["slack"].integration_id == "slack"


def test_hybrid_disable_auto_sync_cancels_task(ing):
    ing.enable_auto_sync("zoho")
    # A MagicMock task keeps this a sync test — ensure_future needs a
    # running loop, which sync pytest tests don't have (py3.10+).
    task = MagicMock()
    ing._sync_tasks["zoho"] = task
    ing.disable_auto_sync("zoho")
    assert ing.usage_stats["zoho"].auto_sync_enabled is False
    assert "zoho" not in ing._sync_tasks
    task.cancel.assert_called_once()
    ing.disable_auto_sync("unknown")  # no-op branch


def test_hybrid_check_auto_enable_no_stats(ing):
    assert ing._check_auto_enable_sync("nope") is None


def test_hybrid_usage_summary(ing):
    ing.record_integration_usage("zoho", "Zoho")
    ing.usage_stats["zoho"].last_synced = DT
    s = ing.get_usage_summary()
    assert s["workspace_id"] == "ws"
    assert s["integrations"][0]["name"] == "Zoho"
    assert s["integrations"][0]["last_synced"] == DT.isoformat()


def test_hybrid_singleton_and_record_call(ing, monkeypatch):
    hybrid_mod._ingestion_service = None
    with patch.object(HybridDataIngestionService, "__init__", lambda self, *a, **k: None):
        s1 = hybrid_mod.get_hybrid_ingestion_service("default")
        s1.workspace_id = "default"  # init was stubbed
        s2 = hybrid_mod.get_hybrid_ingestion_service("default")
        assert s1 is s2
        s1.record_integration_usage = Mock()
        record_integration_call("zoho", "Zoho", success=True, user_id="u")
        assert s1.record_integration_usage.called
    hybrid_mod._ingestion_service = None


# ============================================================================
# HYBRID — sync_integration_data
# ============================================================================

def _syncable(ing, integration_id="zoho"):
    ing.record_integration_usage(integration_id, "X")
    ing.enable_auto_sync(integration_id)


async def test_hybrid_sync_no_config_and_skip(ing):
    assert (await ing.sync_integration_data("none"))["error"].startswith("No sync config")
    _syncable(ing)
    ing.usage_stats["zoho"].last_synced = datetime.now(timezone.utc)
    ing.usage_stats["zoho"].sync_frequency_minutes = 60
    res = await ing.sync_integration_data("zoho")
    assert res == {"skipped": True, "reason": "Recently synced"}


async def test_hybrid_sync_success_with_schema_discovery(ing, monkeypatch):
    _syncable(ing, "ab")  # short id so "X from ab" < 10 chars -> skipped
    ing.graphrag = FakeGraphrag()
    records = [
        {"id": "r1", "type": "crm:lead", "name": "A very long lead name here",
         "email": "a@b.com"},
        {"id": "r2", "type": "z"},  # "Z from ab" -> text too short -> skipped
        {"id": "r3", "type": "crm:lead", "name": "Second long record name ok"},
    ]
    ing._fetch_integration_data = AsyncMock(return_value=records)

    et = MagicMock()
    monkeypatch.setattr("core.entity_type_service.EntityTypeService", et)
    sl = MagicMock()
    monkeypatch.setattr("core.database.SessionLocal", sl)
    monkeypatch.setattr(hybrid_mod, "SessionLocal", sl)
    ing._discover_schema = AsyncMock(return_value={"type": "object"})

    res = await ing.sync_integration_data("ab")
    assert res["success"] is True
    assert res["records_fetched"] == 3
    assert res["records_ingested"] == 2
    assert res["entities_extracted"] == 4
    assert et.return_value.resolve_or_create_draft.called
    assert ing.usage_stats["ab"].last_synced is not None


async def test_hybrid_sync_schema_discovery_failure_tolerated(ing, monkeypatch):
    _syncable(ing)
    ing.memory_handler = None
    ing.graphrag = None
    ing._fetch_integration_data = AsyncMock(return_value=[
        {"id": "r1", "type": "lead", "name": "Long enough name for text"}])
    monkeypatch.setattr("core.entity_type_service.EntityTypeService",
                        MagicMock(side_effect=RuntimeError("boom")))
    sl = MagicMock()
    monkeypatch.setattr("core.database.SessionLocal", sl)
    monkeypatch.setattr(hybrid_mod, "SessionLocal", sl)
    res = await ing.sync_integration_data("zoho", force=True)
    assert res["success"] is True


async def test_hybrid_sync_majority_errors_partial(ing):
    _syncable(ing)
    ing._fetch_integration_data = AsyncMock(return_value=[
        {"id": "r1", "type": "lead", "name": "Long enough name one"},
        {"id": "r2", "type": "lead", "name": "Long enough name two"},
    ])
    ing.memory_handler.add_document = Mock(side_effect=RuntimeError("db down"))
    ing.graphrag = None
    res = await ing.sync_integration_data("zoho", force=True)
    assert res["success"] is False and res["partial"] is True
    assert len(res["errors"]) == 2
    assert ing.usage_stats["zoho"].last_synced is None  # not marked synced


async def test_hybrid_sync_minority_errors_partial_success(ing):
    _syncable(ing)
    recs = [{"id": f"r{i}", "type": "lead", "name": f"Long enough name number {i}"}
            for i in range(4)]
    ing._fetch_integration_data = AsyncMock(return_value=recs)
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("one-off")
        return True

    ing.memory_handler.add_document = Mock(side_effect=flaky)
    ing.graphrag = None
    res = await ing.sync_integration_data("zoho", force=True)
    assert res["success"] is True and res["partial"] is True
    assert ing.usage_stats["zoho"].last_synced is not None


async def test_hybrid_sync_fetch_raises(ing):
    _syncable(ing)
    ing._fetch_integration_data = AsyncMock(side_effect=RuntimeError("explode"))
    res = await ing.sync_integration_data("zoho", force=True)
    assert res["success"] is False and "explode" in res["error"]


async def test_hybrid_sync_zero_records(ing):
    _syncable(ing)
    ing._fetch_integration_data = AsyncMock(return_value=[])
    res = await ing.sync_integration_data("zoho", force=True)
    assert res["success"] is True


# ============================================================================
# HYBRID — cost estimate / record_to_text
# ============================================================================

async def test_hybrid_estimate_api_cost():
    svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
    assert await svc._estimate_api_cost("x", SyncMode.DISCOVERY) == 100
    assert await svc._estimate_api_cost("x", SyncMode.HYBRID) == 30
    assert await svc._estimate_api_cost("x", SyncMode.FULL) == 50
    assert await svc._estimate_api_cost("x", SyncMode.INCREMENTAL) == 10
    assert await svc._estimate_api_cost("x", "bogus") == 10  # invalid str -> INCREMENTAL
    assert await svc._estimate_api_cost("x", "full") == 50


def test_hybrid_record_to_text():
    svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
    out = svc._record_to_text(
        {"type": "contact", "name": "Bob", "email": "b@x.com", "stage": "new",
         "other": "ignored"}, "zoho")
    assert "Contact from zoho" in out and "name: Bob" in out
    assert "email: b@x.com" in out and "other" not in out


# ============================================================================
# HYBRID — _fetch_integration_data dispatch
# ============================================================================

async def test_hybrid_fetch_dispatch(ing, monkeypatch):
    called = []

    async def one(c, role=None):  # direct fetchers take config + role
        return [{"id": "1", "type": "t", "name": "Long enough record name"}]

    async def uni(integration_id, config, discovery_mode=False, role=None):
        called.append(integration_id)
        return [{"id": "1", "type": "t", "name": "Long enough record name"}]

    for name in ("_fetch_salesforce_data", "_fetch_slack_data", "_fetch_gmail_data",
                 "_fetch_zendesk_data", "_fetch_shopify_data", "_fetch_onedrive_data",
                 "_fetch_google_drive_data", "_fetch_telegram_data"):
        monkeypatch.setattr(ing, name, one)
    monkeypatch.setattr(ing, "_fetch_universal_adapter_data", uni)

    c = cfg(max_records=10)
    for iid in ("salesforce", "hubspot", "notion", "airtable", "jira", "zoho",
                "zoho_crm", "slack", "gmail", "zendesk", "shopify", "onedrive",
                "google_drive", "telegram"):
        recs = await ing._fetch_integration_data(iid, c)
        assert recs and recs[0]["id"] == "1"

    # unknown integration
    assert await ing._fetch_integration_data("unknown", c) == []
    # exception swallowed
    ing._fetch_salesforce_data = AsyncMock(side_effect=RuntimeError("x"))
    assert await ing._fetch_integration_data("salesforce", c) == []


# ============================================================================
# HYBRID — universal adapter fetcher
# ============================================================================

def _universal_env(monkeypatch, adapter):
    if hasattr(adapter, "ensure_token") and not isinstance(adapter.ensure_token, AsyncMock):
        adapter.ensure_token = AsyncMock()
    sl = MagicMock()
    monkeypatch.setattr("core.database.SessionLocal", sl)
    monkeypatch.setattr(hybrid_mod, "SessionLocal", sl)
    sf = MagicMock()
    monkeypatch.setattr("core.service_factory.ServiceFactory", sf)
    for m in ("get_hubspot_adapter", "get_notion_adapter", "get_airtable_adapter",
              "get_jira_adapter", "get_zoho_adapter"):
        setattr(sf, m, MagicMock(return_value=adapter))
    return sf


async def test_hybrid_universal_basic_fetch_and_pagination(ing, monkeypatch):
    adapter = MagicMock()
    adapter.fetch_records = AsyncMock(side_effect=[
        {"results": [{"id": str(i)} for i in range(100)]},   # full page
        {"results": [{"id": "last"}]},                        # short page
    ])
    _universal_env(monkeypatch, adapter)
    c = cfg("hubspot", entity_types=["contacts"])
    recs = await ing._fetch_universal_adapter_data("hubspot", c)
    assert len(recs) == 101
    assert recs[0]["type"] == "contacts" and recs[0]["source"] == "hubspot"


async def test_hybrid_universal_max_records_cap(ing, monkeypatch):
    adapter = MagicMock()
    adapter.fetch_records = AsyncMock(side_effect=[
        {"results": [{"id": str(i)} for i in range(100)]},
        {"results": [{"id": "x"} for i in range(100)]},
    ])
    _universal_env(monkeypatch, adapter)
    recs = await ing._fetch_universal_adapter_data("hubspot", cfg("hubspot", max_records=150))
    assert len(recs) == 200  # capped after second page


async def test_hybrid_universal_discovery_branches(ing, monkeypatch):
    schemas = [
        {"name": "hs_contacts"},
        {"id": "nt_page"},
        {"base_id": "b1", "id": "t1"},
        {"project_key": "P", "issue_type": "Bug"},
        {"api_name": "Leads"},
    ]
    adapter = MagicMock()
    adapter.get_available_schemas = AsyncMock(return_value=schemas)

    async def fetch(entity_type, limit, offset):
        return {"results": [{"id": "1", "etype": entity_type}]}

    adapter.fetch_records = AsyncMock(side_effect=fetch)
    _universal_env(monkeypatch, adapter)
    for iid, expect in (("hubspot", "hs_contacts"), ("notion", "nt_page"),
                        ("airtable", "b1:t1"), ("jira", "P:Bug"), ("zoho", "Leads")):
        recs = await ing._fetch_universal_adapter_data(
            iid, cfg(iid, entity_types=["base"]), discovery_mode=True)
        # config entity + discovered entity merged via set() (order-free)
        assert expect in {r["type"] for r in recs}


async def test_hybrid_universal_no_schemas_attr_and_fetch_error(ing, monkeypatch):
    adapter = MagicMock(spec=["ensure_token"])  # no get_available_schemas / fetch_records
    _universal_env(monkeypatch, adapter)
    recs = await ing._fetch_universal_adapter_data("hubspot", cfg("hubspot"), discovery_mode=True)
    assert recs == []
    # fetch_records raising for one entity type tolerated
    adapter2 = MagicMock()
    adapter2.fetch_records = AsyncMock(side_effect=RuntimeError("fetch fail"))
    _universal_env(monkeypatch, adapter2)
    recs2 = await ing._fetch_universal_adapter_data("hubspot", cfg("hubspot", entity_types=["a", "b"]))
    assert recs2 == []


async def test_hybrid_universal_missing_factory_method(ing, monkeypatch):
    class Empty:
        pass
    monkeypatch.setattr("core.database.SessionLocal", MagicMock())
    monkeypatch.setattr(hybrid_mod, "SessionLocal", MagicMock())
    monkeypatch.setattr("core.service_factory.ServiceFactory", Empty())
    assert await ing._fetch_universal_adapter_data("hubspot", cfg("hubspot")) == []


async def test_hybrid_universal_zoho_legacy_fallback(ing, monkeypatch):
    adapter = MagicMock(spec=["ensure_token"])  # no fetch_records
    _universal_env(monkeypatch, adapter)
    ing._fetch_zoho_multi_app_data = AsyncMock(return_value=[{"id": "z1"}])
    recs = await ing._fetch_universal_adapter_data("zoho", cfg("zoho"))
    assert recs == [{"id": "z1"}]
    # non-zoho without fetch_records just warns
    recs2 = await ing._fetch_universal_adapter_data("airtable", cfg("airtable"))
    assert recs2 == []


async def test_hybrid_universal_outer_error(ing, monkeypatch):
    monkeypatch.setattr("core.database.SessionLocal",
                        MagicMock(side_effect=RuntimeError("db")))
    monkeypatch.setattr(hybrid_mod, "SessionLocal", MagicMock(side_effect=RuntimeError("db")))
    assert await ing._fetch_universal_adapter_data("hubspot", cfg("hubspot")) == []


# ============================================================================
# HYBRID — per-integration fetchers
# ============================================================================

async def test_hybrid_fetch_salesforce(ing, monkeypatch):
    client = MagicMock()
    client.query.side_effect = [
        {"records": [{"Id": "c1", "Name": "C", "Email": "c@x", "Title": "T",
                      "Account": {"Name": "Acme"}}]},
        {"records": [{"Id": "o1", "Name": "Opp", "StageName": "Won", "Amount": 5}]},
    ]
    monkeypatch.setattr("integrations.salesforce_service.get_salesforce_client",
                        AsyncMock(return_value=client))
    c = cfg("salesforce", entity_types=["contacts", "opportunities"])
    recs = await ing._fetch_salesforce_data(c)
    assert recs[0]["type"] == "contact" and recs[1]["type"] == "opportunity"
    # no client
    monkeypatch.setattr("integrations.salesforce_service.get_salesforce_client",
                        AsyncMock(return_value=None))
    assert await ing._fetch_salesforce_data(c) == []
    # error
    monkeypatch.setattr("integrations.salesforce_service.get_salesforce_client",
                        AsyncMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_salesforce_data(c) == []


async def test_hybrid_fetch_hubspot_direct(ing, monkeypatch):
    svc = MagicMock()
    svc.get_contacts = AsyncMock(return_value=[
        {"id": "c1", "properties": {"firstname": "A", "lastname": "B",
                                    "email": "a@x", "company": "Co"}}])
    svc.get_deals = AsyncMock(return_value=[
        {"id": "d1", "properties": {"dealname": "D", "dealstage": "s", "amount": 1}}])
    monkeypatch.setattr("integrations.hubspot_service.get_hubspot_service",
                        MagicMock(return_value=svc))
    recs = await ing._fetch_hubspot_data(cfg("hubspot", entity_types=["contacts", "deals"]))
    assert recs[0]["type"] == "contact" and recs[0]["name"] == "A B"
    assert recs[1]["type"] == "deal"
    # service None / error
    monkeypatch.setattr("integrations.hubspot_service.get_hubspot_service",
                        MagicMock(return_value=None))
    assert await ing._fetch_hubspot_data(cfg("hubspot")) == []
    monkeypatch.setattr("integrations.hubspot_service.get_hubspot_service",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_hubspot_data(cfg("hubspot")) == []


async def test_hybrid_fetch_slack(ing, monkeypatch):
    monkeypatch.setattr("core.token_storage.token_storage",
                        MagicMock(get_token=MagicMock(return_value={"access_token": "tok"})))
    unified = MagicMock()
    unified.list_channels = AsyncMock(return_value=[{"id": "c1", "name": "gen"}])
    unified.get_channel_history = AsyncMock(return_value={"messages": [
        {"ts": "1", "type": "message", "text": "hello", "user": "u"},
        {"ts": "2", "type": "other", "text": "skip"},
    ]})
    monkeypatch.setattr("integrations.slack_service_unified.slack_unified_service", unified)
    recs = await ing._fetch_slack_data(cfg("slack"))
    assert len(recs) == 1 and recs[0]["text"] == "hello"
    # no token
    monkeypatch.setattr("core.token_storage.token_storage",
                        MagicMock(get_token=MagicMock(return_value=None)))
    assert await ing._fetch_slack_data(cfg("slack")) == []
    # error
    monkeypatch.setattr("core.token_storage.token_storage",
                        MagicMock(get_token=MagicMock(side_effect=RuntimeError("x"))))
    assert await ing._fetch_slack_data(cfg("slack")) == []


async def test_hybrid_fetch_gmail(ing, monkeypatch):
    gmail = MagicMock()
    gmail.get_messages = MagicMock(return_value=[
        {"id": "m1", "threadId": "t1", "subject": "S", "from": "a@x",
         "to": "b@x", "date": "d", "snippet": "sn", "body": "b", "labels": ["L"]}])
    monkeypatch.setattr("integrations.gmail_service.get_gmail_service",
                        MagicMock(return_value=gmail))
    recs = await ing._fetch_gmail_data(cfg("gmail"))
    assert recs[0]["type"] == "email" and recs[0]["thread_id"] == "t1"
    # ImportError branch
    monkeypatch.setattr("integrations.gmail_service.get_gmail_service",
                        MagicMock(side_effect=ImportError("no lib")))
    assert await ing._fetch_gmail_data(cfg("gmail")) == []
    # generic error
    monkeypatch.setattr("integrations.gmail_service.get_gmail_service",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_gmail_data(cfg("gmail")) == []


async def test_hybrid_fetch_notion_direct(ing, monkeypatch):
    notion = MagicMock()
    notion.search_pages_in_workspace = MagicMock(return_value=[
        {"id": "p1", "title": "P", "url": "u", "created_time": "c",
         "last_edited_time": "e", "archived": False}])
    notion.get_block_children = MagicMock(return_value={"results": [{}]})
    notion.search_databases_in_workspace = MagicMock(return_value=[{"id": "db1"}])
    notion.get_database = MagicMock(return_value={
        "title": [{"plain_text": "DB"}], "created_time": "c",
        "last_edited_time": "e", "properties": {"a": 1}})
    monkeypatch.setattr("integrations.notion_service.NotionService",
                        MagicMock(return_value=notion))
    c = cfg("notion", entity_types=["pages", "databases"])
    recs = await ing._fetch_notion_data(c)
    assert recs[0]["type"] == "page" and recs[1]["type"] == "database"
    # ImportError + generic error
    monkeypatch.setattr("integrations.notion_service.NotionService",
                        MagicMock(side_effect=ImportError()))
    assert await ing._fetch_notion_data(c) == []
    monkeypatch.setattr("integrations.notion_service.NotionService",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_notion_data(c) == []


async def test_hybrid_fetch_jira_direct(ing, monkeypatch):
    jira = MagicMock()
    jira.search_issues = MagicMock(return_value={"issues": [
        {"key": "J-1", "fields": {"summary": "s", "status": {"name": "Open"},
                                  "assignee": {"displayName": "A"},
                                  "priority": {"name": "P"}}}]})
    monkeypatch.setattr("integrations.jira_service.get_jira_service",
                        MagicMock(return_value=jira))
    recs = await ing._fetch_jira_data(cfg("jira"))
    assert recs[0]["type"] == "issue" and recs[0]["assignee"] == "A"
    # not configured
    monkeypatch.setattr("integrations.jira_service.get_jira_service",
                        MagicMock(return_value=None))
    assert await ing._fetch_jira_data(cfg("jira")) == []
    # error
    monkeypatch.setattr("integrations.jira_service.get_jira_service",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_jira_data(cfg("jira")) == []


async def test_hybrid_fetch_zendesk(ing, monkeypatch):
    zd = MagicMock()
    zd.get_tickets = AsyncMock(return_value=[
        {"id": "t1", "subject": "s", "status": "open", "priority": "high",
         "created_at": "c", "updated_at": "u", "requester_id": 1, "assignee_id": 2,
         "type": "bug", "description": "d"}])
    zd.get_users = AsyncMock(return_value=[
        {"id": "u1", "name": "N", "email": "e@x", "role": "agent",
         "created_at": "c", "last_login_at": "l", "verified": True}])
    monkeypatch.setattr("integrations.zendesk_service.ZendeskService",
                        MagicMock(return_value=zd))
    c = cfg("zendesk", entity_types=["tickets", "users"])
    recs = await ing._fetch_zendesk_data(c)
    assert recs[0]["type"] == "ticket" and recs[1]["type"] == "user"
    # tickets implied when entity_types empty
    recs2 = await ing._fetch_zendesk_data(cfg("zendesk", entity_types=[]))
    assert recs2[0]["type"] == "ticket"
    monkeypatch.setattr("integrations.zendesk_service.ZendeskService",
                        MagicMock(side_effect=ImportError()))
    assert await ing._fetch_zendesk_data(c) == []
    monkeypatch.setattr("integrations.zendesk_service.ZendeskService",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_zendesk_data(c) == []


# ============================================================================
# HYBRID — zoho multi-app fetcher
# ============================================================================

def _zoho_env(monkeypatch, token, adapter):
    sl = MagicMock()
    db = sl.return_value
    db.query.return_value.filter.return_value.first.return_value = token
    monkeypatch.setattr("core.database.SessionLocal", sl)
    monkeypatch.setattr(hybrid_mod, "SessionLocal", sl)
    monkeypatch.setattr("core.integrations.adapters.zoho.ZohoAdapter",
                        MagicMock(return_value=adapter))
    return sl


async def test_hybrid_zoho_multi_app_all_entities(ing, monkeypatch):
    token = SimpleNamespace(
        instance_url="https://zoho", credential_metadata={"organization_id": "org",
                                                          "portal_id": "pt",
                                                          "active_projects": ["pj"]})
    adapter = MagicMock()
    adapter.get_leads = AsyncMock(return_value=[{"id": "l"}])
    adapter.get_deals = AsyncMock(return_value=[{"id": "d"}])
    adapter.get_invoices = AsyncMock(return_value=[{"id": "i"}])
    adapter.get_items = AsyncMock(return_value=[{"id": "it"}])
    adapter.get_sales_orders = AsyncMock(return_value=[{"id": "so"}])
    adapter.get_tasks = AsyncMock(return_value=[{"id": "tk"}])
    adapter.ensure_token = AsyncMock()
    _zoho_env(monkeypatch, token, adapter)
    c = cfg("zoho", entity_types=["crm_leads", "crm_deals", "books_invoices",
                                  "inventory_items", "inventory_sales_orders",
                                  "projects_tasks"])
    recs = await ing._fetch_zoho_multi_app_data(c)
    assert len(recs) == 6


async def test_hybrid_zoho_no_token_no_org_discovery(ing, monkeypatch):
    adapter = MagicMock()
    adapter.get_portals = AsyncMock(return_value=[{"id": "found_pt"}])
    adapter.get_projects = AsyncMock(return_value=[{"id": "p1"}, {"id": "p2"},
                                                    {"id": "p3"}, {"id": "p4"}])
    adapter.get_tasks = AsyncMock(return_value=[{"id": "tk"}])
    adapter.ensure_token = AsyncMock()
    _zoho_env(monkeypatch, None, adapter)  # no token at all
    c = cfg("zoho", entity_types=["projects_tasks"])
    recs = await ing._fetch_zoho_multi_app_data(c, discovery_mode=True)
    assert len(recs) == 3  # top 3 projects
    adapter.get_portals.assert_called_once()
    adapter.get_projects.assert_called_once_with("found_pt")


async def test_hybrid_zoho_error(ing, monkeypatch):
    monkeypatch.setattr("core.database.SessionLocal", MagicMock(side_effect=RuntimeError("db")))
    monkeypatch.setattr(hybrid_mod, "SessionLocal", MagicMock(side_effect=RuntimeError("db")))
    assert await ing._fetch_zoho_multi_app_data(cfg("zoho")) == []


# ============================================================================
# HYBRID — shopify / onedrive / google_drive / telegram
# ============================================================================

async def test_hybrid_fetch_shopify(ing, monkeypatch):
    svc = SimpleNamespace(
        config={"access_token": "tok"}, shop_name="shop",
        get_products=AsyncMock(return_value=[{"id": "p", "title": "P"}]),
        get_orders=AsyncMock(return_value=[{"id": "o", "n": 1}]),
        get_customers=AsyncMock(return_value=[{"id": "c", "n": "C"}]))
    monkeypatch.setattr("integrations.shopify_service.ShopifyService",
                        MagicMock(return_value=svc))
    c = cfg("shopify", entity_types=["products", "orders", "customers"])
    recs = await ing._fetch_shopify_data(c)
    assert len(recs) == 3 and recs[0]["source"] == "shopify"
    # per-entity error tolerated
    svc2 = SimpleNamespace(config={}, shop_name=None,
                           get_products=AsyncMock(side_effect=RuntimeError("x")))
    monkeypatch.setattr("integrations.shopify_service.ShopifyService",
                        MagicMock(return_value=svc2))
    assert await ing._fetch_shopify_data(cfg("shopify", entity_types=["products"])) == []
    # missing token/shop
    monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
    svc3 = SimpleNamespace(config={}, shop_name=None)
    monkeypatch.setattr("integrations.shopify_service.ShopifyService",
                        MagicMock(return_value=svc3))
    monkeypatch.setattr(hybrid_mod.os, "getenv", lambda k, d=None: None)
    assert await ing._fetch_shopify_data(c) == []


async def test_hybrid_fetch_onedrive(ing, monkeypatch):
    doc_ing = MagicMock()
    doc_ing.process_file_bytes = AsyncMock(return_value=True)
    svc = MagicMock()
    svc.get_access_token = AsyncMock(return_value="tok")
    svc.list_files = AsyncMock(return_value={"status": "success",
                                             "data": {"value": [
        {"id": "f1", "folder": {}, "name": "dir"},
        {"id": "f2", "name": "notes.txt", "webUrl": "u", "size": 5,
         "lastModifiedDateTime": "l", "createdDateTime": "c", "createdBy": "x"},
    ]}})
    svc.download_file_bytes = AsyncMock(return_value=b"content")
    monkeypatch.setattr("integrations.onedrive_service.OneDriveService",
                        MagicMock(return_value=svc))
    monkeypatch.setattr("core.auto_document_ingestion.AutoDocumentIngestionService",
                        MagicMock(return_value=doc_ing))
    recs = await ing._fetch_onedrive_data(cfg("onedrive"))
    assert len(recs) == 1 and recs[0]["type"] == "onedrive_file"
    assert doc_ing.process_file_bytes.called
    # no token
    svc.get_access_token = AsyncMock(return_value=None)
    assert await ing._fetch_onedrive_data(cfg("onedrive")) == []
    # list failure
    svc.get_access_token = AsyncMock(return_value="tok")
    svc.list_files = AsyncMock(return_value={"status": "error", "message": "m"})
    assert await ing._fetch_onedrive_data(cfg("onedrive")) == []
    # doc ingestor unavailable + download error tolerated
    svc.list_files = AsyncMock(return_value={"status": "success",
                                             "data": {"value": [{"id": "f3", "name": "a.pdf"}]}})
    monkeypatch.setattr("core.auto_document_ingestion.AutoDocumentIngestionService",
                        MagicMock(side_effect=ImportError()))
    recs2 = await ing._fetch_onedrive_data(cfg("onedrive"))
    assert len(recs2) == 1
    # outer exception
    monkeypatch.setattr("integrations.onedrive_service.OneDriveService",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_onedrive_data(cfg("onedrive")) == []


async def test_hybrid_fetch_google_drive(ing, monkeypatch):
    doc_ing = MagicMock()
    doc_ing.process_file_bytes = AsyncMock(return_value=True)
    svc = MagicMock()
    svc.get_access_token = AsyncMock(return_value="tok")
    svc.list_files = AsyncMock(return_value={"status": "success", "data": {
        "value": [
            {"id": "g1", "name": "folder", "mimeType": "application/vnd.google-apps.folder"},
            {"id": "g2", "name": "doc.docx", "mimeType": "application/vnd.google-apps.document",
             "webViewLink": "w", "size": 1, "modifiedTime": "m", "createdTime": "c"},
        ]}})
    svc.download_file_bytes = AsyncMock(return_value=b"bytes")
    monkeypatch.setattr("integrations.google_drive_service.GoogleDriveService",
                        MagicMock(return_value=svc))
    monkeypatch.setattr("core.auto_document_ingestion.AutoDocumentIngestionService",
                        MagicMock(return_value=doc_ing))
    recs = await ing._fetch_google_drive_data(cfg("google_drive"))
    assert len(recs) == 2
    assert recs[0]["object_type"] == "folder" and recs[1]["object_type"] == "file"
    # no token / list failure / files-key fallback / outer error
    svc.get_access_token = AsyncMock(return_value=None)
    assert await ing._fetch_google_drive_data(cfg("google_drive")) == []
    svc.get_access_token = AsyncMock(return_value="tok")
    svc.list_files = AsyncMock(return_value={"status": "err", "message": "m"})
    assert await ing._fetch_google_drive_data(cfg("google_drive")) == []
    svc.list_files = AsyncMock(return_value={"status": "success", "data": {"files": [
        {"id": "g3", "name": "f.txt", "mimeType": "text/plain"}]}})
    assert len(await ing._fetch_google_drive_data(cfg("google_drive"))) == 1
    monkeypatch.setattr("integrations.google_drive_service.GoogleDriveService",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_google_drive_data(cfg("google_drive")) == []


async def test_hybrid_fetch_telegram(ing, monkeypatch):
    adapter = MagicMock()
    adapter.get_updates = AsyncMock(return_value=[
        {"message": {"message_id": 1, "text": "hi",
                     "chat": {"id": 1, "title": "c", "username": "u"},
                     "from": {"id": 9, "username": "sender", "first_name": "S"},
                     "date": 123}},
        {"channel_post": {"message_id": 2, "text": "post", "chat": {}, "from": {}}},
        {"other": {}},
    ])
    monkeypatch.setattr("core.communication.adapters.telegram.TelegramAdapter",
                        MagicMock(return_value=adapter))
    recs = await ing._fetch_telegram_data(cfg("telegram"))
    assert len(recs) == 2 and recs[0]["type"] == "telegram_message"
    # empty
    adapter.get_updates = AsyncMock(return_value=[])
    assert await ing._fetch_telegram_data(cfg("telegram")) == []
    # error
    monkeypatch.setattr("core.communication.adapters.telegram.TelegramAdapter",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await ing._fetch_telegram_data(cfg("telegram")) == []


# ============================================================================
# HYBRID — schema discovery
# ============================================================================

async def test_hybrid_discover_schema_types_no_llm(ing):
    ing.llm = None
    schema = await ing._discover_schema({
        "b": True, "i": 1, "f": 1.5, "d": {"x": 1}, "l": [1], "s": "str",
        "raw_metadata": "skip"})
    props = schema["properties"]
    assert props["b"]["type"] == "boolean"
    assert props["i"]["type"] == "integer"
    assert props["f"]["type"] == "number"
    assert props["d"]["type"] == "object"
    assert props["l"]["type"] == "array"
    assert props["s"]["type"] == "string"
    assert "raw_metadata" not in props


async def test_hybrid_discover_schema_llm_refine_and_failure(ing):
    ing.llm = MagicMock()
    ing.llm.generate_structured_response = AsyncMock(return_value=SimpleNamespace(
        display_names={"name": "Name"}, descriptions={"name": "The name"}))
    schema = await ing._discover_schema({"name": "x"})
    assert schema["properties"]["name"]["title"] == "Name"
    assert schema["properties"]["name"]["description"] == "The name"
    ing.llm.generate_structured_response = AsyncMock(side_effect=RuntimeError("llm"))
    schema2 = await ing._discover_schema({"name": "x"})
    assert "title" not in schema2["properties"]["name"]


# ============================================================================
# HYBRID — scheduled syncs / stop
# ============================================================================

async def test_hybrid_run_scheduled_syncs_and_stop(ing, monkeypatch):
    _syncable(ing, "zoho")

    async def fake_sync(iid):
        ing._running = False

    ing.sync_integration_data = AsyncMock(side_effect=fake_sync)
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(hybrid_mod, "asyncio", SimpleNamespace(sleep=fake_sleep))
    await ing.run_scheduled_syncs()
    assert sleeps  # exited loop via sleep patch
    # error branch inside loop
    ing._running = True
    ing.sync_integration_data = AsyncMock(side_effect=RuntimeError("x"))

    async def stop_sleep(s):
        ing._running = False

    monkeypatch.setattr(hybrid_mod, "asyncio", SimpleNamespace(sleep=stop_sleep))
    await ing.run_scheduled_syncs()
    ing.stop()
    assert ing._running is False


async def test_hybrid_run_scheduled_not_due(ing, monkeypatch):
    ing.record_integration_usage("zoho", "Z")
    ing.enable_auto_sync("zoho")
    ing.usage_stats["zoho"].last_synced = datetime.now(timezone.utc)

    async def fake_sleep(s):
        ing._running = False

    monkeypatch.setattr(hybrid_mod, "asyncio", SimpleNamespace(sleep=fake_sleep))
    ing.sync_integration_data = AsyncMock()
    await ing.run_scheduled_syncs()
    ing.sync_integration_data.assert_not_called()


# ============================================================================
# WORLD MODEL — fixtures
# ============================================================================

@pytest.fixture()
def mock_handler():
    handler = Mock()
    handler.db = Mock()
    handler.db.table_names = Mock(return_value=["agent_experience", "business_facts"])
    handler.workspace_id = "ws1"
    handler.add_document = Mock(return_value=True)
    handler.search = Mock(return_value=[])
    handler.create_table = Mock()
    handler.get_table = Mock(return_value=None)
    return handler


@pytest.fixture()
def wsvc(mock_handler):
    with patch("core.agent_world_model.get_lancedb_handler", return_value=mock_handler):
        return WorldModelService(workspace_id="ws1")


@pytest.fixture()
def experience():
    return AgentExperience(
        id=str(uuid.uuid4()), agent_id="a1", task_type="recon",
        input_summary="Reconcile SKU", outcome="Success", learnings="learned",
        confidence_score=0.8, feedback_score=0.5, artifacts=["r.pdf"],
        step_efficiency=1.0, metadata_trace={"steps": 2}, agent_role="Finance",
        specialty="acct", timestamp=DT)


def _fact(fid="f1", status="unverified"):
    return BusinessFact(
        id=fid, fact="Invoices > $500 need VP approval",
        citations=["policy.pdf:p4"], reason="compliance",
        source_agent_id="a1", created_at=DT, last_verified=DT,
        verification_status=status, metadata={"domain": "finance"})


def _meta_fact(fid="f1", status="unverified"):
    return {
        "id": fid, "fact": "Facts are facts", "citations": ["c1"],
        "reason": "why", "source_agent_id": "a1",
        "created_at": DT.isoformat(), "last_verified": DT.isoformat(),
        "verification_status": status, "domain": "finance"}


# ============================================================================
# WORLD MODEL — ensure tables / record / formula
# ============================================================================

def test_wm_ensure_tables_creates(wsvc, mock_handler):
    mock_handler.db.table_names = Mock(return_value=[])
    wsvc._ensure_tables()
    assert mock_handler.create_table.call_count == 2
    # db None early return
    mock_handler.db = None
    assert wsvc._ensure_tables() is None


async def test_wm_record_experience(wsvc, mock_handler, experience):
    assert await wsvc.record_experience(experience) is True
    args = mock_handler.add_document.call_args
    assert args.kwargs["metadata"]["agent_id"] == "a1"


async def test_wm_record_formula_usage(wsvc, mock_handler):
    assert await wsvc.record_formula_usage(
        agent_id="a1", agent_role="Finance", formula_id="f1",
        formula_name="Gross Margin", task_description="margin calc",
        inputs={"rev": 10}, result=4.0, success=True, learnings="") is True
    kwargs = mock_handler.add_document.call_args.kwargs
    assert kwargs["metadata"]["formula_id"] == "f1"
    assert kwargs["metadata"]["formula_inputs"] == '{"rev": 10}'
    # failure + no learnings branch
    assert await wsvc.record_formula_usage(
        "a1", "Finance", "f1", "GM", "calc", {}, None, False) is True


# ============================================================================
# WORLD MODEL — feedback / boost / statistics
# ============================================================================

async def test_wm_update_experience_feedback(wsvc, mock_handler):
    mock_handler.search = Mock(return_value=[
        {"id": "e1", "text": "T", "source": "s", "metadata": {"confidence_score": 0.5}}])
    assert await wsvc.update_experience_feedback("e1", 0.8, "good") is True
    kwargs = mock_handler.add_document.call_args.kwargs
    assert kwargs["text"].endswith("Feedback: good")
    assert kwargs["metadata"]["feedback_score"] == 0.8
    # not found
    mock_handler.search = Mock(return_value=[])
    assert await wsvc.update_experience_feedback("nope", 1.0) is False
    # error
    mock_handler.search = Mock(side_effect=RuntimeError("db"))
    assert await wsvc.update_experience_feedback("e1", 1.0) is False


async def test_wm_boost_experience_confidence(wsvc, mock_handler):
    mock_handler.search = Mock(return_value=[
        {"id": "e1", "text": "T", "source": "s", "metadata": {"confidence_score": 0.95}}])
    assert await wsvc.boost_experience_confidence("e1", 0.5) is True
    meta = mock_handler.add_document.call_args.kwargs["metadata"]
    assert meta["confidence_score"] == 1.0  # clamped high
    assert meta["boost_count"] == 1
    mock_handler.search = Mock(return_value=[
        {"id": "e1", "text": "T", "source": "s", "metadata": {"confidence_score": 0.1}}])
    await wsvc.boost_experience_confidence("e1", -0.5)
    assert mock_handler.add_document.call_args.kwargs["metadata"]["confidence_score"] == 0.0
    mock_handler.search = Mock(return_value=[])
    assert await wsvc.boost_experience_confidence("nope", 0.1) is False
    mock_handler.search = Mock(side_effect=RuntimeError("x"))
    assert await wsvc.boost_experience_confidence("e1", 0.1) is False


async def test_wm_experience_statistics(wsvc, mock_handler):
    mock_handler.search = Mock(return_value=[
        {"metadata": {"agent_id": "a1", "agent_role": "finance", "outcome": "success",
                      "confidence_score": 0.8, "feedback_score": 0.5}},
        {"metadata": {"agent_id": "a1", "agent_role": "finance", "outcome": "failed",
                      "confidence_score": 0.2}},
        {"metadata": {"agent_id": "other", "outcome": "success"}},
    ])
    stats = await wsvc.get_experience_statistics(agent_id="a1", agent_role="Finance")
    assert stats["total_experiences"] == 2
    assert stats["successes"] == 1 and stats["failures"] == 1
    assert stats["feedback_coverage"] == 0.5
    # empty
    mock_handler.search = Mock(return_value=[])
    empty = await wsvc.get_experience_statistics()
    assert empty["total_experiences"] == 0 and empty["avg_confidence"] == 0.5
    # error
    mock_handler.search = Mock(side_effect=RuntimeError("x"))
    assert "error" in await wsvc.get_experience_statistics()


# ============================================================================
# WORLD MODEL — facts CRUD / verification / listing
# ============================================================================

async def test_wm_record_business_fact_and_bulk(wsvc, mock_handler):
    assert await wsvc.record_business_fact(_fact()) is True
    assert mock_handler.add_document.called
    mock_handler.add_document = Mock(side_effect=[True, RuntimeError("x"), True])
    n = await wsvc.bulk_record_facts([_fact("1"), _fact("2"), _fact("3")])
    assert n == 2


async def test_wm_update_fact_verification(wsvc, mock_handler):
    mock_handler.search = Mock(return_value=[
        {"metadata": _meta_fact("f1", "unverified"), "text": "Fact: X\nStatus: unverified",
         "source": "s"}])
    assert await wsvc.update_fact_verification("f1", "verified") is True
    kwargs = mock_handler.add_document.call_args.kwargs
    assert kwargs["text"].endswith("Status: verified")
    assert kwargs["metadata"]["verification_status"] == "verified"
    # not found / error / delete_fact delegates
    mock_handler.search = Mock(return_value=[])
    assert await wsvc.update_fact_verification("nope", "verified") is False
    assert await wsvc.delete_fact("nope") is False
    mock_handler.search = Mock(side_effect=RuntimeError("x"))
    assert await wsvc.update_fact_verification("f1", "verified") is False


async def test_wm_get_relevant_business_facts(wsvc, mock_handler):
    mock_handler.search = Mock(return_value=[{"metadata": _meta_fact("f1", "verified")}])
    facts = await wsvc.get_relevant_business_facts("invoices", limit=3)
    assert facts[0].verification_status == "verified"
    assert facts[0].citations == ["c1"]
    mock_handler.search = Mock(side_effect=RuntimeError("x"))
    assert await wsvc.get_relevant_business_facts("q") == []


async def test_wm_get_business_fact_table_paths(wsvc, mock_handler):
    df = MagicMock()
    df.empty = False
    row = {"id": "f1", "text": "Fact: X\nStatus: ok",
           "metadata": {"id": "f1", "reason": "r", "source_agent_id": "a1",
                        "created_at": DT.isoformat(),
                        "last_verified": DT.isoformat()}}
    df.iloc.__getitem__.return_value = row
    table = MagicMock()
    table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = df
    mock_handler.get_table = Mock(return_value=table)
    fact = await wsvc.get_business_fact("f1")
    assert fact.id == "f1"
    # string metadata branch
    row2 = {"id": "f1", "text": "Fact: X", "metadata": json.dumps(
        {"id": "f1", "reason": "r", "source_agent_id": "a1",
         "created_at": DT.isoformat(),
         "last_verified": DT.isoformat()})}
    df.iloc.__getitem__.return_value = row2
    fact2 = await wsvc.get_business_fact("f1")
    assert fact2.id == "f1"
    # empty metadata branch -> created_at falls back to now(), fact still returned
    row3 = {"id": "f1", "text": "Fact: Y", "metadata": None}
    df.iloc.__getitem__.return_value = row3
    fact3 = await wsvc.get_business_fact("f1")
    assert fact3 is not None and fact3.id == "f1"
    assert fact3.created_at is not None  # guarded fallback, not a TypeError -> None
    mock_handler.get_table = Mock(return_value=None)
    assert await wsvc.get_business_fact("f1") is None
    mock_handler.get_table = Mock(side_effect=RuntimeError("x"))
    assert await wsvc.get_business_fact("f1") is None


async def test_wm_relevant_facts_survive_bad_rows(wsvc, mock_handler):
    # A row without metadata (or with an unparseable timestamp) must not nuke
    # the whole result set — good rows still come back.
    good = {"metadata": _meta_fact("f1", "verified")}
    no_meta = {"metadata": None}
    bad_ts = {"metadata": {**_meta_fact("f2"), "created_at": "not-a-date"}}
    mock_handler.search = Mock(return_value=[good, no_meta, bad_ts])
    facts = await wsvc.get_relevant_business_facts("invoices", limit=5)
    ids = [f.id for f in facts]
    assert "f1" in ids          # good row survives
    assert "f2" not in ids      # unparseable-timestamp row is skipped, not fatal


async def test_wm_list_all_facts_and_get_by_id(wsvc, mock_handler):
    mock_handler.search = Mock(return_value=[
        {"metadata": _meta_fact("f1", "verified")},
        {"metadata": _meta_fact("f2", "unverified")},
        {"metadata": {"id": None}},  # parse failure tolerated
    ])
    facts = await wsvc.list_all_facts(status="verified", limit=10)
    assert len(facts) == 1 and facts[0].id == "f1"
    dom = await wsvc.list_all_facts(domain="finance", limit=10)
    assert len(dom) == 2
    # limit truncation
    lim = await wsvc.list_all_facts(limit=1)
    assert len(lim) == 1
    got = await wsvc.get_fact_by_id("f2")
    assert got is not None and got.id == "f2"
    assert await wsvc.get_fact_by_id("nope") is None
    mock_handler.search = Mock(side_effect=RuntimeError("x"))
    assert await wsvc.list_all_facts() == []
    assert await wsvc.get_fact_by_id("f1") is None


# ============================================================================
# WORLD MODEL — recall_integration_experiences
# ============================================================================

async def test_wm_recall_integration_experiences(wsvc, mock_handler):
    assert await wsvc.recall_integration_experiences("Finance", "x", "y") == []
    mock_handler.db = object()
    mock_handler.search = Mock(return_value=[
        {"id": "e1", "text": "Task: t\nInput: Reconcile X\nOutcome: ok\nLearnings: L",
         "created_at": DT.isoformat(),
         "metadata": {"agent_id": "a1", "task_type": "integration_x_y",
                      "outcome": "Success", "confidence_score": 0.7,
                      "specialty": "s"}},
        {"id": "e2", "text": "garbage", "created_at": "not-a-date",
         "metadata": {}},  # parse failure tolerated
    ])
    exps = await wsvc.recall_integration_experiences("Finance", "zoho", "get_leads")
    assert len(exps) == 1
    assert exps[0].input_summary == "Reconcile X"
    assert mock_handler.search.call_args.kwargs["filter_str"] == (
        "task_type = 'integration_zoho_get_leads' AND agent_role = 'Finance'")


# ============================================================================
# WORLD MODEL — archive / recover / hard delete (ChatMessage paths)
# ============================================================================

def _msg(cid="c1", role="user", content="hi", metadata_json=None, created_at=None):
    m = Mock(spec=["conversation_id", "role", "content", "metadata_json", "created_at"])
    m.conversation_id = cid
    m.role = role
    m.content = content
    m.metadata_json = metadata_json if metadata_json is not None else {}
    m.created_at = created_at or DT
    return m


async def test_wm_archive_session_to_cold_storage(wsvc, mock_handler):
    msgs = [_msg(), _msg(role="assistant", content="yo")]
    with patch("core.agent_world_model.SessionLocal") as sl, \
         patch("core.usage_tracking_service.UsageTrackingService") as uts:
        uts.return_value.track_acu_usage = AsyncMock(return_value=None)
        db = sl.return_value
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = msgs
        assert await wsvc.archive_session_to_cold_storage("c1") is True
        assert db.commit.called
        # billing failure tolerated (track_acu_usage raises)
        uts.return_value.track_acu_usage = AsyncMock(side_effect=RuntimeError("bill"))
        assert await wsvc.archive_session_to_cold_storage("c1") is True
        # commit failure tolerated
        db.commit = Mock(side_effect=RuntimeError("c"))
        assert await wsvc.archive_session_to_cold_storage("c1") is True
        # no messages
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        assert await wsvc.archive_session_to_cold_storage("c1") is False
        # outer error
        db.query = Mock(side_effect=RuntimeError("x"))
        assert await wsvc.archive_session_to_cold_storage("c1") is False
    # add_document failing -> success False, no commit path
    mock_handler.add_document = Mock(return_value=False)
    with patch("core.agent_world_model.SessionLocal") as sl:
        db = sl.return_value
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = msgs
        assert await wsvc.archive_session_to_cold_storage("c1") is False


async def test_wm_recover_archived_session(wsvc):
    msgs = [_msg(metadata_json={"_archived": True})]
    with patch("core.agent_world_model.SessionLocal") as sl:
        db = sl.return_value
        db.query.return_value.filter.return_value.all.return_value = msgs
        res = await wsvc.recover_archived_session("c1")
        assert res["status"] == "success" and res["recovered_count"] == 1
        assert "_archived" not in msgs[0].metadata_json
        # none found
        db.query.return_value.filter.return_value.all.return_value = []
        res2 = await wsvc.recover_archived_session("c1")
        assert res2["status"] == "failed"
        # error
        db.query = Mock(side_effect=RuntimeError("x"))
        res3 = await wsvc.recover_archived_session("c1")
        assert res3["status"] == "failed"


async def test_wm_hard_delete_archived_sessions(wsvc):
    now = datetime.now(timezone.utc)
    past_retention = _msg(metadata_json={
        "_archived": True, "_retention_until": (now - timedelta(days=1)).isoformat()})
    by_created = _msg(metadata_json={"_archived": True}, created_at=now - timedelta(days=60))
    future = _msg(metadata_json={
        "_archived": True, "_retention_until": (now + timedelta(days=5)).isoformat()})
    with patch("core.agent_world_model.SessionLocal") as sl:
        db = sl.return_value
        db.query.return_value.filter.return_value.all.return_value = [past_retention, by_created, future]
        res = await wsvc.hard_delete_archived_sessions(30)
        assert res["status"] == "success" and res["deleted_count"] == 2
        # nothing to delete
        db.query.return_value.filter.return_value.all.return_value = []
        res2 = await wsvc.hard_delete_archived_sessions(30)
        assert res2["deleted_count"] == 0
        # error
        db.query = Mock(side_effect=RuntimeError("x"))
        res3 = await wsvc.hard_delete_archived_sessions(30)
        assert res3["status"] == "failed"


# ============================================================================
# WORLD MODEL — recall_experiences (full composite)
# ============================================================================

def _agent():
    a = MagicMock()
    a.id = "atom_main"
    a.category = "Finance"
    return a


async def test_wm_recall_experiences_composite(wsvc, mock_handler, monkeypatch):
    def search(table_name=None, query=None, limit=None, **kw):
        if table_name == "agent_experience":
            return [{
                "id": "e1", "score": 0.9, "created_at": DT.isoformat(),
                "text": "Task: t\nInput: Do X\nLearnings: L",
                "metadata": {"agent_id": "atom_main", "agent_role": "finance",
                             "task_type": "recon", "outcome": "success",
                             "confidence_score": 0.8, "artifacts": ["a"]}}]
        if table_name == "documents":
            return [{"text": "doc text"}]
        return []

    mock_handler.search = Mock(side_effect=search)

    # graphrag context
    gre = MagicMock()
    gre.get_context_for_ai = AsyncMock(return_value="graph ctx")
    monkeypatch.setattr("core.graphrag_engine.graphrag_engine", gre)

    # formula manager
    fm = MagicMock()
    fm.search_formulas = MagicMock(return_value=[
        {"id": "f1", "name": "GM", "expression": "a-b", "domain": "Finance",
         "use_case": "u", "parameters": []}])
    monkeypatch.setattr("core.formula_memory.get_formula_manager",
                        MagicMock(return_value=fm))

    # conversations via SessionLocal
    msgs = [_msg(role="user", content="q")]
    sl = MagicMock()
    sl.return_value.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = msgs
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)

    # facts
    wsvc.get_relevant_business_facts = AsyncMock(return_value=[_fact()])

    # episodes
    ers = MagicMock()
    ers.retrieve_contextual = AsyncMock(return_value={"episodes": [
        {"id": "ep1", "canvas_ids": ["c1"], "feedback_ids": ["fb1"]}]})
    ers._fetch_canvas_context = AsyncMock(return_value=[{"canvas_type": "sheets", "action": "close", "id": "cv"}])
    ers._fetch_feedback_context = AsyncMock(return_value=[{"rating": 5}])
    monkeypatch.setattr("core.episode_retrieval_service.EpisodeRetrievalService",
                        MagicMock(return_value=ers))

    result = await wsvc.recall_experiences(_agent(), "reconcile invoices")
    assert result["experiences"][0].input_summary == "Do X"
    assert result["knowledge"] == [{"text": "doc text"}]
    assert result["knowledge_graph"] == "graph ctx"
    assert result["formulas"][0]["id"] == "f1"
    assert result["conversations"][0]["content"] == "q"
    assert result["business_facts"][0].id == "f1"
    assert result["episodes"][0]["canvas_context"][0]["canvas_type"] == "sheets"
    assert result["episodes"][0]["feedback_context"] == [{"rating": 5}]


async def test_wm_recall_experiences_failure_paths(wsvc, mock_handler, monkeypatch):
    # top-level search works but returns nothing; every sub-source fails
    # (each is individually caught and tolerated)
    def search(table_name=None, query=None, limit=None, **kw):
        return []
    mock_handler.search = Mock(side_effect=search)
    monkeypatch.setattr("core.graphrag_engine.graphrag_engine",
                        MagicMock(get_context_for_ai=AsyncMock(side_effect=RuntimeError("g"))))
    monkeypatch.setattr("core.formula_memory.get_formula_manager",
                        MagicMock(side_effect=ImportError()))
    sl = MagicMock(side_effect=RuntimeError("db"))
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    monkeypatch.setattr("core.episode_retrieval_service.EpisodeRetrievalService",
                        MagicMock(side_effect=ImportError()))
    result = await wsvc.recall_experiences(_agent(), "task")
    assert result["experiences"] == [] and result["episodes"] == []


# ============================================================================
# WORLD MODEL — recall_experiences_with_detail / formatting
# ============================================================================

async def test_wm_recall_with_detail(wsvc, monkeypatch):
    es = MagicMock()
    es.recall_episodes_with_detail = AsyncMock(return_value=[
        {"id": "ep1", "task_description": "t", "presentation_summary": "s",
         "outcome": "success", "visual_elements": "v", "critical_data_points": "d",
         "audit_trail": "a"}])
    monkeypatch.setattr("core.episode_service.EpisodeService", MagicMock(return_value=es))
    for level in (DetailLevel.SUMMARY, DetailLevel.STANDARD, DetailLevel.FULL):
        out = await wsvc.recall_experiences_with_detail("t1", "Finance", "task",
                                                        detail_level=level, agent_id="a1")
        assert out[0]["episode_id"] == "ep1"
    # FULL without agent_id -> recall_episodes path
    wsvc.recall_episodes = AsyncMock(return_value=[{"episode_id": "ep2"}])
    out2 = await wsvc.recall_experiences_with_detail("t1", "Finance", "task",
                                                     detail_level=DetailLevel.FULL)
    assert out2 == [{"episode_id": "ep2"}]
    # SUMMARY without agent_id -> PG query path
    cursor = MagicMock()
    cursor.fetchall.return_value = [SimpleNamespace(
        _mapping={"id": "ep3", "task_description": "x", "outcome": "success",
                  "success": True, "constitutional_score": 1.0, "started_at": "s",
                  "canvas_type": "c", "presentation_summary": "p"})]
    sess = MagicMock()
    sess.execute.return_value = cursor
    monkeypatch.setattr("core.database.SessionLocal", MagicMock(return_value=sess))
    out3 = await wsvc.recall_experiences_with_detail(
        "t1", "Finance", "task", detail_level=DetailLevel.STANDARD)
    assert out3[0]["id"] == "ep3"


async def test_wm_archive_episode_cold_storage(wsvc):
    wsvc.sync_episode_to_lancedb = AsyncMock(side_effect=[True, False, RuntimeError("x")])
    assert await wsvc.archive_episode_to_cold_storage("e1", "a", "t", "task", "s", "l", "F", "junior") is True
    assert await wsvc.archive_episode_to_cold_storage("e1", "a", "t", "task", "s", "l", "F", "junior") is False
    assert await wsvc.archive_episode_to_cold_storage("e1", "a", "t", "task", "s", "l", "F", "junior") is False


async def test_wm_get_recent_episodes(wsvc, monkeypatch):
    ep = SimpleNamespace(
        id="e1", task_description="t", outcome="success", success=True,
        maturity_at_time="junior", constitutional_score=1.0,
        human_intervention_count=0, confidence_score=0.5, step_efficiency=1.0,
        started_at=DT, completed_at=DT)
    sl = MagicMock()
    sl.return_value.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [ep]
    monkeypatch.setattr("core.database.SessionLocal", sl)  # inner import
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    res = await wsvc.get_recent_episodes("a1", "t1")
    assert res[0]["episode_id"] == "e1"
    sl2 = MagicMock(side_effect=RuntimeError("x"))
    monkeypatch.setattr("core.database.SessionLocal", sl2)
    monkeypatch.setattr(wm_mod, "SessionLocal", sl2)
    assert await wsvc.get_recent_episodes("a1", "t1") == []


def test_wm_get_episode_feedback_for_decision(wsvc, monkeypatch):
    assert wsvc.get_episode_feedback_for_decision([]) == {}
    fb = SimpleNamespace(
        episode_id="e1", id="fb1", feedback_score=0.5, feedback_notes="n",
        feedback_category="c", provider_id="p", provider_type="t", provided_at=DT)
    sl = MagicMock()
    sl.return_value.query.return_value.filter.return_value.all.return_value = [fb]
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    res = wsvc.get_episode_feedback_for_decision(["e1"])
    assert res["e1"][0]["feedback_score"] == 0.5
    sl2 = MagicMock(side_effect=RuntimeError("x"))
    monkeypatch.setattr(wm_mod, "SessionLocal", sl2)
    assert wsvc.get_episode_feedback_for_decision(["e1"]) == {}


# ============================================================================
# WORLD MODEL — skill recommendation
# ============================================================================

def test_wm_recommend_skills_no_agent(wsvc, monkeypatch):
    sl = MagicMock()
    sl.return_value.query.return_value.filter.return_value.first.return_value = None
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    assert wsvc.recommend_skills_for_task("task", "a1", "t1") == []


def test_wm_recommend_skills_flow(wsvc, monkeypatch):
    agent = SimpleNamespace(category="Finance", name="MySkill")
    skill_ep = {"episode_id": "e1",
                "metadata": {"skill_type": "openclaw", "skill_id": "sk1"},
                "outcome": "success", "similarity_score": 0.8, "final_score": 0.9}
    wsvc.recall_episodes = AsyncMock(return_value=[skill_ep])
    episode_rows = [SimpleNamespace(success=True, completed_at=DT)]
    skill_row = SimpleNamespace(name="MySkill")
    sl = MagicMock()
    db = sl.return_value
    db.query.return_value.filter.return_value.first.return_value = agent
    db.query.return_value.filter.return_value.all.return_value = episode_rows
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = episode_rows
    # Skill table query — same chain; last first() call determines skill
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    with patch.object(WorldModelService, "recommend_skills_for_task",
                      wraps=wsvc.recommend_skills_for_task):
        recs = wsvc.recommend_skills_for_task("task desc", "a1", "t1")
    assert recs and recs[0].skill_id == "sk1" and recs[0].success_rate == 1.0
    # no skill episodes
    wsvc.recall_episodes = AsyncMock(return_value=[{"episode_id": "e1", "metadata": {}}])
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    assert wsvc.recommend_skills_for_task("task", "a1", "t1") == []
    # recall raising tolerated
    wsvc.recall_episodes = AsyncMock(side_effect=RuntimeError("x"))
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    assert wsvc.recommend_skills_for_task("task", "a1", "t1") == []
    # outer exception
    sl2 = MagicMock(side_effect=RuntimeError("x"))
    monkeypatch.setattr(wm_mod, "SessionLocal", sl2)
    assert wsvc.recommend_skills_for_task("task", "a1", "t1") == []


def test_wm_get_successful_skills(wsvc, monkeypatch):
    eps = [SimpleNamespace(metadata_json={"skill_id": "s1"})]
    sl = MagicMock()
    sl.return_value.query.return_value.filter.return_value.limit.return_value.all.return_value = eps
    monkeypatch.setattr(wm_mod, "SessionLocal", sl)
    assert wsvc.get_successful_skills_for_agent("a1", "t1") == {"s1"}
    monkeypatch.setattr(wm_mod, "SessionLocal", MagicMock(side_effect=RuntimeError("x")))
    assert wsvc.get_successful_skills_for_agent("a1", "t1") == set()


# ============================================================================
# WORLD MODEL — canvas family
# ============================================================================

async def test_wm_canvas_recall_and_preferences(wsvc, mock_handler):
    good = {"id": "e1", "metadata": {
        "agent_id": "a1", "task_type": "t", "input_summary": "in",
        "outcome": "success", "learnings": "l", "confidence_score": 0.8,
        "feedback_score": 0.6, "artifacts": [], "step_efficiency": 1.0,
        "trace": {}, "agent_role": "Finance", "specialty": "s",
        "timestamp": DT.isoformat(), "canvas_types": ["sheets"]}}
    bad_role = {"id": "e2", "metadata": {"agent_id": "other", "outcome": "success"}}
    failed = {"id": "e3", "metadata": {"agent_id": "a1", "outcome": "failure",
                                       "canvas_types": ["sheets"], "feedback_score": -0.9,
                                       "engagement_time_seconds": 10.0}}
    other_canvas = {"id": "e4", "metadata": {"agent_id": "a1", "outcome": "success",
                                             "canvas_types": ["charts"]}}
    mock_handler.search = Mock(return_value=[good, bad_role, failed, other_canvas])
    exps = await wsvc.recall_experiences_with_canvas("a1", "task", preferred_canvas_type="sheets")
    assert [e.id for e in exps] == ["e1"]
    # preferences
    prefs = await wsvc.get_canvas_type_preferences("a1", task_type="t")
    assert prefs["sheets"]["count"] == 2
    assert prefs["sheets"]["success_rate"] == 0.5
    assert prefs["sheets"]["avg_feedback_score"] == pytest.approx(-0.15)  # (0.6 + -0.9) / 2
    assert prefs["charts"]["avg_feedback_score"] == 0.0  # no feedback recorded
    # no data at all
    mock_handler.search = Mock(return_value=[])
    assert await wsvc.get_canvas_type_preferences("a1") == {}
    # error
    mock_handler.search = Mock(side_effect=RuntimeError("x"))
    assert await wsvc.recall_experiences_with_canvas("a1", "t") == []
    assert await wsvc.get_canvas_type_preferences("a1") == {}


async def test_wm_recommend_canvas_type(wsvc):
    # no preferences -> generic
    wsvc.get_canvas_type_preferences = AsyncMock(return_value={})
    rec = await wsvc.recommend_canvas_type("a1", "t")
    assert rec["canvas_type"] == "generic"
    # insufficient sample
    wsvc.get_canvas_type_preferences = AsyncMock(return_value={
        "sheets": {"count": 1, "success_rate": 1.0, "avg_engagement": 0, "avg_feedback_score": 0}})
    rec2 = await wsvc.recommend_canvas_type("a1", "t")
    assert rec2["reason"] == "Insufficient data for recommendation"
    # good sample
    wsvc.get_canvas_type_preferences = AsyncMock(return_value={
        "sheets": {"count": 5, "success_rate": 0.9, "avg_engagement": 45.0,
                   "avg_feedback_score": 0.6},
        "charts": {"count": 4, "success_rate": 0.5, "avg_engagement": 10.0,
                   "avg_feedback_score": 0.0}})
    rec3 = await wsvc.recommend_canvas_type("a1", "t")
    assert rec3["canvas_type"] == "sheets"
    assert "High success rate" in rec3["reason"] and "feedback" in rec3["reason"]
    assert rec3["alternatives"] == ["charts"]
    # error
    wsvc.get_canvas_type_preferences = AsyncMock(side_effect=RuntimeError("x"))
    assert await wsvc.recommend_canvas_type("a1", "t") is None


async def test_wm_record_canvas_outcome(wsvc, experience):
    wsvc.record_experience = AsyncMock(return_value=True)
    assert await wsvc.record_canvas_outcome(experience, ["sheets"],
                                            engagement_time_seconds=30.0,
                                            user_feedback=0.5) is True
    wsvc.record_experience = AsyncMock(side_effect=RuntimeError("x"))
    assert await wsvc.record_canvas_outcome(experience, []) is False


def test_wm_extract_canvas_insights(wsvc):
    episodes = [{
        "canvas_context": [
            {"canvas_type": "sheets", "action": "close", "id": "c1"},
            {"canvas_type": "charts", "action": "present", "id": "c2"},
            {"canvas_type": "forms", "action": "submit", "id": "c3"},
            {"action": "no-type", "id": "c4"},
        ],
        "feedback_context": [{"rating": 5}, {"rating": 4}],
    }]
    ins = wsvc._extract_canvas_insights(episodes)
    assert ins["canvas_type_counts"] == {"sheets": 1, "charts": 1, "forms": 1}
    assert ins["user_actions"] == {"close": 1, "present": 1, "submit": 1}
    assert ins["preferred_canvas_types"][0] in ("sheets", "charts", "forms")
    assert any(h["canvas_type"] == "sheets" for h in ins["high_engagement_canvases"])
    # low feedback -> no high engagement
    ins2 = wsvc._extract_canvas_insights([{
        "canvas_context": [{"canvas_type": "sheets", "action": "close"}],
        "feedback_context": [{"rating": 2}]}])
    assert ins2["high_engagement_canvases"] == []
    # broken input tolerated
    ins3 = wsvc._extract_canvas_insights([{"canvas_context": None}])
    assert ins3["canvas_type_counts"] == {}


# ============================================================================
# META AGENT — fixtures
# ============================================================================

@pytest.fixture
def meta_agent(monkeypatch):
    monkeypatch.setattr(ama, "WorldModelService", MagicMock())
    monkeypatch.setattr(ama, "CapabilityGraduationService", MagicMock())
    monkeypatch.setattr(ama, "get_canvas_provider", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(ama, "mcp_service", MagicMock())
    monkeypatch.setattr(ama, "AgentGovernanceService", MagicMock())
    monkeypatch.setattr(ama, "AgentFleetService", MagicMock())
    monkeypatch.setattr(ama, "FleetOptimizationService", MagicMock())
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)

    sl = MagicMock()
    sl.return_value.__enter__.return_value = MagicMock()
    monkeypatch.setattr(ama, "SessionLocal", sl)

    sf = MagicMock()
    sf.get_llm_service.return_value = MagicMock()
    monkeypatch.setattr("core.service_factory.ServiceFactory", sf)

    agent = AtomMetaAgent()
    agent.llm = MagicMock()
    agent.world_model = MagicMock()
    return agent


def _prepare_execute(agent, sl, monkeypatch, *, route_category=None, tools=None):
    from ai.nlp_engine import NaturalLanguageEngine, RouteCategory, RouteClassification

    workspace = SimpleNamespace(tenant_id="default")
    db = sl.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.first.return_value = workspace

    nlu = MagicMock()
    nlu.classify_route = AsyncMock(return_value=RouteClassification(
        category=route_category or RouteCategory.ONE_OFF,
        reasoning="r", confidence=0.9,
    ))
    monkeypatch.setattr(ama, "NaturalLanguageEngine", MagicMock(return_value=nlu))

    agent.world_model.recall_experiences = AsyncMock(return_value={"experiences": []})
    agent.mcp.get_all_tools = AsyncMock(return_value=tools or [
        {"name": "trigger_workflow", "description": "d", "parameters": {}},
    ])
    monkeypatch.setattr("core.field_guide_service.get_field_guide_service",
                        lambda: MagicMock(get_field_guide_context=lambda w: "guide"))
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
    agent._persist_reasoning_step = MagicMock(return_value="step-id")
    agent._record_execution = AsyncMock()
    return nlu


def _step(**kw):
    return ama.ReActStep(thought=kw.get("thought", "t"),
                         action=kw.get("action"),
                         actions=kw.get("actions"),
                         final_answer=kw.get("final_answer"))


def _call(tool, **params):
    return ToolCall(tool=tool, params=params)


# ============================================================================
# META — is_error_observation helper
# ============================================================================

def test_meta_is_error_observation():
    assert ama._is_error_observation(None) is False
    assert ama._is_error_observation("Tool error. Please try again.") is True
    assert ama._is_error_observation("Governance blocked: nope") is True
    assert ama._is_error_observation("was rejected by user") is True
    assert ama._is_error_observation("sandbox blocked the call") is True
    assert ama._is_error_observation("all good, error field is fine") is False


# ============================================================================
# META — execute() branches
# ============================================================================

_sl_holder = {}


@pytest.fixture
def meta_sl(meta_agent, monkeypatch):
    sl = ama.SessionLocal
    _sl_holder["sl"] = sl
    _prepare_execute(meta_agent, sl, monkeypatch)
    return sl


async def test_meta_execute_success_final_answer_fx(meta_agent, meta_sl, monkeypatch):
    meta_agent._react_step = AsyncMock(return_value=_step(final_answer="done"))
    res = await meta_agent.execute("hello")
    assert res["status"] == "success" and res["final_output"] == "done"


async def test_meta_execute_canvas_context(meta_agent, meta_sl, monkeypatch):
    canvas_state = SimpleNamespace(
        canvas_id="c1", artifact_count=2,
        comments=[SimpleNamespace(content="fix the chart")])
    meta_agent.canvas_provider.get_canvas_context = AsyncMock(return_value=canvas_state)
    meta_agent.canvas_provider.format_for_agent = MagicMock(return_value="CANVAS TEXT")
    meta_agent.world_model.recall_episodes = AsyncMock(return_value=[{"episode_id": "e1"}])
    meta_agent._react_step = AsyncMock(return_value=_step(final_answer="ok"))
    res = await meta_agent.execute("do a thing", canvas_context={"canvas_id": "c1"})
    assert res["status"] == "success"
    assert meta_agent.world_model.recall_episodes.called
    # canvas fetch failure re-raises
    meta_agent.canvas_provider.get_canvas_context = AsyncMock(side_effect=RuntimeError("x"))
    with pytest.raises(RuntimeError):
        await meta_agent.execute("again", canvas_context={"canvas_id": "c1"})


async def test_meta_execute_tool_search_and_delegation(meta_agent, meta_sl, monkeypatch):
    meta_agent.mcp.search_tools = AsyncMock(return_value=[
        {"name": "new_tool", "description": "d", "parameters": {}}])
    meta_agent._execute_delegation = AsyncMock(return_value="Delegation Result from X:\nok")
    meta_agent._execute_tool_with_governance = AsyncMock(return_value={"success": True})
    meta_agent._react_step = AsyncMock(side_effect=[
        _step(action=_call("mcp_tool_search", query="q")),
        _step(action=_call("delegate_task", agent_name="accounting", task="t")),
        _step(action=_call("some_tool", x=1)),
        _step(final_answer="finished"),
    ])
    cb = AsyncMock()
    res = await meta_agent.execute("short req", step_callback=cb)
    assert res["status"] == "success"
    assert cb.await_count >= 4
    assert meta_agent.mcp.search_tools.called
    assert meta_agent._execute_delegation.called


async def test_meta_execute_no_action_final_thought(meta_agent, meta_sl, monkeypatch):
    meta_agent._react_step = AsyncMock(return_value=_step(thought="I will answer now"))
    res = await meta_agent.execute("hi")
    assert res["final_output"] == "I will answer now"


async def test_meta_execute_budget_exceeded(meta_agent, meta_sl, monkeypatch):
    meta_agent._check_budget_before_react = AsyncMock(return_value={
        "allowed": False, "reason": "over", "enforcement_mode": "hard_stop"})
    meta_agent._react_step = AsyncMock()
    res = await meta_agent.execute("hi")
    assert res["status"] == "budget_exceeded"
    assert res["failure_reason"] == "over" and res["failure_mode"] == "hard_stop"
    meta_agent._react_step.assert_not_called()


async def test_meta_execute_max_steps_timeout(meta_agent, meta_sl, monkeypatch):
    meta_agent._execute_tool_with_governance = AsyncMock(return_value="ok")
    meta_agent._react_step = AsyncMock(return_value=_step(action=_call("t", a=1)))
    res = await meta_agent.execute("hi")
    assert res["status"] == "timeout"
    assert res["final_output"].startswith("Maximum reasoning steps")


async def test_meta_execute_body_exception_finalizes_failed(meta_agent, meta_sl, monkeypatch):
    meta_agent.world_model.recall_experiences = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await meta_agent.execute("hi")


async def test_meta_execute_killrun_aborted(meta_agent, meta_sl, monkeypatch):
    from core.sandbox_killrun import KillRunAborted
    meta_agent._react_step = AsyncMock(side_effect=KillRunAborted("tripwire"))
    res = await meta_agent.execute("hi")
    assert res["status"] == "killed_sandbox"
    assert "killed by sandbox" in res["final_output"]


async def test_meta_execute_parallel_tools(meta_agent, meta_sl, monkeypatch):
    monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                        lambda: True)
    meta_agent._execute_parallel_tools = AsyncMock(return_value=[
        {"tool_name": "a", "params": {}, "output": "Tool error. x",
         "verified_kind": "unverified", "verified_evidence": None},
        {"tool_name": "b", "params": {}, "output": "ok",
         "verified_kind": "failed_verification", "verified_evidence": "ev"},
    ])
    meta_agent._react_step = AsyncMock(side_effect=[
        _step(actions=[_call("a"), _call("b")]),
        _step(final_answer="parallel done"),
    ])
    res = await meta_agent.execute("parallel test")
    assert res["status"] == "success"


async def test_meta_execute_actions_degraded_to_single(meta_agent, meta_sl, monkeypatch):
    monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                        lambda: False)
    meta_agent._execute_tool_with_governance = AsyncMock(return_value="obs")
    meta_agent._react_step = AsyncMock(side_effect=[
        _step(actions=[_call("t1")]),
        _step(final_answer="done"),
    ])
    res = await meta_agent.execute("degrade test")
    assert res["status"] == "success"
    meta_agent._execute_tool_with_governance.assert_awaited_once()


async def test_meta_execute_fleet_routing_force(meta_agent, meta_sl, monkeypatch):
    from ai.nlp_engine import RouteCategory
    nlu = _prepare_execute(meta_agent, _sl_holder["sl"], monkeypatch,
                           route_category=RouteCategory.ONE_OFF)
    frt = SimpleNamespace(
        fleet_routing_enabled=lambda: True,
        fleet_routing_force_enforce=lambda: True)
    monkeypatch.setattr("core.fleet_routing_config.fleet_routing_enabled",
                        frt.fleet_routing_enabled)
    monkeypatch.setattr("core.fleet_routing_config.fleet_routing_force_enforce",
                        frt.fleet_routing_force_enforce)
    meta_agent.route_with_governance = AsyncMock(return_value={
        "chain_id": "ch1", "specialists_count": 2, "status": "recruited"})
    cb = AsyncMock()
    long_req = "x" * 60
    res = await meta_agent.execute(long_req, step_callback=cb)
    assert res["chain_id"] == "ch1"
    assert any(c.args[0].get("step_type") == "fleet_recruitment"
               for c in cb.await_args_list)


async def test_meta_execute_fleet_routing_shadow_and_failure(meta_agent, meta_sl, monkeypatch):
    from ai.nlp_engine import RouteCategory
    _prepare_execute(meta_agent, _sl_holder["sl"], monkeypatch,
                     route_category=RouteCategory.ONE_OFF)
    monkeypatch.setattr("core.fleet_routing_config.fleet_routing_enabled", lambda: True)
    monkeypatch.setattr("core.fleet_routing_config.fleet_routing_force_enforce",
                        lambda: False)
    meta_agent.route_with_governance = AsyncMock(return_value={"chain_id": "c"})
    meta_agent._react_step = AsyncMock(return_value=_step(final_answer="shadow"))
    res = await meta_agent.execute("x" * 60)
    assert res["final_output"] == "shadow"
    # routing failure falls back to ReAct
    meta_agent.route_with_governance = AsyncMock(side_effect=RuntimeError("fleet down"))
    meta_agent._react_step = AsyncMock(return_value=_step(final_answer="fallback"))
    res2 = await meta_agent.execute("x" * 60)
    assert res2["final_output"] == "fallback"


async def test_meta_execute_queen_blueprint(meta_agent, meta_sl, monkeypatch):
    from ai.nlp_engine import RouteCategory
    _prepare_execute(meta_agent, _sl_holder["sl"], monkeypatch,
                     route_category=RouteCategory.AUTOMATION)
    queen = MagicMock()
    queen.generate_blueprint = AsyncMock(return_value={
        "architecture_name": "Arch", "nodes": [{"name": "n1", "type": "t",
                                                "capability_required": "c"}],
        "missing_capabilities": ["cap_x"]})
    meta_agent.queen = queen
    meta_agent._react_step = AsyncMock(return_value=_step(final_answer="planned"))
    res = await meta_agent.execute("create a complex automation workflow for reporting")
    assert res["status"] == "success"
    queen.generate_blueprint.assert_awaited_once()


async def test_meta_execute_queen_failure_orchestrator_fallback(meta_agent, meta_sl, monkeypatch):
    from ai.nlp_engine import RouteCategory
    _prepare_execute(meta_agent, _sl_holder["sl"], monkeypatch,
                     route_category=RouteCategory.AUTOMATION)
    meta_agent.queen = MagicMock()
    meta_agent.queen.generate_blueprint = AsyncMock(side_effect=RuntimeError("queen fail"))
    meta_agent.orchestrator.generate_dynamic_workflow = AsyncMock(return_value={
        "nodes": [{"a": 1}, {"b": 2}]})
    meta_agent._react_step = AsyncMock(return_value=_step(final_answer="fallback plan"))
    res = await meta_agent.execute("create a complex automation workflow for reporting")
    assert res["status"] == "success"
    meta_agent.orchestrator.generate_dynamic_workflow.assert_awaited_once()


# ============================================================================
# META — _react_step
# ============================================================================

async def test_meta_react_step_structured(meta_agent, monkeypatch):
    # durable-facts recall off (raises internally -> tolerated)
    monkeypatch.setattr(ama, "_get_active_facts_for_prompt",
                        MagicMock(side_effect=RuntimeError("off")))
    meta_agent.llm.generate_structured_response = AsyncMock(
        return_value=_step(final_answer="struct"))
    out = await meta_agent._react_step("req", {"experiences": [], "knowledge": [],
                                               "formulas": [], "business_facts": []},
                                       "tools", "history", {})
    assert out.final_answer == "struct"
    args = meta_agent.llm.generate_structured_response.call_args.kwargs
    assert "AVAILABLE TOOLS" in args["system_instruction"]
    assert "(No prior context)" in args["prompt"]


async def test_meta_react_step_memory_sections(meta_agent):
    exp = SimpleNamespace(input_summary="sum", outcome="Success")
    fact = SimpleNamespace(verification_status="verified", fact="F",
                           metadata={"source": "s"})
    ep_exp = {"canvas_id": "canvas123", "task_description": "td",
              "outcome": "success", "canvas_boost": 0.3}
    meta_agent.llm.generate_structured_response = AsyncMock(return_value=_step(final_answer="x"))
    await meta_agent._react_step(
        "req",
        {"experiences": [exp], "knowledge": [{"text": "k"}],
         "formulas": [{"name": "F", "description": "d"}], "business_facts": [fact],
         "canvas_episodes": [ep_exp]},
        "tools", "history", {}, canvas_text="CANVAS", turn_index=1)
    prompt = meta_agent.llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "PAST EXPERIENCES" in prompt and "sum" in prompt
    assert "CANVAS EPISODES" in prompt
    assert "RELEVANT KNOWLEDGE" in prompt
    assert "AVAILABLE FORMULAS" in prompt
    assert "TRUSTED BUSINESS FACTS" in prompt
    sysp = meta_agent.llm.generate_structured_response.call_args.kwargs["system_instruction"]
    assert "CURRENT CANVAS STATE" in sysp


async def test_meta_react_step_fallback_paths(meta_agent):
    meta_agent.llm.generate_structured_response = AsyncMock(return_value=None)
    # error keyword response
    meta_agent.llm.generate_completion = AsyncMock(return_value={"content": "LLM not initialized"})
    out = await meta_agent._react_step("req", {}, "t", "h", {})
    assert out.final_answer == "LLM not initialized"
    # empty content
    meta_agent.llm.generate_completion = AsyncMock(return_value={"content": None})
    out2 = await meta_agent._react_step("req", {}, "t", "h", {})
    assert "AI provider unavailable" in out2.final_answer
    # plain content
    meta_agent.llm.generate_completion = AsyncMock(return_value={"content": "plain answer"})
    out3 = await meta_agent._react_step("req", {}, "t", "h", {})
    assert out3.final_answer == "plain answer"


# ============================================================================
# META — _trigger_workflow / _execute_delegation
# ============================================================================

async def test_meta_trigger_workflow(meta_agent, monkeypatch):
    assert "workflow_id is required" in await meta_agent._trigger_workflow(None, {}, {})
    eng = MagicMock()
    eng.start_workflow = AsyncMock(return_value="exec-1")
    monkeypatch.setattr("core.workflow_engine.get_workflow_engine", lambda: eng)
    out = await meta_agent._trigger_workflow("wf1", {"a": 1}, {})
    assert "exec-1" in out
    monkeypatch.setattr("core.workflow_engine.get_workflow_engine",
                        MagicMock(side_effect=RuntimeError("x")))
    assert "Error triggering" in await meta_agent._trigger_workflow("wf1", {}, {})


async def test_meta_execute_delegation(meta_agent, monkeypatch):
    agent = SimpleNamespace(name="Accounting",
                            execute=AsyncMock(return_value={"final_output": "did it"}))
    monkeypatch.setattr("core.business_agents.get_specialized_agent",
                        MagicMock(return_value=agent))
    out = await meta_agent._execute_delegation("accounting", "task", {})
    assert "did it" in out
    # agent missing
    monkeypatch.setattr("core.business_agents.get_specialized_agent",
                        MagicMock(return_value=None))
    out2 = await meta_agent._execute_delegation("nope", "task", {})
    assert "not found" in out2
    # exception
    monkeypatch.setattr("core.business_agents.get_specialized_agent",
                        MagicMock(side_effect=RuntimeError("x")))
    assert await meta_agent._execute_delegation("a", "t", {}) == "Delegation failed. Please try again."


# ============================================================================
# META — _execute_tool_with_governance
# ============================================================================

def _gov_db(meta_agent):
    db = ama.SessionLocal.return_value
    return db


async def test_meta_governance_allowed_tool(meta_agent):
    db = _gov_db(meta_agent)
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 1})
    meta_agent.mcp.call_tool = AsyncMock(return_value={"success": True})
    out = await meta_agent._execute_tool_with_governance("read_tool", {}, {}, None)
    assert out == str({"success": True})


async def test_meta_governance_hitl_approved_and_rejected(meta_agent):
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 2,
        "reason": "complex"})
    gov.request_approval = MagicMock(return_value="aid")
    meta_agent._wait_for_approval = AsyncMock(side_effect=[True, False])
    meta_agent.mcp.call_tool = AsyncMock(return_value="ran")
    out = await meta_agent._execute_tool_with_governance("write_tool", {}, {}, None)
    assert out == "ran"
    out2 = await meta_agent._execute_tool_with_governance("write_tool", {}, {}, None)
    assert "REJECTED" in out2


async def test_meta_governance_blocked(meta_agent):
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": False, "requires_human_approval": False, "action_complexity": 1,
        "reason": "not allowed"})
    out = await meta_agent._execute_tool_with_governance("t", {}, {}, None)
    assert out.startswith("Governance blocked")


async def test_meta_tool_special_paths(meta_agent):
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 1})
    # trigger_workflow
    meta_agent._trigger_workflow = AsyncMock(return_value="wf ran")
    assert await meta_agent._execute_tool_with_governance(
        "trigger_workflow", {"workflow_id": "w"}, {}, None) == "wf ran"
    # delegate_task
    meta_agent._execute_delegation = AsyncMock(return_value="delegated")
    assert await meta_agent._execute_tool_with_governance(
        "delegate_task", {"agent_name": "a", "task": "t"}, {}, None) == "delegated"
    # recruit_fleet
    meta_agent._recruit_fleet = AsyncMock(return_value="fleet ok")
    assert await meta_agent._execute_tool_with_governance(
        "recruit_fleet", {"sub_tasks": []}, {}, None) == "fleet ok"


async def test_meta_invoke_capability(meta_agent):
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 1})
    # student blocked
    meta_agent.graduation_service.get_maturity = MagicMock(return_value="student")
    out = await meta_agent._execute_tool_with_governance(
        "invoke_capability", {"capability_name": "cap"}, {}, None)
    assert "STUDENT level" in out
    # senior executes + graduation recording
    meta_agent.graduation_service.get_maturity = MagicMock(return_value="senior")
    meta_agent.mcp.call_tool = AsyncMock(
        return_value='{"success": true, "verified": true, "evidence": "e"}')
    out2 = await meta_agent._execute_tool_with_governance(
        "invoke_capability", {"capability_name": "cap"}, {}, None)
    meta_agent.graduation_service.record_usage.assert_called_once()
    # graduation parse failure tolerated
    meta_agent.mcp.call_tool = AsyncMock(return_value=RuntimeError("not json"))
    await meta_agent._execute_tool_with_governance(
        "invoke_capability", {"capability_name": "cap"}, {}, None)
    assert meta_agent.graduation_service.record_usage.call_count == 2


async def test_meta_tool_sandbox_enforced_and_shadow(meta_agent, monkeypatch):
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 1})
    enforced = MagicMock(requires_review=True, enforced=True, decision="blocked",
                         violation_detail="bad")
    with patch.object(ama, "_meta_agent_sandbox_check", MagicMock(return_value=enforced)):
        out = await meta_agent._execute_tool_with_governance("t", {}, {}, None)
        assert out.startswith("Sandbox blocked")
    shadow = MagicMock(requires_review=True, enforced=False, violation_type="v")
    meta_agent.mcp.call_tool = AsyncMock(return_value="ok")
    with patch.object(ama, "_meta_agent_sandbox_check", MagicMock(return_value=shadow)):
        out2 = await meta_agent._execute_tool_with_governance("t", {}, {}, None)
        assert out2 == "ok"


async def test_meta_tool_action_judge_block_and_escalate(meta_agent, monkeypatch):
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 1})
    monkeypatch.setattr("core.sandbox_config.is_sandbox_judge_enabled", lambda: True)
    judge_cls = MagicMock()
    verdict_block = SimpleNamespace(verdict="block", rationale="risky")
    judge_cls.return_value.evaluate = AsyncMock(return_value=verdict_block)
    monkeypatch.setattr("core.llm.action_judge.ActionJudge", judge_cls)
    out = await meta_agent._execute_tool_with_governance("t", {}, {}, None)
    assert "safety judge" in out
    # escalate path
    verdict_esc = SimpleNamespace(verdict="escalate", rationale="check")
    judge_cls.return_value.evaluate = AsyncMock(return_value=verdict_esc)
    gov.request_approval = MagicMock(return_value="aid2")
    meta_agent._wait_for_approval = AsyncMock(side_effect=[False, True])
    out2 = await meta_agent._execute_tool_with_governance("t", {}, {}, None)
    assert "REJECTED" in out2
    meta_agent.mcp.call_tool = AsyncMock(return_value="ran")
    out3 = await meta_agent._execute_tool_with_governance("t", {}, {}, None)
    assert out3 == "ran"
    # judge raising tolerated
    judge_cls.return_value.evaluate = AsyncMock(side_effect=RuntimeError("j"))
    out4 = await meta_agent._execute_tool_with_governance("t", {}, {}, None)
    assert out4 == "ran"


async def test_meta_tool_killrun_and_generic_error(meta_agent):
    from core.sandbox_killrun import KillRunAborted
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(side_effect=KillRunAborted("kill"))
    with pytest.raises(KillRunAborted):
        await meta_agent._execute_tool_with_governance("t", {}, {}, None)
    gov.can_perform_action_async = AsyncMock(side_effect=RuntimeError("x"))
    assert await meta_agent._execute_tool_with_governance(
        "t", {}, {}, None) == "Tool error. Please try again."


async def test_meta_tool_pre_approved_skips_governance(meta_agent):
    meta_agent.mcp.call_tool = AsyncMock(return_value="fast")
    out = await meta_agent._execute_tool_with_governance("t", {}, {}, None, pre_approved=True)
    assert out == "fast"
    ama.AgentGovernanceService.assert_not_called()


# ============================================================================
# META — _recruit_fleet
# ============================================================================

async def test_meta_recruit_fleet_success(meta_agent):
    chain = SimpleNamespace(id="ch1")
    fs = ama.AgentFleetService.return_value
    fs.initialize_fleet = MagicMock(return_value=chain)
    fs.recruit_member = MagicMock(return_value=SimpleNamespace())
    opt = ama.FleetOptimizationService.return_value
    opt.get_optimization_parameters = MagicMock(return_value={"optimization_reason": "r"})
    specialist = SimpleNamespace(id="ag1", name="Finance")
    radio_thread = SimpleNamespace(id="rt1")

    db = ama.SessionLocal.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(context_json={}, id="l1")]

    with patch("core.business_agents.get_specialized_agent",
               MagicMock(return_value=specialist)), \
         patch("core.agent_radio.radio_adapter.attach_thread_for_chain",
               MagicMock(return_value=radio_thread)):
        cb = AsyncMock()
        out = await meta_agent._recruit_fleet(
            "goal", [{"domain": "finance", "task": "analyze",
                      "use_optimizer": True},
                     {"domain": "ops", "task": "do", "use_optimizer": False}],
            {"execution_id": "e"}, cb)
    assert "ch1" in out and "Finance" in out
    assert cb.await_count == 1
    # missing specialist falls back to placeholder id
    with patch("core.business_agents.get_specialized_agent",
               MagicMock(return_value=None)), \
         patch("core.agent_radio.radio_adapter.attach_thread_for_chain",
               MagicMock(side_effect=RuntimeError("no radio"))):
        out2 = await meta_agent._recruit_fleet("g", [{"domain": "d", "task": "t"}], {})
    assert "Fleet Successfully Recruited" in out2


async def test_meta_recruit_fleet_failure(meta_agent):
    ama.AgentFleetService.return_value.initialize_fleet = MagicMock(
        side_effect=RuntimeError("db"))
    out = await meta_agent._recruit_fleet("g", [], {})
    assert out == "Fleet recruitment failed. Please try again."


# ============================================================================
# META — spawn_agent / query_memory / mentorship
# ============================================================================

async def test_meta_spawn_agent_paths(meta_agent):
    # template, ephemeral
    a1 = await meta_agent.spawn_agent("finance_analyst")
    assert a1.name == "Finance Analyst"
    assert meta_agent.graduation_service.reset_maturity.called
    # custom
    a2 = await meta_agent.spawn_agent("custom", custom_params={
        "name": "Mine", "category": "X", "description": "d",
        "capabilities": [], "default_params": {}})
    assert a2.name == "Mine"
    # unknown template
    with pytest.raises(ValueError):
        await meta_agent.spawn_agent("bogus")
    # persist without db session
    gov = ama.AgentGovernanceService.return_value
    gov.register_or_update_agent = MagicMock(return_value=SimpleNamespace(id="p1"))
    a3 = await meta_agent.spawn_agent("sales_assistant", persist=True)
    assert a3.id == "p1"
    # persist with provided db
    provided = MagicMock()
    a4 = await meta_agent.spawn_agent("king_agent", persist=True, db=provided)
    assert gov.register_or_update_agent.call_count == 2


async def test_meta_query_memory_scopes(meta_agent):
    full = {"experiences": ["e"], "knowledge": ["k"]}
    meta_agent.world_model.recall_experiences = AsyncMock(return_value=full)
    assert await meta_agent.query_memory("q", scope="experiences") == {"experiences": ["e"]}
    assert await meta_agent.query_memory("q", scope="knowledge") == {"knowledge": ["k"]}
    assert await meta_agent.query_memory("q") is full


async def test_meta_mentorship_guidance(meta_agent, monkeypatch):
    # no supervisors -> interim supervisor note
    db = ama.SessionLocal.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        category="Finance")
    db.query.return_value.filter.return_value.count.return_value = 0
    monkeypatch.setattr(ama.asyncio, "to_thread", lambda fn: _async_wrap(fn()))
    meta_agent.llm.generate_response = AsyncMock(return_value="Guide")
    out = await meta_agent.generate_mentorship_guidance("s1", "act", {"a": 1}, "why")
    assert out == "Guide"
    assert "Interim Supervisor" in meta_agent.llm.generate_response.call_args.kwargs[
        "system_instruction"]
    # with supervisors -> no interim note
    db.query.return_value.filter.return_value.count.return_value = 2
    meta_agent.llm.generate_response = AsyncMock(return_value=None)
    out2 = await meta_agent.generate_mentorship_guidance("s1", "act", {}, "why")
    assert "unable to provide guidance" in out2


def _async_wrap(value):
    fut = asyncio.get_event_loop().create_future()
    fut.set_result(value)
    return fut


async def test_meta_wait_for_approval(meta_agent, monkeypatch):
    gov = ama.AgentGovernanceService.return_value
    from core.models import HITLActionStatus
    gov.get_approval_status = MagicMock(side_effect=[
        {"status": "pending"}, {"status": HITLActionStatus.APPROVED.value}])
    monkeypatch.setattr(ama, "asyncio", SimpleNamespace(
        sleep=AsyncMock(side_effect=lambda s: None)))
    assert await meta_agent._wait_for_approval("aid") is True
    gov.get_approval_status = MagicMock(return_value={"status": HITLActionStatus.REJECTED.value})
    assert await meta_agent._wait_for_approval("aid") is False


async def test_meta_wait_for_all_approvals(meta_agent, monkeypatch):
    from core.models import HITLActionStatus
    gov = ama.AgentGovernanceService.return_value
    monkeypatch.setattr(ama, "asyncio", SimpleNamespace(
        sleep=AsyncMock(side_effect=lambda s: None)))
    gov.get_approval_status = MagicMock(side_effect=[
        {"status": HITLActionStatus.APPROVED.value},
        {"status": HITLActionStatus.APPROVED.value},
        {"status": HITLActionStatus.APPROVED.value},
        {"status": HITLActionStatus.REJECTED.value},
    ])
    assert await meta_agent._wait_for_all_approvals(["a", "b"]) is True
    assert await meta_agent._wait_for_all_approvals(["a", "b"]) is False


# ============================================================================
# META — parallel tools
# ============================================================================

async def test_meta_parallel_disabled_sequential(meta_agent, monkeypatch):
    monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: False)
    monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
    meta_agent._execute_tool_with_governance = AsyncMock(side_effect=["o1", "o2"])
    recs = await meta_agent._execute_parallel_tools(
        [_call("t1"), _call("t2")], {}, None)
    assert [r["output"] for r in recs] == ["o1", "o2"]


async def test_meta_parallel_enabled_paths(meta_agent, monkeypatch):
    monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
    monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
    gov = ama.AgentGovernanceService.return_value
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 1})
    meta_agent.mcp.call_tool = AsyncMock(side_effect=["ok1", RuntimeError("boom")])
    meta_agent.mcp.search_tools = AsyncMock(return_value=[
        {"name": "found_tool", "description": "d", "parameters": {}}])
    recs = await meta_agent._execute_parallel_tools(
        [_call("t1"), _call("t2"), _call("mcp_tool_search", query="q")], {}, None)
    assert recs[0]["output"] == "ok1"
    # t2 raised inside governance-wrapped call -> generic tool-error string
    assert "Tool error" in recs[1]["output"]
    assert "found_tool" in recs[2]["output"]
    # search failure tolerated
    meta_agent.mcp.search_tools = AsyncMock(side_effect=RuntimeError("s"))
    recs2 = await meta_agent._execute_parallel_tools([_call("mcp_tool_search")], {}, None)
    assert "Tool search failed" in recs2[0]["output"]


async def test_meta_parallel_blocked_and_rejected(meta_agent, monkeypatch):
    monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
    monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
    gov = ama.AgentGovernanceService.return_value
    # blocked batch
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": False, "requires_human_approval": False, "action_complexity": 1})
    recs = await meta_agent._execute_parallel_tools([_call("t1")], {}, None)
    assert recs[0]["verified_kind"] == "blocked"
    # requires approval -> rejected batch
    gov.can_perform_action_async = AsyncMock(return_value={
        "allowed": True, "requires_human_approval": False, "action_complexity": 2,
        "reason": "confirm"})
    gov.request_approval = MagicMock(return_value="aid")
    meta_agent._wait_for_all_approvals = AsyncMock(return_value=False)
    recs2 = await meta_agent._execute_parallel_tools([_call("t1")], {}, None)
    assert recs2[0]["verified_kind"] == "rejected"
    # approved batch executes pre-approved
    meta_agent._wait_for_all_approvals = AsyncMock(return_value=True)
    meta_agent.mcp.call_tool = AsyncMock(return_value='{"success": true, "verified": true}')
    recs3 = await meta_agent._execute_parallel_tools([_call("t1")], {}, AsyncMock())
    assert recs3[0]["verified_kind"] in ("verified", "unverified")


# ============================================================================
# META — persistence / recording / communication style
# ============================================================================

def test_meta_persist_reasoning_step(meta_agent, monkeypatch):
    sid = meta_agent._persist_reasoning_step(
        execution_id="e", step_number=1, step_type="action", thought="t",
        action_dict={"tool": "x"}, observation="o", confidence=0.9,
        verified_kind="verified", verification_evidence="ev", duration_ms=1.0,
        request="r", final_answer=None, context={"session_id": "s"})
    assert sid is not None
    # DB failure -> ""
    db = ama.SessionLocal.return_value.__enter__.return_value
    db.add = MagicMock(side_effect=RuntimeError("x"))
    sid2 = meta_agent._persist_reasoning_step(
        "e", 1, "action", "t", None, "o", 0.9, "u", None, 1.0, "r", None, None)
    assert sid2 == ""


async def test_meta_record_execution(meta_agent):
    meta_agent.world_model.record_experience = AsyncMock(return_value=True)
    gov = ama.AgentGovernanceService.return_value
    gov.record_outcome = AsyncMock()
    await meta_agent._record_execution("req", {
        "status": "success", "final_output": "ok", "actions_executed": [{}]},
        ama.AgentTriggerMode.MANUAL)
    meta_agent.world_model.record_experience.assert_awaited_once()
    gov.record_outcome.assert_awaited_once()
    # governance failure tolerated
    gov.record_outcome = AsyncMock(side_effect=RuntimeError("x"))
    await meta_agent._record_execution("req", {"status": "failed", "final_output": None},  # noqa
                                       ama.AgentTriggerMode.SCHEDULED)


def test_meta_communication_instruction(meta_agent):
    # no user
    assert meta_agent._get_communication_instruction({}) == ""
    # user with style
    db = ama.SessionLocal.return_value
    user = SimpleNamespace(metadata_json={
        "communication_style": {"enable_personalization": True,
                                "style_guide": "be brief"}})
    db.query.return_value.filter.return_value.first.return_value = user
    out = meta_agent._get_communication_instruction({"user_id": "u1"})
    assert "be brief" in out
    # user without style
    user2 = SimpleNamespace(metadata_json=None)
    db.query.return_value.filter.return_value.first.return_value = user2
    assert meta_agent._get_communication_instruction({"user_id": "u1"}) == ""
    # db error
    ama.SessionLocal = MagicMock(side_effect=RuntimeError("x"))
    assert meta_agent._get_communication_instruction({"user_id": "u1"}) == ""


# ============================================================================
# META — routing with governance
# ============================================================================

async def test_meta_route_chat_bypasses_governance(meta_agent):
    meta_agent.llm.generate_response = AsyncMock(return_value="hi")
    intent = SimpleNamespace(category=ama.IntentCategory.CHAT)
    res = await meta_agent.route_with_governance("hello", intent, "u1")
    assert res["governance_checked"] is False
    assert res["response"] == "hi"


async def test_meta_route_workflow_allowed(meta_agent):
    gov = ama.AgentGovernanceService.return_value
    gov.canPerformAction = AsyncMock(return_value=SimpleNamespace(allowed=True))
    queen = MagicMock()
    queen.generate_blueprint = AsyncMock(return_value={
        "blueprint_id": "b1", "architecture_name": "A", "nodes": [{}]})
    meta_agent.queen = queen
    intent = SimpleNamespace(category=ama.IntentCategory.WORKFLOW)
    res = await meta_agent.route_with_governance("build workflow", intent, "u1")
    assert res["governance_allowed"] is True
    assert res["blueprint_id"] == "b1"


async def test_meta_route_task_allowed(meta_agent, monkeypatch):
    gov = ama.AgentGovernanceService.return_value
    gov.canPerformAction = AsyncMock(return_value=SimpleNamespace(allowed=True))
    admiral = MagicMock()
    admiral.recruit_and_execute = AsyncMock(return_value={
        "chain_id": "c1", "specialists_count": 3})
    monkeypatch.setattr("core.fleet_admiral.FleetAdmiral", MagicMock(return_value=admiral))
    intent = SimpleNamespace(category=ama.IntentCategory.TASK)
    res = await meta_agent.route_with_governance("do task", intent, "u1")
    assert res["route"] == "TASK" and res["specialists_count"] == 3


async def test_meta_route_denied_proposes_chat(meta_agent):
    gov = ama.AgentGovernanceService.return_value
    gov.canPerformAction = AsyncMock(return_value=SimpleNamespace(
        allowed=False, reason="maturity too low"))
    meta_agent.llm.generate_response = AsyncMock(return_value="try chat instead")
    intent = SimpleNamespace(category=ama.IntentCategory.TASK)
    res = await meta_agent.route_with_governance("do task", intent, "u1")
    assert res["governance_allowed"] is False
    assert res["auto_takeover"] is True
    assert res["proposal"] == "try chat instead"


# ============================================================================
# META — trigger handlers / singleton
# ============================================================================

async def test_meta_handle_data_event_queued(monkeypatch):
    tq = MagicMock()
    tq.enabled = True
    tq.enqueue_job = MagicMock(return_value="task-1")
    monkeypatch.setattr("core.task_queue.get_task_queue", lambda: tq)
    monkeypatch.setattr("core.agent_worker_wrapper.execute_agent_background",
                        lambda: None)
    res = await handle_data_event_trigger("invoice.created", {"id": 1})
    assert res["status"] == "queued" and res["task_id"] == "task-1"
    # queue dispatch fails -> inline fallback
    monkeypatch.setattr("core.task_queue.get_task_queue",
                        MagicMock(side_effect=RuntimeError("no redis")))
    fake_agent = MagicMock()
    fake_agent.execute = AsyncMock(return_value={"status": "success"})
    monkeypatch.setattr(ama, "AtomMetaAgent", MagicMock(return_value=fake_agent))
    res2 = await handle_data_event_trigger("evt", {})
    assert res2["status"] == "success"
    # disabled queue -> inline
    tq2 = MagicMock()
    tq2.enabled = False
    monkeypatch.setattr("core.task_queue.get_task_queue", lambda: tq2)
    res3 = await handle_data_event_trigger("evt", {})
    assert res3["status"] == "success"


async def test_meta_handle_manual_trigger(monkeypatch):
    fake_agent = MagicMock()
    fake_agent.execute = AsyncMock(return_value={"status": "success"})
    monkeypatch.setattr(ama, "AtomMetaAgent", MagicMock(return_value=fake_agent))
    tracker = MagicMock()
    monkeypatch.setattr("core.reasoning_chain.get_reasoning_tracker",
                        lambda: tracker)
    ws = MagicMock()
    ws.broadcast = AsyncMock()
    monkeypatch.setattr("core.websockets.manager", ws)
    user = SimpleNamespace(id="u1", email="e@x")
    res = await handle_manual_trigger("do things", user, additional_context={"k": 1})
    assert res["status"] == "success"
    # streaming callback exercised (execute invoked with callback; call it)
    cb = fake_agent.execute.call_args.kwargs["step_callback"]
    await cb({"execution_id": "e", "step_type": "action", "thought": "t",
              "action": {"tool": "x"}, "output": "o", "confidence": 0.9,
              "step": 1, "duration_ms": 5})
    assert ws.broadcast.called


def test_meta_get_atom_agent(monkeypatch):
    ama._atom_instance = None
    with patch.object(AtomMetaAgent, "__init__", lambda self, *a, **k: None):
        a1 = ama.get_atom_agent("default")
        a1.workspace_id = "default"  # init was stubbed
        a2 = ama.get_atom_agent("default")
        assert a1 is a2
    ama._atom_instance = None
