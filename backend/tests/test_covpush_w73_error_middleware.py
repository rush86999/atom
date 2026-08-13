# -*- coding: utf-8 -*-
"""Coverage wave 73 — core/error_middleware (statistics + middleware).

This module was never imported by any existing test file (0% baseline).
Covers: ErrorStatistics singleton + record/reset/prune/statistics,
ErrorHandlingMiddleware init (debug env default/override, statistics toggle),
dispatch success/exception paths, request-context extraction (with/without
user_id, missing client), error-info extraction (status_code attr, common
exceptions, unknown), 4xx-warning vs 5xx-error logging, debug-mode response
augmentation, non-HTTP details block, error-code mapping (custom attr /
builtin map / fallback), message resolution (detail dict/str/fallbacks) and
the module-level convenience functions. Fully mocked, zero LLM spend, no
network, no real DB.
"""
import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from starlette.requests import Request as StarletteRequest

from core.error_middleware import (
    ErrorHandlingMiddleware,
    ErrorStatistics,
    get_error_statistics,
    reset_error_statistics,
)


def make_request(**state_overrides):
    request = StarletteRequest(
        scope={
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"a=1",
            "headers": [(b"user-agent", b"pytest-agent")],
            "client": ("203.0.113.7", 4444),
        }
    )
    for key, value in state_overrides.items():
        setattr(request.state, key, value)
    return request


class _FakeApp:
    def __init__(self):
        pass


# ============================================================================
# ErrorStatistics
# ============================================================================

class TestErrorStatistics:
    def test_singleton(self):
        first = ErrorStatistics()
        second = ErrorStatistics()
        assert first is second
        first.reset()

    def test_record_and_statistics(self):
        stats = ErrorStatistics()
        stats.reset()
        stats.record_request()
        stats.record_request()
        stats.record_error("ValueError", "/api/x", 400)
        stats.record_error("ValueError", "/api/x", 400)
        stats.record_error("RuntimeError", "/api/y", 500)

        info = stats.get_statistics()
        assert info["total_requests"] == 2
        assert info["total_errors"] == 3
        assert info["error_rate"] == 1.5
        assert info["error_counts"] == {"ValueError": 2, "RuntimeError": 1}
        assert info["endpoint_errors"]["/api/x"] == {"ValueError": 2}
        assert len(info["recent_errors"]) == 3
        assert info["recent_errors"][-1]["status_code"] == 500

    def test_recent_errors_pruned_to_100(self):
        stats = ErrorStatistics()
        stats.reset()
        for i in range(150):
            stats.record_error("ValueError", f"/api/{i % 5}", 400)
        assert len(stats._last_24h_errors) == 100
        assert len(stats.get_statistics()["recent_errors"]) == 10

    def test_reset(self):
        stats = ErrorStatistics()
        stats.record_request()
        stats.record_error("ValueError", "/api/x", 400)
        stats.reset()
        info = stats.get_statistics()
        assert info["total_requests"] == 0
        assert info["total_errors"] == 0
        assert info["error_rate"] == 0.0

    def test_zero_requests_error_rate_zero(self):
        stats = ErrorStatistics()
        stats.reset()
        assert stats.get_statistics()["error_rate"] == 0.0


# ============================================================================
# ErrorHandlingMiddleware — init
# ============================================================================

class TestMiddlewareInit:
    def test_debug_default_from_env(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "true")
        mw = ErrorHandlingMiddleware(_FakeApp())
        assert mw._debug_mode is True
        mw._stats.reset()

    def test_debug_default_false_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("DEBUG", raising=False)
        mw = ErrorHandlingMiddleware(_FakeApp())
        assert mw._debug_mode is False
        mw._stats.reset()

    def test_debug_override(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), debug_mode=True)
        assert mw._debug_mode is True
        mw._stats.reset()

    def test_statistics_disabled(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        assert mw._stats is None

    def test_log_errors_flag_stored(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), log_errors=False)
        assert mw._log_errors is False
        mw._stats.reset()


# ============================================================================
# dispatch
# ============================================================================

class TestDispatch:
    @pytest.mark.asyncio
    async def test_success_adds_timing_header(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        request = make_request()

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await mw.dispatch(request, call_next)
        assert result is response
        assert "X-Process-Time" in response.headers

    @pytest.mark.asyncio
    async def test_slow_request_warned(self, caplog):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        request = make_request()

        async def call_next(req):
            await asyncio.sleep(0)
            return MagicMock(headers={})

        elapsed = [0.0, 1.5]
        with patch("core.error_middleware.time.time", side_effect=lambda: elapsed.pop(0) if elapsed else 99.0):
            with caplog.at_level(logging.WARNING, logger="core.error_middleware"):
                await mw.dispatch(request, call_next)
        assert any("Slow request detected" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_exception_path_returns_error_response(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        request = make_request()

        async def call_next(req):
            raise ValueError("bad input")

        response = await mw.dispatch(request, call_next)
        assert response.status_code == 400
        body = response.body
        assert b'"success":false' in body
        assert b"VALIDATION_ERROR" in body

    @pytest.mark.asyncio
    async def test_exception_records_statistics(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=True)
        request = make_request()

        async def call_next(req):
            raise PermissionError("no")

        await mw.dispatch(request, call_next)
        stats = mw.get_statistics()
        assert stats["total_requests"] == 1
        assert stats["total_errors"] == 1
        assert stats["error_counts"] == {"PermissionError": 1}

    @pytest.mark.asyncio
    async def test_exception_logging_toggle(self, caplog):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False, log_errors=False)
        request = make_request()

        async def call_next(req):
            raise RuntimeError("quiet")

        with caplog.at_level(logging.ERROR, logger="core.error_middleware"):
            await mw.dispatch(request, call_next)
        assert not any("quiet" in r.message for r in caplog.records)


# ============================================================================
# _extract_request_context / _extract_error_info
# ============================================================================

class TestExtractRequestContext:
    def test_with_user_id(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        ctx = mw._extract_request_context(make_request(user_id="user-9"))
        assert ctx["method"] == "GET"
        assert ctx["path"] == "/api/test"
        assert ctx["query_params"] == "a=1"
        assert ctx["client_host"] == "203.0.113.7"
        assert ctx["user_agent"] == "pytest-agent"
        assert ctx["user_id"] == "user-9"

    def test_without_user_id(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        ctx = mw._extract_request_context(make_request())
        assert "user_id" not in ctx

    def test_missing_client(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        request = StarletteRequest(
            scope={
                "type": "http", "method": "GET", "path": "/api/x",
                "query_string": b"", "headers": [], "client": None,
            }
        )
        ctx = mw._extract_request_context(request)
        assert ctx["client_host"] is None


class TestExtractErrorInfo:
    def setup_method(self):
        self.mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)

    def test_http_exception_uses_status_code_attr(self):
        info = self.mw._extract_error_info(
            HTTPException(status_code=418, detail="teapot"), {"path": "/x"}
        )
        assert info["status_code"] == 418
        assert info["is_http_exception"] is True
        assert info["type"] == "HTTPException"

    def test_common_exception_mapping(self):
        ctx = {"path": "/x"}
        assert self.mw._extract_error_info(ValueError("v"), ctx)["status_code"] == 400
        assert self.mw._extract_error_info(TypeError("t"), ctx)["status_code"] == 400
        assert self.mw._extract_error_info(KeyError("k"), ctx)["status_code"] == 400
        assert self.mw._extract_error_info(AttributeError("a"), ctx)["status_code"] == 400
        assert self.mw._extract_error_info(PermissionError("p"), ctx)["status_code"] == 403
        assert self.mw._extract_error_info(FileNotFoundError("n"), ctx)["status_code"] == 404

    def test_unknown_exception_500(self):
        info = self.mw._extract_error_info(RuntimeError("boom"), {"path": "/x"})
        assert info["status_code"] == 500
        assert info["is_http_exception"] is False


# ============================================================================
# _log_error
# ============================================================================

class TestLogError:
    def setup_method(self):
        self.mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)

    def test_client_error_logs_warning(self, caplog):
        ctx = {"method": "GET", "path": "/api/x"}
        exc = HTTPException(status_code=403, detail="denied")
        with caplog.at_level(logging.WARNING, logger="core.error_middleware"):
            self.mw._log_error(exc, ctx, 0.5)
        assert any(r.levelname == "WARNING" and "/api/x" in r.message for r in caplog.records)

    def test_server_error_logs_error(self, caplog):
        ctx = {"method": "GET", "path": "/api/x"}
        exc = RuntimeError("server broke")
        with caplog.at_level(logging.ERROR, logger="core.error_middleware"):
            self.mw._log_error(exc, ctx, 1.2)
        assert any(r.levelname == "ERROR" and "server broke" in r.message for r in caplog.records)


# ============================================================================
# _create_error_response / _get_error_code / _get_error_message
# ============================================================================

class TestCreateErrorResponse:
    def test_debug_mode_augments_body(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False, debug_mode=True)
        ctx = {"path": "/api/x", "method": "GET"}
        info = {"type": "ValueError", "message": "v", "status_code": 400,
                "is_http_exception": False}
        resp = mw._create_error_response(ValueError("v"), info, ctx)
        body = resp.body
        assert b"stack_trace" in body
        assert b'"type":"ValueError"' in body
        assert b'"debug":' in body

    def test_non_http_exception_gets_details_block(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        ctx = {"path": "/api/x", "method": "GET"}
        info = {"type": "RuntimeError", "message": "boom", "status_code": 500,
                "is_http_exception": False}
        resp = mw._create_error_response(RuntimeError("boom"), info, ctx)
        body = resp.body
        assert b'"exception_type":"RuntimeError"' in body
        assert b"INTERNAL_ERROR" in body
        assert resp.status_code == 500

    def test_http_exception_omits_details_block(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        ctx = {"path": "/api/x", "method": "GET"}
        info = {"type": "HTTPException", "message": "teapot", "status_code": 418,
                "is_http_exception": True}
        resp = mw._create_error_response(HTTPException(418, "teapot"), info, ctx)
        assert b"exception_type" not in resp.body
        assert resp.status_code == 418


class TestGetErrorCode:
    def setup_method(self):
        self.mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)

    def test_custom_error_code_attr(self):
        exc = ValueError("x")
        exc.error_code = "MY_CUSTOM_CODE"
        assert self.mw._get_error_code(exc, {"type": "ValueError"}) == "MY_CUSTOM_CODE"

    @pytest.mark.parametrize("exc,expected", [
        (ValueError("x"), "VALIDATION_ERROR"),
        (TypeError("x"), "TYPE_ERROR"),
        (KeyError("x"), "MISSING_FIELD"),
        (AttributeError("x"), "ATTRIBUTE_ERROR"),
        (PermissionError("x"), "PERMISSION_DENIED"),
        (FileNotFoundError("x"), "NOT_FOUND"),
    ])
    def test_mapped_types(self, exc, expected):
        assert self.mw._get_error_code(exc, {"type": type(exc).__name__}) == expected

    def test_fallback_internal_error(self):
        assert self.mw._get_error_code(
            RuntimeError("x"), {"type": "RuntimeError"}
        ) == "INTERNAL_ERROR"


class TestGetErrorMessage:
    def setup_method(self):
        self.mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)

    def test_detail_dict_nested_message(self):
        exc = HTTPException(status_code=400, detail={"error": {"message": "nested msg"}})
        assert self.mw._get_error_message(exc, {}) == "nested msg"

    def test_detail_dict_without_nested_message(self):
        exc = HTTPException(status_code=400, detail={"field": "x"})
        msg = self.mw._get_error_message(exc, {})
        assert msg == str(exc)

    def test_detail_string(self):
        exc = HTTPException(status_code=404, detail="plain detail")
        assert self.mw._get_error_message(exc, {}) == "plain detail"

    def test_str_exception_message(self):
        assert self.mw._get_error_message(ValueError("real msg"), {}) == "real msg"

    def test_fallback_500(self):
        assert self.mw._get_error_message(RuntimeError(), {"status_code": 500}) == "An internal error occurred"

    def test_fallback_404(self):
        assert self.mw._get_error_message(RuntimeError(), {"status_code": 404}) == "Resource not found"

    def test_fallback_403(self):
        assert self.mw._get_error_message(RuntimeError(), {"status_code": 403}) == "Permission denied"

    def test_fallback_401(self):
        assert self.mw._get_error_message(RuntimeError(), {"status_code": 401}) == "Authentication required"

    def test_fallback_default(self):
        assert self.mw._get_error_message(RuntimeError(), {"status_code": 409}) == "An error occurred"


# ============================================================================
# statistics accessors + convenience functions
# ============================================================================

class TestStatisticsAccessors:
    def test_get_statistics_enabled(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=True)
        stats = mw.get_statistics()
        assert "total_requests" in stats
        mw.reset_statistics()
        assert mw.get_statistics()["total_requests"] == 0

    def test_get_statistics_disabled(self):
        mw = ErrorHandlingMiddleware(_FakeApp(), enable_statistics=False)
        assert mw.get_statistics() == {"message": "Statistics not enabled"}
        mw.reset_statistics()

    def test_module_level_convenience(self):
        reset_error_statistics()
        stats = get_error_statistics()
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0
        ErrorStatistics().reset()
