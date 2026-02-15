---
phase: 08-80-percent-coverage-push
plan: 39
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/api/test_auth_routes.py
  - tests/api/test_token_routes.py
  - tests/api/test_user_activity_routes.py
  - api/auth_routes.py
  - api/token_routes.py
  - api/user_activity_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Authentication tests rewritten to test actual mobile API endpoints"
    - "Coverage on auth_routes.py reaches 50%+ (177 lines → ~89 lines covered)"
    - "Coverage on token_routes.py reaches 50%+ (64 lines → ~32 lines covered)"
    - "Coverage on user_activity_routes.py reaches 50%+ (127 lines → ~64 lines covered)"
    - "All tests passing (no blockers)"
    - "Endpoint mismatches resolved"
  artifacts:
    - path: "tests/api/test_auth_routes.py"
      provides: "Authentication route tests (corrected)"
      min_lines: 250
    - path: "tests/api/test_token_routes.py"
      provides: "Token route tests (corrected)"
      min_lines: 150
    - path: "tests/api/test_user_activity_routes.py"
      provides: "User activity route tests (corrected)"
      min_lines: 200
  key_links:
    - from: "test_auth_routes.py"
      to: "api/auth_routes.py"
      via: "Auth endpoint coverage"
      pattern: "50%+"
    - from: "test_token_routes.py"
      to: "api/token_routes.py"
      via: "Token endpoint coverage"
      pattern: "50%+"
    - from: "test_user_activity_routes.py"
      to: "api/user_activity_routes.py"
      via: "Activity tracking coverage"
      pattern: "50%+"
status: pending
created: 2026-02-14
gap_closure: false
---

# Plan 39: Fix Authentication Tests - Endpoint Mismatches

**Status:** Pending
**Wave:** 1
**Dependencies:** None

## Objective

Rewrite authentication, token management, and user activity route tests to test actual mobile API endpoints and achieve 50%+ coverage, resolving endpoint mismatches from Plan 36.

## Context

During Phase 9.1 Plan 36 execution, critical issues were identified:

**Problem:** Test files targeted wrong API endpoints:
- Tests targeted: `/auth/register`, `/auth/login`, `/auth/logout`
- Actual endpoints: `/api/auth/mobile/login`, `/api/auth/mobile/biometric/register`, `/api/auth/logout`
- Result: 0% coverage on auth_routes.py and user_activity_routes.py

**Root Cause:** Existing test file tests were copied from another codebase without verifying actual endpoint paths in auth_routes.py

**Files to Fix:**
1. **api/auth_routes.py** (177 lines, 0% coverage)
   - Actual endpoints: GET/POST `/api/auth/mobile/login`, `/api/auth/mobile/biometric/register`, `/api/auth/logout`
   - Target: 50%+ coverage (~89 lines covered)

2. **api/token_routes.py** (64 lines, 37.84% coverage)
   - Endpoints: Token validation, revocation, blacklisting, expiry
   - Target: 50%+ coverage (~32 lines covered)

3. **api/user_activity_routes.py** (127 lines, 0% coverage)
   - Endpoints: Heartbeat submission, user state retrieval, manual override, clear override, available supervisors, active sessions, terminate session
   - Target: 50%+ coverage (~64 lines covered)

**Total Production Lines:** 368
**Expected Coverage at 50%:** ~184 lines
**Target Coverage Contribution:** +1.0-1.5% overall

## Success Criteria

**Must Have (truths that become verifiable):**
1. Authentication tests rewritten to test actual mobile API endpoints
2. Coverage on auth_routes.py reaches 50%+ (177 lines → ~89 lines covered)
3. Coverage on token_routes.py reaches 50%+ (64 lines → ~32 lines covered)
4. Coverage on user_activity_routes.py reaches 50%+ (127 lines → ~64 lines covered)
5. All tests passing (no blockers)
6. Endpoint mismatches resolved

**Should Have:**
- Mobile authentication flow tests (biometric registration, login)
- JWT token lifecycle tests (refresh, revoke, expire)
- Session management tests (create, update, delete, active sessions)
- User activity tracking tests (heartbeat, state, manual override)

**Could Have:**
- Rate limiting tests (max login attempts)
- Token performance tests (refresh timing)
- Activity aggregation tests (daily, weekly summaries)

**Won't Have:**
- Integration tests with real OAuth providers
- End-to-end authentication workflow tests
- Real-time activity streaming tests

## Tasks

### Task 1: Read actual API endpoint implementations

**File:** READ: `api/auth_routes.py`

**Action:**
Read auth_routes.py to identify actual endpoint paths:

```bash
grep -E "@router\.(get|post|put|delete)" api/auth_routes.py
```

**Expected Endpoints:**
- POST `/api/auth/mobile/login` - Mobile user authentication
- POST `/api/auth/mobile/biometric/register` - Biometric registration
- POST `/api/auth/logout` - User logout

**Verify:**
```bash
# Actual endpoints match test expectations
# Update test files to target correct endpoints
```

**Done:**
- Actual endpoints documented
- Test file requirements updated

### Task 2: Rewrite test_auth_routes.py

**File:** MODIFY: `tests/api/test_auth_routes.py` (250+ lines)

**Action:**
Rewrite authentication tests to target actual mobile endpoints:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.auth_routes import router
from core.auth_service import AuthService

# Tests to implement (corrected endpoints):
# 1. Test POST /api/auth/mobile/login - 200 status, JWT token returned
# 2. Test POST /api/auth/mobile/login - 401 for invalid credentials
# 3. Test POST /api/auth/mobile/biometric/register - 201 status, user registered
# 4. Test POST /api/auth/mobile/biometric/register - 400 for duplicate email
# 5. Test POST /api/auth/mobile/biometric/register - 400 for weak biometric data
# 6. Test POST /api/auth/logout - 200 status, session terminated
# 7. Test POST /api/auth/logout - 401 for no active session
# 8. Test GET /api/auth/session - 200 status, session details
# 9. Test GET /api/auth/session - 401 for no active session
# 10. Test POST /api/auth/refresh - 200 status, new JWT token
# 11. Test POST /api/auth/refresh - 401 for invalid token
# 12. Test POST /api/auth/reset-password - 200 status, reset email sent
# 13. Test POST /api/auth/reset-password - 404 for non-existent email
# 14. Test PUT /api/auth/reset-password/{token} - 200 status, password updated
# 15. Test PUT /api/auth/reset-password/{token} - 400 for expired token
```

**Coverage Targets:**
- Mobile login (POST /api/auth/mobile/login)
- Biometric registration (POST /api/auth/mobile/biometric/register)
- Logout (POST /api/auth/logout)
- Token refresh (POST /api/auth/refresh)
- Password reset (POST /api/auth/reset-password, PUT /api/auth/reset-password/{token})
- Session management (GET /api/auth/session)
- Error handling (400, 401, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_auth_routes.py -v --cov=api/auth_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 250+ lines of tests rewritten
- 50%+ coverage achieved
- All tests passing

### Task 3: Rewrite test_token_routes.py

**File:** MODIFY: `tests/api/test_token_routes.py` (150+ lines)

**Action:**
Rewrite token management tests to target actual endpoints:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.token_routes import router
from core.token_service import TokenService

# Tests to implement:
# 1. Test POST /token/validate - 200 status, token valid
# 2. Test POST /token/validate - 401 for invalid token
# 3. Test POST /token/validate - 401 for expired token
# 4. Test POST /token/revoke - 200 status, token revoked
# 5. Test POST /token/revoke - 401 for token not found
# 6. Test GET /token/blacklist - 200 status, list of revoked tokens
# 7. Test GET /token/blacklist/{token_id} - 200 status, token details
# 8. Test GET /token/blacklist/{token_id} - 404 for token not in blacklist
# 9. Test DELETE /token/blacklist/{token_id} - 200 status, token removed
# 10. Test GET /token/expire - 200 status, expiry timestamp
```

**Coverage Targets:**
- Token validation (POST /token/validate)
- Token revocation (POST /token/revoke)
- Blacklist management (GET /token/blacklist, GET /token/blacklist/{token_id})
- Blacklist cleanup (DELETE /token/blacklist/{token_id})
- Expiry checking (GET /token/expire)
- Error handling (401, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_token_routes.py -v --cov=api/token_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 150+ lines of tests rewritten
- 50%+ coverage achieved
- All tests passing

### Task 4: Rewrite test_user_activity_routes.py

**File:** MODIFY: `tests/api/test_user_activity_routes.py` (200+ lines)

**Action:**
Rewrite user activity tracking tests to target actual endpoints:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.user_activity_routes import router
from core.activity_service import ActivityService

# Tests to implement:
# 1. Test POST /activity/log - 200 status, activity logged
# 2. Test POST /activity/log - 400 for invalid activity type
# 3. Test GET /activity/{user_id} - 200 status, activity list
# 4. Test GET /activity/{user_id} - 404 for user not found
# 5. Test GET /activity/{user_id}/history - 200 status, activity history
# 6. Test GET /activity/{user_id}/history - 400 for invalid date range
# 7. Test GET /activity/{user_id}/analytics - 200 status, analytics data
# 8. Test GET /activity/{user_id}/analytics - 404 for no analytics data
# 9. Test GET /activity/session/{session_id} - 200 status, session activities
# 10. Test GET /activity/session/{session_id} - 404 for session not found
```

**Coverage Targets:**
- Activity logging (POST /activity/log)
- Activity retrieval (GET /activity/{user_id})
- Activity history (GET /activity/{user_id}/history)
- Activity analytics (GET /activity/{user_id}/analytics)
- Session tracking (GET /activity/session/{session_id})
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_user_activity_routes.py -v --cov=api/user_activity_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 200+ lines of tests rewritten
- 50%+ coverage achieved
- All tests passing

### Task 5: Run test suite and document coverage

**Action:**
Run all three rewritten test files and document coverage statistics:

```bash
source venv/bin/activate && python -m pytest \
  tests/api/test_auth_routes.py \
  tests/api/test_token_routes.py \
  tests/api/test_user_activity_routes.py \
  -v \
  --cov=api/auth_routes \
  --cov=api/token_routes \
  --cov=api/user_activity_routes \
  --cov-report=term-missing \
  --cov-report=html:tests/coverage_reports/html
```

**Verify:**
```bash
# Check coverage output:
# auth_routes.py: 50%+
# token_routes.py: 50%+
# user_activity_routes.py: 50%+
```

**Done:**
- All tests passing
- Coverage targets met (50%+ each file)
- Test execution statistics documented in plan summary

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_auth_routes.py | auth_routes.py | Auth endpoint coverage | 50%+ |
| test_token_routes.py | token_routes.py | Token endpoint coverage | 50%+ |
| test_user_activity_routes.py | user_activity_routes.py | Activity tracking coverage | 50%+ |

## Progress Tracking

**Starting Coverage (Phase 9.1):** 24.26%
**Target Coverage (Plan 39):** 25.26-26.76% (+1.0-1.5%)
**Actual Coverage:** Documented in summary after execution

## Notes

- Wave 1 plan (no dependencies)
- Critical bug fix: Authentication tests targeted wrong endpoints
- Must verify actual API endpoints before writing tests
- FastAPI TestClient with dependency overrides for realistic testing
- Avoid service-level mocking that prevents code coverage

**Estimated Duration:** 90 minutes
