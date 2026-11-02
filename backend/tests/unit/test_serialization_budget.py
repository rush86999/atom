"""Shared serialization budget boundaries for executable provider results."""
from __future__ import annotations

import asyncio
import uuid

import pytest

from core.assignment_executor import (
    ExecutablePayloadTooLarge,
    ExternalOutcomeUnknown,
    _action_registry_adapter,
    _json_safe,
    _SerializationBudget,
)
from core.action_registry import action_registry


def test_aggregate_executable_payload_exceeds_shared_byte_budget():
    payload = {"rows": [{"value": "x" * 1000} for _ in range(5000)]}
    with pytest.raises(ExecutablePayloadTooLarge) as exc:
        _json_safe(payload, executable=True, budget=_SerializationBudget())
    assert "UTF-8" in str(exc.value)


def test_oversized_dictionary_key_refuses():
    payload = {"k" * 2_100_000: "v"}
    with pytest.raises(ExecutablePayloadTooLarge) as exc:
        _json_safe(payload, executable=True, budget=_SerializationBudget())
    assert "key" in str(exc.value).lower()


def test_multibyte_content_is_counted_in_persisted_json_bytes():
    # é is ASCII-escaped by the persistence encoder (six bytes each).
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe({"content": "é" * 2_100_000}, executable=True)
    safe = _json_safe({"content": "é" * 500_000}, executable=True)
    assert safe["content"] == "é" * 500_000


def test_exact_serialized_limit_and_limit_plus_one():
    import json

    from core.assignment_executor import (
        _MAX_EXECUTABLE_BYTES, _PERSISTENCE_JSON_KWARGS,
        _enforce_serialized_budget,
    )

    empty = json.dumps({"content": ""}, **_PERSISTENCE_JSON_KWARGS).encode()
    exact = {"content": "x" * (_MAX_EXECUTABLE_BYTES - len(empty))}
    assert len(json.dumps(exact, **_PERSISTENCE_JSON_KWARGS).encode()) == (
        _MAX_EXECUTABLE_BYTES)
    _enforce_serialized_budget(exact)
    exact["content"] += "x"
    with pytest.raises(ExecutablePayloadTooLarge):
        _enforce_serialized_budget(exact)


def test_backslash_quote_and_control_escaping_count_toward_limit():
    # Raw characters under the old estimate exceed the serialized limit.
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe({"a": "\\" * 2_000_000, "b": "\\" * 200_000},
                   executable=True)
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe({"quotes": '"' * 2_100_000}, executable=True)
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe({"control": "\x01" * 700_000}, executable=True)


def test_post_effect_serialization_overflow_is_uncertain_not_failed():
    async def huge_effect(args, context):
        return {
            "status": "success", "action_result": "applied",
            "remote_id": "remote-1",
            "provider_receipt": {"operation_id": "op-1"},
            "big": {"k" * 2_100_000: "v"},
        }

    name = f"test.serialization.huge.{uuid.uuid4().hex[:8]}"
    action_registry.register(
        name, huge_effect, effects=[{"effect": "create"}])
    with pytest.raises(ExternalOutcomeUnknown) as exc:
        asyncio.run(_action_registry_adapter(
            {"action": name, "arguments": {}},
            {"tenant_id": "t1", "workspace_id": "ws-1",
             "employee_id": "u1", "run_id": "run-1",
             "assignment_id": "asg-1", "agent_id": "agent-1"}))
    assert "serialization" in str(exc.value).lower()
    assert "remote-1" in str(exc.value) or "remote-1" in str(
        getattr(exc.value, "evidence", ""))
