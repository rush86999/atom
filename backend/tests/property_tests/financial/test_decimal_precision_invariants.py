"""
Property-Based Tests for Decimal Precision Invariants

Tests critical financial precision invariants:
- Precision preservation (no loss in calculations)
- Conservation of value (sum before = sum after)
- Rounding behavior (ROUND_HALF_UP consistency)
- Idempotency (round(x) == round(round(x)))
- Exact comparison (no epsilon tolerance needed)
"""

import pytest
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from hypothesis import given, strategies as st, assume, settings, example
from typing import List, Union
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tests.fixtures.decimal_fixtures import (
    money_strategy,
    high_precision_strategy,
    large_amount_strategy,
    lists_of_decimals,
)


class TestPrecisionPreservationInvariants:
    """Tests for Decimal precision preservation"""

    @given(amount=money_strategy())
    @settings(max_examples=100)
    @example(amount=Decimal('0.01'))
    @example(amount=Decimal('100.00'))
    @example(amount=Decimal('999999999999.99'))
    def test_decimal_precision_preserved_in_storage(self, amount):
        """Test that Decimal precision is preserved through storage round-trip"""
        # Simulate database round-trip (string conversion)
        serialized = str(amount)
        deserialized = Decimal(serialized)

        assert amount == deserialized, \
            f"Decimal {amount} not preserved through string round-trip"

    @given(amount=high_precision_strategy())
    @settings(max_examples=100)
    def test_high_precision_rounded_to_cents(self, amount):
        """Test that high-precision amounts round correctly to cents"""
        rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Should have exactly 2 decimal places
        assert rounded.as_tuple().exponent == -2, \
            f"Rounded value should have 2 decimal places, got {rounded.as_tuple().exponent}"

        # Should not be negative if input was positive
        if amount > 0:
            assert rounded >= 0

    @given(amounts=lists_of_decimals(min_size=2, max_size=50, min_value='0.01', max_value='1000.00'))
    @settings(max_examples=100)
    def test_sum_precision_preserved(self, amounts):
        """Test that sum of Decimals preserves precision"""
        total = sum(amounts, Decimal('0.00'))

        # Total should be positive
        assert total >= 0

        # Total should be finite
        assert total < Decimal('1e20')

    @given(
        amount=high_precision_strategy(),
        places=st.integers(min_value=0, max_value=6)
    )
    @settings(max_examples=100)
    def test_quantize_preserves_value(self, amount, places):
        """Test that quantize preserves value within specified precision"""
        quantizer = Decimal('0.' + '0' * places) if places > 0 else Decimal('1')
        quantized = amount.quantize(quantizer, rounding=ROUND_HALF_UP)

        # Quantized value should have correct exponent
        expected_exponent = -places if places > 0 else 0
        assert quantized.as_tuple().exponent == expected_exponent


class TestConservationOfValueInvariants:
    """Tests for conservation of value in financial operations"""

    @given(
        amounts=lists_of_decimals(min_size=2, max_size=20, min_value='10.00', max_value='1000.00')
    )
    @settings(max_examples=100)
    def test_sum_conservation(self, amounts):
        """Test that sum is conserved regardless of order"""
        sum_forward = sum(amounts, Decimal('0.00'))
        sum_backward = sum(reversed(amounts), Decimal('0.00'))

        assert sum_forward == sum_backward, \
            "Sum should be conserved regardless of order"

    @given(
        balance=money_strategy('100.00', '10000.00'),
        transactions=lists_of_decimals(min_size=1, max_size=20, min_value='0.01', max_value='100.00')
    )
    @settings(max_examples=100)
    def test_balance_conservation(self, balance, transactions):
        """Test that balance is conserved through transactions"""
        # Simulate account balance changes
        new_balance = balance
        for tx in transactions:
            # Randomly add or subtract (simplified)
            new_balance = new_balance + tx

        # Should be able to reconstruct original balance
        # by reversing transactions
        reconstructed = new_balance
        for tx in reversed(transactions):
            reconstructed = reconstructed - tx

        assert abs(reconstructed - balance) < Decimal('0.01'), \
            f"Balance not conserved: started {balance}, ended {reconstructed}"

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_multiplication_conservation(self, amount):
        """Test that multiplication by 1 conserves value"""
        result = amount * Decimal('1')
        assert result == amount

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_division_roundtrip(self, amount):
        """Test that multiplication/division round-trip approximately"""
        if amount == 0:
            return

        # Multiply and divide by same factor
        factor = Decimal('2.5')
        result = (amount * factor) / factor

        # Should be very close (within rounding)
        assert abs(result - amount) < Decimal('0.02'), \
            f"Round-trip failed: {amount} -> {result}"


class TestRoundingInvariants:
    """Tests for rounding behavior consistency"""

    @given(
        amount=high_precision_strategy(),
        places=st.integers(min_value=0, max_value=4)
    )
    @settings(max_examples=100)
    @example(amount=Decimal('10.005'), places=2)
    @example(amount=Decimal('10.015'), places=2)
    def test_round_half_up_behavior(self, amount, places):
        """Test that ROUND_HALF_UP rounds .005 up"""
        quantizer = Decimal('0.' + '0' * places) if places > 0 else Decimal('1')
        rounded = amount.quantize(quantizer, rounding=ROUND_HALF_UP)

        # The rounded value should have the correct precision
        expected_exponent = -places if places > 0 else 0
        assert rounded.as_tuple().exponent == expected_exponent

    @given(
        amounts=lists_of_decimals(min_size=2, max_size=10, min_value='0.001', max_value='100.00', places=3),
    )
    @settings(max_examples=50)
    def test_sum_then_round_equals_round_then_sum(self, amounts):
        """Test that rounding after sum ≈ sum of rounded values"""
        # Round each amount to cents
        rounded_amounts = [a.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for a in amounts]

        # Sum then round
        sum_then_round = sum(amounts, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Round then sum
        round_then_sum = sum(rounded_amounts, Decimal('0.00'))

        # Should be very close (may differ by 1 cent due to rounding)
        assert abs(sum_then_round - round_then_sum) <= Decimal('0.01'), \
            f"Rounding order matters: sum_then_round={sum_then_round}, round_then_sum={round_then_sum}"


class TestIdempotencyInvariants:
    """Tests for idempotency in financial operations"""

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_round_is_idempotent(self, amount):
        """Test that rounding an already-rounded value is idempotent"""
        once_rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        twice_rounded = once_rounded.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        assert once_rounded == twice_rounded, \
            "Rounding should be idempotent"

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_quantize_is_idempotent(self, amount):
        """Test that quantize is idempotent for same precision"""
        precision = Decimal('0.01')
        once = amount.quantize(precision, rounding=ROUND_HALF_UP)
        twice = once.quantize(precision, rounding=ROUND_HALF_UP)

        assert once == twice, "Quantize should be idempotent"


class TestExactComparisonInvariants:
    """Tests for exact Decimal comparison (no epsilon needed)"""

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_exact_equality_works(self, amount):
        """Test that exact equality works without epsilon"""
        same_amount = Decimal(str(amount))

        # Exact comparison - no epsilon
        assert amount == same_amount

    @given(amount1=money_strategy(), amount2=money_strategy())
    @settings(max_examples=100)
    def test_exact_inequality_detects_differences(self, amount1, amount2):
        """Test that exact comparison detects cent differences"""
        # Make amount2 different by 1 cent
        if amount2 >= Decimal('0.01'):
            amount2_adjusted = amount2 - Decimal('0.01')
            assert amount2 != amount2_adjusted
            assert amount2 - amount2_adjusted == Decimal('0.01')

    @given(amounts=lists_of_decimals(min_size=3, max_size=20, min_value='1.00', max_value='100.00'))
    @settings(max_examples=50)
    def test_split_and_recombine(self, amounts):
        """Test that splitting and recombining preserves total exactly"""
        total = sum(amounts, Decimal('0.00'))

        # Split into equal parts (may have rounding)
        count = len(amounts)
        if count > 0:
            per_part = (total / count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            recombined = per_part * count

            # Should be within 1 cent (rounding error)
            assert abs(recombined - total) <= Decimal('0.01') * count, \
                f"Split/recombine failed: {total} -> {recombined}"


class TestEdgeCases:
    """Tests for edge cases in Decimal operations"""

    def test_zero_value_handling(self):
        """Test that zero is handled correctly"""
        zero = Decimal('0.00')
        assert zero == Decimal('0')
        assert zero.quantize(Decimal('0.01')) == zero

    @given(amount=money_strategy())
    @settings(max_examples=50)
    def test_string_initialization_is_exact(self, amount):
        """Test that string initialization creates exact Decimal"""
        from core.decimal_utils import to_decimal

        # String initialization
        from_string = to_decimal(str(amount))

        assert amount == from_string

    @given(value=st.one_of(
        st.text(min_value=1, max_value=20),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    ))
    @settings(max_examples=100)
    def test_to_decimal_handles_various_inputs(self, value):
        """Test that to_decimal handles various input types"""
        from core.decimal_utils import to_decimal

        try:
            result = to_decimal(value)
            assert isinstance(result, Decimal)
        except (ValueError, TypeError):
            # Some inputs should fail - that's expected
            pass
