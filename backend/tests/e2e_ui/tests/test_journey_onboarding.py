"""First-run onboarding completion through the ordinary UI.

Feature journeys suppress the onboarding modal so it cannot intercept page
interactions; that does not prove onboarding itself completes. This test
exercises the real first-run wizard for a fresh user, completes it without a
live model/provider, and verifies the durable status survives a reload.
"""
from __future__ import annotations

import requests
import pytest
from playwright.sync_api import Page

from tests.e2e_ui.fixtures.journey_fixtures import (  # noqa: F401
    BACKEND_URL,
    journey_user_credentials,
)
from tests.e2e_ui.pages.journey_pages import AuthPage, DashboardJourneyPage


pytestmark = pytest.mark.e2e


def _onboarding_status(token: str) -> dict:
    response = requests.get(
        f"{BACKEND_URL}/api/onboarding/status",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    response.raise_for_status()
    body = response.json()
    return body.get("data", body)


def test_first_run_onboarding_completes_and_persists(
        page: Page, journey_user_credentials):
    creds = journey_user_credentials
    auth = AuthPage(page)
    auth.navigate()
    assert auth.is_loaded(), "login page should load"
    auth.login(creds["email"], creds["password"], expect_redirect=True)

    dialog = page.get_by_role("dialog")
    dialog.wait_for(state="visible", timeout=20000)
    assert "Welcome to Atom" in dialog.inner_text()

    # Welcome -> Profile -> Connect -> Ready. Connecting a provider is
    # optional for completing onboarding; this test deliberately uses no
    # live model/provider.
    dialog.get_by_role("button", name="Next", exact=True).click()
    assert "Tell us about yourself" in dialog.inner_text()

    dialog.get_by_role("button", name="Next", exact=True).click()
    assert "Connect Your Intelligence" in dialog.inner_text()

    dialog.get_by_role("button", name="Next", exact=True).click()
    assert "You're Ready!" in dialog.inner_text()

    dialog.get_by_role("button", name="Start Automating").click()
    dialog.wait_for(state="hidden", timeout=20000)

    status = _onboarding_status(creds["access_token"])
    assert status["onboarding_completed"] is True
    assert status["onboarding_step"] == "completed"

    # A completed first run must not reopen the wizard on the next load, and
    # the user must remain signed in.
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    assert not page.get_by_role("dialog").is_visible(), (
        "completed onboarding should not reopen")
    assert DashboardJourneyPage(page).is_loaded(), (
        "user should remain on the authenticated dashboard")
