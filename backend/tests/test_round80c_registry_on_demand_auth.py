"""RED tests — Round 80c: registry-on-demand integration routers.

These routers are lazy-loaded by POST /api/integrations/{name}/load (auth-
gated load) and then serve data/WRITE endpoints with NO user authentication —
anyone who ever triggers a load (or hits the auto-load middleware) gets
anonymous read + write access (body: cost-bearing deepgram transcription,
Twilio SMS/calls, LinkedIn shares, Obsidian note writes, okta user directory).

Wave-93..105 convention applied: data/action routes require
`current_user: User = Depends(get_current_user)`; /auth/url, /auth/callback,
/status, /health, /webhook stay public (protocol-authenticated).

Routers covered: linear, tableau, intercom, freshdesk, twilio, linkedin,
obsidian, okta, workday, webex, deepgram, email.
(sendgrid skipped — all 4 routes are static OAuth-flow metadata per wave 93.)

TDD: anonymous-401 tests were RED (200/422) before each gate.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import (
    deepgram_routes as dgr,
    email_routes as emr,
    freshdesk_routes as fdr,
    intercom_routes as icr,
    linear_routes as lnr,
    linkedin_routes as lir,
    obsidian_routes as obr,
    okta_routes as okr,
    tableau_routes as tbr,
    twilio_routes as twr,
    webex_routes as wxr,
    workday_routes as wdr,
)


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "r80c-user"
    u.email = "r80c@x.com"
    return u


def _client(router, authed=False, user=None):
    app = FastAPI()
    app.include_router(router)
    if authed:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _anon(router):
    return _client(router, authed=False)


def _authed(router, user):
    return _client(router, authed=True, user=user)


class _AuthMixin:
    """Generic anon-401 + public contract checks for one router."""

    ROUTER = None

    @pytest.fixture
    def anon(self):
        return _anon(self.ROUTER)

    @pytest.fixture
    def authed(self, user):
        return _authed(self.ROUTER, user)

    def check_anon(self, anon, method, path, ok_statuses=(401,), **kw):
        resp = getattr(anon, method)(path, **kw)
        assert resp.status_code in ok_statuses, (
            f"{method.upper()} {path}: expected {ok_statuses}, got {resp.status_code}"
        )


class TestLinear(_AuthMixin):
    ROUTER = lnr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "get", "/api/linear/viewer")
        self.check_anon(anon, "get", "/api/linear/issues")
        self.check_anon(anon, "post", "/api/linear/issues",
                        json={"title": "t", "team_id": "t1"})
        self.check_anon(anon, "get", "/api/linear/teams")
        self.check_anon(anon, "get", "/api/linear/projects")
        self.check_anon(anon, "post", "/api/linear/search", json={"query": "q"})

    def test_oauth_and_status_public(self, anon):
        assert anon.get("/api/linear/auth/url").status_code == 200
        assert anon.get("/api/linear/callback", params={"code": "c"}).status_code != 404
        assert anon.get("/api/linear/status").status_code == 200
        assert anon.get("/api/linear/health").status_code == 200


class TestTableau(_AuthMixin):
    ROUTER = tbr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "post", "/api/tableau/auth/signin",
                        json={"username": "u", "password": "p"})
        self.check_anon(anon, "get", "/api/tableau/workbooks")
        self.check_anon(anon, "get", "/api/tableau/views")
        self.check_anon(anon, "get", "/api/tableau/datasources")

    def test_oauth_and_status_public(self, anon):
        assert anon.get("/api/tableau/auth/url").status_code == 200
        assert anon.get("/api/tableau/status").status_code == 200
        assert anon.get("/api/tableau/health").status_code == 200


class TestIntercom(_AuthMixin):
    ROUTER = icr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "get", "/intercom/contacts")
        self.check_anon(anon, "get", "/intercom/conversations")
        self.check_anon(anon, "get", "/intercom/admins", params={"access_token": "t"})
        self.check_anon(anon, "post", "/intercom/search", json={"query": "q"})

    def test_oauth_and_status_public(self, anon):
        assert anon.get("/intercom/auth/url").status_code == 200
        assert anon.post("/intercom/auth/callback", json={"code": "c"}).status_code != 404
        assert anon.get("/intercom/status").status_code == 200
        assert anon.get("/intercom/health").status_code == 200


class TestFreshdesk(_AuthMixin):
    ROUTER = fdr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "get", "/freshdesk/tickets")
        self.check_anon(anon, "post", "/freshdesk/tickets",
                        json={"subject": "s", "description": "d", "email": "a@b.c"})
        self.check_anon(anon, "get", "/freshdesk/tickets/1")
        self.check_anon(anon, "put", "/freshdesk/tickets/1", json={"status": 3})
        self.check_anon(anon, "get", "/freshdesk/contacts")
        self.check_anon(anon, "get", "/freshdesk/agents")
        self.check_anon(anon, "post", "/freshdesk/search/tickets", json={"query": "q"})

    def test_oauth_and_status_public(self, anon):
        assert anon.get("/freshdesk/auth/url").status_code == 200
        assert anon.get("/freshdesk/status").status_code == 200
        assert anon.get("/freshdesk/health").status_code == 200


class TestTwilio(_AuthMixin):
    ROUTER = twr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "post", "/api/twilio/sms/send",
                        json={"to": "+1", "body": "hi"})
        self.check_anon(anon, "get", "/api/twilio/messages")
        self.check_anon(anon, "post", "/api/twilio/calls/make",
                        json={"to": "+1", "twiml_url": "http://x"})
        self.check_anon(anon, "get", "/api/twilio/calls")
        self.check_anon(anon, "get", "/api/twilio/account")

    def test_public_surfaces(self, anon):
        assert anon.get("/api/twilio/auth/url").status_code == 200
        assert anon.get("/api/twilio/status").status_code == 200
        assert anon.get("/api/twilio/health").status_code == 200
        # inbound webhook stays protocol-authenticated (Twilio signature)
        assert anon.post("/api/twilio/webhook").status_code != 404


class TestLinkedIn(_AuthMixin):
    ROUTER = lir.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "get", "/api/linkedin/profile",
                        params={"access_token": "t"})
        self.check_anon(anon, "post", "/api/linkedin/share",
                        params={"access_token": "t", "text": "hello"})

    def test_oauth_and_status_public(self, anon):
        assert anon.get("/api/linkedin/auth/url").status_code == 200
        assert anon.post("/api/linkedin/callback", json={"code": "c"}).status_code != 404
        assert anon.get("/api/linkedin/status").status_code == 200
        assert anon.get("/api/linkedin/health").status_code == 200


class TestObsidian(_AuthMixin):
    ROUTER = obr.router

    def test_data_anonymous_401(self, anon):
        hdrs = {"api-token": "x"}  # FastAPI kebab-cases Header(...) names
        self.check_anon(anon, "get", "/obsidian/notes", headers=hdrs)
        self.check_anon(anon, "post", "/obsidian/notes",
                        params={"path": "/a.md", "content": "x"}, headers=hdrs)

    def test_status_public(self, anon):
        # SSRF guard rejects the localhost default; pass a benign plugin URL.
        resp = anon.get("/obsidian/status",
                        headers={"api-token": "x",
                                 "plugin-url": "http://obsidian.example:27123"})
        assert resp.status_code == 200


class TestOkta(_AuthMixin):
    ROUTER = okr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "get", "/api/okta/users")

    def test_health_public(self, anon):
        assert anon.get("/api/okta/health").status_code == 200


class TestWorkday(_AuthMixin):
    ROUTER = wdr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "get", "/api/workday/workers/W1")

    def test_health_public(self, anon):
        assert anon.get("/api/workday/health").status_code == 200


class TestWebex(_AuthMixin):
    ROUTER = wxr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "get", "/api/webex/rooms")

    def test_health_public(self, anon):
        assert anon.get("/api/webex/health").status_code == 200


class TestDeepgram(_AuthMixin):
    ROUTER = dgr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "post", "/api/deepgram/transcribe/url",
                        json={"audio_url": "https://x/a.mp3"})
        self.check_anon(anon, "post", "/api/deepgram/transcribe/file",
                        files={"file": ("a.mp3", b"dummy", "audio/mpeg")})
        self.check_anon(anon, "get", "/api/deepgram/projects")
        self.check_anon(anon, "get", "/api/deepgram/usage/p1")

    def test_status_public(self, anon):
        assert anon.get("/api/deepgram/status").status_code == 200
        assert anon.get("/api/deepgram/health").status_code == 200


class TestEmail(_AuthMixin):
    ROUTER = emr.router

    def test_data_anonymous_401(self, anon):
        self.check_anon(anon, "post", "/api/email/send",
                        json={"to": "a@b.c", "subject": "s", "body": "b"})
        self.check_anon(anon, "get", "/api/email/messages")

    def test_oauth_and_health_public(self, anon):
        assert anon.get("/api/email/auth/url").status_code == 200
        assert anon.get("/api/email/callback").status_code != 404
        assert anon.get("/api/email/health").status_code == 200


class TestAuthedFlows:
    """Authenticated calls still reach the handlers (no 401 over-gating)."""

    def test_linear_create_issue_authed(self, user):
        c = _authed(lnr.router, user)
        resp = c.post("/api/linear/issues", json={"title": "t", "team_id": "t1"})
        assert resp.status_code in (200, 500)  # 500 = service mock failure, not auth

    def test_email_send_authed(self, user):
        c = _authed(emr.router, user)
        resp = c.post("/api/email/send", json={"to": "a@b.c", "subject": "s", "body": "b"})
        assert resp.status_code in (200, 500)

    def test_freshdesk_tickets_authed(self, user):
        c = _authed(fdr.router, user)
        resp = c.get("/freshdesk/tickets")
        # 503 = "Freshdesk not configured" (unconfigured state, not auth)
        assert resp.status_code in (200, 500, 503)