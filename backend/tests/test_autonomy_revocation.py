"""ASK-03: a verified regression revokes earned autonomy at the runtime gate."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from core import autonomy_policy
from core.autonomy_policy import MODE_AUTO_IF_MATURE, gate_for_topic
from core.capability_graduation_service import CapabilityGraduationService
from core.database import Base
from core.models import AgentRegistry


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atom.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    agent = AgentRegistry(
        id="agent-revocation-1", name="Revocation", category="test",
        module_path="test.module", class_name="TestAgent",
        tenant_id="t1", workspace_id="w1", status="autonomous",
        configuration={
            "capability_maturities": {"canvas_edit": "autonomous"},
            "capability_stats": {
                "canvas_edit": {"success": 25, "total": 25,
                                "verified_success": 25},
            },
        },
    )
    db.add(agent)
    db.commit()
    yield Session, db
    db.close()
    engine.dispose()


def _allow(monkeypatch):
    monkeypatch.setattr(
        autonomy_policy, "get_effective_mode",
        lambda *a, **k: MODE_AUTO_IF_MATURE)
    monkeypatch.setattr(
        autonomy_policy, "maturity_check",
        lambda *a, **k: {"ok": True, "maturity_level": "autonomous",
                         "required": "supervised", "reason": None})
    monkeypatch.setattr(
        autonomy_policy, "trust_check",
        lambda *a, **k: {"ok": True, "trust": 0.9, "threshold": 0.6})
    monkeypatch.setattr(
        autonomy_policy, "autonomy_cycle", lambda *a, **k: None)


def test_verified_regression_blocks_the_runtime_gate(store, monkeypatch):
    _Session, db = store
    _allow(monkeypatch)
    before = gate_for_topic(db, "user-1", "canvas_edit", "agent-revocation-1")
    assert before["outcome"] == "execute"
    assert before["revocation"]["ok"] is True

    CapabilityGraduationService(db).record_usage(
        "agent-revocation-1", "canvas_edit",
        success=False, verified="failed_verification")

    after = gate_for_topic(db, "user-1", "canvas_edit", "agent-revocation-1")
    assert after["outcome"] == "propose"
    assert after["revocation"]["revoked"] is True
    assert "revoked after a verified regression" in after["reason"]


def test_revocation_survives_a_new_session(store, monkeypatch):
    Session, db = store
    _allow(monkeypatch)
    CapabilityGraduationService(db).record_usage(
        "agent-revocation-1", "canvas_edit",
        success=False, verified="failed_verification")
    db.commit()
    db.close()

    fresh = Session()
    try:
        _allow(monkeypatch)
        gate = gate_for_topic(
            fresh, "user-1", "canvas_edit", "agent-revocation-1")
        assert gate["outcome"] == "propose"
        assert gate["revocation"]["detail"]["reason"] == "verified_regression"
    finally:
        fresh.close()


def test_first_failure_without_prior_success_is_not_a_regression(store, monkeypatch):
    _Session, db = store
    _allow(monkeypatch)
    CapabilityGraduationService(db).record_usage(
        "agent-revocation-1", "task_create",
        success=False, verified="failed_verification")
    gate = gate_for_topic(db, "user-1", "task_create", "agent-revocation-1")
    assert gate["revocation"]["revoked"] is False
    assert gate["outcome"] == "execute"


def test_verified_work_can_reearn_the_capability(store, monkeypatch):
    _Session, db = store
    _allow(monkeypatch)
    service = CapabilityGraduationService(db)
    service.record_usage(
        "agent-revocation-1", "canvas_edit",
        success=False, verified="failed_verification")
    assert gate_for_topic(
        db, "user-1", "canvas_edit", "agent-revocation-1"
    )["revocation"]["revoked"] is True

    for _ in range(20):
        service.record_usage(
            "agent-revocation-1", "canvas_edit",
            success=True, verified="verified")
    assert gate_for_topic(
        db, "user-1", "canvas_edit", "agent-revocation-1"
    )["revocation"]["revoked"] is False


def test_reentry_requires_new_successes_after_the_revocation(store, monkeypatch):
    """25 historical successes must not clear a fresh revocation."""
    _Session, db = store
    _allow(monkeypatch)
    service = CapabilityGraduationService(db)
    service.record_usage(
        "agent-revocation-1", "canvas_edit",
        success=False, verified="failed_verification")
    assert gate_for_topic(
        db, "user-1", "canvas_edit", "agent-revocation-1"
    )["revocation"]["revoked"] is True

    for expected, count in ((1, 1), (19, 18)):
        for _ in range(count):
            service.record_usage(
                "agent-revocation-1", "canvas_edit",
                success=True, verified="verified")
        gate = gate_for_topic(
            db, "user-1", "canvas_edit", "agent-revocation-1")
        assert gate["revocation"]["revoked"] is True, expected
        assert gate["revocation"]["detail"]["reentry_successes"] == expected

    service.record_usage(
        "agent-revocation-1", "canvas_edit",
        success=True, verified="verified")
    gate = gate_for_topic(db, "user-1", "canvas_edit", "agent-revocation-1")
    assert gate["revocation"]["revoked"] is False
    assert gate["outcome"] == "execute"


def test_second_regression_resets_the_reentry_baseline(store, monkeypatch):
    _Session, db = store
    _allow(monkeypatch)
    service = CapabilityGraduationService(db)
    service.record_usage(
        "agent-revocation-1", "canvas_edit",
        success=False, verified="failed_verification")
    first = gate_for_topic(
        db, "user-1", "canvas_edit", "agent-revocation-1")["revocation"]["detail"]
    assert first["epoch"] == 1

    for _ in range(5):
        service.record_usage(
            "agent-revocation-1", "canvas_edit",
            success=True, verified="verified")
    service.record_usage(
        "agent-revocation-1", "canvas_edit",
        success=False, verified="failed_verification")
    second = gate_for_topic(
        db, "user-1", "canvas_edit", "agent-revocation-1")["revocation"]["detail"]
    assert second["epoch"] == 2
    # The 5 new successes are historical now: the next success is not 20.
    service.record_usage(
        "agent-revocation-1", "canvas_edit",
        success=True, verified="verified")
    gate = gate_for_topic(db, "user-1", "canvas_edit", "agent-revocation-1")
    assert gate["revocation"]["revoked"] is True
    assert gate["revocation"]["detail"]["reentry_successes"] == 1


def test_revocation_lookup_fails_closed(monkeypatch):
    """An unreadable authority store must refuse, not grant."""
    from core.autonomy_policy import revocation_check

    class _BrokenDB:
        def query(self, *args, **kwargs):
            raise RuntimeError("authority store down")

    state = revocation_check(_BrokenDB(), "agent-revocation-1", "canvas_edit")
    assert state["ok"] is False
    assert state["unavailable"] is True

    _allow(monkeypatch)
    gate = gate_for_topic(
        _BrokenDB(), "user-1", "canvas_edit", "agent-revocation-1")
    assert gate["outcome"] == "propose"
    assert "could not be checked" in gate["reason"]
