# -*- coding: utf-8 -*-
"""Coverage wave 74 — core/condition_checkers.py (standalone, zero LLM spend,
no network, no real DB).

TDD targets (RED first, fixed in source):
- ``_check_api_metrics`` referenced ``AgentExecution.created_at`` which does
  NOT exist on the model (only ``started_at``) — every api_metrics monitor
  check raised AttributeError (silently swallowed by
  ``check_and_alert_monitors``' broad except → monitoring silently disabled).
- ``_check_composite`` constructed ``ConditionMonitor(agent_id=..., ...)``
  with non-column kwargs → TypeError on every composite monitor check.
- ``_prioritize_citations``-style None guard: (covered in jit file).

Coverage targets: dispatch (task_backlog/api_metrics/database_query/unknown),
window parsing (int, "2h", "90", invalid), error_rate 0 and >0 totals,
response_time_p95 (avg / no-timings / no-executions), request_count, unknown
metric, database_query (result/None/exception), composite (empty, AND, OR,
sub-conditions incl. real DB rows), all compare operators (>, >=, <, <=, ==,
=, !=, unknown, exception), ConditionCheckerFactory.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (  # noqa: F401 (register models)
    AgentExecution,
    ConditionMonitor,
    Team,
    TeamMessage,
    Tenant,
    User,
    Workspace,
)
from core.condition_checkers import (
    CONDITION_TYPE_API_METRICS,
    CONDITION_TYPE_COMPOSITE,
    CONDITION_TYPE_DATABASE_QUERY,
    CONDITION_TYPE_INBOX_VOLUME,
    CONDITION_TYPE_TASK_BACKLOG,
    ConditionCheckerFactory,
    ConditionCheckers,
)


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_tenant(db, tid="t1"):
    tenant = Tenant(id=tid, name="Test", subdomain=f"sub-{tid}")
    db.add(tenant)
    db.commit()
    return tenant


def _make_workspace(db, ws_id="ws-1", tid="t1"):
    _make_tenant(db, tid)
    ws = Workspace(id=ws_id, name="Test WS", tenant_id=tid)
    db.add(ws)
    db.commit()
    return ws


def _make_user(db, uid="user-1", tid="t1"):
    user = User(
        id=uid,
        email=f"{uid}@example.com",
        first_name="Test",
        last_name="User",
        role="admin",
        status="active",
        tenant_id=tid,
    )
    db.add(user)
    db.commit()
    return user


def _make_team_message(db, mid="msg-1", uid="user-1", tid="t1"):
    _make_workspace(db, tid=tid)
    _make_user(db, uid=uid, tid=tid)
    team = Team(id=f"team-{mid}", name=f"Team {mid}", workspace_id="ws-1")
    db.add(team)
    db.commit()
    msg = TeamMessage(id=mid, team_id=team.id, user_id=uid, content="hello")
    db.add(msg)
    db.commit()
    return msg


def _execution(db, ex_id, status="completed", started_minutes_ago=10,
               completed_after_seconds=2.5, agent_id="agent-1"):
    started = datetime.now(timezone.utc) - timedelta(minutes=started_minutes_ago)
    completed = started + timedelta(seconds=completed_after_seconds)
    ex = AgentExecution(
        id=ex_id,
        agent_id=agent_id,
        status=status,
        started_at=started,
        completed_at=completed,
    )
    db.add(ex)
    db.commit()
    return ex


def _monitor(condition_type, threshold_config=None, **kwargs):
    """Mirror ``ConditionMonitoringService._hydrate_config``: the stub model
    only persists ``condition_config``; plain attrs are restored manually."""
    cfg = {"threshold_config": threshold_config or {}}
    monitor = ConditionMonitor(
        id=kwargs.pop("id", f"mon-{condition_type}"),
        user_id="user-1",
        name=kwargs.pop("name", "Test monitor"),
        condition_type=condition_type,
        condition_config=cfg,
        is_active=True,
    )
    monitor.agent_id = kwargs.pop("agent_id", "agent-1")
    monitor.agent_name = kwargs.pop("agent_name", "Agent 1")
    monitor.threshold_config = cfg["threshold_config"]
    monitor.platforms = kwargs.pop("platforms", [])
    monitor.check_interval_seconds = 300
    monitor.alert_template = None
    monitor.composite_logic = kwargs.pop("composite_logic", None)
    monitor.composite_conditions = kwargs.pop("composite_conditions", [])
    monitor.governance_metadata = {}
    monitor.status = "active"
    return monitor


# ============================================================================
# TDD RED tests — real bugs fixed in source
# ============================================================================

class TestRealBugApiMetricsCreatedAt:
    """_check_api_metrics used nonexistent AgentExecution.created_at."""

    def test_error_rate_with_real_db_does_not_crash(self, db):
        _execution(db, "ex-1", status="failed", started_minutes_ago=1)
        _execution(db, "ex-2", status="completed", started_minutes_ago=1)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0.5, "window": "5m"},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 0.5
        assert result["triggered"] is False  # 0.5 is not > 0.5

    def test_error_rate_triggers_and_respects_window(self, db):
        _execution(db, "ex-old", status="failed", started_minutes_ago=600)
        _execution(db, "ex-fail", status="failed", started_minutes_ago=1)
        _execution(db, "ex-ok", status="completed", started_minutes_ago=1)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0.4, "window": "5m"},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 0.5  # old execution excluded by window
        assert result["triggered"] is True

    def test_response_time_p95_with_real_db(self, db):
        _execution(db, "ex-1", completed_after_seconds=1.0, started_minutes_ago=1)
        _execution(db, "ex-2", completed_after_seconds=3.0, started_minutes_ago=1)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "response_time_p95", "operator": ">", "value": 1.5},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 2.0
        assert result["triggered"] is True

    def test_request_count_with_real_db(self, db):
        _execution(db, "ex-1", status="failed", started_minutes_ago=1)
        _execution(db, "ex-2", status="completed", started_minutes_ago=1)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "request_count", "operator": ">=", "value": 2},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 2
        assert result["triggered"] is True


class TestRealBugCompositeKwargs:
    """_check_composite built ConditionMonitor with non-column kwargs."""

    def test_composite_and_triggers_only_when_all_true(self, db):
        _make_team_message(db)  # 1 unread message
        monitor = _monitor(CONDITION_TYPE_COMPOSITE)
        monitor.composite_logic = "AND"
        monitor.composite_conditions = [
            {
                "condition_type": CONDITION_TYPE_INBOX_VOLUME,
                "threshold_config": {"metric": "unread_count", "operator": ">", "value": 0},
            },
            {
                "condition_type": CONDITION_TYPE_TASK_BACKLOG,
                "threshold_config": {"metric": "pending_count", "operator": "<", "value": 1},
            },
        ]
        result = ConditionCheckers(db)._check_composite(monitor)
        assert result["triggered"] is True
        assert len(result["sub_conditions"]) == 2

    def test_composite_and_one_false_not_triggered(self, db):
        _execution(db, "ex-pending", status="pending")
        monitor = _monitor(CONDITION_TYPE_COMPOSITE)
        monitor.composite_logic = "AND"
        monitor.composite_conditions = [
            {
                "condition_type": CONDITION_TYPE_INBOX_VOLUME,
                "threshold_config": {"metric": "unread_count", "operator": ">", "value": 100},
            },
            {
                "condition_type": CONDITION_TYPE_TASK_BACKLOG,
                "threshold_config": {"metric": "pending_count", "operator": ">", "value": 0},
            },
        ]
        result = ConditionCheckers(db)._check_composite(monitor)
        assert result["triggered"] is False

    def test_composite_or_any_true(self, db):
        _make_team_message(db)
        monitor = _monitor(CONDITION_TYPE_COMPOSITE)
        monitor.composite_logic = "OR"
        monitor.composite_conditions = [
            {
                "condition_type": CONDITION_TYPE_INBOX_VOLUME,
                "threshold_config": {"metric": "unread_count", "operator": ">", "value": 0},
            },
            {
                "condition_type": CONDITION_TYPE_TASK_BACKLOG,
                "threshold_config": {"metric": "pending_count", "operator": ">", "value": 100},
            },
        ]
        result = ConditionCheckers(db)._check_composite(monitor)
        assert result["triggered"] is True
        assert result["metric_name"].startswith("Composite (OR")


# ============================================================================
# Dispatch
# ============================================================================

class TestDispatch:
    def test_dispatch_inbox_volume(self, db):
        monitor = _monitor(CONDITION_TYPE_INBOX_VOLUME)
        result = ConditionCheckers(db).check_condition(monitor)
        assert result["triggered"] is False
        assert result["metric_name"] == "Unread messages"

    def test_dispatch_task_backlog(self, db):
        monitor = _monitor(CONDITION_TYPE_TASK_BACKLOG)
        result = ConditionCheckers(db).check_condition(monitor)
        assert result["metric_name"] == "Pending tasks"

    def test_dispatch_api_metrics(self, db):
        monitor = _monitor(CONDITION_TYPE_API_METRICS)
        result = ConditionCheckers(db).check_condition(monitor)
        assert "API error rate" in result["metric_name"]

    def test_dispatch_database_query(self, db):
        monitor = _monitor(
            CONDITION_TYPE_DATABASE_QUERY,
            {"query": "SELECT 1", "operator": ">", "value": 0},
        )
        result = ConditionCheckers(db).check_condition(monitor)
        assert result["metric_name"] == "Database query result"

    def test_dispatch_composite(self, db):
        monitor = _monitor(CONDITION_TYPE_COMPOSITE)
        result = ConditionCheckers(db).check_condition(monitor)
        assert result["triggered"] is False

    def test_dispatch_unknown_type(self, db):
        monitor = _monitor("bogus_type")
        result = ConditionCheckers(db).check_condition(monitor)
        assert result["triggered"] is False
        assert "Unknown type" in result["metric_name"]


# ============================================================================
# inbox_volume / task_backlog
# ============================================================================

class TestInboxAndBacklog:
    def test_inbox_volume_triggers(self, db):
        _make_team_message(db)
        monitor = _monitor(
            CONDITION_TYPE_INBOX_VOLUME,
            {"metric": "unread_count", "operator": ">", "value": 0},
        )
        result = ConditionCheckers(db)._check_inbox_volume(monitor)
        assert result["triggered"] is True
        assert result["value"] == 1

    def test_task_backlog_triggers(self, db):
        _execution(db, "ex-1", status="pending")
        monitor = _monitor(
            CONDITION_TYPE_TASK_BACKLOG,
            {"metric": "pending_count", "operator": ">=", "value": 1},
        )
        result = ConditionCheckers(db)._check_task_backlog(monitor)
        assert result["triggered"] is True
        assert result["value"] == 1

    def test_task_backlog_not_triggered(self, db):
        _execution(db, "ex-1", status="completed")
        monitor = _monitor(
            CONDITION_TYPE_TASK_BACKLOG,
            {"metric": "pending_count", "operator": ">", "value": 0},
        )
        result = ConditionCheckers(db)._check_task_backlog(monitor)
        assert result["triggered"] is False
        assert result["value"] == 0


# ============================================================================
# api_metrics window parsing + branches
# ============================================================================

class TestWindowParsing:
    def test_window_int_minutes(self, db):
        _execution(db, "ex-1", status="failed", started_minutes_ago=5)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0, "window": 10},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["triggered"] is True

    def test_window_hours(self, db):
        _execution(db, "ex-1", status="failed", started_minutes_ago=30)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0, "window": "1h"},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["triggered"] is True  # 30min ago is inside 1h window

    def test_window_plain_number_string(self, db):
        _execution(db, "ex-1", status="failed")
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0, "window": "90"},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["triggered"] is True

    def test_window_none_falls_back_to_5m(self, db):
        _execution(db, "ex-1", status="failed", started_minutes_ago=1)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0, "window": None},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["triggered"] is True

    def test_window_invalid_falls_back_to_5m(self, db):
        _execution(db, "ex-1", status="failed", started_minutes_ago=1)
        _execution(db, "ex-old", status="failed", started_minutes_ago=120)
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0, "window": "banana"},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["triggered"] is True  # 5m window includes ex-1 only

    def test_error_rate_no_executions(self, db):
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "error_rate", "operator": ">", "value": 0.05},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 0.0
        assert result["triggered"] is False

    def test_response_time_no_timings(self, db):
        started = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.add(AgentExecution(id="ex-nt", agent_id="agent-1", status="running",
                              started_at=started, completed_at=None))
        db.commit()
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "response_time_p95", "operator": ">", "value": 0.1},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 0.0
        assert result["triggered"] is False

    def test_response_time_no_executions(self, db):
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "response_time_p95", "operator": ">", "value": 0.1},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 0.0

    def test_unknown_metric(self, db):
        monitor = _monitor(
            CONDITION_TYPE_API_METRICS,
            {"metric": "bogus_metric", "operator": ">", "value": 1},
        )
        result = ConditionCheckers(db)._check_api_metrics(monitor)
        assert result["value"] == 0
        assert "Unknown metric" in result["metric_name"]


# ============================================================================
# database_query
# ============================================================================

class TestDatabaseQuery:
    def test_query_result_triggers(self, db):
        _execution(db, "ex-1", status="completed")
        monitor = _monitor(
            CONDITION_TYPE_DATABASE_QUERY,
            {"query": "SELECT COUNT(*) FROM agent_executions", "operator": ">", "value": 0},
        )
        result = ConditionCheckers(db)._check_database_query(monitor)
        assert result["triggered"] is True
        assert result["metric_name"] == "Database query result"

    def test_query_result_none(self, db):
        monitor = _monitor(
            CONDITION_TYPE_DATABASE_QUERY,
            {"query": "SELECT NULL", "operator": ">", "value": 0},
        )
        result = ConditionCheckers(db)._check_database_query(monitor)
        assert result["value"] == 0
        assert result["triggered"] is False

    def test_query_exception_returns_error_details(self, db):
        monitor = _monitor(
            CONDITION_TYPE_DATABASE_QUERY,
            {"query": "SELECT * FROM does_not_exist", "operator": ">", "value": 0},
        )
        result = ConditionCheckers(db)._check_database_query(monitor)
        assert result["triggered"] is False
        assert result["value"] is None
        assert "Query error" in result["details"]


# ============================================================================
# composite
# ============================================================================

class TestComposite:
    def test_empty_conditions(self, db):
        monitor = _monitor(CONDITION_TYPE_COMPOSITE)
        monitor.composite_logic = "AND"
        monitor.composite_conditions = []
        result = ConditionCheckers(db)._check_composite(monitor)
        assert result["triggered"] is False
        assert result["metric_name"] == "Composite (empty)"

    def test_composite_defaults_to_or_logic(self, db):
        _make_team_message(db)
        monitor = _monitor(CONDITION_TYPE_COMPOSITE)
        monitor.composite_logic = None  # falls to else → OR
        monitor.composite_conditions = [
            {
                "condition_type": CONDITION_TYPE_INBOX_VOLUME,
                "threshold_config": {"metric": "unread_count", "operator": ">", "value": 0},
            },
            {
                "condition_type": CONDITION_TYPE_TASK_BACKLOG,
                "threshold_config": {"metric": "pending_count", "operator": ">", "value": 100},
            },
        ]
        result = ConditionCheckers(db)._check_composite(monitor)
        assert result["triggered"] is True
        assert result["details"].startswith("Logic: None")

    def test_composite_and_false_subcondition_value_map(self, db):
        monitor = _monitor(CONDITION_TYPE_COMPOSITE)
        monitor.composite_logic = "AND"
        monitor.composite_conditions = [
            {
                "condition_type": CONDITION_TYPE_INBOX_VOLUME,
                "threshold_config": {"metric": "unread_count", "operator": ">", "value": 100},
            },
        ]
        result = ConditionCheckers(db)._check_composite(monitor)
        assert result["triggered"] is False
        assert "Unread messages" in result["value"]


# ============================================================================
# comparison operators
# ============================================================================

class TestCompareValues:
    @pytest.fixture()
    def checkers(self, db):
        return ConditionCheckers(db)

    def test_gt(self, checkers):
        assert checkers._compare_values(5, ">", 4) is True
        assert checkers._compare_values(5, ">", 5) is False

    def test_gte(self, checkers):
        assert checkers._compare_values(5, ">=", 5) is True
        assert checkers._compare_values(4, ">=", 5) is False

    def test_lt(self, checkers):
        assert checkers._compare_values(4, "<", 5) is True

    def test_lte(self, checkers):
        assert checkers._compare_values(5, "<=", 5) is True

    def test_eq(self, checkers):
        assert checkers._compare_values(5, "==", 5) is True

    def test_single_eq(self, checkers):
        assert checkers._compare_values(5, "=", 5) is True

    def test_ne(self, checkers):
        assert checkers._compare_values(5, "!=", 4) is True

    def test_unknown_operator(self, checkers):
        assert checkers._compare_values(5, ">>", 4) is False

    def test_comparison_exception(self, checkers):
        assert checkers._compare_values(None, ">", 5) is False


# ============================================================================
# factory
# ============================================================================

class TestFactory:
    def test_create_checker_returns_condition_checkers(self, db):
        checker = ConditionCheckerFactory.create_checker(CONDITION_TYPE_INBOX_VOLUME, db)
        assert isinstance(checker, ConditionCheckers)
        assert checker.db is db
