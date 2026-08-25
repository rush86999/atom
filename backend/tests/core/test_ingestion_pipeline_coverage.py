"""
Coverage + bug-hunt tests for core/ingestion_pipeline.py.

The existing tests/test_covpush_ingestion_pipeline.py already covers
sync_and_ingest, process_webhook_payload, process_webhook_payload_tiered,
file/attachment ingestion and a few helpers (~53% coverage).

This file focuses on the LARGE uncovered area:
  - all _transform_<integration>_payload webhook transformers (~40 of them)
  - _transform_webhook_payload central standardizer (id/content/sender/metadata)
  - _extract_structured_entities edge cases
  - _is_core_entity_type
  - _calculate_acu_consumed
  - _record_to_text passthrough
  - _prepare_record_text_async kill-switch / non-file fallback
  - _fetch_outlook_resource_direct / _fetch_gmail_resource_direct (no-connection)

Plus TDD bug-hunts for real defects found by close reading.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.ingestion_pipeline as ip
from core.ingestion_pipeline import IngestionPipelineService


# ---------------------------------------------------------------------------
# Fixtures (mirror the pattern in tests/test_covpush_ingestion_pipeline.py)
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model

    def filter(self, *a, **k):
        return self

    def filter_by(self, **k):
        return self

    def order_by(self, *a):
        return self

    def first(self):
        return None


class FakeSession:
    def __init__(self):
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

    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda *a, **k: fake_lancedb)
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda *a, **k: fake_graphrag)
    monkeypatch.setattr("core.llm_service.get_llm_service", lambda *a, **k: fake_llm)
    monkeypatch.setattr(ip, "LanceDBHandler", lambda *a, **k: fake_lancedb)
    monkeypatch.setattr("core.lancedb_handler.LanceDBHandler", lambda *a, **k: fake_lancedb)
    monkeypatch.setattr(ip, "GraphRAGEngine", lambda *a, **k: fake_graphrag)
    monkeypatch.setattr(ip, "MultiEntityLLMExtractor", lambda *a, **k: fake_extractor)
    monkeypatch.setattr(ip, "SchemaDiscoveryService", lambda *a, **k: fake_schema)
    monkeypatch.setattr(ip, "EntityLinkingService", lambda *a, **k: fake_linker)
    monkeypatch.setattr("core.meta_agent_orchestrator.MetaAgentOrchestrator", lambda *a, **k: fake_meta)
    monkeypatch.setattr(ip, "UsageTrackingService", lambda *a, **k: fake_usage)

    session = FakeSession()
    monkeypatch.setattr(ip, "SessionLocal", lambda: session)

    svc = IngestionPipelineService(tenant_id="t1", workspace_id="ws1")
    svc.integration_registry = fake_registry

    fake_usage.track_acu_usage = AsyncMock(return_value=MagicMock(id="usage-1"))
    fake_usage.calculate_acu_consumed = MagicMock(return_value=1.5)
    fake_usage.check_quota_before_job = AsyncMock(
        return_value={"allowed": True, "remaining_quota": 10}
    )
    fake_graphrag.ingest_structured_data = MagicMock()

    return {
        "svc": svc,
        "session": session,
        "lancedb": fake_lancedb,
        "graphrag": fake_graphrag,
        "usage": fake_usage,
        "extractor": fake_extractor,
        "schema": fake_schema,
        "linker": fake_linker,
        "meta": fake_meta,
        "llm": fake_llm,
        "registry": fake_registry,
    }


# ===========================================================================
# _extract_structured_entities (helper) - edge cases
# ===========================================================================


class TestExtractStructuredEntities:
    def test_basic_entity_and_relationship(self, pipeline):
        svc = pipeline["svc"]
        record = {
            "id": "r1",
            "type": "contact",
            "name": "Alice",
            "email": "a@b.com",
            "company": "Acme",
            "stage": "lead",
            "status": "open",
            "amount": "5000",
        }
        entity, rel, _anchor = svc._extract_structured_entities(record, "salesforce", "Alice the contact")
        assert entity["name"] == "Alice"
        assert entity["type"] == "contact"
        assert entity["properties"]["source"] == "salesforce"
        assert entity["properties"]["record_id"] == "r1"
        assert entity["properties"]["email"] == "a@b.com"
        assert entity["properties"]["company"] == "Acme"
        assert entity["properties"]["amount"] == "5000"
        assert rel["from"] == "Alice"
        assert rel["to"] == "salesforce"
        assert rel["type"] == "synced_from"

    def test_name_falls_back_through_title_subject(self, pipeline):
        svc = pipeline["svc"]
        e, _, _anchor = svc._extract_structured_entities({"id": 1, "type": "x", "title": "T"}, "i", "txt")
        assert e["name"] == "T"
        e, _, _anchor = svc._extract_structured_entities({"id": 1, "type": "x", "subject": "S"}, "i", "txt")
        assert e["name"] == "S"
        e, _, _anchor = svc._extract_structured_entities({"id": 1, "type": "x"}, "i", "txt")
        assert e["name"] == "x_1"

    def test_id_converted_to_string(self, pipeline):
        svc = pipeline["svc"]
        uid = uuid.uuid4()
        e, _, _anchor = svc._extract_structured_entities({"id": uid, "type": "t"}, "i", "txt")
        assert e["properties"]["record_id"] == str(uid)

    def test_description_truncated_to_500(self, pipeline):
        svc = pipeline["svc"]
        long = "x" * 2000
        e, _, _anchor = svc._extract_structured_entities({"id": 1, "type": "t"}, "i", long)
        assert len(e["description"]) == 500

    def test_promotes_subject_content_summary_description_fields(self, pipeline):
        svc = pipeline["svc"]
        e, _, _anchor = svc._extract_structured_entities(
            {"id": 1, "type": "t", "subject": "S", "content": "C", "summary": "Su", "description": "D"},
            "i", "txt",
        )
        assert e["properties"]["subject"] == "S"
        assert e["properties"]["content"] == "C"
        assert e["properties"]["summary"] == "Su"
        assert e["properties"]["description"] == "D"


# ===========================================================================
# _hash_text / _is_core_entity_type / _calculate_acu_consumed
# ===========================================================================


class TestHashText:
    def test_deterministic(self):
        assert IngestionPipelineService._hash_text("abc") == IngestionPipelineService._hash_text("abc")

    def test_matches_sha256(self):
        assert IngestionPipelineService._hash_text("abc") == hashlib.sha256(b"abc").hexdigest()

    def test_different_inputs_differ(self):
        assert IngestionPipelineService._hash_text("a") != IngestionPipelineService._hash_text("b")


class TestIsCoreEntityType:
    def test_known_core_type(self, pipeline):
        svc = pipeline["svc"]
        # CORE_ENTITY_SCHEMAS keys are the canonical names; check a common one.
        from core.openie_schema_discovery import CORE_ENTITY_SCHEMAS
        if CORE_ENTITY_SCHEMAS:
            some_key = next(iter(CORE_ENTITY_SCHEMAS.keys()))
            assert svc._is_core_entity_type(some_key) is True

    def test_case_insensitive(self, pipeline):
        svc = pipeline["svc"]
        from core.openie_schema_discovery import CORE_ENTITY_SCHEMAS
        if CORE_ENTITY_SCHEMAS:
            some_key = next(iter(CORE_ENTITY_SCHEMAS.keys()))
            assert svc._is_core_entity_type(some_key.upper()) is True
            assert svc._is_core_entity_type(some_key.lower()) is True

    def test_unknown_type_is_false(self, pipeline):
        svc = pipeline["svc"]
        assert svc._is_core_entity_type("definitely_not_a_core_type_xyz_123") is False


class TestCalculateAcuConsumed:
    def test_delegates_to_usage_tracker(self, pipeline):
        svc = pipeline["svc"]
        pipeline["usage"].calculate_acu_consumed.return_value = 2.5
        result = svc._calculate_acu_consumed(llm_calls=3, total_tokens=1000, processing_duration_ms=500)
        assert result == 2.5
        pipeline["usage"].calculate_acu_consumed.assert_called_once()


# ===========================================================================
# _prepare_record_text_async — kill switch & non-file fallback
# ===========================================================================


class TestPrepareRecordTextAsync:
    @pytest.mark.asyncio
    async def test_global_kill_switch_falls_back(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        monkeypatch.setenv("ENABLE_BINARY_INGESTION", "false")
        record = {"id": "r1", "type": "file", "name": "f.txt", "extension": "txt"}
        out = await svc._prepare_record_text_async(record, "salesforce")
        # Should fall back to _record_to_text (metadata-based) rather than parsing.
        assert "f.txt" in out

    @pytest.mark.asyncio
    async def test_non_file_record_uses_record_to_text(self, pipeline):
        svc = pipeline["svc"]
        record = {"id": "r1", "type": "slack_message", "text": "hello world here", "user": "U1"}
        out = await svc._prepare_record_text_async(record, "slack")
        assert "hello world here" in out

    @pytest.mark.asyncio
    async def test_per_provider_legacy_flag_disabled(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        monkeypatch.setenv("ENABLE_SALESFORCE_FILE_PARSING", "false")
        record = {"id": "r1", "type": "file", "name": "doc.pdf", "extension": "pdf"}
        out = await svc._prepare_record_text_async(record, "salesforce")
        assert "doc.pdf" in out

    @pytest.mark.asyncio
    async def test_unsupported_extension_falls_back(self, pipeline):
        svc = pipeline["svc"]
        record = {"id": "r1", "type": "file", "name": "weird.xyz", "extension": "xyz"}
        out = await svc._prepare_record_text_async(record, "salesforce")
        # Unsupported extension -> metadata fallback
        assert "weird.xyz" in out

    @pytest.mark.asyncio
    async def test_zoho_workdrive_flag_disabled(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        monkeypatch.setenv("ENABLE_WORKDRIVE_FILE_PARSING", "false")
        record = {"id": "r1", "type": "file", "name": "report.pdf", "extension": "pdf"}
        out = await svc._prepare_record_text_async(record, "zoho_workdrive")
        assert "report.pdf" in out


# ===========================================================================
# _fetch_outlook_resource_direct / _fetch_gmail_resource_direct
# ===========================================================================


class TestFetchResourceDirect:
    @pytest.mark.asyncio
    async def test_outlook_no_connection_id_returns_none(self, pipeline):
        svc = pipeline["svc"]
        assert await svc._fetch_outlook_resource_direct(None, "path") is None

    @pytest.mark.asyncio
    async def test_gmail_no_connection_id_returns_none(self, pipeline):
        svc = pipeline["svc"]
        assert await svc._fetch_gmail_resource_direct(None, "path") is None


# ===========================================================================
# Webhook transformers — exhaustive coverage of every _transform_* method.
# Each test asserts the record shape is produced for a representative payload.
# ===========================================================================


async def _run(svc, method_name, payload):
    return await getattr(svc, method_name)(payload)


class TestTransformers:
    @pytest.mark.asyncio
    async def test_slack_message(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_slack_payload", {
            "type": "event_callback",
            "team_id": "T1",
            "event": {"type": "message", "client_msg_id": "m1", "text": "hi", "channel": "C1", "user": "U1", "ts": "1"},
        })
        assert out[0]["type"] == "slack_message"
        assert out[0]["id"] == "m1"
        assert out[0]["channel"] == "C1"

    @pytest.mark.asyncio
    async def test_slack_no_message_event_returns_empty(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_slack_payload", {"type": "other", "event": {}})
        assert out == []

    @pytest.mark.asyncio
    async def test_hubspot_single_and_list(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_hubspot_payload", {
            "subscriptionType": "contact.creation", "objectId": "1", "properties": {"a": "b"},
        })
        assert out[0]["object_type"] == "contact.creation"
        # list form: HubSpot may send an array of events
        out = await _run(pipeline["svc"], "_transform_hubspot_payload",
                         [{"subscriptionType": "x", "objectId": "9"}])
        assert len(out) == 1

    @pytest.mark.asyncio
    async def test_salesforce_multiple_record_ids(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_salesforce_payload", {
            "eventType": "create", "objectType": "Account",
            "recordIds": ["a", "b"], "changeEventHeader": {"changeTypes": ["x"]}, "payload": {"p": 1},
        })
        assert len(out) == 2
        assert out[0]["object_type"] == "Account"
        assert out[1]["id"] == "b"

    @pytest.mark.asyncio
    async def test_gmail_fallback_no_connection(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_gmail_payload", {"historyId": "123", "emailAddress": "x@y.com"})
        # No source_connection_id -> fallback record
        assert out[0]["type"] == "gmail_message"
        assert out[0]["id"] == "123"

    @pytest.mark.asyncio
    async def test_notion(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_notion_payload", {"id": "p1", "title": "T", "activity_type": "edited"})
        assert out[0]["type"] == "notion_page"
        assert out[0]["title"] == "T"

    @pytest.mark.asyncio
    async def test_zoho_crm(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_crm_payload", {"module": {"api_name": "Leads"}, "key_id": "k1"})
        assert out[0]["type"] == "zoho_crm_leads"

    @pytest.mark.asyncio
    async def test_zoho_books(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_books_payload", {"module": "Invoices", "IDs": {"entity_id": "e1"}})
        assert out[0]["type"] == "zoho_books_invoices"

    @pytest.mark.asyncio
    async def test_zoho_projects(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_projects_payload", {"id": "z1", "module": "Tasks", "project_id": "p1"})
        assert out[0]["type"] == "zoho_projects_tasks"
        assert out[0]["project_id"] == "p1"

    @pytest.mark.asyncio
    async def test_zoho_desk(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_desk_payload", {"ticketId": "t1"})
        assert out[0]["type"] == "zoho_desk_ticket"

    @pytest.mark.asyncio
    async def test_zoho_recruit(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_recruit_payload", {"module": "Candidates", "entityId": "e1"})
        assert out[0]["type"] == "zoho_recruit_candidates"

    @pytest.mark.asyncio
    async def test_zoho_campaigns(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_campaigns_payload", {"campaign_id": "c1"})
        assert out[0]["type"] == "zoho_campaigns_campaign"

    @pytest.mark.asyncio
    async def test_zoho_forms(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_forms_payload", {"submission_id": "s1"})
        assert out[0]["type"] == "zoho_forms_submission"

    @pytest.mark.asyncio
    async def test_zoho_showtime(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_showtime_payload", {"session_id": "ss1"})
        assert out[0]["type"] == "zoho_showtime_session"

    @pytest.mark.asyncio
    async def test_zoho_meeting(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_meeting_payload", {"meeting_id": "m1"})
        assert out[0]["type"] == "zoho_meeting_session"

    @pytest.mark.asyncio
    async def test_zoho_assist(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoho_assist_payload", {"session_id": "a1"})
        assert out[0]["type"] == "zoho_assist_session"

    @pytest.mark.asyncio
    async def test_jira(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_jira_payload", {"issue": {"id": "i1", "key": "AT-1", "fields": {"summary": "S", "status": {"name": "Open"}, "assignee": {"displayName": "Bob"}}}, "webhookEvent": "jira:issue_created"})
        assert out[0]["key"] == "AT-1"
        assert out[0]["assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_asana(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_asana_payload", {"gid": "g1", "name": "task", "completed": True, "action": "changed"})
        assert out[0]["id"] == "g1"
        assert out[0]["completed"] is True

    @pytest.mark.asyncio
    async def test_trello(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_trello_payload", {"action": {"type": "updateCard", "data": {"card": {"id": "c1", "name": "N"}, "listAfter": {"id": "L1"}}}})
        assert out[0]["id"] == "c1"
        assert out[0]["list_id"] == "L1"

    @pytest.mark.asyncio
    async def test_monday(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_monday_payload", {"event": {"type": "x"}, "payload": {"item_id": "i1", "item_name": "n", "board_id": "b1"}})
        assert out[0]["id"] == "i1"

    @pytest.mark.asyncio
    async def test_clickup(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_clickup_payload", {"task": {"id": "t1", "name": "n", "status": "open"}, "event": "e"})
        assert out[0]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_linear(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_linear_payload", {"data": {"id": "l1", "title": "T", "state": {"name": "Open"}}, "action": "create"})
        assert out[0]["state"] == "Open"

    @pytest.mark.asyncio
    async def test_pipedrive(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_pipedrive_payload", {"current": {"id": "p1", "title": "T"}, "object": "deal", "event": "updated"})
        assert out[0]["type"] == "pipedrive_deal"

    @pytest.mark.asyncio
    async def test_zendesk_sell(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zendesk_sell_payload", {"target_type": "lead", "target_id": "z1", "trigger": "x"})
        assert out[0]["type"] == "zendesk_sell_lead"

    @pytest.mark.asyncio
    async def test_insightly(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_insightly_payload", {"object_name": "Contact", "record_id": "r1"})
        assert out[0]["type"] == "insightly_contact"

    @pytest.mark.asyncio
    async def test_freshsales(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_freshsales_payload", {"entity_type": "Deal", "payload": {"id": "f1"}, "action": "a"})
        assert out[0]["type"] == "freshsales_deal"

    @pytest.mark.asyncio
    async def test_salesloft(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_salesloft_payload", {"data": {"id": "s1", "name": "n"}, "event": {"action": "x"}})
        assert out[0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_mailchimp(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_mailchimp_payload", {"type": "subscribe", "data": {"id": "m1", "email": "a@b.com"}})
        assert out[0]["type"] == "mailchimp_subscribe"

    @pytest.mark.asyncio
    async def test_activecampaign(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_activecampaign_payload", {"contact": {"id": "c1", "email": "a@b.com"}, "type": "x"})
        assert out[0]["id"] == "c1"

    @pytest.mark.asyncio
    async def test_sendgrid_list(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_sendgrid_payload", [{"sg_message_id": "s1", "email": "a@b.com", "event": "delivered"}])
        assert out[0]["event_type"] == "delivered"

    @pytest.mark.asyncio
    async def test_convertkit(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_convertkit_payload", {"subscriber": {"id": "k1", "email_address": "a@b.com"}, "event": {"name": "n"}})
        assert out[0]["id"] == "k1"

    @pytest.mark.asyncio
    async def test_discord(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_discord_payload", {"id": "d1", "content": "hi", "author": {"username": "u"}, "channel_id": "c"})
        assert out[0]["author"] == "u"

    @pytest.mark.asyncio
    async def test_teams(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_teams_payload", {"id": "t1", "text": "hi", "from": {"application": {"displayName": "App"}}})
        assert out[0]["from"] == "App"

    @pytest.mark.asyncio
    async def test_telegram_text_message(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_telegram_payload", {"message": {"message_id": 1, "text": "hi", "from": {"id": 9, "username": "bob"}, "chat": {"id": 5, "title": "Grp"}}})
        assert out[0]["chat_id"] == "5"
        assert out[0]["from"] == "bob"

    @pytest.mark.asyncio
    async def test_telegram_channel_post_with_photo(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_telegram_payload", {"channel_post": {"message_id": 2, "caption": "cap", "from": {}, "chat": {}, "photo": [{"file_id": "f1"}, {"file_id": "f2"}]}})
        assert out[0]["type"] == "telegram_message"
        # largest photo is last entry
        assert out[0]["properties"]["media_id"] == "f2"

    @pytest.mark.asyncio
    async def test_telegram_empty_returns_empty(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_telegram_payload", {})
        assert out == []

    @pytest.mark.asyncio
    async def test_twilio_sms(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_twilio_payload", {"MessageSid": "SM1", "From": "+1", "To": "+2", "MessageStatus": "sent"})
        assert out[0]["type"] == "twilio_sms"
        assert out[0]["object_type"] == "message"

    @pytest.mark.asyncio
    async def test_twilio_call(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_twilio_payload", {"CallSid": "CA1", "From": "+1", "To": "+2", "CallStatus": "ringing"})
        assert out[0]["type"] == "twilio_call"
        assert out[0]["object_type"] == "call"

    @pytest.mark.asyncio
    async def test_intercom(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_intercom_payload", {"data": {"id": "i1", "conversation_message": {"subject": "S"}}, "topic": "t"})
        assert out[0]["subject"] == "S"

    @pytest.mark.asyncio
    async def test_github_pr(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_github_payload", {"action": "opened", "pull_request": {"number": 7, "title": "T", "state": "open"}})
        assert out[0]["type"] == "github_pull_request"
        assert out[0]["id"] == "7"

    @pytest.mark.asyncio
    async def test_github_issue(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_github_payload", {"action": "closed", "issue": {"number": 3, "title": "T", "state": "closed"}})
        assert out[0]["type"] == "github_issue"

    @pytest.mark.asyncio
    async def test_github_push(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_github_payload", {"action": "x", "after": "abcdef1234567", "ref": "refs/heads/main"})
        assert out[0]["type"] == "github_push"
        assert out[0]["id"] == "abcdef1"  # first 7 chars

    @pytest.mark.asyncio
    async def test_gitlab_mr(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_gitlab_payload", {"object_kind": "merge_request", "object_attributes": {"iid": 5, "title": "T", "state": "open", "action": "open"}})
        assert out[0]["type"] == "gitlab_merge_request"

    @pytest.mark.asyncio
    async def test_gitlab_issue(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_gitlab_payload", {"object_kind": "issue", "object_attributes": {"iid": 9, "title": "T", "state": "open", "action": "open"}})
        assert out[0]["type"] == "gitlab_issue"

    @pytest.mark.asyncio
    async def test_gitlab_push(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_gitlab_payload", {"object_kind": "push", "after": "abcdef1234567", "ref": "refs/heads/main"})
        assert out[0]["type"] == "gitlab_push"

    @pytest.mark.asyncio
    async def test_bitbucket_pr(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_bitbucket_payload", {"pullrequest": {"id": 4, "title": "T", "state": "open"}, "action": "x"})
        assert out[0]["type"] == "bitbucket_pull_request"

    @pytest.mark.asyncio
    async def test_bitbucket_push(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_bitbucket_payload", {"changes": [{"toHash": "abcdef1234567", "ref": {"displayId": "main"}}]})
        assert out[0]["type"] == "bitbucket_push"
        assert out[0]["id"] == "abcdef1"

    @pytest.mark.asyncio
    async def test_google_drive(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_google_drive_payload", {"file_id": "g1", "name": "f", "action": "edit"})
        assert out[0]["id"] == "g1"

    @pytest.mark.asyncio
    async def test_dropbox(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_dropbox_payload", {"file_id": "d1", "name": "f"})
        assert out[0]["type"] == "dropbox_file"

    @pytest.mark.asyncio
    async def test_box(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_box_payload", {"file_id": "b1", "file_name": "f"})
        assert out[0]["type"] == "box_file"

    @pytest.mark.asyncio
    async def test_onedrive(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_onedrive_payload", {"file_id": "o1", "file_name": "f"})
        assert out[0]["type"] == "onedrive_file"

    @pytest.mark.asyncio
    async def test_shopify(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_shopify_payload", {"topic": "orders/create", "id": "s1", "email": "a@b.com", "total_price": "9.99"})
        assert out[0]["type"] == "shopify_orders_create"

    @pytest.mark.asyncio
    async def test_woocommerce(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_woocommerce_payload", {"id": "w1", "total": "10", "status": "paid"})
        assert out[0]["type"] == "woocommerce_order"

    @pytest.mark.asyncio
    async def test_bigcommerce(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_bigcommerce_payload", {"data": {"id": "b1", "total_tax_inc": "5"}, "scope": "store/order/created"})
        assert out[0]["id"] == "b1"

    @pytest.mark.asyncio
    async def test_magento(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_magento_payload", {"entity_id": "m1", "grand_total": "20", "event_name": "x"})
        assert out[0]["type"] == "magento_order"

    @pytest.mark.asyncio
    async def test_stripe(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_stripe_payload", {"data": {"object": {"object": "charge", "id": "ch1", "amount": 500, "currency": "usd"}}, "type": "charge.succeeded"})
        assert out[0]["type"] == "stripe_charge"

    @pytest.mark.asyncio
    async def test_airtable(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_airtable_payload", {"record_id": "r1", "base_id": "b", "table_id": "t"})
        assert out[0]["type"] == "airtable_record"

    @pytest.mark.asyncio
    async def test_webex(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_webex_payload", {"data": {"id": "w1", "text": "hi", "personId": "p"}, "name": "msg"})
        assert out[0]["text"] == "hi"

    @pytest.mark.asyncio
    async def test_zoom(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_zoom_payload", {"id": "z1", "topic": "T", "event": "start"})
        assert out[0]["topic"] == "T"

    @pytest.mark.asyncio
    async def test_freshdesk(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_freshdesk_payload", {"ticket_id": "f1", "subject": "S", "status": "open", "trigger": "x"})
        assert out[0]["type"] == "freshdesk_ticket"

    @pytest.mark.asyncio
    async def test_figma(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_figma_payload", {"file_key": "k1", "file_name": "f"})
        assert out[0]["type"] == "figma_file"

    @pytest.mark.asyncio
    async def test_whatsapp_message(self, pipeline):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"id": "w1", "text": {"body": "hi"}, "from": "+1", "timestamp": "1"}
                                ],
                                "metadata": {"phone_number_id": "p"},
                            }
                        }
                    ]
                }
            ]
        }
        out = await _run(pipeline["svc"], "_transform_whatsapp_payload", payload)
        assert out[0]["text"] == "hi"
        assert out[0]["sender_id"] == "+1"

    @pytest.mark.asyncio
    async def test_whatsapp_empty(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_whatsapp_payload", {})
        assert out == []

    @pytest.mark.asyncio
    async def test_whatsapp_malformed_returns_empty(self, pipeline):
        # Missing nested keys should not raise.
        out = await _run(pipeline["svc"], "_transform_whatsapp_payload", {"entry": "notalist"})
        assert out == []

    @pytest.mark.asyncio
    async def test_outlook_prenormalized_email(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_outlook_payload", {"id": "o1", "subject": "S", "from": "a@b.com", "to": "c@d.com", "content": "body"})
        assert out[0]["type"] == "email"
        assert out[0]["subject"] == "S"

    @pytest.mark.asyncio
    async def test_outlook_prenormalized_fallback_id_from_metadata(self, pipeline):
        out = await _run(pipeline["svc"], "_transform_outlook_payload", {"subject": "S", "metadata": {"conversation_id": "conv1"}})
        assert out[0]["id"] == "conv1"


# ===========================================================================
# _transform_webhook_payload central standardizer
# ===========================================================================


class TestCentralStandardizer:
    @pytest.mark.asyncio
    async def test_unknown_integration_returns_empty(self, pipeline):
        out = await pipeline["svc"]._transform_webhook_payload("not_a_real_integration", {"id": "1"})
        assert out == []

    @pytest.mark.asyncio
    async def test_guarantees_string_id(self, pipeline):
        svc = pipeline["svc"]
        # slack transformer yields a record with int-ish id; standardizer str()s it.
        out = await svc._transform_webhook_payload("slack", {
            "type": "event_callback", "team_id": "T",
            "event": {"type": "message", "ts": 12345, "text": "hello world here", "channel": "c", "user": "u"},
        })
        assert out[0]["id"] == "12345"

    @pytest.mark.asyncio
    async def test_sender_extraction_priority(self, pipeline):
        svc = pipeline["svc"]
        out = await svc._transform_webhook_payload("slack", {
            "type": "event_callback", "team_id": "T",
            "event": {"type": "message", "ts": "1", "text": "x" * 20, "channel": "c", "user": "U1"},
        })
        assert out[0]["sender_id"] == "U1"

    @pytest.mark.asyncio
    async def test_subject_extraction(self, pipeline):
        svc = pipeline["svc"]
        out = await svc._transform_webhook_payload("notion", {"id": "n1", "title": "My Page", "activity_type": "x"})
        assert out[0]["subject"] == "My Page"

    @pytest.mark.asyncio
    async def test_content_dict_extraction(self, pipeline):
        svc = pipeline["svc"]
        # Construct a record whose content is a dict (Outlook body style).
        # We patch the slack transformer output by using outlook (email type).
        out = await svc._transform_webhook_payload("outlook", {
            "id": "o1", "subject": "S", "content": {"content": "deep body text", "contentType": "html"},
        })
        assert out[0]["content"] == "deep body text"

    @pytest.mark.asyncio
    async def test_timestamp_extraction(self, pipeline):
        svc = pipeline["svc"]
        out = await svc._transform_webhook_payload("slack", {
            "type": "event_callback", "team_id": "T",
            "event": {"type": "message", "ts": "1700000000.000001", "text": "x" * 20, "channel": "c", "user": "u"},
        })
        assert out[0]["timestamp"] == "1700000000.000001"

    @pytest.mark.asyncio
    async def test_metadata_preserves_flat_fields(self, pipeline):
        svc = pipeline["svc"]
        # Notion transformer keeps object_type on the record; the standardizer
        # copies non-reserved flat keys into metadata too.
        out = await svc._transform_webhook_payload("notion", {"id": "n1", "title": "T", "activity_type": "x"})
        assert out[0]["metadata"].get("object_type") == "page"

    @pytest.mark.asyncio
    async def test_non_dict_record_skipped(self, pipeline):
        svc = pipeline["svc"]
        # Sendgrid returns records; we feed a list with a non-dict to the standardizer
        # via sendgrid (which iterates a list). Instead, patch to return [None].
        with patch.object(svc, "_transform_sendgrid_payload", AsyncMock(return_value=[None, {"id": "s1"}])):
            out = await svc._transform_webhook_payload("sendgrid", {})
        assert len(out) == 1
        assert out[0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_empty_id_becomes_empty_string(self, pipeline):
        svc = pipeline["svc"]
        out = await svc._transform_webhook_payload("notion", {"title": "T", "activity_type": "x"})
        assert out[0]["id"] == ""

    @pytest.mark.asyncio
    async def test_transformer_raising_returns_empty(self, pipeline):
        svc = pipeline["svc"]
        with patch.object(svc, "_transform_notion_payload", AsyncMock(side_effect=RuntimeError("boom"))):
            out = await svc._transform_webhook_payload("notion", {"id": "1"})
        assert out == []

    @pytest.mark.asyncio
    async def test_transformer_returns_empty_returns_empty(self, pipeline):
        svc = pipeline["svc"]
        with patch.object(svc, "_transform_notion_payload", AsyncMock(return_value=[])):
            out = await svc._transform_webhook_payload("notion", {"id": "1"})
        assert out == []


# ===========================================================================
# Job / credential helper branches (full field-set coverage)
# ===========================================================================


class TestJobAndCredentialHelpers:
    def test_update_ingestion_job_all_fields(self, pipeline):
        from datetime import datetime, timezone

        svc = pipeline["svc"]
        # FakeSession.query(...).first() returns None by default; patch to
        # return a MagicMock job so all the field setters execute + commit.
        job = MagicMock()
        pipeline["session"].__class__  # noqa: keep reference
        with patch.object(_FakeQuery, "first", return_value=job):
            ok = svc._update_ingestion_job(
                "job-1",
                "failed",
                started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                records_fetched=10,
                records_processed=8,
                entities_extracted=5,
                relationships_extracted=3,
                error_message="boom",
                error_details={"k": "v"},
            )
        assert ok is True
        assert job.status == "failed"
        assert job.records_fetched == 10
        assert job.records_processed == 8
        assert job.entities_extracted == 5
        assert job.relationships_extracted == 3
        assert job.error_message == "boom"
        assert job.error_details == {"k": "v"}
        assert pipeline["session"].committed >= 1

    def test_update_ingestion_job_when_model_missing(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        monkeypatch.setattr(ip, "INGESTION_JOB_EXISTS", False)
        assert svc._update_ingestion_job("job-1", "completed") is False

    def test_create_ingestion_job_when_model_missing(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        monkeypatch.setattr(ip, "INGESTION_JOB_EXISTS", False)
        job_id = svc._create_ingestion_job("slack", "manual")
        assert job_id.startswith("fallback-")

    def test_record_doc_ingestion_integrity_error_handled(self, pipeline, monkeypatch):
        """IntegrityError on commit is rolled back silently (no crash)."""
        from sqlalchemy.exc import IntegrityError

        svc = pipeline["svc"]
        session = pipeline["session"]
        # Force the DocumentIngestion query to return None (new doc) then commit
        # to raise IntegrityError.
        with patch.object(_FakeQuery, "first", return_value=None):
            original_commit = session.commit

            def raising_commit():
                raise IntegrityError("stmt", params={}, orig=Exception("dup"))

            session.commit = raising_commit
            try:
                svc._record_doc_ingestion("ws1", "doc1", "some text", "slack")
            finally:
                session.commit = original_commit
        # Should have rolled back, not raised.
        assert session.rolled_back >= 1

    def test_is_doc_already_ingested_false_and_true(self, pipeline):
        svc = pipeline["svc"]
        # No existing doc -> False
        with patch.object(_FakeQuery, "first", return_value=None):
            assert svc._is_doc_already_ingested("ws1", "d1", "txt") is False
        # Existing with matching hash -> True
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text("txt")
        with patch.object(_FakeQuery, "first", return_value=existing):
            assert svc._is_doc_already_ingested("ws1", "d1", "txt") is True

    def test_get_user_credentials_found(self, pipeline):
        svc = pipeline["svc"]
        conn = MagicMock()
        conn.id = "c1"
        conn.integration_id = "slack"
        conn.user_id = "u1"
        conn.expires_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with patch.object(_FakeQuery, "first", return_value=conn):
            creds = svc._get_user_credentials("slack", "u1")
        assert creds["connection_id"] == "c1"
        assert creds["integration_id"] == "slack"

    def test_get_user_credentials_not_found(self, pipeline):
        svc = pipeline["svc"]
        with patch.object(_FakeQuery, "first", return_value=None):
            assert svc._get_user_credentials("slack", "u1") is None


# ===========================================================================
# _transform_gmail_payload direct-fetch path (mocked network)
# ===========================================================================


class TestGmailDirectFetch:
    @pytest.mark.asyncio
    async def test_gmail_direct_fetch_with_connection(self, pipeline):
        svc = pipeline["svc"]
        history_payload = {
            "_source_connection_id": "conn-1",
            "historyId": "100",
            "history": [
                {"messagesAdded": [{"message": {"id": "m1"}}, {"message": {"id": "m2"}}]},
            ],
        }
        # First call -> history; subsequent calls -> message details.
        seq = [
            history_payload,
            {  # m1 detail
                "id": "m1", "threadId": "t1",
                "payload": {"headers": [{"name": "Subject", "value": "Hello"}, {"name": "From", "value": "a@b.com"}]},
                "snippet": "body text here", "internalDate": "1700000000000",
            },
            {  # m2 detail
                "id": "m2", "threadId": "t2",
                "payload": {"headers": []},
                "snippet": "second message body", "internalDate": None,
            },
        ]
        call = {"i": 0}

        async def fake_direct(conn_id, path):
            r = seq[call["i"]]
            call["i"] += 1
            return r

        with patch.object(svc, "_fetch_gmail_resource_direct", side_effect=fake_direct):
            out = await svc._transform_gmail_payload(history_payload)
        assert len(out) == 2
        assert out[0]["subject"] == "Hello"
        assert out[0]["from"] == "a@b.com"
        assert out[1]["subject"] == "No Subject"  # default when header missing

    @pytest.mark.asyncio
    async def test_gmail_direct_fetch_failure_falls_back(self, pipeline):
        svc = pipeline["svc"]
        payload = {"_source_connection_id": "conn-1", "historyId": "200"}

        async def boom(conn_id, path):
            raise RuntimeError("network down")

        with patch.object(svc, "_fetch_gmail_resource_direct", side_effect=boom):
            out = await svc._transform_gmail_payload(payload)
        # Falls back to a single notification record.
        assert len(out) == 1
        assert out[0]["type"] == "gmail_message"


class TestOutlookDirectTransformer:
    @pytest.mark.asyncio
    async def test_outlook_message_resource(self, pipeline):
        svc = pipeline["svc"]
        payload = {
            "_source_connection_id": "conn-1",
            "resource": "Users/x/Messages/m1",
            "resourceData": {"@odata.type": "#Microsoft.Graph.Message"},
        }
        full = {"id": "m1", "subject": "S", "bodyPreview": "preview text", "from": {"emailAddress": {"address": "a@b.com"}}, "receivedDateTime": "2024-01-01T00:00:00Z"}
        with patch.object(svc, "_fetch_outlook_resource_direct", AsyncMock(return_value=full)):
            out = await svc._transform_outlook_payload(payload)
        assert out[0]["sender_id"] == "a@b.com"
        assert out[0]["content"] == "preview text"

    @pytest.mark.asyncio
    async def test_outlook_event_resource(self, pipeline):
        svc = pipeline["svc"]
        payload = {
            "_source_connection_id": "conn-1",
            "resource": "Users/x/Events/e1",
            "resourceData": {"@odata.type": "#Microsoft.Graph.Event"},
        }
        full = {"id": "e1", "subject": "Meet", "body": {"content": "agenda"}, "start": "s", "end": "e", "location": "L"}
        with patch.object(svc, "_fetch_outlook_resource_direct", AsyncMock(return_value=full)):
            out = await svc._transform_outlook_payload(payload)
        assert out[0]["type"] == "calendar_event"
        assert out[0]["name"] == "Meet"

    @pytest.mark.asyncio
    async def test_outlook_generic_resource(self, pipeline):
        svc = pipeline["svc"]
        payload = {
            "_source_connection_id": "conn-1",
            "resource": "Users/x/driveItem/d1",
            "resourceData": {"@odata.type": "#Microsoft.Graph.DriveItem"},
        }
        full = {"id": "d1", "name": "file.docx"}
        with patch.object(svc, "_fetch_outlook_resource_direct", AsyncMock(return_value=full)):
            out = await svc._transform_outlook_payload(payload)
        assert out[0]["type"] == "outlook_resource"

    @pytest.mark.asyncio
    async def test_outlook_resource_fetch_returns_none(self, pipeline):
        svc = pipeline["svc"]
        payload = {
            "_source_connection_id": "conn-1",
            "resource": "Users/x/Messages/m1",
            "resourceData": {"@odata.type": "#Microsoft.Graph.Message"},
        }
        with patch.object(svc, "_fetch_outlook_resource_direct", AsyncMock(return_value=None)):
            out = await svc._transform_outlook_payload(payload)
        assert out == []

    @pytest.mark.asyncio
    async def test_outlook_resource_fetch_raises(self, pipeline):
        svc = pipeline["svc"]
        payload = {
            "_source_connection_id": "conn-1",
            "resource": "Users/x/Messages/m1",
            "resourceData": {"@odata.type": "#Microsoft.Graph.Message"},
        }
        with patch.object(svc, "_fetch_outlook_resource_direct", AsyncMock(side_effect=RuntimeError("boom"))):
            out = await svc._transform_outlook_payload(payload)
        assert out == []


# ===========================================================================
# _fetch_outlook_resource_direct / _fetch_gmail_resource_direct DB paths
# ===========================================================================


class TestOutlookGmailDirectFetchDB:
    @pytest.mark.asyncio
    async def test_outlook_no_active_connection(self, pipeline):
        svc = pipeline["svc"]
        # svc.db is a FakeSession; query(...).first() returns None.
        with patch.object(_FakeQuery, "first", return_value=None):
            result = await svc._fetch_outlook_resource_direct("conn-1", "Users/x/Messages/m1")
        assert result is None

    @pytest.mark.asyncio
    async def test_gmail_no_active_connection(self, pipeline):
        svc = pipeline["svc"]
        with patch.object(_FakeQuery, "first", return_value=None):
            result = await svc._fetch_gmail_resource_direct("conn-1", "users/me/messages/m1")
        assert result is None


# ===========================================================================
# Multi-entity extraction / schema discovery (LLM + DB mocked)
# ===========================================================================


class TestMultiEntityExtraction:
    @pytest.mark.asyncio
    async def test_process_multi_entity_no_entities_returns_zero(self, pipeline):
        svc = pipeline["svc"]
        # _extract_multi_entity_only returns [] when LLM yields nothing.
        pipeline["extractor"]._build_extraction_prompt.return_value = "p"
        pipeline["extractor"]._parse_llm_response.return_value = []
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="")
        out = await svc._process_multi_entity_extraction(
            {"id": "r1"}, "salesforce", "some text", "job1", llm_service=llm
        )
        assert out == 0

    @pytest.mark.asyncio
    async def test_process_multi_entity_with_entities(self, pipeline):
        svc = pipeline["svc"]
        svc.db = pipeline["session"]  # inject fake session so add_all is captured
        ent = MagicMock()
        pipeline["extractor"]._build_extraction_prompt.return_value = "p"
        pipeline["extractor"]._parse_llm_response.return_value = [ent]
        llm = MagicMock()
        llm.generate = AsyncMock(return_value='{"entities": []}')
        out = await svc._process_multi_entity_extraction(
            {"id": "r1"}, "salesforce", "text", "job1", llm_service=llm
        )
        assert out == 1
        # entity was added to the session
        assert ent in pipeline["session"].added

    @pytest.mark.asyncio
    async def test_extract_multi_entity_all_attempts_empty(self, pipeline):
        svc = pipeline["svc"]
        pipeline["extractor"]._build_extraction_prompt.return_value = "p"
        pipeline["extractor"]._parse_llm_response.return_value = []
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="")  # empty response -> retry -> empty
        out = await svc._extract_multi_entity_only(
            {"id": "r1"}, "salesforce", "text", "job1", llm_service=llm
        )
        assert out == []

    @pytest.mark.asyncio
    async def test_extract_multi_entity_llm_exception_continues(self, pipeline):
        svc = pipeline["svc"]
        pipeline["extractor"]._build_extraction_prompt.return_value = "p"
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("llm down"))
        out = await svc._extract_multi_entity_only(
            {"id": "r1"}, "salesforce", "text", "job1", llm_service=llm
        )
        assert out == []

    @pytest.mark.asyncio
    async def test_process_multi_entity_with_none_db(self, pipeline, monkeypatch):
        """When self.db is None (webhook path), a local SessionLocal is created."""
        svc = pipeline["svc"]
        svc.db = None
        ent = MagicMock()
        pipeline["extractor"]._build_extraction_prompt.return_value = "p"
        pipeline["extractor"]._parse_llm_response.return_value = [ent]
        llm = MagicMock()
        llm.generate = AsyncMock(return_value='{"entities":[1]}')
        # The function imports SessionLocal from core.database, so patch there.
        local_session = FakeSession()
        monkeypatch.setattr("core.database.SessionLocal", lambda: local_session)
        out = await svc._process_multi_entity_extraction(
            {"id": "r1"}, "salesforce", "text", "job1", llm_service=llm
        )
        assert out == 1
        assert ent in local_session.added


class TestProcessExtractedEntities:
    @pytest.mark.asyncio
    async def test_creates_discovered_models(self, pipeline):
        svc = pipeline["svc"]
        svc.db = pipeline["session"]  # inject fake session
        entities = [
            {"type": "Contact", "properties": {"name": "A"}, "confidence": 0.9},
            {"type": "Deal", "properties": {}, "confidence": 0.5},
        ]
        with patch.object(ip, "DiscoveredEntity") as DE:
            DE.return_value = MagicMock()
            out = await svc._process_extracted_entities(entities, {"id": "rec1", "type": "email"}, "job-1")
        assert len(out) == 2
        # Both were added to the session and flushed.
        assert len(pipeline["session"].added) == 2

    @pytest.mark.asyncio
    async def test_empty_entities_returns_empty(self, pipeline):
        svc = pipeline["svc"]
        out = await svc._process_extracted_entities([], {"id": "rec1"}, "job-1")
        assert out == []
        assert pipeline["session"].added == []


class TestRunSchemaDiscovery:
    @pytest.mark.asyncio
    async def test_runs_without_error(self, pipeline):
        svc = pipeline["svc"]
        pipeline["schema"].discover_schemas_from_entities = AsyncMock(return_value=[MagicMock()])
        pipeline["linker"].link_entities_to_graph = AsyncMock(return_value=[MagicMock(), MagicMock()])
        pipeline["meta"].orchestrate_ontology_management = AsyncMock()
        results = {"entities_extracted": 0, "records_processed": 1}
        await svc._run_schema_discovery(results)
        # linked_nodes count (2) added to entities_extracted
        assert results["entities_extracted"] == 2

    @pytest.mark.asyncio
    async def test_schema_discovery_exception_swallowed(self, pipeline):
        svc = pipeline["svc"]
        pipeline["schema"].discover_schemas_from_entities = AsyncMock(side_effect=RuntimeError("boom"))
        results = {"records_processed": 1}
        # Must not raise.
        await svc._run_schema_discovery(results)


# ===========================================================================
# BUG-HUNT (TDD): real defects found by close reading.
# ===========================================================================


class TestTransformerBugs:
    @pytest.mark.asyncio
    async def test_bug_getresponse_missing_event_key(self, pipeline):
        """BUG: _transform_getresponse_payload used .get('event', '') (a string
        default) then called .get('name','') on it -> AttributeError when a
        GetResponse webhook omits the 'event' key. Default should be {}.
        Function+line: core/ingestion_pipeline.py:_transform_getresponse_payload
        (~line 2374)."""
        svc = pipeline["svc"]
        # Payload has no 'event' key (and no 'contact' either) -> must not raise.
        out = await svc._transform_getresponse_payload({"contact": {"contact_id": "g1"}})
        assert out[0]["event_type"] == ""
        assert out[0]["id"] == "g1"

    @pytest.mark.asyncio
    async def test_bug_bitbucket_empty_changes_list(self, pipeline):
        """BUG: _transform_bitbucket_payload computed
        webhook_data.get('changes', [{}])[0] which raises IndexError when
        'changes' is present but an empty list (a valid push webhook can have
        no change entries). Function+line:
        core/ingestion_pipeline.py:_transform_bitbucket_payload (~line 2622).
        Because _transform_webhook_payload wraps transformers in try/except,
        the crash silently dropped the ENTIRE webhook (returns [])."""
        svc = pipeline["svc"]
        # 'changes' present but empty -> must not raise, must produce a record.
        out = await svc._transform_bitbucket_payload({"changes": []})
        assert len(out) == 1
        assert out[0]["type"] == "bitbucket_push"
        # id should be empty (no hashes) rather than crash.
        assert out[0]["id"] == ""

    @pytest.mark.asyncio
    async def test_bug_bitbucket_empty_changes_via_standardizer(self, pipeline):
        """Same bug, demonstrated end-to-end through _transform_webhook_payload:
        before the fix, an empty 'changes' list caused the whole Bitbucket
        webhook to be silently dropped (returns []). After the fix it yields a
        record."""
        svc = pipeline["svc"]
        out = await svc._transform_webhook_payload("bitbucket", {"changes": []})
        assert len(out) == 1
        assert out[0]["type"] == "bitbucket_push"
