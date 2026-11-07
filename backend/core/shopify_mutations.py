"""Shopify hosted-mutation producers and bound material normalization.

Why this module
---------------
The registered Shopify product-create action used to return the provider's
raw transport object.  A transport 201 (or an object whose title happened to
match) was therefore enough for the action layer to report success, even
though no one had re-read the exact resource from the authoritative shop.

This module keeps the existing service/transport surface and adds only the
pieces the postcondition oracle needs:

* a canonical business payload derived from the *accepted* arguments (never
  from model- or body-supplied store/credential selectors);
* a canonical material projection that is comparable between the accepted
  request and a fresh provider readback;
* a producer that creates through ``ShopifyService``, reads the exact
  resource id back through the service, and reports an explicit
  applied/uncertain outcome.  Missing or contradictory readback is never
  turned into success.

Official provider contract used for the by-id readback (verified against the
current Shopify Admin REST documentation on 2026-11-07):

    GET /admin/api/{version}/products/{product_id}.json
    https://shopify.dev/docs/api/admin-rest/2026-07/resources/product

The service's pinned ``ShopifyService.API_VERSION`` is the ``{version}``.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence

#: Product fields accepted by the registered action.  Identity/transport and
#: oracle-namespace keys are deliberately absent: the server owns those.
PRODUCT_TEXT_FIELDS = (
    "title", "body_html", "vendor", "product_type", "handle", "status",
)
PRODUCT_MATERIAL_FIELDS = (
    "title", "body_html", "vendor", "product_type", "handle", "status",
    "tags",
)

#: A body/model argument that names a store or credential is a default-store
#: override attempt, not product material.  Refuse before any transport call.
STORE_SELECTOR_FIELDS = frozenset({
    "shop", "shop_domain", "store", "store_id", "store_domain",
    "access_token", "token", "credentials", "tenant_id", "workspace_id",
})


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _normalized_html(value: Any) -> str:
    return _text(value).replace("\r\n", "\n").replace("\r", "\n")


def _normalized_price(value: Any) -> str:
    text = _text(value).strip()
    if not text:
        return ""
    try:
        return str(Decimal(text).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return text


def normalize_tags(value: Any) -> List[str]:
    """Canonical tag identity: trimmed, non-empty, order-insensitive."""
    if isinstance(value, (list, tuple, set)):
        parts = [_text(item).strip() for item in value]
    else:
        parts = [part.strip() for part in _text(value).split(",")]
    return sorted({part for part in parts if part}, key=str.casefold)


def _tags_payload(value: Any) -> str:
    # Shopify accepts a comma-separated string and returns one.  Sending the
    # canonical string keeps the request digest stable for list/string input.
    return ", ".join(sorted(
        {part.strip() for part in (
            [_text(item) for item in value]
            if isinstance(value, (list, tuple, set))
            else _text(value).split(",")
        ) if part.strip()}, key=str.casefold))


def _normalize_variant(value: Mapping[str, Any]) -> Dict[str, Any]:
    variant: Dict[str, Any] = {}
    for key in ("option1", "option2", "option3", "title", "sku"):
        raw = value.get(key)
        if raw not in (None, ""):
            variant[key] = _text(raw).strip()
    price = value.get("price")
    if price not in (None, ""):
        variant["price"] = _normalized_price(price)
    return variant


def _normalize_variants(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [
        _normalize_variant(item) for item in value
        if isinstance(item, Mapping)
    ]


def product_payload(arguments: Mapping[str, Any] | None) -> Dict[str, Any]:
    """The exact provider product payload derived from accepted arguments.

    Only registered product fields are forwarded.  The returned mapping is
    also the material whose digest is frozen in the request binding, so both
    producer and oracle hash the same bytes.
    """
    args = arguments if isinstance(arguments, Mapping) else {}
    payload: Dict[str, Any] = {
        "title": _text(args.get("title")),
        "body_html": _normalized_html(args.get("body_html")),
        "vendor": _text(args.get("vendor")),
        "product_type": _text(args.get("product_type")),
        "status": _text(args.get("status") or "active"),
    }
    handle = args.get("handle")
    if handle not in (None, ""):
        payload["handle"] = _text(handle).strip()
    tags = args.get("tags")
    if tags not in (None, "", [], ()):
        payload["tags"] = _tags_payload(tags)
    variants = args.get("variants")
    if isinstance(variants, Sequence) and not isinstance(variants, (str, bytes)):
        normalized = [
            dict(item) for item in variants if isinstance(item, Mapping)
        ]
        if normalized:
            payload["variants"] = normalized
    images = args.get("images")
    if isinstance(images, Sequence) and not isinstance(images, (str, bytes)):
        normalized_images = [
            dict(item) if isinstance(item, Mapping) else _text(item)
            for item in images
            if item not in (None, "")
        ]
        if normalized_images:
            payload["images"] = normalized_images
    return payload


def accepted_product_material(
    arguments: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """The business material the caller authorized for the product.

    Optional fields the caller did not provide are omitted: Shopify derives
    a handle and may fill provider defaults, and those are not fabricated
    caller intent.  ``status`` is always present because the action contract
    defaults it to ``active``.
    """
    payload = product_payload(arguments)
    args = arguments if isinstance(arguments, Mapping) else {}
    material: Dict[str, Any] = {
        "title": _text(payload.get("title")).strip(),
        "body_html": _normalized_html(payload.get("body_html")),
        "vendor": _text(payload.get("vendor")),
        "product_type": _text(payload.get("product_type")),
        "status": _text(payload.get("status")),
    }
    if "handle" in payload:
        material["handle"] = _text(payload.get("handle")).strip()
    if "tags" in payload:
        material["tags"] = normalize_tags(args.get("tags"))
    variants = payload.get("variants")
    if variants:
        material["variants"] = _normalize_variants(variants)
    return material


def observed_product_material(product: Mapping[str, Any] | None) -> Dict[str, Any]:
    """The comparable business material of a provider product readback."""
    item = product if isinstance(product, Mapping) else {}
    material: Dict[str, Any] = {
        "title": _text(item.get("title")).strip(),
        "body_html": _normalized_html(item.get("body_html")),
        "vendor": _text(item.get("vendor")),
        "product_type": _text(item.get("product_type")),
        "status": _text(item.get("status")),
        "tags": normalize_tags(item.get("tags")),
    }
    if item.get("handle") not in (None, ""):
        material["handle"] = _text(item.get("handle")).strip()
    variants = item.get("variants")
    if isinstance(variants, Sequence) and not isinstance(variants, (str, bytes)):
        normalized = _normalize_variants(variants)
        if normalized:
            material["variants"] = normalized
    return material


def _variant_mismatches(expected: Any, observed: Any) -> List[str]:
    expected_items = expected if isinstance(expected, list) else []
    observed_items = observed if isinstance(observed, list) else []
    if len(expected_items) != len(observed_items):
        return ["variants"]
    reasons: List[str] = []
    for index, expected_item in enumerate(expected_items):
        if not isinstance(expected_item, Mapping):
            continue
        observed_item = (
            observed_items[index] if index < len(observed_items) else {})
        if not isinstance(observed_item, Mapping):
            reasons.append(f"variants[{index}]")
            continue
        for key, expected_value in expected_item.items():
            observed_value = observed_item.get(key)
            if key == "price":
                same = _normalized_price(expected_value) == _normalized_price(
                    observed_value)
            else:
                same = _text(expected_value).strip() == _text(
                    observed_value).strip()
            if not same:
                reasons.append(f"variants[{index}].{key}")
    return reasons


def material_mismatches(
    expected: Mapping[str, Any] | None,
    observed: Mapping[str, Any] | None,
) -> List[str]:
    """Names of accepted material fields that the readback contradicts."""
    want = expected if isinstance(expected, Mapping) else {}
    got = observed if isinstance(observed, Mapping) else {}
    mismatches: List[str] = []
    for field, expected_value in want.items():
        observed_value = got.get(field)
        if field == "tags":
            same = normalize_tags(expected_value) == normalize_tags(
                observed_value)
        elif field == "variants":
            mismatches.extend(_variant_mismatches(
                expected_value, observed_value))
            continue
        elif field == "body_html":
            same = _normalized_html(expected_value) == _normalized_html(
                observed_value)
        else:
            same = _text(expected_value).strip() == _text(
                observed_value).strip()
        if not same:
            mismatches.append(field)
    return mismatches


def _payload_digest(payload: Mapping[str, Any]) -> str:
    from core.task_lifecycle import _approval_payload_hash

    return _approval_payload_hash(dict(payload))


def _uncertain(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    product_id: str,
    product: Optional[Dict[str, Any]],
    error_kind: str,
    message: str,
    verification: Dict[str, Any],
    read_receipt: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """An explicit post-dispatch ambiguity; never a fabricated success."""
    return {
        "status": "uncertain",
        "success": False,
        "action_result": "uncertain",
        "effect_possible": True,
        "provider": "shopify",
        "operation": "create_product",
        "error_kind": error_kind,
        "error": message,
        "retryable": False,
        "remote_id": product_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_product",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": product_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": verification,
        "product": product,
        "evidence": [evidence] if evidence else [],
    }


def _applied(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    product_id: str,
    product: Dict[str, Any],
    read_receipt: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "status": "success",
        "success": True,
        "action_result": "applied",
        "provider": "shopify",
        "operation": "create_product",
        "remote_id": product_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_product",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": product_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": {
            "status": "verified",
            "missing_fields": [],
            "mismatches": [],
        },
        "product": product,
    }


async def create_product(
    token: str,
    shop: str,
    arguments: Mapping[str, Any] | None,
    *,
    operation_id: str = "",
) -> Dict[str, Any]:
    """Create one product, then bind the exact id/shop/material readback."""
    from integrations.shopify_service import ShopifyService

    payload = product_payload(arguments)
    expected_material = accepted_product_material(arguments)
    digest = _payload_digest(payload)
    operation = str(operation_id or "")
    service = ShopifyService()

    try:
        created = await service.create_product(token, shop, product=payload)
    except Exception as exc:  # noqa: BLE001 - provider may have applied it
        return _uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            product_id="",
            product=None,
            error_kind="provider_error",
            message=(
                "Shopify product creation did not return a confirmation; "
                f"the effect may have landed ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["transport_confirmation"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_product_transport_error",
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    created = created if isinstance(created, dict) else {}
    product_id = str(created.get("id") or "").strip()
    if not product_id:
        return _uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            product_id="",
            product=created or None,
            error_kind="unidentified_effect",
            message=(
                "Shopify accepted the create request but returned no product "
                "id; the effect cannot be identified and is not safe to "
                "recreate"),
            verification={
                "status": "incomplete",
                "missing_fields": ["remote_id"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_product_missing_id",
                "returned_keys": sorted(created)[:20],
            },
        )

    try:
        observed = await service.get_product(token, shop, product_id)
    except Exception as exc:  # noqa: BLE001 - absent readback is not success
        return _uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            product_id=product_id,
            product=created,
            error_kind="readback_unavailable",
            message=(
                "Shopify product was created but the exact resource could not "
                f"be read back ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_product_readback_unavailable",
                "remote_id": product_id,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    observed = observed if isinstance(observed, dict) else {}
    observed_material = observed_product_material(observed)
    observed_id = str(observed.get("id") or "").strip()
    mismatches = material_mismatches(expected_material, observed_material)
    if observed_id != product_id:
        mismatches.append("remote_id")
    read_receipt = {
        "provider": "shopify",
        "operation": "get_product",
        "resource_id": observed_id,
        "requested_remote_id": product_id,
        "observed_remote_id": observed_id,
        "coverage": "single",
        "account_id": shop,
        "shop": shop,
        "fields": observed_material,
    }
    if mismatches:
        return _uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            product_id=product_id,
            product=observed or created,
            error_kind="readback_mismatch",
            message=(
                "The Shopify readback did not match the accepted product "
                "material: " + ", ".join(mismatches)),
            verification={
                "status": "mismatch",
                "missing_fields": [],
                "mismatches": mismatches,
            },
            read_receipt=read_receipt,
            evidence={
                "kind": "shopify_create_product_readback_mismatch",
                "remote_id": product_id,
                "observed_remote_id": observed_id,
                "mismatches": mismatches,
            },
        )

    return _applied(
        shop=shop,
        operation_id=operation,
        payload_sha256=digest,
        product_id=product_id,
        product=observed or created,
        read_receipt=read_receipt,
    )
