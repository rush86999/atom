"""Fulfilled quantity is not remaining/fulfillable quantity; use real REST shapes."""
import copy
import uuid
from tests.test_oracle_shopify_fulfillment_create import (
    env, _add_store, FakeShopifyTransport, _install_transport,
    _call, _agent, _context, _fulfillment_args,
)


def _oracle(monkeypatch):
    monkeypatch.setenv('ATOM_ORACLE_ENFORCE', 'true')
    monkeypatch.setenv('ATOM_ORACLE_VERIFIER_ENABLED', 'true')


def test_official_fulfillment_rest_shape_is_usable(env, monkeypatch):
    _oracle(monkeypatch)
    _add_store(env)
    class OfficialTransport(FakeShopifyTransport):
        def _materialize(self, payload):
            item = super()._materialize(payload)
            item.pop('fulfillment_orders', None)
            for line in item['line_items']:
                line.pop('fulfillment_order_id', None)
                line['fulfillable_quantity'] = 0
            return item
    transport = OfficialTransport()
    _install_transport(monkeypatch, transport)
    op = 'official-fulfillment-' + uuid.uuid4().hex
    result = _call(_agent(), _fulfillment_args(op, notify_customer=False), _context(op))
    assert len(transport.posts) == 1, result
    assert result.get('oracle_verified') is True, result


def test_wrong_fulfilled_quantity_cannot_borrow_remaining_quantity(env, monkeypatch):
    _oracle(monkeypatch)
    _add_store(env)
    transport = FakeShopifyTransport()
    def wrong_quantity(fulfillment_id, item):
        item = copy.deepcopy(item)
        for line in item['line_items']:
            line['fulfillable_quantity'] = line['quantity']
            line['quantity'] = 0
        return item
    transport.read_override = wrong_quantity
    _install_transport(monkeypatch, transport)
    op = 'wrong-fulfilled-quantity-' + uuid.uuid4().hex
    result = _call(_agent(), _fulfillment_args(op, notify_customer=False), _context(op))
    assert len(transport.posts) == 1, result
    assert result.get('oracle_verified') is not True, result


def test_contradictory_fulfillment_order_parent_refuses_before_post(env, monkeypatch):
    _oracle(monkeypatch)
    _add_store(env)
    transport = FakeShopifyTransport()
    transport.fulfillment_orders[0]['order_id'] = 'foreign-order'
    _install_transport(monkeypatch, transport)
    op = 'wrong-fulfillment-parent-' + uuid.uuid4().hex
    result = _call(_agent(), _fulfillment_args(op, notify_customer=False), _context(op))
    assert len(transport.posts) == 0, 'contradictory source parent was dispatched'
    assert result.get('success') is not True, result


def test_failed_fulfillment_status_is_not_verified(env, monkeypatch):
    _oracle(monkeypatch)
    _add_store(env)
    transport = FakeShopifyTransport()
    def failed_status(identity, item):
        item = copy.deepcopy(item)
        item['status'] = 'failure'
        return item
    transport.read_override = failed_status
    _install_transport(monkeypatch, transport)
    op = 'failed-fulfillment-' + uuid.uuid4().hex
    result = _call(_agent(), _fulfillment_args(op, notify_customer=False), _context(op))
    assert len(transport.posts) == 1, result
    assert result.get('oracle_verified') is not True, result


def test_fulfillment_read_uses_documented_parent_order_endpoint(env, monkeypatch):
    _oracle(monkeypatch)
    _add_store(env)
    transport = FakeShopifyTransport()
    _install_transport(monkeypatch, transport)
    op = 'endpoint-fulfillment-' + uuid.uuid4().hex
    _call(_agent(), _fulfillment_args(op, notify_customer=False), _context(op))
    reads = [url for url in transport.gets if '/fulfillments/' in url]
    assert reads and all('/orders/' in url for url in reads), reads
