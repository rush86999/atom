---
phase: 09-1-api-route-governance-resolution
plan: 36
type: execute
wave: 1
depends_on: []
files_modified:
  - api/auth_routes.py
  - api/token_routes.py
  - api/user_activity_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "auth_routes.py tested with 50%+ coverage (177 lines → ~89 lines covered)"
    - "token_routes.py tested with 50%+ coverage (64 lines → ~32 lines covered)"
    - "user_activity_routes.py tested with 50%+ coverage (127 lines → ~64 lines covered)"
    - "All tests passing (no blockers)"
    - "Authentication flow tests documented"
  artifacts:
    - path: "tests/api/test_auth_routes.py"
      provides: "Authentication route tests"
      min_lines: 250
    - path: "tests/api/test_token_routes.py"
      provides: "Token route tests"
      min_lines: 150
    - path: "tests/api/test_user_activity_routes.py"
      provides: "User activity route tests"
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
status: complete
created: 2026-02-14
completed: 2026-02-14
gap_closure: false
---

# Plan 36: Authentication & Token Management Routes

**Status:** Pending
**Wave:** 1
**Dependencies:** None

## Objective

Create comprehensive tests for authentication, token management, and user activity tracking routes to achieve 50%+ coverage across all three files.

## Context

Phase 9.1 targets 27-29% overall coverage (+5-7% from 22.15% baseline) by testing zero-coverage API routes.

**Files in this plan:**

1. **api/auth_routes.py** (177 lines, 0% coverage)
   - User authentication endpoints (signup, login, logout)
   - Session management
   - Password reset and recovery

2. **api/token_routes.py** (64 lines, 0% coverage)
   - JWT token refresh and validation
   - Token revocation and blacklisting
   - Token expiration handling

3. **api/user_activity_routes.py** (127 lines, 0% coverage)
   - User activity tracking and logging
   - Activity history and analytics
   - Session activity monitoring

**Total Production Lines:** 368
**Expected Coverage at 50%:** ~184 lines
**Target Coverage Contribution:** +1.5-2.0% overall

## Success Criteria

**Must Have (truths that become verifiable):**
1. auth_routes.py tested with 50%+ coverage (177 lines → ~89 lines covered)
2. token_routes.py tested with 50%+ coverage (64 lines → ~32 lines covered)
3. user_activity_routes.py tested with 50%+ coverage (127 lines → ~64 lines covered)
4. All tests passing (no blockers)
5. Authentication flow tests documented

**Should Have:**
- Security tests (password hashing, JWT validation)
- Session management tests (create, update, delete sessions)
- Activity tracking tests (log, retrieve, analyze activities)

**Could Have:**
- Rate limiting tests (max login attempts)
- Token refresh timing tests
- Activity aggregation tests (daily, weekly summaries)

**Won't Have:**
- Integration tests with real OAuth providers
- End-to-end authentication workflow tests
- Real-time activity streaming tests

## Tasks

### Task 1: Create test_auth_routes.py

**File:** CREATE: `tests/api/test_auth_routes.py` (250+ lines)

**Action:**
Create comprehensive tests for authentication routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
from api.auth_routes import router
from core.auth_service import AuthService

# Tests to implement:
# 1. Test POST /auth/signup - 201 status, user created
# 2. Test POST /auth/signup - 400 for duplicate email
# 3. Test POST /auth/signup - 400 for weak password
# 4. Test POST /auth/login - 200 status, JWT token returned
# 5. Test POST /auth/login - 401 for invalid credentials
# 6. Test POST /auth/logout - 200 status, session terminated
# 7. Test POST /auth/logout - 401 for no active session
# 8. Test POST /auth/refresh - 200 status, new JWT token
# 9. Test POST /auth/refresh - 401 for invalid token
# 10. Test POST /auth/reset-password - 200 status, reset email sent
# 11. Test POST /auth/reset-password - 404 for non-existent email
# 12. Test PUT /auth/reset-password/{token} - 200 status, password updated
# 13. Test PUT /auth/reset-password/{token} - 400 for expired token
# 14. Test GET /auth/session - 200 status, session details
# 15. Test GET /auth/session - 401 for no active session
```

**Coverage Targets:**
- User signup (POST /auth/signup)
- User login (POST /auth/login)
- User logout (POST /auth/logout)
- Token refresh (POST /auth/refresh)
- Password reset (POST /auth/reset-password, PUT /auth/reset-password/{token})
- Session management (GET /auth/session)
- Error handling (400, 401, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_auth_routes.py -v --cov=api/auth_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 250+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 2: Create test_token_routes.py

**File:** CREATE: `tests/api/test_token_routes.py` (150+ lines)

**Action:**
Create comprehensive tests for token management routes:

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
- 150+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 3: Create test_user_activity_routes.py

**File:** CREATE: `tests/api/test_user_activity_routes.py` (200+ lines)

**Action:**
Create comprehensive tests for user activity tracking routes:

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
- 200+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 4: Run test suite and document coverage

**Action:**
Run all three test files and document coverage statistics:

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
- Authentication flow tests documented in plan summary

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_auth_routes.py | auth_routes.py | Auth endpoint coverage | 50%+ |
| test_token_routes.py | token_routes.py | Token endpoint coverage | 50%+ |
| test_user_activity_routes.py | user_activity_routes.py | Activity tracking coverage | 50%+ |

## Progress Tracking

**Starting Coverage:** 22.15%
**Target Coverage (Plan 36):** 23.65-24.15% (+1.5-2.0%)
**Actual Coverage:** Documented in summary after execution

## Notes

- Wave 1 plan (no dependencies)
- Focus on authentication, token management, and user activity tracking
- Security tests (password hashing, JWT validation) critical for auth routes
- Token lifecycle tests (create, validate, revoke, expire)
- Activity tracking tests (log, retrieve, analyze)
- Error handling tests (400, 401, 404, 500) essential for robust coverage

**Estimated Duration:** 90 minutes
