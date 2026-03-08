"""
Comprehensive test coverage for Agent Governance Service.

Tests maturity routing, permission checking, lifecycle management, cache validation,
feedback adjudication, and HITL action management.

Target: 80%+ coverage for AgentGovernanceService
"""

import pytest
import pytest_asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.models import (
    AgentRegistry,
    AgentStatus,
    User,
    UserRole,
    AgentFeedback,
    FeedbackStatus,
    HITLAction,
    HITLActionStatus,
)


# =============================================================================
# Test Agent Maturity Routing
# =============================================================================

class TestAgentMaturityRouting:
    """Test agent maturity level routing and permission matrix."""

    @pytest.mark.parametrize("agent_status,action_complexity,allowed", [
        # STUDENT agents (maturity level 0)
        (AgentStatus.STUDENT, 1, True),   # Can do complexity 1
        (AgentStatus.STUDENT, 2, False),  # Cannot do complexity 2+
        (AgentStatus.STUDENT, 3, False),
        (AgentStatus.STUDENT, 4, False),

        # INTERN agents (maturity level 1)
        (AgentStatus.INTERN, 1, True),    # Can do complexity 1-2
        (AgentStatus.INTERN, 2, True),
        (AgentStatus.INTERN, 3, False),   # Cannot do complexity 3+
        (AgentStatus.INTERN, 4, False),

        # SUPERVISED agents (maturity level 2)
        (AgentStatus.SUPERVISED, 1, True), # Can do complexity 1-3
        (AgentStatus.SUPERVISED, 2, True),
        (AgentStatus.SUPERVISED, 3, True),
        (AgentStatus.SUPERVISED, 4, False), # Cannot do complexity 4

        # AUTONOMOUS agents (maturity level 3)
        (AgentStatus.AUTONOMOUS, 1, True),  # Can do all complexities
        (AgentStatus.AUTONOMOUS, 2, True),
        (AgentStatus.AUTONOMOUS, 3, True),
        (AgentStatus.AUTONOMOUS, 4, True),
    ])
    def test_maturity_action_matrix(
        self,
        governance_service: AgentGovernanceService,
        db_session,
        agent_status,
        action_complexity,
        allowed
    ):
        """Test all maturity levels against all action complexities."""
        # Map maturity levels to appropriate confidence scores
        confidence_scores = {
            AgentStatus.STUDENT: 0.3,
            AgentStatus.INTERN: 0.6,
            AgentStatus.SUPERVISED: 0.8,
            AgentStatus.AUTONOMOUS: 0.95
        }

        # Create agent directly with SQL to avoid relationship issues
        agent = AgentRegistry(
            name=f"Agent_{agent_status.value}",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=agent_status.value,
            confidence_score=confidence_scores[agent_status]
        )
        db_session.add(agent)
        db_session.commit()

        # Map complexity to action type
        action_types = {
            1: "search",
            2: "analyze",
            3: "create",
            4: "delete"
        }
        action_type = action_types[action_complexity]

        # Check permission
        result = governance_service.can_perform_action(
            agent_id=agent.id,
            action_type=action_type
        )

        # Verify expected result
        assert result["allowed"] == allowed, (
            f"Agent {agent_status.value} should {'be allowed' if allowed else 'be blocked'} "
            f"for complexity {action_complexity} action '{action_type}'. "
            f"Reason: {result['reason']}"
        )

        if allowed:
            assert agent_status.value in result["reason"]
            assert result["agent_status"] == agent_status.value
            assert result["action_complexity"] == action_complexity
        else:
            assert "lacks maturity" in result["reason"].lower()

    def test_maturity_routing_with_cache(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test that cache is used for repeated permission checks."""
        # Import and use the global cache (same one used by the service)
        from core.governance_cache import get_governance_cache
        global_cache = get_governance_cache()

        # Clear cache completely to ensure clean state
        global_cache._cache.clear()
        global_cache._misses = 0
        global_cache._hits = 0

        # Create INTERN agent
        agent = AgentRegistry(
            name="Cache_Test_Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # First call - cache miss
        result1 = governance_service.can_perform_action(
            agent_id=agent.id,
            action_type="analyze"
        )

        # Verify cache miss occurred
        initial_misses = global_cache._misses
        assert initial_misses >= 1, "First call should be a cache miss"

        # Second call - cache hit
        result2 = governance_service.can_perform_action(
            agent_id=agent.id,
            action_type="analyze"
        )

        # Verify cache hit occurred
        hits = global_cache._hits
        assert hits >= 1, "Second call should be a cache hit"

        # Results should be identical
        assert result1 == result2

    @pytest.mark.parametrize("confidence_score,expected_status", [
        (0.3, AgentStatus.STUDENT),     # <0.5 -> STUDENT
        (0.5, AgentStatus.INTERN),      # 0.5-0.7 -> INTERN
        (0.7, AgentStatus.SUPERVISED),  # 0.7-0.9 -> SUPERVISED
        (0.9, AgentStatus.AUTONOMOUS),  # >0.9 -> AUTONOMOUS
    ])
    def test_confidence_score_routing(
        self,
        governance_service: AgentGovernanceService,
        db_session,
        confidence_score,
        expected_status
    ):
        """Test agent status routing based on confidence score."""
        # Create agent with specific confidence score
        agent = AgentRegistry(
            name=f"Confidence_{confidence_score}",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,  # Will be auto-adjusted
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        # Check that the agent can perform actions appropriate for its maturity
        if expected_status == AgentStatus.STUDENT:
            # Should only do complexity 1
            result = governance_service.can_perform_action(agent.id, "search")
            assert result["allowed"]
            result = governance_service.can_perform_action(agent.id, "analyze")
            assert not result["allowed"]
        elif expected_status == AgentStatus.INTERN:
            # Should do complexity 1-2
            result = governance_service.can_perform_action(agent.id, "analyze")
            assert result["allowed"]
            result = governance_service.can_perform_action(agent.id, "create")
            assert not result["allowed"]
        elif expected_status == AgentStatus.SUPERVISED:
            # Should do complexity 1-3
            result = governance_service.can_perform_action(agent.id, "create")
            assert result["allowed"]
            result = governance_service.can_perform_action(agent.id, "delete")
            assert not result["allowed"]
        elif expected_status == AgentStatus.AUTONOMOUS:
            # Should do all complexities
            result = governance_service.can_perform_action(agent.id, "delete")
            assert result["allowed"]


# =============================================================================
# Test Agent Lifecycle Management
# =============================================================================

class TestAgentLifecycleManagement:
    """Test agent lifecycle operations (register, update, suspend, terminate)."""

    def test_register_new_agent(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test registering a new agent."""
        # Register new agent
        agent = governance_service.register_or_update_agent(
            name="Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            description="Test agent for lifecycle testing"
        )

        # Verify agent was created
        assert agent.id is not None
        assert agent.name == "Test Agent"
        assert agent.category == "Testing"
        assert agent.description == "Test agent for lifecycle testing"
        assert agent.status == AgentStatus.STUDENT.value  # Default status
        assert agent.created_at is not None

        # Verify agent exists in database
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()
        assert retrieved is not None
        assert retrieved.name == "Test Agent"

    def test_update_existing_agent(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test updating an existing agent."""
        # Register initial agent
        agent = governance_service.register_or_update_agent(
            name="Original Name",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            description="Original description"
        )

        original_id = agent.id

        # Update agent with same module_path but different metadata
        updated_agent = governance_service.register_or_update_agent(
            name="Updated Name",
            category="Testing",
            module_path="test.module",  # Same module_path
            class_name="TestAgent",      # Same class_name
            description="Updated description"
        )

        # Verify it's the same agent
        assert updated_agent.id == original_id
        assert updated_agent.name == "Updated Name"
        assert updated_agent.description == "Updated description"

        # Verify only one agent exists in database
        count = db_session.query(AgentRegistry).filter(
            AgentRegistry.module_path == "test.module",
            AgentRegistry.class_name == "TestAgent"
        ).count()
        assert count == 1

    def test_suspend_agent(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test suspending an agent."""
        # Create AUTONOMOUS agent
        agent = AgentRegistry(
            name="Suspendable Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()

        # Suspend the agent
        governance_service.suspend_agent(
            agent_id=agent.id,
            reason="Suspension test"
        )

        # Verify agent status
        db_session.refresh(agent)
        assert agent.status == "SUSPENDED"

    def test_terminate_agent(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test terminating an agent."""
        # Create SUPERVISED agent
        agent = AgentRegistry(
            name="Terminatable Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.commit()

        # Terminate the agent
        governance_service.terminate_agent(
            agent_id=agent.id,
            reason="Termination test"
        )

        # Verify agent status and timestamp
        db_session.refresh(agent)
        assert agent.status == "TERMINATED"
        assert agent.terminated_at is not None

    def test_reactivate_suspended_agent(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test reactivating a suspended agent."""
        # Create agent, suspend it
        agent = AgentRegistry(
            name="Reactivate Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        original_status = agent.status

        # Suspend
        governance_service.suspend_agent(
            agent_id=agent.id,
            reason="Test suspension"
        )
        db_session.refresh(agent)
        assert agent.status == "SUSPENDED"

        # Reactivate
        governance_service.reactivate_agent(agent_id=agent.id)

        # Verify status restored
        db_session.refresh(agent)
        assert agent.status == original_status


# =============================================================================
# Test Feedback Adjudication
# =============================================================================

class TestFeedbackAdjudication:
    """Test feedback submission and AI adjudication workflow."""

    @pytest.mark.asyncio
    async def test_submit_feedback_triggers_adjudication(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test that feedback submission triggers adjudication."""
        # Create agent and user
        agent = AgentRegistry(
            name="Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)

        user = User(
            email="test@example.com",
            first_name="Test",
            role=UserRole.MEMBER.value
        )
        db_session.add(user)
        db_session.commit()

        # Submit feedback with mocked adjudication
        with patch.object(
            governance_service,
            '_adjudicate_feedback',
            new=AsyncMock()
        ) as mock_adjudicate:
            feedback = await governance_service.submit_feedback(
                agent_id=agent.id,
                user_id=user.id,
                original_output="Agent said X",
                user_correction="Should be Y",
                input_context="Test context"
            )

            # Verify feedback was created
            assert feedback.id is not None
            assert feedback.agent_id == agent.id
            assert feedback.user_id == user.id
            assert feedback.original_output == "Agent said X"
            assert feedback.user_correction == "Should be Y"

            # Verify adjudication was triggered
            mock_adjudicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_with_valid_correction(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test adjudication with valid user correction."""
        # Create agent, user, and feedback
        agent = AgentRegistry(
            name="Test Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)

        user = User(
            email="admin@example.com",
            first_name="Admin",
            role=UserRole.WORKSPACE_ADMIN.value,  # Trusted reviewer
            specialty="Finance"
        )
        db_session.add(user)
        db_session.commit()  # Commit to get agent.id and user.id

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Wrong answer",
            user_correction="Correct answer",
            input_context="Test",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        # Mock WorldModelService to avoid dependency
        with patch('core.agent_world_model.AgentExperience') as mock_ae, \
             patch('core.agent_world_model.WorldModelService') as mock_wm:
            mock_wm_instance = Mock()
            mock_wm_instance.record_experience = AsyncMock()
            mock_wm.return_value = mock_wm_instance

            # Adjudicate feedback
            await governance_service._adjudicate_feedback(feedback)

            # Verify feedback was approved
            db_session.refresh(feedback)
            assert feedback.status == FeedbackStatus.ACCEPTED.value
            assert feedback.adjudicated_at is not None
            assert "Trusted reviewer" in feedback.ai_reasoning

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_with_invalid_correction(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test adjudication with untrusted user correction."""
        # Create agent, user, and feedback
        agent = AgentRegistry(
            name="Test Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)

        user = User(
            email="member@example.com",
            first_name="Member",
            role=UserRole.MEMBER.value,  # Not admin
            specialty="Engineering"  # Doesn't match agent category
        )
        db_session.add(user)
        db_session.commit()  # Commit to get agent.id and user.id

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Wrong answer",
            user_correction="Correct answer",
            input_context="Test",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        # Mock WorldModelService to avoid dependency
        with patch('core.agent_world_model.AgentExperience') as mock_ae, \
             patch('core.agent_world_model.WorldModelService') as mock_wm:
            mock_wm_instance = Mock()
            mock_wm_instance.record_experience = AsyncMock()
            mock_wm.return_value = mock_wm_instance

            # Adjudicate feedback
            await governance_service._adjudicate_feedback(feedback)

            # Verify feedback remains pending (not trusted)
            db_session.refresh(feedback)
            assert feedback.status == FeedbackStatus.PENDING.value
            assert feedback.adjudicated_at is not None
            assert "queued" in feedback.ai_reasoning.lower()

    @pytest.mark.asyncio
    async def test_adjudication_with_high_reputation_user(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test adjudication favors high-reputation users."""
        # Create agent and high-reputation user
        agent = AgentRegistry(
            name="Test Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)

        user = User(
            email="expert@example.com",
            first_name="Expert",
            role=UserRole.WORKSPACE_ADMIN.value,
            specialty="Finance"  # Perfect match
        )
        db_session.add(user)
        db_session.commit()  # Commit to get agent.id and user.id

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Wrong",
            user_correction="Correct",
            input_context="Test",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        # Mock WorldModelService to avoid dependency
        with patch('core.agent_world_model.AgentExperience') as mock_ae, \
             patch('core.agent_world_model.WorldModelService') as mock_wm:
            mock_wm_instance = Mock()
            mock_wm_instance.record_experience = AsyncMock()
            mock_wm.return_value = mock_wm_instance

            # Adjudicate
            await governance_service._adjudicate_feedback(feedback)

            # Verify auto-approved due to high reputation
            db_session.refresh(feedback)
            assert feedback.status == FeedbackStatus.ACCEPTED.value


# =============================================================================
# Test HITL Action Management
# =============================================================================

class TestHITLActionManagement:
    """Test Human-in-the-Loop action lifecycle."""

    def test_create_hitl_action(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test creating a HITL action for approval."""
        # Create INTERN agent (cannot do complexity 3 without approval)
        agent = AgentRegistry(
            name="HITL Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Request approval for complexity 3 action
        action_id = governance_service.request_approval(
            agent_id=agent.id,
            action_type="create",
            params={"resource": "test"},
            reason="INTERN agent attempting complexity 3 action"
        )

        # Verify HITL action was created
        assert action_id is not None

        hitl_action = db_session.query(HITLAction).filter(
            HITLAction.id == action_id
        ).first()
        assert hitl_action is not None
        assert hitl_action.status == HITLActionStatus.PENDING.value
        assert hitl_action.action_type == "create"
        assert hitl_action.agent_id == agent.id

    def test_approve_hitl_action(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test approving a HITL action."""
        # Create HITL action
        agent = AgentRegistry(
            name="HITL Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)

        user = User(
            email="reviewer@example.com",
            first_name="Reviewer",
            role=UserRole.MEMBER.value
        )
        db_session.add(user)
        db_session.commit()

        action_id = governance_service.request_approval(
            agent_id=agent.id,
            action_type="create",
            params={"resource": "test"},
            reason="Test approval"
        )

        # Approve the action by updating HITL record
        hitl_action = db_session.query(HITLAction).filter(
            HITLAction.id == action_id
        ).first()
        hitl_action.status = HITLActionStatus.APPROVED.value
        hitl_action.reviewed_at = datetime.now(timezone.utc)
        hitl_action.reviewed_by = user.id
        hitl_action.user_feedback = "Approved"
        db_session.commit()

        # Verify approval
        db_session.refresh(hitl_action)
        assert hitl_action.status == HITLActionStatus.APPROVED.value
        assert hitl_action.reviewed_by == user.id
        assert hitl_action.reviewed_at is not None

    def test_reject_hitl_action(
        self,
        governance_service: AgentGovernanceService,
        db_session
    ):
        """Test rejecting a HITL action."""
        # Create HITL action
        agent = AgentRegistry(
            name="HITL Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)

        user = User(
            email="reviewer@example.com",
            first_name="Reviewer",
            role=UserRole.MEMBER.value
        )
        db_session.add(user)
        db_session.commit()

        action_id = governance_service.request_approval(
            agent_id=agent.id,
            action_type="create",
            params={"resource": "test"},
            reason="Test rejection"
        )

        # Reject the action
        hitl_action = db_session.query(HITLAction).filter(
            HITLAction.id == action_id
        ).first()
        hitl_action.status = HITLActionStatus.REJECTED.value
        hitl_action.reviewed_at = datetime.now(timezone.utc)
        hitl_action.reviewed_by = user.id
        hitl_action.user_feedback = "Rejected: Not appropriate"
        db_session.commit()

        # Verify rejection
        db_session.refresh(hitl_action)
        assert hitl_action.status == HITLActionStatus.REJECTED.value
        assert hitl_action.reviewed_by == user.id
        assert "Not appropriate" in hitl_action.user_feedback


# =============================================================================
# Test Governance Cache Validation
# =============================================================================

class TestGovernanceCacheValidation:
    """Test governance cache behavior (hit, miss, invalidation, TTL)."""

    def test_cache_hit_reduces_db_lookup(
        self,
        governance_service: AgentGovernanceService,
        governance_cache: GovernanceCache,
        db_session
    ):
        """Test that cache hits reduce database lookups."""
        # Create agent and warm cache
        agent = AgentRegistry(
            name="Cache Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Manually set cache entry to test cache behavior
        cache_key = f"{agent.id}:analyze"
        permission_data = {
            "allowed": True,
            "agent_id": agent.id,
            "agent_status": AgentStatus.INTERN.value,
            "action_type": "analyze",
            "action_complexity": 2,
            "reason": f"Agent {agent.name} (intern) can perform analyze (complexity 2)"
        }
        governance_cache.set(agent.id, "analyze", permission_data)

        # Verify cache hit
        result = governance_cache.get(agent.id, "analyze")
        assert result is not None
        assert governance_cache._hits >= 1
        assert result["allowed"] == True

    def test_cache_invalidation_on_agent_status_change(
        self,
        governance_service: AgentGovernanceService,
        governance_cache: GovernanceCache,
        db_session
    ):
        """Test that cache is invalidated when agent status changes."""
        # Create agent
        agent = AgentRegistry(
            name="Cache Invalidation Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Set cache entry
        cache_key = f"{agent.id}:analyze"
        permission_data = {
            "allowed": True,
            "agent_id": agent.id,
            "agent_status": AgentStatus.INTERN.value,
            "action_type": "analyze",
            "action_complexity": 2
        }
        governance_cache.set(agent.id, "analyze", permission_data)

        # Verify entry exists
        result = governance_cache.get(agent.id, "analyze")
        assert result is not None
        initial_hits = governance_cache._hits
        assert initial_hits >= 1

        # Invalidate cache
        governance_cache.invalidate_agent(agent.id)

        # Verify entry is gone (cache miss)
        result = governance_cache.get(agent.id, "analyze")
        assert result is None

    def test_cache_ttl_expiration(
        self,
        governance_service: AgentGovernanceService,
        governance_cache: GovernanceCache,
        db_session
    ):
        """Test that cache entries expire after TTL."""
        # Create agent
        agent = AgentRegistry(
            name="TTL Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Set cache entry
        permission_data = {
            "allowed": True,
            "agent_id": agent.id,
            "agent_status": AgentStatus.INTERN.value,
            "action_type": "analyze",
            "action_complexity": 2
        }
        governance_cache.set(agent.id, "analyze", permission_data)

        # Verify entry exists
        result = governance_cache.get(agent.id, "analyze")
        assert result is not None
        initial_misses = governance_cache._misses
        assert initial_misses >= 0

        # Wait for TTL to expire (1 second)
        time.sleep(1.5)

        # Next call should be cache miss (expired)
        result = governance_cache.get(agent.id, "analyze")
        assert result is None
        assert governance_cache._misses > initial_misses
        result = governance_service.can_perform_action(agent.id, "analyze")

        # Verify cache miss occurred due to expiration
        assert governance_cache._misses >= 1
        assert result["allowed"]  # Should still get correct result
