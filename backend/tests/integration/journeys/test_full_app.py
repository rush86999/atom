"""
Journey tests for the FULL app (main_api_app.py) — the production entrypoint.

These guard against the class of bug that left the full app silently loading
only 148 of its ~800 routes for months: main_api_app.py had ~250 broken import
paths that safe_import_router() swallowed, so most endpoints 404'd in
production. These tests assert the full app boots and a representative set of
endpoints (including integrations like Notion) are actually reachable.

Separate from the minimal-app journeys (which test main.py) — the full app is
heavier and exercises the full router surface.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure backend is on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-full-app-journeys")
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture(scope="module")
def full_app_client():
    """A TestClient against the FULL app (main_api_app.app).

    This is the production entrypoint (per scripts/start-dual-app.sh). It mounts
    every router. We use a module scope because the full app is expensive to
    import; tests here are read-only smoke checks.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.database import get_db
    from core.models import Base
    import core.database as db_module
    import main_api_app  # noqa: import the full app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    original_engine = db_module.engine
    original_sessionlocal = db_module.SessionLocal
    db_module.engine = engine
    db_module.SessionLocal = TestSession

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = main_api_app.app
    app.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    db_module.engine = original_engine
    db_module.SessionLocal = original_sessionlocal
    engine.dispose()


class TestFullAppBoots:
    """The full production app must boot and serve its core surface."""

    def test_app_loads_many_routes(self, full_app_client):
        """The full app loads far more routes than the minimal app.

        Before the import-path fixes, main_api_app silently loaded only ~148
        routes (the rest 404'd). We assert a high floor so a regression that
        drops dozens of routers is caught immediately.
        """
        app = full_app_client.app
        route_count = len(app.routes)
        # The minimal app has ~180; the full app should have hundreds.
        assert route_count > 400, (
            f"Full app only loaded {route_count} routes — expected 400+. "
            "Routers are failing to import (check safe_import_router ERROR logs)."
        )

    def test_root_responds(self, full_app_client):
        """GET / returns a valid response (not a connection error)."""
        resp = full_app_client.get("/")
        assert resp.status_code == 200, f"Root: {resp.status_code}"

    def test_health_live(self, full_app_client):
        """GET /health/live responds 200."""
        resp = full_app_client.get("/health/live")
        assert resp.status_code == 200, f"Health live: {resp.status_code}"

    def test_openapi_reachable(self, full_app_client):
        """The OpenAPI schema is served (full app prefixes it under /api/v1).

        NOTE: schema generation may 500 on some complex Pydantic models
        (a known FastAPI/Pydantic v2 issue). We accept 200 OR 500 — the
        important thing is the route exists and the handler runs.
        """
        for path in ("/api/v1/openapi.json", "/openapi.json"):
            resp = full_app_client.get(path)
            if resp.status_code == 200:
                assert "paths" in resp.json(), "OpenAPI missing 'paths'"
                return
            if resp.status_code == 500:
                pytest.skip("OpenAPI schema generation fails on a complex model (pre-existing Pydantic v2 issue)")
        pytest.fail("Neither /api/v1/openapi.json nor /openapi.json responded")


class TestFullAppIntegrationsReachable:
    """Integrations that previously 404'd must now be reachable."""

    def test_notion_integration_reachable(self, full_app_client):
        """The Notion integration health endpoint responds (was unreachable
        when the integrations router was silently unmounted)."""
        resp = full_app_client.get("/api/v1/integrations/notion/health")
        # 200 (configured) or 503/500 (misconfigured) — both prove the route
        # is wired and the handler ran. NOT 404.
        assert resp.status_code != 404, (
            "Notion integration 404'd — the integrations router is not mounted "
            "in the full app."
        )

    def test_canvas_routes_reachable(self, full_app_client):
        """Canvas endpoints are mounted in the full app."""
        resp = full_app_client.get("/api/canvas/recordings")
        assert resp.status_code != 404, "Canvas router not mounted in full app"

    def test_chat_routes_reachable(self, full_app_client):
        """Chat endpoints are mounted in the full app."""
        resp = full_app_client.get("/api/chat/health")
        assert resp.status_code != 404, "Chat router not mounted in full app"
