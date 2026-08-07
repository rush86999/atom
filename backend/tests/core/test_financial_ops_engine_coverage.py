"""Comprehensive coverage tests for core.financial_ops_engine.

Drives line/branch coverage toward 95% and includes TDD bug-reproduction
tests (docstring ``BUG: <desc>``) that pin real defects before the fix.
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

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
from core import financial_ops_engine as foe_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sub(
    sub_id: str,
    name: str = "Tool",
    cost: Decimal = Decimal("50.00"),
    days_ago: int = 0,
    category: str = "general",
    active_users: int = 1,
    user_count: int = 1,
) -> SaaSSubscription:
    return SaaSSubscription(
        id=sub_id,
        name=name,
        monthly_cost=cost,
        last_used=datetime.now() - timedelta(days=days_ago),
        user_count=user_count,
        active_users=active_users,
        category=category,
    )


# ---------------------------------------------------------------------------
# CostLeakDetector
# ---------------------------------------------------------------------------

class TestCostLeakDetector:
    def test_add_and_get_subscription_by_id(self):
        d = CostLeakDetector()
        s = _sub("a")
        d.add_subscription(s)
        assert d.get_subscription_by_id("a") is s
        assert d.get_subscription_by_id("missing") is None

    def test_detect_unused_sorted_desc_by_cost(self):
        d = CostLeakDetector(unused_threshold_days=10)
        d.add_subscription(_sub("cheap", cost=Decimal("10"), days_ago=20))
        d.add_subscription(_sub("pricey", cost=Decimal("500"), days_ago=20))
        d.add_subscription(_sub("recent", cost=Decimal("999"), days_ago=1))  # not unused

        unused = d.detect_unused()
        assert [u["id"] for u in unused] == ["pricey", "cheap"]
        assert unused[0]["monthly_cost"] == 500.0
        assert unused[0]["recommendation"] == "Cancel or review usage"
        # days_unused is a non-negative int computed from delta
        assert unused[0]["days_unused"] >= 19

    def test_detect_unused_empty(self):
        assert CostLeakDetector().detect_unused() == []

    def test_detect_redundant_groups_by_category(self):
        d = CostLeakDetector()
        d.add_subscription(_sub("a", name="HubSpot", cost=Decimal("10"), category="crm"))
        d.add_subscription(_sub("b", name="Salesforce", cost=Decimal("20"), category="crm"))
        d.add_subscription(_sub("c", name="GA", cost=Decimal("5"), category="analytics"))
        red = d.detect_redundant()
        assert len(red) == 1
        assert red[0]["category"] == "crm"
        assert set(red[0]["tools"]) == {"HubSpot", "Salesforce"}
        assert red[0]["total_monthly_cost"] == 30.0
        assert "Consolidate 2 tools in crm" == red[0]["recommendation"]

    def test_detect_redundant_none_when_all_unique_categories(self):
        d = CostLeakDetector()
        d.add_subscription(_sub("a", category="x"))
        d.add_subscription(_sub("b", category="y"))
        assert d.detect_redundant() == []

    def test_get_savings_report(self):
        d = CostLeakDetector(unused_threshold_days=10)
        d.add_subscription(_sub("unused1", cost=Decimal("100"), days_ago=20))
        d.add_subscription(_sub("unused2", cost=Decimal("50"), days_ago=20))
        d.add_subscription(_sub("used", cost=Decimal("10"), days_ago=1))
        report = d.get_savings_report()
        assert report["potential_monthly_savings"] == 150.0
        assert report["potential_annual_savings"] == 1800.0
        assert len(report["unused_subscriptions"]) == 2
        assert isinstance(report["redundant_tools"], list)

    def test_get_savings_report_empty(self):
        report = CostLeakDetector().get_savings_report()
        assert report["potential_monthly_savings"] == 0.0
        assert report["potential_annual_savings"] == 0.0

    def test_calculate_total_cost(self):
        d = CostLeakDetector()
        d.add_subscription(_sub("a", cost=Decimal("12.50")))
        d.add_subscription(_sub("b", cost=Decimal("7.50")))
        assert d.calculate_total_cost() == Decimal("20.00")

    def test_calculate_total_cost_empty(self):
        assert CostLeakDetector().calculate_total_cost() == Decimal("0.00")

    def test_validate_categorization_all_valid(self):
        d = CostLeakDetector()
        d.add_subscription(_sub("a", category="crm"))
        d.add_subscription(_sub("b", category="analytics"))
        res = d.validate_categorization()
        assert res["valid"] is True
        assert res["uncategorized"] == []
        assert res["invalid"] == []

    def test_validate_categorization_empty_string(self):
        d = CostLeakDetector()
        d.add_subscription(_sub("a", category="   "))
        res = d.validate_categorization()
        assert res["valid"] is False
        assert res["uncategorized"] == ["a"]
        assert res["invalid"] == []

    def test_verify_savings_calculation_matches(self):
        d = CostLeakDetector(unused_threshold_days=10)
        d.add_subscription(_sub("u", cost=Decimal("123.45"), days_ago=20))
        res = d.verify_savings_calculation()
        assert res["match"] is True
        assert res["diff"] == Decimal("0.00")
        assert res["expected"] == Decimal("123.45")

    def test_verify_savings_calculation_empty(self):
        res = CostLeakDetector().verify_savings_calculation()
        assert res["match"] is True
        assert res["actual"] == Decimal("0.00")

    def test_detect_anomalies_zero_active_users_high_cost(self):
        d = CostLeakDetector()
        d.add_subscription(_sub("a", cost=Decimal("150"), active_users=0))
        anomalies = d.detect_anomalies()
        assert any(a["type"] == "zero_active_users_high_cost" for a in anomalies)

    def test_detect_anomalies_low_cost_no_zero_anomaly(self):
        d = CostLeakDetector()
        d.add_subscription(_sub("a", cost=Decimal("50"), active_users=0))
        anomalies = d.detect_anomalies()
        assert not any(a["type"] == "zero_active_users_high_cost" for a in anomalies)

    def test_detect_anomalies_high_cost_unused(self):
        d = CostLeakDetector(unused_threshold_days=10)
        d.add_subscription(_sub("a", cost=Decimal("600"), days_ago=20, active_users=5))
        anomalies = d.detect_anomalies()
        assert any(a["type"] == "high_cost_unused" for a in anomalies)

    def test_detect_anomalies_data_inconsistency(self):
        d = CostLeakDetector(unused_threshold_days=10)
        # active users but stale last_used -> inconsistency
        d.add_subscription(_sub("a", cost=Decimal("10"), days_ago=20, active_users=3))
        anomalies = d.detect_anomalies()
        assert any(a["type"] == "data_inconsistency" for a in anomalies)

    def test_detect_anomalies_clean(self):
        d = CostLeakDetector(unused_threshold_days=10)
        d.add_subscription(_sub("a", cost=Decimal("10"), days_ago=1, active_users=2))
        assert d.detect_anomalies() == []

    # ---- BUG REPRODUCTIONS ----

    def test_validate_categorization_none_is_invalid_not_uncategorized(self):
        """BUG: validate_categorization classifies a None category as BOTH
        'uncategorized' and 'invalid'. Per the docstring, None/missing should
        ONLY appear in 'invalid' (empty/whitespace strings go in
        'uncategorized'). The root cause is that `not sub.category` is True
        for None, so the None subscription leaks into uncategorized before the
        explicit `is None` check.
        """
        d = CostLeakDetector()
        s = SaaSSubscription(
            id="none_cat",
            name="NoCat",
            monthly_cost=Decimal("10"),
            last_used=datetime.now(),
            user_count=1,
            category=None,
        )
        d.add_subscription(s)
        res = d.validate_categorization()
        assert res["valid"] is False
        # None must NOT be reported as merely "uncategorized"
        assert res["uncategorized"] == []
        # and MUST be reported as invalid
        assert res["invalid"] == ["none_cat"]


# ---------------------------------------------------------------------------
# BudgetGuardrails
# ---------------------------------------------------------------------------

class TestBudgetGuardrails:
    def test_set_limit_rejects_non_positive(self):
        g = BudgetGuardrails()
        with pytest.raises(ValueError):
            g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("0")))
        with pytest.raises(ValueError):
            g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("-5")))

    def test_check_spend_no_limit_approved(self):
        g = BudgetGuardrails()
        res = g.check_spend("unknown", Decimal("10"))
        assert res["status"] == SpendStatus.APPROVED.value
        assert res["reason"] == "No limit set"

    def test_check_spend_paused_category(self):
        g = BudgetGuardrails()
        g._paused_categories.add("frozen")
        res = g.check_spend("frozen", Decimal("1"))
        assert res["status"] == SpendStatus.PAUSED.value

    def test_check_spend_below_warn_approved(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("0")))
        res = g.check_spend("x", Decimal("10"))
        assert res["status"] == SpendStatus.APPROVED.value
        assert res["remaining"] == 90.0
        assert res["utilization_pct"] == 10.0

    def test_check_spend_warn_threshold(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("70")))
        res = g.check_spend("x", Decimal("15"))  # 85% -> warn
        assert res["status"] == SpendStatus.PENDING.value
        assert "Warn threshold" in res["reason"]

    def test_check_spend_pause_threshold(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("80")))
        res = g.check_spend("x", Decimal("15"))  # 95% -> pause
        assert res["status"] == SpendStatus.PAUSED.value

    def test_check_spend_block_threshold_pauses_category(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("0")))
        res = g.check_spend("x", Decimal("100"))  # 100% -> block
        assert res["status"] == SpendStatus.REJECTED.value
        assert "x" in g._paused_categories

    def test_check_spend_deal_stage_required_rejected(self):
        g = BudgetGuardrails()
        g.set_limit(
            BudgetLimit(
                category="x",
                monthly_limit=Decimal("100"),
                deal_stage_required="closed_won",
            )
        )
        res = g.check_spend("x", Decimal("10"), deal_stage="negotiation")
        assert res["status"] == SpendStatus.REJECTED.value
        # satisfies requirement
        res2 = g.check_spend("x", Decimal("10"), deal_stage="closed_won")
        assert res2["status"] == SpendStatus.APPROVED.value

    def test_check_spend_milestone_required_pending(self):
        g = BudgetGuardrails()
        g.set_limit(
            BudgetLimit(
                category="x",
                monthly_limit=Decimal("100"),
                milestone_required="kickoff_complete",
            )
        )
        res = g.check_spend("x", Decimal("10"), milestone="not_done")
        assert res["status"] == SpendStatus.PENDING.value
        res2 = g.check_spend("x", Decimal("10"), milestone="kickoff_complete")
        assert res2["status"] == SpendStatus.APPROVED.value

    def test_check_spend_accepts_str_and_float_amount(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100")))
        assert g.check_spend("x", "10")["status"] == SpendStatus.APPROVED.value
        assert g.check_spend("x", 10.0)["status"] == SpendStatus.APPROVED.value

    def test_record_spend_updates_current_spend(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100")))
        g.record_spend("x", Decimal("30"))
        assert g._limits["x"].current_spend == Decimal("30")

    def test_record_spend_ignored_for_unknown_category(self):
        g = BudgetGuardrails()
        g.record_spend("unknown", Decimal("30"))  # no-op, no crash
        assert g._limits == {}

    def test_get_threshold_status_approved(self):
        g = BudgetGuardrails()
        lim = BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("10"))
        g.set_limit(lim)
        res = g.get_threshold_status(lim)
        assert res["status"] == SpendStatus.APPROVED.value
        assert res["next_threshold"] == "Warn at 80%"
        assert res["remaining_until_threshold"] == Decimal("70")

    def test_get_threshold_status_pending(self):
        g = BudgetGuardrails()
        lim = BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("85"))
        g.set_limit(lim)
        res = g.get_threshold_status(lim)
        assert res["status"] == SpendStatus.PENDING.value
        assert res["next_threshold"] == "Pause at 90%"
        # remaining until pause = 90 - 85
        assert res["remaining_until_threshold"] == Decimal("5")

    def test_get_threshold_status_paused(self):
        g = BudgetGuardrails()
        lim = BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("92"))
        g.set_limit(lim)
        res = g.get_threshold_status(lim)
        assert res["status"] == SpendStatus.PAUSED.value
        assert res["next_threshold"] == "Block at 100%"
        assert res["remaining_until_threshold"] == Decimal("8")

    def test_get_threshold_status_blocked(self):
        g = BudgetGuardrails()
        lim = BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("100"))
        g.set_limit(lim)
        res = g.get_threshold_status(lim)
        assert res["status"] == SpendStatus.REJECTED.value
        assert res["next_threshold"] is None
        assert res["remaining_until_threshold"] == Decimal("0")

    def test_get_threshold_status_clamps_negative_remaining(self):
        g = BudgetGuardrails()
        # spend beyond warn threshold but below pause; remaining should clamp >= 0
        lim = BudgetLimit(category="x", monthly_limit=Decimal("100"), current_spend=Decimal("88"))
        g.set_limit(lim)
        res = g.get_threshold_status(lim)
        # pause at 90 -> remaining = 90 - 88 = 2
        assert res["remaining_until_threshold"] == Decimal("2")

    def test_update_thresholds_success(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100")))
        g.update_thresholds("x", warn=50, pause=70, block=90)
        lim = g._limits["x"]
        assert (lim.warn_threshold_pct, lim.pause_threshold_pct, lim.block_threshold_pct) == (50, 70, 90)

    def test_update_thresholds_partial_update(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100")))
        g.update_thresholds("x", pause=85)  # warn/block unchanged
        lim = g._limits["x"]
        assert lim.warn_threshold_pct == 80
        assert lim.pause_threshold_pct == 85
        assert lim.block_threshold_pct == 100

    def test_update_thresholds_unknown_category_raises(self):
        g = BudgetGuardrails()
        with pytest.raises(KeyError):
            g.update_thresholds("nope", warn=10)

    def test_update_thresholds_invalid_order_raises(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100")))
        with pytest.raises(ValueError):
            g.update_thresholds("x", warn=90, pause=80, block=100)  # warn >= pause

    def test_update_thresholds_out_of_range_raises(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100")))
        with pytest.raises(ValueError):
            g.update_thresholds("x", warn=-1, pause=50, block=100)

    def test_reset_thresholds(self):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=Decimal("100")))
        g.update_thresholds("x", warn=50, pause=70, block=90)
        g.reset_thresholds("x")
        lim = g._limits["x"]
        assert (lim.warn_threshold_pct, lim.pause_threshold_pct, lim.block_threshold_pct) == (80, 90, 100)

    def test_reset_thresholds_unknown_category_raises(self):
        g = BudgetGuardrails()
        with pytest.raises(KeyError):
            g.reset_thresholds("nope")


# ---------------------------------------------------------------------------
# InvoiceReconciler
# ---------------------------------------------------------------------------

class TestInvoiceReconciler:
    def _contract(self, cid="c1", vendor="acme", amount=Decimal("100")):
        return Contract(
            id=cid,
            vendor=vendor,
            monthly_amount=amount,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30),
        )

    def _invoice(self, iid="i1", vendor="acme", amount=Decimal("100"), contract_id=None):
        return Invoice(
            id=iid,
            vendor=vendor,
            amount=amount,
            date=datetime.now(),
            contract_id=contract_id,
        )

    def test_add_invoice_contract_approval(self):
        r = InvoiceReconciler()
        r.add_invoice(self._invoice())
        r.add_contract(self._contract())
        r.add_approval("ap1", {"x": 1})
        assert len(r._invoices) == 1
        assert "c1" in r._contracts
        assert r._approvals["ap1"] == {"x": 1}

    def test_reconcile_matched_by_contract_id(self):
        r = InvoiceReconciler()
        r.add_contract(self._contract())
        r.add_invoice(self._invoice(contract_id="c1"))
        res = r.reconcile()
        assert res["summary"]["matched_count"] == 1
        assert res["matched"][0]["contract_id"] == "c1"

    def test_reconcile_matched_by_vendor_case_insensitive(self):
        r = InvoiceReconciler()
        r.add_contract(self._contract(vendor="Acme"))
        r.add_invoice(self._invoice(vendor="ACME"))
        res = r.reconcile()
        assert res["summary"]["matched_count"] == 1

    def test_reconcile_discrepancy_above_tolerance(self):
        r = InvoiceReconciler(tolerance_percent=5.0)
        r.add_contract(self._contract(amount=Decimal("100")))
        r.add_invoice(self._invoice(amount=Decimal("150"), contract_id="c1"))
        res = r.reconcile()
        assert res["summary"]["discrepancy_count"] == 1
        d = res["discrepancies"][0]
        assert d["difference"] == 50.0
        assert d["difference_percent"] == 50.0

    def test_reconcile_within_tolerance_matched(self):
        r = InvoiceReconciler(tolerance_percent=5.0)
        r.add_contract(self._contract(amount=Decimal("100")))
        r.add_invoice(self._invoice(amount=Decimal("104"), contract_id="c1"))  # 4% diff
        res = r.reconcile()
        assert res["summary"]["matched_count"] == 1

    def test_reconcile_unmatched_no_contract(self):
        r = InvoiceReconciler()
        r.add_invoice(self._invoice(vendor="nobody"))
        res = r.reconcile()
        assert res["summary"]["unmatched_count"] == 1
        assert res["unmatched"][0]["reason"] == "No matching contract found"

    def test_reconcile_summary_counts(self):
        r = InvoiceReconciler(tolerance_percent=5.0)
        r.add_contract(self._contract("c1", "a", Decimal("100")))
        r.add_contract(self._contract("c2", "b", Decimal("100")))
        r.add_invoice(self._invoice("i1", "a", Decimal("100"), "c1"))   # matched
        r.add_invoice(self._invoice("i2", "b", Decimal("200"), "c2"))   # discrepancy
        r.add_invoice(self._invoice("i3", "z", Decimal("10")))          # unmatched
        res = r.reconcile()
        s = res["summary"]
        assert s["total_invoices"] == 3
        assert s["matched_count"] == 1
        assert s["discrepancy_count"] == 1
        assert s["unmatched_count"] == 1

    # ---- BUG REPRODUCTION ----

    def test_reconcile_zero_amount_contract_does_not_crash(self):
        """BUG: _match_invoice computes diff_percent = abs(diff)/expected*100
        and divides by zero when the contract's monthly_amount is 0, raising
        ZeroDivisionError. A zero-dollar contract is unusual but a legal
        value (e.g. a free pilot). Reconcile must classify it as a
        discrepancy (or match) rather than crash.
        """
        r = InvoiceReconciler()
        r.add_contract(self._contract(amount=Decimal("0")))
        r.add_invoice(self._invoice(amount=Decimal("10"), contract_id="c1"))
        # Must not raise
        res = r.reconcile()
        assert res["summary"]["total_invoices"] == 1
        # The result must be one of the three valid statuses, not an exception
        statuses = {r2["status"] for r2 in (
            res["matched"] + res["discrepancies"] + res["unmatched"]
        )}
        assert statuses <= {"matched", "discrepancy", "unmatched"}

    def test_reconcile_zero_invoice_against_zero_contract_matches(self):
        """Companion to the zero-amount bug: a 0 invoice against a 0 contract
        has 0 difference and should be classified as 'matched'."""
        r = InvoiceReconciler()
        r.add_contract(self._contract(amount=Decimal("0")))
        r.add_invoice(self._invoice(amount=Decimal("0"), contract_id="c1"))
        res = r.reconcile()
        assert res["summary"]["matched_count"] == 1
        assert res["summary"]["discrepancy_count"] == 0


# ---------------------------------------------------------------------------
# Property-based: utilization math is consistent
# ---------------------------------------------------------------------------

class TestBudgetGuardrailsProperty:
    @given(
        limit=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000"), places=2),
        spend=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
        amount=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
    )
    def test_utilization_pct_invariant_when_below_warn(self, limit, spend, amount):
        g = BudgetGuardrails()
        g.set_limit(BudgetLimit(category="x", monthly_limit=limit, current_spend=spend))
        res = g.check_spend("x", amount)
        # When approved (below warn), utilization must equal (spend+amount)/limit*100
        if res["status"] == SpendStatus.APPROVED.value:
            expected_pct = float((spend + amount) / limit * Decimal("100"))
            assert abs(res["utilization_pct"] - expected_pct) < 1e-6


# ---------------------------------------------------------------------------
# Module-level singleton instances exist
# ---------------------------------------------------------------------------

def test_module_singletons_exist():
    assert isinstance(foe_module.cost_detector, CostLeakDetector)
    assert isinstance(foe_module.budget_guardrails, BudgetGuardrails)
    assert isinstance(foe_module.invoice_reconciler, InvoiceReconciler)
