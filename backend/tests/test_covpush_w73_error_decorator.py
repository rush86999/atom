# -*- coding: utf-8 -*-
"""Coverage wave 73 — core/error_handler_decorator branch completion.

Adds the async/sync coverage the earlier suite missed: handle_errors
(HTTPException passthrough both modes, reraise both modes), handle_validation_errors
(ValueError/TypeError/HTTPException/generic in async+sync), handle_database_errors
(unique-constraint 409, foreign-key 400, connection/timeout 503, generic,
reraise, DEBUG detail suppression, HTTPException passthrough, async+sync) and
log_errors (bare/param forms, level selection, async+sync). Fully mocked, zero
LLM spend, no network, no real DB.
"""
import logging
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from core.error_handler_decorator import (
    handle_database_errors,
    handle_errors,
    handle_validation_errors,
    log_errors,
)
from core.error_handlers import ErrorCode


# ============================================================================
# handle_errors
# ============================================================================

class TestHandleErrors:
    def test_sync_success(self):
        @handle_errors(error_code=ErrorCode.AGENT_EXECUTION_FAILED)
        def fn(x):
            return x * 2

        assert fn(21) == 42

    @pytest.mark.asyncio
    async def test_async_success(self):
        @handle_errors()
        async def fn(x):
            return x + 1

        assert await fn(1) == 2

    def test_sync_http_exception_passthrough(self):
        @handle_errors()
        def fn():
            raise HTTPException(status_code=404, detail="gone")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == "gone"

    @pytest.mark.asyncio
    async def test_async_http_exception_passthrough(self):
        @handle_errors()
        async def fn():
            raise HTTPException(status_code=403, detail="forbidden")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 403

    def test_sync_generic_converted_to_api_error(self):
        @handle_errors(error_code=ErrorCode.BUSINESS_RULE_VIOLATION, default_message="boom")
        def fn():
            raise ValueError("bad value")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 500
        assert excinfo.value.detail["error_code"] == "BUSINESS_RULE_VIOLATION"
        assert "bad value" in excinfo.value.detail["message"]

    @pytest.mark.asyncio
    async def test_async_generic_converted(self):
        @handle_errors(error_code=ErrorCode.EXTERNAL_SERVICE_ERROR)
        async def fn():
            raise RuntimeError("upstream failed")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.detail["error_code"] == "EXTERNAL_SERVICE_ERROR"

    def test_sync_reraise(self):
        @handle_errors(reraise=True)
        def fn():
            raise ValueError("original")

        with pytest.raises(ValueError, match="original"):
            fn()

    @pytest.mark.asyncio
    async def test_async_reraise(self):
        @handle_errors(reraise=True)
        async def fn():
            raise KeyError("original-key")

        with pytest.raises(KeyError, match="original-key"):
            await fn()

    def test_logs_with_function_context(self, caplog):
        @handle_errors()
        def fn():
            raise ValueError("context check")

        with caplog.at_level(logging.ERROR, logger="core.error_handler_decorator"):
            with pytest.raises(HTTPException):
                fn()
        record = [r for r in caplog.records if getattr(r, "function", None) == "fn"][0]
        assert record.error_type == "ValueError"


# ============================================================================
# handle_validation_errors
# ============================================================================

class TestHandleValidationErrors:
    def test_sync_value_error_to_400(self):
        @handle_validation_errors
        def fn():
            raise ValueError("name required")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 400
        assert excinfo.value.detail["error_code"] == "VALIDATION_ERROR"
        assert "name required" in excinfo.value.detail["message"]

    @pytest.mark.asyncio
    async def test_async_type_error_to_400(self):
        @handle_validation_errors
        async def fn():
            raise TypeError("int expected")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 400
        assert excinfo.value.detail["error_code"] == "VALIDATION_ERROR"

    def test_sync_http_exception_passthrough(self):
        @handle_validation_errors
        def fn():
            raise HTTPException(status_code=429, detail="rate limited")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 429

    @pytest.mark.asyncio
    async def test_async_http_exception_passthrough(self):
        @handle_validation_errors
        async def fn():
            raise HTTPException(status_code=401, detail="unauth")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 401

    def test_sync_unexpected_error_generic_message(self):
        """Internal details must NOT leak to the client."""
        @handle_validation_errors
        def fn():
            raise RuntimeError("secret internal detail")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 500
        assert excinfo.value.detail["error_code"] == "INTERNAL_ERROR"
        assert excinfo.value.detail["message"] == "An unexpected error occurred"
        assert "secret internal detail" not in str(excinfo.value.detail)

    @pytest.mark.asyncio
    async def test_async_unexpected_error_generic_message(self):
        @handle_validation_errors
        async def fn():
            raise RuntimeError("secret async detail")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.detail["message"] == "An unexpected error occurred"

    def test_success_paths(self):
        @handle_validation_errors
        def sync_fn(x):
            return x

        @handle_validation_errors
        async def async_fn(x):
            return x

        assert sync_fn(3) == 3

    @pytest.mark.asyncio
    async def test_async_success(self):
        @handle_validation_errors
        async def fn(x):
            return x

        assert await fn("ok") == "ok"


# ============================================================================
# handle_database_errors
# ============================================================================

class TestHandleDatabaseErrors:
    def test_sync_unique_constraint_409(self):
        @handle_database_errors()
        def fn():
            raise ValueError("duplicate key value violates unique constraint")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 409
        assert excinfo.value.detail["error_code"] == "ALREADY_EXISTS"
        assert excinfo.value.detail["details"]["original_error"]

    @pytest.mark.asyncio
    async def test_async_unique_constraint_409(self):
        @handle_database_errors()
        async def fn():
            raise ValueError("UNIQUE constraint failed")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 409

    def test_sync_foreign_key_400(self):
        @handle_database_errors()
        def fn():
            raise ValueError("violates foreign key constraint")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 400
        assert excinfo.value.detail["error_code"] == "VALIDATION_ERROR"
        assert "does not exist" in excinfo.value.detail["message"]

    @pytest.mark.asyncio
    async def test_async_foreign_key_400(self):
        @handle_database_errors()
        async def fn():
            raise ValueError("FOREIGN KEY constraint failed")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 400

    def test_sync_connection_503(self):
        @handle_database_errors()
        def fn():
            raise ConnectionError("connection refused")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 503
        assert excinfo.value.detail["error_code"] == "DATABASE_ERROR"

    @pytest.mark.asyncio
    async def test_async_timeout_503(self):
        @handle_database_errors()
        async def fn():
            raise TimeoutError("query timed out")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 503

    def test_sync_generic_uses_default_message(self):
        @handle_database_errors(default_message="custom db message")
        def fn():
            raise RuntimeError("weird db thing")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 500
        assert excinfo.value.detail["message"] == "custom db message"

    def test_debug_log_level_includes_original_error(self):
        """At DEBUG log level the generic branch attaches the original error
        to details (diagnostic aid); above DEBUG it must be suppressed so
        internals never reach clients."""
        logger = logging.getLogger("core.error_handler_decorator")
        saved = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            @handle_database_errors()
            def fn():
                raise RuntimeError("debug-only-detail")

            with pytest.raises(HTTPException) as excinfo:
                fn()
            assert excinfo.value.detail["details"]["original_error"] == "debug-only-detail"
        finally:
            logger.setLevel(saved)

    @pytest.mark.asyncio
    async def test_async_generic_uses_default_message(self):
        @handle_database_errors(default_message="async db message")
        async def fn():
            raise RuntimeError("async weirdness")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 500
        assert excinfo.value.detail["message"] == "async db message"

    def test_sync_generic_reraise(self):
        @handle_database_errors(reraise=True)
        def fn():
            raise RuntimeError("reraising")

        with pytest.raises(RuntimeError, match="reraising"):
            fn()

    @pytest.mark.asyncio
    async def test_async_generic_reraise(self):
        @handle_database_errors(reraise=True)
        async def fn():
            raise RuntimeError("async reraise")

        with pytest.raises(RuntimeError, match="async reraise"):
            await fn()

    def test_http_exception_passthrough(self):
        @handle_database_errors()
        def fn():
            raise HTTPException(status_code=418, detail="teapot")

        with pytest.raises(HTTPException) as excinfo:
            fn()
        assert excinfo.value.status_code == 418

    @pytest.mark.asyncio
    async def test_async_http_exception_passthrough(self):
        @handle_database_errors()
        async def fn():
            raise HTTPException(status_code=418, detail="teapot")

        with pytest.raises(HTTPException) as excinfo:
            await fn()
        assert excinfo.value.status_code == 418

    def test_success_paths(self):
        @handle_database_errors()
        def sync_fn():
            return "ok"

        @handle_database_errors()
        async def async_fn():
            return "ok"

        assert sync_fn() == "ok"

    @pytest.mark.asyncio
    async def test_async_success(self):
        @handle_database_errors()
        async def fn():
            return "ok"

        assert await fn() == "ok"


# ============================================================================
# log_errors
# ============================================================================

class TestLogErrors:
    def test_bare_form_logs_and_reraises(self, caplog):
        @log_errors
        def fn():
            raise ValueError("bare")

        with caplog.at_level(logging.ERROR, logger="core.error_handler_decorator"):
            with pytest.raises(ValueError, match="bare"):
                fn()
        assert any(r.message.startswith("Exception in fn: bare") for r in caplog.records)

    def test_param_form_with_custom_level(self, caplog):
        @log_errors(level="WARNING")
        def fn():
            raise ValueError("warned")

        with caplog.at_level(logging.WARNING, logger="core.error_handler_decorator"):
            with pytest.raises(ValueError):
                fn()
        assert any(r.levelname == "WARNING" and "warned" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_async_logs_and_reraises(self, caplog):
        @log_errors(level="INFO")
        async def fn():
            raise KeyError("async-key")

        with caplog.at_level(logging.INFO, logger="core.error_handler_decorator"):
            with pytest.raises(KeyError, match="async-key"):
                await fn()
        assert any("Exception in fn: 'async-key'" in r.message for r in caplog.records)

    def test_success(self):
        @log_errors
        def fn():
            return "fine"

        assert fn() == "fine"

    @pytest.mark.asyncio
    async def test_async_success(self):
        @log_errors(level="DEBUG")
        async def fn():
            return "fine"

        assert await fn() == "fine"

    def test_unknown_level_falls_back_to_error(self, caplog):
        @log_errors(level="NOT_A_LEVEL")
        def fn():
            raise ValueError("fallback")

        with caplog.at_level(logging.ERROR, logger="core.error_handler_decorator"):
            with pytest.raises(ValueError):
                fn()
        assert any(r.levelname == "ERROR" and "fallback" in r.message for r in caplog.records)

    def test_wraps_preserves_name(self):
        @log_errors
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"
