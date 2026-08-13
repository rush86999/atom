# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/error_handler (64 stmts, never wave-tested).

- http_exception_handler: dict detail passthrough, str detail wrapped,
  status_code preserved.
- database_error_handler: request_id present/absent, 500 DATABASE_ERROR body,
  SQLAlchemyError raised.
- api_error_handler: exception attrs (message/error_code/status_code/details)
  honored, fallback defaults for plain exceptions, request_id passthrough.
- generic_error_handler: delegates to global_exception_handler.
- setup_error_handlers: registers HTTPException/SQLAlchemyError/Exception
  always, AtomException + APIError when importable (APIError is None in this
  env — patched to a dummy to cover the registration branch), and the
  skip-branch when both are None.

No LLM / no network / no real FastAPI server (fake app records handlers).
"""
import json
from types import SimpleNamespace

import asyncio
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

import core.error_handler as eh
from core.error_handler import (
    api_error_handler,
    database_error_handler,
    generic_error_handler,
    http_exception_handler,
    setup_error_handlers,
)


class _App:
    def __init__(self):
        self.handlers = []

    def add_exception_handler(self, exc_type, handler):
        self.handlers.append((exc_type, handler))


def _request(request_id="req-123"):
    return SimpleNamespace(state=SimpleNamespace(request_id=request_id))


def _request_without_state():
    return SimpleNamespace()


class _ApiError(Exception):
    def __init__(self, message, error_code="CUSTOM_CODE", status_code=422, details=None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class TestHttpExceptionHandler:
    def test_dict_detail_passthrough(self):
        resp = asyncio.run(http_exception_handler(_request(), HTTPException(status_code=403, detail={"why": "nope"})))
        assert resp.status_code == 403
        assert json.loads(resp.body) == {"why": "nope"}

    def test_str_detail_wrapped(self):
        resp = asyncio.run(http_exception_handler(_request(), HTTPException(status_code=404, detail="missing")))
        assert resp.status_code == 404
        assert json.loads(resp.body) == {"detail": "missing"}

    def test_status_code_preserved(self):
        resp = asyncio.run(http_exception_handler(_request(), HTTPException(status_code=429, detail="slow down")))
        assert resp.status_code == 429


class TestDatabaseErrorHandler:
    def test_with_request_id(self, caplog):
        resp = asyncio.run(database_error_handler(_request("r1"), SQLAlchemyError("boom")))
        assert resp.status_code == 500
        body = json.loads(resp.body)
        assert body["error_code"] == "DATABASE_ERROR"
        assert body["request_id"] == "r1"

    def test_without_request_id(self):
        resp = asyncio.run(database_error_handler(_request_without_state(), SQLAlchemyError("boom")))
        body = json.loads(resp.body)
        assert body["request_id"] is None

    def test_logs_exception(self, caplog):
        with caplog.at_level("ERROR", logger="core.error_handler"):
            asyncio.run(database_error_handler(_request(), SQLAlchemyError("db exploded")))
        assert "Database error occurred" in caplog.text
        assert "db exploded" in caplog.text


class TestApiErrorHandler:
    def test_custom_attrs_honored(self):
        resp = asyncio.run(api_error_handler(_request("r9"), _ApiError("bad input", details={"field": "x"})))
        assert resp.status_code == 422
        body = json.loads(resp.body)
        assert body["error_code"] == "CUSTOM_CODE"
        assert body["message"] == "bad input"
        assert body["details"] == {"field": "x"}
        assert body["request_id"] == "r9"

    def test_plain_exception_falls_back(self):
        resp = asyncio.run(api_error_handler(_request(), RuntimeError("kaboom")))
        assert resp.status_code == 500
        body = json.loads(resp.body)
        assert body["error_code"] == "API_ERROR"
        assert body["message"] == "kaboom"
        assert body["details"] is None

    def test_no_request_state(self):
        resp = asyncio.run(api_error_handler(_request_without_state(), _ApiError("x")))
        assert json.loads(resp.body)["request_id"] is None


class TestGenericErrorHandler:
    def test_delegates_to_global_handler(self, monkeypatch):
        async def fake_global(request, exc):
            return JSONResponse(status_code=500, content={"handled": "globally"})

        monkeypatch.setattr(eh, "global_exception_handler", fake_global)
        resp = asyncio.run(generic_error_handler(_request(), RuntimeError("x")))
        assert resp.status_code == 500
        assert json.loads(resp.body) == {"handled": "globally"}


class TestSetupErrorHandlers:
    def test_registers_core_handlers_and_atom_exception(self):
        app = _App()
        setup_error_handlers(app)
        types = [t for t, _ in app.handlers]
        from core.exceptions import AtomException

        assert HTTPException in types
        assert SQLAlchemyError in types
        assert Exception in types
        assert AtomException in types

    def test_registers_api_error_when_importable(self, monkeypatch):
        class DummyAPIError(Exception):
            pass

        monkeypatch.setattr(eh, "APIError", DummyAPIError)
        app = _App()
        setup_error_handlers(app)
        types = [t for t, _ in app.handlers]
        assert DummyAPIError in types

    def test_skips_atom_and_api_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(eh, "AtomException", None)
        monkeypatch.setattr(eh, "APIError", None)
        app = _App()
        setup_error_handlers(app)
        types = [t for t, _ in app.handlers]
        assert types == [HTTPException, SQLAlchemyError, Exception]


class TestImportFailureBranch:
    def test_exceptions_module_missing_sets_both_none(self, monkeypatch):
        # Covers the `except ImportError` branches of both module-level
        # imports. Runs last + reloads with the real import restored so the
        # module is left in its normal state.
        import builtins
        import importlib

        real_import = builtins.__import__

        def _fake_import(name, *a, **k):
            if name == "core.exceptions":
                raise ImportError("No module named core.exceptions")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        importlib.reload(eh)
        assert eh.AtomException is None
        assert eh.APIError is None

        monkeypatch.undo()
        importlib.reload(eh)
        from core.exceptions import AtomException

        assert eh.AtomException is AtomException
        assert eh.APIError is None  # core.exceptions has no APIError in this repo
