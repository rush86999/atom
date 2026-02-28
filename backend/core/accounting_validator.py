"""
Double-Entry Bookkeeping Validation

Ensures accounting invariants using exact Decimal arithmetic.
Per GAAP/IFRS: debits must equal credits exactly - no epsilon tolerance.
"""

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import List, Dict, Any, Optional


class EntryType(str, Enum):
    """Journal entry type"""
    DEBIT = "debit"
    CREDIT = "credit"


class DoubleEntryValidationError(Exception):
    """Raised when double-entry validation fails"""

    def __init__(self, message: str, debits: Decimal, credits: Decimal):
        super().__init__(message)
        self.debits = debits
        self.credits = credits
        self.difference = abs(debits - credits)


def validate_double_entry(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate that debits equal credits exactly (no epsilon tolerance).

    Args:
        entries: List of entry dicts with 'account_id', 'type' (DEBIT/CREDIT), 'amount'

    Returns:
        Dict with 'balanced' (bool), 'debits' (Decimal), 'credits' (Decimal)

    Raises:
        DoubleEntryValidationError: If debits != credits
        ValueError: If entries are invalid

    Examples:
        >>> validate_double_entry([
        ...     {"account_id": "acc_1", "type": EntryType.DEBIT, "amount": Decimal("100.00")},
        ...     {"account_id": "acc_2", "type": EntryType.CREDIT, "amount": Decimal("100.00")}
        ... ])
        {'balanced': True, 'debits': Decimal('100.00'), 'credits': Decimal('100.00')}
    """
    if not entries:
        raise DoubleEntryValidationError(
            "Transaction must have at least one entry",
            Decimal('0.00'),
            Decimal('0.00')
        )

    if len(entries) < 2:
        raise DoubleEntryValidationError(
            "Transaction must have at least two entries (double-entry)",
            Decimal('0.00'),
            Decimal('0.00')
        )

    # Sum debits and credits separately
    debits = Decimal('0.00')
    credits = Decimal('0.00')

    for entry in entries:
        # Validate entry structure
        if "amount" not in entry or "type" not in entry:
            raise ValueError(f"Invalid entry: {entry}")

        # Convert amount to Decimal
        try:
            amount = Decimal(str(entry["amount"]))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid amount: {entry['amount']}")

        # Reject negative amounts
        if amount < 0:
            raise DoubleEntryValidationError(
                f"Negative amounts not allowed: {amount}",
                Decimal('0.00'),
                Decimal('0.00')
            )

        # Round to 2 decimal places (cents)
        amount = amount.quantize(Decimal('0.00'))

        entry_type = entry["type"]
        if isinstance(entry_type, str):
            entry_type = EntryType(entry_type.lower())

        if entry_type == EntryType.DEBIT:
            debits += amount
        elif entry_type == EntryType.CREDIT:
            credits += amount
        else:
            raise ValueError(f"Invalid entry type: {entry_type}")

    # EXACT comparison - no epsilon tolerance per GAAP/IFRS
    if debits != credits:
        raise DoubleEntryValidationError(
            f"Debits ({debits}) do not equal credits ({credits}). "
            f"Difference: {abs(debits - credits)}",
            debits,
            credits
        )

    return {
        "balanced": True,
        "debits": debits,
        "credits": credits
    }


def check_balance_sheet(balance_sheet: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate balance sheet equation: Assets = Liabilities + Equity

    Args:
        balance_sheet: Dict with 'assets', 'liabilities', 'equity' lists

    Returns:
        Dict with 'balanced' (bool) and optional 'discrepancy'

    Examples:
        >>> check_balance_sheet({
        ...     "assets": [Decimal("100.00")],
        ...     "liabilities": [Decimal("50.00")],
        ...     "equity": [Decimal("50.00")]
        ... })
        {'balanced': True, 'discrepancy': None}
    """
    assets_list = balance_sheet.get("assets", [])
    liabilities_list = balance_sheet.get("liabilities", [])
    equity_list = balance_sheet.get("equity", [])

    # Sum each category
    def sum_amounts(amounts):
        return sum((Decimal(str(a)) for a in amounts), Decimal('0.00'))

    total_assets = sum_amounts(assets_list)
    total_liabilities = sum_amounts(liabilities_list)
    total_equity = sum_amounts(equity_list)

    expected_equity = total_assets - total_liabilities
    discrepancy = total_equity - expected_equity

    return {
        "balanced": discrepancy == 0,
        "discrepancy": abs(discrepancy) if discrepancy != 0 else None,
        "assets": total_assets,
        "liabilities": total_liabilities,
        "equity": total_equity
    }


def validate_journal_entries(entries: List[Dict[str, Any]]) -> List[str]:
    """
    Validate journal entries and return list of errors (empty if valid).

    Args:
        entries: List of journal entry dicts

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []

    for i, entry in enumerate(entries):
        # Check required fields
        if "account_id" not in entry:
            errors.append(f"Entry {i}: missing account_id")
        if "type" not in entry:
            errors.append(f"Entry {i}: missing type")
        if "amount" not in entry:
            errors.append(f"Entry {i}: missing amount")

        # Validate amount
        if "amount" in entry:
            try:
                amount = Decimal(str(entry["amount"]))
                if amount < 0:
                    errors.append(f"Entry {i}: negative amount {amount}")
            except (InvalidOperation, ValueError):
                errors.append(f"Entry {i}: invalid amount {entry['amount']}")

    return errors
