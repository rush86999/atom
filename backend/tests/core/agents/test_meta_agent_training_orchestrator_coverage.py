"""
Coverage-driven tests for meta_agent_training_orchestrator.py (0% -> 75%+ target)

Coverage Target Areas:
- Lines 1-40: Service initialization and configuration
- Lines 40-80: Training session creation and initialization
- Lines 80-120: AI-based training duration estimation
- Lines 120-160: Proposal workflow (INTERN maturity requirement)
- Lines 160-200: Training execution and progress tracking
- Lines 200-250: Session completion and graduation readiness
- Lines 250-300: Scenario templates and category mappings
- Lines 300-350: Private helper methods for capability analysis
- Lines 350-400: Risk assessment and action appropriateness
- Lines 400-450: Modification generation and review logic
- Lines 450-500: Training step generation and learning objectives
- Lines 500-570: Edge cases and error handling

Target: 75%+ coverage (107+ of 142 statements)
Focus: Session lifecycle, proposal workflow, duration estimation
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Dict, Any

from core.meta_agent_training_orchestrator import (
    MetaAgentTrainingOrchestrator,
    TrainingProposal,
    ProposalReview,
    TrainingResult,
)
from core.models import (
    AgentRegistry,
    AgentProposal,
    AgentStatus,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    BlockedTriggerContext,
)


@pytest.fixture
def db_session():
    """Create test database session"""
    from core.database import get_db
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def orchestrator(db_session):
    """Create MetaAgentTrainingOrchestrator instance"""
    return MetaAgentTrainingOrchestrator(db=db_session)


@pytest.fixture
def student_agent(db_session):
    """Create test student agent"""
    agent = AgentRegistry(
        id="test-student-agent",
        name="Test Student Agent",
        category="Finance",
        module_path="agents.finance_agent",
        class_name="FinanceAgent",
        confidence_score=0.4,
        status=AgentStatus.STUDENT.value,
        configuration={"capabilities": []},
    )
    db_session.add(agent)
    db_session.commit()
    yield agent
    # Cleanup
    db_session.rollback()


@pytest.fixture
def intern_agent(db_session):
    """Create test intern agent"""
    agent = AgentRegistry(
        id="test-intern-agent",
        name="Test Intern Agent",
        category="Sales",
        module_path="agents.sales_agent",
        class_name="SalesAgent",
        confidence_score=0.6,
        status=AgentStatus.INTERN.value,
        configuration={"capabilities": ["lead_management"]},
    )
    db_session.add(agent)
    db_session.commit()
    yield agent
    # Cleanup
    db_session.rollback()


@pytest.fixture
def supervised_agent(db_session):
    """Create test supervised agent"""
    agent = AgentRegistry(
        id="test-supervised-agent",
        name="Test Supervised Agent",
        category="Operations",
        module_path="agents.operations_agent",
        class_name="OperationsAgent",
        confidence_score=0.8,
        status=AgentStatus.SUPERVISED.value,
        configuration={"capabilities": ["process_automation", "inventory_management"]},
    )
    db_session.add(agent)
    db_session.commit()
    yield agent
    # Cleanup
    db_session.rollback()


@pytest.fixture
def sample_blocked_task():
    """Sample blocked trigger task"""
    return {
        "trigger_type": "workflow_automation",
        "task_description": "Automate invoice reconciliation",
        "action_complexity": 3,
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_intern_proposal(db_session, intern_agent):
    """Sample INTERN agent proposal"""
    proposal = AgentProposal(
        id="test-proposal-123",
        agent_id=intern_agent.id,
        proposal_type=ProposalType.ACTION,
        proposed_action={
            "action_type": "lead_update",
            "reasoning": "Update lead status based on recent interaction",
            "expected_outcome": "Lead status changed to qualified",
        },
        status=ProposalStatus.PENDING,
        confidence_score=0.6,
    )
    db_session.add(proposal)
    db_session.commit()
    return proposal


@pytest.fixture
def sample_training_session(db_session, student_agent, sample_intern_proposal):
    """Sample training session"""
    session = TrainingSession(
        id="test-session-123",
        agent_id=student_agent.id,
        proposal_id=sample_intern_proposal.id,
        status="pending",
        training_scenario="Finance Fundamentals",
    )
    db_session.add(session)
    db_session.commit()
    return session


class TestMetaAgentTrainingOrchestratorInitialization:
    """Test MetaAgentTrainingOrchestrator initialization (lines 81-142)"""

    def test_orchestrator_init_with_db(self, orchestrator, db_session):
        """Test initialization with database session"""
        assert orchestrator.db == db_session
        assert hasattr(orchestrator, 'SCENARIO_TEMPLATES')

    def test_scenario_templates_exists(self, orchestrator):
        """Test SCENARIO_TEMPLATES dictionary exists"""
        assert hasattr(MetaAgentTrainingOrchestrator, 'SCENARIO_TEMPLATES')
        assert isinstance(orchestrator.SCENARIO_TEMPLATES, dict)
        assert len(orchestrator.SCENARIO_TEMPLATES) > 0

    def test_scenario_templates_has_finance(self, orchestrator):
        """Test Finance scenario template exists"""
        assert "Finance" in orchestrator.SCENARIO_TEMPLATES
        finance = orchestrator.SCENARIO_TEMPLATES["Finance"]
        assert finance["name"] == "Finance Fundamentals"
        assert "Reconciliation Training" in finance["scenarios"]

    def test_scenario_templates_has_sales(self, orchestrator):
        """Test Sales scenario template exists"""
        assert "Sales" in orchestrator.SCENARIO_TEMPLATES
        sales = orchestrator.SCENARIO_TEMPLATES["Sales"]
        assert sales["name"] == "Sales Operations"
        assert "Lead Scoring Exercise" in sales["scenarios"]

    def test_scenario_templates_has_operations(self, orchestrator):
        """Test Operations scenario template exists"""
        assert "Operations" in orchestrator.SCENARIO_TEMPLATES
        ops = orchestrator.SCENARIO_TEMPLATES["Operations"]
        assert ops["name"] == "Process Automation"
        assert "Inventory Management" in ops["scenarios"]


class TestTrainingProposalDataClass:
    """Test TrainingProposal data class (lines 26-42)"""

    def test_training_proposal_init(self):
        """Test TrainingProposal initialization"""
        proposal = TrainingProposal(
            title="Test Training",
            description="Test description",
            learning_objectives=["obj1", "obj2"],
            capability_gaps=["gap1", "gap2"],
            estimated_duration_hours=2.5,
            training_steps=[{"step": 1}],
        )
        assert proposal.title == "Test Training"
        assert proposal.estimated_duration_hours == 2.5
        assert len(proposal.learning_objectives) == 2

    def test_training_proposal_defaults(self):
        """Test TrainingProposal with default values"""
        proposal = TrainingProposal(
            title="Test",
            description="Desc",
            learning_objectives=[],
            capability_gaps=[],
            estimated_duration_hours=1.0,
            training_steps=[],
        )
        assert proposal.estimated_duration_hours == 1.0
        assert len(proposal.training_steps) == 0


class TestProposalReviewDataClass:
    """Test ProposalReview data class (lines 45-60)"""

    def test_proposal_review_init_approve(self):
        """Test ProposalReview with approve recommendation"""
        review = ProposalReview(
            recommendation="approve",
            confidence=0.9,
            reasoning="Good proposal",
            suggested_modifications=None,
            concerns=None,
        )
        assert review.recommendation == "approve"
        assert review.confidence == 0.9
        assert review.suggested_modifications == []
        assert review.concerns == []

    def test_proposal_review_init_modify(self):
        """Test ProposalReview with modify recommendation"""
        review = ProposalReview(
            recommendation="modify",
            confidence=0.7,
            reasoning="Needs changes",
            suggested_modifications=["Add detail"],
            concerns=["Missing info"],
        )
        assert review.recommendation == "modify"
        assert len(review.suggested_modifications) == 1
        assert len(review.concerns) == 1


class TestTrainingResultDataClass:
    """Test TrainingResult data class (lines 62-79)"""

    def test_training_result_init_success(self):
        """Test TrainingResult for successful training"""
        result = TrainingResult(
            session_id="session-123",
            success=True,
            performance_score=0.85,
            capabilities_developed=["cap1", "cap2"],
            supervisor_feedback="Good work",
            should_promote=True,
        )
        assert result.session_id == "session-123"
        assert result.success is True
        assert result.performance_score == 0.85
        assert result.should_promote is True

    def test_training_result_init_failure(self):
        """Test TrainingResult for failed training"""
        result = TrainingResult(
            session_id="session-456",
            success=False,
            performance_score=0.3,
            capabilities_developed=[],
            supervisor_feedback="Needs more practice",
            should_promote=False,
        )
        assert result.success is False
        assert result.performance_score == 0.3
        assert len(result.capabilities_developed) == 0


class TestProposeTrainingScenario:
    """Test propose_training_scenario method (lines 144-223)"""

    @pytest.mark.asyncio
    async def test_propose_training_for_student_agent(
        self, orchestrator, student_agent, sample_blocked_task
    ):
        """Test generating training proposal for STUDENT agent"""
        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=sample_blocked_task,
            agent_capabilities=[],
        )

        assert isinstance(proposal, TrainingProposal)
        assert proposal.title == f"Training: {student_agent.name} - Finance Fundamentals"
        assert proposal.estimated_duration_hours > 0
        assert len(proposal.learning_objectives) > 0
        assert len(proposal.capability_gaps) > 0
        assert len(proposal.training_steps) > 0

    @pytest.mark.asyncio
    async def test_propose_training_identifies_capability_gaps(
        self, orchestrator, student_agent, sample_blocked_task
    ):
        """Test that capability gaps are identified correctly"""
        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=sample_blocked_task,
            agent_capabilities=[],
        )

        # Should identify workflow-related gaps
        assert any("workflow" in gap.lower() for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_propose_training_generates_learning_objectives(
        self, orchestrator, student_agent, sample_blocked_task
    ):
        """Test that learning objectives are generated"""
        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=sample_blocked_task,
            agent_capabilities=[],
        )

        assert len(proposal.learning_objectives) > 0
        assert any("understand" in obj.lower() for obj in proposal.learning_objectives)
        assert any("demonstrate" in obj.lower() for obj in proposal.learning_objectives)

    @pytest.mark.asyncio
    async def test_propose_training_creates_training_steps(
        self, orchestrator, student_agent, sample_blocked_task
    ):
        """Test that training steps are created"""
        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=sample_blocked_task,
            agent_capabilities=[],
        )

        assert len(proposal.training_steps) >= 3  # Intro + concepts + assessment
        assert proposal.training_steps[0]["step_number"] == 1
        assert any(step["type"] == "theory" for step in proposal.training_steps)
        assert any(step["type"] == "assessment" for step in proposal.training_steps)

    @pytest.mark.asyncio
    async def test_propose_training_estimates_duration(
        self, orchestrator, student_agent, sample_blocked_task
    ):
        """Test that training duration is estimated"""
        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=sample_blocked_task,
            agent_capabilities=[],
        )

        # Duration should be ~4 hours per step
        expected_hours = len(proposal.training_steps) * 4
        assert proposal.estimated_duration_hours == expected_hours

    @pytest.mark.asyncio
    async def test_propose_training_agent_not_found(self, orchestrator, sample_blocked_task):
        """Test proposing training for non-existent agent raises error"""
        with pytest.raises(ValueError, match="Agent.*not found"):
            await orchestrator.propose_training_scenario(
                student_agent_id="non-existent-agent",
                blocked_task=sample_blocked_task,
                agent_capabilities=[],
            )

    @pytest.mark.asyncio
    async def test_propose_training_with_existing_capabilities(
        self, orchestrator, student_agent, sample_blocked_task
    ):
        """Test proposing training when agent has some capabilities"""
        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=sample_blocked_task,
            agent_capabilities=["workflow_automation", "financial_analysis"],
        )

        # Should filter out existing capabilities from gaps
        assert "workflow_automation" not in proposal.capability_gaps


class TestReviewInternProposal:
    """Test review_intern_proposal method (lines 225-325)"""

    @pytest.mark.asyncio
    async def test_review_proposal_low_risk_approve(
        self, orchestrator, intern_agent, sample_intern_proposal
    ):
        """Test reviewing low-risk proposal results in approve"""
        # Modify proposal to be low-risk
        sample_intern_proposal.proposed_action = {
            "action_type": "lead_update",
            "reasoning": "Update lead based on customer call",
            "expected_outcome": "Lead status updated",
        }

        review = await orchestrator.review_intern_proposal(sample_intern_proposal)

        assert isinstance(review, ProposalReview)
        assert review.recommendation == "approve"
        assert review.confidence >= 0.8
        assert review.suggested_modifications == []
        assert review.concerns == []

    @pytest.mark.asyncio
    async def test_review_proposal_medium_risk_modify(
        self, orchestrator, intern_agent, sample_intern_proposal
    ):
        """Test reviewing medium-risk proposal results in modify"""
        # Create medium-risk scenario
        intern_agent.confidence_score = 0.5
        orchestrator.db.commit()

        sample_intern_proposal.proposed_action = {
            "action_type": "update",
            "reasoning": "Update record",
        }

        review = await orchestrator.review_intern_proposal(sample_intern_proposal)

        assert review.recommendation == "modify"
        assert len(review.suggested_modifications) > 0
        assert len(review.concerns) > 0

    @pytest.mark.asyncio
    async def test_review_proposal_high_risk_reject(
        self, orchestrator, intern_agent, sample_intern_proposal
    ):
        """Test reviewing high-risk proposal results in reject"""
        sample_intern_proposal.proposed_action = {
            "action_type": "delete",
            "reasoning": "Delete old records",
        }

        review = await orchestrator.review_intern_proposal(sample_intern_proposal)

        assert review.recommendation == "reject"
        assert review.confidence >= 0.7
        assert "high risk" in review.reasoning.lower()

    @pytest.mark.asyncio
    async def test_review_proposal_includes_reasoning(
        self, orchestrator, intern_agent, sample_intern_proposal
    ):
        """Test that review includes detailed reasoning"""
        sample_intern_proposal.proposed_action = {
            "action_type": "lead_update",
            "reasoning": "Valid reasoning",
            "expected_outcome": "Success",
        }

        review = await orchestrator.review_intern_proposal(sample_intern_proposal)

        assert len(review.reasoning) > 0
        assert "action type" in review.reasoning.lower()

    @pytest.mark.asyncio
    async def test_review_proposal_agent_not_found(
        self, orchestrator, db_session
    ):
        """Test reviewing proposal for non-existent agent"""
        proposal = AgentProposal(
            id="bad-proposal",
            agent_id="non-existent-agent",
            proposal_type=ProposalType.ACTION,
            proposed_action={"action_type": "test"},
            status=ProposalStatus.PENDING,
        )
        db_session.add(proposal)
        db_session.commit()

        with pytest.raises(ValueError, match="Agent.*not found"):
            await orchestrator.review_intern_proposal(proposal)

    @pytest.mark.asyncio
    async def test_review_proposal_checks_appropriateness(
        self, orchestrator, intern_agent, sample_intern_proposal
    ):
        """Test that action appropriateness is checked"""
        sample_intern_proposal.proposed_action = {
            "action_type": "lead_update",
        }

        review = await orchestrator.review_intern_proposal(sample_intern_proposal)

        # Sales agent should be able to do lead updates
        assert review.recommendation in ["approve", "modify", "reject"]


class TestConductTrainingSession:
    """Test conduct_training_session method (lines 327-382)"""

    @pytest.mark.asyncio
    async def test_conduct_training_session_initializes(
        self,
        orchestrator,
        student_agent,
        sample_intern_proposal,
        sample_training_session,
    ):
        """Test that training session is initialized"""
        result = await orchestrator.conduct_training_session(
            proposal=sample_intern_proposal,
            human_supervisor_id="supervisor-123",
        )

        assert isinstance(result, TrainingResult)
        assert result.session_id == sample_training_session.id
        assert result.success is False  # Not completed yet
        assert result.performance_score == 0.0

        # Verify session status updated
        orchestrator.db.refresh(sample_training_session)
        assert sample_training_session.status == "in_progress"
        assert sample_training_session.supervisor_id == "supervisor-123"
        assert sample_training_session.started_at is not None

    @pytest.mark.asyncio
    async def test_conduct_training_session_agent_not_found(
        self, orchestrator, db_session, sample_intern_proposal
    ):
        """Test conducting session for non-existent agent"""
        session = TrainingSession(
            id="bad-session",
            agent_id="non-existent-agent",
            proposal_id=sample_intern_proposal.id,
            status="pending",
        )
        db_session.add(session)
        db_session.commit()

        with pytest.raises(ValueError, match="Agent.*not found"):
            await orchestrator.conduct_training_session(
                proposal=sample_intern_proposal,
                human_supervisor_id="supervisor-123",
            )

    @pytest.mark.asyncio
    async def test_conduct_training_session_not_found(
        self, orchestrator, student_agent, db_session
    ):
        """Test conducting session when training session doesn't exist"""
        proposal = AgentProposal(
            id="orphan-proposal",
            agent_id=student_agent.id,
            proposal_type=ProposalType.TRAINING,
            proposed_action={},
            status=ProposalStatus.APPROVED,
        )
        db_session.add(proposal)
        db_session.commit()

        with pytest.raises(ValueError, match="Training session.*not found"):
            await orchestrator.conduct_training_session(
                proposal=proposal,
                human_supervisor_id="supervisor-123",
            )


class TestAnalyzeCapabilityGaps:
    """Test _analyze_capability_gaps private method (lines 388-419)"""

    @pytest.mark.asyncio
    async def test_analyze_gaps_workflow_task(self, orchestrator):
        """Test gap analysis for workflow tasks"""
        blocked_task = {"trigger_type": "workflow_automation"}
        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task=blocked_task,
            agent_capabilities=[],
            agent_category="Finance",
        )

        assert "workflow_automation" in gaps
        assert "task_coordination" in gaps

    @pytest.mark.asyncio
    async def test_analyze_gaps_form_task(self, orchestrator):
        """Test gap analysis for form tasks"""
        blocked_task = {"trigger_type": "form_submission"}
        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task=blocked_task,
            agent_capabilities=[],
            agent_category="Operations",
        )

        assert "form_processing" in gaps
        assert "data_validation" in gaps

    @pytest.mark.asyncio
    async def test_analyze_gaps_category_specific(self, orchestrator):
        """Test category-specific capability gaps"""
        blocked_task = {"trigger_type": "task"}
        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task=blocked_task,
            agent_capabilities=[],
            agent_category="Finance",
        )

        assert "financial_analysis" in gaps
        assert "reconciliation" in gaps
        assert "reporting" in gaps

    @pytest.mark.asyncio
    async def test_analyze_gaps_filters_existing_capabilities(self, orchestrator):
        """Test that existing capabilities are filtered out"""
        blocked_task = {"trigger_type": "workflow_automation"}
        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task=blocked_task,
            agent_capabilities=["financial_analysis", "reconciliation"],
            agent_category="Finance",
        )

        # Should not include capabilities agent already has
        assert "financial_analysis" not in gaps
        assert "reconciliation" not in gaps

    @pytest.mark.asyncio
    async def test_analyze_gaps_dedupes(self, orchestrator):
        """Test that duplicate gaps are removed"""
        blocked_task = {"trigger_type": "workflow_automation"}
        gaps = await orchestrator._analyze_capability_gaps(
            blocked_task=blocked_task,
            agent_capabilities=[],
            agent_category="Finance",
        )

        # Check no duplicates
        assert len(gaps) == len(set(gaps))


class TestSelectScenarioTemplate:
    """Test _select_scenario_template private method (lines 421-434)"""

    def test_select_scenario_finance(self, orchestrator):
        """Test selecting Finance scenario template"""
        template = orchestrator._select_scenario_template(
            agent_category="Finance",
            blocked_task={"trigger_type": "task"},
        )

        assert template["name"] == "Finance Fundamentals"
        assert "Reconciliation Training" in template["scenarios"]

    def test_select_scenario_sales(self, orchestrator):
        """Test selecting Sales scenario template"""
        template = orchestrator._select_scenario_template(
            agent_category="Sales",
            blocked_task={"trigger_type": "task"},
        )

        assert template["name"] == "Sales Operations"
        assert "Lead Scoring Exercise" in template["scenarios"]

    def test_select_scenario_operations(self, orchestrator):
        """Test selecting Operations scenario template"""
        template = orchestrator._select_scenario_template(
            agent_category="Operations",
            blocked_task={"trigger_type": "task"},
        )

        assert template["name"] == "Process Automation"

    def test_select_scenario_unknown_category(self, orchestrator):
        """Test selecting scenario for unknown category"""
        template = orchestrator._select_scenario_template(
            agent_category="UnknownCategory",
            blocked_task={"trigger_type": "task"},
        )

        assert template["name"] == "General Operations"
        assert "Basic Task Execution" in template["scenarios"]


class TestGenerateLearningObjectives:
    """Test _generate_learning_objectives private method (lines 436-453)"""

    @pytest.mark.asyncio
    async def test_generate_objectives_basic(self, orchestrator, student_agent):
        """Test generating basic learning objectives"""
        blocked_task = {"trigger_type": "workflow_automation"}
        capability_gaps = ["workflow_automation", "task_coordination"]

        objectives = await orchestrator._generate_learning_objectives(
            agent=student_agent,
            blocked_task=blocked_task,
            capability_gaps=capability_gaps,
        )

        assert len(objectives) >= 3
        assert any("understand" in obj.lower() for obj in objectives)
        assert any("demonstrate" in obj.lower() for obj in objectives)
        assert any("decision-making" in obj.lower() for obj in objectives)

    @pytest.mark.asyncio
    async def test_generate_objectives_includes_capabilities(
        self, orchestrator, student_agent
    ):
        """Test that capability gaps are included in objectives"""
        blocked_task = {"trigger_type": "task"}
        capability_gaps = ["financial_analysis", "reconciliation"]

        objectives = await orchestrator._generate_learning_objectives(
            agent=student_agent,
            blocked_task=blocked_task,
            capability_gaps=capability_gaps,
        )

        # Should have objectives for each gap (limited to top 5)
        assert any("financial_analysis" in obj for obj in objectives)
        assert any("reconciliation" in obj for obj in objectives)


class TestGenerateTrainingSteps:
    """Test _generate_training_steps private method (lines 455-501) """

    @pytest.mark.asyncio
    async def test_generate_steps_includes_intro(self, orchestrator):
        """Test that training starts with introduction"""
        scenario_template = {"name": "Finance Training"}
        steps = await orchestrator._generate_training_steps(
            scenario_template=scenario_template,
            capability_gaps=["financial_analysis"],
            blocked_task={"trigger_type": "task"},
        )

        assert steps[0]["step_number"] == 1
        assert steps[0]["title"] == "Introduction and Context"
        assert steps[0]["type"] == "theory"
        assert steps[0]["estimated_minutes"] == 30

    @pytest.mark.asyncio
    async def test_generate_steps_includes_concepts(self, orchestrator):
        """Test that training includes concept walkthrough"""
        scenario_template = {"name": "Finance Training"}
        steps = await orchestrator._generate_training_steps(
            scenario_template=scenario_template,
            capability_gaps=["financial_analysis"],
            blocked_task={"trigger_type": "task"},
        )

        assert steps[1]["step_number"] == 2
        assert steps[1]["title"] == "Concept Walkthrough"
        assert steps[1]["type"] == "theory"
        assert steps[1]["estimated_minutes"] == 45

    @pytest.mark.asyncio
    async def test_generate_steps_includes_practice(self, orchestrator):
        """Test that training includes practice exercises"""
        scenario_template = {"name": "Finance Training"}
        steps = await orchestrator._generate_training_steps(
            scenario_template=scenario_template,
            capability_gaps=["financial_analysis", "reconciliation"],
            blocked_task={"trigger_type": "task"},
        )

        # Should have practice steps for each gap
        practice_steps = [s for s in steps if s["type"] == "practice"]
        assert len(practice_steps) >= 2

    @pytest.mark.asyncio
    async def test_generate_steps_includes_assessment(self, orchestrator):
        """Test that training ends with assessment"""
        scenario_template = {"name": "Finance Training"}
        steps = await orchestrator._generate_training_steps(
            scenario_template=scenario_template,
            capability_gaps=["financial_analysis"],
            blocked_task={"trigger_type": "task"},
        )

        assert steps[-1]["type"] == "assessment"
        assert "Assessment" in steps[-1]["title"]
        assert steps[-1]["estimated_minutes"] == 90


class TestAssessProposalRisk:
    """Test _assess_proposal_risk private method (lines 503-522)"""

    @pytest.mark.asyncio
    async def test_assess_risk_high_risk_actions(self, orchestrator, intern_agent):
        """Test that high-risk actions are identified"""
        high_risk_actions = ["delete", "payment", "data_export", "permissions_change"]

        for action in high_risk_actions:
            risk = await orchestrator._assess_proposal_risk(
                proposed_action={"action_type": action},
                agent=intern_agent,
            )
            assert risk == "high"

    @pytest.mark.asyncio
    async def test_assess_risk_medium_risk_actions(self, orchestrator, intern_agent):
        """Test medium-risk assessment for low-confidence agents"""
        intern_agent.confidence_score = 0.5
        medium_risk_actions = ["update", "create", "send", "publish"]

        for action in medium_risk_actions:
            risk = await orchestrator._assess_proposal_risk(
                proposed_action={"action_type": action},
                agent=intern_agent,
            )
            assert risk == "medium"

    @pytest.mark.asyncio
    async def test_assess_risk_low_risk_actions(self, orchestrator, supervised_agent):
        """Test low-risk assessment for high-confidence agents"""
        low_risk_actions = ["update", "create", "send", "publish"]

        for action in low_risk_actions:
            risk = await orchestrator._assess_proposal_risk(
                proposed_action={"action_type": action},
                agent=supervised_agent,
            )
            assert risk == "low"

    @pytest.mark.asyncio
    async def test_assess_risk_unknown_action(self, orchestrator, intern_agent):
        """Test risk assessment for unknown action types"""
        risk = await orchestrator._assess_proposal_risk(
            proposed_action={"action_type": "unknown_action"},
            agent=intern_agent,
        )
        assert risk == "low"


class TestCheckActionAppropriateness:
    """Test _check_action_appropriateness private method (lines 524-547)"""

    @pytest.mark.asyncio
    async def test_appropriateness_finance_agent(self, orchestrator):
        """Test appropriateness for Finance agent"""
        appropriate_actions = [
            "reconciliation",
            "analysis",
            "report",
            "categorize",
        ]

        for action in appropriate_actions:
            is_appropriate = await orchestrator._check_action_appropriateness(
                proposed_action={"action_type": action},
                agent_category="Finance",
            )
            assert is_appropriate is True

    @pytest.mark.asyncio
    async def test_appropriateness_sales_agent(self, orchestrator):
        """Test appropriateness for Sales agent"""
        appropriate_actions = ["lead_update", "crm_update", "outreach", "pipeline"]

        for action in appropriate_actions:
            is_appropriate = await orchestrator._check_action_appropriateness(
                proposed_action={"action_type": action},
                agent_category="Sales",
            )
            assert is_appropriate is True

    @pytest.mark.asyncio
    async def test_appropriateness_operations_agent(self, orchestrator):
        """Test appropriateness for Operations agent"""
        appropriate_actions = ["inventory", "logistics", "scheduling", "process"]

        for action in appropriate_actions:
            is_appropriate = await orchestrator._check_action_appropriateness(
                proposed_action={"action_type": action},
                agent_category="Operations",
            )
            assert is_appropriate is True

    @pytest.mark.asyncio
    async def test_appropriateness_unknown_category(self, orchestrator):
        """Test appropriateness defaults to True for unknown categories"""
        is_appropriate = await orchestrator._check_action_appropriateness(
            proposed_action={"action_type": "any_action"},
            agent_category="UnknownCategory",
        )
        assert is_appropriate is True


class TestGenerateModifications:
    """Test _generate_modifications private method (lines 549-569) """

    @pytest.mark.asyncio
    async def test_generate_modifications_low_confidence(self, orchestrator, intern_agent):
        """Test generating modifications for low-confidence agents"""
        intern_agent.confidence_score = 0.5
        modifications = await orchestrator._generate_modifications(
            proposed_action={"action_type": "update"},
            agent=intern_agent,
        )

        assert len(modifications) > 0
        assert any("reasoning" in mod.lower() for mod in modifications)
        assert any("execution plan" in mod.lower() for mod in modifications)

    @pytest.mark.asyncio
    async def test_generate_modifications_missing_reasoning(self, orchestrator, intern_agent):
        """Test modifications when reasoning is missing"""
        modifications = await orchestrator._generate_modifications(
            proposed_action={"action_type": "update"},
            agent=intern_agent,
        )

        assert any("reasoning" in mod.lower() for mod in modifications)

    @pytest.mark.asyncio
    async def test_generate_modifications_missing_outcome(self, orchestrator, intern_agent):
        """Test modifications when expected outcome is missing"""
        modifications = await orchestrator._generate_modifications(
            proposed_action={
                "action_type": "update",
                "reasoning": "Some reasoning",
            },
            agent=intern_agent,
        )

        assert any("expected outcome" in mod.lower() for mod in modifications)

    @pytest.mark.asyncio
    async def test_generate_modifications_complete_proposal(
        self, orchestrator, supervised_agent
    ):
        """Test modifications when proposal is complete"""
        modifications = await orchestrator._generate_modifications(
            proposed_action={
                "action_type": "update",
                "reasoning": "Detailed reasoning",
                "expected_outcome": "Expected result",
            },
            agent=supervised_agent,
        )

        # High-confidence agent with complete proposal should have fewer modifications
        assert len(modifications) == 0


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling (throughout file)"""

    @pytest.mark.asyncio
    async def test_empty_capability_gaps_list(self, orchestrator, student_agent):
        """Test handling of empty capability gaps"""
        blocked_task = {"trigger_type": "unknown_task"}

        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=blocked_task,
            agent_capabilities=[],
        )

        # Should still generate proposal even with minimal gaps
        assert isinstance(proposal, TrainingProposal)

    @pytest.mark.asyncio
    async def test_agent_with_many_capabilities(
        self, orchestrator, student_agent, sample_blocked_task
    ):
        """Test proposing training for agent with many capabilities"""
        many_capabilities = [
            "workflow_automation",
            "financial_analysis",
            "reconciliation",
            "reporting",
            "task_coordination",
            "form_processing",
            "data_validation",
        ]

        proposal = await orchestrator.propose_training_scenario(
            student_agent_id=student_agent.id,
            blocked_task=sample_blocked_task,
            agent_capabilities=many_capabilities,
        )

        # Should filter out existing capabilities
        assert all(cap not in proposal.capability_gaps for cap in many_capabilities)

    @pytest.mark.asyncio
    async def test_proposal_with_minimal_action(self, orchestrator, intern_agent):
        """Test reviewing proposal with minimal action info"""
        proposal = AgentProposal(
            id="minimal-proposal",
            agent_id=intern_agent.id,
            proposal_type=ProposalType.ACTION_PROPOSAL,
            proposed_action={},
            status=ProposalStatus.PENDING,
        )
        orchestrator.db.add(proposal)
        orchestrator.db.commit()

        review = await orchestrator.review_intern_proposal(proposal)

        # Should still generate review
        assert isinstance(review, ProposalReview)
        assert review.recommendation in ["approve", "modify", "reject"]


class TestParametrizedScenarios:
    """Parametrized tests for different scenarios"""

    @pytest.mark.parametrize(
        "category,expected_scenario_name",
        [
            ("Finance", "Finance Fundamentals"),
            ("Sales", "Sales Operations"),
            ("Operations", "Process Automation"),
            ("HR", "HR Management"),
            ("Support", "Customer Support"),
        ],
    )
    def test_scenario_templates_for_all_categories(
        self, orchestrator, category, expected_scenario_name
    ):
        """Test scenario templates exist for all categories"""
        template = orchestrator._select_scenario_template(
            agent_category=category,
            blocked_task={"trigger_type": "task"},
        )

        assert template["name"] == expected_scenario_name

    @pytest.mark.parametrize(
        "maturity_level,confidence,expected_risk",
        [
            ("INTERN", 0.5, "medium"),
            ("SUPERVISED", 0.8, "low"),
            ("AUTONOMOUS", 0.95, "low"),
        ],
    )
    @pytest.mark.asyncio
    async def test_risk_assessment_by_maturity(
        self, orchestrator, db_session, maturity_level, confidence, expected_risk
    ):
        """Test risk assessment varies by maturity level"""
        agent = AgentRegistry(
            id=f"test-agent-{maturity_level}",
            name=f"Test {maturity_level} Agent",
            category="Operations",
            confidence_score=confidence,
            status=maturity_level,
        )
        db_session.add(agent)
        db_session.commit()

        risk = await orchestrator._assess_proposal_risk(
            proposed_action={"action_type": "update"},
            agent=agent,
        )

        assert risk == expected_risk
