"""Explicit grounding verdict: missing/contradictory decisions are unavailable."""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("TESTING", "1")

import pytest

from core.verify_panel import VerifyVerdict, verify_reply


@pytest.mark.parametrize("raw", [
    "{}",
    '{"grounded": null}',
    '{"grounded": "true"}',
    '{"grounded": 1}',
    '{"grounded": true, "unsupported_claims": ["Unsupported profit USD999"]}',
])
def test_invalid_verdicts_fail_validation(raw):
    with pytest.raises(Exception):
        VerifyVerdict.model_validate_json(raw)


def test_explicit_truth_and_falsehood_remain_valid():
    assert VerifyVerdict.model_validate_json(
        '{"grounded": true, "unsupported_claims": []}').grounded is True
    false = VerifyVerdict.model_validate_json(
        '{"grounded": false, "unsupported_claims": ["x"]}')
    assert false.grounded is False and false.unsupported_claims == ["x"]


def test_schema_requires_strict_boolean_grounded():
    schema = VerifyVerdict.model_json_schema()
    assert "grounded" in schema["required"]
    assert schema["properties"]["grounded"]["type"] == "boolean"


class _InvalidHandler:
    def __init__(self, raw: str):
        self.raw = raw
        self.calls = 0

    async def generate_structured_response(self, *, response_model, **_kwargs):
        self.calls += 1
        return response_model.model_validate_json(self.raw)


def test_actual_voter_rejects_malformed_and_verify_is_unavailable(monkeypatch):
    monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "false")
    handler = _InvalidHandler("{}")
    result = asyncio.run(verify_reply(
        "answer", "tool evidence", handler=handler, samples=3,
        user_context="user fact"))
    assert result["ran"] is False
    assert handler.calls == 3  # every sample failed validation, no winner


def test_actual_voter_rejects_contradiction(monkeypatch):
    monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "false")
    handler = _InvalidHandler(
        '{"grounded": true, "unsupported_claims": ["x"]}')
    result = asyncio.run(verify_reply(
        "answer", "tool evidence", handler=handler, samples=3))
    assert result["ran"] is False


def test_explicit_false_verdict_still_surfaces(monkeypatch):
    monkeypatch.setenv("ATOM_VERIFY_ADAPTIVE", "false")
    class Handler:
        async def generate_structured_response(self, *, response_model, **_kwargs):
            return response_model.model_validate_json(
                '{"grounded": false, "unsupported_claims": ["x"]}')
    result = asyncio.run(verify_reply(
        "answer", "tool evidence", handler=Handler(), samples=3))
    assert result["ran"] is True
    assert result["grounded"] is False
    assert result["claims"] == ["x"]


@pytest.mark.parametrize("raw", [
    '{"grounded": "SYNTHETIC_MARKER_VALUE"}',
    '{"grounded": true, "unsupported_claims": ["SYNTHETIC_MARKER_VALUE"]}',
])
def test_validation_errors_hide_submitted_input_values(raw):
    with pytest.raises(Exception) as captured:
        VerifyVerdict.model_validate_json(raw)
    rendered = str(captured.value)
    assert "SYNTHETIC_MARKER_VALUE" not in rendered
    assert "SYNTHETIC_MARKER_VALUE" not in repr(captured.value)
    # Diagnostic field/type/reason remains, without the input value.
    assert "grounded" in rendered or "unsupported" in rendered
