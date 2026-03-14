"""
Coverage-driven tests for EpisodeRetrievalService (currently 0% -> target 70%+)

Target file: core/episode_retrieval_service.py (320 statements)

Focus areas from coverage gap analysis:
- Service initialization (lines 58-62)
- Temporal retrieval (lines 63-146)
- Semantic retrieval with vector search (lines 148-217)
- Sequential retrieval (lines 219-271)
- Contextual hybrid retrieval (lines 273-350)
- Access logging (lines 352-373)
- Episode serialization (lines 375-419)
- Canvas-aware retrieval (lines 498-617)
- Business data retrieval (lines 652-745)
- Canvas type retrieval (lines 747-821)
- Supervision context retrieval (lines 827-981)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone
from core.episode_retrieval_service import EpisodeRetrievalService, RetrievalMode


class TestEpisodeRetrievalServiceCoverage:
    """Coverage-driven tests for episode_retrieval_service.py"""

    def test_service_initialization(self, db_session):
        """Cover lines 58-62: Service initialization"""
        service = EpisodeRetrievalService(db_session)
        assert service.db is db_session
        assert service.lancedb is not None
        assert service.governance is not None

    @pytest.mark.asyncio
    async def test_temporal_retrieval_basic(self, db_session):
        """Cover temporal retrieval (lines 63-146) - basic flow"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test agent
        agent = Mock()
        agent.id = "test-agent-1"
        agent.maturity_level = "INTERN"

        # Create test episodes
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 1",
            started_at=now - timedelta(hours=2),
            status="active",
            maturity_at_time="INTERN"
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 2",
            started_at=now,
            status="active",
            maturity_at_time="INTERN"
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        # Mock governance to allow access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True, "agent_maturity": "INTERN"}):
            result = await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="7d",
                limit=10
            )

            assert "episodes" in result
            assert "count" in result
            assert "time_range" in result
            assert isinstance(result["episodes"], list)
            assert result["time_range"] == "7d"

    @pytest.mark.asyncio
    async def test_temporal_retrieval_governance_blocked(self, db_session):
        """Cover temporal retrieval governance blocking"""
        service = EpisodeRetrievalService(db_session)

        # Mock governance to block access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": False, "reason": "STUDENT blocked"}):
            result = await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="7d"
            )

            assert result["episodes"] == []
            assert "error" in result
            assert result["error"] == "STUDENT blocked"

    @pytest.mark.asyncio
    async def test_temporal_retrieval_with_user_filter(self, db_session):
        """Cover temporal retrieval with user_id filtering"""
        from core.models import Episode, ChatSession

        service = EpisodeRetrievalService(db_session)

        # Create test episodes with sessions
        now = datetime.now(timezone.utc)
        session = ChatSession(
            id="session1",
            user_id="user1",
            created_at=now
        )
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 1",
            session_id="session1",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add_all([session, ep1])
        db_session.commit()

        # Mock governance to allow access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="7d",
                user_id="user1",
                limit=10
            )

            assert isinstance(result["episodes"], list)
            # Verify user_id is added to serialized episodes
            if result["episodes"]:
                assert "user_id" in result["episodes"][0]

    @pytest.mark.asyncio
    async def test_temporal_retrieval_time_ranges(self, db_session):
        """Cover temporal retrieval with different time ranges"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Recent task",
            started_at=now - timedelta(hours=1),
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            # Test 1d range
            result = await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="1d",
                limit=10
            )
            assert result["time_range"] == "1d"

            # Test 7d range
            result = await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="7d",
                limit=10
            )
            assert result["time_range"] == "7d"

            # Test 30d range
            result = await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="30d",
                limit=10
            )
            assert result["time_range"] == "30d"

            # Test 90d range
            result = await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="90d",
                limit=10
            )
            assert result["time_range"] == "90d"

    @pytest.mark.asyncio
    async def test_semantic_retrieval_basic(self, db_session):
        """Cover semantic retrieval with vector search (lines 148-217)"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Machine learning workflow",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        # Mock LanceDB search results
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance to allow access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True, "agent_maturity": "INTERN"}):
            result = await service.retrieve_semantic(
                agent_id="test-agent-1",
                query="machine learning",
                limit=10
            )

            assert "episodes" in result
            assert "query" in result
            assert result["query"] == "machine learning"
            assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_semantic_retrieval_governance_blocked(self, db_session):
        """Cover semantic retrieval governance blocking"""
        service = EpisodeRetrievalService(db_session)

        # Mock governance to block access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": False, "reason": "STUDENT blocked"}):
            result = await service.retrieve_semantic(
                agent_id="test-agent-1",
                query="test query",
                limit=10
            )

            assert result["episodes"] == []
            assert "error" in result

    @pytest.mark.asyncio
    async def test_semantic_retrieval_lancedb_error(self, db_session):
        """Cover semantic retrieval LanceDB error handling"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Test task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        # Mock LanceDB to raise error
        mock_lancedb = Mock()
        mock_lancedb.search.side_effect = Exception("LanceDB connection failed")
        service.lancedb = mock_lancedb

        # Mock governance to allow access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_semantic(
                agent_id="test-agent-1",
                query="test query",
                limit=10
            )

            assert result["episodes"] == []
            assert "error" in result
            assert "LanceDB connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_semantic_retrieval_empty_metadata(self, db_session):
        """Cover semantic retrieval with empty/missing metadata"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Mock LanceDB search results with missing metadata
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {"id": "vector1"},  # No metadata field
            {"id": "vector2", "metadata": None},  # None metadata
            {"id": "vector3", "metadata": "{}"},  # Empty JSON
        ]
        service.lancedb = mock_lancedb

        # Mock governance to allow access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_semantic(
                agent_id="test-agent-1",
                query="test query",
                limit=10
            )

            assert isinstance(result["episodes"], list)
            # Should handle missing metadata gracefully

    @pytest.mark.asyncio
    async def test_sequential_retrieval_basic(self, db_session):
        """Cover sequential retrieval (lines 219-271)"""
        from core.models import Episode, EpisodeSegment

        service = EpisodeRetrievalService(db_session)

        # Create test episode with segments
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Sequential task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="user_message",
            sequence_order=1,
            content="User input",
            source_type="chat"
        )
        seg2 = EpisodeSegment(
            id="seg2",
            episode_id="ep1",
            segment_type="agent_response",
            sequence_order=2,
            content="Agent response",
            source_type="agent"
        )
        db_session.add_all([ep1, seg1, seg2])
        db_session.commit()

        result = await service.retrieve_sequential(
            episode_id="ep1",
            agent_id="test-agent-1"
        )

        assert "episode" in result
        assert "segments" in result
        assert len(result["segments"]) == 2
        assert result["episode"]["id"] == "ep1"

    @pytest.mark.asyncio
    async def test_sequential_retrieval_not_found(self, db_session):
        """Cover sequential retrieval with non-existent episode"""
        service = EpisodeRetrievalService(db_session)

        result = await service.retrieve_sequential(
            episode_id="nonexistent",
            agent_id="test-agent-1"
        )

        assert "error" in result
        assert result["error"] == "Episode not found"

    @pytest.mark.asyncio
    async def test_sequential_retrieval_with_canvas_feedback(self, db_session):
        """Cover sequential retrieval with canvas and feedback context"""
        from core.models import Episode, EpisodeSegment, CanvasAudit, AgentFeedback

        service = EpisodeRetrievalService(db_session)

        # Create test episode with canvas and feedback
        now = datetime.now(timezone.utc)
        canvas = CanvasAudit(
            id="canvas1",
            component_type="chart",
            component_name="test_chart",
            action="present",
            created_at=now
        )
        feedback = AgentFeedback(
            id="feedback1",
            agent_id="test-agent-1",
            feedback_type="thumbs_up_down",
            thumbs_up_down=True,
            created_at=now
        )
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task with canvas and feedback",
            started_at=now,
            status="active",
            canvas_ids=["canvas1"],
            feedback_ids=["feedback1"]
        )
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="user_message",
            sequence_order=1,
            content="User input",
            source_type="chat"
        )
        db_session.add_all([canvas, feedback, ep1, seg1])
        db_session.commit()

        result = await service.retrieve_sequential(
            episode_id="ep1",
            agent_id="test-agent-1",
            include_canvas=True,
            include_feedback=True
        )

        assert "episode" in result
        assert "segments" in result
        assert "canvas_context" in result
        assert "feedback_context" in result
        assert len(result["canvas_context"]) == 1
        assert len(result["feedback_context"]) == 1

    @pytest.mark.asyncio
    async def test_sequential_retrieval_exclude_canvas_feedback(self, db_session):
        """Cover sequential retrieval excluding canvas and feedback"""
        from core.models import Episode, EpisodeSegment

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task",
            started_at=now,
            status="active",
            canvas_ids=["canvas1"],
            feedback_ids=["feedback1"]
        )
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="user_message",
            sequence_order=1,
            content="User input",
            source_type="chat"
        )
        db_session.add_all([ep1, seg1])
        db_session.commit()

        result = await service.retrieve_sequential(
            episode_id="ep1",
            agent_id="test-agent-1",
            include_canvas=False,
            include_feedback=False
        )

        assert "episode" in result
        assert "segments" in result
        assert "canvas_context" not in result
        assert "feedback_context" not in result

    @pytest.mark.asyncio
    async def test_contextual_hybrid_retrieval(self, db_session):
        """Cover contextual hybrid retrieval (lines 273-350)"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episodes
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Agent workflow automation",
            started_at=now,
            status="active",
            canvas_action_count=1,
            aggregate_feedback_score=0.5
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Data processing task",
            started_at=now - timedelta(hours=1),
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        # Mock LanceDB search
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_contextual(
                agent_id="test-agent-1",
                current_task="agent workflow",
                limit=10
            )

            assert "episodes" in result
            assert "count" in result
            assert "query" in result
            assert result["query"] == "agent workflow"
            assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_contextual_retrieval_with_canvas_feedback_boosts(self, db_session):
        """Cover contextual retrieval with canvas/feedback score boosts"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episodes with different canvas/feedback scores
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task with canvas and positive feedback",
            started_at=now,
            status="active",
            canvas_action_count=5,
            aggregate_feedback_score=0.8  # Positive feedback
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task with negative feedback",
            started_at=now - timedelta(hours=1),
            status="active",
            canvas_action_count=0,
            aggregate_feedback_score=-0.5  # Negative feedback
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        # Mock LanceDB search
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_contextual(
                agent_id="test-agent-1",
                current_task="task",
                limit=10
            )

            assert "episodes" in result
            # Episodes should have relevance_score
            for ep in result["episodes"]:
                assert "relevance_score" in ep

    @pytest.mark.asyncio
    async def test_contextual_retrieval_with_filters(self, db_session):
        """Cover contextual retrieval with require_canvas and require_feedback filters"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episodes
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task with canvas",
            started_at=now,
            status="active",
            canvas_action_count=5,
            feedback_ids=["feedback1"]
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task without canvas",
            started_at=now - timedelta(hours=1),
            status="active",
            canvas_action_count=0
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        # Mock LanceDB search
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            # Test require_canvas filter
            result = await service.retrieve_contextual(
                agent_id="test-agent-1",
                current_task="task",
                limit=10,
                require_canvas=True
            )

            # Should only return episodes with canvas
            for ep in result["episodes"]:
                assert ep["canvas_action_count"] > 0

            # Test require_feedback filter
            result = await service.retrieve_contextual(
                agent_id="test-agent-1",
                current_task="task",
                limit=10,
                require_feedback=True
            )

            # Should only return episodes with feedback
            for ep in result["episodes"]:
                assert len(ep.get("feedback_ids", [])) > 0

    @pytest.mark.asyncio
    async def test_access_logging(self, db_session):
        """Cover access logging (lines 352-373)"""
        from core.models import Episode, EpisodeAccessLog

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Test task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True, "agent_maturity": "INTERN"}):
            # Perform retrieval which should log access
            await service.retrieve_temporal(
                agent_id="test-agent-1",
                time_range="7d",
                limit=10
            )

            # Verify access log was created
            logs = db_session.query(EpisodeAccessLog).all()
            assert len(logs) >= 1
            assert logs[0].accessed_by_agent == "test-agent-1"
            assert logs[0].access_type == "temporal"
            assert logs[0].governance_check_passed == True
            assert logs[0].agent_maturity_at_access == "INTERN"

    @pytest.mark.asyncio
    async def test_access_logging_error_handling(self, db_session):
        """Cover access logging error handling"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Test task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        # Mock governance and db.commit to raise error
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            with patch.object(db_session, 'commit', side_effect=Exception("DB error")):
                # Should handle logging error gracefully
                result = await service.retrieve_temporal(
                    agent_id="test-agent-1",
                    time_range="7d",
                    limit=10
                )

                # Should still return result despite logging failure
                assert "episodes" in result

    def test_serialize_episode_basic(self, db_session):
        """Cover episode serialization (lines 375-419)"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Test episode",
            started_at=now,
            completed_at=now + timedelta(hours=1),
            status="active",
            topics=["topic1", "topic2"],
            entities=["entity1"],
            importance_score=0.8,
            maturity_at_time="INTERN",
            human_intervention_count=1,
            constitutional_score=0.9,
            decay_score=0.95,
            access_count=5,
            outcome="success",
            success=True
        )
        db_session.add(ep1)
        db_session.commit()

        # Serialize episode
        serialized = service._serialize_episode(ep1)

        assert serialized["id"] == "ep1"
        assert serialized["title"] == "Test episode"
        assert serialized["description"] == "Test episode"
        assert serialized["summary"] == "Test episode"
        assert serialized["agent_id"] == "test-agent-1"
        assert serialized["status"] == "active"
        assert serialized["started_at"] is not None
        assert serialized["topics"] == ["topic1", "topic2"]
        assert serialized["entities"] == ["entity1"]
        assert serialized["importance_score"] == 0.8
        assert serialized["maturity_at_time"] == "INTERN"
        assert serialized["human_intervention_count"] == 1
        assert serialized["constitutional_score"] == 0.9
        assert serialized["decay_score"] == 0.95
        assert serialized["access_count"] == 5
        assert serialized["outcome"] == "success"
        assert serialized["success"] == True

    def test_serialize_episode_with_user_id(self, db_session):
        """Cover episode serialization with user_id"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Test episode",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        # Serialize episode with user_id
        serialized = service._serialize_episode(ep1, user_id="user123")

        assert serialized["user_id"] == "user123"

    def test_serialize_episode_with_optional_fields(self, db_session):
        """Cover episode serialization with optional/missing fields"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode with minimal fields
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Minimal episode",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        # Serialize episode
        serialized = service._serialize_episode(ep1)

        # Check optional fields have defaults
        assert serialized["topics"] == []
        assert serialized["entities"] == []
        assert serialized["importance_score"] == 0.5
        assert serialized["canvas_ids"] == []
        assert serialized["canvas_action_count"] == 0
        assert serialized["feedback_ids"] == []
        assert serialized["aggregate_feedback_score"] is None
        assert serialized["decay_score"] == 1.0

    def test_serialize_segment(self, db_session):
        """Cover segment serialization (lines 421-433)"""
        from core.models import EpisodeSegment

        service = EpisodeRetrievalService(db_session)

        # Create test segment
        now = datetime.now(timezone.utc)
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="user_message",
            sequence_order=1,
            content="User input",
            content_summary="Summary",
            source_type="chat",
            source_id="source1",
            canvas_context={"canvas_type": "generic"},
            created_at=now
        )
        db_session.add(seg1)
        db_session.commit()

        # Serialize segment
        serialized = service._serialize_segment(seg1)

        assert serialized["id"] == "seg1"
        assert serialized["segment_type"] == "user_message"
        assert serialized["sequence_order"] == 1
        assert serialized["content"] == "User input"
        assert serialized["content_summary"] == "Summary"
        assert serialized["source_type"] == "chat"
        assert serialized["source_id"] == "source1"
        assert serialized["canvas_context"] == {"canvas_type": "generic"}
        assert serialized["created_at"] is not None

    @pytest.mark.asyncio
    async def test_fetch_canvas_context(self, db_session):
        """Cover canvas context fetching (lines 435-465)"""
        from core.models import CanvasAudit

        service = EpisodeRetrievalService(db_session)

        # Create test canvas audits
        now = datetime.now(timezone.utc)
        canvas1 = CanvasAudit(
            id="canvas1",
            component_type="chart",
            component_name="test_chart",
            action="present",
            created_at=now,
            audit_metadata={"key": "value"}
        )
        canvas2 = CanvasAudit(
            id="canvas2",
            component_type="form",
            component_name="test_form",
            action="submit",
            created_at=now
        )
        db_session.add_all([canvas1, canvas2])
        db_session.commit()

        # Fetch canvas context
        result = await service._fetch_canvas_context(["canvas1", "canvas2"])

        assert len(result) == 2
        assert result[0]["id"] == "canvas1"
        assert result[0]["canvas_type"] == "generic"
        assert result[0]["component_type"] == "chart"
        assert result[1]["id"] == "canvas2"
        assert result[1]["canvas_type"] == "docs"

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_empty_list(self, db_session):
        """Cover canvas context fetching with empty list"""
        service = EpisodeRetrievalService(db_session)

        result = await service._fetch_canvas_context([])

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_error_handling(self, db_session):
        """Cover canvas context fetching error handling"""
        service = EpisodeRetrievalService(db_session)

        # Mock query to raise error
        with patch.object(service.db, 'query', side_effect=Exception("DB error")):
            result = await service._fetch_canvas_context(["canvas1"])

            # Should return empty list on error
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_feedback_context(self, db_session):
        """Cover feedback context fetching (lines 467-496)"""
        from core.models import AgentFeedback

        service = EpisodeRetrievalService(db_session)

        # Create test feedbacks
        now = datetime.now(timezone.utc)
        feedback1 = AgentFeedback(
            id="feedback1",
            agent_id="test-agent-1",
            feedback_type="thumbs_up_down",
            thumbs_up_down=True,
            rating=5,
            user_correction="No correction",
            created_at=now
        )
        feedback2 = AgentFeedback(
            id="feedback2",
            agent_id="test-agent-1",
            feedback_type="rating",
            rating=4,
            thumbs_up_down=None,
            created_at=now
        )
        db_session.add_all([feedback1, feedback2])
        db_session.commit()

        # Fetch feedback context
        result = await service._fetch_feedback_context(["feedback1", "feedback2"])

        assert len(result) == 2
        assert result[0]["id"] == "feedback1"
        assert result[0]["feedback_type"] == "thumbs_up_down"
        assert result[0]["thumbs_up_down"] == True
        assert result[0]["rating"] == 5
        assert result[1]["id"] == "feedback2"
        assert result[1]["feedback_type"] == "rating"

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_empty_list(self, db_session):
        """Cover feedback context fetching with empty list"""
        service = EpisodeRetrievalService(db_session)

        result = await service._fetch_feedback_context([])

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_error_handling(self, db_session):
        """Cover feedback context fetching error handling"""
        service = EpisodeRetrievalService(db_session)

        # Mock query to raise error
        with patch.object(service.db, 'query', side_effect=Exception("DB error")):
            result = await service._fetch_feedback_context(["feedback1"])

            # Should return empty list on error
            assert result == []

    @pytest.mark.asyncio
    async def test_canvas_aware_retrieval_basic(self, db_session):
        """Cover canvas-aware retrieval (lines 498-617)"""
        from core.models import Episode, EpisodeSegment

        service = EpisodeRetrievalService(db_session)

        # Create test episode with segments
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Canvas task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="canvas_interaction",
            sequence_order=1,
            content="Presented chart",
            source_type="canvas",
            canvas_context={
                "canvas_type": "generic",
                "presentation_summary": "Chart showing sales data",
                "critical_data_points": {"sales": 1000000}
            }
        )
        db_session.add_all([ep1, seg1])
        db_session.commit()

        # Mock LanceDB search
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_canvas_aware(
                agent_id="test-agent-1",
                query="sales chart",
                limit=10
            )

            assert "episodes" in result
            assert "query" in result
            assert "canvas_context_detail" in result
            assert result["canvas_context_detail"] == "summary"

    @pytest.mark.asyncio
    async def test_canvas_aware_retrieval_with_canvas_type_filter(self, db_session):
        """Cover canvas-aware retrieval with canvas type filter"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Sheets task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        db_session.add(ep1)
        db_session.commit()

        # Mock LanceDB search
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_canvas_aware(
                agent_id="test-agent-1",
                query="spreadsheet",
                canvas_type="sheets",
                limit=10
            )

            assert "episodes" in result
            assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_canvas_aware_retrieval_detail_levels(self, db_session):
        """Cover canvas-aware retrieval with different detail levels"""
        from core.models import Episode, EpisodeSegment

        service = EpisodeRetrievalService(db_session)

        # Create test episode with segments
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Canvas task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="canvas_interaction",
            sequence_order=1,
            content="Presented chart",
            source_type="canvas",
            canvas_context={
                "canvas_type": "generic",
                "presentation_summary": "Summary",
                "critical_data_points": {"key": "value"},
                "visual_elements": ["chart", "table"]
            }
        )
        db_session.add_all([ep1, seg1])
        db_session.commit()

        # Mock LanceDB search
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            # Test summary detail level
            result = await service.retrieve_canvas_aware(
                agent_id="test-agent-1",
                query="chart",
                canvas_context_detail="summary",
                limit=10
            )
            assert result["canvas_context_detail"] == "summary"

            # Test standard detail level
            result = await service.retrieve_canvas_aware(
                agent_id="test-agent-1",
                query="chart",
                canvas_context_detail="standard",
                limit=10
            )
            assert result["canvas_context_detail"] == "standard"

            # Test full detail level
            result = await service.retrieve_canvas_aware(
                agent_id="test-agent-1",
                query="chart",
                canvas_context_detail="full",
                limit=10
            )
            assert result["canvas_context_detail"] == "full"

    def test_filter_canvas_context_detail_summary(self, db_session):
        """Cover canvas context detail filtering - summary level (lines 619-650)"""
        service = EpisodeRetrievalService(db_session)

        canvas_context = {
            "canvas_type": "generic",
            "presentation_summary": "Chart showing sales",
            "critical_data_points": {"sales": 1000000},
            "visual_elements": ["chart"]
        }

        result = service._filter_canvas_context_detail(canvas_context, "summary")

        assert result == {"presentation_summary": "Chart showing sales"}

    def test_filter_canvas_context_detail_standard(self, db_session):
        """Cover canvas context detail filtering - standard level"""
        service = EpisodeRetrievalService(db_session)

        canvas_context = {
            "canvas_type": "generic",
            "presentation_summary": "Chart showing sales",
            "critical_data_points": {"sales": 1000000},
            "visual_elements": ["chart"]
        }

        result = service._filter_canvas_context_detail(canvas_context, "standard")

        assert "canvas_type" in result
        assert "presentation_summary" in result
        assert "critical_data_points" in result
        assert "visual_elements" not in result

    def test_filter_canvas_context_detail_full(self, db_session):
        """Cover canvas context detail filtering - full level"""
        service = EpisodeRetrievalService(db_session)

        canvas_context = {
            "canvas_type": "generic",
            "presentation_summary": "Chart showing sales",
            "critical_data_points": {"sales": 1000000},
            "visual_elements": ["chart"]
        }

        result = service._filter_canvas_context_detail(canvas_context, "full")

        # Should return everything
        assert result == canvas_context

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_basic(self, db_session):
        """Cover business data retrieval (lines 652-745)"""
        from core.models import Episode, EpisodeSegment

        service = EpisodeRetrievalService(db_session)

        # Create test episode with business data in canvas context
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Invoice approval task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="canvas_interaction",
            sequence_order=1,
            content="Invoice presented",
            source_type="canvas",
            canvas_context={
                "critical_data_points": {
                    "approval_status": "approved",
                    "revenue": 1500000,
                    "invoice_amount": 50000
                }
            }
        )
        db_session.add_all([ep1, seg1])
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_by_business_data(
                agent_id="test-agent-1",
                business_filters={"approval_status": "approved"},
                limit=10
            )

            assert "episodes" in result
            assert "filters" in result
            assert result["filters"]["approval_status"] == "approved"

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_with_operators(self, db_session):
        """Cover business data retrieval with comparison operators"""
        from core.models import Episode, EpisodeSegment

        service = EpisodeRetrievalService(db_session)

        # Create test episode with business data
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="High revenue task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        seg1 = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="canvas_interaction",
            sequence_order=1,
            content="Large invoice",
            source_type="canvas",
            canvas_context={
                "critical_data_points": {
                    "revenue": 1500000,
                    "invoice_amount": 50000
                }
            }
        )
        db_session.add_all([ep1, seg1])
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            # Test $gt operator
            result = await service.retrieve_by_business_data(
                agent_id="test-agent-1",
                business_filters={"revenue": {"$gt": 1000000}},
                limit=10
            )

            assert "episodes" in result
            assert "filters" in result

            # Test $lt operator
            result = await service.retrieve_by_business_data(
                agent_id="test-agent-1",
                business_filters={"invoice_amount": {"$lt": 100000}},
                limit=10
            )

            assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_governance_blocked(self, db_session):
        """Cover business data retrieval governance blocking"""
        service = EpisodeRetrievalService(db_session)

        # Mock governance to block access
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": False, "reason": "Blocked"}):
            result = await service.retrieve_by_business_data(
                agent_id="test-agent-1",
                business_filters={"status": "approved"},
                limit=10
            )

            assert result["episodes"] == []
            assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_basic(self, db_session):
        """Cover canvas type retrieval (lines 747-821)"""
        from core.models import Episode, CanvasAudit

        service = EpisodeRetrievalService(db_session)

        # Create test episode with canvas
        now = datetime.now(timezone.utc)
        canvas = CanvasAudit(
            id="canvas1",
            episode_id="ep1",
            component_type="table",
            component_name="sales_table",
            action="present",
            created_at=now
        )
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Spreadsheet task",
            started_at=now,
            status="active",
            canvas_action_count=1
        )
        db_session.add_all([canvas, ep1])
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_by_canvas_type(
                agent_id="test-agent-1",
                canvas_type="sheets",
                limit=10
            )

            assert "episodes" in result
            assert "canvas_type" in result
            assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_with_action_filter(self, db_session):
        """Cover canvas type retrieval with action filter"""
        from core.models import Episode, CanvasAudit

        service = EpisodeRetrievalService(db_session)

        # Create test episode with canvas
        now = datetime.now(timezone.utc)
        canvas = CanvasAudit(
            id="canvas1",
            episode_id="ep1",
            component_type="form",
            component_name="submit_form",
            action="submit",
            created_at=now
        )
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Form submission task",
            started_at=now,
            status="active",
            canvas_action_count=1
        )
        db_session.add_all([canvas, ep1])
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_by_canvas_type(
                agent_id="test-agent-1",
                canvas_type="sheets",
                action="submit",
                limit=10
            )

            assert "episodes" in result
            assert result["action"] == "submit"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_with_time_range(self, db_session):
        """Cover canvas type retrieval with time range filter"""
        from core.models import Episode, CanvasAudit

        service = EpisodeRetrievalService(db_session)

        # Create test episode with canvas
        now = datetime.now(timezone.utc)
        canvas = CanvasAudit(
            id="canvas1",
            episode_id="ep1",
            component_type="document",
            component_name="report",
            action="present",
            created_at=now
        )
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Document task",
            started_at=now - timedelta(hours=1),
            status="active",
            canvas_action_count=1
        )
        db_session.add_all([canvas, ep1])
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_by_canvas_type(
                agent_id="test-agent-1",
                canvas_type="docs",
                time_range="7d",
                limit=10
            )

            assert "episodes" in result
            assert result["time_range"] == "7d"

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_basic(self, db_session):
        """Cover supervision context retrieval (lines 827-981)"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode with supervision data
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Supervised task",
            started_at=now,
            status="active",
            supervisor_id="supervisor1",
            supervisor_rating=5,
            intervention_count=1,
            intervention_types=["correction"],
            supervision_feedback="Good performance"
        )
        db_session.add(ep1)
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.TEMPORAL,
                limit=10
            )

            assert "episodes" in result
            assert "count" in result
            assert "retrieval_mode" in result
            assert result["retrieval_mode"] == "temporal"

            # Check supervision context in first episode
            if result["episodes"]:
                assert "supervision_context" in result["episodes"][0]

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_filters(self, db_session):
        """Cover supervision context retrieval with filters"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episodes with different supervision ratings
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="High rated task",
            started_at=now,
            status="active",
            supervisor_id="supervisor1",
            supervisor_rating=5,
            intervention_count=0
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Low rated task",
            started_at=now - timedelta(hours=1),
            status="active",
            supervisor_id="supervisor1",
            supervisor_rating=2,
            intervention_count=5
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            # Test min_rating filter
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.TEMPORAL,
                limit=10,
                min_rating=4
            )

            assert "episodes" in result
            assert "min_rating_4" in result["supervision_filters_applied"]

            # Test max_interventions filter
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.TEMPORAL,
                limit=10,
                max_interventions=2
            )

            assert "episodes" in result
            assert "max_interventions_2" in result["supervision_filters_applied"]

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_outcome_filters(self, db_session):
        """Cover supervision context retrieval with outcome filters"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episodes
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="High rated task",
            started_at=now,
            status="active",
            supervisor_id="supervisor1",
            supervisor_rating=5,
            intervention_count=0
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Low intervention task",
            started_at=now - timedelta(hours=1),
            status="active",
            supervisor_id="supervisor1",
            supervisor_rating=4,
            intervention_count=1
        )
        db_session.add_all([ep1, ep2])
        db_session.commit()

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            # Test high_rated outcome filter
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.TEMPORAL,
                limit=10,
                supervision_outcome_filter="high_rated"
            )

            assert "episodes" in result
            assert "high_rated" in result["supervision_filters_applied"]

            # Test low_intervention outcome filter
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.TEMPORAL,
                limit=10,
                supervision_outcome_filter="low_intervention"
            )

            assert "episodes" in result
            assert "low_intervention" in result["supervision_filters_applied"]

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_all_modes(self, db_session):
        """Cover supervision context retrieval with all retrieval modes"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Supervised task",
            started_at=now,
            status="active",
            supervisor_id="supervisor1",
            supervisor_rating=4,
            intervention_count=1
        )
        db_session.add(ep1)
        db_session.commit()

        # Mock LanceDB for semantic mode
        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {
                "id": "vector1",
                "metadata": '{"episode_id": "ep1"}'
            }
        ]
        service.lancedb = mock_lancedb

        # Mock governance
        with patch.object(service.governance, 'can_perform_action', return_value={"allowed": True}):
            # Test TEMPORAL mode
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.TEMPORAL,
                limit=10
            )
            assert result["retrieval_mode"] == "temporal"

            # Test SEMANTIC mode
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.SEMANTIC,
                limit=10
            )
            assert result["retrieval_mode"] == "semantic"

            # Test CONTEXTUAL mode
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.CONTEXTUAL,
                limit=10
            )
            assert result["retrieval_mode"] == "contextual"

            # Test SEQUENTIAL mode
            result = await service.retrieve_with_supervision_context(
                agent_id="test-agent-1",
                retrieval_mode=RetrievalMode.SEQUENTIAL,
                limit=10
            )
            assert result["retrieval_mode"] == "sequential"

    def test_create_supervision_context(self, db_session):
        """Cover supervision context creation (lines 983-993)"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Supervised task",
            started_at=now,
            status="active",
            supervisor_id="supervisor1",
            supervisor_rating=5,
            intervention_count=2,
            intervention_types=["correction", "guidance"],
            supervision_feedback="Needs improvement on accuracy"
        )

        context = service._create_supervision_context(ep1)

        assert context["has_supervision"] == True
        assert context["supervisor_id"] == "supervisor1"
        assert context["supervisor_rating"] == 5
        assert context["intervention_count"] == 2
        assert context["intervention_types"] == ["correction", "guidance"]
        assert "feedback_summary" in context
        assert "outcome_quality" in context

    def test_create_supervision_context_no_supervision(self, db_session):
        """Cover supervision context creation for episode without supervision"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episode without supervision
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Unsupervised task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )

        context = service._create_supervision_context(ep1)

        assert context["has_supervision"] == False
        assert context["supervisor_id"] is None
        assert context["supervisor_rating"] is None
        assert context["intervention_count"] == 0
        assert context["intervention_types"] == []

    def test_summarize_feedback(self, db_session):
        """Cover feedback summarization (lines 995-1003)"""
        service = EpisodeRetrievalService(db_session)

        # Test short feedback
        short = "Good performance"
        result = service._summarize_feedback(short)
        assert result == "Good performance"

        # Test long feedback (> 100 chars)
        long = "This is a very long feedback text that exceeds one hundred characters and should be truncated to exactly one hundred characters with ellipsis added at the end"
        result = service._summarize_feedback(long)
        assert len(result) == 100  # 97 chars + "..."
        assert result.endswith("...")

        # Test None feedback
        result = service._summarize_feedback(None)
        assert result is None

    def test_assess_outcome_quality(self, db_session):
        """Cover outcome quality assessment (lines 1005-1028)"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Test excellent: 5 stars, 0-1 interventions
        now = datetime.now(timezone.utc)
        ep_excellent = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Excellent task",
            started_at=now,
            status="active",
            supervisor_rating=5,
            intervention_count=0
        )
        quality = service._assess_outcome_quality(ep_excellent)
        assert quality == "excellent"

        # Test excellent: 5 stars, 1 intervention
        ep_excellent2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Excellent task 2",
            started_at=now,
            status="active",
            supervisor_rating=5,
            intervention_count=1
        )
        quality = service._assess_outcome_quality(ep_excellent2)
        assert quality == "excellent"

        # Test good: 4 stars, 0-2 interventions
        ep_good = Episode(
            id="ep3",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Good task",
            started_at=now,
            status="active",
            supervisor_rating=4,
            intervention_count=2
        )
        quality = service._assess_outcome_quality(ep_good)
        assert quality == "good"

        # Test good: 5 stars, 2 interventions
        ep_good2 = Episode(
            id="ep4",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Good task 2",
            started_at=now,
            status="active",
            supervisor_rating=5,
            intervention_count=2
        )
        quality = service._assess_outcome_quality(ep_good2)
        assert quality == "good"

        # Test fair: 3-4 stars
        ep_fair = Episode(
            id="ep5",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Fair task",
            started_at=now,
            status="active",
            supervisor_rating=3,
            intervention_count=3
        )
        quality = service._assess_outcome_quality(ep_fair)
        assert quality == "fair"

        # Test poor: < 3 stars
        ep_poor = Episode(
            id="ep6",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Poor task",
            started_at=now,
            status="active",
            supervisor_rating=2,
            intervention_count=5
        )
        quality = service._assess_outcome_quality(ep_poor)
        assert quality == "poor"

        # Test unknown: no rating
        ep_unknown = Episode(
            id="ep7",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Unknown task",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        quality = service._assess_outcome_quality(ep_unknown)
        assert quality == "unknown"

    def test_filter_improvement_trend(self, db_session):
        """Cover improvement trend filtering (lines 1030-1076)"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episodes with improving ratings
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Recent high rated",
            started_at=now,
            status="active",
            supervisor_rating=5
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Recent medium rated",
            started_at=now - timedelta(hours=1),
            status="active",
            supervisor_rating=4
        )
        ep3 = Episode(
            id="ep3",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Earlier low rated",
            started_at=now - timedelta(days=1),
            status="active",
            supervisor_rating=2
        )
        ep4 = Episode(
            id="ep4",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Earlier medium rated",
            started_at=now - timedelta(days=2),
            status="active",
            supervisor_rating=3
        )
        ep5 = Episode(
            id="ep5",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Earlier low rated 2",
            started_at=now - timedelta(days=3),
            status="active",
            supervisor_rating=2
        )

        episodes = [ep1, ep2, ep3, ep4, ep5]
        result = service._filter_improvement_trend(episodes)

        # Should return episodes showing improvement (recent avg >= earlier avg)
        assert len(result) > 0

    def test_filter_improvement_trend_insufficient_data(self, db_session):
        """Cover improvement trend filtering with insufficient data"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create only 2 episodes (insufficient for trend analysis)
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 1",
            started_at=now,
            status="active",
            supervisor_rating=5
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 2",
            started_at=now - timedelta(hours=1),
            status="active",
            supervisor_rating=3
        )

        episodes = [ep1, ep2]
        result = service._filter_improvement_trend(episodes)

        # Should return all episodes when insufficient data
        assert len(result) == 2

    def test_filter_improvement_trend_no_ratings(self, db_session):
        """Cover improvement trend filtering with no ratings"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create episodes without ratings
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 1",
            started_at=now,
            status="active",
        maturity_at_time="INTERN"
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 2",
            started_at=now - timedelta(hours=1),
            status="active",
        maturity_at_time="INTERN"
        )
        ep3 = Episode(
            id="ep3",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 3",
            started_at=now - timedelta(days=1),
            status="active",
        maturity_at_time="INTERN"
        )
        ep4 = Episode(
            id="ep4",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 4",
            started_at=now - timedelta(days=2),
            status="active",
        maturity_at_time="INTERN"
        )
        ep5 = Episode(
            id="ep5",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Task 5",
            started_at=now - timedelta(days=3),
            status="active",
        maturity_at_time="INTERN"
        )

        episodes = [ep1, ep2, ep3, ep4, ep5]
        result = service._filter_improvement_trend(episodes)

        # Should return all episodes when can't determine trend
        assert len(result) == 5

    def test_filter_improvement_trend_declining(self, db_session):
        """Cover improvement trend filtering with declining performance"""
        from core.models import Episode

        service = EpisodeRetrievalService(db_session)

        # Create test episodes with declining ratings
        now = datetime.now(timezone.utc)
        ep1 = Episode(
            id="ep1",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Recent low rated",
            started_at=now,
            status="active",
            supervisor_rating=2
        )
        ep2 = Episode(
            id="ep2",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Recent medium rated",
            started_at=now - timedelta(hours=1),
            status="active",
            supervisor_rating=3
        )
        ep3 = Episode(
            id="ep3",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Earlier high rated",
            started_at=now - timedelta(days=1),
            status="active",
            supervisor_rating=5
        )
        ep4 = Episode(
            id="ep4",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Earlier high rated 2",
            started_at=now - timedelta(days=2),
            status="active",
            supervisor_rating=4
        )
        ep5 = Episode(
            id="ep5",
            agent_id="test-agent-1",
            tenant_id="tenant1",
            task_description="Earlier high rated 3",
            started_at=now - timedelta(days=3),
            status="active",
            supervisor_rating=5
        )

        episodes = [ep1, ep2, ep3, ep4, ep5]
        result = service._filter_improvement_trend(episodes)

        # Should return empty list when recent performance is worse
        assert len(result) == 0
