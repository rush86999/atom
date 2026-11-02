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
    # The persistence encoder ASCII-escapes é (six bytes each), so a 1M
    # character value is ~6 MB even though its raw UTF-8 is ~2 MB.
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe({"content": "é" * 2_100_000}, executable=True)
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe({"content": "é" * 1_000_000}, executable=True)
    safe = _json_safe({"content": "é" * 500_000}, executable=True)
    assert safe["content"] == "é" * 500_000


def test_multibyte_keys_count_as_their_persisted_json_representation():
    payload = {
        f"{index:04d}" + "é" * 508: "" for index in range(1_400)
    }
    assert _json_bytes(payload) > 4 * 1024 * 1024
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe(payload, executable=True)


def test_many_short_values_cross_the_serialized_boundary():
    payload = {f"k{index:05d}": "v" * 30 for index in range(99_000)}
    assert _json_bytes(payload) > 4 * 1024 * 1024
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe(payload, executable=True)


def test_post_effect_serialization_overflow_is_uncertain_not_failed():
    async def huge_effect(args, context):
        return {
            "status": "success", "action_result": "applied",
            "remote_id": "remote-1", "provider": "controlled",
            "operation": "create_record",
            "provider_receipt": {"operation_id": "op-1"},
            "big": {"k" * 2_100_000: "v"},
        }

    name = f"test.serialization.huge.{uuid.uuid4().hex[:8]}"
    action_registry.register(
        name, huge_effect, effects=[{"effect": "create"}])
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}},
        {"tenant_id": "t1", "workspace_id": "ws-1",
         "employee_id": "u1", "run_id": "run-1",
         "assignment_id": "asg-1", "agent_id": "agent-1"}))
    assert result["status"] == "uncertain"
    assert result["action_result"] == "uncertain"
    assert result["remote_id"] == "remote-1"
    assert result["provider_receipt"]["remote_id"] == "remote-1"


def test_nested_provider_receipts_are_preserved_exactly():
    payload = {
        "provider_receipt": {
            "operation_id": "op-1",
            "remote_id": "est-1",
            "verification": {
                "status": "verified",
                "checked_fields": ["customer_id", "line_items"],
                "line_items": [{
                    "item_id": "A", "quantity": "2",
                    "rate": "100.00", "evidence": {"row": 2},
                }],
            },
        },
        "read_receipt": {
            "version": "v2",
            "fields": {"sha256": "abc", "truncated": False},
            "rows": [{"item_id": "A", "quantity": "2"}],
        },
    }
    assert _json_safe(payload, executable=True) == payload


def test_serialized_json_overhead_cannot_exceed_the_byte_budget():
    payload = {
        "content": "x" * 1_700_000,
        "other": "y" * 1_700_000,
        "rows": [{"v": "x" * 72} for _ in range(9800)],
    }
    assert _json_bytes(payload) > 4 * 1024 * 1024
    # The text/node budget alone would fit; the final serialized form must be
    # measured, including JSON punctuation, quoting and separators.
    with pytest.raises(ExecutablePayloadTooLarge) as exc:
        _json_safe(payload, executable=True)
    assert "serialized" in str(exc.value).lower()


def test_non_finite_numbers_are_refused_explicitly():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ExecutablePayloadTooLarge) as exc:
            _json_safe({"value": value}, executable=True)
        assert "non-finite" in str(exc.value).lower()


def _over_budget_result():
    return {
        "status": "success", "action_result": "applied",
        "remote_id": "remote-big",
        "content": "x" * 1_700_000,
        "other": "y" * 1_700_000,
        "rows": [{"v": "x" * 72} for _ in range(10000)],
    }


def test_read_action_serialized_overflow_is_explicit_failure():
    async def huge_read(args, context):
        return _over_budget_result()

    name = f"test.serialization.read.{uuid.uuid4().hex[:8]}"
    action_registry.register(
        name, huge_read, effects=[{"effect": "read"}])
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}},
        {"tenant_id": "t1", "workspace_id": "ws-1",
         "employee_id": "u1", "run_id": "run-1",
         "assignment_id": "asg-1", "agent_id": "agent-1"}))
    assert result["status"] == "failed"
    assert result["error_class"] == "payload_too_large"
    assert "serialized" in result["message"].lower()


def test_mutation_serialized_overflow_preserves_uncertain_effect():
    async def huge_write(args, context):
        return _over_budget_result()

    name = f"test.serialization.write.{uuid.uuid4().hex[:8]}"
    action_registry.register(
        name, huge_write, effects=[{"effect": "create"}])
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}},
        {"tenant_id": "t1", "workspace_id": "ws-1",
         "employee_id": "u1", "run_id": "run-1",
         "assignment_id": "asg-1", "agent_id": "agent-1"}))
    assert result["status"] == "uncertain"
    assert result["remote_id"] == "remote-big"
    assert "serialized" in str(result["reason"]).lower()


def _json_bytes(value):
    import json
    return sum(len(chunk.encode("utf-8")) for chunk in json.JSONEncoder(
        ensure_ascii=True, separators=(", ", ": "), allow_nan=False
    ).iterencode(value))


def _three_string_payload(total_bytes):
    base = {"a": "", "b": "", "c": ""}
    overhead = _json_bytes(base)
    remaining = total_bytes - overhead
    first = remaining // 3
    second = remaining // 3
    third = remaining - first - second
    return {"a": "x" * first, "b": "x" * second, "c": "x" * third}


def test_exact_serialized_limit_is_accepted_and_plus_one_is_refused():
    limit = 4 * 1024 * 1024
    exact = _three_string_payload(limit)
    assert _json_bytes(exact) == limit
    assert _json_safe(exact, executable=True) == exact

    over = _three_string_payload(limit + 1)
    assert _json_bytes(over) == limit + 1
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe(over, executable=True)


def test_backslashes_count_as_their_json_representation():
    payload = {"a": "\\" * 2_000_000, "b": "\\" * 200_000}
    assert _json_bytes(payload) > 4 * 1024 * 1024
    with pytest.raises(ExecutablePayloadTooLarge):
        _json_safe(payload, executable=True)


def test_quotes_controls_escapes_and_multibyte_keys_round_trip():
    payload = {
        'k"é\\': "a\\b\"c\n\t\u0001é",
        "nested": {"quote": '"', "backslash": "\\", "control": "\u0002"},
    }
    safe = _json_safe(payload, executable=True)
    assert safe == payload
    assert _json_bytes(safe) == _json_bytes(payload)
