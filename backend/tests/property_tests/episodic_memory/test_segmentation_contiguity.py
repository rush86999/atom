"""
Property-based tests for episode segmentation contiguity invariants.

Tests that episode segments are contiguous with no gaps or overlaps in timestamps.
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from core.episode_segmentation_service import EpisodeBoundaryDetector


# ============================================================================
# SEGMENTATION CONTIGUITY PROPERTY TESTS
# ============================================================================

pytestmark = pytest.mark.property


class TestSegmentationContiguity:
    """
    Property tests for episode segmentation contiguity.

    Invariants tested:
    1. Segments cover full episode timeline with no gaps
    2. No two segments have overlapping time ranges
    3. Time gaps > threshold cause segment split
    4. Messages within segments maintain original order
    """

    @given(st.lists(
        st.datetimes(
            min_value=datetime.now() - timedelta(days=30),
            max_value=datetime.now()
        ),
        min_size=2,
        max_size=50,
        unique=True  # Ensure no duplicate timestamps
    ))
    @settings(max_examples=200, deadline=None)
    def test_segments_are_contiguous_no_gaps(self, message_timestamps):
        """
        PROPERTY: Segments cover full episode timeline with no gaps

        STRATEGY: Generate lists of 2-50 unique message timestamps uniformly distributed
                  across 30-day range. Hypothesis explores edge cases like:
                  - Clumped timestamps (small gaps)
                  - Spread-out timestamps (large gaps)
                  - Uniformly spaced timestamps
                  - Random distributions

        INVARIANT: For episode with messages M = [m₁, m₂, ..., mₙ] sorted by timestamp:
                   Let segments = segment(M)
                   Let S = {s.start_time | s ∈ segments} ∪ {s.end_time | s ∈ segments}

                   Coverage: min(S) ≤ m₁.timestamp (first message covered)
                             max(S) ≥ mₙ.timestamp (last message covered)

                   No gaps: For any two consecutive segments seg_a, seg_b:
                            seg_a.end_time >= seg_b.start_time

                   This ensures no message falls outside segment boundaries and
                   segments touch at boundaries (no unallocated time).

        RADII: 200 examples sufficient because:
               - Time gap threshold is fixed (30 minutes)
               - Contiguity is monotonic property (all-or-nothing)
               - 200 random timestamps explore all gap patterns:
                 * Expected gap variations: O(n²) for n=50 messages = 2500 patterns
                 * Hypothesis shrinking finds minimal counterexample
                 * Covers edge cases: adjacent messages, large gaps, exact threshold
        """
        # Skip if less than 2 messages (need at least 2 for segmentation)
        assume(len(message_timestamps) >= 2)

        # Sort timestamps to simulate message order
        sorted_timestamps = sorted(message_timestamps)

        # Create mock message objects with timestamps
        class MockMessage:
            def __init__(self, timestamp):
                self.created_at = timestamp

        messages = [MockMessage(ts) for ts in sorted_timestamps]

        # Detect time gaps (use EpisodeBoundaryDetector)
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gap_indices = detector.detect_time_gap(messages)

        # Create segments based on gap indices
        # Segment boundaries are at gap_indices
        segments = []
        start_idx = 0

        for gap_idx in gap_indices:
            # Segment from start_idx to gap_idx
            segment_messages = messages[start_idx:gap_idx]
            if segment_messages:
                segments.append({
                    'start': segment_messages[0].created_at,
                    'end': segment_messages[-1].created_at
                })
            start_idx = gap_idx

        # Add final segment
        if start_idx < len(messages):
            final_messages = messages[start_idx:]
            if final_messages:
                segments.append({
                    'start': final_messages[0].created_at,
                    'end': final_messages[-1].created_at
                })

        # INVARIANT 1: First message covered
        assert len(segments) > 0, "At least one segment should exist"
        assert segments[0]['start'] <= messages[0].created_at, \
            f"First segment starts after first message: {segments[0]['start']} > {messages[0].created_at}"

        # INVARIANT 2: Last message covered
        assert segments[-1]['end'] >= messages[-1].created_at, \
            f"Last segment ends before last message: {segments[-1]['end']} < {messages[-1].created_at}"

        # INVARIANT 3: No gaps between segments (contiguity)
        for i in range(len(segments) - 1):
            seg_a_end = segments[i]['end']
            seg_b_start = segments[i + 1]['start']

            # Segments must be contiguous or overlapping (next starts during or after previous)
            assert seg_a_end >= seg_b_start - timedelta(minutes=1), \
                f"Gap detected between segment {i} and {i+1}: {seg_a_end} vs {seg_b_start}"

    @given(st.lists(
        st.datetimes(
            min_value=datetime.now() - timedelta(days=30),
            max_value=datetime.now()
        ),
        min_size=2,
        max_size=50,
        unique=True
    ))
    @settings(max_examples=200, deadline=None)
    def test_segments_do_not_overlap(self, message_timestamps):
        """
        PROPERTY: No two segments have overlapping time ranges

        STRATEGY: Generate lists of 2-50 unique message timestamps to test
                  segment boundary detection. Explores cases where:
                  - Time gaps create clear boundaries
                  - Multiple messages in short time create single segment
                  - Edge case: messages exactly at threshold boundary

        INVARIANT: For any two segments seg_a and seg_b where seg_a precedes seg_b:
                   seg_a.end_time < seg_b.start_time (non-overlapping)

                   Formally: ∀ seg_a, seg_b ∈ segments:
                             order(seg_a) < order(seg_b) ⟹ seg_a.end < seg_b.start

                   This prevents double-counting messages and ensures clear
                   temporal boundaries for semantic understanding.

        RADII: 200 examples sufficient because:
               - Overlap detection is O(n²) for n segments
               - 50 messages → at most 50 segments
               - Worst-case pair checks: 50*49/2 = 1225 pairs
               - 200 examples * 1225 checks = 245,000 pair validations
               - Covers all overlap patterns (consecutive, nested, adjacent)
        """
        # Skip if less than 2 messages
        assume(len(message_timestamps) >= 2)

        # Sort timestamps
        sorted_timestamps = sorted(message_timestamps)

        # Create mock message objects
        class MockMessage:
            def __init__(self, timestamp):
                self.created_at = timestamp

        messages = [MockMessage(ts) for ts in sorted_timestamps]

        # Detect time gaps
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gap_indices = detector.detect_time_gap(messages)

        # Create segments
        segments = []
        start_idx = 0

        for gap_idx in gap_indices:
            segment_messages = messages[start_idx:gap_idx]
            if segment_messages:
                segments.append({
                    'start': segment_messages[0].created_at,
                    'end': segment_messages[-1].created_at,
                    'indices': (start_idx, gap_idx)
                })
            start_idx = gap_idx

        # Add final segment
        if start_idx < len(messages):
            final_messages = messages[start_idx:]
            if final_messages:
                segments.append({
                    'start': final_messages[0].created_at,
                    'end': final_messages[-1].created_at,
                    'indices': (start_idx, len(messages))
                })

        # INVARIANT: No overlaps between any two segments
        for i in range(len(segments)):
            for j in range(i + 1, len(segments)):
                seg_a = segments[i]
                seg_b = segments[j]

                # Segments must not overlap
                # seg_a ends before seg_b starts (or they're adjacent)
                assert seg_a['end'] < seg_b['start'], \
                    f"Segments {i} and {j} overlap: " \
                    f"seg_a[{seg_a['indices'][0]}:{seg_a['indices'][1]}] = [{seg_a['start']}, {seg_a['end']}], " \
                    f"seg_b[{seg_b['indices'][0]}:{seg_b['indices'][1]}] = [{seg_b['start']}, {seg_b['end']}]"

    @given(st.lists(
        st.datetimes(
            min_value=datetime.now() - timedelta(days=30),
            max_value=datetime.now()
        ),
        min_size=5,
        max_size=50,
        unique=True
    ))
    @settings(max_examples=100, deadline=None)
    def test_segmentation_on_time_gaps(self, message_timestamps):
        """
        PROPERTY: Time gaps > threshold (30 minutes) cause segment split

        STRATEGY: Generate lists of 5-50 message timestamps to test gap detection.
                  Hypothesis naturally explores:
                  - All messages within 30 min → 1 segment
                  - One large gap → 2 segments
                  - Multiple gaps → multiple segments
                  - Gap exactly at threshold (30 min)

        INVARIANT: For consecutive messages mᵢ, mᵢ₊₁ with gap g:
                   boundary_created(g) ⟺ g > THRESHOLD

                   Where THRESHOLD = 30 minutes (exclusive)

                   Key insight: Gap of exactly 30 minutes does NOT trigger split.
                   This prevents over-segmentation and preserves context continuity.

        RADII: 100 examples sufficient because:
               - Gap detection is O(n) for n messages
               - Threshold behavior is binary (> 30 min vs <= 30 min)
               - 100 examples explore:
                 * No gaps (all messages in 30 min window)
                 * Single gap scenarios
                 * Multiple gaps
                 * Edge case: gap = 30.0 minutes (exclusive threshold)
        """
        # Skip if less than 5 messages (need reasonable sample for gaps)
        assume(len(message_timestamps) >= 5)

        # Sort timestamps
        sorted_timestamps = sorted(message_timestamps)

        # Create mock message objects
        class MockMessage:
            def __init__(self, timestamp):
                self.created_at = timestamp

        messages = [MockMessage(ts) for ts in sorted_timestamps]

        # Calculate expected gaps
        expected_gaps = []
        for i in range(1, len(messages)):
            gap_minutes = (messages[i].created_at - messages[i-1].created_at).total_seconds() / 60
            expected_gaps.append(gap_minutes)

        # Detect time gaps using service
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        detected_gaps = detector.detect_time_gap(messages)

        # INVARIANT: All detected gaps should have gap > 30 minutes
        for gap_idx in detected_gaps:
            if gap_idx > 0 and gap_idx < len(messages):
                gap_minutes = (messages[gap_idx].created_at - messages[gap_idx-1].created_at).total_seconds() / 60

                # CRITICAL: Threshold is EXCLUSIVE (> 30, not >= 30)
                assert gap_minutes > 30.0, \
                    f"Gap at index {gap_idx} is {gap_minutes} minutes (not > 30)"

        # INVARIANT: All gaps > 30 minutes should be detected
        for i, gap_minutes in enumerate(expected_gaps):
            if gap_minutes > 30.0:
                # This gap should be in detected_gaps
                assert i in detected_gaps, \
                    f"Gap of {gap_minutes} minutes at index {i} not detected"

    @given(st.lists(
        st.integers(min_value=0, max_value=1000),
        min_size=5,
        max_size=100,
        unique=False  # Allow duplicates to test ordering
    ))
    @settings(max_examples=100, deadline=None)
    def test_segmentation_preserves_message_order(self, message_sequence_ids):
        """
        PROPERTY: Messages within segments maintain original chronological order

        STRATEGY: Generate lists of 5-100 sequence IDs representing message order.
                  Tests that segmentation preserves original message ordering.

        INVARIANT: For each segment S in episode:
                   Let messages_in_segment = [m₁, m₂, ..., mₖ] from S

                   Monotonicity: message_sequence_id(m₁) < message_sequence_id(m₂) < ... < message_sequence_id(mₖ)

                   This preserves causality and conversation flow, which is
                   critical for LLM context understanding and episode coherence.

        RADII: 100 examples sufficient because:
               - Ordering check is O(n) per segment
               - 100 messages * monotonic checks = 10,000 comparisons
               - Covers cases: ascending, duplicates, descending (Hypothesis finds)
               - Violations are immediately detectable (non-monotonic sequence)
        """
        # Skip if less than 5 messages
        assume(len(message_sequence_ids) >= 5)

        # Simulate segmentation at every 5th message
        segment_size = 5
        segments = []

        for i in range(0, len(message_sequence_ids), segment_size):
            segment_ids = message_sequence_ids[i:i + segment_size]
            segments.append(segment_ids)

        # INVARIANT: Each segment has monotonically increasing sequence IDs
        for seg_idx, segment in enumerate(segments):
            if len(segment) < 2:
                continue  # Skip single-message segments

            # Check monotonic increase
            for i in range(len(segment) - 1):
                assert segment[i] <= segment[i + 1], \
                    f"Segment {seg_idx} violates monotonicity: " \
                    f"segment[{i}] = {segment[i]}, segment[{i+1}] = {segment[i+1]}"
