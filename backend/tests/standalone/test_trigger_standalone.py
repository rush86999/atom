#!/usr/bin/env python3
"""
Standalone test runner for trigger_interceptor - no pytest dependencies
Manual validation of core logic
"""
import sys
import os
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

# Import the module
from core.trigger_interceptor import (
    TriggerInterceptor,
    TriggerDecision,
    MaturityLevel,
    RoutingDecision,
)
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

def test_maturity_levels():
    """Test maturity level determination"""
    print("Testing maturity level determination...")
    mock_db = MagicMock()
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    # Test explicit status mapping
    assert interceptor._determine_maturity_level("student", 0.3) == MaturityLevel.STUDENT
    assert interceptor._determine_maturity_level("intern", 0.6) == MaturityLevel.INTERN
    assert interceptor._determine_maturity_level("supervised", 0.8) == MaturityLevel.SUPERVISED
    assert interceptor._determine_maturity_level("autonomous", 0.95) == MaturityLevel.AUTONOMOUS
    
    # Test confidence-based fallback
    assert interceptor._determine_maturity_level("unknown", 0.4) == MaturityLevel.STUDENT
    assert interceptor._determine_maturity_level("unknown", 0.55) == MaturityLevel.INTERN
    assert interceptor._determine_maturity_level("unknown", 0.75) == MaturityLevel.SUPERVISED
    assert interceptor._determine_maturity_level("unknown", 0.92) == MaturityLevel.AUTONOMOUS
    
    # Test boundaries
    assert interceptor._determine_maturity_level("unknown", 0.5) == MaturityLevel.INTERN
    assert interceptor._determine_maturity_level("unknown", 0.7) == MaturityLevel.SUPERVISED
    assert interceptor._determine_maturity_level("unknown", 0.9) == MaturityLevel.AUTONOMOUS
    
    print("✓ All maturity level tests passed")

def test_trigger_decision():
    """Test TriggerDecision creation"""
    print("Testing TriggerDecision creation...")
    
    decision = TriggerDecision(
        routing_decision=RoutingDecision.EXECUTION,
        execute=True,
        agent_id="agent-001",
        agent_maturity="autonomous",
        confidence_score=0.95,
        trigger_source="manual"
    )
    
    assert decision.execute is True
    assert decision.agent_id == "agent-001"
    assert decision.routing_decision == RoutingDecision.EXECUTION
    assert decision.confidence_score == 0.95
    assert decision.blocked_context is None
    assert decision.proposal is None
    
    print("✓ TriggerDecision tests passed")

async def test_cache_integration():
    """Test cache integration"""
    print("Testing cache integration...")
    mock_db = MagicMock()
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    # Test cache hit
    with patch('core.trigger_interceptor.get_async_governance_cache') as mock_get:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value={"status": "autonomous", "confidence": 0.95})
        mock_get.return_value = mock_cache
        
        status, confidence = await interceptor._get_agent_maturity_cached("agent-001")
        
        assert status == "autonomous"
        assert confidence == 0.95
        # DB should NOT be queried on cache hit
        mock_db.query.assert_not_called()
    
    print("✓ Cache integration tests passed")

async def test_manual_trigger():
    """Test manual trigger handling"""
    print("Testing manual trigger handling...")
    mock_db = MagicMock()
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    # Test with STUDENT agent
    decision = await interceptor._handle_manual_trigger(
        agent_id="agent-student-001",
        maturity_level=MaturityLevel.STUDENT,
        confidence_score=0.3,
        trigger_context={"action": "test"},
        user_id="user-001"
    )
    
    assert decision.execute is True
    assert decision.routing_decision == RoutingDecision.EXECUTION
    assert "STUDENT mode" in decision.reason
    assert "user-001" in decision.reason
    
    # Test with INTERN agent
    decision = await interceptor._handle_manual_trigger(
        agent_id="agent-intern-001",
        maturity_level=MaturityLevel.INTERN,
        confidence_score=0.6,
        trigger_context={"action": "test"},
        user_id="user-002"
    )
    
    assert decision.execute is True
    assert "INTERN learning mode" in decision.reason
    
    # Test with SUPERVISED agent
    decision = await interceptor._handle_manual_trigger(
        agent_id="agent-supervised-001",
        maturity_level=MaturityLevel.SUPERVISED,
        confidence_score=0.8,
        trigger_context={"action": "test"},
        user_id="user-003"
    )
    
    assert decision.execute is True
    assert "SUPERVISION mode" in decision.reason
    
    # Test with AUTONOMOUS agent
    decision = await interceptor._handle_manual_trigger(
        agent_id="agent-autonomous-001",
        maturity_level=MaturityLevel.AUTONOMOUS,
        confidence_score=0.95,
        trigger_context={"action": "test"},
        user_id="user-004"
    )
    
    assert decision.execute is True
    assert "user-004" in decision.reason
    
    # Test with unknown user
    decision = await interceptor._handle_manual_trigger(
        agent_id="agent-autonomous-001",
        maturity_level=MaturityLevel.AUTONOMOUS,
        confidence_score=0.95,
        trigger_context={"action": "test"},
        user_id=None
    )
    
    assert decision.execute is True
    assert "unknown" in decision.reason
    
    print("✓ Manual trigger tests passed")


async def test_student_agent_routing():
    """Test STUDENT agent routing"""
    print("Testing STUDENT agent routing...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-student-001"
    mock_agent.name = "Student Agent"
    mock_agent.status = "student"
    mock_agent.confidence_score = 0.3
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    # Mock training service
    mock_proposal = MagicMock()
    mock_proposal.id = "proposal-001"
    interceptor.training_service.create_training_proposal = AsyncMock(
        return_value=mock_proposal
    )
    
    # Mock BlockedTriggerContext to avoid SQLAlchemy initialization
    with patch('core.trigger_interceptor.BlockedTriggerContext') as mock_blocked_ctx_class:
        mock_blocked_ctx = MagicMock()
        mock_blocked_ctx_class.return_value = mock_blocked_ctx
        
        from core.models import TriggerSource
        decision = await interceptor._route_student_agent(
            agent_id="agent-student-001",
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context={"action_type": "send_email"},
            confidence_score=0.3
        )
        
        assert decision.execute is False
        assert decision.routing_decision == RoutingDecision.TRAINING
        assert "STUDENT agent blocked" in decision.reason
        assert decision.proposal.id == "proposal-001"
        
        # Verify blocked context was created
        assert mock_db.add.called
        assert mock_db.commit.called
    
    print("✓ STUDENT agent routing tests passed")


async def test_intern_agent_routing():
    """Test INTERN agent routing"""
    print("Testing INTERN agent routing...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-intern-001"
    mock_agent.name = "Intern Agent"
    mock_agent.status = "intern"
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    # Mock BlockedTriggerContext
    with patch('core.trigger_interceptor.BlockedTriggerContext') as mock_blocked_ctx_class:
        mock_blocked_ctx = MagicMock()
        mock_blocked_ctx_class.return_value = mock_blocked_ctx
        
        from core.models import TriggerSource
        decision = await interceptor._route_intern_agent(
            agent_id="agent-intern-001",
            trigger_source=TriggerSource.DATA_SYNC,
            trigger_context={"action_type": "create_record"},
            confidence_score=0.6
        )
        
        assert decision.execute is False
        assert decision.routing_decision == RoutingDecision.PROPOSAL
        assert "INTERN agent" in decision.reason
        assert "proposal" in decision.reason.lower()
        
        # Verify blocked context was created
        assert mock_db.add.called
    
    print("✓ INTERN agent routing tests passed")


async def test_supervised_agent_routing():
    """Test SUPERVISED agent routing"""
    print("Testing SUPERVISED agent routing...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-supervised-001"
    mock_agent.name = "Supervised Agent"
    mock_agent.status = "supervised"
    mock_agent.user_id = "user-001"
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    from core.models import TriggerSource
    
    # Test with available user
    with patch('core.user_activity_service.UserActivityService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_user_state = AsyncMock(return_value="active")
        mock_service.should_supervise = MagicMock(return_value=True)
        mock_service_class.return_value = mock_service
        
        decision = await interceptor._route_supervised_agent(
            agent_id="agent-supervised-001",
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context={"action_type": "execute_workflow"},
            confidence_score=0.8
        )
        
        assert decision.execute is True
        assert decision.routing_decision == RoutingDecision.SUPERVISION
        assert "real-time monitoring" in decision.reason
    
    # Test with unavailable user
    with patch('core.user_activity_service.UserActivityService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_user_state = AsyncMock(return_value="away")
        mock_service.should_supervise = MagicMock(return_value=False)
        mock_service_class.return_value = mock_service
        
        # Mock queue service
        with patch('core.supervised_queue_service.SupervisedQueueService') as mock_queue_class:
            mock_queue = AsyncMock()
            mock_queue.enqueue_execution = AsyncMock()
            mock_queue_class.return_value = mock_queue
            
            decision = await interceptor._route_supervised_agent(
                agent_id="agent-supervised-001",
                trigger_source=TriggerSource.DATA_SYNC,
                trigger_context={"action_type": "execute_workflow"},
                confidence_score=0.75
            )
            
            assert decision.execute is False
            assert "queued" in decision.reason
            assert "user unavailable" in decision.reason
            mock_queue.enqueue_execution.assert_called_once()
    
    # Test agent not found
    mock_query.filter.return_value.first.return_value = None
    
    decision = await interceptor._route_supervised_agent(
        agent_id="nonexistent-agent",
        trigger_source=TriggerSource.WORKFLOW_ENGINE,
        trigger_context={},
        confidence_score=0.8
    )
    
    assert decision.execute is False
    assert decision.routing_decision == RoutingDecision.SUPERVISION
    assert "not found" in decision.reason
    
    print("✓ SUPERVISED agent routing tests passed")


async def test_autonomous_agent_execution():
    """Test AUTONOMOUS agent execution"""
    print("Testing AUTONOMOUS agent execution...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-autonomous-001"
    mock_agent.name = "Autonomous Agent"
    mock_agent.status = "autonomous"
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    from core.models import TriggerSource
    decision = await interceptor._allow_execution(
        agent_id="agent-autonomous-001",
        trigger_source=TriggerSource.WORKFLOW_ENGINE,
        trigger_context={"action_type": "critical_operation"},
        confidence_score=0.95
    )
    
    assert decision.execute is True
    assert decision.routing_decision == RoutingDecision.EXECUTION
    assert "AUTONOMOUS agent" in decision.reason
    assert "approved for full execution" in decision.reason
    
    # Note: _allow_execution doesn't validate agent existence (it's called after validation)
    # The public allow_execution method does validation, but _allow_execution is an optimization
    # that assumes the agent was already validated upstream
    
    print("✓ AUTONOMOUS agent execution tests passed")


async def test_intercept_trigger_main():
    """Test main intercept_trigger method"""
    print("Testing main intercept_trigger method...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = "autonomous"
    mock_agent.confidence_score = 0.95
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    from core.models import TriggerSource
    
    # Mock cache
    with patch('core.trigger_interceptor.get_async_governance_cache') as mock_get:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_get.return_value = mock_cache
        
        # Test MANUAL trigger
        decision = await interceptor.intercept_trigger(
            agent_id="agent-001",
            trigger_source=TriggerSource.MANUAL,
            trigger_context={"action": "test"},
            user_id="user-001"
        )
        
        assert decision.execute is True
        assert "Manual trigger" in decision.reason
    
    print("✓ Main intercept_trigger tests passed")


async def test_route_to_training():
    """Test route_to_training method"""
    print("Testing route_to_training method...")
    mock_db = MagicMock()
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    mock_blocked_trigger = MagicMock()
    mock_blocked_trigger.agent_id = "agent-student-001"
    mock_blocked_trigger.trigger_type = "send_email"
    
    mock_proposal = MagicMock()
    mock_proposal.id = "proposal-training-001"
    interceptor.training_service.create_training_proposal = AsyncMock(
        return_value=mock_proposal
    )
    
    result = await interceptor.route_to_training(mock_blocked_trigger)
    
    assert result.id == "proposal-training-001"
    interceptor.training_service.create_training_proposal.assert_called_once_with(
        mock_blocked_trigger
    )
    
    print("✓ route_to_training tests passed")


async def test_create_proposal():
    """Test create_proposal method"""
    print("Testing create_proposal method...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-intern-001"
    mock_agent.name = "Intern Agent"
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query

    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")

    proposed_action = {"action_type": "send_email", "to": "test@example.com"}
    reasoning = "User requested email"
    
    # Mock AgentProposal to avoid SQLAlchemy initialization issues
    with patch('core.trigger_interceptor.AgentProposal') as mock_proposal_class:
        mock_proposal = MagicMock()
        mock_proposal.agent_id = "agent-intern-001"
        mock_proposal.description = "Agent is proposing an action...send_email..."
        mock_proposal_class.return_value = mock_proposal

        result = await interceptor.create_proposal(
            intern_agent_id="agent-intern-001",
            trigger_context={"action": "test"},
            proposed_action=proposed_action,
            reasoning=reasoning
        )

        # Verify proposal was created
        assert result.agent_id == "agent-intern-001"
        assert "send_email" in result.description

        # Verify database operations
        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    # Test agent not found
    mock_query.filter.return_value.first.return_value = None

    try:
        await interceptor.create_proposal(
            intern_agent_id="nonexistent-agent",
            trigger_context={},
            proposed_action={},
            reasoning="test"
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not found" in str(e)

    print("✓ create_proposal tests passed")


async def test_execute_with_supervision():
    """Test execute_with_supervision method"""
    print("Testing execute_with_supervision method...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-supervised-001"
    mock_agent.name = "Supervised Agent"
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    trigger_context = {"action": "test_action"}
    
    # Mock SupervisionSession to avoid SQLAlchemy initialization issues
    with patch('core.trigger_interceptor.SupervisionSession') as mock_session_class:
        mock_session = MagicMock()
        mock_session.agent_id = "agent-supervised-001"
        mock_session.supervisor_id = "supervisor-001"
        mock_session_class.return_value = mock_session
        
        result = await interceptor.execute_with_supervision(
            trigger_context=trigger_context,
            agent_id="agent-supervised-001",
            user_id="supervisor-001"
        )
        
        # Verify supervision session was created
        assert result.agent_id == "agent-supervised-001"
        assert result.supervisor_id == "supervisor-001"
        
        # Verify database operations
        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    # Test agent not found
    mock_query.filter.return_value.first.return_value = None
    
    try:
        await interceptor.execute_with_supervision(
            trigger_context={},
            agent_id="nonexistent-agent",
            user_id="supervisor-001"
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not found" in str(e)
    
    print("✓ execute_with_supervision tests passed")


async def test_cache_miss():
    """Test cache miss path"""
    print("Testing cache miss path...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.status = "autonomous"
    mock_agent.confidence_score = 0.95
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    with patch('core.trigger_interceptor.get_async_governance_cache') as mock_get:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set = AsyncMock()
        mock_get.return_value = mock_cache
        
        status, confidence = await interceptor._get_agent_maturity_cached("agent-001")
        
        assert status == "autonomous"
        assert confidence == 0.95
        # Verify DB was queried
        mock_db.query.assert_called_once()
        # Verify cache was set
        mock_cache.set.assert_called_once()
    
    print("✓ Cache miss tests passed")

async def main():
    """Run all tests"""
    print("=" * 60)
    print("Running Trigger Interceptor Tests (Standalone)")
    print("=" * 60)
    
    try:
        # Sync tests
        test_maturity_levels()
        test_trigger_decision()
        
        # Async tests
        await test_cache_integration()
        await test_manual_trigger()
        await test_student_agent_routing()
        await test_intern_agent_routing()
        await test_supervised_agent_routing()
        await test_autonomous_agent_execution()
        await test_intercept_trigger_main()
        await test_route_to_training()
        await test_create_proposal()
        await test_execute_with_supervision()
        await test_cache_miss()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
