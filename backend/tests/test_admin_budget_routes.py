"""
Tests for the admin budget control routes (api/admin/budget_routes.py).

Covers the HTTP status-code contract for the GET/PUT
``/api/admin/tenants/{tenant_id}/budget`` endpoints. Logical errors (tenant
not found, invalid enforcement mode) must return the appropriate 4xx status
code, NOT a 200 with an error body — otherwise clients that check
``response.ok`` silently treat failures as success.
"""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.admin.budget_routes import router
from core.admin_endpoints import get_super_admin
from core.models import UserRole


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_admin():
    user = MagicMock()
    user.id = "admin-1"
    user.email = "admin@test.local"
    user.role = UserRole.SUPER_ADMIN.value
    return user


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(router)
    return a


@pytest.fixture
def client(app, mock_admin, worker_database):
    """Authenticated super-admin client backed by the in-memory DB.

    ``get_super_admin`` is overridden so we bypass JWT resolution; the DB is
    the shared in-memory SQLite factory so Tenant/TenantSetting rows persist.
    """
    from core.database import get_db

    SessionLocal = worker_database

    async def _override_admin():
        return mock_admin

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_super_admin] = _override_admin
    app.dependency_overrides[get_db] = _override_get_db

    yield TestClient(app)

    app.dependency_overrides.clear()


def _make_tenant(db, tenant_id="tenant-1", subdomain="test-tenant"):
    from core.models import Tenant
    t = Tenant(id=tenant_id, name="Test Tenant", subdomain=subdomain)
    db.add(t)
    db.commit()
    return t


# ============================================================================
# Status-code contract tests
# ============================================================================

class TestBudgetRouteStatusCodes:

    def test_get_unknown_tenant_returns_404_not_200(self, client, worker_database):
        """A GET for a nonexistent tenant must return 404, not 200 with an
        error body. A client checking ``response.ok`` would otherwise treat
        the missing tenant as a successful empty budget."""
        SessionLocal = worker_database
        db = SessionLocal()
        try:
            # Ensure the tenant truly doesn't exist.
            from core.models import Tenant
            assert not db.query(Tenant).filter(Tenant.id == "ghost").first()

            resp = client.get("/api/admin/tenants/ghost/budget")

            # Contract: 404 for a missing tenant (NOT 200).
            assert resp.status_code == 404, (
                f"Expected 404 for unknown tenant, got {resp.status_code} with "
                f"body {resp.json()}"
            )
        finally:
            db.close()

    def test_put_unknown_tenant_returns_404_not_200(self, client, worker_database):
        """A PUT for a nonexistent tenant must return 404, not 200."""
        resp = client.put(
            "/api/admin/tenants/ghost/budget",
            json={"budget_limit_usd": 50.0},
        )
        assert resp.status_code == 404, (
            f"Expected 404 for PUT to unknown tenant, got {resp.status_code}"
        )

    def test_put_invalid_enforcement_mode_returns_422_not_200(self, client, worker_database):
        """An invalid enforcement_mode must be rejected with 4xx, not 200."""
        SessionLocal = worker_database
        db = SessionLocal()
        try:
            _make_tenant(db, "tenant-invalid-mode", "invalid-mode")
            resp = client.put(
                "/api/admin/tenants/tenant-invalid-mode/budget",
                json={"enforcement_mode": "nonsense_mode"},
            )
            assert resp.status_code in (400, 422), (
                f"Expected 400/422 for invalid enforcement_mode, got "
                f"{resp.status_code} with body {resp.json()}"
            )
        finally:
            db.close()

    def test_put_valid_update_returns_200_and_persists(self, client, worker_database):
        """Sanity: a valid PUT for an existing tenant succeeds and the GET
        reflects the new limit."""
        SessionLocal = worker_database
        db = SessionLocal()
        try:
            _make_tenant(db, "tenant-valid", "valid-tenant")
            resp = client.put(
                "/api/admin/tenants/tenant-valid/budget",
                json={"budget_limit_usd": 75.0, "enforcement_mode": "hard_stop"},
            )
            assert resp.status_code == 200, resp.json()
            body = resp.json()
            assert body["budget_limit_usd"] == 75.0
            assert body["enforcement_mode"] == "hard_stop"

            # GET reflects the persisted state.
            get_resp = client.get("/api/admin/tenants/tenant-valid/budget")
            assert get_resp.status_code == 200
            assert get_resp.json()["budget_limit_usd"] == 75.0
        finally:
            db.close()
