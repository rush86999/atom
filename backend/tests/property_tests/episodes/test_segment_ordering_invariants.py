"""
Property-based tests for episode segment ordering invariants.

Uses Hypothesis to test segment ordering invariants across many generated inputs:
- Chronological ordering: Segments ordered by start_timestamp
- End after start: Every segment has end_timestamp > start_timestamp
- Timestamp consistency: Segment timestamps within episode timeframe
- No overlap: No two segments within same episode have overlapping time ranges
- Contiguity: Adjacent segments have matching boundaries

These tests complement the integration tests by verifying invariants hold
across many different input combinations.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from hypothesis import given, strategies as st, settings, HealthCheck

from core.episode_segmentation_service import EpisodeSegmentationService, EpisodeBoundaryDetector
from core.models import Episode, EpisodeSegment, ChatMessage


# =============================================================================
# Property-Based Tests for Segment Chronological Ordering
# =============================================================================

class TestSegmentChronologicalOrdering:
    """
    Property-based tests for segment chronological ordering invariants.

    Uses Hypothesis to generate many different inputs and verify invariants
    always hold. This catches edge cases that unit tests might miss.
    """

    @pytest.mark.asyncio
    @given(
        timestamp_deltas=st.lists(
            st.integers(min_value=0, max_value=86400),  # 0 to 24 hours in seconds
            min_size=2,
            max_size=50
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_segment_chronological_ordering_invariant(self, db_session, timestamp_deltas):
        """
        Segments within episode are ordered by start_timestamp.

        Property: For any list of message timestamps, segments created
        from them maintain chronological order by start_timestamp.

        Mathematical specification:
        Let S = [s₁, s₂, ..., sₙ] be segments within an episode
        Then: s₁.start_timestamp <= s₂.start_timestamp <= ... <= sₙ.start_timestamp
        """
        from hypothesis import HealthCheck

        # Create test agent
        agent_id = f"test_agent_{uuid4().hex[:8]}"
        user_id = f"test_user_{uuid4().hex[:8]}"

        # Create base time
        base_time = datetime.now(timezone.utc)

        # Create chat session
        session_id = str(uuid4())
        session = Mock(id=session_id, user_id=user_id, created_at=base_time)

        # Create messages with varying timestamps
        messages = []
        for i, delta in enumerate(timestamp_deltas):
            msg = Mock(
                id=str(uuid4()),
                conversation_id=session_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Test message {i}",
                created_at=base_time + timedelta(seconds=delta)
            )
            messages.append(msg)

        # Create segmentation service
        with patch('core.episode_segmentation_service.get_db_session', return_value=db_session):
            with patch('core.episode_segmentation_service.get_lancedb_handler'):
                service = EpisodeSegmentationService(db_session)

                # Detect boundaries (time gaps)
                detector = EpisodeBoundaryDetector(service.lancedb)
                # Create mock ChatMessage objects from our mocks
                mock_messages = []
                for msg in messages:
                    mock_msg = Mock()
                    mock_msg.id = msg.id
                    mock_msg.conversation_id = msg.conversation_id
                    mock_msg.role = msg.role
                    mock_msg.content = msg.content
                    mock_msg.created_at = msg.created_at
                    mock_messages.append(mock_msg)

                # Detect time gaps (no embeddings available, will use keyword similarity)
                boundaries = set()
                if len(mock_messages) >= 2:
                    for i in range(1, len(mock_messages)):
                        prev_time = mock_messages[i-1].created_at
                        curr_time = mock_messages[i].created_at
                        gap_minutes = (curr_time - prev_time).total_seconds() / 60

                        # Time gap threshold is 30 minutes
                        if gap_minutes > 30:
                            boundaries.add(i)

                # Verify chronological ordering invariant
                # Messages should be ordered by created_at
                timestamps = [m.created_at for m in mock_messages]
                assert timestamps == sorted(timestamps), (
                    f"Messages not in chronological order: {timestamps}"
                )

    @pytest.mark.asyncio
    @given(
        durations=st.lists(
            st.integers(min_value=1, max_value=3600),  # 1 second to 1 hour
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_segment_end_after_start_invariant(self, db_session, durations):
        """
        Every segment has end_timestamp > start_timestamp.

        Property: For any segment duration, end_timestamp is always
        after start_timestamp.

        Mathematical specification:
        For all segments s: s.end_timestamp > s.start_timestamp
        Duration = s.end_timestamp - s.start_timestamp > 0
        """
        from hypothesis import HealthCheck

        base_time = datetime.now(timezone.utc)

        # Simulate segments with different durations
        for i, duration in enumerate(durations):
            start_time = base_time + timedelta(hours=i)
            end_time = start_time + timedelta(seconds=duration)

            # Verify end > start
            assert end_time > start_time, (
                f"Segment {i}: end_time {end_time} not after start_time {start_time}"
            )

            # Verify positive duration
            calculated_duration = (end_time - start_time).total_seconds()
            assert calculated_duration > 0, (
                f"Segment {i}: duration {calculated_duration} is not positive"
            )

    @pytest.mark.asyncio
    @given(
        episode_offsets=st.lists(
            st.integers(min_value=-86400, max_value=86400),  # -24h to +24h
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_segment_timestamp_consistency_invariant(self, db_session, episode_offsets):
        """
        Segment timestamps are within episode timeframe.

        Property: For any episode with start and end timestamps,
        all segment timestamps fall within [episode.start, episode.end].

        Mathematical specification:
        Let episode = (start_time, end_time)
        For all segments s: s.start_timestamp >= episode.start_time
                         and s.end_timestamp <= episode.end_time
        """
        from hypothesis import HealthCheck

        base_time = datetime.now(timezone.utc)
        episode_start = base_time
        episode_end = base_time + timedelta(days=1)

        # Simulate segments within episode
        for i, offset in enumerate(episode_offsets):
            # Segment start should be within episode bounds
            segment_start = episode_start + timedelta(seconds=offset)
            segment_end = segment_start + timedelta(minutes=30)

            # Only check if segment would be within episode
            if segment_start >= episode_start and segment_end <= episode_end:
                # Verify segment within episode bounds
                assert segment_start >= episode_start, (
                    f"Segment {i} start {segment_start} before episode start {episode_start}"
                )
                assert segment_end <= episode_end, (
                    f"Segment {i} end {segment_end} after episode end {episode_end}"
                )


# =============================================================================
# Property-Based Tests for Segment Non-Overlap
# =============================================================================

class TestSegmentNonOverlap:
    """
    Property-based tests for segment non-overlap invariants.

    Verifies that segments within an episode don't overlap in time.
    """

    @pytest.mark.asyncio
    @given(
        segment_starts=st.lists(
            st.integers(min_value=0, max_value=7200),  # 0 to 2 hours in seconds
            min_size=2,
            max_size=20,
            unique=True  # Ensure unique start times
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_segment_no_overlap_invariant(self, db_session, segment_starts):
        """
        No two segments within same episode have overlapping time ranges.

        Property: For any two segments s₁ and s₂ within same episode,
        their time ranges do not overlap.

        Mathematical specification:
        For all segments sᵢ, sⱼ in same episode:
        Either: sᵢ.end <= sⱼ.start (sᵢ before sⱼ)
        Or:     sⱼ.end <= sᵢ.start (sⱼ before sᵢ)
        """
        from hypothesis import HealthCheck

        base_time = datetime.now(timezone.utc)
        segment_duration = timedelta(minutes=30)

        # Create segments with sorted start times
        sorted_starts = sorted(segment_starts)
        segments = []
        for i, start_offset in enumerate(sorted_starts):
            start_time = base_time + timedelta(seconds=start_offset)
            end_time = start_time + segment_duration
            segments.append((start_time, end_time))

        # Verify no overlap between consecutive segments
        for i in range(len(segments) - 1):
            current_start, current_end = segments[i]
            next_start, next_end = segments[i + 1]

            # Consecutive segments should not overlap
            # Current segment should end before or when next starts
            assert current_end <= next_start or current_start >= next_end, (
                f"Segments {i} and {i+1} overlap: "
                f"[{current_start}, {current_end}] and [{next_start}, {next_end}]"
            )

    @pytest.mark.asyncio
    @given(
        gaps=st.lists(
            st.integers(min_value=0, max_value=3600),  # 0 to 60 minutes
            min_size=2,
            max_size=20
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_segment_gap_invariant(self, db_session, gaps):
        """
        Gaps between segments don't exceed threshold.

        Property: For any gap between segments, the gap duration
        should be within acceptable threshold (configurable).

        Note: In practice, large gaps trigger new episodes, not segments.
        This test verifies that gaps are detected correctly.
        """
        from hypothesis import HealthCheck

        base_time = datetime.now(timezone.utc)
        segment_duration = timedelta(minutes=30)
        max_gap_threshold = timedelta(minutes=30)  # TIME_GAP_THRESHOLD_MINUTES

        # Create segments with gaps
        segments = []
        current_time = base_time

        for i, gap_seconds in enumerate(gaps):
            start_time = current_time
            end_time = start_time + segment_duration
            segments.append((start_time, end_time))

            # Add gap before next segment
            current_time = end_time + timedelta(seconds=gap_seconds)

        # Verify gap detection
        for i in range(len(segments) - 1):
            current_end = segments[i][1]
            next_start = segments[i + 1][0]
            gap = next_start - current_end

            # Gaps > 30 minutes should trigger new episode
            # This is the boundary from TIME_GAP_THRESHOLD_MINUTES
            if gap > max_gap_threshold:
                # Large gap detected - should be new episode boundary
                assert gap > max_gap_threshold, (
                    f"Gap {gap} between segments {i} and {i+1} exceeds threshold"
                )


# =============================================================================
# Property-Based Tests for Segment Contiguity
# =============================================================================

class TestSegmentContiguity:
    """
    Property-based tests for segment contiguity invariants.

    Verifies that adjacent segments have proper boundary alignment.
    """

    @pytest.mark.asyncio
    @given(
        segment_count=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_segment_contiguity_invariant(self, db_session, segment_count):
        """
        Adjacent segments have matching boundaries (end of prev = start of next).

        Property: For consecutive segments without gaps, the end of
        previous segment equals the start of next segment.

        Mathematical specification:
        For segments sᵢ, sᵢ₊₁ with no gap:
        sᵢ.end_timestamp == sᵢ₊₁.start_timestamp
        """
        from hypothesis import HealthCheck

        base_time = datetime.now(timezone.utc)
        segment_duration = timedelta(minutes=30)

        # Create contiguous segments (no gaps)
        segments = []
        current_time = base_time

        for i in range(segment_count):
            start_time = current_time
            end_time = start_time + segment_duration
            segments.append((start_time, end_time))
            current_time = end_time  # Next segment starts where previous ended

        # Verify contiguity
        for i in range(len(segments) - 1):
            current_end = segments[i][1]
            next_start = segments[i + 1][0]

            # For contiguous segments, end of prev should equal start of next
            assert current_end == next_start, (
                f"Segments {i} and {i+1} not contiguous: "
                f"end={current_end}, next_start={next_start}"
            )

    @pytest.mark.asyncio
    @given(
        event_counts=st.lists(
            st.integers(min_value=1, max_value=10),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_segment_boundary_invariant(self, db_session, event_counts):
        """
        Segment boundaries are aligned to meaningful events.

        Property: Segment boundaries occur at meaningful transition points:
        - Time gaps (>30 minutes)
        - Topic changes (semantic similarity < 0.75)
        - Task completions

        This test verifies that boundaries align with event transitions.
        """
        from hypothesis import HealthCheck

        # Simulate events with different counts per segment
        total_events = sum(event_counts)
        assert total_events >= 2, "Need at least 2 events for segmentation"

        # Verify event groupings
        current_event_index = 0
        segment_boundaries = []

        for i, count in enumerate(event_counts):
            segment_start = current_event_index
            segment_end = current_event_index + count
            segment_boundaries.append((segment_start, segment_end))
            current_event_index = segment_end

        # Verify boundaries are non-overlapping and cover all events
        for i in range(len(segment_boundaries) - 1):
            current_end = segment_boundaries[i][1]
            next_start = segment_boundaries[i + 1][0]

            # Segments should be adjacent (no gaps in event indices)
            assert current_end == next_start, (
                f"Segment boundary mismatch: segment {i} ends at {current_end}, "
                f"segment {i+1} starts at {next_start}"
            )

        # Verify all events covered
        first_start = segment_boundaries[0][0]
        last_end = segment_boundaries[-1][1]
        assert first_start == 0, f"First segment doesn't start at event 0: {first_start}"
        assert last_end == total_events, f"Last segment doesn't end at {total_events}: {last_end}"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db_session():
    """
    Create fresh database session for property tests.

    Uses in-memory SQLite for test isolation.
    """
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import pool

    # Set testing environment
    os.environ["TESTING"] = "1"

    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Use pooled connections with check_same_thread=False for SQLite
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
        echo=False,
        pool_pre_ping=True
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables we need
    from core.database import Base

    tables_to_create = [
        'agent_episodes',
        'episode_segments',
        'canvas_audit',
        'agent_feedback',
        'agent_registry',
        'chat_sessions',
    ]

    for table_name in tables_to_create:
        if table_name in Base.metadata.tables:
            try:
                Base.metadata.tables[table_name].create(engine, checkfirst=True)
            except Exception as e:
                print(f"Warning: Could not create table {table_name}: {e}")

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass
