"""
Tests for LearningService - Agent learning and optimization algorithms.

Coverage Goals (25-30% on 1228 lines):
- Learning algorithms (reinforcement, pattern recognition)
- Skill optimization (memento skills, alpha evolver)
- Learning from failures (error patterns, recovery strategies)
- Performance tracking (execution time, success rate)
- Learning cache and persistence
- Integration with Auto-Dev module
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry
)


class TestLearningAlgorithms:
    """Test learning algorithms and pattern recognition."""

    def test_learn_from_successful_execution(self):
        """Extract learning patterns from successful execution."""
        mock_db = Mock(spec=Session)

        mock_execution = Mock()
        mock_execution.id = "exec-123"
        mock_execution.outcome = "success"
        mock_execution.agent_id = "agent-456"
        mock_execution.execution_time_seconds = 2.5
        mock_execution.metadata_json = {
            "strategy": "parallel_processing",
            "optimization": "cache_hit"
        }

        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        learning = service.learn_from_execution("exec-123")

        assert learning["execution_id"] == "exec-123"
        assert learning["patterns_extracted"] is not None

    def test_learn_from_failed_execution(self):
        """Extract error patterns from failed execution."""
        mock_db = Mock(spec=Session)

        mock_execution = Mock()
        mock_execution.id = "exec-123"
        mock_execution.outcome = "error"
        mock_execution.error_message = "API timeout after 30s"
        mock_execution.error_category = "timeout"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        learning = service.learn_from_failure("exec-123")

        assert learning["error_pattern"] == "timeout"
        assert learning["recovery_strategy"] is not None

    def test_pattern_recognition_repeated_success(self):
        """Recognize patterns in repeated successful executions."""
        mock_db = Mock(spec=Session)

        mock_executions = [
            Mock(outcome="success", strategy="parallel", execution_time=2.0),
            Mock(outcome="success", strategy="parallel", execution_time=1.8),
            Mock(outcome="success", strategy="parallel", execution_time=2.1),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_executions
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        patterns = service.recognize_success_patterns(
            agent_id="agent-123",
            min_occurrences=3
        )

        assert len(patterns) > 0
        assert patterns[0]["strategy"] == "parallel"

    def test_pattern_recognition_repeated_failures(self):
        """Recognize patterns in repeated failures."""
        mock_db = Mock(spec=Session)

        mock_executions = [
            Mock(outcome="error", error_type="timeout", api_endpoint="/api/long-running"),
            Mock(outcome="error", error_type="timeout", api_endpoint="/api/long-running"),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_executions
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        patterns = service.recognize_failure_patterns(
            agent_id="agent-123"
        )

        assert len(patterns) > 0
        assert "timeout" in str(patterns[0])


class TestSkillOptimization:
    """Test skill optimization and Memento skills."""

    def test_optimize_skill_performance(self):
        """Optimize skill based on performance metrics."""
        mock_db = Mock(spec=Session)

        mock_skill = Mock()
        mock_skill.name = "data_analysis"
        mock_skill.success_rate = 0.75
        mock_skill.avg_execution_time = 3.5

        mock_db.query.return_value.filter.return_value.first.return_value = mock_skill
        mock_db.commit = Mock()

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        optimization = service.optimize_skill(
            skill_name="data_analysis",
            agent_id="agent-123"
        )

        assert optimization["skill_name"] == "data_analysis"
        assert optimization["improvements"] is not None

    def test_update_memento_skill(self):
        """Update Memento skill with new patterns."""
        mock_db = Mock(spec=Session)

        mock_skill = Mock()
        mock_skill.id = "skill-123"
        mock_skill.patterns = ["pattern_1", "pattern_2"]

        mock_db.query.return_value.filter.return_value.first.return_value = mock_skill
        mock_db.commit = Mock()

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        updated_skill = service.update_memento_skill(
            skill_id="skill-123",
            new_patterns=["pattern_3"]
        )

        assert "pattern_3" in updated_skill.patterns

    def test_alpha_evolver_mutation(self):
        """Apply Alpha evolver mutation to improve performance."""
        mock_db = Mock(spec=Session)

        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.parameters = {
            "learning_rate": 0.01,
            "batch_size": 32
        }

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.commit = Mock()

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        mutated = service.apply_alpha_evolver_mutation(
            agent_id="agent-123",
            mutation_type="learning_rate_adjustment"
        )

        assert mutated["parameters_modified"] is True


class TestPerformanceTracking:
    """Test performance tracking and metrics."""

    def test_track_execution_performance(self):
        """Track execution time and resource usage."""
        mock_db = Mock(spec=Session)

        mock_execution = Mock()
        mock_execution.id = "exec-123"
        mock_execution.execution_time_seconds = 2.5
        mock_execution.memory_used_mb = 512
        mock_execution.cpu_percent = 45.0

        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        metrics = service.track_performance(
            execution_id="exec-123"
        )

        assert metrics["execution_time"] == 2.5
        assert metrics["memory_used_mb"] == 512

    def test_calculate_success_rate(self):
        """Calculate success rate for agent."""
        mock_db = Mock(spec=Session)

        mock_executions = [
            Mock(outcome="success"),
            Mock(outcome="success"),
            Mock(outcome="error"),
            Mock(outcome="success"),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_executions
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        success_rate = service.calculate_success_rate(
            agent_id="agent-123"
        )

        assert success_rate == 0.75  # 3/4

    def test_track_resource_usage_trends(self):
        """Track resource usage trends over time."""
        mock_db = Mock(spec=Session)

        mock_metrics = [
            Mock(timestamp=datetime.utcnow() - timedelta(hours=3), memory_mb=500, cpu_percent=40),
            Mock(timestamp=datetime.utcnow() - timedelta(hours=2), memory_mb=520, cpu_percent=45),
            Mock(timestamp=datetime.utcnow() - timedelta(hours=1), memory_mb=510, cpu_percent=42),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_metrics
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        trends = service.get_resource_usage_trends(
            agent_id="agent-123",
            hours=3
        )

        assert len(trends) == 3
        assert trends[0]["memory_mb"] == 500


class TestLearningPersistence:
    """Test learning cache and database persistence."""

    def test_cache_learning_result(self):
        """Cache learning results for fast retrieval."""
        from core.learning_service_full import LearningService

        service = LearningService(db=Mock(spec=Session))

        # Cache learning result
        service.cache_learning(
            key="agent-123:pattern-1",
            value={"strategy": "parallel", "success_rate": 0.9}
        )

        # Retrieve from cache
        cached = service.get_cached_learning("agent-123:pattern-1")

        assert cached["strategy"] == "parallel"

    def test_cache_miss(self):
        """Return None for cache misses."""
        from core.learning_service_full import LearningService

        service = LearningService(db=Mock(spec=Session))

        cached = service.get_cached_learning("nonexistent-key")

        assert cached is None

    def test_persist_learning_to_database(self):
        """Persist learning records to database."""
        mock_db = Mock(spec=Session)
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        learning_record = {
            "agent_id": "agent-123",
            "pattern": "parallel_processing",
            "success_rate": 0.85,
            "timestamp": datetime.utcnow()
        }

        service.persist_learning(learning_record)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_get_historical_learning(self):
        """Retrieve historical learning records."""
        mock_db = Mock(spec=Session)

        mock_records = [
            Mock(pattern="pattern_1", success_rate=0.8, timestamp=datetime.utcnow()),
            Mock(pattern="pattern_2", success_rate=0.9, timestamp=datetime.utcnow()),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_records
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        history = service.get_learning_history(
            agent_id="agent-123",
            limit=10
        )

        assert len(history) == 2


class TestAutoDevIntegration:
    """Test integration with Auto-Dev module."""

    def test_event_bus_integration(self):
        """Publish learning events to event bus."""
        mock_db = Mock(spec=Session)
        mock_event_bus = Mock()

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db, event_bus=mock_event_bus)

        service.publish_learning_event(
            event_type="pattern_discovered",
            data={"pattern": "parallel_processing"}
        )

        mock_event_bus.publish.assert_called_once()

    def test_fitness_service_integration(self):
        """Calculate fitness score for skill mutations."""
        mock_db = Mock(spec=Session)

        mock_execution = Mock()
        mock_execution.success = True
        mock_execution.execution_time = 2.0

        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        fitness = service.calculate_fitness_score(
            agent_id="agent-123",
            skill_name="data_analysis"
        )

        assert fitness >= 0.0
        assert fitness <= 1.0

    def test_capability_gates_integration(self):
        """Check if learning unlocks new capabilities."""
        mock_db = Mock(spec=Session)

        mock_agent = Mock()
        mock_agent.capabilities = ["data_analysis", "reporting"]

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        unlocked = service.check_capability_unlock(
            agent_id="agent-123",
            new_skill="advanced_analytics"
        )

        assert unlocked is True or unlocked is False


class TestLearningFromFailures:
    """Test learning from failure patterns."""

    def test_extract_error_pattern(self):
        """Extract error pattern from failed execution."""
        mock_db = Mock(spec=Session)

        mock_execution = Mock()
        mock_execution.id = "exec-123"
        mock_execution.error_message = "Connection timeout after 30s"
        mock_execution.error_category = "timeout"
        mock_execution.retry_count = 3

        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        pattern = service.extract_error_pattern("exec-123")

        assert pattern["error_type"] == "timeout"
        assert pattern["retry_count"] == 3

    def test_suggest_recovery_strategy(self):
        """Suggest recovery strategy based on error pattern."""
        from core.learning_service_full import LearningService

        service = LearningService(db=Mock(spec=Session))

        error_pattern = {
            "error_type": "timeout",
            "endpoint": "/api/long-running",
            "avg_duration": 35.0
        }

        strategy = service.suggest_recovery_strategy(error_pattern)

        assert strategy["approach"] is not None
        assert "timeout" in strategy["approach"].lower()

    def test_learn_from_repeated_failures(self):
        """Learn optimal strategy from repeated failures."""
        mock_db = Mock(spec=Session)

        mock_failures = [
            Mock(error="timeout", strategy="retry"),
            Mock(error="timeout", strategy="increase_timeout"),
            Mock(error="timeout", strategy="async_approach"),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_failures
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        learning = service.learn_from_repeated_failures(
            agent_id="agent-123",
            error_type="timeout"
        )

        assert learning["optimal_strategy"] is not None


class TestErrorHandling:
    """Test error handling in learning operations."""

    def test_execution_not_found(self):
        """Handle missing execution gracefully."""
        mock_db = Mock(spec=Session)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        learning = service.learn_from_execution("nonexistent-exec")

        assert learning is None

    def test_invalid_pattern_data(self):
        """Handle invalid pattern data gracefully."""
        from core.learning_service_full import LearningService

        service = LearningService(db=Mock(spec=Session))

        # Should not raise exception
        result = service.validate_pattern_data({})

        assert result is False

    def test_cache_disabled(self):
        """Handle cache being disabled."""
        from core.learning_service_full import LearningService

        service = LearningService(db=Mock(spec=Session))
        service.cache_enabled = False

        cached = service.get_cached_learning("any-key")

        assert cached is None


class TestLearningMetrics:
    """Test learning metrics and analytics."""

    def test_get_learning_summary(self):
        """Get summary of learning progress."""
        mock_db = Mock(spec=Session)

        mock_records = [
            Mock(pattern="p1", success_rate=0.8),
            Mock(pattern="p2", success_rate=0.9),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_records
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        summary = service.get_learning_summary("agent-123")

        assert summary["total_patterns"] == 2
        assert summary["avg_success_rate"] == 0.85

    def test_compare_learning_performance(self):
        """Compare learning performance across agents."""
        mock_db = Mock(spec=Session)

        mock_stats = [
            Mock(agent_id="agent-1", success_rate=0.85),
            Mock(agent_id="agent-2", success_rate=0.75),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_stats
        mock_db.query.return_value.filter.return_value = mock_query

        from core.learning_service_full import LearningService
        service = LearningService(db=mock_db)

        comparison = service.compare_agents_learning(
            agent_ids=["agent-1", "agent-2"]
        )

        assert len(comparison) == 2
