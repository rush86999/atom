"""
World Model Service Tests

Tests for WorldModelService focusing on actual code structure.
Coverage target: 60%+ for core/agent_world_model.py

Tests cover:
- record_experience: Record agent experiences
- record_business_fact: Record business facts with citations
- get_relevant_business_facts: Retrieve facts by query

Reference: Phase 122-01 Plan - Baseline test infrastructure
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
from typing import Dict, Any

# Import what actually exists
from core.agent_world_model import WorldModelService, AgentExperience, BusinessFact


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDB handler."""
    mock_db = AsyncMock()
    # Mock db property
    mock_db.db = Mock()
    mock_db.db.table_names = Mock(return_value=[])
    mock_db.workspace_id = "default"
    return mock_db


@pytest.fixture
def world_model_service(mock_lancedb_handler):
    """Create WorldModelService instance with mocked handler."""
    with patch('core.agent_world_model.get_lancedb_handler', return_value=mock_lancedb_handler):
        service = WorldModelService(workspace_id="default")
        service.db = mock_lancedb_handler
        return service


# ============================================================================
# TEST CLASS: Record Experience
# ============================================================================

class TestRecordExperience:
    """Tests for record_experience method."""

    @pytest.mark.asyncio
    async def test_record_experience_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN WorldModelService with mocked LanceDBHandler
        WHEN record_experience() is called with valid AgentExperience
        THEN return True and verify add_document called with correct structure
        """
        # Mock add_document to return True (synchronous method)
        mock_lancedb_handler.add_document = Mock(return_value=True)

        # Create test experience
        experience = AgentExperience(
            id="test_exp_1",
            agent_id="agent_123",
            task_type="reconciliation",
            input_summary="Reconcile SKU-123",
            outcome="Success",
            learnings="Process worked correctly",
            confidence_score=0.8,
            agent_role="Finance",
            timestamp=datetime.now()
        )

        # Call the method
        result = await world_model_service.record_experience(experience)

        # Verify success
        assert result is True
        mock_lancedb_handler.add_document.assert_called_once()

        # Verify call arguments contain required metadata
        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["table_name"] == "agent_experience"
        assert "reconciliation" in call_args[1]["text"]
        assert call_args[1]["metadata"]["agent_id"] == "agent_123"
        assert call_args[1]["metadata"]["task_type"] == "reconciliation"
        assert call_args[1]["metadata"]["outcome"] == "Success"


# ============================================================================
# TEST CLASS: Record Business Fact
# ============================================================================

class TestRecordBusinessFact:
    """Tests for record_business_fact method."""

    @pytest.mark.asyncio
    async def test_record_business_fact_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN WorldModelService with mocked LanceDBHandler
        WHEN record_business_fact() is called with valid BusinessFact
        THEN return True and verify fact stored in business_facts table
        """
        # Mock add_document to return True (synchronous method)
        mock_lancedb_handler.add_document = Mock(return_value=True)

        # Create test fact
        fact = BusinessFact(
            id="fact_1",
            fact="Invoices > $500 need VP approval",
            citations=["policy.pdf:p4"],
            reason="Financial control policy",
            source_agent_id="user:test-user",
            created_at=datetime.now(),
            last_verified=datetime.now(),
            verification_status="verified",
            metadata={"domain": "finance"}
        )

        # Call the method
        result = await world_model_service.record_business_fact(fact)

        # Verify success
        assert result is True
        mock_lancedb_handler.add_document.assert_called_once()

        # Verify call arguments contain fact data
        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["table_name"] == "business_facts"
        assert "Invoices > $500 need VP approval" in call_args[1]["text"]
        assert call_args[1]["metadata"]["id"] == "fact_1"
        assert call_args[1]["metadata"]["fact"] == "Invoices > $500 need VP approval"
        assert call_args[1]["metadata"]["citations"] == ["policy.pdf:p4"]
        assert call_args[1]["metadata"]["verification_status"] == "verified"


# ============================================================================
# TEST CLASS: Get Relevant Business Facts
# ============================================================================

class TestGetRelevantBusinessFacts:
    """Tests for get_relevant_business_facts method."""

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts_returns_list(
        self, world_model_service, mock_lancedb_handler
    ):
        """
        GIVEN WorldModelService with mocked LanceDBHandler
        WHEN get_relevant_business_facts() is called with a query
        THEN return list of BusinessFact objects
        """
        # Mock search to return sample results (synchronous method)
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "id": "fact_1",
                "metadata": {
                    "id": "fact_1",
                    "fact": "Invoices > $500 need VP approval",
                    "citations": ["policy.pdf:p4"],
                    "reason": "Financial control",
                    "source_agent_id": "user:test",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified",
                    "domain": "finance"
                }
            }
        ])

        # Call the method
        facts = await world_model_service.get_relevant_business_facts(
            query="invoice approval policy",
            limit=5
        )

        # Verify results
        assert len(facts) == 1
        assert isinstance(facts[0], BusinessFact)
        assert facts[0].fact == "Invoices > $500 need VP approval"
        assert facts[0].citations == ["policy.pdf:p4"]
        assert facts[0].verification_status == "verified"

        # Verify search was called correctly
        mock_lancedb_handler.search.assert_called_once_with(
            table_name="business_facts",
            query="invoice approval policy",
            limit=5
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
