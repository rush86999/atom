# -*- coding: utf-8 -*-
"""Coverage wave 72 — core/canvas_recording_service (in-memory SQLite,
websocket broadcast mocked, zero LLM spend, no network).

Closes the remaining gaps: governance-property lazy fallback, feature-flag
disabled short-circuits (start/record/stop/auto-record), exception tolerance
paths (start/record/stop/get/list/auto/flag/audit/auto-review), record_event
inactive-recording skip, stop_recording missing/naive-started_at branches,
list_recordings agent filter, _generate_summary event-type branches, and the
module-level get_canvas_recording_service helper.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentRegistry, CanvasAudit, CanvasRecording, User
from core.canvas_recording_service import (
    CANVAS_RECORDING_ENABLED,
    CanvasRecordingService,
    get_canvas_recording_service,
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
    agent = AgentRegistry(id=agent_id, name="Test Agent", workspace_id="ws-1",
                          tenant_id="default", category="Test",
                          module_path="test", class_name="Test", status=status)
    db.add(agent)
    db.commit()
    return agent


def _make_recording(db, recording_id="rec-1", status="recording",
                    started_at=None, events=None, user_id="user-1",
                    agent_id="agent-1", canvas_id="canvas-1", tags=None):
    recording = CanvasRecording(
        id=recording_id,
        recording_id=recording_id,
        tenant_id="default",
        agent_id=agent_id,
        user_id=user_id,
        canvas_id=canvas_id,
        session_id="sess-1",
        reason="autonomous_action",
        status=status,
        tags=tags if tags is not None else ["autonomous"],
        events=events if events is not None else [],
        recording_metadata={"agent_name": "Test Agent"},
        started_at=started_at if started_at is not None else datetime.now(timezone.utc),
    )
    db.add(recording)
    db.commit()
    return recording


def _service(db):
    with patch.object(
        __import__("core.service_factory", fromlist=["ServiceFactory"]).ServiceFactory,
        "get_governance_service",
        return_value=MagicMock(),
    ):
        return CanvasRecordingService(db)


@pytest.fixture()
def ws_broadcast():
    with patch("core.canvas_recording_service.ws_manager.broadcast",
               new_callable=AsyncMock) as mock:
        yield mock


def _patch_disabled():
    return patch("core.canvas_recording_service.CANVAS_RECORDING_ENABLED", False)


# ============================================================================
# start_recording
# ============================================================================

def test_start_recording_autonomous_agent(db, ws_broadcast):
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    recording_id = asyncio.run(svc.start_recording("user-1", "agent-1", "canvas-1",
                                                   "autonomous_action", session_id="s1"))
    assert isinstance(recording_id, str)
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == recording_id
    ).one()
    assert recording.status == "recording"
    assert recording.recording_metadata["agent_name"] == "Test Agent"
    assert recording.tags == []
    ws_broadcast.assert_awaited_once()
    audit = db.query(CanvasAudit).filter(
        CanvasAudit.action_type == "start_recording"
    ).one()
    assert audit.canvas_id == "canvas-1"
    assert audit.session_id == "s1"


def test_start_recording_non_autonomous_agent(db, ws_broadcast):
    _make_user(db)
    _make_agent(db, status="supervised")
    svc = _service(db)
    recording_id = asyncio.run(svc.start_recording("user-1", "agent-1", None, "manual"))
    assert isinstance(recording_id, str)


def test_start_recording_missing_agent(db, ws_broadcast):
    _make_user(db)
    svc = _service(db)
    recording_id = asyncio.run(svc.start_recording("user-1", "ghost", "canvas-9", "manual"))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == recording_id
    ).one()
    assert recording.recording_metadata["agent_name"] == "Unknown"
    assert recording.recording_metadata["agent_maturity"] is None


def test_start_recording_disabled(db):
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    with _patch_disabled():
        recording_id = asyncio.run(svc.start_recording("user-1", "agent-1", None, "manual"))
    assert isinstance(recording_id, str)
    assert db.query(CanvasRecording).count() == 0


def test_start_recording_exception_returns_uuid(db):
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
    recording_id = asyncio.run(svc.start_recording("user-1", "agent-1", None, "manual"))
    assert isinstance(recording_id, str)


def test_governance_property_lazy_fallback(db):
    """When __init__ leaves _governance unset (or a caller clears it), the
    property re-fetches from ServiceFactory."""
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    svc._governance = None
    with patch.object(
        __import__("core.service_factory", fromlist=["ServiceFactory"]).ServiceFactory,
        "get_governance_service",
        return_value=MagicMock(),
    ) as factory:
        gov = svc.governance
    assert gov is not None
    factory.assert_called_once()


# ============================================================================
# record_event
# ============================================================================

def test_record_event_success(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, events=[])
    svc = _service(db)
    asyncio.run(svc.record_event("rec-1", "operation_start", {"op": "x"}))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert len(recording.events) == 1
    assert recording.events[0]["event_type"] == "operation_start"
    assert recording.events[0]["data"] == {"op": "x"}
    assert recording.events[0]["timestamp"]


def test_record_event_inactive_or_missing(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, status="completed")  # not recording -> skipped
    svc = _service(db)
    asyncio.run(svc.record_event("rec-1", "operation_start", {}))
    asyncio.run(svc.record_event("missing", "operation_start", {}))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.events == []


def test_record_event_disabled(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, events=[])
    svc = _service(db)
    with _patch_disabled():
        asyncio.run(svc.record_event("rec-1", "operation_start", {}))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.events == []


def test_record_event_exception_tolerated(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
    asyncio.run(svc.record_event("rec-1", "operation_start", {}))  # must not raise


# ============================================================================
# stop_recording
# ============================================================================

def test_stop_recording_success(db, ws_broadcast):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, events=[
        {"event_type": "operation_complete"},
        {"event_type": "error"},
        {"event_type": "other"},
    ])
    svc = _service(db)
    with patch.object(svc, "_trigger_auto_review", AsyncMock()) as trigger:
        asyncio.run(svc.stop_recording("rec-1", status="completed"))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.status == "completed"
    assert recording.stopped_at is not None
    assert recording.duration_seconds is not None and recording.duration_seconds >= 0
    assert recording.event_count == 3
    assert recording.summary == "3 events recorded, operation completed, errors occurred"
    assert recording.expires_at is not None
    ws_broadcast.assert_awaited_once()
    trigger.assert_awaited_once_with("rec-1")
    assert db.query(CanvasAudit).filter(
        CanvasAudit.action_type == "stop_recording"
    ).count() == 1


def test_stop_recording_naive_started_at(db, ws_broadcast):
    _make_user(db)
    _make_agent(db)
    naive = datetime.utcnow() - timedelta(minutes=5)  # tz-less
    _make_recording(db, started_at=naive)
    svc = _service(db)
    with patch.object(svc, "_trigger_auto_review", AsyncMock()):
        asyncio.run(svc.stop_recording("rec-1"))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.status == "completed"
    assert recording.duration_seconds >= 299.0


def test_stop_recording_missing(db):
    svc = _service(db)
    asyncio.run(svc.stop_recording("missing"))  # warning, no raise


def test_stop_recording_disabled(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with _patch_disabled():
        asyncio.run(svc.stop_recording("rec-1"))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.status == "recording"


def test_stop_recording_exception_tolerated(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.first.return_value = MagicMock(
        started_at=datetime.now(timezone.utc)
    )
    svc.db.commit.side_effect = RuntimeError("db down")
    asyncio.run(svc.stop_recording("rec-1"))  # must not raise


def test_stop_recording_explicit_summary(db, ws_broadcast):
    _make_user(db)
    _make_agent(db)
    _make_recording(db)
    svc = _service(db)
    with patch.object(svc, "_trigger_auto_review", AsyncMock()):
        asyncio.run(svc.stop_recording("rec-1", summary="custom summary"))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.summary == "custom summary"


# ============================================================================
# get_recording / list_recordings
# ============================================================================

def test_get_recording_found(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, status="completed", events=[{"event_type": "error"}])
    svc = _service(db)
    result = asyncio.run(svc.get_recording("rec-1"))
    assert result["recording_id"] == "rec-1"
    assert result["agent_id"] == "agent-1"
    assert result["events"] == [{"event_type": "error"}]
    assert result["stopped_at"] is None
    assert result["expires_at"] is None


def test_get_recording_missing(db):
    svc = _service(db)
    assert asyncio.run(svc.get_recording("missing")) is None


def test_get_recording_exception(db):
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
    assert asyncio.run(svc.get_recording("rec-1")) is None


def test_list_recordings_with_and_without_agent_filter(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, recording_id="rec-1")
    _make_recording(db, recording_id="rec-2", agent_id="agent-1")
    _make_recording(db, recording_id="rec-3", user_id="user-1", agent_id="other-agent")
    svc = _service(db)
    all_recordings = asyncio.run(svc.list_recordings("user-1"))
    assert {r["recording_id"] for r in all_recordings} == {"rec-1", "rec-2", "rec-3"}
    filtered = asyncio.run(svc.list_recordings("user-1", agent_id="agent-1"))
    assert {r["recording_id"] for r in filtered} == {"rec-1", "rec-2"}
    assert asyncio.run(svc.list_recordings("nobody")) == []


def test_list_recordings_exception(db):
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.order_by.return_value.limit.side_effect = \
        RuntimeError("db down")
    assert asyncio.run(svc.list_recordings("user-1")) == []


# ============================================================================
# auto_record_autonomous_action
# ============================================================================

def test_auto_record_autonomous_action_start_new(db, ws_broadcast):
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    recording_id = asyncio.run(svc.auto_record_autonomous_action(
        "agent-1", "user-1", "send_email", {"session_id": "s9", "canvas_id": "c9"}
    ))
    assert recording_id is not None
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == recording_id
    ).one()
    assert recording.reason == "autonomous_action"
    assert "send_email" in recording.tags
    assert recording.session_id == "s9"


def test_auto_record_autonomous_action_existing(db, ws_broadcast):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, recording_id="existing")
    svc = _service(db)
    recording_id = asyncio.run(svc.auto_record_autonomous_action(
        "agent-1", "user-1", "send_email", {"session_id": "sess-1"}
    ))
    assert recording_id == "existing"
    ws_broadcast.assert_not_awaited()


def test_auto_record_non_autonomous_agent(db):
    _make_user(db)
    _make_agent(db, status="supervised")
    svc = _service(db)
    assert asyncio.run(svc.auto_record_autonomous_action(
        "agent-1", "user-1", "send_email", {}
    )) is None


def test_auto_record_missing_agent(db):
    _make_user(db)
    svc = _service(db)
    assert asyncio.run(svc.auto_record_autonomous_action(
        "ghost", "user-1", "send_email", {}
    )) is None


def test_auto_record_disabled(db):
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    with _patch_disabled():
        assert asyncio.run(svc.auto_record_autonomous_action(
            "agent-1", "user-1", "send_email", {}
        )) is None


def test_auto_record_exception(db):
    _make_user(db)
    _make_agent(db)
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
    assert asyncio.run(svc.auto_record_autonomous_action(
        "agent-1", "user-1", "send_email", {}
    )) is None


# ============================================================================
# flag_for_review / _generate_summary / _create_audit / _trigger_auto_review
# ============================================================================

def test_flag_for_review_adds_tag(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, tags=["autonomous"])
    svc = _service(db)
    asyncio.run(svc.flag_for_review("rec-1", "suspicious", "user-1"))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.flagged_for_review is True
    assert recording.flag_reason == "suspicious"
    assert recording.flagged_by == "user-1"
    assert recording.flagged_at is not None
    assert "flagged_review" in recording.tags


def test_flag_for_review_existing_tag(db):
    _make_user(db)
    _make_agent(db)
    _make_recording(db, tags=["flagged_review", "autonomous"])
    svc = _service(db)
    asyncio.run(svc.flag_for_review("rec-1", "suspicious", "user-1"))
    recording = db.query(CanvasRecording).filter(
        CanvasRecording.recording_id == "rec-1"
    ).one()
    assert recording.tags == ["flagged_review", "autonomous"]  # no duplicate


def test_flag_for_review_missing_noop(db):
    svc = _service(db)
    asyncio.run(svc.flag_for_review("missing", "suspicious", "user-1"))  # no raise


def test_flag_for_review_exception(db):
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.query.return_value.filter.return_value.first.return_value = MagicMock(
        tags=None
    )
    svc.db.commit.side_effect = RuntimeError("db down")
    asyncio.run(svc.flag_for_review("rec-1", "suspicious", "user-1"))  # no raise


def test_generate_summary_branches(db):
    svc = _service(db)
    rec = MagicMock()
    rec.events = [{"event_type": "operation_complete"}, {"event_type": "other"}]
    assert svc._generate_summary(rec) == "2 events recorded, operation completed"
    rec.events = [{"event_type": "error"}]
    assert svc._generate_summary(rec) == "1 events recorded, errors occurred"
    rec.events = [{"event_type": "other"}]
    assert svc._generate_summary(rec) == "1 events recorded"


def test_create_audit_exception(db):
    svc = _service(db)
    svc.db = MagicMock()
    svc.db.commit.side_effect = RuntimeError("db down")
    asyncio.run(svc._create_audit("agent-1", "user-1", "rec-1", "start_recording"))


def test_trigger_auto_review_returns_id(db):
    svc = _service(db)
    with patch("core.recording_review_service.RecordingReviewService") as rrs_cls:
        rrs_cls.return_value.auto_review_recording = AsyncMock(return_value="rev-1")
        asyncio.run(svc._trigger_auto_review("rec-1"))
    rrs_cls.assert_called_once()


def test_trigger_auto_review_skipped(db):
    svc = _service(db)
    with patch("core.recording_review_service.RecordingReviewService") as rrs_cls:
        rrs_cls.return_value.auto_review_recording = AsyncMock(return_value=None)
        asyncio.run(svc._trigger_auto_review("rec-1"))


def test_trigger_auto_review_exception(db):
    svc = _service(db)
    with patch("core.recording_review_service.RecordingReviewService") as rrs_cls:
        rrs_cls.return_value.auto_review_recording = AsyncMock(
            side_effect=RuntimeError("review down")
        )
        asyncio.run(svc._trigger_auto_review("rec-1"))  # no raise


def test_get_canvas_recording_service_helper(db):
    svc = get_canvas_recording_service(db, tenant_id="custom")
    assert isinstance(svc, CanvasRecordingService)
    assert svc.tenant_id == "custom"


def test_module_flags_present():
    assert isinstance(CANVAS_RECORDING_ENABLED, bool)
