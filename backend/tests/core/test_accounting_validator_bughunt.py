"""
Bug-hunt tests for core/accounting_validator.py (TDD).

Each test documents a genuine, net-new bug discovered via static analysis +
behaviour probing. Tests are written FIRST and must fail for the right reason
before the source is fixed.
"""

import pytest
from decimal import Decimal

from core.accounting_validator import (
    validate_double_entry,
    check_balance_sheet,
    validate_journal_entries,
    DoubleEntryValidationError,
    EntryType,
)


class TestAccountingValidatorBugs:
    """Net-new bugs in accounting_validator."""

    def test_rounding_uses_half_up_not_bankers_rounding(self):
        """BUG: validate_double_entry rounded with default ROUND_HALF_EVEN
        (banker's rounding) instead of ROUND_HALF_UP. Commercial accounting /
        GAAP money rounding is HALF_UP: $0.125 must round to $0.13, not $0.12.

        Concrete failure: a $0.125 debit balanced against a $0.125 credit
        returns balanced=True but reports debits=credits=$0.12 — silently
        recording the wrong cent value in the ledger. HALF_UP yields $0.13.
        """
        entries = [
            {"account_id": "d1", "type": EntryType.DEBIT, "amount": Decimal("0.125")},
            {"account_id": "c1", "type": EntryType.CREDIT, "amount": Decimal("0.125")},
        ]
        result = validate_double_entry(entries)
        assert result["balanced"] is True
        # HALF_UP rounding for money: 0.125 -> 0.13
        assert result["debits"] == Decimal("0.13")
        assert result["credits"] == Decimal("0.13")

    def test_half_up_balanced_journal_not_false_negative(self):
        """BUG (same root cause): two debits of $0.115 each (=$0.23) against
        one $0.23 credit is a balanced journal. Under HALF_EVEN each $0.115
        rounds to $0.12, debits sum to $0.24 != $0.23 -> false imbalance.
        Under HALF_UP each $0.115 rounds to $0.12 too — but the precise
        contract is that the per-leg rounded value must equal HALF_UP, and a
        balanced journal whose legs round identically must remain balanced.
        We use $0.125 legs (HALF_UP=0.13, HALF_EVEN=0.12): two $0.125 debits
        against one $0.26 credit. Under HALF_UP: 0.13+0.13=0.26 == 0.26 (balanced).
        Under HALF_EVEN: 0.12+0.12=0.24 != 0.26 (false imbalance).
        """
        entries = [
            {"account_id": "d1", "type": EntryType.DEBIT, "amount": Decimal("0.125")},
            {"account_id": "d2", "type": EntryType.DEBIT, "amount": Decimal("0.125")},
            {"account_id": "c1", "type": EntryType.CREDIT, "amount": Decimal("0.26")},
        ]
        result = validate_double_entry(entries)
        assert result["balanced"] is True
