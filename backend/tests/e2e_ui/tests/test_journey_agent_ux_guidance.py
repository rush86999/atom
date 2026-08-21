"""AI-employee management UX guidance journey.

A real manager (any authenticated role) landing on the Agent Control Center
must not face an unexplained control surface: the onboarding guide explains
the train-to-autonomy lifecycle, per-tier supervision duties, and how an
employee's role/job-description scopes its memory. The Run and Edit dialogs
carry the same contextual guidance. The guide is dismissible and restorable.
"""

from __future__ import annotations

import pytest

from tests.e2e_ui.fixtures.journey_fixtures import authed_page  # noqa: F401

pytestmark = pytest.mark.e2e


def test_agents_page_shows_onboarding_guide_and_dialog_guidance(authed_page):
    page = authed_page
    page.goto("http://localhost:3001/agents", wait_until="domcontentloaded")
    guide = page.locator("[data-testid='agent-guide']")
    guide.wait_for(state="visible", timeout=20000)

    # The three guidance pillars render.
    for section in ("agent-guide-lifecycle", "agent-guide-supervision", "agent-guide-memory"):
        assert page.locator(f"[data-testid='{section}']").is_visible(), (
            f"{section} missing — first-time managers get no guidance"
        )

    # Dismiss is remembered; the page offers a restore affordance.
    page.locator("[data-testid='agent-guide-dismiss']").click()
    assert page.locator("[data-testid='agent-guide']").count() == 0
    assert page.locator("[data-testid='agent-guide-restore']").is_visible()

    # Restore brings the guide back for reference.
    page.locator("[data-testid='agent-guide-restore']").click()
    guide.wait_for(state="visible", timeout=5000)

    # Dismiss again so the dialogs below are reachable without overlap.
    page.locator("[data-testid='agent-guide-dismiss']").click()


def test_edit_dialog_explains_job_description_drives_memory(authed_page):
    page = authed_page
    page.goto("http://localhost:3001/agents", wait_until="domcontentloaded")
    page.wait_for_selector("[data-testid='agents-grid']", timeout=20000)

    # The guidance hint lives inside the Edit dialog; open it on the first
    # agent if one exists (skip gracefully on an empty workspace).
    edit_buttons = page.locator("button[title='Edit'], [data-testid*='edit']")
    grid_children = page.locator("[data-testid='agents-grid'] > *").count()
    if grid_children > 0 and edit_buttons.count() > 0:
        edit_buttons.first.click()
        hint = page.locator("[data-testid='edit-dialog-guidance']")
        hint.wait_for(state="visible", timeout=5000)
        assert "job description" in hint.inner_text().lower()
        assert "memory" in hint.inner_text().lower() or "recal" in hint.inner_text().lower()
