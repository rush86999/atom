"""Tests for GET /health/decision-router wiring (Phase 5 integration).

Hermetic: calls the route function directly with patched status provider,
mirroring the stage-router health tests' success/error cases.
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch


@pytest.mark.asyncio
async def test_decision_router_route_success():
    from api.health_routes import decision_router_status_route
    with patch("core.decision_automation.decision_status",
               return_value={"phase": "collecting", "surfaces": {}}):
        body = await decision_router_status_route()
        assert body["phase"] == "collecting"


@pytest.mark.asyncio
async def test_decision_router_route_error():
    from api.health_routes import decision_router_status_route
    with patch("core.decision_automation.decision_status",
               side_effect=RuntimeError("boom")):
        body = await decision_router_status_route()
        assert body["phase"] == "error"
        assert body["error"] == "internal"


@pytest.mark.asyncio
async def test_decision_router_route_never_raises_without_db():
    from api.health_routes import decision_router_status_route
    with patch("core.database.SessionLocal", side_effect=RuntimeError("no db")):
        body = await decision_router_status_route()
        assert body["phase"] == "error"
