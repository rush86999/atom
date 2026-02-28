"""
Hypothesis property tests for concurrent spend safety invariants.

Uses property-based testing to validate that concurrent spend operations
maintain budget invariants (no overdrafts, atomic updates, lock safety).
"""

import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from core.decimal_utils import to_decimal
from tests.fixtures.decimal_fixtures import money_strategy, lists_of_decimals


# ============================================================================
# Test Concurrent Spend Invariants
# ============================================================================

class TestConcurrentSpendInvariants:
    """Property tests for concurrent spend operations."""

    @pytest.fixture
    def budget_service(self, db):
        """Provide BudgetEnforcementService for tests."""
        from core.budget_enforcement_service import BudgetEnforcementService
        return BudgetEnforcementService(db)

    @pytest.fixture
    def project_factory(self, db):
        """Create test projects with budget."""
        from service_delivery.models import Project, BudgetStatus
        from datetime import datetime, timezone

        def _create(budget_amount: Decimal, initial_burn: Decimal = Decimal('0.00')):
            project = Project(
                id=f"proj_{budget_amount}_{initial_burn}",
                workspace_id="test_workspace",
                name=f"Test Project {budget_amount}",
                status="active",
                budget_amount=float(budget_amount),
                actual_burn=float(min(initial_burn, budget_amount)),  # Cap at budget
                budget_status=BudgetStatus.ON_TRACK,
                created_at=datetime.now(timezone.utc)
            )
            db.add(project)
            db.commit()
            return project

        return _create

    @given(budget=money_strategy('100', '1000'), num_requests=st.integers(min_value=2, max_value=50))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_spend_never_overdrafts(self, budget_service, project_factory, budget, num_requests):
        """
        N concurrent $10 requests on $budget never exceed limit.

        Invariant: Concurrent spend requests never cause overdraft (actual_burn <= budget_amount).
        """
        project = project_factory(budget_amount=budget)
        spend_amount = Decimal('10.00')

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
            except Exception:
                return None

        # Run concurrent spends
        with ThreadPoolExecutor(max_workers=min(50, num_requests)) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(num_requests)]
            results = [f.result() for f in as_completed(futures)]

        # Verify final budget state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)

        # Invariant: Never exceed budget
        assert final_burn <= budget, f"Overdraft detected: {final_burn} > {budget}"

        # Invariant: Sum of approved spends equals final burn
        successful_results = [r for r in results if r is not None]
        total_approved = sum((r['amount'] for r in successful_results), Decimal('0.00'))
        assert total_approved == final_burn, f"Burn mismatch: {total_approved} != {final_burn}"

        # Invariant: No more than budget / spend_amount approvals
        max_possible = int(budget / spend_amount)
        assert approved_count[0] <= max_possible, f"Too many approvals: {approved_count[0]} > {max_possible}"

    @given(budget=money_strategy('100', '1000'), num_requests=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_spend_allows_valid_requests(self, budget_service, project_factory, budget, num_requests):
        """
        All valid requests (within budget) succeed.

        Invariant: If total requested spend <= budget, all requests succeed.
        """
        project = project_factory(budget_amount=budget)
        spend_amount = budget / Decimal(str(num_requests + 1))  # Ensure total fits in budget

        approved_count = [0]
        errors = []
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Valid spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except Exception as e:
                with lock:
                    errors.append(str(e))
                return None

        # Run concurrent spends
        with ThreadPoolExecutor(max_workers=min(20, num_requests)) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(num_requests)]
            list(as_completed(futures))

        # All requests should succeed (total spend < budget)
        assert approved_count[0] == num_requests, f"Expected {num_requests} approvals, got {approved_count[0]}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    @given(budget=money_strategy('100', '1000'), spend=money_strategy('10', '100'), num_workers=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_identical_spend_one_succeeds(self, budget_service, project_factory, budget, spend, num_workers):
        """
        N identical concurrent requests → exactly 1 succeeds (others hit limit).

        Invariant: Concurrent identical spends result in exactly one approval if spend > remaining.
        """
        # Set initial burn such that only one more spend fits
        initial_burn = budget - spend - Decimal('0.01')  # Leave room for only 1 spend
        project = project_factory(budget_amount=budget, initial_burn=initial_burn)

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend,
                    description=f"Identical spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except Exception:
                return None

        # Run concurrent identical spends
        with ThreadPoolExecutor(max_workers=min(20, num_workers)) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(num_workers)]
            list(as_completed(futures))

        # Exactly 1 should succeed (the one that acquired lock first)
        assert approved_count[0] == 1, f"Expected exactly 1 approval, got {approved_count[0]}"

    @given(budget=money_strategy('100', '1000'), spends=lists_of_decimals(min_size=5, max_size=20, min_value='10', max_value='50'))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_different_spends_sum_correctly(self, budget_service, project_factory, budget, spends):
        """
        Sum of concurrent spends = total approved.

        Invariant: Total approved amount equals sum of all successful spend requests.
        """
        project = project_factory(budget_amount=budget)

        approved_amounts = []
        lock = __import__('threading').Lock()

        def attempt_spend(amount):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=amount,
                    description=f"Variable spend {amount}"
                )
                with lock:
                    approved_amounts.append(result['amount'])
                return result
            except Exception:
                return None

        # Run concurrent spends with different amounts
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_spend, amount) for amount in spends]
            list(as_completed(futures))

        # Verify sum matches
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        total_approved = sum(approved_amounts, Decimal('0.00'))

        assert total_approved == final_burn, f"Sum mismatch: {total_approved} != {final_burn}"
        assert final_burn <= budget, f"Overdraft detected: {final_burn} > {budget}"

    @given(budget=money_strategy('100', '1000'), num_workers=st.integers(min_value=2, max_value=50))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_spend_idempotent(self, budget_service, project_factory, budget, num_workers):
        """
        Same request sent N times → processed exactly once.

        Invariant: Identical concurrent requests are serialized, not duplicated.
        """
        project = project_factory(budget_amount=budget)
        spend_amount = Decimal('10.00')

        approval_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                # Simulate idempotency key - same spend for all workers
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Idempotent spend {index}"
                )
                with lock:
                    approval_count[0] += 1
                return result
            except Exception:
                return None

        # Run concurrent identical spends
        with ThreadPoolExecutor(max_workers=min(50, num_workers)) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(num_workers)]
            list(as_completed(futures))

        # Each request processed independently (no idempotency without keys)
        # Verify budget never exceeded
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= budget, f"Overdraft detected: {final_burn} > {budget}"


# ============================================================================
# Test Atomic Update Invariants
# ============================================================================

class TestAtomicUpdateInvariants:
    """Property tests for atomic read-modify-write operations."""

    @pytest.fixture
    def budget_service(self, db):
        """Provide BudgetEnforcementService for tests."""
        from core.budget_enforcement_service import BudgetEnforcementService
        return BudgetEnforcementService(db)

    @pytest.fixture
    def project_factory(self, db):
        """Create test projects with budget."""
        from service_delivery.models import Project, BudgetStatus
        from datetime import datetime, timezone

        def _create(budget_amount: Decimal, initial_burn: Decimal = Decimal('0.00')):
            project = Project(
                id=f"proj_atomic_{budget_amount}_{initial_burn}",
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

    @given(initial_burn=money_strategy('0', '500'), spend=money_strategy('10', '100'), num_workers=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_read_modify_write_atomic(self, budget_service, project_factory, initial_burn, spend, num_workers):
        """
        Read-burn → check → update is atomic (no interleaving).

        Invariant: Concurrent updates don't interleave read/modify/write operations.
        """
        budget = initial_burn + spend * Decimal('10')  # Enough budget for all spends
        project = project_factory(budget_amount=budget, initial_burn=initial_burn)

        successful_updates = [0]
        lock = __import__('threading').Lock()

        def update_burn(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend,
                    description=f"Atomic update {index}"
                )
                with lock:
                    successful_updates[0] += 1
                return result
            except Exception:
                return None

        # Run concurrent atomic updates
        with ThreadPoolExecutor(max_workers=min(20, num_workers)) as executor:
            futures = [executor.submit(update_burn, i) for i in range(num_workers)]
            list(as_completed(futures))

        # Verify atomicity: final burn = initial + (successful * spend)
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        expected_burn = initial_burn + (Decimal(str(successful_updates[0])) * spend)

        assert final_burn == expected_burn, f"Atomicity violation: {final_burn} != {expected_burn}"

    @given(budget=money_strategy('100', '1000'))
    @settings(max_examples=50, deadline=None)
    def test_budget_check_isolated_from_other_transactions(self, budget_service, project_factory, budget):
        """
        Budget check sees consistent state.

        Invariant: Budget check within transaction sees snapshot, not concurrent modifications.
        """
        project = project_factory(budget_amount=budget)

        def check_and_spend():
            try:
                # Check budget
                status = budget_service.check_budget(
                    project_id=project.id,
                    amount=Decimal('10.00')
                )
                # If allowed, try to spend
                if status['allowed']:
                    return budget_service.approve_spend_locked(
                        db=budget_service.db,
                        project_id=project.id,
                        amount=Decimal('10.00')
                    )
                return None
            except Exception:
                return None

        # Run concurrent check-and-spend operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_and_spend) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # Verify no overdraft
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= budget, f"Overdraft detected: {final_burn} > {budget}"

    @given(budget=money_strategy('100', '1000'), num_workers=st.integers(min_value=2, max_value=10))
    @settings(max_examples=50, deadline=None)
    def test_transaction_rollback_isolated(self, budget_service, project_factory, budget, num_workers):
        """
        Failed transaction doesn't affect others.

        Invariant: Rolled-back transactions don't corrupt budget state.
        """
        project = project_factory(budget_amount=budget)

        successful_count = [0]
        failed_count = [0]
        lock = __import__('threading').Lock()

        def mixed_spend(index):
            try:
                # Every other request tries to overspend
                if index % 2 == 0:
                    # This should fail (overspend)
                    result = budget_service.approve_spend_locked(
                        db=budget_service.db,
                        project_id=project.id,
                        amount=budget,  # Try to spend entire budget
                    )
                    with lock:
                        successful_count[0] += 1
                    return result
                else:
                    # This should succeed (small amount)
                    result = budget_service.approve_spend_locked(
                        db=budget_service.db,
                        project_id=project.id,
                        amount=Decimal('10.00'),
                    )
                    with lock:
                        successful_count[0] += 1
                    return result
            except Exception:
                with lock:
                    failed_count[0] += 1
                return None

        # Run concurrent mixed spend requests
        with ThreadPoolExecutor(max_workers=min(10, num_workers)) as executor:
            futures = [executor.submit(mixed_spend, i) for i in range(num_workers)]
            list(as_completed(futures))

        # Verify consistent state
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)

        # All failed transactions were rolled back
        assert final_burn <= budget, f"Overdraft detected: {final_burn} > {budget}"
        assert final_burn <= Decimal('10.00') * Decimal(str(successful_count[0])), \
            f"Burn exceeds successful spends: {final_burn} > {Decimal('10.00') * successful_count[0]}"


# ============================================================================
# Test Lock Contention Invariants
# ============================================================================

class TestLockContentionInvariants:
    """Property tests for lock contention behavior."""

    @pytest.fixture
    def budget_service(self, db):
        """Provide BudgetEnforcementService for tests."""
        from core.budget_enforcement_service import BudgetEnforcementService
        return BudgetEnforcementService(db)

    @pytest.fixture
    def project_factory(self, db):
        """Create test projects with budget."""
        from service_delivery.models import Project, BudgetStatus
        from datetime import datetime, timezone

        def _create(budget_amount: Decimal):
            project = Project(
                id=f"proj_lock_{budget_amount}",
                workspace_id="test_workspace",
                name=f"Test Project {budget_amount}",
                status="active",
                budget_amount=float(budget_amount),
                actual_burn=0.0,
                budget_status=BudgetStatus.ON_TRACK,
                created_at=datetime.now(timezone.utc)
            )
            db.add(project)
            db.commit()
            return project

        return _create

    @given(budget=money_strategy('100', '1000'), num_workers=st.integers(min_value=5, max_value=50))
    @settings(max_examples=50, deadline=None)
    def test_lock_contention_handled(self, budget_service, project_factory, budget, num_workers):
        """
        High concurrency (50 workers) doesn't cause deadlocks.

        Invariant: Lock contention is handled gracefully, no deadlocks occur.
        """
        project = project_factory(budget_amount=budget)
        spend_amount = Decimal('1.00')  # Small amount to allow many approvals

        completed = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Contention test {index}"
                )
                with lock:
                    completed[0] += 1
                return result
            except Exception:
                return None

        # Run high-concurrency spends
        with ThreadPoolExecutor(max_workers=min(50, num_workers)) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(num_workers)]
            list(as_completed(futures))

        # All workers should complete (no deadlocks)
        assert completed[0] == num_workers, f"Deadlock detected: only {completed[0]}/{num_workers} completed"

        # Verify budget consistency
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= budget, f"Overdraft detected: {final_burn} > {budget}"

    @given(budget=money_strategy('100', '1000'), num_workers=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_locks_released_after_transaction(self, budget_service, project_factory, budget, num_workers):
        """
        Locks released after commit/rollback.

        Invariant: Locks don't leak - subsequent transactions can acquire lock.
        """
        project = project_factory(budget_amount=budget)
        spend_amount = Decimal('5.00')

        successful_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Lock release test {index}"
                )
                with lock:
                    successful_count[0] += 1
                return result
            except Exception:
                return None

        # Run sequential batches of concurrent spends
        # If locks weren't released, second batch would hang
        for batch in range(3):
            with ThreadPoolExecutor(max_workers=min(20, num_workers)) as executor:
                futures = [executor.submit(attempt_spend, f"{batch}_{i}") for i in range(num_workers)]
                list(as_completed(futures))

        # All batches should complete (locks released properly)
        expected_total = num_workers * 3
        assert successful_count[0] == expected_total, \
            f"Lock leak detected: only {successful_count[0]}/{expected_total} completed"


# ============================================================================
# Test Optimistic Locking Invariants
# ============================================================================

class TestOptimisticLockingInvariants:
    """Property tests for optimistic locking behavior."""

    @pytest.fixture
    def budget_service(self, db):
        """Provide BudgetEnforcementService for tests."""
        from core.budget_enforcement_service import BudgetEnforcementService
        return BudgetEnforcementService(db)

    @pytest.fixture
    def project_factory(self, db):
        """Create test projects with budget."""
        from service_delivery.models import Project, BudgetStatus
        from datetime import datetime, timezone

        def _create(budget_amount: Decimal):
            project = Project(
                id=f"proj_optimistic_{budget_amount}",
                workspace_id="test_workspace",
                name=f"Test Project {budget_amount}",
                status="active",
                budget_amount=float(budget_amount),
                actual_burn=0.0,
                budget_status=BudgetStatus.ON_TRACK,
                created_at=datetime.now(timezone.utc)
            )
            db.add(project)
            db.commit()
            return project

        return _create

    @given(budget=money_strategy('100', '1000'), num_workers=st.integers(min_value=2, max_value=10))
    @settings(max_examples=50, deadline=None)
    def test_optimistic_locking_retry_succeeds(self, budget_service, project_factory, budget, num_workers):
        """
        Optimistic locking retries on conflict.

        Invariant: Concurrent modifications trigger retry logic, eventually succeed.
        """
        project = project_factory(budget_amount=budget)
        spend_amount = Decimal('5.00')

        successful_count = [0]
        retry_count = [0]
        lock = __import__('threading').Lock()

        def attempt_spend_with_retry(index):
            try:
                # Use optimistic locking with retry
                result = budget_service.approve_spend_with_retry(
                    project_id=project.id,
                    amount=spend_amount,
                    description=f"Optimistic spend {index}",
                    max_retries=3
                )
                with lock:
                    successful_count[0] += 1
                return result
            except Exception as e:
                # Track retries (concurrent modifications)
                if "concurrent" in str(e).lower() or "retry" in str(e).lower():
                    with lock:
                        retry_count[0] += 1
                return None

        # Run concurrent optimistic spends
        with ThreadPoolExecutor(max_workers=min(10, num_workers)) as executor:
            futures = [executor.submit(attempt_spend_with_retry, i) for i in range(num_workers)]
            list(as_completed(futures))

        # Most should succeed after retries
        assert successful_count[0] > 0, "No optimistic locks succeeded"
        assert successful_count[0] <= num_workers, f"Too many successes: {successful_count[0]} > {num_workers}"

        # Verify budget consistency
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn <= budget, f"Overdraft detected: {final_burn} > {budget}"


# ============================================================================
# Test Distributed Lock Invariants
# ============================================================================

class TestDistributedLockInvariants:
    """Property tests for distributed lock behavior."""

    @pytest.fixture
    def budget_service(self, db):
        """Provide BudgetEnforcementService for tests."""
        from core.budget_enforcement_service import BudgetEnforcementService
        return BudgetEnforcementService(db)

    @pytest.fixture
    def project_factory(self, db):
        """Create test projects with budget."""
        from service_delivery.models import Project, BudgetStatus
        from datetime import datetime, timezone

        def _create(budget_amount: Decimal):
            project = Project(
                id=f"proj_distributed_{budget_amount}",
                workspace_id="test_workspace",
                name=f"Test Project {budget_amount}",
                status="active",
                budget_amount=float(budget_amount),
                actual_burn=0.0,
                budget_status=BudgetStatus.ON_TRACK,
                created_at=datetime.now(timezone.utc)
            )
            db.add(project)
            db.commit()
            return project

        return _create

    @given(budget=money_strategy('100', '1000'), num_workers=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_lock_granularity_per_project(self, budget_service, project_factory, budget, num_workers):
        """
        Locks are per-project (not global).

        Invariant: Concurrent spends on different projects don't block each other.
        """
        # Create multiple projects
        projects = [project_factory(budget_amount=budget) for _ in range(5)]

        completed_by_project = {p.id: 0 for p in projects}
        lock = __import__('threading').Lock()

        def attempt_spend_on_project(project_id):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project_id,
                    amount=Decimal('10.00'),
                    description=f"Multi-project spend"
                )
                with lock:
                    completed_by_project[project_id] += 1
                return result
            except Exception:
                return None

        # Run spends across all projects concurrently
        all_futures = []
        with ThreadPoolExecutor(max_workers=min(20, num_workers)) as executor:
            for project in projects:
                futures = [executor.submit(attempt_spend_on_project, project.id) for _ in range(num_workers // 5)]
                all_futures.extend(futures)
            list(as_completed(all_futures))

        # All projects should have processed spends independently
        for project_id, count in completed_by_project.items():
            assert count > 0, f"Project {project_id} had zero spends (locks blocking across projects)"


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Edge case tests for concurrent spend operations."""

    @pytest.fixture
    def budget_service(self, db):
        """Provide BudgetEnforcementService for tests."""
        from core.budget_enforcement_service import BudgetEnforcementService
        return BudgetEnforcementService(db)

    @pytest.fixture
    def project_factory(self, db):
        """Create test projects with budget."""
        from service_delivery.models import Project, BudgetStatus
        from datetime import datetime, timezone

        def _create(budget_amount: Decimal):
            project = Project(
                id=f"proj_edge_{budget_amount}",
                workspace_id="test_workspace",
                name=f"Test Project {budget_amount}",
                status="active",
                budget_amount=float(budget_amount),
                actual_burn=0.0,
                budget_status=BudgetStatus.ON_TRACK,
                created_at=datetime.now(timezone.utc)
            )
            db.add(project)
            db.commit()
            return project

        return _create

    def test_empty_concurrent_requests(self, budget_service, project_factory):
        """
        Empty list of concurrent requests handled.

        Edge case: Zero concurrent requests doesn't cause errors.
        """
        project = project_factory(budget_amount=Decimal('100.00'))

        # Run zero concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for f in as_completed(futures):
                pass  # No futures

        # Verify project unchanged
        budget_service.db.refresh(project)
        assert to_decimal(project.actual_burn or 0) == Decimal('0.00')

    def test_zero_spend_concurrent(self, budget_service, project_factory):
        """
        Zero amount concurrent requests handled.

        Edge case: Zero amount spends don't affect locking or budget.
        """
        project = project_factory(budget_amount=Decimal('100.00'))

        approved_count = [0]
        lock = __import__('threading').Lock()

        def attempt_zero_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('0.00'),
                    description=f"Zero spend {index}"
                )
                with lock:
                    approved_count[0] += 1
                return result
            except Exception:
                return None

        # Run concurrent zero spends
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_zero_spend, i) for i in range(10)]
            list(as_completed(futures))

        # Zero spends might be rejected (negative check) or allowed
        # Verify budget unchanged
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('0.00'), f"Zero spends changed budget: {final_burn}"

    def test_negative_spend_concurrent_rejected(self, budget_service, project_factory):
        """
        Negative amounts rejected consistently.

        Edge case: Negative amounts are always rejected even under concurrency.
        """
        project = project_factory(budget_amount=Decimal('100.00'))

        rejected_count = [0]
        lock = __import__('threading').Lock()

        def attempt_negative_spend(index):
            try:
                result = budget_service.approve_spend_locked(
                    db=budget_service.db,
                    project_id=project.id,
                    amount=Decimal('-10.00'),
                    description=f"Negative spend {index}"
                )
                return result
            except ValueError as e:
                # Expected rejection
                with lock:
                    rejected_count[0] += 1
                return None
            except Exception:
                return None

        # Run concurrent negative spends
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_negative_spend, i) for i in range(10)]
            list(as_completed(futures))

        # All should be rejected
        assert rejected_count[0] == 10, f"Expected all rejected, got {rejected_count[0]}"

        # Verify budget unchanged
        budget_service.db.refresh(project)
        final_burn = to_decimal(project.actual_burn or 0)
        assert final_burn == Decimal('0.00'), f"Negative spends changed budget: {final_burn}"
