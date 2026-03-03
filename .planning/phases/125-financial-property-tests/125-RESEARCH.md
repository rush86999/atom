# Phase 125: Financial Property Tests - Research

**Researched:** 2026-03-02
**Domain:** Python Property-Based Testing (Hypothesis), Financial Invariants, Decimal Precision
**Confidence:** HIGH

## Summary

Phase 125 requires validating financial system invariants using Hypothesis property-based testing with `max_examples=200` for critical invariants. The codebase already has extensive financial property tests in `backend/tests/property_tests/financial/` and `backend/tests/property_tests/finance/` directories, totaling 41+ tests covering decimal precision, double-entry accounting, and audit immutability.

The existing tests use Hypothesis 6.92+ with custom Decimal strategies from `tests/fixtures/decimal_fixtures.py`. Key patterns include:
- **Decimal precision tests**: 26 tests validating ROUND_HALF_EVEN (banker's rounding), precision preservation, arithmetic operations
- **Double-entry tests**: 14 tests validating debits=credits, accounting equation, transaction integrity
- **Audit immutability tests**: 9 tests validating hash chain integrity, tampering detection, prev_hash linking

**Primary recommendation:** Phase 125 should focus on verifying existing financial property tests use `max_examples=200` for all critical invariants, filling gaps in audit immutability coverage, and documenting the VALIDATED_BUG patterns found in existing tests.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **hypothesis** | 6.92.0+ | Property-based testing framework | De facto standard for Python PBT, superior to QuickCheck libraries |
| **pytest** | 7.4+ | Test runner | Required for Hypothesis integration |
| **Decimal** | Built-in | Exact decimal arithmetic | Python stdlib, no floating-point errors |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-cov** | 4.1+ | Coverage reporting | Verification of test coverage |
| **pytest-asyncio** | 0.21+ | Async test support | Required for database transaction tests |
| **pytest-rerunfailures** | 12.0+ | Flaky test detection | Auto-retry failed tests up to 2 times |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hypothesis | quickcheck (Python) | hypothesis has better Python integration, active development |
| Decimal | fractions | Fractions don't match currency semantics (2 decimal places) |
| pytest | unittest | pytest is superior for fixtures and parametrization |

**Installation:**
```bash
pip install hypothesis>=6.92.0,<7.0.0 pytest pytest-cov pytest-asyncio pytest-rerunfailures
```

## Architecture Patterns

### Recommended Project Structure

Existing test structure is well-organized:

```
backend/tests/
├── property_tests/
│   ├── financial/                    # Financial invariants (Decimal, double-entry)
│   │   ├── test_decimal_precision_invariants.py      # 26 tests, max_examples=100-200
│   │   ├── test_double_entry_invariants.py           # 14 tests, max_examples=200
│   │   └── test_financial_invariants.py              # 41 tests, business logic
│   ├── finance/                      # Audit & accounting tests
│   │   ├── test_audit_immutability_invariants.py     # 9 tests, max_examples=50-100
│   │   ├── test_audit_completeness_invariants.py     # Audit completeness
│   │   └── test_chronological_integrity_invariants.py # Time ordering
│   └── fixtures/
│       └── decimal_fixtures.py       # Reusable Hypothesis strategies
└── integration/finance/               # End-to-end financial workflows
```

### Pattern 1: Decimal Precision Testing with max_examples=200

**What:** Test decimal arithmetic properties with 200 Hypothesis examples per test

**When to use:** All precision-critical financial calculations (currency, tax, percentages)

**Example:**
```python
# Source: backend/tests/property_tests/financial/test_decimal_precision_invariants.py

from hypothesis import given, settings, example
from decimal import Decimal, ROUND_HALF_EVEN
from tests.fixtures.decimal_fixtures import high_precision_strategy

class TestCurrencyRoundingInvariants:
    @given(amount=high_precision_strategy())
    @settings(max_examples=200)
    @example(amount=Decimal('1.005'))  # Should round to 1.00 (even)
    @example(amount=Decimal('1.015'))  # Should round to 1.02 (even)
    def test_round_half_even_for_money(self, amount):
        """
        PROPERTY: Currency values use ROUND_HALF_EVEN (banker's rounding)

        STRATEGY: high_precision_strategy() - 4 decimal places

        INVARIANT: For any money value m: rounding uses banker's rounding
        1.005 rounds to 1.00 (not 1.01) - rounds toward even digit
        1.015 rounds to 1.02 - rounds toward even digit (2)

        FINANCIAL_CRITICAL: ROUND_HALF_EVEN prevents statistical bias that would
        accumulate in large financial datasets. Required by GAAP/IFRS standards.

        RADII: 200 examples explores full rounding edge case space

        VALIDATED_BUG: Money amount 10.005 became 10.01 (should be 10.00)
        Root cause: ROUND_HALF_UP instead of ROUND_HALF_EVEN
        Fixed in commit fin001 by switching to banker's rounding
        """
        rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

        # Should have exactly 2 decimal places
        assert rounded.as_tuple().exponent == -2, \
            f"Rounded value should have 2 decimal places, got {rounded.as_tuple().exponent}"

        # Verify specific banker's rounding behavior for .005 edge cases
        amount_str = f"{amount:.4f}"
        if amount_str[-3:] == '005':
            # Check if digit before 5 is even or odd
            hundredth_digit = int(amount_str[-4])
            actual_hundredth = int(f"{rounded:.2f}"[-1])
            assert actual_hundredth % 2 == 0, \
                f"Should round to even: {amount} -> {rounded}"
```

**Key insight:** `max_examples=200` is CRITICAL for financial invariants per PROP-03 requirement. Lower values (50-100) miss edge cases in rounding behavior.

### Pattern 2: Double-Entry Validation with max_examples=200

**What:** Test accounting equation invariants with 200 examples

**When to use:** All double-entry bookkeeping validation (debits=credits, Assets=Liabilities+Equity)

**Example:**
```python
# Source: backend/tests/property_tests/financial/test_double_entry_invariants.py

from hypothesis import given, settings, example
from tests.fixtures.decimal_fixtures import money_strategy

class TestDoubleEntryValidationInvariants:
    @given(
        amount=money_strategy('0.01', '1000000.00'),
        account_count=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=200)
    @example(amount=Decimal('100.00'), account_count=2)
    @example(amount=Decimal('999999.99'), account_count=5)
    def test_debits_equal_credits(self, amount, account_count):
        """
        PROPERTY: Double-entry accounting requires debits = credits (zero net balance)

        STRATEGY: st.lists of journal_entry_lines with accounts and amounts

        INVARIANT: sum(all_debits) - sum(all_credits) = 0

        ACCOUNTING_FUNDAMENTAL: This is the foundational invariant of double-entry
        bookkeeping. Violation indicates corrupted accounting data or calculation bug.

        RADII: 200 examples explores various transaction configurations

        VALIDATED_BUG: Transaction posted with unbalanced debits/credits
        Root cause: Missing validation in transaction posting logic
        Fixed in commit fin002 by adding pre-post validation
        """
        # Create balanced transaction: split amount evenly across accounts
        entries = []
        per_account = (amount / account_count).quantize(Decimal('0.01'))

        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')

        for i in range(account_count):
            entry_type = EntryType.DEBIT if i % 2 == 0 else EntryType.CREDIT
            entries.append({
                "account_id": f"acc_{i}",
                "type": entry_type,
                "amount": per_account
            })

            if entry_type == EntryType.DEBIT:
                total_debits += per_account
            else:
                total_credits += per_account

        result = validate_double_entry(entries)

        # For truly balanced transactions
        if total_debits == total_credits:
            assert result['balanced'] is True
            assert result['debits'] == total_debits
            assert result['credits'] == total_credits
            assert result['difference'] == Decimal('0.00')
```

**Key insight:** Double-entry tests validate accounting fundamentals with NO epsilon tolerance. Exact Decimal comparison required.

### Pattern 3: Audit Immutability with Hash Chain Verification

**What:** Test audit trail immutability using hash chains

**When to use:** All audit trail validation (FinancialAudit entries cannot be modified/deleted)

**Example:**
```python
# Source: backend/tests/property_tests/finance/test_audit_immutability_invariants.py

from hypothesis import given, settings
from core.models import FinancialAudit
from core.hash_chain_integrity import HashChainIntegrity

@pytest.mark.usefixtures("db_session")
class TestAuditImmutabilityInvariants:

    @given(
        initial_balance=st.decimals(min_value='0', max_value='1000.00', places=2),
        new_balance=st.decimals(min_value='0', max_value='10000.00', places=2)
    )
    @settings(max_examples=50)  # NOTE: Currently 50, should be 200 per PROP-03
    def test_audits_cannot_be_modified(self, initial_balance, new_balance):
        """
        Verify: FinancialAudit entries cannot be modified.

        Invariant: UPDATE on FinancialAudit raises exception

        Property: For any initial_balance and new_balance,
        attempting to modify an audit entry raises an exception.
        """
        # Create audit entry
        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            account_id=str(uuid.uuid4()),
            action_type='create',
            changes={'balance': {'old': None, 'new': float(initial_balance)}},
            old_values=None,
            new_values={'balance': float(initial_balance)},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=1,
            entry_hash=hashlib.sha256(b"initial_hash").hexdigest(),
            prev_hash=''
        )
        self.db.add(audit)
        self.db.commit()

        # Try to modify the audit entry
        audit.success = False
        audit.error_message = "Attempting modification"

        # Should raise exception (database trigger or application guard)
        with pytest.raises((AssertionError, IntegrityError, OperationalError, ProgrammingError)):
            self.db.commit()

        # Rollback to clean up
        self.db.rollback()
```

**Key insight:** Audit immutability tests currently use `max_examples=50`, but should be upgraded to `max_examples=200` per PROP-03 requirement for critical invariants.

### Anti-Patterns to Avoid

- **max_examples=100 for critical invariants**: Financial, security, and data loss invariants require 200 examples
- **Using float for money**: Never use float - always use Decimal with string initialization
- **Epsilon tolerance in accounting**: Double-entry requires exact equality, not `abs(a-b) < 0.01`
- **Wrong rounding mode**: Always use `ROUND_HALF_EVEN` (banker's rounding) per GAAP/IFRS
- **Testing with less examples**: 50 examples insufficient for critical financial invariants

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Decimal strategies | Manual `st.just(Decimal('1.23'))` | `tests/fixtures/decimal_fixtures.py` | Reusable strategies cover edge cases (boundaries, rounding) |
| Rounding logic | Custom rounding functions | `Decimal.quantize(Decimal('0.01'), ROUND_HALF_EVEN)` | Built-in is GAAP-compliant, tested |
| Double-entry validation | Manual debit/credit summation | `core.accounting_validator.validate_double_entry()` | Centralized validation, error handling |
| Hash chain verification | Manual hash comparison | `core.hash_chain_integrity.HashChainIntegrity` | Detects tampering across entire chain |
| Audit guards | Manual checks in tests | `core.audit_immutable_guard.prevent_audit_modification()` | Database triggers + application guards |

**Key insight:** Phase 94 already implemented audit immutability infrastructure. Tests should verify existing guards work correctly, not rebuild them.

## Common Pitfalls

### Pitfall 1: Using Float for Financial Calculations

**What goes wrong:** `0.1 + 0.2 == 0.3` returns `False` in floating-point arithmetic. Money amounts drift over time.

**Why it happens:** Binary floating-point cannot represent 0.1 exactly. Accumulation causes drift.

**How to avoid:** Always use `Decimal(str(amount))` for money values:
```python
# WRONG
amount = 100.01  # float
total = amount + 0.01  # 100.019999999999996

# CORRECT
from decimal import Decimal
amount = Decimal('100.01')  # Exact
total = amount + Decimal('0.01')  # Decimal('100.02')
```

**Warning signs:** `0.009999999999999995` in test output, balance off by $0.01 after many transactions.

### Pitfall 2: Insufficient max_examples for Critical Invariants

**What goes wrong:** Tests pass with `max_examples=50` but fail at example 173 when increased to 200.

**Why it happens:** Financial edge cases are rare but catastrophic (e.g., rounding at .005 boundary).

**How to avoid:** Always use `max_examples=200` for critical invariants:
```python
# WRONG - misses edge cases
@settings(max_examples=50)
def test_round_half_even_for_money(self, amount):
    pass

# CORRECT - explores full edge case space
@settings(max_examples=200)
def test_round_half_even_for_money(self, amount):
    pass
```

**Warning signs:** Test passes sometimes, fails randomly. Hypothesis "fuzzing" finds counterexamples.

### Pitfall 3: Using Wrong Rounding Mode

**What goes wrong:** `ROUND_HALF_UP` causes systematic bias in large datasets.

**Why it happens:** Python's `round()` uses banker's rounding, but `Decimal.quantize()` defaults to `ROUND_HALF_EVEN` only if specified.

**How to avoid:** Always specify `rounding=ROUND_HALF_EVEN`:
```python
# WRONG - systematic bias
rounded = amount.quantize(Decimal('0.01'))  # Uses ROUND_HALF_EVEN by default, but not explicit

# WRONG - systematic bias (rounds 1.005 to 1.01, not 1.00)
rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# CORRECT - banker's rounding (GAAP/IFRS compliant)
from decimal import ROUND_HALF_EVEN
rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
```

**Warning signs:** Financial reports off by pennies after thousands of transactions. Compliance audit fails.

### Pitfall 4: Testing Audit Immutability with Low max_examples

**What goes wrong:** Audit tampering test uses `max_examples=50`, misses rare hash collision scenarios.

**Why it happens:** Developers treat audit tests as "integration tests" with lower example counts.

**How to avoid:** Audit immutability is CRITICAL - use `max_examples=200`:
```python
# CURRENT - insufficient coverage
@settings(max_examples=50)
def test_audits_cannot_be_modified(self, initial_balance, new_balance):
    pass

# REQUIRED - critical invariant
@settings(max_examples=200)
def test_audits_cannot_be_modified(self, initial_balance, new_balance):
    pass
```

**Warning signs:** Tampering detection works for simple cases but fails for complex multi-account scenarios.

### Pitfall 5: Missing VALIDATED_BUG Documentation

**What goes wrong:** Property tests find bugs, but no documentation of what was validated.

**Why it happens:** Developers focus on fixing bugs, not documenting the evidence.

**How to avoid:** Always include VALIDATED_BUG section in docstring:
```python
def test_round_half_even_for_money(self, amount):
    """
    VALIDATED_BUG: Money amount 10.005 became 10.01 (should be 10.00)
    Root cause: ROUND_HALF_UP instead of ROUND_HALF_EVEN
    Fixed in commit fin001 by switching to banker's rounding
    """
```

**Warning signs:** Code reviews ask "what bug does this test prevent?" No historical record of issues found.

## Code Examples

Verified patterns from existing codebase:

### Hypothesis Strategy for Decimal Money

```python
# Source: backend/tests/fixtures/decimal_fixtures.py

from decimal import Decimal
from hypothesis import strategies as st
from typing import Union

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
    return st.decimals(
        min_value=str(min_value),
        max_value=str(max_value),
        places=2,
        allow_nan=False,
        allow_infinity=False
    )
```

### Hypothesis Strategy for High-Precision Decimal

```python
# Source: backend/tests/fixtures/decimal_fixtures.py

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
    return st.decimals(
        min_value=str(min_value),
        max_value=str(max_value),
        places=4,
        allow_nan=False,
        allow_infinity=False
    )
```

### Example-Aware Testing with Hypothesis

```python
# Source: backend/tests/property_tests/financial/test_decimal_precision_invariants.py

from hypothesis import given, settings, example

@given(amount=high_precision_strategy())
@settings(max_examples=200)
@example(amount=Decimal('1.005'))  # Should round to 1.00 (even)
@example(amount=Decimal('1.015'))  # Should round to 1.02 (even)
@example(amount=Decimal('2.005'))  # Should round to 2.00 (even)
@example(amount=Decimal('2.015'))  # Should round to 2.02 (even)
def test_round_half_even_for_money(self, amount):
    """
    Test banker's rounding edge cases with explicit examples.
    """
    rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
    assert rounded.as_tuple().exponent == -2
```

**Key insight:** Use `@example` decorator to ensure specific edge cases are always tested, even if Hypothesis doesn't generate them.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest.TestCase classes | pytest + Hypothesis property tests | 2018+ | Property tests find bugs unit tests miss |
| float for money | Decimal with ROUND_HALF_EVEN | Always | Decimal is required for financial correctness |
| max_examples=100 | max_examples=200 for critical invariants | Phase 103 (2024) | Increased coverage catches rare edge cases |
| Manual rounding strategies | hypothesis.strategies.decimals | Phase 103 (2024) | Built-in strategies are well-tested |

**Deprecated/outdated:**
- **float for money**: Never acceptable, causes rounding errors
- **max_examples=50 for critical invariants**: Insufficient for financial/system-level invariants
- **ROUND_HALF_UP**: Systematic bias, use ROUND_HALF_EVEN instead

## Open Questions

1. **Should all audit immutability tests use max_examples=200?**
   - What we know: PROP-03 requires "max_examples=200 (critical invariant)"
   - What's unclear: Whether audit immutability is considered "critical" vs "standard"
   - Recommendation: Audit immutability is CRITICAL (prevents fraud), upgrade to max_examples=200

2. **Are there gaps in decimal precision coverage?**
   - What we know: 26 tests cover arithmetic, rounding, accumulation
   - What's unclear: Whether currency conversion, multi-currency scenarios covered
   - Recommendation: Review `test_financial_invariants.py` for multi-currency coverage

3. **Should we add property tests for hash chain performance?**
   - What we know: HashChainIntegrity verifies correctness, not performance
   - What's unclear: Whether large chains (10,000+ entries) cause performance issues
   - Recommendation: Add performance test with `max_examples=50` (not critical, IO-bound)

4. **Should double-entry tests verify accounting equation (Assets = Liabilities + Equity)?**
   - What we know: Current tests verify debits=credits, not full equation
   - What's unclear: Whether this is covered elsewhere in the codebase
   - Recommendation: Add `test_accounting_equation_balanced` with `max_examples=200`

## Sources

### Primary (HIGH confidence)
- **backend/tests/property_tests/financial/test_decimal_precision_invariants.py** (690 lines) - 26 tests with max_examples=100-200, VALIDATED_BUG docstrings
- **backend/tests/property_tests/financial/test_double_entry_invariants.py** (678 lines) - 14 tests with max_examples=200, ACCOUNTING_FUNDAMENTAL markers
- **backend/tests/property_tests/finance/test_audit_immutability_invariants.py** (389 lines) - 9 tests with max_examples=50-100
- **backend/tests/fixtures/decimal_fixtures.py** (142 lines) - Reusable Hypothesis strategies for Decimal testing
- **backend/core/accounting_validator.py** - Double-entry validation logic
- **backend/core/hash_chain_integrity.py** - Hash chain verification for audit trails
- **backend/core/models.py** - FinancialAudit model with hash chain fields
- **backend/requirements.txt** - hypothesis>=6.92.0,<7.0.0

### Secondary (MEDIUM confidence)
- **Phase 111 Research Document** - `.planning/phases/111-phase-101-fixes/111-RESEARCH.md` - pytest patterns, mock configuration
- **Phase 103 Completion Report** - `.planning/phases/103-backend-property-based-tests/103-PHASE-SUMMARY.md` - "41 financial tests, 100% pass rate"
- **Hypothesis Documentation** - https://hypothesis.readthedocs.io/ - @given, @settings, @example decorators

### Tertiary (LOW confidence)
- **.planning/ROADMAP.md** - Phase 125 context, PROP-03 requirement
- **.planning/REQUIREMENTS.md** - PROP-03: "Financial invariants tested — Decimal precision, double-entry validation, audit immutability validated"

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Hypothesis 6.92+, pytest, Decimal are industry standards, verified in requirements.txt
- Architecture: HIGH - Patterns extracted from working test files (690+ lines) with proven pass rates
- Pitfalls: HIGH - All pitfalls documented in existing test docstrings with VALIDATED_BUG examples
- Open questions: MEDIUM - Require clarification on audit immutability criticality, multi-currency coverage

**Research date:** 2026-03-02
**Valid until:** 2026-06-01 (3 months - Hypothesis, pytest, and Decimal patterns are stable)

**Key insight for planning:** Phase 125 is primarily a **verification and gap-filling effort**, not greenfield implementation. The tests already exist and pass (100% per Phase 103). Focus on:
1. Upgrading `max_examples=50` to `max_examples=200` for all critical invariants
2. Adding missing audit immutability scenarios (tampering detection across multiple accounts)
3. Verifying all 3 success criteria: Decimal precision, double-entry, audit immutability
4. Documenting VALIDATED_BUG patterns with commit references
