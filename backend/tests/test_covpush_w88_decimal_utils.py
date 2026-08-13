# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/decimal_utils (91 stmts, never wave-tested).

to_decimal: None/int/Decimal-passthrough/str (commas, $, whitespace)/
float-via-str, invalid string ValueError, unsupported type TypeError.
round_money: ROUND_HALF_UP at 2 places (5 rounds up / 4 rounds down),
places=0 (integer quantize), places=3, negative places treated as 0.
quantize: default MONEY_PRECISION, HIGH_PRECISION, str input.
get_decimal_context: prec 28 + ROUND_HALF_UP defaults.
safe_divide: happy path, precision override, zero-check ZeroDivisionError,
zero numerator, high-precision division.

No LLM / no network / stdlib decimal only.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pytest

from core.decimal_utils import (
    HIGH_PRECISION,
    MONEY_PRECISION,
    get_decimal_context,
    quantize,
    round_money,
    safe_divide,
    to_decimal,
)


class TestToDecimal:
    def test_none_returns_zero(self):
        assert to_decimal(None) == Decimal("0.00")

    def test_int(self):
        assert to_decimal(100) == Decimal("100")

    def test_negative_int(self):
        assert to_decimal(-5) == Decimal("-5")

    def test_decimal_passthrough_is_identity(self):
        d = Decimal("3.14159")
        assert to_decimal(d) is d

    def test_plain_string(self):
        assert to_decimal("100.00") == Decimal("100.00")

    def test_string_with_commas(self):
        assert to_decimal("1,234.56") == Decimal("1234.56")

    def test_string_with_dollar_sign(self):
        assert to_decimal("$19.99") == Decimal("19.99")

    def test_string_with_whitespace(self):
        assert to_decimal("  42.5  ") == Decimal("42.5")

    def test_float_converts_via_string(self):
        # 0.1 as float carries binary representation error; the module
        # converts via str() to avoid double-rounding.
        assert to_decimal(0.1) == Decimal("0.1")

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Cannot convert 'abc' to Decimal"):
            to_decimal("abc")

    def test_unsupported_type_raises_type_error(self):
        with pytest.raises(TypeError, match="Unsupported type"):
            to_decimal([1, 2, 3])


class TestRoundMoney:
    def test_rounds_up_on_five(self):
        assert round_money("10.005") == Decimal("10.01")

    def test_rounds_down_below_five(self):
        assert round_money("10.004") == Decimal("10.00")

    def test_rounds_decimal_input(self):
        assert round_money(Decimal("19.995")) == Decimal("20.00")

    def test_rounds_float_input(self):
        assert round_money(1.005) == Decimal("1.01")

    def test_places_zero_rounds_to_integer(self):
        assert round_money("10.5", places=0) == Decimal("11")
        assert round_money("10.4", places=0) == Decimal("10")

    def test_places_three(self):
        assert round_money("1.23455", places=3) == Decimal("1.235")

    def test_negative_places_treated_as_integer(self):
        assert round_money("7.9", places=-1) == Decimal("8")


class TestQuantize:
    def test_default_money_precision(self):
        assert quantize("10.005") == Decimal("10.01")

    def test_high_precision(self):
        assert quantize("1.23456", HIGH_PRECISION) == Decimal("1.2346")

    def test_str_input(self):
        assert quantize("0.005") == Decimal("0.01")

    def test_constant_precisions(self):
        assert MONEY_PRECISION == Decimal("0.01")
        assert HIGH_PRECISION == Decimal("0.0001")


class TestGetDecimalContext:
    def test_defaults(self):
        ctx = get_decimal_context()
        assert ctx["precision"] == 28
        assert ctx["rounding"] == ROUND_HALF_UP


class TestSafeDivide:
    def test_basic_division(self):
        assert safe_divide("1", "2") == Decimal("0.50")

    def test_rounds_to_two_places(self):
        assert safe_divide("1", "3") == Decimal("0.33")

    def test_precision_override(self):
        assert safe_divide("1", "3", precision=4) == Decimal("0.3333")

    def test_zero_numerator(self):
        assert safe_divide("0", "5") == Decimal("0.00")

    def test_divide_by_zero_raises(self):
        with pytest.raises(ZeroDivisionError, match="Cannot divide by zero"):
            safe_divide("1", "0")

    def test_decimal_inputs(self):
        assert safe_divide(Decimal("6"), Decimal("4")) == Decimal("1.50")

    def test_float_inputs(self):
        assert safe_divide(10.0, 4.0) == Decimal("2.50")
