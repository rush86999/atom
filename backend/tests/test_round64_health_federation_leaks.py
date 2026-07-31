"""
Round 64 — Health/federation/workflow str(e) leak sweep (R41 class)
(Red-Green-Refactor).

Mounted-but-unswept leak sites:
  A. api/health_routes.py — /health/ready DB check + disk check put raw
     exception strings in PUBLIC (unauthenticated) health responses.
  B. api/routes/federation_routes.py — /api/federation DID resolve +
     security health/stats leak exception strings.
  C. core/workflow_ui_endpoints.py — /executions returns str(e) in the
     error dict (plus a traceback.print_exc() to stdout).
  D. core/workflow_endpoints.py — /workflows/{id}/edit AI-parse failure
     embeds str(e)[:100] in the client message; failed-execution records
     store str(e).

Fix: generic messages, logger retains {e}.
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db

SECRET = "secret-health-xyz"


def make_client(router, auth=True):
    app = FastAPI()
    app.include_router(router)
    if auth:
        app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
            id="u-64", email="u@example.com"
        )
        app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


class TestHealthRoutesNoLeak:
    def test_health_db_error_does_not_leak(self):
        from api.health_routes import router

        app = FastAPI()
        app.include_router(router)

        def bad_db():
            def gen():
                raise RuntimeError(SECRET)
                yield  # pragma: no cover

            return gen()

        app.dependency_overrides[get_db] = lambda: bad_db()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/health/db")

        assert resp.status_code == 503
        assert SECRET not in resp.text, (
            f"health/db leaks internal exception detail: {resp.text[:200]!r}"
        )

    def test_health_ready_disk_error_does_not_leak(self):
        from api.health_routes import router

        with patch("api.health_routes.psutil.disk_usage", side_effect=RuntimeError(SECRET)):
            resp = make_client(router, auth=False).get("/health/ready")

        assert SECRET not in resp.text, (
            f"health/ready disk check leaks internal detail: {resp.text[:200]!r}"
        )


class TestFederationRoutesNoLeak:
    def test_did_resolve_does_not_leak(self):
        from api.routes.federation_routes import router

        from core.identity import did_manager

        with patch.object(
            did_manager.DIDManager, "resolve_did", side_effect=RuntimeError(SECRET)
        ):
            resp = make_client(router).get("/federation/dids/did:example:abc")

        assert SECRET not in resp.text, (
            f"federation DID resolve leaks internal detail: {resp.text[:200]!r}"
        )

    def test_security_health_does_not_leak(self):
        from api.routes.federation_routes import router

        from core.federation import federation_security

        with patch.object(
            federation_security, "get_federation_security",
            side_effect=RuntimeError(SECRET),
        ):
            resp = make_client(router).get("/federation/security/health")

        assert SECRET not in resp.text, (
            f"federation security health leaks internal detail: {resp.text[:200]!r}"
        )


class TestWorkflowRoutesNoLeak:
    def test_executions_does_not_leak(self):
        from core.workflow_ui_endpoints import router

        with patch(
            "advanced_workflow_orchestrator.get_orchestrator",
            side_effect=RuntimeError(SECRET),
        ):
            resp = make_client(router).get("/executions")

        assert resp.status_code == 200
        assert SECRET not in resp.text, (
            f"workflow-ui executions leaks internal detail: {resp.text[:200]!r}"
        )

    def test_workflow_edit_failure_does_not_leak(self):
        from core.workflow_endpoints import router
        from core.security_dependencies import RBACService

        with patch.object(RBACService, "check_permission", return_value=True), patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[{"id": "wf-1", "name": "W"}],
        ), patch("core.workflow_endpoints.AI_EDITOR_AVAILABLE", False), patch(
            "core.workflow_endpoints._legacy_rule_based_edit",
            side_effect=RuntimeError(SECRET),
        ):
            resp = make_client(router).post(
                "/workflows/wf-1/edit",
                json={"command": "add a step"},
            )

        assert SECRET not in resp.text, (
            f"workflow edit failure leaks internal detail: {resp.text[:200]!r}"
        )
