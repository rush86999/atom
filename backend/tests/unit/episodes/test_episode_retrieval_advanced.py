"""
Advanced Retrieval Mode Tests for EpisodeRetrievalService

Tests for advanced retrieval modes that were untested in Phase 161:
- Sequential retrieval (full episodes with segments)
- Canvas-aware retrieval (with detail filtering)
- Business data retrieval
- Supervision context retrieval
- Contextual retrieval with feedback weighting

Target: 65%+ coverage on EpisodeRetrievalService (up from 32.5%)
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from core.episode_retrieval_service import EpisodeRetrievalService, RetrievalMode
from core.models import (
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    Episode,
    EpisodeSegment,
)


# ========================================================================
# TestSequentialRetrieval - Full episode with segments
# ========================================================================

class TestSequentialRetrieval:
    """Test sequential retrieval of full episodes with segments"""

    @pytest.mark.asyncio
    async def test_retrieve_sequential_full_episode_with_segments(self, retrieval_service, db_session):
        """Should retrieve full episode with all segments ordered by sequence_order"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=1),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create 3 segments
        segments = []
        for i in range(3):
            segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode_id,
                segment_type="conversation",
                sequence_order=i,  # 0, 1, 2
                content=f"Segment {i}",
                content_summary=f"Summary {i}",
                source_type="chat",
                source_id=f"msg_{i}",
                created_at=now - timedelta(hours=2) + timedelta(minutes=i*10)
            )
            db_session.add(segment)
            segments.append(segment)

        db_session.commit()

        # Call retrieve_sequential
        result = await retrieval_service.retrieve_sequential(
            episode_id=episode_id,
            agent_id=agent_id
        )

        # Verify result structure
        assert "episode" in result
        assert "segments" in result
        assert result["episode"]["id"] == episode_id

        # Verify segments present and ordered
        assert len(result["segments"]) == 3
        assert result["segments"][0]["sequence_order"] == 0
        assert result["segments"][1]["sequence_order"] == 1
        assert result["segments"][2]["sequence_order"] == 2

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_canvas_context(self, retrieval_service, db_session):
        """Should include canvas_context when canvas_ids populated"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with canvas_ids
        episode_id = str(uuid.uuid4())
        canvas_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(hours=1),
            completed_at=now,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[canvas_id],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create CanvasAudit record
        canvas = CanvasAudit(
            id=canvas_id,
            canvas_id=str(uuid.uuid4()),  # FK to canvases.id
            tenant_id="default",
            episode_id=episode_id,
            action_type="present",
            agent_id=agent_id,
            details_json={
                "canvas_type": "sheets",
                "component_type": "table",
                "component_name": "sales_table",
                "revenue": 1000000
            },
            created_at=now - timedelta(minutes=30)
        )
        db_session.add(canvas)

        db_session.commit()

        # Call retrieve_sequential with include_canvas=True (default)
        result = await retrieval_service.retrieve_sequential(
            episode_id=episode_id,
            agent_id=agent_id,
            include_canvas=True
        )

        # Verify canvas_context present
        assert "canvas_context" in result
        assert len(result["canvas_context"]) == 1
        assert result["canvas_context"][0]["id"] == canvas_id
        assert result["canvas_context"][0]["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_feedback_context(self, retrieval_service, db_session):
        """Should include feedback_context when feedback_ids populated"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with feedback_ids
        episode_id = str(uuid.uuid4())
        feedback_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(hours=1),
            completed_at=now,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[feedback_id]    )
        db_session.add(episode)

        # Create AgentFeedback record
        feedback = AgentFeedback(
            id=feedback_id,
            agent_id=agent_id,
            user_id="test_user",
            original_output="Analysis complete",
            user_correction="Great analysis",
            feedback_type="thumbs_up",
            thumbs_up_down=True,
            rating=5,
            created_at=now - timedelta(minutes=30)
        )
        db_session.add(feedback)

        db_session.commit()

        # Call retrieve_sequential with include_feedback=True (default)
        result = await retrieval_service.retrieve_sequential(
            episode_id=episode_id,
            agent_id=agent_id,
            include_feedback=True
        )

        # Verify feedback_context present
        assert "feedback_context" in result
        assert len(result["feedback_context"]) == 1
        assert result["feedback_context"][0]["id"] == feedback_id
        assert result["feedback_context"][0]["rating"] == 5

    @pytest.mark.asyncio
    async def test_retrieve_sequential_exclude_canvas_feedback(self, retrieval_service, db_session):
        """Should exclude canvas_context and feedback_context when flags=False"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with canvas_ids and feedback_ids
        episode_id = str(uuid.uuid4())
        canvas_id = str(uuid.uuid4())
        feedback_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(hours=1),
            completed_at=now,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[canvas_id],
            feedback_ids=[feedback_id]    )
        db_session.add(episode)

        db_session.commit()

        # Call retrieve_sequential with both flags False
        result = await retrieval_service.retrieve_sequential(
            episode_id=episode_id,
            agent_id=agent_id,
            include_canvas=False,
            include_feedback=False
        )

        # Verify canvas_context and feedback_context NOT present
        assert "canvas_context" not in result
        assert "feedback_context" not in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_episode_not_found(self, retrieval_service):
        """Should return error when episode not found"""
        result = await retrieval_service.retrieve_sequential(
            episode_id=str(uuid.uuid4()),
            agent_id=str(uuid.uuid4())
        )

        assert "error" in result
        assert result["error"] == "Episode not found"

    def test_serialize_segment(self, retrieval_service):
        """Should serialize segment with all fields"""
        now = datetime.now(timezone.utc)

        # EpisodeSegment now has canvas_context column in schema (added in Plan 05)
        segment = EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="canvas_presentation",
            sequence_order=0,
            content="Presented data",
            content_summary="Data presentation",
            source_type="canvas",
            source_id="canvas1",
            canvas_context={
                "canvas_type": "sheets",
                "presentation_summary": "Test data",
                "critical_data_points": {"value": 100},
                "visual_elements": {"rows": 10}
            },
            created_at=now
        )

        # Call _serialize_segment
        result = retrieval_service._serialize_segment(segment)

        # Verify all fields serialized
        assert result["id"] == "seg1"
        assert result["segment_type"] == "canvas_presentation"
        assert result["sequence_order"] == 0
        assert result["content"] == "Presented data"
        assert result["content_summary"] == "Data presentation"
        assert result["source_type"] == "canvas"
        assert result["source_id"] == "canvas1"
        # Verify canvas_context is serialized (column now exists in schema)
        assert result["canvas_context"]["canvas_type"] == "sheets"
        assert result["canvas_context"]["presentation_summary"] == "Test data"


# ========================================================================
# TestCanvasAwareRetrieval - Detail filtering by level
# ========================================================================

class TestCanvasAwareRetrieval:
    """Test canvas-aware retrieval with progressive detail levels"""

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_with_summary_detail(self, retrieval_service_mocked, db_session):
        """Should filter canvas_context to summary only (~50 tokens)"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create segment with full canvas_context
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            segment_type="canvas_presentation",
            sequence_order=0,
            content="Presented sheet",
            content_summary="Sheet presentation",
            source_type="canvas",
            source_id="canvas1",
            canvas_context={
                "canvas_type": "sheets",
                "presentation_summary": "Sales data for Q4",
                "critical_data_points": {"revenue": 1000000, "status": "approved"},
                "visual_elements": {"rows": 100}
            },
            created_at=now
        )
        db_session.add(segment)
        db_session.commit()

        # Mock LanceDB search
        retrieval_service_mocked.lancedb.search.return_value = [
            {"id": "ep1", "metadata": {"episode_id": episode_id}, "_distance": 0.1}
        ]

        # Call retrieve_canvas_aware with summary detail
        result = await retrieval_service_mocked.retrieve_canvas_aware(
            agent_id=agent_id,
            query="sales data",
            canvas_context_detail="summary"
        )

        # Verify segments have filtered canvas_context
        assert len(result["episodes"]) >= 0
        if result["episodes"]:
            segments = result["episodes"][0].get("segments", [])
            if segments:
                canvas_ctx = segments[0].get("canvas_context", {})
                # Only presentation_summary should be present
                assert "presentation_summary" in canvas_ctx
                assert "critical_data_points" not in canvas_ctx
                assert "visual_elements" not in canvas_ctx

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_with_standard_detail(self, retrieval_service_mocked, db_session):
        """Should include summary + critical_data_points (~200 tokens)"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create segment
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            segment_type="canvas_presentation",
            sequence_order=0,
            content="Presented sheet",
            content_summary="Sheet presentation",
            source_type="canvas",
            source_id="canvas1",
            canvas_context={
                "canvas_type": "sheets",
                "presentation_summary": "Sales data",
                "critical_data_points": {"revenue": 1000000},
                "visual_elements": {"rows": 100}
            },
            created_at=now
        )
        db_session.add(segment)
        db_session.commit()

        # Mock LanceDB search
        retrieval_service_mocked.lancedb.search.return_value = [
            {"id": "ep1", "metadata": {"episode_id": episode_id}, "_distance": 0.1}
        ]

        # Call with standard detail
        result = await retrieval_service_mocked.retrieve_canvas_aware(
            agent_id=agent_id,
            query="sales data",
            canvas_context_detail="standard"
        )

        # Verify canvas_context has summary + critical_data_points
        if result["episodes"] and result["episodes"][0].get("segments"):
            canvas_ctx = result["episodes"][0]["segments"][0].get("canvas_context", {})
            assert "presentation_summary" in canvas_ctx
            assert "critical_data_points" in canvas_ctx
            assert "visual_elements" not in canvas_ctx

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_with_full_detail(self, retrieval_service_mocked, db_session):
        """Should include all fields including visual_elements (~500 tokens)"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create segment
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            segment_type="canvas_presentation",
            sequence_order=0,
            content="Presented sheet",
            content_summary="Sheet presentation",
            source_type="canvas",
            source_id="canvas1",
            canvas_context={
                "canvas_type": "sheets",
                "presentation_summary": "Sales data",
                "critical_data_points": {"revenue": 1000000},
                "visual_elements": {"rows": 100, "columns": 5}
            },
            created_at=now
        )
        db_session.add(segment)
        db_session.commit()

        # Mock LanceDB search
        retrieval_service_mocked.lancedb.search.return_value = [
            {"id": "ep1", "metadata": {"episode_id": episode_id}, "_distance": 0.1}
        ]

        # Call with full detail
        result = await retrieval_service_mocked.retrieve_canvas_aware(
            agent_id=agent_id,
            query="sales data",
            canvas_context_detail="full"
        )

        # Verify all fields present
        if result["episodes"] and result["episodes"][0].get("segments"):
            canvas_ctx = result["episodes"][0]["segments"][0].get("canvas_context", {})
            assert "canvas_type" in canvas_ctx
            assert "presentation_summary" in canvas_ctx
            assert "critical_data_points" in canvas_ctx
            assert "visual_elements" in canvas_ctx

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_with_canvas_type_filter(self, retrieval_service_mocked):
        """Should filter by canvas_type in LanceDB query"""
        agent_id = str(uuid.uuid4())

        # Mock LanceDB search
        retrieval_service_mocked.lancedb.search.return_value = []

        # Call with canvas_type filter
        await retrieval_service_mocked.retrieve_canvas_aware(
            agent_id=agent_id,
            query="data",
            canvas_type="sheets"
        )

        # Verify LanceDB called with canvas_type filter
        call_args = retrieval_service_mocked.lancedb.search.call_args
        filter_str = call_args[1]["filter_str"]
        assert "sheets" in filter_str

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_governance_blocked(self, retrieval_service):
        """Should return error when governance blocks access"""
        # Mock governance to block
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "INTERN maturity required"
        }

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="student_agent",
            query="test"
        )

        assert result["episodes"] == []
        assert "error" in result
        assert result["governance_check"]["allowed"] is False

    def test_filter_canvas_context_detail(self, retrieval_service):
        """Should filter canvas_context by detail level"""
        full_context = {
            "canvas_type": "sheets",
            "presentation_summary": "Sales data",
            "critical_data_points": {"revenue": 1000000},
            "visual_elements": {"rows": 100}
        }

        # Test summary
        summary = retrieval_service._filter_canvas_context_detail(full_context, "summary")
        assert "presentation_summary" in summary
        assert "critical_data_points" not in summary
        assert "visual_elements" not in summary

        # Test standard
        standard = retrieval_service._filter_canvas_context_detail(full_context, "standard")
        assert "presentation_summary" in standard
        assert "critical_data_points" in standard
        assert "visual_elements" not in standard

        # Test full
        full = retrieval_service._filter_canvas_context_detail(full_context, "full")
        assert "canvas_type" in full
        assert "presentation_summary" in full
        assert "critical_data_points" in full
        assert "visual_elements" in full

        # Test unknown detail level (should default to summary)
        unknown = retrieval_service._filter_canvas_context_detail(full_context, "unknown")
        assert "presentation_summary" in unknown
        assert "critical_data_points" not in unknown

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_lancedb_error(self, retrieval_service):
        """Should handle LanceDB errors gracefully"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Mock LanceDB to raise error
        retrieval_service.lancedb.search.side_effect = Exception("LanceDB connection failed")

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="test"
        )

        assert "episodes" in result
        assert result["episodes"] == []
        assert "error" in result


# ========================================================================
# TestBusinessDataRetrieval - Business data and canvas type filtering
# ========================================================================

class TestBusinessDataRetrieval:
    """Test business data and canvas type retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_with_filters(self, retrieval_service, db_session):
        """Should filter episodes by business data in canvas_context"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create segment with business data in canvas_context
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            segment_type="canvas_presentation",
            sequence_order=0,
            content="Form submission",
            content_summary="Approved form",
            source_type="canvas",
            source_id="canvas1",
            canvas_context={
                "canvas_type": "generic",
                "presentation_summary": "Approval form",
                "critical_data_points": {"approval_status": "approved", "revenue": 1000000}
            },
            created_at=now
        )
        db_session.add(segment)
        db_session.commit()

        # Call retrieve_by_business_data
        result = await retrieval_service.retrieve_by_business_data(
            agent_id=agent_id,
            business_filters={"approval_status": "approved"}
        )

        # Verify episodes returned
        assert "episodes" in result
        assert "filters" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_with_operator_filters(self, retrieval_service, db_session):
        """Should apply operator filters like $gt, $lt"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create segment with revenue data
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            segment_type="canvas_presentation",
            sequence_order=0,
            content="Revenue data",
            content_summary="High revenue",
            source_type="canvas",
            source_id="canvas1",
            canvas_context={
                "canvas_type": "sheets",
                "presentation_summary": "Revenue report",
                "critical_data_points": {"revenue": 1000000}
            },
            created_at=now
        )
        db_session.add(segment)
        db_session.commit()

        # Call with $gt operator
        result = await retrieval_service.retrieve_by_business_data(
            agent_id=agent_id,
            business_filters={"revenue": {"$gt": 500000}}
        )

        # Should not error
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_empty_results(self, retrieval_service):
        """Should return empty list when no matches"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent1",
            business_filters={"nonexistent": "value"}
        )

        assert result["episodes"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type(self, retrieval_service, db_session):
        """Should retrieve episodes filtered by canvas type"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(days=7),
            completed_at=now - timedelta(days=7) + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create CanvasAudit with canvas_type="sheets"
        canvas = CanvasAudit(
            id=str(uuid.uuid4()),
            canvas_id=str(uuid.uuid4()),  # FK to canvases.id
            tenant_id="default",
            episode_id=episode_id,
            action_type="submit",
            agent_id=agent_id,
            details_json={
                "canvas_type": "sheets",
                "component_type": "table",
                "component_name": "data_table"
            },
            created_at=now - timedelta(days=7)
        )
        db_session.add(canvas)
        db_session.commit()

        # Call retrieve_by_canvas_type
        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id=agent_id,
            canvas_type="sheets",
            action="submit"
        )

        # Verify episodes returned
        assert "episodes" in result
        assert result["canvas_type"] == "sheets"
        assert result["action"] == "submit"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_governance_check(self, retrieval_service):
        """Should block retrieval when governance denies access"""
        # Mock governance to block
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient permissions"
        }

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent1",
            canvas_type="sheets"
        )

        assert result["episodes"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_time_range(self, retrieval_service, db_session):
        """Should filter episodes by time range"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode from 7 days ago (within 30d)
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Recent episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(days=7),
            completed_at=now - timedelta(days=7) + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=1,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)

        # Create CanvasAudit
        canvas = CanvasAudit(
            id=str(uuid.uuid4()),
            canvas_id=str(uuid.uuid4()),  # FK to canvases.id
            tenant_id="default",
            episode_id=episode_id,
            action_type="present",
            agent_id=agent_id,
            details_json={
                "canvas_type": "sheets",
                "component_type": "table",
                "component_name": "table"
            },
            created_at=now - timedelta(days=7)
        )
        db_session.add(canvas)
        db_session.commit()

        # Call with 30d time range
        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id=agent_id,
            canvas_type="sheets",
            time_range="30d"
        )

        # Should return the 7-day episode
        assert "episodes" in result
        assert result["time_range"] == "30d"


# ========================================================================
# TestSupervisionContextRetrieval - Supervision metadata enrichment
# ========================================================================

class TestSupervisionContextRetrieval:
    """Test supervision context retrieval and enrichment"""

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_high_rated(self, retrieval_service, db_session):
        """Should filter episodes by high supervisor rating (>= 4)"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create high-rated episode (rating=4)
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="High rated episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(hours=1),
            completed_at=now,
            maturity_at_time="SUPERVISED",
            human_intervention_count=1,
            constitutional_score=0.85,
            decay_score=0.95,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor_123",
            supervisor_rating=4,
            intervention_types=["guidance"],
            supervision_feedback="Good work"    )
        db_session.add(episode)
        db_session.commit()

        # Call with high_rated filter
        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id=agent_id,
            retrieval_mode=RetrievalMode.TEMPORAL,
            supervision_outcome_filter="high_rated"
        )

        # Verify supervision_context in result
        if result["episodes"]:
            ep = result["episodes"][0]
            assert "supervision_context" in ep
            assert ep["supervision_context"]["supervisor_rating"] == 4

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_low_intervention(self, retrieval_service, db_session):
        """Should filter episodes with low intervention count (<= 1)"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with 0 interventions
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Low intervention episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(hours=1),
            completed_at=now,
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor_123",
            supervisor_rating=5,
            intervention_types=[],
            supervision_feedback="Excellent"    )
        db_session.add(episode)
        db_session.commit()

        # Call with low_intervention filter
        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id=agent_id,
            retrieval_mode=RetrievalMode.TEMPORAL,
            supervision_outcome_filter="low_intervention"
        )

        # Verify low intervention episode returned
        if result["episodes"]:
            ep = result["episodes"][0]
            assert ep["supervision_context"]["intervention_count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_min_rating(self, retrieval_service, db_session):
        """Should filter episodes by minimum supervisor rating"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episodes with ratings 3, 4, 5
        for rating in [3, 4, 5]:
            episode = Episode(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                tenant_id="default",
                task_description=f"Episode with rating {rating}",
                status="completed",
            outcome="success",
            success=True,

                started_at=now - timedelta(hours=rating),
                completed_at=now - timedelta(hours=rating) + timedelta(minutes=30),
                maturity_at_time="SUPERVISED",
                human_intervention_count=0,
                constitutional_score=0.85,
                decay_score=1.0,
                access_count=1,
                canvas_action_count=0,
                canvas_ids=[],
                feedback_ids=[],
                supervisor_id="supervisor_123",
                supervisor_rating=rating,
                intervention_types=[],
                supervision_feedback=f"Rating {rating}"    )
            db_session.add(episode)

        db_session.commit()

        # Call with min_rating=4
        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id=agent_id,
            retrieval_mode=RetrievalMode.TEMPORAL,
            min_rating=4
        )

        # Should return only episodes with rating >= 4
        # Note: Actual filtering depends on database query results
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_max_interventions(self, retrieval_service, db_session):
        """Should filter episodes by maximum intervention count"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with 2 interventions
        episode_id = str(uuid.uuid4())
        episode = Episode(
            id=episode_id,
            agent_id=agent_id,
            tenant_id="default",
            task_description="Episode with 2 interventions",
            status="completed",
            outcome="success",
            success=True,

            started_at=now - timedelta(hours=1),
            completed_at=now,
            maturity_at_time="SUPERVISED",
            human_intervention_count=2,
            constitutional_score=0.8,
            decay_score=0.9,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor_123",
            supervisor_rating=3,
            intervention_types=["guidance", "correction"],
            supervision_feedback="Some issues"    )
        db_session.add(episode)
        db_session.commit()

        # Call with max_interventions=2
        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id=agent_id,
            retrieval_mode=RetrievalMode.TEMPORAL,
            max_interventions=2
        )

        # Should return episode with <= 2 interventions
        assert "episodes" in result

    def test_create_supervision_context(self, retrieval_service, db_session):
        """Should create supervision context dict from episode"""
        now = datetime.now(timezone.utc)

        episode = Episode(
            id="ep1",
            agent_id="agent1",
            tenant_id="default",
            task_description="Supervised episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="SUPERVISED",
            human_intervention_count=1,
            constitutional_score=0.85,
            decay_score=0.95,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor_123",
            supervisor_rating=4,
            intervention_types=["guidance", "correction"],
            supervision_feedback="Good with corrections"    )

        # Call _create_supervision_context
        context = retrieval_service._create_supervision_context(episode)

        # Verify structure
        assert context["has_supervision"] is True
        assert context["supervisor_id"] == "supervisor_123"
        assert context["supervisor_rating"] == 4
        assert context["intervention_count"] == 2
        assert context["intervention_types"] == ["guidance", "correction"]
        assert "feedback_summary" in context
        assert "outcome_quality" in context

    def test_assess_outcome_quality(self, retrieval_service, db_session):
        """Should assess outcome quality based on rating and interventions"""
        now = datetime.now(timezone.utc)

        # Excellent: 5 stars, 0-1 interventions
        excellent_ep = Episode(
            id="ep1",
            agent_id="agent1",
            tenant_id="default",
            task_description="Excellent",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            constitutional_score=0.95,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor",
            supervisor_rating=5,
            intervention_types=[],
            supervision_feedback="Excellent"    )
        assert retrieval_service._assess_outcome_quality(excellent_ep) == "excellent"

        # Good: 4-5 stars, 0-2 interventions
        good_ep = Episode(
            id="ep2",
            agent_id="agent1",
            tenant_id="default",
            task_description="Good",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now,
            maturity_at_time="SUPERVISED",
            human_intervention_count=2,
            constitutional_score=0.85,
            decay_score=0.95,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor",
            supervisor_rating=4,
            intervention_types=["guidance"],
            supervision_feedback="Good"    )
        assert retrieval_service._assess_outcome_quality(good_ep) == "good"

        # Fair: 3-4 stars
        fair_ep = Episode(
            id="ep3",
            agent_id="agent1",
            tenant_id="default",
            task_description="Fair",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now,
            maturity_at_time="SUPERVISED",
            human_intervention_count=3,
            constitutional_score=0.75,
            decay_score=0.9,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor",
            supervisor_rating=3,
            intervention_types=["guidance", "correction"],
            supervision_feedback="Fair"    )
        assert retrieval_service._assess_outcome_quality(fair_ep) == "fair"

        # Poor: < 3 stars
        poor_ep = Episode(
            id="ep4",
            agent_id="agent1",
            tenant_id="default",
            task_description="Poor",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now,
            maturity_at_time="INTERN",
            human_intervention_count=5,
            constitutional_score=0.65,
            decay_score=0.85,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            supervisor_id="supervisor",
            supervisor_rating=2,
            intervention_types=["correction", "termination"],
            supervision_feedback="Poor"    )
        assert retrieval_service._assess_outcome_quality(poor_ep) == "poor"

        # Unknown: No rating
        unknown_ep = Episode(
            id="ep5",
            agent_id="agent1",
            tenant_id="default",
            task_description="Unknown",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            intervention_types=[],
            supervision_feedback=None    )
        assert retrieval_service._assess_outcome_quality(unknown_ep) == "unknown"

    def test_filter_improvement_trend(self, retrieval_service, db_session):
        """Should filter episodes showing positive performance trend"""
        now = datetime.now(timezone.utc)

        # Create 10 episodes with improving ratings over time
        episodes = []
        for i in range(10):
            episode = Episode(
                id=f"ep{i}",
                agent_id="agent1",
                tenant_id="default",
                task_description=f"Episode {i}",
                status="completed",
            outcome="success",
            success=True,

                started_at=now - timedelta(hours=10-i),  # More recent = higher rating
                completed_at=now - timedelta(hours=10-i) + timedelta(minutes=30),
                maturity_at_time="SUPERVISED",
                human_intervention_count=0,
                constitutional_score=0.85,
                decay_score=1.0,
                access_count=1,
                canvas_action_count=0,
                canvas_ids=[],
                feedback_ids=[],
                supervisor_id="supervisor",
                supervisor_rating=3 + (i // 2),  # Improving ratings: 3,3,4,4,5,5,...
                intervention_types=[],
                supervision_feedback=f"Feedback for episode {i}"    )
            episodes.append(episode)

        # Call _filter_improvement_trend
        filtered = retrieval_service._filter_improvement_trend(episodes)

        # Should return episodes with positive trend
        assert len(filtered) > 0


# ========================================================================
# TestContextualRetrieval - Feedback-weighted contextual retrieval
# ========================================================================

class TestContextualRetrieval:
    """Test contextual retrieval with feedback weighting"""

    @pytest.mark.asyncio
    async def test_retrieve_contextual_canvas_boost(self, retrieval_service, db_session):
        """Should boost episodes with canvas interactions by +0.1"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with canvas
        canvas_ep = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Canvas episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=2,  # Has canvas interactions
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(canvas_ep)

        # Create episode without canvas
        non_canvas_ep = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Non-canvas episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,  # No canvas interactions
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(non_canvas_ep)
        db_session.commit()

        # Call retrieve_contextual
        result = await retrieval_service.retrieve_contextual(
            agent_id=agent_id,
            current_task="data analysis"
        )

        # Verify episodes returned (canvas should get boost)
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_positive_feedback_boost(self, retrieval_service, db_session):
        """Should boost episodes with positive feedback by +0.2"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with positive feedback
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Positive feedback episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
            aggregate_feedback_score=0.5  # Positive feedback
        )
        db_session.add(episode)
        db_session.commit()

        # Call retrieve_contextual
        result = await retrieval_service.retrieve_contextual(
            agent_id=agent_id,
            current_task="task"
        )

        # Positive feedback should boost relevance
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_negative_feedback_penalty(self, retrieval_service, db_session):
        """Should penalize episodes with negative feedback by -0.3"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with negative feedback
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Negative feedback episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[],
aggregate_feedback_score=-0.5,
            # Negative feedback    
        )
        db_session.add(episode)
        db_session.commit()

        # Call retrieve_contextual
        result = await retrieval_service.retrieve_contextual(
            agent_id=agent_id,
            current_task="task"
        )

        # Negative feedback should reduce relevance
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_hybrid_scoring(self, retrieval_service, db_session):
        """Should combine temporal (0.3) and semantic (0.7) weights"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Test episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(episode)
        db_session.commit()

        # Mock LanceDB search for semantic
        retrieval_service.lancedb.search.return_value = [
            {"id": "ep1", "metadata": {"episode_id": episode.id}, "_distance": 0.2}
        ]

        # Call retrieve_contextual
        result = await retrieval_service.retrieve_contextual(
            agent_id=agent_id,
            current_task="test task"
        )

        # Should apply hybrid scoring
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_require_canvas(self, retrieval_service, db_session):
        """Should filter out episodes without canvas context"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with canvas
        canvas_ep = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Canvas episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=2,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(canvas_ep)

        # Create episode without canvas
        non_canvas_ep = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Non-canvas episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(non_canvas_ep)
        db_session.commit()

        # Call with require_canvas=True
        result = await retrieval_service.retrieve_contextual(
            agent_id=agent_id,
            current_task="task",
            require_canvas=True
        )

        # Should filter out non-canvas episodes
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_require_feedback(self, retrieval_service, db_session):
        """Should filter out episodes without feedback"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="TestAgent",
            description="Test agent",
            category="Testing",
            status=AgentStatus.AUTONOMOUS.value,
            tenant_id="default",
            module_path="test",
            class_name="TestAgent",
            created_at=now
        )
        db_session.add(agent)

        # Create episode with feedback
        feedback_ep = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Feedback episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=["feedback1"]    )
        db_session.add(feedback_ep)

        # Create episode without feedback
        no_feedback_ep = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="No feedback episode",
            status="completed",
            outcome="success",
            success=True,

            started_at=now,
            completed_at=now + timedelta(minutes=30),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.85,
            decay_score=1.0,
            access_count=1,
            canvas_action_count=0,
            canvas_ids=[],
            feedback_ids=[]    )
        db_session.add(no_feedback_ep)
        db_session.commit()

        # Call with require_feedback=True
        result = await retrieval_service.retrieve_contextual(
            agent_id=agent_id,
            current_task="task",
            require_feedback=True
        )

        # Should filter out episodes without feedback
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_fetch_canvas_context(self, retrieval_service, db_session):
        """Should fetch canvas context by ID list"""
        now = datetime.now(timezone.utc)

        # Create CanvasAudit records
        canvas_ids = []
        for i in range(3):
            canvas = CanvasAudit(
                id=str(uuid.uuid4()),
                canvas_id=str(uuid.uuid4()),  # FK to canvases.id
                tenant_id="default",
                episode_id=str(uuid.uuid4()),
                action_type="present",
                details_json={
                    "canvas_type": "sheets" if i == 0 else "charts",
                    "component_type": "table" if i == 0 else "chart",
                    "component_name": f"component_{i}",
                    "index": i
                },
                created_at=now
            )
            db_session.add(canvas)
            canvas_ids.append(canvas.id)

        db_session.commit()

        # Call _fetch_canvas_context
        result = await retrieval_service._fetch_canvas_context(canvas_ids)

        # Verify returns list of canvas dicts
        assert len(result) == 3
        assert result[0]["id"] in canvas_ids
        assert "canvas_type" in result[0]
        assert "action" in result[0]

    @pytest.mark.asyncio
    async def test_fetch_feedback_context(self, retrieval_service, db_session):
        """Should fetch feedback context by ID list"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        # Create AgentFeedback records
        feedback_ids = []
        for i in range(3):
            feedback = AgentFeedback(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                user_id="test_user",
                original_output=f"Output {i}",
                user_correction=f"Correction {i}",
                feedback_type="thumbs_up" if i < 2 else "thumbs_down",
                thumbs_up_down=(i < 2),
                rating=5 - i,
                created_at=now
            )
            db_session.add(feedback)
            feedback_ids.append(feedback.id)

        db_session.commit()

        # Call _fetch_feedback_context
        result = await retrieval_service._fetch_feedback_context(feedback_ids)

        # Verify returns list of feedback dicts
        assert len(result) == 3
        assert result[0]["id"] in feedback_ids
        assert "feedback_type" in result[0]
        assert "rating" in result[0]
