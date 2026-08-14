# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/stakeholder_engine.py.

Unit coverage of the stakeholder engagement engine:
- get_stakeholders_for_user: team members (self-skip, name fallback),
  goal-engine stakeholders, communication contacts (system/user/no-@
  filtering, dedupe), exception tolerance of goal/comms legs.
- calculate_engagement: empty results, numeric (int/float) + datetime
  timestamps, silence threshold, content truncation, exception -> error.
- identify_silent_stakeholders: silent vs active, outreach generation,
  sort by days_since desc.
- get_stakeholder_engine singleton.

REAL BUG (TDD RED -> GREEN):
  W104-3: the LanceDB where-clause interpolated the raw email into
  f"(sender = '{email}' OR recipient = '{email}')" — an email containing
  a single quote (e.g. o'brien@x.com) injected a bare quote into the
  filter, breaking the query (injection-class, CWE-89-adjacent). Now
  single quotes are escaped (doubled) before interpolation.

No LLM spend, no network.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from core.stakeholder_engine import (
    StakeholderEngagementEngine,
    get_stakeholder_engine,
    stakeholder_engine,
)


@pytest.fixture()
def engine():
    return StakeholderEngagementEngine()


@pytest.fixture()
def db_mock():
    db = MagicMock()

    def _execute(query):
        result = MagicMock()
        return result

    db.execute.return_value.scalars.return_value.all.return_value = []
    return db


def _team_db(team_ids, members):
    """DB mock whose first execute returns team_ids, second returns members."""
    db = MagicMock()
    results = []
    for values in (team_ids, members):
        result = MagicMock()
        result.scalars.return_value.all.return_value = values
        results.append(result)
    db.execute.side_effect = results
    return db


def _user(uid, email, first="", last=""):
    return SimpleNamespace(
        id=uid, email=email, first_name=first, last_name=last
    )


def _cm(db):
    return MagicMock(__enter__=MagicMock(return_value=db), __exit__=MagicMock())


def _run(coro):
    return asyncio.run(coro)


class TestGetStakeholdersForUser:
    def test_no_teams(self, engine, monkeypatch):
        db = _team_db([], [])
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={})
        )
        result = _run(engine.get_stakeholders_for_user("u1"))
        assert result == []

    def test_team_members_added_self_skipped(self, engine, monkeypatch):
        db = _team_db(
            ["team-1"],
            [_user("u1", "me@x.com", "Me", "Self"), _user("u2", "bob@x.com", "Bob", "B")],
        )
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={})
        )
        result = _run(engine.get_stakeholders_for_user("u1"))
        assert len(result) == 1
        s = result[0]
        assert s["email"] == "bob@x.com"
        assert s["name"] == "Bob B"
        assert s["source"] == "team"
        assert s["id"] == "u2"

    def test_team_member_name_falls_back_to_email(self, engine, monkeypatch):
        db = _team_db(
            ["team-1"], [_user("u2", "bob@x.com")]
        )
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={})
        )
        result = _run(engine.get_stakeholders_for_user("u1"))
        assert result[0]["name"] == "bob@x.com"

    def test_goal_stakeholders(self, engine, monkeypatch):
        db = _team_db([], [])
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        goal = SimpleNamespace(
            owner_id="u1",
            sub_tasks=[
                SimpleNamespace(assigned_to="carol@x.com"),
                SimpleNamespace(assigned_to=None),
            ],
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={"g1": goal})
        )
        result = _run(engine.get_stakeholders_for_user("u1"))
        assert len(result) == 1
        assert result[0]["email"] == "carol@x.com"
        assert result[0]["source"] == "goal"
        assert result[0]["id"] is None

    def test_goal_does_not_override_team(self, engine, monkeypatch):
        db = _team_db(["t1"], [_user("u2", "bob@x.com", "Bob", "B")])
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        goal = SimpleNamespace(
            owner_id="u1",
            sub_tasks=[SimpleNamespace(assigned_to="bob@x.com")],
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={"g1": goal})
        )
        result = _run(engine.get_stakeholders_for_user("u1"))
        assert result[0]["source"] == "team"

    def test_goal_engine_exception_tolerated(self, engine, monkeypatch):
        db = _team_db([], [])
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine",
            MagicMock(goals=SimpleNamespace(values=MagicMock(side_effect=RuntimeError("boom")))),
        )
        assert _run(engine.get_stakeholders_for_user("u1")) == []

    def test_communication_stakeholders(self, engine, monkeypatch):
        db = _team_db([], [])
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={})
        )
        mm = MagicMock()
        mm.db = object()
        mm.get_communications_by_timeframe.return_value = [
            {"sender": "dave@x.com", "recipient": "user"},
            {"sender": "system", "recipient": "erin@x.com"},
            {"sender": "user", "recipient": "no-at-sign"},
            {"sender": "frank@x.com", "recipient": "user"},
            {"sender": "frank@x.com", "recipient": "user"},
        ]
        monkeypatch.setattr(
            "integrations.atom_communication_ingestion_pipeline.get_memory_manager",
            lambda ws: mm,
        )
        result = _run(engine.get_stakeholders_for_user("u1", workspace_id="ws-1"))
        emails = {s["email"] for s in result}
        assert emails == {"dave@x.com", "erin@x.com", "frank@x.com"}
        dave = next(s for s in result if s["email"] == "dave@x.com")
        assert dave["name"] == "Dave"
        assert dave["source"] == "communication"

    def test_communication_memory_manager_initialized(self, engine, monkeypatch):
        db = _team_db([], [])
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={})
        )
        mm = MagicMock()
        mm.db = None
        mm.get_communications_by_timeframe.return_value = []
        monkeypatch.setattr(
            "integrations.atom_communication_ingestion_pipeline.get_memory_manager",
            lambda ws: mm,
        )
        _run(engine.get_stakeholders_for_user("u1", workspace_id="ws-1"))
        mm.initialize.assert_called_once()

    def test_communication_exception_tolerated(self, engine, monkeypatch):
        db = _team_db([], [])
        monkeypatch.setattr(
            "core.stakeholder_engine.get_db_session", lambda: _cm(db)
        )
        monkeypatch.setattr(
            "core.goal_engine.goal_engine", SimpleNamespace(goals={})
        )
        monkeypatch.setattr(
            "integrations.atom_communication_ingestion_pipeline.get_memory_manager",
            MagicMock(side_effect=RuntimeError("down")),
        )
        assert _run(engine.get_stakeholders_for_user("u1")) == []


class TestCalculateEngagement:
    @pytest.fixture()
    def mm(self):
        mm = MagicMock()
        mm.db = object()
        mm.connections_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame(columns=["timestamp", "content"])
        )
        return mm

    def _patch(self, monkeypatch, mm):
        monkeypatch.setattr(
            "integrations.atom_communication_ingestion_pipeline.get_memory_manager",
            lambda ws: mm,
        )

    def test_empty_results(self, engine, monkeypatch, mm):
        self._patch(monkeypatch, mm)
        result = _run(engine.calculate_engagement("u1", "bob@x.com"))
        assert result["last_interaction"] is None
        assert result["interaction_count"] == 0
        assert result["is_silent"] is True
        assert result["days_since"] == 999

    def test_int_microsecond_timestamp(self, engine, monkeypatch, mm):
        ts = int(datetime.now(timezone.utc).timestamp() * 1_000_000) - 5 * 24 * 3600 * 1_000_000
        mm.connections_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame({"timestamp": [ts], "content": ["Hello there"]})
        )
        self._patch(monkeypatch, mm)
        result = _run(engine.calculate_engagement("u1", "bob@x.com"))
        assert result["interaction_count"] == 1
        assert result["is_silent"] is True
        assert result["days_since"] == 5
        assert result["latest_content"].startswith("Hello there")

    def test_float_timestamp(self, engine, monkeypatch, mm):
        ts = float(int(datetime.now(timezone.utc).timestamp() * 1_000_000) - 1 * 24 * 3600 * 1_000_000)
        mm.connections_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame({"timestamp": [ts], "content": ["Recent"]})
        )
        self._patch(monkeypatch, mm)
        result = _run(engine.calculate_engagement("u1", "bob@x.com"))
        assert result["days_since"] == 1
        assert result["is_silent"] is False

    def test_datetime_timestamp(self, engine, monkeypatch, mm):
        ts = datetime.now(timezone.utc) - timedelta(days=2)
        mm.connections_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame({"timestamp": [ts], "content": ["Two days"]})
        )
        self._patch(monkeypatch, mm)
        result = _run(engine.calculate_engagement("u1", "bob@x.com"))
        assert result["days_since"] == 2
        assert result["is_silent"] is False

    def test_naive_datetime_timestamp(self, engine, monkeypatch, mm):
        ts = datetime.now() - timedelta(days=4)
        mm.connections_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame({"timestamp": [ts], "content": ["Naive four days"]})
        )
        self._patch(monkeypatch, mm)
        result = _run(engine.calculate_engagement("u1", "bob@x.com"))
        assert result["days_since"] == 4
        assert result["is_silent"] is True
        assert result["last_interaction"].endswith("+00:00")

    def test_memory_manager_initialized(self, engine, monkeypatch, mm):
        mm.db = None
        mm.connections_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame(columns=["timestamp", "content"])
        )
        self._patch(monkeypatch, mm)
        _run(engine.calculate_engagement("u1", "bob@x.com"))
        mm.initialize.assert_called_once()

    def test_exception_returns_error(self, engine, monkeypatch, mm):
        mm.connections_table.search.side_effect = RuntimeError("lancedb down")
        self._patch(monkeypatch, mm)
        result = _run(engine.calculate_engagement("u1", "bob@x.com"))
        assert "error" in result

    # ---- W104-3 RED: email with a single quote must not break the query ----
    def test_quote_in_email_escaped(self, engine, monkeypatch, mm):
        mm.connections_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = (
            pd.DataFrame(columns=["timestamp", "content"])
        )
        self._patch(monkeypatch, mm)
        _run(engine.calculate_engagement("u1", "o'brien@x.com"))
        where_call = mm.connections_table.search.return_value.where
        where_arg = where_call.call_args[0][0]
        assert where_arg == (
            "(sender = 'o''brien@x.com' OR recipient = 'o''brien@x.com')"
        )
        assert "o'brien" not in where_arg.split("'o'")[0]


class TestIdentifySilentStakeholders:
    def test_mixed_silent_and_active(self, engine, monkeypatch):
        engine.get_stakeholders_for_user = AsyncMock(
            return_value=[
                {"email": "a@x.com", "name": "A"},
                {"email": "b@x.com", "name": "B"},
            ]
        )
        engine.calculate_engagement = AsyncMock(
            side_effect=[
                {"is_silent": True, "days_since": 10, "latest_content": "last msg"},
                {"is_silent": False, "days_since": 1},
            ]
        )
        result = _run(engine.identify_silent_stakeholders("u1"))
        assert len(result) == 1
        assert result[0]["email"] == "a@x.com"
        assert result[0]["is_silent"] is True
        assert result[0]["days_since"] == 10
        assert "Hi A" in result[0]["suggested_outreach"]
        assert "last msg" in result[0]["suggested_outreach"]

    def test_sorted_by_days_since_desc(self, engine, monkeypatch):
        engine.get_stakeholders_for_user = AsyncMock(
            return_value=[
                {"email": "a@x.com", "name": "A"},
                {"email": "b@x.com", "name": "B"},
                {"email": "c@x.com", "name": "C"},
            ]
        )
        engine.calculate_engagement = AsyncMock(
            side_effect=[
                {"is_silent": True, "days_since": 3, "latest_content": "x"},
                {"is_silent": True, "days_since": 20, "latest_content": "y"},
                {"is_silent": True, "days_since": 7, "latest_content": "z"},
            ]
        )
        result = _run(engine.identify_silent_stakeholders("u1"))
        assert [r["days_since"] for r in result] == [20, 7, 3]

    def test_outreach_fallback_without_content(self, engine, monkeypatch):
        engine.get_stakeholders_for_user = AsyncMock(
            return_value=[{"email": "a@x.com", "name": "A"}]
        )
        engine.calculate_engagement = AsyncMock(
            side_effect=[{"is_silent": True, "days_since": 5}]
        )
        result = _run(engine.identify_silent_stakeholders("u1"))
        assert "the project" in result[0]["suggested_outreach"]

    def test_no_stakeholders(self, engine, monkeypatch):
        engine.get_stakeholders_for_user = AsyncMock(return_value=[])
        assert _run(engine.identify_silent_stakeholders("u1")) == []


class TestSingleton:
    def test_engine_attributes(self, engine):
        assert engine.engagement_threshold_days == 3

    def test_global_singleton(self):
        assert isinstance(stakeholder_engine, StakeholderEngagementEngine)
        assert get_stakeholder_engine() is stakeholder_engine
