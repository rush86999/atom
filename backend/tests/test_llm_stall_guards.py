"""Stall guards for chat-path LLM routing (Sep 1, 2026 live incident).

A "try again" chat turn stalled ~2 minutes: BPC ranked a permanently dead
local Ollama model top by value (connection error → 60s breaker → re-ranked
top again next turn), and the routed reasoning model burned its whole
completion budget on hidden thinking — finish_reason='length' with
content=None — which the completion path recorded as a HEALTHY success and
handed None to the chat. These tests pin the three guards:

1. empty visible content is a FAILED attempt (never a silent None success),
2. plain completions carry an explicit completion cap so reasoning models
   keep budget for the actual answer,
3. repeated connection failures escalate the breaker cooldown (60s → 120s →
   … capped) so a dead provider is re-probed at most every few minutes,
   not every turn.
"""
import time

import pytest

from core.llm.byok_handler import (
    _DEFAULT_COMPLETION_MAX_TOKENS,
    _visible_content_missing,
)
from core.provider_health_monitor import ProviderHealthMonitor


# ─────────────────── empty visible content = failed attempt ───────────────────

def test_visible_content_missing_catches_dead_payloads():
    assert _visible_content_missing(None) is True          # reasoning ate the budget
    assert _visible_content_missing("") is True
    assert _visible_content_missing("   \n  ") is True
    assert _visible_content_missing("Hi Jacob, here's the draft…") is False
    assert _visible_content_missing({"unexpected": "shape"}) is False


def test_completion_cap_default_is_generous_and_overridable():
    import subprocess
    import sys

    assert isinstance(_DEFAULT_COMPLETION_MAX_TOKENS, int)
    assert _DEFAULT_COMPLETION_MAX_TOKENS >= 4000  # reasoning + answer must fit

    # The env override is read at import time — verify in a hermetic
    # subprocess so this test never reloads the shared module in-process
    # (a reload here corrupted module identity for later tests once).
    code = (
        "import os, sys; sys.path.insert(0, '.')"
        "; from core.llm.byok_handler import _DEFAULT_COMPLETION_MAX_TOKENS as t"
        "; print(t)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env={"ATOM_COMPLETION_MAX_TOKENS": "9000", "PATH": "/usr/bin:/bin"},
        cwd=".", timeout=60,
    )
    if out.returncode == 0:
        assert out.stdout.strip() == "9000"
    else:
        # Full-package import may need services unavailable in a bare env —
        # the default-path assertion above is the binding check.
        pytest.skip(f"subprocess import unavailable: {out.stderr[-120:]}")


# ─────────────────── escalating breaker cooldown ───────────────────

def _open_cooldown(monitor, provider):
    """Record one connection failure and return the cooldown the monitor
    chose (deadline minus now), or None when no breaker opened."""
    monitor.record_call(provider, success=False, latency_ms=5.0,
                        connection_failure=True)
    deadline = monitor._breaker_open_until.get(provider)
    if deadline is None:
        return None
    return deadline - time.monotonic()


def _expire_breaker(monitor, provider):
    """Simulate the cooldown elapsing — through the REAL half-open path:
    routing consults is_breaker_open(), which pops the expired entry and
    allows the (doomed) probe."""
    if provider in monitor._breaker_open_until:
        monitor._breaker_open_until[provider] = time.monotonic() - 0.01
        assert monitor.is_breaker_open(provider) is False


def test_first_connection_failure_opens_breaker_for_base_cooldown():
    m = ProviderHealthMonitor()
    cooldown = _open_cooldown(m, "ollama")
    assert cooldown is not None
    assert cooldown == pytest.approx(ProviderHealthMonitor.CONN_FAIL_BREAKER_COOLDOWN_SECONDS, abs=2)


def test_repeated_failures_double_cooldown_up_to_cap():
    m = ProviderHealthMonitor()
    provider = "ollama"
    seen = []
    for _ in range(6):
        _open_cooldown(m, provider)
        seen.append(m._breaker_open_until[provider] - time.monotonic())
        _expire_breaker(m, provider)  # half-open probe fails again → re-open
    assert seen[0] == pytest.approx(60, abs=2)
    assert seen[1] == pytest.approx(120, abs=2)
    assert seen[2] == pytest.approx(240, abs=2)
    assert seen[3] == pytest.approx(480, abs=2)
    # capped: never exceeds the max no matter how many cycles fail
    assert seen[4] == pytest.approx(600, abs=2)
    assert seen[5] == pytest.approx(600, abs=2)
    assert max(seen) <= ProviderHealthMonitor.CONN_FAIL_BREAKER_MAX_COOLDOWN_SECONDS + 2


def test_success_resets_streak_and_cooldown_escalation():
    m = ProviderHealthMonitor()
    provider = "flaky"
    _open_cooldown(m, provider)
    _expire_breaker(m, provider)
    # a real success clears the consecutive-failure streak
    m.record_call(provider, success=True, latency_ms=100.0)
    assert provider not in m._conn_fail_streak
    # the next failure starts the ladder from the BASE cooldown again
    cooldown = _open_cooldown(m, provider)
    assert cooldown == pytest.approx(60, abs=2)


def test_is_breaker_open_respects_deadline():
    m = ProviderHealthMonitor()
    m.record_call("dead", success=False, latency_ms=1.0, connection_failure=True)
    assert m.is_breaker_open("dead") is True
    _expire_breaker(m, "dead")
    assert m.is_breaker_open("dead") is False


def test_ordinary_failures_do_not_trip_breaker():
    m = ProviderHealthMonitor()
    for _ in range(5):
        m.record_call("ratelimited", success=False, latency_ms=10.0,
                      connection_failure=False)
    assert "ratelimited" not in m._breaker_open_until
    assert m.is_breaker_open("ratelimited") is False
