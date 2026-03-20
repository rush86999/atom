"""
Comprehensive test coverage for ReconciliationEngine.

Tests cover:
- Reconciliation execution (matching bank to ledger)
- Transaction matching (amount, date, description)
- Anomaly detection (unusual amounts, duplicates, missing)
- Reconciliation reporting (discrepancies, unmatched)
- Confidence scoring for journal entries
- Vendor history tracking
- Error handling and edge cases

Target: 60%+ coverage (98+ lines of 164 total)
"""
import pytest
from datetime import datetime, timedelta
from typing import List

from core.reconciliation_engine import (
    ReconciliationEngine,
    ReconciliationEntry,
    Anomaly,
    AnomalyType,
    ReconciliationStatus,
    EntryConfidence
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def engine():
    """Fresh reconciliation engine for each test."""
    return ReconciliationEngine()


@pytest.fixture
def sample_bank_entry():
    """Sample bank entry for testing."""
    return ReconciliationEntry(
        id="bank-1",
        source="bank",
        date=datetime(2026, 3, 15),
        amount=100.00,
        description="Amazon Web Services"
    )


@pytest.fixture
def sample_ledger_entry():
    """Sample ledger entry for testing."""
    return ReconciliationEntry(
        id="ledger-1",
        source="ledger",
        date=datetime(2026, 3, 15),
        amount=100.00,
        description="Amazon Web Services"
    )


# =============================================================================
# TestReconciliationEngine - Core Reconciliation
# =============================================================================

class TestReconciliationEngine:
    """Test core reconciliation engine functionality."""

    def test_add_bank_entry(self, engine, sample_bank_entry):
        """Test adding a bank entry."""
        engine.add_bank_entry(sample_bank_entry)

        assert "bank-1" in engine._bank_entries
        assert engine._bank_entries["bank-1"].amount == 100.00
        assert engine._bank_entries["bank-1"].description == "Amazon Web Services"

    def test_add_ledger_entry(self, engine, sample_ledger_entry):
        """Test adding a ledger entry."""
        engine.add_ledger_entry(sample_ledger_entry)

        assert "ledger-1" in engine._ledger_entries
        assert engine._ledger_entries["ledger-1"].amount == 100.00

    def test_reconcile_perfect_match(self, engine, sample_bank_entry, sample_ledger_entry):
        """Test reconciliation with perfect match."""
        engine.add_bank_entry(sample_bank_entry)
        engine.add_ledger_entry(sample_ledger_entry)

        result = engine.reconcile()

        assert result["matched_count"] == 1
        assert len(result["unmatched_bank"]) == 0
        assert len(result["unmatched_ledger"]) == 0
        assert len(result["discrepancies"]) == 0
        assert result["status"] == "reconciled"

        # Verify entries marked as matched
        assert engine._bank_entries["bank-1"].status == ReconciliationStatus.MATCHED
        assert engine._ledger_entries["ledger-1"].status == ReconciliationStatus.MATCHED
        assert engine._bank_entries["bank-1"].matched_with == "ledger-1"
        assert engine._ledger_entries["ledger-1"].matched_with == "bank-1"

    def test_reconcile_unmatched_bank_entry(self, engine, sample_bank_entry):
        """Test reconciliation with unmatched bank entry."""
        engine.add_bank_entry(sample_bank_entry)
        # No ledger entry added

        result = engine.reconcile()

        assert result["matched_count"] == 0
        assert len(result["unmatched_bank"]) == 1
        assert "bank-1" in result["unmatched_bank"]

    def test_reconcile_unmatched_ledger_entry(self, engine, sample_ledger_entry):
        """Test reconciliation with unmatched ledger entry."""
        engine.add_ledger_entry(sample_ledger_entry)
        # No bank entry added

        result = engine.reconcile()

        assert result["matched_count"] == 0
        assert len(result["unmatched_ledger"]) == 1
        assert "ledger-1" in result["unmatched_ledger"]

    def test_reconcile_with_discrepancy(self, engine):
        """Test reconciliation with amount discrepancy."""
        bank_entry = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.50,
            description="Test Vendor"
        )
        ledger_entry = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test Vendor"
        )

        engine.add_bank_entry(bank_entry)
        engine.add_ledger_entry(ledger_entry)

        result = engine.reconcile()

        assert result["matched_count"] == 0
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["bank_id"] == "bank-1"
        assert result["discrepancies"][0]["ledger_id"] == "ledger-1"
        assert result["discrepancies"][0]["difference"] == 0.50

        # Verify status
        assert engine._bank_entries["bank-1"].status == ReconciliationStatus.DISCREPANCY
        assert engine._bank_entries["bank-1"].discrepancy_amount == 0.50

    def test_reconcile_multiple_entries(self, engine):
        """Test reconciliation with multiple entries."""
        # Add 3 matched pairs
        for i in range(3):
            bank = ReconciliationEntry(
                id=f"bank-{i}",
                source="bank",
                date=datetime(2026, 3, 15),
                amount=50.00 * (i + 1),
                description=f"Vendor {i}"
            )
            ledger = ReconciliationEntry(
                id=f"ledger-{i}",
                source="ledger",
                date=datetime(2026, 3, 15),
                amount=50.00 * (i + 1),
                description=f"Vendor {i}"
            )
            engine.add_bank_entry(bank)
            engine.add_ledger_entry(ledger)

        result = engine.reconcile()

        assert result["matched_count"] == 3
        assert len(result["unmatched_bank"]) == 0
        assert len(result["unmatched_ledger"]) == 0

    def test_reconcile_already_matched_entries_skipped(self, engine, sample_bank_entry, sample_ledger_entry):
        """Test that already matched entries are skipped."""
        # Mark entries as already matched
        sample_bank_entry.status = ReconciliationStatus.MATCHED
        sample_ledger_entry.status = ReconciliationStatus.MATCHED

        engine.add_bank_entry(sample_bank_entry)
        engine.add_ledger_entry(sample_ledger_entry)

        result = engine.reconcile()

        # Should not match again
        assert result["matched_count"] == 0

    def test_reconcile_respects_rounding_tolerance(self, engine):
        """Test reconciliation respects rounding tolerance (0.01)."""
        bank_entry = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.005,  # Rounds to 100.01
            description="Test"
        )
        ledger_entry = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )

        engine.add_bank_entry(bank_entry)
        engine.add_ledger_entry(ledger_entry)

        result = engine.reconcile()

        # Difference is 0.005, within 0.01 tolerance - should match
        assert result["matched_count"] == 1


# =============================================================================
# TestReconciliationMatching - Transaction Matching Logic
# =============================================================================

class TestReconciliationMatching:
    """Test transaction matching algorithms."""

    def test_match_by_amount(self, engine):
        """Test matching entries by amount."""
        bank = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Amazon"
        )
        ledger = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Amazon"
        )

        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        match = engine._find_match(bank, engine._ledger_entries)

        assert match == "ledger-1"

    def test_match_by_date_tolerance(self, engine):
        """Test date matching within 5-day tolerance."""
        bank = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )
        ledger = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 20),  # 5 days later
            amount=100.00,
            description="Test"
        )

        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        match = engine._find_match(bank, engine._ledger_entries)

        # Should match within 5-day tolerance
        assert match == "ledger-1"

    def test_no_match_date_outside_tolerance(self, engine):
        """Test no match when date outside 5-day tolerance."""
        bank = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )
        ledger = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 25),  # 10 days later
            amount=100.00,
            description="Test"
        )

        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        match = engine._find_match(bank, engine._ledger_entries)

        # Should not match (>5 days)
        assert match is None

    def test_match_by_description_similarity(self, engine):
        """Test matching by description word overlap."""
        bank = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Amazon Web Services AWS"
        )
        ledger = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Amazon AWS Cloud"
        )

        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        match = engine._find_match(bank, engine._ledger_entries)

        # Should match based on description similarity
        assert match == "ledger-1"

    def test_no_match_low_description_similarity(self, engine):
        """Test no match with low description similarity."""
        bank = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Amazon Web Services"
        )
        ledger = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Microsoft Azure"
        )

        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        match = engine._find_match(bank, engine._ledger_entries)

        # Should not match (low similarity)
        assert match is None

    def test_no_match_amount_outside_tolerance(self, engine):
        """Test no match when amount outside 1% tolerance."""
        bank = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )
        ledger = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 15),
            amount=102.00,  # 2% difference
            description="Test"
        )

        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        match = engine._find_match(bank, engine._ledger_entries)

        # Should not match (>1% difference)
        assert match is None


# =============================================================================
# TestAnomalyDetection - Anomaly Detection
# =============================================================================

class TestAnomalyDetection:
    """Test anomaly detection capabilities."""

    def test_detect_unusual_amounts(self, engine):
        """Test detection of unusually large amounts."""
        # Build vendor history: normal amounts around $50
        vendor = "Test Vendor"
        for i in range(10):
            entry = ReconciliationEntry(
                id=f"bank-{i}",
                source="bank",
                date=datetime(2026, 3, 10 + i),
                amount=50.00 + (i % 3) * 5,  # $50, $55, $60 pattern
                description=vendor
            )
            engine.add_bank_entry(entry)

        # Add unusual amount
        unusual_entry = ReconciliationEntry(
            id="bank-unusual",
            source="bank",
            date=datetime(2026, 3, 20),
            amount=500.00,  # Much higher than normal
            description=vendor
        )
        engine.add_bank_entry(unusual_entry)

        anomalies = engine.detect_anomalies()

        # Should detect unusual amount
        unusual_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.UNUSUAL_AMOUNT]
        assert len(unusual_anomalies) > 0
        assert "bank-unusual" in unusual_anomalies[0].transaction_ids

    def test_detect_duplicate_transactions(self, engine):
        """Test detection of duplicate transactions."""
        # Add two similar transactions within time window
        entry1 = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15, 10, 0),
            amount=100.00,
            description="Amazon Web Services"
        )
        entry2 = ReconciliationEntry(
            id="bank-2",
            source="bank",
            date=datetime(2026, 3, 15, 14, 0),  # 4 hours later
            amount=100.00,
            description="Amazon Web Services"
        )

        engine.add_bank_entry(entry1)
        engine.add_bank_entry(entry2)

        anomalies = engine.detect_anomalies()

        # Should detect duplicate
        dup_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.DUPLICATE_TRANSACTION]
        assert len(dup_anomalies) > 0
        assert "bank-1" in dup_anomalies[0].transaction_ids
        assert "bank-2" in dup_anomalies[0].transaction_ids

    def test_detect_duplicates_outside_time_window(self, engine):
        """Test no duplicate detection outside time window."""
        # Add two transactions with same amount but far apart
        entry1 = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 1),
            amount=100.00,
            description="Test"
        )
        entry2 = ReconciliationEntry(
            id="bank-2",
            source="bank",
            date=datetime(2026, 3, 15),  # 14 days later
            amount=100.00,
            description="Test"
        )

        engine.add_bank_entry(entry1)
        engine.add_bank_entry(entry2)

        anomalies = engine.detect_anomalies()

        # Should not detect as duplicate (outside 48-hour window)
        dup_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.DUPLICATE_TRANSACTION]
        assert len(dup_anomalies) == 0

    def test_detect_missing_transactions(self, engine):
        """Test detection of missing ledger entries."""
        # Add old unmatched bank entry
        old_entry = ReconciliationEntry(
            id="bank-old",
            source="bank",
            date=datetime(2026, 3, 1),  # More than 3 days ago
            amount=100.00,
            description="Test Vendor"
        )
        engine.add_bank_entry(old_entry)

        anomalies = engine.detect_anomalies()

        # Should detect missing transaction
        missing_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.MISSING_TRANSACTION]
        assert len(missing_anomalies) > 0
        assert "bank-old" in missing_anomalies[0].transaction_ids

    def test_anomaly_confidence_scoring(self, engine):
        """Test confidence scores for anomalies."""
        # Build history for vendor
        vendor = "Test Vendor"
        for i in range(5):
            entry = ReconciliationEntry(
                id=f"bank-{i}",
                source="bank",
                date=datetime(2026, 3, 10 + i),
                amount=50.00,
                description=vendor
            )
            engine.add_bank_entry(entry)

        # Add unusual amount (high z-score)
        unusual = ReconciliationEntry(
            id="bank-unusual",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=1000.00,  # Very unusual
            description=vendor
        )
        engine.add_bank_entry(unusual)

        anomalies = engine.detect_anomalies()
        unusual_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.UNUSUAL_AMOUNT]

        # Should have high confidence for extreme z-score
        assert len(unusual_anomalies) > 0
        assert unusual_anomalies[0].confidence > 0.7

    def test_get_unresolved_anomalies(self, engine):
        """Test getting only unresolved anomalies."""
        anomaly1 = Anomaly(
            id="anomaly-1",
            anomaly_type=AnomalyType.UNUSUAL_AMOUNT,
            severity="high",
            description="Test",
            transaction_ids=["bank-1"],
            confidence=0.9,
            suggested_action="Review"
        )
        anomaly2 = Anomaly(
            id="anomaly-2",
            anomaly_type=AnomalyType.DUPLICATE_TRANSACTION,
            severity="medium",
            description="Test",
            transaction_ids=["bank-2"],
            confidence=0.8,
            suggested_action="Review",
            resolved=True
        )

        engine._anomalies = [anomaly1, anomaly2]

        unresolved = engine.get_anomalies(unresolved_only=True)

        assert len(unresolved) == 1
        assert unresolved[0].id == "anomaly-1"

    def test_resolve_anomaly(self, engine):
        """Test resolving an anomaly."""
        anomaly = Anomaly(
            id="anomaly-1",
            anomaly_type=AnomalyType.UNUSUAL_AMOUNT,
            severity="high",
            description="Test",
            transaction_ids=["bank-1"],
            confidence=0.9,
            suggested_action="Review",
            resolved=False
        )

        engine._anomalies = [anomaly]
        engine.resolve_anomaly("anomaly-1")

        assert engine._anomalies[0].resolved is True


# =============================================================================
# TestConfidenceScoring - Entry Confidence Scoring
# =============================================================================

class TestConfidenceScoring:
    """Test confidence scoring for journal entries."""

    def test_score_entry_confidence_with_sources(self, engine):
        """Test scoring with multiple data sources."""
        entry = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )
        engine.add_bank_entry(entry)

        # Match it to ledger
        entry.status = ReconciliationStatus.MATCHED

        confidence = engine.score_entry_confidence(
            entry_id="bank-1",
            sources=["bank_feed", "invoice"],
            reasoning="Matched to invoice #12345"
        )

        assert confidence.entry_id == "bank-1"
        assert confidence.confidence_percent > 50  # Should have good score with 2 sources + match
        assert len(confidence.data_sources) == 2

    def test_score_entry_confidence_no_sources(self, engine):
        """Test scoring with no data sources."""
        entry = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )
        engine.add_bank_entry(entry)

        confidence = engine.score_entry_confidence(
            entry_id="bank-1",
            sources=[],
            reasoning="No sources"
        )

        # Low confidence without sources or match
        assert confidence.confidence_percent < 20

    def test_score_entry_confidence_discrepancy(self, engine):
        """Test scoring for entry with discrepancy."""
        entry = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test",
            status=ReconciliationStatus.DISCREPANCY
        )
        engine.add_bank_entry(entry)

        confidence = engine.score_entry_confidence(
            entry_id="bank-1",
            sources=["bank_feed"],
            reasoning="Has discrepancy"
        )

        # Lower score for discrepancy vs match
        assert confidence.confidence_percent < 50

    def test_get_stored_confidence(self, engine):
        """Test retrieving stored confidence scores."""
        entry = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )
        engine.add_bank_entry(entry)

        # Score once
        engine.score_entry_confidence(
            entry_id="bank-1",
            sources=["bank_feed"],
            reasoning="Test"
        )

        # Retrieve from storage
        stored = engine._entry_confidence.get("bank-1")

        assert stored is not None
        assert stored.entry_id == "bank-1"


# =============================================================================
# TestVendorHistory - Vendor History Tracking
# =============================================================================

class TestVendorHistory:
    """Test vendor history tracking."""

    def test_vendor_history_tracked(self, engine, sample_bank_entry):
        """Test that vendor amounts are tracked."""
        engine.add_bank_entry(sample_bank_entry)

        assert "amazon web services" in engine._vendor_history
        assert 100.00 in engine._vendor_history["amazon web services"]

    def test_vendor_history_case_insensitive(self, engine):
        """Test vendor matching is case-insensitive."""
        entry1 = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Amazon Web Services"
        )
        entry2 = ReconciliationEntry(
            id="bank-2",
            source="bank",
            date=datetime(2026, 3, 16),
            amount=150.00,
            description="amazon web services"  # Lowercase
        )

        engine.add_bank_entry(entry1)
        engine.add_bank_entry(entry2)

        # Should track under same key
        assert len(engine._vendor_history["amazon web services"]) == 2
        assert 100.00 in engine._vendor_history["amazon web services"]
        assert 150.00 in engine._vendor_history["amazon web services"]

    def test_vendor_history_amounts_abs_value(self, engine):
        """Test that amounts are stored as absolute values."""
        entry = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=-100.00,  # Negative (credit)
            description="Test Vendor"
        )

        engine.add_bank_entry(entry)

        # Should store absolute value
        assert 100.0 in engine._vendor_history["test vendor"]


# =============================================================================
# TestReconciliationReporting - Reporting and Status
# =============================================================================

class TestReconciliationReporting:
    """Test reconciliation reporting and status tracking."""

    def test_reconciliation_status_pending(self, engine, sample_bank_entry):
        """Test entries start with PENDING status."""
        engine.add_bank_entry(sample_bank_entry)

        assert sample_bank_entry.status == ReconciliationStatus.PENDING

    def test_reconciliation_report_includes_discrepancy_details(self, engine):
        """Test discrepancy details in report."""
        bank = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.50,
            description="Test"
        )
        ledger = ReconciliationEntry(
            id="ledger-1",
            source="ledger",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )

        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        result = engine.reconcile()

        assert len(result["discrepancies"]) == 1
        discrepancy = result["discrepancies"][0]
        assert discrepancy["bank_id"] == "bank-1"
        assert discrepancy["ledger_id"] == "ledger-1"
        assert discrepancy["bank_amount"] == 100.50
        assert discrepancy["ledger_amount"] == 100.00
        assert discrepancy["difference"] == 0.50

    def test_anomaly_severity_levels(self, engine):
        """Test anomaly severity classification."""
        # Build vendor history
        vendor = "Test Vendor"
        for i in range(5):
            entry = ReconciliationEntry(
                id=f"bank-{i}",
                source="bank",
                date=datetime(2026, 3, 10 + i),
                amount=50.00,
                description=vendor
            )
            engine.add_bank_entry(entry)

        # Add extremely unusual amount (high severity)
        unusual = ReconciliationEntry(
            id="bank-unusual",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=1000.00,
            description=vendor
        )
        engine.add_bank_entry(unusual)

        anomalies = engine.detect_anomalies()
        unusual_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.UNUSUAL_AMOUNT]

        # High z-score should trigger high severity
        assert len(unusual_anomalies) > 0
        assert unusual_anomalies[0].severity in ["high", "medium"]

    def test_anomaly_suggested_actions(self, engine):
        """Test anomalies include suggested actions."""
        entry1 = ReconciliationEntry(
            id="bank-1",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )
        entry2 = ReconciliationEntry(
            id="bank-2",
            source="bank",
            date=datetime(2026, 3, 15),
            amount=100.00,
            description="Test"
        )

        engine.add_bank_entry(entry1)
        engine.add_bank_entry(entry2)

        anomalies = engine.detect_anomalies()

        if anomalies:
            # All anomalies should have suggested actions
            for anomaly in anomalies:
                assert len(anomaly.suggested_action) > 0
