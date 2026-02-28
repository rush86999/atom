"""
Decimal utilities for exact monetary arithmetic.

Per GAAP/IFRS, monetary values must use exact decimal arithmetic.
Never use float for money - IEEE 754 cannot represent 0.1 exactly.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from typing import Union, Optional

# Configure global decimal context for financial calculations
getcontext().rounding = ROUND_HALF_UP  # Commercial rounding (5 rounds up)
getcontext().prec = 28  # Sufficient for financial calculations

# Money precision: 2 decimal places (cents)
MONEY_PRECISION = Decimal('0.01')

# High precision: 4 decimal places (tax calculations, per-unit pricing)
HIGH_PRECISION = Decimal('0.0001')


def to_decimal(value: Union[str, int, float, Decimal, None]) -> Decimal:
    """
    Convert value to Decimal with string initialization to avoid float precision errors.

    IMPORTANT: Always initialize from string, never from float.
    Decimal('0.1') is exact. Decimal(0.1) captures binary representation error.

    Args:
        value: Input value (str, int, float, Decimal, or None)

    Returns:
        Decimal: Exact decimal representation

    Raises:
        ValueError: If value cannot be converted to Decimal

    Examples:
        >>> to_decimal('100.00')
        Decimal('100.00')
        >>> to_decimal(100)
        Decimal('100')
        >>> to_decimal('1,234.56')  # Handles commas
        Decimal('1234.56')
    """
    if value is None:
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int,)):
        return Decimal(str(value))
    if isinstance(value, str):
        # Remove common formatting characters
        cleaned = value.strip().replace(',', '').replace('$', '')
        try:
            return Decimal(cleaned)
        except InvalidOperation as e:
            raise ValueError(f"Cannot convert '{value}' to Decimal: {e}")
    if isinstance(value, float):
        # Float is already imprecise, but handle for API compatibility
        # Convert via string to avoid double-rounding errors
        return Decimal(str(value))
    raise TypeError(f"Unsupported type for Decimal conversion: {type(value)}")


def round_money(value: Union[Decimal, str, float], places: int = 2) -> Decimal:
    """
    Round monetary value to specified decimal places using ROUND_HALF_UP.

    Args:
        value: Monetary value to round
        places: Decimal places (default: 2 for cents)

    Returns:
        Decimal: Rounded value

    Examples:
        >>> round_money('10.005')
        Decimal('10.01')  # Rounds up (commercial rounding)
        >>> round_money('10.004')
        Decimal('10.00')
    """
    decimal_value = to_decimal(value)
    quantizer = Decimal('0.' + '0' * places) if places > 0 else Decimal('1')
    return decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)


def quantize(value: Union[Decimal, str, float], precision: Decimal = MONEY_PRECISION) -> Decimal:
    """
    Quantize value to specific precision using global rounding strategy.

    Args:
        value: Value to quantize
        precision: Decimal precision (default: 2 decimal places)

    Returns:
        Decimal: Quantized value
    """
    decimal_value = to_decimal(value)
    return decimal_value.quantize(precision)


def get_decimal_context() -> dict:
    """
    Get current decimal context configuration.

    Returns:
        dict: Context settings (prec, rounding, etc.)
    """
    return {
        'precision': getcontext().prec,
        'rounding': getcontext().rounding,
    }


def safe_divide(numerator: Union[Decimal, str, float],
                denominator: Union[Decimal, str, float],
                precision: int = 2) -> Decimal:
    """
    Safe decimal division with zero-check and rounding.

    Args:
        numerator: Value to divide
        denominator: Value to divide by
        precision: Decimal places for result (default: 2)

    Returns:
        Decimal: Rounded result

    Raises:
        ZeroDivisionError: If denominator is zero
    """
    num = to_decimal(numerator)
    den = to_decimal(denominator)

    if den == 0:
        raise ZeroDivisionError("Cannot divide by zero")

    result = num / den
    return round_money(result, places=precision)
