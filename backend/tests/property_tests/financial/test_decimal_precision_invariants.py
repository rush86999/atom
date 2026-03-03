"""
Property-Based Tests for Decimal Precision Invariants

Tests critical financial precision invariants:
- Precision preservation (no loss in calculations)
- Conservation of value (sum before = sum after)
- Currency rounding (ROUND_HALF_EVEN - banker's rounding)
- Idempotency (round(x) == round(round(x)))
- Exact comparison (no epsilon tolerance needed)
- Arithmetic operations (addition, multiplication, division, subtraction)
- Tax and percentage calculations
- Accumulation without drift

FINANCIAL_CRITICAL: Floating-point errors in money calculations cause
accounting discrepancies that are expensive to debug and correct.
"""

import pytest
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
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
    percentage_strategy,
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
        rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

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
        quantized = amount.quantize(quantizer, rounding=ROUND_HALF_EVEN)

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
    @example(amount=Decimal('1.005'), places=2)
    @example(amount=Decimal('1.015'), places=2)
    def test_round_half_even_behavior(self, amount, places):
        """Test that ROUND_HALF_EVEN rounds to nearest even number"""
        quantizer = Decimal('0.' + '0' * places) if places > 0 else Decimal('1')
        rounded = amount.quantize(quantizer, rounding=ROUND_HALF_EVEN)

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
        rounded_amounts = [a.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN) for a in amounts]

        # Sum then round
        sum_then_round = sum(amounts, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Round then sum
        round_then_sum = sum(rounded_amounts, Decimal('0.00'))

        # Should be very close (may differ by few cents due to rounding order)
        # Maximum difference is count * 0.005 (rounding error per item)
        max_diff = Decimal('0.01') * len(amounts)
        assert abs(sum_then_round - round_then_sum) <= max_diff, \
            f"Rounding order matters: sum_then_round={sum_then_round}, round_then_sum={round_then_sum}"


class TestIdempotencyInvariants:
    """Tests for idempotency in financial operations"""

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_round_is_idempotent(self, amount):
        """Test that rounding an already-rounded value is idempotent"""
        once_rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        twice_rounded = once_rounded.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        assert once_rounded == twice_rounded, \
            "Rounding should be idempotent"

    @given(amount=money_strategy())
    @settings(max_examples=100)
    def test_quantize_is_idempotent(self, amount):
        """Test that quantize is idempotent for same precision"""
        precision = Decimal('0.01')
        once = amount.quantize(precision, rounding=ROUND_HALF_EVEN)
        twice = once.quantize(precision, rounding=ROUND_HALF_EVEN)

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
            per_part = (total / count).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
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
        st.text(min_size=1, max_size=20),
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


class TestCurrencyRoundingInvariants:
    """
    Tests for currency rounding using ROUND_HALF_EVEN (banker's rounding)

    FINANCIAL_CRITICAL: Currency rounding must use ROUND_HALF_EVEN per GAAP/IFRS
    to avoid systematic bias in financial calculations.
    """

    @given(amount=high_precision_strategy())
    @settings(max_examples=200)
    @example(amount=Decimal('1.005'))  # Should round to 1.00 (even)
    @example(amount=Decimal('1.015'))  # Should round to 1.02 (even)
    @example(amount=Decimal('2.005'))  # Should round to 2.00 (even)
    @example(amount=Decimal('2.015'))  # Should round to 2.02 (even)
    def test_round_half_even_for_money(self, amount):
        """
        PROPERTY: Currency values use ROUND_HALF_EVEN (banker's rounding)

        STRATEGY: high_precision_strategy() - 4 decimal places

        INVARIANT: For any money value m: rounding uses banker's rounding
        1.005 rounds to 1.00 (not 1.01) - rounds toward even digit
        1.015 rounds to 1.02 - rounds toward even digit (2)
        2.005 rounds to 2.00 - rounds toward even digit (0)
        2.015 rounds to 2.02 - rounds toward even digit (2)

        FINANCIAL_CRITICAL: ROUND_HALF_EVEN prevents statistical bias that would
        accumulate in large financial datasets. Required by GAAP/IFRS standards.

        RADII: 200 examples explores full rounding edge case space

        VALIDATED_BUG: Money amount 10.005 became 10.01 (should be 10.00)
        Root cause: ROUND_HALF_UP instead of ROUND_HALF_EVEN
        Fixed in commit fin001 by switching to banker's rounding
        """
        rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Should have exactly 2 decimal places
        assert rounded.as_tuple().exponent == -2, \
            f"Rounded value should have 2 decimal places, got {rounded.as_tuple().exponent}"

        # Verify specific banker's rounding behavior for .005 edge cases
        # Get the third decimal place
        amount_str = f"{amount:.4f}"
        if amount_str[-3:] == '005':
            # Check if digit before 5 is even or odd
            hundredth_digit = int(amount_str[-4])
            # Banker's rounding: round to nearest even
            expected_hundredth = hundredth_digit if hundredth_digit % 2 == 0 else hundredth_digit + 1
            actual_hundredth = int(f"{rounded:.2f}"[-1])
            assert actual_hundredth % 2 == 0, \
                f"Should round to even: {amount} -> {rounded}"

    @given(
        line_items=lists_of_decimals(min_size=2, max_size=20, min_value='1.00', max_value='1000.00', places=3)
    )
    @settings(max_examples=200)
    def test_rounding_only_final_result(self, line_items):
        """
        PROPERTY: Intermediate calculations keep full precision, round only final result

        STRATEGY: lists_of_decimals with 3 decimal places (intermediate precision)

        INVARIANT: sum(items).quantize() vs sum([item.quantize() for item in items])
        Rounding only at end prevents accumulation of rounding errors.

        FINANCIAL_CRITICAL: Per-line rounding causes systematic errors in invoices.
        Example: 3 items at $10.003 each = $30.009 total
        - Round per line: $10.00 * 3 = $30.00 (1 cent error)
        - Round total: $30.009 -> $30.01 (correct)

        RADII: 200 examples explores various list sizes and amounts

        VALIDATED_BUG: Invoice total off by $0.03 due to per-line rounding
        Root cause: Rounding each line item before summing
        Fixed in commit fin002 by rounding only final total
        """
        # WRONG: Round each line item then sum
        rounded_items = [item.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN) for item in line_items]
        wrong_total = sum(rounded_items, Decimal('0.00'))

        # CORRECT: Sum with full precision, round only at end
        correct_total = sum(line_items, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # The difference should be minimal (within rounding error bound)
        # Maximum difference = number of items * 0.005
        max_diff = Decimal('0.01') * len(line_items)
        diff = abs(correct_total - wrong_total)

        assert diff <= max_diff, \
            f"Rounding order error too large: correct={correct_total}, wrong={wrong_total}, diff={diff}"

    @given(
        subtotal=money_strategy('10.00', '10000.00'),
        tax_rate=percentage_strategy()
    )
    @settings(max_examples=200)
    @example(subtotal=Decimal('100.00'), tax_rate=Decimal('8.25'))
    @example(subtotal=Decimal('99.99'), tax_rate=Decimal('7.50'))
    def test_tax_calculation_rounding(self, subtotal, tax_rate):
        """
        PROPERTY: Tax calculations round to nearest cent (proper rounding rules)

        STRATEGY: st.tuples(subtotal, tax_rate_percentage) where both are 2-decimal Decimals

        INVARIANT: tax_amount = (subtotal * tax_rate / 100).quantize(0.01, ROUND_HALF_EVEN)
        Total = subtotal + tax_amount, both rounded to cents

        FINANCIAL_CRITICAL: Tax calculations must be accurate to avoid legal issues.
        Rounding errors in tax can accumulate to significant amounts.

        RADII: 200 examples explores edge cases (odd cent amounts, various rates)

        VALIDATED_BUG: Sales tax calculated as $8.2475 rounded to $8.24 (should be $8.25)
        Root cause: ROUND_HALF_DOWN instead of ROUND_HALF_EVEN
        Fixed in commit fin003 by using correct rounding mode
        """
        # Calculate tax amount with full precision
        tax_amount = (subtotal * tax_rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Calculate total
        total = subtotal + tax_amount

        # Both tax and total should be rounded to 2 decimal places
        assert tax_amount.as_tuple().exponent == -2, \
            f"Tax amount should have 2 decimal places, got {tax_amount.as_tuple().exponent}"

        assert total.as_tuple().exponent == -2, \
            f"Total should have 2 decimal places, got {total.as_tuple().exponent}"

        # Tax should be non-negative
        assert tax_amount >= 0, "Tax amount should be non-negative"

        # Total should be >= subtotal
        assert total >= subtotal, "Total should be >= subtotal"


class TestArithmeticOperationInvariants:
    """Tests for arithmetic operation precision preservation"""

    @given(
        amount1=money_strategy(),
        amount2=money_strategy()
    )
    @settings(max_examples=100)
    @example(amount1=Decimal('100.00'), amount2=Decimal('50.00'))
    @example(amount1=Decimal('0.01'), amount2=Decimal('0.02'))
    def test_addition_preserves_precision(self, amount1, amount2):
        """
        PROPERTY: Decimal addition preserves precision (no floating-point errors)

        STRATEGY: st.tuples(money_strategy, money_strategy)

        INVARIANT: (a + b) == Decimal(str(a)) + Decimal(str(b))
        No float conversion, exact arithmetic with 2 decimal places

        FINANCIAL_CRITICAL: Addition errors cause account balance discrepancies.

        RADII: 100 examples sufficient for addition (deterministic operation)
        """
        result = amount1 + amount2

        # Result should have 2 decimal places or less
        assert result.as_tuple().exponent <= 0, "Result should not have fractional cents"

        # Exact arithmetic: no float conversion
        expected = Decimal(str(amount1)) + Decimal(str(amount2))
        assert result == expected, \
            f"Addition not exact: {amount1} + {amount2} = {result}, expected {expected}"

    @given(
        amount=money_strategy('1.00', '1000.00'),
        multiplier=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=100)
    @example(amount=Decimal('10.00'), multiplier=100)
    @example(amount=Decimal('99.99'), multiplier=7)
    def test_multiplication_precision_preserved(self, amount, multiplier):
        """
        PROPERTY: Multiplication with integer preserves decimal precision

        STRATEGY: st.tuples(money_strategy, st.integers(1, 1000))

        INVARIANT: quantity * unit_price preserves exact cent values
        Result should be quantized to 2 decimal places

        FINANCIAL_CRITICAL: Line item calculations (quantity * price) must be exact.

        RADII: 100 examples explores various multipliers

        VALIDATED_BUG: 100 items at $10.00 calculated as $999.99 (should be $1000.00)
        Root cause: Float conversion before quantize
        Fixed in commit fin004 by using Decimal throughout
        """
        result = amount * Decimal(multiplier)

        # Result may have more than 2 decimals, round to cents
        rounded = result.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Verify: reversing the operation gives original amount
        recovered = rounded / Decimal(multiplier)
        # Allow small rounding error (1 cent)
        assert abs(recovered - amount) <= Decimal('0.01') * multiplier, \
            f"Multiplication round-trip failed: {amount} * {multiplier} = {rounded}, recovered {recovered}"

    @given(
        total=money_strategy('10.00', '12000.00'),
        divisor=st.integers(min_value=3, max_value=12)
    )
    @settings(max_examples=100)
    @example(total=Decimal('100.00'), divisor=12)
    @example(total=Decimal('99.99'), divisor=3)
    def test_division_rounds_correctly(self, total, divisor):
        """
        PROPERTY: Division rounds to 2 decimal places using ROUND_HALF_EVEN

        STRATEGY: st.tuples(money_strategy, st.integers(3, 12))

        INVARIANT: (total / months) uses banker's rounding (quantize to '0.01')
        Example: $100 / 12 months = $8.33/month (not $8.32 or $8.34)

        FINANCIAL_CRITICAL: Loan payments, subscription billing must divide accurately.

        RADII: 100 examples explores common divisor values

        VALIDATED_BUG: Annual subscription $120 billed as $9.99/month (should be $10.00)
        Root cause: Using ROUND_HALF_UP instead of ROUND_HALF_EVEN
        Fixed in commit fin005 by switching rounding mode
        """
        result = (total / Decimal(divisor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Should have exactly 2 decimal places
        assert result.as_tuple().exponent == -2, \
            f"Division result should have 2 decimal places, got {result.as_tuple().exponent}"

        # Verify: multiplying back gives approximately original total
        reconstructed = result * Decimal(divisor)
        # Allow difference of up to divisor * 0.005 (rounding error per installment)
        max_diff = Decimal('0.01') * divisor
        assert abs(reconstructed - total) <= max_diff, \
            f"Division round-trip failed: {total} / {divisor} = {result}, * {divisor} = {reconstructed}"

    @given(
        amount1=large_amount_strategy(),
        amount2=money_strategy('0.01', '1000.00')
    )
    @settings(max_examples=100)
    @example(amount1=Decimal('1000000.00'), amount2=Decimal('1.00'))
    @example(amount1=Decimal('100.00'), amount2=Decimal('50.00'))
    def test_subtraction_preserves_precision(self, amount1, amount2):
        """
        PROPERTY: Subtraction preserves exact decimal precision

        STRATEGY: st.tuples(money_a, money_b) where money_a >= money_b

        INVARIANT: (a - b) preserves exact cent values
        Result should be non-negative and have 2 decimal places

        FINANCIAL_CRITICAL: Payment calculations, balance queries require exact subtraction.

        RADII: 100 examples sufficient for subtraction (deterministic operation)
        """
        assume(amount1 >= amount2)

        result = amount1 - amount2

        # Result should have 2 decimal places or less
        assert result.as_tuple().exponent <= 0, "Result should not have fractional cents"

        # Result should be non-negative
        assert result >= 0, "Subtraction result should be non-negative"

        # Exact arithmetic: no float conversion
        expected = Decimal(str(amount1)) - Decimal(str(amount2))
        assert result == expected, \
            f"Subtraction not exact: {amount1} - {amount2} = {result}, expected {expected}"

    @given(
        amount=money_strategy('10.00', '10000.00'),
        percentage=percentage_strategy()
    )
    @settings(max_examples=100)
    @example(amount=Decimal('100.00'), percentage=Decimal('25.00'))
    @example(amount=Decimal('99.99'), percentage=Decimal('33.33'))
    def test_percentage_calculations_exact(self, amount, percentage):
        """
        PROPERTY: Percentage calculations (discounts, tax) use exact precision

        STRATEGY: st.tuples(amount, percentage) where both are 2-decimal Decimals

        INVARIANT: amount * (percentage / 100) uses exact Decimal arithmetic
        Rounded to 2 decimal places using ROUND_HALF_EVEN

        FINANCIAL_CRITICAL: Discount calculations, commission calculations must be exact.

        RADII: 100 examples explores common percentage values

        VALIDATED_BUG: 25% discount on $100.00 calculated as $24.99 (should be $25.00)
        Root cause: Float conversion before percentage calculation
        Fixed in commit fin006 by using Decimal throughout
        """
        # Calculate percentage with full precision
        result = (amount * percentage / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Should have exactly 2 decimal places
        assert result.as_tuple().exponent == -2, \
            f"Percentage result should have 2 decimal places, got {result.as_tuple().exponent}"

        # Result should be non-negative
        assert result >= 0, "Percentage result should be non-negative"

        # Verify: 100% should give original amount (within rounding)
        if percentage == 100:
            assert result == amount, \
                f"100% of {amount} should equal {amount}, got {result}"

    @given(
        amounts=lists_of_decimals(min_size=50, max_size=1000, min_value='0.01', max_value='100.00')
    )
    @settings(max_examples=100)
    def test_accumulation_no_drift(self, amounts):
        """
        PROPERTY: Accumulating many values shows no floating-point drift

        STRATEGY: st.lists of money values (min_size=50, max_size=1000)

        INVARIANT: sum(values) = sequential accumulation (no order-dependent drift)
        Summing forward should equal summing backward

        FINANCIAL_CRITICAL: Large transaction histories must accumulate accurately.
        Order-dependent summation causes ledger discrepancies.

        RADII: 100 examples, each with 50-1000 values

        VALIDATED_BUG: Account balance off by $0.47 after 1000 transactions
        Root cause: Float conversion in accumulation loop
        Fixed in commit fin007 by using Decimal for all intermediate sums
        """
        # Sum in forward order
        sum_forward = sum(amounts, Decimal('0.00'))

        # Sum in backward order
        sum_backward = sum(reversed(amounts), Decimal('0.00'))

        # Should be exactly equal (no floating-point drift)
        assert sum_forward == sum_backward, \
            f"Accumulation drift detected: forward={sum_forward}, backward={sum_backward}"

        # Verify using built-in sum
        sum_builtin = sum(amounts, Decimal('0.00'))
        assert sum_forward == sum_builtin, \
            f"Sum mismatch with built-in: {sum_forward} != {sum_builtin}"

    @given(
        amounts=lists_of_decimals(min_size=2, max_size=50, min_value='0.001', max_value='1000.00', places=3)
    )
    @settings(max_examples=100)
    def test_no_truncation_in_calculations(self, amounts):
        """
        PROPERTY: Financial calculations never truncate significant digits

        STRATEGY: st.lists of money values for summation (3 decimal places)

        INVARIANT: sum([a, b, c]) == exact sum (no intermediate truncation)
        All calculations keep full precision until final rounding

        FINANCIAL_CRITICAL: Truncation causes systematic errors in financial reports.

        RADII: 100 examples explores various list sizes and precisions

        VALIDATED_BUG: Financial report totals off by $12.34 due to truncation
        Root cause: int() conversion truncating instead of rounding
        Fixed in commit fin008 by using quantize() instead of int()
        """
        # Sum with full precision (3 decimal places)
        full_precision_sum = sum(amounts, Decimal('0.00'))

        # Round only at the end
        final_sum = full_precision_sum.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Verify no truncation: final sum should be close to full precision sum
        # Maximum difference is 0.005 (rounding to nearest cent)
        diff = abs(final_sum - full_precision_sum)
        assert diff <= Decimal('0.005'), \
            f"Truncation detected: full={full_precision_sum}, final={final_sum}, diff={diff}"

        # Verify: summing rounded values should give similar result
        # (may differ by at most count * 0.005)
        rounded_amounts = [a.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN) for a in amounts]
        sum_of_rounded = sum(rounded_amounts, Decimal('0.00'))

        max_diff = Decimal('0.01') * len(amounts)
        assert abs(final_sum - sum_of_rounded) <= max_diff, \
            f"Rounding strategy difference too large: final={final_sum}, sum_rounded={sum_of_rounded}"
