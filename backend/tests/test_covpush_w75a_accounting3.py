# -*- coding: utf-8 -*-
"""W75A — coverage push for accounting ledger/models/routes (3 modules).

Targets (>=95% statement coverage, standalone):
- accounting/ledger.py     (82% before)
- accounting/models.py     (100% before — import-time statements; direct
                           unit tests added for defaults/enums/relationships)
- accounting/routes.py     (0% before — router never imported by suites)

Pattern (mirrors test_covpush_w72b_api_routes.py / test_covpush_w74a_accounting2.py):
- Real in-memory SQLite (StaticPool) for ledger/model flows; scripted
  MagicMock sessions for the query-branch edge cases.
- FastAPI TestClient with dependency overrides for the router; all service
  classes (AICategorizer/FPAService/AccountExporter/AccountingSyncManager/
  AccountingDashboardService/APService) patched at the `accounting.routes`
  module level. Zero LLM spend, zero network, no real DB.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import accounting.ledger as ledger_mod
import accounting.models as models_mod
import accounting.routes as routes_mod
from accounting.ledger import (
    DoubleEntryEngine,
    EventSourcedLedger,
    LedgerError,
    UnbalancedTransactionError,
)
from accounting.models import (
    Account,
    AccountType,
    Bill,
    BillStatus,
    Budget,
    CategorizationProposal,
    CategorizationRule,
    Document,
    Entity,
    EntityType,
    EntryType,
    FinancialClose,
    Invoice,
    InvoiceStatus,
    JournalEntry,
    TaxNexus,
    Transaction,
    TransactionStatus,
)
from accounting.routes import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    check_accounting_enabled,
    validate_file_extension,
    validate_file_type_with_magic_bytes,
)
from core.auth_endpoints import get_current_user
from core.database import Base, get_db


# ============================================================================
# Shared fixtures / helpers
# ============================================================================

@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session()
    engine.dispose()


def make_client(overrides=None):
    app = FastAPI()
    app.include_router(routes_mod.router)
    for dep, value in (overrides or {}).items():
        app.dependency_overrides[dep] = value
    return TestClient(app, raise_server_exceptions=False)


def fake_user(user_id="u-75", email="user@test.com"):
    u = MagicMock()
    u.id = user_id
    u.email = email
    u.role = "admin"
    return u


def user_override(user_id="u-75", email="user@test.com"):
    def _override():
        return fake_user(user_id, email)
    return _override


def db_override(db):
    def _override():
        yield db
    return _override


def auth_fail_override():
    def _override():
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _override


@pytest.fixture
def settings_on():
    s = MagicMock()
    s.is_accounting_enabled.return_value = True
    with patch("accounting.routes.get_automation_settings", return_value=s):
        yield s


@pytest.fixture
def settings_off():
    s = MagicMock()
    s.is_accounting_enabled.return_value = False
    with patch("accounting.routes.get_automation_settings", return_value=s):
        yield s


def make_router_client(db, user="u-75"):
    return make_client(
        {
            get_current_user: user_override(user),
            get_db: db_override(db),
        }
    )


# ============================================================================
# 1. accounting/ledger.py — EventSourcedLedger
# ============================================================================

class TestLedgerRecordTransaction:
    def _ledger(self, memory_db):
        return EventSourcedLedger(memory_db)

    def _entries(self, debit=Decimal("100.00"), credit=Decimal("100.00")):
        return [
            {"account_id": "acc-1", "type": EntryType.DEBIT, "amount": debit},
            {"account_id": "acc-2", "type": EntryType.CREDIT, "amount": credit},
        ]

    def test_record_transaction_success(self, memory_db):
        ledger = self._ledger(memory_db)
        tx = ledger.record_transaction(
            workspace_id="ws-1",
            transaction_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            description="Office supplies",
            entries=self._entries(),
        )
        assert isinstance(tx, Transaction)
        assert tx.id
        assert tx.workspace_id == "ws-1"
        assert tx.source == "manual"
        assert tx.status == TransactionStatus.POSTED
        rows = memory_db.query(JournalEntry).all()
        assert len(rows) == 2
        assert {r.type for r in rows} == {EntryType.DEBIT, EntryType.CREDIT}

    def test_record_transaction_defaults_source_and_metadata(self, memory_db):
        ledger = self._ledger(memory_db)
        tx = ledger.record_transaction(
            workspace_id="ws-1",
            transaction_date=datetime(2026, 5, 2, tzinfo=timezone.utc),
            description="Stripe payout",
            entries=self._entries(Decimal("10.00"), Decimal("10.00")),
            source="stripe",
            external_id="ch_123",
            metadata={"customer": "acme"},
        )
        assert tx.source == "stripe"
        assert tx.external_id == "ch_123"
        assert tx.metadata_json == {"customer": "acme"}
        rows = memory_db.query(JournalEntry).all()
        assert all(r.transaction_id == tx.id for r in rows)

    def test_record_transaction_entry_descriptions(self, memory_db):
        ledger = self._ledger(memory_db)
        ledger.record_transaction(
            workspace_id="ws-1",
            transaction_date=datetime(2026, 5, 3, tzinfo=timezone.utc),
            description="Bill",
            entries=[
                {"account_id": "acc-1", "type": EntryType.DEBIT,
                 "amount": Decimal("25.00"), "description": "leg one"},
                {"account_id": "acc-2", "type": EntryType.CREDIT,
                 "amount": Decimal("25.00")},
            ],
        )
        rows = memory_db.query(JournalEntry).order_by(JournalEntry.type).all()
        descs = {r.description for r in rows}
        assert "leg one" in descs
        assert None in descs

    def test_record_transaction_unbalanced_debit_side(self, memory_db):
        ledger = self._ledger(memory_db)
        with pytest.raises(UnbalancedTransactionError) as ei:
            ledger.record_transaction(
                workspace_id="ws-1",
                transaction_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
                description="Bad",
                entries=self._entries(debit=Decimal("101.00")),
            )
        assert "Debits" in str(ei.value)
        assert "Credits" in str(ei.value)
        assert "Difference" in str(ei.value)
        assert memory_db.query(Transaction).count() == 0

    def test_record_transaction_unbalanced_credit_side(self, memory_db):
        ledger = self._ledger(memory_db)
        with pytest.raises(UnbalancedTransactionError):
            ledger.record_transaction(
                workspace_id="ws-1",
                transaction_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
                description="Bad",
                entries=self._entries(credit=Decimal("99.00")),
            )

    def test_record_transaction_commit_error_rolls_back(self, memory_db):
        ledger = self._ledger(memory_db)
        with patch.object(memory_db, "commit", side_effect=RuntimeError("disk full")), \
             patch.object(memory_db, "rollback", wraps=memory_db.rollback) as rb:
            with pytest.raises(LedgerError) as ei:
                ledger.record_transaction(
                    workspace_id="ws-1",
                    transaction_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
                    description="Bad",
                    entries=self._entries(),
                )
        assert "Database error" in str(ei.value)
        assert "disk full" in str(ei.value)
        rb.assert_called_once()


class TestLedgerGetAccountBalance:
    def _account(self, memory_db, account_id="acc-1", acc_type=AccountType.ASSET,
                 workspace_id="ws-1"):
        acc = Account(id=account_id, name="Cash", code="1000",
                      type=acc_type, workspace_id=workspace_id)
        memory_db.add(acc)
        memory_db.flush()
        return acc

    def _post(self, memory_db, account_id, debit, credit, status=TransactionStatus.POSTED):
        tx = Transaction(
            workspace_id="ws-1",
            transaction_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            description="tx",
            source="manual",
            status=status,
        )
        memory_db.add(tx)
        memory_db.flush()
        memory_db.add(JournalEntry(transaction_id=tx.id, account_id=account_id,
                                   type=EntryType.DEBIT, amount=debit))
        memory_db.add(JournalEntry(transaction_id=tx.id, account_id=account_id,
                                   type=EntryType.CREDIT, amount=credit))
        memory_db.commit()

    def test_asset_balance_debit_minus_credit(self, memory_db):
        self._account(memory_db)
        self._post(memory_db, "acc-1", Decimal("100.00"), Decimal("60.00"))
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("acc-1") == Decimal("40.00")

    def test_expense_balance_debit_minus_credit(self, memory_db):
        self._account(memory_db, acc_type=AccountType.EXPENSE)
        self._post(memory_db, "acc-1", Decimal("50.00"), Decimal("10.00"))
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("acc-1") == Decimal("40.00")

    def test_liability_balance_credit_minus_debit(self, memory_db):
        self._account(memory_db, acc_type=AccountType.LIABILITY)
        self._post(memory_db, "acc-1", Decimal("30.00"), Decimal("100.00"))
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("acc-1") == Decimal("70.00")

    def test_revenue_balance_credit_minus_debit(self, memory_db):
        self._account(memory_db, acc_type=AccountType.REVENUE)
        self._post(memory_db, "acc-1", Decimal("5.00"), Decimal("25.00"))
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("acc-1") == Decimal("20.00")

    def test_equity_balance_credit_minus_debit(self, memory_db):
        self._account(memory_db, acc_type=AccountType.EQUITY)
        self._post(memory_db, "acc-1", Decimal("0.00"), Decimal("1000.00"))
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("acc-1") == Decimal("1000.00")

    def test_pending_transactions_excluded(self, memory_db):
        """BUG-070 regression: only POSTED transactions count toward balance."""
        self._account(memory_db)
        self._post(memory_db, "acc-1", Decimal("100.00"), Decimal("0.00"),
                   status=TransactionStatus.PENDING)
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("acc-1") == Decimal("0.00")

    def test_account_with_no_entries(self, memory_db):
        self._account(memory_db)
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("acc-1") == Decimal("0.00")

    def test_missing_account_returns_zero(self, memory_db):
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_account_balance("no-such-account") == Decimal("0.00")

    def test_none_total_debit_row(self):
        db = MagicMock()
        account = Account(id="a1", name="Cash", code="1000",
                          type=AccountType.ASSET, workspace_id="ws-1")
        q = MagicMock()
        q.filter.return_value.first.return_value = account
        totals_q = MagicMock()
        totals_q.join.return_value.filter.return_value.group_by.return_value \
            .all.return_value = [SimpleNamespace(type=EntryType.DEBIT, total=None)]
        db.query.side_effect = [q, totals_q]
        ledger = EventSourcedLedger(db)
        assert ledger.get_account_balance("a1") == Decimal("0.00")

    def test_none_total_credit_row(self):
        db = MagicMock()
        account = Account(id="a1", name="Loan", code="2000",
                          type=AccountType.LIABILITY, workspace_id="ws-1")
        q = MagicMock()
        q.filter.return_value.first.return_value = account
        totals_q = MagicMock()
        totals_q.join.return_value.filter.return_value.group_by.return_value \
            .all.return_value = [SimpleNamespace(type=EntryType.CREDIT, total=None)]
        db.query.side_effect = [q, totals_q]
        ledger = EventSourcedLedger(db)
        assert ledger.get_account_balance("a1") == Decimal("0.00")


class TestLedgerTrialBalance:
    def test_trial_balance_maps_names(self, memory_db):
        for acc_id, name, code, acc_type in [
            ("a1", "Cash", "1000", AccountType.ASSET),
            ("a2", "Revenue", "4000", AccountType.REVENUE),
            ("a3", "Other WS", "9000", AccountType.EXPENSE),
        ]:
            memory_db.add(Account(id=acc_id, name=name, code=code,
                                  type=acc_type, workspace_id="ws-1"))
        memory_db.flush()
        for acc_id, debit, credit in [
            ("a1", Decimal("100.00"), Decimal("30.00")),
            ("a2", Decimal("10.00"), Decimal("80.00")),
            ("a3", Decimal("5.00"), Decimal("0.00")),
        ]:
            tx = Transaction(workspace_id="ws-1",
                             transaction_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
                             description="tx", source="manual",
                             status=TransactionStatus.POSTED)
            memory_db.add(tx)
            memory_db.flush()
            memory_db.add(JournalEntry(transaction_id=tx.id, account_id=acc_id,
                                       type=EntryType.DEBIT, amount=debit))
            memory_db.add(JournalEntry(transaction_id=tx.id, account_id=acc_id,
                                       type=EntryType.CREDIT, amount=credit))
        memory_db.commit()

        ledger = EventSourcedLedger(memory_db)
        balance = ledger.get_trial_balance("ws-1")
        assert balance == {
            "Cash": Decimal("70.00"),
            "Revenue": Decimal("70.00"),
            "Other WS": Decimal("5.00"),
        }

    def test_trial_balance_filters_workspace(self, memory_db):
        memory_db.add(Account(id="a1", name="Cash", code="1000",
                              type=AccountType.ASSET, workspace_id="ws-1"))
        memory_db.add(Account(id="a2", name="Other", code="1001",
                              type=AccountType.ASSET, workspace_id="ws-2"))
        memory_db.commit()
        ledger = EventSourcedLedger(memory_db)
        assert ledger.get_trial_balance("ws-1") == {"Cash": Decimal("0.00")}


class TestDoubleEntryEngine:
    def test_create_payment_entry_string_amount(self):
        entries = DoubleEntryEngine.create_payment_entry("cash-1", "exp-1", "50.25", "coffee")
        assert entries == [
            {"account_id": "exp-1", "type": EntryType.DEBIT, "amount": Decimal("50.25")},
            {"account_id": "cash-1", "type": EntryType.CREDIT, "amount": Decimal("50.25")},
        ]

    def test_create_payment_entry_float_amount(self):
        entries = DoubleEntryEngine.create_payment_entry("cash-1", "exp-1", 12.5, "x")
        assert entries[0]["amount"] == Decimal("12.5")
        assert entries[1]["amount"] == Decimal("12.5")

    def test_create_payment_entry_decimal_passthrough(self):
        amount = Decimal("99.99")
        entries = DoubleEntryEngine.create_payment_entry("cash-1", "exp-1", amount, "x")
        assert entries[0]["amount"] is amount
        assert entries[1]["amount"] is amount

    def test_create_invoice_entry_string_amount(self):
        entries = DoubleEntryEngine.create_invoice_entry("ar-1", "rev-1", "100.00", "invoice")
        assert entries[0]["account_id"] == "ar-1"
        assert entries[0]["type"] == EntryType.DEBIT
        assert entries[1]["account_id"] == "rev-1"
        assert entries[1]["type"] == EntryType.CREDIT
        assert entries[0]["amount"] == Decimal("100.00")

    def test_create_invoice_entry_decimal_passthrough(self):
        amount = Decimal("100.00")
        entries = DoubleEntryEngine.create_invoice_entry("ar-1", "rev-1", amount, "invoice")
        assert entries[0]["amount"] is amount
        assert entries[1]["amount"] is amount

    def test_create_bill_entry_string_amount_with_description(self):
        entries = DoubleEntryEngine.create_bill_entry("ap-1", "exp-1", "75.00", "utilities")
        assert entries[0] == {"account_id": "exp-1", "type": EntryType.DEBIT,
                              "amount": Decimal("75.00"), "description": "utilities"}
        assert entries[1] == {"account_id": "ap-1", "type": EntryType.CREDIT,
                              "amount": Decimal("75.00"), "description": "utilities"}

    def test_create_bill_entry_decimal_passthrough(self):
        amount = Decimal("75.00")
        entries = DoubleEntryEngine.create_bill_entry("ap-1", "exp-1", amount, "u")
        assert entries[0]["amount"] is amount
        assert entries[1]["amount"] is amount

    def test_create_payment_for_bill_string_amount(self):
        entries = DoubleEntryEngine.create_payment_for_bill("cash-1", "ap-1", "40.00", "pay")
        assert entries[0] == {"account_id": "ap-1", "type": EntryType.DEBIT,
                              "amount": Decimal("40.00"), "description": "pay"}
        assert entries[1] == {"account_id": "cash-1", "type": EntryType.CREDIT,
                              "amount": Decimal("40.00"), "description": "pay"}

    def test_create_payment_for_bill_decimal_passthrough(self):
        amount = Decimal("40.00")
        entries = DoubleEntryEngine.create_payment_for_bill("cash-1", "ap-1", amount, "pay")
        assert entries[0]["amount"] is amount
        assert entries[1]["amount"] is amount


# ============================================================================
# 2. accounting/models.py — direct unit tests (enum values, defaults, JSON,
#    relationships). Module body is import-time-covered; these exercise the
#    declared behavior so the 100% is earned, not incidental.
# ============================================================================

class TestAccountingEnums:
    def test_account_type_values(self):
        assert [e.value for e in AccountType] == ["asset", "liability", "equity",
                                                  "revenue", "expense"]

    def test_transaction_status_values(self):
        assert [e.value for e in TransactionStatus] == ["pending", "posted",
                                                        "failed", "cancelled"]

    def test_entry_type_values(self):
        assert [e.value for e in EntryType] == ["debit", "credit"]

    def test_entity_type_values(self):
        assert [e.value for e in EntityType] == ["vendor", "customer", "both"]

    def test_bill_status_values(self):
        assert [e.value for e in BillStatus] == ["draft", "open", "paid", "void"]

    def test_invoice_status_values(self):
        assert [e.value for e in InvoiceStatus] == ["draft", "open", "paid",
                                                    "void", "overdue"]

    def test_enums_are_str_subclasses(self):
        assert isinstance(AccountType.ASSET, str)
        assert isinstance(InvoiceStatus.OVERDUE, str)


class TestAccountingModelDefaults:
    """Column defaults are Python-side, applied at flush (not construction).
    Each test flushes through the in-memory SQLite session, then asserts the
    effective defaults."""

    def test_account_defaults(self, memory_db):
        acc = Account(name="Cash", code="1000", type=AccountType.ASSET,
                      workspace_id="ws-1")
        memory_db.add(acc)
        memory_db.flush()
        assert acc.id and len(acc.id) == 36
        assert acc.is_active is True
        assert acc.description is None
        assert acc.parent_id is None
        assert acc.standards_mapping is None
        assert acc.last_audit_at is None
        assert acc.created_at is not None
        assert acc.updated_at is None

    def test_transaction_defaults(self, memory_db):
        tx = Transaction(workspace_id="ws-1",
                         transaction_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
                         source="manual")
        memory_db.add(tx)
        memory_db.flush()
        assert tx.status == TransactionStatus.PENDING
        assert tx.category == "other"
        assert tx.is_intercompany is False
        assert tx.amount is None
        assert tx.external_id is None
        assert tx.metadata_json is None
        assert tx.counterparty_workspace_id is None
        assert tx.project_id is None
        assert tx.milestone_id is None

    def test_journal_entry_defaults(self, memory_db):
        tx = Transaction(workspace_id="ws-1",
                         transaction_date=datetime(2026, 5, 1), source="manual")
        memory_db.add(tx)
        memory_db.flush()
        entry = JournalEntry(transaction_id=tx.id, account_id="a1",
                             type=EntryType.DEBIT, amount=Decimal("10.00"))
        memory_db.add(entry)
        memory_db.flush()
        assert entry.currency == "USD"
        assert entry.description is None

    def test_categorization_proposal_defaults(self, memory_db):
        prop = CategorizationProposal(transaction_id="t1", suggested_account_id="a1",
                                       confidence=0.9)
        memory_db.add(prop)
        memory_db.flush()
        assert prop.is_accepted is None
        assert prop.reasoning is None
        assert prop.reviewed_by is None
        assert prop.reviewed_at is None

    def test_entity_defaults(self, memory_db):
        ent = Entity(workspace_id="ws-1", name="Acme", type=EntityType.VENDOR)
        memory_db.add(ent)
        memory_db.flush()
        assert ent.email is None
        assert ent.phone is None
        assert ent.address is None
        assert ent.tax_id is None

    def test_bill_defaults(self, memory_db):
        bill = Bill(workspace_id="ws-1", vendor_id="v1",
                    issue_date=datetime(2026, 5, 1), due_date=datetime(2026, 6, 1),
                    amount=Decimal("100.00"))
        memory_db.add(bill)
        memory_db.flush()
        assert bill.status == BillStatus.DRAFT
        assert bill.currency == "USD"
        assert bill.bill_number is None
        assert bill.transaction_id is None

    def test_invoice_defaults(self, memory_db):
        inv = Invoice(workspace_id="ws-1", customer_id="c1",
                      issue_date=datetime(2026, 5, 1), due_date=datetime(2026, 6, 1),
                      amount=Decimal("100.00"))
        memory_db.add(inv)
        memory_db.flush()
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.currency == "USD"
        assert inv.invoice_number is None
        assert inv.metadata_json is None

    def test_document_defaults(self, memory_db):
        doc = Document(workspace_id="ws-1", file_path="/tmp/x.pdf", file_name="x.pdf")
        memory_db.add(doc)
        memory_db.flush()
        assert doc.file_type is None
        assert doc.bill_id is None
        assert doc.invoice_id is None
        assert doc.extracted_data is None

    def test_tax_nexus_defaults(self, memory_db):
        nexus = TaxNexus(workspace_id="ws-1", region="California")
        memory_db.add(nexus)
        memory_db.flush()
        assert nexus.tax_type == "Sales Tax"
        assert nexus.is_active is True

    def test_financial_close_defaults(self, memory_db):
        close = FinancialClose(workspace_id="ws-1", period="2026-05")
        memory_db.add(close)
        memory_db.flush()
        assert close.is_closed is False
        assert close.closed_at is None
        assert close.closed_by is None
        assert close.metadata_json is None

    def test_categorization_rule_defaults(self, memory_db):
        rule = CategorizationRule(workspace_id="ws-1", merchant_pattern="Amazon",
                                  target_account_id="a1")
        memory_db.add(rule)
        memory_db.flush()
        assert rule.confidence_weight == 1.0
        assert rule.is_active is True

    def test_budget_defaults(self, memory_db):
        budget = Budget(workspace_id="ws-1", amount=Decimal("500.00"),
                        start_date=datetime(2026, 5, 1), end_date=datetime(2026, 5, 31))
        memory_db.add(budget)
        memory_db.flush()
        assert budget.period == "month"
        assert budget.project_id is None
        assert budget.category_id is None

    def test_json_round_trip_standards_mapping(self, memory_db):
        acc = Account(name="Cash", code="1000", type=AccountType.ASSET,
                      workspace_id="ws-1", standards_mapping={"gaap": "1001",
                                                              "ifrs": "CASH"})
        memory_db.add(acc)
        memory_db.commit()
        fetched = memory_db.query(Account).filter(Account.id == acc.id).one()
        assert fetched.standards_mapping == {"gaap": "1001", "ifrs": "CASH"}

    def test_metadata_json_round_trip_transaction(self, memory_db):
        tx = Transaction(workspace_id="ws-1",
                         transaction_date=datetime(2026, 5, 1),
                         source="bank_feed",
                         metadata_json={"raw": {"amount": 5}})
        memory_db.add(tx)
        memory_db.commit()
        fetched = memory_db.query(Transaction).filter(Transaction.id == tx.id).one()
        assert fetched.metadata_json == {"raw": {"amount": 5}}

    def test_transaction_journal_entry_relationship(self, memory_db):
        tx = Transaction(workspace_id="ws-1",
                         transaction_date=datetime(2026, 5, 1),
                         source="manual")
        memory_db.add(tx)
        memory_db.flush()
        entry = JournalEntry(transaction_id=tx.id, account_id="a1",
                             type=EntryType.DEBIT, amount=Decimal("5.00"))
        memory_db.add(entry)
        memory_db.commit()
        assert tx.journal_entries == [entry]
        assert entry.transaction is tx

    def test_account_entries_relationship(self, memory_db):
        acc = Account(name="Cash", code="1000", type=AccountType.ASSET,
                      workspace_id="ws-1")
        tx = Transaction(workspace_id="ws-1",
                         transaction_date=datetime(2026, 5, 1), source="manual")
        memory_db.add(acc)
        memory_db.add(tx)
        memory_db.flush()
        entry = JournalEntry(transaction_id=tx.id, account_id=acc.id,
                             type=EntryType.CREDIT, amount=Decimal("5.00"))
        memory_db.add(entry)
        memory_db.commit()
        assert entry.account is acc
        assert acc.entries == [entry]

    def test_account_unique_constraint_code_per_workspace(self, memory_db):
        memory_db.add(Account(name="Cash", code="1000", type=AccountType.ASSET,
                              workspace_id="ws-1"))
        memory_db.commit()
        from sqlalchemy.exc import IntegrityError
        memory_db.add(Account(name="Cash2", code="1000", type=AccountType.ASSET,
                              workspace_id="ws-1"))
        with pytest.raises(IntegrityError):
            memory_db.commit()
        memory_db.rollback()

    def test_account_same_code_different_workspace_ok(self, memory_db):
        memory_db.add(Account(name="Cash", code="1000", type=AccountType.ASSET,
                              workspace_id="ws-1"))
        memory_db.add(Account(name="Cash2", code="1000", type=AccountType.ASSET,
                              workspace_id="ws-2"))
        memory_db.commit()
        assert memory_db.query(Account).count() == 2


# ============================================================================
# 3. accounting/routes.py — helpers
# ============================================================================

class TestCheckAccountingEnabled:
    def test_enabled_passes(self, settings_on):
        assert check_accounting_enabled() is None

    def test_disabled_raises_403(self, settings_off):
        with pytest.raises(HTTPException) as ei:
            check_accounting_enabled()
        assert ei.value.status_code == 403
        assert "disabled" in ei.value.detail


class TestValidateFileExtension:
    def test_empty_filename(self):
        with pytest.raises(HTTPException) as ei:
            validate_file_extension("")
        assert ei.value.status_code == 400
        assert ei.value.detail == "No filename provided"

    def test_none_filename(self):
        with pytest.raises(HTTPException) as ei:
            validate_file_extension(None)
        assert ei.value.status_code == 400

    def test_unsafe_filename_sanitizes_to_empty(self):
        with pytest.raises(HTTPException) as ei:
            validate_file_extension("!!!")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Invalid filename after sanitization"

    def test_disallowed_extension(self):
        with pytest.raises(HTTPException) as ei:
            validate_file_extension("invoice.txt")
        assert ei.value.status_code == 400
        assert "'.txt' not allowed" in ei.value.detail
        assert ".pdf" in ei.value.detail

    def test_valid_extension(self):
        assert validate_file_extension("invoice.pdf") == ".pdf"

    def test_uppercase_extension_lowercased(self):
        assert validate_file_extension("INVOICE.PNG") == ".png"

    def test_path_traversal_filename_sanitized(self):
        assert validate_file_extension("../../etc/passwd.pdf") == ".pdf"


class TestValidateFileTypeWithMagicBytes:
    def test_pdf_match(self, tmp_path):
        fp = tmp_path / "doc.pdf"
        fp.write_bytes(b"%PDF-1.7 fake content")
        assert validate_file_type_with_magic_bytes(str(fp), ".pdf") is True
        assert fp.exists()

    def test_png_match(self, tmp_path):
        fp = tmp_path / "img.png"
        fp.write_bytes(b"\x89PNG\r\n\x1a\n data")
        assert validate_file_type_with_magic_bytes(str(fp), ".png") is True

    def test_jpeg_match(self, tmp_path):
        fp = tmp_path / "img.jpg"
        fp.write_bytes(b"\xff\xd8\xff\xe0 jpeg data")
        assert validate_file_type_with_magic_bytes(str(fp), ".jpg") is True

    def test_mismatch_removes_file_and_raises(self, tmp_path):
        fp = tmp_path / "claim.png"
        fp.write_bytes(b"%PDF-1.4 actual pdf")
        with pytest.raises(HTTPException) as ei:
            validate_file_type_with_magic_bytes(str(fp), ".png")
        assert ei.value.status_code == 400
        assert "doesn't match extension" in ei.value.detail
        assert not fp.exists()

    def test_no_magic_match_removes_file_and_raises(self, tmp_path):
        fp = tmp_path / "doc.pdf"
        fp.write_bytes(b"garbage bytes here")
        with pytest.raises(HTTPException) as ei:
            validate_file_type_with_magic_bytes(str(fp), ".pdf")
        assert ei.value.status_code == 400
        assert "magic byte validation failed" in ei.value.detail
        assert not fp.exists()

    def test_read_error_returns_500(self, tmp_path):
        with patch("builtins.open", side_effect=OSError("io error")):
            with pytest.raises(HTTPException) as ei:
                validate_file_type_with_magic_bytes(str(tmp_path / "nope.pdf"), ".pdf")
        assert ei.value.status_code == 500
        assert ei.value.detail == "Error validating file type"

    def test_generic_error_cleans_up_file(self, tmp_path, monkeypatch):
        fp = tmp_path / "doc.pdf"
        fp.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr("accounting.routes.os.path.exists", lambda _p: True)
        with patch("builtins.open", side_effect=OSError("io error")), \
             patch("accounting.routes.os.remove") as rm:
            with pytest.raises(HTTPException) as ei:
                validate_file_type_with_magic_bytes(str(fp), ".pdf")
        assert ei.value.status_code == 500
        rm.assert_called_once()


# ============================================================================
# 3. accounting/routes.py — endpoints
# ============================================================================

class TestGetAccounts:
    def test_success(self, settings_on):
        accs = [
            Account(name="Cash", code="1000", type=AccountType.ASSET, workspace_id="ws-1"),
            Account(name="Revenue", code="4000", type=AccountType.REVENUE, workspace_id="ws-1"),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = accs
        client = make_router_client(db)
        resp = client.get("/api/v1/accounting/accounts", params={"workspace_id": "ws-1"})
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        db.query.return_value.filter.assert_called_once()

    def test_403_disabled(self, settings_off):
        client = make_router_client(MagicMock())
        resp = client.get("/api/v1/accounting/accounts", params={"workspace_id": "ws-1"})
        assert resp.status_code == 403

    def test_401_unauthenticated(self, settings_on):
        client = make_client({get_current_user: auth_fail_override(),
                              get_db: db_override(MagicMock())})
        resp = client.get("/api/v1/accounting/accounts", params={"workspace_id": "ws-1"})
        assert resp.status_code == 401

    def test_422_missing_workspace(self, settings_on):
        client = make_router_client(MagicMock())
        resp = client.get("/api/v1/accounting/accounts")
        assert resp.status_code == 422


class TestUpdateAccountMapping:
    def test_success(self, settings_on):
        account = Account(name="Cash", code="1000", type=AccountType.ASSET,
                          workspace_id="ws-1")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = account
        client = make_router_client(db)
        resp = client.patch(
            "/api/v1/accounting/accounts/acc-1/mapping",
            json={"gaap": "1001", "ifrs": "CASH"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "success",
                               "mapping": {"gaap": "1001", "ifrs": "CASH"}}
        assert account.standards_mapping == {"gaap": "1001", "ifrs": "CASH"}
        db.commit.assert_called_once()

    def test_404_account_not_found(self, settings_on):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_router_client(db)
        resp = client.patch("/api/v1/accounting/accounts/nope/mapping",
                            json={"gaap": "1001"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Account not found"

    def test_403_disabled(self, settings_off):
        client = make_router_client(MagicMock())
        resp = client.patch("/api/v1/accounting/accounts/a1/mapping",
                            json={"gaap": "1001"})
        assert resp.status_code == 403

    def test_422_invalid_body(self, settings_on):
        client = make_router_client(MagicMock())
        resp = client.patch("/api/v1/accounting/accounts/a1/mapping", json=[1, 2])
        assert resp.status_code == 422


class TestGetPendingProposals:
    def test_success(self, settings_on):
        props = [CategorizationProposal(transaction_id="t1", suggested_account_id="a1",
                                        confidence=0.9)]
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = props
        client = make_router_client(db)
        resp = client.get("/api/v1/accounting/proposals", params={"workspace_id": "ws-1"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_403_disabled(self, settings_off):
        client = make_router_client(MagicMock())
        resp = client.get("/api/v1/accounting/proposals", params={"workspace_id": "ws-1"})
        assert resp.status_code == 403


class TestApproveProposal:
    def _client(self, db, accepted):
        with patch("accounting.routes.AICategorizer") as cls:
            cls.return_value.accept_proposal.return_value = accepted
            client = make_router_client(db)
            yield client
        cls.assert_called_once()

    def test_success(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.AICategorizer") as cls:
            cls.return_value.accept_proposal.return_value = True
            client = make_router_client(db)
            resp = client.post("/api/v1/accounting/proposals/prop-1/approve")
            assert resp.status_code == 200
            assert resp.json() == {"status": "success"}
            cls.assert_called_once_with(db)
            cls.return_value.accept_proposal.assert_called_once_with("prop-1", "u-75")

    def test_404_proposal_not_found(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.AICategorizer") as cls:
            cls.return_value.accept_proposal.return_value = False
            client = make_router_client(db)
            resp = client.post("/api/v1/accounting/proposals/nope/approve")
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Proposal not found"

    def test_403_disabled(self, settings_off):
        with patch("accounting.routes.AICategorizer") as cls:
            client = make_router_client(MagicMock())
            resp = client.post("/api/v1/accounting/proposals/prop-1/approve")
            assert resp.status_code == 403
            cls.assert_not_called()


class TestGetCashForecast:
    def test_success(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.FPAService") as cls:
            cls.return_value.generate_13_week_forecast.return_value = {
                "weeks": [{"week": 1, "balance": 100}]
            }
            client = make_router_client(db)
            resp = client.get("/api/v1/accounting/forecast",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 200
            assert resp.json()["weeks"][0]["balance"] == 100
            cls.assert_called_once_with(db)
            cls.return_value.generate_13_week_forecast.assert_called_once_with("ws-1")

    def test_service_exception_500(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.FPAService") as cls:
            cls.return_value.generate_13_week_forecast.side_effect = ValueError("boom")
            client = make_router_client(db)
            resp = client.get("/api/v1/accounting/forecast",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 500

    def test_403_disabled(self, settings_off):
        with patch("accounting.routes.FPAService") as cls:
            client = make_router_client(MagicMock())
            resp = client.get("/api/v1/accounting/forecast",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 403
            cls.assert_not_called()


class TestRunScenario:
    def test_success(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.FPAService") as cls:
            cls.return_value.model_scenario.return_value = {
                "scenario": "hire", "impact": -11000
            }
            client = make_router_client(db)
            resp = client.post(
                "/api/v1/accounting/scenario",
                params={"workspace_id": "ws-1", "scenario_description": "hire an engineer"},
            )
            assert resp.status_code == 200
            assert resp.json()["impact"] == -11000
            cls.return_value.model_scenario.assert_called_once_with(
                "ws-1", "hire an engineer")

    def test_422_missing_scenario_description(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.FPAService"):
            client = make_router_client(db)
            resp = client.post("/api/v1/accounting/scenario",
                               params={"workspace_id": "ws-1"})
            assert resp.status_code == 422

    def test_403_disabled(self, settings_off):
        with patch("accounting.routes.FPAService") as cls:
            client = make_router_client(MagicMock())
            resp = client.post(
                "/api/v1/accounting/scenario",
                params={"workspace_id": "ws-1", "scenario_description": "hire"},
            )
            assert resp.status_code == 403
            cls.assert_not_called()


class TestExportGl:
    def test_success(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.AccountExporter") as cls:
            cls.return_value.export_general_ledger_csv.return_value = (
                "date,description,amount\n2026-05-01,Office,100.00\n"
            )
            client = make_router_client(db)
            resp = client.get("/api/v1/accounting/export/gl",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/csv")
            assert resp.headers["content-disposition"] == \
                "attachment; filename=gl_export_ws-1.csv"
            assert "Office" in resp.text
            cls.assert_called_once_with(db)
            cls.return_value.export_general_ledger_csv.assert_called_once_with("ws-1")

    def test_403_disabled(self, settings_off):
        with patch("accounting.routes.AccountExporter") as cls:
            client = make_router_client(MagicMock())
            resp = client.get("/api/v1/accounting/export/gl",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 403
            cls.assert_not_called()


class TestExportTrialBalance:
    def test_success(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.AccountExporter") as cls:
            cls.return_value.export_trial_balance_json.return_value = {
                "accounts": [{"name": "Cash", "balance": "40.00"}]
            }
            client = make_router_client(db)
            resp = client.get("/api/v1/accounting/export/trial-balance",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 200
            assert resp.json()["accounts"][0]["name"] == "Cash"
            cls.return_value.export_trial_balance_json.assert_called_once_with("ws-1")

    def test_403_disabled(self, settings_off):
        with patch("accounting.routes.AccountExporter") as cls:
            client = make_router_client(MagicMock())
            resp = client.get("/api/v1/accounting/export/trial-balance",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 403
            cls.assert_not_called()


class TestTriggerExternalSync:
    def test_success(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.AccountingSyncManager") as cls:
            cls.return_value.sync_external_transactions = AsyncMock(
                return_value={"synced": 3, "platform": "zoho"})
            client = make_router_client(db)
            resp = client.post(
                "/api/v1/accounting/sync",
                params={"workspace_id": "ws-1", "platform": "zoho"},
                json={"access_token": "tok", "organization_id": "org-1"},
            )
            assert resp.status_code == 200
            assert resp.json()["synced"] == 3
            cls.assert_called_once_with(db)
            cls.return_value.sync_external_transactions.assert_awaited_once_with(
                "ws-1", "zoho", {"access_token": "tok", "organization_id": "org-1"})

    def test_422_missing_platform(self, settings_on):
        with patch("accounting.routes.AccountingSyncManager"):
            client = make_router_client(MagicMock())
            resp = client.post("/api/v1/accounting/sync",
                               params={"workspace_id": "ws-1"},
                               json={})
            assert resp.status_code == 422

    def test_403_disabled(self, settings_off):
        with patch("accounting.routes.AccountingSyncManager") as cls:
            client = make_router_client(MagicMock())
            resp = client.post(
                "/api/v1/accounting/sync",
                params={"workspace_id": "ws-1", "platform": "zoho"},
                json={},
            )
            assert resp.status_code == 403
            cls.assert_not_called()

    def test_service_exception_500(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.AccountingSyncManager") as cls:
            cls.return_value.sync_external_transactions = AsyncMock(
                side_effect=RuntimeError("sync failed"))
            client = make_router_client(db)
            resp = client.post(
                "/api/v1/accounting/sync",
                params={"workspace_id": "ws-1", "platform": "zoho"},
                json={},
            )
            assert resp.status_code == 500


class TestGetAccountingSummary:
    def test_success(self, settings_on):
        db = MagicMock()
        with patch("accounting.routes.AccountingDashboardService") as cls:
            cls.return_value.get_financial_summary.return_value = {
                "cash": Decimal("1000.00"), "total_revenue": Decimal("500.00")
            }
            client = make_router_client(db)
            resp = client.get("/api/v1/accounting/dashboard/summary",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 200
            assert resp.json()["cash"] == 1000.0
            cls.assert_called_once_with(db)
            cls.return_value.get_financial_summary.assert_called_once_with("ws-1")

    def test_403_disabled(self, settings_off):
        with patch("accounting.routes.AccountingDashboardService") as cls:
            client = make_router_client(MagicMock())
            resp = client.get("/api/v1/accounting/dashboard/summary",
                              params={"workspace_id": "ws-1"})
            assert resp.status_code == 403
            cls.assert_not_called()


# ============================================================================
# 3. accounting/routes.py — /bills/upload (secure upload flow)
# ============================================================================

class TestUploadInvoice:
    def _client(self, db=None, tmp_path=None, monkeypatch=None):
        if tmp_path is not None:
            monkeypatch.setattr("accounting.routes.os.getcwd", lambda: str(tmp_path))
        return make_router_client(db or MagicMock())

    def _file(self, content, filename="invoice.pdf"):
        f = MagicMock()
        f.filename = filename
        f.read = AsyncMock(return_value=content)
        return f

    def test_success_pdf(self, settings_on, tmp_path, monkeypatch):
        db = MagicMock()
        with patch("accounting.routes.APService") as cls:
            cls.return_value.process_invoice_document = AsyncMock(
                return_value={"status": "processed", "bill_id": "b-1"})
            client = self._client(db, tmp_path, monkeypatch)
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("invoice.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "processed"
            # doc tracked in DB with the safe uuid filename
            added = [c.args[0] for c in db.add.call_args_list]
            assert len(added) == 1 and isinstance(added[0], Document)
            doc = added[0]
            assert doc.file_name.startswith("u-") is False
            assert doc.file_name.endswith(".pdf")
            assert doc.file_path.startswith(str(tmp_path))
            db.flush.assert_called_once()
            # file written with magic-validated content
            saved = list((tmp_path / "data" / "uploads" / "invoices").glob("*.pdf"))
            assert len(saved) == 1
            # AP service invoked with the tracked document id
            cls.return_value.process_invoice_document.assert_awaited_once_with(
                document_id=doc.id, workspace_id="ws-1",
                expense_account_code="5100")

    def test_success_expense_account_override(self, settings_on, tmp_path, monkeypatch):
        db = MagicMock()
        with patch("accounting.routes.APService") as cls:
            cls.return_value.process_invoice_document = AsyncMock(
                return_value={"status": "processed"})
            client = self._client(db, tmp_path, monkeypatch)
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1", "expense_account_code": "6000"},
                files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
            assert resp.status_code == 200
            doc = db.add.call_args[0][0]
            cls.return_value.process_invoice_document.assert_awaited_once_with(
                document_id=doc.id, workspace_id="ws-1",
                expense_account_code="6000")

    def test_no_filename_400_direct_call(self, settings_on):
        """`if not file.filename` guard — unreachable via multipart (Starlette
        rejects empty filenames with 422 first), so call the endpoint
        function directly with a scripted UploadFile."""
        db = MagicMock()
        f = MagicMock()
        f.filename = None
        f.read = AsyncMock(return_value=b"%PDF-1.4")
        with patch("accounting.routes.APService") as cls:
            with pytest.raises(HTTPException) as ei:
                asyncio.run(routes_mod.upload_invoice(
                    workspace_id="ws-1", file=f, db=db))
            assert ei.value.status_code == 400
            assert ei.value.detail == "No filename provided"
            cls.assert_not_called()

    def test_empty_filename_multipart_422(self, settings_on):
        db = MagicMock()
        client = make_router_client(db)
        with patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": (None, b"%PDF-1.4", "application/pdf")},
            )
            assert resp.status_code == 422
            cls.assert_not_called()

    def test_http_exception_cleanup_when_file_exists(self, settings_on, tmp_path, monkeypatch):
        """Upload's `except HTTPException` cleanup branch: validation raises
        without removing the file (patched) -> endpoint must remove it."""
        db = MagicMock()
        client = self._client(db, tmp_path, monkeypatch)
        with patch("accounting.routes.validate_file_type_with_magic_bytes",
                   side_effect=HTTPException(status_code=400, detail="boom")), \
             patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "boom"
            cls.assert_not_called()
            db.add.assert_not_called()
        upload_dir = tmp_path / "data" / "uploads" / "invoices"
        assert not list(upload_dir.glob("*"))

    def test_disallowed_extension(self, settings_on):
        client = make_router_client(MagicMock())
        with patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("evil.txt", b"hello", "text/plain")},
            )
            assert resp.status_code == 400
            assert "not allowed" in resp.json()["detail"]
            cls.assert_not_called()

    def test_file_too_large_413(self, settings_on, tmp_path, monkeypatch):
        client = self._client(tmp_path=tmp_path, monkeypatch=monkeypatch)
        big = b"x" * (MAX_FILE_SIZE + 1)
        with patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("big.pdf", big, "application/pdf")},
            )
            assert resp.status_code == 413
            assert "File too large" in resp.json()["detail"]
            cls.assert_not_called()

    def test_empty_file_400(self, settings_on, tmp_path, monkeypatch):
        client = self._client(tmp_path=tmp_path, monkeypatch=monkeypatch)
        with patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("empty.pdf", b"", "application/pdf")},
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Empty file"
            cls.assert_not_called()

    def test_magic_bytes_mismatch_400_and_cleanup(self, settings_on, tmp_path, monkeypatch):
        client = self._client(tmp_path=tmp_path, monkeypatch=monkeypatch)
        with patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("claim.png", b"%PDF-1.4 sneaky", "image/png")},
            )
            assert resp.status_code == 400
            assert "doesn't match extension" in resp.json()["detail"]
            cls.assert_not_called()
        upload_dir = tmp_path / "data" / "uploads" / "invoices"
        assert not list(upload_dir.glob("*"))

    def test_unknown_magic_bytes_400(self, settings_on, tmp_path, monkeypatch):
        client = self._client(tmp_path=tmp_path, monkeypatch=monkeypatch)
        with patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("invoice.pdf", b"no magic here", "application/pdf")},
            )
            assert resp.status_code == 400
            assert "magic byte validation failed" in resp.json()["detail"]
            cls.assert_not_called()
        upload_dir = tmp_path / "data" / "uploads" / "invoices"
        assert not list(upload_dir.glob("*"))

    def test_magic_validation_error_500_and_cleanup(self, settings_on, tmp_path, monkeypatch):
        db = MagicMock()
        client = self._client(db, tmp_path, monkeypatch)
        real_open = open
        state = {"n": 0}

        def fake_open(*args, **kwargs):
            state["n"] += 1
            if state["n"] >= 2:
                raise OSError("read failure")
            return real_open(*args, **kwargs)

        with patch("builtins.open", side_effect=fake_open), \
             patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
            assert resp.status_code == 500
            assert resp.json()["detail"] == "Error validating file type"
            cls.assert_not_called()
            db.add.assert_not_called()
        upload_dir = tmp_path / "data" / "uploads" / "invoices"
        assert not list(upload_dir.glob("*"))

    def test_ap_service_error_500_cleanup(self, settings_on, tmp_path, monkeypatch):
        db = MagicMock()
        client = self._client(db, tmp_path, monkeypatch)
        with patch("accounting.routes.APService") as cls:
            cls.return_value.process_invoice_document = AsyncMock(
                side_effect=RuntimeError("ocr failed"))
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
            assert resp.status_code == 500
            assert resp.json()["detail"] == "Internal error"
        upload_dir = tmp_path / "data" / "uploads" / "invoices"
        assert not list(upload_dir.glob("*"))

    def test_403_disabled(self, settings_off, tmp_path, monkeypatch):
        client = self._client(tmp_path=tmp_path, monkeypatch=monkeypatch)
        with patch("accounting.routes.APService") as cls:
            resp = client.post(
                "/api/v1/accounting/bills/upload",
                data={"workspace_id": "ws-1"},
                files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
            assert resp.status_code == 403
            cls.assert_not_called()

    def test_422_missing_form_fields(self, settings_on):
        client = make_router_client(MagicMock())
        with patch("accounting.routes.APService"):
            resp = client.post("/api/v1/accounting/bills/upload")
            assert resp.status_code == 422
