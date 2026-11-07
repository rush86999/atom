"""Complete authorized-material controls for registered Shopify product create.

Failure-first provenance
------------------------
Root's independent registry/Generic/Oracle HTTP-leaf matrix (real registry,
real Generic mutation claim, real shared Oracle, only ``ShopifyService.http``
doubled) found three false-verified cases in the predecessor material
projection:

* requested ``images`` were omitted by the provider but still verified;
* an accepted variant ``price`` of ``1.005`` read back as ``1.00``;
* an accepted ``compare_at_price`` of ``20.00`` read back as ``25.00``.

The two latter fields were either absent from the material projection or
rounded by it.  These controls are intentionally written against the REAL
registered action/consumer/verifier; only the external HTTP leaf is doubled.
They also cover the same class of change across a durable same-operation
replay: no second create and an honest ``committed_unverified`` result.

Official provider contract used for the shape assumptions:

* Product resource (``images``/``variants`` arrays on create/readback):
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/product
* Product image resource (``src``/``alt`` and CDN-served URL):
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/product-image
* Product variant resource (``price``/``compare_at_price`` decimals):
  https://shopify.dev/docs/api/admin-rest/2026-07/resources/product-variant

The readback is treated as provider *identity* plus the literal material the
provider reports.  A rewritten/CDN URL is not assumed to be the same content:
without a content proof the verdict stays unverified, never fabricated.
"""
from __future__ import annotations

import uuid

import pytest

from tests.test_oracle_shopify_product_replay import (
    FakeShopifyTransport,
    _add_store,
    _agent,
    _call,
    _context,
    _install_transport,
    _product_args,
    env,  # noqa: F401 - imported pytest fixture
)


IMAGE_ARGS = {
    "images": [{
        "src": "https://assets.example.invalid/authorized.png",
        "alt": "Authorized photo",
    }],
}
VARIANT_ARGS = {
    "variants": [{
        "sku": "OPAQUE-SKU",
        "price": "1.005",
        "compare_at_price": "20.00",
    }],
}
FIELD_ARGS = {
    "images": IMAGE_ARGS,
    "price": VARIANT_ARGS,
    "compare_at_price": VARIANT_ARGS,
}


def _corrupt(field, item):
    if field == "images":
        item.pop("images", None)
    elif field == "price":
        item["variants"][0]["price"] = "1.00"
    else:
        item["variants"][0]["compare_at_price"] = "25.00"
    return item


class _FieldTransport(FakeShopifyTransport):
    def __init__(self, field, corrupt):
        super().__init__()
        self.field = field
        self.corrupt = corrupt

    def _materialize(self, product, product_id):
        item = super()._materialize(product, product_id)
        if self.corrupt:
            _corrupt(self.field, item)
        return item


@pytest.mark.parametrize("field", ["images", "price", "compare_at_price"])
def test_accepted_field_is_forwarded_and_exactly_verified(
        env, monkeypatch, field):
    _add_store(env)
    transport = _FieldTransport(field, corrupt=False)
    _install_transport(monkeypatch, transport)
    operation_id = f"op-material-positive-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _product_args(operation_id, **FIELD_ARGS[field]),
        _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is True, result
    assert result.get("success") is True, result
    posted = transport.posts[0]["json"]["product"]
    if field == "images":
        assert posted["images"] == IMAGE_ARGS["images"], posted
    else:
        assert posted["variants"][0]["price"] == "1.005", posted


@pytest.mark.parametrize("field", ["images", "price", "compare_at_price"])
def test_provider_omission_or_rounding_is_not_verified(
        env, monkeypatch, field):
    _add_store(env)
    transport = _FieldTransport(field, corrupt=True)
    _install_transport(monkeypatch, transport)
    operation_id = f"op-material-negative-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _product_args(operation_id, **FIELD_ARGS[field]),
        _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result


def test_image_source_rewrite_is_not_content_proof(env, monkeypatch):
    """A provider CDN rewrite is not byte/content proof; stay unverified."""
    _add_store(env)

    class _RewrittenSourceTransport(_FieldTransport):
        def _materialize(self, product, product_id):
            item = super()._materialize(product, product_id)
            item["images"][0]["src"] = (
                "https://cdn.shopify.com/rewritten/authorized.png")
            return item

    transport = _RewrittenSourceTransport("images", corrupt=False)
    _install_transport(monkeypatch, transport)
    operation_id = f"op-material-cdn-{uuid.uuid4().hex}"

    result = _call(
        _agent(), _product_args(operation_id, **IMAGE_ARGS),
        _context(operation_id))

    assert len(transport.posts) == 1, result
    assert result.get("oracle_verified") is not True, result
    assert result.get("business_success") is not True, result


@pytest.mark.parametrize("field", ["images", "price", "compare_at_price"])
@pytest.mark.parametrize("change", ["omit_or_round", "material"])
def test_replay_respects_complete_field_proof(
        env, monkeypatch, field, change):
    """A same-operation replay re-reads the exact resource and refuses a
    changed/omitted current field without a second create."""
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-material-replay-{field}-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id, **FIELD_ARGS[field])

    first = _call(_agent(), args, context)
    assert first.get("oracle_verified") is True, first
    assert len(transport.posts) == 1, first

    stored = transport.products["500"]
    if field == "images":
        if change == "omit_or_round":
            stored.pop("images", None)
        else:
            stored["images"][0]["alt"] = "Unapproved later alt"
    elif field == "price":
        stored["variants"][0]["price"] = (
            "1.00" if change == "omit_or_round" else "2.00")
    else:
        stored["variants"][0]["compare_at_price"] = (
            "25.00" if change == "omit_or_round" else "30.00")

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "a changed replay recreated the product"
    assert second.get("success") is not True, second
    assert second.get("status") == "committed_unverified", second
    assert second.get("action_result") == "already_applied_unverified", second
    assert second.get("oracle_verified") is False, second
    assert second.get("retryable") is False, second


@pytest.mark.parametrize("field", ["images", "price", "compare_at_price"])
def test_replay_of_complete_material_verifies_without_second_create(
        env, monkeypatch, field):
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    operation_id = f"op-material-replay-ok-{field}-{uuid.uuid4().hex}"
    context = _context(operation_id)
    args = _product_args(operation_id, **FIELD_ARGS[field])

    first = _call(_agent(), args, context)
    assert first.get("oracle_verified") is True, first
    assert len(transport.posts) == 1, first

    second = _call(_agent(), dict(args), dict(context))

    assert len(transport.posts) == 1, "the replay created a second product"
    assert second.get("oracle_verified") is True, second
    assert second.get("action_result") == "already_applied", second
    assert second.get("remote_id") == "500", second
