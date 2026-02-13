"""
Unit tests for meta_agent_training_orchestrator.py

Tests cover:
- Training proposal generation
- Proposal review
- Training session facilitation
- Scenario template selection
- Capability gap analysis
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.meta_agent_training_orchestrator import (
    MetaAgentTrainingOrchestrator,
    TrainingProposal,
    ProposalReview,
    TrainingResult
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentProposal,
    TrainingSession
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def orchestrator(mock_db):
    """Create MetaAgentTrainingOrchestrator"""
    return MetaAgentTrainingOrchestrator(mock_db)


@pytest.fixture
def sample_agent():
    """Create sample STUDENT agent"""
    agent = AgentRegistry(
        id="student_agent_1",
        name="Student Agent",
        status=AgentStatus.STUDENT,
        agent_type="assistant",
        confidence_score=0.3,
        category="Finance"
    )
    return agent


@pytest.fixture
def sample_intern_agent():
    """Create sample INTERN agent"""
    agent = AgentRegistry(
        id="intern_agent_1",
        name="Intern Agent",
        status=AgentStatus.INTERN,
        agent_type="assistant",
        confidence_score=0.6,
        category="Sales"
    )
    return agent


# ============================================================================
# Service Initialization Tests
# ============================================================================

class TestOrchestratorInitialization:
    """Test orchestrator initialization"""

    def test_orchestrator_init(self, orchestrator, mock_db):
        """Test service initialization"""
        assert orchestrator.db == mock_db
        assert orchestrator.SCENARIO_TEMPLATES is not None
        assert "Finance" in orchestrator.SCENARIO_TEMPLATES
        assert "Sales" in orchestrator.SCENARIO_TEMPLATES

    def test_scenario_templates_structure(self, orchestrator):
        """Test scenario templates have correct structure"""
        for category, template in orchestrator.SCENARIO_TEMPLATES.items():
            assert "name" in template
            assert "scenarios" in template
            assert isinstance(template["scenarios"], list)
            assert len(template["scenarios"]) > 0


# ============================================================================
# Training Proposal Generation Tests
# ============================================================================

class TestTrainingProposalGeneration:
    """Test training proposal generation for STUDENT agents"""

    @pytest.mark.asyncio
    async def test_propose_training_scenario_basic(
        self,
        orchestrator,
        mock_db,
        sample_agent
    ):
        """Test basic training proposal generation"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        blocked_task = {
            "trigger_type": "workflow_automation",
            "action": "execute_workflow"
        }

        proposal = await orchestrator.propose_training_scenario(
            student_agent_id="student_agent_1",
            blocked_task=blocked_task,
            agent_capabilities=["basic_chat"]
        )

        assert proposal is not None
        assert isinstance(proposal, TrainingProposal)
        assert proposal.title is not None
        assert "Training" in proposal.title
        assert len(proposal.learning_objectives) > 0
        assert len(proposal.capability_gaps) > 0
        assert proposal.estimated_duration_hours > 0
        assert len(proposal.training_steps) > 0

    @pytest.mark.asyncio
    async def test_propose_training_scenario_agent_not_found(
        self,
        orchestrator,
        mock_db
    ):
        """Test proposal generation when agent not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError):
            await orchestrator.propose_training_scenario(
                student_agent_id="nonexistent",
                blocked_task={"trigger_type": "workflow"},
                agent_capabilities=[]
            )

    @pytest.mark.asyncio
    async def test_analyze_capability_gaps_workflow(
        self,
        orchestrator,
        sample_agent
    ):
        """Test capability gap analysis for workflow tasks"""
        blocked_task = {
            "trigger_type": "workflow_automation",
            "action": "execute"
        }

        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task=blocked_task,
            agent_capabilities=[],
            agent_category="Finance"
        )

        assert isinstance(gaps, list)
        assert "workflow_automation" in gaps

    @pytest.mark.asyncio
    async def test_analyze_capability_gaps_form(
        self,
        orchestrator,
        sample_agent
    ):
        """Test capability gap analysis for form tasks"""
        blocked_task = {
            "trigger_type": "form_submission",
            "action": "submit"
        }

        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task=blocked_task,
            agent_capabilities=[],
            agent_category="Operations"
        )

        assert "form_processing" in gaps

    @pytest.mark.asyncio
    async def test_analyze_capability_gaps_category_specific(
        self,
        orchestrator,
        sample_agent
    ):
        """Test category-specific capability gaps"""
        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task={"trigger_type": "generic"},
            agent_capabilities=[],
            agent_category="Finance"
        )

        # Should include Finance-specific gaps
        assert any(gap in gaps for gap in ["financial_analysis", "reconciliation", "reporting"])

    def test_select_scenario_template_known_category(self, orchestrator):
        """Test scenario template selection for known category"""
        template = orchestrator._select_scenario_template(
            agent_category="Finance",
            blocked_task={"trigger_type": "workflow"}
        )

        assert template is not None
        assert template["name"] == "Finance Fundamentals"
        assert len(template["scenarios"]) > 0

    def test_select_scenario_template_unknown_category(self, orchestrator):
        """Test scenario template selection for unknown category"""
        template = orchestrator._select_scenario_template(
            agent_category="UnknownCategory",
            blocked_task={"trigger_type": "workflow"}
        )

        # Should return default template
        assert template is not None
        assert "General" in template["name"]

    @pytest.mark.asyncio
    async def test_generate_learning_objectives(
        self,
        orchestrator,
        sample_agent
    ):
        """Test learning objective generation"""
        objectives = await orchestrator._generate_learning_objectives(
            agent=sample_agent,
            blocked_task={"trigger_type": "workflow_automation"},
            capability_gaps=["workflow_automation", "task_coordination"]
        )

        assert isinstance(objectives, list)
        assert len(objectives) > 0
        assert any("workflow_automation" in obj for obj in objectives)

    @pytest.mark.asyncio
    async def test_generate_training_steps(
        self,
        orchestrator
    ):
        """Test training step generation"""
        template = {
            "name": "Finance Training",
            "scenarios": ["Reconciliation", "Analysis"]
        }

        steps = await orchestrator._generate_training_steps(
            scenario_template=template,
            capability_gaps=["reconciliation", "analysis"],
            blocked_task={"trigger_type": "workflow"}
        )

        assert len(steps) > 0
        # Should have intro, walkthrough, practice, and assessment
        assert any(step["type"] == "theory" for step in steps)
        assert any(step["type"] == "practice" for step in steps)
        assert any(step["type"] == "assessment" for step in steps)


# ============================================================================
# Proposal Review Tests
# ============================================================================

class TestProposalReview:
    """Test INTERN agent proposal review"""

    @pytest.mark.asyncio
    async def test_review_intern_proposal_approve(
        self,
        orchestrator,
        mock_db,
        sample_intern_agent
    ):
        """Test proposal review with approval"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_intern_agent

        proposal = Mock(spec=AgentProposal)
        proposal.id = "proposal_1"
        proposal.agent_id = "intern_agent_1"
        proposal.proposed_action = {
            "action_type": "read",
            "target": "customer_data"
        }

        review = await orchestrator.review_intern_proposal(proposal)

        assert review is not None
        assert isinstance(review, ProposalReview)
        assert review.recommendation in ["approve", "modify", "reject"]
        assert 0.0 <= review.confidence <= 1.0
        assert review.reasoning is not None

    @pytest.mark.asyncio
    async def test_review_intern_proposal_high_risk(
        self,
        orchestrator,
        mock_db,
        sample_intern_agent
    ):
        """Test proposal review with high-risk action"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_intern_agent

        proposal = Mock(spec=AgentProposal)
        proposal.id = "proposal_1"
        proposal.agent_id = "intern_agent_1"
        proposal.proposed_action = {
            "action_type": "delete",  # High risk
            "target": "customer_records"
        }

        review = await orchestrator.review_intern_proposal(proposal)

        # Should be rejected or require modification
        assert review.recommendation in ["modify", "reject"]

    @pytest.mark.asyncio
    async def test_review_intern_proposal_medium_risk_low_confidence(
        self,
        orchestrator,
        mock_db
    ):
        """Test proposal review with medium risk and low confidence"""
        agent = AgentRegistry(
            id="agent_1",
            status=AgentStatus.INTERN,
            confidence_score=0.5,  # Low confidence
            category="Sales"
        )

        mock_db.query.return_value.filter.return_value.first.return_value = agent

        proposal = Mock(spec=AgentProposal)
        proposal.id = "proposal_1"
        proposal.agent_id = "agent_1"
        proposal.proposed_action = {
            "action_type": "update",  # Medium risk
            "target": "leads"
        }

        review = await orchestrator.review_intern_proposal(proposal)

        # Should suggest modifications due to low confidence
        assert review.recommendation == "modify"

    @pytest.mark.asyncio
    async def test_assess_proposal_risk_high_risk_actions(
        self,
        orchestrator,
        sample_intern_agent
    ):
        """Test risk assessment for high-risk actions"""
        high_risk_actions = ["delete", "payment", "data_export", "permissions_change"]

        for action in high_risk_actions:
            risk = await orchestrator._assess_proposal_risk(
                proposed_action={"action_type": action},
                agent=sample_intern_agent
            )
            assert risk == "high"

    @pytest.mark.asyncio
    async def test_assess_proposal_risk_low_risk(
        self,
        orchestrator,
        sample_intern_agent
    ):
        """Test risk assessment for low-risk actions"""
        risk = await orchestrator._assess_proposal_risk(
            proposed_action={"action_type": "read"},
            agent=sample_intern_agent
        )
        assert risk == "low"

    @pytest.mark.asyncio
    async def test_check_action_appropriateness(
        self,
        orchestrator
    ):
        """Test action appropriateness check"""
        # Finance agent doing reconciliation
        appropriate = await orchestrator._check_action_appropriateness(
            proposed_action={"action_type": "reconciliation"},
            agent_category="Finance"
        )
        assert appropriate is True

        # Support agent doing finance
        less_appropriate = await orchestrator._check_action_appropriateness(
            proposed_action={"action_type": "reconciliation"},
            agent_category="Support"
        )
        # Should be lenient (default to appropriate)
        assert less_appropriate is True

    @pytest.mark.asyncio
    async def test_generate_modifications_low_confidence(
        self,
        orchestrator,
        sample_intern_agent
    ):
        """Test modification suggestions for low confidence agent"""
        sample_intern_agent.confidence_score = 0.4

        modifications = await orchestrator._generate_modifications(
            proposed_action={"action_type": "update"},
            agent=sample_intern_agent
        )

        assert isinstance(modifications, list)
        assert len(modifications) > 0


# ============================================================================
# Training Session Tests
# ============================================================================

class TestTrainingSession:
    """Test training session facilitation"""

    @pytest.mark.asyncio
    async def test_conduct_training_session_basic(
        self,
        orchestrator,
        mock_db
    ):
        """Test basic training session initiation"""
        proposal = Mock(spec=AgentProposal)
        proposal.id = "proposal_1"

        session = Mock(spec=TrainingSession)
        session.id = "session_1"
        session.proposal_id = "proposal_1"
        session.status = "pending"

        mock_db.query.return_value.filter.return_value.first.return_value = session

        result = await orchestrator.conduct_training_session(
            proposal=proposal,
            human_supervisor_id="supervisor_1"
        )

        assert result is not None
        assert isinstance(result, TrainingResult)
        assert result.session_id == "session_1"
        assert session.status == "in_progress"

    @pytest.mark.asyncio
    async def test_conduct_training_session_not_found(
        self,
        orchestrator,
        mock_db
    ):
        """Test training session when session not found"""
        proposal = Mock(spec=AgentProposal)
        proposal.id = "proposal_1"

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError):
            await orchestrator.conduct_training_session(
                proposal=proposal,
                human_supervisor_id="supervisor_1"
            )


# ============================================================================
# Data Classes Tests
# ============================================================================

class TestDataClasses:
    """Test training data classes"""

    def test_training_proposal_creation(self):
        """Test TrainingProposal data class"""
        proposal = TrainingProposal(
            title="Test Training",
            description="Test description",
            learning_objectives=["obj1", "obj2"],
            capability_gaps=["gap1"],
            estimated_duration_hours=4.0,
            training_steps=[
                {"step_number": 1, "title": "Step 1", "type": "theory"}
            ]
        )

        assert proposal.title == "Test Training"
        assert len(proposal.learning_objectives) == 2
        assert proposal.estimated_duration_hours == 4.0
        assert len(proposal.training_steps) == 1

    def test_proposal_review_creation(self):
        """Test ProposalReview data class"""
        review = ProposalReview(
            recommendation="approve",
            confidence=0.9,
            reasoning="Agent is ready",
            suggested_modifications=None,
            concerns=None
        )

        assert review.recommendation == "approve"
        assert review.confidence == 0.9
        assert review.suggested_modifications is None

    def test_proposal_review_with_concerns(self):
        """Test ProposalReview with concerns"""
        review = ProposalReview(
            recommendation="modify",
            confidence=0.7,
            reasoning="Needs improvements",
            suggested_modifications=["Add detail"],
            concerns=["Low confidence"]
        )

        assert review.recommendation == "modify"
        assert len(review.concerns) == 1

    def test_training_result_creation(self):
        """Test TrainingResult data class"""
        result = TrainingResult(
            session_id="session_1",
            success=True,
            performance_score=85.0,
            capabilities_developed=["cap1", "cap2"],
            supervisor_feedback="Good work",
            should_promote=True
        )

        assert result.session_id == "session_1"
        assert result.success is True
        assert result.performance_score == 85.0
        assert result.should_promote is True


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_capability_gaps(
        self,
        orchestrator,
        sample_agent
    ):
        """Test training proposal with no capability gaps"""
        # This shouldn't happen in practice but test handling
        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task={"trigger_type": "generic"},
            agent_capabilities=["everything"],
            agent_category="Unknown"
        )

        # Should still return list
        assert isinstance(gaps, list)

    @pytest.mark.asyncio
    async def test_proposal_review_agent_not_found(
        self,
        orchestrator,
        mock_db
    ):
        """Test proposal review when agent not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        proposal = Mock(spec=AgentProposal)
        proposal.id = "proposal_1"
        proposal.agent_id = "nonexistent"
        proposal.proposed_action = {"action_type": "read"}

        with pytest.raises(ValueError):
            await orchestrator.review_intern_proposal(proposal)

    def test_scenario_templates_completeness(self, orchestrator):
        """Test all scenario templates have required scenarios"""
        required_categories = ["Finance", "Sales", "Operations", "HR", "Support"]

        for category in required_categories:
            assert category in orchestrator.SCENARIO_TEMPLATES
            template = orchestrator.SCENARIO_TEMPLATES[category]
            assert len(template["scenarios"]) >= 3
