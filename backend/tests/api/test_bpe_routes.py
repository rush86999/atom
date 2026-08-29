"""BPE workspace admin API tests (TestClient + dependency overrides).

Covers: admin gate, overview payload (flags/modes/thresholds/policy/
population/workspaces/telemetry), runtime-settings-driven flag overrides
(env wins > db row > default) reflected in bpe_enabled/automation flags,
workspace detail + 404, and the evidence-gated evolution apply endpoint.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.runtime_settings as rs
from api.bpe_routes import router as bpe_router
from core.auth import get_current_user
from core.bpe import automation, evolution, workspace
from core.bpe.actions import bpe_enabled
from core.bpe.telemetry import record_bpe_span
from core.database import Base, get_db
from core.models import RuntimeSetting, SettingChangeAudit, User, UserRole

_BPE_ENV_VARS = (
    "ATOM_BPE_WORKSPACE_ENABLED",
    "ATOM_BPE_AUTOMATION",
    "ATOM_BPE_CONSULT_POLICY",
    "ATOM_BPE_EVOLUTION",
    "ATOM_BPE_EVOLUTION_ENABLED",
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[RuntimeSetting.__table__, SettingChangeAudit.__table__],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    for var in _BPE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    rs.invalidate_settings_cache()
    workspace.reset_registry()
    yield
    workspace.reset_registry()
    rs.invalidate_settings_cache()
    workspace.set_active_bounds(None)


def _user(role: str = UserRole.ADMIN.value):
    u = type("U", (), {})()
    u.id = "admin-1"
    u.email = "admin@test.local"
    u.role = role
    return u


def _client(db, user):
    app = FastAPI()
    app.include_router(bpe_router)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Auth / roles
# ============================================================================


class TestAuth:
    def test_non_admin_gets_403(self, db):
        client = _client(db, _user(UserRole.MEMBER.value))
        assert client.get("/api/v1/admin/bpe/overview").status_code == 403
        assert (
            client.get(
                "/api/v1/admin/bpe/workspaces/detail",
                params={"workspace_id": "w", "agent_id": "a"},
            ).status_code
            == 403
        )
        assert client.post("/api/v1/admin/bpe/evolution/apply/fam").status_code == 403

    def test_unauthenticated_gets_401(self, db):
        app = FastAPI()
        app.include_router(bpe_router)

        def _deny():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = _deny
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/api/v1/admin/bpe/overview").status_code == 401


# ============================================================================
# Overview payload
# ============================================================================


class TestOverview:
    def test_full_payload_shape(self, db):
        client = _client(db, _user())
        resp = client.get("/api/v1/admin/bpe/overview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["modes"]["workspace_enabled"] is True  # default ON
        assert data["modes"]["automation_active"] is True
        assert data["modes"]["consult_gating_active"] is True
        flags = data["flags"]
        assert flags["ATOM_BPE_WORKSPACE_ENABLED"]["value"] is True
        assert flags["ATOM_BPE_WORKSPACE_ENABLED"]["source"] == "default"
        assert flags["ATOM_BPE_CONSULT_POLICY"]["value"] == "auto"
        assert data["thresholds"]["min_evaluated_genomes"] == 3
        assert set(data["gene_bounds"]) == set(workspace.GENE_BOUNDS)
        assert set(data["active_bounds"]) == set(workspace.GENE_BOUNDS)
        assert data["persistence"]["data_dir"]
        names = {a["name"] for a in data["meta_actions"]}
        assert {
            "workspace.track", "workspace.commit",
            "workspace.recall", "workspace.note",
        } <= names

    def test_env_override_shown_with_source(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_BPE_CONSULT_POLICY", "false")
        client = _client(db, _user())
        flags = client.get("/api/v1/admin/bpe/overview").json()["data"]["flags"]
        assert flags["ATOM_BPE_CONSULT_POLICY"]["value"] == "false"
        assert flags["ATOM_BPE_CONSULT_POLICY"]["source"] == "env"
        modes = client.get("/api/v1/admin/bpe/overview").json()["data"]["modes"]
        assert modes["consult_gating_active"] is False

    def test_db_override_shown_with_source(self, db):
        db.add(RuntimeSetting(key="ATOM_BPE_WORKSPACE_ENABLED", value_json=False))
        db.commit()
        rs.invalidate_settings_cache()
        client = _client(db, _user())
        data = client.get("/api/v1/admin/bpe/overview").json()["data"]
        assert data["flags"]["ATOM_BPE_WORKSPACE_ENABLED"]["value"] is False
        assert data["flags"]["ATOM_BPE_WORKSPACE_ENABLED"]["source"] == "db"
        assert data["modes"]["workspace_enabled"] is False
        assert bpe_enabled() is False

    def test_policy_snapshot_in_overview(self, db):
        policy = __import__(
            "core.bpe.consult_policy", fromlist=["get_consult_policy"]
        ).get_consult_policy()
        for _ in range(5):
            policy.record_episode("agent-x", consult_count=2, success=True,
                                  step_efficiency=1.0)
        client = _client(db, _user())
        data = client.get("/api/v1/admin/bpe/overview").json()["data"]
        state = data["consult_policy"]["agent-x"]
        assert state["episodes"] == 5
        assert state["value_ema"] == 1.0
        assert state["render_mode"] in ("full", "recall_only")
        assert "suppressed" in state and "harness_call_rate" in state

    def test_telemetry_aggregates_and_flips(self, db):
        record_bpe_span("recall", agent_id="a", success=True, latency_ms=1.0)
        record_bpe_span("recall", agent_id="a", success=False, latency_ms=2.0)
        automation.maybe_automation_flip(
            "evolution_apply", {"family": "sales", "fitness": 0.4})
        client = _client(db, _user())
        tel = client.get("/api/v1/admin/bpe/overview").json()["data"]["telemetry"]
        assert tel["aggregate"]["bpe.recall"]["count"] == 2
        assert tel["aggregate"]["bpe.recall"]["error_count"] == 1
        assert len(tel["automation_flips"]) == 1
        assert tel["automation_flips"][0]["detail"]["flip"] == "evolution_apply"


# ============================================================================
# Workspace registry surface
# ============================================================================


class TestWorkspaces:
    def _seed(self):
        ws = workspace.get_workspace("ws-ui", "agent-ui", "sess-1")
        ws._commit({"title": "draft invoice email"})
        return ws

    def test_summary_and_detail(self, db):
        self._seed()
        client = _client(db, _user())
        overview = client.get("/api/v1/admin/bpe/overview").json()["data"]
        summaries = [w for w in overview["workspaces"] if w["workspace_id"] == "ws-ui"]
        assert len(summaries) == 1
        assert summaries[0]["progress_count"] == 1
        assert summaries[0]["agent_id"] == "agent-ui"

        resp = client.get(
            "/api/v1/admin/bpe/workspaces/detail",
            params={"workspace_id": "ws-ui", "agent_id": "agent-ui",
                    "scope_key": "sess-1"},
        )
        assert resp.status_code == 200
        detail = resp.json()["data"]
        assert detail["progress"][0]["title"] == "draft invoice email"
        assert detail["experience"]["skills"] == []

    def test_detail_unknown_scope_404(self, db):
        client = _client(db, _user())
        resp = client.get(
            "/api/v1/admin/bpe/workspaces/detail",
            params={"workspace_id": "nope", "agent_id": "nope"},
        )
        assert resp.status_code == 404

    def test_detail_does_not_create(self, db):
        client = _client(db, _user())
        client.get(
            "/api/v1/admin/bpe/workspaces/detail",
            params={"workspace_id": "ghost", "agent_id": "ghost"},
        )
        assert workspace.list_workspace_summaries() == []


# ============================================================================
# Evolution readiness + apply endpoint
# ============================================================================


class TestEvolutionApply:
    def test_apply_empty_population_reports_no_genomes(self, db):
        client = _client(db, _user())
        body = client.post("/api/v1/admin/bpe/evolution/apply/empty-fam").json()
        assert body["applied"] is False
        assert "no evaluated genomes" in body["reason"]

    def test_readiness_in_overview(self, db, monkeypatch):
        import random as _random

        pop = evolution.Population(rng=_random.Random(7))
        for i, fitness in enumerate((0.1, 0.3, 0.5)):
            genome = evolution.random_genome(_random.Random(i))
            genome["max_subgoals"] = 4 + i  # guarantee distinct genomes
            pop.report("fam-a", genome, fitness)
        monkeypatch.setattr(evolution, "population", pop)
        client = _client(db, _user())
        rows = client.get("/api/v1/admin/bpe/overview").json()["data"][
            "evolution_readiness"]
        row = next(r for r in rows if r["family"] == "fam-a")
        assert row["evaluated_genomes"] == 3
        assert row["best_fitness"] == 0.5
        assert row["apply_ready"] is True

    def test_apply_force_override_deploys_genome(self, db, monkeypatch):
        import random as _random

        pop = evolution.Population(rng=_random.Random(7))
        genome = evolution.clamp_genome({
            "max_subgoals": 10, "recall_top_k": 3,
            "max_entries_per_category": 80, "max_render_chars": 2400,
        })
        pop.report("fam-b", genome, 0.5)
        monkeypatch.setattr(evolution, "population", pop)
        monkeypatch.setenv("ATOM_BPE_EVOLUTION_ENABLED", "true")
        client = _client(db, _user())
        body = client.post("/api/v1/admin/bpe/evolution/apply/fam-b").json()
        assert body["applied"] is True
        assert body["data"]["bounds"]["max_subgoals"] == 10
        assert workspace.get_active_bounds()["max_subgoals"] == 10

    def test_apply_held_without_evidence_or_override(self, db, monkeypatch):
        import random as _random

        pop = evolution.Population(rng=_random.Random(7))
        pop.report("fam-c", evolution.random_genome(_random.Random(2)), 0.9)
        monkeypatch.setattr(evolution, "population", pop)
        client = _client(db, _user())
        body = client.post("/api/v1/admin/bpe/evolution/apply/fam-c").json()
        assert body["applied"] is False
        assert "held" in body["reason"]


# ============================================================================
# Flag resolution semantics (shared with the automation module)
# ============================================================================


class TestFlagResolution:
    @staticmethod
    def _stub_db_rows(monkeypatch, rows: dict):
        # Hot-path flag checks resolve the DB leg through the global session;
        # stub the whole-table snapshot so tests stay hermetic.
        monkeypatch.setattr(rs, "_db_snapshot", lambda db=None: dict(rows))
        rs.invalidate_settings_cache()

    def test_env_beats_db_row(self, db, monkeypatch):
        self._stub_db_rows(monkeypatch, {"ATOM_BPE_CONSULT_POLICY": "true"})
        monkeypatch.setenv("ATOM_BPE_CONSULT_POLICY", "false")
        assert automation._flag("ATOM_BPE_CONSULT_POLICY") is False

    def test_db_row_breaks_tie_when_env_unset(self, db, monkeypatch):
        self._stub_db_rows(monkeypatch, {"ATOM_BPE_EVOLUTION": "false"})
        assert automation._flag("ATOM_BPE_EVOLUTION") is False
        assert automation.evolution_apply_enabled() is False

    def test_no_env_no_row_is_auto(self, db, monkeypatch):
        self._stub_db_rows(monkeypatch, {})
        assert automation._flag("ATOM_BPE_AUTOMATION") is None
        assert automation.automation_enabled() is True

    def test_workspace_flag_db_override(self, db, monkeypatch):
        self._stub_db_rows(monkeypatch, {"ATOM_BPE_WORKSPACE_ENABLED": False})
        assert bpe_enabled() is False

    def test_workspace_flag_db_override_true(self, db, monkeypatch):
        self._stub_db_rows(monkeypatch, {"ATOM_BPE_WORKSPACE_ENABLED": True})
        monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "0")
        assert bpe_enabled() is False
