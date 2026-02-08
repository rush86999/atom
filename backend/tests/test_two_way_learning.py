"""
Comprehensive tests for Two-Way Learning System.

Tests supervisor learning from feedback, ratings, comments, and votes.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import uuid

from core.database import SessionLocal
from core.models import (
    AgentRegistry,
    AgentStatus,
    SupervisionSession,
    SupervisionStatus,
    User,
    Workspace,
    SupervisorRating,
    SupervisorComment,
    FeedbackVote,
    SupervisorPerformance,
    InterventionOutcome,
)
from core.feedback_service import FeedbackService
from core.supervisor_performance_service import SupervisorPerformanceService
from core.supervisor_learning_service import SupervisorLearningService


@pytest.fixture
def db():
    """Create a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up test data
        db.query(InterventionOutcome).filter(InterventionOutcome.id.like("test_%")).delete()
        db.query(SupervisorPerformance).delete()
        db.query(FeedbackVote).filter(FeedbackVote.id.like("test_%")).delete()
        db.query(SupervisorComment).filter(SupervisorComment.id.like("test_%")).delete()
        db.query(SupervisorRating).filter(SupervisorRating.id.like("test_%")).delete()
        db.query(SupervisionSession).filter(SupervisionSession.id.like("test_%")).delete()
        db.query(AgentRegistry).filter(AgentRegistry.id.like("test_%")).delete()
        db.query(Workspace).filter(Workspace.id.like("test_%")).delete()
        db.query(User).filter(User.id.like("test_%")).delete()
        db.commit()
        db.close()


class TestFeedbackService:
    """Test feedback management functionality."""

    @pytest.mark.asyncio
    async def test_rate_supervisor(self, db: Session):
        """Test creating supervisor rating."""
        # Create test data
        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        user = User(
            id=supervisor_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="Supervisor",
        )
        db.add(user)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
            status=AgentStatus.SUPERVISED.value,
        )
        db.add(agent)

        workspace = Workspace(id=f"test_workspace_{uuid.uuid4().hex[:8]}", name="Test")
        db.add(workspace)

        session = SupervisionSession(
            id=f"test_session_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_name=agent.name,
            workspace_id=workspace.id,
            supervisor_id=supervisor_id,
            status=SupervisionStatus.COMPLETED.value,
            trigger_context={},  # Required field
            started_at=datetime.now() - timedelta(seconds=300),
            completed_at=datetime.now(),
        )
        db.add(session)
        db.commit()

        # Create rating
        feedback_service = FeedbackService(db)
        rating = await feedback_service.rate_supervisor(
            supervision_session_id=session.id,
            rater_id=supervisor_id,
            rating=5,
            rating_category="helpfulness",
            reason="Excellent guidance",
        )

        assert rating is not None
        assert rating.rating == 5
        assert rating.was_helpful is True
        assert rating.reason == "Excellent guidance"
        print(f"✓ Created supervisor rating: {rating.id}")

    @pytest.mark.asyncio
    async def test_threaded_comments(self, db: Session):
        """Test creating threaded comment hierarchy."""
        feedback_service = FeedbackService(db)

        # Create test data
        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        user = User(
            id=supervisor_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
        )
        db.add(agent)

        workspace = Workspace(id=f"test_workspace_{uuid.uuid4().hex[:8]}", name="Test")
        db.add(workspace)

        session = SupervisionSession(
            id=f"test_session_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_name=agent.name,
            workspace_id=workspace.id,
            supervisor_id=supervisor_id,
            status=SupervisionStatus.COMPLETED.value,
            trigger_context={},  # Required field
        )
        db.add(session)
        db.commit()

        # Create root comment
        root_comment = await feedback_service.add_comment(
            supervision_session_id=session.id,
            author_id=supervisor_id,
            content="Great work on this session",
        )
        assert root_comment.depth == 0
        assert root_comment.thread_path == "root"

        # Create reply
        reply = await feedback_service.add_comment(
            supervision_session_id=session.id,
            author_id=supervisor_id,
            content="Thank you for the feedback",
            parent_comment_id=root_comment.id,
        )
        assert reply.depth == 1
        assert reply.thread_path == f"root.{root_comment.id}"
        assert root_comment.reply_count == 1

        # Create nested reply
        nested_reply = await feedback_service.add_comment(
            supervision_session_id=session.id,
            author_id=supervisor_id,
            content="You're welcome",
            parent_comment_id=reply.id,
        )
        assert nested_reply.depth == 2
        assert reply.reply_count == 1

        print(f"✓ Created threaded comments: depth 0 → 1 → 2")

    @pytest.mark.asyncio
    async def test_comment_voting(self, db: Session):
        """Test thumbs up/down voting on comments."""
        feedback_service = FeedbackService(db)

        # Create test data
        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        user = User(
            id=supervisor_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
        )
        db.add(agent)

        workspace = Workspace(id=f"test_workspace_{uuid.uuid4().hex[:8]}", name="Test")
        db.add(workspace)

        session = SupervisionSession(
            id=f"test_session_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_name=agent.name,
            workspace_id=workspace.id,
            supervisor_id=supervisor_id,
            status=SupervisionStatus.COMPLETED.value,
            trigger_context={},  # Required field
        )
        db.add(session)
        db.commit()

        # Create comment
        comment = await feedback_service.add_comment(
            supervision_session_id=session.id,
            author_id=supervisor_id,
            content="Helpful comment",
        )

        # Upvote
        vote1 = await feedback_service.vote_on_comment(
            comment_id=comment.id,
            user_id=supervisor_id,
            vote_type="up",
        )
        assert vote1 is not None
        assert vote1.vote_type == "up"

        db.refresh(comment)
        assert comment.upvote_count == 1

        # Toggle off
        vote2 = await feedback_service.vote_on_comment(
            comment_id=comment.id,
            user_id=supervisor_id,
            vote_type="up",
        )
        assert vote2 is None  # Removed

        db.refresh(comment)
        assert comment.upvote_count == 0

        # Downvote
        vote3 = await feedback_service.vote_on_comment(
            comment_id=comment.id,
            user_id=supervisor_id,
            vote_type="down",
        )
        assert vote3 is not None
        assert vote3.vote_type == "down"

        db.refresh(comment)
        assert comment.downvote_count == 1

        print(f"✓ Comment voting works correctly")

    @pytest.mark.asyncio
    async def test_session_voting(self, db: Session):
        """Test thumbs up/down voting on sessions."""
        feedback_service = FeedbackService(db)

        # Create test data
        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        user = User(
            id=supervisor_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
        )
        db.add(agent)

        workspace = Workspace(id=f"test_workspace_{uuid.uuid4().hex[:8]}", name="Test")
        db.add(workspace)

        session = SupervisionSession(
            id=f"test_session_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_name=agent.name,
            workspace_id=workspace.id,
            supervisor_id=supervisor_id,
            status=SupervisionStatus.COMPLETED.value,
            trigger_context={},  # Required field
        )
        db.add(session)
        db.commit()

        # Upvote session
        vote = await feedback_service.vote_on_session(
            supervision_session_id=session.id,
            user_id=supervisor_id,
            vote_type="up",
            vote_reason="Very helpful",
        )
        assert vote is not None
        assert vote.vote_type == "up"
        assert vote.vote_reason == "Very helpful"

        # Get summary
        summary = await feedback_service.get_session_feedback_summary(session.id)
        assert summary["upvotes"] == 1
        assert summary["downvotes"] == 0
        assert summary["net_score"] == 1

        print(f"✓ Session voting works correctly")


class TestSupervisorPerformanceService:
    """Test supervisor performance tracking."""

    @pytest.mark.asyncio
    async def test_get_supervisor_metrics(self, db: Session):
        """Test retrieving comprehensive supervisor metrics."""
        perf_service = SupervisorPerformanceService(db)

        # Create test data
        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"

        # Create performance record
        performance = SupervisorPerformance(
            supervisor_id=supervisor_id,
            total_sessions_supervised=10,
            total_interventions=5,
            average_rating=4.5,
            total_ratings=8,
            rating_5_count=5,
            rating_4_count=2,
            rating_3_count=1,
            confidence_score=0.75,
            competence_level="intermediate",
        )
        db.add(performance)
        db.commit()

        # Get metrics
        metrics = await perf_service.get_supervisor_metrics(supervisor_id)

        assert metrics["overall"]["total_sessions"] == 10
        assert metrics["overall"]["average_rating"] == 4.5
        assert metrics["overall"]["confidence_score"] == 0.75
        assert metrics["overall"]["competence_level"] == "intermediate"
        assert metrics["ratings"]["total"] == 8
        assert metrics["ratings"]["distribution"][5] == 5

        print(f"✓ Retrieved supervisor metrics")

    @pytest.mark.asyncio
    async def test_track_intervention_outcome(self, db: Session):
        """Test tracking intervention outcomes."""
        perf_service = SupervisorPerformanceService(db)

        # Create test data
        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        user = User(
            id=supervisor_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
        )
        db.add(agent)

        workspace = Workspace(id=f"test_workspace_{uuid.uuid4().hex[:8]}", name="Test")
        db.add(workspace)

        session = SupervisionSession(
            id=f"test_session_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_name=agent.name,
            workspace_id=workspace.id,
            supervisor_id=supervisor_id,
            status=SupervisionStatus.COMPLETED.value,
            trigger_context={},  # Required field
        )
        db.add(session)

        # Create performance record
        performance = SupervisorPerformance(
            supervisor_id=supervisor_id,
            confidence_score=0.5,
        )
        db.add(performance)
        db.commit()

        # Track intervention outcome
        outcome = await perf_service.track_intervention_outcome(
            supervision_session_id=session.id,
            intervention_type="correct",
            intervention_timestamp=datetime.now(),
            outcome="success",
            agent_behavior_change="Adjusted approach",
            task_completion="completed",
            seconds_to_recovery=30,
            was_necessary=True,
            was_effective=True,
        )

        assert outcome is not None
        assert outcome.outcome == "success"
        assert outcome.was_effective is True

        db.refresh(performance)
        assert performance.total_interventions == 1
        assert performance.successful_interventions == 1

        print(f"✓ Tracked intervention outcome")

    @pytest.mark.asyncio
    async def test_get_leaderboard(self, db: Session):
        """Test supervisor leaderboard by rating."""
        perf_service = SupervisorPerformanceService(db)

        # Create multiple supervisors
        for i in range(3):
            supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"

            user = User(
                id=supervisor_id,
                email=f"test-{uuid.uuid4().hex[:8]}@example.com",
                first_name="Test",
                last_name=f"User{i}",
            )
            db.add(user)

            workspace = Workspace(id=f"test_workspace_{uuid.uuid4().hex[:8]}", name="Test")
            db.add(workspace)

            agent = AgentRegistry(
                id=f"test_agent_{uuid.uuid4().hex[:8]}",
                name="Test Agent",
                category="testing",
                module_path="agents.test",
                class_name="TestAgent",
            )
            db.add(agent)

            session = SupervisionSession(
                id=f"test_session_{uuid.uuid4().hex[:8]}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id=workspace.id,
                supervisor_id=supervisor_id,
                status=SupervisionStatus.COMPLETED.value,
                trigger_context={},  # Required field
                started_at=datetime.now() - timedelta(days=1),
                completed_at=datetime.now() - timedelta(days=1),
            )
            db.add(session)

            performance = SupervisorPerformance(
                supervisor_id=supervisor_id,
                average_rating=3.0 + i,  # 3.0, 4.0, 5.0
                confidence_score=0.5 + (i * 0.1),
                total_sessions_supervised=10 + i,
            )
            db.add(performance)

        db.commit()

        # Get leaderboard
        leaderboard = await perf_service.get_leaderboard(
            metric="average_rating",
            limit=10,
        )

        assert len(leaderboard) == 3
        # Should be sorted by rating descending
        assert leaderboard[0]["average_rating"] >= leaderboard[1]["average_rating"]
        assert leaderboard[1]["average_rating"] >= leaderboard[2]["average_rating"]

        print(f"✓ Generated leaderboard: {len(leaderboard)} supervisors")

    @pytest.mark.asyncio
    async def test_performance_recommendations(self, db: Session):
        """Test generating performance recommendations."""
        from core.models import InterventionOutcome

        perf_service = SupervisorPerformanceService(db)

        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        # Create user and agent
        user = User(
            id=supervisor_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
        )
        db.add(agent)

        workspace = Workspace(id=f"test_workspace_{uuid.uuid4().hex[:8]}", name="Test")
        db.add(workspace)

        # Create a supervision session for intervention outcomes
        session = SupervisionSession(
            id=f"test_session_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            agent_name=agent.name,
            workspace_id=workspace.id,
            supervisor_id=supervisor_id,
            status=SupervisionStatus.COMPLETED.value,
            trigger_context={},
        )
        db.add(session)

        # Create performance with low ratings
        performance = SupervisorPerformance(
            supervisor_id=supervisor_id,
            average_rating=2.5,
            total_ratings=15,
            rating_1_count=5,
            rating_2_count=5,
            rating_3_count=3,
            rating_4_count=2,
            rating_5_count=0,
            total_interventions=10,
            successful_interventions=3,
            failed_interventions=7,
            confidence_score=0.3,
            performance_trend="declining",
            total_sessions_supervised=25,
        )
        db.add(performance)

        # Create intervention outcomes (need >10 for success rate recommendation)
        for i in range(11):
            outcome = InterventionOutcome(
                id=f"test_outcome_{uuid.uuid4().hex[:8]}",
                supervision_session_id=session.id,
                supervisor_id=supervisor_id,
                agent_id=agent_id,
                intervention_type="correct" if i < 4 else "pause",
                intervention_timestamp=datetime.now(),
                outcome="success" if i < 4 else "failure",  # 3 success, 7 failure = 30% success rate
            )
            db.add(outcome)

        db.commit()

        # Get recommendations
        recommendations = await perf_service.get_performance_recommendations(supervisor_id)

        assert len(recommendations) > 0
        assert any("guidance" in r.lower() for r in recommendations)
        assert any("success rate" in r.lower() for r in recommendations)
        assert any("declining" in r.lower() for r in recommendations)

        print(f"✓ Generated {len(recommendations)} recommendations")


class TestSupervisorLearningService:
    """Test supervisor learning and confidence updates."""

    @pytest.mark.asyncio
    async def test_process_rating_feedback(self, db: Session):
        """Test processing rating feedback for learning."""
        learning_service = SupervisorLearningService(db)

        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"

        # Create performance record
        performance = SupervisorPerformance(
            supervisor_id=supervisor_id,
            confidence_score=0.5,
        )
        db.add(performance)
        db.commit()

        old_confidence = performance.confidence_score

        # Process 5-star rating
        result = await learning_service.process_feedback_for_learning(
            supervisor_id=supervisor_id,
            feedback_type="rating",
            feedback_data={"rating": 5},
        )

        assert result["feedback_type"] == "rating"
        assert result["old_confidence"] == old_confidence
        assert result["new_confidence"] > old_confidence  # Should increase

        print(f"✓ 5-star rating increased confidence: {old_confidence:.3f} → {result['new_confidence']:.3f}")

    @pytest.mark.asyncio
    async def test_process_intervention_outcome(self, db: Session):
        """Test processing intervention outcome for learning."""
        learning_service = SupervisorLearningService(db)

        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"

        performance = SupervisorPerformance(
            supervisor_id=supervisor_id,
            confidence_score=0.5,
        )
        db.add(performance)
        db.commit()

        old_confidence = performance.confidence_score

        # Process successful intervention
        result = await learning_service.process_feedback_for_learning(
            supervisor_id=supervisor_id,
            feedback_type="intervention_outcome",
            feedback_data={
                "outcome": "success",
                "was_effective": True,
            },
        )

        assert result["new_confidence"] > old_confidence

        # Process failed intervention
        result2 = await learning_service.process_feedback_for_learning(
            supervisor_id=supervisor_id,
            feedback_type="intervention_outcome",
            feedback_data={
                "outcome": "failure",
                "was_effective": False,
            },
        )

        assert result2["new_confidence"] < result["new_confidence"]  # Should decrease

        print(f"✓ Intervention outcomes adjust confidence correctly")

    @pytest.mark.asyncio
    async def test_calculate_learning_insights(self, db: Session):
        """Test generating comprehensive learning insights."""
        learning_service = SupervisorLearningService(db)

        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"

        # Create performance
        performance = SupervisorPerformance(
            supervisor_id=supervisor_id,
            confidence_score=0.8,
            competence_level="advanced",
            performance_trend="improving",
            learning_rate=0.05,
            total_sessions_supervised=75,
        )
        db.add(performance)
        db.commit()

        # Get insights
        insights = await learning_service.calculate_learning_insights(supervisor_id)

        assert insights["supervisor_id"] == supervisor_id
        assert insights["current_state"]["confidence_score"] == 0.8
        assert insights["current_state"]["competence_level"] == "advanced"
        assert len(insights["strengths"]) > 0
        assert len(insights["recommendations"]) > 0

        print(f"✓ Generated learning insights with {len(insights['strengths'])} strengths")

    @pytest.mark.asyncio
    async def test_update_competence_level(self, db: Session):
        """Test competence level updates."""
        learning_service = SupervisorLearningService(db)

        supervisor_id = f"test_supervisor_{uuid.uuid4().hex[:8]}"

        # Create performance with high metrics
        performance = SupervisorPerformance(
            supervisor_id=supervisor_id,
            confidence_score=0.9,
            competence_level="advanced",
            total_sessions_supervised=120,
            successful_interventions=90,
            failed_interventions=5,
        )
        db.add(performance)
        db.commit()

        # Update competence
        result = await learning_service.update_competence_level(supervisor_id)

        assert result["supervisor_id"] == supervisor_id
        assert result["level_changed"] is True
        assert result["new_level"] == "expert"

        print(f"✓ Competence updated: {result['old_level']} → {result['new_level']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
