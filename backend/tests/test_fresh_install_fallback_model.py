"""Fresh-install absolute fallback: an eligible pair, or an honest refusal.

Isolated clean-install verification (2026-10-08) found the absolute
fallback in get_optimal_provider hardcoding ``gpt-4o-mini`` onto the
first built client; the first repair kept a final ``gpt-4o-mini``
return when no candidate passed the catalog check — recreating the
unsupported-pair problem (owner correction 2026-10-08). The finished
shape walks the CONFIGURED providers through the existing eligibility
mechanisms and raises an accurately classified unavailable-route error
when nothing qualifies.
"""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("TESTING", "1")

from core.llm import byok_handler as bh
from core.llm.byok_handler import (
    BYOKHandler, NoProvidersConfiguredError, QueryComplexity,
)


def _handler(clients, serves, cooldown=lambda p, m: False,
             provider_cooldown=lambda p: False, order=None):
    handler = BYOKHandler.__new__(BYOKHandler)
    handler.clients = clients
    handler._provider_serves_model = serves
    handler._ranked_model_is_known_unserved = (
        lambda p, m: not serves(p, m))
    handler._model_cooldown_active = cooldown
    handler._provider_cooldown_active = provider_cooldown
    handler._get_provider_fallback_order = (
        lambda mode: order or list(clients.keys()))
    return handler


def _run(handler):
    with patch.object(BYOKHandler, "get_ranked_providers",
                      return_value=bh.AwaitableResult([])):
        return handler.get_optimal_provider(QueryComplexity.SIMPLE)


def test_tier_default_served_is_chosen():
    handler = _handler(
        {"ollama": object()},
        lambda p, m: (p, m) == ("ollama", "llama3.1:8b"))
    assert _run(handler) == ("ollama", "llama3.1:8b")


def test_unsupported_tier_default_is_refused_not_swapped():
    """A provider whose catalogue POSITIVELY excludes its own tier
    default yields the unavailable-route error — never the legacy
    gpt-4o-mini pair the dispatch loop would reject again."""
    handler = _handler(
        {"ollama": object()}, lambda p, m: False)
    try:
        _run(handler)
    except NoProvidersConfiguredError as exc:
        assert "not served" in str(exc)
    else:
        raise AssertionError(
            "no eligible pair must raise NoProvidersConfiguredError, "
            "not return an unsupported pair")


def test_unsupported_first_provider_falls_to_usable_second():
    handler = _handler(
        {"ollama": object(), "openai": object()},
        lambda p, m: (p, m) == ("openai", "o4-mini"))
    assert _run(handler) == ("openai", "o4-mini"), (
        "the fallback walks ALL configured providers, not just the "
        "first client")


def test_cooldown_pairs_are_not_bypassed():
    handler = _handler(
        {"ollama": object()},
        lambda p, m: (p, m) == ("ollama", "llama3.1:8b"),
        cooldown=lambda p, m: (p, m) == ("ollama", "llama3.1:8b"))
    try:
        _run(handler)
    except NoProvidersConfiguredError:
        pass
    else:
        raise AssertionError("a model-cooldown pair must not be selected")


def test_provider_cooldown_skips_to_next_provider():
    handler = _handler(
        {"ollama": object(), "openai": object()},
        lambda p, m: (p, m) in (("ollama", "llama3.1:8b"),
                                ("openai", "o4-mini")),
        provider_cooldown=lambda p: p == "ollama")
    assert _run(handler) == ("openai", "o4-mini")


def test_unknown_catalog_still_serves_tier_default():
    """A provider whose discovery NEVER SUCCEEDED is not vetoed (the
    same convention the structured cascade's gate documents) — an
    environment without a successful catalogue keeps its fallback."""
    handler = BYOKHandler.__new__(BYOKHandler)
    handler.clients = {"custom-gw": object()}
    handler._provider_serves_model = lambda p, m: False
    # positively-unserved check also False => unknown, not excluded
    handler._ranked_model_is_known_unserved = lambda p, m: False
    handler._model_cooldown_active = lambda p, m: False
    handler._provider_cooldown_active = lambda p: False
    handler._get_provider_fallback_order = lambda mode: ["custom-gw"]
    tier = (bh.COST_EFFICIENT_MODELS.get("custom-gw") or {}).get(
        QueryComplexity.SIMPLE)
    if tier:  # only meaningful for providers with a tier default
        assert _run(handler) == ("custom-gw", tier)
