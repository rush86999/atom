"""Served-process entry point for the chat-message actor-scope regression.

The regression launches the REAL FastAPI application under uvicorn and drives
the public signup/login/chat boundary (``backend/tests/
test_chat_message_actor_scope.py``). This module supplies only the model
transports the chat turn would otherwise reach for:

* ``LLMService`` completion/structured/stream calls are doubled with a
  deterministic text answer. The planner double declines tool use.
* ``EmbeddingService`` is doubled with a deterministic 384-dimension vector
  so background memory work never downloads/loads a local ONNX model.

Everything that defines the persisted evidence stays real: HTTP + JWT auth,
the module-level ``ChatOrchestrator`` singleton, the owned ``ChatSession``
row, the chat transcript writer, the keyed transport record, and SQLite.

Mid-turn control (test harness, never an authority input): a user message may
carry ``[[probe:<tag>]]``. The completion double parks that turn once,
announces itself by creating ``<control-dir>/<tag>.awaiting`` and waits for
``<control-dir>/<tag>.release``. The pytest process uses that window to
change real durable state (rebind/revoke/drop) before the writer runs, and to
prove two turns are simultaneously awaiting the model. The tag is test
plumbing only; it is never read by the product's scope resolution.

Before importing the app, install a loopback-only socket guard so a stray
provider/telemetry call fails instead of leaving the box.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import socket
import threading
import time
from pathlib import Path

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
                f"served chat-scope fixture denied non-loopback connect: "
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

from fastapi import Request as _FixtureRequest  # noqa: E402

from core.embedding_service import EmbeddingService  # noqa: E402
from core.llm_service import LLMService  # noqa: E402
from core.agent_integration_gateway import AgentIntegrationGateway  # noqa: E402

_TAG_RE = re.compile(r"\[\[probe:([A-Za-z0-9_.-]{1,80})\]\]")
_GATED: set = set()
_GATE_LOCK = threading.Lock()
_TRACE_LOCK = threading.Lock()

_CONTROL_DIR = Path(os.environ.get("SERVED_CHAT_CONTROL_DIR") or "/nonexistent")
_GATE_TIMEOUT_S = float(os.environ.get("SERVED_CHAT_GATE_TIMEOUT", "90"))


def _trace(record: dict) -> None:
    path = os.environ.get("SERVED_CHAT_TRACE")
    if not path:
        return
    with _TRACE_LOCK:
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
        except OSError:
            pass


def _latest_tag(messages) -> str | None:
    tag = None
    for message in messages or []:
        content = (message or {}).get("content")
        if not isinstance(content, str):
            continue
        for match in _TAG_RE.finditer(content):
            tag = match.group(1)
    return tag


async def _control_gate(tag: str | None) -> None:
    if not tag:
        return
    with _GATE_LOCK:
        if tag in _GATED:
            return
        _GATED.add(tag)
    try:
        _CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        from integrations import chat_routes

        orchestrator = chat_routes.chat_orchestrator
        _trace({
            "tag": tag,
            "orchestrator_id": id(orchestrator),
            "orchestrator_tenant": getattr(orchestrator, "tenant_id", None),
            "orchestrator_type": type(orchestrator).__name__,
        })
        (_CONTROL_DIR / f"{tag}.awaiting").write_text("1", encoding="utf-8")
        deadline = time.monotonic() + _GATE_TIMEOUT_S
        while not (_CONTROL_DIR / f"{tag}.release").exists():
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"served chat-scope gate {tag!r} was never released")
            await asyncio.sleep(0.02)
    except Exception as exc:  # noqa: BLE001 — never swallow as a false pass
        _trace({"tag": tag, "gate_error": repr(exc)})
        raise


# ---------------------------------------------------------------------------
# Deterministic embedding double
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
    "reason": "served chat-scope fixture: planner decline",
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


def _answer(tag: str | None) -> str:
    return f"actor-scope-answer:{tag or 'none'}"


async def _fake_structured_response(
        self, prompt=None, response_model=None, system_instruction=None,
        **kwargs):
    name = getattr(response_model, "__name__", type(response_model).__name__)
    if "RouteClassification" in str(name):
        return _validated(response_model, {
            "category": "one_off",
            "reasoning": "served chat-scope fixture",
            "confidence": 1.0,
        })
    return _validated(response_model, dict(_PLAN_DECLINE))


async def _fake_generate_completion(self, messages=None, **kwargs):
    tag = _latest_tag(messages)
    await _control_gate(tag)
    content = _answer(tag)
    return {
        "success": True,
        "content": content,
        "text": content,
        "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                  "total_tokens": 2},
        "model": "served-chat-scope-fixture",
        "provider": "fixture",
        "routing_result_id": None,
        "reasoning": None,
    }


async def _fake_generate(self, prompt=None, **kwargs):
    tag = _latest_tag([{"role": "user", "content": str(prompt or "")}])
    await _control_gate(tag)
    content = _answer(tag)
    return {
        "success": True,
        "content": content,
        "text": content,
        "model": "served-chat-scope-fixture",
        "provider": "fixture",
    }


def _fake_stream_completion(self, *args, **kwargs):
    messages = kwargs.get("messages") or []
    tag = _latest_tag(messages)

    async def _agen():
        await _control_gate(tag)
        yield {"type": "content", "content": _answer(tag)}

    return _agen()


LLMService.generate_completion = _fake_generate_completion
LLMService.generate = _fake_generate
LLMService.generate_structured_response = _fake_structured_response
LLMService.stream_completion = _fake_stream_completion


# ---------------------------------------------------------------------------
# External-platform bridge transport double
# ---------------------------------------------------------------------------
# The universal bridge answers the platform back after the chat turn. That
# outbound leg is a transport, not durable authority: double it so the served
# world never reaches a real integration connector. The bridge's INBOUND path
# (declared external identity -> ChatOrchestrator -> real transcript writer)
# stays real, which is what the external-writer control exercises.
async def _fake_gateway_execute_action(self, action_type, platform, params):
    return {"status": "fixture_sent", "platform": platform}


AgentIntegrationGateway.execute_action = _fake_gateway_execute_action


@app.post("/__fixture/external-bridge-turn")
async def _fixture_external_bridge_turn(request: _FixtureRequest):
    """Drive the REAL universal webhook bridge inbound path once.

    Test plumbing only: a served process has no platform webhook to call, so
    this endpoint hands the real bridge a standardized ``agent`` message. No
    auth, authority, session or transcript code is substituted.
    """
    payload = await request.json()
    from integrations.universal_webhook_bridge import UniversalWebhookBridge

    bridge = UniversalWebhookBridge()
    result = await bridge.process_incoming_message("agent", {
        "agent_id": payload.get("sender_id") or "fixture-sender",
        "target_id": payload.get("recipient_id") or "fixture-bot",
        "message": payload.get("message") or "external bridge turn",
        "metadata": {"id": "served-chat-scope-fixture"},
    })
    return {
        "status": result.get("status"),
        "orchestrator_response": result.get("orchestrator_response"),
    }
