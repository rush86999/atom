"""Coverage wave W65c — integrations route/service coverage push.

Targets (>=95% statement coverage, standalone):
- integrations/signal_service.py   (service class, was NEVER exercised)
- integrations/calendly_routes.py  (was NEVER tested; CALENDLY_AVAILABLE=False path)
- integrations/deepgram_routes.py  (was NEVER tested; DEEPGRAM_AVAILABLE=False path)
- integrations/twilio_routes.py    (was UNIMPORTABLE — see regression tests)
- integrations/intercom_routes.py  (router-level coverage)
- integrations/linear_routes.py    (was UNIMPORTABLE — see regression tests)

Pattern: FastAPI TestClient + patch on the REAL module the app imports
(`integrations.<module>`, NOT `backend.integrations.<module>` — the backend/
prefix is a phantom double-import and patches miss). No network, no LLM, no DB.

Bugs found + fixed in the 6 assigned modules (regression tests below):
1. twilio_routes imported `get_twilio_service` unguarded, but twilio_service.py
   has the factory commented out -> ImportError at import -> router unmountable
   (every /api/twilio/* route 404'd). Now try/except-guarded per the
   calendly/deepgram convention with a TWILIO_AVAILABLE flag and mock-mode
   responses — test_twilio_router_mounts / test_twilio_import_success_branch.
2. twilio_routes webhook referenced `_bg_tasks` which was only defined INSIDE
   the module docstring -> NameError on every POST /api/twilio/webhook (500
   even after a successful bridge dispatch). Moved to real module scope —
   test_webhook_success_dispatches_to_bridge.
3. linear_routes imported a `linear_service` singleton that does not exist in
   linear_service.py (legacy instance removed) -> ImportError at import ->
   router unmountable. Now constructed from LinearService at module level —
   test_linear_router_mounts / test_linear_singleton_created.
4. linear_routes /callback leaked `str(e)` to the client (repo policy: never
   leak str(e)) — test_callback_error_no_str_leak.
"""
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_client(router):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _async_svc(methods, **attrs):
    """Build a MagicMock service with AsyncMock method stubs."""
    svc = MagicMock()
    for name, ret in methods.items():
        setattr(svc, name, AsyncMock(return_value=ret))
    for name, val in attrs.items():
        setattr(svc, name, val)
    return svc


# ---------------------------------------------------------------------------
# SignalService (integrations/signal_service.py)
# ---------------------------------------------------------------------------

class TestSignalService:
    URL = "https://signal.example.com"

    def _svc(self, **config):
        config.setdefault("api_url", self.URL)
        from integrations.signal_service import SignalService
        return SignalService(tenant_id="t-signal", config=config)

    async def test_init_defaults_from_env(self, monkeypatch):
        from integrations.signal_service import SignalService
        monkeypatch.delenv("SIGNAL_API_URL", raising=False)
        monkeypatch.delenv("SIGNAL_SENDER_NUMBER", raising=False)
        svc = SignalService(tenant_id="t", config={"api_url": self.URL})
        assert svc.base_url == self.URL
        assert svc.sender_number is None
        assert svc.tenant_id == "t"
        assert svc.config == {"api_url": self.URL}
        await svc.close()

    async def test_init_env_fallbacks(self, monkeypatch):
        from integrations.signal_service import SignalService
        monkeypatch.setenv("SIGNAL_API_URL", self.URL)
        monkeypatch.setenv("SIGNAL_SENDER_NUMBER", "+123456")
        svc = SignalService(tenant_id="t", config={})
        assert svc.base_url == self.URL
        assert svc.sender_number == "+123456"
        await svc.close()

    async def test_init_config_none_defaults_empty(self, monkeypatch):
        from integrations.signal_service import SignalService
        monkeypatch.delenv("SIGNAL_API_URL", raising=False)
        with pytest.raises(ValueError):
            SignalService(tenant_id="t", config=None)

    async def test_init_ssrf_blocked_raises(self):
        from integrations.signal_service import SignalService
        with pytest.raises(ValueError, match="Invalid api_url"):
            SignalService(tenant_id="t", config={"api_url": "http://169.254.169.254"})

    async def test_init_ssrf_blocked_localhost_default(self, monkeypatch):
        from integrations.signal_service import SignalService
        monkeypatch.delenv("SIGNAL_API_URL", raising=False)
        with pytest.raises(ValueError):
            SignalService(tenant_id="t", config={})

    async def test_close_acloses_client(self):
        svc = self._svc()
        svc.client = MagicMock()
        svc.client.aclose = AsyncMock(return_value=None)
        await svc.close()
        svc.client.aclose.assert_awaited_once()

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        ops = {op["id"] for op in caps["operations"]}
        assert ops == {"send_message", "receive_message", "get_profile"}
        assert caps["required_params"] == ["api_url", "sender_number"]
        assert caps["supports_webhooks"] is True

    def test_health_check_healthy(self):
        body = self._svc(sender_number="+1").health_check()
        assert body["healthy"] is True
        assert body["status"] == "healthy"
        assert "last_check" in body

    def test_health_check_degraded(self):
        body = self._svc().health_check()
        assert body["healthy"] is False
        assert body["status"] == "degraded"
        assert "not configured" in body["message"]

    async def test_execute_operation_tenant_mismatch(self):
        svc = self._svc()
        result = await svc.execute_operation("send_message", {"recipient": "x", "message": "hi"},
                                             context={"tenant_id": "other"})
        assert result["success"] is False
        assert result["error"] == "Tenant ID validation failed"
        assert result["details"]["reason"] == "cross_tenant_access_prevented"

    async def test_execute_operation_tenant_match_proceeds(self):
        svc = self._svc(sender_number="+1")
        svc.client = MagicMock()
        svc.client.post = AsyncMock(return_value=self._resp_ok())
        result = await svc.execute_operation(
            "send_message", {"recipient": "+2", "message": "hi"},
            context={"tenant_id": "t-signal"})
        assert result["success"] is True
        svc.client.post.assert_awaited_once()

    async def test_execute_operation_no_context_proceeds(self):
        svc = self._svc(sender_number="+1")
        result = await svc.execute_operation("receive_message", {"webhook_url": "https://w.example"})
        assert result["success"] is True
        assert result["result"]["webhook_url"] == "https://w.example"

    async def test_execute_operation_unknown_raises(self):
        svc = self._svc()
        with pytest.raises(NotImplementedError, match="'fax'"):
            await svc.execute_operation("fax", {})

    @staticmethod
    def _resp_ok():
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    @staticmethod
    def _resp_error():
        resp = MagicMock()
        resp.raise_for_status = MagicMock(side_effect=RuntimeError("boom"))
        return resp

    async def test_send_message_success(self):
        svc = self._svc(sender_number="+123456")
        svc.client = MagicMock()
        svc.client.post = AsyncMock(return_value=self._resp_ok())
        result = await svc.execute_operation("send_message", {"recipient": "+1555", "message": "Hello"})
        assert result["success"] is True
        assert result["result"] == {"message_sent": True, "recipient": "+1555"}
        svc.client.post.assert_awaited_once_with(
            f"{self.URL}/v1/send",
            json={"message": "Hello", "number": "+123456", "recipients": ["+1555"]})

    async def test_send_message_missing_parameters(self):
        result = await self._svc().execute_operation("send_message", {"recipient": "+1"})
        assert result["success"] is False
        assert "Missing required parameters" in result["error"]
        assert result["details"]["provided_parameters"] == ["recipient"]

    async def test_send_message_sender_not_configured(self):
        result = await self._svc().execute_operation("send_message", {"recipient": "+1", "message": "m"})
        assert result["success"] is False
        assert result["error"] == "Signal sender number not configured"
        assert result["details"]["tenant_id"] == "t-signal"

    async def test_send_message_http_error(self):
        svc = self._svc(sender_number="+1")
        svc.client = MagicMock()
        svc.client.post = AsyncMock(return_value=self._resp_error())
        result = await svc.execute_operation("send_message", {"recipient": "+2", "message": "m"})
        assert result["success"] is False
        assert result["error"] == "boom"

    async def test_send_message_network_error(self):
        svc = self._svc(sender_number="+1")
        svc.client = MagicMock()
        svc.client.post = AsyncMock(side_effect=RuntimeError("connect failed"))
        result = await svc.execute_operation("send_message", {"recipient": "+2", "message": "m"})
        assert result["success"] is False
        assert result["error"] == "connect failed"

    async def test_receive_message_with_webhook(self):
        svc = self._svc()
        result = await svc.execute_operation("receive_message", {"webhook_url": "https://hook.example"})
        assert result["success"] is True
        assert result["result"]["configure_webhook"] == f"{self.URL}/v1/webhook"

    async def test_receive_message_without_webhook(self):
        result = await self._svc().execute_operation("receive_message", {})
        assert result["success"] is True
        assert result["result"]["webhook_url"] is None

    async def test_get_profile_success(self):
        result = await self._svc().execute_operation("get_profile", {"phone_number": "+1555"})
        assert result["success"] is True
        assert result["result"]["phone_number"] == "+1555"

    async def test_get_profile_missing_phone(self):
        result = await self._svc().execute_operation("get_profile", {})
        assert result["success"] is False
        assert "Missing required parameter" in result["error"]

    async def test_operation_missing_sender_internal(self):
        svc = self._svc()
        result = await svc._send_message({"recipient": "+1", "message": "m"})
        assert result["success"] is False
        assert result["error"] == "Signal sender number not configured"


# ---------------------------------------------------------------------------
# Calendly routes (integrations/calendly_routes.py)
# ---------------------------------------------------------------------------

class TestCalendlyRoutesMock:
    """CALENDLY_AVAILABLE=False (natural import state — factory commented out)."""

    def _client(self):
        from integrations.calendly_routes import router
        return make_client(router)

    def test_auth_url_mock(self):
        resp = self._client().get("/api/calendly/auth/url")
        assert resp.status_code == 200
        assert "INSERT_CLIENT_ID" in resp.json()["url"]
        assert "redirect_uri" in resp.json()["url"]

    def test_callback_mock(self):
        resp = self._client().post("/api/calendly/callback",
                                   json={"code": "c1", "redirect_uri": "http://x/cb"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["code"] == "c1"
        assert "(mock)" in body["message"]

    def test_callback_missing_code_422(self):
        resp = self._client().post("/api/calendly/callback", json={"redirect_uri": "http://x/cb"})
        assert resp.status_code == 422

    def test_user_me_mock(self):
        resp = self._client().get("/api/calendly/user/me", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "mock_user_id"

    def test_event_types_mock(self):
        resp = self._client().get("/api/calendly/event-types",
                                  params={"user_uri": "u", "access_token": "t"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_scheduled_events_mock(self):
        resp = self._client().get("/api/calendly/scheduled-events", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_status_mock(self):
        resp = self._client().get("/api/calendly/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["business_value"]["scheduling_automation"] is True

    def test_health_delegates_to_status_when_unavailable(self):
        resp = self._client().get("/api/calendly/health")
        assert resp.status_code == 200
        assert resp.json()["available"] is False


class TestCalendlyRoutesReal:
    """CALENDLY_AVAILABLE=True + patched get_calendly_service."""

    def _client(self):
        from integrations.calendly_routes import router
        return make_client(router)

    def _svc(self):
        return _async_svc({
            "exchange_token": {"access_token": "at", "refresh_token": "rt"},
            "get_current_user": {"id": "u1", "name": "Alice"},
            "get_event_types": [{"uri": "et1"}],
            "get_scheduled_events": [{"uri": "se1"}],
            "health_check": {"healthy": True, "status": "healthy"},
        }, get_authorization_url=MagicMock(return_value="https://auth.calendly.com/oauth/authorize?redirect=X"))

    def _call(self, method, path, **kw):
        with patch("integrations.calendly_routes.CALENDLY_AVAILABLE", True), \
             patch("integrations.calendly_routes.get_calendly_service",
                   return_value=self._svc(), create=True) as m:
            resp = getattr(self._client(), method)(path, **kw)
            return resp, m

    def test_auth_url_real(self):
        resp, m = self._call("get", "/api/calendly/auth/url", params={"redirect_uri": "http://cb"})
        assert resp.status_code == 200
        assert "redirect=X" in resp.json()["url"]
        m.return_value.get_authorization_url.assert_called_once_with("http://cb")

    def test_callback_real(self):
        resp, m = self._call("post", "/api/calendly/callback",
                             json={"code": "c1", "redirect_uri": "http://cb"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["access_token"] == "at"
        assert body["refresh_token"] == "rt"
        m.return_value.exchange_token.assert_awaited_once_with("c1", "http://cb")

    def test_callback_service_exception_400(self):
        svc = self._svc()
        svc.exchange_token = AsyncMock(side_effect=RuntimeError("calendly secret 123"))
        with patch("integrations.calendly_routes.CALENDLY_AVAILABLE", True), \
             patch("integrations.calendly_routes.get_calendly_service", return_value=svc, create=True):
            resp = self._client().post("/api/calendly/callback",
                                       json={"code": "c1", "redirect_uri": "http://cb"})
        assert resp.status_code == 400
        assert "secret 123" not in resp.text

    def test_user_me_real(self):
        resp, m = self._call("get", "/api/calendly/user/me", params={"access_token": "at"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "u1"
        m.return_value.get_current_user.assert_awaited_once_with("at")

    def test_user_me_service_exception_400(self):
        svc = self._svc()
        svc.get_current_user = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.calendly_routes.CALENDLY_AVAILABLE", True), \
             patch("integrations.calendly_routes.get_calendly_service", return_value=svc, create=True):
            resp = self._client().get("/api/calendly/user/me", params={"access_token": "at"})
        assert resp.status_code == 400

    def test_event_types_real(self):
        resp, m = self._call("get", "/api/calendly/event-types",
                             params={"user_uri": "u1", "access_token": "at", "count": 5})
        assert resp.status_code == 200
        assert resp.json() == [{"uri": "et1"}]
        m.return_value.get_event_types.assert_awaited_once_with("u1", "at", 5)

    def test_event_types_service_exception_400(self):
        svc = self._svc()
        svc.get_event_types = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.calendly_routes.CALENDLY_AVAILABLE", True), \
             patch("integrations.calendly_routes.get_calendly_service", return_value=svc, create=True):
            resp = self._client().get("/api/calendly/event-types",
                                      params={"user_uri": "u1", "access_token": "at"})
        assert resp.status_code == 400

    def test_scheduled_events_real(self):
        resp, m = self._call("get", "/api/calendly/scheduled-events",
                             params={"user_uri": "u1", "access_token": "at", "count": 5, "status": "canceled"})
        assert resp.status_code == 200
        assert resp.json() == [{"uri": "se1"}]
        m.return_value.get_scheduled_events.assert_awaited_once_with("u1", "at", 5, "canceled")

    def test_scheduled_events_no_user_uri_real(self):
        resp, m = self._call("get", "/api/calendly/scheduled-events", params={"access_token": "at"})
        assert resp.status_code == 200
        m.return_value.get_scheduled_events.assert_awaited_once_with(None, "at", 20, "active")

    def test_scheduled_events_service_exception_400(self):
        svc = self._svc()
        svc.get_scheduled_events = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.calendly_routes.CALENDLY_AVAILABLE", True), \
             patch("integrations.calendly_routes.get_calendly_service", return_value=svc, create=True):
            resp = self._client().get("/api/calendly/scheduled-events", params={"access_token": "at"})
        assert resp.status_code == 400

    def test_status_real(self):
        resp, _ = self._call("get", "/api/calendly/status")
        assert resp.status_code == 200
        assert resp.json()["available"] is True

    def test_health_real(self):
        resp, m = self._call("get", "/api/calendly/health")
        assert resp.status_code == 200
        assert resp.json()["healthy"] is True
        m.return_value.health_check.assert_awaited_once()

    def test_import_success_branch(self):
        import integrations.calendly_routes as cr
        import integrations.calendly_service as cs
        assert cr.CALENDLY_AVAILABLE is False
        cs.get_calendly_service = lambda: None
        try:
            importlib.reload(cr)
            assert cr.CALENDLY_AVAILABLE is True
        finally:
            delattr(cs, "get_calendly_service")
            importlib.reload(cr)
        assert cr.CALENDLY_AVAILABLE is False


# ---------------------------------------------------------------------------
# Deepgram routes (integrations/deepgram_routes.py)
# ---------------------------------------------------------------------------

class TestDeepgramRoutesMock:
    """DEEPGRAM_AVAILABLE=False (natural import state — factory commented out)."""

    def _client(self):
        from integrations.deepgram_routes import router
        return make_client(router)

    def test_transcribe_url_mock(self):
        resp = self._client().post("/api/deepgram/transcribe/url",
                                   json={"audio_url": "https://a.example/x.mp3"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "Mock" in body["transcript"]

    def test_transcribe_file_mock(self):
        resp = self._client().post("/api/deepgram/transcribe/file",
                                   files={"file": ("x.wav", b"fake", "audio/wav")})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_transcribe_url_invalid_body_422(self):
        resp = self._client().post("/api/deepgram/transcribe/url", json={"language": "en"})
        assert resp.status_code == 422

    def test_projects_mock(self):
        resp = self._client().get("/api/deepgram/projects")
        assert resp.status_code == 200
        assert resp.json() == {"projects": []}

    def test_usage_mock(self):
        resp = self._client().get("/api/deepgram/usage/p1",
                                  params={"start_date": "2026-01-01", "end_date": "2026-02-01"})
        assert resp.status_code == 200
        assert resp.json() == {"usage": {}}

    def test_status_mock(self):
        resp = self._client().get("/api/deepgram/status")
        assert resp.status_code == 200
        assert resp.json()["available"] is False

    def test_health_delegates_to_status_when_unavailable(self):
        resp = self._client().get("/api/deepgram/health")
        assert resp.status_code == 200
        assert resp.json()["available"] is False


class TestDeepgramRoutesReal:
    """DEEPGRAM_AVAILABLE=True + patched get_deepgram_service."""

    def _client(self):
        from integrations.deepgram_routes import router
        return make_client(router)

    def _svc(self):
        return _async_svc({
            "transcribe_url": {"transcript": "Hello world", "ok": True},
            "transcribe_file": {"transcript": "File hello", "ok": True},
            "get_projects": [{"project_id": "p1"}],
            "get_usage": {"requests": 42},
            "health_check": {"healthy": True, "status": "healthy"},
        })

    def _patch(self, svc=None):
        svc = svc or self._svc()
        cm1 = patch("integrations.deepgram_routes.DEEPGRAM_AVAILABLE", True)
        cm2 = patch("integrations.deepgram_routes.get_deepgram_service",
                    return_value=svc, create=True)
        cm1.start()
        cm2.start()
        return svc

    def _end(self):
        patch.stopall()

    def test_transcribe_url_real(self):
        svc = self._patch()
        try:
            resp = self._client().post("/api/deepgram/transcribe/url",
                                       json={"audio_url": "https://a.example/x.mp3"})
        finally:
            self._end()
        assert resp.status_code == 200
        assert resp.json()["transcript"] == "Hello world"
        svc.transcribe_url.assert_awaited_once_with(
            audio_url="https://a.example/x.mp3", model="nova-2", language="en",
            punctuate=True, diarize=False)

    def test_transcribe_url_real_custom_params(self):
        svc = self._patch()
        try:
            resp = self._client().post("/api/deepgram/transcribe/url",
                                       json={"audio_url": "u", "model": "whisper", "language": "es",
                                             "punctuate": False, "diarize": True})
        finally:
            self._end()
        assert resp.status_code == 200
        svc.transcribe_url.assert_awaited_once_with(
            audio_url="u", model="whisper", language="es", punctuate=False, diarize=True)

    def test_transcribe_url_service_exception_400(self):
        svc = self._svc()
        svc.transcribe_url = AsyncMock(side_effect=RuntimeError("boom"))
        self._patch(svc)
        try:
            resp = self._client().post("/api/deepgram/transcribe/url",
                                       json={"audio_url": "u"})
        finally:
            self._end()
        assert resp.status_code == 400

    def test_transcribe_file_real(self):
        svc = self._patch()
        try:
            resp = self._client().post("/api/deepgram/transcribe/file",
                                       files={"file": ("x.wav", b"audio-bytes", "audio/wav")},
                                       params={"model": "nova-2", "language": "en"})
        finally:
            self._end()
        assert resp.status_code == 200
        assert resp.json()["transcript"] == "File hello"
        svc.transcribe_file.assert_awaited_once_with(
            audio_data=b"audio-bytes", mime_type="audio/wav", model="nova-2",
            language="en", punctuate=True, diarize=False)

    def test_transcribe_file_real_no_content_type(self):
        svc = self._patch()
        try:
            resp = self._client().post("/api/deepgram/transcribe/file",
                                       files={"file": ("x.bin", b"audio-bytes")})
        finally:
            self._end()
        assert resp.status_code == 200
        assert svc.transcribe_file.await_args.kwargs["mime_type"] == "application/octet-stream"

    async def test_transcribe_file_mime_fallback_direct_call(self):
        """UploadFile.content_type is None -> 'audio/wav' fallback."""
        from starlette.datastructures import UploadFile
        import integrations.deepgram_routes as dr

        svc = self._svc()
        fake_file = MagicMock(spec=UploadFile)
        fake_file.read = AsyncMock(return_value=b"audio-bytes")
        fake_file.content_type = None
        with patch.object(dr, "DEEPGRAM_AVAILABLE", True), \
             patch.object(dr, "get_deepgram_service", return_value=svc, create=True):
            result = await dr.transcribe_file(file=fake_file, model="nova-2", language="en")
        assert result["transcript"] == "File hello"
        svc.transcribe_file.assert_awaited_once_with(
            audio_data=b"audio-bytes", mime_type="audio/wav", model="nova-2",
            language="en", punctuate=True, diarize=False)

    def test_transcribe_file_service_exception_400(self):
        svc = self._svc()
        svc.transcribe_file = AsyncMock(side_effect=RuntimeError("boom"))
        self._patch(svc)
        try:
            resp = self._client().post("/api/deepgram/transcribe/file",
                                       files={"file": ("x.wav", b"a", "audio/wav")})
        finally:
            self._end()
        assert resp.status_code == 400

    def test_projects_real(self):
        svc = self._patch()
        try:
            resp = self._client().get("/api/deepgram/projects")
        finally:
            self._end()
        assert resp.status_code == 200
        assert resp.json() == {"projects": [{"project_id": "p1"}]}
        svc.get_projects.assert_awaited_once()

    def test_projects_service_exception_400(self):
        svc = self._svc()
        svc.get_projects = AsyncMock(side_effect=RuntimeError("boom"))
        self._patch(svc)
        try:
            resp = self._client().get("/api/deepgram/projects")
        finally:
            self._end()
        assert resp.status_code == 400

    def test_usage_real(self):
        svc = self._patch()
        try:
            resp = self._client().get("/api/deepgram/usage/p1",
                                      params={"start_date": "2026-01-01", "end_date": "2026-02-01"})
        finally:
            self._end()
        assert resp.status_code == 200
        assert resp.json()["requests"] == 42
        svc.get_usage.assert_awaited_once_with("p1", "2026-01-01", "2026-02-01")

    def test_usage_real_no_dates(self):
        svc = self._patch()
        try:
            resp = self._client().get("/api/deepgram/usage/p1")
        finally:
            self._end()
        assert resp.status_code == 200
        svc.get_usage.assert_awaited_once_with("p1", None, None)

    def test_usage_service_exception_400(self):
        svc = self._svc()
        svc.get_usage = AsyncMock(side_effect=RuntimeError("boom"))
        self._patch(svc)
        try:
            resp = self._client().get("/api/deepgram/usage/p1")
        finally:
            self._end()
        assert resp.status_code == 400

    def test_status_real(self):
        self._patch()
        try:
            resp = self._client().get("/api/deepgram/status")
        finally:
            self._end()
        assert resp.status_code == 200
        assert resp.json()["available"] is True

    def test_health_real(self):
        svc = self._patch()
        try:
            resp = self._client().get("/api/deepgram/health")
        finally:
            self._end()
        assert resp.status_code == 200
        assert resp.json()["healthy"] is True
        svc.health_check.assert_awaited_once()

    def test_import_success_branch(self):
        import integrations.deepgram_routes as dr
        import integrations.deepgram_service as ds
        assert dr.DEEPGRAM_AVAILABLE is False
        ds.get_deepgram_service = lambda: None
        try:
            importlib.reload(dr)
            assert dr.DEEPGRAM_AVAILABLE is True
        finally:
            delattr(ds, "get_deepgram_service")
            importlib.reload(dr)
        assert dr.DEEPGRAM_AVAILABLE is False


# ---------------------------------------------------------------------------
# Twilio routes (integrations/twilio_routes.py)
# ---------------------------------------------------------------------------

class TestTwilioRoutesMock:
    """TWILIO_AVAILABLE=False (natural state — get_twilio_service commented out)."""

    def _client(self):
        from integrations.twilio_routes import router
        return make_client(router)

    def test_auth_url(self):
        resp = self._client().get("/api/twilio/auth/url")
        assert resp.status_code == 200
        body = resp.json()
        assert "twilio.com/console" in body["url"]
        assert "not OAuth" in body["message"]

    def test_send_sms_mock(self):
        resp = self._client().post("/api/twilio/sms/send", json={"to": "+1", "body": "hi"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "SMS sent (mock)"

    def test_send_sms_missing_body_422(self):
        resp = self._client().post("/api/twilio/sms/send", json={"to": "+1"})
        assert resp.status_code == 422

    def test_get_messages_mock(self):
        resp = self._client().get("/api/twilio/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert body["messages"] == []
        assert body["count"] == 0

    def test_make_call_mock(self):
        resp = self._client().post("/api/twilio/calls/make",
                                   json={"to": "+1", "twiml_url": "https://x/twiml"})
        assert resp.status_code == 200
        assert resp.json()["call"] == {"call_sid": "mock"}

    def test_make_call_missing_twiml_422(self):
        resp = self._client().post("/api/twilio/calls/make", json={"to": "+1"})
        assert resp.status_code == 422

    def test_get_calls_mock(self):
        resp = self._client().get("/api/twilio/calls")
        assert resp.status_code == 200
        assert resp.json()["calls"] == []

    def test_get_account_mock(self):
        resp = self._client().get("/api/twilio/account")
        assert resp.status_code == 200
        assert resp.json()["account"] == {"account_sid": "mock"}

    def test_status_mock(self):
        resp = self._client().get("/api/twilio/status")
        assert resp.status_code == 200
        assert resp.json()["capabilities"] == ["sms", "voice", "messaging"]

    def test_health_mock(self):
        resp = self._client().get("/api/twilio/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_messages_page_size_validation_422(self):
        assert self._client().get("/api/twilio/messages", params={"page_size": 0}).status_code == 422
        assert self._client().get("/api/twilio/messages", params={"page_size": 500}).status_code == 422


class TestTwilioRoutesReal:
    """TWILIO_AVAILABLE=True + patched get_twilio_service."""

    def _client(self):
        from integrations.twilio_routes import router
        return make_client(router)

    def _svc(self):
        return _async_svc({
            "send_sms": {"sid": "SM1"},
            "get_messages": [{"sid": "SM1"}],
            "make_call": {"sid": "CA1"},
            "get_calls": [{"sid": "CA1"}],
            "get_account_info": {"account_sid": "AC1"},
            "health_check": {"healthy": True, "status": "healthy"},
        })

    def _call(self, method, path, svc=None, **kw):
        svc = svc or self._svc()
        with patch("integrations.twilio_routes.TWILIO_AVAILABLE", True), \
             patch("integrations.twilio_routes.get_twilio_service",
                   return_value=svc, create=True) as m:
            resp = getattr(self._client(), method)(path, **kw)
            return resp, svc

    def test_send_sms_real(self):
        resp, svc = self._call("post", "/api/twilio/sms/send",
                               json={"to": "+1", "body": "hi", "from_number": "+2"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        svc.send_sms.assert_awaited_once_with("+1", "hi", "+2")

    def test_send_sms_service_exception_500(self):
        svc = self._svc()
        svc.send_sms = AsyncMock(side_effect=RuntimeError("twilio secret 456"))
        resp, _ = self._call("post", "/api/twilio/sms/send", svc,
                             json={"to": "+1", "body": "hi"})
        assert resp.status_code == 500
        assert "secret 456" not in resp.text

    def test_get_messages_real(self):
        resp, svc = self._call("get", "/api/twilio/messages",
                               params={"to": "+1", "from_number": "+2", "page_size": 10})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_messages.assert_awaited_once_with("+1", "+2", 10)

    def test_get_messages_service_exception_500(self):
        svc = self._svc()
        svc.get_messages = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/twilio/messages", svc)
        assert resp.status_code == 500

    def test_make_call_real(self):
        resp, svc = self._call("post", "/api/twilio/calls/make",
                               json={"to": "+1", "twiml_url": "https://x/t", "from_number": "+2"})
        assert resp.status_code == 200
        svc.make_call.assert_awaited_once_with("+1", "https://x/t", "+2")

    def test_make_call_service_exception_500(self):
        svc = self._svc()
        svc.make_call = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("post", "/api/twilio/calls/make", svc,
                             json={"to": "+1", "twiml_url": "https://x/t"})
        assert resp.status_code == 500

    def test_get_calls_real(self):
        resp, svc = self._call("get", "/api/twilio/calls",
                               params={"to": "+1", "from_number": "+2", "page_size": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_calls.assert_awaited_once_with("+1", "+2", 5)

    def test_get_calls_service_exception_500(self):
        svc = self._svc()
        svc.get_calls = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/twilio/calls", svc)
        assert resp.status_code == 500

    def test_get_account_real(self):
        resp, svc = self._call("get", "/api/twilio/account")
        assert resp.status_code == 200
        assert resp.json()["account"]["account_sid"] == "AC1"
        svc.get_account_info.assert_awaited_once()

    def test_get_account_service_exception_500(self):
        svc = self._svc()
        svc.get_account_info = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/twilio/account", svc)
        assert resp.status_code == 500

    def test_status_real(self):
        resp, svc = self._call("get", "/api/twilio/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        svc.__class__  # service constructed

    def test_health_real(self):
        resp, svc = self._call("get", "/api/twilio/health")
        assert resp.status_code == 200
        assert resp.json()["healthy"] is True
        svc.health_check.assert_awaited_once()

    def test_health_service_exception_200_unhealthy(self):
        svc = self._svc()
        svc.health_check = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/twilio/health", svc)
        assert resp.status_code == 200
        assert resp.json()["status"] == "unhealthy"

    def test_import_success_branch(self):
        import integrations.twilio_routes as tr
        import integrations.twilio_service as ts
        assert tr.TWILIO_AVAILABLE is False
        ts.get_twilio_service = lambda: MagicMock()
        try:
            importlib.reload(tr)
            assert tr.TWILIO_AVAILABLE is True
        finally:
            delattr(ts, "get_twilio_service")
            importlib.reload(tr)
        assert tr.TWILIO_AVAILABLE is False


class TestTwilioWebhook:
    def _client(self):
        from integrations.twilio_routes import router
        return make_client(router)

    def test_webhook_success_dispatches_to_bridge(self):
        bridge = MagicMock()
        bridge.process_incoming_message = AsyncMock(return_value={"ok": True})
        with patch("integrations.universal_webhook_bridge.universal_webhook_bridge", bridge):
            resp = self._client().post("/api/twilio/webhook",
                                       data={"MessageSid": "SM1", "From": "+1555", "Body": "hi"})
        assert resp.status_code == 200
        assert "Response" in resp.text
        bridge.process_incoming_message.assert_awaited_once()
        args = bridge.process_incoming_message.await_args.args
        assert args[0] == "twilio"
        assert args[1]["MessageSid"] == "SM1"

    def test_webhook_background_task_registered(self):
        bridge = MagicMock()
        bridge.process_incoming_message = AsyncMock(return_value={})
        with patch("integrations.universal_webhook_bridge.universal_webhook_bridge", bridge):
            resp = self._client().post("/api/twilio/webhook", data={"MessageSid": "SM1"})
        assert resp.status_code == 200

    def test_webhook_error_500(self):
        fake = MagicMock()
        fake.universal_webhook_bridge = MagicMock()
        fake.universal_webhook_bridge.process_incoming_message = MagicMock()
        with patch.dict(sys.modules, {"integrations.universal_webhook_bridge": fake}):
            resp = self._client().post("/api/twilio/webhook", data={"MessageSid": "SM1"})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Intercom routes (integrations/intercom_routes.py)
# ---------------------------------------------------------------------------

class TestIntercomRoutes:
    def _svc(self):
        return _async_svc({
            "exchange_token": {"access_token": "t"},
            "get_contacts": [{"id": "c1"}],
            "get_conversations": [{"id": "cv1"}],
            "get_admins": [{"id": "a1"}],
            "search_contacts": [{"id": "c1"}],
        }, client_id="cid", client_secret="cs",
           health_check=MagicMock(return_value={"healthy": True, "status": "healthy"}))

    def _client(self):
        from integrations.intercom_routes import router
        return make_client(router)

    def _call(self, method, path, svc=None, **kw):
        svc = svc or self._svc()
        with patch("integrations.intercom_routes.get_intercom_service", return_value=svc) as m:
            resp = getattr(self._client(), method)(path, **kw)
            return resp, svc

    def test_auth_url(self):
        resp, svc = self._call("get", "/intercom/auth/url")
        assert resp.status_code == 200
        assert "client_id=cid" in resp.json()["url"]

    def test_auth_url_placeholder_client_id(self):
        svc = self._svc()
        svc.client_id = None
        resp, _ = self._call("get", "/intercom/auth/url", svc)
        assert "client_id=INSERT_CLIENT_ID" in resp.json()["url"]

    def test_auth_callback(self):
        resp, svc = self._call("post", "/intercom/auth/callback", json={"code": "c1"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        svc.exchange_token.assert_awaited_once_with("c1")

    def test_auth_callback_error_400(self):
        svc = self._svc()
        svc.exchange_token = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("post", "/intercom/auth/callback", svc, json={"code": "c1"})
        assert resp.status_code == 400

    def test_get_contacts(self):
        resp, svc = self._call("get", "/intercom/contacts",
                               params={"access_token": "t", "limit": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_contacts.assert_awaited_once_with("t", 5)

    def test_get_contacts_error_500(self):
        svc = self._svc()
        svc.get_contacts = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/intercom/contacts", svc, params={"access_token": "t"})
        assert resp.status_code == 500

    def test_get_conversations(self):
        resp, svc = self._call("get", "/intercom/conversations",
                               params={"access_token": "t", "limit": 7})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_conversations.assert_awaited_once_with("t", 7)

    def test_get_conversations_error_500(self):
        svc = self._svc()
        svc.get_conversations = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/intercom/conversations", svc, params={"access_token": "t"})
        assert resp.status_code == 500

    def test_get_admins(self):
        resp, svc = self._call("get", "/intercom/admins", params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_admins.assert_awaited_once_with("t")

    def test_get_admins_error_500(self):
        svc = self._svc()
        svc.get_admins = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/intercom/admins", svc, params={"access_token": "t"})
        assert resp.status_code == 500

    def test_search(self):
        resp, svc = self._call("post", "/intercom/search",
                               json={"query": "bob", "limit": 3}, params={"access_token": "t"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.search_contacts.assert_awaited_once_with("t", "bob")

    def test_search_error_500(self):
        svc = self._svc()
        svc.search_contacts = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("post", "/intercom/search", svc,
                             json={"query": "bob"}, params={"access_token": "t"})
        assert resp.status_code == 500

    def test_status(self):
        resp, _ = self._call("get", "/intercom/status")
        assert resp.status_code == 200
        assert resp.json()["configured"] is True

    def test_status_unconfigured(self):
        svc = self._svc()
        svc.client_id = None
        svc.client_secret = None
        resp, _ = self._call("get", "/intercom/status", svc)
        assert resp.json()["configured"] is False

    def test_health(self):
        resp, _ = self._call("get", "/intercom/health")
        assert resp.status_code == 200
        assert resp.json()["healthy"] is True

    def test_health_error_no_leak(self):
        svc = self._svc()
        svc.health_check = MagicMock(side_effect=RuntimeError("intercom secret 999"))
        resp, _ = self._call("get", "/intercom/health", svc)
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
        assert "secret 999" not in resp.text

    def test_contacts_missing_token_422(self):
        resp, _ = self._call("get", "/intercom/contacts")
        assert resp.status_code == 422

    def test_contacts_limit_out_of_range_422(self):
        resp, _ = self._call("get", "/intercom/contacts",
                             params={"access_token": "t", "limit": 0})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Linear routes (integrations/linear_routes.py)
# ---------------------------------------------------------------------------

class TestLinearRoutes:
    def _svc(self):
        svc = MagicMock()
        svc.client_id = "lin-client"
        svc.get_authorization_url = MagicMock(
            return_value="https://linear.app/oauth/authorize?client_id=lin-client")
        svc.exchange_token = AsyncMock(return_value={"access_token": "at", "refresh_token": "rt"})
        svc.get_viewer = AsyncMock(return_value={"id": "v1", "name": "Viewer"})
        svc.get_issues = AsyncMock(return_value=[{"id": "i1", "title": "Fix bug", "description": ""}])
        svc.create_issue = AsyncMock(return_value={"id": "i-new", "title": "New"})
        svc.get_teams = AsyncMock(return_value=[{"id": "t1", "name": "Team"}])
        svc.get_projects = AsyncMock(return_value=[{"id": "p1", "name": "Proj"}])
        svc.health_check = AsyncMock(return_value={"ok": True, "healthy": True})
        return svc

    def _client(self):
        from integrations.linear_routes import router
        return make_client(router)

    def _call(self, method, path, svc=None, **kw):
        svc = svc or self._svc()
        with patch("integrations.linear_routes.linear_service", svc):
            resp = getattr(self._client(), method)(path, **kw)
            return resp, svc

    def test_auth_url_default_redirect(self):
        resp, svc = self._call("get", "/api/linear/auth/url")
        assert resp.status_code == 200
        assert "linear.app/oauth" in resp.json()["url"]
        svc.get_authorization_url.assert_called_once_with("http://localhost:8000/api/linear/callback")

    def test_auth_url_custom_redirect(self):
        resp, svc = self._call("get", "/api/linear/auth/url", params={"redirect_uri": "http://cb"})
        assert resp.status_code == 200
        svc.get_authorization_url.assert_called_once_with("http://cb")

    def test_callback(self):
        resp, svc = self._call("get", "/api/linear/callback", params={"code": "c1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["access_token"] == "at"
        svc.exchange_token.assert_awaited_once_with("c1", "http://localhost:8000/api/linear/callback")

    def test_callback_custom_redirect(self):
        resp, svc = self._call("get", "/api/linear/callback",
                               params={"code": "c1", "redirect_uri": "http://cb"})
        assert resp.status_code == 200
        svc.exchange_token.assert_awaited_once_with("c1", "http://cb")

    def test_callback_error_no_str_leak(self):
        svc = self._svc()
        svc.exchange_token = AsyncMock(side_effect=RuntimeError("linear secret 777"))
        resp, _ = self._call("get", "/api/linear/callback", svc, params={"code": "c1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["status"] == "error"
        assert "secret 777" not in resp.text

    def test_viewer(self):
        resp, svc = self._call("get", "/api/linear/viewer", params={"access_token": "at"})
        assert resp.status_code == 200
        assert resp.json()["viewer"]["id"] == "v1"
        svc.get_viewer.assert_awaited_once_with("at")

    def test_viewer_no_token(self):
        resp, svc = self._call("get", "/api/linear/viewer")
        assert resp.status_code == 200
        svc.get_viewer.assert_awaited_once_with(None)

    def test_viewer_error_500(self):
        svc = self._svc()
        svc.get_viewer = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/linear/viewer", svc)
        assert resp.status_code == 500

    def test_get_issues(self):
        resp, svc = self._call("get", "/api/linear/issues",
                               params={"access_token": "at", "first": 25, "team_id": "t1"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_issues.assert_awaited_once_with("at", 25, "t1")

    def test_get_issues_error_500(self):
        svc = self._svc()
        svc.get_issues = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/linear/issues", svc)
        assert resp.status_code == 500

    def test_create_issue(self):
        resp, svc = self._call("post", "/api/linear/issues",
                               json={"title": "Bug", "team_id": "t1", "description": "desc",
                                     "assignee_id": "a1", "priority": 2})
        assert resp.status_code == 200
        assert resp.json()["issue"]["id"] == "i-new"
        svc.create_issue.assert_awaited_once_with(
            title="Bug", team_id="t1", access_token=None,
            description="desc", priority=2, assignee_id="a1")

    def test_create_issue_with_token(self):
        resp, svc = self._call("post", "/api/linear/issues",
                               json={"title": "Bug", "team_id": "t1"},
                               params={"access_token": "at"})
        assert resp.status_code == 200
        svc.create_issue.assert_awaited_once_with(
            title="Bug", team_id="t1", access_token="at",
            description=None, priority=None, assignee_id=None)

    def test_create_issue_missing_fields_422(self):
        resp, _ = self._call("post", "/api/linear/issues", json={"title": "Bug"})
        assert resp.status_code == 422

    def test_create_issue_error_500(self):
        svc = self._svc()
        svc.create_issue = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("post", "/api/linear/issues", svc,
                             json={"title": "Bug", "team_id": "t1"})
        assert resp.status_code == 500

    def test_get_teams(self):
        resp, svc = self._call("get", "/api/linear/teams",
                               params={"access_token": "at", "first": 10})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_teams.assert_awaited_once_with("at", 10)

    def test_get_teams_error_500(self):
        svc = self._svc()
        svc.get_teams = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/linear/teams", svc)
        assert resp.status_code == 500

    def test_get_projects(self):
        resp, svc = self._call("get", "/api/linear/projects",
                               params={"access_token": "at", "first": 10})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        svc.get_projects.assert_awaited_once_with("at", 10)

    def test_get_projects_error_500(self):
        svc = self._svc()
        svc.get_projects = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("get", "/api/linear/projects", svc)
        assert resp.status_code == 500

    def test_search_filters_by_title(self):
        resp, svc = self._call("post", "/api/linear/search",
                               json={"query": "fix"}, params={"access_token": "at"})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 1
        svc.get_issues.assert_awaited_once_with("at", team_id=None)

    def test_search_filters_by_description(self):
        svc = self._svc()
        svc.get_issues = AsyncMock(return_value=[
            {"id": "i1", "title": "Other", "description": "Has MATCH here"},
            {"id": "i2", "title": "Other", "description": "nothing"},
        ])
        resp, _ = self._call("post", "/api/linear/search", svc,
                             json={"query": "match"}, params={"access_token": "at"})
        assert len(resp.json()["results"]) == 1
        assert resp.json()["results"][0]["id"] == "i1"

    def test_search_team_filter(self):
        resp, svc = self._call("post", "/api/linear/search",
                               json={"query": "fix", "team_id": "t1"}, params={"access_token": "at"})
        assert resp.status_code == 200
        svc.get_issues.assert_awaited_once_with("at", team_id="t1")

    def test_search_empty_results(self):
        svc = self._svc()
        svc.get_issues = AsyncMock(return_value=[{"id": "i1", "title": "Other", "description": ""}])
        resp, _ = self._call("post", "/api/linear/search", svc,
                             json={"query": "nomatch"}, params={"access_token": "at"})
        assert resp.json()["results"] == []

    def test_search_service_error_returns_empty(self):
        svc = self._svc()
        svc.get_issues = AsyncMock(side_effect=RuntimeError("boom"))
        resp, _ = self._call("post", "/api/linear/search", svc,
                             json={"query": "x"}, params={"access_token": "at"})
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_search_missing_query_422(self):
        resp, _ = self._call("post", "/api/linear/search", json={})
        assert resp.status_code == 422

    def test_status_connected(self):
        resp, svc = self._call("get", "/api/linear/status", params={"user_id": "u1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "connected"
        assert body["user_id"] == "u1"
        svc.health_check.assert_awaited_once()

    def test_status_default_user(self):
        resp, _ = self._call("get", "/api/linear/status")
        assert resp.json()["user_id"] == "test_user"

    def test_status_health_false(self):
        svc = self._svc()
        svc.health_check = AsyncMock(return_value={"ok": False})
        resp, _ = self._call("get", "/api/linear/status", svc)
        assert resp.json()["ok"] is False

    def test_status_not_configured(self):
        svc = self._svc()
        svc.client_id = None
        resp, _ = self._call("get", "/api/linear/status", svc)
        assert resp.json()["status"] == "not_configured"

    def test_health_healthy(self):
        resp, _ = self._call("get", "/api/linear/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
        assert resp.json()["configured"] is True

    def test_health_unhealthy(self):
        svc = self._svc()
        svc.health_check = AsyncMock(return_value={"ok": False})
        resp, _ = self._call("get", "/api/linear/health", svc)
        assert resp.json()["status"] == "unhealthy"

    def test_health_not_configured(self):
        svc = self._svc()
        svc.client_id = None
        resp, _ = self._call("get", "/api/linear/health", svc)
        assert resp.json()["configured"] is False


# ---------------------------------------------------------------------------
# Regression: unmountable routers fixed
# ---------------------------------------------------------------------------

class TestRouterMountRegression:
    def test_linear_singleton_created(self):
        import integrations.linear_routes as lr
        assert lr.linear_service is not None
        from integrations.linear_service import LinearService
        assert isinstance(lr.linear_service, LinearService)

    def test_linear_router_mounts(self):
        from integrations.linear_routes import router
        paths = {r.path for r in router.routes}
        assert "/api/linear/issues" in paths
        assert "/api/linear/health" in paths

    def test_twilio_router_mounts(self):
        from integrations.twilio_routes import router
        paths = {r.path for r in router.routes}
        assert "/api/twilio/sms/send" in paths
        assert "/api/twilio/webhook" in paths

    def test_load_integration_linear(self):
        from core.lazy_integration_registry import load_integration, clear_integration_cache
        clear_integration_cache()
        router = load_integration("linear")
        assert router is not None
        assert any(r.path == "/api/linear/issues" for r in router.routes)

    def test_load_integration_twilio(self):
        from core.lazy_integration_registry import load_integration, clear_integration_cache
        clear_integration_cache()
        router = load_integration("twilio")
        assert router is not None
        assert any(r.path == "/api/twilio/sms/send" for r in router.routes)

    def test_twilio_bg_tasks_defined_in_module_scope(self):
        import integrations.twilio_routes as tr
        assert hasattr(tr, "_bg_tasks")
        assert isinstance(tr._bg_tasks, set)
