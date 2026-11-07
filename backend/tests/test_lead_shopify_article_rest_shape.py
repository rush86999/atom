"""Official REST readbacks expose published_at, not request-only published."""
import copy
import uuid
import pytest
from tests.test_oracle_shopify_article_create import (
    env, _add_store, FakeShopifyTransport, _install_transport,
    _call, _agent, _context, _article_args,
)

@pytest.mark.parametrize('published,observed_at', [(True, '2020-01-01T00:00:00Z'), (False, None)])
def test_official_rest_publication_readback_is_usable(env, monkeypatch, published, observed_at):
    monkeypatch.setenv('ATOM_ORACLE_ENFORCE', 'true')
    monkeypatch.setenv('ATOM_ORACLE_VERIFIER_ENABLED', 'true')
    _add_store(env)
    transport = FakeShopifyTransport()
    def rest_readback(blog_id, article_id, article):
        item = copy.deepcopy(article)
        item.pop('published', None)
        item['published_at'] = observed_at
        return item
    transport.read_override = rest_readback
    _install_transport(monkeypatch, transport)
    op = 'rest-shape-' + uuid.uuid4().hex
    result = _call(_agent(), _article_args(op, published=published), _context(op))
    assert len(transport.posts) == 1, result
    assert result.get('oracle_verified') is True, result
