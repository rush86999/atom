"""
Tests for Autonomous Supervisor Service

Test autonomous agent fallback supervision when users are unavailable.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
    Tenant,
    User,
)
from core.autonomous_supervisor_service import (
    AutonomousSupervisorService,
    ProposalReview,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_tenant(db_session: Session):
    """Create test tenant (required FK for proposals)."""
    tenant = Tenant(
        name=f"Test-{uuid.uuid4()}",
        subdomain=f"test-{uuid.uuid4()}.example.com",
        edition="personal",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def test_user(db_session: Session):
    """Create test user."""
    user = User(
        email=f"test-{uuid.uuid4()}@example.com",
        first_name="Test",
        last_name="User",
        status="ACTIVE", role="member"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def autonomous_agent(db_session: Session, test_user: User):
    """Create autonomous supervisor agent."""
    agent = AgentRegistry(
        name="Autonomous Supervisor",
        description="High-confidence autonomous agent",
        category="finance",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
        user_id=test_user.id,
        module_path="core.generic_agent",
        class_name="GenericAgent",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def intern_agent(db_session: Session, test_user: User):
    """Create INTERN agent needing supervision."""
    agent = AgentRegistry(
        name="Intern Agent",
        description="Low-confidence intern agent",
        category="finance",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        user_id=test_user.id,
        module_path="core.generic_agent",
        class_name="GenericAgent",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def supervisor_service(db_session: Session):
    """Get AutonomousSupervisorService instance."""
    return AutonomousSupervisorService(db_session)


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
    db_session: Session
):
    """Test finding autonomous supervisor when none exists."""
    import asyncio

    # Delete autonomous agents
    db_session.query(AgentRegistry).filter(
        AgentRegistry.status == AgentStatus.AUTONOMOUS.value
    ).delete()
    db_session.commit()

    supervisor = asyncio.run(supervisor_service.find_autonomous_supervisor(
        intern_agent=intern_agent
    ))

    assert supervisor is None


def test_find_autonomous_supervisor_different_category(
    supervisor_service: AutonomousSupervisorService,
    intern_agent: AgentRegistry,
    autonomous_agent: AgentRegistry,
    db_session: Session
):
    """Test finding autonomous supervisor with different category."""
    import asyncio

    # Change autonomous agent to different category
    autonomous_agent.category = "engineering"
    db_session.commit()

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
    test_user: User,
    test_tenant: Tenant,
    db_session: Session
):
    """Test reviewing proposal returns valid review."""
    import asyncio

    # Create proposal
    proposal = AgentProposal(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Test Proposal",
        description="Test proposal for review",
        proposal_data={
            "action_type": "canvas_present",
            "canvas_type": "chart",
            "reasoning": "This action is safe and necessary",
        },
        status=ProposalStatus.PENDING_APPROVAL.value
    )
    db_session.add(proposal)
    db_session.commit()

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
    test_user: User,
    test_tenant: Tenant,
    db_session: Session
):
    """Test reviewing high-risk proposal."""
    import asyncio

    # Create high-risk proposal
    proposal = AgentProposal(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Delete Data Proposal",
        description="Proposal to delete data",
        proposal_data={
            "action_type": "delete",
            "target": "important_data",
            "reasoning": "Need to clean up old data",
        },
        status=ProposalStatus.PENDING_APPROVAL.value
    )
    db_session.add(proposal)
    db_session.commit()

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
    test_user: User,
    test_tenant: Tenant,
    db_session: Session
):
    """Test reviewing safe proposal."""
    import asyncio

    # Create safe proposal
    proposal = AgentProposal(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Present Chart Proposal",
        description="Proposal to present chart",
        proposal_data={
            "action_type": "canvas_present",
            "canvas_type": "chart",
            "reasoning": "Display data visualization",
        },
        status=ProposalStatus.PENDING_APPROVAL.value
    )
    db_session.add(proposal)
    db_session.commit()

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
    test_user: User,
    test_tenant: Tenant,
    db_session: Session
):
    """Test approving proposal as autonomous supervisor."""
    import asyncio

    # Create proposal
    proposal = AgentProposal(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        agent_id=intern_agent.id,
        agent_name=intern_agent.name,
        proposal_type=ProposalType.ACTION.value,
        title="Test Proposal",
        description="Test proposal",
        proposal_data={"action_type": "canvas_present"},
        status=ProposalStatus.PENDING_APPROVAL.value
    )
    db_session.add(proposal)
    db_session.commit()

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
    db_session.refresh(proposal)
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
    db_session: Session
):
    """Test monitoring execution yields supervision events."""
    import asyncio

    # Create execution
    execution = AgentExecution(
        id="test_exec_123",
        agent_id=autonomous_agent.id,
        status="running",
        started_at=datetime.utcnow()
    )
    db_session.add(execution)
    db_session.commit()

    # Monitor execution
    events = []
    async def collect_events():
        async for event in supervisor_service.monitor_execution(
            execution_id=execution.id,
            supervisor=autonomous_agent
        ):
            events.append(event)
            break  # Running executions stream forever; first event is guaranteed

    asyncio.run(collect_events())

    # Should have received events
    assert len(events) > 0
    assert events[0].event_type == "monitoring_started"
    assert events[0].data["execution_id"] == execution.id


def test_monitor_completed_execution(
    supervisor_service: AutonomousSupervisorService,
    autonomous_agent: AgentRegistry,
    db_session: Session
):
    """Test monitoring already completed execution."""
    import asyncio

    # Create completed execution
    execution = AgentExecution(
        id="test_exec_completed",
        agent_id=autonomous_agent.id,
        status="completed",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
        duration_seconds=300,
        result_summary="Execution completed successfully"
    )
    db_session.add(execution)
    db_session.commit()

    # Monitor execution
    events = []
    async def collect_events():
        async for event in supervisor_service.monitor_execution(
            execution_id=execution.id,
            supervisor=autonomous_agent
        ):
            events.append(event)

    asyncio.run(collect_events())

    # Should detect completion
    assert len(events) > 0
    completion_event = next((e for e in events if e.event_type == "execution_completed"), None)
    assert completion_event is not None


def test_monitor_failed_execution(
    supervisor_service: AutonomousSupervisorService,
    autonomous_agent: AgentRegistry,
    db_session: Session
):
    """Test monitoring failed execution."""
    import asyncio

    # Create failed execution
    execution = AgentExecution(
        id="test_exec_failed",
        agent_id=autonomous_agent.id,
        status="failed",
        started_at=datetime.utcnow() - timedelta(minutes=2),
        completed_at=datetime.utcnow(),
        error_message="Execution failed: timeout"
    )
    db_session.add(execution)
    db_session.commit()

    # Monitor execution
    events = []
    async def collect_events():
        async for event in supervisor_service.monitor_execution(
            execution_id=execution.id,
            supervisor=autonomous_agent
        ):
            events.append(event)

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
    db_session: Session
):
    """Test filtering available supervisors by category."""
    import asyncio

    supervisors = asyncio.run(supervisor_service.get_available_supervisors(
        category="finance"
    ))

    assert all(s.category == "finance" for s in supervisors)
