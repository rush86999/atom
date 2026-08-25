"""P3 — Skill-scoped reputation (AGENT_ORG_POLITICS_PLAN.md Phase 3).

R8/R9/R12: recruitment trust must be per-skill, not global. Empirical-Bayes
borrowing across correlated skills helps sparse evidence but creates a
reputation-laundering channel — bounded here by a structural floor (zero
direct evidence caps the borrowed score). Updates are asymmetric
(fast-fail penalty), cold-start agents get a small deterministic exploration
boost, and the SpecialistMatcher consumes this instead of the global
``confidence_score`` when ATOM_SKILL_SCOPED_TRUST_ENABLED is on (default OFF;
shadow-first).

Data source: existing ``configuration.capability_stats`` written by
CapabilityGraduationService.record_usage (verified-gated tri-state).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


# ============================================================================
# Pure math
# ============================================================================


class TestTrustScoreMath:
    def test_no_evidence_anywhere_is_neutral(self):
        from core.skill_scoped_trust import trust_score

        assert trust_score({}, []) == pytest.approx(0.5)

    def test_laundering_guard_caps_borrowed_score(self):
        """Perfect correlated record cannot lift an unevidenced skill."""
        from core.skill_scoped_trust import TRUST_FLOOR_CAP, trust_score

        farmed = {"success": 50, "total": 50, "verified_success": 50}
        score = trust_score({}, [farmed])
        assert score <= TRUST_FLOOR_CAP
        assert score > 0.4  # borrowing still helps cold-start within the cap

    def test_direct_evidence_dominates_when_present(self):
        from core.skill_scoped_trust import TRUST_FLOOR_CAP, trust_score

        direct = {"success": 20, "total": 20, "verified_success": 18}
        farmed = {"success": 50, "total": 50, "verified_success": 50}
        score = trust_score(direct, [farmed])
        assert score > TRUST_FLOOR_CAP  # real evidence breaks the cap
        assert score < 1.0  # shrunk toward the pool, not naive ratio

    def test_shrinkage_pulls_toward_pool(self):
        from core.skill_scoped_trust import trust_score

        weak_direct = {"success": 5, "total": 10, "verified_success": 5}
        strong_pool = [{"success": 90, "total": 100, "verified_success": 90}]
        blended = trust_score(weak_direct, strong_pool)
        assert 0.5 < blended < 0.9
        assert abs(blended - 0.5) < abs(blended - 0.9)  # closer to direct

    def test_fast_fail_penalty_applies_and_is_capped(self):
        from core.skill_scoped_trust import FAIL_PENALTY_CAP, trust_score

        good = {"success": 10, "total": 10, "verified_success": 10}
        clean = trust_score(good, [])
        penalized = trust_score(
            {**good, "failures_verified": 4}, []
        )
        assert penalized < clean
        maxed = trust_score({**good, "failures_verified": 99}, [])
        assert clean - maxed <= FAIL_PENALTY_CAP + 1e-9

    def test_unverified_successes_do_not_inflate(self):
        """Self-reported success without verification must not raise trust."""
        from core.skill_scoped_trust import trust_score

        inflated_claim = {"success": 10, "total": 10, "verified_success": 0}
        assert trust_score(inflated_claim, []) <= 0.5 + 1e-9


class TestCollectStats:
    def test_exact_then_alias_matching(self):
        from core.skill_scoped_trust import collect_stats

        config = {
            "capability_stats": {
                "finance": {"success": 4, "total": 4, "verified_success": 4},
                "invoice_parser": {
                    "success": 8,
                    "total": 10,
                    "verified_success": 6,
                },
                "seo_audit": {"success": 3, "total": 3, "verified_success": 3},
            }
        }
        direct, correlated = collect_stats(config, "finance")
        assert direct is not None
        names = {c[0] for c in correlated}
        assert names == {"invoice_parser"}  # seo_audit is not a finance alias

    def test_missing_config_yields_neutral(self):
        from core.skill_scoped_trust import collect_stats

        direct, correlated = collect_stats({}, "sales")
        assert direct == {}
        assert correlated == []


# ============================================================================
# Graduation service asymmetry
# ============================================================================


class TestRecordUsageAsymmetry:
    @pytest.fixture
    def grad_db(self):
        from core.models import AgentRegistry

        engine = sa.create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=sa.pool.StaticPool,
        )
        AgentRegistry.__table__.create(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(
            AgentRegistry(
                id="ag-grad",
                name="G",
                category="Ops",
                role="agent",
                type="personal",
                module_path="m",
                class_name="C",
            )
        )
        session.commit()
        yield session
        session.close()

    def test_failed_verification_records_penalty_counter(self, grad_db):
        from core.capability_graduation_service import CapabilityGraduationService
        from core.models import AgentRegistry

        svc = CapabilityGraduationService(grad_db)
        svc.record_usage(
            "ag-grad", "inv_tool", success=True, verified="failed_verification"
        )
        row = grad_db.query(AgentRegistry).filter_by(id="ag-grad").first()
        stats = row.configuration["capability_stats"]["inv_tool"]
        assert stats["failures_verified"] == 1
        assert stats.get("last_outcome_at")

    def test_success_stamps_timestamp_without_penalty(self, grad_db):
        from core.capability_graduation_service import CapabilityGraduationService
        from core.models import AgentRegistry

        svc = CapabilityGraduationService(grad_db)
        svc.record_usage("ag-grad", "inv_tool", success=True, verified="verified")
        row = grad_db.query(AgentRegistry).filter_by(id="ag-grad").first()
        stats = row.configuration["capability_stats"]["inv_tool"]
        assert stats.get("failures_verified", 0) == 0
        assert stats.get("last_outcome_at")


# ============================================================================
# Matcher integration
# ============================================================================


@pytest.fixture
def matcher_db():
    from core.models import AgentRegistry

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    AgentRegistry.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_agent(db, id, name, confidence, stats_config=None):
    from core.models import AgentRegistry

    db.add(
        AgentRegistry(
            id=id,
            name=name,
            category="finance",
            role="agent",
            type="personal",
            module_path="m",
            class_name="C",
            status="supervised",
            capabilities=["invoice", "reconciliation"],
            confidence_score=confidence,
            configuration=stats_config or {},
        )
    )
    db.commit()


class TestMatcherIntegration:
    def _results(self, db, monkeypatch, enabled):
        monkeypatch.setenv("ATOM_SKILL_SCOPED_TRUST_ENABLED", str(enabled))
        from core.specialist_matcher import SpecialistMatcher

        return SpecialistMatcher(db).find_specialists_for_domains(["finance"])

    def test_flag_off_preserves_global_confidence_ordering(
        self, matcher_db, monkeypatch
    ):
        _seed_agent(matcher_db, "high-conf", "HighConf", confidence=0.9)
        _seed_agent(matcher_db, "skilled", "Skilled", confidence=0.3)
        ranked = [
            r["agent_id"]
            for r in self._results(matcher_db, monkeypatch, False)["finance"]
        ]
        assert ranked.index("high-conf") < ranked.index("skilled")

    def test_flag_on_lets_domain_evidence_win(self, matcher_db, monkeypatch):
        _seed_agent(matcher_db, "high-conf", "HighConf", confidence=0.9)
        _seed_agent(
            matcher_db,
            "skilled",
            "Skilled",
            confidence=0.3,
            stats_config={
                "capability_stats": {
                    "finance": {
                        "success": 30,
                        "total": 30,
                        "verified_success": 30,
                        "failures_verified": 0,
                    },
                    "invoice_parser": {
                        "success": 40,
                        "total": 40,
                        "verified_success": 40,
                        "failures_verified": 0,
                    },
                }
            },
        )
        results = self._results(matcher_db, monkeypatch, True)["finance"]
        ranked = [r["agent_id"] for r in results]
        assert ranked.index("skilled") < ranked.index("high-conf")
        skilled = next(r for r in results if r["agent_id"] == "skilled")
        assert "trust" in skilled

    def test_flag_default_off(self, monkeypatch):
        monkeypatch.delenv("ATOM_SKILL_SCOPED_TRUST_ENABLED", raising=False)
        from core.skill_scoped_trust import skill_scoped_trust_enabled

        assert skill_scoped_trust_enabled() is False
