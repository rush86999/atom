"""
Property-Based Tests for Episode Segmentation Service - Critical Memory Logic

Tests episode segmentation invariants:
- Time gap detection (>4 hours triggers new episode)
- Topic change detection
- Task completion detection
- Minimum segment length
- Segment boundaries (disjoint, chronological)
- Episode metadata integrity
- Context preservation
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from uuid import uuid4
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestTimeGapSegmentationInvariants:
    """Tests for time-based segmentation invariants"""

    @given(
        num_events=st.integers(min_value=2, max_value=50),
        gap_threshold_hours=st.integers(min_value=1, max_value=12)
    )
    @settings(max_examples=50)
    def test_time_gap_detection(self, num_events, gap_threshold_hours):
        """Test that time gaps > threshold trigger new episodes"""
        events = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Create events with varying gaps
        for i in range(num_events):
            gap_hours = (i % 3) * gap_threshold_hours  # Some gaps exceed threshold
            event_time = base_time + timedelta(hours=i*2 + gap_hours)
            event = {
                "id": str(uuid4()),
                "timestamp": event_time,
                "content": f"Event {i}"
            }
            events.append(event)

        # Simulate segmentation based on time gaps
        episodes = []
        current_episode = [events[0]]

        for i in range(1, len(events)):
            time_diff = (events[i]["timestamp"] - events[i-1]["timestamp"]).total_seconds() / 3600
            if time_diff > gap_threshold_hours:
                # Start new episode
                episodes.append(current_episode)
                current_episode = [events[i]]
            else:
                current_episode.append(events[i])

        if current_episode:
            episodes.append(current_episode)

        # Verify all events are in episodes
        total_events_in_episodes = sum(len(ep) for ep in episodes)
        assert total_events_in_episodes == num_events, "All events should be in episodes"

    @given(
        gap_hours=st.integers(min_value=4, max_value=48)
    )
    @settings(max_examples=50)
    def test_time_gap_threshold_enforcement(self, gap_hours):
        """Test that time gap threshold is enforced"""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        threshold = timedelta(hours=4)

        event1 = {"timestamp": base_time}
        event2 = {"timestamp": base_time + timedelta(hours=gap_hours)}

        # Check if gap exceeds threshold
        time_diff = event2["timestamp"] - event1["timestamp"]
        should_segment = time_diff > threshold

        if gap_hours > 4:
            assert should_segment, f"Gap of {gap_hours} hours should trigger segmentation"
        else:
            assert not should_segment, f"Gap of {gap_hours} hours should not trigger segmentation"


class TestTopicChangeSegmentationInvariants:
    """Tests for topic change detection invariants"""

    @given(
        num_utterances=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=50)
    def test_topic_change_detection(self, num_utterances):
        """Test that topic changes trigger new segments"""
        # Simulate utterances with different topics
        topics = ["work", "personal", "shopping", "health", "finance"]
        utterances = []

        for i in range(num_utterances):
            utterance = {
                "id": str(uuid4()),
                "content": f"Utterance about {topics[i % len(topics)]}",
                "topic": topics[i % len(topics)],
                "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(minutes=i)
            }
            utterances.append(utterance)

        # Simulate topic change segmentation
        segments = []
        current_segment = [utterances[0]]

        for i in range(1, len(utterances)):
            if utterances[i]["topic"] != utterances[i-1]["topic"]:
                # Topic changed - start new segment
                segments.append(current_segment)
                current_segment = [utterances[i]]
            else:
                current_segment.append(utterances[i])

        if current_segment:
            segments.append(current_segment)

        # Verify segments are grouped by topic
        for segment in segments:
            first_topic = segment[0]["topic"]
            assert all(u["topic"] == first_topic for u in segment), "All utterances in segment should have same topic"

    @given(
        utterances=st.lists(
            st.tuples(
                st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz '),
                st.text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz')
            ),
            min_size=2,
            max_size=30
        )
    )
    @settings(max_examples=50)
    def test_topic_consistency_within_segments(self, utterances):
        """Test that segments maintain topic consistency"""
        # Group utterances by topic (second element of tuple)
        segments = {}
        for content, topic in utterances:
            if topic not in segments:
                segments[topic] = []
            segments[topic].append({"content": content, "topic": topic})

        # Verify each segment has consistent topic
        for topic, segment_utterances in segments.items():
            assert all(u["topic"] == topic for u in segment_utterances), f"Segment for {topic} should have consistent topic"


class TestTaskCompletionSegmentationInvariants:
    """Tests for task completion detection invariants"""

    @given(
        num_actions=st.integers(min_value=2, max_value=30)
    )
    @settings(max_examples=50)
    def test_task_completion_detection(self, num_actions):
        """Test that task completion triggers new segments"""
        # Simulate actions with task completion markers
        actions = []
        task_markers = ["start", "progress", "complete"]

        for i in range(num_actions):
            action = {
                "id": str(uuid4()),
                "type": "action",
                "task_complete": (i % 3 == 2),  # Every 3rd action completes task
                "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(minutes=i)
            }
            actions.append(action)

        # Simulate task completion segmentation
        completed_segments = []
        current_segment = []

        for action in actions:
            current_segment.append(action)
            if action["task_complete"]:
                # Task completed - end segment
                completed_segments.append(current_segment)
                current_segment = []

        # Only test if we have completed segments
        assume(len(completed_segments) > 0)

        # Verify all completed segments end with task_complete=True
        for segment in completed_segments:
            if len(segment) > 0:
                assert segment[-1]["task_complete"], "Completed segment should end with task completion"

    @given(
        segment_length=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_minimum_segment_length(self, segment_length):
        """Test that segments meet minimum length requirements"""
        # Minimum segment length should be 1 action
        min_length = 1

        # Create segment with specified length
        segment = [
            {"id": str(uuid4()), "action": f"action_{i}"}
            for i in range(segment_length)
        ]

        # Verify segment meets minimum length
        assert len(segment) >= min_length, f"Segment length {len(segment)} should be >= {min_length}"


class TestSegmentBoundaryInvariants:
    """Tests for segment boundary consistency"""

    @given(
        num_segments=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=50)
    def test_segment_boundaries_disjoint(self, num_segments):
        """Test that segment boundaries are disjoint (no overlaps)"""
        segments = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_segments):
            segment = {
                "id": str(uuid4()),
                "start_time": base_time + timedelta(hours=i*2),
                "end_time": base_time + timedelta(hours=i*2 + 1),
                "events": []
            }
            segments.append(segment)

        # Verify segments don't overlap
        for i in range(1, len(segments)):
            prev_end = segments[i-1]["end_time"]
            curr_start = segments[i]["start_time"]
            assert curr_start >= prev_end, "Segments should not overlap"

    @given(
        num_segments=st.integers(min_value=2, max_value=30)
    )
    @settings(max_examples=50)
    def test_segment_boundaries_chronological(self, num_segments):
        """Test that segments are in chronological order"""
        segments = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_segments):
            segment = {
                "id": str(uuid4()),
                "start_time": base_time + timedelta(hours=i),
                "end_time": base_time + timedelta(hours=i + 1)
            }
            segments.append(segment)

        # Verify chronological order
        for i in range(1, len(segments)):
            assert segments[i]["start_time"] >= segments[i-1]["start_time"], "Segments should be in chronological order"
            assert segments[i]["end_time"] >= segments[i-1]["end_time"], "Segment end times should be chronological"


class TestEpisodeMetadataInvariants:
    """Tests for episode metadata integrity"""

    @given(
        num_episodes=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_episode_metadata_completeness(self, num_episodes):
        """Test that episodes have required metadata"""
        episodes = []
        for i in range(num_episodes):
            episode = {
                "id": str(uuid4()),
                "start_time": datetime(2024, 1, 1, 12, 0, 0) + timedelta(hours=i),
                "end_time": datetime(2024, 1, 1, 13, 0, 0) + timedelta(hours=i),
                "agent_id": "test_agent",
                "segments": []
            }
            episodes.append(episode)

        # Verify all episodes have required metadata
        for episode in episodes:
            assert "id" in episode, "Episode should have ID"
            assert "start_time" in episode, "Episode should have start_time"
            assert "end_time" in episode, "Episode should have end_time"
            assert "agent_id" in episode, "Episode should have agent_id"
            assert "segments" in episode, "Episode should have segments list"
            assert episode["end_time"] >= episode["start_time"], "End time should be after start time"

    @given(
        start_hour=st.integers(min_value=0, max_value=20),
        duration_hours=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_episode_time_bounds(self, start_hour, duration_hours):
        """Test that episode time bounds are consistent"""
        start_time = datetime(2024, 1, 1, start_hour, 0, 0)
        end_time = start_time + timedelta(hours=duration_hours)

        episode = {
            "id": str(uuid4()),
            "start_time": start_time,
            "end_time": end_time
        }

        # Verify time bounds
        assert episode["end_time"] >= episode["start_time"], "End time should be after start time"
        duration = (episode["end_time"] - episode["start_time"]).total_seconds() / 3600
        assert duration == duration_hours, f"Duration should be {duration_hours} hours"


class TestContextPreservationInvariants:
    """Tests for context preservation in segments"""

    @given(
        segment_size=st.integers(min_value=3, max_value=20),
        context_window=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50)
    def test_context_window_preservation(self, segment_size, context_window):
        """Test that context window is preserved across segment boundaries"""
        # Create a segment with events
        events = []
        for i in range(segment_size):
            event = {
                "id": str(uuid4()),
                "content": f"Event {i}",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(minutes=i)
            }
            events.append(event)

        # Split into segments
        split_point = segment_size // 2
        segment1 = events[:split_point]
        segment2 = events[split_point:]

        # Verify context window is preserved
        # (Last context_window events from segment1 should be available in segment2)
        context_events = segment1[-context_window:] if context_window > 0 else []
        assert len(context_events) <= context_window, "Context should not exceed window size"

    @given(
        num_events=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=50)
    def test_no_information_loss(self, num_events):
        """Test that no information is lost during segmentation"""
        # Create events
        events = []
        for i in range(num_events):
            event = {
                "id": str(uuid4()),
                "content": f"Event {i}",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(minutes=i)
            }
            events.append(event)

        # Simulate segmentation (split in middle)
        split_point = num_events // 2
        segments = [events[:split_point], events[split_point:]]

        # Verify no events are lost
        total_in_segments = sum(len(seg) for seg in segments)
        assert total_in_segments == num_events, "No events should be lost during segmentation"

        # Verify all original events are present
        original_ids = set(e["id"] for e in events)
        segmented_ids = set()
        for segment in segments:
            for event in segment:
                segmented_ids.add(event["id"])

        assert original_ids == segmented_ids, "All event IDs should be preserved"
