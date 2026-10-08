"""Fresh-install absolute fallback: serve a model the provider serves.

Isolated clean-install verification (2026-10-08) found the absolute
fallback in get_optimal_provider hardcoding ``gpt-4o-mini`` onto the
first built client. On a keyless install that client is the LOCAL
provider (ollama), the catalog-served pair gate correctly rejects the
name, and every chat turn renders as "You need an AI provider" despite a
healthy local runtime. The fallback now prefers the provider's tier-map
default when the discovered catalogue serves it.
"""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("TESTING", "1")

from core.llm import byok_handler as bh
from core.llm.byok_handler import BYOKHandler, QueryComplexity


def _handler(clients, serves):
    handler = BYOKHandler.__new__(BYOKHandler)
    handler.clients = clients
    handler._provider_serves_model = lambda p, m: serves(p, m)
    return handler


def test_fallback_uses_tier_default_when_served():
    handler = _handler(
        {"ollama": object()},
        lambda p, m: (p, m) == ("ollama", "llama3.1:8b"))
    with patch.object(BYOKHandler, "get_ranked_providers",
                      return_value=bh.AwaitableResult([])):
        provider, model = handler.get_optimal_provider(
            QueryComplexity.SIMPLE)
    assert (provider, model) == ("ollama", "llama3.1:8b"), (
        "the absolute fallback must not hand the local provider a name "
        "its own catalogue rejects")


def test_fallback_keeps_legacy_name_when_nothing_better_serves():
    handler = _handler(
        {"openai": object()},
        lambda p, m: False)
    with patch.object(BYOKHandler, "get_ranked_providers",
                      return_value=bh.AwaitableResult([])):
        provider, model = handler.get_optimal_provider(
            QueryComplexity.SIMPLE)
    assert (provider, model) == ("openai", "gpt-4o-mini")
