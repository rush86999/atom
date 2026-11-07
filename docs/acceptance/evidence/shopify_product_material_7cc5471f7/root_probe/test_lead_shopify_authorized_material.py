"""Independent complete-request material controls; only provider HTTP doubled."""
import uuid
import pytest
from tests.test_oracle_shopify_product_replay import (
    env, FakeShopifyTransport, _add_store, _install_transport,
    _product_args, _context, _call, _agent,
)

@pytest.mark.parametrize('field', ['images','price','compare_at_price'])
@pytest.mark.parametrize('corrupt', [False,True])
def test_every_forwarded_business_field_must_match_readback(env, monkeypatch, field, corrupt):
    class Transport(FakeShopifyTransport):
        def _materialize(self, product, product_id):
            item=super()._materialize(product,product_id)
            if corrupt:
                if field=='images':item.pop('images',None)
                elif field=='price':item['variants'][0]['price']='1.00'
                else:item['variants'][0]['compare_at_price']='25.00'
            return item
    _add_store(env);transport=Transport();_install_transport(monkeypatch,transport)
    operation='lead-material-'+uuid.uuid4().hex
    overrides={'images':[{'src':'https://assets.example.invalid/authorized.png','alt':'Authorized photo'}]} if field=='images' else {'variants':[{'sku':'OPAQUE-SKU','price':'1.005' if field=='price' else '10.00','compare_at_price':'20.00'}]}
    result=_call(_agent(),_product_args(operation,**overrides),_context(operation))
    assert len(transport.posts)==1
    if corrupt:
        assert result.get('oracle_verified') is not True, result
        assert result.get('business_success') is not True, result
    else:
        assert result.get('oracle_verified') is True, result
