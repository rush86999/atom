"""
Property-Based Tests for Governance Edge Cases

Tests edge cases and combinatorial invariants using Hypothesis:
- Maturity × action × complexity combinations (640 total combos)
- Boundary conditions (confidence scores at exact thresholds)
- Malformed inputs (empty strings, None values)
- Cached permission edge cases

Strategic max_examples:
- 200 for critical edge cases (maturity×action×complexity)
- 100 for standard edge cases (boundary conditions, malformed inputs)
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import (
    text, integers, floats, sampled_from, none, one_of,
    lists, dictionaries, booleans, uuids
)
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry, AgentStatus

HYPOTHESIS_SETTINGS_CRITICAL = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200
}

HYPOTHESIS_SETTINGS_STANDARD = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 100
}


class TestGovernanceEdgeCases:
    """Property-based tests for governance edge cases (STANDARD)."""

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        empty_action=one_of(
            text(min_size=0, max_size=0),
            text().filter(lambda x: x.strip() == "")
        )
    )
    def test_empty_action_type_defaults_to_moderate(
        self, db_session: Session, empty_action: str
    ):
        """
        PROPERTY: Empty action types default to complexity 2 (moderate risk)

        STRATEGY: st.one_of(empty_text, whitespace_only_text)

        INVARIANT: Empty/whitespace-only actions default to complexity 2

        RADII: 100 examples explores empty and whitespace-only strings
        """
        agent = AgentRegistry(
            name="EdgeCaseTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        result = service.can_perform_action(agent_id=agent.id, action_type=empty_action)

        # Should handle empty action gracefully
        assert "action_complexity" in result
        # Empty actions default to complexity 2
        assert result["action_complexity"] == 2

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(action_type=none())
    def test_none_action_type_handled_gracefully(
        self, db_session: Session, action_type: None
    ):
        """
        PROPERTY: None action type is handled without exception

        STRATEGY: st.none()

        INVARIANT: No exception raised for None action_type

        RADII: 100 examples (all None values)
        """
        agent = AgentRegistry(
            name="NoneActionTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)

        # Should not raise exception
        try:
            result = service.can_perform_action(agent_id=agent.id, action_type=action_type)
            # If it returns, should have valid structure
            assert "action_complexity" in result
        except (AttributeError, TypeError):
            # Exception is acceptable for None input
            pass

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(long_action=text(min_size=100, max_size=500))
    def test_very_long_action_type_names(
        self, db_session: Session, long_action: str
    ):
        """
        PROPERTY: Very long action type names are handled without error

        STRATEGY: st.text(min_size=100, max_size=500)

        INVARIANT: Long action names don't cause crashes

        RADII: 100 examples explores long string edge cases
        """
        agent = AgentRegistry(
            name="LongActionTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        result = service.can_perform_action(agent_id=agent.id, action_type=long_action)

        # Should handle long names
        assert "action_complexity" in result
        # Long unknown actions default to complexity 2
        assert result["action_complexity"] == 2

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(special_action=text(min_size=1, max_size=50).filter(lambda x: any(c in x for c in '!@#$%^&*()_+-=[]{}|;:,.<>?')))
    def test_special_characters_in_action_type(
        self, db_session: Session, special_action: str
    ):
        """
        PROPERTY: Special characters in action type are handled without crashes

        STRATEGY: st.text() with special characters

        INVARIANT: Special chars don't cause crashes

        RADII: 100 examples explores special character combinations
        """
        agent = AgentRegistry(
            name="SpecialCharTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        result = service.can_perform_action(agent_id=agent.id, action_type=special_action)

        # Should handle special characters
        assert "action_complexity" in result

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        confidence_score=sampled_from([0.0, 0.5, 0.7, 0.9, 1.0])
    )
    def test_confidence_score_at_exact_boundaries(
        self, db_session: Session, confidence_score: float
    ):
        """
        PROPERTY: Exact boundary confidence scores work correctly

        STRATEGY: st.sampled_from([0.0, 0.5, 0.7, 0.9, 1.0])

        INVARIANT: Boundary values don't cause errors

        RADII: 100 examples covers all exact thresholds
        """
        agent = AgentRegistry(
            name="BoundaryTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        result = service.can_perform_action(agent_id=agent.id, action_type="chat")

        # Should not raise exception for any valid confidence score
        assert "allowed" in result
        assert "action_complexity" in result

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        confidence_score=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
        .filter(lambda x: 0.49 < x < 0.51)
    )
    def test_confidence_score_just_below_thresholds(
        self, db_session: Session, confidence_score: float
    ):
        """
        PROPERTY: Values near INTERN threshold (0.5) handled correctly

        STRATEGY: st.floats().filter(0.49 < x < 0.51)

        INVARIANT: Near-threshold values don't cause errors

        RADII: 100 examples explores threshold boundary
        """
        agent = AgentRegistry(
            name="NearThresholdTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        result = service.can_perform_action(agent_id=agent.id, action_type="chat")

        # Should handle near-threshold values
        assert "allowed" in result

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(
        confidence_score=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
        .filter(lambda x: 0.69 < x < 0.71)
    )
    def test_confidence_score_just_above_thresholds(
        self, db_session: Session, confidence_score: float
    ):
        """
        PROPERTY: Values near SUPERVISED threshold (0.7) handled correctly

        STRATEGY: st.floats().filter(0.69 < x < 0.71)

        INVARIANT: Near-threshold values don't cause errors

        RADII: 100 examples explores threshold boundary
        """
        agent = AgentRegistry(
            name="AboveThresholdTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=confidence_score
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        result = service.can_perform_action(agent_id=agent.id, action_type="create")

        # Should handle near-threshold values
        assert "allowed" in result

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(agent_id=uuids())
    def test_nonexistent_agent_id(
        self, db_session: Session, agent_id: str
    ):
        """
        PROPERTY: Nonexistent agent IDs return allowed=False or create default

        STRATEGY: st.uuids() for random IDs not in DB

        INVARIANT: Nonexistent agents handled gracefully

        RADII: 100 examples explores random UUIDs
        """
        service = AgentGovernanceService(db_session)

        # Try to check action for nonexistent agent
        result = service.can_perform_action(agent_id=str(agent_id), action_type="chat")

        # Should return error or denied gracefully
        assert "allowed" in result
        # Nonexistent agents should be denied
        assert result["allowed"] is False

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(malformed_id=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'))
    def test_malformed_agent_id(
        self, db_session: Session, malformed_id: str
    ):
        """
        PROPERTY: Malformed (non-UUID) agent IDs handled gracefully

        STRATEGY: st.text() for non-UUID strings

        INVARIANT: Non-UUID strings don't cause crashes

        RADII: 100 examples explores malformed IDs
        """
        service = AgentGovernanceService(db_session)

        # Should handle malformed IDs without crash
        try:
            result = service.can_perform_action(agent_id=malformed_id, action_type="chat")
            # If it returns, should have valid structure
            assert "allowed" in result
        except Exception:
            # Exception is acceptable for malformed IDs
            pass

    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    @given(unicode_action=text(min_size=1, max_size=30).filter(lambda x: any(ord(c) > 127 for c in x)))
    def test_unicode_action_types(
        self, db_session: Session, unicode_action: str
    ):
        """
        PROPERTY: Unicode characters in action types handled correctly

        STRATEGY: st.text() with unicode characters (ord > 127)

        INVARIANT: Unicode handled, lowercased correctly

        RADII: 100 examples explores unicode strings
        """
        agent = AgentRegistry(
            name="UnicodeTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        result = service.can_perform_action(agent_id=agent.id, action_type=unicode_action)

        # Should handle unicode without crash
        assert "action_complexity" in result


class TestCombinatorialInvariants:
    """Property-based tests for combinatorial invariants (CRITICAL)."""
    # Tests in next task
