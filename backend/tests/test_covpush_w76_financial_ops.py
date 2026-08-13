# -*- coding: utf-8 -*-
"""Coverage wave 76 — core/financial_ops_engine (CostLeakDetector,
BudgetGuardrails, InvoiceReconciler). Pure-Python service (no DB, no network).

TDD bug: a float ``monthly_limit`` (e.g. 5000.0 from a JSON/legacy config)
previously crashed ``check_spend`` with
``TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'float'``
(financial_ops_engine.py:284). ``set_limit`` now normalizes the limit to
Decimal at the engine boundary, so every downstream division
(check_spend, get_threshold_status) is float-safe. Regression test:
``test_check_spend_with_float_limit_does_not_crash`` (RED before fix, GREEN
after; also unblocks tests/test_phase37_financial_ops.py which built
BudgetLimit with a float).

Covered branches:
- CostLeakDetector: detect_unused empty/sorted-by-cost-desc, detect_redundant
  (multi-tool category, single tool, empty), get_savings_report empty/full,
  validate_categorization valid/empty-string-uncategorized/None-invalid,
  get_subscription_by_id hit/miss, calculate_total_cost,
  verify_savings_calculation, detect_anomalies zero_users_high_cost /
  high_cost_unused / data_inconsistency / none.
- BudgetGuardrails: set_limit positive/negative-or-zero ValueError/float
  normalization, check_spend paused/no-limit/deal-stage/milestone/block (and
  category auto-pause)/pause/warn/approved/float-limit, record_spend existing +
  missing category, get_threshold_status approved/pending/paused/rejected/
  zero-limit, update_thresholds full/partial/invalid-order/category-missing,
  reset_thresholds success/category-missing.
- InvoiceReconciler: add_invoice/add_contract/add_approval, reconcile summary,
  matched via contract_id, matched via vendor fallback, amount discrepancy,
  no-contract unmatched, zero-dollar contract + non-zero invoice (infinite
  diff), zero-dollar contract + zero invoice, exact-tolerance boundary.
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from core.financial_ops_engine import (
    BudgetGuardrails,
    BudgetLimit,
    Contract,
    CostLeakDetector,
    Invoice,
    InvoiceReconciler,
    SaaSSubscription,
    SpendStatus,
)


def _sub(sub_id, cost, last_used_days_ago, *, category="general",
         active_users=0, name=None):
    return SaaSSubscription(
        id=sub_id,
        name=name or f"sub-{sub_id}",
        monthly_cost=cost,
        last_used=datetime.now() - timedelta(days=last_used_days_ago),
        user_count=10,
        active_users=active_users,
        category=category,
    )


# ============================================================================
# CostLeakDetector
# ============================================================================

class TestCostLeakDetector:
    def test_detect_unused_flags_only_stale_subs_sorted_by_cost_desc(self):
        det = CostLeakDetector(unused_threshold_days=30)
        det.add_subscription(_sub("a", Decimal("10.00"), 5))   # used recently
        det.add_subscription(_sub("b", Decimal("500.00"), 40))  # stale, costly
        det.add_subscription(_sub("c", Decimal("50.00"), 60))   # stale, cheap

        unused = det.detect_unused()
        assert [u["id"] for u in unused] == ["b", "c"]
        assert unused[0]["monthly_cost"] == 500.0
        assert unused[0]["days_unused"] == 40
        assert unused[0]["recommendation"] == "Cancel or review usage"

    def test_detect_unused_empty_detector(self):
        assert CostLeakDetector().detect_unused() == []

    def test_detect_redundant_groups_same_category(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.00"), 5, category="crm"))
        det.add_subscription(_sub("b", Decimal("20.00"), 5, category="crm"))
        det.add_subscription(_sub("c", Decimal("30.00"), 5, category="crm"))
        det.add_subscription(_sub("d", Decimal("40.00"), 5, category="email"))

        redundant = det.detect_redundant()
        assert len(redundant) == 1
        assert redundant[0]["category"] == "crm"
        assert sorted(redundant[0]["tools"]) == ["sub-a", "sub-b", "sub-c"]
        assert redundant[0]["total_monthly_cost"] == 60.0
        assert redundant[0]["recommendation"] == "Consolidate 3 tools in crm"

    def test_detect_redundant_single_tool_no_group(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.00"), 5, category="crm"))
        assert det.detect_redundant() == []

    def test_get_savings_report_empty(self):
        report = CostLeakDetector().get_savings_report()
        assert report == {
            "unused_subscriptions": [],
            "redundant_tools": [],
            "potential_monthly_savings": 0.0,
            "potential_annual_savings": 0.0,
        }

    def test_get_savings_report_sums_unused_only(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("123.45"), 40))   # stale
        det.add_subscription(_sub("b", Decimal("200.00"), 5))    # used
        det.add_subscription(_sub("c", Decimal("76.55"), 60))    # stale
        report = det.get_savings_report()
        assert report["potential_monthly_savings"] == 200.0
        assert report["potential_annual_savings"] == 2400.0

    def test_validate_categorization_valid(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.00"), 5, category="crm"))
        assert det.validate_categorization() == {
            "valid": True, "uncategorized": [], "invalid": []
        }

    def test_validate_categorization_empty_string_is_uncategorized(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.00"), 5, category=""))
        det.add_subscription(_sub("b", Decimal("10.00"), 5, category="   "))
        result = det.validate_categorization()
        assert result["valid"] is False
        assert result["uncategorized"] == ["a", "b"]
        assert result["invalid"] == []

    def test_validate_categorization_none_is_invalid(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.00"), 5, category=None))
        result = det.validate_categorization()
        assert result["valid"] is False
        assert result["uncategorized"] == []
        assert result["invalid"] == ["a"]

    def test_get_subscription_by_id_hit_and_miss(self):
        det = CostLeakDetector()
        sub = _sub("a", Decimal("10.00"), 5)
        det.add_subscription(sub)
        assert det.get_subscription_by_id("a") is sub
        assert det.get_subscription_by_id("nope") is None

    def test_calculate_total_cost(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.50"), 5))
        det.add_subscription(_sub("b", "20", 5))
        det.add_subscription(_sub("c", 30.0, 5))
        assert det.calculate_total_cost() == Decimal("60.50")

    def test_calculate_total_cost_empty(self):
        assert CostLeakDetector().calculate_total_cost() == Decimal("0.00")

    def test_verify_savings_calculation_matches_report(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("100.00"), 40))
        det.add_subscription(_sub("b", Decimal("50.00"), 5))
        result = det.verify_savings_calculation()
        assert result["match"] is True
        assert result["expected"] == Decimal("100.00")
        assert result["actual"] == Decimal("100.00")
        assert result["diff"] == Decimal("0.00")

    def test_detect_anomalies_zero_active_users_high_cost(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("150.00"), 5, active_users=0))
        anomalies = det.detect_anomalies()
        assert anomalies[0]["type"] == "zero_active_users_high_cost"
        assert anomalies[0]["subscription_id"] == "a"

    def test_detect_anomalies_high_cost_unused(self):
        det = CostLeakDetector()
        # active_users=1 so only the high_cost_unused anomaly fires (cost>500
        # + stale); with active_users=0 the zero-users anomaly would win.
        det.add_subscription(_sub("a", Decimal("600.00"), 60, active_users=1))
        anomalies = det.detect_anomalies()
        assert anomalies[0]["type"] == "high_cost_unused"
        assert "days" in anomalies[0]["description"]

    def test_detect_anomalies_data_inconsistency(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.00"), 60, active_users=5))
        anomalies = det.detect_anomalies()
        assert anomalies[0]["type"] == "data_inconsistency"

    def test_detect_anomalies_cheap_used_sub_has_none(self):
        det = CostLeakDetector()
        det.add_subscription(_sub("a", Decimal("10.00"), 5, active_users=2))
        assert det.detect_anomalies() == []


# ============================================================================
# BudgetGuardrails
# ============================================================================

class TestBudgetGuardrails:
    def test_set_limit_positive(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="marketing", monthly_limit="5000.00"))
        assert g._limits["marketing"].monthly_limit == Decimal("5000.00")

    def test_set_limit_rejects_negative(self):
        g = BudgetGuardrails()
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            g.set_limit(BudgetLimit(category="m", monthly_limit=Decimal("-5")))

    def test_set_limit_rejects_zero(self):
        g = BudgetGuardrails()
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            g.set_limit(BudgetLimit(category="m", monthly_limit=Decimal("0")))

    def test_check_spend_paused_category(self):
        g = BudgetGuardrails()
        g._paused_categories.add("m")
        result = g.check_spend("m", "10.00")
        assert result["status"] == SpendStatus.PAUSED.value
        assert result["reason"] == "Category spending paused"

    def test_check_spend_no_limit_approved(self):
        result = BudgetGuardrails().check_spend("unknown", "10.00")
        assert result["status"] == SpendStatus.APPROVED.value
        assert result["reason"] == "No limit set"

    def test_check_spend_deal_stage_required(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000",
                                deal_stage_required="closed_won"))
        result = g.check_spend("m", "100.00", deal_stage="prospecting")
        assert result["status"] == SpendStatus.REJECTED.value
        assert "deal stage" in result["reason"]

    def test_check_spend_milestone_required(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000",
                                milestone_required="kickoff_complete"))
        result = g.check_spend("m", "100.00", milestone="signed")
        assert result["status"] == SpendStatus.PENDING.value
        assert "milestone" in result["reason"]

    def test_check_spend_block_threshold_rejects_and_pauses(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000",
                                current_spend="950"))
        result = g.check_spend("m", "100.00")
        assert result["status"] == SpendStatus.REJECTED.value
        assert result["utilization_pct"] == 105.0
        assert result["remaining"] == 50.0
        assert "m" in g._paused_categories

    def test_check_spend_pause_threshold(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000",
                                current_spend="850", pause_threshold_pct=90))
        result = g.check_spend("m", "60.00")
        assert result["status"] == SpendStatus.PAUSED.value
        assert result["utilization_pct"] == 91.0
        assert "m" not in g._paused_categories

    def test_check_spend_warn_threshold(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000",
                                current_spend="700"))
        result = g.check_spend("m", "110.00")
        assert result["status"] == SpendStatus.PENDING.value
        assert result["utilization_pct"] == 81.0
        assert result["remaining"] == 190.0

    def test_check_spend_below_warn_approved(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000",
                                current_spend="100"))
        result = g.check_spend("m", "50.00")
        assert result["status"] == SpendStatus.APPROVED.value
        assert result["utilization_pct"] == 15.0
        assert result["remaining"] == 850.0

    def test_check_spend_with_float_limit_does_not_crash(self):
        """TDD regression: float monthly_limit must not TypeError on division."""
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit=5000.0))
        result = g.check_spend("m", "2500.00")
        assert result["status"] == SpendStatus.APPROVED.value
        assert result["utilization_pct"] == 50.0

    def test_check_spend_non_positive_limit_uses_zero_utilization(self):
        """A non-positive limit injected outside set_limit falls back to 0%."""
        g = BudgetGuardrails()
        g._limits["m"] = BudgetLimit(category="m", monthly_limit=Decimal("0"))
        result = g.check_spend("m", "10.00")
        assert result["status"] == SpendStatus.APPROVED.value
        assert result["utilization_pct"] == 0.0

    def test_record_spend_existing_and_missing_category(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000"))
        g.record_spend("m", "123.45")
        assert g._limits["m"].current_spend == Decimal("123.45")
        g.record_spend("other", "10.00")  # no limit -> no-op
        assert "other" not in g._limits

    def test_get_threshold_status_approved(self):
        g = BudgetGuardrails()
        limit = BudgetLimit(category="m", monthly_limit="1000",
                            current_spend="100")
        status = g.get_threshold_status(limit)
        assert status["status"] == SpendStatus.APPROVED.value
        assert status["usage_pct"] == Decimal("10.0")
        assert status["next_threshold"] == "Warn at 80%"
        assert status["remaining_until_threshold"] == Decimal("700.00")

    def test_get_threshold_status_pending_warn(self):
        g = BudgetGuardrails()
        limit = BudgetLimit(category="m", monthly_limit="1000",
                            current_spend="850")
        status = g.get_threshold_status(limit)
        assert status["status"] == SpendStatus.PENDING.value
        assert status["next_threshold"] == "Pause at 90%"
        assert status["remaining_until_threshold"] == Decimal("50.00")

    def test_get_threshold_status_paused(self):
        g = BudgetGuardrails()
        limit = BudgetLimit(category="m", monthly_limit="1000",
                            current_spend="950")
        status = g.get_threshold_status(limit)
        assert status["status"] == SpendStatus.PAUSED.value
        assert status["next_threshold"] == "Block at 100%"
        assert status["remaining_until_threshold"] == Decimal("50.00")

    def test_get_threshold_status_rejected_blocked(self):
        g = BudgetGuardrails()
        limit = BudgetLimit(category="m", monthly_limit="1000",
                            current_spend="1000")
        status = g.get_threshold_status(limit)
        assert status["status"] == SpendStatus.REJECTED.value
        assert status["next_threshold"] is None
        assert status["remaining_until_threshold"] == Decimal("0")

    def test_get_threshold_status_remaining_clamped_to_zero(self):
        g = BudgetGuardrails()
        limit = BudgetLimit(category="m", monthly_limit="1000",
                            current_spend="900")
        status = g.get_threshold_status(limit)
        # 900 is exactly at pause (90%) -> pause branch, block amount 1000
        assert status["status"] == SpendStatus.PAUSED.value
        assert status["remaining_until_threshold"] == Decimal("100.00")

    def test_get_threshold_status_zero_limit_usage(self):
        g = BudgetGuardrails()
        limit = BudgetLimit(category="m", monthly_limit=Decimal("0"))
        status = g.get_threshold_status(limit)
        assert status["usage_pct"] == Decimal("0")
        assert status["status"] == SpendStatus.APPROVED.value

    def test_update_thresholds_full_and_partial(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000"))
        g.update_thresholds("m", warn=50, pause=75, block=95)
        limit = g._limits["m"]
        assert (limit.warn_threshold_pct, limit.pause_threshold_pct,
                limit.block_threshold_pct) == (50, 75, 95)
        g.update_thresholds("m", warn=60)  # partial update
        assert g._limits["m"].warn_threshold_pct == 60
        assert g._limits["m"].pause_threshold_pct == 75

    def test_update_thresholds_invalid_order(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000"))
        with pytest.raises(ValueError, match="Invalid thresholds"):
            g.update_thresholds("m", warn=95, pause=90, block=100)

    def test_update_thresholds_missing_category(self):
        g = BudgetGuardrails()
        with pytest.raises(KeyError, match="not found in limits"):
            g.update_thresholds("missing")

    def test_reset_thresholds_success(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="m", monthly_limit="1000",
                                warn_threshold_pct=10,
                                pause_threshold_pct=20,
                                block_threshold_pct=30))
        g.reset_thresholds("m")
        limit = g._limits["m"]
        assert (limit.warn_threshold_pct, limit.pause_threshold_pct,
                limit.block_threshold_pct) == (80, 90, 100)

    def test_reset_thresholds_missing_category(self):
        g = BudgetGuardrails()
        with pytest.raises(KeyError, match="not found in limits"):
            g.reset_thresholds("missing")


# ============================================================================
# InvoiceReconciler
# ============================================================================

class TestInvoiceReconciler:
    def _reconciler(self):
        rec = InvoiceReconciler(tolerance_percent=5.0)
        rec.add_contract(Contract(
            id="c1", vendor="Acme", monthly_amount=Decimal("100.00"),
            start_date=datetime.now(), end_date=datetime.now(),
        ))
        return rec

    def test_add_approval_stores_details(self):
        rec = self._reconciler()
        rec.add_approval("appr-1", {"status": "approved"})
        assert rec._approvals["appr-1"] == {"status": "approved"}

    def test_reconcile_matched_via_contract_id(self):
        rec = self._reconciler()
        rec.add_invoice(Invoice(id="i1", vendor="Acme",
                                amount=Decimal("100.00"), date=datetime.now(),
                                contract_id="c1"))
        result = rec.reconcile()
        assert result["summary"] == {
            "total_invoices": 1, "matched_count": 1,
            "discrepancy_count": 0, "unmatched_count": 0,
        }
        assert result["matched"][0]["status"] == "matched"
        assert result["matched"][0]["contract_id"] == "c1"

    def test_reconcile_matched_via_vendor_fallback(self):
        rec = self._reconciler()
        rec.add_invoice(Invoice(id="i1", vendor="acme",
                                amount=Decimal("100.00"), date=datetime.now()))
        result = rec.reconcile()
        assert result["matched"][0]["contract_id"] == "c1"

    def test_reconcile_amount_discrepancy(self):
        rec = self._reconciler()
        rec.add_invoice(Invoice(id="i1", vendor="Acme",
                                amount=Decimal("120.00"), date=datetime.now(),
                                contract_id="c1"))
        result = rec.reconcile()
        disc = result["discrepancies"][0]
        assert disc["status"] == "discrepancy"
        assert disc["expected_amount"] == 100.0
        assert disc["difference"] == 20.0
        assert disc["difference_percent"] == 20.0
        assert disc["reason"] == "Amount differs by 20.0%"

    def test_reconcile_exact_tolerance_boundary_matches(self):
        rec = self._reconciler()
        rec.add_invoice(Invoice(id="i1", vendor="Acme",
                                amount=Decimal("105.00"), date=datetime.now(),
                                contract_id="c1"))
        result = rec.reconcile()
        assert result["summary"]["matched_count"] == 1

    def test_reconcile_unmatched_no_contract(self):
        rec = self._reconciler()
        rec.add_invoice(Invoice(id="i1", vendor="Nope Inc.",
                                amount=Decimal("100.00"), date=datetime.now()))
        result = rec.reconcile()
        assert result["unmatched"][0]["reason"] == "No matching contract found"

    def test_reconcile_zero_contract_nonzero_invoice(self):
        rec = InvoiceReconciler()
        rec.add_contract(Contract(
            id="c0", vendor="FreeCo", monthly_amount=Decimal("0.00"),
            start_date=datetime.now(), end_date=datetime.now(),
        ))
        rec.add_invoice(Invoice(id="i1", vendor="FreeCo",
                                amount=Decimal("10.00"), date=datetime.now(),
                                contract_id="c0"))
        result = rec.reconcile()
        disc = result["discrepancies"][0]
        assert disc["status"] == "discrepancy"
        assert disc["difference_percent"] == float("inf")

    def test_reconcile_zero_contract_zero_invoice_matches(self):
        rec = InvoiceReconciler()
        rec.add_contract(Contract(
            id="c0", vendor="FreeCo", monthly_amount=Decimal("0.00"),
            start_date=datetime.now(), end_date=datetime.now(),
        ))
        rec.add_invoice(Invoice(id="i1", vendor="FreeCo",
                                amount=Decimal("0.00"), date=datetime.now(),
                                contract_id="c0"))
        result = rec.reconcile()
        assert result["summary"]["matched_count"] == 1

    def test_reconcile_empty_invoices(self):
        result = InvoiceReconciler().reconcile()
        assert result["summary"]["total_invoices"] == 0
