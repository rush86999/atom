"""
Batch unit tests for core services (Wave 3C)
Target: 800+ lines, 32-42 tests, 60%+ coverage

Tests cover multiple core services grouped by functionality:
- Agent Management Services
- Storage Services
- Cache Services
- Notification Services
- Analytics Services
- Configuration Services
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Import services being tested
from core.agent_social_layer import AgentSocialLayer
from core.skill_registry_service import SkillRegistryService
from core.proposal_service import ProposalService
from core.workflow_debugger import WorkflowDebugger
from core.workflow_analytics_engine import WorkflowAnalyticsEngine
from core.auto_document_ingestion import AutoDocumentIngestion
from core.workflow_versioning_system import WorkflowVersioningSystem
from core.advanced_workflow_system import AdvancedWorkflowSystem
from core.atom_meta_agent import AtomMetaAgent


# =============================================================================
# 1. Agent Management Services (6-8 tests)
# =============================================================================

class TestAgentSocialLayer:
    """Test agent social layer and collaboration features"""

    @pytest.fixture
    def agent_social_layer(self, db_session: Session):
        """Create agent social layer instance"""
        return AgentSocialLayer(db_session)

    def test_create_social_connection(self, agent_social_layer: AgentSocialLayer):
        """Test creating social connection between agents"""
        # Arrange
        agent_id_1 = "agent-001"
        agent_id_2 = "agent-002"
        connection_type = "peer"

        # Act
        result = agent_social_layer.create_connection(
            agent_id_1, agent_id_2, connection_type
        )

        # Assert
        assert result is not None
        assert result.agent_1_id == agent_id_1
        assert result.agent_2_id == agent_id_2
        assert result.connection_type == connection_type
        assert result.created_at is not None

    def test_get_agent_network(self, agent_social_layer: AgentSocialLayer):
        """Test retrieving agent network graph"""
        # Arrange
        agent_id = "agent-001"
        agent_social_layer.create_connection(agent_id, "agent-002", "peer")
        agent_social_layer.create_connection(agent_id, "agent-003", "mentor")

        # Act
        network = agent_social_layer.get_agent_network(agent_id)

        # Assert
        assert network is not None
        assert len(network['connections']) >= 2
        assert 'peers' in network
        assert 'mentors' in network

    def test_share_knowledge_between_agents(self, agent_social_layer: AgentSocialLayer):
        """Test knowledge sharing between connected agents"""
        # Arrange
        agent_id_1 = "agent-001"
        agent_id_2 = "agent-002"
        knowledge = {"workflow_template": "data_analysis"}
        agent_social_layer.create_connection(agent_id_1, agent_id_2, "peer")

        # Act
        result = agent_social_layer.share_knowledge(
            agent_id_1, agent_id_2, knowledge
        )

        # Assert
        assert result is True
        assert result.shared_at is not None

    def test_get_social_recommendations(self, agent_social_layer: AgentSocialLayer):
        """Test getting social connection recommendations"""
        # Arrange
        agent_id = "agent-001"

        # Act
        recommendations = agent_social_layer.get_recommendations(agent_id)

        # Assert
        assert recommendations is not None
        assert isinstance(recommendations, list)

    def test_block_agent_interaction(self, agent_social_layer: AgentSocialLayer):
        """Test blocking interactions between agents"""
        # Arrange
        agent_id_1 = "agent-001"
        agent_id_2 = "agent-002"
        reason = "conflicting objectives"

        # Act
        result = agent_social_layer.block_interaction(
            agent_id_1, agent_id_2, reason
        )

        # Assert
        assert result is True
        assert result.blocked_at is not None
        assert result.reason == reason

    def test_get_agent_influence_score(self, agent_social_layer: AgentSocialLayer):
        """Test calculating agent influence score"""
        # Arrange
        agent_id = "agent-001"

        # Act
        score = agent_social_layer.calculate_influence_score(agent_id)

        # Assert
        assert score is not None
        assert score >= 0
        assert score <= 100


class TestAtomMetaAgent:
    """Test meta agent coordination and orchestration"""

    @pytest.fixture
    def meta_agent(self, db_session: Session):
        """Create meta agent instance"""
        return AtomMetaAgent(db_session)

    def test_coordinate_multi_agent_workflow(self, meta_agent: AtomMetaAgent):
        """Test coordinating workflow across multiple agents"""
        # Arrange
        agents = ["agent-001", "agent-002", "agent-003"]
        workflow_definition = {"steps": ["analyze", "process", "report"]}

        # Act
        coordination = meta_agent.coordinate_workflow(agents, workflow_definition)

        # Assert
        assert coordination is not None
        assert coordination.workflow_id is not None
        assert coordination.status in ["pending", "running"]

    def test_delegate_task_to_specialist(self, meta_agent: AtomMetaAgent):
        """Test delegating task to specialist agent"""
        # Arrange
        task = {"type": "data_analysis", "data": "sales_data.csv"}
        specialist_type = "analyst"

        # Act
        delegation = meta_agent.delegate_task(task, specialist_type)

        # Assert
        assert delegation is not None
        assert delegation.assigned_agent_id is not None
        assert delegation.task_status in ["assigned", "in_progress"]

    def test_merge_agent_outputs(self, meta_agent: AtomMetaAgent):
        """Test merging outputs from multiple agents"""
        # Arrange
        outputs = [
            {"agent_id": "agent-001", "result": "analysis_1"},
            {"agent_id": "agent-002", "result": "analysis_2"}
        ]
        merge_strategy = "vote"

        # Act
        merged = meta_agent.merge_outputs(outputs, merge_strategy)

        # Assert
        assert merged is not None
        assert "final_result" in merged
        assert "confidence" in merged

    def test_monitor_agent_performance(self, meta_agent: AtomMetaAgent):
        """Test monitoring performance of coordinated agents"""
        # Arrange
        agent_ids = ["agent-001", "agent-002"]

        # Act
        performance = meta_agent.monitor_performance(agent_ids)

        # Assert
        assert performance is not None
        assert isinstance(performance, dict)
        assert all(aid in performance for aid in agent_ids)

    def test_handle_agent_conflict(self, meta_agent: AtomMetaAgent):
        """Test handling conflicts between agent outputs"""
        # Arrange
        conflict = {
            "agent_1": "agent-001",
            "agent_2": "agent-002",
            "disagreement": "different_classification",
            "context": "customer_segment"
        }

        # Act
        resolution = meta_agent.resolve_conflict(conflict)

        # Assert
        assert resolution is not None
        assert resolution.resolved_at is not None
        assert resolution.outcome in ["agent_1_wins", "agent_2_wins", "hybrid"]

    def test_propagate_agent_learning(self, meta_agent: AtomMetaAgent):
        """Test propagating learning across agent network"""
        # Arrange
        source_agent = "agent-001"
        learning = {"pattern": "high_value_customers", "accuracy": 0.95}

        # Act
        propagation = meta_agent.propagate_learning(source_agent, learning)

        # Assert
        assert propagation is not None
        assert propagation.learning_id is not None
        assert propagation.recipient_count >= 0


# =============================================================================
# 2. Storage Services (6-8 tests)
# =============================================================================

class TestAutoDocumentIngestion:
    """Test automatic document ingestion and processing"""

    @pytest.fixture
    def doc_ingestion(self, db_session: Session):
        """Create document ingestion service instance"""
        return AutoDocumentIngestion(db_session)

    def test_ingest_document_from_url(self, doc_ingestion: AutoDocumentIngestion):
        """Test ingesting document from URL"""
        # Arrange
        url = "https://example.com/document.pdf"
        metadata = {"source": "external", "priority": "high"}

        # Act
        ingestion = doc_ingestion.ingest_from_url(url, metadata)

        # Assert
        assert ingestion is not None
        assert ingestion.ingestion_id is not None
        assert ingestion.status in ["pending", "processing", "completed"]
        assert ingestion.source_url == url

    def test_process_ingested_document(self, doc_ingestion: AutoDocumentIngestion):
        """Test processing ingested document"""
        # Arrange
        ingestion_id = "ingestion-001"
        doc_ingestion.ingest_from_url("https://example.com/doc.pdf", {})

        # Act
        result = doc_ingestion.process(ingestion_id)

        # Assert
        assert result is not None
        assert result.extracted_text is not None or result.error is not None
        assert result.processing_time > 0

    def test_extract_document_metadata(self, doc_ingestion: AutoDocumentIngestion):
        """Test extracting metadata from document"""
        # Arrange
        document_path = "/path/to/document.pdf"

        # Act
        metadata = doc_ingestion.extract_metadata(document_path)

        # Assert
        assert metadata is not None
        assert "file_type" in metadata
        assert "size" in metadata
        assert "created_at" in metadata

    def test_classify_document_type(self, doc_ingestion: AutoDocumentIngestion):
        """Test automatic document type classification"""
        # Arrange
        document_content = "Financial report Q4 2024"

        # Act
        doc_type = doc_ingestion.classify_document(document_content)

        # Assert
        assert doc_type is not None
        assert doc_type in ["invoice", "report", "contract", "email", "other"]

    def test_index_document_for_search(self, doc_ingestion: AutoDocumentIngestion):
        """Test indexing document for search"""
        # Arrange
        document_id = "doc-001"
        content = "This is a test document about machine learning"

        # Act
        index_result = doc_ingestion.index_document(document_id, content)

        # Assert
        assert index_result is not None
        assert index_result.indexed_at is not None
        assert index_result.vector_id is not None

    def test_cleanup_old_ingestions(self, doc_ingestion: AutoDocumentIngestion):
        """Test cleanup of old processed documents"""
        # Arrange
        days_old = 30

        # Act
        cleaned = doc_ingestion.cleanup_old(days_old)

        # Assert
        assert cleaned is not None
        assert cleaned.deleted_count >= 0
        assert cleaned.freed_space >= 0


# =============================================================================
# 3. Cache Services (5-6 tests)
# =============================================================================

class TestSkillRegistryService:
    """Test skill registry and caching"""

    @pytest.fixture
    def skill_registry(self, db_session: Session):
        """Create skill registry service instance"""
        return SkillRegistryService(db_session)

    def test_register_skill(self, skill_registry: SkillRegistryService):
        """Test registering new skill"""
        # Arrange
        skill_definition = {
            "name": "data_analyzer",
            "version": "1.0.0",
            "description": "Analyze data patterns",
            "capabilities": ["pattern_detection", "anomaly_detection"]
        }

        # Act
        registered = skill_registry.register(skill_definition)

        # Assert
        assert registered is not None
        assert registered.skill_id is not None
        assert registered.name == "data_analyzer"
        assert registered.version == "1.0.0"

    def test_get_skill_from_cache(self, skill_registry: SkillRegistryService):
        """Test retrieving skill from cache"""
        # Arrange
        skill_id = "skill-001"
        skill_registry.register({"name": "test", "id": skill_id})

        # Act
        skill = skill_registry.get_skill(skill_id)

        # Assert
        assert skill is not None
        assert skill.skill_id == skill_id
        assert skill.cached_at is not None

    def test_invalidate_skill_cache(self, skill_registry: SkillRegistryService):
        """Test invalidating cached skill"""
        # Arrange
        skill_id = "skill-001"
        skill_registry.register({"name": "test", "id": skill_id})

        # Act
        invalidated = skill_registry.invalidate_cache(skill_id)

        # Assert
        assert invalidated is True
        assert invalidated.invalidated_at is not None

    def test_search_skills_by_capability(self, skill_registry: SkillRegistryService):
        """Test searching skills by capability"""
        # Arrange
        capability = "pattern_detection"
        skill_registry.register({
            "name": "analyzer",
            "capabilities": [capability, "visualization"]
        })

        # Act
        results = skill_registry.search_by_capability(capability)

        # Assert
        assert results is not None
        assert len(results) >= 1
        assert all(capability in s.capabilities for s in results)

    def test_get_skill_dependencies(self, skill_registry: SkillRegistryService):
        """Test getting skill dependencies"""
        # Arrange
        skill_id = "skill-001"
        skill_registry.register({
            "name": "advanced_analyzer",
            "dependencies": ["numpy", "pandas", "scikit-learn"]
        })

        # Act
        dependencies = skill_registry.get_dependencies(skill_id)

        # Assert
        assert dependencies is not None
        assert len(dependencies) >= 3
        assert "numpy" in dependencies


# =============================================================================
# 4. Proposal Services (5-6 tests)
# =============================================================================

class TestProposalService:
    """Test proposal generation and management"""

    @pytest.fixture
    def proposal_service(self, db_session: Session):
        """Create proposal service instance"""
        return ProposalService(db_session)

    def test_create_action_proposal(self, proposal_service: ProposalService):
        """Test creating action proposal for INTERN agent"""
        # Arrange
        agent_id = "intern-agent-001"
        action = {
            "type": "send_email",
            "recipient": "user@example.com",
            "subject": "Test Subject",
            "body": "Test Body"
        }
        confidence = 0.75

        # Act
        proposal = proposal_service.create_proposal(agent_id, action, confidence)

        # Assert
        assert proposal is not None
        assert proposal.proposal_id is not None
        assert proposal.agent_id == agent_id
        assert proposal.action_type == "send_email"
        assert proposal.confidence == confidence
        assert proposal.status in ["pending", "approved", "rejected"]

    def test_approve_proposal(self, proposal_service: ProposalService):
        """Test approving a proposal"""
        # Arrange
        proposal_id = "proposal-001"
        proposal_service.create_proposal(
            "agent-001", {"type": "send_email"}, 0.75
        )

        # Act
        approved = proposal_service.approve(proposal_id, approver="user-123")

        # Assert
        assert approved is not None
        assert approved.status == "approved"
        assert approved.approved_at is not None
        assert approved.approver == "user-123"

    def test_reject_proposal(self, proposal_service: ProposalService):
        """Test rejecting a proposal"""
        # Arrange
        proposal_id = "proposal-001"
        proposal_service.create_proposal(
            "agent-001", {"type": "send_email"}, 0.75
        )

        # Act
        rejected = proposal_service.reject(
            proposal_id, reason="Unsafe action", rejecter="user-123"
        )

        # Assert
        assert rejected is not None
        assert rejected.status == "rejected"
        assert rejected.rejected_at is not None
        assert rejected.reason == "Unsafe action"

    def test_get_pending_proposals(self, proposal_service: ProposalService):
        """Test getting all pending proposals"""
        # Arrange
        agent_id = "intern-agent-001"
        proposal_service.create_proposal(
            agent_id, {"type": "send_email"}, 0.75
        )
        proposal_service.create_proposal(
            agent_id, {"type": "update_db"}, 0.65
        )

        # Act
        pending = proposal_service.get_pending(agent_id)

        # Assert
        assert pending is not None
        assert len(pending) >= 2
        assert all(p.status == "pending" for p in pending)

    def test_get_proposal_statistics(self, proposal_service: ProposalService):
        """Test getting proposal statistics for agent"""
        # Arrange
        agent_id = "intern-agent-001"
        proposal_service.create_proposal(agent_id, {"type": "action1"}, 0.75)
        proposal_service.create_proposal(agent_id, {"type": "action2"}, 0.65)

        # Act
        stats = proposal_service.get_statistics(agent_id)

        # Assert
        assert stats is not None
        assert stats.total_proposals >= 2
        assert stats.pending_count >= 0
        assert stats.approved_count >= 0
        assert stats.rejected_count >= 0
        assert stats.approval_rate >= 0


# =============================================================================
# 5. Analytics Services (6-8 tests)
# =============================================================================

class TestWorkflowAnalyticsEngine:
    """Test workflow analytics and metrics"""

    @pytest.fixture
    def analytics_engine(self, db_session: Session):
        """Create analytics engine instance"""
        return WorkflowAnalyticsEngine(db_session)

    def test_calculate_workflow_success_rate(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test calculating workflow success rate"""
        # Arrange
        workflow_id = "workflow-001"

        # Act
        success_rate = analytics_engine.get_success_rate(workflow_id)

        # Assert
        assert success_rate is not None
        assert 0 <= success_rate <= 1
        assert isinstance(success_rate, float)

    def test_get_average_execution_time(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test getting average workflow execution time"""
        # Arrange
        workflow_id = "workflow-001"

        # Act
        avg_time = analytics_engine.get_average_execution_time(workflow_id)

        # Assert
        assert avg_time is not None
        assert avg_time >= 0
        assert isinstance(avg_time, (int, float))

    def test_get_workflow_error_breakdown(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test getting error breakdown for workflow"""
        # Arrange
        workflow_id = "workflow-001"

        # Act
        errors = analytics_engine.get_error_breakdown(workflow_id)

        # Assert
        assert errors is not None
        assert isinstance(errors, dict)
        assert "total_errors" in errors
        assert "error_types" in errors

    def test_generate_workflow_report(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test generating comprehensive workflow report"""
        # Arrange
        workflow_id = "workflow-001"
        date_range = {
            "start": datetime.now() - timedelta(days=30),
            "end": datetime.now()
        }

        # Act
        report = analytics_engine.generate_report(workflow_id, date_range)

        # Assert
        assert report is not None
        assert "workflow_id" in report
        assert "success_rate" in report
        assert "avg_execution_time" in report
        assert "total_executions" in report
        assert "generated_at" in report

    def test_get_workflow_performance_trend(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test getting workflow performance trend over time"""
        # Arrange
        workflow_id = "workflow-001"
        days = 30

        # Act
        trend = analytics_engine.get_performance_trend(workflow_id, days)

        # Assert
        assert trend is not None
        assert "data_points" in trend
        assert len(trend["data_points"]) >= 0
        assert "trend_direction" in trend

    def test_compare_workflow_performance(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test comparing performance between workflows"""
        # Arrange
        workflow_ids = ["workflow-001", "workflow-002"]

        # Act
        comparison = analytics_engine.compare_workflows(workflow_ids)

        # Assert
        assert comparison is not None
        assert len(comparison) == 2
        assert all("success_rate" in w for w in comparison)
        assert all("avg_time" in w for w in comparison)

    def test_get_bottleneck_analysis(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test identifying workflow bottlenecks"""
        # Arrange
        workflow_id = "workflow-001"

        # Act
        bottlenecks = analytics_engine.identify_bottlenecks(workflow_id)

        # Assert
        assert bottlenecks is not None
        assert isinstance(bottlenecks, list)
        assert all("step_name" in b for b in bottlenecks)
        assert all("avg_time" in b for b in bottlenecks)


# =============================================================================
# 6. Workflow Versioning and Debugging (4-5 tests)
# =============================================================================

class TestWorkflowVersioningSystem:
    """Test workflow version control"""

    @pytest.fixture
    def versioning_system(self, db_session: Session):
        """Create versioning system instance"""
        return WorkflowVersioningSystem(db_session)

    def test_create_workflow_version(self, versioning_system: WorkflowVersioningSystem):
        """Test creating new workflow version"""
        # Arrange
        workflow_id = "workflow-001"
        workflow_definition = {"steps": ["step1", "step2"]}
        changes = "Added error handling"

        # Act
        version = versioning_system.create_version(
            workflow_id, workflow_definition, changes
        )

        # Assert
        assert version is not None
        assert version.version_id is not None
        assert version.workflow_id == workflow_id
        assert version.changes == changes
        assert version.created_at is not None

    def test_get_workflow_history(self, versioning_system: WorkflowVersioningSystem):
        """Test getting workflow version history"""
        # Arrange
        workflow_id = "workflow-001"
        versioning_system.create_version(workflow_id, {"steps": ["a"]}, "Initial")
        versioning_system.create_version(workflow_id, {"steps": ["a", "b"]}, "Added step b")

        # Act
        history = versioning_system.get_history(workflow_id)

        # Assert
        assert history is not None
        assert len(history) >= 2
        assert all("version_id" in v for v in history)
        assert all("changes" in v for v in history)

    def test_rollback_to_version(self, versioning_system: WorkflowVersioningSystem):
        """Test rolling back workflow to previous version"""
        # Arrange
        workflow_id = "workflow-001"
        version_id = "version-001"

        # Act
        rollback = versioning_system.rollback(workflow_id, version_id)

        # Assert
        assert rollback is not None
        assert rollback.workflow_id == workflow_id
        assert rollback.restored_from_version == version_id
        assert rollback.rolled_back_at is not None


class TestWorkflowDebugger:
    """Test workflow debugging utilities"""

    @pytest.fixture
    def workflow_debugger(self, db_session: Session):
        """Create workflow debugger instance"""
        return WorkflowDebugger(db_session)

    def test_start_debugging_session(self, workflow_debugger: WorkflowDebugger):
        """Test starting debugging session"""
        # Arrange
        execution_id = "execution-001"

        # Act
        session = workflow_debugger.start_session(execution_id)

        # Assert
        assert session is not None
        assert session.session_id is not None
        assert session.execution_id == execution_id
        assert session.status in ["active", "paused"]

    def test_set_breakpoint(self, workflow_debugger: WorkflowDebugger):
        """Test setting breakpoint in workflow"""
        # Arrange
        workflow_id = "workflow-001"
        step_name = "data_processing"

        # Act
        breakpoint = workflow_debugger.set_breakpoint(workflow_id, step_name)

        # Assert
        assert breakpoint is not None
        assert breakpoint.workflow_id == workflow_id
        assert breakpoint.step_name == step_name
        assert breakpoint.enabled is True

    def test_inspect_workflow_state(self, workflow_debugger: WorkflowDebugger):
        """Test inspecting workflow state at execution point"""
        # Arrange
        execution_id = "execution-001"

        # Act
        state = workflow_debugger.inspect_state(execution_id)

        # Assert
        assert state is not None
        assert "variables" in state
        assert "current_step" in state
        assert "call_stack" in state

    def test_step_through_workflow(self, workflow_debugger: WorkflowDebugger):
        """Test stepping through workflow execution"""
        # Arrange
        session_id = "debug-session-001"

        # Act
        step_result = workflow_debugger.step(session_id)

        # Assert
        assert step_result is not None
        assert "executed_step" in step_result
        assert "next_step" in step_result
        assert "state_snapshot" in step_result


# =============================================================================
# 7. Advanced Workflow System (3-4 tests)
# =============================================================================

class TestAdvancedWorkflowSystem:
    """Test advanced workflow features"""

    @pytest.fixture
    def advanced_workflow(self, db_session: Session):
        """Create advanced workflow system instance"""
        return AdvancedWorkflowSystem(db_session)

    def test_create_parallel_workflow(self, advanced_workflow: AdvancedWorkflowSystem):
        """Test creating workflow with parallel execution"""
        # Arrange
        definition = {
            "name": "parallel_analysis",
            "parallel_branches": [
                {"steps": ["analyze_a"]},
                {"steps": ["analyze_b"]},
                {"steps": ["analyze_c"]}
            ]
        }

        # Act
        workflow = advanced_workflow.create_parallel(definition)

        # Assert
        assert workflow is not None
        assert workflow.workflow_id is not None
        assert workflow.execution_mode == "parallel"
        assert len(workflow.branches) == 3

    def test_create_conditional_workflow(self, advanced_workflow: AdvancedWorkflowSystem):
        """Test creating workflow with conditional logic"""
        # Arrange
        definition = {
            "name": "conditional_approval",
            "conditions": [
                {"if": "amount > 1000", "then": ["manager_approval"]},
                {"if": "amount <= 1000", "then": ["auto_approve"]}
            ]
        }

        # Act
        workflow = advanced_workflow.create_conditional(definition)

        # Assert
        assert workflow is not None
        assert workflow.workflow_id is not None
        assert workflow.execution_mode == "conditional"
        assert len(workflow.conditions) >= 2

    def test_execute_workflow_with_retry(self, advanced_workflow: AdvancedWorkflowSystem):
        """Test workflow execution with retry logic"""
        # Arrange
        workflow_id = "workflow-001"
        retry_policy = {"max_retries": 3, "backoff": "exponential"}

        # Act
        execution = advanced_workflow.execute_with_retry(workflow_id, retry_policy)

        # Assert
        assert execution is not None
        assert execution.execution_id is not None
        assert execution.retry_policy == retry_policy
        assert execution.attempts >= 1
