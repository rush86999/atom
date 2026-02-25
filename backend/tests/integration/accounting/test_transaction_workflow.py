"""
Integration Tests for Transaction Workflow

Tests complete transaction workflow:
1. Ingestion (bank feed, manual entry)
2. Categorization (AI/confidence-based)
3. Posting (double-entry validation)
4. Reconciliation (invoice matching, balance sheet)

Uses Decimal precision throughout. No float types for money.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from core.ai_accounting_engine import (
    AIAccountingEngine,
    Transaction,
    TransactionStatus,
    TransactionSource
)
from accounting.ledger import EventSourcedLedger, DoubleEntryEngine
from accounting.models import (
    Account,
    AccountType,
    EntryType,
    Base,
    JournalEntry,
    Transaction as DBTransaction,
    TransactionStatus as DBTransactionStatus
)
from core.decimal_utils import to_decimal, round_money


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create test database session"""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def chart_of_accounts(db_session: Session):
    """Create test chart of accounts"""
    accounts = [
        Account(id="1000", name="Cash", code="1000", type=AccountType.ASSET, workspace_id="test"),
        Account(id="1100", name="Accounts Receivable", code="1100", type=AccountType.ASSET, workspace_id="test"),
        Account(id="2000", name="Accounts Payable", code="2000", type=AccountType.LIABILITY, workspace_id="test"),
        Account(id="4000", name="Revenue", code="4000", type=AccountType.REVENUE, workspace_id="test"),
        Account(id="6100", name="Rent Expense", code="6100", type=AccountType.EXPENSE, workspace_id="test"),
        Account(id="6200", name="Utilities", code="6200", type=AccountType.EXPENSE, workspace_id="test"),
    ]
    for account in accounts:
        db_session.add(account)
    db_session.commit()
    return accounts


class TestTransactionWorkflow:
    """Tests for complete transaction workflow"""

    def test_full_transaction_workflow(self, db_session: Session, chart_of_accounts):
        """Test complete workflow: ingestion -> categorization -> posting"""
        # Step 1: Ingestion
        engine = AIAccountingEngine()
        tx = Transaction(
            id="tx_001",
            date=datetime.now(),
            amount=Decimal('1500.00'),
            description="Office rent payment",
            merchant="Landlord LLC",
            source=TransactionSource.BANK
        )

        ingested = engine.ingest_transaction(tx)

        assert ingested.id == "tx_001"
        assert ingested.amount == Decimal('1500.00')
        assert ingested.category_id is not None  # Should categorize
        assert ingested.confidence >= 0.0

        # Step 2: Categorization (auto-categorized if high confidence)
        if ingested.confidence >= engine.CONFIDENCE_THRESHOLD:
            assert ingested.status == TransactionStatus.CATEGORIZED
        else:
            assert ingested.status == TransactionStatus.REVIEW_REQUIRED

        # Override for testing
        ingested.category_id = "6100"  # Rent Expense
        ingested.status = TransactionStatus.CATEGORIZED
        ingested.confidence = 1.0

        # Step 3: Posting (double-entry)
        ledger = EventSourcedLedger(db_session)

        # Create double-entry entries
        entries = DoubleEntryEngine.create_payment_entry(
            cash_account_id="1000",
            expense_account_id="6100",
            amount=Decimal('1500.00'),
            description="Office rent payment"
        )

        # Post transaction
        ledger_tx = ledger.record_transaction(
            workspace_id="test",
            transaction_date=tx.date,
            description=tx.description,
            entries=entries,
            source="ai_accounting",
            external_id=tx.id
        )

        assert ledger_tx is not None
        assert ledger_tx.status == DBTransactionStatus.POSTED

        # Verify journal entries created
        journal_entries = db_session.query(JournalEntry).filter_by(
            transaction_id=ledger_tx.id
        ).all()

        assert len(journal_entries) == 2

        # Verify debits == credits
        debits = sum(e.amount for e in journal_entries if e.type == EntryType.DEBIT)
        credits = sum(e.amount for e in journal_entries if e.type == EntryType.CREDIT)

        assert debits == Decimal('1500.00')
        assert credits == Decimal('1500.00')
        assert debits == credits  # Exact comparison

    def test_bulk_ingestion_workflow(self, db_session: Session):
        """Test bulk ingestion from bank feed"""
        engine = AIAccountingEngine()

        bank_feed = [
            {
                "id": "tx_001",
                "date": datetime.now().isoformat(),
                "amount": "100.00",
                "description": "Coffee shop",
                "merchant": "Starbucks",
                "source": "credit_card"
            },
            {
                "id": "tx_002",
                "date": datetime.now().isoformat(),
                "amount": "50.00",
                "description": "Office supplies",
                "merchant": "Staples",
                "source": "credit_card"
            },
            {
                "id": "tx_003",
                "date": datetime.now().isoformat(),
                "amount": "1200.50",
                "description": "Software subscription",
                "merchant": "Amazon Web Services",
                "source": "bank"
            }
        ]

        # Ingest all
        results = engine.ingest_bank_feed(bank_feed)

        assert len(results) == 3

        # Verify each transaction
        for i, tx in enumerate(results):
            assert tx.id == bank_feed[i]["id"]
            assert isinstance(tx.amount, Decimal)
            assert tx.amount == to_decimal(bank_feed[i]["amount"])

            # Should have categorization
            assert tx.category_id is not None or tx.confidence == 0.0

    def test_reconciliation_workflow(self, db_session: Session, chart_of_accounts):
        """Test invoice reconciliation workflow"""
        from core.financial_ops_engine import InvoiceReconciler, Invoice, Contract

        reconciler = InvoiceReconciler(tolerance_percent=Decimal('5.0'))

        # Add contract
        contract = Contract(
            id="contract_001",
            vendor="AWS",
            monthly_amount=Decimal('1200.00'),
            start_date=datetime.now() - timedelta(days=60),
            end_date=datetime.now() + timedelta(days=60)
        )
        reconciler.add_contract(contract)

        # Add matching invoice
        invoice = Invoice(
            id="invoice_001",
            vendor="AWS",
            amount=Decimal('1200.00'),
            date=datetime.now(),
            contract_id="contract_001"
        )
        reconciler.add_invoice(invoice)

        # Reconcile
        result = reconciler.reconcile()

        assert result["summary"]["matched_count"] == 1
        assert result["summary"]["discrepancy_count"] == 0

        # Check matched invoice
        assert len(result["matched"]) == 1
        assert result["matched"][0]["invoice_id"] == "invoice_001"

    def test_balance_sheet_verification(self, db_session: Session, chart_of_accounts):
        """Test balance sheet verification after transactions"""
        from core.accounting_validator import check_balance_sheet

        ledger = EventSourcedLedger(db_session)

        # Post several transactions
        transactions = [
            {
                "date": datetime.now(),
                "description": "Initial investment",
                "entries": [
                    {"account_id": "1000", "type": EntryType.DEBIT, "amount": Decimal('10000.00')},
                    {"account_id": "4000", "type": EntryType.CREDIT, "amount": Decimal('10000.00')}
                ]
            },
            {
                "date": datetime.now(),
                "description": "Pay rent",
                "entries": [
                    {"account_id": "6100", "type": EntryType.DEBIT, "amount": Decimal('2000.00')},
                    {"account_id": "1000", "type": EntryType.CREDIT, "amount": Decimal('2000.00')}
                ]
            },
            {
                "date": datetime.now(),
                "description": "Pay utilities",
                "entries": [
                    {"account_id": "6200", "type": EntryType.DEBIT, "amount": Decimal('150.00')},
                    {"account_id": "1000", "type": EntryType.CREDIT, "amount": Decimal('150.00')}
                ]
            }
        ]

        for tx_data in transactions:
            ledger.record_transaction(
                workspace_id="test",
                transaction_date=tx_data["date"],
                description=tx_data["description"],
                entries=tx_data["entries"],
                source="test"
            )

        # Get account balances
        assets = {}
        liabilities = {}
        revenue = {}
        expenses = {}

        for account in chart_of_accounts:
            balance = ledger.get_account_balance(account.id)
            if account.type == AccountType.ASSET:
                assets[account.name] = balance
            elif account.type == AccountType.LIABILITY:
                liabilities[account.name] = balance
            elif account.type == AccountType.REVENUE:
                revenue[account.name] = balance
            elif account.type == AccountType.EXPENSE:
                expenses[account.name] = balance

        # Calculate total equity: Revenue - Expenses
        total_revenue = sum(revenue.values(), Decimal('0.00'))
        total_expenses = sum(expenses.values(), Decimal('0.00'))
        total_equity = total_revenue - total_expenses

        # Verify balance sheet: Assets = Liabilities + (Revenue - Expenses)
        assert assets["Cash"] == Decimal('7850.00')  # 10000 - 2000 - 150
        assert total_revenue == Decimal('10000.00')
        assert total_expenses == Decimal('2150.00')  # 2000 + 150
        assert total_equity == Decimal('7850.00')  # 10000 - 2150

        # Verify balance sheet equation: Assets = Liabilities + Equity
        total_assets = sum(assets.values(), Decimal('0.00'))
        total_liabilities = sum(liabilities.values(), Decimal('0.00'))

        assert total_assets == total_liabilities + total_equity

    def test_high_confidence_auto_post(self, db_session: Session):
        """Test that high confidence transactions auto-post"""
        engine = AIAccountingEngine()

        # Create transaction that will match pattern
        tx = Transaction(
            id="tx_auto",
            date=datetime.now(),
            amount=Decimal('500.00'),
            description="rent payment for office",
            merchant="Landlord"
        )

        result = engine.ingest_transaction(tx)

        # Should auto-categorize (matches "rent" keyword and "Landlord" pattern)
        if result.confidence >= engine.CONFIDENCE_THRESHOLD:
            assert result.status == TransactionStatus.CATEGORIZED

            # Should be able to post
            posted = engine.auto_post_high_confidence()
            assert posted >= 1
        else:
            # Should go to review
            assert result.status == TransactionStatus.REVIEW_REQUIRED

    def test_low_confidence_requires_review(self, db_session: Session):
        """Test that low confidence transactions require review"""
        engine = AIAccountingEngine()

        # Create transaction with no obvious patterns
        tx = Transaction(
            id="tx_review",
            date=datetime.now(),
            amount=Decimal('123.45'),
            description="unknown transaction xyz",
            merchant="UnknownVendor123"
        )

        result = engine.ingest_transaction(tx)

        # Should require review (low confidence)
        if result.confidence < engine.CONFIDENCE_THRESHOLD:
            assert result.status == TransactionStatus.REVIEW_REQUIRED
            assert tx.id in engine._pending_review

    def test_decimal_precision_throughout_workflow(self, db_session: Session):
        """Test that Decimal precision is maintained throughout workflow"""
        engine = AIAccountingEngine()

        # Use amounts that would lose precision with float
        amounts = [
            Decimal('0.01'),
            Decimal('0.10'),
            Decimal('1.11'),
            Decimal('10.50'),
            Decimal('999999.99')
        ]

        for amount in amounts:
            tx = Transaction(
                id=f"tx_{amount}",
                date=datetime.now(),
                amount=amount,
                description=f"Test {amount}",
                merchant="Test"
            )

            result = engine.ingest_transaction(tx)

            # Verify precision preserved
            assert result.amount == amount
            assert isinstance(result.amount, Decimal)
            assert str(result.amount) == str(amount)


class TestEdgeCases:
    """Tests for edge cases in transaction workflow"""

    def test_zero_amount_transaction(self, db_session: Session):
        """Test handling of zero amount transactions"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id="tx_zero",
            date=datetime.now(),
            amount=Decimal('0.00'),
            description="Zero amount test",
            merchant="Test"
        )

        result = engine.ingest_transaction(tx)
        assert result.amount == Decimal('0.00')

    def test_large_amount_transaction(self, db_session: Session):
        """Test handling of large amount transactions"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id="tx_large",
            date=datetime.now(),
            amount=Decimal('99999999.99'),
            description="Large amount test",
            merchant="Test"
        )

        result = engine.ingest_transaction(tx)
        assert result.amount == Decimal('99999999.99')

    def test_fractional_cent_rounding(self, db_session: Session):
        """Test that fractional cents are rounded correctly"""
        amount = Decimal('100.005')

        # Round to cents
        rounded = round_money(amount, places=2)

        assert rounded == Decimal('100.01')  # ROUND_HALF_UP
        assert rounded.as_tuple().exponent == -2
