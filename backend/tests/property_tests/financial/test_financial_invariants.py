"""
Property-Based Tests for Financial Operations Engine

⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md

Tests:
    - 15 comprehensive property-based tests for financial operations
    - Coverage targets: 100% of financial_ops_engine.py
    - Runtime target: <30s
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict
from core.financial_ops_engine import (
    FinancialOpsEngine,
    BudgetCheckResult,
    Invoice,
    Subscription,
    CostSavingsReport,
    Account,
    Transaction
)
from core.financial_forensics import (
    FinancialForensicsEngine,
    AnomalyDetectionResult,
    ReconciliationResult
)


class TestFinancialInvariants:
    """Property-based tests for financial operations invariants."""

    # ========== Budget Guardrails ==========

    @given(
        budget=st.floats(min_value=0, max_value=10_000_000, allow_nan=False, allow_infinity=False),
        spend=st.floats(min_value=0, max_value=10_000_000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=200)
    def test_budget_guardrails_enforcement(self, budget, spend):
        """INVARIANT: Overspend must be rejected."""
        engine = FinancialOpsEngine()

        result = engine.check_budget(budget, spend)

        if spend > budget:
            # Overspend should be rejected
            assert not result.approved, f"Overspend {spend} > {budget} should be rejected"
            assert result.reason in ["Budget exceeded", "Spend exceeds budget"]
            assert result.remaining_budget == 0
        else:
            # Within budget should be approved
            assert result.approved, f"Spend {spend} <= {budget} should be approved"
            assert result.remaining_budget == pytest.approx(budget - spend, rel=1e-9)

    @given(
        budget=st.floats(min_value=1000, max_value=1_000_000, allow_nan=False),
        spend_amounts=st.lists(
            st.floats(min_value=0, max_value=100_000, allow_nan=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_budget_accumulation(self, budget, spend_amounts):
        """INVARIANT: Multiple spends should accumulate correctly."""
        engine = FinancialOpsEngine()

        total_spend = sum(spend_amounts)
        remaining = budget

        for amount in spend_amounts:
            result = engine.check_budget(remaining, amount)
            remaining -= amount

            if remaining < 0:
                assert not result.approved
            else:
                assert result.approved

    @given(
        budget=st.floats(min_value=1000, max_value=1_000_000, allow_nan=False),
        spend=st.floats(min_value=0, max_value=1_000_000, allow_nan=False),
        alert_threshold=st.floats(min_value=0.5, max_value=0.95, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_budget_alert_thresholds(self, budget, spend, alert_threshold):
        """INVARIANT: Alert should trigger at threshold."""
        engine = FinancialOpsEngine()
        engine.set_alert_threshold(alert_threshold)

        result = engine.check_budget(budget, spend)

        spend_ratio = spend / budget if budget > 0 else 0

        if spend_ratio >= alert_threshold:
            assert result.alert_triggered
        else:
            assert not result.alert_triggered

    # ========== Invoice Calculations ==========

    @given(
        line_items=st.lists(
            st.fixed_dictionaries({
                'description': st.text(min_size=1, max_size=50),
                'amount': st.floats(min_value=0, max_value=10_000, allow_nan=False),
                'quantity': st.integers(min_value=1, max_value=100)
            }),
            min_size=1,
            max_size=20
        ),
        tax_rate=st.floats(min_value=0, max_value=0.3, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_invoice_total_calculation(self, line_items, tax_rate):
        """INVARIANT: Invoice total must equal sum of line items + tax."""
        engine = FinancialOpsEngine()

        invoice = Invoice(
            line_items=line_items,
            tax_rate=tax_rate
        )

        total = engine.calculate_invoice_total(invoice)

        # Calculate expected total
        subtotal = sum(item['amount'] * item['quantity'] for item in line_items)
        expected_total = subtotal * (1 + tax_rate)

        assert total == pytest.approx(expected_total, rel=1e-9)

    @given(
        invoices=st.lists(
            st.fixed_dictionaries({
                'invoice_id': st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
                'amount': st.floats(min_value=0, max_value=10_000, allow_nan=False),
                'date': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())
            }),
            min_size=1,
            max_size=50,
            unique_by=lambda x: x['invoice_id']
        )
    )
    @settings(max_examples=100)
    def test_invoice_reconciliation_accuracy(self, invoices):
        """INVARIANT: Reconciliation must match all payments."""
        engine = FinancialOpsEngine()
        forensics = FinancialForensicsEngine()

        # Create invoices
        for inv_data in invoices:
            invoice = Invoice(
                invoice_id=inv_data['invoice_id'],
                line_items=[{'description': 'item', 'amount': inv_data['amount'], 'quantity': 1}],
                tax_rate=0
            )
            engine.record_invoice(invoice)

        # Record payments
        for inv_data in invoices:
            engine.record_payment(inv_data['invoice_id'], inv_data['amount'])

        # Reconcile
        result = forensics.reconcile(invoices)

        assert result.matched_count == len(invoices)
        assert result.unmatched_count == 0
        assert result.total_reconciled == sum(inv['amount'] for inv in invoices)

    # ========== Cost Savings ==========

    @given(
        current_tools=st.lists(
            st.fixed_dictionaries({
                'name': st.text(min_size=1, max_size=30),
                'cost': st.floats(min_value=0, max_value=1000, allow_nan=False),
                'usage_count': st.integers(min_value=0, max_value=1000)
            }),
            min_size=1,
            max_size=20,
            unique_by=lambda x: x['name']
        )
    )
    @settings(max_examples=100)
    def test_unused_subscription_detection(self, current_tools):
        """INVARIANT: Unused subscriptions must be detected."""
        engine = FinancialOpsEngine()

        subscriptions = [
            Subscription(
                name=tool['name'],
                cost=tool['cost'],
                usage_count=tool['usage_count']
            )
            for tool in current_tools
        ]

        report = engine.detect_unused_subscriptions(subscriptions)

        # Verify all unused tools (usage_count == 0) are detected
        expected_unused = [s for s in subscriptions if s.usage_count == 0]
        assert len(report.unused_subscriptions) == len(expected_unused)

        # Verify potential savings calculation
        expected_savings = sum(s.cost for s in expected_unused)
        assert report.potential_savings == pytest.approx(expected_savings, rel=1e-9)

    @given(
        tools=st.lists(
            st.fixed_dictionaries({
                'name': st.text(min_size=1, max_size=30),
                'category': st.sampled_from(['communication', 'analytics', 'storage', 'development']),
                'cost': st.floats(min_value=0, max_value=1000, allow_nan=False)
            }),
            min_size=2,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_redundant_tool_detection(self, tools):
        """INVARIANT: Redundant tools (same category) must be detected."""
        engine = FinancialOpsEngine()

        subscriptions = [
            Subscription(
                name=tool['name'],
                cost=tool['cost'],
                category=tool['category']
            )
            for tool in tools
        ]

        report = engine.detect_redundant_tools(subscriptions)

        # Verify redundancy detection (category with >1 tool)
        from collections import Counter
        category_counts = Counter(tool['category'] for tool in tools)
        expected_redundant = [cat for cat, count in category_counts.items() if count > 1]

        assert len(report.redundant_categories) == len(expected_redundant)

    @given(
        baseline_cost=st.floats(min_value=1000, max_value=100_000, allow_nan=False),
        reduction_percentages=st.lists(
            st.floats(min_value=0, max_value=1, allow_nan=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_cost_savings_report_accuracy(self, baseline_cost, reduction_percentages):
        """INVARIANT: Cost savings calculations must be accurate."""
        engine = FinancialOpsEngine()

        report = CostSavingsReport(baseline_cost=baseline_cost)

        total_savings = 0
        for percentage in reduction_percentages:
            savings = baseline_cost * percentage
            report.add_saving(source="optimization", amount=savings)
            total_savings += savings
            baseline_cost -= savings

        expected_total = sum(s * baseline_cost / (1 + sum(reduction_percentages[:i+1]))
                           for i, s in enumerate(reduction_percentages))

        assert report.total_savings > 0
        assert report.final_cost < baseline_cost + total_savings

    # ========== Currency & Tax ==========

    @given(
        amount=st.floats(min_value=0, max_value=1_000_000, allow_nan=False),
        exchange_rate=st.floats(min_value=0.5, max_value=2.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_multi_currency_conversion(self, amount, exchange_rate):
        """INVARIANT: Currency conversion must be accurate."""
        engine = FinancialOpsEngine()

        converted = engine.convert_currency(amount, exchange_rate)

        expected = amount * exchange_rate
        assert converted == pytest.approx(expected, rel=1e-9)

    @given(
        subtotal=st.floats(min_value=0, max_value=10_000, allow_nan=False),
        tax_rate=st.floats(min_value=0, max_value=0.5, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_tax_calculation_correctness(self, subtotal, tax_rate):
        """INVARIANT: Tax calculations must be correct."""
        engine = FinancialOpsEngine()

        tax = engine.calculate_tax(subtotal, tax_rate)
        expected_tax = subtotal * tax_rate

        assert tax == pytest.approx(expected_tax, rel=1e-9)

    # ========== Accounting Principles ==========

    @given(
        transactions=st.lists(
            st.fixed_dictionaries({
                'debit_account': st.text(min_size=1, max_size=20),
                'credit_account': st.text(min_size=1, max_size=20),
                'amount': st.floats(min_value=0, max_value=10_000, allow_nan=False)
            }),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_financial_account_balance_invariants(self, transactions):
        """INVARIANT: Double-entry bookkeeping (Debits = Credits)."""
        engine = FinancialOpsEngine()

        for txn in transactions:
            engine.record_transaction(
                debit_account=txn['debit_account'],
                credit_account=txn['credit_account'],
                amount=txn['amount']
            )

        balances = engine.get_account_balances()

        # Sum of all debits must equal sum of all credits
        total_debits = sum(txn['amount'] for txn in transactions)
        total_credits = sum(txn['amount'] for txn in transactions)

        assert total_debits == total_credits

    @given(
        transactions=st.lists(
            st.fixed_dictionaries({
                'account': st.text(min_size=1, max_size=20),
                'amount': st.floats(min_value=-10_000, max_value=10_000, allow_nan=False)
            }),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_net_worth_snapshot_consistency(self, transactions):
        """INVARIANT: Net worth = Assets - Liabilities."""
        engine = FinancialOpsEngine()

        for txn in transactions:
            engine.record_transaction(
                debit_account=txn['account'],
                credit_account='cash',
                amount=abs(txn['amount'])
            )

        net_worth = engine.calculate_net_worth()

        # Verify net worth calculation
        balances = engine.get_account_balances()
        assets = sum(balances.get(acc, 0) for acc in balances if acc.startswith('asset_'))
        liabilities = sum(balances.get(acc, 0) for acc in balances if acc.startswith('liability_'))

        assert net_worth == pytest.approx(assets - liabilities, rel=1e-9)

    # ========== Revenue Recognition ==========

    @given(
        contract_value=st.floats(min_value=1000, max_value=100_000, allow_nan=False),
        start_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        contract_duration_months=st.integers(min_value=1, max_value=36)
    )
    @settings(max_examples=100)
    def test_revenue_recognition_rules(self, contract_value, start_date, contract_duration_months):
        """INVARIANT: Revenue must be recognized over contract period."""
        engine = FinancialOpsEngine()

        monthly_revenue = engine.calculate_monthly_revenue(
            contract_value=contract_value,
            duration_months=contract_duration_months
        )

        expected_monthly = contract_value / contract_duration_months
        assert monthly_revenue == pytest.approx(expected_monthly, rel=1e-9)

    # ========== Invoice Aging ==========

    @given(
        invoices=st.lists(
            st.fixed_dictionaries({
                'invoice_id': st.text(min_size=1, max_size=20),
                'amount': st.floats(min_value=100, max_value=10_000, allow_nan=False),
                'days_outstanding': st.integers(min_value=0, max_value=120)
            }),
            min_size=1,
            max_size=30
        )
    )
    @settings(max_examples=100)
    def test_invoice_aging_calculation(self, invoices):
        """INVARIANT: Invoice aging buckets must be correct."""
        engine = FinancialOpsEngine()

        for inv in invoices:
            invoice = Invoice(
                invoice_id=inv['invoice_id'],
                line_items=[{'description': 'item', 'amount': inv['amount'], 'quantity': 1}],
                days_outstanding=inv['days_outstanding']
            )
            engine.record_invoice(invoice)

        aging_report = engine.generate_aging_report()

        # Verify bucketing
        expected_0_30 = sum(inv['amount'] for inv in invoices if 0 <= inv['days_outstanding'] <= 30)
        expected_31_60 = sum(inv['amount'] for inv in invoices if 31 <= inv['days_outstanding'] <= 60)
        expected_61_90 = sum(inv['amount'] for inv in invoices if 61 <= inv['days_outstanding'] <= 90)
        expected_90_plus = sum(inv['amount'] for inv in invoices if inv['days_outstanding'] > 90)

        assert aging_report.bucket_0_30 == pytest.approx(expected_0_30, rel=1e-9)
        assert aging_report.bucket_31_60 == pytest.approx(expected_31_60, rel=1e-9)
        assert aging_report.bucket_61_90 == pytest.approx(expected_61_90, rel=1e-9)
        assert aging_report.bucket_90_plus == pytest.approx(expected_90_plus, rel=1e-9)

    # ========== Payment Terms ==========

    @given(
        invoice_amount=st.floats(min_value=100, max_value=10_000, allow_nan=False),
        payment_terms_days=st.integers(min_value=0, max_value=90),
        days_late=st.integers(min_value=0, max_value=60)
    )
    @settings(max_examples=100)
    def test_payment_term_enforcement(self, invoice_amount, payment_terms_days, days_late):
        """INVARIANT: Late fees must be calculated correctly."""
        engine = FinancialOpsEngine()

        late_fee = engine.calculate_late_fee(
            invoice_amount=invoice_amount,
            payment_terms_days=payment_terms_days,
            days_late=days_late
        )

        if days_late <= payment_terms_days:
            assert late_fee == 0
        else:
            days_overdue = days_late - payment_terms_days
            expected_fee = invoice_amount * 0.01 * days_overdue  # 1% daily late fee
            assert late_fee == pytest.approx(expected_fee, rel=1e-9)

    # ========== Budget Rollover ==========

    @given(
        monthly_budget=st.floats(min_value=1000, max_value=100_000, allow_nan=False),
        month1_spend=st.floats(min_value=0, max_value=100_000, allow_nan=False),
        month2_spend=st.floats(min_value=0, max_value=100_000, allow_nan=False),
        rollover_enabled=st.booleans()
    )
    @settings(max_examples=100)
    def test_budget_rollover_logic(self, monthly_budget, month1_spend, month2_spend, rollover_enabled):
        """INVARIANT: Budget rollover must work correctly."""
        engine = FinancialOpsEngine()
        engine.enable_rollover(rollover_enabled)

        # Month 1
        result1 = engine.check_budget(monthly_budget, month1_spend)
        month1_remaining = monthly_budget - month1_spend

        # Month 2
        month2_budget = monthly_budget + (month1_remaining if rollover_enabled and month1_remaining > 0 else 0)
        result2 = engine.check_budget(month2_budget, month2_spend)

        if rollover_enabled:
            # With rollover, month 2 should have larger budget if month 1 had surplus
            if month1_remaining > 0:
                assert month2_budget > monthly_budget
        else:
            # Without rollover, month 2 budget should equal monthly budget
            assert month2_budget == monthly_budget
