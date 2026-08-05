"""
Tests for dynamic pricing model matching (core/dynamic_pricing_fetcher.py).

get_model_price used a bidirectional substring match that returned the FIRST
dict-insertion-order hit, not the correct model. Querying "gpt-4" could return
gpt-4o's price (6x cheaper) if gpt-4o was inserted first — silently corrupting
cost attribution and context-window sizing.
"""

import pytest
from core.dynamic_pricing_fetcher import DynamicPricingFetcher


@pytest.fixture
def fetcher():
    """Build a fetcher with a controlled pricing cache (no network)."""
    f = DynamicPricingFetcher.__new__(DynamicPricingFetcher)
    f.pricing_cache = {
        "gpt-4o": {"input_cost_per_token": 0.000005, "output_cost_per_token": 0.000015},
        "gpt-4": {"input_cost_per_token": 0.00003, "output_cost_per_token": 0.00006},
        "gpt-4-turbo": {"input_cost_per_token": 0.00001, "output_cost_per_token": 0.00003},
        "gpt-4-32k": {"input_cost_per_token": 0.00006, "output_cost_per_token": 0.00012},
    }
    return f


class TestGetModelPrice:
    def test_exact_match_returns_correct_price(self, fetcher):
        """An exact model name must return its own price."""
        price = fetcher.get_model_price("gpt-4")
        assert price["input_cost_per_token"] == 0.00003

    def test_no_false_match_on_prefix_collision(self, fetcher):
        """Querying "gpt-4" must NOT return gpt-4o's price (6x cheaper).

        The old substring match returned the first cached key containing "gpt-4",
        which was gpt-4o (inserted first) — corrupting cost estimates."""
        price = fetcher.get_model_price("gpt-4")
        assert price is not None
        assert price["input_cost_per_token"] != 0.000005, (
            "get_model_price('gpt-4') returned gpt-4o's price via substring match"
        )

    def test_unknown_model_returns_none(self, fetcher):
        assert fetcher.get_model_price("nonexistent-model-xyz") is None

    def test_non_exact_match_does_not_cross_contaminate(self, fetcher):
        """A model variant NOT in the cache must not silently inherit another
        model's price via a loose substring match. The old bidirectional
        substring match returned the first key containing the query — e.g.
        querying a model variant returns a different variant's price."""
        # "gpt-4-mini" is NOT a cached key. The old match would return the
        # first key containing "gpt-4" (gpt-4o) — wrong price. With exact-only
        # matching, it should return None (unknown model).
        price = fetcher.get_model_price("gpt-4-mini")
        assert price is None, (
            f"Unknown model 'gpt-4-mini' matched a cached key via substring — "
            f"this returns the wrong model's price for cost attribution."
        )


class TestInferProvider:
    def test_llama_not_auto_classified_as_groq(self, fetcher):
        """A Llama model NOT from Groq must not be classified as 'groq'."""
        provider = fetcher._infer_provider("meta-llama/llama-3.1-70b-instruct")
        assert provider != "groq", (
            "Non-Groq Llama model was classified as 'groq' — the condition "
            "matched Llama models WITHOUT 'groq' in the name and returned 'groq'."
        )
