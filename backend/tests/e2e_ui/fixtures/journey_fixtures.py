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
