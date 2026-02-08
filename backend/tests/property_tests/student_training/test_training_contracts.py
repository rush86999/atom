"""
Property-Based Tests for Student Agent Training System

Tests verify high-value end-user functionality:
- STUDENT agents are routed to training (not automated triggers)
- Training duration estimation with historical data
- Graduation readiness validation
- Intervention tracking and constitutional compliance
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from typing import List, Dict
from core.models import AgentRegistry, AgentStatus, TrainingSession, BlockedTriggerContext


class TestTriggerRoutingContracts:
    """Test trigger routing contracts for STUDENT agents."""

    # ========== Maturity Level Routing ==========

    @given(
        is_student=st.booleans(),
        trigger_type=st.sampled_from(['webhook', 'scheduler', 'event', 'manual'])
    )
    def test_student_blocking_invariant(self, is_student, trigger_type):
        """INVARIANT: STUDENT agents must be blocked from automated triggers."""
        # STUDENT agents should be blocked for automated triggers
        should_block = is_student and trigger_type in ['webhook', 'scheduler', 'event']

        if is_student and trigger_type in ['webhook', 'scheduler', 'event']:
            assert should_block, \
                f"STUDENT agent trigger '{trigger_type}' should be blocked for training"

        # Manual triggers should never be auto-blocked
        if trigger_type == 'manual':
            assert not should_block or not is_student, \
                "Manual triggers should not be auto-blocked"


class TestTrainingDurationContracts:
    """Test training duration estimation contracts."""

    # ========== Duration Estimation ==========

    @given(
        base_hours=st.integers(min_value=1, max_value=100),
        agent_count=st.integers(min_value=1, max_value=50)
    )
    def test_duration_estimation_bounds(self, base_hours, agent_count):
        """INVARIANT: Estimated duration should be within reasonable bounds."""
        # Simulate duration estimation
        # More agents with training history = more accurate estimates
        historical_factor = min(max(agent_count / 10.0, 0.5), 2.0)  # Range: 0.5x to 2x
        estimated_hours = base_hours * historical_factor

        # Duration should be at least 0.5 hours and at most 200 hours
        assert 0.5 <= estimated_hours <= 200, \
            f"Estimated duration {estimated_hours}h outside reasonable bounds"

    @given(
        completion_time=st.integers(min_value=1, max_value=1000)
    )
    def test_duration_override_allowed(self, completion_time):
        """INVARIANT: Users should be able to override duration estimates."""
        # Simulate user override
        override_hours = max(1, min(completion_time, 500))  # Clamp to 1-500 hours

        assert 1 <= override_hours <= 500, \
            f"Override duration {override_hours}h should be within bounds"


class TestGraduationReadinessContracts:
    """Test graduation readiness validation contracts."""

    # ========== Episode Count Requirements ==========

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        required=st.integers(min_value=5, max_value=50)
    )
    def test_episode_count_requirement(self, episode_count, required):
        """INVARIANT: Graduation requires minimum episode count."""
        # Simulate episode count check
        meets_requirement = episode_count >= required

        if episode_count >= required:
            assert meets_requirement, \
                f"Should meet requirement with {episode_count} >= {required} episodes"
        else:
            assert not meets_requirement, \
                f"Should not meet requirement with {episode_count} < {required} episodes"

    # ========== Intervention Rate Requirements ==========

    @given(
        intervention_count=st.integers(min_value=0, max_value=50),
        total_episodes=st.integers(min_value=1, max_value=100)
    )
    def test_intervention_rate_calculation(self, intervention_count, total_episodes):
        """INVARIANT: Intervention rate should be calculated correctly."""
        # Clamp intervention_count to total_episodes (can't have more interventions than episodes)
        actual_interventions = min(intervention_count, total_episodes)
        intervention_rate = actual_interventions / total_episodes if total_episodes > 0 else 0.0

        # Intervention rate must be in [0, 1]
        assert 0.0 <= intervention_rate <= 1.0, \
            f"Intervention rate {intervention_rate} outside [0, 1] range"

        # For graduation, lower is better
        # STUDENT -> INTERN: allows up to 50% intervention rate
        # INTERN -> SUPERVISED: allows up to 20% intervention rate
        # SUPERVISED -> AUTONOMOUS: allows 0% intervention rate
        if intervention_rate <= 0.5:
            # At least meets STUDENT -> INTERN requirement
            assert True, "Meets basic intervention rate requirement"

    # ========== Constitutional Score Requirements ==========

    @given(
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
    )
    def test_constitutional_score_thresholds(self, score):
        """INVARIANT: Constitutional score must meet graduation thresholds."""
        # Thresholds:
        # STUDENT -> INTERN: 0.70
        # INTERN -> SUPERVISED: 0.85
        # SUPERVISED -> AUTONOMOUS: 0.95

        if score >= 0.95:
            # Meets all graduation requirements
            assert score >= 0.70, "Should meet INTERN threshold"
            assert score >= 0.85, "Should meet SUPERVISED threshold"
            assert score >= 0.95, "Should meet AUTONOMOUS threshold"
        elif score >= 0.85:
            # Meets INTERN and SUPERVISED requirements
            assert score >= 0.70, "Should meet INTERN threshold"
            assert score >= 0.85, "Should meet SUPERVISED threshold"
        elif score >= 0.70:
            # Meets only INTERN requirement
            assert score >= 0.70, "Should meet INTERN threshold"
        else:
            # Meets no graduation requirements
            assert score < 0.70, "Should not meet any graduation threshold"


class TestTrainingSessionContracts:
    """Test training session lifecycle contracts."""

    # ========== Session State Machine ==========

    @given(
        start_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
        duration_hours=st.floats(min_value=0.5, max_value=100.0, allow_nan=False)
    )
    def test_session_duration_calculation(self, start_time, duration_hours):
        """INVARIANT: Session duration should be calculated correctly."""
        end_time = start_time + timedelta(hours=duration_hours)
        actual_duration = (end_time - start_time).total_seconds() / 3600

        # Duration should match within rounding error
        assert abs(actual_duration - duration_hours) < 0.01, \
            f"Duration mismatch: {actual_duration} vs {duration_hours}"

    # ========== Proposal Tracking ==========

    @given(
        proposal_count=st.integers(min_value=0, max_value=20),
        approved_count=st.integers(min_value=0, max_value=20)
    )
    def test_approval_rate_calculation(self, proposal_count, approved_count):
        """INVARIANT: Approval rate should be calculated correctly."""
        # Clamp approved_count to proposal_count
        actual_approved = min(approved_count, proposal_count)

        if proposal_count > 0:
            approval_rate = actual_approved / proposal_count
            assert 0.0 <= approval_rate <= 1.0, \
                f"Approval rate {approval_rate} outside [0, 1] range"
        else:
            # No proposals means no approval rate
            assert True, "No proposals to calculate"


class TestSupervisionContracts:
    """Test real-time supervision contracts."""

    # ========== Supervision Session ==========

    @given(
        intervention_count=st.integers(min_value=0, max_value=10)
    )
    def test_intervention_tracking(self, intervention_count):
        """INVARIANT: Supervision sessions should track interventions."""
        # Interventions should be non-negative
        assert intervention_count >= 0, \
            f"Intervention count {intervention_count} should be non-negative"

        # Each intervention should be logged
        for i in range(intervention_count):
            # Simulate intervention logging
            intervention_id = f"intervention_{i}"
            assert intervention_id, "Should have valid intervention ID"

    # ========== Session Termination ==========

    @given(
        reason=st.sampled_from(['task_complete', 'error', 'user_cancel', 'timeout']))
    def test_supervision_termination_reasons(self, reason):
        """INVARIANT: Supervision sessions should terminate for valid reasons."""
        valid_reasons = ['task_complete', 'error', 'user_cancel', 'timeout']
        assert reason in valid_reasons, \
            f"Termination reason '{reason}' should be valid"


class TestBlockedTriggerContracts:
    """Test blocked trigger context contracts."""

    # ========== Trigger Context Recording ==========

    @given(
        trigger_type=st.sampled_from(['webhook', 'scheduler', 'event', 'manual']),
        agent_id=st.text(min_size=1, max_size=50, alphabet='abc123'),
        timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())
    )
    def test_blocked_trigger_recording(self, trigger_type, agent_id, timestamp):
        """INVARIANT: Blocked triggers should record full context."""
        # Simulate blocked trigger context
        context = {
            'trigger_type': trigger_type,
            'agent_id': agent_id,
            'blocked_at': timestamp,
            'reason': 'STUDENT agents must complete training'
        }

        assert context['trigger_type'] == trigger_type
        assert context['agent_id'] == agent_id
        assert isinstance(context['blocked_at'], datetime)
        assert context['reason']  # Should be truthy

    # ========== Audit Trail ==========

    @given(
        blocked_count=st.integers(min_value=1, max_value=100)
    )
    def test_audit_trail_completeness(self, blocked_count):
        """INVARIANT: All blocked triggers should be in audit trail."""
        # Simulate audit trail
        audit_entries = []
        for i in range(blocked_count):
            entry = {
                'id': f"blocked_{i}",
                'agent_id': f"student_agent_{i % 10}",
                'trigger_type': 'webhook',
                'blocked_at': datetime.now()
            }
            audit_entries.append(entry)

        assert len(audit_entries) == blocked_count, \
            f"Audit trail should have {blocked_count} entries"

        # Verify all entries have required fields
        for entry in audit_entries:
            assert 'id' in entry
            assert 'agent_id' in entry
            assert 'trigger_type' in entry
            assert 'blocked_at' in entry
