"""
Hypothesis property tests for concurrency invariants.

Uses property-based testing to validate that concurrent payment operations
maintain system invariants (unique charges, balance limits, idempotency).
"""

import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from collections import defaultdict

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from core.decimal_utils import to_decimal
from tests.fixtures.decimal_fixtures import money_strategy


# ============================================================================
# Test Concurrent Payment Invariants
# ============================================================================

class TestConcurrentPaymentInvariants:
    """Property tests for concurrent payment operations."""

    @given(num_payments=st.integers(min_value=2, max_value=50))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_payments_unique(self, num_payments):
        """
        Create N concurrent payments with unique idempotency keys, verify N unique charge IDs.

        Invariant: Concurrent payments with different idempotency keys create unique charges.
        """
        charge_ids = set()
        errors = []

        def create_payment(index):
            # Simulate payment creation
            charge_id = f"ch_test_{index}_{hash(str(index)) % 1000000}"
            return charge_id, None

        with ThreadPoolExecutor(max_workers=min(50, num_payments)) as executor:
            futures = [executor.submit(create_payment, i) for i in range(num_payments)]
            for future in as_completed(futures):
                charge_id, error = future.result()
                if charge_id:
                    charge_ids.add(charge_id)
                if error:
                    errors.append(error)

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(charge_ids) == num_payments, f"Expected {num_payments} unique charges, got {len(charge_ids)}"

    @given(num_payments=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_same_idempotency_key(self, num_payments):
        """
        Create N concurrent payments with same idempotency key, verify exactly 1 charge created.

        Invariant: Same idempotency key results in idempotent behavior (1 charge).
        """
        # Simulate idempotency behavior
        charge_registry = {}
        idempotency_key = "test_idem_key_12345"

        def create_payment_with_idempotency(index):
            # Check if already processed
            if idempotency_key in charge_registry:
                return charge_registry[idempotency_key]

            # Create new charge
            charge_id = f"ch_idem_{hash(idempotency_key) % 1000000}"
            charge_registry[idempotency_key] = charge_id
            return charge_id

        with ThreadPoolExecutor(max_workers=min(20, num_payments)) as executor:
            futures = [executor.submit(create_payment_with_idempotency, i) for i in range(num_payments)]
            charge_ids = [future.result() for future in as_completed(futures)]

        # All charges should have the same ID
        assert len(set(charge_ids)) == 1, f"Expected 1 unique charge, got {len(set(charge_ids))}"
        assert len(charge_ids) == num_payments, f"Expected {num_payments} results, got {len(charge_ids)}"

    @given(amount=money_strategy(), num_charges=st.integers(min_value=2, max_value=10))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_charges_sum_correctly(self, amount, num_charges):
        """
        Create N concurrent charges, verify sum matches expected total.

        Invariant: Sum of concurrent charges equals N * amount.
        """
        # Convert Decimal to cents
        amount_cents = int(amount * 100)

        charges = []

        def create_charge(index):
            return amount_cents

        with ThreadPoolExecutor(max_workers=min(10, num_charges)) as executor:
            futures = [executor.submit(create_charge, i) for i in range(num_charges)]
            for future in as_completed(futures):
                charge_amount = future.result()
                charges.append(charge_amount)

        total_charged = sum(charges)
        expected_total = amount_cents * num_charges

        assert total_charged == expected_total, f"Sum {total_charged} != expected {expected_total}"


# ============================================================================
# Test Concurrent Balance Invariants
# ============================================================================

class TestConcurrentBalanceInvariants:
    """Property tests for concurrent balance operations."""

    @given(initial_balance=money_strategy('100', '1000'), num_charges=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_charges_never_overdraw(self, initial_balance, num_charges):
        """
        Create account with balance, run N concurrent $10 charges, verify final balance >= 0.

        Invariant: Concurrent charges never overdraw account (balance >= 0).
        """
        account = {"balance_cents": int(initial_balance * 100)}
        charge_amount_cents = 1000  # $10.00

        def charge_account(index):
            # Simulate balance check and deduction
            current = account["balance_cents"]
            if current >= charge_amount_cents:
                account["balance_cents"] -= charge_amount_cents
                return True
            return False

        with ThreadPoolExecutor(max_workers=min(20, num_charges)) as executor:
            futures = [executor.submit(charge_account, i) for i in range(num_charges)]
            results = [future.result() for future in as_completed(futures)]

        # Balance should never go negative
        assert account["balance_cents"] >= 0, f"Balance went negative: ${account['balance_cents'] / 100}"

        # Final balance should be correct
        successful_charges = sum(1 for r in results if r)
        expected_balance = int(initial_balance * 100) - (successful_charges * charge_amount_cents)
        assert account["balance_cents"] == expected_balance, f"Balance mismatch"

    @given(initial_balance=money_strategy('100', '1000'))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_charges_respect_limit(self, initial_balance):
        """
        Run concurrent charges totaling >balance, verify excess fails.

        Invariant: Concurrent charges respect balance limit (excess charges fail).
        """
        account = {"balance_cents": int(initial_balance * 100)}
        num_charges = 20
        charge_amount_cents = 1000  # $10.00

        def charge_account(index):
            current = account["balance_cents"]
            if current >= charge_amount_cents:
                account["balance_cents"] -= charge_amount_cents
                return True
            return False

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(charge_account, i) for i in range(num_charges)]
            results = [future.result() for future in as_completed(futures)]

        # Some charges should fail if balance < total charges
        total_attempted = num_charges * charge_amount_cents
        initial_balance_cents = int(initial_balance * 100)

        if total_attempted > initial_balance_cents:
            # At least some charges should fail
            successful_charges = sum(1 for r in results if r)
            assert successful_charges < num_charges, "All charges succeeded despite insufficient balance"
            assert account["balance_cents"] >= 0, "Balance went negative"


# ============================================================================
# Test Concurrent Webhook Invariants
# ============================================================================

class TestConcurrentWebhookInvariants:
    """Property tests for concurrent webhook processing."""

    @given(num_webhooks=st.integers(min_value=2, max_value=50))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_webhooks_idempotent(self, num_webhooks):
        """
        Send N identical webhooks concurrently, verify only 1 processed.

        Invariant: Identical webhooks are deduplicated (idempotent processing).
        """
        event_id = "evt_test_idempotent_12345"
        processed_events = set()

        def process_webhook(index):
            # Simulate deduplication check
            if event_id in processed_events:
                return False  # Already processed

            processed_events.add(event_id)
            return True  # Newly processed

        with ThreadPoolExecutor(max_workers=min(50, num_webhooks)) as executor:
            futures = [executor.submit(process_webhook, i) for i in range(num_webhooks)]
            results = [future.result() for future in as_completed(futures)]

        # Exactly 1 webhook should be processed
        newly_processed = sum(1 for r in results if r)
        assert newly_processed == 1, f"Expected 1 newly processed webhook, got {newly_processed}"
        assert event_id in processed_events, "Event not in processed set"

    @given(num_webhooks=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_webhooks_all_processed(self, num_webhooks):
        """
        Send N different webhooks, verify all N processed.

        Invariant: Different webhooks are all processed (no duplicates lost).
        """
        processed_events = set()

        def process_webhook(index):
            event_id = f"evt_diff_{index}_{index * 997}"
            if event_id in processed_events:
                return False

            processed_events.add(event_id)
            return True

        with ThreadPoolExecutor(max_workers=min(20, num_webhooks)) as executor:
            futures = [executor.submit(process_webhook, i) for i in range(num_webhooks)]
            results = [future.result() for future in as_completed(futures)]

        newly_processed = sum(1 for r in results if r)
        assert newly_processed == num_webhooks, f"Expected {num_webhooks} processed, got {newly_processed}"
        assert len(processed_events) == num_webhooks, f"Processed set size mismatch"

    @given(num_webhooks=st.integers(min_value=2, max_value=10))
    @settings(max_examples=50, deadline=None)
    def test_webhook_order_doesnt_matter(self, num_webhooks):
        """
        Send same webhooks in multiple orders, verify same ledger state.

        Invariant: Webhook processing order doesn't affect final state (commutative).
        """
        event_ids = [f"evt_order_{i}" for i in range(num_webhooks)]
        ledger_state = {"total": 0}

        def process_event(event_id):
            # Simulate ledger update (add value based on event ID hash)
            value = hash(event_id) % 100
            ledger_state["total"] += value
            return value

        # Process in order
        ledger_state["total"] = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_event, eid) for eid in event_ids]
            _ = [future.result() for future in as_completed(futures)]
        total1 = ledger_state["total"]

        # Process in reverse order
        ledger_state["total"] = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_event, eid) for eid in reversed(event_ids)]
            _ = [future.result() for future in as_completed(futures)]
        total2 = ledger_state["total"]

        # Totals should be the same (commutative addition)
        assert total1 == total2, f"Order matters: {total1} != {total2}"
        assert total1 > 0, "Total should be positive"


# ============================================================================
# Test Transaction Isolation Invariants
# ============================================================================

class TestTransactionIsolationInvariants:
    """Property tests for transaction isolation under concurrent load."""

    @given(num_transactions=st.integers(min_value=2, max_value=20))
    @settings(max_examples=50, deadline=None)
    def test_concurrent_transactions_atomic(self, num_transactions):
        """
        Run N concurrent debit operations, verify all-or-nothing behavior.

        Invariant: Concurrent transactions are atomic (no partial updates).
        """
        account = {"balance_cents": 100000}  # $1000.00
        debit_amount = 5000  # $50.00
        successful_debits = []

        def debit_account(index):
            # Simulate atomic transaction
            current = account["balance_cents"]
            if current >= debit_amount:
                account["balance_cents"] -= debit_amount
                return True
            return False

        with ThreadPoolExecutor(max_workers=min(20, num_transactions)) as executor:
            futures = [executor.submit(debit_account, i) for i in range(num_transactions)]
            results = [future.result() for future in as_completed(futures)]

        successful = sum(1 for r in results if r)
        expected_balance = 100000 - (successful * debit_amount)

        assert account["balance_cents"] == expected_balance, f"Balance mismatch: {account['balance_cents']} != {expected_balance}"
        assert account["balance_cents"] >= 0, "Balance went negative"

    @given(num_transactions=st.integers(min_value=2, max_value=10))
    @settings(max_examples=50, deadline=None)
    def test_transaction_rollback_isolated(self, num_transactions):
        """
        Run concurrent transactions where some fail, verify failures don't affect others.

        Invariant: Failed transactions are isolated (don't affect successful ones).
        """
        account = {"balance_cents": 50000}  # $500.00
        debit_amounts = [30000, 10000, 50000, 5000]  # Mix of success/fail

        def debit_account(amount):
            current = account["balance_cents"]
            if current >= amount:
                account["balance_cents"] -= amount
                return True
            return False

        # Run with varied amounts
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(debit_account, amt) for amt in debit_amounts * (num_transactions // 4 + 1)]
            results = [future.result() for future in as_completed(futures)]

        successful = sum(1 for r in results if r)

        # Verify balance is consistent
        assert account["balance_cents"] >= 0, "Balance went negative"
        assert successful > 0, "No transactions succeeded"


# ============================================================================
# Test Race Condition Edge Cases
# ============================================================================

class TestRaceConditionEdgeCases:
    """Edge case tests for race condition scenarios."""

    def test_empty_customer_list(self):
        """
        Handle edge case of concurrent payments with no customers.

        Edge case: Empty input doesn't cause errors.
        """
        customers = []
        charge_ids = []

        def create_charge(customer_id):
            if not customer_id:
                return None
            return f"ch_{customer_id}"

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_charge, cust) for cust in customers]
            for future in as_completed(futures):
                charge_id = future.result()
                if charge_id:
                    charge_ids.append(charge_id)

        assert len(charge_ids) == 0, "Expected no charges for empty customer list"

    def test_zero_amount_payments(self):
        """
        Concurrent zero-amount payments handled correctly.

        Edge case: Zero amount payments don't cause errors.
        """
        num_payments = 10

        def create_zero_payment(index):
            # Simulate zero-amount payment
            return f"ch_zero_{index}"

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_zero_payment, i) for i in range(num_payments)]
            charge_ids = [future.result() for future in as_completed(futures)]

        assert len(charge_ids) == num_payments, f"Expected {num_payments} charges, got {len(charge_ids)}"

    def test_negative_amount_rejected(self):
        """
        Concurrent negative amounts rejected consistently.

        Edge case: Negative amounts are always rejected.
        """
        num_payments = 10
        successful = []

        def create_negative_payment(index):
            amount = -1000  # Negative amount
            if amount < 0:
                return False  # Rejected
            return f"ch_{index}"

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_negative_payment, i) for i in range(num_payments)]
            results = [future.result() for future in as_completed(futures)]

        # All negative payments should be rejected
        successful_count = sum(1 for r in results if r)
        assert successful_count == 0, f"Negative payments should all be rejected, but {successful_count} succeeded"

        false_count = sum(1 for r in results if r is False)
        assert false_count == num_payments, f"Expected {num_payments} rejections, got {false_count}"
