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


# ============================================================================
# TEST CLASS: List All Facts
# ============================================================================

class TestListAllFacts:
    """Tests for list_all_facts method."""

    @pytest.mark.asyncio
    async def test_list_all_facts_returns_list(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN WorldModelService with mocked LanceDBHandler
        WHEN list_all_facts() is called
        THEN return list of all BusinessFact objects
        """
        # Mock search to return results
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "id": "fact_1",
                "metadata": {
                    "id": "fact_1",
                    "fact": "Invoice rule",
                    "citations": ["policy.pdf"],
                    "reason": "Finance",
                    "source_agent_id": "agent:1",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified",
                    "domain": "finance"
                }
            }
        ])

        facts = await world_model_service.list_all_facts()

        assert len(facts) == 1
        assert isinstance(facts[0], BusinessFact)
        assert facts[0].fact == "Invoice rule"


# ============================================================================
# TEST CLASS: Get Fact By ID
# ============================================================================

class TestGetFactById:
    """Tests for get_fact_by_id method."""

    @pytest.mark.asyncio
    async def test_get_fact_by_id_success(self, world_model_service, mock_lancedb_handler):
        """
        GIVEN fact exists
        WHEN get_fact_by_id() is called
        THEN return the BusinessFact object
        """
        fact_id = "fact-123"
        mock_lancedb_handler.search = Mock(return_value=[
            {
                "id": fact_id,
                "metadata": {
                    "id": fact_id,
                    "fact": "Test fact",
                    "citations": ["test.pdf"],
                    "reason": "Test",
                    "source_agent_id": "agent:1",
                    "created_at": datetime.now().isoformat(),
                    "last_verified": datetime.now().isoformat(),
                    "verification_status": "verified",
                    "domain": "test"
                }
            }
        ])

        fact = await world_model_service.get_fact_by_id(fact_id)

        assert fact is not None
        assert fact.id == fact_id
        assert fact.fact == "Test fact"


# ============================================================================
# TEST CLASS: Update Fact Verification
# ============================================================================

class TestUpdateFactVerification:
    """Tests for fact verification status updates."""

    @pytest.mark.asyncio
    async def test_update_fact_verification_success(self, mock_lancedb_handler):
        """
        GIVEN business fact exists
        WHEN update_fact_verification() is called with new status
        THEN update verification_status and last_verified
        """
        from core.agent_world_model import WorldModelService

        # Mock LanceDB
        mock_lancedb = AsyncMock()
        mock_lancedb.search.return_value = [
            {
                "id": "fact-1",
                "text": "Fact: Test\nStatus: unverified",
                "metadata": {"id": "fact-1", "verification_status": "unverified"},
                "source": "fact_agent_1"
            }
        ]
        mock_lancedb.add_document.return_value = True
        mock_lancedb_handler.return_value = mock_lancedb

        service = WorldModelService()
        result = await service.update_fact_verification("fact-1", "verified")

        assert result is True


# ============================================================================
# TEST CLASS: Recall Experiences (Integration Tests)
# ============================================================================

class TestRecallExperiences:
    """Integration tests for recall_experiences() multi-source memory aggregation."""

    @pytest.mark.asyncio
    async def test_recall_experiences_returns_empty_dict_when_no_data(
        self, world_model_service, mock_lancedb_handler
    ):
        """
        GIVEN WorldModelService with mocked LanceDBHandler
        WHEN recall_experiences() is called with agent and all sources return empty
        THEN return dict with 7 keys, all empty lists/strings
        """
        # Mock agent with category "Finance"
        agent = Mock()
        agent.id = "agent_finance_1"
        agent.name = "Finance Agent"
        agent.category = "Finance"
        agent.status = "autonomous"

        # Mock all 5 search sources to return empty results
        mock_lancedb_handler.search = Mock(return_value=[])

        # Mock other dependencies to return empty
        with patch('core.graphrag_engine.graphrag_engine') as mock_graphrag, \
             patch('core.formula_memory.get_formula_manager') as mock_formula_mgr, \
             patch('core.agent_world_model.get_db_session') as mock_get_db, \
             patch('core.episode_retrieval_service.EpisodeRetrievalService') as mock_episode_svc:

            # GraphRAG returns empty string
            mock_graphrag.get_context_for_ai.return_value = ""

            # Formula manager returns empty list
            mock_formula_mgr.return_value.search_formulas.return_value = []

            # Database query returns empty conversation list
            mock_db = AsyncMock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_get_db.return_value.__enter__.return_value = mock_db

            # Episode service returns empty list
            mock_episode_svc.return_value.retrieve_contextual.return_value = {"episodes": []}

            # Call the method
            result = await world_model_service.recall_experiences(
                agent=agent,
                current_task_description="Reconcile invoice discrepancies",
                limit=5
            )

            # Verify return structure
            assert isinstance(result, dict)
            assert "experiences" in result
            assert "knowledge" in result
            assert "knowledge_graph" in result
            assert "formulas" in result
            assert "conversations" in result
            assert "business_facts" in result
            assert "episodes" in result

            # Verify all lists are empty
            assert result["experiences"] == []
            assert result["knowledge"] == []
            assert result["knowledge_graph"] == ""
            assert result["formulas"] == []
            assert result["conversations"] == []
            assert result["business_facts"] == []
            assert result["episodes"] == []

    @pytest.mark.asyncio
    async def test_recall_experiences_aggregates_experiences_with_role_scoping(
        self, world_model_service, mock_lancedb_handler
    ):
        """
        GIVEN WorldModelService with mocked LanceDBHandler
        WHEN recall_experiences() is called with Finance agent
        THEN only role-matched and creator-matched experiences returned, sorted by confidence
        """
        # Mock agent with category "Finance"
        agent = Mock()
        agent.id = "agent_finance_123"
        agent.name = "Finance Agent"
        agent.category = "Finance"
        agent.status = "autonomous"

        # Track call count to return different data
        call_count = [0]

        def search_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First call: agent_experience table
                return [
                    {
                        "id": "exp_1",
                        "text": "Task: reconciliation\nInput: Reconcile SKU-123\nOutcome: Success\nLearnings: Process worked",
                        "created_at": datetime.now().isoformat(),
                        "metadata": {
                            "agent_id": "agent_finance_123",  # Creator match
                            "task_type": "reconciliation",
                            "outcome": "Success",
                            "agent_role": "Sales",  # Different role
                            "confidence_score": 0.7
                        }
                    },
                    {
                        "id": "exp_2",
                        "text": "Task: approval\nInput: Approve invoice\nOutcome: Success\nLearnings: Policy followed",
                        "created_at": datetime.now().isoformat(),
                        "metadata": {
                            "agent_id": "other_agent",
                            "task_type": "approval",
                            "outcome": "Success",
                            "agent_role": "Finance",  # Role match
                            "confidence_score": 0.9
                        }
                    },
                    {
                        "id": "exp_3",
                        "text": "Task: coding\nInput: Write code\nOutcome: Success\nLearnings: Code written",
                        "created_at": datetime.now().isoformat(),
                        "metadata": {
                            "agent_id": "engineering_agent",
                            "task_type": "coding",
                            "outcome": "Success",
                            "agent_role": "Engineering",  # No match
                            "confidence_score": 0.8
                        }
                    }
                ]
            return []  # All other calls return empty

        mock_lancedb_handler.search = Mock(side_effect=search_side_effect)

        # Mock other dependencies
        with patch('core.graphrag_engine.graphrag_engine') as mock_graphrag, \
             patch('core.formula_memory.get_formula_manager') as mock_formula_mgr, \
             patch('core.agent_world_model.get_db_session') as mock_get_db, \
             patch('core.episode_retrieval_service.EpisodeRetrievalService') as mock_episode_svc:

            mock_graphrag.get_context_for_ai.return_value = ""
            mock_formula_mgr.return_value.search_formulas.return_value = []
            mock_db = AsyncMock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_episode_svc.return_value.retrieve_contextual.return_value = {"episodes": []}

            # Call the method
            result = await world_model_service.recall_experiences(
                agent=agent,
                current_task_description="Reconcile accounts",
                limit=5
            )

            # Verify only role-matched and creator-matched experiences returned
            experiences = result["experiences"]
            assert len(experiences) == 2

            # Verify sorted by confidence score descending
            assert experiences[0].confidence_score == 0.9  # Finance role
            assert experiences[1].confidence_score == 0.7  # Creator match

            # Verify Engineering experience excluded
            assert all(exp.agent_role in ["Finance", "Sales"] or exp.agent_id == agent.id for exp in experiences)

    @pytest.mark.asyncio
    async def test_recall_experiences_filters_low_confidence_failures(
        self, world_model_service, mock_lancedb_handler
    ):
        """
        GIVEN WorldModelService with mocked LanceDBHandler
        WHEN recall_experiences() is called with mixed outcomes and confidence scores
        THEN low-confidence failures filtered out, high-confidence failures included
        """
        # Mock agent with category "Sales"
        agent = Mock()
        agent.id = "agent_sales_1"
        agent.name = "Sales Agent"
        agent.category = "Sales"
        agent.status = "autonomous"

        # Track call count to return different data
        call_count = [0]

        def search_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First call: agent_experience table
                return [
                    {
                        "id": "exp_1",
                        "text": "Task: outreach\nInput: Cold call\nOutcome: Success\nLearnings: Good approach",
                        "created_at": datetime.now().isoformat(),
                        "metadata": {
                            "agent_id": "agent_sales_1",
                            "task_type": "outreach",
                            "outcome": "Success",
                            "agent_role": "Sales",
                            "confidence_score": 0.7
                        }
                    },
                    {
                        "id": "exp_2",
                        "text": "Task: outreach\nInput: Failed call\nOutcome: failed\nLearnings: Bad timing",
                        "created_at": datetime.now().isoformat(),
                        "metadata": {
                            "agent_id": "agent_sales_1",
                            "task_type": "outreach",
                            "outcome": "failed",
                            "agent_role": "Sales",
                            "confidence_score": 0.9  # High confidence failure - should be included
                        }
                    },
                    {
                        "id": "exp_3",
                        "text": "Task: outreach\nInput: Another fail\nOutcome: failed\nLearnings: Wrong approach",
                        "created_at": datetime.now().isoformat(),
                        "metadata": {
                            "agent_id": "agent_sales_1",
                            "task_type": "outreach",
                            "outcome": "failed",
                            "agent_role": "Sales",
                            "confidence_score": 0.5  # Low confidence failure - should be excluded
                        }
                    }
                ]
            return []  # All other calls return empty

        mock_lancedb_handler.search = Mock(side_effect=search_side_effect)

        # Mock other dependencies
        with patch('core.graphrag_engine.graphrag_engine') as mock_graphrag, \
             patch('core.formula_memory.get_formula_manager') as mock_formula_mgr, \
             patch('core.agent_world_model.get_db_session') as mock_get_db, \
             patch('core.episode_retrieval_service.EpisodeRetrievalService') as mock_episode_svc:

            mock_graphrag.get_context_for_ai.return_value = ""
            mock_formula_mgr.return_value.search_formulas.return_value = []
            mock_db = AsyncMock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_episode_svc.return_value.retrieve_contextual.return_value = {"episodes": []}

            # Call the method
            result = await world_model_service.recall_experiences(
                agent=agent,
                current_task_description="Customer outreach",
                limit=5
            )

            # Verify experiences filtered correctly
            experiences = result["experiences"]
            assert len(experiences) == 2  # Success + high-confidence failure

            # Verify outcomes
            outcomes = [exp.outcome for exp in experiences]
            assert "Success" in outcomes
            assert "failed" in outcomes

            # Verify low-confidence failure excluded
            assert all(exp.confidence_score >= 0.8 or exp.outcome != "failed" for exp in experiences)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
