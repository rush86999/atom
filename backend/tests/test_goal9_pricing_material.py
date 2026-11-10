"""Configured price MATERIAL contract (Goal 9 correct-price gate).

Root's frozen-973 counterprobe showed the real
``DynamicPricingFetcher.estimate_cost`` returning an authoritative-looking
``0`` for FOUR invalid materials, because rates were read with
``pricing.get(rate, 0)`` and arithmetic could cancel a negative input rate
against a positive output rate:

- both rates missing;
- one rate missing;
- ``False``/``False`` (bools are numerically 0);
- negative input + positive output summing to 0.

All four must be **unknown** (`None`), never known free. Genuine explicit
``0/0`` stays free and a positive pair still prices. Fetch normalization must
not fill a missing rate with 0 either.

The real fetcher is used (only its cache/configured lookup is controlled); no
live pricing fetch, provider call, credential or spend.
"""
from __future__ import annotations

import asyncio

import pytest

from tests.test_goal9_physical_attempts import (
    _IMAGE_MESSAGES,
    _ChatClient,
    _attempt_rows,
    _make_handler,
    _response,
    _seed,
    host,
)
from core.dynamic_pricing_fetcher import DynamicPricingFetcher

pytest_plugins = ("tests.test_goal9_physical_attempts",)

INVALID_MATERIAL = [
    {"name": "controlled-unknown"},
    {"name": "controlled-partial", "input_cost_per_token": 0.0},
    {"input_cost_per_token": False, "output_cost_per_token": False},
    {"input_cost_per_token": -0.001, "output_cost_per_token": 0.001},
]


def _bare_fetcher(pricing):
    fetcher = object.__new__(DynamicPricingFetcher)
    fetcher.get_model_price = lambda model: pricing
    return fetcher


@pytest.mark.parametrize("price", INVALID_MATERIAL)
def test_invalid_or_absent_rate_material_is_not_known_free(price):
    assert _bare_fetcher(price).estimate_cost(
        "controlled-no-static-alias", 100, 100) is None


@pytest.mark.parametrize("rates,expected", [
    ({"input_cost_per_token": 0.0, "output_cost_per_token": 0.0}, 0.0),
    ({"input_cost_per_token": 0.01, "output_cost_per_token": 0.02}, 3.0),
])
def test_explicit_free_and_priced_rates_remain_supported(rates, expected):
    assert _bare_fetcher(rates).estimate_cost(
        "controlled-no-static-alias", 100, 100) == expected


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload, **kwargs):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *args, **kwargs):
        return _FakeResponse(self._payload)


def test_litellm_normalization_skips_incomplete_rates(monkeypatch):
    import core.dynamic_pricing_fetcher as dpf

    payload = {
        "good-free": {"input_cost_per_token": 0.0,
                      "output_cost_per_token": 0.0},
        "good-paid": {"input_cost_per_token": 0.01,
                      "output_cost_per_token": 0.02},
        "missing-both": {},
        "missing-output": {"input_cost_per_token": 0.01},
        "bool-rates": {"input_cost_per_token": False,
                       "output_cost_per_token": False},
    }
    monkeypatch.setattr(dpf.httpx, "AsyncClient",
                        lambda **kw: _FakeAsyncClient(payload, **kw))
    fetcher = object.__new__(DynamicPricingFetcher)
    result = asyncio.run(fetcher.fetch_litellm_pricing())
    assert set(result) >= {"good-free", "good-paid"}
    assert not ({"missing-both", "missing-output", "bool-rates"} & set(result))
    assert result["good-free"]["input_cost_per_token"] == 0.0


def test_openrouter_normalization_skips_incomplete_rates(monkeypatch):
    import core.dynamic_pricing_fetcher as dpf

    payload = {"data": [
        {"id": "good-free", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "good-paid", "pricing": {"prompt": "0.01", "completion": "0.02"}},
        {"id": "missing-completion", "pricing": {"prompt": "0.01"}},
        {"id": "negative", "pricing": {"prompt": "-0.01", "completion": "0.02"}},
    ]}
    monkeypatch.setattr(dpf.httpx, "AsyncClient",
                        lambda **kw: _FakeAsyncClient(payload, **kw))
    fetcher = object.__new__(DynamicPricingFetcher)
    result = asyncio.run(fetcher.fetch_openrouter_pricing())
    assert "good-free" in result and "good-paid" in result
    assert "missing-completion" not in result
    assert "negative" not in result


def _seed_real_pricing(monkeypatch, entries):
    from core.dynamic_pricing_fetcher import get_pricing_fetcher

    fetcher = get_pricing_fetcher()
    saved = dict(fetcher.pricing_cache)
    fetcher.pricing_cache.update(entries)

    def _restore():
        fetcher.pricing_cache.clear()
        fetcher.pricing_cache.update(saved)

    return _restore


def test_missing_rate_material_hardstop_refuses_before_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    restore = _seed_real_pricing(monkeypatch, {
        "controlled-unknown-model": {"name": "controlled-unknown-model"},
    })
    try:
        calls = []
        handler = _make_handler(
            monkeypatch, tmp_path, {"openai": ["controlled-unknown-model"]},
            async_={"openai": _ChatClient(
                [{"response": _response("MUST NOT RUN")}], calls)})
        with pytest.raises(Exception):
            asyncio.run(handler.chat_completion(
                [{"role": "user", "content": "hello"}],
                "controlled-unknown-model", "openai", max_tokens=1000))
        assert calls == []
        assert _attempt_rows(host) == []
    finally:
        restore()


def test_genuine_zero_rate_image_remains_free(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    restore = _seed_real_pricing(monkeypatch, {
        "controlled-free-image-model": {
            "name": "controlled-free-image-model",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        },
    })
    try:
        calls = []
        handler = _make_handler(
            monkeypatch, tmp_path,
            {"openai": ["controlled-free-image-model"]},
            async_={"openai": _ChatClient(
                [{"response": _response("FREE IMAGE")}], calls)})
        result = asyncio.run(handler.chat_completion(
            _IMAGE_MESSAGES, "controlled-free-image-model", "openai",
            max_tokens=1000))
        assert result["choices"][0]["message"]["content"] == "FREE IMAGE"
        rows = _attempt_rows(host)
        assert len(rows) == 1
        assert rows[0].pricing_status == "free"
        assert rows[0].reservation_status == "settled"
        assert float(rows[0].reserved_cost_usd or 0.0) == 0.0
    finally:
        restore()
