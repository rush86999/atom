"""Round 81e — Trust Calibration P1: live shadow recording + outcome join.

- assess_and_record persists one assessment per ask-the-human moment with
  decision_ref -> HITLAction.id; flag-gated; never raises.
- /stats calibration block joins outcomes and computes Brier/ECE + matrix.
- Both ask-paths (generic_agent._step_act, mcp_service._check_hitl_policy)
  are wired (source-pinned), matching the plan's P1 scope.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from core.models import (
    AgentProposal,
    AgentRegistry,
    HITLAction,
    TrustCalibrationAssessment,
    User,
)


@pytest.fixture
def tc_db():
    import sqlalchemy as sa

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    for t in (
        AgentRegistry.__table__,
        HITLAction.__table__,
        AgentProposal.__table__,
        TrustCalibrationAssessment.__table__,
    ):
        t.create(engine)
    return sessionmaker(bind=engine)()


@pytest.fixture
def p1_client(tc_db, monkeypatch):
    from core.auth import get_current_user
    from core.database import get_db as _get_db
    from api.trust_calibration_routes import router
    from core.models import UserRole

    monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="admin-1", role=UserRole.SUPER_ADMIN.value, status="active"
    )
    app.dependency_overrides[_get_db] = lambda: tc_db
    return TestClient(app)


def _hitl(db, ref, status):
    db.add(HITLAction(
        id=ref,
        action_type="send_email",
        platform="internal",
        params={},
        status=status,
        agent_id="ag-1",
        reviewed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()


class TestAssessAndRecord:
    def test_persists_row_with_ref(self, tc_db, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
        from core.trust_calibration.gateway import TrustCalibrationGateway

        gw = TrustCalibrationGateway(db=tc_db)
        out = gw.assess_and_record(
            db=tc_db,
            action_type="send_email",
            platform="internal",
            agent_id=None,
            source_path="hitl_step_act",
            decision_ref="ref-123",
        )
        assert out is not None
        row = (
            tc_db.query(TrustCalibrationAssessment)
            .filter_by(decision_ref="ref-123")
            .first()
        )
        assert row is not None
        assert row.source_path == "hitl_step_act"
        assert row.recommendation in ("allow", "ask", "block")

    def test_flag_off_records_nothing(self, tc_db, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "false")
        from core.trust_calibration.gateway import TrustCalibrationGateway

        gw = TrustCalibrationGateway(db=tc_db)
        out = gw.assess_and_record(db=tc_db, action_type="send_email")
        assert out is None
        assert tc_db.query(TrustCalibrationAssessment).count() == 0

    def test_never_raises_on_bad_session(self, tc_db, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
        from unittest.mock import MagicMock

        bad = MagicMock()
        bad.query.side_effect = RuntimeError("db gone")
        bad.add.side_effect = RuntimeError("db gone")
        from core.trust_calibration.gateway import TrustCalibrationGateway

        gw = TrustCalibrationGateway(db=bad)
        out = gw.assess_and_record(db=bad, action_type="send_email")
        assert out is None  # swallowed


class TestStatsOutcomeJoin:
    def _seed(self, db):
        now = datetime.now(timezone.utc)
        # p=0.9 on an APPROVED action -> error 0.01
        _hitl(db, "ref-good", "approved")
        db.add(TrustCalibrationAssessment(
            id="a1", action_type="send_email", platform="internal",
            p_approve=0.9, uncertainty=0.05, recommendation="allow",
            source_path="hitl_step_act", decision_ref="ref-good",
            created_at=now,
        ))
        # p=0.2 on a REJECTED action -> error 0.04
        _hitl(db, "ref-bad", "rejected")
        db.add(TrustCalibrationAssessment(
            id="a2", action_type="send_email", platform="internal",
            p_approve=0.2, uncertainty=0.06, recommendation="block",
            source_path="governance_hitl_policy", decision_ref="ref-bad",
            created_at=now,
        ))
        # pending -> excluded from resolved metrics
        _hitl(db, "ref-open", "pending")
        db.add(TrustCalibrationAssessment(
            id="a3", action_type="send_email", platform="internal",
            p_approve=0.5, uncertainty=0.20, recommendation="ask",
            source_path="hitl_step_act", decision_ref="ref-open",
            created_at=now,
        ))
        db.commit()

    def test_brier_matrix_and_pending(self, p1_client, tc_db):
        self._seed(tc_db)
        r = p1_client.get("/api/v1/trust-calibration/stats")
        assert r.status_code == 200
        cal = r.json()["calibration"]
        assert cal["assessments_total"] == 3
        assert cal["resolved"] == 2
        assert cal["pending"] == 1
        expected_brier = round(((0.9 - 1) ** 2 + (0.2 - 0) ** 2) / 2, 6)
        assert abs(cal["brier"] - expected_brier) < 1e-6
        m = cal["recommendation_outcome_matrix"]
        assert m["allow"]["approved"] == 1
        assert m["block"]["rejected"] == 1
        assert cal["ece_10bin"] is not None


class TestP1HookWiring:
    def test_generic_agent_hook_present(self):
        import inspect

        src = inspect.getsource(__import__("core.generic_agent").generic_agent)
        assert 'source_path="hitl_step_act"' in src
        assert "assess_and_record" in src

    def test_mcp_policy_hook_present(self):
        import inspect

        import importlib

        mod = importlib.import_module("integrations.mcp_service")
        src = inspect.getsource(mod)
        assert 'source_path="governance_hitl_policy"' in src
        assert "decision_ref" in src

    def test_migration_guarded(self):
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic",
            "versions",
            "20260822_add_trust_calibration_assessments.py",
        )
        src = open(path).read()
        assert "_table_exists" in src
        assert "20260821_fleet_routing_audit" in src
