# Error Path Testing Documentation

**Phase:** 104-backend-error-path-testing
**Date:** 2026-02-28
**Purpose:** Comprehensive guide for error path testing patterns and best practices

---

## Table of Contents

1. [Overview](#overview)
2. [VALIDATED_BUG Docstring Pattern](#validated_bug-docstring-pattern)
3. [Error Path Categories](#error-path-categories)
4. [Test Structure Patterns](#test-structure-patterns)
5. [Common Error Scenarios](#common-error-scenarios)
6. [Severity Classification](#severity-classification)
7. [Reusability for Frontend Phases](#reusability-for-frontend-phases)
8. [Complete Test Examples](#complete-test-examples)
9. [Best Practices](#best-practices)
10. [Tools and Frameworks](#tools-and-frameworks)

---

## Overview

### Purpose of Error Path Testing

Error path testing focuses on validating how a system handles **invalid inputs, exceptional conditions, and edge cases**. Unlike unit tests (which verify happy paths) and property tests (which verify invariants), error path tests specifically target:

- **Crash prevention** - Ensure invalid inputs don't cause unhandled exceptions
- **Graceful degradation** - Verify error messages are helpful and actionable
- **Security validation** - Prevent malicious inputs from exploiting vulnerabilities
- **Data integrity** - Ensure error states don't corrupt data or create inconsistencies

### When to Use Error Path Testing

**Use error path testing when:**
- A function accepts user input (API endpoints, CLI commands, form fields)
- A function performs critical operations (payments, authentication, database writes)
- A function has complex validation logic (business rules, constraints, sanitization)
- A function interfaces with external systems (APIs, databases, file systems)
- Previous bugs indicate missing input validation

**Don't use error path testing for:**
- Trivial getters/setters (overkill for simple accessors)
- Private helper methods (test via public interface)
- Performance optimization (use profiling tools instead)
- Happy path validation (use standard unit tests instead)

### Difference from Other Test Types

| Test Type | Purpose | Example | Tools |
|-----------|---------|---------|-------|
| **Unit Tests** | Verify correct behavior with valid inputs | `login(user, pass)` returns token | pytest, unittest |
| **Property Tests** | Verify invariants hold for all inputs | `sort(sort(x)) == sort(x)` for all lists | Hypothesis, pytest |
| **Error Path Tests** | Verify graceful handling of invalid inputs | `login(None, None)` returns error, not crash | pytest, pytest.raises |
| **Integration Tests** | Verify multi-component workflows | Login → Create agent → Execute skill | pytest, fixtures |

---

## VALIDATED_BUG Docstring Pattern

The `VALIDATED_BUG` docstring pattern is the standard way to document bugs discovered during error path testing. This pattern ensures **reproducibility, severity assessment, and clear fix recommendations**.

### Template

```python
def test_example_error_case(self):
    """
    VALIDATED_BUG: Brief description of the bug

    Expected:
        - What should happen when the error condition occurs
        - Expected return value, exception type, or behavior

    Actual:
        - What actually happens (the bug)
        - Actual error type, return value, or crash behavior

    Severity: [CRITICAL, HIGH, MEDIUM, LOW]
    Impact:
        - Production impact (crashes, data loss, security issues)
        - User impact (confusion, incorrect results)
        - Business impact (lost revenue, compliance issues)

    Fix:
        - Recommended code change with line numbers
        - Example fix code snippet
        - Verification steps after fix

    Validated: ✅ Test confirms bug exists
    """
    # Test implementation here
```

### Example: Real Bug from Phase 104

```python
def test_verify_password_with_none_password(self):
    """
    VALIDATED_BUG: verify_password() crashes with None password

    Expected:
        - verify_password() should return False for None password
        - Graceful degradation without crash

    Actual:
        - TypeError: 'NoneType' object is not subscriptable
        - Crash at line 48: plain_password[:71]

    Severity: HIGH
    Impact:
        - Login endpoint crashes if None password passed
        - Potential DoS vector if attacker sends None passwords
        - Inconsistent with expected graceful degradation

    Fix:
        Add None check at start of verify_password():
        ```python
        def verify_password(plain_password: str, hashed_password: str) -> bool:
            if plain_password is None or hashed_password is None:
                return False
            # ... rest of function
        ```

    Validated: ✅ Test confirms bug exists
    """
    valid_hash = get_password_hash("test_password")
    with pytest.raises(TypeError):
        result = verify_password(None, valid_hash)
```

### Field Descriptions

#### Expected vs Actual

- **Expected**: What the code SHOULD do (correct behavior)
- **Actual**: What the code ACTUALLY does (bug behavior)
- **Contrast**: The difference between expected and actual is the bug

#### Severity Levels

| Severity | Definition | Examples |
|----------|------------|----------|
| **CRITICAL** | Production crashes, data loss, security vulnerabilities | Zero-day exploits, database corruption, authentication bypass |
| **HIGH** | Graceful degradation failures, incorrect results | Crashes on invalid input, TOCTOU race conditions, negative values accepted |
| **MEDIUM** | Error messages not helpful, validation missing | Empty strings accepted, None inputs cause crashes, inconsistent error handling |
| **LOW** | Cosmetic issues, logging improvements | Confusing debug logs, non-standard error codes, verbose error messages |

#### Impact Section

The **Impact** field answers: "Why does this bug matter?"

- **Production impact**: Will this crash production? Cause data loss? Create security issues?
- **User impact**: Will users see errors? Experience incorrect results? Be confused?
- **Business impact**: Will this cause lost revenue? Compliance violations? Reputational damage?

#### Fix Section

The **Fix** field provides:

1. **Location**: Exact file and line number where fix should be applied
2. **Code change**: Minimal code snippet showing the fix
3. **Verification**: How to test that the fix works

---

## Error Path Categories

Error paths fall into 4 main categories based on the type of error being tested.

### 1. Authentication Failures

**Tests:** Invalid credentials, token issues, session management

**Common Error Scenarios:**
- None/empty username or password
- Invalid token signatures
- Expired tokens
- Malformed tokens
- Missing token headers
- Concurrent login attempts

**Example Bugs:**
- Bug #10: `verify_password()` crashes with None password
- Bug #12: `verify_mobile_token()` crashes with None token
- Bug #13: `get_current_user_ws()` crashes with None token

**File:** `backend/tests/error_paths/test_auth_error_paths.py`

---

### 2. Security Violations

**Tests:** Rate limiting, authorization bypass, input sanitization

**Common Error Scenarios:**
- Negative or zero rate limits
- Excessive requests (DoS attempts)
- SQL injection attempts
- XSS attempts
- Path traversal attempts
- CSRF token validation
- Header manipulation

**Example Bugs:**
- Bug #10-12: `RateLimitMiddleware` accepts negative/zero limits, crashes on None client
- Bug #13: Race condition in concurrent requests allows rate limit bypass

**File:** `backend/tests/error_paths/test_security_error_paths.py`

---

### 3. Financial Errors

**Tests:** Payment failures, calculation errors, budget violations

**Common Error Scenarios:**
- Negative payment amounts
- Negative budget limits
- Zero budget limits
- Float to Decimal precision loss
- Division by zero
- Concurrent spend checks (TOCTOU races)
- Negative invoice tolerance

**Example Bugs:**
- Bug #15: Negative payment amounts accepted
- Bug #16: Negative monthly limit accepted
- Bug #17: Zero monthly limit causes incorrect behavior
- Bug #20: TOCTOU race in concurrent budget spend checks

**File:** `backend/tests/error_paths/test_finance_error_paths.py`

---

### 4. Edge Cases

**Tests:** Empty inputs, null values, boundary violations, type errors

**Common Error Scenarios:**
- None inputs
- Empty strings/lists/dicts
- Unicode/special characters
- Numeric edge cases (zero, negative, infinity, NaN)
- Datetime edge cases (leap years, DST transitions)
- Concurrent access patterns

**Example Bugs:**
- Bug #15: `GovernanceCache` crashes on None action_type
- Bug #16: Leap year date addition fails
- Bug #17: Empty string agent_id accepted

**File:** `backend/tests/error_paths/test_edge_case_error_paths.py`

---

## Test Structure Patterns

### Test Class Organization

**Organize tests by service or error type:**

```python
class TestAuthFailures:
    """Tests for authentication error scenarios"""

class TestTokenValidation:
    """Tests for token validation error scenarios"""

class TestPasswordHashingEdgeCases:
    """Tests for password hashing edge cases"""
```

**Recommended structure:**
- **By service** (preferred for large test suites): `TestAuthServiceErrors`, `TestFinanceServiceErrors`
- **By error type** (preferred for cross-service testing): `TestNoneInputs`, `TestEmptyInputs`, `TestBoundaryViolations`

### Test Method Naming

**Use descriptive names that explain the error scenario:**

```python
# Good: Descriptive
def test_verify_password_with_none_password(self):
    """Test that verify_password() handles None password gracefully"""
    pass

def test_budget_limit_with_negative_monthly_limit(self):
    """Test that negative budget limits are rejected"""
    pass

# Bad: Vague
def test_auth_error(self):
    """Test auth error handling"""  # Which error?
    pass

def test_budget_limit(self):
    """Test budget limit"""  # What aspect?
    pass
```

**Naming pattern:** `test_{function_name}_with_{error_condition}`

### Fixture Usage

**Use pytest fixtures for common test setup:**

```python
import pytest
from unittest.mock import Mock, MagicMock
from core.auth import verify_password, get_password_hash

@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)

@pytest.fixture
def valid_password_hash():
    """Valid bcrypt hash for 'test_password'"""
    return get_password_hash("test_password")

class TestAuthFailures:
    def test_verify_password_with_none_password(self, valid_password_hash):
        """Test that verify_password() handles None password gracefully"""
        with pytest.raises(TypeError):
            verify_password(None, valid_password_hash)
```

**Common fixtures:**
- `mock_db`: Mock database session
- `mock_request`: Mock HTTP request object
- `mock_app`: Mock FastAPI app
- `valid_*`: Valid test data (passwords, tokens, hashes)

---

## Common Error Scenarios

### 1. None/Null Inputs

**Test pattern:** Verify function handles None gracefully without crashing

```python
def test_function_with_none_input(self):
    """Test that function() handles None input gracefully"""
    with pytest.raises((AttributeError, TypeError, ValueError)):
        result = function(None)

    # OR if function should return None/False
    result = function(None)
    assert result is None  # or result is False
```

**Common None input bugs:**
- Missing `if x is None:` checks before calling methods
- Passing None to external libraries (jwt.encode, bcrypt.hashpw)
- Uninitialized optional parameters

**Fix pattern:**
```python
def function(param: Optional[str]) -> Optional[ReturnType]:
    if param is None:
        return None  # or raise ValueError
    # ... rest of function
```

---

### 2. Empty Collections

**Test pattern:** Verify function handles empty lists/dicts/strings correctly

```python
def test_function_with_empty_list(self):
    """Test that function() handles empty list gracefully"""
    result = function([])
    assert result is None  # or result == [] or result == False

def test_function_with_empty_dict(self):
    """Test that function() handles empty dict gracefully"""
    result = function({})
    assert result is None  # or result == {}
```

**Common empty collection bugs:**
- Iterating over empty list without checking length
- Accessing `list[0]` on empty list
- Returning incorrect default values

**Fix pattern:**
```python
def function(items: List[Any]) -> Optional[ReturnType]:
    if not items:  # Covers [], (), {}, '', None
        return None
    # ... rest of function
```

---

### 3. Invalid Types

**Test pattern:** Verify function rejects wrong types with clear errors

```python
def test_function_with_wrong_type(self):
    """Test that function() handles wrong type gracefully"""
    # int instead of str
    with pytest.raises((TypeError, AttributeError)):
        result = function(123)

    # list instead of str
    with pytest.raises((TypeError, AttributeError)):
        result = function(["item"])

    # dict instead of str
    with pytest.raises((TypeError, AttributeError)):
        result = function({"key": "value"})
```

**Common type error bugs:**
- Slicing on non-subscriptable types (`int[:71]` crashes)
- Calling string methods on non-strings (`None.lower()` crashes)
- Inconsistent error handling (some types crash, others return False)

**Fix pattern:**
```python
def function(param: str) -> ReturnType:
    if not isinstance(param, str):
        raise TypeError(f"Expected str, got {type(param).__name__}")
    # ... rest of function
```

---

### 4. Boundary Values

**Test pattern:** Test min/max values, zero, negative numbers

```python
def test_function_with_boundary_values(self):
    """Test that function() handles boundary values correctly"""
    # Zero
    result = function(0)
    assert result == expected_zero_behavior

    # Negative
    result = function(-1)
    assert result == expected_negative_behavior  # Should reject or handle

    # Very large
    result = function(2**63)
    assert result == expected_large_behavior

    # Infinity
    result = function(float('inf'))
    assert result == expected_inf_behavior

    # NaN
    result = function(float('nan'))
    assert math.isnan(result)  # NaN != NaN, use math.isnan()
```

**Common boundary bugs:**
- Negative values accepted when they should be rejected
- Division by zero not handled
- Integer overflow (rare in Python 3, but possible with float conversions)
- NaN propagation (NaN + any = NaN)

**Fix pattern:**
```python
def function(amount: Union[int, float]) -> ReturnType:
    if amount < 0:
        raise ValueError(f"Amount must be non-negative, got {amount}")
    if math.isnan(amount) or math.isinf(amount):
        raise ValueError(f"Amount must be finite, got {amount}")
    # ... rest of function
```

---

### 5. Concurrent Access

**Test pattern:** Test thread safety with concurrent operations

```python
def test_concurrent_function_calls(self):
    """Test that function() is thread-safe under concurrent access"""
    import threading

    shared_resource = SharedResource()
    results = []
    errors = []

    def worker():
        try:
            result = shared_resource.method()
            results.append(result)
        except Exception as e:
            errors.append(e)

    # Launch 10 threads
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify no errors occurred
    assert len(errors) == 0, f"Concurrent access caused errors: {errors}"
```

**Common concurrency bugs:**
- TOCTOU (time-of-check-time-of-use) race conditions
- Non-atomic check-and-increment operations
- Missing locks on shared state

**Fix pattern:**
```python
class ThreadSafeClass:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {}

    def method(self):
        with self._lock:  # Atomic operation
            if key not in self._state:
                self._state[key] = compute_value()
            return self._state[key]
```

---

### 6. Network Failures

**Test pattern:** Test graceful handling of network errors

```python
def test_function_with_network_failure(self):
    """Test that function() handles network failures gracefully"""
    import pytest
    from unittest.mock import patch

    # Mock network failure
    with patch('requests.get', side_effect=ConnectionError("Network error")):
        result = function()
        assert result is None  # or raises specific exception

    # Mock timeout
    with patch('requests.get', side_effect=TimeoutError("Request timeout")):
        result = function()
        assert result is None  # or raises specific exception
```

**Common network failure bugs:**
- Crashes on ConnectionError instead of graceful degradation
- No retry logic for transient failures
- Missing timeout configuration (infinite hangs)

**Fix pattern:**
```python
def function() -> Optional[ReturnType]:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return process(response)
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Network error: {e}")
        return None
```

---

### 7. Timeouts

**Test pattern:** Test timeout handling for long-running operations

```python
import pytest

def test_function_with_timeout(self):
    """Test that function() handles timeouts correctly"""
    # Mock slow operation
    with patch('module.slow_operation', side_effect=lambda: time.sleep(100)):
        with pytest.raises(TimeoutError):
            result = function(timeout=1)  # 1 second timeout
```

**Common timeout bugs:**
- No timeout configured (infinite hangs)
- Timeout doesn't cancel operation (resource leaks)
- Timeout exception crashes instead of graceful degradation

**Fix pattern:**
```python
import signal
from contextlib import contextmanager

@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def function() -> Optional[ReturnType]:
    try:
        with timeout(10):
            result = slow_operation()
        return result
    except TimeoutError as e:
        logger.warning(f"Operation timed out: {e}")
        return None
```

---

## Severity Classification

### CRITICAL Severity

**Definition:** Production crashes, data loss, security vulnerabilities

**Examples:**
- Authentication bypass (login without password)
- SQL injection vulnerabilities
- Database corruption (writes to wrong tables)
- Zero-day exploits (remote code execution)

**Action Required:** Fix immediately, do not ship to production

**Examples from Phase 104:**
- Bug #1 (Phase 088): Zero vector cosine similarity returns NaN (episode boundary detection failure)
- Bug #10 (Phase 104): RateLimitMiddleware accepts negative limit (configuration error causes outage)

---

### HIGH Severity

**Definition:** Graceful degradation failures, incorrect results

**Examples:**
- Crashes on invalid input (None, wrong type)
- TOCTOU race conditions (budget exceeded under concurrency)
- Negative values accepted (could cause accounting errors)

**Action Required:** Fix before next production deployment

**Examples from Phase 104:**
- Bug #10-14 (Phase 104): verify_password(), verify_mobile_token(), get_current_user_ws() crash with None
- Bug #15-16 (Phase 104): Negative payment amounts/limits accepted
- Bug #20 (Phase 104): TOCTOU race in concurrent budget spend checks

---

### MEDIUM Severity

**Definition:** Error messages not helpful, validation missing

**Examples:**
- Empty strings accepted (creates confusing state)
- None inputs cause crashes (but caught by exception handler)
- Inconsistent error handling (some types crash, others return False)

**Action Required:** Fix within next 2 sprints

**Examples from Phase 104:**
- Bug #11 (Phase 104): verify_password() crashes with int/float/dict types (inconsistent)
- Bug #17 (Phase 104): Zero monthly limit causes incorrect behavior
- Bug #18-19 (Phase 104): Negative tolerance/user count accepted

---

### LOW Severity

**Definition:** Cosmetic issues, logging improvements

**Examples:**
- Confusing cache keys (empty agent_id creates ":action" key)
- Non-standard error codes (500 instead of 400)
- Verbose error messages (exposes internal details)

**Action Required:** Fix when convenient, backlog item

**Examples from Phase 104:**
- Bug #17 (Phase 104): Empty string agent_id accepted
- Bug #16 (Phase 104): Leap year date addition fails (Python datetime limitation)

---

## Reusability for Frontend Phases

Error path testing patterns from Phase 104 can be **directly applied to frontend testing** in Phases 105-109 with minimal modifications.

### Frontend-Specific Error Scenarios

**React error paths to test:**
- Network failures (API calls return 500, 404, timeout)
- User input edge cases (empty strings, None values, special characters)
- Component state errors (missing props, undefined state)
- Race conditions (concurrent API calls, rapid user interactions)

### Frontend Testing Tools

**React Testing Library** (recommended):
```javascript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

test('login form handles empty password gracefully', async () => {
  render(<LoginForm />)

  // Submit with empty password
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))

  // Should show error message, not crash
  expect(screen.getByText('Password is required')).toBeInTheDocument()
})
```

**MSW (Mock Service Worker)** for API error simulation:
```javascript
import { rest } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  rest.post('/api/login', (req, res, ctx) => {
    return res(ctx.status(500), ctx.json({ error: 'Internal server error' }))
  })
)

test('login form handles API errors gracefully', async () => {
  render(<LoginForm />)

  await userEvent.click(screen.getByRole('button', { name: 'Login' }))

  // Should show error message, not crash
  await waitFor(() => {
    expect(screen.getByText('Login failed. Please try again.')).toBeInTheDocument()
  })
})
```

### Mapping Backend to Frontend Patterns

| Backend Pattern | Frontend Equivalent |
|----------------|---------------------|
| `test_verify_password_with_none_password` | `test_login_form_handles_empty_password` |
| `test_rate_limit_with_negative_limit` | `test_api_client_handles_429_responses` |
| `test_budget_limit_with_negative_monthly_limit` | `test_budget_form_rejects_negative_values` |
| `test_function_with_wrong_type` | `test_component_handles_invalid_props` |
| `test_concurrent_function_calls` | `test_component_handles_rapid_user_interactions` |

### Frontend VALIDATED_BUG Pattern

Adapt the VALIDATED_BUG pattern for frontend bugs:

```javascript
test('select dropdown crashes with None options', () => {
  /**
   * VALIDATED_BUG: Select component crashes with None options
   *
   * Expected:
   *   - Select component should handle None/undefined options gracefully
   *   - Should show empty state or "No options available" message
   *
   * Actual:
   *   - TypeError: Cannot read property 'map' of undefined
   *   - Crash at line 42: options.map(...)
   *
   * Severity: HIGH
   * Impact:
   *   - Select component crashes when options prop is None
   *   - User cannot select value, form submission blocked
   *
   * Fix:
   *   Add default empty array:
   *   const options = props.options || []
   *
   * Validated: ✅ Test confirms bug exists
   */
  render(<Select options={None} />)

  expect(screen.getByText('No options available')).toBeInTheDocument()
})
```

---

## Complete Test Examples

### Example 1: Authentication Error Path (Auth Service)

```python
import pytest
from core.auth import verify_password, get_password_hash

class TestAuthFailures:
    """Tests for authentication failure scenarios"""

    def test_verify_password_with_none_password(self):
        """
        VALIDATED_BUG: verify_password() crashes with None password

        Expected:
            - verify_password() should return False for None password
            - Graceful degradation without crash

        Actual:
            - TypeError: 'NoneType' object is not subscriptable
            - Crash at line 48: plain_password[:71]

        Severity: HIGH
        Impact:
            - Login endpoint crashes if None password passed
            - Potential DoS vector if attacker sends None passwords
            - Inconsistent with expected graceful degradation

        Fix:
            Add None check at start of verify_password():
            ```python
            def verify_password(plain_password: str, hashed_password: str) -> bool:
                if plain_password is None or hashed_password is None:
                    return False
                # ... rest of function
            ```

        Validated: ✅ Test confirms bug exists
        """
        valid_hash = get_password_hash("test_password")

        with pytest.raises(TypeError):
            result = verify_password(None, valid_hash)

    def test_verify_password_with_wrong_type(self):
        """
        VALIDATED_BUG: verify_password() crashes with non-string types

        Expected:
            - verify_password() should return False for non-string types
            - Consistent error handling across all invalid types

        Actual:
            - int: TypeError: 'int' object is not subscriptable
            - float: TypeError: 'float' object is not subscriptable
            - dict: TypeError: unhashable type: 'slice'
            - list: Returns False (caught by exception handler)

        Severity: MEDIUM
        Impact:
            - Inconsistent error handling across types
            - Some types crash, others return False
            - Potential DoS vector with int/float/dict types

        Fix:
            Add type validation:
            ```python
            def verify_password(plain_password: str, hashed_password: str) -> bool:
                if not isinstance(plain_password, (str, bytes)):
                    return False
                if not isinstance(hashed_password, (str, bytes)):
                    return False
                # ... rest of function
            ```

        Validated: ✅ Test confirms bug exists
        """
        valid_hash = get_password_hash("test_password")

        # int crashes
        with pytest.raises(TypeError):
            verify_password(123, valid_hash)

        # list returns False (exception handler)
        assert verify_password(["password"], valid_hash) is False

        # dict crashes
        with pytest.raises(TypeError, match="unhashable type"):
            verify_password({"pw": "test"}, valid_hash)
```

**File:** `backend/tests/error_paths/test_auth_error_paths.py` (lines 15-80)

---

### Example 2: Security Error Path (Rate Limiting)

```python
import pytest
from unittest.mock import Mock, MagicMock
from fastapi import Request
from core.security import RateLimitMiddleware

class TestRateLimiting:
    """Tests for rate limiting error scenarios"""

    def test_rate_limit_with_negative_limit(self, mock_app):
        """
        VALIDATED_BUG: RateLimitMiddleware accepts negative limit

        Expected:
            - RateLimitMiddleware should reject negative requests_per_minute
            - Should raise ValueError during initialization

        Actual:
            - Negative limit accepted without validation
            - All requests rejected (len(list) >= negative always True)

        Severity: HIGH
        Impact:
            - Misconfigured middleware blocks all traffic
            - Configuration error causes production outage
            - No clear error message during initialization

        Fix:
            Add validation in __init__:
            ```python
            def __init__(self, app, requests_per_minute: int = 60):
                if requests_per_minute <= 0:
                    raise ValueError(f"requests_per_minute must be positive, got {requests_per_minute}")
                super().__init__(app)
                self.requests_per_minute = requests_per_minute
            ```

        Validated: ✅ Test confirms bug exists
        """
        middleware = RateLimitMiddleware(app=mock_app, requests_per_minute=-10)

        assert middleware.requests_per_minute == -10  # BUG: Accepted without validation

    def test_rate_limit_with_zero_limit(self, mock_app):
        """
        VALIDATED_BUG: RateLimitMiddleware accepts zero limit

        Expected:
            - RateLimitMiddleware should reject zero requests_per_minute
            - Should raise ValueError during initialization

        Actual:
            - Zero limit accepted without validation
            - All requests rejected (len(list) >= 0 always True)

        Severity: MEDIUM
        Impact:
            - Zero limit effectively blocks all requests
            - May be intentional for "disable mode" but should be explicit
            - No validation or documentation of this behavior

        Fix:
            Same as Bug #10 - validate requests_per_minute > 0 in __init__

        Validated: ✅ Test confirms bug exists
        """
        middleware = RateLimitMiddleware(app=mock_app, requests_per_minute=0)

        assert middleware.requests_per_minute == 0  # Accepted without validation

    async def test_rate_limit_with_none_client_ip(self, mock_app, mock_request_factory):
        """
        VALIDATED_BUG: RateLimitMiddleware crashes on None client

        Expected:
            - Should use fallback value like "unknown" or "0.0.0.0"
            - Graceful degradation without crash

        Actual:
            - AttributeError: 'NoneType' object has no attribute 'host'
            - Crash at line 18: client_ip = request.client.host

        Severity: HIGH
        Impact:
            - Production crashes if request.client is None
            - No graceful degradation or fallback
            - Error not caught by middleware exception handler

        Fix:
            Add None check:
            ```python
            client_ip = request.client.host if request.client else "unknown"
            ```

        Validated: ✅ Test confirms bug exists
        """
        middleware = RateLimitMiddleware(app=mock_app, requests_per_minute=60)

        # Create request with None client
        request = Mock(spec=Request)
        request.client = None  # No client attached
        request.state = MagicMock()

        async def call_next(req):
            return Response(content="OK", status_code=200)

        with pytest.raises(AttributeError):
            await middleware.dispatch(request, call_next)
```

**File:** `backend/tests/error_paths/test_security_error_paths.py` (lines 15-120)

---

### Example 3: Financial Error Path (Negative Values)

```python
import pytest
from decimal import Decimal
from datetime import datetime
from core.financial_ops_engine import BudgetGuardrails, BudgetLimit, SpendStatus

class TestPaymentFailures:
    """Tests for payment failure scenarios"""

    def test_payment_with_negative_amount(self):
        """
        VALIDATED_BUG: Negative payment amounts accepted

        Expected:
            - check_spend() should reject negative amounts
            - Should raise ValueError or return REJECTED status

        Actual:
            - Negative amounts accepted without validation
            - Could bypass budget checks or reverse spend

        Severity: HIGH
        Impact:
            - Negative payments could reverse existing spend (creating credit)
            - Could bypass budget approval logic
            - Accounting discrepancies if negative amounts recorded

        Fix:
            Add validation at start of check_spend():
            ```python
            def check_spend(self, category: str, amount: Union[Decimal, str, float], ...):
                amount_decimal = to_decimal(amount)
                if amount_decimal < 0:
                    raise ValueError(f"Amount must be non-negative, got {amount_decimal}")
                # ... rest of function
            ```

        Validated: ✅ Test confirms bug exists
        """
        guardrails = BudgetGuardrails()
        limit = BudgetLimit(category="marketing", monthly_limit=Decimal('1000.00'))
        guardrails.set_limit(limit)

        # Negative amount should be rejected
        result = guardrails.check_spend("marketing", Decimal('-50.00'))

        # BUG: No validation for negative amounts
        assert result["status"] == SpendStatus.APPROVED.value  # Should be REJECTED

    def test_budget_limit_with_negative_monthly_limit(self):
        """
        VALIDATED_BUG: Negative monthly limit accepted

        Expected:
            - set_limit() should reject negative monthly_limit
            - Should raise ValueError

        Actual:
            - Negative limit accepted without validation
            - Causes incorrect utilization calculations

        Severity: HIGH
        Impact:
            - Negative limit causes utilization_pct calculation to be negative
            - Reverses budget logic (spending decreases utilization)
            - All spends would be rejected at block threshold

        Fix:
            Add validation in set_limit():
            ```python
            def set_limit(self, limit: BudgetLimit):
                if limit.monthly_limit <= 0:
                    raise ValueError(f"monthly_limit must be positive, got {limit.monthly_limit}")
                self._limits[limit.category] = limit
            ```

        Validated: ✅ Test confirms bug exists
        """
        guardrails = BudgetGuardrails()

        # Negative limit should be rejected
        limit = BudgetLimit(category="marketing", monthly_limit=Decimal('-1000.00'))

        # BUG: Negative limit accepted
        guardrails.set_limit(limit)

        assert limit.monthly_limit < 0  # Confirmed: negative limit accepted

    def test_budget_limit_with_zero_monthly_limit(self):
        """
        VALIDATED_BUG: Zero monthly limit causes incorrect behavior

        Expected:
            - Zero limit should be rejected (all spends blocked)
            - OR should be explicitly documented as "unlimited budget" mode

        Actual:
            - Zero limit sets utilization_pct = 0
            - Approves all spends (opposite of expected behavior)

        Severity: MEDIUM
        Impact:
            - Zero limit acts as "unlimited budget" (approves all spends)
            - Opposite of expected behavior (should reject all spends)
            - Configuration error could cause overspend

        Fix:
            Reject zero limit in set_limit() (see Bug #16 fix) or handle explicitly:
            ```python
            if limit.monthly_limit <= 0:
                return {"status": SpendStatus.REJECTED.value, "reason": "Invalid budget limit"}
            ```

        Validated: ✅ Test confirms bug exists
        """
        guardrails = BudgetGuardrails()

        limit = BudgetLimit(category="marketing", monthly_limit=Decimal('0.00'))
        guardrails.set_limit(limit)

        result = guardrails.check_spend("marketing", Decimal('100.00'))

        # BUG: Approves with 0% utilization (should reject)
        assert result["utilization_pct"] == 0
```

**File:** `backend/tests/error_paths/test_finance_error_paths.py` (lines 15-150)

---

### Example 4: Edge Case (None Inputs)

```python
import pytest
from core.governance_cache import GovernanceCache

class TestNullInputs:
    """Tests for None input handling"""

    def test_none_action_type_in_cache_lookup(self):
        """
        VALIDATED_BUG: GovernanceCache crashes on None action_type

        Expected:
            - _make_key() should handle None action_type gracefully
            - Should raise ValueError or return None

        Actual:
            - AttributeError: 'NoneType' object has no attribute 'lower'
            - Crash at line 109: action_type.lower()

        Severity: HIGH
        Impact:
            - Cache operations crash on None action_type
            - Affects both get() and set() operations
            - No graceful degradation for invalid input

        Fix:
            Add None check in _make_key():
            ```python
            def _make_key(self, agent_id: str, action_type: str) -> str:
                if action_type is None:
                    raise ValueError("action_type cannot be None")
                return f"{agent_id}:{action_type.lower()}"
            ```

        Validated: ✅ Test confirms bug exists
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'lower'"):
            result = cache.get("agent-1", None)

    def test_none_agent_id_in_governance_check(self):
        """
        NO BUG: None agent_id handled correctly

        Expected:
            - Cache should handle None agent_id gracefully
            - Should create cache key or reject

        Actual:
            - Creates key "None:action" (weird but working)

        Severity: LOW (not a bug, just unusual behavior)

        Impact:
            - Works but creates confusing cache entries
            - No production impact (rare scenario)

        Fix:
            Optional: Add validation to reject None agent_id

        Validated: ✅ Not a bug, behavior is acceptable
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # None agent_id works (creates "None:stream_chat" key)
        result = cache.set(None, "stream_chat", {"allowed": True})
        assert result is True

        result = cache.get(None, "stream_chat")
        assert result is not None
```

**File:** `backend/tests/error_paths/test_edge_case_error_paths.py` (lines 80-150)

---

## Best Practices

### 1. Always Use VALIDATED_BUG Docstrings

**Why:** Ensures bugs are documented with severity, impact, and fix recommendations

**Do:**
```python
def test_function_with_none_input(self):
    """
    VALIDATED_BUG: Brief description

    Expected: What should happen
    Actual: What actually happens
    Severity: HIGH
    Impact: Why it matters
    Fix: How to fix it
    Validated: ✅ Test confirms bug exists
    """
    with pytest.raises(AttributeError):
        function(None)
```

**Don't:**
```python
def test_function_with_none_input(self):
    """Test that function handles None"""
    with pytest.raises(AttributeError):
        function(None)
    # Bug not documented, no severity/impact/fix
```

---

### 2. Test Isolation

**Why:** Tests should not depend on each other. Each test should be runnable independently.

**Do:**
```python
def test_function_with_none_input(self):
    cache = GovernanceCache()  # Fresh instance for each test
    with pytest.raises(AttributeError):
        cache.get("agent-1", None)
```

**Don't:**
```python
def setUp(self):
    self.cache = GovernanceCache()  # Shared state

def test_function_with_none_input(self):
    with pytest.raises(AttributeError):
        self.cache.get("agent-1", None)  # Depends on setUp
```

---

### 3. Use pytest.raises() for Exception Validation

**Why:** Explicitly validates exception type and message

**Do:**
```python
def test_function_with_none_input(self):
    with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'lower'"):
        function(None)
```

**Don't:**
```python
def test_function_with_none_input(self):
    try:
        function(None)
        assert False, "Should have raised AttributeError"
    except AttributeError:
        pass  # Passed
```

---

### 4. Test One Thing Per Test

**Why:** Tests are easier to understand and debug when they validate a single error scenario

**Do:**
```python
def test_verify_password_with_none_password(self):
    """Test that verify_password() handles None password"""
    with pytest.raises(TypeError):
        verify_password(None, valid_hash)

def test_verify_password_with_empty_password(self):
    """Test that verify_password() handles empty password"""
    result = verify_password("", valid_hash)
    assert result is False
```

**Don't:**
```python
def test_verify_password_with_invalid_inputs(self):
    """Test all invalid inputs"""
    with pytest.raises(TypeError):
        verify_password(None, valid_hash)

    assert verify_password("", valid_hash) is False
    assert verify_password(123, valid_hash) is False
    # Tests 3 things, unclear which failed
```

---

### 5. Use Descriptive Test Names

**Why:** Test names should explain what is being tested and what the expected behavior is

**Do:**
```python
def test_verify_password_with_none_password_raises_type_error(self):
    """Test that verify_password() raises TypeError when password is None"""
    pass

def test_budget_limit_with_negative_monthly_limit_rejected(self):
    """Test that negative monthly limits are rejected during set_limit()"""
    pass
```

**Don't:**
```python
def test_auth_error(self):
    """Test auth error"""  # Which error?
    pass

def test_budget_limit(self):
    """Test budget limit"""  # What aspect?
    pass
```

---

### 6. Mock External Dependencies

**Why:** Tests should be fast and deterministic. External dependencies (APIs, databases) introduce flakiness.

**Do:**
```python
def test_function_with_network_error(self):
    with patch('requests.get', side_effect=ConnectionError("Network error")):
        result = function()
        assert result is None
```

**Don't:**
```python
def test_function_with_network_error(self):
    # Makes real HTTP request (slow, flaky)
    result = function(url="http://invalid-domain-12345.com")
    assert result is None
```

---

### 7. Use Fixtures for Common Setup

**Why:** Fixtures reduce test duplication and make tests more readable

**Do:**
```python
@pytest.fixture
def valid_password_hash():
    """Valid bcrypt hash for 'test_password'"""
    return get_password_hash("test_password")

class TestAuthFailures:
    def test_verify_password_with_none_password(self, valid_password_hash):
        with pytest.raises(TypeError):
            verify_password(None, valid_password_hash)

    def test_verify_password_with_empty_password(self, valid_password_hash):
        assert verify_password("", valid_password_hash) is False
```

**Don't:**
```python
class TestAuthFailures:
    def test_verify_password_with_none_password(self):
        valid_hash = get_password_hash("test_password")  # Duplicated
        with pytest.raises(TypeError):
            verify_password(None, valid_hash)

    def test_verify_password_with_empty_password(self):
        valid_hash = get_password_hash("test_password")  # Duplicated
        assert verify_password("", valid_hash) is False
```

---

## Tools and Frameworks

### pytest

**Primary testing framework for Python error path tests**

**Key features:**
- `pytest.raises()` for exception validation
- `pytest.mark.skipif` for conditional test skipping
- `pytest.fixture` for shared test setup
- `pytest.param` for parameterized tests

**Installation:**
```bash
pip install pytest pytest-cov
```

**Usage:**
```bash
# Run all error path tests
pytest backend/tests/error_paths/ -v

# Run specific test file
pytest backend/tests/error_paths/test_auth_error_paths.py -v

# Run with coverage
pytest backend/tests/error_paths/ --cov=core.auth --cov-report=html
```

---

### pytest-cov

**Coverage reporting for pytest**

**Key features:**
- Line coverage percentage
- Branch coverage percentage
- HTML coverage reports with line-by-line highlighting

**Usage:**
```bash
pytest backend/tests/error_paths/ --cov=core.auth --cov-report=term-missing
```

**Output:**
```
Name           Stmts   Miss Branch BrPart   Cover   Missing
-----------------------------------------------------------
core/auth.py     132     35     28      7  67.50%   27->35, 29, 72, 97->103
-----------------------------------------------------------
```

---

### unittest.mock

**Mocking library for external dependencies**

**Key features:**
- `Mock()` for generic mock objects
- `MagicMock()` for mock objects with magic methods
- `patch()` for temporarily replacing objects

**Usage:**
```python
from unittest.mock import Mock, MagicMock, patch

# Mock object
mock_db = Mock(spec=Session)
mock_db.query.return_value.filter.return_value.first.return_value = agent

# Patch external dependency
with patch('requests.get', side_effect=ConnectionError("Network error")):
    result = function()
    assert result is None
```

---

### Hypothesis (Optional)

**Property-based testing library (for advanced invariants)**

**Key features:**
- Automatically generates test inputs
- Shrinks failing examples to minimal cases
- Finds edge cases humans miss

**Usage:**
```python
from hypothesis import given, strategies as st

@given(st.none())
def test_verify_password_with_none_password(password):
    """Test that verify_password() handles None gracefully"""
    # Hypothesis will test None automatically
    result = verify_password(password, valid_hash)
    assert result is False
```

**Note:** Hypothesis is **not used in Phase 104** error path tests because we explicitly test specific error scenarios. Property tests are more suited for invariants (Phase 103).

---

## Conclusion

Error path testing is a **critical complement to unit tests and property tests**. By systematically testing error scenarios, we discovered **20 validated bugs** across authentication, security, financial, and edge case categories in Phase 104.

**Key takeaways:**
1. **VALIDATED_BUG pattern** ensures bugs are documented with severity, impact, and fixes
2. **Error path categories** help organize tests by service or error type
3. **Common scenarios** (None inputs, empty collections, invalid types, boundary values) account for most bugs
4. **Severity classification** helps prioritize fixes (CRITICAL > HIGH > MEDIUM > LOW)
5. **Reusability** - Frontend phases can apply these patterns with minimal modifications

**Next steps:**
- Apply these patterns to frontend testing (Phases 105-109)
- Fix all 20 VALIDATED_BUG findings (prioritize CRITICAL and HIGH severity)
- Expand error path coverage to other services (LLM streaming, browser automation, device capabilities)

**Files created:**
- `backend/tests/error_paths/test_auth_error_paths.py` (36 tests, 67.5% coverage)
- `backend/tests/error_paths/test_security_error_paths.py` (33 tests, 100% coverage)
- `backend/tests/error_paths/test_finance_error_paths.py` (41 tests, 61.15% coverage)
- `backend/tests/error_paths/test_edge_case_error_paths.py` (33 tests, 31.02% coverage)

**Total:** 143 tests, 100% pass rate, 20 VALIDATED_BUG documented

---

*Documentation created: 2026-02-28*
*Phase: 104-backend-error-path-testing*
*Plan: 05*
*Status: COMPLETE*
