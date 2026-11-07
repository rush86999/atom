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
from datetime import datetime, timezone
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
    # Decimal.normalize() applies the caller's precision and can round.
    # Fixed-point formatting preserves the coefficient exactly; strip only
    # fractional zero padding, never integral zeros or meaningful digits.
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


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


def _normalized_bool(value: Any, default: Any = None) -> Any:
    """Normalise a boolean business field without inventing a value.

    An absent provider field must be omitted from observed material so the
    verifier reports it as unproven; it must never default to the accepted
    value.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return value


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


def blog_payload(arguments: Mapping[str, Any] | None) -> Dict[str, Any]:
    """The exact provider blog payload derived from accepted arguments.

    Only the registered blog fields (``title`` and optional ``handle``) are
    forwarded.  If the caller did not authorize a handle, the provider may
    derive one; that derived value is not fabricated into caller intent.
    """
    args = arguments if isinstance(arguments, Mapping) else {}
    payload: Dict[str, Any] = {"title": _text(args.get("title"))}
    handle = args.get("handle")
    if handle not in (None, ""):
        payload["handle"] = _text(handle).strip()
    return payload


def accepted_blog_material(
    arguments: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """The business material the caller authorized for the blog."""
    payload = blog_payload(arguments)
    material: Dict[str, Any] = {
        "title": _text(payload.get("title")).strip(),
    }
    if "handle" in payload:
        material["handle"] = _text(payload.get("handle")).strip()
    return material


def observed_blog_material(blog: Mapping[str, Any] | None) -> Dict[str, Any]:
    """The comparable business material of a provider blog readback."""
    item = blog if isinstance(blog, Mapping) else {}
    material: Dict[str, Any] = {
        "title": _text(item.get("title")).strip(),
    }
    if item.get("handle") not in (None, ""):
        material["handle"] = _text(item.get("handle")).strip()
    return material


def durable_blog_receipt_projection(
    result: Mapping[str, Any] | None,
    expected: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Provider-specific material for a durable Shopify blog claim receipt."""
    expected = expected if isinstance(expected, Mapping) else {}
    material = expected.get("_oracle_expected_shopify_blog")
    return {
        "authorized_material": (
            copy.deepcopy(dict(material))
            if isinstance(material, Mapping) else None),
    }


def durable_blog_material_conflicts(
    expected: Mapping[str, Any] | None,
    durable_result: Mapping[str, Any] | None,
) -> List[str]:
    """Conflicts between the stored authorized blog material and this request."""
    expected = expected if isinstance(expected, Mapping) else {}
    durable_result = (
        durable_result if isinstance(durable_result, Mapping) else {})
    expected_material = expected.get("_oracle_expected_shopify_blog")
    if not isinstance(expected_material, Mapping) or not expected_material:
        return []
    stored = durable_result.get("authorized_material")
    if not isinstance(stored, Mapping) or not stored:
        return ["authorized_material"]
    return material_mismatches(expected_material, stored)


def article_payload(arguments: Mapping[str, Any] | None) -> Dict[str, Any]:
    """The exact business payload derived from accepted article arguments.

    ``blog_id`` is the target scope and is included in the frozen payload
    digest even though Shopify carries it in the URL rather than the JSON
    body.  Optional fields the caller did not authorize are omitted so a
    provider-derived value cannot be mistaken for caller intent.
    """
    args = arguments if isinstance(arguments, Mapping) else {}
    payload: Dict[str, Any] = {
        "blog_id": _text(args.get("blog_id")).strip(),
        "title": _text(args.get("title")),
        "body_html": _normalized_html(args.get("body_html", "")),
        "published": _normalized_bool(args.get("published", True), True),
    }
    author = args.get("author")
    if author not in (None, ""):
        payload["author"] = _text(author).strip()
    tags = args.get("tags")
    if tags not in (None, "", [], ()):
        payload["tags"] = _tags_payload(tags)
    return payload


def accepted_article_material(
    arguments: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """The business material the caller authorized for the article."""
    payload = article_payload(arguments)
    material: Dict[str, Any] = {
        "blog_id": _text(payload.get("blog_id")).strip(),
        "title": _text(payload.get("title")).strip(),
        "body_html": _normalized_html(payload.get("body_html")),
        "published": _normalized_bool(payload.get("published"), True),
    }
    if "author" in payload:
        material["author"] = _text(payload.get("author")).strip()
    if "tags" in payload:
        material["tags"] = normalize_tags(payload.get("tags"))
    return material


def _observed_publication_state(
    article: Mapping[str, Any] | None,
) -> tuple[Optional[bool], str]:
    """Derive publication from the official REST ``published_at`` field.

    ``None`` is an observed draft (unpublished).  A timezone-aware timestamp
    in the past is observed published; a future timestamp is scheduled and is
    not yet published.  Missing, malformed, naive, or contradictory fields
    return ``(None, reason)`` and must never be defaulted to the requested
    value.

    If a legacy ``published`` boolean is also present, it may only confirm the
    ``published_at`` state; a disagreement is contradictory and unknown.
    """
    item = article if isinstance(article, Mapping) else {}
    if "published_at" not in item:
        return None, "missing_published_at"
    raw = item.get("published_at")
    if raw is None:
        state: Optional[bool] = False
        reason = "draft"
    elif isinstance(raw, datetime):
        timestamp = raw
        state = None
        reason = "malformed_published_at"
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None, "malformed_published_at"
        try:
            timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None, "malformed_published_at"
        state = None
        reason = "malformed_published_at"
    else:
        return None, "malformed_published_at"

    if state is None:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return None, "naive_published_at"
        if timestamp > datetime.now(timezone.utc):
            return None, "scheduled"
        state = True
        reason = "published"

    if "published" in item:
        observed_published = item.get("published")
        if not isinstance(observed_published, bool):
            return None, "contradictory_published"
        if observed_published != state:
            return None, "contradictory_published"
    return state, reason


def observed_article_material(
    article: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """The comparable business material of a provider article readback.

    Official REST readbacks expose ``published_at`` rather than the
    request-only ``published`` value.  An absent, malformed, naive, future, or
    contradictory publication field is omitted, never defaulted to the
    accepted value: the verifier then reports it as unproven.
    """
    item = article if isinstance(article, Mapping) else {}
    material: Dict[str, Any] = {
        "blog_id": _text(item.get("blog_id")).strip(),
        "title": _text(item.get("title")).strip(),
        "body_html": _normalized_html(item.get("body_html")),
    }
    published, _reason = _observed_publication_state(item)
    if published is not None:
        material["published"] = published
    if item.get("author") not in (None, ""):
        material["author"] = _text(item.get("author")).strip()
    if item.get("tags") not in (None, ""):
        material["tags"] = normalize_tags(item.get("tags"))
    return material


def durable_article_receipt_projection(
    result: Mapping[str, Any] | None,
    expected: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Provider-specific material for a durable Shopify article claim."""
    expected = expected if isinstance(expected, Mapping) else {}
    material = expected.get("_oracle_expected_shopify_article")
    return {
        "authorized_material": (
            copy.deepcopy(dict(material))
            if isinstance(material, Mapping) else None),
    }


def durable_article_material_conflicts(
    expected: Mapping[str, Any] | None,
    durable_result: Mapping[str, Any] | None,
) -> List[str]:
    """Conflicts between the stored authorized article material and request."""
    expected = expected if isinstance(expected, Mapping) else {}
    durable_result = (
        durable_result if isinstance(durable_result, Mapping) else {})
    expected_material = expected.get("_oracle_expected_shopify_article")
    if not isinstance(expected_material, Mapping) or not expected_material:
        return []
    stored = durable_result.get("authorized_material")
    if not isinstance(stored, Mapping) or not stored:
        return ["authorized_material"]
    return material_mismatches(expected_material, stored)


def fulfillment_payload(
    arguments: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """The exact business payload derived from accepted fulfillment args.

    ``notify_customer`` is an input preference and is part of the request
    binding, but it is not a field Shopify returns on the Fulfillment
    resource, so it is deliberately not part of the readback material.
    """
    args = arguments if isinstance(arguments, Mapping) else {}
    payload: Dict[str, Any] = {
        "order_id": _text(args.get("order_id")).strip(),
        "notify_customer": _normalized_bool(
            args.get("notify_customer", True), True),
    }
    for field in ("location_id", "tracking_number", "tracking_company"):
        value = args.get(field)
        if value not in (None, ""):
            payload[field] = _text(value).strip()
    return payload


def accepted_fulfillment_material(
    arguments: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """The caller-authorized fulfillment material supported by the registry."""
    payload = fulfillment_payload(arguments)
    material: Dict[str, Any] = {
        "order_id": _text(payload.get("order_id")).strip(),
    }
    for field in ("location_id", "tracking_number", "tracking_company"):
        if field in payload:
            material[field] = _text(payload.get(field)).strip()
    return material


def _fulfillment_planned_quantity(line_item: Mapping[str, Any]) -> str:
    """Quantity still to be fulfilled in a source fulfillment order.

    This is the planning namespace.  It may fall back through the source FO
    line's remaining/fulfillable quantity; it is never the completed quantity
    observed on a Fulfillment resource.
    """
    for field in ("remaining_quantity", "fulfillable_quantity", "quantity"):
        value = line_item.get(field)
        if value is not None:
            return _normalized_number(value)
    return ""


def _fulfillment_completed_quantity(line_item: Mapping[str, Any]) -> str:
    """Quantity completed by a Fulfillment line item.

    The Fulfillment resource reports the fulfilled ``quantity``; its
    ``fulfillable_quantity`` is commonly 0 after the fact and must never be
    borrowed as the completed amount.
    """
    value = line_item.get("quantity")
    return "" if value is None else _normalized_number(value)


def _fulfillment_source_line_identity(line_item: Mapping[str, Any]) -> str:
    """Order-line id of a source FulfillmentOrder line.

    ``FulfillmentOrder.line_items[].id`` is the FO-line id, not the order-line
    id.  Only ``line_item_id`` names the order line, so a missing value stays
    missing and the pre-effect validator refuses it.
    """
    return _text(line_item.get("line_item_id")).strip()


def _fulfillment_observed_line_identity(line_item: Mapping[str, Any]) -> str:
    """Order-line id of a completed Fulfillment line.

    The documented Fulfillment line item uses ``id`` for the order-line id
    (the FO-line namespace does not apply here).  A provider that also returns
    ``line_item_id`` is accepted, but no other field is borrowed.
    """
    return _text(
        line_item.get("line_item_id") or line_item.get("id")).strip()


def _fulfillment_line_material(
    line_item: Mapping[str, Any],
    *,
    fulfillment_order_id: Any = None,
    completed: bool = False,
) -> Dict[str, Any]:
    entry = {
        "line_item_id": (
            _fulfillment_observed_line_identity(line_item)
            if completed else _fulfillment_source_line_identity(line_item)),
        "quantity": (
            _fulfillment_completed_quantity(line_item)
            if completed else _fulfillment_planned_quantity(line_item)),
    }
    fo_id = _text(
        line_item.get("fulfillment_order_id")
        if fulfillment_order_id is None else fulfillment_order_id
    ).strip()
    if fo_id:
        entry["fulfillment_order_id"] = fo_id
    return entry


def fulfillment_dispatch_plan(
    fulfillment_orders: Any,
    location_id: Any = "",
) -> Dict[str, Any]:
    """Exact server-resolved dispatch material for a fulfillment create.

    The registry does not accept fulfillment-order/line-item/quantity ids;
    these are derived from the order's current fulfillment orders immediately
    before the POST and bound to the durable receipt.  A provider readback must
    match them exactly.
    """
    orders = (
        fulfillment_orders
        if isinstance(fulfillment_orders, Sequence)
        and not isinstance(fulfillment_orders, (str, bytes))
        else []
    )
    fulfillment_order_ids = []
    line_items = []
    for order in orders:
        if not isinstance(order, Mapping):
            continue
        fo_id = _text(order.get("id")).strip()
        if fo_id:
            fulfillment_order_ids.append(fo_id)
        for line_item in order.get("line_items") or []:
            if isinstance(line_item, Mapping):
                line_items.append(_fulfillment_line_material(
                    line_item, fulfillment_order_id=fo_id))
    line_items.sort(key=lambda item: (
        item.get("fulfillment_order_id", ""), item["line_item_id"],
        item["quantity"]))
    return {
        "fulfillment_order_ids": sorted(set(fulfillment_order_ids)),
        "line_items": line_items,
        "location_id": _text(location_id).strip(),
    }


def _tracking_number(item: Mapping[str, Any]) -> Optional[str]:
    direct = item.get("tracking_number")
    if direct not in (None, ""):
        return _text(direct).strip()
    numbers = item.get("tracking_numbers")
    if isinstance(numbers, Sequence) and not isinstance(
            numbers, (str, bytes)):
        values = [
            _text(value).strip() for value in numbers
            if value not in (None, "")
        ]
        if len(values) == 1:
            return values[0]
    return None


def observed_fulfillment_material(
    fulfillment: Mapping[str, Any] | None,
    *,
    fulfillment_order_ids: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Comparable material of an exact Fulfillment readback.

    The official Fulfillment resource carries completed line ``quantity`` but
    no trustworthy fulfillment-order association.  ``fulfillment_order_ids``
    is the authoritative association read from the documented FO-scoped
    fulfillments endpoint; it is never inferred from the request.  Completed
    quantities are read from ``quantity`` only, never from
    ``fulfillable_quantity``/``remaining_quantity``.
    """
    item = fulfillment if isinstance(fulfillment, Mapping) else {}
    material: Dict[str, Any] = {
        "order_id": _text(item.get("order_id")).strip(),
    }
    status = _text(item.get("status")).strip()
    if status:
        material["status"] = status
    if item.get("location_id") not in (None, ""):
        material["location_id"] = _text(item.get("location_id")).strip()
    tracking_number = _tracking_number(item)
    if tracking_number is not None:
        material["tracking_number"] = tracking_number
    if item.get("tracking_company") not in (None, ""):
        material["tracking_company"] = _text(
            item.get("tracking_company")).strip()

    fulfillment_order_ids_set = set()
    line_items = []
    for line_item in item.get("line_items") or []:
        if not isinstance(line_item, Mapping):
            continue
        fo_id = _text(
            line_item.get("fulfillment_order_id")).strip()
        if fo_id:
            fulfillment_order_ids_set.add(fo_id)
        line_items.append(_fulfillment_line_material(
            line_item, fulfillment_order_id=fo_id, completed=True))
    for order in item.get("fulfillment_orders") or []:
        if isinstance(order, Mapping):
            fo_id = _text(
                order.get("fulfillment_order_id")
                or order.get("id")).strip()
        else:
            fo_id = _text(order).strip()
        if fo_id:
            fulfillment_order_ids_set.add(fo_id)
    if fulfillment_order_ids is not None:
        fulfillment_order_ids_set = {
            _text(value).strip() for value in fulfillment_order_ids
            if _text(value).strip()
        }
    line_items.sort(key=lambda entry: (
        entry.get("fulfillment_order_id", ""), entry["line_item_id"],
        entry["quantity"]))
    material["fulfillment_order_ids"] = sorted(fulfillment_order_ids_set)
    material["line_items"] = line_items
    return material


def fulfillment_status_issue(
    fulfillment: Mapping[str, Any] | None,
) -> str:
    """Why a Fulfillment readback is not completed business success.

    ``success`` is the only completed state.  ``failure``/``cancelled``/
    ``error`` are contradictory; ``pending``/``open``/missing are honestly
    unresolved.  None of them may be reported as verified success and none
    may trigger a resend.
    """
    item = fulfillment if isinstance(fulfillment, Mapping) else {}
    status = _text(item.get("status")).strip().lower()
    if status == "success":
        return ""
    if not status:
        return "fulfillment status is missing"
    if status in {"failure", "failed", "cancelled", "canceled", "error"}:
        return f"fulfillment status is {status}"
    return f"fulfillment status {status} is not completed success"


def _fulfillment_line_identity(line: Mapping[str, Any]) -> tuple:
    return (
        _text(line.get("line_item_id")).strip(),
        _normalized_number(line.get("quantity")),
    )


def fulfillment_plan_mismatches(
    plan: Mapping[str, Any] | None,
    observed: Mapping[str, Any] | None,
) -> List[str]:
    """Fields where the readback contradicts the server-resolved plan.

    Fulfillment-order association is compared as the exact authoritative id
    set.  Completed line identity is compared by order-line id plus completed
    quantity.  The official line item has no fulfillment-order id, so a
    per-line FO id is only compared when the provider actually supplied one.
    """
    if not isinstance(plan, Mapping) or not plan:
        return ["dispatch_plan"]
    got = observed if isinstance(observed, Mapping) else {}
    reasons: List[str] = []
    for field in ("fulfillment_order_ids", "location_id"):
        if not _field_matches(field, plan.get(field), got.get(field)):
            reasons.append(field)

    planned_lines = [
        line for line in (plan.get("line_items") or [])
        if isinstance(line, Mapping)
    ]
    observed_lines = [
        line for line in (got.get("line_items") or [])
        if isinstance(line, Mapping)
    ]
    observed_has_fo_ids = bool(observed_lines) and all(
        _text(line.get("fulfillment_order_id")).strip()
        for line in observed_lines)
    if observed_has_fo_ids:
        planned_identity = sorted(
            (line.get("fulfillment_order_id", ""),
             _text(line.get("line_item_id")).strip(),
             _normalized_number(line.get("quantity")))
            for line in planned_lines
        )
        observed_identity = sorted(
            (line.get("fulfillment_order_id", ""),
             _text(line.get("line_item_id")).strip(),
             _normalized_number(line.get("quantity")))
            for line in observed_lines
        )
    else:
        planned_identity = sorted(
            _fulfillment_line_identity(line) for line in planned_lines)
        observed_identity = sorted(
            _fulfillment_line_identity(line) for line in observed_lines)
    if planned_identity != observed_identity:
        reasons.append("line_items")
    return reasons


async def authoritative_fulfillment_order_ids(
    service: Any,
    token: str,
    shop: str,
    planned_fulfillment_order_ids: Sequence[Any],
    fulfillment_id: str,
) -> List[str]:
    """FO ids whose documented FO-scoped collection links this fulfillment.

    The association is read from
    ``GET /fulfillment_orders/{id}/fulfillments.json`` for every planned FO.
    A missing/contradictory link is returned as an absent id, so the caller's
    plan comparison stays unverified instead of inventing the association.
    """
    linked: List[str] = []
    for raw_id in planned_fulfillment_order_ids or []:
        fo_id = _text(raw_id).strip()
        if not fo_id:
            continue
        items = await service.get_fulfillment_order_fulfillments(
            token, shop, fo_id)
        for item in items or []:
            if isinstance(item, Mapping) and str(
                item.get("id") or ""
            ).strip() == str(fulfillment_id):
                linked.append(fo_id)
                break
    return linked


def durable_fulfillment_receipt_projection(
    result: Mapping[str, Any] | None,
    expected: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Authorized material plus the server-derived dispatch plan."""
    expected = expected if isinstance(expected, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}
    material = expected.get("_oracle_expected_shopify_fulfillment")
    plan = result.get("dispatch_plan")
    return {
        "authorized_material": (
            copy.deepcopy(dict(material))
            if isinstance(material, Mapping) else None),
        "dispatch_plan": (
            copy.deepcopy(dict(plan))
            if isinstance(plan, Mapping) else None),
    }


def durable_fulfillment_material_conflicts(
    expected: Mapping[str, Any] | None,
    durable_result: Mapping[str, Any] | None,
) -> List[str]:
    """Conflicts between stored authorized material/plan and this request."""
    expected = expected if isinstance(expected, Mapping) else {}
    durable_result = (
        durable_result if isinstance(durable_result, Mapping) else {})
    expected_material = expected.get("_oracle_expected_shopify_fulfillment")
    if not isinstance(expected_material, Mapping) or not expected_material:
        return []
    stored = durable_result.get("authorized_material")
    if not isinstance(stored, Mapping) or not stored:
        return ["authorized_material"]
    reasons = material_mismatches(expected_material, stored)
    if not isinstance(durable_result.get("dispatch_plan"), Mapping):
        reasons.append("dispatch_plan")
    return reasons


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


def _blog_uncertain(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    blog_id: str,
    blog: Optional[Dict[str, Any]],
    error_kind: str,
    message: str,
    verification: Dict[str, Any],
    read_receipt: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """An explicit post-dispatch blog ambiguity; never a fabricated success."""
    return {
        "status": "uncertain",
        "success": False,
        "action_result": "uncertain",
        "effect_possible": True,
        "provider": "shopify",
        "operation": "create_blog",
        "error_kind": error_kind,
        "error": message,
        "retryable": False,
        "remote_id": blog_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_blog",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": blog_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": verification,
        "blog": blog,
        "evidence": [evidence] if evidence else [],
    }


def _blog_applied(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    blog_id: str,
    blog: Dict[str, Any],
    read_receipt: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "status": "success",
        "success": True,
        "action_result": "applied",
        "provider": "shopify",
        "operation": "create_blog",
        "remote_id": blog_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_blog",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": blog_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": {
            "status": "verified",
            "missing_fields": [],
            "mismatches": [],
        },
        "blog": blog,
    }


async def create_blog(
    token: str,
    shop: str,
    arguments: Mapping[str, Any] | None,
    *,
    operation_id: str = "",
) -> Dict[str, Any]:
    """Create one blog, then bind the exact id/shop/material readback.

    Official contract (verified 2026-11-07):
    ``POST /admin/api/{version}/blogs.json`` and
    ``GET /admin/api/{version}/blogs/{blog_id}.json``
    https://shopify.dev/docs/api/admin-rest/2026-07/resources/blog
    """
    from integrations.shopify_service import ShopifyService

    payload = blog_payload(arguments)
    expected_material = accepted_blog_material(arguments)
    digest = _payload_digest(payload)
    operation = str(operation_id or "")
    service = ShopifyService()

    try:
        created = await service.create_blog(
            token, shop,
            title=_text(payload.get("title")),
            handle=payload.get("handle"))
    except Exception as exc:  # noqa: BLE001 - provider may have applied it
        return _blog_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            blog_id="",
            blog=None,
            error_kind="provider_error",
            message=(
                "Shopify blog creation did not return a confirmation; "
                f"the effect may have landed ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["transport_confirmation"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_blog_transport_error",
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    created = created if isinstance(created, dict) else {}
    blog_id = str(created.get("id") or "").strip()
    if not blog_id:
        return _blog_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            blog_id="",
            blog=created or None,
            error_kind="unidentified_effect",
            message=(
                "Shopify accepted the blog create request but returned no "
                "blog id; the effect cannot be identified and is not safe to "
                "recreate"),
            verification={
                "status": "incomplete",
                "missing_fields": ["remote_id"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_blog_missing_id",
                "returned_keys": sorted(created)[:20],
            },
        )

    try:
        observed = await service.get_blog(token, shop, blog_id)
    except Exception as exc:  # noqa: BLE001 - absent readback is not success
        return _blog_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            blog_id=blog_id,
            blog=created,
            error_kind="readback_unavailable",
            message=(
                "Shopify blog was created but the exact resource could not "
                f"be read back ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_blog_readback_unavailable",
                "remote_id": blog_id,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    observed = observed if isinstance(observed, dict) else {}
    observed_material = observed_blog_material(observed)
    observed_id = str(observed.get("id") or "").strip()
    mismatches = material_mismatches(expected_material, observed_material)
    if observed_id != blog_id:
        mismatches.append("remote_id")
    read_receipt = {
        "provider": "shopify",
        "operation": "get_blog",
        "resource_id": observed_id,
        "requested_remote_id": blog_id,
        "observed_remote_id": observed_id,
        "coverage": "single",
        "account_id": shop,
        "shop": shop,
        "fields": observed_material,
    }
    if mismatches:
        return _blog_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            blog_id=blog_id,
            blog=observed or created,
            error_kind="readback_mismatch",
            message=(
                "The Shopify readback did not match the accepted blog "
                "material: " + ", ".join(mismatches)),
            verification={
                "status": "mismatch",
                "missing_fields": [],
                "mismatches": mismatches,
            },
            read_receipt=read_receipt,
            evidence={
                "kind": "shopify_create_blog_readback_mismatch",
                "remote_id": blog_id,
                "observed_remote_id": observed_id,
                "mismatches": mismatches,
            },
        )

    return _blog_applied(
        shop=shop,
        operation_id=operation,
        payload_sha256=digest,
        blog_id=blog_id,
        blog=observed or created,
        read_receipt=read_receipt,
    )


def _article_uncertain(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    article_id: str,
    article: Optional[Dict[str, Any]],
    error_kind: str,
    message: str,
    verification: Dict[str, Any],
    read_receipt: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """An explicit post-dispatch article ambiguity; never a success."""
    return {
        "status": "uncertain",
        "success": False,
        "action_result": "uncertain",
        "effect_possible": True,
        "provider": "shopify",
        "operation": "create_article",
        "error_kind": error_kind,
        "error": message,
        "retryable": False,
        "remote_id": article_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_article",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": article_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": verification,
        "article": article,
        "evidence": [evidence] if evidence else [],
    }


def _article_applied(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    article_id: str,
    article: Dict[str, Any],
    read_receipt: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "status": "success",
        "success": True,
        "action_result": "applied",
        "provider": "shopify",
        "operation": "create_article",
        "remote_id": article_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_article",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": article_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": {
            "status": "verified",
            "missing_fields": [],
            "mismatches": [],
        },
        "article": article,
    }


async def create_article(
    token: str,
    shop: str,
    arguments: Mapping[str, Any] | None,
    *,
    operation_id: str = "",
) -> Dict[str, Any]:
    """Create one article, then bind the exact id/blog/material readback.

    Official contract (verified 2026-11-07):
    ``POST /admin/api/{version}/blogs/{blog_id}/articles.json`` and
    ``GET /admin/api/{version}/blogs/{blog_id}/articles/{article_id}.json``
    https://shopify.dev/docs/api/admin-rest/2026-07/resources/article
    """
    from integrations.shopify_service import ShopifyService

    payload = article_payload(arguments)
    expected_material = accepted_article_material(arguments)
    digest = _payload_digest(payload)
    operation = str(operation_id or "")
    service = ShopifyService()

    try:
        created = await service.create_article(
            token, shop,
            blog_id=_text(payload.get("blog_id")),
            title=_text(payload.get("title")),
            body_html=_text(payload.get("body_html")),
            author=payload.get("author"),
            tags=payload.get("tags"),
            published=payload.get("published"),
        )
    except Exception as exc:  # noqa: BLE001 - provider may have applied it
        return _article_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            article_id="",
            article=None,
            error_kind="provider_error",
            message=(
                "Shopify article creation did not return a confirmation; "
                f"the effect may have landed ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["transport_confirmation"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_article_transport_error",
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    created = created if isinstance(created, dict) else {}
    article_id = str(created.get("id") or "").strip()
    if not article_id:
        return _article_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            article_id="",
            article=created or None,
            error_kind="unidentified_effect",
            message=(
                "Shopify accepted the article create request but returned no "
                "article id; the effect cannot be identified and is not safe "
                "to recreate"),
            verification={
                "status": "incomplete",
                "missing_fields": ["remote_id"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_article_missing_id",
                "returned_keys": sorted(created)[:20],
            },
        )

    blog_id = _text(payload.get("blog_id"))
    try:
        observed = await service.get_article(
            token, shop, blog_id, article_id)
    except Exception as exc:  # noqa: BLE001 - absent readback is not success
        return _article_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            article_id=article_id,
            article=created,
            error_kind="readback_unavailable",
            message=(
                "Shopify article was created but the exact resource could "
                f"not be read back ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_article_readback_unavailable",
                "remote_id": article_id,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    observed = observed if isinstance(observed, dict) else {}
    observed_material = observed_article_material(observed)
    publication_state, publication_reason = _observed_publication_state(observed)
    observed_published_at = observed.get("published_at")
    if isinstance(observed_published_at, datetime):
        observed_published_at = observed_published_at.isoformat()
    observed_id = str(observed.get("id") or "").strip()
    mismatches = material_mismatches(expected_material, observed_material)
    if observed_id != article_id:
        mismatches.append("remote_id")
    read_receipt = {
        "provider": "shopify",
        "operation": "get_article",
        "resource_id": observed_id,
        "requested_remote_id": article_id,
        "observed_remote_id": observed_id,
        "coverage": "single",
        "account_id": shop,
        "shop": shop,
        "fields": observed_material,
        "publication": {
            "published_at": observed_published_at,
            "state": publication_state,
            "reason": publication_reason,
        },
    }
    if mismatches:
        return _article_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            article_id=article_id,
            article=observed or created,
            error_kind="readback_mismatch",
            message=(
                "The Shopify readback did not match the accepted article "
                "material: " + ", ".join(mismatches)),
            verification={
                "status": "mismatch",
                "missing_fields": [],
                "mismatches": mismatches,
            },
            read_receipt=read_receipt,
            evidence={
                "kind": "shopify_create_article_readback_mismatch",
                "remote_id": article_id,
                "observed_remote_id": observed_id,
                "mismatches": mismatches,
            },
        )

    return _article_applied(
        shop=shop,
        operation_id=operation,
        payload_sha256=digest,
        article_id=article_id,
        article=observed or created,
        read_receipt=read_receipt,
    )


def _fulfillment_failed_before_effect(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    error_kind: str,
    message: str,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """An explicit pre-dispatch refusal: no provider effect occurred."""
    return {
        "status": "failed_before_effect",
        "success": False,
        "action_result": "proven_not_applied",
        "effect_possible": False,
        "provider": "shopify",
        "operation": "create_fulfillment",
        "error_kind": error_kind,
        "error": message,
        "message": message,
        "retryable": False,
        "remote_id": "",
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_fulfillment",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": "",
            "shop": shop,
        },
        "evidence": [evidence] if evidence else [],
    }


def _fulfillment_uncertain(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    fulfillment_id: str,
    fulfillment: Optional[Dict[str, Any]],
    error_kind: str,
    message: str,
    verification: Dict[str, Any],
    read_receipt: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """An explicit post-dispatch fulfillment ambiguity; never success."""
    return {
        "status": "uncertain",
        "success": False,
        "action_result": "uncertain",
        "effect_possible": True,
        "provider": "shopify",
        "operation": "create_fulfillment",
        "error_kind": error_kind,
        "error": message,
        "retryable": False,
        "remote_id": fulfillment_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_fulfillment",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": fulfillment_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": verification,
        "fulfillment": fulfillment,
        "evidence": [evidence] if evidence else [],
    }


def _fulfillment_applied(
    *,
    shop: str,
    operation_id: str,
    payload_sha256: str,
    fulfillment_id: str,
    fulfillment: Dict[str, Any],
    read_receipt: Dict[str, Any],
    dispatch_plan: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "status": "success",
        "success": True,
        "action_result": "applied",
        "provider": "shopify",
        "operation": "create_fulfillment",
        "remote_id": fulfillment_id,
        "payload_sha256": payload_sha256,
        "provider_receipt": {
            "provider": "shopify",
            "operation": "create_fulfillment",
            "operation_id": operation_id,
            "payload_sha256": payload_sha256,
            "remote_id": fulfillment_id,
            "shop": shop,
        },
        "read_receipt": read_receipt,
        "verification": {
            "status": "verified",
            "missing_fields": [],
            "mismatches": [],
        },
        "dispatch_plan": dispatch_plan,
        "fulfillment": fulfillment,
    }


async def create_fulfillment(
    token: str,
    shop: str,
    arguments: Mapping[str, Any] | None,
    *,
    operation_id: str = "",
) -> Dict[str, Any]:
    """Create one fulfillment, then bind exact id/order/dispatch readback."""
    from fastapi import HTTPException

    from integrations.shopify_service import (
        ShopifyFulfillmentDispatchError,
        ShopifyFulfillmentPreflightError,
        ShopifyService,
    )

    payload = fulfillment_payload(arguments)
    expected_material = accepted_fulfillment_material(arguments)
    digest = _payload_digest(payload)
    operation = str(operation_id or "")
    service = ShopifyService()
    meta: Dict[str, Any] = {}

    try:
        created = await service.create_fulfillment(
            token, shop,
            order_id=_text(payload.get("order_id")),
            location_id=payload.get("location_id"),
            tracking_number=payload.get("tracking_number"),
            tracking_company=payload.get("tracking_company"),
            notify_customer=payload.get("notify_customer"),
            meta_out=meta,
        )
    except ShopifyFulfillmentPreflightError as exc:
        return _fulfillment_failed_before_effect(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            error_kind=exc.error_kind,
            message=_text(exc.detail),
            evidence={
                "kind": "shopify_create_fulfillment_preflight_refused",
                "error_kind": exc.error_kind,
            },
        )
    except ShopifyFulfillmentDispatchError as exc:
        return _fulfillment_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            fulfillment_id="",
            fulfillment=None,
            error_kind=exc.error_kind,
            message=(
                "Shopify fulfillment creation did not return a confirmation; "
                f"the effect may have landed ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["transport_confirmation"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_fulfillment_transport_error",
                "error": f"{type(exc).__name__}: {str(exc.detail)[:300]}",
            },
        )
    except HTTPException as exc:
        # The service resolves fulfillment orders before it dispatches. A read
        # failure there is pre-effect, not an ambiguous write.
        return _fulfillment_failed_before_effect(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            error_kind="preflight_read_failed",
            message=(
                "Shopify could not resolve the order's fulfillment orders "
                f"before dispatch ({type(exc).__name__})"),
            evidence={
                "kind": "shopify_create_fulfillment_preflight_read_error",
                "error": f"{type(exc).__name__}: {str(exc.detail)[:300]}",
            },
        )
    except Exception as exc:  # noqa: BLE001 - provider may have applied it
        return _fulfillment_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            fulfillment_id="",
            fulfillment=None,
            error_kind="provider_error",
            message=(
                "Shopify fulfillment creation did not return a confirmation; "
                f"the effect may have landed ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["transport_confirmation"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_fulfillment_transport_error",
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    created = created if isinstance(created, dict) else {}
    fulfillment_id = str(created.get("id") or "").strip()
    if not fulfillment_id:
        return _fulfillment_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            fulfillment_id="",
            fulfillment=created or None,
            error_kind="unidentified_effect",
            message=(
                "Shopify accepted the fulfillment create request but returned "
                "no fulfillment id; the effect cannot be identified and is not "
                "safe to recreate"),
            verification={
                "status": "incomplete",
                "missing_fields": ["remote_id"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_fulfillment_missing_id",
                "returned_keys": sorted(created)[:20],
            },
        )

    dispatch_plan = fulfillment_dispatch_plan(
        meta.get("fulfillment_orders") or [],
        meta.get("location_id") or "",
    )
    try:
        observed = await service.get_fulfillment(
            token, shop, expected_material.get("order_id") or "",
            fulfillment_id)
    except Exception as exc:  # noqa: BLE001 - absent readback is not success
        return _fulfillment_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            fulfillment_id=fulfillment_id,
            fulfillment=created,
            error_kind="readback_unavailable",
            message=(
                "Shopify fulfillment was created but the exact resource could "
                f"not be read back ({type(exc).__name__})"),
            verification={
                "status": "incomplete",
                "missing_fields": ["readback"],
                "mismatches": [],
            },
            evidence={
                "kind": "shopify_create_fulfillment_readback_unavailable",
                "remote_id": fulfillment_id,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            },
        )

    observed = observed if isinstance(observed, dict) else {}
    unknown_association = False
    try:
        linked_fulfillment_order_ids = await authoritative_fulfillment_order_ids(
            service, token, shop,
            dispatch_plan.get("fulfillment_order_ids") or [],
            fulfillment_id)
    except Exception as exc:  # noqa: BLE001 - association is proof input
        linked_fulfillment_order_ids = []
        unknown_association = True
        association_error = f"{type(exc).__name__}: {str(exc)[:300]}"
    observed_material = observed_fulfillment_material(
        observed,
        fulfillment_order_ids=linked_fulfillment_order_ids,
    )
    observed_id = str(observed.get("id") or "").strip()
    mismatches = material_mismatches(
        expected_material, observed_material)
    mismatches.extend(fulfillment_plan_mismatches(
        dispatch_plan, observed_material))
    status_issue = fulfillment_status_issue(observed)
    if status_issue:
        mismatches.append("status")
    if observed_id != fulfillment_id:
        mismatches.append("remote_id")
    read_receipt = {
        "provider": "shopify",
        "operation": "get_fulfillment",
        "resource_id": observed_id,
        "requested_remote_id": fulfillment_id,
        "observed_remote_id": observed_id,
        "coverage": "single",
        "account_id": shop,
        "shop": shop,
        "parent_order_id": expected_material.get("order_id") or "",
        "fields": observed_material,
    }
    if mismatches:
        missing_fields = (
            ["fulfillment_order_association"] if unknown_association
            else ["status"] if status_issue and len(mismatches) == 1
            else [])
        evidence = {
            "kind": "shopify_create_fulfillment_readback_mismatch",
            "remote_id": fulfillment_id,
            "observed_remote_id": observed_id,
            "mismatches": mismatches,
        }
        if status_issue:
            evidence["status_issue"] = status_issue
        if unknown_association:
            evidence["association_error"] = association_error
        return _fulfillment_uncertain(
            shop=shop,
            operation_id=operation,
            payload_sha256=digest,
            fulfillment_id=fulfillment_id,
            fulfillment=observed or created,
            error_kind="readback_mismatch",
            message=(
                "The Shopify fulfillment readback did not match the "
                "authorized/dispatched material: " + ", ".join(mismatches)
                + (f" ({status_issue})" if status_issue else "")),
            verification={
                "status": "mismatch",
                "missing_fields": missing_fields,
                "mismatches": mismatches,
            },
            read_receipt=read_receipt,
            evidence=evidence,
        )

    return _fulfillment_applied(
        shop=shop,
        operation_id=operation,
        payload_sha256=digest,
        fulfillment_id=fulfillment_id,
        fulfillment=observed or created,
        read_receipt=read_receipt,
        dispatch_plan=dispatch_plan,
    )
