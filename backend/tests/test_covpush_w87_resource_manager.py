# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/resource_manager (standalone, zero LLM spend,
no network; fake db rows).

- calculate_utilization: user-not-found error; zero tasks → 0% low risk; task
  estimated_hours from metadata_json (numeric + numeric-string) and the 5.0
  default when metadata is missing or non-dict; capacity_hours from the user
  when present else 40.0; risk tiers (high >100%, medium >80%, low otherwise);
  utilization math (hours/capacity*100 rounded); injected db NOT closed vs
  get_db_session path; unexpected exception → error dict (never raises).
- get_team_utilization: team-not-found error; zero-capacity team → 0% average;
  aggregate average/total_tasks across members (with member utilization
  patched); per-member reports surfaced.
"""
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.resource_manager import ResourceMonitor, resource_monitor


@contextmanager
def _cm(value):
    yield value


@contextmanager
def _closing_cm(value):
    try:
        yield value
    finally:
        value.close()


class _FakeQuery:
    def __init__(self, first_row=None, rows=None):
        self._first_row = first_row
        self._rows = rows or []

    def filter(self, *exprs):
        return self

    def first(self):
        return self._first_row

    def all(self):
        return self._rows


class _FakeDB:
    """Sequential query store: first query → users, second → tasks, then
    cycling user/task per calculate_utilization call."""

    def __init__(self, user=None, tasks=None):
        self.user = user
        self.tasks = tasks
        self.pattern = [("user",), ("task",)]
        self._idx = 0
        self.closed = False

    def query(self, model):
        kind = self.pattern[self._idx % len(self.pattern)][0]
        self._idx += 1
        if kind == "user":
            return _FakeQuery(first_row=self.user)
        return _FakeQuery(rows=self.tasks)

    def close(self):
        self.closed = True


def _user(user_id="u1", first="Alice", last="Smith", capacity=None):
    u = SimpleNamespace(
        id=user_id, first_name=first, last_name=last, status="active",
        workspace_id="ws-1",
    )
    if capacity is not None:
        u.capacity_hours = capacity
    return u


def _task(meta=None):
    """meta = the raw metadata_json value (None → 5.0 default; dict →
    estimated_hours; non-dict truthy → non-dict branch)."""
    t = SimpleNamespace(assigned_to="u1", status="in_progress")
    t.metadata_json = meta
    return t


class TestCalculateUtilization:
    def test_user_not_found_returns_error(self):
        fake_db = _FakeDB(user=None)
        result = ResourceMonitor().calculate_utilization("nobody", db=fake_db)
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_zero_tasks_zero_utilization_low_risk(self):
        fake_db = _FakeDB(user=_user(), tasks=[])
        result = ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert result["utilization_percentage"] == 0.0
        assert result["weekly_capacity"] == 40.0
        assert result["active_task_count"] == 0
        assert result["risk_level"] == "low"
        assert result["user_name"] == "Alice Smith"

    def test_estimated_hours_from_metadata(self):
        fake_db = _FakeDB(user=_user(), tasks=[_task(meta={"estimated_hours": 10.0}), _task(meta={"estimated_hours": "5.0"})])
        result = ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert result["total_estimated_hours"] == 15.0
        assert result["utilization_percentage"] == 37.5

    def test_default_five_hours_when_metadata_missing(self):
        fake_db = _FakeDB(user=_user(), tasks=[_task(meta=None), _task(meta={"estimated_hours": 15.0})])
        result = ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert result["total_estimated_hours"] == 20.0
        assert result["utilization_percentage"] == 50.0

    def test_non_dict_metadata_defaults_to_five(self):
        fake_db = _FakeDB(user=_user(), tasks=[_task(meta="not-a-dict")])
        result = ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert result["total_estimated_hours"] == 5.0

    def test_custom_capacity_used(self):
        fake_db = _FakeDB(user=_user(capacity=80), tasks=[_task(meta={"estimated_hours": 40.0})])
        result = ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert result["weekly_capacity"] == 80.0
        assert result["utilization_percentage"] == 50.0

    def test_high_risk_above_100_percent(self):
        fake_db = _FakeDB(user=_user(), tasks=[_task(meta={"estimated_hours": 50.0}), _task(meta={"estimated_hours": 50.0})])
        result = ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert result["utilization_percentage"] == 250.0
        assert result["risk_level"] == "high"

    def test_medium_risk_between_80_and_100(self):
        fake_db = _FakeDB(user=_user(), tasks=[_task(meta={"estimated_hours": 36.0})])
        result = ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert result["utilization_percentage"] == 90.0
        assert result["risk_level"] == "medium"

    def test_injected_db_not_closed(self):
        fake_db = _FakeDB(user=_user(), tasks=[])
        ResourceMonitor().calculate_utilization("u1", db=fake_db)
        assert not fake_db.closed

    def test_get_db_session_path_when_no_db(self):
        fake_db = _FakeDB(user=_user(), tasks=[])
        with patch("core.resource_manager.get_db_session", return_value=_closing_cm(fake_db)):
            result = ResourceMonitor().calculate_utilization("u1")
        assert result["utilization_percentage"] == 0.0
        assert fake_db.closed

    def test_exception_returns_error_dict(self):
        boom = MagicMock()
        boom.query.side_effect = RuntimeError("db down")
        result = ResourceMonitor().calculate_utilization("u1", db=boom)
        assert result["status"] == "error"
        assert "Failed to calculate utilization" in result["message"]


class TestGetTeamUtilization:
    def test_team_not_found_returns_error(self):
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.resource_manager.get_db_session", return_value=_cm(fake_db)):
            result = ResourceMonitor().get_team_utilization("team-x")
        assert result["status"] == "error"
        assert "Team not found" in result["message"]

    def test_team_with_members_aggregates(self):
        team = SimpleNamespace(id="team-1", name="Eng", members=[_user("u1"), _user("u2")])
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = team
        monitor = ResourceMonitor()
        monitor.calculate_utilization = MagicMock(side_effect=[
            {"total_estimated_hours": 20.0, "weekly_capacity": 40.0,
             "active_task_count": 2},
            {"total_estimated_hours": 60.0, "weekly_capacity": 80.0,
             "active_task_count": 3},
        ])
        with patch("core.resource_manager.get_db_session", return_value=_cm(fake_db)):
            result = monitor.get_team_utilization("team-1")
        assert result["team_id"] == "team-1"
        assert result["average_utilization"] == pytest.approx(66.67, abs=0.01)
        assert result["total_tasks"] == 5
        assert len(result["member_reports"]) == 2

    def test_zero_total_capacity_average_is_zero(self):
        team = SimpleNamespace(id="team-1", name="Eng", members=[_user("u1")])
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = team
        monitor = ResourceMonitor()
        monitor.calculate_utilization = MagicMock(return_value={
            "total_estimated_hours": 0.0, "weekly_capacity": 0.0,
            "active_task_count": 0,
        })
        with patch("core.resource_manager.get_db_session", return_value=_cm(fake_db)):
            result = monitor.get_team_utilization("team-1")
        assert result["average_utilization"] == 0.0
        assert result["total_tasks"] == 0


class TestModuleInstance:
    def test_singleton(self):
        assert isinstance(resource_monitor, ResourceMonitor)
