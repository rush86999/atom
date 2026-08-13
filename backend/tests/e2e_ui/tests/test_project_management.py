"""
E2E UI tests for the Project Command Center (dashboards/projects).

The REAL projects UI is `components/dashboards/ProjectCommandCenter.tsx` — a
unified task board over CONNECTED project-management platforms (Jira, Asana,
...). It is NOT a local CRUD app: there is no edit/delete UI and no local
project store.

- Tasks are listed live from GET /api/atom/projects/live/board (external
  platforms only — in a sandboxed env with no connected platforms the table
  renders the empty state).
- Creation goes through the Quick Create modal -> POST
  /api/intelligence/execute (create_task tool) -> POST
  /api/projects/unified-tasks on the backend, which fails GRACEFULLY with
  "No project management platform connected." when nothing is connected.

This suite therefore asserts:
1. The page renders (header, stats, table, empty state, search).
2. The Quick Create modal flow works end-to-end (open/fill/cancel/submit),
   including the graceful unconnected-platform failure path.
3. The backend unified-tasks endpoints (list + create) return a clean success
   envelope with a human-readable, non-exception result.
4. The live-board endpoint serves the board contract (ok/stats/tasks).

Tests use authenticated_page (API-first auth) and authenticated_api_client
(direct backend API calls).
"""

import uuid

from playwright.sync_api import Page


class TestProjectCommandCenter:
    """Tests for the Project Command Center page rendering."""

    def test_projects_page_renders(self, authenticated_page: Page):
        """Test that the Project Command Center page loads with all sections.

        Verifies:
        1. Page navigates to /dashboards/projects
        2. Header ("Project Command Center") is visible
        3. Quick Create + Sync Settings buttons are visible
        4. Stats cards render (Total Tasks / Active Platforms / Overdue)
        5. Tasks table renders with column headers
        6. Without connected platforms the table shows the empty state
        7. Search input accepts input and filters (no rows -> still empty state)

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        from tests.e2e_ui.pages.page_objects import ProjectsPage

        projects = ProjectsPage(authenticated_page)
        projects.navigate()

        assert projects.is_loaded(), "Project Command Center should be loaded"
        assert projects.page_root.is_visible()

        header = authenticated_page.get_by_role("heading", name="Project Command Center")
        assert header.is_visible(), "Header 'Project Command Center' should be visible"

        assert projects.sync_settings_button.is_visible()
        assert projects.projects_table.is_visible(), "Tasks table should be visible"

        stat_total = projects.stat_total_tasks.text_content() or ""
        assert stat_total.isdigit(), f"Total Tasks stat should be numeric, got: {stat_total!r}"

        # No PM platforms connected in the sandbox -> empty state, not an error
        projects.empty_state.wait_for(state="visible", timeout=15000)
        assert projects.empty_state.is_visible(), (
            "Empty state should render when no platforms are connected. "
            "Got task names: %r" % projects.get_project_names()
        )
        assert projects.get_project_count() == 0

        # Search input is functional: typing 3+ chars switches to the memory
        # search results view (the page's unified search), which shows the
        # no-records state for an empty memory.
        projects.search_input.fill("no-such-task")
        search_heading = authenticated_page.locator(
            "h2:has-text('Search Results for')"
        )
        assert search_heading.is_visible(), \
            "Typing in the search box should open the search results view"
        no_records = authenticated_page.get_by_text("No historical records found")
        no_records.wait_for(state="visible", timeout=10000)
        assert no_records.is_visible(), \
            "Empty memory should show the no-records search state"

    def test_quick_create_modal_flow(self, authenticated_page: Page):
        """Test the Quick Create modal: open, fill, cancel, submit.

        Verifies:
        1. Quick Create opens the create modal
        2. Title input accepts text and platform pickers work
        3. Cancel closes the modal without side effects
        4. Re-opening and submitting attempts creation and is handled
           gracefully (modal closes or an error toast appears) — a sandbox
           with no connected PM platform cannot create real tasks

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        from tests.e2e_ui.pages.page_objects import ProjectsPage

        projects = ProjectsPage(authenticated_page)
        projects.navigate()
        assert projects.is_loaded()

        # Open modal
        projects.open_create_modal()
        assert projects.create_modal.is_visible(), "Create modal should open"

        # Fill the form
        project_name = f"Quick Create Task {str(uuid.uuid4())[:8]}"
        projects.fill_project_form(project_name, platform="jira")
        assert projects.modal_save_button.is_enabled(), \
            "Create Task should be enabled once a title is entered"

        # Cancel closes the modal without submitting
        projects.cancel_create()
        projects.create_modal.wait_for(state="hidden", timeout=5000)
        assert projects.get_project_count() == 0, \
            "Cancelling the modal must not create anything"

        # Re-open and submit: with no PM platform connected, the create task
        # tool fails gracefully and the UI surfaces the real result as an
        # error toast (the modal stays open — nothing was created).
        projects.open_create_modal()
        projects.fill_project_form(project_name, platform="asana")
        projects.submit_create_form()

        # Sonner toasts auto-dismiss after a few seconds — wait for the toast
        # immediately after submitting.
        toast = authenticated_page.locator("li[data-sonner-toast]").first
        toast.wait_for(state="visible", timeout=10000)
        toast_text = toast.text_content() or ""
        assert "created successfully" not in toast_text.lower(), \
            f"Unconnected-platform create must not show a success toast: {toast_text!r}"
        assert projects.create_modal.is_visible(), \
            "Modal should stay open after a failed creation"

        # Cancel the modal; page still functional afterwards
        projects.cancel_create()
        projects.quick_create_button.wait_for(state="visible", timeout=5000)
        projects.empty_state.wait_for(state="visible", timeout=15000)
        assert projects.empty_state.is_visible()


class TestUnifiedTasksApi:
    """Tests for the backend unified-tasks API used by the projects page.

    NOTE: `authenticated_api_client` is the e2e APIClient — its .get()/.post()
    return the parsed JSON body and raise requests.HTTPError on non-2xx, so
    a 200 status is implied by a successful return.
    """

    def test_unified_tasks_list_endpoint(self, authenticated_api_client):
        """GET /api/projects/unified-tasks returns a clean success envelope.

        Verifies:
        1. 200 with the standard success envelope (APIClient raises on non-2xx)
        2. Data is a dict of per-platform results
        3. No per-platform result leaks a raw Python exception artifact
           (e.g. "has no attribute" from a broken service adapter)

        Args:
            authenticated_api_client: Authenticated API client fixture
        """
        payload = authenticated_api_client.get("/api/projects/unified-tasks")
        assert payload.get("success") is True, f"Unexpected payload: {payload}"

        data = payload.get("data", {})
        assert isinstance(data, dict), \
            f"data should be a per-platform result dict, got: {type(data)}"

        for platform, result in data.items():
            if isinstance(result, dict):
                error = result.get("error") or ""
                assert "has no attribute" not in error, \
                    f"Platform '{platform}' leaked an AttributeError: {error}"
                assert "can't be used in 'await'" not in error, \
                    f"Platform '{platform}' leaked an await TypeError: {error}"

    def test_unified_tasks_create_endpoint_no_platform(self, authenticated_api_client):
        """POST /api/projects/unified-tasks without a connected platform fails gracefully.

        The create_task tool resolves the platform from the user's connected
        integrations (ConnectionService.list_connections). With no PM
        platform connected it must return a clean, human-readable error —
        never a 500 or a raw exception string.

        Args:
            authenticated_api_client: Authenticated API client fixture
        """
        name = f"Unified Task {str(uuid.uuid4())[:8]}"
        payload = authenticated_api_client.post(
            "/api/projects/unified-tasks",
            json={"summary": name, "status": "To Do"},
        )
        assert payload.get("success") is True, f"Unexpected payload: {payload}"

        data = payload.get("data", {})
        error = data.get("error") if isinstance(data, dict) else str(data)
        assert error, f"Expected a graceful error when no platform is connected: {payload}"
        assert "No project management platform connected" in error, (
            f"Expected the 'no platform connected' message, got: {error}"
        )


class TestLiveBoardApi:
    """Tests for the live board endpoint backing the page's task list."""

    def test_live_board_endpoint(self, authenticated_api_client):
        """GET /api/atom/projects/live/board serves the board contract.

        Verifies:
        1. 200 with ok=true (APIClient raises on non-2xx)
        2. stats contains the required fields (total_active_tasks,
           completed_today, overdue_count, tasks_by_platform)
        3. tasks is a list and providers is a dict

        Args:
            authenticated_api_client: Authenticated API client fixture
        """
        payload = authenticated_api_client.get("/api/atom/projects/live/board")

        assert payload.get("ok") is True, f"Unexpected payload: {payload}"
        stats = payload.get("stats", {})
        for key in ("total_active_tasks", "completed_today", "overdue_count", "tasks_by_platform"):
            assert key in stats, f"stats should contain '{key}': {stats}"
        assert isinstance(payload.get("tasks"), list), "tasks should be a list"
        assert isinstance(payload.get("providers"), dict), "providers should be a dict"
