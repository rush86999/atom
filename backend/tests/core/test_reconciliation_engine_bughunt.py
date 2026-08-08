"""
Bug-hunt tests for core/reconciliation_engine.py (TDD).

Each test documents a genuine, net-new bug. Tests are written FIRST and must
fail for the right reason before the source is fixed.
"""

from datetime import datetime

import pytest

from core.reconciliation_engine import (
    ReconciliationEngine,
    ReconciliationEntry,
    ReconciliationStatus,
    AnomalyType,
)


@pytest.fixture
def engine():
    return ReconciliationEngine()


class TestReconciliationEngineBugs:
    """Net-new bugs in reconciliation_engine."""

    def test_reconcile_is_idempotent_for_discrepancies(self, engine):
        """BUG: reconcile() is not idempotent for DISCREPANCY entries.

        When a bank entry matches a ledger entry with an amount difference
        > $0.01, the bank entry is marked DISCREPANCY but the ledger entry
        is left PENDING and the bank entry is NOT skipped on re-run (only
        MATCHED entries are skipped). Re-running reconcile() therefore
        re-discovers the same discrepancy and appends a duplicate record to
        the report, inflating discrepancy counts on every reconciliation pass.
        """
        bank = ReconciliationEntry(
            id="b1", source="bank", date=datetime(2026, 1, 1),
            amount=100.50, description="Test Vendor",
        )
        ledger = ReconciliationEntry(
            id="l1", source="ledger", date=datetime(2026, 1, 1),
            amount=100.00, description="Test Vendor",
        )
        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        r1 = engine.reconcile()
        assert len(r1["discrepancies"]) == 1

        # Second run must not re-report the same discrepancy.
        r2 = engine.reconcile()
        assert len(r2["discrepancies"]) == 0

    def test_detect_anomalies_is_idempotent(self, engine):
        """BUG: detect_anomalies() is not idempotent. Each call appends
        freshly-detected anomalies to self._anomalies without de-duplicating
        against already-stored anomalies, so calling it twice doubles the
        stored anomaly list and inflates SOX/anomaly reports.
        """
        # Two near-identical transactions within the 48h window -> duplicate.
        engine.add_bank_entry(ReconciliationEntry(
            id="b1", source="bank", date=datetime(2026, 1, 1, 10, 0),
            amount=100.0, description="Acme Corp"))
        engine.add_bank_entry(ReconciliationEntry(
            id="b2", source="bank", date=datetime(2026, 1, 1, 14, 0),
            amount=100.0, description="Acme Corp"))

        engine.detect_anomalies()
        stored_after_1 = len(engine._anomalies)

        engine.detect_anomalies()
        stored_after_2 = len(engine._anomalies)

        # The duplicate anomaly should be stored exactly once.
        assert stored_after_2 == stored_after_1

    def test_reconcile_handles_none_description_without_crash(self, engine):
        """BUG: _description_similarity calls desc.lower() without a None
        guard. A ReconciliationEntry with description=None (the dataclass
        field has no validator forbidding None) crashes reconcile() and
        detect_anomalies() with AttributeError, taking down the whole
        reconciliation run for a single malformed entry.
        """
        bank = ReconciliationEntry(
            id="b1", source="bank", date=datetime(2026, 1, 1),
            amount=100.0, description=None,
        )
        ledger = ReconciliationEntry(
            id="l1", source="ledger", date=datetime(2026, 1, 1),
            amount=100.0, description="Test Vendor",
        )
        engine.add_bank_entry(bank)
        engine.add_ledger_entry(ledger)

        # Must not raise AttributeError.
        result = engine.reconcile()
        assert "status" in result

    def test_description_similarity_none_inputs_return_zero(self, engine):
        """BUG (same root cause): _description_similarity(None, None) and
        _description_similarity(None, 'x') must return 0.0, not crash.
        """
        assert engine._description_similarity(None, "x") == 0.0
        assert engine._description_similarity("x", None) == 0.0
        assert engine._description_similarity(None, None) == 0.0
