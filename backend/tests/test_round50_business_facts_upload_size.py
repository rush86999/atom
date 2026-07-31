"""
Round 50 — Business facts upload: unbounded file read (OOM DoS)
(Red-Green-Refactor).

POST /api/admin/governance/facts/upload reads the ENTIRE upload into memory
with no size cap — R21 capped document_ingestion /parse + /upload but missed
this mounted admin endpoint. A multi-GB upload exhausts worker memory (OOM
denial of service) and then feeds the whole blob to the OCR/LLM fact
extraction pipeline. Fix mirrors R21: MAX_UPLOAD_BYTES cap checked on the
declared size AND the actual byte count before processing.
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


def make_client(monkeypatch):
    from api.admin.business_facts_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
        id="u-50", email="admin@example.com", role="admin"
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


class TestBusinessFactsUploadSizeLimit:
    def test_oversized_upload_rejected(self, monkeypatch):
        monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")
        client = make_client(monkeypatch)

        resp = client.post(
            "/api/admin/governance/facts/upload",
            files={"file": ("big.pdf", b"x" * 4096, "application/pdf")},
        )
        assert resp.status_code == 422, (
            "Oversized upload must be rejected — endpoint reads unbounded "
            f"content into memory (got {resp.status_code})"
        )
        assert "size" in resp.text.lower() or "exceeds" in resp.text.lower()

    def test_oversized_upload_rejected_with_default_cap(self, monkeypatch):
        """Same rejection with no env override (50 MiB default)."""
        monkeypatch.delenv("MAX_UPLOAD_BYTES", raising=False)
        client = make_client(monkeypatch)

        resp = client.post(
            "/api/admin/governance/facts/upload",
            files={"file": ("big.pdf", b"x" * (60 * 1024 * 1024), "application/pdf")},
        )
        assert resp.status_code == 422

    def test_small_upload_still_processed(self, monkeypatch):
        """Regression guard: legitimate uploads still reach extraction."""
        monkeypatch.setenv("MAX_UPLOAD_BYTES", "1048576")
        client = make_client(monkeypatch)

        from core.policy_fact_extractor import ExtractionResult

        result = ExtractionResult(
            facts=[], source_document="ok.pdf", extraction_time=0.01
        )
        extractor = AsyncMock()
        extractor.extract_facts_from_document.return_value = result

        monkeypatch.setattr(
            "api.admin.business_facts_routes.get_policy_fact_extractor",
            lambda workspace_id: extractor,
        )
        wm = AsyncMock()
        wm.bulk_record_facts.return_value = 0
        monkeypatch.setattr(
            "api.admin.business_facts_routes.WorldModelService",
            lambda workspace_id: wm,
        )
        # Imported inside upload_and_extract — patch at source module.
        storage = MagicMock()
        storage.upload_file.return_value = "s3://bucket/ok.pdf"
        monkeypatch.setattr("core.storage.get_storage_service", lambda: storage)

        resp = client.post(
            "/api/admin/governance/facts/upload",
            files={"file": ("ok.pdf", b"%PDF-1.4 small", "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
        extractor.extract_facts_from_document.assert_awaited_once()

    def test_upload_source_enforces_size_limit(self):
        """Source-level guard mirroring R21's inspection test."""
        import inspect

        from api.admin import business_facts_routes as mod

        src = inspect.getsource(mod.upload_and_extract)
        assert (
            "MAX_UPLOAD_BYTES" in src
            or "MAX_FILE_SIZE" in src
            or "file.size" in src
            or "len(content)" in src
        ), (
            "upload_and_extract reads the entire upload into memory with no "
            "size check — OOM denial of service via large file upload"
        )
