"""Legacy SQLite ``agent_registry`` repair through the real startup hook.

``AgentRegistry.promotion_episode_floor`` was added on 2026-09-23 without an
Alembic migration. A Personal-Edition SQLite file created before that date
therefore lacks the column, and *every* ORM read of the table fails with
``no such column: agent_registry.promotion_episode_floor`` — including
startup's ``ensure_admin_user → ensure_demo_agent`` and the ordinary
authenticated ``GET /api/agents/{id}`` read.

This replays the supported startup repair hook
(``core.sqlite_schema_repair.repair_known_drift``, called before
``Base.metadata.create_all`` in ``main_api_app``'s lifespan) against that
historical table shape, then exercises the real agent route in-process with
real RBAC/auth dependencies. It also proves the repair is idempotent across a
process restart (cleared in-process ``_REPAIRED`` cache) and that a seeded
legacy row survives with unrelated columns untouched.
"""
from __future__ import annotations

import os

# Explicit isolated test mode before any core import.
os.environ.setdefault("TESTING", "1")

from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

import core.database as database
from api.agent_routes import router as agent_router
from core import sqlite_schema_repair as schema_repair
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentRegistry, Tenant, User, Workspace

_MISSING = "promotion_episode_floor"


def _legacy_engine(tmp_path):
    """A DB whose agent_registry predates promotion_episode_floor."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy-agent-registry.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add_all([
            Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one",
                   edition="personal"),
            Workspace(id="ws-1", name="Workspace One", tenant_id="tenant-1"),
            User(
                id="admin-1", tenant_id="tenant-1", workspace_id="ws-1",
                email="admin@example.com", first_name="Admin", last_name="One",
                role="admin", status="active", is_active=True),
        ])
        db.commit()

    with engine.begin() as conn:
        # Simulate the pre-2026-09-23 shape exactly: current table minus the
        # one column the feature added. No other drift is introduced.
        conn.execute(text("ALTER TABLE agent_registry DROP COLUMN "
                          f"{_MISSING}"))
        conn.execute(text(
            "INSERT INTO agent_registry ("
            "id, name, category, role, type, capabilities, module_path, "
            "class_name, status, confidence_score, promotion_count, "
            "workspace_id, tenant_id) VALUES ("
            "'legacy-1', 'Legacy Agent', 'operations', 'agent', 'personal', "
            "'[]', 'agents.legacy', 'LegacyAgent', 'student', 0.42, 2, "
            "'ws-1', 'tenant-1')"))
    return engine, Session


def _run_startup_repair(engine, monkeypatch):
    """Invoke the same hook the app lifespan runs, bound to ``engine``."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session_cm():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(database, "get_db_session", _session_cm)
    schema_repair._REPAIRED.clear()
    schema_repair.repair_known_drift()


def _client(engine, user_id="admin-1"):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        actor = db.query(User).filter(User.id == user_id).one()

    app = FastAPI()
    app.include_router(agent_router)

    def _db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: actor
    return TestClient(app, raise_server_exceptions=False), Session


def test_legacy_agent_registry_floor_repaired_at_startup(tmp_path, monkeypatch):
    engine, Session = _legacy_engine(tmp_path)

    before_columns = {c["name"] for c in
                      inspect(engine).get_columns("agent_registry")}
    assert _MISSING not in before_columns

    # Negative control BEFORE repair: the ordinary ORM read (the shape used by
    # startup bootstrap) fails on the drifted table.
    with Session() as db:
        try:
            db.query(AgentRegistry).filter(
                AgentRegistry.id == "legacy-1").one()
        except OperationalError as exc:
            assert f"no such column: agent_registry.{_MISSING}" in str(exc)
        else:  # pragma: no cover - the legacy shape must fail
            raise AssertionError("legacy read unexpectedly succeeded")

    # ... and the authenticated user-facing read fails too.
    http, _ = _client(engine)
    assert http.get("/api/agents/legacy-1").status_code == 500

    # Supported startup repair (same hook main_api_app calls before create_all).
    _run_startup_repair(engine, monkeypatch)

    after_columns = {c["name"] for c in
                     inspect(engine).get_columns("agent_registry")}
    # Only the confirmed drifted field is added; no unrelated widening.
    assert after_columns - before_columns == {_MISSING}
    assert _MISSING in after_columns

    # Seeded legacy row is preserved and the new column reads back NULL.
    with Session() as db:
        row = db.query(AgentRegistry).filter(
            AgentRegistry.id == "legacy-1").one()
        assert (row.name, row.status, row.confidence_score,
                row.promotion_count) == ("Legacy Agent", "student", 0.42, 2)
        assert row.workspace_id == "ws-1"
        assert row.tenant_id == "tenant-1"
        assert row.promotion_episode_floor is None

    # Ordinary authenticated in-process HTTP read now succeeds.
    response = http.get("/api/agents/legacy-1")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["id"] == "legacy-1"
    assert data["name"] == "Legacy Agent"
    assert data["status"] == "student"

    # Focused promotion regression: the repaired column is writable through
    # the real per-agent promotion-floor settings surface.
    updated = http.patch(
        "/api/agents/legacy-1?operation_id=legacy-floor",
        json={"promotion_episode_floor": 7})
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["promotion_episode_floor"] == 7
    with Session() as db:
        assert db.query(AgentRegistry).filter(
            AgentRegistry.id == "legacy-1").one().promotion_episode_floor == 7

    # Idempotent across a simulated restart: cleared cache, same hook rerun.
    schema_repair._REPAIRED.clear()
    _run_startup_repair(engine, monkeypatch)
    assert {c["name"] for c in
            inspect(engine).get_columns("agent_registry")} == after_columns
    with Session() as db:
        rows = db.query(AgentRegistry).all()
        assert [r.id for r in rows] == ["legacy-1"]
        assert rows[0].promotion_episode_floor == 7
        assert rows[0].promotion_count == 2

    engine.dispose()
