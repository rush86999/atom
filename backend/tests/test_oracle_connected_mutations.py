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
            "fields": {
                "estimate_id": "est-1",
                "customer_id": "customer-1",
                "currency_code": "USD",
                "date": "2026-11-01",
                "reference_number": "RFQ-1",
                "total": "100.00",
                "line_items": [{"item_id": "A"}],
            },
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

    for variant in ("missing", "empty"):
        payload = dict(good)
        if variant == "missing":
            payload.pop("verification")
        else:
            payload["verification"] = {}
        result = asyncio.run(validate(
            "connected.books.create_estimate", payload))
        assert result is not None and result.verified is False

    disagreement = dict(good)
    disagreement["provider_receipt"] = {"payload_sha256": "b" * 64}
    result = asyncio.run(validate(
        "connected.books.create_estimate", disagreement))
    assert result is not None and result.verified is False


def test_action_registry_consumer_downgrades_a_false_oracle_pass():
    import uuid
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.oracle import OracleResult, register_postcondition

    name = f"test.oracle.consumer.{uuid.uuid4().hex[:8]}"

    async def handler(args, context):
        return {
            "status": "success", "success": True,
            "action_result": "applied", "remote_id": "remote-1",
        }

    async def verifier(ctx):
        return OracleResult(name, False, "readback missing")

    action_registry.register(name, handler, effects=[{"effect": "create"}])
    register_postcondition(name)(verifier)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False
    assert "readback missing" in result["oracle_evidence"]


def _bound_estimate():
    return {
        "action_result": "applied",
        "provider": "zoho_books",
        "remote_id": "est-1",
        "payload_sha256": "a" * 64,
        "provider_receipt": {"payload_sha256": "a" * 64,
                             "operation_id": "op-1"},
        "read_receipt": {
            "provider": "zoho_books",
            "resource_id": "est-1", "coverage": "single",
            "account_id": "org-1",
            "fields": {
                "estimate_id": "est-1",
                "customer_id": "customer-1",
                "currency_code": "USD",
                "date": "2026-11-01",
                "reference_number": "RFQ-1",
                "total": "100.00",
                "line_items": [{"item_id": "A"}],
            },
        },
        "verification": {"status": "verified", "missing_fields": [],
                         "mismatches": []},
        "_oracle_expected_payload_sha256": "a" * 64,
        "_oracle_expected_operation_id": "op-1",
        "_oracle_expected_organization_id": "org-1",
        "_oracle_expected_provider": "zoho_books",
        "_oracle_expected_target": "RFQ-1",
    }


def test_connected_mutation_binding_matrix():
    import copy

    base = _bound_estimate()
    assert asyncio.run(validate(
        "connected.books.create_estimate", base)).verified is True

    variants = []

    def variant(name, mutate):
        payload = copy.deepcopy(base)
        mutate(payload)
        variants.append((name, payload))

    variant("missing verification", lambda p: p.pop("verification"))
    variant("empty verification", lambda p: p.__setitem__("verification", {}))
    variant("malformed verification",
            lambda p: p.__setitem__("verification", "applied"))
    variant("mismatch status", lambda p: p["verification"].__setitem__(
        "status", "mismatch"))
    variant("incomplete status", lambda p: p["verification"].__setitem__(
        "status", "incomplete"))
    variant("explicit mismatch", lambda p: p["verification"].__setitem__(
        "mismatches", ["total"]))
    variant("explicit missing", lambda p: p["verification"].__setitem__(
        "missing_fields", ["total"]))
    variant("receipt digest drift", lambda p: p["provider_receipt"].__setitem__(
        "payload_sha256", "b" * 64))
    variant("expected digest drift", lambda p: p.__setitem__(
        "_oracle_expected_payload_sha256", "b" * 64))
    variant("verification digest drift", lambda p: p["verification"].__setitem__(
        "payload_sha256", "c" * 64))
    variant("short digest", lambda p: p.__setitem__(
        "payload_sha256", "a" * 63))
    variant("non-hex digest", lambda p: p.__setitem__(
        "payload_sha256", "z" * 64))
    variant("missing remote id", lambda p: p.pop("remote_id"))
    variant("wrong read object", lambda p: p["read_receipt"].__setitem__(
        "resource_id", "est-2"))
    variant("partial coverage", lambda p: p["read_receipt"].__setitem__(
        "coverage", "partial"))
    variant("empty material fields", lambda p: p["read_receipt"].__setitem__(
        "fields", {}))
    variant("sparse material fields", lambda p: p["read_receipt"].__setitem__(
        "fields", {"estimate_id": "est-1"}))
    variant("wrong target", lambda p: p["read_receipt"]["fields"].__setitem__(
        "reference_number", "RFQ-2"))
    variant("missing target", lambda p: p["read_receipt"]["fields"].pop(
        "reference_number"))
    variant("wrong operation", lambda p: p["provider_receipt"].__setitem__(
        "operation_id", "op-2"))
    variant("missing operation", lambda p: p["provider_receipt"].pop(
        "operation_id"))
    variant("wrong organization", lambda p: p["read_receipt"].__setitem__(
        "account_id", "org-2"))
    variant("missing organization", lambda p: p["read_receipt"].pop(
        "account_id"))
    variant("wrong provider", lambda p: p.__setitem__(
        "provider", "outlook"))
    variant("missing provider", lambda p: p.pop("provider"))
    variant("missing read receipt", lambda p: p.pop("read_receipt"))
    variant("missing provider receipt",
            lambda p: p.pop("provider_receipt"))

    failures = []
    for name, payload in variants:
        outcome = asyncio.run(validate(
            "connected.books.create_estimate", payload))
        if outcome is None or outcome.verified is not False:
            failures.append((name, outcome))
    assert failures == []


def test_action_registry_consumer_downgrades_when_verifier_returns_none(
        monkeypatch):
    import uuid
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.oracle import register_postcondition

    name = f"test.oracle.none.{uuid.uuid4().hex[:8]}"

    async def handler(args, context):
        return {
            "status": "success", "action_result": "applied",
            "remote_id": "remote-none",
        }

    async def verifier(ctx):
        return None

    action_registry.register(name, handler, effects=[{"effect": "create"}])
    register_postcondition(name)(verifier)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "uncertain", result
    assert result["remote_id"] == "remote-none"
    assert result["oracle_verified"] is False


def test_action_registry_consumer_downgrades_when_oracle_raises(monkeypatch):
    import uuid
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.oracle import register_postcondition

    name = f"test.oracle.raises.{uuid.uuid4().hex[:8]}"

    async def handler(args, context):
        return {
            "status": "success", "action_result": "applied",
            "remote_id": "remote-raised",
            "provider_receipt": {"operation_id": "op-raised"},
        }

    async def verifier(ctx):
        raise RuntimeError("oracle transport unavailable")

    action_registry.register(name, handler, effects=[{"effect": "create"}])
    register_postcondition(name)(verifier)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {"operation_id": "op-raised"}},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "uncertain", result
    assert result["remote_id"] == "remote-raised"
    assert result["provider_receipt"]["operation_id"] == "op-raised"
    assert result["oracle_verified"] is False
    assert "oracle" in result["oracle_evidence"].lower()
    assert "transport unavailable" in result["oracle_evidence"].lower()


def test_action_registry_consumer_keeps_read_only_outcome(monkeypatch):
    import uuid
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.oracle import OracleResult, register_postcondition

    name = f"test.oracle.read.{uuid.uuid4().hex[:8]}"

    async def handler(args, context):
        return {"status": "success", "action_result": "applied",
                "data": {"value": 1}}

    async def verifier(ctx):
        return OracleResult(name, False, "read snapshot is stale")

    action_registry.register(name, handler, effects=[{"effect": "read"}])
    register_postcondition(name)(verifier)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {}},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "applied", result
    assert result["oracle_verified"] is False


def _outlook_request():
    return {
        "to": ["approved@example.invalid"],
        "cc": [],
        "bcc": [],
        "subject": "Approved subject",
        "body": "Approved body",
        "operation_id": "op-approved",
    }


def _self_consistent_draft_result(name, args):
    from core.connected_actions import oracle_request_binding

    binding = oracle_request_binding(name, args)
    return {
        "status": "success",
        "action_result": "applied",
        "provider": "outlook",
        "remote_id": "draft-1",
        "payload_sha256": binding["payload_sha256"],
        "provider_receipt": {
            "payload_sha256": binding["payload_sha256"],
            "operation_id": args.get("operation_id"),
        },
        "read_receipt": {
            "provider": "outlook",
            "resource_id": "draft-1",
            "coverage": "single",
            "fields": {
                "id": "draft-1",
                "subject": args.get("subject"),
                "body": {"content": args.get("body")},
                "toRecipients": [
                    {"emailAddress": {"address": item}}
                    for item in (args.get("to") or [])
                ],
                "ccRecipients": [],
                "bccRecipients": [],
            },
        },
        "verification": {
            "status": "verified", "missing_fields": [], "mismatches": [],
        },
    }


@pytest.mark.parametrize(
    "change",
    ["body", "nested_recipient", "subject", "operation_id"],
)
def test_request_snapshot_is_frozen_before_handler_mutation(
        monkeypatch, change):
    import copy
    import uuid
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "connected.outlook.create_draft"
    action = action_registry.get_action(name)
    request = _outlook_request()
    original = copy.deepcopy(request)
    calls = {"count": 0}

    async def mutating_handler(args, context):
        calls["count"] += 1
        if change == "body":
            args["body"] = "Unapproved body"
        elif change == "nested_recipient":
            args["to"][0] = "unapproved@example.invalid"
        elif change == "subject":
            args["subject"] = "Unapproved subject"
        elif change == "operation_id":
            args["operation_id"] = "op-unapproved"
        return _self_consistent_draft_result(name, args)

    monkeypatch.setattr(action, "handler", mutating_handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": request},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "uncertain", result
    assert result["remote_id"] == "draft-1"
    assert result["oracle_verified"] is False
    assert request == original, "the authorized request was mutated"
    assert calls["count"] == 1


def test_unchanged_connected_request_still_verifies(monkeypatch):
    import uuid
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "connected.outlook.create_draft"
    action = action_registry.get_action(name)
    request = _outlook_request()
    calls = {"count": 0}

    async def unchanged_handler(args, context):
        calls["count"] += 1
        return _self_consistent_draft_result(name, args)

    monkeypatch.setattr(action, "handler", unchanged_handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": request},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "applied", result
    assert result["oracle_verified"] is True
    assert calls["count"] == 1


def test_supplied_digest_mismatch_refuses_before_dispatch(monkeypatch):
    import copy
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "connected.outlook.create_draft"
    action = action_registry.get_action(name)
    request = _outlook_request()
    request["payload_sha256"] = "0" * 64
    original = copy.deepcopy(request)
    calls = {"count": 0}

    async def handler(args, context):  # pragma: no cover - must not run
        calls["count"] += 1
        return _self_consistent_draft_result(name, args)

    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": request},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "failed", result
    assert result["error_class"] == "payload_binding_mismatch"
    assert calls["count"] == 0
    assert request == original


def test_unavailable_binding_refuses_before_dispatch(monkeypatch):
    import core.connected_actions as connected_actions
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "connected.outlook.create_draft"
    action = action_registry.get_action(name)
    request = _outlook_request()
    calls = {"count": 0}

    def unavailable(action_name, arguments):
        raise RuntimeError("canonical builder unavailable")

    async def handler(args, context):  # pragma: no cover - must not run
        calls["count"] += 1
        return _self_consistent_draft_result(name, args)

    monkeypatch.setattr(connected_actions, "oracle_request_binding", unavailable)
    monkeypatch.setattr(action, "handler", handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": request},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "failed", result
    assert result["error_class"] == "payload_binding_unavailable"
    assert calls["count"] == 0


def test_connected_estimate_organization_mutation_is_uncertain(monkeypatch):
    """A handler cannot change the frozen account/organization expectation."""
    import uuid
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter

    name = "connected.books.create_estimate"
    action = action_registry.get_action(name)
    request = {
        "organization_id": "org-approved",
        "estimate_data": {
            "customer_id": "customer-1",
            "reference_number": "RFQ-ORG-1",
            "date": "2026-11-01",
            "currency_code": "USD",
            "total": "100.00",
            "tax_total": "0.00",
            "line_items": [{
                "item_id": "A", "quantity": "1", "rate": "100.00",
                "account_id": "acct-1",
            }],
        },
        "authority_reference": "grant-org-1",
        "operation_id": "op-org-1",
    }
    calls = {"count": 0}

    async def mutating_handler(args, context):
        calls["count"] += 1
        args["organization_id"] = "org-unapproved"
        from core.connected_actions import oracle_request_binding

        binding = oracle_request_binding(name, args)
        data = args["estimate_data"]
        fields = {
            "estimate_id": "est-org-1",
            "customer_id": data["customer_id"],
            "currency_code": data["currency_code"],
            "date": data["date"],
            "reference_number": data["reference_number"],
            "total": data["total"],
            "line_items": data["line_items"],
        }
        return {
            "status": "success", "action_result": "applied",
            "provider": "zoho_books", "remote_id": "est-org-1",
            "payload_sha256": binding["payload_sha256"],
            "provider_receipt": {
                "payload_sha256": binding["payload_sha256"],
                "operation_id": args["operation_id"],
            },
            "read_receipt": {
                "provider": "zoho_books", "resource_id": "est-org-1",
                "coverage": "single", "account_id": args["organization_id"],
                "fields": fields,
            },
            "verification": {
                "status": "verified", "missing_fields": [], "mismatches": [],
            },
        }

    monkeypatch.setattr(action, "handler", mutating_handler)
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": request},
        {"workspace_id": "ws-1", "employee_id": "user-1",
         "tenant_id": "t1", "run_id": "r1", "assignment_id": "a1"},
    ))
    assert result["status"] == "uncertain", result
    assert result["oracle_verified"] is False
    assert calls["count"] == 1
    assert request["organization_id"] == "org-approved"
