"""
TDD bug-hunt tests for core.apar_engine and core.formula_memory.

Each test reproduces a specific, real defect in a pure-logic module.
Tests are minimal, isolated, and avoid DB/network where the module is pure logic.
Tests assert the CORRECT behaviour, so they FAIL because of the bug.

Run:
    venv/bin/python -m pytest tests/core/test_apar_formula_bughunt.py -q
"""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from core.apar_engine import (
    APAREngine,
    APInvoice,
    ARInvoice,
    InvoiceStatus,
    ReminderTone,
)
from core.formula_memory import FormulaMemoryManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _db_session_context(session):
    """Adapt a mock session to the get_db_session() context manager."""
    yield session


# ===============================================================================
# apar_engine.py
# ===============================================================================

class TestAPAREngineBugs:
    """Reproduced bugs in core.apar_engine."""

    @pytest.fixture
    def engine(self):
        return APAREngine()

    def test_get_upcoming_payments_excludes_past_due(self, engine):
        """BUG: apar_engine get_upcoming_payments includes already-past-due invoices.

        The filter is `due_date <= cutoff`, which is true for any invoice whose
        due date has ALREADY passed (e.g. due 5 days ago). "Upcoming payments"
        therefore returns past-due approved invoices, when it should only return
        invoices due in the future window (now < due_date <= now+days).
        """
        past_due = APInvoice(
            id="ap-past",
            vendor="Late Vendor",
            amount=100.00,
            due_date=datetime.now() - timedelta(days=5),  # already overdue
            line_items=[],
            status=InvoiceStatus.APPROVED,
        )
        future = APInvoice(
            id="ap-future",
            vendor="On Time Vendor",
            amount=200.00,
            due_date=datetime.now() + timedelta(days=3),
            line_items=[],
            status=InvoiceStatus.APPROVED,
        )
        engine._ap_invoices["ap-past"] = past_due
        engine._ap_invoices["ap-future"] = future

        upcoming = engine.get_upcoming_payments(days=7)

        upcoming_ids = {inv.id for inv in upcoming}
        assert "ap-past" not in upcoming_ids, (
            "A past-due invoice (due 5 days ago) must not appear in upcoming "
            "payments, but it does because the filter only checks due_date <= cutoff."
        )
        assert "ap-future" in upcoming_ids

    def test_generate_invoice_rejects_non_positive_amount(self, engine):
        """BUG: apar_engine AR generate_invoice does not validate invoice amount.

        intake_invoice (AP) rejects non-positive amounts, but generate_invoice
        (AR) accepts any value including negative amounts. A negative AR
        invoice silently corrupts get_collection_summary's total_outstanding
        (sum becomes negative) and lets a customer "owe" a negative balance.
        """
        with pytest.raises(ValueError):
            engine.generate_invoice("contract", {
                "customer": "Shady Customer",
                "amount": -1000.00,
                "due_date": "2026-06-15",
                "line_items": [],
            })

    def test_generate_invoice_rejects_zero_amount(self, engine):
        """BUG: apar_engine AR generate_invoice accepts a zero-amount invoice.

        Companion to the negative-amount bug. A zero invoice is meaningless and
        AP-side rejects it (<= 0); AR-side should behave the same.
        """
        with pytest.raises(ValueError):
            engine.generate_invoice("contract", {
                "customer": "Zero Customer",
                "amount": 0.0,
                "due_date": "2026-06-15",
                "line_items": [],
            })

    def test_collection_summary_excludes_negative_outstanding(self, engine):
        """BUG: apar_engine negative AR invoice distorts collection summary.

        Originally a demonstration of the downstream impact of the missing AR
        amount validation: a negative receivable drove total_outstanding below
        zero. Now that generate_invoice rejects non-positive amounts (the root-
        cause fix), a negative invoice cannot be created at all, so the
        collection summary can never go negative from this path. This test
        verifies the upstream rejection that protects the summary.
        """
        # A negative AR invoice must be rejected at creation — previously it
        # was accepted and corrupted get_collection_summary().
        with pytest.raises(ValueError):
            engine.generate_invoice("contract", {
                "customer": "Shady Customer",
                "amount": -1000.00,
                "due_date": "2026-06-15",
                "line_items": [],
            })

        # With no negative invoice able to exist, the summary stays sane.
        summary = engine.get_collection_summary()
        assert summary["total_outstanding"] >= 0

    def test_get_overdue_invoices_is_idempotent(self, engine):
        """BUG: apar_engine get_overdue_invoices mutates state and is not idempotent.

        Calling get_overdue_invoices() flips each SENT+past-due invoice to
        OVERDUE. A second call returns an empty list because no invoice is
        SENT any more, so the previously-returned overdue invoices "disappear"
        from a getter. A read-only lookup should not lose results on repeat.
        """
        overdue_inv = ARInvoice(
            id="ar-od",
            customer="Slow Payer",
            amount=1000.00,
            due_date=datetime.now() - timedelta(days=15),
            line_items=[],
            status=InvoiceStatus.SENT,
        )
        engine._ar_invoices["ar-od"] = overdue_inv

        first_call = engine.get_overdue_invoices()
        second_call = engine.get_overdue_invoices()

        first_ids = {inv.id for inv in first_call}
        second_ids = {inv.id for inv in second_call}
        assert first_ids == second_ids == {"ar-od"}, (
            "Second call returned {} but should match the first call {} — the "
            "getter mutates SENT->OVERDUE so repeat lookups lose the data."
            .format(second_ids, first_ids)
        )


# ===============================================================================
# formula_memory.py
# ===============================================================================

class TestFormulaMemoryBugs:
    """Reproduced bugs in core.formula_memory."""

    @pytest.fixture
    def manager(self):
        """FormulaMemoryManager with a mocked LanceDB handler."""
        m = FormulaMemoryManager(workspace_id="bughunt")
        m._lancedb = Mock()
        m._lancedb.search.return_value = []
        m._initialized = True
        return m

    def test_search_returns_score_where_higher_means_better(self, manager):
        """BUG: formula_memory search_formulas returns raw _distance as 'score'.

        LanceDB _distance is a DISTANCE metric: lower == more similar
        (0 == identical). The field is labelled 'score', for which the
        universal convention is higher == better. So the best match ends up
        with the smallest 'score'. A consumer sorting by score desc will put
        the worst match first. score should be a similarity (e.g. 1-distance)
        or the field should be renamed.
        """
        manager._lancedb.search.return_value = [
            {
                "text": "best match card",
                "metadata": json.dumps(
                    {"formula_id": "f_best", "name": "Best", "domain": "math"}
                ),
                "_distance": 0.05,  # very similar
            },
            {
                "text": "worst match card",
                "metadata": json.dumps(
                    {"formula_id": "f_worst", "name": "Worst", "domain": "math"}
                ),
                "_distance": 0.95,  # barely related
            },
        ]

        results = manager.search_formulas(query="something")

        best = next(r for r in results if r["id"] == "f_best")
        worst = next(r for r in results if r["id"] == "f_worst")
        assert best["score"] > worst["score"], (
            f"Best match should have a higher score than worst match, but got "
            f"best={best['score']} worst={worst['score']} because raw LanceDB "
            "distance is returned verbatim under the 'score' key."
        )

    def test_delete_formula_purges_vector_card(self, manager):
        """BUG: formula_memory delete_formula never deletes the LanceDB card.

        The SQL row is deleted, but the vector "Rich Formula Card" in LanceDB
        is left in place (the delete branch is a `pass` with a TODO comment).
        After deletion the card is still returned by search_formulas, leaking
        stale data and referencing a formula_id that no longer exists.
        """
        mock_row = Mock()
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_row

        mock_table = Mock()
        manager._lancedb.get_table.return_value = mock_table

        with patch(
            "core.database.get_db_session",
            return_value=_db_session_context(mock_session),
        ):
            result = manager.delete_formula("formula_123")

        assert result is True
        # The vector card MUST be removed from LanceDB alongside the SQL row.
        mock_table.delete.assert_called(), (
            "delete_formula removed the SQL row but left the LanceDB formula "
            "card in place (the LanceDB delete branch is a no-op `pass`)."
        )
