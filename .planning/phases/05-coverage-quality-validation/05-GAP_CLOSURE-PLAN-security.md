---
phase: 05-coverage-quality-validation
plan: GAP_CLOSURE-02
subsystem: security-testing
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/security/test_auth_endpoints.py
  - backend/tests/unit/security/test_auth_helpers.py
  - backend/tests/unit/security/test_jwt_validation.py
  - backend/api/auth_routes.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Security domain achieves 80% coverage (all services >80%)"
    - "Auth endpoint tests pass with correct route paths"
    - "Database token cleanup tests pass without transaction errors"
    - "Async token refresher tests pass with proper async mocking"
  artifacts:
    - path: "backend/tests/unit/security/test_auth_endpoints.py"
      provides: "Auth endpoint tests with correct routes"
      min_tests_passing: 25
    - path: "backend/tests/unit/security/test_auth_helpers.py"
      provides: "Auth helpers tests >80% coverage"
      min_tests_passing: 32
    - path: "backend/tests/unit/security/test_jwt_validation.py"
      provides: "JWT validation tests >80% coverage"
      min_tests_passing: 30
    - path: "backend/tests/unit/security/conftest.py"
      provides: "Database fixtures with RevokedToken, ActiveToken models"
      contains: "RevokedToken, ActiveToken in model imports"
  key_links:
    - from: "backend/tests/unit/security/test_auth_endpoints.py"
      to: "backend/api/auth_routes.py"
      via: "correct route path matching"
      pattern: "/api/auth/mobile/login|/api/auth/mobile/biometric/register"
    - from: "backend/tests/unit/security/test_auth_helpers.py"
      to: "backend/core/auth_helpers.py"
      via: "token cleanup with proper transaction handling"
      pattern: "db_session\\.query\\(RevokedToken\\)"
---

<objective>
Fix security domain test failures related to missing endpoints, incorrect route paths, database token cleanup, and async token refresher mocking to achieve 80% coverage.

**Purpose:** Security domain currently ranges from 0-91% coverage. validation_service.py is at 78.62% (1.38% gap), security.py at 91% (exceeds), but auth_helpers.py at 60%, auth.py at ~70%, and auth_routes.py at 0%. Main issues: 21/32 auth endpoint tests failing due to incorrect route paths, 4 token cleanup tests failing due to database issues, and 3 async token refresher tests failing.

**Output:** Fixed test files with correct route paths, working token cleanup tests, passing async refresher tests, and coverage at 80%+ for all security services.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/phases/05-coverage-quality-validation/05-02-SUMMARY.md
@.planning/phases/05-coverage-quality-validation/05-VERIFICATION.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@backend/api/auth_routes.py
@backend/core/auth_helpers.py
@backend/core/auth.py
@backend/tests/unit/security/test_auth_endpoints.py
@backend/tests/unit/security/test_auth_helpers.py
@backend/tests/unit/security/test_jwt_validation.py
</context>

<tasks>

<task type="auto">
  <name>Fix auth endpoint tests with correct route paths</name>
  <files>backend/tests/unit/security/test_auth_endpoints.py backend/api/auth_routes.py</files>
  <action>
    STEP 1: Verify actual routes in auth_routes.py
    Run: grep -n "@router\." backend/api/auth_routes.py
    ACTUAL ROUTES (verified 2026-02-11):
    - POST /api/auth/mobile/login (line 97)
    - POST /api/auth/mobile/biometric/register (line 155)
    - POST /api/auth/mobile/biometric/authenticate (line 215)
    - POST /api/auth/mobile/refresh (line 296)
    - GET /api/auth/mobile/device (line 358)
    - DELETE /api/auth/mobile/device (line 400)

    NON-EXISTENT ROUTES (tests expect but aren't in auth_routes.py):
    - /api/auth/register - NOT FOUND
    - /api/auth/login - NOT FOUND (only /api/auth/mobile/login exists)
    - /api/auth/logout - NOT FOUND
    - /api/auth/refresh - NOT FOUND (only /api/auth/mobile/refresh exists)

    STEP 2: Fix test file
    Current tests are failing because they expect routes that don't exist.

    For each failing test:
    1. test_signup_with_valid_email_password: /api/auth/register doesn't exist - REMOVE TEST (no equivalent endpoint)
    2. test_login_with_valid_credentials: /api/auth/login doesn't exist - UPDATE to /api/auth/mobile/login
    3. test_logout_with_valid_token: /api/auth/logout doesn't exist - REMOVE TEST (no equivalent endpoint)
    4. test_token_refresh_with_valid_token: UPDATE to /api/auth/mobile/refresh
    5. test_password_reset_request: Check if endpoint exists - LIKELY REMOVE (no password reset in mobile auth)

    Keep passing tests as-is (11/32 currently passing).

    STEP 3: Document removed tests
    Add comment in test file explaining why tests were removed (routes don't exist in implementation).
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/unit/security/test_auth_endpoints.py -v --tb=short

    Expected: At least 25/32 tests passing (up from 11/32) - after removing/updating non-existent route tests
  </verify>
  <done>
    Auth endpoint tests route paths match actual implementation. Pass rate increases from 34% to 78%+.
  </done>
</task>

<task type="auto">
  <name>Fix database token cleanup tests in auth_helpers</name>
  <files>backend/tests/unit/security/conftest.py backend/tests/unit/security/test_auth_helpers.py</files>
  <action>
    The token cleanup tests are failing because RevokedToken and ActiveToken models are not being properly registered with Base.metadata.create_all().

    Fix in conftest.py:
    1. Add RevokedToken and ActiveToken to the model imports (lines 3525-3596 in core/models.py)
    2. Ensure they're imported before Base.metadata.create_all()

    Update test_auth_helpers.py:
    1. For tests that fail with "no such table" errors, ensure they use the db_session fixture properly
    2. Wrap token cleanup operations in proper database transactions
    3. Add db_session.commit() calls after creating RevokedToken/ActiveToken instances

    Specific tests to fix (failing due to database issues):
    - test_token_cleanup_removes_expired_tokens
    - test_token_cleanup_preserves_valid_tokens
    - test_token_revoke_all_for_user
    - test_active_token_tracking

    Also add edge case tests to reach 80% coverage:
    - Test token cleanup with empty database
    - Test token cleanup with revoked tokens from multiple users
    - Test active token limit enforcement
    - Test token cleanup with malformed token data
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/unit/security/test_auth_helpers.py -v --cov=core/auth_helpers --cov-report=term-missing

    Expected: At least 32/36 tests passing (up from 27/36), coverage >80%
  </verify>
  <done>
    Token cleanup tests pass. auth_helpers.py coverage increases from 59.76% to 80%+.
  </done>
</task>

<task type="auto">
  <name>Fix async token refresher tests with proper async mocking</name>
  <files>backend/tests/unit/security/test_jwt_validation.py</files>
  <action>
    The token refresher tests are failing because TokenRefresher service uses async functions that aren't properly mocked.

    Fix the async mocking:
    1. Use pytest.mark.asyncio decorator for async test methods
    2. Use AsyncMock from unittest.mock for async function mocking
    3. Properly await async calls in tests

    Pattern to use:
    ```python
    from unittest.mock import AsyncMock, patch

    @pytest.mark.asyncio
    async def test_token_refresher_refreshes_token():
        with patch('core.auth.TokenRefresher.refresh', new_callable=AsyncMock) as mock_refresh:
            mock_refresh.return_value = "new_token"
            # test code
            result = await some_async_function()
            assert result == "expected"
    ```

    Fix these failing tests:
    - test_mobile_token_creation_with_device_id
    - test_token_refresher_refreshes_oauth_token
    - test_token_refresher_handles_expiration

    Also add edge case tests to reach 80% coverage:
    - Test token refresh with network errors
    - Test token refresh with expired refresh token
    - Test token refresh with invalid client credentials
  </action>
  <verify>
    Run: cd backend && PYTHONPATH=. python -m pytest tests/unit/security/test_jwt_validation.py -v --cov=core/auth --cov-report=term-missing

    Expected: At least 30/33 tests passing (up from 22/33), coverage >80%
  </verify>
  <done>
    Async token refresher tests pass. auth.py coverage increases from ~70% to 80%+.
  </done>
</task>

</tasks>

<verification>
Overall verification steps:
1. Run all security tests: pytest tests/unit/security/ -v --cov=core --cov=api --cov-report=term
2. Verify security domain coverage exceeds 80%:
   - validation_service: 80%+ (from 78.62%)
   - auth_helpers: 80%+ (from 59.76%)
   - auth.py (JWT functions): 80%+ (from ~70%)
   - security.py: 90%+ (already exceeded)
3. Verify no database-related test failures remain
4. Verify auth route tests use correct endpoint paths
</verification>

<success_criteria>
Security domain achieves 80% average coverage across all services:
- test_auth_endpoints.py: 25+/32 tests passing (from 11/32)
- test_auth_helpers.py: 32+/36 tests passing (from 27/36), coverage 80%+
- test_jwt_validation.py: 30+/33 tests passing (from 22/33), auth.py coverage 80%+
- validation_service: 80%+ coverage (from 78.62%)
- All database token cleanup tests pass
- All async token refresher tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-GAP_CLOSURE-02-SUMMARY.md`
</output>
