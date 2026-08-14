"""Coverage wave W72a — accounting services edge coverage.

Targets (>=95% statement coverage, standalone):
- accounting/ap_service.py            (0% before)
- accounting/categorizer.py           (0% before — module was UNIMPORTABLE)
- accounting/credit_risk_engine.py    (0% before)
- accounting/revenue_recognition.py   (89% before)
- accounting/tax_service.py           (0% before)
- accounting/multi_entity.py          (0% before)

Pattern: mocked deps, zero LLM spend (ai_enhanced_service faked as an
AsyncMock module), no network, no real DB (scripted fake sessions). The
`integrations.ai_enhanced_service` module is absent from this checkout
(only the .archive copy exists), so the tests inject a fake module into
sys.modules before importing `accounting.categorizer` — the same
technique already used by test_covpush_ghgl.

Bug found + fixed in the assigned modules (regression tests below):
1. accounting/categorizer.py — `from integrations.ai_enhanced_service import
   (...)` at module scope crashed with ModuleNotFoundError on any checkout
   without that module (it does not exist here), making the whole module
   unimportable. Fixed with the repo's established optional-dependency
   pattern (try/except ImportError -> None names, mirroring
   core/business_health_service.py) plus a None-service guard so the AI
   path degrades to a None proposal instead of raising.
   Regression: test_propose_degrades_when_ai_module_absent (import guard)
   and test_propose_returns_none_when_ai_service_is_none (call guard).
"""
import asyncio
import importlib
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fake `integrations.ai_enhanced_service` module (absent from this checkout).
# MUST be registered before importing accounting.categorizer.
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
    ap_service as ap_mod,
    categorizer as cat_mod,
    credit_risk_engine as cre_mod,
    multi_entity as me_mod,
    revenue_recognition as rr_mod,
    tax_service as tax_mod,
)
from accounting.models import (  # noqa: E402
    AccountType,
    EntryType,
    EntityType,
    InvoiceStatus,
)

from accounting.ap_service import APService  # noqa: E402
from accounting.categorizer import AICategorizer  # noqa: E402
from accounting.credit_risk_engine import CreditRiskEngine  # noqa: E402
from accounting.multi_entity import IntercompanyManager  # noqa: E402
from accounting.tax_service import NexusType, TaxService  # noqa: E402


# ---------------------------------------------------------------------------
# Fake session plumbing (scripted per-model query results, keyed by the nth
# query on that model so the same model can serve different branches).
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

    def first(self):
        return self._db._result(self._model, single=True)

    def all(self):
        return self._db._result(self._model, single=False)


class _FakeDB:
    def __init__(self, results=None):
        self._specs = results or {}
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
        idx = self._counts.get(model, 0) - 1
        spec = self._specs.get(model)
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


def _mk_account(code, name=None, desc=None, acc_type=AccountType.EXPENSE):
    return SimpleNamespace(
        id=f"acc-{code}",
        name=name or f"Account {code}",
        description=desc,
        type=acc_type,
        code=code,
    )


def _mk_vendor(name="CloudServices Inc"):
    return SimpleNamespace(id="vendor-1", name=name, type=EntityType.VENDOR, workspace_id="ws1")


def _mk_doc(**overrides):
    doc = SimpleNamespace(
        id="doc-1",
        workspace_id="ws1",
        file_path="/tmp/invoice.pdf",
        extracted_data=None,
        bill_id=None,
    )
    for k, v in overrides.items():
        setattr(doc, k, v)
    return doc


class _FakeBill:
    _instances = []

    def __init__(self, **kwargs):
        self.id = "bill-1"
        self.transaction_id = None
        self.__dict__.update(kwargs)
        _FakeBill._instances.append(self)


class _FakeEntity:
    _instances = []

    workspace_id = None
    name = None
    type = MagicMock()

    def __init__(self, **kwargs):
        self.id = "vendor-new"
        self.__dict__.update(kwargs)
        _FakeEntity._instances.append(self)


# ===========================================================================
# APService
# ===========================================================================
class TestAPServiceProcessInvoice:
    @pytest.fixture(autouse=True)
    def _reset(self):
        _FakeBill._instances = []
        _FakeEntity._instances = []
        yield
        _FakeBill._instances = []
        _FakeEntity._instances = []

    def _make_service(self, db, ocr_text="Invoice INV-20260101 from CloudServices Inc"):
        ocr = MagicMock()
        ocr.process_pdf = AsyncMock(
            return_value={"extracted_content": {"text": ocr_text}, "confidence": 0.95}
        )
        ledger = MagicMock()
        ledger.record_transaction = MagicMock(return_value=SimpleNamespace(id="tx-1"))
        dee = MagicMock()
        dee.create_bill_entry.return_value = [SimpleNamespace()]
        return APService(db), ocr, ledger, dee

    def _patched_env(self):
        return (
            patch.object(ap_mod, "PDFOCRService", return_value=self._ocr),
            patch.object(ap_mod, "EventSourcedLedger", return_value=self._ledger),
            patch.object(ap_mod, "DoubleEntryEngine", self._dee),
            patch.object(ap_mod, "Bill", _FakeBill),
        )

    async def _run(self, db, **kwargs):
        self._ocr = MagicMock()
        self._ocr.process_pdf = AsyncMock(
            return_value={
                "extracted_content": {
                    "text": "Invoice INV-20260101 from CloudServices Inc for monthly subscription"
                },
                "confidence": 0.95,
            }
        )
        self._ledger = MagicMock()
        self._ledger.record_transaction = MagicMock(return_value=SimpleNamespace(id="tx-1"))
        self._dee = MagicMock()
        self._dee.create_bill_entry.return_value = [SimpleNamespace()]
        with patch.object(
            ap_mod, "PDFOCRService", return_value=self._ocr
        ), patch.object(ap_mod, "EventSourcedLedger", return_value=self._ledger), patch.object(
            ap_mod, "DoubleEntryEngine", self._dee
        ), patch.object(ap_mod, "Bill", _FakeBill):
            service = APService(db)
            result = await service.process_invoice_document(
                kwargs.get("document_id", "doc-1"), kwargs.get("workspace_id", "ws1")
            )
        return result, service, self._ocr, self._ledger, self._dee

    def test_document_not_found_raises(self):
        db = _FakeDB({ap_mod.Document: []})
        with pytest.raises(ValueError, match="not found"):
            asyncio.run(self._run(db))

    def test_full_success_records_bill_and_ledger(self):
        db = _FakeDB(
            {
                ap_mod.Document: [_mk_doc()],
                ap_mod.Entity: [_mk_vendor()],
                ap_mod.Account: lambda i: [_mk_account("2000", acc_type=AccountType.LIABILITY)]
                if i == 0
                else [_mk_account("5100")],
            }
        )
        result, _, _, ledger, dee = asyncio.run(self._run(db))
        assert result["status"] == "success"
        assert result["bill_id"] == "bill-1"
        assert result["transaction_id"] == "tx-1"
        assert result["vendor"] == "CloudServices Inc"
        assert result["amount"] == 299.99
        assert result["confidence"] == 0.95
        assert db.commits == 1
        assert db.flushes >= 2
        dee.create_bill_entry.assert_called_once()
        assert ledger.record_transaction.call_args.kwargs["source"] == "ap_automation"
        assert ledger.record_transaction.call_args.kwargs["metadata"]["bill_id"] == "bill-1"
        assert db.added[0].status.value == "open"

    def test_partial_success_when_accounts_missing(self):
        db = _FakeDB(
            {
                ap_mod.Document: [_mk_doc()],
                ap_mod.Entity: [_mk_vendor()],
                ap_mod.Account: [],
            }
        )
        result, _, _, ledger, dee = asyncio.run(self._run(db))
        assert result["status"] == "partial_success"
        assert result["bill_id"] == "bill-1"
        assert "ledger entry failed" in result["message"]
        assert db.commits == 0
        dee.create_bill_entry.assert_not_called()
        ledger.record_transaction.assert_not_called()

    def test_dates_and_custom_expense_code_are_used(self):
        db = _FakeDB(
            {
                ap_mod.Document: [_mk_doc()],
                ap_mod.Entity: [_mk_vendor()],
                ap_mod.Account: lambda i: [_mk_account("2000", acc_type=AccountType.LIABILITY)]
                if i == 0
                else [_mk_account("5200")],
            }
        )
        parsed = {
            "vendor_name": "Acme Corp",
            "amount": "150.5",
            "invoice_number": "INV-9",
            "issue_date": "2026-01-01",
            "due_date": "2026-02-01",
        }
        with patch.object(APService, "_parse_invoice_text", new=AsyncMock(return_value=parsed)):
            result, _, _, _, _ = asyncio.run(self._run(db))
        bill = _FakeBill._instances[0]
        assert bill.issue_date == datetime(2026, 1, 1)
        assert bill.due_date == datetime(2026, 2, 1)
        assert bill.amount == 150.5
        assert bill.bill_number == "INV-9"
        assert "Acme Corp" in bill.description
        assert result["status"] == "success"
        assert result["vendor"] == "Acme Corp"
        assert result["confidence"] == 1.0
        assert self._dee.create_bill_entry.call_args.kwargs["expense_account_id"] == "acc-5200"

    def test_missing_dates_fall_back_to_now(self):
        db = _FakeDB(
            {
                ap_mod.Document: [_mk_doc()],
                ap_mod.Entity: [_mk_vendor()],
                ap_mod.Account: lambda i: [_mk_account("2000", acc_type=AccountType.LIABILITY)]
                if i == 0
                else [_mk_account("5100")],
            }
        )
        parsed = {"vendor_name": "Acme Corp", "amount": 10, "invoice_number": "INV-9"}
        with patch.object(APService, "_parse_invoice_text", new=AsyncMock(return_value=parsed)):
            result, _, _, _, _ = asyncio.run(self._run(db))
        bill = _FakeBill._instances[0]
        assert bill.issue_date.timestamp() == pytest.approx(datetime.now().timestamp(), abs=5)
        assert bill.due_date.timestamp() == pytest.approx(datetime.now().timestamp(), abs=5)
        assert result["confidence"] == 1.0

    def test_new_vendor_created_when_no_match(self):
        db = _FakeDB(
            {
                ap_mod.Document: [_mk_doc()],
                ap_mod.Entity: [],
                ap_mod.Account: lambda i: [_mk_account("2000", acc_type=AccountType.LIABILITY)]
                if i == 0
                else [_mk_account("5100")],
            }
        )
        with patch.object(ap_mod, "Entity", _FakeEntity):
            result, _, _, _, _ = asyncio.run(self._run(db))
        assert result["status"] == "success"
        created = [e for e in db.added if isinstance(e, _FakeEntity)]
        assert len(created) == 1
        assert created[0].name == "CloudServices Inc"
        assert created[0].type == EntityType.VENDOR


class TestAPServiceResolveVendor:
    def test_returns_existing_vendor(self):
        db = _FakeDB({ap_mod.Entity: [_mk_vendor()]})
        service = APService(db)
        vendor = service._resolve_vendor("CloudServices Inc", "ws1")
        assert vendor.id == "vendor-1"
        assert db.added == []

    def test_returns_existing_both_type(self):
        both = SimpleNamespace(id="vendor-2", name="Both Co", type=EntityType.BOTH)
        db = _FakeDB({ap_mod.Entity: [both]})
        service = APService(db)
        assert service._resolve_vendor("Both Co", "ws1") is both

    def test_creates_new_vendor(self):
        db = _FakeDB({ap_mod.Entity: []})
        with patch.object(ap_mod, "Entity", _FakeEntity):
            service = APService(db)
            vendor = service._resolve_vendor("New Vendor", "ws1")
        assert vendor.id == "vendor-new"
        assert vendor.workspace_id == "ws1"
        assert vendor.name == "New Vendor"
        assert vendor.type == EntityType.VENDOR
        assert db.added[0] is vendor


class TestAPServiceParseInvoiceText:
    def test_long_text_with_invoice_marker_full_confidence(self):
        service = APService(_FakeDB())
        text = "Invoice INV-20260101 from CloudServices Inc for monthly subscription of 299.99 due soon"
        result = asyncio.run(service._parse_invoice_text(text))
        assert result["confidence"] == 0.95
        assert result["amount"] == 299.99
        assert result["vendor_name"] == "CloudServices Inc"
        assert result["invoice_number"].startswith("INV-")
        assert result["currency"] == "USD"

    def test_short_text_with_marker_lower_confidence(self):
        service = APService(_FakeDB())
        result = asyncio.run(service._parse_invoice_text("INV paid"))
        assert result["confidence"] == 0.6

    def test_long_text_without_marker_penalized(self):
        service = APService(_FakeDB())
        result = asyncio.run(service._parse_invoice_text("A" * 60))
        assert result["confidence"] == 0.75

    def test_short_text_without_marker_double_penalized(self):
        service = APService(_FakeDB())
        result = asyncio.run(service._parse_invoice_text("short"))
        assert result["confidence"] == pytest.approx(0.4)


# ===========================================================================
# AICategorizer — propose_categorization
# ===========================================================================
def _mk_transaction(**overrides):
    tx = SimpleNamespace(
        id="tx-1",
        description="Starbucks Coffee",
        transaction_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata_json={"source": "card"},
        workspace_id="ws1",
        journal_entries=[
            SimpleNamespace(type="debit", amount=12.5),
            SimpleNamespace(type="credit", amount=12.5),
        ],
    )
    for k, v in overrides.items():
        setattr(tx, k, v)
    return tx


def _mk_proposal(**overrides):
    p = SimpleNamespace(
        id="prop-1",
        transaction_id="tx-1",
        suggested_account_id="acc-5100",
        confidence=0.85,
        reasoning="looks like software",
        is_accepted=None,
        reviewed_by=None,
        reviewed_at=None,
        transaction=SimpleNamespace(
            description="Amazon purchase", workspace_id="ws1", id="tx-1"
        ),
    )
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _mk_rule(pattern="Starbucks", target="acc-5100", weight=1.0):
    return SimpleNamespace(
        workspace_id="ws1",
        is_active=True,
        merchant_pattern=pattern,
        target_account_id=target,
        confidence_weight=weight,
    )


class TestAICategorizerPropose:
    @pytest.fixture(autouse=True)
    def _reset_ai(self):
        _ai_mod.ai_enhanced_service.process_ai_request = AsyncMock()
        yield

    def test_rule_match_creates_high_confidence_proposal(self):
        db = _FakeDB({cat_mod.CategorizationRule: [_mk_rule()]})
        categorizer = AICategorizer(db)
        proposal = asyncio.run(categorizer.propose_categorization(_mk_transaction(), "ws1"))
        assert proposal is not None
        assert proposal.suggested_account_id == "acc-5100"
        assert proposal.confidence == 0.95
        assert "learned rule" in proposal.reasoning
        assert db.commits == 1
        assert db.added[0] is proposal

    def test_ai_confidence_zero_returns_none(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.0, output_data={}
        )
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        result = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert result is None

    def test_ai_negative_confidence_returns_none(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=-0.5, output_data={}
        )
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        result = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert result is None

    def test_ai_json_string_output_parsed(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.9,
            output_data=json.dumps(
                {"account_id": "acc-5100", "confidence": 0.88, "reasoning": "coffee shops"}
            ),
        )
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        proposal = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert proposal.suggested_account_id == "acc-5100"
        assert proposal.confidence == 0.88
        assert proposal.reasoning == "coffee shops"
        assert db.commits == 1

    def test_ai_invalid_json_returns_none(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.9, output_data="{not valid json"
        )
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        result = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert result is None

    def test_ai_output_without_account_id_returns_none(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.9, output_data={"confidence": 0.9}
        )
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        result = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert result is None

    def test_ai_dict_output_success(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.95,
            output_data={"account_id": "acc-5200", "confidence": 0.8, "reasoning": "travel"},
        )
        db = _FakeDB({cat_mod.Account: [_mk_account("5100"), _mk_account("5200")]})
        proposal = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert proposal.suggested_account_id == "acc-5200"
        assert proposal.confidence == 0.8
        assert proposal.reasoning == "travel"
        assert db.added[0] is proposal
        assert db.commits == 1
        ai_request = _ai_mod.ai_enhanced_service.process_ai_request.call_args.args[0]
        assert ai_request.platform == "accounting"
        assert "chart_of_accounts" in json.loads(ai_request.input_data["text"])

    def test_ai_exception_returns_none(self):
        _ai_mod.ai_enhanced_service.process_ai_request.side_effect = RuntimeError("boom")
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        result = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert result is None

    def test_empty_coa_still_reaches_ai(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.9,
            output_data={"account_id": "acc-5100", "confidence": 0.9, "reasoning": "x"},
        )
        db = _FakeDB({cat_mod.Account: []})
        proposal = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert proposal is not None

    def test_debit_amount_sum_in_prompt(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.9,
            output_data={"account_id": "acc-5100", "confidence": 0.9, "reasoning": "x"},
        )
        tx = _mk_transaction()
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        asyncio.run(AICategorizer(db).propose_categorization(tx, "ws1"))
        payload = json.loads(
            _ai_mod.ai_enhanced_service.process_ai_request.call_args.args[0].input_data["text"]
        )
        assert payload["transaction"]["amount"] == 12.5
        assert payload["transaction"]["date"] == "2026-01-01T00:00:00+00:00"
        assert payload["transaction"]["metadata"] == {"source": "card"}

    def test_ai_non_dict_non_str_output_returns_none(self):
        _ai_mod.ai_enhanced_service.process_ai_request.return_value = SimpleNamespace(
            confidence=0.9, output_data=[1, 2]
        )
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        result = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert result is None


# ===========================================================================
# AICategorizer — accept_proposal
# ===========================================================================
class TestAICategorizerAccept:
    def test_proposal_not_found_returns_false(self):
        db = _FakeDB({cat_mod.CategorizationProposal: []})
        assert AICategorizer(db).accept_proposal("prop-1", "user-1") is False
        assert db.commits == 0

    def test_accept_creates_new_rule_and_audit(self):
        db = _FakeDB(
            {cat_mod.CategorizationProposal: [_mk_proposal()], cat_mod.CategorizationRule: []}
        )
        result = AICategorizer(db).accept_proposal("prop-1", "user-1")
        assert result is True
        rule = [a for a in db.added if getattr(a, "merchant_pattern", None) == "Amazon"]
        assert len(rule) == 1
        assert rule[0].target_account_id == "acc-5100"
        assert rule[0].confidence_weight == 1.1
        audit = [a for a in db.added if getattr(a, "action", None) == "ACCEPT_CATEGORIZATION"]
        assert len(audit) == 1
        assert audit[0].action == "ACCEPT_CATEGORIZATION"
        assert audit[0].user_id == "user-1"
        assert audit[0].event_type == "FINANCIAL_APPROVAL"
        proposal = db._specs[cat_mod.CategorizationProposal][0]
        assert proposal.is_accepted is True
        assert proposal.reviewed_by == "user-1"
        assert proposal.reviewed_at is not None
        assert db.commits == 1

    def test_accept_reinforces_matching_rule(self):
        rule = _mk_rule(pattern="Amazon", target="acc-5100", weight=1.0)
        db = _FakeDB(
            {cat_mod.CategorizationProposal: [_mk_proposal()], cat_mod.CategorizationRule: [rule]}
        )
        assert AICategorizer(db).accept_proposal("prop-1", "user-1") is True
        assert rule.confidence_weight == 1.1
        assert all(not hasattr(a, "merchant_pattern") for a in db.added)

    def test_accept_degrades_conflicting_rule(self):
        rule = _mk_rule(pattern="Amazon", target="acc-9999", weight=1.0)
        db = _FakeDB(
            {cat_mod.CategorizationProposal: [_mk_proposal()], cat_mod.CategorizationRule: [rule]}
        )
        assert AICategorizer(db).accept_proposal("prop-1", "user-1") is True
        assert rule.confidence_weight == 0.8


# ===========================================================================
# AICategorizer — import degradation (regression for the import bug)
# ===========================================================================
class TestAICategorizerImportDegradation:
    def test_propose_degrades_when_ai_module_absent(self):
        """Regression: module must import (and degrade) without
        integrations.ai_enhanced_service instead of raising ImportError."""
        saved = sys.modules.get("integrations.ai_enhanced_service")
        sys.modules.pop("integrations.ai_enhanced_service", None)
        try:
            importlib.reload(cat_mod)
            assert cat_mod.ai_enhanced_service is None
            assert cat_mod.AIRequest is None
            assert cat_mod.AIModelType is None
            categorizer = cat_mod.AICategorizer(_FakeDB({cat_mod.CategorizationRule: []}))
            result = asyncio.run(
                categorizer.propose_categorization(_mk_transaction(), "ws1")
            )
            assert result is None
        finally:
            if saved is not None:
                sys.modules["integrations.ai_enhanced_service"] = saved
            importlib.reload(cat_mod)
            assert cat_mod.ai_enhanced_service is _ai_mod.ai_enhanced_service

    def test_propose_returns_none_when_ai_service_is_none(self):
        """Regression: with a None AI service the AI branch must return None
        (guard before constructing AIRequest), not raise TypeError."""
        db = _FakeDB({cat_mod.Account: [_mk_account("5100")]})
        with patch.object(cat_mod, "ai_enhanced_service", None):
            result = asyncio.run(AICategorizer(db).propose_categorization(_mk_transaction(), "ws1"))
        assert result is None


# ===========================================================================
# CreditRiskEngine
# ===========================================================================
def _mk_invoice(**overrides):
    inv = SimpleNamespace(
        status=InvoiceStatus.OPEN,
        updated_at=None,
        due_date=None,
        amount=0.0,
        customer_id="e1",
    )
    for k, v in overrides.items():
        setattr(inv, k, v)
    return inv


def _paid(days_late=0, amount=100.0, **kw):
    due = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return _mk_invoice(
        status=InvoiceStatus.PAID,
        due_date=due,
        updated_at=due + timedelta(days=days_late),
        amount=amount,
        **kw
    )


class TestCreditRiskAnalyze:
    def test_no_invoices_unknown(self):
        db = _FakeDB({cre_mod.Invoice: []})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 0.0
        assert level == "unknown"

    def test_all_paid_on_time_low(self):
        db = _FakeDB({cre_mod.Invoice: [_paid(0)]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 0.0
        assert level == "low"

    def test_all_paid_late_medium(self):
        db = _FakeDB({cre_mod.Invoice: [_paid(10)]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 50.0
        assert level == "medium"

    def test_partial_late_rate(self):
        db = _FakeDB({cre_mod.Invoice: [_paid(0), _paid(15)]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == pytest.approx(25.0)
        assert level == "medium"

    def test_open_overdue_amount_adds_score(self):
        overdue = _mk_invoice(
            status=InvoiceStatus.OPEN,
            due_date=datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(days=5),
            amount=500.0,
        )
        db = _FakeDB({cre_mod.Invoice: [_paid(0), overdue]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == pytest.approx(25.0)
        assert level == "medium"

    def test_overdue_factor_capped_at_50(self):
        overdue = _mk_invoice(
            status=InvoiceStatus.OPEN,
            due_date=datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(days=5),
            amount=20000.0,
        )
        db = _FakeDB({cre_mod.Invoice: [_paid(0), overdue]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 50.0
        assert level == "medium"

    def test_high_risk_level(self):
        overdue = _mk_invoice(
            status=InvoiceStatus.OPEN,
            due_date=datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(days=5),
            amount=500.0,
        )
        db = _FakeDB({cre_mod.Invoice: [_paid(12), overdue]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 75.0
        assert level == "high"

    def test_open_invoice_without_due_date_not_overdue(self):
        db = _FakeDB({cre_mod.Invoice: [_paid(0), _mk_invoice(status=InvoiceStatus.OPEN, amount=900.0)]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 0.0
        assert level == "low"

    def test_paid_without_updated_at_not_late(self):
        paid = _paid(0)
        paid.updated_at = None
        db = _FakeDB({cre_mod.Invoice: [paid]})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 0.0

    def test_void_and_draft_invoices_not_open_or_paid(self):
        invoices = [
            _mk_invoice(status=InvoiceStatus.VOID, amount=50.0),
            _mk_invoice(status=InvoiceStatus.DRAFT, amount=50.0),
        ]
        db = _FakeDB({cre_mod.Invoice: invoices})
        score, level = CreditRiskEngine(db).analyze_customer_risk("e1")
        assert score == 0.0
        assert level == "low"


class TestCreditRiskSync:
    def test_sync_without_customers_commits(self):
        db = _FakeDB({cre_mod.Invoice: [], cre_mod.EcommerceCustomer: []})
        CreditRiskEngine(db).sync_risk_to_ecommerce("e1")
        assert db.commits == 1

    def test_sync_updates_customer_risk(self):
        cust1 = SimpleNamespace(email="a@x.com", risk_score=None, risk_level=None)
        cust2 = SimpleNamespace(email="b@x.com", risk_score=None, risk_level=None)
        overdue = _mk_invoice(
            status=InvoiceStatus.OPEN,
            due_date=datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(days=5),
            amount=500.0,
        )
        db = _FakeDB(
            {
                cre_mod.Invoice: [_paid(12), overdue],
                cre_mod.EcommerceCustomer: [cust1, cust2],
            }
        )
        CreditRiskEngine(db).sync_risk_to_ecommerce("e1")
        assert cust1.risk_score == 75.0
        assert cust1.risk_level == "high"
        assert cust2.risk_score == 75.0
        assert cust2.risk_level == "high"
        assert db.commits == 1


# ===========================================================================
# RevenueRecognitionService
# ===========================================================================
def _mk_milestone(**overrides):
    m = SimpleNamespace(
        id="m-1",
        workspace_id="ws1",
        amount=1000.0,
        name="Milestone One",
        project=None,
    )
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def _mk_project(**overrides):
    p = SimpleNamespace(id="p-1", contract=None)
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _mk_contract(**overrides):
    c = SimpleNamespace(
        id="c-1", product_service=None, product_service_id="ps-1", name="Contract One"
    )
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


class TestRevenueRecognition:
    def _run(self, db, milestone_id="m-1"):
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = False
        ledger = MagicMock()
        ledger.record_transaction = MagicMock(return_value=SimpleNamespace(id="tx-1"))
        with patch.object(rr_mod, "get_db_session", return_value=cm), patch.object(
            rr_mod, "EventSourcedLedger", return_value=ledger
        ):
            result = asyncio.run(rr_mod.revenue_recognition_service.record_revenue_recognition(milestone_id))
        return result, ledger

    def test_milestone_not_found(self):
        db = _FakeDB({})
        result, _ = self._run(db)
        assert result == {"status": "error", "message": "Milestone m-1 not found"}

    def test_contract_missing(self):
        milestone = _mk_milestone(project=_mk_project(contract=None))
        db = _FakeDB({})
        db._specs[rr_mod.Milestone] = [milestone]
        result, _ = self._run(db)
        assert result["status"] == "error"
        assert "Contract or project not found" in result["message"]

    def test_project_missing(self):
        db = _FakeDB({rr_mod.Milestone: [_mk_milestone(project=None)]})
        result, _ = self._run(db)
        assert result["status"] == "error"

    def test_zero_amount_no_entry(self):
        db = _FakeDB(
            {
                rr_mod.Milestone: [
                    _mk_milestone(amount=0.0, project=_mk_project(contract=_mk_contract()))
                ]
            }
        )
        result, ledger = self._run(db)
        assert result == {"status": "success", "message": "Zero amount milestone, no entry needed"}
        ledger.record_transaction.assert_not_called()

    def test_negative_amount_no_entry(self):
        db = _FakeDB(
            {
                rr_mod.Milestone: [
                    _mk_milestone(amount=-5, project=_mk_project(contract=_mk_contract()))
                ]
            }
        )
        result, _ = self._run(db)
        assert result["status"] == "success"

    def test_accounts_missing(self):
        milestone = _mk_milestone(project=_mk_project(contract=_mk_contract()))
        db = _FakeDB({rr_mod.Milestone: [milestone], rr_mod.Account: []})
        result, ledger = self._run(db)
        assert result["status"] == "error"
        assert "4000 or 2100" in result["message"]
        ledger.record_transaction.assert_not_called()

    def test_success_with_product(self):
        product = SimpleNamespace(name="Cloud Consulting")
        contract = _mk_contract(product_service=product)
        milestone = _mk_milestone(project=_mk_project(contract=contract))
        db = _FakeDB(
            {
                rr_mod.Milestone: [milestone],
                rr_mod.Account: lambda i: [
                    _mk_account("4000", acc_type=AccountType.REVENUE)
                ]
                if i == 0
                else [_mk_account("2100", acc_type=AccountType.LIABILITY)],
            }
        )
        result, ledger = self._run(db)
        assert result == {
            "status": "success",
            "transaction_id": "tx-1",
            "amount": 1000.0,
            "product": "Cloud Consulting",
        }
        call = ledger.record_transaction.call_args
        assert call.kwargs["source"] == "auto_recognition"
        assert call.kwargs["metadata"]["milestone_id"] == "m-1"
        assert call.kwargs["metadata"]["project_id"] == "p-1"
        assert call.kwargs["metadata"]["contract_id"] == "c-1"
        assert call.kwargs["metadata"]["product_service_id"] == "ps-1"
        assert call.kwargs["metadata"]["type"] == "revenue_recognition"
        assert call.kwargs["entries"][0]["type"] == EntryType.DEBIT
        assert call.kwargs["entries"][1]["type"] == EntryType.CREDIT
        assert "Milestone One (Cloud Consulting)" in call.kwargs["description"]

    def test_success_without_product_general_service(self):
        milestone = _mk_milestone(project=_mk_project(contract=_mk_contract(product_service=None)))
        db = _FakeDB(
            {
                rr_mod.Milestone: [milestone],
                rr_mod.Account: lambda i: [
                    _mk_account("4000", acc_type=AccountType.REVENUE)
                ]
                if i == 0
                else [_mk_account("2100", acc_type=AccountType.LIABILITY)],
            }
        )
        result, ledger = self._run(db)
        assert result["status"] == "success"
        assert result["product"] == "General Service"
        assert "General Service" in ledger.record_transaction.call_args.kwargs["description"]

    def test_success_without_deferred_account_errors(self):
        milestone = _mk_milestone(project=_mk_project(contract=_mk_contract()))
        db = _FakeDB(
            {
                rr_mod.Milestone: [milestone],
                rr_mod.Account: lambda i: [
                    _mk_account("4000", acc_type=AccountType.REVENUE)
                ]
                if i == 0
                else [],
            }
        )
        result, _ = self._run(db)
        assert result["status"] == "error"


# ===========================================================================
# TaxService — _parse_address
# ===========================================================================
class TestTaxParseAddress:
    def setup_method(self):
        self.service = TaxService(_FakeDB())

    def test_empty_address(self):
        assert self.service._parse_address("") == (None, None)

    def test_abbr_with_zip(self):
        assert self.service._parse_address("123 Main St, New York, NY 10001") == (
            "New York",
            "United States",
        )

    def test_abbr_with_zip_plus_4(self):
        assert self.service._parse_address("123 Main St, Seattle, WA 98101-1234") == (
            "Washington",
            "United States",
        )

    def test_unknown_abbr_falls_back_to_region(self):
        state, country = self.service._parse_address("123 Main St, ZZ 90210")
        assert state == "ZZ 90210"
        assert country is None

    def test_full_state_name(self):
        assert self.service._parse_address("100 Congress Ave, Austin, Texas 78701") == (
            "Texas",
            "United States",
        )

    def test_canada_province(self):
        assert self.service._parse_address("100 Yonge St, Toronto, Ontario") == (None, "Canada")

    def test_canada_direct(self):
        assert self.service._parse_address("100 Rue Peel, Montreal, Quebec") == (None, "Canada")

    def test_united_kingdom(self):
        assert self.service._parse_address("10 Downing St, London, UK") == (None, "United Kingdom")

    def test_united_kingdom_full_name(self):
        assert self.service._parse_address("Oxford St, London, United Kingdom") == (
            None,
            "United Kingdom",
        )

    def test_australia(self):
        assert self.service._parse_address("1 George St, Sydney, Australia") == (None, "Australia")

    def test_fallback_two_letter_region(self):
        assert self.service._parse_address("Paris, CA") == ("California", "United States")

    def test_fallback_region_name(self):
        assert self.service._parse_address("Suite 12, Springfield") == ("Springfield", None)

    def test_no_parts(self):
        assert self.service._parse_address(",") == (None, None)


# ===========================================================================
# TaxService — normalize + thresholds
# ===========================================================================
class TestTaxNormalizeAndThresholds:
    def setup_method(self):
        self.service = TaxService(_FakeDB())

    def test_normalize_empty(self):
        assert self.service._normalize_region_name("") == "Unknown"

    def test_normalize_abbreviation(self):
        assert self.service._normalize_region_name("ca") == "California"

    def test_normalize_title_case(self):
        assert self.service._normalize_region_name("new york") == "New York"

    def test_threshold_california(self):
        assert self.service._get_nexus_threshold("California") == 500000

    def test_threshold_washington(self):
        assert self.service._get_nexus_threshold("Washington") == 25000

    def test_threshold_default_for_unknown(self):
        assert self.service._get_nexus_threshold("Wyoming") == 100000


# ===========================================================================
# TaxService — detect_nexus
# ===========================================================================
class _FakeTaxNexus:
    _instances = []

    workspace_id = None
    region = None
    tax_type = "Sales Tax"
    is_active = True

    def __init__(self, **kwargs):
        self.id = "nx-1"
        self.__dict__.update(kwargs)
        _FakeTaxNexus._instances.append(self)


def _mk_tax_invoice(amount, address, cid="c-1"):
    return SimpleNamespace(
        amount=amount,
        customer=SimpleNamespace(address=address),
        customer_id=cid,
        status=InvoiceStatus.PAID,
    )


class TestTaxDetectNexus:
    def setup_method(self):
        _FakeTaxNexus._instances = []

    def test_no_invoices(self):
        db = _FakeDB({tax_mod.Invoice: []})
        assert asyncio.run(TaxService(db).detect_nexus("ws1")) == []

    def test_below_threshold_no_nexus(self):
        db = _FakeDB(
            {tax_mod.Invoice: [_mk_tax_invoice(100.0, "123 Main St, San Francisco, CA 94103")]}
        )
        assert asyncio.run(TaxService(db).detect_nexus("ws1")) == []
        assert db.commits == 0

    def test_above_threshold_creates_nexus(self):
        db = _FakeDB(
            {tax_mod.Invoice: [_mk_tax_invoice(600000.0, "123 Main St, San Francisco, CA 94103")]}
        )
        with patch.object(tax_mod, "TaxNexus", _FakeTaxNexus):
            result = asyncio.run(TaxService(db).detect_nexus("ws1"))
        assert len(result) == 1
        entry = result[0]
        assert entry["region"] == "California"
        assert entry["nexus_type"] == NexusType.ECONOMIC.value
        assert entry["sales_amount"] == 600000.0
        assert entry["threshold"] == 500000
        assert entry["customer_count"] == 1
        assert entry["nexus_id"] == "nx-1"
        nexus = _FakeTaxNexus._instances[0]
        assert nexus.region == "California"
        assert nexus.tax_type == "Sales Tax"
        assert nexus.is_active is True
        assert db.commits == 1
        assert db.refreshed == [nexus]

    def test_existing_nexus_skipped(self):
        existing = SimpleNamespace(id="nx-0", region="California")
        db = _FakeDB(
            {
                tax_mod.Invoice: [_mk_tax_invoice(600000.0, "123 Main St, San Francisco, CA 94103")],
                tax_mod.TaxNexus: [existing],
            }
        )
        result = asyncio.run(TaxService(db).detect_nexus("ws1"))
        assert result == []
        assert db.commits == 0

    def test_unknown_region_skipped(self):
        db = _FakeDB({tax_mod.Invoice: [_mk_tax_invoice(600000.0, None)]})
        assert asyncio.run(TaxService(db).detect_nexus("ws1")) == []

    def test_country_region_uses_default_threshold(self):
        db = _FakeDB(
            {tax_mod.Invoice: [_mk_tax_invoice(200000.0, "100 Yonge St, Toronto, Ontario")]}
        )
        with patch.object(tax_mod, "TaxNexus", _FakeTaxNexus):
            result = asyncio.run(TaxService(db).detect_nexus("ws1"))
        assert len(result) == 1
        assert result[0]["region"] == "Canada"
        assert result[0]["threshold"] == 100000

    def test_multiple_customers_counted(self):
        db = _FakeDB(
            {
                tax_mod.Invoice: [
                    _mk_tax_invoice(300000.0, "Austin, Texas 78701", cid="c-1"),
                    _mk_tax_invoice(300000.0, "Dallas, Texas 75201", cid="c-2"),
                    _mk_tax_invoice(300000.0, "Houston, Texas 77002", cid=None),
                ]
            }
        )
        with patch.object(tax_mod, "TaxNexus", _FakeTaxNexus):
            result = asyncio.run(TaxService(db).detect_nexus("ws1"))
        assert len(result) == 1
        assert result[0]["region"] == "Texas"
        assert result[0]["customer_count"] == 2
        assert result[0]["sales_amount"] == 900000.0


# ===========================================================================
# TaxService — estimate_tax_liability
# ===========================================================================
class TestTaxEstimateLiability:
    def test_no_nexus_zero_liability(self):
        db = _FakeDB({tax_mod.TaxNexus: []})
        result = TaxService(db).estimate_tax_liability("ws1")
        assert result == {"total_estimated_liability": 0.0, "currency": "USD", "breakdown": {}}

    def test_matches_abbreviated_region(self):
        nexus = SimpleNamespace(region="California", is_active=True)
        db = _FakeDB(
            {
                tax_mod.TaxNexus: [nexus],
                tax_mod.Invoice: [_mk_tax_invoice(100.0, "1 Market St, San Francisco, CA 94103")],
            }
        )
        result = TaxService(db).estimate_tax_liability("ws1")
        assert result["total_estimated_liability"] == 7.0
        assert result["breakdown"] == {"California": 7.0}

    def test_matches_full_region_name(self):
        nexus = SimpleNamespace(region="California", is_active=True)
        db = _FakeDB(
            {
                tax_mod.TaxNexus: [nexus],
                tax_mod.Invoice: [
                    _mk_tax_invoice(10.0, "400 Mission St, San Francisco, California"),
                    _mk_tax_invoice(20.0, "500 Market St, Los Angeles, California"),
                ],
            }
        )
        result = TaxService(db).estimate_tax_liability("ws1")
        assert result["total_estimated_liability"] == 2.1
        assert result["breakdown"] == {"California": 2.1}

    def test_no_region_match(self):
        nexus = SimpleNamespace(region="California", is_active=True)
        db = _FakeDB(
            {
                tax_mod.TaxNexus: [nexus],
                tax_mod.Invoice: [_mk_tax_invoice(100.0, "Miami, FL 33101")],
            }
        )
        result = TaxService(db).estimate_tax_liability("ws1")
        assert result["total_estimated_liability"] == 0.0
        assert result["breakdown"] == {}

    def test_empty_address_not_matched(self):
        nexus = SimpleNamespace(region="California", is_active=True)
        db = _FakeDB(
            {
                tax_mod.TaxNexus: [nexus],
                tax_mod.Invoice: [_mk_tax_invoice(100.0, "")],
            }
        )
        result = TaxService(db).estimate_tax_liability("ws1")
        assert result["total_estimated_liability"] == 0.0

    def test_rounding_applied(self):
        nexus = SimpleNamespace(region="Texas", is_active=True)
        db = _FakeDB(
            {
                tax_mod.TaxNexus: [nexus],
                tax_mod.Invoice: [_mk_tax_invoice(0.1, "Austin, Texas")],
            }
        )
        result = TaxService(db).estimate_tax_liability("ws1")
        assert result["total_estimated_liability"] == 0.01


# ===========================================================================
# IntercompanyManager
# ===========================================================================
def _mk_ictx(tx_id, cp=None, date=None, desc=None, entries=None):
    return SimpleNamespace(
        id=tx_id,
        counterparty_workspace_id=cp,
        transaction_date=date or datetime(2026, 1, 1, tzinfo=timezone.utc),
        description=desc or f"interco {tx_id}",
        journal_entries=entries or [],
    )


def _je(entry_type, amount):
    return SimpleNamespace(type=entry_type, amount=amount)


class TestIntercompany:
    def test_get_intercompany_transactions(self):
        txs = [_mk_ictx("t1", cp="ws2")]
        db = _FakeDB({me_mod.Transaction: txs})
        assert IntercompanyManager(db).get_intercompany_transactions("ws1") == txs

    def test_find_unmatched_skips_without_counterparty(self):
        db = _FakeDB({me_mod.Transaction: [_mk_ictx("t1", cp=None)]})
        assert IntercompanyManager(db).find_unmatched_intercompany("ws1") == []

    def test_find_unmatched_skips_when_matching_exists(self):
        db = _FakeDB(
            {
                me_mod.Transaction: lambda i: [_mk_ictx("t1", cp="ws2")]
                if i == 0
                else [_mk_ictx("t2", cp="ws1")],
            }
        )
        assert IntercompanyManager(db).find_unmatched_intercompany("ws1") == []

    def test_find_unmatched_reports_missing(self):
        date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db = _FakeDB(
            {me_mod.Transaction: lambda i: [_mk_ictx("t1", cp="ws2", date=date)] if i == 0 else []}
        )
        unmatched = IntercompanyManager(db).find_unmatched_intercompany("ws1")
        assert len(unmatched) == 1
        assert unmatched[0]["transaction_id"] == "t1"
        assert unmatched[0]["target_workspace"] == "ws2"
        assert unmatched[0]["date"] == date
        assert unmatched[0]["description"] == "interco t1"

    def test_elimination_report_empty(self):
        db = _FakeDB({me_mod.Transaction: []})
        report = IntercompanyManager(db).generate_elimination_report("ws1")
        assert report == {
            "total_elimination_volume": 0.0,
            "breakdown_by_counterparty": {},
            "transaction_count": 0,
        }

    def test_elimination_report_sums_debits_by_counterparty(self):
        txs = [
            _mk_ictx("t1", cp="ws2", entries=[_je(EntryType.DEBIT, 100.0), _je(EntryType.CREDIT, 100.0)]),
            _mk_ictx("t2", cp=None, entries=[_je(EntryType.DEBIT, 250.0), _je(EntryType.CREDIT, 250.0)]),
            _mk_ictx("t3", cp="ws2", entries=[_je(EntryType.CREDIT, 999.0)]),
        ]
        db = _FakeDB({me_mod.Transaction: txs})
        report = IntercompanyManager(db).generate_elimination_report("ws1")
        assert report["total_elimination_volume"] == 350.0
        assert report["breakdown_by_counterparty"] == {"ws2": 100.0, "Unknown": 250.0}
        assert report["transaction_count"] == 3
