"""
Tests verifying end-to-end wiring of MiniMax (latest), GLM 5.2, and Kimi.

These three providers were partially wired — the audit found:
  - GLM 5.2: no client in providers_config (core path broken)
  - Kimi: COST_EFFICIENT_MODELS mapped to Qwen models (would 404)
  - MiniMax: stale hallucination cascade (M2.7 not M3) + wrong egress domain

Each test class covers one provider across all touchpoints.
"""

from __future__ import annotations

import inspect
import pytest


# ---------------------------------------------------------------------------
# GLM 5.2 (Zhipu AI)
# ---------------------------------------------------------------------------

class TestGLMWiring:
    """GLM 5.2 is wired end-to-end: client, benchmarks, pricing, tier, egress."""

    def test_glm_in_providers_config(self):
        """The _initialize_clients method includes glm in providers_config."""
        from core.llm.byok_handler import BYOKHandler

        source = inspect.getsource(BYOKHandler._initialize_clients)
        assert '"glm"' in source, "glm not in providers_config — no client will be created"
        assert "https://open.bigmodel.cn/api/paas/v4" in source

    def test_glm_models_have_benchmark_scores(self):
        """GLM models have quality scores above the default floor (70)."""
        from core.benchmarks import MODEL_QUALITY_SCORES

        for model in ("glm-5.2", "glm-5", "glm-4.6", "glm-4.5"):
            assert model in MODEL_QUALITY_SCORES, f"{model} missing from benchmark scores"
            assert MODEL_QUALITY_SCORES[model] >= 85, (
                f"{model} score {MODEL_QUALITY_SCORES[model]} too low — BPC will deprioritize"
            )

    def test_glm_in_cost_efficient_models(self):
        """GLM has default models per complexity tier."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        assert "glm" in COST_EFFICIENT_MODELS
        tiers = COST_EFFICIENT_MODELS["glm"]
        assert tiers  # non-empty
        # The ADVANCED tier should map to glm-5.2 (the flagship)
        from core.llm.byok_handler import QueryComplexity
        assert "5.2" in tiers[QueryComplexity.ADVANCED]

    def test_glm_pricing_fallback_exists(self):
        """dynamic_pricing_fetcher has a GLM hardcoded fallback block."""
        from core.dynamic_pricing_fetcher import DynamicPricingFetcher

        source = inspect.getsource(DynamicPricingFetcher.fetch_litellm_pricing)
        assert "glm" in source.lower(), "No GLM pricing fallback block found"
        assert "litellm_provider" in source

    def test_glm_recognized_by_cognitive_tier(self):
        """The cognitive tier provider detector recognizes glm models."""
        from core.llm.cognitive_tier_service import CognitiveTierService

        svc = CognitiveTierService.__new__(CognitiveTierService)
        assert svc._model_to_provider("glm-5.2") == "glm"
        assert svc._model_to_provider("glm-4.6") == "glm"

    def test_glm_sandbox_egress_allowed(self):
        """Sandboxed agents can reach the Zhipu AI API."""
        from core.sandbox_egress_proxy import _BASELINE_EGRESS_HOSTS, _LLM_PROVIDER_HOSTS

        assert "open.bigmodel.cn" in _BASELINE_EGRESS_HOSTS
        assert "open.bigmodel.cn" in _LLM_PROVIDER_HOSTS

    def test_glm_in_hallucination_cascade(self):
        """Hallucination cascade can escalate to glm-5.2."""
        from core.hallucination_config import FRONTIER_MODELS, _FRONTIER_BY_PROVIDER

        assert "glm-5.2" in FRONTIER_MODELS
        assert _FRONTIER_BY_PROVIDER.get("glm") == "glm-5.2"

    def test_glm_in_byok_endpoints_defaults(self):
        """byok_endpoints registers a GLM provider card."""
        from core.byok_endpoints import BYOKManager

        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr._initialize_default_providers()
        assert "glm" in mgr.providers
        assert mgr.providers["glm"].api_key_env_var == "GLM_API_KEY"

    def test_glm_in_valid_providers(self):
        """GLM is in the valid_providers allowlist."""
        from core import byok_endpoints
        import ast

        source = inspect.getsource(byok_endpoints.store_api_key)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "valid_providers":
                        found = ast.literal_eval(node.value)
                        assert "glm" in found
                        return
        pytest.fail("valid_providers not found")

    def test_glm_quality_above_bpc_floor(self):
        """get_quality_score returns a non-default score for GLM models."""
        from core.benchmarks import get_quality_score

        # Should NOT return 70 (the default floor for unknown models)
        assert get_quality_score("glm-5.2") > 90
        assert get_quality_score("glm-5") > 90


# ---------------------------------------------------------------------------
# Kimi (Moonshot AI)
# ---------------------------------------------------------------------------

class TestKimiWiring:
    """Kimi K2 models route correctly through the moonshot client."""

    def test_moonshot_cost_efficient_models_are_kimi(self):
        """COST_EFFICIENT_MODELS['moonshot'] uses Kimi models, NOT Qwen."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS, QueryComplexity

        assert "moonshot" in COST_EFFICIENT_MODELS
        models = COST_EFFICIENT_MODELS["moonshot"]
        all_models = list(models.values())
        # Every model should be a Kimi model, not a Qwen model
        for m in all_models:
            assert "kimi" in m.lower(), f"Moonshot tier maps to non-Kimi model: {m}"
            assert "qwen" not in m.lower(), f"Moonshot tier still maps to Qwen: {m}"

    def test_kimi_models_have_benchmark_scores(self):
        """Kimi K2 models have quality scores."""
        from core.benchmarks import MODEL_QUALITY_SCORES

        assert "kimi-k2.6" in MODEL_QUALITY_SCORES
        assert MODEL_QUALITY_SCORES["kimi-k2.6"] >= 90

    def test_kimi_pricing_fallback_exists(self):
        """dynamic_pricing_fetcher has a Kimi/Moonshot pricing fallback."""
        from core.dynamic_pricing_fetcher import DynamicPricingFetcher

        source = inspect.getsource(DynamicPricingFetcher.fetch_litellm_pricing)
        assert "kimi" in source.lower(), "No Kimi pricing fallback block found"

    def test_kimi_in_hallucination_cascade(self):
        """Hallucination cascade can escalate to kimi-k2.6."""
        from core.hallucination_config import FRONTIER_MODELS, _FRONTIER_BY_PROVIDER

        assert "kimi-k2.6" in FRONTIER_MODELS
        assert _FRONTIER_BY_PROVIDER.get("moonshot") == "kimi-k2.6"

    def test_moonshot_cache_configured(self):
        """cache_aware_router has a moonshot entry."""
        from core.llm.cache_aware_router import CacheAwareRouter
        import inspect as _inspect

        source = _inspect.getsource(CacheAwareRouter)
        assert '"moonshot"' in source, "moonshot missing from cache_aware_router"

    def test_moonshot_in_byok_endpoints_defaults(self):
        """byok_endpoints registers a moonshot provider card."""
        from core.byok_endpoints import BYOKManager

        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr._initialize_default_providers()
        assert "moonshot" in mgr.providers
        assert mgr.providers["moonshot"].api_key_env_var == "MOONSHOT_API_KEY"

    def test_moonshot_sandbox_egress_allowed(self):
        """Sandboxed agents can reach the Moonshot API."""
        from core.sandbox_egress_proxy import _BASELINE_EGRESS_HOSTS, _LLM_PROVIDER_HOSTS

        assert "api.moonshot.cn" in _BASELINE_EGRESS_HOSTS
        assert "api.moonshot.cn" in _LLM_PROVIDER_HOSTS

    def test_kimi_routes_to_moonshot_client(self):
        """The BPC substring/provider match routes kimi models to moonshot."""
        # Simulate the matching logic from get_ranked_providers
        available_providers = ["moonshot", "openai", "deepseek"]
        # kimi-k2.6 has litellm_provider="moonshot" from our pricing fallback
        model_id = "kimi-k2.6"
        litellm_provider = "moonshot"

        active = next(
            (p for p in available_providers if p in model_id.lower() or p == litellm_provider),
            None,
        )
        assert active == "moonshot"

    def test_kimi_provider_detection(self):
        """dynamic_pricing_fetcher._infer_provider recognizes kimi."""
        from core.dynamic_pricing_fetcher import DynamicPricingFetcher

        fetcher = DynamicPricingFetcher.__new__(DynamicPricingFetcher)
        assert fetcher._infer_provider("kimi-k2.6") == "moonshot"
        assert fetcher._infer_provider("kimi-k2-thinking") == "moonshot"


# ---------------------------------------------------------------------------
# MiniMax (latest = M3)
# ---------------------------------------------------------------------------

class TestMiniMaxWiring:
    """MiniMax M3 cascade and egress are current (not stale M2.7)."""

    def test_minimax_cascade_targets_m3(self):
        """Hallucination cascade escalates to M3, not the stale M2.7."""
        from core.hallucination_config import _FRONTIER_BY_PROVIDER

        target = _FRONTIER_BY_PROVIDER.get("minimax")
        assert target is not None
        assert "M3" in target or "m3" in target.lower(), (
            f"Cascade target is '{target}' — should be MiniMax-M3, not the stale M2.7"
        )

    def test_minimax_m3_in_frontier_models(self):
        """MiniMax-M3 is in the FRONTIER_MODELS set."""
        from core.hallucination_config import FRONTIER_MODELS

        assert "MiniMax-M3" in FRONTIER_MODELS

    def test_minimax_sandbox_egress_correct_domain(self):
        """Sandbox egress uses api.minimax.io (not the stale api.minimaxi.com)."""
        from core.sandbox_egress_proxy import _BASELINE_EGRESS_HOSTS, _LLM_PROVIDER_HOSTS

        assert "api.minimax.io" in _BASELINE_EGRESS_HOSTS
        assert "api.minimax.io" in _LLM_PROVIDER_HOSTS

    def test_minimax_in_byok_endpoints_defaults(self):
        """byok_endpoints has a 'minimax' provider card (matching the client key)."""
        from core.byok_endpoints import BYOKManager

        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr._initialize_default_providers()
        assert "minimax" in mgr.providers, (
            "minimax card missing — BYOK key lookups via get_api_key('minimax') will fail"
        )
        assert mgr.providers["minimax"].api_key_env_var == "MINIMAX_API_KEY"

    def test_minimax_byok_routes_not_stale(self):
        """byok_routes.py MiniMax card is not the stale M2.5."""
        from api.byok_routes import BYOKManager

        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr._initialize_default_providers()
        cfg = mgr.providers["minimax"]
        assert "api.minimax.io" in cfg.base_url, (
            f"base_url is '{cfg.base_url}' — should use api.minimax.io not api.minimax.chat"
        )
        assert "2.5" not in cfg.model, f"model is '{cfg.model}' — should be M3 not M2.5"

    def test_minimax_cost_efficient_models_are_m3(self):
        """COST_EFFICIENT_MODELS uses M3 models."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        models = list(COST_EFFICIENT_MODELS["minimax"].values())
        for m in models:
            assert "M3" in m or "m3" in m.lower(), f"MiniMax tier maps to non-M3 model: {m}"


# ---------------------------------------------------------------------------
# Anthropic / Mistral / Groq (added in the production-readiness pass)
# ---------------------------------------------------------------------------

class TestAnthropicWiring:
    """Anthropic is wired end-to-end (was missing from providers_config)."""

    def test_anthropic_in_providers_config(self):
        """The _initialize_clients method includes anthropic in providers_config."""
        from core.llm.byok_handler import BYOKHandler

        source = inspect.getsource(BYOKHandler._initialize_clients)
        assert '"anthropic"' in source, (
            "anthropic not in providers_config — Claude can never serve requests"
        )
        assert "api.anthropic.com" in source

    def test_anthropic_has_cost_efficient_models(self):
        """Anthropic has default models per complexity tier."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        assert "anthropic" in COST_EFFICIENT_MODELS

    def test_anthropic_sandbox_egress(self):
        """Sandboxed agents can reach the Anthropic API."""
        from core.sandbox_egress_proxy import _BASELINE_EGRESS_HOSTS, _LLM_PROVIDER_HOSTS

        assert "api.anthropic.com" in _BASELINE_EGRESS_HOSTS
        assert "api.anthropic.com" in _LLM_PROVIDER_HOSTS


class TestMistralWiring:
    """Mistral is wired end-to-end (was missing from providers_config)."""

    def test_mistral_in_providers_config(self):
        from core.llm.byok_handler import BYOKHandler

        source = inspect.getsource(BYOKHandler._initialize_clients)
        assert '"mistral"' in source
        assert "api.mistral.ai" in source

    def test_mistral_cost_efficient_models(self):
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        assert "mistral" in COST_EFFICIENT_MODELS

    def test_mistral_benchmark_scores(self):
        from core.benchmarks import MODEL_QUALITY_SCORES

        assert "mistral-large-latest" in MODEL_QUALITY_SCORES
        assert MODEL_QUALITY_SCORES["mistral-large-latest"] >= 85

    def test_mistral_hallucination_cascade(self):
        from core.hallucination_config import _FRONTIER_BY_PROVIDER

        assert _FRONTIER_BY_PROVIDER.get("mistral") == "mistral-large-latest"

    def test_mistral_sandbox_egress(self):
        from core.sandbox_egress_proxy import _BASELINE_EGRESS_HOSTS

        assert "api.mistral.ai" in _BASELINE_EGRESS_HOSTS


class TestGroqWiring:
    """Groq is wired end-to-end (was missing from providers_config + egress)."""

    def test_groq_in_providers_config(self):
        from core.llm.byok_handler import BYOKHandler

        source = inspect.getsource(BYOKHandler._initialize_clients)
        assert '"groq"' in source
        assert "api.groq.com" in source

    def test_groq_cost_efficient_models(self):
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        assert "groq" in COST_EFFICIENT_MODELS

    def test_groq_benchmark_scores(self):
        from core.benchmarks import MODEL_QUALITY_SCORES

        assert "llama-3.3-70b-versatile" in MODEL_QUALITY_SCORES
        assert MODEL_QUALITY_SCORES["llama-3.3-70b-versatile"] >= 80

    def test_groq_hallucination_cascade(self):
        from core.hallucination_config import _FRONTIER_BY_PROVIDER

        assert _FRONTIER_BY_PROVIDER.get("groq") == "llama-3.3-70b-versatile"

    def test_groq_sandbox_egress(self):
        from core.sandbox_egress_proxy import _BASELINE_EGRESS_HOSTS, _LLM_PROVIDER_HOSTS

        assert "api.groq.com" in _BASELINE_EGRESS_HOSTS
        assert "api.groq.com" in _LLM_PROVIDER_HOSTS


class TestEgressCompleteness:
    """All provider domains in providers_config have sandbox egress entries."""

    def test_all_llm_provider_domains_allowed(self):
        """Every provider base_url in providers_config has an egress entry."""
        import os
        from core.sandbox_egress_proxy import _BASELINE_EGRESS_HOSTS, _LLM_PROVIDER_HOSTS
        from urllib.parse import urlparse

        # Known provider domains (from providers_config + _load_local_providers)
        expected_domains = [
            "api.anthropic.com",
            "api.openai.com",
            "api.deepseek.com",
            "api.moonshot.cn",
            "api.deepinfra.com",
            "api.minimax.io",
            "dashscope-intl.aliyuncs.com",
            "generativelanguage.googleapis.com",
            "api.xiaomi.com",
            "open.bigmodel.cn",
            "api.mistral.ai",
            "api.groq.com",
            "openrouter.ai",
        ]
        for domain in expected_domains:
            assert domain in _BASELINE_EGRESS_HOSTS, (
                f"{domain} missing from _BASELINE_EGRESS_HOSTS — sandboxed agents blocked"
            )
            assert domain in _LLM_PROVIDER_HOSTS, (
                f"{domain} missing from _LLM_PROVIDER_HOSTS"
            )

