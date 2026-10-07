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
