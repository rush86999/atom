# Browser Bug Discovery Test: [Discovery Type]

## Purpose

Discover [bug type: console errors, accessibility violations, broken links] on [page/component]

**What this test discovers:**
- [Bug category 1: e.g., JavaScript console errors during page load]
- [Bug category 2: e.g., WCAG 2.1 AA accessibility violations]
- [Bug category 3: e.g., Broken links (404 responses)]

**Target:**
- Page: `[URL path]`
- Component: `[component name]`
- Platform: `[web, mobile, desktop]`

## Dependencies

**Required Libraries:**
```bash
pip install playwright==1.58.0
playwright install chromium
```

**Target Page:**
- URL: `/[path]` (e.g., `/agents`, `/workflows`, `/canvas`)
- Authentication required: `[yes/no]`

**Required Fixtures:**
- `authenticated_page` - Playwright Page with API-first auth (from `tests/e2e_ui/fixtures/auth_fixtures.py`)
- `console_monitor` - Console error monitoring fixture
- `accessibility_checker` - Axe-core accessibility checker fixture

## Setup

**Browser setup:**
```python
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page  # API-first auth (10-100x faster)
from tests.browser_discovery.conftest import console_monitor, accessibility_checker

@pytest.fixture
def test_page(authenticated_page: Page):
    """
    Navigate to target page with API-first authentication.

    API-first auth is 10-100x faster than UI login.
    """
    # Navigate to target page
    authenticated_page.goto("/[path]")

    # Wait for page to load
    authenticated_page.wait_for_load_state("networkidle")

    return authenticated_page
```

**Console monitoring setup:**
```python
@pytest.fixture
def console_monitor(page: Page):
    """
    Monitor browser console for errors and warnings.

    Captures:
    - JavaScript errors (Error, TypeError, ReferenceError)
    - Unhandled promise rejections
    - Console warnings (deprecated APIs, etc.)
    """
    errors = []
    warnings = []

    def on_console(msg):
        if msg.type == "error":
            errors.append({
                "text": msg.text,
                "url": page.url,
                "timestamp": datetime.utcnow().isoformat()
            })
        elif msg.type == "warning":
            warnings.append(msg.text)

    page.on("console", on_console)

    yield ConsoleMonitor(errors=errors, warnings=warnings)

    # Cleanup: Remove listener
    page.remove_listener("console", on_console)

class ConsoleMonitor:
    def __init__(self, errors, warnings):
        self.errors = errors
        self.warnings = warnings

    def get_errors(self):
        """Return list of console errors."""
        return self.errors

    def get_warnings(self):
        """Return list of console warnings."""
        return self.warnings

    def has_errors(self):
        """Check if any errors occurred."""
        return len(self.errors) > 0
```

**Accessibility checker setup:**
```python
@pytest.fixture
def accessibility_checker(page: Page):
    """
    Check WCAG 2.1 AA accessibility violations using axe-core.

    Returns violations grouped by severity:
    - Critical: Violations that prevent assistive technology use
    - Serious: Affects accessibility but not blocking
    - Moderate: Minor accessibility issues
    - Minor: Cosmetic accessibility issues
    """
    # Inject axe-core library
    page.add_init_script("""
        window.axe = null;
        import('https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.2/axe.min.js')
            .then(module => {
                window.axe = module.default;
            });
    """)

    # Wait for axe-core to load
    page.wait_for_function("window.axe !== null")

    class AccessibilityChecker:
        def __init__(self, page):
            self.page = page

        def check_wcag(self, level="AA"):
            """
            Run axe-core WCAG scan.

            Args:
                level: WCAG level (A, AA, AAA)

            Returns:
                List of violations
            """
            violations = self.page.evaluate(f"""
                () => {{
                    return window.axe.run(document, {{
                        runOnly: {{
                            type: 'tag',
                            values: ['wcag2{level}']
                        }}
                    }});
                }}
            """)

            # Group by severity
            grouped = {
                "critical": [],
                "serious": [],
                "moderate": [],
                "minor": []
            }

            for v in violations:
                impact = v.get("impact", "minor")
                grouped[impact].append(v)

            return grouped

    return AccessibilityChecker(page)
```

## Test Procedure

### Console Error Detection

```python
@pytest.mark.browser
@pytest.mark.slow
def test_console_errors_on_[page](authenticated_page: Page, console_monitor):
    """
    Discover JavaScript console errors on [page].

    Monitors:
    - JavaScript errors (Error, TypeError, ReferenceError)
    - Unhandled promise rejections
    - Console warnings (deprecated APIs)

    Expected: No console errors or warnings
    """
    # Navigate to page
    authenticated_page.goto("/[path]")
    authenticated_page.wait_for_load_state("networkidle")

    # Interact with page (if applicable)
    # authenticated_page.click("button#create-agent")
    # authenticated_page.wait_for_load_state("networkidle")

    # Check for console errors
    errors = console_monitor.get_errors()

    # Assert no errors
    assert len(errors) == 0, \
        f"Console errors found on /[path]: {errors}"

    # Check for warnings (optional, can be informational)
    warnings = console_monitor.get_warnings()
    if warnings:
        print(f"Console warnings (informational): {warnings}")
```

### Accessibility Violation Detection

```python
@pytest.mark.browser
@pytest.mark.slow
def test_accessibility_on_[page](authenticated_page: Page, accessibility_checker):
    """
    Discover WCAG 2.1 AA accessibility violations on [page].

    Checks:
    - Critical: Assistive technology blocked
    - Serious: Affects accessibility
    - Moderate: Minor issues
    - Minor: Cosmetic issues

    Expected: No critical or serious violations
    """
    # Navigate to page
    authenticated_page.goto("/[path]")
    authenticated_page.wait_for_load_state("networkidle")

    # Run accessibility scan
    violations = accessibility_checker.check_wcag(level="AA")

    # Assert no critical or serious violations
    critical_violations = violations["critical"]
    serious_violations = violations["serious"]

    assert len(critical_violations) == 0, \
        f"Critical WCAG violations: {critical_violations}"

    assert len(serious_violations) == 0, \
        f"Serious WCAG violations: {serious_violations}"

    # Log moderate/minor violations (informational)
    moderate_count = len(violations["moderate"])
    minor_count = len(violations["minor"])
    if moderate_count > 0 or minor_count > 0:
        print(f"WCAG violations (moderate: {moderate_count}, minor: {minor_count})")
```

### Broken Link Detection

```python
@pytest.mark.browser
@pytest.mark.slow
def test_broken_links_on_[page](authenticated_page: Page):
    """
    Discover broken links (404 responses) on [page].

    Checks:
    - All anchor links (<a> tags) return valid responses
    - No 404 Not Found errors
    - No 5xx server errors

    Expected: All links return 2xx or 3xx responses
    """
    # Navigate to page
    authenticated_page.goto("/[path]")
    authenticated_page.wait_for_load_state("networkidle")

    # Get all links
    links = authenticated_page.locator("a").all()
    hrefs = [link.get_attribute("href") for link in links if link.get_attribute("href")]

    # Filter out external links (only test internal links)
    internal_hrefs = [href for href in hrefs if href.startswith("/") or "localhost" in href]

    broken_links = []

    # Check each link
    for href in internal_hrefs:
        try:
            response = authenticated_page.request.get(href)
            status = response.status

            # Check for 404 or 5xx errors
            if status == 404:
                broken_links.append({"href": href, "error": "404 Not Found"})
            elif status >= 500:
                broken_links.append({"href": href, "error": f"{status} Server Error"})

        except Exception as e:
            broken_links.append({"href": href, "error": str(e)})

    # Assert no broken links
    assert len(broken_links) == 0, \
        f"Broken links found on /[path]: {broken_links}"
```

### Visual Regression Detection (Percy Integration)

```python
@pytest.mark.browser
@pytest.mark.slow
@pytest.mark.visual
def test_visual_regression_on_[page](authenticated_page: Page):
    """
    Discover visual regressions on [page] using Percy.

    Compares:
    - Current screenshot against baseline
    - Pixel-level differences
    - Layout shifts

    Expected: No visual differences (or within threshold)
    """
    # Navigate to page
    authenticated_page.goto("/[path]")
    authenticated_page.wait_for_load_state("networkidle")

    # Take screenshot with Percy
    # Percy automatically compares against baseline
    # and creates diff if visual changes detected

    # Example: Use Percy CLI
    # percy exec -- pytest backend/tests/browser_discovery/test_[page]_visual.py -v

    # Or use Percy SDK
    percy_snapshot(authenticated_page, name="[page]")

    # If visual differences detected:
    # 1. Percy uploads screenshot
    # 2. Compares against baseline
    # 3. Creates diff image
    # 4. Files bug with diff URL

    # Assert: Percy comparison passes (no diffs)
    # (Handled by Percy CLI/SDK, not explicit assertion)
```

## Expected Behavior

**Console error detection:**
- No JavaScript errors (Error, TypeError, ReferenceError)
- No unhandled promise rejections
- No deprecated API warnings (or logged as informational)

**Accessibility violation detection:**
- No critical WCAG violations (assistive technology blocked)
- No serious WCAG violations (affects accessibility)
- Moderate/minor violations logged (informational)

**Broken link detection:**
- All links return 2xx (success) or 3xx (redirect) responses
- No 404 Not Found errors
- No 5xx server errors

**Visual regression detection:**
- No visual differences from baseline
- Or differences within acceptable threshold (e.g., <1% pixel diff)

## Bug Filing

**Automatic bug filing on discovery:**
```python
from tests.bug_discovery.bug_filing_service import BugFilingService
import os
from datetime import datetime

def capture_screenshot(page: Page, test_name: str) -> str:
    """Capture screenshot and return path."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{test_name}_{timestamp}.png"
    path = f"/tmp/screenshots/{filename}"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    page.screenshot(path=path)
    return path

def file_bug_from_console_errors(test_name, errors, page):
    """File bug for console errors with screenshot."""
    screenshot_path = capture_screenshot(page, test_name)

    BugFilingService.file_bug(
        test_name=f"test_{test_name}_console_errors",
        error_message=f"{len(errors)} console errors found",
        metadata={
            "test_type": "browser",
            "discovery_type": "console",
            "page": "/[path]",
            "error_count": len(errors),
            "screenshot_path": screenshot_path,
            "console_errors": errors[:10]  # First 10 errors
        },
        expected_behavior="No JavaScript console errors on page load",
        actual_behavior=f"Found {len(errors)} console errors: {errors[:3]}"
    )

def file_bug_from_accessibility_violations(test_name, violations, page):
    """File bug for WCAG violations with screenshot."""
    screenshot_path = capture_screenshot(page, test_name)

    BugFilingService.file_bug(
        test_name=f"test_{test_name}_accessibility",
        error_message=f"{len(violations['critical'])} critical WCAG violations",
        metadata={
            "test_type": "browser",
            "discovery_type": "accessibility",
            "page": "/[path]",
            "critical_violations": len(violations["critical"]),
            "serious_violations": len(violations["serious"]),
            "wcag_level": "AA",
            "screenshot_path": screenshot_path,
            "violations": violations["critical"][:5]  # First 5 critical
        },
        expected_behavior="No critical WCAG 2.1 AA violations",
        actual_behavior=f"Found {len(violations['critical'])} critical violations: {violations['critical'][:3]}"
    )

def file_bug_from_broken_links(test_name, broken_links, page):
    """File bug for broken links with screenshot."""
    screenshot_path = capture_screenshot(page, test_name)

    BugFilingService.file_bug(
        test_name=f"test_{test_name}_broken_links",
        error_message=f"{len(broken_links)} broken links found",
        metadata={
            "test_type": "browser",
            "discovery_type": "links",
            "page": "/[path]",
            "broken_link_count": len(broken_links),
            "screenshot_path": screenshot_path,
            "broken_links": broken_links[:10]  # First 10 broken links
        },
        expected_behavior="All links return 2xx or 3xx responses",
        actual_behavior=f"Found {len(broken_links)} broken links: {broken_links[:3]}"
    )

def file_bug_from_visual_regression(test_name, percy_diff_url, page):
    """File bug for visual regression with Percy diff URL."""
    screenshot_path = capture_screenshot(page, test_name)

    BugFilingService.file_bug(
        test_name=f"test_{test_name}_visual_regression",
        error_message="Visual regression detected by Percy",
        metadata={
            "test_type": "browser",
            "discovery_type": "visual",
            "page": "/[path]",
            "percy_diff_url": percy_diff_url,
            "screenshot_path": screenshot_path,
            "pixel_diff_count": "see Percy report"
        },
        expected_behavior="No visual differences from baseline",
        actual_behavior=f"Visual differences detected: {percy_diff_url}"
    )
```

**Manual bug filing (if not automatic):**
```bash
# Bug title: [Bug] Console errors: [Page Name] Browser Discovery

# Bug body:
## Bug Description

Browser bug discovery test discovered [error type] on [page].

## Discovery Type

- Type: [console errors / accessibility violations / broken links / visual regression]
- Page: /[path]
- Platform: [web / mobile / desktop]

## Steps to Reproduce

1. Run browser discovery test: `pytest backend/tests/browser_discovery/test_[page]_console.py -v`
2. Navigate to: /[path]
3. Observe [error type]

## Actual Behavior

### Console Errors
```
[paste console errors]
```

### Accessibility Violations
```
[paste WCAG violations from axe-core]
```

### Broken Links
```
[paste broken links list]
```

### Visual Regression
- Percy diff URL: [URL]
- Pixel diff count: [N]
- Diff screenshot: [URL]

## Expected Behavior

- No JavaScript console errors
- No critical WCAG violations
- All links return 2xx or 3xx responses
- No visual differences from baseline

## Screenshot

![Screenshot](/path/to/screenshot.png)

## Test Context

- **Test:** `test_[page]_[discovery_type]`
- **Platform:** [output of browser version]
- **Viewport:** [width]x[height]
- **URL:** /[path]
- **Timestamp:** [ISO timestamp]
```

## TQ Compliance

**TQ-01 (Test Independence):**
- `authenticated_page` fixture provides isolated test data (API-first auth)
- Each test navigates to fresh page instance
- No shared browser state between tests

**TQ-02 (Pass Rate):**
- Browser tests are deterministic (same page = same errors)
- Same page navigation produces same console output
- 98%+ pass rate expected (failures = real bugs)

**TQ-03 (Performance):**
- Per-test timeout: 30s (Playwright default)
- Console error tests: ~10s per page
- Accessibility tests: ~15s per page (axe-core scan)
- Link checking: ~20s per page (N requests)

**TQ-04 (Determinism):**
- Same page navigation produces same console output
- Accessibility scan produces same violations
- Link checking produces same 404s
- Use `authenticated_page` fixture (API-first auth, deterministic)

**TQ-05 (Coverage Quality):**
- Tests observable user-facing behavior (console, a11y, links)
- Not implementation details (DOM structure, CSS classes)
- Validates user experience (accessibility, errors)

## pytest.ini Marker

Add to `backend/pytest.ini`:
```ini
[pytest]
markers =
    browser: Browser bug discovery tests (Playwright, slow, console/a11y/link checks)
    visual: Visual regression tests (Percy, screenshots, slow)
    slow: Slow tests (>10s, skip in fast CI)
```

Run only browser discovery tests:
```bash
pytest backend/tests/browser_discovery/ -v -m browser
```

Run only visual regression tests:
```bash
pytest backend/tests/browser_discovery/ -v -m visual
```

Skip slow tests in fast CI:
```bash
pytest backend/tests/ -v -m "not slow"
```

## Performance Optimization

**Parallel execution:**
```bash
# Run browser tests in parallel (requires pytest-xdist)
pytest backend/tests/browser_discovery/ -v -n 4  # 4 parallel workers

# Each worker gets separate browser instance
# Tests run 4x faster (assuming 4 CPU cores)
```

**API-first authentication (10-100x faster than UI login):**
```python
# Use authenticated_page fixture from tests/e2e_ui/fixtures/auth_fixtures.py
# This sets JWT token in localStorage directly (bypasses UI login)

# BAD: UI login (slow, 10-30s)
# page.goto("/login")
# page.fill("input[name='email']", "test@example.com")
# page.fill("input[name='password']", "password")
# page.click("button[type='submit']")
# page.wait_for_url("/dashboard")

# GOOD: API-first auth (fast, 0.1-0.5s)
# authenticated_page = create_authenticated_page()  # Sets JWT token
# authenticated_page.goto("/dashboard")  # Already logged in
```

**Selective monitoring:**
```python
# Monitor only critical errors (not all warnings)
def on_console(msg):
    if msg.type == "error":
        errors.append(msg.text)
    # Skip warnings (informational only)
```

## See Also

- [Playwright Documentation](https://playwright.dev/python/)
- [Axe-Core Documentation](https://www.deque.com/axe/)
- [Percy Documentation](https://docs.percy.io/)
- `backend/docs/TEST_QUALITY_STANDARDS.md` - TQ-01 through TQ-05
- `backend/tests/bug_discovery/TEMPLATES/README.md` - Template usage guide
