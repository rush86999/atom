import pytest
from types import SimpleNamespace

@pytest.mark.parametrize('price',[-1.0,float('nan'),float('inf'),False,True])
def test_invalid_price_cannot_become_free_reservation(monkeypatch,price):
 from core.llm import byok_handler
 monkeypatch.setattr(byok_handler,'get_pricing_fetcher',lambda:SimpleNamespace(estimate_cost=lambda *a,**k:price))
 handler=object.__new__(byok_handler.BYOKHandler)
 result=handler._estimate_reservation_bound('controlled-paid','controlled-model',['A'],10)
 assert result is None, 'Invalid configured pricing must remain unknown, never zero/free or an infinite admitted bound'
