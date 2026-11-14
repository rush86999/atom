#!/usr/bin/env python3
"""Loopback-only model relay for the OPT-IN synthetic invoice replay.

Why this module exists
======================

The signed-in invoice driver (``scripts/acceptance/browser_invoice_partial_
evidence.py``) runs its default episode against the authored loopback
``provider_shim``: the sandboxed server can only reach the shim port, and the
shim serves scripted completions. That is the default and stays the default.

This module is the provider TRANSPORT for the opt-in replay lane. It sits on
loopback between the sandboxed server and an OpenAI-compatible upstream so the
provider call can be observed and bounded in ONE place:

* the server stays sandboxed (seatbelt) and sees only this relay's port;
* only one operation is forwarded (``chat/completions``); model catalog reads
  and every other path are answered locally;
* every physical call is RESERVED before it is dispatched -- call slot and
  worst-case spend -- so a cap cannot be exceeded by an in-flight request;
* the upstream is either a loopback synthetic endpoint or exactly ONE trusted
  live destination, ``https://opencode.ai/zen/v1``.

The credential seam
===================

A live upstream needs a credential, and this relay accepts it ONLY from its
own stdin (``--upstream-api-key-stdin``), supplied by the caller
(``run_isolated.launch_live_relay(upstream_api_key=...)``). The key is held in
memory for the lifetime of the process, is sent only as the upstream
``Authorization`` header, and is never written to the ledger, the log or a
child process argv. This module does not read the environment, ``.env`` or any
auth file; there is deliberately no fallback path that could discover one.

Guarantees for the live route
=============================

* fixed destination: any other https host, path, query or port is refused
  before dispatch; a loopback endpoint never receives the credential;
* one attempt per call -- no retries and no redirect following (a 3xx is
  returned as a 3xx and counted as one physical call);
* the existing call / spend caps are reserved before the socket is opened;
* the ledger records metadata only: model ids, usage counters, status,
  durations, byte counts and a response hash. Neither the prompt/completion
  content nor any credential/header is stored.

Endpoints
=========

``POST /v1/<run_token>/chat/completions``  the only data path (forwarded).
``GET  /v1/<run_token>/models``            catalog read, answered locally with
                                           exactly the pinned model.
``GET  /livez``                            readiness + redacted budget state.
``GET  /ledger``                           bounded per-call ledger.

Bounds (all enforced before dispatch)
=====================================

* ``--max-model-calls``: a call slot is taken under the lock BEFORE the
  upstream request is opened. Once the cap is reached the relay answers
  ``429`` and no socket is opened.
* ``--max-spend-usd``: the worst-case cost of the call is reserved before
  dispatch (request bytes priced as tokens -- bytes are an upper bound on
  tokens -- plus ``--max-output-tokens`` at the output price). A call that
  cannot fit the remaining budget is refused with ``402`` before dispatch.
  On completion the reservation is settled to measured ``usage``; when the
  upstream omits ``usage`` the reservation stays charged (``usage_unknown``),
  so spend can be over-estimated but never under-estimated.
* ``--max-output-tokens``: request ``max_tokens``/``max_completion_tokens``
  are clamped.
* ``--call-timeout-s`` / ``--max-wall-clock-s``: one attempt, no retries.

Every request is recorded in a bounded ledger keyed by sequence number. The
entry carries metadata only; request headers (including any inbound
authorization) and the prompt/completion content are never read into evidence
or written to the ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
import threading
import time
from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:  # pragma: no cover - import wiring
    sys.path.insert(0, str(BACKEND))

#: The ONLY pinned live route for this lane. The relay refuses any other model
#: identifier before dispatch, so a fallback model cannot quietly serve the
#: episode through this transport.
PIN_PROVIDER = "opencode-go"
PIN_MODEL = "deepseek-v4.1-flash"

#: Loopback hosts a synthetic upstream may use.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

#: The ONE fixed live destination. This is the product's existing opencode-go
#: adapter endpoint; no other external host is addressable by this relay.
TRUSTED_LIVE_UPSTREAM_BASE_URL = "https://opencode.ai/zen/v1"
TRUSTED_LIVE_HOST = "opencode.ai"

UPSTREAM_KIND_LOOPBACK = "synthetic_loopback"
UPSTREAM_KIND_LIVE = "trusted_live"

#: The sandboxed server receives THIS run-scoped placeholder as its provider
#: key, never an operator credential. ``launch_server`` refuses any injected
#: key that does not start with :data:`RELAY_DUMMY_KEY_PREFIX`, and the product
#: ignores keys shorter than 12 characters, hence the length here.
RELAY_DUMMY_KEY = "relay-local-not-a-secret"
RELAY_DUMMY_KEY_PREFIX = "relay-local-"


def validate_dummy_key(value: str) -> str:
    """Refuse anything that could be an operator credential.

    The live lane injects a placeholder into the sandbox; it never forwards a
    real key. Making that a *shape* check (not a promise) means a future caller
    cannot pass a provider's real env key here by accident.
    """
    text = str(value or "")
    if not text.startswith(RELAY_DUMMY_KEY_PREFIX):
        raise ValueError(
            "refusing to inject a provider key that is not a relay placeholder "
            f"(must start with {RELAY_DUMMY_KEY_PREFIX!r}); this harness never "
            "reads or forwards an operator credential")
    if len(text) < 16:
        raise ValueError("relay placeholder key is too short to be used")
    return text

MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_HEAD_CHARS = 240
MAX_LEDGER_ENTRIES = 200
MAX_LEDGER_FILE_BYTES = 1024 * 1024


class RelayRefusal(Exception):
    """A bounded request the relay served WITHOUT contacting the upstream."""

    def __init__(self, status: int, reason: str, detail: str = "") -> None:
        self.status = status
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def validate_upstream_base_url(url: str, *, allow_live: bool = False) -> str:
    """The single gate on where this relay will forward to.

    Two destinations exist, and neither is configurable by accident:
    a loopback ``http`` endpoint for synthetic evidence, and exactly
    ``https://opencode.ai/zen/v1`` for the opt-in live transport. ``allow_live``
    is the caller's explicit acknowledgement that a live destination is
    intended; without it the trusted URL is refused. Any other scheme, host,
    port, path, userinfo, query or fragment is refused, never rewritten.
    """
    text = str(url or "").strip()
    if not text:
        raise ValueError("upstream base url is required")
    parts = urlsplit(text)
    if parts.username or parts.password:
        raise ValueError("upstream base url must not carry userinfo")
    if parts.query or parts.fragment:
        raise ValueError(
            "upstream base url must not carry a query or fragment")
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"upstream base url has an invalid port: {exc}") from exc
    path = parts.path.rstrip("/")

    if parts.scheme == "https" and host == TRUSTED_LIVE_HOST:
        if port not in (None, 443):
            raise ValueError(
                "the trusted live destination must not name a port")
        if path != "/zen/v1":
            raise ValueError(
                "the live destination is fixed to "
                f"{TRUSTED_LIVE_UPSTREAM_BASE_URL}; got path {parts.path!r}")
        if not allow_live:
            raise ValueError(
                "the trusted live upstream requires an explicit caller-supplied "
                "credential seam (allow_live=True)")
        return TRUSTED_LIVE_UPSTREAM_BASE_URL

    if parts.scheme != "http":
        raise ValueError(
            "upstream must be a loopback synthetic endpoint "
            "(http://127.0.0.1:<port>/v1) or the fixed trusted live "
            f"destination {TRUSTED_LIVE_UPSTREAM_BASE_URL}; got scheme "
            f"{parts.scheme or '(none)'}")
    if host not in LOOPBACK_HOSTS:
        raise ValueError(
            f"upstream host {host!r} is not loopback. Only a loopback "
            f"synthetic endpoint or the fixed trusted live destination "
            f"{TRUSTED_LIVE_UPSTREAM_BASE_URL} is accepted.")
    if port is None:
        raise ValueError("upstream base url must name an explicit port")
    if not path:
        raise ValueError(
            "upstream base url must carry the API prefix, e.g. "
            "http://127.0.0.1:8123/v1")
    return text.rstrip("/")


def upstream_kind(url: str) -> str:
    """Return the relay's transport class for an already-validated URL."""
    validated = validate_upstream_base_url(url, allow_live=True)
    return (UPSTREAM_KIND_LIVE
            if validated == TRUSTED_LIVE_UPSTREAM_BASE_URL
            else UPSTREAM_KIND_LOOPBACK)


def is_trusted_live_upstream(url: str) -> bool:
    """True only for the exact fixed live destination (no parsing surprises)."""
    try:
        return upstream_kind(url) == UPSTREAM_KIND_LIVE
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Budget: reserve BEFORE dispatch, settle after
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RelayLimits:
    max_calls: int = 12
    max_spend_usd: float = 0.50
    max_output_tokens: int = 1200
    input_usd_per_1m: float = 0.30
    output_usd_per_1m: float = 1.20
    call_timeout_s: float = 60.0
    max_wall_clock_s: float = 1800.0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Reservation:
    seq: int
    worst_case_usd: float


class RelayState:
    """Thread-safe budget, ledger and refusal counters for one relay process."""

    def __init__(self, *, provider: str, model: str, run_token: str,
                 upstream_base_url: str, limits: RelayLimits,
                 ledger_path: Optional[Path] = None) -> None:
        self.provider = provider
        self.model = model
        self.run_token = run_token
        self.upstream_base_url = upstream_base_url
        self.upstream_kind = upstream_kind(upstream_base_url)
        self.limits = limits
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self._lock = threading.RLock()
        self._started = time.monotonic()
        self._deadline = self._started + max(0.0, float(limits.max_wall_clock_s))
        self.calls_started = 0
        self.calls_completed = 0
        self.reserved_usd = 0.0
        self.charged_usd = 0.0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usage_unknown_calls = 0
        self.models_probes = 0
        self.refusals: Dict[str, int] = {
            "call_cap": 0, "spend_cap": 0, "wall_clock": 0,
            "model_not_pinned": 0}
        self.entries: List[Dict[str, Any]] = []
        if self.ledger_path is not None:
            # Truncate once per relay process: append-only afterwards, so the
            # ledger is THIS run's evidence and a reused world cannot serve a
            # prior run's call history.
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            self.ledger_path.write_text("", encoding="utf-8")

    # -- budget ----------------------------------------------------------
    def reserve(self, prompt_bytes: int) -> Reservation:
        """Take a call slot and reserve its worst-case cost BEFORE dispatch."""
        with self._lock:
            if time.monotonic() >= self._deadline:
                self.refusals["wall_clock"] += 1
                raise RelayRefusal(
                    429, "wall_clock",
                    f"wall budget {self.limits.max_wall_clock_s}s exhausted")
            if self.calls_started >= self.limits.max_calls:
                self.refusals["call_cap"] += 1
                raise RelayRefusal(
                    429, "call_cap",
                    f"call cap {self.limits.max_calls} already reserved")
            worst_case = (
                max(0, int(prompt_bytes)) * self.limits.input_usd_per_1m
                + max(0, int(self.limits.max_output_tokens))
                * self.limits.output_usd_per_1m) / 1_000_000.0
            if (self.charged_usd + self.reserved_usd + worst_case
                    > self.limits.max_spend_usd + 1e-12):
                self.refusals["spend_cap"] += 1
                raise RelayRefusal(
                    402, "spend_cap",
                    "worst-case cost of this call does not fit the remaining "
                    f"budget (charged ${self.charged_usd:.6f}, reserved "
                    f"${self.reserved_usd:.6f}, cap ${self.limits.max_spend_usd:.6f})")
            self.calls_started += 1
            self.reserved_usd += worst_case
            return Reservation(seq=self.calls_started, worst_case_usd=worst_case)

    def settle(self, reservation: Reservation,
               usage: Mapping[str, Any]) -> Tuple[float, bool]:
        """Settle a dispatched call. Returns ``(cost_usd, usage_measured)``.

        When the upstream omits ``usage`` the reserved worst case stays charged:
        the relay must never claim a measured spend it did not observe, and a
        cap that can be under-estimated is not a cap.
        """
        with self._lock:
            self.reserved_usd = max(0.0, self.reserved_usd - reservation.worst_case_usd)
            prompt = usage.get("prompt_tokens") if isinstance(usage, Mapping) else None
            completion = (
                usage.get("completion_tokens")
                if isinstance(usage, Mapping) else None)
            measured = (
                isinstance(prompt, int) and not isinstance(prompt, bool)
                and prompt >= 0
                and isinstance(completion, int)
                and not isinstance(completion, bool) and completion >= 0)
            if measured:
                cost = (prompt * self.limits.input_usd_per_1m
                        + completion * self.limits.output_usd_per_1m) / 1_000_000.0
                self.input_tokens += int(prompt)
                self.output_tokens += int(completion)
            else:
                cost = reservation.worst_case_usd
                self.usage_unknown_calls += 1
            self.charged_usd += cost
            self.calls_completed += 1
            return cost, measured

    def note_models_probe(self) -> None:
        """Record a catalog read. Control-plane only: never a model call."""
        with self._lock:
            self.models_probes += 1

    def note_refusal(self, reason: str) -> None:
        """Record a request the relay refused WITHOUT dispatching it.

        A ``model_not_pinned`` refusal is the evidence that some other route
        was attempted through this transport (the product's unpinned fallback
        path); it must be visible instead of vanishing into a 400.
        """
        with self._lock:
            self.refusals[str(reason)] = self.refusals.get(str(reason), 0) + 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "provider": self.provider,
                "model": self.model,
                "upstream_base_url": self.upstream_base_url,
                "upstream_kind": self.upstream_kind,
                "live_upstream_enabled": (
                    self.upstream_kind == UPSTREAM_KIND_LIVE),
                "limits": self.limits.as_dict(),
                "calls_started": self.calls_started,
                "calls_completed": self.calls_completed,
                "models_probes": self.models_probes,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "usage_unknown_calls": self.usage_unknown_calls,
                "reserved_usd": round(self.reserved_usd, 9),
                "charged_usd": round(self.charged_usd, 9),
                "refusals": dict(self.refusals),
                "ledger_entries": len(self.entries),
            }

    # -- ledger ----------------------------------------------------------
    def record(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            if len(self.entries) >= MAX_LEDGER_ENTRIES:
                return
            self.entries.append(entry)
            path = self.ledger_path
            if path is None:
                return
            try:
                if path.stat().st_size >= MAX_LEDGER_FILE_BYTES:
                    return
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Upstream client (loopback synthetic or the one fixed trusted live route)
# ---------------------------------------------------------------------------

@dataclass
class UpstreamResult:
    status: int
    body: bytes
    error: str = ""


class HttpUpstream:
    """One-attempt POST to the configured OpenAI-compatible upstream.

    Deliberately minimal: no retries (an SDK retry is a new physical call and
    must be counted as one), no redirects, no proxy inheritance from the
    developer environment, and no credential discovery. A live destination
    receives ONLY the caller-supplied key, as the ``Authorization`` header;
    a loopback synthetic endpoint refuses a key outright.
    """

    def __init__(self, base_url: str, *, call_timeout_s: float = 60.0,
                 api_key: Optional[str] = None) -> None:
        self.base_url = validate_upstream_base_url(base_url, allow_live=True)
        self.upstream_kind = upstream_kind(self.base_url)
        if self.upstream_kind == UPSTREAM_KIND_LIVE:
            if not str(api_key or "").strip():
                raise ValueError(
                    "the trusted live destination requires a caller-supplied "
                    "credential")
            try:
                self._api_key = validate_credential(str(api_key))
            except ValueError as exc:
                raise ValueError(f"invalid caller-supplied credential: {exc}") from exc
        else:
            if api_key is not None:
                raise ValueError(
                    "refusing to send a credential to a loopback synthetic "
                    "upstream")
            self._api_key = None
        self.call_timeout_s = float(call_timeout_s)
        self._client = None

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _http(self):
        if self._client is None:
            import httpx

            self._client = httpx.Client(
                timeout=self.call_timeout_s,
                trust_env=False,
                follow_redirects=False,
            )
        return self._client

    def post_chat(self, payload: bytes) -> UpstreamResult:
        import httpx

        url = f"{self.base_url}/chat/completions"
        try:
            response = self._http().post(
                url, content=payload, headers=self._headers())
        except httpx.TimeoutException as exc:
            return UpstreamResult(504, b"", f"timeout: {exc}")
        except Exception as exc:  # noqa: BLE001 - transport failure is evidence
            return UpstreamResult(502, b"", f"{type(exc).__name__}: {exc}")
        return UpstreamResult(response.status_code, response.content)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001 - best effort
                pass
            self._client = None


# ---------------------------------------------------------------------------
# Redaction (transport errors only; content and headers are never recorded)
# ---------------------------------------------------------------------------

_FALLBACK_SECRET = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,})")


def _redact_text(text: str) -> Tuple[str, bool]:
    """Bound-and-redact a transport error. Returns ``(text, redacted)``."""
    head = str(text or "")[:MAX_RESPONSE_HEAD_CHARS]
    redacted = False
    try:
        from core.secrets_redactor import (  # local import: harness-only use
            check_for_secrets,
            redact_before_storage,
        )

        if check_for_secrets(head).get("has_secrets"):
            head = redact_before_storage(head)[:MAX_RESPONSE_HEAD_CHARS]
            redacted = True
    except Exception:  # noqa: BLE001 - redaction must not fail the call
        pass
    # Defense in depth: the product redactor's patterns do not cover every
    # credential-shaped string, and a relay ledger must never carry one.
    if _FALLBACK_SECRET.search(head):
        head = _FALLBACK_SECRET.sub("[REDACTED]", head)
        redacted = True
    return head, redacted


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------

def _json_response(handler: BaseHTTPRequestHandler, status: int,
                   payload: Mapping[str, Any]) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _error_body(kind: str, reason: str, detail: str = "") -> Dict[str, Any]:
    return {"error": {"type": kind, "reason": reason, "message": detail or reason}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # The relay's state is attached to the server instance, so tests can build
    # one in-process without a global.
    @property
    def relay(self) -> RelayState:
        return self.server.relay  # type: ignore[attr-defined]

    @property
    def upstream(self) -> HttpUpstream:
        return self.server.upstream  # type: ignore[attr-defined]

    # -- helpers ---------------------------------------------------------
    def _token_matches(self, path: str, suffix: str) -> bool:
        prefix = "/v1/"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return False
        token = path[len(prefix):len(path) - len(suffix)]
        return bool(token) and hmac.compare_digest(token, self.relay.run_token)

    def _read_body(self) -> Optional[bytes]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            _json_response(self, 400, _error_body("invalid_request", "bad_length"))
            return None
        if length <= 0:
            _json_response(self, 400, _error_body("invalid_request", "empty_body"))
            return None
        if length > MAX_REQUEST_BYTES:
            _json_response(self, 413, _error_body(
                "invalid_request", "body_too_large",
                f"request body exceeds {MAX_REQUEST_BYTES} bytes"))
            return None
        return self.rfile.read(length)

    # -- POST ------------------------------------------------------------
    def do_POST(self) -> None:
        path, _, _query = self.path.partition("?")
        if not self._token_matches(path, "/chat/completions"):
            _json_response(self, 404, _error_body("not_found", "unknown_path"))
            return
        raw = self._read_body()
        if raw is None:
            return
        try:
            body = json.loads(raw)
        except ValueError:
            _json_response(self, 400, _error_body("invalid_body", "not_json"))
            return
        if not isinstance(body, dict):
            _json_response(self, 400, _error_body("invalid_body", "not_object"))
            return
        if body.get("stream") is True:
            _json_response(self, 400, _error_body(
                "stream_unsupported", "stream_unsupported",
                "the relay forwards non-streaming chat completions only"))
            return
        model = str(body.get("model") or "")
        if model != self.relay.model:
            self.relay.note_refusal("model_not_pinned")
            _json_response(self, 400, _error_body(
                "model_not_pinned", "model_not_pinned",
                f"this relay is pinned to {self.relay.model!r}, got {model!r}"))
            return
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            _json_response(self, 400, _error_body(
                "invalid_body", "no_messages"))
            return

        # Clamp BEFORE reservation so the reserved worst case is the true one.
        limit = int(self.relay.limits.max_output_tokens)
        requested_max: Optional[int] = None
        clamped = False
        for field in ("max_tokens", "max_completion_tokens"):
            if field not in body:
                continue
            value = body.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                value = limit
                body[field] = limit
                clamped = True
            if requested_max is None:
                requested_max = int(value)
            if value > limit:
                body[field] = limit
                clamped = True
        if requested_max is None:
            body["max_tokens"] = limit
        payload = json.dumps(body).encode()

        started = time.monotonic()
        started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        try:
            reservation = self.relay.reserve(len(payload))
        except RelayRefusal as refusal:
            _json_response(self, refusal.status, _error_body(
                "budget_exhausted", refusal.reason, refusal.detail))
            return

        result = self.upstream.post_chat(payload)
        duration_ms = round((time.monotonic() - started) * 1000.0, 1)

        document: Dict[str, Any] = {}
        if result.body:
            try:
                parsed = json.loads(result.body)
                if isinstance(parsed, dict):
                    document = parsed
            except ValueError:
                document = {}

        usage = document.get("usage") if isinstance(document.get("usage"), dict) else {}
        cost, usage_measured = self.relay.settle(reservation, usage)
        finish_reason = None
        choices = document.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")
        upstream_error, _ = _redact_text(result.error) if result.error else ("", False)

        self.relay.record({
            "seq": reservation.seq,
            "started_at": started_at,
            "duration_ms": duration_ms,
            "operation": "chat.completions",
            "status": result.status,
            "requested_model": model,
            "served_model": document.get("model"),
            "finish_reason": finish_reason,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            } if usage_measured else None,
            "usage_unknown": not usage_measured,
            "settled_by": "usage" if usage_measured else "reservation",
            "request_bytes": len(payload),
            "requested_max_tokens": requested_max,
            "sent_max_tokens": body.get("max_tokens",
                                        body.get("max_completion_tokens")),
            "clamped": clamped,
            "reserved_usd": round(reservation.worst_case_usd, 9),
            "cost_usd": round(cost, 9),
            "response_bytes": len(result.body),
            "response_sha256": (
                hashlib.sha256(result.body).hexdigest() if result.body else None),
            "upstream_error": upstream_error or None,
        })

        if result.error:
            _json_response(self, result.status, _error_body(
                "upstream_unavailable",
                "timeout" if result.status == 504 else "transport_error",
                result.error))
            return
        self.send_response(result.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(result.body)))
        self.send_header("X-Atom-Relay-Seq", str(reservation.seq))
        self.end_headers()
        self.wfile.write(result.body)

    # -- GET -------------------------------------------------------------
    def do_GET(self) -> None:
        path, _, _query = self.path.partition("?")
        if path == "/livez":
            snapshot = self.relay.snapshot()
            _json_response(self, 200, {
                "ready": True,
                "provider": snapshot["provider"],
                "model": snapshot["model"],
                "upstream_base_url": snapshot["upstream_base_url"],
                "upstream_kind": snapshot["upstream_kind"],
                "live_upstream_enabled": snapshot["live_upstream_enabled"],
                "limits": snapshot["limits"],
                "budget": snapshot,
            })
            return
        if path == "/ledger":
            _json_response(self, 200, {
                "budget": self.relay.snapshot(),
                "entries": list(self.relay.entries),
            })
            return
        if self._token_matches(path, "/models"):
            self.relay.note_models_probe()
            _json_response(self, 200, {
                "object": "list",
                "data": [{"id": self.relay.model, "object": "model"}],
            })
            return
        _json_response(self, 404, _error_body("not_found", "unknown_path"))

    def log_message(self, *a) -> None:  # noqa: A003 - stdlib signature
        pass


def build_server(*, port: int, relay: RelayState,
                 upstream: HttpUpstream) -> ThreadingHTTPServer:
    """Bind a relay server on 127.0.0.1 ONLY (never a wildcard address)."""
    server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
    server.daemon_threads = True
    server.relay = relay  # type: ignore[attr-defined]
    server.upstream = upstream  # type: ignore[attr-defined]
    return server


def _credential_from_stdin() -> str:
    """Read the caller-supplied key from stdin. Never log or echo it."""
    raw = sys.stdin.readline()
    return validate_credential(str(raw or "").rstrip("\r\n"))


def validate_credential(value: str) -> str:
    """Validate the key's shape without recording or transforming its value."""
    key = str(value or "")
    if not key.strip():
        raise ValueError("no credential was supplied on stdin")
    if any(character.isspace() for character in key):
        raise ValueError("the supplied credential contains whitespace")
    if len(key) > 4096:
        raise ValueError("the supplied credential is unreasonably long")
    return key


def _limits_from_args(args: argparse.Namespace) -> RelayLimits:
    return RelayLimits(
        max_calls=args.max_model_calls,
        max_spend_usd=args.max_spend_usd,
        max_output_tokens=args.max_output_tokens,
        input_usd_per_1m=args.input_usd_per_1m,
        output_usd_per_1m=args.output_usd_per_1m,
        call_timeout_s=args.call_timeout_s,
        max_wall_clock_s=args.max_wall_clock_s,
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--run-token", required=True)
    ap.add_argument("--upstream-base-url", required=True)
    ap.add_argument(
        "--upstream-api-key-stdin", action="store_true",
        help="read the caller-supplied upstream credential from stdin; "
             "required for the trusted live destination and refused for a "
             "loopback synthetic endpoint")
    ap.add_argument("--model", default=PIN_MODEL)
    ap.add_argument("--provider", default=PIN_PROVIDER)
    ap.add_argument("--ledger", default="")
    ap.add_argument("--max-model-calls", type=int, default=12)
    ap.add_argument("--max-spend-usd", type=float, default=0.50)
    ap.add_argument("--max-output-tokens", type=int, default=1200)
    ap.add_argument("--input-usd-per-1m", type=float, required=True)
    ap.add_argument("--output-usd-per-1m", type=float, required=True)
    ap.add_argument("--call-timeout-s", type=float, default=60.0)
    ap.add_argument("--max-wall-clock-s", type=float, default=1800.0)
    args = ap.parse_args(argv)

    if args.model != PIN_MODEL:
        print(f"[relay] refusing model {args.model!r}: this lane is pinned to "
              f"{PIN_MODEL!r}", file=sys.stderr)
        return 2
    if args.provider != PIN_PROVIDER:
        print(f"[relay] refusing provider {args.provider!r}: this lane is "
              f"pinned to {PIN_PROVIDER!r}", file=sys.stderr)
        return 2
    try:
        upstream_url = validate_upstream_base_url(
            args.upstream_base_url, allow_live=True)
    except ValueError as exc:
        print(f"[relay] refusing upstream: {exc}", file=sys.stderr)
        return 2

    kind = upstream_kind(upstream_url)
    api_key: Optional[str] = None
    if args.upstream_api_key_stdin:
        try:
            api_key = _credential_from_stdin()
        except ValueError as exc:
            print(f"[relay] refusing credential: {exc}", file=sys.stderr)
            return 2
    if kind == UPSTREAM_KIND_LIVE and api_key is None:
        print("[relay] refusing the trusted live destination without a "
              "caller-supplied credential on stdin", file=sys.stderr)
        return 2
    if kind != UPSTREAM_KIND_LIVE and api_key is not None:
        print("[relay] refusing to send a credential to a loopback synthetic "
              "upstream", file=sys.stderr)
        return 2

    limits = _limits_from_args(args)
    relay = RelayState(
        provider=args.provider,
        model=args.model,
        run_token=args.run_token,
        upstream_base_url=upstream_url,
        limits=limits,
        ledger_path=Path(args.ledger) if args.ledger else None,
    )
    upstream = HttpUpstream(
        upstream_url, call_timeout_s=limits.call_timeout_s, api_key=api_key)
    server = build_server(port=args.port, relay=relay, upstream=upstream)
    print(f"[relay] {args.provider}/{args.model} on :{args.port} -> "
          f"{upstream_url} (kind={kind}, "
          f"calls<={limits.max_calls}, spend<=${limits.max_spend_usd}, "
          f"credential={'caller_stdin' if api_key else 'none'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - operator stop
        pass
    finally:
        upstream.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
