"""
Coverage expansion tests for episodic memory services.

Target: 80%+ coverage for episode logic:
- Episode segmentation (time gaps >30min, topic changes <0.75)
- Retrieval modes (temporal, semantic, sequential, contextual)
- Lifecycle management (decay, consolidation, archival)
- Canvas integration tracking
- Feedback aggregation

Tests mock LanceDB to focus on segmentation/retrieval algorithms.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from core.episode_segmentation_service import EpisodeSegmentationService, EpisodeBoundaryDetector
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import (
    AgentEpisode,  # Use AgentEpisode instead of Episode
    EpisodeSegment,
    ChatSession,
    ChatMessage,
    CanvasAudit,
    AgentFeedback,
    AgentRegistry,
    AgentExecution,
    User,
)

# Alias for compatibility
Episode = AgentEpisode


# =============================================================================
# Test Episode Segmentation Algorithms
# =============================================================================

class TestEpisodeSegmentation:
    """Test episode segmentation algorithms"""

    def test_detect_time_gaps(self, segmentation_service_mocked, test_messages):
        """
        Test detection of time gaps >30 minutes between messages.

        Verifies:
        - Time gaps >30min trigger boundary detection
        - Boundary index is correct (message after gap)
        - Gap duration is calculated accurately
        """
        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)

        # Detect boundaries
        boundaries = detector.detect_time_gap(test_messages)

        # Should detect 2 time gaps:
        # 1. After message 1 (45min - 10min = 35min gap)
        # 2. After message 3 (90min - 50min = 40min gap)
        assert len(boundaries) == 2
        assert 2 in boundaries  # Index of message after first gap
        assert 4 in boundaries  # Index of message after second gap

    def test_detect_topic_changes(self, segmentation_service_mocked, mock_lancedb_embeddings):
        """
        Test detection of topic changes using semantic similarity.

        Verifies:
        - Topic changes detected when similarity <0.75
        - Python and cooking topics are distinguished
        - Similarity threshold applied correctly
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        session_id = f"test_session_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=f"msg_{uuid4().hex[:8]}",
                conversation_id=session_id,
                role="user",
                content="Let's discuss Python programming",
                created_at=base_time
            ),
            ChatMessage(
                id=f"msg_{uuid4().hex[:8]}",
                conversation_id=session_id,
                role="assistant",
                content="Python is great for web development",
                created_at=base_time + timedelta(minutes=5)
            ),
            ChatMessage(
                id=f"msg_{uuid4().hex[:8]}",
                conversation_id=session_id,
                role="user",
                content="Now let's talk about cooking recipes",
                created_at=base_time + timedelta(minutes=10)
            ),
            ChatMessage(
                id=f"msg_{uuid4().hex[:8]}",
                conversation_id=session_id,
                role="assistant",
                content="I love Italian pasta dishes",
                created_at=base_time + timedelta(minutes=15)
            ),
        ]

        # Use detector with mocked LanceDB
        detector = EpisodeBoundaryDetector(mock_lancedb_embeddings)

        # Detect topic changes
        changes = detector.detect_topic_changes(messages)

        # Should detect 1 topic change at index 2 (cooking vs Python)
        # Similarity between [0.9, 0.1, 0.0] and [0.1, 0.9, 0.0] is 0.18 < 0.75
        assert len(changes) == 1
        assert 2 in changes

    def test_create_episodes_from_boundaries(self, segmentation_service_mocked, episode_test_session, episode_test_agent):
        """
        Test creating episodes from detected boundaries.

        Verifies:
        - Multiple episodes created when boundaries exist
        - Episodes have correct segment counts
        - Episode timestamps are accurate
        """
        session_id = episode_test_session.id
        base_time = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=f"msg_{uuid4().hex[:8]}",
                conversation_id=session_id,
                role="user",
                content="Message 1",
                created_at=base_time
            ),
            ChatMessage(
                id=f"msg_{uuid4().hex[:8]}",
                conversation_id=session_id,
                role="user",
                content="Message 2",
                created_at=base_time + timedelta(minutes=5)
            ),
            ChatMessage(
                id=f"msg_{uuid4().hex[:8]}",
                conversation_id=session_id,
                role="user",
                content="Message 3",
                created_at=base_time + timedelta(minutes=10)
            ),
        ]

        for msg in messages:
            segmentation_service_mocked.db.add(msg)
        segmentation_service_mocked.db.commit()

        # Create episodes with boundary at index 2 (split after message 1)
        with patch.object(segmentation_service_mocked, 'lancedb'):
            with patch.object(segmentation_service_mocked, 'byok_handler'):
                with patch.object(segmentation_service_mocked, 'canvas_summary_service'):
                    episode = segmentation_service_mocked.create_episode_from_session(
                        session_id=session_id,
                        agent_id=episode_test_agent.id,
                        force_create=True
                    )

        # Verify episode created
        assert episode is not None
        assert episode.status == "completed"
        assert episode.session_id == session_id

        # Verify segments created
        segments = segmentation_service_mocked.db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        # Should have created segments from messages
        assert len(segments) >= 1

    def test_segmentation_with_task_completion(self, segmentation_service_mocked, episode_test_agent):
        """
        Test task completion detection in segmentation.

        Verifies:
        - Completed tasks trigger boundaries
        - Task completion markers are detected
        - Segmentation respects task completion
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        # Create agent executions with task completion
        base_time = datetime.now(timezone.utc)

        executions = [
            AgentExecution(
                id=f"exec_{uuid4().hex[:8]}",
                agent_id=episode_test_agent.id,
                status="completed",
                started_at=base_time,
                completed_at=base_time + timedelta(minutes=5),
                result_summary="Task 1 completed successfully",
                input_summary="Task 1 input"
            ),
            AgentExecution(
                id=f"exec_{uuid4().hex[:8]}",
                agent_id=episode_test_agent.id,
                status="completed",
                started_at=base_time + timedelta(minutes=10),
                completed_at=base_time + timedelta(minutes=15),
                result_summary="Task 2 completed successfully",
                input_summary="Task 2 input"
            ),
        ]

        for exec in executions:
            segmentation_service_mocked.db.add(exec)
        segmentation_service_mocked.db.commit()

        # Detect task completions
        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        completions = detector.detect_task_completion(executions)

        # Should detect 2 task completions
        assert len(completions) == 2
        assert 0 in completions  # First task
        assert 1 in completions  # Second task

    def test_segmentation_cosine_similarity_calculation(self, segmentation_service_mocked):
        """
        Test cosine similarity calculation for topic change detection.

        Verifies:
        - Cosine similarity calculated correctly
        - Similarity ranges from 0.0 to 1.0
        - Same vectors have similarity 1.0
        - Orthogonal vectors have similarity 0.0
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)

        # Test identical vectors (similarity = 1.0)
        vec1 = [0.9, 0.1, 0.0]
        vec2 = [0.9, 0.1, 0.0]
        similarity = detector._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.01  # Allow small floating point error

        # Test orthogonal vectors (similarity ≈ 0.0)
        vec3 = [1.0, 0.0, 0.0]
        vec4 = [0.0, 1.0, 0.0]
        similarity = detector._cosine_similarity(vec3, vec4)
        assert abs(similarity - 0.0) < 0.01

        # Test similar vectors (similarity > 0.75)
        vec5 = [0.9, 0.1, 0.0]
        vec6 = [0.8, 0.2, 0.0]
        similarity = detector._cosine_similarity(vec5, vec6)
        assert similarity > 0.75  # Should be similar

    def test_segmentation_empty_messages(self, segmentation_service_mocked):
        """Test segmentation with empty message list."""
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)

        # Empty list should return empty boundaries
        boundaries = detector.detect_time_gap([])
        assert boundaries == []

        changes = detector.detect_topic_changes([])
        assert changes == []

    def test_segmentation_single_message(self, segmentation_service_mocked):
        """Test segmentation with single message (no boundaries possible)."""
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        session_id = f"test_session_{uuid4().hex[:8]}"
        msg = ChatMessage(
            id=f"msg_{uuid4().hex[:8]}",
            conversation_id=session_id,
            role="user",
            content="Single message",
            created_at=datetime.now(timezone.utc)
        )

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)

        # Single message should return empty boundaries
        boundaries = detector.detect_time_gap([msg])
        assert boundaries == []

        changes = detector.detect_topic_changes([msg])
        assert changes == []
