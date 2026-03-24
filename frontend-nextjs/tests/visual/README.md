# Visual Regression Testing with Percy

This directory contains Percy visual regression tests for the Atom frontend. Visual regression testing helps catch UI bugs, CSS changes, broken components, and cross-browser issues before they reach production.

## Overview

**Percy** is a visual regression testing platform that:
- Takes screenshots of your application across different viewport sizes
- Compares screenshots against a baseline to detect visual changes
- Highlights visual diffs in an easy-to-review dashboard
- Integrates with CI/CD for automated visual testing on every PR

**Why Visual Regression Testing?**
- Catch CSS/layout changes that break the UI
- Detect broken components and visual bugs
- Ensure cross-browser consistency
- Prevent accidental visual regressions
- Review visual changes in a structured way

## Prerequisites

Before running visual tests, ensure you have:

1. **Percy Account** - Sign up at https://percy.io
2. **PERCY_TOKEN** - Get your token from Percy Dashboard → Project Settings → Token
3. **Percy CLI** - Install `@percy/cli` and `@percy/playwright` (already installed)
4. **Dependencies** - Python 3.11+, pytest, pytest-playwright, playwright

## Percy Setup

### 1. Install Percy CLI

```bash
npm install --save-dev @percy/cli @percy/playwright
```

Or install globally:
```bash
npm install -g @percy/cli
```

### 2. Configure Percy

The Percy configuration is in `.percy.yml` at the project root:

```yaml
version: 2
snapshot:
  widths: [375, 768, 1280]  # Mobile, tablet, desktop
  min-height: 1024
  percy-css: |
    /* Hide dynamic content */
    .timestamp { display: none !important; }
    .session-id { display: none !important; }
  ignore:
    - '.timestamp'
    - '.session-id'
    - '.loading-spinner'
discovery:
  allowed-hostnames:
    - localhost
    - localhost:3000
agent:
  asset-discovery:
    network-idle-timeout: 100
```

### 3. Set PERCY_TOKEN

Set your Percy token as an environment variable:

```bash
export PERCY_TOKEN=your_token_here
```

For CI/CD, add `PERCY_TOKEN` as a secret in your repository settings.

## Running Tests

### Run All Visual Tests Locally

```bash
# Without Percy (dry run)
pytest frontend-nextjs/tests/visual/ -v

# With Percy (uploads snapshots)
percy exec -- pytest frontend-nextjs/tests/visual/ -v
```

### Run Specific Test File

```bash
# Login page tests
pytest frontend-nextjs/tests/visual/test_visual_regression_login.py -v

# Dashboard tests
pytest frontend-nextjs/tests/visual/test_visual_regression_dashboard.py -v

# Agents tests
pytest frontend-nextjs/tests/visual/test_visual_regression_agents.py -v

# Canvas tests
pytest frontend-nextjs/tests/visual/test_visual_regression_canvas.py -v

# Workflows tests
pytest frontend-nextjs/tests/visual/test_visual_regression_workflows.py -v
```

### Run Specific Test

```bash
# Run a single test
pytest frontend-nextjs/tests/visual/test_visual_regression_login.py::TestVisualLogin::test_visual_login_page -v

# Run tests matching a pattern
pytest frontend-nextjs/tests/visual/ -k "login" -v
pytest frontend-nextjs/tests/visual/ -k "mobile" -v
```

### Run with Custom Base URL

```bash
# Custom frontend URL
pytest frontend-nextjs/tests/visual/ --base-url=http://localhost:3001 -v

# Custom API URL
export API_BASE_URL=http://localhost:8001
pytest frontend-nextjs/tests/visual/ -v
```

## Test Coverage

Visual tests cover **20+ critical pages** across the application:

| Page/Component | Tests | Viewports |
|---------------|-------|-----------|
| **Login** | 4 tests | Desktop, Mobile |
| - Default login page | ✓ | 1280, 768, 375 |
| - Validation error state | ✓ | 1280, 768, 375 |
| - Loading state | ✓ | 1280, 768, 375 |
| - Mobile layout | ✓ | 375 |
| **Dashboard** | 6 tests | Desktop, Mobile |
| - Default dashboard | ✓ | 1280, 768, 375 |
| - Empty state | ✓ | 1280, 768, 375 |
| - With data | ✓ | 1280, 768, 375 |
| - Sidebar expanded | ✓ | 1280, 768, 375 |
| - Sidebar collapsed | ✓ | 1280, 768, 375 |
| - Mobile layout | ✓ | 375 |
| **Agents** | 3 tests | Desktop, Mobile |
| - Agents list | ✓ | 1280, 768, 375 |
| - Agent detail | ✓ | 1280, 768, 375 |
| - Execution result | ✓ | 1280, 768, 375 |
| **Canvas** | 7 tests | Desktop, Mobile |
| - Chart canvas | ✓ | 1280, 768, 375 |
| - Sheet canvas | ✓ | 1280, 768, 375 |
| - Form canvas | ✓ | 1280, 768, 375 |
| - Docs canvas | ✓ | 1280, 768, 375 |
| - Email canvas | ✓ | 1280, 768, 375 |
| - Terminal canvas | ✓ | 1280, 768, 375 |
| - Coding canvas | ✓ | 1280, 768, 375 |
| **Workflows** | 6 tests | Desktop, Mobile |
| - Workflows list | ✓ | 1280, 768, 375 |
| - Empty builder | ✓ | 1280, 768, 375 |
| - Builder with skills | ✓ | 1280, 768, 375 |
| - Execution running | ✓ | 1280, 768, 375 |
| - Execution results | ✓ | 1280, 768, 375 |
| - DAG visualization | ✓ | 1280, 768, 375 |

**Total: 26 visual tests × 3 viewports = 78+ snapshots**

## CI/CD Integration

### GitHub Actions

Add Percy to your GitHub Actions workflow:

```yaml
name: Visual Regression Tests

on:
  pull_request:
    branches: [main]

jobs:
  visual-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          npm install
          npm install -g @percy/cli
          pip install pytest pytest-playwright playwright

      - name: Install Playwright browsers
        run: playwright install chromium

      - name: Start frontend
        run: npm run dev &
          sleep 10

      - name: Run Percy tests
        env:
          PERCY_TOKEN: ${{ secrets.PERCY_TOKEN }}
        run: |
          percy exec -- pytest frontend-nextjs/tests/visual/ -v
```

### Percy Dashboard

After tests run, view snapshots and approve/reject changes at:
- **Percy Dashboard**: https://percy.io/[your-org]/[your-project]
- **Build History**: See all visual test runs
- **Diff Review**: Compare screenshots side-by-side
- **Approval Workflow**: Approve or reject visual changes

## Reviewing Visual Diffs

### Percy Dashboard

1. **Open Build** - Click on a build in the Percy dashboard
2. **Review Diffs** - See screenshots with visual differences highlighted
3. **Approve/Reject** - Accept changes as expected or reject as bugs
4. **Baseline Update** - Approving updates the baseline for future comparisons

### Diff Types

- **Pixel-perfect diffs** - Exact pixel differences highlighted in red
- **Ignored regions** - Areas configured to ignore (timestamps, session IDs)
- **Viewport variations** - Diffs across different screen sizes
- **Browser variations** - Cross-browser differences (if testing multiple browsers)

### Best Practices

1. **Review all diffs** - Don't auto-approve without reviewing
2. **Understand the change** - Know what changed in the PR
3. **Test locally first** - Run tests locally before pushing
4. **Communicate changes** - Document intentional UI changes in PR description
5. **Reject bugs** - If a diff looks wrong, reject and file a bug

## Troubleshooting

### PERCY_TOKEN Not Set

**Error:** `PERCY_TOKEN not set`

**Solution:**
```bash
export PERCY_TOKEN=your_token_here
```

Get your token from: Percy Dashboard → Project Settings → Token

### Snapshots Not Uploading

**Error:** Tests pass but no snapshots in Percy dashboard

**Solution:**
1. Verify `PERCY_TOKEN` is set correctly
2. Check internet connection
3. Run with `percy exec -- pytest ...` (not `pytest` alone)
4. Check Percy dashboard for build status

### Snapshot Failures

**Error:** `Timeout waiting for element`

**Solution:**
1. Increase timeout in test: `page.wait_for_timeout(5000)`
2. Check if element selector is correct
3. Verify page is fully loaded before snapshot
4. Use `wait_for_load_state("networkidle")`

### False Positives

**Error:** Dynamic content causes diffs (timestamps, random IDs)

**Solution:**
1. Add to `percy-css` in `.percy.yml`:
   ```yaml
   percy-css: |
     .timestamp { display: none !important; }
     .random-id { display: none !important; }
   ```
2. Add to `ignore` regions:
   ```yaml
   ignore:
     - '.timestamp'
     - '.random-id'
   ```

### Test Data Issues

**Error:** Tests fail due to missing test data

**Solution:**
1. Check `percy_test_data` fixture is creating test data
2. Verify API endpoints are working
3. Check authentication is successful
4. Review test logs for specific errors

## Writing New Visual Tests

### Test Template

```python
import pytest
from playwright.sync_api import Page, expect

class TestVisualNewPage:
    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_new_page(self, authenticated_percy_page: Page, base_url: str):
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to page
        authenticated_percy_page.goto(f"{base_url}/new-page")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Take snapshot
        percy_snapshot(authenticated_percy_page, "New Page")

        # Verify elements
        expect(authenticated_percy_page.locator("h1")).to_be_visible()
```

### Best Practices

1. **Use descriptive names** - "Login Page" not "LP"
2. **Wait for idle** - `wait_for_load_state("networkidle")`
3. **Verify elements** - Assert key elements are visible
4. **Test multiple states** - Default, error, loading, empty
5. **Test mobile** - Use `set_viewport_size({"width": 375, "height": 667})`
6. **Graceful skip** - Use `pytest.skip()` when data unavailable
7. **Ignore dynamic content** - Hide timestamps, session IDs in Percy CSS

## Fixtures

### Available Fixtures

```python
# Basic page with Percy
percy_page

# Authenticated page with API login
authenticated_percy_page

# Test data creation and cleanup
percy_test_data

# Percy token verification
perci_token

# Base URLs
base_url          # Frontend URL (default: http://localhost:3000)
api_base_url      # API URL (default: http://localhost:8000)

# Test user credentials
test_user_data    # {email, password}
```

### Using Fixtures

```python
def test_example(authenticated_percy_page, percy_test_data, base_url):
    # Navigate to page
    authenticated_percy_page.goto(f"{base_url}/page")

    # Use test data
    agent_ids = percy_test_data["agent_ids"]

    # Take snapshot
    percy_snapshot(authenticated_percy_page, "Page Name")
```

## Performance

- **Snapshot time:** ~1-2 seconds per snapshot
- **Upload time:** ~0.5-1 second per snapshot
- **Total test time:** ~2-3 minutes for 26 tests
- **CI/CD impact:** Adds ~3-5 minutes to build time

## Resources

- **Percy Documentation:** https://docs.percy.io
- **Percy Dashboard:** https://percy.io
- **Percy CLI:** https://github.com/percy/cli
- **Playwright Python:** https://playwright.dev/python/
- **Pytest Documentation:** https://docs.pytest.org/

## Support

For issues or questions:
1. Check Percy dashboard for build status
2. Review test logs for errors
3. Verify PERCY_TOKEN is set correctly
4. Check `.percy.yml` configuration
5. Review troubleshooting section above

---

**Last Updated:** 2026-03-24
**Maintained By:** Atom QA Team
