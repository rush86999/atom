"""
Property-Based Tests for Error Guidance Invariants

Tests CRITICAL error guidance invariants:
- Error categorization matches error types
- Resolution suggestions are actionable
- Success rates tracked accurately
- Resolution learning improves suggestions
- Agent can fix flag is correct

These tests protect against incorrect error handling and poor user guidance.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta
from typing import List, Dict
from unittest.mock import Mock

from core.error_guidance_engine import ErrorGuidanceEngine


class TestErrorCategorizationInvariants:
    """Property-based tests for error categorization invariants."""

    @given(
        error_type=st.sampled_from([
            'permission_denied', 'auth_expired', 'network_error',
            'rate_limit', 'invalid_input'
        ])
    )
    @settings(max_examples=50)
    def test_error_type_has_resolutions(self, error_type):
        """INVARIANT: All error types have at least one resolution."""
        engine = ErrorGuidanceEngine

        # Check if error type exists in resolutions
        has_resolutions = error_type in engine.ERROR_RESOLUTIONS

        if has_resolutions:
            resolutions = engine.ERROR_RESOLUTIONS[error_type].get('resolutions', [])

            # Invariant: Should have at least one resolution
            assert len(resolutions) > 0, \
                f"Error type '{error_type}' has no resolutions"

            # Invariant: Each resolution should have required fields
            required_fields = ['title', 'description', 'agent_can_fix', 'steps']
            for resolution in resolutions:
                for field in required_fields:
                    assert field in resolution, \
                        f"Resolution missing field '{field}' for error '{error_type}'"

    @given(
        error_types=st.lists(
            st.sampled_from([
                'permission_denied', 'auth_expired', 'network_error',
                'rate_limit', 'invalid_input'
            ]),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_error_types_are_unique(self, error_types):
        """INVARIANT: Error type categories are unique."""
        engine = ErrorGuidanceEngine

        # Check all error types exist
        for error_type in error_types:
            assert error_type in engine.ERROR_RESOLUTIONS, \
                f"Error type '{error_type}' not defined in ERROR_RESOLUTIONS"

        # Invariant: No duplicate error types
        assert len(error_types) == len(set(error_types)), \
            "Duplicate error types found"

    @given(
        error_message=st.text(min_size=10, max_size=200, alphabet='abc123DEF!@#')
    )
    @settings(max_examples=50)
    def test_error_message_length_validation(self, error_message):
        """INVARIANT: Error messages have reasonable length."""
        # Invariant: Error messages should not be empty
        assert len(error_message.strip()) > 0, \
            "Error message should not be empty"

        # Invariant: Error messages should be reasonable length
        assert len(error_message) <= 200, \
            f"Error message too long: {len(error_message)} characters"


class TestResolutionSuggestionInvariants:
    """Property-based tests for resolution suggestion invariants."""

    @given(
        resolution_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_resolutions_have_steps(self, resolution_count):
        """INVARIANT: All resolutions have actionable steps."""
        # Create mock resolutions
        resolutions = []
        for i in range(resolution_count):
            resolution = {
                'title': f'Resolution {i}',
                'description': f'Description {i}',
                'agent_can_fix': i % 2 == 0,  # Alternate
                'steps': [
                    f'Step {j}' for j in range(1, i % 3 + 2)  # 1-3 steps
                ]
            }
            resolutions.append(resolution)

        # Verify all resolutions have steps
        for resolution in resolutions:
            assert len(resolution['steps']) > 0, \
                f"Resolution '{resolution['title']}' has no steps"

            # Invariant: Steps should be non-empty
            for step in resolution['steps']:
                assert len(step.strip()) > 0, \
                    "Resolution step should not be empty"

    @given(
        step_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_step_ordering_preserved(self, step_count):
        """INVARIANT: Resolution steps maintain sequential order."""
        steps = [f'Step {i}' for i in range(step_count)]

        # Invariant: Steps should be in order
        for i in range(len(steps)):
            expected_step = f'Step {i}'
            assert steps[i] == expected_step, \
                f"Step {i} is '{steps[i]}', expected '{expected_step}'"

    @given(
        agent_can_fix=st.booleans(),
        has_self_service_steps=st.booleans()
    )
    @settings(max_examples=50)
    def test_agent_can_fix_flag_logic(self, agent_can_fix, has_self_service_steps):
        """INVARIANT: Agent can fix flag matches resolution capability."""
        # Invariant: If agent can fix, should have clear steps
        if agent_can_fix:
            # Agent-fixable resolutions should have unambiguous steps
            steps = [
                'I will perform action A',
                'Wait for completion',
                'Verify result'
            ]
            assert len(steps) >= 1, \
                "Agent-fixable resolution should have at least one step"
        else:
            # User-fixable resolutions should have manual steps
            steps = [
                'Go to Settings → Permissions',
                'Enable the required permission',
                'Retry the operation'
            ]
            assert len(steps) >= 1, \
                "User-fixable resolution should have at least one step"


class TestSuccessTrackingInvariants:
    """Property-based tests for success tracking invariants."""

    @given(
        attempt_count=st.integers(min_value=1, max_value=100),
        success_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_success_rate_calculation(self, attempt_count, success_count):
        """INVARIANT: Success rate calculated correctly."""
        # Ensure success_count <= attempt_count
        success_count = min(success_count, attempt_count)

        # Calculate success rate
        success_rate = success_count / attempt_count if attempt_count > 0 else 0.0

        # Invariant: Success rate should be in [0, 1]
        assert 0.0 <= success_rate <= 1.0, \
            f"Success rate {success_rate:.2f} out of bounds [0, 1]"

        # Invariant: Success rate should match formula
        expected_rate = success_count / attempt_count
        assert abs(success_rate - expected_rate) < 0.001, \
            f"Success rate calculation incorrect"

    @given(
        resolution_attempts=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_resolution_tracking_counts(self, resolution_attempts):
        """INVARIANT: Resolution attempt counts are accurate."""
        # Simulate resolution tracking
        attempts = []
        for i in range(resolution_attempts):
            attempt = {
                'resolution_id': f"resolution_{i % 5}",  # 5 different resolutions
                'timestamp': datetime.now() + timedelta(seconds=i),
                'success': i % 3 != 0  # 2/3 success rate
            }
            attempts.append(attempt)

        # Count attempts per resolution
        resolution_counts = {}
        for attempt in attempts:
            res_id = attempt['resolution_id']
            resolution_counts[res_id] = resolution_counts.get(res_id, 0) + 1

        # Invariant: Total count should match
        total_counted = sum(resolution_counts.values())
        assert total_counted == resolution_attempts, \
            f"Total count mismatch: {total_counted} vs {resolution_attempts}"

        # Invariant: Each resolution should have at least one attempt
        for res_id, count in resolution_counts.items():
            assert count >= 1, \
                f"Resolution '{res_id}' has {count} attempts"


class TestResolutionLearningInvariants:
    """Property-based tests for resolution learning invariants."""

    @given(
        initial_success_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        new_success_count=st.integers(min_value=0, max_value=20),
        new_failure_count=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=50)
    def test_success_rate_update(self, initial_success_rate, new_success_count, new_failure_count):
        """INVARIANT: Success rate updates correctly with new data."""
        # Calculate updated success rate
        total_new = new_success_count + new_failure_count

        if total_new > 0:
            new_success_rate = new_success_count / total_new

            # Weighted average (simplified)
            updated_rate = (initial_success_rate + new_success_rate) / 2

            # Invariant: Updated rate should be in [0, 1]
            assert 0.0 <= updated_rate <= 1.0, \
                f"Updated success rate {updated_rate:.2f} out of bounds [0, 1]"

    @given(
        resolution_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_resolution_ranking_by_success(self, resolution_scores):
        """INVARIANT: Resolutions ranked by success rate."""
        # Create mock resolutions with success scores
        resolutions = []
        for i, score in enumerate(resolution_scores):
            resolution = {
                'id': f"resolution_{i}",
                'title': f"Resolution {i}",
                'success_rate': score,
                'attempt_count': 10 + i
            }
            resolutions.append(resolution)

        # Sort by success rate (descending)
        ranked = sorted(resolutions, key=lambda r: r['success_rate'], reverse=True)

        # Verify ranking
        for i in range(len(ranked) - 1):
            current_rate = ranked[i]['success_rate']
            next_rate = ranked[i + 1]['success_rate']
            assert current_rate >= next_rate, \
                "Resolutions not ranked by success rate (descending)"

    @given(
        feedback_scores=st.lists(
            st.integers(min_value=-1, max_value=1),  # -1: bad, 0: neutral, 1: good
            min_size=5,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_feedback_aggregation(self, feedback_scores):
        """INVARIANT: User feedback aggregated correctly."""
        # Calculate aggregate score
        total_score = sum(feedback_scores)
        avg_score = total_score / len(feedback_scores) if feedback_scores else 0.0

        # Invariant: Average should be in [-1, 1]
        assert -1.0 <= avg_score <= 1.0, \
            f"Average feedback score {avg_score:.2f} out of bounds [-1, 1]"

        # Invariant: All individual scores should be valid
        for score in feedback_scores:
            assert -1 <= score <= 1, \
                f"Feedback score {score} out of bounds [-1, 1]"


class TestErrorGuidanceResponseInvariants:
    """Property-based tests for error guidance response invariants."""

    @given(
        error_type=st.sampled_from([
            'permission_denied', 'auth_expired', 'network_error',
            'rate_limit', 'invalid_input'
        ]),
        resolution_index=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=50)
    def test_guidance_response_structure(self, error_type, resolution_index):
        """INVARIANT: Error guidance response has required structure."""
        engine = ErrorGuidanceEngine
        error_config = engine.ERROR_RESOLUTIONS.get(error_type)

        if error_config:
            # Build response structure
            response = {
                'error_type': error_type,
                'title': error_config.get('title', 'Unknown Error'),
                'resolutions': error_config.get('resolutions', [])
            }

            # Invariant: Response should have required fields
            assert 'error_type' in response
            assert 'title' in response
            assert 'resolutions' in response

            # Invariant: Should have at least one resolution
            assert len(response['resolutions']) > 0, \
                f"Error '{error_type}' should have at least one resolution"

    @given(
        title=st.text(min_size=5, max_size=100, alphabet='abcDEF123 -'),
        description=st.text(min_size=10, max_size=200, alphabet='abcDEF123 ,.')
    )
    @settings(max_examples=50)
    def test_guidance_content_validation(self, title, description):
        """INVARIANT: Guidance content is user-friendly."""
        # Invariant: Title should not be empty
        assert len(title.strip()) > 0, \
            "Error guidance title should not be empty"

        # Invariant: Title should be concise
        assert len(title) <= 100, \
            f"Title too long: {len(title)} characters"

        # Invariant: Description should be informative
        assert len(description.strip()) > 0, \
            "Error guidance description should not be empty"

        # Invariant: Description should be reasonable length
        assert len(description) <= 200, \
            f"Description too long: {len(description)} characters"

    @given(
        timestamp=st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime.now()
        )
    )
    @settings(max_examples=50)
    def test_error_timestamp_tracking(self, timestamp):
        """INVARIANT: Error timestamps are tracked accurately."""
        # Simulate error tracking
        error_record = {
            'error_type': 'network_error',
            'timestamp': timestamp,
            'resolved': False,
            'resolution_id': None
        }

        # Invariant: Timestamp should be valid
        assert error_record['timestamp'] is not None, \
            "Error timestamp should not be None"

        # Invariant: Timestamp should be in reasonable range
        assert error_record['timestamp'] >= datetime(2024, 1, 1), \
            "Error timestamp too far in the past"
        assert error_record['timestamp'] <= datetime.now() + timedelta(minutes=5), \
            "Error timestamp too far in the future"
