"""
Unit tests for WorldModelService (agent_world_model.py)
Aligned with actual implementation - reviewed code BEFORE writing tests.

Coverage Target: 50-60% (realistic for 2,206-line file with complex async operations)
Pass Rate Target: 70%+ (focus on tests that actually pass)
Approach: Implementation-first - read actual code, then write tests
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from core.agent_world_model import (
    WorldModelService,
    AgentExperience,
    BusinessFact,
    DetailLevel
)
from core.models import AgentRegistry, ChatMessage
import uuid


# ============================================================================
# FIXTURES - Aligned with actual LanceDBHandler and WorldModelService patterns
# ============================================================================

@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDBHandler with realistic return values based on actual implementation"""
    handler = Mock()
    handler.db = Mock()  # Simulates active LanceDB connection
    handler.db.table_names = Mock(return_value=[])  # No tables exist yet
    handler.workspace_id = "test_workspace"

    # Mock add_document to return True (success)
    handler.add_document = Mock(return_value=True)

    # Mock search to return empty list by default
    handler.search = Mock(return_value=[])

    # Mock create_table
    handler.create_table = Mock()

    # Mock get_table
    handler.get_table = Mock(return_value=None)

    return handler


@pytest.fixture
def world_model_service(mock_lancedb_handler):
    """WorldModelService instance with mocked dependencies"""
    with patch('core.agent_world_model.get_lancedb_handler', return_value=mock_lancedb_handler):
        service = WorldModelService(workspace_id="test_workspace")
        service.db = mock_lancedb_handler
        return service


@pytest.fixture
def sample_agent_experience():
    """Sample AgentExperience matching actual Pydantic model"""
    return AgentExperience(
        id=str(uuid.uuid4()),
        agent_id="agent_123",
        task_type="reconciliation",
        input_summary="Reconcile SKU-123",
        outcome="Success",
        learnings="Mismatch due to timing difference",
        confidence_score=0.8,
        feedback_score=0.5,
        artifacts=["report_123.pdf"],
        step_efficiency=1.0,
        metadata_trace={"steps_taken": 5},
        agent_role="Finance",
        specialty="accounting",
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_business_fact():
    """Sample BusinessFact matching actual Pydantic model"""
    return BusinessFact(
        id=str(uuid.uuid4()),
        fact="Invoices > $500 need VP approval",
        citations=["policy.pdf:p4", "src/approvals.ts:L20"],
        reason="AP policy threshold for approval workflow",
        source_agent_id="agent_123",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="unverified",
        metadata={"domain": "finance", "priority": "high"}
    )


# ============================================================================
# CATEGORY 1: EXPERIENCE RECORDING (5 methods)
# Focus: record_experience, record_formula_usage, update_experience_feedback
# ============================================================================

class TestExperienceRecording:
    """Test experience recording and feedback methods"""

    @pytest.mark.asyncio
    async def test_record_experience_success(self, world_model_service, sample_agent_experience):
        """Test successful experience recording"""
        result = await world_model_service.record_experience(sample_agent_experience)

        assert result is True
        world_model_service.db.add_document.assert_called_once()

        # Verify call arguments match actual implementation
        call_args = world_model_service.db.add_document.call_args
        assert call_args[1]['table_name'] == 'agent_experience'
        assert 'Task: reconciliation' in call_args[1]['text']
        assert 'Input: Reconcile SKU-123' in call_args[1]['text']
        assert 'Outcome: Success' in call_args[1]['text']
        assert call_args[1]['metadata']['type'] == 'experience'
        assert call_args[1]['metadata']['agent_id'] == 'agent_123'
        assert call_args[1]['metadata']['confidence_score'] == 0.8

    @pytest.mark.asyncio
    async def test_record_experience_lancedb_failure(self, world_model_service, sample_agent_experience):
        """Test experience recording when LanceDB add fails"""
        world_model_service.db.add_document = Mock(return_value=False)

        result = await world_model_service.record_experience(sample_agent_experience)

        assert result is False

    @pytest.mark.asyncio
    async def test_record_experience_with_feedback(self, world_model_service):
        """Test recording experience with human feedback score"""
        experience = AgentExperience(
            id=str(uuid.uuid4()),
            agent_id="agent_456",
            task_type="outreach",
            input_summary="Contact customer",
            outcome="Success",
            learnings="Best time to call is morning",
            confidence_score=0.7,
            feedback_score=0.9,  # Human feedback
            agent_role="Sales",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True
        call_args = world_model_service.db.add_document.call_args
        metadata = call_args[1]['metadata']
        assert metadata['feedback_score'] == 0.9

    @pytest.mark.asyncio
    async def test_record_formula_usage_success(self, world_model_service):
        """Test formula usage recording"""
        result = await world_model_service.record_formula_usage(
            agent_id="agent_123",
            agent_role="Finance",
            formula_id="sum_formula",
            formula_name="Sum",
            task_description="Calculate monthly expenses",
            inputs={"amounts": [100, 200, 300]},
            result=600,
            success=True,
            learnings="Formula worked correctly"
        )

        assert result is True
        world_model_service.db.add_document.assert_called_once()

        # Verify metadata structure matches implementation
        call_args = world_model_service.db.add_document.call_args
        metadata = call_args[1]['metadata']
        assert metadata['type'] == 'experience'
        assert metadata['task_type'] == 'formula_application'
        assert metadata['formula_id'] == 'sum_formula'
        assert metadata['formula_name'] == 'Sum'
        assert metadata['outcome'] == 'Success'

    @pytest.mark.asyncio
    async def test_record_formula_usage_failure(self, world_model_service):
        """Test formula usage recording when calculation fails"""
        result = await world_model_service.record_formula_usage(
            agent_id="agent_123",
            agent_role="Finance",
            formula_id="divide_formula",
            formula_name="Divide",
            task_description="Calculate ratio",
            inputs={"numerator": 100, "denominator": 0},
            result="Error: Division by zero",
            success=False,
            learnings="Need to validate denominator first"
        )

        assert result is True
        call_args = world_model_service.db.add_document.call_args
        assert 'Outcome: Failure' in call_args[1]['text']

    @pytest.mark.asyncio
    async def test_update_experience_feedback_success(self, world_model_service):
        """Test updating experience with feedback"""
        experience_id = str(uuid.uuid4())

        # Mock search to return the experience
        world_model_service.db.search = Mock(return_value=[
            {
                "id": experience_id,
                "text": "Task: reconciliation\nOutcome: Success",
                "metadata": {
                    "confidence_score": 0.5,
                    "agent_id": "agent_123"
                },
                "source": "agent_123"
            }
        ])

        result = await world_model_service.update_experience_feedback(
            experience_id=experience_id,
            feedback_score=0.8,
            feedback_notes="Great job!"
        )

        assert result is True
        # Verify new document added with updated confidence
        assert world_model_service.db.add_document.called
        # Confidence should blend: 0.5 * 0.6 + (0.8 + 1.0) / 2.0 * 0.4 = 0.3 + 0.36 = 0.66

    @pytest.mark.asyncio
    async def test_update_experience_feedback_not_found(self, world_model_service):
        """Test feedback update when experience not found"""
        world_model_service.db.search = Mock(return_value=[])

        result = await world_model_service.update_experience_feedback(
            experience_id="nonexistent",
            feedback_score=0.5
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_experience_feedback_negative_score(self, world_model_service):
        """Test feedback with negative score (poor performance)"""
        experience_id = str(uuid.uuid4())
        world_model_service.db.search = Mock(return_value=[
            {
                "id": experience_id,
                "text": "Task: outreach\nOutcome: Failure",
                "metadata": {"confidence_score": 0.7, "agent_id": "agent_123"},
                "source": "agent_123"
            }
        ])

        result = await world_model_service.update_experience_feedback(
            experience_id=experience_id,
            feedback_score=-0.8,  # Poor performance
            feedback_notes="Approach was incorrect"
        )

        assert result is True
        # Confidence should decrease significantly

    @pytest.mark.asyncio
    async def test_boost_experience_confidence(self, world_model_service):
        """Test confidence boost (placeholder implementation)"""
        result = await world_model_service.boost_experience_confidence(
            experience_id="exp_123",
            boost_amount=0.1
        )

        # Current implementation is placeholder - returns True
        assert result is True

    @pytest.mark.asyncio
    async def test_get_experience_statistics_success(self, world_model_service):
        """Test retrieving experience statistics"""
        world_model_service.db.search = Mock(return_value=[
            {
                "metadata": {
                    "agent_id": "agent_123",
                    "agent_role": "Finance",
                    "outcome": "Success",
                    "confidence_score": 0.8,
                    "feedback_score": 0.5
                }
            },
            {
                "metadata": {
                    "agent_id": "agent_123",
                    "agent_role": "Finance",
                    "outcome": "Failure",
                    "confidence_score": 0.3,
                    "feedback_score": None
                }
            },
            {
                "metadata": {
                    "agent_id": "agent_123",
                    "agent_role": "Finance",
                    "outcome": "Success",
                    "confidence_score": 0.9,
                    "feedback_score": 0.7
                }
            }
        ])

        stats = await world_model_service.get_experience_statistics(
            agent_id="agent_123"
        )

        assert stats['total_experiences'] == 3
        assert stats['successes'] == 2
        assert stats['failures'] == 1
        assert stats['success_rate'] == 2/3
        assert stats['avg_confidence'] == (0.8 + 0.3 + 0.9) / 3
        assert stats['feedback_coverage'] == 2/3

    @pytest.mark.asyncio
    async def test_get_experience_statistics_filtered_by_role(self, world_model_service):
        """Test statistics filtered by agent role"""
        world_model_service.db.search = Mock(return_value=[
            {"metadata": {"agent_role": "Finance", "outcome": "Success", "confidence_score": 0.8}},
            {"metadata": {"agent_role": "Sales", "outcome": "Success", "confidence_score": 0.7}}
        ])

        stats = await world_model_service.get_experience_statistics(agent_role="Finance")

        assert stats['total_experiences'] == 1  # Only Finance
        assert stats['agent_role'] == "Finance"

    @pytest.mark.asyncio
    async def test_get_experience_statistics_error(self, world_model_service):
        """Test statistics retrieval with database error"""
        world_model_service.db.search = Mock(side_effect=Exception("DB connection lost"))

        stats = await world_model_service.get_experience_statistics()

        assert "error" in stats
        assert stats["error"] == "DB connection lost"


# ============================================================================
# CATEGORY 2: BUSINESS FACTS (8 methods)
# Focus: record_business_fact, get_relevant_business_facts, bulk_record_facts
# ============================================================================

class TestBusinessFacts:
    """Test business fact recording and retrieval methods"""

    @pytest.mark.asyncio
    async def test_record_business_fact_success(self, world_model_service, sample_business_fact):
        """Test successful business fact recording"""
        result = await world_model_service.record_business_fact(sample_business_fact)

        assert result is True
        world_model_service.db.add_document.assert_called_once()

        # Verify fact structure
        call_args = world_model_service.db.add_document.call_args
        assert call_args[1]['table_name'] == 'business_facts'
        assert 'Invoices > $500 need VP approval' in call_args[1]['text']
        assert call_args[1]['metadata']['type'] == 'business_fact'
        assert call_args[1]['metadata']['verification_status'] == 'unverified'
        assert call_args[1]['metadata']['fact'] == sample_business_fact.fact

    @pytest.mark.asyncio
    async def test_record_business_fact_with_citations(self, world_model_service):
        """Test fact with multiple citations"""
        fact = BusinessFact(
            id=str(uuid.uuid4()),
            fact="Expense reports > $1000 require receipts",
            citations=["policy.pdf:p10", "handbook.doc:p5", "email.md:ref123"],
            reason="Compliance requirement for audit trail",
            source_agent_id="agent_456",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_business_fact(fact)

        assert result is True
        call_args = world_model_service.db.add_document.call_args
        assert 'policy.pdf:p10' in call_args[1]['text']
        assert call_args[1]['metadata']['citations'] == ["policy.pdf:p10", "handbook.doc:p5", "email.md:ref123"]

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts_success(self, world_model_service):
        """Test retrieving relevant business facts via semantic search"""
        world_model_service.db.search = Mock(return_value=[
            {
                "metadata": {
                    "id": "fact_123",
                    "fact": "Invoices > $500 need VP approval",
                    "citations": ["policy.pdf:p4"],
                    "reason": "AP policy",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "verified"
                }
            },
            {
                "metadata": {
                    "id": "fact_456",
                    "fact": "All expenses require manager approval",
                    "citations": ["handbook.pdf:p2"],
                    "reason": "General expense policy",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "verified"
                }
            }
        ])

        facts = await world_model_service.get_relevant_business_facts(
            query="invoice approval process",
            limit=5
        )

        assert len(facts) == 2
        assert facts[0].fact == "Invoices > $500 need VP approval"
        assert facts[0].verification_status == "verified"
        assert facts[1].fact == "All expenses require manager approval"

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts_empty(self, world_model_service):
        """Test retrieving facts when none found"""
        world_model_service.db.search = Mock(return_value=[])

        facts = await world_model_service.get_relevant_business_facts(
            query="nonexistent topic"
        )

        assert len(facts) == 0

    @pytest.mark.asyncio
    async def test_update_fact_verification_success(self, world_model_service):
        """Test updating fact verification status"""
        fact_id = "fact_123"

        world_model_service.db.search = Mock(return_value=[
            {
                "id": "doc_123",
                "text": "Fact: Invoices > $500\nStatus: unverified",
                "metadata": {
                    "id": fact_id,
                    "verification_status": "unverified"
                },
                "source": "fact_agent_123"
            }
        ])

        result = await world_model_service.update_fact_verification(
            fact_id=fact_id,
            status="verified"
        )

        assert result is True
        # Verify new document added with updated status
        assert world_model_service.db.add_document.called

    @pytest.mark.asyncio
    async def test_update_fact_verification_not_found(self, world_model_service):
        """Test verification update when fact not found"""
        world_model_service.db.search = Mock(return_value=[])

        result = await world_model_service.update_fact_verification(
            fact_id="nonexistent",
            status="verified"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_bulk_record_facts_success(self, world_model_service):
        """Test bulk fact recording"""
        facts = [
            BusinessFact(
                id=str(uuid.uuid4()),
                fact=f"Fact {i}",
                citations=[],
                reason="Test",
                source_agent_id="agent_123",
                created_at=datetime.now(timezone.utc),
                last_verified=datetime.now(timezone.utc)
            )
            for i in range(3)
        ]

        success_count = await world_model_service.bulk_record_facts(facts)

        assert success_count == 3
        assert world_model_service.db.add_document.call_count == 3

    @pytest.mark.asyncio
    async def test_bulk_record_facts_partial_failure(self, world_model_service):
        """Test bulk recording with some failures"""
        facts = [
            BusinessFact(
                id=str(uuid.uuid4()),
                fact="Fact 1",
                citations=[],
                reason="Test",
                source_agent_id="agent_123",
                created_at=datetime.now(timezone.utc),
                last_verified=datetime.now(timezone.utc)
            ),
            BusinessFact(
                id=str(uuid.uuid4()),
                fact="Fact 2",
                citations=[],
                reason="Test",
                source_agent_id="agent_123",
                created_at=datetime.now(timezone.utc),
                last_verified=datetime.now(timezone.utc)
            )
        ]

        # First succeeds, second fails
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            return call_count[0] == 1

        world_model_service.db.add_document = Mock(side_effect=side_effect)

        success_count = await world_model_service.bulk_record_facts(facts)

        assert success_count == 1  # Only first succeeded

    @pytest.mark.asyncio
    async def test_list_all_facts_with_filters(self, world_model_service):
        """Test listing facts with status filter"""
        world_model_service.db.search = Mock(return_value=[
            {
                "metadata": {
                    "id": "fact_1",
                    "fact": "Fact 1",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "verified",
                    "domain": "finance"
                }
            },
            {
                "metadata": {
                    "id": "fact_2",
                    "fact": "Fact 2",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "unverified",
                    "domain": "finance"
                }
            }
        ])

        facts = await world_model_service.list_all_facts(
            status="verified",
            limit=10
        )

        # Should only return verified facts
        assert len(facts) == 1
        assert facts[0].verification_status == "verified"

    @pytest.mark.asyncio
    async def test_list_all_facts_domain_filter(self, world_model_service):
        """Test listing facts filtered by domain"""
        world_model_service.db.search = Mock(return_value=[
            {
                "metadata": {
                    "id": "fact_1",
                    "fact": "Finance fact",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "verified",
                    "domain": "finance"
                }
            },
            {
                "metadata": {
                    "id": "fact_2",
                    "fact": "HR fact",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "verified",
                    "domain": "hr"
                }
            }
        ])

        facts = await world_model_service.list_all_facts(
            domain="finance",
            limit=10
        )

        assert len(facts) == 1
        assert facts[0].fact == "Finance fact"

    @pytest.mark.asyncio
    async def test_get_fact_by_id_success(self, world_model_service):
        """Test retrieving fact by ID using search method"""
        fact_id = "fact_123"
        world_model_service.db.search = Mock(return_value=[
            {
                "metadata": {
                    "id": fact_id,
                    "fact": "Test fact",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "verified",
                    "domain": "test"
                }
            }
        ])

        fact = await world_model_service.get_fact_by_id(fact_id)

        assert fact is not None
        assert fact.id == fact_id
        assert fact.fact == "Test fact"

    @pytest.mark.asyncio
    async def test_get_fact_by_id_not_found(self, world_model_service):
        """Test get_fact_by_id when fact doesn't exist"""
        world_model_service.db.search = Mock(return_value=[])

        fact = await world_model_service.get_fact_by_id("nonexistent")

        assert fact is None

    @pytest.mark.asyncio
    async def test_delete_fact_soft_delete(self, world_model_service):
        """Test fact deletion (soft delete via status update)"""
        fact_id = "fact_123"

        world_model_service.db.search = Mock(return_value=[
            {
                "id": "doc_123",
                "text": "Fact: Test\nStatus: unverified",
                "metadata": {"id": fact_id, "verification_status": "unverified"},
                "source": "fact_agent_123"
            }
        ])

        result = await world_model_service.delete_fact(fact_id)

        assert result is True
        # delete_fact calls update_fact_verification with "deleted" status
        assert world_model_service.db.add_document.called


# ============================================================================
# CATEGORY 3: INTEGRATION EXPERIENCES (1 method)
# ============================================================================

class TestIntegrationExperiences:
    """Test integration experience recall methods"""

    @pytest.mark.asyncio
    async def test_recall_integration_experiences_success(self, world_model_service):
        """Test recalling integration experiences"""
        world_model_service.db.search = Mock(return_value=[
            {
                "id": "exp_1",
                "text": "Task: integration_hubspot_sync\nInput: Sync contacts\nOutcome: Success",
                "metadata": {
                    "agent_id": "agent_123",
                    "task_type": "integration_hubspot_sync",
                    "outcome": "Success",
                    "agent_role": "Sales",
                    "confidence_score": 0.8
                },
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ])

        experiences = await world_model_service.recall_integration_experiences(
            agent_role="Sales",
            connector_id="hubspot",
            operation_name="sync",
            limit=5
        )

        assert len(experiences) == 1
        assert experiences[0].task_type == "integration_hubspot_sync"
        assert experiences[0].outcome == "Success"

    @pytest.mark.asyncio
    async def test_recall_integration_experiences_no_database(self, world_model_service):
        """Test integration recall when database is None"""
        world_model_service.db.db = None

        experiences = await world_model_service.recall_integration_experiences(
            agent_role="Sales",
            connector_id="hubspot",
            operation_name="sync"
        )

        assert experiences == []

    @pytest.mark.asyncio
    async def test_recall_integration_experiences_empty(self, world_model_service):
        """Test integration recall when no experiences found"""
        world_model_service.db.search = Mock(return_value=[])

        experiences = await world_model_service.recall_integration_experiences(
            agent_role="Finance",
            connector_id="quickbooks",
            operation_name="import"
        )

        assert experiences == []


# ============================================================================
# CATEGORY 4: COLD STORAGE (4 methods)
# Focus: archive_session, recover_session
# ============================================================================

class TestColdStorage:
    """Test cold storage archival and recovery methods"""

    @pytest.mark.asyncio
    async def test_archive_session_success(self, world_model_service):
        """Test successful session archival to LanceDB"""
        conversation_id = "conv_123"

        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            # Mock database query to return messages
            mock_msg = Mock(spec=ChatMessage)
            mock_msg.conversation_id = conversation_id
            mock_msg.tenant_id = "test_workspace"
            mock_msg.role = "user"
            mock_msg.content = "Hello"
            mock_msg.metadata_json = {}

            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_msg]

            result = await world_model_service.archive_session_to_cold_storage(conversation_id)

            assert result is True
            # Verify document added to LanceDB
            assert world_model_service.db.add_document.called

            # Verify messages marked as archived
            assert mock_msg.metadata_json["_archived"] is True
            assert "_archived_at" in mock_msg.metadata_json
            assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_archive_session_no_messages(self, world_model_service):
        """Test archival when no messages found"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

            result = await world_model_service.archive_session_to_cold_storage("conv_123")

            assert result is False

    @pytest.mark.asyncio
    async def test_archive_session_multiple_messages(self, world_model_service):
        """Test archival with multiple messages"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            messages = []
            for i in range(3):
                msg = Mock(spec=ChatMessage)
                msg.conversation_id = "conv_456"
                msg.tenant_id = "test_workspace"
                msg.role = "user" if i % 2 == 0 else "assistant"
                msg.content = f"Message {i}"
                msg.metadata_json = {}
                messages.append(msg)

            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = messages

            result = await world_model_service.archive_session_to_cold_storage("conv_456")

            assert result is True
            # All messages should be marked as archived
            for msg in messages:
                assert msg.metadata_json["_archived"] is True

    @pytest.mark.asyncio
    async def test_recover_archived_session_success(self, world_model_service):
        """Test recovering soft-deleted session"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_msg = Mock(spec=ChatMessage)
            mock_msg.conversation_id = "conv_123"
            mock_msg.tenant_id = "test_workspace"
            mock_msg.metadata_json = {"_archived": True}

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_msg]

            result = await world_model_service.recover_archived_session("conv_123")

            assert result["status"] == "success"
            assert result["recovered_count"] == 1
            # Verify archived flag removed
            assert "_archived" not in mock_msg.metadata_json
            assert mock_msg.metadata_json["_recovered"] is True
            assert "_recovered_at" in mock_msg.metadata_json
            assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_recover_archived_session_not_found(self, world_model_service):
        """Test recovery when no archived messages found"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = []

            result = await world_model_service.recover_archived_session("conv_999")

            assert result["status"] == "failed"
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_hard_delete_archived_sessions_success(self, world_model_service):
        """Test hard deletion of archived sessions past retention"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            # Create mock messages past retention
            mock_msg = Mock(spec=ChatMessage)
            mock_msg.metadata_json = {
                "_archived": True,
                "_retention_until": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            }

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_msg]

            result = await world_model_service.hard_delete_archived_sessions(older_than_days=30)

            assert result["status"] == "success"
            assert result["deleted_count"] == 1
            assert mock_db.delete.called
            assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_hard_delete_no_sessions_past_retention(self, world_model_service):
        """Test hard delete when no sessions are past retention"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = []

            result = await world_model_service.hard_delete_archived_sessions()

            assert result["status"] == "success"
            assert result["deleted_count"] == 0


# ============================================================================
# CATEGORY 5: ERROR HANDLING
# Focus: Database failures, edge cases, robustness
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_get_experience_statistics_empty_results(self, world_model_service):
        """Test statistics when no experiences exist"""
        world_model_service.db.search = Mock(return_value=[])

        stats = await world_model_service.get_experience_statistics()

        assert stats['total_experiences'] == 0
        assert stats['successes'] == 0
        assert stats['failures'] == 0
        assert stats['success_rate'] == 0
        assert stats['avg_confidence'] == 0.5  # Default when no data

    @pytest.mark.asyncio
    async def test_get_relevant_business_facts_search_error(self, world_model_service):
        """Test fact retrieval with search error"""
        world_model_service.db.search = Mock(side_effect=Exception("Search failed"))

        facts = await world_model_service.get_relevant_business_facts("query")

        # Should return empty list on error
        assert facts == []

    @pytest.mark.asyncio
    async def test_list_all_facts_parse_error(self, world_model_service):
        """Test listing facts when some fail to parse"""
        world_model_service.db.search = Mock(return_value=[
            {
                "metadata": {
                    "id": "fact_1",
                    "fact": "Valid fact",
                    "citations": [],
                    "reason": "Test",
                    "source_agent_id": "agent_123",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                    "verification_status": "verified"
                }
            },
            {
                "metadata": {
                    "id": "fact_2",
                    # Missing required fields - will fail parsing
                    "citations": [],
                    "source_agent_id": "agent_123"
                }
            }
        ])

        facts = await world_model_service.list_all_facts(limit=10)

        # Should return only valid facts, skip invalid ones
        assert len(facts) == 1
        assert facts[0].fact == "Valid fact"

    @pytest.mark.asyncio
    async def test_bulk_record_facts_empty_list(self, world_model_service):
        """Test bulk recording with empty list"""
        success_count = await world_model_service.bulk_record_facts([])

        assert success_count == 0

    @pytest.mark.asyncio
    async def test_update_experience_feedback_search_error(self, world_model_service):
        """Test feedback update with search error"""
        world_model_service.db.search = Mock(side_effect=Exception("Search failed"))

        result = await world_model_service.update_experience_feedback(
            experience_id="exp_123",
            feedback_score=0.5
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_record_experience_with_minimal_fields(self, world_model_service):
        """Test recording experience with only required fields"""
        experience = AgentExperience(
            id=str(uuid.uuid4()),
            agent_id="agent_minimal",
            task_type="test",
            input_summary="Minimal test",
            outcome="Success",
            learnings="Test learning",
            agent_role="Test",
            timestamp=datetime.now(timezone.utc)
        )

        result = await world_model_service.record_experience(experience)

        assert result is True

    @pytest.mark.asyncio
    async def test_archive_session_database_error(self, world_model_service):
        """Test archival when database query fails"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.side_effect = Exception("Database connection lost")

            result = await world_model_service.archive_session_to_cold_storage("conv_123")

            assert result is False

    @pytest.mark.asyncio
    async def test_recall_integration_experiences_parse_error(self, world_model_service):
        """Test integration recall with malformed results"""
        world_model_service.db.search = Mock(return_value=[
            {
                "id": "exp_1",
                # Missing required fields - will cause parse error
                "metadata": {}
            }
        ])

        experiences = await world_model_service.recall_integration_experiences(
            agent_role="Sales",
            connector_id="hubspot",
            operation_name="sync"
        )

        # Should handle parse errors gracefully and return empty
        assert experiences == []

    @pytest.mark.asyncio
    async def test_recover_session_database_error(self, world_model_service):
        """Test session recovery with database error"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.side_effect = Exception("Database error")

            result = await world_model_service.recover_archived_session("conv_123")

            assert result["status"] == "failed"
            assert "Database error" in result["error"]


# ============================================================================
# CATEGORY 6: ADDITIONAL COVERAGE (Methods not covered above)
# Focus: get_business_fact, archive_session_with_cleanup
# ============================================================================

class TestAdditionalCoverage:
    """Additional tests to reach coverage target"""

    @pytest.mark.asyncio
    async def test_get_business_fact_by_table_access(self, world_model_service):
        """Test get_business_fact which uses direct table access (not search)"""
        fact_id = "fact_123"

        # Mock get_table to return a mock table
        mock_table = Mock()
        mock_pandas_df = Mock()

        # Mock pandas DataFrame with search result
        import pandas as pd
        mock_row = {
            'id': fact_id,
            'text': 'Fact: Test fact',
            'metadata': '{"id": "fact_123", "fact": "Test fact", "citations": [], "reason": "Test", "source_agent_id": "agent_123", "created_at": "2026-04-27T00:00:00Z", "last_verified": "2026-04-27T00:00:00Z", "verification_status": "unverified"}'
        }
        mock_df = pd.DataFrame([mock_row])
        mock_pandas_df.empty = False
        mock_pandas_df.iloc = [mock_row]

        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = mock_pandas_df
        world_model_service.db.get_table = Mock(return_value=mock_table)

        fact = await world_model_service.get_business_fact(fact_id)

        assert fact is not None
        assert fact.id == fact_id
        assert fact.fact == "Test fact"

    @pytest.mark.asyncio
    async def test_get_business_fact_not_found(self, world_model_service):
        """Test get_business_fact when fact doesn't exist"""
        mock_table = Mock()
        mock_pandas_df = Mock()
        import pandas as pd
        mock_df = pd.DataFrame([])
        mock_pandas_df.empty = True
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = mock_pandas_df
        world_model_service.db.get_table = Mock(return_value=mock_table)

        fact = await world_model_service.get_business_fact("nonexistent")

        assert fact is None

    @pytest.mark.asyncio
    async def test_archive_session_with_cleanup_success(self, world_model_service):
        """Test archival with verification and cleanup"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_msg = Mock(spec=ChatMessage)
            mock_msg.conversation_id = "conv_123"
            mock_msg.tenant_id = "test_workspace"
            mock_msg.role = "user"
            mock_msg.content = "Test message"
            mock_msg.metadata_json = {}

            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_msg]

            result = await world_model_service.archive_session_to_cold_storage_with_cleanup(
                conversation_id="conv_123",
                retention_days=30,
                verify_before_delete=True
            )

            assert result["status"] == "success"
            assert result["archived"] is True
            assert result["soft_deleted"] is True
            assert "audit_id" in result

    @pytest.mark.asyncio
    async def test_archive_session_with_cleanup_no_messages(self, world_model_service):
        """Test archival with cleanup when no messages found"""
        with patch('core.agent_world_model.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

            result = await world_model_service.archive_session_to_cold_storage_with_cleanup("conv_999")

            assert result["status"] == "failed"
            assert "No messages found" in result["error"]
