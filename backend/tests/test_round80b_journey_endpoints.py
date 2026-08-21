"""RED tests — Round 80b: journey endpoints for hub pages resolve in the real app.

The hub pages (/integrations/dropbox|telegram|gitlab|xero|monday|whatsapp) call
REAL backend endpoints:
  dropbox  /api/dropbox/oauth/status + /api/dropbox/oauth/url
  telegram /api/telegram/status (+ /send)
  gitlab   /api/gitlab/status + /api/gitlab/auth/url
  xero     /api/xero/status + /api/xero/auth/url
  monday   /api/monday/auth/url + /api/monday/status
  whatsapp /api/whatsapp/health

These routers are registry-LAZY (never boot-mounted), so the legacy health
stub (api_legacy_health.py, mounted last) was SHADOWING the bare status paths
with fake data — and crashed with `NameError: name 'logger' is not defined`
in integration_health_endpoints.get_integration_health():284 (the broadcast
exception path) → every /api/{app}/status in the whole app 500'd.

RED: the probes below fail (404/500) before the Round-80b fix; GREEN after:
  - logger restored in integration_health_endpoints.py (no more 500s)
  - dropbox/gitlab/monday/telegram/whatsapp/xero boot-mounted at their
    declared root prefixes so real routes precede and win over the stub.
"""
from fastapi.testclient import TestClient

from main_api_app import app


class TestJourneyEndpointsResolve:
    def _client(self):
        return TestClient(app, raise_server_exceptions=False)

    def test_xero_status_is_real_not_stub(self):
        """Real xero router: ok + service=xero + status=active (not the legacy
        stub health shape, and never a 500)."""
        resp = self._client().get("/api/xero/status")
        assert resp.status_code == 200, f"xero status: {resp.status_code} {resp.text[:200]}"
        body = resp.json()
        assert body.get("ok") is True and body.get("service") == "xero"
        assert body.get("status") == "active"

    def test_dropbox_oauth_status_resolves(self):
        resp = self._client().get("/api/dropbox/oauth/status")
        assert resp.status_code == 200, f"dropbox oauth/status: {resp.status_code}"

    def test_dropbox_oauth_url_resolves(self):
        resp = self._client().get("/api/dropbox/oauth/url")
        assert resp.status_code == 200

    def test_gitlab_status_and_auth_url_resolve(self):
        c = self._client()
        assert c.get("/api/gitlab/status").status_code == 200
        resp = c.get("/api/gitlab/auth/url")
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_monday_auth_url_resolves(self):
        resp = self._client().get("/api/monday/auth/url")
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_telegram_status_resolves(self):
        """Telegram status requires auth (R80) — 200 with a token path would be
        ideal, but the bare route must exist (401 with no token, never 404)."""
        resp = self._client().get("/api/telegram/status")
        assert resp.status_code in (200, 401), f"telegram status: {resp.status_code}"

    def test_whatsapp_health_resolves(self):
        """WhatsApp health fails closed (503 + clear reason) when the optional
        dependency/service is missing — the route must exist (never 404)."""
        resp = self._client().get("/api/whatsapp/health")
        assert resp.status_code != 404, "whatsapp health: 404 (router not mounted)"
        if resp.status_code == 503:
            assert resp.json().get("detail") in (
                "Service not configured",
                "WhatsApp integration not available (missing optional dependency)",
            ), resp.text[:200]

    def test_legacy_stub_no_longer_500s(self):
        """Any /api/{app}/status must never crash the legacy health broadcast
        path (logger NameError) again."""
        for path in ("/api/teams/status", "/api/notion/status", "/api/salesforce/status"):
            resp = self._client().get(path)
            assert resp.status_code != 500, f"{path} returned 500"

    def test_discord_real_surface_on_auto_load(self):
        """Round 80c: the auto-load middleware must mount own-prefix routers
        (discord declares /api/discord) UNPREFIXED — previously the real
        surface only existed at the bogus double prefix
        /api/v1/integrations/discord/api/discord/*."""
        c = self._client()
        assert c.get("/api/discord/status").status_code == 200
        # the bogus double-prefixed duplicate must be gone
        assert c.get("/api/v1/integrations/discord/api/discord/status").status_code == 404