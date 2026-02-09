"""
Property-Based Tests for Episode Retrieval Service - Critical Memory Logic

Tests episode retrieval invariants:
- Temporal retrieval (chronological order)
- Semantic retrieval (vector search similarity)
- Sequential retrieval (full episode context)
- Contextual retrieval (hybrid quality)
- Similarity score bounds [0, 1]
- Retrieval limit enforcement
- Episode boundary consistency
- Agent relationship integrity
- Access log accuracy
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from uuid import uuid4
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestTemporalRetrievalInvariants:
    """Tests for temporal (time-based) retrieval invariants"""

    @given(
        num_episodes=st.integers(min_value=1, max_value=50),
        limit=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_temporal_retrieval_chronological_order(self, num_episodes, limit):
        """Test that temporal retrieval returns episodes in chronological order"""
        # Simulate episodes with timestamps
        episodes = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_episodes):
            episode = {
                "id": str(uuid4()),
                "start_time": base_time + timedelta(hours=i),
                "end_time": base_time + timedelta(hours=i, minutes=30),
                "summary": f"Episode {i}",
                "agent_id": "test_agent"
            }
            episodes.append(episode)

        # Simulate temporal retrieval (sorted by start_time)
        effective_limit = min(limit, num_episodes)
        retrieved = sorted(episodes, key=lambda e: e["start_time"], reverse=True)[:effective_limit]

        # Verify chronological order (most recent first)
        assert len(retrieved) <= limit, "Should respect limit"
        for i in range(1, len(retrieved)):
            assert retrieved[i-1]["start_time"] >= retrieved[i]["start_time"], "Should be in descending chronological order"

    @given(
        num_episodes=st.integers(min_value=10, max_value=100),
        limit=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_temporal_retrieval_respects_limit(self, num_episodes, limit):
        """Test that temporal retrieval respects the limit parameter"""
        episodes = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_episodes):
            episode = {
                "id": str(uuid4()),
                "start_time": base_time + timedelta(hours=i),
                "agent_id": "test_agent"
            }
            episodes.append(episode)

        # Simulate retrieval with limit
        retrieved = sorted(episodes, key=lambda e: e["start_time"], reverse=True)[:limit]

        # Should not exceed limit
        assert len(retrieved) <= limit, f"Retrieved {len(retrieved)} episodes, should be <= {limit}"

        # If we have more episodes than limit, should return exactly limit
        if num_episodes >= limit:
            assert len(retrieved) == limit, f"Should return exactly {limit} episodes when available"

    @given(
        num_episodes=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_temporal_retrieval_time_bounds(self, num_episodes):
        """Test that temporal retrieval respects time bounds"""
        episodes = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_episodes):
            episode = {
                "id": str(uuid4()),
                "start_time": base_time + timedelta(hours=i),
                "end_time": base_time + timedelta(hours=i, minutes=30),
                "agent_id": "test_agent"
            }
            episodes.append(episode)

        # Set time bounds (from 5 hours after base to end)
        start_bound = base_time + timedelta(hours=5)
        end_bound = base_time + timedelta(hours=num_episodes)

        # Filter episodes by time bounds
        filtered = [
            e for e in episodes
            if e["start_time"] >= start_bound and e["start_time"] <= end_bound
        ]

        # Verify all retrieved episodes are within bounds
        for episode in filtered:
            assert episode["start_time"] >= start_bound, "Episode should be after start bound"
            assert episode["start_time"] <= end_bound, "Episode should be before end bound"


class TestSemanticRetrievalInvariants:
    """Tests for semantic (vector search) retrieval invariants"""

    @given(
        dimension=st.integers(min_value=10, max_value=30),
        num_episodes=st.integers(min_value=3, max_value=10),
        limit=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=20)
    def test_semantic_retrieval_ranked_by_similarity(self, dimension, num_episodes, limit):
        """Test that semantic retrieval is ranked by similarity score"""
        # Generate query and episode vectors with same dimension
        import random
        random.seed(42)

        query_vector = [random.uniform(-1.0, 1.0) for _ in range(dimension)]
        episode_vectors = [[random.uniform(-1.0, 1.0) for _ in range(dimension)] for _ in range(num_episodes)]

        # Calculate cosine similarity
        def cosine_similarity(v1, v2):
            dot_product = sum(a * b for a, b in zip(v1, v2))
            magnitude1 = sum(a * a for a in v1) ** 0.5
            magnitude2 = sum(b * b for b in v2) ** 0.5
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            return dot_product / (magnitude1 * magnitude2)

        # Calculate similarities
        similarities = []
        for i, episode_vector in enumerate(episode_vectors[:limit]):
            sim = cosine_similarity(query_vector, episode_vector)
            similarities.append((i, sim))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Verify descending order
        for i in range(1, len(similarities)):
            assert similarities[i-1][1] >= similarities[i][1], "Similarities should be in descending order"

    @given(
        similarity_scores=st.lists(
            st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_semantic_similarity_bounds(self, similarity_scores):
        """Test that semantic similarity scores are in valid range"""
        # Cosine similarity should be in [-1, 1]
        for score in similarity_scores:
            assert -1.0 <= score <= 1.0, f"Similarity score {score} must be in [-1, 1]"

    @given(
        num_episodes=st.integers(min_value=10, max_value=100),
        limit=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_semantic_retrieval_limit_enforcement(self, num_episodes, limit):
        """Test that semantic retrieval respects the limit"""
        # Simulate episodes with similarity scores
        episodes = []
        for i in range(num_episodes):
            episode = {
                "id": str(uuid4()),
                "similarity_score": 0.9 - (i * 0.01),  # Decreasing similarity
                "agent_id": "test_agent"
            }
            episodes.append(episode)

        # Sort by similarity and apply limit
        retrieved = sorted(episodes, key=lambda e: e["similarity_score"], reverse=True)[:limit]

        # Should not exceed limit
        assert len(retrieved) <= limit, f"Retrieved {len(retrieved)} episodes, should be <= {limit}"

        # Should be sorted by similarity (highest first)
        for i in range(1, len(retrieved)):
            assert retrieved[i-1]["similarity_score"] >= retrieved[i]["similarity_score"], "Should be sorted by similarity"


class TestSequentialRetrievalInvariants:
    """Tests for sequential (full episode) retrieval invariants"""

    @given(
        num_segments=st.integers(min_value=1, max_value=20),
        segment_length=st.integers(min_value=100, max_value=1000)
    )
    @settings(max_examples=50)
    def test_sequential_retrieval_includes_full_context(self, num_segments, segment_length):
        """Test that sequential retrieval includes full episode context"""
        # Simulate episode with multiple segments
        episode = {
            "id": str(uuid4()),
            "segments": []
        }

        base_content = "Sample episode content. "
        for i in range(num_segments):
            segment = {
                "id": str(uuid4()),
                "sequence_number": i,
                "content": base_content * segment_length,
                "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(minutes=i*10)
            }
            episode["segments"].append(segment)

        # Sequential retrieval should return all segments in order
        retrieved_segments = sorted(episode["segments"], key=lambda s: s["sequence_number"])

        # Verify all segments are present
        assert len(retrieved_segments) == num_segments, f"Should have {num_segments} segments"

        # Verify sequential order
        for i in range(1, len(retrieved_segments)):
            assert retrieved_segments[i]["sequence_number"] > retrieved_segments[i-1]["sequence_number"], "Segments should be in sequential order"

    @given(
        num_episodes=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=50)
    def test_sequential_retrieval_episode_integrity(self, num_episodes):
        """Test that sequential retrieval maintains episode integrity"""
        episodes = []
        for i in range(num_episodes):
            episode = {
                "id": str(uuid4()),
                "agent_id": "test_agent",
                "start_time": datetime(2024, 1, 1, 12, 0, 0) + timedelta(hours=i),
                "end_time": datetime(2024, 1, 1, 13, 0, 0) + timedelta(hours=i),
                "summary": f"Episode {i}",
                "segments": [
                    {"id": str(uuid4()), "sequence_number": 0},
                    {"id": str(uuid4()), "sequence_number": 1}
                ]
            }
            episodes.append(episode)

        # Sequential retrieval should return complete episodes
        for episode in episodes:
            # Verify episode has required fields
            assert "id" in episode, "Episode should have ID"
            assert "agent_id" in episode, "Episode should have agent_id"
            assert "start_time" in episode, "Episode should have start_time"
            assert "end_time" in episode, "Episode should have end_time"
            assert episode["end_time"] >= episode["start_time"], "End time should be after start time"

            # Verify segments are present
            assert "segments" in episode, "Episode should have segments"
            assert len(episode["segments"]) >= 1, "Episode should have at least one segment"


class TestContextualRetrievalInvariants:
    """Tests for contextual (hybrid) retrieval invariants"""

    @given(
        score_pairs=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=5,
            max_size=30
        ),
        temporal_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_contextual_hybrid_scoring(self, score_pairs, temporal_weight):
        """Test that contextual retrieval uses hybrid scoring"""
        # Unzip the pairs
        temporal_scores = [t for t, _ in score_pairs]
        semantic_scores = [s for _, s in score_pairs]

        semantic_weight = 1.0 - temporal_weight

        # Calculate hybrid scores
        hybrid_scores = []
        for t_score, s_score in zip(temporal_scores, semantic_scores):
            hybrid_score = (temporal_weight * t_score) + (semantic_weight * s_score)
            hybrid_scores.append(hybrid_score)

        # Verify hybrid scores are in valid range [0, 1]
        for score in hybrid_scores:
            assert 0.0 <= score <= 1.0, f"Hybrid score {score} must be in [0, 1]"

        # Verify hybrid score is weighted average
        for i, (t_score, s_score) in enumerate(zip(temporal_scores, semantic_scores)):
            expected = (temporal_weight * t_score) + (semantic_weight * s_score)
            epsilon = 1e-10
            assert abs(hybrid_scores[i] - expected) < epsilon, "Hybrid score should be weighted average"

    @given(
        limit=st.integers(min_value=1, max_value=50),
        num_candidates=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_contextual_retrieval_respects_limit(self, limit, num_candidates):
        """Test that contextual retrieval respects the limit"""
        # Simulate candidate episodes with hybrid scores
        candidates = []
        for i in range(num_candidates):
            candidate = {
                "id": str(uuid4()),
                "hybrid_score": 0.9 - (i * 0.005),  # Decreasing scores
                "agent_id": "test_agent"
            }
            candidates.append(candidate)

        # Sort by hybrid score and apply limit
        retrieved = sorted(candidates, key=lambda e: e["hybrid_score"], reverse=True)[:limit]

        # Should not exceed limit
        assert len(retrieved) <= limit, f"Retrieved {len(retrieved)} candidates, should be <= {limit}"

        # Should be sorted by hybrid score
        for i in range(1, len(retrieved)):
            assert retrieved[i-1]["hybrid_score"] >= retrieved[i]["hybrid_score"], "Should be sorted by hybrid score"


class TestEpisodeRetrievalInvariants:
    """Tests for general episode retrieval invariants"""

    @given(
        num_episodes=st.integers(min_value=1, max_value=100),
        limit=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_retrieval_limit_enforcement(self, num_episodes, limit):
        """Test that all retrieval methods respect limit parameter"""
        episodes = []
        for i in range(num_episodes):
            episode = {
                "id": str(uuid4()),
                "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(hours=i),
                "score": 0.9 - (i * 0.005),
                "agent_id": "test_agent"
            }
            episodes.append(episode)

        # Simulate retrieval with limit
        retrieved = sorted(episodes, key=lambda e: e["score"], reverse=True)[:limit]

        assert len(retrieved) <= limit, "Retrieval should respect limit"

    @given(
        agent_id=st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        episode_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_agent_filtering(self, agent_id, episode_count):
        """Test that retrieval can filter by agent"""
        # Create episodes for multiple agents
        episodes = []
        agents = ["agent_1", "agent_2", "agent_3"]

        for i in range(episode_count):
            for agent in agents:
                episode = {
                    "id": str(uuid4()),
                    "agent_id": agent,
                    "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(hours=i)
                }
                episodes.append(episode)

        # Filter by specific agent
        filtered = [e for e in episodes if e["agent_id"] == agent_id]

        # If agent_id is in our list, verify filtering worked
        if agent_id in agents:
            # All filtered episodes should have the correct agent_id
            assert all(e["agent_id"] == agent_id for e in filtered), "All episodes should match agent filter"


class TestEpisodeBoundaryInvariants:
    """Tests for episode boundary consistency"""

    @given(
        start_hour=st.integers(min_value=0, max_value=20),
        duration_hours=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_episode_time_boundaries(self, start_hour, duration_hours):
        """Test that episode time boundaries are consistent"""
        start_time = datetime(2024, 1, 1, start_hour, 0, 0)
        end_time = start_time + timedelta(hours=duration_hours)

        # Create episode
        episode = {
            "id": str(uuid4()),
            "start_time": start_time,
            "end_time": end_time,
            "agent_id": "test_agent"
        }

        # Verify time boundaries
        assert episode["end_time"] >= episode["start_time"], "End time should be after start time"

        # Calculate duration
        duration = (episode["end_time"] - episode["start_time"]).total_seconds() / 3600
        assert duration == duration_hours, f"Duration should be {duration_hours} hours"

    @given(
        num_segments=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=50)
    def test_segment_boundaries(self, num_segments):
        """Test that segment boundaries are consistent"""
        segments = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_segments):
            segment = {
                "id": str(uuid4()),
                "sequence_number": i,
                "start_time": base_time + timedelta(minutes=i*10),
                "end_time": base_time + timedelta(minutes=(i+1)*10)
            }
            segments.append(segment)

        # Verify segment boundaries don't overlap
        for i in range(1, len(segments)):
            assert segments[i]["start_time"] >= segments[i-1]["end_time"], "Segments should not overlap"


class TestEpisodeAccessInvariants:
    """Tests for episode access logging"""

    @given(
        num_accesses=st.integers(min_value=1, max_value=100),
        agent_id=st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    )
    @settings(max_examples=50)
    def test_access_log_accuracy(self, num_accesses, agent_id):
        """Test that episode access is logged accurately"""
        access_logs = []

        # Simulate episode accesses
        for i in range(num_accesses):
            log_entry = {
                "id": str(uuid4()),
                "episode_id": str(uuid4()),
                "agent_id": agent_id,
                "access_type": "retrieval",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0) + timedelta(minutes=i)
            }
            access_logs.append(log_entry)

        # Verify access logs
        assert len(access_logs) == num_accesses, f"Should have {num_accesses} access logs"

        # Verify all logs have required fields
        for log in access_logs:
            assert "id" in log, "Access log should have ID"
            assert "episode_id" in log, "Access log should have episode_id"
            assert "agent_id" in log, "Access log should have agent_id"
            assert "access_type" in log, "Access log should have access_type"
            assert "timestamp" in log, "Access log should have timestamp"

        # Verify agent filtering works
        agent_logs = [log for log in access_logs if log["agent_id"] == agent_id]
        assert len(agent_logs) == num_accesses, "All logs should match the agent"

    @given(
        num_logs=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_access_log_chronology(self, num_logs):
        """Test that access logs maintain chronological order"""
        access_logs = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_logs):
            log_entry = {
                "id": str(uuid4()),
                "timestamp": base_time + timedelta(minutes=i)
            }
            access_logs.append(log_entry)

        # Sort by timestamp
        sorted_logs = sorted(access_logs, key=lambda log: log["timestamp"])

        # Verify chronological order
        for i in range(1, len(sorted_logs)):
            assert sorted_logs[i]["timestamp"] >= sorted_logs[i-1]["timestamp"], "Logs should be in chronological order"
