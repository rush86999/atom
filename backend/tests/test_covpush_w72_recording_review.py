# -*- coding: utf-8 -*-
"""Coverage wave 72 — core/recording_review_service (in-memory SQLite,
fully mocked governance/world-model deps, zero LLM spend, no network).

Closes the remaining gaps: create_review error paths (missing recording,
inner-service raise re-raised), auto-review disabled/not-found/flagged/
low-confidence/exception branches, _analyze_recording_events error/high-
intervention/approved/rejected outcomes incl. feedback + lessons branches,
_analyze_recording_for_review standard-approval / pending / 3+-issue
adjustments, confidence-update early-return + governance exception tolerance,
audit exception tolerance, get_review_metrics empty-result shape, and the
module-level get_recording_review_service helper.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentRegistry,
    CanvasRecording,
    CanvasRecordingReview,
    User,
)
from core.recording_review_service import (
    AUTO_REVIEW_ENABLED,
    RecordingReviewService,
    get_recording_review_service,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1"):
    user = User(id=user_id, email=f"{user_id}@test.com", role="member",
                first_name="T", last_name="U", status="active")
    db.add(user)
    db.commit()
    return user


def _make_agent(db, agent_id="agent-1", status="autonomous"):
    agent = AgentRegistry(id=agent_id, name=agent_id, workspace_id="ws-1",
                          tenant_id="default", category="Test",
                          module_path="test", class_name="Test", status=status)
    db.add(agent)
    db.commit()
    return agent


def _make_recording(db, recording_id="rec-1", agent_id="agent-1", user_id="user-1",
                    events=None, canvas_id="canvas-1", reason="autonomous_action",
                    status="completed", duration_seconds=120.0, metadata_=None,
                    flagged=False):
    recording = CanvasRecording(
        id=recording_id,
        recording_id=recording_id,
        tenant_id="default",
        agent_id=agent_id,
        user_id=user_id,
        canvas_id=canvas_id,
        session_id="sess-1",
        reason=reason,
        status=status,
        tags=["autonomous"],
        events=events if events is not None else [],
        recording_metadata=metadata_ if metadata_ is not None else {"agent_name": "Test Agent"},
        duration_seconds=duration_seconds,
        flagged_for_review=flagged,
    )
    db.add(recording)
    db.commit()
    return recording


def _service(db, **kwargs):
    return RecordingReviewService(db, **kwargs)


def _patch_governance(mock=None):
    return patch.object(
        __import__("core.service_factory", fromlist=["ServiceFactory"]).ServiceFactory,
        "get_governance_service",
        return_value=mock if mock is not None else AsyncMock(),
    )


# ============================================================================
# create_review
# ============================================================================

def test_create_review_missing_recording_raises(db):
    svc = _service(db)
    with pytest.raises(ValueError, match="not found"):
        _ = asyncio.run(
            svc.create_review("nope", "user-1", "approved")
        )


def test_create_review_inner_error_reraises(db):
    """create_review re-raises when the analysis step blows up."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with patch.object(RecordingReviewService, "_analyze_recording_for_review",
                      AsyncMock(side_effect=RuntimeError("analysis failed"))):
        with pytest.raises(RuntimeError, match="analysis failed"):
            _ = asyncio.run(
                svc.create_review("rec-1", "user-1", "approved")
            )


def test_create_review_standard_approval_low_rating(db):
    """approved with rating < 4 -> +0.02 delta, medium training value."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance() as gov_factory:
        review_id = asyncio.run(
            svc.create_review("rec-1", "user-1", "approved", overall_rating=3,
                              feedback="ok", positive_patterns=["p1"])
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.confidence_delta == pytest.approx(0.02)
    assert review.training_value == "medium"
    assert review.promoted is False
    assert review.demoted is False
    assert gov_factory.return_value.record_outcome.await_count == 1


def test_create_review_pending_status_zero_delta(db):
    """unknown status -> zero confidence impact (early return in update path)."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance() as gov_factory:
        review_id = asyncio.run(
            svc.create_review("rec-1", "user-1", "pending")
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.confidence_delta == 0.0
    assert review.training_value == "low"
    assert gov_factory.return_value.record_outcome.await_count == 0
    # audit row still created for a recording with a canvas_id
    from core.models import CanvasAudit
    audits = db.query(CanvasAudit).filter(
        CanvasAudit.action_type == "review_pending"
    ).all()
    assert len(audits) == 1


def test_create_review_approved_high_rating_with_issues(db):
    """approved + rating >= 4 + 3+ issues -> +0.03 delta, high training,
    world model update (approved + has_useful_patterns)."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance() as gov_factory, \
         patch("core.agent_world_model.WorldModelService") as wm_cls:
        wm_cls.return_value.record_experience = AsyncMock()
        review_id = asyncio.run(
            svc.create_review(
                "rec-1", "user-1", "approved", overall_rating=5,
                identified_issues=["i1", "i2", "i3"], lessons_learned="lesson"
            )
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.confidence_delta == pytest.approx(0.03)  # 0.05 - 0.02 (3 issues)
    assert review.training_value == "high"
    assert review.promoted is False  # 0.03 < 0.05
    assert review.used_for_training is True
    assert review.world_model_updated is True
    assert wm_cls.return_value.record_experience.await_count == 1
    assert gov_factory.return_value.record_outcome.await_count == 1
    assert review.governance_notes.startswith("Confidence increased")


def test_create_review_rejected_status(db):
    """rejected -> -0.10 delta, high training, demoted, world model updated."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance() as gov_factory, \
         patch("core.agent_world_model.WorldModelService") as wm_cls:
        wm_cls.return_value.record_experience = AsyncMock()
        review_id = asyncio.run(
            svc.create_review("rec-1", "user-1", "rejected", overall_rating=1)
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.confidence_delta == -0.10
    assert review.training_value == "high"
    assert review.demoted is True
    # rejected recordings are marked high training value + useful patterns,
    # so they MUST reach the world model too
    assert review.used_for_training is True
    assert review.world_model_updated is True


def test_create_review_no_feedback_updates_world_model(db):
    """BUG REGRESSION: approved reviews without feedback/lessons made
    AgentExperience validation fail (learnings=None), silently skipping the
    world-model update. The fallback string must be used instead."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance(), \
         patch("core.agent_world_model.WorldModelService") as wm_cls:
        wm_cls.return_value.record_experience = AsyncMock()
        review_id = asyncio.run(
            svc.create_review("rec-1", "user-1", "approved", overall_rating=4)
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.used_for_training is True
    assert review.world_model_updated is True
    assert wm_cls.return_value.record_experience.await_count == 1
    experience = wm_cls.return_value.record_experience.call_args.args[0]
    assert experience.learnings == "No specific learnings recorded"


def test_create_review_world_model_exception_tolerated(db):
    """world-model failure must not break review creation."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance(), \
         patch("core.agent_world_model.WorldModelService") as wm_cls:
        wm_cls.return_value.record_experience = AsyncMock(
            side_effect=RuntimeError("wm down")
        )
        review_id = asyncio.run(
            svc.create_review("rec-1", "user-1", "approved", overall_rating=4)
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.confidence_delta == pytest.approx(0.05)
    assert review.used_for_training is False  # never reached the commit


def test_create_review_governance_exception_tolerated(db):
    """governance failure must not break review creation."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    gov = AsyncMock()
    gov.record_outcome = AsyncMock(side_effect=RuntimeError("gov down"))
    with _patch_governance(gov), \
         patch("core.agent_world_model.WorldModelService") as wm_cls:
        wm_cls.return_value.record_experience = AsyncMock()
        review_id = asyncio.run(
            svc.create_review("rec-1", "user-1", "approved", overall_rating=4)
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.confidence_delta == pytest.approx(0.05)


def test_create_review_audit_exception_reraises(db):
    """an exception escaping an inner step is re-raised by create_review."""
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance(), \
         patch.object(RecordingReviewService, "_create_review_audit",
                      AsyncMock(side_effect=RuntimeError("audit down"))):
        with pytest.raises(RuntimeError, match="audit down"):
            asyncio.run(
                svc.create_review("rec-1", "user-1", "needs_changes")
            )


def test_create_review_single_issue_small_positive_adjustment(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance():
        review_id = asyncio.run(
            svc.create_review("rec-1", "user-1", "approved", overall_rating=4,
                              identified_issues=["only-one"])
        )
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == review_id
    ).one()
    assert review.confidence_delta == pytest.approx(0.06)  # 0.05 + 0.01 single issue


# ============================================================================
# auto_review_recording
# ============================================================================

def test_auto_review_disabled(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with patch("core.recording_review_service.AUTO_REVIEW_ENABLED", False):
        result = asyncio.run(
            svc.auto_review_recording("rec-1")
        )
    assert result is None


def test_auto_review_recording_not_found(db):
    svc = _service(db)
    result = asyncio.run(
        svc.auto_review_recording("missing")
    )
    assert result is None


def test_auto_review_flagged_skipped(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, flagged=True)
    svc = _service(db)
    with patch.object(RecordingReviewService, "_analyze_recording_events",
                      AsyncMock(return_value={"review_status": "approved"})):
        result = asyncio.run(
            svc.auto_review_recording("rec-1")
        )
    assert result is None


def test_auto_review_low_confidence_skipped(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with patch.object(RecordingReviewService, "_analyze_recording_events",
                      AsyncMock(return_value={
                          "review_status": "approved",
                          "overall_rating": 4,
                          "confidence": 0.5,  # below 0.7 threshold
                      })):
        result = asyncio.run(
            svc.auto_review_recording("rec-1")
        )
    assert result is None


def test_auto_review_exception_returns_none(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with patch.object(RecordingReviewService, "_analyze_recording_events",
                      AsyncMock(side_effect=RuntimeError("analysis down"))):
        result = asyncio.run(
            svc.auto_review_recording("rec-1")
        )
    assert result is None


def test_auto_review_success_path(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_governance(), \
         patch.object(RecordingReviewService, "_analyze_recording_events",
                      AsyncMock(return_value={
                          "review_status": "approved",
                          "overall_rating": 4,
                          "performance_rating": 4,
                          "safety_rating": 5,
                          "confidence": 0.9,
                          "feedback": "good run",
                          "issues": [],
                          "patterns": ["error_free_execution"],
                          "lessons": "lesson",
                      })), \
         patch("core.agent_world_model.WorldModelService") as wm_cls, \
         patch.object(RecordingReviewService, "_create_review_audit", AsyncMock()):
        wm_cls.return_value.record_experience = AsyncMock()
        result = asyncio.run(
            svc.auto_review_recording("rec-1")
        )
    assert result is not None
    review = db.query(CanvasRecordingReview).filter(
        CanvasRecordingReview.id == result
    ).one()
    assert review.auto_reviewed is True
    assert review.auto_review_confidence == 0.9
    assert review.reviewed_by is None


# ============================================================================
# _analyze_recording_events
# ============================================================================

def test_analyze_events_errors_and_high_intervention():
    svc = _service(MagicMock())
    recording = SimpleNamespace(events=[
        {"event_type": "error", "data": {}},
        {"event_type": "error", "data": {}},
        {"event_type": "user_input", "data": {}},
        {"event_type": "user_input", "data": {}},
        {"event_type": "user_input", "data": {}},
        {"event_type": "other", "data": {}},
    ])
    analysis = asyncio.run(
        svc._analyze_recording_events(recording)
    )
    assert analysis["review_status"] == "rejected"  # 3+ issues
    assert "errors_occurred" in analysis["issues"][0]
    assert any("high_intervention" in i for i in analysis["issues"])
    assert "low_success_rate" in analysis["issues"]
    assert analysis["overall_rating"] == 1
    assert analysis["safety_rating"] == 2
    assert "Recording shows significant issues" in analysis["feedback"]
    assert "need for improved autonomy" in analysis["lessons"]


def test_analyze_events_clean_run_approved():
    svc = _service(MagicMock())
    recording = SimpleNamespace(events=[
        {"event_type": "operation_complete", "data": {}},
        {"event_type": "operation_complete", "data": {}},
        {"event_type": "operation_complete", "data": {}},
        {"event_type": "operation_complete", "data": {}},
        {"event_type": "other", "data": {}},
    ])
    analysis = asyncio.run(
        svc._analyze_recording_events(recording)
    )
    assert analysis["review_status"] == "approved"
    assert analysis["overall_rating"] == 5
    assert "error_free_execution" in analysis["patterns"]
    assert "high_success_rate" in analysis["patterns"]
    assert "fully_autonomous" in analysis["patterns"]
    assert "Recording reviewed successfully" in analysis["feedback"]
    assert "operated autonomously" in analysis["lessons"]


def test_analyze_events_no_events():
    svc = _service(MagicMock())
    recording = SimpleNamespace(events=None)
    analysis = asyncio.run(
        svc._analyze_recording_events(recording)
    )
    assert analysis["review_status"] == "needs_changes"
    assert analysis["overall_rating"] == 4  # error-free +1, no success-rate pattern


# ============================================================================
# _create_review_audit exception + helper
# ============================================================================

def test_create_review_audit_exception(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    review = CanvasRecordingReview(
        id="rev-x", recording_id="rec-1", agent_id="agent-1", user_id="user-1",
        tenant_id="default", review_status="approved",
    )
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.first.return_value = MagicMock(
        canvas_id="canvas-1"
    )
    svc.db.commit.side_effect = RuntimeError("db down")
    asyncio.run(
        svc._create_review_audit(review, {"confidence_delta": 0.05, "training_value": "high"})
    )


def test_get_review_metrics_empty(db):
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    metrics = asyncio.run(
        svc.get_review_metrics("agent-1")
    )
    assert metrics == {
        "total_reviews": 0,
        "approval_rate": 0.0,
        "average_rating": 0.0,
        "confidence_impact": 0.0,
        "training_recordings": 0,
        "common_issues": [],
        "strengths": [],
    }


def test_get_review_metrics_with_reviews(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    now = datetime.now(timezone.utc)
    db.add_all([
        CanvasRecordingReview(
            id="r1", recording_id="rec-1", agent_id="agent-1", user_id="user-1",
            tenant_id="default", review_status="approved", overall_rating=5,
            confidence_delta=0.05, used_for_training=True,
            identified_issues=["slow"], positive_patterns=["fast"],
            reviewed_at=now - timedelta(days=1),
        ),
        CanvasRecordingReview(
            id="r2", recording_id="rec-1", agent_id="agent-1", user_id="user-1",
            tenant_id="default", review_status="rejected", overall_rating=None,
            confidence_delta=-0.10, used_for_training=False,
            identified_issues=["slow"], positive_patterns=[],
            reviewed_at=now - timedelta(days=2),
        ),
        CanvasRecordingReview(
            id="r3", recording_id="rec-1", agent_id="agent-1", user_id="user-1",
            tenant_id="default", review_status="approved", overall_rating=4,
            confidence_delta=0.02, used_for_training=True,
            identified_issues=None, positive_patterns=None,
            reviewed_at=now - timedelta(days=100),  # outside window
        ),
    ])
    db.commit()
    metrics = asyncio.run(
        svc.get_review_metrics("agent-1", days=30)
    )
    assert metrics["total_reviews"] == 2
    assert metrics["approval_rate"] == 0.5
    assert metrics["average_rating"] == 5.0
    assert metrics["confidence_impact"] == -0.05
    assert metrics["training_recordings"] == 1
    assert metrics["common_issues"] == ["slow"]
    assert metrics["strengths"] == ["fast"]


def test_get_recording_review_service_helper(db):
    svc = get_recording_review_service(db, tenant_id="custom")
    assert isinstance(svc, RecordingReviewService)
    assert svc.tenant_id == "custom"


def test_module_flags_present():
    assert isinstance(AUTO_REVIEW_ENABLED, bool)
