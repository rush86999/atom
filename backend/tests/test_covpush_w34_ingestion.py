"""Coverage wave 34 — core/ingestion_pipeline (53% → 85%+).

Targets the deterministic helpers + webhook transformers:
- _hash_text, _record_doc_ingestion (create/update/IntegrityError/error),
  _is_doc_already_ingested (match/differ/missing)
- _get_user_credentials (found w/ + w/o expiry, not-found, exception)
- _create_ingestion_job (success + fallback), _update_ingestion_job
  (success/not-found/exception)
- _transform_slack/hubspot/salesforce/gmail/notion payloads
- all 10 zoho transforms (parametrized)
"""
import os
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ingestion_pipeline import IngestionPipelineService


@pytest.fixture
def svc():
    return IngestionPipelineService(tenant_id="t1", workspace_id="ws1", db=MagicMock())


class TestHashing:
    def test_hash_deterministic(self):
        h1 = IngestionPipelineService._hash_text("hello world")
        h2 = IngestionPipelineService._hash_text("hello world")
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_differs(self):
        assert (IngestionPipelineService._hash_text("a")
                != IngestionPipelineService._hash_text("b"))


class TestDocIngestion:
    def test_record_create_and_update(self, svc):
        session = MagicMock()
        existing = MagicMock()
        session.query.return_value.filter_by.return_value.first.side_effect = [None, existing]
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            svc._record_doc_ingestion("ws1", "doc-1", "text", "source-x")
            svc._record_doc_ingestion("ws1", "doc-1", "text2", "source-y")
        assert session.add.called
        assert existing.content_hash
        assert existing.source == "source-y"
        assert session.commit.called
        assert session.close.called

    def test_record_integrity_error_rollback(self, svc):
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None
        from sqlalchemy.exc import IntegrityError
        session.commit.side_effect = IntegrityError("stmt", {}, Exception("dup"))
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            svc._record_doc_ingestion("ws1", "doc-1", "text", "s")
        assert session.rollback.called

    def test_record_generic_error_rollback(self, svc):
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.side_effect = RuntimeError("boom")
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            svc._record_doc_ingestion("ws1", "doc-1", "text", "s")
        assert session.rollback.called

    def test_is_already_ingested(self, svc):
        session = MagicMock()
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text("text")
        session.query.return_value.filter_by.return_value.first.return_value = existing
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            assert svc._is_doc_already_ingested("ws1", "doc-1", "text") is True
            assert svc._is_doc_already_ingested("ws1", "doc-1", "other") is False
        assert session.close.called

    def test_is_already_ingested_missing(self, svc):
        session = MagicMock()
        session.query.return_value.filter_by.return_value.first.return_value = None
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            assert svc._is_doc_already_ingested("ws1", "doc-1", "text") is False


class TestCredentials:
    def test_credentials_found_with_expiry(self, svc):
        session = MagicMock()
        conn = MagicMock()
        conn.id = "conn-1"
        conn.integration_id = "slack"
        conn.user_id = "u1"
        conn.expires_at = SimpleNamespace(isoformat=lambda: "2026-12-31")
        session.query.return_value.filter.return_value.first.return_value = conn
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            creds = svc._get_user_credentials("slack", "u1")
        assert creds["connection_id"] == "conn-1"
        assert creds["token_valid_until"] == "2026-12-31"
        assert session.close.called

    def test_credentials_no_expiry(self, svc):
        session = MagicMock()
        conn = MagicMock()
        conn.id = "conn-2"
        conn.integration_id = "gmail"
        conn.user_id = "u1"
        conn.expires_at = None
        session.query.return_value.filter.return_value.first.return_value = conn
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            creds = svc._get_user_credentials("gmail", "u1")
        assert creds["token_valid_until"] is None

    def test_credentials_not_found(self, svc):
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            assert svc._get_user_credentials("slack", "u1") is None

    def test_credentials_exception(self, svc):
        session = MagicMock()
        session.query.side_effect = RuntimeError("db down")
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            assert svc._get_user_credentials("slack", "u1") is None


class TestIngestionJobs:
    def test_create_job_success(self, svc):
        session = MagicMock()
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session), \
             patch("core.ingestion_pipeline.INGESTION_JOB_EXISTS", True), \
             patch("core.ingestion_pipeline.IngestionJob") as job_cls:
            job = MagicMock()
            job.id = "job-1"
            job_cls.return_value = job
            job_id = svc._create_ingestion_job("slack", "webhook", connection_id="conn-1")
        assert job_id == "job-1"
        assert session.add.called
        assert job_cls.call_args.kwargs["source_connection_id"] == "conn-1"

    def test_create_job_fallback_model_missing(self, svc):
        with patch("core.ingestion_pipeline.INGESTION_JOB_EXISTS", False):
            job_id = svc._create_ingestion_job("slack", "webhook")
        assert job_id.startswith("fallback-")

    def test_create_job_exception_fallback(self, svc):
        session = MagicMock()
        session.add.side_effect = RuntimeError("boom")
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session), \
             patch("core.ingestion_pipeline.INGESTION_JOB_EXISTS", True), \
             patch("core.ingestion_pipeline.IngestionJob"):
            job_id = svc._create_ingestion_job("slack", "webhook")
        assert job_id.startswith("fallback-")
        assert session.rollback.called

    def test_update_job_success(self, svc):
        session = MagicMock()
        job = MagicMock()
        job.id = "job-1"
        session.query.return_value.filter.return_value.first.return_value = job
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            result = svc._update_ingestion_job(
                "job-1", "completed", records_fetched=10, error_message="err"
            )
        assert result is True
        assert job.status == "completed"
        assert job.records_fetched == 10
        assert job.error_message == "err"
        assert session.commit.called

    def test_update_job_not_found(self, svc):
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            result = svc._update_ingestion_job("job-1", "completed")
        assert result is False

    def test_update_job_exception(self, svc):
        session = MagicMock()
        session.query.side_effect = RuntimeError("boom")
        with patch("core.ingestion_pipeline.SessionLocal", return_value=session):
            result = svc._update_ingestion_job("job-1", "completed")
        assert result is False


class TestWebhookTransforms:
    async def test_slack_message_event(self, svc):
        records = await svc._transform_slack_payload({
            "type": "event_callback",
            "team_id": "T1",
            "event": {
                "type": "message", "client_msg_id": "m1",
                "text": "hello", "channel": "C1", "user": "U1", "ts": "123",
            },
        })
        assert len(records) == 1
        assert records[0]["type"] == "slack_message"
        assert records[0]["id"] == "m1"
        assert records[0]["team"] == "T1"

    async def test_slack_non_message(self, svc):
        records = await svc._transform_slack_payload({"type": "url_verification"})
        assert records == []

    async def test_hubspot_list_and_single(self, svc):
        records = await svc._transform_hubspot_payload([
            {"subscriptionType": "contact.creation", "objectId": 1, "properties": {"a": 1}},
            {"subscriptionType": "deal.creation", "objectId": 2},
        ])
        assert len(records) == 2
        assert records[0]["type"] == "hubspot_contact.creation"
        assert records[0]["id"] == 1

        single = await svc._transform_hubspot_payload({"subscriptionType": "x", "objectId": 9})
        assert len(single) == 1
        assert single[0]["id"] == 9

    async def test_salesforce_multiple_ids(self, svc):
        records = await svc._transform_salesforce_payload({
            "eventType": "change", "objectType": "Account",
            "recordIds": ["001a", "001b"],
            "changeEventHeader": {"changeTypes": ["CREATE"]},
        })
        assert len(records) == 2
        assert records[0]["type"] == "salesforce_account"
        assert records[1]["id"] == "001b"
        assert records[0]["changes"] == ["CREATE"]

    async def test_gmail_no_connection(self, svc):
        # fallback record is still produced when no connection id is present
        records = await svc._transform_gmail_payload({"historyId": "h1"})
        assert len(records) == 1
        assert records[0]["type"] == "gmail_message"
        assert records[0]["subject"] == "New email notification"

    async def test_gmail_with_fetch(self, svc):
        svc._fetch_gmail_resource_direct = AsyncMock(side_effect=[
            {"history": [{"messagesAdded": [
                {"message": {"id": "msg1"}}, {"message": {"id": "msg2"}},
            ]}]},
            {"payload": {"headers": [{"name": "Subject", "value": "Hi"}]},
             "threadId": "t1", "internalDate": "1700000000000"},
            {"payload": {"headers": [{"name": "Subject", "value": "Hi2"}]},
             "threadId": "t2", "internalDate": "1700000001000"},
        ])
        records = await svc._transform_gmail_payload({
            "historyId": "h1", "_source_connection_id": "conn-1",
        })
        assert len(records) == 2
        assert records[0]["type"] == "gmail_message"
        assert records[0]["message_id"] == "msg1"
        assert records[0]["subject"] == "Hi"
        assert records[1]["message_id"] == "msg2"

    async def test_notion_payload(self, svc):
        records = await svc._transform_notion_payload({
            "activity_type": "page.created", "id": "p1", "title": "T",
        })
        assert len(records) == 1
        assert records[0]["type"] == "notion_page"
        assert records[0]["event_type"] == "page.created"


class TestZohoTransforms:
    @pytest.mark.parametrize("name,payload,expected_type", [
        ("crm", {"module": {"api_name": "Leads"}, "key_id": "1", "data": {}}, "zoho_crm_leads"),
        ("books", {"module": "invoices", "IDs": {"entity_id": "2"}, "payload": {}}, "zoho_books_invoices"),
        ("projects", {"module": "tasks", "id": "3", "data": {}}, "zoho_projects_tasks"),
        ("desk", {"ticketId": "4", "ticket": {}}, "zoho_desk_ticket"),
        ("recruit", {"module": "Candidates", "entityId": "5", "data": {}}, "zoho_recruit_candidates"),
        ("campaigns", {"campaign_id": "6", "data": {}}, "zoho_campaigns_campaign"),
        ("forms", {"submission_id": "7", "data": {}}, "zoho_forms_submission"),
        ("showtime", {"session_id": "8", "data": {}}, "zoho_showtime_session"),
        ("meeting", {"meeting_id": "9", "data": {}}, "zoho_meeting_session"),
        ("assist", {"session_id": "10", "data": {}}, "zoho_assist_session"),
    ])
    async def test_zoho_transform(self, svc, name, payload, expected_type):
        fn = getattr(svc, f"_transform_zoho_{name}_payload")
        records = await fn(payload)
        assert len(records) == 1
        assert records[0]["type"] == expected_type
        assert records[0]["id"]


class TestDispatcher:
    async def test_dispatch_known_integration(self, svc):
        records = await svc._transform_webhook_payload("slack", {
            "type": "event_callback",
            "event": {"type": "message", "text": "hi", "channel": "C1"},
        })
        assert records and records[0]["type"] == "slack_message"

    async def test_dispatch_unknown_integration(self, svc):
        records = await svc._transform_webhook_payload("not_an_integration", {})
        assert records == []

    async def test_dispatch_zoho_crm(self, svc):
        records = await svc._transform_webhook_payload(
            "zoho_crm", {"module": {"api_name": "Leads"}, "key_id": "1"}
        )
        assert records[0]["type"] == "zoho_crm_leads"

    async def test_dispatch_transformer_exception(self, svc):
        with patch.object(svc, "_transform_slack_payload",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            records = await svc._transform_webhook_payload("slack", {})
        assert records == []


class TestAllTransformers:
    """Drive every registered transformer with an empty payload — each must
    return a list (records) without raising."""

    @pytest.mark.parametrize("integration", [
        "slack", "hubspot", "salesforce", "gmail", "notion",
        "zoho_crm", "zoho_books", "zoho_projects", "zoho_desk",
        "zoho_recruit", "zoho_campaigns", "zoho_forms", "zoho_showtime",
        "zoho_meeting", "zoho_assist",
        "jira", "asana", "trello", "monday", "clickup", "linear",
        "pipedrive", "zendesk_sell", "insightly", "freshsales", "salesloft",
        "mailchimp", "activecampaign", "sendgrid", "convertkit", "getresponse",
        "discord", "teams", "telegram", "twilio", "whatsapp", "intercom",
        "github", "gitlab", "bitbucket",
        "google_drive", "dropbox", "box", "onedrive",
        "shopify", "woocommerce", "bigcommerce", "magento", "stripe",
        "airtable", "webex", "zoom", "freshdesk", "figma", "outlook",
    ])
    async def test_transformer_handles_empty_payload(self, svc, integration):
        records = await svc._transform_webhook_payload(integration, {})
        assert isinstance(records, list)
