"""Mini-app guest protocol — transport-agnostic exchange core.

The mini-app guest agent (``firecracker_guest/agent.py``) speaks one JSON-line
protocol regardless of how the host reaches it:

  * Host sends ``{"type":"exec", "code", "inputs"}``.
  * Guest may send 0..N ``{"type":"callback","kind":"fetch_integration",
    "service","action","params"}`` lines mid-run; the host services each via
    the caller's ``callback_handler`` (credentials resolved host-side, never
    in the guest) and answers ``{"type":"callback_result", "ok", "data"|"error"}``.
  * Guest sends one terminal line tagged ``"type":"final"`` (or, for older
    agents, an untagged line treated as final) carrying
    ``{"stdout","stderr","exit_code","state_envelope"?}``.

Two transports exist, both ``asyncio`` ``StreamReader``/``StreamWriter`` pairs,
so the exchange logic lives here ONCE:

  * ``FirecrackerRuntime`` — vsock UDS opened with
    ``asyncio.open_unix_connection`` (the microVM command channel).
  * ``MiniAppDevRuntime`` — the container process's stdin/stdout pipes
    (``docker run -i``, DEV-ONLY local execution).

Moved verbatim from ``FirecrackerRuntime._exchange``/``._service_callback``
when the docker-dev transport arrived, so both runners exercise identical
callback servicing and terminal-reply parsing.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Output cap per stream (mirrors the Docker/E2B runners).
OUTPUT_CAP = 65536  # 64 KiB


async def exchange(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    code: str,
    inputs: Dict[str, Any],
    callback_handler: Any = None,
) -> Tuple[str, str, int, Optional[dict], List[dict]]:
    """Send exec, service callbacks, read the final reply.

    Returns ``(stdout, stderr, exit_code, envelope, callbacks)``. ``envelope``
    is the guest's ``state_envelope`` dict (or None). Callback time counts
    against the CALLER's deadline — this coroutine owns no timeout of its own;
    wrap it in ``asyncio.wait_for``.
    """
    callbacks: List[dict] = []
    payload = json.dumps({"type": "exec", "code": code, "inputs": inputs})
    writer.write((payload + "\n").encode("utf-8"))
    await writer.drain()

    # Service the guest's lines until a terminal/final reply arrives.
    while True:
        line = await reader.readline()
        if not line:
            raise asyncio.TimeoutError("guest agent returned no response")
        data = json.loads(line.decode("utf-8"))
        msg_type = data.get("type")

        if msg_type == "callback":
            reply, log_entry = await service_callback(data, callback_handler)
            callbacks.append(log_entry)
            writer.write((json.dumps(reply) + "\n").encode("utf-8"))
            await writer.drain()
            continue

        # Terminal (msg_type == "final") OR untagged legacy reply.
        stdout = str(data.get("stdout", ""))
        stderr = str(data.get("stderr", ""))
        exit_code = int(data.get("exit_code", -1))
        envelope = data.get("state_envelope")
        if not isinstance(envelope, dict):
            envelope = None
        return (stdout, stderr, exit_code, envelope, callbacks)


async def service_callback(
    request: Dict[str, Any], callback_handler: Any
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Dispatch one guest callback request; return (reply_dict, log_entry).

    When no handler is configured (legacy run / Docker runtime), every
    callback fails with ``callbacks_disabled`` so user code sees a clear
    error instead of hanging.
    """
    kind = request.get("kind") or "unknown"
    cb_start = time.time()
    if callback_handler is None:
        reply = {"type": "callback_result", "ok": False, "error": "callbacks_disabled"}
        log_entry = {"kind": kind, "ok": False, "error": "callbacks_disabled",
                     "duration_ms": int((time.time() - cb_start) * 1000)}
        return reply, log_entry
    try:
        result = await callback_handler(request)
        reply = {"type": "callback_result", "ok": bool(result.get("ok", True)),
                 "data": result.get("data")}
        if not reply["ok"]:
            reply["error"] = result.get("error", "failed")
        log_entry = {
            "kind": kind,
            "service": request.get("service"),
            "action": request.get("action"),
            "ok": reply["ok"],
            "duration_ms": int((time.time() - cb_start) * 1000),
        }
        return reply, log_entry
    except Exception as e:  # noqa: BLE001
        logger.warning("callback %s failed: %s", kind, e)
        reply = {"type": "callback_result", "ok": False, "error": "failed"}
        log_entry = {"kind": kind, "ok": False, "error": "failed",
                     "duration_ms": int((time.time() - cb_start) * 1000)}
        return reply, log_entry
