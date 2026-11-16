"""Contract: the PUBLIC HTTPException wire format vs. a bare FastAPI app.

`main_api_app` installs `core.error_handler.setup_error_handlers`, whose
`http_exception_handler` returns a dict `HTTPException.detail` DIRECTLY as the
response body. A structured refusal raised as
`HTTPException(409, detail={"error": {"code": ..., "message": ...}})`
therefore reaches production clients as top-level `body.error.message` — NOT
`body.detail.error.message`.

A bare FastAPI app (no custom handler, as in several backend tests) nests the
same detail under `detail`. Both shapes are asserted here so the client-side
reader cannot regress to only one of them.

Scratch-only: no database, no app import, no network.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.error_handler import setup_error_handlers

DETAIL = {
    "error": {
        "code": "STALE_TARGET",
        "message": "The goal changed after it was reviewed. Refresh and review again.",
    },
    "verification": {"status": "conflict"},
}


def _app(with_public_handlers: bool) -> FastAPI:
    app = FastAPI()
    if with_public_handlers:
        setup_error_handlers(app)

    @app.post("/refuse")
    async def refuse():
        raise HTTPException(status_code=409, detail=DETAIL)

    return app


def test_public_handler_returns_the_detail_dict_top_level():
    response = TestClient(_app(True)).post("/refuse")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "STALE_TARGET"
    assert body["error"]["message"] == DETAIL["error"]["message"]
    assert body["verification"] == DETAIL["verification"]
    # The production handler does NOT add a "detail" wrapper.
    assert "detail" not in body


def test_bare_fastapi_nests_the_same_detail():
    response = TestClient(_app(False)).post("/refuse")

    assert response.status_code == 409
    body = response.json()
    assert body["detail"]["error"]["code"] == "STALE_TARGET"
    assert body["detail"]["error"]["message"] == DETAIL["error"]["message"]
