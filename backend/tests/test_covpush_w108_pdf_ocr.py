# -*- coding: utf-8 -*-
"""Coverage wave 108 — integrations/pdf_processing/pdf_ocr_routes
(TestClient + fully mocked service/BYOK/httpx, zero LLM spend, no network).

BUGS found (RED -> GREEN):
- W108-1: /pdf/status, /pdf/process, /pdf/extract-text-only,
  /pdf/analyze-pdf-type, /pdf/health had NO auth (only /pdf/process-url did)
  -> anon requests returned 200; now 401.
- W108-2: SSRF guard in process_pdf_from_url only checked literal IPs; DNS
  names ("localhost", or names resolving to private IPs) bypassed it.
- W108-3: str(e) leaked to clients in /pdf/health byok error, in
  _get_pdf_byok_providers, and in _optimize_pdf_processing_with_byok.

All success/validation/error/exception branches covered per route.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

try:
    from backend.core.auth import get_current_user
except ImportError:
    from core.auth import get_current_user

import integrations.pdf_processing.pdf_ocr_routes as mod
from integrations.pdf_processing.pdf_ocr_routes import (
    _get_pdf_byok_providers,
    _optimize_pdf_processing_with_byok,
    router,
)

app = FastAPI()
app.include_router(router)

FAKE_USER = MagicMock()
FAKE_USER.id = "user-1"


def _make_service():
    svc = AsyncMock()
    svc.service_status = {"basic_extraction": True, "ocr": True}
    svc.ocr_readers = {"basic_extraction": MagicMock(), "tesseract": MagicMock()}
    svc.process_pdf.return_value = {
        "success": True,
        "extracted_content": {"text": "hello world", "pages": []},
        "processing_summary": {
            "total_pages": 1,
            "total_characters": 11,
            "best_method": "basic_extraction",
        },
        "processing_method": "basic_extraction",
    }
    svc._extract_basic_text.return_value = {
        "text_ratio": 0.8, "page_count": 2, "total_chars": 100,
    }
    return svc


def _make_byok_manager():
    mgr = MagicMock()
    mgr.get_provider_status.side_effect = lambda pid: (
        {"status": "active", "provider": {
            "name": "OpenAI",
            "supported_tasks": ["pdf_ocr"],
            "cost_per_token": 0.001,
        }} if pid == "openai" else {"status": "inactive", "provider": {}})
    mgr.get_optimal_provider.return_value = "openai"
    mgr.get = AsyncMock(return_value={"status": "ok"})
    return mgr


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    service = _make_service()
    with patch.object(mod, "get_pdf_service", return_value=service), \
            patch.object(mod, "BYOK_AVAILABLE", False), \
            patch.object(mod, "get_byok_manager", return_value=_make_byok_manager()):
        with TestClient(app) as c:
            c.service = service
            yield c
    app.dependency_overrides.clear()


SAMPLE_PDF = b"%PDF-1.4 fake"


# ============================================================================
# Auth: 401 for anonymous on EVERY route
# ============================================================================

class TestAuth:
    def test_all_routes_require_auth(self):
        app.dependency_overrides.clear()
        with patch.object(mod, "get_pdf_service",
                          return_value=_make_service()):
            with TestClient(app) as c:
                assert c.get("/pdf/status").status_code == 401
                assert c.get("/pdf/health").status_code == 401
                assert c.post("/pdf/process").status_code == 401
                assert c.post("/pdf/process-url",
                              data={"pdf_url": "https://example.com/x.pdf"}
                              ).status_code == 401
                assert c.post("/pdf/extract-text-only").status_code == 401
                assert c.post("/pdf/analyze-pdf-type").status_code == 401


# ============================================================================
# /status
# ============================================================================

class TestStatus:
    def test_status_without_byok(self, client):
        resp = client.get("/pdf/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "available"
        assert body["service_capabilities"] == {"basic_extraction": True,
                                                "ocr": True}
        assert list(body["available_ocr_methods"]) == ["basic_extraction",
                                                       "tesseract"]
        assert "byok_integration" not in body

    def test_status_with_byok(self, client):
        with patch.object(mod, "BYOK_AVAILABLE", True):
            resp = client.get("/pdf/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["byok_integration"]["byok_integrated"] is True
        assert body["byok_integration"]["byok_manager_available"] is True
        assert body["byok_integration"]["pdf_providers"]["total_providers"] == 1

    def test_status_error(self, client):
        class _Boom:
            ocr_readers = {}

            @property
            def service_status(self):
                raise RuntimeError("db down")

        with patch.object(mod, "get_pdf_service", return_value=_Boom()):
            resp = client.get("/pdf/status")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /process
# ============================================================================

class TestProcess:
    def _upload(self, client, filename="test.pdf", content=None,
                use_ocr="true", use_advanced_comprehension="false",
                fallback_strategy="cascade", optimize_with_byok="false"):
        return client.post(
            "/pdf/process",
            files={"file": (filename, content if content is not None else SAMPLE_PDF,
                            "application/pdf")},
            data={
                "use_ocr": use_ocr,
                "extract_images": "false",
                "use_advanced_comprehension": use_advanced_comprehension,
                "fallback_strategy": fallback_strategy,
                "optimize_with_byok": optimize_with_byok,
            },
        )

    def test_process_success(self, client):
        resp = self._upload(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["file_metadata"]["filename"] == "test.pdf"
        assert body["file_metadata"]["size_bytes"] == len(SAMPLE_PDF)
        assert body["file_metadata"]["content_type"] == "application/pdf"
        client.service.process_pdf.assert_awaited_once_with(
            pdf_data=SAMPLE_PDF, use_ocr=True, extract_images=False,
            use_advanced_comprehension=False, fallback_strategy="cascade")

    def test_process_with_byok_optimization(self, client):
        with patch.object(mod, "BYOK_AVAILABLE", True):
            resp = self._upload(client, optimize_with_byok="true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["byok_optimization"]["optimized"] is True
        assert body["byok_optimization"]["task_type"] == "pdf_ocr"
        assert body["byok_optimization"]["optimal_provider"] == "openai"

    def test_process_advanced_comprehension_task_type(self, client):
        with patch.object(mod, "BYOK_AVAILABLE", True):
            resp = self._upload(client, optimize_with_byok="true",
                                use_advanced_comprehension="true")
        assert resp.status_code == 200
        assert resp.json()["byok_optimization"]["task_type"] == "image_comprehension"

    def test_process_non_pdf_rejected(self, client):
        resp = self._upload(client, filename="notes.txt")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Only PDF files are supported"

    def test_process_empty_file(self, client):
        resp = self._upload(client, content=b"")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Uploaded file is empty"

    def test_process_service_exception(self, client):
        client.service.process_pdf.side_effect = RuntimeError("boom")
        resp = self._upload(client)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /process-url
# ============================================================================

class TestProcessUrl:
    def _call(self, client, url="https://example.com/doc.pdf", **data):
        payload = {"pdf_url": url}
        payload.update(data)
        return client.post("/pdf/process-url", data=payload)

    @patch("httpx.AsyncClient")
    def test_process_url_success(self, mock_client_cls, client):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_PDF
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_resp.raise_for_status.return_value = None
        mock_client_cls.return_value.__aenter__.return_value.get.return_value = \
            mock_resp
        resp = self._call(client, optimize_with_byok="false")
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_metadata"]["url"] == "https://example.com/doc.pdf"
        assert body["source_metadata"]["size_bytes"] == len(SAMPLE_PDF)
        client.service.process_pdf.assert_awaited_once_with(
            pdf_data=SAMPLE_PDF, use_ocr=True, extract_images=True,
            use_advanced_comprehension=False)

    @patch("httpx.AsyncClient")
    def test_process_url_with_byok(self, mock_client_cls, client):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_PDF
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_resp.raise_for_status.return_value = None
        mock_client_cls.return_value.__aenter__.return_value.get.return_value = \
            mock_resp
        with patch.object(mod, "BYOK_AVAILABLE", True):
            resp = self._call(client, optimize_with_byok="true")
        assert resp.status_code == 200
        assert resp.json()["byok_optimization"]["task_type"] == "pdf_ocr"

    def test_process_url_bad_scheme(self, client):
        resp = self._call(client, url="file:///etc/passwd")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "URL must be http or https"

    def test_process_url_private_ip(self, client):
        resp = self._call(client, url="http://10.0.0.5/x.pdf")
        assert resp.status_code == 400
        assert "private" in resp.json()["detail"]

    def test_process_url_loopback_ip(self, client):
        resp = self._call(client, url="http://127.0.0.1/x.pdf")
        assert resp.status_code == 400
        assert "private" in resp.json()["detail"]

    def test_process_url_link_local_ip(self, client):
        resp = self._call(client, url="http://169.254.1.1/x.pdf")
        assert resp.status_code == 400

    def test_process_url_reserved_ip(self, client):
        resp = self._call(client, url="http://240.0.0.1/x.pdf")
        assert resp.status_code == 400

    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 80))])
    def test_process_url_localhost_name_blocked(self, mock_gai, client):
        resp = self._call(client, url="http://localhost/x.pdf")
        assert resp.status_code == 400
        assert "private" in resp.json()["detail"]

    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.1.2.3", 80))])
    def test_process_url_dns_to_private_ip_blocked(self, mock_gai, client):
        resp = self._call(client, url="http://internal.example.com/x.pdf")
        assert resp.status_code == 400
        assert "private" in resp.json()["detail"]

    @patch("httpx.AsyncClient")
    def test_process_url_public_dns_allowed(self, mock_client_cls, client):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_PDF
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_resp.raise_for_status.return_value = None
        mock_client_cls.return_value.__aenter__.return_value.get.return_value = \
            mock_resp
        with patch("socket.getaddrinfo",
                   return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
            resp = self._call(client, url="http://example.com/x.pdf")
        assert resp.status_code == 200

    @patch("httpx.AsyncClient")
    def test_process_url_unresolvable_hostname_proceeds(self, mock_client_cls, client):
        import socket
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_PDF
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_resp.raise_for_status.return_value = None
        mock_client_cls.return_value.__aenter__.return_value.get.return_value = \
            mock_resp
        with patch("socket.getaddrinfo",
                   side_effect=socket.gaierror("no such host")):
            resp = self._call(client, url="http://no-such-host.invalid/x.pdf")
        assert resp.status_code == 200

    @patch("httpx.AsyncClient")
    def test_process_url_not_a_pdf(self, mock_client_cls, client):
        mock_resp = MagicMock()
        mock_resp.content = b"<html>"
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.raise_for_status.return_value = None
        mock_client_cls.return_value.__aenter__.return_value.get.return_value = \
            mock_resp
        resp = self._call(client)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "URL does not point to a PDF file"

    @patch("httpx.AsyncClient")
    def test_process_url_http_error(self, mock_client_cls, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("boom")
        mock_client_cls.return_value.__aenter__.return_value.get.return_value = \
            mock_resp
        import httpx
        with patch("httpx.AsyncClient", side_effect=httpx.HTTPError("down")):
            resp = self._call(client)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Internal error"

    @patch("httpx.AsyncClient")
    def test_process_url_service_exception(self, mock_client_cls, client):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_PDF
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_resp.raise_for_status.return_value = None
        mock_client_cls.return_value.__aenter__.return_value.get.return_value = \
            mock_resp
        client.service.process_pdf.side_effect = RuntimeError("boom")
        resp = self._call(client)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /extract-text-only
# ============================================================================

class TestExtractTextOnly:
    def _call(self, client, filename="test.pdf", content=SAMPLE_PDF):
        return client.post(
            "/pdf/extract-text-only",
            files={"file": (filename, content, "application/pdf")},
        )

    def test_success(self, client):
        resp = self._call(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["extracted_text"] == "hello world"
        assert body["page_count"] == 1
        assert body["total_characters"] == 11
        assert body["method_used"] == "basic_extraction"
        assert body["filename"] == "test.pdf"
        client.service.process_pdf.assert_awaited_once_with(
            pdf_data=SAMPLE_PDF, use_ocr=False, extract_images=False,
            use_advanced_comprehension=False)

    def test_non_pdf_rejected(self, client):
        resp = self._call(client, filename="x.txt")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Only PDF files are supported"

    def test_service_exception(self, client):
        client.service.process_pdf.side_effect = RuntimeError("boom")
        resp = self._call(client)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"

    def test_missing_fields_in_result(self, client):
        client.service.process_pdf.return_value = {"success": True}
        resp = self._call(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["extracted_text"] == ""
        assert body["page_count"] == 0
        assert body["method_used"] == "unknown"


# ============================================================================
# /analyze-pdf-type
# ============================================================================

class TestAnalyzePdfType:
    def _call(self, client, filename="test.pdf", ratio=None):
        svc = client.service
        if ratio is not None:
            svc._extract_basic_text.return_value = {
                "text_ratio": ratio, "page_count": 3, "total_chars": 50}
        return client.post(
            "/pdf/analyze-pdf-type",
            files={"file": (filename, SAMPLE_PDF, "application/pdf")},
        )

    def test_searchable(self, client):
        resp = self._call(client, ratio=0.8)
        assert resp.status_code == 200
        body = resp.json()
        assert body["pdf_type"] == "searchable"
        assert body["confidence"] == "high"
        assert body["recommended_processing"]["needs_ocr"] is False
        assert body["recommended_processing"]["suggested_methods"] == ["basic_extraction"]

    def test_mostly_searchable(self, client):
        resp = self._call(client, ratio=0.3)
        body = resp.json()
        assert body["pdf_type"] == "mostly_searchable"
        assert body["confidence"] == "medium"
        assert body["recommended_processing"]["needs_ocr"] is True
        assert body["recommended_processing"]["suggested_methods"] == ["ocr_processing"]

    def test_scanned(self, client):
        resp = self._call(client, ratio=0.05)
        body = resp.json()
        assert body["pdf_type"] == "scanned_or_image_based"
        assert body["confidence"] == "high"
        assert body["recommended_processing"]["needs_ocr"] is True
        assert body["total_pages"] == 3
        assert body["total_characters"] == 50

    def test_non_pdf_rejected(self, client):
        resp = self._call(client, filename="x.txt")
        assert resp.status_code == 400

    def test_service_exception(self, client):
        client.service._extract_basic_text.side_effect = RuntimeError("boom")
        resp = self._call(client)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /health
# ============================================================================

class TestHealth:
    def test_health_ok_without_byok(self, client):
        resp = client.get("/pdf/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["basic_functionality"] is True
        assert "byok_integration" not in body

    def test_health_with_byok_connected(self, client):
        with patch.object(mod, "BYOK_AVAILABLE", True):
            resp = client.get("/pdf/health")
        assert resp.status_code == 200
        assert resp.json()["byok_integration"]["status"] == "connected"

    def test_health_with_byok_disconnected(self, client):
        mgr = _make_byok_manager()
        mgr.get.side_effect = RuntimeError("byok down")
        with patch.object(mod, "BYOK_AVAILABLE", True), \
                patch.object(mod, "get_byok_manager", return_value=mgr):
            resp = client.get("/pdf/health")
        assert resp.status_code == 200
        assert resp.json()["byok_integration"]["status"] == "disconnected"
        assert "byok down" not in json.dumps(resp.json())

    def test_health_service_error(self, client):
        client.service.process_pdf.side_effect = RuntimeError("boom")
        resp = client.get("/pdf/health")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# get_pdf_service factory
# ============================================================================

class TestGetPdfService:
    def test_lazy_init_and_cache(self):
        fake_cls = MagicMock()
        fake_cls.return_value = MagicMock()
        with patch.object(mod, "_pdf_service", None), \
                patch.object(mod, "PDFOCRService", fake_cls):
            svc = mod.get_pdf_service()
            assert svc is fake_cls.return_value
            assert mod._pdf_service is svc
            assert mod.get_pdf_service() is svc
            fake_cls.assert_called_once()
            args, kwargs = fake_cls.call_args
            assert kwargs["tesseract_path"] is None
            assert kwargs["easyocr_languages"] == ["en"]

    def test_returns_cached_when_set(self):
        existing = MagicMock()
        with patch.object(mod, "_pdf_service", existing), \
                patch.object(mod, "PDFOCRService") as fake_cls:
            assert mod.get_pdf_service() is existing
            fake_cls.assert_not_called()


# ============================================================================
# BYOK helper functions
# ============================================================================

class TestGetPdfByokProviders:
    async def test_active_providers_collected(self):
        mgr = MagicMock()
        statuses = {
            "openai": {"status": "active", "provider": {
                "name": "OpenAI", "supported_tasks": ["pdf_ocr"],
                "cost_per_token": 0.001}},
            "google_gemini": {"status": "inactive", "provider": {}},
            "anthropic": {"status": "active", "provider": {
                "name": "Anthropic", "supported_tasks": ["pdf_ocr"],
                "cost_per_token": 0.002}},
            "azure_openai": {"status": "active", "provider": {
                "name": "Azure", "supported_tasks": ["pdf_ocr"],
                "cost_per_token": 0.003}},
        }
        mgr.get_provider_status.side_effect = lambda pid: statuses[pid]
        result = await _get_pdf_byok_providers(mgr)
        assert result["total_providers"] == 3
        assert {p["provider_id"] for p in result["pdf_providers"]} == {
            "openai", "anthropic", "azure_openai"}

    async def test_provider_status_exception_skipped(self):
        mgr = MagicMock()
        mgr.get_provider_status.side_effect = [
            {"status": "active", "provider": {
                "name": "OpenAI", "supported_tasks": [], "cost_per_token": 0}},
            RuntimeError("boom"),
            {"status": "active", "provider": {
                "name": "Anthropic", "supported_tasks": [], "cost_per_token": 0}},
            {"status": "active", "provider": {
                "name": "Azure", "supported_tasks": [], "cost_per_token": 0}},
        ]
        result = await _get_pdf_byok_providers(mgr)
        assert result["total_providers"] == 3

    async def test_no_active_providers(self):
        mgr = MagicMock()
        mgr.get_provider_status.return_value = {"status": "inactive",
                                                "provider": {}}
        result = await _get_pdf_byok_providers(mgr)
        assert result == {"pdf_providers": [], "total_providers": 0}

    async def test_outer_exception_generic_error(self):
        mgr = MagicMock()
        mgr.get_provider_status.side_effect = RuntimeError("boom")
        with patch.object(mod.logger, "error"):
            result = await _get_pdf_byok_providers(mgr)
        assert result["total_providers"] == 0
        assert "boom" not in json.dumps(result)


class TestOptimizePdfProcessingWithByok:
    async def test_advanced_comprehension(self):
        mgr = _make_byok_manager()
        result = await _optimize_pdf_processing_with_byok(
            mgr, use_advanced_comprehension=True, use_ocr=True)
        assert result["task_type"] == "image_comprehension"
        assert result["optimized"] is True
        assert result["optimal_provider"] == "openai"
        assert result["provider_name"] == "OpenAI"

    async def test_pdf_ocr_task(self):
        mgr = _make_byok_manager()
        result = await _optimize_pdf_processing_with_byok(
            mgr, use_advanced_comprehension=False, use_ocr=True)
        assert result["task_type"] == "pdf_ocr"

    async def test_document_processing_task(self):
        mgr = _make_byok_manager()
        result = await _optimize_pdf_processing_with_byok(
            mgr, use_advanced_comprehension=False, use_ocr=False)
        assert result["task_type"] == "document_processing"

    async def test_no_optimal_provider(self):
        mgr = _make_byok_manager()
        mgr.get_optimal_provider.return_value = None
        result = await _optimize_pdf_processing_with_byok(
            mgr, use_advanced_comprehension=False, use_ocr=True)
        assert result["optimized"] is False
        assert "No suitable providers" in result["reason"]

    async def test_exception_generic_error(self):
        mgr = _make_byok_manager()
        mgr.get_optimal_provider.side_effect = RuntimeError("boom")
        with patch.object(mod.logger, "error"):
            result = await _optimize_pdf_processing_with_byok(
                mgr, use_advanced_comprehension=False, use_ocr=True)
        assert result["optimized"] is False
        assert result["task_type"] == "unknown"
        assert "boom" not in json.dumps(result)
