"""
Round 63 — Protection API: str(e) leak sweep (R41 class)
(Red-Green-Refactor).

api/protection_api.py (mounted at /api/protection) forwards raw exception
strings to clients via details={"error": str(e)} on all 4 endpoints —
internal exception detail (service internals, paths, line info) reaches
clients on every failure. Fix: generic messages, logger retains {e}.
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db

SECRET = "secret-protection-xyz"


def make_client():
    from api.protection_api import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
        id="u-63", email="u@example.com"
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


class TestProtectionApiNoLeak:
    def test_churn_does_not_leak(self):
        services = {"churn": MagicMock()}
        services["churn"].predict_churn_risk.side_effect = RuntimeError(SECRET)

        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = make_client().get("/api/protection/churn")

        assert resp.status_code == 500
        assert SECRET not in resp.text, (
            f"churn endpoint leaks internal exception detail: {resp.text[:200]!r}"
        )

    def test_financial_does_not_leak(self):
        services = {
            "warning": MagicMock(),
            "fraud": MagicMock(),
        }
        services["warning"].detect_ar_delays.side_effect = RuntimeError(SECRET)

        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = make_client().get("/api/protection/financial")

        assert resp.status_code == 500
        assert SECRET not in resp.text, (
            f"financial endpoint leaks internal exception detail: {resp.text[:200]!r}"
        )

    def test_growth_does_not_leak(self):
        services = {"growth": MagicMock()}
        services["growth"].check_scaling_readiness.side_effect = RuntimeError(SECRET)

        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = make_client().get("/api/protection/growth")

        assert resp.status_code == 500
        assert SECRET not in resp.text, (
            f"growth endpoint leaks internal exception detail: {resp.text[:200]!r}"
        )

    def test_scan_does_not_leak(self):
        analyzer_cls = MagicMock()
        analyzer_cls.return_value.scan_content.side_effect = RuntimeError(SECRET)

        with patch(
            "atom_security.analyzers.static.StaticAnalyzer", analyzer_cls
        ):
            resp = make_client().post(
                "/api/protection/scan",
                json={
                    "skill_name": "test",
                    "instruction_body": "do nothing",
                    "file_contents": {"main.py": "print('hi')"},
                },
            )

        assert resp.status_code == 500
        assert SECRET not in resp.text, (
            f"scan endpoint leaks internal exception detail: {resp.text[:200]!r}"
        )
