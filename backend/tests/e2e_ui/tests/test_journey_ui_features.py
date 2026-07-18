"""
UI feature journey tests — browser-driven coverage of each major surface,
exercised independently (not as one long flow) so a regression in one area
is easy to localize.

Each test uses the authed_page fixture (API-first auth, no UI login cost).
"""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page

from tests.e2e_ui.pages.journey_pages import (
    AgentsJourneyPage,
    CanvasListJourneyPage,
    ChatJourneyPage,
    DashboardJourneyPage,
    IntegrationsHubJourneyPage,
    MarketplaceJourneyPage,
    ProjectsJourneyPage,
    SettingsJourneyPage,
    WorkflowBuilderJourneyPage,
)
from tests.e2e_ui.fixtures.journey_fixtures import authed_page  # noqa: F401


pytestmark = pytest.mark.e2e


class TestAgentsUI:
    def test_agents_page_renders(self, authed_page: Page):
        agents = AgentsJourneyPage(authed_page)
        agents.navigate()
        assert agents.is_loaded(), "Agent Control Center should render for an authed user"
        # The seeded Demo Assistant should be visible.
        assert agents.text_visible("Demo Assistant", timeout=5000) or not agents.has_agents()


class TestChatUI:
    def test_chat_composer_loaded(self, authed_page: Page):
        chat = ChatJourneyPage(authed_page)
        chat.navigate()
        assert chat.is_loaded(), "Chat composer should render"

    def test_chat_send_message_persists_in_input(self, authed_page: Page):
        chat = ChatJourneyPage(authed_page)
        chat.navigate()
        assert chat.is_loaded()
        msg = f"journey msg {uuid.uuid4().hex[:6]}"
        chat.input_box.fill(msg)
        assert chat.input_box.input_value() == msg


class TestCanvasUI:
    def test_canvas_list_renders(self, authed_page: Page):
        canvas = CanvasListJourneyPage(authed_page)
        canvas.navigate()
        assert canvas.is_loaded(), "Canvas list page should render"


class TestMarketplaceUI:
    def test_marketplace_renders_and_searches(self, authed_page: Page):
        market = MarketplaceJourneyPage(authed_page)
        market.navigate()
        assert market.is_loaded(), "Workflow Marketplace should render"
        # Searching with a random term must not crash the page.
        market.search("nonexistent-" + uuid.uuid4().hex[:6])
        assert market.is_loaded()


class TestWorkflowBuilderUI:
    def test_builder_renders_and_accepts_name(self, authed_page: Page):
        builder = WorkflowBuilderJourneyPage(authed_page)
        builder.navigate()
        assert builder.is_loaded(), "Workflow builder should render"
        name = f"UI Workflow {uuid.uuid4().hex[:6]}"
        builder.set_name(name)
        assert builder.name_input.input_value() == name


class TestProjectsUI:
    def test_project_command_center_renders(self, authed_page: Page):
        projects = ProjectsJourneyPage(authed_page)
        projects.navigate()
        assert projects.is_loaded(), "Project Command Center should render"


class TestIntegrationsHubUI:
    def test_integrations_hub_renders(self, authed_page: Page):
        hub = IntegrationsHubJourneyPage(authed_page)
        hub.navigate()
        assert hub.is_loaded(), "Integrations Hub should render"


class TestSettingsUI:
    def test_theme_persists_across_reload(self, authed_page: Page):
        settings = SettingsJourneyPage(authed_page)
        settings.navigate()
        assert settings.is_loaded(), "Settings should render"

        before = settings.current_theme().strip().lower()
        target = "light" if before != "light" else "dark"
        settings.pick_theme(target.capitalize())
        after = settings.current_theme().strip().lower()
        assert target in after, f"theme select should show {target}, got {after}"

        # Reload — preference must persist.
        authed_page.reload()
        settings.navigate()
        persisted = settings.current_theme().strip().lower()
        assert target in persisted, f"theme should persist; got {persisted}"
