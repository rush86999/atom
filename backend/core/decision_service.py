"""DecisionService — local Ollaya decision sidecar client (Phase 1).

Shadow-first, Atom-style contract (mirrors turn_fact_extractor + stage_router):
- NEVER raises. ``decide()`` catches everything → ``source="fallback"``.
- Flag-off (``ATOM_OLLAYA_ENABLED=false``, default) → ``source="disabled"``, no HTTP.
- Timeout / connection error / malformed wire → ``source="fallback"``.
- Circuit breaker: ``_BREAKER_THRESHOLD`` consecutive failures → ``source="breaker"``
  fast short-circuit for ``_BREAKER_COOLDOWN_S`` seconds. Never permanent.
- Stdlib only (urllib). Resolution via ``core.runtime_settings`` (env wins >
  DB row > default); unknown keys degrade to defaults, never raise.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flags (defaults mirror settings_catalog entries; runtime_settings wins)
# ---------------------------------------------------------------------------

_DEFAULT_URL = "http://127.0.0.1:11435"
_DEFAULT_MODEL = "laya"
_DEFAULT_TIMEOUT_S = 0.8

_BREAKER_THRESHOLD = 5
_BREAKER_COOLDOWN_S = 60.0

_failures = 0
_open_until = 0.0

_stats = {"ollaya_ok": 0, "fallback": 0, "breaker": 0, "disabled": 0}


def ollaya_enabled() -> bool:
    try:
        from core.runtime_settings import get_bool_setting
        return bool(get_bool_setting("ATOM_OLLAYA_ENABLED", False))
    except Exception:
        return False


def ollaya_url() -> str:
    try:
        from core.runtime_settings import get_setting
        return str(get_setting("ATOM_OLLAYA_URL", _DEFAULT_URL) or _DEFAULT_URL).rstrip("/")
    except Exception:
        return _DEFAULT_URL


def ollaya_model() -> str:
    try:
        from core.runtime_settings import get_setting
        return str(get_setting("ATOM_OLLAYA_MODEL", _DEFAULT_MODEL) or _DEFAULT_MODEL)
    except Exception:
        return _DEFAULT_MODEL


def ollaya_timeout_s() -> float:
    try:
        from core.runtime_settings import get_float_setting
        return float(get_float_setting("ATOM_OLLAYA_TIMEOUT_S", _DEFAULT_TIMEOUT_S))
    except Exception:
        return _DEFAULT_TIMEOUT_S


def reset_breaker() -> None:
    """Test/admin hook: clear breaker state."""
    global _failures, _open_until
    _failures = 0
    _open_until = 0.0


def _breaker_open() -> bool:
    return _open_until > time.monotonic()


def _record_success() -> None:
    global _failures, _open_until
    _failures = 0
    _open_until = 0.0
    _stats["ollaya_ok"] += 1


def _record_failure() -> str:
    """Returns 'breaker' if the threshold just tripped, else 'fallback'."""
    global _failures, _open_until
    _failures += 1
    _stats["fallback"] += 1
    if _failures >= _BREAKER_THRESHOLD:
        _open_until = time.monotonic() + _BREAKER_COOLDOWN_S
        _stats["breaker"] += 1
        return "breaker"
    return "fallback"


def _ollaya_bin() -> str:
    """Locate the ollaya CLI (installed to ~/.local/bin by install.sh)."""
    found = shutil.which("ollaya")
    if found:
        return found
    cand = os.path.expanduser("~/.local/bin/ollaya")
    return cand


def _run_cli_preset(model: str, preset: str, state, timeout: float) -> dict:
    """Resolve a preset via ``ollaya run --preset --format json``.

    Presets live in the CLI/MCP layer — the HTTP API requires explicit
    ``questions``. Returns a wire-compatible dict with an ``answers`` object.
    Raises on any failure (caller converts to fallback).
    """
    exe = _ollaya_bin()
    if isinstance(state, dict):
        state_arg = json.dumps(state)
    else:
        state_arg = str(state)
    proc = subprocess.run(
        [exe, "run", model, "--preset", preset, "--format", "json", state_arg],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ollaya run exited {proc.returncode}: {proc.stderr[:200]}")
    wire = json.loads(proc.stdout)
    if not isinstance(wire, dict):
        raise ValueError("CLI output is not an object")
    return wire


def _post_decide(payload: dict, timeout: float) -> dict:
    """Real HTTP POST to {url}/v1/systemone. Raises on any transport/parse error."""
    url = ollaya_url() + "/v1/systemone"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    wire = json.loads(raw)
    if not isinstance(wire, dict):
        raise ValueError("wire response is not an object")
    return wire


def _parse_answers(wire: dict) -> dict:
    """Validate /v1/systemone wire format. Raises ValueError on anything unexpected."""
    answers = wire.get("answers")
    if not isinstance(answers, dict) or not answers:
        raise ValueError("missing answers object")
    parsed: dict = {}
    for qid, ans in answers.items():
        if not isinstance(ans, dict):
            raise ValueError(f"answer {qid!r} is not an object")
        atype = ans.get("type")
        if atype == "choice":
            if "choice" not in ans or "confidence" not in ans:
                raise ValueError(f"choice {qid!r} missing fields")
            parsed[qid] = {
                "type": "choice",
                "choice": str(ans["choice"]),
                "confidence": float(ans["confidence"]),
                "probabilities": dict(ans.get("probabilities", {})),
            }
        elif atype == "noul":
            if "noul" not in ans:
                raise ValueError(f"noul {qid!r} missing fields")
            parsed[qid] = {"type": "noul", "noul": float(ans["noul"])}
        elif atype == "score":
            if "score" not in ans:
                raise ValueError(f"score {qid!r} missing fields")
            parsed[qid] = {
                "type": "score",
                "score": float(ans["score"]),
                "confidence": float(ans.get("confidence", 0.0)),
                "legend": dict(ans.get("legend", {})),
                "probabilities": dict(ans.get("probabilities", {})),
            }
        else:
            raise ValueError(f"answer {qid!r} has unknown type {atype!r}")
    return parsed


def decide(state, questions: dict | None = None, preset: str | None = None,
           model: str | None = None, timeout_s: float | None = None) -> dict:
    """Ask the local decision model. Never raises.

    ``timeout_s`` overrides the flag (None = flag value). Background callers
    (shadow audit) pass a generous budget — cold model load is ~5s on
    internal SSD; inline callers keep the tight default.

    Returns ``{"source": "ollaya"|"fallback"|"breaker"|"disabled",
    "answers": {...}, "model": str, "latency_ms": float}``.
    """
    started = time.monotonic()
    try:
        if not ollaya_enabled():
            _stats["disabled"] += 1
            return {"source": "disabled", "answers": {},
                    "model": model or ollaya_model(), "latency_ms": 0.0}
        if _breaker_open():
            _stats["breaker"] += 1
            return {"source": "breaker", "answers": {},
                    "model": model or ollaya_model(), "latency_ms": 0.0}
        chosen_model = model or ollaya_model()
        budget = timeout_s if timeout_s is not None else ollaya_timeout_s()
        if preset and not questions:
            # Presets live in the CLI/MCP layer; the HTTP API takes questions.
            # CLI timeout is generous: cold model load is ~5s on internal SSD.
            wire = _run_cli_preset(chosen_model, preset, state,
                                   max(budget, 90.0))
        else:
            if not questions:
                raise ValueError("decide() needs preset or questions")
            payload: dict = {"model": chosen_model, "state": state,
                             "questions": questions}
            wire = _post_decide(payload, budget)
        answers = _parse_answers(wire)
        _record_success()
        latency_ms = (time.monotonic() - started) * 1000.0
        return {"source": "ollaya", "answers": answers,
                "model": wire.get("model", chosen_model), "latency_ms": latency_ms}
    except Exception as exc:  # never raise: fallback is the contract
        logger.warning("[DecisionService] fallback (%s: %s)", type(exc).__name__, exc)
        try:
            source = _record_failure()
        except Exception:
            source = "fallback"
        latency_ms = (time.monotonic() - started) * 1000.0
        return {"source": source, "answers": {},
                "model": model or _DEFAULT_MODEL, "latency_ms": latency_ms}
