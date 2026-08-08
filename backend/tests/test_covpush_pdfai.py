"""
Coverage-push tests for PDF memory integration, PDF OCR service, Atom AI
integration and Atom Video AI service. TDD: failing tests first, then minimal
fixes in the four assigned modules.
"""

import asyncio
import base64
import io
import json
import os
import sqlite3
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest
from PIL import Image

import integrations.pdf_processing.pdf_memory_integration as pdf_memory_integration
from integrations.pdf_processing.pdf_memory_integration import (
    PDFMemoryIntegration,
)
from integrations.pdf_processing.pdf_ocr_service import PDFOCRService
from integrations.atom_ai_integration import (
    AIConversationContext,
    AIConversationManager,
    AtomAIIntegration,
    CrossPlatformAIManager,
    IntelligentSearchManager,
    WorkflowIntelligenceManager,
)
from integrations.atom_video_ai_service import (
    AtomVideoAIService,
    VideoAnalysis,
    VideoContent,
    VideoFormat,
    VideoModelType,
    VideoRequest,
    VideoResolution,
    VideoSummary,
    VideoTaskType,
    VideoResponse,
)

SAMPLE_PDF = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
190
%%EOF
"""


def make_processing_result(**overrides):
    result = {
        "processing_summary": {
            "best_method": "basic_pdf",
            "used_ocr": False,
            "total_pages": 2,
            "total_characters": 1500,
        },
        "extracted_content": {"text": "alpha bravo charlie " * 100, "text_ratio": 0.8},
        "file_metadata": {"filename": "report.pdf", "size_bytes": 2048},
    }
    result.update(overrides)
    return result


def make_lancedb_handler():
    handler = MagicMock()
    handler.list_tables = Mock(return_value=[])
    handler.create_table = Mock()
    handler.get_table = Mock(return_value=MagicMock())
    handler.embed_text = Mock(return_value=[0.1] * 768)
    handler.search = Mock(return_value=[])
    return handler


def create_simple_db_schema(db_path):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pdf_documents (
            doc_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            filename TEXT,
            page_count INTEGER,
            total_chars INTEGER,
            pdf_type TEXT,
            processing_method TEXT,
            extracted_text TEXT,
            created_at TEXT,
            source_uri TEXT,
            tags TEXT
        )
    """)
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS pdf_documents_fts
        USING fts5(doc_id, extracted_text, content='pdf_documents', content_rowid='rowid')
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS pdf_documents_ai
        AFTER INSERT ON pdf_documents BEGIN
            INSERT INTO pdf_documents_fts(rowid, doc_id, extracted_text)
            VALUES (new.rowid, new.doc_id, new.extracted_text);
        END
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS pdf_documents_ad
        AFTER DELETE ON pdf_documents BEGIN
            INSERT INTO pdf_documents_fts(pdf_documents_fts, rowid, doc_id, extracted_text)
            VALUES ('delete', old.rowid, old.doc_id, old.extracted_text);
        END
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_pdf_documents_tags ON pdf_documents(tags)"
    )
    conn.commit()
    conn.close()


@pytest.fixture
def mem_service(tmp_path):
    with patch.object(PDFMemoryIntegration, "_init_simple_db", autospec=True):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
    db_path = str(tmp_path / "pdf_simple.db")
    create_simple_db_schema(db_path)
    service._simple_db_path = db_path
    return service


# ---------------------------------------------------------------- memory init

class TestPDFMemoryInit:
    def test_init_without_lancedb(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        assert service.table_name == "pdf_documents"
        assert service.use_byok is False
        assert service._simple_db_path

    def test_init_with_lancedb_creates_table(self):
        handler = make_lancedb_handler()
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        handler.list_tables.assert_called_once()
        handler.create_table.assert_called_once()
        assert service.lancedb_handler is handler

    def test_init_existing_table(self):
        handler = make_lancedb_handler()
        handler.list_tables = Mock(return_value=["pdf_documents"])
        PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        handler.create_table.assert_not_called()

    def test_init_lancedb_error_swallowed(self):
        handler = make_lancedb_handler()
        handler.list_tables = Mock(side_effect=RuntimeError("boom"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        assert service.lancedb_handler is handler

    def test_init_byok_available(self):
        with patch(
            "integrations.pdf_processing.pdf_memory_integration.get_byok_manager",
            return_value=MagicMock(),
        ) as mgr:
            service = PDFMemoryIntegration(
                lancedb_handler=None, use_byok=True
            )
            mgr.assert_called_once()
            assert service.use_byok is True
            assert service.byok_manager is not None

    def test_init_byok_failure_disables(self):
        with patch(
            "integrations.pdf_processing.pdf_memory_integration.get_byok_manager",
            side_effect=RuntimeError("no byok"),
        ):
            service = PDFMemoryIntegration(
                lancedb_handler=None, use_byok=True
            )
            assert service.use_byok is False

    def test_get_byok_status(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        status = service.get_byok_status()
        assert status["byok_integrated"] is False
        assert status["tracking_enabled"] is False


# ------------------------------------------------------------------ memory store

class TestPDFMemoryStore:
    @pytest.mark.asyncio
    async def test_store_processed_pdf_simple_only(self, mem_service):
        result = await mem_service.store_processed_pdf(
            "user1", make_processing_result(), source_uri="s3://x/report.pdf",
            tags=["finance"], metadata={"dept": "sales"},
        )
        assert result["success"] is True
        assert result["storage_methods"] == ["simple_format"]
        doc = await mem_service.get_document("user1", result["doc_id"])
        assert doc["filename"] == "report.pdf"
        assert doc["page_count"] == 2
        assert doc["tags"] == []

    @pytest.mark.asyncio
    async def test_store_processed_pdf_with_lancedb(self):
        handler = make_lancedb_handler()
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        result = await service.store_processed_pdf(
            "user1", make_processing_result(), source_uri="u", tags=["t"]
        )
        assert result["success"] is True
        assert "lancedb" in result["storage_methods"]
        table = handler.get_table.return_value
        assert table.add.call_count == 1

    @pytest.mark.asyncio
    async def test_store_processed_pdf_scanned_ocr_type(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        result = await service.store_processed_pdf(
            "user1", make_processing_result(
                processing_summary={"used_ocr": True, "best_method": "tesseract",
                                    "total_pages": 1, "total_characters": 10},
                extracted_content={"text": "x", "text_ratio": 0.0},
            )
        )
        assert result["document_info"]["pdf_type"] == "scanned"

    @pytest.mark.asyncio
    async def test_store_processed_pdf_byok_tracking(self):
        byok = MagicMock()
        byok.track_usage = Mock()
        with patch(
            "integrations.pdf_processing.pdf_memory_integration.get_byok_manager",
            return_value=byok,
        ):
            service = PDFMemoryIntegration(lancedb_handler=None, use_byok=True)
            await service.store_processed_pdf(
                "user1",
                make_processing_result(
                    processing_summary={
                        "best_method": "openai_vision",
                        "used_ocr": True,
                        "total_pages": 1,
                        "total_characters": 500,
                    }
                ),
            )
            byok.track_usage.assert_called_once()
            args = byok.track_usage.call_args[1]
            assert args["provider_id"] == "openai"
            assert args["tokens_used"] == 125

    @pytest.mark.asyncio
    async def test_store_processed_pdf_byok_tracking_error_swallowed(self):
        byok = MagicMock()
        byok.track_usage = Mock(side_effect=RuntimeError("track failed"))
        with patch(
            "integrations.pdf_processing.pdf_memory_integration.get_byok_manager",
            return_value=byok,
        ):
            service = PDFMemoryIntegration(lancedb_handler=None, use_byok=True)
            result = await service.store_processed_pdf("user1", make_processing_result())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_store_processed_pdf_error_returns_failure(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._store_simple_format = AsyncMock(
            side_effect=RuntimeError("store failed")
        )
        result = await service.store_processed_pdf("user1", make_processing_result())
        assert result["success"] is False
        assert "store failed" in result["error"]

    @pytest.mark.asyncio
    async def test_store_lancedb_empty_text_skipped(self):
        handler = make_lancedb_handler()
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        document_data = {
            "doc_id": "d1", "user_id": "u", "extracted_text": "",
            "filename": "f", "file_size": 1, "page_count": 1, "total_chars": 0,
            "processing_method": "m", "pdf_type": "searchable", "metadata": "{}",
            "created_at": datetime.now(), "updated_at": datetime.now(),
            "source_uri": "", "tags": [],
        }
        await service._store_in_lancedb(document_data)
        handler.get_table.return_value.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_lancedb_error_raises(self):
        handler = make_lancedb_handler()
        handler.embed_text = Mock(side_effect=RuntimeError("embed failed"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        document_data = {
            "doc_id": "d1", "user_id": "u", "extracted_text": "lots of text",
            "filename": "f", "file_size": 1, "page_count": 1, "total_chars": 10,
            "processing_method": "m", "pdf_type": "searchable", "metadata": "{}",
            "created_at": datetime.now(), "updated_at": datetime.now(),
            "source_uri": "", "tags": [],
        }
        with pytest.raises(RuntimeError):
            await service._store_in_lancedb(document_data)

    @pytest.mark.asyncio
    async def test_store_simple_format_no_db_path(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = None
        result = await service._store_simple_format({"doc_id": "d"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_store_simple_format_db_error(self, tmp_path):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = str(tmp_path / "nonexistent" / "x.db")
        result = await service._store_simple_format(
            {"doc_id": "d", "user_id": "u"}
        )
        assert result["success"] is False

    def test_determine_pdf_type(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        assert (
            service._determine_pdf_type(
                {"processing_summary": {"used_ocr": True}}
            )
            == "scanned"
        )
        assert (
            service._determine_pdf_type(
                {"processing_summary": {}, "extracted_content": {"text_ratio": 0.9}}
            )
            == "searchable"
        )
        assert (
            service._determine_pdf_type(
                {"processing_summary": {}, "extracted_content": {"text_ratio": 0.5}}
            )
            == "mixed"
        )
        assert (
            service._determine_pdf_type(
                {"processing_summary": {}, "extracted_content": {"text_ratio": 0.1}}
            )
            == "scanned"
        )

    def test_serialize_metadata(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        assert service._serialize_metadata({"a": 1}) == '{"a": 1}'
        assert service._serialize_metadata({"a": object()}) == "{}"

    def test_parse_metadata(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        assert service._parse_metadata('{"a": 1}') == {"a": 1}
        assert service._parse_metadata("not json") == {}

    def test_map_processing_method_to_provider(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        assert service._map_processing_method_to_provider("", False) is None
        assert (
            service._map_processing_method_to_provider("openai_vision", False)
            == "openai"
        )
        assert service._map_processing_method_to_provider("tesseract", False) == "openai"
        assert service._map_processing_method_to_provider("easyocr", False) == "openai"
        assert service._map_processing_method_to_provider("basic_pdf", False) == "openai"
        assert service._map_processing_method_to_provider("weird", True) == "openai"
        assert service._map_processing_method_to_provider("weird", False) is None

    def test_sliding_window_chunks(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        assert service._create_sliding_window_chunks("") == []
        text = "x" * 2500
        chunks = service._create_sliding_window_chunks(text, 1000, 200)
        assert chunks[0] == "x" * 1000
        assert [len(c) for c in chunks] == [1000, 1000, 900]


# ------------------------------------------------------------------ memory search

class TestPDFMemorySearch:
    @pytest.mark.asyncio
    async def test_search_lancedb_with_filters(self):
        handler = make_lancedb_handler()
        handler.search = Mock(return_value=[
            {"doc_id": "d1", "filename": "a.pdf", "_distance": 0.2,
             "page_count": 2, "total_chars": 100, "pdf_type": "searchable",
             "extracted_text": "alpha beta gamma delta", "created_at": "t",
             "source_uri": "u"},
            {"doc_id": "d1", "filename": "a.pdf", "_distance": 0.1,
             "page_count": 2, "total_chars": 100, "pdf_type": "searchable",
             "extracted_text": "delta epsilon zeta", "created_at": "t",
             "source_uri": "u"},
            {"doc_id": "d2", "filename": "b.pdf", "_distance": 0.5,
             "page_count": 1, "total_chars": 50, "pdf_type": "scanned",
             "extracted_text": "theta", "created_at": "t", "source_uri": "u"},
        ])
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        results = await service.search_pdfs(
            "u", "alpha", limit=5, filters={"pdf_type": "searchable", "tags": ["a", "b"]}
        )
        assert len(results) == 2
        assert results[0]["doc_id"] == "d1"
        assert results[0]["similarity_score"] == 0.1
        assert "delta" in results[0]["excerpt"]

    @pytest.mark.asyncio
    async def test_search_falls_back_to_simple(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau",
            "created_at": datetime.now(), "source_uri": "u",
        })
        results = await mem_service.search_pdfs("u", "alpha")
        assert len(results) == 1
        assert results[0]["doc_id"] == "d1"

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self):
        handler = make_lancedb_handler()
        handler.search = Mock(side_effect=RuntimeError("search boom"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        results = await service.search_pdfs("u", "alpha")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_byok_tracking(self):
        byok = MagicMock()
        byok.get_optimal_provider = Mock(return_value="openai")
        byok.track_usage = Mock()
        with patch(
            "integrations.pdf_processing.pdf_memory_integration.get_byok_manager",
            return_value=byok,
        ):
            service = PDFMemoryIntegration(lancedb_handler=None, use_byok=True)
            await service.search_pdfs("u", "find me something")
            byok.track_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_byok_tracking_errors(self):
        byok = MagicMock()
        byok.get_optimal_provider = Mock(return_value="openai")
        byok.track_usage = Mock(side_effect=RuntimeError("usage failed"))
        with patch(
            "integrations.pdf_processing.pdf_memory_integration.get_byok_manager",
            return_value=byok,
        ):
            service = PDFMemoryIntegration(lancedb_handler=None, use_byok=True)
            results = await service.search_pdfs("u", "find me something")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_in_lancedb_error(self):
        handler = make_lancedb_handler()
        handler.get_table = Mock(side_effect=RuntimeError("no table"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        results = await service._search_in_lancedb("u", "q", 5, 0.7, None)
        assert results == []

    @pytest.mark.asyncio
    async def test_simple_search_no_db(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = None
        assert await service._simple_search("u", "q", 5, None) == []

    @pytest.mark.asyncio
    async def test_simple_search_with_filters(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf",
            "extracted_text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau",
            "created_at": datetime.now(), "source_uri": "u",
        })
        await mem_service._store_simple_format({
            "doc_id": "d2", "user_id": "u", "filename": "b.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "scanned",
            "processing_method": "tesseract",
            "extracted_text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau",
            "created_at": datetime.now(), "source_uri": "u",
        })
        results = await mem_service._simple_search(
            "u", "alpha", 5, {"pdf_type": "searchable", "processing_method": "basic_pdf"}
        )
        assert len(results) == 1
        assert results[0]["doc_id"] == "d1"

    @pytest.mark.asyncio
    async def test_simple_search_error(self, tmp_path):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = str(tmp_path / "t.db")
        conn = sqlite3.connect(service._simple_db_path)
        conn.execute("CREATE TABLE pdf_documents (doc_id TEXT PRIMARY KEY, user_id TEXT)")
        conn.execute("INSERT INTO pdf_documents VALUES ('d', 'u')")
        conn.commit()
        conn.close()
        assert await service._simple_search("u", "alpha", 5, None) == []

    def test_get_text_excerpt(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        long_text = "alpha beta gamma delta " * 100
        assert service._get_text_excerpt("", "q") == ""
        assert service._get_text_excerpt("ab", "q") == "ab"
        excerpt = service._get_text_excerpt(long_text, "gamma")
        assert "..." in excerpt
        assert service._get_text_excerpt("a" * 500, "zzz") == "a" * 200 + "..."
        assert service._get_text_excerpt("x" * 500, None) == "x" * 200 + "..."


# ------------------------------------------------------------------ document ops

class TestPDFMemoryDocumentOps:
    @pytest.mark.asyncio
    async def test_get_document_lancedb_hit(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = [{
            "doc_id": "d1", "filename": "a.pdf", "page_count": 2,
            "total_chars": 100, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "source_uri": "u", "tags": ["t"], "created_at": "c", "file_size": 10,
            "metadata": '{"k": "v"}',
        }]
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        doc = await service.get_document("u", "d1")
        assert doc["doc_id"] == "d1"
        assert doc["metadata"] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_get_document_simple_fallback(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": datetime.now(), "source_uri": "u",
        })
        doc = await mem_service.get_document("u", "d1")
        assert doc["doc_id"] == "d1"
        assert await mem_service.get_document("u", "missing") is None

    @pytest.mark.asyncio
    async def test_get_document_error(self):
        handler = make_lancedb_handler()
        handler.get_table = Mock(side_effect=RuntimeError("boom"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        assert await service.get_document("u", "d1") is None

    @pytest.mark.asyncio
    async def test_get_simple_document_no_path(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = None
        assert await service._get_simple_document("u", "d") is None

    @pytest.mark.asyncio
    async def test_delete_document_both(self, mem_service):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.delete = Mock()
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        service._simple_db_path = mem_service._simple_db_path
        await service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": datetime.now(), "source_uri": "u",
        })
        result = await service.delete_document("u", "d1")
        assert result["success"] is True
        assert "lancedb" in result["deleted_from"]
        assert "simple_storage" in result["deleted_from"]
        fake_table.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_lancedb_error(self, tmp_path):
        handler = make_lancedb_handler()
        handler.get_table = Mock(side_effect=RuntimeError("no table"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        service._simple_db_path = str(tmp_path / "t.db")
        result = await service.delete_document("u", "d1")
        assert result["success"] is True
        assert "lancedb" not in result["deleted_from"]

    @pytest.mark.asyncio
    async def test_delete_simple_document_no_path(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = None
        result = await service._delete_simple_document("u", "d")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_simple_document_error(self, tmp_path):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = str(tmp_path / "nonexistent" / "x.db")
        result = await service._delete_simple_document("u", "d")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_documents_lancedb(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = [
            {"doc_id": "d1", "filename": "a.pdf", "page_count": 2,
             "total_chars": 100, "pdf_type": "searchable",
             "processing_method": "basic_pdf", "extracted_text": "txt",
             "source_uri": "u", "tags": ["t"], "created_at": "c", "file_size": 10,
             "metadata": "{}"},
            {"doc_id": "d2", "filename": "b.pdf", "page_count": 1,
             "total_chars": 100, "pdf_type": "scanned",
             "processing_method": "tesseract", "extracted_text": "txt",
             "source_uri": "u", "tags": [], "created_at": "c", "file_size": 10,
             "metadata": "{}"},
        ]
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        result = await service.list_documents(
            "u", limit=1, pdf_type="searchable", date_from="2020-01-01",
            date_to="2030-01-01", tags=["t"],
        )
        assert result["success"] is True
        assert result["total"] == 1
        assert len(result["documents"]) == 1

    @pytest.mark.asyncio
    async def test_list_documents_sqlite(self, mem_service):
        for i in range(3):
            await mem_service._store_simple_format({
                "doc_id": f"d{i}", "user_id": "u", "filename": f"{i}.pdf",
                "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
                "processing_method": "basic_pdf", "extracted_text": "txt",
                "created_at": datetime.now(), "source_uri": "u",
            })
        result = await mem_service.list_documents("u", limit=2, offset=1, pdf_type="searchable")
        assert result["success"] is True
        assert result["total"] == 3
        assert len(result["documents"]) == 2

    @pytest.mark.asyncio
    async def test_list_documents_error(self):
        handler = make_lancedb_handler()
        handler.get_table = Mock(side_effect=RuntimeError("boom"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        result = await service.list_documents("u")
        assert result["success"] is False


# ------------------------------------------------------------------ tags

class TestPDFMemoryTags:
    @pytest.mark.asyncio
    async def test_update_tags_sqlite(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": datetime.now(), "source_uri": "u",
        })
        result = await mem_service.update_document_tags("u", "d1", [" alpha ", "finance"])
        assert result["success"] is True
        assert result["tags"] == ["alpha", "finance"]
        tags = await mem_service.get_document_tags("d1", "u")
        assert tags["tags"] == ["alpha", "finance"]
        assert tags["count"] == 2

    @pytest.mark.asyncio
    async def test_update_tags_validation(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        result = await service.update_document_tags("u", "d1", "notalist")
        assert result["success"] is False
        result = await service.update_document_tags("u", "d1", ["x" * 60])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_update_tags_lancedb(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = [{"doc_id": "d1"}]
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        result = await service.update_document_tags("u", "d1", ["a"])
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_tags_lancedb_not_found(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = []
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        result = await service.update_document_tags("u", "d1", ["a"])
        assert result["success"] is False
        assert result["error"] == "Document not found"

    @pytest.mark.asyncio
    async def test_update_tags_sqlite_not_found(self, mem_service):
        result = await mem_service.update_document_tags("u", "nope", ["a"])
        assert result["success"] is False
        assert result["error"] == "Document not found"

    @pytest.mark.asyncio
    async def test_update_tags_error(self, tmp_path):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = str(tmp_path / "nonexistent" / "x.db")
        result = await service.update_document_tags("u", "d", ["a"])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_document_tags_not_found(self, mem_service):
        result = await mem_service.get_document_tags("d1", "u")
        assert result["success"] is False
        assert result["error"] == "Document not found"

    @pytest.mark.asyncio
    async def test_get_document_tags_no_db(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = None
        result = await service.get_document_tags("d1", "u")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_document_tags(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": datetime.now(), "source_uri": "u",
        })
        await mem_service.update_document_tags("u", "d1", ["a", "b", "c"])
        result = await mem_service.delete_document_tags("d1", "u", ["a", "c"])
        assert result["success"] is True
        assert result["deleted_count"] == 2
        assert result["remaining_tags"] == ["b"]
        tags = await mem_service.get_document_tags("d1", "u")
        assert tags["tags"] == ["b"]

    @pytest.mark.asyncio
    async def test_delete_document_tags_not_found(self, mem_service):
        result = await mem_service.delete_document_tags("d1", "u", ["a"])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_document_tags_no_db(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = None
        result = await service.delete_document_tags("d1", "u", ["a"])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_by_tags(self, mem_service):
        for doc_id in ("d1", "d2", "d3"):
            await mem_service._store_simple_format({
                "doc_id": doc_id, "user_id": "u", "filename": f"{doc_id}.pdf",
                "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
                "processing_method": "basic_pdf", "extracted_text": "txt",
                "created_at": datetime.now(), "source_uri": "u",
            })
        await mem_service.update_document_tags("u", "d1", ["finance", "q1"])
        await mem_service.update_document_tags("u", "d2", ["finance"])
        await mem_service.update_document_tags("u", "d3", ["hr"])
        any_match = await mem_service.search_by_tags("u", ["finance", "q1"], match_all=False)
        assert any_match["count"] == 2
        all_match = await mem_service.search_by_tags("u", ["finance", "q1"], match_all=True)
        assert all_match["count"] == 1
        assert all_match["documents"][0]["doc_id"] == "d1"

    @pytest.mark.asyncio
    async def test_search_by_tags_no_db(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = None
        result = await service.search_by_tags("u", ["a"])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_by_tags_invalid_json_skipped(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": datetime.now(), "source_uri": "u",
        })
        conn = sqlite3.connect(mem_service._simple_db_path)
        conn.execute("UPDATE pdf_documents SET tags = 'not json' WHERE doc_id = 'd1'")
        conn.commit()
        conn.close()
        result = await mem_service.search_by_tags("u", ["finance"])
        assert result["success"] is True
        assert result["count"] == 0


# ------------------------------------------------------------------ stats + misc

class TestPDFMemoryStats:
    @pytest.mark.asyncio
    async def test_get_user_document_stats(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = [
            {"page_count": 2, "total_chars": 100, "file_size": 10,
             "pdf_type": "searchable"},
            {"page_count": 1, "total_chars": 50, "file_size": 20,
             "pdf_type": "scanned"},
        ]
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        stats = await service.get_user_document_stats("u")
        assert stats["total_documents"] == 2
        assert stats["total_pages"] == 3
        assert stats["total_characters"] == 150
        assert stats["pdf_types"] == {"searchable": 1, "scanned": 1}
        assert stats["storage_size_bytes"] == 30

    @pytest.mark.asyncio
    async def test_get_user_document_stats_no_lancedb(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        stats = await service.get_user_document_stats("u")
        assert stats["total_documents"] == 0

    @pytest.mark.asyncio
    async def test_get_user_document_stats_error(self):
        handler = make_lancedb_handler()
        handler.get_table = Mock(side_effect=RuntimeError("boom"))
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        stats = await service.get_user_document_stats("u")
        assert stats["total_documents"] == 0
        assert "error" in stats


# ================================================================ OCR service

class TestOCRInit:
    def test_init_defaults(self):
        service = PDFOCRService()
        assert service.tesseract_path is None
        assert service.easyocr_languages == ["en"]
        assert service.tenant_id == "default"
        assert "basic_pdf" in service.service_status
        assert service.service_status["basic_pdf"] is True

    def test_init_custom(self):
        service = PDFOCRService(
            tesseract_path="/usr/bin/tesseract",
            easyocr_languages=["en", "fr"],
            tenant_id="t1",
        )
        assert service.tesseract_path == "/usr/bin/tesseract"
        assert service.easyocr_languages == ["en", "fr"]
        assert service.tenant_id == "t1"

    def test_service_status_reflects_readers(self):
        service = PDFOCRService()
        for key in ("docling", "tesseract", "easyocr", "openai_vision"):
            assert key in service.service_status
        assert service.service_status["openai_vision"] == (
            "ai_vision" in service.ocr_readers
        )


class TestOCRProcess:
    @pytest.mark.asyncio
    async def test_process_pdf_from_bytes(self):
        service = PDFOCRService()
        result = await service.process_pdf(SAMPLE_PDF, use_ocr=False, extract_images=False)
        assert result["success"] is True
        assert result["processing_summary"]["best_method"] == "basic_pdf"
        assert result["processing_summary"]["used_ocr"] is False

    @pytest.mark.asyncio
    async def test_process_pdf_from_path(self, tmp_path):
        pdf_path = tmp_path / "sample.pdf"
        pdf_path.write_bytes(SAMPLE_PDF)
        service = PDFOCRService()
        result = await service.process_pdf(str(pdf_path), use_ocr=False, extract_images=False)
        assert result["success"] is True
        result = await service.process_pdf(Path(pdf_path), use_ocr=False, extract_images=False)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_pdf_uses_ocr_when_needed(self):
        service = PDFOCRService()
        with patch.object(
            service, "_extract_basic_text", new=AsyncMock(return_value={
                "method": "basic_pdf", "extracted_text": "tiny", "page_texts": [],
                "page_count": 1, "total_chars": 4, "text_ratio": 0.0, "success": True,
            })
        ), patch.object(service, "_process_with_ocr", new=AsyncMock(return_value={
            "best_result": {"method": "tesseract", "extracted_text": "OCR text",
                            "page_texts": [], "page_count": 1, "total_chars": 8,
                            "success": True},
            "methods_tried": ["tesseract"], "success": True,
        })) as mock_ocr:
            result = await service.process_pdf(b"pdf", extract_images=False)
            mock_ocr.assert_awaited_once()
            assert result["processing_summary"]["used_ocr"] is True
            assert result["processing_summary"]["best_method"] == "tesseract"
            assert result["extracted_content"]["text"] == "OCR text"

    @pytest.mark.asyncio
    async def test_process_pdf_extracts_images(self):
        service = PDFOCRService()
        with patch.object(
            service, "_extract_basic_text", new=AsyncMock(return_value={
                "method": "basic_pdf", "extracted_text": "text", "page_texts": [],
                "page_count": 1, "total_chars": 4, "text_ratio": 0.9, "success": True,
            })
        ), patch.object(service, "_extract_and_process_images", new=AsyncMock(return_value={
            "images_found": 2, "image_descriptions": [], "success": True,
        })):
            result = await service.process_pdf(b"pdf")
            assert result["extracted_content"]["images"]["images_found"] == 2

    @pytest.mark.asyncio
    async def test_process_pdf_error(self):
        service = PDFOCRService()
        with patch.object(
            service, "_extract_basic_text", new=AsyncMock(side_effect=RuntimeError("boom"))
        ):
            result = await service.process_pdf(b"pdf")
            assert result["success"] is False
            assert "boom" in result["error"]

    def test_create_error_result(self):
        service = PDFOCRService()
        result = service._create_error_result("broken")
        assert result["success"] is False
        assert result["error"] == "broken"
        assert result["processing_summary"]["total_pages"] == 0
        assert result["extracted_content"]["text"] == ""


class TestOCRExtractBasic:
    @pytest.mark.asyncio
    async def test_extract_basic_text_success(self):
        service = PDFOCRService()
        result = await service._extract_basic_text(SAMPLE_PDF)
        assert result["success"] is True
        assert result["page_count"] == 1
        assert result["total_chars"] == 0
        assert result["text_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_extract_basic_text_error(self):
        service = PDFOCRService()
        result = await service._extract_basic_text(b"not a pdf at all")
        assert result["success"] is False
        assert "error" in result


class TestOCROcrPipeline:
    @pytest.mark.asyncio
    async def test_process_with_ocr_cascade_success(self):
        service = PDFOCRService()
        service.ocr_readers = {"tesseract": MagicMock(), "easyocr": MagicMock()}
        with patch.object(
            service, "_run_ocr_method",
            new=AsyncMock(return_value={
                "success": True, "total_chars": 50, "extracted_text": "abc",
                "page_texts": [], "page_count": 1, "method": "tesseract",
            }),
        ) as run:
            result = await service._process_with_ocr(b"pdf", "cascade", False)
            assert result["success"] is True
            assert result["best_result"]["method"] == "tesseract"
            assert result["methods_tried"] == ["easyocr"]
            run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_with_ocr_cascade_empty_result_keeps_trying(self):
        service = PDFOCRService()
        service.ocr_readers = {"tesseract": MagicMock(), "easyocr": MagicMock()}
        calls = {
            "easyocr": {"success": True, "total_chars": 0, "method": "easyocr"},
            "tesseract": {"success": True, "total_chars": 99, "method": "tesseract"},
        }

        async def fake_run(method, data):
            return calls[method]

        with patch.object(service, "_run_ocr_method", new=fake_run):
            result = await service._process_with_ocr(b"pdf", "cascade", False)
            assert result["best_result"]["method"] == "tesseract"
            assert result["methods_tried"] == ["easyocr", "tesseract"]

    @pytest.mark.asyncio
    async def test_process_with_ocr_cascade_method_failure(self):
        service = PDFOCRService()
        service.ocr_readers = {"tesseract": MagicMock(), "easyocr": MagicMock()}

        async def fake_run(method, data):
            if method == "easyocr":
                raise RuntimeError("easyocr died")
            return {"success": True, "total_chars": 5, "method": "tesseract"}

        with patch.object(service, "_run_ocr_method", new=fake_run):
            result = await service._process_with_ocr(b"pdf", "cascade", False)
            assert result["methods_tried"] == ["easyocr_failed", "tesseract"]
            assert result["best_result"]["method"] == "tesseract"

    @pytest.mark.asyncio
    async def test_process_with_ocr_cascade_all_fail(self):
        service = PDFOCRService()
        service.ocr_readers = {"tesseract": MagicMock()}

        async def fake_run(method, data):
            return {"success": False, "total_chars": 0, "method": method}

        with patch.object(service, "_run_ocr_method", new=fake_run):
            result = await service._process_with_ocr(b"pdf", "cascade", False)
            assert result["success"] is False
            assert result["best_result"] is None

    @pytest.mark.asyncio
    async def test_process_with_ocr_parallel_picks_most_text(self):
        service = PDFOCRService()
        service.ocr_readers = {"tesseract": MagicMock(), "easyocr": MagicMock()}
        results = {
            "tesseract": {"success": True, "total_chars": 10, "method": "tesseract"},
            "easyocr": {"success": True, "total_chars": 100, "method": "easyocr"},
        }

        async def fake_run(method, data):
            return results[method]

        with patch.object(service, "_run_ocr_method", new=fake_run):
            result = await service._process_with_ocr(b"pdf", "parallel", False)
            assert result["best_result"]["method"] == "easyocr"

    @pytest.mark.asyncio
    async def test_process_with_ocr_parallel_with_failure(self):
        service = PDFOCRService()
        service.ocr_readers = {"tesseract": MagicMock(), "easyocr": MagicMock()}

        async def fake_run(method, data):
            if method == "easyocr":
                raise RuntimeError("boom")
            return {"success": True, "total_chars": 10, "method": "tesseract"}

        with patch.object(service, "_run_ocr_method", new=fake_run):
            result = await service._process_with_ocr(b"pdf", "parallel", False)
            assert result["methods_tried"] == ["easyocr_failed", "tesseract"]

    def test_get_available_ocr_methods_priority(self):
        service = PDFOCRService()
        service.ocr_readers = {"docling": MagicMock(), "tesseract": MagicMock()}
        methods = service._get_available_ocr_methods(False)
        assert methods == ["docling", "tesseract"]

    def test_get_available_ocr_methods_byok_optimization(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        service.byok_manager.get_optimal_provider = Mock(return_value="openai")
        service.ocr_readers = {"ai_vision": MagicMock()}
        methods = service._get_available_ocr_methods(True)
        assert "openai_vision" in methods

    def test_get_available_ocr_methods_byok_error(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        service.byok_manager.get_optimal_provider = Mock(
            side_effect=RuntimeError("byok down")
        )
        service.ocr_readers = {"ai_vision": MagicMock()}
        methods = service._get_available_ocr_methods(True)
        assert methods == ["openai_vision"]

    @pytest.mark.asyncio
    async def test_run_ocr_method_unknown(self):
        service = PDFOCRService()
        with pytest.raises(ValueError):
            await service._run_ocr_method("bogus", b"pdf")


class TestOCROcrMethodImpls:
    @pytest.mark.asyncio
    async def test_ocr_with_docling_success(self):
        service = PDFOCRService()
        processor = AsyncMock()
        processor.process_pdf = AsyncMock(return_value={
            "success": True, "extracted_text": "docling text",
            "page_texts": [{"page": 1, "text": "docling text"}],
            "page_count": 1, "total_chars": 12, "tables": [],
        })
        service.ocr_readers = {"docling": processor}
        result = await service._ocr_with_docling(b"pdf")
        assert result["success"] is True
        assert result["method"] == "docling"
        assert result["extracted_text"] == "docling text"

    @pytest.mark.asyncio
    async def test_ocr_with_docling_failure(self):
        service = PDFOCRService()
        processor = AsyncMock()
        processor.process_pdf = AsyncMock(return_value={"success": False, "error": "nope"})
        service.ocr_readers = {"docling": processor}
        result = await service._ocr_with_docling(b"pdf")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ocr_with_docling_not_available(self):
        service = PDFOCRService()
        service.ocr_readers = {}
        with pytest.raises(RuntimeError):
            await service._ocr_with_docling(b"pdf")

    @pytest.mark.asyncio
    async def test_ocr_with_tesseract_success(self):
        service = PDFOCRService()
        fake_tesseract = MagicMock()
        fake_tesseract.image_to_string = Mock(side_effect=["page one text", "page two text"])
        service.ocr_readers = {"tesseract": fake_tesseract}
        img = Image.new("RGB", (10, 10), color="white")
        with patch.object(service, "_pdf_to_images", new=AsyncMock(return_value=[img, img])), \
             patch("integrations.pdf_processing.pdf_ocr_service.pytesseract", fake_tesseract):
            result = await service._ocr_with_tesseract(b"pdf")
            assert result["success"] is True
            assert result["total_chars"] == len("page one text") + len("page two text")
            assert result["page_count"] == 2

    @pytest.mark.asyncio
    async def test_ocr_with_tesseract_failure(self):
        service = PDFOCRService()
        service.ocr_readers = {"tesseract": MagicMock()}
        with patch.object(service, "_pdf_to_images", new=AsyncMock(side_effect=RuntimeError("no pdf"))):
            result = await service._ocr_with_tesseract(b"pdf")
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ocr_with_tesseract_not_available(self):
        service = PDFOCRService()
        service.ocr_readers = {}
        with pytest.raises(RuntimeError):
            await service._ocr_with_tesseract(b"pdf")

    @pytest.mark.asyncio
    async def test_ocr_with_easyocr_success(self):
        service = PDFOCRService()
        reader = MagicMock()
        reader.readtext = Mock(return_value=[([1], "hello", 0.9), ([2], "world", 0.8)])
        service.ocr_readers = {"easyocr": reader}
        img = Image.new("RGB", (10, 10), color="white")
        with patch.object(service, "_pdf_to_images", new=AsyncMock(return_value=[img])):
            result = await service._ocr_with_easyocr(b"pdf")
            assert result["success"] is True
            assert result["extracted_text"] == "hello world"

    @pytest.mark.asyncio
    async def test_ocr_with_easyocr_no_numpy(self):
        service = PDFOCRService()
        service.ocr_readers = {"easyocr": MagicMock()}
        img = Image.new("RGB", (10, 10), color="white")
        with patch.object(service, "_pdf_to_images", new=AsyncMock(return_value=[img])), \
             patch("integrations.pdf_processing.pdf_ocr_service.NUMPY_AVAILABLE", False):
            result = await service._ocr_with_easyocr(b"pdf")
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ocr_with_easyocr_failure(self):
        service = PDFOCRService()
        service.ocr_readers = {"easyocr": MagicMock()}
        with patch.object(service, "_pdf_to_images", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service._ocr_with_easyocr(b"pdf")
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ocr_with_ai_vision_success(self):
        service = PDFOCRService()
        service.llm_service = MagicMock()
        service.llm_service.generate_completion = AsyncMock(return_value={
            "success": True, "content": "vision text",
        })
        img = Image.new("RGB", (10, 10), color="white")
        with patch.object(service, "_pdf_to_images", new=AsyncMock(return_value=[img])):
            result = await service._ocr_with_ai_vision(b"pdf")
            assert result["success"] is True
            assert result["method"] == "openai_vision"
            assert result["extracted_text"] == "vision text"
            assert result["image_descriptions"][0]["page"] == 1
            call_args = service.llm_service.generate_completion.call_args
            assert call_args.kwargs["messages"][0]["content"][1]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_ocr_with_ai_vision_llm_failure(self):
        service = PDFOCRService()
        service.llm_service = MagicMock()
        service.llm_service.generate_completion = AsyncMock(
            return_value={"success": False, "error": "llm down"}
        )
        img = Image.new("RGB", (10, 10), color="white")
        with patch.object(service, "_pdf_to_images", new=AsyncMock(return_value=[img])):
            result = await service._ocr_with_ai_vision(b"pdf")
            assert result["success"] is True
            assert result["extracted_text"] == ""

    @pytest.mark.asyncio
    async def test_ocr_with_ai_vision_exception(self):
        service = PDFOCRService()
        service.llm_service = MagicMock()
        service.llm_service.generate_completion = AsyncMock(
            side_effect=RuntimeError("vision exploded")
        )
        img = Image.new("RGB", (10, 10), color="white")
        with patch.object(service, "_pdf_to_images", new=AsyncMock(return_value=[img])):
            result = await service._ocr_with_ai_vision(b"pdf")
            assert result["success"] is False
            assert "vision exploded" in result["error"]

    @pytest.mark.asyncio
    async def test_ocr_with_ai_vision_not_available(self):
        service = PDFOCRService()
        service.llm_service = None
        with pytest.raises(RuntimeError):
            await service._ocr_with_ai_vision(b"pdf")


class TestOCRByok:
    def test_get_openai_api_key_byok(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        service.byok_manager.get_api_key = Mock(return_value="byok-key")
        assert service._get_openai_api_key() == "byok-key"

    def test_get_openai_api_key_byok_failure_then_attr(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        service.byok_manager.get_api_key = Mock(side_effect=RuntimeError("down"))
        service.openai_api_key = "attr-key"
        assert service._get_openai_api_key() == "attr-key"

    def test_get_openai_api_key_env(self, monkeypatch):
        service = PDFOCRService()
        service.use_byok = False
        service.openai_api_key = None
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        assert service._get_openai_api_key() == "env-key"

    @pytest.mark.asyncio
    async def test_optimize_provider_selection_disabled(self):
        service = PDFOCRService()
        service.use_byok = False
        service.byok_manager = None
        result = await service._optimize_provider_selection(True, "cascade")
        assert result["optimized"] is False

    @pytest.mark.asyncio
    async def test_optimize_provider_selection_success(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        service.byok_manager.get_optimal_provider = Mock(return_value="gemini")
        result = await service._optimize_provider_selection(True, "parallel")
        assert result["optimized"] is True
        assert result["task_type"] == "image_comprehension"
        result = await service._optimize_provider_selection(False, "cascade")
        assert result["task_type"] == "pdf_ocr"

    @pytest.mark.asyncio
    async def test_optimize_provider_selection_error(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        service.byok_manager.get_optimal_provider = Mock(side_effect=RuntimeError("boom"))
        result = await service._optimize_provider_selection(True, "cascade")
        assert result["optimized"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_track_byok_usage_disabled(self):
        service = PDFOCRService()
        result = await service._track_byok_usage({}, False)
        assert result is None

    @pytest.mark.asyncio
    async def test_track_byok_usage_success(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        result = await service._track_byok_usage(
            {"best_result": {"method": "tesseract", "total_chars": 400}}, False
        )
        service.byok_manager.track_usage.assert_called_once()
        args = service.byok_manager.track_usage.call_args[1]
        assert args["provider_id"] == "openai"
        assert args["tokens_used"] == 100

    @pytest.mark.asyncio
    async def test_track_byok_usage_no_provider_mapping(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        await service._track_byok_usage({"best_result": {"method": "basic_pdf"}}, False)
        service.byok_manager.track_usage.assert_not_called()

    @pytest.mark.asyncio
    async def test_track_byok_usage_error(self):
        service = PDFOCRService()
        service.use_byok = True
        service.byok_manager = MagicMock()
        service.byok_manager.track_usage = Mock(side_effect=RuntimeError("boom"))
        await service._track_byok_usage({"best_result": {"method": "tesseract"}}, False)

    def test_map_method_to_provider(self):
        service = PDFOCRService()
        assert service._map_method_to_provider("openai_vision") == "openai"
        assert service._map_method_to_provider("tesseract") == "openai"
        assert service._map_method_to_provider("easyocr") == "openai"
        assert service._map_method_to_provider("basic_pdf") is None
        assert service._map_method_to_provider("other") is None


class TestOCRPDFToImages:
    @pytest.mark.asyncio
    async def test_pdf_to_images_uses_pdf2image(self, monkeypatch):
        service = PDFOCRService()
        img = Image.new("RGB", (50, 50), color="white")

        def fake_convert_from_bytes(*args, **kwargs):
            return [img, img]

        pdf2image_mod = types.ModuleType("pdf2image")
        pdf2image_mod.convert_from_bytes = fake_convert_from_bytes
        monkeypatch.setitem(sys.modules, "pdf2image", pdf2image_mod)
        with patch("asyncio.to_thread", new=AsyncMock(side_effect=fake_convert_from_bytes)):
            images = await service._pdf_to_images(b"pdf")
        assert len(images) == 2

    @pytest.mark.asyncio
    async def test_pdf_to_images_uses_fitz(self, monkeypatch):
        service = PDFOCRService()

        jpeg_bytes = io.BytesIO()
        Image.new("RGB", (30, 30), color="blue").save(jpeg_bytes, format="JPEG")
        jpeg_data = jpeg_bytes.getvalue()

        class FakePix:
            def tobytes(self, fmt="jpeg"):
                return jpeg_data

        class FakePage:
            def get_pixmap(self, matrix=None):
                return FakePix()

        class FakeDoc:
            page_count = 2

            def __getitem__(self, idx):
                return FakePage()

            def close(self):
                pass

        class FakeMatrix:
            def __init__(self, a, b):
                pass

        fitz_mod = types.ModuleType("fitz")
        fitz_mod.Matrix = FakeMatrix
        fitz_mod.open = Mock(return_value=FakeDoc())
        monkeypatch.setitem(sys.modules, "fitz", fitz_mod)
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        images = await service._pdf_to_images(b"pdf")
        assert len(images) == 2
        assert isinstance(images[0], Image.Image)

    @pytest.mark.asyncio
    async def test_pdf_to_images_placeholder(self, monkeypatch):
        service = PDFOCRService()
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        monkeypatch.delitem(sys.modules, "fitz", raising=False)
        images = await service._pdf_to_images(SAMPLE_PDF)
        assert len(images) == 1
        assert isinstance(images[0], Image.Image)
        assert images[0].size == (612, 792)

    @pytest.mark.asyncio
    async def test_pdf_to_images_placeholder_mediabox_error(self, monkeypatch):
        service = PDFOCRService()
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        monkeypatch.delitem(sys.modules, "fitz", raising=False)

        class BadBox:
            @property
            def width(self):
                raise AttributeError("no width")

            @property
            def height(self):
                raise AttributeError("no height")

        class FakePage:
            mediabox = BadBox()

            def extract_text(self):
                return "hello world\nsecond line\n"

        fake_reader = MagicMock()
        fake_reader.pages = [FakePage()]
        with patch(
            "integrations.pdf_processing.pdf_ocr_service.PyPDF2.PdfReader",
            return_value=fake_reader,
        ), patch(
            "PIL.ImageFont.truetype", side_effect=OSError("no font")
        ):
            images = await service._pdf_to_images(SAMPLE_PDF)
        assert len(images) == 1
        assert images[0].size == (800, 1000)

    @pytest.mark.asyncio
    async def test_pdf_to_images_total_failure(self, monkeypatch):
        service = PDFOCRService()
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        monkeypatch.delitem(sys.modules, "fitz", raising=False)
        with patch(
            "integrations.pdf_processing.pdf_ocr_service.PyPDF2.PdfReader",
            side_effect=RuntimeError("corrupt"),
        ):
            images = await service._pdf_to_images(b"garbage")
        assert images == []


class TestOCRExtractImages:
    @pytest.mark.asyncio
    async def test_extract_and_process_images_fitz_path(self, monkeypatch):
        service = PDFOCRService()

        png_bytes = io.BytesIO()
        Image.new("RGB", (600, 400), color="green").save(png_bytes, format="PNG")
        png_data = png_bytes.getvalue()

        class FakePage:
            def get_images(self, full=True):
                return [(1, 0, 0, 0, 0, 0, 0), (2, 0, 0, 0, 0, 0, 0)]

        class FakeDoc:
            page_count = 1

            def __getitem__(self, idx):
                return FakePage()

            def extract_image(self, xref):
                if xref == 1:
                    return {"ext": "png", "width": 600, "height": 400, "image": png_data}
                return {"ext": "png", "width": 100, "height": 100, "image": png_data}

            def close(self):
                pass

        fitz_mod = types.ModuleType("fitz")
        fitz_mod.open = Mock(return_value=FakeDoc())
        monkeypatch.setitem(sys.modules, "fitz", fitz_mod)
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)

        result = await service._extract_and_process_images(b"pdf", False)
        assert result["success"] is True
        assert result["images_found"] == 2
        assert result["image_descriptions"][0]["description"] == (
            "Large image (possibly photo or chart)"
        )
        assert result["image_descriptions"][1]["description"] == (
            "Small image (possibly icon or bullet point)"
        )

    @pytest.mark.asyncio
    async def test_extract_images_advanced_comprehension(self, monkeypatch):
        service = PDFOCRService()
        png_bytes = io.BytesIO()
        Image.new("RGB", (300, 200), color="green").save(png_bytes, format="PNG")
        png_data = png_bytes.getvalue()

        class FakePage:
            def get_images(self, full=True):
                return [(1, 0, 0, 0, 0, 0, 0)]

        class FakeDoc:
            page_count = 1

            def __getitem__(self, idx):
                return FakePage()

            def extract_image(self, xref):
                return {"ext": "png", "width": 300, "height": 200, "image": png_data}

            def close(self):
                pass

        fitz_mod = types.ModuleType("fitz")
        fitz_mod.open = Mock(return_value=FakeDoc())
        monkeypatch.setitem(sys.modules, "fitz", fitz_mod)
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)

        service.use_byok = True
        handler = MagicMock()
        handler._get_coordinated_vision_description = AsyncMock(
            return_value="An important chart"
        )
        service.byok_manager = MagicMock()
        service.byok_manager.get_handler = Mock(return_value=handler)

        result = await service._extract_and_process_images(b"pdf", True)
        assert result["success"] is True
        assert result["image_descriptions"][0]["ai_description"] == "An important chart"

    @pytest.mark.asyncio
    async def test_extract_images_advanced_comprehension_failure(self, monkeypatch):
        service = PDFOCRService()
        png_bytes = io.BytesIO()
        Image.new("RGB", (300, 200), color="green").save(png_bytes, format="PNG")
        png_data = png_bytes.getvalue()

        class FakePage:
            def get_images(self, full=True):
                return [(1, 0, 0, 0, 0, 0, 0)]

        class FakeDoc:
            page_count = 1

            def __getitem__(self, idx):
                return FakePage()

            def extract_image(self, xref):
                return {"ext": "png", "width": 300, "height": 200, "image": png_data}

            def close(self):
                pass

        fitz_mod = types.ModuleType("fitz")
        fitz_mod.open = Mock(return_value=FakeDoc())
        monkeypatch.setitem(sys.modules, "fitz", fitz_mod)
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)

        service.use_byok = True
        handler = MagicMock()
        handler._get_coordinated_vision_description = AsyncMock(
            side_effect=RuntimeError("vision down")
        )
        service.byok_manager = MagicMock()
        service.byok_manager.get_handler = Mock(return_value=handler)

        result = await service._extract_and_process_images(b"pdf", True)
        assert "ai_description" not in result["image_descriptions"][0]
        assert result["image_descriptions"][0]["description"] == (
            "Medium image (possibly icon or diagram)"
        )

    @pytest.mark.asyncio
    async def test_extract_images_pypdf2_fallback(self, monkeypatch):
        service = PDFOCRService()
        monkeypatch.delitem(sys.modules, "fitz", raising=False)
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)

        xobj = MagicMock()
        xobj.get_object.return_value = {"/Im0": {"/Subtype": "/Image"}}
        resources = {"/XObject": xobj}
        page = {"/Resources": resources}
        fake_reader = MagicMock()
        fake_reader.pages = [page]
        with patch(
            "integrations.pdf_processing.pdf_ocr_service.PyPDF2.PdfReader",
            return_value=fake_reader,
        ):
            result = await service._extract_and_process_images(b"pdf", False)
        assert result["success"] is True
        assert result["images_found"] == 1
        assert "limited info" in result["image_descriptions"][0]["description"]

    @pytest.mark.asyncio
    async def test_extract_images_pypdf2_fallback_error(self, monkeypatch):
        service = PDFOCRService()
        monkeypatch.delitem(sys.modules, "fitz", raising=False)
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        with patch(
            "integrations.pdf_processing.pdf_ocr_service.PyPDF2.PdfReader",
            side_effect=RuntimeError("corrupt"),
        ):
            result = await service._extract_and_process_images(b"garbage", False)
        assert result["success"] is True
        assert result["images_found"] == 0


class TestOCRCombine:
    def test_combine_results_with_ocr(self):
        service = PDFOCRService()
        basic = {"method": "basic_pdf", "success": True, "extracted_text": "",
                 "page_texts": [], "page_count": 0, "total_chars": 0}
        ocr = {
            "success": True,
            "methods_tried": ["tesseract"],
            "best_result": {
                "method": "tesseract", "extracted_text": "OCR text",
                "page_texts": [{"page": 1, "text": "OCR text"}],
                "page_count": 1, "total_chars": 8,
            },
        }
        result = service._combine_results(basic, ocr, {"images_found": 1}, True)
        assert result["processing_summary"]["best_method"] == "tesseract"
        assert result["processing_summary"]["used_ocr"] is True
        assert result["extracted_content"]["text"] == "OCR text"
        assert result["success"] is True

    def test_combine_results_without_ocr(self):
        service = PDFOCRService()
        basic = {"method": "basic_pdf", "success": True, "extracted_text": "plain",
                 "page_texts": [], "page_count": 1, "total_chars": 5}
        result = service._combine_results(basic, None, None, False)
        assert result["processing_summary"]["best_method"] == "basic_pdf"
        assert result["processing_summary"]["ocr_methods_tried"] == []
        assert result["extracted_content"]["images"] == {}
        assert result["success"] is True


# ============================================================ Atom AI integration

class FakeLLM:
    """Fake LLMService-like object exposing generate_completion."""

    def __init__(self, responses=None, response_dict=None):
        self.responses = list(responses or [])
        self.response_dict = response_dict or {}
        self.calls = []

    async def generate_completion(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.responses:
            return self.responses.pop(0)
        return {"success": True, "content": "default response"}

    async def chat_completion(self, messages, system_prompt=None):
        self.calls.append((messages, {"system_prompt": system_prompt}))
        if self.responses:
            return self.responses.pop(0)
        return "default response"


def make_integration(llm=None, **services):
    config = {
        "llm_service": llm,
        "atom_memory_service": services.get("memory"),
        "atom_search_service": services.get("search"),
        "atom_workflow_service": services.get("workflow"),
        "atom_ingestion_pipeline": services.get("ingestion"),
    }
    return AtomAIIntegration(config)


def make_message(**overrides):
    message = {
        "id": "m1", "content": "hello world", "html_content": "<p>hi</p>",
        "platform": "slack", "workspace_id": "ws", "channel_id": "ch",
        "user_id": "u1", "user_name": "bob", "user_display_name": "Bob",
        "user_avatar": "a", "timestamp": "t", "thread_id": None,
        "reply_to_id": None, "message_type": "message", "is_edited": False,
        "is_pinned": False, "is_bot": False, "is_webhook": False,
        "reactions": [], "attachments": [], "embeds": [], "mentions": [],
        "files": [], "integration_data": {}, "metadata": {},
    }
    message.update(overrides)
    return message


def make_workspace(**overrides):
    workspace = {
        "id": "slack_ws1", "name": "Team", "platform": "slack",
        "type": "public", "status": "active", "member_count": 120,
        "channel_count": 25, "icon_url": "i", "description": "d",
        "capabilities": {"voice_chat": True}, "integration_data": {},
    }
    workspace.update(overrides)
    return workspace


def make_channel(**overrides):
    channel = {
        "id": "slack_ch1", "name": "general", "display_name": "General",
        "type": "public", "platform": "slack", "workspace_id": "slack_ws1",
        "workspace_name": "Team", "status": "active", "member_count": 30,
        "message_count": 600, "unread_count": 5, "is_private": False,
        "is_text": True, "is_voice": False, "capabilities": {},
        "integration_data": {},
    }
    channel.update(overrides)
    return channel


def fake_platform_integration(**overrides):
    integration = MagicMock()
    integration.get_unified_workspaces = AsyncMock(return_value=[])
    integration.get_unified_channels = AsyncMock(return_value=[])
    integration.get_unified_messages = AsyncMock(return_value=[])
    integration.send_unified_message = AsyncMock(return_value={"ok": True, "message_id": "x"})
    for k, v in overrides.items():
        setattr(integration, k, v)
    return integration


class TestAtomAIIntegrationInit:
    def test_init_with_config_services(self):
        memory = MagicMock()
        integration = make_integration(
            llm=FakeLLM(), memory=memory,
            search=MagicMock(), workflow=MagicMock(), ingestion=MagicMock(),
        )
        assert integration.atom_memory is memory
        assert integration.is_initialized is False
        assert integration.platform_integrations["slack"] is None
        assert integration.conversation_manager is not None
        assert integration.search_manager is not None
        assert integration.workflow_intelligence is not None
        assert integration.cross_platform_ai is not None

    def test_init_creates_llm_service_when_missing(self):
        with patch("integrations.atom_ai_integration.LLMService") as mock_llm_cls:
            integration = AtomAIIntegration({})
            mock_llm_cls.assert_called_once_with(workspace_id="default")
            assert integration.llm_service is mock_llm_cls.return_value


class TestAtomAIIntegrationLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        search_mgr = MagicMock()
        search_mgr.initialize = AsyncMock()
        llm = FakeLLM()
        integration = make_integration(
            llm=llm, memory=MagicMock(), search=MagicMock()
        )
        integration.search_manager = search_mgr
        integration.workflow_intelligence.initialize = AsyncMock()
        integration.cross_platform_ai.initialize = AsyncMock()
        ok = await integration.initialize()
        assert ok is True
        assert integration.is_initialized is True
        assert "intelligent_search" in integration.active_ai_features
        search_mgr.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_missing_services(self):
        integration = make_integration(llm=None)
        ok = await integration.initialize()
        assert ok is False

    @pytest.mark.asyncio
    async def test_initialize_error(self):
        llm = FakeLLM()
        integration = make_integration(llm=llm, memory=MagicMock(), search=MagicMock())
        integration.search_manager.initialize = AsyncMock(
            side_effect=RuntimeError("init boom")
        )
        ok = await integration.initialize()
        assert ok is False


class TestAtomAIWorkspaces:
    @pytest.mark.asyncio
    async def test_get_intelligent_workspaces(self):
        integration = make_integration(llm=FakeLLM())
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                get_unified_workspaces=AsyncMock(return_value=[make_workspace()])
            ),
            "teams": None,
        }
        workspaces = await integration.get_intelligent_workspaces("u1")
        assert len(workspaces) == 1
        assert workspaces[0]["ai_features"]["voice_analysis"] is True
        assert workspaces[0]["ai_insights"]["engagement_level"] == "high"
        assert workspaces[0]["ai_settings"]["analysis_level"] == "comprehensive"
        assert integration.intelligent_workspaces == workspaces

    @pytest.mark.asyncio
    async def test_get_intelligent_workspaces_error(self):
        integration = make_integration(llm=FakeLLM())
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                get_unified_workspaces=AsyncMock(
                    side_effect=RuntimeError("platform down")
                )
            ),
        }
        assert await integration.get_intelligent_workspaces("u1") == []

    @pytest.mark.asyncio
    async def test_get_intelligent_channels(self):
        integration = make_integration(llm=FakeLLM())
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                get_unified_channels=AsyncMock(return_value=[make_channel()])
            ),
        }
        channels = await integration.get_intelligent_channels("slack_ws1", "u1")
        assert len(channels) == 1
        assert channels[0]["ai_insights"]["engagement_level"] == "high"
        assert channels[0]["ai_features"]["voice_analysis"] is False

    @pytest.mark.asyncio
    async def test_get_intelligent_channels_unknown_platform(self):
        integration = make_integration(llm=FakeLLM())
        integration.platform_integrations = {"slack": fake_platform_integration()}
        assert await integration.get_intelligent_channels("discord_ws1", "u1") == []

    @pytest.mark.asyncio
    async def test_get_intelligent_channels_error(self):
        integration = make_integration(llm=FakeLLM())
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                get_unified_channels=AsyncMock(
                    side_effect=RuntimeError("platform down")
                )
            ),
        }
        assert await integration.get_intelligent_channels("slack_ws1", "u1") == []

    @pytest.mark.asyncio
    async def test_get_intelligent_messages(self):
        llm = FakeLLM(responses=['{"sentiment": "positive", "sentiment_score": 0.8, "key_topics": ["ai"]}'])
        integration = make_integration(llm=llm)
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                get_unified_messages=AsyncMock(return_value=[make_message()])
            ),
        }
        messages = await integration.get_intelligent_messages(
            "slack_ws1", "slack_ch1", limit=10
        )
        assert len(messages) == 1
        assert messages[0]["ai_analysis"]["sentiment"] == "positive"
        assert messages[0]["ai_analysis"]["key_topics"] == ["ai"]
        assert messages[0]["ai_features"]["translation_target"] is None

    @pytest.mark.asyncio
    async def test_get_intelligent_messages_unparsable_analysis(self):
        llm = FakeLLM(responses=["not json at all"])
        integration = make_integration(llm=llm)
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                get_unified_messages=AsyncMock(return_value=[make_message()])
            ),
        }
        messages = await integration.get_intelligent_messages(
            "slack_ws1", "slack_ch1", options={"translation_language": "fr"}
        )
        assert messages[0]["ai_analysis"]["sentiment"] == "neutral"
        assert messages[0]["ai_features"]["translation_target"] == "fr"

    @pytest.mark.asyncio
    async def test_get_intelligent_messages_error(self):
        integration = make_integration(llm=FakeLLM())
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                get_unified_messages=AsyncMock(
                    side_effect=RuntimeError("platform down")
                )
            ),
        }
        assert await integration.get_intelligent_messages("slack_ws1", "slack_ch1") == []


class TestAtomAIActions:
    @pytest.mark.asyncio
    async def test_intelligent_search(self):
        search_mgr = MagicMock()
        search_mgr.search = AsyncMock(return_value=[{"id": "r1"}])
        integration = make_integration(llm=FakeLLM())
        integration.search_manager = search_mgr
        results = await integration.intelligent_search("query", user_id="u1")
        assert results == [{"id": "r1"}]
        search_mgr.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_intelligent_search_error(self):
        search_mgr = MagicMock()
        search_mgr.search = AsyncMock(side_effect=RuntimeError("search down"))
        integration = make_integration(llm=FakeLLM())
        integration.search_manager = search_mgr
        assert await integration.intelligent_search("q") == []

    @pytest.mark.asyncio
    async def test_send_intelligent_message(self):
        llm = FakeLLM(responses=["enhanced content here"])
        integration = make_integration(llm=llm)
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                send_unified_message=AsyncMock(
                    return_value={"ok": True, "message_id": "m1", "channel_id": "c"}
                )
            ),
        }
        result = await integration.send_intelligent_message(
            "slack_ws1", "slack_ch1", "hello"
        )
        assert result["ok"] is True
        sent = integration.platform_integrations["slack"].send_unified_message
        sent_args = sent.call_args[0]
        assert sent_args[2] == "enhanced content here"

    @pytest.mark.asyncio
    async def test_send_intelligent_message_unsupported_platform(self):
        integration = make_integration(llm=FakeLLM())
        result = await integration.send_intelligent_message("ws", "unknown_ch", "hi")
        assert result["ok"] is False
        assert result["error"] == "Unsupported platform"

    @pytest.mark.asyncio
    async def test_send_intelligent_message_error(self):
        integration = make_integration(llm=FakeLLM())
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                send_unified_message=AsyncMock(
                    side_effect=RuntimeError("send failed")
                )
            ),
        }
        result = await integration.send_intelligent_message("ws", "slack_ch", "hi")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_send_intelligent_message_skips_analysis(self):
        llm = FakeLLM(responses=["enhanced"])
        integration = make_integration(llm=llm)
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                send_unified_message=AsyncMock(return_value={"ok": False})
            ),
        }
        result = await integration.send_intelligent_message(
            "slack_ws1", "slack_ch1", "hello", {"analyze_after_send": True}
        )
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_send_intelligent_message_stores_analysis(self):
        llm = FakeLLM(responses=["enhanced"])
        memory = MagicMock()
        memory.store = AsyncMock()
        integration = make_integration(llm=llm, memory=memory)
        integration.platform_integrations = {
            "slack": fake_platform_integration(
                send_unified_message=AsyncMock(
                    return_value={"ok": True, "message_id": "m1"}
                )
            ),
        }
        await integration.send_intelligent_message(
            "slack_ws1", "slack_ch1", "hello", {"analyze_after_send": True}
        )
        memory.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_intelligent_workflow(self):
        workflow = MagicMock()
        workflow.create_workflow = AsyncMock(return_value={"ok": True, "id": "w1"})
        integration = make_integration(llm=FakeLLM(responses=['{"suggestions": []}']), workflow=workflow)
        result = await integration.create_intelligent_workflow({"name": "wf"})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_create_intelligent_workflow_no_service(self):
        integration = make_integration(llm=FakeLLM())
        result = await integration.create_intelligent_workflow({"name": "wf"})
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_create_intelligent_workflow_error(self):
        workflow = MagicMock()
        workflow.create_workflow = AsyncMock(side_effect=RuntimeError("wf down"))
        integration = make_integration(llm=FakeLLM(), workflow=workflow)
        result = await integration.create_intelligent_workflow({"name": "wf"})
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_get_intelligent_analytics_parsed(self):
        llm = FakeLLM(responses=['{"insight": "growth"}'])
        integration = make_integration(llm=llm)
        result = await integration.get_intelligent_analytics("messages", "7d")
        assert result == {"insight": "growth"}

    @pytest.mark.asyncio
    async def test_get_intelligent_analytics_unparsable(self):
        llm = FakeLLM(responses=["plain text insights"])
        integration = make_integration(llm=llm)
        result = await integration.get_intelligent_analytics("messages", "7d")
        assert result == {"analysis": "plain text insights"}

    @pytest.mark.asyncio
    async def test_get_intelligent_analytics_error(self):
        llm = FakeLLM(responses=[])
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        integration = make_integration(llm=llm)
        result = await integration.get_intelligent_analytics("messages", "7d")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_process_natural_language_command(self):
        llm = FakeLLM(responses=['{"action": "send"}'])
        integration = make_integration(llm=llm)
        result = await integration.process_natural_language_command(
            "send a message", "u1", platform="slack"
        )
        assert result == {"action": "send"}

    @pytest.mark.asyncio
    async def test_process_natural_language_command_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        integration = make_integration(llm=llm)
        result = await integration.process_natural_language_command("cmd", "u1")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_start_ai_conversation(self):
        integration = make_integration(llm=FakeLLM())
        conv_id = await integration.start_ai_conversation("u1", "slack", "slack_ws1")
        assert conv_id.startswith("ai_conv_u1_slack_slack_ws1_")
        conv_id = await integration.start_ai_conversation("u1", "slack")
        assert conv_id.startswith("ai_conv_u1_slack_")

    @pytest.mark.asyncio
    async def test_continue_ai_conversation(self):
        llm = FakeLLM(responses=["AI reply"])
        integration = make_integration(llm=llm)
        conv_id = await integration.start_ai_conversation("u1", "slack")
        result = await integration.continue_ai_conversation(conv_id, "hello", "u1")
        assert result["ok"] is True
        assert result["response"] == "AI reply"
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_continue_ai_conversation_error(self):
        integration = make_integration(llm=FakeLLM())
        result = await integration.continue_ai_conversation("missing", "hi", "u1")
        assert result["ok"] is False
        assert result["error"] == "Conversation not found"


class TestAtomAIHelpers:
    def test_get_platform_from_workspace(self):
        integration = make_integration(llm=FakeLLM())
        assert integration._get_platform_from_workspace("slack_1") == "slack"
        assert integration._get_platform_from_workspace("teams_1") == "teams"
        assert integration._get_platform_from_workspace("google_chat_1") == "google_chat"
        assert integration._get_platform_from_workspace("discord_1") == "discord"
        assert integration._get_platform_from_workspace("other") == "unknown"

    def test_get_platform_from_channel(self):
        integration = make_integration(llm=FakeLLM())
        assert integration._get_platform_from_channel("slack_c") == "slack"
        assert integration._get_platform_from_channel("teams_c") == "teams"
        assert integration._get_platform_from_channel("google_chat_c") == "google_chat"
        assert integration._get_platform_from_channel("discord_c") == "discord"
        assert integration._get_platform_from_channel("zz") == "unknown"

    @pytest.mark.asyncio
    async def test_engagement_levels(self):
        integration = make_integration(llm=FakeLLM())
        assert await integration._calculate_engagement_level(make_workspace()) == "high"
        assert (
            await integration._calculate_engagement_level(
                make_workspace(member_count=60, channel_count=12)
            )
            == "medium"
        )
        assert (
            await integration._calculate_engagement_level(
                make_workspace(member_count=5, channel_count=2)
            )
            == "low"
        )

    @pytest.mark.asyncio
    async def test_mock_insight_helpers(self):
        integration = make_integration(llm=FakeLLM())
        ws = make_workspace()
        trends = await integration._get_activity_trends(ws)
        assert trends["trend"] == "increasing"
        patterns = await integration._get_communication_patterns(ws)
        assert patterns["response_times"]["average"] == 5.2
        prediction = await integration._predict_activity(ws)
        assert prediction["next_7_days"]["messages"] == 1200
        actions = await integration._get_recommended_actions(ws)
        assert len(actions) == 4

    @pytest.mark.asyncio
    async def test_channel_engagement_levels(self):
        integration = make_integration(llm=FakeLLM())
        assert (
            await integration._calculate_channel_engagement(make_channel())
            == "high"
        )
        assert (
            await integration._calculate_channel_engagement(
                make_channel(message_count=250, member_count=15)
            )
            == "medium"
        )
        assert (
            await integration._calculate_channel_engagement(
                make_channel(message_count=10, member_count=2)
            )
            == "low"
        )

    @pytest.mark.asyncio
    async def test_channel_insight_helpers(self):
        integration = make_integration(llm=FakeLLM())
        channel = make_channel()
        topics = await integration._get_channel_topic_trends(channel)
        assert len(topics) == 3
        evolution = await integration._get_sentiment_evolution(channel)
        assert evolution["trend"] == "improving"
        peak = await integration._get_peak_activity_times(channel)
        assert len(peak) == 3
        volume = await integration._predict_message_volume(channel)
        assert volume["confidence"] == 0.75
        suggestions = await integration._get_channel_suggestions(channel)
        assert len(suggestions) == 4

    @pytest.mark.asyncio
    async def test_message_ai_analysis_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        integration = make_integration(llm=llm)
        analysis = await integration._get_message_ai_analysis(make_message())
        assert analysis["sentiment"] == "neutral"
        assert analysis["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_enhance_content_skipped(self):
        integration = make_integration(llm=FakeLLM())
        content = await integration._enhance_content("raw", {"enhance_content": False})
        assert content == "raw"

    @pytest.mark.asyncio
    async def test_enhance_content_success(self):
        llm = FakeLLM(responses=["polished"])
        integration = make_integration(llm=llm)
        content = await integration._enhance_content("raw", {})
        assert content == "polished"

    @pytest.mark.asyncio
    async def test_enhance_content_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        integration = make_integration(llm=llm)
        content = await integration._enhance_content("raw", {})
        assert content == "raw"

    @pytest.mark.asyncio
    async def test_analyze_message_after_send_skipped(self):
        integration = make_integration(llm=FakeLLM())
        await integration._analyze_message_after_send(
            {"message_id": "m1"}, {"analyze_after_send": False}
        )

    @pytest.mark.asyncio
    async def test_analyze_message_after_send_no_memory(self):
        integration = make_integration(llm=FakeLLM())
        await integration._analyze_message_after_send({"message_id": "m1"}, {})

    @pytest.mark.asyncio
    async def test_analyze_message_after_send_store_error(self):
        memory = MagicMock()
        memory.store = AsyncMock(side_effect=RuntimeError("mem down"))
        integration = make_integration(llm=FakeLLM(), memory=memory)
        await integration._analyze_message_after_send({"message_id": "m1"}, {})


class TestAIConversationManager:
    @pytest.mark.asyncio
    async def test_continue_conversation_missing(self):
        manager = AIConversationManager(FakeLLM())
        result = await manager.continue_conversation("nope", "hi", "u1")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_continue_conversation_ai_failure(self):
        llm = FakeLLM(responses=[""])
        manager = AIConversationManager(llm)
        conv_id = await manager.start_conversation("u1", "slack")
        result = await manager.continue_conversation(conv_id, "hi", "u1")
        assert result["ok"] is False
        assert result["error"] == "AI processing failed"

    @pytest.mark.asyncio
    async def test_continue_conversation_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        manager = AIConversationManager(llm)
        conv_id = await manager.start_conversation("u1", "slack")
        result = await manager.continue_conversation(conv_id, "hi", "u1")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_process_command_json(self):
        llm = FakeLLM(responses=['{"parsed": true}'])
        manager = AIConversationManager(llm)
        result = await manager.process_command("cmd", "u1")
        assert result == {"parsed": True}

    @pytest.mark.asyncio
    async def test_process_command_plain(self):
        llm = FakeLLM(responses=["done"])
        manager = AIConversationManager(llm)
        result = await manager.process_command("cmd", "u1", "ws", "slack")
        assert result == {"ok": True, "response": "done"}

    @pytest.mark.asyncio
    async def test_process_command_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        manager = AIConversationManager(llm)
        result = await manager.process_command("cmd", "u1")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_conversation_context_metadata(self):
        manager = AIConversationManager(FakeLLM())
        conv_id = await manager.start_conversation("u1", "teams", "teams_ws")
        context = manager.conversations[conv_id]
        assert context.metadata["workspace_id"] == "teams_ws"
        assert context.user_id == "u1"


class TestIntelligentSearchManager:
    @pytest.mark.asyncio
    async def test_initialize(self):
        manager = IntelligentSearchManager(FakeLLM(), MagicMock())
        await manager.initialize()
        assert manager.search_index == {"documents": [], "embeddings": [], "metadata": {}}

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        search = MagicMock()
        search.unified_search = AsyncMock(return_value=[])
        manager = IntelligentSearchManager(FakeLLM(), search)
        assert await manager.search("q") == []

    @pytest.mark.asyncio
    async def test_search_ranked(self):
        search = MagicMock()
        search.unified_search = AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])
        llm = FakeLLM(responses=['{"ranked_results": [{"id": "b"}]}'])
        manager = IntelligentSearchManager(llm, search)
        results = await manager.search("q", options={"filters": {}, "limit": 5})
        assert results == [{"id": "b"}]

    @pytest.mark.asyncio
    async def test_search_rank_fallback(self):
        search = MagicMock()
        search.unified_search = AsyncMock(return_value=[{"id": "a"}])
        llm = FakeLLM(responses=["garbage"])
        manager = IntelligentSearchManager(llm, search)
        results = await manager.search("q")
        assert results == [{"id": "a"}]

    @pytest.mark.asyncio
    async def test_search_error(self):
        search = MagicMock()
        search.unified_search = AsyncMock(side_effect=RuntimeError("down"))
        manager = IntelligentSearchManager(FakeLLM(), search)
        assert await manager.search("q") == []

    @pytest.mark.asyncio
    async def test_update_search_index_with_ingestion(self):
        search = MagicMock()
        llm = FakeLLM()
        manager = IntelligentSearchManager(llm, search, atom_ingestion=MagicMock())
        with patch(
            "integrations.atom_ai_integration.IntelligentSearchManager._get_recent_communications",
            new=AsyncMock(return_value=[
                {"id": "c1", "subject": "Weekly report", "body": "Numbers for the team", "sender": "alice"}
            ]),
        ), patch(
            "integrations.atom_ai_integration.IntelligentSearchManager._index_communication",
            new=AsyncMock(),
        ) as index_mock:
            await manager.update_search_index()
            index_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_search_index_error(self):
        manager = IntelligentSearchManager(FakeLLM(), MagicMock(), atom_ingestion=MagicMock())
        with patch(
            "integrations.atom_ai_integration.IntelligentSearchManager._get_recent_communications",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            await manager.update_search_index()

    @pytest.mark.asyncio
    async def test_index_communication_short_content(self):
        manager = IntelligentSearchManager(FakeLLM(), MagicMock())
        await manager._index_communication({"id": "c1", "subject": "x"})

    @pytest.mark.asyncio
    async def test_index_communication_success(self):
        manager = IntelligentSearchManager(FakeLLM(), MagicMock())
        embedding_svc = MagicMock()
        embedding_svc.generate_embedding = AsyncMock(return_value=[0.1, 0.2])
        with patch(
            "core.embedding_service.EmbeddingService",
            return_value=embedding_svc,
        ), patch(
            "core.lancedb_handler.get_lancedb_handler",
            return_value=MagicMock(),
        ) as get_handler:
            await manager._index_communication(
                {"id": "c1", "subject": "Weekly report", "body": "Numbers for the team", "sender": "alice"}
            )
            get_handler.return_value.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_communication_error(self):
        manager = IntelligentSearchManager(FakeLLM(), MagicMock())
        with patch(
            "core.embedding_service.EmbeddingService",
            side_effect=RuntimeError("no embeddings"),
        ):
            await manager._index_communication({"id": "c1", "subject": "Weekly report", "body": "Numbers for the team"})


class TestWorkflowIntelligenceManager:
    @pytest.mark.asyncio
    async def test_initialize(self):
        manager = WorkflowIntelligenceManager(FakeLLM(), MagicMock())
        await manager.initialize()
        assert "approval_patterns" in manager.workflow_patterns

    @pytest.mark.asyncio
    async def test_enhance_workflow_parsed(self):
        llm = FakeLLM(responses=['{"optimize": true}'])
        manager = WorkflowIntelligenceManager(llm, MagicMock())
        result = await manager.enhance_workflow({"name": "wf"})
        assert result["ai_enhancements"] == {"optimize": True}

    @pytest.mark.asyncio
    async def test_enhance_workflow_unparsable(self):
        llm = FakeLLM(responses=["some suggestions text"])
        manager = WorkflowIntelligenceManager(llm, MagicMock())
        result = await manager.enhance_workflow({"name": "wf"})
        assert result["ai_enhancements"] == {"suggestions": "some suggestions text"}

    @pytest.mark.asyncio
    async def test_enhance_workflow_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        manager = WorkflowIntelligenceManager(llm, MagicMock())
        result = await manager.enhance_workflow({"name": "wf"})
        assert result == {"name": "wf"}

    @pytest.mark.asyncio
    async def test_optimize_workflows(self):
        llm = FakeLLM(responses=['{"opt": 1}'])
        manager = WorkflowIntelligenceManager(llm, MagicMock())
        with patch(
            "integrations.atom_ai_integration.WorkflowIntelligenceManager._get_all_workflows",
            new=AsyncMock(return_value=[{"id": "w1"}]),
        ):
            await manager.optimize_workflows()

    @pytest.mark.asyncio
    async def test_optimize_workflows_no_workflow_service(self):
        manager = WorkflowIntelligenceManager(FakeLLM(), None)
        await manager.optimize_workflows()

    @pytest.mark.asyncio
    async def test_optimize_workflows_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        manager = WorkflowIntelligenceManager(llm, MagicMock())
        with patch(
            "integrations.atom_ai_integration.WorkflowIntelligenceManager._get_all_workflows",
            new=AsyncMock(return_value=[{"id": "w1"}]),
        ):
            await manager.optimize_workflows()

    @pytest.mark.asyncio
    async def test_setup_workflow_automation(self):
        manager = WorkflowIntelligenceManager(FakeLLM(), MagicMock())
        await manager.setup_workflow_automation()

    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        manager = WorkflowIntelligenceManager(FakeLLM(), MagicMock())
        await manager.start_monitoring()

    @pytest.mark.asyncio
    async def test_apply_optimizations(self):
        manager = WorkflowIntelligenceManager(FakeLLM(), MagicMock())
        await manager._apply_optimizations({"id": "w1"}, {"x": 1})


class TestCrossPlatformAIManager:
    @pytest.mark.asyncio
    async def test_initialize(self):
        manager = CrossPlatformAIManager(FakeLLM(), {})
        await manager.initialize()
        assert manager.cross_platform_insights["shared_users"] == set()

    @pytest.mark.asyncio
    async def test_synchronize_ai_insights(self):
        llm = FakeLLM(responses=['{"cross": "insight"}'])
        manager = CrossPlatformAIManager(llm, {"slack": MagicMock()})
        await manager.synchronize_ai_insights()
        assert manager.cross_platform_insights == {"cross": "insight"}

    @pytest.mark.asyncio
    async def test_synchronize_ai_insights_unparsable(self):
        llm = FakeLLM(responses=["plain analysis"])
        manager = CrossPlatformAIManager(llm, {"slack": MagicMock()})
        await manager.synchronize_ai_insights()
        assert manager.cross_platform_insights == {"analysis": "plain analysis"}

    @pytest.mark.asyncio
    async def test_synchronize_ai_insights_error(self):
        llm = FakeLLM()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        manager = CrossPlatformAIManager(llm, {"slack": MagicMock()})
        await manager.synchronize_ai_insights()

    @pytest.mark.asyncio
    async def test_get_platform_insights_and_data(self):
        manager = CrossPlatformAIManager(FakeLLM(), {})
        insights = await manager._get_platform_insights("slack", MagicMock())
        assert insights["platform"] == "slack"
        data = await manager._get_platform_data("slack")
        assert data["connected"] is False


# ========================================================= Atom video AI service


def make_video_request(task_type=VideoTaskType.SUMMARIZATION, **overrides):
    req = VideoRequest(
        request_id="req1",
        task_type=task_type,
        model_type=VideoModelType.BLIP,
        video_path=None,
        video_data=b"fake-video-bytes",
        format=VideoFormat.MP4,
        resolution=VideoResolution.HD_720P,
        duration=60.0,
        fps=30.0,
        platform="slack",
        user_id="u1",
        metadata={},
    )
    for k, v in overrides.items():
        setattr(req, k, v)
    return req


class FakeBox:
    def __init__(self, cls, conf, xyxy):
        self.cls = cls
        self.conf = conf
        self.xyxy = np.array([xyxy])

    def tolist(self):
        return list(self.xyxy[0])


class FakeResult:
    def __init__(self, names, boxes):
        self.names = names
        self.boxes = boxes


def make_yolo_mock(detections, names):
    boxes = [FakeBox(c, conf, [0, 0, 10, 10]) for (c, conf) in detections]
    return Mock(return_value=[FakeResult(names, boxes)])


def make_video_service(**config_overrides):
    config = {"enable_enterprise_features": False}
    config.update(config_overrides)
    return AtomVideoAIService(config=config)


class TestVideoInit:
    def test_init_defaults(self):
        service = make_video_service()
        assert service.video_config["max_video_length"] == 3600
        assert service.analytics_metrics["total_video_requests"] == 0
        assert service.performance_metrics["total_processing_time"] == 0.0
        assert service.is_initialized is False

    def test_init_custom_config(self):
        service = make_video_service(
            blip_model="custom/blip", max_video_length=100, security_level="high"
        )
        assert service.video_config["blip_model"] == "custom/blip"
        assert service.video_config["max_video_length"] == 100
        assert service.video_config["security_level"] == "high"

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        service = make_video_service()
        with patch.object(service, "_load_video_models", new=AsyncMock()) as load_mock:
            ok = await service.initialize()
        assert ok is True
        assert service.is_initialized is True
        load_mock.assert_awaited_once()
        assert service.content_moderation_policies["violence"]["threshold"] == 0.6

    @pytest.mark.asyncio
    async def test_initialize_enterprise_features(self):
        service = make_video_service(enable_enterprise_features=True)
        ok = await service.initialize()
        assert ok is True
        assert service.video_retention_policies["meeting_recordings"] == 365
        assert service.security_monitoring["video_anomaly_detection"]["enabled"] is True
        assert service.compliance_monitoring["content_compliance_checking"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_initialize_error(self):
        service = make_video_service()
        with patch.object(service, "_load_video_models", new=AsyncMock(side_effect=RuntimeError("boom"))):
            ok = await service.initialize()
        assert ok is False

    @pytest.mark.asyncio
    async def test_load_video_models_import_error(self):
        service = make_video_service()
        await service._load_video_models()
        assert service.blip_model is None
        assert service.yolo_model is None

    @pytest.mark.asyncio
    async def test_get_service_status(self):
        service = make_video_service()
        status = await service.get_service_status()
        assert status["service"] == "video_ai"
        assert status["status"] == "inactive"
        assert status["models_loaded"]["blip"] is False

    @pytest.mark.asyncio
    async def test_get_service_status_uptime(self):
        service = make_video_service()
        service._start_time = datetime.now().timestamp()
        status = await service.get_service_status()
        assert status["uptime"] >= 0

    @pytest.mark.asyncio
    async def test_close(self):
        service = make_video_service()
        service.blip_model = Mock()
        service.yolo_model = Mock()
        await service.close()
        assert service.blip_model is None
        assert service.yolo_model is None

    def test_create_error_response(self):
        service = make_video_service()
        response = service._create_error_response(make_video_request(), "bad video")
        assert response.success is False
        assert response.metadata == {"error": "bad video"}
        assert response.confidence == 0.0


class TestVideoRequestProcessing:
    @pytest.mark.asyncio
    async def test_process_summarization(self):
        service = make_video_service()
        with patch.object(service, "_summarize_video", new=AsyncMock()) as m:
            response = await service.process_video_request(make_video_request())
        m.assert_awaited_once()
        assert service.analytics_metrics["total_video_requests"] == 1

    @pytest.mark.asyncio
    async def test_process_unsupported_task(self):
        service = make_video_service()
        response = await service.process_video_request(
            make_video_request(task_type=VideoTaskType.EMOTION_DETECTION)
        )
        assert response.success is False
        assert response.metadata["error"] == "Unsupported task type"

    @pytest.mark.asyncio
    async def test_process_enterprise_security_failure(self):
        service = make_video_service(enable_enterprise_features=True)
        service._perform_security_check = AsyncMock(
            return_value={"passed": False, "reason": "blocked"}
        )
        response = await service.process_video_request(make_video_request())
        assert response.success is False
        assert response.metadata["error"] == "blocked"

    @pytest.mark.asyncio
    async def test_process_enterprise_logs_request(self):
        service = make_video_service(enable_enterprise_features=True)
        with patch.object(service, "_summarize_video", new=AsyncMock()) as m:
            await service.process_video_request(make_video_request())
        m.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_task_error(self):
        service = make_video_service()
        with patch.object(service, "_summarize_video", new=AsyncMock(side_effect=RuntimeError("kaboom"))):
            response = await service.process_video_request(make_video_request())
        assert response.success is False
        assert "kaboom" in response.metadata["error"]


class TestVideoTaskMethods:
    @pytest.mark.asyncio
    async def test_summarize_video_no_ai_service(self):
        service = make_video_service()
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        processor = MagicMock()
        processor.return_value = {"pixel_values": np.zeros((1, 3, 10, 10))}
        blip_model = MagicMock()
        blip_model.generate = Mock(return_value=np.array([[1, 2, 3]]))
        service.blip_processor = processor
        service.blip_model = blip_model
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._summarize_video(make_video_request(), b"data")
        assert response.success is True
        assert response.text == "Unable to generate summary"
        assert response.metadata["model"] == "blip+gpt4"
        assert service.analytics_metrics["total_summarizations"] == 1
        assert len(service.video_summaries) == 1

    @pytest.mark.asyncio
    async def test_summarize_video_with_ai_service(self):
        class FakeAIResponse:
            ok = True
            output_data = {
                "summary": "Great meeting", "key_points": ["p1"],
                "topics": ["t1"],
            }

        ai_service = MagicMock()
        ai_service.process_ai_request = AsyncMock(return_value=FakeAIResponse())
        service = make_video_service(ai_service=ai_service)
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        processor = MagicMock()
        processor.return_value = {"pixel_values": np.zeros((1, 3, 10, 10))}
        processor.decode = Mock(return_value="a frame caption")
        blip_model = MagicMock()
        blip_model.generate = Mock(return_value=np.array([[1, 2, 3]]))
        service.blip_processor = processor
        service.blip_model = blip_model
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._summarize_video(make_video_request(), b"data")
        assert response.success is True
        assert response.text == "Great meeting"
        assert response.content_analysis["key_points"] == ["p1"]

    @pytest.mark.asyncio
    async def test_summarize_video_error(self):
        service = make_video_service()
        with patch.object(service, "_extract_frames", new=AsyncMock(side_effect=RuntimeError("no frames"))):
            response = await service._summarize_video(make_video_request(), b"data")
        assert response.success is False

    @pytest.mark.asyncio
    async def test_analyze_video_content(self):
        service = make_video_service()
        yolo = make_yolo_mock([(0, 0.9), (1, 0.4), (2, 0.8)], {0: "person", 1: "dog", 2: "car"})
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 2
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)), \
             patch.object(service, "_classify_video_content", new=AsyncMock(return_value="traffic_scene")), \
             patch.object(service, "_analyze_video_quality", new=AsyncMock(return_value=75.0)):
            response = await service._analyze_video_content(make_video_request(), b"data")
        assert response.success is True
        assert len(response.objects_detected) == 4
        assert response.video_class == "traffic_scene"
        assert service.analytics_metrics["total_content_analyses"] == 1
        assert len(service.video_analyses) == 1

    @pytest.mark.asyncio
    async def test_analyze_video_content_error(self):
        service = make_video_service()
        with patch.object(service, "_extract_frames", new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = await service._analyze_video_content(make_video_request(), b"data")
        assert response.success is False

    @pytest.mark.asyncio
    async def test_detect_objects(self):
        service = make_video_service()
        yolo = make_yolo_mock([(0, 0.9), (0, 0.8), (1, 0.4)], {0: "person", 1: "cat"})
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 3
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._detect_objects(make_video_request(), b"data")
        assert response.success is True
        assert response.content_analysis["unique_objects"] == ["person"]
        assert response.content_analysis["total_detections"] == 6
        assert response.content_analysis["most_common"] == "person"

    @pytest.mark.asyncio
    async def test_detect_objects_no_detections(self):
        service = make_video_service()
        yolo = make_yolo_mock([], {0: "person"})
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._detect_objects(make_video_request(), b"data")
        assert response.success is True
        assert response.content_analysis["most_common"] is None

    @pytest.mark.asyncio
    async def test_recognize_faces(self):
        service = make_video_service()
        face_model = MagicMock()
        face_model.detect = Mock(return_value=[
            {"bbox": [1, 2, 3, 4], "confidence": 0.9, "identity": "alice"},
            {"bbox": [], "confidence": 0.5},
        ])
        service.face_recognition_model = face_model
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._recognize_faces(make_video_request(), b"data")
        assert response.success is True
        assert len(response.faces_detected) == 2

    @pytest.mark.asyncio
    async def test_recognize_faces_no_model(self):
        service = make_video_service()
        service.face_recognition_model = None
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._recognize_faces(make_video_request(), b"data")
        assert response.success is True
        assert response.faces_detected == []

    @pytest.mark.asyncio
    async def test_detect_scenes(self):
        service = make_video_service()
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 8
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._detect_scenes(make_video_request(), b"data")
        assert response.success is True
        assert len(response.scenes_detected) == 4

    @pytest.mark.asyncio
    async def test_diarize_speakers(self):
        service = make_video_service()
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 2
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._diarize_speakers(make_video_request(), b"data")
        assert response.success is True
        assert len(response.speakers_detected) == 2

    @pytest.mark.asyncio
    async def test_classify_video(self):
        service = make_video_service()
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)), \
             patch.object(service, "_classify_video_content", new=AsyncMock(return_value="tutorial")):
            response = await service._classify_video(make_video_request(), b"data")
        assert response.success is True
        assert response.video_class == "tutorial"
        assert service.analytics_metrics["total_video_classifications"] == 1

    @pytest.mark.asyncio
    async def test_moderate_content_safe(self):
        service = make_video_service()
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._moderate_content(make_video_request(), b"data")
        assert response.success is True
        assert response.content_rating == VideoContent.SAFE

    @pytest.mark.asyncio
    async def test_moderate_content_unsafe(self):
        service = make_video_service()
        mod_model = Mock(return_value={"unsafe": True})
        service.content_moderation_model = mod_model
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)]
        with patch.object(service, "_extract_frames", new=AsyncMock(return_value=frames)):
            response = await service._moderate_content(make_video_request(), b"data")
        assert response.success is True
        assert response.content_rating == VideoContent.UNSAFE
        assert len(response.content_analysis["content_flags"]) == 1

    @pytest.mark.asyncio
    async def test_moderate_content_error(self):
        service = make_video_service()
        with patch.object(service, "_extract_frames", new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = await service._moderate_content(make_video_request(), b"data")
        assert response.success is False


class TestVideoHelpers:
    @pytest.mark.asyncio
    async def test_extract_frames_error(self):
        service = make_video_service()
        with patch("cv2.VideoCapture", side_effect=RuntimeError("no cv2")):
            frames = await service._extract_frames(b"data")
        assert frames == []

    def test_get_quality_category(self):
        service = make_video_service()
        assert service._get_quality_category(95) == "excellent"
        assert service._get_quality_category(85) == "very_good"
        assert service._get_quality_category(75) == "good"
        assert service._get_quality_category(65) == "fair"
        assert service._get_quality_category(55) == "poor"
        assert service._get_quality_category(10) == "very_poor"

    @pytest.mark.asyncio
    async def test_analyze_video_quality_error(self):
        service = make_video_service()
        with patch("cv2.VideoCapture", side_effect=RuntimeError("no cv2")):
            score = await service._analyze_video_quality(b"data")
        assert score == 50.0

    @pytest.mark.asyncio
    async def test_classify_video_content_office_meeting(self):
        service = make_video_service()
        yolo = make_yolo_mock(
            [(0, 0.9)] * 11 + [(1, 0.9)] * 6, {0: "person", 1: "computer"}
        )
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 5
        assert await service._classify_video_content(frames) == "office_meeting"

    @pytest.mark.asyncio
    async def test_classify_video_content_presentation(self):
        service = make_video_service()
        yolo = make_yolo_mock(
            [(0, 0.9)] * 11 + [(2, 0.9)] * 3, {0: "person", 2: "whiteboard"}
        )
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 5
        assert await service._classify_video_content(frames) == "presentation"

    @pytest.mark.asyncio
    async def test_classify_video_content_social_gathering(self):
        service = make_video_service()
        yolo = make_yolo_mock([(0, 0.9)] * 11, {0: "person"})
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 5
        assert await service._classify_video_content(frames) == "social_gathering"

    @pytest.mark.asyncio
    async def test_classify_video_content_traffic_scene(self):
        service = make_video_service()
        yolo = make_yolo_mock([(3, 0.9)] * 6, {3: "car"})
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 5
        assert await service._classify_video_content(frames) == "traffic_scene"

    @pytest.mark.asyncio
    async def test_classify_video_content_tutorial(self):
        service = make_video_service()
        yolo = make_yolo_mock([(1, 0.9)] * 11, {1: "computer"})
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 5
        assert await service._classify_video_content(frames) == "tutorial"

    @pytest.mark.asyncio
    async def test_classify_video_content_general(self):
        service = make_video_service()
        yolo = make_yolo_mock([(4, 0.9)], {4: "tree"})
        service.yolo_model = yolo
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 5
        assert await service._classify_video_content(frames) == "general"

    @pytest.mark.asyncio
    async def test_classify_video_content_error(self):
        service = make_video_service()
        service.yolo_model = Mock(side_effect=RuntimeError("yolo down"))
        frames = [np.zeros((10, 10, 3), dtype=np.uint8)] * 2
        assert await service._classify_video_content(frames) == "unknown"

    @pytest.mark.asyncio
    async def test_preprocess_video_mp4(self):
        service = make_video_service()
        data = await service._preprocess_video(make_video_request())
        assert data == b"fake-video-bytes"
        assert service.performance_metrics["video_preprocessing_time"] >= 0

    @pytest.mark.asyncio
    async def test_preprocess_video_non_mp4(self):
        service = make_video_service()
        req = make_video_request(format=VideoFormat.AVI)
        data = await service._preprocess_video(req)
        assert data == b"fake-video-bytes"

    @pytest.mark.asyncio
    async def test_perform_security_check_no_service(self):
        service = make_video_service()
        result = await service._perform_security_check(make_video_request())
        assert result == {"passed": True}

    @pytest.mark.asyncio
    async def test_perform_security_check_error(self):
        service = make_video_service()
        service.enterprise_security = MagicMock()
        service.enterprise_security.audit_event = AsyncMock(
            side_effect=RuntimeError("audit down")
        )
        result = await service._perform_security_check(make_video_request())
        assert result == {"passed": True}

    @pytest.mark.asyncio
    async def test_log_video_request(self):
        security = MagicMock()
        security.audit_event = AsyncMock()
        service = make_video_service(security_service=security, enable_enterprise_features=True)
        await service._log_video_request(make_video_request(), VideoResponse(
            request_id="r", task_type=VideoTaskType.SUMMARIZATION, success=True,
            text=None, confidence=0.5, content_analysis=None, objects_detected=None,
            faces_detected=None, scenes_detected=None, speakers_detected=None,
            video_class=None, content_rating=None, quality_score=None,
            timestamp=datetime.now(timezone.utc), processing_time=1.0, metadata={},
        ))
        security.audit_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_video_request_no_security(self):
        service = make_video_service()
        await service._log_video_request(make_video_request(), VideoResponse(
            request_id="r", task_type=VideoTaskType.SUMMARIZATION, success=True,
            text=None, confidence=0.5, content_analysis=None, objects_detected=None,
            faces_detected=None, scenes_detected=None, speakers_detected=None,
            video_class=None, content_rating=None, quality_score=None,
            timestamp=datetime.now(timezone.utc), processing_time=1.0, metadata={},
        ))

    @pytest.mark.asyncio
    async def test_log_video_request_error(self):
        security = MagicMock()
        security.audit_event = AsyncMock(side_effect=RuntimeError("audit down"))
        service = make_video_service(security_service=security)
        await service._log_video_request(make_video_request(), VideoResponse(
            request_id="r", task_type=VideoTaskType.SUMMARIZATION, success=True,
            text=None, confidence=0.5, content_analysis=None, objects_detected=None,
            faces_detected=None, scenes_detected=None, speakers_detected=None,
            video_class=None, content_rating=None, quality_score=None,
            timestamp=datetime.now(timezone.utc), processing_time=1.0, metadata={},
        ))


# ====================================================== branch-coverage wave 2

from integrations.atom_ai_integration import _chat_completion_text


class TestChatCompletionAdapter:
    @pytest.mark.asyncio
    async def test_generate_completion_dict(self):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"content": "hello"})
        text = await _chat_completion_text(llm, [{"role": "user", "content": "x"}], "sys")
        assert text == "hello"
        messages = llm.generate_completion.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "sys"

    @pytest.mark.asyncio
    async def test_generate_completion_text_fallback_key(self):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"text": "via text"})
        text = await _chat_completion_text(llm, [{"role": "user", "content": "x"}])
        assert text == "via text"

    @pytest.mark.asyncio
    async def test_legacy_chat_completion(self):
        llm = MagicMock()
        llm.generate_completion = None
        llm.chat_completion = AsyncMock(return_value="legacy text")
        text = await _chat_completion_text(llm, [{"role": "user", "content": "x"}], "sys")
        assert text == "legacy text"
        llm.chat_completion.assert_awaited_once_with(
            messages=[{"role": "user", "content": "x"}], system_prompt="sys"
        )

    @pytest.mark.asyncio
    async def test_llm_none(self):
        assert await _chat_completion_text(None, [{"role": "user", "content": "x"}]) == ""

    @pytest.mark.asyncio
    async def test_no_methods(self):
        assert await _chat_completion_text(object(), [{"role": "user", "content": "x"}]) == ""

    @pytest.mark.asyncio
    async def test_generate_completion_empty(self):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"success": False, "content": ""})
        assert await _chat_completion_text(llm, [{"role": "user", "content": "x"}]) == ""


class TestAIWorkers:
    @pytest.mark.asyncio
    async def test_ai_message_analysis_worker_error_path(self):
        integration = make_integration(llm=FakeLLM())
        with patch("asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("stop"))):
            with pytest.raises(RuntimeError):
                await integration._ai_message_analysis_worker()

    @pytest.mark.asyncio
    async def test_intelligent_search_indexing_worker(self):
        integration = make_integration(llm=FakeLLM())
        integration.search_manager = MagicMock()
        integration.search_manager.update_search_index = AsyncMock()
        with patch("asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("stop"))):
            with pytest.raises(RuntimeError):
                await integration._intelligent_search_indexing_worker()
        integration.search_manager.update_search_index.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ai_workflow_optimization_worker(self):
        integration = make_integration(llm=FakeLLM())
        integration.workflow_intelligence.optimize_workflows = AsyncMock()
        with patch("asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("stop"))):
            with pytest.raises(RuntimeError):
                await integration._ai_workflow_optimization_worker()
        integration.workflow_intelligence.optimize_workflows.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cross_platform_ai_worker(self):
        integration = make_integration(llm=FakeLLM())
        integration.cross_platform_ai.synchronize_ai_insights = AsyncMock()
        with patch("asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("stop"))):
            with pytest.raises(RuntimeError):
                await integration._cross_platform_ai_worker()
        integration.cross_platform_ai.synchronize_ai_insights.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_ai_conversation_error(self):
        integration = make_integration(llm=FakeLLM())
        integration.conversation_manager.start_conversation = AsyncMock(
            side_effect=RuntimeError("conv down")
        )
        assert await integration.start_ai_conversation("u1", "slack") == ""

    @pytest.mark.asyncio
    async def test_setup_intelligent_search(self):
        integration = make_integration(llm=FakeLLM())
        integration.search_manager.initialize = AsyncMock()
        await integration._setup_intelligent_search()
        integration.search_manager.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calculate_engagement_level_error(self):
        integration = make_integration(llm=FakeLLM())

        class BadWorkspace(dict):
            def get(self, key, default=None):
                raise RuntimeError("boom")

        assert await integration._calculate_engagement_level(BadWorkspace()) == "unknown"


class TestOCRRunMethodDispatch:
    @pytest.mark.asyncio
    async def test_run_each_method(self):
        service = PDFOCRService()
        with patch.object(service, "_ocr_with_docling", new=AsyncMock(return_value={"method": "docling"})), \
             patch.object(service, "_ocr_with_tesseract", new=AsyncMock(return_value={"method": "tesseract"})), \
             patch.object(service, "_ocr_with_easyocr", new=AsyncMock(return_value={"method": "easyocr"})), \
             patch.object(service, "_ocr_with_ai_vision", new=AsyncMock(return_value={"method": "openai_vision"})):
            assert (await service._run_ocr_method("docling", b"pdf"))["method"] == "docling"
            assert (await service._run_ocr_method("tesseract", b"pdf"))["method"] == "tesseract"
            assert (await service._run_ocr_method("easyocr", b"pdf"))["method"] == "easyocr"
            assert (await service._run_ocr_method("ai_vision", b"pdf"))["method"] == "openai_vision"
            assert (await service._run_ocr_method("openai_vision", b"pdf"))["method"] == "openai_vision"


class TestOCRPDFToImagesFont:
    @pytest.mark.asyncio
    async def test_placeholder_draws_text(self, monkeypatch):
        service = PDFOCRService()
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        monkeypatch.delitem(sys.modules, "fitz", raising=False)

        class FakePage:
            mediabox = None

            @property
            def mediabox(self):
                return self

            @property
            def width(self):
                return 500

            @property
            def height(self):
                return 700

            def extract_text(self):
                return "line one\nline two\n"

        fake_reader = MagicMock()
        fake_reader.pages = [FakePage()]
        draw_cls = MagicMock()
        with patch(
            "integrations.pdf_processing.pdf_ocr_service.PyPDF2.PdfReader",
            return_value=fake_reader,
        ), patch("PIL.ImageDraw.Draw", return_value=draw_cls), \
             patch("PIL.ImageFont.truetype", return_value=MagicMock()):
            images = await service._pdf_to_images(SAMPLE_PDF)
        assert len(images) == 1
        assert draw_cls.text.call_count == 2

    @pytest.mark.asyncio
    async def test_placeholder_extract_text_error(self, monkeypatch):
        service = PDFOCRService()
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        monkeypatch.delitem(sys.modules, "fitz", raising=False)

        class FakePage:
            @property
            def mediabox(self):
                return self

            @property
            def width(self):
                return 500

            @property
            def height(self):
                return 700

            def extract_text(self):
                raise RuntimeError("text extraction failed")

        fake_reader = MagicMock()
        fake_reader.pages = [FakePage()]
        with patch(
            "integrations.pdf_processing.pdf_ocr_service.PyPDF2.PdfReader",
            return_value=fake_reader,
        ):
            images = await service._pdf_to_images(SAMPLE_PDF)
        assert len(images) == 1


class TestOCRExtractImagesOuter:
    @pytest.mark.asyncio
    async def test_extract_images_outer_error(self, monkeypatch):
        service = PDFOCRService()
        fitz_mod = types.ModuleType("fitz")
        fitz_mod.open = Mock(side_effect=RuntimeError("fitz exploded"))
        monkeypatch.setitem(sys.modules, "fitz", fitz_mod)
        monkeypatch.delitem(sys.modules, "pdf2image", raising=False)
        result = await service._extract_and_process_images(b"pdf", False)
        assert result["success"] is False
        assert "fitz exploded" in result["error"]


class TestPDFMemoryInitBranch:
    def test_init_simple_db_error(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        with patch("os.makedirs", side_effect=OSError("disk full")):
            service._init_simple_db()
        assert service._simple_db_path is None

    def test_init_simple_db_adds_tags_column(self, tmp_path):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        fake_file = tmp_path / "b" / "c" / "file.py"
        with patch.object(
            pdf_memory_integration.os.path,
            "abspath",
            return_value=str(fake_file),
        ):
            service._init_simple_db()
        db_path = tmp_path / "b" / "data" / "pdf_simple.db"
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(pdf_documents)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        assert "tags" in columns

    @pytest.mark.asyncio
    async def test_search_byok_provider_error(self):
        byok = MagicMock()
        byok.get_optimal_provider = Mock(side_effect=RuntimeError("provider down"))
        with patch(
            "integrations.pdf_processing.pdf_memory_integration.get_byok_manager",
            return_value=byok,
        ):
            service = PDFMemoryIntegration(lancedb_handler=None, use_byok=True)
            results = await service.search_pdfs("u", "find me something")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_pdfs_outer_error(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        with patch.object(service, "_search_in_lancedb", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await service.search_pdfs("u", "q") == []

    def test_get_text_excerpt_start_offset(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        text = "x" * 80 + "gamma found here" + "y" * 300
        excerpt = service._get_text_excerpt(text, "gamma")
        assert excerpt.startswith("...")
        assert "gamma" in excerpt

    @pytest.mark.asyncio
    async def test_get_simple_document_error(self, tmp_path):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        service._simple_db_path = str(tmp_path / "t.db")
        conn = sqlite3.connect(service._simple_db_path)
        conn.execute("CREATE TABLE pdf_documents (doc_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO pdf_documents VALUES ('d1')")
        conn.commit()
        conn.close()
        assert await service._get_simple_document("u", "d1") is None

    @pytest.mark.asyncio
    async def test_delete_document_outer_error(self):
        service = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        with patch.object(service, "_delete_simple_document", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await service.delete_document("u", "d1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_documents_sqlite_date_filters(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": "2025-01-01", "source_uri": "u",
        })
        result = await mem_service.list_documents(
            "u", date_from="2026-01-01", date_to="2026-12-31"
        )
        assert result["total"] == 0
        result = await mem_service.list_documents(
            "u", date_from="2020-01-01", date_to="2030-12-31"
        )
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_get_document_tags_invalid_json(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": datetime.now(), "source_uri": "u",
        })
        conn = sqlite3.connect(mem_service._simple_db_path)
        conn.execute("UPDATE pdf_documents SET tags = '{' WHERE doc_id = 'd1'")
        conn.commit()
        conn.close()
        result = await mem_service.get_document_tags("d1", "u")
        assert result["success"] is False
        assert "Invalid tags format" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_document_tags_error(self, mem_service):
        await mem_service._store_simple_format({
            "doc_id": "d1", "user_id": "u", "filename": "a.pdf",
            "page_count": 1, "total_chars": 10, "pdf_type": "searchable",
            "processing_method": "basic_pdf", "extracted_text": "txt",
            "created_at": datetime.now(), "source_uri": "u",
        })
        with patch("sqlite3.connect", side_effect=RuntimeError("db locked")):
            result = await mem_service.delete_document_tags("d1", "u", ["a"])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_by_tags_error(self, mem_service):
        with patch("sqlite3.connect", side_effect=RuntimeError("db locked")):
            result = await mem_service.search_by_tags("u", ["a"])
        assert result["success"] is False


class TestVideoDispatchWave2:
    @pytest.mark.asyncio
    async def test_process_content_analysis_dispatch(self):
        service = make_video_service()
        with patch.object(service, "_analyze_video_content", new=AsyncMock()):
            await service.process_video_request(
                make_video_request(task_type=VideoTaskType.CONTENT_ANALYSIS)
            )

    @pytest.mark.asyncio
    async def test_process_object_detection_dispatch(self):
        service = make_video_service()
        with patch.object(service, "_detect_objects", new=AsyncMock()):
            await service.process_video_request(
                make_video_request(task_type=VideoTaskType.OBJECT_DETECTION)
            )

    @pytest.mark.asyncio
    async def test_process_face_recognition_dispatch(self):
        service = make_video_service()
        with patch.object(service, "_recognize_faces", new=AsyncMock()):
            await service.process_video_request(
                make_video_request(task_type=VideoTaskType.FACE_RECOGNITION)
            )

    @pytest.mark.asyncio
    async def test_process_scene_detection_dispatch(self):
        service = make_video_service()
        with patch.object(service, "_detect_scenes", new=AsyncMock()):
            await service.process_video_request(
                make_video_request(task_type=VideoTaskType.SCENE_DETECTION)
            )

    @pytest.mark.asyncio
    async def test_process_speaker_diarization_dispatch(self):
        service = make_video_service()
        with patch.object(service, "_diarize_speakers", new=AsyncMock()):
            await service.process_video_request(
                make_video_request(task_type=VideoTaskType.SPEAKER_DIARIZATION)
            )

    @pytest.mark.asyncio
    async def test_process_video_classification_dispatch(self):
        service = make_video_service()
        with patch.object(service, "_classify_video", new=AsyncMock()):
            await service.process_video_request(
                make_video_request(task_type=VideoTaskType.VIDEO_CLASSIFICATION)
            )

    @pytest.mark.asyncio
    async def test_process_content_moderation_dispatch(self):
        service = make_video_service()
        with patch.object(service, "_moderate_content", new=AsyncMock()):
            await service.process_video_request(
                make_video_request(task_type=VideoTaskType.CONTENT_MODERATION)
            )

    @pytest.mark.asyncio
    async def test_analyze_video_quality_success(self):
        service = make_video_service()
        score = await service._analyze_video_quality(b"garbage bytes")
        assert 0.0 <= score <= 100.0


class TestPDFMemoryFilterInjection:
    @pytest.mark.asyncio
    async def test_get_document_escapes_user_id(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = []
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        await service.get_document("u' OR 1=1 --", "d'1")
        where = fake_table.search.return_value.where.call_args[0][0]
        assert where == "doc_id = 'd''1' AND user_id = 'u'' OR 1=1 --'"

    @pytest.mark.asyncio
    async def test_delete_document_escapes_ids(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        await service.delete_document("u'", "d'")
        expr = fake_table.delete.call_args[0][0]
        assert "user_id = 'u'''" in expr
        assert "doc_id = 'd'''" in expr

    @pytest.mark.asyncio
    async def test_update_tags_escapes_ids(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = [{"doc_id": "x"}]
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        await service.update_document_tags("u'", "d'", ["a"])
        where = fake_table.search.return_value.where.call_args[0][0]
        assert "''" in where

    @pytest.mark.asyncio
    async def test_list_documents_escapes_filters(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = []
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        await service.list_documents(
            "u' OR 1=1", pdf_type="searchable'", date_from="2020-01-01'", date_to="2030-01-01"
        )
        where = fake_table.search.return_value.where.call_args[0][0]
        assert "''" in where

    @pytest.mark.asyncio
    async def test_stats_escapes_user_id(self):
        handler = make_lancedb_handler()
        fake_table = MagicMock()
        fake_table.search.return_value.where.return_value.to_list.return_value = []
        handler.get_table = Mock(return_value=fake_table)
        service = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        await service.get_user_document_stats("u' OR 1=1 --")
        where = fake_table.search.return_value.where.call_args[0][0]
        assert where == "user_id = 'u'' OR 1=1 --'"
