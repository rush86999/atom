"""Frozen request expectations shared by every registered-action consumer.

Why this module exists
----------------------
The postcondition oracle never grades a tool by its own self-report.  It
re-reads the system of record and compares it with the *authorized request*
frozen before dispatch.  Two consumers dispatch registered actions:

* ``AssignmentExecutor._action_registry_adapter`` (typed assignment steps), and
* ``GenericAgent._step_act_unaudited`` (ordinary ReAct tool calls).

Historically the assignment adapter built the expected operation/request
digest/scope/material block inline, while the Generic consumer only forwarded
``_oracle_expected_*`` fields that happened to be present in the model's
arguments.  A normal model never authors those hidden fields, so a real,
landed mutation was reported as "no frozen operation/request binding" even
though the producer had written a complete receipt.

This module is the single builder both consumers use.  It derives proof
expectations from the accepted business arguments plus the server-owned
runtime identity (operation, tenant, workspace, actor).  The ``_oracle_expected_*``
namespace is *internal*: model/body arguments cannot populate it.  A result
envelope cannot populate it either (``GenericAgent._oracle_context`` keeps
results below the frozen snapshot).

Design note (runtime context vs. model input)
---------------------------------------------
LangChain's tool contract separates immutable runtime context/execution
identity from the model-visible input and injects it outside the tool schema
(https://docs.langchain.com/oss/python/langchain/tools#access-context).  MCP
likewise defines ``inputSchema`` as the model-visible argument contract and
treats annotations as untrusted unless they come from a trusted server
(https://modelcontextprotocol.io/specification/2025-06-18/server/tools).  We
apply that separation with Atom's existing registry/claim/oracle machinery;
no framework dependency or second runner is introduced.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Mapping, Optional

#: The protected, server-owned expectation namespace.
EXPECTED_PREFIX = "_oracle_expected_"


def strip_expected_fields(arguments: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Return a deep copy of the business arguments without internal fields.

    Model-visible input may legitimately contain any business key, but the
    oracle-expectation namespace is not part of the action contract.  Removing
    it before dispatch also keeps the producer's request digest honest: the
    receipt hashes exactly what the server authorized, not model-supplied
    proof material.
    """
    return {
        str(key): copy.deepcopy(value)
        for key, value in (arguments or {}).items()
        if not str(key).startswith(EXPECTED_PREFIX)
    }


def approved_payload_sha256(arguments: Mapping[str, Any] | None) -> str:
    """Stable digest of the exact authorized business request.

    Uses the same helper the producers use for their receipt binding
    (``core.task_lifecycle._approval_payload_hash``).  An unsupported value is
    a missing binding, never a lossy fallback.
    """
    try:
        from core.task_lifecycle import _approval_payload_hash

        return _approval_payload_hash(dict(arguments or {}))
    except Exception:  # noqa: BLE001 - a receipt without a binding is refused
        return ""


def _as_text(value: Any) -> str:
    return "" if value is None else str(value)


def build_request_expectations(
    action: str,
    arguments: Mapping[str, Any] | None,
    *,
    operation_id: str = "",
    tenant_id: str = "",
    workspace_id: str = "",
    actor_id: str = "",
    agent_id: str = "",
    request_sha256: Optional[str] = None,
    binding: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the ``_oracle_expected_*`` snapshot for one authorized request.

    Parameters are server-owned runtime identity.  ``arguments`` is the
    accepted business request; any client-supplied ``_oracle_expected_*`` keys
    are stripped and can never become authority.

    ``request_sha256`` may be supplied when the caller already froze the digest
    (the assignment adapter does this for mutating steps).  When it is ``None``
    the digest is computed over the sanitized arguments — the exact bytes the
    producer will hash for its receipt.

    ``binding`` may be supplied when the caller already computed the connected
    mutation binding; otherwise it is derived here through the existing
    ``core.connected_actions.oracle_request_binding`` helper.
    """
    name = str(action or "")
    args = strip_expected_fields(arguments)

    if binding is None:
        try:
            from core.connected_actions import oracle_request_binding

            binding = oracle_request_binding(name, args) or {}
        except Exception:  # noqa: BLE001 - malformed arguments stay unbound
            binding = {}
    binding = binding or {}

    if request_sha256 is None:
        request_sha256 = approved_payload_sha256(args)

    # Provenance: a canonical provider binding wins over a caller-supplied
    # digest; otherwise a business ``payload_sha256`` argument is the only
    # candidate.  Mirrors the assignment adapter exactly.
    expected_digest = str(
        binding.get("payload_sha256") or args.get("payload_sha256") or "")
    expected_operation = str(
        binding.get("operation_id") or args.get("operation_id")
        or operation_id or "")
    expected_organization = str(
        binding.get("organization_id") or args.get("organization_id") or "")
    expected_provider = str(binding.get("provider") or "")
    expected_target = str(binding.get("target") or "")

    expected_tenant_id = str(args.get("tenant_id") or tenant_id or "")
    expected_workspace_id = str(args.get("workspace_id") or workspace_id or "")
    expected_actor_id = str(actor_id or "")
    expected_agent_id = str(args.get("agent_id") or agent_id or "")

    expected_canvas_id = str(args.get("canvas_id") or "")
    expected_restore_audit_id = (
        str(args.get("audit_id") or "")
        if name == "canvas.restore_version" else "")
    expected_prior_audit_id = (
        str(args.get("expected_prior_audit_id") or "")
        if name == "canvas.delete" else "")
    expected_tombstone_audit_id = (
        str(args.get("tombstone_audit_id")
            or args.get("expected_tombstone_audit_id") or "")
        if name == "canvas.undelete" else "")
    expected_source_audit_id = (
        str(args.get("source_audit_id")
            or args.get("expected_source_audit_id") or "")
        if name == "canvas.undelete" else "")
    expected_canvas_content_sha256 = ""
    if name == "canvas.update" and "content" in args:
        expected_canvas_content_sha256 = approved_payload_sha256(
            args.get("content"))

    expected_goal_id = str(args.get("goal_id") or "")
    expected_goal_title = (
        str(args.get("title") or "") if name == "goals.create" else "")

    expected_chart_type = (
        str(args.get("chart_type") or args.get("type") or "")
        if name == "canvas.present_chart" else "")
    expected_data_points = None
    if name == "canvas.present_chart":
        chart_data = args.get("data")
        if chart_data is None and isinstance(args.get("chart"), dict):
            chart_data = args["chart"].get("data")
        if isinstance(chart_data, list):
            expected_data_points = len(chart_data)

    expected_present_title = (
        str(args.get("title") or "")
        if name in ("canvas.present_chart", "canvas.present_markdown")
        else "")
    expected_task_title = (
        str(args.get("title") or "") if name == "tasks.create" else "")
    expected_board_id = (
        str(args.get("board_id") or "") if name == "tasks.create" else "")

    # Shopify product material is frozen from the accepted business arguments
    # (never from the handler's returned object).  The verifier compares this
    # projection with a fresh provider readback, so a matching title alone can
    # never certify the effect.
    expected_shopify_product = None
    if name == "shopify_create_product":
        try:
            from core.shopify_mutations import accepted_product_material

            expected_shopify_product = accepted_product_material(args)
        except Exception:  # noqa: BLE001 - verifier refuses absent binding
            expected_shopify_product = None

    expected_shopify_blog = None
    if name == "shopify_create_blog":
        try:
            from core.shopify_mutations import accepted_blog_material

            expected_shopify_blog = accepted_blog_material(args)
        except Exception:  # noqa: BLE001 - verifier refuses absent binding
            expected_shopify_blog = None

    expected_shopify_article = None
    if name == "shopify_create_article":
        try:
            from core.shopify_mutations import accepted_article_material

            expected_shopify_article = accepted_article_material(args)
        except Exception:  # noqa: BLE001 - verifier refuses absent binding
            expected_shopify_article = None

    expected_radio_message = None
    if name == "radio.send_message":
        try:
            from core.agent_radio.radio_mutations import radio_payload

            expected_radio_message = radio_payload(
                args, agent_id=agent_id, tenant_id=expected_tenant_id)
            # The producer binds the same canonical message material, not the
            # whole argument map (which also carries operation metadata).
            expected_digest = approved_payload_sha256(expected_radio_message)
        except Exception:  # noqa: BLE001 - verifier refuses absent binding
            expected_radio_message = None

    expected_shopify_fulfillment = None
    if name == "shopify_create_fulfillment":
        try:
            from core.shopify_mutations import (
                accepted_fulfillment_material,
            )

            expected_shopify_fulfillment = accepted_fulfillment_material(args)
        except Exception:  # noqa: BLE001 - verifier refuses absent binding
            expected_shopify_fulfillment = None

    # Presentation material is frozen from the authorized arguments, not from
    # the handler's returned envelope.  Both consumers and the canvas producer
    # derive it through ``core.presentation_material`` so the digests cannot
    # drift.
    expected_presentation_material = None
    expected_material_sha256 = ""
    if name in ("canvas.present_markdown", "canvas.present_chart"):
        try:
            from core.presentation_material import (
                material_sha256,
                presentation_material,
            )

            expected_presentation_material = presentation_material(name, args)
        except Exception:  # noqa: BLE001 - verifier refuses absent binding
            expected_presentation_material = None
        if expected_presentation_material is not None:
            expected_material_sha256 = material_sha256(
                expected_presentation_material)

    _mini_app_app_actions = {
        "mini_app_set_tests", "mini_app_write_logic", "mini_app_publish",
        "mini_app_install", "mini_app_revert_logic",
    }
    expected_app_id = (
        str(args.get("app_id") or "")
        if name in _mini_app_app_actions else "")
    expected_tests = args.get("tests") if name == "mini_app_set_tests" else None
    expected_tests_sha256 = ""
    if name == "mini_app_set_tests":
        expected_tests_sha256 = approved_payload_sha256(args.get("tests"))

    expected_mini_app_name = ""
    expected_mini_app_declared_scopes: list = []
    expected_mini_app_dependencies: list = []
    expected_mini_app_spec: Dict[str, Any] = {}
    expected_mini_app_source_sha256 = ""
    expected_mini_app_version = ""
    expected_db_op = ""
    expected_db_series = None
    expected_db_data = None
    expected_db_record_id = ""
    expected_db_append_id = ""
    expected_db_filter: Dict[str, Any] = {}
    if name == "mini_app_scaffold":
        expected_mini_app_name = str(args.get("name") or "")
        expected_mini_app_declared_scopes = [
            str(item) for item in (args.get("declared_scopes") or [])]
        expected_mini_app_dependencies = [
            str(item) for item in (args.get("dependencies") or [])]
        spec = args.get("spec")
        expected_mini_app_spec = dict(spec) if isinstance(spec, dict) else {}
    elif name == "mini_app_write_logic":
        source = args.get("source")
        if isinstance(source, str):
            try:
                from core.mini_app_service import logic_source_sha256

                expected_mini_app_source_sha256 = logic_source_sha256(source)
            except Exception:  # noqa: BLE001 - verifier refuses absent binding
                expected_mini_app_source_sha256 = ""
    elif name == "mini_app_revert_logic":
        expected_mini_app_version = str(args.get("version"))
    elif name == "mini_app_db_write":
        expected_db_op = str(args.get("op") or "")
        expected_db_series = args.get("series")
        expected_db_data = args.get("data")
        expected_db_record_id = str(args.get("record_id") or "")
        expected_db_append_id = str(args.get("id") or "")
        filt = args.get("filter")
        expected_db_filter = dict(filt) if isinstance(filt, dict) else {}

    return {
        "_oracle_expected_payload_sha256": expected_digest,
        "_oracle_expected_request_sha256": str(request_sha256 or ""),
        "_oracle_expected_operation_id": expected_operation,
        "_oracle_expected_organization_id": expected_organization,
        "_oracle_expected_provider": expected_provider,
        "_oracle_expected_target": expected_target,
        "_oracle_expected_canvas_id": expected_canvas_id,
        "_oracle_expected_restore_audit_id": expected_restore_audit_id,
        "_oracle_expected_prior_audit_id": expected_prior_audit_id,
        "_oracle_expected_tombstone_audit_id": expected_tombstone_audit_id,
        "_oracle_expected_source_audit_id": expected_source_audit_id,
        "_oracle_expected_canvas_content_sha256": (
            expected_canvas_content_sha256),
        "_oracle_expected_material_sha256": expected_material_sha256,
        "_oracle_expected_material": expected_presentation_material,
        "_oracle_expected_tenant_id": expected_tenant_id,
        "_oracle_expected_actor_id": expected_actor_id,
        "_oracle_expected_goal_id": expected_goal_id,
        "_oracle_expected_goal_title": expected_goal_title,
        "_oracle_expected_workspace_id": expected_workspace_id,
        "_oracle_expected_agent_id": expected_agent_id,
        "_oracle_expected_chart_type": expected_chart_type,
        "_oracle_expected_data_points": expected_data_points,
        "_oracle_expected_title": expected_present_title,
        "_oracle_expected_task_title": expected_task_title,
        "_oracle_expected_board_id": expected_board_id,
        "_oracle_expected_shopify_product": expected_shopify_product,
        "_oracle_expected_shopify_blog": expected_shopify_blog,
        "_oracle_expected_shopify_article": expected_shopify_article,
        "_oracle_expected_shopify_fulfillment": expected_shopify_fulfillment,
        "_oracle_expected_radio_message": expected_radio_message,
        "_oracle_expected_app_id": expected_app_id,
        "_oracle_expected_tests": expected_tests,
        "_oracle_expected_tests_sha256": expected_tests_sha256,
        "_oracle_expected_mini_app_name": expected_mini_app_name,
        "_oracle_expected_mini_app_declared_scopes": (
            expected_mini_app_declared_scopes),
        "_oracle_expected_mini_app_dependencies": (
            expected_mini_app_dependencies),
        "_oracle_expected_mini_app_spec": expected_mini_app_spec,
        "_oracle_expected_mini_app_source_sha256": (
            expected_mini_app_source_sha256),
        "_oracle_expected_mini_app_version": expected_mini_app_version,
        "_oracle_expected_db_op": expected_db_op,
        "_oracle_expected_db_series": expected_db_series,
        "_oracle_expected_db_data": expected_db_data,
        "_oracle_expected_db_record_id": expected_db_record_id,
        "_oracle_expected_db_append_id": expected_db_append_id,
        "_oracle_expected_db_filter": expected_db_filter,
    }
