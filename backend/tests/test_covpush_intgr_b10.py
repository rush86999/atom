"""Final gap-fill: atom_ai_integration / pdf_ocr / pdf_memory except branches."""
import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


class TestAtomAIFinalGaps:
    def _svc(self):
        from integrations.atom_ai_integration import AtomAIIntegration
        llm = MagicMock()
        llm.chat_completion = AsyncMock(return_value=json.dumps({"sentiment": "positive"}))
        svc = AtomAIIntegration({"llm_service": llm})
        platform = MagicMock()
        platform.get_unified_workspaces = AsyncMock(return_value=[])
        platform.get_unified_channels = AsyncMock(return_value=[])
        platform.get_unified_messages = AsyncMock(return_value=[])
        svc.platform_integrations = {"slack": platform}
        svc.atom_memory = MagicMock()
        svc.atom_search = MagicMock()
        svc.atom_workflow = MagicMock()
        return svc

    async def test_public_method_excepts(self):
        from integrations.atom_ai_integration import AtomAIIntegration
        svc = self._svc()
        svc.platform_integrations["slack"].get_unified_workspaces = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_intelligent_workspaces("u1") == []
        svc.platform_integrations["slack"].get_unified_channels = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_intelligent_channels("slack_w1", "u1") == []
        svc.platform_integrations["slack"].get_unified_messages = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.get_intelligent_messages("w1", "slack_c1") == []
        svc.search_manager.search = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.intelligent_search("q") == []
        svc._enhance_content = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.send_intelligent_message("w1", "slack_c1", "hi")
        assert result["ok"] is False
        svc.workflow_intelligence.enhance_workflow = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.create_intelligent_workflow({})
        assert result["ok"] is False
        svc.llm_service.chat_completion = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.get_intelligent_analytics("m", "r", "w")
        assert result["ok"] is False
        svc.conversation_manager.process_command = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.process_natural_language_command("c", "u")
        assert result["ok"] is False
        svc.conversation_manager.start_conversation = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc.start_ai_conversation("u", "p") == ""
        svc.conversation_manager.continue_conversation = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc.continue_ai_conversation("c", "m", "u")
        assert result["ok"] is False

    async def test_worker_exception_branches(self):
        from integrations.atom_ai_integration import AtomAIIntegration
        svc = self._svc()
        svc.search_manager.update_search_index = AsyncMock()
        svc.workflow_intelligence.optimize_workflows = AsyncMock()
        svc.cross_platform_ai.synchronize_ai_insights = AsyncMock()

        def boom(*a, **k):
            raise RuntimeError("x")

        with patch("asyncio.sleep", side_effect=boom):
            with patch("integrations.atom_ai_integration.logger"):
                with pytest.raises(RuntimeError):
                    await svc._ai_message_analysis_worker()
                with pytest.raises(RuntimeError):
                    await svc._intelligent_search_indexing_worker()
                with pytest.raises(RuntimeError):
                    await svc._ai_workflow_optimization_worker()
                with pytest.raises(RuntimeError):
                    await svc._cross_platform_ai_worker()

    async def test_index_communication_except(self):
        from integrations.atom_ai_integration import IntelligentSearchManager
        mgr = IntelligentSearchManager(MagicMock(), MagicMock())
        with patch("core.lancedb_handler.get_lancedb_handler", side_effect=RuntimeError("x")):
            await mgr._index_communication({"id": "c", "subject": "s", "body": "b" * 30})
        with patch("core.lancedb_handler.get_lancedb_handler") as gh, \
             patch("core.embedding_service.EmbeddingService") as es:
            es.return_value.generate_embedding = AsyncMock(side_effect=RuntimeError("x"))
            gh.return_value.upsert = AsyncMock()
            await mgr._index_communication({"id": "c", "subject": "s", "body": "b" * 30})
        with patch("core.lancedb_handler.get_lancedb_handler") as gh, \
             patch("core.embedding_service.EmbeddingService") as es:
            es.return_value.generate_embedding = AsyncMock(return_value=[0.1])
            gh.return_value.upsert = AsyncMock(side_effect=RuntimeError("x"))
            await mgr._index_communication({"id": "c", "subject": "s", "body": "b" * 30})

    async def test_workflow_manager_excepts(self):
        from integrations.atom_ai_integration import WorkflowIntelligenceManager
        llm = MagicMock()
        mgr = WorkflowIntelligenceManager(llm, None)
        with patch("integrations.atom_ai_integration.logger"):
            await mgr._load_workflow_patterns()
        with patch("integrations.atom_ai_integration.logger"):
            await mgr._apply_optimizations({"id": 1}, {})
        with patch("integrations.atom_ai_integration.logger"):
            await mgr.setup_workflow_automation()
        with patch("integrations.atom_ai_integration.logger"):
            await mgr.start_monitoring()
        with patch.object(mgr, "_get_all_workflows", new=AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_ai_integration.logger"):
                await mgr.optimize_workflows()
        await mgr._load_workflow_patterns()
        assert mgr.workflow_patterns["approval_patterns"] == []

    async def test_cross_platform_excepts(self):
        from integrations.atom_ai_integration import CrossPlatformAIManager
        mgr = CrossPlatformAIManager(MagicMock(), {})
        with patch("integrations.atom_ai_integration.logger"):
            await mgr._get_platform_insights("p", None)
        with patch("integrations.atom_ai_integration.logger"):
            await mgr._get_platform_data("p")
        await mgr.initialize()
        assert "platforms" in mgr.cross_platform_insights
        with patch.object(mgr, "_get_platform_data", new=AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_ai_integration.logger"):
                await mgr._load_cross_platform_data()
        with patch.object(mgr, "_get_platform_insights", new=AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_ai_integration.logger"):
                await mgr.synchronize_ai_insights()

    async def test_engagement_unknown(self):
        svc = self._svc()
        assert await svc._calculate_engagement_level({"member_count": MagicMock(),
                                                      "channel_count": MagicMock()}) == "unknown"


class TestPDFOCRFinalGaps:
    def _svc(self):
        from integrations.pdf_processing.pdf_ocr_service import PDFOCRService
        return PDFOCRService()

    async def test_ocr_reader_init(self):
        import integrations.pdf_processing.pdf_ocr_service as mod
        svc = self._svc()
        svc.ocr_readers = {}
        with patch.object(mod, "DOCLING_AVAILABLE", True), \
             patch.object(mod, "get_docling_processor", side_effect=RuntimeError("x")):
            svc._init_ocr_readers()
        with patch.object(mod, "TESSERACT_AVAILABLE", True):
            svc._init_ocr_readers()
        with patch.object(mod, "EASYOCR_AVAILABLE", True), \
             patch.object(mod, "easyocr") as easyocr:
            easyocr.Reader.side_effect = RuntimeError("x")
            svc._init_ocr_readers()
        with patch.object(mod, "TESSERACT_AVAILABLE", True), \
             patch.object(mod, "pytesseract") as pt:
            svc.tesseract_path = "/usr/bin/tesseract"
            svc._init_ocr_readers()
            assert pt.pytesseract.tesseract_cmd == "/usr/bin/tesseract"

    async def test_needs_ocr_branch(self):
        svc = self._svc()
        svc.ocr_readers = {}
        result = await svc.process_pdf(b"x", use_ocr=False, extract_images=False)
        assert result is not None
        assert result["success"] is False

    async def test_vision_page_text_and_quality(self):
        import integrations.pdf_processing.pdf_ocr_service as mod
        svc = self._svc()
        svc.llm_service = MagicMock()
        svc.llm_service.generate_completion = AsyncMock(side_effect=RuntimeError("x"))
        svc._pdf_to_images = AsyncMock(return_value=[MagicMock()])
        result = await svc._ocr_with_ai_vision(b"x")
        assert result["success"] is False


class TestPDFMemoryFinalGaps:
    def _svc(self, tmp_path):
        from pathlib import Path
        from integrations.pdf_processing.pdf_memory_integration import PDFMemoryIntegration
        svc = PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        fake = str(Path(tmp_path) / "a" / "b" / "pdf_memory_integration.py")
        with patch("os.path.abspath", return_value=fake):
            svc._init_simple_db()
        return svc

    async def test_byok_init_failure(self):
        from integrations.pdf_processing import pdf_memory_integration as mod
        with patch.object(mod, "get_byok_manager", side_effect=RuntimeError("x")):
            svc = mod.PDFMemoryIntegration(lancedb_handler=None, use_byok=True)
        assert svc.use_byok is False

    async def test_init_db_failure(self):
        from integrations.pdf_processing import pdf_memory_integration as mod
        with patch("os.makedirs", side_effect=RuntimeError("x")):
            svc = mod.PDFMemoryIntegration(lancedb_handler=None, use_byok=False)
        assert svc._simple_db_path is None

    async def test_legacy_table_migration(self, tmp_path):
        svc = self._svc(tmp_path)
        assert svc._simple_db_path is not None
        conn = sqlite3.connect(svc._simple_db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS pdf_documents (doc_id TEXT PRIMARY KEY, user_id TEXT NOT NULL)")
        conn.commit()
        conn.close()
        svc._init_simple_db()  # adds tags column via ALTER

    async def test_get_document_lancedb(self, tmp_path):
        handler = MagicMock()
        table = MagicMock()
        handler.get_table.return_value = table
        table.search.return_value.where.return_value.to_list.return_value = [
            {"doc_id": "d1", "filename": "f", "page_count": 1, "total_chars": 1,
             "pdf_type": "t", "processing_method": "m", "extracted_text": "x",
             "source_uri": "u", "tags": [], "created_at": "c", "file_size": 1,
             "metadata": '{"x": 1}'}]
        svc = self._svc(tmp_path)
        svc.lancedb_handler = handler
        doc = await svc.get_document("u1", "d1")
        assert doc is not None
        assert doc["metadata"] == {"x": 1}
        table.search.return_value.where.return_value.to_list.return_value = []
        svc2 = self._svc(tmp_path)
        svc2.lancedb_handler = handler
        assert await svc2.get_document("u1", "missing") is None
        table.search.return_value.where.side_effect = RuntimeError("x")
        svc3 = self._svc(tmp_path)
        svc3.lancedb_handler = handler
        assert await svc3.get_document("u1", "d1") is None

    async def test_get_simple_no_path(self, tmp_path):
        svc = self._svc(tmp_path)
        svc._simple_db_path = None
        assert await svc._get_simple_document("u1", "d1") is None
        assert await svc._delete_simple_document("u1", "d1") == {"success": False, "error": "SQLite fallback not initialized"}
        assert await svc.search_pdfs("u1", "q") == []

    async def test_delete_lancedb(self, tmp_path):
        handler = MagicMock()
        table = MagicMock()
        table.delete = MagicMock(side_effect=RuntimeError("x"))
        handler.get_table.return_value = table
        svc = self._svc(tmp_path)
        svc.lancedb_handler = handler
        result = await svc.delete_document("u1", "d1")
        assert result["success"] is True
        assert "simple_storage" in result["deleted_from"]
        svc2 = self._svc(tmp_path)
        svc2._simple_db_path = None
        svc2.lancedb_handler = handler
        result = await svc2.delete_document("u1", "d1")
        assert result["success"] is True

    async def test_list_lancedb_filters(self, tmp_path):
        handler = MagicMock()
        table = MagicMock()
        table.search.return_value.where.return_value.to_list.return_value = [
            {"doc_id": "d1", "filename": "f", "page_count": 1, "total_chars": 1,
             "pdf_type": "searchable", "processing_method": "m", "extracted_text": "x",
             "source_uri": "u", "tags": ["a"], "created_at": "t", "file_size": 1,
             "metadata": "{}"}]
        handler.get_table.return_value = table
        svc = self._svc(tmp_path)
        svc.lancedb_handler = handler
        listing = await svc.list_documents("u1", pdf_type="searchable", date_from="2020-01-01", date_to="2030-01-01")
        assert listing["total"] == 1
        listing = await svc.list_documents("u1", tags=["a"])
        assert listing["total"] == 1
        svc2 = self._svc(tmp_path)
        svc2._simple_db_path = None
        listing = await svc2.list_documents("u1")
        assert listing["total"] == 0

    async def test_update_tags_lancedb_flow(self, tmp_path):
        handler = MagicMock()
        table = MagicMock()
        table.search.return_value.where.return_value.to_list.return_value = [{"doc_id": "d1"}]
        handler.get_table.return_value = table
        svc = self._svc(tmp_path)
        svc.lancedb_handler = handler
        result = await svc.update_document_tags("u1", "d1", ["a", "b"])
        assert result["success"] is True
        table.search.return_value.where.side_effect = RuntimeError("x")
        result = await svc.update_document_tags("u1", "d1", ["a"])
        assert result["success"] is False
        # sqlite not-found path
        svc3 = self._svc(tmp_path)
        result = await svc3.update_document_tags("u1", "missing", ["a"])
        assert result["success"] is False

    async def test_tags_json_errors(self, tmp_path):
        svc = self._svc(tmp_path)
        await svc.store_processed_pdf("u1", {
            "extracted_content": {"text": "Hello world " * 100, "text_ratio": 0.8},
            "processing_summary": {"best_method": "basic_pdf", "used_ocr": False,
                                   "total_pages": 1, "total_characters": 100},
            "file_metadata": {"filename": "f", "size_bytes": 1}})
        stored = await svc.store_processed_pdf("u1", {
            "extracted_content": {"text": "Hello world " * 100, "text_ratio": 0.8},
            "processing_summary": {"best_method": "basic_pdf", "used_ocr": False,
                                   "total_pages": 1, "total_characters": 100},
            "file_metadata": {"filename": "f", "size_bytes": 1}})
        doc_id = stored["doc_id"]
        conn = sqlite3.connect(svc._simple_db_path)
        conn.execute("UPDATE pdf_documents SET tags = 'bad-json{' WHERE doc_id = ?", (doc_id,))
        conn.commit()
        conn.close()
        result = await svc.get_document_tags(doc_id, "u1")
        assert result["success"] is False
        result = await svc.delete_document_tags(doc_id, "u1", ["x"])
        assert result["success"] is False  # corrupt json -> error
        result = await svc.search_by_tags("u1", ["x"])
        assert result["success"] is True

    async def test_byok_search_tracking(self, tmp_path):
        from integrations.pdf_processing import pdf_memory_integration as mod
        with patch.object(mod, "get_byok_manager") as gbm:
            gbm.return_value = MagicMock()
            svc = mod.PDFMemoryIntegration(lancedb_handler=None, use_byok=True)
        svc._simple_db_path = None
        svc.byok_manager.track_usage = MagicMock()
        await svc.search_pdfs("u1", "hello")
        svc.byok_manager.track_usage.side_effect = RuntimeError("x")
        await svc.search_pdfs("u1", "hello")

    async def test_store_lancedb_path(self, tmp_path):
        handler = MagicMock()
        handler.embed_text.return_value = [0.1]
        table = MagicMock()
        handler.get_table.return_value = table
        svc = self._svc(tmp_path)
        svc.lancedb_handler = handler
        result = await svc.store_processed_pdf("u1", {
            "extracted_content": {"text": "Hello world " * 100, "text_ratio": 0.8},
            "processing_summary": {"best_method": "basic_pdf", "used_ocr": False,
                                   "total_pages": 1, "total_characters": 100},
            "file_metadata": {"filename": "f", "size_bytes": 1}})
        assert result["success"] is True
        assert "lancedb" in result["storage_methods"]
        assert table.add.called


class TestAtomAIFinalGaps2:
    def _svc(self):
        from integrations.atom_ai_integration import AtomAIIntegration
        llm = MagicMock()
        llm.chat_completion = AsyncMock(return_value=json.dumps({"sentiment": "positive"}))
        svc = AtomAIIntegration({"llm_service": llm})
        platform = MagicMock()
        platform.get_unified_workspaces = AsyncMock(return_value=[])
        svc.platform_integrations = {"slack": platform, "teams": None}
        svc.atom_memory = MagicMock()
        svc.atom_search = MagicMock()
        svc.atom_workflow = MagicMock()
        return svc

    async def test_initialize_except_branch(self):
        svc = self._svc()
        with patch.object(svc, "_start_ai_integration_workers", AsyncMock(side_effect=RuntimeError("x"))):
            with patch("integrations.atom_ai_integration.logger"):
                assert await svc.initialize() is False

    async def test_platform_none_continue(self):
        svc = self._svc()
        ws = await svc.get_intelligent_workspaces("u1")
        assert ws == []

    async def test_channel_engagement_medium(self):
        from integrations.atom_ai_integration import AtomAIIntegration
        svc = AtomAIIntegration({"llm_service": MagicMock()})
        assert await svc._calculate_channel_engagement({"message_count": 300, "member_count": 15}) == "medium"

    async def test_optimize_workflows_loop(self):
        from integrations.atom_ai_integration import WorkflowIntelligenceManager
        llm = MagicMock()
        llm.chat_completion = AsyncMock(return_value=json.dumps({"opt": 1}))
        mgr = WorkflowIntelligenceManager(llm, MagicMock())
        mgr._get_all_workflows = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        mgr._apply_optimizations = AsyncMock()
        with patch.object(mgr, "_get_all_workflows", new=AsyncMock(return_value=[{"id": 1}])):
            await mgr.optimize_workflows()
        llm.chat_completion = AsyncMock(return_value="bad json")
        with patch.object(mgr, "_get_all_workflows", new=AsyncMock(return_value=[{"id": 1}])):
            await mgr.optimize_workflows()
        llm.chat_completion = AsyncMock(side_effect=RuntimeError("x"))
        with patch.object(mgr, "_get_all_workflows", new=AsyncMock(return_value=[{"id": 1}])):
            with patch("integrations.atom_ai_integration.logger"):
                await mgr.optimize_workflows()
        mgr.atom_workflow = None
        await mgr.optimize_workflows()


class TestPDFOCRFinalGaps2:
    def _svc(self):
        from integrations.pdf_processing.pdf_ocr_service import PDFOCRService
        return PDFOCRService()

    async def test_process_pdf_from_path(self, tmp_path):
        svc = self._svc()
        path = tmp_path / "doc.pdf"
        path.write_bytes(b"not a pdf")
        result = await svc.process_pdf(str(path))
        assert result["success"] is False
        result = await svc.process_pdf(path)
        assert result["success"] is False

    async def test_optimize_provider_pdf_ocr(self):
        svc = self._svc()
        svc.use_byok = True
        svc.byok_manager = MagicMock()
        svc.byok_manager.get_optimal_provider.return_value = "openai"
        result = await svc._optimize_provider_selection(False, "parallel")
        assert result["optimized"] is True
        assert result["task_type"] == "pdf_ocr"

    async def test_placeholder_dimension_excepts(self):
        import integrations.pdf_processing.pdf_ocr_service as mod
        svc = self._svc()
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                reader = MagicMock()
                page = MagicMock()
                page.mediabox.width.side_effect = AttributeError("no width")
                page.mediabox.height = MagicMock()
                page.extract_text.return_value = "text"
                reader.pages = [page]
                pypdf.PdfReader.return_value = reader
                images = await svc._pdf_to_images(b"x")
        assert len(images) == 1
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                reader = MagicMock()
                page = MagicMock()
                page.mediabox.width = MagicMock()
                page.mediabox.width.__int__ = MagicMock(side_effect=RuntimeError("x"))
                page.mediabox.height = MagicMock()
                page.extract_text.return_value = "text"
                reader.pages = [page]
                pypdf.PdfReader.return_value = reader
                images = await svc._pdf_to_images(b"x")
        assert len(images) == 1

    async def test_placeholder_font_and_draw_excepts(self):
        import integrations.pdf_processing.pdf_ocr_service as mod
        from PIL import Image, ImageDraw, ImageFont
        svc = self._svc()
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                reader = MagicMock()
                page = MagicMock()
                page.mediabox.width = 100
                page.mediabox.height = 100
                page.extract_text.return_value = "text"
                reader.pages = [page]
                pypdf.PdfReader.return_value = reader
                from PIL import ImageFont as RealImageFont
                with patch.object(RealImageFont, "truetype", side_effect=RuntimeError("x")):
                    images = await svc._pdf_to_images(b"x")
        assert len(images) == 1
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                reader = MagicMock()
                page = MagicMock()
                page.mediabox.width = 100
                page.mediabox.height = 100
                page.extract_text.return_value = "text"
                reader.pages = [page]
                pypdf.PdfReader.return_value = reader
                from PIL import ImageDraw as RealImageDraw
                with patch.object(RealImageDraw, "Draw", side_effect=RuntimeError("x")):
                    images = await svc._pdf_to_images(b"x")
        assert len(images) == 1

    async def test_extract_images_outer_except(self):
        import integrations.pdf_processing.pdf_ocr_service as mod
        svc = self._svc()
        fitz = MagicMock()
        fitz.open.side_effect = RuntimeError("outer")
        with patch.dict(sys.modules, {"fitz": fitz}):
            with patch("integrations.pdf_processing.pdf_ocr_service.logger"):
                result = await svc._extract_and_process_images(b"x", False)
        assert result["success"] is False
