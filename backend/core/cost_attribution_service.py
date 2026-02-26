"""
Cost attribution service for category assignment and allocation.

This service provides centralized cost attribution to ensure all spends are
correctly categorized and allocated to budgets for accurate tracking.

Per GAAP/IFRS, all monetary calculations use Decimal for exact precision.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.decimal_utils import to_decimal, round_money
from accounting.models import Transaction


# Standard cost categories for consistent attribution
STANDARD_CATEGORIES = {
    "llm_tokens": "LLM API usage (OpenAI, Anthropic, etc.)",
    "compute": "Cloud compute costs (AWS, GCP, Azure)",
    "storage": "Database and object storage",
    "network": "Bandwidth, CDN, DNS",
    "labor": "Human labor costs (hours * rate)",
    "software": "SaaS subscriptions and licenses",
    "infrastructure": "DevOps, monitoring, logging",
    "support": "Customer support operations",
    "sales": "Sales and marketing expenses",
    "other": "Miscellaneous costs"
}


class CostAttributionError(Exception):
    """Base exception for cost attribution"""
    pass


class UncategorizedCostError(CostAttributionError):
    """Raised when cost has no category"""

    def __init__(self, message="Transaction category cannot be None or empty"):
        self.message = message
        super().__init__(self.message)


class InvalidCategoryError(CostAttributionError):
    """Raised when category is not recognized"""

    def __init__(self, category: str, message=None):
        self.category = category
        self.message = message or f"Category '{category}' is not a standard category"
        super().__init__(self.message)


class AllocationMismatchError(CostAttributionError):
    """Raised when cost allocations don't sum to original amount"""

    def __init__(self, original: Decimal, allocated_sum: Decimal):
        self.original = original
        self.allocated_sum = allocated_sum
        self.difference = original - allocated_sum
        super().__init__(
            f"Allocation sum ({allocated_sum}) != original amount ({original}), "
            f"difference: {self.difference}"
        )


class CostAttributionService:
    """
    Centralized cost attribution service.

    Ensures all costs are categorized (no uncategorized transactions),
    category assignment rules are consistent, and cost allocation is accurate.
    """

    def __init__(self, db: Session):
        """
        Initialize cost attribution service.

        Args:
            db: Database session
        """
        self.db = db

    def attribute_cost(
        self,
        amount: Union[Decimal, str, float],
        category: str,
        project_id: Optional[str] = None,
        description: Optional[str] = None,
        allow_custom_category: bool = False,
        workspace_id: Optional[str] = None
    ) -> Transaction:
        """
        Attribute a cost to a category and optionally to a project budget.

        Args:
            amount: Cost amount (Decimal, string, or float)
            category: Cost category (must be in STANDARD_CATEGORIES)
            project_id: Optional project ID for budget tracking
            description: Optional transaction description
            allow_custom_category: Allow non-standard categories with warning
            workspace_id: Optional workspace ID (defaults to 'test_workspace' for testing)

        Returns:
            Transaction: Created transaction record

        Raises:
            UncategorizedCostError: If category is None or empty
            InvalidCategoryError: If category is not recognized (unless allow_custom_category=True)
        """
        # Validate category
        if not category or (isinstance(category, str) and category.strip() == ''):
            raise UncategorizedCostError("Transaction category cannot be None or empty")

        category = category.strip()
        if category not in STANDARD_CATEGORIES:
            if allow_custom_category:
                # Log warning but allow custom category
                import logging
                logging.warning(f"Using custom category '{category}', not in STANDARD_CATEGORIES")
            else:
                raise InvalidCategoryError(
                    category,
                    f"Category '{category}' is not in STANDARD_CATEGORIES. "
                    f"Valid categories: {list(STANDARD_CATEGORIES.keys())}"
                )

        # Convert amount to Decimal
        amount_decimal = to_decimal(amount)

        # Create transaction
        transaction = Transaction(
            workspace_id=workspace_id or 'test_workspace',
            amount=amount_decimal,
            category=category,
            project_id=project_id,
            description=description,
            source='cost_attribution',
            status='posted',
            transaction_date=datetime.utcnow()
        )

        self.db.add(transaction)
        self.db.flush()

        return transaction

    def get_budget_attribution(self, project_id: str) -> Dict[str, Any]:
        """
        Get cost attribution breakdown for a project by category.

        Args:
            project_id: Project ID to get attribution for

        Returns:
            Dict with:
                - total_spend: Decimal (total spend across all categories)
                - by_category: Dict[str, Decimal] (spend per category)
                - uncategorized: Decimal (should be 0 - database enforces this)
                - transaction_count: int (number of transactions)
        """
        # Query all transactions for project
        transactions = self.db.query(Transaction).filter(
            Transaction.project_id == project_id,
            Transaction.status == 'posted'
        ).all()

        # Calculate attribution
        by_category: Dict[str, Decimal] = {}
        total_spend = Decimal('0.00')
        uncategorized = Decimal('0.00')

        for tx in transactions:
            amount = to_decimal(tx.amount or 0)
            total_spend += amount

            category = tx.category or 'uncategorized'
            if category == 'uncategorized':
                uncategorized += amount
            else:
                by_category[category] = by_category.get(category, Decimal('0.00')) + amount

        return {
            'total_spend': round_money(total_spend),
            'by_category': {cat: round_money(amt) for cat, amt in by_category.items()},
            'uncategorized': round_money(uncategorized),
            'transaction_count': len(transactions)
        }

    def validate_categorization(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate that all transactions are properly categorized.

        Args:
            project_id: Optional project ID to validate (validates all if None)

        Returns:
            Dict with:
                - is_valid: bool (True if all transactions categorized)
                - uncategorized_count: int (number of uncategorized transactions)
                - total_transactions: int (total transaction count)
                - issues: List[str] (list of validation issues)
        """
        # Build query
        query = self.db.query(Transaction).filter(Transaction.status == 'posted')
        if project_id:
            query = query.filter(Transaction.project_id == project_id)

        transactions = query.all()
        uncategorized = []

        for tx in transactions:
            if not tx.category or tx.category.strip() == '':
                uncategorized.append(tx.id)

        issues = []
        if uncategorized:
            issues.append(f"Found {len(uncategorized)} uncategorized transactions")

        return {
            'is_valid': len(uncategorized) == 0,
            'uncategorized_count': len(uncategorized),
            'total_transactions': len(transactions),
            'issues': issues
        }

    def allocate_cost(
        self,
        amount: Union[Decimal, str, float],
        category: str,
        allocations: List[Dict[str, Any]]
    ) -> List[Transaction]:
        """
        Split a cost across multiple budgets/projects.

        Args:
            amount: Total amount to allocate
            category: Cost category for all allocations
            allocations: List of allocation dicts with:
                - project_id: str (target project)
                - amount: Decimal (allocation amount)
                - description: str (optional)

        Returns:
            List[Transaction]: Created transaction records

        Raises:
            AllocationMismatchError: If allocations don't sum to original amount
            UncategorizedCostError: If category is missing
        """
        # Validate category
        if not category:
            raise UncategorizedCostError("Category required for cost allocation")

        total_amount = to_decimal(amount)

        # Verify allocations sum to original amount
        allocation_sum = sum(
            to_decimal(alloc.get('amount', 0))
            for alloc in allocations
        )

        if allocation_sum != total_amount:
            raise AllocationMismatchError(total_amount, allocation_sum)

        # Create transactions for each allocation
        transactions = []
        for alloc in allocations:
            tx = self.attribute_cost(
                amount=to_decimal(alloc['amount']),
                category=category,
                project_id=alloc.get('project_id'),
                description=alloc.get('description')
            )
            transactions.append(tx)

        return transactions

    def get_category_breakdown(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Decimal]:
        """
        Get aggregate spend by category across all projects.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dict[str, Decimal]: Category totals sorted by amount (descending)
        """
        # Build query
        query = self.db.query(
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.status == 'posted'
        )

        # Apply date filters if provided
        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)

        # Group by category
        results = query.group_by(Transaction.category).all()

        # Convert to dict and sort by amount
        breakdown = {
            category: round_money(Decimal(total or 0))
            for category, total in results
        }

        # Sort by amount (descending)
        sorted_breakdown = dict(
            sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        )

        return sorted_breakdown

    def get_standard_categories(self) -> Dict[str, str]:
        """
        Get standard cost categories with descriptions.

        Returns:
            Dict[str, str]: Category name -> description
        """
        return STANDARD_CATEGORIES.copy()
