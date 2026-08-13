"""
Network simulation fixtures for E2E testing.

This module provides Playwright-based network simulation capabilities including:
- Slow 3G connection throttling
- Offline mode simulation
- API timeout injection
- Database connection drop simulation

Fixtures use Playwright's context.route() and context.offline APIs for
network interception without requiring environment variable changes.

Run with: pytest backend/tests/e2e_ui/tests/test_network_*.py -v
"""

import os
import subprocess
import time
from typing import Callable, Tuple
from playwright.sync_api import Browser, Page, BrowserContext
import pytest

# Add backend to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


# =============================================================================
# Slow 3G Connection Fixture
# =============================================================================

@pytest.fixture(scope="function")
def slow_3g_context(browser: Browser) -> BrowserContext:
    """Create a Playwright context with slow 3G network throttling.

    Simulates slow 3G connection with:
    - Download: 500 Kbps (~62.5 KB/s)
    - Upload: 500 Kbps (~62.5 KB/s)
    - Latency: 400ms (RTT)

    This fixture is useful for testing:
    - Login flow under poor network conditions
    - Agent execution with delayed responses
    - Canvas rendering with slow loading
    - Error messages during slow operations

    Args:
        browser: Playwright browser fixture (session-scoped)

    Yields:
        BrowserContext: Playwright context with slow 3G throttling

    Example:
        def test_slow_3g_login(slow_3g_context):
            page = slow_3g_context.new_page()
            page.goto("http://localhost:3001/login")
            # Login will take 5-10 seconds due to throttling
    """
    # Create context with slow 3G throttling profile
    context = browser.new_context(
        offline=False,
        # Slow 3G profile: 500 Kbps down/up, 400ms latency
        # Based on Chrome DevTools "Slow 3G" preset
    )

    # Apply network throttling using Chrome DevTools Protocol
    # This is the most reliable way to throttle network in Playwright
    try:
        cdp = context.new_cdp_session(context.page)
        cdp.send("Network.emulateNetworkConditions", {
            "offline": False,
            "downloadThroughput": 500 * 1024 / 8,  # 500 Kbps in bytes/s
            "uploadThroughput": 500 * 1024 / 8,     # 500 Kbps in bytes/s
            "latency": 400                           # 400ms RTT
        })
    except Exception as e:
        # Fallback: CDP not available, continue without throttling
        # (Some browser configurations don't support CDP)
        print(f"Warning: Could not apply network throttling: {e}")

    yield context

    # Cleanup: close context
    context.close()


# =============================================================================
# Offline Mode Fixture
# =============================================================================

@pytest.fixture(scope="function")
def offline_mode_context(browser: Browser) -> Tuple[BrowserContext, Callable, Callable]:
    """Create a Playwright context with offline mode control functions.

    This fixture provides control functions to simulate network disconnection
    and reconnection during test execution. Useful for testing:
    - Offline error messages during login/agent execution
    - Network reconnection recovery
    - Session persistence after offline period

    Args:
        browser: Playwright browser fixture (session-scoped)

    Yields:
        Tuple[BrowserContext, Callable, Callable]:
            - context: Playwright browser context
            - go_offline: Function to enable offline mode
            - come_online: Function to disable offline mode

    Example:
        def test_offline_login(offline_mode_context):
            context, go_offline, come_online = offline_mode_context
            page = context.new_page()
            page.goto("http://localhost:3001/login")

            # Go offline and try to login
            go_offline()
            page.fill("input[name='email']", "test@example.com")
            page.click("button[type='submit']")
            # Verify error message appears

            # Come back online and verify login works
            come_online()
            page.click("button[type='submit']")
            # Verify successful login
    """
    # Create normal context (online by default)
    context = browser.new_context(offline=False)

    def go_offline() -> None:
        """Enable offline mode (simulate network disconnection)."""
        # BUG-FIX (2026-08-13): the old code called
        # context._impl_obj._set_offline(True) FIRST and nested the CDP
        # fallback INSIDE the same try. _set_offline doesn't exist in the
        # current Playwright version and raised AttributeError, which jumped
        # straight to the outer except and skipped the CDP emulation — so
        # "offline" never actually applied and the tests ran fully online.
        # CDP Network.emulateNetworkConditions is the reliable mechanism
        # (verified: fetch() rejects with "Failed to fetch" while offline).
        try:
            page = context.pages[0] if context.pages else context.new_page()
            cdpsession = context.new_cdp_session(page)
            cdpsession.send("Network.emulateNetworkConditions", {
                "offline": True,
                "downloadThroughput": 0,
                "uploadThroughput": 0,
                "latency": 0
            })
        except Exception as e:
            print(f"Warning: Could not enable offline mode: {e}")

    def come_online() -> None:
        """Disable offline mode (simulate network reconnection)."""
        try:
            page = context.pages[0] if context.pages else context.new_page()
            cdpsession = context.new_cdp_session(page)
            cdpsession.send("Network.emulateNetworkConditions", {
                "offline": False,
                "downloadThroughput": -1,  # -1 = no throttling
                "uploadThroughput": -1,
                "latency": 0
            })
        except Exception as e:
            print(f"Warning: Could not disable offline mode: {e}")

    yield context, go_offline, come_online

    # Cleanup: ensure we're back online before closing
    try:
        come_online()
    except Exception:
        pass

    context.close()


# =============================================================================
# API Timeout Fixture
# =============================================================================

@pytest.fixture(scope="function")
def timeout_api_context(browser: Browser) -> BrowserContext:
    """Create a Playwright context with API timeout injection.

    This fixture intercepts specific API endpoints and adds a 30-second delay
    to simulate server-side timeout conditions. Useful for testing:
    - Timeout error messages
    - Client-side timeout handling
    - Retry logic
    - UI responsiveness during long requests

    Intercepted endpoints:
    - /api/v1/agents/execute (agent execution timeout)
    - /api/v1/canvas/present (canvas presentation timeout)

    Args:
        browser: Playwright browser fixture (session-scoped)

    Yields:
        BrowserContext: Playwright context with API timeout injection

    Example:
        def test_api_timeout(timeout_api_context):
            page = timeout_api_context.new_page()
            page.goto("http://localhost:3001/agents")
            page.click("button:has-text('Execute')")
            # After 30s, verify timeout error message appears
    """
    # Create context
    context = browser.new_context()

    # List of endpoints to intercept with timeout
    timeout_endpoints = [
        "**/api/v1/agents/execute",
        "**/api/v1/canvas/present",
        "**/api/v1/workflows/execute",
    ]

    def add_timeout_to_page(page: Page):
        """Add timeout interception to a specific page."""
        def timeout_handler(route):
            # Delay for 30 seconds before continuing
            time.sleep(30)
            route.continue_()

        for endpoint in timeout_endpoints:
            page.route(endpoint, timeout_handler)

    # Add timeout to default page
    if context.pages:
        add_timeout_to_page(context.pages[0])

    # Store function to add timeout to new pages
    context._add_timeout_to_page = add_timeout_to_page

    yield context

    # Cleanup: close context
    context.close()


# =============================================================================
# Database Drop Simulation Fixture
# =============================================================================

@pytest.fixture(scope="function")
def database_drop_simulation(browser: Browser, base_url: str) -> Tuple[Page, Callable, Callable]:
    """Create database connection drop simulation with control functions.

    This fixture provides control functions to simulate database connection
    drops and restoration during test execution. Useful for testing:
    - Database connection error messages
    - Automatic reconnection logic
    - Connection pool exhaustion handling
    - Graceful degradation when database unavailable

    NOTE: This fixture uses different strategies based on database type:
    - SQLite: Temporarily locks database file
    - PostgreSQL: Stops/starts database service (requires sudo/systemd)

    Args:
        browser: Playwright browser fixture (session-scoped)
        base_url: Base URL fixture

    Yields:
        Tuple[Page, Callable, Callable]:
            - page: Playwright page object
            - simulate_db_drop: Function to simulate database drop
            - restore_db: Function to restore database connection

    Example:
        def test_database_drop(database_drop_simulation):
            page, simulate_drop, restore_db = database_drop_simulation
            page.goto(f"{base_url}/login")

            # Drop database and try to login
            simulate_drop()
            page.fill("input[name='email']", "test@example.com")
            page.click("button[type='submit']")
            # Verify database error message

            # Restore database and retry
            restore_db()
            page.click("button[type='submit']")
            # Verify successful login
    """
    # Create page
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url)

    # Detect database type from environment
    database_url = os.getenv("DATABASE_URL", "")
    is_postgresql = "postgresql" in database_url or "postgres" in database_url
    is_sqlite = "sqlite" in database_url

    # SQLite-specific state
    sqlite_db_path = None
    original_db_perms = None

    def simulate_db_drop() -> bool:
        """Simulate database connection drop.

        Returns:
            bool: True if the drop simulation actually took effect (verified
            by probing a fresh connection's write path), False otherwise —
            e.g. chmod'ing a SQLite file read-only does NOT break a live
            backend whose connection pool already holds open file
            descriptors; macOS also lets existing FDs keep writing.
        """
        nonlocal sqlite_db_path, original_db_perms

        if is_sqlite:
            # Strategy 1: Lock SQLite database file
            # Extract database path from DATABASE_URL
            if "sqlite:///" in database_url:
                sqlite_db_path = database_url.replace("sqlite:///", "")

                # BUG-FIX (2026-08-13): never chmod the SQLite file when a
                # LIVE backend shares it (ATOM_E2E_PRESERVE_DB=1). SQLite
                # decides read-only at connection OPEN time, so connections
                # the backend opens during the chmod window stay read-only
                # FOREVER (even after restore) — poisoning its QueuePool
                # (pool_recycle=3600s) and 500ing every subsequent
                # register/login until the pool recycles. The failure-path
                # assertions are simply not testable against a live shared
                # backend; tests skip via the return value instead.
                if os.getenv("ATOM_E2E_PRESERVE_DB", "0") == "1":
                    print(
                        "Skipping SQLite chmod: ATOM_E2E_PRESERVE_DB=1 "
                        "(live backend shares this DB — chmod would poison "
                        "its connection pool)"
                    )
                    return False

                if not os.path.isabs(sqlite_db_path):
                    # Relative path, resolve from backend directory
                    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    sqlite_db_path = os.path.join(backend_dir, sqlite_db_path)

                if os.path.exists(sqlite_db_path):
                    # Remove write permissions to lock database
                    original_db_perms = os.stat(sqlite_db_path).st_mode
                    os.chmod(sqlite_db_path, 0o444)  # Read-only
                    print(f"Locked SQLite database: {sqlite_db_path}")

                # Verify the drop took effect for NEW connections: a fresh
                # engine opening the chmod'ed file must NOT be able to write.
                try:
                    import sqlalchemy as _sa
                    from sqlalchemy import text as _text
                    probe_engine = _sa.create_engine(database_url)
                    with probe_engine.connect() as conn:
                        conn.execute(_text("CREATE TABLE _db_drop_probe (x INTEGER)"))
                        conn.execute(_text("DROP TABLE _db_drop_probe"))
                        conn.commit()
                    # Writes still work -> the drop simulation did not apply.
                    return False
                except Exception:
                    return True
            return False

        elif is_postgresql:
            # Strategy 2: Stop PostgreSQL service (requires systemd/sudo)
            # This will only work in CI/CD with proper permissions
            try:
                subprocess.run(
                    ["pg_ctl", "stop", "-D", "/usr/local/var/postgresql"],  # macOS Homebrew path
                    capture_output=True,
                    timeout=10
                )
                print("Stopped PostgreSQL service")
                return True
            except FileNotFoundError:
                # pg_ctl not found, try systemctl (Linux)
                try:
                    subprocess.run(
                        ["sudo", "systemctl", "stop", "postgresql"],
                        capture_output=True,
                        timeout=10
                    )
                    print("Stopped PostgreSQL service via systemctl")
                    return True
                except Exception as e:
                    print(f"Warning: Could not stop PostgreSQL: {e}")
                    return False
            except Exception as e:
                print(f"Warning: Could not stop PostgreSQL: {e}")
                return False
        else:
            # Fallback: No database-specific action
            # Tests should skip if database type not supported
            pytest.skip(f"Database drop simulation not implemented for: {database_url}")
            return False

    def restore_db() -> None:
        """Restore database connection."""
        nonlocal sqlite_db_path, original_db_perms

        if is_sqlite and sqlite_db_path and original_db_perms:
            # Restore SQLite database permissions
            try:
                os.chmod(sqlite_db_path, original_db_perms)
                print(f"Unlocked SQLite database: {sqlite_db_path}")
            except Exception as e:
                print(f"Warning: Could not restore SQLite database: {e}")

        elif is_postgresql:
            # Restart PostgreSQL service
            try:
                subprocess.run(
                    ["pg_ctl", "start", "-D", "/usr/local/var/postgresql"],
                    capture_output=True,
                    timeout=10
                )
                print("Started PostgreSQL service")
                # Wait for database to be ready
                time.sleep(2)
            except FileNotFoundError:
                try:
                    subprocess.run(
                        ["sudo", "systemctl", "start", "postgresql"],
                        capture_output=True,
                        timeout=10
                    )
                    print("Started PostgreSQL service via systemctl")
                    time.sleep(2)
                except Exception as e:
                    print(f"Warning: Could not start PostgreSQL: {e}")
            except Exception as e:
                print(f"Warning: Could not start PostgreSQL: {e}")

    yield page, simulate_db_drop, restore_db

    # Cleanup: ensure database is restored
    try:
        restore_db()
    except Exception:
        pass

    # Cleanup: close page and context
    page.close()
    context.close()


# =============================================================================
# Network Condition Helper Functions
# =============================================================================

def set_auth_cookie(context: BrowserContext, base_url: str, token: str) -> None:
    """Set the auth_token cookie required by the Next.js auth middleware.

    frontend-nextjs/middleware.ts gates every non-public route on the
    auth_token cookie (set by lib/auth.ts on real login). localStorage alone
    is NOT enough — without the cookie, navigating to /dashboard or /agents
    bounces to /login?callbackUrl=... This helper must be called after a JWT
    is injected into localStorage by the network test helpers.

    Args:
        context: Playwright browser context
        base_url: Frontend base URL (e.g. http://localhost:3001)
        token: JWT access token
    """
    context.add_cookies([
        {"name": "auth_token", "value": token, "url": f"{base_url}/"},
    ])


def hide_nextjs_overlays(page: Page) -> None:
    """Hide Next.js dev-mode overlays that intercept pointer events.

    The Next.js 16 dev-tools floating button (``<nextjs-portal>``) is an
    absolutely-positioned full-viewport element that swallows clicks in dev
    mode. CSS-hiding it keeps form clicks deterministic without touching app
    code.

    Two mechanisms, because the overlay can mount at any time (hydration,
    HMR websocket drops, webpack recompiles):
    1. context.add_init_script — the kill-CSS + a MutationObserver run on
       EVERY new document, so portals are removed at birth after
       navigations.
    2. An immediate evaluate on the CURRENT document — add_init_script does
       NOT run on documents that are already loaded, so the current page
       gets the same style + observer injected directly.
    """
    # IMPORTANT: hide via CSS (display:none), never el.remove(). Next.js's
    # dev overlay re-mounts the portal when its HMR websocket drops (go
    # offline!) and retries — remove() fights the remount and can spin a
    # mount→remove→mount loop that pegs the page's JS thread and hangs
    # context.close() in teardown forever. display:none is idempotent and
    # does not mutate the DOM tree, so the observer settles immediately.
    KILL_JS = """
        const style = document.createElement('style');
        style.textContent = 'nextjs-portal, .nextjs-portal { display: none !important; }';
        (document.head || document.documentElement).appendChild(style);
        const hide = () => {
            document.querySelectorAll('nextjs-portal, .nextjs-portal')
                .forEach(el => { el.style.display = 'none'; });
        };
        hide();
        new MutationObserver(hide).observe(
            document.documentElement, {childList: true, subtree: true});
    """
    try:
        context = page.context
        context.add_init_script(KILL_JS)
    except Exception:
        pass
    try:
        page.evaluate(KILL_JS)
    except Exception:
        pass


def verify_network_error(page: Page) -> bool:
    """Verify that a network error message is visible on the page.

    Checks for common network error indicators:
    - "Network error" text
    - "Connection failed" text
    - "Offline" text
    - Error toast/notification

    Args:
        page: Playwright page object

    Returns:
        bool: True if network error detected, False otherwise
    """
    try:
        # Check for common error messages
        error_texts = [
            "Network error",
            "Connection failed",
            "Offline",
            "Unable to connect",
            "Service unavailable",
            "Connection refused",
        ]

        for error_text in error_texts:
            if page.locator(f"text={error_text}").count() > 0:
                return True

        # Check for error toast/notification (common UI pattern)
        error_selectors = [
            "[role='alert']",
            ".error-message",
            ".toast-error",
            ".notification-error",
        ]

        for selector in error_selectors:
            if page.locator(selector).count() > 0:
                return True

        return False

    except Exception:
        return False


def wait_for_network_error(page: Page, timeout: int = 5000) -> None:
    """Wait for a network error to appear on the page.

    Args:
        page: Playwright page object
        timeout: Maximum time to wait in milliseconds (default: 5000ms)

    Raises:
        TimeoutError: If no network error appears within timeout
    """
    start_time = time.time()
    timeout_sec = timeout / 1000

    while time.time() - start_time < timeout_sec:
        if verify_network_error(page):
            return
        time.sleep(0.1)

    raise TimeoutError(f"Network error not found within {timeout}ms")


# =============================================================================
# Fixture Registration
# =============================================================================

# This module's fixtures are automatically available via conftest.py imports
# No additional registration needed
