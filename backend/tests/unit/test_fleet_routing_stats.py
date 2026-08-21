"""Tests for fleet routing validation statistics.

Covers: workload-key normalization, hot-path audit writes (incl. never-raises),
the execution-outcome join, and calibration-status phase logic (off /
collecting / blocked / ready / enforced) using a fake session.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from core.fleet_orchestration import fleet_routing_stats as stats


# ── Fake session / rows ─────────────────────────────────────────────────────


class FakeRow:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeQuery:
    def __init__(self, rows: List[Any]) -> None:
        self.rows = rows

    def filter(self, *args, **kwargs):  # noqa: A002
        return self

    def all(self) -> List[Any]:
        return list(self.rows)

    def count(self) -> int:
        return len(self.rows)


class FakeDb:
    def __init__(self, rows: Optional[List[Any]] = None) -> None:
        self.rows = rows or []
        self.added: List[Any] = []
        self.committed = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, row: Any) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.committed += 1

    def query(self, model):  # noqa: A002
        return FakeQuery(self.rows)


def _patch_db(monkeypatch, rows: Optional[List[Any]] = None) -> FakeDb:
    fake = FakeDb(rows)
    monkeypatch.setattr("core.database.get_db_session", lambda: fake)
    return fake


def _audit_row(**overrides: Any) -> FakeRow:
    base = dict(
        id="a1",
        execution_id="exec-1",
        workspace_id="ws-1",
        tenant_id="t-1",
        agent_id="atom_main",
        workload_key="wk1",
        request_text="analyze my sales pipeline",
        chain_id="chain-1",
        specialists_count=2,
        roster_json=[],
        recruitment_succeeded=True,
        enforced=False,
        decision_source="fleet_eligible",
        error=None,
        success=None,
        actual_latency_ms=None,
        actual_model=None,
        actual_provider=None,
    )
    base.update(overrides)
    return FakeRow(**base)


class TestWorkloadKey:
    def test_normalizes_case_and_whitespace(self) -> None:
        assert stats.workload_key_for("  Analyze My   SALES Pipeline ") == stats.workload_key_for(
            "analyze my sales pipeline"
        )

    def test_unknown_for_empty(self) -> None:
        assert stats.workload_key_for("") == "unknown"
        assert stats.workload_key_for(None) == "unknown"

    def test_stable_hex_signature(self) -> None:
        key = stats.workload_key_for("analyze my sales pipeline")
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)


class TestRecordFleetDecision:
    def test_writes_row_with_all_fields(self, monkeypatch) -> None:
        fake = _patch_db(monkeypatch)
        row_id = stats.record_fleet_decision(
            execution_id="exec-1",
            workspace_id="ws-1",
            tenant_id="t-1",
            agent_id="atom_main",
            request="analyze my sales pipeline in detail this quarter",
            chain_id="chain-1",
            specialists_count=2,
            roster=[{"agent_id": "s1", "agent_name": "Analyst", "domain": "sales"}],
            recruitment_succeeded=True,
            enforced=False,
        )
        assert row_id is not None
        assert fake.committed == 1
        row = fake.added[0]
        assert row.execution_id == "exec-1"
        assert row.workspace_id == "ws-1"
        assert row.chain_id == "chain-1"
        assert row.specialists_count == 2
        assert row.recruitment_succeeded is True
        assert row.enforced is False
        assert row.roster_json[0]["domain"] == "sales"
        assert row.workload_key == stats.workload_key_for(
            "analyze my sales pipeline in detail this quarter"
        )

    def test_never_raises_on_db_failure(self, monkeypatch) -> None:
        def _boom():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", _boom)
        assert stats.record_fleet_decision(execution_id="e", request="x") is None

    def test_truncates_request_text(self, monkeypatch) -> None:
        fake = _patch_db(monkeypatch)
        long_req = "x" * 500
        stats.record_fleet_decision(execution_id="e", request=long_req)
        assert len(fake.added[0].request_text) == 200


class TestRecordFleetExecutionOutcome:
    def test_joins_success_onto_matching_rows(self, monkeypatch) -> None:
        row = _audit_row(id="a1", execution_id="exec-1")
        fake = _patch_db(monkeypatch, rows=[row])
        stats.record_fleet_execution_outcome(
            "exec-1", success=True, actual_latency_ms=123.0
        )
        assert fake.committed == 1
        assert row.success is True
        assert row.actual_latency_ms == 123.0

    def test_joins_failure_with_error(self, monkeypatch) -> None:
        row = _audit_row(id="a1", execution_id="exec-1", error=None)
        _patch_db(monkeypatch, rows=[row])
        stats.record_fleet_execution_outcome("exec-1", success=False, error_message="boom")
        assert row.success is False
        assert row.error == "boom"

    def test_never_raises_on_db_failure(self, monkeypatch) -> None:
        def _boom():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", _boom)
        stats.record_fleet_execution_outcome("exec-1", success=True)  # must not raise


class TestCalibrationStatus:
    def _patch_common(self, monkeypatch, enforced: bool = False) -> None:
        monkeypatch.setattr(
            "core.fleet_orchestration.fleet_router_automation.resolved_fleet_enforce",
            lambda db=None: enforced,
        )

    def test_phase_off_when_routing_disabled(self, monkeypatch) -> None:
        _patch_db(monkeypatch, rows=[])
        monkeypatch.setattr("core.fleet_routing_config.fleet_routing_enabled", lambda: False)
        self._patch_common(monkeypatch)
        status = stats.fleet_calibration_status()
        assert status["phase"] == "off"

    def test_phase_collecting_below_min_rows(self, monkeypatch) -> None:
        rows = [_audit_row(success=True) for _ in range(5)]
        _patch_db(monkeypatch, rows=rows)
        monkeypatch.setattr("core.fleet_routing_config.fleet_routing_enabled", lambda: True)
        self._patch_common(monkeypatch)
        status = stats.fleet_calibration_status()
        assert status["phase"] == "collecting"
        assert status["counts"]["outcome_joined"] == 5
        assert "min_detectable_gap" in next(iter(status["workloads"].values()))

    def test_phase_blocked_on_unhealthy_recruitment(self, monkeypatch) -> None:
        rows = [_audit_row(success=True, recruitment_succeeded=False) for _ in range(12)]
        _patch_db(monkeypatch, rows=rows)
        monkeypatch.setattr("core.fleet_routing_config.fleet_routing_enabled", lambda: True)
        self._patch_common(monkeypatch)
        status = stats.fleet_calibration_status()
        assert status["phase"] == "blocked"
        assert "recruit" in status["why"].lower()

    def test_phase_ready_when_healthy_and_sufficient(self, monkeypatch) -> None:
        rows = [_audit_row(success=True) for _ in range(40)]
        _patch_db(monkeypatch, rows=rows)
        monkeypatch.setattr("core.fleet_routing_config.fleet_routing_enabled", lambda: True)
        self._patch_common(monkeypatch)
        status = stats.fleet_calibration_status()
        assert status["phase"] == "ready"
        assert status["recruitment"]["recruit_attempts"] == 40

    def test_phase_enforced_when_override_active(self, monkeypatch) -> None:
        rows = [_audit_row(success=True) for _ in range(40)]
        _patch_db(monkeypatch, rows=rows)
        monkeypatch.setattr("core.fleet_routing_config.fleet_routing_enabled", lambda: True)
        self._patch_common(monkeypatch, enforced=True)
        status = stats.fleet_calibration_status()
        assert status["phase"] == "enforced"
        assert status["enforced"] is True

    def test_never_raises_and_reports_error(self, monkeypatch) -> None:
        def _boom():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", _boom)
        status = stats.fleet_calibration_status()
        assert status["phase"] == "error"
