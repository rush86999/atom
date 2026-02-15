---
phase: 08-80-percent-coverage-push
plan: 42
type: execute
wave: 2
depends_on: []
files_modified:
  - api/browser_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "browser_routes.py tested with 50%+ coverage (228 lines → ~114 lines covered)"
    - "All tests passing (no blockers)"
    - "Browser automation tests documented"
  artifacts:
    - path: "tests/api/test_browser_routes.py"
      provides: "Browser automation route tests"
      min_lines: 250
  key_links:
    - from: "test_browser_routes.py"
      to: "api/browser_routes.py"
      via: "Browser endpoint coverage"
      pattern: "50%+"
status: complete
created: 2026-02-14
gap_closure: false
---

# Plan 42: Browser Automation Routes

**Status:** Pending
**Wave:** 2
**Dependencies:** None

## Objective

Create comprehensive tests for browser automation API routes to achieve 50%+ coverage.

## Context

Phase 9.2 targets 32-35% overall coverage (+28.12% from 3.9% current) by testing zero-coverage API routes.

**File in this plan:**

**api/browser_routes.py** (228 lines, 0% coverage)
   - Browser automation via CDP (Chrome DevTools Protocol)
   - Web scraping and form filling
   - Screenshots and PDF generation
   - Page navigation and interaction
   - Browser session management
   - Playwright integration for advanced workflows

**Total Production Lines:** 228
**Expected Coverage at 50%:** ~114 lines
**Target Coverage Contribution:** +0.2-0.3% overall

## Success Criteria

**Must Have (truths that become verifiable):**
1. browser_routes.py tested with 50%+ coverage (228 lines → ~114 lines covered)
2. All tests passing (no blockers)
3. Browser automation tests documented

**Should Have:**
- CDP command tests (navigate, screenshot, execute script)
- Form filling tests (input fields, dropdowns, checkboxes)
- Screenshot generation tests (full page, element, viewport)
- PDF generation tests
- Session management tests (create, update, delete, list)

**Could Have:**
- Playwright workflow tests (multi-step browser automation)
- Performance tests (page load times, interaction latency)
- Cross-browser testing (Chrome, Firefox, Safari)

**Won't Have:**
- Integration tests with real browser instances
- End-to-end workflow execution tests (CDP → screenshot → PDF)
- Real-time browser control streaming tests

## Tasks

### Task 1: Create test_browser_routes.py

**File:** CREATE: `tests/api/test_browser_routes.py` (250+ lines)

**Action:**
Create comprehensive tests for browser automation routes:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, MagicMock
from api.browser_routes import router
from core.browser_service import BrowserService
from playwright.async_api import async_playwright

# Tests to implement:
# 1. Test POST /browser/session - 200 status, session created
# 2. Test POST /browser/session - 400 for invalid browser type
# 3. Test POST /browser/session/navigate - 200 status, navigated to URL
# 4. Test POST /browser/session/screenshot - 200 status, screenshot captured
# 5. Test POST /browser/session/screenshot - 400 for invalid session ID
# 6. Test POST /browser/session/execute - 200 status, script executed
# 7. Test POST /browser/session/execute - 400 for invalid script
# 8. Test POST /browser/session/pdf - 200 status, PDF generated
# 9. Test POST /browser/session/pdf - 400 for invalid session ID
# 10. Test GET /browser/session/{session_id} - 200 status, session details
# 11. Test GET /browser/session/{session_id} - 404 for session not found
# 12. Test PUT /browser/session/{session_id} - 200 status, session updated
# 13. Test PUT /browser/session/{session_id} - 404 for session not found
# 14. Test DELETE /browser/session/{session_id} - 200 status, session deleted
# 15. Test DELETE /browser/session/{session_id} - 404 for session not found
# 16. Test GET /browser/sessions - 200 status, list of sessions
```

**Coverage Targets:**
- Session creation (POST /browser/session)
- Navigation (POST /browser/session/navigate)
- Screenshots (POST /browser/session/screenshot)
- Script execution (POST /browser/session/execute)
- PDF generation (POST /browser/session/pdf)
- Session management (GET /browser/session/{session_id}, PUT /browser/session/{session_id}, DELETE /browser/session/{session_id})
- Session listing (GET /browser/sessions)
- Error handling (400, 404, 500)

**Verify:**
```bash
source venv/bin/activate && python -m pytest tests/api/test_browser_routes.py -v --cov=api/browser_routes --cov-report=term-missing
# Expected: 50%+ coverage
```

**Done:**
- 250+ lines of tests created
- 50%+ coverage achieved
- All tests passing

### Task 2: Run test suite and document coverage

**Action:**
Run test file and document coverage statistics:

```bash
source venv/bin/activate && python -m pytest \
  tests/api/test_browser_routes.py \
  -v \
  --cov=api/browser_routes \
  --cov-report=term-missing \
  --cov-report=html:tests/coverage_reports/html
```

**Verify:**
```bash
# Check coverage output:
# browser_routes.py: 50%+
```

**Done:**
- All tests passing
- Coverage target met (50%+)
- Test execution statistics documented

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_browser_routes.py | browser_routes.py | Browser endpoint coverage | 50%+ |

## Progress Tracking

**Starting Coverage:** 3.9%
**Target Coverage (Plan 42):** 4.1-4.4% (+0.2-0.3%)
**Actual Coverage:** Documented in summary after execution

## Notes

- Wave 2 plan (no dependencies)
- Focus on browser automation for web scraping and form filling
- CDP (Chrome DevTools Protocol) integration
- Playwright support for advanced workflows
- Screenshot and PDF generation capabilities
- Session lifecycle management
- Error handling tests (400, 404, 500) essential

**Estimated Duration:** 60 minutes
