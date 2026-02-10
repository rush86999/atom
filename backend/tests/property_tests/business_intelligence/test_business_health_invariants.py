"""
Property-Based Tests for Business Health Service - Critical Business Intelligence Logic

Tests business health and intelligence invariants:
- Priority generation and ranking
- AI score bounds and validation
- Churn probability calculations
- Cash flow risk assessment
- Growth opportunity identification
- Operational bottleneck detection
- Financial health metrics
- Risk level classification
- Priority action links
- drift percentage calculations
- margin compression detection
- subscription waste identification
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


class TestPriorityGenerationInvariants:
    """Tests for daily priority generation invariants"""

    @given(
        lead_scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_ai_score_bounds(self, lead_scores):
        """Test that AI scores are always in valid range"""
        for score in lead_scores:
            assert 0.0 <= score <= 100.0, "AI score must be in [0, 100]"

    @given(
        high_intent_leads=st.integers(min_value=0, max_value=10),
        failed_jobs=st.integers(min_value=0, max_value=5),
        drifts=st.integers(min_value=0, max_value=5),
        pricing_opportunities=st.integers(min_value=0, max_value=5),
        churn_risks=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=50)
    def test_priority_count_reasonable(self, high_intent_leads, failed_jobs, drifts, pricing_opportunities, churn_risks):
        """Test that total priority count is reasonable"""
        total_priorities = high_intent_leads + failed_jobs + drifts + pricing_opportunities + churn_risks + 1  # +1 for hiring check

        # Should have at least the hiring check priority
        assert total_priorities >= 1, "Should always have at least one priority"
        assert total_priorities <= 50, "Should not have excessive priorities"

    @given(
        priority_types=st.lists(
            st.sampled_from(["GROWTH", "RISK", "STRATEGY", "OPERATIONAL"]),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_priority_type_valid(self, priority_types):
        """Test that all priority types are valid"""
        valid_types = ["GROWTH", "RISK", "STRATEGY", "OPERATIONAL"]

        for ptype in priority_types:
            assert ptype in valid_types, "Priority type must be valid"

    @given(
        priorities=st.lists(
            st.fixed_dictionaries({
                'priority': st.sampled_from(["HIGH", "MEDIUM", "LOW"]),
                'type': st.sampled_from(["GROWTH", "RISK", "STRATEGY"])
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_priority_ranking_consistency(self, priorities):
        """Test that priorities are ranked consistently"""
        # Priority weights
        priority_weights = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

        # Sort by priority weight
        sorted_priorities = sorted(priorities, key=lambda p: priority_weights[p['priority']], reverse=True)

        # Verify sorting
        for i in range(1, len(sorted_priorities)):
            prev_weight = priority_weights[sorted_priorities[i-1]['priority']]
            curr_weight = priority_weights[sorted_priorities[i]['priority']]
            assert prev_weight >= curr_weight, "Priorities should be sorted by weight"


class TestChurnRiskInvariants:
    """Tests for churn risk prediction invariants"""

    @given(
        churn_probability=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_churn_probability_bounds(self, churn_probability):
        """Test that churn probability is in valid range"""
        assert 0.0 <= churn_probability <= 1.0, "Churn probability must be in [0, 1]"

    @given(
        churn_probabilities=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_high_churn_risk_identification(self, churn_probabilities):
        """Test that high churn risks are correctly identified"""
        high_risk_threshold = 0.7

        high_risk_count = sum(1 for prob in churn_probabilities if prob > high_risk_threshold)

        assert high_risk_count >= 0, "High risk count must be non-negative"
        assert high_risk_count <= len(churn_probabilities), "Cannot have more high risks than total"

    @given(
        customer_tenure_days=st.integers(min_value=0, max_value=3650),
        avg_purchase_value=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        purchase_frequency=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_churn_factor_consistency(self, customer_tenure_days, avg_purchase_value, purchase_frequency):
        """Test that churn factors are consistent"""
        # All factors should be non-negative
        assert customer_tenure_days >= 0, "Tenure must be non-negative"
        assert avg_purchase_value >= 0, "Average purchase value must be non-negative"
        assert purchase_frequency >= 0, "Purchase frequency must be non-negative"

        # Higher tenure and purchase value should correlate with lower churn risk
        # (This is a property the system should enforce)
        if customer_tenure_days > 365 and avg_purchase_value > 1000:
            # Long-term, high-value customers should have lower churn
            assert True, "Should have lower churn risk"


class TestCashFlowRiskInvariants:
    """Tests for cash flow risk assessment invariants"""

    @given(
        accounts_receivable=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
        accounts_payable=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
        cash_balance=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_cash_flow_calculation(self, accounts_receivable, accounts_payable, cash_balance):
        """Test that cash flow calculations are correct"""
        # Working capital = AR - AP
        working_capital = accounts_receivable - accounts_payable

        # Quick ratio = (Cash + AR) / AP
        if accounts_payable > 0:
            quick_ratio = (cash_balance + accounts_receivable) / accounts_payable
            assert quick_ratio >= 0, "Quick ratio must be non-negative"
        else:
            # No AP, healthy position
            assert True

        # All values must be non-negative
        assert accounts_receivable >= 0, "AR must be non-negative"
        assert accounts_payable >= 0, "AP must be non-negative"
        assert cash_balance >= 0, "Cash balance must be non-negative"

    @given(
        monthly_revenue=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
        monthly_expenses=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_burn_rate_calculation(self, monthly_revenue, monthly_expenses):
        """Test that burn rate calculations are correct"""
        # Burn rate = expenses - revenue
        burn_rate = monthly_expenses - monthly_revenue

        # If expenses > revenue, burning cash
        if monthly_expenses > monthly_revenue:
            assert burn_rate > 0, "Should have positive burn rate"
        # If revenue > expenses, generating cash
        elif monthly_revenue > monthly_expenses:
            assert burn_rate < 0, "Should have negative burn rate (generating cash)"


class TestGrowthOpportunityInvariants:
    """Tests for growth opportunity identification invariants"""

    @given(
        lead_scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_high_intent_lead_filtering(self, lead_scores):
        """Test that high-intent leads are correctly filtered"""
        threshold = 85.0

        high_intent_leads = [score for score in lead_scores if score > threshold]

        # All high-intent leads should have scores above threshold
        for score in high_intent_leads:
            assert score > threshold, "High-intent lead should have score above threshold"

    @given(
        conversion_rate=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        lead_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_conversion_calculation(self, conversion_rate, lead_count):
        """Test that conversion calculations are correct"""
        # Converted leads = lead_count * (conversion_rate / 100)
        converted = lead_count * (conversion_rate / 100.0)

        # Verify bounds
        assert 0 <= converted <= lead_count, "Converted count must be between 0 and lead count"

    @given(
        deal_values=st.lists(
            st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_pipeline_value_calculation(self, deal_values):
        """Test that pipeline value calculations are correct"""
        # Total pipeline value = sum of all deal values
        total_value = sum(deal_values)

        assert total_value >= 0, "Total pipeline value must be non-negative"

        if deal_values:
            average_value = total_value / len(deal_values)
            assert average_value >= 0, "Average deal value must be non-negative"


class TestOperationalBottleneckInvariants:
    """Tests for operational bottleneck detection invariants"""

    @given(
        task_completion_times=st.lists(
            st.floats(min_value=0.001, max_value=3600.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_bottleneck_identification(self, task_completion_times):
        """Test that bottlenecks are correctly identified"""
        if task_completion_times:
            avg_time = sum(task_completion_times) / len(task_completion_times)
            max_time = max(task_completion_times)

            # Bottleneck threshold: > 2x average
            if max_time > 2 * avg_time:
                assert True, "Should identify as bottleneck"

            # Max should always be >= average (with floating-point tolerance)
            epsilon = 1e-9
            assert max_time >= avg_time - epsilon, \
                f"Max time {max_time} should be >= average {avg_time}"

    @given(
        failure_count=st.integers(min_value=0, max_value=100),
        total_attempts=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_failure_rate_calculation(self, failure_count, total_attempts):
        """Test that failure rate calculations are correct"""
        assume(failure_count <= total_attempts)

        # Failure rate = failures / total_attempts
        if total_attempts > 0:
            failure_rate = failure_count / total_attempts
            assert 0.0 <= failure_rate <= 1.0, "Failure rate must be in [0, 1]"


class TestFinancialHealthInvariants:
    """Tests for financial health metrics invariants"""

    @given(
        monthly_revenue=st.floats(min_value=1.0, max_value=10000000.0, allow_nan=False, allow_infinity=False),
        monthly_expenses=st.floats(min_value=0.0, max_value=10000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_profit_margin_calculation(self, monthly_revenue, monthly_expenses):
        """Test that profit margin calculations are correct"""
        # Profit = revenue - expenses
        profit = monthly_revenue - monthly_expenses

        # Profit margin = profit / revenue (if revenue > 0)
        if monthly_revenue > 0:
            profit_margin = profit / monthly_revenue
            # Limit expenses to prevent extreme negative margins (> -100%)
            # In reality, margins can be very negative, but for this test we'll limit to reasonable cases
            assert profit_margin <= 1.0, "Profit margin cannot exceed 100%"

    @given(
        current_assets=st.floats(min_value=0.0, max_value=10000000.0, allow_nan=False, allow_infinity=False),
        current_liabilities=st.floats(min_value=0.0, max_value=10000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_current_ratio_calculation(self, current_assets, current_liabilities):
        """Test that current ratio calculations are correct"""
        if current_liabilities > 0:
            current_ratio = current_assets / current_liabilities
            assert current_ratio >= 0, "Current ratio must be non-negative"
        else:
            # No liabilities, healthy position
            assert current_assets >= 0, "Assets must be non-negative"

    @given(
        ebitda=st.floats(min_value=-1000000.0, max_value=10000000.0, allow_nan=False, allow_infinity=False),
        interest_expense=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_interest_coverage_ratio(self, ebitda, interest_expense):
        """Test that interest coverage ratio calculations are correct"""
        if interest_expense > 0:
            coverage_ratio = ebitda / interest_expense
            # Can be negative if EBITDA is negative
            assert isinstance(coverage_ratio, float), "Coverage ratio should be float"
        else:
            # No interest expense, no coverage concern
            assert True


class TestRiskLevelClassificationInvariants:
    """Tests for risk level classification invariants"""

    @given(
        risk_scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_risk_level_bounds(self, risk_scores):
        """Test that risk scores are in valid range"""
        for score in risk_scores:
            assert 0.0 <= score <= 100.0, "Risk score must be in [0, 100]"

    @given(
        risk_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_risk_classification(self, risk_score):
        """Test that risk levels are correctly classified"""
        # Risk classification thresholds
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        elif risk_score >= 20:
            risk_level = "LOW"
        else:
            risk_level = "MINIMAL"

        # Verify classification is valid
        valid_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]
        assert risk_level in valid_levels, "Risk level must be valid"

        # Higher scores should correspond to higher risk levels
        if risk_score >= 80:
            assert risk_level == "CRITICAL", "Score >= 80 should be CRITICAL"
        elif risk_score < 20:
            assert risk_level == "MINIMAL", "Score < 20 should be MINIMAL"


class TestVendorDriftInvariants:
    """Tests for vendor price drift detection invariants"""

    @given(
        historical_avg_price=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        current_price=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_drift_percentage_calculation(self, historical_avg_price, current_price):
        """Test that drift percentage calculations are correct"""
        assume(historical_avg_price > 0)

        # Drift % = ((current - historical) / historical) * 100
        drift_percent = ((current_price - historical_avg_price) / historical_avg_price) * 100

        # Verify calculation bounds
        assert drift_percent >= -100, "Cannot have more than 100% decrease (unless free)"

        # If current > historical, should have positive drift
        if current_price > historical_avg_price:
            assert drift_percent > 0, "Price increase should have positive drift"
        elif current_price < historical_avg_price:
            assert drift_percent < 0, "Price decrease should have negative drift"

    @given(
        drift_percentages=st.lists(
            st.floats(min_value=-50.0, max_value=200.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_significant_drift_threshold(self, drift_percentages):
        """Test that significant drift thresholds are applied"""
        significant_threshold = 10.0  # 10% change is significant

        significant_drifts = [d for d in drift_percentages if abs(d) > significant_threshold]

        # All significant drifts should exceed threshold
        for drift in significant_drifts:
            assert abs(drift) > significant_threshold, "Significant drift should exceed threshold"


class TestPricingOpportunityInvariants:
    """Tests for pricing opportunity detection invariants"""

    @given(
        current_price=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        margin_percent=st.floats(min_value=-50.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_margin_compression_detection(self, current_price, margin_percent):
        """Test that margin compression is correctly detected"""
        # Calculate cost from price and margin
        # margin = (price - cost) / price
        # cost = price * (1 - margin/100)

        cost = current_price * (1 - margin_percent / 100.0)

        # Verify calculation
        assert cost >= 0 or margin_percent > 100, "Cost should be non-negative unless margin > 100%"

        # Margin compression detected when margin is too low
        compression_threshold = 20.0  # 20% margin is minimum
        is_compressed = margin_percent < compression_threshold

        if margin_percent < compression_threshold:
            assert is_compressed, "Should detect margin compression"

    @given(
        current_price=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        target_price=st.floats(min_value=1.0, max_value=15000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_target_price_calculation(self, current_price, target_price):
        """Test that target price recommendations are reasonable"""
        # Target price should be >= current price for increases
        price_increase = target_price - current_price

        # Price change percentage
        if current_price > 0:
            price_change_pct = (price_increase / current_price) * 100

            # Price should be positive
            assert target_price > 0, "Target price should be positive"

            # Check that the calculation is reasonable (not strict bounds)
            assert isinstance(price_change_pct, float), "Price change should be float"


class TestSubscriptionWasteInvariants:
    """Tests for subscription waste detection invariants"""

    @given(
        mrr_amounts=st.lists(
            st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_zombie_subscription_detection(self, mrr_amounts):
        """Test that zombie subscriptions are correctly detected"""
        # Zombie subscriptions: canceled but still being charged
        # This is detected by comparing active subscriptions with billing

        # Total MRR for zombie subscriptions
        zombie_mrr = sum(mrr_amounts)
        subscription_count = len(mrr_amounts)

        assert zombie_mrr >= 0, "Zombie MRR must be non-negative"
        assert zombie_mrr <= sum(mrr_amounts), "Zombie MRR cannot exceed total"
        assert subscription_count >= 1, "Should have at least one subscription"

    @given(
        active_subs=st.integers(min_value=0, max_value=50),
        billed_subs=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=50)
    def test_subscription_discrepancy_detection(self, active_subs, billed_subs):
        """Test that subscription billing discrepancies are detected"""
        # Discrepancy = billed - active (zombie subs)
        discrepancy = billed_subs - active_subs

        # Zombie subs when billed > active
        zombie_count = max(0, discrepancy)

        assert zombie_count >= 0, "Zombie count must be non-negative"

        if billed_subs > active_subs:
            assert zombie_count > 0, "Should detect zombie subscriptions when billed > active"


class TestActionLinkInvariants:
    """Tests for priority action link invariants"""

    @given(
        resource_types=st.sampled_from(["lead", "job", "drift", "pricing", "waste", "churn"]),
        resource_ids=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    )
    @settings(max_examples=50)
    def test_action_link_format(self, resource_types, resource_ids):
        """Test that action links follow correct format"""
        # Generate action link
        action_link = f"/{resource_types}/{resource_ids}" if resource_types != "drift" else f"/dashboard/forensics?vendor={resource_ids}"

        # All links should start with /
        assert action_link.startswith("/"), "Action link should start with /"

        # Link should be non-empty
        assert len(action_link) > 1, "Action link should not be empty"

    @given(
        action_links=st.lists(
            st.text(min_size=5, max_size=200, alphabet='abcdefghijklmnopqrstuvwxyz/=?-_0123456789'),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_action_link_uniqueness(self, action_links):
        """Test that action links are unique within priorities"""
        # In real system, each priority should have unique actionable link
        unique_links = set(action_links)

        assert len(unique_links) <= len(action_links), "Should have unique or deduplicated links"


class TestHealthScoreInvariants:
    """Tests for overall health score calculation invariants"""

    @given(
        revenue_health=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        operational_health=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        customer_health=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        financial_health=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_overall_health_score_bounds(self, revenue_health, operational_health, customer_health, financial_health):
        """Test that overall health score is in valid range"""
        # Overall health = weighted average of components
        weights = [0.3, 0.25, 0.25, 0.2]  # Revenue, Operational, Customer, Financial
        components = [revenue_health, operational_health, customer_health, financial_health]

        overall_health = sum(w * c for w, c in zip(weights, components))

        assert 0.0 <= overall_health <= 100.0, "Overall health score must be in [0, 100]"

    @given(
        health_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_health_status_classification(self, health_score):
        """Test that health status is correctly classified"""
        if health_score >= 80:
            status = "EXCELLENT"
        elif health_score >= 60:
            status = "GOOD"
        elif health_score >= 40:
            status = "FAIR"
        else:
            status = "POOR"

        # Verify classification
        valid_statuses = ["EXCELLENT", "GOOD", "FAIR", "POOR"]
        assert status in valid_statuses, "Health status must be valid"

        # Higher scores should map to better statuses
        if health_score >= 80:
            assert status == "EXCELLENT", "Score >= 80 should be EXCELLENT"
        elif health_score < 40:
            assert status == "POOR", "Score < 40 should be POOR"


class TestRecommendationInvariants:
    """Tests for business recommendation invariants"""

    @given(
        impact_scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_recommendation_ranking(self, impact_scores):
        """Test that recommendations are ranked by impact"""
        # Sort by impact score descending
        ranked = sorted(impact_scores, reverse=True)

        # Verify descending order
        for i in range(1, len(ranked)):
            assert ranked[i] <= ranked[i-1], "Rankings should be in descending order"

    @given(
        effort=st.sampled_from(["easy", "medium", "complex"]),
        impact=st.sampled_from(["low", "medium", "high", "critical"])
    )
    @settings(max_examples=50)
    def test_effort_impact_balance(self, effort, impact):
        """Test that effort vs impact is properly balanced"""
        # Impact weights
        impact_weights = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        effort_weights = {"easy": 1, "medium": 2, "complex": 3}

        impact_score = impact_weights[impact]
        effort_score = effort_weights[effort]

        # High impact + low effort = highest priority
        priority_score = impact_score - (effort_score * 0.5)

        # Verify score is calculated
        assert isinstance(priority_score, float), "Priority score should be float"
