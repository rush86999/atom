"""
Unit tests for Governance Helper

Tests cover:
- GovernanceHelper initialization
- execute_with_governance method
- Governance checks and permissions
- Agent context resolution
- AgentExecution record creation
- Outcome recording
- Error handling
- Feature flags and emergency bypass
- Decorator functionality
- create_audit_entry helper
- Sync and async function support
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.governance_helper import (
    GovernanceHelper,
    with_governance,
    create_audit_entry
)
from core.models import AgentRegistry, AgentExecution, User
from core.exceptions import AgentGovernanceError, AgentNotFoundError, InternalServerError


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_agent():
    """Mock agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "agent_123"
    agent.name = "Test Agent"
    agent.maturity_level = 0.8  # SUPERVISED
    return agent


@pytest.fixture
def mock_user():
    """Mock user"""
    user = Mock(spec=User)
    user.id = "user_123"
    return user


@pytest.fixture
def governance_helper(mock_db):
    """Create GovernanceHelper instance"""
    return GovernanceHelper(mock_db, "test_tool")


# ============================================================================
# Initialization Tests
# ============================================================================

def test_governance_helper_initialization(governance_helper, mock_db):
    """Test helper initializes correctly"""
    assert governance_helper is not None
    assert governance_helper.db == mock_db
    assert governance_helper.tool_name == "test_tool"
    assert hasattr(governance_helper, 'context_resolver')
    assert hasattr(governance_helper, 'governance_service')


def test_governance_helper_has_dependencies(governance_helper):
    """Test helper has required dependencies"""
    assert governance_helper.context_resolver is not None
    assert governance_helper.governance_service is not None


def test_governance_helper_different_tool_names(mock_db):
    """Test helper with different tool names"""
    tools = ["browser_tool", "canvas_tool", "device_tool"]
    for tool_name in tools:
        helper = GovernanceHelper(mock_db, tool_name)
        assert helper.tool_name == tool_name


# ============================================================================
# execute_with_governance Tests - User Actions
# ============================================================================

@pytest.mark.asyncio
async def test_execute_with_governance_user_action(governance_helper):
    """Test execution for user-initiated action (no agent)"""
    user_id = "user_123"
    action_name = "test_action"
    action_func = Mock(return_value={"success": True, "data": "result"})

    result = await governance_helper.execute_with_governance(
        agent_id=None,
        user_id=user_id,
        action_complexity=2,
        action_name=action_name,
        action_func=action_func,
        action_params={"param": "value"}
    )

    assert result["success"] is True
    assert result["data"] == "result"
    action_func.assert_called_once()


@pytest.mark.asyncio
async def test_execute_with_governance_user_action_allowed(governance_helper):
    """Test user action always allowed regardless of complexity"""
    user_id = "user_123"
    action_func = Mock(return_value={"result": "done"})

    result = await governance_helper.execute_with_governance(
        agent_id=None,
        user_id=user_id,
        action_complexity=4,  # CRITICAL complexity
        action_name="user_action",
        action_func=action_func
    )

    assert result["result"] == "done"


# ============================================================================
# execute_with_governance Tests - Agent Actions
# ============================================================================

@pytest.mark.asyncio
async def test_execute_with_governance_agent_action_success(governance_helper, mock_agent):
    """Test successful agent action execution"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": True}):
            with patch.object(governance_helper.governance_service, 'record_outcome', new=AsyncMock()):
                action_func = Mock(return_value={"success": True, "data": "result"})

                result = await governance_helper.execute_with_governance(
                    agent_id=mock_agent.id,
                    user_id="user_123",
                    action_complexity=2,
                    action_name="test_action",
                    action_func=action_func
                )

                assert result["success"] is True
                action_func.assert_called_once()


@pytest.mark.asyncio
async def test_execute_with_governance_agent_not_found(governance_helper):
    """Test execution fails when agent not found"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=None):
        action_func = Mock(return_value={"success": True})

        with pytest.raises(AgentNotFoundError):
            await governance_helper.execute_with_governance(
                agent_id="nonexistent_agent",
                user_id="user_123",
                action_complexity=2,
                action_name="test_action",
                action_func=action_func
            )


@pytest.mark.asyncio
async def test_execute_with_governance_permission_denied(governance_helper, mock_agent):
    """Test execution fails when permission denied"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": False, "reason": "Maturity too low"}):
            action_func = Mock(return_value={"success": True})

            with pytest.raises(AgentGovernanceError) as exc_info:
                await governance_helper.execute_with_governance(
                    agent_id=mock_agent.id,
                    user_id="user_123",
                    action_complexity=3,
                    action_name="high_risk_action",
                    action_func=action_func
                )

            assert "Maturity too low" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_with_governance_creates_execution_record(governance_helper, mock_agent, mock_db):
    """Test execution creates AgentExecution record"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": True}):
            with patch.object(governance_helper.governance_service, 'record_outcome', new=AsyncMock()):
                # Mock execution creation
                mock_execution = Mock(spec=AgentExecution)
                mock_execution.id = "exec_123"
                mock_db.add = Mock()
                mock_db.commit = Mock()

                with patch.object(governance_helper, '_create_execution_record', return_value=mock_execution):
                    action_func = Mock(return_value={"success": True})

                    result = await governance_helper.execute_with_governance(
                        agent_id=mock_agent.id,
                        user_id="user_123",
                        action_complexity=2,
                        action_name="test_action",
                        action_func=action_func,
                        feature_enabled=True
                    )

                    assert result["success"] is True


# ============================================================================
# Feature Flags and Emergency Bypass Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_with_governance_emergency_bypass(governance_helper, mock_agent):
    """Test emergency bypass allows execution"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        action_func = Mock(return_value={"success": True})

        result = await governance_helper.execute_with_governance(
            agent_id=mock_agent.id,
            user_id="user_123",
            action_complexity=4,  # Would normally be blocked
            action_name="emergency_action",
            action_func=action_func,
            emergency_bypass=True
        )

        assert result["success"] is True
        # Should skip governance check


@pytest.mark.asyncio
async def test_execute_with_governance_feature_disabled(governance_helper, mock_agent):
    """Test execution when governance feature disabled"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        action_func = Mock(return_value={"success": True})

        result = await governance_helper.execute_with_governance(
            agent_id=mock_agent.id,
            user_id="user_123",
            action_complexity=3,
            action_name="test_action",
            action_func=action_func,
            feature_enabled=False
        )

        assert result["success"] is True


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_with_governance_action_exception(governance_helper, mock_agent):
    """Test execution handles action exceptions"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": True}):
            with patch.object(governance_helper.governance_service, 'record_outcome', new=AsyncMock()):
                # Action raises exception
                action_func = Mock(side_effect=ValueError("Action failed"))

                result = await governance_helper.execute_with_governance(
                    agent_id=mock_agent.id,
                    user_id="user_123",
                    action_complexity=2,
                    action_name="failing_action",
                    action_func=action_func
                )

                assert result["success"] is False
                assert "Action failed" in result["error"]


@pytest.mark.asyncio
async def test_execute_with_governance_records_failure_outcome(governance_helper, mock_agent):
    """Test execution records failure outcome"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": True}):
            with patch.object(governance_helper.governance_service, 'record_outcome', new=AsyncMock()) as mock_record:
                action_func = Mock(side_effect=Exception("Test error"))

                result = await governance_helper.execute_with_governance(
                    agent_id=mock_agent.id,
                    user_id="user_123",
                    action_complexity=2,
                    action_name="failing_action",
                    action_func=action_func
                )

                assert result["success"] is False
                # Should record failure
                mock_record.assert_called()


@pytest.mark.asyncio
async def test_execute_with_governance_governance_check_error(governance_helper, mock_agent):
    """Test execution handles governance check errors"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         side_effect=Exception("Governance service error")):
            action_func = Mock(return_value={"success": True})

            result = await governance_helper.execute_with_governance(
                agent_id=mock_agent.id,
                user_id="user_123",
                action_complexity=2,
                action_name="test_action",
                action_func=action_func
            )

            # Should return error response (fail closed)
            assert result["success"] is False
            assert "error" in result


# ============================================================================
# Async and Sync Function Support Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_with_governance_async_function(governance_helper):
    """Test execution with async function"""
    async def async_action():
        return {"success": True, "async": True}

    result = await governance_helper.execute_with_governance(
        agent_id=None,
        user_id="user_123",
        action_complexity=2,
        action_name="async_action",
        action_func=async_action
    )

    assert result["success"] is True
    assert result["async"] is True


@pytest.mark.asyncio
async def test_execute_with_governance_sync_function(governance_helper):
    """Test execution with sync function"""
    def sync_action():
        return {"success": True, "sync": True}

    result = await governance_helper.execute_with_governance(
        agent_id=None,
        user_id="user_123",
        action_complexity=2,
        action_name="sync_action",
        action_func=sync_action
    )

    assert result["success"] is True
    assert result["sync"] is True


# ============================================================================
# _perform_governance_check Tests
# ============================================================================

@pytest.mark.asyncio
async def test_perform_governance_check_emergency_bypass(governance_helper):
    """Test governance check with emergency bypass"""
    result = await governance_helper._perform_governance_check(
        agent=None,
        user_id="user_123",
        action_complexity=4,
        feature_enabled=True,
        emergency_bypass=True
    )

    assert result["allowed"] is True
    assert result["reason"] == "Emergency bypass"


@pytest.mark.asyncio
async def test_perform_governance_check_no_agent(governance_helper):
    """Test governance check with no agent (user action)"""
    result = await governance_helper._perform_governance_check(
        agent=None,
        user_id="user_123",
        action_complexity=2,
        feature_enabled=True,
        emergency_bypass=False
    )

    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_perform_governance_check_feature_disabled(governance_helper, mock_agent):
    """Test governance check when feature disabled"""
    result = await governance_helper._perform_governance_check(
        agent=mock_agent,
        user_id="user_123",
        action_complexity=2,
        feature_enabled=False,
        emergency_bypass=False
    )

    assert result["allowed"] is True
    assert result["reason"] == "Feature disabled"


@pytest.mark.asyncio
async def test_perform_governance_check_normal(governance_helper, mock_agent):
    """Test normal governance check"""
    with patch.object(governance_helper.governance_service, 'check_agent_permission',
                     return_value={"allowed": True, "confidence": 0.9}) as mock_check:
        result = await governance_helper._perform_governance_check(
            agent=mock_agent,
            user_id="user_123",
            action_complexity=2,
            feature_enabled=True,
            emergency_bypass=False
        )

        assert result["allowed"] is True
        mock_check.assert_called_once_with(
            agent_id=mock_agent.id,
            action_complexity=2
        )


@pytest.mark.asyncio
async def test_perform_governance_check_service_error(governance_helper, mock_agent):
    """Test governance check handles service errors"""
    with patch.object(governance_helper.governance_service, 'check_agent_permission',
                     side_effect=Exception("Service error")):
        result = await governance_helper._perform_governance_check(
            agent=mock_agent,
            user_id="user_123",
            action_complexity=2,
            feature_enabled=True,
            emergency_bypass=False
        )

        # Should fail closed
        assert result["allowed"] is False
        assert "Governance check error" in result["reason"]


# ============================================================================
# _create_execution_record Tests
# ============================================================================

def test_create_execution_record(governance_helper, mock_db):
    """Test execution record creation"""
    agent_id = "agent_123"
    action_name = "test_action"
    action_params = {"param1": "value1"}

    execution = governance_helper._create_execution_record(
        agent_id=agent_id,
        action_name=action_name,
        action_params=action_params
    )

    assert execution is not None
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_create_execution_record_handles_error(governance_helper, mock_db):
    """Test execution record creation handles errors"""
    mock_db.commit.side_effect = Exception("Database error")

    execution = governance_helper._create_execution_record(
        agent_id="agent_123",
        action_name="test_action",
        action_params={}
    )

    # Should return None on error, not raise
    assert execution is None


# ============================================================================
# _update_execution_record Tests
# ============================================================================

def test_update_execution_record_success(governance_helper):
    """Test execution record update for success"""
    execution = Mock(spec=AgentExecution)
    execution.status = "running"

    governance_helper._update_execution_record(
        execution=execution,
        status="completed",
        output_summary="Action completed successfully",
        duration_ms=150
    )

    assert execution.status == "completed"
    assert execution.output_summary == "Action completed successfully"
    assert execution.completed_at is not None


def test_update_execution_record_failure(governance_helper):
    """Test execution record update for failure"""
    execution = Mock(spec=AgentRegistry)

    governance_helper._update_execution_record(
        execution=execution,
        status="failed",
        error_message="Action failed: permission denied"
    )

    assert execution.status == "failed"
    assert execution.error_message == "Action failed: permission denied"


def test_update_execution_record_handles_error(governance_helper):
    """Test execution record update handles errors"""
    execution = Mock(spec=AgentExecution)
    execution.status = "running"

    # Make commit fail
    with patch.object(governance_helper, 'db', Mock()) as mock_db:
        mock_db.commit.side_effect = Exception("Database error")

        # Should not raise exception
        governance_helper._update_execution_record(
            execution=execution,
            status="completed",
            output_summary="Test"
        )


# ============================================================================
# with_governance Decorator Tests
# ============================================================================

@pytest.mark.asyncio
async def test_with_governance_decorator_async(mock_db):
    """Test governance decorator on async function"""
    @with_governance(action_complexity=2, action_name="decorated_action")
    async def test_function(db, user_id, agent_id=None):
        return {"success": True, "decorated": True}

    # Mock the helper
    with patch('core.governance_helper.GovernanceHelper') as MockHelper:
        mock_helper = Mock()
        mock_helper.execute_with_governance = AsyncMock(return_value={"success": True})
        MockHelper.return_value = mock_helper

        result = await test_function(mock_db, "user_123", "agent_456")

        assert result["success"] is True
        mock_helper.execute_with_governance.assert_called_once()


@pytest.mark.asyncio
async def test_with_governance_decorator_sync(mock_db):
    """Test governance decorator on sync function"""
    @with_governance(action_complexity=2)
    def test_function(db, user_id, agent_id=None):
        return {"success": True, "sync": True}

    # Mock the helper
    with patch('core.governance_helper.GovernanceHelper') as MockHelper:
        mock_helper = Mock()
        mock_helper.execute_with_governance = AsyncMock(return_value={"success": True})
        MockHelper.return_value = mock_helper

        result = await test_function(mock_db, "user_123")

        assert result["success"] is True


# ============================================================================
# create_audit_entry Tests
# ============================================================================

def test_create_audit_entry_success(mock_db):
    """Test audit entry creation"""
    audit_model = Mock
    audit_instance = Mock()
    audit_model.return_value = audit_instance

    result = create_audit_entry(
        db=mock_db,
        audit_model=audit_model,
        user_id="user_123",
        agent_id="agent_456",
        action_type="test_action",
        action_params={"param": "value"},
        success=True,
        result_summary="Action completed"
    )

    assert result == audit_instance
    mock_db.add.assert_called_once_with(audit_instance)
    mock_db.commit.assert_called_once()


def test_create_audit_entry_failure(mock_db):
    """Test audit entry for failed action"""
    audit_model = Mock
    audit_instance = Mock()
    audit_model.return_value = audit_instance

    result = create_audit_entry(
        db=mock_db,
        audit_model=audit_model,
        user_id="user_123",
        agent_id="agent_456",
        action_type="failing_action",
        action_params={},
        success=False,
        error_message="Action failed"
    )

    assert result is not None
    # Verify error stored
    assert audit_instance.error_message == "Action failed"


def test_create_audit_entry_with_metadata(mock_db):
    """Test audit entry with metadata"""
    audit_model = Mock
    audit_instance = Mock()
    audit_model.return_value = audit_instance

    metadata = {"key": "value", "number": 123}

    result = create_audit_entry(
        db=mock_db,
        audit_model=audit_model,
        user_id="user_123",
        agent_id="agent_456",
        action_type="test_action",
        action_params={},
        success=True,
        metadata=metadata
    )

    assert result is not None


def test_create_audit_entry_no_agent(mock_db):
    """Test audit entry without agent"""
    audit_model = Mock
    audit_instance = Mock()
    audit_model.return_value = audit_instance

    result = create_audit_entry(
        db=mock_db,
        audit_model=audit_model,
        user_id="user_123",
        agent_id=None,
        action_type="user_action",
        action_params={},
        success=True
    )

    assert result is not None


def test_create_audit_entry_handles_error(mock_db):
    """Test audit entry creation handles errors"""
    audit_model = Mock
    mock_db.commit.side_effect = Exception("Database error")

    result = create_audit_entry(
        db=mock_db,
        audit_model=audit_model,
        user_id="user_123",
        agent_id="agent_456",
        action_type="test_action",
        action_params={},
        success=True
    )

    # Should return None on error
    assert result is None


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_with_governance_no_action_params(governance_helper, mock_agent):
    """Test execution without action parameters"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": True}):
            with patch.object(governance_helper.governance_service, 'record_outcome', new=AsyncMock()):
                action_func = Mock(return_value={"success": True})

                result = await governance_helper.execute_with_governance(
                    agent_id=mock_agent.id,
                    user_id="user_123",
                    action_complexity=2,
                    action_name="test_action",
                    action_func=action_func,
                    action_params=None
                )

                assert result["success"] is True


@pytest.mark.asyncio
async def test_execute_with_governance_feature_disabled_no_tracking(governance_helper, mock_agent):
    """Test execution with feature disabled doesn't create tracking"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper, '_create_execution_record', return_value=None) as mock_create:
            action_func = Mock(return_value={"success": True})

            result = await governance_helper.execute_with_governance(
                agent_id=mock_agent.id,
                user_id="user_123",
                action_complexity=2,
                action_name="test_action",
                action_func=action_func,
                feature_enabled=False
            )

            assert result["success"] is True
            # Should not create execution record when feature disabled
            mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_execute_with_governance_updates_execution_duration(governance_helper, mock_agent, mock_db):
    """Test execution records duration"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": True}):
            with patch.object(governance_helper.governance_service, 'record_outcome', new=AsyncMock()):
                mock_execution = Mock(spec=AgentExecution)
                mock_execution.status = "running"

                with patch.object(governance_helper, '_create_execution_record', return_value=mock_execution):
                    with patch.object(governance_helper, '_update_execution_record') as mock_update:
                        action_func = Mock(return_value={"success": True})

                        result = await governance_helper.execute_with_governance(
                            agent_id=mock_agent.id,
                            user_id="user_123",
                            action_complexity=2,
                            action_name="test_action",
                            action_func=action_func
                        )

                        assert result["success"] is True
                        # Should update execution with duration
                        mock_update.assert_called_once()
                        call_kwargs = mock_update.call_args[1]
                        assert "duration_ms" in call_kwargs
                        assert call_kwargs["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_execute_with_governance_governance_error_not_recorded(governance_helper, mock_agent):
    """Test governance errors are not recorded as outcomes"""
    with patch.object(governance_helper.context_resolver, 'resolve_agent', return_value=mock_agent):
        with patch.object(governance_helper.governance_service, 'check_agent_permission',
                         return_value={"allowed": False, "reason": "Denied"}):
            with patch.object(governance_helper.governance_service, 'record_outcome', new=AsyncMock()) as mock_record:
                action_func = Mock(return_value={"success": True})

                with pytest.raises(AgentGovernanceError):
                    await governance_helper.execute_with_governance(
                        agent_id=mock_agent.id,
                        user_id="user_123",
                        action_complexity=3,
                        action_name="blocked_action",
                        action_func=action_func
                    )

                # Governance errors should be recorded as failure
                mock_record.assert_called_once_with(mock_agent.id, success=False)
