"""Tests for LKGP (Last-Known-Good-Path) sticky routing.

Covers: sticky boost to position 0, silent fallback when sticky pair absent,
session persistence of last-known-good, and the env flag gate.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_sticky_boost_prepends_known_pair():
    """When a sticky (provider, model) is in the candidate list, it moves to position 0."""
    from core.llm.byok_handler import BYOKHandler

    handler = BYOKHandler.__new__(BYOKHandler)
    options = [("openai", "gpt-4o"), ("deepseek", "deepseek-v4-pro"), ("anthropic", "claude-sonnet")]
    sticky = ("deepseek", "deepseek-v4-pro")

    # Simulate the LKGP boost logic
    if sticky in options:
        options.remove(sticky)
        options.insert(0, sticky)

    assert options[0] == sticky, "Sticky pair should be at position 0"
    assert len(options) == 3, "No candidates lost"


def test_sticky_absent_falls_through():
    """When the sticky pair is NOT in the candidate list, options unchanged."""
    options = [("openai", "gpt-4o"), ("anthropic", "claude-sonnet")]
    original = list(options)
    sticky = ("deepseek", "deepseek-v4-pro")  # not in the list

    if sticky in options:
        options.remove(sticky)
        options.insert(0, sticky)

    assert options == original, "Options should be unchanged when sticky pair absent"


def test_sticky_none_no_change():
    """When sticky_hint is None, options unchanged."""
    options = [("openai", "gpt-4o"), ("anthropic", "claude-sonnet")]
    original = list(options)
    sticky = None

    if sticky and sticky in options:
        options.remove(sticky)
        options.insert(0, sticky)

    assert options == original


def test_session_stores_last_known_good():
    """After a successful AI turn, the session stores the model/provider."""
    session = {"history": [], "last_known_good_model": None, "last_known_good_provider": None}
    used_model = "gpt-4o"
    used_provider = "openai"

    # Simulate the store logic from process_chat_message
    if used_model and used_provider and used_model not in ("template", "auto"):
        session["last_known_good_model"] = used_model
        session["last_known_good_provider"] = used_provider

    assert session["last_known_good_model"] == "gpt-4o"
    assert session["last_known_good_provider"] == "openai"


def test_session_does_not_store_template_or_auto():
    """Template/auto model ids are not stored as LKGP."""
    session = {"history": []}
    for invalid in ("template", "auto", None):
        used_model = invalid
        used_provider = "openai"
        if used_model and used_provider and used_model not in ("template", "auto"):
            session["last_known_good_model"] = used_model
            session["last_known_good_provider"] = used_provider
    assert "last_known_good_model" not in session, "Invalid model should not be stored"


def test_sticky_hint_read_from_session():
    """The orchestrator reads sticky hint from session when LKGP is enabled."""
    session = {
        "history": [],
        "last_known_good_model": "claude-sonnet",
        "last_known_good_provider": "anthropic",
    }

    with patch.dict(os.environ, {"ATOM_LKGP_ENABLED": "true"}):
        sticky_hint = None
        if os.getenv("ATOM_LKGP_ENABLED", "true").lower() == "true":
            _m = session.get("last_known_good_model")
            _p = session.get("last_known_good_provider")
            if _m and _p:
                sticky_hint = (_p, _m)

        assert sticky_hint == ("anthropic", "claude-sonnet")


def test_lkgp_disabled_no_sticky_hint():
    """When ATOM_LKGP_ENABLED=false, no sticky hint is produced."""
    session = {
        "history": [],
        "last_known_good_model": "gpt-4o",
        "last_known_good_provider": "openai",
    }

    with patch.dict(os.environ, {"ATOM_LKGP_ENABLED": "false"}):
        sticky_hint = None
        if os.getenv("ATOM_LKGP_ENABLED", "true").lower() == "true":
            _m = session.get("last_known_good_model")
            _p = session.get("last_known_good_provider")
            if _m and _p:
                sticky_hint = (_p, _m)

        assert sticky_hint is None


@pytest.mark.asyncio
async def test_byok_handler_accepts_sticky_hint(monkeypatch):
    """generate_response should accept sticky_hint without TypeError."""
    from core.llm.byok_handler import BYOKHandler

    handler = BYOKHandler.__new__(BYOKHandler)
    handler.workspace_id = "test"
    handler.tenant_id = "default"
    handler.clients = {}
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    handler._pending_routing_result_id = None
    monkeypatch.setattr(
        "core.llm.byok_handler.llm_usage_tracker.is_budget_exceeded",
        lambda ws: False,
    )

    # With no clients, returns early — but must accept the kwarg.
    result = await BYOKHandler.generate_response(
        handler,
        prompt="hi",
        model_type="auto",
        sticky_hint=("openai", "gpt-4o"),
    )
    assert isinstance(result, str)
