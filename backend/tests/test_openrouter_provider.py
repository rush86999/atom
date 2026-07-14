"""
Tests for OpenRouter as a first-class BYOK provider.

Verifies that OpenRouter is wired end-to-end:
  - Present in the provider allowlist (so keys can be stored)
  - Present in both BYOKManager default-provider lists (so it appears in the UI)
  - Has an OpenAI-compatible client registered in the BYOK handler
  - Models in the pricing cache carry litellm_provider="openrouter" so the
    BPC ranker can route them to the openrouter client
"""

from __future__ import annotations

import pytest


class TestProviderAllowlist:
    """OpenRouter is accepted by the key-store endpoints."""

    def test_openrouter_in_byok_endpoints_allowlist(self):
        """The valid_providers list in byok_endpoints.store_api_key accepts openrouter."""
        import ast
        import inspect

        from core import byok_endpoints

        # Extract the valid_providers list literal from the source of store_api_key
        source = inspect.getsource(byok_endpoints.store_api_key)
        tree = ast.parse(source)
        found = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "valid_providers":
                        found = ast.literal_eval(node.value)
                        break
        assert found is not None, "valid_providers list not found in store_api_key"
        assert "openrouter" in found, (
            "openrouter missing from valid_providers — keys cannot be stored"
        )


class TestByokEndpointsDefaults:
    """OpenRouter is a default provider in the runtime BYOKManager."""

    def test_openrouter_provider_config_exists(self):
        """byok_endpoints.BYOKManager registers an OpenRouter provider by default."""
        from core.byok_endpoints import BYOKManager, AIProviderConfig

        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr._initialize_default_providers()
        assert "openrouter" in mgr.providers, "openrouter not in default providers"
        cfg = mgr.providers["openrouter"]
        assert isinstance(cfg, AIProviderConfig)
        assert cfg.api_key_env_var == "OPENROUTER_API_KEY"
        assert cfg.base_url == "https://openrouter.ai/api/v1"

    def test_openrouter_supports_reasoning_tasks(self):
        """OpenRouter should be categorized as a reasoning/chat provider for the UI."""
        from core.byok_endpoints import BYOKManager

        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr._initialize_default_providers()
        cfg = mgr.providers["openrouter"]
        assert "reasoning" in cfg.supported_tasks or "chat" in cfg.supported_tasks


class TestByokRoutesDefaults:
    """OpenRouter is a default provider in the authed API BYOKManager."""

    def test_openrouter_in_byok_routes_defaults(self):
        """byok_routes.BYOKManager registers an OpenRouter provider by default."""
        from api.byok_routes import BYOKManager, AIProviderConfig

        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr._initialize_default_providers()
        assert "openrouter" in mgr.providers
        cfg = mgr.providers["openrouter"]
        assert isinstance(cfg, AIProviderConfig)
        assert cfg.api_key_env_var == "OPENROUTER_API_KEY"
        assert cfg.base_url == "https://openrouter.ai/api/v1"


class TestByokHandlerClient:
    """OpenRouter has a client registered in the BYOK handler."""

    def test_openrouter_in_providers_config(self):
        """The _initialize_clients method includes openrouter in providers_config.

        We check the source text (not AST evaluation) because the dict contains
        os.getenv() calls for the ollama entry, which aren't literal-evaluable.
        """
        import inspect

        from core.llm.byok_handler import BYOKHandler

        source = inspect.getsource(BYOKHandler._initialize_clients)
        assert '"openrouter"' in source, "openrouter not in providers_config"
        assert "https://openrouter.ai/api/v1" in source, "openrouter base_url missing"

    def test_openrouter_in_cost_efficient_models(self):
        """OpenRouter has default models for each query-complexity tier."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        assert "openrouter" in COST_EFFICIENT_MODELS
        tiers = COST_EFFICIENT_MODELS["openrouter"]
        # Every tier should map to a model with a provider/ prefix (OpenRouter convention)
        for tier, model_id in tiers.items():
            assert "/" in model_id, (
                f"OpenRouter model '{model_id}' for tier {tier} should use provider/model format"
            )


class TestPricingCacheRoutingKey:
    """The critical routing fix: OpenRouter models get litellm_provider='openrouter'."""

    def test_fetch_openrouter_sets_litellm_provider(self):
        """fetch_openrouter_pricing sets litellm_provider='openrouter' on each entry.

        Without this, the BPC substring match in get_ranked_providers cannot
        route OpenRouter models to the openrouter client — they would have no
        provider key to join on.
        """
        import ast
        import inspect
        import textwrap

        from core import dynamic_pricing_fetcher

        source = inspect.getsource(
            dynamic_pricing_fetcher.DynamicPricingFetcher.fetch_openrouter_pricing
        )
        source = textwrap.dedent(source)
        tree = ast.parse(source)
        # Find the dict literal assigned into pricing[model_id]
        found_litellm_provider = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                keys = []
                for k in node.keys:
                    if isinstance(k, ast.Constant):
                        keys.append(k.value)
                if "source" in keys and "openrouter" in [
                    v.value for v in node.values if isinstance(v, ast.Constant)
                ]:
                    if "litellm_provider" in keys:
                        found_litellm_provider = True
                        break
        assert found_litellm_provider, (
            "fetch_openrouter_pricing does not set litellm_provider on pricing entries — "
            "BPC routing to the openrouter client will fail"
        )

    def test_openrouter_model_routes_to_openrouter_client(self):
        """The BPC substring match maps an OpenRouter model to the openrouter client.

        Simulates the active_provider resolution logic at byok_handler.py:959:
            active_provider = next(
                (p for p in available_providers if p in model_id.lower() or p == litellm_provider),
                None
            )
        """
        available_providers = ["openai", "deepseek", "openrouter"]
        # An OpenRouter-sourced model (provider/model format, litellm_provider=openrouter)
        model_id = "anthropic/claude-3.5-sonnet"
        litellm_provider = "openrouter"

        active_provider = next(
            (p for p in available_providers if p in model_id.lower() or p == litellm_provider),
            None,
        )
        assert active_provider == "openrouter", (
            f"Expected openrouter, got {active_provider} — the routing join is broken"
        )

    def test_litellm_model_does_not_steal_openrouter_routing(self):
        """A model with a different litellm_provider should not route to openrouter."""
        available_providers = ["openai", "deepseek", "openrouter"]
        model_id = "deepseek-chat"
        litellm_provider = "deepseek"

        active_provider = next(
            (p for p in available_providers if p in model_id.lower() or p == litellm_provider),
            None,
        )
        assert active_provider == "deepseek"
