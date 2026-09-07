"""Mini Apps — stateful canvas-UI apps (service + storage + routes + runtime).

TDD contract. All Firecracker execution is mocked — no real VM/KVM in CI.
"""
import contextlib
import os
import uuid

import pytest

from core.models import Canvas, CanvasAudit, CanvasLogic, CanvasState, MiniApp, MiniAppAsset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_app(db, name="calc", deps=None, scopes=None):
    user = type("U", (), {"id": "u1", "tenant_id": "t1", "workspace_id": "w1"})()
    # Unique ids per test: _make_app commits (the source canvas is the app's
    # dev canvas), and the worker DB persists across tests — fixed ids would
    # collide on the shared in-memory engine.
    canvas_id = f"c-{uuid.uuid4().hex[:12]}"
    app_id = f"app-{uuid.uuid4().hex[:12]}"
    canvas = Canvas(
        id=canvas_id, tenant_id="t1", created_by="u1", name=name,
        canvas_type="mini_app", content={"blocks": []}, style={}, status="active",
        mini_app_id=app_id,  # source canvas is the app's dev instance
    )
    db.add(canvas)
    db.add(CanvasLogic(canvas_id=canvas_id, language="python", source="state = {**state, 'n': state.get('n', 0) + 1}", created_by="u1"))
    app = MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by="u1", name=name,
        manifest={
            "declared_scopes": scopes or ["*"],
            "skills": [], "mcp_servers": [], "entrypoint": "logic",
            "dependencies": deps or [],
            "base_image": "python:3.11-slim", "assets": [],
            "storage": {"enabled": True, "backend": "local", "max_bytes_per_object": 5 * 1024 * 1024},
            "initial_state": {}, "blueprint": {},
        },
        blueprint_canvas_id=canvas_id, status="draft",
    )
    db.add(app)
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={"n": 0}, version=1))
    db.commit()
    return app, user


@pytest.fixture
def app_fixture(db_session):
    app, user = _make_app(db_session)
    return app, user


def _patch_db(monkeypatch, db_session):
    @contextlib.contextmanager
    def _cm():
        yield db_session
    # run_stateful imports get_db_session lazily from core.database, so patch it
    # at the source (not at core.mini_app_service, where it isn't an attribute).
    monkeypatch.setattr("core.database.get_db_session", _cm)


# ---------------------------------------------------------------------------
# validate_manifest
# ---------------------------------------------------------------------------
class TestValidateManifest:
    def test_valid(self):
        from core.mini_app_service import validate_manifest
        validate_manifest({
            "declared_scopes": ["*"], "dependencies": ["pandas==2.2"],
            "base_image": "python:3.11-slim", "assets": ["data.xlsx"],
            "storage": {"enabled": True, "backend": "local", "max_bytes_per_object": 1024},
        })

    def test_unknown_scope_raises(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["totally_bogus_tool"]})

    def test_bad_backend_raises(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "storage": {"backend": "nope"}})

    def test_bad_max_bytes_raises(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "storage": {"max_bytes_per_object": "big"}})

    def test_disallowed_base_image_raises(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "base_image": "ubuntu:latest"})


# ---------------------------------------------------------------------------
# resolve_effective_scopes
# ---------------------------------------------------------------------------
class TestResolveEffectiveScopes:
    def test_autonomous_star_full_floor(self):
        from core.mini_app_service import resolve_effective_scopes
        scopes = resolve_effective_scopes({"declared_scopes": ["*"]}, tier="autonomous")
        assert scopes == ("*",)

    def test_supervised_capped(self):
        from core.mini_app_service import resolve_effective_scopes
        scopes = resolve_effective_scopes({"declared_scopes": ["*"]}, tier="supervised")
        assert scopes != ("*",)
        assert len(scopes) > 0

    def test_no_viewer_read_only(self):
        from core.mini_app_service import resolve_effective_scopes
        scopes = resolve_effective_scopes({"declared_scopes": ["*"]})
        assert scopes != ("*",)  # student floor, never widens

    def test_never_widens_beyond_tier_floor(self):
        """Declared scopes never exceed the viewer's tier floor (P0 #5)."""
        from core.capability_resolver import resolve_allowed_tools
        from core.mini_app_service import resolve_effective_scopes
        from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS
        from types import SimpleNamespace

        for tier, floor in TIER_FLOOR_TOOL_WHITELISTS.items():
            # '*' declared → the effective set is the tier floor itself (or
            # '*' only when the AUTONOMOUS floor is already '*'), never wider.
            effective = resolve_effective_scopes({"declared_scopes": ["*"]}, tier=tier)
            assert effective == resolve_allowed_tools(SimpleNamespace(capabilities=None), tier=tier)
            # Declared specific scopes → intersected with the floor (bounded,
            # never widened). An unrestricted ('*',) floor passes them through
            # verbatim; any other floor narrows to its own members.
            specific = resolve_effective_scopes(
                {"declared_scopes": ["canvas_render", "memory_search"]}, tier=tier
            )
            if floor == ("*",):
                assert specific == ("canvas_render", "memory_search")
            else:
                assert set(specific).issubset(set(floor))


# ---------------------------------------------------------------------------
# syntax_check
# ---------------------------------------------------------------------------
class TestSyntaxCheck:
    def test_valid(self):
        from core.mini_app_service import syntax_check
        syntax_check("x = 1")

    def test_invalid_raises(self):
        from core.mini_app_service import syntax_check
        with pytest.raises(SyntaxError):
            syntax_check("def broken(:")


# ---------------------------------------------------------------------------
# prepare_runtime
# ---------------------------------------------------------------------------
class TestPrepareRuntime:
    def _patch_scanner(self, monkeypatch, safe=True):
        import core.mini_app_service as svc
        class FakeScanner:
            def scan_packages(self, reqs):
                return {"safe": safe, "vulnerabilities": [] if safe else [{"id": "V1"}], "conflicts": []}
        monkeypatch.setattr("core.package_dependency_scanner.PackageDependencyScanner", FakeScanner)

    def _patch_rootfs_dir(self, monkeypatch, tmp_path):
        import core.mini_app_service as svc
        monkeypatch.setattr(svc, "get_miniapp_rootfs_dir", lambda: str(tmp_path))
        return tmp_path

    def test_deps_unsafe_raises(self, db_session, app_fixture, monkeypatch):
        from core.mini_app_service import prepare_runtime
        app, _ = app_fixture
        app.manifest["dependencies"] = ["pandas==2.2"]
        self._patch_scanner(monkeypatch, safe=False)
        with pytest.raises(ValueError):
            prepare_runtime(app, db_session)

    def test_deps_rootfs_missing_raises(self, db_session, app_fixture, monkeypatch, tmp_path):
        from core.mini_app_service import prepare_runtime
        app, _ = app_fixture
        app.manifest["dependencies"] = ["pandas==2.2"]
        self._patch_scanner(monkeypatch, safe=True)
        self._patch_rootfs_dir(monkeypatch, tmp_path)
        with pytest.raises(RuntimeError) as e:
            prepare_runtime(app, db_session)
        assert "build_miniapp_rootfs.sh" in str(e.value)

    def test_deps_rootfs_present_sets_image(self, db_session, app_fixture, monkeypatch, tmp_path):
        from core.mini_app_service import prepare_runtime
        app, _ = app_fixture
        app.manifest["dependencies"] = ["pandas==2.2"]
        self._patch_scanner(monkeypatch, safe=True)
        root = self._patch_rootfs_dir(monkeypatch, tmp_path)
        (root / f"miniapp-{app.id}.ext4").write_bytes(b"x")
        path = prepare_runtime(app, db_session)
        assert path == str(root / f"miniapp-{app.id}.ext4")
        assert app.runtime_image == path
        assert app.runtime_version == 1

    def test_no_deps_returns_none(self, db_session, app_fixture):
        from core.mini_app_service import prepare_runtime
        app, _ = app_fixture
        assert prepare_runtime(app, db_session) is None
        assert app.runtime_image is None


# ---------------------------------------------------------------------------
# scaffold
# ---------------------------------------------------------------------------
class TestScaffold:
    def test_creates_source_canvas_and_draft(self, db_session):
        from core.mini_app_service import scaffold
        viewer = type("U", (), {"id": "u1", "tenant_id": "t1", "workspace_id": "w1"})()
        app, canvas_id = scaffold({}, "calc", ["*"], [], viewer, db_session)
        assert app.status == "draft"
        assert app.blueprint_canvas_id == canvas_id
        canvas = db_session.query(Canvas).filter(Canvas.id == canvas_id).first()
        assert canvas is not None and canvas.canvas_type == "mini_app"
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).first()
        assert logic is not None
        import ast
        ast.parse(logic.source)  # starter logic passes the syntax gate

    def test_scaffold_base_canvas_type_any_kind(self, db_session):
        """Any app family is buildable: spec.canvas_type becomes the blueprint's
        type + the manifest record — known types, unknown slugs, malformed."""
        from core.mini_app_service import scaffold, _validate_base_canvas_type
        from core.canvas_type_registry import canvas_type_registry
        viewer = type("U", (), {"id": "u1", "tenant_id": "t1", "workspace_id": "w1"})()

        for kind in ("crm", "accounting", "inventory", "sheets"):
            app, canvas_id = scaffold({"canvas_type": kind}, f"app-{kind}", ["canvas_render"], [], viewer, db_session)
            canvas = db_session.query(Canvas).filter(Canvas.id == canvas_id).first()
            assert canvas.canvas_type == kind, kind
            assert app.manifest["canvas_type"] == kind, kind
            # Unknown slugs self-register with generic defaults; known are kept.
            assert canvas_type_registry.validate_canvas_type(kind), kind
            # The scaffold audit row carries the type — read_canvas (the page
            # load path) serves FROM the audit trail.
            audit = (
                db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).first()
            )
            assert audit is not None and audit.canvas_type == kind, kind

        # Validation details: slug normalization and malformed rejection.
        assert _validate_base_canvas_type("  CRM ") == "crm"
        import pytest
        with pytest.raises(ValueError, match="slug"):
            _validate_base_canvas_type("Not A Slug!")

    def test_scaffold_default_type_is_mini_app(self, db_session):
        from core.mini_app_service import scaffold
        viewer = type("U", (), {"id": "u1", "tenant_id": "t1", "workspace_id": "w1"})()
        app, canvas_id = scaffold({}, "plain", ["canvas_render"], [], viewer, db_session)
        canvas = db_session.query(Canvas).filter(Canvas.id == canvas_id).first()
        assert canvas.canvas_type == "mini_app"
        assert app.manifest["canvas_type"] == "mini_app"


# ---------------------------------------------------------------------------
# publish / install
# ---------------------------------------------------------------------------
class TestPublishInstall:
    def test_publish_strips_credentials(self, db_session, app_fixture, monkeypatch, tmp_path):
        from core.mini_app_service import prepare_runtime, publish
        app, _ = app_fixture
        app.manifest["dependencies"] = []
        # plant a credential-shaped key in the source canvas content
        src = db_session.query(Canvas).filter(Canvas.id == app.blueprint_canvas_id).first()
        src.content = {"api_key": "sk-123", "safe": 1}
        db_session.commit()
        result = publish(app, db_session)
        assert result["success"]
        assert "api_key" not in str(app.manifest["blueprint"]["content"])
        assert app.status == "published"

    def test_install_hydrates_fresh_instance(self, db_session, app_fixture):
        from core.mini_app_service import install
        app, _ = app_fixture
        app.status = "published"
        # Reassign the whole manifest (not in-place mutation) so SQLAlchemy's
        # JSON column detects the change — in-place key assignment on a JSON
        # column isn't tracked without MutableDict/flag_modified.
        new_manifest = dict(app.manifest)
        new_manifest["blueprint"] = {
            "content": {"hello": 1}, "style": {},
            "logic_source": "state = state", "logic_language": "python",
            "component_installations": [],
        }
        new_manifest["initial_state"] = {"x": 1}
        app.manifest = new_manifest
        db_session.commit()
        viewer = type("U", (), {"id": "viewer1"})()
        new_id = install(app, viewer, db_session)
        canvas = db_session.query(Canvas).filter(Canvas.id == new_id).first()
        assert canvas.mini_app_id == app.id
        assert canvas.share_token is None
        assert canvas.status == "active"
        assert canvas.created_by == "viewer1"
        st = db_session.query(CanvasState).filter(CanvasState.canvas_id == new_id).first()
        assert st is not None and st.state == {"x": 1} and st.version == 1
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == new_id, CanvasAudit.action_type == "mini_app_install"
        ).all()
        assert len(audits) == 1
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == new_id).first()
        assert logic is not None

    def test_install_instance_inherits_base_canvas_type(self, db_session, app_fixture):
        """The instance renders as the app's base kind — e.g. an inventory
        tracker scaffolded on "inventory" installs as an inventory canvas.
        Apps without a manifest canvas_type keep the native mini_app type."""
        from core.mini_app_service import install
        app, _ = app_fixture
        app.status = "published"
        new_manifest = dict(app.manifest)
        new_manifest["canvas_type"] = "inventory"
        new_manifest["blueprint"] = {"content": {"hello": 1}, "style": {}, "logic_source": "state = state"}
        app.manifest = new_manifest
        db_session.commit()
        viewer = type("U", (), {"id": "viewer1"})()
        typed_id = install(app, viewer, db_session)
        typed = db_session.query(Canvas).filter(Canvas.id == typed_id).first()
        assert typed.canvas_type == "inventory"
        install_audit = (
            db_session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == typed_id, CanvasAudit.action_type == "mini_app_install")
            .first()
        )
        assert install_audit is not None and install_audit.canvas_type == "inventory"

        app2_manifest = dict(app.manifest)
        app2_manifest.pop("canvas_type")
        app.manifest = app2_manifest
        db_session.commit()
        legacy_id = install(app, viewer, db_session)
        legacy = db_session.query(Canvas).filter(Canvas.id == legacy_id).first()
        assert legacy.canvas_type == "mini_app"


# ---------------------------------------------------------------------------
# run_stateful / dev_run
# ---------------------------------------------------------------------------
class TestRunStateful:
    def _fake_runtime(self, monkeypatch, state_out, ops, image_log):
        import core.mini_app_service as svc
        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None, image=None, callback_handler=None, **kwargs):
                import json
                image_log.append(image)
                assert policy is not None
                assert getattr(policy, "tool_whitelist", None) == ("*",)
                assert "state" in inputs
                res = type("R", (), {
                    "success": True, "exit_code": 0, "stderr": "",
                    "stdout": "__MINIAPP_STATE__:" + json.dumps({"state": state_out, "storage_ops": ops}),
                })()
                return res
        monkeypatch.setattr(svc, "get_miniapp_runtime", FakeRuntime)

    @pytest.mark.asyncio
    async def test_run_bumps_version_and_forwards_image(self, db_session, app_fixture, monkeypatch):
        import core.mini_app_service as svc
        from core.mini_app_runtime import get_miniapp_rootfs_dir
        app, _ = app_fixture
        app.runtime_image = "/data/mini_app_rootfs/miniapp-app1.ext4"
        db_session.commit()
        image_log = []
        self._fake_runtime(monkeypatch, {"n": 1}, [], image_log)
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(app.blueprint_canvas_id, user_id="u1", scopes=("*",))
        assert result["success"]
        assert result["state"] == {"n": 1}
        assert result["version"] == 2
        assert image_log == ["/data/mini_app_rootfs/miniapp-app1.ext4"]
        st = db_session.query(CanvasState).filter(CanvasState.canvas_id == app.blueprint_canvas_id).first()
        assert st.version == 2 and st.state == {"n": 1}

    @pytest.mark.asyncio
    async def test_run_none_image_uses_template(self, db_session, app_fixture, monkeypatch):
        import core.mini_app_service as svc
        app, _ = app_fixture
        app.runtime_image = None
        db_session.commit()
        image_log = []
        self._fake_runtime(monkeypatch, {"n": 1}, [], image_log)
        _patch_db(monkeypatch, db_session)
        await svc.run_stateful(app.blueprint_canvas_id, user_id="u1", scopes=("*",))
        assert image_log == [None]  # None → base template rootfs

    @pytest.mark.asyncio
    async def test_run_storage_ops_put(self, db_session, app_fixture, monkeypatch, tmp_path):
        import core.mini_app_service as svc
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path))
        app, _ = app_fixture
        app.runtime_image = None
        db_session.commit()
        self._fake_runtime(monkeypatch, {"n": 1}, [{"op": "put", "key": "data.txt", "data": "hello"}], [])
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(app.blueprint_canvas_id, user_id="u1", scopes=("*",))
        assert result["success"]
        assert result["op_results"][0]["ok"] is True
        row = db_session.query(MiniAppAsset).filter(
            MiniAppAsset.canvas_id == app.blueprint_canvas_id, MiniAppAsset.key == "data.txt"
        ).first()
        assert row is not None and row.size == 5

    @pytest.mark.asyncio
    async def test_dev_run_persist_false_no_commit(self, db_session, app_fixture, monkeypatch):
        import core.mini_app_service as svc
        app, _ = app_fixture
        app.runtime_image = None
        db_session.commit()
        self._fake_runtime(monkeypatch, {"n": 99}, [{"op": "put", "key": "x", "data": "y"}], [])
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(app.blueprint_canvas_id, user_id="u1", scopes=("*",), persist=False)
        assert result["success"]
        st = db_session.query(CanvasState).filter(CanvasState.canvas_id == app.blueprint_canvas_id).first()
        assert st.version == 1 and st.state == {"n": 0}  # unchanged
        assert db_session.query(MiniAppAsset).filter(MiniAppAsset.canvas_id == app.blueprint_canvas_id).count() == 0


# ---------------------------------------------------------------------------
# MiniAppStorage
# ---------------------------------------------------------------------------
class TestMiniAppStorage:
    def test_local_roundtrip(self, tmp_path):
        from core.mini_app_storage import MiniAppStorage, LocalFileSystemBackend
        st = MiniAppStorage(LocalFileSystemBackend(str(tmp_path)), "t1", "c1")
        uri = st.store("a/b.txt", b"data", content_type="text/plain")
        assert st.exists("a/b.txt")
        assert st.retrieve("a/b.txt") == b"data"
        # The facade namespaces keys internally (t1/c1/...) but exposes logical
        # keys to callers — consistent with the S3 backend's list_keys().
        assert st.list_keys() == ["a/b.txt"]
        st.delete("a/b.txt")
        assert not st.exists("a/b.txt")

    def test_path_traversal_rejected(self, tmp_path):
        from core.mini_app_storage import MiniAppStorage, LocalFileSystemBackend, validate_key
        st = MiniAppStorage(LocalFileSystemBackend(str(tmp_path)), "t1", "c1")
        for bad in ("../evil", "..%2fevil", "/abs", ""):
            with pytest.raises(ValueError):
                st.store(bad, b"x")
        with pytest.raises(ValueError):
            validate_key("../etc/passwd")

    def test_cloud_backend_returns_s3_uri(self, monkeypatch, tmp_path):
        from core.mini_app_storage import MiniAppStorage, S3StorageBackend
        class FakeSvc:
            def __init__(self):
                self.uploaded = []
            def upload_file(self, stream, key, content_type=None):
                self.uploaded.append(key)
                return f"s3://bucket/{key}"
            def download_file(self, key): return b"z"
            def delete_object(self, key): return True
            def check_exists(self, key): return True
            def list_keys(self, prefix=""): return []
        svc = FakeSvc()
        st = MiniAppStorage(S3StorageBackend(svc, "mini-apps"), "t1", "c1")
        uri = st.store("data.txt", b"z")
        assert uri == "s3://bucket/mini-apps/t1/c1/data.txt"
        assert st.retrieve("data.txt") == b"z"


# ---------------------------------------------------------------------------
# CanvasLogicService.run with scopes
# ---------------------------------------------------------------------------
class TestCanvasLogicScopes:
    @pytest.mark.asyncio
    async def test_scopes_set_tool_whitelist(self, db_session, monkeypatch):
        from core import canvas_logic_service as cls
        from dataclasses import dataclass
        @dataclass
        class Policy:
            tool_whitelist: tuple = ()
        seen = {}
        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None, image=None, callback_handler=None, **kwargs):
                seen["wl"] = getattr(policy, "tool_whitelist", None)
                res = type("R", (), {"success": True, "stdout": "", "stderr": "", "exit_code": 0})()
                return res
        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())
        monkeypatch.setattr("core.sandbox_policy.PolicyIssuer.issue", lambda self, **kw: Policy())
        svc = cls.CanvasLogicService(db_session)
        svc.save_logic(canvas_id="c9", source="x=1", created_by="u1")
        await svc.run("c9", inputs={}, scopes=("canvas_render",))
        assert seen["wl"] == ("canvas_render",)


# ---------------------------------------------------------------------------
# Route guards
# ---------------------------------------------------------------------------
class TestRouteGuards:
    def test_migration_has_guards(self):
        src = open("alembic/versions/20260805_add_mini_apps.py").read()
        assert "_table_exists" in src and "_column_exists" in src
        assert "op.batch_alter_table" in src
