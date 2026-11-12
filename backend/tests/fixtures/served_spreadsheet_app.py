"""Served-process entry point for the stale-cache spreadsheet regression.

The regression launches the REAL FastAPI application under uvicorn (see
``backend/tests/test_served_spreadsheet_stale_cache.py``).  This module is
that process's app entry point and supplies only the two MODEL transports the
turn would otherwise reach for:

* ``LLMService`` planner/narration/stream calls are doubled.  The planner
  double declines tool use; the chat turn's deterministic calculation lane
  still runs, and an explicit formula ask is answered from the workbook.  A
  narration double is provided for any path that asks for prose.
* ``EmbeddingService`` is doubled with a deterministic 384-dimension vector so
  the upload's LanceDB mirror can be written without downloading/loading a
  local ONNX model.

Everything that defines the result under test stays real: the HTTP/auth
routes, document upload, sheet-dataset materialization (Parquet + formula
sidecar), the workbook calculation lane, the formula engine, task lifecycle
persistence, and the chat response rendering.

Before importing the app, install a loopback-only socket guard.  A stray
provider, telemetry or web call therefore fails instead of leaving the box.
No provider credential is read from this file; the test pins every known key
to an empty string and passes an explicit scratch SQLite URL.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import threading

# ---------------------------------------------------------------------------
# Loopback-only network guard (installed BEFORE the app imports)
# ---------------------------------------------------------------------------
_ALLOWED_CONNECT_HOSTS = {"127.0.0.1", "::1", "localhost"}
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_create_connection = socket.create_connection


def _host_allowed(host) -> bool:
    return str(host) in _ALLOWED_CONNECT_HOSTS


def _check_address(address) -> None:
    if isinstance(address, tuple) and address:
        if not _host_allowed(address[0]):
            raise OSError(
                f"served spreadsheet fixture denied non-loopback connect: "
                f"{address!r}")


def _connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _check_address(address)
    return _orig_connect(self, address)


def _connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _check_address(address)
    return _orig_connect_ex(self, address)


def _create_connection(address, *args, **kwargs):
    _check_address(address)
    return _orig_create_connection(address, *args, **kwargs)


socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
socket.create_connection = _create_connection

import main_api_app  # noqa: E402  (must follow the network guard)

app = main_api_app.app

from core.embedding_service import EmbeddingService  # noqa: E402
from core.llm_service import LLMService  # noqa: E402

# ---------------------------------------------------------------------------
# Transport trace (optional; the test can inspect which double was used)
# ---------------------------------------------------------------------------
_TRACE_LOCK = threading.Lock()


def _trace(kind: str, **fields) -> None:
    path = os.getenv("SERVED_SPREADSHEET_TRACE")
    if not path:
        return
    record = {"kind": kind, **fields}
    with _TRACE_LOCK:
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Deterministic embedding double (no FastEmbed download / ONNX model)
# ---------------------------------------------------------------------------
def _deterministic_embedding(text) -> list[float]:
    digest = hashlib.sha512(str(text or "").encode("utf-8")).digest()
    vector: list[float] = []
    while len(vector) < 384:
        vector.extend((byte - 127.5) / 127.5 for byte in digest)
        digest = hashlib.sha512(digest).digest()
    return vector[:384]


async def _fake_fastembed_embedding(self, text):
    return _deterministic_embedding(text)


async def _fake_fastembed_embeddings_batch(self, texts):
    return [_deterministic_embedding(text) for text in (texts or [])]


EmbeddingService._generate_fastembed_embedding = _fake_fastembed_embedding
EmbeddingService._generate_fastembed_embeddings_batch = (
    _fake_fastembed_embeddings_batch)


# ---------------------------------------------------------------------------
# LLM transport doubles
# ---------------------------------------------------------------------------
_PLAN_DECLINE = {
    "use_tool": False,
    "service": None,
    "intent": "search",
    "query": "",
    "reason": ("served spreadsheet fixture: planner decline; the explicit "
               "formula ask is handled by the deterministic calculation lane"),
}


def _validated(response_model, payload):
    if response_model is None:
        return payload
    try:
        return response_model.model_validate(payload)
    except Exception:  # noqa: BLE001 — pydantic v1 / unrelated schema
        try:
            return response_model(**payload)
        except Exception:  # noqa: BLE001 — caller handles None
            return None


async def _fake_structured_response(
        self, prompt=None, response_model=None, system_instruction=None,
        **kwargs):
    name = getattr(response_model, "__name__", type(response_model).__name__)
    _trace("structured", response_model=str(name))
    if "RouteClassification" in str(name):
        return _validated(response_model, {
            "category": "one_off",
            "reasoning": "served spreadsheet fixture",
            "confidence": 1.0,
        })
    return _validated(response_model, dict(_PLAN_DECLINE))


def _calc_value_from_messages(messages) -> str | None:
    text = "\n".join(
        str((message or {}).get("content") or "")
        for message in (messages or []))
    match = re.search(
        r"computed_value=([-+]?\d[\d,]*(?:\.\d+)?)", text)
    if not match:
        match = re.search(
            r"Computed value \(neutral workbook arithmetic\):\s*"
            r"([-+]?\d[\d,]*(?:\.\d+)?)", text)
    return match.group(1) if match else None


def _narration(messages) -> str:
    value = _calc_value_from_messages(messages)
    if value:
        return f"The current total from the workbook is {value}."
    return "The workbook calculation did not produce a usable value."


def _completion_payload(messages) -> dict:
    content = _narration(messages)
    return {
        "success": True,
        "content": content,
        "text": content,
        "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                  "total_tokens": 2},
        "model": "served-spreadsheet-fixture",
        "provider": "fixture",
        "routing_result_id": None,
        "reasoning": None,
    }


async def _fake_completion(self, messages=None, **kwargs):
    _trace("completion",
           has_calc_value=_calc_value_from_messages(messages) is not None)
    return _completion_payload(messages)


async def _fake_stream(self, messages=None, **kwargs):
    content = _narration(messages)
    _trace("stream",
           has_calc_value=_calc_value_from_messages(messages) is not None)
    yield content


LLMService.generate_structured_response = _fake_structured_response
LLMService.generate_completion = _fake_completion
LLMService.stream_completion = _fake_stream
