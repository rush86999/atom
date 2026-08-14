"""Coverage wave W74a — accounting services round 2 (7 modules).

Targets (>=95% statement coverage, standalone):
- accounting/assistant.py            (0% before)
- accounting/close_agent.py          (0% before)
- accounting/dashboard_service.py    (32% before)
- accounting/document_processor.py   (0% before)
- accounting/fpa_service.py          (68% before)
- accounting/margin_service.py       (55% before)
- accounting/reconciliation.py       (0% before)

Pattern (mirrors test_covpush_w72a_accounting.py): mocked deps, zero LLM
spend, no network, no real DB (scripted fake sessions). The
`integrations.ai_enhanced_service` module is absent from this checkout, so a
fake module is injected into sys.modules before importing the two modules
that need it (assistant, document_processor) — the same technique already
used by test_covpush_w72a_accounting / test_covpush_ghgl.
"""
import asyncio
import builtins
import importlib
import sys
import types
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fake `integrations.ai_enhanced_service` module (absent from this checkout).
# MUST be registered before importing accounting.assistant / document_processor.
# ---------------------------------------------------------------------------
# Share ONE canonical fake across wave files when the real module is
# absent — two files registering distinct ModuleType objects for the same
# name made batch order decide which object sys.modules held, so identity
# assertions compared across instances and failed depending on import order.
_ai_mod = sys.modules.get("integrations.ai_enhanced_service")
if _ai_mod is None or not hasattr(_ai_mod, "AITaskType"):
    _ai_mod = types.ModuleType("integrations.ai_enhanced_service")
    _ai_mod.AIModelType = SimpleNamespace(GPT_4="gpt-4")
    _ai_mod.AIServiceType = SimpleNamespace(OPENAI="openai")
    _ai_mod.AITaskType = SimpleNamespace(NATURAL_LANGUAGE_COMMANDS="natural_language_commands")
    sys.modules["integrations.ai_enhanced_service"] = _ai_mod


class _AIRequest:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


_ai_mod.AIRequest = _AIRequest
if not hasattr(_ai_mod, "ai_enhanced_service"):
    # Only the first wave file to load creates the shared service mock —
    # rebinding here would wipe another file's configured return_value and
    # break batch runs ('<=' not supported between AsyncMock and int).
    _ai_mod.ai_enhanced_service = MagicMock()
    _ai_mod.ai_enhanced_service.process_ai_request = AsyncMock()
    # Honor the real service contract for callers that import the module
    # (e.g. api/marketing_routes' stub fallback expects generate_insights
    # to return the stub envelope when the service is absent).
    _ai_mod.ai_enhanced_service.generate_insights = AsyncMock(
        return_value={"status": "stub", "message": "AI Enhanced service not available"}
    )
sys.modules["integrations.ai_enhanced_service"] = _ai_mod

from accounting import (  # noqa: E402
    assistant as assist_mod,
    close_agent as ca_mod,
    dashboard_service as dash_mod,
    document_processor as doc_mod,
    fpa_service as fpa_mod,
    margin_service as marg_mod,
    reconciliation as rec_mod,
)
from accounting.models import (  # noqa: E402
    Account,
    AccountType,
    EntryType,
    JournalEntry,
    Transaction,
)
from core.models import BusinessProductService  # noqa: E402
from ecommerce.models import EcommerceOrderItem  # noqa: E402

from accounting.assistant import AccountingAssistant  # noqa: E402
from accounting.close_agent import CloseChecklistAgent  # noqa: E402
from accounting.dashboard_service import AccountingDashboardService  # noqa: E402
from accounting.document_processor import AIDocumentProcessor  # noqa: E402
from accounting.fpa_service import FPAService  # noqa: E402
from accounting.margin_service import MarginCalculatorService  # noqa: E402
from accounting.reconciliation import ReconciliationService  # noqa: E402


# ---------------------------------------------------------------------------
# Fake session plumbing: per-model scripted results. Un-keyed query models
# (e.g. fresh `func.sum(...)` expressions) are served from an ordered queue.
# ---------------------------------------------------------------------------
class _FakeQuery:
    def __init__(self, db, model):
        self._db = db
        self._model = model

    def filter(self, *args, **kwargs):
        self._db.last_filter_kwargs = kwargs
        return self

    def options(self, *args, **kwargs):
        return self

    def joinedload(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def with_entities(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def having(self, *args, **kwargs):
        return self

    def first(self):
        return self._db._result(self._model, single=True)

    def all(self):
        return self._db._result(self._model, single=False)

    def scalar(self):
        return self._db._result(self._model, single=True)

    def count(self):
        return self._db._result(self._model, single=True)


class _FakeDB:
    def __init__(self, results=None, seq=None):
        self._specs = results or {}
        self._seq = list(seq or [])
        self._counts = {}
        self.added = []
        self.flushes = 0
        self.commits = 0
        self.refreshed = []
        self.last_filter_kwargs = {}

    def query(self, model):
        self._counts[model] = self._counts.get(model, 0) + 1
        return _FakeQuery(self, model)

    def _result(self, model, single):
        spec = self._specs.get(model)
        if spec is None:
            rows = self._seq.pop(0) if self._seq else []
        else:
            idx = self._counts.get(model, 0) - 1
            rows = spec(idx) if callable(spec) else (spec if spec is not None else [])
        rows = rows if isinstance(rows, list) else [rows]
        if single:
            return rows[0] if rows else None
        return list(rows)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def _mk_account(acc_id="acc-1", name="Cash", code="1000", acc_type=AccountType.ASSET):
    return SimpleNamespace(id=acc_id, name=name, code=code, type=acc_type)


def _mk_entry(acc_type, entry_type, amount):
    return SimpleNamespace(account=SimpleNamespace(type=acc_type), type=entry_type, amount=amount)


def _mk_doc(**overrides):
    doc = SimpleNamespace(
        id="doc-1",
        workspace_id="ws1",
        file_path="/tmp/invoice.pdf",
        extracted_data=None,
        bill_id=None,
        invoice_id=None,
    )
    for k, v in overrides.items():
        setattr(doc, k, v)
    return doc


def _mk_tx(external_id=None, tx_id="tx-1", metadata_json=None):
    return SimpleNamespace(
        id=tx_id,
        external_id=external_id,
        description=f"desc-{external_id}",
        metadata_json=metadata_json,
    )


def _patched_ai(output=None, side_effect=None):
    ai = MagicMock()
    if side_effect is not None:
        ai.process_ai_request = AsyncMock(side_effect=side_effect)
    else:
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(output_data=output))
    return ai


# ===========================================================================
# AccountingAssistant
# ===========================================================================
class TestAccountingAssistant:
    def _run(self, db, output=None, side_effect=None):
        ai = _patched_ai(output=output, side_effect=side_effect)
        ledger = MagicMock()
        ledger.get_account_balance = MagicMock(return_value=12345.67)
        with patch.object(assist_mod, "ai_enhanced_service", ai), patch.object(
            assist_mod, "EventSourcedLedger", return_value=ledger
        ):
            svc = AccountingAssistant(db)
            result = asyncio.run(svc.process_query("ws1", "what's my balance?"))
        return result, svc, ledger

    def test_ledger_is_initialized_from_db(self):
        db = _FakeDB()
        _, svc, _ = self._run(db, output={"intent": "unknown"})
        assert svc.db is db
        assert svc.ledger is not None

    def test_get_balance_found(self):
        db = _FakeDB({Account: [_mk_account(name="Bank of America")]})
        result, _, ledger = self._run(
            db, output={"intent": "get_balance", "params": {"account_name": "Bank"}}
        )
        assert result["answer"] == "The current balance of Bank of America is $12,345.67."
        assert result["data"]["balance"] == 12345.67
        ledger.get_account_balance.assert_called_once_with("acc-1")

    def test_get_balance_not_found(self):
        db = _FakeDB({Account: []})
        result, _, ledger = self._run(
            db, output={"intent": "get_balance", "params": {"account_name": "Nope"}}
        )
        assert result["answer"] == "I couldn't find an account named 'Nope'."
        ledger.get_account_balance.assert_not_called()

    def test_runway_no_cash_account(self):
        db = _FakeDB({Account: []})
        result, _, _ = self._run(db, output={"intent": "get_runway"})
        assert result["answer"] == "I need a cash account to calculate runway."

    def test_runway_infinite_burn_zero(self):
        db = _FakeDB({Account: [_mk_account()]}, seq=[0.0])
        result, _, _ = self._run(db, output={"intent": "get_runway"})
        assert "runway is infinite" in result["answer"]

    def test_runway_positive(self):
        db = _FakeDB({Account: [_mk_account()]}, seq=[2000.0])
        result, _, _ = self._run(db, output={"intent": "get_runway"})
        assert "$12,345.67" in result["answer"]
        assert "$2,000.00/mo" in result["answer"]
        assert "6.2 months" in result["answer"]
        assert result["data"] == {"cash": 12345.67, "burn": 2000.0, "runway": 6.172835}

    def test_check_overdue_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output={"intent": "check_overdue"})
        assert result == {"intent": "check_overdue"}

    def test_get_aging_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output={"intent": "get_aging"})
        assert result == {"intent": "get_aging"}

    def test_check_close_readiness_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(
            db, output={"intent": "check_close_readiness", "params": {"period": "2026-01"}}
        )
        assert result == {"intent": "check_close_readiness", "params": {"period": "2026-01"}}

    def test_get_tax_estimate_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output={"intent": "get_tax_estimate"})
        assert result == {"intent": "get_tax_estimate"}

    def test_get_cash_forecast_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output={"intent": "get_cash_forecast"})
        assert result == {"intent": "get_cash_forecast"}

    def test_run_scenario_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(
            db, output={"intent": "run_scenario", "params": {"weekly_impact": -100}}
        )
        assert result == {"intent": "run_scenario", "params": {"weekly_impact": -100}}

    def test_get_intercompany_report_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output={"intent": "get_intercompany_report"})
        assert result == {"intent": "get_intercompany_report"}

    def test_record_transaction_intent(self):
        db = _FakeDB()
        result, _, _ = self._run(
            db,
            output={
                "intent": "record_transaction",
                "params": {"amount": 50, "description": "coffee"},
            },
        )
        assert result["intent"] == "record_transaction"
        assert result["extracted_params"] == {"amount": 50, "description": "coffee"}

    def test_unknown_intent_fallback(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output={"intent": "build_rocket"})
        assert result["intent"] == "build_rocket"
        assert "not sure how to help" in result["answer"]

    def test_missing_intent_key_defaults_unknown(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output={"params": {}})
        assert result["intent"] == "unknown"

    def test_ai_response_as_json_string(self):
        db = _FakeDB({Account: [_mk_account()]})
        result, _, _ = self._run(
            db, output='{"intent": "get_balance", "params": {"account_name": "Cash"}}'
        )
        assert "current balance of Cash" in result["answer"]

    def test_ai_response_bad_json_string(self):
        db = _FakeDB()
        result, _, _ = self._run(db, output="not-json-at-all")
        assert "Sorry, I encountered an error" in result["answer"]

    def test_ai_service_error_returns_message(self):
        db = _FakeDB()
        result, _, _ = self._run(db, side_effect=RuntimeError("boom"))
        assert "Sorry, I encountered an error: boom" in result["answer"]


# ===========================================================================
# CloseChecklistAgent
# ===========================================================================
class TestCloseChecklistAgent:
    def _close_rec(self, **kwargs):
        meta = kwargs.pop("metadata_json", None)
        return SimpleNamespace(
            workspace_id="ws1",
            period="2026-01",
            metadata_json=meta,
            is_closed=False,
            closed_at=None,
            closed_by=None,
            **kwargs,
        )

    def test_all_clear_creates_close_record(self):
        db = _FakeDB(
            {
                Transaction: 0,
                JournalEntry.transaction_id: [],
                ca_mod.Bill: 0,
                ca_mod.FinancialClose: [],
            }
        )
        result = asyncio.run(CloseChecklistAgent(db).run_close_check("ws1", "2026-01"))
        assert result["is_ready"] is True
        assert [c["status"] for c in result["checklist"]] == ["complete", "complete", "complete"]
        assert result["blockers"] == []
        assert db.commits == 1
        assert len(db.added) == 1
        assert db.added[0].period == "2026-01"
        assert db.added[0].metadata_json is result

    def test_blockers_present(self):
        db = _FakeDB(
            {
                Transaction: 3,
                JournalEntry.transaction_id: [(1,), (2,)],
                ca_mod.Bill: 2,
                ca_mod.FinancialClose: [],
            }
        )
        result = asyncio.run(CloseChecklistAgent(db).run_close_check("ws1", "2026-01"))
        assert result["is_ready"] is False
        assert len(result["blockers"]) == 2
        assert any("pending categorization" in b for b in result["blockers"])
        assert any("unbalanced" in b for b in result["blockers"])
        assert [c["status"] for c in result["checklist"]] == ["blocked", "blocked", "warning"]

    def test_open_bills_only_warning(self):
        db = _FakeDB(
            {
                Transaction: 0,
                JournalEntry.transaction_id: [],
                ca_mod.Bill: 5,
                ca_mod.FinancialClose: [],
            }
        )
        result = asyncio.run(CloseChecklistAgent(db).run_close_check("ws1", "2026-01"))
        assert result["is_ready"] is True
        assert result["checklist"][2]["status"] == "warning"
        assert result["checklist"][2]["note"] == "5 bills are still open."

    def test_existing_close_record_updated(self):
        rec = self._close_rec(metadata_json={"old": True})
        db = _FakeDB(
            {
                Transaction: 0,
                JournalEntry.transaction_id: [],
                ca_mod.Bill: 0,
                ca_mod.FinancialClose: [rec],
            }
        )
        result = asyncio.run(CloseChecklistAgent(db).run_close_check("ws1", "2026-01"))
        assert rec.metadata_json is result
        assert db.added == []

    def test_close_period_not_ready(self):
        db = _FakeDB(
            {
                Transaction: 2,
                JournalEntry.transaction_id: [],
                ca_mod.Bill: 0,
                ca_mod.FinancialClose: [],
            }
        )
        result = asyncio.run(CloseChecklistAgent(db).close_period("ws1", "2026-01", "user-9"))
        assert result["success"] is False
        assert "Cannot close period" in result["message"]
        assert result["blockers"]

    def test_close_period_success(self):
        rec = self._close_rec()
        db = _FakeDB(
            {
                Transaction: 0,
                JournalEntry.transaction_id: [],
                ca_mod.Bill: 0,
                ca_mod.FinancialClose: [rec],
            }
        )
        result = asyncio.run(CloseChecklistAgent(db).close_period("ws1", "2026-01", "user-9"))
        assert result["success"] is True
        assert rec.is_closed is True
        assert rec.closed_by == "user-9"
        assert rec.closed_at is not None
        assert db.commits == 2


# ===========================================================================
# AccountingDashboardService
# ===========================================================================
class TestAccountingDashboardService:
    def test_profit_average_runway_12(self):
        db = _FakeDB(
            {Account: [_mk_account()], JournalEntry: [_mk_entry(AccountType.REVENUE, EntryType.CREDIT, 90.0)]},
            seq=[100.0, 40.0, 250.0, 75.0],
        )
        result = AccountingDashboardService(db).get_financial_summary("ws1")
        assert result["total_cash"] == 60.0
        assert result["accounts_payable"] == 250.0
        assert result["accounts_receivable"] == 75.0
        assert result["monthly_burn"] == 0.0
        assert result["net_profit_avg"] == 30.0
        assert result["runway_months"] == 12.0

    def test_loss_average_burn_and_runway(self):
        db = _FakeDB(
            {
                Account: [_mk_account()],
                JournalEntry: [
                    _mk_entry(AccountType.REVENUE, EntryType.DEBIT, 100.0),
                    _mk_entry(AccountType.EXPENSE, EntryType.CREDIT, 30.0),
                ],
            },
            seq=[100.0, 40.0, 0.0, 0.0],
        )
        result = AccountingDashboardService(db).get_financial_summary("ws1")
        assert result["net_profit_avg"] == -23.33
        assert result["monthly_burn"] == 23.33
        assert result["runway_months"] == 2.6

    def test_expense_debit_and_asset_skip(self):
        db = _FakeDB(
            {
                Account: [_mk_account()],
                JournalEntry: [
                    _mk_entry(AccountType.EXPENSE, EntryType.DEBIT, 10.0),
                    _mk_entry(AccountType.ASSET, EntryType.DEBIT, 999.0),
                ],
            },
            seq=[0.0, 0.0, None, None],
        )
        result = AccountingDashboardService(db).get_financial_summary("ws1")
        assert result["accounts_payable"] == 0.0
        assert result["accounts_receivable"] == 0.0
        assert result["net_profit_avg"] == -3.33
        assert result["monthly_burn"] == 3.33
        assert result["runway_months"] == 0.0

    def test_error_path_returns_error_dict(self):
        db = _FakeDB()
        svc = AccountingDashboardService(db)
        svc.fpa_service.get_current_cash_balance = MagicMock(side_effect=RuntimeError("kaput"))
        result = svc.get_financial_summary("ws1")
        assert result["error"] == "kaput"
        assert result["total_cash"] == 0


# ===========================================================================
# AIDocumentProcessor
# ===========================================================================
class TestAIDocumentProcessor:
    def _settings(self, enabled):
        return SimpleNamespace(is_accounting_enabled=lambda: enabled)

    def _processor(self, db, ocr=None):
        with patch.object(doc_mod, "PDFOCRService", return_value=ocr or MagicMock()):
            svc = AIDocumentProcessor(db)
        return svc

    def _extract(self, data, side_effect=None):
        ai = _patched_ai(output=data, side_effect=side_effect)
        return patch.object(doc_mod, "ai_enhanced_service", ai)

    def test_disabled_skips_processing(self):
        db = _FakeDB()
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(False)):
            svc = self._processor(db)
            assert asyncio.run(svc.process_document("ws1", "doc-1")) is None

    def test_document_not_found(self):
        db = _FakeDB({doc_mod.Document: []})
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            svc = self._processor(db)
            assert asyncio.run(svc.process_document("ws1", "doc-1")) is None

    def test_no_raw_text_no_ocr_service(self):
        db = _FakeDB({doc_mod.Document: [_mk_doc()]})
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            svc = self._processor(db, ocr=None)
            svc.pdf_ocr_service = None
            assert asyncio.run(svc.process_document("ws1", "doc-1")) is None

    def test_no_raw_text_no_file_path(self):
        db = _FakeDB({doc_mod.Document: [_mk_doc(file_path=None)]})
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            svc = self._processor(db)
            assert asyncio.run(svc.process_document("ws1", "doc-1")) is None

    def test_ocr_success_full_bill_flow(self, tmp_path):
        pdf = tmp_path / "bill.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        doc = _mk_doc(file_path=str(pdf))
        db = _FakeDB({doc_mod.Document: [doc], doc_mod.Entity: [SimpleNamespace(id="e-1")]})
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(
            return_value={"success": True, "extracted_text": "Acme Corp bill $100", "total_chars": 20}
        )
        extraction = {
            "entity_name": "Acme Corp",
            "number": "B-1",
            "date": "2026-01-10",
            "due_date": "2026-02-10",
            "amount": "100.5",
            "currency": "USD",
            "description": "hosting",
        }
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            with self._extract(extraction):
                svc = self._processor(db, ocr=ocr)
                record = asyncio.run(svc.process_document("ws1", "doc-1"))
        assert record is not None
        assert record.bill_number == "B-1"
        assert float(record.amount) == 100.5
        assert record.vendor_id == "e-1"
        assert doc.bill_id == record.id
        assert doc.extracted_data == extraction
        assert db.commits == 1
        assert db.refreshed == [record]
        ocr.process_pdf.assert_awaited_once()
        args = ocr.process_pdf.await_args
        assert args.kwargs["perform_ocr"] is True
        assert args.kwargs["fallback_strategy"] == "cascade"

    def test_ocr_result_failure(self, tmp_path):
        pdf = tmp_path / "bill.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        db = _FakeDB({doc_mod.Document: [_mk_doc(file_path=str(pdf))]})
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(return_value={"success": False, "error": "no text found"})
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            svc = self._processor(db, ocr=ocr)
            assert asyncio.run(svc.process_document("ws1", "doc-1")) is None

    def test_ocr_exception(self, tmp_path):
        pdf = tmp_path / "bill.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        db = _FakeDB({doc_mod.Document: [_mk_doc(file_path=str(pdf))]})
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(side_effect=RuntimeError("tesseract missing"))
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            svc = self._processor(db, ocr=ocr)
            assert asyncio.run(svc.process_document("ws1", "doc-1")) is None

    def test_ocr_file_missing(self):
        db = _FakeDB({doc_mod.Document: [_mk_doc(file_path="/nonexistent/nowhere.pdf")]})
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(return_value={"success": True, "extracted_text": "x"})
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            svc = self._processor(db, ocr=ocr)
            assert asyncio.run(svc.process_document("ws1", "doc-1")) is None
        ocr.process_pdf.assert_not_awaited()

    def test_extraction_returns_none(self):
        db = _FakeDB({doc_mod.Document: [_mk_doc(extracted_data={"raw_text": "hello"})]})
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            with self._extract(None):
                svc = self._processor(db)
                assert asyncio.run(svc.process_document("ws1", "doc-1")) is None

    def test_bill_success_with_raw_text(self):
        doc = _mk_doc(extracted_data={"raw_text": "Acme Corp invoice data"})
        db = _FakeDB({doc_mod.Document: [doc], doc_mod.Entity: [SimpleNamespace(id="e-1")]})
        extraction = {
            "entity_name": "Acme Corp",
            "number": "B-2",
            "date": "2026-03-01",
            "due_date": None,
            "amount": 55,
            "currency": "EUR",
            "description": None,
        }
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            with self._extract(extraction):
                svc = self._processor(db)
                record = asyncio.run(svc.process_document("ws1", "doc-1"))
        assert record.bill_number == "B-2"
        assert record.currency == "EUR"
        assert record.description is None
        assert db.added == [record]
        assert db.commits == 1

    def test_invoice_success_with_entity_created(self):
        doc = _mk_doc(extracted_data={"raw_text": "data"})
        db = _FakeDB({doc_mod.Document: [doc], doc_mod.Entity: []})
        extraction = {
            "entity_name": "New Customer Inc",
            "number": "INV-9",
            "amount": 199.99,
            "currency": "USD",
            "description": "services",
        }
        with patch.object(doc_mod, "get_automation_settings", return_value=self._settings(True)):
            with self._extract(extraction):
                svc = self._processor(db)
                record = asyncio.run(svc.process_document("ws1", "doc-1", doc_type="invoice"))
        assert record.invoice_number == "INV-9"
        assert doc.invoice_id == record.id
        assert len(db.added) == 2
        assert db.flushes == 1
        created = db.added[0]
        assert created.name == "New Customer Inc"
        assert created.workspace_id == "ws1"
        assert record.customer_id == created.id

    def test_ai_extract_dict_output(self):
        db = _FakeDB()
        svc = self._processor(db)
        with self._extract({"entity_name": "X"}):
            assert asyncio.run(svc._ai_extract("text", "bill")) == {"entity_name": "X"}

    def test_ai_extract_markdown_string(self):
        db = _FakeDB()
        svc = self._processor(db)
        with self._extract('```json\n{"entity_name": "X"}\n```'):
            assert asyncio.run(svc._ai_extract("text", "bill")) == {"entity_name": "X"}

    def test_ai_extract_invalid_json_string(self):
        db = _FakeDB()
        svc = self._processor(db)
        with self._extract("{broken json"):
            assert asyncio.run(svc._ai_extract("text", "bill")) is None

    def test_ai_extract_exception(self):
        db = _FakeDB()
        svc = self._processor(db)
        with self._extract(None, side_effect=RuntimeError("provider down")):
            assert asyncio.run(svc._ai_extract("text", "bill")) is None

    def test_parse_date_none_returns_now(self):
        svc = self._processor(_FakeDB())
        dt = svc._parse_date(None)
        assert dt.tzinfo == timezone.utc

    def test_parse_date_valid(self):
        svc = self._processor(_FakeDB())
        dt = svc._parse_date("2026-01-15")
        assert dt.year == 2026 and dt.month == 1 and dt.day == 15

    def test_parse_date_unparseable(self):
        svc = self._processor(_FakeDB())
        with patch.object(doc_mod.dateparser, "parse", return_value=None):
            dt = svc._parse_date("not a date")
        assert dt.tzinfo == timezone.utc

    def test_parse_date_parse_raises(self):
        svc = self._processor(_FakeDB())
        with patch.object(doc_mod.dateparser, "parse", side_effect=ValueError("boom")):
            dt = svc._parse_date("not a date")
        assert dt.tzinfo == timezone.utc

    def test_perform_ocr_direct_success(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(
            return_value={"success": True, "extracted_text": "hello", "total_chars": 5}
        )
        db = _FakeDB()
        svc = self._processor(db, ocr=ocr)
        text = asyncio.run(svc._perform_ocr(SimpleNamespace(file_path=str(pdf), id="doc-1")))
        assert text == "hello"

    def test_pdf_ocr_module_absent(self):
        real_import = builtins.__import__

        def _blocked(name, *args, **kwargs):
            if name == "integrations.pdf_processing.pdf_ocr_service":
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=_blocked):
                importlib.reload(doc_mod)
            assert doc_mod.PDF_OCR_AVAILABLE is False
            assert doc_mod.PDFOCRService is None
            db = _FakeDB()
            svc = doc_mod.AIDocumentProcessor(db)
            assert svc.pdf_ocr_service is None
            assert asyncio.run(svc._perform_ocr(SimpleNamespace(file_path="/x.pdf", id="d"))) is None
        finally:
            importlib.reload(doc_mod)
        assert doc_mod.PDF_OCR_AVAILABLE is True


# ===========================================================================
# FPAService
# ===========================================================================
class TestFPAService:
    def test_cash_balance_no_accounts(self):
        db = _FakeDB({Account: []})
        assert FPAService(db).get_current_cash_balance("ws1") == 0.0

    def test_cash_balance_with_accounts(self):
        db = _FakeDB(
            {Account: [_mk_account("cash-1"), _mk_account("cash-2")]},
            seq=[100.0, 40.0, 50.0, None],
        )
        result = FPAService(db).get_current_cash_balance("ws1")
        assert result == 110.0

    def test_forecast_no_history(self):
        db = _FakeDB(
            {
                Account: [],
                JournalEntry: [],
                fpa_mod.Bill: [],
                fpa_mod.Invoice: [],
                fpa_mod.Milestone: [],
            }
        )
        forecast = FPAService(db).get_13_week_forecast("ws1")
        assert len(forecast) == 13
        assert forecast[0]["week"] == 1
        assert forecast[12]["week"] == 13
        assert all(f["projected_change"] == 0.0 for f in forecast)
        assert forecast[0]["details"]["average_burn"] == 0.0

    def test_forecast_with_history_and_items(self):
        now = datetime.now(timezone.utc)
        historical = [
            _mk_entry(AccountType.REVENUE, EntryType.CREDIT, 100.0),
            _mk_entry(AccountType.REVENUE, EntryType.DEBIT, 20.0),
            _mk_entry(AccountType.EXPENSE, EntryType.DEBIT, 30.0),
            _mk_entry(AccountType.EXPENSE, EntryType.CREDIT, 5.0),
            _mk_entry(AccountType.ASSET, EntryType.DEBIT, 10.0),
        ]
        bills = [
            SimpleNamespace(amount=50.0, due_date=now + timedelta(days=1)),
            SimpleNamespace(amount=999.0, due_date=now + timedelta(days=200)),
            SimpleNamespace(amount=77.0, due_date=None),
        ]
        invoices = [
            SimpleNamespace(amount=30.0, due_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)),
            SimpleNamespace(amount=66.0, due_date=None),
        ]
        milestones = [
            SimpleNamespace(amount=20.0, due_date=now + timedelta(days=2)),
            SimpleNamespace(amount=88.0, due_date=None),
        ]
        db = _FakeDB(
            {
                Account: [_mk_account()],
                JournalEntry: historical,
                fpa_mod.Bill: bills,
                fpa_mod.Invoice: invoices,
                fpa_mod.Milestone: milestones,
            },
            seq=[100.0, 40.0],
        )
        forecast = FPAService(db).get_13_week_forecast("ws1")
        assert len(forecast) == 13
        week1 = forecast[0]
        assert week1["details"]["outflows"] == 50.0
        assert week1["details"]["inflows"] == 30.0
        assert week1["details"]["contracted_revenue"] == 20.0
        assert week1["details"]["average_burn"] == pytest.approx(55.0 / 12.0)
        assert forecast[4]["details"]["inflows"] == 0.0
        assert forecast[12]["projected_balance"] is not None

    def test_forecast_with_product_service_id(self):
        db = _FakeDB(
            {
                Account: [],
                JournalEntry: [],
                fpa_mod.Bill: [],
                fpa_mod.Invoice: [],
                fpa_mod.Milestone: [],
            }
        )
        forecast = FPAService(db).get_13_week_forecast("ws1", product_service_id="ps-1")
        assert len(forecast) == 13

    def test_run_scenario_no_scenarios(self):
        db = _FakeDB(
            {
                Account: [],
                JournalEntry: [],
                fpa_mod.Bill: [],
                fpa_mod.Invoice: [],
                fpa_mod.Milestone: [],
            }
        )
        result = FPAService(db).run_scenario("ws1", [])
        assert len(result) == 13
        assert all(r["impact"] == 0.0 for r in result)
        assert all(r["is_scenario"] is True for r in result)

    def test_run_scenario_with_scenarios(self):
        db = _FakeDB(
            {
                Account: [],
                JournalEntry: [],
                fpa_mod.Bill: [],
                fpa_mod.Invoice: [],
                fpa_mod.Milestone: [],
            }
        )
        scenarios = [
            {"name": "Hire Engineer", "weekly_impact": -2000, "start_week": 4},
            {"weekly_impact": 100},
        ]
        result = FPAService(db).run_scenario("ws1", scenarios)
        assert result[0]["impact"] == 100.0
        assert result[3]["impact"] == -1900.0
        assert result[12]["impact"] == -1900.0
        assert result[0]["projected_balance"] == 100.0
        assert result[12]["projected_balance"] == pytest.approx(100.0 * 3 - 1900.0 * 10)


# ===========================================================================
# MarginCalculatorService
# ===========================================================================
class TestMarginCalculatorService:
    def _user(self, user_id, rate):
        return SimpleNamespace(id=user_id, hourly_cost_rate=rate)

    def _task(self, task_id, assigned_to=None, actual_hours=None):
        return SimpleNamespace(id=task_id, assigned_to=assigned_to, actual_hours=actual_hours)

    @contextmanager
    def _session_ctx(self, db):
        @contextmanager
        def _cm():
            yield db

        with patch.object(marg_mod, "get_db_session", _cm):
            yield

    def test_labor_cost_without_db(self):
        db = _FakeDB({marg_mod.ProjectTask: []})
        with self._session_ctx(db):
            svc = MarginCalculatorService()
            assert svc.calculate_project_labor_cost("p-1") == 0.0

    def test_labor_cost_with_db(self):
        users = [self._user("u1", 100.0), None, self._user("u4", 0.0), self._user("u5", 10.0)]
        tasks = [
            self._task("t1", "u1", 10),
            self._task("t2", "u2", 5),
            self._task("t3", None, 5),
            self._task("t4", "u3", None),
            self._task("t5", "u4", 2),
            self._task("t6", "u5", 3.333),
        ]
        db = _FakeDB({marg_mod.ProjectTask: tasks, marg_mod.User: lambda i: [users[i]] if i < 4 else []})
        svc = MarginCalculatorService()
        assert svc.calculate_project_labor_cost("p-1", db) == 1033.33

    def test_project_margin_not_found(self):
        db = _FakeDB({marg_mod.Project: []})
        result = MarginCalculatorService().get_project_margin("p-x", db)
        assert result == {"error": "Project not found"}

    def test_project_margin_with_revenue(self):
        db = _FakeDB(
            {
                marg_mod.Project: [SimpleNamespace(id="p-1", name="Alpha", budget_amount=10000.0)],
                marg_mod.ProjectTask: [self._task("t1", "u1", 10)],
                marg_mod.User: [self._user("u1", 100.0)],
            }
        )
        result = MarginCalculatorService().get_project_margin("p-1", db)
        assert result["project_id"] == "p-1"
        assert result["project_name"] == "Alpha"
        assert result["revenue"] == 10000.0
        assert result["labor_cost"] == 1000.0
        assert result["gross_margin"] == 9000.0
        assert result["margin_percentage"] == 90.0

    def test_project_margin_zero_revenue(self):
        db = _FakeDB(
            {
                marg_mod.Project: [SimpleNamespace(id="p-1", name="Beta", budget_amount=None)],
                marg_mod.ProjectTask: [],
            }
        )
        result = MarginCalculatorService().get_project_margin("p-1", db)
        assert result["revenue"] == 0.0
        assert result["margin_percentage"] == 0.0
        assert result["gross_margin"] == 0.0

    def test_project_margin_without_db(self):
        db = _FakeDB(
            {
                marg_mod.Project: [SimpleNamespace(id="p-1", name="Alpha", budget_amount=500.0)],
                marg_mod.ProjectTask: [],
            }
        )
        with self._session_ctx(db):
            result = MarginCalculatorService().get_project_margin("p-1")
        assert result["revenue"] == 500.0

    def test_product_margins_without_db(self):
        db = _FakeDB({BusinessProductService: []})
        with self._session_ctx(db):
            result = MarginCalculatorService().get_product_margins("ws1")
        assert result == []

    def test_product_margins_empty(self):
        db = _FakeDB({BusinessProductService: []})
        result = MarginCalculatorService().get_product_margins("ws1", db)
        assert result == []

    def test_product_margins_with_data(self):
        product_1 = SimpleNamespace(id="prod-1", name="Service A", unit_cost=5.0)
        product_2 = SimpleNamespace(id="prod-2", name="Product B", unit_cost=2.0)
        contract_1 = SimpleNamespace(id="c-1", product_service_id="prod-1")
        contract_2 = SimpleNamespace(id="c-2", product_service_id="prod-1")
        project_1 = SimpleNamespace(id="pr-1", budget_amount=1000.0)
        project_2 = SimpleNamespace(id="pr-2", budget_amount=2000.0)
        task_1 = self._task("t1", "u1", 10)
        task_2 = self._task("t2", "u2", 5)
        order_item = SimpleNamespace(product_id="prod-1", price=50.0, quantity=3)
        db = _FakeDB(
            {
                BusinessProductService: [product_1, product_2],
                marg_mod.Contract: lambda i: [contract_1, contract_2] if i == 0 else [],
                marg_mod.Project: lambda i: [project_1, project_2] if i == 0 else [],
                marg_mod.ProjectTask: lambda i: [task_1] if i == 0 else ([task_2] if i == 1 else []),
                marg_mod.User: lambda i: [self._user("u1", 100.0), self._user("u2", 20.0)][i]
                if i < 2
                else [],
                EcommerceOrderItem: lambda i: [order_item] if i == 0 else [],
            }
        )
        result = MarginCalculatorService().get_product_margins("ws1", db)
        assert len(result) == 2
        prod1 = result[0]
        assert prod1["product_name"] == "Service A"
        assert prod1["total_revenue"] == 1000.0 + 2000.0 + 150.0
        assert prod1["total_labor_cost"] == 1000.0 + 100.0 + 15.0
        assert prod1["gross_margin"] == pytest.approx(3150.0 - 1115.0)
        assert prod1["margin_percentage"] == round((3150.0 - 1115.0) / 3150.0 * 100, 2)
        prod2 = result[1]
        assert prod2["total_revenue"] == 0.0
        assert prod2["margin_percentage"] == 0.0

    def test_singleton_exists(self):
        assert marg_mod.margin_calculator is not None


# ===========================================================================
# ReconciliationService
# ===========================================================================
class TestReconciliationService:
    def test_skipped_when_stripe_unavailable(self):
        db = _FakeDB()
        result = asyncio.run(
            ReconciliationService(db).reconcile_stripe("ws1", "tok-1", days_to_look_back=15)
        )
        assert result["status"] == "skipped"
        assert result["missing_in_ledger"] == []
        assert result["matched"] == []
        assert result["duplicates"] == []

    @pytest.fixture
    def stripe_enabled(self):
        mod = types.ModuleType("integrations.stripe_service")
        fake_service = MagicMock()
        mod.stripe_service = fake_service
        sys.modules["integrations.stripe_service"] = mod
        importlib.reload(rec_mod)
        yield fake_service
        del sys.modules["integrations.stripe_service"]
        importlib.reload(rec_mod)

    def test_flag_anomaly_not_found(self):
        db = _FakeDB({Transaction: []})
        assert ReconciliationService(db).flag_anomaly("tx-9", "why") is False
        assert db.commits == 0

    def test_flag_anomaly_without_meta(self):
        db = _FakeDB({Transaction: [_mk_tx("ext-1")]})
        assert ReconciliationService(db).flag_anomaly("tx-1", "duplicate") is True
        tx = db._specs[Transaction][0]
        assert tx.metadata_json == {"anomaly_flag": True, "anomaly_reason": "duplicate"}
        assert db.commits == 1

    def test_flag_anomaly_preserves_existing_meta(self):
        tx = _mk_tx("ext-1", metadata_json={"reviewed": False})
        db = _FakeDB({Transaction: [tx]})
        assert ReconciliationService(db).flag_anomaly("tx-1", "suspicious") is True
        assert tx.metadata_json["reviewed"] is False
        assert tx.metadata_json["anomaly_flag"] is True
        assert tx.metadata_json["anomaly_reason"] == "suspicious"

    def test_full_reconcile_with_stripe_pagination(self, stripe_enabled):
        tx1 = _mk_tx("ch_1", "t-1")
        tx2 = _mk_tx("ch_1", "t-2")
        tx3 = _mk_tx("ch_3", "t-3")
        db = _FakeDB({Transaction: [tx1, tx2, tx3]})

        def _list_payments(token, **params):
            if "starting_after" not in params:
                return {
                    "data": [
                        {
                            "id": "ch_1",
                            "amount": 5000,
                            "currency": "usd",
                            "description": "match me",
                            "created": 1700000000,
                        }
                    ],
                    "has_more": True,
                }
            if params["starting_after"] == "ch_1":
                return {
                    "data": [
                        {
                            "id": "ch_2",
                            "amount": 1234,
                            "currency": "eur",
                            "description": "missing in ledger",
                            "created": 1700000001,
                        }
                    ],
                    "has_more": True,
                }
            return {"data": [], "has_more": True}

        stripe_enabled.list_payments.side_effect = _list_payments
        result = asyncio.run(ReconciliationService(db).reconcile_stripe("ws1", "tok-1"))
        assert result["stripe_count"] == 2
        assert result["internal_count"] == 3
        assert result["matched_count"] == 1
        assert result["missing_count"] == 1
        assert result["missing_transactions"][0]["id"] == "ch_2"
        assert result["missing_transactions"][0]["amount"] == 12.34
        assert result["missing_transactions"][0]["currency"] == "eur"
        assert result["missing_transactions"][0]["created"] == 1700000001
        assert len(result["duplicates"]) == 1
        assert result["duplicates"][0]["external_id"] == "ch_1"
        assert result["duplicate_count"] == 1
        assert result["period_days"] == 30
        assert stripe_enabled.list_payments.call_count == 3
        first_call = stripe_enabled.list_payments.call_args_list[0]
        assert first_call.kwargs["limit"] == 100
        assert isinstance(first_call.kwargs["created"]["gte"], int)
        second_call = stripe_enabled.list_payments.call_args_list[1]
        assert second_call.kwargs["starting_after"] == "ch_1"
