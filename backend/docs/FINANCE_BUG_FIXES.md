# Finance & Accounting Bug Fixes

This document tracks known finance/accounting bugs discovered during Phase 91 testing and their fixes.

## Critical Bugs (Fixed)

### BUG-001: Epsilon Tolerance in Double-Entry Validation

**Location:** `backend/accounting/ledger.py` line 55

**Description:**
The `EventSourcedLedger.record_transaction()` method used epsilon tolerance to validate double-entry balance:
```python
if abs(debits - credits) > 0.00001:  # WRONG: Hides precision errors
    raise UnbalancedTransactionError(...)
```

This violates GAAP/IFRS requirements for exact equality in accounting. Transactions with tiny imbalances (e.g., 0.00001) would post, causing accumulated balance sheet discrepancies.

**Impact:**
- Balance sheet doesn't balance
- Accumulated rounding errors over time
- Violates accounting standards

**Fix:**
```python
# Import Decimal and validator
from decimal import Decimal
from core.accounting_validator import validate_double_entry, DoubleEntryValidationError

def record_transaction(...):
    try:
        validation = validate_double_entry(entries)
        # Exact comparison - no epsilon
    except DoubleEntryValidationError as e:
        raise UnbalancedTransactionError(...) from e
```

**Fixed in:** Phase 91, Plan 02

**Test:** `backend/tests/property_tests/accounting/test_double_entry_invariants.py`

---

### BUG-002: Float Type for Monetary Values

**Location:** `backend/core/financial_ops_engine.py`, `backend/core/ai_accounting_engine.py`

**Description:**
Monetary values used `float` type which cannot represent decimal fractions exactly:
```python
@dataclass
class SaaSSubscription:
    monthly_cost: float  # WRONG: Precision loss
```

IEEE 754 binary floating-point cannot represent 0.1 exactly. 0.1 + 0.2 != 0.3 in binary.

**Impact:**
- Off-by-one-cent errors in calculations
- Accumulated precision errors
- Test failures due to floating-point comparison

**Fix:**
```python
from decimal import Decimal

@dataclass
class SaaSSubscription:
    monthly_cost: Decimal  # Exact precision
```

All monetary dataclasses updated:
- `SaaSSubscription.monthly_cost`
- `BudgetLimit.monthly_limit`
- `Transaction.amount`
- `Invoice.amount`
- `Bill.amount`
- `Contract.monthly_amount`

**Fixed in:** Phase 91, Plan 01

**Test:** `backend/tests/property_tests/financial/test_decimal_precision_invariants.py`

---

### BUG-003: Database Float Columns for Money

**Location:** `backend/accounting/models.py`

**Description:**
Database schema used `Float` columns for monetary values:
```python
amount = Column(Float, nullable=False)  # WRONG: Database precision loss
```

SQLAlchemy Float maps to REAL/FLOAT in databases, causing precision loss during round-trip.

**Impact:**
- Precision loss when reading from database
- Decimal -> Float -> Decimal conversion errors
- Database doesn't enforce precision

**Fix:**
```python
from sqlalchemy import Numeric

amount = Column(Numeric(precision=19, scale=4), nullable=False)
```

Migration created: `backend/alembic/versions/091_decimal_precision_migration.py`

**Fixed in:** Phase 91, Plan 03

**Test:** `backend/tests/unit/accounting/test_decimal_migration.py`

---

### BUG-004: String Initialization Not Enforced

**Location:** Various files initializing Decimal

**Description:**
Decimal initialized from float captures binary error:
```python
# WRONG: Captures float representation error
price = Decimal(19.99)  # Decimal('19.99000000000000198951966012828052043914794921875')
```

**Impact:**
- Precision errors even when using Decimal type
- Tests pass with wrong values
- Subtle bugs in production

**Fix:**
```python
# CORRECT: Initialize from string
price = Decimal('19.99')  # Exact

# Use utility for safety
from core.decimal_utils import to_decimal
price = to_decimal('19.99')  # Handles string, int, float
```

**Fixed in:** Phase 91, Plan 01 (decimal_utils.py)

**Test:** `backend/tests/property_tests/financial/test_decimal_precision_invariants.py::test_string_initialization_is_exact`

---

### BUG-005: No Global Rounding Strategy

**Location:** Throughout codebase

**Description:**
Rounding strategy not consistently defined. Code mixed:
- Python's `round()` (banker's rounding: round half to even)
- Decimal `.quantize()` with unspecified rounding
- Inconsistent rounding causing discrepancies

**Impact:**
- Tax calculations off by one cent
- Invoice totals don't match line items
- Customer disputes over amounts

**Fix:**
```python
# In backend/core/decimal_utils.py
from decimal import ROUND_HALF_UP, getcontext

# Set global rounding strategy
getcontext().rounding = ROUND_HALF_UP  # Commercial rounding
getcontext().prec = 28

def round_money(value: Union[Decimal, str, float], places: int = 2) -> Decimal:
    decimal_value = to_decimal(value)
    quantizer = Decimal('0.' + '0' * places) if places > 0 else Decimal('1')
    return decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)
```

**Fixed in:** Phase 91, Plan 01

**Test:** `backend/tests/property_tests/financial/test_decimal_precision_invariants.py::test_round_half_up_behavior`

---

## Minor Issues (Fixed)

### ISSUE-001: Property Tests Used Float Strategies

**Location:** `backend/tests/property_tests/financial/test_financial_invariants.py`

**Description:**
Property tests used `st.floats()` which doesn't validate Decimal precision behavior.

**Fix:**
Created `backend/tests/fixtures/decimal_fixtures.py` with `money_strategy`, `high_precision_strategy`
Updated all tests to use Decimal strategies.

**Fixed in:** Phase 91, Plan 04

---

### ISSUE-002: Confidence Score Type Confusion

**Location:** `backend/core/ai_accounting_engine.py`

**Description:**
Confidence scores (0.0 to 1.0) were conflated with monetary values in type hints.

**Fix:**
Documented that confidence scores remain `float` (percentages, not money). Only monetary fields use `Decimal`.

**Fixed in:** Phase 91, Plan 01

---

## Verification

To verify all fixes:

```bash
# Run all financial property tests
pytest backend/tests/property_tests/financial/ -v

# Run accounting property tests
pytest backend/tests/property_tests/accounting/ -v

# Run integration tests
pytest backend/tests/integration/accounting/ -v

# Check for epsilon tolerance (should find none)
grep -r "abs(.*credits" backend/accounting/ backend/core/ --include="*.py"

# Check for float monetary types (should find only confidence percentages)
grep -r "monthly_cost: float" backend/ --include="*.py"
grep -r "amount: float" backend/core/ backend/accounting/ --include="*.py"
```

**Expected results:**
- All tests pass
- No epsilon tolerance found
- No float types for monetary values

---

*Document updated: Phase 91, Plan 05*
*Last updated: 2026-02-25*
