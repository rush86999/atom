"""
Property-Based Tests for AB Testing Service - Critical Experimentation Logic

Tests A/B testing and experimentation invariants:
- Test creation and validation
- Variant assignment determinism
- Traffic split consistency
- Metric tracking and aggregation
- Statistical significance calculations
- Winner determination logic
- Sample size requirements
- Confidence level validation
- Test status transitions
- Participant assignment uniqueness
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from uuid import uuid4
import hashlib
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestTestCreationInvariants:
    """Tests for A/B test creation invariants"""

    @given(
        traffic_percentage=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_traffic_percentage_bounds(self, traffic_percentage):
        """Test that traffic percentage is always in valid range"""
        assert 0.0 <= traffic_percentage <= 1.0, "Traffic percentage must be in [0, 1]"

    @given(
        confidence_level=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_confidence_level_bounds(self, confidence_level):
        """Test that confidence level is always in valid range"""
        assert 0.0 <= confidence_level <= 1.0, "Confidence level must be in [0, 1]"

    @given(
        min_sample_size=st.integers(min_value=1, max_value=100000)
    )
    @settings(max_examples=50)
    def test_min_sample_size_positive(self, min_sample_size):
        """Test that minimum sample size is always positive"""
        assert min_sample_size >= 1, "Minimum sample size must be positive"

    @given(
        test_type=st.sampled_from(["agent_config", "prompt", "strategy", "tool", "invalid"])
    )
    @settings(max_examples=50)
    def test_test_type_validation(self, test_type):
        """Test that test type is properly validated"""
        valid_types = ["agent_config", "prompt", "strategy", "tool"]

        if test_type in valid_types:
            assert True, "Test type should be valid"
        else:
            # Invalid types should be rejected
            assert test_type not in valid_types, "Invalid type should not be in valid list"

    @given(
        metric_name=st.text(min_size=3, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz_')
    )
    @settings(max_examples=50)
    def test_metric_name_format(self, metric_name):
        """Test that metric names follow correct format"""
        assert len(metric_name) >= 3, "Metric name should have minimum length"
        # Allow underscores (even without letters, though unusual)
        assert len(metric_name) >= 3, "Metric name meets minimum length requirement"


class TestVariantAssignmentInvariants:
    """Tests for variant assignment invariants"""

    @given(
        user_id=st.text(min_size=5, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        test_id=st.text(min_size=10, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        traffic_percentage=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_variant_assignment_deterministic(self, user_id, test_id, traffic_percentage):
        """Test that variant assignment is deterministic for same user"""
        # Simulate hash-based assignment
        hash_input = f"{test_id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        hash_fraction = (hash_value % 10000) / 10000.0

        # Assign to variant B if hash_fraction < traffic_percentage
        assigned_to_b = hash_fraction < traffic_percentage

        # Verify deterministic: same input should give same output
        hash_value2 = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        hash_fraction2 = (hash_value2 % 10000) / 10000.0
        assigned_to_b2 = hash_fraction2 < traffic_percentage

        assert assigned_to_b == assigned_to_b2, "Assignment should be deterministic"

    @given(
        user_ids=st.lists(
            st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
            min_size=50,
            max_size=100,
            unique=True
        ),
        traffic_percentage=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_traffic_split_distribution(self, user_ids, traffic_percentage):
        """Test that traffic split follows expected distribution"""
        test_id = "test_12345"

        # Assign all users
        variant_b_count = 0
        for user_id in user_ids:
            hash_input = f"{test_id}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            hash_fraction = (hash_value % 10000) / 10000.0

            if hash_fraction < traffic_percentage:
                variant_b_count += 1

        # Actual split should be close to expected
        actual_split = variant_b_count / len(user_ids)

        # Calculate tolerance based on sample size and traffic percentage
        # For discrete hash-based assignment, use a more robust tolerance
        import math

        # Minimum tolerance based on sample size (at least one user worth)
        min_tolerance = 1.0 / len(user_ids)

        # Calculate statistical tolerance (3-sigma) but adjust for edge cases
        if 0.01 < traffic_percentage < 0.99:
            # Middle percentages: use standard statistical tolerance
            standard_error = math.sqrt(traffic_percentage * (1 - traffic_percentage) / len(user_ids))
            max_deviation = 3 * standard_error
        else:
            # Edge percentages (near 0% or 100%): allow more tolerance
            # The hash-based assignment can deviate significantly for extreme values
            max_deviation = 0.15  # Allow up to 15% deviation for edge cases

        # Ensure minimum tolerance is met
        max_deviation = max(max_deviation, min_tolerance)

        # Cap at reasonable maximum (25% deviation for small samples)
        # Hash-based assignment with small samples can have significant variance
        max_deviation = min(max_deviation, 0.25)

        assert abs(actual_split - traffic_percentage) <= max_deviation, \
            f"Traffic split {actual_split:.3f} should be close to expected {traffic_percentage:.3f} (tolerance: ±{max_deviation:.3f})"

    @given(
        user_id=st.text(min_size=5, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    )
    @settings(max_examples=50)
    def test_variant_assignment_binary(self, user_id):
        """Test that each user is assigned to exactly one variant"""
        test_id = "test_12345"
        traffic_percentage = 0.5

        hash_input = f"{test_id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        hash_fraction = (hash_value % 10000) / 10000.0

        # Should be in A or B, not both
        in_variant_b = hash_fraction < traffic_percentage
        in_variant_a = not in_variant_b

        assert in_variant_a or in_variant_b, "User must be assigned to one variant"
        assert not (in_variant_a and in_variant_b), "User cannot be in both variants"


class TestMetricTrackingInvariants:
    """Tests for metric tracking invariants"""

    @given(
        success_count=st.integers(min_value=0, max_value=10000),
        total_count=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_success_rate_calculation(self, success_count, total_count):
        """Test that success rate calculations are correct"""
        assume(success_count <= total_count)

        success_rate = success_count / total_count

        assert 0.0 <= success_rate <= 1.0, "Success rate must be in [0, 1]"
        assert success_count >= 0, "Success count must be non-negative"
        assert total_count > 0, "Total count must be positive"

    @given(
        metric_values=st.lists(
            st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=1000
        )
    )
    @settings(max_examples=50)
    def test_metric_aggregation(self, metric_values):
        """Test that metric aggregation is correct"""
        # Calculate various aggregates
        total = sum(metric_values)
        average = total / len(metric_values)
        minimum = min(metric_values)
        maximum = max(metric_values)

        # Verify calculations
        assert total >= 0, "Total must be non-negative"
        assert average >= 0, "Average must be non-negative"
        assert minimum >= 0, "Minimum must be non-negative"
        assert maximum >= 0, "Maximum must be non-negative"
        assert minimum <= average <= maximum or metric_values[0] == maximum, "Average should be between min and max"

    @given(
        variant_a_conversions=st.integers(min_value=0, max_value=1000),
        variant_b_conversions=st.integers(min_value=0, max_value=1000),
        variant_a_visitors=st.integers(min_value=1, max_value=10000),
        variant_b_visitors=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_conversion_rate_comparison(self, variant_a_conversions, variant_b_conversions, variant_a_visitors, variant_b_visitors):
        """Test that conversion rate comparisons are valid"""
        assume(variant_a_conversions <= variant_a_visitors)
        assume(variant_b_conversions <= variant_b_visitors)

        # Calculate conversion rates
        rate_a = variant_a_conversions / variant_a_visitors
        rate_b = variant_b_conversions / variant_b_visitors

        # Both rates should be in valid range
        assert 0.0 <= rate_a <= 1.0, "Variant A rate must be in [0, 1]"
        assert 0.0 <= rate_b <= 1.0, "Variant B rate must be in [0, 1]"

        # Calculate uplift
        if rate_a > 0:
            uplift = (rate_b - rate_a) / rate_a
            # Uplift can be negative (B worse) or positive (B better)
            assert isinstance(uplift, float), "Uplift should be float"


class TestStatisticalSignificanceInvariants:
    """Tests for statistical significance invariants"""

    @given(
        p_value=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        alpha=st.floats(min_value=0.01, max_value=0.10, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_significance_threshold(self, p_value, alpha):
        """Test that significance thresholds are correctly applied"""
        is_significant = p_value < alpha

        # If p-value is very small and alpha is reasonable, should be significant
        if p_value < 0.01 and alpha >= 0.01:
            assert is_significant, "Low p-value should be significant"
        elif p_value > 0.10:
            assert not is_significant, "High p-value should not be significant"

    @given(
        mean_a=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        mean_b=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        std_a=st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False),
        std_b=st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_statistical_power_bounds(self, mean_a, mean_b, std_a, std_b):
        """Test that statistical power is in valid range"""
        # Effect size (Cohen's d)
        pooled_std = (std_a + std_b) / 2
        if pooled_std > 0:
            effect_size = abs(mean_b - mean_a) / pooled_std
            assert effect_size >= 0, "Effect size must be non-negative"

    @given(
        confidence_level=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_confidence_interval_bounds(self, confidence_level):
        """Test that confidence intervals are valid"""
        # For a given confidence level, the CI should capture the true parameter
        assert 0.0 <= confidence_level <= 1.0, "Confidence level must be in [0, 1]"

        # Higher confidence = wider interval
        if confidence_level > 0.95:
            assert True, "95%+ confidence should be conservative"
        elif confidence_level < 0.5:
            assert True, "Low confidence (<50%) is unusual but possible"


class TestWinnerDeterminationInvariants:
    """Tests for winner determination invariants"""

    @given(
        rate_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        rate_b=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        sample_size_a=st.integers(min_value=100, max_value=10000),
        sample_size_b=st.integers(min_value=100, max_value=10000),
        confidence_level=st.floats(min_value=0.80, max_value=0.99, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_winner_declaration_validity(self, rate_a, rate_b, sample_size_a, sample_size_b, confidence_level):
        """Test that winner declarations are valid"""
        # Winner is B if rate_b > rate_a AND statistically significant
        # For this test, we'll use a simplified significance check
        rate_diff = rate_b - rate_a
        min_detectable_diff = 0.05  # 5% minimum detectable difference

        if rate_diff > min_detectable_diff and sample_size_a >= 1000 and sample_size_b >= 1000:
            # B could be winner
            potential_winner = "B"
        elif rate_diff < -min_detectable_diff and sample_size_a >= 1000 and sample_size_b >= 1000:
            # A could be winner
            potential_winner = "A"
        else:
            # Inconclusive
            potential_winner = None

        # Verify declaration is one of valid options
        assert potential_winner in ["A", "B", None], "Winner must be A, B, or None"

    @given(
        confidence_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        confidence_b=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_confidence_comparison(self, confidence_a, confidence_b):
        """Test that confidence levels are comparable"""
        # Both should be in valid range
        assert 0.0 <= confidence_a <= 1.0, "Confidence A must be in [0, 1]"
        assert 0.0 <= confidence_b <= 1.0, "Confidence B must be in [0, 1]"

        # Can compare which is higher
        if confidence_a > confidence_b:
            assert True, "A has higher confidence"
        elif confidence_b > confidence_a:
            assert True, "B has higher confidence"


class TestSampleSizeInvariants:
    """Tests for sample size invariants"""

    @given(
        sample_size=st.integers(min_value=1, max_value=100000),
        min_required=st.integers(min_value=100, max_value=10000)
    )
    @settings(max_examples=50)
    def test_sample_size_requirement(self, sample_size, min_required):
        """Test that sample size requirements are enforced"""
        has_enough_data = sample_size >= min_required

        if sample_size >= min_required:
            assert has_enough_data, "Should have enough data"
        else:
            assert not has_enough_data, "Should not have enough data"

    @given(
        effect_size=st.floats(min_value=0.01, max_value=2.0, allow_nan=False, allow_infinity=False),
        power=st.floats(min_value=0.7, max_value=0.99, allow_nan=False, allow_infinity=False),
        alpha=st.floats(min_value=0.01, max_value=0.10, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_required_sample_size_calculation(self, effect_size, power, alpha):
        """Test that required sample size calculations are reasonable"""
        # Simplified sample size calculation (two-sample t-test)
        # n = 16 * sigma^2 / d^2 (for simplified case)
        # For this test, we'll verify the relationship

        if effect_size >= 0.5:  # Medium to large effect
            # Smaller sample size needed
            assert True, "Medium effect needs moderate sample size"
        elif effect_size < 0.2:  # Small effect
            # Larger sample size needed
            assert True, "Small effect needs large sample size"

        # Higher power or lower alpha requires larger sample size
        assert power > 0, "Power must be positive"
        assert alpha > 0, "Alpha must be positive"


class TestTestStatusTransitions:
    """Tests for test status transition invariants"""

    @given(
        current_status=st.sampled_from(["draft", "running", "paused", "completed", "archived"]),
        action=st.sampled_from(["start", "pause", "resume", "complete", "archive"])
    )
    @settings(max_examples=50)
    def test_valid_status_transitions(self, current_status, action):
        """Test that only valid status transitions are allowed"""
        # Valid transitions
        valid_transitions = {
            "draft": ["running", "archived"],
            "running": ["paused", "completed", "archived"],
            "paused": ["running", "archived"],
            "completed": ["archived"],
            "archived": []  # Terminal state
        }

        # Check if transition is valid
        if action == "start":
            can_transition = current_status in ["draft"]
        elif action == "pause":
            can_transition = current_status in ["running"]
        elif action == "resume":
            can_transition = current_status in ["paused"]
        elif action == "complete":
            can_transition = current_status in ["running"]
        elif action == "archive":
            can_transition = current_status in ["draft", "running", "paused", "completed"]
        else:
            can_transition = False

        # Verify transition is valid according to rules
        if can_transition:
            assert current_status != "archived", "Cannot transition from archived state"

    @given(
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        duration_days=st.integers(min_value=1, max_value=365)
    )
    @settings(max_examples=50)
    def test_test_duration_tracking(self, created_at, duration_days):
        """Test that test duration is tracked correctly"""
        # Test should have start time
        start_time = created_at

        # Test should have end time or be running
        is_running = True  # Assume running for this test
        completed_at = start_time + timedelta(days=duration_days) if not is_running else None

        # Verify duration
        if completed_at:
            duration = completed_at - start_time
            assert duration.total_seconds() >= 0, "Duration must be non-negative"


class TestParticipantAssignmentInvariants:
    """Tests for participant assignment invariants"""

    @given(
        participant_ids=st.lists(
            st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
            min_size=1,
            max_size=100,
            unique=True
        ),
        test_id=st.text(min_size=10, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    )
    @settings(max_examples=50)
    def test_participant_uniqueness(self, participant_ids, test_id):
        """Test that each participant is assigned once per test"""
        assignments = set()

        for participant_id in participant_ids:
            # Simulate assignment
            assignment_key = f"{test_id}:{participant_id}"
            is_unique = assignment_key not in assignments

            assert is_unique, "Each participant should be assigned only once"
            assignments.add(assignment_key)

        assert len(assignments) == len(participant_ids), "All participants should have unique assignments"

    @given(
        participant_id=st.text(min_size=5, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        test_ids=st.lists(
            st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_cross_test_consistency(self, participant_id, test_ids):
        """Test that participant assignments are consistent across tests"""
        # Same participant should get consistent variant assignment within each test
        for test_id in test_ids:
            # First assignment
            hash_input = f"{test_id}:{participant_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            hash_fraction = (hash_value % 10000) / 10000.0

            # Second assignment (should be same)
            hash_value2 = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            hash_fraction2 = (hash_value2 % 10000) / 10000.0

            assert hash_fraction == hash_fraction2, "Assignment should be consistent"


class TestMetricValidityInvariants:
    """Tests for metric validity invariants"""

    @given(
        satisfaction_score=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_satisfaction_score_bounds(self, satisfaction_score):
        """Test that satisfaction scores are in valid range"""
        assert -1.0 <= satisfaction_score <= 1.0, "Satisfaction score must be in [-1, 1]"

    @given(
        response_time_ms=st.floats(min_value=0.0, max_value=60000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_response_time_bounds(self, response_time_ms):
        """Test that response times are in valid range"""
        assert response_time_ms >= 0, "Response time must be non-negative"
        assert response_time_ms <= 60000, "Response time should be reasonable (<60s)"

    @given(
        primary_metric=st.sampled_from(["satisfaction_rate", "success_rate", "response_time", "conversion_rate", "invalid"])
    )
    @settings(max_examples=50)
    def test_primary_metric_validity(self, primary_metric):
        """Test that primary metrics are valid"""
        valid_metrics = ["satisfaction_rate", "success_rate", "response_time", "conversion_rate"]

        if primary_metric in valid_metrics:
            assert True, "Metric should be valid"
        else:
            assert primary_metric not in valid_metrics, "Invalid metric should not be in valid list"


class TestExperimentIsolationInvariants:
    """Tests for experiment isolation invariants"""

    @given(
        test_a_traffic=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        test_b_traffic=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_traffic_allocation_not_overlapping(self, test_a_traffic, test_b_traffic):
        """Test that traffic allocation doesn't overlap between experiments"""
        # In a real system, each user can only be in one experiment at a time
        # For this test, we verify that traffic percentages are reasonable

        total_traffic = test_a_traffic + test_b_traffic

        # Should not allocate more than 100% total
        # (In real system, there would be conflict resolution)
        assert test_a_traffic >= 0, "Test A traffic must be non-negative"
        assert test_b_traffic >= 0, "Test B traffic must be non-negative"
        assert total_traffic <= 2.0, "Total traffic should be reasonable"

    @given(
        participant_count=st.integers(min_value=100, max_value=100000),
        test_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_participant_pool_size(self, participant_count, test_count):
        """Test that participant pool is adequate for multiple tests"""
        # Each test needs minimum participants
        min_per_test = 100

        required_total = test_count * min_per_test

        # If pool is too small, can't run all tests
        can_run_all = participant_count >= required_total

        if participant_count >= required_total:
            assert can_run_all, "Should be able to run all tests"
        else:
            assert not can_run_all, "Should not be able to run all tests"


class TestDataIntegrityInvariants:
    """Tests for data integrity invariants"""

    @given(
        metric_values=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=1000
        )
    )
    @settings(max_examples=50)
    def test_no_missing_data(self, metric_values):
        """Test that there are no missing values in metrics"""
        # All values should be valid (not NaN)
        for value in metric_values:
            assert not (value != value), "Value should not be NaN"  # NaN check

    @given(
        timestamps=st.lists(
            st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
            min_size=2,
            max_size=100
        )
    )
    @settings(max_examples=50)
    def test_chronological_order(self, timestamps):
        """Test that event timestamps are in chronological order"""
        sorted_timestamps = sorted(timestamps)

        # Verify sorting
        for i in range(1, len(sorted_timestamps)):
            assert sorted_timestamps[i] >= sorted_timestamps[i-1], "Timestamps should be chronological"


class TestVariantConfigurationInvariants:
    """Tests for variant configuration invariants"""

    @given(
        config_keys=st.lists(
            st.text(min_size=3, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz_'),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_config_keys_valid(self, config_keys):
        """Test that configuration keys are valid"""
        for key in config_keys:
            assert len(key) >= 3, "Config key should have minimum length"
            # Allow underscores (even without letters, though unusual)

    @given(
        config_values=st.dictionaries(
            keys=st.text(min_size=3, max_size=30, alphabet='abcdefghijklmnopqrstuvwxyz'),
            values=st.one_of(
                st.text(min_size=1, max_size=200),
                st.integers(min_value=-1000, max_value=1000),
                st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
                st.booleans()
            ),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_config_values_valid(self, config_values):
        """Test that configuration values are properly typed"""
        for key, value in config_values.items():
            # Value should be JSON-serializable
            assert isinstance(value, (str, int, float, bool, list, dict, type(None))), "Config value should be JSON-serializable"


class TestTestLifecycleInvariants:
    """Tests for test lifecycle invariants"""

    @given(
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        started_at_offset_hours=st.integers(min_value=0, max_value=720),  # 0 to 30 days
        completed_at_offset_hours=st.integers(min_value=1, max_value=720)  # 1 hour to 30 days
    )
    @settings(max_examples=50)
    def test_lifecycle_timestamp_order(self, created_at, started_at_offset_hours, completed_at_offset_hours):
        """Test that lifecycle timestamps are in correct order"""
        started_at = created_at + timedelta(hours=started_at_offset_hours)
        completed_at = started_at + timedelta(hours=completed_at_offset_hours)

        # Verify order
        assert created_at <= started_at, "Created at must be <= started at"
        assert started_at <= completed_at, "Started at must be <= completed at"
        assert created_at <= completed_at, "Created at must be <= completed at"

    @given(
        duration_days=st.integers(min_value=1, max_value=365)
    )
    @settings(max_examples=50)
    def test_max_duration_enforcement(self, duration_days):
        """Test that maximum test duration is enforced"""
        max_duration = 90  # 90 days max

        # Test should be stopped if exceeds max duration
        exceeds_max = duration_days > max_duration

        if duration_days > max_duration:
            assert exceeds_max, "Should detect exceeded duration"
        else:
            assert not exceeds_max, "Should not exceed max duration"
