"""Coverage-push + bug-hunt: core/mini_app_service.py + api/mini_app_routes.py.

TDD: failing tests first for every bug found, then minimal fixes.
Bugs hunted here:
  * upload_instance_asset lets a NON-owner write assets into another user's
    instance canvas of a public app (write-what-where; record/store mutations
    are owner-gated everywhere else).
  * record update/delete/delete-series routes ignore the manifest db.enabled
    gate (append + the record_ops envelope enforce it → fail-closed 503).

Firecracker runtime, storage and DB are mocked; no Docker/Firecracker.
"""
from __future__ import annotations

import contextlib
import json
import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import (
    Canvas,
    CanvasAudit,
    CanvasLogic,
    CanvasRecord,
    CanvasState,
    ComponentInstallation,
    IntegrationToken,
    MiniApp,
    MiniAppAsset,
    MiniAppInstallation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _viewer(user_id="u1", tenant_id="t1", workspace_id="w1", tier="autonomous"):
    return SimpleNamespace(
        id=user_id, tenant_id=tenant_id, workspace_id=workspace_id, tier=tier,
    )


def _make_app(
    db,
    name="calc",
    deps=None,
    scopes=None,
    owner="u1",
    status="draft",
    manifest_extra=None,
    canvas_id=None,
    app_id=None,
    with_logic=True,
):
    canvas_id = canvas_id or f"c-{uuid.uuid4().hex[:12]}"
    app_id = app_id or f"app-{uuid.uuid4().hex[:12]}"
    canvas = Canvas(
        id=canvas_id, tenant_id="t1", workspace_id="w1", created_by=owner,
        name=name, canvas_type="mini_app", content={"blocks": []}, style={},
        status="active", mini_app_id=app_id,
    )
    db.add(canvas)
    if with_logic:
        db.add(CanvasLogic(
            canvas_id=canvas_id, language="python",
            source="state = {**state, 'n': state.get('n', 0) + 1}",
            created_by=owner,
        ))
    manifest = {
        "declared_scopes": scopes or ["*"],
        "skills": [], "mcp_servers": [], "entrypoint": "logic",
        "dependencies": deps or [],
        "base_image": "python:3.11-slim", "assets": [],
        "storage": {"enabled": True, "backend": "local", "max_bytes_per_object": 1024 * 1024},
        "db": {"enabled": True, "max_records_per_series": 10, "max_record_bytes": 1024 * 100, "record_queries": []},
        "initial_state": {}, "blueprint": {},
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    app = MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by=owner,
        name=name, manifest=manifest, blueprint_canvas_id=canvas_id,
        status=status, runtime_version=0,
    )
    db.add(app)
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={"n": 0}, version=1))
    db.commit()
    return app, canvas_id, owner


def _patch_db(monkeypatch, db_session):
    @contextlib.contextmanager
    def _cm():
        yield db_session
    monkeypatch.setattr("core.database.get_db_session", _cm)


def _fake_runtime(monkeypatch, envelope=None, metadata=None, truncated=False, stdout_extra=""):
    import core.mini_app_service as svc

    class FakeRuntime:
        def __init__(self):
            self.seen = {}

        async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                                 image=None, callback_handler=None, **kwargs):
            self.seen["policy"] = policy
            self.seen["inputs"] = inputs
            self.seen["image"] = image
            if envelope is not None:
                stdout = "__MINIAPP_STATE__:" + json.dumps(envelope) + stdout_extra
            else:
                stdout = stdout_extra
            res = type("R", (), {
                "success": True, "exit_code": 0, "stderr": "",
                "stdout": stdout, "truncated": truncated,
                "metadata": metadata or {},
            })()
            return res

    fake = FakeRuntime()
    monkeypatch.setattr(svc, "get_miniapp_runtime", lambda: fake)
    return fake


def _record_op_db(db, canvas_id, app_id, series="chart_data", n=3):
    for i in range(n):
        from core.mini_app_db_service import append_record
        append_record(db, canvas_id, "t1", app_id, series, {"label": f"v{i}", "value": i}, created_by="u1")
    return series


# ===========================================================================
# validate_manifest / validate_tests error branches
# ===========================================================================
class TestManifestValidationBranches:
    def test_non_dict_manifest(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest([])

    def test_missing_scopes(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({})

    def test_non_string_scope(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": [1]})

    def test_wildcard_scope_accepted(self):
        from core.mini_app_service import validate_manifest
        validate_manifest({"declared_scopes": ["*"]})

    def test_bad_dependencies(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "dependencies": "numpy"})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "dependencies": [1]})

    def test_bad_storage_enabled(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "storage": {"enabled": "yes"}})

    def test_bad_db_config(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "db": [1]})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "db": {"enabled": "x"}})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "db": {"max_records_per_series": 0}})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "db": {"max_record_bytes": "big"}})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "db": {"record_queries": [1]}})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "db": {"record_queries": ["BAD SERIES!"]}})

    def test_bad_data_sources(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "data_sources": [1]})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "data_sources": ["docs"]})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "data_sources": [{"type": "nope"}]})

    def test_bad_integrations(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "integrations": {}})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "integrations": ["notion"]})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "integrations": [{"service": "", "action": "search"}]})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "integrations": [{"service": "notion"}]})
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "integrations": [{"service": "notion", "action": "search", "params": []}]})

    def test_bad_assets(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "assets": [1]})

    def test_mcp_servers_alias_warns(self, caplog):
        from core.mini_app_service import validate_manifest
        with caplog.at_level("WARNING", logger="core.mini_app_service"):
            validate_manifest({"declared_scopes": ["*"], "mcp_servers": [{"service": "notion", "action": "search"}]})
        assert any("deprecated" in r.message for r in caplog.records)

    def test_bad_tests(self):
        from core.mini_app_service import validate_manifest, validate_tests
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "tests": {}})
        with pytest.raises(ValueError):
            validate_tests(["not a dict"])
        with pytest.raises(ValueError):
            validate_tests([{"initial_state": []}])
        with pytest.raises(ValueError):
            validate_tests([{"expect_ops": "x"}])
        with pytest.raises(ValueError):
            validate_tests([{"name": 1, "expect_state": {}}])
        with pytest.raises(ValueError):
            validate_tests([{"inputs": {}}])
        validate_tests([{"name": "c", "initial_state": {"a": 1}, "inputs": {}, "expect_state": {"a": 1}, "expect_ops": []}])


# ===========================================================================
# prepare_runtime — fail-closed scan + rootfs
# ===========================================================================
class TestPrepareRuntime:
    def test_no_deps_clears_runtime_image(self, db_session, monkeypatch):
        from core.mini_app_service import prepare_runtime
        app, _, _ = _make_app(db_session)
        app.runtime_image = "/tmp/stale.ext4"
        db_session.commit()
        assert prepare_runtime(app, db_session) is None
        assert app.runtime_image is None

    def test_unsafe_deps_raise(self, db_session, monkeypatch):
        from core.mini_app_service import prepare_runtime
        app, _, _ = _make_app(db_session, deps=["pandas==9.9"])
        monkeypatch.setattr(
            "core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
            lambda self, pkgs: {"safe": False, "vulnerabilities": ["CVE-1"], "conflicts": []},
        )
        with pytest.raises(ValueError, match="fail-closed"):
            prepare_runtime(app, db_session)

    def test_rootfs_missing_raises(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import prepare_runtime
        monkeypatch.setattr(
            "core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
            lambda self, pkgs: {"safe": True, "vulnerabilities": [], "conflicts": []},
        )
        monkeypatch.setenv("MINIAPP_ROOTFS_DIR", str(tmp_path / "rootfs"))
        app, _, _ = _make_app(db_session, deps=["numpy"])
        with pytest.raises(RuntimeError, match="build_miniapp_rootfs"):
            prepare_runtime(app, db_session)

    def test_rootfs_present_sets_image_and_bumps_version(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import prepare_runtime
        monkeypatch.setattr(
            "core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
            lambda self, pkgs: {"safe": True, "vulnerabilities": [], "conflicts": []},
        )
        rootfs = tmp_path / "rootfs"
        rootfs.mkdir()
        monkeypatch.setenv("MINIAPP_ROOTFS_DIR", str(rootfs))
        app, _, _ = _make_app(db_session, deps=["numpy"])
        (rootfs / f"miniapp-{app.id}.ext4").write_bytes(b"x")
        path = prepare_runtime(app, db_session)
        assert path == str(rootfs / f"miniapp-{app.id}.ext4")
        assert app.runtime_version == 1
        # Idempotent: same path → no bump.
        prepare_runtime(app, db_session)
        assert app.runtime_version == 1


# ===========================================================================
# syntax_check / envelope helpers
# ===========================================================================
class TestSyntaxAndEnvelope:
    def test_empty_source_raises(self):
        from core.mini_app_service import syntax_check
        with pytest.raises(SyntaxError):
            syntax_check("   ")
        with pytest.raises(SyntaxError):
            syntax_check("def broken(:")

    def test_parse_envelope_missing_and_invalid(self):
        from core.mini_app_service import _parse_envelope
        assert _parse_envelope("") is None
        assert _parse_envelope("no marker here") is None
        assert _parse_envelope("__MINIAPP_STATE__:{not json}") is None
        assert _parse_envelope("x\n__MINIAPP_STATE__:{\"a\": 1}\n") == {"a": 1}


# ===========================================================================
# storage op validation branches
# ===========================================================================
class TestValidateStorageOp:
    def test_invalid_shapes_rejected(self):
        from core.mini_app_service import _validate_storage_op
        assert _validate_storage_op("nope", 100) is None
        assert _validate_storage_op({"op": "write"}, 100) is None
        assert _validate_storage_op({"op": "put"}, 100) is None
        assert _validate_storage_op({"op": "put", "key": ""}, 100) is None
        assert _validate_storage_op({"op": "put", "key": "k" * 501, "data": "x"}, 100) is None
        assert _validate_storage_op({"op": "put", "key": "k", "data": None}, 100) is None
        assert _validate_storage_op({"op": "put", "key": "k", "data": 42}, 100) is None

    def test_base64_roundtrip_and_errors(self):
        import base64
        from core.mini_app_service import _validate_storage_op
        op = _validate_storage_op(
            {"op": "put", "key": "bin", "data": base64.b64encode(b"\x00\x01").decode(), "encoding": "base64"},
            100,
        )
        assert op["data"] == b"\x00\x01"
        assert _validate_storage_op({"op": "put", "key": "k", "data": "!!!", "encoding": "base64"}, 100) is None
        assert _validate_storage_op({"op": "put", "key": "k", "data": [1, 2], "encoding": "base64"}, 100) is None

    def test_oversize_and_get_delete(self):
        from core.mini_app_service import _validate_storage_op
        assert _validate_storage_op({"op": "put", "key": "k", "data": "x" * 101}, 100) is None
        assert _validate_storage_op({"op": "get", "key": "k"}, 100) == {"op": "get", "key": "k"}
        assert _validate_storage_op({"op": "delete", "key": "k"}, 100) == {"op": "delete", "key": "k"}


# ===========================================================================
# record op validation branches
# ===========================================================================
class TestValidateRecordOp:
    def _v(self, op, cap=1024):
        from core.mini_app_service import _validate_record_op
        return _validate_record_op(op, cap)

    def test_bad_shapes(self):
        assert self._v("nope") is None
        assert self._v({"op": "drop_table"}) is None
        assert self._v({"op": "append", "series": "BAD!"}) is None
        assert self._v({"op": "append", "series": "ok", "data": []}) is None
        assert self._v({"op": "append", "series": "ok", "data": {"a": 1}, "id": 5}) is None
        assert self._v({"op": "update", "series": "ok"}) is None
        assert self._v({"op": "delete", "series": "ok"}) is None
        assert self._v({"op": "query", "series": "ok", "filter": {"a": []}}) is None
        assert self._v({"op": "query", "series": "ok", "limit": 0}) is None
        assert self._v({"op": "query", "series": "ok", "limit": 10001}) is None
        assert self._v({"op": "query", "series": "ok", "order": "sideways"}) is None
        assert self._v({"op": "update_many", "series": "ok", "filter": [1]}) is None

    def test_valid_shapes(self):
        assert self._v({"op": "clear"})["op"] == "clear"
        assert self._v({"op": "list_series"})["op"] == "list_series"
        v = self._v({"op": "append", "series": "ok", "data": {"a": 1}, "id": "r1"})
        assert v["id"] == "r1"
        v = self._v({"op": "query", "series": "ok", "filter": {"a": 1}, "limit": 5, "order": "asc"})
        assert v["limit"] == 5 and v["order"] == "asc"
        v = self._v({"op": "update_many", "series": "ok", "filter": {"a": 1}, "data": {"b": 2}})
        assert v["data"] == {"b": 2}
        v = self._v({"op": "count", "series": "ok", "filter": {"a": 1}})
        assert v["filter"] == {"a": 1}
        v = self._v({"op": "update", "series": "ok", "id": "r1", "data": {"b": 2}})
        assert v["id"] == "r1"

    def test_get_op_carries_id(self):
        """BUG (MED): 'get' record ops were validated without carrying an id,
        so every get-by-id op in the envelope failed with a generic error."""
        v = self._v({"op": "get", "series": "ok", "id": "r1"})
        assert v["id"] == "r1"

    def test_record_data_size_cap(self):
        assert self._v({"op": "append", "series": "ok", "data": {"pad": "x" * 2000}}, cap=100) is None


# ===========================================================================
# scaffold — including the LLM-assisted path
# ===========================================================================
class TestScaffold:
    def test_scaffold_basic(self, db_session):
        from core.mini_app_service import scaffold
        app, canvas_id = scaffold(
            {"description": "d"}, "my app", ["canvas_render"], [], _viewer(), db_session,
        )
        assert app.status == "draft" and app.blueprint_canvas_id == canvas_id
        assert db_session.query(Canvas).filter(Canvas.id == canvas_id).first().canvas_type == "mini_app"
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).first()
        assert "state = result" in logic.source
        assert db_session.query(MiniApp).filter(MiniApp.id == app.id).first() is not None

    def test_scaffold_llm_path(self, db_session, monkeypatch):
        """BUG (MED): _llm_scaffold imported a nonexistent module attribute
        (core.llm_service.llm_service) and called a nonexistent method
        (.complete) — the ATOM_MINIAAP_LLM_SCAFFOLD opt-in silently never
        worked and always fell back to the template."""
        from core.mini_app_service import scaffold
        monkeypatch.setenv("ATOM_MINIAAP_LLM_SCAFFOLD", "true")
        calls = {}

        class FakeLLM:
            async def generate_completion(self, messages, **kw):
                calls["prompt"] = messages[0]["content"]
                return {"success": True, "content": "result = dict(state)\nresult['llm'] = True\nstate = result"}

        monkeypatch.setattr("core.llm_service.LLMService", FakeLLM)
        app, canvas_id = scaffold({}, "llm app", ["*"], [], _viewer(), db_session)
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).first()
        assert "llm" in logic.source
        assert "llm app" in calls["prompt"]

    def test_scaffold_llm_bad_code_falls_back(self, db_session, monkeypatch):
        from core.mini_app_service import scaffold
        monkeypatch.setenv("ATOM_MINIAAP_LLM_SCAFFOLD", "true")

        class BadLLM:
            async def generate_completion(self, messages, **kw):
                return {"success": True, "content": "def broken(:"}

        monkeypatch.setattr("core.llm_service.LLMService", BadLLM)
        app, canvas_id = scaffold({}, "bad llm app", ["*"], [], _viewer(), db_session)
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).first()
        assert "state = result" in logic.source


# ===========================================================================
# publish — blueprint snapshot + sanitization
# ===========================================================================
class TestPublish:
    def test_publish_snapshot_and_strip_credentials(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import publish
        app, canvas_id, _ = _make_app(db_session)
        state_row = db_session.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).first()
        state_row.state = {"n": 1, "api_key": "sk-secret", "ok": True}
        db_session.commit()
        db_session.add(ComponentInstallation(
            tenant_id="t1", canvas_id=canvas_id, component_id="comp-1",
            config={"api_key": "sekrit", "theme": "dark"}, position=0, z_index=1,
        ))
        db_session.commit()
        res = publish(app, db_session, public=True)
        assert res["success"] and res["is_public"] and res["share_token"]
        assert app.status == "published"
        assert app.manifest["initial_state"] == {"n": 1, "ok": True}
        assert app.manifest["blueprint"]["logic_source"]
        assert app.manifest["blueprint"]["component_installations"][0]["config"] == {"theme": "dark"}
        assert "api_key" not in json.dumps(app.manifest)

    def test_publish_public_keeps_existing_token(self, db_session):
        from core.mini_app_service import publish
        app, _, _ = _make_app(db_session)
        app.share_token = "tok-1"
        db_session.commit()
        res = publish(app, db_session, public=True)
        assert res["share_token"] == "tok-1"

    def test_publish_missing_blueprint_canvas(self, db_session):
        from core.mini_app_service import publish
        app, canvas_id, _ = _make_app(db_session, canvas_id=f"orphan-{uuid.uuid4().hex[:6]}")
        db_session.query(Canvas).filter(Canvas.id == canvas_id).delete()
        db_session.commit()
        with pytest.raises(ValueError, match="not found"):
            publish(app, db_session)

    def test_publish_audit_fallback_initial_state(self, db_session):
        from core.mini_app_service import publish
        app, canvas_id, _ = _make_app(db_session, canvas_id=f"ca-{uuid.uuid4().hex[:6]}")
        db_session.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).delete()
        db_session.add(CanvasAudit(
            canvas_id=canvas_id, tenant_id="t1", action_type="update",
            user_id="u1", canvas_type="mini_app",
            details_json={"content": {"audit_state": 1}},
        ))
        db_session.commit()
        publish(app, db_session)
        assert app.manifest["initial_state"] == {"audit_state": 1}


# ===========================================================================
# install — hydration + ownership
# ===========================================================================
class TestInstall:
    def _published_app(self, db_session, owner="u1"):
        app, canvas_id, _ = _make_app(
            db_session, scopes=["canvas_render"], owner=owner, status="draft",
        )
        app.status = "published"
        app.manifest = {
            **app.manifest,
            "initial_state": {"seed": 1},
            "blueprint": {
                "content": {"blocks": [{"id": "b1"}]},
                "style": {"bg": "#fff"},
                "logic_source": "result = dict(state)\nstate = result",
                "logic_language": "python",
                "component_installations": [
                    {"component_id": "c1", "config": {"api_key": "k", "keep": 1}, "position": 1, "z_index": 2},
                ],
            },
        }
        db_session.commit()
        return app

    def test_install_creates_fresh_instance(self, db_session):
        from core.mini_app_service import install
        app = self._published_app(db_session)
        new_id = install(app, _viewer("u2", "t2", None), db_session)
        canvas = db_session.query(Canvas).filter(Canvas.id == new_id).first()
        assert canvas.tenant_id == "t2" and canvas.created_by == "u2"
        assert canvas.mini_app_id == app.id
        assert canvas.share_token is None
        st = db_session.query(CanvasState).filter(CanvasState.canvas_id == new_id).first()
        assert st.state == {"seed": 1} and st.version == 1
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == new_id).first()
        assert logic.source == "result = dict(state)\nstate = result"
        insts = db_session.query(ComponentInstallation).filter(ComponentInstallation.canvas_id == new_id).all()
        assert insts[0].config == {"keep": 1}
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == new_id, CanvasAudit.action_type == "mini_app_install",
        ).all()
        assert len(audits) == 1
        inst_row = db_session.query(MiniAppInstallation).filter(MiniAppInstallation.canvas_id == new_id).first()
        assert inst_row.source == "marketplace" and inst_row.installed_version == app.version

    def test_install_not_published_raises(self, db_session):
        from core.mini_app_service import install
        app, _, _ = _make_app(db_session)
        with pytest.raises(ValueError, match="not published"):
            install(app, _viewer(), db_session)


# ===========================================================================
# run_stateful — error paths, gates, storage/record ops execution
# ===========================================================================
class TestRunStatefulErrors:
    @pytest.mark.asyncio
    async def test_missing_canvas(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        res = await run_stateful("does-not-exist")
        assert not res["success"] and "not found" in res["error"]

    @pytest.mark.asyncio
    async def test_not_mini_app_canvas(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        cid = f"c-{uuid.uuid4().hex[:12]}"
        db_session.add(Canvas(id=cid, tenant_id="t1", created_by="u1", name="x", canvas_type="plain", status="active"))
        db_session.commit()
        res = await run_stateful(cid)
        assert not res["success"] and "not a mini-app" in res["error"]

    @pytest.mark.asyncio
    async def test_missing_app(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        cid = f"c-{uuid.uuid4().hex[:12]}"
        db_session.add(Canvas(id=cid, tenant_id="t1", created_by="u1", name="x",
                              canvas_type="mini_app", status="active", mini_app_id="gone"))
        db_session.commit()
        res = await run_stateful(cid)
        assert not res["success"] and "not found" in res["error"]

    @pytest.mark.asyncio
    async def test_missing_logic(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session, with_logic=False)
        res = await run_stateful(canvas_id)
        assert not res["success"] and "No logic" in res["error"]

    @pytest.mark.asyncio
    async def test_runtime_error_fails_closed(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        import core.mini_app_service as svc
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        monkeypatch.setattr(svc, "get_miniapp_runtime", lambda: (_ for _ in ()).throw(RuntimeError("no firecracker")))
        res = await run_stateful(canvas_id)
        assert not res["success"] and "no firecracker" in res["error"]

    @pytest.mark.asyncio
    async def test_internal_error_generic_message(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        import core.mini_app_service as svc
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)

        class BoomRuntime:
            async def execute_python(self, *a, **kw):
                raise ValueError("boom")

        monkeypatch.setattr(svc, "get_miniapp_runtime", BoomRuntime)
        res = await run_stateful(canvas_id)
        assert not res["success"] and res["error"] == "Mini-app run failed"

    @pytest.mark.asyncio
    async def test_truncated_output_fails_loud(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        _fake_runtime(monkeypatch, metadata={}, truncated=True, stdout_extra="__MINIAPP_STATE__:{\"state\": ")
        res = await run_stateful(canvas_id)
        assert not res["success"] and "truncated" in res["error"]


class TestRunStatefulOps:
    @pytest.mark.asyncio
    async def test_storage_disabled_rejects_ops(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session, manifest_extra={
            "storage": {"enabled": False},
        })
        _fake_runtime(monkeypatch, envelope={"state": {"n": 1}, "storage_ops": [{"op": "put", "key": "k", "data": "x"}]})
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert res["success"]
        assert res["op_results"] == [{"op": "put", "key": "k", "ok": False, "error": "storage_disabled"}]

    @pytest.mark.asyncio
    async def test_invalid_storage_op_skipped(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        _fake_runtime(monkeypatch, envelope={"state": {"n": 1}, "storage_ops": [{"op": "rm -rf"}]})
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert res["success"] and res["op_results"] == []

    @pytest.mark.asyncio
    async def test_record_ops_db_disabled(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        monkeypatch.setenv("ATOM_MINIAPP_DB_ENABLED", "false")
        _fake_runtime(monkeypatch, envelope={"state": {"n": 1}, "record_ops": [{"op": "append", "series": "s", "data": {"a": 1}}]})
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert res["success"]
        assert res["record_results"] == [{"op": "append", "ok": False, "error": "db_disabled"}]

    @pytest.mark.asyncio
    async def test_record_ops_all_types(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        _record_op_db(db_session, canvas_id, app.id)
        ops = [
            {"op": "append", "series": "chart_data", "data": {"label": "new", "value": 9}},
            {"op": "get", "series": "chart_data", "id": "nope"},
            {"op": "query", "series": "chart_data", "filter": {"label": "v1"}},
            {"op": "count", "series": "chart_data", "filter": {"label": "v1"}},
            {"op": "update", "series": "chart_data", "id": "nope", "data": {"x": 1}},
            {"op": "update_many", "series": "chart_data", "filter": {"label": "v1"}, "data": {"done": True}},
            {"op": "delete", "series": "chart_data", "id": "nope"},
            {"op": "delete_series", "series": "chart_data"},
            {"op": "clear"},
            {"op": "list_series"},
            {"op": "bad_op"},
        ]
        _fake_runtime(monkeypatch, envelope={"state": {"n": 1}, "record_ops": ops})
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert res["success"]
        by_op = {r["op"]: r for r in res["record_results"]}
        assert by_op["append"]["ok"] is True and "seq" in by_op["append"]
        assert by_op["get"]["ok"] is False and by_op["get"]["error"] == "not_found"
        assert by_op["query"]["ok"] is True and by_op["query"]["count"] == 1
        assert by_op["count"]["count"] == 1
        assert by_op["update"]["ok"] is False and by_op["update"]["error"] == "not_found"
        assert by_op["update_many"]["updated"] == 1
        assert by_op["delete"]["ok"] is False
        assert by_op["delete_series"]["deleted"] >= 1
        assert by_op["clear"]["deleted"] >= 0
        assert isinstance(by_op["list_series"]["series"], list)
        assert "bad_op" not in by_op

    @pytest.mark.asyncio
    async def test_storage_ops_put_get_delete(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import run_stateful
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        ops = [
            {"op": "put", "key": "data.txt", "data": "hello"},
            {"op": "get", "key": "data.txt"},
            {"op": "get", "key": "missing.txt"},
            {"op": "delete", "key": "data.txt"},
            {"op": "put", "key": "keep.txt", "data": "x"},
            {"op": "put", "key": "keep.txt", "data": "y"},
        ]
        _fake_runtime(monkeypatch, envelope={"state": {"n": 1}, "storage_ops": ops})
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert res["success"]
        by_op = res["op_results"]
        assert by_op[0]["ok"] is True and by_op[0]["uri"]
        assert by_op[1]["ok"] is True and by_op[1]["encoding"] == "base64"
        assert by_op[2]["ok"] is False and by_op[2]["error"] == "not_found"
        assert by_op[3]["ok"] is True
        row = db_session.query(MiniAppAsset).filter(MiniAppAsset.canvas_id == canvas_id, MiniAppAsset.key == "keep.txt").first()
        assert row is not None and row.size == 1

    @pytest.mark.asyncio
    async def test_storage_op_failure_reported(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import run_stateful
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        _fake_runtime(monkeypatch, envelope={"state": {"n": 1}, "storage_ops": [{"op": "put", "key": "k", "data": "x"}]})
        import core.mini_app_service as svc

        class BadStorage:
            def store(self, *a, **kw):
                raise OSError("disk full")

        monkeypatch.setattr("core.mini_app_storage.get_mini_app_storage", lambda *a, **kw: BadStorage())
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert res["op_results"][0]["ok"] is False and res["op_results"][0]["error"] == "failed"

    @pytest.mark.asyncio
    async def test_new_state_row_created_when_missing(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        db_session.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).delete()
        db_session.commit()
        _fake_runtime(monkeypatch, envelope={"state": {"fresh": 1}, "storage_ops": []})
        res = await run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert res["success"] and res["version"] == 1
        row = db_session.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).first()
        assert row.state == {"fresh": 1}

    @pytest.mark.asyncio
    async def test_initial_state_override_dry_run(self, db_session, monkeypatch):
        from core.mini_app_service import run_stateful
        _patch_db(monkeypatch, db_session)
        app, canvas_id, _ = _make_app(db_session)
        _fake_runtime(monkeypatch, envelope={"state": {"n": 5}, "storage_ops": [], "record_ops": [{"op": "append", "series": "s", "data": {"a": 1}}]})
        res = await run_stateful(
            canvas_id, user_id="u1", scopes=("*",), persist=False,
            initial_state={"n": 5},
        )
        assert res["success"] and res["state"] == {"n": 5}
        assert res["proposed_ops"] == []
        assert res["proposed_record_ops"] and res["proposed_record_ops"][0]["proposed"] is True
        assert db_session.query(CanvasRecord).filter(CanvasRecord.canvas_id == canvas_id).count() == 0


# ===========================================================================
# Read bridge — assets, records, data sources, integrations
# ===========================================================================
class TestReadBridge:
    @pytest.mark.asyncio
    async def test_inject_assets_cap_missing_and_error(self, monkeypatch, tmp_path):
        from core.mini_app_service import _inject_assets
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        from core.mini_app_storage import get_mini_app_storage
        st = get_mini_app_storage("t1", "c1")
        st.store("small.txt", b"hello")
        st.store("big.bin", b"x" * 100)
        out = _inject_assets(
            {"storage": {"max_bytes_per_object": 10}, "assets": ["small.txt", "big.bin", "missing.txt"]},
            "t1", "c1",
        )
        assert out == {"small.txt": "hello"}

    @pytest.mark.asyncio
    async def test_inject_record_queries(self, db_session, monkeypatch):
        from core.mini_app_service import _inject_record_queries
        app, canvas_id, _ = _make_app(db_session)
        _record_op_db(db_session, canvas_id, app.id, n=3)
        out = _inject_record_queries(
            {"db": {"record_queries": ["chart_data", "nope_series"]}},
            db_session, canvas_id,
        )
        assert len(out["chart_data"]) == 3 and out["nope_series"] == []

    @pytest.mark.asyncio
    async def test_inject_data_sources(self, monkeypatch):
        from core.mini_app_service import _inject_data_sources
        from core import action_registry as ar

        class FakeRegistry:
            async def execute_action(self, name, args, context):
                return {"data": {"results": [{"id": 1}], "pad": "x" * 10}}

        monkeypatch.setattr(ar, "action_registry", FakeRegistry())
        out = await _inject_data_sources(
            {"data_sources": [{"type": "documents.search", "query": "q", "limit": 3}]},
            "t1", "w1", "a1",
        )
        assert out["documents"] == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_inject_data_sources_empty_and_failing(self, monkeypatch):
        from core.mini_app_service import _inject_data_sources

        class FailingRegistry:
            async def execute_action(self, name, args, context):
                raise RuntimeError("down")

        from core import action_registry as ar
        monkeypatch.setattr(ar, "action_registry", FailingRegistry())
        out = await _inject_data_sources(
            {"data_sources": [{"type": "documents.search", "query": "  "}, {"type": "documents.search", "query": "q"}]},
            "t1", "w1", "a1",
        )
        assert "documents" not in out

    @pytest.mark.asyncio
    async def test_inject_integration_sources(self, db_session, monkeypatch):
        from core.mini_app_service import _inject_integration_sources
        db_session.add(IntegrationToken(
            tenant_id="t1", provider="notion", access_token="tok", token_type="Bearer",
        ))
        db_session.commit()
        from core import external_integration_service as eis

        class FakeEIS:
            async def execute_integration_action(self, **kw):
                return SimpleNamespace(data={"pages": 1})

        monkeypatch.setattr(eis, "ExternalIntegrationService", FakeEIS)
        out = await _inject_integration_sources(
            {"integrations": [{"service": "notion", "action": "search", "params": {"q": 1}}]},
            "t1", "w1", "a1", db=db_session,
        )
        assert out == {"notion": {"pages": 1}}

    @pytest.mark.asyncio
    async def test_inject_integration_oversize_and_failure(self, monkeypatch):
        from core.mini_app_service import _inject_integration_sources
        from core import external_integration_service as eis
        from core.mini_app_service import _DEFAULT_DATA_SOURCE_CAP

        class BigEIS:
            async def execute_integration_action(self, **kw):
                return SimpleNamespace(data={"pad": "x" * (_DEFAULT_DATA_SOURCE_CAP + 1)})

        class BoomEIS:
            async def execute_integration_action(self, **kw):
                raise RuntimeError("down")

        monkeypatch.setattr(eis, "ExternalIntegrationService", BoomEIS)
        out = await _inject_integration_sources(
            {"mcp_servers": [{"service": "x", "action": "y"}]}, "t1", "w1", "a1",
        )
        assert out == {}
        monkeypatch.setattr(eis, "ExternalIntegrationService", BigEIS)
        out = await _inject_integration_sources(
            {"integrations": [{"service": "x", "action": "y"}]}, "t1", "w1", "a1",
        )
        assert out == {}

    @pytest.mark.asyncio
    async def test_safe_action_call(self, monkeypatch):
        from core.mini_app_service import _safe_action_call

        async def boom(*a, **k):
            raise RuntimeError("down")

        res = await _safe_action_call(SimpleNamespace(execute_action=boom), "x", {}, {})
        assert res == {}

        async def ok(*a, **k):
            return {"ok": 1}

        res = await _safe_action_call(SimpleNamespace(execute_action=ok), "x", {}, {})
        assert res == {"ok": 1}

    def test_json_bytes_unserializable(self):
        from core.mini_app_service import _DEFAULT_DATA_SOURCE_CAP, _json_bytes
        assert _json_bytes({"a": 1}) > 0
        assert _json_bytes(object()) == _DEFAULT_DATA_SOURCE_CAP + 1


# ===========================================================================
# Callback handler — fetch_integration scope gate
# ===========================================================================
class TestCallbackHandler:
    @pytest.mark.asyncio
    async def test_unknown_kind(self, db_session):
        from core.mini_app_service import _make_callback_handler
        h = _make_callback_handler(db_session, "t1", ("canvas_render",), "w1", "a1")
        res = await h({"kind": "nope"})
        assert not res["ok"] and "unknown callback" in res["error"]

    @pytest.mark.asyncio
    async def test_scope_denied(self, db_session, caplog):
        from core.mini_app_service import _make_callback_handler
        h = _make_callback_handler(db_session, "t1", ("canvas_render",), "w1", "a1")
        res = await h({"kind": "fetch_integration", "service": "notion", "action": "search"})
        assert res == {"ok": False, "error": "scope_denied"}

    @pytest.mark.asyncio
    async def test_allowed_ok_and_too_large(self, db_session, monkeypatch):
        from core.mini_app_service import _DEFAULT_DATA_SOURCE_CAP, _make_callback_handler
        from core import external_integration_service as eis

        class FakeEIS:
            async def execute_integration_action(self, **kw):
                return SimpleNamespace(data={"ok": 1})

        monkeypatch.setattr(eis, "ExternalIntegrationService", FakeEIS)
        h = _make_callback_handler(db_session, "t1", ("*",), "w1", "a1")
        res = await h({"kind": "fetch_integration", "service": "notion", "action": "search", "params": {}})
        assert res == {"ok": True, "data": {"ok": 1}}

        class BigEIS:
            async def execute_integration_action(self, **kw):
                return SimpleNamespace(data={"pad": "x" * (_DEFAULT_DATA_SOURCE_CAP + 1)})

        monkeypatch.setattr(eis, "ExternalIntegrationService", BigEIS)
        res = await h({"kind": "fetch_integration", "service": "notion", "action": "search"})
        assert res == {"ok": False, "error": "result_too_large"}

    @pytest.mark.asyncio
    async def test_failed(self, db_session, monkeypatch):
        from core.mini_app_service import _make_callback_handler
        from core import external_integration_service as eis

        class BoomEIS:
            async def execute_integration_action(self, **kw):
                raise RuntimeError("down")

        monkeypatch.setattr(eis, "ExternalIntegrationService", BoomEIS)
        h = _make_callback_handler(db_session, "t1", ("*",), "w1", "a1")
        res = await h({"kind": "fetch_integration", "service": "notion", "action": "search"})
        assert res == {"ok": False, "error": "failed"}


# ===========================================================================
# Broadcasts
# ===========================================================================
class TestBroadcasts:
    @pytest.mark.asyncio
    async def test_broadcast_db_and_state_errors_swallowed(self, monkeypatch):
        from core.mini_app_service import _broadcast_db, _broadcast_state
        from core import websockets

        class Boom:
            async def broadcast(self, *a, **k):
                raise RuntimeError("ws down")

        monkeypatch.setattr(websockets, "manager", Boom())
        await _broadcast_db("u1", "c1", [{"ok": True}])
        await _broadcast_state("u1", "c1", 1, {"a": 1})

    @pytest.mark.asyncio
    async def test_broadcast_db_success(self, monkeypatch):
        from core.mini_app_service import _broadcast_db
        from core import websockets
        seen = {}

        class FakeMgr:
            async def broadcast(self, stream, message):
                seen["m"] = message

        monkeypatch.setattr(websockets, "manager", FakeMgr())
        await _broadcast_db("u1", "c1", [{"ok": True}])
        assert seen["m"]["data"]["action"] == "mini_app_db"


# ===========================================================================
# Logic checkpoints + revert
# ===========================================================================
class TestLogicHistory:
    def test_snapshot_history_and_revert(self, db_session):
        from core.mini_app_service import (
            list_logic_history, record_logic_snapshot, revert_logic,
        )
        app, canvas_id, _ = _make_app(db_session)
        record_logic_snapshot(db_session, canvas_id, "t1", app.id, "source v1", actor_id="u1")
        record_logic_snapshot(db_session, canvas_id, "t1", app.id, "source v2", actor_id="u1")
        hist = list_logic_history(app, db_session)
        assert [h["version"] for h in hist] == [1, 2]
        assert hist[0]["preview"] == "source v1"
        res = revert_logic(app, db_session, 1, actor_id="u1")
        assert res["version"] == 1 and res["source"] == "source v1"
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).first()
        assert logic.source == "source v1"
        hist = list_logic_history(app, db_session)
        assert hist[-1]["version"] == 3  # revert is itself checkpointed

    def test_revert_missing_version_raises(self, db_session):
        from core.mini_app_service import revert_logic
        app, _, _ = _make_app(db_session)
        with pytest.raises(ValueError, match="not found"):
            revert_logic(app, db_session, 99)

    def test_list_logic_history_empty(self, db_session):
        from core.mini_app_service import list_logic_history
        app, _, _ = _make_app(db_session)
        assert list_logic_history(app, db_session) == []


# ===========================================================================
# run_tests harness
# ===========================================================================
class TestRunTests:
    @pytest.mark.asyncio
    async def test_run_tests_pass_fail_and_ops(self, db_session, monkeypatch):
        from core.mini_app_service import run_tests
        app, canvas_id, _ = _make_app(db_session)
        calls = {}

        async def fake_stateful(blueprint_canvas_id, *, inputs=None, user_id=None, persist=None,
                                viewer=None, viewer_tier=None, initial_state=None):
            calls["initial"] = initial_state
            if initial_state == {"fail": True}:
                return {"success": False, "error": "run failed", "stdout": "", "state": {}}
            return {
                "success": True, "stdout": "out", "state": {"n": (initial_state or {}).get("n", 0) + 1},
                "proposed_ops": [{"op": "put", "key": "k", "ok": True}],
            }

        import core.mini_app_service as svc
        monkeypatch.setattr(svc, "run_stateful", fake_stateful)
        res = await run_tests(app.id, canvas_id, [
            {"name": "ok", "initial_state": {"n": 1}, "expect_state": {"n": 2},
             "expect_ops": [{"op": "put", "key": "k"}]},
            {"name": "fail", "initial_state": {"fail": True}, "expect_state": {"n": 2}},
            {"name": "no-name", "initial_state": {}, "expect_ops": [{"op": "put", "key": "zzz"}]},
        ])
        assert res["total"] == 3 and res["passed"] == 1
        assert res["results"][0]["passed"] is True
        assert res["results"][1]["passed"] is False
        assert res["results"][2]["passed"] is False and res["results"][2]["ops_ok"] is False

    @pytest.mark.asyncio
    async def test_run_tests_case_raises(self, db_session, monkeypatch):
        from core.mini_app_service import run_tests
        app, canvas_id, _ = _make_app(db_session)
        import core.mini_app_service as svc

        async def boom(*a, **kw):
            raise RuntimeError("x")

        monkeypatch.setattr(svc, "run_stateful", boom)
        res = await run_tests(app.id, canvas_id, [{"name": "c", "initial_state": {}, "expect_state": {}}])
        assert res["results"][0]["passed"] is False and res["results"][0]["error"] == "test run raised"


# ===========================================================================
# status_probe
# ===========================================================================
class TestStatusProbe:
    def test_probe_full(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import status_probe
        app, canvas_id, _ = _make_app(db_session, deps=["numpy"])
        app.manifest = {
            **app.manifest,
            "tests": [{"name": "t", "expect_state": {}}],
            "db": {"enabled": True, "record_queries": ["chart_data"], "data_sources": [], "max_records_per_series": 10, "max_record_bytes": 100},
        }
        db_session.commit()
        rootfs = tmp_path / "rootfs"
        rootfs.mkdir()
        monkeypatch.setenv("MINIAPP_ROOTFS_DIR", str(rootfs))
        (rootfs / f"miniapp-{app.id}.ext4").write_bytes(b"x")
        monkeypatch.setattr(
            "core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
            lambda self, pkgs: {"safe": True, "vulnerabilities": [], "conflicts": []},
        )
        monkeypatch.setattr(
            "core.mini_app_service.get_miniapp_runtime",
            lambda: (_ for _ in ()).throw(RuntimeError("fc unavailable")),
        )
        probe = status_probe(app, db_session, viewer=_viewer())
        assert probe["logic"]["present"] and probe["logic"]["syntax_ok"]
        assert probe["scopes"]["declared"] == ["*"]
        assert probe["dependencies"]["count"] == 1 and probe["dependencies"]["scan_safe"]
        assert probe["rootfs"]["present"] is True
        assert probe["runtime"]["available"] is False
        assert probe["tests"]["count"] == 1
        assert probe["db"]["record_queries"] == ["chart_data"]

    def test_probe_bad_syntax_and_scan_error(self, db_session, monkeypatch):
        from core.mini_app_service import status_probe
        app, canvas_id, _ = _make_app(db_session, deps=["numpy"])
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).first()
        logic.source = "def broken(:"
        db_session.commit()
        monkeypatch.setattr(
            "core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
            lambda self, pkgs: (_ for _ in ()).throw(ValueError("no scanner")),
        )
        probe = status_probe(app, db_session)
        assert probe["logic"]["syntax_ok"] is False and probe["logic"]["syntax_error"]
        assert probe["dependencies"]["scan_safe"] is False


# ===========================================================================
# Routes
# ===========================================================================
@pytest.fixture()
def user_store():
    return {
        "user": SimpleNamespace(
            id="user-1", role="super_admin", tenant_id="t1", workspace_id=None,
            is_admin=False, is_staff=False,
        ),
    }


@pytest.fixture()
def client(db_session, user_store, monkeypatch):
    from core.auth import get_current_user
    from core.database import get_db
    from api.mini_app_routes import router

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db_session

    def override_user():
        return user_store["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as c:
        yield c


def _route_app(db, owner="user-1", status="draft", is_public=False, manifest_extra=None,
               canvas_id=None, app_id=None):
    app, canvas_id, _ = _make_app(
        db, name="route-app", owner=owner, status=status,
        scopes=["canvas_render"], manifest_extra=manifest_extra,
        canvas_id=canvas_id, app_id=app_id,
    )
    if is_public:
        app.is_public = True
        app.share_token = f"share-{uuid.uuid4().hex[:12]}"
        db.commit()
    return app, canvas_id


class TestRoutesCreateListGetUpdate:
    def test_create_invalid_manifest_400(self, client):
        res = client.post("/api/mini-apps", json={"name": "x", "manifest": {"declared_scopes": ["bogus"]}})
        assert res.status_code == 400

    def test_create_and_get(self, client, db_session):
        res = client.post("/api/mini-apps", json={
            "name": "x", "description": "d", "version": "2.0.0",
            "manifest": {"declared_scopes": ["*"]},
        })
        assert res.status_code == 200 and res.json()["success"]
        app_id = res.json()["app"]["id"]
        res = client.get(f"/api/mini-apps/{app_id}")
        assert res.status_code == 200 and res.json()["app"]["status"] == "draft"

    def test_get_missing_404(self, client):
        assert client.get("/api/mini-apps/nope").status_code == 404

    def test_list_search_and_scopes(self, client, db_session):
        app, _ = _route_app(db_session, manifest_extra={"integrations": [{"service": "notion", "action": "search"}]})
        res = client.get("/api/mini-apps", params={"q": "route-app"})
        assert res.status_code == 200
        assert res.json()["apps"][0]["id"] == app.id
        assert res.json()["apps"][0]["integrations_count"] == 1
        assert res.json()["apps"][0]["is_approved"] is False

    def test_update_owner_only_and_deps_reset_image(self, client, db_session, user_store):
        app, _ = _route_app(db_session)
        app.runtime_image = "/x/y.ext4"
        db_session.commit()
        res = client.put(f"/api/mini-apps/{app.id}", json={
            "name": "renamed",
            "manifest": {"declared_scopes": ["*"], "dependencies": ["numpy"]},
        })
        assert res.status_code == 200
        assert app.name == "renamed"
        assert app.runtime_image is None
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        res = client.put(f"/api/mini-apps/{app.id}", json={"name": "x"})
        assert res.status_code == 403

    def test_update_invalid_manifest_400(self, client, db_session):
        app, _ = _route_app(db_session)
        res = client.put(f"/api/mini-apps/{app.id}", json={"manifest": {"declared_scopes": ["bogus"]}})
        assert res.status_code == 400

    def test_scaffold_route(self, client):
        res = client.post("/api/mini-apps/scaffold", json={"name": "scaff"})
        assert res.status_code == 200
        body = res.json()
        assert body["success"] and body["canvas_id"] and body["manifest"]["declared_scopes"]


class TestRoutesPublishShareApproveInstall:
    def test_publish_route_owner_only_and_errors(self, client, db_session, user_store):
        app, _ = _route_app(db_session)
        res = client.post(f"/api/mini-apps/{app.id}/publish", params={"public": "true"})
        assert res.status_code == 200 and res.json()["success"]
        assert app.status == "published" and app.share_token
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        app2, _ = _route_app(db_session)
        assert client.post(f"/api/mini-apps/{app2.id}/publish").status_code == 403

    def test_publish_runtime_error_500_and_value_500(self, client, db_session, monkeypatch):
        app, _ = _route_app(db_session)
        monkeypatch.setattr("core.mini_app_service.prepare_runtime", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no fc")))
        assert client.post(f"/api/mini-apps/{app.id}/publish").status_code == 500

    def test_share_toggle(self, client, db_session, user_store):
        app, _ = _route_app(db_session)
        res = client.post(f"/api/mini-apps/{app.id}/share", params={"public": "true"})
        assert res.status_code == 200 and app.share_token
        res = client.post(f"/api/mini-apps/{app.id}/share", params={"public": "false"})
        assert res.status_code == 200 and app.share_token is None
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        app2, _ = _route_app(db_session)
        assert client.post(f"/api/mini-apps/{app2.id}/share").status_code == 403

    def test_approve_admin_gate(self, client, db_session, user_store):
        app, _ = _route_app(db_session)
        assert client.post(f"/api/mini-apps/{app.id}/approve").status_code == 403
        user_store["user"] = SimpleNamespace(id="admin", tenant_id="t1", is_admin=True, is_staff=True)
        res = client.post(f"/api/mini-apps/{app.id}/approve")
        assert res.status_code == 200 and app.is_approved is True

    def test_install_owner_and_pending_review(self, client, db_session, user_store, monkeypatch):
        monkeypatch.setattr("core.mini_app_service.install", lambda app, viewer, db: "new-canvas-1")
        app, _ = _route_app(db_session)
        res = client.post(f"/api/mini-apps/{app.id}/install")
        assert res.status_code == 200 and res.json()["canvas_id"] == "new-canvas-1"
        app.is_public, app.is_approved = True, False
        db_session.commit()
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        res = client.post(f"/api/mini-apps/{app.id}/install")
        assert res.status_code == 403 and "pending review" in res.json()["detail"]
        app.is_approved = True
        db_session.commit()
        assert client.post(f"/api/mini-apps/{app.id}/install").status_code == 200

    def test_install_private_forbidden(self, client, db_session, user_store):
        app, _ = _route_app(db_session)
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        res = client.post(f"/api/mini-apps/{app.id}/install")
        assert res.status_code == 403

    def test_by_token_install(self, client, db_session, user_store, monkeypatch):
        monkeypatch.setattr("core.mini_app_service.install", lambda app, viewer, db: "tok-canvas-1")
        assert client.post("/api/mini-apps/by-token/nope/install").status_code == 404
        app, _ = _route_app(db_session, is_public=True)
        res = client.post(f"/api/mini-apps/by-token/{app.share_token}/install")
        assert res.status_code == 403  # not approved
        app.is_approved = True
        db_session.commit()
        res = client.post(f"/api/mini-apps/by-token/{app.share_token}/install")
        assert res.status_code == 200 and res.json()["canvas_id"] == "tok-canvas-1"

    def test_update_check(self, client, db_session, user_store):
        app, canvas_id = _route_app(db_session, status="published")
        # no installation record
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/update-check")
        assert res.json()["update_available"] is False
        db_session.add(MiniAppInstallation(
            app_id=app.id, canvas_id=canvas_id, tenant_id="t1", installed_by="user-1",
            installed_version=app.version, installed_runtime_version=0, source="owned",
        ))
        db_session.commit()
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/update-check")
        assert res.json()["update_available"] is False
        app.version = "2.0.0"
        db_session.commit()
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/update-check")
        assert res.json()["update_available"] is True
        # app deleted → app_deleted
        app2, canvas2 = _route_app(db_session)
        db_session.add(MiniAppInstallation(
            app_id=app2.id, canvas_id=canvas2, tenant_id="t1", installed_by="user-1",
            installed_version="1.0.0", installed_runtime_version=0, source="owned",
        ))
        db_session.delete(app2)
        db_session.commit()
        res = client.get(f"/api/mini-apps/instances/{canvas2}/update-check")
        assert res.json()["reason"] == "app_deleted"


class TestRoutesAssets:
    def test_asset_upload_list_download_delete(self, client, db_session, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        app, canvas_id = _route_app(db_session)
        res = client.post(
            f"/api/mini-apps/instances/{canvas_id}/assets",
            data={"key": "data.txt"}, files={"file": ("data.txt", b"hello", "text/plain")},
        )
        assert res.status_code == 200 and res.json()["uri"]
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/assets")
        assert res.json()["assets"][0]["key"] == "data.txt"
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/assets/data.txt")
        assert res.status_code == 200 and res.content == b"hello"
        assert client.get(f"/api/mini-apps/instances/{canvas_id}/assets/missing").status_code == 404
        res = client.delete(f"/api/mini-apps/instances/{canvas_id}/assets/data.txt")
        assert res.status_code == 200 and res.json()["deleted"] is True
        assert db_session.query(MiniAppAsset).filter(MiniAppAsset.canvas_id == canvas_id).count() == 0

    def test_asset_upload_oversize_413_and_bad_key(self, client, db_session, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        app, canvas_id = _route_app(db_session)
        res = client.post(
            f"/api/mini-apps/instances/{canvas_id}/assets",
            data={"key": "ok.txt"}, files={"file": ("ok.txt", b"x" * (50 * 1024 * 1024 + 1), "text/plain")},
        )
        assert res.status_code == 413
        res = client.post(
            f"/api/mini-apps/instances/{canvas_id}/assets",
            data={"key": "../evil.txt"}, files={"file": ("evil.txt", b"x", "text/plain")},
        )
        assert res.status_code == 400

    def test_asset_upload_overwrites_existing(self, client, db_session, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        app, canvas_id = _route_app(db_session)
        db_session.add(MiniAppAsset(
            canvas_id=canvas_id, tenant_id="t1", key="k.txt", uri="old", size=1, created_by="user-1",
        ))
        db_session.commit()
        res = client.post(
            f"/api/mini-apps/instances/{canvas_id}/assets",
            data={"key": "k.txt"}, files={"file": ("k.txt", b"new-data", "text/plain")},
        )
        assert res.status_code == 200
        row = db_session.query(MiniAppAsset).filter(MiniAppAsset.canvas_id == canvas_id, MiniAppAsset.key == "k.txt").first()
        assert row.size == 8 and row.uri != "old"

    def test_asset_non_instance_canvas_404(self, client, db_session, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        cid = f"plain-{uuid.uuid4().hex[:6]}"
        db_session.add(Canvas(id=cid, tenant_id="t1", created_by="user-1", name="p", canvas_type="plain", status="active"))
        db_session.commit()
        res = client.post(
            f"/api/mini-apps/instances/{cid}/assets",
            data={"key": "k"}, files={"file": ("k", b"x", "text/plain")},
        )
        assert res.status_code == 404

    def test_asset_delete_non_owner_403(self, client, db_session, user_store, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        app, canvas_id = _route_app(db_session)
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        assert client.delete(f"/api/mini-apps/instances/{canvas_id}/assets/k").status_code == 403


class TestRoutesAssetUploadAuthz:
    """BUG (HIGH): a non-owner could upload/overwrite assets on another user's
    instance canvas whenever the app was public — a write-what-where on the
    owner's instance namespace (every other mutation is owner-gated)."""

    def test_non_owner_cannot_upload_to_public_instance(self, client, db_session, user_store, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        app, canvas_id = _route_app(db_session, is_public=True)
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        res = client.post(
            f"/api/mini-apps/instances/{canvas_id}/assets",
            data={"key": "pwn.txt"}, files={"file": ("pwn.txt", b"evil", "text/plain")},
        )
        assert res.status_code == 403
        assert db_session.query(MiniAppAsset).filter(MiniAppAsset.canvas_id == canvas_id).count() == 0

    def test_non_owner_cannot_overwrite_existing_asset(self, client, db_session, user_store, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        app, canvas_id = _route_app(db_session, is_public=True)
        db_session.add(MiniAppAsset(
            canvas_id=canvas_id, tenant_id="t1", key="k.txt", uri="orig", size=3, created_by="user-1",
        ))
        db_session.commit()
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        res = client.post(
            f"/api/mini-apps/instances/{canvas_id}/assets",
            data={"key": "k.txt"}, files={"file": ("k.txt", b"pwned", "text/plain")},
        )
        assert res.status_code == 403
        row = db_session.query(MiniAppAsset).filter(MiniAppAsset.canvas_id == canvas_id, MiniAppAsset.key == "k.txt").first()
        assert row.size == 3 and row.uri == "orig"

    def test_owner_can_still_upload_to_public_instance(self, client, db_session, tmp_path, monkeypatch):
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path / "store"))
        app, canvas_id = _route_app(db_session, is_public=True)
        res = client.post(
            f"/api/mini-apps/instances/{canvas_id}/assets",
            data={"key": "mine.txt"}, files={"file": ("mine.txt", b"ok", "text/plain")},
        )
        assert res.status_code == 200


class TestRoutesRecords:
    def test_record_append_query_count_get_update_delete(self, client, db_session, user_store):
        app, canvas_id = _route_app(db_session, manifest_extra={
            "db": {"enabled": True, "max_records_per_series": 10, "max_record_bytes": 102400, "record_queries": []},
        })
        res = client.post(f"/api/mini-apps/instances/{canvas_id}/records", json={"series": "s1", "data": {"a": 1}})
        assert res.status_code == 200
        rid = res.json()["record"]["id"]
        res = client.post(f"/api/mini-apps/instances/{canvas_id}/records/query", json={"series": "s1", "filter": {"a": 1}, "limit": 5, "order": "desc"})
        assert res.json()["count"] == 1
        assert client.post(f"/api/mini-apps/instances/{canvas_id}/records/query", json={"series": "s1", "order": "bad"}).status_code == 400
        assert client.post(f"/api/mini-apps/instances/{canvas_id}/records/query", json={"series": "s1", "filter": {"a": []}}).status_code == 400
        res = client.post(f"/api/mini-apps/instances/{canvas_id}/records/count", json={"series": "s1", "filter": {"a": 1}})
        assert res.json()["count"] == 1
        assert client.post(f"/api/mini-apps/instances/{canvas_id}/records/count", json={"series": "BAD!"}).status_code == 400
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", params={"series": "s1"})
        assert res.json()["record"]["data"] == {"a": 1}
        assert client.get(f"/api/mini-apps/instances/{canvas_id}/records/nope", params={"series": "s1"}).status_code == 404
        assert client.get(f"/api/mini-apps/instances/{canvas_id}/records", params={"series": "s1", "order": "bad"}).status_code == 400
        assert client.get(f"/api/mini-apps/instances/{canvas_id}/records", params={"series": "BAD!"}).status_code == 400
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/records", params={"series": "s1"})
        assert res.json()["count"] == 1
        res = client.get(f"/api/mini-apps/instances/{canvas_id}/records/series")
        assert res.json()["series"] == [{"series": "s1", "count": 1}]
        res = client.put(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", json={"series": "s1", "data": {"b": 2}})
        assert res.status_code == 200 and res.json()["record"]["data"] == {"a": 1, "b": 2}
        assert client.put(f"/api/mini-apps/instances/{canvas_id}/records/nope", json={"series": "s1", "data": {"b": 2}}).status_code == 404
        assert client.put(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", json={"series": "s1", "data": {"pad": "x" * 200000}}).status_code == 400
        res = client.delete(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", params={"series": "s1"})
        assert res.status_code == 200 and res.json()["deleted"] is True
        assert client.delete(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", params={"series": "s1"}).status_code == 404
        res = client.delete(f"/api/mini-apps/instances/{canvas_id}/records", params={"series": "s1"})
        assert res.status_code == 200 and res.json()["deleted"] == 0
        assert client.delete(f"/api/mini-apps/instances/{canvas_id}/records", params={"series": "BAD!"}).status_code == 400

    def test_record_mutations_owner_only(self, client, db_session, user_store):
        app, canvas_id = _route_app(db_session)
        db_session.add(CanvasRecord(
            id=str(uuid.uuid4()), canvas_id=canvas_id, tenant_id="t1", app_id=app.id,
            series="s1", seq=1, data={"a": 1}, created_by="user-1",
        ))
        db_session.commit()
        user_store["user"] = SimpleNamespace(id="user-2", tenant_id="t1", is_admin=False, is_staff=False)
        assert client.post(f"/api/mini-apps/instances/{canvas_id}/records", json={"series": "s1", "data": {"a": 1}}).status_code == 403
        rid = db_session.query(CanvasRecord).filter(CanvasRecord.canvas_id == canvas_id).first().id
        assert client.put(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", json={"series": "s1", "data": {"a": 2}}).status_code == 403
        assert client.delete(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", params={"series": "s1"}).status_code == 403

    def test_append_respects_manifest_db_enabled(self, client, db_session):
        app, canvas_id = _route_app(db_session, manifest_extra={"db": {"enabled": False}})
        res = client.post(f"/api/mini-apps/instances/{canvas_id}/records", json={"series": "s1", "data": {"a": 1}})
        assert res.status_code == 503 and res.json()["detail"] == "db_disabled"

    def test_append_bad_data_and_series(self, client, db_session):
        app, canvas_id = _route_app(db_session)
        assert client.post(f"/api/mini-apps/instances/{canvas_id}/records", json={"series": "BAD!", "data": {}}).status_code == 400
        assert client.post(f"/api/mini-apps/instances/{canvas_id}/records", json={"series": "s1", "data": {"pad": "x" * 200000}}).status_code == 400


class TestRoutesRecordsManifestGate:
    """BUG (MED): update/delete/delete-series record routes ignored the
    manifest's db.enabled=false gate (append + the record_ops envelope both
    fail-closed with 503 db_disabled)."""

    def _instance(self, db_session):
        return _route_app(db_session, manifest_extra={"db": {"enabled": False}})

    def test_update_record_503_when_manifest_db_disabled(self, client, db_session):
        app, canvas_id = self._instance(db_session)
        rid = "r-1"
        db_session.add(CanvasRecord(
            id=rid, canvas_id=canvas_id, tenant_id="t1", app_id=app.id,
            series="s1", seq=1, data={"a": 1}, created_by="user-1",
        ))
        db_session.commit()
        res = client.put(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", json={"series": "s1", "data": {"a": 2}})
        assert res.status_code == 503 and res.json()["detail"] == "db_disabled"

    def test_delete_record_503_when_manifest_db_disabled(self, client, db_session):
        app, canvas_id = self._instance(db_session)
        rid = "r-2"
        db_session.add(CanvasRecord(
            id=rid, canvas_id=canvas_id, tenant_id="t1", app_id=app.id,
            series="s1", seq=1, data={"a": 1}, created_by="user-1",
        ))
        db_session.commit()
        res = client.delete(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", params={"series": "s1"})
        assert res.status_code == 503 and res.json()["detail"] == "db_disabled"

    def test_delete_series_503_when_manifest_db_disabled(self, client, db_session):
        app, canvas_id = self._instance(db_session)
        res = client.delete(f"/api/mini-apps/instances/{canvas_id}/records", params={"series": "s1"})
        assert res.status_code == 503 and res.json()["detail"] == "db_disabled"

    def test_enabled_manifest_still_allows_update_delete(self, client, db_session):
        app, canvas_id = _route_app(db_session, manifest_extra={
            "db": {"enabled": True, "max_records_per_series": 10, "max_record_bytes": 102400, "record_queries": []},
        })
        rid = "r-3"
        db_session.add(CanvasRecord(
            id=rid, canvas_id=canvas_id, tenant_id="t1", app_id=app.id,
            series="s1", seq=1, data={"a": 1}, created_by="user-1",
        ))
        db_session.commit()
        assert client.put(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", json={"series": "s1", "data": {"a": 2}}).status_code == 200
        assert client.delete(f"/api/mini-apps/instances/{canvas_id}/records/{rid}", params={"series": "s1"}).status_code == 200
