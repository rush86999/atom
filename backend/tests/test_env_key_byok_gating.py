"""
AGPL self-hosted edition: env-configured API keys are BYOK.

The plan-gating logic in BYOKHandler must treat providers whose client was
built from a process-environment API key (e.g. OPENCODE_API_KEY in .env) as
bring-your-own-key, so free-tier model allow-lists never restrict a
self-hosted user's own key. These tests pin the tracking that powers that
gate (BYOKHandler.env_key_providers).
"""

import os
os.environ.setdefault("TESTING", "1")

import pytest

from core.llm.byok_handler import BYOKHandler


def _fresh_handler():
    # BYOKHandler resolves credentials per-instance; a fresh instance is the
    # same code path the server uses at startup.
    return BYOKHandler()


def test_env_key_provider_tracked(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-opencode-test-key")
    handler = _fresh_handler()
    assert "opencode-go" in handler.env_key_providers
    assert "opencode-go" in handler.clients


def test_no_env_key_not_tracked(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    handler = _fresh_handler()
    assert "opencode-go" not in handler.env_key_providers
    assert "opencode-go" not in handler.clients


def test_env_keys_byok_gate_flips(monkeypatch):
    """The AGPL BYOK gate: any env-sourced key present → not plan-managed."""
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-opencode-test-key")
    handler = _fresh_handler()
    # The gate in generate_completion checks truthiness of env_key_providers:
    # non-empty means the operator supplied their own key(s).
    assert bool(handler.env_key_providers) is True


def test_no_env_keys_gate_stays_managed(monkeypatch):
    for var in (
        "OPENCODE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "GOOGLE_API_KEY",
        "GLM_API_KEY",
        "MOONSHOT_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "MISTRAL_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    handler = _fresh_handler()
    assert bool(handler.env_key_providers) is False
