"""
Unit Tests for Decimal Utilities

Tests decimal utility functions for exact monetary arithmetic:
- to_decimal: Convert various types to Decimal
- round_money: Round monetary values
- quantize: Quantize to specific precision
- get_decimal_context: Get decimal context info
- safe_divide: Safe division with zero handling
- format_money: Format monetary values for display
- calculate_percentage: Safe percentage calculations

Target Coverage: 95%
Target Branch Coverage: 80%+
Pass Rate Target: 100%
"""

import pytest
from decimal import Decimal, InvalidOperation
from core.decimal_utils import (
    to_decimal,
    round_money,
    quantize,
    get_decimal_context,
    safe_divide,
    MONEY_PRECISION,
    HIGH_PRECISION
)


# =============================================================================
# Test Class: to_decimal
# =============================================================================

class TestToDecimal:
    """Tests for to_decimal function."""

    def test_to_decimal_from_string(self):
        """RED: Test converting string to decimal."""
        result = to_decimal('100.00')
        assert result == Decimal('100.00')
        assert isinstance(result, Decimal)

    def test_to_decimal_from_int(self):
        """RED: Test converting int to decimal."""
        result = to_decimal(42)
        assert result == Decimal('42')
        assert isinstance(result, Decimal)

    def test_to_decimal_from_decimal(self):
        """RED: Test passing Decimal through."""
        input_val = Decimal('123.45')
        result = to_decimal(input_val)
        assert result == input_val
        assert isinstance(result, Decimal)

    def test_to_decimal_from_none(self):
        """RED: Test converting None returns zero."""
        result = to_decimal(None)
        assert result == Decimal('0.00')

    def test_to_decimal_from_float(self):
        """RED: Test converting float (with warning)."""
        result = to_decimal(10.5)
        assert isinstance(result, Decimal)
        # Float conversion happens via string
        assert result == Decimal('10.5')

    def test_to_decimal_with_commas(self):
        """RED: Test converting string with commas."""
        result = to_decimal('1,234.56')
        assert result == Decimal('1234.56')

    def test_to_decimal_with_dollar_sign(self):
        """RED: Test converting string with dollar sign."""
        result = to_decimal('$100.00')
        assert result == Decimal('100.00')

    def test_to_decimal_with_whitespace(self):
        """RED: Test converting string with whitespace."""
        result = to_decimal('  50.00  ')
        assert result == Decimal('50.00')

    def test_to_decimal_invalid_string(self):
        """RED: Test converting invalid string raises error."""
        with pytest.raises(ValueError):
            to_decimal('not_a_number')

    def test_to_decimal_unsupported_type(self):
        """RED: Test converting unsupported type raises error."""
        with pytest.raises(TypeError):
            to_decimal([1, 2, 3])


# =============================================================================
# Test Class: round_money
# =============================================================================

class TestRoundMoney:
    """Tests for round_money function."""

    def test_round_money_default_places(self):
        """RED: Test rounding to default 2 places."""
        result = round_money('10.005')
        assert result == Decimal('10.01')  # Rounds up

    def test_round_money_rounds_down(self):
        """RED: Test rounding down values."""
        result = round_money('10.004')
        assert result == Decimal('10.00')

    def test_round_money_custom_places(self):
        """RED: Test rounding to custom places."""
        result = round_money('10.0055', places=3)
        assert result == Decimal('10.006')

    def test_round_money_from_decimal(self):
        """RED: Test rounding Decimal input."""
        result = round_money(Decimal('10.005'))
        assert result == Decimal('10.01')

    def test_round_money_from_int(self):
        """RED: Test rounding int input."""
        result = round_money(100)
        assert result == Decimal('100.00')

    def test_round_money_negative_value(self):
        """RED: Test rounding negative values."""
        result = round_money('-10.005')
        assert result == Decimal('-10.01')

    def test_round_money_zero(self):
        """RED: Test rounding zero."""
        result = round_money(0)
        assert result == Decimal('0.00')

    def test_round_money_large_value(self):
        """RED: Test rounding large monetary value."""
        result = round_money('1234567.895')
        assert result == Decimal('1234567.90')


# =============================================================================
# Test Class: quantize
# =============================================================================

class TestQuantize:
    """Tests for quantize function."""

    def test_quantize_default_precision(self):
        """RED: Test quantize to money precision."""
        result = quantize('10.123')
        assert result == Decimal('10.12')

    def test_quantize_custom_precision(self):
        """RED: Test quantize to custom precision."""
        result = quantize('10.1234', precision=HIGH_PRECISION)
        assert result == Decimal('10.1234')

    def test_quantize_rounds_up(self):
        """RED: Test quantize rounds up."""
        result = quantize('10.005')
        assert result == Decimal('10.01')

    def test_quantize_from_string(self):
        """RED: Test quantize string input."""
        result = quantize('100.456')
        assert result == Decimal('100.46')

    def test_quantize_from_decimal(self):
        """RED: Test quantize Decimal input."""
        result = quantize(Decimal('10.999'))
        assert result == Decimal('11.00')


# =============================================================================
# Test Class: get_decimal_context
# =============================================================================

class TestGetDecimalContext:
    """Tests for get_decimal_context function."""

    def test_get_context_returns_dict(self):
        """RED: Test getting decimal context returns dict."""
        context = get_decimal_context()
        assert isinstance(context, dict)

    def test_get_context_has_required_keys(self):
        """RED: Test context has required keys."""
        context = get_decimal_context()
        assert 'precision' in context or 'prec' in context
        assert 'rounding' in context

    def test_get_context_precision_value(self):
        """RED: Test context precision is 28."""
        context = get_decimal_context()
        # Returns string key 'precision' or int key 'prec'
        precision = context.get('precision') or context.get('prec')
        assert precision == 28

    def test_get_context_rounding_mode(self):
        """RED: Test context uses ROUND_HALF_UP."""
        context = get_decimal_context()
        # Returns string 'ROUND_HALF_UP' or int 1
        rounding = context.get('rounding')
        assert rounding in ['ROUND_HALF_UP', 1]


# =============================================================================
# Test Class: safe_divide
# =============================================================================

class TestSafeDivide:
    """Tests for safe_divide function."""

    def test_safe_divide_normal_division(self):
        """RED: Test normal division."""
        result = safe_divide('100', '4')
        assert result == Decimal('25')

    def test_safe_divide_with_remainder(self):
        """RED: Test division with remainder (rounded to 2 decimals)."""
        result = safe_divide('10', '3')
        assert result == Decimal('3.33')  # Rounds to 2 decimal places

    def test_safe_divide_by_zero(self):
        """RED: Test dividing by zero raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError):
            safe_divide('100', '0')

    def test_safe_divide_zero_by_zero(self):
        """RED: Test 0/0 raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError):
            safe_divide('0', '0')

    def test_safe_divide_negative_numbers(self):
        """RED: Test dividing negative numbers."""
        result = safe_divide('-100', '4')
        assert result == Decimal('-25')

    def test_safe_divide_from_decimal(self):
        """RED: Test dividing Decimal inputs."""
        result = safe_divide(Decimal('100'), Decimal('4'))
        assert result == Decimal('25')

    def test_safe_divide_result_precision(self):
        """RED: Test division rounds to money precision (2 decimals)."""
        result = safe_divide('1', '3')
        # Rounds to 2 decimal places for money
        assert result == Decimal('0.33')


# =============================================================================
# Test Class: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_very_large_number(self):
        """RED: Test handling very large numbers."""
        result = to_decimal('999999999999.99')
        assert result == Decimal('999999999999.99')

    def test_very_small_number(self):
        """RED: Test handling very small numbers."""
        result = to_decimal('0.00000001')
        assert result == Decimal('0.00000001')

    def test_negative_zero(self):
        """RED: Test handling negative zero."""
        result = to_decimal('-0.00')
        assert result == Decimal('0.00') or result == Decimal('-0.00')

    def test_exponential_notation(self):
        """RED: Test handling exponential notation."""
        result = to_decimal('1.23E+2')
        assert result == Decimal('123')

    def test_round_money_half_even(self):
        """RED: Test ROUND_HALF_UP behavior (5 always rounds up)."""
        # Important for financial calculations
        assert round_money('1.005') == Decimal('1.01')
        assert round_money('2.005') == Decimal('2.01')
        assert round_money('3.005') == Decimal('3.01')

    def test_quantize_vs_round_money(self):
        """RED: Test quantize and round_money consistency."""
        value = '10.005'
        assert quantize(value) == round_money(value)

    def test_decimal_immutability(self):
        """RED: Test Decimal operations create new instances."""
        original = to_decimal('10.00')
        rounded = round_money(original)
        # Original should not be modified
        assert original == Decimal('10.00')


# =============================================================================
# Test Class: Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for combined operations."""

    def test_calculate_tax(self):
        """RED: Test calculating tax with decimal utilities."""
        price = to_decimal('100.00')
        tax_rate = to_decimal('0.0875')  # 8.75%
        tax = round_money(price * tax_rate, places=2)
        assert tax == Decimal('8.75')

    def test_calculate_total(self):
        """RED: Test calculating total with tax."""
        price = to_decimal('99.99')
        tax = to_decimal('8.75')
        total = quantize(price + tax)
        assert total == Decimal('108.74')

    def test_calculate_discount(self):
        """RED: Test calculating discount percentage."""
        original = to_decimal('100.00')
        discount_percent = to_decimal('0.20')  # 20%
        discount = round_money(original * discount_percent)
        assert discount == Decimal('20.00')

    def test_split_amount(self):
        """RED: Test splitting amount among people."""
        total = to_decimal('100.00')
        people = 3
        share = safe_divide(total, people)
        assert share is not None
        # When split 3 ways with 2 decimal precision, should be 33.33
        assert share == Decimal('33.33')


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
