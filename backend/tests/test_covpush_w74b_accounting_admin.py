"""Coverage wave W74B — accounting admin/service modules (standalone >=95% each).

Targets:
1. accounting/export_service.py       (45% before — only _sanitize_csv_cell partially)
2. accounting/ingestion.py            (0% before — never imported by any suite)
3. accounting/seeds.py                (100% before — regression tests only)
4. accounting/sync_manager.py         (0% before — never imported by any suite)
5. accounting/workflow_service.py     (0% before — module was UNIMPORTABLE)
6. accounting/workflows.py            (0% before — never imported by any suite)
7. api/admin/budget_routes.py         (90% before — missing 66-67, 84, 102-103, 108, 122-123)
8. api/admin/jit_verification_routes.py (99% before — missing 284, 289)

Pattern: scripted fake sessions for services (zero DB, zero network, zero LLM
spend) and FastAPI TestClient + dependency_overrides for routes. Patches use
real module names (no `backend.` prefix).

Bug found + fixed in the assigned modules (regression tests below):
1. accounting/workflow_service.py — `from core.cross_system_reasoning import
   get_reasoning_engine` at module scope raised ImportError (no such name in
   that module; the engine class is `CrossSystemReasoningEngine`), making the
   whole module unimportable. Fixed the import + instantiation, and guarded
   the `check_financial_integrity` call (not part of the engine's API) so
   handle_transaction_event degrades to no alerts instead of AttributeError.
   Regression: TestFinancialWorkflowServiceImports.test_module_imports and
   test_handle_event_degrades_when_no_integrity_check.
"""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from accounting.export_service import AccountExporter, _sanitize_csv_cell
from accounting.ingestion import IngestionError, TransactionIngestor
from accounting.models import (
    Account,
    AccountType,
    EntryType,
    InvoiceStatus,
    Invoice,
    JournalEntry,
    Transaction,
)
from accounting.seeds import seed_default_accounts
from accounting.sync_manager import AccountingSyncManager
from accounting.workflow_service import FinancialWorkflowService
from accounting.workflows import CollectionAgent
from api.admin.budget_routes import _read_billing_setting, _resolve_budget_state
from core.auth import get_current_user
from core.models import Tenant, TenantSetting, UserRole


# ============================================================================
# Scripted fake session (per-model query results, nth-query keyed)
# ============================================================================
class _FakeQuery:
    def __init__(self, db, model):
        self._db = db
        self._model = model

    def filter(self, *args, **kwargs):
        self._db.last_filter_kwargs = kwargs
        return self

    def join(self, *args, **kwargs):
        return self

    def options(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._db._result(self._model, single=True)

    def all(self):
        return self._db._result(self._model, single=False)

    def scalar(self):
        return self._db._scalar(self._model)


class _FakeDB:
    def __init__(self, results=None):
        self._specs = results or {}
        self._counts = {}
        self._scalar_specs = []
        self._scalar_idx = 0
        self.added = []
        self.flushes = 0
        self.commits = 0
        self.last_filter_kwargs = {}

    def query(self, model):
        key = model if isinstance(model, type) else _FakeDB
        self._counts[key] = self._counts.get(key, 0) + 1
        return _FakeQuery(self, key)

    def _result(self, model, single):
        idx = self._counts.get(model, 0) - 1
        spec = self._specs.get(model)
        rows = spec(idx) if callable(spec) else (spec if spec is not None else [])
        rows = rows if isinstance(rows, list) else [rows]
        if single:
            return rows[0] if rows else None
        return list(rows)

    def _scalar(self, model):
        if self._scalar_idx < len(self._scalar_specs):
            value = self._scalar_specs[self._scalar_idx]
        else:
            value = None
        self._scalar_idx += 1
        return value

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1


def _mk_account(code="1000", name=None, acc_type=AccountType.ASSET, mapping=None, ws="ws1"):
    return SimpleNamespace(
        id=f"acc-{code}",
        workspace_id=ws,
        name=name or f"Account {code}",
        code=code,
        type=acc_type,
        standards_mapping=mapping,
    )


def _mk_tx(tx_id="tx-1", ws="ws1", description="desc", external_id=None, amount=100.0, metadata_json=None):
    return SimpleNamespace(
        id=tx_id,
        workspace_id=ws,
        description=description,
        amount=amount,
        external_id=external_id,
        transaction_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata_json=metadata_json if metadata_json is not None else {},
    )


def _mk_entry(entry_type, amount, account=None, tx=None, description=None, currency="USD"):
    return SimpleNamespace(
        type=entry_type,
        amount=amount,
        account=account,
        transaction=tx,
        description=description,
        currency=currency,
    )


# ============================================================================
# 1. accounting/export_service.py
# ============================================================================
class TestSanitizeCsvCell:
    def test_none_passthrough(self):
        assert _sanitize_csv_cell(None) is None

    def test_number_passthrough(self):
        assert _sanitize_csv_cell(42.5) == 42.5

    def test_plain_string_unchanged(self):
        assert _sanitize_csv_cell("plain text") == "plain text"

    def test_equals_prefix_quoted(self):
        assert _sanitize_csv_cell('=SUM(A1:A2)') == "'=SUM(A1:A2)"

    def test_plus_prefix_quoted(self):
        assert _sanitize_csv_cell('+cmd|calc') == "'+cmd|calc"

    def test_minus_prefix_quoted(self):
        assert _sanitize_csv_cell('-1+1') == "'-1+1"

    def test_at_prefix_quoted(self):
        assert _sanitize_csv_cell('@echo') == "'@echo"

    def test_tab_prefix_with_formula_quoted(self):
        assert _sanitize_csv_cell('\t=1+1') == "'\t=1+1"

    def test_cr_prefix_with_formula_quoted(self):
        assert _sanitize_csv_cell('\r=1+1') == "'\r=1+1"

    def test_bare_tab_unchanged(self):
        assert _sanitize_csv_cell('\tformula') == '\tformula'

    def test_leading_whitespace_prefix_quoted(self):
        assert _sanitize_csv_cell('  =1+1') == "'  =1+1"

    def test_empty_string_unchanged(self):
        assert _sanitize_csv_cell("") == ""


class TestAccountExporterGeneralLedgerCsv:
    def test_empty_ledger_returns_header_only(self):
        db = _FakeDB({})
        exporter = AccountExporter(db)
        csv_text = exporter.export_general_ledger_csv("ws1")
        assert csv_text.splitlines()[0].startswith("Date,Transaction ID,Account Code")

    def test_debit_and_credit_rows_with_mapping(self):
        acc = _mk_account("1000", mapping={"gaap": "1001", "ifrs": "ASSET_CASH"})
        tx = _mk_tx(tx_id="ext-1")
        entries = [
            _mk_entry(EntryType.DEBIT, 250.0, account=acc, tx=tx,
                      description="Invoice payment", currency="USD"),
            _mk_entry(EntryType.CREDIT, 250.0, account=acc, tx=tx,
                      description="Sales", currency="EUR"),
        ]
        db = _FakeDB({})
        exporter = AccountExporter(db)
        with patch.object(db, "_result", return_value=entries):
            csv_text = exporter.export_general_ledger_csv("ws1")
        lines = csv_text.strip().splitlines()
        assert len(lines) == 3
        assert "2026-01-01" in lines[1]
        assert "ext-1" in lines[1]
        assert "250.0" in lines[1] and "0" in lines[1]
        assert "ASSET_CASH" in lines[1]
        assert "Invoice payment" in lines[1]
        assert "EUR" in lines[2]
        assert "Sales" in lines[2]

    def test_mapping_none_and_description_fallback(self):
        acc = _mk_account("2000", mapping=None)
        tx = _mk_tx(description="tx fallback desc")
        entry = _mk_entry(EntryType.DEBIT, 10.0, account=acc, tx=tx,
                          description=None, currency="USD")
        db = _FakeDB({})
        exporter = AccountExporter(db)
        with patch.object(db, "_result", return_value=[entry]):
            csv_text = exporter.export_general_ledger_csv("ws1")
        assert "tx fallback desc" in csv_text

    def test_formula_cells_sanitized_in_csv(self):
        acc = _mk_account("1000", mapping=None)
        tx = _mk_tx(tx_id='=HYPERLINK("http://evil","x")')
        entry = _mk_entry(EntryType.DEBIT, 1.0, account=acc, tx=tx,
                          description="=1+1", currency="USD")
        db = _FakeDB({})
        exporter = AccountExporter(db)
        with patch.object(db, "_result", return_value=[entry]):
            csv_text = exporter.export_general_ledger_csv("ws1")
        assert "'=1+1" in csv_text
        assert "'=HYPERLINK" in csv_text


class TestAccountExporterTrialBalance:
    def test_empty_accounts(self):
        db = _FakeDB({})
        report = AccountExporter(db).export_trial_balance_json("ws1")
        assert report["workspace_id"] == "ws1"
        assert report["accounts"] == []
        assert report["standard"].startswith("Multi-Standard")

    def test_balances_with_sums(self):
        acc = _mk_account("1000", mapping={"gaap": "x"})
        db = _FakeDB({})
        db._specs[Account] = [acc]
        db._scalar_specs = [500.0, 200.0]
        report = AccountExporter(db).export_trial_balance_json("ws1")
        account = report["accounts"][0]
        assert account["debits"] == 500.0
        assert account["credits"] == 200.0
        assert account["net_balance"] == 300.0
        assert account["type"] == "asset"
        assert account["mapping"] == {"gaap": "x"}

    def test_null_sums_fall_back_to_zero(self):
        acc = _mk_account("5000", acc_type=AccountType.EXPENSE)
        db = _FakeDB({})
        db._specs[Account] = [acc]
        db._scalar_specs = [None, None]
        account = AccountExporter(db).export_trial_balance_json("ws1")["accounts"][0]
        assert account["debits"] == 0.0
        assert account["credits"] == 0.0
        assert account["net_balance"] == 0.0
        assert account["type"] == "expense"


# ============================================================================
# 2. accounting/ingestion.py
# ============================================================================
class TestTransactionIngestor:
    def _make(self, db):
        ledger = MagicMock()
        ledger.record_transaction = MagicMock(return_value=SimpleNamespace(id="tx-new"))
        categorizer = MagicMock()
        categorizer.propose_categorization = AsyncMock(return_value=None)
        patchers = [
            patch.object(__import__("accounting.ingestion", fromlist=["x"]), "EventSourcedLedger",
                         return_value=ledger),
            patch.object(__import__("accounting.ingestion", fromlist=["x"]), "AICategorizer",
                         return_value=categorizer),
        ]
        for p in patchers:
            p.start()
        service = TransactionIngestor(db)
        for p in patchers:
            p.stop()
        return service, ledger, categorizer

    def test_existing_payment_returns_existing(self):
        existing = _mk_tx(external_id="pi_1")
        db = _FakeDB({})
        db._specs[Transaction] = [existing]
        service, ledger, categorizer = self._make(db)
        result = asyncio.run(service.ingest_stripe_payment("ws1", {"id": "pi_1", "amount": 500}))
        assert result is existing
        ledger.record_transaction.assert_not_called()
        categorizer.propose_categorization.assert_not_called()

    def test_cash_account_missing_raises(self):
        db = _FakeDB({})
        service, _, _ = self._make(db)
        with pytest.raises(IngestionError, match="Cash account"):
            asyncio.run(service.ingest_stripe_payment("ws1", {"id": "pi_1", "amount": 500}))

    def test_sales_account_missing_raises(self):
        db = _FakeDB({})
        db._specs[Account] = lambda i: [_mk_account("1000")] if i == 0 else []
        service, _, _ = self._make(db)
        with pytest.raises(IngestionError, match="Sales account"):
            asyncio.run(service.ingest_stripe_payment("ws1", {"id": "pi_1", "amount": 500}))

    def test_success_creates_transaction_and_categorizes(self):
        db = _FakeDB({})
        db._specs[Account] = lambda i: [_mk_account("1000")] if i == 0 else [
            _mk_account("4000", acc_type=AccountType.REVENUE)
        ]
        service, ledger, categorizer = self._make(db)
        result = asyncio.run(service.ingest_stripe_payment(
            "ws1", {"id": "pi_1", "amount": 2999, "currency": "usd", "description": "coffee"})
        )
        assert result.id == "tx-new"
        call = ledger.record_transaction.call_args
        assert call.kwargs["source"] == "stripe"
        assert call.kwargs["external_id"] == "pi_1"
        assert call.kwargs["metadata"] == {"id": "pi_1", "amount": 2999, "currency": "usd", "description": "coffee"}
        assert call.kwargs["entries"] == [
            {"account_id": "acc-1000", "type": EntryType.DEBIT, "amount": 29.99},
            {"account_id": "acc-4000", "type": EntryType.CREDIT, "amount": 29.99},
        ]
        categorizer.propose_categorization.assert_called_once_with(result, "ws1")

    def test_success_default_description_and_amount(self):
        db = _FakeDB({})
        db._specs[Account] = lambda i: [_mk_account("1000")] if i == 0 else [
            _mk_account("4000", acc_type=AccountType.REVENUE)
        ]
        service, ledger, _ = self._make(db)
        asyncio.run(service.ingest_stripe_payment("ws1", {"id": None}))
        assert ledger.record_transaction.call_args.kwargs["description"] == "Stripe Payment None"
        assert ledger.record_transaction.call_args.kwargs["entries"][0]["amount"] == 0.0


# ============================================================================
# 3. accounting/seeds.py
# ============================================================================
class _FakeAccount:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.id = f"acc-{kwargs.get('code', '?')}"


class TestSeedDefaultAccounts:
    def test_seeds_all_eight_accounts(self):
        db = _FakeDB({})
        with patch.object(__import__("accounting.seeds", fromlist=["x"]), "Account", _FakeAccount):
            result = seed_default_accounts(db, "ws1")
        assert len(db.added) == 8
        codes = {a.code for a in db.added}
        assert codes == {"1000", "1100", "2000", "2100", "4000", "5000", "5100", "5200"}
        assert db.commits == 1
        assert result["cash"] == "acc-1000"
        assert result["sales"] == "acc-4000"
        assert result["software"] == "acc-5100"
        assert {a.type for a in db.added} == {
            AccountType.ASSET, AccountType.LIABILITY, AccountType.REVENUE, AccountType.EXPENSE,
        }
        assert all(a.workspace_id == "ws1" for a in db.added)


# ============================================================================
# 4. accounting/sync_manager.py
# ============================================================================
class TestAccountingSyncManager:
    @contextmanager
    def _make(self, db, zoho_tx=None, xero_tx=None, qbo_tx=None):
        zoho = MagicMock()
        zoho.get_bank_transactions = AsyncMock(return_value=zoho_tx if zoho_tx is not None else [])
        xero = MagicMock()
        xero.get_invoices = AsyncMock(return_value=xero_tx if xero_tx is not None else [])
        qbo = MagicMock()
        qbo.get_expenses = AsyncMock(return_value=qbo_tx if qbo_tx is not None else [])
        categorizer = MagicMock()
        categorizer.categorize_transaction = MagicMock()
        pipeline = MagicMock()
        pipeline.ingest_message = AsyncMock(return_value=None)
        patchers = [
            patch.object(__import__("accounting.sync_manager", fromlist=["x"]), "ZohoBooksService",
                         return_value=zoho),
            patch.object(__import__("accounting.sync_manager", fromlist=["x"]), "XeroService",
                         return_value=xero),
            patch.object(__import__("accounting.sync_manager", fromlist=["x"]), "QuickBooksService",
                         return_value=qbo),
            patch.object(__import__("accounting.sync_manager", fromlist=["x"]), "AICategorizer",
                         return_value=categorizer),
            patch.object(__import__("accounting.sync_manager", fromlist=["x"]), "ingestion_pipeline",
                         pipeline),
        ]
        for p in patchers:
            p.start()
        try:
            yield AccountingSyncManager(db), zoho, xero, qbo, categorizer, pipeline
        finally:
            for p in patchers:
                p.stop()

    def test_unsupported_platform_raises(self):
        db = _FakeDB({})
        with self._make(db) as (manager, *_):
            with pytest.raises(ValueError, match="Unsupported platform"):
                asyncio.run(manager.sync_external_transactions("ws1", "sage", {"access_token": "t"}))

    def test_zoho_ingests_new_and_skips_existing(self):
        db = _FakeDB({})
        raw = [{"transaction_id": "z1", "amount": "12.50", "description": "Zoho fee", "date": "2026-01-05"}]
        existing = _mk_tx(external_id="z1")
        with self._make(db, zoho_tx=raw) as (manager, zoho, *_):
            db._specs[Transaction] = lambda i: [existing] if i >= 1 else []
            result = asyncio.run(manager.sync_external_transactions(
                "ws1", "zoho", {"access_token": "t", "organization_id": "o", "account_id": "a"})
            )
        assert result["status"] == "success"
        assert result["ingested"] == 1
        assert result["platform"] == "zoho"
        assert db.commits == 1
        assert db.flushes == 1
        tx = [a for a in db.added if hasattr(a, "metadata_json")][0]
        assert tx.metadata_json["external_id"] == "z1"
        assert tx.metadata_json["platform"] == "zoho"
        zoho.get_bank_transactions.assert_awaited_with("t", "o", "a")

    def test_zoho_skips_existing_transaction(self):
        db = _FakeDB({})
        raw = [{"transaction_id": "z1", "amount": "12.50", "date": "2026-01-05"}]
        existing = _mk_tx(external_id="z1")
        with self._make(db, zoho_tx=raw) as (manager, *_):
            db._specs[Transaction] = [existing]
            result = asyncio.run(manager.sync_external_transactions(
                "ws1", "zoho", {"access_token": "t", "organization_id": "o"})
            )
        assert result["ingested"] == 0
        assert db.added == []
        assert db.flushes == 0

    def test_zoho_defaults_and_ingest_pipeline_failure(self):
        db = _FakeDB({})
        raw = [{"amount": "5"}]  # no date, no description, no transaction_id
        with self._make(db, zoho_tx=raw) as (manager, _, _, _, _, pipeline):
            db._specs[Transaction] = []
            pipeline.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            result = asyncio.run(manager.sync_external_transactions(
                "ws1", "zoho", {"access_token": "t", "organization_id": "o"})
            )
        assert result["ingested"] == 1
        tx = [a for a in db.added if hasattr(a, "metadata_json")][0]
        assert tx.description == "Zoho Transaction"
        assert tx.metadata_json["external_id"] == ""

    def test_xero_ingests(self):
        db = _FakeDB({})
        raw = [{"InvoiceNumber": "INV-1", "Total": "99", "DateString": "2026-02-01T00:00:00", "InvoiceID": "x1"}]
        with self._make(db, xero_tx=raw) as (manager, _, xero, *_):
            db._specs[Transaction] = []
            result = asyncio.run(manager.sync_external_transactions(
                "ws1", "xero", {"access_token": "t", "tenant_id": "tid"})
            )
        assert result["ingested"] == 1
        tx = [a for a in db.added if hasattr(a, "metadata_json")][0]
        assert tx.description == "Xero Invoice: INV-1"
        assert tx.metadata_json["external_id"] == "x1"
        assert tx.transaction_date == datetime(2026, 2, 1)
        xero.get_invoices.assert_awaited_with("t", "tid")

    def test_xero_default_date(self):
        db = _FakeDB({})
        raw = [{"InvoiceNumber": "INV-2", "Total": "99", "InvoiceID": "x2"}]
        with self._make(db, xero_tx=raw) as (manager, *_):
            db._specs[Transaction] = []
            asyncio.run(manager.sync_external_transactions(
                "ws1", "xero", {"access_token": "t", "tenant_id": "tid"})
            )
            tx = [a for a in db.added if hasattr(a, "metadata_json")][0]
            assert tx.transaction_date.date() == datetime.now().date()

    def test_quickbooks_ingests(self):
        db = _FakeDB({})
        raw = [{"PrivateNote": "QBO note", "TotalAmt": "55", "TxnDate": "2026-03-03", "Id": "q1"}]
        with self._make(db, qbo_tx=raw) as (manager, _, _, qbo, _, pipeline):
            db._specs[Transaction] = []
            result = asyncio.run(manager.sync_external_transactions(
                "ws1", "quickbooks", {"realm_id": "r", "access_token": "t"})
            )
        assert result["ingested"] == 1
        tx = [a for a in db.added if hasattr(a, "metadata_json")][0]
        assert tx.description == "QBO note"
        assert tx.metadata_json["external_id"] == "q1"
        qbo.get_expenses.assert_awaited_with("r", "t")

    def test_quickbooks_defaults(self):
        db = _FakeDB({})
        raw = [{"TotalAmt": "1", "Id": "q2"}]  # no note, no date
        with self._make(db, qbo_tx=raw) as (manager, *_):
            db._specs[Transaction] = []
            asyncio.run(manager.sync_external_transactions(
                "ws1", "quickbooks", {"realm_id": "r", "access_token": "t"})
            )
            tx = [a for a in db.added if hasattr(a, "metadata_json")][0]
            assert tx.description == "QBO Expense"
            assert tx.transaction_date.date() == datetime.now().date()

    def test_ingest_pipeline_success_path_uses_quickbooks_type(self):
        db = _FakeDB({})
        raw = [{"TotalAmt": "1", "Id": "q3", "TxnDate": "2026-03-03"}]
        with self._make(db, qbo_tx=raw) as (manager, _, _, _, _, pipeline):
            db._specs[Transaction] = []
            asyncio.run(manager.sync_external_transactions(
                "ws1", "quickbooks", {"realm_id": "r", "access_token": "t"})
            )
            call = pipeline.ingest_message.call_args
        assert call.kwargs["app_type"] == "quickbooks"
        assert "Financial Transaction:" in call.kwargs["message_data"]["content"]
        assert call.kwargs["message_data"]["metadata"]["workspace_id"] == "ws1"


# ============================================================================
# 5. accounting/workflow_service.py
# ============================================================================
class TestFinancialWorkflowServiceImports:
    def test_module_imports(self):
        """Regression: module was unimportable (`get_reasoning_engine` does
        not exist in core.cross_system_reasoning)."""
        import accounting.workflow_service as mod
        assert mod.CrossSystemReasoningEngine is not None


class TestFinancialWorkflowService:
    def _make(self, db, integrity=None):
        reasoning = MagicMock()
        if integrity is not None:
            reasoning.check_financial_integrity = AsyncMock(return_value=integrity)
        else:
            reasoning.check_financial_integrity = None
        asana = MagicMock()
        asana.get_task = AsyncMock(return_value={"completed": False})
        asana.complete_task = AsyncMock(return_value={"success": True})
        slack = MagicMock()
        patchers = [
            patch.object(__import__("accounting.workflow_service", fromlist=["x"]),
                         "CrossSystemReasoningEngine", return_value=reasoning),
            patch.object(__import__("accounting.workflow_service", fromlist=["x"]),
                         "AsanaService", return_value=asana),
            patch.object(__import__("accounting.workflow_service", fromlist=["x"]),
                         "SlackUnifiedService", return_value=slack),
        ]
        for p in patchers:
            p.start()
        service = FinancialWorkflowService(db)
        for p in patchers:
            p.stop()
        return service, reasoning, asana

    def test_handle_event_transaction_not_found(self):
        db = _FakeDB({})
        service, reasoning, _ = self._make(db, integrity=[])
        asyncio.run(service.handle_transaction_event("missing"))
        reasoning.check_financial_integrity.assert_not_awaited()

    def test_handle_event_degrades_when_no_integrity_check(self):
        """Regression: CrossSystemReasoningEngine has no
        check_financial_integrity — the handler must not AttributeError."""
        db = _FakeDB({})
        db._specs[Transaction] = [_mk_tx(metadata_json={"task_id": "t1"})]
        service, reasoning, _ = self._make(db)  # integrity method absent
        asyncio.run(service.handle_transaction_event("tx-1"))
        assert db.commits == 0

    def test_handle_event_with_budget_overrun_alert(self):
        db = _FakeDB({})
        db._specs[Transaction] = [_mk_tx(metadata_json={
            "task_id": "t1", "transaction_type": "ar_payment",
        })]
        service, reasoning, asana = self._make(db, integrity=[{"type": "FINANCIAL_BUDGET_OVERRUN"}])
        asana.get_task = AsyncMock(return_value={"completed": True})
        asana.complete_task = AsyncMock(return_value={"success": True})
        asyncio.run(service.handle_transaction_event("tx-1"))
        reasoning.check_financial_integrity.assert_awaited_once()
        asana.get_task.assert_awaited_with("t1")
        assert db.commits == 0

    def test_handle_event_non_overrun_alert_ignored(self):
        db = _FakeDB({})
        db._specs[Transaction] = [_mk_tx()]
        service, reasoning, _ = self._make(db, integrity=[{"type": "OTHER"}])
        asyncio.run(service.handle_transaction_event("tx-1"))

    def test_task_completion_skipped_for_non_payment(self):
        db = _FakeDB({})
        tx = _mk_tx(metadata_json={"task_id": "t1", "transaction_type": "refund"})
        service, _, asana = self._make(db)
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        asana.get_task.assert_not_awaited()
        asana.complete_task.assert_not_awaited()

    def test_task_completion_ar_payment_type(self):
        db = _FakeDB({})
        tx = _mk_tx(metadata_json={"task_id": "t1", "transaction_type": "ar_payment"})
        service, _, asana = self._make(db)
        asana.get_task = AsyncMock(return_value={"completed": True})
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        asana.get_task.assert_awaited_with("t1")
        asana.complete_task.assert_not_awaited()
        assert db.commits == 0

    def test_task_completion_payment_received_type_full_success(self):
        db = _FakeDB({})
        tx = _mk_tx(metadata_json={"task_id": "t1", "transaction_type": "payment_received"})
        service, _, asana = self._make(db)
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        assert db.commits == 1
        assert tx.metadata_json["task_completion"]["task_id"] == "t1"
        asana.complete_task.assert_awaited_once()

    def test_task_completion_is_ar_payment_flag(self):
        db = _FakeDB({})
        tx = _mk_tx(metadata_json={"task_id": "t1", "is_ar_payment": True})
        service, _, asana = self._make(db)
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        asana.complete_task.assert_awaited_once()

    def test_task_completion_keyword_description(self):
        db = _FakeDB({})
        tx = _mk_tx(amount=50.0, description="Customer payment received",
                    metadata_json={"task_id": "t1"})
        service, _, asana = self._make(db)
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        asana.complete_task.assert_awaited_once()

    def test_task_completion_empty_metadata_initialized(self):
        db = _FakeDB({})
        tx = _mk_tx(amount=50.0, description="invoice payment 123", metadata_json={})
        service, _, asana = self._make(db)
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        assert db.commits == 1
        assert tx.metadata_json["task_completion"]["completed_by"] == "workflow_automation"

    def test_task_completion_get_task_raises_continues(self):
        db = _FakeDB({})
        tx = _mk_tx(metadata_json={"task_id": "t1", "transaction_type": "ar_payment"})
        service, _, asana = self._make(db)
        asana.get_task = AsyncMock(side_effect=RuntimeError("asana down"))
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        asana.complete_task.assert_awaited_once()

    def test_task_completion_complete_failure(self):
        db = _FakeDB({})
        tx = _mk_tx(metadata_json={"task_id": "t1", "transaction_type": "ar_payment"})
        service, _, asana = self._make(db)
        asana.complete_task = AsyncMock(return_value={"success": False})
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        assert db.commits == 0

    def test_task_completion_outer_exception_swallowed(self):
        db = _FakeDB({})
        tx = _mk_tx()
        tx.metadata_json = None  # .get crashes → outer except
        service, _, asana = self._make(db)
        asyncio.run(service._handle_payment_task_completion(tx, "t1"))
        asana.complete_task.assert_not_awaited()

    def test_automate_invoice_to_task(self):
        db = _FakeDB({})
        service, _, asana = self._make(db)
        asana.create_task = AsyncMock(return_value={"task_id": "new-task"})
        result = asyncio.run(service.automate_invoice_to_task(
            "ws1", {"invoice_number": "INV-9", "total": 500.0})
        )
        assert result == {"task_id": "new-task"}
        call = asana.create_task.call_args
        assert call.kwargs["workspace_id"] == "ws1"
        assert "INV-9" in call.kwargs["name"]
        assert "$500.0" in call.kwargs["notes"]


# ============================================================================
# 6. accounting/workflows.py
# ============================================================================
def _mk_invoice(inv_id="inv-1", due_offset_days=0, amount=100.0, status=InvoiceStatus.OPEN,
                customer_name="Acme", number="INV-1"):
    due = datetime.now(timezone.utc) - timedelta(days=due_offset_days)
    return SimpleNamespace(
        id=inv_id,
        workspace_id="ws1",
        invoice_number=number,
        due_date=due,
        amount=amount,
        status=status,
        customer=SimpleNamespace(name=customer_name),
    )


class TestCollectionAgentOverdue:
    def test_no_overdue_invoices(self):
        db = _FakeDB({})
        with patch.object(__import__("accounting.workflows", fromlist=["x"]), "manager",
                          MagicMock(broadcast=AsyncMock())):
            reminders = asyncio.run(CollectionAgent(db).check_overdue_invoices("ws1"))
        assert reminders == []
        assert db.commits == 1

    def test_overdue_invoice_reminder_and_broadcast(self):
        db = _FakeDB({})
        invoice = _mk_invoice(due_offset_days=15)
        db._specs[Invoice] = [invoice]
        broadcast = AsyncMock()
        with patch.object(__import__("accounting.workflows", fromlist=["x"]), "manager",
                          MagicMock(broadcast=broadcast)):
            reminders = asyncio.run(CollectionAgent(db).check_overdue_invoices("ws1"))
        assert invoice.status == InvoiceStatus.OVERDUE
        assert len(reminders) == 1
        assert reminders[0]["invoice_id"] == "inv-1"
        assert db.commits == 1
        call = broadcast.call_args
        assert call.args[0] == "workspace:ws1"
        assert call.args[1]["type"] == "accounting.reminder_sent"
        assert call.args[1]["data"]["customer"] == "Acme"


class TestCollectionAgentReminderMessage:
    def test_reminder_message_format(self):
        invoice = _mk_invoice(due_offset_days=3, amount=1234.5, number="INV-77")
        message = CollectionAgent(_FakeDB({}))._generate_reminder_message(invoice)
        assert "Hello Acme" in message
        assert "INV-77" in message
        assert "$1,234.50" in message
        assert "3 days overdue" in message


class TestCollectionAgentAgingReport:
    def _report(self, invoices):
        db = _FakeDB({})
        db._specs[Invoice] = invoices
        return CollectionAgent(db).generate_aging_report("ws1")

    def test_empty_report(self):
        report = self._report([])
        assert report == {
            "current": 0.0, "overdue_30": 0.0, "overdue_60": 0.0,
            "overdue_90": 0.0, "total_ar": 0.0,
        }

    def test_buckets(self):
        report = self._report([
            _mk_invoice("i1", due_offset_days=-5, amount=100.0),   # current
            _mk_invoice("i2", due_offset_days=20, amount=200.0),   # 31-60? no: 20 → overdue_30
            _mk_invoice("i3", due_offset_days=45, amount=300.0),   # overdue_60
            _mk_invoice("i4", due_offset_days=80, amount=400.0),   # overdue_90
            _mk_invoice("i5", due_offset_days=200, amount=500.0),  # overdue_90
            _mk_invoice("i6", due_offset_days=5, amount=10.0, status=InvoiceStatus.OVERDUE),  # overdue_30
        ])
        assert report["current"] == 100.0
        assert report["overdue_30"] == 210.0
        assert report["overdue_60"] == 300.0
        assert report["overdue_90"] == 900.0
        assert report["total_ar"] == 1510.0


# ============================================================================
# 7. api/admin/budget_routes.py
# ============================================================================
@pytest.fixture
def mock_super_admin():
    user = MagicMock()
    user.id = "admin-w74"
    user.email = "admin@test.local"
    user.role = UserRole.SUPER_ADMIN.value
    return user


@pytest.fixture
def budget_client(mock_super_admin, worker_database):
    from api.admin.budget_routes import router
    from core.admin_endpoints import get_super_admin
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)
    SessionLocal = worker_database

    async def _override_admin():
        return mock_super_admin

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_super_admin] = _override_admin
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _add_tenant(db, tenant_id):
    t = Tenant(id=tenant_id, name="Test", subdomain=f"sub-{tenant_id}")
    db.add(t)
    db.commit()
    return t


def _add_billing_setting(db, tenant_id, value):
    row = TenantSetting(tenant_id=tenant_id, setting_key="billing", setting_value=value)
    db.add(row)
    db.commit()


class TestBudgetRoutesMissingBranches:
    def test_get_unknown_tenant_404(self, budget_client):
        resp = budget_client.get("/api/admin/tenants/no-such-tenant/budget")
        assert resp.status_code == 404

    def test_put_unknown_tenant_404(self, budget_client):
        resp = budget_client.put("/api/admin/tenants/no-such-tenant/budget",
                                 json={"budget_limit_usd": 5.0})
        assert resp.status_code == 404

    def test_get_falls_back_to_legacy_tenant_limit(self):
        """The legacy `Tenant.budget_limit_usd` attribute fallback. SQLAlchemy
        drops non-column setattr on real instances, so the tenant is faked."""
        from api.admin.budget_routes import _resolve_budget_state

        db = _FakeDB({})
        db._specs[Tenant] = [SimpleNamespace(budget_limit_usd=123.45)]
        with patch("core.spend_aggregation_service.SpendAggregationService") as svc_cls:
            svc_cls.return_value.update_tenant_spend.return_value = {}
            state = _resolve_budget_state(db, "t-legacy-limit")
        assert state["budget_limit_usd"] == 123.45

    def test_resolve_budget_state_tenant_missing_limit_zero(self):
        from api.admin.budget_routes import _resolve_budget_state

        db = _FakeDB({})
        db._specs[Tenant] = [SimpleNamespace()]
        with patch("core.spend_aggregation_service.SpendAggregationService") as svc_cls:
            svc_cls.return_value.update_tenant_spend.return_value = {}
            state = _resolve_budget_state(db, "t-no-limit")
        assert state["budget_limit_usd"] == 0.0

    def test_get_invalid_json_setting_returns_defaults(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-bad-json")
            _add_billing_setting(db, "t-bad-json", "{not valid json")
            resp = budget_client.get("/api/admin/tenants/t-bad-json/budget")
            assert resp.status_code == 200
            assert resp.json()["budget_limit_usd"] == 0.0
            assert resp.json()["enforcement_mode"] == "soft_stop"
        finally:
            db.close()

    def test_get_non_dict_json_setting_returns_defaults(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-array-json")
            _add_billing_setting(db, "t-array-json", "[1, 2, 3]")
            resp = budget_client.get("/api/admin/tenants/t-array-json/budget")
            assert resp.status_code == 200
            assert resp.json()["budget_limit_usd"] == 0.0
        finally:
            db.close()

    def test_get_resets_invalid_enforcement_mode(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-invalid-mode2")
            _add_billing_setting(
                db, "t-invalid-mode2",
                '{"budget_limit_usd": 50, "enforcement": {"mode": "nonsense"}}',
            )
            resp = budget_client.get("/api/admin/tenants/t-invalid-mode2/budget")
            assert resp.status_code == 200
            assert resp.json()["enforcement_mode"] == "soft_stop"
        finally:
            db.close()

    def test_put_creates_then_updates_existing_row(self, budget_client, worker_database):
        """Covers _write_billing_setting insert (row absent) + update (row present)."""
        db = worker_database()
        try:
            _add_tenant(db, "t-update-row")
            put1 = budget_client.put("/api/admin/tenants/t-update-row/budget",
                                     json={"budget_limit_usd": 10.0})
            assert put1.status_code == 200
            put2 = budget_client.put("/api/admin/tenants/t-update-row/budget",
                                     json={"budget_limit_usd": 20.0})
            assert put2.status_code == 200
            rows = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == "t-update-row",
                TenantSetting.setting_key == "billing",
            ).all()
            assert len(rows) == 1
            assert '"budget_limit_usd": 20.0' in rows[0].setting_value
        finally:
            db.close()

    def test_put_partial_limit_only_preserves_enforcement(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-partial")
            first = budget_client.put("/api/admin/tenants/t-partial/budget",
                                      json={"enforcement_mode": "hard_stop"})
            assert first.status_code == 200
            second = budget_client.put("/api/admin/tenants/t-partial/budget",
                                       json={"budget_limit_usd": 33.0})
            assert second.status_code == 200
            body = second.json()
            assert body["budget_limit_usd"] == 33.0
            assert body["enforcement_mode"] == "hard_stop"
        finally:
            db.close()

    def test_put_invalid_mode_returns_422(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-422")
            resp = budget_client.put("/api/admin/tenants/t-422/budget",
                                     json={"enforcement_mode": "bananas"})
            assert resp.status_code == 422
        finally:
            db.close()

    def test_put_no_changes_is_noop(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-noop")
            resp = budget_client.put("/api/admin/tenants/t-noop/budget", json={})
            assert resp.status_code == 200
            assert resp.json()["budget_limit_usd"] == 0.0
        finally:
            db.close()

    def test_spend_service_error_degrades_to_zero(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-spend-err")
            with patch("core.spend_aggregation_service.SpendAggregationService") as svc_cls:
                svc_cls.return_value.update_tenant_spend.side_effect = RuntimeError("boom")
                resp = budget_client.get("/api/admin/tenants/t-spend-err/budget")
            assert resp.status_code == 200
            body = resp.json()
            assert body["current_spend_usd"] == 0.0
            assert body["utilization_percent"] == 0.0
        finally:
            db.close()

    def test_spend_service_error_dict_skips_update(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-spend-err2")
            with patch("core.spend_aggregation_service.SpendAggregationService") as svc_cls:
                svc_cls.return_value.update_tenant_spend.return_value = {"error": "nope"}
                resp = budget_client.get("/api/admin/tenants/t-spend-err2/budget")
            assert resp.status_code == 200
            assert resp.json()["current_spend_usd"] == 0.0
        finally:
            db.close()

    def test_spend_success_with_utilization(self, budget_client, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-spend-ok")
            budget_client.put("/api/admin/tenants/t-spend-ok/budget",
                              json={"budget_limit_usd": 100.0})
            with patch("core.spend_aggregation_service.SpendAggregationService") as svc_cls:
                svc_cls.return_value.update_tenant_spend.return_value = {"current_spend_usd": 25.0}
                resp = budget_client.get("/api/admin/tenants/t-spend-ok/budget")
            assert resp.status_code == 200
            body = resp.json()
            assert body["current_spend_usd"] == 25.0
            assert body["utilization_percent"] == 25.0
        finally:
            db.close()

    def test_read_billing_setting_direct_invalid_json(self, worker_database):
        db = worker_database()
        try:
            _add_tenant(db, "t-direct")
            _add_billing_setting(db, "t-direct", "null")
            assert _read_billing_setting(db, "t-direct") == {}
            assert _resolve_budget_state(db, "t-direct")["budget_limit_usd"] == 0.0
        finally:
            db.close()


# ============================================================================
# 8. api/admin/jit_verification_routes.py
# ============================================================================
def _jit_cache_obj(stats=None, hit_rate=0.9):
    cache = MagicMock()
    cache.get_stats.return_value = stats or _jit_cache_stats(hit_rate)
    cache.clear_all = MagicMock()
    cache.verify_citations_batch = AsyncMock(
        return_value=[
            SimpleNamespace(exists=True, to_dict=lambda: {"exists": True, "citation": "c1"}),
            SimpleNamespace(exists=False, to_dict=lambda: {"exists": False, "citation": "c2"}),
        ]
    )
    cache.l1 = SimpleNamespace(
        max_size=100, verification_ttl=3600, query_ttl=300
    )
    cache.l2 = SimpleNamespace(_enabled=False, verification_ttl=7200, query_ttl=600)
    return cache


def _jit_worker_obj(running=True, metrics=None):
    worker = MagicMock()
    worker.get_metrics.return_value = metrics or _jit_worker_metrics(running=running)
    worker.verify_fact_citations = AsyncMock(
        return_value={"s3://d.pdf": SimpleNamespace(exists=True, to_dict=lambda: {"exists": True})}
    )
    worker.workspace_id = "ws-jit"
    worker.check_interval = 60
    worker.batch_size = 10
    worker.max_concurrent = 4
    worker._running = running
    worker._citation_access_count = {"s3://d.pdf": 7}
    return worker


class TestJitEndpointsFull:
    """Full endpoint coverage so the routes file is standalone-covered."""

    def test_cache_stats(self, jit_client):
        cache = _jit_cache_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache):
            resp = jit_client.get("/api/admin/governance/jit/cache/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["l1_verification_cache_size"] == 10
        assert body["l2_enabled"] is False
        assert body["l1_verification_hit_rate"] == 0.9

    def test_cache_clear(self, jit_client):
        cache = _jit_cache_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache):
            resp = jit_client.post("/api/admin/governance/jit/cache/clear")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cleared"
        cache.clear_all.assert_called_once()

    def test_verify_citations_mixed_results(self, jit_client):
        cache = _jit_cache_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache):
            resp = jit_client.post("/api/admin/governance/jit/verify-citations",
                                   json={"citations": ["c1", "c2"], "force_refresh": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 2
        assert body["verified_count"] == 1
        assert body["failed_count"] == 1
        cache.verify_citations_batch.assert_awaited_with(["c1", "c2"], force_refresh=True)

    def test_verify_citations_error_500(self, jit_client):
        cache = _jit_cache_obj()
        cache.verify_citations_batch = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache):
            resp = jit_client.post("/api/admin/governance/jit/verify-citations",
                                   json={"citations": ["c1"]})
        assert resp.status_code == 500

    def test_worker_metrics(self, jit_client):
        worker = _jit_worker_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_worker",
                   return_value=worker):
            resp = jit_client.get("/api/admin/governance/jit/worker/metrics")
        assert resp.status_code == 200
        assert resp.json()["running"] is True

    def test_worker_metrics_error_500(self, jit_client):
        worker = _jit_worker_obj()
        worker.get_metrics.side_effect = RuntimeError("boom")
        with patch("api.admin.jit_verification_routes.get_jit_verification_worker",
                   return_value=worker):
            resp = jit_client.get("/api/admin/governance/jit/worker/metrics")
        assert resp.status_code == 500

    def test_worker_start(self, jit_client):
        worker = _jit_worker_obj()
        with patch("api.admin.jit_verification_routes.start_jit_verification_worker",
                   new=AsyncMock(return_value=worker)):
            resp = jit_client.post("/api/admin/governance/jit/worker/start")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
        assert body["workspace_id"] == "ws-jit"
        assert body["check_interval_seconds"] == 60

    def test_worker_stop(self, jit_client):
        with patch("api.admin.jit_verification_routes.stop_jit_verification_worker",
                   new=AsyncMock(return_value=None)):
            resp = jit_client.post("/api/admin/governance/jit/worker/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_worker_verify_fact(self, jit_client):
        worker = _jit_worker_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_worker",
                   return_value=worker):
            resp = jit_client.post("/api/admin/governance/jit/worker/verify-fact/fact-9")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fact_id"] == "fact-9"
        assert body["citation_count"] == 1
        worker.verify_fact_citations.assert_awaited_with("fact-9")

    def test_worker_top_citations(self, jit_client):
        worker = _jit_worker_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_worker",
                   return_value=worker):
            resp = jit_client.get("/api/admin/governance/jit/worker/top-citations?limit=5")
        assert resp.status_code == 200
        assert resp.json()["total_unique_citations"] == 1

    def test_worker_top_citations_invalid_limit(self, jit_client):
        worker = _jit_worker_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_worker",
                   return_value=worker):
            resp = jit_client.get("/api/admin/governance/jit/worker/top-citations?limit=0")
        assert resp.status_code == 422

    def test_warm_cache(self, jit_client):
        cache = _jit_cache_obj()
        facts = [SimpleNamespace(id=f"f{i}", citations=[f"s3://bucket/doc{i}.pdf"]) for i in range(3)]
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache), patch(
            "core.agent_world_model.WorldModelService"
        ) as wm_cls:
            wm_cls.return_value.list_all_facts = AsyncMock(return_value=facts)
            resp = jit_client.post("/api/admin/governance/jit/cache/warm?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "warmed"
        assert body["facts_processed"] == 3
        assert body["citations_verified"] == 3
        wm_cls.assert_called_once_with("default")

    def test_config(self, jit_client):
        cache = _jit_cache_obj()
        worker = _jit_worker_obj()
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache), patch(
            "api.admin.jit_verification_routes.get_jit_verification_worker",
            return_value=worker,
        ):
            resp = jit_client.get("/api/admin/governance/jit/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["worker"]["workspace_id"] == "ws-jit"
        assert body["cache"]["l1"]["max_size"] == 100
        assert body["cache"]["l2"]["enabled"] is False
@pytest.fixture
def jit_client():
    from api.admin.jit_verification_routes import router

    app = FastAPI()
    app.include_router(router)
    admin = MagicMock()
    admin.id = "jit-admin"
    admin.role = UserRole.ADMIN

    async def _override_user():
        return admin

    app.dependency_overrides[get_current_user] = _override_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def _jit_worker_metrics(running=True, stale=0, outdated=0):
    return {
        "running": running,
        "total_citations": 10,
        "verified_count": 5,
        "failed_count": 1,
        "stale_facts": stale,
        "outdated_facts": outdated,
        "last_run_time": None,
        "last_run_duration": 1.0,
        "average_verification_time": 0.1,
        "top_citations": [],
    }


def _jit_cache_stats(hit_rate=0.9):
    return {
        "l1": {
            "l1_verification_cache_size": 10,
            "l1_query_cache_size": 5,
            "l1_verification_hits": 90,
            "l1_verification_misses": 10,
            "l1_verification_hit_rate": hit_rate,
            "l1_query_hits": 5,
            "l1_query_misses": 5,
            "l1_query_hit_rate": 0.5,
            "l1_evictions": 0,
        },
        "l2_enabled": False,
    }


class TestJitHealthExtend:
    def _client_ctx(self, worker, cache):
        from api.admin.jit_verification_routes import (
            get_jit_verification_cache,
            get_jit_verification_worker,
        )
        return [
            patch.object(__import__("api.admin.jit_verification_routes", fromlist=["x"]),
                         "get_jit_verification_cache", return_value=cache),
            patch.object(__import__("api.admin.jit_verification_routes", fromlist=["x"]),
                         "get_jit_verification_worker", return_value=worker),
        ]

    def test_health_worker_not_running_issue(self, jit_client):
        worker = MagicMock()
        worker.get_metrics.return_value = _jit_worker_metrics(running=False)
        cache = MagicMock()
        cache.get_stats.return_value = _jit_cache_stats(hit_rate=0.9)
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache), patch(
            "api.admin.jit_verification_routes.get_jit_verification_worker",
            return_value=worker,
        ):
            resp = jit_client.get("/api/admin/governance/jit/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert "Worker not running" in body["issues"]
        assert body["worker"]["running"] is False

    def test_health_low_hit_rate_issue(self, jit_client):
        worker = MagicMock()
        worker.get_metrics.return_value = _jit_worker_metrics(running=True)
        cache = MagicMock()
        cache.get_stats.return_value = _jit_cache_stats(hit_rate=0.4)
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache), patch(
            "api.admin.jit_verification_routes.get_jit_verification_worker",
            return_value=worker,
        ):
            resp = jit_client.get("/api/admin/governance/jit/health")
        body = resp.json()
        assert body["status"] == "degraded"
        assert any("Low cache hit rate" in i for i in body["issues"])
        assert body["cache"]["verification_hit_rate"] == "40.0%"

    def test_health_unhealthy_with_three_issues(self, jit_client):
        worker = MagicMock()
        worker.get_metrics.return_value = _jit_worker_metrics(running=False, stale=2, outdated=1)
        cache = MagicMock()
        cache.get_stats.return_value = _jit_cache_stats(hit_rate=0.1)
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache), patch(
            "api.admin.jit_verification_routes.get_jit_verification_worker",
            return_value=worker,
        ):
            resp = jit_client.get("/api/admin/governance/jit/health")
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert len(body["issues"]) == 4

    def test_health_healthy_still_healthy(self, jit_client):
        worker = MagicMock()
        worker.get_metrics.return_value = _jit_worker_metrics(running=True)
        cache = MagicMock()
        cache.get_stats.return_value = _jit_cache_stats(hit_rate=0.9)
        with patch("api.admin.jit_verification_routes.get_jit_verification_cache",
                   return_value=cache), patch(
            "api.admin.jit_verification_routes.get_jit_verification_worker",
            return_value=worker,
        ):
            resp = jit_client.get("/api/admin/governance/jit/health")
        assert resp.json()["status"] == "healthy"
