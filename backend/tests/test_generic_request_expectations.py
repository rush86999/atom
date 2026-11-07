"""Normal registered-action requests must be independently verifiable.

The outcome consumer (``GenericAgent._step_act_unaudited``) and the typed
assignment adapter must freeze the SAME proof material from an accepted
business request plus server-owned runtime identity.  A model never authors
``_oracle_expected_*`` fields; arbitrary values in its JSON are stripped and
cannot become authority.

Scope note: every dispatch is a real registered handler against a scratch
SQLite store.  Governance is explicitly bypassed (``pre_approved=True``) to
isolate the outcome consumer; no model, guest microVM, provider or live
account is invoked.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from core.action_registry import action_registry
from core.oracle import OracleResult, register_postcondition
from core.oracle.request_expectations import (
    approved_payload_sha256,
    build_request_expectations,
    strip_expected_fields,
)
from tests.test_generic_oracle_mutation_contract import _agent, _claim_context
from tests.test_oracle_mini_app_host_mutations import (
    TENANT,
    USER,
    WORKSPACE,
    _adapter,
    host,
)

SCAFFOLD_ARGS = {
    "name": "Normal consumer app",
    "declared_scopes": ["canvas_render"],
    "dependencies": [],
}


def _plain_context(execution: str = "normal-generic-execution") -> dict:
    return {
        "workspace_id": WORKSPACE,
        "tenant_id": TENANT,
        "user_id": USER,
        "actor_id": USER,
        "execution_id": execution,
        "run_id": execution,
        "tier": "autonomous",
    }


def _real_registry_agent():
    async def leaf(name, arguments, context=None):
        return await action_registry.execute_action(
            name, arguments, context or {})

    agent = _agent(leaf)
    agent.workspace_id = WORKSPACE
    agent.tenant_id = TENANT
    return agent


def _run_generic(agent, action, arguments, context):
    return asyncio.run(agent._step_act_unaudited(
        action, arguments, context=context, pre_approved=True))


def _enable_oracle(monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")


# ---------------------------------------------------------------------------
# Shared builder contract
# ---------------------------------------------------------------------------

def test_builder_freezes_business_args_and_ignores_model_expected_fields():
    forged = {
        "name": "Builder app",
        "declared_scopes": ["canvas_render"],
        "dependencies": [],
        "_oracle_expected_operation_id": "forged-operation",
        "_oracle_expected_tenant_id": "forged-tenant",
        "_oracle_expected_actor_id": "forged-actor",
        "_oracle_expected_mini_app_name": "forged-name",
        "_oracle_expected_request_sha256": "f" * 64,
    }
    clean = strip_expected_fields(forged)
    assert clean == {
        "name": "Builder app",
        "declared_scopes": ["canvas_render"],
        "dependencies": [],
    }
    expected = build_request_expectations(
        "mini_app_scaffold", forged,
        operation_id="server-operation",
        tenant_id="tenant-1",
        workspace_id="ws-1",
        actor_id="user-1",
        agent_id="agent-1",
    )
    assert expected["_oracle_expected_operation_id"] == "server-operation"
    assert expected["_oracle_expected_tenant_id"] == "tenant-1"
    assert expected["_oracle_expected_workspace_id"] == "ws-1"
    assert expected["_oracle_expected_actor_id"] == "user-1"
    assert expected["_oracle_expected_agent_id"] == "agent-1"
    assert expected["_oracle_expected_mini_app_name"] == "Builder app"
    assert expected["_oracle_expected_request_sha256"] == (
        approved_payload_sha256(clean))


# ---------------------------------------------------------------------------
# Normal plain-args twin: Generic == typed assignment
# ---------------------------------------------------------------------------

def test_plain_args_generic_and_assignment_produce_the_same_verified_effect(
        host, monkeypatch):
    _enable_oracle(monkeypatch)
    monkeypatch.setattr("core.generic_agent.get_db_session", host.session)
    agent = _real_registry_agent()

    generic_args = dict(SCAFFOLD_ARGS)
    generic = _run_generic(
        agent, "mini_app_scaffold", generic_args, _plain_context())

    assert generic.get("success") is True, generic
    assert generic.get("oracle_verified") is True, generic
    assert generic.get("oracle_evidence"), generic

    assignment_args = {**SCAFFOLD_ARGS, "name": "Assignment twin app"}
    assignment = _adapter(
        "mini_app_scaffold", assignment_args, "normal-assignment-operation")
    assert assignment.get("_adapter_status") == "applied", assignment

    from core.models import CanvasAudit, MiniApp

    with host.Session() as db:
        assert db.query(MiniApp).count() == 2
        scaffold_audits = db.query(CanvasAudit).filter(
            CanvasAudit.action_type == "mini_app_scaffold").all()
        assert len(scaffold_audits) == 2
        by_operation = {
            row.details_json["operation_id"]: row for row in scaffold_audits
        }
        generic_receipt = by_operation[generic["operation_id"]]
        assert generic_receipt.details_json["request_sha256"] == (
            approved_payload_sha256(generic_args))
        assert generic_receipt.details_json["actor_id"] == USER
        assert generic_receipt.details_json["tenant_id"] == TENANT
        assert generic_receipt.details_json["workspace_id"] == WORKSPACE


# ---------------------------------------------------------------------------
# A second, non-MiniApp registered family uses the same mechanism
# ---------------------------------------------------------------------------

def test_plain_args_non_miniapp_presentation_is_verified(host, monkeypatch):
    _enable_oracle(monkeypatch)
    monkeypatch.setattr("core.generic_agent.get_db_session", host.session)
    monkeypatch.setattr(
        "tools.canvas_tool.ws_manager.broadcast", AsyncMock())
    from core.feature_flags import FeatureFlags

    monkeypatch.setattr(
        FeatureFlags, "should_enforce_governance",
        classmethod(lambda cls, feature: True))

    class _Resolver:
        def __init__(self, db):
            self.db = db

        async def resolve_agent_for_request(self, **kwargs):
            return None, {"resolution_path": ["test"]}

    monkeypatch.setattr("tools.canvas_tool.AgentContextResolver", _Resolver)

    class _Governance:
        def can_perform_action(self, **kwargs):
            return {"allowed": True, "reason": ""}

    from core.service_factory import ServiceFactory

    monkeypatch.setattr(
        ServiceFactory, "get_governance_service",
        classmethod(lambda cls, db, **kwargs: _Governance()))

    agent = _real_registry_agent()
    arguments = {"title": "Quote", "content": "APPROVED total 350.00"}
    result = _run_generic(
        agent, "canvas.present_markdown", arguments,
        _plain_context("non-miniapp-presentation"))

    assert result.get("success") is True, result
    assert result.get("oracle_verified") is True, result
    assert result.get("audit_id"), result

    from core.models import CanvasAudit
    from core.presentation_material import material_sha256, presentation_material

    with host.Session() as db:
        audit = db.query(CanvasAudit).filter(
            CanvasAudit.id == result["audit_id"]).one()
        details = audit.details_json
        assert str(details["operation_id"]).startswith("auto-")
        assert details["material_sha256"] == material_sha256(
            presentation_material("canvas.present_markdown", arguments))


# ---------------------------------------------------------------------------
# Model-supplied "expected" metadata is never authority
# ---------------------------------------------------------------------------

def test_model_forged_expected_metadata_is_stripped_before_dispatch(
        host, monkeypatch):
    _enable_oracle(monkeypatch)
    monkeypatch.setattr("core.generic_agent.get_db_session", host.session)
    seen = []

    async def leaf(name, arguments, context=None):
        seen.append(dict(arguments))
        return await action_registry.execute_action(
            name, arguments, context or {})

    agent = _agent(leaf)
    agent.workspace_id = WORKSPACE
    agent.tenant_id = TENANT
    forged = {
        **SCAFFOLD_ARGS,
        "name": "Forged metadata app",
        "_oracle_expected_operation_id": "forged-operation",
        "_oracle_expected_tenant_id": "forged-tenant",
        "_oracle_expected_actor_id": "forged-actor",
        "_oracle_expected_mini_app_name": "forged-name",
        "_oracle_expected_request_sha256": "f" * 64,
    }
    snapshot = dict(forged)
    result = _run_generic(
        agent, "mini_app_scaffold", forged,
        _plain_context("forged-metadata-execution"))

    assert forged == snapshot, "the model request was rewritten in place"
    assert seen, "the handler was never dispatched"
    assert not any(
        str(key).startswith("_oracle_expected_")
        for key in seen[0]), seen[0]
    assert result.get("success") is True, result
    assert result.get("oracle_verified") is True, result
    assert result.get("operation_id") != "forged-operation", result

    from core.models import CanvasAudit, MiniApp

    with host.Session() as db:
        app = db.query(MiniApp).filter(
            MiniApp.name == "Forged metadata app").one()
        assert app.created_by == USER
        assert app.tenant_id == TENANT
        audit = db.query(CanvasAudit).filter(
            CanvasAudit.action_type == "mini_app_scaffold",
            CanvasAudit.canvas_id == app.blueprint_canvas_id).one()
        assert audit.details_json["operation_id"] == (
            result["operation_id"])
        assert audit.details_json["operation_id"] != "forged-operation"


def test_model_forged_expected_metadata_cannot_rescue_wrong_server_scope(
        host, monkeypatch):
    """The never-frozen tenant in the runtime context stays refuted even when
    the model forges expected metadata claiming the real tenant."""
    _enable_oracle(monkeypatch)
    monkeypatch.setattr("core.generic_agent.get_db_session", host.session)
    agent = _real_registry_agent()
    context = _plain_context("wrong-scope-execution")
    context["tenant_id"] = "wrong-tenant"
    forged = {
        **SCAFFOLD_ARGS,
        "name": "Wrong scope app",
        "_oracle_expected_tenant_id": TENANT,
        "_oracle_expected_actor_id": USER,
        "_oracle_expected_operation_id": "forged-operation",
    }
    result = _run_generic(agent, "mini_app_scaffold", forged, context)

    assert result.get("success") is not True, result
    assert result.get("oracle_verified") is False, result
    assert result.get("status") == "uncertain", result
    assert result.get("requires_reconciliation") is True, result
    assert "tenant" in str(result.get("oracle_evidence") or "").lower(), (
        result.get("oracle_evidence"))

    from core.models import MiniApp

    with host.Session() as db:
        # The real effect landed (honest uncertainty, not a false failure).
        assert db.query(MiniApp).filter(
            MiniApp.name == "Wrong scope app").count() == 1


# ---------------------------------------------------------------------------
# Reconciliation of a landed-but-unverified operation (no resend)
# ---------------------------------------------------------------------------

def test_uncertain_operation_reconciles_from_frozen_material_without_resend(
        host, monkeypatch):
    _enable_oracle(monkeypatch)
    monkeypatch.setattr("core.generic_agent.get_db_session", host.session)

    name = "test.generic.reconcile." + uuid.uuid4().hex
    operation_id = "op-reconcile-" + uuid.uuid4().hex
    calls = []
    verdicts = [False, True]

    async def leaf(tool, args, context=None):
        calls.append(dict(args))
        with host.Session() as db:
            from core.models import User
            marker = User(
                id=f"effect-{uuid.uuid4().hex}", tenant_id=TENANT,
                workspace_id=WORKSPACE, email=f"{uuid.uuid4().hex}@x.test",
                hashed_password="x", first_name="E", last_name="F",
                role="member", status="active", is_active=True)
            db.add(marker)
            db.commit()
        return {"success": True, "status": "success",
                "action_result": "applied"}

    async def verifier(ctx):
        # First readback deliberately disagrees; the second represents the
        # later reconciliation pass over the SAME durable effect.
        value = verdicts.pop(0) if verdicts else True
        return OracleResult(name, value, "fresh same-effect readback")

    action_registry.register(
        name, leaf, effects=[{"effect": "create", "scope": "local"}])
    register_postcondition(name)(verifier)

    context = _claim_context(operation_id)
    first = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {"value": "one"}, context=dict(context), pre_approved=True))
    assert first.get("status") == "uncertain", first
    assert len(calls) == 1

    second = asyncio.run(_agent(leaf)._step_act_unaudited(
        name, {"value": "one"}, context=dict(context), pre_approved=True))
    assert len(calls) == 1, "the uncertain operation was resent"
    assert second.get("success") is True, second
    assert second.get("reconciled") is True, second
    assert second.get("idempotent") is True, second
    assert second.get("oracle_verified") is True, second
    assert "no second dispatch" in str(second.get("message") or "").lower()

    from core import outbound_operation_claim as claims

    with host.Session() as db:
        row = claims.generic_operations(
            context["workspace_id"], operation_id,
            db_factory=host.session, strict=True)
        assert row and row[0]["status"] == claims.SUCCEEDED, row
