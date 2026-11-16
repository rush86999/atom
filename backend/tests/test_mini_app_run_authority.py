"""Mini-app run authority — an actor must not cross into someone else's canvas.

Reported hole: ``tools.mini_app_tool.mini_app_run`` passed a caller-supplied
``canvas_id`` straight into ``core.mini_app_service.run_stateful`` with no
canvas authorization, so actor B could read actor A's ``CanvasState``, execute
the app, and write state/storage/records/broadcasts on A's instance.

These are integration regressions: a real file-backed scratch SQLite database,
the ACTUAL ``tools.mini_app_tool`` handlers (dispatched exactly as the agent
loop / RPC surface does), and the real ``core.canvas_authority`` gate. Only the
Firecracker guest is faked — the host executor is the code under test.

Every denial asserts the full effect surface is untouched:
  * no ``CanvasState`` read (``_read_state`` spy),
  * no asset/record/data-source/integration injection,
  * no policy/FS allocation (the per-canvas rootfs is never created),
  * no runtime call,
  * no storage/record execution,
  * no state/record commit, no ``canvas:update`` broadcast, no audit receipt.

Scratch DB only: ``TESTING=1`` + an explicit per-test SQLite file. No live DB,
no credentials, no network, no VM.
"""
from __future__ import annotations

import contextlib
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import (  # noqa: E402
    Canvas,
    CanvasAudit,
    CanvasLogic,
    CanvasRecord,
    CanvasState,
    MiniApp,
    MiniAppAsset,
    Tenant,
    User,
    Workspace,
)
from core.models_registration import Base  # noqa: E402


# ---------------------------------------------------------------------------
# Scratch world
# ---------------------------------------------------------------------------
class World:
    """One scratch SQLite file per test; every actor/canvas is a real row."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/miniapp_authority.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:8]
        with self.Session() as db:
            for tenant_id in ("tenant-a", "tenant-b"):
                db.add(Tenant(
                    id=tenant_id, name=tenant_id,
                    subdomain=f"{tenant_id}-{suffix}",
                    edition="personal", is_active=True,
                ))
            db.add_all([
                Workspace(id="ws-a", name="A", tenant_id="tenant-a"),
                Workspace(id="ws-a-other", name="A other", tenant_id="tenant-a"),
                Workspace(id="ws-b", name="B", tenant_id="tenant-b"),
            ])
            db.commit()

    def actor(self, user_id, *, tenant_id, workspace_id, active=True):
        with self.Session() as db:
            db.add(User(
                id=user_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                email=f"{user_id}@authority.test",
                hashed_password="x",
                first_name="Test",
                last_name="Actor",
                role="member",
                status="active",
                is_active=active,
            ))
            db.commit()

    def app(self, *, author, tenant_id, workspace_id, manifest=None,
            canvas_id=None, blueprint_of=None, status="draft"):
        """Create a MiniApp (+ its blueprint canvas/logic/audit) and return ids."""
        app_id = f"app-{uuid.uuid4().hex[:10]}"
        blueprint_id = canvas_id or f"cv-{uuid.uuid4().hex[:10]}"
        manifest = dict(manifest or {
            "declared_scopes": ["*"],
            "skills": [], "mcp_servers": [], "integrations": [],
            "entrypoint": "logic", "dependencies": [],
            "base_image": "python:3.11-slim", "assets": [],
            "storage": {"enabled": True, "backend": "local",
                        "max_bytes_per_object": 1024 * 1024},
            "db": {"enabled": True, "max_records_per_series": 100,
                   "max_record_bytes": 4096, "record_queries": []},
            "data_sources": [],
            "initial_state": {}, "blueprint": {},
        })
        with self.Session() as db:
            db.add(MiniApp(
                id=app_id, tenant_id=tenant_id, workspace_id=workspace_id,
                created_by=author, name="Counter", manifest=manifest,
                blueprint_canvas_id=blueprint_of or blueprint_id,
                status=status, runtime_version=0,
            ))
            if blueprint_of is None:
                db.add(Canvas(
                    id=blueprint_id, tenant_id=tenant_id,
                    workspace_id=workspace_id, created_by=author,
                    name="Counter", canvas_type="mini_app",
                    content={"blocks": []}, style={}, status="active",
                    mini_app_id=app_id,
                ))
                db.add(CanvasLogic(
                    canvas_id=blueprint_id, language="python",
                    source="state = state", created_by=author,
                ))
                db.add(CanvasAudit(
                    id=str(uuid.uuid4()), canvas_id=blueprint_id,
                    tenant_id=tenant_id, user_id=author,
                    canvas_type="mini_app", action_type="mini_app_scaffold",
                    details_json={"title": "Counter", "content": {"blocks": []}},
                ))
            db.commit()
        return app_id, blueprint_id

    def instance(self, *, app_id, installer, tenant_id, workspace_id):
        """Create an installed copy (canvas owner = installer, as ``install`` does)."""
        canvas_id = f"cv-{uuid.uuid4().hex[:10]}"
        with self.Session() as db:
            db.add(Canvas(
                id=canvas_id, tenant_id=tenant_id, workspace_id=workspace_id,
                created_by=installer, name="Counter", canvas_type="mini_app",
                content={"blocks": []}, style={}, status="active",
                mini_app_id=app_id,
            ))
            db.add(CanvasLogic(
                canvas_id=canvas_id, language="python",
                source="state = state", created_by=installer,
            ))
            db.add(CanvasState(
                canvas_id=canvas_id, tenant_id=tenant_id, state={"n": 0},
                version=1, created_by=installer,
            ))
            db.add(CanvasAudit(
                id=str(uuid.uuid4()), canvas_id=canvas_id,
                tenant_id=tenant_id, user_id=installer,
                canvas_type="mini_app", action_type="mini_app_install",
                details_json={"app_id": app_id, "canvas_type": "mini_app"},
            ))
            db.commit()
        return canvas_id

    def canvas(self, canvas_id):
        with self.Session() as db:
            return db.query(Canvas).filter(Canvas.id == canvas_id).first()

    def state(self, canvas_id):
        with self.Session() as db:
            return db.query(CanvasState).filter(
                CanvasState.canvas_id == canvas_id).first()

    def counts(self, canvas_id):
        with self.Session() as db:
            return {
                "state": db.query(CanvasState).filter(
                    CanvasState.canvas_id == canvas_id).count(),
                "assets": db.query(MiniAppAsset).filter(
                    MiniAppAsset.canvas_id == canvas_id).count(),
                "records": db.query(CanvasRecord).filter(
                    CanvasRecord.canvas_id == canvas_id).count(),
                "audits": db.query(CanvasAudit).filter(
                    CanvasAudit.canvas_id == canvas_id).count(),
            }


class FakeRuntime:
    """Deterministic guest: bumps ``n``, proposes one asset + one record row."""

    def __init__(self):
        self.calls = []

    async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                             image=None, callback_handler=None, **kwargs):
        self.calls.append({"policy": policy, "inputs": inputs})
        state = dict((inputs or {}).get("state") or {})
        state["n"] = int(state.get("n", 0)) + 1
        return SimpleNamespace(
            success=True, stdout="", stderr="", exit_code=0, truncated=False,
            metadata={"state_envelope": {
                "state": state,
                "storage_ops": [
                    {"op": "put", "key": "run.txt", "data": "hello",
                     "content_type": "text/plain"},
                ],
                "record_ops": [
                    {"op": "append", "series": "runs", "data": {"n": state["n"]}},
                ],
            }},
        )


_EFFECT_SPIES = {
    "_read_state": False,
    "_inject_assets": False,
    "_inject_record_queries": False,
    "_inject_data_sources": True,
    "_inject_integration_sources": True,
    "_make_callback_handler": False,
    "_execute_storage_op": False,
    "_execute_record_op": False,
}


@pytest.fixture
def world(tmp_path, monkeypatch):
    import core.mini_app_service as svc

    w = World(tmp_path)

    @contextlib.contextmanager
    def _session():
        db = w.Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("core.database.get_db_session", _session)
    monkeypatch.setenv("MINIAPP_STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("MINIAPP_ROOTFS_DIR", str(tmp_path / "rootfs"))

    w.runtime = FakeRuntime()
    monkeypatch.setattr(svc, "get_miniapp_runtime", lambda: w.runtime)
    w.broadcast_state = AsyncMock()
    w.broadcast_db = AsyncMock()
    monkeypatch.setattr(svc, "_broadcast_state", w.broadcast_state)
    monkeypatch.setattr(svc, "_broadcast_db", w.broadcast_db)

    w.spies = {}
    for name, is_async in _EFFECT_SPIES.items():
        cls = AsyncMock if is_async else MagicMock
        spy = cls(wraps=getattr(svc, name))
        monkeypatch.setattr(svc, name, spy)
        w.spies[name] = spy
    return w


def assert_no_effects(world, canvas_id, *, before_audits=None):
    """Nothing past authorization may have happened."""
    for name, spy in world.spies.items():
        assert spy.call_count == 0, f"{name} ran before/without authority"
    assert world.runtime.calls == [], "runtime executed without authority"
    world.broadcast_state.assert_not_awaited()
    world.broadcast_db.assert_not_awaited()
    counts = world.counts(canvas_id)
    assert counts["assets"] == 0
    assert counts["records"] == 0
    if before_audits is not None:
        assert counts["audits"] == before_audits
    # No policy/FS allocation: run_stateful creates the per-run rootfs dir
    # only after the gate.
    assert not (world.tmp_path / "rootfs").exists(), "run FS was allocated"
    assert not (world.tmp_path / "storage").exists(), "storage backend was touched"


def _tool():
    from tools import mini_app_tool

    return mini_app_tool


# ---------------------------------------------------------------------------
# Denial: foreign owner
# ---------------------------------------------------------------------------
class TestForeignOwnerDenied:
    @pytest.mark.asyncio
    async def test_actor_b_cannot_run_actor_a_instance(self, world):
        """The reported exploit: tools.mini_app_run actorB → A-owned canvas."""
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("bob", tenant_id="tenant-b", workspace_id="ws-b")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before = world.state(instance)
        before_audits = world.counts(instance)["audits"]

        result = await _tool().mini_app_run(
            {"canvas_id": instance, "inputs": {}}, {"user_id": "bob"})

        assert result["success"] is False
        assert result["http_status"] == 404
        assert result["error_code"] == "CANVAS_NOT_AUTHORIZED"
        # Non-owner gets the accepted canvas "not found" wording (no oracle).
        assert "not found" in result["error"].lower()
        assert_no_effects(world, instance, before_audits=before_audits)
        after = world.state(instance)
        assert after.version == before.version
        assert after.state == before.state
        assert world.canvas(instance).created_by == "alice"

    @pytest.mark.asyncio
    async def test_service_dry_run_is_also_gated(self, world):
        """persist=False (dev-run/acceptance semantics) must not leak state."""
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("bob", tenant_id="tenant-b", workspace_id="ws-b")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before_audits = world.counts(instance)["audits"]

        result = await run_stateful(instance, user_id="bob", persist=False)

        assert result["success"] is False
        assert result["error_code"] == "CANVAS_NOT_AUTHORIZED"
        assert_no_effects(world, instance, before_audits=before_audits)


# ---------------------------------------------------------------------------
# Denial: missing / contradictory identity
# ---------------------------------------------------------------------------
class TestIdentityRefused:
    @pytest.mark.asyncio
    async def test_tool_requires_an_authenticated_actor(self, world):
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before_audits = world.counts(instance)["audits"]

        result = await _tool().mini_app_run({"canvas_id": instance}, {})

        assert result["success"] is False
        assert "Authenticated user" in result["error"]
        assert_no_effects(world, instance, before_audits=before_audits)

    @pytest.mark.asyncio
    async def test_service_rejects_missing_actor_and_unknown_actor(self, world):
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before_audits = world.counts(instance)["audits"]

        missing = await run_stateful(instance, user_id=None)
        assert missing["success"] is False
        assert missing["error_code"] == "CANVAS_ACTOR_REFUSED"
        assert_no_effects(world, instance, before_audits=before_audits)

        unknown = await run_stateful(instance, user_id="ghost-user")
        assert unknown["success"] is False
        assert unknown["error_code"] == "CANVAS_ACTOR_REFUSED"
        assert_no_effects(world, instance, before_audits=before_audits)

    @pytest.mark.asyncio
    async def test_inactive_actor_is_refused(self, world):
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("frozen", tenant_id="tenant-a", workspace_id="ws-a",
                    active=False)
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="frozen",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before_audits = world.counts(instance)["audits"]

        result = await run_stateful(instance, user_id="frozen")

        assert result["success"] is False
        assert result["error_code"] == "CANVAS_ACTOR_REFUSED"
        assert "not active" in result["error"].lower()
        assert_no_effects(world, instance, before_audits=before_audits)

    @pytest.mark.asyncio
    async def test_contradictory_viewer_and_user_id_refused(self, world):
        """A caller-body viewer must never override/contradict the actor id."""
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("bob", tenant_id="tenant-b", workspace_id="ws-b")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before_audits = world.counts(instance)["audits"]

        result = await run_stateful(
            instance, user_id="alice",
            viewer=SimpleNamespace(id="bob", tenant_id="tenant-a",
                                   workspace_id="ws-a"))

        assert result["success"] is False
        assert result["error_code"] == "CANVAS_ACTOR_MISMATCH"
        assert_no_effects(world, instance, before_audits=before_audits)


# ---------------------------------------------------------------------------
# Denial: same actor id, authoritative scope differs (existing mechanism)
# ---------------------------------------------------------------------------
class TestScopeMismatchDenied:
    @pytest.mark.asyncio
    async def test_owner_id_in_foreign_tenant_is_refused(self, world):
        """Canvas.created_by matches, but the User row lives in another tenant.

        The caller's own claimed tenant/workspace (viewer body) must not turn
        this into a grant — the authoritative User row decides.
        """
        from core.mini_app_service import run_stateful

        world.actor("bob", tenant_id="tenant-b", workspace_id="ws-b")
        app_id, _ = world.app(author="bob", tenant_id="tenant-a",
                              workspace_id="ws-a")
        canvas_id = world.instance(app_id=app_id, installer="bob",
                                   tenant_id="tenant-a", workspace_id="ws-a")
        before_audits = world.counts(canvas_id)["audits"]

        result = await run_stateful(
            canvas_id, user_id="bob", persist=False,
            viewer=SimpleNamespace(id="bob", tenant_id="tenant-a",
                                   workspace_id="ws-a"))

        assert result["success"] is False
        assert result["http_status"] == 403
        assert "tenant" in result["error"].lower()
        assert_no_effects(world, canvas_id, before_audits=before_audits)

    @pytest.mark.asyncio
    async def test_owner_id_in_other_workspace_is_refused(self, world):
        from core.mini_app_service import run_stateful

        world.actor("carol", tenant_id="tenant-a", workspace_id="ws-a-other")
        app_id, _ = world.app(author="carol", tenant_id="tenant-a",
                              workspace_id="ws-a")
        canvas_id = world.instance(app_id=app_id, installer="carol",
                                   tenant_id="tenant-a", workspace_id="ws-a")
        before_audits = world.counts(canvas_id)["audits"]

        result = await run_stateful(canvas_id, user_id="carol")

        assert result["success"] is False
        assert result["http_status"] == 403
        assert "workspace" in result["error"].lower()
        assert_no_effects(world, canvas_id, before_audits=before_audits)


# ---------------------------------------------------------------------------
# Legitimate paths (the gate must not block the real operator)
# ---------------------------------------------------------------------------
class TestLegitimateRuns:
    @pytest.mark.asyncio
    async def test_owner_runs_and_persists_through_the_tool(self, world):
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")

        result = await _tool().mini_app_run(
            {"canvas_id": instance, "inputs": {}}, {"user_id": "alice"})

        assert result["success"] is True, result
        assert result["version"] == 2
        assert len(world.runtime.calls) == 1
        row = world.state(instance)
        assert row.version == 2 and row.state == {"n": 1}
        assert row.created_by == "alice"
        counts = world.counts(instance)
        assert counts["assets"] == 1 and counts["records"] == 1
        world.broadcast_state.assert_awaited_once()
        world.broadcast_db.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_installer_runs_copy_of_foreign_authored_app(self, world):
        """Installed-copy owner wins even though MiniApp.created_by differs."""
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("bob", tenant_id="tenant-b", workspace_id="ws-b")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a", status="published")
        instance = world.instance(app_id=app_id, installer="bob",
                                  tenant_id="tenant-b", workspace_id="ws-b")

        result = await _tool().mini_app_run(
            {"canvas_id": instance, "inputs": {}}, {"user_id": "bob"})

        assert result["success"] is True, result
        assert len(world.runtime.calls) == 1
        row = world.state(instance)
        assert row.created_by == "bob"
        assert row.version == 2
        with world.Session() as db:
            assert db.query(MiniApp).filter(
                MiniApp.id == app_id).one().created_by == "alice"

    @pytest.mark.asyncio
    async def test_coeditor_authorship_still_authorizes(self, world):
        """Existing rule: historical (non-event) audit authorship is an owner."""
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("dana", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        with world.Session() as db:
            db.add(CanvasAudit(
                id=str(uuid.uuid4()), canvas_id=instance,
                tenant_id="tenant-a", user_id="dana",
                canvas_type="mini_app", action_type="update",
                details_json={"title": "Counter"},
            ))
            db.commit()

        result = await _tool().mini_app_run(
            {"canvas_id": instance, "inputs": {}}, {"user_id": "dana"})

        assert result["success"] is True, result
        assert len(world.runtime.calls) == 1


# ---------------------------------------------------------------------------
# dev-run (dry) + acceptance-test call paths
# ---------------------------------------------------------------------------
class TestDryRunAndAcceptancePaths:
    @pytest.mark.asyncio
    async def test_dev_run_owner_dry_runs_without_effect(self, world):
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, blueprint = world.app(author="alice", tenant_id="tenant-a",
                                      workspace_id="ws-a")
        before = world.counts(blueprint)

        result = await _tool().mini_app_dev_run(
            {"app_id": app_id, "inputs": {}}, {"user_id": "alice"})

        assert result["success"] is True, result
        assert result["state"] == {"n": 1}
        assert len(world.runtime.calls) == 1
        assert result["op_results"][0]["proposed"] is True
        # Dry-run commits/proposes nothing and never broadcasts.
        world.broadcast_state.assert_not_awaited()
        world.broadcast_db.assert_not_awaited()
        assert world.counts(blueprint) == before

    @pytest.mark.asyncio
    async def test_dev_run_foreign_app_denied_before_runtime(self, world):
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("bob", tenant_id="tenant-b", workspace_id="ws-b")
        app_id, blueprint = world.app(author="alice", tenant_id="tenant-a",
                                      workspace_id="ws-a")
        before = world.counts(blueprint)

        result = await _tool().mini_app_dev_run(
            {"app_id": app_id, "inputs": {}}, {"user_id": "bob"})

        assert result["success"] is False
        assert "owner" in result["error"].lower()
        assert world.runtime.calls == []
        assert world.counts(blueprint) == before

    @pytest.mark.asyncio
    async def test_acceptance_run_tests_owner_grades_dry(self, world):
        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, blueprint = world.app(
            author="alice", tenant_id="tenant-a", workspace_id="ws-a",
            manifest={
                "declared_scopes": ["*"], "skills": [], "mcp_servers": [],
                "integrations": [], "entrypoint": "logic", "dependencies": [],
                "base_image": "python:3.11-slim", "assets": [],
                "storage": {"enabled": True, "backend": "local"},
                "db": {"enabled": True}, "data_sources": [],
                "initial_state": {},
                "tests": [
                    {"name": "increments", "inputs": {},
                     "initial_state": {"n": 0}, "expect_state": {"n": 1}},
                ],
            })
        before = world.counts(blueprint)

        result = await _tool().mini_app_run_tests(
            {"app_id": app_id}, {"user_id": "alice"})

        assert result["success"] is True, result
        assert result["total"] == 1 and result["passed"] == 1
        assert len(world.runtime.calls) == 1
        world.broadcast_state.assert_not_awaited()
        assert world.counts(blueprint) == before

    @pytest.mark.asyncio
    async def test_acceptance_path_denies_foreign_actor_without_runtime(self, world):
        """Service-level acceptance denial: every case fails closed, no VM."""
        from core.mini_app_service import run_tests

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        world.actor("bob", tenant_id="tenant-b", workspace_id="ws-b")
        app_id, blueprint = world.app(author="alice", tenant_id="tenant-a",
                                      workspace_id="ws-a")
        before_audits = world.counts(blueprint)["audits"]

        report = await run_tests(
            app_id, blueprint,
            [{"name": "case", "initial_state": {"n": 0},
              "expect_state": {"n": 1}}],
            viewer=SimpleNamespace(id="bob", tenant_id="tenant-b",
                                   workspace_id="ws-b"),
        )

        assert report["passed"] == 0
        assert report["total"] == 1
        assert report["results"][0]["passed"] is False
        assert "not found" in report["results"][0]["error"].lower()
        assert_no_effects(world, blueprint, before_audits=before_audits)


# ---------------------------------------------------------------------------
# In-run external dispatch: the pre-run grant is not reused
# ---------------------------------------------------------------------------
class MutatingRuntime:
    """Runs one guest, mutates authority mid-run, then fires one callback."""

    def __init__(self, world, mutate, *, service="notion"):
        self.world = world
        self.mutate = mutate
        self.service = service
        self.calls = 0
        self.callback_result = None

    async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                             image=None, callback_handler=None, **kwargs):
        self.calls += 1
        self.mutate()
        self.callback_result = await callback_handler({
            "kind": "fetch_integration", "service": self.service,
            "action": "search", "params": {"q": "x"},
        })
        state = dict((inputs or {}).get("state") or {})
        state["n"] = int(state.get("n", 0)) + 1
        return SimpleNamespace(
            success=True, stdout="", stderr="", exit_code=0, truncated=False,
            metadata={"state_envelope": {
                "state": state,
                "storage_ops": [],
                "record_ops": [],
            }},
        )


def _deactivate(world, user_id):
    def mutate():
        with world.Session() as db:
            db.query(User).filter(User.id == user_id).one().is_active = False
            db.commit()
    return mutate


def _move_workspace(world, canvas_id, workspace_id):
    def mutate():
        with world.Session() as db:
            db.query(Canvas).filter(Canvas.id == canvas_id).one().workspace_id = workspace_id
            db.commit()
    return mutate


def _dispatch_spies(monkeypatch):
    from core import mini_app_integration_dispatch as dispatch_mod

    resolve = AsyncMock(return_value=("native", None))
    dispatch = AsyncMock(return_value={"ok": True, "data": {"v": 1},
                                       "backend": "native"})
    monkeypatch.setattr(dispatch_mod, "resolve_backend", resolve)
    monkeypatch.setattr(dispatch_mod, "dispatch", dispatch)
    return resolve, dispatch


class TestInRunDispatchReauthorized:
    @pytest.mark.asyncio
    async def test_actor_deactivated_mid_guest_blocks_callback_dispatch(self, world, monkeypatch):
        """A callback fired after the actor was deactivated dispatches nothing.

        The persisting run's write gate then re-claims the stale actor and
        refuses, so the whole run leaves no state/storage/record/broadcast.
        """
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before = world.state(instance)
        before_counts = world.counts(instance)
        resolve, dispatch = _dispatch_spies(monkeypatch)
        world.runtime = MutatingRuntime(world, _deactivate(world, "alice"))

        result = await run_stateful(
            instance, user_id="alice", persist=True, scopes=("*",))

        assert world.runtime.calls == 1
        assert world.runtime.callback_result == {
            "ok": False, "error": "authority_denied"}
        resolve.assert_not_awaited()
        dispatch.assert_not_awaited()
        assert result["success"] is False
        assert result["error_code"] == "CANVAS_AUTHORITY_CHANGED"
        world.broadcast_state.assert_not_awaited()
        world.broadcast_db.assert_not_awaited()
        after = world.state(instance)
        assert (after.version, after.state) == (before.version, before.state)
        assert world.counts(instance) == before_counts

    @pytest.mark.asyncio
    async def test_workspace_moved_mid_guest_blocks_callback_dispatch(self, world, monkeypatch):
        """A canvas scope move after the pre-run gate revokes mid-run dispatch."""
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before = world.state(instance)
        resolve, dispatch = _dispatch_spies(monkeypatch)
        world.runtime = MutatingRuntime(
            world, _move_workspace(world, instance, "ws-a-other"))

        result = await run_stateful(
            instance, user_id="alice", persist=True, scopes=("*",))

        assert world.runtime.callback_result == {
            "ok": False, "error": "authority_denied"}
        assert world.runtime.calls == 1
        resolve.assert_not_awaited()
        dispatch.assert_not_awaited()
        # The post-guest write gate refuses: a fresh scope read sees the moved
        # target (CANVAS_NOT_AUTHORIZED), or — when the run session's
        # pre-guest snapshot is still identity-mapped — the guarded write
        # claim detects the move and matches zero rows (CANVAS_TARGET_CHANGED).
        # Both are the existing fail-closed mechanisms; neither writes.
        assert result["success"] is False
        assert result["error_code"] in {
            "CANVAS_NOT_AUTHORIZED", "CANVAS_TARGET_CHANGED"}
        assert result["http_status"] in (403, 409)
        after = world.state(instance)
        assert (after.version, after.state) == (before.version, before.state)
        assert world.counts(instance)["assets"] == 0
        assert world.counts(instance)["records"] == 0
        world.broadcast_state.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dry_run_rechecks_callbacks_and_stays_effect_free(self, world, monkeypatch):
        """Dry-run contract: revoked mid-run → callback denied, still no writes."""
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        before = world.state(instance)
        before_counts = world.counts(instance)
        resolve, dispatch = _dispatch_spies(monkeypatch)
        world.runtime = MutatingRuntime(world, _deactivate(world, "alice"))

        result = await run_stateful(
            instance, user_id="alice", persist=False, scopes=("*",))

        assert world.runtime.callback_result == {
            "ok": False, "error": "authority_denied"}
        resolve.assert_not_awaited()
        dispatch.assert_not_awaited()
        # The dry-run itself is proposal-only: nothing committed/broadcast.
        assert result["success"] is True
        assert result["proposed_ops"] == []
        world.broadcast_state.assert_not_awaited()
        world.broadcast_db.assert_not_awaited()
        after = world.state(instance)
        assert (after.version, after.state) == (before.version, before.state)
        assert world.counts(instance) == before_counts

    @pytest.mark.asyncio
    async def test_callback_dispatches_while_authority_holds(self, world, monkeypatch):
        """Positive control: the recheck must not block a legitimate dispatch."""
        from core.mini_app_service import run_stateful

        world.actor("alice", tenant_id="tenant-a", workspace_id="ws-a")
        app_id, _ = world.app(author="alice", tenant_id="tenant-a",
                              workspace_id="ws-a")
        instance = world.instance(app_id=app_id, installer="alice",
                                  tenant_id="tenant-a", workspace_id="ws-a")
        resolve, dispatch = _dispatch_spies(monkeypatch)
        world.runtime = MutatingRuntime(world, lambda: None)

        result = await run_stateful(
            instance, user_id="alice", persist=False, scopes=("*",))

        assert world.runtime.callback_result == {
            "ok": True, "data": {"v": 1}, "backend": "native"}
        resolve.assert_awaited_once()
        dispatch.assert_awaited_once()
        assert result["success"] is True
