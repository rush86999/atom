"""Goal 9 regression: curated OpenCode free-candidate hard-stop admission.

Audit finding under test
========================

The shared OpenCode Zen catalog (``core.llm.opencode_catalog``) records a real,
provider-qualified free candidate — ``opencode-go/deepseek-v4.1-flash-free`` —
in :data:`OPCODE_KNOWN_FREE_MODELS`, while deliberately keeping it OUT of the
ranking price table (:data:`OPCODE_KNOWN_PRICES`). The free fact is therefore
present in the trusted provider catalog and absent from the pricing catalog.

``BYOKHandler._estimate_reservation_bound`` consults only the pricing catalog.
Under ``hard_stop`` an absent price is unknown (the documented "absence is never
free" contract), so the trusted free route is refused before dispatch even
though ``opencode-go`` is configured and the route catalog says it serves the
model. This regression pins the expected provider-qualified outcome:

* the curated ``(opencode-go, <curated-free-model>)`` route is admitted with an
  explicit zero reservation (the catalog's free fact is authoritative for THIS
  provider route — it is not inferred from an absent price);
* the same model name on another provider is still unknown and refuses;
* an uncurated ``-free`` suffix is still unknown and refuses;
* the OpenCode free→paid fallback keeps a SEPARATE paid reservation/attempt;
* a PRESENT but partial/invalid price row stays unknown: it is not the absent
  price that licenses the curated free fact, and a static ``MODEL_COSTS``
  fallback must not mask the malformed explicit material;
* a known-free attempt whose settlement resolves a conflicting positive cost
  keeps that real spend instead of rewriting it to ``$0``.

The controls matter: a fix keyed on the model name alone (or on the ``-free``
suffix) would make the other-provider/unknown-suffix controls pass at $0 too,
which is exactly the cross-provider mispricing this regression forbids.

Everything is doubled: a scratch SQLite ledger/route catalog and fake SDK
clients. No real provider, live DB, credential, network fetch or spend.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from core.dynamic_pricing_fetcher import DynamicPricingFetcher
from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
    _opencode_paid_fallback_model,
)
from core.llm.opencode_catalog import (
    OPCODE_KNOWN_FREE_MODELS,
    OPCODE_KNOWN_PRICES,
)
from tests.test_goal9_physical_attempts import (
    TENANT,
    WORKSPACE,
    _ChatClient,
    _attempt_rows,
    _make_handler,
    _response,
    _seed,
    host,
)
from tests.test_opencode_go_provider import _insufficient_balance_error

pytest_plugins = ("tests.test_goal9_physical_attempts",)

PROVIDER = "opencode-go"
OTHER_PROVIDER = "openrouter"
FREE_MODEL = "deepseek-v4.1-flash-free"
PAID_MODEL = "deepseek-v4.1-flash"
UNKNOWN_FREE_MODEL = "stealth-unlisted-model-free"


@pytest.fixture()
def scratch_pricing(monkeypatch):
    """Real estimate semantics over a scratch, curated-only price catalog.

    Only the real ``OPCODE_KNOWN_PRICES`` slice is seeded. The curated free
    candidate is deliberately absent, exactly as production
    ``fetch_opencode_pricing`` excludes free models from the ranking catalog.
    This is a scratch object: no disk cache, global mutation or live fetch.
    """
    fetcher = object.__new__(DynamicPricingFetcher)
    fetcher.pricing_cache = dict(fetcher._opencode_static_fallback())

    # The reproduction precondition: curated free, not priced, no explicit 0/0.
    assert FREE_MODEL in OPCODE_KNOWN_FREE_MODELS
    assert FREE_MODEL not in OPCODE_KNOWN_PRICES
    assert FREE_MODEL not in fetcher.pricing_cache
    assert fetcher.get_model_price(FREE_MODEL) is None

    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher", lambda: fetcher)
    return fetcher


def _handler(monkeypatch, tmp_path, provider_id, catalog, client):
    """Doubled handler: one fake provider client + explicit route catalog."""
    handler = _make_handler(
        monkeypatch, tmp_path, {provider_id: catalog},
        async_={provider_id: client})
    # Provider policy is a separate gate, not the subject of this regression.
    from core.llm.provider_policy import ProviderPolicy
    handler.provider_policy = ProviderPolicy(mode="unset")
    return handler


PRESENT_BUT_UNUSABLE_PRICES = [
    # Partial: output material is required for a positive output quantity.
    {"input_cost_per_token": 0.0},
    {"input_cost_per_token": 0.01},
    # Invalid: bools and a negative rate are not monetary material.
    {"input_cost_per_token": False, "output_cost_per_token": False},
    {"input_cost_per_token": -0.001, "output_cost_per_token": 0.001},
]


@pytest.mark.parametrize("material", PRESENT_BUT_UNUSABLE_PRICES)
def test_present_partial_or_invalid_price_is_not_curated_free(
        monkeypatch, tmp_path, scratch_pricing, material):
    """A present-but-unusable row stays unknown; it is not an absent price."""
    scratch_pricing.pricing_cache[FREE_MODEL] = dict(material)
    assert scratch_pricing.get_model_price(FREE_MODEL) == material

    handler = _handler(monkeypatch, tmp_path, PROVIDER, [FREE_MODEL], None)

    assert handler._estimate_reservation_bound(
        PROVIDER, FREE_MODEL, ["hello"], 1000) is None


def test_present_invalid_price_is_not_hidden_by_static_fallback(
        monkeypatch, tmp_path, scratch_pricing):
    """Malformed explicit material must not be masked by MODEL_COSTS."""
    from core.cost_config import get_llm_cost

    assert get_llm_cost("gpt-4o", 1000, 1000) is not None
    scratch_pricing.pricing_cache["gpt-4o"] = {
        "input_cost_per_token": 0.01,
    }

    handler = _handler(monkeypatch, tmp_path, "openai", ["gpt-4o"], None)

    assert handler._estimate_reservation_bound(
        "openai", "gpt-4o", ["hello"], 1000) is None


def test_known_free_settlement_preserves_conflicting_positive_cost(
        host, monkeypatch):
    """A positive settlement on a known-free attempt is real spend, not $0."""
    _seed(host, spend=90.0)

    class _PositivePricing:
        def estimate_cost(self, model, input_tokens, output_tokens):
            return 5.0

    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: _PositivePricing())
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT

    cost = handler._settle_physical_response(
        provider_id=PROVIDER,
        model=PAID_MODEL,
        response=_response("PAID OK"),
        request_id="conflicting-positive",
        attempt_id="conflicting-positive-attempt",
        known_free=True,
    )

    assert cost == 5.0
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].attempt_id == "conflicting-positive-attempt"
    assert float(rows[0].cost_usd) == 5.0


def _response_without_usage(content):
    """A successful paid reply whose usage is absent (unknown liability)."""
    response = _response(content)
    response.usage = None
    return response


def test_curated_opencode_free_candidate_admits_zero_under_hard_stop(
        host, monkeypatch, tmp_path, scratch_pricing):
    """The audit case: trusted free route must not be refused as unpriced."""
    _seed(host, spend=90.0)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, PROVIDER, [FREE_MODEL],
        _ChatClient([{"response": _response("FREE OK")}], calls))

    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}],
        FREE_MODEL, PROVIDER, max_tokens=1000))

    assert result["choices"][0]["message"]["content"] == "FREE OK"
    assert [call["model"] for call in calls] == [FREE_MODEL]

    rows = _attempt_rows(host)
    assert len(rows) == 1
    row = rows[0]
    assert row.provider_id == PROVIDER
    assert row.model_name == FREE_MODEL
    assert float(row.reserved_cost_usd or 0.0) == 0.0
    # Zero is the trusted free bound; it must not remain an open admission.
    assert row.reservation_status != "active"
    assert row.cost_usd is None or float(row.cost_usd) == 0.0


def test_same_free_model_name_on_other_provider_still_refuses(
        host, monkeypatch, tmp_path, scratch_pricing):
    """Trust is provider-qualified: the name alone buys nothing elsewhere."""
    _seed(host, spend=90.0)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, OTHER_PROVIDER, [FREE_MODEL],
        _ChatClient([{"response": _response("MUST NOT RUN")}], calls))

    with pytest.raises(AllProvidersFailedError) as excinfo:
        asyncio.run(handler.chat_completion(
            [{"role": "user", "content": "hello"}],
            FREE_MODEL, OTHER_PROVIDER, max_tokens=1000))

    assert "budget authorization is unavailable" in str(excinfo.value).lower()
    assert calls == []
    assert _attempt_rows(host) == []


def test_unknown_free_suffix_is_not_curated_trust(
        host, monkeypatch, tmp_path, scratch_pricing):
    """A ``-free`` suffix is not evidence of a curated free route."""
    _seed(host, spend=90.0)
    assert UNKNOWN_FREE_MODEL not in OPCODE_KNOWN_FREE_MODELS
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, PROVIDER, [UNKNOWN_FREE_MODEL],
        _ChatClient([{"response": _response("MUST NOT RUN")}], calls))

    with pytest.raises(AllProvidersFailedError) as excinfo:
        asyncio.run(handler.chat_completion(
            [{"role": "user", "content": "hello"}],
            UNKNOWN_FREE_MODEL, PROVIDER, max_tokens=1000))

    assert "budget authorization is unavailable" in str(excinfo.value).lower()
    assert calls == []
    assert _attempt_rows(host) == []


def test_paid_free_fallback_keeps_a_separate_paid_reservation(
        host, monkeypatch, tmp_path, scratch_pricing):
    """Free allowance exhausted -> paid sibling, with its own attempt/bound."""
    _seed(host, spend=90.0)
    assert _opencode_paid_fallback_model(FREE_MODEL) == PAID_MODEL
    assert PAID_MODEL in OPCODE_KNOWN_PRICES

    calls = []
    client = _ChatClient(
        [
            {"raise": _insufficient_balance_error()},
            # No usage: the paid reservation remains visible after settlement
            # as the documented explicit-unknown liability.
            {"response": _response_without_usage("PAID OK")},
        ],
        calls,
    )
    handler = _handler(
        monkeypatch, tmp_path, PROVIDER, [FREE_MODEL, PAID_MODEL], client)

    # The real healer has no rule for a credit-exhaustion error; keep this
    # control focused on admission/accounting rather than healer behavior.
    monkeypatch.setattr(
        "core.llm.routing.request_healer.get_request_healer",
        lambda: SimpleNamespace(
            heal=lambda *a, **k: SimpleNamespace(patched_kwargs=None)))

    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}],
        FREE_MODEL, PROVIDER, max_tokens=1000))

    assert result["model"] == PAID_MODEL
    assert [call["model"] for call in calls] == [FREE_MODEL, PAID_MODEL]

    rows = _attempt_rows(host)
    assert len(rows) == 2, [row.attempt_id for row in rows]
    free_row, paid_row = rows

    assert free_row.model_name == FREE_MODEL
    assert float(free_row.reserved_cost_usd or 0.0) == 0.0

    assert paid_row.model_name == PAID_MODEL
    assert paid_row.attempt_id != free_row.attempt_id
    assert float(paid_row.reserved_cost_usd or 0.0) > 0.0
    assert paid_row.reservation_status == "uncertain"
