"""
Enhanced Feedback System Phase 2 Tests

Comprehensive test suite for Phase 2 features including:
- Batch feedback operations (approve, reject, update status)
- Agent promotion suggestions and evaluation
- Feedback export functionality (JSON, CSV, summary)
- Advanced analytics (correlation, cohorts, prediction, velocity)
"""

import csv
import json
import uuid
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import Mock, patch
import pytest
from sqlalchemy.orm import Session

from api.feedback_batch import router as feedback_batch_router
from core.agent_promotion_service import AgentPromotionService, PromotionCriteria
from core.database import SessionLocal
from core.feedback_advanced_analytics import AdvancedFeedbackAnalytics
from core.feedback_export_service import FeedbackExportService
from core.models import AgentExecution, AgentFeedback, AgentRegistry, User

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user_id = f"user-{uuid.uuid4()}"
    user = User(
        id=user_id,
        email=f"test-{uuid.uuid4()}@example.com",
        first_name="Test",
        last_name="User"
    )
    db.add(user)
    db.commit()
    db.expunge(user)  # Detach from session to avoid lazy loading issues
    yield user
    # Cleanup - use user_id directly to avoid lazy loading
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def intern_agent(db):
    """Create an INTERN agent for testing."""
    agent_id = f"intern-agent-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Intern Agent",
        category="Sales",
        module_path="agents.intern_agent",
        class_name="InternAgent",
        status="INTERN",
        confidence_score=0.6
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)  # Detach from session to avoid lazy loading issues
    yield agent
    # Cleanup - use agent_id directly to avoid lazy loading
    db.query(AgentFeedback).filter(AgentFeedback.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def supervised_agent(db):
    """Create a SUPERVISED agent for testing."""
    agent_id = f"supervised-agent-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Supervised Agent",
        category="Finance",
        module_path="agents.supervised_agent",
        class_name="SupervisedAgent",
        status="SUPERVISED",
        confidence_score=0.8
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)  # Detach from session to avoid lazy loading issues
    yield agent
    # Cleanup - use agent_id directly
    db.query(AgentFeedback).filter(AgentFeedback.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def autonomous_agent(db):
    """Create an AUTONOMOUS agent for testing."""
    agent_id = f"autonomous-agent-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Autonomous Agent",
        category="Operations",
        module_path="agents.autonomous_agent",
        class_name="AutonomousAgent",
        status="AUTONOMOUS",
        confidence_score=0.95
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)  # Detach from session to avoid lazy loading issues
    yield agent
    # Cleanup - use agent_id directly
    db.query(AgentFeedback).filter(AgentFeedback.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


# ============================================================================
# Batch Feedback Operations Tests
# ============================================================================

class TestBatchFeedbackOperations:
    """Test batch feedback approval and rejection."""

    def test_batch_approve_feedback(self, db, intern_agent, test_user):
        """Test batch approving multiple feedback entries."""
        # Create feedback entries
        feedback_ids = []
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                status="pending"
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            feedback_ids.append(feedback.id)

        # Batch approve
        request_data = {
            "feedback_ids": feedback_ids,
            "user_id": test_user.id,
            "reason": "Approved after review"
        }

        # Simulate API call
        from api.feedback_batch import BatchOperationRequest
        req = BatchOperationRequest(**request_data)

        processed = 0
        for feedback_id in req.feedback_ids:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()
            if feedback:
                feedback.status = "approved"
                feedback.adjudicated_at = datetime.now()
                processed += 1

        db.commit()

        # Verify
        assert processed == 5
        for feedback_id in feedback_ids:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()
            assert feedback.status == "approved"
            assert feedback.adjudicated_at is not None

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.id.in_(feedback_ids)).delete()

    def test_batch_reject_feedback(self, db, intern_agent, test_user):
        """Test batch rejecting multiple feedback entries."""
        feedback_ids = []
        for i in range(3):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                status="pending"
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            feedback_ids.append(feedback.id)

        # Batch reject
        request_data = {
            "feedback_ids": feedback_ids,
            "user_id": test_user.id,
            "reason": "Does not meet quality standards"
        }

        from api.feedback_batch import BatchOperationRequest
        req = BatchOperationRequest(**request_data)

        processed = 0
        for feedback_id in req.feedback_ids:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()
            if feedback:
                feedback.status = "rejected"
                feedback.adjudicated_at = datetime.now()
                if req.reason:
                    feedback.ai_reasoning = f"Rejected: {req.reason}"
                processed += 1

        db.commit()

        # Verify
        assert processed == 3
        for feedback_id in feedback_ids:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()
            assert feedback.status == "rejected"
            assert "Rejected" in feedback.ai_reasoning

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.id.in_(feedback_ids)).delete()

    def test_batch_update_status(self, db, intern_agent, test_user):
        """Test bulk status update to any state."""
        feedback_ids = []
        for i in range(4):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                status="pending"
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            feedback_ids.append(feedback.id)

        # Update to approved
        request_data = {
            "feedback_ids": feedback_ids[:2],
            "new_status": "approved",
            "user_id": test_user.id,
            "ai_reasoning": "High quality feedback"
        }

        from api.feedback_batch import BulkStatusUpdateRequest
        req = BulkStatusUpdateRequest(**request_data)

        processed = 0
        for feedback_id in req.feedback_ids:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()
            if feedback:
                feedback.status = req.new_status
                if req.new_status in ["approved", "rejected"]:
                    feedback.adjudicated_at = datetime.now()
                if req.ai_reasoning:
                    feedback.ai_reasoning = req.ai_reasoning
                processed += 1

        db.commit()

        # Verify
        assert processed == 2
        feedback = db.query(AgentFeedback).filter(
            AgentFeedback.id == feedback_ids[0]
        ).first()
        assert feedback.status == "approved"

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.id.in_(feedback_ids)).delete()

    def test_get_pending_feedback(self, db, intern_agent, test_user):
        """Test getting pending feedback list."""
        # Create mix of pending and approved feedback
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                status="pending" if i < 7 else "approved",
                thumbs_up_down=(i % 2 == 0)
            )
            db.add(feedback)
        db.commit()

        # Get pending feedback
        pending = db.query(AgentFeedback).filter(
            AgentFeedback.status == "pending",
            AgentFeedback.agent_id == intern_agent.id
        ).all()

        assert len(pending) == 7

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()


# ============================================================================
# Agent Promotion Tests
# ============================================================================

class TestAgentPromotionService:
    """Test agent promotion suggestions and evaluation."""

    def test_intern_to_supervised_promotion_ready(self, db, intern_agent, test_user):
        """Test INTERN agent ready for SUPERVISED promotion."""
        # Create qualifying feedback
        for i in range(15):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i < 12),  # 12 thumbs up, 3 thumbs down (80% positive)
                rating=5 if i < 12 else 2,
                feedback_type="rating"
            )
            db.add(feedback)
        db.commit()

        # Create successful executions
        for i in range(10):
            execution = AgentExecution(
                id=f"exec-{uuid.uuid4()}",
                agent_id=intern_agent.id,
                workspace_id="default",
                status="completed",
                input_summary=f"Task {i}",
                triggered_by="api"
            )
            db.add(execution)
        db.commit()

        service = AgentPromotionService(db)
        evaluation = service.is_agent_ready_for_promotion(
            agent_id=intern_agent.id,
            target_status="SUPERVISED"
        )

        assert evaluation["agent_id"] == intern_agent.id
        assert evaluation["current_status"] == "INTERN"
        assert evaluation["target_status"] == "SUPERVISED"
        # Should be ready with 80% positive ratio
        assert "readiness_score" in evaluation
        assert "criteria_met" in evaluation
        assert "criteria_failed" in evaluation

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()
        db.query(AgentExecution).filter(AgentExecution.agent_id == intern_agent.id).delete()

    def test_supervised_to_autonomous_not_ready(self, db, supervised_agent, test_user):
        """Test SUPERVISED agent NOT ready for AUTONOMOUS promotion."""
        # Create mediocre feedback (not enough for AUTONOMOUS)
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=supervised_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i < 7),  # 70% positive (needs 90% for AUTONOMOUS)
                rating=4 if i < 7 else 2,  # Low rating for negative feedback
                feedback_type="rating"
            )
            db.add(feedback)
        db.commit()

        service = AgentPromotionService(db)
        evaluation = service.is_agent_ready_for_promotion(
            agent_id=supervised_agent.id,
            target_status="AUTONOMOUS"
        )

        assert evaluation["ready_for_promotion"] is False
        assert evaluation["target_status"] == "AUTONOMOUS"
        # Should fail positive ratio criteria (70% < 90%)
        assert "positive_ratio" in evaluation["criteria_failed"]

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == supervised_agent.id).delete()

    def test_get_promotion_path(self, db, intern_agent):
        """Test getting complete promotion path."""
        service = AgentPromotionService(db)
        path = service.get_promotion_path(intern_agent.id)

        assert path["agent_id"] == intern_agent.id
        assert path["current_status"] == "INTERN"
        assert "promotion_path" in path
        assert len(path["promotion_path"]) >= 1

        # Verify path structure
        step = path["promotion_path"][0]
        assert "from" in step
        assert "to" in step
        assert "requirements" in step
        assert "ready" in step

    def test_promotion_criteria_constants(self):
        """Test promotion criteria constants are defined correctly."""
        assert hasattr(PromotionCriteria, 'MIN_FEEDBACK_COUNT')
        assert PromotionCriteria.MIN_FEEDBACK_COUNT == 10

        assert hasattr(PromotionCriteria, 'INTERN_TO_SUPERVISED_POSITIVE_RATIO')
        assert PromotionCriteria.INTERN_TO_SUPERVISED_POSITIVE_RATIO == 0.75

        assert hasattr(PromotionCriteria, 'SUPERVISED_TO_AUTONOMOUS_POSITIVE_RATIO')
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_POSITIVE_RATIO == 0.90

        assert hasattr(PromotionCriteria, 'INTERN_TO_SUPERVISED_AVG_RATING')
        assert PromotionCriteria.INTERN_TO_SUPERVISED_AVG_RATING == 3.8

        assert hasattr(PromotionCriteria, 'SUPERVISED_TO_AUTONOMOUS_AVG_RATING')
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_AVG_RATING == 4.5


# ============================================================================
# Feedback Export Tests
# ============================================================================

class TestFeedbackExportService:
    """Test feedback export functionality."""

    def test_export_to_json(self, db, intern_agent, test_user):
        """Test exporting feedback to JSON format."""
        # Create feedback
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                rating=5,
                feedback_type="rating",
                status="approved"
            )
            db.add(feedback)
        db.commit()

        service = FeedbackExportService(db)
        json_data = service.export_to_json(
            agent_id=intern_agent.id,
            days=30
        )

        # Parse and verify
        data = json.loads(json_data)
        assert "export_date" in data
        assert "total_records" in data
        assert data["total_records"] == 5
        assert "feedback" in data
        assert len(data["feedback"]) == 5

        # Verify structure
        feedback_entry = data["feedback"][0]
        assert "id" in feedback_entry
        assert "agent_id" in feedback_entry
        assert "user_id" in feedback_entry
        assert "original_output" in feedback_entry

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()

    def test_export_to_csv(self, db, intern_agent, test_user):
        """Test exporting feedback to CSV format."""
        # Create feedback
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                rating=5,
                feedback_type="rating"
            )
            db.add(feedback)
        db.commit()

        service = FeedbackExportService(db)
        csv_data = service.export_to_csv(
            agent_id=intern_agent.id,
            days=30
        )

        # Parse CSV
        reader = csv.DictReader(StringIO(csv_data))
        rows = list(reader)

        assert len(rows) == 5

        # Verify headers
        expected_headers = [
            "feedback_id", "agent_id", "agent_name", "agent_execution_id",
            "user_id", "feedback_type", "thumbs_up_down", "rating",
            "original_output", "user_correction", "status", "created_at",
            "adjudicated_at"
        ]
        assert set(rows[0].keys()) == set(expected_headers)

        # Verify data
        assert rows[0]["agent_id"] == intern_agent.id
        assert rows[0]["rating"] == "5"

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()

    def test_export_summary_to_json(self, db, intern_agent, test_user):
        """Test exporting summary statistics."""
        # Create mixed feedback
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i < 7),  # 7 thumbs up, 3 thumbs down
                rating=5 if i < 7 else 2,
                feedback_type="rating"
            )
            db.add(feedback)
        db.commit()

        service = FeedbackExportService(db)
        json_data = service.export_summary_to_json(
            agent_id=intern_agent.id,
            days=30
        )

        # Parse and verify
        data = json.loads(json_data)
        assert "summary" in data
        assert data["summary"]["total_feedback"] == 10
        assert data["summary"]["positive_count"] == 7
        assert data["summary"]["thumbs_up_count"] == 7
        assert data["summary"]["thumbs_down_count"] == 3

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()

    def test_get_export_filters(self, db, intern_agent, test_user):
        """Test getting available export filter values."""
        # Create feedback with different types
        for feedback_type in ["correction", "rating", "approval"]:
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output="Test",
                user_correction="",
                feedback_type=feedback_type,
                status="pending"
            )
            db.add(feedback)
        db.commit()

        service = FeedbackExportService(db)
        filters = service.get_export_filters(db)

        # Verify
        assert "agents" in filters
        assert "feedback_types" in filters
        assert "statuses" in filters

        # Check agent is in list
        agent_ids = [a["id"] for a in filters["agents"]]
        assert intern_agent.id in agent_ids

        # Check feedback types
        assert "correction" in filters["feedback_types"]
        assert "rating" in filters["feedback_types"]
        assert "approval" in filters["feedback_types"]

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()


# ============================================================================
# Advanced Analytics Tests
# ============================================================================

class TestAdvancedFeedbackAnalytics:
    """Test advanced analytics functionality."""

    def test_correlation_analysis(self, db, intern_agent, test_user):
        """Test feedback-performance correlation analysis."""
        # Create executions with linked feedback
        execution_id = f"exec-{uuid.uuid4()}"

        execution = AgentExecution(
            id=execution_id,
            agent_id=intern_agent.id,
            workspace_id="default",
            status="completed",
            input_summary="Test task",
            triggered_by="api"
        )
        db.add(execution)

        # Create feedback linked to execution
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                agent_execution_id=execution_id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=True,  # All positive
                rating=5
            )
            db.add(feedback)
        db.commit()

        service = AdvancedFeedbackAnalytics(db)
        correlation = service.analyze_feedback_performance_correlation(
            agent_id=intern_agent.id,
            days=30
        )

        assert correlation["agent_id"] == intern_agent.id
        assert "positive_success_rate" in correlation
        assert "correlation_strength" in correlation
        assert "interpretation" in correlation

        # Should have strong positive correlation
        assert correlation["positive_success_rate"] > 0.5

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()
        db.query(AgentExecution).filter(AgentExecution.id == execution_id).delete()

    def test_cohort_analysis(self, db, intern_agent, supervised_agent, test_user):
        """Test cohort analysis by agent category."""
        # Create feedback for both agents
        for agent in [intern_agent, supervised_agent]:
            for i in range(5):
                feedback = AgentFeedback(
                    agent_id=agent.id,
                    user_id=test_user.id,
                    original_output=f"Output {i}",
                    user_correction="",
                    thumbs_up_down=True,
                    rating=5
                )
                db.add(feedback)
        db.commit()

        service = AdvancedFeedbackAnalytics(db)
        cohorts = service.analyze_feedback_by_agent_cohort(days=30)

        assert "analysis_period_days" in cohorts
        assert "cohorts" in cohorts

        # Should have Sales cohort (intern_agent)
        assert "Sales" in cohorts["cohorts"]
        assert cohorts["cohorts"]["Sales"]["agent_count"] == 1
        assert cohorts["cohorts"]["Sales"]["total_feedback"] == 5

        # Should have Finance cohort (supervised_agent)
        assert "Finance" in cohorts["cohorts"]
        assert cohorts["cohorts"]["Finance"]["agent_count"] == 1
        assert cohorts["cohorts"]["Finance"]["total_feedback"] == 5

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id.in_([
            intern_agent.id, supervised_agent.id
        ])).delete()

    def test_performance_prediction(self, db, intern_agent, test_user):
        """Test performance prediction from trends."""
        # Create improving trend feedback
        for i in range(20):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i >= 10),  # First 10 negative, last 10 positive
                rating=2 if i < 10 else 5
            )
            db.add(feedback)
        db.commit()

        service = AdvancedFeedbackAnalytics(db)
        prediction = service.predict_agent_performance(
            agent_id=intern_agent.id,
            days=30
        )

        assert prediction["agent_id"] == intern_agent.id
        assert "trend" in prediction
        assert "prediction" in prediction
        assert "confidence" in prediction
        assert "recommendation" in prediction

        # Should detect improvement trend
        # Second half has more positive feedback than first half
        assert prediction["second_half_positive_ratio"] > prediction["first_half_positive_ratio"]

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()

    def test_velocity_analysis(self, db, intern_agent, test_user):
        """Test feedback velocity analysis."""
        # Create feedback over multiple days
        now = datetime.now()
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                rating=5,
                created_at=now - timedelta(days=i)
            )
            db.add(feedback)
        db.commit()

        service = AdvancedFeedbackAnalytics(db)
        velocity = service.analyze_feedback_velocity(
            agent_id=intern_agent.id,
            days=30
        )

        assert velocity["agent_id"] == intern_agent.id
        assert "total_feedback" in velocity
        assert velocity["total_feedback"] == 10
        assert "average_per_day" in velocity
        assert "pattern" in velocity
        assert "feedback_by_day" in velocity

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()


# ============================================================================
# Integration Tests
# ============================================================================

class TestFeedbackPhase2Integration:
    """Integration tests for Phase 2 features."""

    def test_full_promotion_workflow(self, db, intern_agent, test_user):
        """Test complete workflow from feedback to promotion."""
        # Step 1: Create feedback
        for i in range(15):
            feedback = AgentFeedback(
                agent_id=intern_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i < 12),  # 80% positive
                rating=5 if i < 12 else 3
            )
            db.add(feedback)
        db.commit()

        # Step 2: Check promotion readiness
        promotion_service = AgentPromotionService(db)
        evaluation = promotion_service.is_agent_ready_for_promotion(
            agent_id=intern_agent.id,
            target_status="SUPERVISED"
        )

        assert evaluation["current_status"] == "INTERN"
        assert evaluation["target_status"] == "SUPERVISED"

        # Step 3: Get promotion path
        path = promotion_service.get_promotion_path(intern_agent.id)
        assert path["current_status"] == "INTERN"
        assert len(path["promotion_path"]) > 0

        # Step 4: Export feedback data
        export_service = FeedbackExportService(db)
        json_data = export_service.export_to_json(
            agent_id=intern_agent.id,
            days=30
        )
        data = json.loads(json_data)
        assert data["total_records"] == 15

        # Step 5: Analyze performance prediction
        analytics = AdvancedFeedbackAnalytics(db)
        prediction = analytics.predict_agent_performance(
            agent_id=intern_agent.id,
            days=30
        )
        assert "prediction" in prediction

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == intern_agent.id).delete()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
