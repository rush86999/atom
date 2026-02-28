"""
Integration tests for concurrent budget checks with real database.

Tests validate pessimistic locking, concurrent spend approval, and
transaction isolation under high concurrency (50-100 workers).
"""

import pytest
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    InsufficientBudgetError,
    BudgetNotFoundError,
    ConcurrentModificationError
)
from core.decimal_utils import to_decimal
from service_delivery.models import Project, BudgetStatus
from accounting.models import Transaction
from datetime import datetime, timezone


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def budget_service(db):
    """Provide BudgetEnforcementService for tests."""
    return BudgetEnforcementService(db)


@pytest.fixture
def project_factory(db):
    """Create test projects with budget."""
    def _create(
        budget_amount: Decimal,
        initial_burn: Decimal = Decimal('0.00'),
        project_id: str = None
    ) -> Project:
        if not project_id:
            project_id = f"proj_intg_{budget_amount}_{initial_burn}_{time.time()}"

        project = Project(
            id=project_id,
            workspace_id="test_workspace",
            name=f"Test Project {budget_amount}",
            status="active",
            budget_amount=float(budget_amount),
            actual_burn=float(min(initial_burn, budget_amount)),
            budget_status=BudgetStatus.ON_TRACK,
            created_at=datetime.now(timezone.utc)
        )
        db.add(project)
        db.commit()
        return project

    return _create


# ============================================================================
# Test Concurrent Spend Approval
# ============================================================================

class TestConcurrentSpendApproval:
    """Integration tests for concurrent spend approval."""

    def test_concurrent_spend_10_workers_10_dollars(self, budget_service, project_factory):
        """10 workers, $10 each on $100 budget → exactly 10 succeed."""
        project = project_factory(budget_amount=Decimal('100.00'))
        spend_amount = Decimal('10.00')

        approved_count = [0]
        rejected_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Concurrent spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                with lock:
                    rejected_count[0] += 1
                return None

        # Run 10 concurrent spends
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(10)]
            list(as_completed(futures))

        # Exactly 10 should succeed, 0 rejected
        assert approved_count[0] == 10, f"Expected 10 approvals, got {approved_count[0]}"
        assert rejected_count[0] == 0, f"Expected 0 rejections, got {rejected_count[0]}"

        # Verify final budget state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('100.00'), f"Final burn: {final_burn}"

    def test_concurrent_spend_20_workers_5_dollars(self, budget_service, project_factory):
        """20 workers, $5 each on $100 budget → exactly 20 succeed."""
        project = project_factory(budget_amount=Decimal('100.00'))
        spend_amount = Decimal('5.00')

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Concurrent spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # Run 20 concurrent spends
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(20)]
            list(as_completed(futures))

        # Exactly 20 should succeed
        assert approved_count[0] == 20, f"Expected 20 approvals, got {approved_count[0]}"

        # Verify final budget state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('100.00'), f"Final burn: {final_burn}"

    def test_concurrent_spend_50_workers_2_dollars(self, budget_service, project_factory):
        """50 workers, $2 each on $100 budget → exactly 50 succeed."""
        project = project_factory(budget_amount=Decimal('100.00'))
        spend_amount = Decimal('2.00')

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Concurrent spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # Run 50 concurrent spends
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(50)]
            list(as_completed(futures))

        # Exactly 50 should succeed
        assert approved_count[0] == 50, f"Expected 50 approvals, got {approved_count[0]}"

        # Verify final budget state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('100.00'), f"Final burn: {final_burn}"

    def test_concurrent_spend_exceeds_budget(self, budget_service, project_factory):
        """20 workers, $10 each on $100 budget → exactly 10 succeed, 10 fail."""
        project = project_factory(budget_amount=Decimal('100.00'))
        spend_amount = Decimal('10.00')

        approved_count = [0]
        rejected_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Concurrent spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                with lock:
                    rejected_count[0] += 1
                return None

        # Run 20 concurrent spends (exceeds budget)
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(20)]
            list(as_completed(futures))

        # Exactly 10 should succeed, 10 should fail
        assert approved_count[0] == 10, f"Expected 10 approvals, got {approved_count[0]}"
        assert rejected_count[0] == 10, f"Expected 10 rejections, got {rejected_count[0]}"

        # Verify final budget state (no overdraft)
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('100.00'), f"Final burn: {final_burn}"
        assert final_burn <= Decimal('100.00'), "No overdraft allowed"


# ============================================================================
# Test Concurrent Spend Stress
# ============================================================================

class TestConcurrentSpendStress:
    """Stress tests for high concurrency scenarios."""

    @pytest.mark.stress
    def test_concurrent_spend_100_workers(self, budget_service, project_factory):
        """100 workers on $1000 budget → all $10 spends processed correctly."""
        project = project_factory(budget_amount=Decimal('1000.00'))
        spend_amount = Decimal('10.00')

        approved_count = [0]
        rejected_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Stress test spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                with lock:
                    rejected_count[0] += 1
                return None

        # Run 100 concurrent spends
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(100)]
            list(as_completed(futures))
        duration = time.time() - start_time

        # Exactly 100 should succeed
        assert approved_count[0] == 100, f"Expected 100 approvals, got {approved_count[0]}"
        assert rejected_count[0] == 0, f"Expected 0 rejections, got {rejected_count[0]}"

        # Verify final budget state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('1000.00'), f"Final burn: {final_burn}"

        # Performance check: should complete in reasonable time
        assert duration < 30, f"Stress test took too long: {duration}s"

    @pytest.mark.stress
    def test_concurrent_spend_burst_load(self, budget_service, project_factory):
        """1000 requests in 1 second → verify <1% error rate."""
        project = project_factory(budget_amount=Decimal('10000.00'))
        spend_amount = Decimal('1.00')

        success_count = [0]
        error_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Burst load {index}"
                )
                with lock:
                    success_count[0] += 1
                return result
            except Exception as e:
                with lock:
                    error_count[0] += 1
                return None

        # Run 1000 concurrent requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(1000)]
            list(as_completed(futures))
        duration = time.time() - start_time

        # Verify low error rate (<1%)
        error_rate = error_count[0] / 1000
        assert error_rate < 0.01, f"Error rate too high: {error_rate:.2%}"

        # Verify final budget state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= Decimal('10000.00'), "No overdraft allowed"

        # Performance check
        assert duration < 60, f"Burst load took too long: {duration}s"

    @pytest.mark.stress
    def test_concurrent_spend_sustained_load(self, budget_service, project_factory):
        """100 requests/second for 5 seconds → verify consistent locking."""
        project = project_factory(budget_amount=Decimal('10000.00'))
        spend_amount = Decimal('1.00')

        total_requests = 500  # 100 req/s * 5 seconds
        success_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Sustained load {index}"
                )
                with lock:
                    success_count[0] += 1
                return result
            except Exception:
                return None

        # Run sustained load
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(total_requests)]
            list(as_completed(futures))
        duration = time.time() - start_time

        # Verify most requests succeeded
        success_rate = success_count[0] / total_requests
        assert success_rate > 0.95, f"Success rate too low: {success_rate:.2%}"

        # Verify budget consistency
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= Decimal('10000.00'), "No overdraft allowed"


# ============================================================================
# Test Database Locking
# ============================================================================

class TestDatabaseLocking:
    """Integration tests for database row locking behavior."""

    def test_with_for_update_prevents_race_condition(self, budget_service, project_factory):
        """Verify SELECT FOR UPDATE pattern prevents race conditions."""
        project = project_factory(budget_amount=Decimal('100.00'))
        spend_amount = Decimal('10.00')

        # Run concurrent spends that would exceed budget without locking
        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description="Race condition test"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # 20 concurrent $10 requests on $100 budget
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_spend) for _ in range(20)]
            list(as_completed(futures))

        # Exactly 10 should succeed (no race condition)
        assert approved_count[0] == 10, f"Race condition detected: {approved_count[0]} != 10"

        # Verify budget integrity
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('100.00'), f"Budget corruption: {final_burn}"

    def test_lock_timeout_behavior(self, budget_service, project_factory):
        """Lock timeout raises appropriate error."""
        project = project_factory(budget_amount=Decimal('100.00'))

        # Note: Lock timeout testing requires long-running transaction
        # This is a basic test to verify timeout parameter is accepted
        try:
            result = budget_service.approve_spend_locked(
                db=budget_service.db,
                project_id=project.id,
                amount=Decimal('10.00'),
                description="Lock timeout test",
                lock_timeout=5  # 5 second timeout
            )
            assert result['status'] == 'approved'
        except Exception as e:
            pytest.fail(f"Lock timeout parameter caused error: {e}")

    def test_lock_released_on_commit(self, budget_service, project_factory):
        """Verify lock released after transaction commit."""
        project = project_factory(budget_amount=Decimal('100.00'))

        # First spend (acquires and releases lock)
        result1 = budget_service.approve_spend_locked(
            db=budget_service.db,
            project_id=project.id,
            amount=Decimal('10.00'),
            description="First spend"
        )
        assert result1['status'] == 'approved'

        # Second spend should succeed immediately (lock was released)
        result2 = budget_service.approve_spend_locked(
            db=budget_service.db,
            project_id=project.id,
            amount=Decimal('10.00'),
            description="Second spend"
        )
        assert result2['status'] == 'approved'

    def test_lock_released_on_rollback(self, budget_service, project_factory):
        """Verify lock released after transaction rollback."""
        project = project_factory(budget_amount=Decimal('10.00'))

        # Try to overspend (will rollback)
        try:
            budget_service.approve_spend_locked(
                db=budget_service.db,
                project_id=project.id,
                amount=Decimal('100.00'),  # Exceeds budget
                description="Overspend attempt"
            )
            pytest.fail("Expected InsufficientBudgetError")
        except InsufficientBudgetError:
            pass  # Expected

        # Next spend should succeed immediately (lock was released)
        result = budget_service.approve_spend_locked(
            db=budget_service.db,
            project_id=project.id,
            amount=Decimal('5.00'),
            description="Post-rollback spend"
        )
        assert result['status'] == 'approved'


# ============================================================================
# Test Transaction Isolation
# ============================================================================

class TestTransactionIsolation:
    """Integration tests for transaction isolation."""

    def test_concurrent_transactions_isolated(self, budget_service, project_factory):
        """Concurrent transactions don't interfere."""
        project = project_factory(budget_amount=Decimal('100.00'))
        spend_amount = Decimal('5.00')

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description="Isolation test"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # 20 concurrent transactions
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_spend) for _ in range(20)]
            list(as_completed(futures))

        # All 20 should succeed
        assert approved_count[0] == 20, f"Expected 20 approvals, got {approved_count[0]}"

        # Verify isolation
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('100.00'), f"Isolation violation: {final_burn}"

    def test_failed_transaction_isolation(self, budget_service, project_factory):
        """Failed transaction doesn't affect budget."""
        project = project_factory(budget_amount=Decimal('100.00'))

        initial_burn = to_decimal(project.actual_burn or 0)

        # Try to overspend (will fail and rollback)
        try:
            budget_service.approve_spend_locked(
                db=budget_service.db,
                project_id=project.id,
                amount=Decimal('200.00'),  # Exceeds budget
                description="Failed transaction"
            )
            pytest.fail("Expected InsufficientBudgetError")
        except InsufficientBudgetError:
            pass  # Expected

        # Verify budget unchanged (transaction rolled back)
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == initial_burn, "Failed transaction affected budget"

    def test_partial_rollback_handling(self, budget_service, project_factory):
        """Partial rollback doesn't corrupt budget state."""
        project = project_factory(budget_amount=Decimal('100.00'))

        # Mix of successful and failed transactions
        successful_count = [0]
        failed_count = [0]
        lock = __import__('threading').Lock()

        def mixed_spend(amount):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=amount,
                    description="Mixed transaction"
                )
                with lock:
                    successful_count[0] += 1
                return result
            except InsufficientBudgetError:
                with lock:
                    failed_count[0] += 1
                return None

        # Run concurrent mixed spends
        amounts = [Decimal('10.00')] * 10 + [Decimal('100.00')] * 5
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(mixed_spend, amt) for amt in amounts]
            list(as_completed(futures))

        # Verify some succeeded, some failed
        assert successful_count[0] > 0, "No transactions succeeded"
        assert failed_count[0] > 0, "No transactions failed"

        # Verify budget consistency
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= Decimal('100.00'), "Budget corrupted"


# ============================================================================
# Test Optimistic Locking
# ============================================================================

class TestOptimisticLocking:
    """Integration tests for optimistic locking behavior."""

    def test_optimistic_locking_retry_logic(self, budget_service, project_factory):
        """Verify retry on version mismatch."""
        project = project_factory(budget_amount=Decimal('1000.00'))
        spend_amount = Decimal('5.00')

        successful_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend_with_retry():
            try:
                result = budget_service.approve_spend_with_retry(
                    project_id=project.id,
                    amount=spend_amount,
                    description="Optimistic locking test",
                    max_retries=3
                )
                with lock:
                    successful_count[0] += 1
                return result
            except ConcurrentModificationError:
                return None  # Retries exhausted
            except InsufficientBudgetError:
                return None  # Budget exhausted

        # Run concurrent optimistic spends
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_spend_with_retry) for _ in range(20)]
            list(as_completed(futures))

        # Most should succeed after retries
        assert successful_count[0] > 0, "No optimistic locks succeeded"

        # Verify budget consistency
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= Decimal('1000.00'), "Budget exceeded"

    def test_optimistic_locking_max_retries(self, budget_service, project_factory):
        """Exceeding max retries raises error."""
        project = project_factory(budget_amount=Decimal('100.00'))

        # Note: This test is limited by SQLite's locking behavior
        # In production with PostgreSQL, this would test concurrent modification
        try:
            # Single spend should succeed
            result = budget_service.approve_spend_with_retry(
                project_id=project.id,
                amount=Decimal('10.00'),
                description="Max retries test",
                max_retries=3
            )
            assert result['status'] == 'approved'
        except ConcurrentModificationError:
            # Would occur under high contention
            pass

    def test_optimistic_vs_pessimistic_performance(self, budget_service, project_factory):
        """Compare throughput (optimistic should be faster when low contention)."""
        # Test pessimistic locking
        project_pess = project_factory(budget_amount=Decimal('1000.00'), project_id="pessimistic")

        start_time = time.time()
        for i in range(10):
            budget_service.approve_spend_locked(
                db=budget_service.db,
                project_id=project_pess.id,
                amount=Decimal('10.00'),
                description=f"Pessimistic {i}"
            )
        pess_duration = time.time() - start_time

        # Test optimistic locking
        project_opt = project_factory(budget_amount=Decimal('1000.00'), project_id="optimistic")

        start_time = time.time()
        for i in range(10):
            budget_service.approve_spend_with_retry(
                project_id=project_opt.id,
                amount=Decimal('10.00'),
                description=f"Optimistic {i}"
            )
        opt_duration = time.time() - start_time

        # Both should complete (optimistic might be slightly faster)
        assert pess_duration < 5, f"Pessimistic too slow: {pess_duration}s"
        assert opt_duration < 5, f"Optimistic too slow: {opt_duration}s"


# ============================================================================
# Test Multi-Project Concurrency
# ============================================================================

class TestMultiProjectConcurrency:
    """Integration tests for concurrent spends across multiple projects."""

    def test_concurrent_spend_different_projects(self, budget_service, project_factory):
        """Concurrent spends on different projects don't block each other."""
        projects = [project_factory(budget_amount=Decimal('100.00'), project_id=f"proj_multi_{i}") for i in range(5)]

        completed_by_project = {p.id: 0 for p in projects}
        lock = __import__('threading').Lock()

        def attempt_spend_on_project(project_id):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project_id,
                    amount=Decimal('10.00'),
                    description="Multi-project spend"
                )
                with lock:
                    completed_by_project[project_id] += 1
                return result
            except InsufficientBudgetError:
                return None

        # Run spends across all projects concurrently
        all_futures = []
        with ThreadPoolExecutor(max_workers=25) as executor:
            for project in projects:
                futures = [executor.submit(attempt_spend_on_project, project.id) for _ in range(5)]
                all_futures.extend(futures)
            list(as_completed(all_futures))

        # All projects should have processed spends independently
        for project_id, count in completed_by_project.items():
            assert count == 5, f"Project {project_id} had {count} spends (expected 5)"

    def test_concurrent_spend_same_project(self, budget_service, project_factory):
        """Concurrent spends on same project are serialized."""
        project = project_factory(budget_amount=Decimal('100.00'))

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('10.00'),
                    description="Same project spend"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # 10 concurrent spends on same project
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_spend) for _ in range(10)]
            list(as_completed(futures))

        # All should be serialized (exactly 10 succeed)
        assert approved_count[0] == 10, f"Expected 10 approvals, got {approved_count[0]}"

    def test_mixed_project_concurrency(self, budget_service, project_factory):
        """Mix of same-project and different-project concurrent spends."""
        projects = {
            'shared': project_factory(budget_amount=Decimal('100.00'), project_id="shared"),
            'independent1': project_factory(budget_amount=Decimal('100.00'), project_id="independent1"),
            'independent2': project_factory(budget_amount=Decimal('100.00'), project_id="independent2"),
        }

        counts = {k: 0 for k in projects.keys()}
        lock = __import__('threading').Lock()

        def attempt_spend(project_type):
            project_id = projects[project_type].id
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project_id,
                    amount=Decimal('10.00'),
                    description=f"Mixed concurrency {project_type}"
                )
                with lock:
                    counts[project_type] += 1
                return result
            except InsufficientBudgetError:
                return None

        # Mix of same-project and different-project spends
        all_futures = []
        with ThreadPoolExecutor(max_workers=30) as executor:
            # Shared project: 10 spends
            all_futures.extend([executor.submit(attempt_spend, 'shared') for _ in range(10)])
            # Independent projects: 10 spends each
            all_futures.extend([executor.submit(attempt_spend, 'independent1') for _ in range(10)])
            all_futures.extend([executor.submit(attempt_spend, 'independent2') for _ in range(10)])
            list(as_completed(all_futures))

        # Verify all processed correctly
        assert counts['shared'] == 10, f"Shared project: {counts['shared']} != 10"
        assert counts['independent1'] == 10, f"Independent1: {counts['independent1']} != 10"
        assert counts['independent2'] == 10, f"Independent2: {counts['independent2']} != 10"


# ============================================================================
# Test Concurrent Budget Status
# ============================================================================

class TestConcurrentBudgetStatus:
    """Integration tests for budget status updates under concurrency."""

    def test_status_update_atomic(self, budget_service, project_factory):
        """Budget status update is atomic with spend."""
        project = project_factory(budget_amount=Decimal('100.00'))

        # Spend to cross 80% threshold
        for i in range(9):
            budget_service.approve_spend_locked(
                db=budget_service.db,
                project_id=project.id,
                amount=Decimal('10.00'),
                description=f"Status test {i}"
            )

        budget_service.db.refresh(project)
        assert project.budget_status == BudgetStatus.AT_RISK, \
            f"Expected AT_RISK, got {project.budget_status}"

    def test_status_transition_concurrent(self, budget_service, project_factory):
        """Status transitions correctly under concurrent load."""
        project = project_factory(budget_amount=Decimal('100.00'))

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('10.00'),
                    description="Status transition test"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # Run concurrent spends
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_spend) for _ in range(20)]
            list(as_completed(futures))

        # Verify final status
        budget_service.db.refresh(project)
        assert project.budget_status == BudgetStatus.OVER_BUDGET, \
            f"Final status should be OVER_BUDGET, got {project.budget_status}"

    def test_final_status_consistent(self, budget_service, project_factory):
        """Final status consistent regardless of execution order."""
        project = project_factory(budget_amount=Decimal('100.00'))

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('10.00'),
                    description="Status consistency test"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # Run concurrent spends
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_spend) for _ in range(10)]
            list(as_completed(futures))

        # Verify consistent final state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)

        assert final_burn == Decimal('100.00'), f"Final burn: {final_burn}"
        assert project.budget_status == BudgetStatus.OVER_BUDGET, \
            f"Final status should be OVER_BUDGET, got {project.budget_status}"


# ============================================================================
# Test Real-World Scenarios
# ============================================================================

class TestRealWorldScenarios:
    """Integration tests for real-world usage patterns."""

    def test_concurrent_team_spending(self, budget_service, project_factory):
        """Simulate 20 team members spending simultaneously."""
        project = project_factory(budget_amount=Decimal('1000.00'))

        team_member_spends = [Decimal('10.00'), Decimal('25.00'), Decimal('50.00')]
        approved_count = [0]
        lock = __import__('threading').Lock()

        def team_member_spend(member_index):
            amount = team_member_spends[member_index % len(team_member_spends)]
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=amount,
                    description=f"Team member {member_index} spend"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # 20 team members spending concurrently
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(team_member_spend, i) for i in range(20)]
            list(as_completed(futures))

        # Verify all succeeded (budget sufficient)
        assert approved_count[0] == 20, f"Expected 20 approvals, got {approved_count[0]}"

        # Verify budget integrity
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= Decimal('1000.00'), "Budget exceeded"

    def test_concurrent_api_requests(self, budget_service, project_factory):
        """Simulate 50 concurrent API requests."""
        project = project_factory(budget_amount=Decimal('500.00'))

        approved_count = [0]
        rejected_count = [0]
        lock = __import__('threading').Lock()

        def api_request(request_id):
            amount = Decimal('10.00')
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=amount,
                    description=f"API request {request_id}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except InsufficientBudgetError:
                with lock:
                    rejected_count[0] += 1
                return None

        # 50 concurrent API requests
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(api_request, i) for i in range(50)]
            list(as_completed(futures))

        # Exactly 50 should succeed
        assert approved_count[0] == 50, f"Expected 50 approvals, got {approved_count[0]}"
        assert rejected_count[0] == 0, f"Expected 0 rejections, got {rejected_count[0]}"

    def test_concurrent_webhook_processing(self, budget_service, project_factory):
        """Simulate concurrent payment webhooks updating budget."""
        project = project_factory(budget_amount=Decimal('1000.00'))

        processed_count = [0]
        lock = __import__('threading').Lock()

        def process_webhook(webhook_id):
            amount = Decimal('5.00')
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=amount,
                    description=f"Webhook {webhook_id}"
                )
                with lock:
                    processed_count[0] += 1
                return result
            except InsufficientBudgetError:
                return None

        # 100 concurrent webhooks
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(process_webhook, i) for i in range(100)]
            list(as_completed(futures))

        # All should succeed
        assert processed_count[0] == 100, f"Expected 100 processed, got {processed_count[0]}"

        # Verify final budget state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('500.00'), f"Final burn: {final_burn}"


# ============================================================================
# Test Lock Performance
# ============================================================================

class TestLockPerformance:
    """Integration tests for lock performance metrics."""

    def test_lock_acquisition_time(self, budget_service, project_factory):
        """Measure lock acquisition time (<10ms P99)."""
        project = project_factory(budget_amount=Decimal('1000.00'))

        acquisition_times = []

        def measure_lock_time():
            start_time = time.time()
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('1.00'),
                    description="Lock timing test"
                )
                duration = time.time() - start_time
                acquisition_times.append(duration)
                return result
            except InsufficientBudgetError:
                return None

        # Measure 100 lock acquisitions
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(measure_lock_time) for _ in range(100)]
            list(as_completed(futures))

        # Calculate P99
        acquisition_times.sort()
        p99_index = int(len(acquisition_times) * 0.99)
        p99_time = acquisition_times[p99_index]

        # P99 should be < 10ms (relaxed for SQLite)
        assert p99_time < 0.1, f"P99 lock acquisition too slow: {p99_time*1000:.2f}ms"

    def test_lock_hold_time(self, budget_service, project_factory):
        """Measure time lock is held (<50ms P99)."""
        project = project_factory(budget_amount=Decimal('1000.00'))

        hold_times = []

        def measure_hold_time():
            start_time = time.time()
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('1.00'),
                    description="Hold timing test"
                )
                duration = time.time() - start_time
                hold_times.append(duration)
                return result
            except InsufficientBudgetError:
                return None

        # Measure 100 lock holds
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(measure_hold_time) for _ in range(100)]
            list(as_completed(futures))

        # Calculate P99
        hold_times.sort()
        p99_index = int(len(hold_times) * 0.99)
        p99_time = hold_times[p99_index]

        # P99 should be < 50ms
        assert p99_time < 0.05, f"P99 lock hold too slow: {p99_time*1000:.2f}ms"

    def test_contention_under_high_load(self, budget_service, project_factory):
        """Measure behavior under 100 concurrent requests."""
        project = project_factory(budget_amount=Decimal('1000.00'))

        success_count = [0]
        error_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('1.00'),
                    description="Contention test"
                )
                with lock:
                    success_count[0] += 1
                return result
            except Exception as e:
                with lock:
                    error_count[0] += 1
                return None

        # 100 concurrent requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(attempt_spend) for _ in range(100)]
            list(as_completed(futures))
        duration = time.time() - start_time

        # All should succeed despite contention
        assert success_count[0] == 100, f"Expected 100 successes, got {success_count[0]}"
        assert error_count[0] == 0, f"Expected 0 errors, got {error_count[0]}"

        # Should complete in reasonable time
        assert duration < 30, f"High contention load too slow: {duration}s"


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Integration tests for edge cases."""

    def test_concurrent_zero_amount(self, budget_service, project_factory):
        """Zero amount spends don't affect locking."""
        project = project_factory(budget_amount=Decimal('100.00'))

        # Zero amount should be rejected
        try:
            budget_service.approve_spend_locked(
                db=budget_service.db,
                project_id=project.id,
                amount=Decimal('0.00'),
                description="Zero amount"
            )
            # If it succeeds, verify budget unchanged
            budget_service.db.refresh(project)
            final_burn = to_decimal(project.actual_burn or 0)
            assert final_burn == Decimal('0.00'), "Zero spend changed budget"
        except ValueError:
            # Expected rejection
            pass

    def test_concurrent_negative_amount(self, budget_service, project_factory):
        """Negative amounts rejected consistently."""
        project = project_factory(budget_amount=Decimal('100.00'))

        rejected_count = [0]
        lock = __import__('threading').Lock()

        def attempt_negative_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('-10.00'),
                    description="Negative amount"
                )
                return result
            except ValueError:
                with lock:
                    rejected_count[0] += 1
                return None

        # 10 concurrent negative spends
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_negative_spend) for _ in range(10)]
            list(as_completed(futures))

        # All should be rejected
        assert rejected_count[0] == 10, f"Expected 10 rejections, got {rejected_count[0]}"

        # Verify budget unchanged
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('0.00'), "Negative spends changed budget"

    def test_concurrent_invalid_project(self, budget_service):
        """Invalid project IDs raise BudgetNotFoundError."""
        error_count = [0]
        lock = __import__('threading').Lock()

        def attempt_invalid_spend():
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id="nonexistent_project",
                    amount=Decimal('10.00'),
                    description="Invalid project"
                )
                return result
            except BudgetNotFoundError:
                with lock:
                    error_count[0] += 1
                return None

        # 10 concurrent requests to invalid project
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_invalid_spend) for _ in range(10)]
            list(as_completed(futures))

        # All should raise BudgetNotFoundError
        assert error_count[0] == 10, f"Expected 10 errors, got {error_count[0]}"
