"""Coverage wave 39 — core/hybrid_data_ingestion.py edge branches (TDD).

Closes the remaining branches: __init__ ImportError fallbacks, universal
adapter discovery schema-extraction variants (notion/airtable/jira/zoho),
legacy zoho fallback, and the OneDrive/Google Drive content-ingestion
tolerance paths — no network, zero spend.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.hybrid_data_ingestion import (
    HybridDataIngestionService,
    SyncConfiguration,
)


def make_config(entity_types=None, **kw):
    defaults = dict(integration_id="x", entity_types=entity_types or ["records"],
                    sync_last_n_days=30, max_records_per_sync=1000)
    defaults.update(kw)
    return SyncConfiguration(**defaults)


class TestInitFallbacks:
    def test_lancedb_import_error(self):
        with patch("core.lancedb_handler.get_lancedb_handler",
                   side_effect=ImportError("no lancedb")), \
             patch("core.graphrag_engine.GraphRAGEngine",
                   return_value=MagicMock()), \
             patch("core.llm_service.get_llm_service",
                   return_value=MagicMock()):
            svc = HybridDataIngestionService()
        assert svc.memory_handler is None
        assert svc.graphrag is not None

    def test_graphrag_import_error(self):
        with patch("core.lancedb_handler.get_lancedb_handler",
                   return_value=MagicMock()), \
             patch("core.graphrag_engine.GraphRAGEngine",
                   side_effect=ImportError("no graphrag")), \
             patch("core.llm_service.get_llm_service",
                   return_value=MagicMock()):
            svc = HybridDataIngestionService()
        assert svc.graphrag is None
        assert svc.memory_handler is not None

    def test_llm_import_error(self):
        with patch("core.lancedb_handler.get_lancedb_handler",
                   return_value=MagicMock()), \
             patch("core.graphrag_engine.GraphRAGEngine",
                   return_value=MagicMock()), \
             patch("core.llm_service.get_llm_service",
                   side_effect=ImportError("no llm")):
            svc = HybridDataIngestionService()
        assert svc.llm is None


class TestDiscoveryVariants:
    async def test_notion_airtable_jira_zoho_variants(self):
        for integration_id, schema, expected in [
            ("notion", {"id": "page-1"}, "page-1"),
            ("airtable", {"base_id": "b1", "id": "tbl-1"}, "b1:tbl-1"),
            ("jira", {"project_key": "PROJ", "issue_type": "bug"}, "PROJ:bug"),
            ("zoho", {"api_name": "Leads"}, "Leads"),
            ("zoho_crm", {"api_name": "Deals"}, "Deals"),
        ]:
            svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
            svc.workspace_id = "default"
            adapter = MagicMock()
            adapter.ensure_token = AsyncMock()
            adapter.get_available_schemas = AsyncMock(
                return_value=[schema])
            adapter.fetch_records = AsyncMock(return_value={"results": []})
            db = MagicMock()
            db.close = MagicMock()
            factory = MagicMock()
            factory.get_hubspot_adapter.return_value = adapter
            factory.get_notion_adapter.return_value = adapter
            factory.get_airtable_adapter.return_value = adapter
            factory.get_jira_adapter.return_value = adapter
            factory.get_zoho_adapter.return_value = adapter
            with patch("core.database.SessionLocal", return_value=db), \
                 patch("core.service_factory.ServiceFactory", factory):
                records = await svc._fetch_universal_adapter_data(
                    integration_id,
                    make_config(integration_id=integration_id,
                                entity_types=["base"]),
                    discovery_mode=True)
            assert records == []
            called_types = [c.kwargs["entity_type"] for c in adapter.fetch_records.call_args_list]
            assert expected in called_types

    async def test_legacy_zoho_fallback(self):
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        adapter = MagicMock()
        adapter.ensure_token = AsyncMock()
        del adapter.fetch_records
        db = MagicMock()
        db.close = MagicMock()
        factory = MagicMock()
        factory.get_zoho_adapter.return_value = adapter
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.service_factory.ServiceFactory", factory), \
             patch.object(svc, "_fetch_zoho_multi_app_data",
                          new=AsyncMock(return_value=[{"id": "z1"}])) as zoho:
            records = await svc._fetch_universal_adapter_data(
                "zoho_crm", make_config(integration_id="zoho_crm"))
        assert records == [{"id": "z1"}]
        zoho.assert_called_once()


class TestCloudDriveContentEdges:
    async def test_onedrive_download_failure_tolerated(self):
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = "default"
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"value": [{"id": "f1", "name": "a.docx"}]}})
        service.download_file_bytes = AsyncMock(side_effect=RuntimeError("dl failed"))
        ingestor = MagicMock()
        ingestor.process_file_bytes = AsyncMock()
        with patch("integrations.onedrive_service.OneDriveService",
                   return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   return_value=ingestor):
            records = await svc._fetch_onedrive_data(make_config(integration_id="onedrive"))
        assert len(records) == 1  # file entity still recorded
        ingestor.process_file_bytes.assert_not_called()

    async def test_onedrive_ingestor_unavailable(self):
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = "default"
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"value": [{"id": "f1", "name": "a.pdf"}]}})
        with patch("integrations.onedrive_service.OneDriveService",
                   return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   side_effect=RuntimeError("no ingestor")):
            records = await svc._fetch_onedrive_data(make_config(integration_id="onedrive"))
        assert len(records) == 1

    async def test_google_drive_content_error_tolerated(self):
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = "default"
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"files": [{"id": "g1", "name": "doc.pdf",
                                "mimeType": "application/pdf"}]}})
        service.download_file_bytes = AsyncMock(side_effect=RuntimeError("dl failed"))
        ingestor = MagicMock()
        ingestor.process_file_bytes = AsyncMock()
        with patch("integrations.google_drive_service.GoogleDriveService",
                   return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   return_value=ingestor):
            records = await svc._fetch_google_drive_data(make_config(integration_id="google_drive"))
        assert len(records) == 1
        ingestor.process_file_bytes.assert_not_called()

    async def test_google_drive_ingestor_unavailable(self):
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = "default"
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="tok")
        service.list_files = AsyncMock(return_value={
            "status": "success",
            "data": {"files": [{"id": "g1", "name": "doc.pdf",
                                "mimeType": "application/pdf"}]}})
        with patch("integrations.google_drive_service.GoogleDriveService",
                   return_value=service), \
             patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   side_effect=RuntimeError("no ingestor")):
            records = await svc._fetch_google_drive_data(make_config(integration_id="google_drive"))
        assert len(records) == 1

    async def test_google_drive_fetch_error(self):
        svc = HybridDataIngestionService.__new__(HybridDataIngestionService)
        svc.workspace_id = "default"
        svc.tenant_id = "default"
        service = MagicMock()
        service.get_access_token = AsyncMock(side_effect=RuntimeError("oauth down"))
        with patch("integrations.google_drive_service.GoogleDriveService",
                   return_value=service):
            records = await svc._fetch_google_drive_data(make_config(integration_id="google_drive"))
        assert records == []
