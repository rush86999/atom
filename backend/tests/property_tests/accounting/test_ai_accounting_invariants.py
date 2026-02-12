"""
Property-Based Tests for AI Accounting Engine - Critical Financial Business Logic

Tests financial transaction invariants:
- Transaction ingestion and categorization
- Chart of Accounts learning and consistency
- Confidence scoring thresholds
- Posting and approval workflows
- Audit trail integrity
- Ledger integration
- Financial accuracy and correctness
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from uuid import uuid4
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from core.ai_accounting_engine import (
    AIAccountingEngine,
    Transaction,
    TransactionStatus,
    TransactionSource,
    ChartOfAccountsEntry
)


class TestTransactionIngestionInvariants:
    """Tests for transaction ingestion invariants"""

    @given(
        amount=st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=1, max_size=200, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '),
        merchant=st.one_of(st.none(), st.text(min_size=1, max_size=100))
    )
    @settings(max_examples=50)
    def test_transaction_ingestion_preserves_data(self, amount, description, merchant):
        """Test that transaction ingestion preserves all data"""
        engine = AIAccountingEngine()
        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            merchant=merchant
        )

        result = engine.ingest_transaction(tx)

        assert result.id == tx.id, "Transaction ID must be preserved"
        assert result.amount == amount, "Amount must be preserved"
        assert result.description == description, "Description must be preserved"
        assert result.merchant == merchant, "Merchant must be preserved"
        assert result.date == tx.date, "Date must be preserved"

    @given(
        transactions=st.lists(
            st.fixed_dictionaries({
                'amount': st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
                'description': st.text(min_size=1, max_size=100),
                'merchant': st.one_of(st.none(), st.text(min_size=1, max_size=50))
            }),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_bulk_ingestion_count_matches(self, transactions):
        """Test that bulk ingestion returns correct count"""
        engine = AIAccountingEngine()

        tx_data = []
        for i, tx_dict in enumerate(transactions):
            tx_data.append({
                'id': f'tx_{i}',
                'date': datetime.now().isoformat(),
                'amount': tx_dict['amount'],
                'description': tx_dict['description'],
                'merchant': tx_dict.get('merchant'),
                'source': 'bank'
            })

        results = engine.ingest_bank_feed(tx_data)

        assert len(results) == len(tx_data), "Bulk ingestion count must match input count"


class TestCategorizationInvariants:
    """Tests for transaction categorization invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ '),
        merchant=st.text(min_size=3, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ')
    )
    @settings(max_examples=50)
    def test_categorization_confidence_bounds(self, amount, description, merchant):
        """Test that categorization confidence is always in valid range"""
        engine = AIAccountingEngine()
        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            merchant=merchant
        )

        result = engine.ingest_transaction(tx)

        assert 0.0 <= result.confidence <= 1.0, "Confidence must be in [0, 1]"
        assert result.category_id is not None or result.confidence == 0.0, "Uncategorized must have 0 confidence"

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100),
        merchant=st.text(min_size=3, max_size=50)
    )
    @settings(max_examples=50)
    def test_categorization_status_consistency(self, amount, description, merchant):
        """Test that categorization status is consistent with confidence"""
        engine = AIAccountingEngine()
        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            merchant=merchant
        )

        result = engine.ingest_transaction(tx)

        # High confidence should be CATEGORIZED
        if result.confidence >= AIAccountingEngine.CONFIDENCE_THRESHOLD:
            assert result.status == TransactionStatus.CATEGORIZED, "High confidence should be CATEGORIZED"
        else:
            assert result.status == TransactionStatus.REVIEW_REQUIRED, "Low confidence should be REVIEW_REQUIRED"

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100),
        merchant=st.text(min_size=3, max_size=50)
    )
    @settings(max_examples=50)
    def test_categorization_reasoning_provided(self, amount, description, merchant):
        """Test that categorization provides reasoning when confidence > 0"""
        engine = AIAccountingEngine()
        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            merchant=merchant
        )

        result = engine.ingest_transaction(tx)

        if result.confidence > 0.0:
            assert result.reasoning is not None, "Categorized transactions should have reasoning"
            assert len(result.reasoning) > 0, "Reasoning should not be empty"


class TestChartOfAccountsInvariants:
    """Tests for Chart of Accounts invariants"""

    @given(
        account_id=st.text(min_size=4, max_size=10, alphabet='0123456789'),
        name=st.text(min_size=3, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ '),
        account_type=st.sampled_from(['asset', 'liability', 'equity', 'revenue', 'expense'])
    )
    @settings(max_examples=50)
    def test_chart_of_accounts_entry_validity(self, account_id, name, account_type):
        """Test that Chart of Accounts entries are valid"""
        entry = ChartOfAccountsEntry(
            account_id=account_id,
            name=name,
            type=account_type
        )

        assert entry.account_id == account_id, "Account ID must be set"
        assert entry.name == name, "Name must be set"
        assert entry.type in ['asset', 'liability', 'equity', 'revenue', 'expense'], "Type must be valid"
        assert isinstance(entry.keywords, list), "Keywords must be a list"
        assert isinstance(entry.merchant_patterns, list), "Merchant patterns must be a list"

    @given(
        keywords=st.lists(
            st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            min_size=0,
            max_size=10
        ),
        merchant_patterns=st.lists(
            st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=50)
    def test_chart_of_accounts_patterns_are_lists(self, keywords, merchant_patterns):
        """Test that pattern fields are always lists"""
        entry = ChartOfAccountsEntry(
            account_id="9999",
            name="Test Account",
            type="expense",
            keywords=keywords,
            merchant_patterns=merchant_patterns
        )

        assert isinstance(entry.keywords, list), "Keywords must be a list"
        assert isinstance(entry.merchant_patterns, list), "Merchant patterns must be a list"
        assert all(isinstance(k, str) for k in entry.keywords), "All keywords must be strings"
        assert all(isinstance(m, str) for m in entry.merchant_patterns), "All merchant patterns must be strings"


class TestConfidenceThresholdInvariants:
    """Tests for confidence threshold invariants"""

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_confidence_threshold_constant(self, confidence):
        """Test that confidence threshold is constant and reasonable"""
        engine = AIAccountingEngine()

        assert engine.CONFIDENCE_THRESHOLD == 0.85, "Confidence threshold should be 0.85"
        assert 0.0 < engine.CONFIDENCE_THRESHOLD < 1.0, "Threshold should be between 0 and 1"

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_high_confidence_auto_posts(self, amount, description):
        """Test that transactions above threshold don't require review"""
        engine = AIAccountingEngine()

        # Create a transaction that should match a pattern
        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=f"rent payment {description}",
            merchant="Landlord"
        )

        result = engine.ingest_transaction(tx)

        # If confidence is high enough, should be CATEGORIZED not REVIEW_REQUIRED
        if result.confidence >= engine.CONFIDENCE_THRESHOLD:
            assert result.status == TransactionStatus.CATEGORIZED, "High confidence should auto-categorize"


class TestLearningInvariants:
    """Tests for learning system invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100),
        merchant=st.text(min_size=3, max_size=50),
        category_id=st.text(min_size=4, max_size=10, alphabet='0123456789')
    )
    @settings(max_examples=50)
    def test_learning_updates_transaction(self, amount, description, merchant, category_id):
        """Test that learning updates transaction categorization"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            merchant=merchant
        )

        engine.ingest_transaction(tx)

        # Learn from user categorization (only if account exists)
        if category_id in engine._chart_of_accounts:
            original_confidence = tx.confidence
            original_status = tx.status

            engine.learn_categorization(tx.id, category_id, "test_user")

            assert tx.category_id == category_id, "Category ID should be updated"
            assert tx.confidence == 1.0, "Confidence should be 1.0 after learning"
            assert tx.status == TransactionStatus.CATEGORIZED, "Status should be CATEGORIZED"
            assert tx.reviewed_by == "test_user", "Reviewed by should be set"

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100),
        merchant=st.text(min_size=3, max_size=50)
    )
    @settings(max_examples=50)
    def test_learning_builds_history(self, amount, description, merchant):
        """Test that learning builds merchant history"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            merchant=merchant
        )

        engine.ingest_transaction(tx)

        # Use a valid account ID
        valid_account_id = "6100"  # Rent account
        engine.learn_categorization(tx.id, valid_account_id, "test_user")

        merchant_key = merchant.lower()
        if merchant_key in engine._category_history:
            assert valid_account_id in engine._category_history[merchant_key], "Category should be in history"


class TestPostingInvariants:
    """Tests for posting workflow invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_cannot_post_review_required(self, amount, description):
        """Test that review-required transactions cannot be posted"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            status=TransactionStatus.REVIEW_REQUIRED,
            confidence=0.5
        )

        engine._transactions[tx.id] = tx

        result = engine.post_transaction(tx.id)

        assert result is False, "Should not post review-required transaction"
        assert tx.status == TransactionStatus.REVIEW_REQUIRED, "Status should remain REVIEW_REQUIRED"

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_posting_updates_timestamp(self, amount, description):
        """Test that posting sets posted_at timestamp"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            status=TransactionStatus.CATEGORIZED,
            confidence=0.9
        )

        engine._transactions[tx.id] = tx

        before_post = datetime.now()
        result = engine.post_transaction(tx.id)

        if result:
            assert tx.status == TransactionStatus.POSTED, "Status should be POSTED"
            assert tx.posted_at is not None, "posted_at should be set"
            assert tx.posted_at >= before_post, "posted_at should be after post time"


class TestAuditTrailInvariants:
    """Tests for audit trail invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_audit_entry_created_on_ingestion(self, amount, description):
        """Test that ingestion creates audit entry"""
        engine = AIAccountingEngine()

        initial_log_count = len(engine._audit_log)

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description
        )

        engine.ingest_transaction(tx)

        assert len(engine._audit_log) > initial_log_count, "Audit log should have new entry"

    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_audit_log_chronological(self, amounts):
        """Test that audit log entries are chronological"""
        engine = AIAccountingEngine()

        for i, amount in enumerate(amounts):
            tx = Transaction(
                id=f"tx_{i}",
                date=datetime.now(),
                amount=amount,
                description=f"Transaction {i}"
            )
            engine.ingest_transaction(tx)

        # Verify timestamps are non-decreasing
        for i in range(1, len(engine._audit_log)):
            current_time = engine._audit_log[i]['timestamp']
            prev_time = engine._audit_log[i-1]['timestamp']
            assert current_time >= prev_time, "Audit log should be chronological"

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_audit_log_contains_required_fields(self, amount, description):
        """Test that audit log entries contain all required fields"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description
        )

        engine.ingest_transaction(tx)

        if engine._audit_log:
            entry = engine._audit_log[-1]
            assert 'timestamp' in entry, "Audit entry must have timestamp"
            assert 'action' in entry, "Audit entry must have action"
            assert 'transaction_id' in entry, "Audit entry must have transaction_id"
            assert 'confidence' in entry, "Audit entry must have confidence"
            assert 'details' in entry, "Audit entry must have details"


class TestFinancialAccuracyInvariants:
    """Tests for financial accuracy and correctness"""

    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_transaction_amounts_preserved(self, amounts):
        """Test that all transaction amounts are preserved accurately"""
        engine = AIAccountingEngine()

        original_amounts = {}
        for i, amount in enumerate(amounts):
            tx_id = f"tx_{i}"
            tx = Transaction(
                id=tx_id,
                date=datetime.now(),
                amount=amount,
                description=f"Transaction {i}"
            )
            original_amounts[tx_id] = amount
            engine.ingest_transaction(tx)

        # Verify all amounts preserved
        for tx_id, original_amount in original_amounts.items():
            stored_tx = engine._transactions.get(tx_id)
            if stored_tx:
                assert stored_tx.amount == original_amount, f"Amount for {tx_id} must be preserved"

    @given(
        amount=st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_debits_and_credits_distinct(self, amount, description):
        """Test that debits (negative) and credits (positive) are distinct"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description
        )

        engine.ingest_transaction(tx)

        # Amount should be preserved exactly (no rounding)
        assert tx.amount == amount, "Amount must be exact (no rounding)"

        # Sign should be preserved
        if amount > 0:
            assert tx.amount > 0, "Positive amount must stay positive"
        elif amount < 0:
            assert tx.amount < 0, "Negative amount must stay negative"

    @given(
        amounts=st.lists(
            st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_total_balance_calculable(self, amounts):
        """Test that total balance can be calculated from all transactions"""
        engine = AIAccountingEngine()

        for i, amount in enumerate(amounts):
            tx = Transaction(
                id=f"tx_{i}",
                date=datetime.now(),
                amount=amount,
                description=f"Transaction {i}"
            )
            engine.ingest_transaction(tx)

        # Calculate balance
        total_balance = sum(tx.amount for tx in engine._transactions.values())

        # Balance should be finite (no NaN or infinity)
        assert abs(total_balance) < float('inf'), "Total balance must be finite"
        assert not any(str(total_balance).startswith('nan') for _ in [0]), "Total balance must not be NaN"


class TestReviewQueueInvariants:
    """Tests for review queue management"""

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_low_confidence_goes_to_review(self, amount, description):
        """Test that low confidence transactions go to review queue"""
        engine = AIAccountingEngine()

        # Create a transaction with no matching patterns
        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description="xyz abc 123 random text",  # Unlikely to match anything
            merchant="UnknownMerchant"
        )

        result = engine.ingest_transaction(tx)

        if result.confidence < engine.CONFIDENCE_THRESHOLD:
            assert tx.id in engine._pending_review, "Low confidence should be in review queue"
            pending = engine.get_pending_review()
            assert any(p.id == tx.id for p in pending), "Transaction should be in pending review list"

    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_review_queue_count_matches(self, amounts):
        """Test that review queue count matches low-confidence transactions"""
        engine = AIAccountingEngine()

        for i, amount in enumerate(amounts):
            tx = Transaction(
                id=f"tx_{i}",
                date=datetime.now(),
                amount=amount,
                description=f"transaction {i} xyz",  # Low confidence
            )
            engine.ingest_transaction(tx)

        # Count low confidence transactions
        low_confidence_count = sum(
            1 for tx in engine._transactions.values()
            if tx.confidence < engine.CONFIDENCE_THRESHOLD
        )

        pending_review = engine.get_pending_review()

        assert len(pending_review) == low_confidence_count, "Review queue count should match low confidence count"


class TestSourceInvariants:
    """Tests for transaction source invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100),
        source=st.sampled_from(['bank', 'credit_card', 'stripe', 'paypal', 'manual'])
    )
    @settings(max_examples=50)
    def test_transaction_source_preserved(self, amount, description, source):
        """Test that transaction source is preserved"""
        engine = AIAccountingEngine()

        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description,
            source=TransactionSource(source)
        )

        result = engine.ingest_transaction(tx)

        assert result.source == TransactionSource(source), "Source must be preserved"
        assert result.source.value == source, "Source value must match"

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100)
    )
    @settings(max_examples=50)
    def test_default_source_is_bank(self, amount, description):
        """Test that default source is BANK"""
        tx = Transaction(
            id=str(uuid4()),
            date=datetime.now(),
            amount=amount,
            description=description
        )

        assert tx.source == TransactionSource.BANK, "Default source should be BANK"


class TestDateInvariants:
    """Tests for date-related invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=5, max_size=100),
        days_offset=st.integers(min_value=-365, max_value=365)
    )
    @settings(max_examples=50)
    def test_transaction_date_preserved(self, amount, description, days_offset):
        """Test that transaction date is preserved"""
        engine = AIAccountingEngine()

        tx_date = datetime.now() + timedelta(days=days_offset)
        tx = Transaction(
            id=str(uuid4()),
            date=tx_date,
            amount=amount,
            description=description
        )

        result = engine.ingest_transaction(tx)

        assert result.date == tx_date, "Transaction date must be preserved"

    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_posted_at_after_created_at(self, amounts):
        """Test that posted_at timestamp is always after or equal to created date"""
        engine = AIAccountingEngine()

        for i, amount in enumerate(amounts):
            tx = Transaction(
                id=f"tx_{i}",
                date=datetime.now(),
                amount=amount,
                description=f"Transaction {i}"
            )
            engine.ingest_transaction(tx)

        # Post all high confidence transactions
        posted = engine.auto_post_high_confidence()

        # Verify posted_at is after or equal to transaction date
        for tx in engine._transactions.values():
            if tx.posted_at is not None:
                assert tx.posted_at >= tx.date, "posted_at should be after or equal to transaction date"
