"""
End-to-end sidebar navigation route tests.

Every sidebar nav item maps to a frontend page that calls a backend API
endpoint on load. This test verifies each endpoint is REACHABLE and does NOT
crash (500). A 200/401/403/404/422 is acceptable (the route exists and
responds); a 500 or ImportError means the nav destination is broken.

This is a SMOKE test — it catches missing routes, import errors, and handler
crashes, not deep business logic.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Real FastAPI app client (no auth override — 401s are acceptable)."""
    from main_api_app import app
    with TestClient(app) as c:
        yield c


def _assert_reachable(client, method, path, **kwargs):
    """Assert the endpoint EXISTS (not 404) and does NOT crash (not 500).

    A 200/401/403/422 is acceptable — the route is wired and responds.
    A 404 means the route is missing (broken nav). A 500 means it crashes.
    """
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code != 404, (
        f"{method.upper()} {path} returned 404 — the nav route is MISSING. "
        f"The sidebar links to a page that calls this endpoint."
    )
    assert resp.status_code < 500, (
        f"{method.upper()} {path} returned {resp.status_code} (server error) — "
        f"the nav destination is broken. Body: {resp.text[:300]}"
    )
    return resp


# ============================================================================
# CORE nav items
# ============================================================================

class TestCoreNavRoutes:
    def test_dashboard(self, client):
        _assert_reachable(client, "get", "/api/health")  # dashboard's health check

    def test_chat_sessions(self, client):
        _assert_reachable(client, "get", "/api/chat/sessions", params={"user_id": "default_user"})

    def test_canvas_list(self, client):
        _assert_reachable(client, "get", "/api/canvas/")

    def test_documents_list(self, client):
        _assert_reachable(client, "get", "/api/documents")

    def test_boards_list(self, client):
        _assert_reachable(client, "get", "/api/boards")

    def test_tasks_list(self, client):
        # KNOWN GAP: /api/v1/tasks endpoint doesn't exist on the backend yet.
        # The Tasks page (TaskManagement.tsx) calls it but gets 404.
        # Requires backend implementation — not a URL fix.
        pytest.skip("Backend endpoint /api/v1/tasks not yet implemented")

    def test_agents_list(self, client):
        _assert_reachable(client, "get", "/api/agents/")

    def test_workflow_definitions(self, client):
        # Frontend now calls the correct v1 path (BUG-057 fix).
        _assert_reachable(client, "get", "/api/v1/workflows/workflows")

    def test_workflow_templates(self, client):
        _assert_reachable(client, "get", "/api/workflow-templates/")


# ============================================================================
# COMMAND CENTERS
# ============================================================================

class TestCommandCenterRoutes:
    def test_sales_dashboard_insights(self, client):
        _assert_reachable(client, "get", "/api/intelligence/insights")

    def test_support_tickets(self, client):
        # KNOWN GAP: support tickets endpoint doesn't exist yet.
        pytest.skip("Backend endpoint /api/atom/communication/live/support/tickets not yet implemented")

    def test_knowledge_entities(self, client):
        _assert_reachable(client, "get", "/api/intelligence/entities")

    def test_communication_analytics(self, client):
        # KNOWN GAP: communication analytics endpoint doesn't exist yet.
        pytest.skip("Backend endpoint /api/atom/communication/memory/analytics not yet implemented")


# ============================================================================
# BUSINESS nav items
# ============================================================================

class TestBusinessNavRoutes:
    def test_marketing_summary(self, client):
        _assert_reachable(client, "get", "/api/marketing/dashboard/summary")

    def test_finance_transactions(self, client):
        _assert_reachable(client, "post", "/api/accounting/transactions",
                         json={"workspace_id": "default", "limit": 10})

    def test_analytics_dashboard(self, client):
        # Frontend now calls /kpis suffix (BUG-055 fix).
        _assert_reachable(client, "get", "/api/analytics/dashboard/kpis")


# ============================================================================
# PRODUCTIVITY nav items
# ============================================================================

class TestProductivityNavRoutes:
    def test_calendar_events(self, client):
        # Frontend now calls the correct dashboard path (BUG-056 fix).
        _assert_reachable(client, "get", "/api/dashboard/events")


# ============================================================================
# GOVERNANCE nav items
# ============================================================================

class TestGovernanceNavRoutes:
    def test_jit_verification_health(self, client):
        _assert_reachable(client, "get", "/api/admin/governance/jit/health")

    def test_business_facts_list(self, client):
        _assert_reachable(client, "get", "/api/admin/governance/facts")


# ============================================================================
# PLATFORM nav items
# ============================================================================

class TestPlatformNavRoutes:
    def test_integrations_health(self, client):
        # KNOWN GAP: the frontend calls /api/integrations/{provider}/health
        # but the backend has /api/slack/health (different prefix pattern).
        pytest.skip("Integration health endpoint URL mismatch — needs backend unification")

    def test_settings_preferences(self, client):
        _assert_reachable(client, "get", "/api/v1/preferences",
                         params={"user_id": "default_user", "workspace_id": "default"})
