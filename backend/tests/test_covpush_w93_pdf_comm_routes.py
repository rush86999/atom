# -*- coding: utf-8 -*-
"""Coverage wave 93 — pdf memory/ocr routes, communication memory API,
Zoom OAuth handler, workflow UI endpoints.

No network / no LLM / no real DB: every external boundary (LanceDB handlers,
OCR service, BYOK managers, httpx, aiohttp, websocket manager, orchestrator)
is mocked. Plain pytest + unittest.mock with FastAPI TestClient and
dependency_overrides for get_current_user / service providers.
"""
from __future__ import annotations

import asyncio
import json
import socket
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user

USER = SimpleNamespace(id="u1", email="u1@example.com", tenant_id="t1")


# ============================================================================
# 1. integrations/pdf_processing/pdf_memory_routes.py
# ============================================================================
import integrations.pdf_processing.pdf_memory_routes as pmr
from integrations.pdf_processing.pdf_memory_routes import (
    get_pdf_memory_service,
    router as pmr_router,
)

PM_APP = FastAPI()
PM_APP.include_router(pmr_router)


def pm_service(**overrides):
    svc = AsyncMock()
    svc.lancedb_handler = MagicMock()
    svc.table_name = "pdf_documents"
    svc.store_processed_pdf.return_value = {"success": True, "doc_id": "d1"}
    svc.search_pdfs.return_value = [{"doc_id": "d1", "score": 0.9}]
    svc.get_document.return_value = {"doc_id": "d1", "text": "hello"}
    svc.delete_document.return_value = {"success": True}
    svc.get_user_document_stats.return_value = {"total_documents": 3}
    svc.list_documents.return_value = {
        "success": True, "limit": 50, "offset": 0,
        "total": 1, "documents": [{"doc_id": "d1"}],
    }
    svc.update_document_tags.return_value = {
        "success": True, "tags": ["a"], "message": "ok"}
    svc.get_document_tags.return_value = {"success": True, "tags": ["a"], "count": 1}
    svc.delete_document_tags.return_value = {
        "success": True, "deleted_tags": ["a"], "deleted_count": 1,
        "remaining_tags": [], "message": "ok"}
    svc.search_by_tags.return_value = {
        "success": True, "count": 1, "documents": [{"doc_id": "d1"}]}
    for k, v in overrides.items():
        setattr(svc, k, v)
    return svc


@pytest.fixture()
def pm_client():
    service = pm_service()
    PM_APP.dependency_overrides[pmr.get_current_user] = lambda: USER
    PM_APP.dependency_overrides[get_pdf_memory_service] = lambda: service
    with TestClient(PM_APP, raise_server_exceptions=False) as c:
        c.service = service
        yield c
    PM_APP.dependency_overrides.clear()


class TestPdfMemoryRoutes:
    def test_get_pdf_memory_service_lazy_init(self):
        pmr._pdf_memory_service = None
        with patch.object(pmr, "get_lancedb_handler", return_value=MagicMock()) as gl:
            svc = get_pdf_memory_service()
            assert gl.called
        assert get_pdf_memory_service() is svc  # cached
        pmr._pdf_memory_service = None

    def test_status_and_health(self, pm_client):
        r = pm_client.get("/pdf-memory/status")
        assert r.status_code == 200 and r.json()["status"] == "available"
        r = pm_client.get("/pdf-memory/health")
        assert r.status_code == 200 and r.json()["status"] == "healthy"

    def test_store_success_and_failure(self, pm_client):
        body = {"processing_result": {"text": "hi"}, "metadata": {"m": 1}}
        r = pm_client.post("/pdf-memory/store", params={"user_id": "u1"},
                           json=body)
        assert r.status_code == 200 and r.json()["success"] is True
        pm_client.service.store_processed_pdf.return_value = {"success": False, "error": "x"}
        assert pm_client.post("/pdf-memory/store", params={"user_id": "u1"},
                              json=body).status_code == 500

    def test_store_validation_and_error(self, pm_client):
        body = {"processing_result": {"text": "hi"}, "metadata": None}
        assert pm_client.post("/pdf-memory/store", params={"user_id": ""},
                              json=body).status_code == 400
        pm_client.service.store_processed_pdf.side_effect = RuntimeError("boom")
        assert pm_client.post("/pdf-memory/store", params={"user_id": "u1"},
                              json=body).status_code == 500

    def test_search_paths(self, pm_client):
        c = pm_client
        assert c.get("/pdf-memory/search", params={"user_id": "u1", "query": "q"}).status_code == 200
        assert c.get("/pdf-memory/search", params={"user_id": "", "query": "q"}).status_code == 400
        assert c.get("/pdf-memory/search", params={"user_id": "u1", "query": "  "}).status_code == 400
        assert c.get("/pdf-memory/search", params={
            "user_id": "u1", "query": "q", "pdf_type": "bogus"}).status_code == 400
        r = c.get("/pdf-memory/search", params={
            "user_id": "u1", "query": "q", "pdf_type": "scanned", "tags": ["a", "b"]})
        assert r.status_code == 200 and r.json()["results_count"] == 1
        c.service.search_pdfs.side_effect = RuntimeError("boom")
        assert c.get("/pdf-memory/search", params={"user_id": "u1", "query": "q"}).status_code == 500

    def test_get_document_paths(self, pm_client):
        c = pm_client
        assert c.get("/pdf-memory/documents/d1", params={"user_id": "u1"}).status_code == 200
        c.service.get_document.return_value = None
        assert c.get("/pdf-memory/documents/d1", params={"user_id": "u1"}).status_code == 404
        c.service.get_document.side_effect = RuntimeError("boom")
        assert c.get("/pdf-memory/documents/d1", params={"user_id": "u1"}).status_code == 500

    def test_delete_document_paths(self, pm_client):
        c = pm_client
        assert c.delete("/pdf-memory/documents/d1", params={"user_id": "u1"}).status_code == 200
        c.service.delete_document.return_value = {"success": False, "error": "x"}
        assert c.delete("/pdf-memory/documents/d1", params={"user_id": "u1"}).status_code == 500
        c.service.delete_document.side_effect = RuntimeError("boom")
        assert c.delete("/pdf-memory/documents/d1", params={"user_id": "u1"}).status_code == 500

    def test_stats_and_list_documents(self, pm_client):
        c = pm_client
        r = c.get("/pdf-memory/users/u1/stats")
        assert r.status_code == 200 and r.json()["statistics"]["total_documents"] == 3
        r = c.get("/pdf-memory/users/u1/documents",
                  params={"tags": "a, b", "pdf_type": "searchable",
                          "date_from": "2026-01-01", "date_to": "2026-02-01"})
        assert r.status_code == 200 and r.json()["documents"][0]["doc_id"] == "d1"
        c.service.list_documents.return_value = {"success": False, "error": "x"}
        assert c.get("/pdf-memory/users/u1/documents").status_code == 500
        c.service.list_documents.side_effect = RuntimeError("boom")
        assert c.get("/pdf-memory/users/u1/documents").status_code == 500

    def test_update_tags_paths(self, pm_client):
        c = pm_client
        r = c.post("/pdf-memory/documents/d1/tags", params={"user_id": "u1"},
                   json=["a", "b"])
        assert r.status_code == 200 and r.json()["tags"] == ["a"]
        c.service.update_document_tags.return_value = {"success": False, "error": "Doc not found"}
        assert c.post("/pdf-memory/documents/d1/tags", params={"user_id": "u1"},
                      json=["a"]).status_code == 404
        c.service.update_document_tags.return_value = {"success": False, "error": "boom"}
        assert c.post("/pdf-memory/documents/d1/tags", params={"user_id": "u1"},
                      json=["a"]).status_code == 500
        c.service.update_document_tags.side_effect = RuntimeError("boom")
        assert c.post("/pdf-memory/documents/d1/tags", params={"user_id": "u1"},
                      json=["a"]).status_code == 500

    def test_get_tags_paths(self, pm_client):
        c = pm_client
        assert c.get("/pdf-memory/documents/d1/tags", params={"user_id": "u1"}).status_code == 200
        c.service.get_document_tags.return_value = {"success": False, "error": "not found"}
        assert c.get("/pdf-memory/documents/d1/tags", params={"user_id": "u1"}).status_code == 404
        c.service.get_document_tags.return_value = {"success": False, "error": "boom"}
        assert c.get("/pdf-memory/documents/d1/tags", params={"user_id": "u1"}).status_code == 500
        c.service.get_document_tags.side_effect = RuntimeError("boom")
        assert c.get("/pdf-memory/documents/d1/tags", params={"user_id": "u1"}).status_code == 500

    def test_delete_tags_paths(self, pm_client):
        c = pm_client
        r = c.request("DELETE", "/pdf-memory/documents/d1/tags",
                      params={"user_id": "u1"}, json=["a"])
        assert r.status_code == 200 and r.json()["deleted_count"] == 1
        assert c.request("DELETE", "/pdf-memory/documents/d1/tags",
                         params={"user_id": "u1"}, json=[]).status_code == 400
        c.service.delete_document_tags.return_value = {"success": False, "error": "not found"}
        assert c.request("DELETE", "/pdf-memory/documents/d1/tags",
                         params={"user_id": "u1"}, json=["a"]).status_code == 404
        c.service.delete_document_tags.return_value = {"success": False, "error": "boom"}
        assert c.request("DELETE", "/pdf-memory/documents/d1/tags",
                         params={"user_id": "u1"}, json=["a"]).status_code == 500

    def test_search_by_tags(self, pm_client):
        c = pm_client
        r = c.get("/pdf-memory/users/u1/documents/search", params={"tags": "a,b"})
        assert r.status_code == 200 and r.json()["count"] == 1
        assert c.get("/pdf-memory/users/u1/documents/search",
                     params={"tags": " , ,"}).status_code == 400
        c.service.search_by_tags.return_value = {"success": False, "error": "x"}
        assert c.get("/pdf-memory/users/u1/documents/search",
                     params={"tags": "a"}).status_code == 500
        c.service.search_by_tags.side_effect = RuntimeError("boom")
        assert c.get("/pdf-memory/users/u1/documents/search",
                     params={"tags": "a"}).status_code == 500


# ============================================================================
# 2. integrations/pdf_processing/pdf_ocr_routes.py
# ============================================================================
import integrations.pdf_processing.pdf_ocr_routes as por
from integrations.pdf_processing.pdf_ocr_routes import (
    _get_pdf_byok_providers,
    _optimize_pdf_processing_with_byok,
    get_byok_manager_dependency,
    router as por_router,
)

POR_APP = FastAPI()
POR_APP.include_router(por_router)
SAMPLE_PDF = b"%PDF-1.4 fake"


def por_service():
    svc = AsyncMock()
    svc.service_status = {"basic_extraction": True}
    svc.ocr_readers = {"basic_extraction": MagicMock()}
    svc.process_pdf.return_value = {
        "success": True,
        "extracted_content": {"text": "hello"},
        "processing_summary": {"total_pages": 1, "total_characters": 5,
                               "best_method": "basic_extraction"},
    }
    svc._extract_basic_text.return_value = {"text_ratio": 0.8, "page_count": 2,
                                            "total_chars": 100}
    return svc


def por_byok():
    mgr = MagicMock()
    mgr.get_provider_status.side_effect = lambda pid: (
        {"status": "active", "provider": {"name": "OpenAI",
                                          "supported_tasks": ["pdf_ocr"],
                                          "cost_per_token": 0.001}}
        if pid == "openai" else {"status": "inactive", "provider": {}})
    mgr.get_optimal_provider.return_value = "openai"
    mgr.get = AsyncMock(return_value={"status": "ok"})
    return mgr


@pytest.fixture()
def por_client():
    service = por_service()
    POR_APP.dependency_overrides[por.get_current_user] = lambda: USER
    with patch.object(por, "get_pdf_service", return_value=service), \
         patch.object(por, "BYOK_AVAILABLE", False), \
         patch.object(por, "get_byok_manager", return_value=por_byok()):
        with TestClient(POR_APP, raise_server_exceptions=False) as c:
            c.service = service
            yield c
    POR_APP.dependency_overrides.clear()


def _fake_httpx_response(content=SAMPLE_PDF, ctype="application/pdf"):
    resp = MagicMock()
    resp.content = content
    resp.headers = {"content-type": ctype}
    resp.raise_for_status.return_value = None
    return resp


class TestPdfOcrRoutes:
    def test_byok_manager_dependency_branches(self):
        with patch.object(por, "BYOK_AVAILABLE", False):
            assert get_byok_manager_dependency() is None
        with patch.object(por, "BYOK_AVAILABLE", True), \
             patch.object(por, "get_byok_manager", return_value="mgr") as gm:
            assert get_byok_manager_dependency() == "mgr"
            gm.assert_called_once()

    def test_status_with_and_without_byok(self, por_client):
        r = por_client.get("/pdf/status")
        assert r.status_code == 200 and "byok_integration" not in r.json()
        with patch.object(por, "BYOK_AVAILABLE", True):
            r = por_client.get("/pdf/status")
        assert r.json()["byok_integration"]["pdf_providers"]["total_providers"] == 1

    def test_status_error(self, por_client):
        class Boom:
            ocr_readers = {}
            @property
            def service_status(self):
                raise RuntimeError("x")
        with patch.object(por, "get_pdf_service", return_value=Boom()):
            assert por_client.get("/pdf/status").status_code == 500

    def _upload(self, c, filename="test.pdf", content=SAMPLE_PDF, **data):
        payload = {"use_ocr": "true", "extract_images": "false",
                   "use_advanced_comprehension": "false",
                   "fallback_strategy": "cascade", "optimize_with_byok": "false"}
        payload.update(data)
        return c.post("/pdf/process", files={"file": (filename, content,
                                                      "application/pdf")},
                      data=payload)

    def test_process_success(self, por_client):
        r = self._upload(por_client)
        assert r.status_code == 200 and r.json()["file_metadata"]["filename"] == "test.pdf"

    def test_process_byok_task_types(self, por_client):
        with patch.object(por, "BYOK_AVAILABLE", True):
            r = self._upload(por_client, optimize_with_byok="true")
            assert r.json()["byok_optimization"]["task_type"] == "pdf_ocr"
            r = self._upload(por_client, optimize_with_byok="true",
                             use_advanced_comprehension="true")
            assert r.json()["byok_optimization"]["task_type"] == "image_comprehension"

    def test_process_validation_and_error(self, por_client):
        assert self._upload(por_client, filename="x.txt").status_code == 400
        assert self._upload(por_client, content=b"").status_code == 400
        por_client.service.process_pdf.side_effect = RuntimeError("boom")
        assert self._upload(por_client).status_code == 500

    @patch("httpx.AsyncClient")
    def test_process_url_success_and_byok(self, mc, por_client):
        mc.return_value.__aenter__.return_value.get.return_value = _fake_httpx_response()
        r = por_client.post("/pdf/process-url",
                            data={"pdf_url": "https://93.184.216.34/doc.pdf",
                                  "optimize_with_byok": "false"})
        assert r.status_code == 200 and r.json()["source_metadata"]["url"].endswith("doc.pdf")
        with patch.object(por, "BYOK_AVAILABLE", True):
            r = por_client.post("/pdf/process-url",
                                data={"pdf_url": "https://93.184.216.34/doc.pdf",
                                      "optimize_with_byok": "true"})
            assert r.json()["byok_optimization"]["task_type"] == "pdf_ocr"

    @patch("httpx.AsyncClient")
    def test_process_url_failures(self, mc, por_client):
        c = por_client
        assert c.post("/pdf/process-url", data={"pdf_url": "file:///x"}).status_code == 400
        assert c.post("/pdf/process-url", data={"pdf_url": "https://10.0.0.5/x.pdf"}).status_code == 400
        with patch.object(socket, "getaddrinfo",
                          return_value=[(0, 0, 0, "", ("192.168.1.5", 443))]):
            assert c.post("/pdf/process-url",
                          data={"pdf_url": "https://internal.host/x.pdf"}).status_code == 400
        mc.return_value.__aenter__.return_value.get.return_value = _fake_httpx_response(
            ctype="text/html")
        assert c.post("/pdf/process-url",
                      data={"pdf_url": "https://93.184.216.34/doc.pdf",
                            "optimize_with_byok": "false"}).status_code == 400
        import httpx
        with patch("httpx.AsyncClient", side_effect=httpx.HTTPError("down")):
            assert c.post("/pdf/process-url",
                          data={"pdf_url": "https://93.184.216.34/doc.pdf"}).status_code == 400

    def test_extract_text_only(self, por_client):
        files = {"file": ("t.pdf", SAMPLE_PDF, "application/pdf")}
        r = por_client.post("/pdf/extract-text-only", files=files)
        assert r.status_code == 200 and r.json()["extracted_text"] == "hello"
        files = {"file": ("t.txt", b"x", "text/plain")}
        assert por_client.post("/pdf/extract-text-only", files=files).status_code == 400
        por_client.service.process_pdf.side_effect = RuntimeError("boom")
        files = {"file": ("t.pdf", SAMPLE_PDF, "application/pdf")}
        assert por_client.post("/pdf/extract-text-only", files=files).status_code == 500

    @pytest.mark.parametrize("ratio,pdf_type", [
        (0.8, "searchable"), (0.3, "mostly_searchable"), (0.01, "scanned_or_image_based")])
    def test_analyze_pdf_type(self, ratio, pdf_type, por_client):
        por_client.service._extract_basic_text.return_value = {
            "text_ratio": ratio, "page_count": 2, "total_chars": 10}
        files = {"file": ("t.pdf", SAMPLE_PDF, "application/pdf")}
        r = por_client.post("/pdf/analyze-pdf-type", files=files)
        assert r.status_code == 200 and r.json()["pdf_type"] == pdf_type

    def test_analyze_pdf_type_errors(self, por_client):
        files = {"file": ("t.txt", b"x", "text/plain")}
        assert por_client.post("/pdf/analyze-pdf-type", files=files).status_code == 400
        por_client.service._extract_basic_text.side_effect = RuntimeError("boom")
        files = {"file": ("t.pdf", SAMPLE_PDF, "application/pdf")}
        assert por_client.post("/pdf/analyze-pdf-type", files=files).status_code == 500

    def test_health(self, por_client):
        r = por_client.get("/pdf/health")
        assert r.status_code == 200 and r.json()["status"] == "healthy"
        with patch.object(por, "BYOK_AVAILABLE", True):
            r = por_client.get("/pdf/health")
        assert r.json()["byok_integration"]["status"] == "connected"
        with patch.object(por, "BYOK_AVAILABLE", True), \
             patch.object(por, "get_byok_manager") as gm:
            gm.return_value.get = AsyncMock(side_effect=RuntimeError("x"))
            r = por_client.get("/pdf/health")
        assert r.json()["byok_integration"]["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_get_pdf_byok_providers(self):
        out = await _get_pdf_byok_providers(por_byok())
        assert out["total_providers"] == 1
        mgr = MagicMock()
        mgr.get_provider_status.side_effect = RuntimeError("x")
        out = await _get_pdf_byok_providers(mgr)
        assert out["total_providers"] == 0

    @pytest.mark.asyncio
    async def test_optimize_pdf_processing_with_byok(self):
        mgr = por_byok()
        out = await _optimize_pdf_processing_with_byok(mgr, True, False)
        assert out["task_type"] == "image_comprehension" and out["optimized"] is True
        out = await _optimize_pdf_processing_with_byok(mgr, False, False)
        assert out["task_type"] == "document_processing"
        mgr.get_optimal_provider.return_value = None
        out = await _optimize_pdf_processing_with_byok(mgr, False, True)
        assert out["optimized"] is False and "reason" in out
        mgr.get_optimal_provider.side_effect = RuntimeError("x")
        out = await _optimize_pdf_processing_with_byok(mgr, False, True)
        assert out["optimized"] is False and "error" in out


# ============================================================================
# 3. integrations/atom_communication_memory_api.py
# ============================================================================
from integrations import atom_communication_memory_api as cma

COMM_APP = FastAPI()
COMM_APP.include_router(cma.atom_memory_router)


@pytest.fixture()
def comm_client():
    COMM_APP.dependency_overrides[get_current_user] = lambda: USER
    with TestClient(COMM_APP, raise_server_exceptions=False) as c:
        yield c
    COMM_APP.dependency_overrides.clear()


def _mm(records=None):
    mm = MagicMock()
    mm.db = MagicMock()  # already initialized
    mm.db_path = "/tmp/lance"
    mm.db.table_names.return_value = ["connections"]
    if records is None:
        mm.connections_table = None
    else:
        df = MagicMock()
        df.__len__.return_value = len(records)
        df.to_dict.return_value = records
        df.__getitem__.return_value.value_counts.return_value.to_dict.return_value = {
            "slack": len(records)}
        mm.connections_table = MagicMock()
        mm.connections_table.to_pandas.return_value = df
    return mm


def _ip(stats=None, configs=None):
    ip = MagicMock()
    ip.get_ingestion_stats.return_value = stats or {
        "configured_apps": ["slack"], "active_streams": ["s1"], "total_messages": 5}
    ip.ingestion_configs = configs if configs is not None else {
        "slack": {"enabled": True, "real_time": True, "batch_size": 10,
                  "ingest_attachments": True, "embed_content": True}}
    ip.ingest_message = AsyncMock(return_value=True)
    return ip


class TestCommunicationMemoryApi:
    def test_status(self, comm_client):
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            r = comm_client.get("/api/atom/communication/memory/status")
        assert r.status_code == 200
        body = r.json()
        assert body["database_statistics"]["total_records"] == 0  # no table
        with patch.object(cma, "memory_manager", _mm([{"app_type": "slack"}])), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            r = comm_client.get("/api/atom/communication/memory/status")
        assert r.json()["database_statistics"]["total_records"] == 1

    def test_status_initializes_and_errors(self, comm_client):
        mm = _mm()
        mm.db = None
        mm.initialize.side_effect = lambda: setattr(mm, "db", MagicMock())
        with patch.object(cma, "memory_manager", mm), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            assert comm_client.get("/api/atom/communication/memory/status").status_code == 200
            mm.initialize.assert_called()
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()) as ip:
            ip.get_ingestion_stats.side_effect = RuntimeError("boom")
            assert comm_client.get(
                "/api/atom/communication/memory/status").status_code == 500

    def test_apps_listing(self, comm_client):
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            r = comm_client.get("/api/atom/communication/memory/apps")
        assert r.status_code == 200 and r.json()["total"] > 0

    def test_ingest_message(self, comm_client):
        url = "/api/atom/communication/memory/ingest"
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()), \
             patch("core.websockets.manager") as ws:
            ws.broadcast_event = AsyncMock()
            r = comm_client.post(url, params={"app_id": "slack"},
                                 json={"id": "m1", "content": "hi"})
        assert r.status_code == 200 and r.json()["success"] is True
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            assert comm_client.post(url, params={"app_id": "bogus"},
                                    json={}).status_code == 404
            ip = _ip()
            ip.ingest_message = AsyncMock(return_value=False)
            with patch.object(cma, "ingestion_pipeline", ip):
                assert comm_client.post(url, params={"app_id": "slack"},
                                        json={}).status_code == 500
            ip2 = _ip()
            ip2.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            with patch.object(cma, "ingestion_pipeline", ip2):
                assert comm_client.post(url, params={"app_id": "slack"},
                                        json={}).status_code == 500

    def test_ingest_batch(self, comm_client):
        url = "/api/atom/communication/memory/ingest/batch"
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()) as ip:
            r = comm_client.post(url, params={"app_id": "slack"},
                                 json=[{"id": "m1"}, {"id": "m2"}])
            assert r.status_code == 200 and r.json()["success_count"] == 2
            assert comm_client.post(url, params={"app_id": "bogus"},
                                    json=[]).status_code == 404
            results = iter([True, False])
            ip.ingest_message = AsyncMock(side_effect=lambda a, m: next(results))
            r = comm_client.post(url, params={"app_id": "slack"},
                                 json=[{"id": "m1"}, {"id": "m2"}])
            assert r.json()["success_count"] == 1 and r.json()["failure_count"] == 1
            r = comm_client.post(url, params={"app_id": "slack"}, json=[])
            assert r.json()["success_rate"] == "0.0%"
            ip.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            assert comm_client.post(url, params={"app_id": "slack"},
                                    json=[{"id": "x"}]).status_code == 500

    def test_search_memory(self, comm_client):
        url = "/api/atom/communication/memory/search"
        mm = _mm()
        mm.search_communications.return_value = [{"content": "x"}]
        with patch.object(cma, "memory_manager", mm), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            r = comm_client.get(url, params={"query": "q"})
            assert r.status_code == 200 and r.json()["total_results"] == 1
            mm.get_communications_by_timeframe.return_value = [
                {"app_type": "slack", "content": "Q text", "tags": ["sales"]}]
            r = comm_client.get(url, params={
                "query": "q", "app_id": "slack", "tag": "sales",
                "time_start": "2026-01-01T00:00:00",
                "time_end": "2026-01-31T00:00:00"})
            assert r.json()["total_results"] == 1
            assert comm_client.get(url, params={
                "query": "q", "time_start": "bad", "time_end": "2026-01-01"}).status_code == 400
            mm.get_communications_by_timeframe.side_effect = RuntimeError("boom")
            assert comm_client.get(url, params={
                "query": "q", "time_start": "2026-01-01T00:00:00",
                "time_end": "2026-01-02T00:00:00"}).status_code == 500

    def test_app_communications(self, comm_client):
        url = "/api/atom/communication/memory/communications/slack"
        mm = _mm()
        mm.get_communications_by_app.return_value = [{"id": "m1"}]
        with patch.object(cma, "memory_manager", mm), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            r = comm_client.get(url)
            assert r.status_code == 200 and r.json()["total_results"] == 1
            mm.get_communications_by_timeframe.return_value = [
                {"app_type": "slack"}, {"app_type": "email"}]
            r = comm_client.get(url, params={"time_start": "2026-01-01T00:00:00",
                                             "time_end": "2026-01-02T00:00:00"})
            assert r.json()["total_results"] == 1
            assert comm_client.get(
                "/api/atom/communication/memory/communications/bogus").status_code == 404
            mm.get_communications_by_app.side_effect = RuntimeError("boom")
            assert comm_client.get(url).status_code == 500

    def test_analytics(self, comm_client):
        url = "/api/atom/communication/memory/analytics"
        records = [
            {"id": "m1", "app_type": "slack", "direction": "inbound",
             "priority": "high", "status": "read",
             "timestamp": "2026-01-01T10:00:00",
             "metadata": json.dumps({"thread_id": "t1"}), "subject": "S"},
            {"id": "m2", "app_type": "slack", "direction": "outbound",
             "priority": "normal", "status": "sent",
             "timestamp": "2026-01-01T10:00:40",
             "metadata": {"thread_id": "t1"}, "subject": "S"},
            {"id": "m3", "app_type": "email", "direction": "internal",
             "priority": "normal", "status": "sent",
             "timestamp": "2026-01-01T20:00:00",
             "metadata": "{corrupt", "subject": "R"},
            {"id": "m4", "app_type": "teams", "direction": "outbound",
             "priority": "low", "status": "queued",
             "timestamp": datetime(2026, 1, 2, 9, 0),
             "metadata": "{}", "subject": None},
            {"id": "m5", "app_type": "slack", "direction": "inbound",
             "priority": "normal", "status": "read", "timestamp": "not-a-date",
             "metadata": "{}", "subject": None},
        ]
        with patch.object(cma, "memory_manager", _mm(records)), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            r = comm_client.get(url)
        assert r.status_code == 200
        analytics = r.json()["analytics"]
        assert analytics["summary"]["total_messages"] == 5
        assert analytics["direction_distribution"]["inbound"] == 2
        assert analytics["performance"]["avg_response_time"] == "40s"
        assert analytics["performance"]["response_rate"] == 100.0
        assert set(analytics["app_distribution"]) == {"slack", "email", "teams"}
        with patch.object(cma, "memory_manager", _mm(records[:1])), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            r = comm_client.get(url, params={"time_start": "2026-01-01T00:00:00",
                                             "time_end": "2026-01-02T00:00:00"})
            assert r.json()["analytics"]["summary"]["total_messages"] == 1
            assert comm_client.get(url, params={"time_start": "bad",
                                                "time_end": "x"}).status_code == 400

    def test_analytics_response_time_formats_and_error(self, comm_client):
        url = "/api/atom/communication/memory/analytics"
        # 2-minute response -> "2m"
        recs = [
            {"id": "a", "app_type": "slack", "direction": "inbound",
             "timestamp": "2026-01-01T10:00:00", "metadata": "{}", "subject": "S",
             "priority": "normal", "status": "read"},
            {"id": "b", "app_type": "slack", "direction": "outbound",
             "timestamp": "2026-01-01T10:02:00", "metadata": "{}", "subject": "S",
             "priority": "normal", "status": "read"},
        ]
        with patch.object(cma, "memory_manager", _mm(recs)), \
             patch.object(cma, "ingestion_pipeline", _ip()):
            assert comm_client.get(url).json()["analytics"]["performance"][
                "avg_response_time"] == "2m"
        with patch.object(cma, "memory_manager", MagicMock()), \
             patch.object(cma, "ingestion_pipeline", _ip()) as ip:
            ip.get_ingestion_stats.side_effect = RuntimeError("boom")
            assert comm_client.get(url).status_code == 500

    def test_configure_app(self, comm_client):
        base = "/api/atom/communication/memory/configure"
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()) as ip:
            r = comm_client.post(base, params={"app_id": "slack"},
                                 json={"app_type": "slack", "enabled": True,
                                       "real_time": True, "batch_size": 10,
                                       "ingest_attachments": True,
                                       "embed_content": True,
                                       "retention_days": 30})
            assert r.status_code == 200
            ip.configure_app.assert_called_once()
        with patch.object(cma, "memory_manager", _mm()), \
             patch.object(cma, "ingestion_pipeline", _ip()) as ip:
            ip.configure_app.side_effect = RuntimeError("boom")
            assert comm_client.post(base, params={"app_id": "slack"},
                                    json={"app_type": "slack", "enabled": True,
                                          "real_time": True, "batch_size": 10,
                                          "ingest_attachments": True,
                                          "embed_content": True,
                                          "retention_days": 30}).status_code == 500
        assert comm_client.post(base, params={"app_id": "bogus"},
                                json={"app_type": "slack", "enabled": True,
                                      "real_time": True, "batch_size": 10,
                                      "ingest_attachments": True,
                                      "embed_content": True,
                                      "retention_days": 30}).status_code == 404


# ============================================================================
# 4. integrations/auth_handler_zoom.py
# ============================================================================
from integrations import auth_handler_zoom as zm
from integrations.auth_handler_zoom import ZoomAuthHandler


class _FakeResponse:
    def __init__(self, status=200, payload=None, text="err"):
        self.status = status
        self._payload = payload
        self._text = text

    async def text(self):
        return self._text

    async def json(self):
        return self._payload or {}


class _FakeRespCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _next(self):
        return self._responses[0] if len(self._responses) == 1 else self._responses.pop(0)

    def post(self, *a, **k):
        return _FakeRespCM(self._next())

    def get(self, *a, **k):
        return _FakeRespCM(self._next())

    def request(self, *a, **k):
        return _FakeRespCM(self._next())


def _mock_session(*responses):
    return patch.object(zm.aiohttp, "ClientSession",
                        MagicMock(return_value=_FakeSession(responses)))


def _token_state(h):
    h.access_token = "tok"
    h.refresh_token = "rt"
    h.token_expires_at = datetime.now() + timedelta(hours=1)


@pytest.fixture(autouse=True)
def _zoom_env(monkeypatch):
    monkeypatch.setenv("ZOOM_CLIENT_ID", "zcid")
    monkeypatch.setenv("ZOOM_CLIENT_SECRET", "zcsecret")
    monkeypatch.setenv("ZOOM_REDIRECT_URI", "https://app.example/cb")


class TestZoomAuthHandler:
    def test_init_defaults(self):
        h = ZoomAuthHandler()
        assert h.client_id == "zcid" and h.client_secret == "zcsecret"
        assert h.token_url == "https://zoom.us/oauth/token"

    def test_authorization_url(self):
        h = ZoomAuthHandler()
        url = h.get_authorization_url()
        assert url.startswith("https://zoom.us/oauth/authorize?")
        assert "state=xyz" in h.get_authorization_url(state="xyz")

    def test_basic_auth_header(self):
        import base64
        h = ZoomAuthHandler()
        decoded = base64.b64decode(h._get_basic_auth_header()).decode()
        assert decoded == "zcid:zcsecret"

    def test_exchange_code_success(self):
        h = ZoomAuthHandler()
        token = {"access_token": "at", "refresh_token": "rft", "expires_in": 7200}
        with _mock_session(_FakeResponse(payload=token)):
            out = asyncio.run(h.exchange_code_for_token("code-1"))
        assert out["access_token"] == "at"
        assert h.access_token == "at" and h.refresh_token == "rft"
        assert h.token_expires_at > datetime.now()

    def test_exchange_code_non_200_and_error(self):
        h = ZoomAuthHandler()
        with _mock_session(_FakeResponse(status=400, text="bad")):
            with pytest.raises(HTTPException):
                asyncio.run(h.exchange_code_for_token("c"))
        with patch.object(zm.aiohttp, "ClientSession",
                          MagicMock(side_effect=RuntimeError("net"))):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(h.exchange_code_for_token("c"))
            assert ei.value.status_code == 500

    def test_refresh_token_paths(self):
        h = ZoomAuthHandler()
        with pytest.raises(HTTPException):
            asyncio.run(h.refresh_access_token())
        _token_state(h)
        token = {"access_token": "at2", "refresh_token": "rt2", "expires_in": 3600}
        with _mock_session(_FakeResponse(payload=token)):
            out = asyncio.run(h.refresh_access_token())
        assert out["access_token"] == "at2" and h.access_token == "at2"
        with _mock_session(_FakeResponse(status=400, text="bad")):
            with pytest.raises(HTTPException):
                asyncio.run(h.refresh_access_token())
        with patch.object(zm.aiohttp, "ClientSession",
                          MagicMock(side_effect=RuntimeError("net"))):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(h.refresh_access_token())
            assert ei.value.status_code == 500

    def test_get_user_info_paths(self):
        h = ZoomAuthHandler()
        with pytest.raises(HTTPException):
            asyncio.run(h.get_user_info())
        h.access_token = "tok"
        with _mock_session(_FakeResponse(payload={"id": "me", "email": "z@x.com"})):
            out = asyncio.run(h.get_user_info())
        assert out["id"] == "me" and h.user_info == out
        with _mock_session(_FakeResponse(status=403, text="no")):
            with pytest.raises(HTTPException):
                asyncio.run(h.get_user_info())
        with patch.object(zm.aiohttp, "ClientSession",
                          MagicMock(side_effect=RuntimeError("net"))):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(h.get_user_info())
            assert ei.value.status_code == 500

    def test_revoke_token_paths(self):
        h = ZoomAuthHandler()
        assert asyncio.run(h.revoke_token()) is True  # no token
        _token_state(h)
        with _mock_session(_FakeResponse(status=200)):
            assert asyncio.run(h.revoke_token()) is True
        assert h.access_token is None and h.refresh_token is None
        _token_state(h)
        with _mock_session(_FakeResponse(status=400, text="no")):
            assert asyncio.run(h.revoke_token()) is False
        _token_state(h)
        with patch.object(zm.aiohttp, "ClientSession",
                          MagicMock(side_effect=RuntimeError("net"))):
            assert asyncio.run(h.revoke_token()) is False

    def test_is_token_valid(self):
        h = ZoomAuthHandler()
        assert h.is_token_valid() is False
        h.access_token = "tok"
        h.token_expires_at = datetime.now() - timedelta(hours=1)
        assert h.is_token_valid() is False
        h.token_expires_at = datetime.now() + timedelta(hours=2)
        assert h.is_token_valid() is True
        h.token_expires_at = datetime.now() + timedelta(minutes=2)  # inside buffer
        assert h.is_token_valid() is False

    def test_ensure_valid_token(self):
        h = ZoomAuthHandler()
        with pytest.raises(HTTPException):
            asyncio.run(h.ensure_valid_token())
        h.access_token = "tok"
        h.token_expires_at = datetime.now() + timedelta(hours=1)
        assert asyncio.run(h.ensure_valid_token()) == "tok"
        h.token_expires_at = datetime.now()  # expired but refreshable
        h.refresh_token = "rt"
        with _mock_session(_FakeResponse(payload={"access_token": "at3",
                                                  "refresh_token": "rt",
                                                  "expires_in": 3600})):
            assert asyncio.run(h.ensure_valid_token()) == "at3"

    def test_make_authenticated_request(self):
        h = ZoomAuthHandler()
        _token_state(h)
        with _mock_session(_FakeResponse(payload={"ok": True})):
            out = asyncio.run(h.make_authenticated_request("GET", "/users/me"))
        assert out == {"ok": True}
        with _mock_session(_FakeResponse(status=204)):
            assert asyncio.run(h.make_authenticated_request("DELETE", "/x")) == {}
        with _mock_session(_FakeResponse(status=404, text="nf")):
            with pytest.raises(HTTPException):
                asyncio.run(h.make_authenticated_request("GET", "/missing"))
        # 401 -> refresh -> retry
        h.token_expires_at = datetime.now()  # force refresh path
        with _mock_session(
            _FakeResponse(payload={"access_token": "at9", "refresh_token": "rt",
                                   "expires_in": 3600}),
            _FakeResponse(payload={"ok": "retried"}),
        ):
            out = asyncio.run(h.make_authenticated_request("GET", "/users/me"))
        assert out == {"ok": "retried"}
        with patch.object(zm.aiohttp, "ClientSession",
                          MagicMock(side_effect=RuntimeError("net"))):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(h.make_authenticated_request("GET", "/x"))
            assert ei.value.status_code == 500

    def test_connection_status(self):
        h = ZoomAuthHandler()
        st = h.get_connection_status()
        assert st["connected"] is False and st["client_id_configured"] is True
        _token_state(h)
        h.user_info = {"id": "me"}
        st = h.get_connection_status()
        assert st["connected"] is True and st["user_info_available"] is True
        assert st["token_expires_at"]


# ============================================================================
# 5. core/workflow_ui_endpoints.py
# ============================================================================
import core.workflow_ui_endpoints as wui
from core.workflow_ui_endpoints import (
    MOCK_EXECUTIONS,
    MOCK_TEMPLATES,
    _merge_persisted_executions,
    cancel_execution,
    create_workflow,
    create_workflow_definition,
    delete_workflow,
    execute_workflow,
    get_executions,
    get_orchestrator_state,
    get_services,
    get_templates,
    get_workflow_by_id,
    get_workflow_history,
    get_workflows,
    import_template,
    list_workflows,
    update_workflow,
)


def _tpl(**kw):
    defaults = dict(
        id="tpl-1", tenant_id="t-1", name="T", description="d",
        category="automation", is_public=True, icon="icon",
        steps=[{"id": "s1"}], input_schema={"a": 1},
        rating=4.5, usage_count=10, author_id="u1", version="1.0",
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 2))
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _db(template=None, rows=None):
    db = MagicMock()
    chain = MagicMock()
    chain.filter.return_value = chain  # recursive filter chain
    chain.first.return_value = template
    chain.all.return_value = rows or []
    chain.order_by.return_value.limit.return_value.all.return_value = rows or []
    chain.order_by.return_value.limit.return_value.offset.return_value \
        .all.return_value = rows or []
    db.query.return_value = chain
    return db


def _patch_db(db):
    return patch.object(wui, "get_db", MagicMock(return_value=iter([db])))


def _mock_flag(value=True):
    return patch.object(wui, "WORKFLOW_MOCK_ENABLED", value)


class TestWorkflowTemplates:
    async def test_get_templates_mock_and_db(self):
        with _mock_flag(True):
            out = await get_templates(category=None, complexity=None,
                                      is_public=True, db=MagicMock())
        assert out["count"] == len(MOCK_TEMPLATES)
        db = _db(rows=[_tpl(), _tpl(icon=None, steps=None, input_schema=None,
                                    rating=0, usage_count=0, author_id=None,
                                    version=None)])
        with _mock_flag(False):
            out = await get_templates(category="automation", complexity=None,
                                      is_public=True, db=db)
        assert out["count"] == 2
        assert out["templates"][1]["icon"] == "workflow"
        assert out["templates"][1]["input_schema"] == {}

    async def test_import_template_paths(self):
        with _mock_flag(True):
            out = await import_template("tpl_daily_standup", db=MagicMock())
            assert out["workflow_id"] == "imported_tpl_daily_standup"
            with pytest.raises(HTTPException):
                await import_template("nope", db=MagicMock())
        src = _tpl()
        db = _db(template=src)
        with _mock_flag(False):
            out = await import_template("tpl-1", db=db)
        assert out["success"] is True and db.add.called
        assert src.usage_count == 11
        with _mock_flag(False):
            with pytest.raises(HTTPException):
                await import_template("missing", db=_db(template=None))

    async def test_get_services(self):
        out = await get_services()
        assert out["success"] is True and len(out["services"]) >= 10


class TestWorkflowDefinitions:
    async def test_get_workflows_mock_and_db(self):
        with _mock_flag(True):
            out = await get_workflows(limit=5, offset=0, db=MagicMock())
        assert "workflows" in out
        db = _db(rows=[_tpl(), _tpl(created_at=None, updated_at=None, steps=None)])
        with _mock_flag(False):
            out = await get_workflows(limit=5, offset=0, db=db)
        assert out["count"] == 2
        assert out["workflows"][1]["created_at"] is None
        assert out["workflows"][1]["steps_count"] == 0

    async def test_list_workflows_alias(self):
        db = _db(rows=[_tpl()])
        with _mock_flag(False):
            out = await list_workflows(limit=5, offset=0, db=db)
        assert out["count"] == 1

    async def test_get_workflow_by_id_paths(self):
        with _mock_flag(True):
            out = await get_workflow_by_id("wf_1", db=MagicMock())
            assert out["workflow"]["id"] == "wf_1"
            with pytest.raises(HTTPException):
                await get_workflow_by_id("none", db=MagicMock())
        db = _db(template=_tpl())
        with _mock_flag(False):
            out = await get_workflow_by_id("tpl-1", db=db)
        assert out["workflow"]["name"] == "T"
        with _mock_flag(False):
            with pytest.raises(HTTPException):
                await get_workflow_by_id("none", db=_db(template=None))

    async def test_create_workflow_mock_and_db(self):
        with _mock_flag(True):
            out = await create_workflow({"name": "N", "steps": [1, 2, 3]},
                                        author_id=None, db=MagicMock())
        assert out["workflow"]["steps_count"] == 3
        db = _db()
        with _mock_flag(False):
            out = await create_workflow({"name": "N"}, author_id="u1", db=db)
        assert out["success"] is True and db.add.called

    async def test_update_workflow_mock_and_all_fields(self):
        with _mock_flag(True):
            out = await update_workflow("wf_1",
                                        {"name": "N2", "description": "d2"},
                                        db=MagicMock())
            assert out["workflow"]["name"] == "N2"
        tpl = _tpl()
        payload = {"name": "n", "description": "d", "category": "c",
                   "icon": "i", "input_schema": {"x": 1}, "steps": [],
                   "is_public": False}
        with _mock_flag(False):
            out = await update_workflow("tpl-1", payload, db=_db(template=tpl))
        assert out["workflow"]["is_public"] is False and tpl.icon == "i"

    async def test_delete_workflow_paths(self):
        with _mock_flag(True):
            out = await delete_workflow("wf-temp", db=MagicMock()) if False else None
        # mock branch found + 404
        wui.MOCK_WORKFLOWS.insert(0, type(wui.MOCK_WORKFLOWS[0])(
            id="wf-del", name="x", description="", steps=[], input_schema={},
            created_at="t", updated_at="t", steps_count=0))
        try:
            with _mock_flag(True):
                out = await delete_workflow("wf-del", db=MagicMock())
                assert out["success"] is True
                with pytest.raises(HTTPException):
                    await delete_workflow("wf-del", db=MagicMock())
        finally:
            wui.MOCK_WORKFLOWS[:] = [w for w in wui.MOCK_WORKFLOWS if w.id != "wf-del"]
        db = _db(template=_tpl())
        with _mock_flag(False):
            out = await delete_workflow("tpl-1", db=db)
        assert out["success"] is True and db.delete.called

    async def test_history_and_create_definition(self):
        out = await get_workflow_history("wf_1")
        assert out["history"][0]["execution_id"] == "exec_1"
        out = await create_workflow_definition(
            {"name": "V", "definition": {"nodes": [1, 2]}})
        assert out["workflow"]["steps_count"] == 2


class TestExecutionsAndOrchestrator:
    def _orch(self):
        orch = MagicMock()
        orch.workflows = {}
        orch.active_contexts = {}
        orch.memory_snapshots = {"snap1": {"current_step": 2, "variables": {"a": 1}}}
        return orch

    async def test_merge_persisted_executions(self):
        row = SimpleNamespace(
            execution_id="db-exec-1", workflow_id="wf-1", status="RUNNING",
            created_at=datetime(2026, 1, 1), completed_at=None,
            input_data=json.dumps({"i": 1}), outputs=json.dumps({"o": 1}),
            steps=json.dumps({"s": 1}), error="e1")
        db = _db()
        db.query.return_value.order_by.return_value.limit.return_value \
            .all.return_value = [row]
        with _patch_db(db):
            out = _merge_persisted_executions([])
        assert out[0].execution_id == "db-exec-1"
        assert out[0].status == "running" and out[0].errors == ["e1"]
        assert out[0].total_steps == 1
        # dedup + corrupt json branches
        db2 = _db()
        bad = SimpleNamespace(execution_id="db-exec-1", workflow_id="w",
                              status=None, created_at="not-a-dt",
                              completed_at=None, input_data=None,
                              outputs="{bad", steps=None, error=None)
        db2.query.return_value.order_by.return_value.limit.return_value \
            .all.return_value = [bad]
        with _patch_db(db2):
            out = _merge_persisted_executions(
                [SimpleNamespace(execution_id="db-exec-1")])
        assert len(out) == 1  # deduped

    async def test_get_executions_context_variants(self):
        class St:
            value = "running"
        ctx = SimpleNamespace(
            workflow_id="wf-9", input_data={"_ui_workflow_id": "wf-ui"},
            status=St(), started_at=datetime(2026, 1, 1),
            completed_at="2026-01-01T01:00:00", results={"r": 1},
            error_message="boom")
        orch = self._orch()
        orch.active_contexts = {"e1": ctx}
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orch), \
             patch.object(wui, "get_db", MagicMock(side_effect=RuntimeError("no db"))):
            out = await get_executions(current_user=USER)
        assert out["executions"][0]["status"] == "running"
        assert out["executions"][0]["errors"] == ["boom"]

        # dict-form context + ImportError fallback
        orch2 = self._orch()
        orch2.active_contexts = {"e2": {
            "workflow_id": "wf-d", "input_data": {}, "status": "pending",
            "started_at": "2026-01-01T00:00:00", "completed_at": None,
            "results": None, "error_message": None}}
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orch2), \
             patch.object(wui, "get_db", MagicMock(side_effect=RuntimeError("x"))):
            out = await get_executions(current_user=USER)
            assert out["executions"][0]["workflow_id"] == "wf-d"
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   side_effect=ImportError("gone")), \
             patch.object(wui, "get_db", MagicMock(side_effect=RuntimeError("x"))):
            out = await get_executions(current_user=USER)
            assert out["executions"][0]["execution_id"] == "exec_1"

    async def test_execute_workflow_bridge_types(self):
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=self._orch()), \
             patch.object(wui, "require_workflow_executor_orchestrator",
                          AsyncMock()), \
             patch.object(wui, "MOCK_TEMPLATES", MOCK_TEMPLATES):
            # ai step -> NLU_ANALYSIS (tpl_marketing_campaign has an ai step)
            out = await execute_workflow(
                {"workflow_id": "tpl_marketing_campaign", "input": {}},
                background_tasks=MagicMock(), current_user=USER)
            assert out["success"] is True
            # slack step -> SLACK_NOTIFICATION
            out = await execute_workflow(
                {"workflow_id": "tpl_daily_standup", "input": {}},
                background_tasks=MagicMock(), current_user=USER)
            assert out["total_steps"] >= 1
            # unknown workflow -> warning branch
            out = await execute_workflow(
                {"workflow_id": "no-such-wf", "input": {}},
                background_tasks=MagicMock(), current_user=USER)
            assert out["total_steps"] == 0

    async def test_cancel_execution_paths(self):
        # 1) legacy mock
        for exc in MOCK_EXECUTIONS:
            if exc.execution_id == "exec_1":
                assert (await cancel_execution("exec_1", current_user=USER))["success"] is True
                exc.status = "completed"  # restore
        # 2) DB row
        row = SimpleNamespace(execution_id="db-exec-9", status="RUNNING")
        db = _db(template=row)
        with _patch_db(db):
            out = await cancel_execution("db-exec-9", current_user=USER)
        assert out["success"] is True and row.status == "CANCELLED"
        # 3) orchestrator in-memory + 404
        orch = self._orch()
        orch.active_contexts = {"orch-1": SimpleNamespace()}
        with _patch_db(_db(template=None)), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orch):
            assert (await cancel_execution("orch-1",
                                           current_user=USER))["success"] is True
        with _patch_db(_db(template=None)), \
             patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=self._orch()):
            with pytest.raises(HTTPException):
                await cancel_execution("ghost", current_user=USER)

    async def test_get_orchestrator_state(self):
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=self._orch()):
            out = await get_orchestrator_state(current_user=USER)
        assert out["snapshot_details"]["snap1"]["step"] == 2
