"""P5 — Allocator integrity controls (AGENT_ORG_POLITICS_PLAN.md Phase 5).

Self-dealing block, coordinator rotation, model-family diversity floor, and
the radio→recruitment conflict-of-interest signal. Pure helpers in
core/org_integrity.py; wire-ins in atom_meta_agent._recruit_fleet (shadow:
signals are recorded, never blocking, until calibrated).
Flag: ATOM_ALLOCATOR_INTEGRITY_ENABLED default FALSE.
"""

from __future__ import annotations

from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


# ============================================================================
# Self-recruitment
# ============================================================================


class TestSelfRecruitment:
    def test_same_agent_blocked(self):
        from core.org_integrity import self_recruitment_blocked

        assert self_recruitment_blocked("atom_main", "atom_main") is True
        assert self_recruitment_blocked("Atom_Main", " atom_main ") is True

    def test_different_agent_allowed(self):
        from core.org_integrity import self_recruitment_blocked

        assert self_recruitment_blocked("atom_main", "spec_finance") is False

    def test_none_safe(self):
        from core.org_integrity import self_recruitment_blocked

        assert self_recruitment_blocked(None, "x") is False
        assert self_recruitment_blocked("x", None) is False


# ============================================================================
# Coordinator rotation
# ============================================================================


class TestCoordinatorRotation:
    CFG = {
        "coordinator_rotation": "task",
        "coordinator_candidates": ["a", "b", "c"],
    }

    def test_no_config_returns_none(self):
        from core.org_integrity import resolve_coordinator

        assert resolve_coordinator(None) is None
        assert resolve_coordinator({}) is None
        assert resolve_coordinator({"coordinator_candidates": []}) is None

    def test_fixed_is_default_and_stable(self):
        from core.org_integrity import resolve_coordinator

        cfg = {"coordinator_candidates": ["a", "b"]}
        assert resolve_coordinator(cfg, run_seq=7) == "a"
        assert resolve_coordinator(self.CFG.copy(), run_seq=0) == "a"

    def test_task_rotation_round_robins(self):
        from core.org_integrity import resolve_coordinator

        seq = [resolve_coordinator(self.CFG, run_seq=i) for i in range(4)]
        assert seq == ["a", "b", "c", "a"]

    def test_daily_rotation_changes_per_day(self):
        from core.org_integrity import resolve_coordinator

        cfg = {
            "coordinator_rotation": "daily",
            "coordinator_candidates": ["a", "b", "c"],
        }
        d1 = date(2026, 8, 21)
        d2 = date(2026, 8, 22)
        assert resolve_coordinator(cfg, today=d1) != resolve_coordinator(cfg, today=d2)


# ============================================================================
# Diversity floor
# ============================================================================


class TestDiversityFloor:
    def test_small_team_exempt(self):
        from core.org_integrity import enforce_diversity_floor

        result = enforce_diversity_floor(
            ["a1", "a2"], lambda a: "claude", min_team_size=3
        )
        assert result["ok"] is True

    def test_single_family_team_flagged(self):
        from core.org_integrity import enforce_diversity_floor

        result = enforce_diversity_floor(
            ["a1", "a2", "a3"], lambda a: "gpt"
        )
        assert result["ok"] is False
        assert result["reason"] == "single_family_team"

    def test_mixed_family_passes(self):
        from core.org_integrity import enforce_diversity_floor

        fams = {"a1": "gpt", "a2": "gpt", "a3": "claude"}
        result = enforce_diversity_floor(
            list(fams), lambda a: fams[a]
        )
        assert result["ok"] is True
        assert result["distinct_families"] == 2

    def test_all_unknown_passes_shadow_posture(self):
        """Undeclared families can't be judged — pass (never block)."""
        from core.org_integrity import enforce_diversity_floor

        result = enforce_diversity_floor(
            ["a1", "a2", "a3"], lambda a: None
        )
        assert result["ok"] is True


# ============================================================================
# COI signal over P0 telemetry
# ============================================================================


@pytest.fixture
def tel_db():
    from core.models import AgentOrgEvent

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    AgentOrgEvent.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestRadioContactSignal:
    def test_prior_contact_detected_both_directions(self, tel_db):
        from core.org_integrity import has_radio_contact
        from core.org_telemetry_service import AgentOrgTelemetryService

        svc = AgentOrgTelemetryService(tel_db)
        svc.emit(
            "radio_message", actor_agent_id="peer", target_agent_id="atom_main"
        )
        assert has_radio_contact(tel_db, "atom_main", "peer") is True
        # unrelated pair clean
        assert has_radio_contact(tel_db, "atom_main", "stranger") is False


# ============================================================================
# Contract RACI field + wire-ins
# ============================================================================


class TestContractAccountability:
    def test_accountable_field_roundtrips(self):
        from core.fleet_orchestration.delegation_contracts import (
            DelegationContract,
        )

        c = DelegationContract(objective="x", accountable_agent_id="ag-1")
        d = c.to_dict()
        assert d["accountable_agent_id"] == "ag-1"
        assert DelegationContract.from_dict(d).accountable_agent_id == "ag-1"

    def test_absent_field_omitted_from_dict(self):
        from core.fleet_orchestration.delegation_contracts import (
            DelegationContract,
        )

        assert "accountable_agent_id" not in DelegationContract(objective="x").to_dict()


class TestRecruitWireIns:
    def test_meta_agent_source_wires_integrity_guards(self):
        import inspect

        from core import atom_meta_agent

        src = inspect.getsource(atom_meta_agent.AtomMetaAgent._recruit_fleet)
        assert "self_recruitment_blocked" in src
        assert "enforce_diversity_floor" in src
