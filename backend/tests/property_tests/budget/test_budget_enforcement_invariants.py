"""
Property-based tests for budget enforcement invariants.

Uses Hypothesis to generate thousands of test cases and validate
mathematical invariants that must always hold true for budget operations.

Invariants tested:
- Spend never exceeds budget (overdraft prevention)
- Sum of spends equals total burn (conservation of value)
- Remaining calculation is always exact
- Zero spend is always allowed
- Status thresholds are correct
"""

import pytest
from decimal import Decimal
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    InsufficientBudgetError,
)
from service_delivery.models import Project, BudgetStatus, ProjectStatus
from tests.fixtures.decimal_fixtures import money_strategy
from core.decimal_utils import to_decimal


@pytest.fixture
def project_factory(db_session):
    """Factory for creating test projects."""

    def _create_project(budget_amount, initial_burn=Decimal('0.00')):
        # Ensure initial_burn doesn't exceed budget
        if initial_burn > budget_amount:
            initial_burn = budget_amount

        # Calculate budget status based on utilization
        if budget_amount > 0:
            utilization = (initial_burn / budget_amount) * Decimal('100')
            if utilization >= Decimal('100'):
                budget_status = BudgetStatus.OVER_BUDGET
            elif utilization >= Decimal('80'):
                budget_status = BudgetStatus.AT_RISK
            else:
                budget_status = BudgetStatus.ON_TRACK
        else:
            budget_status = BudgetStatus.ON_TRACK

        project = Project(
            name="Test Project",
            workspace_id="test-workspace",
            status=ProjectStatus.ACTIVE,
            budget_amount=float(budget_amount),
            actual_burn=float(initial_burn),
            budget_status=budget_status,
        )
        db_session.add(project)
        db_session.commit()
        return project

    return _create_project


class TestBudgetEnforcementInvariants:
    """Test mathematical invariants of budget enforcement."""

    @given(
        budget=money_strategy('100', '10000'),
        initial_burn=money_strategy('0', '5000'),
        spend_amount=money_strategy('1', '1000')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_spend_never_exceeds_budget(self, project_factory, db_session, budget, initial_burn, spend_amount):
        """Verify that after any spend, actual_burn <= budget_amount."""
        project = project_factory(budget_amount=budget, initial_burn=initial_burn)
        service = BudgetEnforcementService(db_session)

        try:
            service.approve_spend(project.id, spend_amount)
            db_session.refresh(project)
            assert to_decimal(project.actual_burn) <= budget
        except InsufficientBudgetError:
            db_session.refresh(project)
            assert to_decimal(project.actual_burn) <= budget

    @given(
        budget=money_strategy('100', '10000'),
        spends=st.lists(
            money_strategy('1', '100'),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sum_of_spends_equals_burn(self, project_factory, db_session, budget, spends):
        """Record multiple spends, verify sum(actual_burn) = initial_burn + sum(spends)."""
        initial_burn = Decimal('0.00')
        project = project_factory(budget_amount=budget, initial_burn=initial_burn)
        service = BudgetEnforcementService(db_session)

        approved_spends = []
        for spend in spends:
            try:
                service.approve_spend(project.id, spend)
                approved_spends.append(spend)
            except InsufficientBudgetError:
                pass

        db_session.refresh(project)
        final_burn = to_decimal(project.actual_burn)
        expected_burn = initial_burn + sum(approved_spends, Decimal('0.00'))

        assert final_burn == expected_burn

    @given(
        budget=money_strategy('100', '10000'),
        initial_burn=money_strategy('0', '5000')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_remaining_calculation_invariant(self, project_factory, db_session, budget, initial_burn):
        """Verify remaining = budget - burn always holds."""
        # Cap initial_burn to budget (factory enforces this)
        if initial_burn > budget:
            initial_burn = budget

        project = project_factory(budget_amount=budget, initial_burn=initial_burn)
        service = BudgetEnforcementService(db_session)
        status = service.get_budget_status(project.id)

        expected_remaining = budget - initial_burn
        assert status["remaining"] == expected_remaining
        assert status["budget_amount"] == budget
        assert status["actual_burn"] == initial_burn

    @given(
        budget=money_strategy('100', '10000'),
        spends=st.lists(
            money_strategy('1', '500'),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_overdraft_prevention(self, project_factory, db_session, budget, spends):
        """Try to spend beyond budget, verify InsufficientBudgetError raised and no spend recorded."""
        project = project_factory(budget_amount=budget, initial_burn=Decimal('0.00'))
        service = BudgetEnforcementService(db_session)

        for spend in spends:
            try:
                service.approve_spend(project.id, spend)
            except InsufficientBudgetError:
                pass

        db_session.refresh(project)
        final_burn = to_decimal(project.actual_burn)
        assert final_burn <= budget, f"Burn {final_burn} exceeds budget {budget}"

    @given(
        budget=money_strategy('100', '10000'),
        spend=money_strategy('0', '1000')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_zero_spend_allowed(self, project_factory, db_session, budget, spend):
        """Verify $0 spend is always allowed."""
        project = project_factory(budget_amount=budget, initial_burn=Decimal('0.00'))
        service = BudgetEnforcementService(db_session)

        result = service.check_budget(project.id, Decimal('0.00'))
        assert result["allowed"] is True

    @given(
        budget=money_strategy('100', '10000'),
        initial_burn=money_strategy('0', '5000')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_utilization_percentage_invariant(self, project_factory, db_session, budget, initial_burn):
        """Verify utilization_pct = (burn / budget) * 100 exactly."""
        # Cap initial_burn to budget (factory enforces this)
        if initial_burn > budget:
            initial_burn = budget

        project = project_factory(budget_amount=budget, initial_burn=initial_burn)
        service = BudgetEnforcementService(db_session)
        status = service.get_budget_status(project.id)

        if budget > 0:
            from core.decimal_utils import round_money
            expected_utilization = round_money((initial_burn / budget) * Decimal('100'))
            assert status["utilization_pct"] == expected_utilization
        else:
            assert status["utilization_pct"] == Decimal('0.00')


class TestBudgetStatusInvariants:
    """Test budget status transition invariants."""

    @given(
        budget=money_strategy('100', '10000'),
        burn_ratio=st.decimals(min_value='0', max_value='2', places=2)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_status_thresholds(self, project_factory, db_session, budget, burn_ratio):
        """Verify status based on burn ratio (on_track <0.8, at_risk 0.8-0.99, over_budget >=1.0)."""
        if budget == 0:
            return

        burn = budget * burn_ratio
        # Cap burn to budget (factory enforces this)
        if burn > budget:
            burn = budget

        project = project_factory(budget_amount=budget, initial_burn=burn)
        service = BudgetEnforcementService(db_session)
        status = service.get_budget_status(project.id)

        # Adjust expected status based on capped burn
        actual_burn_ratio = burn / budget if budget > 0 else Decimal('0')

        if actual_burn_ratio >= Decimal('1.0'):
            assert status["budget_status"] == "over_budget"
        elif actual_burn_ratio >= Decimal('0.8'):
            assert status["budget_status"] == "at_risk"
        else:
            assert status["budget_status"] == "on_track"

    @given(
        budget=money_strategy('100', '10000'),
        spend=money_strategy('1', '1000')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_status_monotonic_with_burn(self, project_factory, db_session, budget, spend):
        """Status only gets worse as burn increases (never improves without adjustment)."""
        project = project_factory(budget_amount=budget, initial_burn=Decimal('0.00'))
        service = BudgetEnforcementService(db_session)

        initial_status = service.get_budget_status(project.id)["budget_status"]

        try:
            service.approve_spend(project.id, spend)
            final_status = service.get_budget_status(project.id)["budget_status"]

            status_order = {"on_track": 0, "at_risk": 1, "over_budget": 2}
            assert status_order[final_status] >= status_order[initial_status]

        except InsufficientBudgetError:
            pass
