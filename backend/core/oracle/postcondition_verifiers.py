"""
Concrete postcondition verifiers for high-risk mutating actions (W2, P3a).

Each verifier re-derives success against the system of record (NOT the tool's
own claim). Add new mutating actions here by ``@register_postcondition``.

Pattern (verify-before-retry, arXiv 2608.02645): on an ambiguous timeout,
call ``validate(action, ctx)`` BEFORE retrying — if the postcondition is
already met, the action succeeded despite the timeout; don't duplicate it.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, Optional

from core.oracle import (
    OracleResult,
    register_durable_receipt_matcher,
    register_durable_receipt_projector,
    register_postcondition,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: Any) -> str:
    return str(value or "").strip().lower()


def _valid_digest(value: Any) -> bool:
    return bool(_SHA256_RE.match(_digest(value)))


def _first_field(fields: Any, names: Iterable[str]) -> Optional[Any]:
    if not isinstance(fields, dict):
        return None
    for name in names:
        value = fields.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def _material_fields(action: str) -> tuple:
    """Required material-field aliases for each connected mutation class."""
    if action.endswith("books.create_estimate"):
        return (
            ("customer_id",),
            ("currency_code", "currency"),
            ("date", "estimate_date"),
            ("reference_number",),
            ("total", "grand_total"),
            ("line_items", "lines"),
        )
    if action.endswith("books.create_bill"):
        return (
            ("vendor_id",),
            ("currency_code", "currency"),
            ("date", "bill_date"),
            ("reference_number", "bill_number"),
            ("total", "grand_total"),
            ("line_items", "lines"),
        )
    if action.endswith("outlook.create_draft"):
        return (
            ("subject",),
            ("body",),
            ("toRecipients", "to_recipients"),
        )
    return ()


@register_postcondition("trigger_workflow")
async def _verify_workflow_triggered(ctx: Dict[str, Any]) -> OracleResult:
    """A triggered workflow must actually exist in the DB and be runnable."""
    workflow_id = ctx.get("workflow_id")
    db = ctx.get("db")
    if not workflow_id or not db:
        return OracleResult("trigger_workflow", False, "missing workflow_id or db session")
    try:
        from core.models import Workflow
        wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if wf is None:
            return OracleResult("trigger_workflow", False, f"workflow {workflow_id} not in DB")
        active = str(getattr(wf, "status", "")).lower() in {"active", "running", "enabled", "true"}
        return OracleResult(
            "trigger_workflow", verified=active,
            evidence=f"workflow.status == {getattr(wf, 'status', None)!r}",
        )
    except Exception as e:
        return OracleResult("trigger_workflow", False, f"DB read-back failed: {e}")


async def _verify_connected_mutation(ctx: Dict[str, Any]) -> OracleResult:
    """Verify a registered connected write's authoritative readback receipt.

    The production action already performs provider readback. The oracle
    independently checks that the returned receipt is bound to the same remote
    object, carries a syntactically valid payload digest that agrees with the
    independently supplied request digest, and did not report an uncertain,
    conflict or incomplete verification. It never treats a bare success label
    as proof.
    """
    action = str(ctx.get("_oracle_action") or "connected.mutation")
    if str(ctx.get("action_result") or "").strip().lower() != "applied":
        return OracleResult(
            action, False,
            f"action_result == {ctx.get('action_result')!r}, not applied")
    remote_id = str(ctx.get("remote_id") or "").strip()
    if not remote_id:
        return OracleResult(action, False, "no remote_id in the result")
    read_receipt = ctx.get("read_receipt")
    if not isinstance(read_receipt, dict) or not read_receipt:
        return OracleResult(action, False, "no authoritative read_receipt")
    if str(read_receipt.get("resource_id") or "") != remote_id:
        return OracleResult(
            action, False,
            "read_receipt.resource_id does not match remote_id")
    coverage = str(read_receipt.get("coverage") or "").lower()
    if coverage not in {"single", "complete"}:
        return OracleResult(
            action, False, f"read_receipt.coverage == {coverage!r}")
    fields = read_receipt.get("fields")
    if not isinstance(fields, dict) or not fields:
        return OracleResult(
            action, False,
            "read_receipt carries no complete material-field mapping")
    required = _material_fields(action)
    missing_material = [
        aliases[0] for aliases in required
        if _first_field(fields, aliases) is None
    ]
    if missing_material:
        return OracleResult(
            action, False,
            "read_receipt is missing material field(s): "
            + ", ".join(missing_material))
    verification = ctx.get("verification")
    if not isinstance(verification, dict) or not verification:
        return OracleResult(
            action, False, "no explicit verification object")
    status = str(verification.get("status") or "").lower()
    if status != "verified":
        return OracleResult(
            action, False, f"verification.status == {status!r}, not verified")
    if verification.get("mismatches"):
        return OracleResult(
            action, False, "verification reports mismatches")
    if verification.get("missing_fields"):
        return OracleResult(
            action, False, "verification reports missing fields")
    receipt = ctx.get("provider_receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    top_digest = _digest(ctx.get("payload_sha256"))
    receipt_digest = _digest(receipt.get("payload_sha256"))
    if not top_digest or not receipt_digest:
        return OracleResult(action, False, "no payload digest in the receipt")
    if not _valid_digest(top_digest) or not _valid_digest(receipt_digest):
        return OracleResult(
            action, False, "payload digest is not a 64-character hex digest")
    if top_digest != receipt_digest:
        return OracleResult(
            action, False,
            "top-level and provider-receipt payload digests disagree")
    expected_digest = _digest(
        ctx.get("_oracle_expected_payload_sha256"))
    if expected_digest:
        if not _valid_digest(expected_digest):
            return OracleResult(
                action, False,
                "expected request payload digest is malformed")
        if expected_digest != top_digest:
            return OracleResult(
                action, False,
                "returned payload digest does not match the expected request")
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "")
    if expected_operation:
        observed_operation = str(
            receipt.get("operation_id") or verification.get("operation_id")
            or "")
        if not observed_operation:
            return OracleResult(
                action, False,
                "provider receipt carries no operation identity")
        if observed_operation != expected_operation:
            return OracleResult(
                action, False,
                "returned operation id does not match the expected operation")
    expected_org = str(
        ctx.get("_oracle_expected_organization_id") or "")
    if expected_org:
        observed_org = str(
            read_receipt.get("account_id")
            or read_receipt.get("organization_id") or "")
        if not observed_org:
            return OracleResult(
                action, False,
                "readback carries no account/organization identity")
        if observed_org != expected_org:
            return OracleResult(
                action, False,
                "readback account/organization does not match the request")
    expected_provider = str(
        ctx.get("_oracle_expected_provider") or "")
    if expected_provider:
        observed_provider = str(ctx.get("provider") or "")
        if not observed_provider:
            return OracleResult(
                action, False, "result carries no provider identity")
        if observed_provider != expected_provider:
            return OracleResult(
                action, False,
                "result provider does not match the expected provider")
        receipt_provider = str(read_receipt.get("provider") or "")
        if receipt_provider and receipt_provider != expected_provider:
            return OracleResult(
                action, False,
                "readback provider does not match the expected provider")
    expected_target = str(
        ctx.get("_oracle_expected_target") or "")
    if expected_target:
        observed_target = _first_field(
            fields, ("reference_number", "bill_number", "external_id",
                     "subject"))
        if observed_target is None:
            return OracleResult(
                action, False,
                "readback carries no target identity")
        if " ".join(str(observed_target).split()).casefold() != (
                " ".join(expected_target.split()).casefold()):
            return OracleResult(
                action, False,
                "readback target does not match the authorized request")
    verification_digest = _digest(verification.get("payload_sha256"))
    if verification_digest:
        if not _valid_digest(verification_digest):
            return OracleResult(
                action, False,
                "verification payload digest is malformed")
        if verification_digest != top_digest:
            return OracleResult(
                action, False,
                "verification payload digest disagrees with the receipt")
    return OracleResult(
        action, True,
        f"remote {remote_id} read back ({coverage}); "
        f"payload {top_digest[:12]}")


def _connected_postcondition(action: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        return await _verify_connected_mutation(
            {**ctx, "_oracle_action": action})
    return _verify


for _action in (
    "brennan.books.create_bill",
    "brennan.books.create_estimate",
    "brennan.outlook.create_draft",
    "connected.books.create_bill",
    "connected.books.create_estimate",
    "connected.outlook.create_draft",
):
    register_postcondition(_action)(_connected_postcondition(_action))


@register_durable_receipt_projector("shopify_create_product")
def _shopify_durable_receipt_projection(
    result: Dict[str, Any], expected: Dict[str, Any],
) -> Dict[str, Any]:
    from core.shopify_mutations import durable_product_receipt_projection

    return durable_product_receipt_projection(result, expected)


@register_durable_receipt_matcher("shopify_create_product")
def _shopify_durable_receipt_conflicts(
    expected: Dict[str, Any], durable_result: Dict[str, Any],
) -> Iterable[str]:
    from core.shopify_mutations import durable_product_material_conflicts

    return durable_product_material_conflicts(expected, durable_result)


@register_postcondition("shopify_create_product")
async def _verify_shopify_create_product(
    ctx: Dict[str, Any],
) -> OracleResult:
    """Verify one Shopify product create by an exact fresh readback.

    The frozen accepted material and the durable operation identity are
    supplied by the server-owned request snapshot.  A transport label, a
    matching title, or the producer's own receipt is insufficient: the exact
    returned id is re-read from the *current* workspace store through the real
    Shopify service, and the readback must match the accepted material.  An
    absent/contradictory readback is unverified, never success.
    """
    from core.shopify_mutations import (
        material_mismatches,
        observed_product_material,
    )

    action = "shopify_create_product"
    if str(ctx.get("action_result") or "").strip().lower() != "applied":
        return OracleResult(
            action, False,
            f"action_result == {ctx.get('action_result')!r}, not applied")

    remote_id = str(ctx.get("remote_id") or "").strip()
    if not remote_id:
        return OracleResult(
            action, False,
            "no exact remote id in the result; an unidentifiable effect is "
            "uncertain, not safe to recreate")

    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    if not expected_operation:
        return OracleResult(action, False, "no frozen operation identity")

    expected_digest = _digest(
        ctx.get("_oracle_expected_payload_sha256"))
    if not _valid_digest(expected_digest):
        return OracleResult(
            action, False, "no valid frozen request payload digest")
    result_digest = _digest(ctx.get("payload_sha256"))
    if not _valid_digest(result_digest):
        return OracleResult(
            action, False, "result carries no valid payload digest")
    if result_digest != expected_digest:
        return OracleResult(
            action, False,
            "returned payload digest does not match the expected request")

    receipt = ctx.get("provider_receipt")
    if not isinstance(receipt, dict) or not receipt:
        return OracleResult(action, False, "no provider receipt")
    if str(receipt.get("operation_id") or "") != expected_operation:
        return OracleResult(
            action, False,
            "returned operation id does not match the expected operation")
    if _digest(receipt.get("payload_sha256")) != expected_digest:
        return OracleResult(
            action, False,
            "provider receipt payload digest does not match the request")

    expected_material = ctx.get("_oracle_expected_shopify_product")
    if not isinstance(expected_material, dict) or not expected_material:
        return OracleResult(
            action, False, "no frozen accepted product material")

    read_receipt = ctx.get("read_receipt")
    if not isinstance(read_receipt, dict) or not read_receipt:
        return OracleResult(action, False, "no authoritative read_receipt")
    if str(read_receipt.get("resource_id") or "") != remote_id:
        return OracleResult(
            action, False,
            "read_receipt.resource_id does not match the created product id")
    coverage = str(read_receipt.get("coverage") or "").lower()
    if coverage not in {"single", "complete"}:
        return OracleResult(
            action, False, f"read_receipt.coverage == {coverage!r}")
    receipt_material = read_receipt.get("fields")
    if not isinstance(receipt_material, dict) or not receipt_material:
        return OracleResult(
            action, False,
            "read_receipt carries no complete material mapping")
    receipt_mismatches = material_mismatches(
        expected_material, receipt_material)
    if receipt_mismatches:
        return OracleResult(
            action, False,
            "producer readback does not match the accepted material: "
            + ", ".join(receipt_mismatches))

    # Re-read the exact resource from the CURRENT workspace store.  This is
    # the independent system-of-record check; the producer's receipt is only
    # evidence input, never the verdict.
    from core.action_registry import _resolve_shopify_store

    token, shop = _resolve_shopify_store(ctx)
    if not token or not shop:
        return OracleResult(
            action, False, "no current workspace store authority")
    observed_shop = str(
        read_receipt.get("account_id") or read_receipt.get("shop") or "")
    if observed_shop and observed_shop != shop:
        return OracleResult(
            action, False,
            "readback store does not match the current workspace store")
    receipt_shop = str(receipt.get("shop") or "")
    if receipt_shop and receipt_shop != shop:
        return OracleResult(
            action, False,
            "provider receipt store does not match the current workspace "
            "store")

    from integrations.shopify_service import ShopifyService

    service = ShopifyService()
    try:
        observed = await service.get_product(
            token, shop, remote_id)
    except Exception as exc:  # noqa: BLE001 - unavailable is not verified
        return OracleResult(
            action, False,
            "independent Shopify readback unavailable: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    observed = observed if isinstance(observed, dict) else {}
    observed_id = str(observed.get("id") or "").strip()
    if not observed_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned no exact product id")
    if observed_id != remote_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned a different product id")

    observed_material = observed_product_material(observed)
    mismatches = material_mismatches(
        expected_material, observed_material)
    if mismatches:
        return OracleResult(
            action, False,
            "independent Shopify readback contradicts the accepted material: "
            + ", ".join(mismatches))
    from core.shopify_mutations import verify_product_image_content

    try:
        image_content = await verify_product_image_content(
            service, token, shop, remote_id, expected_material, observed)
    except Exception as exc:  # noqa: BLE001 - unavailable proof is not success
        return OracleResult(
            action, False,
            "independent image-content proof unavailable: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    if image_content.get("mismatches"):
        return OracleResult(
            action, False,
            "independent image-content proof contradicts the accepted image: "
            + ", ".join(image_content["mismatches"]))
    return OracleResult(
        action, True,
        f"Shopify product {remote_id} re-read from {shop}; accepted material "
        f"and image content match (payload {expected_digest[:12]})")


@register_durable_receipt_projector("shopify_create_blog")
def _shopify_blog_durable_receipt_projection(
    result: Dict[str, Any], expected: Dict[str, Any],
) -> Dict[str, Any]:
    from core.shopify_mutations import durable_blog_receipt_projection

    return durable_blog_receipt_projection(result, expected)


@register_durable_receipt_matcher("shopify_create_blog")
def _shopify_blog_durable_receipt_conflicts(
    expected: Dict[str, Any], durable_result: Dict[str, Any],
) -> Iterable[str]:
    from core.shopify_mutations import durable_blog_material_conflicts

    return durable_blog_material_conflicts(expected, durable_result)


@register_postcondition("shopify_create_blog")
async def _verify_shopify_create_blog(
    ctx: Dict[str, Any],
) -> OracleResult:
    """Verify one Shopify blog create by an exact fresh readback.

    The frozen accepted title/handle and the durable operation identity come
    from the server-owned request snapshot.  A transport 201, a matching
    title, or the producer's own receipt is insufficient: the exact returned
    id is re-read from the *current* workspace store through the real Shopify
    service, and the readback must match the accepted material.
    """
    from core.shopify_mutations import (
        material_mismatches,
        observed_blog_material,
    )

    action = "shopify_create_blog"
    if str(ctx.get("action_result") or "").strip().lower() != "applied":
        return OracleResult(
            action, False,
            f"action_result == {ctx.get('action_result')!r}, not applied")

    remote_id = str(ctx.get("remote_id") or "").strip()
    if not remote_id:
        return OracleResult(
            action, False,
            "no exact remote id in the result; an unidentifiable effect is "
            "uncertain, not safe to recreate")

    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    if not expected_operation:
        return OracleResult(action, False, "no frozen operation identity")

    expected_digest = _digest(
        ctx.get("_oracle_expected_payload_sha256"))
    if not _valid_digest(expected_digest):
        return OracleResult(
            action, False, "no valid frozen request payload digest")
    result_digest = _digest(ctx.get("payload_sha256"))
    if not _valid_digest(result_digest):
        return OracleResult(
            action, False, "result carries no valid payload digest")
    if result_digest != expected_digest:
        return OracleResult(
            action, False,
            "returned payload digest does not match the expected request")

    receipt = ctx.get("provider_receipt")
    if not isinstance(receipt, dict) or not receipt:
        return OracleResult(action, False, "no provider receipt")
    if str(receipt.get("operation_id") or "") != expected_operation:
        return OracleResult(
            action, False,
            "returned operation id does not match the expected operation")
    if _digest(receipt.get("payload_sha256")) != expected_digest:
        return OracleResult(
            action, False,
            "provider receipt payload digest does not match the request")

    expected_material = ctx.get("_oracle_expected_shopify_blog")
    if not isinstance(expected_material, dict) or not expected_material:
        return OracleResult(
            action, False, "no frozen accepted blog material")

    read_receipt = ctx.get("read_receipt")
    if not isinstance(read_receipt, dict) or not read_receipt:
        return OracleResult(action, False, "no authoritative read_receipt")
    if str(read_receipt.get("resource_id") or "") != remote_id:
        return OracleResult(
            action, False,
            "read_receipt.resource_id does not match the created blog id")
    coverage = str(read_receipt.get("coverage") or "").lower()
    if coverage not in {"single", "complete"}:
        return OracleResult(
            action, False, f"read_receipt.coverage == {coverage!r}")
    receipt_material = read_receipt.get("fields")
    if not isinstance(receipt_material, dict) or not receipt_material:
        return OracleResult(
            action, False,
            "read_receipt carries no complete material mapping")
    receipt_mismatches = material_mismatches(
        expected_material, receipt_material)
    if receipt_mismatches:
        return OracleResult(
            action, False,
            "producer readback does not match the accepted material: "
            + ", ".join(receipt_mismatches))

    # Re-read the exact resource from the CURRENT workspace store.  This is
    # the independent system-of-record check; the producer's receipt is only
    # evidence input, never the verdict.
    from core.action_registry import _resolve_shopify_store

    token, shop = _resolve_shopify_store(ctx)
    if not token or not shop:
        return OracleResult(
            action, False, "no current workspace store authority")
    observed_shop = str(
        read_receipt.get("account_id") or read_receipt.get("shop") or "")
    if observed_shop and observed_shop != shop:
        return OracleResult(
            action, False,
            "readback store does not match the current workspace store")
    receipt_shop = str(receipt.get("shop") or "")
    if receipt_shop and receipt_shop != shop:
        return OracleResult(
            action, False,
            "provider receipt store does not match the current workspace "
            "store")

    from integrations.shopify_service import ShopifyService

    try:
        observed = await ShopifyService().get_blog(
            token, shop, remote_id)
    except Exception as exc:  # noqa: BLE001 - unavailable is not verified
        return OracleResult(
            action, False,
            "independent Shopify readback unavailable: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    observed = observed if isinstance(observed, dict) else {}
    observed_id = str(observed.get("id") or "").strip()
    if not observed_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned no exact blog id")
    if observed_id != remote_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned a different blog id")

    observed_material = observed_blog_material(observed)
    mismatches = material_mismatches(
        expected_material, observed_material)
    if mismatches:
        return OracleResult(
            action, False,
            "independent Shopify readback contradicts the accepted material: "
            + ", ".join(mismatches))
    return OracleResult(
        action, True,
        f"Shopify blog {remote_id} re-read from {shop}; accepted material "
        f"matches (payload {expected_digest[:12]})")


@register_durable_receipt_projector("shopify_create_article")
def _shopify_article_durable_receipt_projection(
    result: Dict[str, Any], expected: Dict[str, Any],
) -> Dict[str, Any]:
    from core.shopify_mutations import durable_article_receipt_projection

    return durable_article_receipt_projection(result, expected)


@register_durable_receipt_matcher("shopify_create_article")
def _shopify_article_durable_receipt_conflicts(
    expected: Dict[str, Any], durable_result: Dict[str, Any],
) -> Iterable[str]:
    from core.shopify_mutations import durable_article_material_conflicts

    return durable_article_material_conflicts(expected, durable_result)


@register_postcondition("shopify_create_article")
async def _verify_shopify_create_article(
    ctx: Dict[str, Any],
) -> OracleResult:
    """Verify one Shopify article create by an exact fresh readback.

    The frozen accepted blog/title/body/author/tags/published material and the
    durable operation identity come from the server-owned request snapshot.
    The exact returned id is re-read from the authorized blog on the CURRENT
    workspace store through the real Shopify service; a transport 201, a
    matching title, or the producer's own receipt is never the verdict.
    """
    from core.shopify_mutations import (
        material_mismatches,
        observed_article_material,
    )

    action = "shopify_create_article"
    if str(ctx.get("action_result") or "").strip().lower() != "applied":
        return OracleResult(
            action, False,
            f"action_result == {ctx.get('action_result')!r}, not applied")

    remote_id = str(ctx.get("remote_id") or "").strip()
    if not remote_id:
        return OracleResult(
            action, False,
            "no exact remote id in the result; an unidentifiable effect is "
            "uncertain, not safe to recreate")

    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    if not expected_operation:
        return OracleResult(action, False, "no frozen operation identity")

    expected_digest = _digest(
        ctx.get("_oracle_expected_payload_sha256"))
    if not _valid_digest(expected_digest):
        return OracleResult(
            action, False, "no valid frozen request payload digest")
    result_digest = _digest(ctx.get("payload_sha256"))
    if not _valid_digest(result_digest):
        return OracleResult(
            action, False, "result carries no valid payload digest")
    if result_digest != expected_digest:
        return OracleResult(
            action, False,
            "returned payload digest does not match the expected request")

    receipt = ctx.get("provider_receipt")
    if not isinstance(receipt, dict) or not receipt:
        return OracleResult(action, False, "no provider receipt")
    if str(receipt.get("operation_id") or "") != expected_operation:
        return OracleResult(
            action, False,
            "returned operation id does not match the expected operation")
    if _digest(receipt.get("payload_sha256")) != expected_digest:
        return OracleResult(
            action, False,
            "provider receipt payload digest does not match the request")

    expected_material = ctx.get("_oracle_expected_shopify_article")
    if not isinstance(expected_material, dict) or not expected_material:
        return OracleResult(
            action, False, "no frozen accepted article material")
    expected_blog_id = str(
        expected_material.get("blog_id") or "").strip()
    if not expected_blog_id:
        return OracleResult(
            action, False, "no frozen authorized blog id")

    read_receipt = ctx.get("read_receipt")
    if not isinstance(read_receipt, dict) or not read_receipt:
        return OracleResult(action, False, "no authoritative read_receipt")
    if str(read_receipt.get("resource_id") or "") != remote_id:
        return OracleResult(
            action, False,
            "read_receipt.resource_id does not match the created article id")
    coverage = str(read_receipt.get("coverage") or "").lower()
    if coverage not in {"single", "complete"}:
        return OracleResult(
            action, False, f"read_receipt.coverage == {coverage!r}")
    receipt_material = read_receipt.get("fields")
    if not isinstance(receipt_material, dict) or not receipt_material:
        return OracleResult(
            action, False,
            "read_receipt carries no complete material mapping")
    receipt_mismatches = material_mismatches(
        expected_material, receipt_material)
    if receipt_mismatches:
        return OracleResult(
            action, False,
            "producer readback does not match the accepted material: "
            + ", ".join(receipt_mismatches))

    # Re-read the exact resource from the CURRENT workspace store.  This is
    # the independent system-of-record check; the producer's receipt is only
    # evidence input, never the verdict.
    from core.action_registry import _resolve_shopify_store

    token, shop = _resolve_shopify_store(ctx)
    if not token or not shop:
        return OracleResult(
            action, False, "no current workspace store authority")
    observed_shop = str(
        read_receipt.get("account_id") or read_receipt.get("shop") or "")
    if observed_shop and observed_shop != shop:
        return OracleResult(
            action, False,
            "readback store does not match the current workspace store")
    receipt_shop = str(receipt.get("shop") or "")
    if receipt_shop and receipt_shop != shop:
        return OracleResult(
            action, False,
            "provider receipt store does not match the current workspace "
            "store")

    from integrations.shopify_service import ShopifyService

    try:
        observed = await ShopifyService().get_article(
            token, shop, expected_blog_id, remote_id)
    except Exception as exc:  # noqa: BLE001 - unavailable is not verified
        return OracleResult(
            action, False,
            "independent Shopify readback unavailable: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    observed = observed if isinstance(observed, dict) else {}
    observed_id = str(observed.get("id") or "").strip()
    if not observed_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned no exact article id")
    if observed_id != remote_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned a different article id")

    observed_material = observed_article_material(observed)
    mismatches = material_mismatches(
        expected_material, observed_material)
    if mismatches:
        return OracleResult(
            action, False,
            "independent Shopify readback contradicts the accepted material: "
            + ", ".join(mismatches))
    return OracleResult(
        action, True,
        f"Shopify article {remote_id} re-read from {shop} blog "
        f"{expected_blog_id}; accepted material matches "
        f"(payload {expected_digest[:12]})")


@register_durable_receipt_projector("radio.send_message")
def _radio_message_durable_receipt_projection(
    result: Dict[str, Any], expected: Dict[str, Any],
) -> Dict[str, Any]:
    from core.agent_radio.radio_mutations import (
        durable_radio_receipt_projection,
    )

    return durable_radio_receipt_projection(result, expected)


@register_durable_receipt_matcher("radio.send_message")
def _radio_message_durable_receipt_conflicts(
    expected: Dict[str, Any], durable_result: Dict[str, Any],
) -> Iterable[str]:
    from core.agent_radio.radio_mutations import (
        durable_radio_material_conflicts,
    )

    return durable_radio_material_conflicts(expected, durable_result)


@register_postcondition("radio.send_message")
async def _verify_radio_send_message(
    ctx: Dict[str, Any],
) -> OracleResult:
    """Verify one radio message by exact id/material from a fresh session.

    The durable row locates the message; it does not supply authority.  The
    verifier re-reads the exact ``LateralMessage`` and its ``AgentThread`` in a
    fresh session and compares the server-owned sender, thread, content,
    mention set, response flag and tenant scope with the frozen request.
    """
    from core.agent_radio.radio_mutations import (
        observed_message_material,
        radio_material_mismatches,
        read_message,
        read_thread,
    )

    action = "radio.send_message"
    if str(ctx.get("action_result") or "").strip().lower() != "applied":
        return OracleResult(
            action, False,
            f"action_result == {ctx.get('action_result')!r}, not applied")

    remote_id = str(ctx.get("remote_id") or "").strip()
    if not remote_id:
        return OracleResult(
            action, False,
            "no exact message id in the result; an unidentifiable effect is "
            "uncertain, not safe to recreate")

    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    if not expected_operation:
        return OracleResult(action, False, "no frozen operation identity")

    expected_digest = _digest(
        ctx.get("_oracle_expected_payload_sha256"))
    if not _valid_digest(expected_digest):
        return OracleResult(
            action, False, "no valid frozen request payload digest")
    result_digest = _digest(ctx.get("payload_sha256"))
    if not _valid_digest(result_digest):
        return OracleResult(
            action, False, "result carries no valid payload digest")
    if result_digest != expected_digest:
        return OracleResult(
            action, False,
            "returned payload digest does not match the expected request")

    receipt = ctx.get("provider_receipt")
    if not isinstance(receipt, dict) or not receipt:
        return OracleResult(action, False, "no provider receipt")
    if str(receipt.get("operation_id") or "") != expected_operation:
        return OracleResult(
            action, False,
            "returned operation id does not match the expected operation")
    if _digest(receipt.get("payload_sha256")) != expected_digest:
        return OracleResult(
            action, False,
            "provider receipt payload digest does not match the request")

    expected_material = ctx.get("_oracle_expected_radio_message")
    if not isinstance(expected_material, dict) or not expected_material:
        return OracleResult(
            action, False, "no frozen accepted radio message material")
    expected_thread_id = str(
        expected_material.get("thread_id") or "").strip()
    if not expected_thread_id:
        return OracleResult(action, False, "no frozen radio thread id")

    read_receipt = ctx.get("read_receipt")
    if not isinstance(read_receipt, dict) or not read_receipt:
        return OracleResult(action, False, "no authoritative read_receipt")
    if str(read_receipt.get("resource_id") or "") != remote_id:
        return OracleResult(
            action, False,
            "read_receipt.resource_id does not match the message id")
    coverage = str(read_receipt.get("coverage") or "").lower()
    if coverage not in {"single", "complete"}:
        return OracleResult(
            action, False, f"read_receipt.coverage == {coverage!r}")
    receipt_material = read_receipt.get("fields")
    if not isinstance(receipt_material, dict) or not receipt_material:
        return OracleResult(
            action, False,
            "read_receipt carries no complete material mapping")
    receipt_mismatches = radio_material_mismatches(
        expected_material, receipt_material)
    if receipt_mismatches:
        return OracleResult(
            action, False,
            "producer readback does not match the accepted material: "
            + ", ".join(receipt_mismatches))

    def _read(session):
        return (
            read_message(session, remote_id),
            read_thread(session, expected_thread_id),
        )

    try:
        # A fresh session is mandatory: the caller's identity map could
        # otherwise certify an uncommitted/expired row.
        message, thread = _fresh_read_with_db(ctx, _read)
    except Exception as exc:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            action, False,
            "radio readback failed: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    if message is None or thread is None:
        return OracleResult(
            action, False,
            "radio message/thread absent in the authoritative store")
    observed_id = str(getattr(message, "id", "") or "").strip()
    if observed_id != remote_id:
        return OracleResult(
            action, False,
            "independent radio readback returned a different message id")
    observed = observed_message_material(message, thread)
    mismatches = radio_material_mismatches(expected_material, observed)
    if mismatches:
        return OracleResult(
            action, False,
            "independent radio readback contradicts the accepted material: "
            + ", ".join(mismatches))
    return OracleResult(
        action, True,
        f"radio message {remote_id} re-read in thread {expected_thread_id}; "
        f"authorized material matches (payload {expected_digest[:12]})")


@register_durable_receipt_projector("shopify_create_fulfillment")
def _shopify_fulfillment_durable_receipt_projection(
    result: Dict[str, Any], expected: Dict[str, Any],
) -> Dict[str, Any]:
    from core.shopify_mutations import (
        durable_fulfillment_receipt_projection,
    )

    return durable_fulfillment_receipt_projection(result, expected)


@register_durable_receipt_matcher("shopify_create_fulfillment")
def _shopify_fulfillment_durable_receipt_conflicts(
    expected: Dict[str, Any], durable_result: Dict[str, Any],
) -> Iterable[str]:
    from core.shopify_mutations import (
        durable_fulfillment_material_conflicts,
    )

    return durable_fulfillment_material_conflicts(expected, durable_result)


@register_postcondition("shopify_create_fulfillment")
async def _verify_shopify_create_fulfillment(
    ctx: Dict[str, Any],
) -> OracleResult:
    """Verify one Shopify fulfillment create by exact by-id readback.

    The registry authorizes the order plus optional location/tracking.  The
    fulfillment-order/line-item/quantity set is resolved server-side before
    dispatch and bound as a durable dispatch plan; the fresh exact-id readback
    must match both the authorized material and that plan.  Missing or
    contradictory proof stays unverified.
    """
    from core.shopify_mutations import (
        authoritative_fulfillment_order_ids,
        fulfillment_plan_mismatches,
        fulfillment_status_issue,
        material_mismatches,
        observed_fulfillment_material,
    )

    action = "shopify_create_fulfillment"
    if str(ctx.get("action_result") or "").strip().lower() != "applied":
        return OracleResult(
            action, False,
            f"action_result == {ctx.get('action_result')!r}, not applied")

    remote_id = str(ctx.get("remote_id") or "").strip()
    if not remote_id:
        return OracleResult(
            action, False,
            "no exact remote id in the result; an unidentifiable effect is "
            "uncertain, not safe to recreate")

    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    if not expected_operation:
        return OracleResult(action, False, "no frozen operation identity")

    expected_digest = _digest(
        ctx.get("_oracle_expected_payload_sha256"))
    if not _valid_digest(expected_digest):
        return OracleResult(
            action, False, "no valid frozen request payload digest")
    result_digest = _digest(ctx.get("payload_sha256"))
    if not _valid_digest(result_digest):
        return OracleResult(
            action, False, "result carries no valid payload digest")
    if result_digest != expected_digest:
        return OracleResult(
            action, False,
            "returned payload digest does not match the expected request")

    receipt = ctx.get("provider_receipt")
    if not isinstance(receipt, dict) or not receipt:
        return OracleResult(action, False, "no provider receipt")
    if str(receipt.get("operation_id") or "") != expected_operation:
        return OracleResult(
            action, False,
            "returned operation id does not match the expected operation")
    if _digest(receipt.get("payload_sha256")) != expected_digest:
        return OracleResult(
            action, False,
            "provider receipt payload digest does not match the request")

    expected_material = ctx.get("_oracle_expected_shopify_fulfillment")
    if not isinstance(expected_material, dict) or not expected_material:
        return OracleResult(
            action, False, "no frozen accepted fulfillment material")

    dispatch_plan = ctx.get("dispatch_plan")
    if not isinstance(dispatch_plan, dict) or not dispatch_plan:
        return OracleResult(
            action, False,
            "no server-resolved fulfillment dispatch plan")

    read_receipt = ctx.get("read_receipt")
    if not isinstance(read_receipt, dict) or not read_receipt:
        return OracleResult(action, False, "no authoritative read_receipt")
    if str(read_receipt.get("resource_id") or "") != remote_id:
        return OracleResult(
            action, False,
            "read_receipt.resource_id does not match the created fulfillment")
    coverage = str(read_receipt.get("coverage") or "").lower()
    if coverage not in {"single", "complete"}:
        return OracleResult(
            action, False, f"read_receipt.coverage == {coverage!r}")
    receipt_material = read_receipt.get("fields")
    if not isinstance(receipt_material, dict) or not receipt_material:
        return OracleResult(
            action, False,
            "read_receipt carries no complete material mapping")
    receipt_mismatches = material_mismatches(
        expected_material, receipt_material)
    receipt_mismatches.extend(fulfillment_plan_mismatches(
        dispatch_plan, receipt_material))
    if receipt_mismatches:
        return OracleResult(
            action, False,
            "producer readback does not match the authorized/dispatched "
            "material: " + ", ".join(receipt_mismatches))

    # Re-read the exact resource from the CURRENT workspace store.  This is
    # the independent system-of-record check; the producer's receipt is only
    # evidence input, never the verdict.
    from core.action_registry import _resolve_shopify_store

    token, shop = _resolve_shopify_store(ctx)
    if not token or not shop:
        return OracleResult(
            action, False, "no current workspace store authority")
    observed_shop = str(
        read_receipt.get("account_id") or read_receipt.get("shop") or "")
    if observed_shop and observed_shop != shop:
        return OracleResult(
            action, False,
            "readback store does not match the current workspace store")
    receipt_shop = str(receipt.get("shop") or "")
    if receipt_shop and receipt_shop != shop:
        return OracleResult(
            action, False,
            "provider receipt store does not match the current workspace "
            "store")

    from integrations.shopify_service import ShopifyService

    service = ShopifyService()
    parent_order_id = str(expected_material.get("order_id") or "").strip()
    if not parent_order_id:
        return OracleResult(
            action, False,
            "no frozen parent order for the exact fulfillment read")
    try:
        observed = await service.get_fulfillment(
            token, shop, parent_order_id, remote_id)
    except Exception as exc:  # noqa: BLE001 - unavailable is not verified
        return OracleResult(
            action, False,
            "independent Shopify readback unavailable: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    observed = observed if isinstance(observed, dict) else {}
    observed_id = str(observed.get("id") or "").strip()
    if not observed_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned no exact fulfillment id")
    if observed_id != remote_id:
        return OracleResult(
            action, False,
            "independent Shopify readback returned a different fulfillment id")
    try:
        linked_fulfillment_order_ids = await authoritative_fulfillment_order_ids(
            service, token, shop,
            dispatch_plan.get("fulfillment_order_ids") or [],
            remote_id)
    except Exception as exc:  # noqa: BLE001 - unavailable is not verified
        return OracleResult(
            action, False,
            "independent fulfillment-order association readback unavailable: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    if sorted(linked_fulfillment_order_ids) != sorted(
        str(value).strip() for value in (
            dispatch_plan.get("fulfillment_order_ids") or [])
    ):
        return OracleResult(
            action, False,
            "independent fulfillment-order association does not match the "
            "server-resolved dispatch plan")

    observed_material = observed_fulfillment_material(
        observed,
        fulfillment_order_ids=linked_fulfillment_order_ids,
    )
    mismatches = material_mismatches(
        expected_material, observed_material)
    mismatches.extend(fulfillment_plan_mismatches(
        dispatch_plan, observed_material))
    status_issue = fulfillment_status_issue(observed)
    if status_issue:
        mismatches.append("status")
    if mismatches:
        return OracleResult(
            action, False,
            "independent Shopify readback contradicts the authorized/"
            "dispatched material: " + ", ".join(mismatches)
            + (f" ({status_issue})" if status_issue else ""))
    return OracleResult(
        action, True,
        f"Shopify fulfillment {remote_id} re-read from {shop} for order "
        f"{parent_order_id}; order and dispatch material match "
        f"(payload {expected_digest[:12]})")


@register_postcondition("mini_app_set_tests")
async def _verify_mini_app_set_tests(ctx: Dict[str, Any]) -> OracleResult:
    """Independent readback for a mini-app manifest write.

    The handler appends a CanvasAudit row with the exact tests digest and the
    executor-owned operation id. This verifier requires BOTH that receipt and
    the persisted manifest to match the frozen authorized request, so neither
    an old identical row nor the handler's own success flag can certify a new
    operation.
    """
    action = "mini_app_set_tests"
    app_id = str(
        ctx.get("_oracle_expected_app_id") or ctx.get("app_id") or "").strip()
    expected_tests = ctx.get("_oracle_expected_tests")
    if expected_tests is None:
        expected_tests = ctx.get("tests")
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    audit_id = str(ctx.get("audit_id") or "").strip()
    expected_tenant = str(ctx.get("_oracle_expected_tenant_id") or "")
    expected_workspace = str(ctx.get("_oracle_expected_workspace_id") or "")
    expected_actor = str(ctx.get("_oracle_expected_actor_id") or "")
    if not app_id:
        return OracleResult(action, False, "missing app_id")
    if not isinstance(expected_tests, list):
        return OracleResult(
            action, False, "no frozen acceptance-test request")
    if not expected_operation:
        return OracleResult(
            action, False, "no frozen operation identity")
    if not audit_id:
        return OracleResult(
            action, False, "no audit receipt from this invocation")
    if not expected_tenant:
        return OracleResult(
            action, False, "no frozen tenant identity")
    if not expected_actor:
        return OracleResult(
            action, False, "no frozen actor identity")
    try:
        from core.task_lifecycle import _approval_payload_hash

        expected_digest = str(
            ctx.get("_oracle_expected_tests_sha256") or ""
        ) or _approval_payload_hash(expected_tests)
    except Exception as exc:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            action, False, f"test request digest unavailable: {exc}")

    def _read(session):
        from core.models import Canvas, CanvasAudit, MiniApp

        app = session.query(MiniApp).filter(MiniApp.id == app_id).first()
        audit = (
            session.query(CanvasAudit)
            .filter(CanvasAudit.id == audit_id)
            .first()
        )
        canvas = None
        if app is not None and app.blueprint_canvas_id:
            canvas = (
                session.query(Canvas)
                .filter(Canvas.id == app.blueprint_canvas_id)
                .first()
            )
        return app, audit, canvas

    def _same(actual, expected) -> bool:
        return str(actual or "") == str(expected or "")

    try:
        # Fresh session: the caller's session/identity map is never used to
        # certify authoritative columns. Peer commits are visible; dirty
        # request objects are not.
        app, audit, canvas = _fresh_read_with_db(ctx, _read)
        if app is None:
            return OracleResult(
                action, False, f"MiniApp {app_id} absent in DB")
        if audit is None:
            return OracleResult(
                action, False,
                f"audit receipt {audit_id[:12]} absent for this app")
        if canvas is None:
            return OracleResult(
                action, False,
                f"blueprint canvas {app.blueprint_canvas_id!r} absent")
        details = audit.details_json or {}
        if isinstance(details, str):
            details = json.loads(details)
        details = details if isinstance(details, dict) else {}
        manifest = app.manifest if isinstance(app.manifest, dict) else {}
        reasons = []
        # Authoritative MiniApp scope/owner must match the frozen request.
        if not _same(app.tenant_id, expected_tenant):
            reasons.append(
                f"app tenant={app.tenant_id!r}, expected "
                f"{expected_tenant!r}")
        if not _same(app.workspace_id, expected_workspace):
            reasons.append(
                f"app workspace={app.workspace_id!r}, expected "
                f"{expected_workspace!r}")
        if not _same(app.created_by, expected_actor):
            reasons.append(
                f"app owner={app.created_by!r}, expected {expected_actor!r}")
        if not app.blueprint_canvas_id:
            reasons.append("app has no blueprint canvas")
        # The authoritative audit row and blueprint canvas must be the same
        # current objects, at the same scope.
        if str(audit.canvas_id or "") != str(app.blueprint_canvas_id or ""):
            reasons.append("audit canvas does not match app blueprint canvas")
        if str(canvas.id or "") != str(app.blueprint_canvas_id or ""):
            reasons.append("blueprint canvas identity mismatch")
        if not _same(canvas.tenant_id, expected_tenant):
            reasons.append(
                f"canvas tenant={canvas.tenant_id!r}, expected "
                f"{expected_tenant!r}")
        if not _same(canvas.workspace_id, expected_workspace):
            reasons.append(
                f"canvas workspace={canvas.workspace_id!r}, expected "
                f"{expected_workspace!r}")
        if str(audit.action_type or "") != action:
            reasons.append(f"audit action_type={audit.action_type!r}")
        if not _same(audit.tenant_id, expected_tenant):
            reasons.append(
                f"audit tenant={audit.tenant_id!r}, expected "
                f"{expected_tenant!r}")
        if not _same(audit.user_id, expected_actor):
            reasons.append(
                f"audit actor={audit.user_id!r}, expected {expected_actor!r}")
        # Details are corroboration, never a fallback for an authoritative
        # contradiction above.
        if not _same(details.get("app_id"), app_id):
            reasons.append("audit app_id does not match the request")
        if not _same(details.get("tests_sha256"), expected_digest):
            reasons.append("audit tests digest does not match the request")
        if not _same(details.get("operation_id"), expected_operation):
            reasons.append("audit operation id does not match this operation")
        if not _same(details.get("tenant_id"), expected_tenant):
            reasons.append("audit details tenant does not match the request")
        if not _same(details.get("workspace_id"), expected_workspace):
            reasons.append(
                "audit details workspace does not match the request")
        if not _same(details.get("actor_id"), expected_actor):
            reasons.append("audit details actor does not match the request")
        if manifest.get("tests") != expected_tests:
            reasons.append("persisted manifest tests do not match the request")
        return OracleResult(
            action, not reasons,
            f"MiniApp {app_id} manifest tests={len(manifest.get('tests') or [])} "
            f"audit={audit_id[:12]} operation={expected_operation[:12]} "
            f"scope={expected_tenant}/{expected_workspace}/{expected_actor}"
            + ("" if not reasons else "; " + "; ".join(reasons)))
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            action, False, f"mini-app read-back failed: {e}")


@register_postcondition("tasks.create")
async def _verify_task_created(ctx: Dict[str, Any]) -> OracleResult:
    """A created task must persist to the DB (not just be returned by the tool)."""
    task = ctx.get("task") if isinstance(ctx.get("task"), dict) else {}
    task_id = str(ctx.get("task_id") or task.get("id") or "")
    if not task_id:
        return OracleResult("tasks.create", False, "missing task id")

    def _read(session):
        from core.models_board import BoardTask
        return session.query(BoardTask).filter(
            BoardTask.id == task_id).first()

    try:
        row = _read_with_db(ctx, _read)
        if row is None:
            return OracleResult(
                "tasks.create", False,
                f"BoardTask {task_id} absent in DB")
        expected_title = str(
            ctx.get("_oracle_expected_task_title")
            or ctx.get("title") or "")
        expected_board = str(
            ctx.get("_oracle_expected_board_id")
            or ctx.get("board_id") or "")
        verified = True
        if expected_title:
            verified = verified and str(row.title or "") == expected_title
        if expected_board:
            verified = (
                verified and str(row.board_id or "") == expected_board)
        return OracleResult(
            "tasks.create", verified,
            f"BoardTask {task_id} title={row.title!r} "
            f"board={row.board_id!r}")
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            "tasks.create", False, f"DB read-back failed: {e}")


def _content_digest(value: Any) -> str:
    blob = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def canvas_content_digest(value: Any) -> str:
    """Public alias for the canonical canvas material digest.

    The direct HTTP write service must freeze the SAME material the oracle
    verifier reads back. Keeping one digest prevents a self-consistent
    parallel representation from passing while the real consumer sees a
    different value.
    """
    return _content_digest(value)


def _read_with_db(ctx: Dict[str, Any], reader):
    db = ctx.get("db")
    if db is not None:
        return reader(db)
    from core.database import get_db_session
    with get_db_session() as session:
        return reader(session)


def _fresh_read_with_db(ctx: Dict[str, Any], reader):
    """Read through a NEW session bound to the caller's store.

    Verification must not reuse the caller's identity map or uncommitted
    request objects: a dirty in-memory object could otherwise certify an
    authoritative row it does not match. The predecessor session is only used
    to discover the engine; the read runs in its own session.
    """
    db = ctx.get("db") or ctx.get("session")
    if db is not None:
        from sqlalchemy.orm import sessionmaker

        bind = db.get_bind()
        engine = getattr(bind, "engine", bind)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        session = Session()
        try:
            return reader(session)
        finally:
            session.close()
    from core.database import get_db_session
    with get_db_session() as session:
        return reader(session)


def _canvas_present_postcondition(component_type: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = str(ctx.get("_oracle_action") or "canvas.present")
        canvas_id = str(
            ctx.get("_oracle_expected_canvas_id")
            or ctx.get("canvas_id") or ctx.get("remote_id") or "").strip()
        audit_id = str(ctx.get("audit_id") or "").strip()
        expected_material_digest = str(
            ctx.get("_oracle_expected_material_sha256") or "").strip()
        expected_operation = str(
            ctx.get("_oracle_expected_operation_id") or "").strip()
        if not canvas_id:
            return OracleResult(action, False, "missing canvas_id")
        if not audit_id:
            return OracleResult(
                action, False,
                "no audit_id from the current presentation invocation")
        if not expected_material_digest:
            return OracleResult(
                action, False,
                "no frozen material digest for the presentation")
        if not expected_operation:
            return OracleResult(
                action, False,
                "no frozen operation identity for the presentation")

        def _read(session):
            from core.models import CanvasAudit
            return (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == audit_id,
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )

        try:
            row = _read_with_db(ctx, _read)
            if row is None:
                return OracleResult(
                    action, False,
                    f"canvas_audit {audit_id[:12]} not found for canvas "
                    f"{canvas_id}")
            details = row.details_json or {}
            if isinstance(details, str):
                details = json.loads(details)
            details = details if isinstance(details, dict) else {}
            observed_component = str(details.get("component_type") or "")
            observed_operation = str(details.get("operation_id") or "")
            observed_digest = str(details.get("material_sha256") or "")
            observed_material = details.get("material")
            from core.presentation_material import material_sha256
            computed_digest = (
                material_sha256(observed_material)
                if isinstance(observed_material, dict) else "")
            expected_workspace = str(
                ctx.get("_oracle_expected_workspace_id") or "")
            expected_tenant = str(
                ctx.get("_oracle_expected_tenant_id") or "")
            observed_workspace = str(details.get("workspace_id") or "")
            observed_tenant = str(
                details.get("tenant_id") or row.tenant_id or "")
            reasons = []
            if str(row.action_type or "") != "present":
                reasons.append(f"action_type={row.action_type!r}")
            if observed_component != component_type:
                reasons.append(f"component_type={observed_component!r}")
            if observed_operation != expected_operation:
                reasons.append(
                    f"operation_id={observed_operation!r}, expected "
                    f"{expected_operation!r}")
            if not observed_material or not observed_digest:
                reasons.append("audit carries no material/digest")
            elif observed_digest != computed_digest:
                reasons.append("audit material digest does not match its material")
            elif observed_digest != expected_material_digest:
                reasons.append("audit material does not match the authorized request")
            if expected_workspace and observed_workspace != expected_workspace:
                reasons.append(
                    f"workspace={observed_workspace!r}, expected "
                    f"{expected_workspace!r}")
            if expected_tenant and observed_tenant != expected_tenant:
                reasons.append(
                    f"tenant={observed_tenant!r}, expected {expected_tenant!r}")
            verified = not reasons
            return OracleResult(
                action, verified,
                f"canvas_audit {row.id} action_type={row.action_type!r} "
                f"component_type={observed_component!r} "
                f"operation={observed_operation!r} "
                f"material={observed_digest[:12]}"
                + ("" if verified else "; " + "; ".join(reasons)))
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"audit read-back failed: {e}")
    return _verify


def _canvas_write_postcondition(restore: bool):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = str(ctx.get("_oracle_action") or "canvas.update")
        canvas_id = str(
            ctx.get("_oracle_expected_canvas_id")
            or ctx.get("canvas_id") or "").strip()
        if not canvas_id:
            return OracleResult(action, False, "missing canvas_id")
        expected_tenant = str(
            ctx.get("_oracle_expected_tenant_id") or "").strip()
        expected_workspace = str(
            ctx.get("_oracle_expected_workspace_id") or "").strip()
        expected_actor = str(
            ctx.get("_oracle_expected_actor_id") or "").strip()
        write_outcome = str(ctx.get("write_outcome") or "")
        no_change = bool(ctx.get("no_change"))

        def _read_canvas(session):
            from core.models import Canvas
            return (
                session.query(Canvas)
                .filter(Canvas.id == canvas_id)
                .first()
            )

        def _scope_value_allowed(observed, expected):
            """Mirror the writer's legacy/default scope rule."""
            observed = str(observed or "").strip()
            expected = str(expected or "").strip()
            if not observed:
                return True
            if expected:
                return observed == expected
            return observed.lower() == "default"

        def _scope_reasons(row, canvas, *, check_actor: bool):
            reasons = []
            strict_scope = bool(ctx.get("_oracle_require_scope_match"))
            if expected_tenant or strict_scope:
                if not _scope_value_allowed(row.tenant_id, expected_tenant):
                    reasons.append(
                        f"audit tenant={row.tenant_id!r}, expected "
                        f"{expected_tenant!r}")
            if canvas is None:
                reasons.append("canvas mirror missing")
            else:
                if (expected_tenant or strict_scope) and (
                        not _scope_value_allowed(
                            canvas.tenant_id, expected_tenant)):
                    reasons.append(
                        f"canvas tenant={canvas.tenant_id!r}, expected "
                        f"{expected_tenant!r}")
                if (expected_workspace or strict_scope) and (
                        not _scope_value_allowed(
                            canvas.workspace_id, expected_workspace)):
                    reasons.append(
                        f"canvas workspace={canvas.workspace_id!r}, expected "
                        f"{expected_workspace!r}")
            if check_actor and expected_actor:
                if str(row.user_id or "") != expected_actor:
                    reasons.append(
                        f"audit actor={row.user_id!r}, expected "
                        f"{expected_actor!r}")
            return reasons

        def _read_new(session, audit_id: str):
            from core.models import CanvasAudit, Canvas
            row = (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == audit_id,
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )
            canvas = (
                session.query(Canvas)
                .filter(Canvas.id == canvas_id)
                .first()
            )
            return row, canvas

        def _read_audit(session, audit_id: str):
            from core.models import CanvasAudit
            return (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == audit_id,
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )

        def _latest(session):
            from core.models import CanvasAudit
            from sqlalchemy import desc
            return (
                session.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at),
                          desc(CanvasAudit.id))
                .first()
            )

        def _details(row):
            value = row.details_json or {}
            if isinstance(value, str):
                value = json.loads(value)
            return value or {}

        def _latest_content(session):
            """Latest CONTENT revision, skipping event-only audit stamps.

            A send/event row can append after the write without carrying a
            body. Recency must compare against the current content revision,
            not the absolute newest event row.
            """
            from core.models import CanvasAudit
            from sqlalchemy import desc

            rows = (
                session.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at),
                          desc(CanvasAudit.id))
                .limit(50)
                .all()
            )
            for candidate in rows:
                details = _details(candidate)
                if "content" in details or "data" in details:
                    return candidate
            return rows[0] if rows else None

        try:
            if no_change:
                target_id = str(
                    ctx.get("_oracle_expected_restore_audit_id")
                    or ctx.get("restored_from") or "")
                if not target_id:
                    return OracleResult(
                        action, False, "no-change restore has no target audit")
                target = _read_with_db(
                    ctx, lambda session: _read_audit(session, target_id))
                latest = _read_with_db(ctx, _latest_content)
                if target is None or latest is None:
                    return OracleResult(
                        action, False,
                        "no-change restore could not read the target/current "
                        "version")
                if str(target.action_type or "") == "delete":
                    return OracleResult(
                        action, False,
                        "no-change target is a deletion marker")
                target_details = _details(target)
                if ("content" not in target_details
                        and "data" not in target_details):
                    return OracleResult(
                        action, False,
                        "no-change target carries no restorable content")
                canvas = _read_with_db(ctx, _read_canvas)
                scope_reasons = _scope_reasons(
                    latest, canvas, check_actor=False)
                if scope_reasons:
                    return OracleResult(
                        action, False, "; ".join(scope_reasons))
                if canvas is None:
                    return OracleResult(
                        action, False,
                        "no-change restore has no authoritative canvas "
                        "mirror")
                expected_target_tenant = expected_tenant or str(
                    canvas.tenant_id or "")
                if not _scope_value_allowed(
                        target.tenant_id, expected_target_tenant):
                    return OracleResult(
                        action, False,
                        f"target audit tenant={target.tenant_id!r}, expected "
                        f"{expected_target_tenant!r}")
                from tools.canvas_crud_tool import (
                    canonical_restore_content,
                )

                _, restored_content = canonical_restore_content(
                    latest, target)
                if restored_content is None:
                    return OracleResult(
                        action, False,
                        "no-change target carries no restorable content")
                target_digest = _content_digest(restored_content)
                latest_digest = _content_digest(
                    _details(latest).get("content",
                                         _details(latest).get("data")))
                mirror_digest = _content_digest(canvas.content)
                verified = (
                    target_digest == latest_digest == mirror_digest)
                return OracleResult(
                    action, verified,
                    f"no-change restore target {target_id[:12]} "
                    f"content_match={target_digest == latest_digest} "
                    f"mirror_match={latest_digest == mirror_digest}")
            if write_outcome and write_outcome != "committed":
                return OracleResult(
                    action, False,
                    f"write_outcome == {write_outcome!r}, not committed")
            new_audit_id = str(ctx.get("audit_id") or "")
            if not new_audit_id:
                return OracleResult(
                    action, False, "no appended audit_id in the result")
            row, canvas = _read_with_db(
                ctx, lambda session: _read_new(session, new_audit_id))
            if row is None:
                return OracleResult(
                    action, False,
                    f"canvas_audit {new_audit_id[:12]} not found")
            scope_reasons = _scope_reasons(row, canvas, check_actor=True)
            if scope_reasons:
                return OracleResult(
                    action, False, "; ".join(scope_reasons))
            if str(row.action_type or "") != "update":
                return OracleResult(
                    action, False,
                    f"canvas_audit action_type == {row.action_type!r}")
            latest_content = _read_with_db(ctx, _latest_content)
            if (latest_content is None
                    or str(latest_content.id) != new_audit_id):
                return OracleResult(
                    action, False,
                    "audit is not the current content revision; a later "
                    "content audit exists")
            details = _details(row)
            observed_content = details.get("content", details.get("data"))
            if restore:
                expected_operation = str(
                    ctx.get("_oracle_expected_operation_id") or "")
                if expected_operation and str(
                        details.get("operation_id") or ""
                ) != expected_operation:
                    return OracleResult(
                        action, False,
                        "restore audit operation_id does not match the "
                        "authorized operation")
                expected_target = str(
                    ctx.get("_oracle_expected_restore_audit_id") or "")
                restored_from = details.get("restored_from") or {}
                observed_target = str(
                    restored_from.get("audit_id") or "") if isinstance(
                        restored_from, dict) else ""
                if not expected_target:
                    return OracleResult(
                        action, False,
                        "restore has no frozen target audit id")
                if observed_target != expected_target:
                    return OracleResult(
                        action, False,
                        "restored_from does not match the authorized target")
                target = _read_with_db(
                    ctx, lambda session: _read_audit(
                        session, expected_target))
                if target is None:
                    return OracleResult(
                        action, False, "authorized target version not found")
                if str(target.action_type or "") == "delete":
                    return OracleResult(
                        action, False,
                        "authorized target is a deletion marker")
                expected_target_tenant = expected_tenant
                if not expected_target_tenant and canvas is not None:
                    expected_target_tenant = str(canvas.tenant_id or "")
                if not _scope_value_allowed(
                        target.tenant_id, expected_target_tenant):
                    return OracleResult(
                        action, False,
                        f"target audit tenant={target.tenant_id!r}, expected "
                        f"{expected_target_tenant!r}")
                from tools.canvas_crud_tool import (
                    canonical_restore_content,
                )

                _, restored_content = canonical_restore_content(row, target)
                if restored_content is None:
                    return OracleResult(
                        action, False,
                        "authorized target carries no restorable content")
                expected_digest = _content_digest(restored_content)
            else:
                expected_digest = str(
                    ctx.get("_oracle_expected_canvas_content_sha256") or "")
                if not expected_digest:
                    if "content" not in ctx:
                        return OracleResult(
                            action, False,
                            "authorized content was not captured")
                    expected_digest = _content_digest(ctx.get("content"))
                expected_operation = str(
                    ctx.get("_oracle_expected_operation_id") or "")
                if expected_operation:
                    if str(details.get("operation_id") or "") != expected_operation:
                        return OracleResult(
                            action, False,
                            "audit operation_id does not match the authorized "
                            "operation")
                expected_review = str(
                    ctx.get("_oracle_expected_review_status") or "")
                if expected_review:
                    if str(details.get("review_status") or "") != expected_review:
                        return OracleResult(
                            action, False,
                            "audit review_status does not match the authorized "
                            "request")
            observed_digest = _content_digest(observed_content)
            if observed_digest != expected_digest:
                return OracleResult(
                    action, False,
                    "persisted canvas content does not match the authorized "
                    "content")
            review_status = str(details.get("review_status") or "accepted")
            if canvas is not None and review_status == "accepted":
                canvas_digest = _content_digest(canvas.content)
                if canvas_digest != observed_digest:
                    return OracleResult(
                        action, False,
                        "accepted canvas mirror does not match the audit content")
            return OracleResult(
                action, True,
                f"canvas_audit {new_audit_id[:12]} action_type=update "
                f"content={observed_digest[:12]} canvas_id={canvas_id}")
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"canvas read-back failed: {e}")
    return _verify


def _canvas_lifecycle_postcondition(kind: str):
    """Independent readback for the append-only delete/undelete rows.

    This is the same postcondition oracle the accepted canvas update/restore
    uses, parameterized by the lifecycle action. It reads the exact appended
    row and its prior/tombstone/source rows in a FRESH session, then refuses
    unless action, actor, scope, operation identity, source material and
    recency all match the authority frozen before dispatch.
    """
    expected_action = "delete" if kind == "delete" else "restore"

    def _details(row: Any) -> Dict[str, Any]:
        value = getattr(row, "details_json", None) or {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                value = {}
        return value if isinstance(value, dict) else {}

    def _scope_allowed(observed: Any, expected: Any) -> bool:
        observed = str(observed or "").strip()
        expected = str(expected or "").strip()
        if not observed:
            return True
        if expected:
            return observed == expected
        return observed.lower() == "default"

    def _content_of(row: Any) -> Any:
        if row is None:
            return None
        details = _details(row)
        for key in ("content", "data"):
            if key in details and details[key] is not None:
                return details[key]
        return None

    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = str(ctx.get("_oracle_action") or f"canvas.{kind}")
        canvas_id = str(
            ctx.get("_oracle_expected_canvas_id")
            or ctx.get("canvas_id") or "").strip()
        audit_id = str(ctx.get("audit_id") or "").strip()
        expected_operation = str(
            ctx.get("_oracle_expected_operation_id") or "").strip()
        operation_optional = bool(
            ctx.get("_oracle_lifecycle_operation_optional"))
        expected_actor = str(
            ctx.get("_oracle_expected_actor_id") or "").strip()
        expected_tenant = str(
            ctx.get("_oracle_expected_tenant_id") or "").strip()
        expected_workspace = str(
            ctx.get("_oracle_expected_workspace_id") or "").strip()
        expected_prior = str(
            ctx.get("_oracle_expected_prior_audit_id") or "").strip()
        expected_tombstone = str(
            ctx.get("_oracle_expected_tombstone_audit_id") or "").strip()
        expected_source = str(
            ctx.get("_oracle_expected_source_audit_id") or "").strip()
        expected_digest = str(
            ctx.get("_oracle_expected_canvas_content_sha256") or "").strip()
        write_outcome = str(ctx.get("write_outcome") or "")
        already_applied = bool(ctx.get("already_applied"))
        strict_scope = bool(ctx.get("_oracle_require_scope_match"))

        if not canvas_id:
            return OracleResult(action, False, "missing canvas_id")
        if not audit_id:
            return OracleResult(
                action, False, "no appended audit_id in the result")
        if not operation_optional and not expected_operation:
            return OracleResult(
                action, False, "no frozen operation identity")
        if write_outcome and write_outcome != "committed":
            return OracleResult(
                action, False,
                f"write_outcome == {write_outcome!r}, not committed")

        def _read_head(session):
            from core.models import Canvas, CanvasAudit
            from sqlalchemy import desc

            row = (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == audit_id,
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )
            canvas = (
                session.query(Canvas)
                .filter(Canvas.id == canvas_id)
                .first()
            )
            latest = (
                session.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at),
                          desc(CanvasAudit.id))
                .first()
            )
            return row, canvas, latest

        def _read_audit(session, target_id: str):
            from core.models import CanvasAudit

            return (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == str(target_id),
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )

        try:
            row, canvas, latest = _fresh_read_with_db(ctx, _read_head)
            if row is None:
                return OracleResult(
                    action, False,
                    f"canvas_audit {audit_id[:12]} not found for canvas "
                    f"{canvas_id}")
            if str(row.action_type or "") != expected_action:
                return OracleResult(
                    action, False,
                    f"canvas_audit action_type == {row.action_type!r}")
            if expected_actor and str(row.user_id or "") != expected_actor:
                return OracleResult(
                    action, False,
                    f"audit actor={row.user_id!r}, expected {expected_actor!r}")

            details = _details(row)
            if (not operation_optional and str(
                    details.get("operation_id") or "") != expected_operation):
                return OracleResult(
                    action, False,
                    "audit operation_id does not match the authorized "
                    "operation")
            if expected_tenant or strict_scope:
                if not _scope_allowed(row.tenant_id, expected_tenant):
                    return OracleResult(
                        action, False,
                        f"audit tenant={row.tenant_id!r}, expected "
                        f"{expected_tenant!r}")
            if canvas is not None:
                if (expected_tenant or strict_scope) and (
                        not _scope_allowed(
                            canvas.tenant_id, expected_tenant)):
                    return OracleResult(
                        action, False,
                        f"canvas tenant={canvas.tenant_id!r}, expected "
                        f"{expected_tenant!r}")
                if (expected_workspace or strict_scope) and (
                        not _scope_allowed(
                            canvas.workspace_id, expected_workspace)):
                    return OracleResult(
                        action, False,
                        f"canvas workspace={canvas.workspace_id!r}, expected "
                        f"{expected_workspace!r}")
            # Audit-only canvases have no workspace column; workspace stays
            # legacy/unqualified rather than becoming a foreign grant.

            if not already_applied:
                if latest is None or str(latest.id) != audit_id:
                    return OracleResult(
                        action, False,
                        "audit is not the current lifecycle row; a later "
                        "audit exists")

            stored_digest = str(details.get("content_sha256") or "")

            if kind == "delete":
                stored_prior = str(details.get("prior_audit_id") or "")
                if expected_prior and stored_prior != expected_prior:
                    return OracleResult(
                        action, False,
                        "audit prior_audit_id does not match the authorized "
                        "prior row")
                source_id = str(details.get("source_audit_id") or "")
                if expected_source and source_id != expected_source:
                    return OracleResult(
                        action, False,
                        "audit source_audit_id does not match the authorized "
                        "source row")
                prior = (
                    _fresh_read_with_db(
                        ctx, lambda session: _read_audit(
                            session, expected_prior))
                    if expected_prior else None)
                if expected_prior and prior is None:
                    return OracleResult(
                        action, False,
                        "authorized prior audit row not found")
                if prior is not None and str(
                        prior.action_type or "") == "delete":
                    return OracleResult(
                        action, False,
                        "authorized prior row is a deletion marker")
                source = (
                    _fresh_read_with_db(
                        ctx, lambda session: _read_audit(
                            session, source_id))
                    if source_id else None)
                if source_id and source is None:
                    return OracleResult(
                        action, False, "source content row not found")
                if source is not None:
                    if str(source.action_type or "") == "delete":
                        return OracleResult(
                            action, False,
                            "source content row is a deletion marker")
                    from tools.canvas_crud_tool import _EVENT_ONLY_ACTIONS
                    if str(source.action_type or "") in _EVENT_ONLY_ACTIONS:
                        return OracleResult(
                            action, False,
                            "source content row is an event-only stamp")
                    source_content = _content_of(source)
                    if source_content is None:
                        return OracleResult(
                            action, False,
                            "source content row carries no content")
                    source_digest = _content_digest(source_content)
                    if stored_digest and source_digest != stored_digest:
                        return OracleResult(
                            action, False,
                            "stored content digest does not match the source "
                            "row")
                    if expected_digest and source_digest != expected_digest:
                        return OracleResult(
                            action, False,
                            "source content does not match the authorized "
                            "material")
                return OracleResult(
                    action, True,
                    f"canvas_audit {audit_id[:12]} action_type=delete "
                    f"prior={(stored_prior or '-')[:12]} "
                    f"content={(stored_digest or '-')[:12]} "
                    f"canvas_id={canvas_id}")

            stored_tombstone = str(
                details.get("tombstone_audit_id")
                or details.get("restored_from_tombstone_id") or "")
            if expected_tombstone and stored_tombstone != expected_tombstone:
                return OracleResult(
                    action, False,
                    "audit tombstone_audit_id does not match the authorized "
                    "tombstone")
            if not stored_tombstone:
                return OracleResult(
                    action, False, "audit carries no tombstone identity")
            tombstone = _fresh_read_with_db(
                ctx, lambda session: _read_audit(
                    session, stored_tombstone))
            if tombstone is None:
                return OracleResult(
                    action, False, "authorized tombstone row not found")
            if str(tombstone.action_type or "") != "delete":
                return OracleResult(
                    action, False,
                    "tombstone row is not a deletion marker")

            source_id = str(details.get("source_audit_id") or "")
            if expected_source and source_id != expected_source:
                return OracleResult(
                    action, False,
                    "audit source_audit_id does not match the authorized "
                    "source row")
            if not source_id:
                return OracleResult(
                    action, False, "audit carries no source content row")
            source = _fresh_read_with_db(
                ctx, lambda session: _read_audit(session, source_id))
            if source is None:
                return OracleResult(
                    action, False, "authorized source content row not found")
            if str(source.action_type or "") == "delete":
                return OracleResult(
                    action, False,
                    "source content row is a deletion marker")
            from tools.canvas_crud_tool import _EVENT_ONLY_ACTIONS
            if str(source.action_type or "") in _EVENT_ONLY_ACTIONS:
                return OracleResult(
                    action, False,
                    "source content row is an event-only stamp")
            source_content = _content_of(source)
            if source_content is None:
                return OracleResult(
                    action, False,
                    "source content row carries no content")
            source_digest = _content_digest(source_content)
            if stored_digest and source_digest != stored_digest:
                return OracleResult(
                    action, False,
                    "stored content digest does not match the source row")
            if expected_digest and source_digest != expected_digest:
                return OracleResult(
                    action, False,
                    "source content does not match the authorized material")
            restored_content = _content_of(row)
            if restored_content is None:
                return OracleResult(
                    action, False, "restore row carries no restored content")
            if _content_digest(restored_content) != source_digest:
                return OracleResult(
                    action, False,
                    "restored content does not match the exact source row")
            return OracleResult(
                action, True,
                f"canvas_audit {audit_id[:12]} action_type=restore "
                f"tombstone={stored_tombstone[:12]} "
                f"source={source_id[:12]} content={source_digest[:12]} "
                f"canvas_id={canvas_id}")
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"canvas lifecycle read-back failed: {e}")
    return _verify


def _canvas_submit_postcondition():
    """Independent readback for one append-only form-submission EVENT.

    The audit row is located by its EXACT id (never "latest"), and the Canvas,
    current User and canonical request material are re-derived in a fresh
    session. ``Canvas.content`` is not an input: a submission records an event,
    it does not claim authorship or mirror content.
    """
    action = "canvas.submit"

    def _details(row: Any) -> Dict[str, Any]:
        value = getattr(row, "details_json", None) or {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                value = {}
        return value if isinstance(value, dict) else {}

    def _scope_value_same(actual: Any, expected: Any) -> bool:
        return actual == expected

    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        required = (
            "_oracle_expected_canvas_id", "_oracle_expected_operation_id",
            "_oracle_expected_material_sha256", "_oracle_expected_actor_id",
            "_oracle_expected_actor_tenant_id", "_oracle_expected_actor_workspace_id",
            "_oracle_expected_canvas_tenant_id", "_oracle_expected_canvas_workspace_id",
            "_oracle_expected_agent_id", "_oracle_expected_agent_execution_id",
        )
        if any(key not in ctx for key in required):
            return OracleResult(action, False, "incomplete frozen submission binding")
        for key in required[:4]:
            if not isinstance(ctx[key], str) or not ctx[key].strip():
                return OracleResult(action, False, "invalid frozen submission identity")
        for key in required[4:8]:
            if ctx[key] is not None and not isinstance(ctx[key], str):
                return OracleResult(action, False, "invalid frozen submission scope")
        if any(not isinstance(ctx[key], str) for key in required[8:]):
            return OracleResult(action, False, "invalid frozen submission agent identity")
        canvas_id = str(
            ctx.get("_oracle_expected_canvas_id")
            or ctx.get("canvas_id") or "").strip()
        audit_id = str(ctx.get("audit_id") or "").strip()
        expected_operation = str(
            ctx.get("_oracle_expected_operation_id") or "").strip()
        expected_digest = str(
            ctx.get("_oracle_expected_material_sha256") or "").strip()
        expected_actor = str(
            ctx.get("_oracle_expected_actor_id") or "").strip()
        expected_agent = str(
            ctx.get("_oracle_expected_agent_id") or "").strip()
        expected_execution = str(
            ctx.get("_oracle_expected_agent_execution_id") or "").strip()
        write_outcome = str(ctx.get("write_outcome") or "")

        if not canvas_id:
            return OracleResult(action, False, "missing canvas_id")
        if not audit_id:
            return OracleResult(
                action, False, "no appended audit_id in the result")
        if not expected_operation:
            return OracleResult(
                action, False, "no frozen operation identity")
        if not expected_digest:
            return OracleResult(
                action, False, "no frozen submission material digest")
        if not expected_actor:
            return OracleResult(
                action, False, "no frozen actor identity")
        if write_outcome and write_outcome != "committed":
            return OracleResult(
                action, False,
                f"write_outcome == {write_outcome!r}, not committed")

        _missing = object()

        def _expected(key: str, fallback_key: str):
            if key in ctx:
                return ctx.get(key)
            if fallback_key in ctx:
                return ctx.get(fallback_key)
            return _missing

        expected_actor_tenant = _expected(
            "_oracle_expected_actor_tenant_id",
            "_oracle_expected_tenant_id")
        expected_actor_workspace = _expected(
            "_oracle_expected_actor_workspace_id",
            "_oracle_expected_workspace_id")
        expected_canvas_tenant = _expected(
            "_oracle_expected_canvas_tenant_id",
            "_oracle_expected_tenant_id")
        expected_canvas_workspace = _expected(
            "_oracle_expected_canvas_workspace_id",
            "_oracle_expected_workspace_id")

        def _read(session):
            from core.models import Canvas, CanvasAudit, User

            audit = (
                session.query(CanvasAudit)
                .filter(
                    CanvasAudit.id == audit_id,
                    CanvasAudit.canvas_id == canvas_id,
                )
                .first()
            )
            canvas = (
                session.query(Canvas)
                .filter(Canvas.id == canvas_id)
                .first()
            )
            actor = (
                session.query(User)
                .filter(User.id == expected_actor)
                .first()
            )
            return audit, canvas, actor

        try:
            audit, canvas, actor_row = _fresh_read_with_db(ctx, _read)
            if audit is None:
                return OracleResult(
                    action, False,
                    f"canvas_audit {audit_id[:12]} not found for canvas "
                    f"{canvas_id}")
            if canvas is None:
                return OracleResult(
                    action, False,
                    f"Canvas {canvas_id} absent in DB")
            if actor_row is None:
                return OracleResult(
                    action, False,
                    f"acting user {expected_actor[:12]} absent in DB")

            reasons = []
            if str(audit.action_type or "") != "submit":
                reasons.append(f"action_type={audit.action_type!r}")
            if str(audit.user_id or "") != expected_actor:
                reasons.append(
                    f"audit actor={audit.user_id!r}, expected "
                    f"{expected_actor!r}")
            if str(canvas.status or "").lower() != "active":
                reasons.append(f"canvas status={canvas.status!r}")
            if (expected_canvas_tenant is not _missing
                    and not _scope_value_same(
                        audit.tenant_id, expected_canvas_tenant)):
                reasons.append(
                    f"audit tenant={audit.tenant_id!r}, expected "
                    f"{expected_canvas_tenant!r}")
            if (expected_canvas_tenant is not _missing
                    and not _scope_value_same(
                        canvas.tenant_id, expected_canvas_tenant)):
                reasons.append(
                    f"canvas tenant={canvas.tenant_id!r}, expected "
                    f"{expected_canvas_tenant!r}")
            if (expected_canvas_workspace is not _missing
                    and not _scope_value_same(
                        canvas.workspace_id, expected_canvas_workspace)):
                reasons.append(
                    f"canvas workspace={canvas.workspace_id!r}, expected "
                    f"{expected_canvas_workspace!r}")

            actor_status = str(getattr(
                getattr(actor_row, "status", ""), "value",
                getattr(actor_row, "status", "")) or "")
            if actor_status != "active" or not bool(
                    getattr(actor_row, "is_active", False)):
                reasons.append("acting user is not active")
            if (expected_actor_tenant is not _missing
                    and not _scope_value_same(
                        actor_row.tenant_id, expected_actor_tenant)):
                reasons.append(
                    f"actor tenant={actor_row.tenant_id!r}, expected "
                    f"{expected_actor_tenant!r}")
            if (expected_actor_workspace is not _missing
                    and not _scope_value_same(
                        actor_row.workspace_id, expected_actor_workspace)):
                reasons.append(
                    f"actor workspace={actor_row.workspace_id!r}, expected "
                    f"{expected_actor_workspace!r}")

            details = _details(audit)
            if str(details.get("operation_id") or "") != expected_operation:
                reasons.append(
                    "audit operation_id does not match this operation")
            if str(details.get("actor_id") or "") != expected_actor:
                reasons.append(
                    "audit details actor does not match the request")
            if (expected_actor_tenant is not _missing
                    and not _scope_value_same(
                        details.get("actor_tenant_id"),
                        expected_actor_tenant)):
                reasons.append(
                    "audit details actor tenant does not match the request")
            if (expected_actor_workspace is not _missing
                    and not _scope_value_same(
                        details.get("actor_workspace_id"),
                        expected_actor_workspace)):
                reasons.append(
                    "audit details actor workspace does not match the request")
            if (expected_canvas_tenant is not _missing
                    and not _scope_value_same(
                        details.get("tenant_id"),
                        expected_canvas_tenant)):
                reasons.append(
                    "audit details tenant does not match the request")
            if (expected_canvas_workspace is not _missing
                    and not _scope_value_same(
                        details.get("workspace_id"),
                        expected_canvas_workspace)):
                reasons.append(
                    "audit details workspace does not match the request")
            if "form_data" not in details:
                reasons.append("audit carries no form_data")
            if str(details.get("agent_id") or "") != expected_agent:
                reasons.append(
                    "audit agent binding does not match the request")
            if str(details.get("agent_execution_id") or "") != (
                    expected_execution):
                reasons.append(
                    "audit agent execution does not match the request")
            if expected_agent and str(audit.agent_id or "") != expected_agent:
                reasons.append(
                    "audit agent column does not match the request")
            if not expected_agent and str(audit.agent_id or ""):
                reasons.append(
                    "audit carries an unexpected agent binding")

            observed_digest = str(details.get("material_sha256") or "")
            if observed_digest != expected_digest:
                reasons.append(
                    "audit material digest does not match the request")
            else:
                from tools.canvas_crud_tool import (
                    canonical_submit_material,
                )

                material = canonical_submit_material(
                    canvas_id,
                    details.get("form_data"),
                    actor_id=expected_actor,
                    tenant_id=(
                        None if expected_actor_tenant is _missing
                        else expected_actor_tenant),
                    workspace_id=(
                        None if expected_actor_workspace is _missing
                        else expected_actor_workspace),
                    agent_id=details.get("agent_id"),
                    agent_execution_id=details.get("agent_execution_id"),
                )
                if _content_digest(material) != expected_digest:
                    reasons.append(
                        "persisted submission material does not match the "
                        "authorized request")
                stored_material = details.get("material")
                if isinstance(stored_material, dict):
                    if _content_digest(stored_material) != expected_digest:
                        reasons.append(
                            "stored submission material digest is "
                            "self-inconsistent")

            if reasons:
                return OracleResult(
                    action, False,
                    "; ".join(reasons))
            return OracleResult(
                action, True,
                f"canvas_audit {audit_id[:12]} action_type=submit "
                f"operation={expected_operation[:12]} "
                f"material={expected_digest[:12]} canvas_id={canvas_id}")
        except Exception as exc:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False,
                f"canvas submit read-back failed: {type(exc).__name__}")

    return _verify


def _goal_postcondition(mode: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = str(ctx.get("_oracle_action") or "goals")
        expected_goal_id = str(
            ctx.get("_oracle_expected_goal_id") or "")
        try:
            if mode == "create":
                goal = ctx.get("goal") or {}
                goal_id = str(goal.get("id") or expected_goal_id or "")
                if not goal_id:
                    return OracleResult(action, False, "missing goal id")

                def _read(session):
                    from core.models import GoalObjective
                    return session.query(GoalObjective).filter(
                        GoalObjective.id == goal_id).first()

                row = _read_with_db(ctx, _read)
                if row is None:
                    return OracleResult(
                        action, False, f"goal {goal_id} not persisted")
                expected_title = str(
                    ctx.get("_oracle_expected_goal_title") or "")
                expected_workspace = str(
                    ctx.get("_oracle_expected_workspace_id") or "")
                verified = True
                if expected_title:
                    verified = verified and str(row.title or "") == expected_title
                if expected_workspace:
                    verified = (
                        verified
                        and str(row.workspace_id or "") == expected_workspace)
                return OracleResult(
                    action, verified,
                    f"GoalObjective {goal_id} title={row.title!r} "
                    f"workspace={row.workspace_id!r}")
            if mode == "evaluate":
                goal_id = expected_goal_id or str(ctx.get("goal_id") or "")
                if not goal_id:
                    return OracleResult(action, False, "missing goal id")
                if ctx.get("error"):
                    return OracleResult(
                        action, False, f"goal evaluation error: {ctx['error']}")

                def _read(session):
                    from core.models import GoalObjective
                    return session.query(GoalObjective).filter(
                        GoalObjective.id == goal_id).first()

                row = _read_with_db(ctx, _read)
                if row is None:
                    return OracleResult(
                        action, False, f"goal {goal_id} not persisted")
                result_status = str(ctx.get("status") or "")
                result_progress = ctx.get("progress")
                if not result_status and result_progress is None:
                    return OracleResult(
                        action, False,
                        "the evaluation returned no status/progress "
                        "observation to compare with the persisted goal")
                verified = True
                if result_status:
                    verified = verified and str(row.status or "") == result_status
                if result_progress is not None:
                    try:
                        verified = (
                            verified
                            and abs(float(row.progress or 0)
                                    - float(result_progress)) < 0.01)
                    except (TypeError, ValueError):
                        verified = False
                return OracleResult(
                    action, verified,
                    f"GoalObjective {goal_id} status={row.status!r} "
                    f"progress={row.progress!r}")
            if mode == "run":
                run = ctx.get("run") or {}
                run_id = str(ctx.get("id") or run.get("id") or "")
                if not run_id:
                    return OracleResult(action, False, "missing run id")

                def _read(session):
                    from core.models import GoalRun
                    return session.query(GoalRun).filter(
                        GoalRun.id == run_id).first()

                row = _read_with_db(ctx, _read)
                if row is None:
                    return OracleResult(
                        action, False, f"goal run {run_id} not persisted")
                expected_agent = str(
                    ctx.get("_oracle_expected_agent_id") or "")
                verified = True
                if expected_goal_id:
                    verified = (
                        verified
                        and str(row.goal_id or "") == expected_goal_id)
                if expected_agent:
                    verified = (
                        verified
                        and str(row.agent_id or "") == expected_agent)
                if str(row.status or "").lower() in {"failed", "cancelled"}:
                    verified = False
                return OracleResult(
                    action, verified,
                    f"GoalRun {run_id} goal={row.goal_id!r} "
                    f"agent={row.agent_id!r} status={row.status!r}")
            return OracleResult(action, False, f"unknown goal mode {mode!r}")
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"goal read-back failed: {e}")
    return _verify


@register_postcondition("goals.decompose")
async def _verify_plan_produced(ctx: Dict[str, Any]) -> OracleResult:
    action = "goals.decompose"
    plan = ctx.get("plan")
    if not isinstance(plan, dict):
        return OracleResult(action, False, "no plan object in the result")
    if plan.get("cycles"):
        return OracleResult(
            action, False,
            f"plan contains dependency cycles: {plan.get('cycles')!r}")
    subtasks = [item for item in (plan.get("subtasks") or [])
                if isinstance(item, dict)]
    if not subtasks:
        return OracleResult(action, False, "plan has no subtasks")
    ids = [str(item.get("id") or "") for item in subtasks]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        return OracleResult(
            action, False, "plan subtask ids are missing or duplicated")
    known = set(ids)
    for item in subtasks:
        for dependency in item.get("depends_on") or []:
            if str(dependency) not in known:
                return OracleResult(
                    action, False,
                    f"subtask {item.get('id')!r} depends on unknown "
                    f"{dependency!r}")
    groups = plan.get("execution_groups") or []
    grouped = {str(step) for group in groups if isinstance(group, list)
               for step in group}
    if grouped and grouped != known:
        return OracleResult(
            action, False,
            "execution groups do not cover exactly the subtasks")
    return OracleResult(
        action, True,
        f"plan method={plan.get('method')!r} subtasks={len(subtasks)} "
        f"groups={len(groups)}")


register_postcondition("canvas.present_markdown")(
    _canvas_present_postcondition("markdown"))
register_postcondition("canvas.present_chart")(
    _canvas_present_postcondition("chart"))
register_postcondition("canvas.update")(
    _canvas_write_postcondition(restore=False))
register_postcondition("canvas.restore_version")(
    _canvas_write_postcondition(restore=True))
register_postcondition("canvas.delete")(
    _canvas_lifecycle_postcondition("delete"))
register_postcondition("canvas.undelete")(
    _canvas_lifecycle_postcondition("undelete"))
register_postcondition("canvas.submit")(_canvas_submit_postcondition())
register_postcondition("goals.create")(_goal_postcondition("create"))
register_postcondition("goals.evaluate")(_goal_postcondition("evaluate"))
register_postcondition("goal_runs.start")(_goal_postcondition("run"))


# ===========================================================================
# Mini-app host writes — supported host-side producers (no guest execution).
# Each verifier requires a receipt written in the SAME transaction as the
# effect, bound to the executor-owned operation id and the frozen authorized
# request digest, and re-reads the authoritative store in a fresh session.
# ===========================================================================
def _mini_app_receipt_details(row: Any) -> Dict[str, Any]:
    details = getattr(row, "details_json", None) or {}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except (TypeError, ValueError):
            details = {}
    return details if isinstance(details, dict) else {}


def _mini_app_scope_reasons(
    *,
    label: str,
    tenant_id: Any,
    workspace_id: Any,
    expected_tenant: str,
    expected_workspace: str,
    strict_workspace: bool = True,
) -> list:
    reasons = []
    if str(tenant_id or "") != str(expected_tenant or ""):
        reasons.append(
            f"{label} tenant={tenant_id!r}, expected {expected_tenant!r}")
    observed_ws = str(workspace_id or "")
    expected_ws = str(expected_workspace or "")
    if expected_ws:
        if observed_ws != expected_ws:
            reasons.append(
                f"{label} workspace={workspace_id!r}, expected "
                f"{expected_workspace!r}")
    elif strict_workspace and observed_ws:
        reasons.append(
            f"{label} workspace={workspace_id!r}, expected an unscoped "
            "workspace")
    return reasons


def _mini_app_common_receipt_reasons(
    row: Any,
    *,
    action: str,
    expected_operation: str,
    expected_request: str,
    expected_tenant: str,
    expected_actor: str,
    canvas_id: str,
) -> list:
    reasons = []
    if row is None:
        return [f"no {action} receipt for this invocation"]
    details = _mini_app_receipt_details(row)
    if str(row.action_type or "") != action:
        reasons.append(f"receipt action_type={row.action_type!r}")
    if str(row.canvas_id or "") != str(canvas_id or ""):
        reasons.append("receipt canvas does not match the target")
    if str(row.tenant_id or "") != str(expected_tenant or ""):
        reasons.append(
            f"receipt tenant={row.tenant_id!r}, expected {expected_tenant!r}")
    if str(row.user_id or "") != str(expected_actor or ""):
        reasons.append(
            f"receipt actor={row.user_id!r}, expected {expected_actor!r}")
    if str(details.get("operation_id") or "") != expected_operation:
        reasons.append("receipt operation id does not match this operation")
    if str(details.get("request_sha256") or "") != expected_request:
        reasons.append("receipt does not match the authorized request")
    if str(details.get("tenant_id") or "") != str(expected_tenant or ""):
        reasons.append("receipt details tenant does not match the request")
    if str(details.get("actor_id") or "") != str(expected_actor or ""):
        reasons.append("receipt details actor does not match the request")
    return reasons


@register_postcondition("mini_app_scaffold")
async def _verify_mini_app_scaffold(ctx: Dict[str, Any]) -> OracleResult:
    """Verify a scaffolded draft app + blueprint + starter receipt."""
    action = "mini_app_scaffold"
    app_id = str(ctx.get("app_id") or "").strip()
    canvas_id = str(ctx.get("canvas_id") or "").strip()
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    expected_request = str(
        ctx.get("_oracle_expected_request_sha256") or "").strip()
    expected_name = str(
        ctx.get("_oracle_expected_mini_app_name") or "")
    expected_scopes = list(
        ctx.get("_oracle_expected_mini_app_declared_scopes") or [])
    expected_dependencies = list(
        ctx.get("_oracle_expected_mini_app_dependencies") or [])
    spec = ctx.get("_oracle_expected_mini_app_spec") or {}
    spec = spec if isinstance(spec, dict) else {}
    expected_tenant = str(ctx.get("_oracle_expected_tenant_id") or "")
    expected_workspace = str(ctx.get("_oracle_expected_workspace_id") or "")
    expected_actor = str(ctx.get("_oracle_expected_actor_id") or "")
    if not app_id or not canvas_id:
        return OracleResult(action, False, "missing scaffolded ids")
    if not expected_operation or not expected_request:
        return OracleResult(action, False, "no frozen operation/request binding")
    if not expected_tenant or not expected_actor:
        return OracleResult(action, False, "no frozen scope/actor identity")

    def _read(session):
        from sqlalchemy import desc

        from core.models import Canvas, CanvasAudit, CanvasLogic, MiniApp

        app = session.query(MiniApp).filter(MiniApp.id == app_id).first()
        canvas = session.query(Canvas).filter(Canvas.id == canvas_id).first()
        audit = (
            session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas_id,
                    CanvasAudit.action_type == action)
            .order_by(desc(CanvasAudit.created_at), desc(CanvasAudit.id))
            .first()
        )
        logic = (
            session.query(CanvasLogic)
            .filter(CanvasLogic.canvas_id == canvas_id)
            .first()
        )
        return app, canvas, audit, logic

    try:
        app, canvas, audit, logic = _fresh_read_with_db(ctx, _read)
        if app is None:
            return OracleResult(action, False, f"MiniApp {app_id} absent in DB")
        if canvas is None:
            return OracleResult(action, False, f"Canvas {canvas_id} absent in DB")
        reasons = _mini_app_common_receipt_reasons(
            audit, action=action, expected_operation=expected_operation,
            expected_request=expected_request, expected_tenant=expected_tenant,
            expected_actor=expected_actor, canvas_id=canvas_id)
        details = _mini_app_receipt_details(audit)
        if str(app.id or "") != app_id:
            reasons.append("scaffolded app id mismatch")
        if str(app.blueprint_canvas_id or "") != canvas_id:
            reasons.append("app blueprint canvas is not the returned source")
        if str(app.name or "") != expected_name:
            reasons.append(
                f"app name={app.name!r}, expected {expected_name!r}")
        if str(app.status or "") != "draft":
            reasons.append(f"app status={app.status!r}, not draft")
        if str(app.created_by or "") != expected_actor:
            reasons.append(
                f"app owner={app.created_by!r}, expected {expected_actor!r}")
        reasons.extend(_mini_app_scope_reasons(
            label="app", tenant_id=app.tenant_id,
            workspace_id=app.workspace_id, expected_tenant=expected_tenant,
            expected_workspace=expected_workspace))
        if str(canvas.mini_app_id or "") != app_id:
            reasons.append("source canvas is not linked to the app")
        if str(canvas.created_by or "") != expected_actor:
            reasons.append(
                f"canvas owner={canvas.created_by!r}, expected "
                f"{expected_actor!r}")
        reasons.extend(_mini_app_scope_reasons(
            label="canvas", tenant_id=canvas.tenant_id,
            workspace_id=canvas.workspace_id, expected_tenant=expected_tenant,
            expected_workspace=expected_workspace))
        manifest = app.manifest if isinstance(app.manifest, dict) else {}
        if str(details.get("app_id") or "") != app_id:
            reasons.append("receipt app_id does not match the scaffolded app")
        if str(details.get("name") or "") != expected_name:
            reasons.append("receipt name does not match the authorized request")
        if list(details.get("declared_scopes") or []) != list(
                manifest.get("declared_scopes") or []):
            reasons.append("receipt/scope declaration disagree")
        if expected_scopes and list(expected_scopes) != list(
                manifest.get("declared_scopes") or []):
            reasons.append("app declared scopes do not match the request")
        if expected_dependencies and list(expected_dependencies) != list(
                manifest.get("dependencies") or []):
            reasons.append("app dependencies do not match the request")
        if list(details.get("dependencies") or []) != list(
                manifest.get("dependencies") or []):
            reasons.append("receipt/dependency declaration disagree")
        expected_base = str(spec.get("base_image") or "python:3.11-slim")
        if str(manifest.get("base_image") or "") != expected_base:
            reasons.append("app base image does not match the request")
        expected_canvas_type = str(
            spec.get("canvas_type") or "mini_app").strip().lower()
        if str(manifest.get("canvas_type") or "") != expected_canvas_type:
            reasons.append("app base canvas type does not match the request")
        if logic is None:
            reasons.append("starter logic row is missing")
        else:
            try:
                from core.mini_app_service import logic_source_sha256

                digest = logic_source_sha256(logic.source)
            except Exception:  # noqa: BLE001 - unreadable is not verified
                digest = ""
            if digest != str(details.get("logic_source_sha256") or ""):
                reasons.append("starter logic digest does not match the receipt")
        return OracleResult(
            action, not reasons,
            f"MiniApp {app_id} canvas {canvas_id} "
            f"operation={expected_operation[:12]}"
            + ("" if not reasons else "; " + "; ".join(reasons)))
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(action, False, f"mini-app scaffold read-back failed: {e}")


@register_postcondition("mini_app_publish")
async def _verify_mini_app_publish(ctx: Dict[str, Any]) -> OracleResult:
    """Verify the exact publish receipt and current app/manifest material."""
    action = "mini_app_publish"
    app_id = str(
        ctx.get("_oracle_expected_app_id") or ctx.get("app_id") or "").strip()
    receipt_id = str(ctx.get("audit_id") or "").strip()
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    expected_request = str(
        ctx.get("_oracle_expected_request_sha256") or "").strip()
    expected_tenant = str(ctx.get("_oracle_expected_tenant_id") or "")
    expected_workspace = str(ctx.get("_oracle_expected_workspace_id") or "")
    expected_actor = str(ctx.get("_oracle_expected_actor_id") or "")
    if not app_id:
        return OracleResult(action, False, "missing app_id")
    if not receipt_id:
        return OracleResult(action, False, "no publish receipt from this invocation")
    if not expected_operation or not expected_request:
        return OracleResult(action, False, "no frozen operation/request binding")
    if not expected_tenant or not expected_actor:
        return OracleResult(action, False, "no frozen scope/actor identity")

    def _read(session):
        from core.models import Canvas, CanvasAudit, MiniApp

        app = session.query(MiniApp).filter(MiniApp.id == app_id).first()
        audit = (
            session.query(CanvasAudit)
            .filter(CanvasAudit.id == receipt_id,
                    CanvasAudit.action_type == action)
            .first()
        )
        canvas = None
        if app is not None and app.blueprint_canvas_id:
            canvas = (
                session.query(Canvas)
                .filter(Canvas.id == app.blueprint_canvas_id)
                .first()
            )
        return app, audit, canvas

    try:
        app, audit, canvas = _fresh_read_with_db(ctx, _read)
        if app is None:
            return OracleResult(action, False, f"MiniApp {app_id} absent in DB")
        if audit is None:
            return OracleResult(action, False, "publish receipt absent")
        if canvas is None:
            return OracleResult(action, False, "blueprint canvas absent")
        reasons = _mini_app_common_receipt_reasons(
            audit, action=action, expected_operation=expected_operation,
            expected_request=expected_request, expected_tenant=expected_tenant,
            expected_actor=expected_actor,
            canvas_id=str(app.blueprint_canvas_id or ""))
        details = _mini_app_receipt_details(audit)
        if str(details.get("app_id") or "") != app_id:
            reasons.append("receipt app_id does not match the request")
        if str(app.status or "") != "published":
            reasons.append(f"app status={app.status!r}, not published")
        if str(app.version or "") != str(details.get("version") or ""):
            reasons.append("receipt published version is not current")
        if bool(app.is_public) != bool(details.get("is_public")):
            reasons.append("receipt public flag does not match the app")
        if str(app.created_by or "") != expected_actor:
            reasons.append(
                f"app owner={app.created_by!r}, expected {expected_actor!r}")
        reasons.extend(_mini_app_scope_reasons(
            label="app", tenant_id=app.tenant_id,
            workspace_id=app.workspace_id, expected_tenant=expected_tenant,
            expected_workspace=expected_workspace))
        manifest = app.manifest if isinstance(app.manifest, dict) else {}
        if _content_digest(manifest) != str(
                details.get("manifest_sha256") or ""):
            reasons.append("current manifest does not match the published receipt")
        if _content_digest(manifest.get("blueprint")) != str(
                details.get("blueprint_sha256") or ""):
            reasons.append("current blueprint does not match the receipt")
        if _content_digest(manifest.get("initial_state")) != str(
                details.get("initial_state_sha256") or ""):
            reasons.append("current initial_state does not match the receipt")
        return OracleResult(
            action, not reasons,
            f"MiniApp {app_id} v{details.get('version')} "
            f"receipt={receipt_id[:12]} operation={expected_operation[:12]}"
            + ("" if not reasons else "; " + "; ".join(reasons)))
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(action, False, f"mini-app publish read-back failed: {e}")


@register_postcondition("mini_app_install")
async def _verify_mini_app_install(ctx: Dict[str, Any]) -> OracleResult:
    """Verify the exact new instance, installed version and install receipt."""
    action = "mini_app_install"
    app_id = str(
        ctx.get("_oracle_expected_app_id") or ctx.get("app_id") or "").strip()
    canvas_id = str(ctx.get("canvas_id") or "").strip()
    receipt_id = str(ctx.get("audit_id") or "").strip()
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    expected_request = str(
        ctx.get("_oracle_expected_request_sha256") or "").strip()
    expected_tenant = str(ctx.get("_oracle_expected_tenant_id") or "")
    expected_workspace = str(ctx.get("_oracle_expected_workspace_id") or "")
    expected_actor = str(ctx.get("_oracle_expected_actor_id") or "")
    if not app_id or not canvas_id:
        return OracleResult(action, False, "missing app/instance ids")
    if not receipt_id:
        return OracleResult(action, False, "no install receipt from this invocation")
    if not expected_operation or not expected_request:
        return OracleResult(action, False, "no frozen operation/request binding")
    if not expected_tenant or not expected_actor:
        return OracleResult(action, False, "no frozen scope/actor identity")

    def _read(session):
        from core.models import (
            Canvas, CanvasAudit, CanvasLogic, CanvasState, MiniApp,
            MiniAppInstallation,
        )

        app = session.query(MiniApp).filter(MiniApp.id == app_id).first()
        canvas = session.query(Canvas).filter(Canvas.id == canvas_id).first()
        audit = (
            session.query(CanvasAudit)
            .filter(CanvasAudit.id == receipt_id,
                    CanvasAudit.action_type == action)
            .first()
        )
        installation = (
            session.query(MiniAppInstallation)
            .filter(MiniAppInstallation.canvas_id == canvas_id)
            .first()
        )
        state = (
            session.query(CanvasState)
            .filter(CanvasState.canvas_id == canvas_id)
            .first()
        )
        logic = (
            session.query(CanvasLogic)
            .filter(CanvasLogic.canvas_id == canvas_id)
            .first()
        )
        return app, canvas, audit, installation, state, logic

    try:
        app, canvas, audit, installation, state, logic = _fresh_read_with_db(
            ctx, _read)
        if app is None:
            return OracleResult(action, False, f"MiniApp {app_id} absent in DB")
        if canvas is None:
            return OracleResult(action, False, f"instance {canvas_id} absent in DB")
        if audit is None:
            return OracleResult(action, False, "install receipt absent")
        reasons = _mini_app_common_receipt_reasons(
            audit, action=action, expected_operation=expected_operation,
            expected_request=expected_request, expected_tenant=expected_tenant,
            expected_actor=expected_actor, canvas_id=canvas_id)
        details = _mini_app_receipt_details(audit)
        if str(details.get("app_id") or "") != app_id:
            reasons.append("receipt app_id does not match the request")
        if str(details.get("instance_canvas_id") or "") != canvas_id:
            reasons.append("receipt instance canvas does not match the returned id")
        if str(details.get("installed_by") or "") != expected_actor:
            reasons.append("receipt installer does not match the actor")
        if str(canvas.mini_app_id or "") != app_id:
            reasons.append("instance canvas is not linked to the app")
        if str(canvas.created_by or "") != expected_actor:
            reasons.append(
                f"instance owner={canvas.created_by!r}, expected "
                f"{expected_actor!r}")
        reasons.extend(_mini_app_scope_reasons(
            label="instance", tenant_id=canvas.tenant_id,
            workspace_id=canvas.workspace_id, expected_tenant=expected_tenant,
            expected_workspace=expected_workspace))
        # A published-app install may legitimately belong to a different
        # instance owner; verify the sharing policy instead of owner-only rules.
        if str(app.created_by or "") != expected_actor and not (
                bool(app.is_public) and bool(getattr(app, "is_approved", False))):
            reasons.append("non-owner install is not authorized by the sharing policy")
        if str(app.status or "") != "published":
            reasons.append(f"app status={app.status!r}, not published")
        installed_version = str(details.get("installed_version") or "")
        if str(app.version or "") != installed_version:
            reasons.append("receipt installed version is not the current app version")
        manifest = app.manifest if isinstance(app.manifest, dict) else {}
        blueprint = manifest.get("blueprint") if isinstance(
            manifest.get("blueprint"), dict) else {}
        initial_state = manifest.get("initial_state")
        if _content_digest(blueprint) != str(
                details.get("blueprint_sha256") or ""):
            reasons.append("receipt blueprint does not match the app")
        if _content_digest(initial_state) != str(
                details.get("initial_state_sha256") or ""):
            reasons.append("receipt initial_state does not match the app")
        if _content_digest(manifest) != str(
                details.get("manifest_sha256") or ""):
            reasons.append("receipt manifest does not match the app")
        if installation is None:
            reasons.append("MiniAppInstallation row is missing")
        else:
            if str(installation.app_id or "") != app_id:
                reasons.append("installation app id mismatch")
            if str(installation.canvas_id or "") != canvas_id:
                reasons.append("installation canvas id mismatch")
            if str(installation.installed_by or "") != expected_actor:
                reasons.append("installation installer mismatch")
            if str(installation.tenant_id or "") != str(canvas.tenant_id or ""):
                reasons.append("installation tenant does not match the instance")
            if str(installation.installed_version or "") != installed_version:
                reasons.append("installation version does not match the receipt")
            if int(installation.installed_runtime_version or 0) != int(
                    details.get("installed_runtime_version") or 0):
                reasons.append("installation runtime version mismatch")
        if state is None:
            reasons.append("instance CanvasState row is missing")
        else:
            if int(state.version or 0) != 1:
                reasons.append(
                    f"instance state version={state.version!r}, expected 1")
            if state.state != initial_state:
                reasons.append("instance state does not match the published seed")
        if logic is not None and str(blueprint.get("logic_source") or ""):
            try:
                from core.mini_app_service import logic_source_sha256

                digest = logic_source_sha256(logic.source)
            except Exception:  # noqa: BLE001 - unreadable is not verified
                digest = ""
            if digest != logic_source_sha256(blueprint.get("logic_source")):
                reasons.append("instance logic does not match the blueprint")
        if canvas.content != blueprint.get("content"):
            reasons.append("instance content does not match the blueprint")
        if canvas.style != blueprint.get("style"):
            reasons.append("instance style does not match the blueprint")
        return OracleResult(
            action, not reasons,
            f"instance {canvas_id} app {app_id} v{installed_version} "
            f"operation={expected_operation[:12]}"
            + ("" if not reasons else "; " + "; ".join(reasons)))
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(action, False, f"mini-app install read-back failed: {e}")


def _mini_app_logic_postcondition(mode: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = (
            "mini_app_revert_logic" if mode == "revert"
            else "mini_app_write_logic")
        app_id = str(
            ctx.get("_oracle_expected_app_id") or ctx.get("app_id") or "").strip()
        receipt_id = str(ctx.get("audit_id") or "").strip()
        expected_operation = str(
            ctx.get("_oracle_expected_operation_id") or "").strip()
        expected_request = str(
            ctx.get("_oracle_expected_request_sha256") or "").strip()
        expected_tenant = str(ctx.get("_oracle_expected_tenant_id") or "")
        expected_workspace = str(ctx.get("_oracle_expected_workspace_id") or "")
        expected_actor = str(ctx.get("_oracle_expected_actor_id") or "")
        expected_source = str(
            ctx.get("_oracle_expected_mini_app_source_sha256") or "")
        expected_version = str(
            ctx.get("_oracle_expected_mini_app_version") or "")
        if not app_id:
            return OracleResult(action, False, "missing app_id")
        if not receipt_id:
            return OracleResult(action, False, "no logic receipt from this invocation")
        if not expected_operation or not expected_request:
            return OracleResult(action, False, "no frozen operation/request binding")
        if not expected_tenant or not expected_actor:
            return OracleResult(action, False, "no frozen scope/actor identity")
        if mode == "write" and not expected_source:
            return OracleResult(action, False, "no frozen logic source digest")
        if mode == "revert" and not expected_version:
            return OracleResult(action, False, "no frozen checkpoint version")

        def _read(session):
            from sqlalchemy import asc

            from core.models import Canvas, CanvasAudit, CanvasLogic, MiniApp

            app = session.query(MiniApp).filter(MiniApp.id == app_id).first()
            canvas = None
            if app is not None and app.blueprint_canvas_id:
                canvas = (
                    session.query(Canvas)
                    .filter(Canvas.id == app.blueprint_canvas_id)
                    .first()
                )
            logic = (
                session.query(CanvasLogic)
                .filter(CanvasLogic.canvas_id == app.blueprint_canvas_id)
                .first()
            ) if app is not None and app.blueprint_canvas_id else None
            receipt = (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == receipt_id)
                .first()
            )
            checkpoints = (
                session.query(CanvasAudit)
                .filter(
                    CanvasAudit.canvas_id == app.blueprint_canvas_id,
                    CanvasAudit.action_type == "mini_app_logic",
                )
                .order_by(asc(CanvasAudit.created_at), asc(CanvasAudit.id))
                .all()
            ) if app is not None and app.blueprint_canvas_id else []
            return app, canvas, logic, receipt, checkpoints

        try:
            app, canvas, logic, receipt, checkpoints = _fresh_read_with_db(
                ctx, _read)
            if app is None:
                return OracleResult(action, False, f"MiniApp {app_id} absent in DB")
            if canvas is None or logic is None:
                return OracleResult(
                    action, False, "blueprint canvas/logic row is missing")
            if receipt is None:
                return OracleResult(action, False, "logic receipt absent")
            reasons = _mini_app_common_receipt_reasons(
                receipt, action="mini_app_logic",
                expected_operation=expected_operation,
                expected_request=expected_request,
                expected_tenant=expected_tenant,
                expected_actor=expected_actor, canvas_id=canvas.id)
            details = _mini_app_receipt_details(receipt)
            if str(details.get("app_id") or "") != app_id:
                reasons.append("receipt app_id does not match the request")
            if str(app.created_by or "") != expected_actor:
                reasons.append(
                    f"app owner={app.created_by!r}, expected {expected_actor!r}")
            reasons.extend(_mini_app_scope_reasons(
                label="app", tenant_id=app.tenant_id,
                workspace_id=app.workspace_id,
                expected_tenant=expected_tenant,
                expected_workspace=expected_workspace))
            reasons.extend(_mini_app_scope_reasons(
                label="canvas", tenant_id=canvas.tenant_id,
                workspace_id=canvas.workspace_id,
                expected_tenant=expected_tenant,
                expected_workspace=expected_workspace))
            try:
                from core.mini_app_service import logic_source_sha256

                logic_digest = logic_source_sha256(logic.source)
            except Exception:  # noqa: BLE001 - unreadable is not verified
                logic_digest = ""
            receipt_digest = str(details.get("source_sha256") or "")
            if logic_digest != receipt_digest:
                reasons.append("current logic does not match the receipt digest")
            if receipt_digest != logic_source_sha256(
                    details.get("source")):
                reasons.append("receipt source does not match its digest")
            # The receipt must be the CURRENT checkpoint, not an older
            # identical version left on the canvas.
            if not checkpoints:
                reasons.append("no logic checkpoints exist")
            else:
                latest = checkpoints[-1]
                if str(latest.id or "") != receipt_id:
                    reasons.append(
                        "receipt is not the current logic checkpoint")
                max_version = max(
                    int(_mini_app_receipt_details(row).get("version") or 0)
                    for row in checkpoints)
                if int(details.get("version") or 0) != max_version:
                    reasons.append("receipt version is not the current head")
            if mode == "write":
                if logic_digest != expected_source:
                    reasons.append("logic does not match the authorized source")
            else:
                if str(details.get("reverted_to") or "") != expected_version:
                    reasons.append(
                        "receipt reverted_to does not match the authorized "
                        "checkpoint")
                target_id = str(details.get("target_audit_id") or "")
                target = next(
                    (row for row in checkpoints
                     if str(row.id or "") == target_id), None)
                if target is None:
                    reasons.append("authorized target checkpoint is absent")
                else:
                    target_details = _mini_app_receipt_details(target)
                    if str(target_details.get("version") or "") != expected_version:
                        reasons.append(
                            "target checkpoint version does not match the "
                            "authorized version")
                    target_digest = logic_source_sha256(
                        target_details.get("source"))
                    if target_digest != receipt_digest:
                        reasons.append(
                            "reverted logic does not match the target "
                            "checkpoint source")
            return OracleResult(
                action, not reasons,
                f"MiniApp {app_id} checkpoint v{details.get('version')} "
                f"operation={expected_operation[:12]}"
                + ("" if not reasons else "; " + "; ".join(reasons)))
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"mini-app logic read-back failed: {e}")
    return _verify


register_postcondition("mini_app_write_logic")(
    _mini_app_logic_postcondition("write"))
register_postcondition("mini_app_revert_logic")(
    _mini_app_logic_postcondition("revert"))


@register_postcondition("mini_app_db_write")
async def _verify_mini_app_db_write(ctx: Dict[str, Any]) -> OracleResult:
    """Verify exact record ids/sequences/material for one record mutation."""
    action = "mini_app_db_write"
    canvas_id = str(
        ctx.get("_oracle_expected_canvas_id")
        or ctx.get("_oracle_expected_db_canvas_id") or "").strip()
    receipt_id = str(ctx.get("audit_id") or "").strip()
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    expected_request = str(
        ctx.get("_oracle_expected_request_sha256") or "").strip()
    expected_tenant = str(ctx.get("_oracle_expected_tenant_id") or "")
    expected_workspace = str(ctx.get("_oracle_expected_workspace_id") or "")
    expected_actor = str(ctx.get("_oracle_expected_actor_id") or "")
    expected_op = str(ctx.get("_oracle_expected_db_op") or "")
    expected_series = ctx.get("_oracle_expected_db_series")
    expected_data = ctx.get("_oracle_expected_db_data")
    expected_record_id = str(
        ctx.get("_oracle_expected_db_record_id") or "")
    expected_append_id = str(
        ctx.get("_oracle_expected_db_append_id") or "")
    expected_filter = ctx.get("_oracle_expected_db_filter") or {}
    if not canvas_id:
        return OracleResult(action, False, "missing instance canvas_id")
    if not receipt_id:
        return OracleResult(action, False, "no db_write receipt from this invocation")
    if not expected_operation or not expected_request:
        return OracleResult(action, False, "no frozen operation/request binding")
    if not expected_tenant or not expected_actor:
        return OracleResult(action, False, "no frozen scope/actor identity")
    if expected_op not in {
            "append", "update", "update_many", "delete", "delete_series",
            "clear"}:
        return OracleResult(action, False, "no frozen record operation")

    def _read(session):
        from core.models import Canvas, CanvasAudit, CanvasRecord, MiniApp

        canvas = session.query(Canvas).filter(Canvas.id == canvas_id).first()
        app = None
        if canvas is not None and canvas.mini_app_id:
            app = (
                session.query(MiniApp)
                .filter(MiniApp.id == canvas.mini_app_id)
                .first()
            )
        receipt = (
            session.query(CanvasAudit)
            .filter(CanvasAudit.id == receipt_id,
                    CanvasAudit.action_type == action)
            .first()
        )
        rows = (
            session.query(CanvasRecord)
            .filter(CanvasRecord.canvas_id == canvas_id)
            .all()
        )
        return canvas, app, receipt, rows

    try:
        canvas, app, receipt, rows = _fresh_read_with_db(ctx, _read)
        if canvas is None:
            return OracleResult(action, False, f"instance {canvas_id} absent in DB")
        if app is None:
            return OracleResult(action, False, "instance app is absent in DB")
        if receipt is None:
            return OracleResult(action, False, "db_write receipt absent")
        reasons = _mini_app_common_receipt_reasons(
            receipt, action=action, expected_operation=expected_operation,
            expected_request=expected_request, expected_tenant=expected_tenant,
            expected_actor=expected_actor, canvas_id=canvas_id)
        details = _mini_app_receipt_details(receipt)
        effect = details.get("effect") if isinstance(
            details.get("effect"), dict) else {}
        if str(details.get("canvas_id") or "") != canvas_id:
            reasons.append("receipt canvas_id does not match the instance")
        if str(details.get("app_id") or "") != str(app.id or ""):
            reasons.append("receipt app_id does not match the instance app")
        if str(details.get("op") or "") != expected_op:
            reasons.append("receipt op does not match the authorized request")
        expected_series_text = (
            "" if expected_op in {"clear"} else str(expected_series or ""))
        if str(details.get("series") or "") != expected_series_text:
            reasons.append("receipt series does not match the authorized request")
        # The record store is owner-gated by the instance or app owner.
        if not (
                str(canvas.created_by or "") == expected_actor
                or str(app.created_by or "") == expected_actor):
            reasons.append("actor is not the instance/app owner")
        reasons.extend(_mini_app_scope_reasons(
            label="instance", tenant_id=canvas.tenant_id,
            workspace_id=canvas.workspace_id, expected_tenant=expected_tenant,
            expected_workspace=expected_workspace))
        by_id = {str(row.id): row for row in rows}

        def _row_matches(row: Any) -> list:
            problems = []
            if str(row.canvas_id or "") != canvas_id:
                problems.append("record canvas mismatch")
            if str(row.app_id or "") != str(app.id or ""):
                problems.append("record app mismatch")
            if str(row.series or "") != expected_series_text:
                problems.append("record series mismatch")
            return problems

        if expected_op == "append":
            record_id = str(effect.get("record_id") or "")
            row = by_id.get(record_id)
            if not record_id:
                reasons.append("receipt carries no appended record id")
            if expected_append_id and expected_append_id != record_id:
                reasons.append("appended record id does not match the request")
            if row is None:
                reasons.append("appended record is absent")
            else:
                reasons.extend(_row_matches(row))
                if int(row.seq or 0) != int(effect.get("seq") or 0):
                    reasons.append("appended record sequence mismatch")
                if row.data != expected_data:
                    reasons.append("appended record data does not match the request")
                if _content_digest(row.data) != str(
                        effect.get("data_sha256") or ""):
                    reasons.append("appended record digest mismatch")
                if str(row.tenant_id or "") != str(canvas.tenant_id or ""):
                    reasons.append("appended record tenant mismatch")
                if str(row.created_by or "") != expected_actor:
                    reasons.append("appended record creator mismatch")
        elif expected_op == "update":
            if str(effect.get("record_id") or "") != expected_record_id:
                reasons.append("receipt record id does not match the request")
            row = by_id.get(expected_record_id)
            if row is None:
                reasons.append("updated record is absent")
            else:
                reasons.extend(_row_matches(row))
                if int(row.seq or 0) != int(effect.get("seq") or 0):
                    reasons.append("updated record sequence mismatch")
                prior = effect.get("prior_data")
                merged = dict(prior or {})
                if not isinstance(expected_data, dict):
                    reasons.append("no frozen update payload")
                else:
                    merged.update(expected_data)
                if row.data != merged or effect.get("data") != merged:
                    reasons.append("updated record data does not match prior+request")
                if _content_digest(row.data) != str(
                        effect.get("data_sha256") or ""):
                    reasons.append("updated record digest mismatch")
                if _content_digest(prior) != str(
                        effect.get("prior_sha256") or ""):
                    reasons.append("updated record prior digest mismatch")
        elif expected_op == "update_many":
            records = effect.get("records") if isinstance(
                effect.get("records"), list) else []
            if effect.get("filter") != expected_filter:
                reasons.append("receipt filter does not match the request")
            if not records:
                reasons.append("receipt carries no affected record set")
            if int(effect.get("updated") or 0) != len(records):
                reasons.append("receipt affected-record list is incomplete")
            seen = set()
            for item in records:
                if not isinstance(item, dict):
                    reasons.append("malformed affected-record entry")
                    continue
                rid = str(item.get("id") or "")
                if not rid or rid in seen:
                    reasons.append("affected record ids are missing/duplicated")
                    continue
                seen.add(rid)
                row = by_id.get(rid)
                if row is None:
                    reasons.append(f"affected record {rid[:12]} is absent")
                    continue
                reasons.extend(_row_matches(row))
                if int(row.seq or 0) != int(item.get("seq") or 0):
                    reasons.append(f"affected record {rid[:12]} sequence mismatch")
                if _content_digest(row.data) != str(
                        item.get("data_sha256") or ""):
                    reasons.append(f"affected record {rid[:12]} digest mismatch")
                if isinstance(expected_data, dict) and isinstance(row.data, dict):
                    for key, value in expected_data.items():
                        if row.data.get(key) != value:
                            reasons.append(
                                f"affected record {rid[:12]} does not carry "
                                "the authorized update")
                            break
        elif expected_op == "delete":
            if str(effect.get("record_id") or "") != expected_record_id:
                reasons.append("receipt record id does not match the request")
            if expected_record_id in by_id:
                reasons.append("deleted record is still present")
            if not str(effect.get("prior_sha256") or ""):
                reasons.append("receipt carries no deleted-record material")
        elif expected_op in {"delete_series", "clear"}:
            records = effect.get("records") if isinstance(
                effect.get("records"), list) else []
            if not records:
                reasons.append("receipt carries no deleted record set")
            if int(effect.get("deleted") or 0) != len(records):
                reasons.append("receipt deleted-record list is incomplete")
            seen = set()
            for item in records:
                if not isinstance(item, dict):
                    reasons.append("malformed deleted-record entry")
                    continue
                rid = str(item.get("id") or "")
                if not rid or rid in seen:
                    reasons.append("deleted record ids are missing/duplicated")
                    continue
                seen.add(rid)
                if rid in by_id:
                    reasons.append(f"deleted record {rid[:12]} is still present")
            if expected_op == "delete_series" and str(
                    details.get("series") or "") != expected_series_text:
                reasons.append("delete_series target series mismatch")
        return OracleResult(
            action, not reasons,
            f"canvas {canvas_id} {expected_op} "
            f"operation={expected_operation[:12]}"
            + ("" if not reasons else "; " + "; ".join(reasons)))
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(action, False, f"mini-app record read-back failed: {e}")


# ---------------------------------------------------------------------------
# AgentRadio thread creation
# ---------------------------------------------------------------------------


@register_durable_receipt_projector("radio.create_thread")
def _radio_thread_durable_receipt_projection(
    result: Dict[str, Any], expected: Dict[str, Any],
) -> Dict[str, Any]:
    from core.agent_radio.radio_thread_mutations import (
        durable_thread_receipt_projection,
    )

    return durable_thread_receipt_projection(result, expected)


@register_durable_receipt_matcher("radio.create_thread")
def _radio_thread_durable_receipt_conflicts(
    expected: Dict[str, Any], durable_result: Dict[str, Any],
) -> Iterable[str]:
    from core.agent_radio.radio_thread_mutations import (
        durable_thread_material_conflicts,
    )

    return durable_thread_material_conflicts(expected, durable_result)


@register_postcondition("radio.create_thread")
async def _verify_radio_create_thread(ctx: Dict[str, Any]) -> OracleResult:
    """Verify one radio thread by exact id/material and current authority.

    The durable row locates the thread; it does not supply authority.  The
    verifier re-reads the exact ``AgentThread`` row in a fresh session and
    re-runs the same single-tenant AgentRegistry scope checks used before the
    write.  A later disabled/moved/deleted creator or member is therefore a
    truthful stale-authority refusal, never a copied-details success.
    """
    from core.agent_radio.radio_thread_mutations import (
        authorize_thread_material,
        find_threads_by_operation,
        observed_thread_material,
        read_thread,
        thread_material_mismatches,
    )

    action = "radio.create_thread"
    expected_material = ctx.get("_oracle_expected_radio_thread")
    if not isinstance(expected_material, dict) or not expected_material:
        return OracleResult(
            action, False, "no frozen accepted radio thread material")

    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    if not expected_operation:
        return OracleResult(action, False, "no frozen operation identity")

    expected_digest = _digest(ctx.get("_oracle_expected_payload_sha256"))
    if not _valid_digest(expected_digest):
        return OracleResult(
            action, False, "no valid frozen request payload digest")

    action_result = str(ctx.get("action_result") or "").strip().lower()
    result_digest = _digest(ctx.get("payload_sha256"))
    if result_digest:
        if not _valid_digest(result_digest):
            return OracleResult(
                action, False, "result carries no valid payload digest")
        if result_digest != expected_digest:
            return OracleResult(
                action, False,
                "returned payload digest does not match the expected request")
    elif action_result == "applied":
        return OracleResult(
            action, False, "result carries no valid payload digest")

    receipt = ctx.get("provider_receipt")
    if isinstance(receipt, dict) and receipt:
        if str(receipt.get("operation_id") or "") != expected_operation:
            return OracleResult(
                action, False,
                "returned operation id does not match the expected operation")
        if _digest(receipt.get("payload_sha256")) != expected_digest:
            return OracleResult(
                action, False,
                "provider receipt payload digest does not match the request")
    elif action_result == "applied":
        return OracleResult(action, False, "no provider receipt")

    expected_thread_id = str(
        ctx.get("thread_id") or ctx.get("remote_id") or "").strip()
    expected_creator = str(
        expected_material.get("created_by_agent_id") or "").strip()
    expected_members = list(
        expected_material.get("member_agent_ids") or [])

    read_receipt = ctx.get("read_receipt")
    if isinstance(read_receipt, dict) and read_receipt:
        coverage = str(read_receipt.get("coverage") or "").lower()
        if coverage not in {"single", "complete"}:
            return OracleResult(
                action, False, f"read_receipt.coverage == {coverage!r}")
        receipt_id = str(read_receipt.get("resource_id") or "").strip()
        if expected_thread_id and receipt_id and receipt_id != expected_thread_id:
            return OracleResult(
                action, False,
                "read_receipt.resource_id does not match the thread id")
        receipt_fields = read_receipt.get("fields")
        if isinstance(receipt_fields, dict) and receipt_fields:
            receipt_mismatches = thread_material_mismatches(
                expected_material, receipt_fields)
            if receipt_mismatches:
                return OracleResult(
                    action, False,
                    "producer readback does not match the accepted material: "
                    + ", ".join(receipt_mismatches))

    def _read(session):
        row = None
        if expected_thread_id:
            row = read_thread(session, expected_thread_id)
        operation_rows = find_threads_by_operation(
            session, expected_operation, expected_creator) \
            if expected_operation else []
        if len(operation_rows) > 1:
            return None, [], (
                f"multiple threads ({len(operation_rows)}) are bound to the "
                f"same operation {expected_operation}")
        operation_row = operation_rows[0] if operation_rows else None
        if row is None:
            row = operation_row
        elif operation_row is not None and str(
                getattr(operation_row, "id", "")) != expected_thread_id:
            return None, [], (
                "operation id is bound to a different thread than the "
                "returned identity")
        if row is None:
            return None, [], ""
        problems, _creator = authorize_thread_material(
            session,
            expected_creator,
            expected_members,
            workspace_id=str(expected_material.get("workspace_id") or ""),
            tenant_id=str(expected_material.get("tenant_id") or ""),
            context_tier="",
            allow_unknown_tier=True,
        )
        return row, problems, ""

    try:
        # A fresh session is mandatory: the caller's identity map could
        # otherwise certify an uncommitted/expired row.
        row, authority_problems, conflict = _fresh_read_with_db(ctx, _read)
    except Exception as exc:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            action, False,
            "radio thread readback failed: "
            f"{type(exc).__name__}: {str(exc)[:200]}")
    if conflict:
        return OracleResult(action, False, conflict)
    if row is None:
        return OracleResult(
            action, False,
            "radio thread absent in the authoritative store")
    observed_id = str(getattr(row, "id", "") or "").strip()
    if expected_thread_id and observed_id != expected_thread_id:
        return OracleResult(
            action, False,
            "independent radio readback returned a different thread id")
    observed = observed_thread_material(row)
    mismatches = thread_material_mismatches(expected_material, observed)
    if mismatches:
        return OracleResult(
            action, False,
            "independent radio readback contradicts the accepted material: "
            + ", ".join(mismatches))
    if authority_problems:
        return OracleResult(
            action, False,
            "current creator/member authority no longer supports the roster: "
            + "; ".join(authority_problems))
    return OracleResult(
        action, True,
        f"radio thread {observed_id} re-read; authorized material and current "
        f"AgentRegistry authority match (payload {expected_digest[:12]})")


# ===========================================================================
# BPE harness mutations — workspace.note / workspace.commit
# ===========================================================================
# These actions mutate the per-scope workspace state persisted by the existing
# BPE JSON store. The producer records an exact operation/scope/material
# receipt in that same snapshot; these verifiers independently re-load the
# snapshot from disk. They never read the tool's result envelope, so a forged
# echo or an in-memory-only state cannot certify the request.

def _bpe_expected_binding(ctx: Dict[str, Any], action: str):
    expected = {
        "operation_id": str(
            ctx.get("_oracle_expected_operation_id") or "").strip(),
        "workspace_id": str(
            ctx.get("_oracle_expected_bpe_workspace_id") or "").strip(),
        "agent_id": str(
            ctx.get("_oracle_expected_bpe_agent_id") or "").strip(),
        "scope_key": str(
            ctx.get("_oracle_expected_bpe_scope_key") or ""),
        "actor_id": str(
            ctx.get("_oracle_expected_bpe_actor_id") or ""),
        "material": ctx.get("_oracle_expected_bpe_material"),
        "material_sha256": _digest(
            ctx.get("_oracle_expected_bpe_material_sha256")),
    }
    missing = [
        key for key in (
            "operation_id", "workspace_id", "agent_id", "scope_key",
            "material", "material_sha256",
        )
        if expected[key] in (None, "", {}, [])
    ]
    if missing:
        return None, (
            "missing frozen BPE operation/scope/material binding: "
            + ", ".join(missing))
    if not isinstance(expected["material"], dict):
        return None, "frozen BPE material is not an object"
    if not _valid_digest(expected["material_sha256"]):
        return None, "frozen BPE material digest is not sha256"
    return expected, ""


def _bpe_receipt_mismatches(
    receipt: Dict[str, Any], expected: Dict[str, Any], action: str,
) -> list:
    mismatches = []
    if str(receipt.get("action") or "") != action:
        mismatches.append("action")
    for field in (
        "operation_id", "workspace_id", "agent_id", "scope_key", "actor_id",
    ):
        if str(receipt.get(field) or "") != str(expected[field]):
            mismatches.append(field)
    receipt_digest = _digest(receipt.get("material_sha256"))
    if receipt_digest != expected["material_sha256"]:
        mismatches.append("material_sha256")
    if receipt.get("material") != expected["material"]:
        mismatches.append("material")
    return mismatches


def _bpe_receipt(snapshot: Dict[str, Any], action: str, operation_id: str):
    receipts = snapshot.get("operation_receipts")
    if not isinstance(receipts, list):
        return None
    for receipt in reversed(receipts):
        if not isinstance(receipt, dict):
            continue
        if (
            str(receipt.get("action") or "") == action
            and str(receipt.get("operation_id") or "") == operation_id
        ):
            return receipt
    return None


def _bpe_note_in_state(snapshot: Dict[str, Any], content: str) -> bool:
    pending = snapshot.get("pending_notes")
    if isinstance(pending, list) and any(
            str(item) == content for item in pending):
        return True
    experience = snapshot.get("experience")
    if isinstance(experience, dict):
        for entries in experience.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict) and str(
                        entry.get("content") or "") == content:
                    return True
    return False


def _bpe_commit_in_state(
    snapshot: Dict[str, Any], receipt: Dict[str, Any],
    material: Dict[str, Any],
) -> bool:
    resolved_title = str(
        receipt.get("resolved_title") or material.get("title") or "")
    if not resolved_title:
        return False
    expected_status = material.get("status")
    progress = snapshot.get("progress")
    if not isinstance(progress, list):
        return False
    for subgoal in progress:
        if not isinstance(subgoal, dict):
            continue
        if str(subgoal.get("title") or "") != resolved_title:
            continue
        if expected_status is None:
            # A new subgoal starts pending. An existing same-title done entry
            # cannot stand in for the append this operation authorized.
            if str(subgoal.get("status") or "pending") == "pending":
                return True
        elif str(subgoal.get("status") or "") == str(expected_status):
            return True
    return False


def _bpe_postcondition(action: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        expected, problem = _bpe_expected_binding(ctx, action)
        if problem:
            return OracleResult(action, False, problem)
        try:
            from core.bpe.persistence import BPEWorkspaceStore

            snapshot = BPEWorkspaceStore().load(
                expected["workspace_id"], expected["agent_id"],
                expected["scope_key"])
        except Exception as exc:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False,
                "BPE durable read-back failed: "
                f"{type(exc).__name__}: {str(exc)[:200]}")
        if not isinstance(snapshot, dict) or not snapshot:
            return OracleResult(
                action, False,
                "no persisted BPE scope for the frozen workspace/agent/run")
        receipt = _bpe_receipt(snapshot, action, expected["operation_id"])
        if receipt is None:
            return OracleResult(
                action, False,
                "no durable receipt for the exact operation/scope in the "
                "persisted BPE state")
        mismatches = _bpe_receipt_mismatches(receipt, expected, action)
        if mismatches:
            return OracleResult(
                action, False,
                "durable BPE receipt contradicts the frozen request: "
                + ", ".join(mismatches))
        material = expected["material"]
        if action == "workspace.note":
            content = str(material.get("content") or "")
            if not content or not _bpe_note_in_state(snapshot, content):
                return OracleResult(
                    action, False,
                    "note content is absent from the independently reloaded "
                    "pending/consolidated workspace state")
            return OracleResult(
                action, True,
                "durable note receipt matches operation/scope/material and "
                f"the content is present in reloaded state "
                f"(payload {expected['material_sha256'][:12]})")
        if not _bpe_commit_in_state(snapshot, receipt, material):
            return OracleResult(
                action, False,
                "the authorized subgoal/status is absent from the "
                "independently reloaded Progress state")
        return OracleResult(
            action, True,
            "durable commit receipt matches operation/scope/material and the "
            f"subgoal is present in reloaded Progress state "
            f"(payload {expected['material_sha256'][:12]})")
    return _verify


register_postcondition("workspace.note")(_bpe_postcondition("workspace.note"))
register_postcondition("workspace.commit")(
    _bpe_postcondition("workspace.commit"))
