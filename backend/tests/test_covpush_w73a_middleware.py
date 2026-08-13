"""Coverage wave 73a — middleware/audit_middleware, domain_routing_middleware,
error_handling, performance → >=95% each.

Standalone file (final probe runs only this file), so every branch of the 4
target modules is exercised here:

- ``middleware.audit_middleware``: request timing + X-Process-Time header,
  tenant_id from request.state, Bearer-token user resolution (primary
  ``get_current_user_optional`` path, natural ImportError fallback to
  ``get_current_user``, user-found/None/raises variants, blocked-import
  variant, generic exception variants), health-path early return, Prometheus
  track_http_request (called + raises), audit logger (called + raises),
  re-raise of downstream exceptions, client None.
- ``middleware.domain_routing_middleware``: exempt system paths, local/dev
  host skip list (localhost/.localhost/127.0.0.1/testserver/.fly.dev/
  .ngrok-free.app), port stripping, custom-domain lookup (hit/miss/raises),
  subdomain lookup (hit/miss/raises), www/api subdomain skip, 'raj' dev
  fallback (dev + production), 404 JSONResponse for unknown subdomains,
  tenant branding state, db.close() in finally.
- ``middleware.error_handling``: ErrorHandlingMiddleware init + setup_logging,
  dispatch success (request_id state + X-Request-ID header), HTTPException
  handler (debug on/off), server-error handler (debug on/off), fast/slow
  performance logging, ValidationErrorMiddleware (passthrough, validation
  match, pydantic match, non-validation re-raise, field-required parse,
  parse-failure tolerance), CircuitBreakerMiddleware (init, open-circuit 503,
  success reset, failure accumulation, threshold critical log, timeout
  expiry), setup_error_middleware wiring.
- ``middleware.performance``: LocalCacheFallback (miss/hit/expiry/LRU
  eviction/move_to_end/delete/clear/stats), SimpleCache (get/set/delete/
  expiry/cleanup interval), CacheMiddleware (non-GET passthrough, no-cache
  pattern passthrough, HIT/MISS/SKIP, cache key generation), Compression
  middleware (accept-encoding gate, min-size gate, content-type gate, gzip
  header), DatabaseConnectionPool (lazy httpx init, get/release/close,
  async context manager), RequestMetricsMiddleware (counters, header,
  get_metrics), setup_performance_middleware, cached decorator.

No LLM spend, no network, no real DB, no filesystem writes — every dependency
is mocked (SimpleNamespace rows, MagicMock sessions, patched loggers, patched
FileHandler, fake httpx module, in-memory fake caches).
"""
import datetime
import logging
import os
import sys
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from middleware import audit_middleware as audmod
from middleware import domain_routing_middleware as drmod
from middleware import error_handling as ehmod
from middleware import performance as perfmod


# ============================================================================
# Shared fixtures
# ============================================================================

def make_audit_request(path="/api/v1/agents", method="GET", auth=None,
                       client_host="127.0.0.1", tenant_id=None):
    req = MagicMock(spec=Request)
    req.method = method
    req.url.path = path
    req.headers = {"Authorization": auth} if auth else {}
    req.client = SimpleNamespace(host=client_host) if client_host is not None else None
    req.state = SimpleNamespace(tenant_id=tenant_id) if tenant_id is not None else SimpleNamespace()
    return req


def make_response(status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {}
    return resp


def make_domain_request(path="/dashboard", host="acme.example.com"):
    req = MagicMock(spec=Request)
    req.url.path = path
    req.headers = {"host": host}
    req.scope = {}
    req.state = SimpleNamespace()
    return req


def make_error_request(path="/api/v1/items", method="POST"):
    req = MagicMock(spec=Request)
    req.method = method
    req.url.path = path
    req.url.query = ""
    req.state = SimpleNamespace()
    req.headers = {"user-agent": "test"}
    req.query_params = {"a": "b"}
    return req


@pytest.fixture
def error_mw(monkeypatch):
    monkeypatch.setattr(
        logging, "FileHandler", lambda *a, **k: MagicMock()
    )
    return ehmod.ErrorHandlingMiddleware(app=MagicMock(), debug=False)


@pytest.fixture
def error_mw_debug(monkeypatch):
    monkeypatch.setattr(
        logging, "FileHandler", lambda *a, **k: MagicMock()
    )
    return ehmod.ErrorHandlingMiddleware(app=MagicMock(), debug=True)


# ============================================================================
# middleware/audit_middleware.py
# ============================================================================

class TestAuditMiddlewareTiming:
    async def test_process_time_header_and_audit_log(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request()
        resp = make_response()

        async def call_next(request):
            return resp

        with patch.object(audmod, "SessionLocal") as mock_sl:
            with patch.object(audmod, "track_http_request") as mock_track:
                with patch.object(audmod, "logger") as mock_logger:
                    out = await mw.dispatch(req, call_next)

        assert out is resp
        assert "X-Process-Time" in resp.headers
        float(resp.headers["X-Process-Time"]) >= 0
        mock_sl.assert_not_called()
        mock_track.assert_called_once()
        kwargs = mock_track.call_args.kwargs
        assert kwargs["method"] == "GET"
        assert kwargs["endpoint"] == "/api/v1/agents"
        assert kwargs["status"] == 200
        log_kwargs = mock_logger.info.call_args.kwargs
        assert log_kwargs["method"] == "GET"
        assert log_kwargs["path"] == "/api/v1/agents"
        assert log_kwargs["status_code"] == 200
        assert log_kwargs["user_id"] is None
        assert log_kwargs["tenant_id"] == "global"
        assert log_kwargs["client_ip"] == "127.0.0.1"

    async def test_client_none_and_tenant_from_state(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(client_host=None, tenant_id="tenant-77")
        resp = make_response()

        async def call_next(request):
            return resp

        with patch.object(audmod, "logger") as mock_logger:
            await mw.dispatch(req, call_next)
        log_kwargs = mock_logger.info.call_args.kwargs
        assert log_kwargs["client_ip"] is None
        assert log_kwargs["tenant_id"] == "tenant-77"

    async def test_health_paths_skip_metrics_and_header(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        for path in ["/", "/health", "/api/health", "/api/health/metrics"]:
            req = make_audit_request(path=path)
            resp = make_response()

            async def call_next(request):
                return resp

            with patch.object(audmod, "track_http_request") as mock_track:
                with patch.object(audmod, "logger") as mock_logger:
                    out = await mw.dispatch(req, call_next)
            assert out is resp
            mock_track.assert_not_called()
            mock_logger.info.assert_not_called()
            assert "X-Process-Time" not in resp.headers

    async def test_track_http_request_raises_is_tolerated(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request()

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "track_http_request", side_effect=RuntimeError("metrics down")):
            with patch.object(audmod, "logger"):
                out = await mw.dispatch(req, call_next)
        assert "X-Process-Time" in out.headers

    async def test_audit_logger_raises_is_tolerated(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request()

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "logger") as mock_logger:
            mock_logger.info.side_effect = RuntimeError("log down")
            out = await mw.dispatch(req, call_next)
        assert "X-Process-Time" in out.headers

    async def test_downstream_exception_is_re_raised(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request()

        async def call_next(request):
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await mw.dispatch(req, call_next)


class TestAuditMiddlewareUserResolution:
    async def test_primary_optional_resolves_user(self, monkeypatch):
        import core.auth
        fake = AsyncMock(return_value=SimpleNamespace(id="u-42"))
        monkeypatch.setattr(core.auth, "get_current_user_optional", fake, raising=False)
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-1")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__.return_value = MagicMock()
            with patch.object(audmod, "logger") as mock_logger:
                await mw.dispatch(req, call_next)
        fake.assert_awaited_once_with("token-1", mock_sl.return_value.__enter__.return_value)
        assert mock_logger.info.call_args.kwargs["user_id"] == "u-42"

    async def test_primary_optional_returns_none(self, monkeypatch):
        import core.auth
        fake = AsyncMock(return_value=None)
        monkeypatch.setattr(core.auth, "get_current_user_optional", fake, raising=False)
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-1")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "SessionLocal"):
            with patch.object(audmod, "logger") as mock_logger:
                await mw.dispatch(req, call_next)
        assert mock_logger.info.call_args.kwargs["user_id"] is None

    async def test_primary_optional_raises_generic(self, monkeypatch):
        import core.auth
        fake = AsyncMock(side_effect=RuntimeError("db down"))
        monkeypatch.setattr(core.auth, "get_current_user_optional", fake, raising=False)
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-1")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "SessionLocal"):
            with patch.object(audmod, "logger") as mock_logger:
                out = await mw.dispatch(req, call_next)
        assert out.headers["X-Process-Time"]
        assert mock_logger.info.call_args.kwargs["user_id"] is None

    async def test_natural_import_error_falls_back_to_get_current_user(self, monkeypatch):
        import core.auth
        assert not hasattr(core.auth, "get_current_user_optional")
        fake = AsyncMock(return_value=SimpleNamespace(id="u-fallback"))
        monkeypatch.setattr(core.auth, "get_current_user", fake)
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-2")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__.return_value = mock_db
            with patch.object(audmod, "logger") as mock_logger:
                await mw.dispatch(req, call_next)
        fake.assert_awaited_once_with(req, "token-2", mock_db)
        assert mock_logger.info.call_args.kwargs["user_id"] == "u-fallback"

    async def test_fallback_get_current_user_receives_request_first(self, monkeypatch):
        """Regression: fallback must call get_current_user(request, token, db) —
        the real signature is (request, token, db), so passing only (token, db)
        always raised TypeError and user_id was never resolved via the fallback.
        """
        import core.auth
        fake = AsyncMock(return_value=SimpleNamespace(id="u-fallback"))
        monkeypatch.setattr(core.auth, "get_current_user", fake)
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-2")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__.return_value = mock_db
            with patch.object(audmod, "logger"):
                await mw.dispatch(req, call_next)
        fake.assert_awaited_once()
        first_arg = fake.await_args.args[0]
        assert first_arg is req
        assert fake.await_args.args[1:] == ("token-2", mock_db)

    async def test_fallback_returns_none(self, monkeypatch):
        import core.auth
        fake = AsyncMock(return_value=None)
        monkeypatch.setattr(core.auth, "get_current_user", fake)
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-3")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "SessionLocal"):
            with patch.object(audmod, "logger") as mock_logger:
                await mw.dispatch(req, call_next)
        assert mock_logger.info.call_args.kwargs["user_id"] is None

    async def test_fallback_raises_is_swallowed(self, monkeypatch):
        import core.auth
        fake = AsyncMock(side_effect=RuntimeError("strict user lookup failed"))
        monkeypatch.setattr(core.auth, "get_current_user", fake)
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-4")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "SessionLocal"):
            with patch.object(audmod, "logger") as mock_logger:
                out = await mw.dispatch(req, call_next)
        assert "X-Process-Time" in out.headers
        assert mock_logger.info.call_args.kwargs["user_id"] is None

    async def test_both_imports_blocked_is_swallowed(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-5")

        async def call_next(request):
            return make_response()

        with patch.dict(sys.modules, {"core.auth": None}):
            with patch.object(audmod, "SessionLocal"):
                with patch.object(audmod, "logger") as mock_logger:
                    out = await mw.dispatch(req, call_next)
        assert "X-Process-Time" in out.headers
        assert mock_logger.info.call_args.kwargs["user_id"] is None

    async def test_header_access_raises_is_swallowed(self):
        mw = audmod.AuditMiddleware(app=MagicMock())
        req = make_audit_request(auth="Bearer token-6")
        req.headers = MagicMock()
        req.headers.get.side_effect = RuntimeError("header read failed")

        async def call_next(request):
            return make_response()

        with patch.object(audmod, "logger") as mock_logger:
            out = await mw.dispatch(req, call_next)
        assert "X-Process-Time" in out.headers
        assert mock_logger.info.call_args.kwargs["user_id"] is None


# ============================================================================
# middleware/domain_routing_middleware.py
# ============================================================================

class TestDomainRoutingExemptPaths:
    @pytest.mark.parametrize(
        "path",
        ["/", "/health", "/alive", "/api/health",
         "/api/v1/openapi.json", "/api/v1/docs", "/api/v1/redoc"],
    )
    async def test_exempt_path_passthrough(self, path):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(path=path, host="customer.example.com")
        resp = make_response()
        calls = []

        async def call_next(request):
            calls.append(request)
            return resp

        with patch.object(drmod, "SessionLocal") as mock_sl:
            out = await mw.dispatch(req, call_next)
        assert out is resp
        assert len(calls) == 1
        mock_sl.assert_not_called()


class TestDomainRoutingLocalHosts:
    @pytest.mark.parametrize(
        "host",
        ["localhost", "app.localhost", "127.0.0.1", "testserver",
         "myapp.fly.dev", "tunnel.ngrok-free.app"],
    )
    async def test_local_host_skips_routing(self, host):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host=host)
        resp = make_response()
        calls = []

        async def call_next(request):
            calls.append(request)
            return resp

        with patch.object(drmod, "SessionLocal") as mock_sl:
            out = await mw.dispatch(req, call_next)
        assert out is resp
        assert req.state.tenant_id is None
        assert len(calls) == 1
        mock_sl.assert_not_called()


class TestDomainRoutingTenantLookup:
    def _mock_db(self, custom=None, sub=None, raise_custom=False, raise_sub=False):
        mock_db = MagicMock()
        first_chain = mock_db.query.return_value.filter.return_value.first
        first_chain.side_effect = [
            RuntimeError("custom domain query failed") if raise_custom else custom,
            RuntimeError("subdomain query failed") if raise_sub else sub,
        ]
        return mock_db

    def _tenant(self, with_branding=True):
        if with_branding:
            return SimpleNamespace(
                id="t-1", name="Acme", logo_url="http://logo", primary_color="#fff"
            )
        return SimpleNamespace(id="t-2", name="Plain")

    async def test_custom_domain_hit_sets_state(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="acme.example.com")
        resp = make_response()
        mock_db = self._mock_db(custom=self._tenant())

        async def call_next(request):
            return resp

        with patch.object(drmod, "SessionLocal", return_value=mock_db) as mock_sl:
            with patch.object(drmod.logger, "debug") as mock_debug:
                out = await mw.dispatch(req, call_next)
        assert out is resp
        assert req.scope["db"] is mock_db
        assert req.state.tenant_id == "t-1"
        assert req.state.tenant_name == "Acme"
        assert req.state.branding == {"logo_url": "http://logo", "primary_color": "#fff"}
        mock_debug.assert_called_once()
        mock_db.close.assert_called_once()

    async def test_custom_domain_hit_without_branding_columns(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="plain.example.com")
        resp = make_response()
        mock_db = self._mock_db(custom=self._tenant(with_branding=False))

        async def call_next(request):
            return resp

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            await mw.dispatch(req, call_next)
        assert req.state.branding == {"logo_url": None, "primary_color": None}

    async def test_subdomain_hit_after_custom_domain_miss(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="support.example.com")
        resp = make_response()
        mock_db = self._mock_db(custom=None, sub=self._tenant())

        async def call_next(request):
            return resp

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert out is resp
        assert req.state.tenant_id == "t-1"
        assert req.state.tenant_name == "Acme"
        mock_db.close.assert_called_once()

    async def test_www_and_api_subdomains_skipped(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        for host in ["www.example.com", "api.example.com"]:
            req = make_domain_request(host=host)
            resp = make_response()
            mock_db = self._mock_db(custom=None, sub=None)

            async def call_next(request):
                return resp

            with patch.object(drmod, "SessionLocal", return_value=mock_db):
                out = await mw.dispatch(req, call_next)
            assert out is resp
            assert req.state.tenant_id is None

    async def test_unknown_subdomain_returns_404(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="ghost.example.com")
        mock_db = self._mock_db(custom=None, sub=None)

        async def call_next(request):
            raise AssertionError("call_next must not run for 404")

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert isinstance(out, JSONResponse)
        assert out.status_code == 404
        assert "ghost" in out.body.decode()
        mock_db.close.assert_called_once()

    async def test_missing_host_header_404s(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request()
        req.headers = {}
        mock_db = self._mock_db(custom=None, sub=None)

        async def call_next(request):
            raise AssertionError("call_next must not run for 404")

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert out.status_code == 404

    async def test_port_is_stripped_from_host(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="acme.example.com:8080")
        resp = make_response()
        mock_db = MagicMock()
        captured = {}

        real_filter = mock_db.query.return_value.filter

        def _capture(*args, **kwargs):
            captured["host"] = args[0].right.value
            return real_filter

        real_filter.side_effect = _capture
        real_filter.first.return_value = self._tenant()

        async def call_next(request):
            return resp

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert out is resp
        assert captured["host"] == "acme.example.com"
        assert req.state.tenant_id == "t-1"

    async def test_custom_domain_query_raises_then_subdomain_hit(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="sales.example.com")
        resp = make_response()
        mock_db = self._mock_db(raise_custom=True, sub=self._tenant())

        async def call_next(request):
            return resp

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert out is resp
        mock_db.rollback.assert_called_once()
        assert req.state.tenant_id == "t-1"

    async def test_subdomain_query_raises_then_404(self):
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="missing.example.com")
        mock_db = self._mock_db(custom=None, raise_sub=True)

        async def call_next(request):
            raise AssertionError("call_next must not run")

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert out.status_code == 404
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()


class TestDomainRoutingRajFallback:
    async def test_raj_dev_fallback_sets_state(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="raj.example.com")
        resp = make_response()
        mock_db = self._db_no_tenant()
        calls = []

        async def call_next(request):
            calls.append(request)
            return resp

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert out is resp
        assert req.state.tenant_id == "raj-test-tenant-id"
        assert req.state.tenant_name == "Raj Test Tenant"
        assert len(calls) == 1
        mock_db.close.assert_called_once()

    async def test_raj_environment_unset_is_not_production(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="raj.example.com")
        resp = make_response()
        mock_db = self._db_no_tenant()

        async def call_next(request):
            return resp

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert req.state.tenant_id == "raj-test-tenant-id"

    async def test_raj_production_returns_404(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        mw = drmod.DomainRoutingMiddleware(app=MagicMock())
        req = make_domain_request(host="raj.example.com")
        mock_db = self._db_no_tenant()

        async def call_next(request):
            raise AssertionError("call_next must not run")

        with patch.object(drmod, "SessionLocal", return_value=mock_db):
            out = await mw.dispatch(req, call_next)
        assert out.status_code == 404
        assert "raj" in out.body.decode()
        mock_db.close.assert_called_once()

    def _db_no_tenant(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        return mock_db


# ============================================================================
# middleware/error_handling.py — ErrorHandlingMiddleware
# ============================================================================

class TestErrorHandlingMiddlewareInit:
    def test_init_and_setup_logging(self, monkeypatch):
        handlers = []
        monkeypatch.setattr(
            logging, "FileHandler",
            lambda *a, **k: handlers.append(a) or MagicMock(),
        )
        mw = ehmod.ErrorHandlingMiddleware(app=MagicMock(), debug=False)
        assert mw.debug is False
        assert handlers == [("logs/errors.log",), ("logs/performance.log",)]

    def test_init_debug_true(self, monkeypatch):
        monkeypatch.setattr(logging, "FileHandler", lambda *a, **k: MagicMock())
        mw = ehmod.ErrorHandlingMiddleware(app=MagicMock(), debug=True)
        assert mw.debug is True

    def test_init_default_debug_false(self, monkeypatch):
        monkeypatch.setattr(logging, "FileHandler", lambda *a, **k: MagicMock())
        mw = ehmod.ErrorHandlingMiddleware(app=MagicMock())
        assert mw.debug is False


class TestErrorHandlingMiddlewareDispatch:
    async def test_successful_request(self, error_mw, monkeypatch):
        req = make_error_request()
        resp = make_response()
        calls = []

        async def call_next(request):
            calls.append(request)
            return resp

        with patch.object(ehmod, "performance_logger") as mock_perf:
            out = await error_mw.dispatch(req, call_next)
        assert out is resp
        assert len(calls) == 1
        assert req.state.request_id is not None
        uuid.UUID(req.state.request_id)
        assert resp.headers["X-Request-ID"] == req.state.request_id
        mock_perf.info.assert_called_once()
        mock_perf.warning.assert_not_called()

    async def test_http_exception_handled(self, error_mw):
        req = make_error_request()

        async def call_next(request):
            raise HTTPException(status_code=404, detail="Not found")

        with patch.object(ehmod, "error_logger") as mock_err_log:
            out = await error_mw.dispatch(req, call_next)
        assert isinstance(out, JSONResponse)
        assert out.status_code == 404
        body = out.body.decode()
        assert '"type":"http_error"' in body
        assert '"code":404' in body
        assert '"message":"Not found"' in body
        assert '"path":"/api/v1/items"' in body
        assert '"method":"POST"' in body
        mock_err_log.warning.assert_called_once()

    async def test_http_exception_debug_info(self, error_mw_debug):
        req = make_error_request()

        async def call_next(request):
            raise HTTPException(status_code=400, detail="Bad")

        with patch.object(ehmod, "error_logger"):
            out = await error_mw_debug.dispatch(req, call_next)
        assert out.status_code == 400
        body = out.body.decode()
        assert '"debug"' in body
        assert '"query_params"' in body

    async def test_server_error_handled(self, error_mw):
        req = make_error_request()

        async def call_next(request):
            raise ValueError("boom")

        with patch.object(ehmod, "error_logger") as mock_err_log:
            out = await error_mw.dispatch(req, call_next)
        assert isinstance(out, JSONResponse)
        assert out.status_code == 500
        body = out.body.decode()
        assert '"type":"server_error"' in body
        assert '"code":500' in body
        assert '"message":"Internal server error occurred"' in body
        assert '"debug"' not in body
        mock_err_log.error.assert_called_once()

    async def test_server_error_debug_info(self, error_mw_debug):
        req = make_error_request()

        async def call_next(request):
            raise ValueError("secret detail")

        with patch.object(ehmod, "error_logger"):
            out = await error_mw_debug.dispatch(req, call_next)
        assert out.status_code == 500
        body = out.body.decode()
        assert '"debug"' in body
        assert "secret detail" in body
        assert "Traceback" in body


class TestErrorHandlingLogPerformance:
    def test_slow_request_warns(self, error_mw):
        req = make_error_request()
        resp = make_response()
        with patch.object(ehmod, "performance_logger") as mock_perf:
            error_mw.log_performance(req, resp, 2.5, "rid-1")
        mock_perf.warning.assert_called_once()
        mock_perf.info.assert_not_called()

    def test_fast_request_logs_info(self, error_mw):
        req = make_error_request()
        resp = make_response()
        with patch.object(ehmod, "performance_logger") as mock_perf:
            error_mw.log_performance(req, resp, 1.0, "rid-1")
        mock_perf.info.assert_called_once()
        mock_perf.warning.assert_not_called()

    def test_exactly_two_seconds_is_fast(self, error_mw):
        req = make_error_request()
        resp = make_response()
        with patch.object(ehmod, "performance_logger") as mock_perf:
            error_mw.log_performance(req, resp, 2.0, "rid-1")
        mock_perf.info.assert_called_once()


# ============================================================================
# middleware/error_handling.py — ValidationErrorMiddleware
# ============================================================================

class TestValidationErrorMiddleware:
    async def test_success_passthrough(self):
        mw = ehmod.ValidationErrorMiddleware(app=MagicMock())
        req = make_error_request()
        resp = make_response()
        calls = []

        async def call_next(request):
            calls.append(request)
            return resp

        out = await mw.dispatch(req, call_next)
        assert out is resp
        assert len(calls) == 1

    async def test_validation_message_returns_422(self):
        mw = ehmod.ValidationErrorMiddleware(app=MagicMock())
        req = make_error_request()

        async def call_next(request):
            raise ValueError("Validation error: field required")

        out = await mw.dispatch(req, call_next)
        assert isinstance(out, JSONResponse)
        assert out.status_code == 422
        body = out.body.decode()
        assert '"type":"validation_error"' in body
        assert '"code":422' in body
        assert '"path":"/api/v1/items"' in body

    async def test_pydantic_message_returns_422(self):
        mw = ehmod.ValidationErrorMiddleware(app=MagicMock())
        req = make_error_request()

        async def call_next(request):
            raise ValueError("pydantic.ValidationError: bad field")

        out = await mw.dispatch(req, call_next)
        assert out.status_code == 422

    async def test_unrelated_exception_re_raised(self):
        mw = ehmod.ValidationErrorMiddleware(app=MagicMock())
        req = make_error_request()

        async def call_next(request):
            raise ValueError("something else entirely")

        with pytest.raises(ValueError, match="something else"):
            await mw.dispatch(req, call_next)

    async def test_field_required_parsed(self):
        mw = ehmod.ValidationErrorMiddleware(app=MagicMock())
        req = make_error_request()

        async def call_next(request):
            raise ValueError("Validation error: field required")

        out = await mw.dispatch(req, call_next)
        body = out.body.decode()
        assert "Required field is missing" in body
        assert '"type":"missing"' in body

    async def test_parse_failure_tolerated(self):
        mw = ehmod.ValidationErrorMiddleware(app=MagicMock())
        req = make_error_request()

        class WeirdError(Exception):
            def __str__(self):
                raise RuntimeError("cannot stringify")

        with patch.object(ehmod, "error_logger") as mock_err_log:
            out = mw.handle_validation_error(WeirdError("x"), req)
        assert isinstance(out, JSONResponse)
        assert out.status_code == 422
        assert '"validation_errors":[]' in out.body.decode()
        mock_err_log.warning.assert_called_once()


# ============================================================================
# middleware/error_handling.py — CircuitBreakerMiddleware
# ============================================================================

class TestCircuitBreakerMiddleware:
    def test_init_attributes(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=3, timeout=60)
        assert mw.failure_threshold == 3
        assert mw.timeout == 60
        assert mw.failure_count == {}
        assert mw.last_failure_time == {}

    def test_init_defaults(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock())
        assert mw.failure_threshold == 5
        assert mw.timeout == 60

    async def test_successful_request_passthrough(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5)
        req = make_error_request()
        resp = make_response()

        async def call_next(request):
            return resp

        out = await mw.dispatch(req, call_next)
        assert out is resp

    async def test_success_clears_prior_failure_records(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5)
        req = make_error_request()
        endpoint = f"{req.method}_{req.url.path}"
        mw.failure_count[endpoint] = 4
        mw.last_failure_time[endpoint] = datetime.datetime.now()

        async def call_next(request):
            return make_response()

        out = await mw.dispatch(req, call_next)
        assert endpoint not in mw.failure_count
        assert endpoint not in mw.last_failure_time
        assert out is not None

    async def test_failure_below_threshold_re_raises(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5)
        req = make_error_request()

        async def call_next(request):
            raise ValueError("upstream failed")

        with patch.object(ehmod, "error_logger") as mock_err_log:
            with pytest.raises(ValueError, match="upstream failed"):
                await mw.dispatch(req, call_next)
        endpoint = f"{req.method}_{req.url.path}"
        assert mw.failure_count[endpoint] == 1
        assert endpoint in mw.last_failure_time
        mock_err_log.critical.assert_not_called()

    async def test_failure_at_threshold_logs_critical(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5)
        req = make_error_request()
        endpoint = f"{req.method}_{req.url.path}"
        mw.failure_count[endpoint] = 4
        mw.last_failure_time[endpoint] = datetime.datetime.now()

        async def call_next(request):
            raise RuntimeError("upstream failed")

        with patch.object(ehmod, "error_logger") as mock_err_log:
            with pytest.raises(RuntimeError):
                await mw.dispatch(req, call_next)
        assert mw.failure_count[endpoint] == 5
        mock_err_log.critical.assert_called_once()

    async def test_open_circuit_returns_503(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5, timeout=60)
        req = make_error_request()
        endpoint = f"{req.method}_{req.url.path}"
        mw.failure_count[endpoint] = 5
        mw.last_failure_time[endpoint] = datetime.datetime.now()

        async def call_next(request):
            raise AssertionError("call_next must not run when circuit is open")

        out = await mw.dispatch(req, call_next)
        assert isinstance(out, JSONResponse)
        assert out.status_code == 503
        assert '"retry_after":60' in out.body.decode()

    async def test_open_circuit_expired_allows_request(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5, timeout=60)
        req = make_error_request()
        endpoint = f"{req.method}_{req.url.path}"
        mw.failure_count[endpoint] = 5
        mw.last_failure_time[endpoint] = datetime.datetime.now() - datetime.timedelta(seconds=120)
        resp = make_response()

        async def call_next(request):
            return resp

        out = await mw.dispatch(req, call_next)
        assert out is resp

    def test_is_circuit_open_below_threshold(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5)
        assert mw.is_circuit_open("GET_/api/x") is False
        mw.failure_count["GET_/api/x"] = 3
        assert mw.is_circuit_open("GET_/api/x") is False

    def test_is_circuit_open_at_threshold_without_time(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5)
        mw.failure_count["GET_/api/x"] = 5
        assert mw.is_circuit_open("GET_/api/x") is False

    def test_is_circuit_open_at_threshold_within_timeout(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5, timeout=60)
        mw.failure_count["GET_/api/x"] = 5
        mw.last_failure_time["GET_/api/x"] = datetime.datetime.now()
        assert mw.is_circuit_open("GET_/api/x") is True

    def test_is_circuit_open_past_timeout(self):
        mw = ehmod.CircuitBreakerMiddleware(app=MagicMock(), failure_threshold=5, timeout=60)
        mw.failure_count["GET_/api/x"] = 5
        mw.last_failure_time["GET_/api/x"] = datetime.datetime.now() - datetime.timedelta(seconds=61)
        assert mw.is_circuit_open("GET_/api/x") is False


# ============================================================================
# middleware/error_handling.py — setup_error_middleware
# ============================================================================

class TestSetupErrorMiddleware:
    def test_adds_middleware_in_order(self, monkeypatch):
        monkeypatch.setattr(logging, "FileHandler", lambda *a, **k: MagicMock())
        added = []
        app = MagicMock()
        app.add_middleware = lambda cls, **kw: added.append((cls, kw))
        monkeypatch.setattr(os, "makedirs", lambda *a, **k: None)
        ehmod.setup_error_middleware(app, debug=True)
        assert [c for c, _ in added] == [
            ehmod.ValidationErrorMiddleware,
            ehmod.CircuitBreakerMiddleware,
            ehmod.ErrorHandlingMiddleware,
        ]
        assert added[2][1] == {"debug": True}

    def test_creates_logs_directory(self, monkeypatch):
        monkeypatch.setattr(logging, "FileHandler", lambda *a, **k: MagicMock())
        app = MagicMock()
        makedirs_calls = []
        monkeypatch.setattr(os, "makedirs", lambda *a, **k: makedirs_calls.append((a, k)))
        ehmod.setup_error_middleware(app)
        assert makedirs_calls == [(("logs",), {"exist_ok": True})]


# ============================================================================
# middleware/performance.py — LocalCacheFallback
# ============================================================================

class TestLocalCacheFallback:
    async def test_miss_increments_misses(self):
        c = perfmod.LocalCacheFallback(max_size=10)
        assert await c.get("nope") is None
        assert c.misses == 1
        assert c.hits == 0

    async def test_set_and_get_hit(self):
        c = perfmod.LocalCacheFallback()
        assert await c.set("k", {"v": 1}) is True
        assert await c.get("k") == {"v": 1}
        assert c.hits == 1

    async def test_get_expired_entry_removed(self):
        c = perfmod.LocalCacheFallback()
        c._cache["k"] = {"value": "old", "expires_at": time.time() - 10}
        assert await c.get("k") is None
        assert c.misses == 1
        assert "k" not in c._cache

    async def test_get_moves_entry_to_end_lru(self):
        c = perfmod.LocalCacheFallback(max_size=2)
        await c.set("a", 1)
        await c.set("b", 2)
        await c.get("a")  # a becomes MRU
        await c.set("c", 3)  # evicts b (oldest)
        assert c.evictions == 1
        assert "a" in c._cache
        assert "b" not in c._cache
        assert "c" in c._cache

    async def test_set_evicts_oldest_at_capacity(self):
        c = perfmod.LocalCacheFallback(max_size=2)
        await c.set("a", 1)
        await c.set("b", 2)
        await c.set("c", 3)
        assert c.evictions == 1
        assert "a" not in c._cache
        assert "b" in c._cache and "c" in c._cache

    async def test_set_existing_key_no_eviction(self):
        c = perfmod.LocalCacheFallback(max_size=1)
        await c.set("a", 1)
        await c.set("a", 2)
        assert c.evictions == 0
        assert await c.get("a") == 2

    async def test_set_custom_ttl(self):
        c = perfmod.LocalCacheFallback(default_ttl=60)
        await c.set("k", "v", ttl=5)
        entry = c._cache["k"]
        assert 4 < entry["expires_at"] - time.time() <= 5

    async def test_set_ttl_zero_falls_back_to_default(self):
        c = perfmod.LocalCacheFallback(default_ttl=60)
        await c.set("k", "v", ttl=0)
        entry = c._cache["k"]
        assert 59 < entry["expires_at"] - time.time() <= 60

    async def test_delete_present_key(self):
        c = perfmod.LocalCacheFallback()
        await c.set("k", "v")
        assert await c.delete("k") is True
        assert "k" not in c._cache

    async def test_delete_missing_key(self):
        c = perfmod.LocalCacheFallback()
        assert await c.delete("k") is False

    def test_clear_resets_everything(self):
        c = perfmod.LocalCacheFallback()
        c._cache = {"a": {"value": 1, "expires_at": time.time() + 10}, "b": {"value": 2, "expires_at": time.time() + 10}}
        c.hits, c.misses, c.evictions = 5, 3, 2
        c.clear()
        assert c._cache == {}
        assert (c.hits, c.misses, c.evictions) == (0, 0, 0)

    def test_get_stats_empty(self):
        c = perfmod.LocalCacheFallback()
        stats = c.get_stats()
        assert stats["hits"] == 0
        assert stats["hit_rate_percent"] == 0.0
        assert stats["size"] == 0
        assert stats["usage_percent"] == 0.0
        assert stats["entries"] == []

    def test_get_stats_with_data(self):
        c = perfmod.LocalCacheFallback(max_size=10)
        for i in range(3):
            c._cache[f"k{i}"] = {"value": i, "expires_at": time.time() + 10}
        c.hits = 8
        c.misses = 2
        stats = c.get_stats()
        assert stats["size"] == 3
        assert stats["hits"] == 8
        assert stats["misses"] == 2
        assert stats["hit_rate_percent"] == 80.0
        assert stats["usage_percent"] == 30.0
        assert stats["entries"] == ["k0", "k1", "k2"]

    def test_get_stats_entries_capped_at_ten(self):
        c = perfmod.LocalCacheFallback(max_size=100)
        for i in range(25):
            c._cache[f"k{i}"] = {"value": i, "expires_at": time.time() + 10}
        stats = c.get_stats()
        assert len(stats["entries"]) == 10


# ============================================================================
# middleware/performance.py — SimpleCache
# ============================================================================

class TestSimpleCache:
    def test_get_miss(self):
        c = perfmod.SimpleCache()
        assert c.get("nope") is None

    def test_set_then_get_hit(self):
        c = perfmod.SimpleCache()
        c.set("k", "value", ttl=300)
        assert c.get("k") == "value"

    def test_get_expired_removes_entry(self):
        c = perfmod.SimpleCache()
        c.set("k", "value", ttl=1)
        c.cache["k"]["expires_at"] = time.time() - 5
        assert c.get("k") is None
        assert "k" not in c.cache

    def test_set_creates_entry_with_created_at(self):
        c = perfmod.SimpleCache()
        before = time.time()
        c.set("k", "v", ttl=300)
        entry = c.cache["k"]
        assert entry["value"] == "v"
        assert entry["expires_at"] > before
        assert entry["created_at"] >= before

    def test_delete_present_key(self):
        c = perfmod.SimpleCache()
        c.set("k", "v")
        c.delete("k")
        assert "k" not in c.cache

    def test_delete_missing_key_no_error(self):
        c = perfmod.SimpleCache()
        c.delete("missing")

    def test_cleanup_expired_removes_stale_entries(self):
        c = perfmod.SimpleCache()
        c.set("fresh", "v", ttl=300)
        c.cache["stale1"] = {"value": "s1", "expires_at": time.time() - 10}
        c.cache["stale2"] = {"value": "s2", "expires_at": time.time() - 5}
        c.last_cleanup = time.time() - 400  # force interval elapsed
        c._cleanup_expired()
        assert "stale1" not in c.cache
        assert "stale2" not in c.cache
        assert "fresh" in c.cache
        assert c.last_cleanup > time.time() - 10

    def test_cleanup_not_run_within_interval(self):
        c = perfmod.SimpleCache()
        c.cache["stale"] = {"value": "s", "expires_at": time.time() - 10}
        c.last_cleanup = time.time()  # interval not elapsed
        c._cleanup_expired()
        assert "stale" in c.cache

    def test_set_triggers_cleanup(self):
        c = perfmod.SimpleCache()
        c.last_cleanup = time.time() - 400
        c.cache["stale"] = {"value": "s", "expires_at": time.time() - 10}
        c.set("k", "v", ttl=300)
        assert "stale" not in c.cache
        assert "k" in c.cache


# ============================================================================
# middleware/performance.py — CacheMiddleware
# ============================================================================

class FakeSimpleCache:
    def __init__(self, hit_data=None):
        self.hit_data = hit_data
        self.store = {}
        self.sets = []

    def get(self, key):
        return self.hit_data if self.hit_data is not None else self.store.get(key)

    def set(self, key, value, ttl=300):
        self.sets.append((key, value, ttl))
        self.store[key] = value


class FakeStreamingResponse:
    """Starlette 1.x Response no longer exposes body_iterator publicly, so the
    cache middleware's MISS path needs a response-like object with one."""

    def __init__(self, body, status_code=200, headers=None, media_type=None):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type
        self.body_iterator = self._iter()

    async def _iter(self):
        yield self.body


class TestCacheMiddleware:
    def _mw(self):
        return perfmod.CacheMiddleware(app=MagicMock(), cache_ttl=300)

    async def test_non_get_passthrough(self):
        mw = self._mw()
        req = MagicMock(spec=Request)
        req.method = "POST"
        req.url.path = "/api/items"
        fake = FakeSimpleCache()
        resp = make_response()
        calls = []

        async def call_next(request):
            calls.append(request)
            return resp

        with patch.object(perfmod, "cache", fake):
            out = await mw.dispatch(req, call_next)
        assert out is resp
        assert len(calls) == 1
        assert fake.sets == []

    async def test_no_cache_patterns_passthrough(self):
        for path in ["/api/agent/run", "/api/ai/chat", "/api/workflows/execute",
                     "/health/live", "/metrics", "/api/v1/workflows/execute"]:
            mw = self._mw()
            req = MagicMock(spec=Request)
            req.method = "GET"
            req.url.path = path
            fake = FakeSimpleCache()
            resp = make_response()
            calls = []

            async def call_next(request):
                calls.append(request)
                return resp

            with patch.object(perfmod, "cache", fake):
                out = await mw.dispatch(req, call_next)
            assert out is resp
            assert len(calls) == 1
            assert fake.sets == []

    async def test_cache_hit_returns_cached_response(self):
        mw = self._mw()
        req = MagicMock(spec=Request)
        req.method = "GET"
        req.url.path = "/api/items"
        req.url.query = "page=1"
        cached = {
            "content": b'{"items": []}',
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "media_type": "application/json",
        }
        fake = FakeSimpleCache(hit_data=cached)

        async def call_next(request):
            raise AssertionError("call_next must not run on cache hit")

        with patch.object(perfmod, "cache", fake):
            out = await mw.dispatch(req, call_next)
        assert out.headers["X-Cache"] == "HIT"
        assert out.status_code == 200
        assert out.body == b'{"items": []}'
        assert out.media_type == "application/json"

    async def test_cache_hit_media_type_fallback(self):
        mw = self._mw()
        req = MagicMock(spec=Request)
        req.method = "GET"
        req.url.path = "/api/items"
        cached = {"content": b"data", "status_code": 200, "headers": {}}
        fake = FakeSimpleCache(hit_data=cached)

        async def call_next(request):
            raise AssertionError("call_next must not run on cache hit")

        with patch.object(perfmod, "cache", fake):
            out = await mw.dispatch(req, call_next)
        assert out.headers["X-Cache"] == "HIT"
        assert out.media_type == "application/json"

    async def test_cache_miss_stores_and_returns_new_response(self):
        mw = self._mw()
        req = MagicMock(spec=Request)
        req.method = "GET"
        req.url.path = "/api/items"
        req.url.query = ""
        fake = FakeSimpleCache()

        async def call_next(request):
            return FakeStreamingResponse(
                body=b'{"a": 1}', status_code=200,
                headers={"content-type": "application/json"},
                media_type="application/json",
            )

        with patch.object(perfmod, "cache", fake):
            out = await mw.dispatch(req, call_next)
        assert out.headers["X-Cache"] == "MISS"
        assert out.body == b'{"a": 1}'
        assert len(fake.sets) == 1
        key, value, ttl = fake.sets[0]
        assert key.startswith("cache:")
        assert value["content"] == b'{"a": 1}'
        assert value["status_code"] == 200
        assert value["media_type"] == "application/json"
        assert ttl == 300

    async def test_non_success_response_skips_cache(self):
        mw = self._mw()
        req = MagicMock(spec=Request)
        req.method = "GET"
        req.url.path = "/api/missing"
        fake = FakeSimpleCache()

        async def call_next(request):
            return Response(content=b"not found", status_code=404)

        with patch.object(perfmod, "cache", fake):
            out = await mw.dispatch(req, call_next)
        assert out.headers["X-Cache"] == "SKIP"
        assert fake.sets == []
        assert out.status_code == 404

    def test_generate_cache_key_deterministic(self):
        mw = self._mw()
        req = MagicMock(spec=Request)
        req.url.path = "/api/items"
        req.url.query = "a=1&b=2"
        req.method = "GET"
        key1 = mw._generate_cache_key(req)
        key2 = mw._generate_cache_key(req)
        assert key1 == key2
        assert key1.startswith("cache:")
        assert len(key1) == len("cache:") + 32
        req2 = MagicMock(spec=Request)
        req2.url.path = "/api/items"
        req2.url.query = "a=2&b=1"
        req2.method = "GET"
        assert mw._generate_cache_key(req2) != key1


# ============================================================================
# middleware/performance.py — CompressionMiddleware
# ============================================================================

class TestCompressionMiddleware:
    def _req(self, accept_encoding=None):
        req = MagicMock(spec=Request)
        req.headers = {}
        if accept_encoding is not None:
            req.headers["accept-encoding"] = accept_encoding
        return req

    async def test_no_gzip_accept_encoding_passthrough(self):
        mw = perfmod.CompressionMiddleware(app=MagicMock(), min_size=1024)
        req = self._req()
        resp = make_response()
        calls = []

        async def call_next(request):
            calls.append(request)
            return resp

        out = await mw.dispatch(req, call_next)
        assert out is resp
        assert len(calls) == 1

    async def test_small_response_not_compressed(self):
        mw = perfmod.CompressionMiddleware(app=MagicMock(), min_size=1024)
        req = self._req(accept_encoding="gzip")
        resp = make_response()
        resp.headers["content-length"] = "100"

        async def call_next(request):
            return resp

        out = await mw.dispatch(req, call_next)
        assert out is resp
        assert "content-encoding" not in resp.headers

    async def test_compressible_content_type_gets_gzip_header(self):
        mw = perfmod.CompressionMiddleware(app=MagicMock(), min_size=1024)
        for ct in ["application/json", "text/html; charset=utf-8", "text/css",
                   "text/javascript", "application/javascript"]:
            req = self._req(accept_encoding="gzip")
            resp = make_response()
            resp.headers["content-length"] = "5000"
            resp.headers["content-type"] = ct

            async def call_next(request):
                return resp

            out = await mw.dispatch(req, call_next)
            assert out.headers["content-encoding"] == "gzip"

    async def test_non_compressible_content_type_unchanged(self):
        mw = perfmod.CompressionMiddleware(app=MagicMock(), min_size=1024)
        req = self._req(accept_encoding="gzip")
        resp = make_response()
        resp.headers["content-length"] = "5000"
        resp.headers["content-type"] = "image/png"

        async def call_next(request):
            return resp

        out = await mw.dispatch(req, call_next)
        assert "content-encoding" not in resp.headers

    async def test_missing_content_length_still_checks_type(self):
        mw = perfmod.CompressionMiddleware(app=MagicMock(), min_size=1024)
        req = self._req(accept_encoding="gzip")
        resp = make_response()
        resp.headers["content-type"] = "application/json"

        async def call_next(request):
            return resp

        out = await mw.dispatch(req, call_next)
        assert out.headers["content-encoding"] == "gzip"

    async def test_accept_encoding_case_insensitive(self):
        mw = perfmod.CompressionMiddleware(app=MagicMock(), min_size=1024)
        req = self._req(accept_encoding="GZip, br")
        resp = make_response()
        resp.headers["content-length"] = "5000"
        resp.headers["content-type"] = "text/html"

        async def call_next(request):
            return resp

        out = await mw.dispatch(req, call_next)
        assert out.headers["content-encoding"] == "gzip"


# ============================================================================
# middleware/performance.py — DatabaseConnectionPool
# ============================================================================

class FakeHttpxModule:
    def __init__(self, client):
        self.client = client
        self.AsyncClient = MagicMock(return_value=client)
        self.Limits = MagicMock(return_value="limits")
        self.Timeout = MagicMock(return_value="timeout")


class TestDatabaseConnectionPool:
    def test_init_attributes(self):
        pool = perfmod.DatabaseConnectionPool(max_connections=5, connection_timeout=15.0)
        assert pool.max_connections == 5
        assert pool.connection_timeout == 15.0
        assert pool._pool is None
        assert pool._initialized is False

    async def test_get_pool_lazy_init(self, monkeypatch):
        client = AsyncMock()
        fake_httpx = FakeHttpxModule(client)
        monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
        pool = perfmod.DatabaseConnectionPool(max_connections=4, connection_timeout=10.0)
        result = await pool._get_pool()
        assert result is client
        assert pool._initialized is True
        fake_httpx.AsyncClient.assert_called_once()
        call_kwargs = fake_httpx.AsyncClient.call_args.kwargs
        assert call_kwargs["limits"] == "limits"
        assert call_kwargs["timeout"] == "timeout"
        assert call_kwargs["http2"] is True
        fake_httpx.Limits.assert_called_once_with(max_connections=4, max_keepalive_connections=2)

    async def test_get_pool_idempotent(self, monkeypatch):
        client = AsyncMock()
        fake_httpx = FakeHttpxModule(client)
        monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
        pool = perfmod.DatabaseConnectionPool()
        first = await pool._get_pool()
        second = await pool._get_pool()
        assert first is second is client
        assert fake_httpx.AsyncClient.call_count == 1

    async def test_get_connection_returns_pool(self, monkeypatch):
        client = AsyncMock()
        monkeypatch.setitem(sys.modules, "httpx", FakeHttpxModule(client))
        pool = perfmod.DatabaseConnectionPool()
        conn = await pool.get_connection()
        assert conn is client

    async def test_release_connection_noop(self):
        pool = perfmod.DatabaseConnectionPool()
        assert await pool.release_connection(MagicMock()) is None

    async def test_close_with_pool(self, monkeypatch):
        client = AsyncMock()
        monkeypatch.setitem(sys.modules, "httpx", FakeHttpxModule(client))
        pool = perfmod.DatabaseConnectionPool()
        await pool._get_pool()
        await pool.close()
        client.aclose.assert_awaited_once()
        assert pool._initialized is False
        assert pool._pool is client

    async def test_close_without_pool(self):
        pool = perfmod.DatabaseConnectionPool()
        await pool.close()
        assert pool._initialized is False

    async def test_async_context_manager(self, monkeypatch):
        client = AsyncMock()
        monkeypatch.setitem(sys.modules, "httpx", FakeHttpxModule(client))
        pool = perfmod.DatabaseConnectionPool()
        async with pool as p:
            assert p is pool
            assert pool._initialized is True
        assert pool._initialized is False
        client.aclose.assert_awaited_once()

    def test_module_level_db_pool_instance(self):
        assert isinstance(perfmod.db_pool, perfmod.DatabaseConnectionPool)


# ============================================================================
# middleware/performance.py — RequestMetricsMiddleware
# ============================================================================

class TestRequestMetricsMiddleware:
    async def test_dispatch_tracks_metrics_and_header(self):
        mw = perfmod.RequestMetricsMiddleware(app=MagicMock())
        req = MagicMock(spec=Request)
        req.method = "GET"
        req.url.path = "/api/items"
        resp = make_response(status=200)
        resp.headers = {"x": "y"}

        async def call_next(request):
            return resp

        out = await mw.dispatch(req, call_next)
        assert out.headers["X-Response-Time"].endswith("s")
        assert mw.metrics["total_requests"] == 1
        assert mw.metrics["requests_by_method"] == {"GET": 1}
        assert mw.metrics["requests_by_path"] == {"/api/items": 1}
        assert mw.metrics["status_codes"] == {200: 1}
        assert len(mw.metrics["response_times"]) == 1

    async def test_dispatch_multiple_requests(self):
        mw = perfmod.RequestMetricsMiddleware(app=MagicMock())

        for method, path, status in [("GET", "/a", 200), ("GET", "/a", 200), ("POST", "/b", 404)]:
            req = MagicMock(spec=Request)
            req.method = method
            req.url.path = path
            resp = make_response(status=status)
            resp.headers = {}

            async def call_next(request):
                return resp

            await mw.dispatch(req, call_next)
        assert mw.metrics["total_requests"] == 3
        assert mw.metrics["requests_by_method"] == {"GET": 2, "POST": 1}
        assert mw.metrics["requests_by_path"] == {"/a": 2, "/b": 1}
        assert mw.metrics["status_codes"] == {200: 2, 404: 1}

    def test_get_metrics_empty(self):
        mw = perfmod.RequestMetricsMiddleware(app=MagicMock())
        metrics = mw.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["average_response_time"] == 0
        assert metrics["uptime_seconds"] >= 0
        assert metrics["requests_per_second"] == 0
        assert metrics["top_paths"] == []

    def test_get_metrics_with_data(self):
        mw = perfmod.RequestMetricsMiddleware(app=MagicMock())
        mw.metrics["total_requests"] = 2
        mw.metrics["requests_by_method"] = {"GET": 2}
        mw.metrics["requests_by_path"] = {"/a": 1, "/b": 1}
        mw.metrics["response_times"] = [1.0, 3.0]
        mw.metrics["status_codes"] = {200: 2}
        metrics = mw.get_metrics()
        assert metrics["average_response_time"] == 2.0
        assert metrics["requests_per_second"] > 0
        assert metrics["top_paths"] == [("/a", 1), ("/b", 1)]


# ============================================================================
# middleware/performance.py — setup_performance_middleware
# ============================================================================

class TestSetupPerformanceMiddleware:
    def test_adds_middleware_in_order(self):
        added = []
        app = MagicMock()
        app.add_middleware = lambda cls, **kw: added.append((cls, kw))
        perfmod.setup_performance_middleware(app)
        assert [c for c, _ in added] == [
            perfmod.RequestMetricsMiddleware,
            perfmod.CompressionMiddleware,
            perfmod.CacheMiddleware,
        ]
        assert added[2][1] == {"cache_ttl": 300}


# ============================================================================
# middleware/performance.py — cached decorator
# ============================================================================

class TestCachedDecorator:
    async def test_miss_then_hit(self):
        fake = FakeSimpleCache()
        calls = []

        @perfmod.cached(ttl=120, key_prefix="pfx")
        async def compute(x):
            calls.append(x)
            return x * 2

        with patch.object(perfmod, "cache", fake):
            assert await compute(21) == 42
            assert await compute(21) == 42
        assert calls == [21]
        assert len(fake.sets) == 1
        key, value, ttl = fake.sets[0]
        assert ttl == 120
        assert value == 42
        assert key.startswith("pfx:")

    async def test_key_includes_prefix_and_is_deterministic(self):
        fake = FakeSimpleCache()

        @perfmod.cached(ttl=300, key_prefix="")
        async def compute(x, y=2):
            return x + y

        with patch.object(perfmod, "cache", fake):
            await compute(1, y=3)
        key = fake.sets[0][0]
        assert len(key) == 1 + 32
        assert key.startswith(":")

        fake2 = FakeSimpleCache()

        @perfmod.cached(ttl=300, key_prefix="pfx")
        async def other():
            return 1

        with patch.object(perfmod, "cache", fake2):
            await other()
        assert fake2.sets[0][0].startswith("pfx:")
        assert fake2.sets[0][0] != key

    async def test_cached_none_result_is_not_served_from_cache(self):
        fake = FakeSimpleCache()
        calls = []

        @perfmod.cached(ttl=300, key_prefix="")
        async def compute():
            calls.append(1)
            return None

        with patch.object(perfmod, "cache", fake):
            assert await compute() is None
            assert await compute() is None
        assert len(calls) == 2
        assert len(fake.sets) == 2

    async def test_different_args_not_served_from_cache(self):
        fake = FakeSimpleCache()
        calls = []

        @perfmod.cached(ttl=300, key_prefix="")
        async def compute(x):
            calls.append(x)
            return x

        with patch.object(perfmod, "cache", fake):
            assert await compute(1) == 1
            assert await compute(2) == 2
        assert calls == [1, 2]
