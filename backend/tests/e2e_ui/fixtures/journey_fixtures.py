"""
Fixtures for the realistic user-journey E2E suite.

These fixtures do API-first setup against the running full backend on port
8001: register a unique user, log in to obtain a JWT, and inject it into the
Playwright browser localStorage so the journey can start on an authenticated
page without paying the UI-login cost for every test.

The canonical full-journey test instead logs in through the UI once (to also
exercise that flow) using the `journey_user` + `journey_user_credentials`
fixtures.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict

import pytest
import requests
from playwright.sync_api import Browser, Page


BACKEND_URL = (os.getenv("BACKEND_URL") or "http://localhost:8001").rstrip("/")
FRONTEND_URL = (os.getenv("FRONTEND_URL") or "http://localhost:3001").rstrip("/")
DEFAULT_PASSWORD = "TestPassword123!"


def _register_and_login(email: str, password: str) -> Dict[str, Any]:
    """Register a user and return {email, password, access_token}."""
    requests.post(
        f"{BACKEND_URL}/api/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Journey",
            "last_name": "Test",
        },
        timeout=15,
    ).raise_for_status()
    login = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        json={"username": email, "password": password},
        timeout=15,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    return {"email": email, "password": password, "access_token": token}


@pytest.fixture(scope="function")
def journey_user_credentials() -> Dict[str, str]:
    """Create a unique user via API and return email + password + token."""
    email = f"journey_{uuid.uuid4().hex[:8]}@example.com"
    return _register_and_login(email, DEFAULT_PASSWORD)


@pytest.fixture(scope="function")
def journey_user(journey_user_credentials: Dict[str, str]) -> Dict[str, str]:
    """Alias kept for readability in tests that need the user identity."""
    return journey_user_credentials


def _inject_token(page: Page, token: str) -> None:
    """Inject the JWT into localStorage so the app treats the session as authed."""
    page.goto(FRONTEND_URL, wait_until="domcontentloaded")
    page.evaluate(
        """(token) => {
            localStorage.setItem('auth_token', token);
            localStorage.setItem('access_token', token);
        }""",
        token,
    )


@pytest.fixture(scope="function")
def authed_page(browser: Browser, journey_user_credentials: Dict[str, str]) -> Page:
    """An authenticated Playwright page.

    Performs a real UI login so that BOTH the localStorage `auth_token` (used
    by direct-backend-call pages) AND the next-auth session cookie (used by
    session-gated pages like /chat) are established. API-only token injection
    is insufficient because several pages gate on the next-auth session.
    """
    creds = journey_user_credentials
    context = browser.new_context()
    page = context.new_page()
    # UI login — establishes next-auth session + localStorage auth_token.
    page.goto(f"{FRONTEND_URL}/login", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("[data-testid='login-email-input']", timeout=10000)
    except Exception:
        page.wait_for_selector("input#email", timeout=10000)
    page.locator("[data-testid='login-email-input'], input#email").first.fill(creds["email"])
    page.locator("[data-testid='login-password-input'], input#password").first.fill(creds["password"])
    page.locator("[data-testid='login-submit-button'], button[type='submit']").first.click()
    try:
        page.wait_for_url("**/dashboard**", timeout=20000)
    except Exception:
        # If login didn't redirect, the test assertions will surface the real
        # problem; don't fail at fixture setup.
        pass
    yield page
    try:
        context.close()
    except Exception:
        pass


@pytest.fixture(scope="function")
def journey_api_headers(journey_user_credentials: Dict[str, str]) -> Dict[str, str]:
    """Authorization headers for direct backend API calls from tests."""
    return {
        "Authorization": f"Bearer {journey_user_credentials['access_token']}",
        "Content-Type": "application/json",
    }


# ============================================================================
# Role-based fixtures (all 8 UserRole values)
# ============================================================================
#
# The backend reads the user's role from the DB at request time (the JWT only
# carries the user id), so we register a user and then UPDATE its role in the
# SQLite DB directly. The next request with that user's token sees the new role.
#
# Roles (backend/core/models.py UserRole): super_admin, owner, admin,
# workspace_admin, team_lead, member, viewer, guest.
#
# RBAC (backend/core/rbac_service.py): only guest/member/team_lead/
# workspace_admin/super_admin have explicit permission mappings. owner/admin/
# viewer fall through to an EMPTY permission set — likely a bug, surfaced by
# these fixtures. The parametrized permission-matrix journey will document it.

ALL_ROLES = [
    "super_admin",
    "owner",
    "admin",
    "workspace_admin",
    "team_lead",
    "member",
    "viewer",
    "guest",
]


def _set_user_role(email: str, role: str) -> None:
    """Update a user's role directly in the SQLite DB.

    Resolves the active atom_dev.db the SAME way the backend does: honor
    DATABASE_URL when it points at sqlite, otherwise default to the
    repo-root atom_dev.db (the backend runs with cwd = repo root).
    """
    import sqlite3
    from urllib.parse import urlparse

    db_url = os.getenv("DATABASE_URL", "")
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

    db_path = None
    if db_url.startswith("sqlite:///"):
        raw = db_url[len("sqlite:///"):]
        path_only = raw.split("?")[0]
        db_path = path_only if os.path.isabs(path_only) else os.path.join(repo_root, path_only)

    if not db_path or not os.path.exists(db_path):
        # Backend default when DATABASE_URL is unset/relative: repo-root atom_dev.db
        db_path = os.path.join(repo_root, "atom_dev.db")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE users SET role = ? WHERE email = ?", (role, email))
        conn.commit()
    finally:
        conn.close()


def _register_role_user(role: str) -> Dict[str, Any]:
    """Register a user, set its role, and return credentials with a token."""
    email = f"role_{role}_{uuid.uuid4().hex[:8]}@example.com"
    requests.post(
        f"{BACKEND_URL}/api/auth/register",
        json={"email": email, "password": DEFAULT_PASSWORD, "first_name": role.title(), "last_name": "Role"},
        timeout=15,
    ).raise_for_status()
    _set_user_role(email, role)
    login = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        json={"username": email, "password": DEFAULT_PASSWORD},
        timeout=15,
    )
    login.raise_for_status()
    return {"email": email, "password": DEFAULT_PASSWORD, "access_token": login.json()["access_token"], "role": role}


@pytest.fixture(scope="function")
def role_credentials(request) -> Dict[str, Any]:
    """Parametrized: create a user with the role set by `request.param`.

    Usage:
        @pytest.mark.parametrize("role_credentials", ALL_ROLES, indirect=True)
        def test_x(role_credentials): ...
    """
    return _register_role_user(request.param)


def role_headers_factory(role: str) -> Dict[str, Any]:
    """Factory used by tests that need an ad-hoc role's headers (no fixture)."""
    return _register_role_user(role)


@pytest.fixture(scope="function")
def all_role_headers() -> Dict[str, Dict[str, str]]:
    """Create ONE user per role and return {role: Authorization headers}.

    Expensive (8 registrations) but lets a single permission-matrix test hit
    every role without per-param fixture setup overhead.
    """
    result: Dict[str, Dict[str, str]] = {}
    for role in ALL_ROLES:
        creds = _register_role_user(role)
        result[role] = {
            "Authorization": f"Bearer {creds['access_token']}",
            "Content-Type": "application/json",
        }
    return result


@pytest.fixture(scope="function")
def role_authed_page(browser: Browser, role_credentials: Dict[str, Any]) -> Page:
    """A Playwright page logged in as the parametrized role.

    Pairs with the `role_credentials` indirect fixture:
        @pytest.mark.parametrize("role_credentials", ALL_ROLES, indirect=True)
        def test_x(role_credentials, role_authed_page): ...

    Performs a real UI login so both localStorage auth_token AND the next-auth
    session cookie are established for the role's user.
    """
    creds = role_credentials
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{FRONTEND_URL}/login", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("[data-testid='login-email-input']", timeout=10000)
    except Exception:
        page.wait_for_selector("input#email", timeout=10000)
    page.locator("[data-testid='login-email-input'], input#email").first.fill(creds["email"])
    page.locator("[data-testid='login-password-input'], input#password").first.fill(creds["password"])
    page.locator("[data-testid='login-submit-button'], button[type='submit']").first.click()
    try:
        page.wait_for_url("**/dashboard**", timeout=20000)
    except Exception:
        pass
    yield page
    try:
        context.close()
    except Exception:
        pass
