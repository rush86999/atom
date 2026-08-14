# -*- coding: utf-8 -*-
"""Coverage wave 109 — accounting/document_processor.py (never-tested module,
0% baseline -> target 100%; fully mocked: no real AI calls, no DB, no OCR).

- process_document: accounting disabled / document missing / no raw text with
  and without OCR service / OCR returning text / OCR failing / AI extraction
  returning None / bill flow (entity create + record + link + commit) /
  invoice flow.
- _ai_extract: dict output, markdown-fenced string output, exception.
- _get_or_create_entity: found vs created.
- _create_bill/_create_invoice: field mapping incl. date parsing
  (missing/invalid/valid).
- _parse_date: falsy / parsed / parse-None / parse-exception.
- _perform_ocr: no service / missing file / success / failure / exception.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import accounting.document_processor as dp


class TestModuleFallbacks:
    def test_pdf_ocr_import_failure_sets_none(self):
        """Coverage: lines 15-17 (the OCR ImportError branch) — only reachable
        when integrations.pdf_processing.pdf_ocr_service is absent."""
        import builtins
        import importlib.util
        import sys
        path = dp.__file__
        spec = importlib.util.spec_from_file_location("doc_processor_w109_fb", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["doc_processor_w109_fb"] = mod
        real_import = builtins.__import__

        def blocker(name, *args, **kwargs):
            if name == "integrations.pdf_processing.pdf_ocr_service":
                raise ImportError("blocked")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocker):
            spec.loader.exec_module(mod)
        assert mod.PDF_OCR_AVAILABLE is False
        assert mod.PDFOCRService is None


@pytest.fixture
def proc():
    db = MagicMock()
    return dp.AIDocumentProcessor(db), db


def _doc(**kw):
    base = dict(extracted_data=None, file_path=None, bill_id=None, invoice_id=None, id="doc1")
    base.update(kw)
    return SimpleNamespace(**base)


class TestProcessDocument:
    async def test_accounting_disabled(self, proc):
        p, db = proc
        with patch.object(dp, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: False)):
            result = await p.process_document("ws", "d1")
        assert result is None
        db.query.assert_not_called()

    async def test_document_not_found(self, proc):
        p, db = proc
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(dp, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)):
            result = await p.process_document("ws", "d1")
        assert result is None

    async def test_no_raw_text_no_ocr_service(self, proc):
        p, db = proc
        db.query.return_value.filter.return_value.first.return_value = _doc()
        p.pdf_ocr_service = None
        with patch.object(dp, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)):
            result = await p.process_document("ws", "d1")
        assert result is None

    async def test_no_raw_text_ocr_fails(self, proc, tmp_path):
        p, db = proc
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF fake")
        db.query.return_value.filter.return_value.first.return_value = _doc(file_path=str(f))
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(return_value={"success": False, "error": "no text"})
        p.pdf_ocr_service = ocr
        with patch.object(dp, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)):
            result = await p.process_document("ws", "d1")
        assert result is None

    async def test_no_raw_text_ocr_success_but_ai_none(self, proc, tmp_path):
        p, db = proc
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF fake")
        doc = _doc(file_path=str(f))
        db.query.return_value.filter.return_value.first.return_value = doc
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(return_value={"success": True, "extracted_text": "INV 123", "total_chars": 7})
        p.pdf_ocr_service = ocr
        p._ai_extract = AsyncMock(return_value=None)
        with patch.object(dp, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)):
            result = await p.process_document("ws", "d1")
        assert result is None
        p._ai_extract.assert_awaited_once_with("INV 123", "bill")

    async def test_bill_flow_entity_created(self, proc):
        p, db = proc
        doc = _doc(extracted_data={"raw_text": "Vendor Inc invoice 5"})
        db.query.return_value.filter.return_value.first.return_value = doc
        entity = SimpleNamespace(id="e1")
        p._get_or_create_entity = MagicMock(return_value=entity)
        p._ai_extract = AsyncMock(return_value={
            "entity_name": "Vendor Inc", "number": "INV-5", "date": "2026-08-01",
            "due_date": "2026-09-01", "amount": "99.5", "currency": "EUR",
            "description": "services",
        })
        with patch.object(dp, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)):
            record = await p.process_document("ws", "d1", doc_type="bill")
        assert record is not None
        assert record.vendor_id == "e1"
        assert record.bill_number == "INV-5"
        assert record.amount == 99.5
        assert record.currency == "EUR"
        assert record.status.value == "draft"
        assert doc.bill_id == record.id
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(record)

    async def test_invoice_flow_existing_entity(self, proc):
        p, db = proc
        doc = _doc(extracted_data={"raw_text": "Acme invoice 9"})
        db.query.return_value.filter.return_value.first.return_value = doc
        entity = SimpleNamespace(id="e2")
        p._get_or_create_entity = MagicMock(return_value=entity)
        p._ai_extract = AsyncMock(return_value={"entity_name": "Acme", "amount": 10})
        with patch.object(dp, "get_automation_settings",
                          returnValue=SimpleNamespace(is_accounting_enabled=lambda: True)):
            record = await p.process_document("ws", "d1", doc_type="invoice")
        assert record is not None
        assert record.customer_id == "e2"
        assert record.invoice_number is None
        assert doc.invoice_id == record.id

    async def test_ai_extract_none_returns_none(self, proc):
        p, db = proc
        doc = _doc(extracted_data={"raw_text": "text"})
        db.query.return_value.filter.return_value.first.return_value = doc
        p._ai_extract = AsyncMock(return_value=None)
        with patch.object(dp, "get_automation_settings",
                          return_value=SimpleNamespace(is_accounting_enabled=lambda: True)):
            result = await p.process_document("ws", "d1")
        assert result is None


class TestAiExtract:
    @pytest.fixture(autouse=True)
    def _fake_ai_names(self):
        # The real integrations.ai_enhanced_service is absent in this
        # environment; the module falls back to None attrs (W109-3). Patch
        # the type/request attrs so the construction path is exercised.
        with patch.object(dp, "AITaskType", SimpleNamespace(NATURAL_LANGUAGE_COMMANDS="nlp")), \
             patch.object(dp, "AIModelType", SimpleNamespace(GPT_4="gpt4")), \
             patch.object(dp, "AIServiceType", SimpleNamespace(OPENAI="openai")), \
             patch.object(dp, "AIRequest", lambda **kw: SimpleNamespace(**kw)):
            yield

    async def test_dict_output(self, proc):
        p, db = proc
        resp = SimpleNamespace(output_data={"entity_name": "X"})
        p_ai = MagicMock()
        p_ai.process_ai_request = AsyncMock(return_value=resp)
        with patch.object(dp, "ai_enhanced_service", p_ai):
            data = await p._ai_extract("text", "bill")
        assert data == {"entity_name": "X"}
        req = p_ai.process_ai_request.await_args.args[0]
        assert req.task_type == "nlp"
        assert req.service_type == "openai"

    async def test_fenced_string_output(self, proc):
        p, db = proc
        resp = SimpleNamespace(output_data='```json\n{"a": 1}\n```')
        p_ai = MagicMock()
        p_ai.process_ai_request = AsyncMock(return_value=resp)
        with patch.object(dp, "ai_enhanced_service", p_ai):
            data = await p._ai_extract("text", "invoice")
        assert data == {"a": 1}

    async def test_exception_returns_none(self, proc):
        p, db = proc
        p_ai = MagicMock()
        p_ai.process_ai_request = AsyncMock(side_effect=RuntimeError("ai down"))
        with patch.object(dp, "ai_enhanced_service", p_ai):
            data = await p._ai_extract("text", "bill")
        assert data is None

    async def test_missing_ai_service_returns_none(self, proc):
        p, db = proc
        with patch.object(dp, "ai_enhanced_service", None):
            data = await p._ai_extract("text", "bill")
        assert data is None


class TestEntityAndRecords:
    def test_get_or_create_entity_found(self, proc):
        p, db = proc
        entity = SimpleNamespace(id="e1")
        db.query.return_value.filter.return_value.first.return_value = entity
        result = p._get_or_create_entity("ws", "Vendor Inc", dp.EntityType.VENDOR)
        assert result is entity
        db.add.assert_not_called()

    def test_get_or_create_entity_created(self, proc):
        p, db = proc
        db.query.return_value.filter.return_value.first.return_value = None
        result = p._get_or_create_entity("ws", "NewCo", dp.EntityType.CUSTOMER)
        assert result.type == dp.EntityType.CUSTOMER
        db.add.assert_called_once()
        db.flush.assert_called_once()

    def test_create_bill_mapping(self, proc):
        p, db = proc
        with patch.object(p, "_parse_date", side_effect=lambda x: f"parsed:{x}"):
            bill = p._create_bill("ws", "v1", {
                "number": "B1", "date": "d", "due_date": "dd",
                "amount": "42.5", "currency": "GBP", "description": "desc",
            })
        assert bill.vendor_id == "v1"
        assert bill.amount == 42.5
        assert bill.issue_date == "parsed:d"
        assert bill.status == dp.BillStatus.DRAFT

    def test_create_invoice_defaults(self, proc):
        p, db = proc
        inv = p._create_invoice("ws", "c1", {})
        assert inv.amount == 0.0
        assert inv.currency == "USD"
        assert inv.invoice_number is None

    def test_parse_date_missing(self, proc):
        p, db = proc
        dt = p._parse_date(None)
        assert isinstance(dt, datetime)

    def test_parse_date_valid(self, proc):
        p, db = proc
        with patch.object(dp.dateparser, "parse", return_value=datetime(2026, 1, 1)):
            assert p._parse_date("2026-01-01") == datetime(2026, 1, 1)

    def test_parse_date_none_result(self, proc):
        p, db = proc
        with patch.object(dp.dateparser, "parse", return_value=None):
            assert isinstance(p._parse_date("garbage"), datetime)

    def test_parse_date_exception(self, proc):
        p, db = proc
        with patch.object(dp.dateparser, "parse", side_effect=ValueError("bad")):
            assert isinstance(p._parse_date("garbage"), datetime)


class TestPerformOcr:
    async def test_no_service(self, proc):
        p, db = proc
        p.pdf_ocr_service = None
        assert await p._perform_ocr(_doc()) is None

    async def test_file_missing(self, proc, tmp_path):
        p, db = proc
        p.pdf_ocr_service = MagicMock()
        assert await p._perform_ocr(_doc(file_path=str(tmp_path / "nope.pdf"))) is None

    async def test_success(self, proc, tmp_path):
        p, db = proc
        f = tmp_path / "ok.pdf"
        f.write_bytes(b"data")
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(return_value={
            "success": True, "extracted_text": "TEXT", "total_chars": 4,
        })
        p.pdf_ocr_service = ocr
        result = await p._perform_ocr(_doc(file_path=str(f)))
        assert result == "TEXT"
        kwargs = ocr.process_pdf.await_args.kwargs
        assert kwargs["perform_ocr"] is True
        assert kwargs["fallback_strategy"] == "cascade"

    async def test_failure(self, proc, tmp_path):
        p, db = proc
        f = tmp_path / "bad.pdf"
        f.write_bytes(b"data")
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(return_value={"success": False, "error": "nope"})
        p.pdf_ocr_service = ocr
        assert await p._perform_ocr(_doc(file_path=str(f))) is None

    async def test_exception(self, proc, tmp_path):
        p, db = proc
        f = tmp_path / "crash.pdf"
        f.write_bytes(b"data")
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(side_effect=RuntimeError("boom"))
        p.pdf_ocr_service = ocr
        assert await p._perform_ocr(_doc(file_path=str(f))) is None
