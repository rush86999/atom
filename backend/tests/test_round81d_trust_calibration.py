"""Round 81d — Trust Calibration Gateway P0 spike (R81l).

Implements docs/architecture/TRUST_CALIBRATION_PLAN.md §3/P0:
- core/trust_calibration/gp.py: probit-link GP, product kernel
  k_tool x k_ctx x k_time (pointwise half-life decay down-weights stale
  evidence; label noise folded as base/w_i so stale points are noisier AND
  lower-scale).
- features.py v1 vectors; gateway.py three-tier allow/ask/block;
  service.py adapters over hitl_actions + agent_proposals.
- api/trust_calibration_routes.py: admin-gated /assess + /stats,
  ATOM_TRUST_CALIBRATION_ENABLED default false -> 503.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import Mock

import numpy as np


# ============================================================================
# Fixtures: isolated sqlite with just the observation-source tables
# ============================================================================


@pytest.fixture
def tmp_sqlite():
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from core.models import (
        HITLAction, AgentProposal, AgentRegistry,
        TrustCalibrationAssessment,
    )

    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,  # one shared in-memory DB across threads
    )
    HITLAction.__table__.create(engine)
    AgentProposal.__table__.create(engine)
    AgentRegistry.__table__.create(engine)
    TrustCalibrationAssessment.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    yield Session()


@pytest.fixture
def tmp_sqlite_seeded(tmp_sqlite):
    """12 HITL decisions + 6 proposal decisions across both bands."""
    from core.models import HITLAction, AgentProposal

    db = tmp_sqlite
    now = datetime.now(timezone.utc)

    for i in range(8):
        db.add(HITLAction(
            id=f"hitl-ok-{i}",
            action_type="search_contacts",
            platform="internal",
            params={},
            status="approved",
            agent_id="ag-intern",
            reviewed_at=now - timedelta(hours=i),
            created_at=now - timedelta(hours=i),
        ))
    for i in range(4):
        db.add(HITLAction(
            id=f"hitl-bad-{i}",
            action_type="bulk_delete_leads",
            platform="payment",
            params={},
            status="rejected",
            agent_id="ag-intern",
            reviewed_at=now - timedelta(days=3 + i),
            created_at=now - timedelta(days=3 + i),
        ))
    for i in range(4):
        db.add(AgentProposal(
            id=f"prop-ok-{i}",
            tenant_id="default",
            user_id="u1",
            agent_id="ag-intern",
            title="look up contacts",
            proposal_type="action",
            proposal_data={"action_type": "search_contacts"},
            status="approved",
            approved_at=now - timedelta(hours=i),
            created_at=now - timedelta(hours=i),
        ))
    for i in range(2):
        db.add(AgentProposal(
            id=f"prop-bad-{i}",
            tenant_id="default",
            user_id="u1",
            agent_id="ag-intern",
            title="mass delete",
            proposal_type="action",
            proposal_data={"action_type": "bulk_delete_leads"},
            status="rejected",
            approved_at=now - timedelta(days=130 + i),
            created_at=now - timedelta(days=130 + i),
        ))
    db.commit()
    yield db


# ============================================================================
# GP unit behavior (no DB)
# ============================================================================


class TestProductKernelGP:
    def _fit(self, denial_age=0.0, n_each=25):
        """Approvals and DENIALS both at the SAME point — contradictory
        evidence colocated so the time-decay path is isolated cleanly."""
        from core.trust_calibration.gp import ProductKernelGP

        tool = np.tile(np.array([0.5, 0.5, 0.5]), (n_each * 2, 1))
        ctx = np.full((n_each * 2, 1), 0.5)
        y = np.concatenate([np.ones(n_each), -np.ones(n_each)])
        age = np.concatenate([np.zeros(n_each), np.full(n_each, denial_age)])

        gp = ProductKernelGP(half_life_days=30.0)
        gp.fit(tool, ctx, y, age)
        return gp

    def _separated(self):
        """Two-cluster geometry for monotonicity/uncertainty checks."""
        from core.trust_calibration.gp import ProductKernelGP

        rng = np.random.default_rng(7)
        tool_ok = np.tile(np.array([0.25, 0.0, 0.0]), (25, 1))
        ctx_ok = np.clip(rng.normal(0.5, 0.02, size=(25, 1)), 0, 1)
        tool_bad = np.tile(np.array([1.0, 1.0, 1.0]), (25, 1))
        ctx_bad = np.clip(rng.normal(0.5, 0.02, size=(25, 1)), 0, 1)

        gp = ProductKernelGP(half_life_days=30.0)
        gp.fit(
            np.vstack([tool_ok, tool_bad]),
            np.vstack([ctx_ok, ctx_bad]),
            np.concatenate([np.ones(25), -np.ones(25)]),
            np.zeros(50),
        )
        return gp

    def test_monotonic_separation(self):
        gp = self._separated()
        p_low = gp.predict(
            tool_vec=np.array([0.25, 0.0, 0.0]), ctx_vec=np.array([0.5]), age_days=0.0
        )["p_approve"]
        p_high = gp.predict(
            tool_vec=np.array([1.0, 1.0, 1.0]), ctx_vec=np.array([0.5]), age_days=0.0
        )["p_approve"]
        assert p_low > 0.75
        assert p_high < 0.35

    def test_uncertainty_grows_away_from_data(self):
        gp = self._separated()
        near = gp.predict(
            tool_vec=np.array([0.25, 0.05, 0.0]), ctx_vec=np.array([0.5]), age_days=0.0
        )["uncertainty"]
        far = gp.predict(
            tool_vec=np.array([1.0, 1.0, 1.0]), ctx_vec=np.array([0.9]), age_days=0.0
        )["uncertainty"]
        assert far > near

    def test_time_decay_downweights_stale_denials(self):
        point = {
            "tool_vec": np.array([0.5, 0.5, 0.5]),
            "ctx_vec": np.array([0.5]),
            "age_days": 0.0,
        }
        fresh_denials = self._fit(denial_age=0.0).predict(**point)["p_approve"]
        stale_denials = self._fit(denial_age=120.0).predict(**point)["p_approve"]
        # Identical counts at identical points: only k_time differs.
        # Balanced colocated labels are an exact tie -> p == 0.5; stale
        # denials (w=1/16, noise x16) must break the tie toward approvals.
        assert abs(fresh_denials - 0.5) < 1e-6
        assert stale_denials > 0.6

    def test_cold_start_is_ask_band(self):
        from core.trust_calibration.gp import ProductKernelGP

        gp = ProductKernelGP()
        out = gp.predict(
            tool_vec=np.array([0.5, 0.5, 0.5]), ctx_vec=np.array([0.5]), age_days=0.0
        )
        assert abs(out["p_approve"] - 0.5) < 0.05
        assert out["uncertainty"] > 0.15


# ============================================================================
# Feature extraction
# ============================================================================


class TestFeatures:
    def test_tool_vector_bounded_and_ordered(self):
        from core.trust_calibration.features import tool_vector

        safe = tool_vector("search_contacts")
        destr = tool_vector("bulk_delete_leads")
        assert len(safe) == 3
        assert all(0.0 <= x <= 1.0 for x in safe)
        assert safe[1] == 0.0 and destr[1] == 1.0  # destructive flag flips on
        assert destr[0] > safe[0]  # complexity ordering

    def test_context_vector_tier_ordering(self):
        from core.trust_calibration.features import context_vector

        s = context_vector(agent_status="student", platform="internal")
        a = context_vector(agent_status="autonomous", platform="internal")
        assert s[0] < a[0]


# ============================================================================
# Gateway three-tier recommendations
# ============================================================================


@pytest.fixture
def gw_seeded(tmp_sqlite_seeded, monkeypatch):
    monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
    from core.trust_calibration.gateway import TrustCalibrationGateway

    return TrustCalibrationGateway(db=tmp_sqlite_seeded)


class TestGatewayRecommendations:
    def test_allow_band(self, gw_seeded):
        out = gw_seeded.assess(action_type="search_contacts", platform="internal")
        assert out["recommendation"] == "allow"
        assert out["p_approve"] > 0.7

    def test_block_band(self, gw_seeded):
        out = gw_seeded.assess(action_type="bulk_delete_leads", platform="payment")
        assert out["recommendation"] == "block"
        assert out["p_approve"] < 0.4

    def test_cold_start_asks(self, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
        from core.trust_calibration.gateway import TrustCalibrationGateway

        gw = TrustCalibrationGateway(db=None)
        out = gw.assess(action_type="anything", platform="internal")
        assert out["recommendation"] == "ask"
        assert out["n_obs"] == 0


# ============================================================================
# Service adapters over real tables (sqlite)
# ============================================================================


class TestDecisionAdapters:
    def test_loads_both_sources(self, tmp_sqlite_seeded):
        db = tmp_sqlite_seeded
        from core.trust_calibration.service import load_decisions

        obs = load_decisions(db, limit=50)
        sources = {o.source for o in obs}
        assert "hitl" in sources and "proposal" in sources
        assert all(o.y in (1, -1) for o in obs)
        assert all(o.age_days >= 0 for o in obs)


# ============================================================================
# Routes: admin-gated, flag-off 503
# ============================================================================


@pytest.fixture
def tc_client(tmp_sqlite_seeded, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core.auth import get_current_user
    from core.database import get_db as _get_db
    from api.trust_calibration_routes import router
    from core.models import UserRole

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="admin-1", role=UserRole.SUPER_ADMIN.value, status="active"
    )
    app.dependency_overrides[_get_db] = lambda: tmp_sqlite_seeded
    client = TestClient(app)
    client.app_ref = app
    return client


class TestTrustCalibrationRoutes:
    def test_flag_off_returns_503(self, tc_client, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "false")
        r = tc_client.get("/api/v1/trust-calibration/stats")
        assert r.status_code == 503

    def test_stats_enabled(self, tc_client, monkeypatch, tmp_sqlite_seeded):
        from core.models import HITLAction as _H
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
        pre = tmp_sqlite_seeded.query(_H).count()
        r = tc_client.get("/api/v1/trust-calibration/stats")
        post = tmp_sqlite_seeded.query(_H).count()
        print("DBG pre/post HITL:", pre, post)
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is True
        assert body["observations"]["total"] >= 10
        assert set(body["observations"]["by_source"]) >= {"hitl", "proposal"}

    def test_assess_shape(self, tc_client, monkeypatch):
        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
        r = tc_client.get(
            "/api/v1/trust-calibration/assess",
            params={"action_type": "send_email", "platform": "gmail"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["recommendation"] in ("allow", "ask", "block")
        assert 0.0 <= body["p_approve"] <= 1.0
        assert body["uncertainty"] >= 0.0

    def test_non_admin_forbidden(self, tc_client, monkeypatch):
        from core.auth import get_current_user

        monkeypatch.setenv("ATOM_TRUST_CALIBRATION_ENABLED", "true")
        tc_client.app.dependency_overrides[get_current_user] = lambda: Mock(
            id="u1", role="member", status="active"
        )
        r = tc_client.get("/api/v1/trust-calibration/stats")
        assert r.status_code == 403
