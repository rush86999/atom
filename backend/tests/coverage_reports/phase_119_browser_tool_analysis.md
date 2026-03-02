# Phase 119 Coverage Analysis: Browser Tool

**Generated:** 2026-03-02T05:56:01Z
**File:** tools/browser_tool.py (819 lines)
**Baseline:** 57% coverage
**Target:** 60%+ coverage

## Summary
- **Current Coverage:** 57%
- **Target Coverage:** 60%
- **Coverage Gap:** 3%
- **Total Missing Lines:** 130
- **Status:** ⚠️ BELOW TARGET (needs 3 more percentage points)

## Functions to Cover

### BrowserSession.start (lines 71-98)
**Purpose:** Start the browser session with Playwright
**Complexity:** Medium - Browser launch, context creation
**Current Coverage:** 0%
**Missing lines:** 14 (73-85, 91-98)
**Tests needed:**
  - Chromium browser launch (default)
  - Firefox browser type selection
  - WebKit browser type selection
  - Headless vs non-headless mode
  - Error handling on launch failure
  - SlowMo and devtools options
  - Browser context creation

### BrowserSession.close (lines 100-117)
**Purpose:** Close browser and cleanup resources
**Complexity:** Low
**Current Coverage:** 0%
**Missing lines:** 14 (102-117)
**Tests needed:**
  - Successful closure
  - Error handling during cleanup
  - Browser close failure
  - Page close failure

### BrowserSessionManager (lines 120-180)
**Purpose:** Manage active sessions with timeout
**Complexity:** Low-Medium
**Current Coverage:** 96%
**Missing lines:** 1 (164)
**Tests needed:**
  - Session close error handling (1 line)
  - Note: Already excellent coverage

### browser_create_session (lines 196-308)
**Purpose:** Create session with governance integration
**Complexity:** High - Governance, agent execution tracking
**Current Coverage:** 67%
**Missing lines:** 14 (259, 290-305)
**Tests needed:**
  - Governance check error path (line 259)
  - Agent execution tracking error handling (lines 290-305)
  - Rollback on session creation failure

### browser_navigate (lines 311-372)
**Purpose:** Navigate to URL
**Complexity:** Low-Medium
**Current Coverage:** 33%
**Missing lines:** 10 (346-369)
**Tests needed:**
  - Session not found handling
  - Wrong user ownership rejection
  - Different wait_until options (load, domcontentloaded, networkidle)
  - Navigation timeout handling
  - Page.goto error handling

### browser_screenshot (lines 375-446)
**Purpose:** Capture screenshot
**Complexity:** Medium
**Current Coverage:** 48%
**Missing lines:** 11 (395, 401, 420-426, 441-443)
**Tests needed:**
  - Screenshot capture error path (line 395)
  - Base64 encoding error (line 401)
  - File path save error handling (lines 420-426)
  - Full page vs viewport
  - Screenshot type parameter

### browser_fill_form (lines 449-542)
**Purpose:** Fill form fields
**Complexity:** Medium-High - Multiple input types
**Current Coverage:** 44%
**Missing lines:** 24 (469, 475, 496-503, 516-531, 537-539)
**Tests needed:**
  - Element not found error (line 469)
  - Form submission error (line 475)
  - INPUT field fill errors (lines 496-503)
  - TEXTAREA fill errors (lines 516-531)
  - SELECT option errors (lines 537-539)
  - Unsupported element handling
  - Partial fill failure handling

### browser_click (lines 545-606)
**Purpose:** Click element
**Complexity:** Low-Medium
**Current Coverage:** 53%
**Missing lines:** 9 (565, 571, 587-590, 601-603)
**Tests needed:**
  - Click execution error (line 565)
  - Timeout error (line 571)
  - Wait for selector error (lines 587-590)
  - Session manager cleanup errors (lines 601-603)

### browser_extract_text (lines 609-664)
**Purpose:** Extract page/element text
**Complexity:** Low
**Current Coverage:** 53%
**Missing lines:** 8 (627, 633, 641-643, 659-661)
**Tests needed:**
  - Element query error (line 627)
  - Text content extraction error (line 633)
  - Inner text error (lines 641-643)
  - Multiple elements concatenation (lines 659-661)

### browser_execute_script (lines 667-715)
**Purpose:** Execute JavaScript
**Complexity:** Low
**Current Coverage:** 62%
**Missing lines:** 5 (685, 691, 710-712)
**Tests needed:**
  - Navigation error (line 685)
  - Page not loaded error (line 691)
  - Script execution errors (lines 710-712)

### browser_close_session (lines 718-765)
**Purpose:** Close browser session
**Complexity:** Low
**Current Coverage:** 57%
**Missing lines:** 6 (734, 740, 755-762)
**Tests needed:**
  - Session retrieval error (line 734)
  - Session not found (line 740)
  - Browser close errors (lines 755-762)

### browser_get_page_info (lines 768-818)
**Purpose:** Get page metadata
**Complexity:** Low
**Current Coverage:** 0%
**Missing lines:** 14 (782-815)
**Tests needed:**
  - Title and URL retrieval
  - Cookie count
  - Error handling
  - Session validation

## Gap-Filling Priority

### Priority 1: Zero-Coverage Functions (Highest Impact)
1. **BrowserSession.start** - 0% coverage, 14 missing lines
   - Test browser launch variations (chromium, firefox, webkit)
   - Test headless vs non-headless
   - Test launch error handling
   - **Impact:** ~5% coverage increase

2. **BrowserSession.close** - 0% coverage, 14 missing lines
   - Test browser closure
   - Test cleanup error handling
   - **Impact:** ~5% coverage increase

3. **browser_get_page_info** - 0% coverage, 14 missing lines
   - Test title, URL, cookie count
   - Test error handling
   - **Impact:** ~5% coverage increase

**Total Priority 1 Impact:** ~15% coverage increase (57% → 72%)

### Priority 2: Low-Coverage Core Functions (Medium Impact)
1. **browser_fill_form** - 44% coverage, 24 missing lines
   - Test element not found errors
   - Test form submission errors
   - Test TEXTAREA and SELECT handling
   - **Impact:** ~8% coverage increase

2. **browser_navigate** - 33% coverage, 10 missing lines
   - Test session not found
   - Test wrong user ownership
   - Test wait_until variations
   - **Impact:** ~3% coverage increase

**Total Priority 2 Impact:** ~11% coverage increase (57% → 68%)

### Priority 3: Moderate-Coverage Functions (Lower Priority)
1. **browser_screenshot** - 48% coverage, 11 missing lines
   - Test screenshot capture errors
   - Test file save errors
   - **Impact:** ~4% coverage increase

2. **browser_click** - 53% coverage, 9 missing lines
   - Test click errors
   - Test timeout handling
   - **Impact:** ~3% coverage increase

3. **browser_extract_text** - 53% coverage, 8 missing lines
   - Test extraction errors
   - **Impact:** ~3% coverage increase

**Total Priority 3 Impact:** ~10% coverage increase (57% → 67%)

### Priority 4: High-Coverage Functions (Lowest Priority)
1. **browser_create_session** - 67% coverage, 14 missing lines
2. **browser_execute_script** - 62% coverage, 5 missing lines
3. **browser_close_session** - 57% coverage, 6 missing lines

## Test Strategy for Plan 03

### Target: Reach 60% coverage (3 percentage point increase)
**Strategy:** Focus on Priority 1 only - zero-coverage functions

### Minimum Tests to Reach 60% (3-4 tests)
1. **test_browser_session_start_chromium** - Test Chromium browser launch
2. **test_browser_session_close** - Test browser closure
3. **test_browser_get_page_info** - Test page info extraction
4. **test_browser_session_start_firefox** - Test Firefox browser type

**Estimated Impact:** +12-15% coverage (57% → 69-72%)

### Additional Tests for 70%+ (5-8 tests)
Add to above:
5. **test_browser_fill_form_errors** - Test element not found, form errors
6. **test_browser_navigate_wait_until** - Test wait_until variations
7. **test_browser_navigate_session_not_found** - Test session error handling
8. **test_browser_screenshot_errors** - Test screenshot capture errors

**Estimated Impact:** +20-25% coverage (57% → 77-82%)

## Estimated Tests Needed

### To Reach 60% Target (Minimum)
- **Priority 1 only:** 3-4 tests (~12-15 lines coverage)
- **Target:** 60-62% coverage
- **Duration:** 20-30 minutes

### To Reach 70% (Recommended)
- **Priority 1 + 2:** 6-8 tests (~20-25 lines coverage)
- **Target:** 70-75% coverage
- **Duration:** 40-50 minutes

### To Reach 80% (Stretch Goal)
- **Priority 1 + 2 + 3:** 10-12 tests (~30-35 lines coverage)
- **Target:** 80-85% coverage
- **Duration:** 60-80 minutes

## Test Implementation Notes

### BrowserSession.start Tests
- Use AsyncMock for playwright.async_api.async_playwright
- Test browser_type parameter (chromium, firefox, webkit)
- Test headless parameter
- Test slow_mo and devtools parameters
- Test launch failure error handling
- Mock Browser object and Page object

### BrowserSession.close Tests
- Mock browser.close() and page.close()
- Test successful closure
- Test exception handling during close
- Verify cleanup happens even on errors

### browser_get_page_info Tests
- Mock session.get_page_info()
- Test successful info retrieval
- Test session not found error
- Test page info extraction (title, url, cookies)

### browser_fill_form Error Tests
- Mock page.query_selector() returning None
- Test element not found error
- Test form submission errors
- Test TEXTAREA and SELECT errors

### browser_navigate Error Tests
- Mock session_manager.get_session() returning None
- Test session not found error
- Test wrong user ownership rejection
- Test page.goto() timeout

## Key Insights

1. **Zero-coverage functions offer highest ROI** - BrowserSession.start, BrowserSession.close, browser_get_page_info are completely untested
2. **3-4 focused tests can reach 60% target** - Focus on Priority 1 functions only
3. **browser_fill_form has most missing lines** - 24 missing lines but complex to test
4. **Error paths are primary gap** - Most missing lines are error handling paths
5. **BrowserSessionManager already excellent** - 96% coverage, minimal work needed

## Recommendation

**Start with Priority 1 functions** (BrowserSession.start, BrowserSession.close, browser_get_page_info):
- 3-4 tests
- 20-30 minutes work
- 12-15% coverage increase
- **Reaches 60% target comfortably**

If time permits, add Priority 2 tests for 70%+ coverage.
