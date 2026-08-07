"""
Coverage-push + bug-hunt tests for agent core modules:
- agent_coordination
- agent_request_manager
- agent_integration_gateway
- background_agent_runner
- agent_promotion_service
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import os

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session():
    import tempfile
    from core.models_registration import Base
    _fd, _db_path = tempfile.mkstemp(suffix=".db")
    os.close(_fd)
    engine = create_engine(
        f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
    _seen_idx = set()
    for _table in list(Base.metadata.tables.values()):
        for _idx in list(_table.indexes):
            if _idx.name in _seen_idx:
                _table.indexes.remove(_idx)
            else:
                _seen_idx.add(_idx.name)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(_db_path)
        except OSError:
            pass


# ============================================================================
# Agent promotion service
# ============================================================================

GOOD_SUMMARY = {
    "total_feedback": 12,
    "positive_count": 11,
    "average_rating": 4.6,
    "feedback_types": {"correction": 1},
}


class TestAgentPromotionService:
    def _svc(self, db_session, summary=None):
        from core.agent_promotion_service import AgentPromotionService
        svc = AgentPromotionService(db_session)
        svc.feedback_analytics.get_agent_feedback_summary = Mock(
            return_value=summary if summary is not None else GOOD_SUMMARY)
        return svc

    def _agent(self, db_session, agent_id, status, confidence=0.9):
        from core.models import AgentRegistry
        agent = AgentRegistry(
            id=agent_id, name=f"Agent {agent_id}", category="Ops",
            module_path="m", class_name="c", status=status,
            confidence_score=confidence)
        db_session.add(agent)
        db_session.commit()
        return agent

    def test_get_promotion_suggestions_returns_interns(self, db_session):
        self._agent(db_session, "a1", "intern", confidence=0.85)
        svc = self._svc(db_session)
        suggestions = svc.get_promotion_suggestions()
        assert len(suggestions) == 1
        assert suggestions[0]["agent_id"] == "a1"
        assert suggestions[0]["target_status"] == "SUPERVISED"
        assert suggestions[0]["ready_for_promotion"] is True

    def test_get_promotion_suggestions_excludes_autonomous(self, db_session):
        self._agent(db_session, "a1", "intern", confidence=0.85)
        self._agent(db_session, "a2", "supervised", confidence=0.95)
        self._agent(db_session, "a3", "autonomous", confidence=0.99)
        self._agent(db_session, "a4", "student", confidence=0.99)
        svc = self._svc(db_session)
        suggestions = svc.get_promotion_suggestions()
        assert len(suggestions) == 2

    def test_get_promotion_suggestions_sorted_and_limited(self, db_session):
        self._agent(db_session, "low", "intern", confidence=0.4)
        self._agent(db_session, "high", "intern", confidence=0.95)
        svc = self._svc(db_session)
        suggestions = svc.get_promotion_suggestions(limit=1)
        assert len(suggestions) == 1
        assert suggestions[0]["agent_id"] == "high"

    def test_get_promotion_suggestions_agents_not_ready(self, db_session):
        from core.agent_promotion_service import AgentPromotionService
        self._agent(db_session, "a1", "intern", confidence=0.4)
        svc = AgentPromotionService(db_session)
        svc.feedback_analytics.get_agent_feedback_summary = Mock(return_value={
            "total_feedback": 1,
            "positive_count": 0,
            "average_rating": 1.0,
            "feedback_types": {"correction": 0},
        })
        assert svc.get_promotion_suggestions() == []

    def test_is_agent_ready_not_found(self, db_session):
        svc = self._svc(db_session)
        result = svc.is_agent_ready_for_promotion("missing")
        assert result["ready"] is False
        assert "not found" in result["reason"]

    def test_is_agent_ready_already_autonomous(self, db_session):
        self._agent(db_session, "a1", "autonomous")
        svc = self._svc(db_session)
        result = svc.is_agent_ready_for_promotion("a1")
        assert result["ready"] is False

    def test_is_agent_ready_with_explicit_target(self, db_session):
        self._agent(db_session, "a1", "intern", confidence=0.8)
        svc = self._svc(db_session)
        result = svc.is_agent_ready_for_promotion("a1", target_status="AUTONOMOUS")
        assert result["ready"] is False
        assert result["criteria_failed"]["confidence_score"]

    def test_evaluate_no_feedback(self, db_session):
        from core.agent_promotion_service import AgentPromotionService
        self._agent(db_session, "a1", "intern")
        svc = AgentPromotionService(db_session)
        svc.feedback_analytics.get_agent_feedback_summary = Mock(
            side_effect=ValueError("no feedback"))
        result = svc.is_agent_ready_for_promotion("a1")
        assert result["ready"] is False
        assert result["reason"] == "No feedback data available"

    def test_evaluate_supervised_to_autonomous_requires_0_9_confidence(self, db_session):
        self._agent(db_session, "a1", "supervised", confidence=0.75)
        svc = self._svc(db_session)
        result = svc.is_agent_ready_for_promotion("a1")
        assert result["target_status"] == "AUTONOMOUS"
        assert "confidence_score" in result["criteria_failed"]
        assert "need ≥ 0.9" in result["criteria_failed"]["confidence_score"]

    def test_evaluate_ready_for_supervised(self, db_session):
        self._agent(db_session, "a1", "intern", confidence=0.8)
        svc = self._svc(db_session)
        result = svc.is_agent_ready_for_promotion("a1")
        assert result["ready"] is True
        assert result["readiness_score"] >= 0.8
        assert "feedback_count" in result["criteria_met"]
        assert "positive_ratio" in result["criteria_met"]
        assert "average_rating" in result["criteria_met"]
        assert "correction_count" in result["criteria_met"]
        assert "confidence_score" in result["criteria_met"]

    def test_evaluate_not_ready(self, db_session):
        self._agent(db_session, "a1", "intern", confidence=0.4)
        svc = self._svc(db_session)
        result = svc.is_agent_ready_for_promotion("a1")
        assert result["ready"] is False
        assert "Needs improvement" in result["reason"]

    def test_get_promotion_path_not_found(self, db_session):
        svc = self._svc(db_session)
        assert svc.get_promotion_path("missing")["error"] == "Agent not found"

    def test_get_promotion_path_student(self, db_session):
        self._agent(db_session, "a1", "student", confidence=0.3)
        svc = self._svc(db_session)
        path = svc.get_promotion_path("a1")
        steps = path["promotion_path"]
        assert len(steps) == 3
        assert steps[0]["from"] == "STUDENT"
        assert steps[0]["to"] == "INTERN"
        assert steps[1]["to"] == "SUPERVISED"
        assert steps[2]["to"] == "AUTONOMOUS"

    def test_get_promotion_path_intern(self, db_session):
        self._agent(db_session, "a1", "intern", confidence=0.8)
        svc = self._svc(db_session)
        path = svc.get_promotion_path("a1")
        assert len(path["promotion_path"]) == 2
        assert path["promotion_path"][0]["to"] == "SUPERVISED"

    def test_get_promotion_path_supervised(self, db_session):
        self._agent(db_session, "a1", "supervised", confidence=0.9)
        svc = self._svc(db_session)
        path = svc.get_promotion_path("a1")
        assert len(path["promotion_path"]) == 1
        assert path["promotion_path"][0]["to"] == "AUTONOMOUS"
        assert path["promotion_path"][0]["ready"] is True

    def test_get_promotion_path_autonomous(self, db_session):
        self._agent(db_session, "a1", "autonomous")
        svc = self._svc(db_session)
        assert svc.get_promotion_path("a1")["promotion_path"] == []

    def test_executions_affect_success_rate_criteria(self, db_session):
        from core.models import AgentExecution
        self._agent(db_session, "a1", "intern", confidence=0.8)
        db_session.add(AgentExecution(
            id="e1", agent_id="a1", tenant_id="default",
            status="completed", started_at=datetime.now(timezone.utc)))
        db_session.commit()
        svc = self._svc(db_session)
        result = svc.is_agent_ready_for_promotion("a1")
        assert "execution_success_rate" in result["criteria_met"]


# ============================================================================
# Background agent runner
# ============================================================================

class TestBackgroundAgentRunner:
    def _runner(self, tmp_path):
        from core.background_agent_runner import BackgroundAgentRunner
        return BackgroundAgentRunner(log_dir=str(tmp_path / "logs"))

    def test_register_agent(self, tmp_path):
        runner = self._runner(tmp_path)
        runner.register_agent("agent-1", interval_seconds=10)
        assert runner.get_status("agent-1")["status"] == "stopped"
        assert runner.get_status("agent-1")["run_count"] == 0

    @pytest.mark.asyncio
    async def test_start_agent_not_registered(self, tmp_path):
        runner = self._runner(tmp_path)
        with pytest.raises(ValueError):
            await runner.start_agent("missing")

    @pytest.mark.asyncio
    async def test_start_and_stop_agent(self, tmp_path):
        runner = self._runner(tmp_path)
        runner.register_agent("agent-1")
        await runner.start_agent("agent-1")
        assert runner.get_status("agent-1")["status"] == "running"
        with patch.object(runner, "_run_loop", new=AsyncMock()):
            await runner.start_agent("agent-1")
        await runner.stop_agent("agent-1")
        assert runner.get_status("agent-1")["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_stop_agent_unregistered(self, tmp_path):
        runner = self._runner(tmp_path)
        await runner.stop_agent("missing")

    @pytest.mark.asyncio
    async def test_run_loop_success(self, tmp_path):
        from core.background_agent_runner import AgentStatus
        runner = self._runner(tmp_path)
        runner.register_agent("agent-1", interval_seconds=0)
        runner._agents["agent-1"].status = AgentStatus.RUNNING
        with patch.object(runner, "_execute_agent", new=AsyncMock(return_value={})), \
             patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)):
            await runner._run_loop("agent-1")
        status = runner.get_status("agent-1")
        assert status["run_count"] == 1
        assert status["last_run"] is not None

    @pytest.mark.asyncio
    async def test_run_loop_error_sets_error_state(self, tmp_path):
        from core.background_agent_runner import AgentStatus
        runner = self._runner(tmp_path)
        runner.register_agent("agent-1", interval_seconds=0)
        runner._agents["agent-1"].status = AgentStatus.RUNNING
        with patch.object(runner, "_execute_agent",
                          new=AsyncMock(side_effect=RuntimeError("boom"))), \
             patch("asyncio.sleep", new=AsyncMock()):
            await runner._run_loop("agent-1")
        status = runner.get_status("agent-1")
        assert status["status"] == "error"
        assert status["error_count"] == 1
        assert status["last_error"] == "boom"

    @pytest.mark.asyncio
    async def test_execute_agent_in_registry(self, tmp_path):
        runner = self._runner(tmp_path)
        fake_agent_routes = MagicMock()
        fake_agent_routes.AGENTS = {"agent-1": {"name": "Test Agent"}}
        fake_agent_routes.execute_agent_task = AsyncMock(return_value={"status": "ok"})

        from contextlib import contextmanager

        @contextmanager
        def fake_session():
            from sqlalchemy.orm import sessionmaker
            session = sessionmaker(bind=runner_db_engine)()
            try:
                yield session
            finally:
                session.close()

        from core.models_registration import Base
        engine = create_engine("sqlite:///:memory:",
                               connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(engine)
        runner_db_engine = engine

        from core.models import AgentRegistry
        session = sessionmaker(bind=engine)()
        session.add(AgentRegistry(
            id="agent-1", name="Test Agent", category="Ops",
            module_path="m", class_name="c", user_id="user-1"))
        session.commit()
        session.close()

        with patch.dict(sys.modules, {"api.agent_routes": fake_agent_routes}), \
             patch("core.database.get_db_session", side_effect=fake_session):
            result = await runner._execute_agent("agent-1")
        assert result == {"status": "ok"}
        call = fake_agent_routes.execute_agent_task.await_args
        assert call.args[2]["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_execute_agent_not_in_registry(self, tmp_path):
        runner = self._runner(tmp_path)
        fake_agent_routes = MagicMock()
        fake_agent_routes.AGENTS = {}
        with patch.dict(sys.modules, {"api.agent_routes": fake_agent_routes}):
            assert await runner._execute_agent("ghost") is None

    @pytest.mark.asyncio
    async def test_execute_agent_exception_re_raises(self, tmp_path):
        runner = self._runner(tmp_path)
        fake_agent_routes = MagicMock()
        fake_agent_routes.AGENTS = {"agent-1": {}}
        fake_agent_routes.execute_agent_task = AsyncMock(side_effect=RuntimeError("failed"))
        with patch.dict(sys.modules, {"api.agent_routes": fake_agent_routes}), \
             patch("core.database.get_db_session",
                   side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                await runner._execute_agent("agent-1")

    def test_log_and_get_logs(self, tmp_path):
        runner = self._runner(tmp_path)
        runner.register_agent("agent-1")
        runner._log("agent-1", "test-event", "some details", "info")
        logs = runner.get_logs("agent-1")
        assert len(logs) == 2
        assert logs[0]["event"] in ("registered", "test-event")
        assert logs[-1]["details"] == "some details"
        assert (tmp_path / "logs" / "agent-1.log").exists()

    def test_get_logs_limit(self, tmp_path):
        runner = self._runner(tmp_path)
        for i in range(5):
            runner._log("agent-1", f"event-{i}", None)
        assert len(runner.get_logs("agent-1", limit=3)) == 3
        assert len(runner.get_logs()) == 5

    def test_get_status_not_found(self, tmp_path):
        runner = self._runner(tmp_path)
        assert "error" in runner.get_status("missing")

    def test_get_status_all(self, tmp_path):
        runner = self._runner(tmp_path)
        runner.register_agent("agent-1")
        runner.register_agent("agent-2")
        statuses = runner.get_status()
        assert set(statuses.keys()) == {"agent-1", "agent-2"}

    def test_global_runner_exists(self):
        from core.background_agent_runner import background_runner
        assert background_runner is not None


# ============================================================================
# Agent request manager
# ============================================================================

class TestAgentRequestManager:
    def _svc(self, db_session):
        from core.agent_request_manager import AgentRequestManager
        return AgentRequestManager(db_session)

    @pytest.mark.asyncio
    async def test_create_permission_request_success(self, db_session):
        from core.models import AgentRequestLog, CanvasAudit
        db_session.add(_make_agent(db_session, "agent-1"))
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "Need permission", "send_email",
            {"operation": "email"}, urgency="high")
        assert isinstance(request_id, str)
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row is not None
        assert row.request_type == "permission"
        assert row.user_id == "user-1"
        assert row.request_data["urgency"] == "high"
        assert row.request_data["governance"]["requires_signature"] is False
        assert db_session.query(CanvasAudit).count() == 1
        assert request_id in svc._pending_requests

    @pytest.mark.asyncio
    async def test_create_permission_request_blocking_signature(self, db_session):
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "blocking", "delete", {}, urgency="blocking")
        from core.models import AgentRequestLog
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.request_data["governance"]["requires_signature"] is True

    @pytest.mark.asyncio
    async def test_create_permission_request_disabled(self, db_session):
        from core import agent_request_manager as arm
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        with patch.object(arm, "AGENT_REQUESTS_ENABLED", False):
            request_id = await svc.create_permission_request(
                "user-1", "agent-1", "t", "p", {})
        from core.models import AgentRequestLog
        assert db_session.query(AgentRequestLog).count() == 0

    @pytest.mark.asyncio
    async def test_create_permission_request_exception(self, db_session):
        svc = self._svc(db_session)
        with patch.object(svc, "_create_audit",
                          new=AsyncMock(side_effect=RuntimeError("audit fail"))):
            with patch("core.agent_request_manager.ws_manager") as ws:
                ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
                request_id = await svc.create_permission_request(
                    "user-1", "agent-1", "t", "p", {})
        assert isinstance(request_id, str)

    @pytest.mark.asyncio
    async def test_create_decision_request(self, db_session):
        from core.models import AgentRequestLog
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_decision_request(
            "user-1", "agent-1", "Which option?", "Need a decision",
            [{"label": "A"}, {"label": "B"}], {}, suggested_option=1)
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.request_type == "decision"
        assert row.request_data["suggested_option"] == 1

    @pytest.mark.asyncio
    async def test_create_decision_request_missing_agent_name(self, db_session):
        svc = self._svc(db_session)
        request_id = await svc.create_decision_request(
            "user-1", "ghost-agent", "title", "explanation", [{}], {})
        from core.models import AgentRequestLog
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.request_data["agent_name"] == "Agent"

    @pytest.mark.asyncio
    async def test_wait_for_response_not_found(self, db_session):
        svc = self._svc(db_session)
        assert await svc.wait_for_response("missing") is None

    @pytest.mark.asyncio
    async def test_wait_for_response_timeout_marks_revoked(self, db_session):
        from core.models import AgentRequestLog
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "t", "p", {})
        result = await svc.wait_for_response(request_id, timeout=0)
        assert result is None
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.revoked is True
        assert request_id not in svc._pending_requests

    @pytest.mark.asyncio
    async def test_wait_for_response_returns_user_response(self, db_session):
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "t", "p", {})
        svc._pending_requests[request_id].set()
        from core.models import AgentRequestLog
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        row.user_response = {"action": "approve"}
        db_session.commit()
        result = await svc.wait_for_response(request_id)
        assert result == {"action": "approve"}

    @pytest.mark.asyncio
    async def test_handle_response_disabled(self, db_session):
        from core import agent_request_manager as arm
        svc = self._svc(db_session)
        with patch.object(arm, "AGENT_REQUESTS_ENABLED", False):
            await svc.handle_response("user-1", "r1", {})

    @pytest.mark.asyncio
    async def test_handle_response_not_found(self, db_session):
        svc = self._svc(db_session)
        await svc.handle_response("user-1", "missing", {"action": "approve"})

    @pytest.mark.asyncio
    async def test_handle_response_wrong_user(self, db_session):
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "t", "p", {})
        await svc.handle_response("user-2", request_id, {"action": "approve"})
        from core.models import AgentRequestLog
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.user_response is None

    @pytest.mark.asyncio
    async def test_handle_response_expired(self, db_session):
        from core.models import AgentRequestLog
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "t", "p", {})
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()
        await svc.handle_response("user-1", request_id, {"action": "approve"})
        db_session.expire_all()
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.user_response is None

    @pytest.mark.asyncio
    async def test_handle_response_success_sets_event(self, db_session):
        from core.models import AgentRequestLog, CanvasAudit
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "t", "p", {})
        await svc.handle_response("user-1", request_id, {"action": "approve"})
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.user_response == {"action": "approve"}
        assert row.response_time_seconds is not None
        assert svc._pending_requests[request_id].is_set()
        assert db_session.query(CanvasAudit).count() == 2

    @pytest.mark.asyncio
    async def test_revoke_request(self, db_session):
        from core.models import AgentRequestLog
        _make_agent(db_session, "agent-1")
        svc = self._svc(db_session)
        request_id = await svc.create_permission_request(
            "user-1", "agent-1", "t", "p", {})
        await svc.revoke_request(request_id)
        row = db_session.query(AgentRequestLog).filter(
            AgentRequestLog.request_id == request_id).first()
        assert row.revoked is True
        assert svc._pending_requests[request_id].is_set()

    @pytest.mark.asyncio
    async def test_revoke_request_unknown(self, db_session):
        svc = self._svc(db_session)
        await svc.revoke_request("missing")

    @pytest.mark.asyncio
    async def test_create_audit_exception(self, db_session):
        svc = self._svc(db_session)
        with patch.object(db_session, "commit",
                          side_effect=RuntimeError("db down")):
            await svc._create_audit("a1", "u1", "r1", "action")

    def test_get_agent_request_manager_factory(self, db_session):
        from core.agent_request_manager import get_agent_request_manager
        svc = get_agent_request_manager(db_session)
        assert svc.db is db_session


def _make_agent(db_session, agent_id):
    from core.models import AgentRegistry
    agent = AgentRegistry(
        id=agent_id, name=f"Agent {agent_id}", category="Ops",
        module_path="m", class_name="c")
    db_session.add(agent)
    db_session.commit()
    return agent


def _coord_manager_mock():
    manager = Mock()
    manager.AGENT_HANDOFF = "agent:handoff"
    manager.AGENT_COORDINATION_RESPONSE = "agent:coordination:response"
    manager.AGENT_ACTION_COMPLETE = "agent:action:complete"
    manager.AGENT_JOIN_CANVAS = "agent:join"
    manager.AGENT_LEAVE_CANVAS = "agent:leave"
    manager.broadcast_event = AsyncMock()
    return manager


class TestAgentHandoffProtocol:
    def test_validate_payload_no_schema(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        assert protocol.validate_handoff_payload({}, None) is True

    def test_validate_payload_valid(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        schema = {"type": "object", "required": ["task"]}
        assert protocol.validate_handoff_payload({"task": "x"}, schema) is True

    def test_validate_payload_invalid(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        schema = {"type": "object", "required": ["task"]}
        assert protocol.validate_handoff_payload({"nope": 1}, schema) is False

    def test_validate_payload_import_error_fallback(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        with patch.dict(sys.modules, {"jsonschema": None}):
            assert protocol.validate_handoff_payload({"task": 1},
                                                     {"required": ["task"]}) is True
            assert protocol.validate_handoff_payload({},
                                                     {"required": ["task"]}) is False

    @pytest.mark.asyncio
    async def test_initiate_handoff_invalid_agents(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        with pytest.raises(ValueError):
            await protocol.initiate_handoff(
                "missing-a", "missing-b", "canvas-1", "tenant-1", {}, "because")

    @pytest.mark.asyncio
    async def test_initiate_handoff_invalid_canvas(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        from core.models import AgentRegistry
        db_session.add_all([
            AgentRegistry(id="a1", name="A", category="Ops", module_path="m", class_name="c"),
            AgentRegistry(id="a2", name="B", category="Ops", module_path="m", class_name="c"),
        ])
        db_session.commit()
        protocol = AgentHandoffProtocol(db_session)
        with pytest.raises(ValueError):
            await protocol.initiate_handoff("a1", "a2", "canvas-1", "tenant-1", {}, "because")

    @pytest.mark.asyncio
    async def test_initiate_handoff_schema_mismatch(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        from core.models import AgentRegistry, Canvas, Tenant
        db_session.add_all([
            Tenant(id="tenant-1", name="T", subdomain="t1"),
            AgentRegistry(id="a1", name="A", category="Ops", module_path="m", class_name="c"),
            AgentRegistry(id="a2", name="B", category="Ops", module_path="m", class_name="c"),
        ])
        db_session.add(Canvas(id="canvas-1", tenant_id="tenant-1", created_by="user-1", name="Test Canvas"))
        db_session.commit()
        protocol = AgentHandoffProtocol(db_session)
        with pytest.raises(ValueError):
            await protocol.initiate_handoff(
                "a1", "a2", "canvas-1", "tenant-1", {},
                "because", input_schema={"required": ["task"]})

    @pytest.mark.asyncio
    async def test_initiate_handoff_success(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        from core.models import AgentRegistry, Canvas, Tenant, AgentHandoff
        db_session.add_all([
            Tenant(id="tenant-1", name="T", subdomain="t1"),
            AgentRegistry(id="a1", name="Alpha", category="Ops", module_path="m", class_name="c"),
            AgentRegistry(id="a2", name="Beta", category="Finance", module_path="m", class_name="c"),
        ])
        db_session.add(Canvas(id="canvas-1", tenant_id="tenant-1", created_by="user-1", name="Test Canvas"))
        db_session.commit()
        protocol = AgentHandoffProtocol(db_session)
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            result = await protocol.initiate_handoff(
                "a1", "a2", "canvas-1", "tenant-1", {"task": "x"}, "handoff please",
                initiated_by="user-1")
        assert result["status"] == "pending"
        row = db_session.query(AgentHandoff).filter(
            AgentHandoff.id == result["handoff_id"]).first()
        assert row.status == "pending"
        assert row.reason == "handoff please"
        manager.broadcast_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_accept_handoff(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        from core.models import AgentHandoff
        db_session.add(AgentHandoff(
            id="h1", from_agent_id="a1", to_agent_id="a2", canvas_id="canvas-1",
            tenant_id="tenant-1", context={}, status="pending"))
        db_session.commit()
        protocol = AgentHandoffProtocol(db_session)
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            result = await protocol.accept_handoff("h1", "a2", "tenant-1")
        assert result["status"] == "accepted"
        row = db_session.query(AgentHandoff).filter(AgentHandoff.id == "h1").first()
        assert row.status == "accepted"
        assert row.responded_at is not None

    @pytest.mark.asyncio
    async def test_accept_handoff_not_found(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        with pytest.raises(ValueError):
            await protocol.accept_handoff("missing", "a2", "tenant-1")

    @pytest.mark.asyncio
    async def test_accept_handoff_unauthorized(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        from core.models import AgentHandoff
        db_session.add(AgentHandoff(
            id="h1", from_agent_id="a1", to_agent_id="a2", canvas_id="canvas-1",
            tenant_id="tenant-1", context={}, status="pending"))
        db_session.commit()
        protocol = AgentHandoffProtocol(db_session)
        with pytest.raises(ValueError):
            await protocol.accept_handoff("h1", "intruder", "tenant-1")

    @pytest.mark.asyncio
    async def test_reject_handoff(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        from core.models import AgentHandoff
        db_session.add(AgentHandoff(
            id="h1", from_agent_id="a1", to_agent_id="a2", canvas_id="canvas-1",
            tenant_id="tenant-1", context={}, status="pending"))
        db_session.commit()
        protocol = AgentHandoffProtocol(db_session)
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            result = await protocol.reject_handoff("h1", "a2", "tenant-1", reason="busy")
        assert result["status"] == "rejected"
        row = db_session.query(AgentHandoff).filter(AgentHandoff.id == "h1").first()
        assert row.status == "rejected"
        assert row.rejection_reason == "busy"

    @pytest.mark.asyncio
    async def test_reject_handoff_not_found(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        with pytest.raises(ValueError):
            await protocol.reject_handoff("missing", "a2", "tenant-1")

    @pytest.mark.asyncio
    async def test_complete_handoff(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        from core.models import AgentHandoff
        db_session.add(AgentHandoff(
            id="h1", from_agent_id="a1", to_agent_id="a2", canvas_id="canvas-1",
            tenant_id="tenant-1", context={}, status="accepted"))
        db_session.commit()
        protocol = AgentHandoffProtocol(db_session)
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            result = await protocol.complete_handoff("h1", {"out": 1}, "tenant-1")
        assert result["status"] == "completed"
        row = db_session.query(AgentHandoff).filter(AgentHandoff.id == "h1").first()
        assert row.status == "completed"
        assert row.result == {"out": 1}

    @pytest.mark.asyncio
    async def test_complete_handoff_not_found(self, db_session):
        from core.agent_coordination import AgentHandoffProtocol
        protocol = AgentHandoffProtocol(db_session)
        with pytest.raises(ValueError):
            await protocol.complete_handoff("missing", {}, "tenant-1")


class TestMultiAgentCanvasService:
    def _svc(self, db_session):
        from core.agent_coordination import MultiAgentCanvasService
        return MultiAgentCanvasService(db_session)

    def _setup(self, db_session):
        from core.models import AgentRegistry, Canvas, Tenant
        db_session.add_all([
            Tenant(id="tenant-1", name="T", subdomain="t1"),
            AgentRegistry(id="a1", name="Alpha", category="Ops", module_path="m", class_name="c"),
        ])
        db_session.add(Canvas(id="canvas-1", tenant_id="tenant-1", created_by="user-1", name="Test Canvas"))
        db_session.commit()

    @pytest.mark.asyncio
    async def test_add_agent_invalid(self, db_session):
        svc = self._svc(db_session)
        with pytest.raises(ValueError):
            await svc.add_agent_to_canvas("missing", "canvas-1", "tenant-1")

    @pytest.mark.asyncio
    async def test_add_agent_success(self, db_session):
        from core.models import AgentCanvasPresence
        self._setup(db_session)
        svc = self._svc(db_session)
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            result = await svc.add_agent_to_canvas("a1", "canvas-1", "tenant-1", role="reviewer")
        assert result["status"] == "joined"
        assert result["role"] == "reviewer"
        row = db_session.query(AgentCanvasPresence).first()
        assert row.status == "active"
        assert row.role == "reviewer"

    @pytest.mark.asyncio
    async def test_add_agent_already_present(self, db_session):
        from core.models import AgentCanvasPresence
        self._setup(db_session)
        db_session.add(AgentCanvasPresence(
            agent_id="a1", canvas_id="canvas-1", tenant_id="tenant-1",
            role="collaborator", status="active"))
        db_session.commit()
        svc = self._svc(db_session)
        result = await svc.add_agent_to_canvas("a1", "canvas-1", "tenant-1")
        assert result["status"] == "already_present"

    @pytest.mark.asyncio
    async def test_remove_agent_not_present(self, db_session):
        svc = self._svc(db_session)
        result = await svc.remove_agent_from_canvas("a1", "canvas-1", "tenant-1")
        assert result["status"] == "not_present"

    @pytest.mark.asyncio
    async def test_remove_agent_success(self, db_session):
        from core.models import AgentCanvasPresence
        self._setup(db_session)
        db_session.add(AgentCanvasPresence(
            agent_id="a1", canvas_id="canvas-1", tenant_id="tenant-1",
            role="collaborator", status="active"))
        db_session.commit()
        svc = self._svc(db_session)
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            result = await svc.remove_agent_from_canvas("a1", "canvas-1", "tenant-1")
        assert result["status"] == "removed"
        row = db_session.query(AgentCanvasPresence).first()
        assert row.status == "left"
        assert row.left_at is not None

    @pytest.mark.asyncio
    async def test_coordinate_sequential(self, db_session):
        svc = self._svc(db_session)
        result = await svc.coordinate_agents(
            "canvas-1", "tenant-1", "task", ["a1", "a2"])
        assert result["coordination_type"] == "sequential"

    @pytest.mark.asyncio
    async def test_coordinate_diverse_strategy(self, db_session):
        from core import agent_coordination as ac
        from core.models import AgentCanvasPresence
        self._setup(db_session)
        strategy_service = Mock()
        strategy = Mock()
        strategy.id = "strat-1"
        strategy_service.initiate_strategy = Mock(return_value=strategy)
        partner = Mock()
        partner.id = "a1"
        strategy_service.recruit_diverse_partner = Mock(
            side_effect=lambda sid, spec: partner if spec == "finance" else None)
        svc = self._svc(db_session)
        with patch.object(ac, "CoordinatedStrategyService", return_value=strategy_service):
            result = await svc.coordinate_agents(
                "canvas-1", "tenant-1", "do finance things",
                ["finance", "ops"], coordination_strategy="coordinated_strategy")
        assert result["status"] == "negotiation_active"
        assert result["strategy_id"] == "strat-1"
        assert len(result["recruited_partners"]) == 1
        assert db_session.query(AgentCanvasPresence).count() == 1

    @pytest.mark.asyncio
    async def test_coordinate_dynamic_import_fails_falls_back(self, db_session):
        svc = self._svc(db_session)
        with patch.dict(sys.modules, {"core.dytopo_router": None}):
            result = await svc.coordinate_agents(
                "canvas-1", "tenant-1", "task", ["a1"], coordination_strategy="dynamic")
        assert result["coordination_type"] == "sequential"

    @pytest.mark.asyncio
    async def test_coordinate_dynamic_flag_off_falls_back(self, db_session):
        fake_dytopo = MagicMock()
        fake_dytopo.DYTOPO_ROUTING_ENABLED = False
        svc = self._svc(db_session)
        with patch.dict(sys.modules, {"core.dytopo_router": fake_dytopo}):
            result = await svc.coordinate_agents(
                "canvas-1", "tenant-1", "task", ["a1"], coordination_strategy="dynamic")
        assert result["coordination_type"] == "sequential"

    @pytest.mark.asyncio
    async def test_coordinate_dynamic_success(self, db_session):
        fake_dytopo = MagicMock()
        fake_dytopo.DYTOPO_ROUTING_ENABLED = True
        fake_dytopo.DyTopoRouter = Mock
        router = Mock()
        router.compute_round_topology = AsyncMock(return_value={"round": 1})
        fake_dytopo.DyTopoRouter = Mock(return_value=router)
        self._setup(db_session)
        svc = self._svc(db_session)
        with patch.dict(sys.modules, {"core.dytopo_router": fake_dytopo}):
            result = await svc.coordinate_agents(
                "canvas-1", "tenant-1", "task", ["a1"], coordination_strategy="dynamic")
        assert result["coordination_type"] == "dynamic"
        assert result["topology"] == {"round": 1}

    @pytest.mark.asyncio
    async def test_coordinate_unsupported_strategy(self, db_session):
        svc = self._svc(db_session)
        with pytest.raises(ValueError):
            await svc.coordinate_agents(
                "canvas-1", "tenant-1", "task", ["a1"], coordination_strategy="bogus")


class TestHandleAgentHandoff:
    @pytest.mark.asyncio
    async def test_missing_fields(self, db_session):
        from core.agent_coordination import handle_agent_handoff
        await handle_agent_handoff("room-1", {}, Mock(id="user-1"), "tenant-1", db_session)

    @pytest.mark.asyncio
    async def test_success(self, db_session):
        from core.agent_coordination import handle_agent_handoff
        from core.models import AgentRegistry, Canvas, Tenant
        db_session.add_all([
            Tenant(id="tenant-1", name="T", subdomain="t1"),
            AgentRegistry(id="a1", name="A", category="Ops", module_path="m", class_name="c"),
            AgentRegistry(id="a2", name="B", category="Ops", module_path="m", class_name="c"),
        ])
        db_session.add(Canvas(id="canvas-1", tenant_id="tenant-1", created_by="user-1", name="Test Canvas"))
        db_session.commit()
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            await handle_agent_handoff(
                "room-1",
                {"from_agent": "a1", "to_agent": "a2", "canvas_id": "canvas-1"},
                Mock(id="user-1"), "tenant-1", db_session)

    @pytest.mark.asyncio
    async def test_exception_logged(self, db_session):
        from core.agent_coordination import handle_agent_handoff
        manager = _coord_manager_mock()
        with patch("core.websockets.get_connection_manager", return_value=manager):
            await handle_agent_handoff(
                "room-1",
                {"from_agent": "a1", "to_agent": "a2", "canvas_id": "canvas-1"},
                Mock(id="user-1"), "tenant-1", db_session)


# ============================================================================
# Agent integration gateway
# ============================================================================

class _FakeSessionCM:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


def _session_cm(session):
    return _FakeSessionCM(session)


class FakeService:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    async def send_message(self, *a, **k):
        self.calls.append(("send_message", a, k))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    async def send_intelligent_message(self, *a, **k):
        self.calls.append(("send_intelligent_message", a, k))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result if isinstance(self.result, dict) else {"success": self.result}

    async def get_ad_insights(self, *a, **k):
        self.calls.append(("get_ad_insights", a, k))
        return self.result

    async def get_campaign_performance(self, *a, **k):
        self.calls.append(("get_campaign_performance", a, k))
        return self.result

    async def update_inventory(self, *a, **k):
        self.calls.append(("update_inventory", a, k))
        return self.result


class TestAgentIntegrationGateway:
    @pytest.fixture(autouse=True)
    def _no_governance_pause(self):
        # governance_engine.is_external_contact misuses get_db_session()
        # (returns _GeneratorContextManager, not a Session) -> crash on
        # email recipients. Patch it out; the pause path is covered by
        # test_send_message_governance_pause.
        with patch("core.agent_integration_gateway.contact_governance") as gov:
            gov.is_external_contact = Mock(return_value=False)
            yield gov

    def _gateway(self):
        import core.agent_integration_gateway as g
        gateway = g.AgentIntegrationGateway()
        return gateway, g

    @pytest.mark.asyncio
    async def test_unsupported_action(self):
        gateway, g = self._gateway()
        result = await gateway.execute_action(g.ActionType.SYNC_DATA, "x", {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_send_message_meta_unavailable(self):
        gateway, g = self._gateway()
        with patch.object(g, "meta_business_service", None):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "meta", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_send_message_meta_success(self):
        gateway, g = self._gateway()
        fake = FakeService(True)
        with patch.object(g, "meta_business_service", fake):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "meta",
                {"recipient_id": "r", "content": "hi", "platform": "instagram"})
        assert result["status"] == "success"
        assert fake.calls[0][1][0].value == "instagram"

    @pytest.mark.asyncio
    async def test_send_message_meta_failed(self):
        gateway, g = self._gateway()
        with patch.object(g, "meta_business_service", FakeService(False)):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "meta", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_send_message_whatsapp(self):
        gateway, g = self._gateway()
        fake = FakeService({"success": True})
        with patch.object(g, "atom_whatsapp_integration", fake):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "whatsapp",
                {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"
        fake = FakeService({"success": False, "error": "blocked"})
        with patch.object(g, "atom_whatsapp_integration", fake):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "whatsapp",
                {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"
        assert result["error"] == "blocked"

    @pytest.mark.asyncio
    async def test_send_message_agent_route(self):
        gateway, g = self._gateway()
        bridge = Mock()
        bridge.process_incoming_message = AsyncMock(return_value={"status": "ok"})
        with patch.dict(sys.modules,
                        {"integrations.universal_webhook_bridge": MagicMock(
                            universal_webhook_bridge=bridge)}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "agent",
                {"recipient_id": "r", "content": "hi", "sender_agent_id": "agent-9"})
        assert result == {"status": "ok"}
        args = bridge.process_incoming_message.await_args.args
        assert args[1]["agent_id"] == "agent-9"

    @pytest.mark.asyncio
    async def test_send_message_discord(self):
        gateway, g = self._gateway()
        with patch.object(g, "atom_discord_integration", FakeService(True)):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "discord",
                {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"
        with patch.object(g, "atom_discord_integration", FakeService(False)):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "discord",
                {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_send_message_teams(self):
        gateway, g = self._gateway()
        with patch.object(g, "teams_enhanced_service", None):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "teams", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"
        with patch.object(g, "teams_enhanced_service", FakeService(True)):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "teams",
                {"recipient_id": "r", "content": "hi", "thread_ts": "t1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_message_telegram(self):
        gateway, g = self._gateway()
        with patch.object(g, "atom_telegram_integration", FakeService({"success": True})):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "telegram", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_message_google_chat(self):
        gateway, g = self._gateway()
        with patch.object(g, "google_chat_enhanced_service", None):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "google_chat", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"
        with patch.object(g, "google_chat_enhanced_service", FakeService(True)):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "google_chat",
                {"recipient_id": "r", "content": "hi", "thread_ts": "t"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_message_slack(self):
        gateway, g = self._gateway()
        with patch.object(g, "slack_enhanced_service", None):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "slack",
                {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"
        slack = FakeService({"ok": True})
        with patch.object(g, "slack_enhanced_service", slack):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "slack",
                {"recipient_id": "r", "content": "hi", "workspace_id": "w", "thread_ts": "t"})
        assert result["status"] == "success"
        assert slack.calls[0][2]["workspace_id"] == "w"
        with patch.object(g, "slack_enhanced_service", FakeService({"ok": False, "error": "e"})):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "slack", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_send_message_twilio(self):
        gateway, g = self._gateway()
        twilio = MagicMock()
        twilio.send_sms = AsyncMock(return_value=True)
        with patch.dict(sys.modules,
                        {"integrations.twilio_service": MagicMock(twilio_service=twilio)}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "twilio", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_message_matrix_import_error(self):
        gateway, g = self._gateway()
        with patch.dict(sys.modules, {"integrations.matrix_service": None}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "matrix", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_send_message_matrix_success(self):
        gateway, g = self._gateway()
        matrix = MagicMock()
        matrix.send_message = AsyncMock(return_value=True)
        with patch.dict(sys.modules,
                        {"integrations.matrix_service": MagicMock(matrix_service=matrix)}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "matrix", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_message_messenger_import_error(self):
        gateway, g = self._gateway()
        with patch.dict(sys.modules, {"integrations.messenger_service": None}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "messenger", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_send_message_line_signal(self):
        gateway, g = self._gateway()
        line = MagicMock()
        line.send_message = AsyncMock(return_value=True)
        with patch.dict(sys.modules,
                        {"integrations.line_service": MagicMock(line_service=line)}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "line", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"
        with patch.dict(sys.modules, {"integrations.line_service": None}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "line", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"
        signal = MagicMock()
        signal.send_message = AsyncMock(return_value=True)
        with patch.dict(sys.modules,
                        {"integrations.signal_service": MagicMock(signal_service=signal)}):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "signal", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_message_openclaw(self):
        gateway, g = self._gateway()
        with patch.object(g, "openclaw_service", None):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "openclaw", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "failed"
        openclaw = FakeService({"status": "sent"})
        with patch.object(g, "openclaw_service", openclaw):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "openclaw",
                {"recipient_id": "r", "content": "hi", "thread_ts": "t"})
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_message_legacy_fallback(self):
        gateway, g = self._gateway()
        result = await gateway.execute_action(
            g.ActionType.SEND_MESSAGE, "carrier_pigeon", {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "success"
        assert "legacy" in result["note"]

    @pytest.mark.asyncio
    async def test_send_message_governance_pause(self, _no_governance_pause):
        gateway, g = self._gateway()
        governance = _no_governance_pause
        governance.is_external_contact = Mock(return_value=True)
        governance.should_require_approval = AsyncMock(return_value=True)
        governance.request_approval = AsyncMock(return_value="hitl-1")
        with patch.object(g, "atom_whatsapp_integration", FakeService({"success": True})):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "whatsapp",
                {"recipient_id": "r", "content": "hi", "workspace_id": "w1"})
        assert result["status"] == "waiting_approval"
        assert result["hitl_id"] == "hitl-1"

    @pytest.mark.asyncio
    async def test_update_record_inventory(self):
        gateway, g = self._gateway()
        ecommerce = FakeService(True)
        with patch.object(g, "ecommerce_service", ecommerce):
            result = await gateway.execute_action(
                g.ActionType.UPDATE_RECORD, "amazon", {"record_id": "sku-1", "data": {"quantity": 5}})
        assert result["status"] == "success"
        assert ecommerce.calls[0][0] == "update_inventory"

    @pytest.mark.asyncio
    async def test_update_record_generic(self):
        gateway, g = self._gateway()
        result = await gateway.execute_action(
            g.ActionType.UPDATE_RECORD, "crm", {"record_id": "r1", "data": {"x": 1}})
        assert result["status"] == "success"
        assert "r1" in result["note"]

    @pytest.mark.asyncio
    async def test_fetch_insights_meta(self):
        gateway, g = self._gateway()
        with patch.object(g, "meta_business_service", None):
            result = await gateway.execute_action(
                g.ActionType.FETCH_INSIGHTS, "meta", {"account_id": "a1"})
        assert result["status"] == "failed"
        fake = FakeService({"ads": []})
        with patch.object(g, "meta_business_service", fake):
            result = await gateway.execute_action(
                g.ActionType.FETCH_INSIGHTS, "meta", {"account_id": "a1"})
        assert result["status"] == "success"
        assert result["data"] == {"ads": []}

    @pytest.mark.asyncio
    async def test_fetch_insights_marketing(self):
        gateway, g = self._gateway()
        with patch.object(g, "marketing_service", None):
            result = await gateway.execute_action(
                g.ActionType.FETCH_INSIGHTS, "google_ads", {})
        assert result["status"] == "failed"
        fake = FakeService({"perf": 1})
        with patch.object(g, "marketing_service", fake):
            result = await gateway.execute_action(
                g.ActionType.FETCH_INSIGHTS, "tiktok_ads", {})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_fetch_insights_no_provider(self):
        gateway, g = self._gateway()
        result = await gateway.execute_action(
            g.ActionType.FETCH_INSIGHTS, "yahoo", {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_fetch_logic(self):
        gateway, g = self._gateway()
        result = await gateway.execute_action(
            g.ActionType.FETCH_LOGIC, "docs", {"query": "discount", "workspace_id": "w"})
        assert result["status"] == "success"
        assert "discount" in result["logic"][0]

    @pytest.mark.asyncio
    async def test_fetch_formulas_with_results(self):
        gateway, g = self._gateway()
        manager = Mock()
        manager.search_formulas = Mock(return_value=[
            {"id": "f1", "name": "tax", "expression": "=A1*0.2",
             "domain": "finance", "use_case": "tax calc", "parameters": ["A1"]}])
        with patch("core.formula_memory.get_formula_manager", return_value=manager):
            result = await gateway.execute_action(
                g.ActionType.FETCH_FORMULAS, "x", {"query": "tax"})
        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["formulas"][0]["name"] == "tax"

    @pytest.mark.asyncio
    async def test_fetch_formulas_empty(self):
        gateway, g = self._gateway()
        manager = Mock()
        manager.search_formulas = Mock(return_value=[])
        with patch("core.formula_memory.get_formula_manager", return_value=manager):
            result = await gateway.execute_action(
                g.ActionType.FETCH_FORMULAS, "x", {"query": "nothing"})
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_fetch_formulas_error(self):
        gateway, g = self._gateway()
        with patch("core.formula_memory.get_formula_manager",
                   side_effect=RuntimeError("formula memory down")):
            result = await gateway.execute_action(
                g.ActionType.FETCH_FORMULAS, "x", {"query": "q"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_apply_formula_no_id(self):
        gateway, g = self._gateway()
        result = await gateway.execute_action(
            g.ActionType.APPLY_FORMULA, "x", {"inputs": {}})
        assert result["status"] == "error"
        assert "required" in result["message"]

    @pytest.mark.asyncio
    async def test_apply_formula_success(self):
        gateway, g = self._gateway()
        manager = Mock()
        manager.apply_formula = Mock(return_value={"success": True, "result": 42.0})
        manager.get_formula = Mock(return_value={"name": "tax"})
        world_model = Mock()
        world_model.record_formula_usage = AsyncMock()
        db_session_mock = Mock()
        governance = Mock()
        governance._update_confidence_score = Mock()
        with patch("core.formula_memory.get_formula_manager", return_value=manager), \
             patch("core.agent_world_model.WorldModelService", return_value=world_model), \
             patch("core.agent_governance_service.AgentGovernanceService",
                   return_value=governance), \
             patch("core.database.get_db_session",
                   return_value=_session_cm(db_session_mock)):
            result = await gateway.execute_action(
                g.ActionType.APPLY_FORMULA, "x",
                {"formula_id": "f1", "inputs": {"A1": 100}, "agent_id": "agent-1",
                 "agent_role": "finance", "workspace_id": "w"})
        assert result == {"success": True, "result": 42.0}
        world_model.record_formula_usage.assert_awaited_once()
        governance._update_confidence_score.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_formula_error(self):
        gateway, g = self._gateway()
        with patch("core.formula_memory.get_formula_manager",
                   side_effect=RuntimeError("mem down")):
            result = await gateway.execute_action(
                g.ActionType.APPLY_FORMULA, "x", {"formula_id": "f1"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_shopify_handlers_missing_credentials(self):
        gateway, g = self._gateway()
        for action, params in [
            (g.ActionType.SHOPIFY_GET_CUSTOMERS, {}),
            (g.ActionType.SHOPIFY_GET_ORDERS, {"access_token": "t"}),
            (g.ActionType.SHOPIFY_GET_PRODUCTS, {"shop": "s"}),
            (g.ActionType.SHOPIFY_CREATE_FULFILLMENT, {"access_token": "t", "shop": "s"}),
            (g.ActionType.SHOPIFY_GET_ANALYTICS, {"shop": "s"}),
            (g.ActionType.SHOPIFY_MANAGE_INVENTORY, {}),
        ]:
            result = await gateway.execute_action(action, "shopify", params)
            assert result["status"] == "error"
            assert "required" in result["message"]

    @pytest.mark.asyncio
    async def test_shopify_customers_branches(self):
        gateway, g = self._gateway()
        shopify = Mock()
        shopify.get_customer = AsyncMock(return_value={"id": 1})
        shopify.search_customers = AsyncMock(return_value=[{"id": 2}])
        shopify.get_customers = AsyncMock(return_value=[{"id": 3}])
        gateway.services["shopify"] = shopify
        base = {"access_token": "t", "shop": "s"}
        r1 = await gateway.execute_action(
            g.ActionType.SHOPIFY_GET_CUSTOMERS, "shopify", {**base, "customer_id": "c1"})
        assert r1["data"] == {"id": 1}
        r2 = await gateway.execute_action(
            g.ActionType.SHOPIFY_GET_CUSTOMERS, "shopify", {**base, "query": "joe"})
        assert r2["count"] == 1
        r3 = await gateway.execute_action(
            g.ActionType.SHOPIFY_GET_CUSTOMERS, "shopify", {**base, "limit": 5})
        assert r3["count"] == 1

    @pytest.mark.asyncio
    async def test_shopify_orders_products_analytics(self):
        gateway, g = self._gateway()
        shopify = Mock()
        shopify.get_orders = AsyncMock(return_value=[{"id": 1}])
        shopify.get_products = AsyncMock(return_value=[{"id": 2}])
        shopify.get_shop_analytics = AsyncMock(return_value={"revenue": 100})
        gateway.services["shopify"] = shopify
        base = {"access_token": "t", "shop": "s"}
        result = await gateway.execute_action(
            g.ActionType.SHOPIFY_GET_ORDERS, "shopify", base)
        assert result["count"] == 1
        result = await gateway.execute_action(
            g.ActionType.SHOPIFY_GET_PRODUCTS, "shopify", base)
        assert result["count"] == 1
        result = await gateway.execute_action(
            g.ActionType.SHOPIFY_GET_ANALYTICS, "shopify", base)
        assert result["data"]["revenue"] == 100

    @pytest.mark.asyncio
    async def test_shopify_fulfillment_and_inventory(self):
        gateway, g = self._gateway()
        shopify = Mock()
        shopify.create_fulfillment = AsyncMock(return_value={"id": "f1"})
        shopify.get_inventory_levels = AsyncMock(return_value=[{"qty": 1}])
        shopify.get_locations = AsyncMock(return_value=[{"id": "loc1"}])
        gateway.services["shopify"] = shopify
        base = {"access_token": "t", "shop": "s"}
        result = await gateway.execute_action(
            g.ActionType.SHOPIFY_CREATE_FULFILLMENT, "shopify",
            {**base, "order_id": "o1", "location_id": "l1",
             "tracking_number": "tn", "tracking_company": "ups"})
        assert result["status"] == "success"
        result = await gateway.execute_action(
            g.ActionType.SHOPIFY_MANAGE_INVENTORY, "shopify",
            {**base, "location_id": "l1"})
        assert result["inventory_count"] == 1
        assert result["location_count"] == 1

    @pytest.mark.asyncio
    async def test_shopify_error_path(self):
        gateway, g = self._gateway()
        shopify = Mock()
        shopify.get_customers = AsyncMock(side_effect=RuntimeError("shopify down"))
        gateway.services["shopify"] = shopify
        result = await gateway.execute_action(
            g.ActionType.SHOPIFY_GET_CUSTOMERS, "shopify",
            {"access_token": "t", "shop": "s"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_gateway_generic_exception(self):
        gateway, g = self._gateway()
        with patch.object(g, "atom_whatsapp_integration",
                          FakeService(RuntimeError("boom"))):
            result = await gateway.execute_action(
                g.ActionType.SEND_MESSAGE, "whatsapp",
                {"recipient_id": "r", "content": "hi"})
        assert result["status"] == "error"
