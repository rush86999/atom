from types import SimpleNamespace

def test_estimated_token_count_uses_real_utf8_upper_bound(monkeypatch):
 from core.llm import byok_handler,prompt_budget
 observed={}
 def estimate(model,prompt_tokens,completion_tokens):
  observed['prompt_tokens']=prompt_tokens
  return 1.0
 monkeypatch.setattr(byok_handler,'get_pricing_fetcher',lambda:SimpleNamespace(estimate_cost=estimate))
 # Existing count_tokens contract: True means estimated/heuristic, NOT exact.
 monkeypatch.setattr(prompt_budget,'count_tokens',lambda text:(1,True))
 h=object.__new__(byok_handler.BYOKHandler)
 text='é'*1000
 result=h._estimate_reservation_bound('controlled-paid','controlled-model',[text],10)
 assert result is not None
 assert observed['prompt_tokens']>=len(text.encode('utf-8')),observed
