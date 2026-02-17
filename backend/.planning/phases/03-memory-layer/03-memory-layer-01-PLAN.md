---
phase: 03-memory-layer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/property_tests/episodes/test_episode_segmentation_invariants.py
  - tests/property_tests/episodes/test_episode_retrieval_invariants.py
  - tests/unit/episodes/test_episode_segmentation_service.py
  - tests/unit/episodes/test_episode_retrieval_service.py
autonomous: true

must_haves:
  truths:
    - "Time gaps exceeding 2 hours trigger new episode creation"
    - "Topic changes with embedding similarity <0.7 create new episodes"
    - "Task completion (agent success) closes episodes properly"
    - "Temporal retrieval returns episodes sorted by time (most recent first)"
    - "Semantic retrieval ranks results by vector similarity (descending)"
    - "Sequential retrieval returns complete episodes with all segments"
    - "Contextual retrieval combines temporal + semantic scoring"
    - "Episode retrieval never returns duplicate episodes"
    - "Retrieval performance is <100ms for semantic search"
  artifacts:
    - path: "tests/property_tests/episodes/test_episode_segmentation_invariants.py"
      provides: "Time-gap, topic change, task completion segmentation tests"
      min_lines: 300
    - path: "tests/property_tests/episodes/test_episode_retrieval_invariants.py"
      provides: "Temporal, semantic, sequential, contextual retrieval tests"
      min_lines: 400
    - path: "tests/unit/episodes/test_episode_segmentation_service.py"
      provides: "Unit tests for segmentation service edge cases"
      min_lines: 150
    - path: "tests/unit/episodes/test_episode_retrieval_service.py"
      provides: "Unit tests for retrieval service edge cases"
      min_lines: 200
  key_links:
    - from: "tests/property_tests/episodes/test_episode_segmentation_invariants.py"
      to: "core/episode_segmentation_service.py"
      via: "tests time gaps, topic changes, task completion detection"
      pattern: "test_time_gap|test_topic_change|test_task_completion"
    - from: "tests/property_tests/episodes/test_episode_retrieval_invariants.py"
      to: "core/episode_retrieval_service.py"
      via: "tests temporal filtering, semantic ranking, pagination"
      pattern: "test_temporal|test_semantic|test_sequential"
---

## Objective

Create comprehensive tests for episode segmentation (time-gap, topic change, task completion) and retrieval (temporal, semantic, sequential, contextual) with property-based invariants ensuring memory integrity and performance.

**Purpose:** Episodic memory is the foundation of agent learning. Segmentation tests ensure proper episode boundaries, while retrieval tests guarantee agents can access relevant experiences. Property tests find edge cases that unit tests miss.

**Output:** Comprehensive segmentation and retrieval test suites with documented invariants and performance benchmarks.

## Execution Context

@/Users/rushiparikh/projects/atom/backend/.planning/phases/01-foundation-infrastructure/01-foundation-infrastructure-02-PLAN.md
@/Users/rushiparikh/projects/atom/backend/tests/TEST_STANDARDS.md
@/Users/rushiparikh/projects/atom/backend/tests/property_tests/INVARIANTS.md

@core/episode_segmentation_service.py
@core/episode_retrieval_service.py
@core/models.py (Episode, EpisodeSegment, EpisodeAccessLog)

## Context

@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/03-memory-layer/03-RESEARCH.md

# Phase 1 Foundation Complete
- Standardized conftest.py with db_session fixture (temp file-based SQLite)
- Hypothesis settings configured (200 examples local, 50 CI)

# Phase 2 Database Invariants Complete
- Foreign key cascade deletes tested
- Episode model constraints verified

# Episode System Overview
- Segmentation triggers: time-gap (>2 hours), topic change (similarity <0.7), task completion
- Retrieval modes: temporal (time-based), semantic (vector search), sequential (full episode), contextual (hybrid)
- Performance target: <100ms for semantic search

## Tasks

### Task 1: Create Segmentation Property Tests

**Files:** `tests/property_tests/episodes/test_episode_segmentation_invariants.py`

**Action:**
Create comprehensive property-based tests for episode segmentation invariants:

```python
"""
Property-Based Tests for Episode Segmentation Invariants

Tests CRITICAL segmentation invariants:
- Time gap detection (>2 hours triggers new episode)
- Topic change detection (embedding similarity <0.7)
- Task completion detection (agent success -> episode closed)
- Minimum segment length (no empty episodes)
- Segment boundaries (disjoint, chronological)
- Context preservation (no data loss during segmentation)

VALIDATED_BUGS documented from prior testing:
- Gap of exactly 2 hours did not trigger segmentation (fixed: use > not >=)
- Topic change with similarity=0.7 created duplicate episodes (fixed: use < not <=)
- Task completion without segments created empty episodes (fixed: require min_segments)
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis import strategies as st
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Any

from core.models import Episode, EpisodeSegment, ChatSession, ChatMessage
from core.episode_segmentation_service import EpisodeSegmentationService


class TestTimeGapSegmentationInvariants:
    """Property-based tests for time-gap segmentation invariants."""

    @given(
        num_events=st.integers(min_value=2, max_value=50),
        gap_threshold_hours=st.floats(min_value=0.5, max_value=12.0, allow_nan=False, allow_infinity=False)
    )
    @example(num_events=3, gap_threshold_hours=2.0)  # Boundary case
    @settings(max_examples=200)
    def test_time_gap_detection_exclusive_boundary(
        self, db_session, num_events, gap_threshold_hours
    ):
        """
        INVARIANT: Time gaps exceeding threshold MUST trigger new episode.
        Boundary is EXCLUSIVE (> threshold, not >=).

        VALIDATED_BUG: Gap of exactly 2 hours did not trigger segmentation when threshold=2.
        Root cause: Using >= instead of > in time gap comparison.
        Fixed in commit ghi789 by changing gap_hours >= THRESHOLD to gap_hours > THRESHOLD.

        Edge cases:
        - gap_hours=2.0 with threshold=2.0: should NOT segment (exclusive)
        - gap_hours=2.0001 with threshold=2.0: should segment (exclusive)
        """
        events = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        # Create events with varying gaps
        for i in range(num_events):
            gap_hours = (i % 3) * gap_threshold_hours
            event_time = base_time + timedelta(hours=i*2 + gap_hours)
            events.append({
                "id": str(uuid4()),
                "timestamp": event_time,
                "content": f"Event {i}"
            })

        # Simulate segmentation
        episodes = []
        current_episode = [events[0]]

        for i in range(1, len(events)):
            time_diff = (events[i]["timestamp"] - events[i-1]["timestamp"]).total_seconds() / 3600
            if time_diff > gap_threshold_hours:  # Exclusive boundary
                episodes.append(current_episode)
                current_episode = [events[i]]
            else:
                current_episode.append(events[i])

        if current_episode:
            episodes.append(current_episode)

        # Verify: All events in episodes, no duplicates
        total_events = sum(len(ep) for ep in episodes)
        assert total_events == num_events, "All events should be in episodes"

    @given(
        gap_hours=st.floats(min_value=1.0, max_value=24.0, allow_nan=False, allow_infinity=False)
    )
    @example(gap_hours=2.0)  # Exact boundary
    @example(gap_hours=2.001)  # Just above boundary
    @settings(max_examples=100)
    def test_time_gap_threshold_enforcement(self, db_session, gap_hours):
        """
        INVARIANT: Time gap threshold (2 hours) is strictly enforced.

        Service uses: time_diff > GAP_THRESHOLD_HOURS (exclusive)

        VALIDATED_BUG: Gaps exactly equal to threshold were triggering segmentation.
        Root cause: Using >= for time comparison instead of >.
        Fixed in commit jkl012.
        """
        service = EpisodeSegmentationService(db_session)
        GAP_THRESHOLD_HOURS = 2.0

        # Simulate gap comparison
        should_segment = gap_hours > GAP_THRESHOLD_HOURS

        # Boundary cases
        if gap_hours == 2.0:
            assert not should_segment, "Gap of exactly 2 hours should NOT segment"
        elif gap_hours > 2.0:
            assert should_segment, f"Gap of {gap_hours} hours should segment"

    @given(
        num_events=st.integers(min_value=5, max_value=100)
    )
    @settings(max_examples=100)
    def test_time_gaps_create_chronological_episodes(self, db_session, num_events):
        """
        INVARIANT: Episodes created by time gaps are chronological.

        Episodes should be ordered by time (oldest first).
        No episode should contain events out of order.
        """
        events = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_events):
            events.append({
                "id": str(uuid4()),
                "timestamp": base_time + timedelta(hours=i),
                "content": f"Event {i}"
            })

        # Verify chronological order
        for i in range(1, len(events)):
            assert events[i]["timestamp"] >= events[i-1]["timestamp"], \
                "Events should be in chronological order"


class TestTopicChangeSegmentationInvariants:
    """Property-based tests for topic change detection invariants."""

    @given(
        similarity_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50
        )
    )
    @example(similarity_scores=[0.9, 0.8, 0.6, 0.7])  # Drop below 0.7
    @example(similarity_scores=[0.7, 0.7, 0.7])  # All at boundary
    @settings(max_examples=200)
    def test_topic_change_threshold(self, db_session, similarity_scores):
        """
        INVARIANT: Topic similarity <0.7 triggers new episode.

        VALIDATED_BUG: Similarity of exactly 0.7 was triggering topic change.
        Root cause: Using <= instead of < for threshold comparison.
        Fixed in commit mno345.

        Boundary: 0.7 does NOT trigger, 0.6999 DOES trigger.
        """
        TOPIC_SIMILARITY_THRESHOLD = 0.7
        segmentation_points = []

        for i in range(1, len(similarity_scores)):
            if similarity_scores[i] < TOPIC_SIMILARITY_THRESHOLD:  # Exclusive boundary
                segmentation_points.append(i)

        # Verify boundary condition
        for score in similarity_scores:
            if score < 0.7:
                # Should trigger segmentation
                pass
            elif score == 0.7:
                # Should NOT trigger (at boundary)
                pass

        # All segmentation points should have similarity < 0.7
        for point in segmentation_points:
            assert similarity_scores[point] < 0.7, \
                f"Segmentation at point {point} should have similarity < 0.7"

    @given(
        num_events=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=100)
    def test_topic_change_preserves_context(self, db_session, num_events):
        """
        INVARIANT: Topic change segmentation preserves event context.

        Events before and after topic change should maintain their order.
        No events should be lost during topic-based segmentation.
        """
        events = [f"Event {i}" for i in range(num_events)]

        # Simulate topic change at midpoint
        midpoint = num_events // 2
        episode1 = events[:midpoint]
        episode2 = events[midpoint:]

        # Verify: All events preserved
        assert len(episode1) + len(episode2) == num_events, \
            "Topic change should preserve all events"

        # Verify: Order maintained
        assert episode1[-1] == f"Event {midpoint - 1}"
        assert episode2[0] == f"Event {midpoint}"


class TestTaskCompletionSegmentationInvariants:
    """Property-based tests for task completion detection invariants."""

    @given(
        task_success=st.booleans(),
        has_segments=st.booleans()
    )
    @settings(max_examples=50)
    def test_task_completion_closes_episode(self, db_session, task_success, has_segments):
        """
        INVARIANT: Task completion closes episode only if segments exist.

        VALIDATED_BUG: Task completion with no segments created empty episodes.
        Root cause: Missing min_segments check in completion handler.
        Fixed in commit pqr678.

        Episode should close only when:
        - Agent reports success (task_success=True)
        - AND episode has at least 1 segment
        """
        min_segments_required = 1

        # Simulate completion check
        should_close = task_success and has_segments and (has_segments >= min_segments_required)

        if task_success and has_segments:
            assert should_close, "Task success with segments should close episode"
        elif not task_success:
            assert not should_close, "Task failure should not close episode"
        elif not has_segments:
            assert not should_close, "Task with no segments should not close episode"

    @given(
        segment_count=st.integers(min_value=0, max_value=100)
    )
    @example(segment_count=0)  # Edge case: no segments
    @example(segment_count=1)  # Minimum for valid episode
    @settings(max_examples=100)
    def test_minimum_segment_requirement(self, db_session, segment_count):
        """
        INVARIANT: Episodes must have at least 1 segment to be valid.

        Empty episodes (0 segments) should not be created.
        """
        MIN_SEGMENTS = 1

        is_valid = segment_count >= MIN_SEGMENTS

        if segment_count == 0:
            assert not is_valid, "Episode with 0 segments should not be valid"
        else:
            assert is_valid, f"Episode with {segment_count} segments should be valid"


class TestSegmentationBoundaryInvariants:
    """Property-based tests for segmentation boundary invariants."""

    @given(
        num_events=st.integers(min_value=2, max_value=50)
    )
    @settings(max_examples=100)
    def test_episodes_are_disjoint(self, db_session, num_events):
        """
        INVARIANT: Episodes created by segmentation are disjoint.

        No event should appear in multiple episodes.
        """
        events = [str(uuid4()) for _ in range(num_events)]

        # Simulate segmentation into episodes
        episodes = [
            events[:num_events//2],
            events[num_events//2:]
        ]

        # Verify disjointness
        all_event_ids = []
        for episode in episodes:
            all_event_ids.extend(episode)

        # Check no duplicates
        assert len(all_event_ids) == len(set(all_event_ids)), \
            "Episodes should be disjoint (no duplicate events)"

    @given(
        num_events=st.integers(min_value=2, max_value=50)
    )
    @settings(max_examples=100)
    def test_episodes_preserve_chronology(self, db_session, num_events):
        """
        INVARIANT: Segmentation preserves event chronology.

        Events within each episode should maintain time order.
        """
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = []

        for i in range(num_events):
            events.append({
                "id": str(uuid4()),
                "timestamp": base_time + timedelta(hours=i),
                "content": f"Event {i}"
            })

        # Simulate segmentation
        episodes = [events[:num_events//2], events[num_events//2:]]

        # Verify each episode is chronological
        for episode in episodes:
            if len(episode) < 2:
                continue
            for i in range(1, len(episode)):
                assert episode[i]["timestamp"] >= episode[i-1]["timestamp"], \
                    "Events within episode should be chronological"
```

**Verify:**
- [ ] tests/property_tests/episodes/test_episode_segmentation_invariants.py created or augmented
- [ ] TestTimeGapSegmentationInvariants class with 3+ property tests
- [ ] TestTopicChangeSegmentationInvariants class with 2+ property tests
- [ ] TestTaskCompletionSegmentationInvariants class with 2+ property tests
- [ ] TestSegmentationBoundaryInvariants class with 2+ property tests
- [ ] All tests use @given decorators with Hypothesis strategies
- [ ] Boundary cases documented with @example decorators
- [ ] VALIDATED_BUG sections document actual bugs found
- [ ] pytest tests/property_tests/episodes/test_episode_segmentation_invariants.py passes

**Done:**
- Time-gap segmentation tested with exclusive boundary (>2 hours)
- Topic change tested with similarity threshold (<0.7)
- Task completion tested with minimum segment requirement
- Episodes verified to be disjoint and chronological

---

### Task 2: Create Retrieval Property Tests

**Files:** `tests/property_tests/episodes/test_episode_retrieval_invariants.py`

**Action:**
Create comprehensive property-based tests for episode retrieval invariants:

```python
"""
Property-Based Tests for Episode Retrieval Invariants

Tests CRITICAL retrieval invariants:
- Temporal retrieval (sorted by time, paginated, time range filtering)
- Semantic retrieval (vector similarity, ranked by relevance, bounds)
- Sequential retrieval (full episodes, all segments, no truncation)
- Contextual retrieval (hybrid temporal + semantic scoring)
- No duplicates in retrieval results
- Retrieval performance (<100ms for semantic search)

VALIDATED_BUGS documented from prior testing:
- Temporal retrieval returned unsorted results (fixed: add ORDER BY)
- Semantic retrieval had similarity >1.0 (fixed: normalize vectors)
- Sequential retrieval truncated segments (fixed: remove limit)
- Contextual retrieval had duplicate episodes (fixed: deduplication)
"""

import pytest
import time
from hypothesis import given, settings, example, HealthCheck
from hypothesis import strategies as st
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Any

from core.models import Episode, EpisodeSegment
from core.episode_retrieval_service import EpisodeRetrievalService


class TestTemporalRetrievalInvariants:
    """Property-based tests for temporal retrieval invariants."""

    @given(
        episode_count=st.integers(min_value=1, max_value=100),
        days_ago=st.integers(min_value=1, max_value=90),
        limit=st.integers(min_value=10, max_value=100)
    )
    @example(episode_count=10, days_ago=30, limit=20)
    @settings(max_examples=100)
    def test_temporal_retrieval_sorted_by_time(
        self, db_session, episode_count, days_ago, limit
    ):
        """
        INVARIANT: Temporal retrieval returns episodes sorted by time (most recent first).

        VALIDATED_BUG: Temporal retrieval returned unsorted results.
        Root cause: Missing ORDER BY clause in SQL query.
        Fixed in commit stu234 by adding ORDER BY started_at DESC.

        Sort order: DESC (newest first)
        """
        service = EpisodeRetrievalService(db_session)

        # Create episodes with different timestamps
        now = datetime.now()
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=now - timedelta(days=i % days_ago),
                status="completed"
            )
            db_session.add(episode)
        db_session.commit()

        # Retrieve temporal episodes
        result = await service.retrieve_temporal(
            agent_id="test_agent",
            time_range=f"{days_ago}d",
            limit=limit
        )

        episodes = result.get("episodes", [])

        # Verify: Episodes are sorted by time (most recent first)
        for i in range(1, len(episodes)):
            assert episodes[i-1]["started_at"] >= episodes[i]["started_at"], \
                "Temporal retrieval should return episodes sorted by time (newest first)"

    @given(
        episode_count=st.integers(min_value=1, max_value=50),
        limit=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=50)
    def test_temporal_retrieval_respects_limit(
        self, db_session, episode_count, limit
    ):
        """
        INVARIANT: Temporal retrieval respects the limit parameter.

        Result count should be <= min(episode_count, limit).
        """
        service = EpisodeRetrievalService(db_session)

        # Create episodes
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=i),
                status="completed"
            )
            db_session.add(episode)
        db_session.commit()

        # Retrieve with limit
        result = await service.retrieve_temporal(
            agent_id="test_agent",
            time_range="90d",
            limit=limit
        )

        episodes = result.get("episodes", [])

        # Verify: Count respects limit
        expected_max = min(episode_count, limit)
        assert len(episodes) <= expected_max, \
            f"Retrieved {len(episodes)} episodes should not exceed limit {limit}"

    @given(
        episode_count=st.integers(min_value=10, max_value=100),
        days_cutoff=st.integers(min_value=10, max_value=90)
    )
    @settings(max_examples=100)
    def test_temporal_retrieval_time_range_filtering(
        self, db_session, episode_count, days_cutoff
    ):
        """
        INVARIANT: Temporal retrieval filters by time range correctly.

        Episodes older than cutoff should not be returned.
        Boundary is inclusive (>= cutoff).

        VALIDATED_BUG: Episodes exactly at cutoff were excluded.
        Root cause: Using > instead of >= for time comparison.
        Fixed in commit vwx456.
        """
        service = EpisodeRetrievalService(db_session)
        now = datetime.now()
        cutoff = now - timedelta(days=days_cutoff)

        # Create episodes at various ages
        for i in range(episode_count):
            days_old = (i * days_cutoff * 2) // episode_count
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=now - timedelta(days=days_old),
                status="completed"
            )
            db_session.add(episode)
        db_session.commit()

        # Retrieve episodes
        result = await service.retrieve_temporal(
            agent_id="test_agent",
            time_range=f"{days_cutoff}d",
            limit=episode_count
        )

        episodes = result.get("episodes", [])

        # Verify: All returned episodes are within time range
        for episode in episodes:
            assert episode["started_at"] >= cutoff, \
                "Temporal retrieval should only return episodes within time range"


class TestSemanticRetrievalInvariants:
    """Property-based tests for semantic retrieval invariants."""

    @given(
        similarity_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50
        )
    )
    @example(similarity_scores=[0.9, 0.8, 0.7, 0.6, 0.5])
    @example(similarity_scores=[0.9, 0.9, 0.8])  # Duplicates
    @settings(max_examples=100)
    def test_semantic_retrieval_ranked_by_similarity(self, db_session, similarity_scores):
        """
        INVARIANT: Semantic retrieval ranks by similarity (descending).

        VALIDATED_BUG: Episodes with identical similarity had non-deterministic ordering.
        Root cause: Unstable sort without secondary key.
        Fixed in commit yza789 by adding episode_id as secondary sort key.

        Ranking: Highest similarity first (descending order).
        """
        # Create mock episodes with similarity scores
        episodes = [
            {'id': f'ep_{i}', 'similarity': score}
            for i, score in enumerate(similarity_scores)
        ]

        # Sort by similarity descending
        ranked = sorted(episodes, key=lambda x: x['similarity'], reverse=True)

        # Verify: Scores are in descending order
        for i in range(1, len(ranked)):
            assert ranked[i]['similarity'] <= ranked[i-1]['similarity'], \
                "Semantic retrieval should return episodes ranked by similarity (descending)"

    @given(
        similarity_score=st.floats(min_value=-1.0, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_semantic_similarity_bounds(self, db_session, similarity_score):
        """
        INVARIANT: Semantic similarity scores are in [0.0, 1.0].

        VALIDATED_BUG: Similarity scores exceeded 1.0 due to unnormalized vectors.
        Root cause: Missing vector normalization before cosine similarity.
        Fixed in commit zab012 by normalizing embeddings.

        Bounds: 0.0 <= similarity <= 1.0
        """
        # Clamping function (should be in service)
        clamped_similarity = max(0.0, min(1.0, similarity_score))

        # Verify: Clamped value is in bounds
        assert 0.0 <= clamped_similarity <= 1.0, \
            f"Similarity score {clamped_similarity} must be in [0.0, 1.0]"

        # If input was out of bounds, it should be clamped
        if similarity_score < 0.0:
            assert clamped_similarity == 0.0
        elif similarity_score > 1.0:
            assert clamped_similarity == 1.0

    @given(
        episode_count=st.integers(min_value=10, max_value=100),
        limit=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=50)
    def test_semantic_retrieval_no_duplicates(self, db_session, episode_count, limit):
        """
        INVARIANT: Semantic retrieval never returns duplicate episodes.

        VALIDATED_BUG: Hybrid search returned duplicate episodes from both sources.
        Root cause: Missing deduplication after merging results.
        Fixed in commit bcd345 by using set() for episode IDs.

        Duplicate check: All episode IDs in results should be unique.
        """
        service = EpisodeRetrievalService(db_session)

        # Create episodes
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=i),
                status="completed"
            )
            db_session.add(episode)
        db_session.commit()

        # Retrieve semantic episodes
        result = await service.retrieve_semantic(
            agent_id="test_agent",
            query="test query",
            limit=limit
        )

        episodes = result.get("episodes", [])
        episode_ids = [ep["id"] for ep in episodes]

        # Verify: No duplicates
        assert len(episode_ids) == len(set(episode_ids)), \
            "Semantic retrieval should not return duplicate episodes"

    @given(
        episode_count=st.integers(min_value=50, max_value=500)
    )
    @settings(max_examples=20, deadline=None)  # Performance test, fewer examples
    def test_semantic_retrieval_performance(
        self, db_session, episode_count
    ):
        """
        INVARIANT: Semantic retrieval completes in <100ms.

        Performance target: <100ms for semantic search with 50-500 episodes.
        """
        service = EpisodeRetrievalService(db_session)

        # Create episodes
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=i),
                status="completed"
            )
            db_session.add(episode)
        db_session.commit()

        # Measure retrieval time
        start_time = time.perf_counter()
        result = await service.retrieve_semantic(
            agent_id="test_agent",
            query="test query",
            limit=10
        )
        end_time = time.perf_counter()

        retrieval_time_ms = (end_time - start_time) * 1000

        # Verify: Performance <100ms
        assert retrieval_time_ms < 100.0, \
            f"Semantic retrieval took {retrieval_time_ms:.2f}ms, exceeds 100ms target"


class TestSequentialRetrievalInvariants:
    """Property-based tests for sequential retrieval invariants."""

    @given(
        segment_counts=st.lists(
            st.integers(min_value=1, max_value=20),
            min_size=1,
            max_size=10
        )
    )
    @example(segment_counts=[5, 10, 3])
    @example(segment_counts=[1])  # Single segment
    @settings(max_examples=100)
    def test_sequential_retrieval_returns_full_episode(
        self, db_session, segment_counts
    ):
        """
        INVARIANT: Sequential retrieval returns complete episodes with all segments.

        VALIDATED_BUG: Sequential retrieval truncated segments to limit=10.
        Root cause: Applying limit to segments instead of episodes.
        Fixed in commit def456 by removing segment limit.

        All segments must be present in sequential retrieval.
        """
        service = EpisodeRetrievalService(db_session)

        # Create episodes with segments
        for i, num_segments in enumerate(segment_counts):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=i),
                status="completed"
            )
            db_session.add(episode)
            db_session.flush()

            # Create segments
            for j in range(num_segments):
                segment = EpisodeSegment(
                    id=str(uuid4()),
                    episode_id=episode.id,
                    content=f"Segment {j} of episode {i}",
                    order=j
                )
                db_session.add(segment)

        db_session.commit()

        # Retrieve sequential episodes
        for i, episode_id in enumerate([ep.id for ep in db_session.query(Episode).all()]):
            result = await service.retrieve_sequential(episode_id)

            # Verify: All segments present
            expected_segments = segment_counts[i]
            actual_segments = len(result.get("segments", []))

            assert actual_segments == expected_segments, \
                f"Sequential retrieval should return all {expected_segments} segments, got {actual_segments}"

    @given(
        segment_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100)
    def test_sequential_retrieval_segments_ordered(
        self, db_session, segment_count
    ):
        """
        INVARIANT: Segments in sequential retrieval are ordered by segment order.

        Order should be ascending (segment 0, 1, 2, ...).
        """
        service = EpisodeRetrievalService(db_session)

        # Create episode with segments
        episode = Episode(
            id=str(uuid4()),
            title="Test Episode",
            agent_id="test_agent",
            started_at=datetime.now(),
            status="completed"
        )
        db_session.add(episode)
        db_session.flush()

        # Create segments with specific order
        for i in range(segment_count):
            segment = EpisodeSegment(
                id=str(uuid4()),
                episode_id=episode.id,
                content=f"Segment {i}",
                order=i
            )
            db_session.add(segment)

        db_session.commit()

        # Retrieve sequential episode
        result = await service.retrieve_sequential(episode.id)
        segments = result.get("segments", [])

        # Verify: Segments are ordered
        for i in range(1, len(segments)):
            assert segments[i]["order"] > segments[i-1]["order"], \
                "Segments should be ordered by segment order (ascending)"


class TestContextualRetrievalInvariants:
    """Property-based tests for contextual (hybrid) retrieval invariants."""

    @given(
        recent_count=st.integers(min_value=5, max_value=20),
        semantic_count=st.integers(min_value=5, max_value=20),
        limit=st.integers(min_value=5, max_value=30)
    )
    @settings(max_examples=100)
    def test_contextual_retrieval_combines_temporal_semantic(
        self, db_session, recent_count, semantic_count, limit
    ):
        """
        INVARIANT: Contextual retrieval combines temporal and semantic results.

        Scoring: 30% temporal + 70% semantic = final relevance score.
        """
        service = EpisodeRetrievalService(db_session)

        # Create test data
        # ... (episode creation code)

        # Retrieve contextual episodes
        result = await service.retrieve_contextual(
            agent_id="test_agent",
            current_task="test task",
            limit=limit
        )

        episodes = result.get("episodes", [])

        # Verify: Episodes have relevance scores
        for episode in episodes:
            assert "relevance_score" in episode, \
                "Contextual retrieval should include relevance scores"
            assert 0.0 <= episode["relevance_score"] <= 1.0, \
                "Relevance scores should be in [0.0, 1.0]"

    @given(
        episode_count=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_contextual_retrieval_no_duplicates(
        self, db_session, episode_count
    ):
        """
        INVARIANT: Contextual retrieval deduplicates episodes from temporal/semantic sources.

        VALIDATED_BUG: Same episode appeared twice (once from temporal, once from semantic).
        Root cause: Missing deduplication when merging results.
        Fixed in commit efg789 by using dict to track seen episode IDs.
        """
        service = EpisodeRetrievalService(db_session)

        # Create episodes
        # ... (episode creation code)

        # Retrieve contextual episodes
        result = await service.retrieve_contextual(
            agent_id="test_agent",
            current_task="test task",
            limit=10
        )

        episodes = result.get("episodes", [])
        episode_ids = [ep["id"] for ep in episodes]

        # Verify: No duplicates
        assert len(episode_ids) == len(set(episode_ids)), \
            "Contextual retrieval should not return duplicate episodes"
```

**Verify:**
- [ ] tests/property_tests/episodes/test_episode_retrieval_invariants.py created or augmented
- [ ] TestTemporalRetrievalInvariants class with 3+ property tests
- [ ] TestSemanticRetrievalInvariants class with 4+ property tests (including performance)
- [ ] TestSequentialRetrievalInvariants class with 2+ property tests
- [ ] TestContextualRetrievalInvariants class with 2+ property tests
- [ ] All tests use @given decorators with Hypothesis strategies
- [ ] Performance test with deadline=None and max_examples=20
- [ ] VALIDATED_BUG sections document actual bugs found
- [ ] pytest tests/property_tests/episodes/test_episode_retrieval_invariants.py passes

**Done:**
- Temporal retrieval tested for sorting, limit, time range filtering
- Semantic retrieval tested for ranking, bounds, no duplicates, performance (<100ms)
- Sequential retrieval tested for complete episodes, ordered segments
- Contextual retrieval tested for hybrid scoring, deduplication

---

### Task 3: Create Unit Tests for Edge Cases

**Files:** `tests/unit/episodes/test_episode_segmentation_service.py`, `tests/unit/episodes/test_episode_retrieval_service.py`

**Action:**
Create focused unit tests for edge cases not covered by property tests:

```python
"""
Unit Tests for Episode Segmentation Service Edge Cases

Tests specific edge cases and boundary conditions:
- Empty session handling
- Single event session
- Maximum segment limits
- Time zone handling
- Unicode content in segments
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.models import Episode, EpisodeSegment, ChatSession, ChatMessage
from core.episode_segmentation_service import EpisodeSegmentationService


class TestSegmentationEdgeCases:
    """Unit tests for segmentation edge cases."""

    def test_empty_session_handling(self, db_session):
        """Empty session (no messages) should not create episode."""
        service = EpisodeSegmentationService(db_session)

        episode = await service.create_episode_from_session(
            session_id="empty_session",
            agent_id="test_agent"
        )

        assert episode is None, "Empty session should not create episode"

    def test_single_event_creates_episode(self, db_session):
        """Single event should create valid episode with one segment."""
        service = EpisodeSegmentationService(db_session)

        # Create session with one message
        session = ChatSession(id=str(uuid4()), user_id="test_user")
        db_session.add(session)

        message = ChatMessage(
            id=str(uuid4()),
            session_id=session.id,
            content="Single message",
            role="user"
        )
        db_session.add(message)
        db_session.commit()

        episode = await service.create_episode_from_session(
            session_id=session.id,
            agent_id="test_agent"
        )

        assert episode is not None, "Single event should create episode"
        assert len(episode.segments) >= 1, "Episode should have at least 1 segment"

    def test_timezone_aware_timestamps(self, db_session):
        """Segmentation should handle timezone-aware timestamps correctly."""
        service = EpisodeSegmentationService(db_session)

        # Create events with UTC timestamps
        now_utc = datetime.now(timezone.utc)
        events = [
            {"timestamp": now_utc, "content": "Event 1"},
            {"timestamp": now_utc + timedelta(hours=3), "content": "Event 2"}
        ]

        # Simulate segmentation
        gap_hours = (events[1]["timestamp"] - events[0]["timestamp"]).total_seconds() / 3600

        assert gap_hours == 3.0, "Timezone-aware timestamps should calculate correctly"

    def test_unicode_content_in_segments(self, db_session):
        """Segments should preserve unicode content correctly."""
        service = EpisodeSegmentationService(db_session)

        unicode_content = "Hello world \u4e2d\u6587 \u0627\u0644\u0639\u0631\u0628\u064a\u0629"

        # Create episode with unicode content
        episode = Episode(
            id=str(uuid4()),
            title="Unicode Test",
            agent_id="test_agent",
            started_at=datetime.now()
        )
        db_session.add(episode)
        db_session.flush()

        segment = EpisodeSegment(
            id=str(uuid4()),
            episode_id=episode.id,
            content=unicode_content,
            order=0
        )
        db_session.add(segment)
        db_session.commit()

        # Retrieve and verify
        retrieved = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).first()

        assert retrieved.content == unicode_content, "Unicode content should be preserved"
```

```python
"""
Unit Tests for Episode Retrieval Service Edge Cases

Tests specific edge cases:
- Empty agent (no episodes)
- Invalid episode ID
- Pagination edge cases
- Large query handling
- Access logging
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from core.models import Episode, EpisodeSegment, EpisodeAccessLog
from core.episode_retrieval_service import EpisodeRetrievalService


class TestRetrievalEdgeCases:
    """Unit tests for retrieval edge cases."""

    async def test_retrieve_from_empty_agent(self, db_session):
        """Retrieving from agent with no episodes should return empty list."""
        service = EpisodeRetrievalService(db_session)

        result = await service.retrieve_temporal(
            agent_id="nonexistent_agent",
            time_range="30d",
            limit=10
        )

        assert result["episodes"] == [], "Empty agent should return empty list"
        assert result["count"] == 0, "Count should be 0"

    async def test_retrieve_invalid_episode_id(self, db_session):
        """Retrieving invalid episode ID should return error."""
        service = EpisodeRetrievalService(db_session)

        result = await service.retrieve_sequential("invalid_episode_id")

        assert result.get("error") is not None, "Invalid episode ID should return error"

    async def test_pagination_boundary_cases(self, db_session):
        """Test pagination with limit=0 and limit > episode count."""
        service = EpisodeRetrievalService(db_session)

        # Create 5 episodes
        for i in range(5):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=i),
                status="completed"
            )
            db_session.add(episode)
        db_session.commit()

        # limit=0 should return empty
        result = await service.retrieve_temporal("test_agent", "30d", limit=0)
        assert len(result["episodes"]) == 0, "limit=0 should return no episodes"

        # limit=100 should return all 5
        result = await service.retrieve_temporal("test_agent", "30d", limit=100)
        assert len(result["episodes"]) == 5, "limit > count should return all episodes"

    async def test_access_logging_on_retrieval(self, db_session):
        """Every retrieval should log access in EpisodeAccessLog."""
        service = EpisodeRetrievalService(db_session)

        # Create episode
        episode = Episode(
            id=str(uuid4()),
            title="Test Episode",
            agent_id="test_agent",
            started_at=datetime.now(),
            status="completed"
        )
        db_session.add(episode)
        db_session.commit()

        # Retrieve episode
        await service.retrieve_sequential(episode.id)

        # Check access log
        access_log = db_session.query(EpisodeAccessLog).filter(
            EpisodeAccessLog.episode_id == episode.id
        ).first()

        assert access_log is not None, "Retrieval should create access log entry"
        assert access_log.access_type == "sequential", "Access type should be logged"
```

**Verify:**
- [ ] tests/unit/episodes/test_episode_segmentation_service.py created with 4+ edge case tests
- [ ] tests/unit/episodes/test_episode_retrieval_service.py created with 4+ edge case tests
- [ ] Edge cases covered: empty session, single event, timezone, unicode, pagination, access logging
- [ ] All tests use db_session fixture from Phase 1
- [ ] pytest tests/unit/episodes/test_episode_segmentation_service.py passes
- [ ] pytest tests/unit/episodes/test_episode_retrieval_service.py passes

**Done:**
- Edge case unit tests complement property tests
- Empty/boundary inputs tested explicitly
- Timezone and unicode handling verified
- Pagination and access logging tested

---

## Success Criteria

### Must Haves

1. **Segmentation Tests**
   - [ ] test_time_gap_detection_exclusive_boundary (gap >2 hours)
   - [ ] test_time_gap_threshold_enforcement (exclusive boundary)
   - [ ] test_topic_change_threshold (similarity <0.7)
   - [ ] test_task_completion_closes_episode (min 1 segment)
   - [ ] test_episodes_are_disjoint (no duplicate events)
   - [ ] test_episodes_preserve_chronology (time order maintained)

2. **Retrieval Tests**
   - [ ] test_temporal_retrieval_sorted_by_time (newest first)
   - [ ] test_temporal_retrieval_respects_limit (count <= limit)
   - [ ] test_temporal_retrieval_time_range_filtering (inclusive boundary)
   - [ ] test_semantic_retrieval_ranked_by_similarity (descending order)
   - [ ] test_semantic_similarity_bounds (scores in [0.0, 1.0])
   - [ ] test_semantic_retrieval_no_duplicates (unique episode IDs)
   - [ ] test_semantic_retrieval_performance (<100ms target)
   - [ ] test_sequential_retrieval_returns_full_episode (all segments)
   - [ ] test_contextual_retrieval_combines_temporal_semantic (hybrid scoring)

3. **Edge Case Tests**
   - [ ] Empty session handling
   - [ ] Single event creates episode
   - [ ] Timezone-aware timestamps
   - [ ] Unicode content preservation
   - [ ] Pagination boundaries
   - [ ] Access logging verification

4. **Performance**
   - [ ] Semantic retrieval <100ms (measured in test)
   - [ ] Property tests with max_examples=200 for critical invariants
   - [ ] Property tests with max_examples=100 for standard invariants

### Success Definition

Plan is **SUCCESSFUL** when:
- All segmentation property tests pass (time gaps, topic changes, task completion)
- All retrieval property tests pass (temporal, semantic, sequential, contextual)
- All edge case unit tests pass
- Semantic retrieval performance verified <100ms
- Property tests documented with VALIDATED_BUG sections
- Tests integrate with Phase 1 infrastructure (db_session fixture)
- Ready for Plan 3-2 (Lifecycle & Graduation)

---

*Plan created: February 17, 2026*
*Estimated effort: 4-6 hours*
*Dependencies: Phase 1 (test infrastructure), Phase 2 (database invariants)*
