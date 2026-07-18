"""
Per-role UI journeys — log in as each of the 8 roles and verify the pages
each role can reach in the browser, plus that login works for every role.

These are browser-driven and complement the API permission matrix: they
cover the UI/UX a real user of each role experiences, not just the API
behavior. A role that can't log in, or that sees a broken dashboard, is a
real-world blocker this surfaces.

Roles (backend/core/models.py UserRole):
  super_admin, owner, admin, workspace_admin, team_lead, member, viewer, guest

We assert the invariants that hold for EVERY authenticated role:
  - login succeeds and lands on /dashboard
  - the dashboard renders its heading
  - protected pages the role should see (per the sidebar) render without
    redirecting back to /login

Role-specific allow/deny of *data* is covered by the permission matrix
(test_journey_permission_matrix.py); this file covers the UI shell.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.e2e_ui.fixtures.journey_fixtures import (  # noqa: F401
    ALL_ROLES,
    role_credentials,
)
from tests.e2e_ui.pages.journey_pages import (
    AuthPage,
    DashboardJourneyPage,
)


pytestmark = pytest.mark.e2e


# Pages every authenticated role should be able to load (the role's access to
# the *data* on these pages is enforced by the API; the page shell should
# always render rather than bounce to /login).
ROLE_SHARED_PAGES = [
    ("/dashboard", "ATOM Dashboard"),
    ("/settings", "Settings"),
    ("/agents", "Agent Control Center"),
    ("/canvas", "Canvases"),
]


@pytest.mark.parametrize("role_credentials", ALL_ROLES, indirect=True)
def test_every_role_can_log_in(role_credentials, page: Page):
    """Every defined role must be able to log in via the UI and reach the
    dashboard. A role that can't authenticate is a real-world blocker."""
    creds = role_credentials
    auth = AuthPage(page)
    auth.navigate()
    assert auth.is_loaded(), f"{creds['role']}: login page did not load"
    auth.login(creds["email"], creds["password"], expect_redirect=True)
    assert DashboardJourneyPage(page).is_loaded(), (
        f"{creds['role']}: did not reach dashboard after login"
    )


@pytest.mark.parametrize("role_credentials", ALL_ROLES, indirect=True)
@pytest.mark.parametrize("path,expected_text", ROLE_SHARED_PAGES, ids=[p for p, _ in ROLE_SHARED_PAGES])
def test_every_role_can_load_shared_pages(role_credentials, role_authed_page: Page, path: str, expected_text: str):
    """Every role should be able to load the shared authenticated pages
    without being bounced to /login."""
    role_authed_page.goto(f"http://localhost:3001{path}", wait_until="domcontentloaded")
    role_authed_page.wait_for_timeout(2000)
    assert "/login" not in role_authed_page.url, (
        f"{role_credentials['role']}: {path} redirected to /login"
    )
    try:
        role_authed_page.wait_for_selector(f"text={expected_text}", timeout=10000)
        found = True
    except Exception:
        found = False
    assert found, (
        f"{role_credentials['role']}: {path} did not render '{expected_text}'"
    )
