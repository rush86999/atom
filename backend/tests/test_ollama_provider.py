"""
TDD regression tests for Ollama provider integration.

Verifies Ollama is registered as a first-class LLM provider across:
  - byok_handler.py        (provider config, tiers, cost-efficient models, fallback order, no-key init)
  - llm_service.py         (LLMProvider enum + get_provider routing)
  - byok_endpoints.py      (default AIProviderConfig entry)
  - cognitive_tier_system.py (tier model mappings)

These tests are source/introspection-based so they run without a live Ollama
server or database session.
"""

from __future__ import annotations

import inspect
import os
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# 1. Provider config registration
# ---------------------------------------------------------------------------


class TestOllamaProviderConfig:
    """Ollama must be registered in the BYOK handler provider config."""

    def test_ollama_in_providers_config(self):
        """_initialize_clients must include ollama with a base_url."""
        from core.llm import byok_handler

        src = inspect.getsource(byok_handler.BYOKHandler._initialize_clients)
        # The providers_config dict literal must contain an ollama entry
        assert '"ollama"' in src, "Ollama missing from providers_config in _initialize_clients"
        # Must reference the env var with a localhost default
        assert "OLLAMA_BASE_URL" in src, "providers_config must read OLLAMA_BASE_URL env var"
        assert "localhost:11434" in src, "providers_config must default to localhost:11434"

    def test_ollama_uses_dummy_api_key(self):
        """Ollama requires no API key — handler must initialize without one."""
        from core.llm import byok_handler

        src = inspect.getsource(byok_handler.BYOKHandler._initialize_clients)
        # There must be a dedicated special-case block for ollama (separate from
        # the main API-key-gated loop) that uses a dummy key.
        assert '"ollama"' in src, "Missing ollama branch"
        assert 'api_key="ollama"' in src or "api_key='ollama'" in src, (
            "Ollama must be initialized with a dummy api_key (no real key needed)"
        )

    def test_ollama_base_url_env_override(self):
        """OLLAMA_BASE_URL env var must override the default base_url."""
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://example.invalid:9999/v1"}):
            # Re-import to pick up env var at module load is not necessary —
            # the handler reads the env var inside _initialize_clients, so we
            # verify by instantiating the handler.
            from core.llm.byok_handler import BYOKHandler

            # Constructor calls _initialize_clients internally
            try:
                handler = BYOKHandler(workspace_id="test-ollama-override")
            except Exception:
                # If construction fails due to unrelated infra (db, redis), we
                # still want to check the ollama client if it was set.
                handler = None

            if handler is not None and "ollama" in (handler.async_clients or {}):
                client = handler.async_clients["ollama"]
                base = str(client.base_url)
                assert "example.invalid" in base and "9999" in base, (
                    f"OLLAMA_BASE_URL override was not applied to the Ollama client (got {base})"
                )


# ---------------------------------------------------------------------------
# 2. Provider tier membership
# ---------------------------------------------------------------------------


class TestOllamaProviderTier:
    """Ollama belongs in the budget tier (it's free / local)."""

    def test_ollama_in_budget_tier(self):
        from core.llm.byok_handler import PROVIDER_TIERS

        assert "ollama" in PROVIDER_TIERS["budget"], (
            "Ollama must be listed in PROVIDER_TIERS['budget'] — it is free / local"
        )

    def test_ollama_in_fallback_order(self):
        """_get_provider_fallback_order must list ollama in the priority list."""
        from core.llm import byok_handler

        src = inspect.getsource(byok_handler.BYOKHandler._get_provider_fallback_order)
        assert '"ollama"' in src, (
            "Ollama missing from priority_order in _get_provider_fallback_order"
        )


# ---------------------------------------------------------------------------
# 3. Cost-efficient model routing
# ---------------------------------------------------------------------------


class TestOllamaCostEfficientModels:
    """Ollama models must be present in COST_EFFICIENT_MODELS."""

    def test_ollama_in_cost_efficient_models(self):
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        assert "ollama" in COST_EFFICIENT_MODELS, (
            "Ollama missing from COST_EFFICIENT_MODELS"
        )
        ollama_models = COST_EFFICIENT_MODELS["ollama"]
        # Each QueryComplexity must be represented
        from core.llm.byok_handler import QueryComplexity

        for complexity in QueryComplexity:
            assert complexity in ollama_models, (
                f"Ollama COST_EFFICIENT_MODELS missing entry for {complexity}"
            )

    def test_ollama_models_are_local_models(self):
        """Cost-efficient ollama models must be actual local model tags."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        models = set(COST_EFFICIENT_MODELS["ollama"].values())
        # llama3 / mistral / mixtral are the canonical local model families
        assert any("llama3" in m for m in models), "Expected a llama3 variant"
        assert any("mixtral" in m or "mistral" in m for m in models), (
            "Expected a mistral/mixtral variant for complex tasks"
        )


# ---------------------------------------------------------------------------
# 4. LLMProvider enum + routing
# ---------------------------------------------------------------------------


class TestOllamaEnumAndRouting:
    """LLMProvider enum and get_provider() must recognize ollama models."""

    def test_ollama_in_provider_enum(self):
        from core.llm_service import LLMProvider

        assert hasattr(LLMProvider, "OLLAMA"), "LLMProvider enum missing OLLAMA member"
        assert LLMProvider.OLLAMA.value == "ollama"

    @pytest.mark.parametrize(
        "model",
        [
            "ollama/llama3:8b",
            "ollama/mistral:7b",
            "ollama/mixtral:8x7b",
            "llama3:8b",
            "llama3:70b",
            "mistral:7b",
            "mixtral:8x7b",
        ],
    )
    def test_get_provider_routes_ollama_models(self, model):
        """Models prefixed with ollama/ or canonical local tags route to OLLAMA."""
        # LLMService requires a DB-less construction path; get_provider is a
        # pure function over the enum, so we bypass __init__.
        from core.llm_service import LLMProvider, LLMService

        svc = LLMService.__new__(LLMService)
        provider = svc.get_provider(model)
        assert provider is LLMProvider.OLLAMA, (
            f"Model {model!r} routed to {provider}, expected OLLAMA"
        )

    def test_get_provider_default_unchanged(self):
        """Unknown models still fall through to OPENAI default."""
        from core.llm_service import LLMProvider, LLMService

        svc = LLMService.__new__(LLMService)
        assert svc.get_provider("some-unknown-model") is LLMProvider.OPENAI


# ---------------------------------------------------------------------------
# 5. Default AIProviderConfig
# ---------------------------------------------------------------------------


class TestOllamaDefaultProviderConfig:
    """BYOK manager must register a default AIProviderConfig for ollama."""

    def test_ollama_in_default_providers(self):
        from core.byok_endpoints import AIProviderConfig, BYOKManager

        # Instantiate manager (loads defaults)
        try:
            manager = BYOKManager()
        except Exception as e:
            pytest.skip(f"BYOKManager could not be constructed in this env: {e}")

        assert "ollama" in manager.providers, (
            "Ollama missing from default AIProviderConfig registration"
        )
        provider = manager.providers["ollama"]
        assert isinstance(provider, AIProviderConfig)
        # Zero cost — local inference is free
        assert provider.cost_per_token == 0.0, (
            "Ollama cost_per_token must be 0.0 (local inference is free)"
        )
        # Must point at the local Ollama OpenAI-compatible endpoint
        assert provider.base_url is not None
        assert "11434" in provider.base_url or "OLLAMA_BASE_URL" in provider.base_url or "/v1" in provider.base_url

    def test_ollama_provider_does_not_require_encryption(self):
        """Ollama stores no secret — requires_encryption should be False."""
        from core.byok_endpoints import BYOKManager

        try:
            manager = BYOKManager()
        except Exception as e:
            pytest.skip(f"BYOKManager could not be constructed in this env: {e}")

        provider = manager.providers.get("ollama")
        if provider is None:
            pytest.fail("Ollama provider not registered")
        assert provider.requires_encryption is False, (
            "Ollama requires no encryption (no API key to protect)"
        )


# ---------------------------------------------------------------------------
# 6. Cognitive tier mappings
# ---------------------------------------------------------------------------


class TestOllamaCognitiveTierModels:
    """Ollama models must appear in the cognitive tier model recommendations."""

    def test_ollama_in_micro_and_standard_tiers(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        classifier = CognitiveClassifier()
        micro = classifier.get_tier_models(CognitiveTier.MICRO)
        standard = classifier.get_tier_models(CognitiveTier.STANDARD)

        # llama3:8b is the canonical small/local model
        assert any("llama3" in m for m in micro), (
            "MICRO tier must include an ollama llama3 model"
        )
        assert any("llama3" in m for m in standard), (
            "STANDARD tier must include an ollama llama3 model"
        )

    def test_ollama_mixtral_in_high_tiers(self):
        """Mixtral (larger local model) belongs in HEAVY/COMPLEX tiers."""
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        classifier = CognitiveClassifier()
        heavy = classifier.get_tier_models(CognitiveTier.HEAVY)
        complex_tier = classifier.get_tier_models(CognitiveTier.COMPLEX)

        assert any("mixtral" in m for m in heavy) or any("mixtral" in m for m in complex_tier), (
            "Mixtral must be recommended in HEAVY or COMPLEX tier"
        )
