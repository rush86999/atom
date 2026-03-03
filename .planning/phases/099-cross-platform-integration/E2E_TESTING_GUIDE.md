# E2E Testing Guide

## Overview

Atom uses E2E (End-to-End) tests to verify complete user workflows across web, mobile, and desktop platforms. E2E tests run on merge to main (not on PRs) to avoid blocking development workflow while maintaining comprehensive quality validation.

**Architecture:**
- **Web E2E:** Playwright (Python) for browser automation
- **Mobile E2E:** API-level tests (adapted from Detox due to expo-dev-client requirement)
- **Desktop E2E:** Tauri integration tests (adapted from tauri-driver due to unavailability)
- **Aggregation:** Unified E2E report combines results from all platforms

**Execution:**
- **Unit/Integration Tests:** Run on every PR (1-2 minutes, fast feedback)
- **E2E Tests:** Run on push to main (5-15 minutes, comprehensive validation)

## Quick Start

### Web E2E Tests (Playwright)

```bash
# Install dependencies
cd backend
pip install -r requirements-testing.txt
playwright install chromium

# Run web E2E tests
pytest tests/e2e_ui/tests/ -v

# Run specific test file
pytest tests/e2e_ui/tests/cross-platform/test_shared_workflows.py -v

# Run with HTML report
pytest tests/e2e_ui/tests/ -v --html=report.html
```

**Prerequisites:**
- Python 3.11+
- PostgreSQL database running
- Backend server running on port 8000
- Frontend dev server running on port 3000

### Mobile E2E Tests (API-Level)

```bash
cd mobile

# Run mobile cross-platform API tests
npm test src/__tests__/e2e/cross-platform-api.test.ts

# Run specific test file
npm test src/__tests__/e2e/auth-api.test.ts
```

**Note:** Mobile E2E adapted to API-level tests (Plan 099-04) due to Detox requirement for expo-dev-client. Tests verify mobile supports all backend workflows.

### Desktop E2E Tests (Tauri Integration)

```bash
cd frontend-nextjs

# Run Tauri integration tests
npm run test:integration

# Or use cargo directly
cd src-tauri
cargo test --test integration
```

**Note:** Desktop E2E uses Tauri's built-in integration tests (Plan 099-05) due to tauri-driver unavailability. Tests cover IPC, window state, file operations, and system integration.

## Test Structure

### Cross-Platform Tests

All platforms test the same shared workflows to ensure feature parity:

| Workflow | Web | Mobile | Desktop |
|----------|-----|--------|---------|
| Authentication | ✅ | ✅ | ✅ |
| Agent Execution | ✅ | ✅ | ✅ |
| Canvas Presentations | ✅ | ✅ | ✅ |
| Skill Execution | ✅ | ✅ | ✅ |
| Feature Parity | ✅ | ✅ | ✅ |

**Test Parity Strategy:**
- Web: Playwright browser automation (full UI testing)
- Mobile: API contract validation (backend workflow verification)
- Desktop: Tauri integration tests (IPC + system integration)

### File Locations

- **Web:** `backend/tests/e2e_ui/tests/cross-platform/`
  - `test_shared_workflows.py` - Shared workflow tests (5 tests)
  - `test_feature_parity.py` - Feature parity tests (5 tests)
  - `visual/test_visual_regression.py` - Percy visual tests (5 pages)
- **Mobile:** `mobile/src/__tests__/e2e/`
  - `cross-platform-api.test.ts` - API contract tests (79 tests)
  - `auth-api.test.ts` - Authentication flow tests
  - `agent-api.test.ts` - Agent execution tests
- **Desktop:** `frontend-nextjs/src-tauri/tests/`
  - `integration/` - Tauri integration tests (54 tests)
  - `property_tests.rs` - Rust property tests

## CI/CD Integration

### When E2E Tests Run

- **On push to main:** All platform E2E tests run in parallel
- **On PR:** E2E tests do NOT run (only unit/integration tests run)
- **Manual trigger:** Available via `workflow_dispatch` in GitHub Actions

**Rationale:** E2E tests take 5-15 minutes vs 1-2 minutes for unit/integration tests. Running E2E on every PR would block development workflow. Instead, E2E validates after merge to main.

### Workflows

- `e2e-ui-tests.yml` - Web E2E (Playwright)
  - Runs backend + frontend servers
  - Executes Playwright tests
  - Uploads HTML report as artifact
- `e2e-mobile.yml` - Mobile E2E (API-level)
  - Runs mobile cross-platform API tests
  - Validates backend contract compliance
  - Uploads test results as artifact
- `e2e-desktop.yml` - Desktop E2E (Tauri)
  - Runs Tauri integration tests
  - Parses cargo test JSON output
  - Uploads test results as artifact
- `e2e-unified.yml` - Aggregates all platform results
  - Downloads artifacts from web, mobile, desktop
  - Runs `e2e_aggregator.py` to combine results
  - Posts summary to commit
  - Uploads unified report as artifact
- `lighthouse-ci.yml` - Performance regression tests
  - Runs Lighthouse audits on every PR
  - Enforces performance budgets
  - Comments on PR with results
- `visual-regression.yml` - Visual regression tests
  - Runs Percy screenshot tests on every PR
  - Compares against baseline
  - Comments on PR with visual diffs

### Results

E2E test results are uploaded as GitHub Actions artifacts:

- `e2e-test-report` - Web HTML report (Playwright)
- `e2e-mobile-artifacts` - Mobile test results
- `e2e-desktop-artifacts` - Desktop test results
- `e2e-unified-results` - Aggregated results (all platforms)
- `lighthouse-results` - Performance metrics
- `percy-screenshots` - Visual diffs (Percy dashboard)

### Unified E2E Report

The unified E2E report combines results from all platforms:

```json
{
  "timestamp": "2026-02-27T12:00:00Z",
  "aggregate": {
    "total": 131,
    "passed": 131,
    "failed": 0,
    "skipped": 0,
    "pass_rate": 100.0,
    "duration": 45.2
  },
  "platforms": {
    "web": {
      "total": 10,
      "passed": 10,
      "failed": 0,
      "duration": 12.5
    },
    "mobile": {
      "total": 79,
      "passed": 79,
      "failed": 0,
      "duration": 18.3
    },
    "desktop": {
      "total": 54,
      "passed": 54,
      "failed": 0,
      "duration": 14.4
    }
  }
}
```

## Writing E2E Tests

### Pattern: Shared Workflow

When adding a new shared workflow:

1. Implement on web first (Playwright)
2. Mirror on mobile (API-level)
3. Mirror on desktop (Tauri integration)
4. Update feature parity tests

**Web Example (Playwright):**

```python
# backend/tests/e2e_ui/tests/cross-platform/test_shared_workflows.py
def test_new_workflow(self, browser, authenticated_user):
    """Test new shared workflow across platforms."""
    workflow_page = SharedWorkflowPage(browser.new_page())
    workflow_page.navigate()
    workflow_page.do_action()
    assert workflow_page.is_complete()
```

**Mobile Example (API-Level):**

```typescript
// mobile/src/__tests__/e2e/workflows/newWorkflow-api.test.ts
describe('New Workflow (API)', () => {
  it('should complete new workflow', async () => {
    // Verify backend API contract
    const response = await fetch('/api/workflows/new', {
      method: 'POST',
      body: JSON.stringify({ action: 'do_action' })
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ complete: true });
  });
});
```

**Desktop Example (Tauri Integration):**

```rust
// frontend-nextjs/src-tauri/tests/integration/workflow_tests.rs
#[test]
fn test_new_workflow() {
    // Test Tauri IPC command
    let result = invoke_workflow_command("new_workflow", json!({
        "action": "do_action"
    }));
    assert_eq!(result["complete"], true);
}
```

### Selectors

Use `data-testid` attributes for selectors (resilient to CSS/class changes):

```python
# Good: Resilient
page.get_by_test_id("login-submit-button").click()

# Bad: Fragile
page.locator(".btn.btn-primary").click()
```

**Test ID Infrastructure:**
- Centralized constants: `frontend-nextjs/src/lib/testIds.ts`
- Usage: `data-testid={testIds.login.submitButton}`
- Pattern: `{feature}.{element}.{variant}`

### Page Objects

Use page object pattern for maintainable E2E tests:

```python
# backend/tests/e2e_ui/tests/pages/shared_workflow_page.py
class SharedWorkflowPage:
    def __init__(self, page):
        self.page = page

    def navigate(self):
        self.page.goto("/workflow")

    def do_action(self):
        self.page.get_by_test_id("do-action-button").click()

    def is_complete(self):
        return self.page.get_by_test_id("complete-indicator").is_visible()
```

## Performance Testing

### Lighthouse CI

Performance audits run on every PR to detect regressions:

```bash
# Run locally
cd frontend-nextjs
npm run lighthouse:collect
npm run lighthouse:assert
```

### Budgets

| Metric | Budget | Rationale |
|--------|--------|-----------|
| Performance Score | >90 | Prevents slow pages |
| First Contentful Paint | <2s | Fast initial render |
| Time to Interactive | <5s | Quick interactivity |
| Cumulative Layout Shift | <0.1 | Prevents layout shifts |
| Total Blocking Time | <300ms | Responsive main thread |
| Total Bundle Size | <500 kB | Prevents bloat |
| Individual Chunk | <200 kB | Lazy loading targets |

See `frontend-nextjs/LIGHTHOUSE.md` for detailed guide.

## Visual Regression Testing

### Percy

Percy screenshot diffing runs on every PR:

```bash
# Run locally with Percy
cd backend
percy exec -- pytest tests/e2e_ui/tests/visual/ -v
```

**Multi-Width Snapshots:**
- 1280px (Desktop)
- 768px (Tablet)
- 375px (Mobile)

**Percy CSS:** Hide dynamic content to reduce false positives:

```javascript
// frontend-nextjs/.percyrc.js
percyCSS: `
  [data-testid="timestamp"],
  [data-testid="loading-spinner"] {
    display: none !important;
  }
`
```

See `frontend-nextjs/PERCY.md` for detailed guide.

## Troubleshooting

### Flaky E2E Tests

If E2E tests fail intermittently:

1. **Check for timing issues:**
   - Use explicit waits (`page.wait_for_selector()`)
   - Avoid hard-coded sleeps (`time.sleep()`)
   - Increase timeout for slow networks

2. **Verify test data:**
   - Ensure tests create their own data
   - Clean up test data in `finally` blocks
   - Use transactions and rollbacks

3. **Check for race conditions:**
   - Use `waitFor*` methods
   - Mock external APIs
   - Disable animations in tests

4. **Review CI logs:**
   - Check for network timeouts
   - Verify server startup times
   - Review resource limits

### Mobile Tests Failing

If mobile tests fail:

1. **Verify API contracts:**
   - Check backend schema matches expected format
   - Verify authentication tokens are valid
   - Review API response codes

2. **Check test environment:**
   - Ensure backend server is running
   - Verify database migrations applied
   - Check environment variables

3. **Review Plan 099-02 decisions:**
   - Detox E2E blocked by expo-dev-client
   - Using API-level tests as alternative
   - Tests validate backend workflows, not UI

### Desktop Tests Failing

If desktop tests fail:

1. **Verify Tauri environment:**
   - Ensure Rust toolchain installed
   - Check Tauri CLI version
   - Verify system dependencies

2. **Check integration tests:**
   - Review IPC command signatures
   - Verify window state management
   - Test file operations permissions

3. **Review Plan 099-03 decisions:**
   - tauri-driver blocked by unavailability
   - Using Tauri integration tests
   - Tests cover IPC, window state, file ops

### Performance Tests Failing

If Lighthouse tests fail:

1. **Review performance budgets:**
   - Check if budgets are realistic
   - Verify baseline metrics are accurate
   - Adjust budgets if needed

2. **Check bundle size:**
   - Analyze bundle with `npm run analyze`
   - Identify large dependencies
   - Implement code splitting

3. **Review Lighthouse docs:**
   - `frontend-nextjs/LIGHTHOUSE.md`
   - Web.dev performance guides
   - Chrome DevTools audits

### Visual Regression Tests Failing

If Percy tests fail:

1. **Review visual diffs:**
   - Check Percy dashboard for screenshots
   - Verify changes are intentional
   - Approve or reject diffs

2. **Update Percy CSS:**
   - Add selectors for dynamic content
   - Hide timestamps, loading indicators
   - Reduce false positives

3. **Review Percy docs:**
   - `frontend-nextjs/PERCY.md`
   - Percy documentation
   - Snapshot best practices

## Maintenance

### Adding New E2E Tests

1. **Write test on web platform first**
   - Use Playwright for browser automation
   - Test complete user workflow
   - Verify test passes locally

2. **Mirror test to mobile/desktop**
   - Mobile: API contract validation
   - Desktop: Tauri integration test
   - Maintain feature parity

3. **Update documentation**
   - Add test to E2E test inventory
   - Update cross-platform test matrix
   - Document any new patterns

4. **Commit with conventional format:**
   ```bash
   git commit -m "test(e2e): add {workflow} E2E test

   - Web: Playwright test for {workflow}
   - Mobile: API contract validation
   - Desktop: Tauri integration test"
   ```

### Updating E2E Dependencies

Update dependencies quarterly or when major releases include breaking changes:

- **Playwright:** `backend/requirements-testing.txt`
- **Detox:** `mobile/package.json` (when adopted)
- **WebDriverIO:** `frontend-nextjs/package.json` (when adopted)
- **Percy:** `frontend-nextjs/package.json` (@percy/cli, @percy/playwright)
- **Lighthouse CI:** `frontend-nextjs/package.json` (@lhci/cli)

**Update process:**
1. Update dependency version
2. Run tests locally
3. Review breaking changes
4. Update test code if needed
5. Commit with `chore(e2e): update {dependency}`

### Test Inventory

Maintain an inventory of all E2E tests:

| Workflow | Web | Mobile | Desktop | Last Updated |
|----------|-----|--------|---------|--------------|
| Authentication | ✅ | ✅ | ✅ | 2026-02-27 |
| Agent Execution | ✅ | ✅ | ✅ | 2026-02-27 |
| Canvas Presentations | ✅ | ✅ | ✅ | 2026-02-27 |
| Skill Execution | ✅ | ✅ | ✅ | 2026-02-27 |
| Feature Parity | ✅ | ✅ | ✅ | 2026-02-27 |

**Total Tests:** 42+ E2E + 89 cross-platform + 15 visual snapshots = 146+ test scenarios

## Further Reading

### Phase 099 Documentation
- Phase 099 Plans: `.planning/phases/099-cross-platform-integration/*-PLAN.md`
- Phase 099 Research: `.planning/phases/099-cross-platform-integration/099-RESEARCH.md`
- Phase 099 Verification: `.planning/phases/099-cross-platform-integration/099-VERIFICATION.md`

### Platform-Specific Guides
- Web (Playwright): `backend/tests/e2e_ui/README.md`
- Mobile: `mobile/README.md`
- Desktop: `frontend-nextjs/src-tauri/tests/README.md`

### Tool Documentation
- Playwright Docs: https://playwright.dev/python/
- Detox Docs: https://wix.github.io/Detox/ (future reference)
- WebDriverIO Docs: https://webdriver.io/ (future reference)
- Percy Docs: https://docs.percy.io/
- Lighthouse CI Docs: https://github.com/GoogleChrome/lighthouse-ci

### Performance Guides
- Web.dev Performance: https://web.dev/performance/
- Chrome DevTools: https://developer.chrome.com/docs/devtools/
- Bundle Analyzer: https://www.npmjs.com/package/webpack-bundle-analyzer

---

*Last updated: 2026-02-27*
*Phase: 099 Cross-Platform Integration & E2E*
*Status: COMPLETE*
