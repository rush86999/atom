# -*- coding: utf-8 -*-
"""Coverage wave 108 — integrations/pdf_processing/pdf_memory_routes
(TestClient + fully mocked service, zero LLM spend, no network).

Auth: router-level get_current_user dependency — every route returns 401 for
anonymous requests (verified per route). All validation/error/exception
branches per route, plus get_pdf_memory_service lazy-init.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import integrations.pdf_processing.pdf_memory_routes as mod
try:
    from backend.core.auth import get_current_user
except ImportError:
    from core.auth import get_current_user
from integrations.pdf_processing.pdf_memory_routes import (
    get_pdf_memory_service,
    router,
)

app = FastAPI()
app.include_router(router)

FAKE_USER = MagicMock()
FAKE_USER.id = "user-1"
FAKE_USER.email = "user@example.com"


def _make_service(**attrs):
    svc = AsyncMock()
    svc.lancedb_handler = MagicMock()
    svc.table_name = "pdf_documents"
    for key, value in attrs.items():
        setattr(svc, key, value)
    return svc


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    service = _make_service()
    app.dependency_overrides[get_pdf_memory_service] = lambda: service
    with TestClient(app) as c:
        c.service = service
        yield c
    app.dependency_overrides.clear()


# ============================================================================
# Auth: 401 for anonymous
# ============================================================================

class TestAuth:
    def test_all_routes_require_auth(self):
        app.dependency_overrides.clear()
        with TestClient(app) as c:
            assert c.get("/pdf-memory/status").status_code == 401
            assert c.post("/pdf-memory/store").status_code == 401
            assert c.get("/pdf-memory/search").status_code == 401
            assert c.get("/pdf-memory/documents/d1").status_code == 401
            assert c.delete("/pdf-memory/documents/d1").status_code == 401
            assert c.get("/pdf-memory/users/u1/stats").status_code == 401
            assert c.get("/pdf-memory/users/u1/documents").status_code == 401
            assert c.post("/pdf-memory/documents/d1/tags").status_code == 401
            assert c.get("/pdf-memory/documents/d1/tags").status_code == 401
            assert c.delete("/pdf-memory/documents/d1/tags").status_code == 401
            assert c.get("/pdf-memory/users/u1/documents/search").status_code == 401
            assert c.get("/pdf-memory/health").status_code == 401


# ============================================================================
# /status
# ============================================================================

class TestStatus:
    def test_status_ok(self, client):
        resp = client.get("/pdf-memory/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "available"
        assert body["lancedb_available"] is True
        assert body["table_name"] == "pdf_documents"
        assert "semantic_search" in body["capabilities"]

    def test_status_error(self, client):
        class _Boom:
            table_name = "t"

            @property
            def lancedb_handler(self):
                raise RuntimeError("db down")

        app.dependency_overrides[get_pdf_memory_service] = lambda: _Boom()
        resp = client.get("/pdf-memory/status")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /store
# ============================================================================

class TestStore:
    def test_store_success(self, client):
        client.service.store_processed_pdf.return_value = {
            "success": True, "doc_id": "d1", "user_id": "user-1"}
        resp = client.post("/pdf-memory/store", params={"user_id": "user-1"},
                           json={"processing_result": {"text": "hi"}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["doc_id"] == "d1"
        client.service.store_processed_pdf.assert_awaited_once_with(
            user_id="user-1", processing_result={"text": "hi"},
            source_uri=None, tags=None, metadata=None)

    async def _call_store(self, client, params=None, body=None, tags=None,
                          metadata=None):
        query = params or {}
        if tags is not None:
            for tag in tags:
                query.setdefault("tags", []).append(tag)
        return client.post("/pdf-memory/store", params=query,
                           json=body if body is not None else {},
                           )

    def test_store_empty_user_id(self, client):
        resp = client.post("/pdf-memory/store",
                           params={"user_id": ""},
                           json={"processing_result": {"text": "hi"}})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "user_id is required"

    def test_store_empty_processing_result(self, client):
        resp = client.post("/pdf-memory/store", params={"user_id": "user-1"},
                           json={"processing_result": {}})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "processing_result is required"

    def test_store_service_failure(self, client):
        client.service.store_processed_pdf.return_value = {
            "success": False, "error": "embedding failed"}
        resp = client.post("/pdf-memory/store", params={"user_id": "user-1"},
                           json={"processing_result": {"text": "hi"}})
        assert resp.status_code == 500
        assert "embedding failed" in resp.json()["detail"]

    def test_store_service_exception(self, client):
        client.service.store_processed_pdf.side_effect = RuntimeError("boom")
        resp = client.post("/pdf-memory/store", params={"user_id": "user-1"},
                           json={"processing_result": {"text": "hi"}})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /search
# ============================================================================

class TestSearch:
    def test_search_success(self, client):
        client.service.search_pdfs.return_value = [{"doc_id": "d1"}, {"doc_id": "d2"}]
        resp = client.get("/pdf-memory/search",
                          params={"user_id": "user-1", "query": "invoice",
                                  "pdf_type": "searchable", "tags": ["tax"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["results_count"] == 2
        client.service.search_pdfs.assert_awaited_once_with(
            user_id="user-1", query="invoice", limit=10,
            similarity_threshold=0.7,
            filters={"pdf_type": "searchable", "tags": ["tax"]})

    def test_search_empty_user_id(self, client):
        resp = client.get("/pdf-memory/search", params={"user_id": "", "query": "x"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "user_id is required"

    def test_search_empty_query(self, client):
        resp = client.get("/pdf-memory/search", params={"user_id": "u", "query": "  "})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "query is required"

    def test_search_bad_pdf_type(self, client):
        resp = client.get("/pdf-memory/search",
                          params={"user_id": "u", "query": "x", "pdf_type": "bad"})
        assert resp.status_code == 400
        assert "pdf_type must be one of" in resp.json()["detail"]

    def test_search_without_filters(self, client):
        client.service.search_pdfs.return_value = []
        resp = client.get("/pdf-memory/search",
                          params={"user_id": "u", "query": "x"})
        assert resp.status_code == 200
        client.service.search_pdfs.assert_awaited_once_with(
            user_id="u", query="x", limit=10, similarity_threshold=0.7,
            filters={})

    def test_search_service_exception(self, client):
        client.service.search_pdfs.side_effect = RuntimeError("boom")
        resp = client.get("/pdf-memory/search",
                          params={"user_id": "u", "query": "x"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /documents/{doc_id}
# ============================================================================

class TestGetDocument:
    def test_get_success(self, client):
        client.service.get_document.return_value = {"doc_id": "d1", "text": "hi"}
        resp = client.get("/pdf-memory/documents/d1", params={"user_id": "u"})
        assert resp.status_code == 200
        assert resp.json()["document"]["doc_id"] == "d1"

    def test_get_not_found(self, client):
        client.service.get_document.return_value = None
        resp = client.get("/pdf-memory/documents/d1", params={"user_id": "u"})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_get_empty_user_id(self, client):
        resp = client.get("/pdf-memory/documents/d1", params={"user_id": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "user_id is required"

    def test_get_empty_doc_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.get_document("u", "", service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "doc_id is required"

    def test_get_service_exception(self, client):
        client.service.get_document.side_effect = RuntimeError("boom")
        resp = client.get("/pdf-memory/documents/d1", params={"user_id": "u"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestDeleteDocument:
    def test_delete_success(self, client):
        client.service.delete_document.return_value = {"success": True,
                                                       "deleted": True}
        resp = client.delete("/pdf-memory/documents/d1", params={"user_id": "u"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "deleted successfully" in resp.json()["message"]

    def test_delete_failure(self, client):
        client.service.delete_document.return_value = {
            "success": False, "error": "delete failed"}
        resp = client.delete("/pdf-memory/documents/d1", params={"user_id": "u"})
        assert resp.status_code == 500
        assert "delete failed" in resp.json()["detail"]

    def test_delete_empty_user_id(self, client):
        resp = client.delete("/pdf-memory/documents/d1", params={"user_id": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "user_id is required"

    def test_delete_empty_doc_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.delete_document("u", "", service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "doc_id is required"

    def test_delete_service_exception(self, client):
        client.service.delete_document.side_effect = RuntimeError("boom")
        resp = client.delete("/pdf-memory/documents/d1", params={"user_id": "u"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /users/{user_id}/stats and /users/{user_id}/documents
# ============================================================================

class TestStats:
    def test_stats_success(self, client):
        client.service.get_user_document_stats.return_value = {"total": 3}
        resp = client.get("/pdf-memory/users/u1/stats")
        assert resp.status_code == 200
        assert resp.json()["statistics"] == {"total": 3}

    def test_stats_empty_user_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.get_user_document_stats("", service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "user_id is required"

    def test_stats_service_exception(self, client):
        client.service.get_user_document_stats.side_effect = RuntimeError("boom")
        resp = client.get("/pdf-memory/users/u1/stats")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestListDocuments:
    def test_list_success(self, client):
        client.service.list_documents.return_value = {
            "success": True, "limit": 50, "offset": 0, "total": 1,
            "documents": [{"doc_id": "d1"}],
        }
        resp = client.get("/pdf-memory/users/u1/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"] == {"limit": 50, "offset": 0, "total": 1}
        assert body["documents"] == [{"doc_id": "d1"}]

    def test_list_with_filters(self, client):
        client.service.list_documents.return_value = {
            "success": True, "limit": 10, "offset": 5, "total": 0,
            "documents": [],
        }
        resp = client.get("/pdf-memory/users/u1/documents",
                          params={"limit": 10, "offset": 5, "pdf_type": "mixed",
                                  "tags": "tax,  invoice ",
                                  "date_from": "2026-01-01",
                                  "date_to": "2026-12-31"})
        assert resp.status_code == 200
        client.service.list_documents.assert_awaited_once_with(
            user_id="u1", limit=10, offset=5, pdf_type="mixed",
            tags=["tax", "invoice"], date_from="2026-01-01",
            date_to="2026-12-31")

    def test_list_empty_user_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.list_user_documents("", service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "user_id is required"

    def test_list_service_failure(self, client):
        client.service.list_documents.return_value = {
            "success": False, "error": "list failed"}
        resp = client.get("/pdf-memory/users/u1/documents")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "list failed"

    def test_list_service_exception(self, client):
        client.service.list_documents.side_effect = RuntimeError("boom")
        resp = client.get("/pdf-memory/users/u1/documents")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"

    def test_list_invalid_limit_rejected(self, client):
        resp = client.get("/pdf-memory/users/u1/documents", params={"limit": 0})
        assert resp.status_code == 422


# ============================================================================
# /documents/{doc_id}/tags (update / get / delete)
# ============================================================================

class TestUpdateDocumentTags:
    def test_update_success(self, client):
        client.service.update_document_tags.return_value = {
            "success": True, "tags": ["a", "b"], "message": "ok"}
        resp = client.post("/pdf-memory/documents/d1/tags",
                           params={"user_id": "u"}, json=["a", "b"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["tags"] == ["a", "b"]
        assert body["message"] == "ok"
        client.service.update_document_tags.assert_awaited_once_with(
            user_id="u", doc_id="d1", tags=["a", "b"])

    def test_update_empty_user_id(self, client):
        resp = client.post("/pdf-memory/documents/d1/tags",
                           params={"user_id": ""}, json=["a"])
        assert resp.status_code == 400
        assert resp.json()["detail"] == "user_id is required"

    def test_update_empty_doc_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.update_document_tags("", "u", ["a"],
                                                 service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "doc_id is required"

    def test_update_tags_not_a_list(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.update_document_tags("d1", "u", "notalist",
                                                 service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "tags must be a list"

    def test_update_not_found(self, client):
        client.service.update_document_tags.return_value = {
            "success": False, "error": "Document not found"}
        resp = client.post("/pdf-memory/documents/d1/tags",
                           params={"user_id": "u"}, json=["a"])
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_update_other_error(self, client):
        client.service.update_document_tags.return_value = {
            "success": False, "error": "disk full"}
        resp = client.post("/pdf-memory/documents/d1/tags",
                           params={"user_id": "u"}, json=["a"])
        assert resp.status_code == 500
        assert resp.json()["detail"] == "disk full"

    def test_update_service_exception(self, client):
        client.service.update_document_tags.side_effect = RuntimeError("boom")
        resp = client.post("/pdf-memory/documents/d1/tags",
                           params={"user_id": "u"}, json=["a"])
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestGetDocumentTags:
    def test_get_success(self, client):
        client.service.get_document_tags.return_value = {
            "success": True, "tags": ["a"], "count": 1}
        resp = client.get("/pdf-memory/documents/d1/tags", params={"user_id": "u"})
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["a"]
        assert resp.json()["count"] == 1

    def test_get_empty_user_id(self, client):
        resp = client.get("/pdf-memory/documents/d1/tags", params={"user_id": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "user_id is required"

    def test_get_empty_doc_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.get_document_tags("", "u", service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "doc_id is required"

    def test_get_not_found(self, client):
        client.service.get_document_tags.return_value = {
            "success": False, "error": "Document not found"}
        resp = client.get("/pdf-memory/documents/d1/tags", params={"user_id": "u"})
        assert resp.status_code == 404

    def test_get_other_error(self, client):
        client.service.get_document_tags.return_value = {
            "success": False, "error": "nope"}
        resp = client.get("/pdf-memory/documents/d1/tags", params={"user_id": "u"})
        assert resp.status_code == 500

    def test_get_service_exception(self, client):
        client.service.get_document_tags.side_effect = RuntimeError("boom")
        resp = client.get("/pdf-memory/documents/d1/tags", params={"user_id": "u"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestDeleteDocumentTags:
    def test_delete_success(self, client):
        client.service.delete_document_tags.return_value = {
            "success": True, "deleted_tags": ["a"], "deleted_count": 1,
            "remaining_tags": ["b"], "message": "ok"}
        resp = client.request("DELETE", "/pdf-memory/documents/d1/tags",
                                 params={"user_id": "u"}, json=["a"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted_tags"] == ["a"]
        assert body["deleted_count"] == 1
        assert body["remaining_tags"] == ["b"]
        client.service.delete_document_tags.assert_awaited_once_with(
            doc_id="d1", user_id="u", tags_to_delete=["a"])

    def test_delete_empty_user_id(self, client):
        resp = client.request("DELETE", "/pdf-memory/documents/d1/tags",
                                 params={"user_id": ""}, json=["a"])
        assert resp.status_code == 400

    def test_delete_empty_tags_list(self, client):
        resp = client.request("DELETE", "/pdf-memory/documents/d1/tags",
                                 params={"user_id": "u"}, json=[])
        assert resp.status_code == 400
        assert "non-empty" in resp.json()["detail"]

    def test_delete_empty_doc_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.delete_document_tags("", "u", ["a"],
                                                 service=client.service))
        assert exc.value.status_code == 400
        assert exc.value.detail == "doc_id is required"

    def test_delete_not_found(self, client):
        client.service.delete_document_tags.return_value = {
            "success": False, "error": "Document not found"}
        resp = client.request("DELETE", "/pdf-memory/documents/d1/tags",
                                 params={"user_id": "u"}, json=["a"])
        assert resp.status_code == 404

    def test_delete_other_error(self, client):
        client.service.delete_document_tags.return_value = {
            "success": False, "error": "nope"}
        resp = client.request("DELETE", "/pdf-memory/documents/d1/tags",
                                 params={"user_id": "u"}, json=["a"])
        assert resp.status_code == 500

    def test_delete_service_exception(self, client):
        client.service.delete_document_tags.side_effect = RuntimeError("boom")
        resp = client.request("DELETE", "/pdf-memory/documents/d1/tags",
                                 params={"user_id": "u"}, json=["a"])
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /users/{user_id}/documents/search
# ============================================================================

class TestSearchDocumentsByTags:
    def test_search_success(self, client):
        client.service.search_by_tags.return_value = {
            "success": True, "count": 2, "documents": [{"doc_id": "d1"}]}
        resp = client.get("/pdf-memory/users/u1/documents/search",
                          params={"tags": "tax, invoice", "match_all": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["search_tags"] == ["tax", "invoice"]
        assert body["match_all"] is True
        assert body["count"] == 2
        client.service.search_by_tags.assert_awaited_once_with(
            user_id="u1", tags=["tax", "invoice"], match_all=True)

    def test_search_empty_user_id(self, client):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(mod.search_documents_by_tags("", service=client.service,
                                                     tags="tax"))
        assert exc.value.status_code == 400
        assert exc.value.detail == "user_id is required"

    def test_search_no_tags(self, client):
        resp = client.get("/pdf-memory/users/u1/documents/search",
                          params={"tags": " , "})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "At least one tag is required"

    def test_search_missing_tags_param(self, client):
        resp = client.get("/pdf-memory/users/u1/documents/search")
        assert resp.status_code == 422

    def test_search_service_failure(self, client):
        client.service.search_by_tags.return_value = {
            "success": False, "error": "search failed"}
        resp = client.get("/pdf-memory/users/u1/documents/search",
                          params={"tags": "tax"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "search failed"

    def test_search_service_exception(self, client):
        client.service.search_by_tags.side_effect = RuntimeError("boom")
        resp = client.get("/pdf-memory/users/u1/documents/search",
                          params={"tags": "tax"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /health
# ============================================================================

class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/pdf-memory/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["lancedb_connected"] is True
        assert body["table_available"] is True

    def test_health_service_down(self, client):
        class _Boom:
            table_name = "t"

            @property
            def lancedb_handler(self):
                raise RuntimeError("db down")

        app.dependency_overrides[get_pdf_memory_service] = lambda: _Boom()
        resp = client.get("/pdf-memory/health")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Internal error"


# ============================================================================
# get_pdf_memory_service lazy init
# ============================================================================

class TestServiceFactory:
    def test_lazy_init_and_cache(self):
        with patch.object(mod, "_pdf_memory_service", None), \
                patch.object(mod, "get_lancedb_handler", return_value=MagicMock()), \
                patch.object(mod, "PDFMemoryIntegration") as integ_cls:
            svc = MagicMock()
            integ_cls.return_value = svc
            assert get_pdf_memory_service() is svc
            assert mod._pdf_memory_service is svc
            assert get_pdf_memory_service() is svc
            integ_cls.assert_called_once()
