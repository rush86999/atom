"""The documented minimal_app dev launcher repairs legacy SQLite drift.

``docs/development/DEVELOPMENT_SETUP.md`` runs the daily dev loop with
``uvicorn minimal_app:app``. That entrypoint has its own startup hook, so the
``agent_registry.promotion_episode_floor`` repair added to ``main_api_app``'s
lifespan (df0fb0f3c) never ran there: ``ensure_admin_user →
ensure_demo_agent`` silently failed and the next ordinary agent read died on
``no such column``.

This runs the launcher's real ``_startup_bootstrap`` in a subprocess against a
scratch SQLite file, with ``TESTING=1`` and the scratch ``DATABASE_URL`` set
before any import. That also pins import identity: the hook must use the same
``core.database`` engine the routers and ``core.admin_bootstrap`` use, not a
second ``backend.core.database`` module with its own engine/metadata.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent

_CHILD = textwrap.dedent(
    """
    import json
    import os

    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import sessionmaker

    from core.database import Base, DATABASE_URL
    from core.models import AgentRegistry, Tenant, User, Workspace

    MISSING = "promotion_episode_floor"
    scratch_url = os.environ["ATOM_SCRATCH_DB_URL"]
    assert DATABASE_URL == scratch_url, (DATABASE_URL, scratch_url)

    engine = create_engine(
        scratch_url, connect_args={"check_same_thread": False, "timeout": 30})
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
        conn.execute(text(f"ALTER TABLE agent_registry DROP COLUMN {MISSING}"))
        conn.execute(text(
            "INSERT INTO agent_registry ("
            "id, name, category, role, type, capabilities, module_path, "
            "class_name, status, confidence_score, promotion_count, "
            "workspace_id, tenant_id) VALUES ("
            "'legacy-1', 'Legacy Agent', 'operations', 'agent', 'personal', "
            "'[]', 'agents.legacy', 'LegacyAgent', 'student', 0.42, 2, "
            "'ws-1', 'tenant-1')"))

    before = {c["name"] for c in
              inspect(engine).get_columns("agent_registry")}
    assert MISSING not in before

    # Negative control: ordinary ORM read fails on the legacy shape BEFORE
    # the launcher's startup hook runs.
    with Session() as db:
        try:
            db.query(AgentRegistry).one()
        except OperationalError as exc:
            assert f"no such column: agent_registry.{MISSING}" in str(exc)
        else:  # pragma: no cover - the legacy shape must fail
            raise AssertionError("legacy read unexpectedly succeeded")

    import minimal_app
    minimal_app._startup_bootstrap()

    after = {c["name"] for c in
             inspect(engine).get_columns("agent_registry")}
    # Only the confirmed drifted field is added.
    assert after - before == {MISSING}, (before, after)

    with Session() as db:
        rows = db.query(AgentRegistry).order_by(AgentRegistry.id).all()
        legacy = db.query(AgentRegistry).filter(
            AgentRegistry.id == "legacy-1").one()
        assert (legacy.name, legacy.status, legacy.confidence_score,
                legacy.promotion_count) == ("Legacy Agent", "student", 0.42, 2)
        assert legacy.workspace_id == "ws-1"
        assert legacy.tenant_id == "tenant-1"
        assert legacy.promotion_episode_floor is None
        assert any(r.name == "Demo Assistant" and r.category == "system"
                   for r in rows), (
            "startup admin bootstrap did not create the demo agent; the "
            "repair must run before ensure_admin_user")
        ids = [r.id for r in rows]

    # Idempotent across a second startup on the same file.
    minimal_app._startup_bootstrap()
    with Session() as db:
        ids_after_restart = [r.id for r in
                             db.query(AgentRegistry).order_by(
                                 AgentRegistry.id).all()]
        assert ids_after_restart == ids
        assert db.query(AgentRegistry).filter(
            AgentRegistry.id == "legacy-1").one().promotion_count == 2

    engine.dispose()
    print(json.dumps({
        "ids": ids,
        "columns_added": sorted(after - before),
        "legacy_read": "ok",
    }))
    """
)


def test_documented_minimal_app_launcher_repairs_legacy_agent_registry(
        tmp_path):
    scratch_db = tmp_path / "legacy-minimal-app.db"
    child = tmp_path / "run_minimal_app_startup.py"
    child.write_text(_CHILD)

    env = {
        "TESTING": "1",
        "DATABASE_URL": f"sqlite:///{scratch_db}",
        "ATOM_SCRATCH_DB_URL": f"sqlite:///{scratch_db}",
        # Never write a bootstrap password anywhere near the repo.
        "ATOM_BOOTSTRAP_PASSWORD_FILE": str(tmp_path / "admin-password.txt"),
        "PYTHONPATH": os.pathsep.join((str(REPO_ROOT), str(BACKEND))),
        # TESTING=1 only honors an explicit non-dev DB when the process is
        # recognizably a pytest child (see core.database.get_database_url).
        "PYTEST_CURRENT_TEST": os.environ.get(
            "PYTEST_CURRENT_TEST", "test_minimal_app_startup"),
        "PYTHONUNBUFFERED": "1",
    }
    completed = subprocess.run(
        [sys.executable, str(child)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, (
        f"minimal_app startup did not repair the legacy registry.\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}")
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["columns_added"] == ["promotion_episode_floor"]
    assert "legacy-1" in result["ids"]
    assert result["legacy_read"] == "ok"

    # The only database this test touched is the scratch file under tmp_path.
    assert scratch_db.exists()
    assert not (tmp_path / "admin-password.txt").exists(), (
        "the seeded admin user should prevent bootstrap from generating a "
        "credential file")
