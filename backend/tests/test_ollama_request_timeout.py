"""The local Ollama request budget is explicit and default-preserving.

The OpenAI SDK default (600s) is the only budget the Ollama client had, which
caps CPU inference over a larger record set. The knob must not change behaviour
for anyone who does not set it.
"""
from __future__ import annotations

import pytest

from core.llm.byok_handler import _ollama_request_timeout


def test_default_stays_at_the_sdk_budget(monkeypatch):
    monkeypatch.delenv("OLLAMA_REQUEST_TIMEOUT", raising=False)
    assert _ollama_request_timeout() == 600.0


def test_operator_can_declare_a_longer_local_budget(monkeypatch):
    monkeypatch.setenv("OLLAMA_REQUEST_TIMEOUT", "1800")
    assert _ollama_request_timeout() == 1800.0


def test_invalid_value_falls_back_instead_of_raising(monkeypatch):
    monkeypatch.setenv("OLLAMA_REQUEST_TIMEOUT", "not-a-number")
    assert _ollama_request_timeout() == 600.0
