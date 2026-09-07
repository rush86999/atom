"""Regression: the WebhookBridge circuit-open fallback must accept the
dispatch contract's single argument.

Observed live Sep 5, 2026: with the external memory store disconnected,
webhook circuits opened and the breaker's on_open dispatch crashed with
"WebhookBridge._on_circuit_open_fallback() missing 1 required positional
argument: 'stats'" — the data-loss-prevention fallback never fired.
core/circuit_breaker.py:_disable_integration invokes callbacks as
callback(integration); the bridge's signature must match.
"""
import os
os.environ.setdefault("TESTING", "1")

import pytest

from api.routes.webhooks.webhook_bridge import WebhookBridge
from core.circuit_breaker import circuit_breaker


def test_fallback_is_registered_on_the_global_breaker():
    bridge = WebhookBridge()
    assert bridge._on_circuit_open_fallback in circuit_breaker._on_open_callbacks


@pytest.mark.asyncio
async def test_fallback_survives_breaker_dispatch_arity():
    """Dispatch passes ONE positional arg. The old (service, stats)
    signature raised TypeError here — this call reproduces that path."""
    bridge = WebhookBridge()
    # Un-scoped service key exits early — exercises the signature without
    # touching DB or sync services.
    await bridge._on_circuit_open_fallback("unscoped-service-key")


@pytest.mark.asyncio
async def test_breaker_dispatch_reaches_registered_fallback():
    """End-to-end through the breaker's own dispatch loop: a callback
    registered like the bridge's must be invoked without error."""
    received = []

    async def probe(integration):
        received.append(integration)

    circuit_breaker._on_open_callbacks.append(probe)
    try:
        await circuit_breaker._disable_integration("slack:tenant-x", None)
    finally:
        circuit_breaker._on_open_callbacks.remove(probe)
    assert received == ["slack:tenant-x"]
