"""
Tests for the local model provider system.

Verifies that user-registered local LLM backends (Ollama, LM Studio, vLLM, etc.)
are correctly integrated into the cognitive tier system, BPC ranking, and the
learning router.
"""

from __future__ import annotations

import pytest


class TestLocalModelModels:
    """ORM models exist and have the right fields."""

    def test_local_model_provider_model_exists(self):
        from core.models import LocalModelProvider
        assert LocalModelProvider.__tablename__ == "local_model_providers"
        cols = {c.name for c in LocalModelProvider.__table__.columns}
        assert {"id", "workspace_id", "name", "provider_type", "base_url", "is_active"}.issubset(cols)

    def test_local_model_capabilities_model_exists(self):
        from core.models import LocalModelCapabilities
        assert LocalModelCapabilities.__tablename__ == "local_model_capabilities"
        cols = {c.name for c in LocalModelCapabilities.__table__.columns}
        assert {"id", "provider_id", "model_id", "supports_tools", "supports_vision", "quality_score"}.issubset(cols)

    def test_audio_transcription_columns_and_defaults(self):
        """Fresh schemas declare explicit audio columns; unset rate != zero."""
        from core.models import LocalModelCapabilities
        cols = LocalModelCapabilities.__table__.columns
        assert "supports_transcription" in cols
        assert "audio_input_cost_per_second_usd" in cols

        transcription = cols["supports_transcription"]
        assert transcription.nullable is False
        assert transcription.default.arg is False

        audio_rate = cols["audio_input_cost_per_second_usd"]
        assert audio_rate.nullable is True
        assert audio_rate.default is None


class TestLocalModelRoutes:
    """API routes exist and have the right paths."""

    def test_routes_registered(self):
        from api.routes.local_model_routes import router
        paths = {r.path for r in router.routes if hasattr(r, "path")}
        assert "/api/local-models" in paths
        assert "/api/local-models/{provider_id}" in paths
        assert "/api/local-models/{provider_id}/models" in paths
        assert "/api/local-models/{provider_id}/capabilities" in paths
        assert "/api/local-models/{provider_id}/test" in paths


class TestAudioCapabilityValidation:
    """Request-level validation for the audio settings."""

    def test_non_finite_rate_is_rejected(self):
        from pydantic import ValidationError
        from api.routes.local_model_routes import SetCapabilitiesRequest

        for bad in (float("inf"), float("-inf"), float("nan")):
            with pytest.raises(ValidationError):
                SetCapabilitiesRequest(
                    model_id="m", audio_input_cost_per_second_usd=bad
                )

    def test_old_capability_fields_keep_original_defaults_and_null_behavior(self):
        from pydantic import ValidationError
        from api.routes.local_model_routes import SetCapabilitiesRequest

        omitted = SetCapabilitiesRequest(model_id="m")
        assert omitted.supports_tools is False
        assert omitted.supports_vision is False
        assert omitted.supports_reasoning is False
        assert omitted.quality_score == 0.5
        assert omitted.speed_score == 0.5
        assert omitted.context_window == 4096

        for field in ("supports_tools", "supports_vision", "supports_reasoning"):
            with pytest.raises(ValidationError):
                SetCapabilitiesRequest(model_id="m", **{field: None})

    def test_zero_rate_and_unset_are_distinct(self):
        from api.routes.local_model_routes import SetCapabilitiesRequest

        omitted = SetCapabilitiesRequest(model_id="m")
        assert "audio_input_cost_per_second_usd" not in omitted.model_fields_set
        assert omitted.audio_input_cost_per_second_usd is None

        zero = SetCapabilitiesRequest(
            model_id="m", audio_input_cost_per_second_usd=0
        )
        assert "audio_input_cost_per_second_usd" in zero.model_fields_set
        assert zero.audio_input_cost_per_second_usd == 0

        cleared = SetCapabilitiesRequest(
            model_id="m", audio_input_cost_per_second_usd=None
        )
        assert "audio_input_cost_per_second_usd" in cleared.model_fields_set
        assert cleared.audio_input_cost_per_second_usd is None


class TestCognitiveTierLocalModels:
    """The cognitive tier system supports local models in all tiers."""

    def test_all_tiers_have_local_models(self):
        """Every tier's default model list should include at least one ollama/ entry."""
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier
        clf = CognitiveClassifier()
        for tier in CognitiveTier:
            models = clf.get_tier_models(tier)
            local_models = [m for m in models if "ollama/" in m or "local" in m.lower()]
            assert len(local_models) > 0, (
                f"Tier {tier.value} should have at least one local model option"
            )

    def test_get_tier_models_accepts_workspace_override(self):
        """get_tier_models accepts a workspace_id for override lookup."""
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier
        clf = CognitiveClassifier()
        # With no DB / no preference, should fall back to defaults.
        models = clf.get_tier_models(CognitiveTier.MICRO, workspace_id="test_ws")
        assert len(models) > 0  # Defaults returned


class TestLearningRouterLocalModels:
    """The learning router can load local models into its registry."""

    def test_load_local_models_method_exists(self):
        from core.learning_llm_router import LearningBasedRouter
        assert hasattr(LearningBasedRouter, "load_local_models_into_registry"), (
            "LearningBasedRouter must have load_local_models_into_registry for local model integration"
        )

    def test_load_returns_zero_with_no_db(self):
        """When no providers are registered, returns 0 without crashing."""
        from core.learning_llm_router import LearningBasedRouter
        from unittest.mock import Mock
        from sqlalchemy.orm import Session
        router = LearningBasedRouter(Mock(spec=Session))
        # This will fail to find providers (no DB) and return 0.
        result = router.load_local_models_into_registry(workspace_id="nonexistent")
        assert result == 0


class TestBYOKHandlerLocalProviders:
    """BYOKHandler has the local-provider loading method."""

    def test_load_local_providers_method_exists(self):
        from core.llm.byok_handler import BYOKHandler
        assert hasattr(BYOKHandler, "_load_local_providers"), (
            "BYOKHandler must have _load_local_providers to load registered local models"
        )


class TestPricingCacheIntegration:
    """Local models can be injected into the pricing cache."""

    def test_pricing_cache_accepts_local_entries(self):
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        # Inject a local model directly (simulating what the routes do).
        fetcher.pricing_cache["test_local_model_123"] = {
            "model_id": "test_local_model_123",
            "litellm_provider": "ollama",
            "input_cost": 0.0,
            "output_cost": 0.0,
            "max_input_tokens": 8192,
            "supports_tools": True,
            "supports_vision": False,
            "supports_reasoning": False,
            "quality_score": 0.7,
        }
        # Verify it's retrievable.
        price = fetcher.get_model_price("test_local_model_123")
        assert price is not None
        assert price.get("input_cost") == 0.0
        # Cleanup.
        del fetcher.pricing_cache["test_local_model_123"]


class TestMigration:
    """The migration chains correctly off the current head."""

    def test_migration_file_exists(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "20260712_add_local_model_providers.py"
        )
        assert os.path.exists(path), "Migration file must exist"

    def test_migration_chains_correctly(self):
        """Read the migration's revision/down_revision to verify the chain."""
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "20260712_add_local_model_providers.py"
        )
        content = open(path).read()
        assert 'revision: str = "20260712_local_models"' in content
        assert 'down_revision: Union[str, Sequence[str], None] = "20260711_llm_routing_feedback"' in content

    def test_audio_capability_migration_chains_from_goal_run_revision(self):
        """The additive audio migration sits on the required head and is additive."""
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "20261118_local_model_audio_capability.py"
        )
        assert os.path.exists(path), "Audio capability migration file must exist"
        content = open(path).read()
        assert 'revision: str = "20261118_local_model_audio_capability"' in content
        assert 'down_revision: Union[str, Sequence[str], None] = "20261102_goal_run_material_revision"' in content
        assert "supports_transcription" in content
        assert "audio_input_cost_per_second_usd" in content
        assert "create_table" not in content
        assert "drop_table" not in content
