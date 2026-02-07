"""
Property-Based Tests for Episode Segmentation Invariants

⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for episode segmentation.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md

Tests:
    - 5 comprehensive property-based tests for episode segmentation
    - Coverage targets: 100% of episode_segmentation_service.py
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from typing import List, Dict
from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    SegmentationResult,
    SegmentationBoundary
)
from core.models import Episode, EpisodeSegment


class TestEpisodeSegmentationInvariants:
    """Property-based tests for episode segmentation invariants."""

    # ========== Boundary Detection ==========

    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'event_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'event_type': st.sampled_from(['message', 'action', 'query', 'response']),
                'content': st.text(min_size=5, max_size=100)
            }),
            min_size=2,
            max_size=100
        ),
        time_gap_threshold_hours=st.floats(min_value=1.0, max_value=24.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_segmentation_boundary_detection(self, events, time_gap_threshold_hours):
        """INVARIANT: Segmentation must detect time gaps > threshold."""
        service = EpisodeSegmentationService()
        service.set_time_gap_threshold(hours=time_gap_threshold_hours)

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Detect boundaries
        result = service.detect_boundaries(sorted_events)

        # Verify all detected boundaries exceed threshold
        for boundary in result.boundaries:
            if boundary.prev_event_time and boundary.next_event_time:
                gap_hours = (boundary.next_event_time - boundary.prev_event_time).total_seconds() / 3600
                assert gap_hours >= time_gap_threshold_hours, \
                    f"Boundary gap {gap_hours}h is less than threshold {time_gap_threshold_hours}h"

    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'event_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'topic': st.sampled_from(['finance', 'development', 'marketing', 'sales', 'support', 'general']),
                'content': st.text(min_size=5, max_size=100)
            }),
            min_size=5,
            max_size=50
        ),
        topic_change_threshold=st.floats(min_value=0.3, max_value=0.8, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_segmentation_topic_change_detection(self, events, topic_change_threshold):
        """INVARIANT: Segmentation must detect topic changes."""
        service = EpisodeSegmentationService()
        service.set_topic_change_threshold(topic_change_threshold)

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Detect boundaries (including topic changes)
        result = service.detect_boundaries(sorted_events, detect_topic_changes=True)

        # Verify topic change boundaries
        topic_boundaries = [b for b in result.boundaries if b.reason == 'topic_change']

        # Verify topic changes are significant
        for boundary in topic_boundaries:
            assert boundary.topic_confidence >= topic_change_threshold, \
                f"Topic change confidence {boundary.topic_confidence} below threshold {topic_change_threshold}"

    # ========== Task Completion Detection ==========

    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'event_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'event_type': st.sampled_from(['task_start', 'task_update', 'task_complete', 'other']),
                'task_id': st.text(min_size=1, max_size=20, alphabet='abc123')
            }),
            min_size=5,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_segmentation_task_completion_detection(self, events):
        """INVARIANT: Segmentation must detect task completion boundaries."""
        service = EpisodeSegmentationService()

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Detect boundaries (including task completion)
        result = service.detect_boundaries(sorted_events, detect_task_completion=True)

        # Verify task completion boundaries
        task_boundaries = [b for b in result.boundaries if b.reason == 'task_complete']

        # Verify task_complete events create boundaries
        task_complete_events = [e for e in sorted_events if e['event_type'] == 'task_complete']
        assert len(task_boundaries) >= len(task_complete_events), \
            "Each task_complete should create at least one boundary"

    # ========== Segment Size Validation ==========

    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'event_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'content': st.text(min_size=5, max_size=100)
            }),
            min_size=10,
            max_size=200
        ),
        min_segment_size=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_segmentation_minimum_length(self, events, min_segment_size):
        """INVARIANT: Segments must meet minimum size requirement."""
        service = EpisodeSegmentationService()
        service.set_min_segment_size(min_segment_size)

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Create segments
        result = service.create_segments(sorted_events)

        # Verify minimum segment size
        for segment in result.segments:
            assert len(segment.events) >= min_segment_size, \
                f"Segment has {len(segment.events)} events, minimum is {min_segment_size}"

    # ========== Segment Disjointness ==========

    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'event_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'content': st.text(min_size=5, max_size=100)
            }),
            min_size=10,
            max_size=100
        )
    )
    @settings(max_examples=100)
    def test_segmentation_no_overlapping_segments(self, events):
        """INVARIANT: Segments must be temporally disjoint (no overlaps)."""
        service = EpisodeSegmentationService()

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Create segments
        result = service.create_segments(sorted_events)

        # Verify no overlapping segments
        for i in range(len(result.segments) - 1):
            current_segment = result.segments[i]
            next_segment = result.segments[i + 1]

            # Get last event of current segment
            current_last_time = max(e['timestamp'] for e in current_segment.events)

            # Get first event of next segment
            next_first_time = min(e['timestamp'] for e in next_segment.events)

            # Verify no overlap
            assert current_last_time <= next_first_time, \
                f"Segments overlap: current ends at {current_last_time}, next starts at {next_first_time}"

    # ========== Segment Coverage ==========

    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'event_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'content': st.text(min_size=5, max_size=100)
            }),
            min_size=10,
            max_size=100
        )
    )
    @settings(max_examples=100)
    def test_segmentation_complete_coverage(self, events):
        """INVARIANT: All events must be assigned to segments (no gaps)."""
        service = EpisodeSegmentationService()

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Create segments
        result = service.create_segments(sorted_events)

        # Count events in segments
        events_in_segments = sum(len(seg.events) for seg in result.segments)

        # Verify all events are covered
        assert events_in_segments == len(sorted_events), \
            f"Not all events covered: {events_in_segments} in segments, {len(sorted_events)} total"

        # Verify no duplicate events
        all_event_ids = []
        for segment in result.segments:
            for event in segment.events:
                all_event_ids.append(event['event_id'])

        assert len(all_event_ids) == len(set(all_event_ids)), \
            "Duplicate events found in segments"
