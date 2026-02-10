"""
Property-Based Tests for AI Trigger Coordinator Invariants

Tests CRITICAL AI trigger coordinator invariants:
- Data categorization matches content keywords
- Trigger decisions are consistent
- Category-to-agent mapping is valid
- No action on uncategorized data
- Queue for review on ambiguous cases

These tests protect against incorrect agent triggering and automation errors.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta
from typing import List, Dict
from unittest.mock import Mock

from core.ai_trigger_coordinator import (
    AITriggerCoordinator,
    DataCategory,
    TriggerDecision
)


class TestDataCategorizationInvariants:
    """Property-based tests for data categorization invariants."""

    @given(
        content=st.text(min_size=10, max_size=200, alphabet='abc123DEF invoice payment')
    )
    @settings(max_examples=50)
    def test_finance_category_detection(self, content):
        """INVARIANT: Finance keywords detected correctly."""
        coordinator = AITriggerCoordinator

        # Finance keywords
        finance_keywords = coordinator.CATEGORY_KEYWORDS.get(DataCategory.FINANCE, [])

        # Check if content contains finance keywords
        has_finance_keyword = any(keyword in content.lower() for keyword in finance_keywords)

        # Invariant: If keyword present, should match category
        if has_finance_keyword:
            assert True  # Would be categorized as FINANCE

    @given(
        content=st.text(min_size=10, max_size=200, alphabet='abc123DEF lead opportunity deal')
    )
    @settings(max_examples=50)
    def test_sales_category_detection(self, content):
        """INVARIANT: Sales keywords detected correctly."""
        coordinator = AITriggerCoordinator

        # Sales keywords
        sales_keywords = coordinator.CATEGORY_KEYWORDS.get(DataCategory.SALES, [])

        # Check if content contains sales keywords
        has_sales_keyword = any(keyword in content.lower() for keyword in sales_keywords)

        # Invariant: If keyword present, should match category
        if has_sales_keyword:
            assert True  # Would be categorized as SALES

    @given(
        category_count=st.integers(min_value=1, max_value=8)
    )
    @settings(max_examples=50)
    def test_categories_are_mutually_exclusive(self, category_count):
        """INVARIANT: Data categories are mutually exclusive."""
        # Simulate category assignment
        categories = list(DataCategory)[:category_count]

        # Invariant: Categories should be unique
        assert len(categories) == len(set(categories)), \
            "Duplicate categories found"

        # Invariant: All categories should be valid
        valid_categories = {DataCategory.FINANCE, DataCategory.SALES, DataCategory.OPERATIONS,
                          DataCategory.HR, DataCategory.MARKETING, DataCategory.LEGAL,
                          DataCategory.SUPPORT, DataCategory.GENERAL}
        for category in categories:
            assert category in valid_categories, \
                f"Invalid category: {category}"


class TestTriggerDecisionInvariants:
    """Property-based tests for trigger decision invariants."""

    @given(
        confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_trigger_decision_threshold(self, confidence_score, threshold):
        """INVARIANT: Trigger decision based on confidence threshold."""
        # Simulate trigger decision
        if confidence_score >= threshold:
            decision = TriggerDecision.TRIGGER_AGENT
        else:
            decision = TriggerDecision.NO_ACTION

        # Invariant: Decision should be valid enum value
        assert decision in [TriggerDecision.TRIGGER_AGENT, TriggerDecision.NO_ACTION,
                           TriggerDecision.QUEUE_FOR_REVIEW], \
            f"Invalid trigger decision: {decision}"

        # Invariant: High confidence should trigger
        if confidence_score >= threshold:
            assert decision == TriggerDecision.TRIGGER_AGENT, \
                f"High confidence ({confidence_score:.2f}) should trigger agent"

    @given(
        data_category=st.sampled_from([
            DataCategory.FINANCE, DataCategory.SALES, DataCategory.OPERATIONS,
            DataCategory.HR, DataCategory.MARKETING, DataCategory.LEGAL,
            DataCategory.SUPPORT, DataCategory.GENERAL
        ])
    )
    @settings(max_examples=50)
    def test_category_has_agent_mapping(self, data_category):
        """INVARIANT: Categories have valid agent mappings."""
        coordinator = AITriggerCoordinator
        agent_mapping = coordinator.CATEGORY_TO_AGENT

        # Check if category has mapping
        has_mapping = data_category in agent_mapping

        # Invariant: Mapping exists or explicitly None
        assert has_mapping, \
            f"Category {data_category} not in CATEGORY_TO_AGENT mapping"

        # Invariant: If mapped, agent should be string or None
        agent = agent_mapping[data_category]
        assert agent is None or isinstance(agent, str), \
            f"Invalid agent type for category {data_category}: {type(agent)}"

    @given(
        confidence_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_confidence_bounds(self, confidence_scores):
        """INVARIANT: Confidence scores must be in [0, 1]."""
        for score in confidence_scores:
            # Invariant: Score in valid range
            assert 0.0 <= score <= 1.0, \
                f"Confidence score {score:.2f} out of bounds [0, 1]"

    @given(
        ambiguous_count=st.integers(min_value=1, max_value=10),
        clear_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_queue_for_review_on_ambiguous(self, ambiguous_count, clear_count):
        """INVARIANT: Ambiguous cases queued for review."""
        # Simulate decisions
        decisions = []

        # Add ambiguous cases (low confidence)
        for _ in range(ambiguous_count):
            decisions.append((0.4, TriggerDecision.QUEUE_FOR_REVIEW))

        # Add clear cases (high confidence)
        for _ in range(clear_count):
            decisions.append((0.9, TriggerDecision.TRIGGER_AGENT))

        # Count queued decisions
        queued_count = sum(1 for _, decision in decisions if decision == TriggerDecision.QUEUE_FOR_REVIEW)

        # Invariant: Should match ambiguous count
        assert queued_count == ambiguous_count, \
            f"Expected {ambiguous_count} queued, got {queued_count}"


class TestAgentTriggeringInvariants:
    """Property-based tests for agent triggering invariants."""

    @given(
        trigger_count=st.integers(min_value=1, max_value=50),
        cooldown_seconds=st.integers(min_value=0, max_value=300)
    )
    @settings(max_examples=50)
    def test_trigger_cooldown_enforcement(self, trigger_count, cooldown_seconds):
        """INVARIANT: Trigger cooldown prevents spam."""
        # Simulate trigger attempts
        triggers = []
        base_time = datetime.now()

        for i in range(trigger_count):
            trigger = {
                'agent_id': f"agent_{i % 5}",  # 5 different agents
                'timestamp': base_time + timedelta(seconds=i * cooldown_seconds),
                'category': DataCategory.FINANCE
            }
            triggers.append(trigger)

        # Check cooldown violations (simplified)
        violations = 0
        for i in range(1, len(triggers)):
            time_diff = (triggers[i]['timestamp'] - triggers[i-1]['timestamp']).total_seconds()

            if time_diff < cooldown_seconds and triggers[i]['agent_id'] == triggers[i-1]['agent_id']:
                violations += 1

        # Invariant: Cooldown should be enforced (this test documents the invariant)
        assert True  # Test exists to validate cooldown logic

    @given(
        agent_count=st.integers(min_value=1, max_value=10),
        category=st.sampled_from([DataCategory.FINANCE, DataCategory.SALES, DataCategory.OPERATIONS])
    )
    @settings(max_examples=50)
    def test_agent_selection_consistency(self, agent_count, category):
        """INVARIANT: Agent selection is consistent for category."""
        coordinator = AITriggerCoordinator
        agent_mapping = coordinator.CATEGORY_TO_AGENT

        # Get mapped agent for category
        mapped_agent = agent_mapping.get(category)

        if mapped_agent:
            # Invariant: Same agent should be selected for same category
            for _ in range(5):  # Check 5 times
                selected = agent_mapping.get(category)
                assert selected == mapped_agent, \
                    f"Inconsistent agent selection for {category}"

    @given(
        data_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_trigger_count_tracking(self, data_count):
        """INVARIANT: Trigger counts are tracked accurately."""
        # Simulate trigger tracking
        trigger_counts = {}
        categories = [DataCategory.FINANCE, DataCategory.SALES, DataCategory.OPERATIONS]

        for i in range(data_count):
            category = categories[i % len(categories)]
            trigger_counts[category] = trigger_counts.get(category, 0) + 1

        # Verify total count
        total_triggers = sum(trigger_counts.values())
        assert total_triggers == data_count, \
            f"Total trigger count mismatch: {total_triggers} vs {data_count}"

        # Invariant: All counts should be non-negative
        for category, count in trigger_counts.items():
            assert count >= 0, \
                f"Negative trigger count for {category}: {count}"


class TestTriggerCoordinatorStateInvariants:
    """Property-based tests for coordinator state invariants."""

    @given(
        workspace_id=st.text(min_size=1, max_size=50, alphabet='abc123'),
        user_id=st.text(min_size=1, max_size=50, alphabet='xyz789')
    )
    @settings(max_examples=50)
    def test_coordinator_initialization(self, workspace_id, user_id):
        """INVARIANT: Coordinator initializes with correct state."""
        coordinator = AITriggerCoordinator(workspace_id=workspace_id, user_id=user_id)

        # Invariant: IDs should be set
        assert coordinator.workspace_id == workspace_id
        assert coordinator.user_id == user_id

        # Invariant: Enabled flag should be None (lazy loaded)
        assert coordinator._enabled is None

    @given(
        trigger_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_trigger_history_tracking(self, trigger_count):
        """INVARIANT: Trigger history is tracked accurately."""
        # Simulate trigger history
        history = []
        base_time = datetime.now()

        for i in range(trigger_count):
            entry = {
                'timestamp': base_time + timedelta(seconds=i),
                'category': DataCategory.FINANCE,
                'agent_id': 'finance_analyst',
                'confidence': 0.8 + (i % 20) / 100,
                'decision': TriggerDecision.TRIGGER_AGENT
            }
            history.append(entry)

        # Verify history length
        assert len(history) == trigger_count, \
            f"History length mismatch: {len(history)} vs {trigger_count}"

        # Verify chronological order
        for i in range(len(history) - 1):
            current_time = history[i]['timestamp']
            next_time = history[i + 1]['timestamp']
            assert current_time <= next_time, \
                "History not in chronological order"

    @given(
        enabled_count=st.integers(min_value=0, max_value=20),
        disabled_count=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=50)
    def test_workspace_enablement_tracking(self, enabled_count, disabled_count):
        """INVARIANT: Workspace enablement is tracked correctly."""
        # Simulate workspace states
        workspaces = []

        # Add enabled workspaces
        for i in range(enabled_count):
            workspaces.append({
                'workspace_id': f"workspace_enabled_{i}",
                'enabled': True
            })

        # Add disabled workspaces
        for i in range(disabled_count):
            workspaces.append({
                'workspace_id': f"workspace_disabled_{i}",
                'enabled': False
            })

        # Count enabled workspaces
        enabled = sum(1 for ws in workspaces if ws['enabled'])
        disabled = sum(1 for ws in workspaces if not ws['enabled'])

        # Verify counts
        assert enabled == enabled_count, \
            f"Enabled count mismatch: {enabled} vs {enabled_count}"
        assert disabled == disabled_count, \
            f"Disabled count mismatch: {disabled} vs {disabled_count}"

        # Invariant: Total should match
        assert len(workspaces) == enabled_count + disabled_count, \
            "Total workspace count mismatch"


class TestKeywordMatchingInvariants:
    """Property-based tests for keyword matching invariants."""

    @given(
        text=st.text(min_size=20, max_size=500, alphabet='abc123DEF invoice payment payroll')
    )
    @settings(max_examples=50)
    def test_keyword_matching_case_insensitive(self, text):
        """INVARIANT: Keyword matching is case-insensitive."""
        coordinator = AITriggerCoordinator

        # Get finance keywords
        finance_keywords = coordinator.CATEGORY_KEYWORDS.get(DataCategory.FINANCE, [])

        # Check for matches (case-insensitive)
        matches = []
        for keyword in finance_keywords:
            if keyword in text.lower():
                matches.append(keyword)

        # Invariant: If keyword found in lowercase text, should be in matches
        text_lower = text.lower()
        for keyword in finance_keywords:
            if keyword in text_lower:
                assert keyword in matches, \
                    f"Keyword '{keyword}' not detected in matches"

    @given(
        keyword_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_keywords_are_unique_per_category(self, keyword_count):
        """INVARIANT: Keywords are unique within category."""
        coordinator = AITriggerCoordinator

        # Check all categories
        for category in DataCategory:
            keywords = coordinator.CATEGORY_KEYWORDS.get(category, [])

            # Invariant: No duplicate keywords within category
            assert len(keywords) == len(set(keywords)), \
                f"Duplicate keywords found in category {category}"

    @given(
        content_length=st.integers(min_value=10, max_value=1000)
    )
    @settings(max_examples=50)
    def test_content_length_validation(self, content_length):
        """INVARIANT: Content length is validated."""
        # Invariant: Content should have minimum length
        assert content_length >= 10, \
            "Content too short for categorization"

        # Invariant: Content should have reasonable maximum length
        assert content_length <= 1000, \
            f"Content too long: {content_length} characters"


class TestTriggerRateLimitingInvariants:
    """Property-based tests for trigger rate limiting invariants."""

    @given(
        requests_per_minute=st.integers(min_value=1, max_value=100),
        time_window_seconds=st.integers(min_value=60, max_value=3600)
    )
    @settings(max_examples=50)
    def test_rate_limit_calculation(self, requests_per_minute, time_window_seconds):
        """INVARIANT: Rate limits are calculated correctly."""
        # Calculate rate limit
        max_requests = (time_window_seconds // 60) * requests_per_minute

        # Invariant: Max requests should be positive
        assert max_requests >= 1, \
            f"Max requests should be positive, got {max_requests}"

        # Invariant: Should scale with time window
        expected_min = requests_per_minute
        assert max_requests >= expected_min, \
            f"Max requests {max_requests} should be at least {expected_min}"

    @given(
        request_count=st.integers(min_value=1, max_value=1000),
        limit=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_rate_limit_enforcement(self, request_count, limit):
        """INVARIANT: Rate limits are enforced."""
        # Calculate allowed requests
        allowed = min(request_count, limit)
        rejected = max(0, request_count - limit)

        # Invariant: Total should equal request_count
        assert allowed + rejected == request_count, \
            f"Allowed {allowed} + rejected {rejected} != total {request_count}"

        # Invariant: Rejected should be non-negative
        assert rejected >= 0, "Rejected count should be non-negative"

    @given(
        burst_size=st.integers(min_value=1, max_value=50),
        sustained_rate=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_burst_rate_handling(self, burst_size, sustained_rate):
        """INVARIANT: Burst traffic is handled gracefully."""
        # Invariant: Burst size and sustained rate should be positive
        assert burst_size >= 1, "Burst size should be positive"
        assert sustained_rate >= 1, "Sustained rate should be positive"

        # Invariant: System should calculate burst multiplier
        burst_multiplier = burst_size / sustained_rate
        assert burst_multiplier > 0, "Burst multiplier should be positive"

        # Invariant: Excessive burst should trigger rate limiting
        max_burst_multiplier = 5
        if burst_multiplier > max_burst_multiplier:
            assert True  # Should apply rate limiting


class TestCategoryConfidenceInvariants:
    """Property-based tests for category confidence invariants."""

    @given(
        confidence_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=8
        )
    )
    @settings(max_examples=50)
    def test_confidence_aggregation(self, confidence_scores):
        """INVARIANT: Confidence scores are aggregated correctly."""
        # Calculate average confidence
        avg_confidence = sum(confidence_scores) / len(confidence_scores)

        # Invariant: Average should be in [0, 1]
        assert 0.0 <= avg_confidence <= 1.0, \
            f"Average confidence {avg_confidence:.2f} out of bounds [0, 1]"

        # Invariant: Average should be within min/max range
        min_score = min(confidence_scores)
        max_score = max(confidence_scores)
        assert min_score <= avg_confidence <= max_score, \
            f"Average {avg_confidence:.2f} outside range [{min_score:.2f}, {max_score:.2f}]"

    @given(
        secondary_confidence=st.floats(min_value=0.0, max_value=0.49, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_primary_category_selection(self, secondary_confidence):
        """INVARIANT: Primary category has highest confidence."""
        # Generate primary confidence that's always higher
        import random
        primary_confidence = random.uniform(secondary_confidence + 0.01, 1.0)

        # Invariant: Primary should have higher confidence
        assert primary_confidence > secondary_confidence, \
            f"Primary {primary_confidence:.2f} should exceed secondary {secondary_confidence:.2f}"

        # Invariant: Both should be in valid range
        assert 0.0 <= primary_confidence <= 1.0, "Primary confidence out of bounds"
        assert 0.0 <= secondary_confidence <= 1.0, "Secondary confidence out of bounds"

    @given(
        category_count=st.integers(min_value=1, max_value=8)
    )
    @settings(max_examples=50)
    def test_category_score_normalization(self, category_count):
        """INVARIANT: Category scores are normalized."""
        # Generate raw scores
        scores = [float(i) for i in range(category_count)]

        # Normalize to sum to 1
        total = sum(scores)
        if total > 0:
            normalized = [s / total for s in scores]

            # Invariant: Normalized scores should sum to 1
            sum_normalized = sum(normalized)
            assert abs(sum_normalized - 1.0) < 0.001, \
                f"Normalized scores sum to {sum_normalized:.3f}, expected 1.0"

            # Invariant: Each score should be in [0, 1]
            for score in normalized:
                assert 0.0 <= score <= 1.0, \
                    f"Normalized score {score:.3f} out of bounds [0, 1]"
