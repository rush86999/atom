"""
Property-Based Tests for Double-Entry Bookkeeping Invariants

Tests the fundamental accounting equation: debits must equal credits exactly.
Uses Decimal precision - no epsilon tolerance allowed per GAAP/IFRS.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from hypothesis import given, strategies as st, assume, settings, example
from typing import List, Dict, Any
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from core.accounting_validator import (
    validate_double_entry,
    check_balance_sheet,
    DoubleEntryValidationError,
    EntryType
)


class TestDoubleEntryValidationInvariants:
    """Tests for double-entry validation invariants"""

    @given(
        amount=st.decimals(min_value='0.01', max_value='1000000.00', places=2),
        account_count=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=100)
    def test_balanced_transaction_always_passes(self, amount, account_count):
        """Test that any balanced transaction passes validation"""
        # Create split transaction across multiple accounts
        entries = []
        per_account = amount / account_count
        rounded_amount = (per_account.quantize(Decimal('0.00')))

        # Create alternating debit/credit entries
        for i in range(account_count):
            entry_type = EntryType.DEBIT if i % 2 == 0 else EntryType.CREDIT
            entries.append({
                "account_id": f"acc_{i}",
                "type": entry_type,
                "amount": rounded_amount
            })

        # Calculate total debits and credits
        debits = sum(e["amount"] for e in entries if e["type"] == EntryType.DEBIT)
        credits = sum(e["amount"] for e in entries if e["type"] == EntryType.CREDIT)

        # Only test if naturally balanced (can happen with rounding)
        if debits == credits:
            result = validate_double_entry(entries)
            assert result["balanced"] is True
            assert result["debits"] == debits
            assert result["credits"] == credits

    @given(
        debit_amount=st.decimals(min_value='0.01', max_value='10000.00', places=2),
        credit_amount=st.decimals(min_value='0.01', max_value='10000.00', places=2)
    )
    @settings(max_examples=100)
    def test_imbalanced_transaction_fails(self, debit_amount, credit_amount):
        """Test that imbalanced transactions fail validation"""
        assume(debit_amount != credit_amount)

        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": debit_amount},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": credit_amount}
        ]

        with pytest.raises(DoubleEntryValidationError) as exc_info:
            validate_double_entry(entries)

        error = exc_info.value
        assert error.debits == debit_amount
        assert error.credits == credit_amount
        assert error.difference == abs(debit_amount - credit_amount)

    @given(
        amount=st.decimals(min_value='0.01', max_value='10000.00', places=2)
    )
    @settings(max_examples=50)
    @example(amount=Decimal('100.00'))
    def test_perfectly_balanced_passes(self, amount):
        """Test that perfectly balanced transaction passes"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": amount},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": amount}
        ]

        result = validate_double_entry(entries)
        assert result["balanced"] is True
        assert result["debits"] == amount
        assert result["credits"] == amount

    @given(
        amounts=st.lists(
            st.decimals(min_value='0.01', max_value='1000.00', places=2),
            min_size=2,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_complex_transaction_validation(self, amounts):
        """Test validation of complex multi-entry transactions"""
        # Split amounts into debits and credits
        entries = []
        for i, amount in enumerate(amounts):
            entry_type = EntryType.DEBIT if i % 2 == 0 else EntryType.CREDIT
            entries.append({
                "account_id": f"acc_{i}",
                "type": entry_type,
                "amount": amount
            })

        debits = sum(e["amount"] for e in entries if e["type"] == EntryType.DEBIT)
        credits = sum(e["amount"] for e in entries if e["type"] == EntryType.CREDIT)

        if debits == credits:
            result = validate_double_entry(entries)
            assert result["balanced"] is True
        else:
            with pytest.raises(DoubleEntryValidationError):
                validate_double_entry(entries)

    @given(
        amounts=st.lists(
            st.decimals(min_value='0.01', max_value='1000.00', places=2),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_single_entry_fails(self, amounts):
        """Test that single-entry transactions fail"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": amounts[0]}
        ]

        with pytest.raises(DoubleEntryValidationError):
            validate_double_entry(entries)

    @given(
        amount=st.decimals(min_value='0.01', max_value='10000.00', places=2)
    )
    @settings(max_examples=50)
    def test_zero_discrepancy_detected(self, amount):
        """Test that even tiny discrepancies are detected (no epsilon tolerance)"""
        # Create transaction with 1-cent difference
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": amount},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": amount - Decimal('0.01')}
        ]

        with pytest.raises(DoubleEntryValidationError) as exc_info:
            validate_double_entry(entries)

        # The difference should be exactly 0.01
        assert exc_info.value.difference == Decimal('0.01')


class TestBalanceSheetInvariants:
    """Tests for balance sheet equation: Assets = Liabilities + Equity"""

    @given(
        assets=st.lists(
            st.decimals(min_value='0.00', max_value='1000000.00', places=2),
            min_size=1,
            max_size=20
        ),
        liabilities=st.lists(
            st.decimals(min_value='0.00', max_value='500000.00', places=2),
            min_size=1,
            max_size=10
        ),
        equity=st.lists(
            st.decimals(min_value='0.00', max_value='500000.00', places=2),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_balance_sheet_equation(self, assets, liabilities, equity):
        """Test that Assets = Liabilities + Equity holds"""
        total_assets = sum(assets, Decimal('0.00'))
        total_liabilities = sum(liabilities, Decimal('0.00'))
        total_equity = sum(equity, Decimal('0.00'))

        # For balanced sheet: assets must equal liabilities + equity
        # Create adjustment to make it balance
        adjustment = (total_liabilities + total_equity) - total_assets

        balance_sheet = {
            "assets": assets + [adjustment] if adjustment != 0 else assets,
            "liabilities": liabilities,
            "equity": equity
        }

        result = check_balance_sheet(balance_sheet)
        assert result["balanced"] is True

    @given(
        assets=st.lists(
            st.decimals(min_value='1000.00', max_value='100000.00', places=2),
            min_size=2,
            max_size=10
        ),
        discrepancy=st.decimals(min_value='0.01', max_value='1000.00', places=2)
    )
    @settings(max_examples=50)
    def test_balance_sheet_discrepancy_detected(self, assets, discrepancy):
        """Test that balance sheet discrepancies are detected"""
        total_assets = sum(assets, Decimal('0.00'))

        # Create imbalanced sheet
        balance_sheet = {
            "assets": assets,
            "liabilities": [total_assets / 2],
            "equity": [total_assets / 2 - discrepancy]  # Intentionally off
        }

        result = check_balance_sheet(balance_sheet)
        assert result["balanced"] is False
        assert result["discrepancy"] == discrepancy


class TestDecimalPrecisionInvariants:
    """Tests for Decimal precision handling"""

    @given(
        amount=st.decimals(min_value='0.001', max_value='1000.00', places=3)
    )
    @settings(max_examples=50)
    def test_fractional_cents_rounded(self, amount):
        """Test that fractional cents are properly rounded"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": amount},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": amount}
        ]

        # Should round to 2 decimal places
        result = validate_double_entry(entries)
        assert result["debits"].as_tuple().exponent >= -2
        assert result["credits"].as_tuple().exponent >= -2

    @given(
        amount=st.decimals(min_value='1000000.00', max_value='10000000000.00', places=2)
    )
    @settings(max_examples=50)
    def test_large_amounts_handled(self, amount):
        """Test that large amounts (billions) are handled correctly"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": amount},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": amount}
        ]

        result = validate_double_entry(entries)
        assert result["balanced"] is True
        assert result["debits"] == amount


class TestEdgeCases:
    """Tests for edge cases and error conditions"""

    def test_empty_entries_fails(self):
        """Test that empty entry list fails validation"""
        with pytest.raises(DoubleEntryValidationError):
            validate_double_entry([])

    @given(
        amount=st.decimals(min_value='-100.00', max_value='-0.01', places=2)
    )
    @settings(max_examples=50)
    def test_negative_amounts_rejected(self, amount):
        """Test that negative amounts are rejected"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": amount},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": amount}
        ]

        with pytest.raises(DoubleEntryValidationError) as exc_info:
            validate_double_entry(entries)

        assert "negative" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    @given(
        amount=st.decimals(min_value='0.00', max_value='10000.00', places=2)
    )
    @settings(max_examples=50)
    def test_zero_amounts_allowed(self, amount):
        """Test that zero amounts are allowed"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal('0.00')},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal('0.00')}
        ]

        result = validate_double_entry(entries)
        assert result["balanced"] is True
