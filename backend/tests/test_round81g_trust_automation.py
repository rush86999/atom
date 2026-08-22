"""Round 81g — P3 consent-gated automation loop for the trust gateway.

Mirrors fleet_router_automation semantics:
- off mode: no rows, no side effects
- auto + certified: applied enable row -> resolved_trust_enforce True
- regression after applied: automatic revoke row -> enforce False
- notify/approve: queued approval row, admin consent applies it
"""

import pytest
from unittest.mock import Mock

from core.models import (
    AgentProposal,
    AgentRegistry,
    HITLAction,
    TrustCalibrationAction,
    TrustCalibrationAssessment,
    User,
)


@pytest.fixture
def tc_db():
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

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
        TrustCalibrationAction.__table__,
    ):
        t.create(engine)
    return sessionmaker(bind=engine)()


def _seed_history(db, n_pairs=18, deny_age_days=3):
    """Certifiable history: approvals at low corner, rejections at high."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    for i in range(n_pairs):
        good = True
        # INTERLEAVE decision times across classes so the temporal
        # train/eval split sees both (else train = all denials).
        good_hours = 1.5 * i + 1.0
        bad_hours = 1.5 * i + 3.0
        ref = f"h-good-{i}"
        db.add(HITLAction(
            id=ref, action_type="search_contacts", platform="internal",
            params={}, status="approved", agent_id="ag-1",
            reviewed_at=now - timedelta(hours=i + 1),
            created_at=now - timedelta(hours=i + 1),
        ))
        db.add(TrustCalibrationAssessment(
            id=f"a-good-{i}", action_type="search_contacts", platform="internal",
            p_approve=0.9, uncertainty=0.05, recommendation="allow",
            source_path="hitl_step_act", decision_ref=ref,
            features_json={"tool": [0.25, 0.0, 0.0], "ctx": [0.33]},
            created_at=now - timedelta(hours=i + 1),
        ))
        ref = f"h-bad-{i}"
        decided = now - timedelta(
            days=deny_age_days * 0, hours=bad_hours
        )  # deny_age_days kept for signature compat
        db.add(HITLAction(
            id=ref, action_type=f"bulk_delete_leads_{i}", platform="payment",
            params={}, status="rejected", agent_id="ag-1",
            reviewed_at=decided, created_at=decided,
        ))
        db.add(TrustCalibrationAssessment(
            id=f"a-bad-{i}", action_type=f"bulk_delete_leads_{i}",
            platform="payment", p_approve=0.1, uncertainty=0.05,
            recommendation="block", source_path="hitl_step_act",
            decision_ref=ref,
            features_json={"tool": [1.0, 1.0, 1.0], "ctx": [0.33]},
            created_at=decided,
        ))
    db.commit()


@pytest.fixture
def fresh_module(monkeypatch):
    """Automation module keeps module-level config; reset per test."""
    import core.trust_calibration.automation as auto

    monkeypatch.setattr(auto, "_mode", None)
    monkeypatch.setattr(auto, "_interval_min", None)
    monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
    return auto


class TestAutomationLoop:
    def test_off_mode_noop(self, tc_db, fresh_module):
        out = fresh_module.run_automation_pass(tc_db, force=True)
        assert out["ran"] is False
        assert tc_db.query(TrustCalibrationAction).count() == 0

    def test_auto_certified_applies(self, tc_db, fresh_module, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "auto")
        _seed_history(tc_db)

        out = fresh_module.run_automation_pass(tc_db, force=True)
        assert out["ran"] and out["verdict"] == "enable" and out["applied"]
        assert fresh_module.resolved_trust_enforce(tc_db) is True
        row = tc_db.query(TrustCalibrationAction).first()
        assert row.state == "applied" and row.verdict == "enable"

    def test_regression_after_applied_revokes(self, tc_db, fresh_module,
                                               monkeypatch):
        """A previously-applied gate whose certification regressed is
        revoked automatically (the plan's always-automatic revocation)."""
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "auto")
        _seed_history(tc_db)
        fresh_module.run_automation_pass(tc_db, force=True)
        assert fresh_module.resolved_trust_enforce(tc_db) is True

        # Deterministic regression: the certifier now fails its gate.
        from core.trust_calibration.certify import CertificationResult

        failing = CertificationResult(
            certified=False,
            reasons=["holdout Brier 0.61 > baseline 0.25"],
            n_train=28, n_eval=10,
            brier_holdout=0.61, denial_coverage=0.1, ece_10bin=0.3,
        )
        monkeypatch.setattr(
            "core.trust_calibration.certify.certify",
            lambda resolved: failing,
        )

        out = fresh_module.run_automation_pass(tc_db, force=True)
        assert out["verdict"] == "revoke" and out.get("revoked")
        assert fresh_module.resolved_trust_enforce(tc_db) is False
        states = [
            r.state for r in tc_db.query(TrustCalibrationAction)
            .order_by(TrustCalibrationAction.created_at).all()
        ]
        assert states == ["applied", "revoked"]

    def test_notify_mode_queues_and_notifies_once(self, tc_db, fresh_module, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "notify")
        _seed_history(tc_db)
        notified = []
        monkeypatch.setattr(fresh_module, "_notify",
                            lambda t, m: notified.append(t))

        out1 = fresh_module.run_automation_pass(tc_db, force=True)
        out2 = fresh_module.run_automation_pass(tc_db, force=True)

        assert out1["notified"] is True
        # cooldown suppresses the immediate second notification
        assert len(notified) == 1
        row = tc_db.query(TrustCalibrationAction).first()
        assert row.state == "approval"
        assert fresh_module.resolved_trust_enforce(tc_db) is False  # not applied


class TestConsentEndpointsLogic:
    def test_approve_and_reject_states(self, tc_db, fresh_module):
        aid = fresh_module._record_action(tc_db, "enable", "approval", {})
        assert fresh_module.approve_action(tc_db, aid) is True
        assert fresh_module.resolved_trust_enforce(tc_db) is True

        rid = fresh_module._record_action(tc_db, "enable", "approval", {})
        assert fresh_module.reject_action(tc_db, rid) is True
        # Latest ledger entry wins: a later REJECTED consent means the
        # operator declined relaxation — enforcement stays off.
        assert fresh_module.resolved_trust_enforce(tc_db) is False

    def test_approve_unknown_id(self, tc_db, fresh_module):
        assert fresh_module.approve_action(tc_db, "nope") is False


class TestTableSelfProvisioning:
    def test_assess_and_record_creates_missing_table(self, tmp_path, monkeypatch):
        """Un-migrated DB: the first record call provisions the table."""
        import sqlalchemy as sa
        from sqlalchemy.orm import sessionmaker
        from unittest.mock import MagicMock

        engine = sa.create_engine(
            f"sqlite:///{tmp_path}/bare.db",
            connect_args={"check_same_thread": False},
            poolclass=sa.pool.StaticPool,
        )
        bare = sessionmaker(bind=engine)()
        # Only source tables exist — assessments table deliberately absent.
        HITLAction.__table__.create(engine)
        AgentRegistry.__table__.create(engine)

        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
        from core.trust_calibration.gateway import TrustCalibrationGateway

        gw = TrustCalibrationGateway(db=bare)
        out = gw.assess_and_record(
            db=bare, action_type="send_email", platform="internal",
            agent_id=None, source_path="hitl_step_act", decision_ref="r1",
        )
        assert out is not None
        insp = sa.inspect(engine)
        assert "trust_calibration_assessments" in insp.get_table_names()
