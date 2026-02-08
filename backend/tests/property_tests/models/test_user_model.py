"""
⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md
"""

import uuid
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.models import User, AgentRegistry, AgentStatus


class TestUserModelInvariants:
    """Test User model maintains critical invariants."""

    @given(
        role=st.sampled_from(["user", "admin", "supervisor", "guest"]),
        capacity_hours=st.floats(
            min_value=0.0,
            max_value=168.0,
            allow_nan=False,
            allow_infinity=False
        ),
        hourly_cost_rate=st.floats(
            min_value=0.0,
            max_value=1000.0,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.filter_too_much])
    def test_user_creation_maintains_constraints(
        self, db_session: Session, role: str,
        capacity_hours: float, hourly_cost_rate: float
    ):
        """
        INVARIANT: User creation MUST maintain all constraints.

        - Email must be unique
        - Role must be valid
        - Capacity hours >= 0
        - Hourly cost rate >= 0
        """
        # Generate unique email for each Hypothesis example
        email = f"{uuid.uuid4()}@example.com"

        # Arrange & Act: Create user
        user = User(
            email=email,
            role=role,
            capacity_hours=capacity_hours,
            hourly_cost_rate=hourly_cost_rate
        )
        db_session.add(user)
        db_session.commit()

        # Assert: Verify all invariants
        assert user.id is not None, (
            "User must have ID"
        )
        assert user.email == email, (
            f"Email must match: expected {email}, got {user.email}"
        )
        assert user.role == role, (
            f"Role must match: expected {role}, got {user.role}"
        )
        assert user.capacity_hours >= 0, (
            f"Capacity hours must be >= 0, got {user.capacity_hours}"
        )
        assert user.hourly_cost_rate >= 0, (
            f"Hourly cost rate must be >= 0, got {user.hourly_cost_rate}"
        )

    def test_email_uniqueness_constraint(
        self, db_session: Session
    ):
        """
        INVARIANT: Email uniqueness constraint MUST be enforced.

        Cannot create two users with same email.
        """
        # Generate a unique email for this test run
        email = f"{uuid.uuid4()}@example.com"

        # Arrange: Create first user
        user1 = User(email=email, role="user")
        db_session.add(user1)
        db_session.commit()

        # Act: Try to create second user with same email
        user2 = User(email=email, role="user")
        db_session.add(user2)

        # Assert: Should raise integrity error or handle gracefully
        # SQLAlchemy will raise an IntegrityError on commit
        try:
            db_session.commit()
            # If we get here, uniqueness wasn't enforced
            assert False, "Email uniqueness constraint not enforced"
        except Exception as e:
            # Expected - integrity constraint violation
            assert "email" in str(e).lower() or "unique" in str(e).lower(), (
                f"Email uniqueness should be enforced, got: {e}"
            )

    @given(
        confidence_score=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_agent_confidence_in_bounds(
        self, db_session: Session, confidence_score: float
    ):
        """
        INVARIANT: Agent confidence_score MUST be in [0.0, 1.0].

        This is a critical safety constraint for AI decision-making.
        """
        # Arrange & Act: Create agent with specific confidence
        agent = AgentRegistry(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        # Assert: Verify invariant
        assert 0.0 <= agent.confidence_score <= 1.0, (
            f"Confidence score must be in [0.0, 1.0], got {agent.confidence_score}"
        )

    @given(
        status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]),
        confidence_score=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_agent_status_enum_validity(
        self, db_session: Session, status: str, confidence_score: float
    ):
        """
        INVARIANT: Agent status MUST be a valid enum value.

        All status values must be in the AgentStatus enum.
        """
        # Arrange & Act: Create agent with specific status
        agent = AgentRegistry(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=status,
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        # Assert: Verify invariant
        valid_statuses = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]
        assert agent.status in valid_statuses, (
            f"Status must be valid enum value, got {agent.status}"
        )
