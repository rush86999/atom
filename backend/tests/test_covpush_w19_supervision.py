"""Coverage wave 19 — core/supervision_service (TDD).

Real-bug probes:
- WH1: ``complete_supervision`` uses ``asyncio.create_task`` on
  ``episode_service.create_supervision_episode`` and
  ``_process_supervision_feedback`` — inside async context so it schedules
  fine, but exceptions inside those tasks are unobserved; and when called
  from a SYNC context (e.g. test/CLI) create_task raises RuntimeError.
- WH2: ``monitor_with_autonomous_fallback`` reads
  ``session.trigger_context.get("user_id")`` — trigger_context is JSON; a
  non-dict or None crashes with AttributeError.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    SupervisionSession,
    SupervisionStatus,
)
from core.supervision_service import SupervisionService


@pytest.fixture
def fresh_db():
    """Isolated temp-file SQLite DB per test."""
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def _agent(db, status=AgentStatus.SUPERVISED.value, confidence=0.75, agent_id=None):
    agent = AgentRegistry(
        id=agent_id or f"agent-{uuid.uuid4().hex[:8]}",
        name="Helper", category="general", description="d",
        status=status, confidence_score=confidence,
        module_path="core.agents.generic_agent", class_name="GenericAgent",
        workspace_id="ws-1",
    )
    db.add(agent)
    db.commit()
    return agent


def _session(db, agent, status=SupervisionStatus.RUNNING.value, supervisor_id="u-sup",
             trigger_context=None, interventions=None):
    s = SupervisionSession(
        agent_id=agent.id, agent_name=agent.name, workspace_id="ws-1",
        trigger_context=trigger_context or {"trigger_type": "manual"},
        status=status, supervisor_id=supervisor_id,
    )
    if interventions:
        s.interventions = list(interventions)
        s.intervention_count = len(interventions)
    db.add(s)
    db.commit()
    return s


class TestStartSession:
    @pytest.mark.asyncio
    async def test_start_supervision_session(self, fresh_db):
        agent = _agent(fresh_db)
        svc = SupervisionService(fresh_db)
        session = await svc.start_supervision_session(
            agent_id=agent.id, trigger_context={"t": 1}, workspace_id="ws-1",
            supervisor_id="u-sup",
        )
        assert session.id
        assert session.agent_id == agent.id
        assert session.agent_name == "Helper"
        assert session.status == SupervisionStatus.RUNNING.value
        assert session.supervisor_id == "u-sup"
        # persisted
        fresh_db.expire_all()
        row = fresh_db.query(SupervisionSession).filter(SupervisionSession.id == session.id).first()
        assert row is not None

    @pytest.mark.asyncio
    async def test_start_session_missing_agent_raises(self, fresh_db):
        svc = SupervisionService(fresh_db)
        with pytest.raises(ValueError):
            await svc.start_supervision_session(
                agent_id="ghost", trigger_context={}, workspace_id="ws-1",
                supervisor_id="u-sup",
            )


class TestMonitorExecution:
    @pytest.mark.asyncio
    async def test_monitor_yields_events_until_completed(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        # Realistic timing: execution started AFTER the supervision session.
        # Both timestamps must be AWARE — the naive func.now() default mixes
        # with aware values in SQLite's string comparisons (a real footgun).
        session.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        exec_row = AgentExecution(
            id=f"exec-{uuid.uuid4().hex[:8]}", agent_id=agent.id,
            status="running", started_at=session.started_at + timedelta(minutes=1),
            workspace_id="ws-1", triggered_by="test",
        )
        fresh_db.add(exec_row)
        fresh_db.commit()

        # After the first poll, flip the execution to completed so the loop
        # terminates (status change yields a "result" event and breaks).
        flipped = {"done": False}

        async def fake_sleep(sec):
            if not flipped["done"]:
                flipped["done"] = True
                exec_row.status = "completed"
                fresh_db.commit()

        svc = SupervisionService(fresh_db)
        events = []
        with patch("core.supervision_service.asyncio.sleep", side_effect=fake_sleep):
            async for ev in svc.monitor_agent_execution(session, fresh_db):
                events.append(ev)

        assert events, "should yield at least the execution_started event"
        types = [e.event_type for e in events]
        assert "action" in types
        assert "result" in types  # execution completed after first poll
        assert all(e.timestamp for e in events)

    @pytest.mark.asyncio
    async def test_monitor_completed_breaks_early(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        session.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        fresh_db.add(AgentExecution(
            id=f"exec-{uuid.uuid4().hex[:8]}", agent_id=agent.id,
            status="completed", started_at=session.started_at + timedelta(minutes=1),
            workspace_id="ws-1", triggered_by="test",
        ))
        fresh_db.commit()
        svc = SupervisionService(fresh_db)
        events = []
        with patch("core.supervision_service.asyncio.sleep", new=AsyncMock()):
            async for ev in svc.monitor_agent_execution(session, fresh_db):
                events.append(ev)
        types = [e.event_type for e in events]
        assert "result" in types
        assert types[-1] == "result"

    @pytest.mark.asyncio
    async def test_monitor_failed_breaks_early(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        session.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        fresh_db.add(AgentExecution(
            id=f"exec-{uuid.uuid4().hex[:8]}", agent_id=agent.id,
            status="failed", error_message="boom",
            started_at=session.started_at + timedelta(minutes=1),
            workspace_id="ws-1", triggered_by="test",
        ))
        fresh_db.commit()
        svc = SupervisionService(fresh_db)
        events = []
        with patch("core.supervision_service.asyncio.sleep", new=AsyncMock()):
            async for ev in svc.monitor_agent_execution(session, fresh_db):
                events.append(ev)
        types = [e.event_type for e in events]
        assert "error" in types
        assert types[-1] == "error"

    @pytest.mark.asyncio
    async def test_monitor_session_not_running_breaks(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent, status=SupervisionStatus.COMPLETED.value)
        svc = SupervisionService(fresh_db)
        events = []
        async for ev in svc.monitor_agent_execution(session, fresh_db):
            events.append(ev)
        assert events == []

    @pytest.mark.asyncio
    async def test_monitor_error_yields_error_event(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        events = []
        db_broken = MagicMock()
        db_broken.refresh.side_effect = RuntimeError("db down")
        with patch("core.supervision_service.asyncio.sleep", new=AsyncMock()):
            async for ev in svc.monitor_agent_execution(session, db_broken):
                events.append(ev)
        assert events
        assert events[-1].event_type == "error"
        assert events[-1].data["error_type"] == "monitoring_error"


class TestIntervene:
    @pytest.mark.asyncio
    async def test_intervene_pause(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        result = await svc.intervene(session.id, "pause", "wait for approval")
        assert result.success is True
        assert result.session_state == "paused"
        fresh_db.expire_all()
        row = fresh_db.query(SupervisionSession).filter(SupervisionSession.id == session.id).first()
        assert row.intervention_count == 1
        assert row.interventions[0]["type"] == "pause"

    @pytest.mark.asyncio
    async def test_intervene_correct(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        result = await svc.intervene(session.id, "correct", "use the other field")
        assert result.success is True
        assert result.session_state == "running"

    @pytest.mark.asyncio
    async def test_intervene_terminate(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        result = await svc.intervene(session.id, "terminate", "bad behavior")
        assert result.success is True
        assert result.session_state == "terminated"
        fresh_db.expire_all()
        row = fresh_db.query(SupervisionSession).filter(SupervisionSession.id == session.id).first()
        assert row.status == SupervisionStatus.INTERRUPTED.value
        assert row.completed_at is not None

    @pytest.mark.asyncio
    async def test_intervene_errors(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        with pytest.raises(ValueError):
            await svc.intervene("ghost", "pause", "x")
        with pytest.raises(ValueError):
            await svc.intervene(session.id, "weird", "x")
        completed = _session(fresh_db, agent, status=SupervisionStatus.COMPLETED.value)
        with pytest.raises(ValueError):
            await svc.intervene(completed.id, "pause", "x")


class TestCompleteSupervision:
    @pytest.mark.asyncio
    async def test_complete_boosts_confidence_and_promotes(self, fresh_db):
        agent = _agent(fresh_db, confidence=0.85)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        outcome = await svc.complete_supervision(session.id, supervisor_rating=5, feedback="great")
        assert outcome.success is True
        assert outcome.confidence_boost == 0.1
        fresh_db.expire_all()
        agent2 = fresh_db.query(AgentRegistry).filter(AgentRegistry.id == agent.id).first()
        assert agent2.confidence_score == 0.95
        assert agent2.status == AgentStatus.AUTONOMOUS.value  # 0.95 >= 0.9 promotes
        session2 = fresh_db.query(SupervisionSession).filter(SupervisionSession.id == session.id).first()
        assert session2.status == SupervisionStatus.COMPLETED.value
        assert session2.supervisor_rating == 5
        assert session2.duration_seconds is not None

    @pytest.mark.asyncio
    async def test_complete_promotes_to_autonomous(self, fresh_db):
        agent = _agent(fresh_db, confidence=0.85)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        await svc.complete_supervision(session.id, 5, "great")
        fresh_db.expire_all()
        agent2 = fresh_db.query(AgentRegistry).filter(AgentRegistry.id == agent.id).first()
        assert agent2.status == AgentStatus.AUTONOMOUS.value  # 0.95 >= 0.9

    @pytest.mark.asyncio
    async def test_complete_low_rating_no_promotion(self, fresh_db):
        agent = _agent(fresh_db, confidence=0.75)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        outcome = await svc.complete_supervision(session.id, 1, "poor")
        assert outcome.success is False
        assert outcome.confidence_boost == 0.0
        fresh_db.expire_all()
        agent2 = fresh_db.query(AgentRegistry).filter(AgentRegistry.id == agent.id).first()
        assert agent2.confidence_score == 0.75
        assert agent2.status == AgentStatus.SUPERVISED.value

    @pytest.mark.asyncio
    async def test_complete_intervention_penalty(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent, interventions=[
            {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "pause", "guidance": "g"},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "correct", "guidance": "g"},
        ])
        svc = SupervisionService(fresh_db)
        outcome = await svc.complete_supervision(session.id, 5, "ok")
        assert outcome.intervention_count == 2
        assert outcome.confidence_boost == 0.08  # 0.1 - 2*0.01

    @pytest.mark.asyncio
    async def test_complete_errors(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        svc = SupervisionService(fresh_db)
        with pytest.raises(ValueError):
            await svc.complete_supervision("ghost", 5, "x")
        completed = _session(fresh_db, agent, status=SupervisionStatus.COMPLETED.value)
        with pytest.raises(ValueError):
            await svc.complete_supervision(completed.id, 5, "x")


class TestQueries:
    @pytest.mark.asyncio
    async def test_get_active_sessions(self, fresh_db):
        agent = _agent(fresh_db)
        s1 = _session(fresh_db, agent, supervisor_id="u-1")
        s2 = _session(fresh_db, agent, supervisor_id="u-2")
        _session(fresh_db, agent, status=SupervisionStatus.COMPLETED.value)
        svc = SupervisionService(fresh_db)
        active = await svc.get_active_sessions()
        ids = {s.id for s in active}
        assert s1.id in ids and s2.id in ids
        assert len(active) == 2
        ws_active = await svc.get_active_sessions(workspace_id="ws-1")
        assert len(ws_active) == 2
        other = await svc.get_active_sessions(workspace_id="other")
        assert other == []

    @pytest.mark.asyncio
    async def test_get_supervision_history(self, fresh_db):
        agent = _agent(fresh_db)
        s1 = _session(fresh_db, agent, status=SupervisionStatus.COMPLETED.value)
        s1.supervisor_rating = 4
        s1.supervisor_feedback = "good"
        s1.confidence_boost = 0.05
        s1.completed_at = datetime.now(timezone.utc)
        fresh_db.commit()
        svc = SupervisionService(fresh_db)
        history = await svc.get_supervision_history(agent.id)
        assert len(history) == 1
        assert history[0]["session_id"] == s1.id
        assert history[0]["supervisor_rating"] == 4
        assert history[0]["confidence_boost"] == 0.05
        assert history[0]["completed_at"] is not None
        assert await svc.get_supervision_history("ghost") == []


class TestConfidenceBoost:
    def test_boost_math(self):
        svc = SupervisionService(MagicMock())
        assert svc._calculate_confidence_boost(5, 0, 60) == 0.1
        assert svc._calculate_confidence_boost(1, 0, 60) == 0.0
        assert svc._calculate_confidence_boost(3, 0, 60) == 0.05
        assert svc._calculate_confidence_boost(5, 5, 60) == 0.05  # penalty capped
        assert svc._calculate_confidence_boost(5, 20, 60) == 0.05
        assert svc._calculate_confidence_boost(2, 10, 60) == 0.0  # floor


class TestAutonomousFallback:
    @pytest.mark.asyncio
    async def test_user_online_no_autonomous(self, fresh_db):
        agent = _agent(fresh_db)
        user_activity = AsyncMock()
        user_activity.get_user_state.return_value = "online"
        with patch("core.user_activity_service.UserActivityService", return_value=user_activity):
            svc = SupervisionService(fresh_db)
            session = await svc.start_supervision_with_fallback(
                agent_id=agent.id, trigger_context={"trigger_type": "manual"},
                workspace_id="ws-1", user_id="u-1",
            )
        assert session.supervisor_id == "u-1"
        assert session.status == SupervisionStatus.RUNNING.value

    @pytest.mark.asyncio
    async def test_user_away_falls_back_to_autonomous(self, fresh_db):
        agent = _agent(fresh_db)
        user_activity = AsyncMock()
        user_activity.get_user_state.return_value = "offline"
        autonomous = AsyncMock()
        autonomous.find_autonomous_supervisor.return_value = SimpleNamespace(id="agent-sup")
        with patch("core.user_activity_service.UserActivityService", return_value=user_activity), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService", return_value=autonomous):
            svc = SupervisionService(fresh_db)
            session = await svc.start_supervision_with_fallback(
                agent_id=agent.id, trigger_context={}, workspace_id="ws-1", user_id="u-1",
            )
        assert session.supervisor_id == "agent-sup"
        assert session.status == SupervisionStatus.RUNNING.value

    @pytest.mark.asyncio
    async def test_user_away_no_supervisor_queues(self, fresh_db):
        agent = _agent(fresh_db)
        user_activity = AsyncMock()
        user_activity.get_user_state.return_value = "offline"
        autonomous = AsyncMock()
        autonomous.find_autonomous_supervisor.return_value = None
        queue = AsyncMock()
        with patch("core.user_activity_service.UserActivityService", return_value=user_activity), \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService", return_value=autonomous), \
             patch("core.supervised_queue_service.SupervisedQueueService", return_value=queue):
            svc = SupervisionService(fresh_db)
            with pytest.raises(ValueError) as exc:
                await svc.start_supervision_with_fallback(
                    agent_id=agent.id, trigger_context={"trigger_type": "automated"},
                    workspace_id="ws-1", user_id="u-1",
                )
        assert "queued" in str(exc.value)
        queue.enqueue_execution.assert_awaited_once()
        kwargs = queue.enqueue_execution.await_args.kwargs
        assert kwargs["trigger_type"] == "automated"

    @pytest.mark.asyncio
    async def test_monitor_with_autonomous_fallback(self, fresh_db):
        agent = _agent(fresh_db)
        sup = _agent(fresh_db, agent_id="sup-agent")
        session = _session(fresh_db, agent, supervisor_id=sup.id,
                           trigger_context={"user_id": "u-1"})
        session.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        fresh_db.add(AgentExecution(
            id=f"exec-{uuid.uuid4().hex[:8]}", agent_id=agent.id,
            status="running", started_at=session.started_at + timedelta(minutes=1),
            workspace_id="ws-1", triggered_by="test",
        ))
        fresh_db.commit()
        autonomous = AsyncMock()
        called = {"n": 0}

        async def fake_monitor(*a, **k):
            called["n"] += 1
            yield SimpleNamespace(event_type="action", data={})
            yield SimpleNamespace(event_type="concern_detected", data={})

        autonomous.monitor_execution = fake_monitor
        with patch("core.autonomous_supervisor_service.AutonomousSupervisorService", return_value=autonomous):
            svc = SupervisionService(fresh_db)
            await svc.monitor_with_autonomous_fallback(session)
        assert called["n"] == 1

    @pytest.mark.asyncio
    async def test_monitor_autonomous_supervisor_missing(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent, supervisor_id="ghost-sup",
                           trigger_context={"user_id": "u-1"})
        with patch("core.autonomous_supervisor_service.AutonomousSupervisorService"):
            svc = SupervisionService(fresh_db)
            await svc.monitor_with_autonomous_fallback(session)  # no crash

    @pytest.mark.asyncio
    async def test_monitor_human_session_noop(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent, supervisor_id="u-1",
                           trigger_context={"user_id": "u-1"})
        with patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as auto:
            svc = SupervisionService(fresh_db)
            await svc.monitor_with_autonomous_fallback(session)
        auto.assert_not_called()


class TestFeedbackProcessing:
    @pytest.mark.asyncio
    async def test_process_feedback_with_interventions(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent, supervisor_id="u-sup",
                           interventions=[
                               {"timestamp": datetime.now(timezone.utc).isoformat(),
                                "type": "pause", "guidance": "g"},
                           ])
        session.supervisor_rating = 4
        fresh_db.commit()
        feedback = AsyncMock()
        learning = AsyncMock()
        perf = AsyncMock()
        with patch("core.supervisor_performance_service.SupervisorPerformanceService", return_value=perf):
            svc = SupervisionService(fresh_db)
            await svc._process_supervision_feedback(session, feedback, learning)
        feedback.rate_supervisor.assert_awaited_once()
        kwargs = feedback.rate_supervisor.await_args.kwargs
        assert kwargs["rater_id"] == "system_u-sup"
        assert kwargs["rating"] == 4
        perf.track_intervention_outcome.assert_awaited_once()
        learning.process_feedback_for_learning.assert_awaited()

    @pytest.mark.asyncio
    async def test_process_feedback_error_swallowed(self, fresh_db):
        agent = _agent(fresh_db)
        session = _session(fresh_db, agent)
        feedback = AsyncMock()
        feedback.rate_supervisor.side_effect = RuntimeError("boom")
        with patch("core.supervision_service.logger") as mock_logger:
            svc = SupervisionService(fresh_db)
            await svc._process_supervision_feedback(session, feedback, AsyncMock())
        mock_logger.error.assert_called_once()
