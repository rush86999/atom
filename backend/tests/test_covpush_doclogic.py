"""
Coverage-push tests: integrations.document_logic_service + integrations.ecommerce_unified_service.

TDD: bug tests written RED first (missing awaits, singleton misconfig, str(e) leaks),
then minimal fixes applied in the modules.
"""

import logging

import pytest
from unittest.mock import AsyncMock

import integrations.document_logic_service as dls_mod
import integrations.ecommerce_unified_service as ecom_mod
from integrations.document_logic_service import DocumentLogicService, DocumentType
from integrations.ecommerce_unified_service import EcommercePlatform, EcommerceUnifiedService


@pytest.fixture
def doc_logic():
    return DocumentLogicService()


class TestDocumentLogicInit:
    def test_default_config(self):
        svc = DocumentLogicService()
        assert svc.config == {}
        assert svc.tenant_id == "default"

    def test_custom_config(self):
        svc = DocumentLogicService(tenant_id="t1", config={"k": "v"})
        assert svc.tenant_id == "t1"
        assert svc.config == {"k": "v"}

    def test_document_type_enum(self):
        assert DocumentType.GOOGLE_DOC.value == "google_doc"
        assert DocumentType.MS_WORD.value == "docx"
        assert DocumentType.MS_EXCEL.value == "xlsx"
        assert DocumentType.PDF.value == "pdf"
        assert DocumentType.CSV.value == "csv"


class TestIngestDocument:
    async def test_ingest_awaits_pipeline(self, doc_logic, monkeypatch):
        mock_ingest = AsyncMock(return_value=True)
        monkeypatch.setattr(dls_mod.atom_ingestion_pipeline, "ingest_record", mock_ingest)
        result = await doc_logic.ingest_document("/tmp/doc.pdf", DocumentType.PDF, "ws1")
        assert result == {"snippets_extracted": 1}
        mock_ingest.assert_awaited_once()
        kwargs = mock_ingest.call_args.kwargs
        assert kwargs["app_type"] == "pdf"
        assert kwargs["record_type"] == "document"
        assert kwargs["data"]["file_path"] == "/tmp/doc.pdf"
        assert kwargs["data"]["workspace_id"] == "ws1"
        assert kwargs["data"]["logic_snippet"] == "orders_over_500_require_cfo_approval"

    async def test_ingest_pipeline_unavailable(self, doc_logic, monkeypatch):
        monkeypatch.setattr(dls_mod, "atom_ingestion_pipeline", None)
        result = await doc_logic.ingest_document("/tmp/doc.pdf", DocumentType.PDF, "ws1")
        assert result == {"snippets_extracted": 1, "ingestion": "disabled"}


class TestExtractText:
    def test_extract_text_placeholder(self, doc_logic):
        content = doc_logic._extract_text("ignored.pdf", DocumentType.PDF)
        assert content == "Example business rule: All orders over $500 require CFO approval."

    async def test_extract_logic_with_ai(self, doc_logic):
        snippets = await doc_logic._extract_logic_with_ai("some content")
        assert snippets == ["orders_over_500_require_cfo_approval"]


class TestCapabilitiesAndHealth:
    def test_get_capabilities(self, doc_logic):
        caps = doc_logic.get_capabilities()
        assert [op["id"] for op in caps["operations"]] == [
            "parse_document", "extract_text", "classify_document", "merge_documents",
        ]
        assert caps["rate_limits"] == {"requests_per_minute": 50, "max_file_size_mb": 50}
        assert caps["supports_webhooks"] is False

    def test_health_check(self, doc_logic):
        health = doc_logic.health_check()
        assert health["healthy"] is True
        assert health["message"] == "Document Logic service is operational"
        assert health["tenant_id"] == "default"


class TestExecuteOperation:
    async def test_tenant_mismatch_denied(self):
        svc = DocumentLogicService(tenant_id="t1")
        result = await svc.execute_operation(
            "parse_document", {"file_path": "f"}, context={"tenant_id": "other"}
        )
        assert result == {
            "success": False,
            "error": "Tenant validation failed",
            "details": {"tenant_mismatch": True},
        }

    async def test_parse_document_dispatch(self, doc_logic, monkeypatch):
        captured = {}

        async def fake_parse(params):
            captured["params"] = params
            return {"success": True, "result": {"snippets_extracted": 1}}

        monkeypatch.setattr(doc_logic, "_parse_document", fake_parse)
        result = await doc_logic.execute_operation(
            "parse_document", {"file_path": "f", "doc_type": "pdf", "workspace_id": "w"}
        )
        assert result["success"] is True
        assert captured["params"]["workspace_id"] == "w"

    async def test_extract_text_dispatch(self, doc_logic, monkeypatch):
        monkeypatch.setattr(doc_logic, "_extract_text_operation",
                            lambda params: {"success": True, "result": {}})
        result = await doc_logic.execute_operation(
            "extract_text", {"file_path": "f", "doc_type": "pdf"}
        )
        assert result["success"] is True

    async def test_classify_document_dispatch(self, doc_logic, monkeypatch):
        async def fake_classify(params):
            return {"success": True, "result": {"classification": "legal"}}

        monkeypatch.setattr(doc_logic, "_classify_document", fake_classify)
        result = await doc_logic.execute_operation("classify_document", {"content": "x"})
        assert result["result"]["classification"] == "legal"

    async def test_merge_documents_dispatch(self, doc_logic, monkeypatch):
        async def fake_merge(params):
            return {"success": True, "result": {"merged_file": "m.pdf"}}

        monkeypatch.setattr(doc_logic, "_merge_documents", fake_merge)
        result = await doc_logic.execute_operation("merge_documents", {"file_paths": ["a", "b"]})
        assert result["result"]["merged_file"] == "m.pdf"

    async def test_unknown_operation(self, doc_logic):
        result = await doc_logic.execute_operation("delete_everything", {})
        assert result["success"] is False
        assert result["error"] == "Unknown operation: delete_everything"
        assert "parse_document" in result["details"]["available_operations"]

    async def test_internal_error_is_generic(self, doc_logic, monkeypatch):
        async def boom(params):
            raise RuntimeError("secret internal detail")

        monkeypatch.setattr(doc_logic, "_parse_document", boom)
        result = await doc_logic.execute_operation(
            "parse_document", {"file_path": "f", "doc_type": "pdf", "workspace_id": "w"}
        )
        assert result["success"] is False
        assert result["details"]["operation"] == "parse_document"
        assert "secret internal detail" not in result["error"]
        assert result["error"]


class TestParseDocument:
    async def test_missing_params(self, doc_logic):
        result = await doc_logic._parse_document({"file_path": "", "doc_type": ""})
        assert result["success"] is False
        assert result["error"] == "file_path and doc_type are required"

        result = await doc_logic._parse_document({"file_path": "f", "doc_type": None})
        assert result["success"] is False
        assert result["error"] == "file_path and doc_type are required"

    async def test_invalid_doc_type(self, doc_logic):
        result = await doc_logic._parse_document({"file_path": "f", "doc_type": "exe"})
        assert result["success"] is False
        assert result["error"] == "Invalid document type: exe"
        assert result["details"]["valid_types"] == [dt.value for dt in DocumentType]

    async def test_success(self, doc_logic, monkeypatch):
        async def fake_ingest(file_path, doc_type, workspace_id):
            assert doc_type == DocumentType.MS_WORD
            return {"snippets_extracted": 2}

        monkeypatch.setattr(doc_logic, "ingest_document", fake_ingest)
        result = await doc_logic._parse_document(
            {"file_path": "f.docx", "doc_type": "docx", "workspace_id": "w"}
        )
        assert result["success"] is True
        assert result["result"] == {"snippets_extracted": 2}
        assert result["details"] == {"file_path": "f.docx", "doc_type": "docx"}

    async def test_internal_error_is_generic(self, doc_logic, monkeypatch):
        async def boom(file_path, doc_type, workspace_id):
            raise RuntimeError("db exploded")

        monkeypatch.setattr(doc_logic, "ingest_document", boom)
        result = await doc_logic._parse_document(
            {"file_path": "f", "doc_type": "pdf", "workspace_id": "w"}
        )
        assert result["success"] is False
        assert result["details"] == {"file_path": "f"}
        assert "db exploded" not in result["error"]
        assert result["error"]


class TestExtractTextOperation:
    async def test_missing_params(self, doc_logic):
        result = doc_logic._extract_text_operation({"file_path": "", "doc_type": ""})
        assert result["success"] is False
        assert result["error"] == "file_path and doc_type are required"

    async def test_invalid_doc_type(self, doc_logic):
        result = doc_logic._extract_text_operation({"file_path": "f", "doc_type": "exe"})
        assert result["success"] is False
        assert result["error"] == "Invalid document type: exe"
        assert result["details"] == {}

    async def test_success(self, doc_logic):
        result = doc_logic._extract_text_operation({"file_path": "f.pdf", "doc_type": "pdf"})
        assert result["success"] is True
        assert result["result"]["file_path"] == "f.pdf"
        assert "CFO approval" in result["result"]["content"]

    async def test_internal_error_is_generic(self, doc_logic, monkeypatch):
        def boom(file_path, doc_type):
            raise OSError("permission denied on /etc")

        monkeypatch.setattr(doc_logic, "_extract_text", boom)
        result = doc_logic._extract_text_operation({"file_path": "f", "doc_type": "pdf"})
        assert result["success"] is False
        assert result["details"] == {"file_path": "f"}
        assert "/etc" not in result["error"]
        assert result["error"]


class TestClassifyDocument:
    async def test_missing_content(self, doc_logic):
        result = await doc_logic._classify_document({"content": None})
        assert result == {"success": False, "error": "content is required", "details": {}}

    async def test_financial_keywords(self, doc_logic):
        result = await doc_logic._classify_document(
            {"content": "INVOICE #12: outstanding payment of $500"}
        )
        assert result["result"]["classification"] == "financial"

    async def test_legal_keywords(self, doc_logic):
        result = await doc_logic._classify_document({"content": "This contract is an agreement"})
        assert result["result"]["classification"] == "legal"

    async def test_policy_keywords(self, doc_logic):
        result = await doc_logic._classify_document({"content": "Company Policy handbook"})
        assert result["result"]["classification"] == "policy"

    async def test_general(self, doc_logic):
        result = await doc_logic._classify_document({"content": "Weekly status notes"})
        assert result["result"]["classification"] == "general"
        assert result["result"]["confidence"] == 0.8
        assert result["details"]["content_length"] == 19


class TestMergeDocuments:
    async def test_missing_file_paths(self, doc_logic):
        result = await doc_logic._merge_documents({"file_paths": []})
        assert result == {"success": False, "error": "file_paths is required", "details": {}}

    async def test_success_default_format(self, doc_logic):
        result = await doc_logic._merge_documents({"file_paths": ["a.pdf", "b.pdf"]})
        assert result["success"] is True
        assert result["result"]["merged_file"] == "merged_document.pdf"
        assert result["result"]["source_count"] == 2
        assert result["result"]["output_format"] == "pdf"

    async def test_success_custom_format(self, doc_logic):
        result = await doc_logic._merge_documents(
            {"file_paths": ["a.docx"], "output_format": "docx"}
        )
        assert result["result"]["output_format"] == "docx"
        assert result["details"]["file_paths"] == ["a.docx"]


class TestEcommerceInit:
    def test_default_config(self):
        svc = EcommerceUnifiedService()
        assert svc.config == {}
        assert svc.tenant_id == "default"

    def test_custom_config(self):
        svc = EcommerceUnifiedService(tenant_id="t9", config={"api_key": "k"})
        assert svc.tenant_id == "t9"
        assert svc.config == {"api_key": "k"}

    def test_singleton_is_well_configured(self):
        from integrations.ecommerce_unified_service import ecommerce_service
        assert isinstance(ecommerce_service, EcommerceUnifiedService)
        assert ecommerce_service.config == {}
        assert ecommerce_service.tenant_id == "default"


class TestSyncOrders:
    async def test_sync_orders_awaits_pipeline(self, monkeypatch):
        mock_ingest = AsyncMock(return_value=True)
        monkeypatch.setattr(ecom_mod.atom_ingestion_pipeline, "ingest_record", mock_ingest)
        svc = EcommerceUnifiedService(tenant_id="t1")
        orders = await svc.sync_orders(EcommercePlatform.SHOPIFY)
        assert orders[0]["id"] == "shopify_ord_999"
        mock_ingest.assert_awaited_once()
        kwargs = mock_ingest.call_args.kwargs
        assert kwargs["app_type"] == "shopify"
        assert kwargs["record_type"] == "deal"
        assert kwargs["data"]["email"] == "customer@example.com"

    async def test_sync_orders_amazon(self, monkeypatch):
        mock_ingest = AsyncMock(return_value=True)
        monkeypatch.setattr(ecom_mod.atom_ingestion_pipeline, "ingest_record", mock_ingest)
        orders = await EcommerceUnifiedService().sync_orders(EcommercePlatform.AMAZON)
        assert orders[0]["id"] == "amazon_ord_999"

    async def test_sync_orders_pipeline_unavailable_graceful(self, monkeypatch):
        monkeypatch.setattr(ecom_mod, "atom_ingestion_pipeline", None)
        result = await EcommerceUnifiedService().sync_orders(EcommercePlatform.ETSY)
        assert result == {"success": False, "error": "Ingestion pipeline unavailable", "details": {}}


class TestUpdateInventory:
    async def test_all_platforms(self, caplog):
        svc = EcommerceUnifiedService()
        with caplog.at_level(logging.INFO):
            result = await svc.update_inventory("SKU-1", 5)
        assert result is None
        for p in EcommercePlatform:
            assert f"Updating {p.value} inventory for SKU-1 to 5" in caplog.text

    async def test_single_platform(self, caplog):
        svc = EcommerceUnifiedService()
        with caplog.at_level(logging.INFO):
            await svc.update_inventory("SKU-1", 3, platform=EcommercePlatform.ETSY)
        assert "Updating etsy inventory for SKU-1 to 3" in caplog.text
        assert "amazon" not in caplog.text
