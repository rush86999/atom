"""
Budget enforcement service with atomic spend approval.

This service provides centralized budget enforcement to prevent overdrafts
and ensure spend approval is atomic (check + update in single transaction).

Per GAAP/IFRS, all monetary calculations use Decimal for exact precision.
"""

from decimal import Decimal
from typing import Any, Dict, Union
from sqlalchemy.orm import Session

from core.decimal_utils import to_decimal, round_money
from service_delivery.models import Project, BudgetStatus


class BudgetError(Exception):
    """Base exception for budget operations"""
    pass


class InsufficientBudgetError(BudgetError):
    """Raised when spend would exceed budget limit"""

    def __init__(self, requested, remaining, budget_id=None):
        self.requested = requested
        self.remaining = remaining
        self.budget_id = budget_id
        super().__init__(
            f"Requested {requested}, only {remaining} remaining"
            + (f" for budget {budget_id}" if budget_id else "")
        )


class BudgetNotFoundError(BudgetError):
    """Raised when budget doesn't exist"""
    pass


class BudgetEnforcementService:
    """
    Centralized budget enforcement with atomic spend approval.

    All database operations use explicit transactions to ensure atomicity.
    No check-then-act outside transaction boundary.
    """

    def __init__(self, db: Session):
        """
        Initialize budget enforcement service.

        Args:
            db: Database session (must be within transaction for atomicity)
        """
        self.db = db

    def check_budget(
        self, project_id: str, amount: Union[Decimal, str, float]
    ) -> Dict[str, Any]:
        """
        Check if spend amount is within budget limit.

        Args:
            project_id: Project ID to check budget for
            amount: Amount to check (Decimal, string, or float)

        Returns:
            Dict with:
                - allowed: bool (True if within budget)
                - remaining: Decimal (remaining budget)
                - budget_status: str (on_track, at_risk, over_budget)
                - utilization_pct: Decimal (percentage used)

        Raises:
            BudgetNotFoundError: If project doesn't exist
            ValueError: If amount is negative
        """
        # Query project
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise BudgetNotFoundError(f"Project {project_id} not found")

        # Convert and validate amount
        spend_amount = to_decimal(amount)
        if spend_amount < 0:
            raise ValueError("Spend amount cannot be negative")

        # Calculate remaining budget
        budget_amount = to_decimal(project.budget_amount or 0)
        actual_burn = to_decimal(project.actual_burn or 0)
        remaining = budget_amount - actual_burn

        # Calculate utilization percentage
        utilization_pct = (
            round_money((actual_burn / budget_amount) * Decimal('100'))
            if budget_amount > 0
            else Decimal('0.00')
        )

        # Get budget status
        budget_status = project.budget_status.value if project.budget_status else "on_track"

        # Check if spend is allowed
        allowed = spend_amount <= remaining

        return {
            "allowed": allowed,
            "remaining": remaining,
            "budget_status": budget_status,
            "utilization_pct": utilization_pct,
        }

    def approve_spend(
        self,
        project_id: str,
        amount: Union[Decimal, str, float],
        description: str = None
    ) -> Dict[str, Any]:
        """
        Atomically approve and record spend.

        This method performs check-and-update within a single transaction
        to prevent race conditions. If budget is insufficient, the spend
        is rejected and no changes are made.

        Args:
            project_id: Project ID to approve spend for
            amount: Amount to spend (Decimal, string, or float)
            description: Optional description for audit trail

        Returns:
            Dict with:
                - approved: bool (True if spend approved)
                - remaining: Decimal (remaining budget after spend)
                - budget_status: str (updated budget status)
                - utilization_pct: Decimal (updated utilization)
                - previous_burn: Decimal (burn before this spend)

        Raises:
            InsufficientBudgetError: If spend would exceed budget
            BudgetNotFoundError: If project doesn't exist
        """
        # Start transaction (assert we're in transaction context)
        try:
            # Query project with row lock for atomicity
            project = (
                self.db.query(Project)
                .filter(Project.id == project_id)
                .with_for_update()  # Prevent concurrent modifications
                .first()
            )

            if not project:
                raise BudgetNotFoundError(f"Project {project_id} not found")

            # Convert amount
            spend_amount = to_decimal(amount)
            if spend_amount < 0:
                raise ValueError("Spend amount cannot be negative")

            # Store previous burn for result
            previous_burn = to_decimal(project.actual_burn or 0)

            # Check budget
            budget_amount = to_decimal(project.budget_amount or 0)
            remaining = budget_amount - previous_burn

            if spend_amount > remaining:
                # Insufficient budget - raise error
                raise InsufficientBudgetError(
                    requested=spend_amount,
                    remaining=remaining,
                    budget_id=project_id
                )

            # Approve spend: update actual_burn
            project.actual_burn = float(previous_burn + spend_amount)

            # Recalculate budget status
            new_burn = to_decimal(project.actual_burn)
            new_utilization = (
                round_money((new_burn / budget_amount) * Decimal('100'))
                if budget_amount > 0
                else Decimal('0.00')
            )

            # Status thresholds: on_track <80%, at_risk 80-99%, over_budget >=100%
            if new_utilization >= Decimal('100.00'):
                project.budget_status = BudgetStatus.OVER_BUDGET
            elif new_utilization >= Decimal('80.00'):
                project.budget_status = BudgetStatus.AT_RISK
            else:
                project.budget_status = BudgetStatus.ON_TRACK

            # Commit transaction
            self.db.commit()

            # Return approval result
            return {
                "approved": True,
                "remaining": budget_amount - new_burn,
                "budget_status": project.budget_status.value,
                "utilization_pct": new_utilization,
                "previous_burn": previous_burn,
            }

        except Exception as e:
            # Rollback on any error
            self.db.rollback()
            raise

    def record_spend(
        self,
        project_id: str,
        amount: Union[Decimal, str, float],
        category: str,
        description: str = None
    ) -> Dict[str, Any]:
        """
        Record spend after approval.

        This method calls approve_spend() (which raises if insufficient)
        and then creates a Transaction record for audit trail.

        Args:
            project_id: Project ID to record spend for
            amount: Amount to record (Decimal, string, or float)
            category: Category for the spend (e.g., "labor", "expenses")
            description: Optional description

        Returns:
            Dict with approval result and transaction details

        Raises:
            InsufficientBudgetError: If spend would exceed budget
            BudgetNotFoundError: If project doesn't exist
        """
        # Approve spend first (raises if insufficient)
        approval_result = self.approve_spend(project_id, amount, description)

        # Create transaction record
        from accounting.models import Transaction, TransactionStatus
        from datetime import datetime, timezone

        transaction = Transaction(
            workspace_id="",  # Will be filled from project
            external_id=None,
            source=f"budget_enforcement:{category}",
            status=TransactionStatus.POSTED,
            transaction_date=datetime.now(timezone.utc),
            description=description or f"{category} spend for project {project_id}",
            project_id=project_id,
            amount=float(to_decimal(amount)),  # Convert to float for DB
        )

        # Set workspace_id from project
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if project:
            transaction.workspace_id = project.workspace_id

        self.db.add(transaction)
        self.db.commit()

        # Return combined result
        return {
            **approval_result,
            "transaction_id": transaction.id,
            "category": category,
        }

    def get_budget_status(self, project_id: str) -> Dict[str, Any]:
        """
        Get full budget status for a project.

        Args:
            project_id: Project ID to get status for

        Returns:
            Dict with:
                - project_id: str
                - budget_amount: Decimal
                - actual_burn: Decimal
                - remaining: Decimal
                - budget_status: str
                - utilization_pct: Decimal

        Raises:
            BudgetNotFoundError: If project doesn't exist
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise BudgetNotFoundError(f"Project {project_id} not found")

        budget_amount = to_decimal(project.budget_amount or 0)
        actual_burn = to_decimal(project.actual_burn or 0)
        remaining = budget_amount - actual_burn

        utilization_pct = (
            round_money((actual_burn / budget_amount) * Decimal('100'))
            if budget_amount > 0
            else Decimal('0.00')
        )

        return {
            "project_id": project_id,
            "budget_amount": budget_amount,
            "actual_burn": actual_burn,
            "remaining": remaining,
            "budget_status": project.budget_status.value if project.budget_status else "on_track",
            "utilization_pct": utilization_pct,
        }
