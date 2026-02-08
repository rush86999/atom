"""
Tests for Autonomous Supervisor Service

Test autonomous agent fallback supervision when users are unavailable.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import (
    AgentExecution,
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
    QueueStatus,
    SupervisionSession,
    SupervisionStatus,
    User,
    UserActivity,
    UserState,
)
from core.autonomous_supervisor_service import (
    AutonomousSupervisorService,
    ProposalReview,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Get database session."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db: Session):
    """Create test user."""
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def autonomous_agent(db: Session, test_user: User):
    """Create autonomous supervisor agent."""
    agent = AgentRegistry(
        name="Autonomous Supervisor",
        description="High-confidence autonomous agent",
        agent_type="generic",
        category="finance",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
        user_id=test_user.id
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def intern_agent(db: Session, test_user: User):
    """Create INTERN agent needing supervision."""
    agent = AgentRegistry(
        name="Intern Agent",
        description="Low-confidence intern agent",
        agent_type="generic",
        category="finance",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        user_id=test_user.id
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def supervisor_service(db: Session):
    """Get AutonomousSupervisorService instance."""
    return AutonomousSupervisorService(db)


# ============================================================================
# Find Autonomous Supervisor Tests
# ============================================================================

def test_find_autonomous_supervisor_by_category(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    autonomous_agent: AgentRegistry
):
    """Test finding autonomous supervisor by category."""
    import asyncio

    supervisor = asyncio.run(supervisor_service.find_autonomous_supervisor(
        intern_agent=intern_agent
    ))

    assert supervisor is not None
    assert supervisor.id == autonomous_agent.id
    assert supervisor.status == AgentStatus.AUTONOMOUS.value
    assert supervisor.category == intern_agent.category


def test_find_autonomous_supervisor_no_match(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    db: Session
):
    """Test finding autonomous supervisor when none exists."""
    import asyncio

    # Delete autonomous agents
    db.query(AgentRegistry).filter(
        AgentRegistry.status == AgentStatus.AUTONOMOUS.value
    ).delete()
    db.commit()

    supervisor = asyncio.run(supervisor_service.find_autonomous_supervisor(
        intern_agent=intern_agent
    ))

    assert supervisor is None


def test_find_autonomous_supervisor_different_category(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    autonomous_agent: AgentRegistry,
    db: Session
):
    """Test finding autonomous supervisor with different category."""
    import asyncio

    # Change autonomous agent to different category
    autonomous_agent.category = "engineering"
    db.commit()

    supervisor = asyncio.run(supervisor_service.find_autonomous_supervisor(
        intern_agent=intern_agent,
        category="finance"  # Looking for finance, but agent is engineering
    ))

    # Should not find match
    assert supervisor is None


# ============================================================================
# Proposal Review Tests
# ============================================================================

def test_review_proposal_returns_review(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    autonomous_agent: AgentRegistry,
    db: Session
):
    """Test reviewing proposal returns valid review."""
    import asyncio

    # Create proposal
    proposal = AgentProposal(
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Test Proposal",
        description="Test proposal for review",
        proposed_action={
            "action_type": "canvas_present",
            "canvas_type": "chart"
        },
        reasoning="This action is safe and necessary",
        status=ProposalStatus.PROPOSED.value
    )
    db.add(proposal)
    db.commit()

    # Review proposal
    review = asyncio.run(supervisor_service.review_proposal(
        proposal=proposal,
        supervisor=autonomous_agent
    ))

    assert isinstance(review, ProposalReview)
    assert hasattr(review, 'approved')
    assert hasattr(review, 'confidence_score')
    assert hasattr(review, 'risk_level')
    assert hasattr(review, 'reasoning')
    assert review.risk_level in ["safe", "medium", "high"]


def test_review_proposal_high_risk_action(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    autonomous_agent: AgentRegistry,
    db: Session
):
    """Test reviewing high-risk proposal."""
    import asyncio

    # Create high-risk proposal
    proposal = AgentProposal(
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Delete Data Proposal",
        description="Proposal to delete data",
        proposed_action={
            "action_type": "delete",
            "target": "important_data"
        },
        reasoning="Need to clean up old data",
        status=ProposalStatus.PROPOSED.value
    )
    db.add(proposal)
    db.commit()

    # Review proposal
    review = asyncio.run(supervisor_service.review_proposal(
        proposal=proposal,
        supervisor=autonomous_agent
    ))

    # High-risk actions should have higher scrutiny
    assert review.risk_level == "high"


def test_review_proposal_safe_action(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    autonomous_agent: AgentRegistry,
    db: Session
):
    """Test reviewing safe proposal."""
    import asyncio

    # Create safe proposal
    proposal = AgentProposal(
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Present Chart Proposal",
        description="Proposal to present chart",
        proposed_action={
            "action_type": "canvas_present",
            "canvas_type": "chart"
        },
        reasoning="Display data visualization",
        status=ProposalStatus.PROPOSED.value
    )
    db.add(proposal)
    db.commit()

    # Review proposal
    review = asyncio.run(supervisor_service.review_proposal(
        proposal=proposal,
        supervisor=autonomous_agent
    ))

    # Safe actions should be approved
    assert review.risk_level == "safe"
    # With high-confidence autonomous supervisor, should be approved
    assert review.approved is True


# ============================================================================
# Proposal Approval Tests
# ============================================================================

def test_approve_proposal_success(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    autonomous_agent: AgentRegistry,
    db: Session
):
    """Test approving proposal as autonomous supervisor."""
    import asyncio

    # Create proposal
    proposal = AgentProposal(
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Test Proposal",
        description="Test proposal",
        proposed_action={"action_type": "canvas_present"},
        reasoning="Safe action",
        status=ProposalStatus.PROPOSED.value
    )
    db.add(proposal)
    db.commit()

    # Create review
    review = ProposalReview(
        approved=True,
        confidence_score=0.95,
        risk_level="safe",
        reasoning="Safe action, approved"
    )

    # Approve proposal
    success = asyncio.run(supervisor_service.approve_proposal(
        proposal_id=proposal.id,
        supervisor_id=autonomous_agent.id,
        review=review
    ))

    assert success is True

    # Check proposal status
    db.refresh(proposal)
    assert proposal.status == ProposalStatus.EXECUTED.value
    assert proposal.approved_by == autonomous_agent.id


def test_approve_proposal_nonexistent_proposal(
    supervisor_service: AutonomousSupervisorService
):
    """Test approving non-existent proposal."""
    import asyncio

    review = ProposalReview(
        approved=True,
        confidence_score=0.95,
        risk_level="safe",
        reasoning="Test"
    )

    success = asyncio.run(supervisor_service.approve_proposal(
        proposal_id="nonexistent",
        supervisor_id="test_supervisor",
        review=review
    ))

    assert success is False


# ============================================================================
# Execution Monitoring Tests
# ============================================================================

def test_monitor_execution_yields_events(
    supervisor_service: AutonomousSupervisorService,
    autonomous_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test monitoring execution yields supervision events."""
    import asyncio

    # Create execution
    execution = AgentExecution(
        id="test_exec_123",
        agent_id=autonomous_agent.id,
        user_id=test_user.id,
        agent_name=autonomous_agent.name,
        status="running",
        input_data={"test": "data"},
        started_at=datetime.utcnow()
    )
    db.add(execution)
    db.commit()

    # Monitor execution
    events = []
    async def collect_events():
        async for event in supervisor_service.monitor_execution(
            execution_id=execution.id,
            supervisor=autonomous_agent
        ):
            events.append(event)
            if len(events) >= 2:  # Collect first 2 events
                break

    asyncio.run(collect_events())

    # Should have received events
    assert len(events) > 0
    assert events[0].event_type == "monitoring_started"
    assert events[0].data["execution_id"] == execution.id


def test_monitor_completed_execution(
    supervisor_service: AutonomousSupervisorService,
    autonomous_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test monitoring already completed execution."""
    import asyncio

    # Create completed execution
    execution = AgentExecution(
        id="test_exec_completed",
        agent_id=autonomous_agent.id,
        user_id=test_user.id,
        agent_name=autonomous_agent.name,
        status="completed",
        input_data={},
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
        duration_seconds=300,
        output_summary="Execution completed successfully"
    )
    db.add(execution)
    db.commit()

    # Monitor execution
    events = []
    async def collect_events():
        async for event in supervisor_service.monitor_execution(
            execution_id=execution.id,
            supervisor=autonomous_agent
        ):
            events.append(event)
            break  # Only collect first event

    asyncio.run(collect_events())

    # Should detect completion
    assert len(events) > 0
    completion_event = next((e for e in events if e.event_type == "execution_completed"), None)
    assert completion_event is not None


def test_monitor_failed_execution(
    supervisor_service: AutonomousSupervisorService,
    autonomous_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test monitoring failed execution."""
    import asyncio

    # Create failed execution
    execution = AgentExecution(
        id="test_exec_failed",
        agent_id=autonomous_agent.id,
        user_id=test_user.id,
        agent_name=autonomous_agent.name,
        status="failed",
        input_data={},
        started_at=datetime.utcnow() - timedelta(minutes=2),
        completed_at=datetime.utcnow(),
        error_message="Execution failed: timeout"
    )
    db.add(execution)
    db.commit()

    # Monitor execution
    events = []
    async def collect_events():
        async for event in supervisor_service.monitor_execution(
            execution_id=execution.id,
            supervisor=autonomous_agent
        ):
            events.append(event)
            break  # Only collect first event

    asyncio.run(collect_events())

    # Should detect failure
    assert len(events) > 0
    failed_event = next((e for e in events if e.event_type == "execution_failed"), None)
    assert failed_event is not None


# ============================================================================
# Get Available Supervisors Tests
# ============================================================================

def test_get_available_supervisors_returns_autonomous_agents(
    supervisor_service: AutonomousSupervisorService,
    autonomous_agent: AgentRegistry
):
    """Test getting available autonomous supervisors."""
    import asyncio

    supervisors = asyncio.run(supervisor_service.get_available_supervisors())

    assert len(supervisors) > 0
    assert autonomous_agent.id in [s.id for s in supervisors]
    assert all(s.status == AgentStatus.AUTONOMOUS.value for s in supervisors)
    assert all(s.confidence_score >= 0.9 for s in supervisors)


def test_get_available_supervisors_filters_by_category(
    supervisor_service: AutonomousSupervisorService,
    autonomous_agent: AgentRegistry,
    db: Session
):
    """Test filtering available supervisors by category."""
    import asyncio

    supervisors = asyncio.run(supervisor_service.get_available_supervisors(
        category="finance"
    ))

    assert all(s.category == "finance" for s in supervisors)
