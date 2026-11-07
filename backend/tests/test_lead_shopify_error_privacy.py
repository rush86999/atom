"""Independent provider error material must not escape the real consumer."""
import json
import uuid
from tests.test_oracle_shopify_blog_create import (
    env, _add_store, FakeShopifyTransport, _install_transport,
    _call, _agent, _context, _blog_args,
)


def test_provider_exception_material_is_not_returned(env, monkeypatch):
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    _add_store(env)
    marker = 'private-provider-material-' + uuid.uuid4().hex
    transport = FakeShopifyTransport()
    transport.post_raises_after_create = RuntimeError(marker)
    _install_transport(monkeypatch, transport)
    operation = 'privacy-' + uuid.uuid4().hex
    result = _call(_agent(), _blog_args(operation), _context(operation))
    assert len(transport.posts) == 1, result
    assert result['success'] is not True
    assert marker not in json.dumps(result, default=str), 'raw provider exception escaped'
