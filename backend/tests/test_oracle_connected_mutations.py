"""Postcondition oracle coverage for every registered mutating action."""
from __future__ import annotations

import asyncio

import pytest

from core.action_registry import action_registry
from core.oracle import _VERIFIERS, validate
import core.connected_actions  # noqa: F401 - registers provider actions
import core.oracle.postcondition_verifiers  # noqa: F401 - registers checks


def _mutating_actions():
    names = []
    for name in action_registry.list_actions():
        action = action_registry.get_action(name)
        effects = getattr(action, "effects", None) or []
        for effect in effects:
            kind = effect.get("effect") if isinstance(effect, dict) else effect
            if str(kind).lower() in {
                    "create", "update", "delete", "write", "send"}:
                names.append(name)
                break
    return names


def test_every_connected_mutating_action_has_a_postcondition_verifier():
    mutating = _mutating_actions()
    assert mutating, "no mutating actions registered"
    missing = [name for name in mutating if name not in _VERIFIERS]
    assert missing == [], missing


def test_connected_readback_receipt_is_required_for_verification():
    good = {
        "action_result": "applied",
        "remote_id": "est-1",
        "payload_sha256": "a" * 64,
        "read_receipt": {
            "resource_id": "est-1", "coverage": "single",
            "fields": {"estimate_id": "est-1"},
        },
        "verification": {"status": "verified"},
        "provider_receipt": {"payload_sha256": "a" * 64},
    }
    result = asyncio.run(validate(
        "connected.books.create_estimate", good))
    assert result is not None and result.verified is True

    refused = dict(good)
    refused["action_result"] = "uncertain"
    result = asyncio.run(validate(
        "connected.books.create_estimate", refused))
    assert result is not None and result.verified is False

    mismatched = dict(good)
    mismatched["read_receipt"] = {
        "resource_id": "other", "coverage": "single", "fields": {}}
    result = asyncio.run(validate(
        "connected.books.create_estimate", mismatched))
    assert result is not None and result.verified is False

    incomplete = dict(good)
    incomplete["verification"] = {"status": "incomplete"}
    result = asyncio.run(validate(
        "connected.books.create_estimate", incomplete))
    assert result is not None and result.verified is False

    no_digest = {key: value for key, value in good.items()
                 if key not in {"payload_sha256", "provider_receipt"}}
    result = asyncio.run(validate(
        "connected.books.create_estimate", no_digest))
    assert result is not None and result.verified is False
