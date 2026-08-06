"""Mini-app storage_ops bug fixes — kill switch, cap parity, lossless get.

Regression tests for three asset-storage fixes:
  1. storage_ops now respects manifest.storage.enabled (storage_disabled).
  2. storage_ops per-object cap defaults to the REST upload cap (50 MiB), not
     the old 5 MiB injection cap — an asset written via the API must round-trip.
  3. storage_ops.get returns base64 so binary assets aren't corrupted by the
     old utf-8(errors="replace") decode.

FC execution is mocked; the host-side run_stateful executor is under test.
"""
import base64
import contextlib
import json
import uuid

import pytest

from core.models import Canvas, CanvasLogic, CanvasState, MiniApp


def _make_app(db, storage_cfg=None):
    canvas_id = f"c-{uuid.uuid4().hex[:10]}"
    app_id = f"app-{uuid.uuid4().hex[:10]}"
    manifest = {
        "declared_scopes": ["*"],
        "skills": [], "mcp_servers": [], "entrypoint": "logic",
        "dependencies": [], "base_image": "python:3.11-slim", "assets": [],
        "storage": storage_cfg or {"enabled": True, "backend": "local",
                                    "max_bytes_per_object": 5 * 1024 * 1024},
        "initial_state": {}, "blueprint": {},
    }
    db.add(MiniApp(id=app_id, tenant_id="t1", workspace_id="w1", created_by="u1",
                   name="t", manifest=manifest, blueprint_canvas_id=canvas_id, status="draft"))
    db.add(Canvas(id=canvas_id, tenant_id="t1", created_by="u1", name="inst",
                  canvas_type="mini_app", content={}, style={}, status="active",
                  mini_app_id=app_id))
    db.add(CanvasLogic(canvas_id=canvas_id, language="python", source="state = state", created_by="u1"))
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={}, version=1))
    db.commit()
    return app_id, canvas_id


def _patch_db(monkeypatch, db_session):
    @contextlib.contextmanager
    def _cm():
        yield db_session
    monkeypatch.setattr("core.database.get_db_session", _cm)


def _fake_runtime(monkeypatch, storage_ops, state_out=None):
    import core.mini_app_service as svc

    class FakeRuntime:
        async def execute_python(self, code, *, policy=None, inputs=None, cwd=None, image=None, callback_handler=None, **kwargs):
            return type("R", (), {
                "success": True, "exit_code": 0, "stderr": "",
                "stdout": "__MINIAPP_STATE__:" + json.dumps({
                    "state": state_out if state_out is not None else inputs.get("state", {}),
                    "storage_ops": storage_ops,
                    "record_ops": [],
                }),
                "metadata": {},
                "truncated": False,
            })()
    monkeypatch.setattr(svc, "get_miniapp_runtime", FakeRuntime)


# ---------------------------------------------------------------------------
# Bug 1: storage.enabled kill switch
# ---------------------------------------------------------------------------
class TestStorageKillSwitch:
    @pytest.mark.asyncio
    async def test_disabled_manifest_rejects_ops(self, db_session, monkeypatch):
        import core.mini_app_service as svc
        _, cid = _make_app(db_session, storage_cfg={"enabled": False, "backend": "local"})
        _fake_runtime(monkeypatch, [{"op": "put", "key": "k", "data": "x"}])
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(cid, user_id="u1", scopes=("*",))
        assert result["success"]
        assert result["op_results"][0]["ok"] is False
        assert result["op_results"][0]["error"] == "storage_disabled"

    @pytest.mark.asyncio
    async def test_enabled_manifest_allows_ops(self, db_session, monkeypatch, tmp_path):
        import core.mini_app_service as svc
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path))
        _, cid = _make_app(db_session, storage_cfg={"enabled": True, "backend": "local"})
        _fake_runtime(monkeypatch, [{"op": "put", "key": "k", "data": "x"}])
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(cid, user_id="u1", scopes=("*",))
        assert result["op_results"][0]["ok"] is True


# ---------------------------------------------------------------------------
# Bug 2: cap parity (storage_ops uses upload cap when manifest omits it)
# ---------------------------------------------------------------------------
class TestStorageCapParity:
    @pytest.mark.asyncio
    async def test_default_cap_is_upload_cap_not_injection_cap(self, db_session, monkeypatch, tmp_path):
        """An asset between 5–10 MiB must succeed via storage_ops when the
        manifest doesn't override max_bytes_per_object (previously silently
        dropped because the default was 5 MiB)."""
        import core.mini_app_service as svc
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path))
        # manifest.storage has NO max_bytes_per_object → must default to upload cap
        _, cid = _make_app(db_session, storage_cfg={"enabled": True, "backend": "local"})
        # 6 MiB — over the old 5 MiB injection cap, under the 50 MiB upload cap
        payload = "a" * (6 * 1024 * 1024)
        _fake_runtime(monkeypatch, [{"op": "put", "key": "big.bin", "data": payload}])
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(cid, user_id="u1", scopes=("*",))
        assert result["op_results"][0]["ok"] is True, result["op_results"]


# ---------------------------------------------------------------------------
# Bug 3: lossless get (base64, not utf-8 errors=replace)
# ---------------------------------------------------------------------------
class TestStorageGetLossless:
    @pytest.mark.asyncio
    async def test_binary_get_returns_base64(self, db_session, monkeypatch, tmp_path):
        """A binary asset put via storage_ops must round-trip losslessly via get
        (base64), not be corrupted by utf-8(errors='replace')."""
        import core.mini_app_service as svc
        from core.mini_app_storage import MINIAPP_STORAGE_LOCAL_ROOT
        from core.models import MiniAppAsset
        monkeypatch.setenv(MINIAPP_STORAGE_LOCAL_ROOT, str(tmp_path))
        _, cid = _make_app(db_session)
        # Binary bytes that would corrupt under utf-8 replace (invalid sequences)
        raw = bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0xff, 0xfe])  # PNG-ish + invalid
        # Seed the asset via a put op with base64 encoding (binary-safe channel)
        _fake_runtime(monkeypatch, [{"op": "put", "key": "img.png",
                                      "data": base64.b64encode(raw).decode(),
                                      "encoding": "base64",
                                      "content_type": "image/png"}])
        _patch_db(monkeypatch, db_session)
        await svc.run_stateful(cid, user_id="u1", scopes=("*",))

        # Now a get op in a fresh run — must return base64 that decodes to raw
        _fake_runtime(monkeypatch, [{"op": "get", "key": "img.png"}])
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(cid, user_id="u1", scopes=("*",))
        get_result = result["op_results"][0]
        assert get_result["ok"] is True
        assert get_result["encoding"] == "base64"
        assert base64.b64decode(get_result["data"]) == raw  # lossless round-trip
