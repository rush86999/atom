"""Org-politics lifecycle automation (AGENT_ORG_POLITICS_PLAN.md — full automation).

Mirrors the consent-gated stage/fleet-router pattern:

- ``ATOM_ORG_AUTO_ENFORCE`` = off | notify | approve (default) | auto
- Escalation requires consent; **revocation never does** (fail-safe).
- Actions persist in ``org_politics_actions`` (approval queue + audit trail).
- Feature flags resolve: env kill-switch wins > latest applied/revoked action
  > default off — so automation can flip P2/P3/P5 without restarts while a
  plain env var still restores prior behavior instantly.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    from core.models import AgentOrgEvent, OrgPoliticsAction

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    AgentOrgEvent.__table__.create(engine)
    OrgPoliticsAction.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in (
        "ATOM_ORG_AUTO_ENFORCE",
        "ATOM_SKILL_SCOPED_TRUST_ENABLED",
        "ATOM_ALLOCATOR_INTEGRITY_ENABLED",
        "ATOM_ORG_PRIVILEGES_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)
    from core.org_politics_automation import (
        _last_notified,
        _last_run,
        invalidate_resolver_cache,
        set_automation_config,
    )

    import os as _os

    set_automation_config(
        mode=_os.getenv("ATOM_ORG_AUTO_ENFORCE", "auto")
    )
    _last_notified.clear()
    _last_run.clear()
    invalidate_resolver_cache()
    yield
    set_automation_config(
        mode=_os.getenv("ATOM_ORG_AUTO_ENFORCE", "auto")
    )
    invalidate_resolver_cache()


# ============================================================================
# Resolver precedence
# ============================================================================


class TestResolvedFlag:
    def test_default_off_without_env_or_actions(self, db):
        from core.org_politics_automation import resolve_flag_value

        assert resolve_flag_value(db, "skill_trust") is False

    def test_env_true_wins_over_revoked_action(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_SKILL_SCOPED_TRUST_ENABLED", "true")
        from core.models import OrgPoliticsAction
        from core.org_politics_automation import resolve_flag_value

        db.add(
            OrgPoliticsAction(
                flag_key="skill_trust", verdict="enable", mode="auto",
                state="revoked", stats_json={},
            )
        )
        db.commit()
        assert resolve_flag_value(db, "skill_trust") is True  # kill switch wins

    def test_env_false_wins_over_applied_action(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_PRIVILEGES_ENABLED", "false")
        from core.models import OrgPoliticsAction
        from core.org_politics_automation import resolve_flag_value

        db.add(
            OrgPoliticsAction(
                flag_key="org_privileges", verdict="enable", mode="auto",
                state="applied", stats_json={},
            )
        )
        db.commit()
        assert resolve_flag_value(db, "org_privileges") is False

    def test_applied_action_enables_when_env_unset(self, db):
        from core.models import OrgPoliticsAction
        from core.org_politics_automation import resolve_flag_value

        db.add(
            OrgPoliticsAction(
                flag_key="allocator_integrity", verdict="enable", mode="auto",
                state="applied", stats_json={},
            )
        )
        db.commit()
        assert resolve_flag_value(db, "allocator_integrity") is True

    def test_unknown_flag_defaults_off(self, db):
        from core.org_politics_automation import resolve_flag_value

        assert resolve_flag_value(db, "not_a_flag") is False


class TestFlagFunctionIntegration:
    def test_skill_trust_follows_action(self, db, monkeypatch):
        """The live matcher gate must consult the resolver, not just env."""
        monkeypatch.setattr(
            "core.database.get_db_session",
            _owned_session_factory(db),
        )
        from core.models import OrgPoliticsAction
        import core.skill_scoped_trust as sst

        assert sst.skill_scoped_trust_enabled() is False
        db.add(
            OrgPoliticsAction(
                flag_key="skill_trust", verdict="enable", mode="auto",
                state="applied", stats_json={},
            )
        )
        db.commit()
        __import__("core.org_politics_automation", fromlist=["x"]).invalidate_resolver_cache("skill_trust")
        assert sst.skill_scoped_trust_enabled() is True

    def test_env_still_kill_switches(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_SKILL_SCOPED_TRUST_ENABLED", "false")
        monkeypatch.setattr(
            "core.database.get_db_session",
            _owned_session_factory(db),
        )
        from core.models import OrgPoliticsAction
        import core.skill_scoped_trust as sst

        db.add(
            OrgPoliticsAction(
                flag_key="skill_trust", verdict="enable", mode="auto",
                state="applied", stats_json={},
            )
        )
        db.commit()
        __import__("core.org_politics_automation", fromlist=["x"]).invalidate_resolver_cache("skill_trust")
        assert sst.skill_scoped_trust_enabled() is False


def _owned_session_factory(db):
    import contextlib

    @contextlib.contextmanager
    def fake_session():
        yield db

    return fake_session


# ============================================================================
# Readiness inputs
# ============================================================================


class TestTelemetryReadiness:
    def test_counts_events_and_coi(self, db):
        from core.org_politics_automation import telemetry_readiness
        from core.org_telemetry_service import AgentOrgTelemetryService

        svc = AgentOrgTelemetryService(db)
        for _ in range(12):
            svc.emit("fleet_recruit", actor_agent_id="c", target_agent_id="s")
        svc.emit("radio_message", actor_agent_id="s", target_agent_id="c")

        readiness = telemetry_readiness(db)
        assert readiness["events"]["fleet_recruit"] >= 12
        assert readiness["coi_pairs"] == 1
        assert readiness["telemetry_flowing"] is True

    def test_empty_db_not_flowing(self, db):
        from core.org_politics_automation import telemetry_readiness

        readiness = telemetry_readiness(db)
        assert readiness["telemetry_flowing"] is False


class TestAlignmentVerdict:
    def test_green_sweep(self, monkeypatch):
        monkeypatch.setenv("ATOM_ALIGNMENT_SWEEP_ENABLED", "true")
        from core.org_politics_automation import alignment_verdict

        def fake_chat(system, user):
            return '{"utility": 8, "policy": 9, "violations": []}'

        verdict = alignment_verdict(chat_fn=fake_chat)
        assert verdict["ran"] is True
        assert verdict["green"] is True
        assert verdict["max_gap"] <= 0.01

    def test_red_sweep_reports_gap(self, monkeypatch):
        monkeypatch.setenv("ATOM_ALIGNMENT_SWEEP_ENABLED", "true")
        from core.org_politics_automation import alignment_verdict

        judges = {"n": 0}

        def fake_chat(system, user):
            if "BINDING POLICY" in user:
                judges["n"] += 1
                if judges["n"] % 3 == 1:  # first judge per scenario = single
                    return '{"utility": 8, "policy": 9, "violations": []}'
                return '{"utility": 9, "policy": 3, "violations": ["x"]}'
            return "proposal text"

        verdict = alignment_verdict(chat_fn=fake_chat)
        assert verdict["ran"] is True
        assert verdict["green"] is False
        assert verdict["max_gap"] > 2.0


# ============================================================================
# Certification pass
# ============================================================================


def _seed_eligible(db):
    from core.org_telemetry_service import AgentOrgTelemetryService

    svc = AgentOrgTelemetryService(db)
    for i in range(15):
        svc.emit("fleet_recruit", actor_agent_id="c", target_agent_id=f"s{i}")


class TestCertifyPass:
    def test_auto_mode_applies_when_eligible(self, db, monkeypatch):
        from core.org_politics_automation import set_automation_config

        set_automation_config(mode="auto")
        monkeypatch.setattr(
            "core.org_politics_automation.alignment_verdict",
            lambda **kw: {"ran": True, "green": True, "max_gap": 0.0,
                          "scores": {}, "skipped_reason": None},
        )
        _seed_eligible(db)
        from core.org_politics_automation import certify, resolve_flag_value

        result = certify(db)
        assert result["applied"], result
        assert resolve_flag_value(db, "skill_trust") is True

    def test_approve_mode_queues_without_applying(self, db, monkeypatch):
        from core.org_politics_automation import set_automation_config

        set_automation_config(mode="approve")
        monkeypatch.setattr(
            "core.org_politics_automation.alignment_verdict",
            lambda **kw: {"ran": True, "green": True, "max_gap": 0.0,
                          "scores": {}, "skipped_reason": None},
        )
        _seed_eligible(db)
        from core.org_politics_automation import certify, resolve_flag_value

        result = certify(db)
        assert result["queued"] and not result["applied"]
        assert resolve_flag_value(db, "allocator_integrity") is False

    def test_no_alignment_run_blocks_escalation(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_AUTO_ENFORCE", "auto")
        monkeypatch.setattr(
            "core.org_politics_automation.alignment_verdict",
            lambda **kw: {"ran": False, "green": False, "max_gap": None,
                          "scores": {}, "skipped_reason": "disabled"},
        )
        _seed_eligible(db)
        from core.org_politics_automation import certify, resolve_flag_value

        result = certify(db)
        assert not result["applied"]
        assert resolve_flag_value(db, "skill_trust") is False

    def test_low_telemetry_blocks_escalation(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_AUTO_ENFORCE", "auto")
        monkeypatch.setattr(
            "core.org_politics_automation.alignment_verdict",
            lambda **kw: {"ran": True, "green": True, "max_gap": 0.0,
                          "scores": {}, "skipped_reason": None},
        )
        from core.org_politics_automation import certify, resolve_flag_value

        certify(db)
        assert resolve_flag_value(db, "skill_trust") is False

    def test_red_sweep_auto_revokes_even_in_approve(self, db, monkeypatch):
        from core.org_politics_automation import set_automation_config

        set_automation_config(mode="approve")
        from core.models import OrgPoliticsAction
        from core.org_politics_automation import certify, resolve_flag_value

        db.add(
            OrgPoliticsAction(
                flag_key="skill_trust", verdict="enable", mode="auto",
                state="applied", stats_json={},
            )
        )
        db.commit()

        monkeypatch.setattr(
            "core.org_politics_automation.alignment_verdict",
            lambda **kw: {"ran": True, "green": False, "max_gap": 4.0,
                          "scores": {}, "skipped_reason": None},
        )
        result = certify(db)
        assert result["revoked"] == ["skill_trust"]
        assert resolve_flag_value(db, "skill_trust") is False

    def test_no_requeue_while_pending(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_ORG_AUTO_ENFORCE", "approve")
        monkeypatch.setattr(
            "core.org_politics_automation.alignment_verdict",
            lambda **kw: {"ran": True, "green": True, "max_gap": 0.0,
                          "scores": {}, "skipped_reason": None},
        )
        _seed_eligible(db)
        from core.models import OrgPoliticsAction
        from core.org_politics_automation import certify

        certify(db)
        first_count = db.query(OrgPoliticsAction).count()
        certify(db)
        assert db.query(OrgPoliticsAction).count() == first_count


# ============================================================================
# Approval queue
# ============================================================================


class TestApprovals:
    def _queue_one(self, db, monkeypatch):
        from core.org_politics_automation import set_automation_config

        set_automation_config(mode="approve")
        monkeypatch.setattr(
            "core.org_politics_automation.alignment_verdict",
            lambda **kw: {"ran": True, "green": True, "max_gap": 0.0,
                          "scores": {}, "skipped_reason": None},
        )
        _seed_eligible(db)
        from core.org_politics_automation import certify

        certify(db)

    def test_pending_and_apply(self, db, monkeypatch):
        self._queue_one(db, monkeypatch)
        from core.org_politics_automation import (
            apply_pending_decision,
            pending_approvals,
            resolve_flag_value,
        )

        pending = pending_approvals(db)
        assert len(pending) >= 1
        flag_key = pending[0]["flag_key"]

        assert apply_pending_decision(db, flag_key, approve=True)["state"] == "applied"
        assert resolve_flag_value(db, flag_key) is True

    def test_reject_marks_rejected(self, db, monkeypatch):
        self._queue_one(db, monkeypatch)
        from core.org_politics_automation import (
            apply_pending_decision,
            resolve_flag_value,
        )

        out = apply_pending_decision(db, "org_privileges", approve=False)
        assert out["state"] == "rejected"
        assert resolve_flag_value(db, "org_privileges") is False
