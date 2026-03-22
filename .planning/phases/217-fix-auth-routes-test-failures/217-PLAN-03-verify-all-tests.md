---
wave: 2
depends_on:
  - 217-PLAN-01-debug-database-state
  - 217-PLAN-02-fix-mock-session
files_modified:
  - tests/test_auth_routes_coverage.py
autonomous: false
---

# Plan 217-03: Verify All Auth Tests Pass

**Goal:** Confirm all 10 failing auth tests now pass after fixes from Plans 01-02.

## Tests to Verify

Based on initial analysis, these tests were failing:

1. `test_login_success_with_valid_credentials`
2. `test_login_with_username_as_email`
3. `test_login_with_invalid_password` (should return 401)
4. `test_login_with_locked_account` (should return 401)
5. `test_login_updates_last_login_timestamp`
6. `test_login_returns_security_level`
7. `test_login_returns_user_roles`
8. `test_login_with_extra_fields`
9. `test_refresh_token_success`
10. `test_state_transitions` tests

## Tasks

### Task 1: Run All Auth Route Tests

**Command:**
```bash
cd /Users/rushiparikh/projects/atom/backend
PYTHONPATH=. pytest tests/test_auth_routes_coverage.py -v --tb=short 2>&1 | tee /tmp/auth-test-results.txt
```

**Expected Output:**
```
======================== 67 passed in XX.XXs =========================
```

### Task 2: Analyze Any Remaining Failures

If any tests still fail, categorize the failure:

**A. Database-related failures:**
- User not found
- Transaction not committed
- Session isolation issue

**B. Password-related failures:**
- Hash mismatch
- Encoding issue
- Bcrypt version mismatch

**C. Mock/patch-related failures:**
- Mock not called
- Wrong patch location
- Side_effect not working

**D. Test logic issues:**
- Wrong assertion
- Incorrect test data
- Missing setup

### Task 3: Fix Remaining Failures (if any)

For each remaining failure, apply appropriate fix based on category from Task 2.

**Example fixes:**

**Database issue:**
```python
# Ensure user is committed before login
test_db.flush()  # Force write to database
test_db.refresh(user)  # Refresh from DB
```

**Password issue:**
```python
# Ensure consistent encoding
password_hash = auth_service.hash_password("TestPassword123!").encode('utf-8').decode('utf-8')
```

**Mock issue:**
```python
# Try alternative patch location
with patch('core.enterprise_auth_service.EnterpriseAuthService.verify_credentials') as mock_verify:
    mock_verify.return_value = UserCredentials(...)
```

### Task 4: Run Test Suite 3 Times for Stability

**Command:**
```bash
cd /Users/rushiparikh/projects/atom/backend
for i in {1..3}; do
    echo "=== Run $i ==="
    PYTHONPATH=. pytest tests/test_auth_routes_coverage.py -v --tb=no -q
done
```

**Expected:** All 3 runs show 67 passed (100% pass rate, no flakiness)

### Task 5: Document Results

**Create:** `.planning/phases/217-fix-auth-routes-test-failures/217-VERIFICATION.md`

**Content:**
```markdown
# Phase 217 Verification Report

## Tests Fixed
- Before: 57/67 passing (85.1% pass rate)
- After: 67/67 passing (100% pass rate)
- Tests fixed: 10

## Root Cause
Database session mismatch in mock credential verification.

## Solution Applied
[Describe what was fixed]

## Test Results
[Attach test output]

## Stability
3 consecutive runs: 67/67 passing each run
```

## Verification

- [ ] All 67 auth tests pass
- [ ] Zero failures in 3 consecutive runs
- [ ] No hardcoded workarounds in test code
- [ ] Verification report created

## Success Criteria

**Complete:** All 67 auth tests passing (100% pass rate)
**Documented:** Verification report with before/after metrics
**Stable:** 100% pass rate maintained across 3 runs
---
wave: 2
depends_on:
  - 217-PLAN-01-debug-database-state
  - 217-PLAN-02-fix-mock-session
files_modified:
  - tests/test_auth_routes_coverage.py
  - .planning/phases/217-fix-auth-routes-test-failures/217-VERIFICATION.md
autonomous: false
---

# Plan 217-03: Verify All Auth Tests Pass

**Goal:** Confirm all 10 failing auth tests now pass after fixes from Plans 01-02.

## Tests to Verify

Based on initial analysis, these tests were failing:

1. `test_login_success_with_valid_credentials`
2. `test_login_with_username_as_email`
3. `test_login_with_invalid_password` (should return 401)
4. `test_login_with_locked_account` (should return 401)
5. `test_login_updates_last_login_timestamp`
6. `test_login_returns_security_level`
7. `test_login_returns_user_roles`
8. `test_login_with_extra_fields`
9. `test_refresh_token_success`
10. `test_state_transitions` tests

## Tasks

### Task 1: Run All Auth Route Tests

**Command:**
```bash
cd /Users/rushiparikh/projects/atom/backend
PYTHONPATH=. pytest tests/test_auth_routes_coverage.py -v --tb=short 2>&1 | tee /tmp/auth-test-results.txt
```

**Expected Output:**
```
======================== 67 passed in XX.XXs =========================
```

### Task 2: Analyze Any Remaining Failures

If any tests still fail, categorize the failure:

**A. Database-related failures:**
- User not found
- Transaction not committed
- Session isolation issue

**B. Password-related failures:**
- Hash mismatch
- Encoding issue
- Bcrypt version mismatch

**C. Mock/patch-related failures:**
- Mock not called
- Wrong patch location
- Side_effect not working

**D. Test logic issues:**
- Wrong assertion
- Incorrect test data
- Missing setup

### Task 3: Fix Remaining Failures (if any)

For each remaining failure, apply appropriate fix based on category from Task 2.

**Example fixes:**

**Database issue:**
```python
# Ensure user is committed before login
test_db.flush()  # Force write to database
test_db.refresh(user)  # Refresh from DB
```

**Password issue:**
```python
# Ensure consistent encoding
password_hash = auth_service.hash_password("TestPassword123!").encode('utf-8').decode('utf-8')
```

**Mock issue:**
```python
# Try alternative patch location
with patch('core.enterprise_auth_service.EnterpriseAuthService.verify_credentials') as mock_verify:
    mock_verify.return_value = UserCredentials(...)
```

### Task 4: Run Test Suite 3 Times for Stability

**Command:**
```bash
cd /Users/rushiparikh/projects/atom/backend
for i in {1..3}; do
    echo "=== Run $i ==="
    PYTHONPATH=. pytest tests/test_auth_routes_coverage.py -v --tb=no -q
done
```

**Expected:** All 3 runs show 67 passed (100% pass rate, no flakiness)

### Task 5: Document Results

**Create:** `.planning/phases/217-fix-auth-routes-test-failures/217-VERIFICATION.md`

**Content:**
```markdown
# Phase 217 Verification Report

## Tests Fixed
- Before: 57/67 passing (85.1% pass rate)
- After: 67/67 passing (100% pass rate)
- Tests fixed: 10

## Root Cause
Database session mismatch in mock credential verification.

## Solution Applied
[Describe what was fixed]

## Test Results
[Attach test output]

## Stability
3 consecutive runs: 67/67 passing each run
```

## Verification

- [ ] All 67 auth tests pass
- [ ] Zero failures in 3 consecutive runs
- [ ] No hardcoded workarounds in test code
- [ ] Verification report created

## Success Criteria

**Complete:** All 67 auth tests passing (100% pass rate)
**Documented:** Verification report with before/after metrics
**Stable:** 100% pass rate maintained across 3 runs
