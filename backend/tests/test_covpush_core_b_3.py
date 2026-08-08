"""
Coverage-push tests — core modules wave B (part 3): mini_app_service.

Targets the untested 30% of core/mini_app_service.py: manifest validation
branches, runtime preparation, scaffold/publish/install, the stateful run
envelope processing, storage/record op execution matrices, acceptance-test
harness, and the constraint probe. All DB via db_session; Firecracker,
storage backends, and broadcasts mocked.
"""
import asyncio
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import (
    AgentRegistry, Canvas, CanvasAudit, CanvasLogic, CanvasState, MiniApp,
    MiniAppAsset, ComponentInstallation,
)


def _make_app(db, name="covapp", manifest_extra=None, user="u1", status="draft",
              canvas_content=None, with_state=True, state=None):
    canvas_id = f"c-{uuid.uuid4().hex[:12]}"
    app_id = f"app-{uuid.uuid4().hex[:12]}"
    manifest = {
        "declared_scopes": ["canvas_render", "canvas_get_state"],
        "skills": [], "mcp_servers": [], "entrypoint": "logic",
        "dependencies": [], "base_image": "python:3.11-slim", "assets": [],
        "storage": {"enabled": True, "backend": "local",
                    "max_bytes_per_object": 1024 * 1024},
        "db": {"enabled": True, "max_records_per_series": 100,
               "max_record_bytes": 4096, "record_queries": []},
        "data_sources": [], "integrations": [],
        "initial_state": {"seed": 1}, "blueprint": {
            "content": canvas_content or {"blocks": []}, "style": {},
            "logic_source": "state = state",
            "logic_language": "python",
            "component_installations": [
                {"component_id": "comp1", "config": {"api_key": "SECRET"},
                 "position": 1, "z_index": 2},
            ],
        },
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    db.add(Canvas(
        id=canvas_id, tenant_id="t1", workspace_id="w1", created_by=user,
        name=name, canvas_type="mini_app", content={"blocks": []}, style={},
        is_collaborative=True, status="active", mini_app_id=app_id,
    ))
    db.add(CanvasLogic(canvas_id=canvas_id, language="python",
                       source="state = state", created_by=user))
    db.add(MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by=user, name=name,
        manifest=manifest, blueprint_canvas_id=canvas_id, status=status,
        is_public=False, runtime_version=0,
    ))
    if with_state:
        db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1",
                           state=state if state is not None else {"seed": 1},
                           version=1))
    db.commit()
    return app_id, canvas_id


def _make_runtime(monkeypatch, envelope=None, truncated=False, side_effect=None):
    class FakeRuntime:
        async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                                 image=None, callback_handler=None, **kwargs):
            if side_effect is not None:
                raise side_effect
            return SimpleNamespace(
                success=True, stdout="", stderr="", exit_code=0,
                truncated=truncated,
                metadata={"state_envelope": envelope},
            )
    monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime",
                        lambda: FakeRuntime())


# ============================================================================
# validate_manifest — remaining branches
# ============================================================================


class TestValidateManifestBranches:
    def _base(self, **over):
        m = {
            "declared_scopes": ["canvas_render"],
            "dependencies": [], "base_image": "python:3.11-slim",
            "storage": {}, "db": {}, "data_sources": [], "integrations": [],
            "assets": [],
        }
        m.update(over)
        return m

    def test_scopes_not_list(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(declared_scopes="*"))

    def test_unknown_scope(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(declared_scopes=["nope_scope"]))

    def test_wildcard_scope_allowed(self):
        from core.mini_app_service import validate_manifest
        validate_manifest(self._base(declared_scopes=["*"]))

    def test_deps_not_string_list(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(dependencies=["pandas", 42]))

    def test_base_image_not_allowlisted(self, monkeypatch):
        from core.mini_app_service import validate_manifest
        monkeypatch.setenv("MINIAPP_BASE_IMAGE_ALLOWLIST", "python:3.11-slim")
        with pytest.raises(ValueError):
            validate_manifest(self._base(base_image="ubuntu:24.04"))

    def test_storage_backend_invalid(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(storage={"backend": "nope"}))

    def test_storage_max_bytes_invalid(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(storage={"max_bytes_per_object": -5}))

    def test_db_enabled_not_bool(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(db={"enabled": "yes"}))

    def test_db_max_records_invalid(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(db={"max_records_per_series": 0}))

    def test_db_max_record_bytes_invalid(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(db={"max_record_bytes": "big"}))

    def test_record_queries_invalid_series(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(db={"record_queries": ["has spaces"]}))

    def test_data_sources_invalid(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(data_sources=["not-an-object"]))
        with pytest.raises(ValueError):
            validate_manifest(self._base(data_sources=[{"type": "sql.query"}]))

    def test_integrations_invalid(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(integrations=[{"service": "notion"}]))
        with pytest.raises(ValueError):
            validate_manifest(self._base(integrations=[{"service": "", "action": "x"}]))
        with pytest.raises(ValueError):
            validate_manifest(self._base(integrations=[{"service": "n", "action": "a",
                                                        "params": "bad"}]))
        with pytest.raises(ValueError):
            validate_manifest(self._base(integrations=["not-an-object"]))

    def test_mcp_servers_alias_warns(self, caplog):
        import logging
        from core.mini_app_service import validate_manifest

        manifest = self._base(mcp_servers=[{"service": "s", "action": "a"}])
        manifest.pop("integrations")
        with caplog.at_level(logging.WARNING):
            validate_manifest(manifest)
        assert "deprecated" in caplog.text

    def test_assets_not_strings(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(assets=["ok", 5]))

    def test_tests_delegates_to_validate_tests(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest(self._base(tests=["not-a-case"]))


# ============================================================================
# validate_tests
# ============================================================================


class TestValidateTests:
    def test_validation_matrix(self):
        from core.mini_app_service import validate_tests
        with pytest.raises(ValueError):
            validate_tests("nope")
        with pytest.raises(ValueError):
            validate_tests([5])
        with pytest.raises(ValueError):
            validate_tests([{"initial_state": "bad"}])
        with pytest.raises(ValueError):
            validate_tests([{"expect_ops": {"op": "x"}}])
        with pytest.raises(ValueError):
            validate_tests([{"name": 5, "expect_state": {}}])
        with pytest.raises(ValueError):
            validate_tests([{}])  # neither expect_state nor expect_ops
        validate_tests([{"name": "ok", "expect_state": {"a": 1}, "expect_ops": []}])


# ============================================================================
# prepare_runtime
# ============================================================================


class TestPrepareRuntime:
    def test_no_deps_clears_image(self, db_session):
        from core.mini_app_service import prepare_runtime
        app_id, canvas_id = _make_app(db_session, manifest_extra={"dependencies": []})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        app.runtime_image = "stale"
        prepare_runtime(app, db_session)
        assert app.runtime_image is None

    def test_unsafe_scan_raises(self, db_session):
        from core.mini_app_service import prepare_runtime
        app_id, _ = _make_app(db_session, manifest_extra={"dependencies": ["pkg"]})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        with patch("core.package_dependency_scanner.PackageDependencyScanner") as scanner:
            scanner.return_value.scan_packages.return_value = {
                "safe": False, "vulnerabilities": [{"id": "CVE-1"}], "conflicts": []}
            with pytest.raises(ValueError):
                prepare_runtime(app, db_session)

    def test_rootfs_missing_raises(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import prepare_runtime
        app_id, _ = _make_app(db_session, manifest_extra={"dependencies": ["pkg"]})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        monkeypatch.setattr("core.mini_app_service.get_miniapp_rootfs_dir",
                            lambda: str(tmp_path))
        with patch("core.package_dependency_scanner.PackageDependencyScanner") as scanner:
            scanner.return_value.scan_packages.return_value = {"safe": True}
            with pytest.raises(RuntimeError):
                prepare_runtime(app, db_session)

    def test_rootfs_present_bumps_version(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import prepare_runtime
        app_id, _ = _make_app(db_session, manifest_extra={"dependencies": ["pkg"]})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        (tmp_path / f"miniapp-{app_id}.ext4").write_bytes(b"x")
        monkeypatch.setattr("core.mini_app_service.get_miniapp_rootfs_dir",
                            lambda: str(tmp_path))
        with patch("core.package_dependency_scanner.PackageDependencyScanner") as scanner:
            scanner.return_value.scan_packages.return_value = {"safe": True}
            assert prepare_runtime(app, db_session) == str(tmp_path / f"miniapp-{app_id}.ext4")
            assert app.runtime_version == 1
            # second call: unchanged
            assert prepare_runtime(app, db_session) == str(tmp_path / f"miniapp-{app_id}.ext4")
            assert app.runtime_version == 1


# ============================================================================
# resolve_effective_scopes + syntax_check + scaffold helpers
# ============================================================================


class TestScopesAndSyntax:
    def test_resolve_effective_scopes(self):
        from core.mini_app_service import resolve_effective_scopes

        from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS

        assert resolve_effective_scopes({"declared_scopes": ["*"]}, tier="autonomous") == ("*",)
        assert resolve_effective_scopes({"declared_scopes": ["*"]}) == TIER_FLOOR_TOOL_WHITELISTS["student"]
        assert resolve_effective_scopes(
            {"declared_scopes": ["canvas_render"]}, tier="student") == ("canvas_render",)
        viewer = SimpleNamespace(tier="autonomous")
        assert resolve_effective_scopes({"declared_scopes": ["*"]}, viewer=viewer) == ("*",)
        assert resolve_effective_scopes({"declared_scopes": []}, tier="autonomous") == ("*",)

    def test_syntax_check(self):
        from core.mini_app_service import syntax_check
        with pytest.raises(SyntaxError):
            syntax_check("")
        with pytest.raises(SyntaxError):
            syntax_check("   ")
        with pytest.raises(SyntaxError):
            syntax_check("def broken(:")
        syntax_check("x = 1")

    def test_llm_scaffold_flag_used(self, monkeypatch, db_session):
        monkeypatch.setenv("ATOM_MINIAAP_LLM_SCAFFOLD", "true")
        from core.mini_app_service import scaffold, _llm_scaffold
        with patch("core.mini_app_service._llm_scaffold",
                   return_value="state = {'llm': True}") as llm:
            viewer = SimpleNamespace(id="v1", tenant_id="t1", workspace_id="w1")
            app, canvas_id = scaffold({"description": "d"}, "MyApp", ["canvas_render"], [],
                                      viewer, db_session)
            llm.assert_called_once()
            assert app.name == "MyApp"
            assert isinstance(canvas_id, str) and canvas_id

    def test_run_async_error_and_result(self):
        from core.mini_app_service import _run_async

        async def ok():
            return 42
        assert _run_async(ok()) == 42

        async def boom():
            raise ValueError("nope")
        with pytest.raises(ValueError):
            _run_async(boom())

    def test_llm_scaffold_failure_and_success(self, monkeypatch):
        from core.mini_app_service import _llm_scaffold

        # LLM returns invalid code -> fallback None.
        class FakeSvc:
            async def generate_completion(self, msgs):
                return {"content": "def broken(:"}
        with patch("core.llm_service.LLMService", lambda: FakeSvc()):
            assert _llm_scaffold("n", {}) is None
        # LLM raises -> fallback None.
        class RaisingSvc:
            async def generate_completion(self, msgs):
                raise RuntimeError("llm down")
        with patch("core.llm_service.LLMService", lambda: RaisingSvc()):
            assert _llm_scaffold("n", {}) is None
        # LLM returns valid code -> used.
        class GoodSvc:
            async def generate_completion(self, msgs):
                return {"content": "state = {'ok': 1}"}
        with patch("core.llm_service.LLMService", lambda: GoodSvc()):
            assert _llm_scaffold("n", {}) == "state = {'ok': 1}"


# ============================================================================
# publish + install
# ============================================================================


class TestPublishInstall:
    def test_publish_canvas_missing(self, db_session):
        from core.mini_app_service import publish
        app_id, _ = _make_app(db_session)
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        app.blueprint_canvas_id = "missing-canvas"
        with patch("core.mini_app_service.prepare_runtime", lambda a, db: None):
            with pytest.raises(ValueError):
                publish(app, db_session)

    def test_publish_uses_audit_fallback_and_public(self, db_session):
        from core.mini_app_service import publish
        app_id, canvas_id = _make_app(db_session, with_state=False)
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        db_session.add(CanvasAudit(
            canvas_id=canvas_id, tenant_id="t1", action_type="edit",
            user_id="u1", canvas_type="mini_app",
            details_json={"content": {"blocks": [{"t": "x"}]}},
        ))
        db_session.commit()
        with patch("core.mini_app_service.prepare_runtime", lambda a, db: None):
            result = publish(app, db_session, public=True)
        assert result["success"] is True
        assert result["is_public"] is True
        assert result["share_token"]
        assert app.status == "published"
        # initial_state from the audit fallback.
        assert app.manifest["initial_state"] == {"blocks": [{"t": "x"}]}

    def test_publish_strips_credentials_from_manifest(self, db_session):
        from core.mini_app_service import publish
        app_id, _ = _make_app(db_session, state={"api_key": "LEAKED", "ok": 1})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        with patch("core.mini_app_service.prepare_runtime", lambda a, db: None):
            publish(app, db_session)
        assert app.manifest["initial_state"].get("api_key") is None
        assert app.manifest["initial_state"]["ok"] == 1

    def test_install_requires_published(self, db_session):
        from core.mini_app_service import install
        app_id, _ = _make_app(db_session, status="draft")
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        with pytest.raises(ValueError):
            install(app, SimpleNamespace(id="u2", tenant_id="t2", workspace_id="w2"),
                    db_session)

    def test_install_hydrates_instance(self, db_session):
        from core.mini_app_service import install
        app_id, canvas_id = _make_app(db_session, status="published")
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        viewer = SimpleNamespace(id="u2", tenant_id="t2", workspace_id="w2")
        new_id = install(app, viewer, db_session)
        instance = db_session.query(Canvas).filter(Canvas.id == new_id).first()
        assert instance.tenant_id == "t2"  # installer's tenant, not author's
        assert instance.workspace_id == "w2"
        assert instance.mini_app_id == app_id
        # Controller copied.
        logic = db_session.query(CanvasLogic).filter(
            CanvasLogic.canvas_id == new_id).first()
        assert logic.source == "state = state"
        # Component configs credential-stripped.
        inst = db_session.query(ComponentInstallation).filter(
            ComponentInstallation.canvas_id == new_id).first()
        assert inst.config.get("api_key") is None
        # State + exactly one audit row.
        st = db_session.query(CanvasState).filter(CanvasState.canvas_id == new_id).first()
        assert st.version == 1
        audits = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == new_id).all()
        assert len(audits) == 1
        assert audits[0].action_type == "mini_app_install"

    def test_install_author_workspace_fallback(self, db_session):
        from core.mini_app_service import install
        app_id, _ = _make_app(db_session, status="published")
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        # Author installs from another workspace-less context -> author ws.
        viewer = SimpleNamespace(id="u1", tenant_id=None, workspace_id=None)
        new_id = install(app, viewer, db_session)
        instance = db_session.query(Canvas).filter(Canvas.id == new_id).first()
        assert instance.tenant_id == app.tenant_id
        assert instance.workspace_id == "w1"


# ============================================================================
# Envelope parsing + storage op validation + injectors
# ============================================================================


class TestEnvelopeAndOps:
    def test_wrap_source_and_parse_envelope(self):
        from core.mini_app_service import _wrap_source, _parse_envelope

        wrapped = _wrap_source("x = 1")
        assert "try:" in wrapped
        assert "__MINIAPP_STATE__:" in wrapped
        assert _parse_envelope(None) is None
        assert _parse_envelope("") is None
        assert _parse_envelope("no marker here") is None
        assert _parse_envelope("__MINIAPP_STATE__:{bad json") is None
        parsed = _parse_envelope('pre\n__MINIAPP_STATE__:{"state": {"a": 1}, "storage_ops": []}\ntail')
        assert parsed == {"state": {"a": 1}, "storage_ops": []}

    def test_validate_storage_op_matrix(self):
        from core.mini_app_service import _validate_storage_op

        assert _validate_storage_op("nope", 10) is None
        assert _validate_storage_op({"op": "explode"}, 10) is None
        assert _validate_storage_op({"op": "put", "key": ""}, 10) is None
        assert _validate_storage_op({"op": "put", "key": "k" * 501, "data": "x"}, 10) is None
        assert _validate_storage_op({"op": "put", "key": "k", "data": None}, 10) is None
        assert _validate_storage_op({"op": "put", "key": "k", "data": "x", "encoding": "base64"}, 10) is None
        assert _validate_storage_op({"op": "put", "key": "k", "data": "eA==", "encoding": "base64", "content_type": "t"}, 10) == {
            "op": "put", "key": "k", "data": b"x", "content_type": "t"}
        assert _validate_storage_op({"op": "put", "key": "k", "data": "x"}, 10)["data"] == b"x"
        assert _validate_storage_op({"op": "put", "key": "k", "data": b"x"}, 0) is None  # too big
        assert _validate_storage_op({"op": "put", "key": "k", "data": 5}, 10) is None
        assert _validate_storage_op({"op": "get", "key": "k"}, 10) == {"op": "get", "key": "k"}
        assert _validate_storage_op({"op": "delete", "key": "k"}, 10) == {"op": "delete", "key": "k"}

    def test_inject_assets(self, db_session, monkeypatch):
        from core.mini_app_service import _inject_assets

        class Storage:
            def retrieve(self, key):
                if key == "missing":
                    return None
                if key == "big":
                    return b"x" * 2000
                return b"hello"

        monkeypatch.setattr("core.mini_app_storage.get_mini_app_storage",
                            lambda t, c: Storage())
        out = _inject_assets(
            {"assets": ["missing", "big", "ok"], "storage": {"max_bytes_per_object": 1000}},
            "t1", "c1")
        assert out == {"ok": "hello"}

    def test_inject_assets_exception_skipped(self, db_session, monkeypatch, caplog):
        from core.mini_app_service import _inject_assets

        class BadStorage:
            def retrieve(self, key):
                raise RuntimeError("backend down")

        monkeypatch.setattr("core.mini_app_storage.get_mini_app_storage",
                            lambda t, c: BadStorage())
        out = _inject_assets({"assets": ["a"], "storage": {}}, "t1", "c1")
        assert out == {}

    def test_inject_record_queries_skip_on_error(self, db_session, monkeypatch):
        from core.mini_app_service import _inject_record_queries
        with patch("core.mini_app_db_service.query_records",
                   side_effect=RuntimeError("db down")):
            out = _inject_record_queries(
                {"db": {"record_queries": ["series_a"]}}, db_session, "c1")
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_data_sources(self, monkeypatch):
        from core.mini_app_service import _inject_data_sources

        with patch("core.mini_app_service._safe_action_call", new=AsyncMock(return_value={
                "data": {"results": [{"id": "d1"}]}})) as sac:
            out = await _inject_data_sources(
                {"data_sources": [{"type": "documents.search", "query": "  "}]},
                "t1", "w1", "a1")
            assert out == {}  # blank query skipped
            sac.assert_not_awaited()

        with patch("core.mini_app_service._safe_action_call", new=AsyncMock(return_value={
                "data": {"results": [{"id": "d1"}]}})) as sac:
            out = await _inject_data_sources(
                {"data_sources": [{"type": "documents.search", "query": "q", "limit": 2}]},
                "t1", "w1", "a1")
            assert out == {"documents": [{"id": "d1"}]}
            sac.assert_awaited_once()

        with patch("core.mini_app_service._safe_action_call", new=AsyncMock(return_value={
                "data": {"results": "x" * 6000000}})):
            out = await _inject_data_sources(
                {"data_sources": [{"type": "documents.search", "query": "q"}]},
                "t1", "w1", "a1")
            assert out == {}  # oversize skipped

    @pytest.mark.asyncio
    async def test_inject_integration_sources(self, monkeypatch):
        from core.mini_app_service import _inject_integration_sources

        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": [1, 2, 3]})) as dispatch:
            out = await _inject_integration_sources(
                {"integrations": [{"service": "s", "action": "a"}]}, "t1", "w1", "a1")
            assert out == {"s": [1, 2, 3]}
            dispatch.assert_awaited_once_with("s", "a", {}, tenant_id="t1", db=None)

        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": False, "data": None})):
            out = await _inject_integration_sources(
                {"integrations": [{"service": "s", "action": "a"}]}, "t1", "w1", "a1")
            assert out == {}

        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": [0] * 3000000})):
            out = await _inject_integration_sources(
                {"integrations": [{"service": "s", "action": "a"}]}, "t1", "w1", "a1")
            assert out == {}  # oversize skipped

        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(side_effect=RuntimeError("x"))):
            out = await _inject_integration_sources(
                {"integrations": [{"service": "s", "action": "a"}]}, "t1", "w1", "a1")
            assert out == {}

        out = await _inject_integration_sources(
            {"integrations": [{"service": "", "action": ""}]}, "t1", "w1", "a1")
        assert out == {}

    def test_json_bytes_errors(self):
        from core.mini_app_service import _json_bytes, _DEFAULT_DATA_SOURCE_CAP
        assert _json_bytes({"a": [1, 2]}) > 0
        assert _json_bytes(object()) == _DEFAULT_DATA_SOURCE_CAP + 1

    @pytest.mark.asyncio
    async def test_safe_action_call_timeout(self):
        from core.mini_app_service import _safe_action_call

        class SlowRegistry:
            async def execute_action(self, *a, **k):
                await asyncio_sleep(2)

        import asyncio as _a
        async def asyncio_sleep(n):
            await _a.sleep(n)

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            assert await _safe_action_call(SlowRegistry(), "x", {}, {}) == {}

        with patch("asyncio.wait_for", side_effect=RuntimeError("boom")):
            assert await _safe_action_call(SlowRegistry(), "x", {}, {}) == {}

    def test_resolve_integration_credentials(self, db_session, monkeypatch):
        from core.mini_app_service import _resolve_integration_credentials
        from core.models import IntegrationToken
        from datetime import datetime, timezone

        db_session.add(IntegrationToken(
            tenant_id="t1", provider="notion", access_token="enc-token",
            token_type="Bearer", updated_at=datetime.now(timezone.utc)))
        db_session.commit()
        with patch("core.privsec.token_encryption.decrypt_token",
                   side_effect=lambda v: f"dec:{v}"):
            creds = _resolve_integration_credentials("t1", "notion", db_session)
        assert creds["access_token"] == "dec:enc-token"
        assert creds["token_type"] == "Bearer"
        # No row -> {}.
        assert _resolve_integration_credentials("t1", "ghost", db_session) == {}
        # DB None -> get_db_session path.
        with patch("core.database.get_db_session") as m:
            cm = MagicMock()
            cm.__enter__.return_value = db_session
            cm.__exit__.return_value = False
            m.return_value = cm
            with patch("core.privsec.token_encryption.decrypt_token",
                       side_effect=lambda v: f"dec:{v}"):
                assert _resolve_integration_credentials("t1", "notion", None)["access_token"].startswith("dec:")
        # Exception -> {}.
        with patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            assert _resolve_integration_credentials("t1", "notion", None) == {}

    @pytest.mark.asyncio
    async def test_callback_handler_gate(self):
        from core.mini_app_service import _make_callback_handler

        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("mcp", "server1"))):
            with patch("core.mini_app_integration_dispatch.dispatch",
                       new=AsyncMock(return_value={"ok": True, "data": {"x": 1}})) as dispatch:
                h = _make_callback_handler(db=None, tenant_id="t1", scopes=("mcp.server1",),
                                           workspace_id=None, agent_id="a1")
                res = await h({"kind": "fetch_integration", "service": "s", "action": "a"})
                assert res["ok"] is True
                dispatch.assert_awaited_once()
                # unknown kind
                assert (await h({"kind": "other"}))["ok"] is False

        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("native", None))):
            h = _make_callback_handler(db=None, tenant_id="t1", scopes=("canvas_render",),
                                       workspace_id=None, agent_id="a1")
            res = await h({"kind": "fetch_integration", "service": "slack", "action": "send"})
            assert res["error"] == "scope_denied"
            # '*' scopes allow everything.
            h2 = _make_callback_handler(db=None, tenant_id="t1", scopes=("*",),
                                        workspace_id=None, agent_id="a1")
            with patch("core.mini_app_integration_dispatch.dispatch",
                       new=AsyncMock(return_value={"ok": True, "data": {"z": 1}})):
                assert (await h2({"kind": "fetch_integration", "service": "x", "action": "y"}))["ok"] is True
            # result too large
            with patch("core.mini_app_integration_dispatch.dispatch",
                       new=AsyncMock(return_value={"ok": True, "data": {"big": "z" * 6000000}})):
                assert (await h2({"kind": "fetch_integration", "service": "x", "action": "y"}))["error"] == "result_too_large"
            # dispatch raises
            with patch("core.mini_app_integration_dispatch.dispatch",
                       new=AsyncMock(side_effect=RuntimeError("x"))):
                assert (await h2({"kind": "fetch_integration", "service": "x", "action": "y"}))["error"] == "failed"


# ============================================================================
# run_stateful — remaining paths
# ============================================================================


class TestRunStatefulPaths:
    @pytest.mark.asyncio
    async def test_canvas_not_found_and_not_miniapp(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_stateful

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)

        res = await run_stateful("ghost-canvas")
        assert "not found" in res["error"]
        db_session.add(Canvas(
            id="plain-canvas", tenant_id="t1", created_by="u1", name="p",
            canvas_type="canvas", content={}, style={}, status="active",
        ))
        db_session.commit()
        res = await run_stateful("plain-canvas")
        assert "not a mini-app" in res["error"]

    @pytest.mark.asyncio
    async def test_app_missing_and_no_logic(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_stateful

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)
        db_session.add(Canvas(
            id="orphan", tenant_id="t1", created_by="u1", name="o",
            canvas_type="mini_app", content={}, style={}, status="active",
            mini_app_id="ghost-app",
        ))
        db_session.commit()
        res = await run_stateful("orphan")
        assert "not found" in res["error"]

        app_id, canvas_id = _make_app(db_session)
        db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).delete()
        db_session.commit()
        _make_runtime(monkeypatch, envelope=None)
        res = await run_stateful(canvas_id)
        assert "No logic" in res["error"]

    @pytest.mark.asyncio
    async def test_truncated_stdout_fails_loudly(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_stateful, _MINIAPP_STATE_MARKER

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)
        app_id, canvas_id = _make_app(db_session)

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                                     image=None, callback_handler=None, **kwargs):
                return SimpleNamespace(
                    success=True, stdout=f"partial {_MINIAPP_STATE_MARKER}cut", stderr="",
                    exit_code=0, truncated=True, metadata={})
        monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime",
                            lambda: FakeRuntime())
        res = await run_stateful(canvas_id)
        assert res["success"] is False
        assert "truncated" in res["error"]

    @pytest.mark.asyncio
    async def test_storage_disabled_rejects_ops(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_stateful

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)
        app_id, canvas_id = _make_app(db_session, manifest_extra={
            "storage": {"enabled": False}})
        envelope = {"state": {"n": 2}, "storage_ops": [{"op": "put", "key": "k", "data": "x"}],
                    "record_ops": []}
        _make_runtime(monkeypatch, envelope=envelope)
        monkeypatch.setattr("core.mini_app_storage.get_mini_app_storage",
                            lambda t, c: MagicMock())
        monkeypatch.setattr("core.mini_app_service._broadcast_state", AsyncMock())
        res = await run_stateful(canvas_id, user_id="u1")
        assert res["op_results"][0]["error"] == "storage_disabled"
        assert res["success"] is True

    @pytest.mark.asyncio
    async def test_dry_run_proposes_ops(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_stateful

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)
        app_id, canvas_id = _make_app(db_session)
        envelope = {"state": {"n": 3},
                    "storage_ops": [{"op": "put", "key": "k", "data": "x"}],
                    "record_ops": [{"op": "append", "series": "rows", "data": {"v": 1}}]}
        _make_runtime(monkeypatch, envelope=envelope)
        monkeypatch.setattr("core.mini_app_storage.get_mini_app_storage",
                            lambda t, c: MagicMock())
        res = await run_stateful(canvas_id, user_id="u1", persist=False)
        assert res["proposed_ops"][0]["proposed"] is True
        assert res["proposed_record_ops"][0]["proposed"] is True
        assert res["success"] is True

    @pytest.mark.asyncio
    async def test_state_row_created_when_missing(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_stateful

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)
        app_id, canvas_id = _make_app(db_session, with_state=False)
        envelope = {"state": {"fresh": 1}, "storage_ops": [], "record_ops": []}
        _make_runtime(monkeypatch, envelope=envelope)
        monkeypatch.setattr("core.mini_app_service._broadcast_state", AsyncMock())
        res = await run_stateful(canvas_id, user_id="u1")
        assert res["success"] is True
        row = db_session.query(CanvasState).filter(
            CanvasState.canvas_id == canvas_id).first()
        assert row is not None
        assert row.version == 1
        assert row.created_by == "u1"

    @pytest.mark.asyncio
    async def test_initial_state_override_and_no_broadcast(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_stateful

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)
        app_id, canvas_id = _make_app(db_session, state={"old": 1})
        envelope = {"state": {"override": 1}, "storage_ops": [], "record_ops": []}
        _make_runtime(monkeypatch, envelope=envelope)
        res = await run_stateful(canvas_id, user_id=None, persist=True,
                                 initial_state={"custom": 9})
        assert res["state"] == {"override": 1}
        assert res["success"] is True


# ============================================================================
# _execute_storage_op + _validate_record_op + _execute_record_op
# ============================================================================


class _FakeStorage:
    def __init__(self):
        self.data = {"exists": b"payload"}

    def store(self, key, data, content_type=None):
        self.data[key] = data
        return f"uri://{key}"

    def retrieve(self, key):
        return self.data.get(key)

    def delete(self, key):
        if key in self.data:
            del self.data[key]
            return True
        return False


class TestStorageRecordOps:
    def _ctx(self, db_session):
        app_id, canvas_id = _make_app(db_session)
        canvas = db_session.query(Canvas).filter(Canvas.id == canvas_id).first()
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        return canvas, app

    def test_execute_storage_op_matrix(self, db_session):
        from core.mini_app_service import _execute_storage_op

        canvas, app = self._ctx(db_session)
        storage = _FakeStorage()
        assert _execute_storage_op(
            {"op": "put", "key": "k1", "data": b"v1", "content_type": "text/plain"},
            storage, db_session, canvas, app)["ok"] is True
        row = db_session.query(MiniAppAsset).filter(
            MiniAppAsset.canvas_id == canvas.id, MiniAppAsset.key == "k1").first()
        assert row.uri == "uri://k1"
        # put again -> update path
        _execute_storage_op({"op": "put", "key": "k1", "data": b"v2"},
                            storage, db_session, canvas, app)
        assert db_session.query(MiniAppAsset).filter(
            MiniAppAsset.canvas_id == canvas.id, MiniAppAsset.key == "k1").count() == 1
        # get missing
        assert _execute_storage_op({"op": "get", "key": "nope"}, storage,
                                   db_session, canvas, app)["error"] == "not_found"
        # get existing
        got = _execute_storage_op({"op": "get", "key": "k1"}, storage,
                                  db_session, canvas, app)
        assert got["ok"] is True and got["encoding"] == "base64"
        # delete existing + missing
        assert _execute_storage_op({"op": "delete", "key": "k1"}, storage,
                                   db_session, canvas, app)["ok"] is True
        assert _execute_storage_op({"op": "delete", "key": "k1"}, storage,
                                   db_session, canvas, app)["ok"] is False
        # unknown op
        assert _execute_storage_op({"op": "zzz", "key": "k"}, storage,
                                   db_session, canvas, app)["error"] == "unknown_op"
        # storage failure -> failed
        class Boom:
            def store(self, *a, **k):
                raise OSError("disk full")
        assert _execute_storage_op({"op": "put", "key": "x", "data": b"y"}, Boom(),
                                   db_session, canvas, app)["error"] == "failed"

    def test_validate_record_op_matrix(self):
        from core.mini_app_service import _validate_record_op

        assert _validate_record_op("x", 100) is None
        assert _validate_record_op({"op": "bogus", "series": "s"}, 100) is None
        assert _validate_record_op({"op": "append", "series": "BAD SERIES", "data": {"a": 1}}, 100) is None
        assert _validate_record_op({"op": "append", "series": "s", "data": {"a": 1}, "id": 5}, 100) is None
        assert _validate_record_op({"op": "append", "series": "s", "data": "not-dict"}, 100) is None
        assert _validate_record_op({"op": "append", "series": "s", "data": {"a": 1}, "id": "r1"}, 100)["id"] == "r1"
        assert _validate_record_op({"op": "get", "series": "s"}, 100) is None
        assert _validate_record_op({"op": "get", "series": "s", "id": "r1"}, 100)["op"] == "get"
        assert _validate_record_op({"op": "update", "series": "s", "id": "r1", "data": {"a": 1}}, 100)["op"] == "update"
        assert _validate_record_op({"op": "delete", "series": "s", "id": "r1"}, 100)["op"] == "delete"
        assert _validate_record_op({"op": "query", "series": "s", "filter": {"a": 1}}, 100)["op"] == "query"
        assert _validate_record_op({"op": "query", "series": "s", "limit": 0}, 100) is None
        assert _validate_record_op({"op": "query", "series": "s", "order": "sideways"}, 100) is None
        assert _validate_record_op({"op": "query", "series": "s", "filter": {"a": [1]}}, 100) is None
        assert _validate_record_op({"op": "count", "series": "s", "filter": {}}, 100)["op"] == "count"
        assert _validate_record_op({"op": "update_many", "series": "s", "data": {"a": 1}}, 100)["op"] == "update_many"
        assert _validate_record_op({"op": "update_many", "series": "s", "filter": {"a": 1}, "data": {"a": 2}}, 100)["op"] == "update_many"
        assert _validate_record_op({"op": "clear"}, 100)["op"] == "clear"
        assert _validate_record_op({"op": "list_series"}, 100)["op"] == "list_series"
        assert _validate_record_op({"op": "delete_series", "series": "s"}, 100)["op"] == "delete_series"

    def test_execute_record_op_matrix(self, db_session):
        from core.mini_app_service import _execute_record_op, _validate_record_op

        canvas, app = self._ctx(db_session)
        valid = lambda op: _validate_record_op(op, 4096)

        r = _execute_record_op(valid({"op": "append", "series": "rows", "data": {"v": 1}}),
                               db_session, canvas, app, created_by="u2")
        assert r["ok"] is True and r["seq"] == 1
        # get found + not found
        g = _execute_record_op(valid({"op": "get", "series": "rows", "id": r["id"]}),
                               db_session, canvas, app, created_by="u2")
        assert g["ok"] is True
        g2 = _execute_record_op(valid({"op": "get", "series": "rows", "id": "ghost"}),
                                db_session, canvas, app, created_by="u2")
        assert g2["ok"] is False
        # query + count
        q = _execute_record_op(valid({"op": "query", "series": "rows"}), db_session,
                               canvas, app, created_by="u2")
        assert q["count"] == 1
        c = _execute_record_op(valid({"op": "count", "series": "rows"}), db_session,
                               canvas, app, created_by="u2")
        assert c["count"] == 1
        # update found + missing
        u = _execute_record_op(valid({"op": "update", "series": "rows", "id": r["id"], "data": {"v": 9}}),
                               db_session, canvas, app, created_by="u2")
        assert u["ok"] is True
        u2 = _execute_record_op(valid({"op": "update", "series": "rows", "id": "ghost", "data": {"v": 9}}),
                                db_session, canvas, app, created_by="u2")
        assert u2["ok"] is False
        # update_many
        um = _execute_record_op(valid({"op": "update_many", "series": "rows", "filter": {"v": 9}, "data": {"v": 10}}),
                                db_session, canvas, app, created_by="u2")
        assert um["ok"] is True and um["updated"] == 1
        # delete
        d = _execute_record_op(valid({"op": "delete", "series": "rows", "id": r["id"]}),
                               db_session, canvas, app, created_by="u2")
        assert d["ok"] is True
        d2 = _execute_record_op(valid({"op": "delete", "series": "rows", "id": r["id"]}),
                                db_session, canvas, app, created_by="u2")
        assert d2["ok"] is False
        # append again then delete_series + list_series + clear
        r2 = _execute_record_op(valid({"op": "append", "series": "rows", "data": {"v": 1}}),
                                db_session, canvas, app, created_by="u2")
        ls = _execute_record_op(valid({"op": "list_series"}), db_session, canvas, app, created_by="u2")
        assert "rows" in [s["series"] for s in ls["series"]]
        ds = _execute_record_op(valid({"op": "delete_series", "series": "rows"}),
                                db_session, canvas, app, created_by="u2")
        assert ds["deleted"] == 1
        r3 = _execute_record_op(valid({"op": "append", "series": "rows2", "data": {"v": 1}}),
                                db_session, canvas, app, created_by="u2")
        cl = _execute_record_op(valid({"op": "clear"}), db_session, canvas, app, created_by="u2")
        assert cl["deleted"] == 1
        # unknown op + exception
        unk = _execute_record_op({"op": "zzz", "series": "rows"}, db_session, canvas, app, created_by="u2")
        assert unk["ok"] is False
        with patch("core.mini_app_db_service.append_record",
                   side_effect=RuntimeError("boom")):
            failed = _execute_record_op(valid({"op": "append", "series": "rows", "data": {"v": 1}}),
                                        db_session, canvas, app, created_by="u2")
        assert failed["ok"] is False


# ============================================================================
# Broadcast helpers + logic checkpoints + run_tests + status_probe
# ============================================================================


class TestHarness:
    @pytest.mark.asyncio
    async def test_broadcasts(self, monkeypatch):
        from core.mini_app_service import _broadcast_state, _broadcast_db

        with patch("core.websockets.manager.broadcast", new=AsyncMock()) as b:
            await _broadcast_state("u1", "c1", 2, {"a": 1})
            b.assert_awaited_once()
        with patch("core.websockets.manager.broadcast", new=AsyncMock()):
            await _broadcast_db("u1", "c1", [{"op": "append"}])
        with patch("core.websockets.manager.broadcast",
                   new=AsyncMock(side_effect=RuntimeError("ws down"))):
            await _broadcast_state("u1", "c1", 2, {})  # no raise
            await _broadcast_db("u1", "c1", [])  # no raise

    def test_logic_checkpoints(self, db_session):
        from core.mini_app_service import (
            record_logic_snapshot, list_logic_history, revert_logic,
        )

        app_id, canvas_id = _make_app(db_session)
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        v1 = record_logic_snapshot(db_session, canvas_id, "t1", app_id, "state = 1", "u1")
        v2 = record_logic_snapshot(db_session, canvas_id, "t1", app_id, "state = 2", "u1")
        assert v2["version"] == v1["version"] + 1
        history = list_logic_history(app, db_session)
        assert len(history) == 2
        assert history[0]["preview"] == "state = 1"
        reverted = revert_logic(app, db_session, v1["version"], actor_id="u1")
        assert reverted["reverted_to"] == v1["version"]
        assert reverted["success"] is True
        # Revert to a nonexistent version raises.
        with pytest.raises(ValueError):
            revert_logic(app, db_session, 999, actor_id="u1")

    @pytest.mark.asyncio
    async def test_run_tests_grading(self, db_session, monkeypatch):
        import contextlib
        from core.mini_app_service import run_tests
        app_id, canvas_id = _make_app(db_session, state={"runs": 0})

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                                     image=None, callback_handler=None, **kwargs):
                state = inputs.get("state") or {}
                state = dict(state)
                state["runs"] = state.get("runs", 0) + 1
                return SimpleNamespace(
                    success=True, stdout="", stderr="", exit_code=0,
                    metadata={"state_envelope": {"state": state, "storage_ops": [
                        {"op": "put", "key": "k", "data": "x"}]}},
                )
        monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime",
                            lambda: FakeRuntime())
        monkeypatch.setattr("core.mini_app_storage.get_mini_app_storage",
                            lambda t, c: _FakeStorage())

        real_run_stateful = __import__("core.mini_app_service", fromlist=["run_stateful"]).run_stateful

        async def run_stateful_flaky(*args, **kwargs):
            if kwargs.get("inputs"):
                raise RuntimeError("flaky harness")
            return await real_run_stateful(*args, **kwargs)

        with patch("core.mini_app_service.run_stateful", new=run_stateful_flaky):
            result = await run_tests(app_id, canvas_id, [
                {"name": "pass", "initial_state": {"runs": 0},
                 "expect_state": {"runs": 1}, "expect_ops": [{"op": "put", "key": "k"}]},
                {"name": "fail", "initial_state": {"runs": 0},
                 "expect_state": {"runs": 99}},
                {"name": "raise", "initial_state": {"runs": 0},
                 "expect_state": {"runs": 1}, "inputs": {"boom": 1}},
            ])
        assert result["total"] == 3
        assert result["passed"] == 1
        by_name = {r["name"]: r for r in result["results"]}
        assert by_name["pass"]["passed"] is True
        assert by_name["fail"]["passed"] is False
        assert by_name["fail"]["diff"]["runs"]["expected"] == 99

    @pytest.mark.asyncio
    async def test_run_tests_run_failure(self, db_session, monkeypatch):
        from core.mini_app_service import run_tests
        app_id, canvas_id = _make_app(db_session)

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                                     image=None, callback_handler=None, **kwargs):
                raise RuntimeError("vm crashed")
        monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime",
                            lambda: FakeRuntime())

        result = await run_tests(app_id, canvas_id, [
            {"name": "x", "expect_state": {"a": 1}}])
        assert result["results"][0]["passed"] is False
        assert result["results"][0]["error"]

    def test_status_probe(self, db_session, monkeypatch, tmp_path):
        from core.mini_app_service import status_probe
        app_id, canvas_id = _make_app(db_session, manifest_extra={"dependencies": ["pkg"]})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        monkeypatch.setattr("core.mini_app_runtime.get_miniapp_rootfs_dir",
                            lambda: str(tmp_path))
        (tmp_path / f"miniapp-{app_id}.ext4").write_bytes(b"x")
        with patch("core.package_dependency_scanner.PackageDependencyScanner") as scanner:
            scanner.return_value.scan_packages.return_value = {"safe": True}
            with patch("core.mini_app_runtime.get_miniapp_runtime",
                       side_effect=RuntimeError("not provisioned")):
                probe = status_probe(app, db_session)
        assert probe["logic"]["syntax_ok"] is True
        assert probe["dependencies"]["scan_safe"] is True
        assert probe["rootfs"]["present"] is True
        assert probe["runtime"]["available"] is False
        assert probe["tests"]["count"] == 0

    def test_status_probe_syntax_error_and_scan_failure(self, db_session, monkeypatch):
        from core.mini_app_service import status_probe
        app_id, canvas_id = _make_app(
            db_session, manifest_extra={"dependencies": ["pkg"], "tests": [{"expect_state": {}}]})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        row = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == canvas_id).first()
        row.source = "def broken(:"
        db_session.commit()
        with patch("core.package_dependency_scanner.PackageDependencyScanner",
                   side_effect=RuntimeError("scanner down")):
            with patch("core.mini_app_runtime.get_miniapp_runtime", return_value=object()):
                probe = status_probe(app, db_session)
        assert probe["logic"]["syntax_ok"] is False
        assert probe["logic"]["syntax_error"]
        assert probe["dependencies"]["scan"] == {"safe": False, "error": "scan failed"}
        assert probe["tests"]["count"] == 1
        assert probe["db"]["enabled"] is True


# ============================================================================
# Final top-up tests (combined-coverage gaps)
# ============================================================================


class TestFinalTopUps:
    def test_known_scope_names_registry_failure(self, monkeypatch):
        from core import mini_app_service as m

        monkeypatch.setattr(
            "core.action_registry.action_registry.list_actions",
            lambda: (_ for _ in ()).throw(RuntimeError("registry down")))
        assert m._known_scope_names() == m._RAW_TOOL_SCOPES

    def test_validate_manifest_data_sources_valid_entry(self):
        from core.mini_app_service import validate_manifest

        validate_manifest({
            "declared_scopes": ["*"],
            "dependencies": [], "base_image": "python:3.11-slim",
            "storage": {}, "db": {},
            "data_sources": [{"type": "documents.search", "query": "q", "limit": 5}],
            "integrations": [], "assets": [],
        })

    def test_install_miniapp_installation_write_failure(self, db_session):
        from core.mini_app_service import install

        app_id, _ = _make_app(db_session, status="published")
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        with patch("core.models.MiniAppInstallation",
                   side_effect=RuntimeError("table missing")):
            new_id = install(app, SimpleNamespace(id="u9", tenant_id="t1", workspace_id=None),
                             db_session)
        assert new_id  # install still succeeds

    def test_status_probe_mcp_servers_fallback(self, db_session, monkeypatch):
        from core.mini_app_service import status_probe

        manifest_extra = {"integrations": None, "mcp_servers": [
            {"service": "s", "action": "a"}]}
        app_id, _ = _make_app(db_session, manifest_extra=manifest_extra)
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        with patch("core.mini_app_runtime.get_miniapp_runtime", return_value=object()):
            probe = status_probe(app, db_session)
        assert probe["db"]["integrations"] == manifest_extra["mcp_servers"]


class TestFinalTopUps2:
    def test_data_sources_not_a_list(self):
        from core.mini_app_service import validate_manifest

        with pytest.raises(ValueError):
            validate_manifest({
                "declared_scopes": ["*"], "dependencies": [],
                "base_image": "python:3.11-slim", "storage": {}, "db": {},
                "data_sources": "not-a-list", "integrations": [], "assets": [],
            })

    def test_update_many_invalid_filter_rejected(self):
        from core.mini_app_service import _validate_record_op

        assert _validate_record_op(
            {"op": "update_many", "series": "s", "filter": {"a": [1]},
             "data": {"a": 2}}, 100) is None

    def test_status_probe_runtime_generic_failure(self, db_session):
        from core.mini_app_service import status_probe

        app_id, _ = _make_app(db_session)
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        with patch("core.mini_app_runtime.get_miniapp_runtime",
                   side_effect=ValueError("weird")):
            probe = status_probe(app, db_session)
        assert probe["runtime"]["available"] is False
        assert probe["runtime"]["reason"] == "runtime init failed"
