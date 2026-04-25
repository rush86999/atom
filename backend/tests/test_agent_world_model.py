"""
Comprehensive Agent World Model Tests

Tests for core/agent_world_model.py covering:
- Business facts storage and retrieval
- Citation verification (R2/S3)
- Semantic search (vector similarity)
- Knowledge graph traversal
- Fact synthesis and answer generation
- Security (secrets redaction, RBAC)

Target: 40%+ coverage (712 statements → cover ~285 lines, current 11.94%)
"""

import os
os.environ["TESTING"] = "1"

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

# Import WorldModelService and related classes
from core.agent_world_model import (
    WorldModelService,
    AgentExperience,
    BusinessFact,
    DetailLevel
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDB handler."""
    handler = Mock()
    handler.db = Mock()
    handler.db.table_names = Mock(return_value=[])
    handler.create_table = Mock()
    handler.add_documents = Mock()
    handler.search = Mock(return_value=[])
    return handler


@pytest.fixture
def world_model_service(mock_lancedb_handler):
    """Create WorldModelService instance for testing."""
    with patch('core.agent_world_model.get_lancedb_handler', return_value=mock_lancedb_handler):
        service = WorldModelService(workspace_id="test-workspace")
        return service


@pytest.fixture
def sample_experience():
    """Sample agent experience for testing."""
    return AgentExperience(
        id="exp-001",
        agent_id="agent-123",
        task_type="reconciliation",
        input_summary="Reconcile SKU-123",
        outcome="Success",
        learnings="Mismatch due to timing difference",
        confidence_score=0.8,
        agent_role="Finance",
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_business_fact():
    """Sample business fact for testing."""
    return BusinessFact(
        id="fact-001",
        fact="Invoices > $500 need VP approval",
        citations=["policy.pdf:p4", "src/approvals.ts:L20"],
        reason="Approval policy for large invoices",
        source_agent_id="agent-123",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="verified"
    )


# ============================================================================
# TEST CLASS: TestBusinessFacts
# ============================================================================

class TestBusinessFacts:
    """Test fact storage, retrieval, citation validation."""

    @pytest.mark.asyncio
    async def test_add_business_fact(self, world_model_service, sample_business_fact):
        """Test adding a business fact to the world model."""
        with patch.object(world_model_service, 'db') as mock_db:
            result = await world_model_service.add_business_fact(sample_business_fact)
            assert result is True

    @pytest.mark.asyncio
    async def test_get_business_facts(self, world_model_service):
        """Test retrieving business facts."""
        with patch.object(world_model_service.db, 'search', return_value=[]):
            facts = await world_model_service.get_business_facts(
                agent_id="agent-123",
                limit=10
            )
            assert isinstance(facts, list)

    @pytest.mark.asyncio
    async def test_verify_citation(self, world_model_service):
        """Test citation verification."""
        with patch('core.agent_world_model.verify_citation_from_storage') as mock_verify:
            mock_verify.return_value = True
            result = await world_model_service.verify_citation(
                fact_id="fact-001",
                citation="policy.pdf:p4"
            )
            assert result is True


# ============================================================================
# TEST CLASS: TestSemanticSearch
# ============================================================================

class TestSemanticSearch:
    """Test vector search, similarity scoring, result ranking."""

    @pytest.mark.asyncio
    async def test_semantic_search_experiences(self, world_model_service):
        """Test semantic search across agent experiences."""
        with patch.object(world_model_service.db, 'search') as mock_search:
            mock_search.return_value = []
            results = await world_model_service.semantic_search_experiences(
                query="How to reconcile invoices",
                agent_id="agent-123",
                limit=5
            )
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_business_facts(self, world_model_service):
        """Test searching business facts."""
        with patch.object(world_model_service.db, 'search') as mock_search:
            mock_search.return_value = []
            results = await world_model_service.search_business_facts(
                query="approval policy",
                limit=10
            )
            assert isinstance(results, list)


# ============================================================================
# TEST CLASS: TestKnowledgeGraph
# ============================================================================

class TestKnowledgeGraph:
    """Test graph traversal, relationship queries, path finding."""

    @pytest.mark.asyncio
    async def test_get_related_experiences(self, world_model_service):
        """Test getting experiences related to a specific task."""
        with patch.object(world_model_service.db, 'search') as mock_search:
            mock_search.return_value = []
            related = await world_model_service.get_related_experiences(
                task_type="reconciliation",
                agent_id="agent-123"
            )
            assert isinstance(related, list)


# ============================================================================
# TEST CLASS: TestFactSynthesis
# ============================================================================

class TestFactSynthesis:
    """Test answer generation, context aggregation, LLM calls."""

    @pytest.mark.asyncio
    async def test_synthesize_answer(self, world_model_service):
        """Test synthesizing answer from retrieved context."""
        with patch.object(world_model_service.db, 'search', return_value=[]):
            with patch('core.agent_world_model.llm_service') as mock_llm:
                mock_llm.generate = AsyncMock(return_value="Synthesized answer")
                answer = await world_model_service.synthesize_answer(
                    query="What is the approval policy?",
                    context=[]
                )
                assert answer is not None


# ============================================================================
# TEST CLASS: TestSecurity
# ============================================================================

class TestSecurity:
    """Test secrets redaction, RBAC enforcement, audit logging."""

    def test_redact_secrets_from_text(self, world_model_service):
        """Test redacting secrets from text."""
        text_with_secrets = "API key: sk-1234567890abcdef"
        redacted = world_model_service._redact_secrets(text_with_secrets)
        assert "sk-1234567890abcdef" not in redacted

    def test_check_rbac_permissions(self, world_model_service):
        """Test RBAC permission checking."""
        # Admin should have full access
        has_access = world_model_service._check_permissions(
            user_role="admin",
            action="read",
            resource="business_facts"
        )
        assert has_access is True


# ============================================================================
# TEST CLASS: TestExperienceRecording
# ============================================================================

class TestExperienceRecording:
    """Test recording and retrieving agent experiences."""

    @pytest.mark.asyncio
    async def test_record_experience(self, world_model_service, sample_experience):
        """Test recording agent experience."""
        with patch.object(world_model_service.db, 'add_documents') as mock_add:
            result = await world_model_service.record_experience(sample_experience)
            assert result is True

    @pytest.mark.asyncio
    async def test_get_agent_experiences(self, world_model_service):
        """Test retrieving experiences for an agent."""
        with patch.object(world_model_service.db, 'search') as mock_search:
            mock_search.return_value = []
            experiences = await world_model_service.get_agent_experiences(
                agent_id="agent-123",
                limit=10
            )
            assert isinstance(experiences, list)

    @pytest.mark.asyncio
    async def test_get_experiences_by_task(self, world_model_service):
        """Test retrieving experiences by task type."""
        with patch.object(world_model_service.db, 'search') as mock_search:
            mock_search.return_value = []
            experiences = await world_model_service.get_experiences_by_task(
                task_type="reconciliation",
                limit=10
            )
            assert isinstance(experiences, list)


# ============================================================================
# TEST CLASS: TestDetailLevels
# ============================================================================

class TestDetailLevels:
    """Test different detail levels for episode recall."""

    def test_summary_detail_level(self):
        """Test SUMMARY detail level enum."""
        assert DetailLevel.SUMMARY == "summary"

    def test_standard_detail_level(self):
        """Test STANDARD detail level enum."""
        assert DetailLevel.STANDARD == "standard"

    def test_full_detail_level(self):
        """Test FULL detail level enum."""
        assert DetailLevel.FULL == "full"


# ============================================================================
# TEST CLASS: TestModels
# ============================================================================

class TestModels:
    """Test data models and validation."""

    def test_agent_experience_model(self, sample_experience):
        """Test AgentExperience model validation."""
        assert sample_experience.id == "exp-001"
        assert sample_experience.agent_id == "agent-123"
        assert sample_experience.confidence_score >= 0.0
        assert sample_experience.confidence_score <= 1.0

    def test_business_fact_model(self, sample_business_fact):
        """Test BusinessFact model validation."""
        assert sample_business_fact.id == "fact-001"
        assert len(sample_business_fact.citations) > 0
        assert sample_business_fact.verification_status in ["unverified", "verified", "outdated"]


# ============================================================================
# TEST CLASS: TestEdgeCases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_search_query(self, world_model_service):
        """Test handling empty search query."""
        with patch.object(world_model_service.db, 'search', return_value=[]):
            results = await world_model_service.semantic_search_experiences(
                query="",
                agent_id="agent-123"
            )
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_fact(self, world_model_service):
        """Test retrieving fact that doesn't exist."""
        with patch.object(world_model_service.db, 'search', return_value=[]):
            facts = await world_model_service.get_business_facts(
                fact_id="nonexistent-fact"
            )
            assert isinstance(facts, list)

    @pytest.mark.asyncio
    async def test_record_experience_with_low_confidence(self, world_model_service):
        """Test recording experience with low confidence score."""
        low_conf_exp = AgentExperience(
            id="exp-low",
            agent_id="agent-123",
            task_type="test",
            input_summary="Test",
            outcome="Failure",
            learnings="Failed",
            confidence_score=0.1,
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )
        with patch.object(world_model_service.db, 'add_documents'):
            result = await world_model_service.record_experience(low_conf_exp)
            assert result is True
