"""Authorized image-content receipt sub-contract, failure first.

Only the Shopify Admin HTTP leaf and the bounded asset HTTP leaf are doubled.
The real registered action, GenericAgent claim/Oracle path, product material
mapper, durable claim and replay remain in the path.
"""
from __future__ import annotations

import copy
import hashlib
import re
import uuid

import httpx
import pytest

from tests.test_oracle_shopify_product_replay import (
    FakeShopifyTransport,
    _add_store,
    _agent,
    _call,
    _context,
    _install_transport,
    _product_args,
    env,
)

SOURCE = "https://assets.example.invalid/authorized.png"
IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"authorized-image-content"
IMAGE_SHA = hashlib.sha256(IMAGE_BYTES).hexdigest()
CDN_HOST = "cdn.shopify.com"


EXPLICIT_IMAGE = {
    "src": SOURCE,
    "alt": "Authorized photo",
    "position": 1,
    "variant_ids": ["variant-1"],
    "content_sha256": IMAGE_SHA,
    "bytes": len(IMAGE_BYTES),
}

ASSET_RECEIPT = {
    "sha256": IMAGE_SHA,
    "bytes": len(IMAGE_BYTES),
    "read_receipt": {
        "provider": "zoho_workdrive",
        "operation": "download_file",
        "resource_id": "asset-file-1",
        "account_id": "ws-shop",
        "coverage": "complete",
        "access": "granted",
        "fields": {"sha256": IMAGE_SHA, "size": len(IMAGE_BYTES)},
        "evidence": [{"kind": "file", "id": "asset-file-1",
                      "sha256": IMAGE_SHA}],
    },
}

RECEIPT_IMAGE = {
    "src": SOURCE,
    "alt": "Receipt photo",
    "position": 1,
    "variant_ids": ["variant-1"],
    "asset_receipt": ASSET_RECEIPT,
}


class ImageReceiptTransport(FakeShopifyTransport):
    """Adds product-image by-id readback; Shopify HTTP only."""

    def __init__(self):
        super().__init__()
        self.images = {}
        self.image_gets = []
        self.image_bytes = IMAGE_BYTES

    def _materialize(self, product, product_id):
        item = super()._materialize(product, product_id)
        images = []
        for index, raw in enumerate(item.get("images") or []):
            image = copy.deepcopy(raw) if isinstance(raw, dict) else {"src": raw}
            for proof in ("content_sha256", "bytes", "asset_receipt"):
                image.pop(proof, None)
            image_id = f"img-{product_id}-{index}"
            image.update({
                "id": image_id,
                "product_id": product_id,
                "position": index + 1,
                "src": f"https://{CDN_HOST}/rewritten/{image_id}.png",
                "width": 320,
                "height": 180,
            })
            self.images[(product_id, image_id)] = image
            images.append(image)
        if images:
            item["images"] = images
        return item

    async def get(self, integration, url, headers=None, params=None):
        match = re.search(
            r"/products/([^/]+)/images/([^/.]+)\.json", url)
        if match:
            self.image_gets.append(url)
            product_id, image_id = match.group(1), match.group(2)
            image = self.images.get((product_id, image_id))
            if image is None:
                return self._response(404, url, payload={"errors": "not found"})
            return self._response(200, url, payload={"image": image})
        return await super().get(integration, url, headers=headers, params=params)


class AssetDouble:
    def __init__(self, *, verified=True, reason="", body=IMAGE_BYTES,
                 content_type="image/png"):
        self.verified = verified
        self.reason = reason
        self.body = body
        self.content_type = content_type
        self.calls = []

    async def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        digest = hashlib.sha256(self.body).hexdigest()
        verified = bool(self.verified)
        reason = self.reason
        expected = str(kwargs.get("expected_sha256") or "").lower()
        if verified and expected and digest != expected:
            verified = False
            reason = "content_mismatch_or_provider_transform"
        expected_bytes = kwargs.get("expected_bytes")
        if verified and expected_bytes is not None and len(self.body) != int(expected_bytes):
            verified = False
            reason = "byte_count_mismatch"
        fields = {"sha256": digest, "bytes": len(self.body),
                  "content_type": self.content_type, "url_host": CDN_HOST}
        return {
            "verified": verified,
            "reason": reason,
            "sha256": digest,
            "bytes": len(self.body),
            "content_type": self.content_type,
            "host": CDN_HOST,
            "read_receipt": {
                "provider": "shopify_cdn",
                "operation": "read_asset",
                "resource_id": kwargs.get("resource_id") or "",
                "account_id": kwargs.get("account_id") or "",
                "coverage": "single",
                "access": "granted",
                "fields": fields,
                "evidence": [{"kind": "asset_content", "sha256": digest,
                              "bytes": len(self.body), "host": CDN_HOST}],
            },
        }


def _install_asset(monkeypatch, asset):
    from core import shopify_mutations

    monkeypatch.setattr(
        shopify_mutations, "read_provider_asset", asset, raising=False)


def _image_args(operation_id, image=EXPLICIT_IMAGE):
    return _product_args(operation_id, images=[copy.deepcopy(image)])


def test_explicit_digest_verifies_cdn_rewritten_image(
        env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-explicit-{uuid.uuid4().hex}"

    result = _call(_agent(), _image_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is True, result
    assert result.get("success") is True, result
    posted = transport.posts[0]["json"]["product"]["images"][0]
    assert posted["src"] == SOURCE
    assert posted["alt"] == "Authorized photo"
    assert posted["position"] == 1
    assert posted["variant_ids"] == ["variant-1"]
    assert "content_sha256" not in posted
    assert "bytes" not in posted
    assert transport.image_gets, "no by-id image readback"
    assert asset.calls, "no provider CDN content read"
    proof = result["read_receipt"]["image_content"][0]
    assert proof["resource_id"] == "img-500-0"
    assert proof["product_id"] == "500"
    assert proof["account_id"] == "scratch-replay.myshopify.com"
    assert proof["fields"]["sha256"] == IMAGE_SHA
    assert proof["fields"]["bytes"] == len(IMAGE_BYTES)


def test_existing_asset_receipt_verifies_cdn_rewritten_image(
        env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-receipt-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _image_args(operation_id, RECEIPT_IMAGE),
        _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is True, result
    posted = transport.posts[0]["json"]["product"]["images"][0]
    assert "asset_receipt" not in posted
    assert posted["src"] == SOURCE
    assert posted["alt"] == "Receipt photo"
    assert posted["position"] == 1
    assert posted["variant_ids"] == ["variant-1"]


def test_raw_url_only_remains_open_and_unverified(env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-raw-{uuid.uuid4().hex}"

    raw = {"src": SOURCE, "alt": "Authorized photo", "position": 1}
    result = _call(
        _agent(), _image_args(operation_id, raw), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result
    assert not asset.calls


def test_wrong_digest_is_not_certified(env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble(verified=False, reason="content_mismatch")
    _install_asset(monkeypatch, asset)
    operation_id = f"img-wrong-{uuid.uuid4().hex}"

    result = _call(_agent(), _image_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result


def test_missing_by_id_image_is_not_certified(env, monkeypatch):
    _add_store(env)

    class _MissingImages(ImageReceiptTransport):
        def _materialize(self, product, product_id):
            item = super()._materialize(product, product_id)
            item["images"] = []
            return item

    transport = _MissingImages()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-missing-{uuid.uuid4().hex}"

    result = _call(_agent(), _image_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result
    assert not asset.calls

def test_exact_image_replay_without_second_create(env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-replay-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _image_args(operation_id)

    first = _call(_agent(), args, context)
    assert first.get("oracle_verified") is True, first
    assert len(transport.posts) == 1

    second = _call(_agent(), dict(args), dict(context))
    assert len(transport.posts) == 1, "image replay created a second product"
    assert second.get("oracle_verified") is True, second
    assert second.get("action_result") == "already_applied", second
    assert asset.calls, "replay did not re-read image content"


def _image_for(index):
    image = copy.deepcopy(EXPLICIT_IMAGE)
    image["position"] = index
    image["alt"] = f"Authorized photo {index}"
    image["src"] = f"{SOURCE}?image={index}"
    return image


def test_many_images_are_not_arbitrarily_capped(env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-many-{uuid.uuid4().hex}"
    images = [_image_for(index) for index in range(1, 7)]

    result = _call(
        _agent(), _product_args(operation_id, images=images),
        _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is True, result
    assert len(transport.posts[0]["json"]["product"]["images"]) == 6
    assert len(transport.image_gets) >= 6
    assert len(asset.calls) >= 6


def test_wrong_by_id_image_id_is_not_certified(env, monkeypatch):
    _add_store(env)

    class _WrongId(ImageReceiptTransport):
        async def get(self, integration, url, headers=None, params=None):
            response = await super().get(
                integration, url, headers=headers, params=params)
            if "/images/" in url and response.status_code == 200:
                payload = response.json()
                payload["image"]["id"] = "different-image"
                return self._response(200, url, payload=payload)
            return response

    transport = _WrongId()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-wrong-id-{uuid.uuid4().hex}"

    result = _call(_agent(), _image_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result


def test_wrong_by_id_product_id_is_not_certified(env, monkeypatch):
    _add_store(env)

    class _WrongProduct(ImageReceiptTransport):
        async def get(self, integration, url, headers=None, params=None):
            response = await super().get(
                integration, url, headers=headers, params=params)
            if "/images/" in url and response.status_code == 200:
                payload = response.json()
                payload["image"]["product_id"] = "different-product"
                return self._response(200, url, payload=payload)
            return response

    transport = _WrongProduct()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-wrong-product-{uuid.uuid4().hex}"

    result = _call(_agent(), _image_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result


def test_invalid_explicit_proof_fails_before_effect(env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-invalid-{uuid.uuid4().hex}"
    image = copy.deepcopy(EXPLICIT_IMAGE)
    image["content_sha256"] = "not-a-digest"

    result = _call(
        _agent(), _product_args(operation_id, images=[image]),
        _context(operation_id))

    assert result.get("status") == "failed_before_effect", result
    assert result.get("success") is not True, result
    assert len(transport.posts) == 0
    assert not asset.calls


def test_invalid_asset_receipt_fails_before_effect(env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-invalid-receipt-{uuid.uuid4().hex}"
    image = copy.deepcopy(RECEIPT_IMAGE)
    image["asset_receipt"] = {
        "sha256": IMAGE_SHA,
        "bytes": len(IMAGE_BYTES),
        "read_receipt": {
            "provider": "zoho_workdrive",
            "resource_id": "asset-file-1",
            "account_id": "ws-shop",
            "coverage": "complete",
            "access": "denied",
            "fields": {"sha256": IMAGE_SHA, "size": len(IMAGE_BYTES)},
            "evidence": [{"sha256": IMAGE_SHA}],
        },
    }

    result = _call(
        _agent(), _product_args(operation_id, images=[image]),
        _context(operation_id))

    assert result.get("status") == "failed_before_effect", result
    assert result.get("success") is not True, result
    assert len(transport.posts) == 0
    assert not asset.calls


def test_replay_provider_transform_stays_committed_unverified(
        env, monkeypatch):
    _add_store(env)
    transport = ImageReceiptTransport()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-replay-transform-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _image_args(operation_id)

    first = _call(_agent(), args, context)
    assert first.get("oracle_verified") is True, first
    assert len(transport.posts) == 1

    asset.body = b"provider-transformed-image-bytes"
    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a transformed replay recreated the product"
    assert second.get("success") is not True, second
    assert second.get("status") == "committed_unverified", second
    assert second.get("action_result") == "already_applied_unverified", second
    assert second.get("oracle_verified") is False, second
    assert second.get("retryable") is False, second


@pytest.mark.parametrize("field,value", [
    ("alt", "Unapproved alt"),
    ("position", 9),
    ("variant_ids", ["unapproved-variant"]),
])
def test_authorized_image_qualifier_mismatch_is_not_certified(
        env, monkeypatch, field, value):
    _add_store(env)

    class _ChangedQualifier(ImageReceiptTransport):
        def _materialize(self, product, product_id):
            item = super()._materialize(product, product_id)
            if item.get("images"):
                item["images"][0][field] = value
            return item

    transport = _ChangedQualifier()
    _install_transport(monkeypatch, transport)
    asset = AssetDouble()
    _install_asset(monkeypatch, asset)
    operation_id = f"img-qualifier-{field}-{uuid.uuid4().hex}"

    result = _call(_agent(), _image_args(operation_id), _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result
    assert f"images[0].{field}" in result["verification"]["mismatches"], result
