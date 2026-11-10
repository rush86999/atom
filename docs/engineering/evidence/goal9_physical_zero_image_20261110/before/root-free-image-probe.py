import asyncio
from tests.test_goal9_physical_attempts import host, _clean_transport_state, _seed, _pricing, _make_handler, _ChatClient, _response, _IMAGE_MESSAGES, _attempt_rows

def test_authoritative_zero_price_image_retains_free_route(host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _pricing(monkeypatch, lambda *args, **kwargs: 0.0)
    calls=[]
    handler=_make_handler(monkeypatch,tmp_path,{"openai":["gpt-4o"]},async_={"openai":_ChatClient([{"response":_response("FREE IMAGE")}],calls)})
    result=asyncio.run(handler.chat_completion(_IMAGE_MESSAGES,"gpt-4o","openai",max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "FREE IMAGE"
    assert len(calls)==1
    rows=_attempt_rows(host)
    assert len(rows)==1
    assert rows[0].pricing_status=="free"
    assert float(rows[0].reserved_cost_usd)==0.0
