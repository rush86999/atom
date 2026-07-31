"""
Round 55 — Unbounded request bodies: OOM DoS via huge JSON/form payloads
(Red-Green-Refactor).

InputValidationMiddleware (registered on the real app) reads the ENTIRE
POST/PUT/PATCH body into memory with no size cap — a multi-GB JSON body is
fully allocated (and regex-scanned) before any handler runs. FastAPI/
Starlette impose no default body limit, so every JSON-accepting endpoint is
an OOM amplification point. The middleware is the right choke point: it
already materializes every body, so it must stream-read with a hard cap.

Fix: stream the body with a cap (MAX_BODY_BYTES, default 64 MiB — covers the
50 MiB multipart uploads the R21/R50 caps allow) instead of unbounded
request.body(); return 413 when exceeded.
"""

import inspect

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.middleware import InputValidationMiddleware


def _make_app():
    app = FastAPI()

    @app.post("/echo")
    async def echo(payload: dict):
        return {"received": len(payload)}

    app.add_middleware(InputValidationMiddleware)
    return app


class TestRequestBodySizeLimit:
    def test_oversized_body_rejected(self, monkeypatch):
        monkeypatch.setenv("MAX_BODY_BYTES", "2048")
        client = TestClient(_make_app(), raise_server_exceptions=False)

        resp = client.post("/echo", json={"data": "x" * 4096})

        assert resp.status_code == 413, (
            "Oversized request body was accepted — unbounded allocation "
            f"before handler execution (got {resp.status_code})"
        )

    def test_oversized_body_rejected_with_default_cap(self, monkeypatch):
        monkeypatch.delenv("MAX_BODY_BYTES", raising=False)
        client = TestClient(_make_app(), raise_server_exceptions=False)

        resp = client.post(
            "/echo", json={"data": "x" * (80 * 1024 * 1024)}
        )

        assert resp.status_code == 413

    def test_small_body_still_processed(self, monkeypatch):
        monkeypatch.setenv("MAX_BODY_BYTES", "2048")
        client = TestClient(_make_app(), raise_server_exceptions=False)

        resp = client.post("/echo", json={"data": "ok"})

        assert resp.status_code == 200

    def test_middleware_reads_body_with_streaming_cap(self):
        """Source guard: the middleware must stream with a cap, not
        request.body() the whole payload unbounded."""
        src = inspect.getsource(InputValidationMiddleware)
        assert "stream()" in src and "MAX_BODY_BYTES" in src, (
            "InputValidationMiddleware materializes the full request body "
            "with no size cap — OOM denial of service"
        )
