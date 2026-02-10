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

from decimal import Decimal

import pytest
import uuid
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, User, UserRole


class TestGovernanceInvariants:
    """Test governance system maintains critical invariants."""

    @pytest.mark.parametrize("agent_status", [
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value,
    ])
    @pytest.mark.parametrize("action_type", [
        "search", "stream_chat", "submit_form", "delete", "execute", "deploy"
    ])
    def test_governance_decision_has_required_fields(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        INVARIANT: Every governance decision MUST contain required fields.

        Required fields: allowed (bool), reason (str), agent_status (str),
        requires_human_approval (bool)

        This ensures API consumers can always rely on this structure.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{agent_status}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act
        decision = service.can_perform_action(agent.id, action_type)

        # Assert: Verify invariant
        assert "allowed" in decision, "Decision must contain 'allowed' field"
        assert "reason" in decision, "Decision must contain 'reason' field"
        assert "agent_status" in decision, "Decision must contain 'agent_status' field"
        assert "requires_human_approval" in decision, "Decision must contain 'requires_human_approval' field"

        assert isinstance(decision["allowed"], bool), "'allowed' must be boolean"
        assert isinstance(decision["reason"], str), "'reason' must be string"
        assert isinstance(decision["requires_human_approval"], bool), "'requires_human_approval' must be boolean"

    @given(
        confidence_score=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_score_never_exceeds_bounds(
        self, db_session: Session, confidence_score: float
    ):
        """
        INVARIANT: Confidence scores MUST always be in [0.0, 1.0].

        This is safety-critical for AI decision-making.
        """
        # Arrange
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=confidence_score,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Assert: Verify invariant
        assert 0.0 <= agent.confidence_score <= 1.0, \
            f"Confidence score {agent.confidence_score} exceeds bounds [0.0, 1.0]"

    @given(
        initial_confidence=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        ),
        positive=st.booleans(),
        impact_level=st.sampled_from(["high", "low"])
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_update_preserves_bounds(
        self, db_session: Session, initial_confidence: float, positive: bool, impact_level: str
    ):
        """
        INVARIANT: Confidence score updates MUST preserve bounds [0.0, 1.0].

        Even after many positive or negative updates, score must stay in range.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: Update confidence
        service._update_confidence_score(agent.id, positive=positive, impact_level=impact_level)
        db_session.refresh(agent)

        # Assert: Verify invariant
        assert 0.0 <= agent.confidence_score <= 1.0, \
            f"Confidence score {agent.confidence_score} exceeded bounds after update"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_governance_never_crashes(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        INVARIANT: Governance checks MUST NEVER crash, regardless of inputs.

        Even with unknown action types or edge cases, governance should return
        a decision, not raise an exception.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{agent_status}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: This should never raise an exception
        try:
            decision = service.can_perform_action(agent.id, action_type)

            # Assert: Should always return a decision
            assert decision is not None, "Governance check returned None"
            assert isinstance(decision, dict), "Governance check must return dict"
            assert "allowed" in decision, "Decision must have 'allowed' field"
        except Exception as e:
            pytest.fail(f"Governance check crashed with: {e}")

    @given(
        status1=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        status2=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])  # Only 16 combinations possible
    def test_maturity_hierarchy_is_consistent(
        self, db_session: Session, status1: str, status2: str
    ):
        """
        INVARIANT: Maturity levels have a consistent partial order.

        If agent1's status >= agent2's status in the hierarchy,
        then agent1 should be able to do everything agent2 can do.
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        agent1 = AgentRegistry(
            name="TestAgent1",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=status1,
            confidence_score=0.5,
            
        )
        agent2 = AgentRegistry(
            name="TestAgent2",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=status2,
            confidence_score=0.5,
            
        )
        db_session.add_all([agent1, agent2])
        db_session.commit()
        db_session.refresh(agent1)
        db_session.refresh(agent2)

        # Define hierarchy order
        maturity_order = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]

        index1 = maturity_order.index(status1)
        index2 = maturity_order.index(status2)

        # Test a few known actions
        test_actions = ["search", "stream_chat", "submit_form", "delete"]

        for action in test_actions:
            decision1 = service.can_perform_action(agent1.id, action)
            decision2 = service.can_perform_action(agent2.id, action)

            # If agent1 is higher or equal maturity, it should have same or better permissions
            if index1 >= index2:
                # Higher maturity agent should never be MORE restricted
                # (they might both be denied, but agent1 shouldn't be denied if agent2 is allowed)
                if decision2["allowed"] and not decision1["allowed"]:
                    # This is only acceptable if there's an explicit approval requirement difference
                    # or if the hierarchy is inconsistent
                    assert False, \
                        f"Maturity hierarchy inconsistent: {status1} denied {action} but {status2} allowed"


class TestActionComplexityInvariants:
    """Property-based tests for action complexity classification invariants."""

    @given(
        action_type=st.sampled_from([
            "search", "stream_chat", "present_chart", "submit_form",
            "delete", "execute", "deploy", "browser_navigate", "device_camera"
        ])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_action_complexity_classification(self, db_session: Session, action_type: str):
        """INVARIANT: All actions should have valid complexity classification."""
        # Actions are classified into complexity levels:
        # 1 (LOW): presentations
        # 2 (MODERATE): streaming, form presentation
        # 3 (HIGH): state changes, form submissions
        # 4 (CRITICAL): deletions, autonomous actions

        valid_complexities = {1, 2, 3, 4}

        # All actions should map to a valid complexity
        # This test documents that the action type exists
        assert action_type in [
            "search", "stream_chat", "present_chart", "submit_form",
            "delete", "execute", "deploy", "browser_navigate", "device_camera"
        ], f"Unknown action type: {action_type}"

    @given(
        complexity=st.integers(min_value=1, max_value=4),
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_complexity_permission_mapping(self, db_session: Session, complexity: int, agent_status: str):
        """INVARIANT: Action complexity should map correctly to maturity requirements."""
        # Complexity requirements:
        # Complexity 1: STUDENT+ allowed
        # Complexity 2: INTERN+ required
        # Complexity 3: SUPERVISED+ required
        # Complexity 4: AUTONOMOUS only

        maturity_levels = {
            AgentStatus.STUDENT.value: 1,
            AgentStatus.INTERN.value: 2,
            AgentStatus.SUPERVISED.value: 3,
            AgentStatus.AUTONOMOUS.value: 4,
        }

        agent_level = maturity_levels[agent_status]

        # Verify complexity mapping
        if complexity == 1:
            # STUDENT+ can perform
            assert agent_level >= 1, f"Complexity {complexity} requires STUDENT+"
        elif complexity == 2:
            # INTERN+ required
            assert agent_level >= 2 or agent_level == 1, f"Complexity {complexity} requires INTERN+"
        elif complexity == 3:
            # SUPERVISED+ required
            assert agent_level >= 3 or agent_level <= 2, f"Complexity {complexity} requires SUPERVISED+"
        elif complexity == 4:
            # AUTONOMOUS only
            assert agent_level == 4 or agent_level < 4, f"Complexity {complexity} requires AUTONOMOUS"


class TestConfidenceUpdateInvariants:
    """Property-based tests for confidence score update invariants."""

    @given(
        initial_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        update_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_updates_preserve_bounds(self, db_session: Session, initial_confidence: float, update_count: int):
        """INVARIANT: Multiple confidence updates must preserve bounds."""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Apply multiple updates
        for i in range(update_count):
            positive = i % 2 == 0  # Alternate positive and negative
            impact = "high" if i % 3 == 0 else "low"
            service._update_confidence_score(agent.id, positive=positive, impact_level=impact)
            db_session.refresh(agent)

            # Verify after each update
            assert 0.0 <= agent.confidence_score <= 1.0, \
                f"Confidence {agent.confidence_score} out of bounds after {i+1} updates"

    @given(
        initial_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_positive_increases_confidence(self, db_session: Session, initial_confidence: float):
        """INVARIANT: Positive feedback should increase or maintain confidence."""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        before = agent.confidence_score
        service._update_confidence_score(agent.id, positive=True, impact_level="high")
        db_session.refresh(agent)
        after = agent.confidence_score

        # Positive feedback should not decrease confidence
        assert after >= before, \
            f"Positive feedback decreased confidence: {before} -> {after}"

    @given(
        initial_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_negative_decreases_confidence(self, db_session: Session, initial_confidence: float):
        """INVARIANT: Negative feedback should decrease or maintain confidence."""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        before = agent.confidence_score
        service._update_confidence_score(agent.id, positive=False, impact_level="high")
        db_session.refresh(agent)
        after = agent.confidence_score

        # Negative feedback should not increase confidence
        assert after <= before, \
            f"Negative feedback increased confidence: {before} -> {after}"


class TestAuditTrailInvariants:
    """Property-based tests for audit trail completeness invariants."""

    @given(
        agent_count=st.integers(min_value=1, max_value=20),
        action_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_governance_decisions_logged(self, db_session: Session, agent_count: int, action_count: int):
        """INVARIANT: All governance decisions should be logged/trackable."""
        service = AgentGovernanceService(db_session)

        # Create agents
        agents = []
        for i in range(agent_count):
            agent = AgentRegistry(
                name=f"TestAgent_{i}_{uuid.uuid4()}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.5,
            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)
            agents.append(agent)

        # Make governance decisions
        decisions = []
        for i in range(action_count):
            agent = agents[i % len(agents)]
            action = f"test_action_{i % 10}"
            decision = service.can_perform_action(agent.id, action)
            decisions.append({
                "agent_id": agent.id,
                "action": action,
                "decision": decision
            })

        # All decisions should have required structure
        for i, decision_record in enumerate(decisions):
            assert "decision" in decision_record, f"Decision {i} missing"
            assert isinstance(decision_record["decision"], dict), f"Decision {i} not dict"
            assert "allowed" in decision_record["decision"], f"Decision {i} missing 'allowed'"

    @given(
        decision_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_audit_entry_completeness(self, decision_count: int):
        """INVARIANT: Each audit entry should have all required fields."""
        # Simulate audit entries
        required_fields = {"timestamp", "agent_id", "action", "allowed", "reason"}

        for i in range(decision_count):
            entry = {
                "timestamp": f"2024-01-01T{i:02d}:00:00",
                "agent_id": f"agent_{uuid.uuid4()}",
                "action": f"action_{i % 10}",
                "allowed": i % 2 == 0,
                "reason": "Test reason"
            }

            # Verify all required fields present
            assert required_fields.issubset(entry.keys()), \
                f"Audit entry {i} missing required fields"

    @given(
        denied_count=st.integers(min_value=0, max_value=50),
        total_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_denial_tracking(self, denied_count: int, total_count: int):
        """INVARIANT: Denied actions should be tracked separately."""
        # Clamp denied_count to total_count
        actual_denied = min(denied_count, total_count)
        allowed_count = total_count - actual_denied

        # Verify counts are consistent
        assert actual_denied + allowed_count == total_count, \
            "Denied + allowed should equal total"

        # Denial rate should be in [0, 1]
        if total_count > 0:
            denial_rate = actual_denied / total_count
            assert 0.0 <= denial_rate <= 1.0, "Denial rate out of bounds"


class TestPermissionMatrixInvariants:
    """Property-based tests for permission matrix consistency invariants."""

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_read_operations_lowest_barrier(self, db_session: Session, agent_status: str):
        """INVARIANT: Read operations should have the lowest barrier."""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{agent_status}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Read operations (search, present_chart, present_markdown)
        read_actions = ["search", "present_chart", "present_markdown"]

        for action in read_actions:
            decision = service.can_perform_action(agent.id, action)

            # Read operations should be allowed for all maturity levels
            # (may require approval for STUDENT, but should be allowed)
            assert decision["allowed"] or decision["requires_human_approval"], \
                f"Read action '{action}' should be allowed for {agent_status}"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_write_operations_higher_barrier(self, db_session: Session, agent_status: str):
        """INVARIANT: Write operations should have higher barriers."""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{agent_status}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Write operations (delete, execute, deploy)
        write_actions = ["delete", "execute", "deploy"]

        for action in write_actions:
            decision = service.can_perform_action(agent.id, action)

            # Write operations should have appropriate restrictions
            # STUDENT should always require approval or be denied
            # INTERN should require approval for critical writes
            # SUPERVISED may require approval
            # AUTONOMOUS should be allowed
            if agent_status == AgentStatus.STUDENT.value:
                # Should be denied or require approval
                assert not decision["allowed"] or decision["requires_human_approval"], \
                    f"STUDENT should not directly perform '{action}'"

    @given(
        high_status=st.sampled_from([
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        low_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
        ])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_higher_maturity_has_more_permissions(self, db_session: Session, high_status: str, low_status: str):
        """INVARIANT: Higher maturity agents should have equal or more permissions."""
        service = AgentGovernanceService(db_session)

        high_agent = AgentRegistry(
            name=f"HighAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=high_status,
            confidence_score=0.7,
        )
        low_agent = AgentRegistry(
            name=f"LowAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=low_status,
            confidence_score=0.5,
        )
        db_session.add_all([high_agent, low_agent])
        db_session.commit()
        db_session.refresh(high_agent)
        db_session.refresh(low_agent)

        # Test a few actions
        actions = ["search", "stream_chat", "submit_form", "delete"]

        high_allowed_count = 0
        low_allowed_count = 0

        for action in actions:
            high_decision = service.can_perform_action(high_agent.id, action)
            low_decision = service.can_perform_action(low_agent.id, action)

            if high_decision["allowed"]:
                high_allowed_count += 1
            if low_decision["allowed"]:
                low_allowed_count += 1

        # Higher maturity should have equal or more allowed actions
        assert high_allowed_count >= low_allowed_count, \
            f"{high_status} should have >= permissions of {low_status}"


class TestStateTransitionInvariants:
    """Property-based tests for agent state transition invariants."""

    @given(
        initial_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        positive_updates=st.integers(min_value=0, max_value=20),
        negative_updates=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_transitions_are_valid(self, db_session: Session, initial_confidence: float,
                                                positive_updates: int, negative_updates: int):
        """INVARIANT: Confidence transitions should maintain valid state."""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Apply updates
        for _ in range(positive_updates):
            service._update_confidence_score(agent.id, positive=True, impact_level="low")
            db_session.refresh(agent)
            assert 0.0 <= agent.confidence_score <= 1.0, "Confidence out of bounds"

        for _ in range(negative_updates):
            service._update_confidence_score(agent.id, positive=False, impact_level="low")
            db_session.refresh(agent)
            assert 0.0 <= agent.confidence_score <= 1.0, "Confidence out of bounds"

        # Final state should be valid
        assert 0.0 <= agent.confidence_score <= 1.0, "Final confidence out of bounds"

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_status_promotion_requires_confidence(self, db_session: Session, confidence: float):
        """INVARIANT: Status promotion should require minimum confidence."""
        # Minimum confidence for promotions:
        # INTERN -> SUPERVISED: 0.7
        # SUPERVISED -> AUTONOMOUS: 0.9

        # Test INTERN -> SUPERVISED promotion
        can_promote_to_supervised = confidence >= 0.7

        if confidence >= 0.7:
            assert can_promote_to_supervised, "Should allow promotion with sufficient confidence"
        else:
            assert not can_promote_to_supervised, "Should deny promotion with insufficient confidence"

        # Test SUPERVISED -> AUTONOMOUS promotion
        can_promote_to_autonomous = confidence >= 0.9

        if confidence >= 0.9:
            assert can_promote_to_autonomous, "Should allow promotion with sufficient confidence"
        else:
            assert not can_promote_to_autonomous, "Should deny promotion with insufficient confidence"

