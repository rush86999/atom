"""RED tests — Round 80: integration-journey auth gaps (every-role audit).

User-journey audit of the app-integration surface found data/action endpoints
that are reachable by any unauthenticated caller — bypassing ALL role checks
(viewer/guest included) and letting anonymous callers read data and, worse,
create/mutate records (post tweets, create BambooHR employees, post Discord
messages, add Slack reactions).

Wave 93–105 established the convention: data/action routes require
`current_user: User = Depends(get_current_user)`; `/auth/url`, `/auth/callback`,
`/status`, `/health`, `/webhook`, `/interactions` stay public (OAuth + inbound
webhook handshakes are authenticated by their own protocol). The following
routers were never aligned with it:

  G1 — integrations/bridge/external_integration_routes.py (/api/v1/external-
       integrations): ZERO auth on all 3 endpoints, INCLUDING POST /execute,
       which runs arbitrary Node-bridge "piece" actions with caller-supplied
       credentials.
  G2 — GET /api/integrations/stats (main_api_app): circuit-breaker internals
       exposed anonymously.
  G3 — integrations/twitter_routes.py: POST /tweets (write) + 2 data reads.
  G4 — integrations/bamboohr_routes.py: employee list/read/create POST + time-off.
  G5 — integrations/discord_routes.py: /user, /guilds, /guilds/{id}/channels,
       POST/GET /channels/{id}/messages, /search, /items.
  G6 — integrations/slack_routes.py: /channels, /channels/{id}, /users/{id},
       /conversations/history, POST /reactions/add (send_message & /search were
       already gated by wave 93).

TDD: anonymous-401 tests were RED (200) before each fix.
"""
from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import (
    bamboohr_routes as bhr,
    discord_routes as dr,
    slack_routes as sr,
    twitter_routes as twr,
)
from integrations.bridge import external_integration_routes as extr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "r80-user"
    u.email = "r80@x.com"
    return u


def _app_with(router, auth_user=None):
    app = FastAPI()
    app.include_router(router)
    if auth_user is not None:
        app.dependency_overrides[get_current_user] = lambda: auth_user
    return TestClient(app, raise_server_exceptions=False)


# --------------------------------------------------------------------------
# G1 — external-integration bridge (all 3 endpoints)
# --------------------------------------------------------------------------

class TestExternalIntegrationAuth:
    def _anon(self):
        return _app_with(extr.router)

    def test_list_anonymous_401(self):
        assert self._anon().get("/api/v1/external-integrations/").status_code == 401

    def test_details_anonymous_401(self):
        assert self._anon().get("/api/v1/external-integrations/slack").status_code == 401

    def test_execute_anonymous_401(self):
        resp = self._anon().post("/api/v1/external-integrations/execute", json={
            "pieceName": "slack", "actionName": "send_message",
            "props": {"text": "hi"}, "auth": {"token": "x"},
        })
        assert resp.status_code == 401

    def test_execute_authenticated_still_works(self, user):
        from unittest.mock import AsyncMock
        c = _app_with(extr.router, auth_user=user)
        with patch.object(extr.external_integration_service, "execute_integration_action",
                          new=AsyncMock(return_value={"ok": True})):
            resp = c.post("/api/v1/external-integrations/execute", json={
                "pieceName": "slack", "actionName": "send_message",
                "props": {"text": "hi"}, "auth": {"token": "x"},
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


# --------------------------------------------------------------------------
# G2 — /api/integrations/stats (real app)
# --------------------------------------------------------------------------

class TestIntegrationStatsAuth:
    def test_stats_anonymous_401(self):
        from main_api_app import app
        c = TestClient(app)
        resp = c.get("/api/integrations/stats")
        assert resp.status_code == 401, (
            "integration circuit-breaker stats are exposed anonymously"
        )


# --------------------------------------------------------------------------
# G2b — legacy /api/billing/webhook alias stays fail-closed (404)
# --------------------------------------------------------------------------

class TestLegacyBillingWebhookClosed:
    def test_legacy_billing_webhook_not_registered(self):
        """Stripe webhook processing was removed; the legacy /api/billing/webhook
        alias referenced a module that no longer exists and was silently
        swallowed by except ImportError while logging a false '✓ Loaded'.
        The surface must stay absent (404 = fail-closed), never an anonymous
        processing endpoint."""
        from main_api_app import app
        c = TestClient(app)
        resp = c.post("/api/billing/webhook", json={"type": "invoice.paid"})
        assert resp.status_code == 404
        routes = {getattr(r, "path", "") for r in app.routes}
        assert "/api/billing/webhook" not in routes


# --------------------------------------------------------------------------
# G3 — twitter_routes
# --------------------------------------------------------------------------

class TestTwitterAuth:
    def _anon(self):
        return _app_with(twr.router)

    def test_post_tweet_anonymous_401(self):
        resp = self._anon().post("/api/twitter/tweets",
                                 json={"text": "hello world"})
        assert resp.status_code == 401

    def test_user_tweets_anonymous_401(self):
        resp = self._anon().get("/api/twitter/users/elon/tweets")
        assert resp.status_code == 401

    def test_search_anonymous_401(self):
        resp = self._anon().get("/api/twitter/search/recent", params={"query": "ai"})
        assert resp.status_code == 401

    def test_status_public(self):
        resp = self._anon().get("/api/twitter/status")
        assert resp.status_code == 200

    def test_health_public(self):
        resp = self._anon().get("/api/twitter/health")
        assert resp.status_code == 200


# --------------------------------------------------------------------------
# G4 — bamboohr_routes
# --------------------------------------------------------------------------

class TestBambooHRAuth:
    def _anon(self):
        return _app_with(bhr.router)

    def test_list_employees_anonymous_401(self):
        assert self._anon().get("/api/bamboohr/employees").status_code == 401

    def test_get_employee_anonymous_401(self):
        assert self._anon().get("/api/bamboohr/employees/emp1").status_code == 401

    def test_create_employee_anonymous_401(self):
        resp = self._anon().post("/api/bamboohr/employees", json={
            "firstName": "A", "lastName": "B", "email": "a@b.com",
        })
        assert resp.status_code == 401

    def test_time_off_anonymous_401(self):
        assert self._anon().get("/api/bamboohr/time-off/requests").status_code == 401

    def test_status_public(self):
        assert self._anon().get("/api/bamboohr/status").status_code == 200


class TestBambooHRAuthenticated:
    def test_create_employee_works(self, user):
        c = _app_with(bhr.router, auth_user=user)
        resp = c.post("/api/bamboohr/employees", json={
            "firstName": "A", "lastName": "B", "email": "a@b.com",
        })
        assert resp.status_code == 200


# --------------------------------------------------------------------------
# G5 — discord_routes (data/write endpoints)
# --------------------------------------------------------------------------

class TestDiscordAuth:
    def _anon(self):
        return _app_with(dr.router)

    def _call(self, method, path, **kw):
        with patch("integrations.discord_routes.discord_service", MagicMock()):
            resp = getattr(self._anon(), method)(path, **kw)
        return resp

    def test_user_anonymous_401(self):
        assert self._call("get", "/api/discord/user").status_code == 401

    def test_guilds_anonymous_401(self):
        assert self._call("get", "/api/discord/guilds").status_code == 401

    def test_guild_channels_anonymous_401(self):
        assert self._call("get", "/api/discord/guilds/g1/channels").status_code == 401

    def test_send_message_anonymous_401(self):
        resp = self._call("post", "/api/discord/channels/c1/messages",
                          json={"channel_id": "c1", "content": "hi"})
        assert resp.status_code == 401

    def test_channel_messages_anonymous_401(self):
        assert self._call("get", "/api/discord/channels/c1/messages").status_code == 401

    def test_search_anonymous_401(self):
        resp = self._call("post", "/api/discord/search", json={"query": "x"})
        assert resp.status_code == 401

    def test_items_anonymous_401(self):
        assert self._call("get", "/api/discord/items").status_code == 401

    def test_status_public(self):
        from unittest.mock import AsyncMock
        with patch("integrations.discord_routes.discord_service",
                   MagicMock(health_check=AsyncMock(return_value={"ok": True}),
                             client_id="abc")):
            resp = self._anon().get("/api/discord/status")
        assert resp.status_code == 200

    def test_auth_url_public(self):
        with patch("integrations.discord_routes.discord_service",
                   MagicMock(get_authorization_url=lambda u: "https://discord.com/oauth")):
            resp = self._anon().get("/api/discord/auth/url")
        assert resp.status_code == 200

    def test_health_public(self):
        from unittest.mock import AsyncMock
        with patch("integrations.discord_routes.discord_service",
                   MagicMock(health_check=AsyncMock(return_value={"ok": True}),
                             client_id="abc")):
            resp = self._anon().get("/api/discord/health")
        assert resp.status_code == 200


# --------------------------------------------------------------------------
# G6 — slack_routes (remaining bare data/write endpoints)
# --------------------------------------------------------------------------

class TestSlackAuth:
    def _anon(self):
        return _app_with(sr.router)

    def test_list_channels_anonymous_401(self):
        assert self._anon().get("/api/slack/channels").status_code == 401

    def test_get_channel_anonymous_401(self):
        assert self._anon().get("/api/slack/channels/C1").status_code == 401

    def test_get_user_anonymous_401(self):
        assert self._anon().get("/api/slack/users/U1").status_code == 401

    def test_conversation_history_anonymous_401(self):
        assert self._anon().get(
            "/api/slack/conversations/history", params={"channel": "C1"}
        ).status_code == 401

    def test_add_reaction_anonymous_401(self):
        resp = self._anon().post("/api/slack/reactions/add",
                                 params={"channel": "C1", "timestamp": "1", "reaction": ":x:"})
        assert resp.status_code == 401

    def test_status_public(self):
        assert self._anon().get("/api/slack/status").status_code == 200

    def test_health_public(self):
        assert self._anon().get("/api/slack/health").status_code == 200
