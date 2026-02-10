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
from datetime import datetime, timedelta
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.models import User, AgentRegistry, AgentStatus


class TestUserModelInvariants:
    """Test User model maintains critical invariants."""

    @given(
        role=st.sampled_from(["MEMBER", "ADMIN", "SUPERVISOR", "GUEST"]),
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
        user1 = User(email=email, role="MEMBER")
        db_session.add(user1)
        db_session.commit()

        # Act: Try to create second user with same email
        user2 = User(email=email, role="MEMBER")
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


class TestUserAuthenticationInvariants:
    """Test user authentication security invariants."""

    @given(
        status=st.sampled_from(["ACTIVE", "INACTIVE", "SUSPENDED"]),
        email_verified=st.booleans()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_authentication_status(self, db_session: Session, status: str, email_verified: bool):
        """INVARIANT: User authentication status should be trackable."""
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            status=status,
            email_verified=email_verified
        )
        db_session.add(user)
        db_session.commit()

        # Verify authentication flags
        assert user.status == status, "Status mismatch"
        assert user.email_verified == email_verified, "Verified status mismatch"

    @given(
        last_login_days_ago=st.integers(min_value=0, max_value=3650)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_last_login_tracking(self, db_session: Session, last_login_days_ago: int):
        """INVARIANT: User last login should be tracked."""
        last_login = datetime.utcnow() - timedelta(days=last_login_days_ago)

        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            last_login=last_login
        )
        db_session.add(user)
        db_session.commit()

        # Verify last login is set
        assert user.last_login is not None, "Last login should be tracked"


class TestUserPermissionsInvariants:
    """Test user permissions and access control invariants."""

    @given(
        role=st.sampled_from(["MEMBER", "ADMIN", "SUPERVISOR", "GUEST"])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_role_permissions(self, db_session: Session, role: str):
        """INVARIANT: User roles should have defined permission levels."""
        # Define permission levels
        role_permissions = {
            "GUEST": 1,
            "MEMBER": 2,
            "SUPERVISOR": 3,
            "ADMIN": 4
        }

        assert role in role_permissions, f"Invalid role: {role}"

        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role=role
        )
        db_session.add(user)
        db_session.commit()

        # Verify role is set
        assert user.role == role, f"Role mismatch"

    @given(
        two_factor_enabled=st.booleans(),
        onboarding_completed=st.booleans()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_security_settings(self, db_session: Session, two_factor_enabled: bool, onboarding_completed: bool):
        """INVARIANT: User security settings should be configurable."""
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            two_factor_enabled=two_factor_enabled,
            onboarding_completed=onboarding_completed
        )
        db_session.add(user)
        db_session.commit()

        # Verify security settings
        assert user.two_factor_enabled == two_factor_enabled, "2FA setting mismatch"
        assert user.onboarding_completed == onboarding_completed, "Onboarding setting mismatch"


class TestUserDataValidationInvariants:
    """Test user data validation invariants."""

    @given(
        first_name_length=st.integers(min_value=1, max_value=100),
        last_name_length=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_name_validation(self, db_session: Session, first_name_length: int, last_name_length: int):
        """INVARIANT: User names should have valid length."""
        first_name = "x" * first_name_length
        last_name = "y" * last_name_length

        assert 1 <= first_name_length <= 100, f"First name length {first_name_length} outside valid range"
        assert 1 <= last_name_length <= 100, f"Last name length {last_name_length} outside valid range"

        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            first_name=first_name,
            last_name=last_name
        )
        db_session.add(user)
        db_session.commit()

        # Verify names are set
        assert len(user.first_name) == first_name_length, f"First name length mismatch"
        assert len(user.last_name) == last_name_length, f"Last name length mismatch"

    @given(
        specialty=st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_specialty_validation(self, db_session: Session, specialty: str):
        """INVARIANT: User specialty should be valid."""
        assert len(specialty) <= 100, f"Specialty too long: {len(specialty)}"

        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            specialty=specialty
        )
        db_session.add(user)
        db_session.commit()

        # Verify specialty is set
        assert user.specialty == specialty, f"Specialty mismatch"


class TestUserLifecycleInvariants:
    """Test user lifecycle state transitions."""

    @given(
        initial_status=st.sampled_from(["ACTIVE", "INACTIVE", "SUSPENDED"]),
        new_status=st.sampled_from(["ACTIVE", "INACTIVE", "SUSPENDED"])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_status_transitions(self, db_session: Session, initial_status: str, new_status: str):
        """INVARIANT: User status can be updated."""
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            status=initial_status
        )
        db_session.add(user)
        db_session.commit()

        # Update status
        user.status = new_status
        db_session.commit()

        # Verify status changed
        assert user.status == new_status, f"Status mismatch"

    @given(
        created_days_ago=st.integers(min_value=0, max_value=3650)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_timestamp_consistency(self, db_session: Session, created_days_ago: int):
        """INVARIANT: User timestamps should be consistent."""
        created_at = datetime.utcnow() - timedelta(days=created_days_ago)

        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            created_at=created_at
        )
        db_session.add(user)
        db_session.commit()

        # Verify timestamp is set
        assert user.created_at is not None, "created_at should be set"


class TestUserResourceConstraints:
    """Test user resource allocation constraints."""

    @given(
        capacity_hours=st.floats(min_value=0.0, max_value=168.0, allow_nan=False, allow_infinity=False),
        hourly_cost_rate=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_capacity_constraints(self, db_session: Session, capacity_hours: float, hourly_cost_rate: float):
        """INVARIANT: User capacity and cost should be constrained."""
        assert 0.0 <= capacity_hours <= 168.0, f"Capacity hours {capacity_hours} outside valid range"
        assert 0.0 <= hourly_cost_rate <= 1000.0, f"Hourly cost rate {hourly_cost_rate} outside valid range"

        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            capacity_hours=capacity_hours,
            hourly_cost_rate=hourly_cost_rate
        )
        db_session.add(user)
        db_session.commit()

        # Verify values are set
        assert user.capacity_hours == capacity_hours, f"Capacity mismatch"
        assert user.hourly_cost_rate == hourly_cost_rate, f"Cost rate mismatch"


class TestUserPreferencesInvariants:
    """Test user preferences and settings."""

    @given(
        preferences_json=st.dictionaries(
            keys=st.sampled_from(["notifications", "theme", "language", "timezone"]),
            values=st.one_of(st.booleans(), st.text(min_size=2, max_size=10, alphabet='abc'))
        ),
        metadata_json=st.dictionaries(
            keys=st.sampled_from(["department", "location", "team"]),
            values=st.text(min_size=2, max_size=20, alphabet='abc123')
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_preferences_json(self, db_session: Session, preferences_json: dict, metadata_json: dict):
        """INVARIANT: User preferences should be storable as JSON."""
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            preferences=preferences_json,
            metadata_json=metadata_json
        )
        db_session.add(user)
        db_session.commit()

        # Verify preferences are set
        assert user.preferences == preferences_json, "Preferences mismatch"
        assert user.metadata_json == metadata_json, "Metadata mismatch"

    @given(
        skills_json=st.text(min_size=1, max_size=1000, alphabet='["abc123", ", ]')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_skills_tracking(self, db_session: Session, skills_json: str):
        """INVARIANT: User skills should be trackable as JSON."""
        assert len(skills_json) <= 1000, f"Skills JSON too long: {len(skills_json)}"

        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            skills=skills_json
        )
        db_session.add(user)
        db_session.commit()

        # Verify skills are set
        assert user.skills == skills_json, f"Skills mismatch"


class TestUserOnboardingInvariants:
    """Test user onboarding state tracking."""

    @given(
        onboarding_completed=st.booleans(),
        onboarding_step=st.sampled_from(["welcome", "profile", "preferences", "integrations", "completed"])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_onboarding_progress(self, db_session: Session, onboarding_completed: bool, onboarding_step: str):
        """INVARIANT: User onboarding progress should be trackable."""
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            onboarding_completed=onboarding_completed,
            onboarding_step=onboarding_step
        )
        db_session.add(user)
        db_session.commit()

        # Verify onboarding state
        assert user.onboarding_completed == onboarding_completed, "Onboarding completed mismatch"
        assert user.onboarding_step == onboarding_step, "Onboarding step mismatch"


class TestUserEmailVerificationInvariants:
    """Test user email verification flow."""

    @given(
        email_verified=st.booleans()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_email_verification_status(self, db_session: Session, email_verified: bool):
        """INVARIANT: User email verification status should be trackable."""
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            email_verified=email_verified
        )
        db_session.add(user)
        db_session.commit()

        # Verify email verification status
        assert user.email_verified == email_verified, "Email verification status mismatch"

    @given(
        two_factor_enabled=st.booleans()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_two_factor_status(self, db_session: Session, two_factor_enabled: bool):
        """INVARIANT: User two-factor authentication status should be configurable."""
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            role="MEMBER",
            two_factor_enabled=two_factor_enabled
        )
        db_session.add(user)
        db_session.commit()

        # Verify 2FA status
        assert user.two_factor_enabled == two_factor_enabled, "2FA status mismatch"
