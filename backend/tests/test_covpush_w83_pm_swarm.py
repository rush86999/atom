# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/pm_swarm.py to >=95% (in-memory SQLite with the
real Project/ProjectTask/Milestone models; analytics service mocked; zero LLM
spend, zero network).

Covers:
- run_correction_cycle: no project (general ops), project found (state
  gathering with overdue tasks), project missing, learning-phase gate
  (learning_mode + hitl_request), approved path applies corrections,
  finally-closes self-managed db, injected db left open.
- _gather_state: with/without project, missing project warning.
- _planner_propose: no overdue/skill gaps (empty actions), overdue ->
  extend_timeline, skill mismatches -> reassign_task.
- _risk_critique: ok, bias > 1.2 -> request_change.
- _finance_critique: always ok.
- _executor_critique: ok, unmet skill blocker.
- _auditor_finalize: approved, blocker -> pending_user + hitl, risk
  adjustment adds 3 days.
- _apply_corrections: extend_timeline (project found/missing), reassign_task
  (task found/missing, metadata_json None/empty), commit called.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.models  # noqa: F401 (register models)
import service_delivery.models  # noqa: F401
from core.database import Base
from core.pm_swarm import AutonomousBusinessSwarm
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
def swarm(db):
    with patch("core.pm_swarm.WorkforceAnalyticsService") as analytics_cls:
        analytics_cls.return_value.calculate_estimation_bias.return_value = {"bias_factor": 1.0}
        analytics_cls.return_value.map_skill_gaps.return_value = {
            "assignment_mismatches": [],
            "unmet_requirements": {},
        }
        s = AutonomousBusinessSwarm(db_session=db)
        s._analytics_cls = analytics_cls
        yield s


def _make_project(db, pid="p1", ws="ws1", planned_end_date=None):
    if planned_end_date is None:
        planned_end_date = datetime.now() + timedelta(days=30)
    project = Project(
        id=pid,
        workspace_id=ws,
        name="Project P",
        status="active",
        planned_end_date=planned_end_date,
    )
    db.add(project)
    db.commit()
    return project


def _make_project_no_end_date(db, pid="p2", ws="ws1"):
    project = Project(
        id=pid,
        workspace_id=ws,
        name="Project P",
        status="active",
        planned_end_date=None,
    )
    db.add(project)
    db.commit()
    return project


def _make_task(db, tid, pid="p1", due_date=None, status="pending", assigned_to="u1", ws="ws1"):
    task = ProjectTask(
        id=tid,
        workspace_id=ws,
        project_id=pid,
        milestone_id=f"m-{pid}",
        name=f"Task {tid}",
        status=status,
        due_date=due_date,
        assigned_to=assigned_to,
    )
    db.add(task)
    db.commit()
    return task


# ============================================================================
# run_correction_cycle
# ============================================================================

def test_run_correction_cycle_general_ops_no_project(db, swarm):
    result = __import__("asyncio").run(swarm.run_correction_cycle("ws1"))
    assert result["workspace_id"] == "ws1"
    assert result["project_id"] is None
    assert result["decision"]["status"] == "approved"
    assert result["negotiation_log"]["proposal"]["type"] == "stabilization"


def test_run_correction_cycle_approved_applies_extend(db, swarm):
    project = _make_project(db)
    _make_task(db, "t1", due_date=datetime.now() - timedelta(days=1))
    result = __import__("asyncio").run(swarm.run_correction_cycle("ws1", project.id))
    assert result["decision"]["status"] == "approved"
    assert result["decision"]["actions"][0]["action"] == "extend_timeline"
    assert result["decision"]["actions"][0]["days"] == 7


def test_run_correction_cycle_missing_project_is_noop(db, swarm):
    result = __import__("asyncio").run(swarm.run_correction_cycle("ws1", "ghost"))
    assert result["decision"]["status"] == "approved"
    assert result["decision"]["actions"] == []


def test_run_correction_cycle_learning_mode_gate(db, swarm):
    project = _make_project(db)
    _make_task(db, "t1", due_date=datetime.now() - timedelta(days=1))
    workspace = db.query(core.models.Workspace).filter(core.models.Workspace.id == "ws1").first()
    if workspace is None:
        workspace = core.models.Workspace(id="ws1", name="WS1", tenant_id="tenant-1")
        db.add(workspace)
    workspace.is_startup = False
    workspace.learning_phase_completed = False
    db.commit()
    result = __import__("asyncio").run(swarm.run_correction_cycle("ws1", project.id))
    assert result["decision"]["status"] == "learning_mode"
    assert result["decision"]["hitl_request"]


def test_run_correction_cycle_learning_mode_skipped_for_startup(db, swarm):
    project = _make_project(db)
    _make_task(db, "t1", due_date=datetime.now() - timedelta(days=1))
    workspace = core.models.Workspace(id="ws1", name="WS1", tenant_id="tenant-1")
    workspace.is_startup = True
    workspace.learning_phase_completed = False
    db.add(workspace)
    db.commit()
    result = __import__("asyncio").run(swarm.run_correction_cycle("ws1", project.id))
    assert result["decision"]["status"] == "approved"


def test_run_correction_cycle_self_managed_db_closed():
    with patch("core.pm_swarm.WorkforceAnalyticsService") as analytics_cls:
        analytics_cls.return_value.calculate_estimation_bias.return_value = {"bias_factor": 1.0}
        analytics_cls.return_value.map_skill_gaps.return_value = {
            "assignment_mismatches": [], "unmet_requirements": {},
        }
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.pm_swarm.get_db_session") as get_session:
            get_session.return_value.__enter__.return_value = fake_db
            swarm = AutonomousBusinessSwarm(db_session=None)
            __import__("asyncio").run(swarm.run_correction_cycle("ws1"))
    fake_db.close.assert_called_once()


def test_run_correction_cycle_injected_db_not_closed(db, swarm):
    project = _make_project(db)
    result = __import__("asyncio").run(swarm.run_correction_cycle("ws1", project.id))
    assert result["workspace_id"] == "ws1"
    # session still usable after the cycle
    assert db.query(Project).count() == 1


# ============================================================================
# _gather_state
# ============================================================================

def test_gather_state_with_project(db, swarm):
    project = _make_project(db)
    _make_task(db, "t1", due_date=datetime.now() - timedelta(days=1))
    _make_task(db, "t2", due_date=datetime.now() + timedelta(days=5), status="completed")
    state = swarm._gather_state("ws1", project.id, db)
    assert state["workspace_id"] == "ws1"
    assert state["project"]["id"] == project.id
    assert state["project"]["tasks_total"] == 2
    assert state["project"]["tasks_overdue"] == 1
    assert "timestamp" in state
    assert "bias_profile" in state and "skill_gaps" in state


def test_gather_state_without_project(db, swarm):
    state = swarm._gather_state("ws1", None, db)
    assert "project" not in state


def test_gather_state_missing_project_warns(db, swarm):
    state = swarm._gather_state("ws1", "ghost", db)
    assert "project" not in state


def test_gather_state_planned_end_date_none(db, swarm):
    project = _make_project_no_end_date(db)
    state = swarm._gather_state("ws1", project.id, db)
    assert state["project"]["planned_end_date"] is None


# ============================================================================
# _planner_propose
# ============================================================================

def test_planner_propose_no_issues():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    state = {
        "skill_gaps": {"assignment_mismatches": []},
    }
    proposal = swarm._planner_propose(state)
    assert proposal == {"type": "stabilization", "actions": []}


def test_planner_propose_overdue_extends_timeline():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    state = {
        "project": {"id": "p1", "tasks_overdue": 2},
        "skill_gaps": {"assignment_mismatches": []},
    }
    proposal = swarm._planner_propose(state)
    assert proposal["actions"][0]["action"] == "extend_timeline"
    assert proposal["actions"][0]["days"] == 7
    assert proposal["actions"][0]["project_id"] == "p1"


def test_planner_propose_skill_mismatch_reassigns():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    state = {
        "project": {"id": "p1", "tasks_overdue": 0},
        "skill_gaps": {
            "assignment_mismatches": [
                {"task_id": "t9", "missing_skills": "sql"}
            ]
        },
    }
    proposal = swarm._planner_propose(state)
    action = proposal["actions"][0]
    assert action["action"] == "reassign_task"
    assert action["task_id"] == "t9"
    assert action["project_id"] == "p1"


# ============================================================================
# critiques
# ============================================================================

def test_risk_critique_ok():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    assert swarm._risk_critique(
        {"actions": [{"action": "reassign_task"}]},
        {"bias_profile": {"bias_factor": 1.1}},
    ) == {"status": "ok"}


def test_risk_critique_optimistic_bias_requests_change():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    critique = swarm._risk_critique(
        {"actions": [{"action": "extend_timeline"}]},
        {"bias_profile": {"bias_factor": 1.5}},
    )
    assert critique["status"] == "request_change"
    assert "3 more days" in critique["adjustment"]


def test_risk_critique_default_bias_factor():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    assert swarm._risk_critique(
        {"actions": [{"action": "extend_timeline"}]},
        {"bias_profile": {}},
    ) == {"status": "ok"}


def test_finance_critique_always_ok():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    assert swarm._finance_critique({"actions": []}, {}) == {"status": "ok"}


def test_executor_critique_ok():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    assert swarm._executor_critique(
        {"actions": [{"action": "reassign_task", "reason": "Missing skills: sql"}]},
        {"skill_gaps": {"unmet_requirements": {"python"}}},
    ) == {"status": "ok"}


def test_executor_critique_blocker_on_unmet_skill():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    critique = swarm._executor_critique(
        {"actions": [{"action": "reassign_task", "reason": "Missing skills: sql"}]},
        {"skill_gaps": {"unmet_requirements": {"sql"}}},
    )
    assert critique == {"status": "blocker", "reason": "missing_skill_data"}


# ============================================================================
# _auditor_finalize
# ============================================================================

def test_auditor_finalize_approved():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    decision = swarm._auditor_finalize(
        {"actions": [{"action": "x"}]},
        [{"status": "ok"}, {"status": "ok"}],
        {},
    )
    assert decision["status"] == "approved"
    assert decision["hitl_request"] is None


def test_auditor_finalize_blocker_triggers_hitl():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    decision = swarm._auditor_finalize(
        {"actions": []},
        [{"status": "blocker", "reason": "missing_skill_data"}],
        {},
    )
    assert decision["status"] == "pending_user"
    assert decision["hitl_request"]


def test_auditor_finalize_risk_adjustment_applies_3_days():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    decision = swarm._auditor_finalize(
        {"actions": [{"action": "extend_timeline", "days": 7}]},
        [{"status": "request_change", "adjustment": "Add 3 more days due to historical bias."}],
        {},
    )
    assert decision["actions"][0]["days"] == 10


def test_auditor_finalize_request_change_without_matching_action():
    swarm = AutonomousBusinessSwarm(db_session=MagicMock())
    decision = swarm._auditor_finalize(
        {"actions": [{"action": "other", "days": 7}]},
        [{"status": "request_change", "adjustment": "Add 3 more days"}],
        {},
    )
    assert decision["status"] == "approved"
    assert decision["actions"][0]["days"] == 7


# ============================================================================
# _apply_corrections
# ============================================================================

def test_apply_corrections_extend_timeline(db):
    project = _make_project(db, planned_end_date=datetime(2026, 9, 1))
    swarm = AutonomousBusinessSwarm(db_session=db)
    decision = {"actions": [{"action": "extend_timeline", "project_id": "p1", "days": 7}]}
    swarm._apply_corrections(decision, db)
    assert project.planned_end_date == datetime(2026, 9, 8)
    assert project.planned_end_date == db.query(Project).filter(Project.id == "p1").first().planned_end_date


def test_apply_corrections_extend_missing_project_noop(db):
    swarm = AutonomousBusinessSwarm(db_session=db)
    swarm._apply_corrections({"actions": [{"action": "extend_timeline", "project_id": "ghost", "days": 7}]}, db)


def test_apply_corrections_extend_without_project_id(db):
    swarm = AutonomousBusinessSwarm(db_session=db)
    swarm._apply_corrections({"actions": [{"action": "extend_timeline", "days": 7}]}, db)


def test_apply_corrections_reassign_task_with_metadata(db):
    task = _make_task(db, "t1", assigned_to="u1")
    swarm = AutonomousBusinessSwarm(db_session=db)
    decision = {
        "actions": [{
            "action": "reassign_task", "task_id": "t1",
            "reason": "Missing skills: sql",
        }]
    }
    swarm._apply_corrections(decision, db)
    db.refresh(task)
    assert task.assigned_to is None
    assert task.metadata_json["needs_reassignment"] is True
    assert task.metadata_json["reassignment_reason"] == "Missing skills: sql"


def test_apply_corrections_reassign_task_existing_metadata(db):
    task = _make_task(db, "t1", assigned_to="u1")
    task.metadata_json = {"prev": 1}
    db.commit()
    swarm = AutonomousBusinessSwarm(db_session=db)
    decision = {"actions": [{"action": "reassign_task", "task_id": "t1", "reason": "r"}]}
    swarm._apply_corrections(decision, db)
    db.refresh(task)
    assert task.metadata_json["prev"] == 1
    assert task.metadata_json["needs_reassignment"] is True


def test_apply_corrections_reassign_missing_task_noop(db):
    swarm = AutonomousBusinessSwarm(db_session=db)
    swarm._apply_corrections({"actions": [{"action": "reassign_task", "task_id": "ghost", "reason": "r"}]}, db)


def test_apply_corrections_reassign_without_task_id(db):
    swarm = AutonomousBusinessSwarm(db_session=db)
    swarm._apply_corrections({"actions": [{"action": "reassign_task", "reason": "r"}]}, db)


def test_apply_corrections_unknown_action_ignored(db):
    swarm = AutonomousBusinessSwarm(db_session=db)
    swarm._apply_corrections({"actions": [{"action": "frobnicate"}]}, db)
