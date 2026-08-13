# -*- coding: utf-8 -*-
"""Coverage wave 80 — core/pm_engine.py to >=95% (standalone, in-memory
SQLite; ai_service/GraphRAG/reasoning/swarm fully mocked — zero LLM spend,
zero network).

Covers:
- generate_project_from_nl: success (milestones+tasks, flush), nlu_result
  key form, no milestones, no tasks, defaults, failure → {"status":
  "failed"}, session close for non-injected db, bias adjustment.
- infer_project_status: project not found, completed-task skip, evidence
  "completed"/"started" inference, milestone auto-completion, success
  summary.
- analyze_project_risks: no project, schedule risk, milestone slip (incl.
  completed milestone exemption), budget overrun, risk levels high/medium/
  low.
- auto_assign_resources: no tasks, already-assigned skip, suggestion without
  user, assignment recorded with confidence.
- trigger_autonomous_correction: swarm success + exception → failed.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.models  # noqa: F401 (register models)
import service_delivery.models  # noqa: F401
from core.database import Base
from core.pm_engine import AIProjectManager
from service_delivery.models import (
    Milestone,
    MilestoneStatus,
    Project,
    ProjectStatus,
    ProjectTask,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def engine(db):
    with patch("core.pm_engine.KnowledgeExtractor"), \
         patch("core.pm_engine.get_ai_service") as get_ai, \
         patch("core.pm_engine.ResourceReasoningEngine") as make_reasoning:
        ai = MagicMock()
        ai.process_with_nlu = AsyncMock()
        get_ai.return_value = ai
        pm = AIProjectManager(db_session=db)
        pm.ai = ai
        return pm


def _make_project(db, pid="proj1", ws="ws1", *, status=ProjectStatus.PENDING,
                  planned_end=None, budget_hours=0.0, actual_hours=0.0):
    project = Project(
        id=pid, workspace_id=ws, name=f"Project {pid}",
        status=status, planned_end_date=planned_end,
        budget_hours=budget_hours, actual_hours=actual_hours,
    )
    db.add(project)
    db.commit()
    return project


def _make_milestone(db, mid, project_id="proj1", ws="ws1", *,
                    status=MilestoneStatus.PENDING, due=None):
    ms = Milestone(
        id=mid, workspace_id=ws, project_id=project_id, name=f"M {mid}",
        order=0, status=status, due_date=due,
    )
    db.add(ms)
    db.commit()
    return ms


def _make_task(db, tid, project_id="proj1", milestone_id="ms1", ws="ws1",
               *, status="pending", name=None, assigned_to=None,
               description=None):
    task = ProjectTask(
        id=tid, workspace_id=ws, project_id=project_id,
        milestone_id=milestone_id, name=name or f"Task {tid}",
        status=status, assigned_to=assigned_to, description=description,
    )
    db.add(task)
    db.commit()
    return task


# ============================================================================
# generate_project_from_nl
# ============================================================================

@pytest.mark.asyncio
async def test_generate_project_from_nl_success(engine, db):
    engine.ai.process_with_nlu.return_value = {
        "nlu_result": {
            "name": "Launch Website",
            "description": "Full launch",
            "priority": "high",
            "planned_duration_days": 30,
            "budget_amount": 5000,
            "milestones": [
                {
                    "name": "Design", "order": 1, "planned_start_day": 0,
                    "duration_days": 5,
                    "tasks": [
                        {"name": "Wireframes", "description": "Draw"},
                    ],
                },
            ],
        }
    }
    result = await engine.generate_project_from_nl(
        "launch a website", "user1", "ws1", contract_id="ct1")
    assert result["status"] == "success"
    assert result["name"] == "Launch Website"
    project = db.query(Project).filter(Project.id == result["project_id"]).first()
    assert project.contract_id == "ct1"
    assert project.priority == "high"
    assert project.budget_amount == 5000.0
    assert project.status == ProjectStatus.PENDING
    ms = db.query(Milestone).filter(Milestone.project_id == project.id).first()
    assert ms.name == "Design"
    task = db.query(ProjectTask).filter(
        ProjectTask.milestone_id == ms.id).first()
    assert task.name == "Wireframes"
    assert task.status == "pending"


@pytest.mark.asyncio
async def test_generate_project_from_nl_defaults_and_bias(engine, db):
    engine.ai.process_with_nlu.return_value = {"nlu_result": {}}
    engine.analytics.calculate_estimation_bias = MagicMock(
        return_value={"bias_factor": 2.0})
    result = await engine.generate_project_from_nl("build app", "user1", "ws1")
    assert result["status"] == "success"
    project = db.query(Project).filter(Project.id == result["project_id"]).first()
    assert project.name == "New AI Generated Project"
    assert project.priority == "medium"
    assert project.budget_amount == 0.0
    # planned 30 days * bias 2.0
    expected_end = project.planned_start_date + timedelta(days=60)
    assert project.planned_end_date == expected_end


@pytest.mark.asyncio
async def test_generate_project_from_nl_ai_failure(engine, db):
    engine.ai.process_with_nlu = AsyncMock(side_effect=RuntimeError("llm down"))
    result = await engine.generate_project_from_nl("x", "user1", "ws1")
    assert result["status"] == "failed"
    assert "llm down" in result["error"]


@pytest.mark.asyncio
async def test_generate_project_from_nl_closes_session():
    class _FakeAI:
        def __init__(self):
            self.process_with_nlu = AsyncMock(return_value={"nlu_result": {}})

    ai = _FakeAI()
    closed = []

    class _FakeDb:
        def __init__(self):
            self.added = 0

        def add(self, obj):
            self.added += 1

        def flush(self):
            pass

        def commit(self):
            pass

        def close(self):
            closed.append(True)

    fake_db = _FakeDb()
    with patch("core.pm_engine.KnowledgeExtractor"), \
         patch("core.pm_engine.get_db_session", return_value=fake_db):
        pm = AIProjectManager()
        pm.ai = ai
        pm.analytics.calculate_estimation_bias = MagicMock(
            return_value={"bias_factor": 1.0})
        result = await pm.generate_project_from_nl("x", "user1", "ws1")
    assert result["status"] == "success"
    assert closed == [True]


# ============================================================================
# infer_project_status
# ============================================================================

@pytest.mark.asyncio
async def test_infer_project_status_not_found(engine, db):
    result = await engine.infer_project_status("missing", "user1")
    assert result == {"status": "error", "message": "Project not found"}


@pytest.mark.asyncio
async def test_infer_project_status_inferences(engine, db):
    _make_project(db, "proj1", "ws1")
    _make_milestone(db, "ms1", "proj1", "ws1")
    _make_task(db, "t1", "proj1", "ms1", "ws1", status="pending",
               name="Deploy")
    _make_task(db, "t2", "proj1", "ms1", "ws1", status="completed",
               name="Done task")
    _make_milestone(db, "ms2", "proj1", "ws1")
    _make_task(db, "t3", "proj1", "ms2", "ws1", status="pending",
               name="Pending")

    async def fake_query(user_id, query, mode="local"):
        if "Deploy" in query:
            return {"answer": "The task is completed and verified."}
        if "Pending" in query:
            return {"answer": "Work is in progress."}
        return {"answer": "no evidence"}

    with patch("core.pm_engine.graphrag_engine") as graphrag:
        graphrag.query = AsyncMock(side_effect=fake_query)
        result = await engine.infer_project_status("proj1", "user1")
    assert result["status"] == "success"
    updates = result["updates"]
    assert any("Deploy" in u and "COMPLETED" in u for u in updates)
    assert any("Pending" in u and "IN_PROGRESS" in u for u in updates)
    assert any("Milestone 'M ms1' marked as COMPLETED" in u for u in updates)
    task = db.query(ProjectTask).filter(ProjectTask.id == "t1").first()
    assert task.status == "completed"
    assert task.completed_at is not None
    t3 = db.query(ProjectTask).filter(ProjectTask.id == "t3").first()
    assert t3.status == "in_progress"
    ms1 = db.query(Milestone).filter(Milestone.id == "ms1").first()
    assert ms1.status == MilestoneStatus.COMPLETED
    assert ms1.completed_at is not None
    ms2 = db.query(Milestone).filter(Milestone.id == "ms2").first()
    assert ms2.status == MilestoneStatus.PENDING


# ============================================================================
# analyze_project_risks
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_project_risks_not_found(engine, db):
    result = await engine.analyze_project_risks("missing", "user1")
    assert result == {"status": "error", "message": "Project not found"}


@pytest.mark.asyncio
async def test_analyze_project_risks_schedule_and_budget(engine, db):
    past = datetime.now() - timedelta(days=5)
    _make_project(db, "proj1", "ws1", status=ProjectStatus.ACTIVE,
                  planned_end=past, budget_hours=100, actual_hours=150)
    _make_milestone(db, "ms1", "proj1", "ws1", due=past)
    _make_milestone(db, "ms2", "proj1", "ws1",
                    status=MilestoneStatus.COMPLETED, due=past)
    result = await engine.analyze_project_risks("proj1", "user1")
    assert result["status"] == "success"
    types = [r["type"] for r in result["risks"]]
    assert "schedule" in types
    assert "milestone_slip" in types
    assert "budget" in types
    # completed milestone is exempt from slippage
    slip_targets = [r.get("milestone") for r in result["risks"]
                    if r["type"] == "milestone_slip"]
    assert "M ms2" not in slip_targets
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_analyze_project_risks_medium_level(engine, db):
    _make_project(db, "proj1", "ws1", status=ProjectStatus.PENDING,
                  planned_end=datetime.now() + timedelta(days=30))
    past = datetime.now() - timedelta(days=1)
    _make_milestone(db, "ms1", "proj1", "ws1", due=past)
    result = await engine.analyze_project_risks("proj1", "user1")
    assert result["risk_level"] == "medium"
    assert result["risks"][0]["type"] == "milestone_slip"


@pytest.mark.asyncio
async def test_analyze_project_risks_low_level(engine, db):
    _make_project(db, "proj1", "ws1", status=ProjectStatus.ACTIVE,
                  planned_end=datetime.now() + timedelta(days=30),
                  budget_hours=100, actual_hours=50)
    result = await engine.analyze_project_risks("proj1", "user1")
    assert result["risk_level"] == "low"
    assert result["risks"] == []


# ============================================================================
# auto_assign_resources
# ============================================================================

@pytest.mark.asyncio
async def test_auto_assign_resources_assigns_and_skips(engine, db):
    _make_project(db, "proj1", "ws1")
    _make_milestone(db, "ms1", "proj1", "ws1")
    _make_task(db, "t1", "proj1", "ms1", "ws1", status="pending")
    _make_task(db, "t2", "proj1", "ms1", "ws1", status="pending",
               assigned_to="existing-user")
    _make_task(db, "t3", "proj1", "ms1", "ws1", status="pending")

    async def fake_assignee(workspace_id, task_name, task_description=None):
        if task_name == "Task t1":
            return {"suggested_user": {
                "user_id": "u9", "name": "Alice", "composite_score": 0.87}}
        return {"suggested_user": None}

    engine.reasoning.get_optimal_assignee = AsyncMock(side_effect=fake_assignee)
    result = await engine.auto_assign_resources("proj1", "ws1")
    assert result["status"] == "success"
    assert len(result["assignments"]) == 1
    assert result["assignments"][0]["task_id"] == "t1"
    assert result["assignments"][0]["assigned_to"] == "Alice"
    assert result["assignments"][0]["confidence"] == 0.87
    t1 = db.query(ProjectTask).filter(ProjectTask.id == "t1").first()
    assert t1.assigned_to == "u9"
    t2 = db.query(ProjectTask).filter(ProjectTask.id == "t2").first()
    assert t2.assigned_to == "existing-user"


@pytest.mark.asyncio
async def test_auto_assign_resources_no_tasks(engine, db):
    result = await engine.auto_assign_resources("proj1", "ws1")
    assert result == {"status": "success", "assignments": []}


# ============================================================================
# trigger_autonomous_correction
# ============================================================================

@pytest.mark.asyncio
async def test_trigger_autonomous_correction_success(engine, db):
    with patch("core.pm_engine.AutonomousBusinessSwarm") as swarm_cls:
        swarm = MagicMock()
        swarm.run_correction_cycle = AsyncMock(
            return_value={"status": "ok", "changes": 3})
        swarm_cls.return_value = swarm
        result = await engine.trigger_autonomous_correction("ws1", "proj1")
    swarm_cls.assert_called_once_with(db_session=engine.db_session)
    swarm.run_correction_cycle.assert_awaited_once_with("ws1", "proj1")
    assert result == {"status": "ok", "changes": 3}


@pytest.mark.asyncio
async def test_trigger_autonomous_correction_failure(engine, db):
    with patch("core.pm_engine.AutonomousBusinessSwarm") as swarm_cls:
        swarm = MagicMock()
        swarm.run_correction_cycle = AsyncMock(
            side_effect=RuntimeError("swarm exploded"))
        swarm_cls.return_value = swarm
        result = await engine.trigger_autonomous_correction("ws1")
    assert result == {"status": "failed", "error": "swarm exploded"}


# ============================================================================
# non-injected session plumbing (db.close() in finally)
# ============================================================================

class _ClosedSession:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.closed = True
        return None

    def query(self, model):
        return _EmptyQuery()

    def add(self, obj):
        pass

    def flush(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class _EmptyQuery:
    def filter(self, *a, **k):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def count(self):
        return 0


@pytest.mark.asyncio
async def test_infer_project_status_closes_borrowed_session():
    fake = _ClosedSession()
    with patch("core.pm_engine.KnowledgeExtractor"), \
         patch("core.pm_engine.get_ai_service"), \
         patch("core.pm_engine.ResourceReasoningEngine"), \
         patch("core.pm_engine.get_db_session", return_value=fake):
        pm = AIProjectManager()
        result = await pm.infer_project_status("nope", "user1")
    assert result == {"status": "error", "message": "Project not found"}
    assert fake.closed is True


@pytest.mark.asyncio
async def test_analyze_project_risks_closes_borrowed_session():
    fake = _ClosedSession()
    with patch("core.pm_engine.KnowledgeExtractor"), \
         patch("core.pm_engine.get_ai_service"), \
         patch("core.pm_engine.ResourceReasoningEngine"), \
         patch("core.pm_engine.get_db_session", return_value=fake):
        pm = AIProjectManager()
        result = await pm.analyze_project_risks("nope", "user1")
    assert result == {"status": "error", "message": "Project not found"}
    assert fake.closed is True


@pytest.mark.asyncio
async def test_auto_assign_resources_closes_borrowed_session():
    fake = _ClosedSession()
    with patch("core.pm_engine.KnowledgeExtractor"), \
         patch("core.pm_engine.get_ai_service"), \
         patch("core.pm_engine.ResourceReasoningEngine"), \
         patch("core.pm_engine.get_db_session", return_value=fake):
        pm = AIProjectManager()
        result = await pm.auto_assign_resources("nope", "ws1")
    assert result == {"status": "success", "assignments": []}
    assert fake.closed is True
