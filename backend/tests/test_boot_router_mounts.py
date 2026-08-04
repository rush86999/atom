"""RED tests — Round 70 / Plan 315-08: boot-time router mounts (B12).

The `catalog_router` NameError required two boot fixes (`75ed867f3`,
`82aa20258`). The catalog router and oauth_status router both mount inside
try/except blocks that log-and-continue, so a failed mount silently disables
a feature with no CI signal. These tests lock the mounts in place via real
HTTP reachability (the route tree wraps included routers in lazy
`_IncludedRouter` objects that don't surface in `app.routes`, so a request
is the reliable signal).

Checks:
- catalog GET must not 404 (the route exists → any of 200/401/500 means mounted).
- oauth status GET without a token must 401 (route mounted + auth enforced — B7).
"""
from fastapi.testclient import TestClient

from main_api_app import app


def test_catalog_router_mounted():
    c = TestClient(app)
    r = c.get("/api/v1/integrations/catalog")
    assert r.status_code != 404, (
        "B12 regression: catalog router is not mounted — a silent mount "
        "failure disabled the integrations catalog feature (got 404)."
    )


def test_oauth_status_router_mounted_and_authenticated():
    c = TestClient(app)
    for path in ("/api/auth/gmail/status", "/api/auth/oauth-status"):
        r = c.get(path)
        assert r.status_code == 401, (
            f"B12/B7 regression: {path} is not mounted-with-auth. Expected 401 "
            f"without a token, got {r.status_code}."
        )
