"""
Realistic page objects for the Atom user-journey E2E suite.

These page objects use selectors verified against the running application
(role / text / placeholder / aria-label based), rather than data-testids
which are largely absent from the frontend. Where a stable data-testid exists
(e.g. login, dashboard welcome), it is used as the primary selector.

Frontend base URL defaults to http://localhost:3001 (E2E frontend).
Backend base URL defaults to http://localhost:8001 (full main_api_app).

Each page object exposes only the interactions the journey exercises, kept
small on purpose so UI churn doesn't ripple.
"""

from __future__ import annotations

import os
from typing import Optional

from playwright.sync_api import Page, Locator


def _frontend_base() -> str:
    return (os.getenv("FRONTEND_URL") or "http://localhost:3001").rstrip("/")


class JourneyBase:
    """Common helpers for journey page objects."""

    def __init__(self, page: Page, base_url: Optional[str] = None):
        self.page = page
        self.base_url = (base_url or _frontend_base()).rstrip("/")

    def goto(self, path: str) -> None:
        """Navigate to a path under the frontend base URL.

        Uses domcontentloaded (not networkidle) because several pages open
        WebSockets or poll on intervals, which would make networkidle hang.
        """
        self.page.goto(f"{self.base_url}{path}", wait_until="domcontentloaded")

    def text_visible(self, text: str, timeout: int = 5000) -> bool:
        try:
            self.page.wait_for_selector(f"text={text}", timeout=timeout)
            return True
        except Exception:
            return False

    def _settle(self, timeout_ms: int = 3000) -> None:
        """Best-effort wait for the network to settle.

        Several pages open WebSockets or poll on intervals, so a strict
        networkidle wait can hang. We wait briefly and tolerate a timeout.
        """
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

    @staticmethod
    def _visible(locator: Locator, timeout: int = 10000) -> bool:
        """Return whether a locator is visible, without raising on timeout."""
        try:
            return locator.is_visible(timeout=timeout)
        except Exception:
            return False


class AuthPage(JourneyBase):
    """Login / register page (pages/login.tsx)."""

    @property
    def email_input(self) -> Locator:
        return self.page.locator("[data-testid='login-email-input'], input#email")

    @property
    def password_input(self) -> Locator:
        return self.page.locator("[data-testid='login-password-input'], input#password")

    @property
    def submit_button(self) -> Locator:
        return self.page.locator("[data-testid='login-submit-button'], button[type='submit']")

    @property
    def toggle_mode_button(self) -> Locator:
        # The toggle link contains "Sign up" / "Sign in" but is NOT the submit
        # button (which reads "Sign In"). Scope to the testid, falling back to
        # the text match that excludes the submit button.
        return self.page.locator(
            "[data-testid='login-toggle-mode'], button:has-text('Sign up')"
        )

    @property
    def error_message(self) -> Locator:
        return self.page.locator("[data-testid='login-error-message']")

    def is_loaded(self) -> bool:
        return self.email_input.first.is_visible()

    def navigate(self) -> None:
        self.goto("/login")
        self._settle()

    def login(self, email: str, password: str, expect_redirect: bool = True) -> None:
        """Fill credentials and submit. If expect_redirect, wait for /dashboard."""
        self.email_input.first.fill(email)
        self.password_input.first.fill(password)
        self.submit_button.first.click()
        if expect_redirect:
            # 45s: the login flow does signIn() + getSession() + router.push,
            # and on a cold CI runner the Next.js dev server may still be
            # compiling /dashboard on first hit. wait_for_url only confirms
            # the navigation started; the page then needs to finish rendering.
            self.page.wait_for_url("**/dashboard**", timeout=45000)
            # Give the just-compiled page a moment to mount before callers
            # assert on its contents.
            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

    def switch_to_register(self) -> None:
        self.toggle_mode_button.first.click()

    def get_error(self, timeout: int = 3000) -> Optional[str]:
        try:
            self.error_message.wait_for(timeout=timeout)
            return self.error_message.text_content()
        except Exception:
            return None


class DashboardJourneyPage(JourneyBase):
    """Main dashboard (pages/dashboard.tsx) — shown right after login."""

    @property
    def welcome(self) -> Locator:
        return self.page.locator(
            "[data-testid='dashboard-welcome-message'], h1:has-text('ATOM Dashboard')"
        )

    def is_loaded(self) -> bool:
        # The dashboard fires several integration-health + summary API calls
        # on mount; the H1 doesn't render until React settles. Wait for it
        # rather than returning False the instant the URL changes.
        return self._visible(self.welcome.first, timeout=15000)

    def navigate(self) -> None:
        self.goto("/dashboard")
        self._settle()

    def get_welcome_text(self) -> str:
        return self.welcome.first.text_content() or ""


class SettingsJourneyPage(JourneyBase):
    """Settings page (pages/settings/index.tsx → PreferencesTab).

    Theme is a <Select> with Light/Dark/System items (no data-testid).
    Notifications is a <Switch>. PreferencesTab calls GET/POST
    /api/v1/preferences and persists per (user_id, workspace_id).
    """

    @property
    def heading(self) -> Locator:
        return self.page.locator("h1:has-text('Settings')")

    @property
    def theme_trigger(self) -> Locator:
        # The Select trigger is the only button-ish element in the Appearance card.
        return self.page.locator("button[role='combobox']").first

    @property
    def notifications_switch(self) -> Locator:
        return self.page.locator("button[role='switch']").first

    def is_loaded(self) -> bool:
        # The Settings H1 + the theme combobox (Preferences tab is default) are
        # the reliable indicators the page rendered.
        return self._visible(self.heading.first, 10000)

    def navigate(self) -> None:
        self.goto("/settings")
        self._settle()
        # Wait for the theme combobox (PreferencesTab fetches prefs first).
        try:
            self.theme_trigger.wait_for(state="visible", timeout=10000)
        except Exception:
            pass

    def open_theme_dropdown(self) -> None:
        self.theme_trigger.click()

    def pick_theme(self, theme: str) -> None:
        """theme: 'Light', 'Dark', or 'System' (matches the SelectItem text)."""
        self.open_theme_dropdown()
        self.page.locator(f"[role='option']:has-text('{theme}')").first.click()
        # Wait for the save POST to settle
        self.page.wait_for_timeout(800)

    def current_theme(self) -> str:
        """Read the currently-selected theme from the combobox display value."""
        return (self.theme_trigger.text_content() or "").strip()

    def document_is_dark(self) -> bool:
        return self.page.evaluate("document.documentElement.classList.contains('dark')")


class AgentsJourneyPage(JourneyBase):
    """Agents control center (pages/agents/index.tsx)."""

    @property
    def heading(self) -> Locator:
        return self.page.locator("h1:has-text('Agent Control Center')")

    @property
    def browse_templates_button(self) -> Locator:
        return self.page.locator("button:has-text('Browse templates')")

    def is_loaded(self) -> bool:
        return self._visible(self.heading.first, 10000)

    def navigate(self) -> None:
        self.goto("/agents")
        self._settle()

    def has_agents(self) -> bool:
        # Empty state shows "No agents found"
        return not self.text_visible("No agents found", timeout=2000)


class ChatJourneyPage(JourneyBase):
    """Chat interface (pages/chat/index.tsx → ChatInput)."""

    @property
    def input_box(self) -> Locator:
        # ChatInput.tsx: placeholder="Type a message..."
        return self.page.locator("input[placeholder='Type a message...']").first

    @property
    def send_button(self) -> Locator:
        return self.page.locator("button[type='submit'], button:has(svg.lucide-send)").first

    def is_loaded(self) -> bool:
        try:
            return self.input_box.is_visible(timeout=15000)
        except Exception:
            return False

    def navigate(self) -> None:
        # Chat opens a WebSocket that keeps the network busy — don't wait for
        # networkidle (it will time out). Wait for the composer instead.
        self.page.goto(f"{self.base_url}/chat", wait_until="domcontentloaded")
        try:
            self.input_box.wait_for(state="visible", timeout=15000)
        except Exception:
            pass

    def send_message(self, text: str) -> None:
        self.input_box.fill(text)
        try:
            self.send_button.click(timeout=2000)
        except Exception:
            # Fallback: press Enter to submit
            self.input_box.press("Enter")


class CanvasListJourneyPage(JourneyBase):
    """Canvas list page (pages/canvas/index.tsx)."""

    @property
    def heading(self) -> Locator:
        return self.page.locator("h1:has-text('Canvases')")

    @property
    def empty_state(self) -> Locator:
        return self.page.locator("text=No canvases yet")

    @property
    def canvas_links(self) -> Locator:
        return self.page.locator("a[href^='/canvas/']")

    def is_loaded(self) -> bool:
        return self._visible(self.heading.first, 10000)

    def navigate(self) -> None:
        self.goto("/canvas")
        self._settle()

    def canvas_count(self) -> int:
        return self.canvas_links.count()


class MarketplaceJourneyPage(JourneyBase):
    """Workflow marketplace (pages/marketplace.tsx)."""

    @property
    def heading(self) -> Locator:
        return self.page.locator("h1:has-text('Workflow Marketplace')")

    @property
    def search_input(self) -> Locator:
        return self.page.locator("input[placeholder='Search workflows...']").first

    def is_loaded(self) -> bool:
        return self._visible(self.heading.first, 10000)

    def navigate(self) -> None:
        self.goto("/marketplace")
        self._settle()

    def search(self, query: str) -> None:
        self.search_input.fill(query)
        self.page.wait_for_timeout(800)

    def template_count(self) -> int:
        # Each template card has an Import or Preview button.
        return self.page.locator("button:has-text('Import'), button:has-text('Preview')").count()


class WorkflowBuilderJourneyPage(JourneyBase):
    """Workflow builder (pages/workflows/builder.tsx)."""

    @property
    def heading(self) -> Locator:
        return self.page.locator("h2:has-text('Workflow Builder')")

    @property
    def name_input(self) -> Locator:
        return self.page.locator("input[placeholder='Workflow Name']").first

    @property
    def save_button(self) -> Locator:
        return self.page.locator("button:has-text('Save')").first

    def is_loaded(self) -> bool:
        return self._visible(self.heading.first, 10000)

    def navigate(self) -> None:
        self.goto("/workflows/builder")
        self._settle()

    def set_name(self, name: str) -> None:
        self.name_input.fill(name)

    def save(self) -> None:
        self.save_button.click()
        self.page.wait_for_timeout(1500)


class IntegrationsHubJourneyPage(JourneyBase):
    """Integrations hub (pages/integrations/index.tsx)."""

    @property
    def heading(self) -> Locator:
        return self.page.locator("h1:has-text('ATOM Integrations Hub')")

    @property
    def refresh_button(self) -> Locator:
        return self.page.locator("button:has-text('Refresh Status')")

    def is_loaded(self) -> bool:
        return self._visible(self.heading.first, 10000)

    def navigate(self) -> None:
        self.goto("/integrations")
        self._settle()

    def category_count(self) -> int:
        return self.page.locator("button:has-text('Integrations')").count()


class ProjectsJourneyPage(JourneyBase):
    """Project Command Center (pages/dashboards/projects → ProjectCommandCenter)."""

    @property
    def heading(self) -> Locator:
        return self.page.locator("h1:has-text('Project Command Center')")

    @property
    def quick_create_input(self) -> Locator:
        return self.page.locator("input[placeholder='Enter task summary...']").first

    def is_loaded(self) -> bool:
        return self._visible(self.heading.first, 10000)

    def navigate(self) -> None:
        self.goto("/dashboards/projects")
        self._settle()
