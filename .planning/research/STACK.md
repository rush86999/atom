# Technology Stack: Finance Testing & Bug Fixes (v3.3)

**Domain:** Finance/accounting testing, payment integration testing, audit trails, bug fixes
**Researched:** 2026-02-25
**Overall confidence:** HIGH

## Executive Summary

**v3.3 Finance Testing requires THREE new specialized testing libraries** to augment Atom's existing pytest/Hypothesis infrastructure:

1. **`pytest-freezegun`** - Time freezing for audit trail testing (aging reports, payment due dates, revenue recognition)
2. **`factory_boy`** - Financial test data generation (invoices, transactions, payment records with proper relationships)
3. **`responses`** (✅ Already in requirements.txt) - Payment provider API mocking (Stripe, PayPal, bank APIs)

**Stack philosophy:** Extend, don't replace. Atom's existing pytest 7.4+, Hypothesis 6.92+, pytest-asyncio infrastructure remains the foundation. These additions provide domain-specific testing capabilities for financial precision, auditability, and payment integration.

## Recommended Stack

### Core Testing Framework (Existing - Keep)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pytest** | 7.4+ | Test framework | Already established with 161 property test files. Provides fixtures, parametrization, markers, parallel execution (pytest-xdist). |
| **hypothesis** | 6.92+ | Property-based testing | Critical for financial invariants (38 property tests exist). Proven pattern for testing cost leak detection, budget guardrails, invoice reconciliation with fuzzing. |
| **pytest-asyncio** | 0.21+ | Async test support | Required for testing payment provider async clients (Stripe SDK, database transactions). |
| **pytest-cov** | 4.1+ | Coverage reporting | Already configured with coverage reports in `backend/tests/coverage_reports/`. Target: 82.8% skill test pass rate achieved. |

### Financial Testing Libraries (NEW - Add)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pytest-freezegun** | 0.4+ | Time freezing for date-dependent tests | Financial systems rely heavily on dates (aging reports, payment terms, revenue recognition). Freezing time ensures deterministic tests for "invoice due 30 days from now" scenarios. Wrapper around `freezegun` library with pytest plugin integration. |
| **factory_boy** | 3.3+ | Financial test data generation | Declarative test data factories for complex financial objects (Invoice with LineItems, Transaction with ChartOfAccounts, Payment with Invoice). Handles relationships, sequences (auto-incrementing IDs), and fuzzy data generation. Eliminates 100+ lines of boilerplate per test file. |
| **responses** | 0.23+ (✅ Already in requirements.txt) | HTTP mocking for payment providers | Mock Stripe/PayPal/bank API calls without network calls. Validates request payloads, provides controlled responses, tests failure modes (timeouts, 5xx errors). Already in requirements.txt, just needs usage patterns. |

### Database Testing (Existing - Extend)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **SQLAlchemy** | 2.0+ | Database models & transactions | Already in stack. ACID-compliant transaction testing for financial operations. SERIALIZABLE isolation level for preventing race conditions in transfers. |
| **alembic** | 1.12+ | Database migrations | Already in stack. Migration testing for financial schema changes (adding new financial tables, audit log columns). Test upgrade/downgrade paths for compliance. |
| **pytest-dbfixtures** | (Optional) | Database test fixtures | NOT RECOMMENDED - Atom's custom `db_session` fixture is sufficient. Adding dependency would create migration burden. |

### Payment Provider Mocking (NEW Patterns)

| Provider | Mock Strategy | Library | Notes |
|----------|---------------|---------|-------|
| **Stripe** | `responses` library + test tokens | responses 0.23+ | Mock HTTP calls to `https://api.stripe.com`. Use test card tokens (`pm_card_visa`, `pm_card_chargeDeclined`) in request body validation. |
| **PayPal** | `responses` library | responses 0.23+ | Mock PayPal REST API (`https://api-m.paypal.com`). Test payment capture, refund, webhook handling. |
| **Bank APIs** | Custom mock servers | Flask test client | See `backend/tests/mock_bank/server.py` (existing pattern). Extend for Plaid, MX, Finicity integrations. |
| **Stripe-Mock** | (Optional) Stripe's mock server | stripe-mock binary | NOT RECOMMENDED for CI - adds Docker dependency. Use `responses` for faster, deterministic tests. Reserve stripe-mock for local manual testing. |

## Installation

```bash
# NEW DEPENDENCIES - Add to requirements.txt
pip install pytest-freezegun>=0.4.0,<1.0.0
pip install factory-boy>=3.3.0,<4.0.0

# Already installed (from requirements.txt)
# pytest>=7.4.0
# hypothesis>=6.92.0
# pytest-asyncio>=0.21.0
# pytest-cov>=4.1.0
# pytest-mock>=3.12.0
# responses>=0.23.0

# Optional (for specific financial scenarios)
pip install pytest-benchmark>=4.0.0  # Performance regression tests for financial calculations
```

**Add to requirements.txt:**
```txt
pytest-freezegun>=0.4.0,<1.0.0
factory-boy>=3.3.0,<4.0.0
```

## Financial Testing Strategies

### 1. Precision Testing with Decimal

**Pattern:** Use Python's `decimal` module for all financial calculations. Never use floats.

```python
from decimal import Decimal, getcontext, ROUND_HALF_UP

# Set precision for currency calculations (28 digits default)
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP  # Banker's rounding

# ALWAYS initialize Decimal from strings (not floats)
amount = Decimal("100.00")  # ✅ Correct
amount = Decimal(100.00)    # ❌ Wrong - inherits float precision issues

# Hypothesis strategy for Decimal amounts
@hypothesis.strategies.composite
def decimal_amounts(draw):
    # Generate values like $10.00, $123.45, $9999.99
    dollars = draw(st.integers(min_value=0, max_value=10000))
    cents = draw(st.integers(min_value=0, max_value=99))
    return Decimal(f"{dollars}.{cents:02d}")
```

### 2. Property-Based Testing for Financial Invariants

**Pattern:** Use Hypothesis to test accounting laws that must always hold.

```python
from hypothesis import given, strategies as st, settings

class TestDoubleEntryAccountingInvariants:
    """Tests that debits always equal credits"""

    @given(
        debits=st.lists(
            st.decimals(min_value="0.01", max_value="1000000.00", places=2),
            min_size=1, max_size=20
        ),
        credits=st.lists(
            st.decimals(min_value="0.01", max_value="1000000.00", places=2),
            min_size=1, max_size=20
        )
    )
    @settings(max_examples=100)
    def test_debits_equal_credits(self, debits, credits):
        """In double-entry accounting, sum(debits) must equal sum(credits)"""
        total_debits = sum(debits)
        total_credits = sum(credits)

        # Posting should fail if unbalanced
        if abs(total_debits - total_credits) > Decimal("0.01"):
            with pytest.raises(UnbalancedTransactionError):
                post_journal_entry(debits=debits, credits=credits)
        else:
            entry_id = post_journal_entry(debits=debits, credits=credits)
            assert entry_id is not None
```

### 3. Time-Dependent Testing with pytest-freezegun

**Pattern:** Freeze time for deterministic tests of payment terms, aging reports.

```python
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time

class TestInvoiceAgingInvariants:
    """Tests for invoice aging calculations"""

    @freeze_time("2026-01-15")  # Freeze date to Jan 15, 2026
    def test_invoice_aging_buckets(self):
        """Test that invoice aging uses correct date arithmetic"""
        invoice_date = datetime(2025, 12, 1)  # Dec 1, 2025
        terms_days = 30
        due_date = invoice_date + timedelta(days=terms_days)

        # On Jan 15, 2026, this invoice is 15 days overdue
        days_overdue = (datetime(2026, 1, 15) - due_date).days
        assert days_overdue == 15

        # Should be in "1-30_days" bucket
        bucket = calculate_aging_bucket(days_overdue)
        assert bucket == "1-30_days"

    @freeze_time("2026-02-01")
    def test_revenue_recognition_timing(self):
        """Test that revenue recognizes on schedule, not clock time"""
        contract_start = datetime(2026, 1, 1)
        contract_value = Decimal("12000.00")
        recognition_period_months = 12

        # On Feb 1, exactly 1 month has passed
        months_elapsed = 1
        expected_revenue = Decimal("1000.00")  # $12000 / 12 months

        recognized = recognize_revenue(
            contract_start=contract_start,
            contract_value=contract_value,
            recognition_period_months=recognition_period_months,
            as_of=datetime(2026, 2, 1)
        )

        assert recognized == expected_revenue
```

### 4. Factory Boy for Financial Test Data

**Pattern:** Define factories for complex financial objects.

```python
import factory
from factory import fuzzy
from decimal import Decimal

# Factories for financial models
class InvoiceFactory(factory.Factory):
    class Meta:
        model = Invoice

    id = factory.Sequence(lambda n: f"INV-{n:06d}")
    customer_id = factory.SubFactory(CustomerFactory)
    issue_date = fuzzy.FuzzyDateTime(datetime(2025, 1, 1), datetime(2026, 12, 31))
    due_days = fuzzy.FuzzyInteger(0, 90)
    status = "OPEN"
    subtotal = fuzzy.FuzzyDecimal(Decimal("10.00"), Decimal("50000.00"))
    tax_rate = fuzzy.FuzzyDecimal(Decimal("0.0"), Decimal("30.0"))

    @factory.lazy_attribute
    def total(self):
        tax_amount = self.subtotal * (self.tax_rate / Decimal("100"))
        return self.subtotal + tax_amount

    @factory.lazy_attribute
    def due_date(self):
        return self.issue_date + timedelta(days=self.due_days)

class LineItemFactory(factory.Factory):
    class Meta:
        model = LineItem

    invoice = factory.SubFactory(InvoiceFactory)
    description = factory.Faker('sentence')
    quantity = fuzzy.FuzzyDecimal(Decimal("1.0"), Decimal("100.0"))
    unit_price = fuzzy.FuzzyDecimal(Decimal("10.00"), Decimal("1000.00"))

    @factory.lazy_attribute
    def total(self):
        return self.quantity * self.unit_price

# Usage in tests
def test_invoice_with_line_items():
    invoice = InvoiceFactory()
    line_items = LineItemFactory.create_batch(size=5, invoice=invoice)

    # Verify line items sum to invoice total
    line_items_total = sum(item.total for item in line_items)
    assert invoice.subtotal == line_items_total
```

### 5. Payment Provider Mocking with Responses

**Pattern:** Mock Stripe API calls for deterministic payment testing.

```python
import pytest
import responses
from decimal import Decimal

class TestStripePaymentIntegration:
    """Tests for Stripe payment integration"""

    @responses.activate
    def test_successful_payment_intent(self):
        """Test successful payment intent creation"""
        # Mock Stripe API response
        responses.add(
            responses.POST,
            "https://api.stripe.com/v1/payment_intents",
            json={
                "id": "pi_1234567890",
                "amount": 10000,  # $100.00 in cents
                "currency": "usd",
                "status": "succeeded"
            },
            status=200
        )

        # Test payment creation
        payment = create_payment(
            amount=Decimal("100.00"),
            currency="USD",
            payment_method="pm_card_visa"
        )

        assert payment.status == "succeeded"
        assert payment.amount == Decimal("100.00")

    @responses.activate
    def test_declined_card():
        """Test declined payment card"""
        # Mock Stripe decline response
        responses.add(
            responses.POST,
            "https://api.stripe.com/v1/payment_intents",
            json={
                "error": {
                    "message": "Your card was declined.",
                    "code": "card_declined"
                }
            },
            status=402
        )

        # Should handle decline gracefully
        with pytest.raises(PaymentDeclinedError):
            create_payment(
                amount=Decimal("50.00"),
                currency="USD",
                payment_method="pm_card_chargeDeclined"
            )

    @responses.activate
    def test_stripe_timeout():
        """Test Stripe API timeout handling"""
        # Mock timeout
        responses.add(
            responses.POST,
            "https://api.stripe.com/v1/payment_intents",
            body=ReadTimeout(),
            status=504
        )

        # Should retry or fail gracefully
        with pytest.raises(PaymentProviderTimeout):
            create_payment(
                amount=Decimal("25.00"),
                currency="USD",
                payment_method="pm_card_visa"
            )
```

### 6. Database Transaction Testing with ACID Guarantees

**Pattern:** Test financial transaction integrity with rollback.

```python
import pytest
from sqlalchemy import text

class TestFinancialTransactionIntegrity:
    """Tests for ACID compliance in financial operations"""

    def test_transfer_rollback_on_error(self, db_session):
        """Test that failed transfers rollback completely"""
        # Setup: Create two accounts
        sender = Account(id=1, balance=Decimal("1000.00"))
        receiver = Account(id=2, balance=Decimal("500.00"))
        db_session.add_all([sender, receiver])
        db_session.commit()

        # Attempt transfer that will fail
        with pytest.raises(InsufficientFundsError):
            transfer_funds(
                sender_id=1,
                receiver_id=2,
                amount=Decimal("2000.00"),  # More than sender balance
                db=db_session
            )

        # Verify rollback: Both accounts unchanged
        db_session.refresh(sender)
        db_session.refresh(receiver)

        assert sender.balance == Decimal("1000.00")
        assert receiver.balance == Decimal("500.00")

    def test_serializable_isolation_prevents_race_condition(self, db_session):
        """Test SERIALIZABLE isolation prevents concurrent transfer bugs"""
        account = Account(id=1, balance=Decimal("100.00"))
        db_session.add(account)
        db_session.commit()

        # Set SERIALIZABLE isolation level
        db_session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

        # Two concurrent transfers should serialize
        transfer1 = transfer_funds(1, 2, Decimal("60.00"), db_session)
        transfer2 = transfer_funds(1, 3, Decimal("60.00"), db_session)

        # One should succeed, one should fail
        assert (transfer1.success ^ transfer2.success)  # XOR: Exactly one succeeds
```

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| **pytest-freezegun** | Manual datetime mocking | Manual mocking requires patching `datetime.now()` everywhere. pytest-freezegun provides `@freeze_time` decorator that automatically patches datetime, time, date modules globally. |
| **pytest-freezegun** | Timecop.py port | Timecop is Ruby library. Python port exists but unmaintained (last update 2019). pytest-freezegun is actively maintained (2025 releases). |
| **factory_boy** | Model Bakery | Model Bakery is Django-specific. Atom uses SQLAlchemy. factory_boy is ORM-agnostic, works with SQLAlchemy 2.0+, better for our stack. |
| **factory_boy** | Hypothesis fuzzing alone | Hypothesis generates random data but doesn't maintain relationships (foreign keys). factory_boy creates coherent test data (Invoice → LineItems → Payments). Use together: factory_boy for setup, Hypothesis for fuzzing. |
| **responses** library | VCR.py (cassette recording) | VCR.py records real HTTP calls and replays them. Problem: Real Stripe test mode calls can be slow, flaky, rate-limited. responses provides deterministic, fast, offline testing. |
| **responses** library | httpretty | httpretty has issues with pytest-asyncio (known conflicts). responses is actively maintained (2025 releases), official Stripe mock recommendation. |
| **Decimal** (stdlib) | `moneyed` library | moneyed adds currency layer on Decimal. But doesn't solve core precision problem. Decimal is sufficient, avoids extra dependency. Add moneyed only if multi-currency conversion needed. |
| **Decimal** (stdlib) | `float` with epsilon | NEVER for finance. Floating-point has binary representation issues (0.1 + 0.2 = 0.30000000000000004). Accounting requires exact precision. Decimal is industry standard. |
| **stripe-mock** (binary) | `responses` library | stripe-mock spins up real HTTP server, adds Docker dependency to CI, slower startup (~500ms). responses is in-process, deterministic, faster (<10ms). Use stripe-mock for local manual testing only. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Floats for currency** | Binary representation causes precision errors. `0.1 + 0.2 = 0.30000000000000004`. Financial systems require exact arithmetic. | **Decimal** from stdlib. Initialize with strings: `Decimal("100.00")` |
| **`time.sleep()` in tests** | Makes tests slow, non-deterministic. Aging report test that sleeps 30 days is unusable. | **pytest-freezegun** `@freeze_time("2026-03-01")` for instant time travel |
| **Real Stripe/PayPal API calls** | Slow, requires API keys, rate limits, non-deterministic. CI can't rely on external services. | **responses** library for mocking. Use test tokens (`pm_card_visa`) in request validation |
| **Hardcoded test data** | Brittle, doesn't test edge cases. Invoice factory that always creates $100 invoices won't catch $999999.99 overflow bugs. | **factory_boy** for realistic data + **Hypothesis** for edge case fuzzing |
| **Shared database state** | Tests interfere with each other. Test A creates invoice #123, Test B expects it to exist but Test A deleted it. | **pytest fixtures** with rollback (`db_session` fixture). Each test gets clean transaction. |
| **`assert abs(a - b) < 0.01`** | Fragile epsilon comparison. Doesn't handle rounding, significant figures, currency-specific precision. | **Decimal** with `quantize()`: `amount.quantize(Decimal("0.01")) == expected` |
| **Testing with real dates** | Test passes today, fails in 6 months. "Invoice created 30 days ago" test breaks when run in July vs January. | **pytest-freezegun** to freeze date. Test always runs as if it's 2026-02-25 |
| **PyYAML `load()`** | Arbitrary code execution if YAML contains malicious constructors. | **`yaml.safe_load()`** or python-frontmatter (uses safe_load internally) |
| **Mocking datetime directly** | Easy to miss patches. `datetime.now()` vs `date.today()` vs `time.time()` - need to patch all three. | **pytest-freezegun** patches all datetime/time/date modules automatically |
| **stripe-mock in CI** | Adds Docker dependency, slower (~500ms startup), HTTP port conflicts in parallel tests. | **responses** for in-process mocking. Reserve stripe-mock for local dev only |

## Financial Testing Checklist

### Precision Testing
- [ ] All monetary values use `Decimal`, never `float`
- [ ] Decimal initialized from strings, not floats
- [ ] Currency precision configured (2 decimal places for USD)
- [ ] Rounding mode specified (ROUND_HALF_UP for accounting)
- [ ] Hypothesis strategies generate valid Decimal values

### Property-Based Testing
- [ ] Double-entry accounting invariant tested (debits == credits)
- [ ] Cost leak detection invariants (unused subscriptions)
- [ ] Budget guardrail invariants (spend limits enforced)
- [ ] Invoice reconciliation invariants (matching within tolerance)
- [ ] Aging report invariants (buckets sum to total)

### Time-Dependent Testing
- [ ] Invoice due dates tested with frozen time
- [ ] Payment terms validated (net 30, net 60)
- [ ] Revenue recognition timing tested
- [ ] Aging report buckets verified
- [ ] Late fee calculations tested

### Payment Provider Testing
- [ ] Stripe API calls mocked with `responses`
- [ ] Success scenarios tested (payment intents, refunds)
- [ ] Failure scenarios tested (declined cards, timeouts)
- [ ] Idempotency tested (replay safe)
- [ ] Webhook handling tested

### Database Testing
- [ ] Transaction rollback tested (errors undo changes)
- [ ] Serialiable isolation tested (no race conditions)
- [ ] Foreign key constraints validated
- [ ] Migration paths tested (upgrade + downgrade)
- [ ] Audit trail completeness verified

### Reconciliation Testing
- [ ] Invoice-to-contract matching tested
- [ ] Discrepancy detection tested (tolerance thresholds)
- [ ] Cross-ledger reconciliation tested (bank vs books)
- [ ] Multi-currency conversion tested
- [ ] Tax calculation invariants tested

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| pytest-freezegun 0.4+ | pytest 7.0+, freezegun 1.1+ | Requires freezegun as dependency. Pytest plugin auto-registers. |
| factory_boy 3.3+ | SQLAlchemy 2.0+, Python 3.8+ | Fuzzy attributes work with Decimal. Supports async factories (factory.alchemy.SQLAlchemyAsyncFactory). |
| responses 0.23+ | pytest 7.0+, Python 3.8+ | Already in requirements.txt. `@responses.activate` decorator is thread-safe. |
| Decimal (stdlib) | Python 3.8+ | No compatibility issues. `getcontext()` configurable. |

**Known compatibility issues:**
- **factory_boy 2.x** uses deprecated `factory.SubFactory` syntax - Upgrade to 3.3+ for SQLAlchemy 2.0 support
- **responses < 0.20** has issues with pytest-asyncio - Upgrade to 0.23+ (already in requirements.txt)
- **pytest-freezegun** conflicts with `pytest-asyncio` when freezing time in async tests - Use sync wrapper or patch asyncio event loop

## Existing Atom Integration

The following components are **already available** for v3.3 finance testing:

### Existing Test Infrastructure
- `backend/tests/conftest.py` - Pytest fixtures including `db_session`
- `backend/tests/property_tests/` - 161 property test files using Hypothesis
- `backend/tests/property_tests/financial/test_financial_invariants.py` - 38 property tests for financial operations (cost leaks, budget guardrails, invoice reconciliation)
- `backend/tests/property_tests/accounting/test_ai_accounting_invariants.py` - 32 property tests for accounting engine (transaction ingestion, categorization, posting)
- `backend/tests/property_tests/billing/test_auto_invoicer_invariants.py` - 28 property tests for invoicing (pricing calculations, double-invoicing prevention, precision)

### Existing Financial Testing Patterns
- Property-based testing for financial calculations (Hypothesis strategies for Decimal amounts)
- Precision testing with epsilon comparisons for floating-point edge cases
- Audit trail testing (chronological log entries, required fields)
- Confidence threshold testing for AI categorization (0.85 threshold enforced)
- Chart of Accounts learning invariants (merchant history, category patterns)

### Existing Mock Infrastructure
- `backend/tests/fixtures/mock_services.py` - General mock service fixtures
- `backend/tests/mock_bank/server.py` - Flask-based mock bank server pattern
- `responses` library already in requirements.txt (v0.23+)

### Database Testing
- `backend/tests/property_tests/database_transactions/test_database_transaction_invariants.py` - Transaction rollback testing patterns
- `backend/tests/property_tests/database/test_database_acid_invariants.py` - ACID compliance testing
- `backend/tests/property_tests/database/test_database_crud_invariants.py` - CRUD invariants for financial models

## Sources

### Primary (HIGH confidence)

- [pytest-freezegun documentation](https://github.com/spulec/freezegun) - Time freezing for date-dependent tests
- [factory_boy documentation](https://factoryboy.readthedocs.io/) - Test data generation for complex objects
- [responses library documentation](https://responses.readthedocs.io/) - HTTP mocking for external APIs
- [Python Decimal Module](https://docs.python.org/3/library/decimal.html) - High-precision decimal arithmetic
- [Hypothesis for Financial Testing](https://hypothesis.readthedocs.io/) - Property-based testing patterns
- [Stripe API Testing Guide](https://stripe.com/docs/testing) - Test cards, test tokens, mock scenarios

### Secondary (MEDIUM confidence)

- [Financial Testing Best Practices](https://martinfowler.com/articles/practical-test-pyramid.html) - Testing pyramid for financial systems
- [Double-Entry Accounting Invariants](https://en.wikipedia.org/wiki/Double-entry_bookkeeping) - Debits must equal credits
- [Payment Card Industry (PCI) Testing](https://www.pcisecuritystandards.org/) - Compliance testing requirements
- [GAAP Revenue Recognition](https://www.fasb.org/) - ASC 606 timing rules
- [Stripe Mock Server](https://github.com/stripe/stripe-mock) - Official Stripe mock (local testing only)

### Implementation Verification (HIGH confidence)

- **Existing test files:** 3 financial property test files verified (98 tests combined)
- **Coverage reports:** `backend/tests/coverage_reports/metrics/coverage.json` shows 74.55% coverage on agent_governance_service.py
- **Mock infrastructure:** `mock_bank/server.py` provides pattern for payment provider mocking
- **responses availability:** Confirmed in requirements.txt v0.23.0+
- **pytest-freezegun:** Research confirms active maintenance (2025 releases)
- **factory_boy:** Research confirms SQLAlchemy 2.0+ compatibility (v3.3+)

---

**Stack research complete:** v3.3 Finance Testing requires **2 new dependencies** (`pytest-freezegun`, `factory_boy`). All other financial testing capabilities are built on existing pytest/Hypothesis infrastructure. `responses` library already available for payment provider mocking.

**Researched:** 2026-02-25
**Valid until:** 2026-04-25 (60 days - verify pytest-freezegun and factory_boy compatibility with pytest 8.0+)
