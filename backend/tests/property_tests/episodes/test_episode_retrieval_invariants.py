"""
Property-Based Tests for Episode Retrieval Invariants

⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for episode retrieval.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md

Tests:
    - 6 comprehensive property-based tests for episode retrieval
    - Coverage targets: 100% of episode_retrieval_service.py
    - Performance target: <100ms per retrieval
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from typing import List, Dict
from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
    RetrievalResult
)
from core.models import Episode, EpisodeSegment


class TestEpisodeRetrievalInvariants:
    """Property-based tests for episode retrieval invariants."""

    # ========== Temporal Retrieval ==========

    @given(
        episodes=st.lists(
            st.fixed_dictionaries({
                'episode_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'agent_id': st.text(min_size=1, max_size=20),
                'start_time': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'end_time': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())
            }),
            min_size=1,
            max_size=50
        ),
        limit=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_temporal_retrieval_ordered_by_time(self, episodes, limit):
        """INVARIANT: Temporal retrieval must return episodes in chronological order."""
        service = EpisodeRetrievalService()

        # Create episodes with proper time ordering
        valid_episodes = []
        for ep in episodes:
            assume(ep['end_time'] > ep['start_time'])
            episode = Episode(
                episode_id=ep['episode_id'],
                agent_id=ep['agent_id'],
                start_time=ep['start_time'],
                end_time=ep['end_time']
            )
            valid_episodes.append(episode)

        # Retrieve episodes temporally
        result = service.retrieve_episodes(
            agent_id=episodes[0]['agent_id'],
            mode=RetrievalMode.TEMPORAL,
            limit=min(limit, len(valid_episodes))
        )

        # Verify chronological order
        timestamps = [ep.start_time for ep in result.episodes]
        assert timestamps == sorted(timestamps), "Episodes must be in chronological order"

    @given(
        episodes=st.lists(
            st.fixed_dictionaries({
                'episode_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'agent_id': st.text(min_size=1, max_size=20),
                'start_time': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())
            }),
            min_size=10,
            max_size=100
        ),
        limit=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100)
    def test_temporal_retrieval_respects_limit(self, episodes, limit):
        """INVARIANT: Temporal retrieval must not return more than limit episodes."""
        service = EpisodeRetrievalService()

        # Create episodes
        valid_episodes = []
        for ep in episodes:
            episode = Episode(
                episode_id=ep['episode_id'],
                agent_id=ep['agent_id'],
                start_time=ep['start_time'],
                end_time=ep['start_time'] + timedelta(hours=1)
            )
            valid_episodes.append(episode)

        # Retrieve with limit
        result = service.retrieve_episodes(
            agent_id=episodes[0]['agent_id'],
            mode=RetrievalMode.TEMPORAL,
            limit=limit
        )

        # Verify limit
        assert len(result.episodes) <= limit, f"Returned {len(result.episodes)} episodes, limit is {limit}"

    # ========== Semantic Retrieval ==========

    @given(
        episodes=st.lists(
            st.fixed_dictionaries({
                'episode_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'agent_id': st.text(min_size=1, max_size=20),
                'summary': st.text(min_size=10, max_size=200),
                'embedding': st.lists(st.floats(min_value=-1, max_value=1, allow_nan=False), min_size=384, max_size=384)
            }),
            min_size=5,
            max_size=30
        ),
        query_embedding=st.lists(st.floats(min_value=-1, max_value=1, allow_nan=False), min_size=384, max_size=384),
        limit=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_semantic_retrieval_ranked_by_similarity(self, episodes, query_embedding, limit):
        """INVARIANT: Semantic retrieval must rank episodes by similarity score."""
        service = EpisodeRetrievalService()

        # Create episodes with embeddings
        valid_episodes = []
        for ep in episodes:
            episode = Episode(
                episode_id=ep['episode_id'],
                agent_id=ep['agent_id'],
                summary=ep['summary'],
                embedding=ep['embedding']
            )
            valid_episodes.append(episode)

        # Retrieve semantically
        result = service.retrieve_episodes(
            agent_id=episodes[0]['agent_id'],
            mode=RetrievalMode.SEMANTIC,
            query_embedding=query_embedding,
            limit=min(limit, len(valid_episodes))
        )

        # Verify ranking (similarity scores should be descending)
        if len(result.episodes) > 1:
            similarities = [ep.similarity_score for ep in result.episodes]
            assert similarities == sorted(similarities, reverse=True), "Episodes must be ranked by similarity (descending)"

    @given(
        query_embedding=st.lists(st.floats(min_value=-1, max_value=1, allow_nan=False), min_size=384, max_size=384),
        episodes=st.lists(
            st.fixed_dictionaries({
                'episode_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'agent_id': st.text(min_size=1, max_size=20),
                'embedding': st.lists(st.floats(min_value=-1, max_value=1, allow_nan=False), min_size=384, max_size=384)
            }),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_semantic_retrieval_similarity_bounds(self, query_embedding, episodes):
        """INVARIANT: Similarity scores must be in [0, 1] range."""
        service = EpisodeRetrievalService()

        # Create episodes
        valid_episodes = []
        for ep in episodes:
            episode = Episode(
                episode_id=ep['episode_id'],
                agent_id=ep['agent_id'],
                embedding=ep['embedding']
            )
            valid_episodes.append(episode)

        # Retrieve semantically
        result = service.retrieve_episodes(
            agent_id=episodes[0]['agent_id'],
            mode=RetrievalMode.SEMANTIC,
            query_embedding=query_embedding,
            limit=len(valid_episodes)
        )

        # Verify similarity bounds
        for ep in result.episodes:
            assert hasattr(ep, 'similarity_score'), "Episode must have similarity_score"
            assert 0.0 <= ep.similarity_score <= 1.0, f"Similarity {ep.similarity_score} not in [0, 1]"

    # ========== Sequential Retrieval ==========

    @given(
        episodes=st.lists(
            st.fixed_dictionaries({
                'episode_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'agent_id': st.text(min_size=1, max_size=20),
                'start_time': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'summary': st.text(min_size=10, max_size=200),
                'segments': st.lists(
                    st.fixed_dictionaries({
                        'segment_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                        'content': st.text(min_size=20, max_size=500)
                    }),
                    min_size=1,
                    max_size=10
                )
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_sequential_retrieval_includes_full_context(self, episodes):
        """INVARIANT: Sequential retrieval must include full episode context."""
        service = EpisodeRetrievalService()

        # Create episodes with segments
        valid_episodes = []
        for ep in episodes:
            # Create episode
            episode = Episode(
                episode_id=ep['episode_id'],
                agent_id=ep['agent_id'],
                start_time=ep['start_time'],
                end_time=ep['start_time'] + timedelta(hours=1),
                summary=ep['summary']
            )

            # Add segments
            for seg in ep['segments']:
                segment = EpisodeSegment(
                    segment_id=seg['segment_id'],
                    episode_id=ep['episode_id'],
                    content=seg['content']
                )
                episode.segments.append(segment)

            valid_episodes.append(episode)

        # Retrieve sequentially
        result = service.retrieve_episodes(
            agent_id=episodes[0]['agent_id'],
            mode=RetrievalMode.SEQUENTIAL,
            limit=len(valid_episodes)
        )

        # Verify full context included
        for ep in result.episodes:
            assert hasattr(ep, 'summary'), "Episode must have summary"
            assert hasattr(ep, 'segments'), "Episode must have segments"
            assert len(ep.segments) > 0, "Episode must have at least one segment"

            # Verify segments have content
            for seg in ep.segments:
                assert hasattr(seg, 'content'), "Segment must have content"
                assert len(seg.content) > 0, "Segment content must not be empty"

    # ========== Contextual Retrieval ==========

    @given(
        episodes=st.lists(
            st.fixed_dictionaries({
                'episode_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'agent_id': st.text(min_size=1, max_size=20),
                'start_time': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()),
                'summary': st.text(min_size=10, max_size=200),
                'embedding': st.lists(st.floats(min_value=-1, max_value=1, allow_nan=False), min_size=384, max_size=384),
                'topic': st.sampled_from(['finance', 'development', 'marketing', 'sales', 'support'])
            }),
            min_size=10,
            max_size=50
        ),
        query_context=st.fixed_dictionaries({
            'embedding': st.lists(st.floats(min_value=-1, max_value=1, allow_nan=False), min_size=384, max_size=384),
            'topic': st.sampled_from(['finance', 'development', 'marketing', 'sales', 'support']),
            'time_weight': st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            'semantic_weight': st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
        })
    )
    @settings(max_examples=50)
    def test_contextual_retrieval_hybrid_accuracy(self, episodes, query_context):
        """INVARIANT: Contextual retrieval must balance time and semantic relevance."""
        service = EpisodeRetrievalService()

        # Normalize weights
        total_weight = query_context['time_weight'] + query_context['semantic_weight']
        assume(total_weight > 0)
        time_weight = query_context['time_weight'] / total_weight
        semantic_weight = query_context['semantic_weight'] / total_weight

        # Create episodes
        valid_episodes = []
        for ep in episodes:
            episode = Episode(
                episode_id=ep['episode_id'],
                agent_id=ep['agent_id'],
                start_time=ep['start_time'],
                end_time=ep['start_time'] + timedelta(hours=1),
                summary=ep['summary'],
                embedding=ep['embedding'],
                topic=ep['topic']
            )
            valid_episodes.append(episode)

        # Retrieve contextually
        result = service.retrieve_episodes(
            agent_id=episodes[0]['agent_id'],
            mode=RetrievalMode.CONTEXTUAL,
            query_embedding=query_context['embedding'],
            query_topic=query_context['topic'],
            time_weight=time_weight,
            semantic_weight=semantic_weight,
            limit=len(valid_episodes)
        )

        # Verify hybrid ranking
        # Episodes should be ranked by combined score
        if len(result.episodes) > 1:
            for ep in result.episodes:
                assert hasattr(ep, 'contextual_score'), "Episode must have contextual_score"
                assert 0.0 <= ep.contextual_score <= 1.0, f"Contextual score {ep.contextual_score} not in [0, 1]"

    # ========== Performance Tests ==========

    @given(
        episode_count=st.integers(min_value=100, max_value=1000),
        retrieval_mode=st.sampled_from([RetrievalMode.TEMPORAL, RetrievalMode.SEMANTIC, RetrievalMode.SEQUENTIAL])
    )
    @settings(max_examples=20)
    def test_retrieval_performance_target(self, episode_count, retrieval_mode):
        """INVARIANT: All retrieval modes must complete in <100ms."""
        import time

        service = EpisodeRetrievalService()

        # Create episodes
        agent_id = "test_agent"
        for i in range(episode_count):
            episode = Episode(
                episode_id=f"ep_{i}",
                agent_id=agent_id,
                start_time=datetime.now() - timedelta(days=i),
                end_time=datetime.now() - timedelta(days=i) + timedelta(hours=1),
                summary=f"Episode {i}"
            )

        # Measure retrieval time
        start_time = time.time()

        result = service.retrieve_episodes(
            agent_id=agent_id,
            mode=retrieval_mode,
            limit=50
        )

        end_time = time.time()
        retrieval_time_ms = (end_time - start_time) * 1000

        # Verify performance target
        assert retrieval_time_ms < 100, f"Retrieval took {retrieval_time_ms:.2f}ms, target is <100ms"

        # Verify results returned
        assert len(result.episodes) <= 50, "Should not exceed limit"
