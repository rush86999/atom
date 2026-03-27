# Phase 240: Headless Browser Bug Discovery - Research

**Researched:** 2026-03-24
**Domain:** Headless browser automation, intelligent UI exploration, bug discovery, accessibility testing, visual regression
**Confidence:** HIGH

## Summary

Phase 240 focuses on implementing intelligent headless browser bug discovery using Playwright Python 1.58.0 with heuristic exploration agents, console error detection, accessibility violation checking (axe-core for WCAG 2.1 AA), broken link detection, and visual regression testing (Percy integration from Phase 236). The research confirms that **browser discovery infrastructure already exists** in `backend/tests/browser_discovery/conftest.py` with fixtures for console monitoring, accessibility checking, visual regression, broken link checking, and an intelligent exploration agent prototype.

**Primary recommendation:** Build on existing browser discovery fixtures in `backend/tests/browser_discovery/conftest.py` (console_monitor, accessibility_checker, exploration_agent, broken_link_checker, visual_regression_checker) to implement comprehensive bug discovery tests. Leverage existing Percy integration from Phase 236 (78+ screenshots across 5 test files, .percy.yml configured with widths [375, 768, 1280] and ignore rules). Reuse API-first authentication fixtures from e2e_ui for 10-100x faster test setup. Create test files covering all 7 BROWSER-01 through BROWSER-07 requirements with heuristic exploration algorithms (depth-first, breadth-first, random walk), console error detection, accessibility violations (axe-core WCAG 2.1 AA), broken links (404, redirect loops), visual regression (Percy), form filling edge cases (null bytes, XSS, SQL injection).

**Key findings:**
1. **Browser discovery fixtures exist**: `backend/tests/browser_discovery/conftest.py` has 5 fixtures (console_monitor, accessibility_checker with axe-core, exploration_agent prototype, broken_link_checker, visual_regression_checker)
2. **Percy visual regression configured**: Phase 236-06 completed with 26 tests across 5 page groups (78+ screenshots), .percy.yml with widths [375, 768, 1280], ignore rules for dynamic content
3. **API-first auth fixtures**: `tests/e2e_ui/fixtures/auth_fixtures.py` provides authenticated_page (10-100x faster than UI login), reusable across browser discovery tests
4. **Playwright Python 1.58.0 installed**: Already in backend/requirements.txt, 91 E2E tests use it
5. **axe-core integration pattern exists**: accessibility_checker fixture injects axe-core 4.8.2 via CDN, runs WCAG 2.1 AA compliance checks (wcag2a, wcag2aa, wcag21a, wcag21aa tags)
6. **Console error detection implemented**: console_monitor fixture uses page.on("console") to capture errors, warnings, info, log, debug with timestamps and locations
7. **Exploration agent prototype**: ExplorationAgent class with explore(max_depth, max_actions), _check_for_bugs() for console errors and broken images
8. **Broken link checking implemented**: broken_link_checker fixture finds all <a> elements, checks HTTP status codes via requests.head(), skips localhost
9. **pytest markers configured**: browser_discovery, accessibility, visual_regression, broken_links markers already in conftest.py

## Standard Stack

### Core Bug Discovery Tools
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Playwright Python** | 1.58.0 | Headless browser automation | Industry standard, auto-waiting, network interception, 91 E2E tests already use it |
| **pytest-playwright** | 0.5.2 | Pytest plugin for Playwright | Pytest integration, fixtures for browser/page/context |
| **axe-core** | 4.8.2 (CDN) | Accessibility testing (WCAG 2.1 AA) | De facto standard for automated a11y testing, inject via CDN |
| **requests** | (existing) | HTTP link checking | Already installed, simple HEAD requests for broken link detection |

### Visual Regression Testing
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **@percy/cli** | (npm) | Percy CLI for visual regression | Already installed from Phase 236-06 |
| **@percy/playwright** | (npm) | Percy Playwright integration | Already configured in .percy.yml with 3 widths |
| **Playwright screenshot API** | 1.58.0 | Screenshot capture for visual comparison | Use for baseline screenshots, Percy integration |

### Exploration Algorithms (Custom Implementation)
| Algorithm | Purpose | When to Use |
|-----------|---------|-------------|
| **Depth-First Search (DFS)** | Explore deep UI paths first | Finding bugs in nested workflows, form wizards |
| **Breadth-First Search (BFS)** | Explore all links at current depth first | Discovering all reachable pages, navigation bugs |
| **Random Walk** | Stochastic exploration for edge cases | Uncovering unexpected state combinations |
| **Heuristic-Guided Exploration** | Prioritize high-value actions (forms, buttons) | Focused bug discovery on critical paths |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **Playwright Python** | Selenium WebDriver | Playwright has auto-waiting, faster, better API, already in use |
| **axe-core (CDN injection)** | axe-selenium-python | axe-selenium-python requires npm install, CDN injection is simpler |
| **Percy** | Playwright screenshot comparison | Percy provides cloud hosting, diff UI, team approval workflow |
| **Custom exploration algorithms** | Taiko, TestCafe | Playwright has richer API for advanced exploration (page.evaluate, response interception) |

**Installation:**
```bash
# Core browser automation (already installed)
pip install playwright==1.58.0 pytest-playwright==0.5.2
playwright install chromium

# Visual regression (already installed from Phase 236-06)
npm install -g @percy/cli @percy/playwright

# Percy configuration (already exists)
cat .percy.yml  # widths: [375, 768, 1280], ignore rules configured

# Accessibility testing (axe-core injected via CDN, no install needed)
```

## Architecture Patterns

### Recommended Test Structure

**Existing Structure (from Phase 237):**
```
backend/tests/
├── browser_discovery/        # ✅ EXISTS - Browser bug discovery infrastructure
│   ├── conftest.py            # ✅ EXISTS - Fixtures for console, a11y, exploration, links, visual
│   └── __init__.py
├── e2e_ui/                    # ✅ EXISTS - E2E tests with reusable fixtures
│   ├── fixtures/
│   │   ├── auth_fixtures.py   # ✅ EXISTS - API-first auth (10-100x faster)
│   │   ├── database_fixtures.py
│   │   └── test_data_factory.py
│   └── tests/
├── bug_discovery/             # ✅ EXISTS - Bug filing service
│   ├── bug_filing_service.py
│   └── fixtures/
└── conftest.py
```

**NEW Test Files (Phase 240):**
```
backend/tests/browser_discovery/
├── conftest.py                 # ✅ KEEP - Existing fixtures
├── __init__.py
├── test_console_errors.py      # ✅ NEW - BROWSER-02: Console error detection
├── test_accessibility.py       # ✅ NEW - BROWSER-03: WCAG 2.1 AA compliance
├── test_broken_links.py        # ✅ NEW - BROWSER-04: 404s and redirect loops
├── test_visual_regression.py   # ✅ NEW - BROWSER-05: Percy integration (78+ snapshots)
├── test_form_filling.py        # ✅ NEW - BROWSER-06: Edge cases (null bytes, XSS, SQLi)
├── test_exploration_agent.py   # ✅ NEW - BROWSER-01: DFS, BFS, random walk algorithms
└── artifacts/                  # ✅ NEW - Screenshots, logs, crash dumps
    ├── screenshots/
    ├── logs/
    └── reports/
```

**Key Principle:** Reuse existing fixtures from `browser_discovery/conftest.py` and `e2e_ui/fixtures/auth_fixtures.py` to avoid duplication (INFRA-01, INFRA-02 requirements from Phase 237).

### Pattern 1: Intelligent Exploration Agent

**What:** Heuristic-guided UI exploration using graph traversal algorithms (DFS, BFS, random walk) to discover bugs by clicking buttons, filling forms, and navigating through the application.

**When to use:** Automated bug discovery across entire application, finding edge cases not covered by manual tests, regression testing for UI changes.

**Example:**
```python
# Source: backend/tests/browser_discovery/conftest.py (existing ExplorationAgent prototype)
@pytest.mark.browser_discovery
def test_depth_first_exploration(authenticated_page: Page, exploration_agent):
    """Explore UI using depth-first search to discover bugs."""
    authenticated_page.goto("http://localhost:3001/dashboard")

    # Explore with DFS (max_depth=3, max_actions=20)
    exploration_agent.explore(max_depth=3, max_actions=20)

    # Check bugs found during exploration
    bugs = exploration_agent.get_bugs()
    assert len(bugs) == 0, f"Exploration found {len(bugs)} bugs: {bugs}"
```

**Implementation details:**
- **DFS (Depth-First Search):** Navigate deep into UI paths first (e.g., dashboard → agent → execute → results → back to explore next agent)
- **BFS (Breadth-First Search):** Explore all links at current depth before going deeper (e.g., explore all dashboard sections before diving into each)
- **Random Walk:** Stochastic exploration for edge cases (click random buttons, fill forms with random data)
- **Heuristic-Guided:** Prioritize high-value actions (forms with required fields, buttons with CTA labels, navigation links)

### Pattern 2: Console Error Detection

**What:** Capture JavaScript console errors and unhandled exceptions using Playwright's `page.on("console")` and `page.on("pageerror")` event handlers.

**When to use:** All browser discovery tests should detect console errors (JavaScript errors, uncaught exceptions, console.error() calls).

**Example:**
```python
# Source: backend/tests/browser_discovery/conftest.py (existing console_monitor fixture)
@pytest.mark.browser_discovery
def test_no_console_errors_on_dashboard(authenticated_page: Page, console_monitor, assert_no_console_errors):
    """Verify dashboard has no JavaScript console errors."""
    authenticated_page.goto("http://localhost:3001/dashboard")
    authenticated_page.wait_for_load_state("networkidle")

    # Assert no console errors (fails with detailed error messages if any)
    assert_no_console_errors()
```

**Console error types captured:**
- **error:** JavaScript errors, console.error() calls
- **warning:** Console warnings, deprecation notices
- **info:** Informational messages
- **log:** General console.log() output
- **debug:** Debug-level messages

**Metadata captured:**
- Error text/message
- Timestamp (ISO 8601)
- URL where error occurred
- Location (file URL, line number, column number)

### Pattern 3: Accessibility Testing with axe-core

**What:** Inject axe-core library via CDN and run WCAG 2.1 AA compliance checks to detect accessibility violations (missing ARIA labels, low contrast, keyboard navigation issues).

**When to use:** All browser discovery tests should verify accessibility compliance (critical for screen reader users, WCAG compliance requirements).

**Example:**
```python
# Source: backend/tests/browser_discovery/conftest.py (existing accessibility_checker fixture)
@pytest.mark.browser_discovery
@pytest.mark.accessibility
def test_dashboard_accessibility_wcag_aa(authenticated_page: Page, assert_accessibility):
    """Verify dashboard has no WCAG 2.1 AA accessibility violations."""
    authenticated_page.goto("http://localhost:3001/dashboard")

    # Assert no accessibility violations (fails with detailed violation messages)
    assert_accessibility()
```

**WCAG 2.1 AA rules checked:**
- wcag2a: Level A compliance (critical issues)
- wcag2aa: Level AA compliance (important issues)
- wcag21a: WCAG 2.1 Level A (new rules in 2.1)
- wcag21aa: WCAG 2.1 Level AA (new rules in 2.1)

**Violation metadata captured:**
- Violation ID (e.g., "color-contrast", "label")
- Impact level (critical, serious, moderate, minor)
- Description of the issue
- Help text for fixing
- Help URL (axe-core documentation)
- Affected nodes (up to 3 for brevity)

### Pattern 4: Broken Link Detection

**What:** Find all links on the page and check their HTTP status codes to detect broken links (404, 500, redirect loops).

**When to use:** After major UI changes, link structure updates, regression testing for navigation bugs.

**Example:**
```python
# Source: backend/tests/browser_discovery/conftest.py (existing broken_link_checker fixture)
@pytest.mark.browser_discovery
@pytest.mark.broken_links
def test_no_broken_links_on_dashboard(authenticated_page: Page, broken_link_checker):
    """Verify dashboard has no broken links (404, 500, redirect loops)."""
    authenticated_page.goto("http://localhost:3001/dashboard")

    # Check all links
    broken_links = broken_link_checker()
    assert len(broken_links) == 0, f"Found {len(broken_links)} broken links: {broken_links}"
```

**Link checking process:**
1. Find all `<a href>` elements using page.evaluate()
2. Extract href, text content, and absolute URL
3. Filter for HTTP/HTTPS links only (skip mailto:, javascript:, anchor links)
4. Send HEAD request with 5s timeout (skip localhost in test environment)
5. Check status code >= 400 indicates broken link
6. Capture URL, text, status code, or error message

### Pattern 5: Visual Regression Testing with Percy

**What:** Capture screenshots across multiple viewport sizes (mobile: 375px, tablet: 768px, desktop: 1280px) and compare against baseline using Percy.

**When to use:** After CSS/layout changes, component updates, cross-browser testing, regression prevention.

**Example:**
```python
# Source: frontend-nextjs/tests/visual/test_visual_regression_dashboard.py (existing from Phase 236-06)
@pytest.mark.e2e
@pytest.mark.visual
def test_visual_dashboard(authenticated_percy_page: Page):
    """Test visual appearance of dashboard page."""
    from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

    # Navigate to dashboard
    authenticated_percy_page.goto("http://localhost:3001/dashboard")
    authenticated_percy_page.wait_for_load_state("networkidle")

    # Take Percy snapshot (captures 3 widths: 375, 768, 1280)
    percy_snapshot(authenticated_percy_page, "Dashboard")

    # Verify dashboard layout elements
    expect(authenticated_percy_page.locator("h1")).to_be_visible()
    expect(authenticated_percy_page.locator("nav")).to_be_visible()
```

**Percy configuration (from Phase 236-06):**
- **Widths:** [375, 768, 1280] (mobile, tablet, desktop)
- **Ignore rules:** Timestamps, session IDs, loading spinners, skeleton loaders
- **Dynamic content hiding:** percy-css hides .timestamp, .session-id, .loading-spinner
- **Coverage:** 26 tests across 5 page groups (login, dashboard, agents, canvas, workflows) = 78+ screenshots

### Pattern 6: Form Filling with Edge Cases

**What:** Fill forms with edge case inputs (null bytes, XSS payloads, SQL injection attempts, unicode, massive strings) to discover input validation bugs and security vulnerabilities.

**When to use:** Testing form validation, input sanitization, security hardening, regression testing for form bugs.

**Example:**
```python
@pytest.mark.browser_discovery
def test_form_filling_null_bytes(authenticated_page: Page):
    """Test form handles null bytes without crashing (BROWSER-06)."""
    authenticated_page.goto("http://localhost:3001/agents/new")

    # Fill agent name with null bytes (edge case)
    authenticated_page.fill("input[name='agent_name']", "agent\x00name\x00with\x00nulls")

    # Fill other fields
    authenticated_page.fill("textarea[name='system_prompt']", "Test prompt")
    authenticated_page.select_option("select[name='maturity_level']", "AUTONOMOUS")

    # Submit form
    authenticated_page.click("button[type='submit']")

    # Verify no crash (either validation error or graceful handling)
    # Null bytes should be sanitized or rejected with clear error message
    assert authenticated_page.locator("body").is_visible()

@pytest.mark.browser_discovery
def test_form_filling_xss_payloads(authenticated_page: Page):
    """Test form sanitizes XSS payloads (BROWSER-06 security testing)."""
    authenticated_page.goto("http://localhost:3001/agents/new")

    # XSS payloads from Phase 237 security patterns
    xss_payloads = [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert("XSS")>',
        '"><script>alert(String.fromCharCode(88,83,83))</script>',
        'javascript:alert("XSS")',
    ]

    for payload in xss_payloads:
        authenticated_page.fill("input[name='agent_name']", payload)
        authenticated_page.fill("textarea[name='system_prompt']", "Test prompt")
        authenticated_page.click("button[type='submit']")

        # Verify XSS not executed (no alert dialog, sanitized in DOM)
        page_content = authenticated_page.content()
        assert '<script>' not in page_content or 'alert' not in page_content, \
            f"XSS payload not sanitized: {payload}"

        # Navigate back for next test
        authenticated_page.goto("http://localhost:3001/agents/new")
```

**Edge case coverage:**
- **Null bytes:** `\x00` in strings (causes C string truncation bugs)
- **XSS payloads:** Script tags, event handlers, javascript: protocol (Phase 237 has 18+ patterns)
- **SQL injection:** `' OR '1'='1`, `'; DROP TABLE agents; --`, UNION SELECT payloads
- **Unicode:** Emoji (🎨), Chinese characters (你好), Arabic (مرحبا), right-to-left text
- **Massive strings:** 1000, 10000, 1000000 character inputs (buffer overflow testing)
- **Special characters:** `\n`, `\r`, `\t`, `\x1b` (ANSI escape sequences)

### Anti-Patterns to Avoid

- **Recreating existing fixtures:** Import from `browser_discovery.conftest` and `e2e_ui.fixtures.auth_fixtures` instead of duplicating
- **Skipping accessibility checks:** All browser discovery tests should include accessibility_checker
- **Exploring without limits:** Always set max_depth and max_actions to prevent infinite loops
- **Ignoring localhost links:** Broken link checker should skip localhost (test environment)
- **Hardcoding viewport sizes:** Use Percy configuration (widths: [375, 768, 1280]) instead of hardcoded values
- **Filling forms randomly without validation:** Verify form accepts/rejects edge cases appropriately
- **Not checking console errors:** Every browser discovery test should use console_monitor fixture

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Browser automation** | Custom Selenium wrappers | Playwright Python 1.58.0 | Auto-waiting, network interception, faster execution |
| **Accessibility testing** | Custom WCAG rule checks | axe-core 4.8.2 | Industry standard, comprehensive WCAG 2.1 AA coverage, active maintenance |
| **Visual regression** | Custom screenshot comparison | Percy (from Phase 236-06) | Cloud hosting, diff UI, team approval workflow, 3-viewport testing |
| **Console error detection** | Custom error logging | page.on("console"), page.on("pageerror") | Playwright built-in event API, captures all error types |
| **Link checking** | Custom HTTP client | requests.head() | Already installed, simple API, timeout handling |
| **Exploration algorithms** | Random clicking only | DFS, BFS, random walk, heuristic-guided | Systematic coverage, reproducible results, configurable depth |
| **Authentication setup** | UI login for every test | API-first auth fixtures (10-100x faster) | authenticated_page fixture bypasses UI login |
| **Bug filing** | Manual GitHub issues | bug_filing_service.py (Phase 236-08) | Automated GitHub Issues API, idempotency, artifact collection |

**Key insight:** Browser discovery should leverage existing Playwright infrastructure and Phase 236/237 investments (Percy, bug filing, auth fixtures) rather than building custom tooling. The only custom code needed is exploration algorithms and test logic for specific bug categories.

## Common Pitfalls

### Pitfall 1: Ignoring Existing Browser Discovery Infrastructure

**What goes wrong:** Duplicating console monitoring, accessibility checking, exploration agent logic that already exists in `browser_discovery/conftest.py`.

**Why it happens:** Developers don't review existing fixtures before implementing new tests.

**How to avoid:**
1. Read `backend/tests/browser_discovery/conftest.py` before writing tests
2. Import existing fixtures: `from tests.browser_discovery.conftest import console_monitor, accessibility_checker, exploration_agent`
3. Extend existing ExplorationAgent class instead of creating new agent

**Warning signs:** New conftest.py files with duplicate console_monitor or accessibility_checker fixtures.

### Pitfall 2: Exploration Without Limits Causes Infinite Loops

**What goes wrong:** Exploration agent navigates in circles (A → B → A → B → ...) or gets stuck in infinite redirect loops.

**Why it happens:** Not tracking visited URLs or setting max_depth/max_actions limits.

**How to avoid:**
1. Always set max_depth (default: 3) to prevent infinite depth exploration
2. Always set max_actions (default: 20) to prevent endless clicking
3. Track visited_urls set to avoid revisiting pages
4. Implement timeout (page.click() timeout=5000) to prevent hanging

**Warning signs:** Test runs for >5 minutes without completion, same URLs visited repeatedly.

### Pitfall 3: Missing Console Errors Due to Race Conditions

**What goes wrong:** Console errors occur before page.on("console") handler is registered, causing false negatives.

**Why it happens:** Registering console handler after page.goto() or waiting for networkidle too late.

**How to avoid:**
1. Use console_monitor fixture (registers handler before page load)
2. Register handlers in fixture setup (yield), not in test body
3. Use page.wait_for_load_state("domcontentloaded") instead of networkidle (console errors can fire during lazy loading)
4. Check console_monitor dict immediately after navigation (before interactions)

**Warning signs:** Console errors manually visible in browser DevTools but not captured in tests.

### Pitfall 4: Accessibility Testing Without axe-core

**What goes wrong:** Custom accessibility checks miss WCAG violations, inconsistent with axe-core results.

**Why it happens:** Developers implement custom ARIA attribute checks instead of using axe-core.

**How to avoid:**
1. Always use accessibility_checker fixture (injects axe-core 4.8.2)
2. Configure runOnly tags: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] for WCAG 2.1 AA
3. Check violations list (not just assertion count) for detailed remediation guidance
4. Graceful degradation: Skip test if axe-core fails to load (network issues, CDN blocked)

**Warning signs:** Custom ARIA checks, missing critical violations (e.g., color-contrast, label).

### Pitfall 5: Broken Link Checking Hangs on Slow/Unresponsive URLs

**What goes wrong:** Link checker hangs indefinitely on external URLs that timeout or redirect loops.

**Why it happens:** Not setting timeout on requests.head() or not detecting redirect loops.

**How to avoid:**
1. Set timeout=5 on requests.head() (skip slow links)
2. Allow redirects (allow_redirects=True) but detect loops (same URL visited >3 times)
3. Skip localhost/127.0.0.1 in test environment (not real URLs)
4. Capture network errors as "broken" (connection refused, DNS failure)

**Warning signs:** Test runs for >10 minutes, "requests.exceptions.Timeout" errors.

### Pitfall 6: Visual Regression Tests Flaky Due to Dynamic Content

**What goes wrong:** Percy snapshots fail due to timestamps, loading spinners, random data changing between runs.

**Why it happens:** Not hiding dynamic content in .percy.yml ignore rules or percy-css.

**How to avoid:**
1. Add dynamic content selectors to .percy.yml ignore: ['.timestamp', '.session-id']
2. Use percy-css to hide dynamic elements: `.timestamp { display: none !important; }`
3. Freeze time with freezegun for time-based content (if可控)
4. Use deterministic test data (no random values, fixed timestamps)

**Warning signs:** Percy diff shows only timestamps/session IDs changed, "flaky" visual tests.

### Pitfall 7: Form Edge Cases Not Sanitized Leading to Security Bugs

**What goes wrong:** XSS payloads, SQL injection, null bytes crash backend or execute malicious code.

**Why it happens:** Form validation only checks for required fields, not edge cases.

**How to avoid:**
1. Test all Phase 237 security payloads (18+ patterns: XSS, SQLi, null bytes, unicode, massive strings)
2. Verify backend rejects or sanitizes payloads (HTTP 400, clear error message)
3. Check DOM for unescaped output: `assert '<script>' not in page.content()`
4. Test null bytes: `\x00` should trigger validation error, not crash

**Warning signs:** Form accepts `<script>alert("XSS")</script>`, console shows 500 error on null byte submission.

## Code Examples

Verified patterns from existing codebase:

### Pattern 1: Console Error Detection (existing fixture)

```python
# Source: backend/tests/browser_discovery/conftest.py
@pytest.fixture(scope="function")
def console_monitor(page: Page) -> Dict[str, List[Dict[str, Any]]]:
    """Monitor JavaScript console for errors and warnings."""
    console_logs: Dict[str, List[Dict[str, Any]]] = {
        "error": [],
        "warning": [],
        "info": [],
        "log": [],
        "debug": [],
    }

    def _handle_console(msg):
        """Handle console message and categorize by type."""
        log_entry = {
            "type": msg.type,
            "text": msg.text,
            "timestamp": datetime.now().isoformat(),
            "url": page.url,
        }

        # Add location if available
        if msg.location:
            log_entry["location"] = {
                "url": msg.location.get("url"),
                "line_number": msg.location.get("lineNumber"),
                "column_number": msg.location.get("columnNumber"),
            }

        # Categorize by message type
        msg_type = msg.type.lower()
        if msg_type in console_logs:
            console_logs[msg_type].append(log_entry)
        else:
            console_logs["log"].append(log_entry)

    # Subscribe to console events
    page.on("console", _handle_console)

    yield console_logs

    # Unsubscribe after test
    page.remove_listener("console", _handle_console)
```

### Pattern 2: Accessibility Testing with axe-core (existing fixture)

```python
# Source: backend/tests/browser_discovery/conftest.py
@pytest.fixture(scope="function")
def accessibility_checker(page: Page):
    """Accessibility checker using axe-core for automated a11y testing."""
    # Inject axe-core library (version 4.8.2 from CDN)
    axe_core_script = """
    (function() {
        return new Promise((resolve, reject) => {
            if (window.axe) {
                resolve(true);
                return;
            }
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.2/axe.min.js';
            script.onload = () => resolve(true);
            script.onerror = () => reject(new Error('Failed to load axe-core'));
            document.head.appendChild(script);
        });
    })();
    """

    def _run_audit() -> List[Dict[str, Any]]:
        """Run axe-core accessibility audit and return violations."""
        # Load axe-core if not already loaded
        page.evaluate(axxe_core_script)

        # Run axe-core audit with WCAG 2.1 AA tags
        results = page.evaluate("""
        async () => {
            try {
                const results = await axe.run(document, {
                    runOnly: {
                        type: 'tag',
                        values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']
                    }
                });
                return results;
            } catch (error) {
                return { error: error.message };
            }
        }
        """)

        if isinstance(results, dict) and "error" in results:
            raise Exception(f"axe-core audit failed: {results['error']}")

        # Extract and format violations
        violations = results.get("violations", [])
        formatted_violations = []
        for violation in violations:
            formatted_violations.append({
                "id": violation["id"],
                "impact": violation["impact"],
                "description": violation["description"],
                "help": violation["help"],
                "help_url": violation["helpUrl"],
                "tags": violation["tags"],
                "nodes": violation["nodes"][:3],  # Limit to first 3 nodes
            })

        return formatted_violations

    return _run_audit
```

### Pattern 3: Intelligent Exploration Agent (existing prototype)

```python
# Source: backend/tests/browser_discovery/conftest.py
class ExplorationAgent:
    """Intelligent UI exploration agent."""

    def __init__(self, page: Page):
        self.page = page
        self.visited_urls = set()
        self.bugs_found = []
        self.actions_taken = []

    def explore(self, max_depth: int = 3, max_actions: int = 20):
        """Explore UI intelligently to discover bugs.

        Args:
            max_depth: Maximum depth to explore (default: 3)
            max_actions: Maximum number of actions to take (default: 20)
        """
        current_url = self.page.url
        if current_url in self.visited_urls:
            return

        self.visited_urls.add(current_url)

        # Find clickable elements using JavaScript evaluation
        clickable = self.page.evaluate("""
        () => {
            const selectors = [
                'button:not([disabled])',
                'a[href]',
                'input[type="submit"]',
                'input[type="button"]',
                '[role="button"]',
            ].join(', ');

            return Array.from(document.querySelectorAll(selectors)).map(el => ({
                tag: el.tagName,
                type: el.type || 'button',
                text: el.textContent?.trim() || '',
                id: el.id || '',
                class: el.className || '',
            }));
        }
        """)

        # Explore first few clickable elements (depth-first)
        for i, element in enumerate(clickable[:max_actions]):
            if i >= max_actions:
                break

            try:
                # Try to click element
                selector = f'{element["tag"]}{f"#{element["id"]}" if element["id"] else ""}'
                self.page.click(selector, timeout=5000)
                self.actions_taken.append(f"Clicked: {selector}")

                # Check for bugs (console errors, broken layout, etc.)
                self._check_for_bugs()

                # Navigate back if page changed (recursive DFS)
                if self.page.url != current_url and max_depth > 0:
                    self.explore(max_depth - 1, max_actions - i)
                    self.page.go_back()
                    self.page.wait_for_load_state("networkidle")

            except Exception as e:
                # Log potential bug (element not clickable, timeout, etc.)
                self.bugs_found.append({
                    "type": "exploration_error",
                    "element": element,
                    "error": str(e),
                    "url": self.page.url,
                })

    def _check_for_bugs(self):
        """Check for common bugs on current page."""
        # Check for console errors
        console_errors = self.page.evaluate("""
        () => {
            return window.__consoleErrors || [];
        }
        """)
        if console_errors:
            self.bugs_found.extend([
                {"type": "console_error", "error": err}
                for err in console_errors
            ])

        # Check for broken images
        broken_images = self.page.evaluate("""
        () => {
            return Array.from(document.querySelectorAll('img')).filter(img =>
                img.naturalWidth === 0 || img.complete === false
            ).map(img => img.src);
        }
        """)
        if broken_images:
            self.bugs_found.append({
                "type": "broken_images",
                "sources": broken_images,
            })

    def get_bugs(self) -> List[Dict[str, Any]]:
        """Get list of bugs found during exploration."""
        return self.bugs_found
```

### Pattern 4: Broken Link Detection (existing fixture)

```python
# Source: backend/tests/browser_discovery/conftest.py
@pytest.fixture(scope="function")
def broken_link_checker(page: Page):
    """Broken link checker for detecting dead links and 404s."""
    def _check_links() -> List[Dict[str, Any]]:
        """Check all links on page and return broken ones."""
        # Find all links using JavaScript evaluation
        links = page.evaluate("""
        () => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            return anchors.map(a => ({
                href: a.href,
                text: a.textContent.trim(),
                url: new URL(a.href, window.location.origin).href
            })).filter(link =>
                link.url.startsWith('http://') ||
                link.url.startsWith('https://')
            );
        }
        """)

        broken_links = []
        import requests

        for link in links:
            try:
                # Skip localhost links in test environment
                if "localhost" in link["url"] or "127.0.0.1" in link["url"]:
                    continue

                # Check link status with 5s timeout
                response = requests.head(link["url"], timeout=5, allow_redirects=True)
                if response.status_code >= 400:
                    broken_links.append({
                        "url": link["url"],
                        "text": link["text"],
                        "status_code": response.status_code,
                    })
            except Exception as e:
                # Link check failed (network error, timeout, etc.)
                broken_links.append({
                    "url": link["url"],
                    "text": link["text"],
                    "error": str(e),
                })

        return broken_links

    return _check_links
```

### Pattern 5: Visual Regression Testing with Percy (existing from Phase 236-06)

```python
# Source: frontend-nextjs/tests/visual/test_visual_regression_dashboard.py
@pytest.mark.e2e
@pytest.mark.visual
def test_visual_dashboard(authenticated_percy_page: Page):
    """Test visual appearance of dashboard page."""
    from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

    # Navigate to dashboard
    authenticated_percy_page.goto("http://localhost:3001/dashboard")
    authenticated_percy_page.wait_for_load_state("networkidle")

    # Take Percy snapshot (captures 3 widths: 375, 768, 1280 per .percy.yml)
    percy_snapshot(authenticated_percy_page, "Dashboard")

    # Verify dashboard layout elements
    expect(authenticated_percy_page.locator("h1")).to_be_visible()
    expect(authenticated_percy_page.locator("nav")).to_be_visible()
```

**Percy configuration (.percy.yml from Phase 236-06):**
```yaml
version: 2
snapshot:
  widths: [375, 768, 1280]  # Mobile, tablet, desktop
  min-height: 1024
  percy-css: |
    /* Hide dynamic content */
    .timestamp { display: none !important; }
    .session-id { display: none !important; }
    .loading-spinner { opacity: 0 !important; }
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Custom accessibility checks** | axe-core 4.8.2 WCAG 2.1 AA compliance | Phase 237 (browser_discovery/conftest.py) | Comprehensive a11y testing, industry standard, detailed violation reports |
| **Manual screenshot comparison** | Percy cloud visual regression | Phase 236-06 (completed) | Team approval workflow, 3-viewport testing, diff UI, 78+ snapshots |
| **Random clicking for exploration** | DFS, BFS, random walk, heuristic-guided algorithms | Phase 240 (planned) | Systematic coverage, reproducible results, configurable depth/actions |
| **Basic console.log() checking** | page.on("console") + page.on("pageerror") event handlers | Phase 237 (browser_discovery/conftest.py) | Captures all error types, metadata (timestamp, location), structured logging |
| **Manual link checking** | Automated requests.head() status code checking | Phase 237 (browser_discovery/conftest.py) | Detects 404s, 500s, redirect loops, timeout handling |
| **UI login for tests** | API-first authentication (JWT in localStorage) | Phase 234 (e2e_ui/fixtures/) | 10-100x faster test setup, 91 E2E tests use this pattern |

**Deprecated/outdated:**
- **Custom Selenium wrappers**: Use Playwright Python 1.58.0 instead (auto-waiting, faster execution)
- **Manual visual regression**: Use Percy (from Phase 236-06) instead of custom screenshot comparison
- **Random exploration without limits**: Always set max_depth and max_actions to prevent infinite loops
- **UI-based authentication**: Use authenticated_page fixture (API-first, 10-100x faster)

## Open Questions

1. **Exploration algorithm effectiveness**
   - What we know: DFS, BFS, random walk algorithms exist in computer science literature
   - What's unclear: Which algorithm provides best bug discovery rate for Atom's UI architecture
   - Recommendation: Implement all three algorithms (DFS, BFS, random walk) and compare bug discovery rates in Phase 240 execution

2. **Percy baseline management**
   - What we know: 78+ snapshots from Phase 236-06 exist in Percy cloud
   - What's unclear: How to manage baselines when UI changes intentionally (feature additions, redesigns)
   - Recommendation: Use Percy "approve all" workflow for intentional changes, document baseline update process in README

3. **Accessibility violation prioritization**
   - What we know: axe-core provides impact levels (critical, serious, moderate, minor)
   - What's unclear: Should all WCAG 2.1 AA violations block deployment or only critical/serious?
   - Recommendation: Block deployment on critical/serious violations, warn on moderate/minor (configurable via pytest markers)

4. **Console error tolerance**
   - What we know: Console errors always indicate bugs (JavaScript errors, uncaught exceptions)
   - What's unclear: Should warnings be treated as errors (deprecation notices, third-party library warnings)?
   - Recommendation: Fail tests on console errors, log warnings but don't fail (configurable via --strict-warnings flag)

5. **Exploration agent timeout configuration**
   - What we know: max_depth=3, max_actions=20 are reasonable defaults
   - What's unclear: Optimal timeout values for different page types (dashboard vs complex forms)
   - Recommendation: Start with 5s timeout per action, increase to 10s for complex forms, make configurable via pytest fixtures

## Sources

### Primary (HIGH confidence)
- **backend/tests/browser_discovery/conftest.py** - Browser discovery fixtures (console_monitor, accessibility_checker, exploration_agent, broken_link_checker, visual_regression_checker) with complete implementation
- **frontend-nextjs/tests/visual/** - Percy visual regression tests from Phase 236-06 (26 tests, 78+ screenshots, 5 page groups)
- **.percy.yml** - Percy configuration with widths [375, 768, 1280], ignore rules, allowed-hostnames
- **backend/tests/e2e_ui/fixtures/auth_fixtures.py** - API-first authentication fixtures (authenticated_page, 10-100x faster than UI login)
- **backend/requirements.txt** - Playwright Python 1.58.0, pytest-playwright 0.5.2
- **pytest.ini** - Pytest markers (browser_discovery, accessibility, visual_regression, broken_links)

### Secondary (MEDIUM confidence)
- **Playwright Python documentation** (playwright.dev/python) - page.on("console"), page.on("pageerror") event API, page.evaluate() JavaScript execution
- **axe-core documentation** (dequeuniversity.com/rules/axe) - WCAG 2.1 AA rule documentation, violation remediation guidance
- **Percy documentation** (docs.percy.io) - Percy CLI usage, snapshot configuration, ignore rules, width configuration
- **pytest-playwright plugin** (pytest-playwright.readthedocs.io) - Pytest fixture integration, browser/page/context fixtures

### Tertiary (LOW confidence)
- **Web search limitations** - Weekly/monthly search limit exhausted, unable to verify 2026 best practices for exploration algorithms
- **General knowledge of web crawling algorithms** - DFS, BFS, random walk patterns from computer science literature (verified against existing conftest.py implementation)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already installed and in use (Playwright 1.58.0, axe-core 4.8.2, Percy from Phase 236-06), verified against requirements.txt and codebase
- Architecture: HIGH - Existing fixtures well-documented in conftest.py (692 lines), Percy integration complete from Phase 236-06 (26 tests, 78+ screenshots)
- Pitfalls: HIGH - Common pitfalls identified from existing conftest.py implementation patterns (console handler timing, exploration limits, accessibility testing)
- Exploration algorithms: MEDIUM - DFS/BFS/random walk patterns documented in computer science literature, but effectiveness for UI bug discovery untested in Atom context (validation needed in Phase 240 execution)

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (30 days - stable Playwright/axe-core/Percy ecosystem, mature projects with slow API changes)
