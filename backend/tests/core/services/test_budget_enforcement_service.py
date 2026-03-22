"""
Tests for BudgetEnforcementService

Tests for budget enforcement service including:
- Budget checking
- Spend approval
- Atomic transactions
- Pessimistic locking
- Optimistic locking
- Budget status tracking
"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    BudgetError,
    InsufficientBudgetError,
    BudgetNotFoundError,
    ConcurrentModificationError,
)
from service_delivery.models import Project, BudgetStatus


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")

    # Import and create all tables
    from service_delivery.models import Base
    from accounting.models import Base as AccountingBase
    Base.metadata.create_all(engine)
    AccountingBase.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def budget_service(db_session):
    """Create budget enforcement service instance."""
    return BudgetEnforcementService(db_session)


@pytest.fixture
def test_project(db_session):
    """Create a test project."""
    project = Project(
        id="project-1",
        workspace_id="workspace-1",
        name="Test Project",
        budget_amount=10000.0,
        actual_burn=2000.0,
        budget_status=BudgetStatus.ON_TRACK,
    )
    db_session.add(project)
    db_session.commit()
    return project


class TestBudgetEnforcementServiceInit:
    """Tests for BudgetEnforcementService initialization."""

    def test_init_with_db(self, db_session):
        """Test initialization with database session."""
        service = BudgetEnforcementService(db_session)
        assert service.db == db_session


class TestCheckBudget:
    """Tests for check_budget method."""

    def test_check_budget_within_limit(self, budget_service, test_project):
        """Test checking budget that is within limit."""
        result = budget_service.check_budget(
            project_id=test_project.id,
            amount=5000.0
        )

        assert result["allowed"] is True
        assert result["remaining"] == Decimal("8000.0")
        assert result["budget_status"] == "on_track"

    def test_check_budget_exceeds_limit(self, budget_service, test_project):
        """Test checking budget that exceeds limit."""
        result = budget_service.check_budget(
            project_id=test_project.id,
            amount=9000.0  # More than remaining (8000)
        )

        assert result["allowed"] is False
        assert result["remaining"] == Decimal("8000.0")

    def test_check_budget_with_decimal(self, budget_service, test_project):
        """Test checking budget with Decimal amount."""
        result = budget_service.check_budget(
            project_id=test_project.id,
            amount=Decimal("1000.50")
        )

        assert result["allowed"] is True
        assert result["remaining"] == Decimal("7999.50")

    def test_check_budget_with_string(self, budget_service, test_project):
        """Test checking budget with string amount."""
        result = budget_service.check_budget(
            project_id=test_project.id,
            amount="2500.75"
        )

        assert result["allowed"] is True
        assert result["remaining"] == Decimal("7499.25")

    def test_check_budget_negative_amount(self, budget_service, test_project):
        """Test checking budget with negative amount."""
        with pytest.raises(ValueError, match="cannot be negative"):
            budget_service.check_budget(
                project_id=test_project.id,
                amount=-100.0
            )

    def test_check_budget_project_not_found(self, budget_service):
        """Test checking budget for non-existent project."""
        with pytest.raises(BudgetNotFoundError):
            budget_service.check_budget(
                project_id="non-existent",
                amount=100.0
            )

    def test_check_budget_utilization_calculation(self, budget_service, test_project):
        """Test budget utilization percentage calculation."""
        result = budget_service.check_budget(
            project_id=test_project.id,
            amount=0
        )

        # 2000 / 10000 = 20%
        assert result["utilization_pct"] == Decimal("20.00")


class TestApproveSpend:
    """Tests for approve_spend method."""

    def test_approve_spend_success(self, budget_service, test_project):
        """Test successful spend approval."""
        result = budget_service.approve_spend(
            project_id=test_project.id,
            amount=1000.0,
            description="Test spend"
        )

        assert result["approved"] is True
        assert result["remaining"] < Decimal("8000.0")  # Updated remaining

        # Verify database was updated
        budget_service.db.refresh(test_project)
        assert test_project.actual_burn == 3000.0

    def test_approve_spend_insufficient_budget(self, budget_service, test_project):
        """Test spend approval with insufficient budget."""
        with pytest.raises(InsufficientBudgetError):
            budget_service.approve_spend(
                project_id=test_project.id,
                amount=9000.0  # More than remaining
            )

    def test_approve_spend_project_not_found(self, budget_service):
        """Test spend approval for non-existent project."""
        with pytest.raises(BudgetNotFoundError):
            budget_service.approve_spend(
                project_id="non-existent",
                amount=100.0
            )

    def test_approve_spend_negative_amount(self, budget_service, test_project):
        """Test spend approval with negative amount."""
        with pytest.raises(ValueError):
            budget_service.approve_spend(
                project_id=test_project.id,
                amount=-100.0
            )

    def test_approve_spend_updates_budget_status(self, budget_service, test_project, db_session):
        """Test that spend approval updates budget status."""
        # Set actual burn to near budget limit
        test_project.actual_burn = 8500.0
        db_session.commit()

        result = budget_service.approve_spend(
            project_id=test_project.id,
            amount=1000.0
        )

        # Should move to AT_RISK or OVER_BUDGET
        assert result["budget_status"] in [BudgetStatus.AT_RISK.value, BudgetStatus.OVER_BUDGET.value]

    def test_approve_spend_rollback_on_error(self, budget_service, test_project, db_session):
        """Test that errors trigger rollback."""
        initial_burn = test_project.actual_burn

        with patch.object(budget_service.db, 'commit', side_effect=Exception("DB error")):
            with pytest.raises(Exception):
                budget_service.approve_spend(
                    project_id=test_project.id,
                    amount=1000.0
                )

        # Verify rollback happened
        budget_service.db.refresh(test_project)
        assert test_project.actual_burn == initial_burn


class TestRecordSpend:
    """Tests for record_spend method."""

    def test_record_spend_success(self, budget_service, test_project):
        """Test successful spend recording."""
        result = budget_service.record_spend(
            project_id=test_project.id,
            amount=500.0,
            category="labor",
            description="Hourly work"
        )

        assert result["approved"] is True
        assert "transaction_id" in result
        assert result["category"] == "labor"

    def test_record_spend_creates_transaction(self, budget_service, test_project):
        """Test that record_spend creates transaction."""
        result = budget_service.record_spend(
            project_id=test_project.id,
            amount=500.0,
            category="expenses"
        )

        from accounting.models import Transaction
        transaction = budget_service.db.query(Transaction).filter(
            Transaction.id == result["transaction_id"]
        ).first()

        assert transaction is not None
        assert transaction.amount == 500.0

    def test_record_spend_insufficient_budget(self, budget_service, test_project):
        """Test record_spend with insufficient budget."""
        with pytest.raises(InsufficientBudgetError):
            budget_service.record_spend(
                project_id=test_project.id,
                amount=9000.0,
                category="labor"
            )


class TestGetBudgetStatus:
    """Tests for get_budget_status method."""

    def test_get_budget_status(self, budget_service, test_project):
        """Test getting budget status."""
        result = budget_service.get_budget_status(
            project_id=test_project.id
        )

        assert result["project_id"] == test_project.id
        assert result["budget_amount"] == Decimal("10000.0")
        assert result["actual_burn"] == Decimal("2000.0")
        assert result["remaining"] == Decimal("8000.0")
        assert result["utilization_pct"] == Decimal("20.00")

    def test_get_budget_status_project_not_found(self, budget_service):
        """Test getting status for non-existent project."""
        with pytest.raises(BudgetNotFoundError):
            budget_service.get_budget_status("non-existent")


class TestApproveSpendLocked:
    """Tests for approve_spend_locked method (pessimistic locking)."""

    def test_approve_spend_locked_success(self, budget_service, test_project):
        """Test spend approval with pessimistic locking."""
        result = budget_service.approve_spend_locked(
            project_id=test_project.id,
            amount=1000.0,
            description="Locked spend"
        )

        assert result["status"] == "approved"
        assert result["amount"] == Decimal("1000.0")
        assert "remaining" in result

    def test_approve_spend_locked_insufficient(self, budget_service, test_project):
        """Test locked spend approval with insufficient budget."""
        with pytest.raises(InsufficientBudgetError):
            budget_service.approve_spend_locked(
                project_id=test_project.id,
                amount=9000.0
            )

    def test_approve_spend_locked_rollback(self, budget_service, test_project):
        """Test that locked approval rolls back on error."""
        initial_burn = test_project.actual_burn

        with patch.object(budget_service.db, 'begin', side_effect=Exception("Lock error")):
            with pytest.raises(Exception):
                budget_service.approve_spend_locked(
                    project_id=test_project.id,
                    amount=1000.0
                )

        # Verify rollback
        budget_service.db.refresh(test_project)
        assert test_project.actual_burn == initial_burn


class TestApproveSpendWithRetry:
    """Tests for approve_spend_with_retry method (optimistic locking)."""

    def test_approve_spend_with_retry_success(self, budget_service, test_project):
        """Test spend approval with optimistic locking."""
        result = budget_service.approve_spend_with_retry(
            project_id=test_project.id,
            amount=1000.0,
            description="Optimistic spend",
            max_retries=3
        )

        assert result["status"] == "approved"
        assert result["amount"] == Decimal("1000.0")

    def test_approve_spend_with_retry_insufficient(self, budget_service, test_project):
        """Test optimistic approval with insufficient budget."""
        with pytest.raises(InsufficientBudgetError):
            budget_service.approve_spend_with_retry(
                project_id=test_project.id,
                amount=9000.0
            )

    def test_approve_spend_with_retry_concurrent_modification(self, budget_service, test_project):
        """Test optimistic locking retry on concurrent modification."""
        from core.budget_enforcement_service import StaleDataError

        call_count = 0

        def mock_commit():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise StaleDataError("Concurrent modification")

        with patch.object(budget_service.db, 'commit', side_effect=mock_commit):
            result = budget_service.approve_spend_with_retry(
                project_id=test_project.id,
                amount=1000.0,
                max_retries=3
            )

            # Should succeed on second try
            assert result["status"] == "approved"

    def test_approve_spend_with_retry_max_retries_exceeded(self, budget_service, test_project):
        """Test optimistic locking when max retries exceeded."""
        from core.budget_enforcement_service import StaleDataError

        with patch.object(budget_service.db, 'commit', side_effect=StaleDataError("Always busy")):
            with pytest.raises(ConcurrentModificationError, match="max retries"):
                budget_service.approve_spend_with_retry(
                    project_id=test_project.id,
                    amount=1000.0,
                    max_retries=3
                )


class TestBudgetErrors:
    """Tests for budget exception classes."""

    def test_insufficient_budget_error(self):
        """Test InsufficientBudgetError properties."""
        error = InsufficientBudgetError(
            requested=Decimal("100.0"),
            remaining=Decimal("50.0"),
            budget_id="budget-1"
        )

        assert error.requested == Decimal("100.0")
        assert error.remaining == Decimal("50.0")
        assert error.budget_id == "budget-1"
        assert "100" in str(error)
        assert "50" in str(error)

    def test_budget_not_found_error(self):
        """Test BudgetNotFoundError."""
        error = BudgetNotFoundError("Project not found")

        assert "Project not found" in str(error)

    def test_concurrent_modification_error(self):
        """Test ConcurrentModificationError."""
        error = ConcurrentModificationError("Concurrent update detected")

        assert "Concurrent update detected" in str(error)


class TestBudgetStatusTransitions:
    """Tests for budget status transitions."""

    def test_transition_to_at_risk(self, budget_service, test_project, db_session):
        """Test transition to AT_RISK status."""
        # Set burn to 80% of budget
        test_project.actual_burn = 8000.0
        db_session.commit()

        budget_service.approve_spend(
            project_id=test_project.id,
            amount=500.0
        )

        db_session.refresh(test_project)
        assert test_project.budget_status == BudgetStatus.AT_RISK

    def test_transition_to_over_budget(self, budget_service, test_project, db_session):
        """Test transition to OVER_BUDGET status."""
        # Set burn to 100% of budget
        test_project.actual_burn = 10000.0
        db_session.commit()

        budget_service.approve_spend(
            project_id=test_project.id,
            amount=100.0
        )

        db_session.refresh(test_project)
        assert test_project.budget_status == BudgetStatus.OVER_BUDGET

    def test_stay_on_track(self, budget_service, test_project, db_session):
        """Test staying ON_TRACK with low utilization."""
        test_project.actual_burn = 1000.0  # 10%
        db_session.commit()

        budget_service.approve_spend(
            project_id=test_project.id,
            amount=1000.0
        )

        db_session.refresh(test_project)
        assert test_project.budget_status == BudgetStatus.ON_TRACK


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_budget_amount(self, budget_service, db_session):
        """Test project with zero budget."""
        project = Project(
            id="zero-budget",
            workspace_id="workspace-1",
            name="Zero Budget Project",
            budget_amount=0.0,
            actual_burn=0.0,
            budget_status=BudgetStatus.ON_TRACK,
        )
        db_session.add(project)
        db_session.commit()

        result = budget_service.check_budget(
            project_id="zero-budget",
            amount=100.0
        )

        assert result["allowed"] is False

    def test_zero_remaining_budget(self, budget_service, db_session):
        """Test project with zero remaining budget."""
        project = Project(
            id="no-remaining",
            workspace_id="workspace-1",
            name="No Remaining Project",
            budget_amount=1000.0,
            actual_burn=1000.0,
            budget_status=BudgetStatus.OVER_BUDGET,
        )
        db_session.add(project)
        db_session.commit()

        result = budget_service.check_budget(
            project_id="no-remaining",
            amount=0.01
        )

        assert result["allowed"] is False

    def test_exact_budget_match(self, budget_service, test_project):
        """Test spend that exactly matches remaining budget."""
        # Remaining is 8000
        result = budget_service.check_budget(
            project_id=test_project.id,
            amount=8000.0
        )

        assert result["allowed"] is True
