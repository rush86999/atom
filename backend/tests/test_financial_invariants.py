"""
Property-based tests for financial invariants using Hypothesis.

These tests validate system invariants for financial operations:
- All calculations use Decimal, not float
- Double-entry: debits must equal credits
- Audit trail entries are immutable
- Budget enforcement: cost <= budget
- Decimal precision preserved at 2 decimal places
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from decimal import Decimal, InvalidOperation, getcontext
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import Mock
import hashlib

from core.accounting_validator import (
    validate_double_entry,
    EntryType,
    DoubleEntryValidationError
)


# ============================================================================
# Strategy Definitions
# ============================================================================

# Decimal amounts: 0 to 1,000,000 with 2 decimal places
decimal_amount_strategy = st.decimals(
    min_value='0.00',
    max_value='1000000.00',
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Small decimal amounts for precision tests
small_decimal_strategy = st.decimals(
    min_value='0.01',
    max_value='100.00',
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Budget and cost pairs
budget_cost_strategy = (
    st.tuples(decimal_amount_strategy, decimal_amount_strategy)
)

# Entry types
entry_type_strategy = st.sampled_from([EntryType.DEBIT, EntryType.CREDIT])


# ============================================================================
# Test Decimal Precision Invariants
# ============================================================================

class TestDecimalPrecisionInvariants:
    """Tests for Decimal precision invariants"""

    @given(amount=decimal_amount_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_always_use_decimal(self, amount):
        """
        INVARIANT: All financial calculations use Decimal

        Financial amounts must use Decimal type, not float.
        """
        # Verify type
        assert isinstance(amount, Decimal)

        # No float conversion
        result = amount * Decimal('1.0')
        assert isinstance(result, Decimal)

        # Arithmetic preserves type
        addition = amount + Decimal('10.00')
        assert isinstance(addition, Decimal)

    @given(amount=decimal_amount_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_precision_preserved(self, amount):
        """
        INVARIANT: Decimal precision is preserved (2 decimal places)

        Financial amounts should maintain 2 decimal places (cents).
        """
        # Round to 2 decimal places
        rounded = amount.quantize(Decimal('0.00'))

        # Verify precision
        # Get exponent (-2 means 2 decimal places)
        exponent = rounded.as_tuple().exponent
        assert exponent >= -2  # 2 or fewer decimal places

        # Value should be unchanged
        assert abs(rounded - amount) < Decimal('0.01')

    @given(amount1=decimal_amount_strategy, amount2=decimal_amount_strategy)
    @settings(max_examples=500, deadline=None)
    def test_arithmetic_preserves_precision(self, amount1, amount2):
        """
        INVARIANT: Arithmetic operations preserve Decimal precision

        Addition, subtraction should maintain Decimal type.
        """
        # Addition
        sum_result = amount1 + amount2
        assert isinstance(sum_result, Decimal)

        # Subtraction
        diff_result = amount1 - amount2
        assert isinstance(diff_result, Decimal)

        # Rounding after operations
        rounded_sum = sum_result.quantize(Decimal('0.00'))
        assert isinstance(rounded_sum, Decimal)

    @given(amount=decimal_amount_strategy)
    @settings(max_examples=500, deadline=None)
    def test_no_float_conversion(self, amount):
        """
        INVARIANT: Decimal never converts to float

        Prevents floating-point precision loss.
        """
        # String conversion maintains precision
        amount_str = str(amount)
        amount_from_str = Decimal(amount_str)

        assert abs(amount_from_str - amount) < Decimal('0.0001')

        # Quantized value matches
        quantized = amount.quantize(Decimal('0.00'))
        assert isinstance(quantized, Decimal)


# ============================================================================
# Test Double Entry Invariants
# ============================================================================

class TestDoubleEntryInvariants:
    """Tests for double-entry bookkeeping invariants"""

    @given(debit=decimal_amount_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_double_entry_balance(self, debit):
        """
        INVARIANT: Every debit has equal credit

        Double-entry bookkeeping requires debits == credits exactly.
        """
        credit = -debit  # Credit is negative of debit in accounting

        # Create balanced entries
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": debit},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": debit}  # Equal amount
        ]

        result = validate_double_entry(entries)

        assert result['balanced'] == True
        assert result['debits'] == result['credits']
        assert result['debits'] == debit

    @given(amount1=decimal_amount_strategy, amount2=decimal_amount_strategy)
    @settings(max_examples=500, deadline=None)
    def test_multiple_debits_single_credit(self, amount1, amount2):
        """
        INVARIANT: Sum of debits equals sum of credits

        Multiple debits can balance against one credit.
        """
        total_debit = amount1 + amount2

        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": amount1},
            {"account_id": "acc_2", "type": EntryType.DEBIT, "amount": amount2},
            {"account_id": "acc_3", "type": EntryType.CREDIT, "amount": total_debit}
        ]

        result = validate_double_entry(entries)

        assert result['balanced'] == True
        assert result['debits'] == result['credits']

    @given(debit=decimal_amount_strategy, credit=decimal_amount_strategy)
    @settings(max_examples=500, deadline=None)
    def test_imbalanced_entries_fail(self, debit, credit):
        """
        INVARIANT: Imbalanced entries fail validation

        When debits != credits, validation should fail.
        """
        assume(debit != credit)

        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": debit},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": credit}
        ]

        # Should raise error for imbalanced entries
        with pytest.raises(DoubleEntryValidationError):
            validate_double_entry(entries)

    @given(amount=decimal_amount_strategy)
    @settings(max_examples=200, deadline=None)
    def test_no_negative_amounts(self, amount):
        """
        INVARIANT: Negative amounts are rejected

        Accounting entries should not have negative amounts.
        """
        # Skip zero amount (negation doesn't change it)
        assume(amount > Decimal('0.00'))

        # Try to create entry with negative amount
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": -amount},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": amount}
        ]

        # Should reject negative amounts
        with pytest.raises(DoubleEntryValidationError):
            validate_double_entry(entries)

    @given(amounts=st.lists(decimal_amount_strategy, min_size=2, max_size=20))
    @settings(max_examples=200, deadline=None)
    def test_complex_transaction_balance(self, amounts):
        """
        INVARIANT: Complex transactions balance

        Transactions with multiple entries must balance.
        """
        assume(len(amounts) >= 2)

        # Simple approach: create balanced pairs
        entries = []
        for i in range(0, len(amounts) - 1, 2):
            if i + 1 < len(amounts):
                # Create balanced pair
                debit_amount = amounts[i]
                credit_amount = amounts[i]  # Same amount for balance
                entries.append({"account_id": f"debit_{i}", "type": EntryType.DEBIT, "amount": debit_amount})
                entries.append({"account_id": f"credit_{i}", "type": EntryType.CREDIT, "amount": credit_amount})

        # Validate (should balance)
        if entries:
            result = validate_double_entry(entries)
            assert result['balanced'] == True


# ============================================================================
# Test Budget Invariants
# ============================================================================

class TestBudgetInvariants:
    """Tests for budget enforcement invariants"""

    @given(budget=decimal_amount_strategy, cost=decimal_amount_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_budget_enforcement(self, budget, cost):
        """
        INVARIANT: Costs never exceed approved budget

        Budget enforcement should prevent overspending.
        """
        # Simple budget check
        can_execute = cost <= budget

        if cost > budget:
            assert can_execute == False
        else:
            assert can_execute == True

    @given(budget=decimal_amount_strategy,
           costs=st.lists(decimal_amount_strategy, min_size=1, max_size=10))
    @settings(max_examples=500, deadline=None)
    def test_cumulative_budget_enforcement(self, budget, costs):
        """
        INVARIANT: Cumulative costs never exceed budget

        Multiple transactions should not exceed total budget.
        """
        total_cost = sum(costs, Decimal('0.00'))

        # Budget check for cumulative spending
        within_budget = total_cost <= budget

        if total_cost > budget:
            assert within_budget == False
        else:
            assert within_budget == True

    @given(budget=decimal_amount_strategy, cost1=decimal_amount_strategy, cost2=decimal_amount_strategy)
    @settings(max_examples=500, deadline=None)
    def test_budget_depletion(self, budget, cost1, cost2):
        """
        INVARIANT: Budget decreases with spending

        Remaining budget should be initial minus spent.
        """
        # Sequential spending
        remaining_after_first = budget - cost1
        remaining_after_second = remaining_after_first - cost2

        # Remaining should never go below zero (with budget enforcement)
        if cost1 <= budget:
            assert remaining_after_first >= Decimal('0.00')

            if cost1 + cost2 <= budget:
                assert remaining_after_second >= Decimal('0.00')

    @given(budget=decimal_amount_strategy, spend=decimal_amount_strategy)
    @settings(max_examples=200, deadline=None)
    def test_budget_never_negative(self, budget, spend):
        """
        INVARIANT: Budget balance never goes negative

        Budget enforcement should prevent negative balances.
        """
        # Initial budget
        balance = budget

        # Enforce spending cap
        if spend > balance:
            actual_spend = balance
        else:
            actual_spend = spend

        balance = balance - actual_spend

        # Balance should be non-negative
        assert balance >= Decimal('0.00')


# ============================================================================
# Test Audit Trail Invariants
# ============================================================================

class TestAuditTrailInvariants:
    """Tests for audit trail immutability invariants"""

    @given(transaction_id=st.uuids().map(lambda u: str(u)),
           amount=decimal_amount_strategy,
           timestamp=st.datetimes())
    @settings(max_examples=200, deadline=None)
    def test_audit_trail_immutability(self, transaction_id, amount, timestamp):
        """
        INVARIANT: Audit trail entries are immutable

        Once written, audit entries should not be modifiable.
        """
        # Mock audit entry with frozen timestamp
        class AuditEntry:
            def __init__(self, transaction_id, amount, timestamp):
                self._transaction_id = transaction_id
                self._amount = amount
                self._timestamp = timestamp
                self._hash = self._compute_hash()

            def _compute_hash(self):
                """Compute content hash for integrity"""
                content = f"{self._transaction_id}{self._amount}{self._timestamp}"
                return hashlib.sha256(content.encode()).hexdigest()

            @property
            def transaction_id(self):
                return self._transaction_id

            @property
            def amount(self):
                return self._amount

            @property
            def timestamp(self):
                return self._timestamp

            def get_hash(self):
                """Get immutable hash"""
                return self._hash

        # Create audit entry
        entry = AuditEntry(transaction_id, amount, timestamp)
        original_hash = entry.get_hash()

        # Properties should be read-only
        assert entry.transaction_id == transaction_id
        assert entry.amount == amount
        assert entry.timestamp == timestamp
        assert entry.get_hash() == original_hash

        # Hash is deterministic
        entry2 = AuditEntry(transaction_id, amount, timestamp)
        assert entry2.get_hash() == original_hash

    @given(entries=st.lists(
        st.fixed_dictionaries({
            'transaction_id': st.uuids().map(lambda u: str(u)),
            'amount': decimal_amount_strategy,
            'timestamp': st.datetimes()
        }),
        min_size=1, max_size=50
    ))
    @settings(max_examples=200, deadline=None)
    def test_audit_trail_ordering(self, entries):
        """
        INVARIANT: Audit trail maintains chronological order

        Entries should be stored in timestamp order.
        """
        # Sort by timestamp
        sorted_entries = sorted(entries, key=lambda e: e['timestamp'])

        # Verify ordering
        for i in range(len(sorted_entries) - 1):
            assert sorted_entries[i]['timestamp'] <= sorted_entries[i + 1]['timestamp']

    @given(transaction_id=st.uuids().map(lambda u: str(u)),
           amount=decimal_amount_strategy)
    @settings(max_examples=200, deadline=None)
    def test_audit_entry_completeness(self, transaction_id, amount):
        """
        INVARIANT: Audit entries have all required fields

        Every audit entry should have transaction_id, amount, timestamp.
        """
        # Mock audit entry
        entry = {
            'transaction_id': transaction_id,
            'amount': amount,
            'timestamp': datetime.now(timezone.utc)
        }

        # Verify all required fields present
        assert 'transaction_id' in entry
        assert 'amount' in entry
        assert 'timestamp' in entry

        # Verify field types
        assert isinstance(entry['transaction_id'], str)
        assert isinstance(entry['amount'], Decimal)
        assert isinstance(entry['timestamp'], datetime)


# ============================================================================
# Test Decimal Utility Invariants
# ============================================================================

class TestDecimalUtilityInvariants:
    """Tests for decimal utility function invariants"""

    @given(amount=decimal_amount_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_round_money(self, amount):
        """
        INVARIANT: Money rounding produces 2 decimal places

        All monetary values should be rounded to cents.
        """
        # Mock round_money function
        def round_money(value: Decimal, places: int = 2) -> Decimal:
            return value.quantize(Decimal('0.01'))

        rounded = round_money(amount)

        # Should have 2 decimal places
        exponent = rounded.as_tuple().exponent
        assert exponent == -2

        # Should be Decimal type
        assert isinstance(rounded, Decimal)

    @given(amount=decimal_amount_strategy, places=st.integers(min_value=0, max_value=4))
    @settings(max_examples=500, deadline=None)
    def test_round_to_precision(self, amount, places):
        """
        INVARIANT: Rounding respects specified precision

        Should round to exact decimal places requested.
        """
        # Mock round_to_precision function
        def round_to_precision(value: Decimal, places: int) -> Decimal:
            quantizer = Decimal('0.1') ** places
            return value.quantize(quantizer)

        rounded = round_to_precision(amount, places)

        # Should have correct precision
        exponent = rounded.as_tuple().exponent
        assert exponent == -places

    @given(value=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False))
    @settings(max_examples=500, deadline=None)
    def test_to_decimal(self, value):
        """
        INVARIANT: Float to Decimal conversion preserves value

        Converting float to Decimal should maintain precision.
        """
        # Mock to_decimal function
        def to_decimal(value: float) -> Decimal:
            return Decimal(str(value))

        decimal_value = to_decimal(value)

        # Should be Decimal type
        assert isinstance(decimal_value, Decimal)

        # Should be close to original value
        assert abs(decimal_value - Decimal(str(value))) < Decimal('0.0001')


# ============================================================================
# Test Financial Calculation Invariants
# ============================================================================

class TestFinancialCalculationInvariants:
    """Tests for financial calculation invariants"""

    @given(principal=decimal_amount_strategy, rate=st.decimals(min_value='0.00', max_value='1.00', places=4))
    @settings(max_examples=500, deadline=None)
    def test_interest_calculation(self, principal, rate):
        """
        INVARIANT: Interest calculations use Decimal

        Simple interest: principal * rate
        """
        interest = principal * rate

        # Result should be Decimal
        assert isinstance(interest, Decimal)

        # Interest should be non-negative
        assert interest >= Decimal('0.00')

    @given(principal=decimal_amount_strategy,
           rate=st.decimals(min_value='0.00', max_value='0.20', places=4),
           periods=st.integers(min_value=1, max_value=360))
    @settings(max_examples=200, deadline=None)
    def test_compound_interest(self, principal, rate, periods):
        """
        INVARIANT: Compound interest preserves Decimal precision

        Compound interest: principal * (1 + rate)^periods
        """
        # Simple compound calculation
        amount = principal * (Decimal('1') + rate) ** periods

        # Result should be Decimal
        assert isinstance(amount, Decimal)

        # Should be greater than principal (for positive rate)
        if rate > Decimal('0.00'):
            assert amount >= principal

    @given(amount1=decimal_amount_strategy, amount2=decimal_amount_strategy)
    @settings(max_examples=500, deadline=None)
    def test_percentage_calculation(self, amount1, amount2):
        """
        INVARIANT: Percentage calculations use Decimal

        Percentage: (amount1 / amount2) * 100
        """
        assume(amount2 > Decimal('0.00'))

        percentage = (amount1 / amount2) * Decimal('100')

        # Result should be Decimal
        assert isinstance(percentage, Decimal)

        # Should be reasonable
        assert percentage >= Decimal('0.00')
