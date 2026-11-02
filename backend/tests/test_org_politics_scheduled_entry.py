"""The scheduled org-politics pass, not just its inner certify() helper.

The claim's gap was that the opt-in nightly path was never exercised. These
controls call ``run_auto_certification`` (the startup-scheduled entry point,
which opens its own session) and then read the durable queue from a NEW
session, so an in-memory result cannot stand in for persistence.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from core.models import AgentOrgEvent, OrgPoliticsAction


def _world():
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    AgentOrgEvent.__table__.create(engine)
    OrgPoliticsAction.__table__.create(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _seed(db):
    from core.org_telemetry_service import AgentOrgTelemetryService

    svc = AgentOrgTelemetryService(db)
    for i in range(15):
        svc.emit("fleet_recruit", actor_agent_id="c", target_agent_id=f"s{i}")
    db.commit()


def _green(monkeypatch):
    monkeypatch.setattr(
        "core.org_politics_automation.alignment_verdict",
        lambda **kw: {"ran": True, "green": True, "max_gap": 0.0,
                      "scores": {}, "skipped_reason": None},
    )
    monkeypatch.setattr(
        "core.org_politics_automation._spawn_notification",
        lambda *args, **kwargs: None,
    )


def test_scheduled_notify_pass_files_no_policy_change(monkeypatch):
    engine, factory = _world()
    try:
        db = factory()
        _seed(db)
        monkeypatch.setattr("core.database.get_db_session", factory)
        monkeypatch.setenv("ATOM_ORG_AUTO_ENFORCE", "notify")
        _green(monkeypatch)
        from core.org_politics_automation import (
            run_auto_certification,
            resolve_flag_value,
            set_automation_config,
        )

        set_automation_config(mode="notify")
        result = run_auto_certification()
        assert result["notified"], result
        assert not result["applied"] and not result["queued"], result

        fresh = factory()
        try:
            assert fresh.query(OrgPoliticsAction).count() == 0
            assert resolve_flag_value(fresh, "skill_trust") is False
            assert resolve_flag_value(fresh, "org_privileges") is False
        finally:
            fresh.close()
            db.close()
    finally:
        engine.dispose()


def test_scheduled_approve_pass_persists_pending_across_a_new_session(
        monkeypatch):
    engine, factory = _world()
    try:
        db = factory()
        _seed(db)
        monkeypatch.setattr("core.database.get_db_session", factory)
        monkeypatch.setenv("ATOM_ORG_AUTO_ENFORCE", "approve")
        _green(monkeypatch)
        from core.org_politics_automation import (
            run_auto_certification,
            resolve_flag_value,
            set_automation_config,
        )

        set_automation_config(mode="approve")
        result = run_auto_certification()
        assert result["queued"], result
        assert not result["applied"], result

        fresh = factory()
        try:
            rows = fresh.query(OrgPoliticsAction).all()
            assert rows, "the approval queue must survive the pass session"
            assert {row.state for row in rows} == {"approval"}
            assert {row.mode for row in rows} == {"approve"}
            assert set(row.flag_key for row in rows) == {
                "skill_trust", "allocator_integrity", "org_privileges"}
            # Consent was requested, not assumed.
            for key in ("skill_trust", "allocator_integrity",
                        "org_privileges"):
                assert resolve_flag_value(fresh, key) is False
        finally:
            fresh.close()

        # A second scheduled pass must not requeue the same pending actions.
        second = run_auto_certification()
        assert not second["queued"], second
        fresh = factory()
        try:
            assert fresh.query(OrgPoliticsAction).count() == len(rows)
        finally:
            fresh.close()
            db.close()
    finally:
        engine.dispose()
