"""Tests for core/self_directed_progress.py — the self-directed pathway
validation read side (snapshot) and milestone nudges (maybe_notify_milestone).

Snapshot must translate the AgentEpisode ledger into progress vs the
graduation floors without lying: ratio math, guidance flags, and the
readiness verdict pass through the multi-pathway gate. Milestones must fire
once per threshold, skip non-students and ownerless agents, and never raise
(notification failures are best-effort by contract).
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.models import AgentEpisode, AgentRegistry, BlockedTriggerContext, TrainingSession
from core.self_directed_progress import maybe_notify_milestone, snapshot


def _agent(**kw):
    base = dict(
        id="a1", name="Sales Agent", category="sales",
        status="student", confidence_score=0.74,
        user_id="u1", tenant_id="default", workspace_id="default",
        configuration={},
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _episode_row(**kw):
    base = dict(
        id="e1", agent_id="a1", task_description="Quote the bandsaw",
        outcome="success", success=True,
        started_at=datetime(2026, 9, 8, 12, 0, 0),
        human_intervention_count=0, maturity_at_time="student",
        canvas_ids=["c1"],
    )
    base.update(kw)
    return SimpleNamespace(**base)


class _FakeQuery:
    """Tiny query chain; counts pop from a per-model list because
    _evidence_totals issues two AgentEpisode count queries in a fixed
    order (total rows, then successes)."""

    def __init__(self, counts, rows):
        self._counts = counts
        self._rows = rows

    def filter(self, *a, **kw):
        return self

    def order_by(self, *a, **kw):
        return self

    def limit(self, n):
        return self

    def count(self):
        return self._counts.pop(0) if self._counts else 0

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


def _db_with(episodes=4, successes=3, recent=None, agent=None, sessions=0, triggers=0,
             last_trigger=None):
    db = MagicMock()
    recent = recent if recent is not None else [_episode_row()]
    agent = agent if agent is not None else _agent()
    # Shared pop-list: _evidence_totals issues two AgentEpisode count
    # queries in a fixed order (total rows, then successes).
    episode_counts = [episodes, successes]

    def query(model):
        if model is AgentEpisode:
            return _FakeQuery(episode_counts, recent)
        if model is TrainingSession:
            return _FakeQuery([sessions], [])
        if model is AgentRegistry:
            return _FakeQuery([], [agent])
        if model is BlockedTriggerContext:
            return _FakeQuery([triggers], [last_trigger] if last_trigger else [])
        return _FakeQuery([], [])

    db.query.side_effect = query
    return db


@pytest.fixture(autouse=True)
def _pin_readiness(monkeypatch):
    """Readiness evaluation is StudentTrainingService's job; pin it here."""
    monkeypatch.setattr(
        "core.student_training_service.StudentTrainingService._evaluate_intern_readiness",
        lambda self, agent: {
            "ready": False, "pathway": "self_directed",
            "reason": "needs 3 completed sessions",
            "required_training_sessions": 3, "required_episodes": 10,
            "success_ratio": 0.7,
        },
    )


class TestSnapshot:
    async def test_evidence_math_and_guidance(self):
        db = _db_with(episodes=5, successes=4)
        snap = snapshot(db, _agent())
        assert snap["evidence"]["episodes"] == 5
        assert snap["evidence"]["successes"] == 4
        assert snap["evidence"]["success_ratio"] == 0.8
        assert snap["evidence"]["required_episodes"] == 10
        assert snap["episode_progress"] == 0.5
        assert snap["success_ratio_ok"] is True
        assert snap["confidence_ok"] is True  # 0.74 >= 0.5
        # 5/10 episodes: floors not met yet → no review flag
        assert snap["evidence_floor_met"] is False
        assert snap["ready_for_review"] is False
        labels = [g["label"] for g in snap["guidance"]]
        assert any("5/10 episodes" in l for l in labels)
        assert any("Success ratio: 80%" in l for l in labels)
        assert snap["readiness"]["pathway"] == "self_directed"

    async def test_evidence_floor_met_sets_ready_for_review(self):
        db = _db_with(episodes=12, successes=11)
        snap = snapshot(db, _agent())
        assert snap["evidence_floor_met"] is True
        assert snap["ready_for_review"] is True
        # Guidance adds the review step even though the strict pathway
        # verdict (needs sessions) is still not ready.
        assert snap["readiness"]["ready"] is False
        assert any("Evidence floor met" in g["label"] for g in snap["guidance"])

    async def test_low_ratio_marks_ratio_step_not_done(self):
        db = _db_with(episodes=10, successes=6)
        snap = snapshot(db, _agent())
        assert snap["success_ratio_ok"] is False
        ratio_steps = [g for g in snap["guidance"] if "Success ratio" in g["label"]]
        assert ratio_steps and ratio_steps[0]["done"] is False

    async def test_recent_episode_row_mapping(self):
        db = _db_with(recent=[_episode_row()])
        snap = snapshot(db, _agent())
        row = snap["recent_episodes"][0]
        assert row["task"] == "Quote the bandsaw"
        assert row["outcome"] == "success"
        assert row["canvas_ids"] == ["c1"]
        assert row["started_at"] == "2026-09-08T12:00:00"

    async def test_readiness_failure_degrades_not_raises(self, monkeypatch):
        def _boom(self, agent):
            raise RuntimeError("gate exploded")

        monkeypatch.setattr(
            "core.student_training_service.StudentTrainingService._evaluate_intern_readiness",
            _boom,
        )
        snap = snapshot(_db_with(), _agent())
        assert snap["readiness"]["ready"] is False
        assert snap["readiness"]["pathway"] is None


class TestTriggerHealthGuidance:
    """The panel must distinguish "0/3 is expected — no automated trigger
    has fired" from "the pipeline is alive, approve the proposal"."""

    async def test_zero_triggers_flags_dead_pipeline(self):
        db = _db_with(triggers=0)
        snap = snapshot(db, _agent())
        line = [g for g in snap["guidance"] if "automated trigger" in g["label"].lower()]
        assert line and line[0]["done"] is False
        assert "Manual chat and canvas work never" in line[0]["detail"]
        assert snap["trigger_health"]["blocked_triggers"] == 0

    async def test_fired_triggers_report_recency(self):
        last = SimpleNamespace(
            created_at=datetime(2026, 9, 9, 8, 30, 0),
            trigger_type="workflow_execution",
            trigger_source="WORKFLOW_ENGINE",
        )
        db = _db_with(triggers=2, last_trigger=last)
        snap = snapshot(db, _agent())
        line = [g for g in snap["guidance"] if "Automated triggers firing" in g["label"]]
        assert line and line[0]["done"] is True
        assert "2026-09-09" in line[0]["label"]
        assert "2 total" in line[0]["label"]
        assert snap["trigger_health"]["last_trigger_type"] == "workflow_execution"
        assert snap["trigger_health"]["last_fired_at"] == "2026-09-09T08:30:00"


class TestMaybeNotifyMilestone:
    async def test_fires_on_first_crossing_and_dedupes(self):
        agent = _agent()
        db = _db_with(episodes=8, agent=agent)  # 8/10 → crosses 0.5 and 0.75
        with patch("core.notification_service.NotificationService") as NS:
            NS.return_value._persist_and_maybe_email.return_value = {"success": True}
            payload = maybe_notify_milestone(db, "a1")
            assert payload is not None
            assert "8/10" in payload["message"]
            # All crossed milestones recorded (0.8 crosses 0.25/0.5/0.75) so
            # a burst of episodes never spams one notification per threshold.
            notified = agent.configuration["learning"]["milestones_notified"]
            assert sorted(notified) == [0.25, 0.5, 0.75]
            db.commit.assert_called()
            # Second run: nothing pending → no notification
            assert maybe_notify_milestone(db, "a1") is None

    async def test_skips_non_student(self):
        db = _db_with(agent=_agent(status="intern"))
        assert maybe_notify_milestone(db, "a1") is None

    async def test_skips_below_first_milestone(self):
        db = _db_with(episodes=1)
        assert maybe_notify_milestone(db, "a1") is None

    async def test_skips_ownerless_agent(self):
        db = _db_with(agent=_agent(user_id=None))
        assert maybe_notify_milestone(db, "a1") is None

    async def test_notification_failure_never_raises(self):
        db = _db_with(episodes=8)
        with patch("core.notification_service.NotificationService") as NS:
            NS.return_value._persist_and_maybe_email.side_effect = RuntimeError("db down")
            # Best-effort contract: returns None, doesn't raise, rolls back.
            assert maybe_notify_milestone(db, "a1") is None
