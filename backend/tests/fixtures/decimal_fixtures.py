"""
Hypothesis strategies for Decimal property testing.

Provides reusable Decimal strategies for financial property tests.
"""

from decimal import Decimal
from hypothesis import strategies as st
from typing import Union


def decimal_strategy(
    min_value: Union[str, float] = '0.00',
    max_value: Union[str, float] = '10000.00',
    places: int = 2
):
    """
    Strategy for generating Decimal values with specified precision.

    Args:
        min_value: Minimum value (as string or float)
        max_value: Maximum value (as string or float)
        places: Number of decimal places

    Returns:
        Hypothesis strategy for Decimal values
    """
    return st.decimals(
        min_value=str(min_value),
        max_value=str(max_value),
        places=places,
        allow_nan=False,
        allow_infinity=False
    )


def money_strategy(
    min_value: Union[str, float] = '0.01',
    max_value: Union[str, float] = '1000000.00'
):
    """
    Strategy for generating monetary values (2 decimal places).

    Use for: transaction amounts, balances, budget limits

    Examples:
        >>> money_strategy().example()  # doctest: +SKIP
        Decimal('123.45')
    """
    return decimal_strategy(min_value, max_value, places=2)


def high_precision_strategy(
    min_value: Union[str, float] = '0.0001',
    max_value: Union[str, float] = '10000.0000'
):
    """
    Strategy for high-precision Decimal values (4 decimal places).

    Use for: tax calculations, per-unit pricing, fractional cents

    Examples:
        >>> high_precision_strategy().example()  # doctest: +SKIP
        Decimal('12.3456')
    """
    return decimal_strategy(min_value, max_value, places=4)


def large_amount_strategy():
    """
    Strategy for large monetary amounts (up to billions).

    Examples:
        >>> large_amount_strategy().example()  # doctest: +SKIP
        Decimal('1234567890.00')
    """
    return decimal_strategy('0.01', '999999999999.99', places=2)


def percentage_strategy():
    """
    Strategy for percentage values (0-100, 2 decimal places).

    Use for: discount percentages, tax rates, commission rates

    Examples:
        >>> percentage_strategy().example()  # doctest: +SKIP
        Decimal('8.25')
    """
    return decimal_strategy('0.00', '100.00', places=2)


def lists_of_decimals(
    min_size: int = 1,
    max_size: int = 20,
    **decimal_kwargs
):
    """
    Strategy for lists of Decimal values.

    Args:
        min_size: Minimum list size
        max_size: Maximum list size
        **decimal_kwargs: Arguments passed to decimal_strategy()

    Returns:
        Strategy for lists of Decimal values

    Examples:
        >>> lists_of_decimals(min_size=2, max_size=5).example()  # doctest: +SKIP
        [Decimal('10.00'), Decimal('20.50'), Decimal('15.25')]
    """
    return st.lists(
        decimal_strategy(**decimal_kwargs),
        min_size=min_size,
        max_size=max_size
    )


# Strategies for specific use cases
invoice_amount_strategy = money_strategy('100.00', '100000.00')
budget_amount_strategy = money_strategy('1000.00', '1000000.00')
subscription_cost_strategy = money_strategy('9.99', '999.99')
tax_rate_strategy = percentage_strategy()
discount_strategy = percentage_strategy()


# Convenience exports
__all__ = [
    'decimal_strategy',
    'money_strategy',
    'high_precision_strategy',
    'large_amount_strategy',
    'percentage_strategy',
    'lists_of_decimals',
    'invoice_amount_strategy',
    'budget_amount_strategy',
    'subscription_cost_strategy',
    'tax_rate_strategy',
    'discount_strategy',
]
