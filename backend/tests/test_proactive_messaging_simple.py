"""
Simple tests for Proactive Messaging Service (without full app import)

Tests proactive messaging with governance based on agent maturity levels.
Run with: python -m pytest tests/test_proactive_messaging_simple.py -v
"""

import sys
import os

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base
from core.models import AgentRegistry, AgentStatus, User, UserRole, ProactiveMessageStatus
from core.proactive_messaging_service import ProactiveMessagingService


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_proactive_simple.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def mock_heavy_dependencies():
    """
    Mock numpy/pandas/lancedb/pyarrow to prevent DLL loading issues on Python 3.13.

    This fixture runs automatically for all tests in this file to prevent
    loading heavy data science libraries that may have DLL compatibility issues.
    """
    original_modules = {}
    for mod in ["numpy", "pandas", "lancedb", "pyarrow"]:
        original_modules[mod] = sys.modules.get(mod)
        sys.modules[mod] = None

    yield

    # Restore original modules after test
    for mod, original in original_modules.items():
        if original is None:
            sys.modules.pop(mod, None)
        else:
            sys.modules[mod] = original


@pytest.fixture
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def student_agent(db):
    """Create a STUDENT agent."""
    agent = AgentRegistry(
        name="Student Agent",
        category="testing",
        module_path="test.student",
        class_name="StudentAgent",
        description="A student agent for testing",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def intern_agent(db):
    """Create an INTERN agent."""
    agent = AgentRegistry(
        name="Intern Agent",
        category="testing",
        module_path="test.intern",
        class_name="InternAgent",
        description="An intern agent for testing",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def autonomous_agent(db):
    """Create an AUTONOMOUS agent."""
    agent = AgentRegistry(
        name="Autonomous Agent",
        category="testing",
        module_path="test.autonomous",
        class_name="AutonomousAgent",
        description="An autonomous agent for testing",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


class TestProactiveMessagingGovernance:
    """Tests for governance-based proactive messaging."""

    def test_student_agent_blocked(self, db, student_agent):
        """STUDENT agents should be blocked from proactive messaging."""
        service = ProactiveMessagingService(db)

        with pytest.raises(Exception) as exc_info:
            service.create_proactive_message(
                agent_id=student_agent.id,
                platform="slack",
                recipient_id="C12345",
                content="Hello from student agent!",
            )

        assert "STUDENT agents are not allowed" in str(exc_info.value)

    def test_intern_agent_requires_approval(self, db, intern_agent):
        """INTERN agents should create pending messages requiring approval."""
        service = ProactiveMessagingService(db)

        message = service.create_proactive_message(
            agent_id=intern_agent.id,
            platform="slack",
            recipient_id="C12345",
            content="Hello from intern agent!",
        )

        assert message.status == ProactiveMessageStatus.PENDING.value
        assert message.agent_maturity_level == AgentStatus.INTERN.value
        assert message.approved_by is None
        assert message.approved_at is None

    def test_autonomous_agent_auto_approved(self, db, autonomous_agent):
        """AUTONOMOUS agents should be auto-approved."""
        service = ProactiveMessagingService(db)

        message = service.create_proactive_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C12345",
            content="Hello from autonomous agent!",
            send_now=False,
        )

        assert message.status == ProactiveMessageStatus.APPROVED.value
        assert message.agent_maturity_level == AgentStatus.AUTONOMOUS.value
        assert message.approved_at is not None


class TestProactiveMessageApproval:
    """Tests for message approval workflow."""

    def test_approve_pending_message(self, db, intern_agent, test_user):
        """Test approving a pending message."""
        service = ProactiveMessagingService(db)

        # Create pending message
        message = service.create_proactive_message(
            agent_id=intern_agent.id,
            platform="slack",
            recipient_id="C12345",
            content="Please approve this message",
        )

        assert message.status == ProactiveMessageStatus.PENDING.value

        # Approve the message
        approved_message = service.approve_message(
            message_id=message.id,
            approver_user_id=test_user.id,
        )

        assert approved_message.status == ProactiveMessageStatus.APPROVED.value
        assert approved_message.approved_by == test_user.id
        assert approved_message.approved_at is not None

    def test_reject_pending_message(self, db, intern_agent, test_user):
        """Test rejecting a pending message."""
        service = ProactiveMessagingService(db)

        # Create pending message
        message = service.create_proactive_message(
            agent_id=intern_agent.id,
            platform="slack",
            recipient_id="C12345",
            content="Please reject this message",
        )

        # Reject the message
        rejected_message = service.reject_message(
            message_id=message.id,
            rejecter_user_id=test_user.id,
            rejection_reason="Not appropriate",
        )

        assert rejected_message.status == ProactiveMessageStatus.CANCELLED.value
        assert rejected_message.rejection_reason == "Not appropriate"


class TestProactiveMessageQueries:
    """Tests for querying proactive messages."""

    def test_get_pending_messages(self, db, intern_agent, autonomous_agent):
        """Test retrieving pending messages."""
        service = ProactiveMessagingService(db)

        # Create pending message (INTERN)
        pending_message = service.create_proactive_message(
            agent_id=intern_agent.id,
            platform="slack",
            recipient_id="C12345",
            content="Pending message",
        )

        # Create approved message (AUTONOMOUS)
        approved_message = service.create_proactive_message(
            agent_id=autonomous_agent.id,
            platform="slack",
            recipient_id="C67890",
            content="Approved message",
            send_now=False,
        )

        # Get pending messages
        pending_messages = service.get_pending_messages()

        assert len(pending_messages) == 1
        assert pending_messages[0].id == pending_message.id

    def test_get_message_by_id(self, db, intern_agent):
        """Test retrieving a specific message by ID."""
        service = ProactiveMessagingService(db)

        # Create message
        message = service.create_proactive_message(
            agent_id=intern_agent.id,
            platform="slack",
            recipient_id="C12345",
            content="Test message",
        )

        # Get by ID
        retrieved_message = service.get_message(message_id=message.id)

        assert retrieved_message is not None
        assert retrieved_message.id == message.id
        assert retrieved_message.content == "Test message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
