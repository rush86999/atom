# -*- coding: utf-8 -*-
"""
Coverage-push tests for core/ingestion_pipeline.py — pipeline orchestration,
helpers, binary file/attachment preparation, webhook processing.

TDD target (RED first): process_webhook_payload / _transform_webhook_payload /
_transform_outlook_payload / _extract_multi_entity_only /
_process_multi_entity_extraction leak [FATAL_DEBUG] payload fragments (record
ids, content previews) to stderr in the webhook ingestion path.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.hybrid_data_ingestion as hdi
import core.ingestion_pipeline as ip
from core.hybrid_data_ingestion import SyncConfiguration
from core.ingestion_pipeline import IngestionPipelineService
from core.models import DocumentIngestion, IngestionJob, Tenant, UserConnection


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
        if self.model is IngestionJob:
            return self.session.job
        if self.model is DocumentIngestion:
            return self.session.existing_doc
        if self.model is UserConnection:
            return self.session.user_conn
        if self.model is Tenant:
            return self.session.tenant
        return None


class FakeSession:
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

    def delete(self, obj):
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


LONG_TEXT = "This is a sufficiently long record text for ingestion here"


def make_record(text=LONG_TEXT):
    return {"id": "r1", "type": "slack_message", "text": text, "channel": "C1", "user": "U1"}


class TestPipelineCore:
    def test_init_and_close(self, pipeline):
        svc = pipeline["svc"]
        assert svc.tenant_id == "t1"
        assert svc.workspace_id == "ws1"
        svc.graphrag.close = MagicMock()
        svc.usage_tracker.close = MagicMock()
        svc.close()
        svc.graphrag.close.assert_called_once()
        svc.usage_tracker.close.assert_called_once()

    def test_ingestion_job_model_imported(self):
        assert ip.INGESTION_JOB_EXISTS is True

    @pytest.mark.asyncio
    async def test_sync_no_configuration(self, pipeline):
        result = await pipeline["svc"].sync_and_ingest("made_up_integration")
        assert result["success"] is False
        assert "No sync configuration" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_no_records(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"]
        )
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[])):
            result = await svc.sync_and_ingest("salesforce")
        assert result["success"] is True
        assert result["records_fetched"] == 0
        assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_sync_success_full_path(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"]
        )
        record = {
            "id": "c1",
            "type": "contact",
            "name": "Alice",
            "email": "a@b.c",
            "company": "Acme",
            "text": LONG_TEXT,
        }
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[record])):
            with patch.object(
                svc, "_process_multi_entity_extraction", new=AsyncMock(return_value=2)
            ):
                with patch.object(svc, "_run_schema_discovery", new=AsyncMock()):
                    result = await svc.sync_and_ingest("salesforce")
        assert result["success"] is True
        assert result["records_processed"] == 1
        assert result["entities_extracted"] == 1
        assert result["relationships_extracted"] == 1
        assert result["acu_consumed"] == 1.5
        assert result["usage_log_id"] == "usage-1"
        assert len(pipeline["session"].added) >= 2

    @pytest.mark.asyncio
    async def test_sync_skips_already_ingested(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"]
        )
        record = make_record()
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text(
            svc._record_to_text(record, "salesforce")
        )
        pipeline["session"].existing_doc = existing
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[record])):
            with patch.object(svc, "_run_schema_discovery", new=AsyncMock()):
                result = await svc.sync_and_ingest("salesforce")
        assert result["records_processed"] == 1
        assert result["entities_extracted"] == 0

    @pytest.mark.asyncio
    async def test_sync_record_error_collected(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"]
        )
        svc._record_to_text = MagicMock(side_effect=Exception("boom"))
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[make_record()])):
            result = await svc.sync_and_ingest("salesforce")
        assert result["success"] is True
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_sync_usage_tracking_failure(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"]
        )
        pipeline["usage"].track_acu_usage = AsyncMock(side_effect=Exception("boom"))
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[make_record()])):
            with patch.object(svc, "_run_schema_discovery", new=AsyncMock()):
                result = await svc.sync_and_ingest("salesforce")
        assert result["success"] is True
        assert "usage_tracking_error" in result

    @pytest.mark.asyncio
    async def test_sync_global_failure(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"]
        )
        with patch.object(
            svc, "_fetch_integration_data", new=AsyncMock(side_effect=Exception("boom"))
        ):
            result = await svc.sync_and_ingest("salesforce")
        assert result["success"] is False
        assert "Pipeline failed" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_multi_entity_integration(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["slack"] = SyncConfiguration(integration_id="slack")
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[make_record()])):
            with patch.object(
                svc, "_process_multi_entity_extraction", new=AsyncMock(return_value=3)
            ) as me:
                with patch.object(svc, "_run_schema_discovery", new=AsyncMock()):
                    result = await svc.sync_and_ingest("slack")
        me.assert_awaited_once()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sync_short_text_skipped(self, pipeline):
        svc = pipeline["svc"]
        svc.sync_configs["salesforce"] = SyncConfiguration(
            integration_id="salesforce", entity_types=["contacts"]
        )
        svc._record_to_text = MagicMock(return_value="short")
        with patch.object(svc, "_fetch_integration_data", new=AsyncMock(return_value=[make_record("hi")])):
            result = await svc.sync_and_ingest("salesforce")
        assert result["records_processed"] == 0
        assert result["success"] is True


class TestPipelineHelpers:
    def test_extract_structured_entities(self, pipeline):
        record = {
            "id": "c1",
            "type": "contact",
            "name": "Alice",
            "email": "a@b.c",
            "company": "Acme",
            "stage": "won",
            "amount": 100,
            "subject": "Subj",
            "summary": "Sum",
        }
        entity, rel, integ = pipeline["svc"]._extract_structured_entities(record, "salesforce", "text")
        assert entity["name"] == "Alice"
        assert entity["properties"]["source"] == "salesforce"
        assert entity["properties"]["doc_id"] == "c1"
        assert rel["type"] == "synced_from"
        assert rel["to"] == "salesforce"
        assert entity["properties"]["summary"] == "Sum"

    def test_extract_structured_entities_fallback_name(self, pipeline):
        record = {"id": 42, "type": "thing"}
        entity, rel, integ = pipeline["svc"]._extract_structured_entities(record, "x", "text")
        assert entity["name"] == "thing_42"

    def test_hash_text(self, pipeline):
        h1 = IngestionPipelineService._hash_text("hello")
        h2 = IngestionPipelineService._hash_text("hello")
        h3 = IngestionPipelineService._hash_text("world")
        assert h1 == h2
        assert h1 != h3

    def test_record_doc_ingestion_new(self, pipeline):
        pipeline["svc"]._record_doc_ingestion("ws1", "d1", "text here", "src")
        added = pipeline["session"].added[0]
        assert added.doc_id == "d1"
        assert added.source == "src"
        assert pipeline["session"].committed >= 1

    def test_record_doc_ingestion_existing(self, pipeline):
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text("text here")
        pipeline["session"].existing_doc = existing
        pipeline["svc"]._record_doc_ingestion("ws1", "d1", "text here", "src")
        assert pipeline["session"].committed >= 1

    def test_record_doc_ingestion_error(self, pipeline):
        pipeline["session"].add = MagicMock(side_effect=Exception("boom"))
        pipeline["svc"]._record_doc_ingestion("ws1", "d1", "text here", "src")
        assert pipeline["session"].rolled_back >= 1

    def test_is_doc_already_ingested_false(self, pipeline):
        assert pipeline["svc"]._is_doc_already_ingested("ws1", "d1", "text") is False

    def test_is_doc_already_ingested_true(self, pipeline):
        existing = MagicMock()
        existing.content_hash = IngestionPipelineService._hash_text("text")
        pipeline["session"].existing_doc = existing
        assert pipeline["svc"]._is_doc_already_ingested("ws1", "d1", "text") is True

    def test_is_doc_already_ingested_different_hash(self, pipeline):
        existing = MagicMock()
        existing.content_hash = "different"
        pipeline["session"].existing_doc = existing
        assert pipeline["svc"]._is_doc_already_ingested("ws1", "d1", "text") is False

    def test_get_user_credentials_found(self, pipeline):
        conn = MagicMock()
        conn.id = "conn-1"
        conn.integration_id = "slack"
        conn.user_id = "u1"
        conn.expires_at = datetime.now(timezone.utc)
        pipeline["session"].user_conn = conn
        creds = pipeline["svc"]._get_user_credentials("slack", "u1")
        assert creds["connection_id"] == "conn-1"
        assert creds["token_valid_until"] is not None

    def test_get_user_credentials_not_found(self, pipeline):
        pipeline["session"].user_conn = None
        assert pipeline["svc"]._get_user_credentials("slack", "u1") is None

    def test_get_user_credentials_error(self, pipeline):
        pipeline["session"].query = MagicMock(side_effect=Exception("boom"))
        assert pipeline["svc"]._get_user_credentials("slack", "u1") is None

    def test_create_ingestion_job(self, pipeline):
        job_id = pipeline["svc"]._create_ingestion_job("slack", "manual", "conn-1")
        assert not job_id.startswith("fallback-")
        job = pipeline["session"].added[0]
        assert job.integration_id == "slack"
        assert job.trigger_type == "manual"
        assert job.source_connection_id == "conn-1"

    def test_create_ingestion_job_error(self, pipeline):
        pipeline["session"].add = MagicMock(side_effect=Exception("boom"))
        job_id = pipeline["svc"]._create_ingestion_job("slack", "manual")
        assert job_id.startswith("fallback-")

    def test_update_ingestion_job(self, pipeline):
        job = MagicMock()
        pipeline["session"].job = job
        ok = pipeline["svc"]._update_ingestion_job("job-1", "completed", records_fetched=2)
        assert ok is True
        assert job.status == "completed"
        assert job.records_fetched == 2

    def test_update_ingestion_job_not_found(self, pipeline):
        pipeline["session"].job = None
        assert pipeline["svc"]._update_ingestion_job("job-1", "completed") is False

    def test_update_ingestion_job_error(self, pipeline):
        pipeline["session"].query = MagicMock(side_effect=Exception("boom"))
        assert pipeline["svc"]._update_ingestion_job("job-1", "completed") is False

    def test_update_ingestion_job_no_model(self, pipeline, monkeypatch):
        monkeypatch.setattr(ip, "INGESTION_JOB_EXISTS", False)
        assert pipeline["svc"]._update_ingestion_job("job-1", "completed") is False

    def test_calculate_acu_consumed(self, pipeline):
        assert pipeline["svc"]._calculate_acu_consumed(2, 1000, 500) == 1.5

    def test_is_core_entity_type(self, pipeline):
        assert pipeline["svc"]._is_core_entity_type("contact") is True
        assert pipeline["svc"]._is_core_entity_type("CONTACT") is True
        assert pipeline["svc"]._is_core_entity_type("random_thing") is False


class TestPipelinePrepareText:
    @pytest.mark.asyncio
    async def test_kill_switch_disabled(self, pipeline, monkeypatch):
        monkeypatch.setenv("ENABLE_BINARY_INGESTION", "false")
        text = await pipeline["svc"]._prepare_record_text_async(
            {"id": "1", "type": "file", "name": "a.pdf", "text": "metadata text"}, "onedrive"
        )
        assert "metadata text" in text

    @pytest.mark.asyncio
    async def test_non_file_record(self, pipeline):
        text = await pipeline["svc"]._prepare_record_text_async(
            {"id": "1", "type": "message", "text": "hello there"}, "slack"
        )
        assert "hello there" in text

    @pytest.mark.asyncio
    async def test_file_legacy_flag_disabled(self, pipeline, monkeypatch):
        monkeypatch.setenv("ENABLE_ONEDRIVE_FILE_PARSING", "false")
        text = await pipeline["svc"]._prepare_record_text_async(
            {"id": "1", "type": "file", "name": "a.pdf", "text": "meta"}, "onedrive"
        )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_workdrive_flag_disabled(self, pipeline, monkeypatch):
        monkeypatch.setenv("ENABLE_WORKDRIVE_FILE_PARSING", "false")
        text = await pipeline["svc"]._prepare_record_text_async(
            {"id": "1", "type": "file", "name": "a.pdf", "text": "meta"}, "zoho_workdrive"
        )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_unsupported_extension(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = False
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.xyz", "extension": "xyz", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_no_service(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        pipeline["registry"].get_service = AsyncMock(return_value=None)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_service_no_download_method(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        service = MagicMock()
        del service.download_file
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_empty_download(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        service = MagicMock()
        service.download_file = AsyncMock(return_value=None)
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_oversize(self, pipeline, monkeypatch):
        monkeypatch.setenv("MAX_INGESTION_FILE_SIZE_MB", "1")
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        service = MagicMock()
        service.download_file = AsyncMock(return_value=b"x" * (2 * 1024 * 1024))
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_docling_failure(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        processor.process_document = AsyncMock(return_value={"success": False, "error": "parse fail"})
        service = MagicMock()
        service.download_file = AsyncMock(return_value=b"data")
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_insufficient_text(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        processor.process_document = AsyncMock(return_value={"success": True, "content": "short"})
        service = MagicMock()
        service.download_file = AsyncMock(return_value=b"data")
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_file_success(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        processor.process_document = AsyncMock(
            return_value={"success": True, "content": "Extracted document content here"}
        )
        service = MagicMock()
        service.download_file = AsyncMock(return_value=b"data")
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert text == "Extracted document content here"

    @pytest.mark.asyncio
    async def test_file_download_exception(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        service = MagicMock()
        service.download_file = AsyncMock(side_effect=Exception("boom"))
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            text = await pipeline["svc"]._prepare_record_text_async(
                {"id": "1", "type": "file", "name": "a.pdf", "extension": "pdf", "text": "meta"},
                "onedrive",
            )
        assert "meta" in text

    @pytest.mark.asyncio
    async def test_attachment_flag_disabled(self, pipeline, monkeypatch):
        monkeypatch.setenv("ENABLE_OUTLOOK_ATTACHMENT_INGESTION", "false")
        record = {
            "id": "m1",
            "type": "email",
            "hasAttachments": True,
            "subject": "Subject here",
            "body": "Body text here",
        }
        text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_nested_metadata_flag(self, pipeline, monkeypatch):
        monkeypatch.setenv("ENABLE_OUTLOOK_ATTACHMENT_INGESTION", "false")
        record = {
            "id": "m1",
            "type": "email",
            "metadata": {"hasAttachments": True},
            "subject": "Subject here",
            "body": "Body text here",
        }
        text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_no_message_id(self, pipeline):
        record = {
            "type": "email",
            "hasAttachments": True,
            "subject": "Subject here",
            "body": "Body text here",
        }
        text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_no_service(self, pipeline):
        pipeline["registry"].get_service = AsyncMock(return_value=None)
        record = {
            "id": "m1",
            "type": "email",
            "hasAttachments": True,
            "subject": "Subject here",
            "body": "Body text here",
        }
        text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_no_attachments(self, pipeline):
        service = MagicMock()
        service.config = {}
        service.get_attachment_metadata = AsyncMock(return_value=[])
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        record = {
            "id": "m1",
            "type": "email",
            "hasAttachments": True,
            "subject": "Subject here",
            "body": "Body text here",
        }
        text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_success(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        processor.process_document = AsyncMock(
            return_value={"success": True, "content": "Attachment extracted content body"}
        )
        service = MagicMock()
        service.config = {"access_token": "tok"}
        service.get_attachment_metadata = AsyncMock(
            return_value=[
                {"id": "a1", "name": "file.pdf", "size": 100, "contentType": "application/pdf"}
            ]
        )
        service.download_attachment = AsyncMock(return_value=b"bytes")
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            record = {
                "id": "m1",
                "type": "email",
                "hasAttachments": True,
                "subject": "Subject here",
                "body": "Body text here",
            }
            text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "[Attachment: file.pdf]" in text

    @pytest.mark.asyncio
    async def test_attachment_unsupported_extension_skipped(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = False
        service = MagicMock()
        service.config = {}
        service.get_attachment_metadata = AsyncMock(
            return_value=[{"id": "a1", "name": "file.xyz", "size": 100, "contentType": "x"}]
        )
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            record = {
                "id": "m1",
                "type": "email",
                "hasAttachments": True,
                "subject": "Subject here",
                "body": "Body text here",
            }
            text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_oversize(self, pipeline, monkeypatch):
        monkeypatch.setenv("MAX_OUTLOOK_ATTACHMENT_SIZE_MB", "1")
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        service = MagicMock()
        service.config = {}
        service.get_attachment_metadata = AsyncMock(
            return_value=[{"id": "a1", "name": "f.pdf", "size": 10 * 1024 * 1024, "contentType": "x"}]
        )
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            record = {
                "id": "m1",
                "type": "email",
                "hasAttachments": True,
                "subject": "Subject here",
                "body": "Body text here",
            }
            text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_download_failure(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        service = MagicMock()
        service.config = {}
        service.get_attachment_metadata = AsyncMock(
            return_value=[{"id": "a1", "name": "f.pdf", "size": 10, "contentType": "x"}]
        )
        service.download_attachment = AsyncMock(return_value=None)
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            record = {
                "id": "m1",
                "type": "email",
                "hasAttachments": True,
                "subject": "Subject here",
                "body": "Body text here",
            }
            text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_parse_failure_continues(self, pipeline):
        processor = MagicMock()
        processor.is_format_supported.return_value = True
        processor.process_document = AsyncMock(return_value={"success": False, "error": "x"})
        service = MagicMock()
        service.config = {}
        service.get_attachment_metadata = AsyncMock(
            return_value=[{"id": "a1", "name": "f.pdf", "size": 10, "contentType": "x"}]
        )
        service.download_attachment = AsyncMock(return_value=b"bytes")
        pipeline["registry"].get_service = AsyncMock(return_value=service)
        with patch.object(ip, "get_docling_processor", return_value=processor):
            record = {
                "id": "m1",
                "type": "email",
                "hasAttachments": True,
                "subject": "Subject here",
                "body": "Body text here",
            }
            text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text

    @pytest.mark.asyncio
    async def test_attachment_outer_exception(self, pipeline):
        pipeline["registry"].get_service = AsyncMock(side_effect=Exception("boom"))
        record = {
            "id": "m1",
            "type": "email",
            "hasAttachments": True,
            "subject": "Subject here",
            "body": "Body text here",
        }
        text = await pipeline["svc"]._prepare_record_text_async(record, "outlook")
        assert "Subject here" in text


class TestPipelineWebhook:
    def _setup(self, pipeline):
        pipeline["graphrag"].ingest_structured_data = MagicMock()
        pipeline["lancedb"].add_document = MagicMock(return_value=True)
        return pipeline["svc"]

    @pytest.mark.asyncio
    async def test_webhook_no_records(self, pipeline):
        svc = self._setup(pipeline)
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[])):
            result = await svc.process_webhook_payload("slack", {"type": "x"})
        assert result["success"] is True
        assert result["records_processed"] == 0

    @pytest.mark.asyncio
    async def test_webhook_success_slack(self, pipeline, capsys):
        svc = self._setup(pipeline)
        payload = {
            "team_id": "T1",
            "type": "event_callback",
            "event": {
                "type": "message",
                "client_msg_id": "msg-123",
                "text": "Hello from Slack with enough text to process",
                "channel": "C1",
                "user": "U1",
                "ts": "123.45",
            },
        }
        with patch.object(svc, "_process_multi_entity_extraction", new=AsyncMock(return_value=2)):
            result = await svc.process_webhook_payload("slack", payload)
        assert result["success"] is True
        assert result["records_processed"] == 1
        assert result["entities_extracted"] >= 1
        assert result["lancedb_indexed"] == 1
        assert result["usage_log_id"] == "usage-1"
        captured = capsys.readouterr()
        assert "[FATAL_DEBUG]" not in captured.err
        assert "msg-123" not in captured.err

    @pytest.mark.asyncio
    async def test_webhook_short_text_skipped(self, pipeline):
        svc = self._setup(pipeline)
        svc._prepare_record_text_async = AsyncMock(return_value="short")
        with patch.object(
            svc, "_transform_webhook_payload", new=AsyncMock(return_value=[{"id": "1", "type": "x", "content": "short"}])
        ):
            result = await svc.process_webhook_payload("slack", {})
        assert result["records_processed"] == 0
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_webhook_no_entities(self, pipeline):
        svc = self._setup(pipeline)
        svc._extract_structured_entities = MagicMock(return_value=(None, None))
        with patch.object(
            svc,
            "_transform_webhook_payload",
            new=AsyncMock(
                return_value=[
                    {"id": "1", "type": "slack_message", "content": "A sufficiently long text here"}
                ]
            ),
        ):
            result = await svc.process_webhook_payload("slack", {})
        assert result["success"] is True
        assert result["entities_extracted"] == 0

    @pytest.mark.asyncio
    async def test_webhook_record_error(self, pipeline):
        svc = self._setup(pipeline)
        svc._prepare_record_text_async = AsyncMock(side_effect=Exception("boom"))
        with patch.object(
            svc,
            "_transform_webhook_payload",
            new=AsyncMock(return_value=[{"id": "1", "type": "x", "content": "long enough text here"}]),
        ):
            result = await svc.process_webhook_payload("slack", {})
        assert result["success"] is True
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_webhook_transform_exception(self, pipeline):
        svc = self._setup(pipeline)
        with patch.object(
            svc, "_transform_webhook_payload", new=AsyncMock(side_effect=Exception("boom"))
        ):
            result = await svc.process_webhook_payload("slack", {})
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_webhook_lancedb_failure_does_not_fail(self, pipeline):
        svc = self._setup(pipeline)
        pipeline["lancedb"].add_document = MagicMock(side_effect=Exception("boom"))
        with patch.object(
            svc,
            "_transform_webhook_payload",
            new=AsyncMock(
                return_value=[
                    {"id": "1", "type": "slack_message", "content": "A sufficiently long text here"}
                ]
            ),
        ):
            result = await svc.process_webhook_payload("slack", {})
        assert result["success"] is True
        assert "lancedb_error" in result

    @pytest.mark.asyncio
    async def test_webhook_usage_tracking_failure(self, pipeline):
        svc = self._setup(pipeline)
        pipeline["usage"].track_acu_usage = AsyncMock(side_effect=Exception("boom"))
        with patch.object(
            svc,
            "_transform_webhook_payload",
            new=AsyncMock(
                return_value=[
                    {"id": "1", "type": "slack_message", "content": "A sufficiently long text here"}
                ]
            ),
        ):
            result = await svc.process_webhook_payload("slack", {})
        assert result["success"] is True
        assert "usage_tracking_error" in result

    @pytest.mark.asyncio
    async def test_webhook_outlook_indexing(self, pipeline):
        svc = self._setup(pipeline)
        with patch.object(
            svc,
            "_transform_webhook_payload",
            new=AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "type": "email",
                        "subject": "Subj",
                        "content": "A sufficiently long email body here",
                        "from": "a@b.c",
                        "to": "d@e.f",
                    }
                ]
            ),
        ):
            result = await svc.process_webhook_payload("outlook", {})
        assert result["success"] is True
        assert result["lancedb_indexed"] == 1
        args = pipeline["lancedb"].add_document.call_args
        assert args.kwargs["table_name"] == "atom_communications"
        assert "extract_knowledge" not in args.kwargs  # dead param removed (R84)

    @pytest.mark.asyncio
    async def test_webhook_no_source_connection(self, pipeline):
        svc = self._setup(pipeline)
        with patch.object(
            svc,
            "_transform_webhook_payload",
            new=AsyncMock(
                return_value=[
                    {"id": "1", "type": "gmail_message", "content": "A sufficiently long text here"}
                ]
            ),
        ):
            result = await svc.process_webhook_payload("gmail", {}, source_connection_id="c1")
        assert result["success"] is True


class TestPipelineTiered:
    @pytest.mark.asyncio
    async def test_tiered_no_records(self, pipeline):
        svc = pipeline["svc"]
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[])):
            result = await svc.process_webhook_payload_tiered("slack", {})
        assert result["success"] is True
        assert result["tier"] == "none"

    @pytest.mark.asyncio
    async def test_tiered_standard_basic_and_deep(self, pipeline):
        svc = pipeline["svc"]
        record = {
            "id": "r1",
            "type": "contact",
            "name": "Alice",
            "email": "a@b.c",
            "text": LONG_TEXT,
        }
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            with patch.object(
                svc, "_process_multi_entity_extraction", new=AsyncMock(return_value=1)
            ):
                result = await svc.process_webhook_payload_tiered("hubspot", {})
        assert result["success"] is True
        assert result["tier"] == "deep"
        assert result["records_processed"] == 1
        assert result["entities_extracted"] == 1
        # R84: basic tier writes the index row AND a deterministic
        # business_facts row for the same record.
        tables = [c.kwargs.get("table_name")
                  for c in pipeline["lancedb"].add_document.call_args_list]
        assert sum(1 for t in tables if t and t.startswith("tenant_")) == 1
        assert tables.count("business_facts") == 1

    @pytest.mark.asyncio
    async def test_tiered_communication_pipeline(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        fake_mod = types.ModuleType("integrations.atom_communication_ingestion_pipeline")
        fake_pipeline = MagicMock()
        fake_pipeline.ingest_message = MagicMock()
        fake_mod.get_ingestion_pipeline = lambda tenant_id: fake_pipeline
        monkeypatch.setitem(sys.modules, "integrations.atom_communication_ingestion_pipeline", fake_mod)
        record = {"id": "r1", "type": "email", "subject": "Subj", "text": LONG_TEXT}
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            result = await svc.process_webhook_payload_tiered("outlook", {})
        fake_pipeline.ingest_message.assert_called_once()
        assert result["records_processed"] == 1
        assert result["tier"] in ("basic", "deep")

    @pytest.mark.asyncio
    async def test_tiered_comm_pipeline_failure_falls_back(self, pipeline, monkeypatch):
        svc = pipeline["svc"]
        fake_mod = types.ModuleType("integrations.atom_communication_ingestion_pipeline")
        fake_pipeline = MagicMock()
        fake_pipeline.ingest_message = MagicMock(side_effect=Exception("boom"))
        fake_mod.get_ingestion_pipeline = lambda tenant_id: fake_pipeline
        monkeypatch.setitem(sys.modules, "integrations.atom_communication_ingestion_pipeline", fake_mod)
        record = {"id": "r1", "type": "email", "subject": "Subj", "text": LONG_TEXT}
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            result = await svc.process_webhook_payload_tiered("outlook", {})
        assert result["records_processed"] == 1

    @pytest.mark.asyncio
    async def test_tiered_solo_plan_llm_extraction(self, pipeline):
        svc = pipeline["svc"]
        pipeline["session"].tenant = MagicMock(plan_type="solo")
        record = {"id": "r1", "type": "contact", "name": "Alice", "text": LONG_TEXT}
        pipeline["graphrag"].ingest_document = AsyncMock()
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            result = await svc.process_webhook_payload_tiered("hubspot", {})
        assert result.get("llm_entities_extracted") == 1
        pipeline["graphrag"].ingest_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tiered_solo_llm_failure(self, pipeline):
        svc = pipeline["svc"]
        pipeline["session"].tenant = MagicMock(plan_type="solo")
        record = {"id": "r1", "type": "contact", "name": "Alice", "text": LONG_TEXT}
        pipeline["graphrag"].ingest_document = AsyncMock(side_effect=Exception("boom"))
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            result = await svc.process_webhook_payload_tiered("hubspot", {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_tiered_tenant_query_error(self, pipeline):
        svc = pipeline["svc"]
        session = pipeline["session"]

        def failing_query(model):
            if model is Tenant:
                raise Exception("boom")
            return _FakeQuery(session, model)

        session.query = failing_query
        record = {"id": "r1", "type": "contact", "name": "Alice", "text": LONG_TEXT}
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            with patch.object(
                svc, "_process_multi_entity_extraction", new=AsyncMock(return_value=0)
            ):
                result = await svc.process_webhook_payload_tiered("hubspot", {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_tiered_quota_denied_still_basic(self, pipeline):
        svc = pipeline["svc"]
        pipeline["usage"].check_quota_before_job = AsyncMock(
            return_value={"allowed": False, "remaining_quota": 0}
        )
        record = {"id": "r1", "type": "contact", "name": "Alice", "text": LONG_TEXT}
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            with patch.object(
                svc, "_process_multi_entity_extraction", new=AsyncMock(return_value=0)
            ):
                result = await svc.process_webhook_payload_tiered("hubspot", {})
        assert result["success"] is True
        assert result["records_processed"] == 1

    @pytest.mark.asyncio
    async def test_tiered_short_text_skipped(self, pipeline):
        svc = pipeline["svc"]
        svc._record_to_text = MagicMock(return_value="short")
        record = {"id": "r1", "type": "contact", "name": "Alice", "text": "short"}
        with patch.object(svc, "_transform_webhook_payload", new=AsyncMock(return_value=[record])):
            with patch.object(
                svc, "_process_multi_entity_extraction", new=AsyncMock(return_value=0)
            ):
                result = await svc.process_webhook_payload_tiered("hubspot", {})
        assert result["records_processed"] == 0
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_tiered_exception(self, pipeline):
        svc = pipeline["svc"]
        with patch.object(
            svc, "_transform_webhook_payload", new=AsyncMock(side_effect=Exception("boom"))
        ):
            result = await svc.process_webhook_payload_tiered("slack", {})
        assert result["success"] is False
        assert "error" in result
