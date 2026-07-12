"""
Test suite for Phase 3 Learning-Based LLM Routing.

RED PHASE: Tests for preference data collection, RouteLLM training, and cache optimization.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


# ============================================================================
# Preference Data Collector Tests
# ============================================================================

class TestFeedbackConfig:
    """Tests for FeedbackConfig"""

    def test_config_import(self):
        """Test that FeedbackConfig can be imported"""
        try:
            from core.llm.routing.preference_collector import FeedbackConfig
            assert FeedbackConfig is not None
        except ImportError as e:
            pytest.fail(f"FeedbackConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that FeedbackConfig has sensible defaults"""
        from core.llm.routing.preference_collector import FeedbackConfig

        config = FeedbackConfig()

        assert config.min_samples_for_training > 0
        assert 0 <= config.min_quality_score <= 1
        assert 0 <= config.ab_test_sample_rate <= 1


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass"""

    def test_decision_import(self):
        """Test that RoutingDecision can be imported"""
        try:
            from core.llm.routing.preference_collector import RoutingDecision
            assert RoutingDecision is not None
        except ImportError as e:
            pytest.fail(f"RoutingDecision import failed: {e}")

    def test_decision_creation(self):
        """Test that RoutingDecision can be created"""
        from core.llm.routing.preference_collector import RoutingDecision

        decision = RoutingDecision(
            workspace_id="test_ws",
            estimated_tokens=100,
            task_type="code",
            chosen_model="gpt-4o",
            chosen_provider="openai"
        )

        assert decision.workspace_id == "test_ws"
        assert decision.estimated_tokens == 100
        assert decision.task_type == "code"


class TestRoutingFeedback:
    """Tests for RoutingFeedback dataclass"""

    def test_feedback_import(self):
        """Test that RoutingFeedback can be imported"""
        try:
            from core.llm.routing.preference_collector import RoutingFeedback
            assert RoutingFeedback is not None
        except ImportError as e:
            pytest.fail(f"RoutingFeedback import failed: {e}")

    def test_feedback_creation(self):
        """Test that RoutingFeedback can be created"""
        from core.llm.routing.preference_collector import RoutingFeedback, RoutingOutcome

        feedback = RoutingFeedback(
            decision_id="test_decision",
            outcome=RoutingOutcome.SUCCESS,
            quality_score=0.8
        )

        assert feedback.decision_id == "test_decision"
        assert feedback.outcome == RoutingOutcome.SUCCESS
        assert feedback.quality_score == 0.8


class TestPreferenceDataCollector:
    """Tests for PreferenceDataCollector"""

    def test_collector_import(self):
        """Test that PreferenceDataCollector can be imported"""
        try:
            from core.llm.routing.preference_collector import PreferenceDataCollector
            assert PreferenceDataCollector is not None
        except ImportError as e:
            pytest.fail(f"PreferenceDataCollector import failed: {e}")

    def test_collector_initialization(self):
        """Test that collector can be initialized"""
        from core.llm.routing.preference_collector import PreferenceDataCollector, FeedbackConfig

        config = FeedbackConfig()
        collector = PreferenceDataCollector(config)

        assert collector is not None
        assert collector.config == config

    def test_record_decision(self):
        """Test that routing decision can be recorded"""
        from core.llm.routing.preference_collector import PreferenceDataCollector

        collector = PreferenceDataCollector()

        decision_id = collector.record_routing_decision(
            workspace_id="test_ws",
            tenant_id="test_tenant",
            estimated_tokens=100,
            task_type="code",
            prompt="Write a function",
            chosen_model="gpt-4o",
            chosen_provider="openai",
            chosen_tier="versatile"
        )

        assert decision_id in collector.decisions
        assert len(collector.decisions) == 1

    def test_record_feedback(self):
        """Test that feedback can be recorded"""
        from core.llm.routing.preference_collector import PreferenceDataCollector, RoutingOutcome

        collector = PreferenceDataCollector()

        # First record a decision
        decision_id = collector.record_routing_decision(
            workspace_id="test_ws",
            tenant_id="test_tenant",
            estimated_tokens=100,
            task_type="code",
            prompt="Write a function",
            chosen_model="gpt-4o",
            chosen_provider="openai",
            chosen_tier="versatile"
        )

        # Then record feedback
        feedback_id = collector.record_feedback(
            decision_id=decision_id,
            outcome=RoutingOutcome.SUCCESS,
            quality_score=0.9
        )

        assert feedback_id in collector.feedback_records

    def test_ab_test_group_assignment(self):
        """Test that A/B test group assignment works"""
        from core.llm.routing.preference_collector import PreferenceDataCollector

        collector = PreferenceDataCollector()

        # Assign groups
        group1 = collector.assign_ab_test_group("workspace1")
        group2 = collector.assign_ab_test_group("workspace1")

        # Should be deterministic
        assert group1 == group2
        assert group1 in ["learning", "control"]

    def test_should_use_learning_router(self):
        """Test that learning router usage decision works"""
        from core.llm.routing.preference_collector import PreferenceDataCollector, FeedbackConfig

        config = FeedbackConfig(enable_ab_testing=True, ab_test_sample_rate=1.0)
        collector = PreferenceDataCollector(config)

        # Force control group
        collector.ab_test_group["test_ws"] = "control"
        result = collector.should_use_learning_router("test_ws")

        assert result is False  # Control group shouldn't use learning

        # Force learning group
        collector.ab_test_group["test_ws2"] = "learning"
        result = collector.should_use_learning_router("test_ws2")

        assert result is True  # Learning group should use learning

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.llm.routing.preference_collector import get_preference_collector

        assert callable(get_preference_collector)


# ============================================================================
# RouteLLM Trainer Tests
# ============================================================================

class TestTrainingConfig:
    """Tests for TrainingConfig"""

    def test_config_import(self):
        """Test that TrainingConfig can be imported"""
        try:
            from core.llm.routing.routellm_trainer import TrainingConfig
            assert TrainingConfig is not None
        except ImportError as e:
            pytest.fail(f"TrainingConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that TrainingConfig has sensible defaults"""
        from core.llm.routing.routellm_trainer import TrainingConfig

        config = TrainingConfig()

        assert 0 < config.test_size < 1
        assert config.min_samples > 0
        assert config.n_estimators > 0
        assert config.ab_test_confidence > 0


class TestModelType:
    """Tests for ModelType enum"""

    def test_model_type_import(self):
        """Test that ModelType can be imported"""
        try:
            from core.llm.routing.routellm_trainer import ModelType
            assert ModelType is not None
        except ImportError as e:
            pytest.fail(f"ModelType import failed: {e}")

    def test_model_type_values(self):
        """Test that ModelType has required values"""
        from core.llm.routing.routellm_trainer import ModelType

        assert hasattr(ModelType, 'RANDOM_FOREST')
        assert hasattr(ModelType, 'LOGISTIC_REGRESSION')
        assert hasattr(ModelType, 'NEURAL_NETWORK')


class TestTrainingStatus:
    """Tests for TrainingStatus enum"""

    def test_status_import(self):
        """Test that TrainingStatus can be imported"""
        try:
            from core.llm.routing.routellm_trainer import TrainingStatus
            assert TrainingStatus is not None
        except ImportError as e:
            pytest.fail(f"TrainingStatus import failed: {e}")


class TestRouteLLMTrainer:
    """Tests for RouteLLMTrainer"""

    def test_trainer_import(self):
        """Test that RouteLLMTrainer can be imported"""
        try:
            from core.llm.routing.routellm_trainer import RouteLLMTrainer
            assert RouteLLMTrainer is not None
        except ImportError as e:
            pytest.fail(f"RouteLLMTrainer import failed: {e}")

    def test_trainer_initialization(self):
        """Test that trainer can be initialized"""
        from core.llm.routing.routellm_trainer import RouteLLMTrainer, TrainingConfig

        config = TrainingConfig()
        trainer = RouteLLMTrainer(config)

        assert trainer is not None
        assert trainer.config == config

    def test_train_returns_result(self):
        """Test that train returns TrainingResult"""
        from core.llm.routing.routellm_trainer import RouteLLMTrainer, TrainingResult, TrainingStatus

        trainer = RouteLLMTrainer()

        # Empty examples should return failed result
        result = trainer.train([])

        assert isinstance(result, TrainingResult)
        assert result.status == TrainingStatus.FAILED

    def test_predict_method(self):
        """Test that predict method exists"""
        from core.llm.routing.routellm_trainer import RouteLLMTrainer

        trainer = RouteLLMTrainer()

        assert hasattr(trainer, 'predict')
        assert callable(trainer.predict)

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.llm.routing.routellm_trainer import get_router_trainer

        assert callable(get_router_trainer)


class TestFeatureExtractor:
    """Tests for FeatureExtractor"""

    def test_extractor_import(self):
        """Test that FeatureExtractor can be imported"""
        try:
            from core.llm.routing.routellm_trainer import FeatureExtractor
            assert FeatureExtractor is not None
        except ImportError as e:
            pytest.fail(f"FeatureExtractor import failed: {e}")

    def test_extractor_initialization(self):
        """Test that extractor can be initialized"""
        from core.llm.routing.routellm_trainer import FeatureExtractor

        extractor = FeatureExtractor()

        assert extractor is not None
        assert len(extractor.feature_names) > 0

    def test_extract_features(self):
        """Test that extract_features returns correct shape"""
        from core.llm.routing.routellm_trainer import FeatureExtractor, TrainingExample

        extractor = FeatureExtractor()

        # Create mock example
        example = TrainingExample(
            estimated_tokens=100,
            task_type="code",
            prompt_features={"has_code": 1.0}
        )

        features = extractor.extract_features([example])

        assert features.shape == (1, len(extractor.feature_names))


# ============================================================================
# Cache Optimizer Tests
# ============================================================================

class TestCacheOptimizationConfig:
    """Tests for CacheOptimizationConfig"""

    def test_config_import(self):
        """Test that CacheOptimizationConfig can be imported"""
        try:
            from core.llm.routing.cache_optimizer import CacheOptimizationConfig
            assert CacheOptimizationConfig is not None
        except ImportError as e:
            pytest.fail(f"CacheOptimizationConfig import failed: {e}")

    def test_config_defaults(self):
        """Test that config has sensible defaults"""
        from core.llm.routing.cache_optimizer import CacheOptimizationConfig

        config = CacheOptimizationConfig()

        assert config.enable_prediction is not False
        assert config.min_prediction_confidence >= 0
        assert config.min_prediction_confidence <= 1


class TestCacheStrategy:
    """Tests for CacheStrategy enum"""

    def test_strategy_import(self):
        """Test that CacheStrategy can be imported"""
        try:
            from core.llm.routing.cache_optimizer import CacheStrategy
            assert CacheStrategy is not None
        except ImportError as e:
            pytest.fail(f"CacheStrategy import failed: {e}")

    def test_strategy_values(self):
        """Test that CacheStrategy has required values"""
        from core.llm.routing.cache_optimizer import CacheStrategy

        assert hasattr(CacheStrategy, 'LRU')
        assert hasattr(CacheStrategy, 'LFU')
        assert hasattr(CacheStrategy, 'PREDICTIVE')
        assert hasattr(CacheStrategy, 'ADAPTIVE')


class TestCacheOptimizer:
    """Tests for CacheOptimizer"""

    def test_optimizer_import(self):
        """Test that CacheOptimizer can be imported"""
        try:
            from core.llm.routing.cache_optimizer import CacheOptimizer
            assert CacheOptimizer is not None
        except ImportError as e:
            pytest.fail(f"CacheOptimizer import failed: {e}")

    def test_optimizer_initialization(self):
        """Test that optimizer can be initialized"""
        from core.llm.routing.cache_optimizer import CacheOptimizer, CacheOptimizationConfig

        config = CacheOptimizationConfig()
        optimizer = CacheOptimizer(config)

        assert optimizer is not None
        assert optimizer.config == config

    def test_record_access(self):
        """Test that cache access can be recorded"""
        from core.llm.routing.cache_optimizer import CacheOptimizer

        optimizer = CacheOptimizer()

        optimizer.record_access(
            prompt_hash="abc123",
            was_hit=True,
            latency_ms=50
        )

        assert len(optimizer.accesses) == 1
        assert optimizer.statistics.total_accesses == 1

    def test_get_cache_recommendations(self):
        """Test that recommendations can be generated"""
        from core.llm.routing.cache_optimizer import CacheOptimizer

        optimizer = CacheOptimizer()

        recommendations = optimizer.get_cache_recommendations("test_ws", 100)

        assert isinstance(recommendations, dict)
        assert "current_hit_rate" in recommendations
        assert "recommendations" in recommendations

    def test_factory_function(self):
        """Test that factory function exists"""
        from core.llm.routing.cache_optimizer import get_cache_optimizer

        assert callable(get_cache_optimizer)


class TestCacheWarmer:
    """Tests for CacheWarmer"""

    def test_warmer_import(self):
        """Test that CacheWarmer can be imported"""
        try:
            from core.llm.routing.cache_optimizer import CacheWarmer
            assert CacheWarmer is not None
        except ImportError as e:
            pytest.fail(f"CacheWarmer import failed: {e}")

    def test_warmer_initialization(self):
        """Test that warmer can be initialized"""
        from core.llm.routing.cache_optimizer import CacheWarmer, CacheOptimizationConfig

        config = CacheOptimizationConfig()
        warmer = CacheWarmer(config)

        assert warmer is not None
        assert warmer.config == config


class TestAccessPatternAnalyzer:
    """Tests for AccessPatternAnalyzer"""

    def test_analyzer_import(self):
        """Test that AccessPatternAnalyzer can be imported"""
        try:
            from core.llm.routing.cache_optimizer import AccessPatternAnalyzer
            assert AccessPatternAnalyzer is not None
        except ImportError as e:
            pytest.fail(f"AccessPatternAnalyzer import failed: {e}")

    def test_analyzer_initialization(self):
        """Test that analyzer can be initialized"""
        from core.llm.routing.cache_optimizer import AccessPatternAnalyzer, CacheOptimizationConfig

        config = CacheOptimizationConfig()
        analyzer = AccessPatternAnalyzer(config)

        assert analyzer is not None
        assert analyzer.config == config

    def test_record_access(self):
        """Test that access can be recorded"""
        from core.llm.routing.cache_optimizer import AccessPatternAnalyzer

        analyzer = AccessPatternAnalyzer()

        analyzer.record_access("hash123", datetime.now())

        assert "hash123" in analyzer.access_history

    def test_detect_pattern(self):
        """Test that pattern detection works"""
        from core.llm.routing.cache_optimizer import AccessPatternAnalyzer

        analyzer = AccessPatternAnalyzer()

        # Initially should be random (no history)
        pattern = analyzer.detect_pattern("new_hash")
        assert pattern.value in ["random", "sequential", "temporal"]


# ============================================================================
# Integration Tests
# ============================================================================

class TestRoutingModuleIntegration:
    """Tests for routing module integration"""

    def test_module_import(self):
        """Test that routing module can be imported"""
        try:
            import core.llm.routing
            assert core.llm.routing is not None
        except ImportError as e:
            pytest.fail(f"routing module import failed: {e}")

    def test_module_exports(self):
        """Test that module exports required components"""
        from core.llm.routing import (
            PreferenceDataCollector,
            RouteLLMTrainer,
            CacheOptimizer,
            get_preference_collector,
            get_router_trainer,
            get_cache_optimizer,
        )

        assert PreferenceDataCollector is not None
        assert RouteLLMTrainer is not None
        assert CacheOptimizer is not None
        assert callable(get_preference_collector)
        assert callable(get_router_trainer)
        assert callable(get_cache_optimizer)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
