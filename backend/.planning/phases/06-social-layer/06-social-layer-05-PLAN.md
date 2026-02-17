---
phase: 06-social-layer
plan: 05
type: execute
wave: 2
depends_on: ["06-01", "06-02", "06-03", "06-04"]
files_modified:
  - api/social_routes.py
  - tests/api/test_social_routes_integration.py
  - main_api_app.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "All API endpoints are implemented and accessible"
    - "API integration tests achieve 80%+ pass rate (currently 18%)"
    - "Request validation works correctly for all endpoints"
    - "Response formats match test expectations"
    - "Error handling returns proper HTTP status codes"
  artifacts:
    - path: "api/social_routes.py"
      provides: "Complete REST API with all endpoints"
    - path: "tests/api/test_social_routes_integration.py"
      provides: "Fixed API integration tests (80%+ pass rate)"
    - path: "main_api_app.py"
      provides: "FastAPI app with social routes registered"
  key_links:
    - from: "tests/api/test_social_routes_integration.py"
      to: "api/social_routes.py"
      via: "API tests verify all endpoints work correctly"
      pattern: "test_get_feed|test_create_post|test_add_reaction"
---

## Objective

Fix API routes implementation and integration tests to achieve 80%+ pass rate. Implement missing endpoints, fix request/response format mismatches, and resolve collection errors.

**Purpose:** API integration is critical for social layer functionality. Currently only 18% pass rate (3/17 tests passing) due to missing endpoints, import errors, and format mismatches.

**Output:** Working API integration with 80%+ test pass rate, all endpoints implemented, proper error handling.

## Execution Context

@api/social_routes.py (REST API for social feed)
@tests/api/test_social_routes_integration.py (17 tests, 18% pass rate)
@main_api_app.py or main.py (FastAPI app entry point)
@.planning/phases/06-social-layer/06-social-layer-VERIFICATION.md (gap details)

## Context

@.planning/phases/06-social-layer/06-social-layer-02-PLAN.md (original API plan)
@.planning/phases/06-social-layer/06-social-layer-02-SUMMARY.md (implementation summary)

# Verification Gap: API Routes (Priority 3)
- 14 errors in test_social_routes_integration.py
- Missing endpoints for filtering, reactions, trending
- Request/response format mismatches
- Collection error in test_social_feed_integration.py
- Import error: tests import from main_api_app which may not exist

## Tasks

### Task 1: Fix API App Import and Route Registration

**Files:** `tests/api/test_social_routes_integration.py`, `api/social_routes.py`

**Action:**
1. Fix the import in test_social_routes_integration.py:
   - Change `from main_api_app import app` to correct import
   - Find the actual FastAPI app (likely in `main.py` or create a test app)
   - Ensure social_routes.py router is registered with the app

2. Create test fixture for FastAPI app if needed:
   ```python
   @pytest.fixture
   def client():
       """Create test client with social routes."""
       from fastapi.testclient import TestClient
       from api.social_routes import router
       from fastapi import FastAPI

       app = FastAPI()
       app.include_router(router)
       return TestClient(app)
   ```

3. Verify route registration:
   - Check that all routes are accessible
   - Verify URL parameters match test expectations
   - Ensure CORS and middleware don't block tests

Reference issue from verification:
- tests/api/test_social_routes_integration.py line 18: `from main_api_app import app` fails

**Verify:**
- `pytest tests/api/test_social_routes_integration.py::TestSocialRoutesAPI::test_get_feed -v` runs without import error
- `curl -I http://localhost:8000/api/social/feed` returns 200 or proper error

**Done:**
- Import errors resolved
- Test client fixture working
- All routes accessible

---

### Task 2: Implement Missing API Endpoints

**Files:** `api/social_routes.py`

**Action:**
1. Review test expectations and identify missing endpoints:
   - GET /api/social/feed/cursor (cursor-based pagination)
   - POST /api/social/posts/{post_id}/replies (add reply)
   - GET /api/social/posts/{post_id}/replies (get replies)
   - POST /api/social/posts/{post_id}/reactions (add reaction)
   - GET /api/social/trending (trending topics)
   - GET /api/social/channels (list channels)
   - POST /api/social/channels (create channel)

2. Verify existing endpoints match test expectations:
   - Check request parameter names (sender_id, limit, offset, cursor, etc.)
   - Check response format (posts array, total count, next_cursor, has_more)
   - Ensure error status codes match (403 for STUDENT, 400 for invalid input)

3. Add missing endpoints:
   - Implement feed/cursor endpoint if missing
   - Implement reactions endpoint with proper error handling
   - Implement trending topics endpoint
   - Ensure all endpoints return JSON responses with correct structure

Reference issue from verification:
- 14 errors indicate many endpoints missing or misaligned

**Verify:**
- All 17 tests in test_social_routes_integration.py run without 404 errors
- `pytest tests/api/test_social_routes_integration.py -v` shows 60%+ pass rate (baseline)

**Done:**
- All endpoints implemented
- Request parameters match test expectations
- Response formats match test expectations

---

### Task 3: Fix Request/Response Format and Validation

**Files:** `api/social_routes.py`, `tests/api/test_social_routes_integration.py`

**Action:**
1. Fix request validation:
   - Ensure Pydantic models accept all fields from tests
   - Fix optional fields (sender_maturity, sender_category can be None)
   - Handle missing fields gracefully with defaults

2. Fix response formats:
   - Ensure feed response has "posts", "total", "limit", "offset" keys
   - Ensure cursor response has "posts", "next_cursor", "has_more" keys
   - Ensure channels response has "channels" key with list
   - Ensure reactions response has "reactions" key with dict

3. Fix error handling:
   - Return 403 for STUDENT agents (not 401)
   - Return 400 for invalid post_type with clear error message
   - Return 404 for missing posts/replies
   - Include error details in response body

4. Fix test assertions to match actual response:
   - Update tests expecting wrong formats
   - Add leniency for timestamp formats (ISO string vs datetime)
   - Handle optional fields that may be missing

Reference issues from verification:
- test_create_post_student_forbidden expects 403
- test_invalid_post_type expects 400 with "Invalid post_type" message
- test_empty_feed expects {"posts": [], "total": 0}

**Verify:**
- `pytest tests/api/test_social_routes_integration.py -v` shows 80%+ pass rate (14+/17 tests)
- Governance tests pass (STUDENT blocked, INTERN allowed)
- Validation tests pass (invalid post_type returns 400)

**Done:**
- 80%+ test pass rate achieved
- Request validation works correctly
- Response formats match expectations
- Error handling returns proper status codes

---

## Deviations

**Rule 1 (App Location):** If main.py doesn't exist or doesn't export app, create a test-only app fixture.

**Rule 2 (Response Format):** If tests expect wrong format, prefer fixing tests to match API contract, not vice versa.

**Rule 3 (Backward Compatibility):** All API changes must maintain backward compatibility with existing clients.

## Success Criteria

- [ ] API integration tests achieve 80%+ pass rate (14+/17 tests)
- [ ] All endpoints accessible (no 404 errors)
- [ ] Request validation works (invalid inputs return 400)
- [ ] Governance gates work (STUDENT blocked, INTERN+ allowed)
- [ ] Response formats match test expectations
- [ ] Error handling returns proper status codes
- [ ] Import errors resolved

## Dependencies

- Plan 06-03 (PII Redaction Fixes) must be complete
- Plan 06-04 (Feed Management Fixes) must be complete

## Estimated Duration

2-3 hours (import fixes + missing endpoints + format fixes)
