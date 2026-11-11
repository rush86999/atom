import pytest
from core.dynamic_pricing_fetcher import DynamicPricingFetcher

@pytest.mark.parametrize('price',[
    {'name':'controlled-unknown'},
    {'name':'controlled-partial','input_cost_per_token':0.0},
    {'input_cost_per_token':False,'output_cost_per_token':False},
    {'input_cost_per_token':-0.001,'output_cost_per_token':0.001},
])
def test_invalid_or_absent_rate_material_is_not_known_free(price):
    fetcher=object.__new__(DynamicPricingFetcher)
    fetcher.get_model_price=lambda model:price
    result=fetcher.estimate_cost('controlled-no-static-alias',100,100)
    assert result is None, f'Invalid or missing rates must remain unknown, got {result!r}'

@pytest.mark.parametrize('rates,expected',[
    ({'input_cost_per_token':0.0,'output_cost_per_token':0.0},0.0),
    ({'input_cost_per_token':0.01,'output_cost_per_token':0.02},3.0),
])
def test_explicit_free_and_priced_rates_remain_supported(rates,expected):
    fetcher=object.__new__(DynamicPricingFetcher)
    fetcher.get_model_price=lambda model:rates
    assert fetcher.estimate_cost('controlled-no-static-alias',100,100)==expected
