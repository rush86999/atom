# -*- coding: utf-8 -*-
"""Coverage wave 80 — core/workforce_analytics.py to >=95% (standalone,
in-memory SQLite; no network, no LLM spend).

Covers:
- _get_db/_close_db: injected session (no cm) + context-manager path.
- calculate_team_velocity: empty data, completed tasks with cycle time,
  missing timestamps (skipped delta), days=0.
- detect_bottlenecks: no data, high-workload user (found/unknown), severity
  high vs medium, stalled tasks.
- get_focus_score: no active tasks → 100, one project → 100, multi-project
  penalty, clamp at 0.
- calculate_estimation_bias: no data, duration variance, hour variance with
  metadata estimated_hours, category optimistic/pessimistic/accurate.
- get_user_bias_profile.
- map_skill_gaps: no users, user skills string split, required_skills list +
  string forms, unmet requirements, assignment mismatches, completed-task
  exemption, missing skills attribute (getattr fallback).
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, null
from sqlalchemy.orm import sessionmaker

import core.models  # noqa: F401 (register models)
import service_delivery.models  # noqa: F401
from core.database import Base
from core.models import User
from core.workforce_analytics import WorkforceAnalyticsService
from service_delivery.models import Project, ProjectTask


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def svc(db):
    return WorkforceAnalyticsService(db_session=db)


def _make_project(db, pid="p1", ws="ws1"):
    project = Project(id=pid, workspace_id=ws, name=f"Project {pid}")
    db.add(project)
    db.commit()
    return project


def _make_task(db, tid, ws="ws1", *, status="pending", assigned_to=None,
               created_at=None, completed_at=None, updated_at=None,
               due_date=None, actual_hours=0.0, metadata_json=None,
               project_id="p1"):
    task = ProjectTask(
        id=tid, workspace_id=ws, project_id=project_id,
        milestone_id=f"m_{tid}", name=f"Task {tid}", status=status,
        assigned_to=assigned_to, created_at=created_at,
        completed_at=completed_at, updated_at=updated_at,
        due_date=due_date, actual_hours=actual_hours,
        metadata_json=metadata_json,
    )
    db.add(task)
    db.commit()
    return task


def _make_user(db, uid, skills=None, status="active"):
    user = User(id=uid, email=f"{uid}@x.com", first_name="F",
                last_name="L", role="member", status=status)
    db.add(user)
    db.commit()
    if skills is not None:
        # The `skills` column is commented out in the ORM model (schema
        # drift) — set it as an instance attribute instead. With
        # expire_on_commit=False the attribute survives commits and the
        # service's getattr(u, "skills", None) fallback reads it.
        user.skills = skills
    return user


# ============================================================================
# _get_db / _close_db
# ============================================================================

def test_get_db_injected_session_no_cm(svc):
    db, cm = svc._get_db()
    assert db is svc.db
    assert cm is None


def test_get_db_context_manager_path():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    sm = sessionmaker(bind=engine)

    class _CM:
        def __enter__(self):
            return sm()

        def __exit__(self, *a):
            return None

    svc = WorkforceAnalyticsService()
    with patch("core.workforce_analytics.get_db_session", return_value=_CM()):
        db, cm = svc._get_db()
        assert hasattr(db, "query")
        assert cm is not None
        svc._close_db(db, cm)


def test_get_db_plain_session_no_cm():
    """get_db_session returning a bare Session (no __enter__) → passed
    through with cm=None (caller manages lifecycle)."""

    class _Plain:
        def query(self, *a):
            return _FakeQuery([])

    fake = _Plain()
    svc = WorkforceAnalyticsService()
    with patch("core.workforce_analytics.get_db_session", return_value=fake):
        db, cm = svc._get_db()
    assert db is fake
    assert cm is None


class _NoDbSession:
    """Fake session for the no-injected-db path. Mirrors the real
    get_db_session() context-manager protocol (enter → session, exit →
    close)."""

    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.closed = True
        return None

    def query(self, *models):
        return _FakeQuery([])

    def close(self):
        self.closed = True


@pytest.mark.parametrize("method,args", [
    ("calculate_team_velocity", ("ws1",)),
    ("detect_bottlenecks", ("ws1",)),
    ("get_focus_score", ("u1",)),
    ("calculate_estimation_bias", ("ws1",)),
    ("map_skill_gaps", ("ws1",)),
])
def test_no_injected_session_closes_db(method, args):
    """R80 regression: the three legacy methods previously did
    ``db = self.db or get_db_session()`` and crashed with AttributeError on
    the un-entered context manager — every no-session call blew up instead
    of using the session. They now route through _get_db/_close_db and the
    session is closed in the finally block."""
    fake_session = _NoDbSession()
    svc = WorkforceAnalyticsService()
    with patch("core.workforce_analytics.get_db_session",
               return_value=fake_session):
        getattr(svc, method)(*args)
    assert fake_session.closed is True


# ============================================================================
# calculate_team_velocity
# ============================================================================

def test_team_velocity_empty(db, svc):
    result = svc.calculate_team_velocity("ws1", days=30)
    assert result == {"total_completed": 0, "avg_cycle_time_hours": 0.0,
                      "throughput_per_day": 0.0}


def test_team_velocity_with_cycle_times(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed",
               created_at=now - timedelta(hours=50),
               completed_at=now - timedelta(hours=10))
    _make_task(db, "t2", "ws1", status="completed",
               created_at=now - timedelta(hours=30),
               completed_at=now - timedelta(hours=20))
    result = svc.calculate_team_velocity("ws1", days=30)
    assert result["total_completed"] == 2
    assert result["avg_cycle_time_hours"] == 25.0
    assert result["throughput_per_day"] == pytest.approx(2 / 30)


def test_team_velocity_missing_timestamps_skipped(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed",
               created_at=null(), completed_at=now)
    _make_task(db, "t2", "ws1", status="completed",
               created_at=now - timedelta(hours=4),
               completed_at=now - timedelta(hours=2))
    result = svc.calculate_team_velocity("ws1", days=30)
    assert result["total_completed"] == 2
    assert result["avg_cycle_time_hours"] == 2.0


def test_team_velocity_outside_window_excluded(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed",
               created_at=now - timedelta(days=100),
               completed_at=now - timedelta(days=90))
    result = svc.calculate_team_velocity("ws1", days=30)
    assert result["total_completed"] == 0


def test_team_velocity_zero_days(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed",
               created_at=now - timedelta(hours=4),
               completed_at=now - timedelta(hours=2))
    result = svc.calculate_team_velocity("ws1", days=0)
    assert result["throughput_per_day"] == 0


# ============================================================================
# detect_bottlenecks
# ============================================================================

def test_detect_bottlenecks_empty(db, svc):
    assert svc.detect_bottlenecks("ws1") == []


def test_detect_bottlenecks_high_workload(db, svc):
    _make_project(db, "p1", "ws1")
    _make_user(db, "u1")
    for i in range(6):
        _make_task(db, f"t{i}", "ws1", status="in_progress", assigned_to="u1")
    bottlenecks = svc.detect_bottlenecks("ws1")
    assert len(bottlenecks) == 1
    assert bottlenecks[0]["user_id"] == "u1"
    assert bottlenecks[0]["user_name"] == "F L"
    assert bottlenecks[0]["reason"] == "high_workload"
    assert bottlenecks[0]["in_progress_count"] == 6
    assert bottlenecks[0]["severity"] == "medium"


def test_detect_bottlenecks_high_severity_unknown_user(db, svc):
    _make_project(db, "p1", "ws1")
    for i in range(8):
        _make_task(db, f"t{i}", "ws1", status="in_progress", assigned_to="ghost")
    bottlenecks = svc.detect_bottlenecks("ws1")
    assert bottlenecks[0]["severity"] == "high"
    assert bottlenecks[0]["user_name"] == "Unknown"


def test_detect_bottlenecks_stalled_tasks(db, svc):
    old = datetime.now() - timedelta(days=10)
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="in_progress", updated_at=old)
    _make_task(db, "t2", "ws1", status="in_progress",
               updated_at=datetime.now())
    bottlenecks = svc.detect_bottlenecks("ws1")
    assert len(bottlenecks) == 1
    assert bottlenecks[0]["task_id"] == "t1"
    assert bottlenecks[0]["reason"] == "stalled_progress"
    assert bottlenecks[0]["severity"] == "medium"
    assert "last_active" in bottlenecks[0]


# ============================================================================
# get_focus_score
# ============================================================================

def test_focus_score_no_active_tasks(db, svc):
    assert svc.get_focus_score("u1") == 100.0


def test_focus_score_single_project(db, svc):
    _make_project(db, "p1", "ws1")
    _make_project(db, "p2", "ws1")
    _make_task(db, "t1", "ws1", status="in_progress", assigned_to="u1",
               project_id="p1")
    _make_task(db, "t2", "ws1", status="in_progress", assigned_to="u1",
               project_id="p1")
    assert svc.get_focus_score("u1") == 100.0


def test_focus_score_multi_project_penalty(db, svc):
    _make_project(db, "p1", "ws1")
    _make_project(db, "p2", "ws1")
    _make_project(db, "p3", "ws1")
    _make_task(db, "t1", "ws1", status="in_progress", assigned_to="u1",
               project_id="p1")
    _make_task(db, "t2", "ws1", status="in_progress", assigned_to="u1",
               project_id="p2")
    _make_task(db, "t3", "ws1", status="in_progress", assigned_to="u1",
               project_id="p3")
    assert svc.get_focus_score("u1") == 70.0


def test_focus_score_penalty_clamped(db, svc):
    for i in range(9):
        _make_project(db, f"px{i}", "ws1")
    for i in range(9):
        _make_task(db, f"t{i}", "ws1", status="in_progress", assigned_to="u1",
                   project_id=f"px{i}")
    assert svc.get_focus_score("u1") == 0.0


# ============================================================================
# calculate_estimation_bias
# ============================================================================

def test_estimation_bias_no_data(db, svc):
    result = svc.calculate_estimation_bias("ws1")
    assert result["bias_factor"] == 1.0
    assert result["sample_size"] == 0
    assert result["status"] == "no_data"


def test_estimation_bias_duration_and_hour_variances(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed", assigned_to="u1",
               created_at=now - timedelta(days=10),
               due_date=now - timedelta(days=5),
               completed_at=now - timedelta(days=8),
               actual_hours=12.0,
               metadata_json={"estimated_hours": 10.0})
    result = svc.calculate_estimation_bias("ws1", user_id="u1")
    assert result["sample_size"] == 1
    assert result["duration_bias"] == pytest.approx(0.4, abs=0.01)
    assert result["hour_bias"] == pytest.approx(1.2, abs=0.01)
    # bias_factor = 0.4*0.4 + 0.6*1.2 = 0.88
    assert result["bias_factor"] == pytest.approx(0.88, abs=0.01)
    assert result["category"] == "pessimistic"


def test_estimation_bias_no_variance_data(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed",
               created_at=None, completed_at=None, due_date=None,
               actual_hours=0.0)
    result = svc.calculate_estimation_bias("ws1")
    assert result["duration_bias"] == 1.0
    assert result["hour_bias"] == 1.0
    assert result["bias_factor"] == 1.0
    assert result["category"] == "accurate"


def test_estimation_bias_optimistic_category(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed",
               created_at=now - timedelta(days=10),
               due_date=now - timedelta(days=5),
               completed_at=now - timedelta(days=1),
               actual_hours=4.0,
               metadata_json={"estimated_hours": 4.0})
    result = svc.calculate_estimation_bias("ws1")
    assert result["category"] == "optimistic"
    assert result["bias_factor"] > 1.1


def test_estimation_bias_zero_planned_delta_ignored(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed",
               created_at=now, due_date=now,
               completed_at=now - timedelta(hours=2),
               actual_hours=5.0)
    result = svc.calculate_estimation_bias("ws1")
    # planned_delta == 0 → duration variance skipped (1.0 baseline);
    # hour bias 5.0/1.0 = 5.0 → factor 3.4 → >1.1 maps to "optimistic"
    # (the module's category naming, kept as-is).
    assert result["duration_bias"] == 1.0
    assert result["hour_bias"] == 5.0
    assert result["category"] == "optimistic"
    assert result["bias_factor"] == pytest.approx(3.4, abs=0.01)


def test_get_user_bias_profile(db, svc):
    now = datetime.now()
    _make_project(db, "p1", "ws1")
    _make_task(db, "t1", "ws1", status="completed", assigned_to="u1",
               created_at=now - timedelta(days=10),
               due_date=now - timedelta(days=5),
               completed_at=now - timedelta(days=1),
               actual_hours=4.0,
               metadata_json={"estimated_hours": 4.0})
    profile = svc.get_user_bias_profile("u1", "ws1")
    assert profile["user_id"] == "u1"
    assert isinstance(profile["adjustment_multiplier"], float)
    assert profile["category"] in ["optimistic", "pessimistic", "accurate"]


# ============================================================================
# map_skill_gaps (skill paths — the ORM User model has the `skills` column
# commented out, so the skill-bearing branches are driven with a fake query
# layer instead of relying on ORM instance-attribute survival)
# ============================================================================

class _FakeQuery:
    """Chainable query stand-in: query(Model).filter(...).all() -> rows."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def group_by(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


def _fake_db(users, tasks):
    db = MagicMock()
    rows = {"users": users, "tasks": tasks}

    def query(model):
        if model.__name__ == "User":
            return _FakeQuery(rows["users"])
        return _FakeQuery(rows["tasks"])

    db.query = MagicMock(side_effect=query)
    return db


def _skill_user(uid, skills):
    return SimpleNamespace(id=uid, skills=skills, status="active")


def _skill_task(tid, *, status, assigned_to, required_skills):
    return SimpleNamespace(
        id=tid, name=f"Task {tid}", status=status, assigned_to=assigned_to,
        metadata_json={"required_skills": required_skills},
    )


def test_skill_gaps_no_users_empty(db, svc):
    fake_db = _fake_db([], [])
    with patch.object(svc, "_get_db", return_value=(fake_db, None)):
        result = svc.map_skill_gaps("ws1")
    assert result["team_size"] == 0
    assert result["unmet_requirements"] == {}
    assert result["assignment_mismatches"] == []
    assert result["competency_density"] == {}


def test_skill_gaps_unmet_and_mismatches(db, svc):
    fake_db = _fake_db(
        [_skill_user("u1", "Python, AI"), _skill_user("u2", "")],
        [
            _skill_task("t1", status="in_progress", assigned_to="u1",
                        required_skills=["python", "docker"]),
            _skill_task("t2", status="in_progress", assigned_to="u2",
                        required_skills="Python, SQL"),
        ],
    )
    with patch.object(svc, "_get_db", return_value=(fake_db, None)):
        result = svc.map_skill_gaps("ws1")
    assert result["team_size"] == 2
    assert result["competency_density"] == {"python": 1, "ai": 1}
    assert set(result["unmet_requirements"]) == {"docker", "sql"}
    assert result["unmet_requirements"]["docker"] == ["t1"]
    assert len(result["assignment_mismatches"]) == 2
    assert result["assignment_mismatches"][0]["missing_skills"] == ["docker"]


def test_skill_gaps_completed_task_exempt(db, svc):
    fake_db = _fake_db(
        [_skill_user("u1", "Python")],
        [
            _skill_task("t1", status="completed", assigned_to="u1",
                        required_skills=["docker"]),
        ],
    )
    with patch.object(svc, "_get_db", return_value=(fake_db, None)):
        result = svc.map_skill_gaps("ws1")
    assert result["unmet_requirements"] == {"docker": ["t1"]}
    assert result["assignment_mismatches"] == []


def test_skill_gaps_user_without_skills_attr(db, svc):
    fake_db = _fake_db(
        [_skill_user("u1", None)],
        [
            _skill_task("t1", status="in_progress", assigned_to="u1",
                        required_skills=["python"]),
        ],
    )
    with patch.object(svc, "_get_db", return_value=(fake_db, None)):
        result = svc.map_skill_gaps("ws1")
    assert result["unmet_requirements"] == {"python": ["t1"]}
    assert len(result["assignment_mismatches"]) == 1
    assert result["assignment_mismatches"][0]["missing_skills"] == ["python"]
