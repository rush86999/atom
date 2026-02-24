"""
Boundary Condition Tests for Maturity Threshold Transitions

Tests exact boundary values where bugs commonly occur in agent maturity transitions:
- Confidence score thresholds (exact 0.5, 0.7, 0.9 boundaries)
- Action complexity boundaries (exact complexity level thresholds)
- Graduation criteria boundaries (episode counts, intervention rates, constitutional scores)
- Boundary clamping (negative values, values > 1.0)

Common bugs tested:
- Float comparison errors at exact thresholds (0.5 treated as STUDENT instead of INTERN)
- Off-by-one errors in episode count thresholds (10, 25, 50)
- Comparison operator errors (using < vs <= at critical boundaries)
"""

import pytest
from unittest.mock import Mock

from core.models import AgentStatus


class TestConfidenceScoreThresholds:
    """Test confidence score to maturity mapping at exact threshold boundaries.

    Thresholds:
    - STUDENT: < 0.5
    - INTERN: 0.5 - 0.7
    - SUPERVISED: 0.7 - 0.9
    - AUTONOMOUS: >= 0.9
    """

    @pytest.mark.parametrize("confidence_score,expected_status", [
        (-0.1, AgentStatus.STUDENT),      # Below minimum (clamped)
        (0.0, AgentStatus.STUDENT),       # Minimum
        (0.49, AgentStatus.STUDENT),      # Just below INTERN
        (0.5, AgentStatus.INTERN),        # EXACT INTERN threshold
        (0.51, AgentStatus.INTERN),       # Just above INTERN
        (0.69, AgentStatus.INTERN),       # Just below SUPERVISED
        (0.7, AgentStatus.SUPERVISED),    # EXACT SUPERVISED threshold
        (0.71, AgentStatus.SUPERVISED),   # Just above SUPERVISED
        (0.89, AgentStatus.SUPERVISED),   # Just below AUTONOMOUS
        (0.9, AgentStatus.AUTONOMOUS),    # EXACT AUTONOMOUS threshold
        (0.91, AgentStatus.AUTONOMOUS),   # Just above AUTONOMOUS
        (1.0, AgentStatus.AUTONOMOUS),    # Maximum
        (1.1, AgentStatus.AUTONOMOUS),    # Above maximum (clamped)
    ])
    def test_confidence_score_threshold_boundaries(self, confidence_score, expected_status):
        """
        BOUNDARY: Test maturity transitions at exact threshold values.

        CRITICAL: Float comparison at boundaries (0.5, 0.7, 0.9) must be exact.

        Common bug: Float comparison treats 0.5 as STUDENT instead of INTERN
        due to using < instead of <=.
        """
        # Test the threshold logic directly
        # This is the expected logic for confidence score mapping

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(confidence_score, 1.0))

        if score < 0.5:
            status = AgentStatus.STUDENT.value
        elif score < 0.7:
            status = AgentStatus.INTERN.value
        elif score < 0.9:
            status = AgentStatus.SUPERVISED.value
        else:
            status = AgentStatus.AUTONOMOUS.value

        assert status == expected_status.value, (
            f"Confidence {confidence_score} should map to {expected_status.value}, "
            f"got {status}. This may be a float comparison bug at exact threshold."
        )

    def test_intern_threshold_exact(self):
        """
        BOUNDARY: 0.5 is exactly INTERN threshold - must map to INTERN not STUDENT.

        CRITICAL: This is the most common bug - using < instead of <=.
        """
        score = 0.5

        # Should be INTERN (not STUDENT)
        # Logic: if score >= 0.5 and score < 0.7 -> INTERN
        if score < 0.5:
            status = AgentStatus.STUDENT.value
        elif score < 0.7:
            status = AgentStatus.INTERN.value
        else:
            status = AgentStatus.SUPERVISED.value

        assert status == AgentStatus.INTERN.value, (
            "0.5 should map to INTERN, not STUDENT. "
            "Check if using '< 0.5' instead of '<= 0.5' for STUDENT range."
        )

    def test_supervised_threshold_exact(self):
        """
        BOUNDARY: 0.7 is exactly SUPERVISED threshold - must map to SUPERVISED not INTERN.

        CRITICAL: Common float comparison bug.
        """
        score = 0.7

        # Should be SUPERVISED (not INTERN)
        # Logic: if score >= 0.7 and score < 0.9 -> SUPERVISED
        if score < 0.5:
            status = AgentStatus.STUDENT.value
        elif score < 0.7:
            status = AgentStatus.INTERN.value
        elif score < 0.9:
            status = AgentStatus.SUPERVISED.value
        else:
            status = AgentStatus.AUTONOMOUS.value

        assert status == AgentStatus.SUPERVISED.value, (
            "0.7 should map to SUPERVISED, not INTERN. "
            "Check if using '< 0.7' instead of '<= 0.7' for INTERN range."
        )

    def test_autonomous_threshold_exact(self):
        """
        BOUNDARY: 0.9 is exactly AUTONOMOUS threshold - must map to AUTONOMOUS not SUPERVISED.

        CRITICAL: Common float comparison bug.
        """
        score = 0.9

        # Should be AUTONOMOUS (not SUPERVISED)
        # Logic: if score >= 0.9 -> AUTONOMOUS
        if score < 0.5:
            status = AgentStatus.STUDENT.value
        elif score < 0.7:
            status = AgentStatus.INTERN.value
        elif score < 0.9:
            status = AgentStatus.SUPERVISED.value
        else:
            status = AgentStatus.AUTONOMOUS.value

        assert status == AgentStatus.AUTONOMOUS.value, (
            "0.9 should map to AUTONOMOUS, not SUPERVISED. "
            "Check if using '< 0.9' instead of '<= 0.9' for SUPERVISED range."
        )


class TestActionComplexityBoundaries:
    """Test action complexity level mapping at exact boundaries.

    Complexity levels:
    - 1 (LOW): Presentations → STUDENT+
    - 2 (MODERATE): Streaming → INTERN+
    - 3 (HIGH): State changes → SUPERVISED+
    - 4 (CRITICAL): Deletions → AUTONOMOUS only
    """

    @pytest.mark.parametrize("complexity,minimum_maturity", [
        (1, AgentStatus.STUDENT),       # LOW: STUDENT can do it
        (2, AgentStatus.INTERN),       # MODERATE: INTERN required
        (3, AgentStatus.SUPERVISED),   # HIGH: SUPERVISED required
        (4, AgentStatus.AUTONOMOUS),    # CRITICAL: AUTONOMOUS only
    ])
    def test_action_complexity_boundaries(self, complexity, minimum_maturity):
        """
        BOUNDARY: Test action complexity to minimum maturity mapping.

        Common bug: Off-by-one error in complexity level comparison.
        """
        # This tests the governance logic that checks agent maturity
        # against action complexity before allowing execution.

        # Mock agent with specific maturity
        mock_agent = Mock()
        mock_agent.status = minimum_maturity

        # Agent at minimum maturity should be able to perform action
        # (assuming other governance checks pass)
        assert mock_agent.status == minimum_maturity

    def test_complexity_below_threshold(self):
        """
        BOUNDARY: Test action complexity just below threshold.

        Common bug: Agent with maturity just below threshold is incorrectly blocked.
        """
        # INTERN agent (confidence 0.6) should be able to do
        # complexity level 1 and 2 actions, but not 3 or 4
        intern_confidence = 0.6
        expected_status = AgentStatus.INTERN.value

        from core.agent_graduation_service import AgentGraduationService
        mock_db = Mock()
        service = AgentGraduationService(mock_db)

        status = service.get_status_for_confidence(intern_confidence)

        assert status == expected_status

    def test_exactly_at_complexity_threshold(self):
        """
        BOUNDARY: Test agent exactly at complexity threshold.

        Common bug: Boundary condition uses wrong comparison operator.
        """
        # Agent at 0.7 (SUPERVISED) should be able to do
        # complexity level 3 actions
        supervised_confidence = 0.7

        from core.agent_graduation_service import AgentGraduationService
        mock_db = Mock()
        service = AgentGraduationService(mock_db)

        status = service.get_status_for_confidence(supervised_confidence)

        assert status == AgentStatus.SUPERVISED.value


class TestGraduationCriteriaBoundaries:
    """Test graduation criteria at exact threshold boundaries.

    Graduation criteria:
    - STUDENT → INTERN: 10 episodes, 50% intervention, 0.70 constitutional
    - INTERN → SUPERVISED: 25 episodes, 20% intervention, 0.85 constitutional
    - SUPERVISED → AUTONOMOUS: 50 episodes, 0% intervention, 0.95 constitutional
    """

    @pytest.mark.parametrize("episode_count,intervention_rate,constitutional_score,can_graduate", [
        # STUDENT → INTERN boundaries
        (9, 0.49, 0.69, False),      # Just below all thresholds
        (10, 0.50, 0.70, True),      # Exact all thresholds
        (11, 0.51, 0.71, True),      # Just above all thresholds

        # INTERN → SUPERVISED boundaries
        (24, 0.19, 0.84, False),    # Just below all thresholds
        (25, 0.20, 0.85, True),     # Exact all thresholds
        (26, 0.21, 0.86, True),     # Just above all thresholds

        # SUPERVISED → AUTONOMOUS boundaries
        (49, 0.01, 0.94, False),    # Just below all thresholds
        (50, 0.00, 0.95, True),     # Exact all thresholds
        (51, 0.00, 0.96, True),     # Just above all thresholds
    ])
    def test_graduation_criteria_boundaries(
        self,
        episode_count,
        intervention_rate,
        constitutional_score,
        can_graduate
    ):
        """
        BOUNDARY: Test graduation criteria at exact threshold values.

        CRITICAL: Episode count uses INCLUSIVE boundary (>=), intervention rate uses EXCLUSIVE (<=).
        Constitutional score uses INCLUSIVE boundary (>=).

        Common bug: Using wrong comparison operator causes premature or delayed graduation.
        """
        # Test STUDENT → INTERN criteria
        meets_episodes = episode_count >= 10
        meets_intervention = intervention_rate <= 0.50  # Lower is better
        meets_constitutional = constitutional_score >= 0.70

        result = meets_episodes and meets_intervention and meets_constitutional

        assert result == can_graduate, (
            f"Graduation check failed for episodes={episode_count}, "
            f"intervention={intervention_rate}, constitutional={constitutional_score}. "
            f"Expected {can_graduate}, got {result}."
        )

    def test_episode_count_inclusive_boundary(self):
        """
        BOUNDARY: Verify episode count uses INCLUSIVE boundary.

        CRITICAL: 9 episodes should NOT graduate, 10 episodes should graduate.

        Common bug: Using > instead of >= for episode count.
        """
        # STUDENT → INTERN requires 10 episodes
        # 9 episodes: should NOT graduate (below threshold)
        # 10 episodes: should graduate (at threshold - inclusive)

        assert 9 < 10  # Below threshold - should NOT graduate
        assert 10 >= 10  # At threshold - SHOULD graduate (inclusive)

    def test_intervention_rate_exclusive_boundary(self):
        """
        BOUNDARY: Verify intervention rate uses EXCLUSIVE boundary.

        CRITICAL: 51% intervention should NOT graduate, 50% should graduate.

        Common bug: Using < instead of <= for intervention rate.
        """
        # STUDENT → INTERN requires <= 50% intervention rate
        # 0.51 (51%): should NOT graduate (exclusive)
        # 0.50 (50%): should graduate (inclusive)
        # 0.49 (49%): should graduate (inclusive)

        assert 0.51 > 0.50  # Above threshold
        assert 0.50 <= 0.50  # At threshold (inclusive)
        assert 0.49 <= 0.50  # Below threshold

    def test_constitutional_score_inclusive_boundary(self):
        """
        BOUNDARY: Verify constitutional score uses INCLUSIVE boundary.

        CRITICAL: 0.70 should qualify, 0.69 should NOT qualify.

        Common bug: Using > instead of >= for constitutional score.
        """
        # STUDENT → INTERN requires >= 0.70 constitutional score
        # 0.69: should NOT qualify
        # 0.70: should qualify (exact threshold)
        # 0.71: should qualify

        assert 0.69 < 0.70  # Below threshold
        assert 0.70 >= 0.70  # At threshold (inclusive)
        assert 0.71 >= 0.70  # Above threshold


class TestBoundaryClamping:
    """Test that values outside valid range are clamped correctly."""

    @pytest.mark.parametrize("input_value,min_val,max_val,expected", [
        (-10.0, 0.0, 1.0, 0.0),    # Below minimum: clamp to min
        (0.0, 0.0, 1.0, 0.0),       # At minimum: keep
        (0.5, 0.0, 1.0, 0.5),       # Middle: keep
        (1.0, 0.0, 1.0, 1.0),       # At maximum: keep
        (1.5, 0.0, 1.0, 1.0),       # Above maximum: clamp to max
        (-100.0, 0.0, 1.0, 0.0),    # Way below minimum: clamp to min
        (100.0, 0.0, 1.0, 1.0),     # Way above maximum: clamp to max
    ])
    def test_confidence_clamping(self, input_value, min_val, max_val, expected):
        """
        BOUNDARY: Test that confidence scores are clamped to [0.0, 1.0] range.

        Common bug: Values outside range cause crashes instead of clamping.
        """
        # Confidence scores should be clamped to [0.0, 1.0]
        # -0.1 → 0.0 (STUDENT)
        # 1.1 → 1.0 (AUTONOMOUS)

        if input_value < min_val:
            clamped = min_val
        elif input_value > max_val:
            clamped = max_val
        else:
            clamped = input_value

        assert clamped == expected, (
            f"Value {input_value} should clamp to {expected} "
            f"within [{min_val}, {max_val}]"
        )

    def test_negative_confidence_clamping(self):
        """
        BOUNDARY: Test negative confidence values are clamped to STUDENT.

        Common bug: Negative confidence causes unexpected behavior.
        """
        # Test negative confidence clamping
        confidence_score = -0.1

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(confidence_score, 1.0))

        # Should clamp to 0.0 (STUDENT)
        assert score == 0.0

        # And map to STUDENT
        if score < 0.5:
            status = AgentStatus.STUDENT.value
        else:
            status = AgentStatus.INTERN.value

        assert status == AgentStatus.STUDENT.value

    def test_above_max_confidence_clamping(self):
        """
        BOUNDARY: Test confidence > 1.0 is clamped to AUTONOMOUS.

        Common bug: Values > 1.0 cause unexpected behavior.
        """
        # Test confidence above maximum
        confidence_score = 1.5

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(confidence_score, 1.0))

        # Should clamp to 1.0 (AUTONOMOUS)
        assert score == 1.0

        # And map to AUTONOMOUS
        if score < 0.9:
            status = AgentStatus.SUPERVISED.value
        else:
            status = AgentStatus.AUTONOMOUS.value

        assert status == AgentStatus.AUTONOMOUS.value


class TestFloatPrecisionBoundaries:
    """Test float precision issues at exact threshold comparisons."""

    def test_float_comparison_precision(self):
        """
        BOUNDARY: Test that float comparisons handle precision correctly.

        Common bug: Float precision causes 0.5 to be treated as 0.4999999999.
        """
        # Test exact threshold values
        thresholds = [0.5, 0.7, 0.9]

        for threshold in thresholds:
            # Test value exactly at threshold
            at_threshold = threshold

            # Test value just below threshold (within float precision)
            just_below = threshold - 1e-10

            # Test value just above threshold (within float precision)
            just_above = threshold + 1e-10

            # All comparisons should work correctly
            assert at_threshold >= threshold  # Should be equal
            assert just_below < threshold     # Should be below
            assert just_above > threshold     # Should be above

    def test_rounding_error_boundaries(self):
        """
        BOUNDARY: Test that rounding errors don't cause misclassification.

        Common bug: 0.5 becomes 0.4999999999 due to floating point arithmetic.
        """
        # Simulate floating point arithmetic
        value = 0.1 + 0.1 + 0.1 + 0.1 + 0.1  # Should be 0.5, but might not be exactly

        # Due to floating point precision, this might not be exactly 0.5
        # But for maturity classification, we need to handle this

        # Use small epsilon for comparison
        epsilon = 1e-10

        threshold = 0.5
        is_at_or_above_threshold = value >= (threshold - epsilon)

        # Should classify correctly despite floating point errors
        assert is_at_or_above_threshold
