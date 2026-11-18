"""Contract: exception headers survive the installed public HTTP handler.

Regression for real 401s losing ``WWW-Authenticate: Bearer``: the handler in
``core.error_handler`` rebuilt the JSON response from the detail alone. These
tests exercise the handler actually registered by ``setup_error_handlers`` and
keep the existing wire contracts (string detail wrapped, dict detail flat).

Scratch-only: no database, no app import, no network, no server.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from core.error_handler import http_exception_handler, setup_error_handlers


def _app() -> FastAPI:
    app = FastAPI()
    setup_error_handlers(app)

    @app.get("/unauthorized")
    async def unauthorized():
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/conflict")
    async def conflict():
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "STALE_TARGET",
                    "message": "Refresh and review again.",
                },
                "verification": {"status": "conflict"},
            },
            headers={"X-Contract": "dict-detail"},
        )

    return app


def _synthetic_request(path: str = "/synthetic") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


def test_installed_handler_keeps_bearer_challenge_for_string_detail():
    response = TestClient(_app()).get("/unauthorized")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Could not validate credentials"}


def test_installed_handler_keeps_headers_and_flat_dict_detail():
    response = TestClient(_app()).get("/conflict")

    assert response.status_code == 409
    assert response.headers["x-contract"] == "dict-detail"
    body = response.json()
    assert body["error"]["code"] == "STALE_TARGET"
    assert body["verification"] == {"status": "conflict"}
    assert "detail" not in body


def test_direct_installed_handler_with_synthetic_request_preserves_contracts():
    app = _app()
    handler = app.exception_handlers[HTTPException]
    assert handler is http_exception_handler

    response = asyncio.run(
        handler(
            _synthetic_request(),
            HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer", "X-Extra": "kept"},
            ),
        )
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["x-extra"] == "kept"
    assert json.loads(response.body) == {"detail": "Could not validate credentials"}


def test_direct_installed_handler_keeps_dict_detail_flat_and_headers():
    app = _app()
    handler = app.exception_handlers[HTTPException]
    detail = {"error": {"code": "STALE_TARGET", "message": "Refresh."}}

    response = asyncio.run(
        handler(
            _synthetic_request(),
            HTTPException(status_code=409, detail=detail, headers={"X-Contract": "dict"}),
        )
    )

    assert response.status_code == 409
    assert response.headers["x-contract"] == "dict"
    assert json.loads(response.body) == detail
