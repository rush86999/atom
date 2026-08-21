"""Tests for consent-gated fleet router automation.

Covers: verdict logic (collecting / blocked / enable / revoke), mode behavior
(off/notify/approve/auto), the approval queue + apply/reject flow, automatic
revocation, the resolved_fleet_enforce override (env kill-switch always wins),
and the status surface. Mirrors tests/unit/core/test_stage_router_automation.py.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pytest

import core.fleet_orchestration.fleet_router_automation as auto


class FakeAction:
    def __init__(
        self,
        workload_key: str = "__global__",
        verdict: str = "enable",
        mode: str = "approve",
        state: str = "approval",
        stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.id = f"action-{len(TestAutomation.actions)}"
        self.workload_key = workload_key
        self.verdict = verdict
        self.mode = mode
        self.state = state
        self.stats_json = stats or {}
        self.created_at = None
        self.decided_at = None


class TestAutomation:
    actions: List[Any] = []

    class FakeQuery:
        def __init__(self, owner: "TestAutomation", rows: List[Any]) -> None:
            self.owner = owner
            self.rows = list(rows)
            self._filters: List[Any] = []

        def filter(self, *args, **kwargs):  # noqa: A002
            self._filters.extend(args)
            return self

        def order_by(self, *args):
            return self

        def _state_filter(self) -> Optional[str]:
            for expr in self._filters:
                m = re.search(r"state\s*==\s*['\"]([a-z]+)['\"]", str(expr))
                if m:
                    return m.group(1)
            return None

        def _workload_filter(self) -> Optional[str]:
            for expr in self._filters:
                m = re.search(r"workload_key\s*==\s*['\"]([a-z_]+)['\"]", str(expr))
                if m:
                    return m.group(1)
            return None

        def all(self) -> List[Any]:
            return list(self.rows)

        def first(self) -> Optional[Any]:
            return self.rows[0] if self.rows else None

    class FakeDb:
        def __init__(self, owner: "TestAutomation") -> None:
            self.owner = owner

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def add(self, row: Any) -> None:
            row.id = f"action-{len(self.owner.actions)}"
            self.owner.actions.append(row)

        def flush(self) -> None:
            pass

        def commit(self) -> None:
            pass

        def query(self, model):  # noqa: A002
            return TestAutomation.FakeQuery(self.owner, self.owner.actions)

    @pytest.fixture(autouse=True)
    def _fresh(self, monkeypatch):
        TestAutomation.actions = []
        monkeypatch.setattr(auto, "_mode", "approve")
        monkeypatch.setattr(auto, "_last_notified", {})
        monkeypatch.setattr(auto, "_spawn_notification", lambda *a, **k: None)

    def _db(self) -> FakeDb:
        return self.FakeDb(self)

    def _seed(self, rows: List[Any]) -> None:
        TestAutomation.actions = rows


# ── Verdict logic ───────────────────────────────────────────────────────────


class TestVerdict(TestAutomation):
    def _stats(self, n: int, success_rate: Optional[float], recruit_attempts: int = 0, recruit_rate: Optional[float] = None) -> Dict[str, Any]:
        return {
            "workloads": {"wk": {"n": n, "success_rate": success_rate}},
            "recruitment": {
                "recruit_attempts": recruit_attempts,
                "recruit_success_rate": recruit_rate,
            },
        }

    def test_collecting_below_min_rows(self) -> None:
        db = self._db()
        verdict = auto._certify_verdict(db)
        # Empty db → no rows → collecting.
        assert verdict["verdict"] == "collecting"

    def test_blocked_on_unhealthy_recruitment(self) -> None:
        db = self._db()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._workload_stats",
                lambda db: {"wk": {"n": 40, "success_rate": 0.9}},
            )
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._aggregate_recruitment_health",
                lambda db: {"recruit_attempts": 12, "recruit_success_rate": 0.4},
            )
            verdict = auto._certify_verdict(db)
        assert verdict["verdict"] == "blocked"
        assert "recruit" in verdict["why"].lower()

    def test_revoke_on_baseline_regression(self) -> None:
        db = self._db()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._workload_stats",
                lambda db: {"wk": {"n": 25, "success_rate": 0.4}},
            )
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._aggregate_recruitment_health",
                lambda db: {"recruit_attempts": 20, "recruit_success_rate": 0.95},
            )
            verdict = auto._certify_verdict(db)
        assert verdict["verdict"] == "revoke"

    def test_collecting_when_baseline_below_floor(self) -> None:
        db = self._db()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._workload_stats",
                lambda db: {"wk": {"n": 40, "success_rate": 0.6}},
            )
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._aggregate_recruitment_health",
                lambda db: {"recruit_attempts": 20, "recruit_success_rate": 0.95},
            )
            verdict = auto._certify_verdict(db)
        assert verdict["verdict"] == "collecting"

    def test_enable_when_healthy(self) -> None:
        db = self._db()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._workload_stats",
                lambda db: {"wk": {"n": 40, "success_rate": 0.9}},
            )
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._aggregate_recruitment_health",
                lambda db: {"recruit_attempts": 20, "recruit_success_rate": 0.95},
            )
            verdict = auto._certify_verdict(db)
        assert verdict["verdict"] == "enable"


# ── Mode behavior ───────────────────────────────────────────────────────────


class TestModes(TestAutomation):
    _active_patches: list = []

    def teardown_method(self) -> None:
        while TestModes._active_patches:
            TestModes._active_patches.pop().undo()

    def _force_enable(self) -> None:
        # Patch via a restoring context: assigning directly on the module
        # leaked fake stats into every later test in the process (the
        # TestCalibrationStatus suite saw 40 phantom rows → "ready").
        import core.fleet_orchestration.fleet_routing_stats as fstats

        ctx = pytest.MonkeyPatch()
        ctx.setattr(
            fstats, "_workload_stats",
            lambda db: {"wk": {"n": 40, "success_rate": 0.9}},
        )
        ctx.setattr(
            fstats, "_aggregate_recruitment_health",
            lambda db: {"recruit_attempts": 20, "recruit_success_rate": 0.95},
        )
        # Stay patched for the caller's certify_fleet() call; restored in
        # teardown_method so nothing leaks to other test modules.
        TestModes._active_patches.append(ctx)

    def test_off_mode_is_noop(self) -> None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(auto, "_mode", "off")
            result = auto.certify_fleet(self._db())
        assert result["certified"] == [] and result["queued"] == []
        assert TestAutomation.actions == []

    def test_approve_mode_queues_approval(self) -> None:
        self._force_enable()
        result = auto.certify_fleet(self._db())
        assert result["queued"] == ["__global__"]
        assert TestAutomation.actions[-1].state == "approval"

    def test_approve_mode_dedupes_pending(self) -> None:
        self._force_enable()
        auto.certify_fleet(self._db())
        result = auto.certify_fleet(self._db())
        assert result["queued"] == [] and result["kept"] == ["__global__"]
        assert len(TestAutomation.actions) == 1

    def test_auto_mode_applies_immediately(self) -> None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(auto, "_mode", "auto")
            self._force_enable()
            result = auto.certify_fleet(self._db())
        assert result["certified"] == ["__global__"]
        assert TestAutomation.actions[-1].state == "applied"

    def test_revoke_applies_immediately_in_approve_mode(self) -> None:
        with pytest.MonkeyPatch.context() as mp:
            # mp.setattr (not bare assignment) — direct assignment leaked the
            # fake stats into every later test in the process.
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._workload_stats",
                lambda db: {"wk": {"n": 25, "success_rate": 0.4}},
            )
            mp.setattr(
                "core.fleet_orchestration.fleet_routing_stats._aggregate_recruitment_health",
                lambda db: {"recruit_attempts": 20, "recruit_success_rate": 0.95},
            )
            result = auto.certify_fleet(self._db())
        assert result["revoked"] == ["__global__"]
        assert TestAutomation.actions[-1].state == "revoked"

    def test_approval_apply_flips_override(self) -> None:
        self._force_enable()
        auto.certify_fleet(self._db())
        db = self._db()
        result = auto.apply_pending_decision(db, approve=True)
        assert result["applied"] is True
        assert auto.resolved_fleet_enforce(db=db) is True

    def test_approval_reject_then_unchanged_is_kept(self) -> None:
        self._force_enable()
        auto.certify_fleet(self._db())
        db = self._db()
        auto.apply_pending_decision(db, approve=False)
        # Same stats → user's "no" honored.
        result = auto.certify_fleet(db)
        assert result["queued"] == [] and result["kept"] == ["__global__"]

    def test_no_pending_approval_reports_reason(self) -> None:
        result = auto.apply_pending_decision(self._db(), approve=True)
        assert result["applied"] is False
        assert "no pending" in result["reason"]


# ── Resolved enforce override ───────────────────────────────────────────────


class TestResolvedEnforce(TestAutomation):
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        monkeypatch.delenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", raising=False)

    def _patch_db(self, monkeypatch, db) -> None:
        monkeypatch.setattr("core.database.SessionLocal", lambda: db)

    def test_env_kill_switch_wins(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
        assert auto.resolved_fleet_enforce() is True

    def test_applied_enable_override_enforces(self, monkeypatch) -> None:
        self._seed([FakeAction(verdict="enable", state="applied")])
        self._patch_db(monkeypatch, self._db())
        assert auto.resolved_fleet_enforce() is True

    def test_revoked_row_means_shadow(self, monkeypatch) -> None:
        self._seed([FakeAction(verdict="revoke", state="revoked")])
        self._patch_db(monkeypatch, self._db())
        assert auto.resolved_fleet_enforce() is False

    def test_approval_row_does_not_enforce(self, monkeypatch) -> None:
        self._seed([FakeAction(verdict="enable", state="approval")])
        self._patch_db(monkeypatch, self._db())
        assert auto.resolved_fleet_enforce() is False

    def test_empty_db_means_shadow(self, monkeypatch) -> None:
        self._patch_db(monkeypatch, self._db())
        assert auto.resolved_fleet_enforce() is False


# ── Config + status ─────────────────────────────────────────────────────────


class TestConfigStatus(TestAutomation):
    def test_set_automation_config_validates_mode(self) -> None:
        with pytest.raises(ValueError):
            auto.set_automation_config(mode="sideways")
        with pytest.raises(ValueError):
            auto.set_automation_config(interval_min=0.1)

    def test_run_auto_certification_off_mode(self, monkeypatch) -> None:
        monkeypatch.setattr(auto, "_mode", "off")
        result = auto.run_auto_certification()
        assert result == {"enabled": False, "mode": "off"}

    def test_run_auto_certification_never_raises(self, monkeypatch) -> None:
        def _boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(auto, "_mode", "approve")
        monkeypatch.setattr("core.database.get_db_session", _boom)
        result = auto.run_auto_certification()
        assert result.get("error") == "pass failed"

    def test_get_automation_status_shape(self) -> None:
        status = auto.get_automation_status()
        assert set(["enabled", "mode", "interval_min", "pending_approvals", "last_run"]) <= set(status.keys())
