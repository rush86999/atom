"""
Simplified tests for Pydantic custom validators

Tests only accounting_validator which doesn't require database/models
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from decimal import Decimal
from core.accounting_validator import (
    validate_double_entry,
    check_balance_sheet,
    validate_journal_entries,
    DoubleEntryValidationError,
    EntryType
)


class TestAccountingValidator:
    """Test double-entry bookkeeping validation with Decimal arithmetic"""

    def test_valid_double_entry(self):
        """Test accept valid debit/credit entries"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("100.00")}
        ]

        result = validate_double_entry(entries)

        assert result["balanced"] is True
        assert result["debits"] == Decimal("100.00")
        assert result["credits"] == Decimal("100.00")
        print("✓ test_valid_double_entry")

    def test_invalid_double_entry_unequal_amounts(self):
        """Test reject when debits != credits"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("90.00")}
        ]

        try:
            validate_double_entry(entries)
            assert False, "Should have raised DoubleEntryValidationError"
        except DoubleEntryValidationError as e:
            assert e.difference == Decimal("10.00")
            print("✓ test_invalid_double_entry_unequal_amounts")

    def test_invalid_negative_amounts(self):
        """Test reject negative amounts"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("-50.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("-50.00")}
        ]

        try:
            validate_double_entry(entries)
            assert False, "Should have raised DoubleEntryValidationError"
        except DoubleEntryValidationError:
            print("✓ test_invalid_negative_amounts")

    def test_accounting_decimal_precision(self):
        """Test Decimal precision rounding to 2 places"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.123")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("100.123")}
        ]

        result = validate_double_entry(entries)

        # Should round to 2 decimal places
        assert result["debits"] == Decimal("100.12")
        assert result["credits"] == Decimal("100.12")
        print("✓ test_accounting_decimal_precision")

    def test_accounting_zero_amounts(self):
        """Test handling of zero amounts (edge case)"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("0.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("0.00")}
        ]

        result = validate_double_entry(entries)

        assert result["balanced"] is True
        assert result["debits"] == Decimal("0.00")
        assert result["credits"] == Decimal("0.00")
        print("✓ test_accounting_zero_amounts")

    def test_entry_type_enum_values(self):
        """Test EntryType enum has correct values"""
        assert EntryType.DEBIT == "debit"
        assert EntryType.CREDIT == "credit"
        print("✓ test_entry_type_enum_values")

    def test_entry_type_string_conversion(self):
        """Test EntryType accepts string values"""
        entries = [
            {"account_id": "acc_1", "type": "debit", "amount": Decimal("50.00")},
            {"account_id": "acc_2", "type": "credit", "amount": Decimal("50.00")}
        ]

        result = validate_double_entry(entries)

        assert result["balanced"] is True
        print("✓ test_entry_type_string_conversion")

    def test_check_balance_sheet_valid(self):
        """Test balance sheet equation: Assets = Liabilities + Equity"""
        balance_sheet = {
            "assets": [Decimal("100.00")],
            "liabilities": [Decimal("50.00")],
            "equity": [Decimal("50.00")]
        }

        result = check_balance_sheet(balance_sheet)

        assert result["balanced"] is True
        assert result["discrepancy"] is None
        print("✓ test_check_balance_sheet_valid")

    def test_check_balance_sheet_invalid(self):
        """Test reject when balance sheet doesn't balance"""
        balance_sheet = {
            "assets": [Decimal("100.00")],
            "liabilities": [Decimal("30.00")],
            "equity": [Decimal("50.00")]
        }

        result = check_balance_sheet(balance_sheet)

        assert result["balanced"] is False
        assert result["discrepancy"] == Decimal("20.00")
        print("✓ test_check_balance_sheet_invalid")

    def test_check_balance_sheet_empty(self):
        """Test balance sheet with empty lists"""
        balance_sheet = {
            "assets": [],
            "liabilities": [],
            "equity": []
        }

        result = check_balance_sheet(balance_sheet)

        assert result["balanced"] is True
        assert result["assets"] == Decimal("0.00")
        assert result["liabilities"] == Decimal("0.00")
        assert result["equity"] == Decimal("0.00")
        print("✓ test_check_balance_sheet_empty")

    def test_validate_journal_entries_missing_fields(self):
        """Test detect missing required fields"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT},  # missing amount
            {"amount": Decimal("100.00")}  # missing account_id and type
        ]

        errors = validate_journal_entries(entries)

        assert len(errors) > 0
        assert any("amount" in error for error in errors)
        assert any("account_id" in error for error in errors)
        print("✓ test_validate_journal_entries_missing_fields")

    def test_validate_journal_entries_invalid_amount(self):
        """Test detect invalid amount format"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": "invalid"}
        ]

        errors = validate_journal_entries(entries)

        assert len(errors) > 0
        assert any("invalid amount" in error.lower() for error in errors)
        print("✓ test_validate_journal_entries_invalid_amount")

    def test_validate_journal_entries_negative_amount(self):
        """Test detect negative amounts in journal entries"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("-10.00")}
        ]

        errors = validate_journal_entries(entries)

        assert len(errors) > 0
        assert any("negative" in error.lower() for error in errors)
        print("✓ test_validate_journal_entries_negative_amount")

    def test_validate_journal_entries_all_valid(self):
        """Test validate_journal_entries with all valid entries"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.00")},
            {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("100.00")}
        ]

        errors = validate_journal_entries(entries)

        assert len(errors) == 0
        print("✓ test_validate_journal_entries_all_valid")

    def test_double_entry_requires_two_entries(self):
        """Test double-entry requires at least two entries"""
        entries = [
            {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.00")}
        ]

        try:
            validate_double_entry(entries)
            assert False, "Should have raised DoubleEntryValidationError"
        except DoubleEntryValidationError as e:
            assert "at least two entries" in str(e).lower()
            print("✓ test_double_entry_requires_two_entries")

    def test_double_entry_rejects_empty_list(self):
        """Test reject empty entries list"""
        try:
            validate_double_entry([])
            assert False, "Should have raised DoubleEntryValidationError"
        except DoubleEntryValidationError as e:
            assert "at least one entry" in str(e).lower()
            print("✓ test_double_entry_rejects_empty_list")


if __name__ == "__main__":
    # Run all tests
    test_class = TestAccountingValidator()
    test_methods = [m for m in dir(test_class) if m.startswith('test_')]

    total_tests = len(test_methods)
    passed_tests = 0
    failed_tests = []

    for method_name in test_methods:
        try:
            method = getattr(test_class, method_name)
            method()
            passed_tests += 1
        except Exception as e:
            failed_tests.append(f"{method_name}: {e}")

    print(f"\n{'='*60}")
    print(f"Tests run: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    if failed_tests:
        print(f"\nFailed tests:")
        for failure in failed_tests:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print("\n✓ All accounting validator tests passed!")
        sys.exit(0)
