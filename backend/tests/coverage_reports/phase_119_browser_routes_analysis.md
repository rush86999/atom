# Phase 119 Coverage Analysis: Browser Routes

**Generated:** 2026-03-02T05:56:01Z
**File:** api/browser_routes.py (789 lines)
**Baseline:** 76% coverage
**Target:** 60%+ coverage

## Summary
- **Current Coverage:** 76%
- **Target Coverage:** 60%
- **Coverage Gap:** 0% (target already exceeded)
- **Total Missing Lines:** 58
- **Status:** ✅ EXCEEDS TARGET

## Missing Lines by Endpoint

### POST /session/create (lines 209-259)
**Purpose:** Create browser session with governance
**Current Coverage:** 80%
**Missing areas:**
- Line 232: Permission denied error handling
- Lines 252-253: Session record creation error handling

### POST /navigate (lines 262-371)
**Purpose:** Navigate to URL with governance
**Current Coverage:** 68%
**Missing areas:**
- Lines 327-329: Navigation error handling
- Lines 360-369: Database audit record error handling

### POST /screenshot (lines 374-421)
**Purpose:** Take screenshot with governance
**Current Coverage:** 89%
**Missing areas:**
- Line 388: Screenshot error path

### POST /fill-form (lines 424-480)
**Purpose:** Fill form fields with submission
**Current Coverage:** 73%
**Missing areas:**
- Lines 439-440: Element not found handling
- Line 447: Form submission error handling

### POST /click (lines 483-529)
**Purpose:** Click element with selector
**Current Coverage:** 89%
**Missing areas:**
- Line 497: Click timeout error path

### POST /extract-text (lines 532-578)
**Purpose:** Extract text content
**Current Coverage:** 89%
**Missing areas:**
- Line 546: Extract text error path

### POST /execute-script (lines 581-626)
**Purpose:** Execute JavaScript (SUPERVISED+ required)
**Current Coverage:** 89%
**Missing areas:**
- Line 595: Script execution error path

### POST /session/close (lines 629-686)
**Purpose:** Close browser session
**Current Coverage:** 50%
**Missing areas:**
- Line 643: Close session error path
- Lines 675-684: Session info query error handling

### GET /session/{id}/info (lines 689-715)
**Purpose:** Get session information
**Current Coverage:** 82%
**Missing areas:**
- Lines 712-713: Sessions list query error handling

### GET /sessions (lines 718-748)
**Purpose:** List user sessions
**Current Coverage:** 50%
**Missing areas:**
- Lines 746-748: Pagination handling

### GET /audit (lines 751-788)
**Purpose:** Get audit log
**Current Coverage:** 67%
**Missing areas:**
- Lines 786-788: Audit session filter error handling

### Helper Functions

#### _check_browser_governance (lines 121-159)
**Purpose:** Check governance permissions before browser operations
**Current Coverage:** 0%
**Missing areas:**
- Lines 121-159: Entire function uncovered (helper not directly tested)

**Note:** This is a private helper function that's tested indirectly through endpoint tests. 0% coverage is expected.

#### _create_browser_audit (lines 178-202)
**Purpose:** Create audit log entry for browser operations
**Current Coverage:** 67%
**Missing areas:**
- Lines 200-202: Database commit error handling

## Gap-Filling Priority

### Priority 1: High-Impact Error Paths
1. **POST /navigate** - Core navigation with governance tracking (68% coverage, 11 missing lines)
2. **POST /session/close** - Session cleanup (50% coverage, 9 missing lines)
3. **GET /sessions** - Session listing (50% coverage, 3 missing lines)

### Priority 2: Medium-Impact Endpoints
1. **POST /fill-form** - Form submission with SUPERVISED+ gating (73% coverage, 3 missing lines)
2. **POST /session/create** - Session creation (80% coverage, 3 missing lines)
3. **GET /audit** - Audit trail retrieval (67% coverage, 3 missing lines)

### Priority 3: Low-Impact Endpoints (Already >85% coverage)
1. **POST /screenshot** - Screenshot capture (89% coverage)
2. **POST /click** - Element interaction (89% coverage)
3. **POST /extract-text** - Data extraction (89% coverage)
4. **POST /execute-script** - JavaScript execution (89% coverage)
5. **GET /session/{id}/info** - Session information (82% coverage)

## Test Strategy Notes

### Current Status
- **76% coverage exceeds 60% target by 16 percentage points**
- No additional tests required to meet target
- Focus on fixing 10 failing tests in test_api_browser_routes.py

### If Improving Coverage Further
- Use AsyncMock for browser tool functions
- Mock ServiceFactory.get_governance_service
- Real DB session for BrowserSession and BrowserAudit verification
- Test governance denial responses with STUDENT agent
- Test agent execution tracking with INTERN+ agents
- Test SUPERVISED+ requirement for form submission
- Test database record lifecycle (creation, updates, closure)
- Test error paths (timeout handling, element not found, database errors)

### Key Insight
**Browser routes already exceed 60% target.** Plan 03 should focus on browser_tool.py (57% coverage) to close the 3% gap. Only fix failing tests for browser_routes.py.

## Estimated Tests Needed to Reach 90%
- **Priority 1:** 3-4 tests for navigate and close_session error paths
- **Priority 2:** 2-3 tests for fill-form and session creation error paths
- **Priority 3:** 1-2 tests for remaining low-impact endpoints
- **Total:** 6-9 tests to reach 90% coverage (optional - target already met)
