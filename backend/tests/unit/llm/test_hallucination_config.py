"""Unit tests for core.hallucination_config (Phase 2 flag resolvers).

The resolver module is pure infrastructure with no behavior change of its
own — it just centralizes env-var-driven flag lookup so every mitigation
reads from the same source. This is the Personal / single-tenant edition:
no per-tenant override layer (that lives in the SaaS fork).
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip every ATOM_* mitigation env var so tests start from defaults."""
    for k in list(os.environ):
        if k.startswith("ATOM_") and (
            "VERIFIED" in k or "CASCADE" in k or "SELF_CONSISTENCY" in k
        ):
            monkeypatch.delenv(k, raising=False)


# ---------------------------------------------------------------------------
# Boolean toggles
# ---------------------------------------------------------------------------


def test_flags_default_off_when_no_env():
    from core import hallucination_config as hc

    assert hc.is_cascade_routing_enabled() is False
    assert hc.is_self_consistency_enabled() is False


def test_flags_pick_up_env_var(monkeypatch):
    from core import hallucination_config as hc

    monkeypatch.setenv("ATOM_CASCADE_ROUTING", "true")
    monkeypatch.setenv("ATOM_SELF_CONSISTENCY", "1")

    assert hc.is_cascade_routing_enabled() is True
    assert hc.is_self_consistency_enabled() is True


@pytest.mark.parametrize("val", ["false", "0", "no", "off", "", "garbage"])
def test_env_var_truthiness_rejects_non_affirmative(monkeypatch, val):
    from core import hallucination_config as hc

    monkeypatch.setenv("ATOM_CASCADE_ROUTING", val)
    assert hc.is_cascade_routing_enabled() is False


# ---------------------------------------------------------------------------
# Numeric tunables
# ---------------------------------------------------------------------------


def test_self_consistency_samples_default():
    from core import hallucination_config as hc

    assert hc.get_self_consistency_samples() == 3


def test_self_consistency_samples_env(monkeypatch):
    from core import hallucination_config as hc

    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_SAMPLES", "5")
    assert hc.get_self_consistency_samples() == 5


def test_self_consistency_samples_invalid_falls_back(monkeypatch):
    from core import hallucination_config as hc

    monkeypatch.setenv("ATOM_SELF_CONSISTENCY_SAMPLES", "garbage")
    assert hc.get_self_consistency_samples() == 3


# ---------------------------------------------------------------------------
# Temperature spread
# ---------------------------------------------------------------------------


def test_temperature_spread_has_n_values():
    from core import hallucination_config as hc

    out = hc.get_temperature_spread(3)
    assert len(out) == 3
    assert all(isinstance(t, float) for t in out)


def test_temperature_spread_three_symmetric():
    from core import hallucination_config as hc

    assert hc.get_temperature_spread(3) == [0.6, 0.7, 0.8]


def test_temperature_spread_single():
    from core import hallucination_config as hc

    assert hc.get_temperature_spread(1) == [0.7]


# ---------------------------------------------------------------------------
# Frontier model registry
# ---------------------------------------------------------------------------


def test_is_frontier_model_matches_known():
    from core import hallucination_config as hc

    assert hc.is_frontier_model("gpt-4o") is True
    assert hc.is_frontier_model("gpt-4-turbo") is True
    assert hc.is_frontier_model("claude-3-opus-20240229") is True
    assert hc.is_frontier_model("claude-3-5-sonnet") is True
    assert hc.is_frontier_model("deepseek-reasoner") is True


def test_is_frontier_model_rejects_non_frontier():
    from core import hallucination_config as hc

    assert hc.is_frontier_model("gpt-4o-mini") is False
    assert hc.is_frontier_model("claude-3-haiku-20240307") is False
    assert hc.is_frontier_model("deepseek-chat") is False
    assert hc.is_frontier_model("some-random-model") is False


def test_is_frontier_model_handles_none():
    from core import hallucination_config as hc

    assert hc.is_frontier_model(None) is False
    assert hc.is_frontier_model("") is False


def test_frontier_for_provider_returns_same_family_flagship():
    from core import hallucination_config as hc

    assert hc.get_frontier_model_for_provider("openai") == "gpt-4o"
    assert hc.get_frontier_model_for_provider("anthropic") == "claude-3-5-sonnet"
    assert hc.get_frontier_model_for_provider("deepseek") == "deepseek-reasoner"


def test_frontier_for_provider_unknown_returns_none():
    from core import hallucination_config as hc

    assert hc.get_frontier_model_for_provider("made-up") is None
    assert hc.get_frontier_model_for_provider(None) is None


def test_frontier_for_provider_handles_ollama_local():
    """Ollama is the local-LLM provider in Personal edition — escalate to
    the largest locally-runnable llama3 variant."""
    from core import hallucination_config as hc

    assert hc.get_frontier_model_for_provider("ollama") == "llama3:70b"
