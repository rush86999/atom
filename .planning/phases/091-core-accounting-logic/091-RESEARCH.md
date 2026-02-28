# Phase 91: Core Accounting Logic - Research

**Researched:** February 25, 2026
**Domain:** Financial Accounting Precision & Testing
**Confidence:** HIGH

## Summary

Phase 91 requires establishing a Decimal-first foundation for all financial calculations in Atom to prevent floating-point precision errors that violate accounting standards (GAAP/IFRS). The current codebase uses `float` extensively for monetary values (`financial_ops_engine.py`, `accounting/models.py`, `ai_accounting_engine.py`), creating cascading precision errors in transaction processing, budget calculations, and reconciliation. Existing property tests (814 lines financial invariants, 705 lines accounting invariants) already demonstrate Hypothesis patterns but rely on epsilon tolerances (`abs(debits - credits) > 0.00001`) instead of exact precision validation.

**Primary recommendation:** Establish `decimal.Decimal` as the canonical type for all monetary values at three critical boundaries (API layer, database schema, calculation logic) with proper rounding strategy (banker's rounding/ROUND_HALF_EVEN) and comprehensive property-based tests for financial invariants (debits=credits, conservation of value, idempotency). Fix known float-precision bugs in `EventSourcedLedger` (line 55) and migrate `SaaSSubscription.monthly_cost`, `BudgetLimit.monthly_limit`, `Transaction.amount`, `JournalEntry.amount` from Float to Decimal.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Python `decimal.Decimal`** |stdlib (3.11+)|Exact decimal arithmetic for monetary values|IEEE 754 binary floating-point cannot represent 0.1 exactly (0.1 + 0.2 != 0.3). GAAP/IFRS require exact precision. Decimal provides adjustable precision (default 28 places), explicit rounding modes (ROUND_HALF_UP, ROUND_HALF_EVEN), and string initialization to avoid binary conversion errors|
| **Hypothesis 6.92+**|existing (requirements.txt)|Property-based testing for financial invariants|Already proven with 1,500+ lines of property tests. Auto-generates edge cases (zero amounts, negative values, large magnitude) that example-based tests miss. Critical for validating invariants across all valid inputs|
| **SQLAlchemy Numeric type**|existing (2.0+)|Database column type for monetary values|Maps to DECIMAL/NUMERIC in PostgreSQL/SQLite. Preserves precision across DB round-trips. Replaces Float columns (currently used for `amount`, `balance`, `monthly_cost`)|

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **factory_boy 3.3+**|add|Declarative test data for financial objects|Complex fixture relationships (Invoice -> LineItems -> Payments) without 100+ lines of boilerplate. Not in requirements.txt yet - add for this phase|
| **pytest-freezegun 0.4+**|add|Time freezing for date-dependent financial tests|Invoice aging (Net 30, Net 60), payment terms, revenue recognition timing. Prevents tests that fail at month boundaries. Not in requirements.txt yet - add for this phase|

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Decimal (stdlib) | `moneyed` or `py-money` library | Money libraries add currency handling, exchange rates, formatting. Overkill for Atom's current USD-centric needs. Decimal is sufficient, zero dependencies, explicit control over rounding.|
| SQLAlchemy Numeric | Store as INTEGER cents | Storing cents requires multiply/divide by 100 at every boundary (API, DB, calculations). Easy to forget, introduces bugs. Numeric/Decimal matches Decimal type directly.|
| Banker's rounding (ROUND_HALF_EVEN) | ROUND_HALF_UP (commercial rounding) | Both are GAAP-compliant. Banker's rounding reduces bias in large datasets (equal up/down rounding). Atom should pick one and document - recommend ROUND_HALF_UP for business-familiar behavior, unless processing high-volume transactions where bias matters|

**Installation:**
```bash
# factory_boy not in requirements.txt - add to testing dependencies
pip install factory_boy==3.3.0
pip install pytest-freezegun==0.4.2

# Add to requirements.txt under testing section:
# factory_boy>=3.3.0,<4.0.0
# pytest-freezegun>=0.4.0,<0.5.0
```

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── core/
│   ├── financial_ops_engine.py          # EXISTING - refactor to Decimal
│   ├── ai_accounting_engine.py           # EXISTING - refactor to Decimal
│   ├── decimal_utils.py                  # NEW: Decimal conversion, rounding helpers
│   └── accounting_validator.py           # NEW: Double-entry validation invariants
├── accounting/
│   ├── ledger.py                         # EXISTING - fix epsilon tolerance bug
│   ├── models.py                         # EXISTING - Float -> Decimal migration
│   └── reconciliation.py                 # EXISTING - tolerance-based matching
├── tests/
│   ├── property_tests/financial/         # EXISTING - 814 lines
│   ├── property_tests/accounting/        # EXISTING - 705 lines
│   ├── unit/financial/                   # NEW: Calculation logic tests
│   ├── fixtures/
│   │   ├── financial_fixtures.py         # NEW: factory_boy fixtures
│   │   └── decimal_fixtures.py           # NEW: Decimal strategy for Hypothesis
│   └── conftest.py                       # EXISTING - add Decimal strategies
└── alembic/versions/
    └── XXX_decimal_precision_migration.py # NEW: Float -> Decimal schema migration
```

### Pattern 1: Decimal-First API Boundary

**What:** All API endpoints accept/return monetary values as strings or Decimals, never float. Convert at the request boundary.

**When to use:** Every financial API endpoint (`/api/financial*`, `/api/billing`, accounting routes).

**Example:**
```python
# Source: Based on existing /Users/rushiparikh/projects/atom/backend/api/financial_routes.py patterns
from decimal import Decimal, InvalidOperation
from pydantic import Field, validator

class FinancialAccountCreate(BaseModel):
    """API request model with Decimal precision"""
    balance: str = Field(..., description="Balance as string to preserve precision")  # Accept string

    @validator('balance')
    def parse_balance(cls, v):
        """Convert string to Decimal at API boundary"""
        try:
            return Decimal(str(v))  # Initialize from string, not float
        except InvalidOperation:
            raise ValueError(f"Invalid decimal amount: {v}")

# Bad pattern (current code):
# account.balance = float(request.balance)  # LOSSES PRECISION

# Correct pattern:
account.balance = Decimal(request.balance)  # Preserves exact value
```

### Pattern 2: Database Schema Decimal Migration

**What:** Replace Float columns with Numeric(precision=19, scale=4) or higher. Scale=4 supports thousandth-decimal precision (0.0001) for tax calculations.

**When to use:** Alembic migration for all monetary columns.

**Example:**
```python
# Source: SQLAlchemy documentation on Numeric type
from alembic import op
import sqlalchemy as sa

def upgrade():
    """Migrate Float to Decimal for monetary columns"""
    # Transaction.amount (currently Float)
    op.alter_column(
        'accounting_transactions',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        nullable=True
    )

    # JournalEntry.amount (currently Float)
    op.alter_column(
        'accounting_journal_entries',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        nullable=False
    )

    # FinancialAccount.balance (currently Float)
    op.alter_column(
        'financial_accounts',
        'balance',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        default='0.0000'
    )

def downgrade():
    """Revert to Float (not recommended)"""
    op.alter_column('accounting_transactions', 'amount', type_=sa.Float())
    # ... other columns
```

### Pattern 3: Double-Entry Validation with Exact Precision

**What:** Validate debits == credits using exact Decimal comparison, not epsilon tolerance. Fail fast if unbalanced.

**When to use:** Every transaction posting in `EventSourcedLedger.record_transaction()`.

**Example:**
```python
# Source: Existing /Users/rushiparikh/projects/atom/backend/accounting/ledger.py (line 55)
from decimal import Decimal

def record_transaction(self, entries: List[Dict[str, Any]]) -> Transaction:
    """Record a double-entry transaction with exact precision validation"""

    # Validate balance using Decimal (BAD: uses epsilon tolerance)
    # debits = sum(e["amount"] for e in entries if e["type"] == EntryType.DEBIT)
    # credits = sum(e["amount"] for e in entries if e["type"] == EntryType.CREDIT)
    # if abs(debits - credits) > 0.00001:  # WRONG: Hides precision errors

    # CORRECT: Use exact Decimal comparison
    debits = sum(Decimal(str(e["amount"])) for e in entries if e["type"] == EntryType.DEBIT)
    credits = sum(Decimal(str(e["amount"])) for e in entries if e["type"] == EntryType.CREDIT)

    if debits != credits:  # Exact comparison - no epsilon
        raise UnbalancedTransactionError(
            f"Debits ({debits}) do not match Credits ({credits}). "
            f"Difference: {abs(debits - credits)}"
        )
```

### Pattern 4: Rounding Strategy Consistency

**What:** Define explicit rounding strategy at module level. Use for all division, percentage calculations, tax computations.

**When to use:** Division operations, tax calculations, FX conversions, budget allocations.

**Example:**
```python
# Source: Python decimal module documentation
from decimal import Decimal, ROUND_HALF_UP, getcontext

# Set global context
getcontext().rounding = ROUND_HALF_UP  # Commercial rounding (5 rounds up)
getcontext().prec = 28  # Sufficient for financial calculations

def calculate_tax(subtotal: Decimal, tax_rate: Decimal) -> Decimal:
    """Calculate tax with explicit rounding"""
    tax = subtotal * (tax_rate / Decimal('100'))
    # Round to 2 decimal places (cents)
    return tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Example usage:
# subtotal = Decimal('100.00')
# tax_rate = Decimal('8.25')  # 8.25%
# tax = calculate_tax(subtotal, tax_rate)  # Decimal('8.25')
```

### Anti-Patterns to Avoid

- **Mixing Decimal and float:** Never initialize Decimal from float: `Decimal(0.1)` captures binary representation error. Always use string: `Decimal('0.1')`.
- **Epsilon tolerance in accounting:** `abs(a - b) > 0.00001` hides precision errors. Accounting requires exact equality. Use epsilon only for external data (API responses, FX rates).
- **Float for intermediate calculations:** Never convert Decimal to float for math operations, then back to Decimal. All intermediate values must remain Decimal.
- **Implicit rounding:** Never rely on default string formatting for rounding. Always use `.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
|Decimal conversion utilities|Custom validation, parsing logic|`decimal.Decimal(str(value))` with `try/except InvalidOperation`|Decimal module handles edge cases (scientific notation, commas, whitespace). Custom conversion misses edge cases like "1,000.50" or "1e2"|
|Rounding functions|Custom round(x, 2)|`Decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`|Built-in quantize is explicit, banker's rounding compliant, handles negative numbers correctly|
|Money formatting|Custom f-string formatting|`locale.currency()` or `f"${amount:,.2f}"`|Locale-aware formatting handles commas, currency symbols, international formats|
|Property test strategies|Custom random Decimal generators|`st.decimals(min_value, max_value, places)` from Hypothesis|Hypothesis strategy handles precision, edge cases, shrinking automatically|

**Key insight:** The Python stdlib `decimal` module is mature, battle-tested, and handles all edge cases for financial arithmetic. Custom rounding or conversion code inevitably introduces bugs (e.g., off-by-one errors in the last cent).

## Common Pitfalls

### Pitfall 1: Floating-Point Precision in Financial Calculations

**What goes wrong:** Using `float` for monetary values causes binary representation errors that accumulate in batch processing. Example: `0.1 + 0.2 == 0.3` returns `False` because 0.1 is stored as 0.100000000000000005551. In Atom's current code, `EventSourcedLedger` uses `abs(debits - credits) > 0.00001` to hide this error instead of fixing it.

**Why it happens:** IEEE 754 binary floating-point cannot represent decimal fractions exactly. 0.1, 0.2, 0.3 are repeating fractions in binary. Float has ~15 decimal digits of precision, but errors accumulate with addition/multiplication.

**How to avoid:**
1. Use `decimal.Decimal` for all monetary values at API boundaries
2. Initialize from strings: `Decimal('100.00')` not `Decimal(100.00)`
3. Define rounding strategy globally: `getcontext().rounding = ROUND_HALF_UP`
4. Database schema: Use `Numeric(precision=19, scale=4)` not `Float`
5. Property test precision invariants: `@given(st.decimals(min_value='0.01', max_value='1000000.00', places=2))`

**Warning signs:**
- Epsilon tolerances in accounting code (`abs(x - y) > 0.00001`)
- Test comments mentioning "floating point precision"
- Float columns in database schema for monetary values
- Type hints using `float` for amount/balance/price

### Pitfall 2: Inadequate Double-Entry Validation

**What goes wrong:** Transactions post without validating debits == credits, or validation uses epsilon tolerance. This violates fundamental accounting principles and causes balance sheet to not balance.

**Why it happens:** Developers use epsilon tolerance from numerical analysis, not realizing accounting requires exact equality. Float precision makes exact comparison impossible, so tolerance is added as workaround.

**How to avoid:**
1. Exact Decimal comparison: `debits == credits` (no epsilon)
2. Validate before database commit (fail fast)
3. Property test invariant: `@given(entries=st.lists(...))` always validates balance
4. Log all unbalanced transaction attempts for audit
5. Database constraint: `CHECK (debit_total = credit_total)` if supported

**Warning signs:**
- `abs(debits - credits) > epsilon` in validation code
- Transactions posting without balance validation
- Manual balance sheet reconciliation needed
- "Adjusting entries" to fix imbalances

### Pitfall 3: Inconsistent Rounding Strategy

**What goes wrong:** Different parts of codebase use different rounding (Python's `round()` vs. Decimal `quantize()`, banker's vs. commercial rounding). This causes discrepancies in tax calculations, FX conversions, invoice totals.

**Why it happens:** Python's built-in `round()` uses banker's rounding (round half to even), but business users expect commercial rounding (round half up). No global rounding strategy defined.

**How to avoid:**
1. Define global rounding: `getcontext().rounding = ROUND_HALF_UP`
2. Always use `.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)` for cents
3. Document rounding strategy in API docs
4. Property test rounding invariants: `round(x) + round(y) == round(x + y)` for non-edge cases
5. Test edge cases: `0.005`, `0.015`, `1.005`

**Warning signs:**
- Mixed use of `round()` and `.quantize()`
- Tax calculations off by one cent
- Customer complaints about invoice totals
- Manual adjustment entries for rounding differences

### Pitfall 4: Property Testing Without Financial Invariants

**What goes wrong:** Tests generate hundreds of random examples but don't validate accounting principles (conservation of value, idempotency, balance sheet equation). Tests pass but bugs remain.

**Why it happens:** Developers apply generic property testing patterns without identifying domain-specific invariants. Hypothesis generates values but tests don't check meaningful constraints.

**How to avoid:**
1. Document invariants first (3-5 per module) before writing tests
2. Test conservation of value: `total_before = total_after` for any transfer
3. Test idempotency: `post_transaction(tx) == post_transaction(post_transaction(tx))`
4. Test double-entry: `debits == credits` for all transactions
5. Test balance sheet: `assets = liabilities + equity` for any transaction set

**Warning signs:**
- Property tests without assertion invariants
- Tests only check "no exception raised"
- Hypothesis strategies without meaningful assertions
- Bug-finding evidence missing from docstrings

## Code Examples

Verified patterns from official sources:

### Decimal Initialization (Correct vs. Incorrect)

```python
# Source: Python Decimal module documentation
from decimal import Decimal

# CORRECT: Initialize from string
price = Decimal('19.99')
tax_rate = Decimal('0.0825')
total = price * (1 + tax_rate)  # Decimal('21.641175')

# INCORRECT: Initialize from float (captures binary error)
price = Decimal(19.99)  # Decimal('19.99000000000000198951966012828052043914794921875')

# INCORRECT: Float arithmetic before Decimal
total = 19.99 * 1.0825  # float: 21.641175000000002
total_decimal = Decimal(total)  # Captures float error

# CORRECT: All Decimal arithmetic
total = Decimal('19.99') * Decimal('1.0825')  # Exact
```

### Property Test for Double-Entry Invariant

```python
# Source: Based on existing Atom property test patterns
from decimal import Decimal
from hypothesis import given, strategies as st
import pytest

@given(
    amount=st.decimals(min_value='0.01', max_value='1000000.00', places=2),
    account_count=st.integers(min_value=2, max_value=10)
)
def test_double_entry_invariant(amount, account_count):
    """Test that debits always equal credits for any valid amount"""
    from accounting.ledger import EventSourcedLedger

    # Create split transaction across multiple accounts
    entries = []
    per_account = amount / account_count

    for i in range(account_count):
        entries.append({
            "account_id": f"acc_{i}",
            "type": "debit" if i % 2 == 0 else "credit",
            "amount": per_account.quantize(Decimal('0.01'))  # Round to cents
        })

    # Must balance exactly
    debits = sum(e["amount"] for e in entries if e["type"] == "debit")
    credits = sum(e["amount"] for e in entries if e["type"] == "credit")

    assert debits == credits, f"Double-entry violated: debits={debits}, credits={credits}"
```

### Rounding Strategy for Tax Calculations

```python
# Source: Decimal documentation with ROUND_HALF_UP
from decimal import Decimal, ROUND_HALF_UP

def calculate_invoice_total(subtotal: Decimal, tax_rate_percent: Decimal) -> Dict[str, Decimal]:
    """Calculate invoice total with explicit rounding at each step"""
    # Calculate tax: subtotal * (rate / 100)
    tax_rate_decimal = tax_rate_percent / Decimal('100')
    tax = subtotal * tax_rate_decimal

    # Round tax to 2 decimal places (cents)
    tax_rounded = tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Calculate total
    total = subtotal + tax_rounded

    # Verify total precision
    assert total.as_tuple().exponent >= -2, "Total must have at most 2 decimal places"

    return {
        "subtotal": subtotal.quantize(Decimal('0.01')),
        "tax": tax_rounded,
        "total": total.quantize(Decimal('0.01'))
    }

# Example:
# calculate_invoice_total(Decimal('100.00'), Decimal('8.25'))
# => {'subtotal': Decimal('100.00'), 'tax': Decimal('8.25'), 'total': Decimal('108.25')}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
|Float for monetary values|Decimal for exact precision|Python 3.1+ (2009)|Standard for financial software. No reason to use Float in 2026|
|Epsilon tolerance in accounting|Exact Decimal comparison|Established pattern (GAAP/IFRS)|Accounting requires exact equality. Epsilon hides bugs|
|Implicit rounding (round())|Explicit .quantize() with strategy|Decimal module introduction|Prevents rounding errors, makes policy explicit|
|Hypothesis for numeric tests|Hypothesis with Decimal strategies|Hypothesis 6.0+ (2020)|First-class Decimal support, automatic edge case generation|

**Deprecated/outdated:**
- **Float in database schemas for money:** PostgreSQL/SQLite both support NUMERIC/DECIMAL. No performance penalty. Using Float for monetary values is considered a bug in 2026.
- **epsilon tolerances in double-entry:** Modern accounting systems validate `debits == credits` exactly. Epsilon tolerance is only acceptable for external data (API responses with limited precision).
- **Python 2 `decimal` behavior:** Python 3.3+ fixed Decimal context handling. No need for context thrashing or thread-local hacks.

## Open Questions

1. **Rounding strategy choice: ROUND_HALF_UP vs ROUND_HALF_EVEN**
   - What we know: Both are GAAP-compliant. ROUND_HALF_EVEN (banker's rounding) reduces bias in large datasets. ROUND_HALF_UP (commercial rounding) is more intuitive to business users.
   - What's unclear: Atom's transaction volume and user preferences. High-volume payment processors prefer ROUND_HALF_EVEN. Small business accounting prefers ROUND_HALF_UP.
   - Recommendation: **Use ROUND_HALF_UP** (commercial rounding) for business-familiar behavior unless processing >10k transactions/day. Document in API spec. Add test validating rounding choice.

2. **Database scale parameter for Numeric columns**
   - What we know: Scale=2 (cents) is standard for USD. Scale=4 supports tenth-of-a-cent (gas pricing, high-frequency trading).
   - What's unclear: Does Atom need sub-cent precision? Current code has no evidence of sub-cent requirements.
   - Recommendation: **Use scale=4** for future-proofing (supports tax calculations to 4 decimals). Storage difference is negligible. Precision=19 supports up to $10 trillion.

3. **Migration strategy for existing Float data**
   - What we know: Alembic can alter columns Float -> Numeric. Existing data will be converted. Float errors are "baked in" and can't be fixed retroactively.
   - What's unclear: How much historical transaction data exists? Is it acceptable to have imprecise historical data?
   - Recommendation: **Migrate schema to Numeric, flag historical data**. Add `data_precision_migrated = true` flag to workspaces. For critical reconciliation, allow re-importing source data (bank feeds) with Decimal precision.

## Sources

### Primary (HIGH confidence)

- **Python `decimal` module** - Official documentation for exact decimal arithmetic. HIGH confidence, authoritative source. Verifies string initialization, rounding modes, context management.
- **SQLAlchemy Numeric type** - Official docs for database DECIMAL/NUMERIC mapping. HIGH confidence. Verifies precision/scale parameters, PostgreSQL/SQLite behavior.
- **Hypothesis 6.92+ strategies** - Hypothesis documentation for `st.decimals()`, `st.floats()`. HIGH confidence. Verifies Decimal strategy generation, edge case handling.
- **Existing Atom codebase analysis** - 1,500+ lines of property tests, 283 lines of accounting models, 180+ lines of ledger code. HIGH confidence. Verified current float usage, epsilon tolerance bugs, test patterns.

### Secondary (MEDIUM confidence)

- **IEEE 754 floating-point standard** - Explains why 0.1 + 0.2 != 0.3 in binary. MEDIUM confidence, mathematical foundation.
- **GAAP/IFRS accounting standards** - Require exact monetary precision, no rounding errors in ledgers. MEDIUM confidence, accounting principles.
- **Existing test files** - `test_financial_invariants.py` (814 lines), `test_ai_accounting_invariants.py` (705 lines). MEDIUM confidence, verified implementation patterns.

### Tertiary (LOW confidence)

- **WebSearch on Python Decimal best practices** - Community patterns for Decimal usage in production. LOW confidence, needs verification against official docs.
- **Database migration patterns** - StackOverflow/GitHub issues on Float -> Numeric migration. LOW confidence, Atom-specific risks exist.

## Metadata

**Confidence breakdown:**
- Standard stack (Decimal, Hypothesis, SQLAlchemy): HIGH - Based on official documentation and existing verified implementations
- Architecture patterns (API boundaries, DB migration, validation): HIGH - Derived from existing Atom codebase analysis (1,500+ lines of tests, 283 lines of models)
- Pitfalls (precision errors, rounding, invariants): HIGH - Supported by IEEE 754 documentation, accounting standards, existing bugs in codebase
- Migration strategy (scale=4, historical data): MEDIUM - Requires user input on data volume, reconciliation needs

**Research date:** February 25, 2026
**Valid until:** 180 days (July 24, 2026) - Decimal module and SQLAlchemy Numeric are stable standards. Hypothesis strategies mature. Only risk is new Python version breaking changes (unlikely for stdlib).

**Gaps to validate during planning:**
1. **User rounding preference:** Confirm business users expect ROUND_HALF_UP vs ROUND_HALF_EVEN
2. **Historical data volume:** Assess impact of migrating existing Float data to Numeric
3. **Sub-cent precision needs:** Validate scale=4 vs scale=2 for Atom's use cases
4. **Performance impact:** Benchmark Decimal vs Float for high-volume transaction processing (if applicable)
