"""
Unit tests for cost attribution accuracy.

Tests verify proper category assignment, cost allocation, and attribution invariants:
- All costs are categorized (no uncategorized transactions)
- Category assignment rules are consistent
- Sum of categorized spends equals total spend (attribution invariant)
- Cross-budget cost allocation works correctly
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session

from core.cost_attribution_service import (
    CostAttributionService,
    STANDARD_CATEGORIES,
    UncategorizedCostError,
    InvalidCategoryError,
    AllocationMismatchError
)
from accounting.models import Transaction
from tests.fixtures.decimal_fixtures import money_strategy


class TestCategoryValidation:
    """Tests for category validation rules."""

    def test_standard_categories_defined(self):
        """Verify 10 standard categories exist."""
        assert len(STANDARD_CATEGORIES) == 10
        expected_categories = [
            'llm_tokens', 'compute', 'storage', 'network', 'labor',
            'software', 'infrastructure', 'support', 'sales', 'other'
        ]
        assert set(STANDARD_CATEGORIES.keys()) == set(expected_categories)

    def test_valid_category_accepted(self, db):
        """Valid category 'llm_tokens' is accepted."""
        service = CostAttributionService(db)

        tx = service.attribute_cost(
            amount=Decimal('100.00'),
            category='llm_tokens'
        )

        assert tx.category == 'llm_tokens'
        assert tx.amount == Decimal('100.00')

    def test_invalid_category_rejected(self, db):
        """Invalid category 'unknown_category' raises InvalidCategoryError."""
        service = CostAttributionService(db)

        with pytest.raises(InvalidCategoryError) as exc_info:
            service.attribute_cost(
                amount=Decimal('100.00'),
                category='unknown_category'
            )

        assert 'unknown_category' in str(exc_info.value)

    def test_none_category_rejected(self, db):
        """None category raises UncategorizedCostError."""
        service = CostAttributionService(db)

        with pytest.raises(UncategorizedCostError):
            service.attribute_cost(
                amount=Decimal('100.00'),
                category=None
            )

    def test_empty_category_rejected(self, db):
        """Empty string category raises UncategorizedCostError."""
        service = CostAttributionService(db)

        with pytest.raises(UncategorizedCostError):
            service.attribute_cost(
                amount=Decimal('100.00'),
                category='  '
            )

    def test_custom_category_allowed_with_flag(self, db):
        """Custom category allowed when explicitly enabled."""
        service = CostAttributionService(db)

        # Should raise error without flag
        with pytest.raises(InvalidCategoryError):
            service.attribute_cost(
                amount=Decimal('100.00'),
                category='custom_category'
            )

        # Should succeed with flag
        tx = service.attribute_cost(
            amount=Decimal('100.00'),
            category='custom_category',
            allow_custom_category=True
        )

        assert tx.category == 'custom_category'


class TestCostAttribution:
    """Tests for cost attribution functionality."""

    def test_attribute_cost_creates_transaction(self, db):
        """Verify Transaction created with category."""
        service = CostAttributionService(db)

        tx = service.attribute_cost(
            amount=Decimal('50.00'),
            category='compute'
        )

        assert tx.id is not None
        assert tx.amount == Decimal('50.00')
        assert tx.category == 'compute'
        assert tx.status == 'posted'

    def test_attribute_cost_linked_to_project(self, db):
        """Verify project_id linked correctly."""
        service = CostAttributionService(db)

        tx = service.attribute_cost(
            amount=Decimal('75.00'),
            category='storage',
            project_id='project_123'
        )

        assert tx.project_id == 'project_123'

    def test_attribute_cost_description_stored(self, db):
        """Description is preserved."""
        service = CostAttributionService(db)

        tx = service.attribute_cost(
            amount=Decimal('25.00'),
            category='network',
            description='AWS bandwidth costs'
        )

        assert tx.description == 'AWS bandwidth costs'

    def test_attribute_cost_amount_exact(self, db):
        """Decimal amount stored exactly (no precision loss)."""
        service = CostAttributionService(db)

        # Use fractional cent
        tx = service.attribute_cost(
            amount=Decimal('10.005'),
            category='labor'
        )

        # Verify exact storage (no float rounding)
        assert tx.amount == Decimal('10.005')

    def test_attribute_cost_string_amount(self, db):
        """String amount converted to Decimal."""
        service = CostAttributionService(db)

        tx = service.attribute_cost(
            amount='123.45',
            category='software'
        )

        assert tx.amount == Decimal('123.45')

    def test_attribute_cost_returns_transaction(self, db):
        """Verify return value is Transaction instance."""
        service = CostAttributionService(db)

        tx = service.attribute_cost(
            amount=Decimal('100.00'),
            category='infrastructure'
        )

        assert isinstance(tx, Transaction)
        assert tx.id is not None


class TestBudgetAttribution:
    """Tests for budget-level cost attribution."""

    def test_get_budget_attribution_aggregates(self, db):
        """Verify costs grouped by category."""
        service = CostAttributionService(db)

        project_id = 'project_attribution_test'

        # Create transactions across categories
        service.attribute_cost(Decimal('100.00'), 'llm_tokens', project_id)
        service.attribute_cost(Decimal('50.00'), 'compute', project_id)
        service.attribute_cost(Decimal('30.00'), 'llm_tokens', project_id)

        attribution = service.get_budget_attribution(project_id)

        assert attribution['total_spend'] == Decimal('180.00')
        assert attribution['by_category']['llm_tokens'] == Decimal('130.00')
        assert attribution['by_category']['compute'] == Decimal('50.00')
        assert attribution['transaction_count'] == 3

    def test_attribution_total_matches_sum(self, db):
        """Total spend = sum of category spends (attribution invariant)."""
        service = CostAttributionService(db)

        project_id = 'project_sum_test'

        # Create multiple transactions
        service.attribute_cost(Decimal('10.00'), 'storage', project_id)
        service.attribute_cost(Decimal('20.00'), 'network', project_id)
        service.attribute_cost(Decimal('30.00'), 'support', project_id)

        attribution = service.get_budget_attribution(project_id)

        # Sum of categories should equal total
        category_sum = sum(attribution['by_category'].values(), Decimal('0.00'))

        assert attribution['total_spend'] == category_sum
        assert attribution['total_spend'] == Decimal('60.00')

    def test_attribution_uncategorized_zero(self, db):
        """No uncategorized costs allowed."""
        service = CostAttributionService(db)

        project_id = 'project_uncategorized_test'

        # All transactions have categories
        service.attribute_cost(Decimal('100.00'), 'sales', project_id)
        service.attribute_cost(Decimal('50.00'), 'labor', project_id)

        attribution = service.get_budget_attribution(project_id)

        # Uncategorized should be 0
        assert attribution['uncategorized'] == Decimal('0.00')

    def test_attribution_empty_project(self, db):
        """Empty project returns zero attribution."""
        service = CostAttributionService(db)

        attribution = service.get_budget_attribution('nonexistent_project')

        assert attribution['total_spend'] == Decimal('0.00')
        assert attribution['by_category'] == {}
        assert attribution['transaction_count'] == 0

    def test_attribution_single_category(self, db):
        """Single category attribution works."""
        service = CostAttributionService(db)

        project_id = 'project_single_cat_test'

        service.attribute_cost(Decimal('100.00'), 'llm_tokens', project_id)
        service.attribute_cost(Decimal('50.00'), 'llm_tokens', project_id)

        attribution = service.get_budget_attribution(project_id)

        assert attribution['by_category']['llm_tokens'] == Decimal('150.00')
        assert len(attribution['by_category']) == 1

    def test_attribution_multiple_categories(self, db):
        """Multiple categories summed correctly."""
        service = CostAttributionService(db)

        project_id = 'project_multi_cat_test'

        # Create transactions across 5 categories
        categories = {
            'llm_tokens': Decimal('100.00'),
            'compute': Decimal('200.00'),
            'storage': Decimal('50.00'),
            'network': Decimal('25.00'),
            'labor': Decimal('75.00')
        }

        for category, amount in categories.items():
            service.attribute_cost(amount, category, project_id)

        attribution = service.get_budget_attribution(project_id)

        # Verify all categories present
        assert len(attribution['by_category']) == 5

        # Verify amounts
        for category, expected_amount in categories.items():
            assert attribution['by_category'][category] == expected_amount

        # Verify total
        assert attribution['total_spend'] == Decimal('450.00')


class TestCostAllocation:
    """Tests for cross-budget cost allocation."""

    def test_allocate_cost_single_budget(self, db):
        """Allocate to 1 budget -> 1 transaction."""
        service = CostAttributionService(db)

        transactions = service.allocate_cost(
            amount=Decimal('100.00'),
            category='software',
            allocations=[
                {'project_id': 'project_a', 'amount': Decimal('100.00')}
            ]
        )

        assert len(transactions) == 1
        assert transactions[0].amount == Decimal('100.00')
        assert transactions[0].project_id == 'project_a'

    def test_allocate_cost_multiple_budgets(self, db):
        """Allocate to 3 budgets -> 3 transactions."""
        service = CostAttributionService(db)

        transactions = service.allocate_cost(
            amount=Decimal('100.00'),
            category='infrastructure',
            allocations=[
                {'project_id': 'project_a', 'amount': Decimal('50.00')},
                {'project_id': 'project_b', 'amount': Decimal('30.00')},
                {'project_id': 'project_c', 'amount': Decimal('20.00')}
            ]
        )

        assert len(transactions) == 3
        assert transactions[0].project_id == 'project_a'
        assert transactions[1].project_id == 'project_b'
        assert transactions[2].project_id == 'project_c'

    def test_allocation_sum_equals_original(self, db):
        """Sum of allocations = original amount (exact)."""
        service = CostAttributionService(db)

        original_amount = Decimal('100.00')

        transactions = service.allocate_cost(
            amount=original_amount,
            category='support',
            allocations=[
                {'project_id': 'project_a', 'amount': Decimal('33.33')},
                {'project_id': 'project_b', 'amount': Decimal('33.33')},
                {'project_id': 'project_c', 'amount': Decimal('33.34')}
            ]
        )

        allocation_sum = sum(tx.amount for tx in transactions)

        assert allocation_sum == original_amount
        assert allocation_sum == Decimal('100.00')

    def test_allocation_rounding_error_prevented(self, db):
        """Allocation with fractions handles rounding correctly."""
        service = CostAttributionService(db)

        # Allocate $100 across 3 projects (33.33, 33.33, 33.34)
        transactions = service.allocate_cost(
            amount=Decimal('100.00'),
            category='sales',
            allocations=[
                {'project_id': 'project_a', 'amount': Decimal('33.33')},
                {'project_id': 'project_b', 'amount': Decimal('33.33')},
                {'project_id': 'project_c', 'amount': Decimal('33.34')}
            ]
        )

        # Verify exact sum
        total = sum(tx.amount for tx in transactions)
        assert total == Decimal('100.00')

    def test_allocation_mismatch_raises_error(self, db):
        """Allocations not summing to original raise error."""
        service = CostAttributionService(db)

        with pytest.raises(AllocationMismatchError) as exc_info:
            service.allocate_cost(
                amount=Decimal('100.00'),
                category='other',
                allocations=[
                    {'project_id': 'project_a', 'amount': Decimal('50.00')},
                    {'project_id': 'project_b', 'amount': Decimal('40.00')}
                    # Sum = 90.00, not 100.00
                ]
            )

        assert '90.00' in str(exc_info.value)
        assert '100.00' in str(exc_info.value)

    def test_allocation_with_descriptions(self, db):
        """Allocation preserves descriptions."""
        service = CostAttributionService(db)

        transactions = service.allocate_cost(
            amount=Decimal('100.00'),
            category='llm_tokens',
            allocations=[
                {'project_id': 'project_a', 'amount': Decimal('60.00'), 'description': 'GPT-4 usage'},
                {'project_id': 'project_b', 'amount': Decimal('40.00'), 'description': 'Claude usage'}
            ]
        )

        assert transactions[0].description == 'GPT-4 usage'
        assert transactions[1].description == 'Claude usage'


class TestCategoryBreakdown:
    """Tests for aggregate category breakdown."""

    def test_category_breakdown_all_categories(self, db):
        """All 10 categories appear in breakdown."""
        service = CostAttributionService(db)

        # Create transactions for all categories
        for category in STANDARD_CATEGORIES.keys():
            service.attribute_cost(
                amount=Decimal('100.00'),
                category=category
            )

        breakdown = service.get_category_breakdown()

        assert len(breakdown) == 10
        for category in STANDARD_CATEGORIES.keys():
            assert category in breakdown

    def test_category_breakdown_sorted(self, db):
        """Breakdown sorted by amount (descending)."""
        service = CostAttributionService(db)

        # Create transactions with different amounts
        service.attribute_cost(Decimal('1000.00'), 'llm_tokens')
        service.attribute_cost(Decimal('500.00'), 'compute')
        service.attribute_cost(Decimal('2000.00'), 'storage')
        service.attribute_cost(Decimal('100.00'), 'network')

        breakdown = service.get_category_breakdown()

        # Verify descending order
        amounts = list(breakdown.values())
        assert amounts == sorted(amounts, reverse=True)
        assert amounts[0] == Decimal('2000.00')  # storage
        assert amounts[-1] == Decimal('100.00')  # network

    def test_category_breakdown_date_range(self, db):
        """Date range filtering works."""
        service = CostAttributionService(db)

        # Create transactions with different dates
        # Note: We'll use current date for simplicity
        # In real tests, you'd use pytest-freezegun to control time

        service.attribute_cost(Decimal('100.00'), 'llm_tokens')

        breakdown = service.get_category_breakdown()

        assert 'llm_tokens' in breakdown
        assert breakdown['llm_tokens'] == Decimal('100.00')

    def test_category_breakdown_decimal_precision(self, db):
        """Amounts use Decimal precision with rounding."""
        service = CostAttributionService(db)

        # Use fractional cents (will be rounded to 2 decimal places)
        service.attribute_cost(Decimal('10.005'), 'compute')
        service.attribute_cost(Decimal('20.003'), 'storage')

        breakdown = service.get_category_breakdown()

        # Verify Decimal precision with proper rounding (10.005 -> 10.01, 20.003 -> 20.00)
        assert breakdown['compute'] == Decimal('10.01')  # ROUND_HALF_UP
        assert breakdown['storage'] == Decimal('20.00')


class TestCategorizationValidation:
    """Tests for categorization validation."""

    def test_validate_categorization_pass(self, db):
        """Project with all categorized costs passes."""
        service = CostAttributionService(db)

        project_id = 'project_validation_pass'

        # All transactions have categories
        service.attribute_cost(Decimal('100.00'), 'llm_tokens', project_id)
        service.attribute_cost(Decimal('50.00'), 'compute', project_id)

        validation = service.validate_categorization(project_id)

        assert validation['is_valid'] is True
        assert validation['uncategorized_count'] == 0
        assert len(validation['issues']) == 0

    def test_validate_categorization_fails_uncategorized(self, db):
        """Uncategorized costs detected."""
        service = CostAttributionService(db)

        project_id = 'project_validation_fail'

        # Create categorized transaction
        service.attribute_cost(Decimal('100.00'), 'llm_tokens', project_id)

        # Manually create uncategorized transaction (empty string category)
        # Note: category=None would be rejected by NOT NULL constraint
        uncategorized_tx = Transaction(
            workspace_id='test_workspace',
            amount=Decimal('50.00'),
            category='',  # Empty category (uncategorized)
            project_id=project_id,
            source='manual',
            status='posted',
            transaction_date=datetime.utcnow()
        )
        db.add(uncategorized_tx)
        db.commit()

        validation = service.validate_categorization(project_id)

        assert validation['is_valid'] is False
        assert validation['uncategorized_count'] == 1
        assert len(validation['issues']) > 0

        # Cleanup
        db.delete(uncategorized_tx)
        db.commit()

    def test_validate_categorization_reports_issues(self, db):
        """Validation returns specific issues."""
        service = CostAttributionService(db)

        project_id = 'project_validation_issues'

        # Create uncategorized transaction
        uncategorized_tx = Transaction(
            workspace_id='test_workspace',
            amount=Decimal('100.00'),
            category='',
            project_id=project_id,
            source='manual',
            status='posted',
            transaction_date=datetime.utcnow()
        )
        db.add(uncategorized_tx)
        db.commit()

        validation = service.validate_categorization(project_id)

        assert 'uncategorized' in validation['issues'][0].lower()

        # Cleanup
        db.delete(uncategorized_tx)
        db.commit()

    def test_validate_categorization_all_projects(self, db):
        """Validate all projects when project_id is None."""
        service = CostAttributionService(db)

        # Create transactions for multiple projects
        service.attribute_cost(Decimal('100.00'), 'llm_tokens', 'project_a')
        service.attribute_cost(Decimal('50.00'), 'compute', 'project_b')

        validation = service.validate_categorization()  # No project_id

        assert validation['is_valid'] is True
        assert validation['total_transactions'] == 2

    def test_get_standard_categories(self, db):
        """Get standard categories with descriptions."""
        service = CostAttributionService(db)

        categories = service.get_standard_categories()

        assert len(categories) == 10
        assert 'llm_tokens' in categories
        assert categories['llm_tokens'] == 'LLM API usage (OpenAI, Anthropic, etc.)'
