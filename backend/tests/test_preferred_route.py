"""Installation-level preferred LLM route: order, not bypass.

Owner correction 2 (2026-10-08): a hardcoded paid default with no
supported override is a product limitation. The preference
(ATOM_PREFERRED_LLM_PROVIDER / _MODEL, env or the cataloged
runtime-settings row) reorders the ranking ONLY when the pair passes
the same eligibility the ranking applies — client built, cooldowns,
catalog-served (or not known-unserved), capability compatible. Every
control is preserved; an ineligible preference leaves the ranking
unchanged with the precise reason recorded for the unavailable-route
error.
"""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("TESTING", "1")

from core.llm import byok_handler as bh
from core.llm.byok_handler import (
    BYOKHandler, NoProvidersConfiguredError, QueryComplexity,
)


def _handler(clients=("opencode-go", "openai"), serves=None,
             tools=True, cooldown=lambda p, m: False,
             provider_cooldown=lambda p: False):
    h = BYOKHandler.__new__(BYOKHandler)
    h.clients = {c: object() for c in clients}
    served = serves or (lambda p, m: True)
    h._provider_serves_model = served
    h._ranked_model_is_known_unserved = lambda p, m: not served(p, m)
    h._model_supports_tools = lambda m: tools
    h._model_cooldown_active = cooldown
    h._provider_cooldown_active = provider_cooldown
    return h


def _rank(h, **kw):
    with patch.object(BYOKHandler, "get_ranked_providers",
                      return_value=bh.AwaitableResult(
                          [("openai", "o4-mini")])):
        # call the reorder directly on the reconciled list — the seam
        # get_ranked_providers applies before returning
        return h._apply_preferred_route([("openai", "o4-mini")], **kw)


def test_eligible_preference_becomes_primary(monkeypatch):
    monkeypatch.setenv("ATOM_PREFERRED_LLM_PROVIDER", "opencode-go")
    monkeypatch.setenv("ATOM_PREFERRED_LLM_MODEL", "mimo-v2.6-flash-free")
    h = _handler()
    out = _rank(h)
    assert out[0] == ("opencode-go", "mimo-v2.6-flash-free")
    assert ("openai", "o4-mini") in out, "the rest of the ladder is kept"
    assert BYOKHandler._PREF_LAST_DIAGNOSIS == ""


def test_preference_inserted_even_when_outside_ranked_set(monkeypatch):
    """The free-tier model below BPC's quality floor is still an explicit
    operator choice — inserted as primary, other candidates untouched."""
    monkeypatch.setenv("ATOM_PREFERRED_LLM_PROVIDER", "opencode-go")
    monkeypatch.setenv("ATOM_PREFERRED_LLM_MODEL", "free-model")
    h = _handler()
    out = _rank(h)
    assert out == [("opencode-go", "free-model"), ("openai", "o4-mini")]


def test_ineligible_catalog_preference_ignored_with_reason(monkeypatch):
    monkeypatch.setenv("ATOM_PREFERRED_LLM_PROVIDER", "opencode-go")
    monkeypatch.setenv("ATOM_PREFERRED_LLM_MODEL", "gpt-4o-mini")
    h = _handler(serves=lambda p, m: m != "gpt-4o-mini")
    out = _rank(h)
    assert out == [("openai", "o4-mini")], "ineligible preference is a no-op"
    assert "not in provider" in BYOKHandler._PREF_LAST_DIAGNOSIS


def test_ineligible_capability_preference_ignored(monkeypatch):
    monkeypatch.setenv("ATOM_PREFERRED_LLM_PROVIDER", "opencode-go")
    monkeypatch.setenv("ATOM_PREFERRED_LLM_MODEL", "no-tools-model")
    h = _handler(tools=False)
    out = _rank(h, requires_tools=True)
    assert out == [("openai", "o4-mini")]
    assert "capability" in BYOKHandler._PREF_LAST_DIAGNOSIS


def test_cooldown_preference_ignored(monkeypatch):
    monkeypatch.setenv("ATOM_PREFERRED_LLM_PROVIDER", "opencode-go")
    monkeypatch.setenv("ATOM_PREFERRED_LLM_MODEL", "m")
    h = _handler(cooldown=lambda p, m: (p, m) == ("opencode-go", "m"))
    out = _rank(h)
    assert out == [("openai", "o4-mini")]
    assert "cooldown" in BYOKHandler._PREF_LAST_DIAGNOSIS


def test_no_provider_configured_carries_the_diagnosis(monkeypatch):
    monkeypatch.setenv("ATOM_PREFERRED_LLM_PROVIDER", "ghost")
    monkeypatch.setenv("ATOM_PREFERRED_LLM_MODEL", "m")
    h = _handler(serves=lambda p, m: False)  # no eligible route anywhere
    h._get_provider_fallback_order = lambda mode: ["opencode-go", "openai"]
    with patch.object(BYOKHandler, "get_ranked_providers",
                      return_value=bh.AwaitableResult([])):
        try:
            h.get_optimal_provider(QueryComplexity.SIMPLE)
        except NoProvidersConfiguredError as exc:
            assert "no client built" in str(exc), str(exc)
            assert "ghost" in str(exc)
        else:
            raise AssertionError("expected NoProvidersConfiguredError")


def test_unset_preference_is_a_noop(monkeypatch):
    monkeypatch.delenv("ATOM_PREFERRED_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ATOM_PREFERRED_LLM_MODEL", raising=False)
    h = _handler()
    assert _rank(h) == [("openai", "o4-mini")]
