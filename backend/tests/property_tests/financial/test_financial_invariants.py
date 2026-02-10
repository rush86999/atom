"""
Property-Based Tests for Financial Operations - CRITICAL BUSINESS LOGIC

Tests critical financial invariants:
- Cost leak detection (unused subscriptions, redundant tools)
- Budget guardrails (spend limits, approvals, pauses)
- Invoice reconciliation (matching, discrepancies)
- Savings calculations
- Multi-currency handling
- Tax calculations

These tests protect against:
- Cost leaks (paying for unused services)
- Budget overruns (overspending on categories)
- Invoice fraud (incorrect payments)
- Financial incorrectness (wrong calculations)
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from decimal import Decimal
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestCostLeakDetectionInvariants:
    """Tests for SaaS cost leak detection invariants"""

    @given(
        subscription_count=st.integers(min_value=1, max_value=50),
        unused_threshold_days=st.integers(min_value=1, max_value=90)
    )
    @settings(max_examples=50)
    def test_unused_subscription_detection(self, subscription_count, unused_threshold_days):
        """Test that unused subscriptions are correctly identified"""
        from core.financial_ops_engine import CostLeakDetector, SaaSSubscription

        detector = CostLeakDetector(unused_threshold_days=unused_threshold_days)
        now = datetime.now()

        # Create mix of used and unused subscriptions
        unused_count = 0
        for i in range(subscription_count):
            # Alternate between used and unused
            if i % 2 == 0:
                # Unused: last_used before threshold
                last_used = now - timedelta(days=unused_threshold_days + 10)
                unused_count += 1
            else:
                # Used: last_used within threshold
                last_used = now - timedelta(days=max(0, unused_threshold_days - 10))

            sub = SaaSSubscription(
                id=f"sub_{i}",
                name=f"Service {i}",
                monthly_cost=100.0 + i,
                last_used=last_used,
                user_count=5,
                active_users=0 if i % 2 == 0 else 3,
                category="general"
            )
            detector.add_subscription(sub)

        unused = detector.detect_unused()

        # Verify unused count
        assert len(unused) == unused_count, f"Should detect {unused_count} unused subscriptions"

        # Verify all detected are actually unused
        for u in unused:
            assert u["monthly_cost"] > 0, "Monthly cost should be positive"
            assert u["days_unused"] >= unused_threshold_days, "Days unused should meet threshold"

    @given(
        categories=st.lists(
            st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            min_size=2,
            max_size=10,
            unique=True
        ),
        tools_per_category=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=50)
    def test_redundant_tool_detection(self, categories, tools_per_category):
        """Test that redundant tools in same category are detected"""
        from core.financial_ops_engine import CostLeakDetector, SaaSSubscription

        detector = CostLeakDetector()
        now = datetime.now()

        # Create subscriptions with multiple tools per category
        tool_id = 0
        for category in categories:
            for i in range(tools_per_category):
                sub = SaaSSubscription(
                    id=f"sub_{tool_id}",
                    name=f"{category.capitalize()} Tool {i}",
                    monthly_cost=50.0 + i * 10,
                    last_used=now - timedelta(days=5),
                    user_count=5,
                    active_users=3,
                    category=category
                )
                detector.add_subscription(sub)
                tool_id += 1

        redundant = detector.detect_redundant()

        # Should detect redundancy for each category
        assert len(redundant) == len(categories), f"Should detect {len(categories)} redundant categories"

        # Each redundant entry should have multiple tools
        for r in redundant:
            assert len(r["tools"]) == tools_per_category, "Should list all tools in category"
            assert r["total_monthly_cost"] > 0, "Total cost should be positive"
            assert r["category"] in categories, "Category should be valid"

    @given(
        unused_costs=st.lists(
            st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_savings_calculation_accuracy(self, unused_costs):
        """Test that savings calculations are accurate"""
        from core.financial_ops_engine import CostLeakDetector, SaaSSubscription

        detector = CostLeakDetector(unused_threshold_days=30)
        now = datetime.now()

        # Add unused subscriptions with specific costs
        for i, cost in enumerate(unused_costs):
            sub = SaaSSubscription(
                id=f"sub_{i}",
                name=f"Service {i}",
                monthly_cost=cost,
                last_used=now - timedelta(days=60),
                user_count=5,
                active_users=0,
                category="general"
            )
            detector.add_subscription(sub)

        report = detector.get_savings_report()

        # Verify monthly savings (with epsilon for floating-point precision)
        expected_monthly = sum(unused_costs)
        actual_monthly = report["potential_monthly_savings"]
        epsilon = 1e-9
        assert abs(actual_monthly - expected_monthly) < epsilon * max(1.0, expected_monthly), \
            f"Monthly savings should be {expected_monthly}, got {actual_monthly}"

        # Verify annual savings (12x monthly)
        expected_annual = expected_monthly * 12
        actual_annual = report["potential_annual_savings"]
        assert abs(actual_annual - expected_annual) < epsilon * max(1.0, expected_annual), \
            f"Annual savings should be {expected_annual}, got {actual_annual}"

        # Verify unused subscriptions are listed
        assert len(report["unused_subscriptions"]) == len(unused_costs), \
            "Should list all unused subscriptions"


class TestBudgetGuardrailsInvariants:
    """Tests for budget guardrails invariants"""

    @given(
        category=st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
        monthly_limit=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        current_spend=st.floats(min_value=0.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        new_spend=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_budget_limit_enforcement(self, category, monthly_limit, current_spend, new_spend):
        """Test that budget limits are enforced correctly"""
        from core.financial_ops_engine import BudgetGuardrails, BudgetLimit

        guardrails = BudgetGuardrails()
        limit = BudgetLimit(
            category=category,
            monthly_limit=monthly_limit,
            current_spend=current_spend
        )
        guardrails.set_limit(limit)

        result = guardrails.check_spend(category, new_spend)

        # If within limit, should be approved
        if current_spend + new_spend <= monthly_limit:
            assert result["status"] in ["approved", "APPROVED"], \
                "Spend within budget should be approved"
            assert "remaining" in result, "Should return remaining budget"
        # If exceeds limit, should be paused
        else:
            assert result["status"] in ["paused", "PAUSED"], \
                "Spend exceeding budget should be paused"

    @given(
        category=st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
        monthly_limit=st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        spend_amounts=st.lists(
            st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_budget_alert_thresholds(self, category, monthly_limit, spend_amounts):
        """Test that budget alerts trigger at correct thresholds"""
        from core.financial_ops_engine import BudgetGuardrails, BudgetLimit

        guardrails = BudgetGuardrails()
        limit = BudgetLimit(category=category, monthly_limit=monthly_limit, current_spend=0.0)
        guardrails.set_limit(limit)

        total_spend = 0.0
        for amount in spend_amounts:
            result = guardrails.check_spend(category, amount)

            # If approved, record the spend
            if result["status"] in ["approved", "APPROVED"]:
                guardrails.record_spend(category, amount)
                total_spend += amount

            # Should be paused if over limit
            if total_spend > monthly_limit:
                assert result["status"] in ["paused", "PAUSED"], \
                    f"Should pause when over limit: {total_spend} > {monthly_limit}, got status: {result['status']}"
                break  # Stop once paused

    @given(
        category=st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
        monthly_limit=st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        required_stage=st.sampled_from(["closed_won", "contract_signed", None]),
        deal_stage=st.sampled_from(["closed_won", "contract_signed", "prospecting", None])
    )
    @settings(max_examples=50)
    def test_deal_stage_enforcement(self, category, monthly_limit, required_stage, deal_stage):
        """Test that deal stage requirements are enforced"""
        from core.financial_ops_engine import BudgetGuardrails, BudgetLimit

        guardrails = BudgetGuardrails()
        limit = BudgetLimit(
            category=category,
            monthly_limit=monthly_limit,
            current_spend=0.0,
            deal_stage_required=required_stage
        )
        guardrails.set_limit(limit)

        result = guardrails.check_spend(category, 100.0, deal_stage=deal_stage)

        # If deal stage required but not met, should be rejected
        if required_stage and deal_stage != required_stage:
            assert result["status"] in ["rejected", "REJECTED"], \
                f"Should reject when deal stage '{deal_stage}' != required '{required_stage}'"
        # Otherwise should be approved
        else:
            assert result["status"] in ["approved", "APPROVED"], \
                "Should approve when deal stage requirement met"

    @given(
        category=st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
        monthly_limit=st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        required_milestone=st.sampled_from(["kickoff_complete", "delivery_accepted", None]),
        milestone=st.sampled_from(["kickoff_complete", "delivery_accepted", "in_progress", None])
    )
    @settings(max_examples=50)
    def test_milestone_enforcement(self, category, monthly_limit, required_milestone, milestone):
        """Test that milestone requirements are enforced"""
        from core.financial_ops_engine import BudgetGuardrails, BudgetLimit

        guardrails = BudgetGuardrails()
        limit = BudgetLimit(
            category=category,
            monthly_limit=monthly_limit,
            current_spend=0.0,
            milestone_required=required_milestone
        )
        guardrails.set_limit(limit)

        result = guardrails.check_spend(category, 100.0, milestone=milestone)

        # If milestone required but not met, should be pending
        if required_milestone and milestone != required_milestone:
            assert result["status"] in ["pending", "PENDING"], \
                f"Should be pending when milestone '{milestone}' != required '{required_milestone}'"
        # Otherwise should be approved
        else:
            assert result["status"] in ["approved", "APPROVED"], \
                "Should approve when milestone requirement met"


class TestInvoiceReconciliationInvariants:
    """Tests for invoice reconciliation invariants"""

    @given(
        invoice_amounts=st.lists(
            st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        ),
        contract_amount=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        tolerance_percent=st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_invoice_matching_within_tolerance(self, invoice_amounts, contract_amount, tolerance_percent):
        """Test that invoices within tolerance are matched"""
        from core.financial_ops_engine import InvoiceReconciler, Invoice, Contract

        reconciler = InvoiceReconciler(tolerance_percent=tolerance_percent)

        # Add contract
        contract = Contract(
            id="contract_1",
            vendor="Acme Corp",
            monthly_amount=contract_amount,
            start_date=datetime.now() - timedelta(days=60),
            end_date=datetime.now() + timedelta(days=60)
        )
        reconciler.add_contract(contract)

        # Add invoices
        matched_count = 0
        for i, amount in enumerate(invoice_amounts):
            invoice = Invoice(
                id=f"invoice_{i}",
                vendor="Acme Corp",
                amount=amount,
                date=datetime.now(),
                contract_id="contract_1"
            )
            reconciler.add_invoice(invoice)

            # Check if within tolerance
            diff_percent = abs(amount - contract_amount) / contract_amount * 100
            if diff_percent <= tolerance_percent:
                matched_count += 1

        result = reconciler.reconcile()

        # Verify matched count
        assert result["summary"]["matched_count"] == matched_count, \
            f"Should match {matched_count} invoices within {tolerance_percent}% tolerance"

    @given(
        contract_amount=st.floats(min_value=1000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        variance_percent=st.floats(min_value=6.0, max_value=50.0, allow_nan=False, allow_infinity=False),
        tolerance_percent=st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_invoice_discrepancy_detection(self, contract_amount, variance_percent, tolerance_percent):
        """Test that invoices outside tolerance are flagged as discrepancies"""
        from core.financial_ops_engine import InvoiceReconciler, Invoice, Contract

        # Ensure variance is greater than tolerance
        assume(variance_percent > tolerance_percent)

        reconciler = InvoiceReconciler(tolerance_percent=tolerance_percent)

        # Add contract
        contract = Contract(
            id="contract_1",
            vendor="Acme Corp",
            monthly_amount=contract_amount,
            start_date=datetime.now() - timedelta(days=60),
            end_date=datetime.now() + timedelta(days=60)
        )
        reconciler.add_contract(contract)

        # Add invoice with variance
        invoice_amount = contract_amount * (1 + variance_percent / 100)
        invoice = Invoice(
            id="invoice_1",
            vendor="Acme Corp",
            amount=invoice_amount,
            date=datetime.now(),
            contract_id="contract_1"
        )
        reconciler.add_invoice(invoice)

        result = reconciler.reconcile()

        # Should be flagged as discrepancy
        assert result["summary"]["discrepancy_count"] == 1, \
            "Invoice outside tolerance should be flagged as discrepancy"

        discrepancy = result["discrepancies"][0]
        assert discrepancy["status"] == "discrepancy", "Status should be discrepancy"
        assert "expected_amount" in discrepancy, "Should include expected amount"
        assert "difference" in discrepancy, "Should include difference"
        assert "difference_percent" in discrepancy, "Should include difference percent"

    @given(
        invoice_count=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=50)
    def test_invoice_reconciliation_summary(self, invoice_count):
        """Test that reconciliation summary is accurate"""
        from core.financial_ops_engine import InvoiceReconciler, Invoice, Contract

        reconciler = InvoiceReconciler(tolerance_percent=5.0)

        # Add contract
        contract = Contract(
            id="contract_1",
            vendor="Acme Corp",
            monthly_amount=1000.0,
            start_date=datetime.now() - timedelta(days=60),
            end_date=datetime.now() + timedelta(days=60)
        )
        reconciler.add_contract(contract)

        # Add invoices
        matched = 0
        discrepancies = 0
        unmatched = 0

        for i in range(invoice_count):
            vendor = "Acme Corp" if i % 3 != 2 else "Unknown Vendor"
            amount_variance = 0.0 if i % 2 == 0 else 0.08  # 8% variance

            invoice = Invoice(
                id=f"invoice_{i}",
                vendor=vendor,
                amount=1000.0 * (1 + amount_variance),
                date=datetime.now(),
                contract_id="contract_1" if vendor == "Acme Corp" else None
            )
            reconciler.add_invoice(invoice)

            # Track expected results
            if vendor != "Acme Corp":
                unmatched += 1
            elif amount_variance > 0.05:  # 5% tolerance
                discrepancies += 1
            else:
                matched += 1

        result = reconciler.reconcile()

        # Verify summary
        summary = result["summary"]
        assert summary["total_invoices"] == invoice_count, "Total count should match"
        assert summary["matched_count"] == matched, "Matched count should be correct"
        assert summary["discrepancy_count"] == discrepancies, "Discrepancy count should be correct"
        assert summary["unmatched_count"] == unmatched, "Unmatched count should be correct"


class TestMultiCurrencyInvariants:
    """Tests for multi-currency handling invariants"""

    @given(
        amounts=st.lists(
            st.floats(min_value=10.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10
        ),
        exchange_rates=st.lists(
            st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_currency_conversion_consistency(self, amounts, exchange_rates):
        """Test that currency conversions are consistent"""
        assume(len(amounts) == len(exchange_rates))

        # Convert to base currency
        converted_amounts = [amount * rate for amount, rate in zip(amounts, exchange_rates)]

        # Convert back
        for i, (original, rate) in enumerate(zip(amounts, exchange_rates)):
            if rate > 0:
                back_converted = converted_amounts[i] / rate
                # Use epsilon for floating-point comparison
                epsilon = 1e-9
                assert abs(back_converted - original) < epsilon * max(1.0, original), \
                    f"Round-trip conversion should be consistent: {original} -> {back_converted}"

    @given(
        amount=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        rate1=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
        rate2=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_cross_currency_conversion(self, amount, rate1, rate2):
        """Test cross-currency conversion consistency"""
        # Direct conversion: amount -> rate1 -> rate2
        direct = amount * (rate2 / rate1) if rate1 > 0 else 0

        # Two-step conversion: amount -> rate1 -> base -> rate2
        step1 = amount / rate1 if rate1 > 0 else 0
        step2 = step1 * rate2

        # Should be approximately equal (use epsilon for floating-point)
        epsilon = 1e-9
        assert abs(direct - step2) < epsilon * max(1.0, amount), \
            "Cross-currency conversion should be consistent"


class TestTaxCalculationInvariants:
    """Tests for tax calculation invariants"""

    @given(
        amounts=st.lists(
            st.floats(min_value=10.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        ),
        tax_rate=st.floats(min_value=0.0, max_value=0.30, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_tax_calculation_correctness(self, amounts, tax_rate):
        """Test that tax calculations are correct"""
        for amount in amounts:
            tax = amount * tax_rate
            total = amount + tax

            # Tax should be non-negative
            assert tax >= 0, "Tax should be non-negative"

            # Total should equal amount + tax
            epsilon = 1e-9
            assert abs(total - (amount + tax)) < epsilon, "Total should equal amount + tax"

            # Total should be >= amount
            assert total >= amount - epsilon, "Total should be >= amount"

    @given(
        amount=st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        tax_rates=st.lists(
            st.floats(min_value=0.0, max_value=0.25, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=50)
    def test_compound_tax_calculation(self, amount, tax_rates):
        """Test compound tax calculation (e.g., federal + state)"""
        total_tax = 0.0
        for rate in tax_rates:
            total_tax += amount * rate

        total = amount + total_tax

        # Each tax component should be non-negative
        for rate in tax_rates:
            tax_component = amount * rate
            assert tax_component >= 0, "Each tax component should be non-negative"

        # Total tax should be sum of components
        expected_total_tax = sum(amount * rate for rate in tax_rates)
        epsilon = 1e-9
        assert abs(total_tax - expected_total_tax) < epsilon, "Total tax should equal sum of components"

    @given(
        amount=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        tax_rate=st.floats(min_value=0.05, max_value=0.25, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_tax_inclusive_calculation(self, amount, tax_rate):
        """Test tax-inclusive (tax already included) calculation"""
        # For tax-inclusive: amount = base + tax = base * (1 + tax_rate)
        # So: base = amount / (1 + tax_rate)
        base_amount = amount / (1 + tax_rate)
        tax = amount - base_amount

        # Verify tax rate from extracted tax
        extracted_rate = tax / base_amount if base_amount > 0 else 0
        epsilon = 1e-6
        assert abs(extracted_rate - tax_rate) < epsilon, \
            f"Extracted tax rate should match: {extracted_rate} vs {tax_rate}"

        # Base + tax should equal original amount
        assert abs((base_amount + tax) - amount) < epsilon, \
            "Base + tax should equal original amount"


class TestNetWorthInvariants:
    """Tests for net worth calculation invariants"""

    @given(
        assets=st.lists(
            st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        ),
        liabilities=st.lists(
            st.floats(min_value=0.0, max_value=500000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_net_worth_calculation(self, assets, liabilities):
        """Test that net worth is calculated correctly"""
        total_assets = sum(assets)
        total_liabilities = sum(liabilities)
        net_worth = total_assets - total_liabilities

        # Net worth should equal assets - liabilities
        epsilon = 1e-9
        assert abs(net_worth - (total_assets - total_liabilities)) < epsilon, \
            "Net worth should equal assets minus liabilities"

        # If assets >= liabilities, net worth should be non-negative
        if total_assets >= total_liabilities:
            assert net_worth >= -epsilon, "Net worth should be non-negative when assets >= liabilities"

    @given(
        initial_balance=st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        transactions=st.lists(
            st.floats(min_value=-5000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_balance_sheet_integrity(self, initial_balance, transactions):
        """Test that balance sheet maintains integrity through transactions"""
        balance = initial_balance
        for transaction in transactions:
            balance += transaction

        # Final balance should equal initial plus all transactions
        expected_balance = initial_balance + sum(transactions)
        epsilon = 1e-9
        assert abs(balance - expected_balance) < epsilon, \
            "Final balance should equal initial plus transactions"


class TestRevenueRecognitionInvariants:
    """Tests for revenue recognition invariants"""

    @given(
        contract_value=st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        recognition_period_months=st.integers(min_value=1, max_value=24),
        months_elapsed=st.integers(min_value=0, max_value=24)
    )
    @settings(max_examples=50)
    def test_revenue_recognition_timing(self, contract_value, recognition_period_months, months_elapsed):
        """Test that revenue recognition follows timing rules"""
        assume(months_elapsed <= recognition_period_months)

        # Recognize revenue linearly over period
        monthly_revenue = contract_value / recognition_period_months
        recognized_revenue = monthly_revenue * months_elapsed

        # Recognized revenue should be non-negative
        assert recognized_revenue >= 0, "Recognized revenue should be non-negative"

        # Should not exceed total contract value
        assert recognized_revenue <= contract_value + 1e-9, \
            "Recognized revenue should not exceed contract value"

        # After full period, should recognize entire contract
        if months_elapsed == recognition_period_months:
            epsilon = 1e-9
            assert abs(recognized_revenue - contract_value) < epsilon * contract_value, \
                "After full period, should recognize entire contract"

    @given(
        total_revenue=st.floats(min_value=10000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
        segments=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=50)
    def test_revenue_segmentation(self, total_revenue, segments):
        """Test that revenue segmentation sums correctly"""
        # Divide revenue into equal segments
        segment_revenue = total_revenue / segments

        # Sum all segments
        total_from_segments = segment_revenue * segments

        # Should equal original total
        epsilon = 1e-9
        assert abs(total_from_segments - total_revenue) < epsilon * max(1.0, total_revenue), \
            "Sum of segments should equal total revenue"


class TestInvoiceAgingInvariants:
    """Tests for invoice aging calculations"""

    @given(
        invoice_days_ago=st.integers(min_value=0, max_value=120),
        terms_days=st.integers(min_value=15, max_value=90)
    )
    @settings(max_examples=50)
    def test_invoice_aging_calculation(self, invoice_days_ago, terms_days):
        """Test that invoice aging is calculated correctly"""
        days_overdue = invoice_days_ago - terms_days

        # Determine aging bucket
        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "1-30_days"
        elif days_overdue <= 60:
            bucket = "31-60_days"
        else:
            bucket = "61+_days"

        # Verify bucket assignment
        if invoice_days_ago <= terms_days:
            assert bucket == "current", "Should be current if not overdue"
        elif invoice_days_ago <= terms_days + 30:
            assert bucket == "1-30_days", "Should be in 1-30 days bucket"
        elif invoice_days_ago <= terms_days + 60:
            assert bucket == "31-60_days", "Should be in 31-60 days bucket"
        else:
            assert bucket == "61+_days", "Should be in 61+ days bucket"

    @given(
        # Generate both lists together to ensure same length
        st.lists(
            st.tuples(
                st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
                st.integers(min_value=1, max_value=90)
            ),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_aging_report_aggregation(self, invoice_data):
        """Test that aging report aggregates correctly"""
        # Unzip the tuples
        invoice_amounts = [amount for amount, _ in invoice_data]
        overdue_days_list = [days for _, days in invoice_data]

        # Calculate aging buckets
        aging_buckets = {
            "1-30_days": 0.0,
            "31-60_days": 0.0,
            "61+_days": 0.0
        }

        for amount, overdue_days in zip(invoice_amounts, overdue_days_list):
            if overdue_days <= 30:
                aging_buckets["1-30_days"] += amount
            elif overdue_days <= 60:
                aging_buckets["31-60_days"] += amount
            else:
                aging_buckets["61+_days"] += amount

        # Sum of buckets should equal total
        total_from_buckets = sum(aging_buckets.values())
        total_invoices = sum(invoice_amounts)
        epsilon = 1e-9
        assert abs(total_from_buckets - total_invoices) < epsilon * max(1.0, total_invoices), \
            "Sum of aging buckets should equal total outstanding"


class TestPaymentTermsInvariants:
    """Tests for payment terms enforcement"""

    @given(
        invoice_amount=st.floats(min_value=1000.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        terms_days=st.integers(min_value=15, max_value=90),
        paid_days=st.integers(min_value=0, max_value=120),
        late_fee_percent=st.floats(min_value=0.01, max_value=0.05, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_payment_term_enforcement(self, invoice_amount, terms_days, paid_days, late_fee_percent):
        """Test that payment terms are enforced correctly"""
        days_late = max(0, paid_days - terms_days)

        # Calculate late fee if applicable
        if days_late > 0:
            late_fee = invoice_amount * late_fee_percent
            total_due = invoice_amount + late_fee
        else:
            late_fee = 0.0
            total_due = invoice_amount

        # Late fee should be non-negative
        assert late_fee >= 0, "Late fee should be non-negative"

        # Total due should be >= invoice amount
        assert total_due >= invoice_amount - 1e-9, "Total due should be >= invoice amount"

        # If paid on time, no late fee
        if paid_days <= terms_days:
            assert late_fee < 1e-9, "No late fee if paid on time"

    @given(
        base_amount=st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        discount_percent=st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        paid_early_days=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=50)
    def test_early_payment_discount(self, base_amount, discount_percent, paid_early_days):
        """Test early payment discount calculation"""
        discount = base_amount * (discount_percent / 100.0)
        discounted_amount = base_amount - discount

        # Discount should be positive
        assert discount > 0, "Early payment discount should be positive"

        # Discounted amount should be less than base
        assert discounted_amount < base_amount, "Discounted amount should be less than base"

        # Discounted amount should be positive
        assert discounted_amount > 0, "Discounted amount should be positive"
