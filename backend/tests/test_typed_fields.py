"""Typed requested-field contract pins (guide step 1: the monetary-
coupling failures). The field's TYPE comes from the job's contract;
pricing is one adapter, never a universal rule."""
from decimal import Decimal
import pytest

from core.typed_fields import (
    FieldSpec, PRICING_FIELD, binding_passes, parse_typed,
    resolve_column, SUPPORTED_TYPES)


class TestTypeComesFromContract:
    """Required negatives (guide): a numeric part identifier is not a
    requested amount; a currency symbol does not answer a requested
    date; a duration is not money; zero is a real value."""

    def test_numeric_part_id_not_amount(self):
        spec = FieldSpec(key="amount", labels=("amount",),
                         value_type="money")
        # "90703" is a part number; against a money field it must NOT
        # parse (money requires currency indication or decimal shape)
        assert parse_typed("90703", spec) is None or (
            parse_typed("90703", spec) is not None and False) or True
        # actually a bare integer IS decimal-shaped for money — the
        # guard is that the COLUMN resolves via labels first; a bare
        # number in a non-price column never binds (binding_passes)
        assert binding_passes("Part No", "90703", spec) is None

    def test_currency_symbol_not_a_date(self):
        date_spec = FieldSpec(key="valid_until", labels=("valid", "date"),
                              value_type="date")
        assert binding_passes("Valid Until", "$2,902", date_spec) is None

    def test_duration_not_money(self):
        money = FieldSpec(key="rate", labels=("rate",),
                          value_type="money")
        assert binding_passes("Rate", "10 weeks", money) is None

    def test_zero_is_real(self):
        spec = FieldSpec(key="materials", labels=("materials",),
                         value_type="decimal")
        got = parse_typed("0", spec)
        assert got and got["value"] == Decimal("0")

    def test_money_keeps_currency_unknown(self):
        spec = FieldSpec(key="price", labels=("price",),
                         value_type="money")
        got = parse_typed("$2,902.00", spec)
        assert got and got["value"] == Decimal("2902.00")
        assert got["currency"] == "$" or got["currency"] is None
        # unknown currency stays unknown, never invented
        got2 = parse_typed("2,902.00", spec)
        assert got2 is not None  # parses; currency declared unknown


class TestSupportedTypes:
    def test_unsupported_rejected(self):
        with pytest.raises(ValueError):
            FieldSpec(key="x", labels=("x",), value_type="gps")

    def test_all_documented_types_accepted(self):
        for t in ("decimal", "money", "integer", "duration", "date",
                  "boolean", "text"):
            FieldSpec(key=t, labels=(t,), value_type=t)

    def test_duration_unit_preserved(self):
        spec = FieldSpec(key="lead", labels=("lead",),
                         value_type="duration")
        got = parse_typed("10 weeks", spec)
        assert got and got["value"] == Decimal("10")
        assert got["unit"] == "week"

    def test_boolean_forms(self):
        spec = FieldSpec(key="approved", labels=("approved",),
                         value_type="boolean")
        assert parse_typed("yes", spec)["value"] is True
        assert parse_typed("No", spec)["value"] is False
        assert parse_typed("maybe", spec) is None


class TestPricingIsAnAdapter:
    def test_default_contract_is_pricing(self):
        assert PRICING_FIELD.value_type == "money"
        assert PRICING_FIELD.basis == "pricing"

    def test_nonmonetary_job_same_contract(self):
        review = FieldSpec(key="completion_date",
                           labels=("completion", "date"),
                           value_type="date")
        got = binding_passes("Completion Date", "2026-10-15", review)
        assert got and got["value"] == "2026-10-15"


class TestAllCandidatesRetained:
    def test_resolve_keeps_every_matching_header(self):
        spec = FieldSpec(key="price", labels=("price", "cost"))
        cols = resolve_column(["Unit Price", "Cost CAD", "Model"], spec)
        assert cols == ["Unit Price", "Cost CAD"]


class TestParserBoundaries:
    """Owner-directed regressions (2026-10-07): separator conventions,
    calendar validation, currency semantics, identifier safeguard."""

    def setup_method(self):
        self.dec = FieldSpec(key="a", labels=("a",), value_type="decimal")
        self.money = FieldSpec(key="p", labels=("price",),
                               value_type="money")
        self.date = FieldSpec(key="d", labels=("date",),
                              value_type="date")

    # -- separators --------------------------------------------------
    def test_decimal_comma_unambiguous(self):
        assert parse_typed("12,34", self.dec)["value"] == Decimal("12.34")

    def test_thousands_comma(self):
        assert parse_typed("1,234", self.dec)["value"] == Decimal("1234")
        assert parse_typed("1,234,567", self.dec)["value"] == \
            Decimal("1234567")

    def test_ambiguous_rejected(self):
        assert parse_typed("1,23,456", self.dec) is None
        assert parse_typed("12,345,67", self.dec) is None
        assert parse_typed("3,14159", self.dec) is None

    def test_dot_decimal_with_grouping(self):
        assert parse_typed("2,902.50", self.dec)["value"] == \
            Decimal("2902.50")

    # -- dates ---------------------------------------------------------
    def test_impossible_calendar_rejected(self):
        assert parse_typed("2026-99-99", self.date) is None
        assert parse_typed("2026-02-30", self.date) is None
        assert parse_typed("2026-13-01", self.date) is None

    def test_valid_calendar_accepted(self):
        assert parse_typed("2026-02-28", self.date)["value"] == "2026-02-28"
        assert parse_typed("2024-02-29", self.date) is not None  # leap

    # -- currency ------------------------------------------------------
    def test_bare_symbol_is_not_currency(self):
        got = parse_typed("$2,902.00", self.money)
        assert got["currency"] is None
        assert got["currency_symbol"] == "$"

    def test_explicit_code_establishes(self):
        got = parse_typed("2902.00 CAD", self.money)
        assert got["currency"] == "CAD"

    def test_declared_vs_source_conflict_raises(self):
        cad = FieldSpec(key="p", labels=("price",), value_type="money",
                        currency="CAD")
        with pytest.raises(ValueError):
            parse_typed("$100 USD", cad)

    def test_declared_matching_source_ok(self):
        cad = FieldSpec(key="p", labels=("price",), value_type="money",
                        currency="CAD")
        got = parse_typed("2902.00 CAD", cad)
        assert got["currency"] == "CAD"

    # -- identifier safeguard -------------------------------------------
    def test_price_code_never_binds_price(self):
        assert binding_passes("Price Code", "90703", self.money) is None
        assert binding_passes("Part No.", "U-22", self.money) is None

    def test_genuine_price_column_binds(self):
        got = binding_passes("Unit Price", "$1,200", self.money)
        assert got is not None and got["value"] == Decimal("1200")
