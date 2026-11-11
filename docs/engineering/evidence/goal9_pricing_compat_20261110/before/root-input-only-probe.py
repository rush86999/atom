from core.dynamic_pricing_fetcher import DynamicPricingFetcher

def test_known_input_only_charge_is_not_lost_for_zero_output():
    fetcher=object.__new__(DynamicPricingFetcher)
    fetcher.get_model_price=lambda model:{'mode':'embedding','input_cost_per_token':0.01,'max_input_tokens':8192}
    assert fetcher.estimate_cost('controlled-input-only',100,0)==1.0
