"""Tests for curated model overrides in the LLM registry.

Phase 0 acceptance:
    1. ``openrouter/owl-alpha`` is present after ``fetch_openrouter_models()``
       even when the (mocked) upstream payload omits it.
    2. On ``model_id`` collision, the curated entry does NOT override the upstream one.
    3. ``apply_curated_overrides`` is non-destructive (does not mutate upstream).
    4. ``apply_curated_overrides`` tolerates non-dict input defensively.
    5. The dynamic_pricing_fetcher path (which backs ``GET /api/llm/models``)
       also surfaces the curated entry via ``apply_curated_overrides_to_pricing``.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.llm.registry.curated_overrides import (
    CURATED_OVERRIDES,
    apply_curated_overrides,
    apply_curated_overrides_to_pricing,
    curated_overrides_in_pricing_shape,
)
from core.llm.registry.fetchers import ModelMetadataFetcher


# --------------------------------------------------------------------------- #
# apply_curated_overrides (pure function, no I/O)
# --------------------------------------------------------------------------- #
def test_apply_curated_overrides_adds_missing_model():
    """Curated entries are added when absent from upstream."""
    upstream = {"openai/gpt-4": {"id": "openai/gpt-4", "name": "GPT-4"}}

    result = apply_curated_overrides(upstream)

    assert "openrouter/owl-alpha" in result
    assert result["openrouter/owl-alpha"]["id"] == "openrouter/owl-alpha"
    # Existing entry preserved
    assert "openai/gpt-4" in result
    assert len(result) == 2


def test_apply_curated_overrides_does_not_override_on_collision():
    """On model_id collision, the curated payload does NOT replace the upstream one."""
    upstream = {
        "openrouter/owl-alpha": {
            "id": "openrouter/owl-alpha",
            "name": "UPSTREAM NAME",
            "curated": False,
        }
    }

    result = apply_curated_overrides(upstream)

    payload = result["openrouter/owl-alpha"]
    assert payload["name"] == "UPSTREAM NAME"
    assert payload["curated"] is False


def test_apply_curated_overrides_is_non_destructive():
    """The caller's upstream dict must not be mutated."""
    upstream = {"openai/gpt-4": {"id": "openai/gpt-4"}}
    snapshot_before = dict(upstream)

    apply_curated_overrides(upstream)

    assert upstream == snapshot_before, "upstream dict was mutated"


def test_apply_curated_overrides_handles_non_dict_input():
    """Defensive: malformed upstream should not raise."""
    result_from_none = apply_curated_overrides(None)  # type: ignore[arg-type]
    assert "openrouter/owl-alpha" in result_from_none

    result_from_list = apply_curated_overrides([])  # type: ignore[arg-type]
    assert "openrouter/owl-alpha" in result_from_list


# --------------------------------------------------------------------------- #
# fetch_openrouter_models (async, upstream mocked)
# --------------------------------------------------------------------------- #
async def _mock_fetch_openrouter(fetcher, fake_payload):
    """Shared helper: drive fetch_openrouter_models against a mocked upstream.

    Patches the async ``_get_client`` to resolve to a fake client that returns
    a fake response, so we exercise the real fetcher body (including the
    curated-override merge) without hitting the network.
    """
    # Build a plain (non-MagicMock) fake response so .json() returns the dict
    # directly — AsyncMock would turn .json() into a coroutine.
    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    fake_response = _FakeResponse(fake_payload)

    class _FakeClient:
        async def get(self, *args, **kwargs):
            return fake_response

        async def aclose(self):
            pass

    fake_client = _FakeClient()

    async def _fake_get_client():
        return fake_client

    with patch.object(fetcher, "_get_client", side_effect=_fake_get_client):
        return await fetcher.fetch_openrouter_models()


@pytest.mark.asyncio
async def test_fetch_openrouter_models_includes_curated_when_upstream_omits_it():
    """Acceptance #1: owl-alpha is present even when upstream omits it."""
    fetcher = ModelMetadataFetcher(use_retry=False)

    # Upstream payload has other models but NOT owl-alpha
    fake_payload = {
        "data": [
            {"id": "openai/gpt-4", "name": "GPT-4"},
            {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus"},
        ]
    }

    result = await _mock_fetch_openrouter(fetcher, fake_payload)

    assert "openrouter/owl-alpha" in result, "curated override missing from result"
    assert result["openrouter/owl-alpha"]["curated"] is True
    # Upstream models preserved
    assert "openai/gpt-4" in result
    assert "anthropic/claude-3-opus" in result
    # owl-alpha was added, not substituted for an existing entry
    assert len(result) == 3


@pytest.mark.asyncio
async def test_fetch_openrouter_models_does_not_override_on_collision():
    """Acceptance #2: does NOT override on model_id collision."""
    fetcher = ModelMetadataFetcher(use_retry=False)

    fake_payload = {
        "data": [
            {
                "id": "openrouter/owl-alpha",
                "name": "UPSTREAM OWL",
                "pricing": {"prompt": "9.9", "completion": "9.9"},
            }
        ]
    }

    result = await _mock_fetch_openrouter(fetcher, fake_payload)

    payload = result["openrouter/owl-alpha"]
    assert payload["name"] == "UPSTREAM OWL"
    assert payload.get("curated") is None
    assert payload["pricing"]["prompt"] == "9.9"


@pytest.mark.asyncio
async def test_fetch_openrouter_models_empty_upstream_still_empty_after_override_path():
    """If upstream returns no models, we should NOT silently inject curated-only.

    Rationale: silently returning curated-only on a malformed/empty response
    would mask a registry outage. The error path returns {} before the override
    merge runs. (Phase 0 design decision: overrides only apply on the success
    path, not the error path.)
    """
    fetcher = ModelMetadataFetcher(use_retry=False)

    # Missing 'data' field -> error path -> returns {} BEFORE override merge
    fake_payload = {"unexpected": "shape"}

    result = await _mock_fetch_openrouter(fetcher, fake_payload)

    assert result == {}, "error path should not silently inject curated-only models"


# --------------------------------------------------------------------------- #
# Pricing-shape overrides (dynamic_pricing_fetcher / GET /api/llm/models path)
# --------------------------------------------------------------------------- #
def test_curated_overrides_in_pricing_shape_has_expected_keys():
    """Pricing-shape conversion produces the schema dynamic_pricing_fetcher expects."""
    priced = curated_overrides_in_pricing_shape()

    assert "openrouter/owl-alpha" in priced
    payload = priced["openrouter/owl-alpha"]
    # Required keys for the pricing cache shape
    for key in (
        "input_cost_per_token",
        "output_cost_per_token",
        "max_tokens",
        "name",
        "description",
        "source",
        "litellm_provider",
    ):
        assert key in payload, f"missing key {key!r}"
    # Types
    assert isinstance(payload["input_cost_per_token"], float)
    assert isinstance(payload["output_cost_per_token"], float)
    assert isinstance(payload["max_tokens"], int)
    assert payload["source"] == "openrouter"
    assert payload["curated"] is True


def test_apply_curated_overrides_to_pricing_adds_curated_model():
    """Pricing-shape merge: curated model added when absent upstream."""
    upstream = {
        "openai/gpt-4": {
            "input_cost_per_token": 0.00003,
            "output_cost_per_token": 0.00006,
            "max_tokens": 8192,
            "name": "GPT-4",
            "source": "openrouter",
            "litellm_provider": "openai",
        }
    }

    result = apply_curated_overrides_to_pricing(upstream)

    assert "openrouter/owl-alpha" in result
    assert "openai/gpt-4" in result
    assert len(result) == 2
    assert result["openrouter/owl-alpha"]["curated"] is True


def test_apply_curated_overrides_to_pricing_does_not_override_on_collision():
    """Pricing-shape merge: curated entry does NOT override on collision."""
    upstream = {
        "openrouter/owl-alpha": {
            "input_cost_per_token": 9.9,
            "output_cost_per_token": 9.9,
            "max_tokens": 1,
            "name": "UPSTREAM",
            "source": "openrouter",
            "litellm_provider": "openrouter",
        }
    }

    result = apply_curated_overrides_to_pricing(upstream)

    payload = result["openrouter/owl-alpha"]
    assert payload["name"] == "UPSTREAM"
    assert payload["input_cost_per_token"] == 9.9


def test_apply_curated_overrides_to_pricing_handles_non_dict():
    """Defensive: malformed input returns curated-only rather than raising."""
    result = apply_curated_overrides_to_pricing(None)  # type: ignore[arg-type]
    assert "openrouter/owl-alpha" in result
    assert result["openrouter/owl-alpha"]["curated"] is True
