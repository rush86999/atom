# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/budget_guardrail.py.

TDD targets (red → green):
- ``BudgetGuardrailService.calculate_project_burn`` without an injected
  session used ``db = self.db or get_db_session()`` — ``get_db_session()``
  returns a *context manager*, not a ``Session``, so the no-session path
  crashed with ``AttributeError: '_GeneratorContextManager' object has no
  attribute 'query'``.
- ``_calculate_labor_burn`` read ``user.hourly_cost_rate``, a column that is
  commented out on the ``User`` model (core/models.py) — any task with an
  ``assigned_to`` crashed with ``AttributeError`` instead of falling back to
  the default $50/hr rate.
"""
import asyncio

import pytest
from core.budget_guardrail import BudgetGuardrailService


@pytest.fixture()
def db(monkeypatch):
    """Function-scoped in-memory SQLite with the budget-relevant tables, and
    SessionLocal patched so the service's get_db_session() hits it."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from accounting.models import Bill, Transaction
    from core.database import Base
    from core.models import User, Workspace
    from service_delivery.models import Milestone, Project, ProjectTask

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        bind=engine,
        tables=[Workspace.__table__, User.__table__, Project.__table__,
                Milestone.__table__, ProjectTask.__table__,
                Transaction.__table__, Bill.__table__],
    )
    session_factory = sessionmaker(bind=engine)
    # budget_guardrail does `from core.database import SessionLocal` — patch the
    # module-level name, not the core.database attribute.
    monkeypatch.setattr("core.budget_guardrail.SessionLocal", session_factory)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _workspace(session, ws_id="ws-1"):
    from core.models import Workspace

    ws = Workspace(id=ws_id, name="Acme")
    session.add(ws)
    return ws


def _project(session, pid="proj-1", ws_id="ws-1", budget_amount=1000.0):
    from service_delivery.models import Project

    proj = Project(id=pid, workspace_id=ws_id, name="Website", budget_amount=budget_amount)
    session.add(proj)
    return proj


def _milestone(session, mid="ms-1", pid="proj-1", ws_id="ws-1"):
    from service_delivery.models import Milestone

    ms = Milestone(id=mid, workspace_id=ws_id, project_id=pid, name="Phase 1")
    session.add(ms)
    return ms


def _task(session, tid="task-1", pid="proj-1", mid="ms-1", ws_id="ws-1",
          hours=10.0, assigned_to=None):
    from service_delivery.models import ProjectTask

    task = ProjectTask(
        id=tid, workspace_id=ws_id, project_id=pid, milestone_id=mid,
        name="Task 1", actual_hours=hours, assigned_to=assigned_to,
    )
    session.add(task)
    return task


def _transaction(session, amount, pid="proj-1", ws_id="ws-1", tx_id="tx-1"):
    from accounting.models import Transaction
    from datetime import datetime, timezone

    tx = Transaction(
        id=tx_id, workspace_id=ws_id, source="manual", amount=amount,
        transaction_date=datetime.now(timezone.utc), project_id=pid,
    )
    session.add(tx)
    return tx


def _bill(session, amount, pid="proj-1", ws_id="ws-1", bill_id="bill-1"):
    from accounting.models import Bill
    from datetime import datetime, timezone

    bill = Bill(
        id=bill_id, workspace_id=ws_id, vendor_id="vendor-1", amount=amount,
        issue_date=datetime.now(timezone.utc), due_date=datetime.now(timezone.utc),
        project_id=pid,
    )
    session.add(bill)
    return bill


class TestLaborBurn:
    def test_labor_uses_default_rate_when_unassigned(self, db):
        _workspace(db)
        _project(db)
        _milestone(db)
        _task(db, hours=10.0, assigned_to=None)
        db.commit()

        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["labor_burn"] == pytest.approx(500.0)  # 10h * $50 default

    def test_labor_uses_assigned_user_rate(self, db):
        """RED: the User model has no hourly_cost_rate column (commented out)
        — the lookup crashed instead of falling back to the $50 default."""
        from core.models import User

        _workspace(db)
        _project(db)
        _milestone(db)
        user = User(id="u-1", email="dev@acme.com", first_name="Dev", last_name="One",
                    role="user", status="active")
        db.add(user)
        _task(db, hours=4.0, assigned_to="u-1")
        db.commit()

        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["labor_burn"] == pytest.approx(200.0)

    def test_labor_ignores_missing_hours(self, db):
        _workspace(db)
        _project(db)
        _milestone(db)
        _task(db, hours=None, assigned_to=None)
        db.commit()

        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["labor_burn"] == 0.0

    def test_labor_only_counts_this_projects_tasks(self, db):
        from service_delivery.models import Project, ProjectTask, Milestone

        _workspace(db)
        _project(db, pid="proj-1")
        _project(db, pid="proj-2")
        _milestone(db)
        _milestone(db, mid="ms-2", pid="proj-2")
        db.add(ProjectTask(id="t-other", workspace_id="ws-1", project_id="proj-2",
                           milestone_id="ms-2", name="Other", actual_hours=99.0))
        _task(db, hours=2.0)
        db.commit()

        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["labor_burn"] == pytest.approx(100.0)


class TestExpenseBurn:
    def test_expense_sums_transactions_and_bills(self, db):
        _workspace(db)
        _project(db)
        _milestone(db)
        _transaction(db, 120.50, tx_id="tx-1")
        _transaction(db, 30.0, tx_id="tx-2")
        _bill(db, 250.0, bill_id="bill-1")
        db.commit()

        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["expense_burn"] == pytest.approx(400.5)

    def test_expense_zero_when_none_linked(self, db):
        _workspace(db)
        _project(db)
        _milestone(db)
        _task(db, hours=0.0)
        db.commit()

        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["expense_burn"] == 0.0
        assert result["total_burn"] == 0.0


class TestBurnAggregation:
    def test_total_burn_and_project_update(self, db):
        from service_delivery.models import Project

        _workspace(db)
        _project(db, budget_amount=1000.0)
        _milestone(db)
        _task(db, hours=10.0, assigned_to=None)  # 500 labor
        _bill(db, 200.0)
        db.commit()

        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["total_burn"] == pytest.approx(700.0)
        proj = db.query(Project).filter(Project.id == "proj-1").first()
        assert proj.actual_burn == pytest.approx(700.0)

    def test_unknown_project_returns_unknown_status(self, db):
        result = asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("ghost"))
        assert result["status"] == "unknown"
        assert result["total_burn"] == 0.0


class TestStatusThresholds:
    def _burn(self, db, budget, ratio):
        _workspace(db)
        _project(db, budget_amount=budget)
        _milestone(db)
        _task(db, hours=0.0)
        _bill(db, budget * ratio)
        db.commit()
        return asyncio.run(BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))

    def test_on_track_below_80_percent(self, db):
        result = self._burn(db, 1000.0, 0.5)
        assert result["status"] == "on_track"

    def test_at_risk_at_80_percent(self, db):
        result = self._burn(db, 1000.0, 0.8)
        assert result["status"] == "at_risk"

    def test_over_budget_at_100_percent(self, db):
        result = self._burn(db, 1000.0, 1.0)
        assert result["status"] == "over_budget"

    def test_over_budget_above_100_percent(self, db):
        result = self._burn(db, 1000.0, 1.5)
        assert result["status"] == "over_budget"

    def test_no_budget_means_on_track(self, db):
        result = self._burn(db, 0.0, 5.0)
        assert result["status"] == "on_track"


class TestDefaultSession:
    def test_works_without_injected_session(self, worker_database, monkeypatch):
        """RED: no injected session used get_db_session() as if it were a
        Session — the whole no-session path crashed."""
        monkeypatch.setattr("core.budget_guardrail.SessionLocal", worker_database)
        db = worker_database()
        _workspace(db)
        _project(db, budget_amount=500.0)
        _milestone(db)
        _task(db, hours=2.0)
        db.commit()
        db.close()

        result = asyncio.run(BudgetGuardrailService().calculate_project_burn("proj-1"))
        assert result["total_burn"] == pytest.approx(100.0)
        assert result["status"] == "on_track"
