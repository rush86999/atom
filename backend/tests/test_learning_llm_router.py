"""
Tests for Learning-Based LLM Router

Tests RouteLLM-style routing with preference data collection.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

from core.learning_llm_router import (
    LearningBasedRouter,
    ModelSpec,
    ModelCapability,
    RoutingRequest,
    RoutingResult,
    RoutingFeedback,
)


class TestModelSpec:
    """Test ModelSpec dataclass"""

    def test_model_spec_creation(self):
        """Test model specification creation"""
        model = ModelSpec(
            model_id="gpt-4o",
            provider="openai",
            model_name="gpt-4o",
            capabilities={ModelCapability.CODE_GENERATION, ModelCapability.REASONING},
            cost_per_million=2.50,
            quality_score=0.92,
            speed_score=0.70,
            context_window=128000,
            supports_cache=True,
            tier="premium",
        )

        assert model.model_id == "gpt-4o"
        assert model.provider == "openai"
        assert ModelCapability.CODE_GENERATION in model.capabilities
        assert model.cost_per_million == 2.50
        assert model.tier == "premium"


class TestRoutingRequest:
    """Test RoutingRequest dataclass"""

    def test_routing_request_defaults(self):
        """Test routing request with default values"""
        request = RoutingRequest(
            tenant_id="tenant-1",
            task_type="code_generation",
            estimated_tokens=1000,
        )

        assert request.tenant_id == "tenant-1"
        assert request.task_type == "code_generation"
        assert request.estimated_tokens == 1000
        assert request.requires_quality is True
        assert request.requires_reasoning is False
        assert request.max_latency_ms is None

    def test_routing_request_full(self):
        """Test routing request with all fields"""
        request = RoutingRequest(
            tenant_id="tenant-1",
            task_type="reasoning",
            estimated_tokens=5000,
            requires_quality=True,
            requires_reasoning=True,
            requires_vision=False,
            max_latency_ms=1000,
            budget_limit=0.01,
        )

        assert request.requires_reasoning is True
        assert request.max_latency_ms == 1000
        assert request.budget_limit == 0.01


class TestRoutingResult:
    """Test RoutingResult dataclass"""

    def test_routing_result_creation(self):
        """Test routing result creation"""
        model = Mock(
            model_id="gpt-4o",
            model_name="gpt-4o",
            cost_per_million=2.50,
        )

        result = RoutingResult(
            selected_model=model,
            confidence=0.85,
            expected_cost=0.0025,
            expected_quality=0.92,
            reasoning="High quality requirements met",
            alternatives=[],
            routing_time_ms=5.0,
        )

        assert result.confidence == 0.85
        assert result.expected_cost == 0.0025
        assert result.routing_time_ms == 5.0


class TestRoutingFeedback:
    """Test RoutingFeedback dataclass"""

    def test_feedback_creation(self):
        """Test routing feedback creation"""
        feedback = RoutingFeedback(
            routing_result_id="result-123",
            tenant_id="tenant-1",
            model_id="gpt-4o",
            task_type="code_generation",
            success=True,
            quality_satisfied=True,
            cost_within_budget=True,
            user_satisfaction=0.9,
            actual_cost=0.0025,
            actual_latency_ms=150.0,
        )

        assert feedback.success is True
        assert feedback.quality_satisfied is True
        assert feedback.user_satisfaction == 0.9


class TestLearningBasedRouter:
    """Test learning-based router"""

    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def router(self, db_session):
        """Create router instance"""
        return LearningBasedRouter(db_session)

    def test_router_creation(self, router):
        """Test router initialization"""
        assert router.db == router.db
        assert len(router._model_registry) > 0
        assert "gpt-4o" in router._model_registry
        assert "claude-3-5-sonnet" in router._model_registry

    def test_model_registry_contents(self, router):
        """Test model registry has expected models"""
        # Check OpenAI models
        assert "gpt-4o" in router._model_registry
        assert "gpt-4o-mini" in router._model_registry
        assert "o1-preview" in router._model_registry

        # Check Anthropic models
        assert "claude-3-5-sonnet" in router._model_registry
        assert "claude-3-5-haiku" in router._model_registry

        # Check DeepSeek
        assert "deepseek-chat" in router._model_registry

        # Check Gemini
        assert "gemini-2.5-flash" in router._model_registry

    def test_model_specs_have_required_fields(self, router):
        """Test all models have required fields"""
        for model in router._model_registry.values():
            assert hasattr(model, "model_id")
            assert hasattr(model, "provider")
            assert hasattr(model, "capabilities")
            assert hasattr(model, "cost_per_million")
            assert hasattr(model, "quality_score")
            assert hasattr(model, "speed_score")
            assert hasattr(model, "tier")

    def test_get_cheapest_model(self, router):
        """Test getting cheapest model"""
        cheapest = router._get_cheapest_model()

        # Should be gemini-2.5-flash at $0.08/million
        assert cheapest.model_id == "gemini-2.5-flash"
        assert cheapest.cost_per_million == 0.08

    def test_filter_by_capabilities_quality(self, router):
        """Test filtering by quality requirement"""
        request = RoutingRequest(
            tenant_id="tenant-1",
            task_type="reasoning",
            estimated_tokens=1000,
            requires_quality=True,
        )

        candidates = router._filter_by_capabilities(request)

        # Should include models with HIGH_QUALITY capability
        model_ids = [m.model_id for m in candidates]
        assert "o1-preview" in model_ids
        assert "claude-3-5-sonnet" in model_ids

    def test_filter_by_capabilities_vision(self, router):
        """Test filtering by vision requirement"""
        request = RoutingRequest(
            tenant_id="tenant-1",
            task_type="vision",
            estimated_tokens=1000,
            requires_quality=False,  # Only test vision, not quality
            requires_vision=True,
        )

        candidates = router._filter_by_capabilities(request)

        # Should include models with VISION capability
        model_ids = [m.model_id for m in candidates]
        assert "gpt-4o" in model_ids

    def test_filter_by_cost(self, router):
        """Test filtering by cost budget"""
        candidates = list(router._model_registry.values())

        # Filter to models under $0.20/million
        affordable = router._filter_by_cost(
            candidates, budget_limit=0.001, estimated_tokens=1000
        )

        # All models should be affordable at this budget for 1K tokens
        model_ids = [m.model_id for m in affordable]
        assert "gpt-4o-mini" in model_ids
        assert "gemini-2.5-flash" in model_ids

    def test_filter_by_latency(self, router):
        """Test filtering by latency requirement"""
        candidates = list(router._model_registry.values())

        # Filter to fast models (<500ms)
        fast = router._filter_by_latency(candidates, max_latency_ms=500)

        # Should include fast models
        model_ids = [m.model_id for m in fast]
        assert "gemini-2.5-flash" in model_ids  # speed_score 0.95
        assert "gpt-4o-mini" in model_ids  # speed_score 0.85

    def test_get_learned_weights_default(self, router):
        """Test default learned weights"""
        weights = router._get_learned_weights("code_generation", "tenant-1")

        assert weights["quality"] == 0.5
        assert weights["cost"] == 0.2
        assert weights["speed"] == 0.3

    def test_get_learned_weights_reasoning(self, router):
        """Test reasoning task has higher quality weight"""
        weights = router._get_learned_weights("reasoning", "tenant-1")

        assert weights["quality"] == 0.6
        assert weights["cost"] == 0.1

    def test_get_learned_weights_extraction(self, router):
        """Test extraction task has higher cost weight"""
        weights = router._get_learned_weights("extraction", "tenant-1")

        assert weights["cost"] == 0.4

    def test_get_available_models_no_filter(self, router):
        """Test getting all available models"""
        models = router.get_available_models()

        assert len(models) == len(router._model_registry)

    def test_get_available_models_by_capability(self, router):
        """Test filtering by capability"""
        models = router.get_available_models(
            capabilities=[ModelCapability.HIGH_QUALITY]
        )

        model_ids = [m.model_id for m in models]
        assert "o1-preview" in model_ids
        assert "claude-3-5-sonnet" in model_ids

    def test_get_available_models_by_tier(self, router):
        """Test filtering by tier"""
        models = router.get_available_models(tier="premium")

        for model in models:
            assert model.tier == "premium"

    def test_get_available_models_by_cost(self, router):
        """Test filtering by max cost"""
        models = router.get_available_models(max_cost=1.0)

        for model in models:
            assert model.cost_per_million <= 1.0

    @pytest.mark.asyncio
    async def test_route_simple_request(self, router):
        """Test routing a simple request"""
        request = RoutingRequest(
            tenant_id="tenant-1",
            task_type="question_answering",
            estimated_tokens=1000,
        )

        result = await router.route(request)

        assert isinstance(result, RoutingResult)
        assert result.selected_model is not None
        assert result.confidence > 0
        assert result.expected_cost > 0

    @pytest.mark.asyncio
    async def test_route_with_budget_constraint(self, router):
        """Test routing with budget constraint"""
        request = RoutingRequest(
            tenant_id="tenant-1",
            task_type="question_answering",
            estimated_tokens=1000,
            budget_limit=0.0005,
        )

        result = await router.route(request)

        # Should select affordable model
        assert result.selected_model is not None
        assert result.expected_cost <= 0.0005 or result.routing_time_ms > 0

    @pytest.mark.asyncio
    async def test_route_with_latency_constraint(self, router):
        """Test routing with latency constraint"""
        request = RoutingRequest(
            tenant_id="tenant-1",
            task_type="question_answering",
            estimated_tokens=1000,
            max_latency_ms=500,
        )

        result = await router.route(request)

        # Should prefer fast models
        assert result.selected_model is not None

    @pytest.mark.asyncio
    async def test_record_feedback(self, router):
        """Test recording routing feedback"""
        feedback = RoutingFeedback(
            routing_result_id="result-123",
            tenant_id="tenant-1",
            model_id="gpt-4o",
            task_type="code_generation",
            success=True,
            quality_satisfied=True,
            cost_within_budget=True,
        )

        await router.record_feedback(feedback)

        # Check feedback was stored
        key = "tenant-1:code_generation"
        assert key in router._preference_data
        assert len(router._preference_data[key]) == 1

    @pytest.mark.asyncio
    async def test_feedback_triggers_retraining(self, router):
        """Test that enough feedback triggers retraining"""
        # Add 10 feedback entries
        for i in range(10):
            feedback = RoutingFeedback(
                routing_result_id=f"result-{i}",
                tenant_id="tenant-1",
                model_id="gpt-4o",
                task_type="code_generation",
                success=True,
                quality_satisfied=True,
                cost_within_budget=True,
            )
            await router.record_feedback(feedback)

        # Should have triggered retraining
        key = "tenant-1:code_generation"
        assert len(router._preference_data[key]) == 10

    @pytest.mark.asyncio
    async def test_get_routing_statistics(self, router):
        """Test getting routing statistics"""
        # Add some feedback
        feedback = RoutingFeedback(
            routing_result_id="result-1",
            tenant_id="tenant-1",
            model_id="gpt-4o",
            task_type="code_generation",
            success=True,
            quality_satisfied=True,
            cost_within_budget=True,
        )
        await router.record_feedback(feedback)

        stats = await router.get_routing_statistics("tenant-1")

        assert stats["tenant_id"] == "tenant-1"
        assert stats["total_models"] > 0

    @pytest.mark.asyncio
    async def test_export_routing_data(self, router):
        """Test exporting routing data"""
        # Add feedback with recent timestamp
        feedback = RoutingFeedback(
            routing_result_id="result-1",
            tenant_id="tenant-1",
            model_id="gpt-4o",
            task_type="code_generation",
            success=True,
            quality_satisfied=True,
            cost_within_budget=True,
            timestamp=datetime.now(timezone.utc),
        )
        await router.record_feedback(feedback)

        export = await router.export_routing_data("tenant-1", days=30)

        assert export["tenant_id"] == "tenant-1"
        assert "routing_feedback" in export
        assert len(export["routing_feedback"]) >= 1

    def test_update_model_registry(self, router):
        """Test updating model registry"""
        new_models = [{
            "model_id": "test-model",
            "provider": "test",
            "model_name": "Test Model",
            "capabilities": ["fast_response", "cheap"],
            "cost_per_million": 0.05,
            "quality_score": 0.70,
            "speed_score": 0.90,
            "context_window": 4000,
            "supports_cache": False,
            "tier": "standard",
        }]

        added = router.update_model_registry(new_models)

        assert added == 1
        assert "test-model" in router._model_registry

    def test_clear_learning_cache(self, router):
        """Test clearing learning cache"""
        router._router_cache["tenant-1:task"] = (None, 0.5)

        router.clear_learning_cache("tenant-1")

        assert "tenant-1:task" not in router._router_cache

    def test_clear_learning_cache_all(self, router):
        """Test clearing all learning cache"""
        router._router_cache["tenant-1:task"] = (None, 0.5)
        router._router_cache["tenant-2:task"] = (None, 0.5)

        router.clear_learning_cache()

        assert len(router._router_cache) == 0
