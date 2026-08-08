# -*- coding: utf-8 -*-
"""Bug-hunt tests for core/budget_guardrail.py (finance: budget enforcement).

Net-new bug found via TDD (red -> green). See the ``BUG:`` docstring.
"""
import asyncio
from datetime import datetime, timezone

import pytest
from core.budget_guardrail import BudgetGuardrailService


@pytest.fixture()
def db(monkeypatch):
    """In-memory SQLite with the budget-relevant tables (mirrors the fixture
    in tests/test_r80_budget_guardrail.py)."""
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
    monkeypatch.setattr("core.budget_guardrail.SessionLocal", session_factory)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed(session, *, budget=1000.0, actual_burn=None, warn=80, block=100,
          pid="proj-1", ws_id="ws-1"):
    """Seed a workspace + project with configurable budget thresholds."""
    from core.models import Workspace
    from service_delivery.models import Project

    session.add(Workspace(id=ws_id, name="Acme"))
    proj = Project(
        id=pid, workspace_id=ws_id, name="Website",
        budget_amount=budget, actual_burn=actual_burn,
        warn_threshold_pct=warn, block_threshold_pct=block,
    )
    session.add(proj)
    session.commit()
    return proj


# ---------------------------------------------------------------------------
# BUG: _update_status() ignores the per-project configurable thresholds
#      (warn_threshold_pct / block_threshold_pct) and hard-codes 80% / 100%.
# ---------------------------------------------------------------------------

class TestUpdateStatusIgnoresConfiguredThresholds:
    """BUG: Project exposes per-project configurable thresholds
    (``warn_threshold_pct`` default 80, ``block_threshold_pct`` default 100,
    documented as "Budget Guardrail Thresholds (per-project configuration)"
    in service_delivery/models.py). The guardrail service is THE application-
    level enforcement point (the model comment says "Application-level
    validation ensures: warn < pause < block"), but
    ``BudgetGuardrailService._update_status`` hard-codes ``ratio >= 1.0`` and
    ``ratio >= 0.8`` and never reads those columns.

    Effect (finance/enforcement bypass): a project configured to flag
    over-budget at, say, 70% reports ``on_track`` at 75% spend — silently
    disabling the configured guardrail and letting burn run past the
    operator-set block threshold with no OVER_BUDGET signal.

    Fix: read ``block_threshold_pct`` / ``warn_threshold_pct`` from the
    project (falling back to 100 / 80), and compute the thresholds from them.
    """

    def test_custom_block_threshold_marks_over_budget(self, db):
        """Project configured with block_threshold_pct=70 and 75% burn must be
        OVER_BUDGET (was: on_track, ignoring the configured 70% block)."""
        proj = _seed(db, budget=1000.0, actual_burn=750.0, warn=50, block=70)
        BudgetGuardrailService(db_session=db)._update_status(proj)
        from service_delivery.models import BudgetStatus
        assert proj.budget_status == BudgetStatus.OVER_BUDGET, (
            f"expected OVER_BUDGET at 75% burn with block=70%, got {proj.budget_status}"
        )

    def test_custom_warn_threshold_marks_at_risk(self, db):
        """Project configured with warn_threshold_pct=40 and 50% burn must be
        AT_RISK (hard-coded 80% would say on_track)."""
        proj = _seed(db, budget=1000.0, actual_burn=500.0, warn=40, block=90)
        BudgetGuardrailService(db_session=db)._update_status(proj)
        from service_delivery.models import BudgetStatus
        assert proj.budget_status == BudgetStatus.AT_RISK, (
            f"expected AT_RISK at 50% burn with warn=40%, got {proj.budget_status}"
        )

    def test_defaults_preserve_existing_behavior(self, db):
        """Sanity: when thresholds are at the historical defaults (80/100), the
        fix must not change behavior — 79% on_track, 80% at_risk, 100% over."""
        from service_delivery.models import BudgetStatus
        cases = [(790.0, BudgetStatus.ON_TRACK),
                 (800.0, BudgetStatus.AT_RISK),
                 (1000.0, BudgetStatus.OVER_BUDGET)]
        for i, (burn, expected) in enumerate(cases):
            proj = _seed(
                db, budget=1000.0, actual_burn=burn, warn=80, block=100,
                pid=f"proj-defaults-{i}", ws_id=f"ws-defaults-{i}",
            )
            BudgetGuardrailService(db_session=db)._update_status(proj)
            assert proj.budget_status == expected, (
                f"at {burn}/1000 with defaults, expected {expected}, got {proj.budget_status}"
            )

    def test_end_to_end_calculate_project_burn_uses_configured_block(self, db):
        """End-to-end through calculate_project_burn: expenses push burn to 75%
        of a project whose block_threshold_pct=70 -> status must be
        over_budget (was: at_risk under the hard-coded 100% rule)."""
        from accounting.models import Bill
        from service_delivery.models import Project

        from core.models import Workspace
        from service_delivery.models import Milestone, ProjectTask

        db.add(Workspace(id="ws-1", name="Acme"))
        db.add(Project(id="proj-1", workspace_id="ws-1", name="Site",
                       budget_amount=1000.0, warn_threshold_pct=50,
                       block_threshold_pct=70))
        db.add(Milestone(id="ms-1", workspace_id="ws-1", project_id="proj-1", name="P1"))
        db.add(ProjectTask(id="t1", workspace_id="ws-1", project_id="proj-1",
                           milestone_id="ms-1", name="T1", actual_hours=0.0))
        db.add(Bill(id="b1", workspace_id="ws-1", vendor_id="v1", amount=750.0,
                    issue_date=datetime.now(timezone.utc),
                    due_date=datetime.now(timezone.utc), project_id="proj-1"))
        db.commit()

        result = asyncio.run(
            BudgetGuardrailService(db_session=db).calculate_project_burn("proj-1"))
        assert result["total_burn"] == pytest.approx(750.0)
        assert result["status"] == "over_budget", (
            f"expected over_budget (block=70%, burn=75%), got {result['status']}"
        )
