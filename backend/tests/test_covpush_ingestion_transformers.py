# -*- coding: utf-8 -*-
"""
Coverage-push tests for core/ingestion_pipeline.py — payload transformers,
multi-entity extraction helpers, and direct Graph API fetchers.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import core.hybrid_data_ingestion as hdi
import core.ingestion_pipeline as ip
from core.hybrid_data_ingestion import SyncConfiguration
from core.ingestion_pipeline import IngestionPipelineService


class _FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model

    def filter(self, *a, **k):
        return self

    def first(self):
        return self.session.user_conn


class FakeSession:
    def __init__(self, user_conn=None):
        self.user_conn = user_conn
        self.committed = 0
        self.closed = 0
        self.bind = None

    def query(self, model):
        return _FakeQuery(self, model)

    def commit(self):
        self.committed += 1

    def close(self):
        self.closed += 1

    def add_all(self, objs):
        self.added = objs

    def flush(self):
        pass

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

    monkeypatch.setattr("core.lancedb_handler.get_lancedb_handler", lambda *a, **k: fake_lancedb)
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda *a, **k: fake_graphrag)
    monkeypatch.setattr("core.llm_service.get_llm_service", lambda *a, **k: fake_llm)
    monkeypatch.setattr(ip, "LanceDBHandler", lambda *a, **k: fake_lancedb)
    monkeypatch.setattr(ip, "GraphRAGEngine", lambda *a, **k: fake_graphrag)
    monkeypatch.setattr(ip, "MultiEntityLLMExtractor", lambda *a, **k: fake_extractor)
    monkeypatch.setattr(ip, "SchemaDiscoveryService", lambda *a, **k: fake_schema)
    monkeypatch.setattr(ip, "EntityLinkingService", lambda *a, **k: fake_linker)
    monkeypatch.setattr("core.meta_agent_orchestrator.MetaAgentOrchestrator", lambda *a, **k: fake_meta)
    monkeypatch.setattr(ip, "UsageTrackingService", lambda *a, **k: fake_usage)
    monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession())

    fake_usage.track_acu_usage = AsyncMock(return_value=MagicMock(id="usage-1"))
    fake_usage.calculate_acu_consumed = MagicMock(return_value=1.5)

    svc = IngestionPipelineService(tenant_id="t1", workspace_id="ws1")

    return {
        "svc": svc,
        "lancedb": fake_lancedb,
        "graphrag": fake_graphrag,
        "usage": fake_usage,
        "extractor": fake_extractor,
        "schema": fake_schema,
        "linker": fake_linker,
        "meta": fake_meta,
        "llm": fake_llm,
    }


TRANSFORM_CASES = [
    ("slack", {"type": "event_callback", "event": {"type": "message", "text": "hi", "ts": "1"}}),
    ("hubspot", [{"subscriptionType": "contact.creation", "objectId": 1, "properties": {}}]),
    ("salesforce", {"eventType": "created", "objectType": "Account", "recordIds": ["a1"]}),
    ("notion", {"id": "p1", "title": "T", "activity_type": "page.created"}),
    ("zoho_crm", {"module": {"api_name": "Leads"}, "key_id": "1"}),
    ("zoho_books", {"module": "Invoice", "IDs": {"entity_id": "2"}}),
    ("zoho_projects", {"id": "3", "project_id": "p", "module": "Task"}),
    ("zoho_desk", {"ticketId": "4"}),
    ("zoho_recruit", {"module": "Candidates", "entityId": "5"}),
    ("zoho_campaigns", {"campaign_id": "6"}),
    ("zoho_forms", {"submission_id": "7"}),
    ("zoho_showtime", {"session_id": "8"}),
    ("zoho_meeting", {"meeting_id": "9"}),
    ("zoho_assist", {"session_id": "10"}),
    (
        "jira",
        {"webhookEvent": "jira:issue_created", "issue": {"id": "1", "key": "J-1", "fields": {"summary": "S"}}},
    ),
    ("asana", {"gid": "11", "name": "Task", "action": "created"}),
    ("trello", {"action": {"type": "updateCard", "data": {"card": {"id": "c1", "name": "Card"}, "listAfter": {"id": "l2"}}}}),
    ("monday", {"event": {"type": "create_item"}, "payload": {"item_id": "12", "item_name": "Item"}}),
    ("clickup", {"event": "taskCreated", "task": {"id": "13", "name": "Task"}}),
    ("linear", {"action": "create", "data": {"id": "14", "title": "Issue", "state": {"name": "Todo"}}}),
    ("pipedrive", {"object": "deal", "event": "created", "current": {"id": "15", "title": "Deal"}}),
    ("zendesk_sell", {"target_type": "lead", "target_id": "16", "trigger": "create"}),
    ("insightly", {"object_name": "Contact", "record_id": "17", "event": "create"}),
    ("freshsales", {"entity_type": "deal", "action": "create", "payload": {"id": "18"}}),
    ("salesloft", {"event": {"action": "created"}, "data": {"id": "19", "name": "Cadence"}}),
    ("mailchimp", {"type": "subscribe", "data": {"id": "20", "email": "a@b.c"}}),
    ("activecampaign", {"type": "update", "contact": {"id": "21", "email": "a@b.c"}}),
    ("sendgrid", [{"sg_message_id": "22", "event": "delivered", "email": "a@b.c"}]),
    ("convertkit", {"subscriber": {"id": "23", "email_address": "a@b.c"}, "event": {"name": "subscribe"}}),
    ("getresponse", {"contact": {"contact_id": "24", "email": "a@b.c"}, "event": {"name": "new"}}),
    ("discord", {"id": "25", "content": "hi", "author": {"username": "u"}, "channel_id": "c1"}),
    ("teams", {"id": "26", "text": "hi", "from": {"application": {"displayName": "app"}}}),
    ("telegram", {"message": {"message_id": 27, "text": "hi", "chat": {"id": 1}, "from": {"id": 9, "first_name": "Bob"}}}),
    ("twilio", {"MessageSid": "SM1", "From": "+1", "To": "+2", "MessageStatus": "delivered"}),
    ("intercom", {"topic": "conversation.created", "data": {"id": "28", "conversation_message": {"subject": "S"}}}),
    ("github", {"action": "opened", "pull_request": {"number": 29, "title": "PR", "state": "open"}}),
    ("github", {"action": "opened", "issue": {"number": 30, "title": "Issue", "state": "open"}}),
    ("github", {"after": "abc12345", "ref": "refs/heads/main"}),
    ("gitlab", {"object_kind": "merge_request", "object_attributes": {"iid": "31", "title": "MR", "action": "open"}}),
    ("gitlab", {"object_kind": "issue", "object_attributes": {"iid": "32", "title": "Issue"}}),
    ("gitlab", {"object_kind": "push", "after": "abc12345", "ref": "main"}),
    ("bitbucket", {"action": "created", "pullrequest": {"id": 33, "title": "PR", "state": "open"}}),
    ("bitbucket", {"changes": [{"toHash": "abc12345", "ref": {"displayId": "main"}}]}),
    ("google_drive", {"file_id": "34", "name": "f", "action": "created"}),
    ("dropbox", {"file_id": "35", "name": "f", "event_type": "add"}),
    ("box", {"file_id": "36", "file_name": "f", "event_type": "created"}),
    ("onedrive", {"file_id": "37", "file_name": "f", "action": "created"}),
    ("shopify", {"topic": "orders/create", "id": "38", "total_price": "10"}),
    ("woocommerce", {"id": "39", "total": "10", "status": "completed", "action": "order_created"}),
    ("bigcommerce", {"scope": "store/order/created", "data": {"id": "40", "total_tax_inc": "5"}}),
    ("magento", {"entity_id": "41", "grand_total": "10", "event_name": "sales_order"}),
    ("stripe", {"type": "charge.succeeded", "data": {"object": {"object": "charge", "id": "ch_1", "amount": 100}}}),
    ("airtable", {"record_id": "42", "base_id": "b", "table_id": "t", "action": "create"}),
    ("webex", {"name": "message:created", "data": {"id": "43", "text": "hi", "personId": "p"}}),
    ("zoom", {"event": "meeting.ended", "id": "44", "topic": "Sync"}),
    ("freshdesk", {"ticket_id": "45", "subject": "S", "status": "open", "trigger": "create"}),
    ("figma", {"file_key": "46", "file_name": "f", "event_type": "file_update"}),
    ("outlook", {"id": "m1", "subject": "Subj", "content": "Body", "from": "a@b.c"}),
]


class TestTransformers:
    @pytest.fixture
    def svc(self, pipeline):
        return pipeline["svc"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("integration_id,payload", TRANSFORM_CASES)
    async def test_transform_produces_records(self, svc, integration_id, payload):
        method = getattr(svc, f"_transform_{integration_id.replace('-', '_')}_payload")
        records = await method(payload)
        assert isinstance(records, list)
        assert len(records) >= 1
        assert all(isinstance(r, dict) for r in records)

    @pytest.mark.asyncio
    async def test_transform_slack_no_event(self, svc):
        assert await svc._transform_slack_payload({"type": "url_verification"}) == []

    @pytest.mark.asyncio
    async def test_transform_salesforce_empty_ids(self, svc):
        assert await svc._transform_salesforce_payload({"recordIds": []}) == []

    @pytest.mark.asyncio
    async def test_transform_gmail_fallback(self, svc):
        records = await svc._transform_gmail_payload({"historyId": "h1", "emailAddress": "a@b.c"})
        assert records[0]["type"] == "gmail_message"
        assert records[0]["id"] == "h1"

    @pytest.mark.asyncio
    async def test_transform_gmail_with_connection(self, svc):
        async def fake_fetch(conn_id, path):
            if "history" in path:
                return {"history": [{"messagesAdded": [{"message": {"id": "m1"}}]}]}
            return {
                "id": "m1",
                "threadId": "t1",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Hello"},
                        {"name": "From", "value": "x@y.z"},
                        {"name": "To", "value": "to@x.z"},
                    ]
                },
                "snippet": "snippet text",
                "internalDate": "1700000000000",
            }

        svc._fetch_gmail_resource_direct = AsyncMock(side_effect=fake_fetch)
        records = await svc._transform_gmail_payload({"historyId": "h1", "_source_connection_id": "c1"})
        assert len(records) == 1
        assert records[0]["subject"] == "Hello"

    @pytest.mark.asyncio
    async def test_transform_gmail_bad_internal_date(self, svc):
        async def fake_fetch(conn_id, path):
            if "history" in path:
                return {"history": [{"messagesAdded": [{"message": {"id": "m1"}}]}]}
            return {"id": "m1", "payload": {"headers": []}, "internalDate": "not-a-date"}

        svc._fetch_gmail_resource_direct = AsyncMock(side_effect=fake_fetch)
        records = await svc._transform_gmail_payload({"historyId": "h1", "_source_connection_id": "c1"})
        assert records[0]["timestamp"] is not None

    @pytest.mark.asyncio
    async def test_transform_gmail_fetch_error_fallback(self, svc):
        svc._fetch_gmail_resource_direct = AsyncMock(side_effect=Exception("boom"))
        records = await svc._transform_gmail_payload({"historyId": "h1", "_source_connection_id": "c1"})
        assert len(records) == 1
        assert records[0]["id"] == "h1"

    @pytest.mark.asyncio
    async def test_transform_telegram_empty(self, svc):
        assert await svc._transform_telegram_payload({"update_id": 1}) == []

    @pytest.mark.asyncio
    async def test_transform_telegram_channel_post(self, svc):
        records = await svc._transform_telegram_payload(
            {"channel_post": {"message_id": 2, "text": "post", "chat": {"id": 2, "title": "Ch"}}}
        )
        assert records[0]["type"] == "telegram_message"

    @pytest.mark.asyncio
    async def test_transform_telegram_media(self, svc):
        records = await svc._transform_telegram_payload(
            {
                "message": {
                    "message_id": 3,
                    "caption": "with photo",
                    "chat": {"id": 3},
                    "from": {"id": 4, "username": "u"},
                    "photo": [{"file_id": "small"}, {"file_id": "large"}],
                }
            }
        )
        assert records[0]["properties"]["media_type"] == "photo"
        assert records[0]["properties"]["media_id"] == "large"

    @pytest.mark.asyncio
    async def test_transform_whatsapp(self, svc):
        records = await svc._transform_whatsapp_payload(
            {
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "metadata": {"phone_number_id": "pn1"},
                                    "messages": [
                                        {"id": "w1", "from": "1555", "timestamp": "123", "text": {"body": "hi"}}
                                    ],
                                }
                            }
                        ]
                    }
                ]
            }
        )
        assert len(records) == 1
        assert records[0]["direction"] == "inbound"
        assert records[0]["text"] == "hi"

    @pytest.mark.asyncio
    async def test_transform_whatsapp_exception(self, svc):
        assert await svc._transform_whatsapp_payload({"entry": None}) == []

    @pytest.mark.asyncio
    async def test_transform_outlook_pre_normalized(self, svc):
        records = await svc._transform_outlook_payload(
            {"id": "m1", "subject": "Subj", "content": "Body", "from": "a@b.c", "metadata": {}}
        )
        assert records[0]["type"] == "email"

    @pytest.mark.asyncio
    async def test_transform_outlook_raw_message(self, svc):
        svc._fetch_outlook_resource_direct = AsyncMock(
            return_value={
                "id": "g1",
                "from": {"emailAddress": {"address": "a@b.c"}},
                "subject": "S",
                "bodyPreview": "Preview",
                "body": {"content": "Body"},
                "receivedDateTime": "t1",
            }
        )
        records = await svc._transform_outlook_payload(
            {
                "resource": "Users/u/Messages/g1",
                "resourceData": {"@odata.type": "#Microsoft.Graph.Message"},
                "_source_connection_id": "c1",
            }
        )
        assert len(records) == 1
        assert records[0]["id"] == "g1"

    @pytest.mark.asyncio
    async def test_transform_outlook_raw_event(self, svc):
        svc._fetch_outlook_resource_direct = AsyncMock(
            return_value={"id": "e1", "subject": "Meeting", "body": {"content": "agenda"}, "start": {}, "end": {}}
        )
        records = await svc._transform_outlook_payload(
            {
                "resource": "Users/u/Events/e1",
                "resourceData": {"@odata.type": "#Microsoft.Graph.Event"},
                "_source_connection_id": "c1",
            }
        )
        assert records[0]["type"] == "calendar_event"

    @pytest.mark.asyncio
    async def test_transform_outlook_raw_other(self, svc):
        svc._fetch_outlook_resource_direct = AsyncMock(return_value={"id": "d1", "name": "file"})
        records = await svc._transform_outlook_payload(
            {
                "resource": "Users/u/Drive/d1",
                "resourceData": {"@odata.type": "#Microsoft.Graph.DriveItem"},
                "_source_connection_id": "c1",
            }
        )
        assert records[0]["type"] == "outlook_resource"

    @pytest.mark.asyncio
    async def test_transform_outlook_raw_fetch_failure(self, svc):
        svc._fetch_outlook_resource_direct = AsyncMock(return_value=None)
        records = await svc._transform_outlook_payload(
            {
                "resource": "Users/u/Messages/g1",
                "resourceData": {"@odata.type": "#Microsoft.Graph.Message"},
                "_source_connection_id": "c1",
            }
        )
        assert records == []

    @pytest.mark.asyncio
    async def test_transform_outlook_raw_fetch_exception(self, svc):
        svc._fetch_outlook_resource_direct = AsyncMock(side_effect=Exception("boom"))
        records = await svc._transform_outlook_payload(
            {
                "resource": "Users/u/Messages/g1",
                "resourceData": {"@odata.type": "#Microsoft.Graph.Message"},
                "_source_connection_id": "c1",
            }
        )
        assert records == []

    @pytest.mark.asyncio
    async def test_transform_dispatch_unknown(self, svc):
        assert await svc._transform_webhook_payload("made_up", {}) == []

    @pytest.mark.asyncio
    async def test_transform_dispatch_standardizes(self, svc):
        payload = {
            "team_id": "T1",
            "type": "event_callback",
            "event": {
                "type": "message",
                "client_msg_id": "m1",
                "text": "Hello world message",
                "channel": "C1",
                "user": "U1",
                "ts": "1.1",
            },
        }
        records = await svc._transform_webhook_payload("slack", payload)
        rec = records[0]
        assert rec["id"] == "m1"
        assert rec["sender_id"] == "U1"
        assert rec["subject"] == "message"
        assert rec["content"] == "Hello world message"
        assert rec["timestamp"] == "1.1"
        assert "metadata" in rec

    @pytest.mark.asyncio
    async def test_transform_dispatch_skips_non_dict(self, svc):
        with patch.object(
            svc, "_transform_slack_payload", new=AsyncMock(return_value=[{"id": "a"}, "not-dict", None])
        ):
            records = await svc._transform_webhook_payload("slack", {})
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_transform_dispatch_uuid_sanitization(self, svc):
        uid = uuid.uuid4()
        with patch.object(
            svc,
            "_transform_slack_payload",
            new=AsyncMock(
                return_value=[
                    {
                        "id": uid,
                        "sender_id": uid,
                        "text": "content here",
                        "metadata": {"nested": uid, "arr": [uid], "str": "keep"},
                    }
                ]
            ),
        ):
            records = await svc._transform_webhook_payload("slack", {})
        rec = records[0]
        assert isinstance(rec["id"], str)
        assert isinstance(rec["sender_id"], str)
        assert isinstance(rec["metadata"]["nested"], str)
        assert isinstance(rec["metadata"]["arr"][0], str)
        assert rec["metadata"]["str"] == "keep"

    @pytest.mark.asyncio
    async def test_transform_dispatch_empty_records(self, svc):
        with patch.object(svc, "_transform_slack_payload", new=AsyncMock(return_value=[])):
            assert await svc._transform_webhook_payload("slack", {}) == []

    @pytest.mark.asyncio
    async def test_transform_dispatch_transformer_exception(self, svc):
        with patch.object(svc, "_transform_slack_payload", new=AsyncMock(side_effect=Exception("boom"))):
            assert await svc._transform_webhook_payload("slack", {}) == []

    @pytest.mark.asyncio
    async def test_transform_no_fatal_debug_stderr(self, svc, capsys):
        await svc._transform_webhook_payload("slack", {"team_id": "T1", "event": {"type": "message", "text": "hi"}})
        captured = capsys.readouterr()
        assert "[FATAL_DEBUG]" not in captured.err


class TestPipelineMultiEntity:
    @pytest.mark.asyncio
    async def test_extract_multi_entity_success_first_attempt(self, pipeline):
        svc = pipeline["svc"]
        pipeline["extractor"]._build_extraction_prompt = MagicMock(return_value="prompt")
        pipeline["extractor"]._parse_llm_response = MagicMock(return_value=[MagicMock()])
        service = MagicMock()
        service.generate = AsyncMock(return_value='{"entities": []}')
        entities = await svc._extract_multi_entity_only(
            {"id": "r1", "subject": "S"}, "gmail", "long text body", "job-1", llm_service=service
        )
        assert len(entities) == 1
        service.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_extract_multi_entity_retry_after_empty(self, pipeline):
        svc = pipeline["svc"]
        pipeline["extractor"]._build_extraction_prompt = MagicMock(return_value="prompt")
        pipeline["extractor"]._parse_llm_response = MagicMock(return_value=[MagicMock()])
        service = MagicMock()
        service.generate = AsyncMock(side_effect=["", '{"entities": []}'])
        entities = await svc._extract_multi_entity_only(
            {"id": "r1"}, "gmail", "long text body", "job-1", llm_service=service
        )
        assert len(entities) == 1
        assert service.generate.await_count == 2

    @pytest.mark.asyncio
    async def test_extract_multi_entity_all_attempts_fail(self, pipeline):
        svc = pipeline["svc"]
        pipeline["extractor"]._build_extraction_prompt = MagicMock(return_value="prompt")
        pipeline["extractor"]._parse_llm_response = MagicMock(return_value=None)
        service = MagicMock()
        service.generate = AsyncMock(return_value=None)
        entities = await svc._extract_multi_entity_only(
            {"id": "r1"}, "gmail", "long text body", "job-1", llm_service=service
        )
        assert entities == []
        assert service.generate.await_count == 3

    @pytest.mark.asyncio
    async def test_extract_multi_entity_exception_retries(self, pipeline):
        svc = pipeline["svc"]
        pipeline["extractor"]._build_extraction_prompt = MagicMock(return_value="prompt")
        pipeline["extractor"]._parse_llm_response = MagicMock(return_value=[MagicMock()])
        service = MagicMock()
        service.generate = AsyncMock(side_effect=[Exception("rate limit"), '{"entities": []}'])
        entities = await svc._extract_multi_entity_only(
            {"id": "r1"}, "gmail", "long text body", "job-1", llm_service=service
        )
        assert len(entities) == 1

    @pytest.mark.asyncio
    async def test_process_multi_entity_with_db(self, pipeline):
        svc = pipeline["svc"]
        svc.db = MagicMock()
        entities = [MagicMock()]
        with _patch_entities(svc, entities):
            count = await svc._process_multi_entity_extraction(
                {"id": "r1"}, "gmail", "long text", "job-1"
            )
        assert count == 1
        svc.db.add_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_multi_entity_no_entities(self, pipeline):
        svc = pipeline["svc"]
        svc.db = MagicMock()
        with _patch_entities(svc, []):
            assert await svc._process_multi_entity_extraction({"id": "r1"}, "gmail", "long text", "job-1") == 0

    @pytest.mark.asyncio
    async def test_run_schema_discovery(self, pipeline):
        svc = pipeline["svc"]
        pipeline["schema"].discover_schemas_from_entities = AsyncMock(return_value=["type_a"])
        pipeline["linker"].link_entities_to_graph = AsyncMock(return_value=[1, 2])
        pipeline["meta"].orchestrate_ontology_management = AsyncMock()
        results = {"entities_extracted": 0}
        await svc._run_schema_discovery(results)
        assert results["entities_extracted"] == 2

    @pytest.mark.asyncio
    async def test_run_schema_discovery_orchestration_error(self, pipeline):
        svc = pipeline["svc"]
        pipeline["schema"].discover_schemas_from_entities = AsyncMock(return_value=[])
        pipeline["linker"].link_entities_to_graph = AsyncMock(return_value=[])
        pipeline["meta"].orchestrate_ontology_management = AsyncMock(side_effect=Exception("boom"))
        await svc._run_schema_discovery({"entities_extracted": 0})

    @pytest.mark.asyncio
    async def test_run_schema_discovery_error(self, pipeline):
        svc = pipeline["svc"]
        pipeline["schema"].discover_schemas_from_entities = AsyncMock(side_effect=Exception("boom"))
        await svc._run_schema_discovery({"entities_extracted": 0})

    @pytest.mark.asyncio
    async def test_process_extracted_entities(self, pipeline):
        svc = pipeline["svc"]
        db = MagicMock()
        svc.db = db
        entities = [
            {"type": "contact", "name": "Alice", "properties": {"a": 1}, "confidence": 0.9}
        ]
        models = await svc._process_extracted_entities(entities, {"id": "r1", "type": "record"}, "job-1")
        assert len(models) == 1
        assert models[0]._discovered_type == "contact"
        assert models[0].confidence_score == 0.9
        assert models[0].status == "pending"
        assert models[0].source_record_id == "r1"
        db.add_all.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_extracted_entities_empty(self, pipeline):
        svc = pipeline["svc"]
        svc.db = MagicMock()
        models = await svc._process_extracted_entities([], {"id": "r1"}, "job-1")
        assert models == []


def _patch_entities(svc, entities):
    return patch.object(
        svc,
        "_extract_multi_entity_only",
        new=AsyncMock(return_value=entities),
    )


class _FakeAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None, timeout=None):
        return self.response


class TestPipelineDirectFetch:
    @pytest.fixture
    def svc(self, pipeline):
        svc = pipeline["svc"]
        svc.db = None
        return svc

    @pytest.mark.asyncio
    async def test_outlook_no_connection_id(self, svc):
        assert await svc._fetch_outlook_resource_direct(None, "Users/u/Messages/m1") is None

    @pytest.mark.asyncio
    async def test_outlook_connection_not_found(self, svc, monkeypatch):
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=None))
        assert await svc._fetch_outlook_resource_direct("c1", "path") is None

    @pytest.mark.asyncio
    async def test_outlook_no_credentials(self, svc, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=conn))
        conn_service = MagicMock()
        conn_service._decrypt.return_value = None
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        assert await svc._fetch_outlook_resource_direct("c1", "path") is None

    @pytest.mark.asyncio
    async def test_outlook_no_access_token(self, svc, monkeypatch):
        conn = MagicMock()
        session = FakeSession(user_conn=conn)
        monkeypatch.setattr(ip, "SessionLocal", lambda: session)
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"refresh_token": "r"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        assert await svc._fetch_outlook_resource_direct("c1", "path") is None

    @pytest.mark.asyncio
    async def test_outlook_success_with_refresh(self, svc, monkeypatch):
        conn = MagicMock()
        session = FakeSession(user_conn=conn)
        monkeypatch.setattr(ip, "SessionLocal", lambda: session)
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "old"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value={"access_token": "new"})
        conn_service._encrypt.return_value = "encrypted"
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        response = httpx.Response(200, json={"id": "g1", "subject": "S"}, request=httpx.Request("GET", "http://x"))
        monkeypatch.setattr("httpx.AsyncClient", lambda: _FakeAsyncClient(response))
        data = await svc._fetch_outlook_resource_direct("c1", "Users/u/Messages/m1")
        assert data["id"] == "g1"
        assert session.committed == 1
        assert session.closed == 1

    @pytest.mark.asyncio
    async def test_outlook_https_path(self, svc, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=conn))
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "t"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        response = httpx.Response(200, json={"id": "g1"}, request=httpx.Request("GET", "http://x"))
        monkeypatch.setattr("httpx.AsyncClient", lambda: _FakeAsyncClient(response))
        data = await svc._fetch_outlook_resource_direct("c1", "https://graph.example.com/v1.0/x")
        assert data["id"] == "g1"

    @pytest.mark.asyncio
    async def test_outlook_404_returns_empty(self, svc, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=conn))
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "t"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        response = httpx.Response(404, request=httpx.Request("GET", "http://x"))
        monkeypatch.setattr("httpx.AsyncClient", lambda: _FakeAsyncClient(response))
        assert await svc._fetch_outlook_resource_direct("c1", "path") == {}

    @pytest.mark.asyncio
    async def test_outlook_http_error(self, svc, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=conn))
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "t"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        response = httpx.Response(500, request=httpx.Request("GET", "http://x"))
        monkeypatch.setattr("httpx.AsyncClient", lambda: _FakeAsyncClient(response))
        assert await svc._fetch_outlook_resource_direct("c1", "path") is None

    @pytest.mark.asyncio
    async def test_outlook_generic_error(self, svc, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=conn))
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "t"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)

        class _BoomClient(_FakeAsyncClient):
            async def get(self, url, headers=None, timeout=None):
                raise RuntimeError("network down")

        monkeypatch.setattr("httpx.AsyncClient", lambda: _BoomClient(None))
        assert await svc._fetch_outlook_resource_direct("c1", "path") is None

    @pytest.mark.asyncio
    async def test_gmail_no_connection_id(self, svc):
        assert await svc._fetch_gmail_resource_direct(None, "users/me") is None

    @pytest.mark.asyncio
    async def test_gmail_connection_not_found(self, svc, monkeypatch):
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=None))
        assert await svc._fetch_gmail_resource_direct("c1", "users/me") is None

    @pytest.mark.asyncio
    async def test_gmail_success(self, svc, monkeypatch):
        conn = MagicMock()
        session = FakeSession(user_conn=conn)
        monkeypatch.setattr(ip, "SessionLocal", lambda: session)
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "t"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        response = httpx.Response(200, json={"id": "m1"}, request=httpx.Request("GET", "http://x"))
        monkeypatch.setattr("httpx.AsyncClient", lambda: _FakeAsyncClient(response))
        data = await svc._fetch_gmail_resource_direct("c1", "users/me/messages/m1")
        assert data["id"] == "m1"
        assert session.closed == 1

    @pytest.mark.asyncio
    async def test_gmail_404(self, svc, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=conn))
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "t"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        response = httpx.Response(404, request=httpx.Request("GET", "http://x"))
        monkeypatch.setattr("httpx.AsyncClient", lambda: _FakeAsyncClient(response))
        assert await svc._fetch_gmail_resource_direct("c1", "users/me") == {}

    @pytest.mark.asyncio
    async def test_gmail_http_error(self, svc, monkeypatch):
        conn = MagicMock()
        monkeypatch.setattr(ip, "SessionLocal", lambda: FakeSession(user_conn=conn))
        conn_service = MagicMock()
        conn_service._decrypt.return_value = {"access_token": "t"}
        conn_service._refresh_token_if_needed = AsyncMock(return_value=None)
        monkeypatch.setattr("core.connection_service.ConnectionService", lambda: conn_service)
        response = httpx.Response(403, request=httpx.Request("GET", "http://x"))
        monkeypatch.setattr("httpx.AsyncClient", lambda: _FakeAsyncClient(response))
        assert await svc._fetch_gmail_resource_direct("c1", "users/me") is None
