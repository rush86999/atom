# -*- coding: utf-8 -*-
"""Coverage wave 97 — communication APIs + supervisor performance + audit logger.

Targets (gap-closure; other modules of the batch are already >=80% via
tests/test_covpush_intgr_c.py, w94, w96, w103, w108, w20, w55, w82a, govtrio,
w92 — see final report):
1. core/privsec/audit_logger.py (64% -> high)
2. core/supervisor_performance_service.py (83% -> high)
3. integrations/atom_communication_live_api.py (92% -> higher)

Plain pytest + unittest.mock; no network, no LLM, no real DB.
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest


def run(coro):
    return asyncio.run(coro)


# =========================================================================== #
# 1. core/privsec/audit_logger.py
# =========================================================================== #
import core.privsec.audit_logger as al
from core.privsec.audit_logger import (
    AuditLogger,
    get_audit_logger,
    log_media_action_async,
    log_smarthome_action_async,
)


@pytest.fixture()
def audit(tmp_path, monkeypatch):
    """Fresh AuditLogger singleton writing to a temp file."""
    log_file = tmp_path / "audit.log"
    # resolve module dynamically: sibling suites may reload core.privsec.audit_logger
    mod = sys.modules["core.privsec.audit_logger"]
    monkeypatch.setattr(mod, "AUDIT_LOG_PATH", str(log_file))
    monkeypatch.setattr(mod.AuditLogger, "_instance", None)
    monkeypatch.setattr(mod, "_audit_logger_instance", None)
    inst = mod.AuditLogger()
    inst._log_path = log_file
    inst._setup_file_handler()
    yield inst
    inst._audit_handler.close()
    logging.getLogger("atom.audit").handlers.clear()
    monkeypatch.setattr(mod.AuditLogger, "_instance", None)
    monkeypatch.setattr(mod, "_audit_logger_instance", None)


class TestAuditLogger:
    def test_singleton_identity_and_reinit_noop(self, audit):
        mod = sys.modules["core.privsec.audit_logger"]
        # second construction returns the same instance; __init__ early-returns
        assert mod.AuditLogger() is audit
        assert audit._initialized is True

    def test_get_audit_logger_singleton(self, audit):
        mod = sys.modules["core.privsec.audit_logger"]
        assert mod.get_audit_logger() is mod.get_audit_logger()
        assert type(mod.get_audit_logger()).__name__ == "AuditLogger"

    def test_log_smarthome_action(self, audit):
        audit.log_smarthome_action(
            user_id="u1", agent_id="a1", action="turn_on",
            service="hue", details={"light_id": "L1"}, result="success")
        entry = json.loads(audit._log_path.read_text().strip())
        assert entry["category"] == "smarthome"
        assert entry["service"] == "hue"
        assert entry["result"] == "success"
        assert entry["user_id"] == "u1" and entry["agent_id"] == "a1"

    def test_log_creative_action_merges_operation(self, audit):
        audit.log_creative_action(
            user_id="u1", agent_id=None, action="trim_video",
            operation="ffmpeg -ss 0", details={"input": "in.mp4"}, result="success")
        entry = json.loads(audit._log_path.read_text().strip())
        assert entry["category"] == "creative"
        assert entry["service"] == "ffmpeg"
        assert entry["details"]["operation"] == "ffmpeg -ss 0"
        assert entry["details"]["input"] == "in.mp4"

    def test_log_local_only_block_with_and_without_reason(self, audit):
        audit.log_local_only_block("u1", "a1", "spotify", "play_song", reason="local_only")
        audit.log_local_only_block("u2", None, "notion", "search_docs")
        lines = [json.loads(l) for l in audit._log_path.read_text().splitlines() if l.strip()]
        assert lines[0]["action"] == "blocked_play_song"
        assert lines[0]["result"] == "blocked"
        assert lines[0]["category"] == "local_only_block"
        assert lines[0]["details"]["reason"] == "local_only"
        assert "reason" not in lines[1]["details"]
        assert lines[1]["agent_id"] is None

    def test_get_user_audit_log_filters_limit_and_reverses(self, audit):
        for i in range(5):
            audit.log_media_action(
                user_id="uA" if i < 3 else "uB", agent_id=None,
                action=f"play_{i}", service="spotify", details={}, result="success")
        entries = audit.get_user_audit_log("uA", limit=2)
        assert len(entries) == 2
        # forward scan stops at limit, then reversed -> most recent of those first
        assert entries[0]["action"] == "play_1" and entries[1]["action"] == "play_0"
        assert audit.get_user_audit_log("nobody") == []

    def test_get_user_audit_log_malformed_lines_skipped(self, audit):
        with open(audit._log_path, "a") as f:
            f.write("not-json\n")
        audit.log_media_action(
            user_id="u1", agent_id=None, action="pause", service="sonos",
            details={}, result="success")
        entries = audit.get_user_audit_log("u1")
        assert len(entries) == 1 and entries[0]["action"] == "pause"

    def test_get_user_audit_log_file_missing(self, audit, tmp_path):
        audit._log_path = tmp_path / "missing.log"
        assert audit.get_user_audit_log("u1") == []

    def test_get_service_audit_log_filters_and_missing(self, audit, tmp_path):
        audit.log_media_action(
            user_id="u1", agent_id=None, action="play", service="spotify",
            details={}, result="success")
        audit.log_smarthome_action(
            user_id="u1", agent_id=None, action="turn_off", service="hue",
            details={}, result="success")
        entries = audit.get_service_audit_log("hue")
        assert len(entries) == 1 and entries[0]["service"] == "hue"
        audit._log_path = tmp_path / "missing.log"
        assert audit.get_service_audit_log("spotify") == []

    def test_get_service_audit_log_limit_and_malformed(self, audit):
        with open(audit._log_path, "a") as f:
            f.write("garbage\n")  # malformed first -> JSONDecodeError continue
        for i in range(4):
            audit.log_smarthome_action(
                user_id="u1", agent_id=None, action=f"act_{i}", service="hue",
                details={}, result="success")
        entries = audit.get_service_audit_log("hue", limit=2)
        assert len(entries) == 2
        assert entries[0]["action"] == "act_1" and entries[1]["action"] == "act_0"

    def test_async_wrappers(self, audit):
        run(log_media_action_async(
            user_id="u1", agent_id="a1", action="skip", service="spotify",
            details={}, result="success"))
        run(log_smarthome_action_async(
            user_id="u2", agent_id=None, action="dim", service="hue",
            details={}, result="success"))
        lines = [json.loads(l) for l in audit._log_path.read_text().splitlines() if l.strip()]
        assert [l["action"] for l in lines] == ["skip", "dim"]

    def test_rotate_recreates_handler_dedup(self, audit):
        # rotation path (mtime today -> no rotate) plus handler reset dedup
        audit.rotate_audit_logs()
        audit._setup_file_handler()
        audit.log_media_action(
            user_id="u1", agent_id=None, action="play", service="spotify",
            details={}, result="success")
        lines = [l for l in audit._log_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 1  # exactly once (no duplicate handlers)


# =========================================================================== #
# 2. core/supervisor_performance_service.py
# =========================================================================== #
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    InterventionOutcome,
    SupervisionSession,
    SupervisorPerformance,
)
from core.supervisor_performance_service import SupervisorPerformanceService


@pytest.fixture()
def sdb():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def _perf(db, supervisor_id="s-1", **kw):
    base = dict(
        supervisor_id=supervisor_id,
        confidence_score=0.5, competence_level="competent",
        learning_rate=0.0, performance_trend="stable",
        total_sessions_supervised=3, total_interventions=0,
        average_rating=4.0, total_ratings=0,
        rating_1_count=0, rating_2_count=0, rating_3_count=0,
        rating_4_count=0, rating_5_count=0,
        successful_interventions=0, failed_interventions=0,
        agents_promoted=0, agent_confidence_boosted=0.0,
        total_comments_given=0, total_upvotes_received=0,
        total_downvotes_received=0,
    )
    base.update(kw)
    p = SupervisorPerformance(**base)
    db.add(p)
    db.commit()
    return p


def _agent(db):
    a = AgentRegistry(
        id=f"agent-{uuid.uuid4().hex[:8]}", name="Helper", category="general",
        description="d", status=AgentStatus.SUPERVISED.value, confidence_score=0.75,
        module_path="core.agents.generic_agent", class_name="GenericAgent",
        workspace_id="ws-1",
    )
    db.add(a)
    db.commit()
    return a


def _session(db, agent, supervisor_id="s-1", rating=4, completed=None, started=None):
    s = SupervisionSession(
        agent_id=agent.id, agent_name=agent.name, workspace_id="ws-1",
        trigger_context={"trigger_type": "manual"}, status="completed",
        supervisor_id=supervisor_id, supervisor_rating=rating,
        completed_at=completed or datetime.now(timezone.utc),
        started_at=started or datetime.now(timezone.utc) - timedelta(minutes=5),
        duration_seconds=300,
    )
    db.add(s)
    db.commit()
    return s


def _outcome(db, session, outcome="success", assessed=None):
    o = InterventionOutcome(
        supervision_session_id=session.id,
        supervisor_id=session.supervisor_id, agent_id=session.agent_id,
        intervention_type="correct",
        intervention_timestamp=datetime.now(timezone.utc),
        assessed_at=assessed or datetime.now(timezone.utc),
        outcome=outcome,
    )
    db.add(o)
    db.commit()
    return o


class TestSupervisorMetrics:
    def test_metrics_empty_for_unknown_supervisor(self, sdb):
        svc = SupervisorPerformanceService(sdb)
        res = run(svc.get_supervisor_metrics("ghost"))
        assert res["overall"]["total_sessions"] == 0
        assert res["ratings"]["total"] == 0
        assert res["feedback"]["vote_ratio"] == 0.5

    def test_metrics_full(self, sdb):
        agent = _agent(sdb)
        _perf(sdb, total_upvotes_received=3, total_downvotes_received=1,
              rating_1_count=1, rating_2_count=0, rating_3_count=0,
              rating_4_count=2, rating_5_count=2)
        s1 = _session(sdb, agent)
        _outcome(sdb, s1, "success")
        _outcome(sdb, s1, "failure")
        svc = SupervisorPerformanceService(sdb)
        res = run(svc.get_supervisor_metrics("s-1"))
        assert res["interventions"]["total"] == 2
        assert res["interventions"]["success_rate"] == 0.5
        assert res["feedback"]["vote_ratio"] == 0.75
        assert res["ratings"]["distribution"][1] == 1
        assert res["learning"]["performance_trend"] == "stable"


class TestLeaderboard:
    def _setup(self, sdb):
        agent = _agent(sdb)
        _perf(sdb, "s-a", average_rating=3.0, confidence_score=0.9,
              total_sessions_supervised=7)
        _perf(sdb, "s-b", average_rating=None, confidence_score=0.2,
              total_sessions_supervised=2)
        _session(sdb, agent, supervisor_id="s-a")
        _session(sdb, agent, supervisor_id="s-b")
        return agent

    def test_average_rating_metric_handles_none(self, sdb):
        agent = self._setup(sdb)
        svc = SupervisorPerformanceService(sdb)
        ranked = run(svc.get_leaderboard(metric="average_rating"))
        assert ranked[0]["supervisor_id"] == "s-a"
        assert ranked[1]["score"] == 0  # None average_rating -> 0

    def test_confidence_and_total_sessions_and_unknown_metric(self, sdb):
        agent = self._setup(sdb)
        svc = SupervisorPerformanceService(sdb)
        assert run(svc.get_leaderboard(metric="confidence_score"))[0]["supervisor_id"] == "s-a"
        assert run(svc.get_leaderboard(metric="total_sessions"))[0]["total_sessions"] == 7
        assert all(r["score"] == 0 for r in run(svc.get_leaderboard(metric="bogus")))

    def test_success_rate_metric(self, sdb):
        agent = self._setup(sdb)
        svc = SupervisorPerformanceService(sdb)
        sa = sdb.query(SupervisionSession).filter_by(supervisor_id="s-a").first()
        sb = sdb.query(SupervisionSession).filter_by(supervisor_id="s-b").first()
        _outcome(sdb, sa, "success")
        _outcome(sdb, sa, "success")
        _outcome(sdb, sa, "failure")
        _outcome(sdb, sb, "failure")
        ranked = run(svc.get_leaderboard(metric="success_rate"))
        assert ranked[0]["supervisor_id"] == "s-a"
        assert ranked[0]["score"] == round(2 / 3, 3)
        assert ranked[1]["score"] == 0


class TestRecommendations:
    def _svc_with_metrics(self, sdb, metrics):
        svc = SupervisorPerformanceService(sdb)
        svc.get_supervisor_metrics = mock.AsyncMock(return_value=metrics)
        return svc

    def _metrics(self, **kw):
        m = {
            "overall": {"competence_level": "competent"},
            "interventions": {"total": 0, "success_rate": 0.0},
            "ratings": {"total": 0, "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}},
            "feedback": {"vote_ratio": 0.5},
            "learning": {"performance_trend": "stable"},
        }
        m.update(kw)
        return m

    def test_low_rating_imbalance(self, sdb):
        svc = self._svc_with_metrics(sdb, self._metrics(
            ratings={"total": 20, "distribution": {1: 10, 2: 5, 3: 0, 4: 2, 5: 1}}))
        recs = run(svc.get_performance_recommendations("s-1"))
        assert any("clearer guidance" in r for r in recs)

    def test_low_success_rate(self, sdb):
        svc = self._svc_with_metrics(sdb, self._metrics(
            interventions={"total": 20, "success_rate": 0.4}))
        recs = run(svc.get_performance_recommendations("s-1"))
        assert any("success rate" in r for r in recs)

    def test_high_success_rate(self, sdb):
        svc = self._svc_with_metrics(sdb, self._metrics(
            interventions={"total": 20, "success_rate": 0.95}))
        recs = run(svc.get_performance_recommendations("s-1"))
        assert any("Excellent" in r for r in recs)

    def test_vote_ratio_and_trends(self, sdb):
        svc = self._svc_with_metrics(sdb, self._metrics(
            feedback={"vote_ratio": 0.1},
            learning={"performance_trend": "declining"}))
        recs = run(svc.get_performance_recommendations("s-1"))
        assert any("downvotes" in r for r in recs)
        assert any("declining" in r for r in recs)

    def test_improving_trend_and_novice(self, sdb):
        svc = self._svc_with_metrics(sdb, self._metrics(
            learning={"performance_trend": "improving"},
            overall={"competence_level": "novice"},
            ratings={"total": 25, "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 25}}))
        recs = run(svc.get_performance_recommendations("s-1"))
        assert any("improving" in r for r in recs)
        assert any("training materials" in r for r in recs)


class TestInterventionTracking:
    def test_update_metrics_no_performance_row(self, sdb):
        agent = _agent(sdb)
        s = _session(sdb, agent, supervisor_id="ghost-sup")
        svc = SupervisorPerformanceService(sdb)
        run(svc._update_intervention_metrics("ghost-sup", "failure", False))

    def test_update_metrics_effective_and_not(self, sdb):
        agent = _agent(sdb)
        _session(sdb, agent)
        _perf(sdb, "s-1", confidence_score=0.99)
        svc = SupervisorPerformanceService(sdb)
        run(svc._update_intervention_metrics("s-1", "success", True))
        p = sdb.query(SupervisorPerformance).filter_by(supervisor_id="s-1").first()
        assert p.successful_interventions == 1
        assert p.confidence_score == 1.0  # min(1.0, 0.99 + 0.01)
        run(svc._update_intervention_metrics("s-1", "failure", False))
        p = sdb.query(SupervisorPerformance).filter_by(supervisor_id="s-1").first()
        assert p.failed_interventions == 1
        assert p.confidence_score == pytest.approx(0.98)

    def test_track_intervention_outcome_full(self, sdb):
        agent = _agent(sdb)
        _session(sdb, agent)
        _perf(sdb, "s-1")
        svc = SupervisorPerformanceService(sdb)
        rec = run(svc.track_intervention_outcome(
            supervision_session_id=sdb.query(SupervisionSession).first().id,
            intervention_type="guide",
            intervention_timestamp=datetime.now(timezone.utc),
            outcome="success", lesson_learned="be kind",
        ))
        assert rec.outcome == "success"
        p = sdb.query(SupervisorPerformance).filter_by(supervisor_id="s-1").first()
        assert p.successful_interventions == 1


    def test_track_intervention_missing_session(self, sdb):
        svc = SupervisorPerformanceService(sdb)
        with pytest.raises(ValueError):
            run(svc.track_intervention_outcome(
                supervision_session_id="nope",
                intervention_type="correct",
                intervention_timestamp=datetime.now(timezone.utc),
                outcome="success",
            ))


class TestSuccessRateAndCurve:
    def test_success_rate_no_outcomes(self, sdb):
        svc = SupervisorPerformanceService(sdb)
        assert run(svc.calculate_intervention_success_rate("s-1")) == 0.0

    def test_success_rate_with_outcomes(self, sdb):
        agent = _agent(sdb)
        s = _session(sdb, agent)
        _outcome(sdb, s, "success")
        _outcome(sdb, s, "failure")
        _outcome(sdb, s, "success")
        svc = SupervisorPerformanceService(sdb)
        assert run(svc.calculate_intervention_success_rate("s-1")) == pytest.approx(2 / 3)

    def _curve_sessions(self, sdb, agent, ratings):
        now = datetime.now(timezone.utc)
        for i, r in enumerate(ratings):
            _session(
                sdb, agent, rating=r,
                completed=now - timedelta(weeks=len(ratings) - i),
                started=now - timedelta(weeks=len(ratings) - i, minutes=30),
            )

    def test_curve_no_sessions(self, sdb):
        svc = SupervisorPerformanceService(sdb)
        res = run(svc.get_supervisor_learning_curve("ghost"))
        assert res["trend"] == "stable" and res["dates"] == []

    def test_curve_improving(self, sdb):
        agent = _agent(sdb)
        self._curve_sessions(sdb, agent, [1.0, 1.0, 1.0, 5.0, 5.0])
        _perf(sdb, "s-1", confidence_score=0.7)
        svc = SupervisorPerformanceService(sdb)
        res = run(svc.get_supervisor_learning_curve("s-1"))
        assert res["trend"] == "improving"
        assert res["confidence_scores"][0] == 0.7

    def test_curve_declining(self, sdb):
        agent = _agent(sdb)
        self._curve_sessions(sdb, agent, [5.0, 5.0, 5.0, 1.0, 1.0])
        svc = SupervisorPerformanceService(sdb)
        res = run(svc.get_supervisor_learning_curve("s-1"))
        assert res["trend"] == "declining"

    def test_curve_stable_short_series(self, sdb):
        agent = _agent(sdb)
        # only 2 weekly points -> trend defaults to stable
        self._curve_sessions(sdb, agent, [4.0, 4.5])
        svc = SupervisorPerformanceService(sdb)
        res = run(svc.get_supervisor_learning_curve("s-1"))
        assert res["trend"] == "stable" and len(res["dates"]) == 2

    def test_curve_stable_flat(self, sdb):
        agent = _agent(sdb)
        self._curve_sessions(sdb, agent, [3.0, 3.1, 3.0, 3.1, 3.0])
        svc = SupervisorPerformanceService(sdb)
        res = run(svc.get_supervisor_learning_curve("s-1"))
        assert res["trend"] == "stable"


# =========================================================================== #
# 3. integrations/atom_communication_live_api.py
# =========================================================================== #
import integrations.atom_communication_live_api as live
from integrations.atom_communication_live_api import (
    fetch_zoho_mail_recent,
    get_recent_contacts,
)


def _coro(result=None, error=None):
    if error is not None:
        return mock.AsyncMock(side_effect=error)
    return mock.AsyncMock(return_value=result)


class TestFetchZohoMailRecent:
    def test_unavailable_flag(self, monkeypatch):
        monkeypatch.setattr(live, "ZOHO_MAIL_AVAILABLE", False)
        assert run(fetch_zoho_mail_recent()) == []

    def test_missing_token(self, monkeypatch):
        monkeypatch.setattr(live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.delenv("ZOHO_CRM_ACCESS_TOKEN", raising=False)
        assert run(fetch_zoho_mail_recent()) == []

    def test_maps_messages(self, monkeypatch):
        monkeypatch.setattr(live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "tok")
        svc = mock.MagicMock()
        svc.get_recent_inbox = mock.AsyncMock(return_value=[
            {"messageId": "m1", "sender": "a@b.c", "subject": "Hi",
             "summary": "hello", "sentTimeInMS": 1700000000000, "status": "read"},
            {"messageId": "m2", "sender": "d@e.f", "subject": "S2",
             "summary": None, "status": "unread"},  # falls back to subject
        ])
        monkeypatch.setattr(live, "ZohoMailService", lambda: svc)
        msgs = run(fetch_zoho_mail_recent(limit=2))
        assert len(msgs) == 2
        assert msgs[0]["id"] == "zoho_m1"
        assert msgs[0]["provider"] == "zoho"
        assert msgs[0]["status"] == "read"
        assert msgs[1]["content"] == "S2"
        assert msgs[1]["status"] == "unread"

    def test_fetch_error_swallowed(self, monkeypatch):
        monkeypatch.setattr(live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "tok")
        svc = mock.MagicMock()
        svc.get_recent_inbox = mock.AsyncMock(side_effect=RuntimeError("zoho down"))
        monkeypatch.setattr(live, "ZohoMailService", lambda: svc)
        assert run(fetch_zoho_mail_recent()) == []


class TestRecentContacts:
    def _patch_all(self, monkeypatch, results=None, errors=None):
        errors = errors or {}
        results = results or {}
        monkeypatch.setattr(live, "SLACK_AVAILABLE", True)
        monkeypatch.setattr(live, "GMAIL_AVAILABLE", True)
        monkeypatch.setattr(live, "DISCORD_AVAILABLE", True)
        monkeypatch.setattr(live, "ZOHO_MAIL_AVAILABLE", True)
        monkeypatch.setattr(live, "M365_AVAILABLE", True)
        for name in ("fetch_slack_recent", "fetch_gmail_recent", "fetch_discord_recent",
                     "fetch_zoho_mail_recent", "fetch_outlook_recent", "fetch_teams_recent"):
            err = errors.get(name)
            res = results.get(name, [])
            m = _coro(error=err) if err else _coro(res)
            # NOTE: fetch_gmail_recent / fetch_discord_recent are referenced by
            # get_recent_contacts but NOT defined in the module (latent bug —
            # NameError is swallowed by the per-provider except). Install them
            # here with raising=False so the happy/error paths are exercisable.
            monkeypatch.setattr(live, name, m, raising=False)

    def test_all_providers_success(self, monkeypatch):
        self._patch_all(monkeypatch, results={
            "fetch_slack_recent": [{"sender": "alice"}],
            "fetch_gmail_recent": [{"sender": "bob@gmail.com"}],
            "fetch_discord_recent": [{"sender": "carl"}],
            "fetch_zoho_mail_recent": [{"sender": "dana@zoho.com"}],
            "fetch_outlook_recent": [{"sender": "eve@outlook.com"}],
            "fetch_teams_recent": [{"sender": "frank@teams.com"}],
        })
        res = run(get_recent_contacts(limit=10))
        providers = {c["name"]: c["provider"] for c in res["contacts"]}
        assert providers["alice"] == "slack"
        assert providers["bob@gmail.com"] == "gmail"
        assert providers["carl"] == "discord"
        assert providers["dana@zoho.com"] == "zoho"
        assert providers["eve@outlook.com"] == "outlook"
        assert providers["frank@teams.com"] == "teams"

    def test_provider_errors_isolated(self, monkeypatch):
        self._patch_all(monkeypatch, errors={
            "fetch_slack_recent": RuntimeError("slack down"),
            "fetch_gmail_recent": RuntimeError("gmail down"),
            "fetch_discord_recent": RuntimeError("discord down"),
            "fetch_zoho_mail_recent": RuntimeError("zoho down"),
            "fetch_outlook_recent": RuntimeError("outlook down"),
            "fetch_teams_recent": RuntimeError("teams down"),
        })
        res = run(get_recent_contacts())
        assert res == {"ok": True, "contacts": []}

    def test_bot_and_unknown_senders_skipped(self, monkeypatch):
        self._patch_all(monkeypatch, results={
            "fetch_slack_recent": [{"sender": "slackbot"}, {"sender": ""},
                                   {"sender": "SlackBot"}],
            "fetch_gmail_recent": [],
        })
        res = run(get_recent_contacts())
        assert res["contacts"] == []

    def test_limit_truncates_and_slack_online(self, monkeypatch):
        self._patch_all(monkeypatch, results={
            "fetch_slack_recent": [{"sender": f"user{i}"} for i in range(5)],
        })
        res = run(get_recent_contacts(limit=2))
        assert len(res["contacts"]) == 2
        assert res["contacts"][0]["status"] == "online"
