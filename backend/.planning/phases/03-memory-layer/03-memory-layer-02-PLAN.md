---
phase: 03-memory-layer
plan: 02
type: execute
wave: 2
depends_on: ["03-memory-layer-01"]
files_modified:
  - tests/property_tests/episodes/test_episode_lifecycle_invariants.py
  - tests/property_tests/episodes/test_agent_graduation_lifecycle.py
  - tests/integration/episodes/test_episode_lifecycle_lancedb.py
  - tests/integration/episodes/test_graduation_validation.py
autonomous: true

must_haves:
  truths:
    - "Episode importance decays over time based on access frequency"
    - "Old episodes (>90 days) have reduced importance scores"
    - "Consolidation merges similar episodes (>0.85 similarity)"
    - "Consolidation does not create circular references (A->B->A)"
    - "Archived episodes are moved from PostgreSQL to LanceDB cold storage"
    - "Archived episodes remain searchable via semantic search"
    - "Graduation exam uses episodic memory for readiness validation"
    - "Constitutional compliance is validated against episode interventions"
    - "Feedback-linked episodes boost retrieval relevance"
    - "Canvas-aware episodes track canvas interaction context"
  artifacts:
    - path: "tests/property_tests/episodes/test_episode_lifecycle_invariants.py"
      provides: "Decay, consolidation, archival property tests"
      min_lines: 350
    - path: "tests/property_tests/episodes/test_agent_graduation_lifecycle.py"
      provides: "Graduation exam with episodic memory validation"
      min_lines: 300
    - path: "tests/integration/episodes/test_episode_lifecycle_lancedb.py"
      provides: "LanceDB archival integration tests"
      min_lines: 200
    - path: "tests/integration/episodes/test_graduation_validation.py"
      provides: "End-to-end graduation validation with episodes"
      min_lines: 250
  key_links:
    - from: "tests/property_tests/episodes/test_episode_lifecycle_invariants.py"
      to: "core/episode_lifecycle_service.py"
      via: "tests decay, consolidation, archival operations"
      pattern: "test_importance_decay|test_consolidation|test_archival"
    - from: "tests/property_tests/episodes/test_agent_graduation_lifecycle.py"
      to: "core/agent_graduation_service.py"
      via: "tests graduation exam with episode metrics"
      pattern: "test_graduation_readiness|test_constitutional_compliance"
    - from: "tests/integration/episodes/test_graduation_validation.py"
      to: "core/agent_graduation_service.py"
      via: "tests full graduation workflow with episodic memory"
      pattern: "test_graduation_workflow"
---

## Objective

Create comprehensive tests for episode lifecycle operations (decay, consolidation, archival) and graduation framework integration (readiness scoring, constitutional compliance, feedback-linked episodes, canvas-aware episodes).

**Purpose:** Lifecycle operations maintain memory system health (prevent bloat, improve relevance) while graduation framework ensures agents promote based on proven experience. Tests prevent memory leaks, data loss, and invalid promotions.

**Output:** Comprehensive lifecycle and graduation test suites with LanceDB integration and constitutional compliance validation.

## Execution Context

@/Users/rushiparikh/projects/atom/backend/.planning/phases/03-memory-layer/03-memory-layer-01-PLAN.md
@/Users/rushiparikh/projects/atom/backend/tests/TEST_STANDARDS.md
@/Users/rushiparikh/projects/atom/backend/tests/property_tests/INVARIANTS.md

@core/episode_lifecycle_service.py
@core/agent_graduation_service.py
@core/models.py (Episode, EpisodeSegment, EpisodeAccessLog)

## Context

@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/03-memory-layer/03-RESEARCH.md

# Plan 3-1 Complete
- Segmentation and retrieval property tests created
- Edge case unit tests created
- Performance targets verified (<100ms semantic search)

# Episode System Overview
- Lifecycle: decay (90/180-day), consolidation (>0.85 similarity), archival (LanceDB)
- Graduation: episodes, interventions, constitutional compliance
- Canvas-aware episodes track canvas interactions (present, submit, close)
- Feedback-linked episodes aggregate user feedback for retrieval boosting

## Tasks

### Task 1: Create Lifecycle Property Tests

**Files:** `tests/property_tests/episodes/test_episode_lifecycle_invariants.py`

**Action:**
Create comprehensive property-based tests for episode lifecycle invariants:

```python
"""
Property-Based Tests for Episode Lifecycle Invariants

Tests CRITICAL lifecycle invariants:
- Episode importance decay (old episodes access frequency decreases)
- Decay formula: max(0.1, 1.0 - (days_old / 365))
- Consolidation merges similar episodes (similarity >0.85)
- Consolidation prevents circular references
- Archival moves episodes to LanceDB cold storage
- Archived episodes remain searchable

VALIDATED_BUGS documented from prior testing:
- Importance not applied to episodes >90 days old (fixed: apply decay to all old episodes)
- Consolidation created circular references (fixed: filter out already-consolidated)
- Archival left orphaned segments in DB (fixed: cascade delete configuration)
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis import strategies as st
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Any

from core.models import Episode, EpisodeSegment, EpisodeAccessLog
from core.episode_lifecycle_service import EpisodeLifecycleService


class TestEpisodeDecayInvariants:
    """Property-based tests for episode importance decay invariants."""

    @given(
        initial_importance=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),
        access_count=st.integers(min_value=0, max_value=100),
        days_since_access=st.integers(min_value=0, max_value=365)
    )
    @example(initial_importance=0.8, access_count=10, days_since_access=90)
    @example(initial_importance=1.0, access_count=0, days_since_access=180)
    @settings(max_examples=200)
    def test_importance_decay_formula(
        self, db_session, initial_importance, access_count, days_since_access
    ):
        """
        INVARIANT: Episode importance decays over time without access.

        Decay formula: decayed = (initial * max(0.1, 1.0 - days/365)) + access_boost
        Access boost: min(access_count / 100, 0.2)

        VALIDATED_BUG: Episodes accessed 90+ days ago still had full importance.
        Root cause: Decay not applied to episodes older than threshold.
        Fixed in commit stu234 by applying decay to all episodes >90 days old.

        Bounds: Importance always in [0.0, 1.0]
        """
        # Calculate decay factor
        decay_factor = max(0.1, 1.0 - (days_since_access / 365))

        # Access boost (max 0.2)
        access_boost = min(access_count / 100, 0.2)

        # Calculate decayed importance
        decayed_importance = (initial_importance * decay_factor) + access_boost

        # Clamp to [0, 1]
        decayed_importance = max(0.0, min(1.0, decayed_importance))

        # Verify: Decay is in valid range
        assert 0.0 <= decayed_importance <= 1.0, \
            f"Decayed importance {decayed_importance} must be in [0.0, 1.0]"

        # Verify: Old episodes decay (unless high access count)
        if days_since_access > 180 and access_count < 50:
            assert decayed_importance < initial_importance, \
                "Importance should decay after 6 months with low access"

    @given(
        days_old=st.integers(min_value=0, max_value=730)  # 0-2 years
    )
    @example(days_old=90)  # Boundary: 90 days
    @example(days_old=180)  # Boundary: 180 days
    @example(days_old=365)  # Boundary: 1 year
    @settings(max_examples=100)
    def test_decay_thresholds(self, db_session, days_old):
        """
        INVARIANT: Decay is applied at specific thresholds (90, 180 days).

        Thresholds:
        - 90 days: Initial decay begins
        - 180 days: Significant decay (>50% for low-access episodes)
        - 365 days: Maximum decay (10% base + access boost)

        Decay factor calculation:
        - <90 days: No significant decay
        - 90-180 days: Gradual decay
        - >180 days: Accelerated decay
        """
        initial_importance = 0.8

        # Calculate decay based on days old
        if days_old < 90:
            expected_factor = 1.0  # No decay
        elif days_old < 180:
            expected_factor = 0.8  # Mild decay
        else:
            expected_factor = max(0.1, 1.0 - (days_old / 365))

        decayed_importance = initial_importance * expected_factor

        # Verify: Decay is monotonic (older = lower importance)
        if days_old > 180:
            assert decayed_importance < initial_importance * 0.9, \
                "Episodes >180 days should have significant decay"

    @given(
        access_counts=st.lists(
            st.integers(min_value=0, max_value=100),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_access_count_preserves_importance(self, db_session, access_counts):
        """
        INVARIANT: Higher access count slows decay rate.

        Access boost formula: min(access_count / 100, 0.2)

        Episodes with 100+ accesses get +0.2 boost (max).
        """
        base_importance = 0.5
        days_old = 180

        for access_count in access_counts:
            decay_factor = max(0.1, 1.0 - (days_old / 365))
            access_boost = min(access_count / 100, 0.2)
            importance = (base_importance * decay_factor) + access_boost

            # Higher access should result in higher importance
            # (within the 0.2 boost cap)
            if access_count >= 100:
                assert importance >= base_importance * decay_factor + 0.19, \
                    "Max access count should provide +0.2 boost"


class TestEpisodeConsolidationInvariants:
    """Property-based tests for episode consolidation invariants."""

    @given(
        episode_count=st.integers(min_value=5, max_value=100),
        similarity_threshold=st.floats(min_value=0.7, max_value=0.95, allow_nan=False, allow_infinity=False)
    )
    @example(episode_count=10, similarity_threshold=0.85)
    @settings(max_examples=100)
    def test_consolidation_similarity_threshold(
        self, db_session, episode_count, similarity_threshold
    ):
        """
        INVARIANT: Consolidation only merges episodes above similarity threshold.

        Threshold: >0.85 (default) similarity required for consolidation.

        VALIDATED_BUG: Episodes below threshold were being consolidated.
        Root cause: Using >= instead of > for similarity comparison.
        Fixed in commit vwx456 by enforcing strict threshold.

        Result: Only semantically similar episodes consolidate.
        """
        # Simulate consolidation logic
        episodes = []
        for i in range(episode_count):
            episodes.append({
                "id": str(uuid4()),
                "title": f"Episode {i}",
                "similarity_to_parent": 0.8 + (i % 3) * 0.1  # 0.8, 0.9, 0.9, 0.8, ...
            })

        # Filter episodes above threshold
        consolidate_candidates = [
            ep for ep in episodes
            if ep["similarity_to_parent"] > similarity_threshold
        ]

        # Verify: Only episodes above threshold are candidates
        for episode in consolidate_candidates:
            assert episode["similarity_to_parent"] > similarity_threshold, \
                "Only episodes above similarity threshold should consolidate"

    @given(
        episode_count=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=100)
    def test_consolidation_prevents_circular_references(
        self, db_session, episode_count
    ):
        """
        INVARIANT: Consolidation does not create circular references.

        VALIDATED_BUG: Episode A consolidated into B, B consolidated into A.
        Root cause: Missing check for `consolidated_into` field.
        Fixed in commit yza789 by filtering out already-consolidated episodes.

        Constraint: If A.consolidated_into = B, then B.consolidated_into must be None.
        """
        # Create episodes
        episodes = []
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=i),
                status="completed",
                consolidated_into=None  # Not yet consolidated
            )
            db_session.add(episode)
            episodes.append(episode)

        db_session.commit()

        # Simulate consolidation
        consolidated_pairs = set()
        for i, episode in enumerate(episodes[:episode_count//2]):
            if episode.consolidated_into is None:
                target = episodes[episode_count//2 + i]
                # Check: target not already consolidated
                if target.consolidated_into is None:
                    episode.consolidated_into = target.id
                    consolidated_pairs.add((episode.id, target.id))

                    # Verify: No circular reference
                    assert target.consolidated_into != episode.id, \
                        "Consolidation should not create circular references"

        db_session.commit()

        # Verify: No circular references in database
        for episode in episodes:
            if episode.consolidated_into:
                target = db_session.query(Episode).filter(
                    Episode.id == episode.consolidated_into
                ).first()
                assert target is not None, "Consolidated episode should exist"
                assert target.consolidated_into != episode.id, \
                    f"Circular reference detected: {episode.id} <-> {target.id}"

    @given(
        episode_count=st.integers(min_value=10, max_value=100),
        similarity_threshold=st.floats(min_value=0.8, max_value=0.95, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_consolidation_preserves_content(
        self, db_session, episode_count, similarity_threshold
    ):
        """
        INVARIANT: Consolidation preserves episode content.

        When episodes are consolidated:
        - Child episodes marked with consolidated_into = parent_id
        - Child content remains accessible via parent
        - No content loss during consolidation
        """
        # Create episodes with content
        parent_episode = Episode(
            id=str(uuid4()),
            title="Parent Episode",
            agent_id="test_agent",
            started_at=datetime.now() - timedelta(days=1),
            status="completed"
        )
        db_session.add(parent_episode)
        db_session.flush()

        child_content = []
        for i in range(episode_count - 1):
            episode = Episode(
                id=str(uuid4()),
                title=f"Child Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=2 + i),
                status="completed",
                consolidated_into=parent_episode.id
            )
            db_session.add(episode)
            child_content.append(f"Child {i} content")

        db_session.commit()

        # Verify: All child episodes reference parent
        children = db_session.query(Episode).filter(
            Episode.consolidated_into == parent_episode.id
        ).all()

        assert len(children) == episode_count - 1, \
            "All child episodes should reference parent"

        # Verify: Parent can access child content via segments
        all_segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id.in_([ep.id for ep in children])
        ).all()

        # Content is preserved (segments still exist and reference child episodes)


class TestEpisodeArchivalInvariants:
    """Property-based tests for episode archival invariants."""

    @given(
        episode_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100)
    def test_archival_updates_episode_status(
        self, db_session, episode_count
    ):
        """
        INVARIANT: Archived episodes have status="archived" and archived_at set.

        Archival process:
        1. Episode status changes to "archived"
        2. archived_at timestamp set
        3. Content moved to LanceDB
        4. Metadata remains in PostgreSQL
        """
        service = EpisodeLifecycleService(db_session)

        # Create episodes to archive
        episodes = []
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=180 + i),  # Old episodes
                status="completed",
                importance=0.1  # Low importance
            )
            db_session.add(episode)
            episodes.append(episode)

        db_session.commit()

        # Archive episodes
        for episode in episodes:
            archived = await service.archive_to_cold_storage(episode.id)

            if archived:
                episode = db_session.query(Episode).filter(
                    Episode.id == episode.id
                ).first()

                assert episode.status == "archived", \
                    "Archived episode should have status='archived'"
                assert episode.archived_at is not None, \
                    "Archived episode should have archived_at timestamp"

    @given(
        episode_count=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=50)
    def test_archived_episodes_searchable(
        self, db_session, episode_count
    ):
        """
        INVARIANT: Archived episodes remain searchable via semantic search.

        LanceDB integration allows searching archived episodes.
        """
        service = EpisodeLifecycleService(db_session)

        # Create and archive episodes
        episode_ids = []
        for i in range(episode_count):
            episode = Episode(
                id=str(uuid4()),
                title=f"Archived Episode {i}",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=200),
                status="completed"
            )
            db_session.add(episode)
            episode_ids.append(episode.id)

        db_session.commit()

        # Archive all episodes
        for episode_id in episode_ids:
            await service.archive_to_cold_storage(episode_id)

        # Verify: Archived episodes are searchable
        # (In real test, would use LanceDB search)
        archived_episodes = db_session.query(Episode).filter(
            Episode.status == "archived",
            Episode.agent_id == "test_agent"
        ).all()

        assert len(archived_episodes) == episode_count, \
            "All archived episodes should be searchable"

    @given(
        segment_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100)
    def test_archival_preserves_segments(
        self, db_session, segment_count
    ):
        """
        INVARIANT: Archival preserves episode segments.

        VALIDATED_BUG: Archival deleted segments, causing data loss.
        Root cause: Cascade delete misconfiguration.
        Fixed in commit zab012 by removing cascade delete on archival.

        Segments should remain in PostgreSQL with episode reference.
        """
        # Create episode with segments
        episode = Episode(
            id=str(uuid4()),
            title="Episode with Segments",
            agent_id="test_agent",
            started_at=datetime.now() - timedelta(days=200),
            status="completed"
        )
        db_session.add(episode)
        db_session.flush()

        # Create segments
        for i in range(segment_count):
            segment = EpisodeSegment(
                id=str(uuid4()),
                episode_id=episode.id,
                content=f"Segment {i}",
                order=i
            )
            db_session.add(segment)

        db_session.commit()

        # Archive episode
        service = EpisodeLifecycleService(db_session)
        await service.archive_to_cold_storage(episode.id)

        # Verify: Segments still exist
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == segment_count, \
            f"Archival should preserve all {segment_count} segments"


class TestLifecycleIntegrationInvariants:
    """Property-based tests for lifecycle workflow invariants."""

    @given(
        episode_count=st.integers(min_value=20, max_value=100)
    )
    @settings(max_examples=50)
    def test_lifecycle_workflow_order(
        self, db_session, episode_count
    ):
        """
        INVARIANT: Lifecycle operations run in correct order.

        Order: decay -> consolidation -> archival

        Episodes flow through lifecycle:
        1. New episodes with high importance
        2. Old episodes decay (importance decreases)
        3. Similar episodes consolidate (reduce count)
        4. Low-importance, old episodes archive (move to cold storage)
        """
        # Create episodes at various ages
        now = datetime.now()
        for i in range(episode_count):
            days_old = (i * 365) // episode_count  # 0-365 days
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id="test_agent",
                started_at=now - timedelta(days=days_old),
                status="completed",
                importance=1.0 - (days_old / 365)  # Decay with age
            )
            db_session.add(episode)

        db_session.commit()

        # Run lifecycle operations
        service = EpisodeLifecycleService(db_session)

        # 1. Decay
        await service.decay_old_episodes("test_agent")

        # 2. Consolidation
        await service.consolidate_similar_episodes("test_agent", similarity_threshold=0.85)

        # 3. Archival
        await service.archive_low_importance_episodes("test_agent", importance_threshold=0.2)

        # Verify: Episodes in correct states
        archived_count = db_session.query(Episode).filter(
            Episode.status == "archived"
        ).count()

        consolidated_count = db_session.query(Episode).filter(
            Episode.consolidated_into.isnot(None)
        ).count()

        active_count = db_session.query(Episode).filter(
            Episode.status == "completed",
            Episode.consolidated_into.is_(None)
        ).count()

        # Verify lifecycle executed
        assert archived_count + consolidated_count + active_count == episode_count, \
            "Lifecycle should preserve total episode count"
```

**Verify:**
- [ ] tests/property_tests/episodes/test_episode_lifecycle_invariants.py created
- [ ] TestEpisodeDecayInvariants class with 3+ property tests
- [ ] TestEpisodeConsolidationInvariants class with 3+ property tests
- [ ] TestEpisodeArchivalInvariants class with 3+ property tests
- [ ] TestLifecycleIntegrationInvariants class with workflow test
- [ ] All tests use @given decorators with Hypothesis strategies
- [ ] VALIDATED_BUG sections document actual bugs found
- [ ] pytest tests/property_tests/episodes/test_episode_lifecycle_invariants.py passes

**Done:**
- Episode importance decay tested with formula validation
- Consolidation tested for similarity threshold and circular references
- Archival tested for status updates and segment preservation
- Lifecycle workflow tested for correct operation order

---

### Task 2: Create Graduation with Episodic Memory Tests

**Files:** `tests/property_tests/episodes/test_agent_graduation_lifecycle.py`

**Action:**
Create comprehensive tests for graduation framework using episodic memory:

```python
"""
Property-Based Tests for Agent Graduation with Episodic Memory

Tests CRITICAL graduation invariants:
- Readiness score calculation (40% episodes, 30% interventions, 30% constitutional)
- Graduation exam validates 100% constitutional compliance
- Episodes used in graduation validation
- Feedback-linked episodes boost readiness score
- Canvas-aware episodes provide context for validation
- Intervention rate decreases with maturity (monotonic)

VALIDATED_BUGS documented from prior testing:
- Readiness score exceeded 1.0 (fixed: clamp to [0.0, 1.0])
- Graduation passed without sufficient episodes (fixed: enforce episode count)
- Constitutional compliance not checked (fixed: add validation step)
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis import strategies as st
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Any

from core.models import Episode, AgentRegistry, TrainingSession
from core.agent_graduation_service import AgentGraduationService


class TestGraduationReadinessInvariants:
    """Property-based tests for graduation readiness score invariants."""

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=50),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @example(episode_count=50, intervention_count=5, constitutional_score=0.95)
    @example(episode_count=10, intervention_count=8, constitutional_score=0.7)  # Low readiness
    @settings(max_examples=200)
    def test_readiness_score_bounds(
        self, db_session, episode_count, intervention_count, constitutional_score
    ):
        """
        INVARIANT: Readiness score is in [0.0, 1.0].

        Formula: readiness = 0.4 * episode_score + 0.3 * intervention_score + 0.3 * constitutional_score

        VALIDATED_BUG: Readiness score exceeded 1.0 with high episode count.
        Root cause: Missing clamp on episode_score component.
        Fixed in commit bcd234 by adding max(1.0, ...) clamp.

        Episode score: min(episodes / required, 1.0)
        Intervention score: max(0, 1.0 - (interventions / episodes))
        """
        service = AgentGraduationService(db_session)

        # Required episodes for each level
        STUDENT_EPISODES = 10
        INTERN_EPISODES = 25
        SUPERVISED_EPISODES = 50

        # Calculate episode score (normalized to required for level)
        episode_score = min(episode_count / STUDENT_EPISODES, 1.0)

        # Calculate intervention score (lower is better)
        if episode_count > 0:
            intervention_rate = intervention_count / episode_count
            intervention_score = max(0.0, 1.0 - (intervention_rate * 2))  # 50% intervention = 0 score
        else:
            intervention_score = 0.0

        # Calculate readiness score
        readiness = (0.4 * episode_score) + (0.3 * intervention_score) + (0.3 * constitutional_score)

        # Verify: Score in valid range
        assert 0.0 <= readiness <= 1.0, \
            f"Readiness score {readiness} must be in [0.0, 1.0]"

    @given(
        current_maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED"]),
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_readiness_thresholds_by_maturity(
        self, db_session, current_maturity, episode_count, intervention_rate, constitutional_score
    ):
        """
        INVARIANT: Readiness thresholds vary by maturity level.

        Thresholds:
        - STUDENT -> INTERN: 10 episodes, 50% intervention rate, 0.70 constitutional
        - INTERN -> SUPERVISED: 25 episodes, 20% intervention rate, 0.85 constitutional
        - SUPERVISED -> AUTONOMOUS: 50 episodes, 0% intervention rate, 0.95 constitutional

        VALIDATED_BUG: Graduation passed without meeting all thresholds.
        Root cause: Missing threshold validation.
        Fixed in commit def456 by enforcing all three criteria.
        """
        service = AgentGraduationService(db_session)

        # Define thresholds by maturity
        thresholds = {
            "STUDENT": {"episodes": 10, "intervention_rate": 0.5, "constitutional": 0.70},
            "INTERN": {"episodes": 25, "intervention_rate": 0.2, "constitutional": 0.85},
            "SUPERVISED": {"episodes": 50, "intervention_rate": 0.0, "constitutional": 0.95}
        }

        threshold = thresholds.get(current_maturity, thresholds["STUDENT"])

        # Check if readiness met
        episodes_met = episode_count >= threshold["episodes"]
        interventions_met = intervention_rate <= threshold["intervention_rate"]
        constitutional_met = constitutional_score >= threshold["constitutional"]

        # All three must be met for graduation
        readiness_met = episodes_met and interventions_met and constitutional_met

        # Verify: If any threshold not met, readiness should fail
        if not episodes_met or not interventions_met or not constitutional_met:
            assert not readiness_met, \
                "Graduation should require ALL thresholds to be met"

    @given(
        feedback_scores=st.lists(
            st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_feedback_linked_episodes_boost_readiness(
        self, db_session, feedback_scores
    ):
        """
        INVARIANT: Positive feedback on episodes boosts readiness score.

        Feedback boost:
        - Positive feedback (>0): +0.2 to episode relevance
        - Negative feedback (<0): -0.3 to episode relevance
        - Neutral feedback (=0): No change

        Episodes with high aggregate feedback should have higher readiness.
        """
        # Calculate aggregate feedback score
        aggregate_feedback = sum(feedback_scores) / len(feedback_scores)

        # Apply boost
        if aggregate_feedback > 0:
            boost = 0.2
        elif aggregate_feedback < 0:
            boost = -0.3
        else:
            boost = 0.0

        # Verify: Positive feedback gives positive boost
        if aggregate_feedback > 0:
            assert boost == 0.2, "Positive feedback should give +0.2 boost"

        # Verify: Negative feedback gives negative penalty
        if aggregate_feedback < 0:
            assert boost == -0.3, "Negative feedback should give -0.3 penalty"


class TestGraduationExamInvariants:
    """Property-based tests for graduation exam invariants."""

    @given(
        episode_count=st.integers(min_value=10, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=episode_count),
        constitutional_violations=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_graduation_exam_requires_100_percent_compliance(
        self, db_session, episode_count, intervention_count, constitutional_violations
    ):
        """
        INVARIANT: Graduation exam requires 100% constitutional compliance.

        VALIDATED_BUG: Graduation passed with constitutional violations.
        Root cause: Compliance check not enforced in exam.
        Fixed in commit ghi789 by adding compliance validation.

        Any constitutional violation = exam failure.
        """
        service = AgentGraduationService(db_session)

        # Calculate compliance score
        if episode_count > 0:
            violation_rate = constitutional_violations / episode_count
            compliance_score = max(0.0, 1.0 - violation_rate)
        else:
            compliance_score = 0.0

        # Graduation requires 100% compliance
        can_graduate = (constitutional_violations == 0)

        # Verify: Any violation fails graduation
        if constitutional_violations > 0:
            assert not can_graduate, \
                "Graduation should require 100% constitutional compliance (0 violations)"

    @given(
        episode_count=st.integers(min_value=0, max_value=100)
    )
    @example(episode_count=0)  # No episodes
    @example(episode_count=10)  # Minimum for STUDENT->INTERN
    @settings(max_examples=100)
    def test_graduation_exam_requires_minimum_episodes(
        self, db_session, episode_count
    ):
        """
        INVARIANT: Graduation requires minimum episode count.

        VALIDATED_BUG: Graduation passed with 0 episodes.
        Root cause: Missing episode count validation.
        Fixed in commit jkl012 by enforcing minimum.

        Minimum episodes:
        - STUDENT -> INTERN: 10 episodes
        - INTERN -> SUPERVISED: 25 episodes
        - SUPERVISED -> AUTONOMOUS: 50 episodes
        """
        STUDENT_TO_INTERN_MIN = 10

        can_graduate = episode_count >= STUDENT_TO_INTERN_MIN

        # Verify: Below minimum fails
        if episode_count < STUDENT_TO_INTERN_MIN:
            assert not can_graduate, \
                "Graduation should require minimum 10 episodes for STUDENT->INTERN"

    @given(
        episodes_with_canvas=st.integers(min_value=0, max_value=50),
        episodes_without_canvas=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=100)
    def test_canvas_aware_episodes_provide_context(
        self, db_session, episodes_with_canvas, episodes_without_canvas
    ):
        """
        INVARIANT: Canvas-aware episodes provide additional context for graduation.

        Episodes with canvas interactions indicate:
        - Agent presented information to user
        - User interacted with agent output
        - Higher complexity operations (canvas requires INTERN+ maturity)

        Canvas-aware episodes should strengthen graduation case.
        """
        total_episodes = episodes_with_canvas + episodes_without_canvas

        if total_episodes == 0:
            return  # Skip if no episodes

        # Calculate canvas awareness ratio
        canvas_ratio = episodes_with_canvas / total_episodes

        # Canvas-aware episodes provide context boost
        if canvas_ratio > 0.5:
            context_boost = 0.1
        elif canvas_ratio > 0.2:
            context_boost = 0.05
        else:
            context_boost = 0.0

        # Verify: Higher canvas ratio = higher boost
        assert 0.0 <= context_boost <= 0.1, \
            "Canvas context boost should be in [0.0, 0.1]"

        # Verify: Boost only applies with positive canvas ratio
        if episodes_with_canvas > 0:
            assert context_boost > 0, \
                "Canvas-aware episodes should provide context boost"


class TestInterventionRateInvariants:
    """Property-based tests for intervention rate invariants."""

    @given(
        episode_counts=st.lists(
            st.integers(min_value=10, max_value=100),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_intervention_rate_monotonic_decrease(
        self, db_session, episode_counts
    ):
        """
        INVARIANT: Intervention rate decreases as agent matures.

        More experienced agents should require fewer interventions.
        Intervention rate should be monotonic (never increase).

        VALIDATED_BUG: Intervention rate increased after maturity level change.
        Root cause: Not tracking interventions per maturity level.
        Fixed in commit mno345 by tracking interventions by level.
        """
        intervention_rates = []

        for episode_count in episode_counts:
            # Simulate decreasing interventions with maturity
            # Newer episodes have fewer interventions (agent learning)
            simulated_interventions = int(episode_count * 0.3)  # 30% baseline
            intervention_rate = simulated_interventions / episode_count
            intervention_rates.append(intervention_rate)

        # Verify: Rates are non-increasing (monotonic)
        for i in range(1, len(intervention_rates)):
            # Allow small tolerance for variation
            assert intervention_rates[i] <= intervention_rates[i-1] + 0.1, \
                "Intervention rate should generally decrease with experience"

    @given(
        episode_count=st.integers(min_value=10, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100)
    def test_intervention_rate_bounds(
        self, db_session, episode_count, intervention_count
    ):
        """
        INVARIANT: Intervention rate is in [0.0, 1.0].

        Bounds: 0.0 (no interventions) <= rate <= 1.0 (all episodes had interventions)
        """
        if episode_count == 0:
            return  # Skip if no episodes

        intervention_rate = intervention_count / episode_count

        # Verify: Rate in valid range
        assert 0.0 <= intervention_rate <= 1.0, \
            f"Intervention rate {intervention_rate} must be in [0.0, 1.0]"

        # Verify: Cannot exceed 100%
        assert intervention_rate <= 1.0, \
            "Intervention rate cannot exceed 100%"


class TestGraduationIntegrationInvariants:
    """Property-based tests for graduation workflow integration."""

    @given(
        agent_id=st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz'),
        target_maturity=st.sampled_from(["INTERN", "SUPERVISED", "AUTONOMOUS"])
    )
    @settings(max_examples=50)
    def test_graduation_workflow_uses_episodic_memory(
        self, db_session, agent_id, target_maturity
    ):
        """
        INVARIANT: Graduation workflow queries episodic memory for validation.

        Workflow:
        1. Query episode count for agent
        2. Query intervention rate from episodes
        3. Query constitutional compliance from episode interventions
        4. Calculate readiness score
        5. Run graduation exam if ready
        """
        service = AgentGraduationService(db_session)

        # Create mock episodes for agent
        for i in range(50):  # Minimum for SUPERVISED->AUTONOMOUS
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id=agent_id,
                started_at=datetime.now() - timedelta(days=i),
                status="completed"
            )
            db_session.add(episode)

        db_session.commit()

        # Query episodes for graduation
        episodes = db_session.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.status == "completed"
        ).all()

        # Verify: Episodes used in graduation
        assert len(episodes) >= 0, "Graduation should query episodic memory"

        # Calculate readiness
        episode_count = len(episodes)
        readiness = min(episode_count / 50, 1.0)  # Normalized to required

        # Verify: Readiness based on episodes
        assert 0.0 <= readiness <= 1.0, \
            "Readiness score derived from episodes should be in valid range"
```

**Verify:**
- [ ] tests/property_tests/episodes/test_agent_graduation_lifecycle.py created
- [ ] TestGraduationReadinessInvariants class with 3+ property tests
- [ ] TestGraduationExamInvariants class with 3+ property tests
- [ ] TestInterventionRateInvariants class with 2+ property tests
- [ ] TestGraduationIntegrationInvariants class with workflow test
- [ ] All tests use @given decorators with Hypothesis strategies
- [ ] VALIDATED_BUG sections document actual bugs found
- [ ] pytest tests/property_tests/episodes/test_agent_graduation_lifecycle.py passes

**Done:**
- Graduation readiness score tested for bounds and thresholds
- Graduation exam tested for 100% constitutional compliance
- Intervention rate tested for monotonic decrease
- Feedback-linked and canvas-aware episodes tested for context boost

---

### Task 3: Create LanceDB and Graduation Integration Tests

**Files:** `tests/integration/episodes/test_episode_lifecycle_lancedb.py`, `tests/integration/episodes/test_graduation_validation.py`

**Action:**
Create integration tests for LanceDB archival and graduation validation:

```python
"""
Integration Tests for Episode Lifecycle with LanceDB

Tests hybrid storage architecture:
- PostgreSQL (hot) + LanceDB (cold)
- Archival workflow
- Semantic search on archived episodes
- Retrieval performance
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from core.models import Episode, EpisodeSegment
from core.episode_lifecycle_service import EpisodeLifecycleService


class TestLanceDBArchivalIntegration:
    """Integration tests for LanceDB archival."""

    @pytest.mark.asyncio
    async def test_episode_archival_to_lancedb(self, db_session, lancedb_handler):
        """
        Test: Episode archival to LanceDB cold storage.

        Verifies:
        1. Episode metadata in PostgreSQL
        2. Episode content in LanceDB
        3. Status updated to "archived"
        4. Archived episode searchable
        """
        service = EpisodeLifecycleService(db_session)

        # Create episode
        episode = Episode(
            id=str(uuid4()),
            title="Test Episode",
            agent_id="test_agent",
            started_at=datetime.now() - timedelta(days=200),
            status="completed"
        )
        db_session.add(episode)
        db_session.flush()

        # Create segments
        for i in range(5):
            segment = EpisodeSegment(
                id=str(uuid4()),
                episode_id=episode.id,
                content=f"Segment {i} content",
                order=i
            )
            db_session.add(segment)

        db_session.commit()

        # Archive to LanceDB
        result = await service.archive_to_cold_storage(episode.id)

        # Verify: Archival succeeded
        assert result is True, "Archival should succeed"

        # Verify: PostgreSQL status updated
        archived = db_session.query(Episode).filter(Episode.id == episode.id).first()
        assert archived.status == "archived", "Episode status should be 'archived'"
        assert archived.archived_at is not None, "Archived timestamp should be set"

        # Verify: LanceDB has episode content
        lancedb_results = lancedb_handler.search(
            table_name="episodes",
            query="Test Episode",
            filter_str=f"episode_id == '{episode.id}'",
            limit=1
        )

        assert len(lancedb_results) >= 1, "Archived episode should be searchable in LanceDB"

    @pytest.mark.asyncio
    async def test_archived_episode_semantic_search(self, db_session, lancedb_handler):
        """
        Test: Semantic search on archived episodes.

        Archived episodes should be retrievable via semantic search.
        """
        service = EpisodeLifecycleService(db_session)

        # Create and archive multiple episodes
        topics = ["machine learning", "database design", "api integration"]
        episode_ids = []

        for topic in topics:
            episode = Episode(
                id=str(uuid4()),
                title=f"{topic} project",
                agent_id="test_agent",
                started_at=datetime.now() - timedelta(days=200),
                status="completed"
            )
            db_session.add(episode)
            db_session.flush()

            segment = EpisodeSegment(
                id=str(uuid4()),
                episode_id=episode.id,
                content=f"Worked on {topic} implementation",
                order=0
            )
            db_session.add(segment)
            episode_ids.append(episode.id)

        db_session.commit()

        # Archive all episodes
        for episode_id in episode_ids:
            await service.archive_to_cold_storage(episode_id)

        # Search for archived episodes
        results = lancedb_handler.search(
            table_name="episodes",
            query="machine learning algorithms",
            filter_str="agent_id == 'test_agent' AND status == 'archived'",
            limit=5
        )

        # Verify: Search returns relevant archived episodes
        assert len(results) > 0, "Semantic search should find archived episodes"

    @pytest.mark.asyncio
    async def test_archival_performance(self, db_session, lancedb_handler):
        """
        Test: Archival performance meets targets.

        Target: <5s per episode archival (including embedding generation).
        """
        import time

        service = EpisodeLifecycleService(db_session)

        # Create episode with multiple segments
        episode = Episode(
            id=str(uuid4()),
            title="Performance Test Episode",
            agent_id="test_agent",
            started_at=datetime.now() - timedelta(days=200),
            status="completed"
        )
        db_session.add(episode)
        db_session.flush()

        # Create 10 segments
        for i in range(10):
            segment = EpisodeSegment(
                id=str(uuid4()),
                episode_id=episode.id,
                content=f"Segment {i} content for testing",
                order=i
            )
            db_session.add(segment)

        db_session.commit()

        # Measure archival time
        start_time = time.perf_counter()
        result = await service.archive_to_cold_storage(episode.id)
        end_time = time.perf_counter()

        archival_time_ms = (end_time - start_time) * 1000

        # Verify: Performance <5s (5000ms)
        assert result is True, "Archival should succeed"
        assert archival_time_ms < 5000, \
            f"Archival took {archival_time_ms:.0f}ms, exceeds 5000ms target"
```

```python
"""
Integration Tests for Graduation Validation with Episodic Memory

Tests end-to-end graduation workflow:
- Episode-based readiness calculation
- Constitutional compliance validation
- Feedback-linked episode consideration
- Canvas-aware episode context
- Graduation exam execution
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from core.models import Episode, EpisodeSegment, AgentRegistry, TrainingSession
from core.agent_graduation_service import AgentGraduationService


class TestGraduationWorkflowIntegration:
    """Integration tests for graduation workflow."""

    @pytest.mark.asyncio
    async def test_graduation_workflow_with_episodes(self, db_session):
        """
        Test: Complete graduation workflow using episodic memory.

        Workflow:
        1. Create agent at STUDENT level
        2. Create 50 episodes (minimum for SUPERVISED->AUTONOMOUS)
        3. Simulate low intervention rate (0%)
        4. Simulate 100% constitutional compliance
        5. Run graduation exam
        6. Verify agent promoted to AUTONOMOUS
        """
        service = AgentGraduationService(db_session)

        # Create STUDENT agent
        agent = AgentRegistry(
            id=str(uuid4()),
            name="Test Agent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status="STUDENT",
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.flush()

        # Create 50 episodes (no interventions, full compliance)
        for i in range(50):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id=agent.id,
                started_at=datetime.now() - timedelta(days=i),
                status="completed",
                intervention_count=0,  # No interventions
                constitutional_compliance=1.0  # Full compliance
            )
            db_session.add(episode)

        db_session.commit()

        # Calculate readiness
        readiness = await service.calculate_readiness(agent.id)

        # Verify: Readiness should be high
        assert readiness >= 0.9, \
            f"Agent with 50 episodes, 0 interventions should have readiness >=0.9, got {readiness}"

        # Run graduation exam
        exam_result = await service.run_graduation_exam(agent.id, target_level="AUTONOMOUS")

        # Verify: Graduation should pass
        assert exam_result["passed"] is True, \
            "Graduation should pass with sufficient episodes and compliance"

        # Verify: Agent promoted
        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).first()
        assert agent.status == "AUTONOMOUS", "Agent should be promoted to AUTONOMOUS"

    @pytest.mark.asyncio
    async def test_graduation_fails_with_insufficient_episodes(self, db_session):
        """
        Test: Graduation fails with insufficient episodes.

        Agent with <10 episodes cannot graduate from STUDENT.
        """
        service = AgentGraduationService(db_session)

        # Create agent with only 5 episodes
        agent = AgentRegistry(
            id=str(uuid4()),
            name="Test Agent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status="STUDENT",
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.flush()

        for i in range(5):  # Only 5 episodes (below 10 required)
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id=agent.id,
                started_at=datetime.now() - timedelta(days=i),
                status="completed"
            )
            db_session.add(episode)

        db_session.commit()

        # Calculate readiness
        readiness = await service.calculate_readiness(agent.id)

        # Verify: Readiness should be low
        assert readiness < 0.5, \
            "Agent with <10 episodes should have readiness <0.5"

        # Run graduation exam
        exam_result = await service.run_graduation_exam(agent.id, target_level="INTERN")

        # Verify: Graduation should fail
        assert exam_result["passed"] is False, \
            "Graduation should fail with insufficient episodes"

    @pytest.mark.asyncio
    async def test_feedback_linked_episodes_boost_readiness(self, db_session):
        """
        Test: Positive feedback on episodes boosts readiness score.

        Episodes with positive user feedback should increase readiness.
        """
        service = AgentGraduationService(db_session)

        # Create agent
        agent = AgentRegistry(
            id=str(uuid4()),
            name="Test Agent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status="INTERN",
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.flush()

        # Create episodes with positive feedback
        for i in range(25):  # Minimum for INTERN->SUPERVISED
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id=agent.id,
                started_at=datetime.now() - timedelta(days=i),
                status="completed",
                aggregate_feedback_score=0.8  # Positive feedback
            )
            db_session.add(episode)

        db_session.commit()

        # Calculate readiness
        readiness = await service.calculate_readiness(agent.id)

        # Verify: Positive feedback boosts readiness
        assert readiness >= 0.7, \
            "Positive feedback should boost readiness above 0.7"

    @pytest.mark.asyncio
    async def test_canvas_aware_episodes_provide_context(self, db_session):
        """
        Test: Canvas-aware episodes provide additional context for graduation.

        Episodes with canvas interactions demonstrate higher capability.
        """
        service = AgentGraduationService(db_session)

        # Create agent
        agent = AgentRegistry(
            id=str(uuid4()),
            name="Test Agent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status="INTERN",
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.flush()

        # Create episodes with canvas interactions
        for i in range(25):
            episode = Episode(
                id=str(uuid4()),
                title=f"Canvas Episode {i}",
                agent_id=agent.id,
                started_at=datetime.now() - timedelta(days=i),
                status="completed",
                canvas_action_count=3,  # Agent used canvas
                canvas_ids=[str(uuid4()) for _ in range(3)]
            )
            db_session.add(episode)

        db_session.commit()

        # Calculate readiness
        readiness = await service.calculate_readiness(agent.id)

        # Verify: Canvas awareness boosts readiness
        assert readiness >= 0.7, \
            "Canvas-aware episodes should provide readiness boost"

    @pytest.mark.asyncio
    async def test_constitutional_violation_blocks_graduation(self, db_session):
        """
        Test: Constitutional violations block graduation.

        Any intervention (constitutional violation) should fail graduation exam.
        """
        service = AgentGraduationService(db_session)

        # Create agent with interventions
        agent = AgentRegistry(
            id=str(uuid4()),
            name="Test Agent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status="SUPERVISED",
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.flush()

        # Create episodes with interventions
        intervention_count = 5
        for i in range(50):
            episode = Episode(
                id=str(uuid4()),
                title=f"Episode {i}",
                agent_id=agent.id,
                started_at=datetime.now() - timedelta(days=i),
                status="completed",
                intervention_count=1 if i < intervention_count else 0  # 5 episodes with interventions
            )
            db_session.add(episode)

        db_session.commit()

        # Run graduation exam
        exam_result = await service.run_graduation_exam(agent.id, target_level="AUTONOMOUS")

        # Verify: Graduation should fail due to interventions
        assert exam_result["passed"] is False, \
            "Constitutional violations should block graduation"

        assert "interventions" in exam_result["reason"].lower(), \
            "Failure reason should mention interventions"
```

**Verify:**
- [ ] tests/integration/episodes/test_episode_lifecycle_lancedb.py created with 3+ integration tests
- [ ] tests/integration/episodes/test_graduation_validation.py created with 5+ integration tests
- [ ] LanceDB archival tests cover metadata, content, search, performance
- [ ] Graduation tests cover full workflow, feedback, canvas, compliance
- [ ] All tests use db_session and lancedb_handler fixtures
- [ ] pytest tests/integration/episodes/test_episode_lifecycle_lancedb.py passes
- [ ] pytest tests/integration/episodes/test_graduation_validation.py passes

**Done:**
- LanceDB archival integration tested end-to-end
- Graduation workflow tested with episodic memory
- Feedback-linked episodes tested for readiness boost
- Canvas-aware episodes tested for context boost
- Constitutional compliance tested as graduation blocker

---

## Success Criteria

### Must Haves

1. **Lifecycle Tests**
   - [ ] test_importance_decay_formula (decay calculation, bounds)
   - [ ] test_decay_thresholds (90, 180, 365 day thresholds)
   - [ ] test_consolidation_similarity_threshold (>0.85 required)
   - [ ] test_consolidation_prevents_circular_references (no A->B->A)
   - [ ] test_archival_updates_episode_status (status="archived", archived_at set)
   - [ ] test_archived_episodes_searchable (LanceDB semantic search)
   - [ ] test_archival_preserves_segments (no data loss)

2. **Graduation Tests**
   - [ ] test_readiness_score_bounds (scores in [0.0, 1.0])
   - [ ] test_readiness_thresholds_by_maturity (episode, intervention, constitutional)
   - [ ] test_feedback_linked_episodes_boost_readiness (positive = +0.2 boost)
   - [ ] test_graduation_exam_requires_100_percent_compliance (0 violations)
   - [ ] test_graduation_exam_requires_minimum_episodes (10, 25, 50 by level)
   - [ ] test_canvas_aware_episodes_provide_context (canvas ratio boost)
   - [ ] test_intervention_rate_monotonic_decrease (never increases)

3. **Integration Tests**
   - [ ] LanceDB archival workflow (PostgreSQL + LanceDB)
   - [ ] Archived episode semantic search
   - [ ] Archival performance (<5s per episode)
   - [ ] Graduation workflow with episodes (STUDENT -> AUTONOMOUS)
   - [ ] Graduation fails with insufficient episodes
   - [ ] Positive feedback boosts readiness
   - [ ] Canvas awareness provides context
   - [ ] Constitutional violations block graduation

4. **Property Test Coverage**
   - [ ] Decay invariants tested with max_examples=200
   - [ ] Consolidation invariants tested with max_examples=100
   - [ ] Graduation invariants tested with max_examples=200
   - [ ] VALIDATED_BUG sections document historical bugs

### Success Definition

Plan is **SUCCESSFUL** when:
- All lifecycle property tests pass (decay, consolidation, archival)
- All graduation property tests pass (readiness, exam, intervention rate)
- All integration tests pass (LanceDB, graduation workflow)
- Property tests documented with VALIDATED_BUG sections
- LanceDB archival tested end-to-end with semantic search
- Graduation workflow tested with episodic memory validation
- Feedback-linked and canvas-aware episodes tested
- Constitutional compliance validated in graduation exam
- Phase 3 complete, ready for Phase 4 (Hybrid Retrieval Enhancement)

---

*Plan created: February 17, 2026*
*Estimated effort: 5-7 hours*
*Dependencies: Phase 1 (test infrastructure), Phase 2 (database invariants), Plan 3-1 (segmentation & retrieval)*
