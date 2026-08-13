"""Coverage wave 64d — core/docling_processor.py (TDD, mocked docling/BYOK,
no network, no real docling install).

Covers: module-reload import branches (docling present/absent via fake
sys.modules entries, BYOK import blocked-once/blocked-always), constructor
paths (BYOK init success/failure, converter init success/failure, use_byok
gating on BYOK_AVAILABLE), process_document (unavailable, bytes with temp
file + cleanup + unlink failure, str/Path sources, unsupported source type,
conversion None/error, outer exception), _convert_document temp-file
cleanup on convert failure, _extract_content for all export formats +
failure fallback, _extract_tables (with/without tables attr, empty data,
exception), _extract_images (pictures present/absent/exception),
_extract_metadata (pages/metadata/exception), process_pdf mapping,
get_status, singleton get_docling_processor, is_docling_available.

The pre-existing failures in tests/core/services/test_docling_processor.py
(4 tests) are stale-test bugs (mock_instance assigned AFTER the constructor
already built the converter) and are re-covered here with correct mocking.
"""
import builtins
import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.docling_processor as dp


class _FakeConverter:
    """Stand-in for docling's DocumentConverter used in reload tests."""

    def convert(self, *a, **k):
        raise NotImplementedError


class _BoomDoc:
    """Doc whose attribute access raises (exception-branch tests)."""

    def __init__(self, attr):
        self._attr = attr

    @property
    def tables(self):
        raise RuntimeError("tables boom")

    @property
    def pictures(self):
        raise RuntimeError("pictures boom")

    @property
    def pages(self):
        raise RuntimeError("pages boom")

    @property
    def metadata(self):
        raise RuntimeError("metadata boom")


def _ok_doc(content="*text*", pages=1, title="", author=""):
    """A docling-like document object covering all extraction attrs."""
    table_a = SimpleNamespace(data=[["h1", "h2"], ["a", "b"]])
    table_b = SimpleNamespace(data=[])
    pic_a = SimpleNamespace(caption="fig 1", classification="chart")
    pic_b = SimpleNamespace()
    doc = SimpleNamespace(
        export_to_markdown=lambda: content,
        model_dump_json=lambda indent=None: '{"json": 1}',
        export_to_html=lambda: "<html>h</html>",
        pages=[object() for _ in range(pages)],
        tables=[table_a, table_b],
        pictures=[pic_a, pic_b],
        metadata=SimpleNamespace(title=title, author=author),
    )
    return doc


def _make_processor(**kw):
    return dp.DoclingDocumentProcessor(**kw)


# ===========================================================================
# Module reload — import-time branches
# ===========================================================================


class TestModuleReloadBranches:
    def _install_fake_docling(self):
        sys.modules["docling"] = types.ModuleType("docling")
        dc = types.ModuleType("docling.document_converter")
        dc.DocumentConverter = _FakeConverter
        sys.modules["docling.document_converter"] = dc
        dm = types.ModuleType("docling.datamodel")
        sys.modules["docling.datamodel"] = dm
        bm = types.ModuleType("docling.datamodel.base_models")
        bm.InputFormat = object
        sys.modules["docling.datamodel.base_models"] = bm

    def _uninstall_fake_docling(self):
        for name in (
            "docling.datamodel.base_models",
            "docling.datamodel",
            "docling.document_converter",
            "docling",
        ):
            sys.modules.pop(name, None)

    def test_reload_with_docling_installed(self):
        """Lines 19-21: docling import success branch."""
        self._install_fake_docling()
        try:
            importlib.reload(dp)
            assert dp.DOCLING_AVAILABLE is True
            assert dp.DocumentConverter is _FakeConverter
            assert dp.InputFormat is not None
        finally:
            self._uninstall_fake_docling()
            importlib.reload(dp)
        assert dp.DOCLING_AVAILABLE is False
        assert dp.DocumentConverter is None

    def test_reload_byok_first_import_blocked_then_succeeds(self, monkeypatch):
        """Lines 31-34: first BYOK import fails, retry succeeds."""
        self._uninstall_fake_docling()
        real_import = builtins.__import__
        state = {"n": 0}

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "core.byok_endpoints" and state["n"] == 0:
                state["n"] += 1
                raise ImportError("blocked once")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        importlib.reload(dp)
        assert dp.BYOK_AVAILABLE is True
        assert state["n"] == 1
        assert callable(dp.get_byok_manager)

    def test_reload_byok_import_always_blocked(self, monkeypatch):
        """Lines 35-37: both BYOK imports fail -> graceful degradation."""
        self._uninstall_fake_docling()
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "core.byok_endpoints":
                raise ImportError("blocked")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        try:
            importlib.reload(dp)
            assert dp.BYOK_AVAILABLE is False
            assert dp.get_byok_manager is None
        finally:
            monkeypatch.undo()
            importlib.reload(dp)
        assert dp.BYOK_AVAILABLE is True


# ===========================================================================
# Constructor paths
# ===========================================================================


class TestConstructor:
    @patch("core.docling_processor.DOCLING_AVAILABLE", False)
    def test_docling_unavailable_sets_converter_none(self):
        p = _make_processor()
        assert p.converter is None
        assert p.is_available is False

    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    def test_docling_available_initializes_converter(self, mock_cls):
        p = _make_processor()
        mock_cls.assert_called_once()
        assert p.converter is mock_cls.return_value
        assert p.is_available is True

    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter", side_effect=RuntimeError("conv boom"))
    def test_converter_init_failure(self, mock_cls):
        """Lines 111-113: DocumentConverter() raising -> converter None."""
        p = _make_processor()
        assert p.converter is None
        assert p.is_available is False

    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    @patch("core.docling_processor.BYOK_AVAILABLE", False)
    def test_use_byok_false_with_available_flag(self, mock_cls):
        p = _make_processor(use_byok=True)
        assert p.use_byok is False

    @patch("core.docling_processor.BYOK_AVAILABLE", False)
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    def test_use_byok_gated_on_byok_available(self, mock_cls):
        p = _make_processor(use_byok=True)
        assert p.use_byok is False
        assert p.byok_manager is None

    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    @patch("core.docling_processor.get_byok_manager")
    def test_byok_init_success(self, mock_get, mock_cls):
        manager = MagicMock()
        mock_get.return_value = manager
        p = _make_processor(use_byok=True)
        assert p.use_byok is True
        assert p.byok_manager is manager

    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    @patch("core.docling_processor.get_byok_manager", side_effect=RuntimeError("byok boom"))
    def test_byok_init_failure_disables_byok(self, mock_get, mock_cls):
        """Lines 92-94: get_byok_manager raising -> use_byok False."""
        p = _make_processor(use_byok=True)
        assert p.use_byok is False
        assert p.byok_manager is None


# ===========================================================================
# Format support
# ===========================================================================


class TestFormats:
    @patch("core.docling_processor.DOCLING_AVAILABLE", False)
    def test_get_supported_formats_lists_extensions(self):
        fmts = _make_processor().get_supported_formats()
        assert set(fmts) == set(dp.DoclingDocumentProcessor.SUPPORTED_EXTENSIONS)

    @patch("core.docling_processor.DOCLING_AVAILABLE", False)
    def test_is_format_supported_variants(self):
        p = _make_processor()
        assert p.is_format_supported("pdf") is True
        assert p.is_format_supported("PDF") is True
        assert p.is_format_supported(".pdf") is True
        assert p.is_format_supported("PDF ") is False
        assert p.is_format_supported("xyz") is False
        assert p.is_format_supported("") is False


# ===========================================================================
# process_document / _convert_document
# ===========================================================================


class TestProcessDocument:
    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", False)
    async def test_unavailable_returns_error(self):
        p = _make_processor()
        result = await p.process_document(b"x")
        assert result["success"] is False
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_bytes_full_pipeline_with_cleanup(self, mock_cls, tmp_path):
        """Bytes source: temp file created, used, and unlinked after extraction."""
        result_obj = MagicMock()
        result_obj.document = _ok_doc(content="# Heading\nbody", pages=2,
                                      title="Doc T", author="A U")
        converter = MagicMock()
        converter.convert.return_value = result_obj
        mock_cls.return_value = converter
        p = _make_processor()

        unlinked = []

        def fake_unlink(path):
            unlinked.append(path)
            return None

        with patch("core.docling_processor.os.unlink", side_effect=fake_unlink):
            result = await p.process_document(
                source=b"%PDF", file_type="pdf", file_name="a.pdf"
            )
        assert result["success"] is True
        assert result["method"] == "docling"
        assert result["content"] == "# Heading\nbody"
        assert result["export_format"] == "markdown"
        assert result["page_count"] == 2
        assert result["total_chars"] == len("# Heading\nbody")
        assert result["file_name"] == "a.pdf"
        assert result["file_type"] == "pdf"
        assert len(result["tables"]) == 2
        assert len(result["images"]) == 2
        assert result["metadata"]["title"] == "Doc T"
        assert len(unlinked) == 1
        assert unlinked[0] == result_obj._temp_path

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_bytes_cleanup_oserror_swallowed(self, mock_cls):
        """Lines 174-176: os.unlink OSError during cleanup is tolerated."""
        result_obj = MagicMock()
        result_obj.document = _ok_doc()
        converter = MagicMock()
        converter.convert.return_value = result_obj
        mock_cls.return_value = converter
        p = _make_processor()
        with patch("core.docling_processor.os.unlink", side_effect=OSError("gone")):
            result = await p.process_document(source=b"%PDF", file_type="pdf")
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_bytes_default_suffix_without_file_type(self, mock_cls):
        """Line 207: no file_type -> '.pdf' suffix."""
        result_obj = MagicMock()
        result_obj.document = _ok_doc()
        converter = MagicMock()
        converter.convert.return_value = result_obj
        mock_cls.return_value = converter
        p = _make_processor()
        result = await p.process_document(source=b"%PDF")
        assert result["success"] is True
        converter.convert.assert_called_once()
        assert converter.convert.call_args[0][0].endswith(".pdf")

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_bytes_convert_raises_cleans_temp_and_errors(self, mock_cls):
        """Lines 219-224: convert raising -> temp unlinked -> error result."""
        converter = MagicMock()
        converter.convert.side_effect = RuntimeError("parse boom")
        mock_cls.return_value = converter
        p = _make_processor()
        unlinked = []

        def fake_unlink(path):
            unlinked.append(path)
            return None

        with patch("core.docling_processor.os.unlink", side_effect=fake_unlink):
            result = await p.process_document(source=b"%PDF", file_type="pdf")
        assert result["success"] is False
        assert result["error"] == "Document conversion failed"
        assert len(unlinked) == 1

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_bytes_convert_raises_and_unlink_oserror(self, mock_cls):
        """Lines 220-223: cleanup unlink OSError swallowed, convert error re-raised."""
        converter = MagicMock()
        converter.convert.side_effect = RuntimeError("parse boom")
        mock_cls.return_value = converter
        p = _make_processor()
        with patch("core.docling_processor.os.unlink", side_effect=OSError("gone")):
            result = await p.process_document(source=b"%PDF", file_type="pdf")
        assert result["success"] is False

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_bytes_convert_returns_none(self, mock_cls):
        """convert returning None -> no _temp_path -> conversion-failed error."""
        converter = MagicMock()
        converter.convert.return_value = None
        mock_cls.return_value = converter
        p = _make_processor()
        result = await p.process_document(source=b"%PDF", file_type="pdf")
        assert result["success"] is False
        assert result["error"] == "Document conversion failed"

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_str_source(self, mock_cls, tmp_path):
        f = tmp_path / "d.pdf"
        f.write_bytes(b"x")
        result_obj = MagicMock()
        result_obj.document = _ok_doc(content="str content")
        converter = MagicMock()
        converter.convert.return_value = result_obj
        mock_cls.return_value = converter
        p = _make_processor()
        result = await p.process_document(source=str(f), file_type="pdf")
        assert result["success"] is True
        assert result["content"] == "str content"
        converter.convert.assert_called_once_with(str(f))

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_path_source(self, mock_cls, tmp_path):
        f = tmp_path / "d.pdf"
        f.write_bytes(b"x")
        result_obj = MagicMock()
        result_obj.document = _ok_doc(content="path content")
        converter = MagicMock()
        converter.convert.return_value = result_obj
        mock_cls.return_value = converter
        p = _make_processor()
        result = await p.process_document(source=f, file_type="pdf")
        assert result["success"] is True
        converter.convert.assert_called_once_with(str(f))

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_unsupported_source_type(self, mock_cls):
        """Line 230: non-bytes/str/Path source -> ValueError -> error result."""
        converter = MagicMock()
        mock_cls.return_value = converter
        p = _make_processor()
        result = await p.process_document(source=12345, file_type="pdf")
        assert result["success"] is False
        assert result["error"] == "Document conversion failed"

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_outer_exception_wrapped_in_error_result(self, mock_cls):
        """Lines 192-194: post-conversion exception -> error result."""
        result_obj = MagicMock()
        result_obj.document = _ok_doc()
        converter = MagicMock()
        converter.convert.return_value = result_obj
        mock_cls.return_value = converter
        p = _make_processor()
        with patch.object(p, "_extract_content", side_effect=RuntimeError("extract boom")):
            result = await p.process_document(source=b"%PDF", file_type="pdf")
        assert result["success"] is False
        assert "extract boom" in result["error"]


# ===========================================================================
# _extract_content
# ===========================================================================


class TestExtractContent:
    def _p(self):
        with patch("core.docling_processor.DOCLING_AVAILABLE", False):
            return dp.DoclingDocumentProcessor()

    def test_markdown(self):
        doc = _ok_doc(content="# M")
        assert dp.DoclingDocumentProcessor()._extract_content(SimpleNamespace(document=doc), "markdown") == {"content": "# M"}

    def test_json(self):
        result = SimpleNamespace(document=_ok_doc())
        out = self._p()._extract_content(result, "json")
        assert "json" in out["content"]

    def test_text_uses_markdown_export(self):
        doc = _ok_doc(content="plain")
        out = self._p()._extract_content(SimpleNamespace(document=doc), "text")
        assert out["content"] == "plain"

    def test_html(self):
        doc = _ok_doc()
        out = self._p()._extract_content(SimpleNamespace(document=doc), "html")
        assert out["content"] == "<html>h</html>"

    def test_html_attribute_error_falls_back_to_markdown(self):
        """Lines 253-254: export_to_html missing -> markdown fallback."""
        doc = SimpleNamespace(
            export_to_markdown=lambda: "md",
            model_dump_json=lambda indent=None: "{}",
        )
        out = self._p()._extract_content(SimpleNamespace(document=doc), "html")
        assert out["content"] == "md"

    def test_unknown_format_defaults_to_markdown(self):
        """Lines 255-256: unknown export_format -> markdown."""
        doc = _ok_doc(content="md out")
        out = self._p()._extract_content(SimpleNamespace(document=doc), "weird")
        assert out["content"] == "md out"

    def test_export_raises_returns_empty(self):
        """Lines 260-262: extraction exception -> empty content."""
        doc = SimpleNamespace(export_to_markdown=MagicMock(side_effect=RuntimeError("boom")))
        out = self._p()._extract_content(SimpleNamespace(document=doc), "markdown")
        assert out == {"content": ""}


# ===========================================================================
# _extract_tables / _extract_images / _extract_metadata
# ===========================================================================


class TestExtractTables:
    def _p(self):
        with patch("core.docling_processor.DOCLING_AVAILABLE", False):
            return dp.DoclingDocumentProcessor()

    def test_tables_with_data(self):
        doc = SimpleNamespace(tables=[
            SimpleNamespace(data=[["a", "b"], ["c", "d"]]),
            SimpleNamespace(data=[]),
        ])
        out = self._p()._extract_tables(SimpleNamespace(document=doc))
        assert len(out) == 2
        assert out[0]["index"] == 0
        assert out[0]["num_rows"] == 2
        assert out[0]["num_cols"] == 2
        assert out[1]["num_rows"] == 0
        assert out[1]["num_cols"] == 0

    def test_no_tables_attr(self):
        out = self._p()._extract_tables(SimpleNamespace(document=SimpleNamespace()))
        assert out == []

    def test_exception_returns_empty(self):
        """Lines 289-290: table access raising -> empty list."""
        out = self._p()._extract_tables(SimpleNamespace(document=_BoomDoc("tables")))
        assert out == []


class TestExtractImages:
    def _p(self):
        with patch("core.docling_processor.DOCLING_AVAILABLE", False):
            return dp.DoclingDocumentProcessor()

    def test_pictures_with_defaults(self):
        doc = SimpleNamespace(pictures=[
            SimpleNamespace(caption="cap", classification="chart"),
            SimpleNamespace(),
        ])
        out = self._p()._extract_images(SimpleNamespace(document=doc))
        assert len(out) == 2
        assert out[0]["caption"] == "cap"
        assert out[0]["classification"] == "chart"
        assert out[1]["caption"] == ""
        assert out[1]["classification"] == "unknown"

    def test_no_pictures_attr(self):
        out = self._p()._extract_images(SimpleNamespace(document=SimpleNamespace()))
        assert out == []

    def test_exception_returns_empty(self):
        """Lines 308-309: pictures access raising -> empty list."""
        out = self._p()._extract_images(SimpleNamespace(document=_BoomDoc("pictures")))
        assert out == []


class TestExtractMetadata:
    def _p(self):
        with patch("core.docling_processor.DOCLING_AVAILABLE", False):
            return dp.DoclingDocumentProcessor()

    def test_pages_and_metadata(self):
        doc = SimpleNamespace(
            pages=[object(), object(), object()],
            metadata=SimpleNamespace(title="T", author="A"),
        )
        out = self._p()._extract_metadata(SimpleNamespace(document=doc))
        assert out["page_count"] == 3
        assert out["title"] == "T"
        assert out["author"] == "A"
        assert out["created"] == ""
        assert out["modified"] == ""

    def test_no_attrs_returns_defaults(self):
        out = self._p()._extract_metadata(SimpleNamespace(document=SimpleNamespace()))
        assert out == {"page_count": 0, "title": "", "author": "",
                       "created": "", "modified": ""}

    def test_exception_returns_defaults(self):
        """Lines 336-337: metadata access raising -> defaults."""
        out = self._p()._extract_metadata(SimpleNamespace(document=_BoomDoc("pages")))
        assert out["page_count"] == 0


# ===========================================================================
# _create_error_result / process_pdf / get_status / globals
# ===========================================================================


class TestCreateErrorResult:
    def test_shape(self):
        with patch("core.docling_processor.DOCLING_AVAILABLE", False):
            p = dp.DoclingDocumentProcessor()
        out = p._create_error_result("oops")
        assert out == {
            "success": False, "method": "docling", "content": "",
            "error": "oops", "tables": [], "images": [], "metadata": {},
            "total_chars": 0,
        }


class TestProcessPDF:
    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_process_pdf_success_mapping(self, mock_cls):
        result_obj = MagicMock()
        result_obj.document = _ok_doc(content="pdf text", pages=1)
        converter = MagicMock()
        converter.convert.return_value = result_obj
        mock_cls.return_value = converter
        p = _make_processor()
        out = await p.process_pdf(b"%PDF", use_ocr=True)
        assert out["method"] == "docling"
        assert out["extracted_text"] == "pdf text"
        assert out["page_count"] == 1
        assert out["total_chars"] == len("pdf text")
        assert out["success"] is True
        assert out["error"] is None

    @pytest.mark.asyncio
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    async def test_process_pdf_failure_passthrough(self, mock_cls):
        converter = MagicMock()
        converter.convert.side_effect = RuntimeError("boom")
        mock_cls.return_value = converter
        p = _make_processor(enable_ocr=False)
        out = await p.process_pdf(b"%PDF", use_ocr=False)
        assert out["success"] is False
        assert out["error"] == "Document conversion failed"
        assert out["extracted_text"] == ""
        assert out["page_count"] == 0


class TestGetStatus:
    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    def test_status_available(self, mock_cls):
        p = _make_processor(use_byok=False)
        s = p.get_status()
        assert s["available"] is True
        assert s["docling_installed"] is True
        assert s["converter_initialized"] is True
        assert s["byok_integrated"] is False
        assert s["ocr_enabled"] is True
        assert "pdf" in s["supported_formats"]

    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    @patch("core.docling_processor.DocumentConverter")
    @patch("core.docling_processor.get_byok_manager")
    def test_status_byok_integrated(self, mock_get, mock_cls):
        mock_get.return_value = MagicMock()
        p = _make_processor(use_byok=True)
        assert p.get_status()["byok_integrated"] is True

    @patch("core.docling_processor.DOCLING_AVAILABLE", False)
    def test_status_unavailable(self):
        p = _make_processor()
        s = p.get_status()
        assert s["available"] is False
        assert s["docling_installed"] is False
        assert s["converter_initialized"] is False


class TestGlobalFunctions:
    def teardown_method(self, method):
        dp._docling_processor = None

    @patch("core.docling_processor.DoclingDocumentProcessor")
    def test_get_docling_processor_creates_once(self, mock_cls):
        dp._docling_processor = None
        a = dp.get_docling_processor()
        b = dp.get_docling_processor()
        assert a is b
        mock_cls.assert_called_once()

    @patch("core.docling_processor.DOCLING_AVAILABLE", True)
    def test_is_docling_available_true(self):
        assert dp.is_docling_available() is True

    @patch("core.docling_processor.DOCLING_AVAILABLE", False)
    def test_is_docling_available_false(self):
        assert dp.is_docling_available() is False
