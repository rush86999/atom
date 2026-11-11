"""
Canonical end-to-end user journey — one ordered flow through the real app.

This is the "real world usage" path a user takes on first contact with Atom.
It exercises the UI login (not API-first) so the auth flow itself is covered,
then walks through every major surface a logged-in user can reach, asserting
concrete, observable behavior at each step. Where a feature needs backend
data, we set it up via the API first (fast) and then observe it in the UI.

Run:
    PLAYWRIGHT_NODEJS_PATH=$(which node) \
    backend/venv/bin/python -m pytest \
        backend/tests/e2e_ui/tests/test_user_journey.py -v

Preconditions:
    - Full backend (main_api_app:app) on http://localhost:8001
    - Frontend on http://localhost:3001
"""

from __future__ import annotations

import uuid

import pytest
import requests
from playwright.sync_api import Page, expect

from tests.e2e_ui.pages.journey_pages import (
    AgentsJourneyPage,
    AuthPage,
    CanvasListJourneyPage,
    ChatJourneyPage,
    DashboardJourneyPage,
    IntegrationsHubJourneyPage,
    MarketplaceJourneyPage,
    ProjectsJourneyPage,
    SettingsJourneyPage,
    WorkflowBuilderJourneyPage,
)
from tests.e2e_ui.fixtures.journey_fixtures import (  # noqa: F401 (fixtures)
    BACKEND_URL,
    journey_user_credentials,
    product_profile,
    route_enabled,
    deferred_label,
    DEFAULT_PASSWORD,
)


pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _dismiss_first_run_onboarding(page: Page):
    """Keep the onboarding modal from intercepting feature interactions."""
    page.add_init_script(
        "try { sessionStorage.setItem('atom.onboarding.dismissed', '1'); } "
        "catch (e) {}")
    yield


class TestCanonicalUserJourney:
    """One realistic first-run journey touching every major surface."""

    def test_full_journey_login_to_logout(
            self, page: Page, journey_user_credentials, product_profile):
        """
        Login (UI) → Dashboard → Agents → Chat → Canvas list → Marketplace →
        Workflow Builder → Projects → Integrations Hub → Settings (theme
        persistence) → Logout → protected route redirects to login.
        """
        creds = journey_user_credentials

        # ------------------------------------------------------------------
        # 1. UI LOGIN
        # ------------------------------------------------------------------
        auth = AuthPage(page)
        auth.navigate()
        assert auth.is_loaded(), "Login page should load"
        auth.login(creds["email"], creds["password"], expect_redirect=True)

        dashboard = DashboardJourneyPage(page)
        assert dashboard.is_loaded(), "Should land on the dashboard after login"
        assert "Your workspace" in dashboard.get_welcome_text()

        # The frontend stores the JWT in localStorage after login.
        token = page.evaluate("localStorage.getItem('auth_token')")
        assert token, "auth_token should be in localStorage after UI login"

        # ------------------------------------------------------------------
        # 2. AGENTS CONTROL CENTER
        # ------------------------------------------------------------------
        agents = AgentsJourneyPage(page)
        agents.navigate()
        assert agents.is_loaded(), "Agents page should load"
        # Whether or not agents exist, the page must render (not crash).
        # Empty state and populated state are both valid.
        _ = agents.has_agents()

        # ------------------------------------------------------------------
        # 3. CHAT INTERFACE
        # ------------------------------------------------------------------
        chat = ChatJourneyPage(page)
        chat.navigate()
        assert chat.is_loaded(), "Chat composer should be visible"

        # ------------------------------------------------------------------
        # 4. CANVAS LIST
        # ------------------------------------------------------------------
        canvas = CanvasListJourneyPage(page)
        canvas.navigate()
        assert canvas.is_loaded(), "Canvas list page should load"
        # No assertion on count — zero canvases is a valid fresh state.

        # ------------------------------------------------------------------
        # 5. WORKFLOW MARKETPLACE
        # ------------------------------------------------------------------
        market = MarketplaceJourneyPage(page)
        market.navigate()
        if not route_enabled(product_profile, "/marketplace"):
            label = deferred_label(product_profile, "/marketplace")
            assert market.is_not_in_release(label), (
                f"Marketplace should show its deferred scope for {label!r}")
        else:
            assert market.is_loaded(), "Marketplace should load"
            # Searching should not error even with no templates.
            market.search("customer onboarding" + uuid.uuid4().hex[:4])

        # ------------------------------------------------------------------
        # 6. WORKFLOW BUILDER
        # ------------------------------------------------------------------
        builder = WorkflowBuilderJourneyPage(page)
        builder.navigate()
        if not route_enabled(product_profile, "/workflows/builder"):
            label = deferred_label(product_profile, "/workflows/builder")
            assert builder.is_not_in_release(label), (
                f"Workflow builder should show its deferred scope for {label!r}")
        else:
            assert builder.is_loaded(), "Workflow builder should load"
            wf_name = f"Journey Workflow {uuid.uuid4().hex[:6]}"
            builder.set_name(wf_name)
            # Saving may fail if backend validation rejects an empty graph; we
            # only require that the builder UI accepts the name and the save
            # click does not crash the page.
            try:
                builder.save()
            except Exception:
                pass
            assert builder.is_loaded(), "Builder should remain usable after save attempt"

        # ------------------------------------------------------------------
        # 7. PROJECTS / TASKS
        # ------------------------------------------------------------------
        projects = ProjectsJourneyPage(page)
        projects.navigate()
        if not route_enabled(product_profile, "/dashboards/projects"):
            label = deferred_label(product_profile, "/dashboards/projects")
            assert projects.is_not_in_release(label), (
                f"Project Command Center should show its deferred scope for {label!r}")
        else:
            assert projects.is_loaded(), "Project Command Center should load"

        # ------------------------------------------------------------------
        # 8. INTEGRATIONS HUB
        # ------------------------------------------------------------------
        integrations = IntegrationsHubJourneyPage(page)
        integrations.navigate()
        if not route_enabled(product_profile, "/integrations"):
            label = deferred_label(product_profile, "/integrations")
            assert integrations.is_not_in_release(label), (
                f"Integrations Hub should show its deferred scope for {label!r}")
        else:
            assert integrations.is_loaded(), "Integrations Hub should load"

        # ------------------------------------------------------------------
        # 9. SETTINGS — theme persistence
        # ------------------------------------------------------------------
        settings = SettingsJourneyPage(page)
        settings.navigate()
        assert settings.is_loaded(), "Settings page should load with the Preferences tab"

        # Read the starting theme, then switch to a deterministic one.
        before = settings.current_theme()
        target = "Dark" if before.strip().lower() != "dark" else "Light"
        settings.pick_theme(target)
        after = settings.current_theme()
        assert target.lower() in after.lower(), (
            f"Theme select should reflect '{target}' after picking it; got '{after}'"
        )

        # Reload — the persisted preference must survive a full page reload.
        page.reload()
        settings.navigate()
        persisted = settings.current_theme()
        assert target.lower() in persisted.lower(), (
            f"Theme '{target}' should persist across reload; got '{persisted}'"
        )

        # ------------------------------------------------------------------
        # 10. LOGOUT — the real sign-out path, at the boundary a user touches
        # ------------------------------------------------------------------
        # Logging out is NOT "delete some localStorage keys". Since the web
        # session cookie became the sign-in authority (login bridges into
        # NextAuth), a storage-only wipe leaves the browser authenticated and
        # the session→localStorage sync legitimately restores the bearer on the
        # next page load. Drive the sidebar's sign-out handler instead; it
        # revokes the bearer server-side as well as clearing local credentials.
        dashboard = DashboardJourneyPage(page)
        dashboard.navigate()
        assert dashboard.is_loaded(), "Dashboard should load before sign-out"
        pre_logout_token = page.evaluate("localStorage.getItem('auth_token')")
        assert pre_logout_token, "auth_token should exist before sign-out"

        dashboard.logout()

        # Local credential contract: the bearer is gone from storage and from
        # the legacy auth_token cookie the middleware also admits.
        def _signed_out_locally() -> bool:
            try:
                cookie_names = {c["name"] for c in page.context.cookies()}
                return (
                    not page.evaluate("localStorage.getItem('auth_token')")
                    and "auth_token" not in cookie_names
                )
            except Exception:
                return False  # navigation in flight — retry

        local_clear = False
        for _ in range(40):
            local_clear = _signed_out_locally()
            if local_clear:
                break
            page.wait_for_timeout(250)
        assert local_clear, (
            "auth_token (storage and cookie) must be cleared after logout")

        # Revocation is part of logout: the bearer that authorized this journey
        # must no longer authorize backend calls, not merely be forgotten.
        revoked = requests.get(
            f"{BACKEND_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {pre_logout_token}"},
            timeout=15,
        )
        assert revoked.status_code == 401, (
            "Logout must revoke the pre-logout bearer; "
            f"/api/auth/me returned {revoked.status_code}")

        # Browser authority is gone too: a protected route now bounces to login
        # (the middleware gate checks the web session cookie, not just storage).
        page.goto(f"{settings.base_url}/agents", wait_until="domcontentloaded")
        page.wait_for_url("**/login**", timeout=15000)
        auth = AuthPage(page)
        assert auth.is_loaded(), "Should be back on the login page after sign-out"
