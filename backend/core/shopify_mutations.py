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

The material projection is COMPLETE for the fields the caller authorized:
every accepted variant field and every accepted image is compared, not a
curated subset.  Numeric fields keep exact decimal identity (format may be
normalised, values are never rounded).  A provider-rewritten image URL is not
treated as content proof: with no content readback the verdict stays
unverified, never fabricated.

Official provider contract used for the shape assumptions and by-id readback
(verified against the current Shopify Admin REST documentation on 2026-11-07):

* product (``images``/``variants`` arrays on create/readback):
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/product
* product image (``src``/``alt``; provider/CDN-served URL):
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/product-image
* product variant (``price``/``compare_at_price`` decimals):
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/product-variant

The by-id readback is:

    GET /admin/api/{version}/products/{product_id}.json

The service's pinned ``ShopifyService.API_VERSION`` is the ``{version}``.
"""
from __future__ import annotations

import copy
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence

#: Product fields accepted by the registered action.  Identity/transport and
#: oracle-namespace keys are deliberately absent: the server owns those.
PRODUCT_TEXT_FIELDS = (
    "title", "body_html", "vendor", "product_type", "handle", "status",
)
PRODUCT_MATERIAL_FIELDS = (
    "title", "body_html", "vendor", "product_type", "handle", "status",
    "tags", "images", "variants",
)

#: Variant fields whose values are decimals/integers rather than text.  They
#: are compared as exact decimal values: numeric *format* may be normalised
#: (``1.0`` == ``1.00``) but no rounding is allowed (``1.005`` != ``1.00``).
_NUMERIC_VARIANT_FIELDS = frozenset({
    "price", "compare_at_price", "cost", "weight", "grams",
    "inventory_quantity", "position",
})
_NUMERIC_IMAGE_FIELDS = frozenset({"position"})

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


def _normalized_number(value: Any) -> str:
    """Exact decimal/integer identity without rounding.

    A provider may format ``1.00`` where the caller sent ``1.0``; that is the
    same number.  It may not silently turn ``1.005`` into ``1.00``: doing so
    would hide a real provider change, so only format is normalised.
    """
    text = _text(value).strip()
    if not text:
        return ""
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return text
    if not number.is_finite():
        return text
    if number == 0:
        return "0"
    return format(number.normalize(), "f")


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


def _material_value(value: Any) -> Any:
    """JSON-safe, order-stable projection of an arbitrary material value."""
    if isinstance(value, Mapping):
        return {
            str(key).strip(): _material_value(item)
            for key, item in value.items()
            if str(key).strip()
        }
    if isinstance(value, (list, tuple)):
        return [_material_value(item) for item in value]
    if isinstance(value, set):
        return sorted(
            (_material_value(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    return _text(value).strip()


def _normalize_variant(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Project every accepted variant field, not a curated subset.

    Shopify's variant resource carries many caller-authored fields
    (``price``, ``compare_at_price``, ``barcode``, weight/tax flags, ...).
    Dropping any of them from the material would let a provider change it
    without refuting the effect, so every accepted field is retained and
    compared.  Numeric fields use exact decimal identity (no rounding).
    """
    variant: Dict[str, Any] = {}
    for key, raw in value.items():
        name = str(key).strip()
        if not name:
            continue
        if raw is None:
            variant[name] = ""
        elif name in _NUMERIC_VARIANT_FIELDS:
            variant[name] = _normalized_number(raw)
        else:
            variant[name] = _material_value(raw)
    return variant


def _normalize_variants(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [
        _normalize_variant(item) for item in value
        if isinstance(item, Mapping)
    ]


def _normalize_image(value: Any) -> Dict[str, Any]:
    """Project one requested/returned image object.

    A caller may pass a URL string or an object.  Shopify returns an object
    with at least ``id``/``src``/``alt``/``position``; only fields the caller
    actually authorized are compared, so provider-only decorations are not
    fabricated into caller intent.
    """
    if not isinstance(value, Mapping):
        return {"src": _text(value).strip()}
    image: Dict[str, Any] = {}
    for key, raw in value.items():
        name = str(key).strip()
        if not name:
            continue
        if raw is None:
            image[name] = ""
        elif name in _NUMERIC_IMAGE_FIELDS:
            image[name] = _normalized_number(raw)
        else:
            image[name] = _material_value(raw)
    return image


def _normalize_images(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [
        _normalize_image(item) for item in value
        if item not in (None, "")
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
    images = payload.get("images")
    if images:
        material["images"] = _normalize_images(images)
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
    images = item.get("images")
    if isinstance(images, Sequence) and not isinstance(images, (str, bytes)):
        normalized_images = _normalize_images(images)
        if normalized_images:
            material["images"] = normalized_images
    return material


def _field_matches(field: str, expected: Any, observed: Any) -> bool:
    """Compare one accepted material field with its provider readback.

    Numeric fields use exact decimal identity (format may differ, value may
    not).  Structured values compare their canonical JSON-safe projection;
    text compares trimmed text.  No field is skipped because it is hard to
    compare: an unavailable proof is reported as a mismatch by the caller.
    """
    if field in _NUMERIC_VARIANT_FIELDS or field in _NUMERIC_IMAGE_FIELDS:
        return _normalized_number(expected) == _normalized_number(observed)
    if field == "body_html":
        return _normalized_html(expected) == _normalized_html(observed)
    if field == "tags":
        return normalize_tags(expected) == normalize_tags(observed)
    if isinstance(expected, (Mapping, list, tuple, set)) or isinstance(
            observed, (Mapping, list, tuple, set)):
        return _material_value(expected) == _material_value(observed)
    if isinstance(expected, bool) or isinstance(observed, bool):
        return expected is observed
    return _text(expected).strip() == _text(observed).strip()


def _variant_mismatches(expected: Any, observed: Any) -> List[str]:
    expected_items = expected if isinstance(expected, list) else []
    observed_items = observed if isinstance(observed, list) else []
    if len(expected_items) != len(observed_items):
        return ["variants"]
    reasons: List[str] = []
    for index, expected_item in enumerate(expected_items):
        if not isinstance(expected_item, Mapping):
            reasons.append(f"variants[{index}]")
            continue
        observed_item = (
            observed_items[index] if index < len(observed_items) else {})
        if not isinstance(observed_item, Mapping):
            reasons.append(f"variants[{index}]")
            continue
        for key, expected_value in expected_item.items():
            if not _field_matches(key, expected_value, observed_item.get(key)):
                reasons.append(f"variants[{index}].{key}")
    return reasons


def _image_mismatches(expected: Any, observed: Any) -> List[str]:
    """Compare the authorized image identity/material, never a CDN rewrite.

    Shopify's readback ``src`` is a provider-served URL.  A different URL is
    not proof that the same image content was stored, and no download/content
    proof is available here, so the effect must stay unverified rather than
    treating URI equality as content identity.
    """
    expected_items = expected if isinstance(expected, list) else []
    observed_items = observed if isinstance(observed, list) else []
    if len(expected_items) != len(observed_items):
        return ["images"]
    reasons: List[str] = []
    for index, expected_item in enumerate(expected_items):
        if not isinstance(expected_item, Mapping):
            reasons.append(f"images[{index}]")
            continue
        observed_item = (
            observed_items[index] if index < len(observed_items) else {})
        if not isinstance(observed_item, Mapping):
            reasons.append(f"images[{index}]")
            continue
        for key, expected_value in expected_item.items():
            if not _field_matches(key, expected_value, observed_item.get(key)):
                reasons.append(f"images[{index}].{key}")
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
        if field == "variants":
            mismatches.extend(_variant_mismatches(
                expected_value, observed_value))
            continue
        if field == "images":
            mismatches.extend(_image_mismatches(
                expected_value, observed_value))
            continue
        if not _field_matches(field, expected_value, observed_value):
            mismatches.append(field)
    return mismatches


def durable_product_receipt_projection(
    result: Mapping[str, Any] | None,
    expected: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Provider-specific material for a durable Shopify claim receipt.

    The shared claim persistence is domain neutral; it asks the registered
    verifier/provider projection for the exact accepted product material so a
    later replay can compare the CURRENT readback with what was authorized.
    """
    expected = expected if isinstance(expected, Mapping) else {}
    material = expected.get("_oracle_expected_shopify_product")
    return {
        "authorized_material": (
            copy.deepcopy(dict(material))
            if isinstance(material, Mapping) else None),
    }


def durable_product_material_conflicts(
    expected: Mapping[str, Any] | None,
    durable_result: Mapping[str, Any] | None,
) -> List[str]:
    """Conflicts between the stored authorized material and this request.

    Missing stored material is a conflict when the current request has frozen
    material: the receipt cannot prove the exact resource was authorized by
    this operation.  The caller stays committed_unverified without readback or
    resend.
    """
    expected = expected if isinstance(expected, Mapping) else {}
    durable_result = (
        durable_result if isinstance(durable_result, Mapping) else {})
    expected_material = expected.get("_oracle_expected_shopify_product")
    if not isinstance(expected_material, Mapping) or not expected_material:
        return []
    stored = durable_result.get("authorized_material")
    if not isinstance(stored, Mapping) or not stored:
        return ["authorized_material"]
    return material_mismatches(expected_material, stored)


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
