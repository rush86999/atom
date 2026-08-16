# -*- coding: utf-8 -*-
"""Coverage wave 99 — verified gap batch C.

Targets (verified under 80% by existing suites):
1.  core/canvas_email_service.py            (71%)
2.  core/communication/adapters/teams.py    (47%)

No network, no real LLM — httpx and DB sessions are mocked everywhere.
Plain pytest + unittest.mock (asyncio_mode=auto).
"""
import hashlib
import hmac as hmac_mod
import time
from base64 import urlsafe_b64encode as _b64u
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from jose.utils import base64url_encode


# --------------------------------------------------------------------------- #
# helpers: RSA/JWT fixtures for Teams verification
# --------------------------------------------------------------------------- #
def _b64int(i):
    return base64url_encode(i.to_bytes((i.bit_length() + 7) // 8, "big")).decode()


def _make_keypair(kid="test-kid"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    jwk = {
        "kid": kid,
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "n": _b64int(pub.n),
        "e": _b64int(pub.e),
    }
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwk, pem, priv


def _sign(priv_pem, claims, kid="test-kid", algorithm="RS256"):
    return jose_jwt.encode(claims, priv_pem, algorithm=algorithm, headers={"kid": kid})


def _req(auth=None):
    headers = {}
    if auth is not None:
        headers["Authorization"] = auth
    req = MagicMock()
    req.headers = headers
    return req


# --------------------------------------------------------------------------- #
# core/communication/adapters/teams.py
# --------------------------------------------------------------------------- #
class TestTeamsAdapterInit:
    def test_init_explicit_and_env_fallback(self, monkeypatch):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        assert (a.app_id, a.app_password) == ("app", "pw")
        monkeypatch.setenv("MICROSOFT_APP_ID", "env-app")
        monkeypatch.setenv("MICROSOFT_APP_PASSWORD", "env-pw")
        b = T.TeamsAdapter()
        assert (b.app_id, b.app_password) == ("env-app", "env-pw")


class TestTeamsJwks:
    async def test_jwks_cached(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        a.jwks_keys = [{"kid": "k"}]
        a.jwks_expiry = time.time() + 1000
        assert await a._get_jwks_keys() == [{"kid": "k"}]

    async def test_jwks_fetch_success(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        client = AsyncMock()
        r1 = MagicMock(); r1.json = lambda: {"jwks_uri": "https://x/keys"}
        r2 = MagicMock(); r2.json = lambda: {"keys": [{"kid": "k"}]}
        client.get = AsyncMock(side_effect=[r1, r2])
        cm = MagicMock(); cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch.object(T.httpx, "AsyncClient", return_value=cm):
            keys = await a._get_jwks_keys()
        assert keys == [{"kid": "k"}]
        assert a.jwks_expiry > time.time()

    async def test_jwks_fetch_failure_returns_empty(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        client = AsyncMock()
        client.get = AsyncMock(side_effect=RuntimeError("net down"))
        cm = MagicMock(); cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch.object(T.httpx, "AsyncClient", return_value=cm):
            assert await a._get_jwks_keys() == []


class TestTeamsBotToken:
    async def test_cached_token(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        a._access_token = "tok"
        a._token_expiry = time.time() + 100
        assert await a._get_bot_access_token() == "tok"

    async def test_missing_credentials(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter(None, None)
        assert await a._get_bot_access_token() is None

    async def test_token_success_and_failure(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        client = AsyncMock()
        ok = MagicMock(); ok.json = lambda: {"access_token": "T", "expires_in": 100}
        client.post = AsyncMock(return_value=ok)
        cm = MagicMock(); cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch.object(T.httpx, "AsyncClient", return_value=cm):
            assert await a._get_bot_access_token() == "T"
            assert a._token_expiry > time.time()
        a._access_token = None
        a._token_expiry = 0
        client.post = AsyncMock(side_effect=RuntimeError("boom"))
        cm2 = MagicMock(); cm2.__aenter__ = AsyncMock(return_value=client)
        cm2.__aexit__ = AsyncMock(return_value=False)
        with patch.object(T.httpx, "AsyncClient", return_value=cm2):
            assert await a._get_bot_access_token() is None


class TestTeamsVerifyRequest:
    async def test_no_app_id_rejected(self, monkeypatch):
        from core.communication.adapters import teams as T

        monkeypatch.delenv("ENVIRONMENT", raising=False)
        a = T.TeamsAdapter(None, "pw")
        assert await a.verify_request(_req(), b"") is False

    async def test_dev_bypass_optin(self, monkeypatch):
        from core.communication.adapters import teams as T

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("BYPASS_WEBHOOK_SIGNATURE", "true")
        a = T.TeamsAdapter(None, "pw")
        assert await a.verify_request(_req(), b"") is True
        monkeypatch.setenv("BYPASS_WEBHOOK_SIGNATURE", "false")
        assert await a.verify_request(_req(), b"") is False

    async def test_bad_authorization_header(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        assert await a.verify_request(_req("Basic abc"), b"") is False
        assert await a.verify_request(_req(""), b"") is False

    async def test_missing_kid(self):
        from core.communication.adapters import teams as T

        jwk, pem, priv = _make_keypair()
        # token without kid header
        token = jose_jwt.encode({"aud": "app"}, priv, algorithm="RS256")
        a = T.TeamsAdapter("app", "pw")
        assert await a.verify_request(_req(f"Bearer {token}"), b"") is False

    async def test_no_jwks_keys(self):
        from core.communication.adapters import teams as T

        jwk, pem, priv = _make_keypair()
        token = _sign(priv, {"aud": "app"})
        a = T.TeamsAdapter("app", "pw")
        a._get_jwks_keys = AsyncMock(return_value=[])
        assert await a.verify_request(_req(f"Bearer {token}"), b"") is False

    async def test_no_matching_kid(self):
        from core.communication.adapters import teams as T

        jwk, pem, priv = _make_keypair(kid="other-kid")
        token = _sign(priv, {"aud": "app"}, kid="test-kid")
        a = T.TeamsAdapter("app", "pw")
        a._get_jwks_keys = AsyncMock(return_value=[jwk])
        assert await a.verify_request(_req(f"Bearer {token}"), b"") is False

    async def test_bad_jwk_construct(self):
        from core.communication.adapters import teams as T

        token = _sign(_make_keypair()[2], {"aud": "app"})
        a = T.TeamsAdapter("app", "pw")
        bad = {"kid": "test-kid", "kty": "RSA", "n": "!!!", "e": "!!!"}
        a._get_jwks_keys = AsyncMock(return_value=[bad])
        assert await a.verify_request(_req(f"Bearer {token}"), b"") is False

    def _adapter_with_keys(self):
        from core.communication.adapters import teams as T

        jwk, pem, priv = _make_keypair()
        a = T.TeamsAdapter("app", "pw")
        a._get_jwks_keys = AsyncMock(return_value=[jwk])
        return a, priv

    async def test_success(self):
        from core.communication.adapters import teams as T

        a, priv = self._adapter_with_keys()
        now = time.time()
        token = _sign(priv, {
            "aud": "app",
            "iss": "https://api.botframework.com",
            "exp": int(now) + 200,
            "iat": int(now),
            "jti": "jti-ok",
        })
        assert await a.verify_request(_req(f"Bearer {token}"), b"") is True

    async def test_replay_detected(self):
        from core.communication.adapters import teams as T

        a, priv = self._adapter_with_keys()
        now = time.time()
        token = _sign(priv, {
            "aud": "app", "iss": "https://api.botframework.com",
            "exp": int(now) + 200, "iat": int(now), "jti": "jti-replay",
        })
        T._seen_jwt_ids["jti-replay"] = now  # already seen
        assert await a.verify_request(_req(f"Bearer {token}"), b"") is False
        T._seen_jwt_ids.pop("jti-replay", None)

    async def test_expired_and_stale_iat_and_bad_sig(self):
        from core.communication.adapters import teams as T

        a, priv = self._adapter_with_keys()
        now = time.time()
        expired = _sign(priv, {
            "aud": "app", "iss": "https://api.botframework.com",
            "exp": int(now) - 10, "iat": int(now),
        })
        assert await a.verify_request(_req(f"Bearer {expired}"), b"") is False

        stale = _sign(priv, {
            "aud": "app", "iss": "https://api.botframework.com",
            "exp": int(now) + 200, "iat": int(now) - 3600,
        })
        assert await a.verify_request(_req(f"Bearer {stale}"), b"") is False

        other_priv = _make_keypair(kid="test-kid")[2]
        bad_sig = _sign(other_priv, {
            "aud": "app", "iss": "https://api.botframework.com",
            "exp": int(now) + 200, "iat": int(now),
        })
        assert await a.verify_request(_req(f"Bearer {bad_sig}"), b"") is False

        garbage = "Bearer not.a.jwt"
        assert await a.verify_request(_req(garbage), b"") is False


class TestTeamsWebhookSignature:
    def _adapter(self):
        from core.communication.adapters import teams as T

        return T.TeamsAdapter("app", "pw")

    def _sig(self, payload: bytes, timestamp: str, secret="pw", prefix="HMAC "):
        msg = f"{timestamp}.{payload.decode('utf-8', errors='ignore')}"
        digest = hmac_mod.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
        return prefix + base64url_encode(digest).decode()

    def test_bad_timestamp(self):
        assert self._adapter().verify_webhook_signature(b"x", "sig", "notafloat") is False

    def test_timestamp_too_old(self):
        old = str(time.time() - 3600)
        assert self._adapter().verify_webhook_signature(b"x", "sig", old) is False

    def test_missing_signature_or_secret(self):
        a = self._adapter()
        now = str(time.time())
        assert a.verify_webhook_signature(b"x", "", now) is False
        b = type(a)(app_id="app", app_password=None)
        assert b.verify_webhook_signature(b"x", "sig", now) is False

    def test_valid_and_invalid_hmac(self):
        a = self._adapter()
        payload = b'{"a":1}'
        now = str(time.time())
        assert a.verify_webhook_signature(payload, self._sig(payload, now), now) is True
        assert a.verify_webhook_signature(
            payload, self._sig(payload, now, secret="wrong"), now
        ) is False
        assert a.verify_webhook_signature(payload, "Bearer ???", now) is False

    def test_bearer_prefix_stripped(self):
        a = self._adapter()
        payload = b"x"
        now = str(time.time())
        sig = self._sig(payload, now, prefix="Bearer ")
        assert a.verify_webhook_signature(payload, sig, now) is True


class TestTeamsNormalize:
    def test_non_dict(self):
        from core.communication.adapters import teams as T

        assert T.TeamsAdapter().normalize_payload("nope") == {}

    def test_non_message_activity(self):
        from core.communication.adapters import teams as T

        assert T.TeamsAdapter().normalize_payload({"type": "typing"}) == {}

    def test_message_activity(self):
        from core.communication.adapters import teams as T

        out = T.TeamsAdapter().normalize_payload({
            "type": "message",
            "id": "act-1",
            "from": {"id": "u1", "name": "User One"},
            "conversation": {"id": "conv-1"},
            "serviceUrl": "https://svc",
            "text": "hello",
        })
        assert out["platform"] == "teams"
        assert out["user_id"] == "u1"
        assert out["username"] == "User One"
        assert out["channel_id"] == "conv-1"
        assert out["content"] == "hello"
        assert out["metadata"]["serviceUrl"] == "https://svc"
        assert out["metadata"]["activityId"] == "act-1"
        assert out["metadata"]["full_data"]["id"] == "act-1"


class TestTeamsSendMessage:
    async def test_missing_metadata(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        assert await a.send_message("conv", "hi", None) is False
        assert await a.send_message("conv", "hi", {}) is False

    async def test_no_token(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        a._get_bot_access_token = AsyncMock(return_value=None)
        assert await a.send_message("conv", "hi", {"serviceUrl": "https://s"}) is False

    async def test_success_and_failure(self):
        from core.communication.adapters import teams as T

        a = T.TeamsAdapter("app", "pw")
        a._get_bot_access_token = AsyncMock(return_value="tok")
        client = AsyncMock()
        client.post = AsyncMock(return_value=MagicMock())
        cm = MagicMock(); cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch.object(T.httpx, "AsyncClient", return_value=cm):
            ok = await a.send_message("conv", "hi", {"serviceUrl": "https://s/"})
        assert ok is True
        client.post = AsyncMock(side_effect=RuntimeError("net"))
        cm2 = MagicMock(); cm2.__aenter__ = AsyncMock(return_value=client)
        cm2.__aexit__ = AsyncMock(return_value=False)
        with patch.object(T.httpx, "AsyncClient", return_value=cm2):
            bad = await a.send_message("conv", "hi", {"serviceUrl": "https://s/"})
        assert bad is False


# --------------------------------------------------------------------------- #
# core/canvas_email_service.py
# --------------------------------------------------------------------------- #
class TestEmailCanvasService:
    def _svc(self, first_audit=None, fail_commit=False):
        from core.canvas_email_service import EmailCanvasService

        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.order_by.return_value.first.return_value = first_audit
        db.query.return_value = q
        if fail_commit:
            db.commit.side_effect = RuntimeError("db down")
        return EmailCanvasService(db), db

    def _audit(self, metadata):
        return NS(details_json=metadata)

    # -- create ------------------------------------------------------------- #
    def test_create_success(self):
        svc, db = self._svc()
        out = svc.create_email_canvas("u1", "Hello", ["a@b.c"], agent_id="ag1")
        assert out["success"] is True
        assert out["thread_id"]
        assert out["draft_id"]
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_create_explicit_canvas_id(self):
        svc, _ = self._svc()
        out = svc.create_email_canvas("u1", "S", ["a@b.c"], canvas_id="c-1")
        assert out["success"] is True and out["canvas_id"] == "c-1"

    def test_create_failure_rolls_back(self):
        svc, db = self._svc(fail_commit=True)
        out = svc.create_email_canvas("u1", "S", ["a@b.c"])
        assert out["success"] is False and "db down" in out["error"]
        db.rollback.assert_called_once()

    # -- add_message -------------------------------------------------------- #
    def test_add_message_not_found(self):
        svc, _ = self._svc(first_audit=None)
        out = svc.add_message_to_thread("c", "u1", "x@y.z", ["a@b.c"], "S", "B")
        assert out == {"success": False, "error": "Email canvas not found"}

    def test_add_message_success(self):
        audit = self._audit({"thread_id": "t1", "messages": []})
        svc, db = self._svc(first_audit=audit)
        out = svc.add_message_to_thread("c", "u1", "x@y.z", ["a@b.c"], "S", "B",
                                        attachments=[{"name": "f"}])
        assert out["success"] is True and out["thread_id"] == "t1"
        db.add.assert_called_once()

    def test_add_message_failure(self):
        audit = self._audit({"thread_id": "t1", "messages": []})
        svc, db = self._svc(first_audit=audit, fail_commit=True)
        out = svc.add_message_to_thread("c", "u1", "x@y.z", ["a@b.c"], "S", "B")
        assert out["success"] is False
        db.rollback.assert_called_once()

    # -- save_draft --------------------------------------------------------- #
    def test_save_draft_not_found(self):
        svc, _ = self._svc(first_audit=None)
        out = svc.save_draft("c", "u1", ["a@b.c"])
        assert out == {"success": False, "error": "Email canvas not found"}

    def test_save_draft_success_reuses_draft_id(self):
        audit = self._audit({"draft": {"draft_id": "d-1"}})
        svc, db = self._svc(first_audit=audit)
        out = svc.save_draft("c", "u1", ["a@b.c"], cc_emails=["c@d.e"], subject="S", body="B")
        assert out["success"] is True and out["draft_id"] == "d-1"
        db.add.assert_called_once()

    def test_save_draft_generates_draft_id_when_missing(self):
        audit = self._audit({})
        svc, _ = self._svc(first_audit=audit)
        out = svc.save_draft("c", "u1", ["a@b.c"])
        assert out["success"] is True and out["draft_id"]

    def test_save_draft_failure(self):
        svc, db = self._svc(first_audit=self._audit({}), fail_commit=True)
        out = svc.save_draft("c", "u1", ["a@b.c"])
        assert out["success"] is False
        db.rollback.assert_called_once()

    # -- categorize --------------------------------------------------------- #
    def test_categorize_not_found(self):
        svc, _ = self._svc(first_audit=None)
        out = svc.categorize_email("c", "u1", "Work")
        assert out == {"success": False, "error": "Email canvas not found"}

    def test_categorize_success_appends(self):
        audit = self._audit({"categories": [{"name": "old"}]})
        svc, db = self._svc(first_audit=audit)
        out = svc.categorize_email("c", "u1", "Work", color="#ff0000")
        assert out["success"] is True and out["category"] == "Work"
        details = db.add.call_args[0][0].details_json
        assert details["categories"][1]["name"] == "Work"
        assert details["categories"][1]["color"] == "#ff0000"
        assert details["categories"][1]["categorized_by"] == "u1"
        assert details["component_type"] == "category_bucket"

    def test_categorize_failure(self):
        svc, db = self._svc(first_audit=self._audit({}), fail_commit=True)
        out = svc.categorize_email("c", "u1", "Work")
        assert out["success"] is False
        db.rollback.assert_called_once()


class TestEmailDataclasses:
    def test_email_message_defaults(self):
        from core.canvas_email_service import EmailMessage

        m = EmailMessage("m1", "a@b.c", ["x@y.z"])
        assert m.cc_emails == [] and m.attachments == [] and m.read is False
        assert m.timestamp is not None and m.thread_id is None

    def test_email_draft_defaults(self):
        from core.canvas_email_service import EmailDraft

        d = EmailDraft("d1", ["x@y.z"])
        assert d.cc_emails == [] and d.attachments == []

    def test_message_and_draft_to_dict(self):
        from core.canvas_email_service import EmailCanvasService, EmailDraft, EmailMessage

        ts = datetime(2026, 1, 1, 12, 0, 0)
        m = EmailMessage("m1", "a@b.c", ["x@y.z"], cc_emails=["c@d.e"],
                         subject="S", body="B", timestamp=ts, thread_id="t",
                         attachments=[{"n": 1}], read=True)
        md = EmailCanvasService.__new__(EmailCanvasService)._message_to_dict(m)
        assert md["timestamp"] == ts.isoformat() and md["read"] is True

        d = EmailDraft("d1", ["x@y.z"], cc_emails=["c@d.e"], subject="S",
                       body="B", attachments=[{"n": 1}])
        dd = EmailCanvasService.__new__(EmailCanvasService)._draft_to_dict(d)
        assert dd == {
            "draft_id": "d1", "to_emails": ["x@y.z"], "cc_emails": ["c@d.e"],
            "subject": "S", "body": "B", "attachments": [{"n": 1}],
        }
