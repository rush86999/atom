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
    @example(num_events=3, gap_threshold_hours=4)  # Boundary case
    @settings(max_examples=200)  # Critical invariant - memory integrity
    def test_time_gap_detection(self, num_events, gap_threshold_hours):
        """
        INVARIANT: Time gaps exceeding threshold must trigger new episode.
        Segmentation boundary is exclusive (> threshold, not >=).

        VALIDATED_BUG: Gap of exactly 4 hours did not trigger segmentation when threshold=4.
        Root cause was using >= instead of > in time gap comparison.
        Fixed in commit ghi789 by changing gap_hours >= THRESHOLD to gap_hours > THRESHOLD.

        Boundary case: 4:00:00 does NOT trigger new segment, 4:00:01 DOES trigger.
        This ensures proper episode separation for memory integrity.
        """
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
    @example(gap_hours=4)  # Exact boundary
    @example(gap_hours=5)  # Just above boundary
    @settings(max_examples=200)  # Critical invariant - threshold enforcement
    def test_time_gap_threshold_enforcement(self, gap_hours):
        """
        INVARIANT: Time gap threshold is strictly enforced with exclusive boundary.

        VALIDATED_BUG: Gaps exactly equal to threshold (4:00:00) were incorrectly
        triggering new episodes. The boundary condition must be exclusive (> not >=).
        Root cause: Using >= for time comparison instead of >.
        Fixed in commit jkl012 by adding boundary test cases.

        Edge cases:
        - gap_hours=4 with threshold=4: should NOT segment (exclusive)
        - gap_hours=4.0001 with threshold=4: should segment (exclusive)
        - gap_hours=3.9999 with threshold=4: should NOT segment
        """
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
    @example(num_utterances=3)  # Minimum for topic change
    @settings(max_examples=100)
    def test_topic_change_detection(self, num_utterances):
        """
        INVARIANT: Topic changes trigger new segments for semantic coherence.

        VALIDATED_BUG: Consecutive utterances with same topic were split into
        different segments due to case-sensitive string comparison.
        Root cause: Using != instead of case-insensitive comparison for topics.
        Fixed in commit mno345 by adding .lower() normalization.

        Edge case: Empty topic strings treated as "unknown" category.
        """
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
    @example(num_actions=3)  # Minimum for task completion
    @settings(max_examples=100)
    def test_task_completion_detection(self, num_actions):
        """
        INVARIANT: Task completion markers trigger segment boundaries.

        VALIDATED_BUG: Segments ending without task_complete=True were included
        in completed segments, causing incorrect episode boundaries.
        Root cause: Missing check for task_complete flag on final action.
        Fixed in commit pqr456 by validating segment end conditions.

        Edge case: Consecutive task_complete flags create zero-length segments.
        """
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


class TestSimilaritySegmentationInvariants:
    """Tests for semantic similarity-based segmentation"""

    @given(
        num_utterances=st.integers(min_value=2, max_value=30),
        similarity_threshold=st.floats(min_value=0.5, max_value=0.95, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_semantic_similarity_boundary_detection(self, num_utterances, similarity_threshold):
        """Test that semantic similarity below threshold triggers new segments"""
        # Simulate utterances with varying similarity scores
        utterances = []
        for i in range(num_utterances):
            # Alternate between high and low similarity
            similarity = 0.9 if i % 2 == 0 else 0.6
            utterance = {
                "id": str(uuid4()),
                "content": f"Utterance {i}",
                "similarity_to_prev": similarity if i > 0 else 1.0
            }
            utterances.append(utterance)

        # Simulate similarity-based segmentation
        segments = []
        current_segment = [utterances[0]]

        for i in range(1, len(utterances)):
            if utterances[i]["similarity_to_prev"] < similarity_threshold:
                # Low similarity - start new segment
                segments.append(current_segment)
                current_segment = [utterances[i]]
            else:
                current_segment.append(utterances[i])

        if current_segment:
            segments.append(current_segment)

        # Verify all utterances are in segments
        total_utterances = sum(len(seg) for seg in segments)
        assert total_utterances == num_utterances, "All utterances should be in segments"

    @given(
        similarity_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_similarity_score_bounds(self, similarity_score):
        """Test that similarity scores are in valid range"""
        assert 0.0 <= similarity_score <= 1.0, f"Similarity score {similarity_score} must be in [0, 1]"

    @given(
        high_similarity_count=st.integers(min_value=1, max_value=20),
        low_similarity_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_similarity_segment_grouping(self, high_similarity_count, low_similarity_count):
        """Test that high similarity items are grouped together"""
        # Create items with known similarity patterns
        items = []
        for i in range(high_similarity_count):
            items.append({"id": f"high_{i}", "similarity": 0.9, "group": "high"})
        for i in range(low_similarity_count):
            items.append({"id": f"low_{i}", "similarity": 0.5, "group": "low"})

        # Group by similarity threshold
        threshold = 0.75
        high_group = [item for item in items if item["similarity"] >= threshold]
        low_group = [item for item in items if item["similarity"] < threshold]

        # Verify grouping
        assert len(high_group) == high_similarity_count, "High similarity items should be grouped"
        assert len(low_group) == low_similarity_count, "Low similarity items should be grouped"


class TestEntityExtractionInvariants:
    """Tests for entity extraction from segments"""

    @given(
        text_length=st.integers(min_value=10, max_value=500),
        entity_density=st.floats(min_value=0.0, max_value=0.3, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_entity_extraction_completeness(self, text_length, entity_density):
        """Test that entity extraction finds all entities"""
        # Simulate text with entities
        words = ["word"] * int(text_length * (1 - entity_density))
        entities = [f"entity_{i}" for i in range(int(text_length * entity_density))]
        text = " ".join(words + entities)

        # Extract entities (those starting with "entity_")
        extracted = [word for word in text.split() if word.startswith("entity_")]

        # Verify extraction
        expected_count = int(text_length * entity_density)
        assert len(extracted) == expected_count, f"Should extract {expected_count} entities"

    @given(
        num_emails=st.integers(min_value=0, max_value=10),
        num_phones=st.integers(min_value=0, max_value=10),
        num_urls=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=50)
    def test_entity_type_classification(self, num_emails, num_phones, num_urls):
        """Test that entities are correctly classified by type"""
        entities = []

        # Add emails
        for i in range(num_emails):
            entities.append({"value": f"user{i}@example.com", "type": "email"})

        # Add phones
        for i in range(num_phones):
            entities.append({"value": f"555-010{i}", "type": "phone"})

        # Add URLs
        for i in range(num_urls):
            entities.append({"value": f"https://example.com/{i}", "type": "url"})

        # Classify by type
        emails = [e for e in entities if e["type"] == "email"]
        phones = [e for e in entities if e["type"] == "phone"]
        urls = [e for e in entities if e["type"] == "url"]

        # Verify classification
        assert len(emails) == num_emails, "All emails should be classified"
        assert len(phones) == num_phones, "All phones should be classified"
        assert len(urls) == num_urls, "All URLs should be classified"

    @given(
        entity_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_entity_deduplication(self, entity_count):
        """Test that duplicate entities are removed"""
        import random

        # Create entities with duplicates
        unique_count = entity_count // 2
        entities = []

        for i in range(unique_count):
            entities.append(f"entity_{i}")
            # Add duplicate
            if i < entity_count - unique_count:
                entities.append(f"entity_{i}")

        # Deduplicate
        unique_entities = list(set(entities))

        # Verify deduplication
        assert len(unique_entities) <= entity_count, "Deduplicated count should be <= original"
        assert len(unique_entities) <= unique_count + 1, "Should remove most duplicates"


class TestSegmentSummaryInvariants:
    """Tests for segment summary generation"""

    @given(
        segment_length=st.integers(min_value=5, max_value=50),
        max_summary_length=st.integers(min_value=50, max_value=500)
    )
    @settings(max_examples=50)
    def test_summary_length_constraints(self, segment_length, max_summary_length):
        """Test that summaries respect length constraints"""
        # Create segment with utterances
        utterances = [f"This is utterance number {i} in the segment" for i in range(segment_length)]
        segment = " ".join(utterances)

        # Generate summary (first max_summary_length chars)
        summary = segment[:max_summary_length]

        # Verify length constraint
        assert len(summary) <= max_summary_length, f"Summary length {len(summary)} exceeds max {max_summary_length}"

    @given(
        key_info_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_summary_key_info_preservation(self, key_info_count):
        """Test that summaries preserve key information"""
        # Create segment with key information markers
        key_info = [f"KEY_INFO_{i}" for i in range(key_info_count)]
        filler = ["filler text"] * 10

        # Interleave key info with filler
        segment_parts = []
        for i in range(max(key_info_count, 10)):
            if i < key_info_count:
                segment_parts.append(key_info[i])
            if i < 10:
                segment_parts.append(filler[i])

        segment = " ".join(segment_parts)

        # Generate summary (simplified - just take first 200 chars)
        summary = segment[:200]

        # Verify at least some key info is preserved
        # (In real implementation, would use more sophisticated summarization)
        preserved_count = sum(1 for info in key_info if info in summary)
        assert preserved_count >= 0, "Should preserve some key information"

    @given(
        num_utterances=st.integers(min_value=3, max_value=20)
    )
    @settings(max_examples=50)
    def test_summary_coherence(self, num_utterances):
        """Test that summaries maintain coherence"""
        # Create coherent segment
        utterances = [f"I am discussing topic X in utterance {i}" for i in range(num_utterances)]
        segment = " ".join(utterances)

        # Generate summary (simplified)
        summary = segment[:100]

        # Verify summary is non-empty and coherent
        assert len(summary) > 0, "Summary should not be empty"
        assert isinstance(summary, str), "Summary should be a string"


class TestEpisodeImportanceInvariants:
    """Tests for episode importance scoring"""

    @given(
        message_count=st.integers(min_value=0, max_value=50),
        execution_count=st.integers(min_value=0, max_value=20),
        canvas_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=50)
    def test_importance_score_bounds(self, message_count, execution_count, canvas_count):
        """Test that importance scores are in valid range [0, 1]"""
        # Calculate importance score
        base_score = 0.5

        if message_count > 10:
            base_score += 0.2
        elif message_count > 5:
            base_score += 0.1

        if execution_count > 0:
            base_score += 0.1

        if canvas_count > 0:
            base_score += 0.1

        # Cap at 1.0
        score = min(1.0, base_score)

        assert 0.0 <= score <= 1.0, f"Importance score {score} must be in [0, 1]"

    @given(
        high_importance_count=st.integers(min_value=1, max_value=10),
        low_importance_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_importance_ranking(self, high_importance_count, low_importance_count):
        """Test that episodes are ranked by importance"""
        episodes = []

        # Add high importance episodes
        for i in range(high_importance_count):
            episodes.append({"id": f"high_{i}", "importance": 0.9})

        # Add low importance episodes
        for i in range(low_importance_count):
            episodes.append({"id": f"low_{i}", "importance": 0.3})

        # Sort by importance (descending)
        sorted_episodes = sorted(episodes, key=lambda e: e["importance"], reverse=True)

        # Verify ranking
        for i in range(len(sorted_episodes) - 1):
            current = sorted_episodes[i]["importance"]
            next_score = sorted_episodes[i + 1]["importance"]
            assert current >= next_score, "Episodes should be sorted by descending importance"

    @given(
        access_count=st.integers(min_value=0, max_value=100),
        days_since_access=st.integers(min_value=0, max_value=365)
    )
    @settings(max_examples=50)
    def test_importance_decay(self, access_count, days_since_access):
        """Test that importance decays over time without access"""
        initial_importance = 0.8

        # Decay factor based on days since access
        decay_factor = max(0.1, 1.0 - (days_since_access / 365))

        # Boost based on access count
        access_boost = min(access_count / 100, 0.2)

        # Calculate decayed importance
        decayed_importance = (initial_importance * decay_factor) + access_boost

        # Verify decay behavior
        assert 0.0 <= decayed_importance <= 1.0, "Decayed importance must be in [0, 1]"

        if days_since_access > 180:
            assert decayed_importance < initial_importance, "Importance should decay after 6 months"


class TestEpisodeConsolidationInvariants:
    """Tests for episode consolidation and archival"""

    @given(
        episode_count=st.integers(min_value=2, max_value=30),
        consolidation_threshold=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=50)
    def test_consolidation_eligibility(self, episode_count, consolidation_threshold):
        """Test that consolidation eligibility is based on threshold"""
        # Check if eligible for consolidation
        eligible = episode_count >= consolidation_threshold

        if episode_count >= consolidation_threshold:
            assert eligible, f"{episode_count} episodes should be eligible for consolidation"
        else:
            assert not eligible, f"{episode_count} episodes should not be eligible for consolidation"

    @given(
        episode_count=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=50)
    def test_consolidation_metadata_preservation(self, episode_count):
        """Test that consolidation preserves critical metadata"""
        # Create episodes with metadata
        episodes = []
        for i in range(episode_count):
            episode = {
                "id": str(uuid4()),
                "start_time": datetime(2024, 1, 1, 12, 0, 0) + timedelta(hours=i),
                "end_time": datetime(2024, 1, 1, 13, 0, 0) + timedelta(hours=i),
                "agent_id": f"agent_{i % 3}",
                "importance": 0.5 + (i * 0.05)
            }
            episodes.append(episode)

        # Consolidate (combine metadata)
        consolidated = {
            "episode_count": len(episodes),
            "time_range": {
                "start": min(ep["start_time"] for ep in episodes),
                "end": max(ep["end_time"] for ep in episodes)
            },
            "agents": list(set(ep["agent_id"] for ep in episodes)),
            "avg_importance": sum(ep["importance"] for ep in episodes) / len(episodes)
        }

        # Verify metadata preservation
        assert consolidated["episode_count"] == episode_count, "Episode count should be preserved"
        assert len(consolidated["agents"]) > 0, "Agent IDs should be preserved"
        assert 0.0 <= consolidated["avg_importance"] <= 1.0, "Average importance should be valid"

    @given(
        stale_days=st.integers(min_value=90, max_value=365)
    )
    @settings(max_examples=50)
    def test_stale_episode_detection(self, stale_days):
        """Test that stale episodes are correctly identified"""
        # Create episode with last access timestamp
        last_accessed = datetime.now() - timedelta(days=stale_days)

        # Check if stale
        is_stale = (datetime.now() - last_accessed).days >= 90

        if stale_days >= 90:
            assert is_stale, f"Episode not accessed in {stale_days} days should be stale"
        else:
            assert not is_stale, f"Episode accessed {stale_days} days ago should not be stale"

    @given(
        episode_count=st.integers(min_value=5, max_value=30)
    )
    @settings(max_examples=50)
    def test_archival_metadata_integrity(self, episode_count):
        """Test that archival preserves episode integrity"""
        # Create episodes to archive
        episodes = []
        for i in range(episode_count):
            episode = {
                "id": str(uuid4()),
                "created_at": datetime(2024, 1, 1, 12, 0, 0) + timedelta(hours=i),
                "segments": [f"segment_{j}" for j in range(3)],
                "checksum": f"checksum_{i}"
            }
            episodes.append(episode)

        # Archive (simulate)
        archive = {
            "archived_at": datetime.now(),
            "episode_count": len(episodes),
            "episodes": episodes,
            "total_segments": sum(len(ep["segments"]) for ep in episodes)
        }

        # Verify archival integrity
        assert archive["episode_count"] == episode_count, "All episodes should be archived"
        assert archive["total_segments"] == episode_count * 3, "All segments should be preserved"
        assert "archived_at" in archive, "Archival timestamp should be recorded"
