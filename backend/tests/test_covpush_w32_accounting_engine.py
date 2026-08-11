"""Coverage wave 32 — core/ai_accounting_engine.py (TDD, pure in-memory).

Drives the accounting engine end-to-end: CSV-injection sanitization,
transaction ingestion + confidence-based status, bank-feed bulk ingest,
all four categorization strategies (merchant pattern / historical /
keyword / uncategorized), learning, posting + auto-post, review queue,
update with re-categorization, delete, audit trail, GL CSV + trial
balance exports, 13-week forecast (history + fallback), scenario
parsing (expense/hire/lose-client/revenue, $10,000 + k-suffix parsing)
and the ledger integration paths (mock / DB / ImportError / failure) —
no DB, no network, zero spend.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.ai_accounting_engine import (
    AIAccountingEngine,
    Transaction,
    TransactionSource,
    TransactionStatus,
    _sanitize_csv_cell,
)


def make_engine():
    return AIAccountingEngine()


def make_tx(**kw):
    defaults = dict(
        id="tx-1", date=datetime(2026, 7, 15), amount=Decimal("100.00"),
        description="test transaction", merchant=None,
        source=TransactionSource.BANK)
    defaults.update(kw)
    return Transaction(**defaults)


class TestSanitizeCsvCell:
    @pytest.mark.parametrize("value", ["=cmd()", "+sum", "-1+1", "@import", "\tstab", "\rcr"])
    def test_injection_prefixed(self, value):
        assert _sanitize_csv_cell(value) == "'" + value

    def test_safe_values_unchanged(self):
        assert _sanitize_csv_cell("normal") == "normal"
        assert _sanitize_csv_cell("") == ""
        assert _sanitize_csv_cell(5) == 5
        assert _sanitize_csv_cell(None) is None
        assert _sanitize_csv_cell(Decimal("1.5")) == Decimal("1.5")


class TestIngest:
    def test_high_confidence_categorized(self):
        engine = make_engine()
        tx = make_tx(merchant="Slack", description="subscription")
        result = engine.ingest_transaction(tx)
        assert result.status == TransactionStatus.CATEGORIZED
        assert result.category_id == "6300"  # Software
        assert len(engine.get_audit_log()) == 1

    def test_low_confidence_review_required(self):
        engine = make_engine()
        tx = make_tx(merchant="Mystery Shop", description="misc stuff")
        result = engine.ingest_transaction(tx)
        assert result.status == TransactionStatus.REVIEW_REQUIRED
        assert tx.id in engine._pending_review
        assert result.category_id is None

    def test_bank_feed_bulk(self):
        engine = make_engine()
        txs = [
            {"id": "b1", "date": "2026-07-01", "amount": "50.00",
             "description": "rent payment", "merchant": "Landlord",
             "source": "bank"},
            {"id": "b2", "date": datetime(2026, 7, 2), "amount": "20.00",
             "description": "gas bill", "source": "credit_card"},
        ]
        results = engine.ingest_bank_feed(txs)
        assert len(results) == 2
        assert results[0].id == "b1"
        assert results[0].amount == Decimal("50.00")
        assert results[1].source == TransactionSource.CREDIT_CARD
        assert isinstance(results[1].date, datetime)

    def test_bank_feed_default_id(self):
        engine = make_engine()
        results = engine.ingest_bank_feed([
            {"date": "2026-07-01", "amount": "5", "description": "x"}])
        assert results[0].id.startswith("tx_")


class TestCategorization:
    def test_merchant_pattern_wins(self):
        engine = make_engine()
        tx = make_tx(merchant="AWS", description="cloud usage")
        cat_id, name, conf, reason = engine._categorize_transaction(tx)
        assert cat_id == "6300"
        assert conf == 0.95
        assert "Merchant" in reason

    def test_historical_categorization(self):
        engine = make_engine()
        engine._category_history["corner_store"] = ["6700", "6700", "6700"]
        tx = make_tx(merchant="corner_store", description="supplies")
        cat_id, name, conf, reason = engine._categorize_transaction(tx)
        assert cat_id == "6700"
        assert conf == 0.90
        assert "Historical" in reason

    def test_historical_sparse(self):
        engine = make_engine()
        engine._category_history["corner_store"] = ["6700"]
        tx = make_tx(merchant="corner_store", description="supplies")
        cat_id, name, conf, reason = engine._categorize_transaction(tx)
        assert conf == 0.75

    def test_keyword_matching(self):
        engine = make_engine()
        tx = make_tx(merchant=None, description="electric power")
        cat_id, name, conf, reason = engine._categorize_transaction(tx)
        assert cat_id == "6200"  # Utilities
        assert 0.70 <= conf <= 0.85
        assert "Keywords matched" in reason

    def test_uncategorized(self):
        engine = make_engine()
        tx = make_tx(merchant="Random", description="zzz nothing matches")
        cat_id, name, conf, reason = engine._categorize_transaction(tx)
        assert cat_id is None
        assert name == "Uncategorized"
        assert conf == 0.0


class TestLearning:
    def test_learn_missing_tx(self):
        engine = make_engine()
        engine.learn_categorization("ghost", "6100", "u1")  # no crash

    def test_learn_missing_account(self):
        engine = make_engine()
        engine._transactions["tx-1"] = make_tx()
        engine.learn_categorization("tx-1", "9999", "u1")  # no crash

    def test_learn_success(self):
        engine = make_engine()
        tx = make_tx(merchant="Landlord", description="rent")
        engine._transactions["tx-1"] = tx
        engine._pending_review.append("tx-1")
        engine.learn_categorization("tx-1", "6100", "u1")
        assert tx.category_id == "6100"
        assert tx.confidence == 1.0
        assert tx.status == TransactionStatus.CATEGORIZED
        assert tx.reviewed_by == "u1"
        assert "tx-1" not in engine._pending_review
        assert engine._category_history["landlord"] == ["6100"]


class TestPosting:
    def test_post_missing(self):
        engine = make_engine()
        assert engine.post_transaction("ghost") is False

    def test_post_review_required_no_user(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.REVIEW_REQUIRED)
        engine._transactions["tx-1"] = tx
        assert engine.post_transaction("tx-1") is False

    def test_post_success_with_user(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.REVIEW_REQUIRED)
        engine._transactions["tx-1"] = tx
        engine._pending_review.append("tx-1")
        assert engine.post_transaction("tx-1", user_id="u1") is True
        assert tx.status == TransactionStatus.POSTED
        assert tx.reviewed_by == "u1"
        assert "tx-1" not in engine._pending_review

    def test_post_success_system(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.CATEGORIZED)
        engine._transactions["tx-1"] = tx
        assert engine.post_transaction("tx-1") is True
        assert tx.posted_at is not None

    def test_auto_post_high_confidence(self):
        engine = make_engine()
        engine._transactions["a"] = make_tx(
            id="a", status=TransactionStatus.CATEGORIZED, confidence=0.95)
        engine._transactions["b"] = make_tx(
            id="b", status=TransactionStatus.CATEGORIZED, confidence=0.4)
        engine._transactions["c"] = make_tx(
            id="c", status=TransactionStatus.PENDING, confidence=0.95)
        posted = engine.auto_post_high_confidence()
        assert posted == 1
        assert engine._transactions["a"].status == TransactionStatus.POSTED


class TestQueriesAndUpdates:
    def test_pending_review_and_all(self):
        engine = make_engine()
        t1 = make_tx(id="t1", date=datetime(2026, 7, 1))
        t2 = make_tx(id="t2", date=datetime(2026, 7, 2))
        engine._transactions = {"t1": t1, "t2": t2}
        engine._pending_review = ["t1"]
        assert engine.get_pending_review() == [t1]
        assert engine.get_all_transactions() == [t2, t1]  # date desc

    def test_update_missing(self):
        engine = make_engine()
        assert engine.update_transaction("ghost", {}, "u1") is False

    def test_update_re_categorizes_low_confidence(self):
        engine = make_engine()
        tx = make_tx(merchant="Slack", description="subscription")
        engine._transactions["tx-1"] = tx
        engine.ingest_transaction(tx)  # categorized high
        assert engine.update_transaction(
            "tx-1", {"merchant": None, "description": "completely random misc"}, "u1") is True
        assert tx.status == TransactionStatus.REVIEW_REQUIRED
        assert tx.id in engine._pending_review
        assert "Re-categorized" in tx.reasoning

    def test_update_high_confidence_removes_from_review(self):
        engine = make_engine()
        tx = make_tx(merchant=None, description="misc stuff")
        engine._transactions["tx-1"] = tx
        engine._pending_review.append("tx-1")
        tx.status = TransactionStatus.REVIEW_REQUIRED
        assert engine.update_transaction(
            "tx-1", {"merchant": "AWS", "description": "cloud bill"}, "u1") is True
        assert tx.id not in engine._pending_review
        assert tx.status == TransactionStatus.CATEGORIZED

    def test_update_date_string(self):
        engine = make_engine()
        tx = make_tx()
        engine._transactions["tx-1"] = tx
        assert engine.update_transaction(
            "tx-1", {"date": "2026-08-01"}, "u1") is True
        assert tx.date == datetime(2026, 8, 1)

    def test_update_amount_only(self):
        engine = make_engine()
        tx = make_tx()
        engine._transactions["tx-1"] = tx
        assert engine.update_transaction(
            "tx-1", {"amount": Decimal("200.00")}, "u1") is True
        assert tx.amount == Decimal("200.00")

    def test_delete(self):
        engine = make_engine()
        tx = make_tx()
        engine._transactions["tx-1"] = tx
        engine._pending_review.append("tx-1")
        assert engine.delete_transaction("tx-1", "u1") is True
        assert "tx-1" not in engine._transactions
        assert "tx-1" not in engine._pending_review
        assert engine.delete_transaction("ghost", "u1") is False


class TestAuditAndExports:
    def test_audit_log_filtered(self):
        engine = make_engine()
        t1 = make_tx(id="a")
        t2 = make_tx(id="b")
        engine._transactions = {"a": t1, "b": t2}
        engine.ingest_transaction(t1)
        engine.ingest_transaction(t2)
        filtered = engine.get_audit_log("a")
        assert all(e["transaction_id"] == "a" for e in filtered)
        assert len(engine.get_audit_log()) == 2

    def test_export_csv_sanitized(self):
        engine = make_engine()
        tx = make_tx(merchant="=cmd", description="+inject")
        engine.ingest_transaction(tx)
        csv_out = engine.export_general_ledger_csv()
        assert "'=cmd" in csv_out
        assert "'+inject" in csv_out
        assert "Date,Transaction ID" in csv_out

    def test_export_trial_balance(self):
        engine = make_engine()
        tx1 = make_tx(id="a", merchant="Slack", description="subscription",
                      amount=Decimal("-50.00"))
        tx2 = make_tx(id="b", merchant="Slack", description="subscription",
                      amount=Decimal("-30.00"))
        engine.ingest_transaction(tx1)
        engine.ingest_transaction(tx2)
        report = engine.export_trial_balance_json()
        software = [a for a in report["accounts"] if a["name"] == "Software"]
        assert software[0]["net_balance"] == -80.0


class TestForecast:
    def test_with_history(self):
        engine = make_engine()
        engine._transactions["a"] = make_tx(
            id="a", date=datetime(2026, 7, 1), merchant="Slack",
            description="subscription", amount=Decimal("-100.00"))
        engine._transactions["b"] = make_tx(
            id="b", date=datetime(2026, 7, 8), merchant="Stripe",
            description="sale", amount=Decimal("500.00"))
        engine.ingest_transaction(engine._transactions["a"])
        engine.ingest_transaction(engine._transactions["b"])
        forecast = engine.get_13_week_forecast(current_balance=1000.0)
        assert len(forecast["projection"]) == 13
        assert forecast["projection"][0]["week"] == 1
        assert forecast["projection"][0]["projected_balance"] == 1000.0 + forecast["historical_weekly_avg"] + 0  # week1 variance 0
        assert forecast["historical_weekly_avg"] != 0

    def test_empty_fallback(self):
        engine = make_engine()
        forecast = engine.get_13_week_forecast()
        assert forecast["historical_weekly_avg"] == -2500.0
        assert len(forecast["projection"]) == 13

    def test_no_cash_transfers_in_net(self):
        engine = make_engine()
        engine._transactions["a"] = make_tx(
            id="a", date=datetime(2026, 7, 1), description="transfer",
            amount=Decimal("-100.00"), category_id="1000")
        engine.ingest_transaction(engine._transactions["a"])
        forecast = engine.get_13_week_forecast()
        assert forecast["historical_weekly_avg"] == -2500.0  # transfer excluded


class TestScenario:
    def test_hire_expense(self):
        engine = make_engine()
        result = engine.run_scenario("Hire 2 engineers at $11k", [])
        assert result["impact_value"] == -11000
        assert "cash burn" in result["analysis"]
        assert result["risk_level"] == "medium"

    def test_lose_client_high_risk(self):
        engine = make_engine()
        result = engine.run_scenario("Lose a big client", [])
        assert result["impact_value"] == -15000
        assert result["risk_level"] == "high"

    def test_revenue(self):
        engine = make_engine()
        result = engine.run_scenario("Sell $5,000 of product", [])
        assert result["impact_value"] == 5000
        assert "Improves cash position" in result["analysis"]

    def test_k_suffix(self):
        engine = make_engine()
        result = engine.run_scenario("Expense 20k on ads", [])
        assert result["impact_value"] == -20000

    def test_default_impact(self):
        engine = make_engine()
        result = engine.run_scenario("just a thought", [])
        assert result["impact_value"] == -1000


class TestLedgerIntegration:
    def test_not_found(self):
        engine = make_engine()
        result = engine.post_to_ledger("ghost")
        assert result["status"] == "failed"

    def test_review_required(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.REVIEW_REQUIRED)
        engine._transactions["tx-1"] = tx
        result = engine.post_to_ledger("tx-1")
        assert result["status"] == "failed"
        assert "review" in result["error"]

    def test_already_posted(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.POSTED)
        engine._transactions["tx-1"] = tx
        result = engine.post_to_ledger("tx-1")
        assert result["status"] == "skipped"

    def test_mock_post(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.CATEGORIZED)
        engine._transactions["tx-1"] = tx
        result = engine.post_to_ledger("tx-1")
        assert result["status"] == "posted"
        assert result["mode"] == "mock"
        assert tx.status == TransactionStatus.POSTED

    def test_db_post(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.CATEGORIZED)
        engine._transactions["tx-1"] = tx
        ledger = MagicMock()
        ledger.record_transaction.return_value = SimpleNamespace(id="led-1")
        engine_cls = MagicMock()
        engine_cls.create_payment_entry.return_value = ["entry1", "entry2"]
        with patch("accounting.ledger.DoubleEntryEngine", engine_cls), \
             patch("accounting.ledger.EventSourcedLedger", return_value=ledger):
            result = engine.post_to_ledger("tx-1", db_session=MagicMock())
        assert result["status"] == "posted"
        assert result["ledger_tx_id"] == "led-1"
        ledger.record_transaction.assert_called_once()

    def test_import_error_fallback(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.CATEGORIZED)
        engine._transactions["tx-1"] = tx
        with patch("builtins.__import__", side_effect=ImportError("no accounting")):
            result = engine.post_to_ledger("tx-1")
        assert result["status"] == "posted"
        assert result["mode"] == "standalone"

    def test_exception_failed(self):
        engine = make_engine()
        tx = make_tx(status=TransactionStatus.CATEGORIZED)
        engine._transactions["tx-1"] = tx
        with patch("accounting.ledger.DoubleEntryEngine",
                   side_effect=RuntimeError("ledger boom")):
            result = engine.post_to_ledger("tx-1", db_session=MagicMock())
        assert result["status"] == "failed"
        assert result["error"] == "Ledger posting failed"
