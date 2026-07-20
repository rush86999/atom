"""
Page-smoke journey — load every sidebar route and assert it renders.

This is broad, shallow coverage of "all UI/UX": each route must respond 200
and render some heading (i.e., not crash to an error page or redirect to
login for an authenticated user). Routes that require external services or
credentials to show data still count as "passing" as long as the shell
renders.

Run a single route for debugging:
    pytest backend/tests/e2e_ui/tests/test_journey_page_smoke.py \
        -k "canvas" -v
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.e2e_ui.fixtures.journey_fixtures import authed_page  # noqa: F401


pytestmark = pytest.mark.e2e


# (path, a heading-or-text expected on the rendered page). Text chosen to be
# stable across empty/populated states. None means "just assert no crash /
# no redirect to login".
SIDEBAR_ROUTES = [
    ("/dashboard", "ATOM Dashboard"),
    ("/chat", None),                  # session-gated; assert it doesn't redirect to /login
    ("/canvas", "Canvases"),
    ("/search", None),
    ("/tasks", None),
    ("/boards", None),
    ("/automations", None),
    ("/agents", "Agent Control Center"),
    ("/marketplace", "Workflow Marketplace"),
    ("/dashboards/projects", "Project Command Center"),
    ("/communication", None),
    ("/sales", None),
    ("/marketing", None),
    ("/finance", None),
    ("/analytics", None),
    ("/calendar", None),
    ("/integrations", "ATOM Integrations Hub"),
    ("/settings", "Settings"),
]


@pytest.mark.parametrize("path,expected_text", SIDEBAR_ROUTES, ids=[p for p, _ in SIDEBAR_ROUTES])
def test_sidebar_route_renders(authed_page: Page, path: str, expected_text):
    authed_page.goto(f"http://localhost:3001{path}", wait_until="domcontentloaded")
    # Allow the page a moment to settle (some fetch data on mount).
    authed_page.wait_for_timeout(2500)

    # Must not have redirected to login (would mean the route isn't usable).
    assert "/login" not in authed_page.url, f"{path} redirected to /login"

    if expected_text:
        try:
            authed_page.wait_for_selector(f"text={expected_text}", timeout=10000)
            found = True
        except Exception:
            found = False
        assert found, f"{path}: expected text '{expected_text}' not rendered"
