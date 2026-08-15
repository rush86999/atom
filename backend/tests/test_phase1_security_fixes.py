"""
Phase 1 Security and Governance Fixes Tests

Tests for the critical security and governance fixes applied in Phase 1:
1. Token revocation implementation
2. AgentJobStatus enum UPPERCASE values
3. Business agent implementations
4. Workflow parameter validator fixes
5. Resource guards enhancements
"""

import pytest

from datetime import datetime, timedelta
import uuid
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import (
    ActiveToken, AgentJobStatus, HITLActionStatus, User,
    AgentJob, AgentRegistry, Workspace
)
from core.auth_helpers import (
    revoke_all_user_tokens, track_active_token,
    cleanup_expired_active_tokens
)
from core.business_agents import get_specialized_agent, AGENT_SUITE
from core.advanced_workflow_system import (
    ParameterValidator, InputParameter, ParameterType, MAX_REGEX_LENGTH
)
from core.resource_guards import (
    CPUGuard, MemoryGuard, DiskSpaceGuard,
    RateLimiter, IntegrationTimeoutError
)
from core.api_governance import ActionComplexity


def _unique_email(prefix: str) -> str:
    """Unique email per run so repeated executions are idempotent."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


def _purge_test_user(db: Session, user_id: str) -> None:
    """Remove leftover rows from crashed/interrupted prior runs."""
    db.query(ActiveToken).filter(ActiveToken.user_id == user_id).delete()
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        db.delete(existing)
    db.commit()


class TestTokenRevocation:
    """Test token revocation security fixes"""

    def test_active_token_model_exists(self):
        """Test that ActiveToken model is properly defined"""
        assert hasattr(ActiveToken, '__tablename__')
        assert ActiveToken.__tablename__ == 'active_tokens'

    def test_track_active_token(self, db_session):
        """Test tracking active tokens"""
        # Create a test user
        user = User(
            id='test-user-token',
            email=_unique_email('token'),
            role='member', first_name="Test", last_name="User", status="active"
        )
        _purge_test_user(db_session, user.id)
        db_session.add(user)
        db_session.commit()

        # Track a token (unique jti per run — RevokedToken rows persist across
        # runs and would otherwise make revoke_all_user_tokens skip them)
        jti = f"test-jti-{uuid.uuid4().hex[:8]}"
        result = track_active_token(
            jti=jti,
            user_id=user.id,
            expires_at=datetime.now() + timedelta(hours=1),
            db=db_session,
            issued_ip='127.0.0.1',
            issued_user_agent='Test Agent'
        )

        assert result == True, "Token tracking should succeed"

        # Verify token is tracked
        token = db_session.query(ActiveToken).filter_by(jti=jti).first()
        assert token is not None, "Token should be tracked"
        assert token.user_id == user.id
        assert token.issued_ip == '127.0.0.1'

        # Cleanup
        db_session.delete(token)
        db_session.delete(user)
        db_session.commit()

    def test_revoke_all_user_tokens(self, db_session):
        """Test revoking all user tokens"""
        # Create a test user
        user = User(
            id='test-user-revoke',
            email=_unique_email('revoke'),
            role='member', first_name="Test", last_name="User", status="active"
        )
        _purge_test_user(db_session, user.id)
        db_session.add(user)
        db_session.commit()

        # Track multiple tokens
        jtis = [f"revoke-jti-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        for jti in jtis:
            track_active_token(
                jti=jti,
                user_id=user.id,
                expires_at=datetime.now() + timedelta(hours=1),
                db=db_session
            )

        # Revoke all tokens
        count = revoke_all_user_tokens(user_id=user.id, db=db_session)

        assert count == 3, f"Should revoke 3 tokens, got {count}"

        # Verify all tokens are revoked
        active_tokens = db_session.query(ActiveToken).filter_by(user_id=user.id).all()
        assert len(active_tokens) == 0, "All tokens should be revoked"

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_revoke_except_current_token(self, db_session):
        """Test revoking all tokens except current"""
        user = User(
            id='test-user-except',
            email=_unique_email('except'),
            role='member', first_name="Test", last_name="User", status="active"
        )
        _purge_test_user(db_session, user.id)
        db_session.add(user)
        db_session.commit()

        # Track multiple tokens
        jtis = [f"except-jti-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        for jti in jtis:
            track_active_token(
                jti=jti,
                user_id=user.id,
                expires_at=datetime.now() + timedelta(hours=1),
                db=db_session
            )

        # Revoke all except first token
        count = revoke_all_user_tokens(
            user_id=user.id,
            db=db_session,
            except_jti=jtis[0]
        )

        assert count == 2, "Should revoke 2 tokens (not the excepted one)"

        # Verify first token is still active
        token = db_session.query(ActiveToken).filter_by(jti=jtis[0]).first()
        assert token is not None, "Excepted token should still be active"

        # Cleanup
        db_session.query(ActiveToken).filter_by(user_id=user.id).delete()
        db_session.delete(user)
        db_session.commit()


class TestEnumFixes:
    """Test enum values for status fields (lowercase string values; the whole
    codebase compares ``status == Enum.X.value`` with these lowercase values —
    see core/intervention_service.py, core/governance_engine.py)."""

    def test_agent_job_status_values(self):
        """Test AgentJobStatus uses lowercase string values"""
        statuses = [status.value for status in AgentJobStatus]

        assert AgentJobStatus.PENDING.value == 'pending'
        assert AgentJobStatus.RUNNING.value == 'running'
        assert AgentJobStatus.SUCCESS.value == 'success'
        assert AgentJobStatus.FAILED.value == 'failed'

        # All values are lowercase strings
        for status_value in statuses:
            assert isinstance(status_value, str)
            assert status_value.islower(), f"Status {status_value} should be lowercase"

    def test_hitl_action_status_values(self):
        """Test HITLActionStatus uses lowercase string values"""
        assert HITLActionStatus.PENDING.value == 'pending'
        assert HITLActionStatus.APPROVED.value == 'approved'
        assert HITLActionStatus.REJECTED.value == 'rejected'


class TestBusinessAgents:
    """Test business agent implementations"""

    @pytest.mark.asyncio
    async def test_all_agents_available(self):
        """Test all business agents are available"""
        assert len(AGENT_SUITE) == 8, "Should have 8 business agents"

        agent_names = list(AGENT_SUITE.keys())
        expected_names = ['accounting', 'sales', 'marketing', 'logistics',
                         'shipping', 'tax', 'purchasing', 'planning']

        for name in expected_names:
            assert name in agent_names, f"Agent {name} should be available"

    @pytest.mark.asyncio
    async def test_agent_factory(self):
        """Test agent factory function"""
        agent = get_specialized_agent('accounting')
        assert agent is not None, "Should get accounting agent"
        assert agent.name == 'Accounting Assistant'
        assert agent.domain == 'finance'

    @pytest.mark.asyncio
    async def test_accounting_agent_validation(self, db_session):
        """Test accounting agent validates workspace"""
        # Create test workspace
        workspace = Workspace(
            id='test-workspace-accounting',
            name='Test Workspace'
        )
        db_session.add(workspace)
        db_session.commit()

        agent = get_specialized_agent('accounting')

        # Test with missing workspace_id
        result = await agent.run(workspace_id='')
        assert result['status'] == 'error'
        assert 'workspace_id is required' in result['error']

        # Test with valid workspace_id
        result = await agent.run(workspace_id=workspace.id)
        assert result['status'] in ['success', 'error']
        assert 'agent_id' in result
        assert 'workspace_id' in result

        # Cleanup
        db_session.delete(workspace)
        db_session.commit()


class TestWorkflowValidator:
    """Test workflow parameter validator fixes (core.advanced_workflow_system.ParameterValidator).

    The former dedicated module (core.workflow_parameter_validator) was
    archived in 2026-07; the surviving implementation is the static
    ``ParameterValidator.validate_parameter(param, value)`` contract in
    core/advanced_workflow_system.py (with its ReDoS length cap
    ``MAX_REGEX_LENGTH = 256``).
    """

    @staticmethod
    def _param(**overrides) -> InputParameter:
        base = dict(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Param",
            description="A test parameter",
        )
        base.update(overrides)
        return InputParameter(**base)

    def test_required_rule_implementation(self):
        """Test required parameters reject None (with or without default)."""
        rule = self._param(required=True)

        # Should fail for None
        is_valid, error = ParameterValidator.validate_parameter(rule, None)
        assert not is_valid
        assert error == 'Test Param is required'

        # Optional parameter with no value is valid
        is_valid, error = ParameterValidator.validate_parameter(self._param(required=False), None)
        assert is_valid
        assert error is None

        # Should pass for non-empty value
        is_valid, error = ParameterValidator.validate_parameter(rule, 'test')
        assert is_valid
        assert error is None

        # Required + default: default flows through type validation
        is_valid, error = ParameterValidator.validate_parameter(
            self._param(required=True, default_value='fallback'), None
        )
        assert is_valid

    def test_length_rule_implementation(self):
        """Test min_length/max_length custom rules."""
        rule = self._param(
            type=ParameterType.STRING,
            validation_rules={'min_length': 3, 'max_length': 10},
        )

        # Should fail for too short
        is_valid, error = ParameterValidator.validate_parameter(rule, 'ab')
        assert not is_valid
        assert 'at least 3 characters' in error

        # Should fail for too long
        is_valid, error = ParameterValidator.validate_parameter(rule, 'abcdefghijk')
        assert not is_valid
        assert 'at most 10 characters' in error

        # Should pass for valid length
        is_valid, error = ParameterValidator.validate_parameter(rule, 'abc')
        assert is_valid

    def test_numeric_rule_implementation(self):
        """Test number type + min_value/max_value custom rules."""
        rule = self._param(
            type=ParameterType.NUMBER,
            validation_rules={'min_value': 0, 'max_value': 100},
        )

        # Should fail for non-numeric
        is_valid, error = ParameterValidator.validate_parameter(rule, 'not a number')
        assert not is_valid
        assert 'must be a number' in error

        # Should fail for out of range
        is_valid, error = ParameterValidator.validate_parameter(rule, 150)
        assert not is_valid
        assert 'at most 100' in error

        # Should pass for valid number
        is_valid, error = ParameterValidator.validate_parameter(rule, 50)
        assert is_valid

    def test_pattern_rule_redos_guard(self):
        """Test pattern rule validates format and rejects over-long regexes (ReDoS guard)."""
        rule = self._param(validation_rules={'pattern': r'^\d{4}-\d{2}$'})

        is_valid, error = ParameterValidator.validate_parameter(rule, '2026-08')
        assert is_valid

        is_valid, error = ParameterValidator.validate_parameter(rule, 'not-a-date')
        assert not is_valid
        assert 'format is invalid' in error

        # ReDoS guard: a pattern longer than MAX_REGEX_LENGTH is rejected outright
        evil = self._param(validation_rules={'pattern': '(a+)+' + 'x' * MAX_REGEX_LENGTH})
        is_valid, error = ParameterValidator.validate_parameter(evil, 'aaa')
        assert not is_valid
        assert 'pattern is too complex' in error

    def test_type_mismatch_rejected(self):
        """Test wrong types are rejected for each parameter type."""
        cases = [
            (ParameterType.STRING, 42, 'must be a string'),
            (ParameterType.NUMBER, 'nope', 'must be a number'),
            (ParameterType.BOOLEAN, 'yes', 'must be true or false'),
            (ParameterType.ARRAY, 'not-a-list', 'must be an array'),
        ]
        for ptype, bad_value, message in cases:
            param = self._param(type=ptype)
            is_valid, error = ParameterValidator.validate_parameter(param, bad_value)
            assert not is_valid
            assert message in error

    def test_select_rule_implementation(self):
        """Test select parameters restrict to options."""
        rule = self._param(type=ParameterType.SELECT, options=['a', 'b', 'c'])

        is_valid, error = ParameterValidator.validate_parameter(rule, 'a')
        assert is_valid

        is_valid, error = ParameterValidator.validate_parameter(rule, 'zzz')
        assert not is_valid
        assert 'must be one of' in error


class TestResourceGuards:
    """Test resource guard enhancements"""

    def test_integration_timeout_error_has_fields(self):
        """Test IntegrationTimeoutError has proper fields"""
        error = IntegrationTimeoutError(
            message='Test timeout',
            timeout_seconds=30,
            operation='test_operation'
        )

        assert error.message == 'Test timeout'
        assert error.timeout_seconds == 30
        assert error.operation == 'test_operation'

    def test_cpu_guard_functions(self):
        """Test CPUGuard functions work (even if psutil not available)"""
        cpu = CPUGuard.get_cpu_usage_percent()
        assert isinstance(cpu, float)
        assert 0 <= cpu <= 100

        # Test check limit
        result = CPUGuard.check_cpu_limit(max_percent=200)
        assert result == True  # Should always pass with high limit

    def test_memory_guard_functions(self):
        """Test MemoryGuard functions work (even if psutil not available)"""
        memory = MemoryGuard.get_memory_usage_mb()
        assert isinstance(memory, float)
        assert memory >= 0

        # Test check limit
        result = MemoryGuard.check_memory_limit(max_mb=1000000)
        assert result == True  # Should always pass with high limit

    def test_rate_limiter(self):
        """Test RateLimiter implementation"""
        limiter = RateLimiter(max_calls=3, time_window_seconds=60)

        # First 3 calls should succeed
        for _ in range(3):
            assert limiter.check_rate_limit() == True

        # 4th call should be rate limited
        assert limiter.check_rate_limit() == False

        # Check remaining calls
        remaining = limiter.get_remaining_calls()
        assert remaining == 0


class TestAPIGovernance:
    """Test API governance fixes"""

    def test_action_complexity_levels(self):
        """Test ActionComplexity has correct levels"""
        assert ActionComplexity.LOW == 1
        assert ActionComplexity.MODERATE == 2
        assert ActionComplexity.HIGH == 3
        assert ActionComplexity.CRITICAL == 4

    def test_required_maturity_mapping(self):
        """Test maturity level mapping"""
        assert ActionComplexity.get_required_maturity(1) == 'STUDENT'
        assert ActionComplexity.get_required_maturity(2) == 'INTERN'
        assert ActionComplexity.get_required_maturity(3) == 'SUPERVISED'
        assert ActionComplexity.get_required_maturity(4) == 'AUTONOMOUS'


# Fixtures
@pytest.fixture
def db_session():
    """Create a test database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
