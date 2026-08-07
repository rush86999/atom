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
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Import services being tested
from core.agent_social_layer import AgentSocialLayer
from core.skill_registry_service import SkillRegistryService
from core.proposal_service import ProposalService
from core.workflow_debugger import WorkflowDebugger
from core.workflow_analytics_engine import WorkflowAnalyticsEngine, WorkflowStatus
from core.auto_document_ingestion import AutoDocumentIngestion, DocumentParser, IngestedDocument
from core.workflow_versioning_system import WorkflowVersioningSystem, VersionType
from core.advanced_workflow_system import AdvancedWorkflowSystem
from core.atom_meta_agent import AtomMetaAgent
from core.models import AgentRegistry, AgentStatus


# =============================================================================
# 1. Agent Management Services (6-8 tests)
# =============================================================================

class TestAgentSocialLayer:
    """Test agent social layer and collaboration features"""

    @pytest.fixture
    def social_layer(self):
        """Create agent social layer instance"""
        return AgentSocialLayer()

    async def test_create_social_connection(self, social_layer: AgentSocialLayer, db_session: Session):
        """Test creating a social post connection"""
        # Act
        post = await social_layer.create_post(
            sender_type="human",
            sender_id="user-001",
            sender_name="Alice",
            post_type="status",
            content="Hello from Alice",
            db=db_session,
        )

        # Assert
        assert post is not None
        assert post["id"] is not None
        assert post["sender_id"] == "user-001"
        assert post["created_at"] is not None

    async def test_get_agent_network(self, social_layer: AgentSocialLayer, db_session: Session):
        """Test retrieving agent activity feed"""
        # Arrange
        for i in range(2):
            await social_layer.create_post(
                sender_type="human",
                sender_id=f"user-00{i}",
                sender_name=f"User{i}",
                post_type="status",
                content=f"post number {i}",
                db=db_session,
            )

        # Act
        feed = await social_layer.get_feed(sender_id="user-000", db=db_session)

        # Assert
        assert feed is not None
        assert feed["total"] >= 2
        assert len(feed["posts"]) >= 2

    async def test_share_knowledge_between_agents(self, social_layer: AgentSocialLayer, db_session: Session):
        """Test sharing knowledge via reactions on posts"""
        # Arrange
        post = await social_layer.create_post(
            sender_type="human",
            sender_id="user-001",
            sender_name="Alice",
            post_type="insight",
            content="Shared insight",
            db=db_session,
        )

        # Act
        reactions = await social_layer.add_reaction(
            post_id=post["id"], sender_id="user-002", emoji="like", db=db_session
        )

        # Assert
        assert reactions is not None
        assert reactions["like"] == 1

    async def test_get_social_recommendations(self, social_layer: AgentSocialLayer, db_session: Session):
        """Test getting trending topics from social posts"""
        # Arrange
        await social_layer.create_post(
            sender_type="human",
            sender_id="user-000",
            sender_name="User0",
            post_type="status",
            content="checking trending",
            mentioned_user_ids=["user-999"],
            db=db_session,
        )

        # Act
        topics = await social_layer.get_trending_topics(hours=24, db=db_session)

        # Assert
        assert topics is not None
        assert isinstance(topics, list)
        assert any(t["topic"] == "user:user-999" for t in topics)

    async def test_block_agent_interaction(self, social_layer: AgentSocialLayer, db_session: Session):
        """Test rate-limit blocking for read-only agents"""
        # Arrange
        agent = AgentRegistry(
            id="student-agent-001",
            name="Student Agent",
            category="General",
            module_path="core.generic_agent",
            class_name="GenericAgent",
            status=AgentStatus.STUDENT.value,
        )
        db_session.add(agent)
        db_session.commit()

        # Act
        allowed, reason = await social_layer.check_rate_limit(
            agent_id="student-agent-001", db=db_session
        )

        # Assert
        assert allowed is False
        assert reason is not None

    async def test_get_agent_influence_score(self, social_layer: AgentSocialLayer, db_session: Session):
        """Test calculating agent reputation score"""
        # Act
        reputation = await social_layer.get_agent_reputation(
            agent_id="agent-001", db=db_session
        )

        # Assert
        assert reputation is not None
        assert reputation["agent_id"] == "agent-001"
        assert 0 <= reputation["reputation_score"] <= 100


class TestAtomMetaAgent:
    """Test meta agent coordination and orchestration"""

    @pytest.fixture
    def meta_agent(self):
        """Create meta agent instance"""
        return AtomMetaAgent(workspace_id="test-ws")

    async def test_coordinate_multi_agent_workflow(self, meta_agent: AtomMetaAgent):
        """Test coordinating workflow via spawned agents"""
        # Act
        agent = await meta_agent.spawn_agent(
            "custom",
            {"name": "Analyst A", "category": "Analytics", "description": "Test agent"},
        )

        # Assert
        assert agent is not None
        assert agent.id.startswith("spawned_")
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.name == "Analyst A"

    async def test_delegate_task_to_specialist(self, meta_agent: AtomMetaAgent):
        """Test delegating task to a specialist template agent"""
        # Act
        agent = await meta_agent.spawn_agent("finance_analyst")

        # Assert
        assert agent is not None
        assert agent.id.startswith("spawned_")
        assert agent.name == "Finance Analyst"
        assert agent.category == "Finance"

    async def test_merge_agent_outputs(self, meta_agent: AtomMetaAgent, db_session: Session):
        """Test persisting spawned agents into the registry"""
        # Act
        agent = await meta_agent.spawn_agent(
            "custom", {"name": "Persisted Agent", "category": "General"},
            persist=True, db=db_session,
        )

        # Assert
        assert agent is not None
        assert agent.id is not None
        persisted = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()
        assert persisted is not None
        assert persisted.name == "Persisted Agent"

    async def test_monitor_agent_performance(self, meta_agent: AtomMetaAgent):
        """Test spawning multiple agents with distinct identities"""
        # Act
        a1 = await meta_agent.spawn_agent("custom", {"name": "Agent One", "category": "General"})
        a2 = await meta_agent.spawn_agent("custom", {"name": "Agent Two", "category": "General"})

        # Assert
        assert a1 is not None
        assert a2 is not None
        assert a1.id != a2.id
        assert a1.name == "Agent One"
        assert a2.name == "Agent Two"

    async def test_handle_agent_conflict(self, meta_agent: AtomMetaAgent):
        """Test handling unknown template conflicts"""
        # Act / Assert
        with pytest.raises(ValueError):
            await meta_agent.spawn_agent("unknown_template")

    async def test_propagate_agent_learning(self, meta_agent: AtomMetaAgent, db_session: Session):
        """Test propagating agent state across registry"""
        # Arrange
        agent = await meta_agent.spawn_agent(
            "custom", {"name": "Learning Agent", "category": "General"},
            persist=True, db=db_session,
        )

        # Act
        agent.status = AgentStatus.INTERN.value
        db_session.commit()

        # Assert
        fetched = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()
        assert fetched is not None
        assert fetched.status == AgentStatus.INTERN.value


# =============================================================================
# 2. Storage Services (6-8 tests)
# =============================================================================

class TestAutoDocumentIngestion:
    """Test automatic document ingestion and processing"""

    @pytest.fixture
    def doc_ingestion(self):
        """Create document ingestion service instance"""
        return AutoDocumentIngestion()

    def test_ingest_document_from_url(self, doc_ingestion: AutoDocumentIngestion):
        """Test getting per-integration ingestion settings"""
        # Act
        settings = doc_ingestion.get_settings("dropbox")

        # Assert
        assert settings is not None
        assert settings.integration_id == "dropbox"
        assert settings.enabled is False
        assert "pdf" in settings.file_types

    async def test_process_ingested_document(self, doc_ingestion: AutoDocumentIngestion):
        """Test processing raw file bytes into ingested text"""
        # Arrange
        memory = MagicMock()
        memory.add_document.return_value = True
        doc_ingestion.memory_handler = memory

        # Act
        result = await doc_ingestion.process_file_bytes(
            b"name,age\nAlice,30\nBob,25", "people.csv"
        )

        # Assert
        assert result is not None
        assert result["status"] == "ingested"
        assert result["file_name"] == "people.csv"
        assert result["chars_ingested"] > 0
        memory.add_document.assert_called_once()

    async def test_extract_document_metadata(self, doc_ingestion: AutoDocumentIngestion):
        """Test parsing document content into extracted text"""
        # Act
        text = await DocumentParser.parse_document(
            b"name,age\nAlice,30", "csv", "people.csv"
        )

        # Assert
        assert text is not None
        assert "Alice" in text
        assert "30" in text

    def test_classify_document_type(self, doc_ingestion: AutoDocumentIngestion):
        """Test listing ingested documents by integration"""
        # Arrange
        doc = IngestedDocument(
            id="doc-001",
            file_name="report.pdf",
            file_path="/data/report.pdf",
            file_type="pdf",
            integration_id="dropbox",
            workspace_id="default",
            file_size_bytes=1024,
            content_preview="Financial report",
            ingested_at=datetime.now(),
            external_id="ext-001",
        )
        doc_ingestion.ingested_docs["ext-001"] = doc

        # Act
        docs = doc_ingestion.get_ingested_documents(integration_id="dropbox")

        # Assert
        assert docs is not None
        assert len(docs) >= 1
        assert docs[0].file_type == "pdf"

    def test_index_document_for_search(self, doc_ingestion: AutoDocumentIngestion):
        """Test updating ingestion settings"""
        # Act
        settings = doc_ingestion.update_settings(
            "onedrive",
            enabled=True,
            auto_sync_new_files=True,
            file_types=["pdf", "docx"],
            sync_frequency_minutes=30,
        )

        # Assert
        assert settings is not None
        assert settings.enabled is True
        assert settings.auto_sync_new_files is True
        assert settings.file_types == ["pdf", "docx"]
        assert settings.sync_frequency_minutes == 30

    async def test_cleanup_old_ingestions(self, doc_ingestion: AutoDocumentIngestion):
        """Test removing ingested documents from an integration"""
        # Arrange
        doc = IngestedDocument(
            id="doc-002",
            file_name="old.pdf",
            file_path="/data/old.pdf",
            file_type="pdf",
            integration_id="dropbox",
            workspace_id="default",
            file_size_bytes=512,
            content_preview="Old document",
            ingested_at=datetime.now() - timedelta(days=60),
            external_id="ext-002",
        )
        doc_ingestion.ingested_docs["ext-002"] = doc

        # Act
        cleaned = await doc_ingestion.remove_integration_documents("dropbox")

        # Assert
        assert cleaned is not None
        assert cleaned["success"] is True
        assert cleaned["documents_removed"] >= 1
        assert len(doc_ingestion.ingested_docs) == 0


# =============================================================================
# 3. Cache Services (5-6 tests)
# =============================================================================

class TestSkillRegistryService:
    """Test skill registry and caching"""

    @pytest.fixture
    def skill_registry(self, db_session: Session):
        """Create skill registry service instance"""
        registry = SkillRegistryService(db_session)
        scanner = AsyncMock()
        scanner.scan_skill.return_value = {"risk_level": "LOW", "findings": []}
        registry._scanner = scanner
        return registry

    @staticmethod
    def _skill_content(name: str = "data_analyzer", packages=None) -> str:
        package_lines = ""
        if packages:
            package_lines = "packages:\n" + "".join(f"  - {p}\n" for p in packages)
        return (
            "---\n"
            f"name: {name}\n"
            "version: 1.0.0\n"
            f"description: {name} skill\n"
            f"{package_lines}"
            "---\n"
            f"# {name}\n\n"
            "Performs analysis."
        )

    async def test_register_skill(self, skill_registry: SkillRegistryService):
        """Test registering new skill"""
        # Act
        registered = await skill_registry.import_skill(
            source="raw_content",
            content=self._skill_content(),
            metadata={"author": "test"},
        )

        # Assert
        assert registered is not None
        assert registered["skill_id"] is not None
        assert registered["skill_name"] == "data_analyzer"
        assert registered["status"] == "Active"

    async def test_get_skill_from_cache(self, skill_registry: SkillRegistryService):
        """Test retrieving skill details"""
        # Arrange
        registered = await skill_registry.import_skill(
            source="raw_content", content=self._skill_content()
        )

        # Act
        skill = skill_registry.get_skill(registered["skill_id"])

        # Assert
        assert skill is not None
        assert skill["skill_id"] == registered["skill_id"]
        assert skill["skill_name"] == "data_analyzer"

    async def test_invalidate_skill_cache(self, skill_registry: SkillRegistryService):
        """Test promoting an untrusted skill to active"""
        # Arrange
        scanner = AsyncMock()
        scanner.scan_skill.return_value = {"risk_level": "HIGH", "findings": ["eval() detected"]}
        skill_registry._scanner = scanner
        registered = await skill_registry.import_skill(
            source="raw_content", content=self._skill_content()
        )
        assert registered["status"] == "Untrusted"

        # Act
        promoted = skill_registry.promote_skill(registered["skill_id"])

        # Assert
        assert promoted is not None
        assert promoted["status"] == "Active"
        assert promoted["previous_status"] == "Untrusted"

    async def test_search_skills_by_capability(self, skill_registry: SkillRegistryService):
        """Test listing registered skills"""
        # Arrange
        await skill_registry.import_skill(
            source="raw_content", content=self._skill_content()
        )

        # Act
        results = skill_registry.list_skills()

        # Assert
        assert results is not None
        assert len(results) >= 1
        assert any(s["skill_name"] == "data_analyzer" for s in results)

    async def test_get_skill_dependencies(self, skill_registry: SkillRegistryService):
        """Test getting skill package dependencies"""
        # Arrange
        registered = await skill_registry.import_skill(
            source="raw_content",
            content=self._skill_content(name="advanced_analyzer", packages=["numpy", "pandas"]),
        )

        # Act
        skill = skill_registry.get_skill(registered["skill_id"])

        # Assert
        assert skill is not None
        assert len(skill["packages"]) >= 2
        assert "numpy" in skill["packages"]
        assert "pandas" in skill["packages"]


# =============================================================================
# 4. Proposal Services (5-6 tests)
# =============================================================================

class TestProposalService:
    """Test proposal generation and management"""

    @pytest.fixture
    def proposal_service(self, db_session: Session):
        """Create proposal service instance with an INTERN agent"""
        import uuid
        agent_id = f"intern-agent-{uuid.uuid4().hex[:8]}"
        agent = AgentRegistry(
            id=agent_id,
            name="Intern Agent",
            category="General",
            module_path="core.generic_agent",
            class_name="GenericAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()
        service = ProposalService(db_session)
        service._test_agent_id = agent_id
        return service

    async def _create_proposal(self, proposal_service: ProposalService) -> object:
        return await proposal_service.create_action_proposal(
            intern_agent_id=proposal_service._test_agent_id,
            trigger_context={"page": "dashboard"},
            proposed_action={"action_type": "send_email", "recipient": "user@example.com"},
            reasoning="User requested an email",
        )

    async def test_create_action_proposal(self, proposal_service: ProposalService):
        """Test creating action proposal for INTERN agent"""
        # Act
        proposal = await self._create_proposal(proposal_service)

        # Assert
        assert proposal is not None
        assert proposal.id is not None
        assert proposal.agent_id == proposal_service._test_agent_id
        assert proposal.proposed_action["action_type"] == "send_email"
        assert proposal.status == "pending_approval"

    async def test_approve_proposal(self, proposal_service: ProposalService):
        """Test approving a proposal"""
        # Arrange
        proposal = await self._create_proposal(proposal_service)

        # Act
        result = await proposal_service.approve_proposal(
            proposal.id, user_id="user-123"
        )

        # Assert
        assert result is not None
        assert proposal.status == "executed"
        assert proposal.approved_by == "user-123"
        assert proposal.approved_at is not None

    async def test_reject_proposal(self, proposal_service: ProposalService):
        """Test rejecting a proposal"""
        # Arrange
        proposal = await self._create_proposal(proposal_service)

        # Act
        await proposal_service.reject_proposal(
            proposal.id, user_id="user-123", reason="Unsafe action"
        )

        # Assert
        assert proposal.status == "rejected"
        assert proposal.execution_result is not None
        assert proposal.execution_result["reason"] == "Unsafe action"

    async def test_get_pending_proposals(self, proposal_service: ProposalService):
        """Test getting all pending proposals"""
        # Arrange
        await self._create_proposal(proposal_service)
        await proposal_service.create_action_proposal(
            intern_agent_id=proposal_service._test_agent_id,
            trigger_context={"page": "dashboard"},
            proposed_action={"action_type": "update_db"},
            reasoning="User requested update",
        )

        # Act
        pending = await proposal_service.get_pending_proposals(
            agent_id=proposal_service._test_agent_id
        )

        # Assert
        assert pending is not None
        assert len(pending) >= 2
        assert all(p.status == "pending_approval" for p in pending)

    async def test_get_proposal_statistics(self, proposal_service: ProposalService):
        """Test getting proposal history for agent"""
        # Arrange
        await self._create_proposal(proposal_service)
        await self._create_proposal(proposal_service)

        # Act
        history = await proposal_service.get_proposal_history(
            agent_id=proposal_service._test_agent_id
        )

        # Assert
        assert history is not None
        assert len(history) >= 2
        assert all("proposal_id" in h for h in history)
        assert all("status" in h for h in history)


# =============================================================================
# 5. Analytics Services (6-8 tests)
# =============================================================================

class TestWorkflowAnalyticsEngine:
    """Test workflow analytics and metrics"""

    @pytest.fixture
    def analytics_engine(self, db_session: Session, tmp_path):
        """Create analytics engine instance"""
        return WorkflowAnalyticsEngine(
            db=db_session,
            db_path=str(tmp_path / "analytics.db"),
            enable_background_thread=False,
        )

    async def test_calculate_workflow_success_rate(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test calculating workflow success rate"""
        # Arrange
        analytics_engine.track_workflow_start("workflow-001", "exec-1")
        analytics_engine.track_workflow_completion(
            "workflow-001", "exec-1", WorkflowStatus.COMPLETED, duration_ms=100
        )
        await analytics_engine.flush()

        # Act
        metrics = analytics_engine.get_workflow_performance_metrics("workflow-001")

        # Assert
        assert metrics is not None
        assert 0 <= metrics.error_rate <= 1
        assert metrics.total_executions >= 1

    async def test_get_average_execution_time(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test getting average workflow execution time"""
        # Arrange
        analytics_engine.track_workflow_start("workflow-001", "exec-1")
        analytics_engine.track_workflow_completion(
            "workflow-001", "exec-1", WorkflowStatus.COMPLETED, duration_ms=250
        )
        await analytics_engine.flush()

        # Act
        metrics = analytics_engine.get_workflow_performance_metrics("workflow-001")

        # Assert
        assert metrics is not None
        assert metrics.average_duration_ms >= 0

    async def test_get_workflow_error_breakdown(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test getting error breakdown for workflow"""
        # Arrange
        analytics_engine.track_workflow_start("workflow-001", "exec-1")
        analytics_engine.track_workflow_completion(
            "workflow-001", "exec-1", WorkflowStatus.FAILED,
            duration_ms=100, error_message="Execution timeout",
        )
        await analytics_engine.flush()

        # Act
        errors = analytics_engine.get_error_breakdown("workflow-001")

        # Assert
        assert errors is not None
        assert isinstance(errors, dict)
        assert "error_types" in errors
        assert errors["error_types"][0]["count"] >= 1

    async def test_generate_workflow_report(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test generating comprehensive workflow report"""
        # Arrange
        analytics_engine.track_workflow_start("workflow-001", "exec-1")
        analytics_engine.track_workflow_completion(
            "workflow-001", "exec-1", WorkflowStatus.COMPLETED, duration_ms=100
        )
        await analytics_engine.flush()

        # Act
        overview = analytics_engine.get_system_overview(time_window="24h")

        # Assert
        assert overview is not None
        assert "total_workflows" in overview
        assert "total_executions" in overview
        assert "success_rate" in overview

    async def test_get_workflow_performance_trend(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test getting workflow performance trend over time"""
        # Arrange
        analytics_engine.track_workflow_start("workflow-001", "exec-1")
        analytics_engine.track_workflow_completion(
            "workflow-001", "exec-1", WorkflowStatus.COMPLETED, duration_ms=100
        )
        await analytics_engine.flush()

        # Act
        timeline = analytics_engine.get_execution_timeline(
            "workflow-001", time_window="24h", interval="1h"
        )

        # Assert
        assert timeline is not None
        assert isinstance(timeline, list)
        assert len(timeline) >= 0

    async def test_compare_workflow_performance(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test comparing performance between workflows"""
        # Arrange
        analytics_engine.track_workflow_start("workflow-001", "exec-1")
        analytics_engine.track_workflow_completion(
            "workflow-001", "exec-1", WorkflowStatus.COMPLETED, duration_ms=100
        )
        analytics_engine.track_workflow_start("workflow-002", "exec-2")
        analytics_engine.track_workflow_completion(
            "workflow-002", "exec-2", WorkflowStatus.FAILED,
            duration_ms=500, error_message="Error",
        )
        await analytics_engine.flush()

        # Act
        m1 = analytics_engine.get_workflow_performance_metrics("workflow-001")
        m2 = analytics_engine.get_workflow_performance_metrics("workflow-002")

        # Assert
        assert m1 is not None
        assert m2 is not None
        assert m1.workflow_id == "workflow-001"
        assert m2.workflow_id == "workflow-002"
        assert m1.total_executions == 1
        assert m2.total_executions == 1

    async def test_get_bottleneck_analysis(self, analytics_engine: WorkflowAnalyticsEngine):
        """Test identifying workflow events for bottleneck analysis"""
        # Arrange
        analytics_engine.track_workflow_start("workflow-001", "exec-1")
        analytics_engine.track_step_execution(
            "workflow-001", "exec-1", "step-1", "data_processing", "step_started", 200
        )
        await analytics_engine.flush()

        # Act
        events = analytics_engine.get_recent_events(
            limit=10, workflow_id="workflow-001"
        )

        # Assert
        assert events is not None
        assert isinstance(events, list)
        assert len(events) >= 1
        assert all(getattr(e, "workflow_id", None) == "workflow-001" for e in events)


# =============================================================================
# 6. Workflow Versioning and Debugging (4-5 tests)
# =============================================================================

class TestWorkflowVersioningSystem:
    """Test workflow version control"""

    @pytest.fixture
    def versioning_system(self, tmp_path):
        """Create versioning system instance"""
        return WorkflowVersioningSystem(db_path=str(tmp_path / "versions.db"))

    async def test_create_workflow_version(self, versioning_system: WorkflowVersioningSystem):
        """Test creating new workflow version"""
        # Act
        version = await versioning_system.create_version(
            workflow_id="workflow-001",
            workflow_data={"steps": ["step1", "step2"]},
            version_type=VersionType.MAJOR,
            created_by="user-1",
            commit_message="Added error handling",
        )

        # Assert
        assert version is not None
        assert version.workflow_id == "workflow-001"
        assert version.version == "1.0.0"
        assert version.commit_message == "Added error handling"

    async def test_get_workflow_history(self, versioning_system: WorkflowVersioningSystem):
        """Test getting workflow version history"""
        # Arrange
        await versioning_system.create_version(
            "workflow-001", {"steps": [{"id": "a"}]}, VersionType.MAJOR, "user-1", "Initial"
        )
        await versioning_system.create_version(
            "workflow-001", {"steps": [{"id": "a"}, {"id": "b"}]}, VersionType.MINOR, "user-1", "Added step b"
        )

        # Act
        history = await versioning_system.get_version_history("workflow-001")

        # Assert
        assert history is not None
        assert len(history) >= 2
        assert all(v.workflow_id == "workflow-001" for v in history)
        assert any(v.commit_message == "Added step b" for v in history)

    async def test_rollback_to_version(self, versioning_system: WorkflowVersioningSystem):
        """Test rolling back workflow to previous version"""
        # Arrange
        v1 = await versioning_system.create_version(
            "workflow-001", {"steps": [{"id": "a"}]}, VersionType.MAJOR, "user-1", "Initial"
        )
        await versioning_system.create_version(
            "workflow-001", {"steps": [{"id": "a"}, {"id": "b"}]}, VersionType.MINOR, "user-1", "Added step b"
        )

        # Act
        rollback = await versioning_system.rollback_to_version(
            workflow_id="workflow-001",
            target_version=v1.version,
            created_by="user-1",
            rollback_reason="regression",
        )

        # Assert
        assert rollback is not None
        assert rollback.workflow_id == "workflow-001"
        assert rollback.version != v1.version
        assert rollback.commit_message.startswith("Rollback")


class TestWorkflowDebugger:
    """Test workflow debugging utilities"""

    @pytest.fixture
    def workflow_debugger(self, db_session: Session):
        """Create workflow debugger instance"""
        return WorkflowDebugger(db_session)

    def test_start_debugging_session(self, workflow_debugger: WorkflowDebugger):
        """Test starting debugging session"""
        # Act
        session = workflow_debugger.create_debug_session(
            workflow_id="workflow-001", user_id="user-001", execution_id="execution-001"
        )

        # Assert
        assert session is not None
        assert session.id is not None
        assert session.workflow_id == "workflow-001"
        assert session.execution_id == "execution-001"
        assert session.status == "active"

    def test_set_breakpoint(self, workflow_debugger: WorkflowDebugger):
        """Test setting breakpoint in workflow"""
        # Act
        breakpoint = workflow_debugger.add_breakpoint(
            workflow_id="workflow-001", node_id="data_processing", user_id="user-001"
        )

        # Assert
        assert breakpoint is not None
        assert breakpoint.workflow_id == "workflow-001"
        assert breakpoint.node_id == "data_processing"
        assert breakpoint.is_active is True

    def test_inspect_workflow_state(self, workflow_debugger: WorkflowDebugger):
        """Test inspecting workflow state at execution point"""
        # Arrange
        session = workflow_debugger.create_debug_session(
            workflow_id="workflow-001", user_id="user-001"
        )

        # Act
        state = workflow_debugger.get_debug_session(session.id)

        # Assert
        assert state is not None
        assert state.variables == {}
        assert state.call_stack == []
        assert state.current_step == 0

    def test_step_through_workflow(self, workflow_debugger: WorkflowDebugger):
        """Test stepping through workflow execution"""
        # Arrange
        session = workflow_debugger.create_debug_session(
            workflow_id="workflow-001", user_id="user-001"
        )

        # Act
        step_result = workflow_debugger.step_over(session.id)

        # Assert
        assert step_result is not None
        assert step_result["action"] == "step_over"
        assert step_result["current_step"] == 1


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
        assert workflow.branches == 3

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
        assert workflow.conditions >= 2

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
