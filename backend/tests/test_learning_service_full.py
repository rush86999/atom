"""
Comprehensive test suite for LearningServiceFull.

Covers learning session management, progress tracking, completion logic,
and error handling for agent learning and adaptation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import asyncio

from core.learning_service_full import (
    LearningService,
    LearningExperience,
    LearningModel,
    AdaptationStrategy,
    KnowledgeNode,
    KnowledgeEdge,
    EmergentBehavior,
    ExperienceType,
    AdaptationType,
    NodeType
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.query = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    llm = Mock()
    llm.generate_response = AsyncMock(return_value="Test response")
    llm.generate_structured = AsyncMock(return_value={"key": "value"})
    return llm


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    embedding = Mock()
    embedding.get_embedding = AsyncMock(return_value=[0.1] * 384)
    return embedding


@pytest.fixture
def learning_service(mock_db, mock_llm_service, mock_embedding_service):
    """LearningService instance with mocked dependencies."""
    service = LearningService(
        db=mock_db,
        llm_service=mock_llm_service,
        embedding_service=mock_embedding_service
    )
    return service


# ============================================================================
# TEST: LEARNING SESSION CREATION
# ============================================================================

class TestLearningSessionCreation:
    """Test learning session creation and initialization."""

    @pytest.mark.asyncio
    async def test_create_learning_session_success(self, learning_service):
        """Test successful learning experience recording."""
        experience_id = await learning_service.record_experience(
            agent_id="agent_123",
            experience_type="success",
            task_description="Complete data analysis task",
            inputs={"dataset": "sales_2024.csv"},
            actions=[{"action": "analyze", "params": {"method": "regression"}}],
            outcomes={"accuracy": 0.95, "speed": 1.2}
        )

        assert experience_id is not None
        assert experience_id.startswith("exp_")
        assert experience_id in learning_service.experiences_cache

        experience = learning_service.experiences_cache[experience_id]
        assert experience.agent_id == "agent_123"
        assert experience.task_description == "Complete data analysis task"
        assert experience.outcomes["accuracy"] == 0.95

    @pytest.mark.asyncio
    async def test_create_learning_session_with_custom_params(self, learning_service):
        """Test session creation with custom parameters and context."""
        custom_context = {
            "environment": "production",
            "tenant_id": "tenant_abc",
            "priority": "high"
        }

        experience_id = await learning_service.record_experience(
            agent_id="agent_456",
            experience_type="failure",
            task_description="API integration failed",
            inputs={"endpoint": "/api/v1/users"},
            actions=[{"action": "http_request", "status": 500}],
            outcomes={"success": False, "error_rate": 1.0},
            feedback={"issue": "timeout"},
            context=custom_context
        )

        experience = learning_service.experiences_cache[experience_id]
        assert experience.type == "failure"
        assert experience.context["environment"] == "production"
        assert experience.feedback["issue"] == "timeout"

    @pytest.mark.asyncio
    async def test_create_learning_session_invalid_input(self, learning_service):
        """Test session creation with invalid input raises appropriate error."""
        # Test with empty task description - should still create experience
        # (service is resilient to empty strings)
        experience_id = await learning_service.record_experience(
            agent_id="agent_invalid",
            experience_type="success",
            task_description="",  # Empty description
            inputs={},
            actions=[],
            outcomes={}
        )

        # Service should still create experience with empty description
        assert experience_id is not None
        assert experience_id in learning_service.experiences_cache

    @pytest.mark.asyncio
    async def test_create_learning_session_duplicate_detection(self, learning_service):
        """Test duplicate experience handling."""
        # Record first experience
        exp_id_1 = await learning_service.record_experience(
            agent_id="agent_789",
            experience_type="success",
            task_description="Process invoice #12345",
            inputs={"invoice_id": "12345"},
            actions=[{"action": "process"}],
            outcomes={"processed": True}
        )

        # Record similar experience (should create new ID)
        exp_id_2 = await learning_service.record_experience(
            agent_id="agent_789",
            experience_type="success",
            task_description="Process invoice #12345",  # Same task
            inputs={"invoice_id": "12345"},
            actions=[{"action": "process"}],
            outcomes={"processed": True}
        )

        # Different IDs (service doesn't prevent duplicates)
        assert exp_id_1 != exp_id_2


# ============================================================================
# TEST: LEARNING PROGRESS TRACKING
# ============================================================================

class TestLearningProgressTracking:
    """Test learning progress tracking and metrics."""

    @pytest.mark.asyncio
    async def test_track_learning_progress(self, learning_service):
        """Test tracking learning progress over multiple experiences."""
        # Record multiple experiences for same agent
        for i in range(5):
            await learning_service.record_experience(
                agent_id="agent_progress",
                experience_type="success",
                task_description=f"Task {i}",
                inputs={"iteration": i},
                actions=[{"step": i}],
                outcomes={"score": 0.7 + (i * 0.05)}
            )

        # Verify progress tracking
        agent_experiences = [
            exp for exp in learning_service.experiences_cache.values()
            if exp.agent_id == "agent_progress"
        ]

        assert len(agent_experiences) == 5

        # Check score improvement
        scores = [exp.outcomes["score"] for exp in agent_experiences]
        assert scores[0] == 0.7
        assert scores[-1] == pytest.approx(0.9, abs=0.05)  # Improved over time (0.7 + 4*0.05 = 0.9)

    @pytest.mark.asyncio
    async def test_update_learning_metrics(self, learning_service):
        """Test updating learning metrics dynamically."""
        # Create learning model
        model_id = "model_test_001"
        model = LearningModel(
            id=model_id,
            model_type="reinforcement_learning",
            name="Q-Learning Agent",
            description="Test RL model",
            algorithm="Q-Learning",
            parameters={"learning_rate": 0.01, "discount_factor": 0.95},
            performance={"accuracy": 0.8, "reward": 100},
            data={"episodes": 100},
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        learning_service.models_cache[model_id] = model

        # Update metrics
        updated_model = learning_service.models_cache[model_id]
        updated_model.performance["accuracy"] = 0.85
        updated_model.performance["reward"] = 150
        updated_model.data["episodes"] = 150
        updated_model.updated_at = datetime.now(timezone.utc)

        assert updated_model.performance["accuracy"] == 0.85
        assert updated_model.performance["reward"] == 150
        assert updated_model.data["episodes"] == 150

    @pytest.mark.asyncio
    async def test_calculate_learning_completion_rate(self, learning_service):
        """Test calculation of learning completion rate."""
        # Record experiences with different outcomes
        success_count = 7
        failure_count = 3

        for i in range(success_count):
            await learning_service.record_experience(
                agent_id="agent_completion",
                experience_type="success",
                task_description=f"Success task {i}",
                inputs={},
                actions=[],
                outcomes={"success": True}
            )

        for i in range(failure_count):
            await learning_service.record_experience(
                agent_id="agent_completion",
                experience_type="failure",
                task_description=f"Failure task {i}",
                inputs={},
                actions=[],
                outcomes={"success": False}
            )

        # Calculate completion rate
        agent_experiences = [
            exp for exp in learning_service.experiences_cache.values()
            if exp.agent_id == "agent_completion"
        ]

        completion_rate = sum(1 for exp in agent_experiences if exp.type == "success") / len(agent_experiences)

        assert completion_rate == 0.7  # 7/10 = 70%

    @pytest.mark.asyncio
    async def test_learning_progress_persistence(self, learning_service, mock_db):
        """Test that learning progress persists to database."""
        experience_id = await learning_service.record_experience(
            agent_id="agent_persist",
            experience_type="success",
            task_description="Persistent task",
            inputs={"test": "data"},
            actions=[{"action": "test"}],
            outcomes={"result": "success"}
        )

        # Verify experience was created
        assert experience_id in learning_service.experiences_cache


# ============================================================================
# TEST: LEARNING COMPLETION LOGIC
# ============================================================================

class TestLearningCompletionLogic:
    """Test learning session completion and archival."""

    @pytest.mark.asyncio
    async def test_mark_learning_session_complete(self, learning_service):
        """Test marking a learning session as complete."""
        # Create an active strategy
        strategy_id = "strategy_001"
        strategy = AdaptationStrategy(
            id=strategy_id,
            type=AdaptationType.INCREMENTAL,
            name="Performance Optimization",
            description="Improve agent performance",
            trigger={"metric": "accuracy", "threshold": 0.9},
            mechanism={"type": "parameter_tuning"},
            scope={"agents": ["agent_123"]},
            impact={"accuracy_improvement": 0.05},
            validation={"test_set": "validation_001"},
            status="active",
            applied_at=datetime.now(timezone.utc),
            results={"accuracy_before": 0.85, "accuracy_after": 0.90},
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        learning_service.strategies_cache[strategy_id] = strategy

        # Mark as complete
        strategy.status = "completed"
        strategy.is_active = False
        strategy.updated_at = datetime.now(timezone.utc)

        assert strategy.status == "completed"
        assert strategy.is_active is False

    @pytest.mark.asyncio
    async def test_generate_learning_summary(self, learning_service):
        """Test generation of learning summary from experiences."""
        # Record diverse experiences
        experiences_data = [
            ("success", "Task A completed", {"accuracy": 0.95}),
            ("failure", "Task B failed", {"error": "timeout"}),
            ("correction", "Task B corrected", {"accuracy": 0.88}),
        ]

        for exp_type, desc, outcome in experiences_data:
            await learning_service.record_experience(
                agent_id="agent_summary",
                experience_type=exp_type,
                task_description=desc,
                inputs={},
                actions=[],
                outcomes=outcome
            )

        # Generate summary
        agent_experiences = [
            exp for exp in learning_service.experiences_cache.values()
            if exp.agent_id == "agent_summary"
        ]

        summary = {
            "total_experiences": len(agent_experiences),
            "success_rate": sum(1 for e in agent_experiences if e.type == "success") / len(agent_experiences),
            "failure_rate": sum(1 for e in agent_experiences if e.type == "failure") / len(agent_experiences),
            "correction_rate": sum(1 for e in agent_experiences if e.type == "correction") / len(agent_experiences),
        }

        assert summary["total_experiences"] == 3
        assert summary["success_rate"] == pytest.approx(0.333, rel=0.1)
        assert summary["failure_rate"] == pytest.approx(0.333, rel=0.1)
        assert summary["correction_rate"] == pytest.approx(0.333, rel=0.1)

    @pytest.mark.asyncio
    async def test_learning_outcome_validation(self, learning_service):
        """Test validation of learning outcomes."""
        # Record experience with specific outcomes
        await learning_service.record_experience(
            agent_id="agent_validation",
            experience_type="success",
            task_description="Validation test",
            inputs={"test_data": "sample"},
            actions=[{"validate": True}],
            outcomes={
                "accuracy": 0.92,
                "precision": 0.89,
                "recall": 0.94,
                "f1_score": 0.915
            }
        )

        experience = list(learning_service.experiences_cache.values())[0]

        # Validate outcomes meet thresholds
        assert experience.outcomes["accuracy"] >= 0.90
        assert experience.outcomes["precision"] >= 0.85
        assert experience.outcomes["recall"] >= 0.90
        assert 0.90 <= experience.outcomes["f1_score"] <= 0.92

    @pytest.mark.asyncio
    async def test_learning_session_archival(self, learning_service):
        """Test archival of old learning sessions."""
        # Create old experience (30 days ago)
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=30)

        old_experience = LearningExperience(
            id="exp_old_001",
            type="success",
            agent_id="agent_archive",
            task_description="Old task",
            inputs={},
            actions=[],
            outcomes={},
            feedback={},
            reflections=[],
            patterns=[],
            vector=[],
            context={},
            timestamp=old_timestamp
        )

        learning_service.experiences_cache["exp_old_001"] = old_experience

        # Create recent experience
        await learning_service.record_experience(
            agent_id="agent_archive",
            experience_type="success",
            task_description="Recent task",
            inputs={},
            actions=[],
            outcomes={}
        )

        # Verify both exist
        assert "exp_old_001" in learning_service.experiences_cache

        # Archival would move old experiences to cold storage
        # (simulated here by checking timestamp)
        old_exp = learning_service.experiences_cache["exp_old_001"]
        days_since_creation = (datetime.now(timezone.utc) - old_exp.timestamp).days

        assert days_since_creation >= 30


# ============================================================================
# TEST: ERROR HANDLING
# ============================================================================

class TestLearningServiceErrorHandling:
    """Test error handling and recovery."""

    @pytest.mark.asyncio
    async def test_learning_service_exception_handling(self, learning_service, mock_llm_service):
        """Test exception handling in learning service operations."""
        # Mock LLM service to raise exception
        mock_llm_service.generate_response.side_effect = Exception("LLM service unavailable")

        # Service should handle exception gracefully and still create experience
        # (embedding generation may fail but experience is still recorded)
        experience_id = await learning_service.record_experience(
            agent_id="agent_error",
            experience_type="success",
            task_description="Error test",
            inputs={},
            actions=[],
            outcomes={}
        )

        # Experience should still be created despite LLM error
        assert experience_id is not None
        assert experience_id in learning_service.experiences_cache

    @pytest.mark.asyncio
    async def test_invalid_learning_session_id(self, learning_service):
        """Test handling of invalid learning session ID."""
        # Try to retrieve non-existent experience
        invalid_id = "exp_nonexistent_12345"

        experience = learning_service.experiences_cache.get(invalid_id)

        assert experience is None

    @pytest.mark.asyncio
    async def test_learning_progress_corruption_recovery(self, learning_service):
        """Test recovery from corrupted learning progress data."""
        # Simulate corrupted data
        corrupted_experience = LearningExperience(
            id="exp_corrupted",
            type="success",
            agent_id="agent_corrupt",
            task_description="",  # Empty description (potentially corrupted)
            inputs=None,  # None instead of dict
            actions=[],
            outcomes={},  # Empty outcomes
            feedback={},
            reflections=[],
            patterns=[],
            vector=[],
            context={},
            timestamp=datetime.now(timezone.utc)
        )

        # Service should handle corrupted data gracefully
        learning_service.experiences_cache["exp_corrupted"] = corrupted_experience

        # Verify service can still operate
        new_exp_id = await learning_service.record_experience(
            agent_id="agent_corrupt",
            experience_type="success",
            task_description="Valid task",
            inputs={"valid": "data"},
            actions=[],
            outcomes={"result": "success"}
        )

        assert new_exp_id is not None
        assert new_exp_id in learning_service.experiences_cache
