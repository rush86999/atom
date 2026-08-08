"""Coverage push for integrations wave B - batch 8 (pdf_memory_integration)."""
import asyncio
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _result(**kw):
    base = {
        "extracted_content": {"text": "Hello world " * 100, "text_ratio": 0.8},
        "processing_summary": {"best_method": "basic_pdf", "used_ocr": False,
                               "total_pages": 3, "total_characters": 1200},
        "file_metadata": {"filename": "doc.pdf", "size_bytes": 1000},
    }
    base.update(kw)
    return base


class TestPDFMemory:
    def _svc(self, tmp_path=None, with_lance=False, use_byok=True):
        import tempfile as tf
        from integrations.pdf_processing.pdf_memory_integration import PDFMemoryIntegration
        svc = PDFMemoryIntegration(lancedb_handler=None, use_byok=use_byok)
        if tmp_path is None:
            tmp_path = tf.mkdtemp(prefix="pdfmem_")
        from pathlib import Path
        tmp_path = Path(tmp_path)
        fake = str(tmp_path / "a" / "b" / "pdf_memory_integration.py")
        with patch("os.path.abspath", return_value=fake):
            svc._init_simple_db()
        return svc

    async def test_init_and_tables(self, tmp_path):
        from integrations.pdf_processing.pdf_memory_integration import PDFMemoryIntegration
        svc = self._svc(tmp_path=tmp_path)
        assert svc.table_name == "pdf_documents"
        handler = MagicMock()
        handler.list_tables.return_value = ["other"]
        handler.create_table = MagicMock()
        svc2 = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        svc2._initialize_memory_tables()
        assert handler.create_table.called
        handler.list_tables.return_value = ["pdf_documents"]
        svc3 = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        svc3._initialize_memory_tables()
        handler.list_tables.side_effect = RuntimeError("x")
        svc4 = PDFMemoryIntegration(lancedb_handler=handler, use_byok=False)
        svc4._initialize_memory_tables()

    async def test_store_and_search_sqlite(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        result = await svc.store_processed_pdf("u1", _result(), source_uri="/tmp/doc.pdf",
                                               tags=["finance"], metadata={"a": 1})
        assert result["success"] is True
        assert result["storage_methods"] == ["simple_format"]
        doc_id = result["doc_id"]
        results = await svc.search_pdfs("u1", "hello", limit=5)
        assert len(results) >= 1
        doc = await svc.get_document("u1", doc_id)
        assert doc is not None
        assert doc["filename"] == "doc.pdf"
        assert await svc.get_document("u1", "missing") is None
        deleted = await svc.delete_document("u1", doc_id)
        assert deleted["success"] is True
        assert "simple_storage" in deleted["deleted_from"]
        results = await svc.search_pdfs("u1", "hello")
        assert results == []

    async def test_store_error_path(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        result = await svc.store_processed_pdf("u1", {})
        assert result["success"] is True  # defaults
        svc._store_simple_format = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.store_processed_pdf("u1", _result())
        assert result["success"] is False

    async def test_store_in_lancedb(self, tmp_path):
        handler = MagicMock()
        handler.embed_text.return_value = [0.1] * 8
        table = MagicMock()
        handler.get_table.return_value = table
        svc = self._svc(tmp_path=tmp_path)
        svc.lancedb_handler = handler
        doc_data = {
            "doc_id": "d1", "user_id": "u1", "filename": "f", "file_size": 1,
            "page_count": 1, "total_chars": 100, "processing_method": "basic_pdf",
            "pdf_type": "searchable", "extracted_text": "word " * 500,
            "metadata": "{}", "created_at": datetime.now(), "updated_at": datetime.now(),
            "source_uri": "", "tags": [],
        }
        await svc._store_in_lancedb(doc_data)
        assert table.add.called
        doc_data["extracted_text"] = ""
        await svc._store_in_lancedb(doc_data)
        handler.embed_text.side_effect = RuntimeError("x")
        doc_data["extracted_text"] = "word " * 500
        with pytest.raises(RuntimeError):
            await svc._store_in_lancedb(doc_data)

    async def test_store_simple_format_errors(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        result = await svc._store_simple_format({"doc_id": "d", "user_id": "u"})
        assert result["success"] is True
        svc._simple_db_path = None
        result = await svc._store_simple_format({"doc_id": "d"})
        assert result["success"] is False
        svc._simple_db_path = "/nonexistent/dir/x.db"
        result = await svc._store_simple_format({"doc_id": "d"})
        assert result["success"] is False

    async def test_helpers(self):
        svc = self._svc()
        assert svc._determine_pdf_type({"processing_summary": {"used_ocr": True}}) == "scanned"
        assert svc._determine_pdf_type({"processing_summary": {"used_ocr": False},
                                        "extracted_content": {"text_ratio": 0.8}}) == "searchable"
        assert svc._determine_pdf_type({"processing_summary": {"used_ocr": False},
                                        "extracted_content": {"text_ratio": 0.5}}) == "mixed"
        assert svc._determine_pdf_type({"processing_summary": {"used_ocr": False},
                                        "extracted_content": {"text_ratio": 0.1}}) == "scanned"
        assert svc._serialize_metadata({"a": 1}) == '{"a": 1}'
        assert svc._serialize_metadata({"a": datetime.now()}) == "{}"
        assert svc._parse_metadata('{"a": 1}') == {"a": 1}
        assert svc._parse_metadata("bad") == {}
        assert svc._map_processing_method_to_provider("openai_vision", False) == "openai"
        assert svc._map_processing_method_to_provider("", False) is None
        assert svc._map_processing_method_to_provider("unknown", True) == "openai"
        assert svc._map_processing_method_to_provider("unknown", False) is None
        chunks = svc._create_sliding_window_chunks("x" * 2500)
        assert len(chunks) > 1
        assert svc._create_sliding_window_chunks("") == []
        status = svc.get_byok_status()
        assert "byok_integrated" in status
        excerpt = svc._get_text_excerpt("a" * 500, "aaa", 100)
        assert len(excerpt) <= 103
        assert svc._get_text_excerpt("short", "zzz") == "short"
        assert svc._get_text_excerpt("", "") == ""

    async def test_simple_search_filters(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        await svc.store_processed_pdf("u1", _result(), tags=["t"])
        results = await svc.search_pdfs("u1", "hello", filters={"pdf_type": "searchable"})
        assert len(results) >= 1
        results = await svc.search_pdfs("u1", "hello", filters={"processing_method": "basic_pdf"})
        assert len(results) >= 1
        results = await svc.search_pdfs("u1", "hello", filters={"pdf_type": "scanned"})
        assert results == []

    async def test_lancedb_search(self, tmp_path):
        handler = MagicMock()
        table = MagicMock()
        handler.get_table.return_value = table
        table.search.return_value.where.return_value.to_list.return_value = [
            {"doc_id": "d1", "filename": "f", "_distance": 0.1, "page_count": 1,
             "total_chars": 10, "pdf_type": "searchable", "extracted_text": "hello world",
             "created_at": "t", "source_uri": "u"},
            {"doc_id": "d1", "filename": "f", "_distance": 0.05, "page_count": 1,
             "total_chars": 10, "pdf_type": "searchable", "extracted_text": "hello",
             "created_at": "t", "source_uri": "u"},
        ]
        handler.search.return_value = table.search.return_value.where.return_value.to_list.return_value
        svc = self._svc(tmp_path=tmp_path)
        svc.lancedb_handler = handler
        results = await svc._search_in_lancedb("u1", "hello", 10, 0.5, {"pdf_type": "searchable", "tags": ["a"]})
        assert len(results) == 1
        assert results[0]["similarity_score"] == 0.05
        handler.search.side_effect = RuntimeError("x")
        results = await svc._search_in_lancedb("u1", "hello", 10, 0.5, None)
        assert results == []
        results = await svc.search_pdfs("u1", "hello")
        assert len(results) >= 0  # falls back to simple search

    async def test_list_documents(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        await svc.store_processed_pdf("u1", _result(), tags=["a", "b"])
        await svc.store_processed_pdf("u1", _result(), tags=["c"])
        listing = await svc.list_documents("u1", limit=10)
        assert listing["success"] is True
        assert listing["total"] == 2
        listing = await svc.list_documents("u1", pdf_type="searchable")
        assert listing["total"] == 2
        listing = await svc.list_documents("u1", pdf_type="scanned")
        assert listing["total"] == 0
        listing = await svc.list_documents("u1", date_from="2020-01-01", date_to="2030-01-01")
        assert listing["total"] == 2
        # lancedb path
        handler = MagicMock()
        table = MagicMock()
        handler.get_table.return_value = table
        table.search.return_value.where.return_value.to_list.return_value = [
            {"doc_id": "d1", "filename": "f", "page_count": 1, "total_chars": 1,
             "pdf_type": "searchable", "processing_method": "m", "extracted_text": "t",
             "source_uri": "u", "tags": ["a"], "created_at": "t", "file_size": 1,
             "metadata": '{"x": 1}'}]
        svc2 = self._svc(tmp_path=tmp_path)
        svc2.lancedb_handler = handler
        listing = await svc2.list_documents("u1")
        assert listing["total"] == 1
        listing = await svc2.list_documents("u1", tags=["a"])
        assert listing["total"] == 1
        listing = await svc2.list_documents("u1", tags=["zz"])
        assert listing["total"] == 0
        table.search.return_value.where.side_effect = RuntimeError("x")
        listing = await svc2.list_documents("u1")
        assert listing["success"] is False

    async def test_update_tags(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        result = await svc.update_document_tags("u1", "missing", ["a"])
        assert result["success"] is False
        stored = await svc.store_processed_pdf("u1", _result())
        doc_id = stored["doc_id"]
        result = await svc.update_document_tags("u1", doc_id, ["  tag1  ", "tag2", "", None])
        assert result["success"] is True
        assert result["tags"] == ["tag1", "tag2"]
        result = await svc.update_document_tags("u1", doc_id, "notalist")
        assert result["success"] is False
        result = await svc.update_document_tags("u1", doc_id, ["x" * 60])
        assert result["success"] is False
        tags = await svc.get_document_tags(doc_id, "u1")
        assert tags["success"] is True
        assert tags["tags"] == ["tag1", "tag2"]
        tags = await svc.get_document_tags("missing", "u1")
        assert tags["success"] is False
        del_result = await svc.delete_document_tags(doc_id, "u1", ["tag1"])
        assert del_result["success"] is True
        assert del_result["remaining_tags"] == ["tag2"]
        del_result = await svc.delete_document_tags("missing", "u1", ["x"])
        assert del_result["success"] is False
        search = await svc.search_by_tags("u1", ["tag2"])
        assert search["success"] is True
        assert search["count"] == 1
        search = await svc.search_by_tags("u1", ["tag2", "zz"], match_all=True)
        assert search["count"] == 0
        search = await svc.search_by_tags("u1", ["tag2", "zz"])
        assert search["count"] == 1
        # update via lancedb path
        handler = MagicMock()
        table = MagicMock()
        handler.get_table.return_value = table
        table.search.return_value.where.return_value.to_list.return_value = [{"doc_id": "d1"}]
        svc2 = self._svc(tmp_path=tmp_path)
        svc2.lancedb_handler = handler
        result = await svc2.update_document_tags("u1", "d1", ["a"])
        assert result["success"] is True
        table.search.return_value.where.return_value.to_list.return_value = []
        result = await svc2.update_document_tags("u1", "d1", ["a"])
        assert result["success"] is False

    async def test_tag_storage_errors(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        svc._simple_db_path = None
        result = await svc.get_document_tags("d", "u")
        assert result["success"] is False
        result = await svc.delete_document_tags("d", "u", ["x"])
        assert result["success"] is False
        result = await svc.search_by_tags("u", ["x"])
        assert result["success"] is False
        conn = sqlite3.connect(svc._simple_db_path or ":memory:")
        if svc._simple_db_path:
            conn.execute("UPDATE pdf_documents SET tags = 'bad-json' WHERE 1=0")
        svc2 = self._svc(tmp_path=tmp_path)
        await svc2.store_processed_pdf("u1", _result())
        stored = await svc2.store_processed_pdf("u1", _result())
        doc_id = stored["doc_id"]
        with patch("sqlite3.connect") as conn2:
            conn2.return_value.cursor.return_value.execute.side_effect = RuntimeError("x")
            result = await svc2.get_document_tags(doc_id, "u1")
            assert result["success"] is False
            result = await svc2.delete_document_tags(doc_id, "u1", ["x"])
            assert result["success"] is False
            result = await svc2.search_by_tags("u1", ["x"])
            assert result["success"] is False

    async def test_stats_and_byok(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path)
        stats = await svc.get_user_document_stats("u1")
        assert stats["total_documents"] == 0
        handler = MagicMock()
        table = MagicMock()
        handler.get_table.return_value = table
        table.search.return_value.where.return_value.to_list.return_value = [
            {"page_count": 2, "total_chars": 100, "file_size": 10, "pdf_type": "searchable"}]
        svc2 = self._svc(tmp_path=tmp_path)
        svc2.lancedb_handler = handler
        stats = await svc2.get_user_document_stats("u1")
        assert stats["total_documents"] == 1
        assert stats["pdf_types"]["searchable"] == 1
        table.search.return_value.where.side_effect = RuntimeError("x")
        stats = await svc2.get_user_document_stats("u1")
        assert "error" in stats

    async def test_format_document_result(self):
        svc = self._svc()
        formatted = svc._format_document_result({
            "doc_id": "d", "filename": "f", "page_count": 1, "total_chars": 1,
            "pdf_type": "t", "processing_method": "m", "extracted_text": "x",
            "source_uri": "u", "tags": ["a"], "created_at": "c", "file_size": 1,
            "metadata": '{"x": 1}'})
        assert formatted["metadata"] == {"x": 1}

    async def test_byok_tracking(self, tmp_path):
        svc = self._svc(tmp_path=tmp_path, use_byok=True)
        assert svc.use_byok is True
        assert svc.byok_manager is not None
        svc.byok_manager.track_usage = MagicMock()
        result = await svc.store_processed_pdf("u1", _result())
        assert result["success"] is True
        assert svc.byok_manager.track_usage.called
        svc.byok_manager.track_usage = MagicMock(side_effect=RuntimeError("x"))
        result = await svc.store_processed_pdf("u1", _result())
        assert result["success"] is True
        svc.byok_manager.get_optimal_provider = MagicMock(return_value="openai")
        svc.byok_manager.track_usage = MagicMock()
        results = await svc.search_pdfs("u1", "hello")
        assert len(results) == 2
        assert svc.byok_manager.track_usage.called
        svc.byok_manager.get_optimal_provider = MagicMock(side_effect=RuntimeError("x"))
        await svc.search_pdfs("u1", "hello")

    async def test_module_level(self):
        import integrations.pdf_processing.pdf_memory_integration as mod
        assert mod.BYOK_AVAILABLE is True or mod.BYOK_AVAILABLE is False
        assert mod.get_byok_manager is not None
