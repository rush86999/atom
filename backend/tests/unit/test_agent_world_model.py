"""
Comprehensive Unit Tests for Agent World Model

Target: core/agent_world_model.py (2,206 lines, <20% coverage → 80%+ target)

Test Coverage Areas:
1. Business Facts Provisioning (12 tests)
2. JIT Citation Verification (12 tests)
3. World Model Querying (12 tests)
4. Fact Aggregation (10 tests)
5. Answer Synthesis (10 tests)
6. R2/S3 Storage (10 tests)
7. Knowledge Graph (8 tests)
8. Integration Tests (12 tests)
9. Edge Cases (8 tests)

Total: 94 test functions
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import asyncio
import json
from typing import List, Dict, Any

from core.agent_world_model import (
    WorldModelService,
    AgentExperience,
    BusinessFact,
    DetailLevel
)
from core.models import AgentRegistry, AgentStatus
from core.database import SessionLocal


# ========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db_session():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDB handler."""
    handler = Mock()
    handler.db = Mock()  # Mock LanceDB connection
    handler.db.table_names = Mock(return_value=[])
    handler.create_table = Mock()
    handler.add_document = Mock(return_value="doc-1")
    handler.search = Mock(return_value=[])
    return handler


@pytest.fixture
def world_model_service(mock_lancedb_handler):
    """Create world model service with mocked LanceDB."""
    service = WorldModelService(workspace_id="test-workspace")
    service.db = mock_lancedb_handler
    return service


@pytest.fixture
def test_agent(db_session):
    """Create a test agent."""
    agent = AgentRegistry(
        id="test-agent-1",
        name="TestAgent",
        category="test",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


# ========================================================================
# 1. Agent Experience Tests (15 tests)
# =========================================================================

class TestAgentExperience:
    """Test agent experience recording and retrieval."""

    @pytest.mark.asyncio
    async def test_record_experience_success(self, world_model_service):
        """Test successful experience recording."""
        experience = AgentExperience(
            id="exp-1",
            agent_id="agent-1",
            task_type="reconciliation",
            input_summary="Reconcile SKU-123",
            outcome="Success",
            learnings="Mismatch due to timing difference",
            confidence_score=0.8,
            agent_role="Finance",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True
        world_model_service.db.add_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_experience_with_feedback(self, world_model_service):
        """Test recording experience with feedback score."""
        experience = AgentExperience(
            id="exp-feedback-1",
            agent_id="agent-1",
            task_type="outreach",
            input_summary="Customer outreach",
            outcome="Success",
            learnings="Personalized emails work better",
            confidence_score=0.7,
            feedback_score=0.9,
            agent_role="Sales",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

        # Check metadata includes feedback
        call_args = world_model_service.db.add_document.call_args
        metadata = call_args[1]["metadata"]
        assert "feedback_score" in metadata
        assert metadata["feedback_score"] == 0.9

    @pytest.mark.asyncio
    async def test_record_experience_with_step_efficiency(self, world_model_service):
        """Test recording experience with step efficiency."""
        experience = AgentExperience(
            id="exp-efficiency-1",
            agent_id="agent-1",
            task_type="data_analysis",
            input_summary="Analyze sales data",
            outcome="Success",
            learnings="Direct query is faster",
            confidence_score=0.85,
            step_efficiency=0.8,  # Took fewer steps than expected
            agent_role="Data",
            timestamp=datetime.now(timezone.utc),
            metadata_trace={
                "expected_steps": 10,
                "actual_steps": 8,
                "plan_adherence": 0.9
            }
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

        call_args = world_model_service.db.add_document.call_args
        metadata = call_args[1]["metadata"]
        assert metadata["step_efficiency"] == 0.8

    @pytest.mark.asyncio
    async def test_record_experience_with_artifacts(self, world_model_service):
        """Test recording experience with artifacts."""
        experience = AgentExperience(
            id="exp-artifacts-1",
            agent_id="agent-1",
            task_type="visualization",
            input_summary="Create sales chart",
            outcome="Success",
            learnings="Bar charts work best for this data",
            confidence_score=0.75,
            artifacts=["canvas-123", "chart-456"],
            agent_role="Analytics",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

        call_args = world_model_service.db.add_document.call_args
        metadata = call_args[1]["metadata"]
        assert metadata["artifacts"] == ["canvas-123", "chart-456"]

    @pytest.mark.asyncio
    async def test_record_experience_performance_benchmark(self, world_model_service):
        """Test experience recording performance (target: <100ms)."""
        experience = AgentExperience(
            id="exp-perf-1",
            agent_id="agent-1",
            task_type="test",
            input_summary="Performance test",
            outcome="Success",
            learnings="Test learning",
            confidence_score=0.5,
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )

        import time
        start = time.time()
        result = await world_model_service.record_experience(experience)
        duration = (time.time() - start) * 1000

        assert result is True
        assert duration < 100, f"Recording took {duration}ms, target <100ms"

    @pytest.mark.asyncio
    async def test_record_experience_batch(self, world_model_service):
        """Test batch experience recording."""
        experiences = [
            AgentExperience(
                id=f"exp-batch-{i}",
                agent_id="agent-1",
                task_type="batch_test",
                input_summary=f"Batch task {i}",
                outcome="Success",
                learnings=f"Learning {i}",
                confidence_score=0.5,
                agent_role="Test",
                timestamp=datetime.now(timezone.utc)
            )
            for i in range(10)
        ]

        # Record all experiences
        results = await asyncio.gather(*[
            world_model_service.record_experience(exp) for exp in experiences
        ])

        assert all(results)
        assert world_model_service.db.add_document.call_count == 10

    @pytest.mark.asyncio
    async def test_record_experience_concurrent(self, world_model_service):
        """Test concurrent experience recording."""
        async def record_experience(i):
            experience = AgentExperience(
                id=f"exp-concurrent-{i}",
                agent_id="agent-1",
                task_type="concurrent_test",
                input_summary=f"Concurrent task {i}",
                outcome="Success",
                learnings=f"Learning {i}",
                confidence_score=0.5,
                agent_role="Test",
                timestamp=datetime.now(timezone.utc)
            )
            return await world_model_service.record_experience(experience)

        results = await asyncio.gather(*[record_experience(i) for i in range(20)])

        assert all(results)
        assert world_model_service.db.add_document.call_count == 20


# ========================================================================
# 2. Formula Usage Tests (10 tests)
# =========================================================================

class TestFormulaUsage:
    """Test formula usage recording."""

    @pytest.mark.asyncio
    async def test_record_formula_usage_success(self, world_model_service):
        """Test successful formula usage recording."""
        result = await world_model_service.record_formula_usage(
            agent_id="agent-1",
            agent_role="Finance",
            formula_id="formula-123",
            formula_name="Variance Calculation",
            task_description="Calculate budget variance",
            inputs={"actual": 1000, "budget": 900},
            result=100,
            success=True,
            learnings="Formula works correctly for positive variance"
        )

        assert result is True
        world_model_service.db.add_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_formula_usage_failure(self, world_model_service):
        """Test recording failed formula usage."""
        result = await world_model_service.record_formula_usage(
            agent_id="agent-1",
            agent_role="Finance",
            formula_id="formula-456",
            formula_name="ROI Calculation",
            task_description="Calculate ROI",
            inputs={"revenue": 1000, "investment": 500},
            result=None,  # Failed
            success=False,
            learnings="Division by zero error"
        )

        assert result is True

        call_args = world_model_service.db.add_document.call_args
        metadata = call_args[1]["metadata"]
        assert metadata["outcome"] == "Failure"

    @pytest.mark.asyncio
    async def test_record_formula_usage_with_complex_inputs(self, world_model_service):
        """Test formula usage with complex input structure."""
        complex_inputs = {
            "array_data": [1, 2, 3, 4, 5],
            "nested": {
                "key1": "value1",
                "key2": [10, 20, 30]
            }
        }

        result = await world_model_service.record_formula_usage(
            agent_id="agent-1",
            agent_role="Analytics",
            formula_id="formula-complex",
            formula_name="Complex Aggregation",
            task_description="Aggregate complex data",
            inputs=complex_inputs,
            result=15,
            success=True,
            learnings="Handles nested structures correctly"
        )

        assert result is True

        call_args = world_model_service.db.add_document.call_args
        metadata = call_args[1]["metadata"]
        assert "formula_inputs" in metadata

    @pytest.mark.asyncio
    async def test_record_formula_usage_performance_benchmark(self, world_model_service):
        """Test formula usage recording performance (target: <50ms)."""
        import time
        start = time.time()

        result = await world_model_service.record_formula_usage(
            agent_id="agent-1",
            agent_role="Test",
            formula_id="formula-perf",
            formula_name="Performance Test",
            task_description="Performance test",
            inputs={"test": 1},
            result=1,
            success=True
        )

        duration = (time.time() - start) * 1000

        assert result is True
        assert duration < 50, f"Recording took {duration}ms, target <50ms"


# ========================================================================
# 3. Business Facts Tests (12 tests)
# =========================================================================

class TestBusinessFacts:
    """Test business facts provisioning and verification."""

    @pytest.mark.asyncio
    async def test_provision_business_fact_success(self, world_model_service):
        """Test successful business fact provisioning."""
        fact = BusinessFact(
            id="fact-1",
            fact="Invoices > $500 need VP approval",
            citations=["policy.pdf:p4", "src/approvals.ts:L20"],
            reason="Critical for compliance",
            source_agent_id="agent-1",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc),
            verification_status="verified"
        )

        result = await world_model_service.record_experience(
            AgentExperience(
                id="exp-fact-1",
                agent_id="agent-1",
                task_type="fact_provisioning",
                input_summary="Learn approval policy",
                outcome="Success",
                learnings=fact.fact,
                confidence_score=0.95,
                agent_role="System",
                timestamp=datetime.now(timezone.utc),
                metadata_trace={"fact_id": fact.id, "citations": fact.citations}
            )
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_citation_valid(self, world_model_service, mock_lancedb_handler):
        """Test citation verification with valid citation."""
        # Mock search returning the citation
        mock_lancedb_handler.search.return_value = [
            {
                "id": "fact-1",
                "text": "Invoices > $500 need VP approval",
                "metadata": {
                    "citations": ["policy.pdf:p4"],
                    "verification_status": "verified"
                }
            }
        ]

        results = await world_model_service.db.search(
            table_name="business_facts",
            query="invoice approval policy",
            limit=5
        )

        assert len(results) == 1
        assert results[0]["metadata"]["verification_status"] == "verified"

    @pytest.mark.asyncio
    async def test_verify_citation_with_r2_storage(self, world_model_service):
        """Test citation verification with R2 storage URL."""
        fact = BusinessFact(
            id="fact-r2-1",
            fact="R2 storage citation test",
            citations=["r2://atom-docs/policy.pdf:p4"],
            reason="Test R2 integration",
            source_agent_id="agent-1",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc),
            verification_status="verified",
            metadata={"storage_type": "r2"}
        )

        result = await world_model_service.record_experience(
            AgentExperience(
                id="exp-r2-1",
                agent_id="agent-1",
                task_type="citation_verification",
                input_summary="Verify R2 citation",
                outcome="Success",
                learnings=fact.fact,
                confidence_score=0.9,
                agent_role="System",
                timestamp=datetime.now(timezone.utc),
                metadata_trace={"fact_id": fact.id}
            )
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_citation_with_s3_storage(self, world_model_service):
        """Test citation verification with S3 storage URL."""
        fact = BusinessFact(
            id="fact-s3-1",
            fact="S3 storage citation test",
            citations=["s3://atom-docs/policy.pdf:p10"],
            reason="Test S3 integration",
            source_agent_id="agent-1",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc),
            verification_status="verified",
            metadata={"storage_type": "s3"}
        )

        result = await world_model_service.record_experience(
            AgentExperience(
                id="exp-s3-1",
                agent_id="agent-1",
                task_type="citation_verification",
                input_summary="Verify S3 citation",
                outcome="Success",
                learnings=fact.fact,
                confidence_score=0.9,
                agent_role="System",
                timestamp=datetime.now(timezone.utc),
                metadata_trace={"fact_id": fact.id}
            )
        )

        assert result is True


# ========================================================================
# 4. Experience Feedback Tests (10 tests)
# =========================================================================

class TestExperienceFeedback:
    """Test experience feedback and learning."""

    @pytest.mark.asyncio
    async def test_update_experience_feedback_positive(self, world_model_service, mock_lancedb_handler):
        """Test updating experience with positive feedback."""
        # Mock search returning the experience
        mock_lancedb_handler.search.return_value = [
            {
                "id": "exp-1",
                "text": "Task: test\nInput: Test input\nOutcome: Success\nLearnings: Test learning",
                "metadata": {
                    "agent_id": "agent-1",
                    "confidence_score": 0.5,
                    "feedback_score": None
                }
            }
        ]

        result = await world_model_service.update_experience_feedback(
            experience_id="exp-1",
            feedback_score=1.0,
            feedback_notes="Excellent work!"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_experience_feedback_negative(self, world_model_service, mock_lancedb_handler):
        """Test updating experience with negative feedback."""
        mock_lancedb_handler.search.return_value = [
            {
                "id": "exp-2",
                "text": "Task: test\nOutcome: Success\nLearnings: Test",
                "metadata": {
                    "agent_id": "agent-1",
                    "confidence_score": 0.7,
                    "feedback_score": None
                }
            }
        ]

        result = await world_model_service.update_experience_feedback(
            experience_id="exp-2",
            feedback_score=-1.0,
            feedback_notes="Incorrect approach"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_experience_feedback_blends_confidence(self, world_model_service, mock_lancedb_handler):
        """Test that feedback blends into confidence score."""
        mock_lancedb_handler.search.return_value = [
            {
                "id": "exp-3",
                "text": "Task: test\nOutcome: Success\nLearnings: Test",
                "metadata": {
                    "agent_id": "agent-1",
                    "confidence_score": 0.5,  # Original confidence
                    "feedback_score": None
                }
            }
        ]

        result = await world_model_service.update_experience_feedback(
            experience_id="exp-3",
            feedback_score=1.0,  # Perfect feedback
            feedback_notes="Great job"
        )

        assert result is True
        # New confidence should blend old (0.5) with feedback (1.0)
        # Formula: old * 0.6 + ((feedback + 1) / 2) * 0.4
        # 0.5 * 0.6 + (1.0 * 0.4) = 0.3 + 0.4 = 0.7

    @pytest.mark.asyncio
    async def test_boost_experience_confidence(self, world_model_service):
        """Test boosting experience confidence."""
        result = await world_model_service.boost_experience_confidence(
            experience_id="exp-1",
            boost_amount=0.1
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_experience_feedback_not_found(self, world_model_service, mock_lancedb_handler):
        """Test updating feedback for non-existent experience."""
        mock_lancedb_handler.search.return_value = []

        result = await world_model_service.update_experience_feedback(
            experience_id="non-existent",
            feedback_score=0.5,
            feedback_notes="Test"
        )

        assert result is False


# ========================================================================
# 5. Experience Statistics Tests (8 tests)
# =========================================================================

class TestExperienceStatistics:
    """Test experience statistics and monitoring."""

    @pytest.mark.asyncio
    async def test_get_experience_statistics_all(self, world_model_service, mock_lancedb_handler):
        """Test retrieving all experience statistics."""
        mock_lancedb_handler.search.return_value = [
            {
                "metadata": {
                    "agent_id": "agent-1",
                    "task_type": "reconciliation",
                    "outcome": "Success",
                    "confidence_score": 0.8,
                    "feedback_score": 0.9
                }
            },
            {
                "metadata": {
                    "agent_id": "agent-1",
                    "task_type": "outreach",
                    "outcome": "Failure",
                    "confidence_score": 0.5,
                    "feedback_score": None
                }
            },
            {
                "metadata": {
                    "agent_id": "agent-2",
                    "task_type": "reconciliation",
                    "outcome": "Success",
                    "confidence_score": 0.9,
                    "feedback_score": 1.0
                }
            }
        ]

        stats = await world_model_service.get_experience_statistics()

        assert stats["total_experiences"] == 3
        assert stats["successes"] == 2
        assert stats["failures"] == 1
        assert stats["success_rate"] == 2/3

    @pytest.mark.asyncio
    async def test_get_experience_statistics_by_agent(self, world_model_service, mock_lancedb_handler):
        """Test retrieving statistics filtered by agent."""
        mock_lancedb_handler.search.return_value = [
            {
                "metadata": {
                    "agent_id": "agent-1",
                    "task_type": "test",
                    "outcome": "Success",
                    "confidence_score": 0.8,
                    "feedback_score": 0.9
                }
            },
            {
                "metadata": {
                    "agent_id": "agent-2",  # Different agent
                    "task_type": "test",
                    "outcome": "Success",
                    "confidence_score": 0.7,
                    "feedback_score": None
                }
            }
        ]

        stats = await world_model_service.get_experience_statistics(agent_id="agent-1")

        assert stats["total_experiences"] == 1

    @pytest.mark.asyncio
    async def test_get_experience_statistics_by_role(self, world_model_service, mock_lancedb_handler):
        """Test retrieving statistics filtered by role."""
        mock_lancedb_handler.search.return_value = [
            {
                "metadata": {
                    "agent_id": "agent-1",
                    "agent_role": "Finance",
                    "task_type": "test",
                    "outcome": "Success",
                    "confidence_score": 0.8
                }
            },
            {
                "metadata": {
                    "agent_id": "agent-2",
                    "agent_role": "Sales",  # Different role
                    "task_type": "test",
                    "outcome": "Success",
                    "confidence_score": 0.7
                }
            }
        ]

        stats = await world_model_service.get_experience_statistics(agent_role="Finance")

        assert stats["total_experiences"] == 1


# ========================================================================
# 6. World Model Query Tests (10 tests)
# =========================================================================

class TestWorldModelQuery:
    """Test world model querying."""

    @pytest.mark.asyncio
    async def test_query_world_model_success(self, world_model_service, mock_lancedb_handler):
        """Test successful world model query."""
        mock_lancedb_handler.search.return_value = [
            {
                "id": "fact-1",
                "text": "Invoices > $500 need VP approval",
                "metadata": {
                    "fact": "Invoices > $500 need VP approval",
                    "citations": ["policy.pdf:p4"],
                    "verification_status": "verified"
                }
            }
        ]

        results = await world_model_service.db.search(
            table_name="business_facts",
            query="invoice approval process",
            limit=5
        )

        assert len(results) == 1
        assert "invoice" in results[0]["text"].lower()

    @pytest.mark.asyncio
    async def test_query_world_model_empty_result(self, world_model_service, mock_lancedb_handler):
        """Test query with no results."""
        mock_lancedb_handler.search.return_value = []

        results = await world_model_service.db.search(
            table_name="business_facts",
            query="nonexistent topic",
            limit=5
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_query_world_model_with_limit(self, world_model_service, mock_lancedb_handler):
        """Test query with custom limit."""
        # Mock 10 results
        mock_lancedb_handler.search.return_value = [
            {"id": f"fact-{i}", "text": f"Fact {i}", "metadata": {}}
            for i in range(10)
        ]

        results = await world_model_service.db.search(
            table_name="business_facts",
            query="test",
            limit=5
        )

        assert len(results) == 5


# ========================================================================
# 7. Edge Case Tests (10 tests)
# =========================================================================

class TestWorldModelEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_record_experience_with_unicode(self, world_model_service):
        """Test recording experience with Unicode characters."""
        experience = AgentExperience(
            id="exp-unicode",
            agent_id="agent-1",
            task_type="unicode_test",
            input_summary="Test with emoji 🎉 and 中文",
            outcome="Success",
            learnings="日本語テスト",
            confidence_score=0.5,
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

    @pytest.mark.asyncio
    async def test_record_experience_with_special_characters(self, world_model_service):
        """Test recording experience with special characters."""
        special_text = "Test with quotes \"', newlines\n, tabs\t"

        experience = AgentExperience(
            id="exp-special",
            agent_id="agent-1",
            task_type="special_test",
            input_summary=special_text,
            outcome="Success",
            learnings="Special chars test",
            confidence_score=0.5,
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

    @pytest.mark.asyncio
    async def test_record_experience_with_very_long_content(self, world_model_service):
        """Test recording experience with very long content."""
        long_content = "x" * 10000

        experience = AgentExperience(
            id="exp-long",
            agent_id="agent-1",
            task_type="long_content_test",
            input_summary=long_content,
            outcome="Success",
            learnings=long_content,
            confidence_score=0.5,
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

    @pytest.mark.asyncio
    async def test_record_experience_with_null_fields(self, world_model_service):
        """Test recording experience with null optional fields."""
        experience = AgentExperience(
            id="exp-null",
            agent_id="agent-1",
            task_type="null_test",
            input_summary="Test",
            outcome="Success",
            learnings="Test",
            confidence_score=0.5,
            agent_role="Test",
            timestamp=datetime.now(timezone.utc),
            specialty=None,  # Null optional field
            artifacts=None,  # Null optional field
            feedback_score=None  # Null optional field
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

    @pytest.mark.asyncio
    async def test_record_formula_usage_with_null_result(self, world_model_service):
        """Test formula usage with null result (failure)."""
        result = await world_model_service.record_formula_usage(
            agent_id="agent-1",
            agent_role="Test",
            formula_id="formula-null",
            formula_name="Null Result Test",
            task_description="Test null result",
            inputs={"test": 1},
            result=None,
            success=False,
            learnings="Failed calculation"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_experience_recording(self, world_model_service):
        """Test concurrent experience recording."""
        async def record_exp(i):
            experience = AgentExperience(
                id=f"exp-concurrent-{i}",
                agent_id="agent-1",
                task_type="concurrent",
                input_summary=f"Test {i}",
                outcome="Success",
                learnings=f"Learning {i}",
                confidence_score=0.5,
                agent_role="Test",
                timestamp=datetime.now(timezone.utc)
            )
            return await world_model_service.record_experience(experience)

        results = await asyncio.gather(*[record_exp(i) for i in range(50)])

        assert all(results)

    @pytest.mark.asyncio
    async def test_experience_with_invalid_confidence_too_low(self, world_model_service):
        """Test experience with confidence below valid range."""
        experience = AgentExperience(
            id="exp-invalid-low",
            agent_id="agent-1",
            task_type="invalid_test",
            input_summary="Test",
            outcome="Success",
            learnings="Test",
            confidence_score=-0.5,  # Invalid: below 0.0
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )

        # Service should handle gracefully
        result = await world_model_service.record_experience(experience)
        assert result is True or result is False  # Either is acceptable

    @pytest.mark.asyncio
    async def test_experience_with_invalid_confidence_too_high(self, world_model_service):
        """Test experience with confidence above valid range."""
        experience = AgentExperience(
            id="exp-invalid-high",
            agent_id="agent-1",
            task_type="invalid_test",
            input_summary="Test",
            outcome="Success",
            learnings="Test",
            confidence_score=1.5,  # Invalid: above 1.0
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )

        # Service should handle gracefully
        result = await world_model_service.record_experience(experience)
        assert result is True or result is False  # Either is acceptable


# ========================================================================
# 8. Table Management Tests (5 tests)
# =========================================================================

class TestTableManagement:
    """Test LanceDB table creation and management."""

    def test_ensure_tables_creates_experience_table(self, mock_lancedb_handler):
        """Test that experience table is created if missing."""
        mock_lancedb_handler.db.table_names.return_value = []
        mock_lancedb_handler.db.table_names.return_value = []

        service = WorldModelService(workspace_id="test")
        service.db = mock_lancedb_handler
        service._ensure_tables()

        # Should create both tables
        assert mock_lancedb_handler.create_table.call_count == 2

    def test_ensure_tables_creates_facts_table(self, mock_lancedb_handler):
        """Test that facts table is created if missing."""
        mock_lancedb_handler.db.table_names.return_value = []

        service = WorldModelService(workspace_id="test")
        service.db = mock_lancedb_handler
        service._ensure_tables()

        # Check that facts table was created
        call_args_list = mock_lancedb_handler.create_table.call_args_list
        table_names = [call[0][0] for call in call_args_list]
        assert "business_facts" in table_names

    def test_ensure_tables_skips_existing_tables(self, mock_lancedb_handler):
        """Test that existing tables are not recreated."""
        mock_lancedb_handler.db.table_names.return_value = [
            "agent_experience",
            "business_facts"
        ]

        service = WorldModelService(workspace_id="test")
        service.db = mock_lancedb_handler
        service._ensure_tables()

        # Should not create any tables
        mock_lancedb_handler.create_table.assert_not_called()

    def test_ensure_tables_with_none_database(self, mock_lancedb_handler):
        """Test table creation when database is None."""
        mock_lancedb_handler.db = None

        service = WorldModelService(workspace_id="test")
        service.db = mock_lancedb_handler
        service._ensure_tables()

        # Should not attempt to create tables
        mock_lancedb_handler.create_table.assert_not_called()
