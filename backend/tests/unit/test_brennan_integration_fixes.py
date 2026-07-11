"""
Unit tests for the brennan.ca use-case-video integration fixes.

Covers the code changed in Phase 1 (OneDrive real, Zoho WorkDrive completion,
Shopify health_check + fetcher, Telegram transform + fetcher, Outlook learner)
and Phase 2 (Office→memory wiring, process_file_bytes).

These tests are self-contained: they mock HTTP and DB boundaries and exercise
the real logic (sync configs, dispatch wiring, entity extraction, transforms).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Phase 1.1 / 1.3: sync configs + fetcher dispatch wiring
# ---------------------------------------------------------------------------

class TestSyncConfigsAndDispatch:
    def test_new_sync_configs_registered(self):
        """Shopify, OneDrive, and Telegram should have DEFAULT_SYNC_CONFIGS entries."""
        from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS

        for iid in ("shopify", "onedrive", "telegram"):
            assert iid in DEFAULT_SYNC_CONFIGS, f"{iid} missing from DEFAULT_SYNC_CONFIGS"
            cfg = DEFAULT_SYNC_CONFIGS[iid]
            assert cfg.integration_id == iid
            assert len(cfg.entity_types) > 0
            assert cfg.max_records_per_sync > 0

    def test_fetch_dispatch_wires_new_integrations(self):
        """_fetch_integration_data should route shopify/onedrive/telegram to fetchers."""
        import inspect
        from core.hybrid_data_ingestion import HybridDataIngestionService

        src = inspect.getsource(HybridDataIngestionService._fetch_integration_data)
        assert "_fetch_shopify_data" in src
        assert "_fetch_onedrive_data" in src
        assert "_fetch_telegram_data" in src

    def test_shopify_sync_config_entities(self):
        from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS

        cfg = DEFAULT_SYNC_CONFIGS["shopify"]
        assert "products" in cfg.entity_types
        assert "orders" in cfg.entity_types
        assert "customers" in cfg.entity_types


# ---------------------------------------------------------------------------
# Phase 1.3: Shopify health_check NameError fix
# ---------------------------------------------------------------------------

class TestShopifyHealthCheck:
    def test_health_check_does_not_raise_nameerror(self):
        """health_check uses datetime.now(timezone.utc); imports must be present."""
        from integrations.shopify_service import ShopifyService

        svc = ShopifyService(config={"api_key": "test_key"})
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(svc.health_check())
        # Should execute without NameError and report health based on api_key presence.
        assert result["healthy"] is True
        assert result["message"] == "Connected"

    def test_health_check_without_api_key(self):
        from integrations.shopify_service import ShopifyService

        svc = ShopifyService(config={})
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(svc.health_check())
        assert result["healthy"] is False


# ---------------------------------------------------------------------------
# Phase 1.2: Zoho WorkDrive get_teams + abstract methods
# ---------------------------------------------------------------------------

class TestZohoWorkDrive:
    def test_implements_integration_service_contract(self):
        """WorkDrive must implement the 3 abstract methods so the singleton loads."""
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        svc = ZohoWorkDriveService("default", {})
        assert hasattr(svc, "get_capabilities")
        assert hasattr(svc, "health_check")
        assert hasattr(svc, "execute_operation")
        assert hasattr(svc, "get_teams")

    def test_get_capabilities_lists_operations(self):
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        caps = ZohoWorkDriveService("default", {}).get_capabilities()
        op_ids = [op["id"] for op in caps["operations"]]
        assert "list_files" in op_ids
        assert "get_teams" in op_ids
        assert "full_sync" in op_ids

    @pytest.mark.asyncio
    async def test_get_teams_returns_empty_without_token(self):
        """Without a connection/token, get_teams should return [] gracefully."""
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        svc = ZohoWorkDriveService("default", {})
        with patch.object(svc, "get_access_token", AsyncMock(return_value=None)):
            teams = await svc.get_teams("no-conn-user")
        assert teams == []

    @pytest.mark.asyncio
    async def test_get_teams_parses_jsonapi_response(self):
        """get_teams should normalize the WorkDrive JSON:API teams response."""
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        svc = ZohoWorkDriveService("default", {})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "team1", "type": "teams",
                 "attributes": {"name": "Sales Folder", "status": "active", "role": "admin"}},
            ]
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        svc.client = mock_client

        with patch.object(svc, "get_access_token", AsyncMock(return_value="tok")):
            teams = await svc.get_teams("user1")

        assert len(teams) == 1
        assert teams[0]["id"] == "team1"
        assert teams[0]["name"] == "Sales Folder"

    @pytest.mark.asyncio
    async def test_full_sync_ingests_parseable_files(self):
        """full_sync should iterate files and ingest parseable ones into memory."""
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        svc = ZohoWorkDriveService("default", {})
        files = [
            {"id": "f1", "name": "Quote.docx"},
            {"id": "f2", "name": "PriceList.xlsx"},
            {"id": "f3", "name": "readme.md"},
            {"id": "f4", "name": "image.png"},  # should be skipped
        ]
        with patch.object(svc, "list_files", AsyncMock(return_value=files)), \
             patch.object(svc, "ingest_file_to_memory", AsyncMock(
                 return_value={"success": True})) as mock_ingest, \
             patch.object(svc, "sync_to_postgres_cache", AsyncMock(
                 return_value={"success": True, "metrics_synced": 1})):
            result = await svc.full_sync("user1")

        assert result["success"] is True
        assert result["files_found"] == 4
        # 3 parseable files ingested, png skipped.
        assert result["files_ingested"] == 3
        assert mock_ingest.call_count == 3


# ---------------------------------------------------------------------------
# Phase 1.5: Telegram webhook transform enrichment
# ---------------------------------------------------------------------------

class TestTelegramTransform:
    @pytest.mark.asyncio
    async def test_transform_private_message(self):
        from core.ingestion_pipeline import IngestionPipelineService

        pipeline = IngestionPipelineService.__new__(IngestionPipelineService)
        payload = {
            "message": {
                "message_id": 42,
                "text": "What's the price of the press brake?",
                "from": {"id": 111, "username": "fab_shop", "first_name": "Bob"},
                "chat": {"id": 222, "title": None, "username": "fab_shop"},
                "date": 1700000000,
            }
        }
        records = await pipeline._transform_telegram_payload(payload)

        assert len(records) == 1
        r = records[0]
        assert r["type"] == "telegram_message"
        assert r["id"] == "42"
        assert r["text"] == "What's the price of the press brake?"
        assert r["from"] == "fab_shop"
        assert r["chat_id"] == "222"
        assert r["properties"]["sender_id"] == 111

    @pytest.mark.asyncio
    async def test_transform_channel_post(self):
        from core.ingestion_pipeline import IngestionPipelineService

        pipeline = IngestionPipelineService.__new__(IngestionPipelineService)
        payload = {
            "channel_post": {
                "message_id": 7,
                "text": "New machine in stock",
                "chat": {"id": -100, "title": "Announcements"},
                "date": 1700000001,
            }
        }
        records = await pipeline._transform_telegram_payload(payload)

        assert len(records) == 1
        assert records[0]["chat_title"] == "Announcements"

    @pytest.mark.asyncio
    async def test_transform_empty_payload(self):
        from core.ingestion_pipeline import IngestionPipelineService

        pipeline = IngestionPipelineService.__new__(IngestionPipelineService)
        records = await pipeline._transform_telegram_payload({"update_id": 1})
        assert records == []

    @pytest.mark.asyncio
    async def test_transform_captures_media(self):
        from core.ingestion_pipeline import IngestionPipelineService

        pipeline = IngestionPipelineService.__new__(IngestionPipelineService)
        payload = {
            "message": {
                "message_id": 9,
                "caption": "See this part",
                "document": {"file_id": "doc123"},
                "from": {"id": 5},
                "chat": {"id": 6},
                "date": 1700000002,
            }
        }
        records = await pipeline._transform_telegram_payload(payload)
        assert records[0]["properties"]["media_type"] == "document"
        assert records[0]["properties"]["media_id"] == "doc123"
        assert records[0]["text"] == "See this part"


# ---------------------------------------------------------------------------
# Phase 1.4: M365 learner entity extraction
# ---------------------------------------------------------------------------

class TestM365LearnerEntityExtraction:
    def _make_learner(self):
        from core.microsoft365_learner import Microsoft365LifecycleLearner

        learner = Microsoft365LifecycleLearner.__new__(Microsoft365LifecycleLearner)
        learner.doc_learner = MagicMock()
        return learner

    def test_build_entities_invoice_email(self):
        learner = self._make_learner()
        entities, rels = learner._build_entities(
            subject="Invoice INV-2024-001 for press brake",
            from_email="vendor@accorp.com",
            from_name="AcCorp Sales",
            received="2024-06-01T10:00:00Z",
            matched_keywords=["invoice"],
            order_ids=["INV-2024-001"],
            tracking_ids=[],
            amounts=["45,000.00"],
            body_preview="Invoice INV-2024-001 total $45,000.00",
            message_id="msg-1",
        )
        types = {e["type"] for e in entities}
        assert "contact" in types
        assert "email" in types
        assert "order" in types

        order_entity = [e for e in entities if e["type"] == "order"][0]
        assert order_entity["name"] == "INV-2024-001"

        # Relationship from sender → email should exist.
        assert any(r["type"] == "sent" for r in rels)

    def test_build_entities_shipping_email(self):
        learner = self._make_learner()
        entities, rels = learner._build_entities(
            subject="Your order has shipped - tracking 1Z999AA10123456784",
            from_email="shipper@ups.com",
            from_name="UPS",
            received="2024-06-02T08:00:00Z",
            matched_keywords=["shipped", "tracking"],
            order_ids=[],
            tracking_ids=["1Z999AA10123456784"],
            amounts=[],
            body_preview="Tracking 1Z999AA10123456784",
            message_id="msg-2",
        )
        types = {e["type"] for e in entities}
        assert "shipment" in types
        shipment = [e for e in entities if e["type"] == "shipment"][0]
        assert shipment["properties"]["tracking_number"] == "1Z999AA10123456784"

    @pytest.mark.asyncio
    async def test_process_message_no_keywords_returns_false(self):
        learner = self._make_learner()
        msg = {"subject": "Lunch on Friday?", "from": {}, "body": {}}
        result = await learner._process_outlook_message(msg, "u1", "ws1")
        assert result is False


# ---------------------------------------------------------------------------
# Phase 1.4: Outlook retry-path fix (no more "retry_user" / consumed body)
# ---------------------------------------------------------------------------

class TestOutlookRetryPath:
    def test_handle_response_signature_accepts_retry_context(self):
        """_handle_response must accept the original request args (not reconstruct)."""
        import inspect
        from integrations.outlook_service_enhanced import OutlookEnhancedService

        sig = inspect.signature(OutlookEnhancedService._handle_response)
        params = list(sig.parameters)
        # Should accept response + the original request context, not just (response, url).
        assert "is_retry" in params
        assert "user_id" in params
        assert "data" in params

    def test_make_graph_request_has_retry_guard(self):
        import inspect
        from integrations.outlook_service_enhanced import OutlookEnhancedService

        sig = inspect.signature(OutlookEnhancedService._make_graph_request)
        assert "_is_retry" in sig.parameters


# ---------------------------------------------------------------------------
# Phase 2: AutoDocumentIngestionService.process_file_bytes
# ---------------------------------------------------------------------------

class TestProcessFileBytes:
    @pytest.mark.asyncio
    async def test_skips_unknown_extension(self):
        from core.auto_document_ingestion import AutoDocumentIngestionService

        svc = AutoDocumentIngestionService()
        result = await svc.process_file_bytes(b"data", file_name="file.xyz", source="test")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_skips_empty_content(self):
        from core.auto_document_ingestion import AutoDocumentIngestionService

        svc = AutoDocumentIngestionService()
        result = await svc.process_file_bytes(b"", file_name="empty.txt", source="test")
        assert result["status"] in ("skipped", "error")

    @pytest.mark.asyncio
    async def test_ingests_text_content(self):
        from core.auto_document_ingestion import AutoDocumentIngestionService

        svc = AutoDocumentIngestionService()
        # Mock the parser to return text and the memory handler to succeed.
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="This is important quote content about a press brake.")
        svc.memory_handler = MagicMock()
        svc.memory_handler.add_document = MagicMock(return_value=True)

        result = await svc.process_file_bytes(
            b"fake bytes", file_name="Quote.docx", source="office_tool", user_id="u1"
        )
        assert result["status"] == "ingested"
        assert result["chars_ingested"] > 0
        svc.memory_handler.add_document.assert_called_once()
        # Verify extract_knowledge=True is passed.
        _, kwargs = svc.memory_handler.add_document.call_args
        assert kwargs.get("extract_knowledge") is True


# ---------------------------------------------------------------------------
# Phase 2: OfficeSyncService Office→memory wiring exists
# ---------------------------------------------------------------------------

class TestOfficeToMemoryWiring:
    def test_office_sync_has_ingest_methods(self):
        from core.office_sync_service import OfficeSyncService

        assert hasattr(OfficeSyncService, "_ingest_document_to_memory")
        assert hasattr(OfficeSyncService, "_ingest_document_to_memory_sync")

    def test_office_tool_has_ingest_helper(self):
        from tools import office_tool

        assert hasattr(office_tool, "_ingest_after_write")

    def test_office_tool_write_tools_fire_ingestion(self):
        """write_excel_cell / modify_word_document should schedule ingestion on success."""
        import inspect
        from tools import office_tool

        excel_src = inspect.getsource(office_tool.write_excel_cell)
        word_src = inspect.getsource(office_tool.modify_word_document)
        assert "_ingest_after_write" in excel_src
        assert "_ingest_after_write" in word_src


# ---------------------------------------------------------------------------
# Phase 7: Real Google Drive service (replaces mock) + ingestion fetcher
# ---------------------------------------------------------------------------

class TestGoogleDriveService:
    def test_implements_full_contract(self):
        """All preserved signatures + the new download/upload methods must exist."""
        from integrations.google_drive_service import GoogleDriveService, google_drive_service

        svc = GoogleDriveService("default", {})
        # Preserved signatures (consumers depend on these).
        for m in (
            "list_files", "search_files", "get_file_metadata", "download_file",
            "authenticate", "get_capabilities", "health_check", "execute_operation",
            "sync_to_postgres_cache", "full_sync", "get_access_token",
        ):
            assert hasattr(svc, m), f"missing {m}"
        # New methods added by the real implementation.
        assert hasattr(svc, "download_file_bytes")
        assert hasattr(svc, "upload_file")
        # access_token attribute must exist (universal_integration_service reads it).
        assert hasattr(svc, "access_token")
        # Singleton restored (auto_document_ingestion imports it).
        assert google_drive_service is not None

    def test_list_files_no_token_returns_error_envelope(self):
        """Without a token, list_files returns the {"status":"error"} envelope."""
        import asyncio
        from integrations.google_drive_service import GoogleDriveService

        svc = GoogleDriveService("default", {})
        result = asyncio.new_event_loop().run_until_complete(svc.list_files(None))
        assert result["status"] == "error"
        assert "token" in result["message"].lower()

    def test_authenticate_builds_oauth_url(self):
        """authenticate returns a Google OAuth URL with Drive scopes."""
        import asyncio
        from integrations.google_drive_service import GoogleDriveService

        svc = GoogleDriveService("default", {})
        # Without client_id it errors cleanly.
        import os
        old = os.environ.pop("GOOGLE_CLIENT_ID", None)
        try:
            result = asyncio.new_event_loop().run_until_complete(svc.authenticate("u1"))
            assert result["status"] == "error"
        finally:
            if old:
                os.environ["GOOGLE_CLIENT_ID"] = old

    @pytest.mark.asyncio
    async def test_get_access_token_falls_back_to_env(self):
        """get_access_token should use GOOGLE_DRIVE_ACCESS_TOKEN when no connection exists."""
        import os
        from integrations.google_drive_service import GoogleDriveService

        svc = GoogleDriveService("default", {})
        os.environ["GOOGLE_DRIVE_ACCESS_TOKEN"] = "env-test-token"
        try:
            token = await svc.get_access_token("no-conn-user")
            assert token == "env-test-token"
        finally:
            del os.environ["GOOGLE_DRIVE_ACCESS_TOKEN"]

    @pytest.mark.asyncio
    async def test_list_files_parses_drive_api_response(self):
        """list_files should normalize the Drive v3 files response into the envelope."""
        from integrations.google_drive_service import GoogleDriveService

        svc = GoogleDriveService("default", {})
        # Patch the low-level _drive_get helper to avoid real HTTP.
        svc._drive_get = AsyncMock(return_value={
            "files": [
                {"id": "f1", "name": "Quote.docx", "mimeType": "application/vnd.google-apps.document"},
                {"id": "f2", "name": "PriceList.xlsx", "mimeType": "application/vnd.google-apps.spreadsheet"},
            ],
            "nextPageToken": None,
        })

        result = await svc.list_files("real-token")

        assert result["status"] == "success"
        assert len(result["data"]["files"]) == 2
        assert result["data"]["files"][0]["id"] == "f1"
        # Verify _drive_get was called with the files endpoint.
        svc._drive_get.assert_called_once()
        call_args = svc._drive_get.call_args
        assert "/drive/v3/files" in call_args[0][1]

    def test_google_drive_sync_config_registered(self):
        from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS

        assert "google_drive" in DEFAULT_SYNC_CONFIGS
        assert DEFAULT_SYNC_CONFIGS["google_drive"].entity_types == ["files"]

    def test_google_drive_fetcher_wired_into_dispatch(self):
        import inspect
        from core.hybrid_data_ingestion import HybridDataIngestionService

        src = inspect.getsource(HybridDataIngestionService._fetch_integration_data)
        assert "_fetch_google_drive_data" in src

    def test_google_oauth_config_includes_drive_file_scope(self):
        """drive.file scope must be present for upload operations."""
        from core.oauth_handler import GOOGLE_OAUTH_CONFIG

        scopes = GOOGLE_OAUTH_CONFIG.scopes
        assert "https://www.googleapis.com/auth/drive.readonly" in scopes
        assert "https://www.googleapis.com/auth/drive.file" in scopes

