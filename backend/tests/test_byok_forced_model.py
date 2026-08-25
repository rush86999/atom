"""
ATOM_FORCED_LLM_MODEL override tests.

The BPC ranker only considers its benchmark/pricing candidate list, so a
free-usage opencode model (e.g. nemotron-3-ultra-free) is never tried even
when the operator wants it. This env pin lets an operator force one
(provider, model) pair and skip BPC entirely:

    ATOM_FORCED_LLM_MODEL=nemotron-3-ultra-free   -> opencode-go
    ATOM_FORCED_LLM_MODEL=openai:gpt-4o-mini      -> explicit provider
"""

import pytest
from unittest.mock import MagicMock, patch

import core.llm.byok_handler as bh
from core.llm.byok_handler import BYOKHandler, _forced_model_override


def test_forced_override_none_when_unset(monkeypatch):
    monkeypatch.delenv("ATOM_FORCED_LLM_MODEL", raising=False)
    assert _forced_model_override() is None


def test_forced_override_parses_plain_model(monkeypatch):
    monkeypatch.setenv("ATOM_FORCED_LLM_MODEL", "nemotron-3-ultra-free")
    assert _forced_model_override() == ("opencode-go", "nemotron-3-ultra-free")


def test_forced_override_parses_provider_model(monkeypatch):
    monkeypatch.setenv("ATOM_FORCED_LLM_MODEL", "openai:gpt-4o-mini")
    assert _forced_model_override() == ("openai", "gpt-4o-mini")


def test_forced_override_trims_whitespace(monkeypatch):
    monkeypatch.setenv("ATOM_FORCED_LLM_MODEL", "  openai :  gpt-4o-mini  ")
    assert _forced_model_override() == ("openai", "gpt-4o-mini")


def _bare_handler(clients):
    handler = object.__new__(BYOKHandler)  # skip __init__ (DB/pricing side effects)
    handler.clients = clients
    return handler


def test_ranked_forced_skips_bpc_when_configured(monkeypatch):
    monkeypatch.setenv("ATOM_FORCED_LLM_MODEL", "nemotron-3-ultra-free")
    handler = _bare_handler({"opencode-go": MagicMock()})
    with patch.object(
        bh, "get_pricing_fetcher_initialized_sync",
        side_effect=AssertionError("BPC must not run when a model is forced"),
    ):
        options = handler.get_ranked_providers(complexity=bh.QueryComplexity.COMPLEX)
    assert options == [("opencode-go", "nemotron-3-ultra-free")]


def test_ranked_forced_ignored_when_provider_missing(monkeypatch):
    monkeypatch.setenv("ATOM_FORCED_LLM_MODEL", "openai:gpt-4o-mini")
    handler = _bare_handler({"opencode-go": MagicMock()})
    with patch.object(bh, "get_pricing_fetcher_initialized_sync") as mock_fetcher:
        mock_fetcher.return_value = MagicMock()
        options = handler.get_ranked_providers(complexity=bh.QueryComplexity.SIMPLE)
    # Falls through to BPC; the forced pair must NOT appear.
    assert ("openai", "gpt-4o-mini") not in options
