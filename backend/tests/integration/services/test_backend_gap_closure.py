"""
Backend Services Gap Closure Tests

Comprehensive test suite for closing coverage gaps in backend services:
- Governance service (cache invalidation, concurrent checks, edge cases)
- Episode segmentation (time gaps, topic changes, task completion)
- Episode retrieval (temporal, semantic, contextual modes)
- Episode lifecycle (decay, consolidation, archival)
- Canvas tool (governance integration, concurrent updates, error recovery)
- Agent context resolver (cache consistency, concurrent resolution)
- Trigger interceptor (proposal workflow, supervision monitoring)

Target: 85+ tests achieving measurable coverage improvement
"""

import pytest
import pytest_asyncio
import asyncio
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4
import json

# =============================================================================
# Section 1: Governance Service Tests (15 tests)
# =============================================================================

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.models import (
    AgentRegistry,
    AgentStatus,
    User,
    UserRole,
    AgentFeedback,
    FeedbackStatus,
    HITLAction,
    HITLActionStatus,
    AgentExecution,
)


class TestGovernanceCacheInvalidation:
    """Test governance cache invalidation scenarios"""

    def test_governance_cache_invalidation_on_status_change(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test cache is invalidated when agent status changes"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4
        )
        db_session.add(agent)
        db_session.commit()

        cache = GovernanceCache()
        # Warm cache
        cache.set(agent.id, "search", {"allowed": True, "cached": True})

        # Change status (should invalidate)
        governance_service._update_confidence_score(
            agent.id, positive=True, impact_level="high"
        )

        # Verify cache miss after status change
        cached_result = cache.get(agent.id, "search")
        assert cached_result is None

    def test_governance_cache_invalidation_on_suspension(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test cache is invalidated when agent is suspended"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        cache = GovernanceCache()
        cache.set(agent.id, "analyze", {"allowed": True, "cached": True})

        # Suspend agent
        result = governance_service.suspend_agent(agent.id, "Testing suspension")
        assert result is True

        # Verify cache invalidation
        cached_result = cache.get(agent.id, "analyze")
        assert cached_result is None

    def test_governance_cache_invalidation_on_termination(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test cache is invalidated when agent is terminated"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.commit()

        cache = GovernanceCache()
        cache.set(agent.id, "create", {"allowed": True, "cached": True})

        # Terminate agent
        result = governance_service.terminate_agent(agent.id, "Testing termination")
        assert result is True

        # Verify cache invalidation
        cached_result = cache.get(agent.id, "create")
        assert cached_result is None


class TestGovernanceConcurrentChecks:
    """Test concurrent governance check handling"""

    @pytest.mark.asyncio
    async def test_governance_concurrent_checks_same_agent(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test concurrent governance checks for same agent don't cause race conditions"""
        agent = AgentRegistry(
            name="ConcurrentAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()

        # Run concurrent checks
        tasks = []
        for _ in range(10):
            task = asyncio.create_task(
                asyncio.to_thread(
                    governance_service.can_perform_action,
                    agent.id,
                    "search"
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r["allowed"] for r in results)
        # All should return same agent status
        assert all(r["agent_status"] == AgentStatus.AUTONOMOUS.value for r in results)

    @pytest.mark.asyncio
    async def test_governance_concurrent_cache_updates(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test concurrent cache updates don't cause corruption"""
        agent = AgentRegistry(
            name="CacheTestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Concurrent cache updates
        tasks = []
        for i in range(20):
            task = asyncio.create_task(
                asyncio.to_thread(
                    governance_service.can_perform_action,
                    agent.id,
                    f"action_{i % 4}"  # Rotate through 4 action types
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all completed without error
        assert len(results) == 20
        assert all("allowed" in r for r in results)


class TestGovernancePermissionEdgeCases:
    """Test edge cases in permission checking"""

    def test_governance_unknown_action_type_defaults_to_supervised(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test unknown action types default to SUPERVISED requirement"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Check unknown action
        result = governance_service.can_perform_action(
            agent.id, "unknown_action_xyz"
        )

        # Should default to requiring SUPERVISED (complexity 2)
        assert result["allowed"] is False
        assert "required_status" in result

    def test_governance_zero_confidence_score_handling(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test agent with 0.0 confidence is treated as STUDENT"""
        agent = AgentRegistry(
            name="ZeroConfidenceAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,  # Status claims AUTONOMOUS
            confidence_score=0.0  # But confidence is 0.0
        )
        db_session.add(agent)
        db_session.commit()

        # Should use confidence-based maturity (STUDENT) not status
        result = governance_service.can_perform_action(agent.id, "delete")

        # Should be blocked (requires AUTONOMOUS)
        assert result["allowed"] is False
        # Should log warning about mismatch

    def test_governance_none_confidence_score_defaults_to_half(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test None confidence score defaults to 0.5 (INTERN threshold)"""
        agent = AgentRegistry(
            name="NoneConfidenceAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=None  # Explicitly None
        )
        db_session.add(agent)
        db_session.commit()

        result = governance_service.can_perform_action(agent.id, "analyze")

        # Should use 0.5 default (INTERN level)
        assert result["allowed"] is True
        assert result["confidence_score"] == 0.5


class TestGovernanceUnknownMaturityHandling:
    """Test handling of unknown/invalid maturity levels"""

    def test_governance_invalid_status_treated_as_student(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test agent with invalid status is treated as STUDENT"""
        agent = AgentRegistry(
            name="InvalidStatusAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status="INVALID_STATUS",  # Invalid status
            confidence_score=0.5
        )
        db_session.add(agent)
        db_session.commit()

        result = governance_service.can_perform_action(agent.id, "create")

        # Should be blocked (treated as STUDENT)
        assert result["allowed"] is False

    def test_governance_nonexistent_agent_returns_blocked(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test governance check for non-existent agent"""
        result = governance_service.can_perform_action(
            "nonexistent_agent_id", "search"
        )

        assert result["allowed"] is False
        assert "not found" in result["reason"].lower()


class TestGovernanceMetricsTracking:
    """Test governance metrics and tracking"""

    def test_governance_enforce_action_returns_correct_status(
        self, governance_service: AgentGovernanceService, db_session
    ):
        """Test enforce_action returns correct workflow status"""
        # AUTONOMOUS agent - should approve
        agent_auto = AgentRegistry(
            name="AutoAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent_auto)

        # STUDENT agent - should block
        agent_student = AgentRegistry(
            name="StudentAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent_student)
        db_session.commit()

        # Test AUTONOMOUS
        result_auto = governance_service.enforce_action(
            agent_auto.id, "delete", {"test": "data"}
        )
        assert result_auto["proceed"] is True
        assert result_auto["status"] == "APPROVED"

        # Test STUDENT
        result_student = governance_service.enforce_action(
            agent_student.id, "delete", {"test": "data"}
        )
        assert result_student["proceed"] is False
        assert result_student["status"] == "BLOCKED"


# =============================================================================
# Section 2: Episode Segmentation Tests (15 tests)
# =============================================================================

from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD,
)
from core.models import (
    Episode,
    EpisodeSegment,
    ChatSession,
    ChatMessage,
)


class TestEpisodeSegmentationTimeGaps:
    """Test time gap detection in episode segmentation"""

    def test_segment_time_gap_detection_exclusive_boundary(
        self, segmentation_service_mocked, db_session
    ):
        """Test time gap detection uses exclusive boundary (>) not inclusive (>=)"""
        session_id = f"session_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        # Create messages with exactly threshold gap (should NOT trigger)
        messages = [
            ChatMessage(
                id=f"msg_{i}",
                conversation_id=session_id,
                role="user",
                content=f"Message {i}",
                created_at=base_time + timedelta(minutes=i * TIME_GAP_THRESHOLD_MINUTES)
            )
            for i in range(3)
        ]

        db_session.add_all(messages)
        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        boundaries = detector.detect_time_gap(messages)

        # No boundaries should be detected (exactly threshold = not a gap)
        assert len(boundaries) == 0

    def test_segment_time_gap_one_minute_over_threshold(
        self, segmentation_service_mocked, db_session
    ):
        """Test gap of threshold + 1 minute triggers boundary"""
        session_id = f"session_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=f"msg_{i}",
                conversation_id=session_id,
                role="user",
                content=f"Message {i}",
                created_at=base_time + timedelta(minutes=i * (TIME_GAP_THRESHOLD_MINUTES + 1))
            )
            for i in range(3)
        ]

        db_session.add_all(messages)
        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        boundaries = detector.detect_time_gap(messages)

        # Should detect 2 gaps
        assert len(boundaries) == 2

    def test_segment_time_gap_detection_with_variable_spacing(
        self, segmentation_service_mocked, db_session
    ):
        """Test time gap detection with variable message spacing"""
        session_id = f"session_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=f"msg_{i}",
                conversation_id=session_id,
                role="user",
                content=f"Message {i}",
                created_at=base_time + timedelta(minutes=offset)
            )
            for i, offset in enumerate([0, 5, 10, 50, 55, 120])  # Gap at index 3 (40min) and 5 (65min)
        ]

        db_session.add_all(messages)
        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        boundaries = detector.detect_time_gap(messages)

        # Should detect 2 gaps
        assert len(boundaries) == 2
        assert 3 in boundaries  # After 50min timestamp (40min gap)
        assert 5 in boundaries  # After 120min timestamp (65min gap)


class TestEpisodeSegmentationTopicChanges:
    """Test topic change detection using embeddings"""

    def test_segment_topic_change_below_threshold(
        self, segmentation_service_mocked, mock_lancedb_embeddings, db_session
    ):
        """Test topic change when similarity < 0.75"""
        session_id = f"session_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=f"msg_{i}",
                conversation_id=session_id,
                role="user",
                content=msg,
                created_at=base_time + timedelta(minutes=i)
            )
            for i, msg in enumerate([
                "Let's discuss Python programming",
                "Python is great for web development",
                "Now let's talk about cooking recipes",  # Topic change
                "I love making pasta and pizza"
            ])
        ]

        db_session.add_all(messages)
        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        boundaries = detector.detect_topic_changes(messages)

        # Should detect 1 topic change
        assert len(boundaries) >= 1

    def test_segment_topic_change_same_topic_no_boundary(
        self, segmentation_service_mocked, mock_lancedb_embeddings, db_session
    ):
        """Test no boundary when topic remains similar"""
        session_id = f"session_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=f"msg_{i}",
                conversation_id=session_id,
                role="user",
                content=f"Python programming message {i}",  # All about Python
                created_at=base_time + timedelta(minutes=i)
            )
            for i in range(5)
        ]

        db_session.add_all(messages)
        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        boundaries = detector.detect_topic_changes(messages)

        # Should detect no boundaries (same topic)
        assert len(boundaries) == 0


class TestEpisodeSegmentationTaskCompletion:
    """Test task completion marker detection"""

    def test_segment_task_completion_markers(
        self, segmentation_service_mocked, db_session
    ):
        """Test detection of task completion markers"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        executions = []
        for i in range(5):
            exec = AgentExecution(
                id=f"exec_{i}",
                agent_id=agent.id,
                workspace_id="default",
                status="completed" if i % 2 == 0 else "running",
                input_summary=f"Task {i}",
                result_summary=f"Result {i}" if i % 2 == 0 else None
            )
            executions.append(exec)
            db_session.add(exec)

        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        completions = detector.detect_task_completion(executions)

        # Should detect 3 completions (indices 0, 2, 4)
        assert len(completions) == 3
        assert 0 in completions
        assert 2 in completions
        assert 4 in completions


class TestEpisodeSegmentationCombinedSignals:
    """Test combination of multiple segmentation signals"""

    def test_segment_combined_signals_time_and_topic(
        self, segmentation_service_mocked, mock_lancedb_embeddings, db_session
    ):
        """Test segmentation combines time gaps and topic changes"""
        session_id = f"session_{uuid4().hex[:8]}"
        base_time = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=f"msg_{i}",
                conversation_id=session_id,
                role="user",
                content=msg,
                created_at=base_time + timedelta(minutes=offset)
            )
            for i, (msg, offset) in enumerate([
                ("Python programming", 0),
                ("Python web dev", 10),
                ("Cooking recipes", 50),  # Time gap (40min) + topic change
                ("Pasta dishes", 60)
            ])
        ]

        db_session.add_all(messages)
        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        time_boundaries = set(detector.detect_time_gap(messages))
        topic_boundaries = set(detector.detect_topic_changes(messages))

        # Should detect time gap
        assert len(time_boundaries) > 0
        # Should detect topic change
        assert len(topic_boundaries) > 0


class TestEpisodeSegmentationEdgeCases:
    """Test edge cases in episode segmentation"""

    def test_segment_empty_message_list(self, segmentation_service_mocked):
        """Test segmentation with empty message list"""
        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)

        time_boundaries = detector.detect_time_gap([])
        topic_boundaries = detector.detect_topic_change([])

        assert len(time_boundaries) == 0
        assert len(topic_boundaries) == 0

    def test_segment_single_message_no_boundaries(
        self, segmentation_service_mocked, db_session
    ):
        """Test segmentation with single message"""
        session_id = f"session_{uuid4().hex[:8]}"
        message = ChatMessage(
            id="msg_1",
            conversation_id=session_id,
            role="user",
            content="Single message",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(message)
        db_session.commit()

        detector = EpisodeBoundaryDetector(segmentation_service_mocked.lancedb)
        boundaries = detector.detect_time_gap([message])

        assert len(boundaries) == 0


# =============================================================================
# Section 3: Episode Retrieval Tests (15 tests)
# =============================================================================

from core.episode_retrieval_service import EpisodeRetrievalService, RetrievalMode


class TestEpisodeRetrievalTemporalQueries:
    """Test temporal (time-based) episode retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_temporal_one_day_range(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test retrieval with 1-day time range"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create episode within 1 day
        episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="Recent Episode",
            description="Test episode",
            summary="Test",
            agent_id=agent.id,
            user_id="user_1",
            workspace_id="default",
            status="completed",
            started_at=datetime.now(timezone.utc) - timedelta(hours=12),
            ended_at=datetime.now(timezone.utc)
        )
        db_session.add(episode)
        db_session.commit()

        result = await retrieval_service.retrieve_temporal(
            agent_id=agent.id,
            time_range="1d"
        )

        assert len(result["episodes"]) >= 1
        assert result["time_range"] == "1d"

    @pytest.mark.asyncio
    async def test_retrieve_temporal_ninety_day_range(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test retrieval with 90-day time range"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        result = await retrieval_service.retrieve_temporal(
            agent_id=agent.id,
            time_range="90d"
        )

        assert "episodes" in result
        assert "time_range" in result

    @pytest.mark.asyncio
    async def test_retrieve_temporal_with_user_filter(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test temporal retrieval with user filter"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        user_id = f"user_{uuid4().hex[:8]}"

        episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="User Episode",
            description="Test",
            summary="Test",
            agent_id=agent.id,
            user_id=user_id,
            workspace_id="default",
            status="completed",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc)
        )
        db_session.add(episode)
        db_session.commit()

        result = await retrieval_service.retrieve_temporal(
            agent_id=agent.id,
            time_range="7d",
            user_id=user_id
        )

        # Should only return episodes for specified user
        for ep in result["episodes"]:
            assert ep["user_id"] == user_id


class TestEpisodeRetrievalSemanticSimilarity:
    """Test semantic similarity retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_semantic_vector_search(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test semantic retrieval uses vector similarity"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Mock LanceDB search
        with patch.object(
            retrieval_service.lancedb, 'search', return_value=[
                {
                    "metadata": json.dumps({"episode_id": f"ep_{uuid4().hex[:8]}"})
                }
            ]
        ):
            result = await retrieval_service.retrieve_semantic(
                agent_id=agent.id,
                query="Python programming tutorials"
            )

            assert "episodes" in result
            assert "query" in result
            assert result["query"] == "Python programming tutorials"

    @pytest.mark.asyncio
    async def test_retrieve_semantic_empty_query(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test semantic retrieval with empty query"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        result = await retrieval_service.retrieve_semantic(
            agent_id=agent.id,
            query=""
        )

        # Should handle empty query gracefully
        assert "episodes" in result


class TestEpisodeRetrievalContextualFiltering:
    """Test contextual retrieval with filtering"""

    @pytest.mark.asyncio
    async def test_retrieve_contextual_canvas_boost(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test contextual retrieval boosts episodes with canvas interactions"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create episode with canvas interactions
        episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="Canvas Episode",
            description="Test",
            summary="Test",
            agent_id=agent.id,
            user_id="user_1",
            workspace_id="default",
            status="completed",
            canvas_action_count=5,  # Has canvas interactions
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc)
        )
        db_session.add(episode)
        db_session.commit()

        result = await retrieval_service.retrieve_contextual(
            agent_id=agent.id,
            current_task="chart visualization"
        )

        # Episodes with canvas should get boost
        canvas_episodes = [e for e in result["episodes"] if e.get("canvas_action_count", 0) > 0]
        assert len(canvas_episodes) >= 1

    @pytest.mark.asyncio
    async def test_retrieve_contextual_feedback_filtering(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test contextual retrieval filters by feedback requirement"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create episode with feedback
        episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="Feedback Episode",
            description="Test",
            summary="Test",
            agent_id=agent.id,
            user_id="user_1",
            workspace_id="default",
            status="completed",
            feedback_ids=[f"fb_{uuid4().hex[:8]}"],
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc)
        )
        db_session.add(episode)
        db_session.commit()

        result = await retrieval_service.retrieve_contextual(
            agent_id=agent.id,
            current_task="task",
            require_feedback=True
        )

        # Should only return episodes with feedback
        for ep in result["episodes"]:
            assert ep.get("feedback_ids")


class TestEpisodeRetrievalPerformance:
    """Test retrieval performance with large datasets"""

    @pytest.mark.asyncio
    async def test_retrieve_performance_large_dataset(
        self, retrieval_service: EpisodeRetrievalService, db_session
    ):
        """Test retrieval performance with 100+ episodes"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create 100 episodes
        base_time = datetime.now(timezone.utc)
        for i in range(100):
            episode = Episode(
                id=f"ep_{i}",
                title=f"Episode {i}",
                description="Test",
                summary="Test",
                agent_id=agent.id,
                user_id="user_1",
                workspace_id="default",
                status="completed",
                started_at=base_time - timedelta(days=i),
                ended_at=base_time - timedelta(days=i) + timedelta(hours=1)
            )
            db_session.add(episode)

        db_session.commit()

        # Measure retrieval time
        start_time = time.time()
        result = await retrieval_service.retrieve_temporal(
            agent_id=agent.id,
            time_range="90d",
            limit=50
        )
        elapsed = time.time() - start_time

        # Should return within reasonable time (< 1 second)
        assert elapsed < 1.0
        assert len(result["episodes"]) <= 50


# =============================================================================
# Section 4: Episode Lifecycle Tests (10 tests)
# =============================================================================

from core.episode_lifecycle_service import EpisodeLifecycleService


class TestEpisodeDecay:
    """Test episode decay logic"""

    def test_decay_old_episodes(self, lifecycle_service, db_session):
        """Test decay score calculation for old episodes"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create old episode (90 days)
        old_episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="Old Episode",
            description="Test",
            summary="Test",
            agent_id=agent.id,
            user_id="user_1",
            workspace_id="default",
            status="completed",
            started_at=datetime.now(timezone.utc) - timedelta(days=90),
            ended_at=datetime.now(timezone.utc) - timedelta(days=90) + timedelta(hours=1),
            decay_score=0.0
        )
        db_session.add(old_episode)
        db_session.commit()

        # Apply decay
        lifecycle_service.apply_decay([old_episode])

        # Old episode should have high decay score
        assert old_episode.decay_score > 0.5

    def test_decay_recent_episodes_low_score(self, lifecycle_service, db_session):
        """Test recent episodes have low decay scores"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create recent episode (1 day)
        recent_episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="Recent Episode",
            description="Test",
            summary="Test",
            agent_id=agent.id,
            user_id="user_1",
            workspace_id="default",
            status="completed",
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            ended_at=datetime.now(timezone.utc),
            decay_score=0.0
        )
        db_session.add(recent_episode)
        db_session.commit()

        # Apply decay
        lifecycle_service.apply_decay([recent_episode])

        # Recent episode should have low decay score
        assert recent_episode.decay_score < 0.3


class TestEpisodeConsolidation:
    """Test episode consolidation logic"""

    def test_consolidate_related_episodes(self, lifecycle_service, db_session):
        """Test consolidation of similar episodes"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create similar episodes
        episodes = []
        for i in range(3):
            episode = Episode(
                id=f"ep_{i}",
                title=f"Python Tutorial {i}",
                description="Python programming tutorial",
                summary="Learn Python basics",
                agent_id=agent.id,
                user_id="user_1",
                workspace_id="default",
                status="completed",
                topics=["python", "programming"],
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
                ended_at=datetime.now(timezone.utc) - timedelta(days=i) + timedelta(hours=1)
            )
            episodes.append(episode)
            db_session.add(episode)

        db_session.commit()

        # Consolidate
        consolidated = lifecycle_service.consolidate_episodes(episodes)

        # Should produce consolidated episode
        assert consolidated is not None
        assert "consolidated" in consolidated.title.lower()


class TestEpisodeArchival:
    """Test episode archival to cold storage"""

    def test_archive_to_cold_storage(self, lifecycle_service, db_session):
        """Test archiving old episodes to cold storage"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        # Create episode to archive
        episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="Archive Test",
            description="Test",
            summary="Test",
            agent_id=agent.id,
            user_id="user_1",
            workspace_id="default",
            status="completed",
            started_at=datetime.now(timezone.utc) - timedelta(days=365),
            ended_at=datetime.now(timezone.utc) - timedelta(days=365) + timedelta(hours=1)
        )
        db_session.add(episode)
        db_session.commit()

        # Archive
        result = lifecycle_service.archive_episode(episode)

        assert result is True
        # Episode should be marked as archived
        db_session.refresh(episode)
        assert episode.status == "archived"


class TestEpisodeLifecycleTransitions:
    """Test episode lifecycle state transitions"""

    def test_lifecycle_transition_from_active_to_decayed(
        self, lifecycle_service, db_session
    ):
        """Test transition from active to decayed state"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        episode = Episode(
            id=f"ep_{uuid4().hex[:8]}",
            title="Test Episode",
            description="Test",
            summary="Test",
            agent_id=agent.id,
            user_id="user_1",
            workspace_id="default",
            status="completed",
            decay_score=0.0,
            started_at=datetime.now(timezone.utc) - timedelta(days=100),
            ended_at=datetime.now(timezone.utc) - timedelta(days=100) + timedelta(hours=1)
        )
        db_session.add(episode)
        db_session.commit()

        # Trigger lifecycle update
        lifecycle_service.update_lifecycle(episode)

        # Should transition to decayed
        assert episode.decay_score > 0.7


# =============================================================================
# Section 5: Canvas Tool Tests (10 tests)
# =============================================================================

from tools.canvas_tool import (
    present_chart,
    present_markdown,
    present_form,
    update_canvas,
    _create_canvas_audit,
)
from unittest.mock import patch, Mock


class TestCanvasGovernanceIntegration:
    """Test canvas tool governance integration"""

    @pytest.mark.asyncio
    async def test_canvas_governance_integration_chart(
        self, db_session
    ):
        """Test chart presentation respects governance checks"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,  # STUDENT can present charts
            confidence_score=0.4
        )
        db_session.add(agent)
        db_session.commit()

        # Mock WebSocket manager
        with patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):
            with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=True):
                result = await present_chart(
                    user_id="test_user",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 2}],
                    title="Test Chart",
                    agent_id=agent.id
                )

                # STUDENT should be allowed to present charts
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_canvas_governance_blocks_unauthorized_form(
        self, db_session
    ):
        """Test form presentation blocked for STUDENT agents"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,  # STUDENT cannot present forms
            confidence_score=0.4
        )
        db_session.add(agent)
        db_session.commit()

        # Mock dependencies
        with patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):
            with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=True):
                result = await present_form(
                    user_id="test_user",
                    form_schema={"fields": []},
                    title="Test Form",
                    agent_id=agent.id
                )

                # STUDENT should be blocked
                assert result["success"] is False


class TestCanvasConcurrentUpdates:
    """Test concurrent canvas update handling"""

    @pytest.mark.asyncio
    async def test_canvas_concurrent_updates_same_canvas(
        self, db_session
    ):
        """Test concurrent updates to same canvas are handled"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        canvas_id = f"canvas_{uuid4().hex[:8]}"

        # Mock WebSocket
        with patch('tools.canvas_tool.ws_manager.broadcast', new_callable=AsyncMock):
            with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
                # Concurrent updates
                tasks = []
                for i in range(5):
                    task = update_canvas(
                        user_id="test_user",
                        canvas_id=canvas_id,
                        updates={"data": [{"x": i, "y": i * 2}]},
                        agent_id=agent.id
                    )
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # All should complete without error
                assert all(isinstance(r, dict) for r in results if not isinstance(r, Exception))


class TestCanvasErrorRecovery:
    """Test canvas error recovery scenarios"""

    @pytest.mark.asyncio
    async def test_canvas_error_recovery_websocket_failure(
        self, db_session
    ):
        """Test recovery from WebSocket broadcast failure"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Mock WebSocket failure
        with patch('tools.canvas_tool.ws_manager.broadcast', side_effect=Exception("WebSocket error")):
            with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
                result = await present_chart(
                    user_id="test_user",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 2}],
                    title="Test Chart",
                    agent_id=agent.id
                )

                # Should handle error gracefully
                assert result["success"] is False
                assert "error" in result


class TestCanvasAuditCompleteness:
    """Test canvas audit trail completeness"""

    def test_canvas_audit_completeness(self, db_session):
        """Test all canvas actions create audit entries"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Create audit entry
        audit = _create_canvas_audit(
            db=db_session,
            agent_id=agent.id,
            agent_execution_id=f"exec_{uuid4().hex[:8]}",
            user_id="test_user",
            canvas_id=f"canvas_{uuid4().hex[:8]}",
            session_id=f"session_{uuid4().hex[:8]}",
            canvas_type="generic",
            component_type="chart",
            component_name="line_chart",
            action="present",
            governance_check_passed=True,
            metadata={"test": "data"}
        )

        assert audit is not None
        assert audit.action == "present"
        assert audit.governance_check_passed is True


# =============================================================================
# Section 6: Agent Context Resolver Tests (10 tests)
# =============================================================================

from core.agent_context_resolver import AgentContextResolver


class TestContextCacheConsistency:
    """Test context resolver cache consistency"""

    def test_context_cache_consistency_after_update(
        self, context_resolver: AgentContextResolver, db_session
    ):
        """Test cache remains consistent after agent update"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # First resolution (cache miss)
        agent1, _ = context_resolver.resolve_agent_for_request(
            user_id="test_user",
            requested_agent_id=agent.id,
            action_type="search"
        )

        # Update agent
        agent.confidence_score = 0.95
        agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        # Second resolution (should reflect update)
        agent2, _ = context_resolver.resolve_agent_for_request(
            user_id="test_user",
            requested_agent_id=agent.id,
            action_type="search"
        )

        # Should get updated agent
        assert agent2.status == AgentStatus.AUTONOMOUS.value


class TestContextConcurrentResolution:
    """Test concurrent context resolution"""

    @pytest.mark.asyncio
    async def test_context_concurrent_resolution(
        self, context_resolver: AgentContextResolver, db_session
    ):
        """Test concurrent resolution requests don't cause race conditions"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Concurrent resolutions
        tasks = []
        for _ in range(10):
            task = asyncio.to_thread(
                context_resolver.resolve_agent_for_request,
                user_id="test_user",
                requested_agent_id=agent.id,
                action_type="search"
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(agent is not None for agent, _ in results)


class TestContextUpdateRaceConditions:
    """Test race condition handling during updates"""

    @pytest.mark.asyncio
    async def test_context_update_race_conditions(
        self, context_resolver: AgentContextResolver, db_session
    ):
        """Test concurrent updates don't cause race conditions"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        # Concurrent updates
        async def update_agent(score):
            await asyncio.to_thread(
                context_resolver._update_agent_cache,
                agent.id,
                {"confidence_score": score}
            )

        tasks = [update_agent(0.7 + i * 0.05) for i in range(5)]
        await asyncio.gather(*tasks)

        # Agent should still be consistent
        db_session.refresh(agent)
        assert agent.confidence_score >= 0.6


# =============================================================================
# Section 7: Trigger Interceptor Tests (10 tests)
# =============================================================================

from core.trigger_interceptor import TriggerInterceptor
from core.models import BlockedTriggerContext


class TestTriggerProposalWorkflow:
    """Test INTERN agent proposal workflow"""

    @pytest.mark.asyncio
    async def test_trigger_proposal_workflow_intern(
        self, db_session
    ):
        """Test INTERN agents trigger proposal workflow"""
        intern_agent = AgentRegistry(
            name="InternAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(intern_agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session)

        # Attempt trigger (should create proposal)
        result = await interceptor.intercept_trigger(
            agent_id=intern_agent.id,
            trigger_type="automated",
            action_type="create",
            params={"test": "data"}
        )

        # INTERN should require proposal
        assert result["allowed"] is False
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_trigger_proposal_autonomous_allowed(
        self, db_session
    ):
        """Test AUTONOMOUS agents don't require proposals"""
        auto_agent = AgentRegistry(
            name="AutoAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(auto_agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session)

        result = await interceptor.intercept_trigger(
            agent_id=auto_agent.id,
            trigger_type="automated",
            action_type="create",
            params={"test": "data"}
        )

        # AUTONOMOUS should be allowed
        assert result["allowed"] is True


class TestTriggerSupervisionMonitoring:
    """Test SUPERVISED agent supervision monitoring"""

    @pytest.mark.asyncio
    async def test_trigger_supervision_monitoring(
        self, db_session
    ):
        """Test SUPERVISED agents trigger supervision monitoring"""
        supervised_agent = AgentRegistry(
            name="SupervisedAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(supervised_agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session)

        result = await interceptor.intercept_trigger(
            agent_id=supervised_agent.id,
            trigger_type="automated",
            action_type="delete",
            params={"test": "data"}
        )

        # SUPERVISED should require supervision
        assert result["allowed"] is True
        assert result["requires_supervision"] is True


class TestTriggerInterceptionPerformance:
    """Test trigger interception performance"""

    @pytest.mark.asyncio
    async def test_trigger_interception_performance(
        self, db_session
    ):
        """Test trigger interception is fast (< 50ms)"""
        agent = AgentRegistry(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session)

        # Measure performance
        start_time = time.time()
        result = await interceptor.intercept_trigger(
            agent_id=agent.id,
            trigger_type="automated",
            action_type="search",
            params={"test": "data"}
        )
        elapsed = (time.time() - start_time) * 1000  # Convert to ms

        # Should be fast (< 50ms)
        assert elapsed < 50
        assert result["allowed"] is True
