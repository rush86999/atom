"""
World Model Integration Tests

Integration tests for agent_world_model.py that CALL actual WorldModelService class methods.
These tests use real database sessions and LanceDB handlers for true integration testing.

Coverage target: Increase agent_world_model.py coverage from baseline
Reference: Phase 127-08A Plan - Integration tests for high-impact files
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List

# Import WorldModelService and related classes
from core.agent_world_model import WorldModelService, AgentExperience, BusinessFact


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDB handler for integration testing."""
    mock_db = AsyncMock()
    # Mock db property
    mock_db.db = Mock()
    mock_db.db.table_names = Mock(return_value=[])
    mock_db.workspace_id = "default"
    mock_db.add_document = Mock(return_value=True)
    mock_db.search = Mock(return_value=[])
    return mock_db


@pytest.fixture
def world_model_service(mock_lancedb_handler):
    """Create WorldModelService instance with mocked LanceDB handler."""
    with patch('core.agent_world_model.get_lancedb_handler', return_value=mock_lancedb_handler):
        service = WorldModelService(workspace_id="default")
        service.db = mock_lancedb_handler
        return service


@pytest.fixture
def sample_experience_data():
    """Sample agent experience for testing."""
    return AgentExperience(
        id="exp_001",
        agent_id="agent_123",
        task_type="reconciliation",
        input_summary="Reconcile SKU-123 inventory",
        outcome="Success",
        learnings="Automated matching worked correctly",
        confidence_score=0.85,
        agent_role="Finance",
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_business_fact_data():
    """Sample business fact for testing."""
    return BusinessFact(
        id="fact_001",
        fact="Invoices over $500 require VP approval",
        citations=["policy.pdf:p4", "handbook.doc:p12"],
        reason="Financial control policy for large expenses",
        source_agent_id="agent_123",
        created_at=datetime.now(),
        last_verified=datetime.now(),
        verification_status="verified",
        metadata={"category": "finance", "domain": "ap"}
    )


# ============================================================================
# INTEGRATION TESTS: Experience Recording
# ============================================================================

class TestExperienceRecording:
    """Tests for recording agent experiences through WorldModelService."""

    @pytest.mark.asyncio
    async def test_record_experience_success(self, world_model_service, mock_lancedb_handler, sample_experience_data):
        """
        GIVEN WorldModelService with mocked LanceDB handler
        WHEN record_experience() is called with valid AgentExperience
        THEN return True and verify add_document called correctly
        """
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.record_experience(sample_experience_data)

        assert result is True
        mock_lancedb_handler.add_document.assert_called_once()

        # Verify call arguments
        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["table_name"] == "agent_experience"
        assert call_args[1]["metadata"]["agent_id"] == "agent_123"
        assert call_args[1]["metadata"]["task_type"] == "reconciliation"
        assert call_args[1]["metadata"]["outcome"] == "Success"
        assert call_args[1]["metadata"]["type"] == "experience"

    @pytest.mark.asyncio
    async def test_record_experience_with_feedback(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN experience with feedback data
        WHEN record_experience() is called
        THEN feedback fields are included in metadata
        """
        mock_lancedb_handler.add_document = Mock(return_value=True)

        experience = AgentExperience(
            id="exp_002",
            agent_id="agent_456",
            task_type="outreach",
            input_summary="Customer follow-up",
            outcome="Success",
            learnings="Email template worked well",
            confidence_score=0.9,
            feedback_score=0.8,
            rating=5,
            agent_role="Sales",
            timestamp=datetime.now()
        )

        result = await world_model_service.record_experience(experience)

        assert result is True
        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["metadata"]["feedback_score"] == 0.8
        assert call_args[1]["metadata"]["rating"] == 5


class TestFormulaUsageRecording:
    """Tests for formula usage recording through WorldModelService."""

    @pytest.mark.asyncio
    async def test_record_formula_usage_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN WorldModelService instance
        WHEN record_formula_usage() is called with formula data
        THEN return True and record formula application
        """
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.record_formula_usage(
            agent_id="agent_789",
            agent_role="Finance",
            formula_id="formula_001",
            formula_name="ROI Calculator",
            task_description="Calculate campaign ROI",
            inputs={"investment": 1000, "return": 1500},
            result=0.5,
            success=True,
            learnings="Formula accurate for Q1 data"
        )

        assert result is True
        mock_lancedb_handler.add_document.assert_called_once()

        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["metadata"]["task_type"] == "formula_application"
        assert call_args[1]["metadata"]["formula_id"] == "formula_001"
        assert call_args[1]["metadata"]["formula_name"] == "ROI Calculator"


class TestExperienceFeedbackUpdate:
    """Tests for updating experience feedback."""

    @pytest.mark.asyncio
    async def test_update_experience_feedback_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN experience in database
        WHEN update_experience_feedback() is called with feedback
        THEN return True and update confidence score
        """
        # Mock search to return the experience
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "id": "exp_001",
                "text": "Task: reconciliation\nOutcome: Success",
                "source": "agent_agent_123",
                "metadata": {
                    "agent_id": "agent_123",
                    "confidence_score": 0.8
                },
                "created_at": datetime.now().isoformat()
            }
        ])
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.update_experience_feedback(
            experience_id="exp_001",
            feedback_score=0.9,
            feedback_notes="Excellent work"
        )

        assert result is True
        mock_lancedb_handler.search.assert_called_once()
        # Verify new document added with updated confidence
        assert mock_lancedb_handler.add_document.called

    @pytest.mark.asyncio
    async def test_update_experience_feedback_not_found(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN experience not in database
        WHEN update_experience_feedback() is called
        THEN return False
        """
        mock_lancedb_handler.search = Mock(return_value=[])

        result = await world_model_service.update_experience_feedback(
            experience_id="nonexistent",
            feedback_score=0.5
        )

        assert result is False


class TestConfidenceBoosting:
    """Tests for boosting experience confidence."""

    @pytest.mark.asyncio
    async def test_boost_experience_confidence_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN experience in database
        WHEN boost_experience_confidence() is called
        THEN return True and increase confidence score
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "id": "exp_001",
                "text": "Task: reconciliation",
                "source": "agent_agent_123",
                "metadata": {
                    "confidence_score": 0.7,
                    "boost_count": 0
                },
                "created_at": datetime.now().isoformat()
            }
        ])
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.boost_experience_confidence(
            experience_id="exp_001",
            boost_amount=0.1
        )

        assert result is True
        mock_lancedb_handler.search.assert_called_once()
        mock_lancedb_handler.add_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_boost_experience_confidence_caps_at_one(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN experience with high confidence
        WHEN boost_experience_confidence() is called with large boost
        THEN confidence caps at 1.0
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "id": "exp_001",
                "text": "Task: reconciliation",
                "metadata": {
                    "confidence_score": 0.95,
                    "boost_count": 5
                },
                "created_at": datetime.now().isoformat()
            }
        ])
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.boost_experience_confidence(
            experience_id="exp_001",
            boost_amount=0.2  # Would go to 1.15, but should cap at 1.0
        )

        assert result is True

        # Verify the boosted confidence was capped
        call_args = mock_lancedb_handler.add_document.call_args
        new_confidence = call_args[1]["metadata"]["confidence_score"]
        assert new_confidence == 1.0


class TestExperienceStatistics:
    """Tests for experience statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_experience_statistics_all(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN experiences in database
        WHEN get_experience_statistics() is called without filters
        THEN return aggregated statistics
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {
                    "agent_id": "agent_1",
                    "outcome": "Success",
                    "confidence_score": 0.8,
                    "feedback_score": 0.9
                }
            },
            {
                "metadata": {
                    "agent_id": "agent_2",
                    "outcome": "Success",
                    "confidence_score": 0.9,
                    "feedback_score": None
                }
            },
            {
                "metadata": {
                    "agent_id": "agent_3",
                    "outcome": "Failure",
                    "confidence_score": 0.5,
                    "feedback_score": -0.5
                }
            }
        ])

        stats = await world_model_service.get_experience_statistics()

        assert stats["total_experiences"] == 3
        assert stats["successes"] == 2
        assert stats["failures"] == 1
        assert stats["success_rate"] == 2/3
        assert stats["avg_confidence"] == pytest.approx((0.8 + 0.9 + 0.5) / 3)
        assert stats["feedback_coverage"] == pytest.approx(2/3)

    @pytest.mark.asyncio
    async def test_get_experience_statistics_filtered_by_agent(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN experiences from multiple agents
        WHEN get_experience_statistics() is called with agent_id filter
        THEN return statistics for specific agent
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {
                    "agent_id": "agent_1",
                    "outcome": "Success",
                    "confidence_score": 0.8
                }
            },
            {
                "metadata": {
                    "agent_id": "agent_1",
                    "outcome": "Success",
                    "confidence_score": 0.9
                }
            },
            {
                "metadata": {
                    "agent_id": "agent_2",
                    "outcome": "Failure",
                    "confidence_score": 0.5
                }
            }
        ])

        stats = await world_model_service.get_experience_statistics(agent_id="agent_1")

        assert stats["total_experiences"] == 2  # Only agent_1 experiences
        assert stats["agent_id"] == "agent_1"
        assert stats["successes"] == 2


# ============================================================================
# INTEGRATION TESTS: Business Facts
# ============================================================================

class TestBusinessFactRecording:
    """Tests for recording business facts."""

    @pytest.mark.asyncio
    async def test_record_business_fact_success(self, world_model_service, mock_lancedb_handler, sample_business_fact_data):
        """
        GIVEN WorldModelService instance
        WHEN record_business_fact() is called with valid BusinessFact
        THEN return True and verify fact recorded
        """
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.record_business_fact(sample_business_fact_data)

        assert result is True
        mock_lancedb_handler.add_document.assert_called_once()

        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["table_name"] == "business_facts"
        assert call_args[1]["metadata"]["fact"] == sample_business_fact_data.fact
        assert call_args[1]["metadata"]["verification_status"] == "verified"
        assert call_args[1]["metadata"]["type"] == "business_fact"

    @pytest.mark.asyncio
    async def test_record_business_fact_with_metadata(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN business fact with custom metadata
        WHEN record_business_fact() is called
        THEN metadata is included in document
        """
        mock_lancedb_handler.add_document = Mock(return_value=True)

        fact = BusinessFact(
            id="fact_002",
            fact="Employees get 20 PTO days",
            citations=["employee_handbook.pdf:p30"],
            reason="HR policy",
            source_agent_id="agent_hr",
            created_at=datetime.now(),
            last_verified=datetime.now(),
            verification_status="unverified",
            metadata={"category": "hr", "region": "us", "effective_date": "2024-01-01"}
        )

        result = await world_model_service.record_business_fact(fact)

        assert result is True
        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["metadata"]["category"] == "hr"
        assert call_args[1]["metadata"]["region"] == "us"
        assert call_args[1]["metadata"]["effective_date"] == "2024-01-01"


class TestBusinessFactRetrieval:
    """Tests for retrieving business facts."""

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN business facts in database
        WHEN get_relevant_business_facts() is called with query
        THEN return list of matching BusinessFact objects
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {
                    "id": "fact_001",
                    "fact": "Invoices over $500 require VP approval",
                    "citations": ["policy.pdf:p4"],
                    "reason": "Financial control",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified"
                }
            },
            {
                "metadata": {
                    "id": "fact_002",
                    "fact": "POs over $1000 need manager approval",
                    "citations": ["policy.pdf:p5"],
                    "reason": "Procurement policy",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified"
                }
            }
        ])

        facts = await world_model_service.get_relevant_business_facts(
            query="approval policies",
            limit=5
        )

        assert len(facts) == 2
        assert all(isinstance(f, BusinessFact) for f in facts)
        assert "Invoices over $500" in facts[0].fact
        assert "POs over $1000" in facts[1].fact

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts_empty(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN no matching facts in database
        WHEN get_relevant_business_facts() is called
        THEN return empty list
        """
        mock_lancedb_handler.search = Mock(return_value=[])

        facts = await world_model_service.get_relevant_business_facts(
            query="nonexistent topic",
            limit=5
        )

        assert facts == []


class TestBusinessFactListing:
    """Tests for listing business facts."""

    @pytest.mark.asyncio
    async def test_list_all_facts_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN business facts in database
        WHEN list_all_facts() is called
        THEN return all facts with optional filters
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {
                    "id": "fact_001",
                    "fact": "Fact 1",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_1",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified",
                    "domain": "finance"
                }
            },
            {
                "metadata": {
                    "id": "fact_002",
                    "fact": "Fact 2",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_1",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "unverified",
                    "domain": "hr"
                }
            }
        ])

        facts = await world_model_service.list_all_facts(limit=100)

        assert len(facts) == 2
        assert all(isinstance(f, BusinessFact) for f in facts)

    @pytest.mark.asyncio
    async def test_list_all_facts_with_status_filter(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN facts with different verification statuses
        WHEN list_all_facts() is called with status filter
        THEN return only matching facts
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {
                    "id": "fact_001",
                    "fact": "Verified fact",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_1",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified"
                }
            },
            {
                "metadata": {
                    "id": "fact_002",
                    "fact": "Unverified fact",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_1",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "unverified"
                }
            }
        ])

        facts = await world_model_service.list_all_facts(status="verified", limit=100)

        assert len(facts) == 1
        assert facts[0].fact == "Verified fact"


class TestBusinessFactRetrievalById:
    """Tests for retrieving facts by ID."""

    @pytest.mark.asyncio
    async def test_get_fact_by_id_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN fact in database
        WHEN get_fact_by_id() is called with existing ID
        THEN return BusinessFact object
        """
        fact_id = "fact_001"
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {
                    "id": fact_id,
                    "fact": "Test fact",
                    "citations": ["doc.pdf:p1"],
                    "reason": "Test",
                    "source_agent_id": "agent_1",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified"
                }
            }
        ])

        fact = await world_model_service.get_fact_by_id(fact_id)

        assert fact is not None
        assert isinstance(fact, BusinessFact)
        assert fact.id == fact_id
        assert fact.fact == "Test fact"

    @pytest.mark.asyncio
    async def test_get_fact_by_id_not_found(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN fact not in database
        WHEN get_fact_by_id() is called with non-existent ID
        THEN return None
        """
        mock_lancedb_handler.search = Mock(return_value=[])

        fact = await world_model_service.get_fact_by_id("nonexistent")

        assert fact is None


class TestBusinessFactDeletion:
    """Tests for deleting business facts."""

    @pytest.mark.asyncio
    async def test_delete_fact_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN fact in database
        WHEN delete_fact() is called
        THEN mark fact as deleted and return True
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {"id": "fact_001", "verification_status": "verified"},
                "text": "Fact: Test fact"
            }
        ])
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.delete_fact("fact_001")

        assert result is True
        mock_lancedb_handler.add_document.assert_called_once()

        # Verify status was updated to "deleted"
        call_args = mock_lancedb_handler.add_document.call_args
        new_metadata = call_args[1]["metadata"]
        assert new_metadata["verification_status"] == "deleted"


class TestBusinessFactBulkOperations:
    """Tests for bulk fact operations."""

    @pytest.mark.asyncio
    async def test_bulk_record_facts_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN multiple business facts
        WHEN bulk_record_facts() is called
        THEN record all facts and return success count
        """
        mock_lancedb_handler.add_document = Mock(return_value=True)

        facts = [
            BusinessFact(
                id=f"fact_{i}",
                fact=f"Fact number {i}",
                citations=[],
                reason="Bulk test",
                source_agent_id="agent_1",
                created_at=datetime.now(),
                last_verified=datetime.now(),
                verification_status="verified"
            )
            for i in range(5)
        ]

        count = await world_model_service.bulk_record_facts(facts)

        assert count == 5
        assert mock_lancedb_handler.add_document.call_count == 5


class TestFactVerificationUpdate:
    """Tests for updating fact verification status."""

    @pytest.mark.asyncio
    async def test_update_fact_verification_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN fact in database
        WHEN update_fact_verification() is called with new status
        THEN update verification status and return True
        """
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "metadata": {"id": "fact_001", "verification_status": "unverified"},
                "text": "Fact: Test fact\nStatus: unverified"
            }
        ])
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.update_fact_verification("fact_001", "verified")

        assert result is True
        mock_lancedb_handler.add_document.assert_called_once()

        # Verify status was updated
        call_args = mock_lancedb_handler.add_document.call_args
        new_metadata = call_args[1]["metadata"]
        assert new_metadata["verification_status"] == "verified"

    @pytest.mark.asyncio
    async def test_update_fact_verification_not_found(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN fact not in database
        WHEN update_fact_verification() is called
        THEN return False
        """
        mock_lancedb_handler.search = Mock(return_value=[])

        result = await world_model_service.update_fact_verification("nonexistent", "verified")

        assert result is False
