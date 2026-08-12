"""Tests for automated stage-router certification (consent + notification).

Covers: verdict logic, mode behavior (off/notify/approve/auto), the approval
queue + apply/reject flow, automatic revocation, and the status surface.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

import core.llm.stage_router_automation as auto


def arm(n: int, success_rate: float, avg_cost: float = 0.001) -> Dict[str, float]:
    return {"n": n, "success_rate": success_rate, "avg_cost": avg_cost}


def workload(eff: Dict[str, float], cap: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    return {"efficient": eff, "capable": cap}


class TestVerdict:
    def test_insufficient_arms_keeps_shadow(self) -> None:
        assert auto._verdict(workload(arm(5, 0.9), arm(5, 0.95))) == "keep-shadow"
        assert auto._verdict(workload(arm(40, 0.9), arm(5, 0.95))) == "keep-shadow"
        assert auto._verdict(workload(arm(5, 0.9), arm(40, 0.95))) == "keep-shadow"

    def test_certify_when_gain_clears_gap(self) -> None:
        assert (
            auto._verdict(workload(arm(40, 0.80), arm(35, 0.88)))
            == "certify"
        )

    def test_certify_blocked_by_cost_ratio(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MAX_COST_RATIO", 2.0)
        assert (
            auto._verdict(workload(arm(40, 0.80, 0.001), arm(35, 0.88, 0.05)))
            == "keep-shadow"
        )

    def test_revoke_on_regression(self) -> None:
        assert (
            auto._verdict(workload(arm(40, 0.90), arm(35, 0.80)))
            == "revoke"
        )

    def test_keep_shadow_without_verdict(self) -> None:
        assert (
            auto._verdict(workload(arm(40, 0.85), arm(35, 0.84)))
            == "keep-shadow"
        )


# ── Fake DB session ─────────────────────────────────────────────────────────


class FakeAgent:
    def __init__(self, agent_id: str, config: Optional[Dict] = None) -> None:
        self.id = agent_id
        self.configuration = config or {}


class FakeAction:
    def __init__(self, agent_id: str, verdict: str = "certify", state: str = "approval") -> None:
        self.id = f"action-{agent_id}"
        self.agent_id = agent_id
        self.verdict = verdict
        self.mode = "approve"
        self.state = state
        self.stats_json: Dict[str, Any] = {}
        self.created_at = None
        self.decided_at = None


class FakeDb:
    """Minimal session fake: agents by id, actions list, model-dispatched query."""

    def __init__(self, agents: Optional[Dict[str, FakeAgent]] = None, actions: Optional[List[FakeAction]] = None) -> None:
        self.agents = agents or {}
        self.actions = actions or []
        self.committed = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, row) -> None:
        if hasattr(row, "agent_id"):
            self.actions.append(row)

    def commit(self) -> None:
        self.committed += 1

    def query(self, model):
        return _Query(self, model)


class _Query:
    def __init__(self, db: FakeDb, model: Any) -> None:
        self.db = db
        self.model = model
        self._filters: List = []

    def filter(self, *args, **kwargs):  # noqa: A002
        self._filters.extend(args)
        return self

    def order_by(self, *args):
        return self

    def _state_filter(self) -> Optional[str]:
        import re

        for expr in self._filters:
            m = re.search(r"state\s*==\s*['\"]([a-z]+)['\"]", str(expr))
            if m:
                return m.group(1)
        return None

    def _target_id(self) -> Optional[str]:
        for expr in self._filters:
            try:
                return str(expr.right.value)
            except Exception:
                continue
        return None

    def first(self):
        model_name = self.model.__name__
        if model_name == "AgentRegistry":
            target = self._target_id()
            return self.db.agents.get(target) if target else None
        if model_name == "StageRouterAutomationAction":
            target = self._target_id()
            state = self._state_filter()
            matches = [
                a for a in self.db.actions
                if (target is None or a.agent_id == target)
                and (state is None or getattr(a, "state", None) == state)
            ]
            return matches[-1] if matches else None
        return None

    def all(self):
        model_name = self.model.__name__
        if model_name == "StageRouterAutomationAction":
            state = self._state_filter()
            return [
                a for a in self.db.actions
                if state is None or getattr(a, "state", None) == state
            ]
        return list(self.db.actions)


# ── Certification pass per mode ─────────────────────────────────────────────


class TestCertifyWorkloads:
    def _patch_db(self, monkeypatch, agents: Dict[str, FakeAgent], stats: Dict[str, Any]) -> FakeDb:
        db = FakeDb(agents=agents)
        monkeypatch.setattr(auto, "_workload_stats", lambda db_: stats)
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        return db

    def test_off_mode_is_noop(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "off")
        db = self._patch_db(
            monkeypatch,
            {"agent-1": FakeAgent("agent-1")},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        result = auto.certify_workloads(db)
        assert result == {"certified": [], "revoked": [], "queued": [], "notified": [], "kept": []}
        assert db.actions == []

    def test_approve_mode_queues_not_applies(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        agent = FakeAgent("agent-1")
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        result = auto.certify_workloads(db)
        assert result["queued"] == ["agent-1"]
        assert result["certified"] == []
        assert agent.configuration == {}  # not applied without consent
        assert any(a.state == "approval" for a in db.actions)

    def test_auto_mode_applies_immediately(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        agent = FakeAgent("agent-1")
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        result = auto.certify_workloads(db)
        assert result["certified"] == ["agent-1"]
        block = agent.configuration["stage_routing"]
        assert block["enforce"] is True
        assert block["auto_certified"] is True
        assert block.get("certified_at")

    def test_notify_mode_never_writes(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "notify")
        agent = FakeAgent("agent-1")
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        result = auto.certify_workloads(db)
        assert result["notified"] == ["agent-1"]
        assert result["certified"] == [] and result["queued"] == []
        assert agent.configuration == {}
        assert db.actions == []

    def test_revoke_applies_even_in_approve_mode(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        agent = FakeAgent("agent-1", {"stage_routing": {"enforce": True}})
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.9), arm(35, 0.78))},
        )
        result = auto.certify_workloads(db)
        assert result["revoked"] == ["agent-1"]
        assert agent.configuration["stage_routing"]["enforce"] is False
        assert agent.configuration["stage_routing"]["auto_revoked"] is True

    def test_missing_agent_kept(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        db = self._patch_db(
            monkeypatch,
            {},
            {"ghost-agent": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        result = auto.certify_workloads(db)
        assert result["kept"] == ["ghost-agent"]


# ── Approval management ─────────────────────────────────────────────────────


class TestApprovalFlow:
    def _db_with_pending(self, agent: FakeAgent) -> FakeDb:
        return FakeDb(
            agents={agent.id: agent},
            actions=[FakeAction(agent.id, state="approval")],
        )

    def test_approve_applies_enforce(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1")
        db = self._db_with_pending(agent)
        result = auto.apply_pending_decision(db, "agent-1", approve=True)
        assert result["applied"] is True
        assert agent.configuration["stage_routing"]["enforce"] is True
        assert db.actions[0].state == "applied"

    def test_reject_marks_rejected_config_untouched(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        agent = FakeAgent("agent-1")
        db = self._db_with_pending(agent)
        result = auto.apply_pending_decision(db, "agent-1", approve=False)
        assert result["applied"] is False
        assert result["state"] == "rejected"
        assert agent.configuration == {}
        assert db.actions[0].state == "rejected"

    def test_no_pending_returns_not_applied(self) -> None:
        db = FakeDb(agents={"agent-1": FakeAgent("agent-1")})
        result = auto.apply_pending_decision(db, "agent-1", approve=True)
        assert result["applied"] is False
        assert "no pending" in result["reason"]


# ── Run + status surfaces ───────────────────────────────────────────────────


class TestRunAndStatus:
    def test_run_disabled_in_off_mode(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "off")
        result = auto.run_auto_certification()
        assert result == {"enabled": False, "mode": "off"}

    def test_run_certification_updates_last_run(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "certify_workloads", lambda db: {
            "certified": [], "revoked": [], "queued": ["agent-1"], "notified": [], "kept": []
        })

        class FakeSessionCtx:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def commit(self_inner):
                pass

        monkeypatch.setattr("core.database.get_db_session", lambda: FakeSessionCtx())
        result = auto.run_auto_certification()
        assert result["enabled"] is True
        assert result["queued"] == ["agent-1"]
        assert auto._last_run["mode"] == "approve"
        assert auto._last_run["last_run"]

    def test_automation_status_shape(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        monkeypatch.setattr(auto, "_INTERVAL_MIN", 60.0)
        monkeypatch.setattr(auto, "pending_approvals", lambda db: [{"agent_id": "agent-1"}])

        class FakeSessionCtx:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

        monkeypatch.setattr("core.database.get_db_session", lambda: FakeSessionCtx())
        status = auto.get_automation_status()
        assert status["enabled"] is True
        assert status["mode"] == "approve"
        assert status["interval_min"] == 60.0
        assert status["pending_approvals"][0]["agent_id"] == "agent-1"
        assert "last_run" in status

    def test_set_automation_config_validates_mode(self) -> None:
        result = auto.set_automation_config(mode="AUTO", interval_min=30)
        assert result == {"mode": "auto", "interval_min": 30.0}
        result = auto.set_automation_config(mode="bogus")  # ignored
        assert result["mode"] == "auto"
        auto.set_automation_config(mode="approve", interval_min=60)  # restore


# ── Notification-overload guards (dedupe) ───────────────────────────────────


class TestNotificationDedupe:
    def _patch_db(self, monkeypatch, agents: Dict[str, FakeAgent], stats: Dict[str, Any]) -> FakeDb:
        db = FakeDb(agents=agents)
        monkeypatch.setattr(auto, "_workload_stats", lambda db_: stats)
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        return db

    def test_approve_mode_queues_once_across_passes(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        agent = FakeAgent("agent-1")
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        first = auto.certify_workloads(db)
        second = auto.certify_workloads(db)  # same verdict, next pass
        assert first["queued"] == ["agent-1"]
        assert second["queued"] == []
        assert second["kept"] == ["agent-1"]
        assert len([a for a in db.actions if a.state == "approval"]) == 1

    def test_auto_mode_applies_once_across_passes(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        agent = FakeAgent("agent-1")
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        first = auto.certify_workloads(db)
        second = auto.certify_workloads(db)
        assert first["certified"] == ["agent-1"]
        assert second["certified"] == []
        assert second["kept"] == ["agent-1"]
        assert len([a for a in db.actions if a.state == "applied"]) == 1

    def test_notify_mode_respects_cooldown(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "notify")
        monkeypatch.setattr(auto, "_NOTIFY_COOLDOWN_HOURS", 24.0)
        monkeypatch.setattr(auto, "_last_notified", {})  # clear module state
        agent = FakeAgent("agent-1")
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        first = auto.certify_workloads(db)
        second = auto.certify_workloads(db)  # within cooldown → no re-notify
        assert first["notified"] == ["agent-1"]
        assert second["notified"] == []
        assert second["kept"] == ["agent-1"]

        # cooldown expiry → the next pass may notify again
        monkeypatch.setattr(auto, "_last_notified", {})
        third = auto.certify_workloads(db)
        assert third["notified"] == ["agent-1"]

    def test_revoke_fires_once(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        agent = FakeAgent("agent-1", {"stage_routing": {"enforce": True}})
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.9), arm(35, 0.78))},
        )
        first = auto.certify_workloads(db)
        second = auto.certify_workloads(db)
        assert first["revoked"] == ["agent-1"]
        assert second["revoked"] == []
        assert second["kept"] == ["agent-1"]
        assert len([a for a in db.actions if a.state == "revoked"]) == 1

    def test_kept_revoke_audit_written_once(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        agent = FakeAgent("agent-1")  # already shadowed (no enforce)
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.9), arm(35, 0.78))},
        )
        auto.certify_workloads(db)
        auto.certify_workloads(db)
        assert len([a for a in db.actions if a.state == "revoked"]) == 1


class TestIntentRespect:
    def _patch_db(self, monkeypatch, agents: Dict[str, FakeAgent], stats: Dict[str, Any]) -> FakeDb:
        db = FakeDb(agents=agents)
        monkeypatch.setattr(auto, "_workload_stats", lambda db_: stats)
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        return db

    def test_auto_mode_never_overwrites_manual_opt_out(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        agent = FakeAgent("agent-1", {"stage_routing": {"enforce": False}})  # manual opt-out
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        result = auto.certify_workloads(db)
        assert result["certified"] == []
        assert result["kept"] == ["agent-1"]
        assert agent.configuration["stage_routing"]["enforce"] is False  # untouched

    def test_auto_mode_recertifies_after_auto_revoke_recovers(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "auto")
        # auto_revoked marker → not a manual opt-out → re-certification allowed
        agent = FakeAgent(
            "agent-1",
            {"stage_routing": {"enforce": False, "auto_revoked": True}},
        )
        db = self._patch_db(
            monkeypatch,
            {"agent-1": agent},
            {"agent-1": workload(arm(40, 0.8), arm(35, 0.88))},
        )
        result = auto.certify_workloads(db)
        assert result["certified"] == ["agent-1"]
        assert agent.configuration["stage_routing"]["enforce"] is True

    def test_rejection_suppresses_requeue_until_stats_change(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_MODE", "approve")
        agent = FakeAgent("agent-1")
        db = FakeDb(
            agents={"agent-1": agent},
            actions=[FakeAction("agent-1", state="rejected")],
        )
        unchanged_stats = workload(arm(40, 0.8), arm(35, 0.88))
        db.actions[0].stats_json = unchanged_stats  # same snapshot the pass re-computes
        monkeypatch.setattr(auto, "_workload_stats", lambda db_: {"agent-1": unchanged_stats})
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)
        result = auto.certify_workloads(db)
        assert result["queued"] == []  # user's rejection stands
        assert result["kept"] == ["agent-1"]

        # stats changed materially → the pass may ask again
        monkeypatch.setattr(auto, "_workload_stats", lambda db_: {
            "agent-1": workload(arm(120, 0.8), arm(110, 0.92)),
        })
        result = auto.certify_workloads(db)
        assert result["queued"] == ["agent-1"]
